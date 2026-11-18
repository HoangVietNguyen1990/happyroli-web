import csv
import io
import json
import os
import re
import smtplib
import sys
from datetime import date, datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

HAPPYROLLY_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HAPPYROLLY_DIR)
for p in (HAPPYROLLY_DIR, PROJECT_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from database.db_manager import HappyRollyDB
from core_engine import (
    DAYS_OF_WEEK,
    VIC_PUBLIC_HOLIDAYS,
    VIC_SCHOOL_HOLIDAYS,
    annotate_roster_with_unavailability,
    build_historical_payroll_trends,
    build_monthly_unavailability_grid,
    calculate_award_break,
    calculate_haversine_distance,
    calculate_wages_records,
    get_week_holiday_notices,
    is_vic_public_holiday,
    is_vic_school_holiday,
    parse_date_robust,
    parse_shift_range,
    parse_time_to_decimal,
    solve_roster_records,
    sort_records_by_team_and_age,
)
from assistant_engine import process_assistant_chat

db = HappyRollyDB()
STATIC_DIR = os.path.join(HAPPYROLLY_DIR, "static")

# --- SMTP EMAIL NOTIFICATION ENGINE ---
DEFAULT_SMTP_CONFIG = {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": "Brumby.pakenham@gmail.com",
    "sender_password": "vtgz hboh ynqk uhrw",
    "portal_url": "https://roster.happyroli.com.au",
    "sender_name": "Brumby's Bakery Manager",
    "notification_recipients": "quietsong2006@yahoo.com, uyentrinhtran2309@gmail.com",
}


def load_smtp_config() -> dict:
    cfg = DEFAULT_SMTP_CONFIG.copy()
    disk_file = os.path.join(PROJECT_ROOT, "data", "smtp_config.json")
    if os.path.exists(disk_file):
        try:
            with open(disk_file, "r", encoding="utf-8") as f:
                disk_cfg = json.load(f)
                if isinstance(disk_cfg, dict):
                    for k, v in disk_cfg.items():
                        if v or k not in cfg:
                            cfg[k] = v
        except Exception:
            pass
    db_cfg = db.load_system_doc("smtp_config")
    if db_cfg and isinstance(db_cfg, dict):
        for k, v in db_cfg.items():
            if v or k not in cfg:
                cfg[k] = v
    if not cfg.get("portal_url") or "streamlit" in str(cfg.get("portal_url")):
        cfg["portal_url"] = "https://roster.happyroli.com.au"
    return cfg


def save_smtp_config(cfg: dict) -> bool:
    db.save_system_doc("smtp_config", cfg)
    disk_file = os.path.join(PROJECT_ROOT, "data", "smtp_config.json")
    try:
        with open(disk_file, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass
    return True


def _clean_smtp_password(raw_pass: str, smtp_server: str = "") -> str:
    s = str(raw_pass or "").strip()
    if "gmail" in str(smtp_server).lower():
        s = s.replace(" ", "")
    return s


def _connect_and_login_smtp(smtp_server: str, smtp_port: int, sender_email: str, sender_pass: str, timeout: int = 12):
    clean_pass = _clean_smtp_password(sender_pass, smtp_server)
    port = int(smtp_port)
    if port == 465:
        server = smtplib.SMTP_SSL(smtp_server, port, timeout=timeout)
        server.ehlo()
    else:
        server = smtplib.SMTP(smtp_server, port, timeout=timeout)
        server.ehlo()
        server.starttls()
        server.ehlo()
    server.login(sender_email, clean_pass)
    return server


def send_welcome_email_smtp(
    recipient_email: str,
    emp_name: str,
    username: str,
    temp_password: str,
    portal_url: str = "",
    sender_name: str = "",
    position: str = "Team Member",
    classification: str = "Casual",
) -> tuple:
    cfg = load_smtp_config()
    smtp_server = cfg.get("smtp_server", "smtp.gmail.com")
    smtp_port = int(cfg.get("smtp_port", 587))
    sender_email = cfg.get("sender_email", "").strip()
    sender_pass = cfg.get("sender_password", "").strip()
    if not portal_url:
        portal_url = cfg.get("portal_url", "https://roster.happyroli.com.au")
    if not sender_name:
        sender_name = cfg.get("sender_name", "Brumby's Bakery Manager")

    pos = str(position or "Team Member").strip()
    clf = str(classification or "Casual").strip()

    if not recipient_email or not str(recipient_email).strip():
        return False, "Recipient email address is blank."
    if not sender_email or not sender_pass:
        return False, "SMTP credentials are not configured in system settings."

    subject = f"🥐 Offer of Employment & Welcome to Brumby's Pakenham — {pos}"
    body = f"""Dear {emp_name},

Congratulations! We are delighted to formally offer you employment as a {pos} ({clf}) with the team at Brumby's Bakery Pakenham.

We were very impressed with your presentation and enthusiasm, and we are confident you will make a wonderful addition to our store.

==================================================
OFFER OF EMPLOYMENT DETAILS
==================================================
• Position Title: {pos}
• Employment Category: {clf}
• Work Location: Brumby's Pakenham (Pakenham Central Marketplace)
• Reporting To: Store Management / Bakery Owner
• Applicable Modern Award: General Retail Industry Award 2020 [MA000004]

==================================================
EMPLOYEE ONBOARDING & ROSTER PORTAL
==================================================
We manage all weekly rosters, shift availability, and onboarding digitally through our dedicated staff portal.

Please activate your employee account with the credentials below:

🔗 Portal Website: {portal_url}
👤 Username: {username}
🔑 Temporary Password: {temp_password}

REQUIRED SETUP TASKS (BEFORE FIRST SHIFT):
Once logged in, please complete the following tabs in the portal:
1. 📋 Personal Information & Payroll Form:
   Fill in your contact details, Tax File Number (TFN), superannuation details, and bank account for payroll wage deposits.
2. 📅 My Availability & Constraints:
   Submit the days of the week and time windows you are available to work so we can build your weekly roster.
3. 🔒 Change Password:
   Update your temporary password to your own secure personal password.

If you have any questions regarding your offer or need assistance getting set up, please do not hesitate to reach out to store management.

Once again, congratulations and welcome to Brumby's Pakenham!

Warm regards,

{sender_name}
Store Management
Brumby's Bakery Pakenham
"""
    try:
        msg = MIMEMultipart()
        msg["From"] = f"{sender_name} <{sender_email}>"
        msg["To"] = recipient_email.strip()
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        server = _connect_and_login_smtp(smtp_server, smtp_port, sender_email, sender_pass)
        server.send_message(msg)
        server.quit()
        return True, f"Welcome email delivered to {recipient_email}!"
    except smtplib.SMTPAuthenticationError:
        return False, "Gmail authentication failed (Error 535). Please verify the 16-character Google App Password."
    except Exception as e:
        return False, f"SMTP Error: {e}"


def send_availability_notification_email_smtp(emp_name: str, action_type: str, details_str: str) -> tuple:
    cfg = load_smtp_config()
    smtp_server = cfg.get("smtp_server", "smtp.gmail.com")
    smtp_port = int(cfg.get("smtp_port", 587))
    sender_email = cfg.get("sender_email", "").strip()
    sender_pass = cfg.get("sender_password", "").strip()
    sender_name = cfg.get("sender_name", "Brumby's Bakery Manager")

    recipients_raw = cfg.get("notification_recipients", "quietsong2006@yahoo.com, uyentrinhtran2309@gmail.com")
    recipient_list = [r.strip() for r in re.split(r"[,;]", str(recipients_raw)) if r.strip()]
    if not recipient_list:
        recipient_list = ["quietsong2006@yahoo.com", "uyentrinhtran2309@gmail.com"]

    if not sender_email or not sender_pass:
        return False, "SMTP credentials are not configured."

    subject = f"📅 Staff Availability Alert: {emp_name} — {action_type}"
    now_str = datetime.now().strftime("%d/%m/%Y at %I:%M %p")

    body = f"""Staff Availability Notification Alert 🥐
Brumby's Pakenham

Employee Name: {emp_name}
Action: {action_type}
Timestamp: {now_str}

Details of Availability Change:
{details_str}

This is an automated notification sent from the Brumby's Bakery Portal (https://roster.happyroli.com.au) to keep store owners informed of staff availability updates.
"""
    try:
        msg = MIMEMultipart()
        msg["From"] = f"{sender_name} <{sender_email}>"
        msg["To"] = ", ".join(recipient_list)
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        server = _connect_and_login_smtp(smtp_server, smtp_port, sender_email, sender_pass)
        server.send_message(msg)
        server.quit()
        return True, f"Notification sent to {', '.join(recipient_list)}"
    except Exception as e:
        return False, f"SMTP Error: {e}"


def send_test_email_smtp(recipient_email: str) -> tuple:
    cfg = load_smtp_config()
    smtp_server = cfg.get("smtp_server", "smtp.gmail.com")
    smtp_port = int(cfg.get("smtp_port", 587))
    sender_email = cfg.get("sender_email", "").strip()
    sender_pass = cfg.get("sender_password", "").strip()
    sender_name = cfg.get("sender_name", "Brumby's Bakery Manager")

    if not recipient_email or not str(recipient_email).strip():
        return False, "Recipient email is blank."
    if not sender_email or not sender_pass:
        return False, "SMTP credentials not configured."

    subject = "🧪 Test Notification — Brumby's Bakery Portal"
    now_str = datetime.now().strftime("%d/%m/%Y at %I:%M %p")
    test_body = f"""Hello!

This is a test notification from the Brumby's Bakery Portal (https://roster.happyroli.com.au) to verify your automated email delivery setup.

Sender: {sender_email}
SMTP Server: {smtp_server}:{smtp_port}
Timestamp: {now_str}

If you received this message, automated notifications for new employee welcome emails and staff unavailability alerts are fully functional! 🎉
"""
    try:
        msg = MIMEMultipart()
        msg["From"] = f"{sender_name} <{sender_email}>"
        msg["To"] = recipient_email.strip()
        msg["Subject"] = subject
        msg.attach(MIMEText(test_body, "plain", "utf-8"))

        server = _connect_and_login_smtp(smtp_server, smtp_port, sender_email, sender_pass)
        server.send_message(msg)
        server.quit()
        return True, f"Test email successfully delivered to {recipient_email}!"
    except Exception as e:
        return False, f"Test Email Error: {e}"


def get_melbourne_now() -> datetime:
    """Returns the current datetime in Melbourne (AEDT UTC+11 / AEST UTC+10)."""
    try:
        import zoneinfo
        return datetime.now(zoneinfo.ZoneInfo("Australia/Melbourne"))
    except Exception:
        utc_now = datetime.now(timezone.utc)
        m = utc_now.month
        # Melbourne DST (AEDT UTC+11) from 1st Sunday in October to 1st Sunday in April
        offset_hrs = 11 if (m >= 10 or m <= 3) else 10
        return utc_now + timedelta(hours=offset_hrs)


def build_timesheet_audit_records() -> dict:
    """Replicates render_manager_timesheet_audit_dashboard logic from app.py."""
    timecards = db.load_records("timecards") or []
    rosters_meta = db.list_finalized_rosters()
    melb_now = get_melbourne_now()
    today_dt = melb_now.date()
    today_str = today_dt.strftime("%d/%m/%Y")
    now_dec = melb_now.hour + (melb_now.minute / 60.0)

    # Build scheduled shift lookup from latest finalized rosters
    sched_map = {}
    for rm in rosters_meta:
        d_str = rm["date_str"]
        start_dt = parse_date_robust(d_str)
        rows = db.load_finalized_roster(d_str) or []
        if not start_dt or not rows:
            continue
        for idx, day_name in enumerate(DAYS_OF_WEEK):
            cur_dt = start_dt + timedelta(days=idx)
            if cur_dt > today_dt:
                continue
            cur_dt_str = cur_dt.strftime("%d/%m/%Y")
            for r in rows:
                emp = str(r.get("Employee") or r.get("Name") or "").strip()
                shift_val = str(r.get(day_name, "")).strip()
                if emp and shift_val and parse_shift_range(shift_val):
                    key = (cur_dt_str, emp.lower())
                    if key not in sched_map:
                        sched_map[key] = (emp, shift_val)

    existing_keys = set()
    audit_rows = []
    for idx, tc in enumerate(timecards):
        emp = str(tc.get("Employee", "")).strip()
        d_s = str(tc.get("Date", "")).strip()
        existing_keys.add((d_s, emp.lower()))
        sched = sched_map.get((d_s, emp.lower()), (emp, tc.get("Scheduled Shift", "")))[1]
        c_in = str(tc.get("Clock In", "")).strip()
        c_out = str(tc.get("Clock Out", "")).strip()
        note = str(tc.get("Note", "")).strip()
        status = str(tc.get("Status", "Completed")).strip()

        r_d_obj = parse_date_robust(d_s)
        is_today = bool(r_d_obj and r_d_obj == today_dt)
        is_past = bool(r_d_obj and r_d_obj < today_dt)

        # Dynamic Status and Note calculation matching app.py
        if "Approved" in note or "Rejected" in note or status in ("Approved", "Rejected"):
            pass
        elif not c_in:
            if is_today:
                shift_r = parse_shift_range(sched)
                s_start = shift_r[0] if shift_r else None
                if s_start is not None and now_dec < s_start + 0.25:
                    note = "⏳ Scheduled Today"
                    status = "Scheduled"
                else:
                    note = "⚠️ Missing Clock-In"
                    status = "Missing"
            else:
                note = "⚠️ Missing Clock-In"
                status = "Missing"
        elif c_in and not c_out:
            if is_past:
                # Past days with no clock-out are missing records, NOT currently working today!
                note = "⚠️ Missing Clock-Out"
                status = "Missing"
            elif is_today:
                shift_r = parse_shift_range(sched)
                s_end = shift_r[1] if shift_r else None
                if s_end is not None and now_dec >= s_end + 0.25:
                    note = "⚠️ Missing Clock-Out"
                    status = "Working"
                elif sched and "-" in sched:
                    sched_start_str = sched.split("-")[0].strip()
                    c_in_dec = parse_time_to_decimal(c_in)
                    s_in_dec = parse_time_to_decimal(sched_start_str)
                    var_mins = round((c_in_dec - s_in_dec) * 60)
                    if var_mins >= 10:
                        note = f"⚠️ Late Clocking (+{var_mins} mins)"
                    else:
                        note = "🟢 Working Now"
                    status = "Working"
                else:
                    note = "🟢 Working Now"
                    status = "Working"
            else:
                note = "⚠️ Missing Clock-Out"
                status = "Missing"
        elif c_in and c_out:
            status = "Completed"
            if sched and "-" in sched and "Approved" not in note and "Rejected" not in note:
                sched_start_str = sched.split("-")[0].strip()
                c_in_dec = parse_time_to_decimal(c_in)
                s_in_dec = parse_time_to_decimal(sched_start_str)
                var_mins = round((c_in_dec - s_in_dec) * 60)
                if var_mins >= 10:
                    note = f"⚠️ Late Clocking (+{var_mins} mins)"
                elif not note or note == "Working":
                    note = "✅ Verified / Normal"
            elif not note or note == "Working":
                note = "✅ Verified / Normal"

        audit_rows.append(
            {
                "Record ID": tc.get("Record ID") or f"TC_{idx+1}",
                "Date": d_s,
                "Employee": emp,
                "Scheduled Shift": sched,
                "Clock In": c_in,
                "Clock Out": c_out,
                "Distance (m)": tc.get("Distance_m") or tc.get("Distance (m)") or "0.0",
                "Status": status,
                "Note": note or "✅ Verified / Normal",
            }
        )

    # Add synthetic missing clock-in alerts for recent scheduled shifts without a timecard
    for (d_s, emp_low), (emp_orig, sched_val) in list(sched_map.items())[:80]:
        if (d_s, emp_low) not in existing_keys:
            if any(k in emp_low for k in ("viet", "jane")):
                continue
            audit_rows.append(
                {
                    "Record ID": f"MISS_{d_s}_{emp_low.replace(' ', '_')}",
                    "Date": d_s,
                    "Employee": emp_orig,
                    "Scheduled Shift": sched_val,
                    "Clock In": "",
                    "Clock Out": "",
                    "Distance (m)": "0.0",
                    "Status": "Missing",
                    "Note": "⚠️ Missing Clock-In",
                }
            )

    # Attach Monday-Sunday week metadata & sort newest week/date first
    for r in audit_rows:
        dt_obj = parse_date_robust(r.get("Date", ""))
        if dt_obj:
            mon_dt = dt_obj - timedelta(days=dt_obj.weekday())
            sun_dt = mon_dt + timedelta(days=6)
            r["sort_date"] = dt_obj.isoformat()
            r["week_key"] = mon_dt.isoformat()
            r["week_label"] = f"Week of Mon {mon_dt.strftime('%d/%m/%Y')} — Sun {sun_dt.strftime('%d/%m/%Y')}"
        else:
            r["sort_date"] = "0000-00-00"
            r["week_key"] = "0000-00-00"
            r["week_label"] = "Other Dates"

    audit_rows.sort(key=lambda x: (x["week_key"], x["sort_date"]), reverse=True)

    # Crucial Fix: Only count employees actively clocked in TODAY for "ON DUTY TODAY"
    working_today_cnt = sum(1 for r in audit_rows if r["Status"] == "Working" and r.get("Date") == today_str)
    late_today_cnt = sum(1 for r in audit_rows if "Late" in r["Note"] and r.get("Date") == today_str)
    missing_today_cnt = sum(1 for r in audit_rows if "Missing" in r["Note"] and r.get("Date") == today_str)

    total_missing_cnt = sum(1 for r in audit_rows if "Missing" in r["Note"])
    total_late_cnt = sum(1 for r in audit_rows if "Late" in r["Note"])

    return {
        "working_count": working_today_cnt,
        "late_count": late_today_cnt,
        "missing_count": missing_today_cnt,
        "total_missing_count": total_missing_cnt,
        "total_late_count": total_late_cnt,
        "total_records": len(audit_rows),
        "records": audit_rows,
    }


class HappyRollyRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_json(self, status_code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _send_csv(self, filename: str, csv_text: str) -> None:
        body = csv_text.encode("utf-8-sig")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                return {}
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            return json.loads(raw) if raw else {}
        except Exception:
            return {}

    def do_OPTIONS(self):
        self._send_json(200, {"ok": True})

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            index_file = os.path.join(STATIC_DIR, "index.html")
            if os.path.exists(index_file):
                with open(index_file, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return

        if path == "/api/summary":
            stats = db.get_summary_stats()
            rosters = db.list_finalized_rosters()
            drafts = db.list_roster_drafts()
            announcements = db.load_system_doc("announcements") or [
                {
                    "id": "ANN_1001",
                    "title": "Welcome to HappyRolly Standalone Portal",
                    "content": "All weekly rosters, unavailability calendars, and General Retail Award MA000004 payroll calculations are active.",
                    "author": "Viet (Store Owner)",
                    "date": datetime.now().strftime("%d/%m/%Y"),
                    "priority": "Important",
                }
            ]
            profiles = db.load_system_doc("user_profiles") or {}
            holidays = [{"date": d.isoformat(), "name": name} for d, name in sorted(VIC_PUBLIC_HOLIDAYS.items())]
            school_terms = [
                {"name": h["name"], "start": h["start"].isoformat(), "end": h["end"].isoformat()}
                for h in VIC_SCHOOL_HOLIDAYS
            ]
            audit = build_timesheet_audit_records()
            melb_now = get_melbourne_now()
            self._send_json(
                200,
                {
                    "ok": True,
                    "today_str": melb_now.strftime("%d/%m/%Y"),
                    "stats": stats,
                    "rosters": rosters,
                    "drafts": drafts,
                    "announcements": announcements,
                    "profiles_count": len(profiles),
                    "audit_summary": {
                        "working_count": audit["working_count"],
                        "late_count": audit["late_count"],
                        "missing_count": audit["missing_count"],
                        "total_missing_count": audit["total_missing_count"],
                        "total_late_count": audit["total_late_count"],
                    },
                    "public_holidays": holidays,
                    "school_holidays": school_terms,
                },
            )
            return

        if path == "/api/trends":
            rosters_meta = db.list_finalized_rosters()
            all_rosters = []
            for rm in rosters_meta:
                d_str = rm["date_str"]
                rows = db.load_finalized_roster(d_str) or []
                if rows:
                    all_rosters.append((d_str, rows))
            employees = db.load_records("employees") or []
            profiles = db.load_system_doc("user_profiles") or {}
            trends = build_historical_payroll_trends(all_rosters, employees, profiles)
            self._send_json(200, {"ok": True, "trends": trends})
            return

        if path == "/api/unavailability/grid":
            year = int(qs.get("year", [datetime.now().year])[0])
            month = int(qs.get("month", [datetime.now().month])[0])
            unav = db.load_records("unavailability") or []
            emp = db.load_records("employees") or []
            grid = build_monthly_unavailability_grid(year, month, unav, emp)
            self._send_json(200, {"ok": True, "grid": grid})
            return

        if path == "/api/week-info":
            start_date = qs.get("start_date", [datetime.now().strftime("%Y-%m-%d")])[0]
            notices = get_week_holiday_notices(start_date)
            draft_rows, saved_at = db.load_roster_draft(start_date)
            employees = db.load_records("employees") or []
            unavail = db.load_records("unavailability") or []
            profiles = db.load_system_doc("user_profiles") or {}
            wages = calculate_wages_records(draft_rows, employees, profiles) if draft_rows else None
            badges = annotate_roster_with_unavailability(draft_rows or [], unavail, start_date) if draft_rows else {}
            badge_dict = {f"{k[0]}__{k[1]}": v for k, v in badges.items()}
            self._send_json(
                200,
                {
                    "ok": True,
                    "start_date": start_date,
                    "notices": notices,
                    "draft_records": draft_rows,
                    "draft_saved_at": saved_at,
                    "wages": wages,
                    "unavail_badges": badge_dict,
                },
            )
            return

        if path == "/api/audit":
            audit_data = build_timesheet_audit_records()
            self._send_json(200, {"ok": True, "audit": audit_data})
            return

        if path == "/api/profiles":
            profiles = db.load_system_doc("user_profiles") or {}
            employees = sort_records_by_team_and_age(db.load_records("employees") or [])
            self._send_json(200, {"ok": True, "profiles": profiles, "employees": employees})
            return

        if path.startswith("/api/dataset/"):
            coll_name = path.replace("/api/dataset/", "").strip("/")
            records = db.load_records(coll_name) or []
            if coll_name in ("employees", "fixed", "unavailability"):
                records = sort_records_by_team_and_age(records)
            self._send_json(200, {"ok": True, "collection": coll_name, "records": records})
            return

        if path == "/api/rosters":
            rosters = db.list_finalized_rosters()
            self._send_json(200, {"ok": True, "rosters": rosters})
            return

        if path.startswith("/api/rosters/") and path.endswith("/export.csv"):
            date_str = path.replace("/api/rosters/", "").replace("/export.csv", "").strip("/")
            records = db.load_finalized_roster(date_str) or []
            buf = io.StringIO()
            if records:
                cols = ["Employee"] + DAYS_OF_WEEK
                writer = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(records)
            self._send_csv(f"Team_Roster_{date_str}.csv", buf.getvalue())
            return

        if path.startswith("/api/rosters/"):
            date_str = path.replace("/api/rosters/", "").strip("/")
            records = db.load_finalized_roster(date_str)
            if records is None:
                self._send_json(404, {"ok": False, "error": f"Roster {date_str} not found"})
                return
            records = sort_records_by_team_and_age(records)
            employees = db.load_records("employees") or []
            profiles = db.load_system_doc("user_profiles") or {}
            wages = calculate_wages_records(records, employees, profiles)
            self._send_json(200, {"ok": True, "date_str": date_str, "records": records, "wages": wages})
            return

        if path == "/api/smtp-config":
            cfg = load_smtp_config().copy()
            pw = cfg.get("sender_password", "")
            cfg["has_password"] = bool(pw)
            cfg["masked_password"] = "••••••••••••" if pw else ""
            cfg.pop("sender_password", None)
            self._send_json(200, {"ok": True, "config": cfg})
            return

        if path.startswith("/api/system/"):
            doc_key = path.replace("/api/system/", "").strip("/")
            payload = db.load_system_doc(doc_key)
            self._send_json(200, {"ok": True, "doc_key": doc_key, "data": payload})
            return

        if path == "/api/assistant/history":
            session_id = qs.get("session_id", ["default"])[0]
            history = db.get_recent_chat_history(session_id, limit=20)
            rules = db.get_learned_rules(active_only=True)
            facts = db.get_memory_facts()
            self._send_json(200, {"ok": True, "history": history, "learned_rules": rules, "memory_facts": facts})
            return

        if path == "/api/assistant/config":
            cfg = db.load_system_doc("ai_assistant_config") or {}
            key = cfg.get("gemini_api_key", "")
            masked = ("•" * 8 + key[-4:]) if len(key) >= 8 else ("•" * len(key))
            self._send_json(
                200,
                {
                    "ok": True,
                    "config": {
                        "has_key": bool(key),
                        "masked_key": masked,
                        "model_name": cfg.get("model_name", "gemini-2.5-flash"),
                        "persona": "Joy",
                        "accent": "Phan Rang",
                    },
                },
            )
            return

        if path == "/api/assistant/rules":
            rules = db.get_learned_rules(active_only=True)
            self._send_json(200, {"ok": True, "rules": rules})
            return

        self._send_json(404, {"ok": False, "error": "Not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_json_body()

        if path == "/api/assistant/config":
            curr = db.load_system_doc("ai_assistant_config") or {}
            new_key = str(body.get("gemini_api_key", "")).strip()
            if new_key:
                curr["gemini_api_key"] = new_key
            if "model_name" in body:
                curr["model_name"] = str(body["model_name"]).strip()
            db.save_system_doc("ai_assistant_config", curr)
            self._send_json(200, {"ok": True, "message": "Joy AI configuration saved successfully!"})
            return

        if path == "/api/assistant/chat":
            msg = str(body.get("message", "")).strip()
            session_id = str(body.get("session_id", "default")).strip()
            date_str = str(body.get("date_str", "")).strip()
            roster_rows = body.get("roster_rows")

            if not roster_rows:
                if date_str:
                    draft_tuple = db.load_roster_draft(date_str)
                    roster_rows = draft_tuple[0] if draft_tuple else (db.load_finalized_roster(date_str) or [])
                if not roster_rows:
                    recent_drafts = db.list_roster_drafts()
                    if recent_drafts:
                        d_id = recent_drafts[0]["draft_id"]
                        d_tuple = db.load_roster_draft(recent_drafts[0]["date_str"], recent_drafts[0]["owner_key"])
                        roster_rows = d_tuple[0] if d_tuple else []

            ai_cfg = db.load_system_doc("ai_assistant_config") or {}
            api_key = ai_cfg.get("gemini_api_key", "")

            result = process_assistant_chat(
                user_message=msg,
                roster_rows=roster_rows or [],
                db=db,
                session_id=session_id,
                api_key=api_key,
            )

            # Auto-save updated roster draft if actions were taken
            if result.get("actions_executed") and date_str and result.get("updated_roster"):
                db.save_roster_draft(date_str, result["updated_roster"], owner_key="manager")

            self._send_json(200, result)
            return

        if path == "/api/login":
            username = str(body.get("username", "")).strip().lower()
            password = str(body.get("password", ""))
            is_kiosk = bool(body.get("kiosk", False))
            if is_kiosk:
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "username": "store.kiosk",
                        "display_name": "🏪 Store Timeclock Kiosk",
                        "role": "Kiosk",
                        "portal_mode": "kiosk",
                    },
                )
                return

            profiles = db.load_system_doc("user_profiles") or {}
            account = profiles.get(username)
            if not account or str(account.get("password", "")) != password:
                self._send_json(401, {"ok": False, "error": "🔒 Invalid username or password. Please check your credentials."})
                return

            prof = account.get("profile", {}) if isinstance(account.get("profile"), dict) else {}
            is_mgr = (
                account.get("role") == "Manager"
                or str(prof.get("classification", "")).lower() in ("owner", "manager", "store manager", "bakery manager")
                or str(prof.get("employment_level", "")).lower() in ("owner", "manager", "store manager", "bakery manager")
                or username in ("admin", "viet", "jane", "manager", "bakery.manager", "store.manager", "owner")
            )
            role_title = "Manager" if is_mgr else "Employee"
            portal_mode = "manager" if is_mgr else "staff"
            display_name = str(account.get("employee_name") or prof.get("full_name") or username)
            self._send_json(
                200,
                {
                    "ok": True,
                    "username": username,
                    "display_name": display_name,
                    "role": role_title,
                    "portal_mode": portal_mode,
                },
            )
            return

        if path == "/api/announcements":
            announcements = db.load_system_doc("announcements") or []
            new_entry = {
                "id": f"ANN_{len(announcements) + 1001}",
                "title": str(body.get("title", "")).strip(),
                "content": str(body.get("content", "")).strip(),
                "author": str(body.get("author", "Viet (Store Owner)")).strip(),
                "priority": str(body.get("priority", "Normal")).strip(),
                "date": datetime.now().strftime("%d/%m/%Y"),
            }
            announcements.insert(0, new_entry)
            db.save_system_doc("announcements", announcements)
            self._send_json(200, {"ok": True, "announcements": announcements})
            return

        if path.startswith("/api/dataset/"):
            coll_name = path.replace("/api/dataset/", "").strip("/")
            records = body.get("records", [])
            if coll_name in ("employees", "fixed", "unavailability"):
                records = sort_records_by_team_and_age(records)
            ok = db.save_records(coll_name, records)
            self._send_json(200, {"ok": ok, "collection": coll_name, "saved_rows": len(records), "records": records})
            return

        if path == "/api/profiles/save":
            user_key = str(body.get("user_key", "")).strip().lower()
            profile_data = body.get("profile", {})
            new_password = str(body.get("new_password", "")).strip()
            profiles = db.load_system_doc("user_profiles") or {}
            if user_key:
                if user_key not in profiles:
                    profiles[user_key] = {
                        "username": user_key,
                        "password": new_password or "TempPass123!",
                        "role": "Employee",
                        "employee_name": profile_data.get("full_name", user_key),
                        "profile": profile_data,
                    }
                else:
                    if profile_data:
                        profiles[user_key]["profile"] = profile_data
                    if new_password:
                        profiles[user_key]["password"] = new_password
                db.save_system_doc("user_profiles", profiles)
            self._send_json(200, {"ok": True, "profiles": profiles})
            return

        if path == "/api/profiles/delete":
            user_key = str(body.get("user_key", "")).strip().lower()
            profiles = db.load_system_doc("user_profiles") or {}
            if user_key in profiles:
                del profiles[user_key]
                db.save_system_doc("user_profiles", profiles)
                self._send_json(200, {"ok": True, "message": f"Deleted login account '{user_key}'.", "profiles": profiles})
            else:
                self._send_json(404, {"ok": False, "error": f"Account '{user_key}' not found."})
            return

        if path == "/api/profiles/autocreate":
            employees = db.load_records("employees") or []
            profiles = db.load_system_doc("user_profiles") or {}
            existing_names = {str(v.get("employee_name", k)).strip().lower() for k, v in profiles.items()}
            created = 0
            for e in employees:
                ne = {str(k).strip().lower(): v for k, v in e.items()}
                name = str(ne.get("name") or ne.get("employee") or "").strip()
                if not name or name.lower() in existing_names:
                    continue
                uname = name.lower().replace(" ", ".")
                profiles[uname] = {
                    "username": uname,
                    "password": "TempPass123!",
                    "role": "Employee",
                    "employee_name": name,
                    "profile": {
                        "full_name": name,
                        "email": "",
                        "store": "Brumby's Pakenham",
                        "classification": str(ne.get("employment type") or "Casual"),
                        "employment_level": str(ne.get("role") or "Service Staff"),
                        "commencement_date": str(ne.get("start date") or datetime.now().strftime("%Y-%m-%d")),
                    },
                }
                created += 1
            db.save_system_doc("user_profiles", profiles)
            self._send_json(200, {"ok": True, "created_count": created, "profiles": profiles})
            return

        if path == "/api/notify/welcome":
            recip = str(body.get("recipient_email", "")).strip()
            name = str(body.get("emp_name", "")).strip()
            user = str(body.get("username", "")).strip()
            pwd = str(body.get("temp_password", "TempPass123!")).strip()
            portal_url = str(body.get("portal_url", "")).strip()
            pos = str(body.get("position", "Team Member")).strip()
            clf = str(body.get("classification", "Casual")).strip()
            ok, msg = send_welcome_email_smtp(recip, name, user, pwd, portal_url, position=pos, classification=clf)
            self._send_json(200, {"ok": ok, "message": msg})
            return

        if path == "/api/notify/unavailability":
            emp = str(body.get("employee", "")).strip()
            action = str(body.get("action", "Logged Weekly Constraints")).strip()
            details = str(body.get("details", "")).strip()
            ok, msg = send_availability_notification_email_smtp(emp, action, details)
            self._send_json(200, {"ok": ok, "message": msg})
            return

        if path == "/api/notify/test-email":
            recip = str(body.get("recipient_email", "")).strip()
            if not recip:
                cfg = load_smtp_config()
                recip = cfg.get("sender_email", "")
            ok, msg = send_test_email_smtp(recip)
            self._send_json(200, {"ok": ok, "message": msg})
            return

        if path == "/api/smtp-config":
            curr = load_smtp_config()
            for k in ("smtp_server", "smtp_port", "sender_email", "sender_name", "portal_url", "notification_recipients"):
                if k in body and str(body[k]).strip():
                    curr[k] = str(body[k]).strip()
            if body.get("sender_password"):
                curr["sender_password"] = str(body["sender_password"]).strip()
            save_smtp_config(curr)
            self._send_json(200, {"ok": True, "message": "SMTP email configuration updated successfully!"})
            return

        if path == "/api/employees/create":
            new_name = str(body.get("name", "")).strip()
            new_user = str(body.get("username", "")).strip().lower()
            new_pass = str(body.get("password", "TempPass123!")).strip()
            new_email = str(body.get("email", "")).strip()
            new_role = str(body.get("role", "Junior Team Member")).strip()
            new_type = str(body.get("classification", "Casual")).strip()
            new_team = str(body.get("team", "Service Staff")).strip()
            new_dob = str(body.get("dob", "")).strip()
            send_welcome = bool(body.get("send_welcome_email", True))

            if not new_name:
                self._send_json(400, {"ok": False, "error": "Employee name cannot be empty."})
                return
            if not new_user:
                new_user = new_name.lower().replace(" ", ".")

            profiles = db.load_system_doc("user_profiles") or {}
            profiles[new_user] = {
                "username": new_user,
                "password": new_pass,
                "role": "Employee",
                "employee_name": new_name,
                "profile": {
                    "full_name": new_name,
                    "email": new_email,
                    "store": "Brumby's Pakenham",
                    "classification": new_type,
                    "employment_level": new_role,
                    "dob": new_dob,
                    "commencement_date": datetime.now().strftime("%d/%m/%Y"),
                },
            }
            db.save_system_doc("user_profiles", profiles)

            emps = db.load_records("employees") or []
            existing_emp = next((e for e in emps if str(e.get("NAME") or e.get("Name", "")).strip().lower() == new_name.lower()), None)
            if existing_emp:
                existing_emp["position"] = new_role
                existing_emp["status"] = new_type.lower()
                existing_emp["Team"] = new_team
                if new_dob:
                    existing_emp["DOB"] = new_dob
            else:
                emps.append({
                    "NAME": new_name,
                    "Team": new_team,
                    "DOB": new_dob,
                    "Commencing Date": datetime.now().strftime("%d/%m/%Y"),
                    "status": new_type.lower(),
                    "position": new_role,
                })
            emps = sort_records_by_team_and_age(emps)
            db.save_records("employees", emps)

            email_sent = False
            email_msg = "Welcome email not requested."
            if send_welcome and new_email:
                email_sent, email_msg = send_welcome_email_smtp(
                    new_email,
                    new_name,
                    new_user,
                    new_pass,
                    position=new_role or "Team Member",
                    classification=new_type or "Casual",
                )

            self._send_json(200, {
                "ok": True,
                "message": f"Created account for {new_name}!",
                "email_sent": email_sent,
                "email_message": email_msg,
                "profiles": profiles,
                "employees": emps,
            })
            return

        if path == "/api/solve":
            start_date = body.get("start_date", datetime.now().strftime("%Y-%m-%d"))
            employees = body.get("employees") or db.load_records("employees") or []
            unavailability = body.get("unavailability") or db.load_records("unavailability") or []
            requirements = body.get("requirements") or db.load_records("requirements") or []
            fixed = body.get("fixed") or db.load_records("fixed") or []

            learned_rules = db.get_learned_rules(active_only=True)
            solved_rows = solve_roster_records(employees, unavailability, requirements, fixed, start_date, learned_rules=learned_rules)
            db.save_roster_draft(start_date, solved_rows, owner_key="manager")
            profiles = db.load_system_doc("user_profiles") or {}
            wages = calculate_wages_records(solved_rows, employees, profiles)
            notices = get_week_holiday_notices(start_date)
            badges = annotate_roster_with_unavailability(solved_rows, unavailability, start_date)
            badge_dict = {f"{k[0]}__{k[1]}": v for k, v in badges.items()}
            self._send_json(
                200,
                {
                    "ok": True,
                    "start_date": start_date,
                    "records": solved_rows,
                    "wages": wages,
                    "notices": notices,
                    "unavail_badges": badge_dict,
                },
            )
            return

        if path == "/api/drafts/save":
            start_date = body.get("start_date", datetime.now().strftime("%Y-%m-%d"))
            records = body.get("records", [])
            ok, saved_at = db.save_roster_draft(start_date, records, owner_key="manager")
            self._send_json(200, {"ok": ok, "start_date": start_date, "saved_at": saved_at})
            return

        if path == "/api/wages":
            records = body.get("records", [])
            employees = db.load_records("employees") or []
            profiles = db.load_system_doc("user_profiles") or {}
            wages = calculate_wages_records(records, employees, profiles)
            self._send_json(200, {"ok": True, "wages": wages})
            return

        if path == "/api/audit/confirm":
            decisions = body.get("decisions", [])
            timecards = db.load_records("timecards") or []
            tc_by_id = {str(r.get("Record ID", "")): r for r in timecards}
            processed = 0
            for dec in decisions:
                rec_id = str(dec.get("record_id", ""))
                action = str(dec.get("action", "approve"))
                row_data = dec.get("row", {})
                status_label = "Approved" if action == "approve" else "Rejected"
                note_label = f"✅ Manager {status_label}"
                if rec_id in tc_by_id:
                    tc_by_id[rec_id]["Status"] = status_label
                    tc_by_id[rec_id]["Note"] = note_label
                else:
                    row_data["Record ID"] = rec_id
                    row_data["Status"] = status_label
                    row_data["Note"] = note_label
                    timecards.append(row_data)
                processed += 1
            db.save_records("timecards", timecards)
            self._send_json(200, {"ok": True, "processed": processed, "audit": build_timesheet_audit_records()})
            return

        if path.startswith("/api/rosters/") and path.endswith("/delete"):
            date_str = path.replace("/api/rosters/", "").replace("/delete", "").strip("/")
            ok = db.delete_finalized_roster(date_str)
            self._send_json(200, {"ok": ok, "date_str": date_str})
            return

        if path.startswith("/api/rosters/"):
            date_str = path.replace("/api/rosters/", "").strip("/")
            records = sort_records_by_team_and_age(body.get("records", []))
            ok = db.save_finalized_roster(date_str, records)
            employees = db.load_records("employees") or []
            profiles = db.load_system_doc("user_profiles") or {}
            wages = calculate_wages_records(records, employees, profiles)
            self._send_json(200, {"ok": ok, "date_str": date_str, "records": records, "wages": wages})
            return

        if path == "/api/kiosk/clock":
            emp_name = body.get("employee", "")
            action = body.get("action", "Clock In")
            lat = body.get("lat")
            lon = body.get("lon")
            dist_m = 0.0
            if lat is not None and lon is not None:
                dist_m = round(calculate_haversine_distance(float(lat), float(lon)), 1)
            timecards = db.load_records("timecards") or []
            now_dt = datetime.now()
            entry = {
                "Record ID": f"TC_{int(now_dt.timestamp())}",
                "Employee": emp_name,
                "Date": now_dt.strftime("%d/%m/%Y"),
                "Clock In": now_dt.strftime("%H:%M:%S") if action == "Clock In" else "",
                "Clock Out": now_dt.strftime("%H:%M:%S") if action == "Clock Out" else "",
                "Status": "Working" if action == "Clock In" else "Completed",
                "Distance_m": str(dist_m),
                "Note": "🟢 Working Now" if action == "Clock In" else "✅ Verified / Normal",
            }
            timecards.append(entry)
            db.save_records("timecards", timecards)
            self._send_json(200, {"ok": True, "entry": entry, "distance_m": dist_m})
            return

        self._send_json(404, {"ok": False, "error": "Unknown endpoint"})


def run_server(host: str = "0.0.0.0", port: int = 8080):
    server = HTTPServer((host, port), HappyRollyRequestHandler)
    print(f"HappyRolly Standalone Server v2 running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    port_num = int(os.environ.get("PORT", "8080"))
    run_server(port=port_num)
