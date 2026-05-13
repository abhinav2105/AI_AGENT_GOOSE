# ══════════════════════════════════════════════════════════════
# Makefile — Goose AI Agent Computing Project
# SENG 691 — Group 2 — Spring 2026
# ══════════════════════════════════════════════════════════════
# Usage:
#   make install        — install all Python dependencies
#   make run-cost       — run Token Cost Estimator
#   make run-summarizer — run Session Summarizer (interactive)
#   make run-dashboard  — run Task History Dashboard
#   make run-branching  — run Conversation Branching (interactive CLI)
#   make run-branch-ui  — run Conversation Branching Streamlit UI
#   make run-goose      — build and run Goose desktop app from source
#   make check          — check all prerequisites
#   make help           — show this help message
# ══════════════════════════════════════════════════════════════

PYTHON     := python3
PIP        := pip3
REPO_ROOT  := $(shell pwd)

# ── Paths ──────────────────────────────────────────────────────
COST_DIR      := enhancements/token_cost_estimator
SUMM_DIR      := enhancements/session_summarizer
DASH_DIR      := enhancements/task_dashboard
BRANCH_DIR    := features/conversation_branching
TAGGING_DIR   := features/session_tagging

# ── Colors for output ──────────────────────────────────────────
GREEN  := \033[0;32m
YELLOW := \033[0;33m
BLUE   := \033[0;34m
RESET  := \033[0m

.PHONY: all install check run-cost run-summarizer run-dashboard \
        run-branching run-branch-ui run-goose help clean

# ── Default target ─────────────────────────────────────────────
all: help

# ══════════════════════════════════════════════════════════════
# HELP
# ══════════════════════════════════════════════════════════════
help:
	@echo ""
	@echo "$(BLUE)╔══════════════════════════════════════════════════════╗$(RESET)"
	@echo "$(BLUE)║     Goose Project — SENG 691 Group 2 — Makefile      ║$(RESET)"
	@echo "$(BLUE)╚══════════════════════════════════════════════════════╝$(RESET)"
	@echo ""
	@echo "$(GREEN)Setup:$(RESET)"
	@echo "  make check          Check all prerequisites"
	@echo "  make install        Install all Python dependencies"
	@echo ""
	@echo "$(GREEN)Phase 2 Enhancements:$(RESET)"
	@echo "  make run-cost       Token Usage & Cost Estimator"
	@echo "  make run-summarizer Session Summarizer (interactive)"
	@echo "  make run-dashboard  Task History Dashboard (localhost:8501)"
	@echo ""
	@echo "$(GREEN)Phase 3 Features:$(RESET)"
	@echo "  make run-branching  Conversation Branching CLI (interactive)"
	@echo "  make run-branch-ui  Conversation Branching Web UI (localhost:8501)"
	@echo "  make run-goose      Build and run Goose desktop app from source"
	@echo ""
	@echo "$(GREEN)Utilities:$(RESET)"
	@echo "  make clean          Remove generated reports and cache files"
	@echo "  make help           Show this message"
	@echo ""

# ══════════════════════════════════════════════════════════════
# CHECK PREREQUISITES
# ══════════════════════════════════════════════════════════════
check:
	@echo ""
	@echo "$(BLUE)Checking prerequisites...$(RESET)"
	@echo ""

	@# Check Python
	@if command -v python3 >/dev/null 2>&1; then \
		echo "$(GREEN)✅ Python3:$(RESET)  $$(python3 --version)"; \
	else \
		echo "❌  Python3 not found. Install from https://python.org"; \
	fi

	@# Check pip
	@if command -v pip3 >/dev/null 2>&1; then \
		echo "$(GREEN)✅ pip3:$(RESET)     $$(pip3 --version | cut -d' ' -f1-2)"; \
	else \
		echo "❌  pip3 not found."; \
	fi

	@# Check streamlit
	@if command -v streamlit >/dev/null 2>&1; then \
		echo "$(GREEN)✅ Streamlit:$(RESET) $$(streamlit version 2>/dev/null | head -1)"; \
	else \
		echo "$(YELLOW)⚠️  Streamlit not found. Run: make install$(RESET)"; \
	fi

	@# Check sessions.db
	@DB_PATH=$$( \
		if [ "$$(uname)" = "Darwin" ]; then \
			echo "$$HOME/Library/Application Support/Block/goose/sessions/sessions.db"; \
		else \
			echo "$$HOME/.local/share/goose/sessions/sessions.db"; \
		fi \
	); \
	if [ -f "$$DB_PATH" ]; then \
		echo "$(GREEN)✅ sessions.db:$(RESET) Found at $$DB_PATH"; \
	else \
		echo "$(YELLOW)⚠️  sessions.db not found. Run Goose at least once first.$(RESET)"; \
	fi

	@# Check Goose hermit
	@if [ -f "bin/hermit" ]; then \
		echo "$(GREEN)✅ Goose source:$(RESET) bin/hermit found — run 'make run-goose' to build"; \
	else \
		echo "$(YELLOW)⚠️  bin/hermit not found. Are you in the repo root?$(RESET)"; \
	fi

	@echo ""

# ══════════════════════════════════════════════════════════════
# INSTALL ALL DEPENDENCIES
# ══════════════════════════════════════════════════════════════
install:
	@echo ""
	@echo "$(BLUE)Installing dependencies for all modules...$(RESET)"
	@echo ""

	@echo "$(YELLOW)→ Session Summarizer$(RESET)"
	@$(PIP) install -r $(SUMM_DIR)/requirements.txt --quiet
	@echo "$(GREEN)  ✅ Done$(RESET)"

	@echo "$(YELLOW)→ Task History Dashboard$(RESET)"
	@$(PIP) install -r $(DASH_DIR)/requirements.txt --quiet
	@echo "$(GREEN)  ✅ Done$(RESET)"

	@echo "$(YELLOW)→ Conversation Branching$(RESET)"
	@$(PIP) install -r $(BRANCH_DIR)/requirements.txt --quiet
	@echo "$(GREEN)  ✅ Done$(RESET)"

	@echo "$(YELLOW)→ Token Cost Estimator (no external deps)$(RESET)"
	@echo "$(GREEN)  ✅ Done$(RESET)"

	@echo ""
	@echo "$(GREEN)All dependencies installed successfully!$(RESET)"
	@echo ""

# ══════════════════════════════════════════════════════════════
# PHASE 2 — TOKEN COST ESTIMATOR
# ══════════════════════════════════════════════════════════════
run-cost:
	@echo ""
	@echo "$(BLUE)Running Token Usage & Cost Estimator...$(RESET)"
	@echo ""
	@cd $(COST_DIR) && $(PYTHON) cost_estimator.py

# ══════════════════════════════════════════════════════════════
# PHASE 2 — SESSION SUMMARIZER
# ══════════════════════════════════════════════════════════════
run-summarizer:
	@echo ""
	@echo "$(BLUE)Running Session Summarizer...$(RESET)"
	@echo "$(YELLOW)Tip: Use --session SESSION_ID to summarize a specific session$(RESET)"
	@echo "$(YELLOW)     Use --list to see all available sessions$(RESET)"
	@echo ""
	@cd $(SUMM_DIR) && $(PYTHON) session_summarizer.py --list

# ══════════════════════════════════════════════════════════════
# PHASE 2 — TASK HISTORY DASHBOARD
# ══════════════════════════════════════════════════════════════
run-dashboard:
	@echo ""
	@echo "$(BLUE)Starting Task History Dashboard...$(RESET)"
	@echo "$(YELLOW)Opening at http://localhost:8501$(RESET)"
	@echo "$(YELLOW)Press Ctrl+C to stop$(RESET)"
	@echo ""
	@cd $(DASH_DIR) && streamlit run app.py

# ══════════════════════════════════════════════════════════════
# PHASE 3 — CONVERSATION BRANCHING CLI
# ══════════════════════════════════════════════════════════════
run-branching:
	@echo ""
	@echo "$(BLUE)Starting Conversation Branching — Interactive Mode...$(RESET)"
	@echo ""
	@cd $(BRANCH_DIR) && $(PYTHON) branch_session.py --interactive

# ══════════════════════════════════════════════════════════════
# PHASE 3 — CONVERSATION BRANCHING WEB UI
# ══════════════════════════════════════════════════════════════
run-branch-ui:
	@echo ""
	@echo "$(BLUE)Starting Conversation Branching Web UI...$(RESET)"
	@echo "$(YELLOW)Opening at http://localhost:8501$(RESET)"
	@echo "$(YELLOW)Press Ctrl+C to stop$(RESET)"
	@echo ""
	@cd $(BRANCH_DIR) && streamlit run branch_ui.py

# ══════════════════════════════════════════════════════════════
# PHASE 3 — BUILD AND RUN GOOSE FROM SOURCE
# (includes Session Tagging UI)
# ══════════════════════════════════════════════════════════════
run-goose:
	@echo ""
	@echo "$(BLUE)Building and running Goose from source...$(RESET)"
	@echo "$(YELLOW)This may take a few minutes on first build$(RESET)"
	@echo ""
	@source bin/hermit && just run-ui

# ══════════════════════════════════════════════════════════════
# CLEAN
# ══════════════════════════════════════════════════════════════
clean:
	@echo ""
	@echo "$(BLUE)Cleaning generated files...$(RESET)"
	@find $(COST_DIR)/reports -name "*.md" -delete 2>/dev/null && \
		echo "$(GREEN)  ✅ Cost reports cleaned$(RESET)" || true
	@find $(SUMM_DIR)/sample_output -name "*.md" -delete 2>/dev/null && \
		echo "$(GREEN)  ✅ Session summaries cleaned$(RESET)" || true
	@find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null && \
		echo "$(GREEN)  ✅ Python cache cleaned$(RESET)" || true
	@echo ""
	@echo "$(GREEN)Clean complete!$(RESET)"
	@echo ""
