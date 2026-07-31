"""Business logic - Module 6: Budget."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.budget import BudgetItem
from app.models.trip import Trip
from app.services import trip_share_service
from app.services import trip_history_service
from app.models.user import User
from app.schemas.budget import (
    CategoryBudgetSummary,
    CreateBudgetItemRequest,
    UpdateBudgetItemRequest,
    category_label,
)
from app.services.trip_service import get_trip_summary


async def get_budget_summary(db: AsyncSession, trip: Trip) -> dict:
    """GET /trips/{id}/budget - tai su dung logic tinh tu trip_service, dinh dang lai theo spec budget."""
    summary = await get_trip_summary(db, trip)

    categories = [
        CategoryBudgetSummary(
            category=category,
            label=category_label(category),
            planned=brief.planned,
            actual=brief.actual,
            itinerary_planned=brief.itinerary_planned,
            items_count=summary["_items_count_by_category"].get(category, 0),
        )
        for category, brief in summary["by_category"].items()
    ]

    return {
        "trip_id": trip.id,
        "budget_total": trip.budget,
        "budget_planned": summary["budget_planned"],
        "budget_actual": summary["budget_actual"],
        "budget_remaining": summary["budget_remaining"],
        "budget_itinerary_planned": summary["budget_itinerary_planned"],
        "overspent": summary["overspent"],
        "categories": categories,
    }


async def get_group_split_summary(db: AsyncSession, trip: Trip) -> dict:
    """GET /trips/{trip_id}/budget/split-summary - Tinh toan quyet toan no nhom bang Thuat toan Min-Cash-Flow."""
    # 1. Lay danh sach thanh vien tham gia
    owner_stmt = select(User).where(User.id == trip.user_id)
    res_owner = await db.execute(owner_stmt)
    owner = res_owner.scalar_one_or_none()
    owner_name = (owner.full_name if owner and owner.full_name else None) or (owner.email.split('@')[0] if owner and owner.email else "Chủ chuyến đi")

    participants, _ = await trip_share_service.list_share_state(db, trip.id)
    
    member_names = [owner_name]
    for p in participants:
        if getattr(p, "user", None) and p.user:
            name = p.user.full_name or (p.user.email.split('@')[0] if p.user.email else p.user.username)
            if name and name not in member_names:
                member_names.append(name)

    needed = max(1, trip.num_travelers or 1)
    idx = 1
    while len(member_names) < needed:
        idx += 1
        name = f"Thành viên {idx}"
        if name not in member_names:
            member_names.append(name)

    # 2. Lay tat ca cac khoản chi
    items = await list_budget_items(db, trip.id, category=None)

    # 3. Thu gom va phan bo chi phi
    paid_map: dict[str, int] = {m: 0 for m in member_names}
    assigned_map: dict[str, int] = {m: 0 for m in member_names}

    total_actual = 0
    total_planned = 0

    for item in items:
        actual = item.actual_amount or 0
        planned = item.planned_amount or 0
        total_actual += actual
        total_planned += planned

        if actual <= 0:
            continue

        # Payer: Nguoi dung tien
        payer = item.paid_by if item.paid_by and item.paid_by in paid_map else owner_name
        paid_map[payer] = paid_map.get(payer, 0) + actual

        # Beneficiaries: Danh sach nguoi chiu chi phi
        parts = item.participants if item.participants and isinstance(item.participants, list) and len(item.participants) > 0 else member_names
        valid_parts = [p for p in parts if p in assigned_map]
        if not valid_parts:
            valid_parts = member_names

        share_per_person = round(actual / len(valid_parts))
        for p in valid_parts:
            assigned_map[p] = assigned_map.get(p, 0) + share_per_person

    # 4. Tinh Net Balance = Paid - Assigned
    balances: list[dict] = []
    net_map: dict[str, int] = {}
    for m in member_names:
        p_val = paid_map.get(m, 0)
        a_val = assigned_map.get(m, 0)
        net = p_val - a_val
        net_map[m] = net
        balances.append({
            "name": m,
            "paid_amount": p_val,
            "assigned_amount": a_val,
            "net_balance": net
        })

    # 5. THUẬT TOÁN MIN-CASH-FLOW (Debt Minimization Algorithm)
    debtors = [{"name": m, "amount": -net_map[m]} for m in member_names if net_map[m] < -1]
    creditors = [{"name": m, "amount": net_map[m]} for m in member_names if net_map[m] > 1]

    debtors.sort(key=lambda x: x["amount"], reverse=True)
    creditors.sort(key=lambda x: x["amount"], reverse=True)

    settlements: list[dict] = []
    i, j = 0, 0
    while i < len(debtors) and j < len(creditors):
        debtor = debtors[i]
        creditor = creditors[j]

        settle_amt = min(debtor["amount"], creditor["amount"])
        if settle_amt > 0:
            settlements.append({
                "from_name": debtor["name"],
                "to_name": creditor["name"],
                "amount": settle_amt
            })
            debtor["amount"] -= settle_amt
            creditor["amount"] -= settle_amt

        if debtor["amount"] <= 1:
            i += 1
        if creditor["amount"] <= 1:
            j += 1

    return {
        "trip_id": trip.id,
        "companions_count": len(member_names),
        "members": member_names,
        "total_actual": total_actual,
        "total_planned": total_planned,
        "per_person_actual": round(total_actual / len(member_names)) if member_names else 0,
        "per_person_planned": round(total_planned / len(member_names)) if member_names else 0,
        "members_summary": balances,
        "settlements": settlements,
        "currency": "VND"
    }




async def list_budget_items(db: AsyncSession, trip_id: uuid.UUID, category: str | None) -> list[BudgetItem]:
    """GET /trips/{id}/budget/items - filter theo category (optional)."""
    query = select(BudgetItem).where(BudgetItem.trip_id == trip_id)
    if category:
        query = query.where(BudgetItem.category == category)

    result = await db.execute(query.order_by(BudgetItem.date.desc().nullslast(), BudgetItem.created_at.desc()))
    return list(result.scalars().all())


async def create_budget_item(
    db: AsyncSession,
    trip_id: uuid.UUID,
    payload: CreateBudgetItemRequest,
    actor: User,
) -> BudgetItem:
    item = BudgetItem(trip_id=trip_id, **payload.model_dump())
    db.add(item)
    await db.flush()
    await trip_history_service.record_history_event(
        db,
        trip_id=trip_id,
        actor_user_id=actor.id,
        entity_type="budget_item",
        entity_id=item.id,
        action="created",
        summary=f"Da them khoan chi \"{item.label}\"",
        metadata={"label": item.label, "category": item.category},
    )
    await db.commit()
    await db.refresh(item)
    return item


async def get_budget_item_owned_or_404(db: AsyncSession, item_id: uuid.UUID, user_id: uuid.UUID) -> BudgetItem:
    """Lay budget_item + kiem tra quyen so huu qua chain item -> trip -> user."""
    result = await db.execute(
        select(BudgetItem)
        .join(Trip, BudgetItem.trip_id == Trip.id)
        .where(BudgetItem.id == item_id, Trip.user_id == user_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise NotFoundError("Khong tim thay khoan chi nay")
    return item


async def get_budget_item_editable_or_404(db: AsyncSession, item_id: uuid.UUID, user_id: uuid.UUID) -> BudgetItem:
    result = await db.execute(select(BudgetItem).where(BudgetItem.id == item_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise NotFoundError("Khong tim thay khoan chi nay")
    if not await trip_share_service.user_can_edit_trip(db, item.trip_id, user_id):
        raise ForbiddenError("Ban khong co quyen chinh sua khoan chi nay")
    return item


async def update_budget_item(
    db: AsyncSession,
    item: BudgetItem,
    payload: UpdateBudgetItemRequest,
    actor: User,
) -> BudgetItem:
    tracked_fields = list(trip_history_service.BUDGET_FIELD_LABELS.keys())
    before = trip_history_service.snapshot_fields(item, tracked_fields)
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)

    await db.flush()
    after = trip_history_service.snapshot_fields(item, tracked_fields)
    changes = trip_history_service.diff_snapshots(
        before,
        after,
        trip_history_service.BUDGET_FIELD_LABELS,
    )
    if changes:
        await trip_history_service.record_history_event(
            db,
            trip_id=item.trip_id,
            actor_user_id=actor.id,
            entity_type="budget_item",
            entity_id=item.id,
            action="updated",
            summary=f"Da cap nhat khoan chi \"{item.label}\"",
            changes=changes,
        )
    await db.commit()
    await db.refresh(item)
    return item


async def delete_budget_item(db: AsyncSession, item: BudgetItem, actor: User) -> None:
    await trip_history_service.record_history_event(
        db,
        trip_id=item.trip_id,
        actor_user_id=actor.id,
        entity_type="budget_item",
        entity_id=item.id,
        action="deleted",
        summary=f"Da xoa khoan chi \"{item.label}\"",
        metadata={"label": item.label, "category": item.category},
    )
    await db.delete(item)
    await db.commit()
