"""Normalize Vietnamese destination names across the 63-province and 34-province datasets."""
from __future__ import annotations

import re
import unicodedata


def normalize_vietnamese(value: str) -> str:
    normalized = unicodedata.normalize("NFD", (value or "").lower())
    without_marks = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    without_marks = without_marks.replace("đ", "d")
    return re.sub(r"[^a-z0-9]+", " ", without_marks).strip()


# Current province/city -> source provinces in the legacy 63-province dataset.
CURRENT_TO_LEGACY: dict[str, tuple[str, ...]] = {
    "Tuyên Quang": ("Tuyên Quang", "Hà Giang"),
    "Lào Cai": ("Lào Cai", "Yên Bái"),
    "Thái Nguyên": ("Thái Nguyên", "Bắc Kạn"),
    "Phú Thọ": ("Phú Thọ", "Vĩnh Phúc", "Hòa Bình"),
    "Bắc Ninh": ("Bắc Ninh", "Bắc Giang"),
    "Hưng Yên": ("Hưng Yên", "Thái Bình"),
    "Hải Phòng": ("Hải Phòng", "Hải Dương"),
    "Ninh Bình": ("Ninh Bình", "Hà Nam", "Nam Định"),
    "Quảng Trị": ("Quảng Trị", "Quảng Bình"),
    "Đà Nẵng": ("Đà Nẵng", "Quảng Nam"),
    "Quảng Ngãi": ("Quảng Ngãi", "Kon Tum"),
    "Gia Lai": ("Gia Lai", "Bình Định"),
    "Khánh Hòa": ("Khánh Hòa", "Ninh Thuận"),
    "Lâm Đồng": ("Lâm Đồng", "Đắk Nông", "Bình Thuận"),
    "Đắk Lắk": ("Đắk Lắk", "Phú Yên"),
    "Thành phố Hồ Chí Minh": ("Thành phố Hồ Chí Minh", "Bình Dương", "Bà Rịa - Vũng Tàu"),
    "Đồng Nai": ("Đồng Nai", "Bình Phước"),
    "Tây Ninh": ("Tây Ninh", "Long An"),
    "Cần Thơ": ("Cần Thơ", "Sóc Trăng", "Hậu Giang"),
    "Vĩnh Long": ("Vĩnh Long", "Bến Tre", "Trà Vinh"),
    "Đồng Tháp": ("Đồng Tháp", "Tiền Giang"),
    "Cà Mau": ("Cà Mau", "Bạc Liêu"),
    "An Giang": ("An Giang", "Kiên Giang"),
    "Hà Nội": ("Hà Nội",),
    "Huế": ("Thừa Thiên Huế", "Huế"),
    "Quảng Ninh": ("Quảng Ninh",),
    "Thanh Hóa": ("Thanh Hóa",),
    "Nghệ An": ("Nghệ An",),
    "Hà Tĩnh": ("Hà Tĩnh",),
    "Cao Bằng": ("Cao Bằng",),
    "Lạng Sơn": ("Lạng Sơn",),
    "Điện Biên": ("Điện Biên",),
    "Lai Châu": ("Lai Châu",),
    "Sơn La": ("Sơn La",),
}

_EXTRA_ALIASES = {
    "tp hcm": "Thành phố Hồ Chí Minh",
    "tphcm": "Thành phố Hồ Chí Minh",
    "ho chi minh": "Thành phố Hồ Chí Minh",
    "sai gon": "Thành phố Hồ Chí Minh",
    "thua thien hue": "Huế",
    "ba ria vung tau": "Thành phố Hồ Chí Minh",
    "vung tau": "Thành phố Hồ Chí Minh",
    "dak lak": "Đắk Lắk",
    "dac lak": "Đắk Lắk",
    "dak nong": "Lâm Đồng",
    "quan lan": "Quảng Ninh",
    "co to": "Quảng Ninh",
    "van don": "Quảng Ninh",
    "ha long": "Quảng Ninh",
    "phu quoc": "Kiên Giang",
    "hoi an": "Đà Nẵng",
    "sa pa": "Lào Cai",
    "sapa": "Lào Cai",
    "da lat": "Lâm Đồng",
    "dalat": "Lâm Đồng",
    "nha trang": "Khánh Hòa",
    "phan thiet": "Lâm Đồng",
    "quy nhon": "Gia Lai",
}


def province_search_names(destination: str) -> list[str]:
    """Return legacy province names that should be searched for a destination."""
    if not destination:
        return []

    raw_dest = destination.strip()
    candidates: list[str] = [raw_dest]

    # Handle formats like "Quan Lạn (Quảng Ninh)" or "Quan Lạn, Quảng Ninh"
    match_paren = re.search(r"\(([^)]+)\)", raw_dest)
    if match_paren:
        candidates.append(match_paren.group(1).strip())

    if "," in raw_dest:
        parts = [p.strip() for p in raw_dest.split(",") if p.strip()]
        candidates.extend(reversed(parts))

    for cand in candidates:
        key = normalize_vietnamese(cand)
        for prefix in ("thanh pho ", "tinh ", "huyen ", "xa ", "dao "):
            if key.startswith(prefix):
                key = key[len(prefix):]

        current_name = _EXTRA_ALIASES.get(key)
        if current_name is not None:
            return list(CURRENT_TO_LEGACY[current_name])

        for current, legacy_names in CURRENT_TO_LEGACY.items():
            names = (current, *legacy_names)
            if any(normalize_vietnamese(name) == key for name in names):
                exact_legacy = next(
                    (name for name in legacy_names if normalize_vietnamese(name) == key),
                    None,
                )
                return [exact_legacy] if exact_legacy and normalize_vietnamese(current) != key else list(legacy_names)

        # Check substring match (e.g. "quang ninh" inside "quan lan quang ninh")
        for current, legacy_names in CURRENT_TO_LEGACY.items():
            names = (current, *legacy_names)
            for name in names:
                norm_name = normalize_vietnamese(name)
                if len(norm_name) >= 4 and norm_name in key:
                    return list(legacy_names)

    return [raw_dest]


def current_province_name(source_name: str) -> str:
    key = normalize_vietnamese(source_name)
    for current, legacy_names in CURRENT_TO_LEGACY.items():
        if any(normalize_vietnamese(name) == key for name in legacy_names):
            return current
    return source_name
