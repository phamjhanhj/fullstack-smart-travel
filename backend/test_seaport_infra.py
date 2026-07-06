import csv
import json
import os
from datetime import datetime
import requests

# ==================== CẤU HÌNH THÔNG TIN API ====================
BASE_URL = "http://localhost:8080"  # Thay bằng URL Gateway/API thực tế của bạn
API_URL = f"{BASE_URL}/gov/other-taxes/seaport-infra/tax/inquiry/1.0"

# Header chứa token bảo mật (nếu API yêu cầu đăng nhập/chứng thực)
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": "Bearer YOUR_ACCESS_TOKEN_HERE"  # Thay bằng Access Token thực tế
}

# Tên file CSV đầu vào và đầu ra
INPUT_CSV = "DVC - Phí HTCB - Testcase - Dữ liệu test.csv"
OUTPUT_CSV = "results_inquiry.csv"

def format_date(date_str):
    if not date_str:
        return None
    # Bỏ phần giờ nếu có (ví dụ: "03/28/2020 00:00:00" -> "03/28/2020")
    date_part = date_str.split()[0].strip()
    
    # Thử các định dạng ngày khác nhau
    # Trong file của bạn: 03/28/2020 -> dạng MM/DD/YYYY
    for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(date_part, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None

def run_inquiry():
    if not os.path.exists(INPUT_CSV):
        print(f"❌ Không tìm thấy file dữ liệu đầu vào '{INPUT_CSV}'!")
        return

    test_cases = []
    
    # 1. Đọc dữ liệu từ file CSV của bạn
    print(f"📖 Đang đọc dữ liệu từ file '{INPUT_CSV}'...")
    try:
        with open(INPUT_CSV, mode="r", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            
            # Làm sạch header (loại bỏ khoảng trắng thừa nếu có)
            reader.fieldnames = [name.strip() for name in reader.fieldnames]
            
            for idx, row in enumerate(reader, 1):
                # Ánh xạ các cột từ file CSV sang format API:
                # - SO_CT -> notificationNo
                # - KYHIEU_CT -> tccDocSign
                # - NGAY_CT -> notificationDate
                # - MA_DV -> taxCode
                # - MA_DV_THUPHI -> collectorCode
                
                so_ct = row.get("SO_CT", "").strip()
                kyhieu_ct = row.get("KYHIEU_CT", "").strip()
                ngay_ct_raw = row.get("NGAY_CT", "").strip()
                ma_dv = row.get("MA_DV", "").strip()
                ma_dv_thuphi = row.get("MA_DV_THUPHI", "").strip()
                
                # Format lại ngày từ MM/DD/YYYY -> YYYY-MM-DD
                ngay_ct_formatted = format_date(ngay_ct_raw)
                
                if not so_ct or not kyhieu_ct or not ngay_ct_formatted:
                    print(f"⚠️ Dòng {idx}: Bỏ qua do thiếu thông tin bắt buộc (SO_CT: {so_ct}, KYHIEU_CT: {kyhieu_ct}, NGAY_CT: {ngay_ct_raw})")
                    continue
                
                test_cases.append({
                    "taxCode": ma_dv,
                    "collectorCode": ma_dv_thuphi,
                    "notificationNo": so_ct,
                    "notificationDate": ngay_ct_formatted,
                    "tccDocSign": kyhieu_ct,
                    "original_row": row  # Giữ lại thông tin gốc để xuất kết quả
                })
    except Exception as e:
        print(f"❌ Lỗi khi đọc file CSV: {e}")
        return

    if not test_cases:
        print("❌ Không tìm thấy bản ghi hợp lệ nào!")
        return

    print(f"🚀 Tìm thấy {len(test_cases)} case hợp lệ. Bắt đầu gọi API...")
    print("=" * 100)

    results = []
    success_count = 0

    # 2. Thực hiện gọi API tuần tự
    for idx, case in enumerate(test_cases, 1):
        print(f"[{idx}/{len(test_cases)}] Đang truy vấn Số TB: {case['notificationNo']} | Ký hiệu: {case['tccDocSign']} | Ngày: {case['notificationDate']}...")
        
        status = "FAIL"
        amount = ""
        response_msg = ""
        
        # Tạo payload đúng chuẩn spec API
        payload = {
            "taxCode": case["taxCode"],
            "collectorCode": case["collectorCode"],
            "notificationNo": case["notificationNo"],
            "notificationDate": case["notificationDate"],
            "tccDocSign": case["tccDocSign"]
        }
        
        try:
            response = requests.post(API_URL, json=payload, headers=HEADERS, timeout=10)
            
            if response.status_code == 200:
                res_json = response.json()
                
                # Check logic thành công của hệ thống (code="00" hoặc có trường data trả về)
                is_success = res_json.get("code") == "00" or res_json.get("data") is not None
                
                if is_success:
                    status = "SUCCESS"
                    success_count += 1
                    
                    data_res = res_json.get("data", {})
                    if isinstance(data_res, dict):
                        amount = data_res.get("amount", "")
                    
                    print(f"  => ✅ THÀNH CÔNG! Số tiền: {amount} VND")
                else:
                    response_msg = res_json.get("message", "Lỗi nghiệp vụ")
                    print(f"  => ❌ THẤT BẠI: {response_msg}")
            else:
                response_msg = f"HTTP {response.status_code}: {response.text}"
                print(f"  => ❌ THẤT BẠI: {response_msg}")
                
        except requests.exceptions.RequestException as e:
            response_msg = f"Lỗi kết nối: {e}"
            print(f"  => ❌ LỖI KẾT NỐI API: {e}")

        # Thêm kết quả kết hợp thông tin cũ và kết quả truy vấn mới
        result_row = {
            **case["original_row"],
            "INQUIRY_STATUS": status,
            "INQUIRY_AMOUNT": amount,
            "INQUIRY_MESSAGE": response_msg
        }
        results.append(result_row)
        print("-" * 100)

    # 3. Ghi file kết quả results_inquiry.csv
    print(f"\n💾 Đang ghi kết quả vào file '{OUTPUT_CSV}'...")
    try:
        # Lấy danh sách cột gốc từ dòng đầu tiên, cộng thêm 3 cột trạng thái mới
        original_fields = list(test_cases[0]["original_row"].keys())
        fieldnames = original_fields + ["INQUIRY_STATUS", "INQUIRY_AMOUNT", "INQUIRY_MESSAGE"]
        
        with open(OUTPUT_CSV, mode="w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
            
        print("=" * 100)
        print(f"🎉 HOÀN THÀNH!")
        print(f" - Tổng số record đã check: {len(test_cases)}")
        print(f" - Thành công (SUCCESS)   : {success_count}")
        print(f" - Thất bại (FAIL)         : {len(test_cases) - success_count}")
        print(f" - Kết quả được lưu tại   : {os.path.abspath(OUTPUT_CSV)}")
        print("=" * 100)
    except Exception as e:
        print(f"❌ Lỗi ghi file kết quả: {e}")

if __name__ == "__main__":
    run_inquiry()
