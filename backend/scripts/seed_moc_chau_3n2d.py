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
# MOC CHAU 3D2N SEED DATA
#
# Itinerary basis:
# - Public 3-day/2-night Moc Chau tours departing from Hanoi.
# - Day 1 follows Hanoi - Thung Khe - central Moc Chau - Bat Cave.
# - Day 2 groups the Tan Lap tea/plum corridor with Muong Sang attractions.
# - Day 3 focuses on Ban Ang, Chimi Farm and local products before returning.
#
# Coordinate policy:
# - POIs use public Google Maps pins, OpenStreetMap/Mapcarta nodes,
#   published field coordinates, official addresses or clearly labelled
#   representative points for large areas.
# - Large attractions such as Na Ka valley and Moc Chau Island are not a
#   single small pin; coordinate_precision explains the chosen point.
# - Every location includes a Google Maps URL for manual verification.
# - Coordinates were last reviewed on 2026-07-30.
#
# Cost policy:
# - actual_cost is the estimated cost PER PERSON for this sample itinerary.
# - Costs are seed/demo values, not binding quotations.
# - Ticket, room, food and transport prices can change by day and season.
# -----------------------------------------------------------------------------

VERIFIED_AT = "2026-07-30"
NUMBER_OF_TRAVELERS = 2

LOCATIONS: dict[str, dict[str, Any]] = {'ha_noi_opera_house': {'id': '55555555-5555-4555-8555-000000000001',
                        'name': 'Nhà hát Lớn Hà Nội',
                        'address': '1 Tràng Tiền, phường Cửa Nam, Hà Nội',
                        'lat': 21.024376,
                        'lng': 105.857299,
                        'category': 'transport',
                        'province_name': 'Hà Nội',
                        'coordinate_precision': 'poi_pin',
                        'coordinate_source': 'Google Maps public place pin',
                        'google_maps_url': 'https://www.google.com/maps?q=21.024376,105.857299',
                        'verified_at': '2026-07-30'},
 'thung_khe_viewpoint': {'id': '55555555-5555-4555-8555-000000000002',
                         'name': 'Điểm ngắm thung lũng Mai Châu - đèo Thung Khe',
                         'address': 'Quốc lộ 6, khu vực Mai Châu cũ, tỉnh Phú Thọ',
                         'lat': 20.67687,
                         'lng': 105.08528,
                         'category': 'attraction',
                         'province_name': 'Phú Thọ',
                         'coordinate_precision': 'scenic_viewpoint_pin',
                         'coordinate_source': 'OpenStreetMap node 3294682392 via Mapcarta',
                         'google_maps_url': 'https://www.google.com/maps?q=20.67687,105.08528',
                         'verified_at': '2026-07-30',
                         'plus_code': '7PG7M3GP+P4'},
 'trung_tam_moc_chau': {'id': '55555555-5555-4555-8555-000000000003',
                        'name': 'Khu lưu trú trung tâm Mộc Châu',
                        'address': 'Khu trung tâm phường Mộc Châu, tỉnh Sơn La',
                        'lat': 20.84535,
                        'lng': 104.63584,
                        'category': 'hotel',
                        'province_name': 'Sơn La',
                        'coordinate_precision': 'accommodation_area_center',
                        'coordinate_source': 'OpenStreetMap city node 13731718835 via Mapcarta',
                        'google_maps_url': 'https://www.google.com/maps?q=20.84535,104.63584',
                        'verified_at': '2026-07-30',
                        'plus_code': '7PG6RJWP+48'},
 'khu_am_thuc_moc_chau': {'id': '55555555-5555-4555-8555-000000000004',
                          'name': 'Khu ẩm thực trung tâm Mộc Châu',
                          'address': 'Trục Trần Huy Liệu - Hoàng Quốc Việt, phường Mộc Châu, tỉnh Sơn La',
                          'lat': 20.8471,
                          'lng': 104.6374,
                          'category': 'restaurant',
                          'province_name': 'Sơn La',
                          'coordinate_precision': 'restaurant_area_representative_point',
                          'coordinate_source': 'Representative point in the central restaurant corridor',
                          'google_maps_url': 'https://www.google.com/maps?q=20.8471,104.6374',
                          'verified_at': '2026-07-30'},
 'quang_truong_8_5': {'id': '55555555-5555-4555-8555-000000000005',
                      'name': 'Quảng trường 8-5 Mộc Châu',
                      'address': 'Khu trung tâm Mộc Châu, tỉnh Sơn La',
                      'lat': 20.86207,
                      'lng': 104.60228,
                      'category': 'attraction',
                      'province_name': 'Sơn La',
                      'coordinate_precision': 'square_pin',
                      'coordinate_source': 'OpenStreetMap node 10295216667 via Mapcarta',
                      'google_maps_url': 'https://www.google.com/maps?q=20.86207,104.60228',
                      'verified_at': '2026-07-30',
                      'plus_code': '7PG6VJ62+RW'},
 'hang_doi': {'id': '55555555-5555-4555-8555-000000000006',
              'name': 'Hang Dơi - Động Sơn Mộc Hương',
              'address': 'Quốc lộ 6, phường Mộc Châu, tỉnh Sơn La',
              'lat': 20.849333,
              'lng': 104.639,
              'category': 'attraction',
              'province_name': 'Sơn La',
              'coordinate_precision': 'cave_entrance',
              'coordinate_source': "Published field coordinate 20°50.96'N, 104°38.34'E",
              'google_maps_url': 'https://www.google.com/maps?q=20.849333,104.639',
              'verified_at': '2026-07-30'},
 'rung_thong_ban_ang': {'id': '55555555-5555-4555-8555-000000000007',
                        'name': 'Rừng thông Bản Áng',
                        'address': 'Bản Áng, khu vực Đông Sang, Mộc Châu, Sơn La',
                        'lat': 20.82815,
                        'lng': 104.62655,
                        'category': 'attraction',
                        'province_name': 'Sơn La',
                        'coordinate_precision': 'park_entrance_representative_point',
                        'coordinate_source': 'Representative point derived from the mapped Pine Forest '
                                             'beside Chimi Farm',
                        'google_maps_url': 'https://www.google.com/maps?q=20.82815,104.62655',
                        'verified_at': '2026-07-30'},
 'chimi_farm': {'id': '55555555-5555-4555-8555-000000000008',
                'name': 'Chimi Farm Bản Áng',
                'address': '1 Chimi Bản Áng, Mộc Châu, Sơn La',
                'lat': 20.83306,
                'lng': 104.62647,
                'category': 'attraction',
                'province_name': 'Sơn La',
                'coordinate_precision': 'poi_pin',
                'coordinate_source': 'OpenStreetMap node 6403815785 via Mapcarta',
                'google_maps_url': 'https://www.google.com/maps?q=20.83306,104.62647',
                'verified_at': '2026-07-30',
                'plus_code': '7PG6RJMG+6H'},
 'thac_dai_yem': {'id': '55555555-5555-4555-8555-000000000009',
                  'name': 'Thác Dải Yếm',
                  'address': 'Khu vực Mường Sang, Mộc Châu, Sơn La',
                  'lat': 20.81798,
                  'lng': 104.59169,
                  'category': 'attraction',
                  'province_name': 'Sơn La',
                  'coordinate_precision': 'waterfall_pin',
                  'coordinate_source': 'OpenStreetMap node 4958586922 via Mapcarta',
                  'google_maps_url': 'https://www.google.com/maps?q=20.81798,104.59169',
                  'verified_at': '2026-07-30',
                  'plus_code': '7PG6RH9R+5M'},
 'moc_chau_island': {'id': '55555555-5555-4555-8555-000000000010',
                     'name': 'Mộc Châu Island - Cầu kính Bạch Long',
                     'address': 'Tổ dân phố Na Lun, khu vực Mường Sang, Mộc Châu, Sơn La',
                     'lat': 20.8183,
                     'lng': 104.5918,
                     'category': 'attraction',
                     'province_name': 'Sơn La',
                     'coordinate_precision': 'resort_area_representative_point',
                     'coordinate_source': 'Official address combined with mapped Mường Sang representative '
                                          'point',
                     'google_maps_url': 'https://www.google.com/maps?q=20.8183,104.5918',
                     'verified_at': '2026-07-30',
                     'plus_code': '7PG6RH9R+8P'},
 'doi_che_trai_tim': {'id': '55555555-5555-4555-8555-000000000011',
                      'name': 'Đồi chè Trái Tim Mộc Châu',
                      'address': 'Khu đồi chè Tân Lập, Mộc Châu, Sơn La',
                      'lat': 20.88721,
                      'lng': 104.6834,
                      'category': 'attraction',
                      'province_name': 'Sơn La',
                      'coordinate_precision': 'scenic_viewpoint_pin',
                      'coordinate_source': 'OpenStreetMap node 7037505886 via Mapcarta',
                      'google_maps_url': 'https://www.google.com/maps?q=20.88721,104.6834',
                      'verified_at': '2026-07-30',
                      'plus_code': '7PG6VMPM+V9'},
 'nong_truong_moc_chau': {'id': '55555555-5555-4555-8555-000000000012',
                          'name': 'Khu Nông trường Mộc Châu',
                          'address': 'Phường Thảo Nguyên, Mộc Châu, Sơn La',
                          'lat': 20.8371,
                          'lng': 104.6826,
                          'category': 'attraction',
                          'province_name': 'Sơn La',
                          'coordinate_precision': 'locality_center',
                          'coordinate_source': 'OpenStreetMap node 4764313819 via Mapcarta',
                          'google_maps_url': 'https://www.google.com/maps?q=20.8371,104.6826',
                          'verified_at': '2026-07-30',
                          'plus_code': '7PG6RMPM+V2'},
 'thung_lung_man_na_ka': {'id': '55555555-5555-4555-8555-000000000013',
                          'name': 'Thung lũng mận Nà Ka',
                          'address': 'Tỉnh lộ 104, khu vực Tân Lập, Mộc Châu, Sơn La',
                          'lat': 20.9564,
                          'lng': 104.6497,
                          'category': 'attraction',
                          'province_name': 'Sơn La',
                          'coordinate_precision': 'valley_entrance_representative_point',
                          'coordinate_source': 'Public tourism address on Provincial Road 104; '
                                               'representative valley access point',
                          'google_maps_url': 'https://www.google.com/maps?q=20.9564,104.6497',
                          'verified_at': '2026-07-30'}}


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
    """Build an activity and keep its coordinates synchronized with LOCATIONS."""
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


MOC_CHAU_SNAPSHOT: dict[str, Any] = {
    "title": "Lịch trình Mộc Châu 3 ngày 2 đêm chi tiết từ Hà Nội",
    "destination": "Mộc Châu, Sơn La",
    "duration_days": 3,
    "traveler_count": NUMBER_OF_TRAVELERS,
    "actual_cost_per_person": 4_230_000,
    "actual_total_cost": 8_460_000,
    "overall_rating": 4.8,
    "coordinate_verified_at": VERIFIED_AT,
    "cost_note": (
        "Chi phí là mức seed tham khảo theo người, không phải báo giá cố định. "
        "Vé Cầu kính Bạch Long trong lịch trình dùng mức người lớn ngày thường "
        "550.000 đồng; cuối tuần, lễ, combo trò chơi, giá phòng và dịch vụ khác "
        "có thể làm tổng ngân sách thay đổi."
    ),
    "budget_breakdown_per_person": {'transport': 980000,
 'lodging': 650000,
 'food': 1320000,
 'tours_and_tickets': 1000000,
 'shopping_and_miscellaneous': 280000,
 'total': 4230000},
    "days": [
        {
            "day_number": 1,
            "title": 'Hà Nội – đèo Thung Khe – trung tâm Mộc Châu – Hang Dơi',
            "activities": [
                build_activity(
                    location_key='ha_noi_opera_house',
                    start_time='05:30',
                    end_time='06:00',
                    title='Tập trung và ăn sáng nhẹ tại Nhà hát Lớn Hà Nội',
                    activity_type='meal',
                    actual_cost=50000,
                    rating=4.7,
                    author_verdict='recommended',
                    best_time='Có mặt trước giờ xe chạy 15 phút',
                    next_traveler_note='Mang theo áo khoác mỏng và thuốc chống say xe; không nên ăn quá no trước khi đi đường đèo.',
                ),
                build_activity(
                    location_key='trung_tam_moc_chau',
                    start_time='06:00',
                    end_time='10:45',
                    title='Limousine Hà Nội – Mộc Châu theo Quốc lộ 6',
                    activity_type='transport',
                    actual_cost=300000,
                    rating=4.8,
                    author_verdict='must_go',
                    best_time='Khởi hành khoảng 06:00',
                    next_traveler_note='Thời gian thực tế phụ thuộc giao thông Hà Nội và sương mù trên Quốc lộ 6; nên đặt ghế trước 1-2 ngày.',
                ),
                build_activity(
                    location_key='thung_khe_viewpoint',
                    start_time='08:45',
                    end_time='09:20',
                    title='Dừng ngắm thung lũng Mai Châu tại đèo Thung Khe',
                    activity_type='attraction',
                    actual_cost=50000,
                    rating=4.8,
                    author_verdict='recommended',
                    best_time='Buổi sáng khi trời quang',
                    next_traveler_note='Điểm dừng nằm ven đèo; chỉ đứng trong khu an toàn và không bước sát mép đường. Chi phí gồm đồ uống hoặc đồ ăn nhẹ.',
                ),
                build_activity(
                    location_key='khu_am_thuc_moc_chau',
                    start_time='11:00',
                    end_time='12:15',
                    title='Ăn trưa đặc sản bê chao và cá suối',
                    activity_type='meal',
                    actual_cost=180000,
                    rating=4.8,
                    author_verdict='must_go',
                    best_time='Ngay sau khi tới Mộc Châu',
                    next_traveler_note='Hỏi rõ giá theo đĩa hoặc theo cân; gọi lượng vừa đủ vì khẩu phần ở quán đặc sản thường khá lớn.',
                ),
                build_activity(
                    location_key='trung_tam_moc_chau',
                    start_time='12:30',
                    end_time='13:15',
                    title='Nhận phòng khách sạn trung tâm Mộc Châu',
                    activity_type='attraction',
                    actual_cost=650000,
                    rating=4.8,
                    author_verdict='must_go',
                    best_time='Chọn nơi gần Quốc lộ 6 hoặc khu trung tâm',
                    next_traveler_note='Chi phí tính theo người cho 2 đêm, giả định 2 người ở chung phòng. Ưu tiên nơi có chỗ gửi hành lý ngày cuối.',
                ),
                build_activity(
                    location_key='hang_doi',
                    start_time='14:00',
                    end_time='14:15',
                    title='Di chuyển từ khách sạn tới Hang Dơi',
                    activity_type='transport',
                    actual_cost=50000,
                    rating=4.6,
                    author_verdict='recommended',
                    best_time='Đi taxi hoặc xe điện nếu không quen đường',
                    next_traveler_note='Hang nằm gần trục Quốc lộ 6 nhưng lối lên có nhiều bậc; tránh tự đỗ xe ở vị trí cản trở giao thông.',
                ),
                build_activity(
                    location_key='hang_doi',
                    start_time='14:15',
                    end_time='16:00',
                    title='Khám phá Hang Dơi – Động Sơn Mộc Hương',
                    activity_type='attraction',
                    actual_cost=30000,
                    rating=4.6,
                    author_verdict='recommended',
                    best_time='Đầu giờ chiều, khi còn đủ ánh sáng',
                    next_traveler_note='Mang giày bám tốt, đi chậm trên bậc đá và không chạm vào nhũ đá. Vé trong file là mức seed tham khảo.',
                ),
                build_activity(
                    location_key='quang_truong_8_5',
                    start_time='16:20',
                    end_time='17:40',
                    title='Dạo Quảng trường 8-5 và khu trung tâm Mộc Châu',
                    activity_type='attraction',
                    actual_cost=0,
                    rating=4.5,
                    author_verdict='recommended',
                    best_time='Chiều mát',
                    next_traveler_note='Đây là điểm nghỉ nhẹ, không nên xếp hoạt động quá dày ngay ngày đầu sau hành trình dài.',
                ),
                build_activity(
                    location_key='khu_am_thuc_moc_chau',
                    start_time='18:30',
                    end_time='20:00',
                    title='Ăn tối lẩu sữa hoặc cá hồi Mộc Châu',
                    activity_type='meal',
                    actual_cost=250000,
                    rating=4.8,
                    author_verdict='must_go',
                    best_time='Buổi tối se lạnh',
                    next_traveler_note='Nếu gọi cá hồi hoặc cá tầm, cần hỏi rõ trọng lượng trước khi chế biến và kiểm tra giá trong thực đơn.',
                ),
                build_activity(
                    location_key='quang_truong_8_5',
                    start_time='20:00',
                    end_time='21:15',
                    title='Dạo phố tối và mua đồ ăn nhẹ',
                    activity_type='attraction',
                    actual_cost=80000,
                    rating=4.5,
                    author_verdict='recommended',
                    best_time='Buổi tối cuối tuần',
                    next_traveler_note='Giữ tiền mặt nhỏ để mua đồ ăn; không mặc định chợ đêm hoạt động đầy đủ vào mọi ngày trong tuần.',
                ),
            ],
        },
        {
            "day_number": 2,
            "title": 'Đồi chè Trái Tim – Nà Ka – Thác Dải Yếm – Cầu kính Bạch Long',
            "activities": [
                build_activity(
                    location_key='khu_am_thuc_moc_chau',
                    start_time='06:30',
                    end_time='07:15',
                    title='Ăn sáng phở hoặc bánh cuốn Mộc Châu',
                    activity_type='meal',
                    actual_cost=50000,
                    rating=4.6,
                    author_verdict='recommended',
                    best_time='Ăn sớm trước khi đi Tân Lập',
                    next_traveler_note='Chuẩn bị nước uống và áo chống nắng; tuyến đồi chè và Nà Ka có ít điểm nghỉ hơn khu trung tâm.',
                ),
                build_activity(
                    location_key='doi_che_trai_tim',
                    start_time='07:15',
                    end_time='08:00',
                    title='Di chuyển tới Đồi chè Trái Tim',
                    activity_type='transport',
                    actual_cost=80000,
                    rating=4.7,
                    author_verdict='must_go',
                    best_time='Đi sớm để tránh đông',
                    next_traveler_note='Đường qua khu nông trường có xe tải và xe nông nghiệp; người ít kinh nghiệm không nên tự lái xe máy khi sương dày.',
                ),
                build_activity(
                    location_key='doi_che_trai_tim',
                    start_time='08:00',
                    end_time='09:15',
                    title='Check-in Đồi chè Trái Tim Mộc Châu',
                    activity_type='attraction',
                    actual_cost=30000,
                    rating=4.9,
                    author_verdict='must_go',
                    best_time='07:30-09:30 khi ánh sáng dịu',
                    next_traveler_note='Không bước vào luống chè gây hư hại cây; chỉ đi theo lối có sẵn và xin phép nếu chụp gần người lao động.',
                ),
                build_activity(
                    location_key='thung_lung_man_na_ka',
                    start_time='09:15',
                    end_time='09:55',
                    title='Di chuyển từ đồi chè tới Thung lũng mận Nà Ka',
                    activity_type='transport',
                    actual_cost=80000,
                    rating=4.6,
                    author_verdict='recommended',
                    best_time='Đi ban ngày, tránh mưa lớn',
                    next_traveler_note='Đoạn cuối có thể hẹp và trơn. Tọa độ trong file là điểm vào đại diện vì thung lũng gồm nhiều vườn tư nhân.',
                ),
                build_activity(
                    location_key='thung_lung_man_na_ka',
                    start_time='10:00',
                    end_time='11:30',
                    title='Tham quan vườn mận Nà Ka và trải nghiệm hái quả theo mùa',
                    activity_type='attraction',
                    actual_cost=80000,
                    rating=4.9,
                    author_verdict='must_go',
                    best_time='Hoa mận: mùa đông-xuân; mận chín: khoảng tháng 5-7',
                    next_traveler_note='Giá vé và giá quả tùy từng vườn. Không hái quả ngoài khu đã mua vé và không bẻ cành để chụp ảnh.',
                ),
                build_activity(
                    location_key='khu_am_thuc_moc_chau',
                    start_time='12:15',
                    end_time='13:15',
                    title='Ăn trưa tại khu trung tâm Mộc Châu',
                    activity_type='meal',
                    actual_cost=180000,
                    rating=4.7,
                    author_verdict='recommended',
                    best_time='Trở về ăn trước khi đi Mường Sang',
                    next_traveler_note='Nên chọn bữa trưa vừa phải vì buổi chiều có hoạt động đi bộ trên thác và cầu kính.',
                ),
                build_activity(
                    location_key='thac_dai_yem',
                    start_time='13:15',
                    end_time='13:45',
                    title='Di chuyển tới khu Thác Dải Yếm',
                    activity_type='transport',
                    actual_cost=70000,
                    rating=4.7,
                    author_verdict='must_go',
                    best_time='Đầu giờ chiều',
                    next_traveler_note='Đường vào khu Mường Sang có nhiều điểm du lịch gần nhau; nên thống nhất điểm đón với tài xế.',
                ),
                build_activity(
                    location_key='thac_dai_yem',
                    start_time='13:45',
                    end_time='15:15',
                    title='Tham quan Thác Dải Yếm và khu cảnh quan',
                    activity_type='attraction',
                    actual_cost=80000,
                    rating=4.8,
                    author_verdict='must_go',
                    best_time='Mùa nước nhiều, trời khô ráo',
                    next_traveler_note='Không xuống đá sát chân thác khi nước lớn. Mức phí trong file là dự toán gồm vé và dịch vụ cơ bản.',
                ),
                build_activity(
                    location_key='moc_chau_island',
                    start_time='15:15',
                    end_time='15:35',
                    title='Di chuyển sang Mộc Châu Island',
                    activity_type='transport',
                    actual_cost=50000,
                    rating=4.6,
                    author_verdict='recommended',
                    best_time='Đi ngay sau Thác Dải Yếm',
                    next_traveler_note='Hai điểm cùng khu vực Mường Sang nhưng cổng vào và tuyến xe có thể thay đổi; hãy đi theo biển chỉ dẫn tại chỗ.',
                ),
                build_activity(
                    location_key='moc_chau_island',
                    start_time='15:35',
                    end_time='17:45',
                    title='Chinh phục Cầu kính Bạch Long và tham quan Mộc Châu Island',
                    activity_type='attraction',
                    actual_cost=550000,
                    rating=4.9,
                    author_verdict='must_go',
                    best_time='Ngày thường, trước giờ đóng cửa',
                    next_traveler_note='Vé 550.000 đồng là mức người lớn ngày thường được công bố; cuối tuần hoặc lễ có thể cao hơn. Người sợ độ cao, chóng mặt hoặc bệnh tim nên cân nhắc.',
                ),
                build_activity(
                    location_key='khu_am_thuc_moc_chau',
                    start_time='18:30',
                    end_time='20:00',
                    title='Ăn tối BBQ hoặc lẩu gà đen',
                    activity_type='meal',
                    actual_cost=280000,
                    rating=4.8,
                    author_verdict='must_go',
                    best_time='Sau ngày tham quan dài',
                    next_traveler_note='Đặt bàn sớm vào cuối tuần; hạn chế uống rượu nếu hôm sau còn di chuyển đường đèo.',
                ),
            ],
        },
        {
            "day_number": 3,
            "title": 'Rừng thông Bản Áng – Chimi Farm – đặc sản Mộc Châu – Hà Nội',
            "activities": [
                build_activity(
                    location_key='khu_am_thuc_moc_chau',
                    start_time='06:45',
                    end_time='07:30',
                    title='Ăn sáng và làm thủ tục trả phòng',
                    activity_type='meal',
                    actual_cost=50000,
                    rating=4.6,
                    author_verdict='recommended',
                    best_time='Hoàn tất trước 07:30',
                    next_traveler_note='Gửi hành lý tại lễ tân và kiểm tra lại giấy tờ, sạc điện thoại trước khi đi Bản Áng.',
                ),
                build_activity(
                    location_key='rung_thong_ban_ang',
                    start_time='07:30',
                    end_time='07:50',
                    title='Di chuyển tới Rừng thông Bản Áng',
                    activity_type='transport',
                    actual_cost=50000,
                    rating=4.7,
                    author_verdict='must_go',
                    best_time='Đi sớm khi không khí mát',
                    next_traveler_note='Quãng đường ngắn nhưng có thể đông vào cuối tuần; ưu tiên taxi hoặc xe điện nếu nhóm từ 2 người.',
                ),
                build_activity(
                    location_key='rung_thong_ban_ang',
                    start_time='07:50',
                    end_time='09:20',
                    title='Đi bộ ven hồ và khám phá Rừng thông Bản Áng',
                    activity_type='attraction',
                    actual_cost=80000,
                    rating=4.8,
                    author_verdict='must_go',
                    best_time='Sáng sớm hoặc chiều muộn',
                    next_traveler_note='Không đốt lửa tự phát trong rừng thông; giữ khoảng cách với mặt hồ và tuân thủ khu vực được phép tham quan.',
                ),
                build_activity(
                    location_key='chimi_farm',
                    start_time='09:20',
                    end_time='10:40',
                    title='Tham quan Chimi Farm và trải nghiệm dâu tây theo mùa',
                    activity_type='attraction',
                    actual_cost=150000,
                    rating=4.7,
                    author_verdict='recommended',
                    best_time='Buổi sáng, mùa dâu',
                    next_traveler_note='Chi phí gồm đồ uống hoặc lượng dâu nhỏ. Giá dâu hái mang về tính riêng và thay đổi theo mùa.',
                ),
                build_activity(
                    location_key='nong_truong_moc_chau',
                    start_time='10:40',
                    end_time='11:10',
                    title='Di chuyển qua khu Nông trường Mộc Châu',
                    activity_type='transport',
                    actual_cost=0,
                    rating=4.5,
                    author_verdict='recommended',
                    best_time='Kết hợp trên đường về trung tâm',
                    next_traveler_note='Đây là điểm đại diện của vùng nông trường, không phải cổng một trang trại cụ thể; không tự ý đi vào khu sản xuất.',
                ),
                build_activity(
                    location_key='khu_am_thuc_moc_chau',
                    start_time='11:15',
                    end_time='12:15',
                    title='Ăn trưa trước khi về Hà Nội',
                    activity_type='meal',
                    actual_cost=180000,
                    rating=4.7,
                    author_verdict='recommended',
                    best_time='Ăn sớm để khởi hành đúng giờ',
                    next_traveler_note='Ưu tiên món dễ tiêu, hạn chế đồ sống hoặc quá nhiều dầu mỡ trước hành trình dài.',
                ),
                build_activity(
                    location_key='nong_truong_moc_chau',
                    start_time='12:15',
                    end_time='13:00',
                    title='Mua sữa, chè, mận và đặc sản làm quà',
                    activity_type='shopping',
                    actual_cost=200000,
                    rating=4.7,
                    author_verdict='recommended',
                    best_time='Mua tại cửa hàng niêm yết giá',
                    next_traveler_note='Kiểm tra hạn sử dụng, điều kiện bảo quản và hóa đơn; sản phẩm sữa lạnh cần túi giữ nhiệt.',
                ),
                build_activity(
                    location_key='ha_noi_opera_house',
                    start_time='13:00',
                    end_time='18:00',
                    title='Limousine Mộc Châu – Hà Nội',
                    activity_type='transport',
                    actual_cost=300000,
                    rating=4.8,
                    author_verdict='must_go',
                    best_time='Khởi hành đầu giờ chiều',
                    next_traveler_note='Dự phòng thêm 30-60 phút do giao thông cửa ngõ Hà Nội và sương mù trên Quốc lộ 6.',
                ),
                build_activity(
                    location_key='thung_khe_viewpoint',
                    start_time='15:00',
                    end_time='15:25',
                    title='Nghỉ dọc đường tại khu vực đèo Thung Khe',
                    activity_type='meal',
                    actual_cost=50000,
                    rating=4.5,
                    author_verdict='recommended',
                    best_time='Nghỉ ngắn 20-25 phút',
                    next_traveler_note='Không tự ý băng qua đường để chụp ảnh; giữ vé hoặc thông tin xe để tránh lên nhầm chuyến.',
                ),
            ],
        },
    ],
    "review": {
        "best_places": [
            "Đồi chè Trái Tim Mộc Châu",
            "Thung lũng mận Nà Ka",
            "Thác Dải Yếm",
            "Cầu kính Bạch Long",
            "Rừng thông Bản Áng",
        ],
        "best_foods": [
            "Bê chao Mộc Châu",
            "Cá suối",
            "Lẩu sữa",
            "Cá hồi Mộc Châu",
            "Sữa chua và sản phẩm từ sữa",
        ],
        "tips": (
            "Kiểm tra thời tiết trước khi đi Quốc lộ 6; không tự lái xe máy khi sương dày "
            "hoặc thiếu kinh nghiệm đường đèo; đi Nà Ka đúng mùa hoa hoặc mùa mận; "
            "đặt vé Cầu kính Bạch Long theo đúng ngày sử dụng; tôn trọng vườn chè, "
            "vườn mận và khu sản xuất của người dân."
        ),
    },
    "data_sources": {
        "itinerary_basis": [
            "https://dulichdaiphong.vn/du-lich-moc-chau-3-ngay-2-dem/",
            "https://intour.vn/to-chuc-teambuilding/tour-teambuilding-moc-chau-3-ngay-2-dem.html",
            "https://vietuniquetours.com/vi/tour/du-lich-moc-chau-3-ngay-2-dem",
            "https://mocchautour.vn/vi/lo-trinh-du-lich",
        ],
        "ticket_and_operation_basis": [
            "https://www.mocchauisland.com/vi/orderTicket?ticket_type_id=8",
            "https://www.mocchauisland.com/vi",
            "https://www.vietnamairlines.com/vn/vi/useful-information/travel-guide/cau-kinh-moc-chau",
        ],
        "coordinate_basis": [
            "OpenStreetMap/Mapcarta POI nodes",
            "Published field coordinate for Hang Doi",
            "Official Moc Chau tourism addresses",
            "Representative access points for large valleys and resort areas",
        ],
        "verification_date": VERIFIED_AT,
    },
}


def validate_seed_data() -> int:
    """Validate IDs, coordinates, activities, day order and costs."""
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

    expected_day_numbers = list(range(1, MOC_CHAU_SNAPSHOT["duration_days"] + 1))
    actual_day_numbers = [day["day_number"] for day in MOC_CHAU_SNAPSHOT["days"]]
    if actual_day_numbers != expected_day_numbers:
        raise ValueError(
            f"Day numbers must be sequential: expected={expected_day_numbers}, "
            f"actual={actual_day_numbers}"
        )

    total_cost = 0
    activity_count = 0
    for day in MOC_CHAU_SNAPSHOT["days"]:
        previous_start_minutes = -1

        for activity in day["activities"]:
            activity_count += 1
            start_value = datetime.strptime(activity["start_time"], "%H:%M")
            datetime.strptime(activity["end_time"], "%H:%M")
            start_minutes = start_value.hour * 60 + start_value.minute

            if start_minutes < previous_start_minutes:
                raise ValueError(
                    f"Activities are not ordered by start time on day {day['day_number']}: "
                    f"{activity['title']}"
                )
            previous_start_minutes = start_minutes

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

    expected_per_person = MOC_CHAU_SNAPSHOT["actual_cost_per_person"]
    if total_cost != expected_per_person:
        raise ValueError(
            f"Cost mismatch: activities={total_cost:,}, snapshot={expected_per_person:,}"
        )

    expected_total = expected_per_person * NUMBER_OF_TRAVELERS
    if MOC_CHAU_SNAPSHOT["actual_total_cost"] != expected_total:
        raise ValueError(
            "actual_total_cost must equal actual_cost_per_person * traveler_count"
        )

    budget_total = sum(
        value
        for key, value in MOC_CHAU_SNAPSHOT["budget_breakdown_per_person"].items()
        if key != "total"
    )
    if budget_total != MOC_CHAU_SNAPSHOT["budget_breakdown_per_person"]["total"]:
        raise ValueError("Budget breakdown does not add up")

    if budget_total != expected_per_person:
        raise ValueError("Budget breakdown total differs from actual_cost_per_person")

    if activity_count < 20:
        raise ValueError("The itinerary is unexpectedly short")

    return total_cost


async def seed_moc_chau() -> None:
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
        author_email = "guide.mocchau@smarttravel.vn"
        stmt_user = select(User).where(User.email == author_email)
        res_user = await session.execute(stmt_user)
        user = res_user.scalar_one_or_none()

        if not user:
            print(f"No user '{author_email}' found. Creating seed author...")
            user = User(
                id=uuid.uuid4(),
                username="guide-mocchau",
                email=author_email,
                full_name="Lò Thị Ban (Hướng dẫn viên Mộc Châu)",
                password_hash="seed-only-account-not-for-login",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

        # 3. Create or update the public trip publication.
        slug = "lich-trinh-moc-chau-3-ngay-2-dem-chi-tiet"
        stmt_pub = select(PublicTripPublication).where(
            PublicTripPublication.slug == slug
        )
        res_pub = await session.execute(stmt_pub)
        existing = res_pub.scalar_one_or_none()

        publication_values = {
            "title": MOC_CHAU_SNAPSHOT["title"],
            "summary": (
                "Hành trình Mộc Châu 3 ngày 2 đêm từ Hà Nội cho 2 người: dừng tại đèo "
                "Thung Khe, khám phá Hang Dơi, đồi chè Trái Tim, thung lũng mận Nà Ka, "
                "Thác Dải Yếm, Cầu kính Bạch Long, Rừng thông Bản Áng và Chimi Farm "
                "với ngân sách khoảng 4,23 triệu đồng/người."
            ),
            "destination": "Mộc Châu (Sơn La)",
            "province_name": "Sơn La",
            "duration_days": 3,
            "actual_total_cost": MOC_CHAU_SNAPSHOT["actual_total_cost"],
            "actual_cost_per_person": MOC_CHAU_SNAPSHOT["actual_cost_per_person"],
            "overall_rating": MOC_CHAU_SNAPSHOT["overall_rating"],
            "status": "published",
            "visibility": "public",
            "moderation_status": "approved",
            "cover_image_url": (
                "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee"
                "?auto=format&fit=crop&w=1200&q=80"
            ),
            "snapshot_json": MOC_CHAU_SNAPSHOT,
            "tags": [
                "Mộc Châu",
                "Sơn La",
                "3 ngày 2 đêm",
                "Đồi chè",
                "Thung lũng mận Nà Ka",
                "Thác Dải Yếm",
                "Cầu kính Bạch Long",
                "Rừng thông Bản Áng",
                "Chimi Farm",
                "Hang Dơi",
                "Tây Bắc",
            ],
            "save_count": 194,
            "view_count": 2640,
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
        print("Successfully seeded Moc Chau 3D2N itinerary!")


if __name__ == "__main__":
    asyncio.run(seed_moc_chau())
