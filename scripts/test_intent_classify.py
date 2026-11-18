import os
import sys
import re

sys.path.append(os.path.abspath('happyrolly_web'))
from database.db_manager import HappyRollyDB

db = HappyRollyDB()

# Let's test intent detection logic
def classify_intent_test(msg: str):
    low = msg.lower().strip()
    
    # 1. Contact Info Query
    contact_keywords = [
        "số điện thoại", "sđt", "so dien thoai", "sdt", "số phone", "phone", "mobile", 
        "điện thoại", "alo", "gọi", "email", "mail", "thư điện tử", "địa chỉ", "dia chi", 
        "ở đâu", "nhà ở", "nhà của", "sinh nhật", "ngày sinh", "sinh năm", "năm sinh", 
        "sinh ngày", "ngày vào làm", "bắt đầu làm", "vào làm từ", "vào tiệm", "thông tin cá nhân", 
        "thông tin của", "profile của", "hồ sơ của", "profile"
    ]
    if any(k in low for k in contact_keywords):
        return "query_employee_contact"

    # 2. Role / Position Query
    role_keywords = [
        "thợ bánh", "thợ làm bánh", "baker", "phụ bánh", "baker assistant", "baker assitant", 
        "bán hàng", "service staff", "chức vụ", "làm chức vụ", "làm vị trí gì", "vị trí gì",
        "ai là thợ", "ai phụ bánh", "ai làm bánh", "ai bán hàng"
    ]
    if any(k in low for k in role_keywords) and not any(k in low for k in ["đổi", "dời", "chuyển", "thêm ca", "xóa ca"]):
        return "query_employee_role"

    # 3. Restriction / Unavailability Query
    restriction_keywords = [
        "restriction", "unavailability", "bận", "rảnh", "nghỉ phép", "xin nghỉ", 
        "có làm được không", "có đi làm được không", "có rảnh không", "có bận không", 
        "có available không", "unavailable", "available", "lịch bận", "vướng lịch", "vướng"
    ]
    if any(k in low for k in restriction_keywords) and not any(k in low for k in ["cho nghỉ", "xóa ca", "bỏ ca", "thêm ca"]):
        return "query_unavailability_restriction"

    # 4. Holidays
    holiday_keywords = [
        "ngày lễ", "nghỉ lễ", "public holiday", "school holiday", "lễ sắp tới", 
        "nghỉ hè", "nghỉ thu", "lễ tết", "giáng sinh", "christmas", "boxing day", "tết tây"
    ]
    if any(k in low for k in holiday_keywords):
        return "query_holidays"

    # 5. Hours & Schedule Queries
    schedule_keywords = [
        "ai đi làm", "ai làm", "những ai làm", "ai có ca", "có ai làm", "mấy người làm", 
        "danh sách đi làm", "tổng giờ", "bao nhiêu tiếng", "mấy tiếng", "nhiều giờ nhất", 
        "ít giờ nhất", "bao nhiêu ca", "mấy ca", "lịch làm của", "lịch làm việc của", 
        "tuần này làm", "hôm nay ai làm"
    ]
    if any(k in low for k in schedule_keywords):
        return "query_shift_schedule_and_hours"

    return "roster_modification_or_other"

test_queries = [
    "Cho chị xin số điện thoại của Ainsley",
    "Shaelyn có email là gì",
    "Địa chỉ của Shaelyn ở đâu",
    "Ai là thợ làm bánh",
    "Aroha làm vị trí gì",
    "Jude có bận gì không",
    "Thứ 4 Jude có làm được không",
    "Ai bận ngày thứ Tư",
    "Thứ 2 ai đi làm",
    "Tuần này ai làm nhiều giờ nhất",
    "Ainsley tuần này làm mấy tiếng",
    "Sắp tới có ngày lễ gì không",
    "em có thể cho ai mì thêm một ca nữa vào ngày thứ hai 7 giờ tới 12:00 trưa không",
    "dời ca của anatasia từ ngày thứ hai sang ngày thứ tư",
    "đổi ca của Robert sang cho Viet vào thứ Ba",
    "cho Elizabeth nghỉ ngày thứ 7"
]

for q in test_queries:
    print(f"[{classify_intent_test(q):32}] <- '{q}'")
