"""SQLite-backed demo auth and run history store."""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from admitpilot.config import AdmitPilotSettings

DEMO_EMAIL = "demo@admitpilot.local"
DEMO_PASSWORD = "admitpilot-demo"
DEMO_DISPLAY_NAME = "Demo Advisor"


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    """Authenticated API user."""

    user_id: str
    email: str
    display_name: str


class DemoApiStore:
    """Small SQLite store for demo sessions and orchestration history."""

    def __init__(self, settings: AdmitPilotSettings) -> None:
        self.path = Path(settings.api_data_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def authenticate(self, email: str, password: str) -> AuthenticatedUser | None:
        normalized_email = email.strip().lower()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, email, display_name, password_salt, password_hash
                FROM users
                WHERE email = ?
                """,
                (normalized_email,),
            ).fetchone()
        if row is None:
            return None
        expected = self._hash_password(password=password, salt=str(row["password_salt"]))
        if not secrets.compare_digest(expected, str(row["password_hash"])):
            return None
        return AuthenticatedUser(
            user_id=str(row["id"]),
            email=str(row["email"]),
            display_name=str(row["display_name"]),
        )

    def create_session(self, user: AuthenticatedUser) -> str:
        token = secrets.token_urlsafe(32)
        token_hash = self._hash_token(token)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions (token_hash, user_id, created_at)
                VALUES (?, ?, ?)
                """,
                (token_hash, user.user_id, _utc_now()),
            )
        return token

    def get_user_by_token(self, token: str) -> AuthenticatedUser | None:
        token_hash = self._hash_token(token)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT users.id, users.email, users.display_name
                FROM sessions
                JOIN users ON users.id = sessions.user_id
                WHERE sessions.token_hash = ?
                """,
                (token_hash,),
            ).fetchone()
        if row is None:
            return None
        return AuthenticatedUser(
            user_id=str(row["id"]),
            email=str(row["email"]),
            display_name=str(row["display_name"]),
        )

    def delete_session(self, token: str) -> None:
        token_hash = self._hash_token(token)
        with self._connect() as connection:
            connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))

    def create_run(
        self,
        *,
        user: AuthenticatedUser,
        request_payload: dict[str, Any],
        response_payload: dict[str, Any],
    ) -> dict[str, Any]:
        run_id = f"run_{secrets.token_hex(8)}"
        created_at = _utc_now()
        results = response_payload.get("results", [])
        result_count = len(results) if isinstance(results, list) else 0
        stored_response = dict(response_payload)
        stored_response["run_id"] = run_id
        run_summary = {
            "run_id": run_id,
            "trace_id": str(response_payload.get("trace_id") or ""),
            "status": str(response_payload.get("status") or "failed"),
            "summary": str(response_payload.get("summary") or ""),
            "result_count": result_count,
            "created_at": created_at,
        }
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO runs (
                    id, user_id, trace_id, status, summary, result_count,
                    request_json, response_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    user.user_id,
                    run_summary["trace_id"],
                    run_summary["status"],
                    run_summary["summary"],
                    run_summary["result_count"],
                    _json_dumps(request_payload),
                    _json_dumps(stored_response),
                    created_at,
                ),
            )
        return run_summary

    def list_runs(self, user: AuthenticatedUser, limit: int = 20) -> list[dict[str, Any]]:
        bounded_limit = min(max(limit, 1), 100)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, trace_id, status, summary, result_count, created_at
                FROM runs
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (user.user_id, bounded_limit),
            ).fetchall()
        return [
            {
                "run_id": str(row["id"]),
                "trace_id": str(row["trace_id"]),
                "status": str(row["status"]),
                "summary": str(row["summary"]),
                "result_count": int(row["result_count"]),
                "created_at": str(row["created_at"]),
            }
            for row in rows
        ]

    def get_run(self, user: AuthenticatedUser, run_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, trace_id, status, summary, result_count,
                       request_json, response_json, created_at
                FROM runs
                WHERE user_id = ? AND id = ?
                """,
                (user.user_id, run_id),
            ).fetchone()
        if row is None:
            return None
        return {
            "run_id": str(row["id"]),
            "trace_id": str(row["trace_id"]),
            "status": str(row["status"]),
            "summary": str(row["summary"]),
            "result_count": int(row["result_count"]),
            "request": json.loads(str(row["request_json"])),
            "response": json.loads(str(row["response_json"])),
            "created_at": str(row["created_at"]),
        }

    def delete_run(self, user: AuthenticatedUser, run_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM runs WHERE user_id = ? AND id = ?",
                (user.user_id, run_id),
            )
        return cursor.rowcount > 0

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    password_salt TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    result_count INTEGER NOT NULL,
                    request_json TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );
                CREATE INDEX IF NOT EXISTS idx_runs_user_created
                    ON runs(user_id, created_at DESC);
                """
            )
            demo_user = connection.execute(
                "SELECT id FROM users WHERE email = ?",
                (DEMO_EMAIL,),
            ).fetchone()
            if demo_user is None:
                salt = secrets.token_hex(12)
                connection.execute(
                    """
                    INSERT INTO users (
                        id, email, display_name, password_salt, password_hash, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "usr_demo",
                        DEMO_EMAIL,
                        DEMO_DISPLAY_NAME,
                        salt,
                        self._hash_password(password=DEMO_PASSWORD, salt=salt),
                        _utc_now(),
                    ),
                )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _hash_password(self, *, password: str, salt: str) -> str:
        return hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()

    def _hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, default=str)
