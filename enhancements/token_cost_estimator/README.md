# Token Usage & Cost Estimator

A Python CLI tool that reads real token usage data from Goose's local SQLite database and generates a detailed cost breakdown per session and across providers.

## What it does
- Reads actual token data from Goose sessions database
- Calculates cost per session based on provider pricing
- Shows cumulative total across all sessions
- Compares what the same usage would cost on different providers
- Saves a timestamped Markdown report automatically

## How to Run

```bash
python3 cost_estimator.py
```

## Output
- Terminal report with per session breakdown
- Cost comparison across OpenAI, Anthropic, and Gemini
- Markdown report saved to reports/ folder

## Files
- `cost_estimator.py` - Main script
- `pricing.json` - Configurable pricing table per provider
- `requirements.txt` - Dependencies

## Requirements
No external dependencies — uses Python standard library only.

## Known Limitations
- Provider name mapping uses default fallback for unknown providers
- Date filtering planned for Phase 3
- Model selection via command line argument planned for Phase 3
