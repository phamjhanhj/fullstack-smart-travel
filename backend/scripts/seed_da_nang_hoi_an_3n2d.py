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
# DA NANG - HOI AN - BA NA HILLS 3D2N SEED DATA
#
# Itinerary basis:
# - Public Hanoi - Da Nang - Hoi An - Ba Na Hills 3-day/2-night tours.
# - Day 1: Hanoi - Da Nang - Marble Mountains - Hoi An - Da Nang.
# - Day 2: Sun World Ba Na Hills - Golden Bridge - My Khe - Dragon Bridge.
# - Day 3: Son Tra - Linh Ung Pagoda - Han Market - Da Nang - Hanoi.
#
# Administrative naming policy:
# - Da Nang city and the former Quang Nam province were reorganised into the
#   current centrally governed Da Nang city in 2025.
# - Hoi An remains the established tourism destination name, while every local
#   location in this seed stores province_name="Đà Nẵng" for database consistency.
#
# Coordinate policy:
# - POIs use public OpenStreetMap/Mapcarta, GeoNames, Wikidata and published map
#   pins. Large areas use an explicitly described representative point.
# - My Khe lodging uses a representative hotel-zone point rather than claiming
#   to be a specific hotel entrance.
# - Every location includes a Google Maps coordinate URL for manual review.
# - Coordinates were last reviewed on 2026-07-30.
#
# Cost policy:
# - actual_cost is the estimated cost PER PERSON for a group of two travellers.
# - The seed uses the standard Ba Na cable-car ticket estimate of 1,000,000 VND,
#   not the temporary U25 promotion available during part of summer 2026.
# - Flight, room, food and attraction prices are planning estimates and are not
#   binding supplier quotations.
# -----------------------------------------------------------------------------

VERIFIED_AT = "2026-07-30"
NUMBER_OF_TRAVELERS = 2
CURRENT_PROVINCE_NAME = "Đà Nẵng"


LOCATIONS: dict[str, dict[str, Any]] = {
    "noi_bai_airport": {
        "id": "77777777-7777-4777-8777-000000000001",
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
    "da_nang_airport": {
        "id": "77777777-7777-4777-8777-000000000002",
        "name": "Sân bay quốc tế Đà Nẵng",
        "address": "Đường Duy Tân, phường Hòa Cường, thành phố Đà Nẵng",
        "lat": 16.0429,
        "lng": 108.19839,
        "category": "transport",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "airport_aerodrome_center",
        "coordinate_source": "OpenStreetMap way 217476265 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=16.0429,108.19839",
        "plus_code": "7P8C25VX+59",
        "verified_at": VERIFIED_AT,
    },
    "my_khe_hotel_area": {
        "id": "77777777-7777-4777-8777-000000000003",
        "name": "Khu lưu trú ven biển Mỹ Khê",
        "address": "Khu vực Võ Nguyên Giáp - Mỹ Khê, thành phố Đà Nẵng",
        "lat": 16.0522,
        "lng": 108.2452,
        "category": "hotel",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "hotel_zone_representative_point",
        "coordinate_source": "Representative point in the My Khe beachfront hotel zone",
        "google_maps_url": "https://www.google.com/maps?q=16.0522,108.2452",
        "verified_at": VERIFIED_AT,
    },
    "marble_mountains": {
        "id": "77777777-7777-4777-8777-000000000004",
        "name": "Danh thắng Ngũ Hành Sơn - Thủy Sơn",
        "address": "81 Huyền Trân Công Chúa, phường Ngũ Hành Sơn, thành phố Đà Nẵng",
        "lat": 16.00332,
        "lng": 108.26315,
        "category": "attraction",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "main_visitor_entrance_representative_point",
        "coordinate_source": "Representative visitor entrance, cross-checked with nearby OSM POIs",
        "google_maps_url": "https://www.google.com/maps?q=16.00332,108.26315",
        "verified_at": VERIFIED_AT,
    },
    "non_nuoc_stone_village": {
        "id": "77777777-7777-4777-8777-000000000005",
        "name": "Làng đá mỹ nghệ Non Nước",
        "address": "Khu vực Non Nước, phường Ngũ Hành Sơn, thành phố Đà Nẵng",
        "lat": 16.00095,
        "lng": 108.26664,
        "category": "attraction",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "poi_pin",
        "coordinate_source": "OpenStreetMap node 10709724107 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=16.00095,108.26664",
        "plus_code": "7P8C2728+9M",
        "verified_at": VERIFIED_AT,
    },
    "hoi_an_old_town": {
        "id": "77777777-7777-4777-8777-000000000006",
        "name": "Khu phố cổ Hội An",
        "address": "Khu phố cổ Hội An, thành phố Đà Nẵng",
        "lat": 15.87713,
        "lng": 108.32866,
        "category": "attraction",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "old_town_center",
        "coordinate_source": "OpenStreetMap node 4601279489 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=15.87713,108.32866",
        "plus_code": "7P7CV8GH+VF",
        "verified_at": VERIFIED_AT,
    },
    "japanese_covered_bridge": {
        "id": "77777777-7777-4777-8777-000000000007",
        "name": "Chùa Cầu Hội An",
        "address": "Đường Nguyễn Thị Minh Khai - Trần Phú, khu phố cổ Hội An, Đà Nẵng",
        "lat": 15.8771,
        "lng": 108.32601,
        "category": "attraction",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "building_pin",
        "coordinate_source": "OpenStreetMap way 631074476 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=15.8771,108.32601",
        "plus_code": "7P7CV8GG+RC",
        "verified_at": VERIFIED_AT,
    },
    "ba_na_hills": {
        "id": "77777777-7777-4777-8777-000000000008",
        "name": "Sun World Bà Nà Hills",
        "address": "Khu du lịch Bà Nà, khu vực Hòa Vang, thành phố Đà Nẵng",
        "lat": 15.99563,
        "lng": 107.98972,
        "category": "attraction",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "theme_park_area_pin",
        "coordinate_source": "OpenStreetMap way 359114064 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=15.99563,107.98972",
        "plus_code": "7P79XXWQ+7V",
        "verified_at": VERIFIED_AT,
    },
    "golden_bridge": {
        "id": "77777777-7777-4777-8777-000000000009",
        "name": "Cầu Vàng Bà Nà Hills",
        "address": "Khu vực ga Marseille - Le Jardin d'Amour, Bà Nà Hills, Đà Nẵng",
        "lat": 15.99509,
        "lng": 107.99641,
        "category": "attraction",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "bridge_pin",
        "coordinate_source": "OpenStreetMap way 683416736 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=15.99509,107.99641",
        "plus_code": "7P79XXWW+2H",
        "verified_at": VERIFIED_AT,
    },
    "my_khe_beach_park": {
        "id": "77777777-7777-4777-8777-000000000010",
        "name": "Công viên và bãi tắm Mỹ Khê",
        "address": "Đường Võ Nguyên Giáp, phường Ngũ Hành Sơn, thành phố Đà Nẵng",
        "lat": 16.0506,
        "lng": 108.2489,
        "category": "attraction",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "beach_access_park_pin",
        "coordinate_source": "OpenStreetMap way 780440810 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=16.0506,108.2489",
        "plus_code": "7P8C362X+6H",
        "verified_at": VERIFIED_AT,
    },
    "east_sea_park": {
        "id": "77777777-7777-4777-8777-000000000011",
        "name": "Công viên Biển Đông",
        "address": "Đường Võ Nguyên Giáp, phường An Hải, thành phố Đà Nẵng",
        "lat": 16.06815,
        "lng": 108.24593,
        "category": "attraction",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "park_pin",
        "coordinate_source": "OpenStreetMap way 149699484 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=16.06815,108.24593",
        "plus_code": "7P8C369W+79",
        "verified_at": VERIFIED_AT,
    },
    "linh_ung_son_tra": {
        "id": "77777777-7777-4777-8777-000000000012",
        "name": "Chùa Linh Ứng Bãi Bụt - Sơn Trà",
        "address": "Bãi Bụt, phường Sơn Trà, thành phố Đà Nẵng",
        "lat": 16.10014,
        "lng": 108.27844,
        "category": "attraction",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "temple_complex_pin",
        "coordinate_source": "OpenStreetMap way 486703049 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=16.10014,108.27844",
        "plus_code": "7P8C472H+39",
        "verified_at": VERIFIED_AT,
    },
    "dragon_bridge": {
        "id": "77777777-7777-4777-8777-000000000013",
        "name": "Cầu Rồng Đà Nẵng",
        "address": "Cầu Rồng, sông Hàn, thành phố Đà Nẵng",
        "lat": 16.06117,
        "lng": 108.2279,
        "category": "attraction",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "bridge_pin",
        "coordinate_source": "OpenStreetMap way 694831926 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=16.06117,108.2279",
        "plus_code": "7P8C366H+F5",
        "verified_at": VERIFIED_AT,
    },
    "son_tra_night_market": {
        "id": "77777777-7777-4777-8777-000000000014",
        "name": "Chợ đêm Sơn Trà",
        "address": "Khu vực Mai Hắc Đế - Lý Nam Đế, phường An Hải, thành phố Đà Nẵng",
        "lat": 16.06187,
        "lng": 108.23166,
        "category": "restaurant",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "market_pin",
        "coordinate_source": "Published route point; cross-checked against nearby OSM features",
        "google_maps_url": "https://www.google.com/maps?q=16.06187,108.23166",
        "verified_at": VERIFIED_AT,
    },
    "han_market": {
        "id": "77777777-7777-4777-8777-000000000015",
        "name": "Chợ Hàn Đà Nẵng",
        "address": "119 Trần Phú, phường Hải Châu, thành phố Đà Nẵng",
        "lat": 16.06811,
        "lng": 108.22433,
        "category": "attraction",
        "province_name": CURRENT_PROVINCE_NAME,
        "coordinate_precision": "market_building_pin",
        "coordinate_source": "Public map pin cross-checked with nearby OSM visitor-centre and cathedral features",
        "google_maps_url": "https://www.google.com/maps?q=16.06811,108.22433",
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


DA_NANG_HOI_AN_SNAPSHOT: dict[str, Any] = {
    "title": "Lịch trình Đà Nẵng - Hội An - Bà Nà Hills 3 ngày 2 đêm từ Hà Nội",
    "destination": "Đà Nẵng - Hội An",
    "duration_days": 3,
    "traveler_count": NUMBER_OF_TRAVELERS,
    "actual_cost_per_person": 8_250_000,
    "actual_total_cost": 16_500_000,
    "overall_rating": 4.9,
    "coordinate_verified_at": VERIFIED_AT,
    "administrative_note": (
        "Hội An được giữ trong tên hành trình như một địa danh du lịch và di sản quen thuộc. "
        "Theo đơn vị hành chính hiện hành sau sắp xếp năm 2025, khu vực Hội An thuộc thành phố Đà Nẵng."
    ),
    "cost_note": (
        "Chi phí là dữ liệu seed tham khảo theo người cho nhóm 2 người. Giá vé máy bay, phòng, buffet, "
        "vé Bà Nà Hills và các dịch vụ có thể thay đổi theo ngày. Seed dùng giá vé cáp treo người lớn "
        "tham khảo 1.000.000 đồng, không áp dụng ưu đãi U25 ngắn hạn trong mùa hè 2026."
    ),
    "budget_breakdown_per_person": {
        "transport": 4_280_000,
        "lodging": 900_000,
        "food": 1_530_000,
        "tours_and_tickets": 1_340_000,
        "shopping_and_miscellaneous": 200_000,
        "total": 8_250_000,
    },
    "days": [
        {
            "day_number": 1,
            "title": "Hà Nội - Đà Nẵng - Ngũ Hành Sơn - Hội An",
            "activities": [
                build_activity(
                    location_key="noi_bai_airport",
                    start_time="05:15",
                    end_time="06:00",
                    title="Di chuyển từ trung tâm Hà Nội tới sân bay Nội Bài",
                    activity_type="transport",
                    actual_cost=120_000,
                    rating=4.8,
                    author_verdict="must_go",
                    best_time="Rời trung tâm trước giờ bay tối thiểu 3 giờ",
                    next_traveler_note="Đặt xe trước, kiểm tra nhà ga và giấy tờ tùy thân; dự phòng ùn tắc trên đường Võ Nguyên Giáp.",
                ),
                build_activity(
                    location_key="noi_bai_airport",
                    start_time="06:00",
                    end_time="07:00",
                    title="Làm thủ tục bay và ăn sáng tại Nội Bài",
                    activity_type="meal",
                    actual_cost=80_000,
                    rating=4.6,
                    author_verdict="recommended",
                    best_time="Hoàn tất ký gửi trước giờ đóng quầy",
                    next_traveler_note="Chọn món gọn nhẹ; không để pin dự phòng trong hành lý ký gửi.",
                ),
                build_activity(
                    location_key="da_nang_airport",
                    start_time="07:30",
                    end_time="09:00",
                    title="Bay Hà Nội - Đà Nẵng",
                    activity_type="transport",
                    actual_cost=1_600_000,
                    rating=4.9,
                    author_verdict="must_go",
                    best_time="Chuyến bay sáng để tận dụng ngày đầu",
                    next_traveler_note="Giá là mức seed gồm thuế/phí và hành lý cơ bản; giờ bay thực tế phải lấy từ vé đã đặt.",
                ),
                build_activity(
                    location_key="my_khe_hotel_area",
                    start_time="09:15",
                    end_time="09:45",
                    title="Di chuyển từ sân bay về khu lưu trú Mỹ Khê",
                    activity_type="transport",
                    actual_cost=70_000,
                    rating=4.8,
                    author_verdict="must_go",
                    best_time="Đi taxi hoặc xe công nghệ theo đồng hồ/giá ứng dụng",
                    next_traveler_note="Tọa độ là khu khách sạn đại diện; cần thay bằng khách sạn thật khi người dùng đặt phòng.",
                ),
                build_activity(
                    location_key="my_khe_hotel_area",
                    start_time="09:45",
                    end_time="11:15",
                    title="Gửi hành lý, nghỉ ngắn và ăn trưa món Quảng",
                    activity_type="meal",
                    actual_cost=200_000,
                    rating=4.8,
                    author_verdict="recommended",
                    best_time="Ăn trước khi đi Ngũ Hành Sơn",
                    next_traveler_note="Gợi ý mì Quảng, bánh tráng cuốn thịt heo hoặc cơm gà; hỏi khách sạn về giờ nhận phòng chính thức.",
                ),
                build_activity(
                    location_key="marble_mountains",
                    start_time="11:15",
                    end_time="11:45",
                    title="Di chuyển Mỹ Khê - Ngũ Hành Sơn",
                    activity_type="transport",
                    actual_cost=70_000,
                    rating=4.7,
                    author_verdict="must_go",
                    best_time="Tránh giờ nắng gắt nếu có thể",
                    next_traveler_note="Mang nước, giày chống trượt và không để hành lý giá trị trên xe.",
                ),
                build_activity(
                    location_key="marble_mountains",
                    start_time="11:45",
                    end_time="13:30",
                    title="Khám phá Thủy Sơn, động Huyền Không và chùa trên núi",
                    activity_type="attraction",
                    actual_cost=80_000,
                    rating=4.9,
                    author_verdict="must_go",
                    best_time="Sáng hoặc đầu chiều ngày trời mát",
                    next_traveler_note="Chi phí gồm vé và phần dự phòng thang máy; bậc đá có thể trơn, không chen lấn trong hang hẹp.",
                ),
                build_activity(
                    location_key="non_nuoc_stone_village",
                    start_time="13:35",
                    end_time="14:15",
                    title="Tham quan Làng đá mỹ nghệ Non Nước",
                    activity_type="attraction",
                    actual_cost=0,
                    rating=4.6,
                    author_verdict="recommended",
                    best_time="Sau khi xuống núi",
                    next_traveler_note="Không chạm vào sản phẩm dễ vỡ; hỏi rõ vật liệu, giá và phương thức vận chuyển trước khi mua.",
                ),
                build_activity(
                    location_key="hoi_an_old_town",
                    start_time="14:15",
                    end_time="15:00",
                    title="Di chuyển Ngũ Hành Sơn - Phố cổ Hội An",
                    activity_type="transport",
                    actual_cost=90_000,
                    rating=4.8,
                    author_verdict="must_go",
                    best_time="Tới Hội An trước khung giờ phố đi bộ buổi chiều",
                    next_traveler_note="Nếu đi xe công nghệ một chiều, thống nhất điểm đón về trước khi phố cấm xe cơ giới.",
                ),
                build_activity(
                    location_key="hoi_an_old_town",
                    start_time="15:00",
                    end_time="16:30",
                    title="Mua vé và tham quan các công trình di sản trong phố cổ",
                    activity_type="attraction",
                    actual_cost=120_000,
                    rating=4.9,
                    author_verdict="must_go",
                    best_time="15:00-17:00, nắng dịu và các điểm còn mở cửa",
                    next_traveler_note="Giữ vé trong suốt buổi tham quan; lựa chọn số điểm di tích theo quyền lợi ghi trên vé hiện hành.",
                ),
                build_activity(
                    location_key="japanese_covered_bridge",
                    start_time="16:35",
                    end_time="17:10",
                    title="Tham quan Chùa Cầu và khu phố Minh An",
                    activity_type="attraction",
                    actual_cost=0,
                    rating=4.9,
                    author_verdict="must_go",
                    best_time="Chiều muộn trước khi đèn lồng lên sáng",
                    next_traveler_note="Đi theo luồng khách, không đứng chắn lối trên cầu và tuân thủ hướng dẫn bảo tồn di tích.",
                ),
                build_activity(
                    location_key="hoi_an_old_town",
                    start_time="17:15",
                    end_time="18:30",
                    title="Ăn tối đặc sản Hội An",
                    activity_type="meal",
                    actual_cost=220_000,
                    rating=4.9,
                    author_verdict="must_go",
                    best_time="Ăn trước giờ phố đông nhất",
                    next_traveler_note="Gợi ý cao lầu, cơm gà, hoành thánh và bánh hoa hồng trắng; hỏi giá trước khi gọi thêm món.",
                ),
                build_activity(
                    location_key="hoi_an_old_town",
                    start_time="18:30",
                    end_time="20:00",
                    title="Dạo phố đèn lồng và đi thuyền ngắn trên sông Hoài",
                    activity_type="attraction",
                    actual_cost=80_000,
                    rating=4.9,
                    author_verdict="must_go",
                    best_time="18:30-20:00",
                    next_traveler_note="Thỏa thuận rõ giá và thời lượng thuyền; mặc áo phao, không thả rác hoặc vật liệu khó phân hủy xuống sông.",
                ),
                build_activity(
                    location_key="my_khe_hotel_area",
                    start_time="20:00",
                    end_time="21:00",
                    title="Di chuyển Hội An về Đà Nẵng",
                    activity_type="transport",
                    actual_cost=100_000,
                    rating=4.8,
                    author_verdict="must_go",
                    best_time="Rời Hội An trước 20:30 để nghỉ sớm",
                    next_traveler_note="Xác nhận biển số xe và điểm trả; không ngủ quên đồ cá nhân trên xe.",
                ),
                build_activity(
                    location_key="my_khe_hotel_area",
                    start_time="21:00",
                    end_time="21:30",
                    title="Nhận phòng và nghỉ đêm tại khu biển Mỹ Khê",
                    activity_type="lodging",
                    actual_cost=450_000,
                    rating=4.7,
                    author_verdict="must_go",
                    best_time="Đặt phòng có lễ tân muộn và bữa sáng",
                    next_traveler_note="Chi phí tính theo người khi 2 người ở chung phòng; kiểm tra chính sách giữ giấy tờ và giờ ăn sáng.",
                ),
            ],
        },
        {
            "day_number": 2,
            "title": "Bà Nà Hills - Cầu Vàng - biển Mỹ Khê - Cầu Rồng",
            "activities": [
                build_activity(
                    location_key="my_khe_hotel_area",
                    start_time="06:15",
                    end_time="07:00",
                    title="Ăn sáng tại khách sạn",
                    activity_type="meal",
                    actual_cost=0,
                    rating=4.6,
                    author_verdict="recommended",
                    best_time="Ăn trước 07:00",
                    next_traveler_note="Mang áo khoác mỏng vì nhiệt độ trên Bà Nà có thể thấp hơn trung tâm thành phố.",
                ),
                build_activity(
                    location_key="ba_na_hills",
                    start_time="07:00",
                    end_time="08:15",
                    title="Xe đưa đón Đà Nẵng - Bà Nà Hills",
                    activity_type="transport",
                    actual_cost=180_000,
                    rating=4.8,
                    author_verdict="must_go",
                    best_time="Khởi hành sớm để tránh xếp hàng dài",
                    next_traveler_note="Có thể dùng shuttle ghép; xác nhận điểm đón, giờ về và phạm vi đưa đón trước khi thanh toán.",
                ),
                build_activity(
                    location_key="ba_na_hills",
                    start_time="08:15",
                    end_time="08:45",
                    title="Nhận vé cáp treo và vào Sun World Bà Nà Hills",
                    activity_type="attraction",
                    actual_cost=1_000_000,
                    rating=4.9,
                    author_verdict="must_go",
                    best_time="Ngay khi khu du lịch mở cửa",
                    next_traveler_note="Giá seed là mức vé người lớn tham khảo, không áp dụng ưu đãi ngắn hạn; kiểm tra giá và lịch vận hành chính thức trước ngày đi.",
                ),
                build_activity(
                    location_key="golden_bridge",
                    start_time="08:45",
                    end_time="09:15",
                    title="Đi cáp treo lên khu Cầu Vàng",
                    activity_type="transport",
                    actual_cost=0,
                    rating=5.0,
                    author_verdict="must_go",
                    best_time="Chuyến cáp đầu ngày",
                    next_traveler_note="Không tự ý mở cửa cabin; giữ trẻ em ngồi yên và bảo quản điện thoại khi chụp qua cửa kính.",
                ),
                build_activity(
                    location_key="golden_bridge",
                    start_time="09:15",
                    end_time="10:15",
                    title="Check-in Cầu Vàng",
                    activity_type="attraction",
                    actual_cost=0,
                    rating=5.0,
                    author_verdict="must_go",
                    best_time="Trước 10:00 để giảm đông và sương dày",
                    next_traveler_note="Không dừng quá lâu giữa luồng đi; gió mạnh nên giữ chắc mũ, điện thoại và máy ảnh.",
                ),
                build_activity(
                    location_key="golden_bridge",
                    start_time="10:15",
                    end_time="11:45",
                    title="Tham quan Le Jardin d'Amour và khu tâm linh Bà Nà",
                    activity_type="attraction",
                    actual_cost=0,
                    rating=4.8,
                    author_verdict="recommended",
                    best_time="Buổi sáng trời quang",
                    next_traveler_note="Giữ trang phục và cách ứng xử phù hợp tại khu chùa; lịch hoạt động có thể đổi do thời tiết.",
                ),
                build_activity(
                    location_key="ba_na_hills",
                    start_time="11:45",
                    end_time="13:00",
                    title="Ăn trưa buffet trên Bà Nà Hills",
                    activity_type="meal",
                    actual_cost=350_000,
                    rating=4.7,
                    author_verdict="recommended",
                    best_time="Ăn trước khung 12:00-12:30 đông khách",
                    next_traveler_note="Xác nhận nhà hàng nằm trong combo hay mua riêng; lấy lượng vừa đủ để tránh lãng phí.",
                ),
                build_activity(
                    location_key="ba_na_hills",
                    start_time="13:00",
                    end_time="15:15",
                    title="Khám phá Làng Pháp và Fantasy Park",
                    activity_type="attraction",
                    actual_cost=0,
                    rating=4.9,
                    author_verdict="must_go",
                    best_time="Đầu giờ chiều",
                    next_traveler_note="Một số trò chơi có giới hạn chiều cao, sức khỏe hoặc phụ phí; tuân thủ hướng dẫn an toàn tại từng trò.",
                ),
                build_activity(
                    location_key="ba_na_hills",
                    start_time="15:15",
                    end_time="16:00",
                    title="Xuống cáp treo và tập trung tại điểm đón",
                    activity_type="transport",
                    actual_cost=0,
                    rating=4.8,
                    author_verdict="must_go",
                    best_time="Xuống trước giờ cao điểm cuối ngày",
                    next_traveler_note="Theo dõi thông báo tuyến cáp đang vận hành; không tách đoàn sát giờ xe về.",
                ),
                build_activity(
                    location_key="my_khe_hotel_area",
                    start_time="16:00",
                    end_time="17:15",
                    title="Xe Bà Nà Hills về khu biển Mỹ Khê",
                    activity_type="transport",
                    actual_cost=180_000,
                    rating=4.8,
                    author_verdict="must_go",
                    best_time="Rời Bà Nà trước 16:30",
                    next_traveler_note="Thời gian có thể tăng nếu mưa hoặc ùn tại cổng; báo tài xế đúng điểm khách sạn.",
                ),
                build_activity(
                    location_key="my_khe_beach_park",
                    start_time="17:20",
                    end_time="18:30",
                    title="Tắm biển Mỹ Khê và ngắm chiều trên bờ biển",
                    activity_type="attraction",
                    actual_cost=60_000,
                    rating=4.9,
                    author_verdict="must_go",
                    best_time="17:00-18:30 khi có cứu hộ",
                    next_traveler_note="Chi phí dự phòng gửi đồ và tắm nước ngọt; chỉ bơi trong khu có cờ an toàn, không xuống biển khi sóng lớn.",
                ),
                build_activity(
                    location_key="my_khe_hotel_area",
                    start_time="19:00",
                    end_time="20:15",
                    title="Ăn tối hải sản tại khu ven biển",
                    activity_type="meal",
                    actual_cost=300_000,
                    rating=4.8,
                    author_verdict="must_go",
                    best_time="19:00-20:00",
                    next_traveler_note="Yêu cầu cân hải sản trước mặt và xác nhận đơn giá theo kg; ưu tiên quán niêm yết giá rõ ràng.",
                ),
                build_activity(
                    location_key="dragon_bridge",
                    start_time="20:30",
                    end_time="21:15",
                    title="Dạo Cầu Rồng và bờ sông Hàn",
                    activity_type="attraction",
                    actual_cost=0,
                    rating=4.9,
                    author_verdict="must_go",
                    best_time="Buổi tối; kiểm tra lịch phun lửa, phun nước hiện hành",
                    next_traveler_note="Không đứng dưới đầu rồng nếu không muốn bị ướt; tuân thủ phân luồng giao thông khi có chương trình biểu diễn.",
                ),
                build_activity(
                    location_key="son_tra_night_market",
                    start_time="21:15",
                    end_time="22:00",
                    title="Ăn vặt và mua quà nhỏ tại Chợ đêm Sơn Trà",
                    activity_type="meal",
                    actual_cost=120_000,
                    rating=4.7,
                    author_verdict="recommended",
                    best_time="Sau khi tham quan Cầu Rồng",
                    next_traveler_note="Giữ ví và điện thoại tại nơi đông người; hỏi giá trước khi gọi món hoặc mua đồ lưu niệm.",
                ),
                build_activity(
                    location_key="my_khe_hotel_area",
                    start_time="22:10",
                    end_time="22:30",
                    title="Trở về khách sạn và nghỉ đêm",
                    activity_type="lodging",
                    actual_cost=450_000,
                    rating=4.7,
                    author_verdict="must_go",
                    best_time="Nghỉ sớm để sáng hôm sau đi Sơn Trà",
                    next_traveler_note="Sắp xếp hành lý từ tối và xác nhận giờ trả phòng, xe ra sân bay.",
                ),
            ],
        },
        {
            "day_number": 3,
            "title": "Sơn Trà - Chùa Linh Ứng - Chợ Hàn - Đà Nẵng - Hà Nội",
            "activities": [
                build_activity(
                    location_key="my_khe_hotel_area",
                    start_time="06:15",
                    end_time="07:00",
                    title="Ăn sáng và làm thủ tục trả phòng",
                    activity_type="meal",
                    actual_cost=0,
                    rating=4.6,
                    author_verdict="recommended",
                    best_time="Hoàn tất hành lý trước 07:00",
                    next_traveler_note="Gửi hành lý tại lễ tân nếu chưa ra sân bay ngay; kiểm tra kỹ két sắt, ổ điện và phòng tắm.",
                ),
                build_activity(
                    location_key="linh_ung_son_tra",
                    start_time="07:00",
                    end_time="07:35",
                    title="Di chuyển lên Bán đảo Sơn Trà - Chùa Linh Ứng",
                    activity_type="transport",
                    actual_cost=80_000,
                    rating=4.8,
                    author_verdict="must_go",
                    best_time="Sáng sớm, đường ít xe và trời dịu",
                    next_traveler_note="Đi đúng tuyến được phép; không tiếp cận, cho ăn hoặc trêu chọc động vật hoang dã trên Sơn Trà.",
                ),
                build_activity(
                    location_key="linh_ung_son_tra",
                    start_time="07:35",
                    end_time="09:00",
                    title="Viếng Chùa Linh Ứng và ngắm toàn cảnh biển Đà Nẵng",
                    activity_type="attraction",
                    actual_cost=0,
                    rating=4.9,
                    author_verdict="must_go",
                    best_time="07:30-09:00",
                    next_traveler_note="Mặc trang phục lịch sự, nói nhỏ, không dùng flycam khi chưa được phép và giữ khoảng cách với khỉ.",
                ),
                build_activity(
                    location_key="east_sea_park",
                    start_time="09:15",
                    end_time="10:00",
                    title="Uống cà phê và nghỉ tại Công viên Biển Đông",
                    activity_type="meal",
                    actual_cost=80_000,
                    rating=4.7,
                    author_verdict="recommended",
                    best_time="Buổi sáng có gió biển",
                    next_traveler_note="Đây là điểm nghỉ nhẹ trước khi mua sắm; giữ vệ sinh công cộng và tránh nắng trực tiếp quá lâu.",
                ),
                build_activity(
                    location_key="han_market",
                    start_time="10:15",
                    end_time="11:30",
                    title="Mua đặc sản tại Chợ Hàn",
                    activity_type="shopping",
                    actual_cost=200_000,
                    rating=4.7,
                    author_verdict="recommended",
                    best_time="Buổi sáng trước giờ trả phòng và ra sân bay",
                    next_traveler_note="Kiểm tra hạn dùng, niêm phong đồ có mùi và quy định hành lý hàng không; không mua vượt ngân sách dự kiến.",
                ),
                build_activity(
                    location_key="han_market",
                    start_time="11:30",
                    end_time="12:30",
                    title="Ăn trưa tại khu trung tâm Hải Châu",
                    activity_type="meal",
                    actual_cost=180_000,
                    rating=4.8,
                    author_verdict="recommended",
                    best_time="Ăn trước khi ra sân bay",
                    next_traveler_note="Gợi ý bún chả cá, bánh xèo hoặc cơm; chọn món dễ tiêu nếu chuyến bay có thể rung lắc.",
                ),
                build_activity(
                    location_key="da_nang_airport",
                    start_time="12:30",
                    end_time="13:00",
                    title="Di chuyển ra sân bay Đà Nẵng",
                    activity_type="transport",
                    actual_cost=70_000,
                    rating=4.8,
                    author_verdict="must_go",
                    best_time="Có mặt trước chuyến bay nội địa ít nhất 2 giờ",
                    next_traveler_note="Xác nhận nhà ga, cân lại hành lý và đóng gói kỹ đặc sản dạng lỏng hoặc có mùi.",
                ),
                build_activity(
                    location_key="noi_bai_airport",
                    start_time="14:30",
                    end_time="16:00",
                    title="Bay Đà Nẵng - Hà Nội",
                    activity_type="transport",
                    actual_cost=1_600_000,
                    rating=4.9,
                    author_verdict="must_go",
                    best_time="Chuyến chiều để vẫn có nửa ngày tham quan",
                    next_traveler_note="Giờ bay chỉ là mẫu lịch trình; hệ thống production phải đồng bộ theo chuyến bay người dùng đã đặt.",
                ),
                build_activity(
                    location_key="noi_bai_airport",
                    start_time="16:15",
                    end_time="17:15",
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
            "Ngũ Hành Sơn",
            "Phố cổ Hội An",
            "Chùa Cầu",
            "Cầu Vàng",
            "Bà Nà Hills",
            "Bãi biển Mỹ Khê",
            "Chùa Linh Ứng Sơn Trà",
            "Cầu Rồng",
        ],
        "best_foods": [
            "Mì Quảng",
            "Bánh tráng cuốn thịt heo",
            "Cao lầu",
            "Cơm gà Hội An",
            "Bún chả cá",
            "Hải sản Đà Nẵng",
        ],
        "tips": (
            "Đặt vé máy bay và phòng sớm; theo dõi thời tiết Bà Nà và biển Mỹ Khê; mang giày chống trượt khi đi "
            "Ngũ Hành Sơn; kiểm tra lịch phố đi bộ Hội An và lịch biểu diễn Cầu Rồng; không sử dụng ưu đãi vé ngắn hạn "
            "làm giá cố định trong production; thay điểm khu lưu trú đại diện bằng khách sạn thật sau khi người dùng đặt."
        ),
    },
    "data_sources": {
        "itinerary_basis": [
            "https://tour.hanoitourism.com.vn/sp/tour-da-nang-hoi-an-03-ngay-tu-ha-noi/",
            "https://www.tourismdanang.vn/tour/du-lich-da-nang-ba-na-hoi-an-3-ngay-2-dem/",
            "https://travelhanoi.com.vn/hue-da-nang-hoi-an/tour-da-nang-ba-na-hill-hoi-an-3n2d-1359-4727.html",
        ],
        "official_price_and_destination_basis": [
            "https://sunworld.vn/en/banahills/vouchers/from-july-10-u25-visitors-can-experience-ba-na-hills-to-the-fullest-from-just-vnd-500-000-21304",
            "https://www.hoianworldheritage.org.vn/vi/news/Du-lich-Hoi-An/cap-nhat-ve-tham-quan-khu-pho-co-hoi-an-hanh-trinh-cham-ve-nguyen-ban-giua-long-di-san-3033.hwh",
            "https://www.hoianworldheritage.org.vn/vi/news/Dieu-can-biet/ve-tham-quan-hoi-an-1940.hwh",
        ],
        "coordinate_basis": [
            "OpenStreetMap/Mapcarta/GeoNames/Wikidata coordinates for the airports, Hoi An, Chua Cau, Ba Na, Golden Bridge, My Khe, East Sea Park, Linh Ung, Dragon Bridge and Non Nuoc",
            "Published public map points cross-checked against nearby OSM features for Son Tra Night Market and Han Market",
            "Representative point for the My Khe hotel zone and Marble Mountains visitor entrance",
        ],
        "administrative_basis": [
            "https://www.danang.gov.vn/vi/web/dng/w/tong-quan-ve-thanh-pho-da-nang",
            "https://xaydungchinhsach.chinhphu.vn/toan-van-nghi-quyet-so-1659-nq-ubtvqh15-sap-xep-cac-dvhc-cap-xa-cua-thanh-pho-da-nang-nam-2025-119250616202714604.htm",
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

    expected_days = list(range(1, DA_NANG_HOI_AN_SNAPSHOT["duration_days"] + 1))
    actual_days = [day["day_number"] for day in DA_NANG_HOI_AN_SNAPSHOT["days"]]
    if actual_days != expected_days:
        raise ValueError(f"Invalid day sequence: expected={expected_days}, actual={actual_days}")

    total_cost = 0
    activity_count = 0

    for day in DA_NANG_HOI_AN_SNAPSHOT["days"]:
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

    expected_per_person = DA_NANG_HOI_AN_SNAPSHOT["actual_cost_per_person"]
    if total_cost != expected_per_person:
        raise ValueError(
            f"Cost mismatch: activities={total_cost:,}, snapshot={expected_per_person:,}"
        )

    expected_total = expected_per_person * NUMBER_OF_TRAVELERS
    if DA_NANG_HOI_AN_SNAPSHOT["actual_total_cost"] != expected_total:
        raise ValueError("actual_total_cost must equal cost/person * traveler_count")

    breakdown = DA_NANG_HOI_AN_SNAPSHOT["budget_breakdown_per_person"]
    breakdown_sum = sum(value for key, value in breakdown.items() if key != "total")
    if breakdown_sum != breakdown["total"]:
        raise ValueError("Budget breakdown does not add up")
    if breakdown["total"] != expected_per_person:
        raise ValueError("Budget breakdown differs from actual_cost_per_person")

    if activity_count < 25:
        raise ValueError("The itinerary is unexpectedly short")

    return total_cost


async def seed_da_nang_hoi_an() -> None:
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
        author_email = "guide.danang.hoian@smarttravel.vn"
        stmt_user = select(User).where(User.email == author_email)
        res_user = await session.execute(stmt_user)
        user = res_user.scalar_one_or_none()

        if not user:
            print(f"No user '{author_email}' found. Creating seed author...")
            user = User(
                id=uuid.uuid4(),
                username="guide-danang-hoian",
                email=author_email,
                full_name="Trần Minh An (Hướng dẫn viên miền Trung)",
                password_hash="seed-only-account-not-for-login",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

        # 3. Create or update the public trip publication.
        slug = "lich-trinh-da-nang-hoi-an-ba-na-hills-3-ngay-2-dem"
        stmt_pub = select(PublicTripPublication).where(PublicTripPublication.slug == slug)
        res_pub = await session.execute(stmt_pub)
        existing = res_pub.scalar_one_or_none()

        publication_values = {
            "title": DA_NANG_HOI_AN_SNAPSHOT["title"],
            "summary": (
                "Hành trình Đà Nẵng - Hội An - Bà Nà Hills 3 ngày 2 đêm từ Hà Nội cho 2 người, "
                "kết hợp Ngũ Hành Sơn, phố cổ và Chùa Cầu Hội An, Cầu Vàng, Làng Pháp, biển Mỹ Khê, "
                "Cầu Rồng, Chùa Linh Ứng Sơn Trà và Chợ Hàn với ngân sách khoảng 8,25 triệu đồng/người."
            ),
            "destination": "Đà Nẵng - Hội An",
            "province_name": CURRENT_PROVINCE_NAME,
            "duration_days": 3,
            "actual_total_cost": DA_NANG_HOI_AN_SNAPSHOT["actual_total_cost"],
            "actual_cost_per_person": DA_NANG_HOI_AN_SNAPSHOT["actual_cost_per_person"],
            "overall_rating": DA_NANG_HOI_AN_SNAPSHOT["overall_rating"],
            "status": "published",
            "visibility": "public",
            "moderation_status": "approved",
            "cover_image_url": (
                "https://images.unsplash.com/photo-1559592413-7cec4d0cae2b"
                "?auto=format&fit=crop&w=1200&q=80"
            ),
            "snapshot_json": DA_NANG_HOI_AN_SNAPSHOT,
            "tags": [
                "Đà Nẵng",
                "Hội An",
                "3 ngày 2 đêm",
                "Máy bay",
                "Ngũ Hành Sơn",
                "Chùa Cầu",
                "Bà Nà Hills",
                "Cầu Vàng",
                "Làng Pháp",
                "Biển Mỹ Khê",
                "Cầu Rồng",
                "Sơn Trà",
                "Chùa Linh Ứng",
                "Di sản",
                "Miền Trung",
            ],
            "save_count": 0,
            "view_count": 5210,
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
        print("Successfully seeded Da Nang - Hoi An - Ba Na Hills 3D2N itinerary!")


if __name__ == "__main__":
    asyncio.run(seed_da_nang_hoi_an())
