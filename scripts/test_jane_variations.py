import sys, os, re
sys.path.append('happyrolly_web')
from assistant_engine import PHONETIC_ALIASES

PHONETIC_ALIASES['Jane'].extend(['chê anh', 'chê-anh', 'chê in', 'xem', 'xen', 'sen', 'chenh', 'chênh'])

roster_rows = [
    {'Employee': 'Jane', 'Monday': '12:00 - 17:00', 'Tuesday': ''},
    {'Employee': 'Robert', 'Monday': '04:00 - 12:00', 'Tuesday': ''},
    {'Employee': 'Viet', 'Monday': '', 'Tuesday': '04:00 - 12:00'},
]

def parse_day_off(msg):
    low = re.sub(r'\bnghĩ\b', 'nghỉ', msg.lower())
    remove_keywords = [
        "nghỉ", "off", "bỏ ca", "xóa ca", "cho nghỉ", "cho off", "bỏ", "xóa", 
        "hủy ca", "hủy", "không làm", "hông làm", "ko làm", "không đi làm", 
        "nghỉ làm", "khỏi làm"
    ]
    return any(k in low for k in remove_keywords)

test_phrases = [
    "Cho Jane nghỉ ngày thứ Hai đi",
    "cho chê anh nghĩ ngày thứ hai đi",
    "Cho xem nghỉ ngày thứ hai đi",
    "Thứ Hai cho Jane off đi",
    "Xóa ca thứ Hai của Jane",
    "Jane thứ 2 không làm",
    "thứ 2 này cho Jane nghỉ",
    "thứ Hai khỏi xếp Jane làm",
    "Jane thứ 2 không đi làm nữa",
]

for p in test_phrases:
    print(f"'{p}' -> Is day off? {parse_day_off(p)}")
