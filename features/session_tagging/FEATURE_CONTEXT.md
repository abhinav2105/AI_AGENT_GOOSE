# Session Tagging Feature — Full Context for Report

## Student
Harshith Gudapati — SENG 691, Phase 3

---

## Feature Name
**Session Tagging** — Manual and LLM-powered tagging of Goose chat sessions

---

## Overview
This feature adds a complete session tagging system to Goose. Users can manually add tags to any session, auto-tag individual sessions using the configured LLM provider, or bulk auto-tag all sessions with one click. Tags are persisted in SQLite, visible on session cards, and can be used to filter the session list.

---

## Why This Was Built
Goose users accumulate many sessions over time with no way to categorize or find them beyond scrolling through a list by date. Session tagging solves the discoverability problem by letting users label sessions (e.g. "python", "debugging", "frontend") and then filter the list to only sessions matching a tag. The LLM auto-tagging removes the manual burden entirely — the model reads the session content and assigns relevant tags automatically.

---

## Files Added / Modified

### New Files
| File | Purpose |
|------|---------|
| `ui/desktop/src/utils/tags.ts` | Wrapper around generated SDK — simple function signatures for all tag operations |
| `ui/desktop/src/components/tags/TagInput.tsx` | Manual tag input component — text field + predefined tag suggestions |
| `ui/desktop/src/components/tags/TagPill.tsx` | Colored tag badge component with optional remove button |
| `ui/desktop/src/components/tags/TagFilter.tsx` | Filter bar on sessions list — click a tag to filter sessions |
| `features/session_tagging/README.md` | Feature documentation |
| `features/session_tagging/categories.py` | Python tag category definitions |
| `features/session_tagging/config.py` | Python config for tagging system |
| `features/session_tagging/db.py` | Python DB utilities for tagging |
| `features/session_tagging/tagger.py` | Python tagger logic |
| `features/session_tagging/requirements.txt` | Python dependencies |
| `enhancements/task_dashboard/pages/4_Tags.py` | Tags analytics page in Streamlit dashboard |

### Modified Files
| File | What Changed |
|------|-------------|
| `crates/goose-server/src/routes/session.rs` | Added 5 new REST endpoints + request/response structs + auto-tag LLM logic |
| `crates/goose/src/session/session_manager.rs` | Added `SessionTag`, `TagCount` structs + 4 DB methods: `add_tags_to_session`, `get_tags_for_session`, `remove_tag_from_session`, `get_all_tags_with_counts` |
| `crates/goose-server/src/openapi.rs` | Registered all 5 tag endpoints and 5 schemas in `ApiDoc` so they appear in `openapi.json` |
| `ui/desktop/src/components/sessions/SessionHistoryView.tsx` | Added Auto-tag button, tag display via TagInput, state for tags/loading |
| `ui/desktop/src/components/sessions/SessionListView.tsx` | Added Auto-tag All button, tag pills on session cards, tag filter integration |
| `ui/desktop/src/components/sessions/SessionsView.tsx` | Fixed session click behavior — now opens history view instead of resuming chat directly |
| `enhancements/task_dashboard/db.py` | Added tag queries |
| `enhancements/task_dashboard/pages/1_Sessions.py` | Added tag display to session list |

---

## REST API Endpoints Added (Rust/Axum)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/sessions/{session_id}/tags` | Get all tags for a session |
| PUT | `/sessions/{session_id}/tags` | Add tags to a session (manual or auto source) |
| DELETE | `/sessions/{session_id}/tags/{tag}` | Remove a specific tag from a session |
| GET | `/sessions/tags` | Get all unique tags across all sessions with counts |
| POST | `/sessions/{session_id}/tags/auto` | Auto-tag a session using the configured LLM provider |

---

## Database Layer (Rust/SQLite)

Four methods added to `SessionManager` in `crates/goose/src/session/session_manager.rs`:

- `add_tags_to_session(session_id, tags, source)` — inserts tags into `session_tags` table
- `get_tags_for_session(session_id)` — fetches all tags for a session
- `remove_tag_from_session(session_id, tag)` — deletes a specific tag
- `get_all_tags_with_counts()` — returns all distinct tags with how many sessions use each

Two new structs:
- `SessionTag { session_id, tag, source, created_at }` — individual tag record
- `TagCount { tag, count }` — tag with usage count for the filter bar

---

## Auto-Tag Algorithm (LLM-based)

The `auto_tag_session` endpoint in `session.rs`:

1. Loads the session from the DB (first 10 messages, up to 2000 characters of text)
2. Reads the user's configured provider via `Config::global().get_goose_provider()`
3. Instantiates the provider via `goose::providers::create()`
4. Sends a system prompt to the LLM:
   - System: "You are a session tagger. Return ONLY a JSON array of tag strings."
   - User message: session text + list of 30 predefined categories
5. Parses the JSON array from the LLM response using `extract_tags_from_response()`
6. Saves tags to the DB with `source = "auto"`
7. Returns the full updated tag list for that session

Predefined tag categories include: python, javascript, typescript, rust, frontend, backend, debugging, refactoring, testing, devops, data-analysis, machine-learning, automation, scripting, documentation, and more.

---

## Frontend Components

### TagInput
- Text field where users type a tag and press Enter to add it
- Shows a dropdown of predefined tag suggestions
- Calls `addTagsToSession` on add, `removeTagFromSession` on remove
- Displays existing tags as TagPill components with an X button

### TagPill
- Small colored badge showing a tag name
- Optional remove button (X)
- Used on session cards in the list and inside TagInput

### TagFilter
- Horizontal scrollable bar at the top of the sessions list
- Shows all tags that exist across all sessions with counts
- Click a tag to filter — only sessions with that tag are shown
- Multiple tags can be selected at once

### Auto-tag Button (SessionHistoryView)
- Appears in the header of any open session alongside Share and Resume
- Calls `POST /sessions/{id}/tags/auto`
- Shows spinner while running, success toast on completion

### Auto-tag All Button (SessionListView)
- Appears in the Chat History page header next to Import
- Loops through every session sequentially calling `autoTagSession`
- Shows "Tagging..." with spinner while running
- Shows toast: "Auto-tagged N sessions" when done

---

## Key Technical Decisions

| Decision | Chosen Approach | Trade-off |
|----------|----------------|-----------|
| Tag storage | SQLite `session_tags` table via existing SessionManager | Persistent, consistent with Goose data layer; requires DB migration awareness |
| Auto-tag UI | Button in session history view + bulk button in list view | User controls when to tag; no background/automatic tagging |
| LLM provider | Uses user's already-configured provider via `Config::global()` | No extra setup needed; fails if no provider configured |
| API file location | `src/utils/tags.ts` (not `src/api/`) | Survives `just generate-openapi` which wipes `src/api/`; slight indirection but stable |
| Tag source field | `"manual"` or `"auto"` stored per tag | Allows UI to distinguish user-added vs LLM-added tags |
| Session click behavior | Opens history view (not chat) | User sees tags + can choose Resume; one extra click to resume |

---

## Error Handling

| Error Condition | Where Handled | Behavior |
|----------------|--------------|----------|
| No LLM provider configured | `auto_tag_session` handler | Returns 500; UI shows toast "check that a provider is configured" |
| Session not found | `auto_tag_session` handler | Returns 404 |
| LLM returns invalid JSON | `extract_tags_from_response()` | Returns empty vec; no tags saved, no crash |
| Empty tags array on PUT | `add_session_tags` handler | Returns 400 Bad Request |
| DB error on any operation | All handlers | Returns 500 Internal Server Error |
| Auto-tag All partial failure | `handleAutoTagAll` in SessionListView | Counts successes and failures; shows warning toast "Tagged X, Y failed" |
| Tags file missing (old issue) | Resolved permanently | `tags.ts` moved to `src/utils/` — never wiped by code generation |

---

## Integration with Phase 2 Enhancements

| Phase 2 Enhancement | Integration |
|--------------------|-------------|
| Task History Dashboard | New "Tags" page (`4_Tags.py`) shows tag analytics — most used tags, sessions per tag, tag growth over time |
| Session Summarizer | Tagged sessions can be filtered and summarized; tags appear alongside session metadata |
| Token Cost Estimator | Tag filter allows users to compare token costs across sessions of the same type (e.g. all "debugging" sessions) |

---

## How to Use

### Manual Tagging
1. Open the app: `source bin/activate-hermit && just run-ui-only`
2. Click **Show All** in the left sidebar
3. Click any session to open the history view
4. Type a tag in the tag input field and press Enter

### Auto-tag One Session
1. Open any session in the history view
2. Click **Auto-tag** button in the header
3. Wait for the LLM to analyze the session and assign tags

### Auto-tag All Sessions
1. Go to **Show All** (Chat History page)
2. Click **Auto-tag All** button (top-right, next to Import)
3. All sessions are tagged sequentially

### Filter by Tag
1. On the Chat History page, tag pills appear below the header
2. Click any tag to filter the session list

---

## OpenAPI / Code Generation Notes

- All 5 endpoints have `#[utoipa::path(...)]` annotations in Rust
- All request/response structs derive `ToSchema`
- Endpoints and schemas are registered in `crates/goose-server/src/openapi.rs` under `ApiDoc`
- Running `just generate-openapi` now includes tag endpoints in `openapi.json` and generates typed functions in `sdk.gen.ts` and types in `types.gen.ts`
- The `src/utils/tags.ts` wrapper calls the generated SDK functions with simplified signatures

---

## Files NOT Changed (No Regressions)
- Core agent loop (`crates/goose/src/agents/`)
- Provider system (`crates/goose/src/providers/`)
- MCP layer (`crates/goose-mcp/`)
- CLI entry point (`crates/goose-cli/`)
- All existing session endpoints (list, get, delete, export, fork, share)
- All existing UI pages (Home, Chat, Recipes, Skills, Apps, Scheduler)

---

## Branch and Commit
- Branch: `feature/session-tagging`
- Commit message: `Add session tagging: manual tags, auto-tag via LLM, bulk auto-tag all sessions`
- Signed with DCO (`git commit -s`)
