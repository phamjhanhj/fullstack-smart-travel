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
# SA PA - FANSIPAN 3D2N SEED DATA
#
# Itinerary basis:
# - Public 3-day/2-night Sa Pa tours departing from Hanoi.
# - Day 1 focuses on the town centre and Cat Cat Village.
# - Day 2 is reserved for Fansipan, Silver Waterfall and Tram Ton Pass.
# - Day 3 follows the Lao Chai - Ta Van trekking corridor before returning.
#
# Coordinate policy:
# - POIs use public Google Maps pins, OpenStreetMap/Mapcarta nodes,
#   Wikidata coordinates, Apple Maps coordinates, or official place links.
# - Large areas use a clearly labelled entrance, station, village centre,
#   summit marker, market pin or representative area centre.
# - Every location includes a Google Maps URL for manual verification.
# - Coordinates were last reviewed on 2026-07-30.
#
# Cost policy:
# - actual_cost is the estimated cost PER PERSON for this sample itinerary.
# - Costs are seed/demo values, not binding quotations.
# - Fansipan prices and operating schedules can change by date and weather.
# -----------------------------------------------------------------------------

VERIFIED_AT = "2026-07-30"
NUMBER_OF_TRAVELERS = 2

LOCATIONS: dict[str, dict[str, Any]] = {
    "ha_noi_opera_house": {
        "id": "44444444-4444-4444-8444-444444444401",
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
    "trung_tam_sapa": {
        "id": "44444444-4444-4444-8444-444444444402",
        "name": "Khu lưu trú trung tâm Sa Pa",
        "address": "Khu trung tâm phường Sa Pa, tỉnh Lào Cai",
        "lat": 22.333400,
        "lng": 103.842700,
        "category": "hotel",
        "province_name": "Lào Cai",
        "plus_code": "7PJ58RMV+83",
        "coordinate_precision": "accommodation_area_center",
        "coordinate_source": "OpenStreetMap Sa Pa city node 7244010173 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=22.333400,103.842700",
        "verified_at": VERIFIED_AT,
    },
    "nha_tho_da_sapa": {
        "id": "44444444-4444-4444-8444-444444444403",
        "name": "Nhà thờ đá Sa Pa",
        "address": "Quảng trường trung tâm, phường Sa Pa, tỉnh Lào Cai",
        "lat": 22.335200,
        "lng": 103.842250,
        "category": "attraction",
        "province_name": "Lào Cai",
        "plus_code": "7PJ58RPR+3W",
        "coordinate_precision": "poi_building",
        "coordinate_source": "Wikidata Q124156643 / OpenStreetMap node 989240427",
        "google_maps_url": "https://www.google.com/maps?q=22.335200,103.842250",
        "verified_at": VERIFIED_AT,
    },
    "sun_plaza_sapa": {
        "id": "44444444-4444-4444-8444-444444444404",
        "name": "Sun Plaza - Ga Sa Pa",
        "address": "Ngã tư Phan Xi Păng - Hoàng Liên, phường Sa Pa, tỉnh Lào Cai",
        "lat": 22.334781,
        "lng": 103.840355,
        "category": "transport",
        "province_name": "Lào Cai",
        "coordinate_precision": "poi_building",
        "coordinate_source": "Official Sun World Google Maps place link",
        "google_maps_url": "https://www.google.com/maps?q=22.334781,103.840355",
        "verified_at": VERIFIED_AT,
    },
    "khu_am_thuc_sapa": {
        "id": "44444444-4444-4444-8444-444444444405",
        "name": "Khu ẩm thực trung tâm Sa Pa",
        "address": "Khu phố Xuân Viên - Cầu Mây, phường Sa Pa, tỉnh Lào Cai",
        "lat": 22.334620,
        "lng": 103.843460,
        "category": "restaurant",
        "province_name": "Lào Cai",
        "coordinate_precision": "restaurant_area_representative_point",
        "coordinate_source": "Representative centre of the public restaurant corridor",
        "google_maps_url": "https://www.google.com/maps?q=22.334620,103.843460",
        "verified_at": VERIFIED_AT,
    },
    "cho_sapa": {
        "id": "44444444-4444-4444-8444-444444444406",
        "name": "Chợ Sa Pa",
        "address": "Đường Điện Biên Phủ, phường Sa Pa, tỉnh Lào Cai",
        "lat": 22.338290,
        "lng": 103.851990,
        "category": "attraction",
        "province_name": "Lào Cai",
        "plus_code": "7PJ58VQ2+8Q",
        "coordinate_precision": "marketplace_pin",
        "coordinate_source": "OpenStreetMap node 4811351954 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=22.338290,103.851990",
        "verified_at": VERIFIED_AT,
    },
    "ban_cat_cat": {
        "id": "44444444-4444-4444-8444-444444444407",
        "name": "Bản Cát Cát",
        "address": "Bản Cát Cát, phường Sa Pa, tỉnh Lào Cai",
        "lat": 22.328530,
        "lng": 103.834680,
        "category": "attraction",
        "province_name": "Lào Cai",
        "plus_code": "7PJ58RHM+CV",
        "coordinate_precision": "village_center",
        "coordinate_source": "OpenStreetMap node 991996791 / Wikidata Q10743160",
        "google_maps_url": "https://www.google.com/maps?q=22.328530,103.834680",
        "verified_at": VERIFIED_AT,
    },
    "thac_tien_sa": {
        "id": "44444444-4444-4444-8444-444444444408",
        "name": "Thác Tiên Sa - Cát Cát",
        "address": "Bản Cát Cát, phường Sa Pa, tỉnh Lào Cai",
        "lat": 22.326960,
        "lng": 103.834360,
        "category": "attraction",
        "province_name": "Lào Cai",
        "coordinate_precision": "waterfall_pin",
        "coordinate_source": "OpenStreetMap node 991996378 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=22.326960,103.834360",
        "verified_at": VERIFIED_AT,
    },
    "ga_muong_hoa": {
        "id": "44444444-4444-4444-8444-444444444409",
        "name": "Ga Mường Hoa - Ga đi cáp treo Fansipan",
        "address": "Khu du lịch Sun World Fansipan Legend, phường Sa Pa, tỉnh Lào Cai",
        "lat": 22.336620,
        "lng": 103.825000,
        "category": "transport",
        "province_name": "Lào Cai",
        "plus_code": "7PJ58RPF+JX",
        "coordinate_precision": "railway_station_pin",
        "coordinate_source": "OpenStreetMap node 5592212588 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=22.336620,103.825000",
        "verified_at": VERIFIED_AT,
    },
    "dinh_fansipan": {
        "id": "44444444-4444-4444-8444-444444444410",
        "name": "Cột mốc đỉnh Fansipan",
        "address": "Đỉnh Fansipan, dãy Hoàng Liên Sơn, tỉnh Lào Cai",
        "lat": 22.303332,
        "lng": 103.775315,
        "category": "attraction",
        "province_name": "Lào Cai",
        "coordinate_precision": "summit_marker",
        "coordinate_source": "Wikidata Q123782 summit coordinate",
        "google_maps_url": "https://www.google.com/maps?q=22.303332,103.775315",
        "verified_at": VERIFIED_AT,
    },
    "thac_bac": {
        "id": "44444444-4444-4444-8444-444444444411",
        "name": "Thác Bạc Sa Pa",
        "address": "Quốc lộ 4D, khu vực Ô Quy Hồ, tỉnh Lào Cai",
        "lat": 22.361626,
        "lng": 103.778912,
        "category": "attraction",
        "province_name": "Lào Cai",
        "coordinate_precision": "waterfall_pin",
        "coordinate_source": "Published geographic coordinate for Silver Waterfall",
        "google_maps_url": "https://www.google.com/maps?q=22.361626,103.778912",
        "verified_at": VERIFIED_AT,
    },
    "deo_tram_ton": {
        "id": "44444444-4444-4444-8444-444444444412",
        "name": "Điểm ngắm cảnh đèo Trạm Tôn - Ô Quy Hồ",
        "address": "Quốc lộ 4D, khu vực giáp Sa Pa - Tam Đường",
        "lat": 22.355070,
        "lng": 103.760720,
        "category": "attraction",
        "province_name": "Lai Châu",
        "plus_code": "7PJ59Q46+27",
        "coordinate_precision": "scenic_viewpoint_pin",
        "coordinate_source": "OpenStreetMap node 2440165326 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=22.355070,103.760720",
        "verified_at": VERIFIED_AT,
    },
    "lao_chai": {
        "id": "44444444-4444-4444-8444-444444444413",
        "name": "Bản Lao Chải - thung lũng Mường Hoa",
        "address": "Lao Chải, xã Tả Van, tỉnh Lào Cai",
        "lat": 22.310020,
        "lng": 103.876230,
        "category": "attraction",
        "province_name": "Lào Cai",
        "plus_code": "7PJ58V6G+2F",
        "coordinate_precision": "hamlet_center",
        "coordinate_source": "OpenStreetMap node 4414430368 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=22.310020,103.876230",
        "verified_at": VERIFIED_AT,
    },
    "ta_van": {
        "id": "44444444-4444-4444-8444-444444444414",
        "name": "Bản Tả Van",
        "address": "Tả Van, tỉnh Lào Cai",
        "lat": 22.302660,
        "lng": 103.888580,
        "category": "attraction",
        "province_name": "Lào Cai",
        "plus_code": "7PJ58V3Q+3C",
        "coordinate_precision": "village_center",
        "coordinate_source": "OpenStreetMap node 2587546398 via Mapcarta",
        "google_maps_url": "https://www.google.com/maps?q=22.302660,103.888580",
        "verified_at": VERIFIED_AT,
    },
}


SAPA_SNAPSHOT: dict[str, Any] = {
    "title": "Lịch trình Sa Pa - Fansipan 3 ngày 2 đêm chi tiết từ Hà Nội",
    "destination": "Sa Pa, Lào Cai",
    "duration_days": 3,
    "traveler_count": NUMBER_OF_TRAVELERS,
    "actual_cost_per_person": 5_250_000,
    "actual_total_cost": 10_500_000,
    "overall_rating": 4.9,
    "coordinate_verified_at": VERIFIED_AT,
    "cost_note": (
        "Chi phí là mức seed tham khảo theo người, không phải báo giá cố định. "
        "Giá vé Fansipan, phòng, xe và phí bản có thể thay đổi theo ngày, cuối tuần, "
        "lễ Tết, chương trình ưu đãi và điều kiện vận hành thực tế."
    ),
    "budget_breakdown_per_person": {
        "transport": 1_180_000,
        "lodging": 700_000,
        "food": 1_380_000,
        "tours_and_tickets": 1_690_000,
        "miscellaneous": 300_000,
        "total": 5_250_000,
    },
    "days": [
        {
            "day_number": 1,
            "title": "Hà Nội – Sa Pa – Nhà thờ đá – Bản Cát Cát",
            "activities": [
                {
                    "location_id": LOCATIONS["ha_noi_opera_house"]["id"],
                    "lat": LOCATIONS["ha_noi_opera_house"]["lat"],
                    "lng": LOCATIONS["ha_noi_opera_house"]["lng"],
                    "start_time": "05:30",
                    "end_time": "06:00",
                    "title": "Tập trung và ăn sáng nhẹ tại Nhà hát Lớn Hà Nội",
                    "type": "meal",
                    "address": LOCATIONS["ha_noi_opera_house"]["address"],
                    "actual_cost": 50_000,
                    "rating": 4.7,
                    "author_verdict": "recommended",
                    "best_time": "Có mặt trước giờ xe chạy ít nhất 15 phút",
                    "next_traveler_note": (
                        "Mang áo khoác mỏng trong hành lý xách tay vì nhiệt độ Sa Pa có thể "
                        "thấp hơn Hà Nội rõ rệt; không nên ăn quá no trước khi đi cao tốc."
                    ),
                },
                {
                    "location_id": LOCATIONS["trung_tam_sapa"]["id"],
                    "lat": LOCATIONS["trung_tam_sapa"]["lat"],
                    "lng": LOCATIONS["trung_tam_sapa"]["lng"],
                    "start_time": "06:00",
                    "end_time": "12:30",
                    "title": "Xe cabin hoặc limousine Hà Nội – Sa Pa",
                    "type": "transport",
                    "address": LOCATIONS["trung_tam_sapa"]["address"],
                    "actual_cost": 300_000,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Khởi hành khoảng 06:00",
                    "next_traveler_note": (
                        "Tuyến đi theo cao tốc Nội Bài – Lào Cai. Thời gian có thể kéo dài "
                        "do nghỉ dọc đường và đoạn đèo từ thành phố Lào Cai lên Sa Pa."
                    ),
                },
                {
                    "location_id": LOCATIONS["khu_am_thuc_sapa"]["id"],
                    "lat": LOCATIONS["khu_am_thuc_sapa"]["lat"],
                    "lng": LOCATIONS["khu_am_thuc_sapa"]["lng"],
                    "start_time": "12:30",
                    "end_time": "13:30",
                    "title": "Ăn trưa với các món đặc sản Tây Bắc",
                    "type": "meal",
                    "address": LOCATIONS["khu_am_thuc_sapa"]["address"],
                    "actual_cost": 180_000,
                    "rating": 4.8,
                    "author_verdict": "recommended",
                    "best_time": "Ăn ngay sau khi đến Sa Pa",
                    "next_traveler_note": (
                        "Gợi ý gà bản, lợn bản, rau cải mèo và cơm. Hỏi giá trước khi gọi "
                        "cá hồi hoặc cá tầm theo cân."
                    ),
                },
                {
                    "location_id": LOCATIONS["trung_tam_sapa"]["id"],
                    "lat": LOCATIONS["trung_tam_sapa"]["lat"],
                    "lng": LOCATIONS["trung_tam_sapa"]["lng"],
                    "start_time": "13:30",
                    "end_time": "14:15",
                    "title": "Nhận phòng khách sạn tại trung tâm Sa Pa",
                    "type": "attraction",
                    "address": LOCATIONS["trung_tam_sapa"]["address"],
                    "actual_cost": 700_000,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Chọn phòng gần quảng trường để thuận tiện đi bộ",
                    "next_traveler_note": (
                        "Chi phí tính theo đầu người cho 2 đêm, giả định 2 người ở chung phòng. "
                        "Ưu tiên nơi có sưởi, nước nóng và hỗ trợ gửi hành lý ngày cuối."
                    ),
                },
                {
                    "location_id": LOCATIONS["nha_tho_da_sapa"]["id"],
                    "lat": LOCATIONS["nha_tho_da_sapa"]["lat"],
                    "lng": LOCATIONS["nha_tho_da_sapa"]["lng"],
                    "start_time": "14:30",
                    "end_time": "15:10",
                    "title": "Tham quan Nhà thờ đá và Quảng trường Sa Pa",
                    "type": "attraction",
                    "address": LOCATIONS["nha_tho_da_sapa"]["address"],
                    "actual_cost": 0,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Đầu buổi chiều hoặc khi quảng trường ít đông",
                    "next_traveler_note": (
                        "Giữ trật tự nếu bên trong đang có nghi lễ. Sun Plaza nằm chếch "
                        "đối diện nên có thể kết hợp chụp ảnh trong cùng một lượt đi bộ."
                    ),
                },
                {
                    "location_id": LOCATIONS["ban_cat_cat"]["id"],
                    "lat": LOCATIONS["ban_cat_cat"]["lat"],
                    "lng": LOCATIONS["ban_cat_cat"]["lng"],
                    "start_time": "15:10",
                    "end_time": "15:30",
                    "title": "Di chuyển từ trung tâm Sa Pa tới Bản Cát Cát",
                    "type": "transport",
                    "address": LOCATIONS["ban_cat_cat"]["address"],
                    "actual_cost": 60_000,
                    "rating": 4.7,
                    "author_verdict": "must_go",
                    "best_time": "Đi taxi hoặc xe điện để giữ sức",
                    "next_traveler_note": (
                        "Đường xuống bản dốc. Người không quen lái xe đường núi không nên tự thuê xe máy."
                    ),
                },
                {
                    "location_id": LOCATIONS["ban_cat_cat"]["id"],
                    "lat": LOCATIONS["ban_cat_cat"]["lat"],
                    "lng": LOCATIONS["ban_cat_cat"]["lng"],
                    "start_time": "15:30",
                    "end_time": "17:00",
                    "title": "Khám phá Bản Cát Cát và không gian văn hóa người H'Mông",
                    "type": "attraction",
                    "address": LOCATIONS["ban_cat_cat"]["address"],
                    "actual_cost": 150_000,
                    "rating": 4.9,
                    "author_verdict": "must_go",
                    "best_time": "Chiều mát, tránh khung giờ đông nhất buổi sáng",
                    "next_traveler_note": (
                        "Mang giày bám tốt vì có nhiều bậc và đường dốc. Không tự ý chụp cận mặt "
                        "người dân hoặc trẻ em nếu chưa xin phép."
                    ),
                },
                {
                    "location_id": LOCATIONS["thac_tien_sa"]["id"],
                    "lat": LOCATIONS["thac_tien_sa"]["lat"],
                    "lng": LOCATIONS["thac_tien_sa"]["lng"],
                    "start_time": "17:00",
                    "end_time": "17:35",
                    "title": "Check-in Thác Tiên Sa trong khu Cát Cát",
                    "type": "attraction",
                    "address": LOCATIONS["thac_tien_sa"]["address"],
                    "actual_cost": 0,
                    "rating": 4.8,
                    "author_verdict": "recommended",
                    "best_time": "Trước khi rời bản, khi còn đủ ánh sáng",
                    "next_traveler_note": (
                        "Chi phí được tính trong vé Cát Cát. Không bước ra đá trơn sát dòng nước, "
                        "đặc biệt sau mưa."
                    ),
                },
                {
                    "location_id": LOCATIONS["trung_tam_sapa"]["id"],
                    "lat": LOCATIONS["trung_tam_sapa"]["lat"],
                    "lng": LOCATIONS["trung_tam_sapa"]["lng"],
                    "start_time": "17:35",
                    "end_time": "18:00",
                    "title": "Trở về trung tâm Sa Pa",
                    "type": "transport",
                    "address": LOCATIONS["trung_tam_sapa"]["address"],
                    "actual_cost": 60_000,
                    "rating": 4.7,
                    "author_verdict": "must_go",
                    "best_time": "Rời bản trước khi trời tối và sương dày",
                    "next_traveler_note": "Thống nhất trước điểm đón và giá xe để tránh phải đi ngược dốc tìm xe.",
                },
                {
                    "location_id": LOCATIONS["khu_am_thuc_sapa"]["id"],
                    "lat": LOCATIONS["khu_am_thuc_sapa"]["lat"],
                    "lng": LOCATIONS["khu_am_thuc_sapa"]["lng"],
                    "start_time": "19:00",
                    "end_time": "20:30",
                    "title": "Ăn tối đồ nướng Sa Pa",
                    "type": "meal",
                    "address": LOCATIONS["khu_am_thuc_sapa"]["address"],
                    "actual_cost": 250_000,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Buổi tối lạnh",
                    "next_traveler_note": (
                        "Chọn đồ nướng chín kỹ, gọi lượng vừa đủ và ưu tiên quán niêm yết giá rõ ràng."
                    ),
                },
                {
                    "location_id": LOCATIONS["cho_sapa"]["id"],
                    "lat": LOCATIONS["cho_sapa"]["lat"],
                    "lng": LOCATIONS["cho_sapa"]["lng"],
                    "start_time": "20:30",
                    "end_time": "21:45",
                    "title": "Dạo khu chợ Sa Pa, mua đồ ăn nhẹ và đặc sản",
                    "type": "attraction",
                    "address": LOCATIONS["cho_sapa"]["address"],
                    "actual_cost": 100_000,
                    "rating": 4.6,
                    "author_verdict": "recommended",
                    "best_time": "Buổi tối hoặc cuối tuần",
                    "next_traveler_note": (
                        "Giờ và khu vực hoạt động của chợ đêm có thể thay đổi. Mang tiền mặt nhỏ, "
                        "kiểm tra hạn sử dụng và nguồn gốc đặc sản đóng gói."
                    ),
                },
            ],
        },
        {
            "day_number": 2,
            "title": "Tàu Mường Hoa – Fansipan – Thác Bạc – đèo Trạm Tôn",
            "activities": [
                {
                    "location_id": LOCATIONS["khu_am_thuc_sapa"]["id"],
                    "lat": LOCATIONS["khu_am_thuc_sapa"]["lat"],
                    "lng": LOCATIONS["khu_am_thuc_sapa"]["lng"],
                    "start_time": "06:30",
                    "end_time": "07:15",
                    "title": "Ăn sáng phở, bún hoặc bánh cuốn nóng",
                    "type": "meal",
                    "address": LOCATIONS["khu_am_thuc_sapa"]["address"],
                    "actual_cost": 60_000,
                    "rating": 4.7,
                    "author_verdict": "recommended",
                    "best_time": "Ăn đủ năng lượng trước khi lên cao",
                    "next_traveler_note": (
                        "Không uống nhiều rượu tối hôm trước. Mang nước, áo ấm, áo mưa mỏng và thuốc cá nhân."
                    ),
                },
                {
                    "location_id": LOCATIONS["sun_plaza_sapa"]["id"],
                    "lat": LOCATIONS["sun_plaza_sapa"]["lat"],
                    "lng": LOCATIONS["sun_plaza_sapa"]["lng"],
                    "start_time": "07:20",
                    "end_time": "07:50",
                    "title": "Check-in Sun Plaza và làm thủ tục vé Fansipan",
                    "type": "attraction",
                    "address": LOCATIONS["sun_plaza_sapa"]["address"],
                    "actual_cost": 0,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Tới sớm trước lượt khách đoàn",
                    "next_traveler_note": (
                        "Kiểm tra thông báo vận hành trong ngày. Sương, gió mạnh hoặc bảo trì có thể "
                        "làm thay đổi giờ chạy của tàu và cáp treo."
                    ),
                },
                {
                    "location_id": LOCATIONS["dinh_fansipan"]["id"],
                    "lat": LOCATIONS["dinh_fansipan"]["lat"],
                    "lng": LOCATIONS["dinh_fansipan"]["lng"],
                    "start_time": "07:50",
                    "end_time": "12:30",
                    "title": "Combo tàu Mường Hoa, cáp treo và tàu leo núi Fansipan",
                    "type": "attraction",
                    "address": LOCATIONS["dinh_fansipan"]["address"],
                    "actual_cost": 1_320_000,
                    "rating": 5.0,
                    "author_verdict": "must_go",
                    "best_time": "Buổi sáng; ưu tiên ngày dự báo ít mây và gió",
                    "next_traveler_note": (
                        "Mức phí seed tham khảo cho tàu Mường Hoa, cáp treo khứ hồi và tàu leo núi "
                        "đỉnh Fansipan. Cần kiểm tra giá chính thức đúng ngày sử dụng."
                    ),
                },
                {
                    "location_id": LOCATIONS["ga_muong_hoa"]["id"],
                    "lat": LOCATIONS["ga_muong_hoa"]["lat"],
                    "lng": LOCATIONS["ga_muong_hoa"]["lng"],
                    "start_time": "08:00",
                    "end_time": "08:30",
                    "title": "Đi tàu hỏa leo núi Mường Hoa tới ga cáp treo",
                    "type": "transport",
                    "address": LOCATIONS["ga_muong_hoa"]["address"],
                    "actual_cost": 0,
                    "rating": 4.9,
                    "author_verdict": "must_go",
                    "best_time": "Ngồi gần cửa sổ để quan sát thung lũng",
                    "next_traveler_note": "Chi phí đã nằm trong combo Fansipan của hoạt động chính.",
                },
                {
                    "location_id": LOCATIONS["dinh_fansipan"]["id"],
                    "lat": LOCATIONS["dinh_fansipan"]["lat"],
                    "lng": LOCATIONS["dinh_fansipan"]["lng"],
                    "start_time": "08:30",
                    "end_time": "11:30",
                    "title": "Tham quan quần thể tâm linh và chạm cột mốc Fansipan",
                    "type": "attraction",
                    "address": LOCATIONS["dinh_fansipan"]["address"],
                    "actual_cost": 0,
                    "rating": 5.0,
                    "author_verdict": "must_go",
                    "best_time": "Trước giữa trưa, tùy tầm nhìn thực tế",
                    "next_traveler_note": (
                        "Di chuyển chậm để thích nghi độ cao; dừng nghỉ nếu chóng mặt, khó thở hoặc buồn nôn. "
                        "Nhiệt độ trên đỉnh có thể thấp và gió mạnh hơn nhiều so với thị trấn."
                    ),
                },
                {
                    "location_id": LOCATIONS["ga_muong_hoa"]["id"],
                    "lat": LOCATIONS["ga_muong_hoa"]["lat"],
                    "lng": LOCATIONS["ga_muong_hoa"]["lng"],
                    "start_time": "11:30",
                    "end_time": "12:30",
                    "title": "Trở xuống ga Mường Hoa và về trung tâm Sa Pa",
                    "type": "transport",
                    "address": LOCATIONS["ga_muong_hoa"]["address"],
                    "actual_cost": 0,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Theo đúng lượt vận hành được thông báo",
                    "next_traveler_note": "Giữ vé hoặc mã QR tới khi hoàn thành toàn bộ hành trình khứ hồi.",
                },
                {
                    "location_id": LOCATIONS["khu_am_thuc_sapa"]["id"],
                    "lat": LOCATIONS["khu_am_thuc_sapa"]["lat"],
                    "lng": LOCATIONS["khu_am_thuc_sapa"]["lng"],
                    "start_time": "12:45",
                    "end_time": "14:00",
                    "title": "Ăn trưa cá hồi hoặc cá tầm Sa Pa",
                    "type": "meal",
                    "address": LOCATIONS["khu_am_thuc_sapa"]["address"],
                    "actual_cost": 220_000,
                    "rating": 4.8,
                    "author_verdict": "recommended",
                    "best_time": "Sau khi xuống núi và nghỉ 15 phút",
                    "next_traveler_note": (
                        "Nhóm 2 người nên chọn suất nhỏ hoặc lẩu mini, tránh gọi cá nguyên con quá lớn."
                    ),
                },
                {
                    "location_id": LOCATIONS["thac_bac"]["id"],
                    "lat": LOCATIONS["thac_bac"]["lat"],
                    "lng": LOCATIONS["thac_bac"]["lng"],
                    "start_time": "14:15",
                    "end_time": "15:00",
                    "title": "Thuê xe có lái đi Thác Bạc và đèo Trạm Tôn",
                    "type": "transport",
                    "address": LOCATIONS["thac_bac"]["address"],
                    "actual_cost": 300_000,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Đầu giờ chiều, khi tầm nhìn thường ổn định hơn sáng sớm",
                    "next_traveler_note": (
                        "Chi phí là phần chia theo người cho xe khứ hồi tuyến trung tâm – Thác Bạc – "
                        "Trạm Tôn. Không tự lái xe nếu chưa quen đèo và sương mù."
                    ),
                },
                {
                    "location_id": LOCATIONS["thac_bac"]["id"],
                    "lat": LOCATIONS["thac_bac"]["lat"],
                    "lng": LOCATIONS["thac_bac"]["lng"],
                    "start_time": "15:00",
                    "end_time": "16:00",
                    "title": "Tham quan Thác Bạc",
                    "type": "attraction",
                    "address": LOCATIONS["thac_bac"]["address"],
                    "actual_cost": 20_000,
                    "rating": 4.8,
                    "author_verdict": "recommended",
                    "best_time": "Mùa có lượng nước tốt và trời khô",
                    "next_traveler_note": (
                        "Bậc đá có thể trơn; không vượt rào hoặc đi vào khu vực bị cảnh báo sạt lở."
                    ),
                },
                {
                    "location_id": LOCATIONS["deo_tram_ton"]["id"],
                    "lat": LOCATIONS["deo_tram_ton"]["lat"],
                    "lng": LOCATIONS["deo_tram_ton"]["lng"],
                    "start_time": "16:15",
                    "end_time": "17:30",
                    "title": "Ngắm Hoàng Liên Sơn tại đèo Trạm Tôn - Ô Quy Hồ",
                    "type": "attraction",
                    "address": LOCATIONS["deo_tram_ton"]["address"],
                    "actual_cost": 0,
                    "rating": 4.9,
                    "author_verdict": "must_go",
                    "best_time": "Cuối chiều nếu không có sương dày",
                    "next_traveler_note": (
                        "Tọa độ là điểm ngắm cảnh Trạm Tôn trên bản đồ mở. Không đứng sát mép đường, "
                        "không dừng xe ở cua khuất và quay về sớm khi mây mù tăng."
                    ),
                },
                {
                    "location_id": LOCATIONS["khu_am_thuc_sapa"]["id"],
                    "lat": LOCATIONS["khu_am_thuc_sapa"]["lat"],
                    "lng": LOCATIONS["khu_am_thuc_sapa"]["lng"],
                    "start_time": "19:00",
                    "end_time": "20:30",
                    "title": "Ăn tối lẩu cá tầm hoặc thắng cố phiên bản dễ ăn",
                    "type": "meal",
                    "address": LOCATIONS["khu_am_thuc_sapa"]["address"],
                    "actual_cost": 350_000,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Buổi tối sau khi trở về từ đèo",
                    "next_traveler_note": (
                        "Nếu thử thắng cố, nên chọn quán sạch và gọi phần nhỏ. Không uống rượu nếu ngày sau trekking."
                    ),
                },
                {
                    "location_id": LOCATIONS["trung_tam_sapa"]["id"],
                    "lat": LOCATIONS["trung_tam_sapa"]["lat"],
                    "lng": LOCATIONS["trung_tam_sapa"]["lng"],
                    "start_time": "20:30",
                    "end_time": "21:45",
                    "title": "Massage chân hoặc uống cà phê tại trung tâm",
                    "type": "attraction",
                    "address": LOCATIONS["trung_tam_sapa"]["address"],
                    "actual_cost": 180_000,
                    "rating": 4.7,
                    "author_verdict": "recommended",
                    "best_time": "Sau ngày di chuyển nhiều bậc và độ cao",
                    "next_traveler_note": "Xem bảng giá trước khi sử dụng dịch vụ và ngủ sớm để giữ sức ngày 3.",
                },
            ],
        },
        {
            "day_number": 3,
            "title": "Lao Chải – Tả Van – Chợ Sa Pa – Hà Nội",
            "activities": [
                {
                    "location_id": LOCATIONS["khu_am_thuc_sapa"]["id"],
                    "lat": LOCATIONS["khu_am_thuc_sapa"]["lat"],
                    "lng": LOCATIONS["khu_am_thuc_sapa"]["lng"],
                    "start_time": "06:30",
                    "end_time": "07:15",
                    "title": "Ăn sáng và hoàn tất trả phòng",
                    "type": "meal",
                    "address": LOCATIONS["khu_am_thuc_sapa"]["address"],
                    "actual_cost": 60_000,
                    "rating": 4.7,
                    "author_verdict": "recommended",
                    "best_time": "Gửi hành lý tại khách sạn trước khi trekking",
                    "next_traveler_note": (
                        "Chỉ mang ba lô nhỏ, nước, áo mưa, kem chống nắng và giấy tờ cần thiết."
                    ),
                },
                {
                    "location_id": LOCATIONS["lao_chai"]["id"],
                    "lat": LOCATIONS["lao_chai"]["lat"],
                    "lng": LOCATIONS["lao_chai"]["lng"],
                    "start_time": "07:15",
                    "end_time": "08:00",
                    "title": "Di chuyển từ trung tâm Sa Pa xuống Bản Lao Chải",
                    "type": "transport",
                    "address": LOCATIONS["lao_chai"]["address"],
                    "actual_cost": 100_000,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Khởi hành sớm trước nắng và mưa chiều",
                    "next_traveler_note": (
                        "Nên dùng xe có lái hoặc tour trekking. Đường xuống thung lũng có nhiều đoạn dốc và cua."
                    ),
                },
                {
                    "location_id": LOCATIONS["lao_chai"]["id"],
                    "lat": LOCATIONS["lao_chai"]["lat"],
                    "lng": LOCATIONS["lao_chai"]["lng"],
                    "start_time": "08:00",
                    "end_time": "10:30",
                    "title": "Trekking ruộng bậc thang và tìm hiểu Bản Lao Chải",
                    "type": "attraction",
                    "address": LOCATIONS["lao_chai"]["address"],
                    "actual_cost": 200_000,
                    "rating": 5.0,
                    "author_verdict": "must_go",
                    "best_time": "Buổi sáng; mùa nước đổ hoặc mùa lúa chín",
                    "next_traveler_note": (
                        "Chi phí gồm phí bản/hướng dẫn địa phương ước tính. Đi theo lối dân sinh được phép, "
                        "không giẫm lên ruộng và không tự ý vào nhà dân."
                    ),
                },
                {
                    "location_id": LOCATIONS["ta_van"]["id"],
                    "lat": LOCATIONS["ta_van"]["lat"],
                    "lng": LOCATIONS["ta_van"]["lng"],
                    "start_time": "10:30",
                    "end_time": "12:00",
                    "title": "Đi bộ tiếp tới Bản Tả Van và khám phá văn hóa người Giáy",
                    "type": "attraction",
                    "address": LOCATIONS["ta_van"]["address"],
                    "actual_cost": 0,
                    "rating": 4.9,
                    "author_verdict": "must_go",
                    "best_time": "Hoàn thành trước giờ trưa",
                    "next_traveler_note": (
                        "Tọa độ là trung tâm làng. Tuyến đi thực tế do hướng dẫn viên điều chỉnh theo mưa, "
                        "độ trơn và thể lực của nhóm."
                    ),
                },
                {
                    "location_id": LOCATIONS["ta_van"]["id"],
                    "lat": LOCATIONS["ta_van"]["lat"],
                    "lng": LOCATIONS["ta_van"]["lng"],
                    "start_time": "12:00",
                    "end_time": "13:15",
                    "title": "Ăn trưa tại nhà hàng hoặc homestay ở Tả Van",
                    "type": "meal",
                    "address": LOCATIONS["ta_van"]["address"],
                    "actual_cost": 180_000,
                    "rating": 4.8,
                    "author_verdict": "recommended",
                    "best_time": "Nghỉ đủ trước khi lên xe về thị trấn",
                    "next_traveler_note": (
                        "Ưu tiên món nóng, rau địa phương và hỏi trước nếu có yêu cầu ăn chay hoặc dị ứng."
                    ),
                },
                {
                    "location_id": LOCATIONS["trung_tam_sapa"]["id"],
                    "lat": LOCATIONS["trung_tam_sapa"]["lat"],
                    "lng": LOCATIONS["trung_tam_sapa"]["lng"],
                    "start_time": "13:15",
                    "end_time": "14:00",
                    "title": "Xe đón Tả Van về trung tâm Sa Pa",
                    "type": "transport",
                    "address": LOCATIONS["trung_tam_sapa"]["address"],
                    "actual_cost": 60_000,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Rời thung lũng trước khi mưa chiều",
                    "next_traveler_note": "Hẹn trước giờ và điểm đón với lái xe hoặc đơn vị tổ chức trekking.",
                },
                {
                    "location_id": LOCATIONS["cho_sapa"]["id"],
                    "lat": LOCATIONS["cho_sapa"]["lat"],
                    "lng": LOCATIONS["cho_sapa"]["lng"],
                    "start_time": "14:00",
                    "end_time": "14:45",
                    "title": "Mua quà tại Chợ Sa Pa và lấy hành lý",
                    "type": "attraction",
                    "address": LOCATIONS["cho_sapa"]["address"],
                    "actual_cost": 50_000,
                    "rating": 4.6,
                    "author_verdict": "recommended",
                    "best_time": "Mua nhanh trước giờ xe về Hà Nội",
                    "next_traveler_note": (
                        "Ngân sách chỉ là khoản mua nhỏ. Không tính các món quà giá trị cao vào tổng seed."
                    ),
                },
                {
                    "location_id": LOCATIONS["ha_noi_opera_house"]["id"],
                    "lat": LOCATIONS["ha_noi_opera_house"]["lat"],
                    "lng": LOCATIONS["ha_noi_opera_house"]["lng"],
                    "start_time": "15:00",
                    "end_time": "21:00",
                    "title": "Xe cabin Sa Pa – Hà Nội, kết thúc hành trình",
                    "type": "transport",
                    "address": LOCATIONS["ha_noi_opera_house"]["address"],
                    "actual_cost": 300_000,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Chọn chuyến 15:00–16:00",
                    "next_traveler_note": (
                        "Thời gian về phụ thuộc giao thông và điểm trả. Không đặt lịch quan trọng sát giờ dự kiến."
                    ),
                },
            ],
        },
    ],
    "review": {
        "best_places": [
            "Đỉnh Fansipan",
            "Bản Cát Cát",
            "Bản Lao Chải - Tả Van",
            "Đèo Trạm Tôn - Ô Quy Hồ",
            "Nhà thờ đá Sa Pa",
        ],
        "best_foods": [
            "Lẩu cá tầm",
            "Cá hồi Sa Pa",
            "Đồ nướng Sa Pa",
            "Gà bản",
            "Rau cải mèo",
        ],
        "tips": (
            "Kiểm tra thời tiết và lịch vận hành Fansipan trước khi đi; mang áo ấm, áo mưa và giày bám tốt; "
            "không tự lái xe máy trên đèo nếu thiếu kinh nghiệm; thuê hướng dẫn địa phương cho tuyến Lao Chải – Tả Van; "
            "tôn trọng đời sống, ruộng nương và quyền riêng tư của cộng đồng bản địa."
        ),
    },
    "data_sources": {
        "itinerary_basis": [
            "https://dulichdaiphong.vn/tour-ghep-sapa-3-ngay-2-dem-3/",
            "https://dulichdaiviet.com/tour-trong-nuoc/du-lich-sapa-3-ngay-2-dem-khoi-hanh-hang-ngay.html",
            "https://www.klook.com/vi/activity/33969-3d2n-sapa-tour-hanoi-dcar-bus-transfers/",
            "https://visitsapa.com.vn/vi/kham-pha-ban-lao-chai-ta-van-noi-thu-hut-hang-tram-du-khach-8978",
        ],
        "ticket_and_operation_basis": [
            "https://sunworld.vn/vi/fansipan",
            "https://sunworld.vn/fansipan/check-in/cam-nang-trai-nghiem-sun-world-fansipan",
            "https://sunworld.vn/vi/fansipan/cam-nang-du-lich/kinh-nghiem-di-cap-treo-fansipan-day-du-va-chi-tiet",
        ],
        "coordinate_basis": [
            "OpenStreetMap/Mapcarta POI nodes",
            "Wikidata coordinates",
            "Official Sun World Google Maps place link",
            "Published geographic coordinates and Apple Maps where appropriate",
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

    expected_day_numbers = list(range(1, SAPA_SNAPSHOT["duration_days"] + 1))
    actual_day_numbers = [day["day_number"] for day in SAPA_SNAPSHOT["days"]]
    if actual_day_numbers != expected_day_numbers:
        raise ValueError(
            f"Day numbers must be sequential: expected={expected_day_numbers}, "
            f"actual={actual_day_numbers}"
        )

    total_cost = 0
    activity_count = 0
    for day in SAPA_SNAPSHOT["days"]:
        for activity in day["activities"]:
            activity_count += 1
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

    expected_per_person = SAPA_SNAPSHOT["actual_cost_per_person"]
    if total_cost != expected_per_person:
        raise ValueError(
            f"Cost mismatch: activities={total_cost:,}, snapshot={expected_per_person:,}"
        )

    expected_total = expected_per_person * NUMBER_OF_TRAVELERS
    if SAPA_SNAPSHOT["actual_total_cost"] != expected_total:
        raise ValueError(
            "actual_total_cost must equal actual_cost_per_person * traveler_count"
        )

    budget_total = sum(
        value
        for key, value in SAPA_SNAPSHOT["budget_breakdown_per_person"].items()
        if key != "total"
    )
    if budget_total != SAPA_SNAPSHOT["budget_breakdown_per_person"]["total"]:
        raise ValueError("Budget breakdown does not add up")

    if budget_total != expected_per_person:
        raise ValueError("Budget breakdown total differs from actual_cost_per_person")

    if activity_count < 20:
        raise ValueError("The itinerary is unexpectedly short")

    return total_cost


async def seed_sapa() -> None:
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
        author_email = "guide.sapa@smarttravel.vn"
        stmt_user = select(User).where(User.email == author_email)
        res_user = await session.execute(stmt_user)
        user = res_user.scalar_one_or_none()

        if not user:
            print(f"No user '{author_email}' found. Creating seed author...")
            user = User(
                id=uuid.uuid4(),
                username="guide-sapa",
                email=author_email,
                full_name="Giàng A Páo (Hướng dẫn viên Sa Pa)",
                password_hash="seed-only-account-not-for-login",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

        # 3. Create or update the public trip publication.
        slug = "lich-trinh-sapa-fansipan-3-ngay-2-dem-chi-tiet"
        stmt_pub = select(PublicTripPublication).where(
            PublicTripPublication.slug == slug
        )
        res_pub = await session.execute(stmt_pub)
        existing = res_pub.scalar_one_or_none()

        publication_values = {
            "title": SAPA_SNAPSHOT["title"],
            "summary": (
                "Hành trình Sa Pa 3 ngày 2 đêm từ Hà Nội cho 2 người: khám phá Nhà thờ đá, "
                "Bản Cát Cát, chinh phục Fansipan bằng tàu và cáp treo, tham quan Thác Bạc, "
                "đèo Trạm Tôn và trekking Lao Chải – Tả Van với ngân sách khoảng "
                "5,25 triệu đồng/người."
            ),
            "destination": "Sa Pa (Lào Cai)",
            "province_name": "Lào Cai",
            "duration_days": 3,
            "actual_total_cost": SAPA_SNAPSHOT["actual_total_cost"],
            "actual_cost_per_person": SAPA_SNAPSHOT["actual_cost_per_person"],
            "overall_rating": SAPA_SNAPSHOT["overall_rating"],
            "status": "published",
            "visibility": "public",
            "moderation_status": "approved",
            "cover_image_url": (
                "https://commons.wikimedia.org/wiki/Special:FilePath/"
                "Fansipan%20Summit%203143m%20aerial%20wide%20temple%20complex%20"
                "sea%20of%20clouds%20Sa%20Pa%20Vietnam.jpg"
            ),
            "snapshot_json": SAPA_SNAPSHOT,
            "tags": [
                "Sa Pa",
                "Lào Cai",
                "3 ngày 2 đêm",
                "Fansipan",
                "Bản Cát Cát",
                "Lao Chải",
                "Tả Van",
                "Trekking",
                "Thác Bạc",
                "Ô Quy Hồ",
                "Tàu hỏa leo núi",
                "Cáp treo",
            ],
            "save_count": 236,
            "view_count": 3180,
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
        print("Successfully seeded Sa Pa - Fansipan 3D2N itinerary!")


if __name__ == "__main__":
    asyncio.run(seed_sapa())
