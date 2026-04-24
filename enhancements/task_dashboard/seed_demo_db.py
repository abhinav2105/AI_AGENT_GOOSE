"""Generate a demo_sessions.db that mirrors Goose's real schema.

Run once:   python seed_demo_db.py
Then:       streamlit run app.py  (will pick up demo DB if no real one exists)
"""
from __future__ import annotations

import json
import random
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "demo_sessions.db"


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    user_set_name BOOLEAN DEFAULT FALSE,
    session_type TEXT NOT NULL DEFAULT 'user',
    working_dir TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    extension_data TEXT DEFAULT '{}',
    total_tokens INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    accumulated_total_tokens INTEGER,
    accumulated_input_tokens INTEGER,
    accumulated_output_tokens INTEGER,
    schedule_id TEXT,
    recipe_json TEXT,
    user_recipe_values_json TEXT,
    provider_name TEXT,
    model_config_json TEXT,
    goose_mode TEXT NOT NULL DEFAULT 'auto',
    thread_id TEXT
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    role TEXT NOT NULL,
    content_json TEXT NOT NULL,
    created_timestamp INTEGER NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tokens INTEGER,
    metadata_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC);
"""


PROJECT_DIRS = [
    r"C:\Users\alex\projects\inventory-api",
    r"C:\Users\alex\projects\frontend-store",
    r"C:\Users\alex\scratch\leetcode",
    r"C:\Users\alex\projects\data-pipeline",
]
PROVIDERS = ["anthropic", "openai", "google"]
TOOL_NAMES = ["write", "read", "shell", "edit", "list_dir", "search_web", "text_editor"]
TASKS = [
    ("Build a REST endpoint for /inventory", "Created 3 files, added tests"),
    ("Fix flaky integration test", "Root-caused race in setUp, patched"),
    ("Refactor auth middleware", "Extracted JwtVerifier into its own module"),
    ("Scaffold React product page", "Wired Redux slice and routing"),
    ("Debug failing CI build", "Missing env var in GH Actions yaml"),
    ("Optimize slow SQL query", "Added composite index, 12x speedup"),
    ("Write a tic-tac-toe game in JS", "Delivered playable HTML + JS"),
    ("Summarize last week's PRs", "Generated Markdown report"),
]


def _text(t: str) -> dict:
    return {"type": "text", "text": t}


def _tool_request(name: str, args: dict, ok: bool = True) -> dict:
    return {
        "type": "toolRequest",
        "id": f"toolu_{uuid.uuid4().hex[:20]}",
        "toolCall": {
            "status": "success" if ok else "error",
            "value": {"name": name, "arguments": args},
        },
    }


def _tool_response(tid: str, text: str, is_error: bool = False) -> dict:
    return {
        "type": "toolResponse",
        "id": tid,
        "toolResult": {
            "status": "error" if is_error else "success",
            "value": {
                "content": [{"type": "text", "text": text, "annotations": {"priority": 0.0}}],
                "isError": is_error,
            },
        },
    }


def _mk_session(cur: sqlite3.Cursor, created: datetime, task: tuple[str, str]) -> None:
    sid = uuid.uuid4().hex
    cwd = random.choice(PROJECT_DIRS)
    provider = random.choice(PROVIDERS)
    user_task, outcome = task

    tool_pairs: list[tuple[dict, dict]] = []
    n_tools = random.randint(1, 4)
    for i in range(n_tools):
        name = random.choice(TOOL_NAMES)
        if name == "write":
            args = {"path": f"{cwd}\\module_{i}.py", "content": "# sample\nprint('ok')\n"}
            res = f"Created {args['path']} (42 lines)"
            is_err = False
        elif name == "shell":
            args = {"command": "pytest -q"}
            is_err = random.random() < 0.2
            res = "E failed: fixture missing" if is_err else "5 passed in 0.9s"
        elif name == "read":
            args = {"path": f"{cwd}\\README.md"}
            res = "# Project\nSetup instructions..."
            is_err = False
        else:
            args = {"target": name + "_input"}
            res = f"{name} completed"
            is_err = False
        req = _tool_request(name, args, ok=True)
        resp = _tool_response(req["id"], res, is_error=is_err)
        tool_pairs.append((req, resp))

    msgs: list[tuple[str, list]] = [
        ("user", [_text(user_task)]),
        ("assistant", [_text(f"I'll help with that. Let me start by exploring {cwd}.")]),
    ]
    for req, resp in tool_pairs:
        msgs.append(("assistant", [req]))
        msgs.append(("user", [resp]))
    msgs.append(("assistant", [_text(outcome)]))

    total_in = random.randint(2000, 20000)
    total_out = random.randint(500, 6000)
    duration = timedelta(minutes=random.randint(2, 45))
    updated = created + duration

    cur.execute(
        """INSERT INTO sessions
        (id, name, description, session_type, working_dir, created_at, updated_at,
         total_tokens, input_tokens, output_tokens,
         accumulated_total_tokens, accumulated_input_tokens, accumulated_output_tokens,
         provider_name, goose_mode)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            sid,
            user_task[:60],
            outcome,
            random.choice(["user", "user", "user", "scheduled"]),
            cwd,
            created.isoformat(sep=" "),
            updated.isoformat(sep=" "),
            total_in + total_out,
            total_in,
            total_out,
            total_in + total_out,
            total_in,
            total_out,
            provider,
            random.choice(["auto", "approve", "chat"]),
        ),
    )

    t = created
    for role, content in msgs:
        t += timedelta(seconds=random.randint(2, 25))
        cur.execute(
            """INSERT INTO messages
            (message_id, session_id, role, content_json, created_timestamp, timestamp, tokens, metadata_json)
            VALUES (?,?,?,?,?,?,?,?)""",
            (
                uuid.uuid4().hex,
                sid,
                role,
                json.dumps(content),
                int(t.timestamp() * 1000),
                t.isoformat(sep=" "),
                random.randint(50, 800),
                "{}",
            ),
        )


def main() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.executescript(SCHEMA_SQL)
    cur.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (10)")

    random.seed(42)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for i in range(18):
        days_ago = random.randint(0, 21)
        hours = random.randint(0, 23)
        created = now - timedelta(days=days_ago, hours=hours)
        _mk_session(cur, created, random.choice(TASKS))

    con.commit()
    con.close()
    print(f"Wrote {DB_PATH}")


if __name__ == "__main__":
    main()
