"""Decode Goose message content_json into display-friendly structures.

Each row in `messages` has a `content_json` column containing a JSON array
of content items. Observed item types:
  - text:         {type: "text", text: str}
  - toolRequest:  {type: "toolRequest", id, toolCall: {status, value: {name, arguments}}}
  - toolResponse: {type: "toolResponse", id, toolResult: {status, value: {content:[{text}], isError}}}
  - thinking / image / others: preserved but rendered generically
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass
class ParsedItem:
    kind: str                       # "text" | "tool_request" | "tool_response" | "thinking" | "other"
    text: str = ""                  # Flattened text for display
    tool_name: str = ""             # For tool_request / tool_response
    tool_args: dict | None = None   # For tool_request
    tool_status: str = ""           # "success" | "error" | ""
    is_error: bool = False          # For tool_response
    tool_id: str = ""
    raw: Any = None                 # Original dict for fallback rendering


def _safe_json_loads(s: str) -> list[dict]:
    if not s:
        return []
    try:
        data = json.loads(s)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    return []


def parse_content(content_json: str) -> list[ParsedItem]:
    items: list[ParsedItem] = []
    for it in _safe_json_loads(content_json):
        if not isinstance(it, dict):
            continue
        t = it.get("type", "")

        if t == "text":
            items.append(ParsedItem(kind="text", text=it.get("text", ""), raw=it))

        elif t == "toolRequest":
            call = it.get("toolCall", {}) or {}
            status = call.get("status", "")
            value = call.get("value", {}) or {}
            items.append(ParsedItem(
                kind="tool_request",
                tool_name=value.get("name", "<unknown>"),
                tool_args=value.get("arguments", {}) or {},
                tool_status=status,
                tool_id=it.get("id", ""),
                raw=it,
            ))

        elif t == "toolResponse":
            result = it.get("toolResult", {}) or {}
            status = result.get("status", "")
            value = result.get("value", {}) or {}
            is_err = bool(value.get("isError", False)) if isinstance(value, dict) else False
            text_parts: list[str] = []
            if isinstance(value, dict):
                for c in value.get("content", []) or []:
                    if isinstance(c, dict) and c.get("type") == "text":
                        text_parts.append(c.get("text", ""))
            items.append(ParsedItem(
                kind="tool_response",
                text="\n".join(text_parts),
                tool_status=status,
                is_error=is_err,
                tool_id=it.get("id", ""),
                raw=it,
            ))

        elif t == "thinking":
            items.append(ParsedItem(kind="thinking", text=it.get("thinking", ""), raw=it))

        else:
            items.append(ParsedItem(kind="other", text=f"[{t}]", raw=it))

    return items


def summarize_tools(messages_df: pd.DataFrame) -> Counter:
    """Count tool invocations across a messages DataFrame."""
    counts: Counter = Counter()
    for raw in messages_df.get("content_json", []):
        for item in parse_content(raw):
            if item.kind == "tool_request":
                counts[item.tool_name] += 1
    return counts


def first_user_prompt(messages_df: pd.DataFrame) -> str:
    """Return the earliest user text message — used as a session preview/title."""
    if messages_df.empty:
        return ""
    user_rows = messages_df[messages_df["role"] == "user"]
    for raw in user_rows.get("content_json", []):
        for item in parse_content(raw):
            if item.kind == "text" and item.text.strip():
                return item.text.strip()
    return ""


def count_errors(messages_df: pd.DataFrame) -> int:
    n = 0
    for raw in messages_df.get("content_json", []):
        for item in parse_content(raw):
            if item.kind == "tool_response" and item.is_error:
                n += 1
    return n
