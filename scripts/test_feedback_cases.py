import os
import sys

sys.path.append(os.path.abspath('happyrolly_web'))
from database.db_manager import HappyRollyDB
from assistant_engine import process_assistant_chat

db = HappyRollyDB()
roster_rows = [
    {'Employee': 'Jane', 'Monday': '12:00pm-5:00pm', 'Tuesday': '', 'Wednesday': '12:30pm-5:30pm'},
    {'Employee': 'Robert', 'Monday': '4:00am-12:00pm', 'Tuesday': ''},
]

feedback_tests = [
    ("Cho Jane nghỉ ngày thứ Hai đi", "Xong chị ơi! thứ Hai này Joy cho Jane nghỉ"),
    ("cho chê anh nghĩ ngày thứ hai đi", "Xong chị ơi! thứ Hai này Joy cho Jane nghỉ"),
    ("Cho xem nghỉ ngày thứ hai đi", "Xong chị ơi! thứ Hai này Joy cho Jane nghỉ"),
    ("Thứ Hai cho Jane off đi", "Xong chị ơi! thứ Hai này Joy cho Jane nghỉ"),
    ("chị muốn bạn Jane", "Joy nghe chị nhắc tới bạn Jane rồi nè"),
    ("ngày thứ Ba thì sao", "Joy nghe chị nhắc tới ngày thứ Ba rồi nè"),
    ("úm ba la xì bùa", "Joy chưa hiểu rõ ý chị muốn làm gì á"),
    ("hai chọi", "Joy nghe nè chị Nhi! Chị dặn Joy"),
]

print("=== TESTING USER FEEDBACK CASES ===")
passed = 0
for msg, expected in feedback_tests:
    res = process_assistant_chat(msg, roster_rows, db, session_id="test_feedback_sess")
    reply = res.get("reply", "")
    ok = expected.lower() in reply.lower()
    if ok:
        passed += 1
        print(f"✅ Q: '{msg}'\n   -> A: {reply}")
    else:
        print(f"❌ Q: '{msg}'\n   Expected: '{expected}'\n   Got: '{reply}'")

print(f"\nResult: {passed}/{len(feedback_tests)} tests passed!")
