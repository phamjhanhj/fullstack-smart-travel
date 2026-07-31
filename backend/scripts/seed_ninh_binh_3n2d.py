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
# NINH BINH 3D2N SEED DATA
#
# Itinerary basis:
# - Public Ninh Binh 3-day/2-night itineraries from Hanoi.
# - Route is arranged to reduce backtracking and keep the bird-garden visit near
#   sunset, when birds commonly return to the nesting area.
#
# Coordinate policy:
# - POIs use published OpenStreetMap/Mapcarta nodes, Wikidata coordinates, or
#   Google Maps Plus Code centers.
# - A large complex is represented by its public entrance, ticket office, wharf,
#   or a clearly labelled representative point rather than an invented pin.
# - Every location includes a Google Maps URL for manual verification.
# - Coordinates were last reviewed on 2026-07-30.
#
# Cost policy:
# - actual_cost is the estimated cost PER PERSON for this sample itinerary.
# - Costs are seed/demo values, not binding quotations.
# - Recheck tickets, accommodation and transport before a real trip.
# -----------------------------------------------------------------------------

VERIFIED_AT = "2026-07-30"
NUMBER_OF_TRAVELERS = 2

LOCATIONS: dict[str, dict[str, Any]] = {
    "ha_noi_opera_house": {
        "id": "33333333-3333-4333-8333-333333333301",
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
    "co_do_hoa_lu": {
        "id": "33333333-3333-4333-8333-333333333302",
        "name": "Khu di tích Cố đô Hoa Lư",
        "address": "Trường Yên, Hoa Lư, Ninh Bình",
        "lat": 20.282850,
        "lng": 105.901750,
        "category": "attraction",
        "province_name": "Ninh Bình",
        "plus_code": "7PG77WM2+4M",
        "coordinate_precision": "historic_complex_center",
        "coordinate_source": "OpenStreetMap way 1362974362 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=20.282850,105.901750",
        "verified_at": VERIFIED_AT,
    },
    "den_vua_dinh": {
        "id": "33333333-3333-4333-8333-333333333303",
        "name": "Đền Vua Đinh Tiên Hoàng",
        "address": "Khu di tích Cố đô Hoa Lư, Trường Yên, Ninh Bình",
        "lat": 20.284610,
        "lng": 105.905140,
        "category": "attraction",
        "province_name": "Ninh Bình",
        "plus_code": "7PG77WM4+R3",
        "coordinate_precision": "poi_building",
        "coordinate_source": "OpenStreetMap way 772041809 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=20.284610,105.905140",
        "verified_at": VERIFIED_AT,
    },
    "den_vua_le": {
        "id": "33333333-3333-4333-8333-333333333304",
        "name": "Đền Vua Lê Đại Hành",
        "address": "Khu di tích Cố đô Hoa Lư, Trường Yên, Ninh Bình",
        "lat": 20.286170,
        "lng": 105.905720,
        "category": "attraction",
        "province_name": "Ninh Bình",
        "plus_code": "7PG77WP4+F7",
        "coordinate_precision": "poi_building",
        "coordinate_source": "OpenStreetMap way 772041801 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=20.286170,105.905720",
        "verified_at": VERIFIED_AT,
    },
    "ben_thuyen_trang_an": {
        "id": "33333333-3333-4333-8333-333333333305",
        "name": "Bến thuyền Khu du lịch sinh thái Tràng An",
        "address": "Tràng An, Hoa Lư, Ninh Bình",
        "lat": 20.253128,
        "lng": 105.918848,
        "category": "attraction",
        "province_name": "Ninh Bình",
        "plus_code": "7PG77W39+7G5",
        "coordinate_precision": "plus_code_center",
        "coordinate_source": "Google Maps Plus Code 7W39+7G5 - Trang An Departure Boat Ticket",
        "google_maps_url": "https://www.google.com/maps?q=20.253128,105.918848",
        "verified_at": VERIFIED_AT,
    },
    "trung_tam_tam_coc": {
        "id": "33333333-3333-4333-8333-333333333306",
        "name": "Khu lưu trú trung tâm Tam Cốc",
        "address": "Khu Tam Cốc, Nam Hoa Lư, Ninh Bình",
        "lat": 20.215753,
        "lng": 105.937285,
        "category": "hotel",
        "province_name": "Ninh Bình",
        "plus_code": "7PG76W8P+8W3",
        "coordinate_precision": "accommodation_area_center",
        "coordinate_source": "Google Maps Plus Code area center near Tam Coc main street",
        "google_maps_url": "https://www.google.com/maps?q=20.215753,105.937285",
        "verified_at": VERIFIED_AT,
    },
    "khu_am_thuc_tam_coc": {
        "id": "33333333-3333-4333-8333-333333333307",
        "name": "Khu ẩm thực trung tâm Tam Cốc",
        "address": "Đường Tam Cốc - Bích Động, Nam Hoa Lư, Ninh Bình",
        "lat": 20.215590,
        "lng": 105.937500,
        "category": "restaurant",
        "province_name": "Ninh Bình",
        "plus_code": "7PG76W8Q+62",
        "coordinate_precision": "restaurant_area_representative_point",
        "coordinate_source": "OpenStreetMap restaurant node 4829977125 near Tam Coc wharf",
        "google_maps_url": "https://www.google.com/maps?q=20.215590,105.937500",
        "verified_at": VERIFIED_AT,
    },
    "cho_dem_tam_coc": {
        "id": "33333333-3333-4333-8333-333333333308",
        "name": "Chợ đêm và khu đi bộ Tam Cốc",
        "address": "Khu trung tâm Tam Cốc, Nam Hoa Lư, Ninh Bình",
        "lat": 20.213880,
        "lng": 105.934610,
        "category": "attraction",
        "province_name": "Ninh Bình",
        "coordinate_precision": "marketplace_pin",
        "coordinate_source": "OpenStreetMap node 5350977622 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=20.213880,105.934610",
        "verified_at": VERIFIED_AT,
    },
    "ben_thuyen_tam_coc": {
        "id": "33333333-3333-4333-8333-333333333309",
        "name": "Bến thuyền Tam Cốc",
        "address": "Đình Các, Nam Hoa Lư, Ninh Bình",
        "lat": 20.216340,
        "lng": 105.937460,
        "category": "attraction",
        "province_name": "Ninh Bình",
        "plus_code": "7PG76W8P+GX",
        "coordinate_precision": "wharf_pin",
        "coordinate_source": "OpenStreetMap node 4567308091 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=20.216340,105.937460",
        "verified_at": VERIFIED_AT,
    },
    "chua_bich_dong": {
        "id": "33333333-3333-4333-8333-333333333310",
        "name": "Chùa Bích Động",
        "address": "Ninh Hải, Nam Hoa Lư, Ninh Bình",
        "lat": 20.217220,
        "lng": 105.914100,
        "category": "attraction",
        "province_name": "Ninh Bình",
        "plus_code": "7PG76W87+VJ",
        "coordinate_precision": "poi_pin",
        "coordinate_source": "GeoNames/Wikidata coordinate via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=20.217220,105.914100",
        "verified_at": VERIFIED_AT,
    },
    "hang_mua": {
        "id": "33333333-3333-4333-8333-333333333311",
        "name": "Khu du lịch Hang Múa - đỉnh Ngọa Long",
        "address": "Khê Hạ, Ninh Xuân, Hoa Lư, Ninh Bình",
        "lat": 20.229880,
        "lng": 105.934210,
        "category": "attraction",
        "province_name": "Ninh Bình",
        "plus_code": "7PG76WHM+XM",
        "coordinate_precision": "tourist_area_pin",
        "coordinate_source": "GeoNames/Wikidata coordinate via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=20.229880,105.934210",
        "verified_at": VERIFIED_AT,
    },
    "thung_nham": {
        "id": "33333333-3333-4333-8333-333333333312",
        "name": "Khu du lịch sinh thái Thung Nham",
        "address": "Hải Nham, Nam Hoa Lư, Ninh Bình",
        "lat": 20.216400,
        "lng": 105.901890,
        "category": "attraction",
        "province_name": "Ninh Bình",
        "plus_code": "7PG76W82+HQ",
        "coordinate_precision": "ticket_office_pin",
        "coordinate_source": "OpenStreetMap ticket node 3887717277 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=20.216400,105.901890",
        "verified_at": VERIFIED_AT,
    },
    "chua_bai_dinh": {
        "id": "33333333-3333-4333-8333-333333333313",
        "name": "Quần thể chùa Bái Đính",
        "address": "Gia Sinh, Gia Viễn, Ninh Bình",
        "lat": 20.275230,
        "lng": 105.865470,
        "category": "attraction",
        "province_name": "Ninh Bình",
        "plus_code": "7PG77VG8+35",
        "coordinate_precision": "temple_complex_pin",
        "coordinate_source": "OpenStreetMap node 11101746405 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=20.275230,105.865470",
        "verified_at": VERIFIED_AT,
    },
    "dong_am_tien": {
        "id": "33333333-3333-4333-8333-333333333314",
        "name": "Động Am Tiên - Tuyệt Tịnh Cốc",
        "address": "Trường Yên, Hoa Lư, Ninh Bình",
        "lat": 20.281540,
        "lng": 105.911450,
        "category": "attraction",
        "province_name": "Ninh Bình",
        "plus_code": "7PG77WJ6+JH",
        "coordinate_precision": "place_of_worship_pin",
        "coordinate_source": "OpenStreetMap node 5973661787 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=20.281540,105.911450",
        "verified_at": VERIFIED_AT,
    },
}


NINH_BINH_SNAPSHOT: dict[str, Any] = {
    "title": "Lịch trình Ninh Bình 3 ngày 2 đêm chi tiết từ Hà Nội",
    "destination": "Ninh Bình",
    "duration_days": 3,
    "traveler_count": NUMBER_OF_TRAVELERS,
    "actual_cost_per_person": 3_770_000,
    "actual_total_cost": 7_540_000,
    "overall_rating": 4.9,
    "coordinate_verified_at": VERIFIED_AT,
    "cost_note": (
        "Chi phí là mức seed tham khảo theo người, không phải báo giá cố định. "
        "Cần kiểm tra lại vé thắng cảnh, phòng, xe và thời tiết trước ngày đi."
    ),
    "budget_breakdown_per_person": {
        "transport": 750_000,
        "lodging": 700_000,
        "food": 1_200_000,
        "tours_and_tickets": 970_000,
        "miscellaneous": 150_000,
        "total": 3_770_000,
    },
    "days": [
        {
            "day_number": 1,
            "title": "Hà Nội – Cố đô Hoa Lư – Tràng An – Tam Cốc",
            "activities": [
                {
                    "location_id": LOCATIONS["ha_noi_opera_house"]["id"],
                    "lat": LOCATIONS["ha_noi_opera_house"]["lat"],
                    "lng": LOCATIONS["ha_noi_opera_house"]["lng"],
                    "start_time": "05:45",
                    "end_time": "06:00",
                    "title": "Tập trung và ăn sáng nhẹ tại Nhà hát Lớn Hà Nội",
                    "type": "meal",
                    "address": LOCATIONS["ha_noi_opera_house"]["address"],
                    "actual_cost": 50_000,
                    "rating": 4.7,
                    "author_verdict": "recommended",
                    "best_time": "Có mặt trước giờ xe chạy 15 phút",
                    "next_traveler_note": (
                        "Mang giày dễ đi bộ, áo chống nắng, nước uống và thuốc cá nhân. "
                        "Không nên ăn quá no trước quãng đường khoảng 2 giờ."
                    ),
                },
                {
                    "location_id": LOCATIONS["co_do_hoa_lu"]["id"],
                    "lat": LOCATIONS["co_do_hoa_lu"]["lat"],
                    "lng": LOCATIONS["co_do_hoa_lu"]["lng"],
                    "start_time": "06:00",
                    "end_time": "08:15",
                    "title": "Xe du lịch Hà Nội – Cố đô Hoa Lư",
                    "type": "transport",
                    "address": LOCATIONS["co_do_hoa_lu"]["address"],
                    "actual_cost": 220_000,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Khởi hành 06:00 để tránh đông",
                    "next_traveler_note": (
                        "Chi phí là phần xe một chiều ước tính. Tuyến thường đi cao tốc "
                        "Pháp Vân – Cầu Giẽ – Cao Bồ."
                    ),
                },
                {
                    "location_id": LOCATIONS["den_vua_dinh"]["id"],
                    "lat": LOCATIONS["den_vua_dinh"]["lat"],
                    "lng": LOCATIONS["den_vua_dinh"]["lng"],
                    "start_time": "08:30",
                    "end_time": "09:25",
                    "title": "Tham quan Đền Vua Đinh Tiên Hoàng",
                    "type": "attraction",
                    "address": LOCATIONS["den_vua_dinh"]["address"],
                    "actual_cost": 10_000,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Buổi sáng mát",
                    "next_traveler_note": (
                        "Ăn mặc lịch sự, giữ trật tự trong khu thờ tự và dành thời gian xem "
                        "kiến trúc sân rồng, nghi môn, tiền đường."
                    ),
                },
                {
                    "location_id": LOCATIONS["den_vua_le"]["id"],
                    "lat": LOCATIONS["den_vua_le"]["lat"],
                    "lng": LOCATIONS["den_vua_le"]["lng"],
                    "start_time": "09:30",
                    "end_time": "10:15",
                    "title": "Tham quan Đền Vua Lê Đại Hành",
                    "type": "attraction",
                    "address": LOCATIONS["den_vua_le"]["address"],
                    "actual_cost": 10_000,
                    "rating": 4.7,
                    "author_verdict": "recommended",
                    "best_time": "Ngay sau Đền Vua Đinh",
                    "next_traveler_note": (
                        "Hai đền ở gần nhau nên nên đi bộ liên tục, tránh quay lại bãi xe giữa chừng."
                    ),
                },
                {
                    "location_id": LOCATIONS["co_do_hoa_lu"]["id"],
                    "lat": LOCATIONS["co_do_hoa_lu"]["lat"],
                    "lng": LOCATIONS["co_do_hoa_lu"]["lng"],
                    "start_time": "10:30",
                    "end_time": "11:40",
                    "title": "Ăn trưa đặc sản dê núi và cơm cháy",
                    "type": "meal",
                    "address": LOCATIONS["co_do_hoa_lu"]["address"],
                    "actual_cost": 180_000,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Ăn sớm trước khi đi thuyền",
                    "next_traveler_note": (
                        "Gợi ý dê tái chanh hoặc dê xào lăn, cơm cháy sốt dê, rau và canh. "
                        "Hỏi giá trước khi gọi món theo đĩa lớn."
                    ),
                },
                {
                    "location_id": LOCATIONS["ben_thuyen_trang_an"]["id"],
                    "lat": LOCATIONS["ben_thuyen_trang_an"]["lat"],
                    "lng": LOCATIONS["ben_thuyen_trang_an"]["lng"],
                    "start_time": "12:00",
                    "end_time": "15:15",
                    "title": "Đi thuyền khám phá Khu du lịch sinh thái Tràng An",
                    "type": "attraction",
                    "address": LOCATIONS["ben_thuyen_trang_an"]["address"],
                    "actual_cost": 250_000,
                    "rating": 5.0,
                    "author_verdict": "must_go",
                    "best_time": "Khung giờ trưa có thể bớt đông nhưng cần chống nắng",
                    "next_traveler_note": (
                        "Luôn mặc áo phao, mang mũ và nước. Tuyến thuyền thực tế có thể thay đổi "
                        "theo điều phối, mực nước và điều kiện thời tiết."
                    ),
                },
                {
                    "location_id": LOCATIONS["trung_tam_tam_coc"]["id"],
                    "lat": LOCATIONS["trung_tam_tam_coc"]["lat"],
                    "lng": LOCATIONS["trung_tam_tam_coc"]["lng"],
                    "start_time": "15:15",
                    "end_time": "16:00",
                    "title": "Di chuyển Tràng An – khu trung tâm Tam Cốc",
                    "type": "transport",
                    "address": LOCATIONS["trung_tam_tam_coc"]["address"],
                    "actual_cost": 50_000,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Đi ngay sau khi kết thúc tuyến thuyền",
                    "next_traveler_note": (
                        "Chi phí ước tính khi ghép taxi/xe điện hoặc chia xe theo nhóm nhỏ."
                    ),
                },
                {
                    "location_id": LOCATIONS["trung_tam_tam_coc"]["id"],
                    "lat": LOCATIONS["trung_tam_tam_coc"]["lat"],
                    "lng": LOCATIONS["trung_tam_tam_coc"]["lng"],
                    "start_time": "16:00",
                    "end_time": "16:45",
                    "title": "Nhận phòng homestay hoặc khách sạn tại Tam Cốc",
                    "type": "attraction",
                    "address": LOCATIONS["trung_tam_tam_coc"]["address"],
                    "actual_cost": 700_000,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Chọn nơi ở gần bến thuyền và phố chính",
                    "next_traveler_note": (
                        "Chi phí tính theo đầu người cho 2 đêm, giả định 2 người ở chung phòng. "
                        "Ưu tiên nơi có chỗ để xe, ăn sáng hoặc hỗ trợ thuê xe đạp."
                    ),
                },
                {
                    "location_id": LOCATIONS["trung_tam_tam_coc"]["id"],
                    "lat": LOCATIONS["trung_tam_tam_coc"]["lat"],
                    "lng": LOCATIONS["trung_tam_tam_coc"]["lng"],
                    "start_time": "17:00",
                    "end_time": "18:15",
                    "title": "Thuê xe đạp dạo làng quê Tam Cốc",
                    "type": "attraction",
                    "address": LOCATIONS["trung_tam_tam_coc"]["address"],
                    "actual_cost": 70_000,
                    "rating": 4.9,
                    "author_verdict": "must_go",
                    "best_time": "Chiều mát trước hoàng hôn",
                    "next_traveler_note": (
                        "Chỉ đi đường làng dễ quan sát, bật đèn khi trời tối và không đạp xe sát mép ruộng."
                    ),
                },
                {
                    "location_id": LOCATIONS["khu_am_thuc_tam_coc"]["id"],
                    "lat": LOCATIONS["khu_am_thuc_tam_coc"]["lat"],
                    "lng": LOCATIONS["khu_am_thuc_tam_coc"]["lng"],
                    "start_time": "19:00",
                    "end_time": "20:30",
                    "title": "Ăn tối tại khu ẩm thực Tam Cốc",
                    "type": "meal",
                    "address": LOCATIONS["khu_am_thuc_tam_coc"]["address"],
                    "actual_cost": 220_000,
                    "rating": 4.8,
                    "author_verdict": "recommended",
                    "best_time": "19:00 – 20:30",
                    "next_traveler_note": (
                        "Có thể chọn cơm dê, miến lươn, gà đồi hoặc cơm gia đình để cân bằng sau bữa trưa nhiều thịt dê."
                    ),
                },
                {
                    "location_id": LOCATIONS["cho_dem_tam_coc"]["id"],
                    "lat": LOCATIONS["cho_dem_tam_coc"]["lat"],
                    "lng": LOCATIONS["cho_dem_tam_coc"]["lng"],
                    "start_time": "20:30",
                    "end_time": "21:30",
                    "title": "Dạo chợ đêm Tam Cốc và uống cà phê",
                    "type": "attraction",
                    "address": LOCATIONS["cho_dem_tam_coc"]["address"],
                    "actual_cost": 70_000,
                    "rating": 4.7,
                    "author_verdict": "recommended",
                    "best_time": "Buổi tối",
                    "next_traveler_note": (
                        "Đi bộ từ khu lưu trú, giữ đồ cá nhân và ngủ sớm để sáng hôm sau xuống thuyền trước giờ cao điểm."
                    ),
                },
            ],
        },
        {
            "day_number": 2,
            "title": "Tam Cốc – Bích Động – Hang Múa – Thung Nham",
            "activities": [
                {
                    "location_id": LOCATIONS["khu_am_thuc_tam_coc"]["id"],
                    "lat": LOCATIONS["khu_am_thuc_tam_coc"]["lat"],
                    "lng": LOCATIONS["khu_am_thuc_tam_coc"]["lng"],
                    "start_time": "06:30",
                    "end_time": "07:15",
                    "title": "Ăn sáng miến lươn hoặc phở tại Tam Cốc",
                    "type": "meal",
                    "address": LOCATIONS["khu_am_thuc_tam_coc"]["address"],
                    "actual_cost": 50_000,
                    "rating": 4.8,
                    "author_verdict": "recommended",
                    "best_time": "Ăn trước 07:00",
                    "next_traveler_note": "Ăn vừa đủ và mang theo nước vì tuyến thuyền kéo dài khoảng 1,5–2 giờ.",
                },
                {
                    "location_id": LOCATIONS["ben_thuyen_tam_coc"]["id"],
                    "lat": LOCATIONS["ben_thuyen_tam_coc"]["lat"],
                    "lng": LOCATIONS["ben_thuyen_tam_coc"]["lng"],
                    "start_time": "07:30",
                    "end_time": "09:30",
                    "title": "Đi thuyền Tam Cốc trên sông Ngô Đồng",
                    "type": "attraction",
                    "address": LOCATIONS["ben_thuyen_tam_coc"]["address"],
                    "actual_cost": 250_000,
                    "rating": 5.0,
                    "author_verdict": "must_go",
                    "best_time": "07:30 để trời mát và ít đoàn lớn",
                    "next_traveler_note": (
                        "Giữ vé, mặc áo phao và chuẩn bị tiền nhỏ hợp lý. Không mua hàng khi chưa hỏi rõ giá."
                    ),
                },
                {
                    "location_id": LOCATIONS["chua_bich_dong"]["id"],
                    "lat": LOCATIONS["chua_bich_dong"]["lat"],
                    "lng": LOCATIONS["chua_bich_dong"]["lng"],
                    "start_time": "09:45",
                    "end_time": "11:00",
                    "title": "Tham quan Chùa Bích Động",
                    "type": "attraction",
                    "address": LOCATIONS["chua_bich_dong"]["address"],
                    "actual_cost": 20_000,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Buổi sáng sau khi đi thuyền",
                    "next_traveler_note": (
                        "Khoản chi phí là gửi xe/đóng góp dự kiến. Đi giày bám tốt và ăn mặc phù hợp nơi thờ tự."
                    ),
                },
                {
                    "location_id": LOCATIONS["khu_am_thuc_tam_coc"]["id"],
                    "lat": LOCATIONS["khu_am_thuc_tam_coc"]["lat"],
                    "lng": LOCATIONS["khu_am_thuc_tam_coc"]["lng"],
                    "start_time": "11:15",
                    "end_time": "12:15",
                    "title": "Ăn trưa và nghỉ ngắn tại Tam Cốc",
                    "type": "meal",
                    "address": LOCATIONS["khu_am_thuc_tam_coc"]["address"],
                    "actual_cost": 180_000,
                    "rating": 4.7,
                    "author_verdict": "recommended",
                    "best_time": "Ăn sớm để dành thời gian leo Hang Múa",
                    "next_traveler_note": "Ưu tiên món nhẹ, bổ sung nước và điện giải trước khi leo bậc đá.",
                },
                {
                    "location_id": LOCATIONS["hang_mua"]["id"],
                    "lat": LOCATIONS["hang_mua"]["lat"],
                    "lng": LOCATIONS["hang_mua"]["lng"],
                    "start_time": "12:15",
                    "end_time": "13:00",
                    "title": "Di chuyển Tam Cốc – Hang Múa",
                    "type": "transport",
                    "address": LOCATIONS["hang_mua"]["address"],
                    "actual_cost": 40_000,
                    "rating": 4.7,
                    "author_verdict": "must_go",
                    "best_time": "Đi taxi ghép hoặc xe máy",
                    "next_traveler_note": "Nếu tự đi xe máy, khóa xe và để đúng bãi chính thức.",
                },
                {
                    "location_id": LOCATIONS["hang_mua"]["id"],
                    "lat": LOCATIONS["hang_mua"]["lat"],
                    "lng": LOCATIONS["hang_mua"]["lng"],
                    "start_time": "13:00",
                    "end_time": "15:15",
                    "title": "Leo Hang Múa và ngắm toàn cảnh Tam Cốc",
                    "type": "attraction",
                    "address": LOCATIONS["hang_mua"]["address"],
                    "actual_cost": 100_000,
                    "rating": 5.0,
                    "author_verdict": "must_go",
                    "best_time": "Tránh ngày mưa; nghỉ nhiều chặng nếu trời nóng",
                    "next_traveler_note": (
                        "Bậc đá dốc và có thể trơn. Không trèo ra ngoài lan can hoặc chen tại sống lưng rồng."
                    ),
                },
                {
                    "location_id": LOCATIONS["thung_nham"]["id"],
                    "lat": LOCATIONS["thung_nham"]["lat"],
                    "lng": LOCATIONS["thung_nham"]["lng"],
                    "start_time": "15:15",
                    "end_time": "15:45",
                    "title": "Di chuyển Hang Múa – Thung Nham",
                    "type": "transport",
                    "address": LOCATIONS["thung_nham"]["address"],
                    "actual_cost": 50_000,
                    "rating": 4.7,
                    "author_verdict": "must_go",
                    "best_time": "Có mặt trước cuối buổi chiều",
                    "next_traveler_note": "Kiểm tra giờ đóng cửa theo mùa để không bỏ lỡ khu vườn chim.",
                },
                {
                    "location_id": LOCATIONS["thung_nham"]["id"],
                    "lat": LOCATIONS["thung_nham"]["lat"],
                    "lng": LOCATIONS["thung_nham"]["lng"],
                    "start_time": "15:45",
                    "end_time": "18:15",
                    "title": "Khám phá Thung Nham và ngắm đàn chim về tổ",
                    "type": "attraction",
                    "address": LOCATIONS["thung_nham"]["address"],
                    "actual_cost": 150_000,
                    "rating": 4.9,
                    "author_verdict": "must_go",
                    "best_time": "Cuối chiều gần hoàng hôn",
                    "next_traveler_note": (
                        "Tọa độ là khu phòng vé. Điểm xem chim nằm sâu bên trong; giữ yên lặng, không dùng loa và không cho động vật ăn."
                    ),
                },
                {
                    "location_id": LOCATIONS["trung_tam_tam_coc"]["id"],
                    "lat": LOCATIONS["trung_tam_tam_coc"]["lat"],
                    "lng": LOCATIONS["trung_tam_tam_coc"]["lng"],
                    "start_time": "18:15",
                    "end_time": "19:00",
                    "title": "Trở về khu lưu trú Tam Cốc",
                    "type": "transport",
                    "address": LOCATIONS["trung_tam_tam_coc"]["address"],
                    "actual_cost": 50_000,
                    "rating": 4.7,
                    "author_verdict": "must_go",
                    "best_time": "Rời khu sinh thái trước khi quá tối",
                    "next_traveler_note": "Đường tối ở một số đoạn; không nên tự đạp xe về nếu chưa quen đường.",
                },
                {
                    "location_id": LOCATIONS["khu_am_thuc_tam_coc"]["id"],
                    "lat": LOCATIONS["khu_am_thuc_tam_coc"]["lat"],
                    "lng": LOCATIONS["khu_am_thuc_tam_coc"]["lng"],
                    "start_time": "19:15",
                    "end_time": "20:30",
                    "title": "Ăn tối lẩu gà hoặc cơm gia đình",
                    "type": "meal",
                    "address": LOCATIONS["khu_am_thuc_tam_coc"]["address"],
                    "actual_cost": 220_000,
                    "rating": 4.8,
                    "author_verdict": "recommended",
                    "best_time": "Sau khi về phòng thay đồ",
                    "next_traveler_note": "Chọn món nóng và bổ sung nước sau ngày vận động nhiều.",
                },
                {
                    "location_id": LOCATIONS["cho_dem_tam_coc"]["id"],
                    "lat": LOCATIONS["cho_dem_tam_coc"]["lat"],
                    "lng": LOCATIONS["cho_dem_tam_coc"]["lng"],
                    "start_time": "20:45",
                    "end_time": "21:45",
                    "title": "Massage chân hoặc nghỉ tại quán cà phê",
                    "type": "attraction",
                    "address": LOCATIONS["cho_dem_tam_coc"]["address"],
                    "actual_cost": 150_000,
                    "rating": 4.7,
                    "author_verdict": "recommended",
                    "best_time": "Sau một ngày đi bộ nhiều",
                    "next_traveler_note": "Xem bảng giá trước khi sử dụng dịch vụ và giữ hóa đơn nếu có.",
                },
            ],
        },
        {
            "day_number": 3,
            "title": "Chùa Bái Đính – Động Am Tiên – Hà Nội",
            "activities": [
                {
                    "location_id": LOCATIONS["khu_am_thuc_tam_coc"]["id"],
                    "lat": LOCATIONS["khu_am_thuc_tam_coc"]["lat"],
                    "lng": LOCATIONS["khu_am_thuc_tam_coc"]["lng"],
                    "start_time": "06:30",
                    "end_time": "07:15",
                    "title": "Ăn sáng và hoàn tất trả phòng",
                    "type": "meal",
                    "address": LOCATIONS["khu_am_thuc_tam_coc"]["address"],
                    "actual_cost": 50_000,
                    "rating": 4.7,
                    "author_verdict": "recommended",
                    "best_time": "Trả phòng trước khi rời Tam Cốc",
                    "next_traveler_note": "Gửi hành lý trên xe hoặc tại quầy lễ tân theo thỏa thuận trước.",
                },
                {
                    "location_id": LOCATIONS["chua_bai_dinh"]["id"],
                    "lat": LOCATIONS["chua_bai_dinh"]["lat"],
                    "lng": LOCATIONS["chua_bai_dinh"]["lng"],
                    "start_time": "07:15",
                    "end_time": "08:00",
                    "title": "Di chuyển Tam Cốc – Chùa Bái Đính",
                    "type": "transport",
                    "address": LOCATIONS["chua_bai_dinh"]["address"],
                    "actual_cost": 80_000,
                    "rating": 4.7,
                    "author_verdict": "must_go",
                    "best_time": "Khởi hành sớm trước các đoàn lớn",
                    "next_traveler_note": "Chi phí ước tính theo người khi ghép xe hoặc chia taxi nhóm nhỏ.",
                },
                {
                    "location_id": LOCATIONS["chua_bai_dinh"]["id"],
                    "lat": LOCATIONS["chua_bai_dinh"]["lat"],
                    "lng": LOCATIONS["chua_bai_dinh"]["lng"],
                    "start_time": "08:00",
                    "end_time": "10:30",
                    "title": "Tham quan quần thể Chùa Bái Đính",
                    "type": "attraction",
                    "address": LOCATIONS["chua_bai_dinh"]["address"],
                    "actual_cost": 60_000,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Buổi sáng",
                    "next_traveler_note": (
                        "Chi phí là xe điện nội khu ước tính, chưa bao gồm dịch vụ tùy chọn. "
                        "Khuôn viên rộng nên mang nước và ăn mặc lịch sự."
                    ),
                },
                {
                    "location_id": LOCATIONS["dong_am_tien"]["id"],
                    "lat": LOCATIONS["dong_am_tien"]["lat"],
                    "lng": LOCATIONS["dong_am_tien"]["lng"],
                    "start_time": "10:30",
                    "end_time": "11:00",
                    "title": "Di chuyển Bái Đính – Động Am Tiên",
                    "type": "transport",
                    "address": LOCATIONS["dong_am_tien"]["address"],
                    "actual_cost": 40_000,
                    "rating": 4.7,
                    "author_verdict": "must_go",
                    "best_time": "Cuối buổi sáng",
                    "next_traveler_note": "Động Am Tiên gần khu Cố đô Hoa Lư, thuận đường quay về Hà Nội.",
                },
                {
                    "location_id": LOCATIONS["dong_am_tien"]["id"],
                    "lat": LOCATIONS["dong_am_tien"]["lat"],
                    "lng": LOCATIONS["dong_am_tien"]["lng"],
                    "start_time": "11:00",
                    "end_time": "12:30",
                    "title": "Tham quan Động Am Tiên - Tuyệt Tịnh Cốc",
                    "type": "attraction",
                    "address": LOCATIONS["dong_am_tien"]["address"],
                    "actual_cost": 50_000,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Trời khô, ánh sáng cuối buổi sáng",
                    "next_traveler_note": (
                        "Tọa độ là điểm thờ tự/động trên bản đồ công khai. Đi theo lối chính thức và không trèo ra sát mép hồ."
                    ),
                },
                {
                    "location_id": LOCATIONS["co_do_hoa_lu"]["id"],
                    "lat": LOCATIONS["co_do_hoa_lu"]["lat"],
                    "lng": LOCATIONS["co_do_hoa_lu"]["lng"],
                    "start_time": "12:45",
                    "end_time": "13:45",
                    "title": "Ăn trưa trước khi về Hà Nội",
                    "type": "meal",
                    "address": LOCATIONS["co_do_hoa_lu"]["address"],
                    "actual_cost": 180_000,
                    "rating": 4.7,
                    "author_verdict": "recommended",
                    "best_time": "Ăn gọn trong khoảng một giờ",
                    "next_traveler_note": "Ưu tiên món dễ tiêu và kiểm tra lại hành lý trước khi lên xe.",
                },
                {
                    "location_id": LOCATIONS["ha_noi_opera_house"]["id"],
                    "lat": LOCATIONS["ha_noi_opera_house"]["lat"],
                    "lng": LOCATIONS["ha_noi_opera_house"]["lng"],
                    "start_time": "14:00",
                    "end_time": "16:15",
                    "title": "Xe Ninh Bình – Hà Nội, kết thúc hành trình",
                    "type": "transport",
                    "address": LOCATIONS["ha_noi_opera_house"]["address"],
                    "actual_cost": 220_000,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Rời Ninh Bình trước cao điểm chiều",
                    "next_traveler_note": (
                        "Thời gian về phụ thuộc giao thông. Không nên đặt lịch quan trọng sát giờ dự kiến kết thúc."
                    ),
                },
            ],
        },
    ],
    "review": {
        "best_places": [
            "Khu du lịch sinh thái Tràng An",
            "Hang Múa - đỉnh Ngọa Long",
            "Tam Cốc",
            "Khu du lịch sinh thái Thung Nham",
            "Cố đô Hoa Lư",
        ],
        "best_foods": [
            "Dê núi Ninh Bình",
            "Cơm cháy sốt dê",
            "Miến lươn",
            "Gà đồi",
            "Ốc núi theo mùa",
        ],
        "tips": (
            "Đặt phòng Tam Cốc trước cuối tuần; đi Tràng An hoặc Tam Cốc sớm để tránh đông; "
            "mang giày bám tốt khi leo Hang Múa; theo dõi giờ đóng cửa Thung Nham theo mùa; "
            "không xả rác trên sông và tại khu di sản."
        ),
    },
    "data_sources": {
        "itinerary_basis": [
            "https://visitninhbinh.com.vn/en/detailed-itinerary-for-a-3-day-2-night-ninh-binh-trip-6003",
            "https://tamcocorchid.com/en/news/detailed-guide-to-a-3-day-2-night-ninh-binh-tour-the-perfect-itinerary",
            "https://ninhbinh.info/ninh-binh-itineraries",
        ],
        "coordinate_basis": [
            "OpenStreetMap/Mapcarta POI nodes and ways",
            "Wikidata and GeoNames coordinates",
            "Google Maps Plus Codes for public entrances and wharves",
        ],
        "verification_date": VERIFIED_AT,
    },
}


def validate_seed_data() -> int:
    """Validate IDs, coordinates, activities, chronology fields and costs."""
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

    expected_day_numbers = list(range(1, NINH_BINH_SNAPSHOT["duration_days"] + 1))
    actual_day_numbers = [day["day_number"] for day in NINH_BINH_SNAPSHOT["days"]]
    if actual_day_numbers != expected_day_numbers:
        raise ValueError(
            f"Day numbers must be sequential: expected={expected_day_numbers}, "
            f"actual={actual_day_numbers}"
        )

    total_cost = 0
    for day in NINH_BINH_SNAPSHOT["days"]:
        for activity in day["activities"]:
            datetime.strptime(activity["start_time"], "%H:%M")
            datetime.strptime(activity["end_time"], "%H:%M")

            location_id = activity.get("location_id")
            if not location_id or location_id not in location_by_id:
                raise ValueError(f"Unknown location_id in activity: {activity['title']}")

            location = location_by_id[location_id]
            if float(activity["lat"]) != float(location["lat"]):
                raise ValueError(f"Latitude mismatch: {activity['title']}")
            if float(activity["lng"]) != float(location["lng"]):
                raise ValueError(f"Longitude mismatch: {activity['title']}")

            cost = activity.get("actual_cost", 0)
            if not isinstance(cost, int) or cost < 0:
                raise ValueError(f"Invalid actual_cost: {activity['title']}")
            total_cost += cost

    expected_per_person = NINH_BINH_SNAPSHOT["actual_cost_per_person"]
    if total_cost != expected_per_person:
        raise ValueError(
            f"Cost mismatch: activities={total_cost:,}, snapshot={expected_per_person:,}"
        )

    expected_total = expected_per_person * NUMBER_OF_TRAVELERS
    if NINH_BINH_SNAPSHOT["actual_total_cost"] != expected_total:
        raise ValueError(
            "actual_total_cost must equal actual_cost_per_person * traveler_count"
        )

    budget_total = sum(
        value
        for key, value in NINH_BINH_SNAPSHOT["budget_breakdown_per_person"].items()
        if key != "total"
    )
    if budget_total != NINH_BINH_SNAPSHOT["budget_breakdown_per_person"]["total"]:
        raise ValueError("Budget breakdown does not add up")

    if budget_total != expected_per_person:
        raise ValueError("Budget breakdown total differs from actual_cost_per_person")

    return total_cost


async def seed_ninh_binh() -> None:
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
                new_loc = Location(
                    id=loc_id,
                    name=loc_data["name"],
                    address=loc_data["address"],
                    lat=loc_data["lat"],
                    lng=loc_data["lng"],
                    category=loc_data["category"],
                    province_name=loc_data["province_name"],
                )
                session.add(new_loc)
            else:
                existing_loc.name = loc_data["name"]
                existing_loc.address = loc_data["address"]
                existing_loc.lat = loc_data["lat"]
                existing_loc.lng = loc_data["lng"]
                existing_loc.category = loc_data["category"]
                existing_loc.province_name = loc_data["province_name"]

        await session.commit()

        # 2. Find the seed author or create one.
        author_email = "guide.ninhbinh@smarttravel.vn"
        stmt_user = select(User).where(User.email == author_email)
        res_user = await session.execute(stmt_user)
        user = res_user.scalar_one_or_none()

        if not user:
            print(f"No user '{author_email}' found. Creating seed author...")
            user = User(
                id=uuid.uuid4(),
                username="guide-ninhbinh",
                email=author_email,
                full_name="Lê Thu Trang (Hướng dẫn viên Ninh Bình)",
                password_hash="seed-only-account-not-for-login",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

        # 3. Create or update the public trip publication.
        slug = "lich-trinh-ninh-binh-3-ngay-2-dem-chi-tiet"
        stmt_pub = select(PublicTripPublication).where(
            PublicTripPublication.slug == slug
        )
        res_pub = await session.execute(stmt_pub)
        existing = res_pub.scalar_one_or_none()

        publication_values = {
            "title": NINH_BINH_SNAPSHOT["title"],
            "summary": (
                "Hành trình Ninh Bình 3 ngày 2 đêm từ Hà Nội cho 2 người: tham quan "
                "Cố đô Hoa Lư, đi thuyền Tràng An và Tam Cốc, leo Hang Múa, ghé Chùa "
                "Bích Động, ngắm chim tại Thung Nham, tham quan Bái Đính và Động Am Tiên "
                "với ngân sách khoảng 3,77 triệu đồng/người."
            ),
            "destination": "Ninh Bình",
            "province_name": "Ninh Bình",
            "duration_days": 3,
            "actual_total_cost": NINH_BINH_SNAPSHOT["actual_total_cost"],
            "actual_cost_per_person": NINH_BINH_SNAPSHOT["actual_cost_per_person"],
            "overall_rating": NINH_BINH_SNAPSHOT["overall_rating"],
            "status": "published",
            "visibility": "public",
            "moderation_status": "approved",
            "cover_image_url": (
                "https://commons.wikimedia.org/wiki/Special:FilePath/"
                "Trang%20An%20Landscape%20Complex%2C%20Ninh%20Binh%20Province%2C%20"
                "Vietnam%2C%2020240202%201433%205283.jpg"
            ),
            "snapshot_json": NINH_BINH_SNAPSHOT,
            "tags": [
                "Ninh Bình",
                "3 ngày 2 đêm",
                "Tràng An",
                "Tam Cốc",
                "Hang Múa",
                "Cố đô Hoa Lư",
                "Thung Nham",
                "Chùa Bái Đính",
                "Động Am Tiên",
                "Đạp xe",
            ],
            "save_count": 0,
            "view_count": 2160,
            "published_at": datetime.now(timezone.utc),
        }

        if existing:
            print(f"Publication '{slug}' already exists. Updating content...")
            for field, value in publication_values.items():
                setattr(existing, field, value)
        else:
            print(f"Creating new Public Trip Publication '{slug}'...")
            publication = PublicTripPublication(
                id=uuid.uuid4(),
                author_user_id=user.id,
                slug=slug,
                **publication_values,
            )
            session.add(publication)

        await session.commit()
        print("Successfully seeded Ninh Bình 3D2N itinerary!")


if __name__ == "__main__":
    asyncio.run(seed_ninh_binh())
