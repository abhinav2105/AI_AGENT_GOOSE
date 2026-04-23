"""Sessions list: searchable, filterable table with click-to-drill."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from config import resolve_db_path
from db import load_sessions, distinct_working_dirs, mtime_for

st.set_page_config(page_title="Sessions — Goose", page_icon="📋", layout="wide")
st.title("📋 Sessions")

db_path, _ = resolve_db_path()
mtime = mtime_for(db_path)
df = load_sessions(str(db_path), mtime)

if df.empty:
    st.info("No sessions found in the database.")
    st.stop()

# ---------- Sidebar filters ----------
with st.sidebar:
    st.header("Filters")

    min_d = df["created_at"].min().date()
    max_d = df["created_at"].max().date()
    date_range = st.date_input(
        "Created between",
        value=(min_d, max_d),
        min_value=min_d,
        max_value=max_d,
    )

    dirs = distinct_working_dirs(str(db_path), mtime)
    selected_dirs = st.multiselect("Working directory", dirs, default=[])

    types = sorted(df["session_type"].dropna().unique().tolist())
    selected_types = st.multiselect("Session type", types, default=types)

    query = st.text_input("Search (name / description)", value="").strip().lower()

    if st.button("Clear filters"):
        st.rerun()

# ---------- Apply filters ----------
mask = pd.Series(True, index=df.index)

if isinstance(date_range, tuple) and len(date_range) == 2:
    start, end = date_range
    mask &= df["created_at"].dt.date.between(start, end)

if selected_dirs:
    mask &= df["working_dir"].isin(selected_dirs)

if selected_types:
    mask &= df["session_type"].isin(selected_types)

if query:
    hay = (df["name"].fillna("") + " " + df["description"].fillna("")).str.lower()
    mask &= hay.str.contains(query, regex=False)

filtered = df[mask].copy()

st.caption(f"Showing **{len(filtered)}** of {len(df)} sessions.")

# ---------- Table ----------
display_cols = [
    "id",
    "name",
    "session_type",
    "working_dir",
    "created_at",
    "duration_min",
    "message_count",
    "accumulated_total_tokens",
    "provider_name",
]
display_cols = [c for c in display_cols if c in filtered.columns]
view = filtered[display_cols].rename(
    columns={
        "accumulated_total_tokens": "tokens",
        "message_count": "msgs",
        "session_type": "type",
        "working_dir": "cwd",
    }
)

event = st.dataframe(
    view,
    use_container_width=True,
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
    column_config={
        "id": st.column_config.TextColumn("id", width="small"),
        "created_at": st.column_config.DatetimeColumn("created", format="YYYY-MM-DD HH:mm"),
        "duration_min": st.column_config.NumberColumn("dur (min)", format="%.1f"),
        "tokens": st.column_config.NumberColumn("tokens", format="%d"),
    },
)

# ---------- Drill-down launcher ----------
st.divider()

selected_rows = event.selection.rows if event.selection else []
if selected_rows:
    chosen_id = view.iloc[selected_rows[0]]["id"]
    st.session_state["selected_session_id"] = chosen_id
    st.success(f"Selected session `{chosen_id}`")
    if st.button("Open Session Detail →", type="primary"):
        st.switch_page("pages/2_Session_Detail.py")
else:
    st.info("Click a row above, then press **Open Session Detail** to drill in.")
