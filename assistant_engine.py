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
        "jane", "chan", "chane", "trên", "chen", "zen", "dzen", "jen", "den", "gen",
        "chên", "trang", "tran", "chiên", "dane", "dzên", "gian", "giang", "san", "shane",
        "cheyn", "jain", "zane", "sen"
    ],
    "Robert": ["robert", "rô bốt", "ro bốt", "rô bớt", "ro bớt", "rô béc", "rô-bớt", "ro béc", "rô-bét"],
    "Elizabeth": [
        "elizabeth", "helizabeth", "ê li za bét", "ê li za bet", "ê li", "ê-li", "li za", "lisa", "ly za",
        "bét", "bết", "li sa", "lisa pham", "lisa phạm", "e li", "e-li", "li-za", "hê li za bét"
    ],
    "Anastasia": [
        "anastasia", "natasha", "na ta sha", "anatashia", "na ta sia", "a na", "a-na",
        "a na sờ ta sia", "na sờ ta sia", "a na sta sia", "ana"
    ],
    "Milina": ["milina", "mi li na", "mi na", "mơ li na", "mơ na", "mi-na", "melina"],
    "Violet": ["violet", "vai ô lét", "vi ô lét", "vai let", "vi let", "vai-o-let"],
    "Aimi": ["aimi", "ai mi", "ai my", "ay mi"],
    "Ainsley Mactier": ["ainsley", "mactier", "en xli", "en xly", "mắc ti er", "mác ti ơ", "en-xli", "mắc ti e", "ainsley mactier"],
    "Stella": ["stella", "sờ te la", "te la", "tét la", "ste la", "ten la"],
    "Amy": ["amy", "e mi", "ê mi", "ay mi"],
    "Jack": ["jack", "dách", "dzắc", "giắc", "dắt", "zắc", "giắt"],
    "Olivia": ["olivia", "ô li via", "li via", "ô li", "ô-li", "o li via"],
    "Shaelyn": ["shaelyn", "sê lin", "se lin", "sa lin", "sơ lin", "sa e lin", "sa-lin", "se-lin", "xe lin"],
    "Aroha": ["aroha", "a rô ha", "a ro ha", "ro ha", "a lô ha", "a-ro-ha"],
    "Viet": ["viet", "việt", "anh việt"],
    "Jude": ["jude", "dút", "dút đơ", "giu đê", "giu đe"],
}


def normalize_day(text: str) -> Optional[str]:
    low = text.lower().strip()
    for k, v in DAYS_MAP.items():
        if k in low:
            return v
    return None


def find_employees_in_text(text: str, available_names: List[str]) -> List[str]:
    """Finds all employees mentioned in text using strict word boundaries and phonetic aliases."""
    t = " " + text.lower() + " "
    found = []
    for real_name in available_names:
        first = real_name.lower().split()[0]
        aliases = [real_name.lower(), first] + PHONETIC_ALIASES.get(real_name, []) + PHONETIC_ALIASES.get(first, [])
        for a in aliases:
            pattern = (
                r"(?<![a-zA-Z0-9_àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ])"
                + re.escape(a)
                + r"(?![a-zA-Z0-9_àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ])"
            )
            m = re.search(pattern, t)
            if m:
                found.append((m.start(), real_name))
                break
    found.sort(key=lambda x: x[0])
    return [name for _, name in found]


def match_employee_name(name_query: str, available_names: List[str]) -> Optional[str]:
    q = name_query.lower().strip()
    if not q:
        return None
    matches = find_employees_in_text(q, available_names)
    if matches:
        return matches[0]
    # 1. Exact match
    for name in available_names:
        if name.lower() == q:
            return name
    # 2. Substring match
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


def parse_time_range(text: str) -> Optional[str]:
    """Extracts a normalized shift time range e.g. '12:00 - 17:00' from natural Vietnamese."""
    low = text.lower()
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


def execute_roster_action(
    action_type: str,
    params: Dict[str, Any],
    roster_rows: List[Dict[str, Any]],
    db: Any = None,
) -> Tuple[bool, str, List[Dict[str, Any]], Dict[str, Any]]:
    """
    Executes a structured action on roster_rows and returns:
    (success, phan_rang_reply, updated_roster_rows, action_summary)
    """
    if not roster_rows:
        return False, "Ủa chị Nhi ơi, hiện tại Joy chưa thấy có bảng Roster nào để chỉnh hết á!", roster_rows, {}

    all_emp_names = [str(r.get("Employee") or r.get("NAME") or r.get("Name") or "").strip() for r in roster_rows]
    day = params.get("day")
    if day:
        day = normalize_day(day) or day
    if day not in DAYS_VI_NAMES:
        day = "Monday"

    day_vi = DAYS_VI_NAMES.get(day, day)

    if action_type == "swap_shifts":
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
            reply = f"Dạ rồi! Joy đổi ca {day_vi} ({t1_vi}) của {emp1} qua cho {emp2} rồi nghen! 🥖"
        elif t1_vi == "nghỉ":
            reply = f"Dạ rồi! Joy đổi ca {day_vi} ({t2_vi}) của {emp2} qua cho {emp1} rồi nghen! 🥖"
        else:
            reply = f"Dạ rồi! Joy đổi ca {day_vi} giữa {emp1} ({t1_vi}) với {emp2} ({t2_vi}) rồi nghen! 🥖"

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
        reply = f"Dạ rồi! Ca {day_vi} {t_vi} Joy chuyển qua cho {to_emp} làm rồi nhen! ✨"
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
        reply = f"Dạ rồi! {day_vi} này Joy cho {emp} nghỉ rồi nghen! 🌸"
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
        reply = f"Dạ rồi! Ca {day_vi} của {emp} Joy cập nhật {t_vi} rồi nhen! 🌟"
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

        reply = f"Joy nhớ rồi nè chị Nhi! Từ nay Joy sẽ ưu tiên đúng ý chị dặn ({notes}) nghen! ❤️"
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

    elif action_type == "greeting":
        reply = "Dạ Joy nghe nè chị Nhi!"
        return True, reply, roster_rows, {"action": "greeting"}

    return False, "Dạ, Joy nghe nè chị.", roster_rows, {}


def parse_intent_rule_based(
    user_message: str,
    roster_rows: List[Dict[str, Any]],
    history: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[Optional[str], Dict[str, Any]]:
    """Fast, deterministic fallback parser with conversational context memory."""
    msg = user_message.lower().strip()
    all_emp = [str(r.get("Employee") or "").strip() for r in roster_rows]

    day = normalize_day(msg)
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
                d_h = normalize_day(text_h)
                if d_h:
                    prev_day = d_h
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
            matched_target = match_employee_name(cand, all_emp)
            if matched_target and matched_target.lower() != found_emps[0].lower():
                found_emps.append(matched_target)

    # Case A: If user provided a time, but NO employee was mentioned in this turn:
    if time_str and not found_emps and prev_emp:
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

        # 2. Adjust hours / Add shift with time
        if time_str:
            return "adjust_shift_hours", {"emp": emp, "day": day or prev_day or "Monday", "shift_time": time_str}

        # 3. Query / Prompt shift
        if any(k in msg for k in ["đổi ca", "thay đổi ca", "chỉnh ca", "đổi", "thay đổi", "xem ca", "ca", "thêm", "thêm ca", "1k", "1 k"]):
            return "query_or_prompt_shift", {"emp": emp, "day": day or prev_day or "Monday"}

    # Case D: Preference instruction
    if any(k in msg for k in ["nhớ", "sau này", "từ giờ", "từ nay", "ưu tiên"]):
        pref = "AVOID" if any(k in msg for k in ["đừng", "không", "hạn chế"]) else "PREFER"
        emp = found_emps[0] if found_emps else "All"
        return "save_manager_preference", {
            "emp": emp,
            "day": day or prev_day or "",
            "preference": pref,
            "weight": -100 if pref == "AVOID" else 50,
            "notes": user_message,
        }

    # Case E: Greeting
    if any(k in msg for k in ["hello", "chào", "joy ơi", "em ơi", "alo", "hi joy", "troy"]):
        return "greeting", {}

    return None, {}


GEMINI_TOOLS_DECLARATION = [
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
    model_name: str = "gemini-2.5-flash",
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
    with urllib.request.urlopen(req, timeout=12) as resp:
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
    Processes user voice/text message with 3-layer memory, runs tools,
    updates roster, and returns Joy's Phan Rang reply.
    """
    history = db.get_recent_chat_history(session_id, limit=6) if db else []
    learned_rules = db.get_learned_rules(active_only=True) if db else []
    memory_facts = db.get_memory_facts() if db else []

    all_emp = [str(r.get("Employee") or "").strip() for r in roster_rows]
    emp_summary = ", ".join(all_emp[:15])

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
- Ví dụ: "Xong rồi nè chị Nhi! Joy đổi ca thứ Tư từ 6h sáng tới 2h chiều của Shaelyn qua cho Milina rồi nghen."

DANH SÁCH NHÂN VIÊN TIỆM: {emp_summary}

QUY ĐỔI TÊN NÓI / BIỆT DANH SANG TÊN THẬT TRÊN BẢNG ROSTER:
{alias_summary}

QUY TẮC BẮT BUỘC KHI NHẬN LỆNH ĐỔI CA / THAY ĐỔI CA:
- Nếu chị Nhi yêu cầu đổi ca, dời ca, bỏ ca, đổi ca của A sang cho B (ví dụ: "đổi ca của Elizabeth ngày thứ 2 sang cho Chan" -> Chan chính là Jane!), bạn PHẢI GỌI FUNCTION tương ứng (swap_shifts, reassign_shift, remove_shift, adjust_shift_hours).
- TUYỆT ĐỐI KHÔNG hỏi lại "chị muốn đổi cho bạn nào" nếu câu nói đã chứa tên người nhận ca (như "sang cho Chan" -> Jane)! Phải gọi Function Call ngay!

KÝ ỨC THÓI QUEN CỦA CHỊ NHI:
{facts_summary}
QUY TẮC ĐÃ HỌC:
{rules_summary}
"""

    executed_actions = []
    final_reply = ""
    updated_roster = [dict(r) for r in roster_rows]

    # Try Gemini LLM if API Key is configured
    if api_key and api_key.strip():
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
                    executed_actions.append(summary)
                else:
                    text_part = next((p.get("text") for p in parts if "text" in p), "")
                    final_reply = text_part.strip()
        except Exception as e:
            print(f"[Joy Assistant] Gemini API error, falling back to pattern matcher: {e}")

    # Fallback to smart rule-based parser if no action was executed yet
    # (Catches cases where Gemini answered conversationally without triggering the tool, or no API key)
    if not executed_actions:
        action_name, action_params = parse_intent_rule_based(user_message, updated_roster, history)
        if action_name in ["swap_shifts", "reassign_shift", "remove_shift", "adjust_shift_hours", "save_manager_preference"]:
            ok, reply, updated_roster, summary = execute_roster_action(action_name, action_params, updated_roster, db)
            if ok:
                final_reply = reply
                executed_actions.append(summary)
        elif not final_reply:
            if action_name == "query_or_prompt_shift":
                ok, reply, updated_roster, summary = execute_roster_action(action_name, action_params, updated_roster, db)
                final_reply = reply
            else:
                # Check if Joy already spoke recently to avoid repeating long text
                last_joy_msg = next((h.get("message_text", "") for h in reversed(history) if h.get("speaker") == "Joy"), "")
                if not last_joy_msg or len(history) <= 1:
                    final_reply = "Dạ Joy nghe nè chị Nhi! Chị dặn Joy đổi ca bạn nào nghen!"
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
