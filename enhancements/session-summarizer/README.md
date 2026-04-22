# Goose Session Summarizer

**SENG 691 — AI Agent Computing | UMBC**
Enhancement by Harshith Gudapati

---

## What it does

After a Goose session ends, this tool generates a human-readable summary covering:

- **Objective** — what the user was trying to accomplish
- **Tools & Actions Used** — every tool invoked and what it did
- **Results & Outcomes** — what was successfully accomplished
- **Errors & Issues** — any failures encountered
- **Session Stats** — token usage, working directory, timestamps

The summary is printed to the terminal and saved as a Markdown file in `sample_output/`.

---

## How it works

Goose stores all session data in a local SQLite database:

```
~/.local/share/goose/sessions/sessions.db
```

This script reads that database directly — no Goose process needs to be running.
It then calls the same LLM provider Goose is configured to use (reading the API key
from the same place Goose stores it: the macOS Keychain or `secrets.yaml`).

---

## Setup

**Requirements:** Python 3.10+

```bash
cd enhancements/session-summarizer
pip install -r requirements.txt
```

No extra API key configuration is needed if Goose is already set up on your machine.
The script reads the key Goose already stored during `goose configure`.

---

## Usage

### List available sessions
```bash
python session_summarizer.py --list
```
Output:
```
#    Session ID           Name                                Date                   Tokens
────────────────────────────────────────────────────────────────────────────────────────────
1    20260329_14          Tamagotchi game                     2026-03-29 22:08:50     4,880
2    20260329_13          Gibberish input                     2026-03-29 22:08:45     4,897
```

### Interactive mode (pick from a menu)
```bash
python session_summarizer.py
```

### Summarize a specific session
```bash
python session_summarizer.py --session-id 20260329_14
```

### Override provider or API key
```bash
# Use Anthropic directly
python session_summarizer.py --provider anthropic --api-key sk-ant-...

# Use OpenAI
python session_summarizer.py --provider openai --api-key sk-...

# Use Tetrate with explicit key
python session_summarizer.py --provider tetrate --api-key your-tetrate-key
```

### Save to a custom file
```bash
python session_summarizer.py --session-id 20260329_14 --output-file my_summary.md
```

---

## API key resolution order

The script finds your API key automatically — no manual export needed if Goose is configured:

1. `--api-key` CLI flag (explicit override)
2. Environment variable (`TETRATE_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc.)
3. **macOS/Linux Keychain** — where `goose configure` stores keys
4. `~/.config/goose/secrets.yaml` — Goose's plaintext fallback

---

## Supported providers

| Provider | How Goose calls it | SDK used |
|---|---|---|
| Tetrate (default) | `tetrate` | `openai` (compatible API) |
| Anthropic | `anthropic` | `anthropic` |
| OpenAI | `openai` | `openai` |
| Google Gemini | `google` | `google-generativeai` |

---

## Output example

See [`sample_output/`](sample_output/) for real generated summaries.

---

## Project context

This enhancement is part of Phase 2 of the SENG 691 class project analyzing the
[Goose AI agent](https://github.com/block/goose) codebase. The enhancement lives
in `enhancements/session-summarizer/` and does not modify any Rust crates —
it is a standalone Python tool that reads Goose's existing data.
