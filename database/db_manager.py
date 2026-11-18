import csv
import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "database", "happyrolly.db")


class HappyRollyDB:
    """Standalone SQLite/SQL database engine for happyrolly.com.au (replaces Firebase Firestore)."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS datasets (
                    collection_name TEXT PRIMARY KEY,
                    records_json TEXT NOT NULL,
                    row_count INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS finalized_rosters (
                    date_str TEXT PRIMARY KEY,
                    records_json TEXT NOT NULL,
                    row_count INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS roster_drafts (
                    draft_id TEXT PRIMARY KEY,
                    owner_key TEXT NOT NULL,
                    date_str TEXT NOT NULL,
                    records_json TEXT NOT NULL,
                    saved_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS system_store (
                    doc_key TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS assistant_conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    speaker TEXT NOT NULL,
                    message_text TEXT NOT NULL,
                    action_taken_json TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS manager_learned_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rule_type TEXT NOT NULL,
                    employee TEXT NOT NULL,
                    day TEXT,
                    shift_name TEXT,
                    preference TEXT NOT NULL,
                    weight_score INTEGER NOT NULL DEFAULT 50,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS manager_profile_memory (
                    fact_key TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    fact_summary TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    # --- Generic Record Collections (employees, unavailability, requirements, fixed, timecards) ---
    def save_records(self, collection_name: str, records: List[Dict[str, Any]]) -> bool:
        if records is None:
            return False
        now_iso = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO datasets (collection_name, records_json, row_count, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(collection_name) DO UPDATE SET
                    records_json = excluded.records_json,
                    row_count = excluded.row_count,
                    updated_at = excluded.updated_at
                """,
                (collection_name, json.dumps(records, ensure_ascii=False), len(records), now_iso),
            )
        return True

    def load_records(self, collection_name: str) -> Optional[List[Dict[str, Any]]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT records_json FROM datasets WHERE collection_name = ?",
                (collection_name,),
            ).fetchone()
            if not row:
                return None
            return json.loads(row["records_json"])

    # --- Finalized Rosters ---
    def save_finalized_roster(self, date_str: str, records: List[Dict[str, Any]]) -> bool:
        if not records:
            return False
        now_iso = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO finalized_rosters (date_str, records_json, row_count, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(date_str) DO UPDATE SET
                    records_json = excluded.records_json,
                    row_count = excluded.row_count,
                    updated_at = excluded.updated_at
                """,
                (date_str, json.dumps(records, ensure_ascii=False), len(records), now_iso),
            )
        return True

    def load_finalized_roster(self, date_str: str) -> Optional[List[Dict[str, Any]]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT records_json FROM finalized_rosters WHERE date_str = ?",
                (date_str,),
            ).fetchone()
            if not row:
                return None
            return json.loads(row["records_json"])

    def list_finalized_rosters(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT date_str, row_count, updated_at FROM finalized_rosters ORDER BY date_str DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def delete_finalized_roster(self, date_str: str) -> bool:
        with self._connect() as conn:
            conn.execute("DELETE FROM finalized_rosters WHERE date_str = ?", (date_str,))
        return True

    # --- Roster Drafts ---
    def save_roster_draft(self, date_str: str, records: List[Dict[str, Any]], owner_key: str = "manager") -> Tuple[bool, str]:
        if not records:
            return False, "Empty draft records"
        owner = (owner_key or "manager").strip().lower()
        draft_id = f"{owner}__{date_str}"
        saved_at = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO roster_drafts (draft_id, owner_key, date_str, records_json, saved_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(draft_id) DO UPDATE SET
                    records_json = excluded.records_json,
                    saved_at = excluded.saved_at
                """,
                (draft_id, owner, date_str, json.dumps(records, ensure_ascii=False), saved_at),
            )
        return True, saved_at

    def load_roster_draft(self, date_str: str, owner_key: str = "manager") -> Tuple[Optional[List[Dict[str, Any]]], str]:
        owner = (owner_key or "manager").strip().lower()
        draft_id = f"{owner}__{date_str}"
        with self._connect() as conn:
            row = conn.execute(
                "SELECT records_json, saved_at FROM roster_drafts WHERE draft_id = ?",
                (draft_id,),
            ).fetchone()
            if not row:
                return None, ""
            return json.loads(row["records_json"]), row["saved_at"]

    def list_roster_drafts(self, owner_key: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            if owner_key:
                owner = owner_key.strip().lower()
                rows = conn.execute(
                    "SELECT draft_id, owner_key, date_str, saved_at FROM roster_drafts WHERE owner_key = ? ORDER BY saved_at DESC",
                    (owner,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT draft_id, owner_key, date_str, saved_at FROM roster_drafts ORDER BY saved_at DESC"
                ).fetchall()
            return [dict(r) for r in rows]

    # --- System Documents (user_profiles, announcements, smtp_config, holiday_calendar) ---
    def save_system_doc(self, doc_key: str, payload: Any) -> bool:
        now_iso = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO system_store (doc_key, payload_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(doc_key) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (doc_key, json.dumps(payload, ensure_ascii=False, default=str), now_iso),
            )
        return True

    def load_system_doc(self, doc_key: str) -> Optional[Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM system_store WHERE doc_key = ?",
                (doc_key,),
            ).fetchone()
            if not row:
                return None
            return json.loads(row["payload_json"])

    def get_summary_stats(self) -> Dict[str, Any]:
        with self._connect() as conn:
            datasets = conn.execute("SELECT collection_name, row_count, updated_at FROM datasets").fetchall()
            rosters = conn.execute("SELECT COUNT(*) AS cnt FROM finalized_rosters").fetchone()["cnt"]
            drafts = conn.execute("SELECT COUNT(*) AS cnt FROM roster_drafts").fetchone()["cnt"]
            sys_docs = conn.execute("SELECT doc_key, updated_at FROM system_store").fetchall()
            return {
                "db_path": self.db_path,
                "datasets": {r["collection_name"]: r["row_count"] for r in datasets},
                "finalized_rosters_count": rosters,
                "roster_drafts_count": drafts,
                "system_docs": [r["doc_key"] for r in sys_docs],
            }

    # --- AI Assistant Conversations & Memory ---
    def save_chat_message(self, session_id: str, speaker: str, message_text: str, action_taken: Any = None) -> bool:
        now_iso = datetime.now().isoformat()
        act_json = json.dumps(action_taken, ensure_ascii=False) if action_taken else None
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO assistant_conversations (session_id, speaker, message_text, action_taken_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id or "default", speaker, message_text, act_json, now_iso),
            )
        return True

    def get_recent_chat_history(self, session_id: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            if session_id:
                rows = conn.execute(
                    "SELECT id, session_id, speaker, message_text, action_taken_json, created_at FROM assistant_conversations WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                    (session_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, session_id, speaker, message_text, action_taken_json, created_at FROM assistant_conversations ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            res = [dict(r) for r in rows]
            res.reverse()
            return res

    def save_learned_rule(
        self,
        rule_type: str,
        employee: str,
        day: Optional[str] = "",
        shift_name: Optional[str] = "",
        preference: str = "PREFER",
        weight_score: int = 50,
        notes: str = "",
    ) -> bool:
        now_iso = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO manager_learned_rules (rule_type, employee, day, shift_name, preference, weight_score, notes, created_at, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (rule_type, employee, day or "", shift_name or "", preference, weight_score, notes, now_iso),
            )
        return True

    def get_learned_rules(self, active_only: bool = True) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            if active_only:
                rows = conn.execute("SELECT * FROM manager_learned_rules WHERE active = 1 ORDER BY id DESC").fetchall()
            else:
                rows = conn.execute("SELECT * FROM manager_learned_rules ORDER BY id DESC").fetchall()
            return [dict(r) for r in rows]

    def save_memory_fact(self, fact_key: str, category: str, fact_summary: str) -> bool:
        now_iso = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO manager_profile_memory (fact_key, category, fact_summary, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(fact_key) DO UPDATE SET
                    category = excluded.category,
                    fact_summary = excluded.fact_summary,
                    updated_at = excluded.updated_at
                """,
                (fact_key, category, fact_summary, now_iso),
            )
        return True

    def get_memory_facts(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM manager_profile_memory ORDER BY updated_at DESC").fetchall()
            return [dict(r) for r in rows]
