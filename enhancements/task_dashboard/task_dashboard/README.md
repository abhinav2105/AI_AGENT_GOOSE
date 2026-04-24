# Goose Task History Dashboard

A local web dashboard for browsing, filtering, and analyzing Goose session data.
Reads directly from Goose's `sessions.db` (read-only) and presents:

- A searchable, filterable list of all past sessions.
- A drilldown view per session showing every message, tool call, argument, and result.
- Aggregate statistics: sessions per day, tokens per day, most-used tools, provider mix.

Built as **Enhancement 2** of the SENG 691 Phase 2 project plan for Goose.

---

## Quick start

```bash
# from project root
cd task_history_dashboard

# 1. create a venv (once)
python -m venv .venv

# 2. activate it
# Windows (Git Bash / MINGW):
source .venv/Scripts/activate
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate

# 3. install deps
pip install -r requirements.txt

# 4. run
streamlit run app.py
```

The dashboard opens at <http://localhost:8501>.

## Where does the data come from?

`config.py` resolves `sessions.db` in this priority order:

1. `$GOOSE_SESSIONS_DB` environment variable (explicit override).
2. OS default:
   - **Windows**: `%APPDATA%\Block\goose\data\sessions\sessions.db`
   - **macOS**:   `~/Library/Application Support/Block/goose/data/sessions/sessions.db`
   - **Linux**:   `~/.local/share/goose/sessions/sessions.db`
3. Bundled `demo_sessions.db` (run `python seed_demo_db.py` to create it).

To point the dashboard at a specific file:

```bash
# bash
GOOSE_SESSIONS_DB="/path/to/sessions.db" streamlit run app.py
# PowerShell
$env:GOOSE_SESSIONS_DB = "C:\path\to\sessions.db"; streamlit run app.py
```

## Running without a real Goose install

```bash
python seed_demo_db.py      # writes demo_sessions.db (18 synthetic sessions)
streamlit run app.py
```

## Project layout

```
task_history_dashboard/
├── app.py                  # landing page
├── config.py               # DB path resolution + pricing table
├── db.py                   # read-only SQLite access, @st.cache_data
├── parsers.py              # decode content_json into display items
├── seed_demo_db.py         # generate demo_sessions.db
├── requirements.txt
├── README.md
└── pages/
    ├── 1_Sessions.py       # filterable session list
    ├── 2_Session_Detail.py # per-session drilldown
    └── 3_Statistics.py     # charts
```

## Design notes

- **Read-only**: all connections use `file:...?mode=ro` URI — safe to run while Goose is active.
- **Caching**: `@st.cache_data(ttl=60)` keyed on the DB file's mtime. Edits to `sessions.db` auto-invalidate the cache.
- **Schema-tolerant**: works with both older (pre-threads) and newer Goose schemas.
- **Extensibility**: `PRICING_USD_PER_1M` in `config.py` is the hook for Enhancement 3 (Token Usage & Cost Estimator).
