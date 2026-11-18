import os
import sys
import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

sys.path.append(os.path.abspath('happyrolly_web'))
from database.db_manager import HappyRollyDB

db = HappyRollyDB()

DAYS_MAP = {
    "thứ 2": "Monday", "thứ hai": "Monday", "ngày thứ hai": "Monday", "t2": "Monday", "mon": "Monday", "monday": "Monday",
    "thứ 3": "Tuesday", "thứ ba": "Tuesday", "ngày thứ ba": "Tuesday", "t3": "Tuesday", "tue": "Tuesday", "tuesday": "Tuesday",
    "thứ 4": "Wednesday", "thứ tư": "Wednesday", "thứ bốn": "Wednesday", "ngày thứ tư": "Wednesday", "t4": "Wednesday", "wed": "Wednesday", "wednesday": "Wednesday",
    "thứ 5": "Thursday", "thứ năm": "Thursday", "ngày thứ năm": "Thursday", "t5": "Thursday", "thu": "Thursday", "thursday": "Thursday",
    "thứ 6": "Friday", "thứ sáu": "Friday", "ngày thứ sáu": "Friday", "t6": "Friday", "fri": "Friday", "friday": "Friday",
    "thứ 7": "Saturday", "thứ bảy": "Saturday", "ngày thứ bảy": "Saturday", "t7": "Saturday", "sat": "Saturday", "saturday": "Saturday",
    "chủ nhật": "Sunday", "chu nhat": "Sunday", "ngày chủ nhật": "Sunday", "cn": "Sunday", "sun": "Sunday", "sunday": "Sunday",
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

def parse_shift_duration_hours(shift_str: str) -> float:
    s = str(shift_str or '').strip()
    if not s or s.lower() in ['off', '-', 'nan', 'none']:
        return 0.0
    m = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*[-–]\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', s, re.IGNORECASE)
    if not m:
        return 0.0
    h1 = int(m.group(1))
    m1 = int(m.group(2) or 0)
    p1 = (m.group(3) or '').lower()
    h2 = int(m.group(4))
    m2 = int(m.group(5) or 0)
    p2 = (m.group(6) or '').lower()

    if p1 == 'pm' and h1 < 12: h1 += 12
    if p1 == 'am' and h1 == 12: h1 = 0
    if p2 == 'pm' and h2 < 12: h2 += 12
    if p2 == 'am' and h2 == 12: h2 = 0

    if not p1 and not p2:
        if h2 < h1 and h2 < 12:
            h2 += 12
    elif not p1 and p2 == 'pm':
        if h1 < 12 and h1 > (h2 - 12):
            h1 += 12

    t1 = h1 + m1 / 60.0
    t2 = h2 + m2 / 60.0
    return max(0.0, round(t2 - t1, 2))


def load_all_employee_directory(db_instance) -> Dict[str, Dict[str, Any]]:
    employees = db_instance.load_records("employees") or []
    user_profiles = db_instance.load_system_doc("user_profiles") or {}
    
    directory = {}
    
    # Process dataset records
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
        
    # Also check any user_profiles not yet in employees
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


def query_contact_info(emp_name: str, query_type: str, db_instance) -> str:
    directory = load_all_employee_directory(db_instance)
    emp_key = emp_name.lower().strip()
    
    # Match employee
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
    if any(k in query_type for k in ["phone", "mobile", "sđt", "số điện thoại", "alo", "gọi"]):
        if mobile and home_phone and mobile != home_phone:
            return f"Dạ số điện thoại của {name} là {mobile} (hoặc số nhà {home_phone}) nghen chị Nhi! 🥖"
        elif mobile:
            return f"Dạ số điện thoại của {name} là {mobile} nghen chị Nhi! 🥖"
        elif home_phone:
            return f"Dạ {name} có số liên hệ là {home_phone} nghen chị Nhi!"
        else:
            return f"Dạ chị Nhi ơi, trên hệ thống bạn {name} chưa có điền số điện thoại á!"
            
    # Email query
    if any(k in query_type for k in ["email", "thư", "mail"]):
        if email:
            return f"Dạ email của {name} là {email} nghen chị Nhi! ✉️"
        else:
            return f"Dạ chị Nhi ơi, trên app chưa có cập nhật địa chỉ email của bạn {name} nè!"
            
    # Address query
    if any(k in query_type for k in ["address", "địa chỉ", "ở đâu", "nhà"]):
        if addr:
            return f"Dạ địa chỉ nhà của {name} là: {addr} nghen chị Nhi! 🏡"
        else:
            return f"Dạ chị Nhi ơi, trong hồ sơ bạn {name} chưa có lưu địa chỉ nhà á!"
            
    # Birthday / DOB
    if any(k in query_type for k in ["dob", "sinh", "sinh nhật", "tuổi", "năm sinh"]):
        if dob:
            return f"Dạ ngày sinh của {name} là {dob} nghen chị Nhi! 🎂"
        else:
            return f"Dạ trong hồ sơ chưa có ngày sinh của bạn {name} nè chị!"
            
    # Commencement date
    if any(k in query_type for k in ["commence", "bắt đầu", "vào làm", "ngày vào"]):
        if start:
            return f"Dạ bạn {name} bắt đầu vào làm tại tiệm từ ngày {start} nghen chị! 🥖"
        else:
            return f"Dạ trong hệ thống chưa ghi nhận ngày vào làm của {name} nè chị!"

    # Full profile summary
    details = []
    if mobile: details.append(f"SĐT: {mobile}")
    if email: details.append(f"Email: {email}")
    if dob: details.append(f"Ngày sinh: {dob}")
    if pos: details.append(f"Vị trí: {pos}")
    if start: details.append(f"Vào làm: {start}")
    if addr: details.append(f"Địa chỉ: {addr}")
    
    if details:
        return f"Dạ thông tin của {name} nè chị Nhi: {', '.join(details)} nghen! 🌟"
    else:
        return f"Dạ hồ sơ của {name} hiện tại chỉ có tên trên danh sách tiệm thôi chứ chưa điền chi tiết liên hệ á chị!"


def query_unavailability_restrictions(emp_name: Optional[str], day: Optional[str], db_instance) -> str:
    unav_list = db_instance.load_records("unavailability") or []
    
    if day:
        day_vi = DAYS_VI_NAMES.get(day, day)
    else:
        day_vi = ""

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
    if not roster_rows:
        return "Dạ hiện tại Joy chưa thấy có bảng Roster nào đang mở hết á chị Nhi!"

    all_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    # Who is working on a specific day?
    if day and any(k in query_type for k in ["ai làm", "ai đi làm", "những ai", "ai có ca", "mấy người", "danh sách"]):
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
    if any(k in query_type for k in ["nhiều giờ nhất", "nhiều nhất", "top giờ", "ít giờ nhất", "ít nhất", "tổng kết giờ"]):
        hours_by_emp = []
        for r in roster_rows:
            emp = r.get("Employee") or r.get("NAME") or ""
            total_h = sum(parse_shift_duration_hours(str(r.get(d) or "")) for d in all_days)
            shifts_cnt = sum(1 for d in all_days if str(r.get(d) or "").strip() and str(r.get(d) or "").strip().lower() not in ["off", "-", "nan", "none"])
            hours_by_emp.append((emp, total_h, shifts_cnt))
            
        hours_by_emp.sort(key=lambda x: x[1], reverse=True)
        
        if "ít" in query_type:
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


# Test with sample roster rows from DB finalized_rosters
sample_roster = db.load_finalized_roster("2026-11-09") or []
print(f"Loaded finalized roster with {len(sample_roster)} rows.")

print("\n--- TEST 1: Phone number ---")
print(query_contact_info("Ainsley Mactier", "số điện thoại", db))
print(query_contact_info("Shaelyn", "số điện thoại", db))
print(query_contact_info("Aimi", "số điện thoại", db))

print("\n--- TEST 2: Email & Address ---")
print(query_contact_info("Shaelyn", "email", db))
print(query_contact_info("Ainsley", "địa chỉ", db))

print("\n--- TEST 3: Unavailability & Restrictions ---")
print(query_unavailability_restrictions("Jude", "Wednesday", db))
print(query_unavailability_restrictions("Jude", None, db))
print(query_unavailability_restrictions("Violet", "Monday", db))
print(query_unavailability_restrictions(None, "Wednesday", db))

print("\n--- TEST 4: Schedule and Hours ---")
print(query_roster_schedule_and_hours("Ainsley Mactier", None, "tổng giờ", sample_roster))
print(query_roster_schedule_and_hours(None, "Monday", "ai đi làm", sample_roster))
print(query_roster_schedule_and_hours(None, None, "nhiều giờ nhất", sample_roster))
