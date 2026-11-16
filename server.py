import csv
import io
import json
import os
import sys
from datetime import date, datetime, timedelta
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
    solve_roster_records,
    sort_records_by_team_and_age,
)

db = HappyRollyDB()
STATIC_DIR = os.path.join(HAPPYROLLY_DIR, "static")


def build_timesheet_audit_records() -> dict:
    """Replicates render_manager_timesheet_audit_dashboard logic from app.py."""
    timecards = db.load_records("timecards") or []
    rosters_meta = db.list_finalized_rosters()
    today_dt = date.today()
    today_str = today_dt.strftime("%d/%m/%Y")

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
        if not c_in and status != "Approved":
            note = "⚠️ Missing Clock-In"
            status = "Missing"
        elif c_in and not c_out and status != "Working":
            note = "⚠️ Missing Clock-Out"
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

    working_cnt = sum(1 for r in audit_rows if r["Status"] == "Working")
    late_cnt = sum(1 for r in audit_rows if "Late" in r["Note"])
    missing_cnt = sum(1 for r in audit_rows if "Missing" in r["Note"])

    return {
        "working_count": working_cnt,
        "late_count": late_cnt,
        "missing_count": missing_cnt,
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
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw) if raw else {}

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
            self._send_json(
                200,
                {
                    "ok": True,
                    "today_str": datetime.now().strftime("%d/%m/%Y"),
                    "stats": stats,
                    "rosters": rosters,
                    "drafts": drafts,
                    "announcements": announcements,
                    "profiles_count": len(profiles),
                    "audit_summary": {
                        "working_count": audit["working_count"],
                        "late_count": audit["late_count"],
                        "missing_count": audit["missing_count"],
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

        if path.startswith("/api/system/"):
            doc_key = path.replace("/api/system/", "").strip("/")
            payload = db.load_system_doc(doc_key)
            self._send_json(200, {"ok": True, "doc_key": doc_key, "data": payload})
            return

        self._send_json(404, {"ok": False, "error": "Not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_json_body()

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

        if path == "/api/solve":
            start_date = body.get("start_date", datetime.now().strftime("%Y-%m-%d"))
            employees = body.get("employees") or db.load_records("employees") or []
            unavailability = body.get("unavailability") or db.load_records("unavailability") or []
            requirements = body.get("requirements") or db.load_records("requirements") or []
            fixed = body.get("fixed") or db.load_records("fixed") or []

            solved_rows = solve_roster_records(employees, unavailability, requirements, fixed, start_date)
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
