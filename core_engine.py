import calendar
import csv
import io
import json
import math
import os
import re
import sys
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

BAKERY_LAT = -38.063557
BAKERY_LON = 145.455262
DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

VIC_PUBLIC_HOLIDAYS = {
    date(2026, 1, 1): "New Year's Day",
    date(2026, 1, 26): "Australia Day",
    date(2026, 3, 9): "Labour Day",
    date(2026, 4, 3): "Good Friday",
    date(2026, 4, 4): "Easter Saturday",
    date(2026, 4, 5): "Easter Sunday",
    date(2026, 4, 6): "Easter Monday",
    date(2026, 4, 25): "ANZAC Day",
    date(2026, 6, 8): "King's Birthday",
    date(2026, 9, 25): "Friday before AFL Grand Final",
    date(2026, 11, 3): "Melbourne Cup Day",
    date(2026, 12, 25): "Christmas Day",
    date(2026, 12, 28): "Boxing Day (Observed)",
    date(2027, 1, 1): "New Year's Day",
    date(2027, 1, 26): "Australia Day",
    date(2027, 3, 8): "Labour Day",
    date(2027, 3, 26): "Good Friday",
    date(2027, 3, 27): "Easter Saturday",
    date(2027, 3, 28): "Easter Sunday",
    date(2027, 3, 29): "Easter Monday",
    date(2027, 4, 25): "ANZAC Day",
    date(2027, 6, 14): "King's Birthday",
    date(2027, 9, 24): "Friday before AFL Grand Final (TBA)",
    date(2027, 11, 2): "Melbourne Cup Day",
    date(2027, 12, 27): "Christmas Day (Observed)",
    date(2027, 12, 28): "Boxing Day (Observed)",
}

VIC_SCHOOL_HOLIDAYS = [
    {"name": "2026 Autumn School Holidays", "start": date(2026, 4, 3), "end": date(2026, 4, 19)},
    {"name": "2026 Winter School Holidays", "start": date(2026, 6, 27), "end": date(2026, 7, 12)},
    {"name": "2026 Spring School Holidays", "start": date(2026, 9, 19), "end": date(2026, 10, 4)},
    {"name": "2026-2027 Summer School Holidays", "start": date(2026, 12, 19), "end": date(2027, 1, 26)},
    {"name": "2027 Autumn School Holidays", "start": date(2027, 3, 26), "end": date(2027, 4, 11)},
    {"name": "2027 Winter School Holidays", "start": date(2027, 6, 26), "end": date(2027, 7, 11)},
    {"name": "2027 Spring School Holidays", "start": date(2027, 9, 18), "end": date(2027, 10, 3)},
    {"name": "2027-2028 Summer School Holidays", "start": date(2027, 12, 18), "end": date(2028, 1, 26)},
]

KNOWN_BAKERS = ["robert", "viet", "aroha"]
KNOWN_AGES = {
    "jane": 50,
    "robert": 45,
    "viet": 35,
    "aroha": 32,
    "elizabeth": 28,
    "anastasia": 26,
    "jude": 25,
    "esther amataiti": 24,
    "esther": 24,
    "aimi": 20,
    "ainsley mactier": 19,
    "ainsley": 19,
    "stella": 17,
    "amy": 16,
    "jack": 15,
    "shaelyn": 15,
    "olivia": 15,
}

# Strict Fair Work Ombudsman Pay Guide - General Retail Industry Award [MA000004] (Effective 01/07/2026)
PAY_GUIDE_MA000004 = {
    ("casual", "level1", "adult"): {"ord": 34.76, "eve": 41.72, "sat": 41.72, "sun": 48.67, "ph": 69.53},
    ("casual", "level1", 20): {"ord": 34.76, "eve": 41.72, "sat": 41.72, "sun": 48.67, "ph": 69.53},
    ("casual", "level1", 19): {"ord": 27.81, "eve": 33.38, "sat": 33.38, "sun": 38.94, "ph": 55.63},
    ("casual", "level1", 18): {"ord": 24.34, "eve": 29.21, "sat": 29.21, "sun": 34.07, "ph": 48.68},
    ("casual", "level1", 17): {"ord": 20.86, "eve": 25.04, "sat": 25.04, "sun": 29.21, "ph": 41.73},
    ("casual", "level1", 16): {"ord": 17.39, "eve": 20.87, "sat": 20.87, "sun": 24.34, "ph": 34.78},
    ("casual", "level1", 15): {"ord": 15.64, "eve": 18.77, "sat": 18.77, "sun": 21.89, "ph": 31.28},
    ("pt_ft", "level1", "adult"): {"ord": 27.81, "eve": 34.76, "sat": 34.76, "sun": 41.72, "ph": 62.57},
    ("pt_ft", "level1", 20): {"ord": 27.81, "eve": 34.76, "sat": 34.76, "sun": 41.72, "ph": 62.57},
    ("pt_ft", "level1", 19): {"ord": 22.25, "eve": 27.81, "sat": 27.81, "sun": 33.38, "ph": 50.06},
    ("pt_ft", "level1", 18): {"ord": 19.47, "eve": 24.34, "sat": 24.34, "sun": 29.21, "ph": 43.81},
    ("pt_ft", "level1", 17): {"ord": 16.69, "eve": 20.86, "sat": 20.86, "sun": 25.04, "ph": 37.55},
    ("pt_ft", "level1", 16): {"ord": 13.91, "eve": 17.39, "sat": 17.39, "sun": 20.87, "ph": 31.30},
    ("pt_ft", "level1", 15): {"ord": 12.51, "eve": 15.64, "sat": 15.64, "sun": 18.77, "ph": 28.15},
    ("casual", "level3", "adult"): {"ord": 36.11, "eve": 43.34, "sat": 43.34, "sun": 50.56, "ph": 72.23},
    ("casual", "level3", 20): {"ord": 36.11, "eve": 43.34, "sat": 43.34, "sun": 50.56, "ph": 72.23},
    ("casual", "level3", 19): {"ord": 28.89, "eve": 34.67, "sat": 34.67, "sun": 40.44, "ph": 57.78},
    ("casual", "level3", 18): {"ord": 25.28, "eve": 30.33, "sat": 30.33, "sun": 35.39, "ph": 50.55},
    ("casual", "level3", 17): {"ord": 21.66, "eve": 26.00, "sat": 26.00, "sun": 30.33, "ph": 43.33},
    ("casual", "level3", 16): {"ord": 18.05, "eve": 21.66, "sat": 21.66, "sun": 25.27, "ph": 36.10},
    ("casual", "level3", 15): {"ord": 16.25, "eve": 19.50, "sat": 19.50, "sun": 22.75, "ph": 32.50},
    ("pt_ft", "level3", "adult"): {"ord": 28.89, "eve": 36.11, "sat": 36.11, "sun": 43.34, "ph": 65.00},
    ("pt_ft", "level3", 20): {"ord": 28.89, "eve": 36.11, "sat": 36.11, "sun": 43.34, "ph": 65.00},
    ("pt_ft", "level3", 19): {"ord": 23.11, "eve": 28.89, "sat": 28.89, "sun": 34.67, "ph": 52.00},
    ("pt_ft", "level3", 18): {"ord": 20.22, "eve": 25.28, "sat": 25.28, "sun": 30.33, "ph": 45.50},
    ("pt_ft", "level3", 17): {"ord": 17.33, "eve": 21.66, "sat": 21.66, "sun": 26.00, "ph": 38.99},
    ("pt_ft", "level3", 16): {"ord": 14.44, "eve": 18.05, "sat": 18.05, "sun": 21.66, "ph": 32.49},
    ("pt_ft", "level3", 15): {"ord": 13.00, "eve": 16.25, "sat": 16.25, "sun": 19.50, "ph": 29.25},
}


def parse_date_robust(val: Any) -> Optional[date]:
    if not val:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    s = str(val).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    return None


def to_date_obj(dt_val: Any) -> Optional[date]:
    return parse_date_robust(dt_val)


def is_vic_public_holiday(value: Any) -> Tuple[bool, str]:
    name = VIC_PUBLIC_HOLIDAYS.get(to_date_obj(value))
    return bool(name), str(name or "")


def is_vic_school_holiday(value: Any) -> Tuple[bool, str]:
    day = to_date_obj(value)
    if day:
        for holiday in VIC_SCHOOL_HOLIDAYS:
            if holiday["start"] <= day <= holiday["end"]:
                return True, str(holiday["name"])
    return False, ""


def get_week_holiday_notices(start_date_str: str) -> Dict[str, List[str]]:
    start_dt = parse_date_robust(start_date_str) or date.today()
    pubs = []
    schools = []
    for idx in range(7):
        cur_d = start_dt + timedelta(days=idx)
        is_p, p_name = is_vic_public_holiday(cur_d)
        if is_p:
            pubs.append(f"{p_name} ({cur_d.strftime('%d/%m/%Y')})")
        is_s, s_name = is_vic_school_holiday(cur_d)
        if is_s and s_name not in schools:
            schools.append(s_name)
    return {"public_holidays": pubs, "school_holidays": schools}


def calculate_haversine_distance(lat1: float, lon1: float, lat2: float = BAKERY_LAT, lon2: float = BAKERY_LON) -> float:
    r_earth = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * r_earth * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def calculate_award_break(shift_hours: float) -> Tuple[int, str]:
    if shift_hours < 4.0:
        return 0, "No break required (< 4 hrs)"
    elif shift_hours < 5.0:
        return 10, "10 min Paid Rest Break (4-5 hrs)"
    elif shift_hours < 7.0:
        return 30, "30 min Unpaid Meal Break + 10 min Rest (5-7 hrs)"
    elif shift_hours < 10.0:
        return 30, "30 min Unpaid Meal Break + 20 min Rest (7-10 hrs)"
    else:
        return 60, "2 x 30 min Unpaid Meal Breaks (10+ hrs)"


def get_employee_team(emp_name: str, role_str: str = "") -> str:
    emp_lower = str(emp_name or "").strip().lower()
    if any(b in emp_lower for b in KNOWN_BAKERS):
        return "Baking Team"
    role_lower = str(role_str or "").strip().lower()
    if any(kw in role_lower for kw in ("baker", "baking", "pastry")):
        return "Baking Team"
    return "Service Team"


def get_employee_sort_key(emp_name: str, role_str: str = "", age_val: Any = None) -> Tuple[int, int, str]:
    emp_clean = str(emp_name or "").strip()
    if not emp_clean or emp_clean.lower() in ("none", "nan", "total", "summary", ""):
        return (99, 0, "")
    emp_lower = emp_clean.lower()
    team = get_employee_team(emp_clean, role_str)
    team_code = 0 if team == "Baking Team" else 1

    age = KNOWN_AGES.get(emp_lower)
    if age is None:
        for k, v in KNOWN_AGES.items():
            if k in emp_lower:
                age = v
                break
    if age is None and age_val is not None:
        try:
            age = int(float(str(age_val)))
        except ValueError:
            age = None
    if age is None:
        age = 21
    return (team_code, -age, emp_lower)


def sort_records_by_team_and_age(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not records:
        return []

    def _row_key(row: Dict[str, Any]):
        nr = {str(k).strip().lower(): v for k, v in row.items()}
        name = str(nr.get("employee") or nr.get("name") or nr.get("staff member") or nr.get("staff name") or "").strip()
        role = str(nr.get("role") or nr.get("position") or nr.get("team") or "").strip()
        age = nr.get("age")
        return get_employee_sort_key(name, role, age)

    return sorted(records, key=_row_key)


def extract_date_range(text: str) -> Tuple[Optional[date], Optional[date]]:
    if not text or str(text).strip().lower() in ("nan", "none", "nat", ""):
        return None, None
    s = str(text)
    dates_found = []
    for m in re.findall(r"\b\d{1,4}[-/\.]\d{1,2}[-/\.]\d{2,4}\b", s):
        d = parse_date_robust(m)
        if d:
            dates_found.append(d)
    if len(dates_found) >= 2:
        return min(dates_found), max(dates_found)
    elif len(dates_found) == 1:
        low = s.lower()
        if any(kw in low for kw in ("from", "after", "since", "starting")):
            return dates_found[0], None
        elif any(kw in low for kw in ("until", "to", "before", "ending")):
            return None, dates_found[0]
        return dates_found[0], dates_found[0]
    return None, None


def is_unavail_applicable_to_date(dt_obj: date, u_day: str, u_win: str) -> bool:
    u_day_clean = str(u_day or "").strip()
    u_win_clean = str(u_win or "").strip()
    if not u_day_clean:
        return False

    start_d, end_d = extract_date_range(f"{u_day_clean} {u_win_clean}")
    if start_d and dt_obj < start_d:
        return False
    if end_d and dt_obj > end_d:
        return False

    explicit_date = parse_date_robust(u_day_clean)
    if explicit_date:
        return dt_obj == explicit_date

    weekday_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    dt_day_name = weekday_names[dt_obj.weekday()]
    dt_day_short = dt_day_name[:3]
    u_day_lower = u_day_clean.lower()

    if dt_day_name in u_day_lower or dt_day_short in u_day_lower:
        return True
    if any(kw in u_day_lower for kw in ("all week", "everyday", "any day")):
        return True
    if "weekend" in u_day_lower and dt_obj.weekday() in (5, 6):
        return True
    if "weekday" in u_day_lower and dt_obj.weekday() in (0, 1, 2, 3, 4):
        return True
    return False


def clean_win_display(win_str: str) -> str:
    s = str(win_str or "").strip()
    s = re.sub(r"\(From\s+.*?\)", "", s, flags=re.IGNORECASE).strip()
    return s if s else "All Day"


def build_monthly_unavailability_grid(
    year: int,
    month: int,
    unavailability: List[Dict[str, Any]],
    employees: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Builds the 7-column (Mon-Sun) Monthly Calendar Grid Matrix & filtered employee breakdown."""
    cal = calendar.Calendar(firstweekday=0)
    month_weeks = cal.monthdayscalendar(year, month)

    name_map = {}
    for e in employees or []:
        ne = {str(k).strip().lower(): v for k, v in e.items()}
        n = str(ne.get("name") or ne.get("employee") or "").strip()
        if n:
            name_map[n.lower()] = n

    clean_unavail = []
    for r in unavailability or []:
        nr = {str(k).strip().lower(): v for k, v in r.items()}
        emp = str(nr.get("employee") or nr.get("name") or "").strip()
        day_s = str(nr.get("day") or nr.get("date") or "").strip()
        win_s = str(nr.get("time window") or nr.get("window") or "All Day").strip()
        if emp and day_s and emp.lower() not in ("nan", "none"):
            matched = find_matching_employee(emp, name_map) or emp
            clean_unavail.append({"Employee": matched, "Day": day_s, "Time Window": win_s})

    clean_unavail = sort_records_by_team_and_age(clean_unavail)

    weeks_matrix = []
    month_active_rows = []
    seen_active = set()

    for week in month_weeks:
        week_cells = []
        for day_num in week:
            if day_num == 0:
                week_cells.append({"day": 0, "chips": []})
            else:
                dt_obj = date(year, month, day_num)
                chips = []
                for idx_u, urow in enumerate(clean_unavail):
                    if is_unavail_applicable_to_date(dt_obj, urow["Day"], urow["Time Window"]):
                        badge_win = clean_win_display(urow["Time Window"])
                        is_all_day = "all day" in badge_win.lower()
                        chips.append(
                            {
                                "employee": urow["Employee"],
                                "window": badge_win,
                                "raw_window": urow["Time Window"],
                                "type": "all_day" if is_all_day else "partial",
                            }
                        )
                        sig = (urow["Employee"], urow["Day"], urow["Time Window"])
                        if sig not in seen_active:
                            seen_active.add(sig)
                            month_active_rows.append(urow)
                week_cells.append({"day": day_num, "date": dt_obj.isoformat(), "chips": chips})
        weeks_matrix.append(week_cells)

    return {
        "year": year,
        "month": month,
        "month_name": f"{calendar.month_name[month]} {year}",
        "weeks": weeks_matrix,
        "month_breakdown": sort_records_by_team_and_age(month_active_rows),
        "all_records": clean_unavail,
    }


def parse_time_to_decimal(time_str: str) -> float:
    s = str(time_str).strip().lower().replace(".", ":")
    is_pm = "pm" in s or "p" in s
    is_am = "am" in s or "a" in s
    s = re.sub(r"[^0-9:]", "", s)
    if not s:
        return 0.0
    parts = s.split(":")
    hrs = int(parts[0]) if parts[0] else 0
    mins = int(parts[1]) if len(parts) > 1 and parts[1] else 0
    if is_pm and hrs < 12:
        hrs += 12
    elif is_am and hrs == 12:
        hrs = 0
    elif not is_am and not is_pm and hrs < 7:
        hrs += 12
    return hrs + (mins / 60.0)


def parse_shift_range(shift_str: str) -> Optional[Tuple[float, float, float]]:
    if not shift_str:
        return None
    s = str(shift_str).strip().lower()
    if s in ("", "off", "unavailable", "none", "nan") or "unavail" in s or s.startswith("🚫"):
        return None
    # Strip any trailing unavailability annotation badge when parsing shift times
    s = re.sub(r"\(🚫.*?\)", "", s).strip()
    if "-" not in s:
        return None
    parts = s.split("-", 1)
    try:
        start = parse_time_to_decimal(parts[0])
        end = parse_time_to_decimal(parts[1])
        if end <= start:
            if end < 12:
                end += 12
            if end <= start:
                end += 12
        duration = end - start
        return start, end, duration
    except Exception:
        return None


def is_overlapping_unavailability(unavail_str: str, shift_start: float, shift_end: float) -> bool:
    u = clean_win_display(unavail_str).strip().lower()
    if "all day" in u or "anytime" in u:
        return True
    if "before" in u:
        t = parse_time_to_decimal(u.replace("before", "").strip())
        return shift_start < t
    if "after" in u:
        t = parse_time_to_decimal(u.replace("after", "").strip())
        return shift_end > t
    r = parse_shift_range(u)
    if r:
        u_start, u_end, _ = r
        return max(shift_start, u_start) < min(shift_end, u_end)
    return False


def find_matching_employee(query_name: str, name_map: Dict[str, str]) -> Optional[str]:
    q = str(query_name).strip().lower()
    if not q:
        return None
    if q in name_map:
        return name_map[q]
    aliases = {"ana": "anastasia", "ainsley": "ainsley mactier", "esther": "esther amataiti"}
    if q in aliases and aliases[q] in name_map:
        return name_map[aliases[q]]
    for norm_key, orig_name in name_map.items():
        if q in norm_key or norm_key in q or norm_key.split()[0] == q.split()[0]:
            return orig_name
    return None


def annotate_roster_with_unavailability(
    roster_rows: List[Dict[str, Any]],
    unavailability: List[Dict[str, Any]],
    start_date_str: str,
) -> Dict[Tuple[str, str], str]:
    """Returns a map of (employee_lower, day_name) -> unavailability badge text for the target week."""
    start_dt = parse_date_robust(start_date_str) or date.today()
    name_map = {str(r.get("Employee") or r.get("Name") or "").strip().lower(): str(r.get("Employee") or r.get("Name") or "").strip() for r in roster_rows}
    badges: Dict[Tuple[str, str], List[str]] = {}

    for urow in unavailability or []:
        nu = {str(k).strip().lower(): v for k, v in urow.items()}
        raw_emp = str(nu.get("employee") or nu.get("name") or "").strip()
        u_day = str(nu.get("day") or nu.get("date") or "").strip()
        u_win = str(nu.get("time window") or nu.get("window") or "All Day").strip()
        matched = find_matching_employee(raw_emp, name_map) or raw_emp
        if not matched or not u_day:
            continue
        for idx, day in enumerate(DAYS_OF_WEEK):
            day_dt = start_dt + timedelta(days=idx)
            if is_unavail_applicable_to_date(day_dt, u_day, u_win):
                badges.setdefault((matched.lower(), day), []).append(clean_win_display(u_win))

    return {k: ", ".join(dict.fromkeys(v)) for k, v in badges.items()}


def solve_roster_records(
    employees: List[Dict[str, Any]],
    unavailability: List[Dict[str, Any]],
    requirements: List[Dict[str, Any]],
    fixed: List[Dict[str, Any]],
    start_date_str: str,
    learned_rules: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Pure-Python Roster Solver adhering strictly to General Retail Award MA000004 & Bakery rules."""
    start_dt = parse_date_robust(start_date_str) or date.today()

    active_employees = []
    for row in employees:
        norm_row = {str(k).strip().lower(): v for k, v in row.items()}
        raw_name = str(norm_row.get("name") or norm_row.get("employee") or "").strip()
        if not raw_name or raw_name.lower() in ("nan", "") or "demo" in raw_name.lower():
            continue

        start_val = norm_row.get("start date") or norm_row.get("commencement date")
        if start_val:
            st_dt = parse_date_robust(start_val)
            if st_dt and st_dt > start_dt:
                continue

        age = KNOWN_AGES.get(raw_name.lower(), 25)
        raw_age = norm_row.get("age")
        if raw_age:
            try:
                age = int(float(str(raw_age)))
            except ValueError:
                pass

        emp_type = str(norm_row.get("employment type") or norm_row.get("status") or "Casual").strip()
        role = str(norm_row.get("role") or norm_row.get("position") or "Service").strip()
        active_employees.append(
            {
                "Name": raw_name,
                "NormalizedName": raw_name.lower(),
                "Age": age,
                "Type": emp_type,
                "Role": role,
            }
        )

    if not active_employees:
        return []

    name_map = {e["NormalizedName"]: e["Name"] for e in active_employees}
    roster_output = {e["Name"]: {d: "" for d in DAYS_OF_WEEK} for e in active_employees}
    weekly_shifts_count = {e["Name"]: 0 for e in active_employees}
    elizabeth_weekday_shifts = 0

    # 1. Fixed baseline shifts
    for fix_row in fixed:
        norm_fix = {str(k).strip().lower(): v for k, v in fix_row.items()}
        raw_fixed_name = str(norm_fix.get("employee") or norm_fix.get("name") or "").strip()
        matched_name = find_matching_employee(raw_fixed_name, name_map)
        if matched_name:
            for day in DAYS_OF_WEEK:
                val = str(norm_fix.get(day.lower(), "")).strip()
                if val.lower() not in ("", "off", "nan", "none"):
                    roster_output[matched_name][day] = val
                    weekly_shifts_count[matched_name] += 1
                    if matched_name == "Elizabeth" and day not in ("Saturday", "Sunday"):
                        elizabeth_weekday_shifts += 1

    # 2. Unavailability mapping
    unavail_map: Dict[Tuple[str, str], List[str]] = {}
    for un_row in unavailability:
        norm_un = {str(k).strip().lower(): v for k, v in un_row.items()}
        raw_un_name = str(norm_un.get("employee") or norm_un.get("name") or "").strip()
        un_day = str(norm_un.get("day") or norm_un.get("date") or "").strip()
        window = str(norm_un.get("time window") or norm_un.get("window") or "All Day").strip()
        matched_name = find_matching_employee(raw_un_name, name_map)
        if matched_name and un_day:
            for idx, day in enumerate(DAYS_OF_WEEK):
                day_date = start_dt + timedelta(days=idx)
                if is_unavail_applicable_to_date(day_date, un_day, window):
                    key = (matched_name.lower(), day.lower())
                    unavail_map.setdefault(key, []).append(window)

    # 3. Day-by-day scheduling
    for idx, day in enumerate(DAYS_OF_WEEK):
        day_date = start_dt + timedelta(days=idx)
        is_pub, _ = is_vic_public_holiday(day_date)
        is_school_hol, _ = is_vic_school_holiday(day_date)

        if is_pub:
            for emp in active_employees:
                roster_output[emp["Name"]][day] = ""
            continue

        shifts_to_fill = []
        for req in requirements:
            norm_req = {str(k).strip().lower(): v for k, v in req.items()}
            shift_str = str(norm_req.get("shift") or norm_req.get("time") or "").strip()
            if not shift_str:
                continue
            parsed = parse_shift_range(shift_str)
            if not parsed:
                continue
            start_t, end_t, dur = parsed

            count = 0
            if day.lower() in norm_req:
                try:
                    count = int(float(str(norm_req[day.lower()] or 0)))
                except ValueError:
                    count = 0
            elif str(norm_req.get("day", "")).strip().lower().startswith(day[:3].lower()):
                try:
                    count = int(float(str(norm_req.get("count required") or norm_req.get("count") or 1)))
                except ValueError:
                    count = 1
            for _ in range(max(0, count)):
                shifts_to_fill.append({"shift": shift_str, "start": start_t, "end": end_t, "duration": dur})

        fixed_today = [
            roster_output[name][day]
            for name in roster_output
            if roster_output[name][day] not in ("", "off", " unavailable")
        ]
        remaining = []
        for s_req in shifts_to_fill:
            matched_idx = -1
            for f_i, f_val in enumerate(fixed_today):
                f_parsed = parse_shift_range(f_val)
                if f_parsed and abs(f_parsed[0] - s_req["start"]) < 0.05 and abs(f_parsed[1] - s_req["end"]) < 0.05:
                    matched_idx = f_i
                    break
            if matched_idx >= 0:
                fixed_today.pop(matched_idx)
            else:
                remaining.append(s_req)

        remaining.sort(key=lambda x: x["duration"], reverse=True)

        for shift_info in remaining:
            best_candidate = None
            best_score = -999999.0

            for emp in active_employees:
                name = emp["Name"]
                norm_name = emp["NormalizedName"]
                age = emp["Age"]

                if roster_output[name][day] != "":
                    continue
                if weekly_shifts_count[name] >= 5:
                    continue

                windows = unavail_map.get((norm_name, day.lower()), [])
                if any(is_overlapping_unavailability(w, shift_info["start"], shift_info["end"]) for w in windows):
                    continue

                if name == "Elizabeth":
                    if day in ("Saturday", "Sunday") or elizabeth_weekday_shifts >= 2:
                        continue

                if age < 18 and day not in ("Saturday", "Sunday") and not is_school_hol:
                    if max(shift_info["start"], 9.0) < min(shift_info["end"], 15.5):
                        continue

                score = -weekly_shifts_count[name] * 20.0
                if age < 21:
                    score += (21 - age) * shift_info["duration"] * 2.0
                if name == "Elizabeth" and shift_info["start"] in (7.0, 7.5):
                    score += 100.0

                if learned_rules:
                    for rule in learned_rules:
                        r_emp = str(rule.get("employee") or "").strip().lower()
                        if r_emp in ("all", norm_name):
                            r_day = str(rule.get("day") or "").strip().lower()
                            if not r_day or r_day.startswith(day[:3].lower()) or r_day == day.lower():
                                pref = str(rule.get("preference") or "PREFER").upper()
                                weight = float(rule.get("weight_score") or 50.0)
                                if pref in ("AVOID", "NEVER"):
                                    score -= abs(weight)
                                else:
                                    score += abs(weight)

                if score > best_score:
                    best_score = score
                    best_candidate = name

            if best_candidate:
                roster_output[best_candidate][day] = shift_info["shift"]
                weekly_shifts_count[best_candidate] += 1
                if best_candidate == "Elizabeth" and day not in ("Saturday", "Sunday"):
                    elizabeth_weekday_shifts += 1

    result_rows = []
    for emp in active_employees:
        name = emp["Name"]
        row = {"Employee": name}
        for day in DAYS_OF_WEEK:
            row[day] = roster_output[name].get(day, "")
        result_rows.append(row)
    return sort_records_by_team_and_age(result_rows)


def calculate_weekly_hour_rate_breakdown_records(roster_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Calculates Sub-Tab 2: Early (<7am), Late (>6pm), Ordinary (7am-6pm), Saturday, Sunday & Laundry Allowance ($1.28/shift)."""
    records = []
    for row in roster_rows or []:
        emp_raw_name = str(row.get("Employee") or row.get("Name") or "").strip()
        if (
            not emp_raw_name
            or emp_raw_name.lower() in ("none", "nan", "total", "summary")
            or "💰" in emp_raw_name
            or "predicted" in emp_raw_name.lower()
        ):
            continue

        early_hrs = 0.0
        late_hrs = 0.0
        ord_hrs = 0.0
        sat_hrs = 0.0
        sun_hrs = 0.0
        shifts_count = 0

        for day in DAYS_OF_WEEK:
            shift_val = str(row.get(day, "")).strip()
            parsed = parse_shift_range(shift_val)
            if parsed:
                start_t, end_t, duration = parsed
                shifts_count += 1
                if day == "Saturday":
                    sat_hrs += duration
                elif day == "Sunday":
                    sun_hrs += duration
                else:
                    early_raw = max(0.0, min(end_t, 7.0) - start_t)
                    late_raw = max(0.0, end_t - max(start_t, 18.0))
                    ord_start = max(start_t, 7.0)
                    ord_end = min(end_t, 18.0)
                    ord_raw = max(0.0, ord_end - ord_start) if ord_end > ord_start else 0.0

                    early_hrs += early_raw
                    late_hrs += late_raw
                    ord_hrs += ord_raw

        laundry_allowance = round(shifts_count * 1.28, 2)
        records.append(
            {
                "staff name": emp_raw_name,
                "early hour": round(early_hrs, 2),
                "late hour": round(late_hrs, 2),
                "ordinary hour": round(ord_hrs, 2),
                "saturday": round(sat_hrs, 2),
                "sunday": round(sun_hrs, 2),
                "laundry allowance": f"${laundry_allowance:.2f}",
            }
        )

    records.sort(key=lambda r: str(r["staff name"]).lower())
    if records:
        tot_early = sum(r["early hour"] for r in records)
        tot_late = sum(r["late hour"] for r in records)
        tot_ord = sum(r["ordinary hour"] for r in records)
        tot_sat = sum(r["saturday"] for r in records)
        tot_sun = sum(r["sunday"] for r in records)
        tot_laundry = sum(float(str(r["laundry allowance"]).replace("$", "")) for r in records)
        records.append(
            {
                "staff name": "💰 TOTAL SUMMARY",
                "early hour": round(tot_early, 2),
                "late hour": round(tot_late, 2),
                "ordinary hour": round(tot_ord, 2),
                "saturday": round(tot_sat, 2),
                "sunday": round(tot_sun, 2),
                "laundry allowance": f"${tot_laundry:.2f}",
            }
        )
    return records


def generate_xero_timesheet_csv_str(hour_breakdown: List[Dict[str, Any]]) -> str:
    rows = []
    for r in hour_breakdown or []:
        emp = str(r.get("staff name", "")).strip()
        if not emp or "TOTAL" in emp.upper() or "SUMMARY" in emp.upper():
            continue
        ord_h = float(r.get("ordinary hour", 0.0) or 0.0)
        sat_h = float(r.get("saturday", 0.0) or 0.0)
        sun_h = float(r.get("sunday", 0.0) or 0.0)
        early_h = float(r.get("early hour", 0.0) or 0.0)
        late_h = float(r.get("late hour", 0.0) or 0.0)
        laundry_val = float(str(r.get("laundry allowance", "$0.00")).replace("$", "").strip() or 0.0)

        if ord_h > 0:
            rows.append({"Employee Name": emp, "Earnings Rate": "Ordinary Hours", "Hours": ord_h})
        if sat_h > 0:
            rows.append({"Employee Name": emp, "Earnings Rate": "Saturday Penalty", "Hours": sat_h})
        if sun_h > 0:
            rows.append({"Employee Name": emp, "Earnings Rate": "Sunday Penalty", "Hours": sun_h})
        if early_h > 0:
            rows.append({"Employee Name": emp, "Earnings Rate": "Early Morning Shift", "Hours": early_h})
        if late_h > 0:
            rows.append({"Employee Name": emp, "Earnings Rate": "Late Shift", "Hours": late_h})
        if laundry_val > 0:
            rows.append({"Employee Name": emp, "Earnings Rate": "Laundry Allowance", "Hours": laundry_val})

    if not rows:
        return ""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["Employee Name", "Earnings Rate", "Hours"])
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def generate_xero_autofill_js_str(hour_breakdown: List[Dict[str, Any]]) -> str:
    data_records = []
    for row in hour_breakdown or []:
        emp_name = str(row.get("staff name", "")).strip()
        if not emp_name or "TOTAL" in emp_name.upper() or "SUMMARY" in emp_name.upper():
            continue
        data_records.append(
            {
                "name": emp_name,
                "early": float(row.get("early hour", 0.0) or 0.0),
                "late": float(row.get("late hour", 0.0) or 0.0),
                "ordinary": float(row.get("ordinary hour", 0.0) or 0.0),
                "saturday": float(row.get("saturday", 0.0) or 0.0),
                "sunday": float(row.get("sunday", 0.0) or 0.0),
                "laundry": str(row.get("laundry allowance", "$0.00")).replace("$", "").strip(),
            }
        )
    json_str = json.dumps(data_records, indent=2)
    return f"""// Paste into Browser DevTools Console (F12 -> Console) on Xero Pay Run page:
(function() {{
  const staffData = {json_str};
  console.log("🥐 Brumby's Bakery - Xero Payroll Auto-Fill Triggered", staffData);
  staffData.forEach(emp => {{
    const rows = Array.from(document.querySelectorAll('tr, [role="row"]'));
    rows.forEach(r => {{
      if (r.innerText && r.innerText.toLowerCase().includes(emp.name.toLowerCase())) {{
        const inputs = r.querySelectorAll('input[type="text"], input[type="number"]');
        if (inputs.length > 0) {{
          inputs[0].value = emp.ordinary;
          inputs[0].dispatchEvent(new Event('input', {{ bubbles: true }}));
          inputs[0].dispatchEvent(new Event('change', {{ bubbles: true }}));
        }}
      }}
    }});
  }});
}})();"""


def calculate_age_from_dob(dob_val: Any, ref_date: Optional[date] = None) -> Optional[int]:
    dt = parse_date_robust(dob_val)
    if not dt:
        return None
    today = ref_date or date.today()
    return today.year - dt.year - ((today.month, today.day) < (dt.month, dt.day))


def calculate_wages_records(
    roster_rows: List[Dict[str, Any]],
    employees: List[Dict[str, Any]],
    user_profiles: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Calculates Weekly Gross, Tax, Net, Super (12.5%), Daily Gross, Hour Rate Breakdown & Xero exports."""
    emp_meta: Dict[str, Dict[str, Any]] = {}
    for r in employees or []:
        nr = {str(k).strip().lower(): v for k, v in r.items()}
        name = str(nr.get("name") or nr.get("employee") or "").strip()
        if not name:
            continue
        age = calculate_age_from_dob(nr.get("dob") or nr.get("date of birth"))
        if age is None:
            age = KNOWN_AGES.get(name.lower(), 21)
            try:
                if nr.get("age"):
                    age = int(float(str(nr["age"])))
            except ValueError:
                pass
        status = str(nr.get("employment type") or nr.get("status") or "Casual").strip().lower()
        role = str(nr.get("role") or nr.get("position") or "Service").strip()
        emp_meta[name.lower()] = {"name": name, "age": age, "status": status, "role": role}

    if isinstance(user_profiles, dict):
        for u_key, u_data in user_profiles.items():
            if not isinstance(u_data, dict):
                continue
            emp_name = str(u_data.get("employee_name", u_key)).strip()
            prof = u_data.get("profile", {}) if isinstance(u_data.get("profile"), dict) else {}
            status = str(prof.get("classification", "Casual")).strip().lower()
            if emp_name.lower() not in emp_meta:
                emp_meta[emp_name.lower()] = {
                    "name": emp_name,
                    "age": KNOWN_AGES.get(emp_name.lower(), 21),
                    "status": status,
                    "role": str(prof.get("employment_level", "Service")),
                }

    emp_summary = []
    daily_gross_totals = {d: 0.0 for d in DAYS_OF_WEEK}

    for row in roster_rows or []:
        emp_raw_name = str(row.get("Employee") or row.get("Name") or "").strip()
        if (
            not emp_raw_name
            or emp_raw_name.lower() in ("none", "nan", "total", "summary")
            or "💰" in emp_raw_name
            or "predicted" in emp_raw_name.lower()
        ):
            continue

        meta = emp_meta.get(
            emp_raw_name.lower(),
            {
                "name": emp_raw_name,
                "age": KNOWN_AGES.get(emp_raw_name.lower(), 21),
                "status": "casual",
                "role": "Service",
            },
        )
        age = meta["age"]
        status_clean = meta["status"].lower()
        emp_name_lower = emp_raw_name.lower()

        is_viet_or_jane = any(k in emp_name_lower for k in ("viet", "jane")) or "owner" in status_clean
        is_casual = is_viet_or_jane or "casual" in status_clean
        emp_type = "casual" if is_casual else "pt_ft"

        if "robert" in emp_name_lower or is_viet_or_jane:
            lvl = "level1"
        else:
            lvl = "level3" if "level 3" in status_clean else "level1"

        age_key = "adult" if age >= 21 else (age if age in (15, 16, 17, 18, 19, 20) else (15 if age < 15 else "adult"))
        rates = PAY_GUIDE_MA000004.get((emp_type, lvl, age_key), PAY_GUIDE_MA000004[("casual", "level1", "adult")])

        total_emp_hours = 0.0
        total_emp_gross = 0.0

        for day in DAYS_OF_WEEK:
            shift_val = str(row.get(day, "")).strip()
            parsed = parse_shift_range(shift_val)
            if parsed:
                start_t, end_t, duration = parsed
                paid_hrs = duration - 0.5 if duration >= 5.0 else duration
                total_emp_hours += paid_hrs

                if day == "Saturday":
                    day_gross = paid_hrs * rates["sat"]
                elif day == "Sunday":
                    day_gross = paid_hrs * rates["sun"]
                else:
                    if end_t <= 18.0:
                        day_gross = paid_hrs * rates["ord"]
                    elif start_t >= 18.0:
                        day_gross = paid_hrs * rates["eve"]
                    else:
                        pre_6 = max(0.0, 18.0 - start_t)
                        post_6 = max(0.0, end_t - 18.0)
                        ratio = (paid_hrs / duration) if duration >= 5.0 else 1.0
                        day_gross = (pre_6 * ratio * rates["ord"]) + (post_6 * ratio * rates["eve"])

                total_emp_gross += day_gross
                daily_gross_totals[day] += day_gross

        g = total_emp_gross
        if g <= 359:
            tax = 0.0
        elif g <= 865:
            tax = (g - 359) * 0.19
        elif g <= 2500:
            tax = 96.14 + (g - 865) * 0.325
        else:
            tax = 627.51 + (g - 2500) * 0.37

        net_pay = max(0.0, g - tax)
        super_sg = 0.0 if (age < 18 and total_emp_hours <= 30.0) else (g * 0.125)

        if is_viet_or_jane:
            status_label = "Casual Lvl 1 (Owner)"
        elif "robert" in emp_name_lower:
            status_label = "Part-Time (Baker Lvl 1)"
        else:
            status_label = "Casual" if is_casual else ("Part-Time" if "part" in status_clean else "Full-Time")
            if age < 21:
                status_label += f" ({age}yo)"

        emp_team = get_employee_team(emp_raw_name, meta.get("role", ""))
        emp_summary.append(
            {
                "Staff Member": emp_raw_name,
                "Team": emp_team,
                "Status": status_label,
                "Paid Hours": round(total_emp_hours, 1),
                "Gross Pay": round(total_emp_gross, 2),
                "Est. Tax": round(tax, 2),
                "Net Pay": round(net_pay, 2),
                "Super (12.5%)": round(super_sg, 2),
            }
        )

    emp_summary = sort_records_by_team_and_age(emp_summary)
    tot_gross = sum(x["Gross Pay"] for x in emp_summary)
    tot_tax = sum(x["Est. Tax"] for x in emp_summary)
    tot_net = sum(x["Net Pay"] for x in emp_summary)
    tot_super = sum(x["Super (12.5%)"] for x in emp_summary)
    tot_hrs = sum(x["Paid Hours"] for x in emp_summary)
    avg_rate = (tot_gross / tot_hrs) if tot_hrs > 0 else 0.0

    hour_breakdown = calculate_weekly_hour_rate_breakdown_records(roster_rows)
    xero_csv = generate_xero_timesheet_csv_str(hour_breakdown)
    xero_js = generate_xero_autofill_js_str(hour_breakdown)

    return {
        "total_gross": round(tot_gross, 2),
        "total_tax": round(tot_tax, 2),
        "total_net": round(tot_net, 2),
        "total_super": round(tot_super, 2),
        "total_hours": round(tot_hrs, 1),
        "avg_hourly_rate": round(avg_rate, 2),
        "daily_gross": {d: round(daily_gross_totals[d], 2) for d in DAYS_OF_WEEK},
        "breakdown": emp_summary,
        "hour_rate_breakdown": hour_breakdown,
        "xero_csv": xero_csv,
        "xero_js": xero_js,
    }


def build_historical_payroll_trends(
    all_rosters: List[Tuple[str, List[Dict[str, Any]]]],
    employees: List[Dict[str, Any]],
    user_profiles: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Calculates Sub-Tab 3: Historical Payroll Progress & Trends across all finalized weekly rosters."""
    trend_rows = []
    for date_str, records in all_rosters:
        if not records:
            continue
        dt_obj = parse_date_robust(date_str)
        sort_iso = dt_obj.isoformat() if dt_obj else date_str
        label = dt_obj.strftime("%d/%m/%Y") if dt_obj else date_str
        wages = calculate_wages_records(records, employees, user_profiles)
        trend_rows.append(
            {
                "date": sort_iso,
                "Roster Week": f"Week of {label}",
                "Paid Hours": wages["total_hours"],
                "Gross Payroll ($)": wages["total_gross"],
                "Est. PAYG Tax ($)": wages["total_tax"],
                "Net Take-Home ($)": wages["total_net"],
                "Super 12.5% ($)": wages["total_super"],
            }
        )
    trend_rows.sort(key=lambda r: r["date"])
    return trend_rows
