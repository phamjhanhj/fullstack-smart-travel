import asyncio
import uuid
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.location import Location
from app.models.public_trip import PublicTripPublication

# Lat/lng rechecked against Google Maps / Plus Codes on 2026-07-30.
# For generic areas or businesses without a stable public Place ID, the pin uses the nearest verified entrance/area center.
# See lat_lng_verification_report.html for confidence level and clickable map links.
# Define locations with real lat/lng for map route rendering
LOCATIONS = {
    "ao_tien": {
        "id": "11111111-1111-4111-8111-111111111101",
        "name": "Cảng tàu khách quốc tế Ao Tiên",
        "address": "Ao Tiên, Hạ Long - Vân Đồn, Quảng Ninh",
        "lat": 21.0815625,
        "lng": 107.4619375,
        "category": "transport"
    },
    "cang_quan_lan": {
        "id": "11111111-1111-4111-8111-111111111102",
        "name": "Cảng Quan Lạn",
        "address": "Cảng Quan Lạn, Đảo Quan Lạn, Quảng Ninh",
        "lat": 20.8626000,
        "lng": 107.4778500,
        "category": "transport"
    },
    "trung_tam_quan_lan": {
        "id": "11111111-1111-4111-8111-111111111103",
        "name": "Khu trung tâm Quan Lạn",
        "address": "Phố đi bộ trung tâm đảo Quan Lạn, Quảng Ninh",
        "lat": 20.8747000,
        "lng": 107.4922000,
        "category": "hotel"
    },
    "nh_hung_trang": {
        "id": "11111111-1111-4111-8111-111111111104",
        "name": "Nhà hàng Hưng Trang",
        "address": "Phố đi bộ Quan Lạn, Quảng Ninh",
        "lat": 20.8745500,
        "lng": 107.4921500,
        "category": "restaurant"
    },
    "dinh_quan_lan": {
        "id": "11111111-1111-4111-8111-111111111105",
        "name": "Cụm di tích lịch sử Đình Quan Lạn",
        "address": "Xã Quan Lạn, Huyện Vân Đồn, Quảng Ninh",
        "lat": 20.8776875,
        "lng": 107.4892031,
        "category": "attraction"
    },
    "bai_quan_lan": {
        "id": "11111111-1111-4111-8111-111111111106",
        "name": "Bãi biển Quan Lạn",
        "address": "Xã Quan Lạn, Vân Đồn, Quảng Ninh",
        "lat": 20.8594375,
        "lng": 107.4927031,
        "category": "attraction"
    },
    "eo_gio": {
        "id": "11111111-1111-4111-8111-111111111107",
        "name": "Eo Gió Gót Beo",
        "address": "Eo Gió Quan Lạn, Quảng Ninh",
        "lat": 20.8169375,
        "lng": 107.4771875,
        "category": "attraction"
    },
    "dong_song_doi": {
        "id": "11111111-1111-4111-8111-111111111108",
        "name": "Dòng sông đôi bờ cát trắng",
        "address": "Đường xuyên đảo Quan Lạn - Minh Châu, Quảng Ninh",
        "lat": 20.9212875,
        "lng": 107.5362969,
        "category": "attraction"
    },
    "bai_robinson": {
        "id": "11111111-1111-4111-8111-111111111109",
        "name": "Bãi biển Robinson Quan Lạn",
        "address": "Bãi Robinson, Quan Lạn, Quảng Ninh",
        "lat": 20.9281000,
        "lng": 107.5484500,
        "category": "attraction"
    },
    "bai_minh_chau": {
        "id": "11111111-1111-4111-8111-111111111110",
        "name": "Bãi biển Minh Châu",
        "address": "Xã Minh Châu, Vân Đồn, Quảng Ninh",
        "lat": 20.9451745,
        "lng": 107.5517692,
        "category": "attraction"
    },
    "mai_huong_quan": {
        "id": "11111111-1111-4111-8111-111111111111",
        "name": "Mai Hương Quán khu Minh Châu",
        "address": "Khu Minh Châu, Vân Đồn, Quảng Ninh",
        "lat": 20.9438000,
        "lng": 107.5491500,
        "category": "restaurant"
    },
    "bai_son_hao": {
        "id": "11111111-1111-4111-8111-111111111112",
        "name": "Bãi biển Sơn Hào",
        "address": "Bãi Sơn Hào, Quan Lạn, Quảng Ninh",
        "lat": 20.8977375,
        "lng": 107.5198594,
        "category": "attraction"
    },
    "chan_tien_quan": {
        "id": "11111111-1111-4111-8111-111111111113",
        "name": "Chân Tiên Quán",
        "address": "Khu trung tâm Quan Lạn, Quảng Ninh",
        "lat": 20.8739500,
        "lng": 107.5057500,
        "category": "restaurant"
    },
    "cho_quan_lan": {
        "id": "11111111-1111-4111-8111-111111111114",
        "name": "Chợ trung tâm Quan Lạn",
        "address": "Chợ Quan Lạn, Quảng Ninh",
        "lat": 20.8751500,
        "lng": 107.4925500,
        "category": "attraction"
    },
    "doi_vo_cuc": {
        "id": "11111111-1111-4111-8111-111111111115",
        "name": "Đồi Vô Cực Quan Lạn",
        "address": "Đồi Vô Cực, Quan Lạn, Quảng Ninh",
        "lat": 20.8709375,
        "lng": 107.4981875,
        "category": "attraction"
    }
}

QUAN_LAN_SNAPSHOT = {
    "title": "Lịch trình Quan Lạn 3 ngày 2 đêm chi tiết từ Hà Nội",
    "destination": "Quan Lạn, Quảng Ninh",
    "duration_days": 3,
    "actual_cost_per_person": 3940000,
    "actual_total_cost": 7880000,
    "overall_rating": 4.9,
    "days": [
        {
            "day_number": 1,
            "title": "Hà Nội – Cảng Ao Tiên – Trung tâm Quan Lạn",
            "activities": [
                {
                    "location_id": LOCATIONS["ao_tien"]["id"],
                    "lat": LOCATIONS["ao_tien"]["lat"],
                    "lng": LOCATIONS["ao_tien"]["lng"],
                    "start_time": "05:15",
                    "end_time": "09:15",
                    "title": "Limousine Hà Nội đi Cảng Ao Tiên (Vân Đồn)",
                    "type": "transport",
                    "address": LOCATIONS["ao_tien"]["address"],
                    "actual_cost": 275000,
                    "author_verdict": "must_go",
                    "best_time": "Sáng sớm (05:00 - 05:30)",
                    "next_traveler_note": "Nên gọi điện đặt trước ghế đầu limousine 1-2 ngày. Xe chạy cao tốc Hà Nội - Hải Phòng - Vân Đồn rất êm, khoảng 3.5 - 4 tiếng."
                },
                {
                    "start_time": "07:15",
                    "end_time": "07:45",
                    "title": "Nghỉ trạm dừng & ăn sáng bánh mì/phở",
                    "type": "meal",
                    "address": "Trạm dừng nghỉ Cao tốc Hà Nội - Hải Phòng",
                    "actual_cost": 50000,
                    "author_verdict": "recommended",
                    "best_time": "Ăn nhanh trong 30 phút",
                    "next_traveler_note": "Ăn nhẹ đồ nóng để giữ sức cho chuyến đi tàu cao tốc ra đảo."
                },
                {
                    "location_id": LOCATIONS["cang_quan_lan"]["id"],
                    "lat": LOCATIONS["cang_quan_lan"]["lat"],
                    "lng": LOCATIONS["cang_quan_lan"]["lng"],
                    "start_time": "10:30",
                    "end_time": "11:20",
                    "title": "Tàu cao tốc Ao Tiên – Cảng Quan Lạn",
                    "type": "transport",
                    "address": LOCATIONS["cang_quan_lan"]["address"],
                    "actual_cost": 250000,
                    "author_verdict": "must_go",
                    "best_time": "Chuyến tàu 10:30 sáng",
                    "next_traveler_note": "Tàu cao tốc chạy 45 phút là tới đảo. Nếu say sóng nên ngồi khoang giữa và uống thuốc trước 30 phút."
                },
                {
                    "location_id": LOCATIONS["trung_tam_quan_lan"]["id"],
                    "lat": LOCATIONS["trung_tam_quan_lan"]["lat"],
                    "lng": LOCATIONS["trung_tam_quan_lan"]["lng"],
                    "start_time": "11:45",
                    "end_time": "12:15",
                    "title": "Di chuyển về trung tâm & Thuê xe máy",
                    "type": "transport",
                    "address": LOCATIONS["trung_tam_quan_lan"]["address"],
                    "actual_cost": 100000,
                    "author_verdict": "must_go",
                    "best_time": "Trưa (ngay khi lên đảo)",
                    "next_traveler_note": "Thuê xe máy 200k/ngày giúp chủ động đi bãi Minh Châu, Eo Gió. Nhóm 4-10 người nên thuê xe điện."
                },
                {
                    "location_id": LOCATIONS["nh_hung_trang"]["id"],
                    "lat": LOCATIONS["nh_hung_trang"]["lat"],
                    "lng": LOCATIONS["nh_hung_trang"]["lng"],
                    "start_time": "12:15",
                    "end_time": "13:15",
                    "title": "Ăn trưa tại Nhà hàng Hưng Trang",
                    "type": "meal",
                    "address": "Khu phố đi bộ Quan Lạn (SĐT đặt bàn: 0347 811 647)",
                    "actual_cost": 200000,
                    "rating": 5.0,
                    "author_verdict": "must_go",
                    "best_time": "Giờ ăn trưa (12:00 - 13:30)",
                    "next_traveler_note": "Thực đơn gợi ý: Cơm trắng, canh ngao chua, mực xào cần tỏi, tôm rang hải sản tươi rói."
                },
                {
                    "location_id": LOCATIONS["dinh_quan_lan"]["id"],
                    "lat": LOCATIONS["dinh_quan_lan"]["lat"],
                    "lng": LOCATIONS["dinh_quan_lan"]["lng"],
                    "start_time": "15:15",
                    "end_time": "16:30",
                    "title": "Tham quan Đình Quan Lạn – Đền Trần Khánh Dư – Chùa Quan Lạn",
                    "type": "attraction",
                    "address": LOCATIONS["dinh_quan_lan"]["address"],
                    "actual_cost": 0,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Chiều mát (15:00 - 16:30)",
                    "next_traveler_note": "Đình Quan Lạn dựng hoàn toàn bằng gỗ mần lái cực kỳ quý hiếm, kiến trúc chạm khắc tinh xảo từ thời Lê - Nguyễn."
                },
                {
                    "location_id": LOCATIONS["bai_quan_lan"]["id"],
                    "lat": LOCATIONS["bai_quan_lan"]["lat"],
                    "lng": LOCATIONS["bai_quan_lan"]["lng"],
                    "start_time": "16:45",
                    "end_time": "18:15",
                    "title": "Tắm biển & ngắm hoàng hôn Bãi Quan Lạn",
                    "type": "attraction",
                    "address": LOCATIONS["bai_quan_lan"]["address"],
                    "actual_cost": 40000,
                    "rating": 4.9,
                    "author_verdict": "must_go",
                    "best_time": "Hoàng hôn (17:00 - 18:15)",
                    "next_traveler_note": "Bãi biển ngay gần trung tâm, sóng êm, bờ cát mịn thoải dài thích hợp tắm chiều."
                },
                {
                    "location_id": LOCATIONS["nh_hung_trang"]["id"],
                    "lat": LOCATIONS["nh_hung_trang"]["lat"],
                    "lng": LOCATIONS["nh_hung_trang"]["lng"],
                    "start_time": "19:30",
                    "end_time": "21:00",
                    "title": "Ăn tối hải sản tại Nhà hàng Hưng Trang / Hương Dịu",
                    "type": "meal",
                    "address": "Đầu phố đi bộ Quan Lạn (SĐT Hương Dịu: 0913 770 537)",
                    "actual_cost": 250000,
                    "rating": 4.9,
                    "author_verdict": "must_go",
                    "best_time": "Tối (19:30 - 21:00)",
                    "next_traveler_note": "Nên thưởng thức bề bề hấp sả, ngao hấp, cá biển sốt cà chua và mực chiên giòn."
                },
                {
                    "location_id": LOCATIONS["trung_tam_quan_lan"]["id"],
                    "lat": LOCATIONS["trung_tam_quan_lan"]["lat"],
                    "lng": LOCATIONS["trung_tam_quan_lan"]["lng"],
                    "start_time": "21:00",
                    "end_time": "22:00",
                    "title": "Dạo bước Phố đi bộ Quan Lạn & thưởng thức kem",
                    "type": "attraction",
                    "address": "Phố đi bộ trung tâm đảo Quan Lạn",
                    "actual_cost": 50000,
                    "author_verdict": "recommended",
                    "best_time": "Buổi tối mát mẻ",
                    "next_traveler_note": "Phố đi bộ nhộn nhịp buổi tối, có nhiều hàng quán nước mát, kem tươi giải khát."
                }
            ]
        },
        {
            "day_number": 2,
            "title": "Eo Gió Gót Beo – Sơn Hào – Bãi Robinson – Minh Châu",
            "activities": [
                {
                    "location_id": LOCATIONS["eo_gio"]["id"],
                    "lat": LOCATIONS["eo_gio"]["lat"],
                    "lng": LOCATIONS["eo_gio"]["lng"],
                    "start_time": "04:50",
                    "end_time": "06:45",
                    "title": "Đón bình minh tuyệt đẹp tại Eo Gió Gót Beo",
                    "type": "attraction",
                    "address": LOCATIONS["eo_gio"]["address"],
                    "actual_cost": 15000,
                    "rating": 5.0,
                    "author_verdict": "must_go",
                    "best_time": "Bình minh (05:00 - 06:15)",
                    "next_traveler_note": "Cách trung tâm 7km. Đoạn cuối leo dốc đá khoảng 15 phút, nên đi giày thể thao bám tốt để ngắm trọn vẹn mặt trời mọc trên biển."
                },
                {
                    "location_id": LOCATIONS["trung_tam_quan_lan"]["id"],
                    "lat": LOCATIONS["trung_tam_quan_lan"]["lat"],
                    "lng": LOCATIONS["trung_tam_quan_lan"]["lng"],
                    "start_time": "07:15",
                    "end_time": "08:00",
                    "title": "Ăn sáng bún hải sản / phở hải sản",
                    "type": "meal",
                    "address": "Quán ăn trung tâm Quan Lạn",
                    "actual_cost": 50000,
                    "author_verdict": "recommended",
                    "best_time": "Sáng sớm",
                    "next_traveler_note": "Tô bún đầy đặn có tôm, bề bề, chả cá biển nóng hổi nạp năng lượng."
                },
                {
                    "location_id": LOCATIONS["dong_song_doi"]["id"],
                    "lat": LOCATIONS["dong_song_doi"]["lat"],
                    "lng": LOCATIONS["dong_song_doi"]["lng"],
                    "start_time": "08:45",
                    "end_time": "09:15",
                    "title": "Check-in Dòng sông đôi bờ cát trắng",
                    "type": "attraction",
                    "address": LOCATIONS["dong_song_doi"]["address"],
                    "actual_cost": 0,
                    "rating": 4.7,
                    "author_verdict": "must_go",
                    "best_time": "Nắng sáng đẹp (08:30 - 09:30)",
                    "next_traveler_note": "Điểm check-in nổi tiếng với hàng cỏ lau và dòng nước uốn lượn giữa cát trắng như phim Hàn Quốc."
                },
                {
                    "location_id": LOCATIONS["bai_robinson"]["id"],
                    "lat": LOCATIONS["bai_robinson"]["lat"],
                    "lng": LOCATIONS["bai_robinson"]["lng"],
                    "start_time": "09:30",
                    "end_time": "10:45",
                    "title": "Khám phá bãi hoang sơ Robinson",
                    "type": "attraction",
                    "address": LOCATIONS["bai_robinson"]["address"],
                    "actual_cost": 20000,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Buổi sáng",
                    "next_traveler_note": "Bãi biển hoang sơ tuyệt đẹp, đường vào hơi hẹp nên đi chậm và hỏi người dân địa phương."
                },
                {
                    "location_id": LOCATIONS["bai_minh_chau"]["id"],
                    "lat": LOCATIONS["bai_minh_chau"]["lat"],
                    "lng": LOCATIONS["bai_minh_chau"]["lng"],
                    "start_time": "11:00",
                    "end_time": "12:15",
                    "title": "Tắm biển Bãi Minh Châu",
                    "type": "attraction",
                    "address": LOCATIONS["bai_minh_chau"]["address"],
                    "actual_cost": 40000,
                    "rating": 5.0,
                    "author_verdict": "must_go",
                    "best_time": "Trưa / Trưa muộn",
                    "next_traveler_note": "Bãi biển đẹp nhất đảo! Cát trắng như tuyết, nước trong vắt thấy đáy và bờ biển cực thoải."
                },
                {
                    "location_id": LOCATIONS["mai_huong_quan"]["id"],
                    "lat": LOCATIONS["mai_huong_quan"]["lat"],
                    "lng": LOCATIONS["mai_huong_quan"]["lng"],
                    "start_time": "12:30",
                    "end_time": "13:45",
                    "title": "Ăn trưa tại Mai Hương Quán khu Minh Châu",
                    "type": "meal",
                    "address": LOCATIONS["mai_huong_quan"]["address"],
                    "actual_cost": 225000,
                    "rating": 4.9,
                    "author_verdict": "must_go",
                    "best_time": "Trưa (12:30 - 13:30)",
                    "next_traveler_note": "Quán nấu ăn đậm đà vị biển. Món khuyến nghị: Cá biển hấp, tôm tươi nướng, mực xào và canh chua."
                },
                {
                    "location_id": LOCATIONS["bai_son_hao"]["id"],
                    "lat": LOCATIONS["bai_son_hao"]["lat"],
                    "lng": LOCATIONS["bai_son_hao"]["lng"],
                    "start_time": "17:15",
                    "end_time": "18:00",
                    "title": "Ngắm chiều tà tại Bãi biển Sơn Hào",
                    "type": "attraction",
                    "address": LOCATIONS["bai_son_hao"]["address"],
                    "actual_cost": 0,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Chiều hoàng hôn (17:00 - 18:00)",
                    "next_traveler_note": "Bãi Sơn Hào có dải sóng biển rì rào và bờ cát rộng thích hợp dừng chân ngắm vệt hoàng hôn rực rỡ."
                },
                {
                    "location_id": LOCATIONS["chan_tien_quan"]["id"],
                    "lat": LOCATIONS["chan_tien_quan"]["lat"],
                    "lng": LOCATIONS["chan_tien_quan"]["lng"],
                    "start_time": "18:15",
                    "end_time": "19:45",
                    "title": "Tiệc BBQ hải sản tối tại Chân Tiên Quán",
                    "type": "meal",
                    "address": LOCATIONS["chan_tien_quan"]["address"],
                    "actual_cost": 300000,
                    "rating": 5.0,
                    "author_verdict": "must_go",
                    "best_time": "Tối (18:30 - 20:00)",
                    "next_traveler_note": "Quán chuyên BBQ hải sản tươi sống: Hàu nướng mỡ hành, tôm nướng muối ớt, mực nướng sa tế."
                }
            ]
        },
        {
            "day_number": 3,
            "title": "Chợ Quan Lạn – Đồi Vô Cực – Tàu cao tốc về Hà Nội",
            "activities": [
                {
                    "location_id": LOCATIONS["cho_quan_lan"]["id"],
                    "lat": LOCATIONS["cho_quan_lan"]["lat"],
                    "lng": LOCATIONS["cho_quan_lan"]["lng"],
                    "start_time": "05:45",
                    "end_time": "06:45",
                    "title": "Tham quan Chợ hải sản sớm Quan Lạn",
                    "type": "attraction",
                    "address": LOCATIONS["cho_quan_lan"]["address"],
                    "actual_cost": 50000,
                    "rating": 4.8,
                    "author_verdict": "must_go",
                    "best_time": "Sáng sớm (05:30 - 07:00)",
                    "next_traveler_note": "Chợ nhộn nhịp từ 5:30-7:30 sáng với hải sản vừa kéo lưới: sá sùng, mực ống, ghẹ xanh, cá thu tươi."
                },
                {
                    "location_id": LOCATIONS["doi_vo_cuc"]["id"],
                    "lat": LOCATIONS["doi_vo_cuc"]["lat"],
                    "lng": LOCATIONS["doi_vo_cuc"]["lng"],
                    "start_time": "07:00",
                    "end_time": "08:15",
                    "title": "Check-in Đồi Vô Cực ngắm biển từ trên cao",
                    "type": "attraction",
                    "address": LOCATIONS["doi_vo_cuc"]["address"],
                    "actual_cost": 55000,
                    "rating": 4.9,
                    "author_verdict": "must_go",
                    "best_time": "Sáng mát (07:00 - 08:30)",
                    "next_traveler_note": "Điểm view panorama nhìn ra đại dương cực đẹp trước khi trả phòng khách sạn."
                },
                {
                    "location_id": LOCATIONS["nh_hung_trang"]["id"],
                    "lat": LOCATIONS["nh_hung_trang"]["lat"],
                    "lng": LOCATIONS["nh_hung_trang"]["lng"],
                    "start_time": "10:30",
                    "end_time": "11:30",
                    "title": "Ăn trưa tại Nhà hàng Hưng Trang / Hương Dịu",
                    "type": "meal",
                    "address": "Trung tâm Quan Lạn",
                    "actual_cost": 175000,
                    "author_verdict": "recommended",
                    "best_time": "Trưa (10:30 - 11:30)",
                    "next_traveler_note": "Ăn bữa trưa nhẹ nhàng thanh toán phòng trước khi ra bến tàu."
                },
                {
                    "location_id": LOCATIONS["cang_quan_lan"]["id"],
                    "lat": LOCATIONS["cang_quan_lan"]["lat"],
                    "lng": LOCATIONS["cang_quan_lan"]["lng"],
                    "start_time": "13:30",
                    "end_time": "14:20",
                    "title": "Tàu cao tốc Quan Lạn – Cảng Ao Tiên",
                    "type": "transport",
                    "address": LOCATIONS["cang_quan_lan"]["address"],
                    "actual_cost": 250000,
                    "author_verdict": "must_go",
                    "best_time": "Đầu giờ chiều (13:30)",
                    "next_traveler_note": "Nên ra cảng trước 30 phút để xếp hàng lên tàu."
                },
                {
                    "location_id": LOCATIONS["ao_tien"]["id"],
                    "lat": LOCATIONS["ao_tien"]["lat"],
                    "lng": LOCATIONS["ao_tien"]["lng"],
                    "start_time": "14:45",
                    "end_time": "19:00",
                    "title": "Xe Limousine đón tại Ao Tiên về Hà Nội",
                    "type": "transport",
                    "address": LOCATIONS["ao_tien"]["address"],
                    "actual_cost": 275000,
                    "author_verdict": "must_go",
                    "best_time": "Chiều (14:45)",
                    "next_traveler_note": "Xe limousine đưa về tận nơi trong nội thành Hà Nội. Kết thúc hành trình 3N2Đ tuyệt vời!"
                }
            ]
        }
    ],
    "review": {
        "best_places": ["Eo Gió Gót Beo", "Bãi Minh Châu", "Bãi Robinson", "Đồi Vô Cực"],
        "best_foods": ["Bề bề hấp sả", "Ngao hấp", "Hàu nướng mỡ hành", "Bún hải sản"],
        "tips": "Đặt limousine và tàu cao tốc trước 1-2 ngày vào mùa hè. Thuê xe máy để tự do khám phá đảo. Mang theo tiền mặt vì đảo ít ATM."
    }
}


async def seed_quan_lan():
    async with AsyncSessionLocal() as session:
        # Seed locations first
        for key, loc_data in LOCATIONS.items():
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
                    province_name="Quảng Ninh",
                )
                session.add(new_loc)
            else:
                existing_loc.lat = loc_data["lat"]
                existing_loc.lng = loc_data["lng"]
                existing_loc.address = loc_data["address"]
        await session.commit()

        # Check if user exists
        stmt = select(User).limit(1)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()
        if not user:
            print("No user found in DB to attach as author. Creating default user...")
            user = User(
                id=uuid.uuid4(),
                username="guide-quanlan",
                email="guide.quanlan@smarttravel.vn",
                full_name="Nguyễn Hà Phương (Chuyên gia du lịch)",
                hashed_password="hashedpassword123",
                is_active=True,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

        # Check if Quan Lan publication already exists
        slug = "lich-trinh-quan-lan-3-ngay-2-dem-chi-tiet"
        stmt_pub = select(PublicTripPublication).where(PublicTripPublication.slug == slug)
        res_pub = await session.execute(stmt_pub)
        existing = res_pub.scalar_one_or_none()

        if existing:
            print(f"Publication '{slug}' already exists. Updating content...")
            existing.title = QUAN_LAN_SNAPSHOT["title"]
            existing.summary = (
                "Hành trình Quan Lạn 3N2Đ xuất phát từ Hà Nội cho 2 người, lưu trú trung tâm đảo, di chuyển xe máy, ngắm bình minh Eo Gió, "
                "tắm biển Minh Châu, khám phá bãi Robinson và thưởng thức hải sản tươi ngon với ngân sách 3.9 triệu/người."
            )
            existing.destination = "Quan Lạn (Quảng Ninh)"
            existing.province_name = "Quảng Ninh"
            existing.duration_days = 3
            existing.actual_total_cost = 7880000
            existing.actual_cost_per_person = 3940000
            existing.overall_rating = 4.9
            existing.status = "published"
            existing.visibility = "public"
            existing.moderation_status = "approved"
            existing.cover_image_url = "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1200&q=80"
            existing.snapshot_json = QUAN_LAN_SNAPSHOT
            existing.tags = ["Quan Lạn", "Quảng Ninh", "Biển đảo", "3 ngày 2 đêm", "Phượt xe máy", "Eo Gió", "Bãi Minh Châu"]
            existing.save_count = 128
            existing.view_count = 1450
            existing.published_at = datetime.now(timezone.utc)
        else:
            print(f"Creating new Public Trip Publication '{slug}'...")
            pub = PublicTripPublication(
                id=uuid.uuid4(),
                author_user_id=user.id,
                slug=slug,
                title=QUAN_LAN_SNAPSHOT["title"],
                summary=(
                    "Hành trình Quan Lạn 3N2Đ xuất phát từ Hà Nội cho 2 người, lưu trú trung tâm đảo, di chuyển xe máy, ngắm bình minh Eo Gió, "
                    "tắm biển Minh Châu, khám phá bãi Robinson và thưởng thức hải sản tươi ngon với ngân sách 3.9 triệu/người."
                ),
                destination="Quan Lạn (Quảng Ninh)",
                province_name="Quảng Ninh",
                duration_days=3,
                actual_total_cost=7880000,
                actual_cost_per_person=3940000,
                overall_rating=4.9,
                status="published",
                visibility="public",
                moderation_status="approved",
                cover_image_url="https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1200&q=80",
                snapshot_json=QUAN_LAN_SNAPSHOT,
                tags=["Quan Lạn", "Quảng Ninh", "Biển đảo", "3 ngày 2 đêm", "Phượt xe máy", "Eo Gió", "Bãi Minh Châu"],
                save_count=128,
                view_count=1450,
                published_at=datetime.now(timezone.utc),
            )
            session.add(pub)

        await session.commit()
        print("Successfully seeded Locations and Quan Lan 3D2N Itinerary into database!")


if __name__ == "__main__":
    asyncio.run(seed_quan_lan())
