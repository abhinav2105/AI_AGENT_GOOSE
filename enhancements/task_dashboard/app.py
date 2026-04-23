"""Goose Task History Dashboard — landing page.

Launch:
    streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

from config import resolve_db_path, ENV_VAR
from db import load_sessions, mtime_for

st.set_page_config(
    page_title="Goose Task History",
    page_icon="🦢",
    layout="wide",
)

st.title("🦢 Goose Task History Dashboard")
st.caption("Browse, filter, and analyze your local Goose session data.")

db_path, source = resolve_db_path()

with st.sidebar:
    st.header("Data source")
    label = {
        "env":     f"env var `{ENV_VAR}`",
        "default": "Goose default location",
        "demo":    "demo database (bundled)",
        "missing": "⚠️ no database found",
    }[source]
    st.write(f"**Source:** {label}")
    st.code(str(db_path), language="text")

if source == "missing":
    st.error(
        f"No `sessions.db` found at Goose defaults and no demo DB available.\n\n"
        f"Either set `{ENV_VAR}` to an existing DB path, or run "
        f"`python seed_demo_db.py` to generate one."
    )
    st.stop()

df = load_sessions(str(db_path), mtime_for(db_path))

col1, col2, col3, col4 = st.columns(4)
col1.metric("Sessions", len(df))
col2.metric("Total messages", int(df["message_count"].sum()))
total_tokens = int(df["accumulated_total_tokens"].fillna(df["total_tokens"]).fillna(0).sum())
col3.metric("Total tokens", f"{total_tokens:,}")
col4.metric("Distinct working dirs", df["working_dir"].nunique())

st.divider()

st.subheader("Navigate")
st.markdown(
    """
    Use the sidebar to move between pages:

    - **📋 Sessions** — searchable, filterable list of every session.
    - **🔍 Session Detail** — drilldown into messages, tool calls, and outcomes.
    - **📊 Statistics** — activity over time and most-used tools.
    """
)

with st.expander("How the dashboard finds your database"):
    st.markdown(
        f"""
        Path resolution order:

        1. `{ENV_VAR}` environment variable (override).
        2. OS default: `%APPDATA%/Block/goose/data/sessions/sessions.db` on Windows,
           `~/Library/Application Support/Block/goose/...` on macOS,
           `~/.local/share/goose/sessions/sessions.db` on Linux.
        3. Bundled `demo_sessions.db` (generate with `seed_demo_db.py`).

        The DB is opened **read-only** — the dashboard never writes to it.
        """
    )
