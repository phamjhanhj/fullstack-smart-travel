import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.location import Location
from app.models.public_trip import PublicTripPublication
from app.models.user import User


# -----------------------------------------------------------------------------
# HA GIANG - DONG VAN - LUNG CU - MA PI LENG 3D2N SEED DATA
#
# Tourism naming policy:
# - "Ha Giang" is retained as the established destination/brand name.
# - After the 2025 provincial reorganisation, the former Ha Giang area belongs
#   to Tuyen Quang Province. Therefore province_name is stored as "Tuyên Quang"
#   for database consistency, while titles, tags and summaries retain "Hà Giang".
#
# Itinerary basis:
# - Public Hanoi - Ha Giang 3-day/2-night tours published for 2026.
# - Day 1: Hanoi - Ha Giang city - Quan Ba - Yen Minh.
# - Day 2: Yen Minh - Tham Ma - Lung Cam - Sa Phin - Lung Cu - Dong Van.
# - Day 3: Dong Van - Ma Pi Leng - Nho Que River - Ha Giang - Hanoi.
#
# Coordinate policy:
# - POIs use public OpenStreetMap/Mapcarta nodes, Wikidata, published coordinates
#   and public map pins.
# - Large places use a clearly described representative point or access point.
# - Nho Que uses a representative boat-stop point west of Nho Que 1 hydropower
#   station; travellers must confirm the operating wharf before departure.
# - Every location includes a Google Maps coordinate URL for manual review.
# - Coordinates were last reviewed on 2026-07-30.
#
# Cost policy:
# - actual_cost is the estimated cost PER PERSON for this demo itinerary.
# - Costs are not binding supplier quotations and can change by season/date.
# -----------------------------------------------------------------------------

VERIFIED_AT = "2026-07-30"
NUMBER_OF_TRAVELERS = 2
CURRENT_PROVINCE_NAME = "Tuyên Quang"


LOCATIONS: dict[str, dict[str, Any]] = {
    "ha_noi_opera_house": {
        "id": "66666666-6666-4666-8666-000000000001",
        "name": "Nhà hát Lớn Hà Nội",
        "address": "1 Tràng Tiền, phường Cửa Nam, Hà Nội",
        "lat": 21.024376,
        "lng": 105.857299,
        "category": "transport",
        "province_name": "Hà Nội",
        "coordinate_precision": "poi_pin",
        "coordinate_source": "Google Maps public place pin",
        "google_maps_url": "https://www.google.com/maps?q=21.024376,105.857299",
        "verified_at": VERIFIED_AT,
    },
    "ha_giang_city_center": {
        "id": "66666666-6666-4666-8666-000000000002",
        "name": "Khu trung tâm Hà Giang",
        "address": "Khu vực phường Hà Giang 1 - Hà Giang 2, tỉnh Tuyên Quang",
        "lat": 22.82665,
        "lng": 104.98335,
        "category": "restaurant",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "city_center_representative_point",
        "coordinate_source": "Representative point beside March 26 Square and Nguyen Trai corridor",
        "google_maps_url": "https://www.google.com/maps?q=22.82665,104.98335",
        "verified_at": VERIFIED_AT,
    },
    "ha_giang_km0": {
        "id": "66666666-6666-4666-8666-000000000003",
        "name": "Cột mốc Km 0 Hà Giang",
        "address": "Đường Nguyễn Trãi, khu vực Quảng trường 26-3, Hà Giang, Tuyên Quang",
        "lat": 22.827312,
        "lng": 104.984136,
        "category": "attraction",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "poi_pin",
        "coordinate_source": "Public map pin for Km 0 Ha Giang",
        "google_maps_url": "https://www.google.com/maps?q=22.827312,104.984136",
        "verified_at": VERIFIED_AT,
    },
    "quan_ba_heaven_gate": {
        "id": "66666666-6666-4666-8666-000000000004",
        "name": "Cổng trời Quản Bạ",
        "address": "Quốc lộ 4C, khu vực Quản Bạ, tỉnh Tuyên Quang",
        "lat": 23.04932,
        "lng": 104.99302,
        "category": "attraction",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "scenic_viewpoint_pin",
        "coordinate_source": "OpenStreetMap node 5724377221 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=23.04932,104.99302",
        "plus_code": "7PM62XXV+P6",
        "verified_at": VERIFIED_AT,
    },
    "quan_ba_twin_mountains": {
        "id": "66666666-6666-4666-8666-000000000005",
        "name": "Điểm ngắm Núi đôi Quản Bạ - Núi Cô Tiên",
        "address": "Quốc lộ 4C, khu vực Tam Sơn - Quản Bạ, tỉnh Tuyên Quang",
        "lat": 23.06524,
        "lng": 104.99305,
        "category": "attraction",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "viewpoint_representative_point",
        "coordinate_source": "Published public GPS point for Quan Ba Twin Mountains area",
        "google_maps_url": "https://www.google.com/maps?q=23.06524,104.99305",
        "verified_at": VERIFIED_AT,
    },
    "yen_minh_center": {
        "id": "66666666-6666-4666-8666-000000000006",
        "name": "Khu lưu trú trung tâm Yên Minh",
        "address": "Khu trung tâm Yên Minh, tỉnh Tuyên Quang",
        "lat": 23.1172,
        "lng": 105.1491,
        "category": "hotel",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "town_center",
        "coordinate_source": "OpenStreetMap town node 369504296 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=23.1172,105.1491",
        "plus_code": "7PM7448X+VJ",
        "verified_at": VERIFIED_AT,
    },
    "tham_ma_pass": {
        "id": "66666666-6666-4666-8666-000000000007",
        "name": "Dốc Thẩm Mã",
        "address": "Quốc lộ 4C, khu vực Phố Bảng - Đồng Văn, tỉnh Tuyên Quang",
        "lat": 23.169417,
        "lng": 105.194803,
        "category": "attraction",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "scenic_road_viewpoint_pin",
        "coordinate_source": "Published public place coordinate",
        "google_maps_url": "https://www.google.com/maps?q=23.169417,105.194803",
        "verified_at": VERIFIED_AT,
    },
    "pao_house": {
        "id": "66666666-6666-4666-8666-000000000008",
        "name": "Nhà của Pao - Làng văn hóa Lũng Cẩm",
        "address": "Thôn Lũng Cẩm Trên, khu vực Sủng Là, Đồng Văn, tỉnh Tuyên Quang",
        "lat": 23.22714,
        "lng": 105.20236,
        "category": "attraction",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "poi_pin",
        "coordinate_source": "OpenStreetMap node 5793805253 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=23.22714,105.20236",
        "plus_code": "7PM766G2+VW",
        "verified_at": VERIFIED_AT,
    },
    "vuong_palace": {
        "id": "66666666-6666-4666-8666-000000000009",
        "name": "Dinh thự họ Vương - Dinh Vua Mèo",
        "address": "Sà Phìn, khu vực Đồng Văn, tỉnh Tuyên Quang",
        "lat": 23.25625,
        "lng": 105.26209,
        "category": "attraction",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "poi_pin",
        "coordinate_source": "OpenStreetMap node 7975480201 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=23.25625,105.26209",
        "plus_code": "7PM77746+FR",
        "verified_at": VERIFIED_AT,
    },
    "lung_cu_flag_tower": {
        "id": "66666666-6666-4666-8666-000000000010",
        "name": "Cột cờ Lũng Cú",
        "address": "Đỉnh núi Rồng, Lũng Cú, khu vực Đồng Văn, tỉnh Tuyên Quang",
        "lat": 23.36346,
        "lng": 105.31633,
        "category": "attraction",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "monument_pin",
        "coordinate_source": "OpenStreetMap way 504649258 via Mapcarta; cross-checked with published DMS coordinate",
        "google_maps_url": "https://www.google.com/maps?q=23.36346,105.31633",
        "plus_code": "7PM79878+9G",
        "verified_at": VERIFIED_AT,
    },
    "lo_lo_chai": {
        "id": "66666666-6666-4666-8666-000000000011",
        "name": "Làng văn hóa Lô Lô Chải",
        "address": "Lô Lô Chải, Lũng Cú, khu vực Đồng Văn, tỉnh Tuyên Quang",
        "lat": 23.36418,
        "lng": 105.31006,
        "category": "attraction",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "village_center",
        "coordinate_source": "OpenStreetMap node 7962462262 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=23.36418,105.31006",
        "plus_code": "7PM79876+M2",
        "verified_at": VERIFIED_AT,
    },
    "dong_van_old_town": {
        "id": "66666666-6666-4666-8666-000000000012",
        "name": "Phố cổ Đồng Văn",
        "address": "Khu phố cổ Đồng Văn, tỉnh Tuyên Quang",
        "lat": 23.27967,
        "lng": 105.36078,
        "category": "attraction",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "old_town_center",
        "coordinate_source": "OpenStreetMap node 7961606192 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=23.27967,105.36078",
        "plus_code": "7PM779H6+V8",
        "verified_at": VERIFIED_AT,
    },
    "dong_van_accommodation": {
        "id": "66666666-6666-4666-8666-000000000013",
        "name": "Khu lưu trú trung tâm Đồng Văn",
        "address": "Khu trung tâm Đồng Văn, tỉnh Tuyên Quang",
        "lat": 23.2791,
        "lng": 105.3598,
        "category": "hotel",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "accommodation_area_representative_point",
        "coordinate_source": "Representative point adjacent to Dong Van Old Town",
        "google_maps_url": "https://www.google.com/maps?q=23.2791,105.3598",
        "verified_at": VERIFIED_AT,
    },
    "ma_pi_leng_viewpoint": {
        "id": "66666666-6666-4666-8666-000000000014",
        "name": "Điểm ngắm đèo Mã Pì Lèng",
        "address": "Đường Hạnh Phúc, khu vực Pải Lủng - Mèo Vạc, tỉnh Tuyên Quang",
        "lat": 23.24062,
        "lng": 105.41208,
        "category": "attraction",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "scenic_viewpoint_pin",
        "coordinate_source": "OpenStreetMap node 3282165789 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=23.24062,105.41208",
        "plus_code": "7PM76CR6+6R",
        "verified_at": VERIFIED_AT,
    },
    "nho_que_boat_stop": {
        "id": "66666666-6666-4666-8666-000000000015",
        "name": "Điểm lên thuyền sông Nho Quế - khu vực Tu Sản",
        "address": "Khu vực bến thuyền Tu Sản/Nho Quế 1, Mèo Vạc, tỉnh Tuyên Quang",
        "lat": 23.23025,
        "lng": 105.4266,
        "category": "attraction",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "boat_stop_representative_point",
        "coordinate_source": (
            "Representative point approximately 450 m west of mapped Nho Que 1 hydropower station; "
            "confirm the active wharf with the operator"
        ),
        "google_maps_url": "https://www.google.com/maps?q=23.23025,105.4266",
        "verified_at": VERIFIED_AT,
    },
}


def build_activity(
    *,
    location_key: str,
    start_time: str,
    end_time: str,
    title: str,
    activity_type: str,
    actual_cost: int,
    rating: float,
    author_verdict: str,
    best_time: str,
    next_traveler_note: str,
) -> dict[str, Any]:
    """Build an activity while synchronising location_id and coordinates."""
    location = LOCATIONS[location_key]
    return {
        "location_id": location["id"],
        "lat": location["lat"],
        "lng": location["lng"],
        "start_time": start_time,
        "end_time": end_time,
        "title": title,
        "type": activity_type,
        "address": location["address"],
        "actual_cost": actual_cost,
        "rating": rating,
        "author_verdict": author_verdict,
        "best_time": best_time,
        "next_traveler_note": next_traveler_note,
    }


HA_GIANG_SNAPSHOT: dict[str, Any] = {
    "title": "Lịch trình Hà Giang - Đồng Văn - Lũng Cú 3 ngày 2 đêm từ Hà Nội",
    "destination": "Khu vực Hà Giang, tỉnh Tuyên Quang",
    "tourism_destination_name": "Hà Giang",
    "duration_days": 3,
    "traveler_count": NUMBER_OF_TRAVELERS,
    "actual_cost_per_person": 4_300_000,
    "actual_total_cost": 8_600_000,
    "overall_rating": 4.9,
    "coordinate_verified_at": VERIFIED_AT,
    "administrative_note": (
        "Hà Giang được giữ trong tên hành trình như một địa danh du lịch quen thuộc. "
        "Theo đơn vị hành chính hiện hành sau sắp xếp năm 2025, khu vực này thuộc tỉnh Tuyên Quang."
    ),
    "cost_note": (
        "Chi phí là dữ liệu seed tham khảo theo người cho nhóm 2 người, không phải báo giá cố định. "
        "Giá xe, phòng, vé thuyền, vé tham quan và dịch vụ trung chuyển có thể thay đổi theo mùa, "
        "ngày lễ, điều kiện thời tiết và bến thuyền đang vận hành."
    ),
    "budget_breakdown_per_person": {
        "transport": 1_750_000,
        "lodging": 600_000,
        "food": 1_450_000,
        "tours_and_tickets": 300_000,
        "shopping_and_miscellaneous": 200_000,
        "total": 4_300_000,
    },
    "days": [
        {
            "day_number": 1,
            "title": "Hà Nội - Hà Giang - Cổng trời Quản Bạ - Yên Minh",
            "activities": [
                build_activity(
                    location_key="ha_noi_opera_house",
                    start_time="04:45",
                    end_time="05:20",
                    title="Tập trung và ăn sáng nhẹ tại Nhà hát Lớn Hà Nội",
                    activity_type="meal",
                    actual_cost=50_000,
                    rating=4.7,
                    author_verdict="recommended",
                    best_time="Có mặt trước giờ xe chạy tối thiểu 15 phút",
                    next_traveler_note="Mang áo khoác, thuốc say xe và nước uống; không ăn quá no trước hành trình dài.",
                ),
                build_activity(
                    location_key="ha_giang_city_center",
                    start_time="05:30",
                    end_time="12:00",
                    title="Xe du lịch Hà Nội - khu vực Hà Giang",
                    activity_type="transport",
                    actual_cost=380_000,
                    rating=4.8,
                    author_verdict="must_go",
                    best_time="Khởi hành trước 06:00",
                    next_traveler_note="Thời gian phụ thuộc giao thông và điểm nghỉ; nên chọn xe có dây an toàn và tài xế quen đường núi.",
                ),
                build_activity(
                    location_key="ha_giang_city_center",
                    start_time="12:00",
                    end_time="13:00",
                    title="Ăn trưa tại trung tâm Hà Giang",
                    activity_type="meal",
                    actual_cost=180_000,
                    rating=4.7,
                    author_verdict="recommended",
                    best_time="Ăn trước khi bắt đầu Quốc lộ 4C",
                    next_traveler_note="Chọn món chín, dễ tiêu; hạn chế đồ uống có cồn trước khi đi đường đèo.",
                ),
                build_activity(
                    location_key="ha_giang_km0",
                    start_time="13:00",
                    end_time="13:25",
                    title="Check-in Cột mốc Km 0 Hà Giang",
                    activity_type="attraction",
                    actual_cost=0,
                    rating=4.8,
                    author_verdict="must_go",
                    best_time="Đầu hành trình vòng cung Hà Giang",
                    next_traveler_note="Không đứng tràn xuống lòng đường; chụp nhanh và giữ lối cho các đoàn khác.",
                ),
                build_activity(
                    location_key="quan_ba_heaven_gate",
                    start_time="13:25",
                    end_time="15:00",
                    title="Di chuyển từ Hà Giang tới Cổng trời Quản Bạ",
                    activity_type="transport",
                    actual_cost=100_000,
                    rating=4.8,
                    author_verdict="must_go",
                    best_time="Đi ban ngày khi tầm nhìn tốt",
                    next_traveler_note="Đoạn Bắc Sum nhiều cua; không nên tự lái xe máy nếu thiếu kinh nghiệm đường đèo hoặc gặp sương dày.",
                ),
                build_activity(
                    location_key="quan_ba_heaven_gate",
                    start_time="15:00",
                    end_time="15:40",
                    title="Ngắm toàn cảnh từ Cổng trời Quản Bạ",
                    activity_type="attraction",
                    actual_cost=0,
                    rating=4.9,
                    author_verdict="must_go",
                    best_time="Chiều trời quang hoặc sáng sớm săn mây",
                    next_traveler_note="Chỉ đứng trong khu vực quan sát an toàn; gió mạnh và sương có thể làm mặt đường trơn.",
                ),
                build_activity(
                    location_key="quan_ba_twin_mountains",
                    start_time="15:50",
                    end_time="16:25",
                    title="Ngắm Núi đôi Quản Bạ - Núi Cô Tiên",
                    activity_type="attraction",
                    actual_cost=0,
                    rating=4.8,
                    author_verdict="must_go",
                    best_time="Chiều nắng dịu",
                    next_traveler_note="Tọa độ là điểm ngắm đại diện; không tự ý đi vào ruộng hoặc khu canh tác của người dân.",
                ),
                build_activity(
                    location_key="yen_minh_center",
                    start_time="16:25",
                    end_time="18:00",
                    title="Di chuyển Quản Bạ - Yên Minh",
                    activity_type="transport",
                    actual_cost=80_000,
                    rating=4.7,
                    author_verdict="must_go",
                    best_time="Hoàn thành trước khi trời tối",
                    next_traveler_note="Không cố chạy nhanh để kịp lịch; luôn ưu tiên an toàn nếu mưa, sương hoặc có đá rơi.",
                ),
                build_activity(
                    location_key="yen_minh_center",
                    start_time="18:00",
                    end_time="18:30",
                    title="Nhận phòng nghỉ đêm tại Yên Minh",
                    activity_type="lodging",
                    actual_cost=300_000,
                    rating=4.6,
                    author_verdict="must_go",
                    best_time="Đặt phòng gần trung tâm, có chỗ đỗ xe",
                    next_traveler_note="Chi phí tính theo người, giả định 2 người ở chung phòng; kiểm tra nước nóng và giờ phục vụ bữa sáng.",
                ),
                build_activity(
                    location_key="yen_minh_center",
                    start_time="18:45",
                    end_time="20:00",
                    title="Ăn tối đặc sản vùng cao tại Yên Minh",
                    activity_type="meal",
                    actual_cost=220_000,
                    rating=4.8,
                    author_verdict="must_go",
                    best_time="Ăn sớm để nghỉ ngơi",
                    next_traveler_note="Gợi ý lợn bản, gà đen, rau cải mèo; hỏi rõ giá trước khi gọi món theo cân.",
                ),
                build_activity(
                    location_key="yen_minh_center",
                    start_time="20:00",
                    end_time="21:00",
                    title="Dạo trung tâm Yên Minh và mua đồ ăn nhẹ",
                    activity_type="meal",
                    actual_cost=60_000,
                    rating=4.5,
                    author_verdict="recommended",
                    best_time="Buổi tối mát",
                    next_traveler_note="Ngủ sớm vì ngày 2 có nhiều điểm; chuẩn bị tiền mặt nhỏ cho vé và hàng quán địa phương.",
                ),
            ],
        },
        {
            "day_number": 2,
            "title": "Yên Minh - Thẩm Mã - Nhà Pao - Dinh họ Vương - Lũng Cú - Đồng Văn",
            "activities": [
                build_activity(
                    location_key="yen_minh_center",
                    start_time="06:15",
                    end_time="06:55",
                    title="Ăn sáng và trả phòng tại Yên Minh",
                    activity_type="meal",
                    actual_cost=50_000,
                    rating=4.6,
                    author_verdict="recommended",
                    best_time="Ăn trước 07:00",
                    next_traveler_note="Mang theo nước và đồ ăn nhỏ; tuyến tiếp theo có nhiều điểm dừng nhưng ít cửa hàng lớn.",
                ),
                build_activity(
                    location_key="tham_ma_pass",
                    start_time="07:00",
                    end_time="08:20",
                    title="Di chuyển Yên Minh - Dốc Thẩm Mã",
                    activity_type="transport",
                    actual_cost=80_000,
                    rating=4.8,
                    author_verdict="must_go",
                    best_time="Buổi sáng khi tầm nhìn tốt",
                    next_traveler_note="Đường có cua tay áo; tuyệt đối không dừng xe tại điểm khuất hoặc giữa khúc cua.",
                ),
                build_activity(
                    location_key="tham_ma_pass",
                    start_time="08:20",
                    end_time="08:55",
                    title="Check-in Dốc Thẩm Mã",
                    activity_type="attraction",
                    actual_cost=0,
                    rating=4.9,
                    author_verdict="must_go",
                    best_time="Sáng sớm, ít xe",
                    next_traveler_note="Chụp tại khu dừng an toàn; không chụp trẻ em hoặc người dân khi chưa được đồng ý.",
                ),
                build_activity(
                    location_key="pao_house",
                    start_time="08:55",
                    end_time="09:20",
                    title="Di chuyển tới Làng văn hóa Lũng Cẩm",
                    activity_type="transport",
                    actual_cost=50_000,
                    rating=4.7,
                    author_verdict="recommended",
                    best_time="Buổi sáng",
                    next_traveler_note="Đi chậm qua khu dân cư, không bấm còi liên tục và không đỗ chắn lối nhà dân.",
                ),
                build_activity(
                    location_key="pao_house",
                    start_time="09:20",
                    end_time="10:10",
                    title="Tham quan Nhà của Pao và làng Lũng Cẩm",
                    activity_type="attraction",
                    actual_cost=30_000,
                    rating=4.8,
                    author_verdict="must_go",
                    best_time="Mùa hoa hoặc buổi sáng",
                    next_traveler_note="Giữ trật tự vì đây là không gian sinh hoạt cộng đồng; không tự ý chạm đồ thờ hoặc đi vào phòng riêng.",
                ),
                build_activity(
                    location_key="vuong_palace",
                    start_time="10:10",
                    end_time="10:35",
                    title="Di chuyển Lũng Cẩm - Sà Phìn",
                    activity_type="transport",
                    actual_cost=40_000,
                    rating=4.7,
                    author_verdict="recommended",
                    best_time="Trước giờ trưa",
                    next_traveler_note="Theo sát xe đoàn vì tín hiệu di động có thể yếu ở một số đoạn.",
                ),
                build_activity(
                    location_key="vuong_palace",
                    start_time="10:35",
                    end_time="11:35",
                    title="Tham quan Dinh thự họ Vương - Dinh Vua Mèo",
                    activity_type="attraction",
                    actual_cost=30_000,
                    rating=4.9,
                    author_verdict="must_go",
                    best_time="Buổi sáng hoặc đầu giờ chiều",
                    next_traveler_note="Không khắc, viết hoặc dựa mạnh vào kết cấu gỗ đá; nên nghe thuyết minh để hiểu giá trị lịch sử.",
                ),
                build_activity(
                    location_key="dong_van_old_town",
                    start_time="11:35",
                    end_time="12:30",
                    title="Di chuyển về Đồng Văn và ăn trưa",
                    activity_type="meal",
                    actual_cost=180_000,
                    rating=4.8,
                    author_verdict="must_go",
                    best_time="Ăn trước khi đi Lũng Cú",
                    next_traveler_note="Gợi ý thắng cố phiên bản dễ ăn, lẩu gà đen hoặc cơm địa phương; hỏi thành phần nếu dị ứng.",
                ),
                build_activity(
                    location_key="lung_cu_flag_tower",
                    start_time="12:45",
                    end_time="13:40",
                    title="Di chuyển Đồng Văn - Cột cờ Lũng Cú",
                    activity_type="transport",
                    actual_cost=80_000,
                    rating=4.8,
                    author_verdict="must_go",
                    best_time="Đi đầu giờ chiều, tránh tối muộn",
                    next_traveler_note="Khu vực gần biên giới; tuân thủ biển báo, không sử dụng flycam khi chưa được phép.",
                ),
                build_activity(
                    location_key="lung_cu_flag_tower",
                    start_time="13:40",
                    end_time="15:00",
                    title="Chinh phục Cột cờ Lũng Cú",
                    activity_type="attraction",
                    actual_cost=40_000,
                    rating=5.0,
                    author_verdict="must_go",
                    best_time="Trời quang, không mưa giông",
                    next_traveler_note="Có nhiều bậc thang; đi giày bám tốt, nghỉ giữa chặng nếu mệt và không chen lấn trên cầu thang xoắn.",
                ),
                build_activity(
                    location_key="lo_lo_chai",
                    start_time="15:10",
                    end_time="16:15",
                    title="Khám phá Làng văn hóa Lô Lô Chải",
                    activity_type="attraction",
                    actual_cost=50_000,
                    rating=4.9,
                    author_verdict="must_go",
                    best_time="Chiều nắng dịu",
                    next_traveler_note="Chi phí gồm đồ uống hoặc đóng góp dịch vụ cộng đồng; tôn trọng nhà trình tường và đời sống người dân.",
                ),
                build_activity(
                    location_key="dong_van_accommodation",
                    start_time="16:15",
                    end_time="17:30",
                    title="Trở về trung tâm Đồng Văn",
                    activity_type="transport",
                    actual_cost=80_000,
                    rating=4.7,
                    author_verdict="must_go",
                    best_time="Về trước khi trời tối",
                    next_traveler_note="Nếu có sương hoặc mưa, giảm tốc độ và bỏ bớt điểm dừng thay vì cố bám lịch.",
                ),
                build_activity(
                    location_key="dong_van_accommodation",
                    start_time="17:30",
                    end_time="18:00",
                    title="Nhận phòng nghỉ đêm tại Đồng Văn",
                    activity_type="lodging",
                    actual_cost=300_000,
                    rating=4.7,
                    author_verdict="must_go",
                    best_time="Chọn nơi đi bộ được tới phố cổ",
                    next_traveler_note="Chi phí tính theo người cho phòng 2 người; kiểm tra chỗ gửi hành lý và giờ trả phòng sáng hôm sau.",
                ),
                build_activity(
                    location_key="dong_van_old_town",
                    start_time="18:30",
                    end_time="19:45",
                    title="Ăn tối tại khu phố cổ Đồng Văn",
                    activity_type="meal",
                    actual_cost=220_000,
                    rating=4.8,
                    author_verdict="must_go",
                    best_time="Buổi tối se lạnh",
                    next_traveler_note="Có thể thử lẩu gà đen, thịt lợn bản, rau cải mèo; không uống rượu nếu sáng hôm sau tiếp tục đi đèo.",
                ),
                build_activity(
                    location_key="dong_van_old_town",
                    start_time="19:45",
                    end_time="21:15",
                    title="Dạo Phố cổ Đồng Văn và uống cà phê",
                    activity_type="attraction",
                    actual_cost=80_000,
                    rating=4.8,
                    author_verdict="recommended",
                    best_time="Tối cuối tuần hoặc đêm có chợ phiên",
                    next_traveler_note="Không mặc định chợ đêm hoạt động đầy đủ mọi ngày; giữ yên tĩnh gần khu lưu trú của người dân.",
                ),
            ],
        },
        {
            "day_number": 3,
            "title": "Đồng Văn - Mã Pì Lèng - sông Nho Quế - Hà Giang - Hà Nội",
            "activities": [
                build_activity(
                    location_key="dong_van_old_town",
                    start_time="05:45",
                    end_time="06:25",
                    title="Ăn sáng bánh cuốn trứng hoặc phở tại Đồng Văn",
                    activity_type="meal",
                    actual_cost=50_000,
                    rating=4.8,
                    author_verdict="recommended",
                    best_time="Ăn trước 06:30",
                    next_traveler_note="Chuẩn bị áo ấm và nước; gió trên đèo có thể lạnh ngay cả khi dưới thị trấn trời ấm.",
                ),
                build_activity(
                    location_key="ma_pi_leng_viewpoint",
                    start_time="06:30",
                    end_time="07:20",
                    title="Di chuyển Đồng Văn - đèo Mã Pì Lèng",
                    activity_type="transport",
                    actual_cost=80_000,
                    rating=4.9,
                    author_verdict="must_go",
                    best_time="Sáng sớm, ít xe và nắng dịu",
                    next_traveler_note="Đây là đường đèo hẹp sát vực; chỉ dừng tại điểm có chỗ đỗ và không vượt xe ở đoạn cua khuất.",
                ),
                build_activity(
                    location_key="ma_pi_leng_viewpoint",
                    start_time="07:20",
                    end_time="08:10",
                    title="Ngắm đèo Mã Pì Lèng và hẻm Tu Sản từ trên cao",
                    activity_type="attraction",
                    actual_cost=0,
                    rating=5.0,
                    author_verdict="must_go",
                    best_time="Trời quang, trước 09:00",
                    next_traveler_note="Không leo qua lan can hoặc đứng trên mỏm đá không được bảo vệ để chụp ảnh.",
                ),
                build_activity(
                    location_key="nho_que_boat_stop",
                    start_time="08:10",
                    end_time="09:00",
                    title="Trung chuyển xuống điểm lên thuyền sông Nho Quế",
                    activity_type="transport",
                    actual_cost=150_000,
                    rating=4.7,
                    author_verdict="must_go",
                    best_time="Đặt trước nhà thuyền và xe trung chuyển",
                    next_traveler_note="Đường xuống bến dốc và có thể thay đổi theo bến đang hoạt động; không tự lái xe ga nếu không quen đường.",
                ),
                build_activity(
                    location_key="nho_que_boat_stop",
                    start_time="09:00",
                    end_time="10:30",
                    title="Đi thuyền sông Nho Quế ngắm Hẻm Tu Sản",
                    activity_type="attraction",
                    actual_cost=150_000,
                    rating=5.0,
                    author_verdict="must_go",
                    best_time="Buổi sáng, ít mưa và gió",
                    next_traveler_note="Mặc áo phao suốt hành trình; xác nhận giá, thời lượng và bến trả khách trước khi xuống thuyền.",
                ),
                build_activity(
                    location_key="dong_van_old_town",
                    start_time="10:30",
                    end_time="11:30",
                    title="Trở lại Đồng Văn, lấy hành lý và trả phòng",
                    activity_type="transport",
                    actual_cost=0,
                    rating=4.6,
                    author_verdict="recommended",
                    best_time="Hoàn tất trước 11:30",
                    next_traveler_note="Thời gian có thể kéo dài nếu bến đông; nên gửi sẵn hành lý tại lễ tân và thanh toán phòng từ tối hôm trước.",
                ),
                build_activity(
                    location_key="dong_van_old_town",
                    start_time="11:30",
                    end_time="12:30",
                    title="Ăn trưa tại Đồng Văn",
                    activity_type="meal",
                    actual_cost=180_000,
                    rating=4.7,
                    author_verdict="recommended",
                    best_time="Ăn sớm trước chặng đường dài",
                    next_traveler_note="Ưu tiên món chín, dễ tiêu và hạn chế rượu bia trước khi về Hà Giang.",
                ),
                build_activity(
                    location_key="ha_giang_city_center",
                    start_time="12:30",
                    end_time="17:00",
                    title="Di chuyển Đồng Văn - Hà Giang",
                    activity_type="transport",
                    actual_cost=250_000,
                    rating=4.8,
                    author_verdict="must_go",
                    best_time="Rời Đồng Văn đầu giờ chiều",
                    next_traveler_note="Dự phòng thời gian do sương, mưa, công trình hoặc ùn xe; không ép tài xế chạy nhanh để kịp giờ.",
                ),
                build_activity(
                    location_key="yen_minh_center",
                    start_time="14:30",
                    end_time="15:00",
                    title="Nghỉ giữa đường và dùng đồ uống nhẹ",
                    activity_type="meal",
                    actual_cost=60_000,
                    rating=4.5,
                    author_verdict="recommended",
                    best_time="Nghỉ 20-30 phút",
                    next_traveler_note="Kiểm tra lại hành lý và không tách đoàn quá xa tại điểm nghỉ.",
                ),
                build_activity(
                    location_key="ha_giang_city_center",
                    start_time="17:00",
                    end_time="18:00",
                    title="Ăn tối sớm tại khu vực Hà Giang",
                    activity_type="meal",
                    actual_cost=120_000,
                    rating=4.6,
                    author_verdict="recommended",
                    best_time="Ăn trước chuyến xe về Hà Nội",
                    next_traveler_note="Chọn suất cơm hoặc món dễ tiêu; chuẩn bị đồ giữ ấm nếu đi xe tối.",
                ),
                build_activity(
                    location_key="ha_giang_city_center",
                    start_time="18:00",
                    end_time="18:30",
                    title="Mua đặc sản Hà Giang làm quà",
                    activity_type="shopping",
                    actual_cost=200_000,
                    rating=4.6,
                    author_verdict="recommended",
                    best_time="Mua tại cửa hàng có niêm yết giá",
                    next_traveler_note="Kiểm tra hạn sử dụng và bao bì; mật ong, thịt khô hoặc đồ lỏng cần đóng kín khi đi xe.",
                ),
                build_activity(
                    location_key="ha_noi_opera_house",
                    start_time="18:30",
                    end_time="23:30",
                    title="Xe Hà Giang - Hà Nội, kết thúc hành trình",
                    activity_type="transport",
                    actual_cost=380_000,
                    rating=4.8,
                    author_verdict="must_go",
                    best_time="Chuyến tối sau khi ăn",
                    next_traveler_note="Giờ đến có thể muộn hơn 30-60 phút; chuẩn bị phương án di chuyển từ điểm trả về nhà.",
                ),
            ],
        },
    ],
    "review": {
        "best_places": [
            "Cổng trời Quản Bạ",
            "Dốc Thẩm Mã",
            "Cột cờ Lũng Cú",
            "Làng văn hóa Lô Lô Chải",
            "Đèo Mã Pì Lèng",
            "Sông Nho Quế - Hẻm Tu Sản",
        ],
        "best_foods": [
            "Gà đen",
            "Lợn bản",
            "Rau cải mèo",
            "Bánh cuốn trứng Đồng Văn",
            "Cháo ấu tẩu",
        ],
        "tips": (
            "Ưu tiên xe du lịch hoặc tài xế địa phương quen đường; kiểm tra dự báo mưa, sương và cảnh báo sạt lở; "
            "không tự lái xe máy nếu thiếu kinh nghiệm đèo núi; mang giấy tờ tùy thân; tôn trọng khu vực biên giới, "
            "làng cộng đồng và nhà dân; xác nhận bến thuyền Nho Quế trước ngày đi."
        ),
    },
    "data_sources": {
        "itinerary_basis": [
            "https://hagiang.travel/tour-ha-giang-dong-van-nho-que-3-ngay/",
            "https://hagiangtour.vn/tour-ha-giang-3-ngay-2-dem-tu-ha-noi",
            "https://hanoietoco.com/dulich/du-lich-ha-giang-tour-ha-giang-3-ngay-119-253.html",
            "https://travelhanoi.com.vn/tour-dong-tay-bac/du-lich-ha-noi-ha-giang-dong-van-lung-cu-ma-pi-leng-3-ngay-2-dem-302-4694.html",
        ],
        "coordinate_basis": [
            "OpenStreetMap/Mapcarta POI nodes for Quan Ba, Yen Minh, Pao House, Vuong Palace, Lung Cu, Lo Lo Chai, Dong Van and Ma Pi Leng",
            "Published public GPS pins for Km 0, Tham Ma and Quan Ba Twin Mountains",
            "Representative access point for the Nho Que boat-stop area",
        ],
        "administrative_basis": [
            "https://xaydungchinhsach.chinhphu.vn/uy-ban-thuong-vu-quoc-hoi-cho-y-kien-ve-de-an-sap-xep-don-vi-hanh-chinh-cap-tinh-119250605174855605.htm",
            "https://xaydungchinhsach.chinhphu.vn/toan-van-nghi-quyet-so-1684-nq-ubtvqh15-sap-xep-cac-dvhc-cap-xa-cua-tinh-tuyen-quang-nam-2025-119250616211706973.htm",
        ],
        "verification_date": VERIFIED_AT,
    },
}


def validate_seed_data() -> int:
    """Validate IDs, coordinates, chronological order, references and costs."""
    seen_ids: set[str] = set()
    location_by_id: dict[str, dict[str, Any]] = {}

    for key, location in LOCATIONS.items():
        location_id = location["id"]
        uuid.UUID(location_id)

        if location_id in seen_ids:
            raise ValueError(f"Duplicate location UUID: {location_id}")
        seen_ids.add(location_id)
        location_by_id[location_id] = location

        lat = float(location["lat"])
        lng = float(location["lng"])
        if not -90 <= lat <= 90:
            raise ValueError(f"Invalid latitude for {key}: {lat}")
        if not -180 <= lng <= 180:
            raise ValueError(f"Invalid longitude for {key}: {lng}")

        maps_url = str(location.get("google_maps_url", ""))
        if not maps_url.startswith("https://www.google.com/maps?q="):
            raise ValueError(f"Missing/invalid Google Maps URL for {key}")
        if not location.get("coordinate_precision"):
            raise ValueError(f"Missing coordinate_precision for {key}")
        if not location.get("coordinate_source"):
            raise ValueError(f"Missing coordinate_source for {key}")

    expected_days = list(range(1, HA_GIANG_SNAPSHOT["duration_days"] + 1))
    actual_days = [day["day_number"] for day in HA_GIANG_SNAPSHOT["days"]]
    if actual_days != expected_days:
        raise ValueError(f"Invalid day sequence: expected={expected_days}, actual={actual_days}")

    total_cost = 0
    activity_count = 0

    for day in HA_GIANG_SNAPSHOT["days"]:
        previous_start_minutes = -1

        for activity in day["activities"]:
            activity_count += 1
            start_dt = datetime.strptime(activity["start_time"], "%H:%M")
            end_dt = datetime.strptime(activity["end_time"], "%H:%M")
            start_minutes = start_dt.hour * 60 + start_dt.minute
            end_minutes = end_dt.hour * 60 + end_dt.minute

            if end_minutes <= start_minutes:
                raise ValueError(f"End time must follow start time: {activity['title']}")
            if start_minutes < previous_start_minutes:
                raise ValueError(
                    f"Activities are not ordered on day {day['day_number']}: {activity['title']}"
                )
            previous_start_minutes = start_minutes

            location_id = activity.get("location_id")
            if not location_id or location_id not in location_by_id:
                raise ValueError(f"Unknown location_id: {activity['title']}")

            location = location_by_id[location_id]
            if float(activity["lat"]) != float(location["lat"]):
                raise ValueError(f"Latitude mismatch: {activity['title']}")
            if float(activity["lng"]) != float(location["lng"]):
                raise ValueError(f"Longitude mismatch: {activity['title']}")

            cost = activity.get("actual_cost", 0)
            if not isinstance(cost, int) or cost < 0:
                raise ValueError(f"Invalid actual_cost: {activity['title']}")
            total_cost += cost

    expected_per_person = HA_GIANG_SNAPSHOT["actual_cost_per_person"]
    if total_cost != expected_per_person:
        raise ValueError(
            f"Cost mismatch: activities={total_cost:,}, snapshot={expected_per_person:,}"
        )

    expected_total = expected_per_person * NUMBER_OF_TRAVELERS
    if HA_GIANG_SNAPSHOT["actual_total_cost"] != expected_total:
        raise ValueError("actual_total_cost must equal cost/person * traveler_count")

    breakdown = HA_GIANG_SNAPSHOT["budget_breakdown_per_person"]
    breakdown_sum = sum(value for key, value in breakdown.items() if key != "total")
    if breakdown_sum != breakdown["total"]:
        raise ValueError("Budget breakdown does not add up")
    if breakdown["total"] != expected_per_person:
        raise ValueError("Budget breakdown differs from actual_cost_per_person")

    if activity_count < 25:
        raise ValueError("The itinerary is unexpectedly short")

    return total_cost


async def seed_ha_giang() -> None:
    validated_cost = validate_seed_data()
    print(
        f"Validated {len(LOCATIONS)} locations; "
        f"activity cost per person = {validated_cost:,} VND"
    )

    async with AsyncSessionLocal() as session:
        # 1. Seed or update locations.
        for loc_data in LOCATIONS.values():
            loc_id = uuid.UUID(loc_data["id"])
            stmt_loc = select(Location).where(Location.id == loc_id)
            res_loc = await session.execute(stmt_loc)
            existing_loc = res_loc.scalar_one_or_none()

            if not existing_loc:
                session.add(
                    Location(
                        id=loc_id,
                        name=loc_data["name"],
                        address=loc_data["address"],
                        lat=loc_data["lat"],
                        lng=loc_data["lng"],
                        category=loc_data["category"],
                        province_name=loc_data["province_name"],
                    )
                )
            else:
                existing_loc.name = loc_data["name"]
                existing_loc.address = loc_data["address"]
                existing_loc.lat = loc_data["lat"]
                existing_loc.lng = loc_data["lng"]
                existing_loc.category = loc_data["category"]
                existing_loc.province_name = loc_data["province_name"]

        await session.commit()

        # 2. Find or create the seed author.
        author_email = "guide.hagiang@smarttravel.vn"
        stmt_user = select(User).where(User.email == author_email)
        res_user = await session.execute(stmt_user)
        user = res_user.scalar_one_or_none()

        if not user:
            print(f"No user '{author_email}' found. Creating seed author...")
            user = User(
                id=uuid.uuid4(),
                username="guide-hagiang",
                email=author_email,
                full_name="Vàng Mí Sính (Hướng dẫn viên Cao nguyên đá)",
                password_hash="seed-only-account-not-for-login",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

        # 3. Create or update the public trip publication.
        slug = "lich-trinh-ha-giang-dong-van-lung-cu-3-ngay-2-dem"
        stmt_pub = select(PublicTripPublication).where(PublicTripPublication.slug == slug)
        res_pub = await session.execute(stmt_pub)
        existing = res_pub.scalar_one_or_none()

        publication_values = {
            "title": HA_GIANG_SNAPSHOT["title"],
            "summary": (
                "Hành trình Hà Giang 3 ngày 2 đêm từ Hà Nội cho 2 người qua Km 0, "
                "Cổng trời và Núi đôi Quản Bạ, Yên Minh, Dốc Thẩm Mã, Nhà của Pao, "
                "Dinh họ Vương, Cột cờ Lũng Cú, Lô Lô Chải, phố cổ Đồng Văn, "
                "đèo Mã Pì Lèng và sông Nho Quế với ngân sách khoảng 4,3 triệu đồng/người."
            ),
            "destination": "Hà Giang - Cao nguyên đá Đồng Văn (Tuyên Quang)",
            "province_name": CURRENT_PROVINCE_NAME,
            "duration_days": 3,
            "actual_total_cost": HA_GIANG_SNAPSHOT["actual_total_cost"],
            "actual_cost_per_person": HA_GIANG_SNAPSHOT["actual_cost_per_person"],
            "overall_rating": HA_GIANG_SNAPSHOT["overall_rating"],
            "status": "published",
            "visibility": "public",
            "moderation_status": "approved",
            "cover_image_url": (
                "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee"
                "?auto=format&fit=crop&w=1200&q=80"
            ),
            "snapshot_json": HA_GIANG_SNAPSHOT,
            "tags": [
                "Hà Giang",
                "Tuyên Quang",
                "3 ngày 2 đêm",
                "Cao nguyên đá Đồng Văn",
                "Cổng trời Quản Bạ",
                "Dốc Thẩm Mã",
                "Nhà của Pao",
                "Dinh họ Vương",
                "Cột cờ Lũng Cú",
                "Lô Lô Chải",
                "Mã Pì Lèng",
                "Sông Nho Quế",
                "Hẻm Tu Sản",
                "Đông Bắc",
            ],
            "save_count": 0,
            "view_count": 3980,
            "published_at": datetime.now(timezone.utc),
        }

        if existing:
            print(f"Publication '{slug}' already exists. Updating content...")
            for field, value in publication_values.items():
                setattr(existing, field, value)
        else:
            print(f"Creating new Public Trip Publication '{slug}'...")
            session.add(
                PublicTripPublication(
                    id=uuid.uuid4(),
                    author_user_id=user.id,
                    slug=slug,
                    **publication_values,
                )
            )

        await session.commit()
        print("Successfully seeded Ha Giang - Dong Van - Lung Cu 3D2N itinerary!")


if __name__ == "__main__":
    asyncio.run(seed_ha_giang())
