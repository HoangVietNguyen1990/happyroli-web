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
    "t2": "Monday",
    "mon": "Monday",
    "monday": "Monday",
    "thứ 3": "Tuesday",
    "thứ ba": "Tuesday",
    "t3": "Tuesday",
    "tue": "Tuesday",
    "tuesday": "Tuesday",
    "thứ 4": "Wednesday",
    "thứ tư": "Wednesday",
    "t4": "Wednesday",
    "wed": "Wednesday",
    "wednesday": "Wednesday",
    "thứ 5": "Thursday",
    "thứ năm": "Thursday",
    "t5": "Thursday",
    "thu": "Thursday",
    "thursday": "Thursday",
    "thứ 6": "Friday",
    "thứ sáu": "Friday",
    "t6": "Friday",
    "fri": "Friday",
    "friday": "Friday",
    "thứ 7": "Saturday",
    "thứ bảy": "Saturday",
    "t7": "Saturday",
    "sat": "Saturday",
    "saturday": "Saturday",
    "chủ nhật": "Sunday",
    "chu nhat": "Sunday",
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


def normalize_day(text: str) -> Optional[str]:
    low = text.lower().strip()
    for k, v in DAYS_MAP.items():
        if k in low:
            return v
    return None


def match_employee_name(name_query: str, available_names: List[str]) -> Optional[str]:
    q = name_query.lower().strip()
    if not q:
        return None
    # 1. Exact match
    for name in available_names:
        if name.lower() == q:
            return name
    # 2. Substring match
    for name in available_names:
        if q in name.lower() or name.lower() in q:
            return name
    # 3. First name match
    for name in available_names:
        first = name.lower().split()[0]
        if q == first or first in q:
            return name
    return None


def format_shift_time_vi(shift_str: str) -> str:
    s = str(shift_str or "").strip()
    if not s or s.lower() in ["off", "-", "nan", "none"]:
        return "nghỉ"
    # Convert '06:00 - 14:00' to 'từ 6h sáng tới 2h chiều'
    m = re.search(r"(\d{1,2}):?(\d{2})?\s*[-–]\s*(\d{1,2}):?(\d{2})?", s)
    if m:
        h1 = int(m.group(1))
        m1 = m.group(2) or "00"
        h2 = int(m.group(3))
        m2 = m.group(4) or "00"
        t1 = f"{h1}h{m1 if m1 != '00' else ''}"
        t2 = f"{h2}h{m2 if m2 != '00' else ''}"
        return f"từ {t1} tới {t2}"
    return s


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

        reply = f"Xong rồi nè chị Nhi! Joy đổi ca {day_vi} ({t1_vi}) của {emp1} qua cho {emp2} ({t2_vi}) rồi nghen! 🥖"
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
        reply = f"Dạ rồi chị Nhi! Ca {day_vi} {t_vi} Joy chuyển qua cho {to_emp} làm rồi nhen! ✨"
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
        reply = f"Dạ rồi nè chị Nhi! {day_vi} này Joy cho {emp} nghỉ ({t_vi}) rồi nghen! 🌸"
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
        reply = f"Xong liền nè chị Nhi! Ca {day_vi} của {emp} Joy cập nhật {t_vi} rồi nhen! 🌟"
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

        reply = f"Joy nhớ rồi nè chị Nhi! Từ nay về sau {day_vi if day else 'mọi tuần'} Joy sẽ ưu tiên đúng ý chị dặn ({notes}) nghen! ❤️"
        return True, reply, roster_rows, {"action": "save_manager_preference", "notes": notes}

    return False, "Chị Nhi ơi, Joy chưa rõ lệnh này lắm á, chị dặn lại Joy nghen!", roster_rows, {}


def parse_intent_rule_based(user_message: str, roster_rows: List[Dict[str, Any]]) -> Tuple[Optional[str], Dict[str, Any]]:
    """Fast, deterministic fallback parser for roster commands in Vietnamese / Phan Rang dialect."""
    msg = user_message.lower().strip()
    all_emp = [str(r.get("Employee") or "").strip() for r in roster_rows]

    day = normalize_day(msg)

    # 1. Swap shifts: "đổi ca [thứ 4] của [Shaelyn] cho/qua/sang [Milina]"
    if any(k in msg for k in ["đổi ca", "hoán đổi", "thay ca", "đổi shift", "swap"]):
        # Find all names mentioned
        found_emps = [e for e in all_emp if e.lower() in msg]
        if len(found_emps) >= 2:
            return "swap_shifts", {"emp1": found_emps[0], "emp2": found_emps[1], "day": day or "Wednesday"}

    # 2. Remove shift / give day off: "cho [Jack] nghỉ [thứ 7]" / "thứ 7 cho [Jack] nghỉ"
    if any(k in msg for k in ["nghỉ", "off", "bỏ ca", "xóa ca"]):
        found_emps = [e for e in all_emp if e.lower() in msg]
        if found_emps:
            return "remove_shift", {"emp": found_emps[0], "day": day or "Saturday"}

    # 3. Reassign: "chuyển ca [thứ 6] cho [Robert]" / "nhường ca cho [Robert]"
    if any(k in msg for k in ["chuyển ca", "giao ca", "nhường ca"]):
        found_emps = [e for e in all_emp if e.lower() in msg]
        if len(found_emps) == 1:
            return "reassign_shift", {"from_emp": "", "to_emp": found_emps[0], "day": day or "Friday"}
        elif len(found_emps) >= 2:
            return "reassign_shift", {"from_emp": found_emps[0], "to_emp": found_emps[1], "day": day or "Friday"}

    # 4. Adjust time: "cho [Aroha] làm từ 12h tới 17h [chủ nhật]"
    time_m = re.search(r"(\d{1,2}(?::\d{2}|h\d{0,2})?)\s*(?:tới|đến|-)\s*(\d{1,2}(?::\d{2}|h\d{0,2})?)", msg)
    if time_m:
        found_emps = [e for e in all_emp if e.lower() in msg]
        if found_emps:
            t1 = time_m.group(1).replace("h", ":").rstrip(":")
            if ":" not in t1:
                t1 += ":00"
            if len(t1.split(":")[0]) == 1:
                t1 = "0" + t1

            t2 = time_m.group(2).replace("h", ":").rstrip(":")
            if ":" not in t2:
                t2 += ":00"
            if len(t2.split(":")[0]) == 1:
                t2 = "0" + t2

            shift_time = f"{t1} - {t2}"
            return "adjust_shift_hours", {"emp": found_emps[0], "day": day or "Monday", "shift_time": shift_time}

    # 5. Preference instruction: "nhớ từ nay...", "sau này đừng xếp...", "ưu tiên..."
    if any(k in msg for k in ["nhớ", "sau này", "từ giờ", "từ nay", "ưu tiên"]):
        found_emps = [e for e in all_emp if e.lower() in msg]
        pref = "AVOID" if any(k in msg for k in ["đừng", "không", "hạn chế"]) else "PREFER"
        emp = found_emps[0] if found_emps else "All"
        return "save_manager_preference", {
            "emp": emp,
            "day": day or "",
            "preference": pref,
            "weight": -100 if pref == "AVOID" else 50,
            "notes": user_message,
        }

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

    # Fallback to smart rule-based parser if no API key or LLM didn't call tool
    if not final_reply:
        action_name, action_params = parse_intent_rule_based(user_message, updated_roster)
        if action_name:
            ok, reply, updated_roster, summary = execute_roster_action(action_name, action_params, updated_roster, db)
            final_reply = reply
            executed_actions.append(summary)
        else:
            final_reply = "Dạ chị Nhi ơi, Joy nghe rõ rồi nè! Chị muốn Joy đổi ca cho bạn nào, thứ mấy với mấy giờ dặn Joy nghen! 🥖"

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
