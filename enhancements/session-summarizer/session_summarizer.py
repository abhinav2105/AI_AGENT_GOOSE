#!/usr/bin/env python3
"""
session_summarizer.py — Goose Session Summarizer
=================================================
Reads a completed Goose session from the local SQLite database, builds a
human-readable transcript, and uses an LLM to generate a structured summary
covering: objective, tools used, outcomes, errors, and session stats.

Works with any LLM provider Goose is configured for (Tetrate, Anthropic,
OpenAI, Google). The API key is read automatically from the same place
Goose stores it — no extra setup needed if Goose is already configured.

Usage:
    python session_summarizer.py --list
    python session_summarizer.py
    python session_summarizer.py --session-id 20260329_14
    python session_summarizer.py --provider anthropic --api-key sk-ant-...
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# ─── Optional imports (installed via requirements.txt) ───────────────────────

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

try:
    import keyring
    HAS_KEYRING = True
except ImportError:
    HAS_KEYRING = False

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    from google import genai as genai_client
    HAS_GOOGLE = True
except ImportError:
    HAS_GOOGLE = False


# ─── File paths (standard Goose locations on macOS/Linux) ────────────────────

DB_PATH      = Path.home() / ".local" / "share" / "goose" / "sessions" / "sessions.db"
CONFIG_PATH  = Path.home() / ".config" / "goose" / "config.yaml"
SECRETS_PATH = Path.home() / ".config" / "goose" / "secrets.yaml"
OUTPUT_DIR   = Path(__file__).parent / "sample_output"

# Goose stores all secrets as one JSON blob in the macOS Keychain under these:
KEYRING_SERVICE  = "goose"
KEYRING_USERNAME = "secrets"

# Tetrate is Goose's default managed provider — it's OpenAI-compatible
TETRATE_BASE_URL = "https://api.router.tetrate.ai/v1"


# ─── CONFIG ──────────────────────────────────────────────────────────────────

def read_goose_config() -> dict:
    """
    Read GOOSE_PROVIDER and GOOSE_MODEL from Goose's config.yaml.
    Returns an empty dict if the file doesn't exist or can't be parsed.
    """
    if not CONFIG_PATH.exists():
        return {}
    if not HAS_YAML:
        print("Warning: pyyaml not installed. Using defaults.", file=sys.stderr)
        return {}
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f) or {}


def get_api_key(provider: str) -> str | None:
    """
    Try to find the API key for the given provider in order:
      1. Environment variable  (e.g. ANTHROPIC_API_KEY, TETRATE_API_KEY)
      2. macOS/Linux Keychain  (where Goose stores keys after 'goose configure')
      3. secrets.yaml          (Goose's plaintext fallback when keyring is off)
    Returns None if no key is found anywhere.
    """
    p = provider.lower()

    # Map each provider to its env var name and secret key name
    env_var_map = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai":    "OPENAI_API_KEY",
        "google":    "GOOGLE_API_KEY",
        "gemini":    "GOOGLE_API_KEY",
        "tetrate":   "TETRATE_API_KEY",
        "azure":     "AZURE_OPENAI_API_KEY",
        "databricks":"DATABRICKS_TOKEN",
    }
    secret_key_map = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai":    "OPENAI_API_KEY",
        "google":    "GOOGLE_API_KEY",
        "gemini":    "GOOGLE_API_KEY",
        "tetrate":   "TETRATE_API_KEY",
    }

    # Find which keys to look up for this provider
    env_var    = env_var_map.get(p)
    secret_key = secret_key_map.get(p)

    # 1. Check environment variable
    if env_var:
        val = os.environ.get(env_var)
        if val:
            return val

    # 2. Check macOS/Linux Keychain (same place Goose stores keys)
    if HAS_KEYRING and secret_key:
        try:
            raw = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
            if raw:
                secrets = json.loads(raw)
                if secret_key in secrets:
                    return secrets[secret_key]
        except Exception:
            pass  # Keychain unavailable — fall through to secrets.yaml

    # 3. Check secrets.yaml (Goose's plaintext fallback)
    if SECRETS_PATH.exists() and secret_key and HAS_YAML:
        try:
            with open(SECRETS_PATH) as f:
                file_secrets = yaml.safe_load(f) or {}
            if secret_key in file_secrets:
                return file_secrets[secret_key]
        except Exception:
            pass

    return None


# ─── DATABASE ─────────────────────────────────────────────────────────────────

def list_sessions(limit: int = 15) -> list[dict]:
    """
    Return the most recent 'user' sessions from the database.
    Filters out scheduled/sub-agent/hidden sessions.
    """
    if not DB_PATH.exists():
        print(f"Error: Goose database not found at {DB_PATH}", file=sys.stderr)
        print("Make sure Goose has been run at least once.", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        """
        SELECT id, name, created_at, total_tokens, working_dir
        FROM   sessions
        WHERE  session_type = 'user'
        ORDER  BY created_at DESC
        LIMIT  ?
        """,
        (limit,),
    )
    sessions = [dict(row) for row in cur.fetchall()]
    conn.close()
    return sessions


def get_session(session_id: str) -> dict | None:
    """Return a single session row by ID, or None if not found."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_messages(session_id: str) -> list[dict]:
    """Return all messages for a session in chronological order."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        """
        SELECT role, content_json, created_timestamp
        FROM   messages
        WHERE  session_id = ?
        ORDER  BY created_timestamp ASC
        """,
        (session_id,),
    )
    messages = [dict(row) for row in cur.fetchall()]
    conn.close()
    return messages


# ─── TRANSCRIPT BUILDER ───────────────────────────────────────────────────────

def extract_text_from_content(content_json: str) -> str:
    """
    Parse a message's content_json array and return a readable string.

    Goose stores message content as a JSON array of typed blocks:
      {"type":"text", "text":"..."}
      {"type":"toolRequest", "toolCall":{"value":{"name":"...", "arguments":{...}}}}
      {"type":"toolResponse", "toolResult":{"value":{"content":[...], "isError":false}}}
    """
    try:
        blocks = json.loads(content_json)
    except (json.JSONDecodeError, TypeError):
        return str(content_json)

    parts = []
    for block in blocks:
        btype = block.get("type", "")

        if btype == "text":
            text = block.get("text", "").strip()
            if text:
                parts.append(text)

        elif btype == "toolRequest":
            # Extract tool name and arguments from the nested structure
            tool_call = block.get("toolCall", {})
            value     = tool_call.get("value", {})
            name      = value.get("name", "unknown_tool")
            args      = value.get("arguments", {})
            args_str  = json.dumps(args)
            # Truncate long arguments so the transcript stays readable
            if len(args_str) > 300:
                args_str = args_str[:300] + "..."
            parts.append(f"[TOOL CALL → {name}]\nArgs: {args_str}")

        elif btype == "toolResponse":
            # Extract result text and error status
            tool_result = block.get("toolResult", {})
            value       = tool_result.get("value", {})
            is_error    = value.get("isError", False)
            content     = value.get("content", [])

            # Content is itself an array of blocks — grab the text ones
            result_text = ""
            if isinstance(content, list):
                texts = [c.get("text", "") for c in content if c.get("type") == "text"]
                result_text = " ".join(texts)
            elif isinstance(content, str):
                result_text = content

            # Truncate long tool outputs
            if len(result_text) > 400:
                result_text = result_text[:400] + "..."

            prefix = "[TOOL ERROR]" if is_error else "[TOOL RESULT]"
            parts.append(f"{prefix}: {result_text}")

    return "\n".join(parts)


def build_transcript(messages: list[dict], max_chars: int = 14000) -> str:
    """
    Convert raw database messages into a readable transcript for the LLM.
    If the session is very long, keeps the beginning and end (most important parts)
    and notes how many characters were skipped in the middle.
    """
    lines = []
    for msg in messages:
        role = msg["role"].upper()
        text = extract_text_from_content(msg["content_json"])
        if not text.strip():
            continue
        lines.append(f"[{role}]\n{text}")

    full_transcript = "\n\n".join(lines)

    # If the transcript fits within the limit, return it as-is
    if len(full_transcript) <= max_chars:
        return full_transcript

    # Otherwise keep first half + last half with a truncation notice in the middle
    half = max_chars // 2
    skipped = len(full_transcript) - max_chars
    return (
        full_transcript[:half]
        + f"\n\n... [{skipped:,} characters skipped — session was very long] ...\n\n"
        + full_transcript[-half:]
    )


# ─── LLM SUMMARIZATION ───────────────────────────────────────────────────────

SUMMARY_PROMPT_TEMPLATE = """\
You are analyzing a session log from Goose — an open-source autonomous AI agent \
that can write code, run shell commands, manage files, and call external APIs.

Below is the full transcript of one session. Generate a structured summary with \
exactly these five sections:

## Objective
What was the user trying to accomplish? (1–3 sentences)

## Tools & Actions Used
List each tool that was invoked and what it did. Use bullet points.
Example:
- developer__shell: Ran `npm install` to install dependencies
- apps__create_app: Created a pixel-art Tamagotchi game HTML app

## Results & Outcomes
What was successfully accomplished? What is the final deliverable or output?

## Errors & Issues
Any failures, errors, or problems encountered. Write "None" if the session was clean.

## Session Stats
- Session ID: {session_id}
- Messages exchanged: {message_count}
- Total tokens used: {total_tokens}
- Working directory: {working_dir}
- Date: {created_at}

---

SESSION TRANSCRIPT:

{transcript}
"""


def summarize_with_openai_compat(
    transcript: str,
    session: dict,
    messages: list[dict],
    api_key: str,
    model: str,
    base_url: str | None = None,
) -> str:
    """
    Call any OpenAI-compatible API (OpenAI, Tetrate, Azure, etc.).
    Pass base_url to redirect to a non-OpenAI endpoint.
    """
    if not HAS_OPENAI:
        raise RuntimeError(
            "openai package not installed.\nRun: pip install openai"
        )

    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url

    client = openai.OpenAI(**kwargs)
    prompt = SUMMARY_PROMPT_TEMPLATE.format(
        session_id    = session.get("id", "N/A"),
        message_count = len(messages),
        total_tokens  = session.get("total_tokens") or "N/A",
        working_dir   = session.get("working_dir", "N/A"),
        created_at    = session.get("created_at", "N/A"),
        transcript    = transcript,
    )
    response = client.chat.completions.create(
        model    = model or "gpt-4o-mini",
        messages = [{"role": "user", "content": prompt}],
        max_tokens = 1024,
    )
    return response.choices[0].message.content


def summarize_with_anthropic(
    transcript: str,
    session: dict,
    messages: list[dict],
    api_key: str,
    model: str,
) -> str:
    """Call the Anthropic API directly."""
    if not HAS_ANTHROPIC:
        raise RuntimeError(
            "anthropic package not installed.\nRun: pip install anthropic"
        )

    client = anthropic.Anthropic(api_key=api_key)
    prompt = SUMMARY_PROMPT_TEMPLATE.format(
        session_id    = session.get("id", "N/A"),
        message_count = len(messages),
        total_tokens  = session.get("total_tokens") or "N/A",
        working_dir   = session.get("working_dir", "N/A"),
        created_at    = session.get("created_at", "N/A"),
        transcript    = transcript,
    )
    response = client.messages.create(
        model      = model or "claude-haiku-4-5",
        max_tokens = 1024,
        messages   = [{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def summarize_with_google(
    transcript: str,
    session: dict,
    messages: list[dict],
    api_key: str,
    model: str,
) -> str:
    """Call the Google Gemini API."""
    if not HAS_GOOGLE:
        raise RuntimeError(
            "google-genai package not installed.\n"
            "Run: pip install google-genai"
        )

    client = genai_client.Client(api_key=api_key)
    prompt = SUMMARY_PROMPT_TEMPLATE.format(
        session_id    = session.get("id", "N/A"),
        message_count = len(messages),
        total_tokens  = session.get("total_tokens") or "N/A",
        working_dir   = session.get("working_dir", "N/A"),
        created_at    = session.get("created_at", "N/A"),
        transcript    = transcript,
    )
    response = client.models.generate_content(
        model    = model or "gemini-2.0-flash",
        contents = prompt,
    )
    return response.text


def call_llm(
    transcript: str,
    session: dict,
    messages: list[dict],
    provider: str,
    model: str,
    api_key: str,
) -> str:
    """
    Dispatch to the right LLM SDK based on the provider name.

    Tetrate is OpenAI-compatible (it routes to Claude/GPT/Gemini behind a proxy),
    so we use the OpenAI SDK with Tetrate's base URL.
    """
    p = provider.lower()

    if "tetrate" in p:
        return summarize_with_openai_compat(
            transcript, session, messages, api_key, model,
            base_url=TETRATE_BASE_URL,
        )
    elif "openai" in p or "azure" in p or "gpt" in p:
        base = "https://api.openai.com/v1" if "openai" in p else None
        return summarize_with_openai_compat(
            transcript, session, messages, api_key, model, base_url=base
        )
    elif "anthropic" in p or "claude" in p:
        return summarize_with_anthropic(
            transcript, session, messages, api_key, model
        )
    elif "google" in p or "gemini" in p or "vertex" in p:
        return summarize_with_google(
            transcript, session, messages, api_key, model
        )
    else:
        # Unknown provider — try OpenAI-compatible as a best guess
        print(f"Warning: unknown provider '{provider}', trying OpenAI-compatible API.")
        return summarize_with_openai_compat(
            transcript, session, messages, api_key, model
        )


# ─── OUTPUT ──────────────────────────────────────────────────────────────────

def save_summary(session_id: str, summary: str, output_file: str | None = None) -> Path:
    """
    Save the summary as a markdown file.
    Default location: sample_output/<session_id>_summary.md
    """
    if output_file:
        path = Path(output_file)
    else:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUTPUT_DIR / f"{session_id}_summary.md"

    header = (
        f"# Goose Session Summary — {session_id}\n"
        f"*Generated by session_summarizer.py on "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n"
    )
    path.write_text(header + summary, encoding="utf-8")
    return path


# ─── CLI ─────────────────────────────────────────────────────────────────────

def print_sessions_table(sessions: list[dict]) -> None:
    """Print available sessions in a numbered table."""
    print(f"\n{'#':<4} {'Session ID':<20} {'Name':<35} {'Date':<20} {'Tokens':>8}")
    print("─" * 92)
    for i, s in enumerate(sessions, 1):
        name   = (s["name"] or "Unnamed")[:34]
        date   = (s["created_at"] or "")[:19]
        tokens = s["total_tokens"] or 0
        print(f"{i:<4} {s['id']:<20} {name:<35} {date:<20} {tokens:>8,}")
    print()


def interactive_pick(sessions: list[dict]) -> dict:
    """Show a numbered list and let the user pick one session."""
    print_sessions_table(sessions)
    while True:
        try:
            choice = input("Enter session number (or 'q' to quit): ").strip()
            if choice.lower() == "q":
                sys.exit(0)
            idx = int(choice) - 1
            if 0 <= idx < len(sessions):
                return sessions[idx]
            print(f"Please enter a number between 1 and {len(sessions)}.")
        except (ValueError, KeyboardInterrupt):
            print("\nCancelled.")
            sys.exit(0)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a human-readable summary of a Goose session.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python session_summarizer.py --list
  python session_summarizer.py
  python session_summarizer.py --session-id 20260329_14
  python session_summarizer.py --provider anthropic --api-key sk-ant-...
  python session_summarizer.py --session-id 20260329_14 --output-file my_summary.md
        """,
    )
    parser.add_argument("--list",       action="store_true", help="List available sessions and exit")
    parser.add_argument("--session-id", help="ID of the session to summarize (e.g. 20260329_14)")
    parser.add_argument("--provider",   help="Override LLM provider (anthropic / openai / google / tetrate)")
    parser.add_argument("--model",      help="Override model name")
    parser.add_argument("--api-key",    help="Override API key (default: read from keychain / env)")
    parser.add_argument("--output-file",help="Save summary to this file instead of sample_output/")
    args = parser.parse_args()

    # ── Step 1: Read Goose config ────────────────────────────────────────────
    config   = read_goose_config()
    provider = args.provider or config.get("GOOSE_PROVIDER") or "tetrate"
    model    = args.model    or config.get("GOOSE_MODEL")    or ""

    # ── Step 2: List sessions mode ───────────────────────────────────────────
    sessions = list_sessions()
    if not sessions:
        print("No user sessions found in the Goose database.")
        sys.exit(0)

    if args.list:
        print_sessions_table(sessions)
        return

    # ── Step 3: Choose which session to summarize ────────────────────────────
    if args.session_id:
        session = get_session(args.session_id)
        if not session:
            print(f"Error: session '{args.session_id}' not found in the database.")
            sys.exit(1)
    else:
        print("Available sessions:")
        session = interactive_pick(sessions)

    session_id = session["id"]
    print(f"\nSummarizing session: {session_id} — {session.get('name') or 'Unnamed'}")

    # ── Step 4: Get API key ──────────────────────────────────────────────────
    api_key = args.api_key or get_api_key(provider)
    if not api_key:
        print(
            f"\nNo API key found for provider '{provider}'.\n"
            f"Options:\n"
            f"  1. Set env var:   export TETRATE_API_KEY=your_key_here\n"
            f"  2. Pass directly: python session_summarizer.py --api-key your_key_here\n"
            f"  3. Run 'goose configure' to store the key in your system keychain."
        )
        sys.exit(1)

    # ── Step 5: Load messages and build transcript ───────────────────────────
    messages   = get_messages(session_id)
    if not messages:
        print(f"No messages found for session '{session_id}'.")
        sys.exit(0)

    print(f"Loaded {len(messages)} messages. Building transcript...")
    transcript = build_transcript(messages)

    # ── Step 6: Call LLM ─────────────────────────────────────────────────────
    print(f"Calling {provider} ({model or 'default model'}) to generate summary...")
    try:
        summary = call_llm(transcript, session, messages, provider, model, api_key)
    except Exception as e:
        print(f"\nError calling LLM: {e}")
        sys.exit(1)

    # ── Step 7: Print and save ───────────────────────────────────────────────
    print("\n" + "═" * 70)
    print(summary)
    print("═" * 70 + "\n")

    saved_path = save_summary(session_id, summary, args.output_file)
    print(f"Summary saved to: {saved_path}")


if __name__ == "__main__":
    main()
