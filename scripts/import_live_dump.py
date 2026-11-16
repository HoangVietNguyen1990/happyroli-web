import json
import os
import sys

HAPPYROLLY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HAPPYROLLY_DIR)

from database.db_manager import HappyRollyDB

DUMP_PATH = os.path.join(HAPPYROLLY_DIR, "backup_snapshot", "firestore_live_dump.json")

with open(DUMP_PATH, "r", encoding="utf-8") as f:
    dump = json.load(f)

db = HappyRollyDB()

for c in ["employees", "unavailability", "requirements", "fixed"]:
    for d in dump.get(c, []):
        if d.get("_id") == "master_list" and "records" in d:
            db.save_records(c, d["records"])
            print(f"Saved {c}: {len(d['records'])} rows")

# Timecards: merge timecard_records (639 docs with real Clock In / Clock Out) + timecards master_list
tc_map = {}
for d in dump.get("timecards", []):
    if d.get("_id") == "master_list" and isinstance(d.get("records"), list):
        for r in d["records"]:
            rid = r.get("Record ID") or f"{r.get('Date', '')}_{r.get('Employee', '')}"
            tc_map[rid] = r

for d in dump.get("timecard_records", []):
    rec = {k: v for k, v in d.items() if k != "_id"}
    rid = rec.get("Record ID") or d.get("_id")
    rec["Record ID"] = rid
    tc_map[rid] = rec

tc_list = list(tc_map.values())
db.save_records("timecards", tc_list)
print(f"Saved timecards: {len(tc_list)} rows")

for r in dump.get("finalized_rosters", []):
    d_str = r.get("date_str") or r.get("_id")
    recs = r.get("records", [])
    if d_str and recs:
        db.save_finalized_roster(d_str, recs)

rosters = db.list_finalized_rosters()
print(f"Saved finalized_rosters: {len(rosters)} weeks -> {[x['date_str'] for x in rosters[:8]]}")

for dr in dump.get("roster_drafts", []):
    d_str = dr.get("date_str") or dr.get("_id")
    recs = dr.get("records", [])
    owner = dr.get("owner_key", "manager")
    if d_str and recs:
        db.save_roster_draft(d_str, recs, owner_key=owner)

for s in dump.get("system", []):
    sid = s.get("_id")
    if sid == "user_profiles":
        db.save_system_doc("user_profiles", s.get("profiles", s))
    elif sid == "announcements":
        db.save_system_doc("announcements", s.get("announcements", []))
    elif sid == "smtp_config":
        db.save_system_doc("smtp_config", s.get("config", s))
    elif sid:
        db.save_system_doc(sid, s)

print("Summary:", json.dumps(db.get_summary_stats(), indent=2))
