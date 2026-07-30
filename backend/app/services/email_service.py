from __future__ import annotations

import asyncio
import html
import smtplib
from email.message import EmailMessage

from app.core.config import settings
from app.core.exceptions import AppError


def _send_message(message: EmailMessage) -> None:
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as smtp:
        smtp.ehlo()
        if settings.SMTP_USE_TLS:
            smtp.starttls()
            smtp.ehlo()
        smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        smtp.send_message(message)


async def send_email(to_email: str, subject: str, text_body: str, html_body: str) -> None:
    if not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD or not settings.SMTP_FROM_EMAIL:
        raise AppError("Dich vu email chua duoc cau hinh", status_code=503)

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    message["To"] = to_email
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    try:
        await asyncio.to_thread(_send_message, message)
    except (OSError, smtplib.SMTPException) as exc:
        raise AppError("Khong the gui email, vui long thu lai sau", status_code=503) from exc


async def send_verification_email(to_email: str, full_name: str, token: str) -> None:
    verification_url = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/verify-email?token={token}"
    safe_name = html.escape(full_name)
    safe_url = html.escape(verification_url, quote=True)
    await send_email(
        to_email,
        "Xac minh email Smart Travel PKA",
        f"Xin chao {full_name},\n\nXac minh email tai: {verification_url}\nLien ket co hieu luc trong 24 gio.",
        f"""
        <div style="font-family:Arial,sans-serif;max-width:560px;margin:auto;color:#172033">
          <h2 style="color:#2563eb">Smart Travel PKA</h2>
          <p>Xin chào <strong>{safe_name}</strong>,</p>
          <p>Hãy xác minh địa chỉ email để kích hoạt đầy đủ tài khoản của bạn.</p>
          <p style="margin:28px 0"><a href="{safe_url}" style="background:#2563eb;color:#fff;padding:12px 20px;border-radius:10px;text-decoration:none;font-weight:bold">Xác minh email</a></p>
          <p style="font-size:13px;color:#64748b">Liên kết có hiệu lực trong 24 giờ và chỉ sử dụng được một lần.</p>
        </div>
        """,
    )


async def send_trip_invite_email(
    to_email: str,
    recipient_name: str,
    inviter_name: str,
    trip_title: str,
    destination: str,
    role: str,
    token: str,
) -> None:
    invite_url = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/trip-invites/{token}"
    safe_url = html.escape(invite_url, quote=True)
    await send_email(
        to_email,
        f"Loi moi tham gia chuyen di: {trip_title}",
        f"{inviter_name} moi ban tham gia {trip_title} tai {destination}. Mo loi moi: {invite_url}",
        f"""
        <div style="font-family:Arial,sans-serif;max-width:560px;margin:auto;color:#172033">
          <h2 style="color:#2563eb">Smart Travel PKA</h2>
          <p>Xin chào <strong>{html.escape(recipient_name)}</strong>,</p>
          <p><strong>{html.escape(inviter_name)}</strong> đã mời bạn tham gia chuyến đi <strong>{html.escape(trip_title)}</strong>.</p>
          <p>Điểm đến: {html.escape(destination)}<br>Quyền: {"Có thể chỉnh sửa" if role == "editor" else "Chỉ xem"}</p>
          <p style="margin:28px 0"><a href="{safe_url}" style="background:#2563eb;color:#fff;padding:12px 20px;border-radius:10px;text-decoration:none;font-weight:bold">Xem lời mời</a></p>
        </div>
        """,
    )
