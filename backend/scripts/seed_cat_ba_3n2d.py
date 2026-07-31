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
# CAT BA - LAN HA BAY 3D2N SEED DATA
#
# Coordinate policy:
# - Exact terminals/POIs use public map pins or published coordinates.
# - Bays, beaches and central areas use a representative point/area center.
# - Every location includes a Google Maps URL for manual verification.
# - Coordinates were last reviewed on 2026-07-30.
#
# Cost policy:
# - actual_cost is the estimated cost PER PERSON for this sample itinerary.
# - Prices and ferry/boat schedules can change; verify again before travelling.
# -----------------------------------------------------------------------------

VERIFIED_AT = "2026-07-30"
NUMBER_OF_TRAVELERS = 2

LOCATIONS: dict[str, dict[str, Any]] = {
    "ha_noi_opera_house": {
        "id": "22222222-2222-4222-8222-222222222201",
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
    "dong_bai_ferry": {
        "id": "22222222-2222-4222-8222-222222222202",
        "name": "Bến phà Đồng Bài",
        "address": "RV6V+PPH, Đồng Bài, Cát Hải, Hải Phòng",
        "lat": 20.811850,
        "lng": 106.894199,
        "category": "transport",
        "province_name": "Hải Phòng",
        "plus_code": "7PG8RV6V+PPH",
        "coordinate_precision": "plus_code_center",
        "coordinate_source": "Google Maps Plus Code RV6V+PPH",
        "google_maps_url": "https://www.google.com/maps?q=20.811850,106.894199",
        "verified_at": VERIFIED_AT,
    },
    "cai_vieng_ferry": {
        "id": "22222222-2222-4222-8222-222222222203",
        "name": "Bến phà Cái Viềng",
        "address": "Phù Long, Cát Hải, Hải Phòng",
        "lat": 20.818260,
        "lng": 106.913430,
        "category": "transport",
        "province_name": "Hải Phòng",
        "plus_code": "7PG8RW97+89",
        "coordinate_precision": "poi_pin",
        "coordinate_source": "OpenStreetMap/Mapcarta ferry terminal node 267557985",
        "google_maps_url": "https://www.google.com/maps?q=20.818260,106.913430",
        "verified_at": VERIFIED_AT,
    },
    "trung_tam_cat_ba": {
        "id": "22222222-2222-4222-8222-222222222204",
        "name": "Khu lưu trú trung tâm Cát Bà",
        "address": "Khu trung tâm đường 1/4, thị trấn Cát Bà, Hải Phòng",
        "lat": 20.724310,
        "lng": 107.049500,
        "category": "hotel",
        "province_name": "Hải Phòng",
        "plus_code": "7PG9P2FX+PQ",
        "coordinate_precision": "area_center",
        "coordinate_source": "Quảng trường Cát Bà area center - OpenStreetMap/Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=20.724310,107.049500",
        "verified_at": VERIFIED_AT,
    },
    "khu_am_thuc_cat_ba": {
        "id": "22222222-2222-4222-8222-222222222205",
        "name": "Khu ẩm thực trung tâm Cát Bà",
        "address": "Đường 1/4 - Núi Ngọc, trung tâm Cát Bà, Hải Phòng",
        "lat": 20.725680,
        "lng": 107.047620,
        "category": "restaurant",
        "province_name": "Hải Phòng",
        "coordinate_precision": "restaurant_area_center",
        "coordinate_source": "Central restaurant area near Đường 1/4 and Núi Ngọc",
        "google_maps_url": "https://www.google.com/maps?q=20.725680,107.047620",
        "verified_at": VERIFIED_AT,
    },
    "quang_truong_cat_ba": {
        "id": "22222222-2222-4222-8222-222222222206",
        "name": "Quảng trường Cát Bà",
        "address": "Đường 1/4, thị trấn Cát Bà, Hải Phòng",
        "lat": 20.724310,
        "lng": 107.049500,
        "category": "attraction",
        "province_name": "Hải Phòng",
        "plus_code": "7PG9P2FX+PQ",
        "coordinate_precision": "poi_area",
        "coordinate_source": "OpenStreetMap/Mapcarta way 1182833332",
        "google_maps_url": "https://www.google.com/maps?q=20.724310,107.049500",
        "verified_at": VERIFIED_AT,
    },
    "cat_co_1": {
        "id": "22222222-2222-4222-8222-222222222207",
        "name": "Bãi tắm Cát Cò 1",
        "address": "Bãi Cát Cò 1, thị trấn Cát Bà, Hải Phòng",
        "lat": 20.717777,
        "lng": 107.052744,
        "category": "attraction",
        "province_name": "Hải Phòng",
        "coordinate_precision": "beach_center",
        "coordinate_source": "Published beach coordinates cross-checked with map imagery",
        "google_maps_url": "https://www.google.com/maps?q=20.717777,107.052744",
        "verified_at": VERIFIED_AT,
    },
    "cat_co_2": {
        "id": "22222222-2222-4222-8222-222222222208",
        "name": "Bãi tắm Cát Cò 2",
        "address": "Bãi Cát Cò 2, thị trấn Cát Bà, Hải Phòng",
        "lat": 20.719136,
        "lng": 107.054702,
        "category": "attraction",
        "province_name": "Hải Phòng",
        "coordinate_precision": "beach_center",
        "coordinate_source": "Published beach coordinates cross-checked with map imagery",
        "google_maps_url": "https://www.google.com/maps?q=20.719136,107.054702",
        "verified_at": VERIFIED_AT,
    },
    "ben_beo": {
        "id": "22222222-2222-4222-8222-222222222209",
        "name": "Bến Bèo",
        "address": "Bến Bèo, Cát Bà, Cát Hải, Hải Phòng",
        "lat": 20.732130,
        "lng": 107.058910,
        "category": "transport",
        "province_name": "Hải Phòng",
        "coordinate_precision": "ferry_terminal_pin",
        "coordinate_source": "OpenStreetMap/Mapcarta passenger terminal",
        "google_maps_url": "https://www.google.com/maps?q=20.732130,107.058910",
        "verified_at": VERIFIED_AT,
    },
    "lang_chai_cai_beo": {
        "id": "22222222-2222-4222-8222-222222222210",
        "name": "Làng chài Cái Bèo",
        "address": "Vịnh Cái Bèo, Cát Bà, Cát Hải, Hải Phòng",
        "lat": 20.734412,
        "lng": 107.062457,
        "category": "attraction",
        "province_name": "Hải Phòng",
        "coordinate_precision": "floating_village_route_point",
        "coordinate_source": "Geotagged public image point within Cái Bèo floating village",
        "google_maps_url": "https://www.google.com/maps?q=20.734412,107.062457",
        "verified_at": VERIFIED_AT,
    },
    "vinh_lan_ha": {
        "id": "22222222-2222-4222-8222-222222222211",
        "name": "Vịnh Lan Hạ",
        "address": "Vịnh Lan Hạ, quần đảo Cát Bà, Hải Phòng",
        "lat": 20.751572,
        "lng": 107.104278,
        "category": "attraction",
        "province_name": "Hải Phòng",
        "coordinate_precision": "bay_representative_center",
        "coordinate_source": "Public geographic coordinate for Lan Hạ Bay",
        "google_maps_url": "https://www.google.com/maps?q=20.751572,107.104278",
        "verified_at": VERIFIED_AT,
    },
    "van_boi": {
        "id": "22222222-2222-4222-8222-222222222212",
        "name": "Khu vực Vạn Bội",
        "address": "Vạn Bội, Vịnh Lan Hạ, Cát Hải, Hải Phòng",
        "lat": 20.760240,
        "lng": 107.078490,
        "category": "attraction",
        "province_name": "Hải Phòng",
        "plus_code": "7PG9Q36H+39",
        "coordinate_precision": "tourist_area_point",
        "coordinate_source": "OpenStreetMap/Mapcarta tourist attraction node 4587394292",
        "google_maps_url": "https://www.google.com/maps?q=20.760240,107.078490",
        "verified_at": VERIFIED_AT,
    },
    "vuon_quoc_gia_cat_ba": {
        "id": "22222222-2222-4222-8222-222222222213",
        "name": "Cổng Vườn quốc gia Cát Bà",
        "address": "Đường xuyên đảo Cát Bà, Trân Châu, Cát Hải, Hải Phòng",
        "lat": 20.793550,
        "lng": 106.990879,
        "category": "attraction",
        "province_name": "Hải Phòng",
        "plus_code": "7PG8QXVR+F3G",
        "coordinate_precision": "plus_code_center",
        "coordinate_source": "Google Maps Plus Code QXVR+F3G",
        "google_maps_url": "https://www.google.com/maps?q=20.793550,106.990879",
        "verified_at": VERIFIED_AT,
    },
    "dinh_ngu_lam": {
        "id": "22222222-2222-4222-8222-222222222214",
        "name": "Đỉnh Ngự Lâm",
        "address": "Vườn quốc gia Cát Bà, Cát Hải, Hải Phòng",
        "lat": 20.794364,
        "lng": 106.999344,
        "category": "attraction",
        "province_name": "Hải Phòng",
        "coordinate_precision": "summit_viewpoint_geotag",
        "coordinate_source": "Geotagged panorama from Ngự Lâm Peak",
        "google_maps_url": "https://www.google.com/maps?q=20.794364,106.999344",
        "verified_at": VERIFIED_AT,
    },
    "dong_trung_trang": {
        "id": "22222222-2222-4222-8222-222222222215",
        "name": "Động Trung Trang",
        "address": "Trung Trang, Trân Châu, Cát Hải, Hải Phòng",
        "lat": 20.788488,
        "lng": 106.997854,
        "category": "attraction",
        "province_name": "Hải Phòng",
        "coordinate_precision": "cave_pin",
        "coordinate_source": "Wikidata coordinate 20°47'18.55727\"N, 106°59'52.27408\"E",
        "google_maps_url": "https://www.google.com/maps?q=20.788488,106.997854",
        "verified_at": VERIFIED_AT,
    },
    "cho_cat_ba": {
        "id": "22222222-2222-4222-8222-222222222216",
        "name": "Khu chợ trung tâm Cát Bà",
        "address": "Khu chợ đường 1/4 - Tùng Dinh, thị trấn Cát Bà, Hải Phòng",
        "lat": 20.727090,
        "lng": 107.046690,
        "category": "attraction",
        "province_name": "Hải Phòng",
        "coordinate_precision": "market_area_center",
        "coordinate_source": "Central market area near 124 Đường 1/4",
        "google_maps_url": "https://www.google.com/maps?q=20.727090,107.046690",
        "verified_at": VERIFIED_AT,
    },
}


CAT_BA_SNAPSHOT: dict[str, Any] = {
    "title": "Lịch trình Cát Bà - Vịnh Lan Hạ 3 ngày 2 đêm chi tiết từ Hà Nội",
    "destination": "Cát Bà, Hải Phòng",
    "duration_days": 3,
    "traveler_count": NUMBER_OF_TRAVELERS,
    "actual_cost_per_person": 3_930_000,
    "actual_total_cost": 7_860_000,
    "overall_rating": 4.9,
    "coordinate_verified_at": VERIFIED_AT,
    "cost_note": (
        "Chi phí là mức seed tham khảo theo người, không phải báo giá cố định. "
        "Cần kiểm tra lại giá phòng, vé phà, tour vịnh và lịch vận hành trước ngày đi."
    ),
    "budget_breakdown_per_person": {
        "transport": 950_000,
        "lodging": 850_000,
        "food": 1_170_000,
        "tours_and_tickets": 810_000,
        "miscellaneous": 150_000,
        "total": 3_930_000,
    },
    "days": [
        {
            "day_number": 1,
            "title": "Hà Nội – Bến phà Đồng Bài – Trung tâm Cát Bà – Bãi Cát Cò",
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
                        "Chuẩn bị CCCD, thuốc say xe và áo khoác mỏng. Ăn sáng gọn để không ảnh hưởng giờ khởi hành."
                    ),
                },
                {
                    "location_id": LOCATIONS["dong_bai_ferry"]["id"],
                    "lat": LOCATIONS["dong_bai_ferry"]["lat"],
                    "lng": LOCATIONS["dong_bai_ferry"]["lng"],
                    "start_time": "06:00",
                    "end_time": "09:00",
                    "title": "Xe du lịch Hà Nội – Bến phà Đồng Bài",
                    "type": "transport",
                    "address": LOCATIONS["dong_bai_ferry"]["address"],
                    "actual_cost": 320_000,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Khởi hành 06:00 để tránh ùn tắc",
                    "next_traveler_note": (
                        "Đi cao tốc Hà Nội – Hải Phòng. Cuối tuần mùa hè nên khởi hành sớm và kiểm tra tình trạng bến phà."
                    ),
                },
                {
                    "location_id": LOCATIONS["cai_vieng_ferry"]["id"],
                    "lat": LOCATIONS["cai_vieng_ferry"]["lat"],
                    "lng": LOCATIONS["cai_vieng_ferry"]["lng"],
                    "start_time": "09:00",
                    "end_time": "09:25",
                    "title": "Qua phà Đồng Bài – Cái Viềng",
                    "type": "transport",
                    "address": LOCATIONS["cai_vieng_ferry"]["address"],
                    "actual_cost": 20_000,
                    "rating": 4.6,
                    "author_verdict": "must_go",
                    "best_time": "Buổi sáng trước cao điểm",
                    "next_traveler_note": (
                        "Giờ chạy và giá vé có thể thay đổi. Nên xem thông báo vận hành mới nhất trước chuyến đi."
                    ),
                },
                {
                    "location_id": LOCATIONS["trung_tam_cat_ba"]["id"],
                    "lat": LOCATIONS["trung_tam_cat_ba"]["lat"],
                    "lng": LOCATIONS["trung_tam_cat_ba"]["lng"],
                    "start_time": "09:25",
                    "end_time": "10:45",
                    "title": "Di chuyển Cái Viềng – trung tâm Cát Bà",
                    "type": "transport",
                    "address": LOCATIONS["trung_tam_cat_ba"]["address"],
                    "actual_cost": 80_000,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Ngay sau khi qua phà",
                    "next_traveler_note": (
                        "Đường xuyên đảo có nhiều đoạn cua. Người dễ say xe nên ngồi phía trước và hạn chế dùng điện thoại."
                    ),
                },
                {
                    "location_id": LOCATIONS["trung_tam_cat_ba"]["id"],
                    "lat": LOCATIONS["trung_tam_cat_ba"]["lat"],
                    "lng": LOCATIONS["trung_tam_cat_ba"]["lng"],
                    "start_time": "10:45",
                    "end_time": "11:30",
                    "title": "Gửi hành lý và nhận phòng khách sạn khu trung tâm",
                    "type": "attraction",
                    "address": LOCATIONS["trung_tam_cat_ba"]["address"],
                    "actual_cost": 850_000,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Chọn khách sạn gần đường 1/4 hoặc Núi Ngọc",
                    "next_traveler_note": (
                        "Chi phí tính theo đầu người cho 2 đêm, giả định 2 người ở chung phòng. Hỏi rõ giờ nhận phòng và phụ thu cuối tuần."
                    ),
                },
                {
                    "location_id": LOCATIONS["khu_am_thuc_cat_ba"]["id"],
                    "lat": LOCATIONS["khu_am_thuc_cat_ba"]["lat"],
                    "lng": LOCATIONS["khu_am_thuc_cat_ba"]["lng"],
                    "start_time": "11:45",
                    "end_time": "13:00",
                    "title": "Ăn trưa hải sản tại khu trung tâm Cát Bà",
                    "type": "meal",
                    "address": LOCATIONS["khu_am_thuc_cat_ba"]["address"],
                    "actual_cost": 180_000,
                    "rating": 4.8,
                    "author_verdict": "recommended",
                    "best_time": "11:45 – 13:00",
                    "next_traveler_note": (
                        "Gợi ý cơm gia đình gồm mực xào, canh ngao chua, cá biển và rau. Hỏi giá trước khi gọi hải sản theo cân."
                    ),
                },
                {
                    "location_id": LOCATIONS["cat_co_1"]["id"],
                    "lat": LOCATIONS["cat_co_1"]["lat"],
                    "lng": LOCATIONS["cat_co_1"]["lng"],
                    "start_time": "15:30",
                    "end_time": "16:45",
                    "title": "Tắm biển và chụp ảnh tại Bãi Cát Cò 1",
                    "type": "attraction",
                    "address": LOCATIONS["cat_co_1"]["address"],
                    "actual_cost": 30_000,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Chiều mát sau 15:30",
                    "next_traveler_note": (
                        "Mang dép chống trượt, túi chống nước và chỉ bơi trong khu vực được phép khi biển êm."
                    ),
                },
                {
                    "location_id": LOCATIONS["cat_co_2"]["id"],
                    "lat": LOCATIONS["cat_co_2"]["lat"],
                    "lng": LOCATIONS["cat_co_2"]["lng"],
                    "start_time": "16:45",
                    "end_time": "18:00",
                    "title": "Đi đường ven biển sang Bãi Cát Cò 2 ngắm hoàng hôn",
                    "type": "attraction",
                    "address": LOCATIONS["cat_co_2"]["address"],
                    "actual_cost": 30_000,
                    "rating": 4.9,
                    "author_verdict": "must_go",
                    "best_time": "16:45 – 18:00",
                    "next_traveler_note": (
                        "Đường ven biển đẹp nhưng có bậc và đoạn dốc. Không đi sát mép đá khi trời mưa hoặc gió lớn."
                    ),
                },
                {
                    "location_id": LOCATIONS["khu_am_thuc_cat_ba"]["id"],
                    "lat": LOCATIONS["khu_am_thuc_cat_ba"]["lat"],
                    "lng": LOCATIONS["khu_am_thuc_cat_ba"]["lng"],
                    "start_time": "19:00",
                    "end_time": "20:30",
                    "title": "Ăn tối hải sản tại trung tâm Cát Bà",
                    "type": "meal",
                    "address": LOCATIONS["khu_am_thuc_cat_ba"]["address"],
                    "actual_cost": 280_000,
                    "rating": 4.9,
                    "author_verdict": "must_go",
                    "best_time": "19:00 – 20:30",
                    "next_traveler_note": (
                        "Gợi ý bề bề, hàu nướng, mực hấp và cá biển. Tránh gọi quá nhiều món trong ngày đầu."
                    ),
                },
                {
                    "location_id": LOCATIONS["quang_truong_cat_ba"]["id"],
                    "lat": LOCATIONS["quang_truong_cat_ba"]["lat"],
                    "lng": LOCATIONS["quang_truong_cat_ba"]["lng"],
                    "start_time": "20:30",
                    "end_time": "22:00",
                    "title": "Dạo Quảng trường và đường ven biển Cát Bà",
                    "type": "attraction",
                    "address": LOCATIONS["quang_truong_cat_ba"]["address"],
                    "actual_cost": 50_000,
                    "rating": 4.7,
                    "author_verdict": "recommended",
                    "best_time": "Buổi tối",
                    "next_traveler_note": (
                        "Có thể uống nước, ăn kem hoặc đi xe điện một vòng. Nên ngủ trước 22:30 để sáng hôm sau đi vịnh sớm."
                    ),
                },
            ],
        },
        {
            "day_number": 2,
            "title": "Bến Bèo – Làng chài Cái Bèo – Vịnh Lan Hạ – Vạn Bội",
            "activities": [
                {
                    "location_id": LOCATIONS["khu_am_thuc_cat_ba"]["id"],
                    "lat": LOCATIONS["khu_am_thuc_cat_ba"]["lat"],
                    "lng": LOCATIONS["khu_am_thuc_cat_ba"]["lng"],
                    "start_time": "06:30",
                    "end_time": "07:15",
                    "title": "Ăn sáng bánh đa cua hoặc bún hải sản",
                    "type": "meal",
                    "address": LOCATIONS["khu_am_thuc_cat_ba"]["address"],
                    "actual_cost": 50_000,
                    "rating": 4.8,
                    "author_verdict": "recommended",
                    "best_time": "06:30 – 07:15",
                    "next_traveler_note": "Ăn vừa đủ, tránh đồ quá dầu trước khi đi tàu và chèo kayak.",
                },
                {
                    "location_id": LOCATIONS["ben_beo"]["id"],
                    "lat": LOCATIONS["ben_beo"]["lat"],
                    "lng": LOCATIONS["ben_beo"]["lng"],
                    "start_time": "07:15",
                    "end_time": "07:45",
                    "title": "Di chuyển từ trung tâm đến Bến Bèo và làm thủ tục",
                    "type": "transport",
                    "address": LOCATIONS["ben_beo"]["address"],
                    "actual_cost": 30_000,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Có mặt trước giờ tàu 20–30 phút",
                    "next_traveler_note": (
                        "Mang CCCD, nước uống, kem chống nắng và túi chống nước. Xác nhận rõ tour đã gồm vé, kayak và bữa trưa."
                    ),
                },
                {
                    "location_id": LOCATIONS["lang_chai_cai_beo"]["id"],
                    "lat": LOCATIONS["lang_chai_cai_beo"]["lat"],
                    "lng": LOCATIONS["lang_chai_cai_beo"]["lng"],
                    "start_time": "08:00",
                    "end_time": "09:00",
                    "title": "Đi tàu qua Làng chài Cái Bèo",
                    "type": "attraction",
                    "address": LOCATIONS["lang_chai_cai_beo"]["address"],
                    "actual_cost": 0,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Sáng sớm ánh sáng đẹp",
                    "next_traveler_note": (
                        "Tọa độ là điểm đại diện trên tuyến làng chài nổi, không phải một công trình đơn lẻ. Không xả rác xuống vịnh."
                    ),
                },
                {
                    "location_id": LOCATIONS["vinh_lan_ha"]["id"],
                    "lat": LOCATIONS["vinh_lan_ha"]["lat"],
                    "lng": LOCATIONS["vinh_lan_ha"]["lng"],
                    "start_time": "09:00",
                    "end_time": "10:30",
                    "title": "Du thuyền tham quan Vịnh Lan Hạ",
                    "type": "attraction",
                    "address": LOCATIONS["vinh_lan_ha"]["address"],
                    "actual_cost": 450_000,
                    "rating": 5.0,
                    "author_verdict": "must_go",
                    "best_time": "Buổi sáng, thời tiết quang",
                    "next_traveler_note": (
                        "Chi phí là phần tàu tham quan trong gói ngày. Tuyến thực tế có thể đổi theo sóng, gió và điều phối của ban quản lý vịnh."
                    ),
                },
                {
                    "location_id": LOCATIONS["van_boi"]["id"],
                    "lat": LOCATIONS["van_boi"]["lat"],
                    "lng": LOCATIONS["van_boi"]["lng"],
                    "start_time": "10:30",
                    "end_time": "11:45",
                    "title": "Chèo kayak tại khu vực Vạn Bội",
                    "type": "attraction",
                    "address": LOCATIONS["van_boi"]["address"],
                    "actual_cost": 100_000,
                    "rating": 5.0,
                    "author_verdict": "must_go",
                    "best_time": "Khi nước êm và có hướng dẫn viên",
                    "next_traveler_note": (
                        "Luôn mặc áo phao, đi theo cặp và không tự chèo vào hang hoặc luồng tàu khi hướng dẫn viên chưa cho phép."
                    ),
                },
                {
                    "location_id": LOCATIONS["vinh_lan_ha"]["id"],
                    "lat": LOCATIONS["vinh_lan_ha"]["lat"],
                    "lng": LOCATIONS["vinh_lan_ha"]["lng"],
                    "start_time": "12:00",
                    "end_time": "13:00",
                    "title": "Ăn trưa hải sản trên tàu",
                    "type": "meal",
                    "address": LOCATIONS["vinh_lan_ha"]["address"],
                    "actual_cost": 180_000,
                    "rating": 4.8,
                    "author_verdict": "recommended",
                    "best_time": "12:00 – 13:00",
                    "next_traveler_note": (
                        "Thông báo trước nếu ăn chay hoặc dị ứng hải sản. Không đứng dậy di chuyển khi tàu đang cập hoặc rời điểm neo."
                    ),
                },
                {
                    "location_id": LOCATIONS["van_boi"]["id"],
                    "lat": LOCATIONS["van_boi"]["lat"],
                    "lng": LOCATIONS["van_boi"]["lng"],
                    "start_time": "13:15",
                    "end_time": "15:15",
                    "title": "Tắm biển và nghỉ ngơi tại điểm dừng phù hợp trên Vịnh Lan Hạ",
                    "type": "attraction",
                    "address": LOCATIONS["van_boi"]["address"],
                    "actual_cost": 0,
                    "rating": 4.9,
                    "author_verdict": "must_go",
                    "best_time": "Theo điều kiện thủy triều và hướng dẫn tàu",
                    "next_traveler_note": (
                        "Điểm tắm có thể thay đổi, Vạn Bội chỉ là điểm đại diện. Chỉ xuống nước khi thủy thủ cho phép và luôn mặc áo phao."
                    ),
                },
                {
                    "location_id": LOCATIONS["ben_beo"]["id"],
                    "lat": LOCATIONS["ben_beo"]["lat"],
                    "lng": LOCATIONS["ben_beo"]["lng"],
                    "start_time": "15:15",
                    "end_time": "16:30",
                    "title": "Tàu trở lại Bến Bèo",
                    "type": "transport",
                    "address": LOCATIONS["ben_beo"]["address"],
                    "actual_cost": 0,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Kết thúc tour trước chiều tối",
                    "next_traveler_note": "Kiểm tra lại đồ cá nhân và thiết bị điện tử trước khi rời tàu.",
                },
                {
                    "location_id": LOCATIONS["khu_am_thuc_cat_ba"]["id"],
                    "lat": LOCATIONS["khu_am_thuc_cat_ba"]["lat"],
                    "lng": LOCATIONS["khu_am_thuc_cat_ba"]["lng"],
                    "start_time": "18:30",
                    "end_time": "20:00",
                    "title": "Ăn tối lẩu hải sản hoặc cơm gia đình",
                    "type": "meal",
                    "address": LOCATIONS["khu_am_thuc_cat_ba"]["address"],
                    "actual_cost": 250_000,
                    "rating": 4.9,
                    "author_verdict": "must_go",
                    "best_time": "18:30 – 20:00",
                    "next_traveler_note": "Sau một ngày đi vịnh nên chọn món nóng, dễ ăn và bổ sung đủ nước.",
                },
                {
                    "location_id": LOCATIONS["quang_truong_cat_ba"]["id"],
                    "lat": LOCATIONS["quang_truong_cat_ba"]["lat"],
                    "lng": LOCATIONS["quang_truong_cat_ba"]["lng"],
                    "start_time": "20:00",
                    "end_time": "21:30",
                    "title": "Tự do dạo phố và uống cà phê",
                    "type": "attraction",
                    "address": LOCATIONS["quang_truong_cat_ba"]["address"],
                    "actual_cost": 50_000,
                    "rating": 4.7,
                    "author_verdict": "recommended",
                    "best_time": "Buổi tối",
                    "next_traveler_note": "Không thức quá khuya vì ngày 3 có hoạt động đi bộ trong rừng.",
                },
            ],
        },
        {
            "day_number": 3,
            "title": "Chợ Cát Bà – Vườn quốc gia – Đỉnh Ngự Lâm – Động Trung Trang – Hà Nội",
            "activities": [
                {
                    "location_id": LOCATIONS["cho_cat_ba"]["id"],
                    "lat": LOCATIONS["cho_cat_ba"]["lat"],
                    "lng": LOCATIONS["cho_cat_ba"]["lng"],
                    "start_time": "05:45",
                    "end_time": "06:45",
                    "title": "Ăn sáng và tham quan khu chợ trung tâm Cát Bà",
                    "type": "meal",
                    "address": LOCATIONS["cho_cat_ba"]["address"],
                    "actual_cost": 70_000,
                    "rating": 4.7,
                    "author_verdict": "recommended",
                    "best_time": "05:45 – 06:45",
                    "next_traveler_note": (
                        "Mua hải sản khô cần hỏi cách đóng gói. Không nên mua đồ tươi nếu phải di chuyển nhiều giờ về Hà Nội."
                    ),
                },
                {
                    "location_id": LOCATIONS["vuon_quoc_gia_cat_ba"]["id"],
                    "lat": LOCATIONS["vuon_quoc_gia_cat_ba"]["lat"],
                    "lng": LOCATIONS["vuon_quoc_gia_cat_ba"]["lng"],
                    "start_time": "07:15",
                    "end_time": "08:00",
                    "title": "Di chuyển đến Vườn quốc gia Cát Bà và mua vé",
                    "type": "transport",
                    "address": LOCATIONS["vuon_quoc_gia_cat_ba"]["address"],
                    "actual_cost": 80_000,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Đến trước 08:00",
                    "next_traveler_note": (
                        "Mang giày bám tốt, nước uống và thuốc chống côn trùng. Không đi tuyến rừng khi có cảnh báo thời tiết xấu."
                    ),
                },
                {
                    "location_id": LOCATIONS["dinh_ngu_lam"]["id"],
                    "lat": LOCATIONS["dinh_ngu_lam"]["lat"],
                    "lng": LOCATIONS["dinh_ngu_lam"]["lng"],
                    "start_time": "08:00",
                    "end_time": "10:00",
                    "title": "Trekking tuyến ngắn lên Đỉnh Ngự Lâm",
                    "type": "attraction",
                    "address": LOCATIONS["dinh_ngu_lam"]["address"],
                    "actual_cost": 120_000,
                    "rating": 5.0,
                    "author_verdict": "must_go",
                    "best_time": "Buổi sáng mát, đường khô",
                    "next_traveler_note": (
                        "Tuyến có bậc đá và đoạn dốc. Không phù hợp với người đang chấn thương chân hoặc có vấn đề tim mạch nặng."
                    ),
                },
                {
                    "location_id": LOCATIONS["dong_trung_trang"]["id"],
                    "lat": LOCATIONS["dong_trung_trang"]["lat"],
                    "lng": LOCATIONS["dong_trung_trang"]["lng"],
                    "start_time": "10:15",
                    "end_time": "11:15",
                    "title": "Khám phá Động Trung Trang",
                    "type": "attraction",
                    "address": LOCATIONS["dong_trung_trang"]["address"],
                    "actual_cost": 80_000,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Sau khi xuống Đỉnh Ngự Lâm",
                    "next_traveler_note": (
                        "Trong hang có nền ẩm và trần thấp ở một số đoạn. Đi chậm, không chạm hoặc bẻ nhũ đá."
                    ),
                },
                {
                    "location_id": LOCATIONS["khu_am_thuc_cat_ba"]["id"],
                    "lat": LOCATIONS["khu_am_thuc_cat_ba"]["lat"],
                    "lng": LOCATIONS["khu_am_thuc_cat_ba"]["lng"],
                    "start_time": "11:45",
                    "end_time": "12:45",
                    "title": "Ăn trưa, lấy hành lý và trả phòng",
                    "type": "meal",
                    "address": LOCATIONS["khu_am_thuc_cat_ba"]["address"],
                    "actual_cost": 160_000,
                    "rating": 4.8,
                    "author_verdict": "recommended",
                    "best_time": "11:45 – 12:45",
                    "next_traveler_note": "Ăn gọn, kiểm tra lại phòng và có mặt tại điểm đón đúng giờ.",
                },
                {
                    "location_id": LOCATIONS["cai_vieng_ferry"]["id"],
                    "lat": LOCATIONS["cai_vieng_ferry"]["lat"],
                    "lng": LOCATIONS["cai_vieng_ferry"]["lng"],
                    "start_time": "13:15",
                    "end_time": "14:30",
                    "title": "Di chuyển từ trung tâm Cát Bà đến Bến phà Cái Viềng",
                    "type": "transport",
                    "address": LOCATIONS["cai_vieng_ferry"]["address"],
                    "actual_cost": 80_000,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Rời trung tâm sớm hơn giờ phà dự kiến",
                    "next_traveler_note": "Chừa thời gian dự phòng cho ùn tắc và xếp hàng tại bến.",
                },
                {
                    "location_id": LOCATIONS["dong_bai_ferry"]["id"],
                    "lat": LOCATIONS["dong_bai_ferry"]["lat"],
                    "lng": LOCATIONS["dong_bai_ferry"]["lng"],
                    "start_time": "14:30",
                    "end_time": "15:00",
                    "title": "Qua phà Cái Viềng – Đồng Bài",
                    "type": "transport",
                    "address": LOCATIONS["dong_bai_ferry"]["address"],
                    "actual_cost": 20_000,
                    "rating": 4.6,
                    "author_verdict": "must_go",
                    "best_time": "Đầu giờ chiều",
                    "next_traveler_note": "Giờ tới bờ có thể thay đổi theo lượng phương tiện và điều kiện vận hành.",
                },
                {
                    "location_id": LOCATIONS["ha_noi_opera_house"]["id"],
                    "lat": LOCATIONS["ha_noi_opera_house"]["lat"],
                    "lng": LOCATIONS["ha_noi_opera_house"]["lng"],
                    "start_time": "15:00",
                    "end_time": "18:30",
                    "title": "Xe Đồng Bài – Hà Nội, kết thúc hành trình",
                    "type": "transport",
                    "address": LOCATIONS["ha_noi_opera_house"]["address"],
                    "actual_cost": 320_000,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Xuất phát ngay sau khi qua phà",
                    "next_traveler_note": (
                        "Thời gian về Hà Nội phụ thuộc giao thông. Nên tránh đặt lịch quan trọng sát giờ dự kiến kết thúc."
                    ),
                },
            ],
        },
    ],
    "review": {
        "best_places": [
            "Vịnh Lan Hạ",
            "Khu vực Vạn Bội",
            "Đỉnh Ngự Lâm",
            "Bãi Cát Cò 1 và Cát Cò 2",
        ],
        "best_foods": [
            "Bánh đa cua",
            "Bề bề",
            "Mực hấp",
            "Hàu nướng mỡ hành",
            "Canh ngao chua",
        ],
        "tips": (
            "Đặt xe, phòng và tour vịnh trước khi đi vào cuối tuần mùa hè. "
            "Theo dõi dự báo thời tiết, thông báo vận hành phà và tuyến tàu. "
            "Mang giày trekking, túi chống nước, kem chống nắng và thuốc say tàu."
        ),
    },
    "data_sources": {
        "itinerary_basis": [
            "Public 3D2N Cat Ba tour programs from Hanoi",
            "Public Lan Ha Bay day-cruise itineraries departing from Ben Beo",
        ],
        "coordinate_basis": [
            "Google Maps Plus Codes",
            "OpenStreetMap/Mapcarta POI nodes",
            "Wikidata and geotagged Wikimedia coordinates",
            "Published beach and bay coordinates",
        ],
        "verification_date": VERIFIED_AT,
    },
}


def validate_seed_data() -> int:
    """Validate IDs, coordinates, activity references and cost totals."""
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

    total_cost = 0
    for day in CAT_BA_SNAPSHOT["days"]:
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

    expected_per_person = CAT_BA_SNAPSHOT["actual_cost_per_person"]
    if total_cost != expected_per_person:
        raise ValueError(
            f"Cost mismatch: activities={total_cost:,}, snapshot={expected_per_person:,}"
        )

    expected_total = expected_per_person * NUMBER_OF_TRAVELERS
    if CAT_BA_SNAPSHOT["actual_total_cost"] != expected_total:
        raise ValueError(
            "actual_total_cost must equal actual_cost_per_person * traveler_count"
        )

    budget_total = sum(
        value
        for key, value in CAT_BA_SNAPSHOT["budget_breakdown_per_person"].items()
        if key != "total"
    )
    if budget_total != CAT_BA_SNAPSHOT["budget_breakdown_per_person"]["total"]:
        raise ValueError("Budget breakdown does not add up")

    if budget_total != expected_per_person:
        raise ValueError("Budget breakdown total differs from actual_cost_per_person")

    return total_cost


async def seed_cat_ba() -> None:
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

        # 2. Find an author or create a deterministic seed author.
        author_email = "guide.catba@smarttravel.vn"
        stmt_user = select(User).where(User.email == author_email)
        res_user = await session.execute(stmt_user)
        user = res_user.scalar_one_or_none()

        if not user:
            print(f"No user '{author_email}' found. Creating seed author...")
            user = User(
                id=uuid.uuid4(),
                username="guide-catba",
                email=author_email,
                full_name="Trần Minh Anh (Hướng dẫn viên Cát Bà)",
                password_hash="seed-only-account-not-for-login",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

        # 3. Create or update public trip publication.
        slug = "lich-trinh-cat-ba-vinh-lan-ha-3-ngay-2-dem-chi-tiet"
        stmt_pub = select(PublicTripPublication).where(
            PublicTripPublication.slug == slug
        )
        res_pub = await session.execute(stmt_pub)
        existing = res_pub.scalar_one_or_none()

        publication_values = {
            "title": CAT_BA_SNAPSHOT["title"],
            "summary": (
                "Hành trình Cát Bà - Vịnh Lan Hạ 3 ngày 2 đêm từ Hà Nội cho 2 người: "
                "qua phà Đồng Bài - Cái Viềng, tắm Bãi Cát Cò, đi tàu qua làng chài "
                "Cái Bèo, chèo kayak tại Vạn Bội, trekking Đỉnh Ngự Lâm và khám phá "
                "Động Trung Trang với ngân sách khoảng 3,93 triệu đồng/người."
            ),
            "destination": "Cát Bà (Hải Phòng)",
            "province_name": "Hải Phòng",
            "duration_days": 3,
            "actual_total_cost": CAT_BA_SNAPSHOT["actual_total_cost"],
            "actual_cost_per_person": CAT_BA_SNAPSHOT["actual_cost_per_person"],
            "overall_rating": CAT_BA_SNAPSHOT["overall_rating"],
            "status": "published",
            "visibility": "public",
            "moderation_status": "approved",
            "cover_image_url": (
                "https://images.unsplash.com/photo-1528127269322-539801943592"
                "?auto=format&fit=crop&w=1200&q=80"
            ),
            "snapshot_json": CAT_BA_SNAPSHOT,
            "tags": [
                "Cát Bà",
                "Hải Phòng",
                "Vịnh Lan Hạ",
                "3 ngày 2 đêm",
                "Chèo kayak",
                "Bãi Cát Cò",
                "Vườn quốc gia",
                "Đỉnh Ngự Lâm",
                "Động Trung Trang",
            ],
            "save_count": 0,
            "view_count": 1830,
            "published_at": datetime.now(timezone.utc),
        }

        if existing:
            print(f"Publication '{slug}' already exists. Updating content...")
            for field, value in publication_values.items():
                setattr(existing, field, value)
        else:
            print(f"Creating new Public Trip Publication '{slug}'...")
            pub = PublicTripPublication(
                id=uuid.uuid4(),
                author_user_id=user.id,
                slug=slug,
                **publication_values,
            )
            session.add(pub)

        await session.commit()
        print("Successfully seeded Cat Ba 3D2N itinerary!")


if __name__ == "__main__":
    asyncio.run(seed_cat_ba())
