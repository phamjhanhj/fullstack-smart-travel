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
# HUE 3D2N SEED DATA
#
# Itinerary basis:
# - Public Hanoi - Hue 3-day/2-night tours and official Hue tourism itineraries.
# - Day 1: Hanoi - Hue - Dong Ba - Imperial City - Thien Mu - Perfume River.
# - Day 2: Khai Dinh - Minh Mang - Thuy Xuan - Tu Duc - Vong Canh.
# - Day 3: Chuon Lagoon - An Dinh Palace - Dong Ba - Hue - Hanoi.
#
# Administrative naming policy:
# - Hue became a centrally governed municipality from 2025-01-01.
# - All Hue destinations therefore store province_name="Huế".
#
# Coordinate policy:
# - Airports and established monuments use public OpenStreetMap, Mapcarta,
#   GeoNames or Wikidata coordinates.
# - Large areas such as the hotel zone, Thuy Xuan incense village and Chuon
#   Lagoon use an explicitly described representative access point.
# - Every location includes a Google Maps coordinate URL for manual review.
# - Coordinates were last reviewed on 2026-07-30.
#
# Cost policy:
# - actual_cost is the estimated cost PER PERSON for a group of two travellers.
# - The monument ticket is seeded as the official four-site combination ticket:
#   Imperial City - Tu Duc - Khai Dinh - Minh Mang.
# - Flight, hotel, food, boat and local transport prices are planning estimates,
#   not binding supplier quotations.
# -----------------------------------------------------------------------------

VERIFIED_AT = "2026-07-30"
NUMBER_OF_TRAVELERS = 2
CURRENT_PROVINCE_NAME = "Huế"


LOCATIONS: dict[str, dict[str, Any]] = {
    "noi_bai_airport": {
        "id": "88888888-8888-4888-8888-000000000001",
        "name": "Sân bay quốc tế Nội Bài",
        "address": "Phú Minh, Sóc Sơn, Hà Nội",
        "lat": 21.22119,
        "lng": 105.80718,
        "category": "transport",
        "province_name": "Hà Nội",
        "coordinate_precision": "airport_aerodrome_center",
        "coordinate_source": "Mapcarta/GeoNames/Wikidata airport coordinate",
        "google_maps_url": "https://www.google.com/maps?q=21.22119,105.80718",
        "plus_code": "7PH76RC4+FV",
        "verified_at": VERIFIED_AT,
    },
    "phu_bai_airport": {
        "id": "88888888-8888-4888-8888-000000000002",
        "name": "Sân bay quốc tế Phú Bài",
        "address": "Phú Bài, thành phố Huế",
        "lat": 16.39835,
        "lng": 107.70461,
        "category": "transport",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "airport_aerodrome_center",
        "coordinate_source": "Mapcarta/OpenStreetMap airport coordinate",
        "google_maps_url": "https://www.google.com/maps?q=16.39835,107.70461",
        "plus_code": "7P899PX3+8R",
        "verified_at": VERIFIED_AT,
    },
    "hue_central_hotel_area": {
        "id": "88888888-8888-4888-8888-000000000003",
        "name": "Khu lưu trú trung tâm Huế",
        "address": "Khu vực Võ Thị Sáu - Phạm Ngũ Lão, trung tâm thành phố Huế",
        "lat": 16.4673,
        "lng": 107.5945,
        "category": "hotel",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "hotel_zone_representative_point",
        "coordinate_source": "Representative point in the central Hue hotel and walking-street zone",
        "google_maps_url": "https://www.google.com/maps?q=16.4673,107.5945",
        "verified_at": VERIFIED_AT,
    },
    "dong_ba_market": {
        "id": "88888888-8888-4888-8888-000000000004",
        "name": "Chợ Đông Ba",
        "address": "Đường Trần Hưng Đạo, thành phố Huế",
        "lat": 16.47253,
        "lng": 107.58866,
        "category": "attraction",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "market_building_pin",
        "coordinate_source": "OpenStreetMap way 161714451 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=16.47253,107.58866",
        "plus_code": "7P89FHFQ+2F",
        "verified_at": VERIFIED_AT,
    },
    "hue_imperial_city": {
        "id": "88888888-8888-4888-8888-000000000005",
        "name": "Đại Nội Huế - Hoàng thành Huế",
        "address": "Đường 23 Tháng 8, phường Phú Xuân, thành phố Huế",
        "lat": 16.46897,
        "lng": 107.57813,
        "category": "attraction",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "imperial_citadel_visitor_pin",
        "coordinate_source": "OpenStreetMap node 5182931945 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=16.46897,107.57813",
        "plus_code": "7P89FH9H+H7",
        "verified_at": VERIFIED_AT,
    },
    "thien_mu_pagoda": {
        "id": "88888888-8888-4888-8888-000000000006",
        "name": "Chùa Thiên Mụ",
        "address": "Đồi Hà Khê, phường Kim Long, thành phố Huế",
        "lat": 16.4536,
        "lng": 107.54466,
        "category": "attraction",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "temple_complex_pin",
        "coordinate_source": "OpenStreetMap way 205794912 via Mapcarta/Wikidata",
        "google_maps_url": "https://www.google.com/maps?q=16.4536,107.54466",
        "plus_code": "7P89FG3V+CV",
        "verified_at": VERIFIED_AT,
    },
    "truong_tien_bridge": {
        "id": "88888888-8888-4888-8888-000000000007",
        "name": "Cầu Trường Tiền",
        "address": "Cầu Trường Tiền bắc qua sông Hương, thành phố Huế",
        "lat": 16.46901,
        "lng": 107.5887,
        "category": "attraction",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "bridge_center_pin",
        "coordinate_source": "Wikidata/Apple Maps bridge coordinate",
        "google_maps_url": "https://www.google.com/maps?q=16.46901,107.5887",
        "plus_code": "7P89FH9Q+J7",
        "verified_at": VERIFIED_AT,
    },
    "khai_dinh_tomb": {
        "id": "88888888-8888-4888-8888-000000000008",
        "name": "Lăng vua Khải Định",
        "address": "Khu vực Châu Chữ, thành phố Huế",
        "lat": 16.39902,
        "lng": 107.59034,
        "category": "attraction",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "mausoleum_complex_pin",
        "coordinate_source": "OpenStreetMap way 175035807 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=16.39902,107.59034",
        "plus_code": "7P899HXR+J4",
        "verified_at": VERIFIED_AT,
    },
    "minh_mang_tomb": {
        "id": "88888888-8888-4888-8888-000000000009",
        "name": "Lăng vua Minh Mạng",
        "address": "Khu vực núi Cẩm Khê, thành phố Huế",
        "lat": 16.38772,
        "lng": 107.56825,
        "category": "attraction",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "mausoleum_complex_pin",
        "coordinate_source": "GeoNames/Wikidata coordinate via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=16.38772,107.56825",
        "plus_code": "7P899HQ9+38",
        "verified_at": VERIFIED_AT,
    },
    "tu_duc_tomb": {
        "id": "88888888-8888-4888-8888-000000000010",
        "name": "Lăng vua Tự Đức",
        "address": "Khu vực Thượng Ba, thành phố Huế",
        "lat": 16.43,
        "lng": 107.57,
        "category": "attraction",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "mausoleum_complex_pin",
        "coordinate_source": "Wikidata coordinate 16°25'48N, 107°34'12E",
        "google_maps_url": "https://www.google.com/maps?q=16.43,107.57",
        "plus_code": "7P89CHJC+22",
        "verified_at": VERIFIED_AT,
    },
    "thuy_xuan_incense_village": {
        "id": "88888888-8888-4888-8888-000000000011",
        "name": "Làng hương Thủy Xuân",
        "address": "Đường Huyền Trân Công Chúa, khu vực Thủy Xuân, thành phố Huế",
        "lat": 16.43713,
        "lng": 107.57879,
        "category": "attraction",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "village_representative_point",
        "coordinate_source": "Public Thuy Xuan map coordinate; representative point for the incense-village strip",
        "google_maps_url": "https://www.google.com/maps?q=16.43713,107.57879",
        "verified_at": VERIFIED_AT,
    },
    "vong_canh_hill": {
        "id": "88888888-8888-4888-8888-000000000012",
        "name": "Đồi Vọng Cảnh",
        "address": "Khu vực Long Hồ, thành phố Huế",
        "lat": 16.42707,
        "lng": 107.56257,
        "category": "attraction",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "hill_viewpoint_representative_point",
        "coordinate_source": "GeoNames/Wikidata coordinate via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=16.42707,107.56257",
        "plus_code": "7P89CHG7+R2",
        "verified_at": VERIFIED_AT,
    },
    "an_dinh_palace": {
        "id": "88888888-8888-4888-8888-000000000013",
        "name": "Cung An Định",
        "address": "179 Phan Đình Phùng, thành phố Huế",
        "lat": 16.45663,
        "lng": 107.59831,
        "category": "attraction",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "palace_building_pin",
        "coordinate_source": "OpenStreetMap way 1172897446 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=16.45663,107.59831",
        "plus_code": "7P89FH4X+M8",
        "verified_at": VERIFIED_AT,
    },
    "chuon_lagoon_access": {
        "id": "88888888-8888-4888-8888-000000000014",
        "name": "Điểm tham quan Đầm Chuồn - làng Chuồn",
        "address": "Khu vực làng Chuồn, đầm phá Tam Giang - Cầu Hai, thành phố Huế",
        "lat": 16.50737,
        "lng": 107.63579,
        "category": "attraction",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "lagoon_access_representative_point",
        "coordinate_source": "OpenStreetMap node 9960139117 (Liễn làng Chuồn) via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=16.50737,107.63579",
        "plus_code": "7P89GJ4P+W8",
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


HUE_SNAPSHOT: dict[str, Any] = {
    "title": "Lịch trình Huế 3 ngày 2 đêm từ Hà Nội",
    "destination": "Huế",
    "duration_days": 3,
    "traveler_count": NUMBER_OF_TRAVELERS,
    "actual_cost_per_person": 7_540_000,
    "actual_total_cost": 15_080_000,
    "overall_rating": 4.9,
    "coordinate_verified_at": VERIFIED_AT,
    "administrative_note": (
        "Từ ngày 01/01/2025, Huế là thành phố trực thuộc Trung ương. "
        "Vì vậy tất cả điểm trong hành trình được lưu province_name='Huế'."
    ),
    "cost_note": (
        "Chi phí là dữ liệu seed tham khảo theo người cho nhóm 2 người. Vé máy bay, khách sạn, "
        "dịch vụ thuyền rồng và Đầm Chuồn có thể thay đổi theo ngày. Vé di tích được tính theo "
        "gói 4 điểm Đại Nội - Tự Đức - Khải Định - Minh Mạng ở mức 530.000 đồng/người tại ngày xác minh."
    ),
    "budget_breakdown_per_person": {
        "transport": 4_140_000,
        "lodging": 900_000,
        "food": 1_870_000,
        "tours_and_tickets": 580_000,
        "shopping_and_miscellaneous": 50_000,
        "total": 7_540_000,
    },
    "days": [
        {
            "day_number": 1,
            "title": "Hà Nội - Huế - Chợ Đông Ba - Đại Nội - Chùa Thiên Mụ",
            "activities": [
                build_activity(
                    location_key="noi_bai_airport",
                    start_time="05:10",
                    end_time="06:00",
                    title="Di chuyển từ trung tâm Hà Nội tới sân bay Nội Bài",
                    activity_type="transport",
                    actual_cost=120_000,
                    rating=4.8,
                    author_verdict="must_go",
                    best_time="Rời trung tâm trước giờ bay tối thiểu 3 giờ",
                    next_traveler_note="Đặt xe trước và kiểm tra đúng nhà ga; dự phòng ùn tắc trên tuyến Võ Nguyên Giáp.",
                ),
                build_activity(
                    location_key="noi_bai_airport",
                    start_time="06:00",
                    end_time="06:50",
                    title="Làm thủ tục và ăn sáng tại sân bay Nội Bài",
                    activity_type="meal",
                    actual_cost=70_000,
                    rating=4.6,
                    author_verdict="recommended",
                    best_time="Hoàn tất ký gửi trước giờ đóng quầy",
                    next_traveler_note="Ăn món gọn nhẹ; không để pin dự phòng trong hành lý ký gửi.",
                ),
                build_activity(
                    location_key="phu_bai_airport",
                    start_time="07:30",
                    end_time="08:45",
                    title="Bay Hà Nội - Huế",
                    activity_type="transport",
                    actual_cost=1_400_000,
                    rating=4.9,
                    author_verdict="must_go",
                    best_time="Chuyến sáng để tận dụng ngày đầu",
                    next_traveler_note="Giá là mức seed gồm thuế phí và hành lý cơ bản; production phải lấy giờ và giá từ vé thật.",
                ),
                build_activity(
                    location_key="hue_central_hotel_area",
                    start_time="09:00",
                    end_time="09:40",
                    title="Di chuyển sân bay Phú Bài về trung tâm Huế",
                    activity_type="transport",
                    actual_cost=100_000,
                    rating=4.8,
                    author_verdict="must_go",
                    best_time="Đi taxi hoặc xe hợp đồng theo giá đã xác nhận",
                    next_traveler_note="Tọa độ là khu khách sạn đại diện; thay bằng khách sạn thật sau khi người dùng đặt phòng.",
                ),
                build_activity(
                    location_key="hue_central_hotel_area",
                    start_time="09:40",
                    end_time="10:30",
                    title="Gửi hành lý, nhận phòng sớm nếu có và tính chi phí đêm thứ nhất",
                    activity_type="hotel",
                    actual_cost=450_000,
                    rating=4.8,
                    author_verdict="must_go",
                    best_time="Gửi hành lý trước, không chờ phòng nếu chưa tới giờ nhận",
                    next_traveler_note="Mức phòng tính theo người khi 2 khách ở chung; cần cập nhật theo booking thật.",
                ),
                build_activity(
                    location_key="dong_ba_market",
                    start_time="10:40",
                    end_time="11:45",
                    title="Ăn trưa sớm và khám phá ẩm thực Chợ Đông Ba",
                    activity_type="meal",
                    actual_cost=150_000,
                    rating=4.9,
                    author_verdict="must_go",
                    best_time="10:30-12:00 trước khi khu chợ đông nhất",
                    next_traveler_note="Gợi ý bún bò, bánh bèo, bánh nậm, bánh lọc và chè Huế; hỏi giá trước khi gọi.",
                ),
                build_activity(
                    location_key="hue_imperial_city",
                    start_time="11:45",
                    end_time="12:05",
                    title="Di chuyển Chợ Đông Ba - Đại Nội Huế",
                    activity_type="transport",
                    actual_cost=50_000,
                    rating=4.8,
                    author_verdict="must_go",
                    best_time="Đi xe công nghệ hoặc xích lô có thỏa thuận giá",
                    next_traveler_note="Mang nước và mũ vì khu Đại Nội rộng, ít bóng râm ở một số đoạn.",
                ),
                build_activity(
                    location_key="hue_imperial_city",
                    start_time="12:05",
                    end_time="12:20",
                    title="Mua vé gộp 4 điểm di tích Huế",
                    activity_type="ticket",
                    actual_cost=530_000,
                    rating=4.9,
                    author_verdict="must_go",
                    best_time="Mua tại quầy chính thức hoặc hệ thống vé điện tử",
                    next_traveler_note="Gói seed gồm Đại Nội, Tự Đức, Khải Định và Minh Mạng; kiểm tra thời hạn sử dụng trên vé hiện hành.",
                ),
                build_activity(
                    location_key="hue_imperial_city",
                    start_time="12:20",
                    end_time="15:10",
                    title="Tham quan Ngọ Môn, Điện Thái Hòa, Tử Cấm Thành và các cung điện",
                    activity_type="attraction",
                    actual_cost=0,
                    rating=5.0,
                    author_verdict="must_go",
                    best_time="Dành ít nhất 2,5-3 giờ",
                    next_traveler_note="Không trèo lên cấu kiện, không chạm hiện vật và tuân thủ khu vực hạn chế chụp ảnh.",
                ),
                build_activity(
                    location_key="thien_mu_pagoda",
                    start_time="15:20",
                    end_time="16:00",
                    title="Đi thuyền rồng trên sông Hương tới Chùa Thiên Mụ",
                    activity_type="transport",
                    actual_cost=150_000,
                    rating=4.8,
                    author_verdict="recommended",
                    best_time="Chiều mát, mực nước và thời tiết ổn định",
                    next_traveler_note="Mặc áo phao, xác nhận giá và điểm trả khách trước khi lên thuyền.",
                ),
                build_activity(
                    location_key="thien_mu_pagoda",
                    start_time="16:00",
                    end_time="17:20",
                    title="Tham quan Chùa Thiên Mụ và ngắm sông Hương",
                    activity_type="attraction",
                    actual_cost=0,
                    rating=4.9,
                    author_verdict="must_go",
                    best_time="16:00-17:30",
                    next_traveler_note="Ăn mặc kín đáo, giữ yên tĩnh, không dùng flycam hoặc chụp tại nơi cấm.",
                ),
                build_activity(
                    location_key="hue_central_hotel_area",
                    start_time="18:00",
                    end_time="19:30",
                    title="Ăn tối đặc sản Huế tại khu trung tâm",
                    activity_type="meal",
                    actual_cost=250_000,
                    rating=4.9,
                    author_verdict="must_go",
                    best_time="18:00-19:30",
                    next_traveler_note="Gợi ý cơm hến, bánh khoái, nem lụi, thịt luộc chấm tôm chua; chọn mức cay phù hợp.",
                ),
                build_activity(
                    location_key="truong_tien_bridge",
                    start_time="19:40",
                    end_time="21:00",
                    title="Dạo Cầu Trường Tiền và bờ sông Hương về đêm",
                    activity_type="attraction",
                    actual_cost=50_000,
                    rating=4.8,
                    author_verdict="recommended",
                    best_time="Sau khi hệ thống chiếu sáng được bật",
                    next_traveler_note="Đi trên lối dành cho người đi bộ, giữ đồ cá nhân khi khu vực đông khách.",
                ),
            ],
        },
        {
            "day_number": 2,
            "title": "Lăng Khải Định - Minh Mạng - Làng hương - Tự Đức - Đồi Vọng Cảnh",
            "activities": [
                build_activity(
                    location_key="hue_central_hotel_area",
                    start_time="06:30",
                    end_time="07:15",
                    title="Ăn sáng bún bò Huế hoặc bánh canh Nam Phổ",
                    activity_type="meal",
                    actual_cost=60_000,
                    rating=4.9,
                    author_verdict="must_go",
                    best_time="Ăn sớm trước tuyến lăng tẩm",
                    next_traveler_note="Mang theo nước, kem chống nắng và giày bám tốt vì có nhiều bậc thang.",
                ),
                build_activity(
                    location_key="khai_dinh_tomb",
                    start_time="07:20",
                    end_time="08:00",
                    title="Thuê xe theo ngày và di chuyển đến Lăng Khải Định",
                    activity_type="transport",
                    actual_cost=350_000,
                    rating=4.8,
                    author_verdict="must_go",
                    best_time="Khởi hành trước 07:30",
                    next_traveler_note="Chi phí là phần chia theo người cho xe 2 khách; xác nhận rõ số giờ, điểm đón và phí chờ.",
                ),
                build_activity(
                    location_key="khai_dinh_tomb",
                    start_time="08:00",
                    end_time="09:20",
                    title="Tham quan Lăng Khải Định và Điện Thiên Định",
                    activity_type="attraction",
                    actual_cost=0,
                    rating=4.9,
                    author_verdict="must_go",
                    best_time="Buổi sáng trước nắng gắt",
                    next_traveler_note="Vé đã nằm trong gói 4 điểm; bậc thang dốc nên đi chậm và không chen lấn.",
                ),
                build_activity(
                    location_key="minh_mang_tomb",
                    start_time="09:20",
                    end_time="10:00",
                    title="Di chuyển Lăng Khải Định - Lăng Minh Mạng",
                    activity_type="transport",
                    actual_cost=0,
                    rating=4.7,
                    author_verdict="must_go",
                    best_time="Đi theo tuyến ngoại thành, không quay lại trung tâm",
                    next_traveler_note="Chi phí đã nằm trong xe theo ngày; thắt dây an toàn và không yêu cầu tài xế chạy nhanh.",
                ),
                build_activity(
                    location_key="minh_mang_tomb",
                    start_time="10:00",
                    end_time="11:35",
                    title="Tham quan Lăng Minh Mạng và cảnh quan hồ - đồi",
                    activity_type="attraction",
                    actual_cost=0,
                    rating=5.0,
                    author_verdict="must_go",
                    best_time="Sáng mát hoặc cuối chiều",
                    next_traveler_note="Vé đã nằm trong gói; giữ khoảng cách với mép hồ và không đi vào khu vực đang trùng tu.",
                ),
                build_activity(
                    location_key="minh_mang_tomb",
                    start_time="11:40",
                    end_time="12:50",
                    title="Ăn trưa món Huế trên tuyến lăng tẩm",
                    activity_type="meal",
                    actual_cost=200_000,
                    rating=4.7,
                    author_verdict="recommended",
                    best_time="Ăn trước khi về khu Thủy Xuân",
                    next_traveler_note="Chọn quán có bảng giá, ưu tiên món chín nóng và hạn chế uống rượu khi còn di chuyển.",
                ),
                build_activity(
                    location_key="thuy_xuan_incense_village",
                    start_time="13:20",
                    end_time="14:10",
                    title="Check-in và tìm hiểu nghề làm hương Thủy Xuân",
                    activity_type="attraction",
                    actual_cost=50_000,
                    rating=4.7,
                    author_verdict="recommended",
                    best_time="Đầu chiều khi hàng hương đủ ánh sáng",
                    next_traveler_note="Chi phí là mua món nhỏ/ủng hộ điểm chụp; không làm gãy bó hương hoặc chắn lối kinh doanh.",
                ),
                build_activity(
                    location_key="tu_duc_tomb",
                    start_time="14:20",
                    end_time="15:50",
                    title="Tham quan Lăng Tự Đức và hồ Lưu Khiêm",
                    activity_type="attraction",
                    actual_cost=0,
                    rating=4.9,
                    author_verdict="must_go",
                    best_time="14:00-16:00",
                    next_traveler_note="Vé đã nằm trong gói; khuôn viên rộng nên theo biển chỉ dẫn và giữ vé tới khi ra cổng.",
                ),
                build_activity(
                    location_key="vong_canh_hill",
                    start_time="16:00",
                    end_time="17:15",
                    title="Ngắm sông Hương và hoàng hôn tại Đồi Vọng Cảnh",
                    activity_type="attraction",
                    actual_cost=0,
                    rating=4.9,
                    author_verdict="must_go",
                    best_time="16:15-17:30 tùy mùa",
                    next_traveler_note="Không đứng sát mép dốc, chú ý xe trên đường nhỏ và rời điểm trước khi quá tối.",
                ),
                build_activity(
                    location_key="vong_canh_hill",
                    start_time="17:20",
                    end_time="17:50",
                    title="Uống cà phê hoặc nước giải khát sau hành trình lăng tẩm",
                    activity_type="meal",
                    actual_cost=80_000,
                    rating=4.6,
                    author_verdict="recommended",
                    best_time="Sau khi ngắm cảnh",
                    next_traveler_note="Không xả rác tại điểm ngắm cảnh; chọn đồ uống đóng chai nếu quán dã chiến không bảo đảm vệ sinh.",
                ),
                build_activity(
                    location_key="hue_central_hotel_area",
                    start_time="18:20",
                    end_time="18:40",
                    title="Trở về khách sạn và tính chi phí đêm thứ hai",
                    activity_type="hotel",
                    actual_cost=450_000,
                    rating=4.8,
                    author_verdict="must_go",
                    best_time="Nghỉ trước bữa tối",
                    next_traveler_note="Mức phòng tính theo người khi hai khách ở chung; kiểm tra hóa đơn và giờ trả phòng ngày cuối.",
                ),
                build_activity(
                    location_key="hue_central_hotel_area",
                    start_time="19:00",
                    end_time="20:30",
                    title="Ăn tối với thực đơn cung đình hoặc cơm Huế",
                    activity_type="meal",
                    actual_cost=300_000,
                    rating=4.8,
                    author_verdict="recommended",
                    best_time="19:00-20:30",
                    next_traveler_note="Trải nghiệm cung đình là tùy chọn; kiểm tra rõ thực đơn, phụ phí trang phục và biểu diễn.",
                ),
                build_activity(
                    location_key="hue_central_hotel_area",
                    start_time="20:30",
                    end_time="22:00",
                    title="Dạo phố đi bộ trung tâm Huế và thưởng thức chè",
                    activity_type="attraction",
                    actual_cost=80_000,
                    rating=4.7,
                    author_verdict="recommended",
                    best_time="Buổi tối cuối tuần hoặc khi phố đi bộ hoạt động",
                    next_traveler_note="Kiểm tra lịch cấm xe thực tế; giữ điện thoại và ví ở nơi đông người.",
                ),
            ],
        },
        {
            "day_number": 3,
            "title": "Đầm Chuồn - Cung An Định - Chợ Đông Ba - Huế - Hà Nội",
            "activities": [
                build_activity(
                    location_key="chuon_lagoon_access",
                    start_time="04:50",
                    end_time="05:30",
                    title="Di chuyển sớm từ trung tâm Huế tới Đầm Chuồn",
                    activity_type="transport",
                    actual_cost=400_000,
                    rating=4.8,
                    author_verdict="must_go",
                    best_time="Khởi hành trước bình minh",
                    next_traveler_note="Chi phí gồm xe khứ hồi và phần thuyền địa phương dự kiến; xác nhận thời tiết, áo phao và bến đón trước một ngày.",
                ),
                build_activity(
                    location_key="chuon_lagoon_access",
                    start_time="05:30",
                    end_time="07:10",
                    title="Ngắm bình minh và trải nghiệm thuyền trên Đầm Chuồn",
                    activity_type="attraction",
                    actual_cost=0,
                    rating=4.9,
                    author_verdict="must_go",
                    best_time="Bình minh hoặc hoàng hôn",
                    next_traveler_note="Tọa độ là điểm tiếp cận đại diện; bến thực tế phụ thuộc nhà thuyền. Luôn mặc áo phao và không đứng dồn một phía.",
                ),
                build_activity(
                    location_key="chuon_lagoon_access",
                    start_time="07:10",
                    end_time="08:20",
                    title="Ăn sáng hải sản và bánh khoái cá kình tại khu đầm",
                    activity_type="meal",
                    actual_cost=250_000,
                    rating=4.9,
                    author_verdict="must_go",
                    best_time="Sau chuyến thuyền sáng",
                    next_traveler_note="Hỏi giá theo cân/phần trước khi chế biến, báo dị ứng hải sản và không gọi quá nhiều món.",
                ),
                build_activity(
                    location_key="hue_central_hotel_area",
                    start_time="08:20",
                    end_time="09:10",
                    title="Trở về khách sạn, tắm rửa và trả phòng",
                    activity_type="transport",
                    actual_cost=0,
                    rating=4.7,
                    author_verdict="must_go",
                    best_time="Trả phòng đúng giờ quy định",
                    next_traveler_note="Chi phí xe đã nằm trong hoạt động đầu ngày; kiểm tra kỹ giấy tờ và đồ sạc trước khi rời phòng.",
                ),
                build_activity(
                    location_key="an_dinh_palace",
                    start_time="09:30",
                    end_time="10:45",
                    title="Tham quan Cung An Định",
                    activity_type="attraction",
                    actual_cost=50_000,
                    rating=4.8,
                    author_verdict="recommended",
                    best_time="Buổi sáng khi ánh sáng mặt tiền đẹp",
                    next_traveler_note="Mua vé tại quầy chính thức; tuân thủ khu vực hạn chế chụp ảnh và không tự ý đi vào lối đóng.",
                ),
                build_activity(
                    location_key="hue_central_hotel_area",
                    start_time="11:00",
                    end_time="12:00",
                    title="Ăn trưa nhẹ trước chuyến bay",
                    activity_type="meal",
                    actual_cost=180_000,
                    rating=4.7,
                    author_verdict="recommended",
                    best_time="Ăn trước khi ra sân bay",
                    next_traveler_note="Gợi ý cơm hến, bánh canh hoặc cơm gia đình; tránh món quá cay nếu dễ say máy bay.",
                ),
                build_activity(
                    location_key="dong_ba_market",
                    start_time="12:05",
                    end_time="12:50",
                    title="Mua đặc sản tại Chợ Đông Ba",
                    activity_type="shopping",
                    actual_cost=150_000,
                    rating=4.7,
                    author_verdict="recommended",
                    best_time="Trước khi ra sân bay",
                    next_traveler_note="Gợi ý mè xửng, tôm chua và nón lá; kiểm tra quy định hành lý với đồ lỏng, mùi mạnh hoặc dễ vỡ.",
                ),
                build_activity(
                    location_key="phu_bai_airport",
                    start_time="13:00",
                    end_time="13:40",
                    title="Di chuyển trung tâm Huế ra sân bay Phú Bài",
                    activity_type="transport",
                    actual_cost=100_000,
                    rating=4.8,
                    author_verdict="must_go",
                    best_time="Có mặt trước chuyến bay nội địa ít nhất 2 giờ",
                    next_traveler_note="Xác nhận nhà ga và tình trạng chuyến bay trước khi rời trung tâm.",
                ),
                build_activity(
                    location_key="noi_bai_airport",
                    start_time="15:10",
                    end_time="16:25",
                    title="Bay Huế - Hà Nội",
                    activity_type="transport",
                    actual_cost=1_400_000,
                    rating=4.9,
                    author_verdict="must_go",
                    best_time="Chuyến chiều để vẫn có nửa ngày tham quan",
                    next_traveler_note="Giờ và giá chỉ là mẫu; production phải đồng bộ theo vé thực tế của người dùng.",
                ),
                build_activity(
                    location_key="noi_bai_airport",
                    start_time="16:45",
                    end_time="17:45",
                    title="Di chuyển Nội Bài về trung tâm Hà Nội, kết thúc hành trình",
                    activity_type="transport",
                    actual_cost=120_000,
                    rating=4.8,
                    author_verdict="must_go",
                    best_time="Đặt xe sau khi nhận đủ hành lý",
                    next_traveler_note="Giờ về có thể thay đổi do hành lý và giao thông; kiểm tra lại toàn bộ đồ trước khi rời xe.",
                ),
            ],
        },
    ],
    "review": {
        "best_places": [
            "Đại Nội Huế",
            "Chùa Thiên Mụ",
            "Lăng Khải Định",
            "Lăng Minh Mạng",
            "Lăng Tự Đức",
            "Đồi Vọng Cảnh",
            "Đầm Chuồn",
            "Cung An Định",
        ],
        "best_foods": [
            "Bún bò Huế",
            "Cơm hến",
            "Bánh bèo - bánh nậm - bánh lọc",
            "Nem lụi",
            "Bánh khoái",
            "Chè Huế",
            "Bánh khoái cá kình Đầm Chuồn",
        ],
        "tips": (
            "Đặt vé máy bay và phòng sớm; mua vé di tích tại kênh chính thức; mang giày dễ đi và nước uống; "
            "không ghép quá nhiều lăng trong một buổi; xác nhận bến thuyền Đầm Chuồn và sông Hương trước ngày đi; "
            "thay tọa độ khu khách sạn bằng cơ sở lưu trú thật sau khi người dùng đặt phòng."
        ),
    },
    "data_sources": {
        "itinerary_basis": [
            "https://visithue.vn/3-ngay-2-dem-o-Hue.html/",
            "https://khamphahue.com.vn/Du-lich/Chi-tiet/tid/Goi-y-tour-du-lich-Hue-tu-tuc-3-ngay-2-dem.html/pid/15305/cid/365",
            "https://travelhanoi.com.vn/hue-da-nang-hoi-an/du-lich-xu-hue-mong-mo-3-ngay-2-dem-1358-4727.html",
            "https://www.vietnambooking.com/du-lich/tour-du-lich/du-lich-hue.html",
        ],
        "official_price_and_destination_basis": [
            "https://eticket.hueworldheritage.org.vn/chon-ve",
            "https://vdt.hueworldheritage.org.vn/",
        ],
        "coordinate_basis": [
            "OpenStreetMap/Mapcarta/GeoNames/Wikidata coordinates for airports, Dong Ba, Imperial City, Thien Mu, royal tombs, Vong Canh, An Dinh and Truong Tien Bridge",
            "Representative central-hotel point for the Vo Thi Sau - Pham Ngu Lao zone",
            "Representative Thuy Xuan village point and Chuon Lagoon access point; the actual shop or boat pier must be confirmed before travel",
        ],
        "administrative_basis": [
            "https://xaydungchinhsach.chinhphu.vn/nghi-quyet-so-175-2024-qh15-thanh-lap-thanh-pho-hue-truc-thuoc-trung-uong-119241205102339073.htm",
            "https://chinhphu.vn/?docid=211916&pageid=27160",
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

    expected_days = list(range(1, HUE_SNAPSHOT["duration_days"] + 1))
    actual_days = [day["day_number"] for day in HUE_SNAPSHOT["days"]]
    if actual_days != expected_days:
        raise ValueError(f"Invalid day sequence: expected={expected_days}, actual={actual_days}")

    total_cost = 0
    activity_count = 0

    for day in HUE_SNAPSHOT["days"]:
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

    expected_per_person = HUE_SNAPSHOT["actual_cost_per_person"]
    if total_cost != expected_per_person:
        raise ValueError(
            f"Cost mismatch: activities={total_cost:,}, snapshot={expected_per_person:,}"
        )

    expected_total = expected_per_person * NUMBER_OF_TRAVELERS
    if HUE_SNAPSHOT["actual_total_cost"] != expected_total:
        raise ValueError("actual_total_cost must equal cost/person * traveler_count")

    breakdown = HUE_SNAPSHOT["budget_breakdown_per_person"]
    breakdown_sum = sum(value for key, value in breakdown.items() if key != "total")
    if breakdown_sum != breakdown["total"]:
        raise ValueError("Budget breakdown does not add up")
    if breakdown["total"] != expected_per_person:
        raise ValueError("Budget breakdown differs from actual_cost_per_person")

    if activity_count < 25:
        raise ValueError("The itinerary is unexpectedly short")

    return total_cost


async def seed_hue() -> None:
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
        author_email = "guide.hue@smarttravel.vn"
        stmt_user = select(User).where(User.email == author_email)
        res_user = await session.execute(stmt_user)
        user = res_user.scalar_one_or_none()

        if not user:
            print(f"No user '{author_email}' found. Creating seed author...")
            user = User(
                id=uuid.uuid4(),
                username="guide-hue",
                email=author_email,
                full_name="Nguyễn Ngọc Lam (Hướng dẫn viên di sản Huế)",
                password_hash="seed-only-account-not-for-login",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

        # 3. Create or update the public trip publication.
        slug = "lich-trinh-hue-3-ngay-2-dem-tu-ha-noi"
        stmt_pub = select(PublicTripPublication).where(PublicTripPublication.slug == slug)
        res_pub = await session.execute(stmt_pub)
        existing = res_pub.scalar_one_or_none()

        publication_values = {
            "title": HUE_SNAPSHOT["title"],
            "summary": (
                "Hành trình Huế 3 ngày 2 đêm từ Hà Nội cho 2 người, kết hợp Đại Nội, Chùa Thiên Mụ, "
                "ba lăng vua Khải Định - Minh Mạng - Tự Đức, làng hương Thủy Xuân, Đồi Vọng Cảnh, "
                "Đầm Chuồn và Cung An Định với ngân sách khoảng 7,54 triệu đồng/người."
            ),
            "destination": "Huế",
            "province_name": CURRENT_PROVINCE_NAME,
            "duration_days": 3,
            "actual_total_cost": HUE_SNAPSHOT["actual_total_cost"],
            "actual_cost_per_person": HUE_SNAPSHOT["actual_cost_per_person"],
            "overall_rating": HUE_SNAPSHOT["overall_rating"],
            "status": "published",
            "visibility": "public",
            "moderation_status": "approved",
            "cover_image_url": (
                "https://images.unsplash.com/photo-1583417319070-4a69db38a482"
                "?auto=format&fit=crop&w=1200&q=80"
            ),
            "snapshot_json": HUE_SNAPSHOT,
            "tags": [
                "Huế",
                "3 ngày 2 đêm",
                "Máy bay",
                "Đại Nội",
                "Chùa Thiên Mụ",
                "Lăng Khải Định",
                "Lăng Minh Mạng",
                "Lăng Tự Đức",
                "Làng hương Thủy Xuân",
                "Đồi Vọng Cảnh",
                "Đầm Chuồn",
                "Cung An Định",
                "Sông Hương",
                "Di sản",
                "Ẩm thực Huế",
            ],
            "save_count": 0,
            "view_count": 4380,
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
        print("Successfully seeded Hue 3D2N itinerary and locations!")


if __name__ == "__main__":
    asyncio.run(seed_hue())
