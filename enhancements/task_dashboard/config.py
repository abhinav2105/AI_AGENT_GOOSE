"""Resolve the Goose sessions.db path across OSes, with env override and demo fallback."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ENV_VAR = "GOOSE_SESSIONS_DB"
DEMO_DB_FILENAME = "demo_sessions.db"


def _candidate_paths() -> list[Path]:
    """Return OS-default Goose sessions.db locations in priority order."""
    home = Path.home()
    paths: list[Path] = []

    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        if appdata:
            paths.append(Path(appdata) / "Block" / "goose" / "data" / "sessions" / "sessions.db")
        local = os.environ.get("LOCALAPPDATA")
        if local:
            paths.append(Path(local) / "Block" / "goose" / "data" / "sessions" / "sessions.db")
    elif sys.platform == "darwin":
        paths.append(home / "Library" / "Application Support" / "Block" / "goose" / "data" / "sessions" / "sessions.db")
        paths.append(home / ".local" / "share" / "goose" / "sessions" / "sessions.db")
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        base = Path(xdg) if xdg else home / ".local" / "share"
        paths.append(base / "goose" / "sessions" / "sessions.db")

    return paths


def resolve_db_path() -> tuple[Path, str]:
    """Return (path, source_label). Source is one of: 'env', 'default', 'demo', 'missing'."""
    env_val = os.environ.get(ENV_VAR)
    if env_val:
        p = Path(env_val).expanduser()
        if p.exists():
            return p, "env"

    for candidate in _candidate_paths():
        if candidate.exists():
            return candidate, "default"

    demo = Path(__file__).parent / DEMO_DB_FILENAME
    if demo.exists():
        return demo, "demo"

    return demo, "missing"


# Pricing table for Token Usage estimator (Enhancement 3 will reuse this).
# Prices are USD per 1M tokens. Adjust as providers update.
PRICING_USD_PER_1M = {
    "anthropic/claude-opus-4": {"input": 15.0, "output": 75.0},
    "anthropic/claude-sonnet-4": {"input": 3.0, "output": 15.0},
    "anthropic/claude-haiku-4": {"input": 1.0, "output": 5.0},
    "openai/gpt-4o": {"input": 2.5, "output": 10.0},
    "openai/gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "google/gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "google/gemini-2.0-pro": {"input": 1.25, "output": 5.0},
}
