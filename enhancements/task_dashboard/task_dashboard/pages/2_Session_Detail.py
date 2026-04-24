"""Session detail: render message timeline with tool calls and outcomes."""
from __future__ import annotations

import json
import streamlit as st

from config import resolve_db_path
from db import load_session_row, load_session_messages, load_sessions, mtime_for
from parsers import (
    parse_content,
    summarize_tools,
    first_user_prompt,
    count_errors,
)

st.set_page_config(page_title="Session Detail — Goose", page_icon="🔍", layout="wide")
st.title("🔍 Session Detail")

db_path, _ = resolve_db_path()
mtime = mtime_for(db_path)

# ---------- Resolve which session to show ----------
sessions_df = load_sessions(str(db_path), mtime)
all_ids = sessions_df["id"].tolist()

default_id = st.session_state.get("selected_session_id") or (all_ids[0] if all_ids else None)
if default_id is None:
    st.info("No sessions available.")
    st.stop()

session_id = st.selectbox(
    "Session",
    options=all_ids,
    index=all_ids.index(default_id) if default_id in all_ids else 0,
    format_func=lambda sid: f"{sid[:8]}…  {sessions_df.loc[sessions_df['id']==sid, 'name'].values[0] or '(unnamed)'}",
)
st.session_state["selected_session_id"] = session_id

row = load_session_row(str(db_path), session_id, mtime)
msgs = load_session_messages(str(db_path), session_id, mtime)

# ---------- Summary bar ----------
st.subheader(row.get("name") or "(unnamed session)")
meta_cols = st.columns(6)
meta_cols[0].metric("Messages", len(msgs))
meta_cols[1].metric("Tool calls", sum(summarize_tools(msgs).values()))
meta_cols[2].metric("Errors", count_errors(msgs))
tot = row.get("accumulated_total_tokens") or row.get("total_tokens") or 0
meta_cols[3].metric("Tokens", f"{int(tot):,}" if tot else "—")
meta_cols[4].metric("Type", row.get("session_type", "—"))
meta_cols[5].metric("Provider", row.get("provider_name") or "—")

with st.expander("Session metadata"):
    st.write(
        {
            "id": row["id"],
            "working_dir": row.get("working_dir"),
            "created_at": str(row.get("created_at")),
            "updated_at": str(row.get("updated_at")),
            "input_tokens": row.get("input_tokens"),
            "output_tokens": row.get("output_tokens"),
            "goose_mode": row.get("goose_mode"),
        }
    )

prompt = first_user_prompt(msgs)
if prompt:
    st.info(f"**Original task:** {prompt[:500]}{'…' if len(prompt) > 500 else ''}")

st.divider()
st.subheader("Conversation timeline")

# ---------- Timeline ----------
ROLE_ICON = {"user": "🧑", "assistant": "🤖", "tool": "🔧", "system": "⚙️"}

for _, m in msgs.iterrows():
    role = m["role"]
    icon = ROLE_ICON.get(role, "•")
    items = parse_content(m["content_json"])

    ts = m["timestamp"]
    ts_str = ts.strftime("%Y-%m-%d %H:%M:%S") if ts is not None and not (isinstance(ts, float)) else ""

    with st.chat_message(role if role in ("user", "assistant") else "assistant"):
        header = f"**{icon} {role}**"
        if ts_str:
            header += f"   `{ts_str}`"
        if m.get("tokens"):
            header += f"   · {int(m['tokens'])} tokens"
        st.markdown(header)

        for item in items:
            if item.kind == "text":
                if item.text.strip():
                    st.markdown(item.text)

            elif item.kind == "tool_request":
                status_badge = "✅" if item.tool_status == "success" else "⚠️"
                with st.expander(f"{status_badge} 🔧 tool call: `{item.tool_name}`", expanded=False):
                    st.markdown("**Arguments**")
                    st.json(item.tool_args or {}, expanded=False)

            elif item.kind == "tool_response":
                badge = "❌ error" if item.is_error else "✅ ok"
                with st.expander(f"↳ tool result {badge}", expanded=False):
                    if item.text.strip():
                        st.code(item.text[:4000], language="text")
                    else:
                        st.caption("(no text output)")

            elif item.kind == "thinking":
                with st.expander("💭 thinking", expanded=False):
                    st.caption(item.text[:2000])

            else:
                with st.expander(f"⋯ {item.kind}", expanded=False):
                    st.json(item.raw)
