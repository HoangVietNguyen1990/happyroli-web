import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

DAYS_MAP = {
    "thứ 2": "Monday",
    "thứ hai": "Monday",
    "ngày thứ hai": "Monday",
    "t2": "Monday",
    "mon": "Monday",
    "monday": "Monday",
    "thứ 3": "Tuesday",
    "thứ ba": "Tuesday",
    "ngày thứ ba": "Tuesday",
    "t3": "Tuesday",
    "tue": "Tuesday",
    "tuesday": "Tuesday",
    "thứ 4": "Wednesday",
    "thứ tư": "Wednesday",
    "thứ bốn": "Wednesday",
    "ngày thứ tư": "Wednesday",
    "t4": "Wednesday",
    "wed": "Wednesday",
    "wednesday": "Wednesday",
    "thứ 5": "Thursday",
    "thứ năm": "Thursday",
    "ngày thứ năm": "Thursday",
    "t5": "Thursday",
    "thu": "Thursday",
    "thursday": "Thursday",
    "thứ 6": "Friday",
    "thứ sáu": "Friday",
    "ngày thứ sáu": "Friday",
    "t6": "Friday",
    "fri": "Friday",
    "friday": "Friday",
    "thứ 7": "Saturday",
    "thứ bảy": "Saturday",
    "ngày thứ bảy": "Saturday",
    "t7": "Saturday",
    "sat": "Saturday",
    "saturday": "Saturday",
    "chủ nhật": "Sunday",
    "chu nhat": "Sunday",
    "ngày chủ nhật": "Sunday",
    "cn": "Sunday",
    "sun": "Sunday",
    "sunday": "Sunday",
}

DAYS_VI_NAMES = {
    "Monday": "thứ Hai",
    "Tuesday": "thứ Ba",
    "Wednesday": "thứ Tư",
    "Thursday": "thứ Năm",
    "Friday": "thứ Sáu",
    "Saturday": "thứ Bảy",
    "Sunday": "Chủ Nhật",
}

# Phonetic & speech recognition dictionary for Brumby's Pakenham staff
PHONETIC_ALIASES = {
    "Jane": [
        "jane", "chan", "chane", "trên", "chen", "zen", "dzen", "jen",
        "chên", "trang", "tran", "chiên", "dane", "dzên", "gian", "giang", "san", "shane",
        "cheyn", "jain", "zane"
    ],
    "Robert": ["robert", "rô bốt", "ro bốt", "rô bớt", "ro bớt", "rô béc", "rô-bớt", "ro béc", "rô-bét"],
    "Elizabeth": [
        "elizabeth", "helizabeth", "ê li za bét", "ê li za bet", "ê li", "ê-li", "li za", "lisa", "ly za",
        "bét", "bết", "li sa", "lisa pham", "lisa phạm", "e li", "e-li", "li-za", "hê li za bét", "elisabeth"
    ],
    "Anastasia": [
        "anastasia", "annastasia", "anatasia", "annatasia", "anastacia", "anastatia", "anastasiya",
        "natasha", "na ta sha", "anatashia", "na ta sia", "a na", "a-na", "anas",
        "a na sờ ta sia", "na sờ ta sia", "a na sta sia", "ana"
    ],
    "Milina": ["milina", "milana", "mi li na", "mi na", "mơ li na", "mơ na", "mi-na", "melina", "milena"],
    "Milana": ["milina", "milana", "mi li na", "mi na", "mơ li na", "mơ na", "mi-na", "melina", "milena"],
    "Violet": ["violet", "vai ô lét", "vi ô lét", "vai let", "vi let", "vai-o-let"],
    "Aimi": [
        "aimi", "ai mi", "ai mì", "ai my", "ai mỳ", "ay mi", "ay my",
        "ai-mi", "ai-mì", "ai-my", "e mi", "ê mi", "e mì", "ê mì",
        "a mi", "a mì", "aimy", "em mi", "em mì", "mai mày", "mai may"
    ],
    "Ainsley Mactier": [
        "ainsley", "mactier", "en xli", "en xly", "mắc ti er", "mác ti ơ", "en-xli",
        "mắc ti e", "ainsley mactier", "en-xi-li", "en xi li", "en-xờ-li"
    ],
    "Stella": ["stella", "sờ te la", "te la", "tét la", "ste la", "ten la"],
    "Amy": ["amy", "e mi", "ê mi", "ay mi"],
    "Jack": ["jack", "dách", "dắc", "giắc", "dắt", "zắc", "giắt"],
    "Olivia": ["olivia", "ô li via", "li via", "ô li", "ô-li", "o li via"],
    "Shaelyn": ["shaelyn", "sê lin", "se lin", "sa lin", "sơ lin", "sa e lin", "sa-lin", "se-lin", "xe lin", "shaelynn"],
    "Aroha": ["aroha", "aloha", "a rô ha", "a ro ha", "ro ha", "a lô ha", "a-ro-ha", "a lo ha", "lo ha"],
    "Viet": ["viet", "việt", "anh việt"],
    "Jude": ["jude", "dút", "dút đơ", "giu đê", "giu đe"],
}

ASSISTANT_VOCATIVES = {"joy", "troy", "chơi", "choi", "chơi ơi", "joy ơi", "troy ơi", "em ơi", "troi", "ok chơi ơi", "ok joy", "ok troy"}
NON_NAME_STOP_WORDS = {
    "ngày", "thứ", "chơi", "thêm", "được", "không", "giúp", "muốn", "người", "trời",
    "hãy", "sang", "rời", "dời", "cho", "ca", "giờ", "làm", "nghen", "nhen", "nghe",
    "nè", "nhe", "nha", "nó", "nào", "nghỉ", "đổi", "sửa", "xếp", "nên", "vào", "qua",
    "ai", "bạn", "chị", "em", "nữa", "thế", "của", "từ", "tới", "đến", "có", "thể",
    "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "sáng", "trưa", "chiều", "tối"
}


def normalize_day(text: str) -> Optional[str]:
    low = text.lower().strip()
    for k in sorted(DAYS_MAP.keys(), key=len, reverse=True):
        if k in low:
            return DAYS_MAP[k]
    return None


def find_days_in_text(text: str) -> List[str]:
    """Finds all days of week mentioned in text in chronological order."""
    low = text.lower()
    found = []
    for k in sorted(DAYS_MAP.keys(), key=len, reverse=True):
        pat = (
            r"(?<![a-zA-Z0-9_àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ])"
            + re.escape(k)
            + r"(?![a-zA-Z0-9_àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ])"
        )
        for m in re.finditer(pat, low):
            found.append((m.start(), m.end(), DAYS_MAP[k]))
    found.sort(key=lambda x: x[0])
    clean = []
    last_end = -1
    for start, end, day in found:
        if start >= last_end:
            clean.append(day)
            last_end = end
    return clean


def find_employees_in_text(text: str, available_names: List[str]) -> List[str]:
    """Finds all employees mentioned using phonetic aliases and fuzzy sound-alike matching."""
    import difflib

    t_clean = text.lower()
    for voc in ["chơi ơi", "joy ơi", "troy ơi", "em ơi", "ok chơi ơi", "ok joy", "ok troy"]:
        t_clean = t_clean.replace(voc, " ")

    alias_to_real = {}
    for real in available_names:
        first = real.lower().split()[0]
        alias_to_real[real.lower()] = real
        alias_to_real[first] = real
        for k, aliases in PHONETIC_ALIASES.items():
            if k.lower() == real.lower() or difflib.SequenceMatcher(None, k.lower(), real.lower()).ratio() > 0.8:
                for a in aliases:
                    if a.lower() not in ASSISTANT_VOCATIVES and a.lower() not in NON_NAME_STOP_WORDS:
                        alias_to_real[a.lower()] = real

    t = " " + t_clean + " "
    found = []

    # 1. Exact alias matches (multi-word first)
    for a in sorted(alias_to_real.keys(), key=len, reverse=True):
        real = alias_to_real[a]
        pattern = (
            r"(?<![a-zA-Z0-9_àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ])"
            + re.escape(a)
            + r"(?![a-zA-Z0-9_àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ])"
        )
        for m in re.finditer(pattern, t):
            if not any(abs(m.start() - pos) < 3 for pos, _ in found):
                found.append((m.start(), real))

    # 2. Fuzzy match individual words >= 4 chars
    words = re.findall(r"[a-zA-Z]+", t_clean)
    for w in words:
        if len(w) >= 4 and w not in NON_NAME_STOP_WORDS and w not in ASSISTANT_VOCATIVES:
            matches = difflib.get_close_matches(w, list(alias_to_real.keys()), n=1, cutoff=0.72)
            if matches:
                matched_real = alias_to_real[matches[0]]
                if matched_real not in [r for _, r in found]:
                    pos = t_clean.find(w)
                    found.append((pos, matched_real))

    found.sort(key=lambda x: x[0])
    res = []
    for _, r in found:
        if r not in res:
            res.append(r)
    return res


def match_employee_name(name_query: str, available_names: List[str]) -> Optional[str]:
    q = name_query.lower().strip()
    if not q:
        return None
    matches = find_employees_in_text(q, available_names)
    if matches:
        return matches[0]
    for name in available_names:
        if name.lower() == q:
            return name
    for name in available_names:
        if q in name.lower() or name.lower() in q:
            return name
    return None


def format_shift_time_vi(shift_str: str) -> str:
    s = str(shift_str or "").strip()
    if not s or s.lower() in ["off", "-", "nan", "none"]:
        return "nghỉ"
    m = re.search(r"(\d{1,2}):?(\d{2})?\s*[-–]\s*(\d{1,2}):?(\d{2})?", s)
    if m:
        h1 = int(m.group(1))
        m1 = m.group(2) or "00"
        h2 = int(m.group(3))
        m2 = m.group(4) or "00"

        p1 = "sáng" if h1 < 12 else ("trưa" if h1 == 12 else "chiều")
        p2 = "sáng" if h2 < 12 else ("trưa" if h2 == 12 else "chiều")

        h1_disp = h1 if h1 <= 12 else (h1 - 12)
        h2_disp = h2 if h2 <= 12 else (h2 - 12)

        t1 = f"{h1_disp}h{m1 if m1 != '00' else ''} {p1}"
        t2 = f"{h2_disp}h{m2 if m2 != '00' else ''} {p2}"
        return f"từ {t1} tới {t2}"
    return s


def parse_shift_duration_hours(shift_str: str) -> float:
    s = str(shift_str or "").strip()
    if not s or s.lower() in ["off", "-", "nan", "none"]:
        return 0.0
    m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*[-–]\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", s, re.IGNORECASE)
    if not m:
        return 0.0
    h1 = int(m.group(1))
    m1 = int(m.group(2) or 0)
    p1 = (m.group(3) or "").lower()
    h2 = int(m.group(4))
    m2 = int(m.group(5) or 0)
    p2 = (m.group(6) or "").lower()

    if p1 == "pm" and h1 < 12:
        h1 += 12
    if p1 == "am" and h1 == 12:
        h1 = 0
    if p2 == "pm" and h2 < 12:
        h2 += 12
    if p2 == "am" and h2 == 12:
        h2 = 0

    if not p1 and not p2:
        if h2 < h1 and h2 < 12:
            h2 += 12
    elif not p1 and p2 == "pm":
        if h1 < 12 and h1 > (h2 - 12):
            h1 += 12

    t1 = h1 + m1 / 60.0
    t2 = h2 + m2 / 60.0
    return max(0.0, round(t2 - t1, 2))


def parse_time_range(text: str) -> Optional[str]:
    """Extracts a normalized shift time range e.g. '12:00 - 17:00' from natural Vietnamese."""
    low = text.lower()
    if any(k in low for k in ["ca sáng", "sáng sớm", "ca mở cửa"]):
        return "07:00 - 12:00"
    if any(k in low for k in ["ca chiều", "ca đóng cửa", "ca tối"]):
        return "12:30 - 17:30"

    norm = re.sub(r"(\d{1,2})\s*giờ", r"\1h", low)
    m = re.search(
        r"(\d{1,2})(?:h(\d{2})?|:(\d{2}))?\s*(sáng|trưa|chiều|tối)?\s*(?:tới|đến|-)\s*(\d{1,2})(?:h(\d{2})?|:(\d{2}))?\s*(sáng|trưa|chiều|tối)?",
        norm,
    )
    if m:
        h1 = int(m.group(1))
        m1 = m.group(2) or m.group(3) or "00"
        p1 = m.group(4) or ""

        h2 = int(m.group(5))
        m2 = m.group(6) or m.group(7) or "00"
        p2 = m.group(8) or ""

        if p1 in ["chiều", "tối"] and h1 < 12:
            h1 += 12
        if p2 in ["chiều", "tối"] and h2 < 12:
            h2 += 12
        if not p1 and p2 in ["chiều", "tối"] and h1 < 12 and h1 > (h2 - 12):
            h1 += 12

        t1 = f"{h1:02d}:{m1}"
        t2 = f"{h2:02d}:{m2}"
        return f"{t1} - {t2}"
    return None


def parse_start_end_time_adjustment(msg: str, current_shift: str) -> Optional[str]:
    low = msg.lower()
    norm = re.sub(r"(\d{1,2})\s*giờ", r"\1h", low)
    m_from_to = re.search(r"từ\s*(\d{1,2})h?\s*thành\s*(\d{1,2})h?", norm)
    m_target = re.search(r"(?:thành|lúc|sang|đến|lên|thành ca)\s*(\d{1,2})(?:h(\d{2})?|:(\d{2}))?\s*(sáng|trưa|chiều|tối)?", norm)

    target_h = None
    target_m = "00"
    if m_from_to:
        target_h = int(m_from_to.group(2))
    elif m_target:
        target_h = int(m_target.group(1))
        target_m = m_target.group(2) or m_target.group(3) or "00"
        p = m_target.group(4) or ""
        if p in ["chiều", "tối"] and target_h < 12:
            target_h += 12

    if target_h is None:
        return None

    is_start = any(k in low for k in ["bắt đầu", "vào", "vô", "vào ca", "mở", "bắt đầu từ"])
    is_end = any(k in low for k in ["kết thúc", "về", "hết ca", "đóng", "tan"])

    m_cur = re.search(r"(\d{1,2}):?(\d{2})?\s*(?:am|pm)?\s*[-–]\s*(\d{1,2}):?(\d{2})?\s*(?:am|pm)?", current_shift or "", re.IGNORECASE)
    if m_cur:
        cur_h1 = int(m_cur.group(1))
        cur_m1 = m_cur.group(2) or "00"
        cur_h2 = int(m_cur.group(3))
        cur_m2 = m_cur.group(4) or "00"

        cur_low = (current_shift or "").lower()
        if "pm" in cur_low and cur_h2 < 12 and cur_h2 <= cur_h1:
            cur_h2 += 12
        elif cur_h2 < cur_h1 and cur_h2 < 12:
            cur_h2 += 12

        if is_start or (not is_end and target_h < cur_h2):
            return f"{target_h:02d}:{target_m} - {cur_h2:02d}:{cur_m2}"
        elif is_end or target_h > cur_h1:
            return f"{cur_h1:02d}:{cur_m1} - {target_h:02d}:{target_m}"

    return f"{target_h:02d}:{target_m} - {target_h+5:02d}:{target_m}"


# =========================================================================
# OMNISCIENT DATABASE QUERY HANDLERS (FULL APP DATABASE KNOWLEDGE)
# =========================================================================

def load_all_employee_directory(db_instance: Any) -> Dict[str, Dict[str, Any]]:
    """Loads all employee records, combining datasets/employees and system_store/user_profiles."""
    if not db_instance:
        return {}
    employees = db_instance.load_records("employees") or []
    user_profiles = db_instance.load_system_doc("user_profiles") or {}

    directory = {}
    for e in employees:
        name = (e.get("NAME") or e.get("Name") or e.get("Employee") or "").strip()
        if not name:
            continue
        up = None
        for k, v in user_profiles.items():
            emp_n = v.get("employee_name", "").strip()
            if emp_n.lower() == name.lower() or k.lower() == name.lower() or name.lower().startswith(k.lower()):
                up = v
                break
        prof = up.get("profile", {}) if up else {}

        directory[name.lower()] = {
            "name": name,
            "full_name": prof.get("full_name") or name,
            "position": e.get("position") or prof.get("employment_level") or "Service Staff",
            "team": e.get("Team") or "Service Staff",
            "status": e.get("status") or prof.get("classification") or "casual",
            "dob": prof.get("dob") or e.get("DOB") or "",
            "commencement_date": prof.get("commencement_date") or e.get("Commencing Date") or "",
            "mobile": prof.get("mobile") or "",
            "home_phone": prof.get("home_phone") or "",
            "email": prof.get("email") or "",
            "address": prof.get("address") or "",
            "emergency_contact": prof.get("emergency_contact") or prof.get("super_contact") or "",
        }

    for k, v in user_profiles.items():
        emp_n = (v.get("employee_name") or k).strip()
        if emp_n.lower() not in directory and emp_n.lower() != "admin":
            prof = v.get("profile", {})
            directory[emp_n.lower()] = {
                "name": emp_n,
                "full_name": prof.get("full_name") or emp_n,
                "position": prof.get("employment_level") or v.get("role") or "Service Staff",
                "team": "Service Staff",
                "status": prof.get("classification") or "casual",
                "dob": prof.get("dob") or "",
                "commencement_date": prof.get("commencement_date") or "",
                "mobile": prof.get("mobile") or "",
                "home_phone": prof.get("home_phone") or "",
                "email": prof.get("email") or "",
                "address": prof.get("address") or "",
                "emergency_contact": prof.get("emergency_contact") or "",
            }

    return directory


def query_contact_info(emp_name: str, query_type: str, db_instance: Any) -> str:
    """Answers contact details: phone, email, address, DOB, commencement date from database."""
    directory = load_all_employee_directory(db_instance)
    emp_key = emp_name.lower().strip()

    matched_info = None
    for k, v in directory.items():
        if k == emp_key or emp_key in k or k in emp_key:
            matched_info = v
            break

    if not matched_info:
        return f"Chị Nhi ơi, Joy hổng tìm thấy hồ sơ của bạn '{emp_name}' trong dữ liệu tiệm mình nè!"

    name = matched_info["name"]
    mobile = matched_info["mobile"]
    home_phone = matched_info["home_phone"]
    email = matched_info["email"]
    addr = matched_info["address"]
    dob = matched_info["dob"]
    start = matched_info["commencement_date"]
    pos = matched_info["position"]

    # Phone number query
    if any(k in query_type.lower() for k in ["phone", "mobile", "sđt", "số điện thoại", "alo", "gọi", "điện thoại"]):
        if mobile and home_phone and mobile != home_phone:
            return f"Dạ số điện thoại của {name} là {mobile} (hoặc số nhà {home_phone}) nghen chị Nhi! 🥖"
        elif mobile:
            return f"Dạ số điện thoại của {name} là {mobile} nghen chị Nhi! 🥖"
        elif home_phone:
            return f"Dạ {name} có số liên hệ là {home_phone} nghen chị Nhi!"
        else:
            return f"Dạ chị Nhi ơi, trên hệ thống bạn {name} chưa có điền số điện thoại á!"

    # Email query
    if any(k in query_type.lower() for k in ["email", "thư", "mail"]):
        if email:
            return f"Dạ email của {name} là {email} nghen chị Nhi! ✉️"
        else:
            return f"Dạ chị Nhi ơi, trên app chưa có cập nhật địa chỉ email của bạn {name} nè!"

    # Address query
    if any(k in query_type.lower() for k in ["address", "địa chỉ", "ở đâu", "nhà"]):
        if addr:
            return f"Dạ địa chỉ nhà của {name} là: {addr} nghen chị Nhi! 🏡"
        else:
            return f"Dạ chị Nhi ơi, trong hồ sơ bạn {name} chưa có lưu địa chỉ nhà á!"

    # Birthday / DOB
    if any(k in query_type.lower() for k in ["dob", "sinh", "sinh nhật", "tuổi", "năm sinh"]):
        if dob:
            return f"Dạ ngày sinh của {name} là {dob} nghen chị Nhi! 🎂"
        else:
            return f"Dạ trong hồ sơ chưa có ngày sinh của bạn {name} nè chị!"

    # Commencement date
    if any(k in query_type.lower() for k in ["commence", "bắt đầu", "vào làm", "ngày vào"]):
        if start:
            return f"Dạ bạn {name} bắt đầu vào làm tại tiệm từ ngày {start} nghen chị! 🥖"
        else:
            return f"Dạ trong hệ thống chưa ghi nhận ngày vào làm của {name} nè chị!"

    # Full profile summary
    details = []
    if mobile:
        details.append(f"SĐT: {mobile}")
    if email:
        details.append(f"Email: {email}")
    if dob:
        details.append(f"Ngày sinh: {dob}")
    if pos:
        details.append(f"Vị trí: {pos}")
    if start:
        details.append(f"Vào làm: {start}")
    if addr:
        details.append(f"Địa chỉ: {addr}")

    if details:
        return f"Dạ thông tin của {name} nè chị Nhi: {', '.join(details)} nghen! 🌟"
    else:
        return f"Dạ hồ sơ của {name} hiện tại chỉ có tên trên danh sách tiệm thôi chứ chưa điền chi tiết liên hệ á chị!"


def query_employee_role(query_type: str, emp_name: str, db_instance: Any) -> str:
    """Answers positions, roles, baker vs service staff status from database."""
    directory = load_all_employee_directory(db_instance)
    low = query_type.lower()

    if emp_name:
        emp_key = emp_name.lower().strip()
        matched = None
        for k, v in directory.items():
            if k == emp_key or emp_key in k or k in emp_key:
                matched = v
                break
        if not matched:
            return f"Chị Nhi ơi, Joy hổng tìm thấy hồ sơ của bạn '{emp_name}' trong tiệm á!"
        name = matched["name"]
        pos = matched["position"]
        team = matched["team"]
        status = matched["status"]
        return f"Dạ bạn {name} giữ vị trí {pos} ({team}, hình thức {status}) nghen chị Nhi! 🥖"

    if any(k in low for k in ["thợ bánh", "thợ làm bánh", "baker"]) and "phụ" not in low:
        bakers = [
            v["name"]
            for v in directory.values()
            if "baker" in v["position"].lower() and "assitant" not in v["position"].lower() and "assistant" not in v["position"].lower()
        ]
        assts = [v["name"] for v in directory.values() if "assitant" in v["position"].lower() or "assistant" in v["position"].lower()]
        b_str = ", anh ".join(bakers)
        a_str = ", ".join(assts)
        return f"Dạ tiệm mình có anh {b_str} là thợ làm bánh chính, còn bạn {a_str} là thợ phụ bánh nè chị Nhi! 🥐"

    if any(k in low for k in ["phụ bánh", "baker assistant", "baker assitant"]):
        assts = [v["name"] for v in directory.values() if "assitant" in v["position"].lower() or "assistant" in v["position"].lower()]
        return f"Dạ ở tiệm mình người làm phụ tá thợ bánh là bạn {', '.join(assts)} nghen chị Nhi! 🥐"

    if any(k in low for k in ["bán hàng", "service staff", "service"]):
        service = [v["name"] for v in directory.values() if "service" in v["position"].lower()]
        return f"Dạ nhóm nhân viên bán hàng (Service Staff) gồm có: {', '.join(service)} nghen chị Nhi! 🌟"

    return "Dạ chị muốn hỏi về vị trí của bạn nào hay chức danh nào trong tiệm dặn Joy nghen!"


def query_unavailability_restrictions(emp_name: Optional[str], day: Optional[str], db_instance: Any) -> str:
    """Queries employee unavailability and restrictions from database."""
    if not db_instance:
        return "Dạ Joy chưa truy cập được dữ liệu ngày nghỉ á chị!"
    unav_list = db_instance.load_records("unavailability") or []

    day_vi = DAYS_VI_NAMES.get(day, day) if day else ""

    # Specific employee + Specific day
    if emp_name and day:
        emp_key = emp_name.lower().strip()
        matched_records = [u for u in unav_list if u.get("Employee", "").lower() == emp_key and u.get("Day") == day]
        if matched_records:
            windows = []
            for r in matched_records:
                w = r.get("Time Window", "")
                w_disp = re.sub(r"\(From [^)]+\)", "", w).strip()
                windows.append(w_disp)
            win_str = ", ".join(set(windows))
            return f"Dạ {day_vi} này {emp_name} có restriction/bận khung giờ: {win_str} nghen chị Nhi!"
        else:
            return f"Dạ {day_vi} này {emp_name} hoàn toàn rảnh, không có restriction nào hết, chị xếp ca thoải mái nghen! ✨"

    # Specific employee, overall restrictions
    if emp_name and not day:
        emp_key = emp_name.lower().strip()
        matched_records = [u for u in unav_list if u.get("Employee", "").lower() == emp_key]
        if not matched_records:
            return f"Dạ bạn {emp_name} không có đăng ký restriction nào hết á chị Nhi, bạn hoàn toàn available nghen! ✨"

        by_day = {}
        for r in matched_records:
            d = r.get("Day", "")
            d_vi = DAYS_VI_NAMES.get(d, d)
            w = r.get("Time Window", "")
            w_disp = re.sub(r"\(From [^)]+\)", "", w).strip()
            by_day.setdefault(d_vi, set()).add(w_disp)

        parts = [f"{d}: {', '.join(wins)}" for d, wins in by_day.items()]
        if len(parts) > 4:
            parts_str = "; ".join(parts[:4]) + f" (và {len(parts)-4} ngày khác)"
        else:
            parts_str = "; ".join(parts)
        return f"Dạ lịch bận (restriction) của {emp_name} gồm có: {parts_str} nghen chị Nhi!"

    # Query who is unavailable on a specific day
    if day and not emp_name:
        matched_records = [u for u in unav_list if u.get("Day") == day]
        if not matched_records:
            return f"Dạ {day_vi} này tiệm mình không có bạn nào đăng ký bận hết, tất cả đều available nghen chị! 🥖"

        emp_map = {}
        for r in matched_records:
            e = r.get("Employee")
            w = r.get("Time Window", "")
            w_disp = re.sub(r"\(From [^)]+\)", "", w).strip()
            emp_map.setdefault(e, set()).add(w_disp)

        desc = [f"{e} ({', '.join(wins)})" for e, wins in emp_map.items()]
        return f"Dạ {day_vi} này có các bạn sau có restriction/bận nè chị: {', '.join(desc)} nghen!"

    return "Dạ chị muốn xem lịch bận của bạn nào hoặc thứ mấy dặn Joy coi liền nghen!"


def query_roster_schedule_and_hours(
    emp_name: Optional[str],
    day: Optional[str],
    query_type: str,
    roster_rows: List[Dict[str, Any]],
) -> str:
    """Answers shift queries: who is working on a day, employee weekly hours, top hours ranking."""
    if not roster_rows:
        return "Dạ hiện tại Joy chưa thấy có bảng Roster nào đang mở hết á chị Nhi!"

    all_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    # Who is working on a specific day?
    if day and any(k in query_type.lower() for k in ["ai làm", "ai đi làm", "những ai", "ai có ca", "mấy người", "danh sách"]):
        day_vi = DAYS_VI_NAMES.get(day, day)
        working_staff = []
        for r in roster_rows:
            emp = r.get("Employee") or r.get("NAME") or ""
            shift = str(r.get(day) or "").strip()
            if shift and shift.lower() not in ["off", "-", "nan", "none"]:
                working_staff.append(f"{emp} ({shift})")
        if working_staff:
            return f"Dạ {day_vi} này tiệm mình có {len(working_staff)} bạn đi làm nè chị Nhi: {', '.join(working_staff)} nghen! 🥖"
        else:
            return f"Dạ {day_vi} này chưa có bạn nào được xếp ca làm hết á chị!"

    # Ranking who works the most hours / least hours
    if any(k in query_type.lower() for k in ["nhiều giờ nhất", "nhiều nhất", "top giờ", "ít giờ nhất", "ít nhất", "tổng kết giờ"]):
        hours_by_emp = []
        for r in roster_rows:
            emp = r.get("Employee") or r.get("NAME") or ""
            total_h = sum(parse_shift_duration_hours(str(r.get(d) or "")) for d in all_days)
            shifts_cnt = sum(
                1
                for d in all_days
                if str(r.get(d) or "").strip() and str(r.get(d) or "").strip().lower() not in ["off", "-", "nan", "none"]
            )
            hours_by_emp.append((emp, total_h, shifts_cnt))

        hours_by_emp.sort(key=lambda x: x[1], reverse=True)

        if "ít" in query_type.lower():
            hours_by_emp.sort(key=lambda x: x[1])
            top_few = [f"{e}: {h}h ({c} ca)" for e, h, c in hours_by_emp[:4] if h > 0]
            return f"Dạ tuần này những bạn làm ít giờ nhất là: {', '.join(top_few)} nghen chị Nhi!"
        else:
            top_few = [f"{e}: {h}h ({c} ca)" for e, h, c in hours_by_emp[:4]]
            return f"Dạ tuần này bạn làm nhiều giờ nhất là {hours_by_emp[0][0]} với {hours_by_emp[0][1]} tiếng. Tiếp theo là {', '.join(top_few[1:])} nghen chị Nhi! 🌟"

    # Specific employee working hours & schedule
    if emp_name:
        row = next((r for r in roster_rows if str(r.get("Employee") or r.get("NAME") or "").lower() == emp_name.lower()), None)
        if not row:
            return f"Chị Nhi ơi, Joy hổng tìm thấy bạn '{emp_name}' trên bảng lịch tuần này á!"

        emp_real = row.get("Employee") or row.get("NAME") or emp_name
        shifts = []
        total_h = 0.0
        for d in all_days:
            s = str(row.get(d) or "").strip()
            if s and s.lower() not in ["off", "-", "nan", "none"]:
                d_vi = DAYS_VI_NAMES.get(d, d)
                dur = parse_shift_duration_hours(s)
                total_h += dur
                shifts.append(f"{d_vi} ({s})")

        if shifts:
            return f"Dạ tuần này {emp_real} làm {len(shifts)} ca, tổng cộng {total_h} tiếng ({', '.join(shifts)}) nghen chị Nhi! 🥖"
        else:
            return f"Dạ tuần này bạn {emp_real} không có ca nào trên lịch hết, đang nghỉ trọn tuần nghen chị!"

    return "Dạ chị muốn coi giờ làm của bạn nào hay ngày thứ mấy nghen?"


def query_holidays_info(query_type: str, db_instance: Any) -> str:
    """Answers upcoming public holidays and Victorian school holidays."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    h_doc = db_instance.load_system_doc("holiday_calendar") if db_instance else {}
    cal = h_doc.get("calendar", {}) if h_doc else {}
    pub = cal.get("public", [])
    school = cal.get("school", [])

    upcoming_pub = [p for p in pub if p.get("start", "") >= today_str][:3]
    upcoming_sch = [s for s in school if s.get("end", "") >= today_str][:2]

    lines = []
    if upcoming_sch:
        for s in upcoming_sch:
            lines.append(f"- Kỳ nghỉ học sinh {s.get('name')}: từ {s.get('start')} tới {s.get('end')}")
    if upcoming_pub:
        for p in upcoming_pub:
            lines.append(f"- Ngày lễ {p.get('name')}: ngày {p.get('start')}")

    if lines:
        return "Dạ sắp tới tiểu bang Victoria mình có các kỳ nghỉ và ngày lễ nè chị Nhi:\n" + "\n".join(lines) + "\nChị lưu ý sắp xếp thợ bánh với nhân viên bán hàng những ngày này nghen! 🥖✨"
    else:
        return "Dạ trong thời gian tới không có kỳ nghỉ lễ lớn nào ở Victoria hết nghen chị!"


# =========================================================================
# ACTION EXECUTION ENGINE
# =========================================================================

def execute_roster_action(
    action_type: str,
    params: Dict[str, Any],
    roster_rows: List[Dict[str, Any]],
    db: Any = None,
) -> Tuple[bool, str, List[Dict[str, Any]], Dict[str, Any]]:
    """
    Executes a structured action on roster_rows or queries app databases:
    (success, phan_rang_reply, updated_roster_rows, action_summary)
    """
    all_emp_names = [str(r.get("Employee") or r.get("NAME") or r.get("Name") or "").strip() for r in roster_rows] if roster_rows else []
    day = params.get("day")
    if day:
        day = normalize_day(day) or day
    if day and day not in DAYS_VI_NAMES:
        day = "Monday"

    day_vi = DAYS_VI_NAMES.get(day, day) if day else ""

    # --- 1. Omnichannel Database Query Handlers ---
    if action_type == "query_employee_contact":
        emp_raw = params.get("emp", "")
        emp = match_employee_name(emp_raw, all_emp_names) or emp_raw
        q_type = params.get("query_type", "contact")
        reply = query_contact_info(emp, q_type, db)
        return True, reply, roster_rows, {"action": "query_employee_contact", "emp": emp}

    elif action_type == "query_employee_role":
        emp_raw = params.get("emp", "")
        emp = match_employee_name(emp_raw, all_emp_names) if emp_raw else ""
        q_type = params.get("query_type", "")
        reply = query_employee_role(q_type, emp, db)
        return True, reply, roster_rows, {"action": "query_employee_role", "emp": emp}

    elif action_type == "query_unavailability_restriction":
        emp_raw = params.get("emp", "")
        emp = match_employee_name(emp_raw, all_emp_names) if emp_raw else ""
        reply = query_unavailability_restrictions(emp, day, db)
        return True, reply, roster_rows, {"action": "query_unavailability_restriction", "emp": emp, "day": day}

    elif action_type == "query_shift_schedule_and_hours":
        emp_raw = params.get("emp", "")
        emp = match_employee_name(emp_raw, all_emp_names) if emp_raw else ""
        q_type = params.get("query_type", "")
        reply = query_roster_schedule_and_hours(emp, day, q_type, roster_rows)
        return True, reply, roster_rows, {"action": "query_shift_schedule_and_hours", "emp": emp, "day": day}

    elif action_type == "query_holidays":
        q_type = params.get("query_type", "")
        reply = query_holidays_info(q_type, db)
        return True, reply, roster_rows, {"action": "query_holidays"}

    # --- 2. Roster Modification Actions (Require roster_rows) ---
    if not roster_rows:
        return False, "Ủa chị Nhi ơi, hiện tại Joy chưa thấy có bảng Roster nào để chỉnh hết á!", roster_rows, {}

    if action_type == "move_shift_day":
        emp_raw = params.get("emp", "")
        from_day = params.get("from_day")
        to_day = params.get("to_day")
        if from_day:
            from_day = normalize_day(from_day) or from_day
        if to_day:
            to_day = normalize_day(to_day) or to_day
        if from_day not in DAYS_VI_NAMES:
            from_day = "Monday"
        if to_day not in DAYS_VI_NAMES:
            to_day = "Wednesday"

        from_day_vi = DAYS_VI_NAMES.get(from_day, from_day)
        to_day_vi = DAYS_VI_NAMES.get(to_day, to_day)
        emp = match_employee_name(emp_raw, all_emp_names)

        if not emp:
            return False, f"Chị Nhi ơi, Joy hổng tìm thấy bạn '{emp_raw}' trong tiệm á!", roster_rows, {}

        row = next((r for r in roster_rows if str(r.get("Employee") or "").lower() == emp.lower()), None)
        if not row:
            return False, f"Chị Nhi ơi, Joy hổng tìm thấy dòng của {emp} trên bảng á!", roster_rows, {}

        cur_from = row.get(from_day, "")
        t_from_vi = format_shift_time_vi(cur_from)

        if t_from_vi == "nghỉ":
            reply = f"Dạ chị Nhi ơi, {from_day_vi} này {emp} đang nghỉ không có ca. Chị muốn xếp ca mấy giờ vào {to_day_vi} cho {emp} dặn Joy làm liền nghen! 🥖"
            action_summary = {"action": "move_shift_day_prompt", "emp": emp, "from_day": from_day, "to_day": to_day}
            return True, reply, roster_rows, action_summary
        else:
            row[from_day] = ""
            row[to_day] = cur_from
            reply = f"Xong chị ơi! Joy dời ca {from_day_vi} ({t_from_vi}) của {emp} sang {to_day_vi} rồi nghen! 🥖"
            action_summary = {"action": "move_shift_day", "emp": emp, "from_day": from_day, "to_day": to_day, "shift_time": cur_from}
            return True, reply, roster_rows, action_summary

    elif action_type == "swap_shifts":
        emp1_raw = params.get("emp1", "")
        emp2_raw = params.get("emp2", "")
        emp1 = match_employee_name(emp1_raw, all_emp_names)
        emp2 = match_employee_name(emp2_raw, all_emp_names)

        if not emp1 or not emp2:
            return False, f"Chị Nhi ơi, Joy tìm hổng ra nhân viên '{emp1_raw}' hoặc '{emp2_raw}' trong tiệm mình nè!", roster_rows, {}

        row1 = next((r for r in roster_rows if str(r.get("Employee") or "").lower() == emp1.lower()), None)
        row2 = next((r for r in roster_rows if str(r.get("Employee") or "").lower() == emp2.lower()), None)

        if not row1 or not row2:
            return False, "Chị Nhi ơi, Joy hổng tìm thấy dòng ca của hai bạn trên bảng lịch á!", roster_rows, {}

        val1 = row1.get(day, "")
        val2 = row2.get(day, "")
        row1[day] = val2
        row2[day] = val1

        t1_vi = format_shift_time_vi(val1)
        t2_vi = format_shift_time_vi(val2)

        if t2_vi == "nghỉ":
            reply = f"Xong chị ơi! Joy đổi ca {day_vi} ({t1_vi}) của {emp1} qua cho {emp2} rồi nghen! 🥖"
        elif t1_vi == "nghỉ":
            reply = f"Xong chị ơi! Joy đổi ca {day_vi} ({t2_vi}) của {emp2} qua cho {emp1} rồi nghen! 🥖"
        else:
            reply = f"Xong chị ơi! Joy đổi ca {day_vi} giữa {emp1} ({t1_vi}) với {emp2} ({t2_vi}) rồi nghen! 🥖"

        action_summary = {"action": "swap_shifts", "emp1": emp1, "emp2": emp2, "day": day, "shift_emp1": val1, "shift_emp2": val2}
        return True, reply, roster_rows, action_summary

    elif action_type == "reassign_shift":
        from_raw = params.get("from_emp", "")
        to_raw = params.get("to_emp", "")
        from_emp = match_employee_name(from_raw, all_emp_names)
        to_emp = match_employee_name(to_raw, all_emp_names)

        if not to_emp:
            return False, f"Chị Nhi ơi, Joy hổng thấy bạn '{to_raw}' trong danh sách tiệm mình nè!", roster_rows, {}

        to_row = next((r for r in roster_rows if str(r.get("Employee") or "").lower() == to_emp.lower()), None)
        shift_val = params.get("shift_time", "")

        if from_emp:
            from_row = next((r for r in roster_rows if str(r.get("Employee") or "").lower() == from_emp.lower()), None)
            if from_row:
                shift_val = shift_val or from_row.get(day, "")
                from_row[day] = ""

        if not shift_val:
            shift_val = "06:00 - 14:00"

        if to_row:
            to_row[day] = shift_val

        t_vi = format_shift_time_vi(shift_val)
        reply = f"Xong chị ơi! Ca {day_vi} {t_vi} Joy chuyển qua cho {to_emp} làm rồi nhen! ✨"
        action_summary = {"action": "reassign_shift", "from_emp": from_emp, "to_emp": to_emp, "day": day, "shift_time": shift_val}
        return True, reply, roster_rows, action_summary

    elif action_type == "remove_shift":
        emp_raw = params.get("emp", "")
        emp = match_employee_name(emp_raw, all_emp_names)
        if not emp:
            return False, f"Chị Nhi ơi, Joy tìm hổng thấy bạn '{emp_raw}' trên bảng lịch nè!", roster_rows, {}

        row = next((r for r in roster_rows if str(r.get("Employee") or "").lower() == emp.lower()), None)
        old_val = row.get(day, "") if row else ""
        if row:
            row[day] = ""

        t_vi = format_shift_time_vi(old_val)
        reply = f"Xong chị ơi! {day_vi} này Joy cho {emp} nghỉ rồi nghen! 🌸"
        action_summary = {"action": "remove_shift", "emp": emp, "day": day, "old_shift": old_val}
        return True, reply, roster_rows, action_summary

    elif action_type in ["adjust_shift_hours", "add_extra_shift"]:
        emp_raw = params.get("emp", "")
        emp = match_employee_name(emp_raw, all_emp_names)
        shift_time = params.get("shift_time", "").strip()

        if not emp:
            return False, f"Chị Nhi ơi, Joy hổng tìm thấy bạn '{emp_raw}' trong tiệm á!", roster_rows, {}

        row = next((r for r in roster_rows if str(r.get("Employee") or "").lower() == emp.lower()), None)
        if row:
            row[day] = shift_time

        t_vi = format_shift_time_vi(shift_time)
        reply = f"Xong chị ơi! Ca {day_vi} của {emp} Joy cập nhật {t_vi} rồi nhen! 🌟"
        action_summary = {"action": action_type, "emp": emp, "day": day, "shift_time": shift_time}
        return True, reply, roster_rows, action_summary

    elif action_type == "save_manager_preference":
        emp_raw = params.get("emp", "")
        pref = params.get("preference", "PREFER")
        shift_name = params.get("shift_name", "")
        weight = int(params.get("weight", 50))
        notes = params.get("notes", "")

        if db:
            db.save_learned_rule("manager_voice_rule", emp_raw, day, shift_name, pref, weight, notes)
            db.save_memory_fact(f"rule_{emp_raw}_{day}_{shift_name}", "scheduling_preference", f"{notes} ({pref})")

        reply = f"Xong chị ơi! Joy lưu ý dặn của chị ({notes}) rồi nghen! ❤️"
        return True, reply, roster_rows, {"action": "save_manager_preference", "notes": notes}

    elif action_type == "query_or_prompt_shift":
        emp_raw = params.get("emp", "")
        emp = match_employee_name(emp_raw, all_emp_names) or emp_raw
        row = next((r for r in roster_rows if str(r.get("Employee") or "").lower() == emp.lower()), None)
        cur_val = row.get(day, "") if row else ""
        if cur_val and cur_val.lower() not in ["off", "-", "nan", "none", ""]:
            t_vi = format_shift_time_vi(cur_val)
            reply = f"Dạ {day_vi} {emp} đang làm {t_vi}. Chị muốn đổi hay sửa mấy giờ nè?"
        else:
            reply = f"Dạ {day_vi} {emp} đang nghỉ. Chị muốn thêm ca mấy giờ cho {emp} nghen?"
        return True, reply, roster_rows, {"action": "query_shift", "emp": emp, "day": day}

    elif action_type == "unknown_employee":
        emp_raw = params.get("emp_raw", "")
        reply = f"Chị Nhi ơi, Joy hổng tìm thấy bạn '{emp_raw}' trong bảng lịch tuần này á!"
        return False, reply, roster_rows, {}

    elif action_type == "greeting":
        raw = str(params.get("raw", "")).lower()
        if any(k in raw for k in ["sao không nói", "không nói gì", "im re", "alo ủa", "sao nó không nói"]):
            reply = "Dạ Joy vẫn đang nghe rõ nè chị Nhi ơi! Chị dặn Joy sửa ca của bạn nào nghen! 🥖"
        else:
            reply = "Dạ Joy nghe nè chị Nhi! Chị dặn Joy sửa ca bạn nào nghen!"
        return True, reply, roster_rows, {"action": "greeting"}

    return False, "Dạ, Joy nghe nè chị.", roster_rows, {}


# =========================================================================
# DETERMINISTIC INTENT PARSER
# =========================================================================

def parse_intent_rule_based(
    user_message: str,
    roster_rows: List[Dict[str, Any]],
    history: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[Optional[str], Dict[str, Any]]:
    """Fast, deterministic fallback parser with conversational context memory and database knowledge."""
    msg = user_message.lower().strip()
    all_emp = [str(r.get("Employee") or "").strip() for r in roster_rows] if roster_rows else []

    days = find_days_in_text(msg)
    day = days[0] if days else None
    found_emps = find_employees_in_text(msg, all_emp)
    time_str = parse_time_range(msg)

    # Extract previous context from recent turns
    prev_emp = None
    prev_day = None
    if history:
        for h in reversed(history):
            text_h = h.get("message_text", "")
            if not prev_emp:
                emps_h = find_employees_in_text(text_h, all_emp)
                if emps_h:
                    prev_emp = emps_h[0]
            if not prev_day:
                d_h = find_days_in_text(text_h)
                if d_h:
                    prev_day = d_h[-1]
            if prev_emp and prev_day:
                break

    # If only 1 employee found, check if there is another employee after 'sang cho', 'qua cho', 'cho'
    if len(found_emps) == 1:
        m_to = re.search(
            r"(?:sang\s+cho|qua\s+cho|cho)\s+([a-zA-Zàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]+)",
            msg,
        )
        if m_to:
            cand = m_to.group(1).strip()
            matches = find_employees_in_text(cand, all_emp)
            if matches and matches[0].lower() != found_emps[0].lower():
                found_emps.append(matches[0])

    # ---------------------------------------------------------------------
    # QUERY INTENT 1: Contact info (Phone, Email, Address, DOB, Commencement)
    # ---------------------------------------------------------------------
    contact_keywords = [
        "số điện thoại", "sđt", "so dien thoai", "sdt", "số phone", "phone", "mobile",
        "điện thoại", "alo", "gọi", "email", "mail", "thư điện tử", "địa chỉ", "dia chi",
        "ở đâu", "nhà ở", "nhà của", "sinh nhật", "ngày sinh", "sinh năm", "năm sinh",
        "sinh ngày", "ngày vào làm", "bắt đầu làm", "vào làm từ", "vào tiệm", "thông tin cá nhân",
        "thông tin của", "profile của", "hồ sơ của", "profile"
    ]
    if any(k in msg for k in contact_keywords):
        target_emp = found_emps[0] if found_emps else (prev_emp or "")
        return "query_employee_contact", {"emp": target_emp, "query_type": msg}

    # ---------------------------------------------------------------------
    # QUERY INTENT 2: Employee roles & positions (Baker, Baker Assistant, Service Staff)
    # ---------------------------------------------------------------------
    role_keywords = [
        "thợ bánh", "thợ làm bánh", "baker", "phụ bánh", "baker assistant", "baker assitant",
        "bán hàng", "service staff", "chức vụ", "làm chức vụ", "làm vị trí gì", "vị trí gì",
        "ai là thợ", "ai phụ bánh", "ai làm bánh", "ai bán hàng"
    ]
    if any(k in msg for k in role_keywords) and not any(k in msg for k in ["đổi", "dời", "chuyển", "thêm ca", "xóa ca", "cho nghỉ"]):
        target_emp = found_emps[0] if found_emps else ""
        return "query_employee_role", {"emp": target_emp, "query_type": msg}

    # ---------------------------------------------------------------------
    # QUERY INTENT 3: Unavailability & Restrictions
    # ---------------------------------------------------------------------
    restriction_keywords = [
        "restriction", "unavailability", "bận", "rảnh", "nghỉ phép", "xin nghỉ",
        "có làm được không", "có đi làm được không", "có rảnh không", "có bận không",
        "có available không", "unavailable", "available", "lịch bận", "vướng lịch", "vướng"
    ]
    if any(k in msg for k in restriction_keywords) and not any(k in msg for k in ["cho nghỉ", "xóa ca", "bỏ ca", "thêm ca", "1k"]):
        target_emp = found_emps[0] if found_emps else ""
        return "query_unavailability_restriction", {"emp": target_emp, "day": day or "", "query_type": msg}

    # ---------------------------------------------------------------------
    # QUERY INTENT 4: Holidays (Public holidays, School holidays)
    # ---------------------------------------------------------------------
    holiday_keywords = [
        "ngày lễ", "nghỉ lễ", "public holiday", "school holiday", "lễ sắp tới",
        "nghỉ hè", "nghỉ thu", "lễ tết", "giáng sinh", "christmas", "boxing day", "tết tây"
    ]
    if any(k in msg for k in holiday_keywords):
        return "query_holidays", {"query_type": msg}

    # ---------------------------------------------------------------------
    # QUERY INTENT 5: Shift schedule, total hours, who is working, rankings
    # ---------------------------------------------------------------------
    schedule_keywords = [
        "ai đi làm", "ai làm", "những ai làm", "ai có ca", "có ai làm", "mấy người làm",
        "danh sách đi làm", "tổng giờ", "bao nhiêu tiếng", "mấy tiếng", "nhiều giờ nhất",
        "ít giờ nhất", "bao nhiêu ca", "mấy ca", "lịch làm của", "lịch làm việc của",
        "tuần này làm", "hôm nay ai làm"
    ]
    if any(k in msg for k in schedule_keywords) and not any(k in msg for k in ["đổi", "dời", "chuyển", "thêm", "xóa", "cho nghỉ"]):
        target_emp = found_emps[0] if found_emps else ""
        return "query_shift_schedule_and_hours", {"emp": target_emp, "day": day or "", "query_type": msg}

    # ---------------------------------------------------------------------
    # ROSTER MODIFICATION ACTIONS
    # ---------------------------------------------------------------------

    # Priority: Preference instruction
    if any(k in msg for k in ["dặn joy", "dặn em", "nhớ là", "sau này", "từ giờ", "từ nay", "nhớ nghen", "nhớ nhen", "nhớ nha"]):
        pref = "AVOID" if any(k in msg for k in ["đừng", "không", "hạn chế", "hông thích", "ko thích"]) else "PREFER"
        emp = found_emps[0] if found_emps else "All"
        return "save_manager_preference", {
            "emp": emp,
            "day": day or prev_day or "",
            "preference": pref,
            "weight": -100 if pref == "AVOID" else 50,
            "notes": user_message,
        }

    # Case 0: Move shift from Day 1 to Day 2 for same employee
    if len(found_emps) == 1 and len(days) >= 2 and any(k in msg for k in ["dời", "rời", "chuyển", "đổi", "sang", "qua"]):
        return "move_shift_day", {"emp": found_emps[0], "from_day": days[0], "to_day": days[1]}

    # Case A: If user provided a time, but NO employee was matched in this turn:
    if time_str and not found_emps:
        m_p = re.search(r"(?:cho|của|bạn|nhân viên)\s+([a-zA-Zàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]+)", msg)
        if m_p:
            cand = m_p.group(1).strip()
            if cand not in NON_NAME_STOP_WORDS and cand not in ASSISTANT_VOCATIVES:
                return "unknown_employee", {"emp_raw": cand}
        if prev_emp:
            return "adjust_shift_hours", {"emp": prev_emp, "day": day or prev_day or "Monday", "shift_time": time_str}

    # Case B: If two employees mentioned:
    if len(found_emps) >= 2:
        if time_str and any(k in msg for k in ["thêm", "thêm ca", "1k", "1 k", "làm ca"]):
            target_emp = found_emps[-1]
            return "adjust_shift_hours", {"emp": target_emp, "day": day or prev_day or "Wednesday", "shift_time": time_str}
        return "swap_shifts", {"emp1": found_emps[0], "emp2": found_emps[1], "day": day or "Monday"}

    # Case C: One employee mentioned
    if len(found_emps) == 1:
        emp = found_emps[0]
        # 1. Remove shift / day off
        if any(k in msg for k in ["nghỉ", "off", "bỏ ca", "xóa ca", "cho nghỉ", "bỏ", "xóa"]):
            return "remove_shift", {"emp": emp, "day": day or prev_day or "Saturday"}

        # 2. Adjust hours / Add shift with time (full range)
        if time_str:
            return "adjust_shift_hours", {"emp": emp, "day": day or prev_day or "Monday", "shift_time": time_str}

        # 3. Adjust hours (single start or end time change)
        row = next((r for r in roster_rows if str(r.get("Employee") or "").lower() == emp.lower()), None)
        cur_shift = row.get(day or prev_day or "Wednesday", "") if row else ""
        adj_time = parse_start_end_time_adjustment(msg, cur_shift)
        if adj_time:
            return "adjust_shift_hours", {"emp": emp, "day": day or prev_day or "Wednesday", "shift_time": adj_time}

        # 4. Query / Prompt shift
        if any(k in msg for k in ["đổi ca", "thay đổi ca", "chỉnh ca", "chỉnh", "sửa", "đổi", "thay đổi", "xem ca", "ca", "thêm", "thêm ca", "1k", "1 k", "làm ca", "làm", "xếp", "xếp ca", "giờ"]):
            return "query_or_prompt_shift", {"emp": emp, "day": day or prev_day or "Monday"}

    # Case D: Greeting or mic check (ONLY when no employee was mentioned)
    if not found_emps:
        greeting_patterns = [
            r"\bhello\b", r"\bhi\b", r"\bchào\b", r"\bjoy ơi\b", r"\bem ơi\b", r"\balo\b",
            r"\bhi joy\b", r"\btroy\b", r"không nói gì", r"sao không nói", r"sao nó không nói", r"im re"
        ]
        if any(re.search(p, msg) for p in greeting_patterns):
            return "greeting", {"raw": user_message}

    return None, {}


# =========================================================================
# GEMINI 2.0 FLASH FALLBACK WITH EXPANDED TOOL DECLARATIONS
# =========================================================================

GEMINI_TOOLS_DECLARATION = [
    {
        "name": "query_employee_contact",
        "description": "Tra cứu thông tin liên hệ của nhân viên trong app: số điện thoại, email, địa chỉ nhà, ngày sinh (DOB), ngày vào làm việc.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "emp": {"type": "STRING", "description": "Tên nhân viên"},
                "query_type": {"type": "STRING", "description": "Loại thông tin: phone, email, address, dob, commencement"},
            },
            "required": ["emp"],
        },
    },
    {
        "name": "query_employee_role",
        "description": "Tra cứu vị trí, chức vụ của nhân viên trong tiệm: ai là thợ làm bánh (baker), ai phụ bánh (baker assistant), ai là nhân viên bán hàng (service staff), chủ tiệm.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "emp": {"type": "STRING", "description": "Tên nhân viên nếu hỏi cụ thể một người, hoặc để trống nếu hỏi chung"},
                "query_type": {"type": "STRING", "description": "Chức danh cần hỏi: baker, baker assistant, service staff"},
            },
        },
    },
    {
        "name": "query_unavailability_restriction",
        "description": "Tra cứu ngày nghỉ, hạn chế lịch làm việc (restrictions, availability) của nhân viên hoặc kiểm tra ai bận vào một ngày cụ thể.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "emp": {"type": "STRING", "description": "Tên nhân viên (nếu có)"},
                "day": {"type": "STRING", "description": "Ngày trong tuần (Monday - Sunday) nếu có"},
            },
        },
    },
    {
        "name": "query_shift_schedule_and_hours",
        "description": "Tra cứu lịch làm việc trên bảng Roster: ai đi làm vào thứ mấy, tổng số giờ làm trong tuần của nhân viên, xếp hạng ai làm nhiều giờ / ít giờ nhất.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "emp": {"type": "STRING", "description": "Tên nhân viên (nếu hỏi giờ của một người)"},
                "day": {"type": "STRING", "description": "Ngày trong tuần (nếu hỏi ai đi làm ngày đó)"},
                "query_type": {"type": "STRING", "description": "Loại câu hỏi: ai đi làm, tổng giờ, nhiều giờ nhất, ít giờ nhất"},
            },
        },
    },
    {
        "name": "query_holidays",
        "description": "Tra cứu các ngày nghỉ lễ công cộng (Public Holidays) và kỳ nghỉ học sinh (School Holidays) tại tiểu bang Victoria.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query_type": {"type": "STRING", "description": "Loại ngày lễ cần hỏi"},
            },
        },
    },
    {
        "name": "swap_shifts",
        "description": "Hoán đổi ca làm việc giữa 2 nhân viên trong 1 ngày cụ thể trong tuần.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "emp1": {"type": "STRING", "description": "Tên nhân viên thứ nhất"},
                "emp2": {"type": "STRING", "description": "Tên nhân viên thứ hai"},
                "day": {"type": "STRING", "description": "Ngày trong tuần (Monday - Sunday)"},
            },
            "required": ["emp1", "emp2", "day"],
        },
    },
    {
        "name": "reassign_shift",
        "description": "Chuyển ca làm việc từ một nhân viên sang cho nhân viên khác, hoặc giao ca cho nhân viên.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "from_emp": {"type": "STRING", "description": "Tên nhân viên ban đầu có ca (nếu có)"},
                "to_emp": {"type": "STRING", "description": "Tên nhân viên nhận ca"},
                "day": {"type": "STRING", "description": "Ngày trong tuần (Monday - Sunday)"},
                "shift_time": {"type": "STRING", "description": "Khung giờ ca (ví dụ: '06:00 - 14:00')"},
            },
            "required": ["to_emp", "day"],
        },
    },
    {
        "name": "adjust_shift_hours",
        "description": "Chỉnh sửa khung giờ ca làm việc của một nhân viên trong ngày cụ thể.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "emp": {"type": "STRING", "description": "Tên nhân viên"},
                "day": {"type": "STRING", "description": "Ngày trong tuần (Monday - Sunday)"},
                "shift_time": {"type": "STRING", "description": "Khung giờ mới (ví dụ: '08:00 - 13:00')"},
            },
            "required": ["emp", "day", "shift_time"],
        },
    },
    {
        "name": "remove_shift",
        "description": "Cho nhân viên nghỉ ca trong ngày cụ thể (xóa ca).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "emp": {"type": "STRING", "description": "Tên nhân viên cho nghỉ"},
                "day": {"type": "STRING", "description": "Ngày trong tuần (Monday - Sunday)"},
            },
            "required": ["emp", "day"],
        },
    },
    {
        "name": "save_manager_preference",
        "description": "Lưu thói quen, quy tắc hoặc sở thích xếp lịch của chị Nhi để áp dụng cho các tuần sau.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "emp": {"type": "STRING", "description": "Tên nhân viên liên quan"},
                "day": {"type": "STRING", "description": "Ngày trong tuần nếu có"},
                "shift_name": {"type": "STRING", "description": "Tên ca nếu có (Opening, Bake, Service, Closing)"},
                "preference": {"type": "STRING", "description": "PREFER hoặc AVOID"},
                "notes": {"type": "STRING", "description": "Tóm tắt dặn dò của chị Nhi"},
            },
            "required": ["notes"],
        },
    },
]


def call_gemini_with_tools(
    api_key: str,
    system_prompt: str,
    messages: List[Dict[str, Any]],
    model_name: str = "gemini-2.0-flash",
) -> Dict[str, Any]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": messages,
        "tools": [{"functionDeclarations": GEMINI_TOOLS_DECLARATION}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 300},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def process_assistant_chat(
    user_message: str,
    roster_rows: List[Dict[str, Any]],
    db: Any,
    session_id: str = "default",
    api_key: str = "",
) -> Dict[str, Any]:
    """
    Main Assistant entry point.
    Processes user voice/text message with omniscient app database knowledge,
    instant sub-millisecond local execution, tool calling, and Joy's Phan Rang reply.
    """
    # Auto-load latest finalized roster or draft if client passed an empty roster
    if not roster_rows and db:
        finalized = db.list_finalized_rosters()
        if finalized:
            latest_date = finalized[0]["date_str"]
            roster_rows = db.load_finalized_roster(latest_date) or []
        else:
            drafts = db.list_roster_drafts("manager")
            if drafts:
                roster_rows, _ = db.load_roster_draft(drafts[0]["date_str"], "manager")

    history = db.get_recent_chat_history(session_id, limit=6) if db else []
    learned_rules = db.get_learned_rules(active_only=True) if db else []
    memory_facts = db.get_memory_facts() if db else []

    all_emp = [str(r.get("Employee") or "").strip() for r in roster_rows] if roster_rows else []
    emp_summary = ", ".join(all_emp[:15]) if all_emp else "Robert, Viet, Aroha, Jane, Elizabeth, Anastasia, Jude, Aimi, Ainsley Mactier, Stella, Amy, Violet, Jack, Olivia, Shaelyn"

    alias_lines = []
    for k, v in PHONETIC_ALIASES.items():
        alias_lines.append(f"- {k}: thường nghe/nói là {', '.join(v[:8])}")
    alias_summary = "\n".join(alias_lines)

    rules_summary = "\n".join([f"- {r.get('notes')} ({r.get('preference')})" for r in learned_rules[:5]]) or "Chưa có quy tắc nào."
    facts_summary = "\n".join([f"- {f.get('fact_summary')}" for f in memory_facts[:5]]) or "Chưa có ghi chú đặc biệt."

    system_prompt = f"""Bạn là Joy — cô bé phụ việc trẻ tuổi (18-22 tuổi), tháo vát, thân thiện, người Phan Rang (Nam Trung Bộ) tại tiệm bánh Brumby's Pakenham.
Người đang nói chuyện với bạn là chị Nhi (vợ của chủ tiệm).

PHONG CÁCH GIAO TIẾP PHAN RANG CỦA JOY:
- Xưng: "Joy" hoặc "em". Gọi: "chị Nhi".
- Mộc mạc, gần gũi, bộc trực, không khách sáo dài dòng.
- Dùng từ đệm thân thuộc: "nè chị Nhi", "nghen chị", "rồi nhen", "xong liền nè", "dạ rồi".
- CÔNG THỨC TRẢ LỜI BẮT BUỘC KHI ĐỔI CA (Ngắn gọn nhưng ĐỦ 4 THÔNG TIN):
  1. Ai đổi cho ai
  2. Thứ mấy
  3. Mấy giờ tới mấy giờ cụ thể
  4. Tên ca làm việc nếu có.
- Ví dụ: "Xong chị ơi! Joy đổi ca thứ Tư từ 6h sáng tới 2h chiều của Shaelyn qua cho Milina rồi nghen."
- BẮT BUỘC: Khi hoàn thành một thao tác đổi ca, xóa ca, thêm ca hay điều chỉnh giờ, câu trả lời của Joy PHẢI bắt đầu bằng cụm từ: "Xong chị ơi!".

DANH SÁCH NHÂN VIÊN TIỆM: {emp_summary}

QUY ĐỔI TÊN NÓI / BIỆT DANH SANG TÊN THẬT TRÊN BẢNG ROSTER:
{alias_summary}

HỒ SƠ VÀ THÔNG TIN TOÀN DIỆN CỦA TIỆM (BẠN NẮM RÕ 100%):
- Robert: Thợ làm bánh chính (Baker), Part-time, vào làm 22/01/2024, sinh 19/02/2004.
- Viet: Chủ tiệm & Thợ bánh chính (Baker).
- Aroha: Thợ phụ bánh (Baker Assistant), Part-time, vào làm 27/09/2021, sinh 24/05/2005. Nghỉ Chủ Nhật.
- Jane: Chủ tiệm & Bán hàng (Store Owner / Service Staff).
- Ainsley Mactier: Nhân viên bán hàng, Casual, SĐT: 0479122444, Số nhà: 0359192106, Email: ainsley.mac@outlook.com, Đ/C: 8 Knapton Ave, Beaconsfield Upper, vào làm 04/10/2021, sinh 14/08/2006.
- Shaelyn: Nhân viên bán hàng, Casual, SĐT: 0466894554, Email: shaelyndean@gmail.com, Đ/C: 28 Moore Mews, sinh 25/02/2011.
- Aimi: Nhân viên bán hàng, Casual, vào làm 01/10/2023, sinh 10/11/2006.
- Elizabeth: Nhân viên bán hàng, Casual, vào làm 03/06/2024, sinh 30/07/2004.
- Anastasia: Nhân viên bán hàng, Casual, vào làm 04/10/2021, sinh 02/03/2000.
- Jude: Nhân viên bán hàng, Casual, sinh 28/04/2011, vướng lịch học các buổi chiều 4h-7h các ngày trong tuần.
- Stella: Nhân viên bán hàng, Casual, vào làm 09/01/2024, sinh 03/07/2007.
- Amy: Nhân viên bán hàng, Casual, sinh 27/02/2010.
- Violet: Nhân viên bán hàng, Casual, sinh 27/02/2010, bận trước 4h chiều các ngày trong tuần.
- Jack: Nhân viên bán hàng, Casual, sinh 28/04/2011, bận 4h30-7h tối.
- Olivia: Nhân viên bán hàng, Casual, vào làm 27/05/2024, sinh 15/01/2007.

QUY TẮC BẮT BUỘC KHI NHẬN LỆNH:
- Nếu chị Nhi hỏi thông tin cá nhân (SĐT, email, địa chỉ, ngày sinh, ngày vào làm), vị trí, ngày nghỉ (unavailability), hoặc giờ làm việc, bạn trả lời chính xác, nhiệt tình theo phong cách Phan Rang.
- Nếu chị Nhi yêu cầu đổi ca, dời ca, bỏ ca, đổi ca của A sang cho B, bạn PHẢI GỌI FUNCTION tương ứng (swap_shifts, reassign_shift, remove_shift, adjust_shift_hours).

KÝ ỨC THÓI QUEN CỦA CHỊ NHI:
{facts_summary}
QUY TẮC ĐÃ HỌC:
{rules_summary}
"""

    executed_actions = []
    final_reply = ""
    updated_roster = [dict(r) for r in roster_rows] if roster_rows else []

    # Priority 1: Instant deterministic local intent execution (< 2 milliseconds!)
    action_name, action_params = parse_intent_rule_based(user_message, updated_roster, history)
    if action_name:
        action_params["raw"] = user_message
        ok, reply, updated_roster, summary = execute_roster_action(action_name, action_params, updated_roster, db)
        if ok:
            final_reply = reply
            if action_name not in [
                "greeting",
                "query_or_prompt_shift",
                "move_shift_day_prompt",
                "query_employee_contact",
                "query_employee_role",
                "query_unavailability_restriction",
                "query_shift_schedule_and_hours",
                "query_holidays",
            ]:
                executed_actions.append(summary)

    # Priority 2: If no direct rule matched and Gemini API key is configured, call Gemini
    if not final_reply and api_key and api_key.strip():
        try:
            contents = []
            for h in history:
                role = "user" if h.get("speaker") == "manager" else "model"
                contents.append({"role": role, "parts": [{"text": h.get("message_text", "")}]})
            contents.append({"role": "user", "parts": [{"text": user_message}]})

            resp = call_gemini_with_tools(api_key.strip(), system_prompt, contents)
            cands = resp.get("candidates", [])
            if cands:
                parts = cands[0].get("content", {}).get("parts", [])
                fn_call = next((p.get("functionCall") for p in parts if "functionCall" in p), None)
                if fn_call:
                    name = fn_call.get("name")
                    args = fn_call.get("args") or {}
                    ok, reply, updated_roster, summary = execute_roster_action(name, args, updated_roster, db)
                    final_reply = reply
                    if name not in [
                        "query_employee_contact",
                        "query_employee_role",
                        "query_unavailability_restriction",
                        "query_shift_schedule_and_hours",
                        "query_holidays",
                    ]:
                        executed_actions.append(summary)
                else:
                    text_part = next((p.get("text") for p in parts if "text" in p), "")
                    final_reply = text_part.strip()
        except Exception as e:
            print(f"[Joy Assistant] Gemini API error: {e}")

    # Fallback default response
    if not final_reply:
        last_joy_msg = next((h.get("message_text", "") for h in reversed(history) if h.get("speaker") == "Joy"), "")
        if not last_joy_msg or len(history) <= 1:
            final_reply = "Dạ Joy nghe nè chị Nhi! Chị dặn Joy sửa ca bạn nào nghen!"
        else:
            final_reply = "Dạ, Joy nghe nè chị."

    # Save to chat history
    if db:
        db.save_chat_message(session_id, "manager", user_message)
        db.save_chat_message(session_id, "Joy", final_reply, executed_actions)

    return {
        "ok": True,
        "reply": final_reply,
        "actions_executed": executed_actions,
        "updated_roster": updated_roster,
        "rules_count": len(learned_rules),
    }
