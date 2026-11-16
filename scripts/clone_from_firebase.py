import csv
import json
import os
import sys
from datetime import datetime

HAPPYROLLY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(HAPPYROLLY_DIR)
sys.path.insert(0, HAPPYROLLY_DIR)
sys.path.insert(0, PROJECT_ROOT)

from database.db_manager import HappyRollyDB

SNAPSHOT_DIR = os.path.join(HAPPYROLLY_DIR, "backup_snapshot")
LOCAL_DATA_DIR = os.path.join(PROJECT_ROOT, "data")


def read_csv_records(csv_path: str):
    if not os.path.exists(csv_path):
        return []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def write_csv_records(csv_path: str, records):
    if not records:
        return
    fieldnames = list(records[0].keys())
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def try_connect_firestore_readonly():
    """Attempt read-only connection to existing Firebase project if key & network exist."""
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore

        key_path = os.path.join(
            PROJECT_ROOT,
            "app-database-b486e-firebase-adminsdk-fbsvc-913610cd6b.json",
        )
        if not os.path.exists(key_path):
            return None, "Service account JSON not found locally"

        if not firebase_admin._apps:
            cred = credentials.Certificate(key_path)
            firebase_admin.initialize_app(cred)
        return firestore.client(), "Connected"
    except Exception as e:
        return None, str(e)


def read_firestore_records(fs_db, collection_name: str):
    if fs_db is None:
        return None
    try:
        doc = fs_db.collection(collection_name).document("master_list").get(timeout=5.0)
        if doc.exists:
            records = (doc.to_dict() or {}).get("records", [])
            if records:
                return records
        docs = list(fs_db.collection(collection_name).stream(timeout=5.0))
        rows = []
        for d in docs:
            if d.id == "master_list":
                continue
            payload = d.to_dict() or {}
            if "records" in payload and isinstance(payload["records"], list):
                rows.extend(payload["records"])
            elif payload:
                rows.append(payload)
        if rows:
            return rows
    except Exception:
        pass
    return None


def clone_all_data():
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    os.makedirs(os.path.join(SNAPSHOT_DIR, "finalized_rosters"), exist_ok=True)
    os.makedirs(os.path.join(SNAPSHOT_DIR, "roster_drafts"), exist_ok=True)

    db = HappyRollyDB()
    fs_db, fs_status = try_connect_firestore_readonly()
    report = {
        "timestamp": datetime.now().isoformat(),
        "firebase_status": fs_status,
        "cloned_collections": {},
        "finalized_rosters": [],
        "roster_drafts": [],
        "system_docs": [],
    }

    # 1. Core DataFrame collections
    csv_mapping = {
        "employees": "employees.csv",
        "unavailability": "unavailability.csv",
        "requirements": "requirements.csv",
        "fixed": "fixed.csv",
        "timecards": "timecards.csv",
    }

    for coll_name, csv_file in csv_mapping.items():
        records = read_firestore_records(fs_db, coll_name)
        source_used = "firebase_cloud"
        if not records:
            local_csv = os.path.join(LOCAL_DATA_DIR, csv_file)
            records = read_csv_records(local_csv)
            source_used = "local_data_dir"
        if records is not None:
            db.save_records(coll_name, records)
            write_csv_records(os.path.join(SNAPSHOT_DIR, csv_file), records)
            report["cloned_collections"][coll_name] = {
                "rows": len(records),
                "source": source_used,
            }

    # 2. Finalized Rosters
    finalized_loaded = set()
    if fs_db is not None:
        try:
            for doc in fs_db.collection("finalized_rosters").stream(timeout=5.0):
                records = (doc.to_dict() or {}).get("records", [])
                if records:
                    db.save_finalized_roster(doc.id, records)
                    write_csv_records(
                        os.path.join(SNAPSHOT_DIR, "finalized_rosters", f"Roster_{doc.id}.csv"),
                        records,
                    )
                    finalized_loaded.add(doc.id)
        except Exception:
            pass

    local_finalized_dir = os.path.join(LOCAL_DATA_DIR, "finalized_rosters")
    if os.path.exists(local_finalized_dir):
        for fname in sorted(os.listdir(local_finalized_dir)):
            if fname.startswith("Roster_") and fname.endswith(".csv"):
                date_str = fname.replace("Roster_", "").replace(".csv", "")
                if date_str not in finalized_loaded:
                    records = read_csv_records(os.path.join(local_finalized_dir, fname))
                    if records:
                        db.save_finalized_roster(date_str, records)
                        write_csv_records(
                            os.path.join(SNAPSHOT_DIR, "finalized_rosters", fname),
                            records,
                        )
                        finalized_loaded.add(date_str)

    report["finalized_rosters"] = sorted(finalized_loaded)

    # 3. Roster Drafts
    if fs_db is not None:
        try:
            for doc in fs_db.collection("roster_drafts").stream(timeout=5.0):
                payload = doc.to_dict() or {}
                records = payload.get("records", [])
                date_str = payload.get("date_str", doc.id)
                owner_key = payload.get("owner_key", "manager")
                if records:
                    db.save_roster_draft(date_str, records, owner_key=owner_key)
                    report["roster_drafts"].append(doc.id)
        except Exception:
            pass

    # 4. System Documents (user_profiles, smtp_config, announcements, holiday_calendar)
    system_files = {
        "user_profiles": ("user_profiles.json", "profiles"),
        "smtp_config": ("smtp_config.json", "config"),
        "announcements": ("announcements.json", "announcements"),
        "holiday_calendar": ("holiday_calendar.json", None),
    }

    for doc_key, (local_filename, nested_field) in system_files.items():
        payload = None
        if fs_db is not None:
            try:
                doc = fs_db.collection("system").document(doc_key).get(timeout=5.0)
                if doc.exists:
                    raw = doc.to_dict() or {}
                    payload = raw.get(nested_field, raw) if nested_field else raw
            except Exception:
                pass

        if payload is None:
            local_json_path = os.path.join(LOCAL_DATA_DIR, local_filename)
            if os.path.exists(local_json_path):
                with open(local_json_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)

        if payload is None and doc_key == "holiday_calendar":
            try:
                from holiday_sources import baseline
                from vic_holidays import VIC_PUBLIC_HOLIDAYS, VIC_SCHOOL_HOLIDAYS
                payload = baseline(VIC_PUBLIC_HOLIDAYS, VIC_SCHOOL_HOLIDAYS)
            except Exception:
                pass

        if payload is not None:
            db.save_system_doc(doc_key, payload)
            with open(os.path.join(SNAPSHOT_DIR, local_filename), "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False, default=str)
            report["system_docs"].append(doc_key)

    report["database_summary"] = db.get_summary_stats()
    with open(os.path.join(SNAPSHOT_DIR, "migration_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return report


if __name__ == "__main__":
    result = clone_all_data()
    print(json.dumps(result, indent=2, ensure_ascii=False))
