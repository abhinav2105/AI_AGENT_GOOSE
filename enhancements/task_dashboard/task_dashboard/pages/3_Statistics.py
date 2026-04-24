"""Aggregate statistics across all sessions."""
from __future__ import annotations

from collections import Counter

import pandas as pd
import plotly.express as px
import streamlit as st

from config import resolve_db_path
from db import load_sessions, load_session_messages, mtime_for
from parsers import summarize_tools

st.set_page_config(page_title="Statistics — Goose", page_icon="📊", layout="wide")
st.title("📊 Statistics")

db_path, _ = resolve_db_path()
mtime = mtime_for(db_path)
sessions = load_sessions(str(db_path), mtime)

if sessions.empty:
    st.info("No sessions to analyze yet.")
    st.stop()

# ---------- Sessions per day ----------
st.subheader("Sessions per day")
per_day = (
    sessions.assign(day=sessions["created_at"].dt.date)
    .groupby("day")
    .size()
    .reset_index(name="sessions")
)
fig1 = px.bar(per_day, x="day", y="sessions", title=None, labels={"day": "Date", "sessions": "Sessions"})
fig1.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0))
st.plotly_chart(fig1, use_container_width=True)

# ---------- Tokens per day ----------
st.subheader("Tokens per day")
tok_col = "accumulated_total_tokens" if "accumulated_total_tokens" in sessions.columns else "total_tokens"
tokens_per_day = (
    sessions.assign(day=sessions["created_at"].dt.date)
    .groupby("day")[tok_col]
    .sum(min_count=1)
    .reset_index(name="tokens")
    .fillna(0)
)
fig2 = px.line(tokens_per_day, x="day", y="tokens", markers=True)
fig2.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0))
st.plotly_chart(fig2, use_container_width=True)

# ---------- Most used tools ----------
st.subheader("Most used tools")

@st.cache_data(ttl=60, show_spinner="Aggregating tool usage…")
def _tool_counts(db_path_str: str, mtime: float, session_ids: tuple[str, ...]) -> pd.DataFrame:
    total: Counter = Counter()
    for sid in session_ids:
        msgs = load_session_messages(db_path_str, sid, mtime)
        total.update(summarize_tools(msgs))
    if not total:
        return pd.DataFrame(columns=["tool", "count"])
    return (
        pd.DataFrame(total.items(), columns=["tool", "count"])
        .sort_values("count", ascending=False)
        .reset_index(drop=True)
    )

tools_df = _tool_counts(str(db_path), mtime, tuple(sessions["id"].tolist()))

if tools_df.empty:
    st.caption("No tool calls recorded in any session.")
else:
    fig3 = px.bar(
        tools_df.head(15), x="count", y="tool", orientation="h",
        title=None, labels={"count": "Calls", "tool": ""},
    )
    fig3.update_layout(height=max(280, 24 * len(tools_df.head(15))), yaxis={"categoryorder": "total ascending"},
                       margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig3, use_container_width=True)
    with st.expander("Full table"):
        st.dataframe(tools_df, use_container_width=True, hide_index=True)

# ---------- Sessions by type / provider ----------
c1, c2 = st.columns(2)

with c1:
    st.subheader("By session type")
    type_counts = sessions["session_type"].value_counts().reset_index()
    type_counts.columns = ["session_type", "count"]
    fig4 = px.pie(type_counts, names="session_type", values="count", hole=0.45)
    fig4.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig4, use_container_width=True)

with c2:
    st.subheader("By provider")
    prov = sessions["provider_name"].fillna("(unknown)").value_counts().reset_index()
    prov.columns = ["provider", "count"]
    fig5 = px.pie(prov, names="provider", values="count", hole=0.45)
    fig5.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig5, use_container_width=True)
