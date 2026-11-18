import os
import sys
import json
import time

sys.path.append(os.path.abspath('happyrolly_web'))
from database.db_manager import HappyRollyDB
from assistant_engine import process_assistant_chat

db = HappyRollyDB()
roster_rows = db.load_finalized_roster("2026-11-09") or []

test_cases = [
    # 1. Contact info queries
    ("Cho chị xin số điện thoại của Ainsley", "0479122444"),
    ("Shaelyn có email là gì", "shaelyndean@gmail.com"),
    ("Số điện thoại của Shaelyn", "0466894554"),
    ("Địa chỉ của Ainsley ở đâu", "8 Knapton Ave"),
    ("Địa chỉ của Shaelyn ở đâu em", "28 Moore Mews"),
    ("Aimi sinh ngày mấy", "10/11/2006"),
    ("Robert bắt đầu vào làm từ khi nào", "22/01/2024"),
    
    # 2. Roles and positions
    ("Ai là thợ làm bánh", "Robert"),
    ("Ai là thợ phụ bánh", "Aroha"),
    ("Aroha làm vị trí gì", "baker assitant"),
    ("Robert giữ chức vụ gì", "baker"),
    
    # 3. Unavailability & Restrictions
    ("Jude có bận gì không", "restriction"),
    ("Thứ 4 Jude có làm được không", "restriction/bận"),
    ("Violet có rảnh thứ Hai không", "Violet"),
    ("Ai bận ngày thứ Tư", "thứ Tư"),
    
    # 4. Schedule and hours
    ("Thứ 2 ai đi làm", "tiệm mình có"),
    ("Tuần này ai làm nhiều giờ nhất", "nhiều giờ nhất"),
    ("Ainsley tuần này làm mấy tiếng", "tiếng"),
    
    # 5. Holidays
    ("Sắp tới có ngày lễ gì không", "Victoria"),
    
    # 6. Roster actions (Aimi phonetic matching, shift move, etc.)
    ("em có thể cho ai mì thêm một ca nữa vào ngày thứ hai 7 giờ tới 12:00 trưa không", "Xong chị ơi! Ca thứ Hai của Aimi"),
    ("dời ca của anatasia từ ngày thứ hai sang ngày thứ tư", "Xong chị ơi! Joy dời ca thứ Hai"),
]

print("=== STARTING FULL SUITE TEST ===")
passed = 0
for msg, expected in test_cases:
    t0 = time.time()
    res = process_assistant_chat(
        user_message=msg,
        roster_rows=roster_rows,
        db=db,
        session_id="test_suite_session",
    )
    dt = time.time() - t0
    reply = res.get("reply", "")
    ok = expected.lower() in reply.lower()
    if ok:
        passed += 1
        print(f"✅ [{dt*1000:.1f}ms] Q: '{msg}'\n   -> A: {reply}")
    else:
        print(f"❌ [{dt*1000:.1f}ms] Q: '{msg}'\n   Expected '{expected}' but got: '{reply}'")

print(f"\nResult: {passed}/{len(test_cases)} tests passed!")
