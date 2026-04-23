# Enhancement 2 — Task History Dashboard

**Course:** SENG 691 AI Agent Computing — Phase 2
**Group 2 — Goose Autonomous Coding Agent**
**Enhancement target:** existing session-storage / chat-history subsystem of Goose.

This document is the Phase‑2 report section for Enhancement 2 (one of three enhancements in the combined team submission). It follows the rubric sections: motivation, implementation, architecture, evidence, limitations, Phase 3 plan.

---

## 1. What was enhanced (and why)

### 1.1 The existing feature
Goose already persists every session locally in a SQLite database at
`%APPDATA%\Block\goose\data\sessions\sessions.db` (Windows) / `~/Library/Application Support/Block/goose/...` (macOS) / `~/.local/share/goose/sessions/sessions.db` (Linux).

Schema (verified from `crates/goose/src/session/session_manager.rs`, schema v10):
- `sessions(id, name, description, session_type, working_dir, created_at, updated_at, total_tokens, input_tokens, output_tokens, accumulated_*_tokens, provider_name, goose_mode, …)`
- `messages(id, session_id, role, content_json, created_timestamp, timestamp, tokens, …)`

Goose’s current UI exposes this data only as a linear chat‑history sidebar inside the active session. There is **no cross‑session view, no filters, no statistics, and no audit trail over time**.

### 1.2 The gap the dashboard fills
| Existing chat history | Task History Dashboard |
|---|---|
| One session at a time | All sessions at once |
| Scroll-only navigation | Filter by date / working‑dir / type / free‑text search |
| Raw, linear message stream | Drilldown with tool‑call cards, arguments, results, error badges |
| No aggregation | Sessions/day, tokens/day, top‑N tools, provider mix |
| Requires running Goose app | Stand‑alone, read‑only, runs even if Goose itself is closed |
| No way to audit across projects | Unified cross‑project auditing |

### 1.3 Technical justification (performance / efficiency / scalability)
- **Efficiency** — eliminates the need for `sqlite3` CLI queries or scrolling to review past work.
- **Scalability** — as session count grows, a filtered + indexed view becomes necessary; the dashboard caches pre‑aggregated queries with a 60‑second TTL keyed on the DB file’s `mtime`, so the cache self‑invalidates whenever Goose writes a new row.
- **Performance** — dashboard opens the DB in **read‑only URI mode** (`file:…?mode=ro`). It never blocks, locks, or races with the live Goose process.

---

## 2. High‑level description

A local web dashboard built with **Streamlit + Plotly + Pandas**. Three pages:

1. **📋 Sessions** — filterable, sortable table of every past session. Click → drilldown.
2. **🔍 Session Detail** — header summary (tool calls, errors, tokens, provider) + full message timeline. Each tool call renders as an expandable card showing its arguments, result text, and success/error badge.
3. **📊 Statistics** — sessions/day (bar), tokens/day (line), top‑15 tools (horizontal bar), type + provider mix (donut).

Runs with:
```bash
cd enhancements/task_dashboard
python -m venv .venv && source .venv/Scripts/activate
pip install -r requirements.txt
streamlit run app.py
```
Opens at <http://localhost:8501>. Automatically finds `sessions.db` via OS-specific defaults; falls back to a bundled demo DB.

---

## 3. Technical changes & architecture

### 3.1 Module / interaction map
```
            ┌────────────────────────────┐
            │          app.py            │  landing page + metrics
            └──────────────┬─────────────┘
                           │ (reads)
      ┌────────────────────┼───────────────────────┐
      │                    │                       │
┌─────▼──────┐      ┌──────▼──────┐       ┌────────▼────────┐
│ 1_Sessions │      │ 2_Session_  │       │ 3_Statistics    │
│   .py      │      │   Detail.py │       │   .py           │
└─────┬──────┘      └──────┬──────┘       └────────┬────────┘
      │                    │                       │
      │            ┌───────▼───────┐               │
      └────────────►   db.py       ◄───────────────┘
                   │ (cached, RO)  │
                   └───────┬───────┘
                           │
                   ┌───────▼────────┐
                   │ parsers.py     │  decodes content_json
                   └───────┬────────┘
                           │
                   ┌───────▼────────┐          ┌─────────────────┐
                   │ config.py      │  ◄──────► seed_demo_db.py  │
                   │ (path + pricing)│          │ (fallback data) │
                   └───────┬────────┘          └─────────────────┘
                           │
                   ┌───────▼───────────────┐
                   │ sessions.db (Goose)   │  read-only
                   └───────────────────────┘
```

### 3.2 New files (no modifications to the Goose core; additive only)
| File | Purpose | LOC |
|---|---|---:|
| `app.py` | Landing page, top-level metrics, path diagnostic | 78 |
| `config.py` | OS-aware DB path resolution, pricing table (hook for Enhancement 3) | 64 |
| `db.py` | Read-only SQLite access, `@st.cache_data` (TTL=60s, keyed on file mtime) | 128 |
| `parsers.py` | Decodes `content_json` → `ParsedItem` (text / tool_request / tool_response / thinking / other) | 125 |
| `pages/1_Sessions.py` | Filterable session table + click‑to‑drill selection | 113 |
| `pages/2_Session_Detail.py` | Per-session timeline with collapsible tool-call cards | 117 |
| `pages/3_Statistics.py` | Aggregate charts (Plotly) | 100 |
| `seed_demo_db.py` | Generates a demo DB matching Goose schema v10 | 224 |
| **Total (ex. demo seed)** | | **725** |

No Rust or TypeScript changes. No database migrations. No modifications to the Goose agent loop, provider system, MCP layer, or UI app.

### 3.3 ER view (the subset we consume)
```
┌──────────────────────────────┐        ┌────────────────────────────────┐
│ sessions                     │ 1    n │ messages                       │
│──────────────────────────────│────────│────────────────────────────────│
│ id            TEXT PK        │        │ id                INT PK       │
│ name          TEXT           │        │ session_id        TEXT FK      │
│ working_dir   TEXT           │        │ role              TEXT         │
│ session_type  TEXT           │        │ content_json      TEXT (JSON)  │
│ created_at    TS             │        │ created_timestamp INT          │
│ updated_at    TS             │        │ timestamp         TS           │
│ total_tokens, input_tokens,  │        │ tokens            INT          │
│ output_tokens, acc_*_tokens  │        └────────────────────────────────┘
│ provider_name TEXT           │
│ goose_mode    TEXT           │        content_json items:
└──────────────────────────────┘          • {type:"text", text}
                                          • {type:"toolRequest", toolCall:{value:{name,arguments}}}
                                          • {type:"toolResponse", toolResult:{value:{content[].text, isError}}}
                                          • {type:"thinking", thinking}
```

### 3.4 Algorithmic choices
- **Cache-key strategy**: `@st.cache_data(ttl=60, ..., key=(db_path_str, mtime))`. The mtime parameter is a stable hash input so edits to the DB invalidate the cache immediately — no manual refresh needed.
- **Defensive parser**: `parsers.parse_content` tolerates missing keys, unknown item types, and malformed JSON rows, so a single corrupt record never crashes the UI.
- **Streamlit multi-page** convention (`pages/*.py`) gives us sidebar navigation for free and a single Streamlit process for all three views.

---

## 4. Evidence of improvement

### 4.1 Baseline vs post-change

| Task | Baseline (raw SQLite CLI) | With Dashboard | Improvement |
|---|---|---|---|
| List all sessions with msg counts | Type a 5-line SQL JOIN + GROUP BY query | Open `/` → page loads | ~100× fewer keystrokes |
| Find all sessions under a specific working_dir | Write `WHERE working_dir LIKE '%...%'` | Multiselect filter | no SQL knowledge required |
| See which tool was used most this week | Parse every `content_json` by hand | Open Statistics → top‑tools chart | n/a (was infeasible by hand) |
| Inspect one session’s tool calls and errors | `jq` over a content_json column | Click row → expandable cards | minutes → seconds |

### 4.2 Run-time measurements (own test machine, 11 sessions / 106 messages)

| Operation | Cold | Warm (cached) |
|---|---:|---:|
| `load_sessions` (full JOIN + msg count) | ~14 ms | <1 ms |
| `load_session_messages(sid)` | ~3 ms | <1 ms |
| `parse_content` on one message | ~0.1 ms | — |
| First page render (app.py) | ~0.9 s | ~0.15 s |

Cache TTL is 60 s; `mtime_for()` causes instant invalidation when Goose writes. Tested concurrent run with Goose active — no `database is locked` errors (RO mode confirms safety).

### 4.3 LOC summary
- **Added:** 949 Python LOC across 9 files (725 for the dashboard, 224 for the demo seeder).
- **Modified:** 0 lines in Goose core. This enhancement is purely additive inside `enhancements/task_dashboard/`.
- **Deleted:** 1 file — replaced `enhancements/task_dashboard/.gitkeep` placeholder.

### 4.4 Lizard complexity analysis
Ran `python -m lizard app.py config.py db.py parsers.py pages/` (see raw output in demo logs).

| Metric | Value |
|---|---:|
| Total NLOC | 548 |
| Avg CCN | 4.2 |
| Avg tokens/function | 92.7 |
| Functions analyzed | 16 |
| Warnings (CCN > 15) | **1** |

The single warning is `parsers.parse_content` (CCN = 18, NLOC = 43). It is the central dispatcher that handles **five distinct `content_json` item shapes**, each with defensive null-handling for malformed rows. The high CCN is inherent to the data format rather than accidental complexity; splitting into per-type handlers would reduce CCN to ~4 but add 30 LOC of plumbing. Accepting as a known tradeoff; will revisit if new item types are added in a future Goose schema.

All other functions are ≤ CCN 6 — well under the Lizard default threshold of 15.

### 4.5 Screenshots / logs (bundle with submission)
- `screenshots/01_sessions_list.png` — filtered table
- `screenshots/02_session_detail.png` — timeline with tool-call expanded
- `screenshots/03_statistics.png` — charts page
- `logs/streamlit_launch.txt` — clean startup log against real `sessions.db`
- `logs/lizard_report.txt` — full complexity output

---

## 5. Known limitations

1. **Read-only only.** No renaming/tagging/deleting of sessions from the dashboard. Intentional — session-writing is Goose’s responsibility and would require schema coordination. Tagging is Phase 3 Feature 1.
2. **No live streaming.** Cache TTL is 60 s; during a live Goose session you may need to `R` to refresh Streamlit to see the newest messages in real time. Could be addressed by SSE or a `st.autorefresh` component.
3. **Tool-call aggregation is O(messages).** `pages/3_Statistics.py` walks every message across every session to count tool calls. Fine for hundreds of sessions; for 10 k+ sessions we’d materialize a `tool_name` column either in a view or in a background job. Currently cached, so not felt in practice.
4. **`parse_content` complexity (CCN 18)** — see §4.4.
5. **Schema version drift.** The dashboard was written against schema v10. We gracefully `LEFT JOIN` on `messages` and do not rely on `threads` / `thread_messages`, so earlier schemas (pre-v10) still work. A future Goose schema change to `content_json` shape would require updating `parsers.py`.

---

## 6. Phase 3 plan

Planned additions building on this dashboard:

1. **Integrate Token Usage & Cost Estimator (Enhancement 3)** — `config.PRICING_USD_PER_1M` is already in place; a fourth page `4_Costs.py` will multiply `input_tokens × input_price + output_tokens × output_price` per provider and show cumulative spend.
2. **Session tagging UI (Phase 3 New Feature 1)** — once Goose adds a `tags` column to the `sessions` table, expose a tag filter + colored chip column in `pages/1_Sessions.py`.
3. **Live mode** — replace 60 s TTL with a file-watcher or `st_autorefresh(interval=3000)` so an active session updates in near‑real‑time.
4. **Export** — CSV/JSON export of filtered session lists for reporting.
5. **Branch visualization** (pending Conversation Branching — Phase 3 New Feature 2) — render parent/child session relationships as a tree in the session list.

---

## 7. Setup & run (for graders)

```bash
git checkout Task-History-Dashboard-
cd enhancements/task_dashboard
python -m venv .venv
source .venv/Scripts/activate              # Git Bash on Windows
# or: .venv\Scripts\Activate.ps1            # PowerShell
pip install -r requirements.txt
# optional: generate demo data if no real Goose DB is present
python seed_demo_db.py
streamlit run app.py
```

Open <http://localhost:8501>. Dashboard auto-detects Goose's default `sessions.db` location on your OS, or falls back to the bundled demo DB.

**New dependencies:** `streamlit>=1.32`, `pandas>=2.2`, `plotly>=5.20`. All are pure-Python installs; no system libs required.
