import argparse
import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.expanduser("~/.local/share/goose/sessions/sessions.db")
PRICING_PATH = os.path.join(os.path.dirname(__file__), "pricing.json")
DEFAULT_MODEL = "claude-haiku-4-5"
REPORT_DIR = os.path.join(os.path.dirname(__file__), "reports")

# Maps substrings of Goose's provider_name to a pricing key.
# Goose stores provider-level names like "tetrate", "anthropic", "openai" —
# not full model names — so we can't match pricing keys directly.
PROVIDER_FAMILY_MAP = {
    "anthropic": "claude-haiku-4-5",
    "claude":    "claude-haiku-4-5",
    "tetrate":   "claude-haiku-4-5",
    "openai":    "gpt-4o",
    "gpt":       "gpt-4o",
    "azure":     "gpt-4o",
    "google":    "gemini-2.0-flash",
    "gemini":    "gemini-2.0-flash",
    "vertex":    "gemini-2.0-flash",
}

def load_pricing():
    with open(PRICING_PATH, "r") as f:
        return json.load(f)

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_all_sessions():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, working_dir, provider_name, input_tokens, output_tokens, total_tokens, created_at FROM sessions ORDER BY created_at")
    sessions = cursor.fetchall()
    conn.close()
    return sessions

def resolve_model_key(provider, pricing, default_model):
    """Map a Goose provider name to a pricing key."""
    provider_lower = (provider or "").lower()
    # Check if the provider string itself contains a full pricing key (e.g. "claude-haiku-4-5")
    for k in pricing:
        if k != "default" and k.lower() in provider_lower:
            return k
    # Fall back to family-level mapping (e.g. "anthropic" → claude-haiku-4-5)
    for family, model_key in PROVIDER_FAMILY_MAP.items():
        if family in provider_lower and model_key in pricing:
            return model_key
    return default_model

def calculate_cost(input_tokens, output_tokens, pricing, model):
    rates = pricing.get(model, pricing["default"])
    input_cost = (input_tokens / 1000) * rates["input_per_1k"]
    output_cost = (output_tokens / 1000) * rates["output_per_1k"]
    return input_cost, output_cost, input_cost + output_cost

def print_terminal_report(pricing, default_model):
    sessions = get_all_sessions()
    all_models = [k for k in pricing.keys() if k != "default"]

    if not sessions:
        print("No sessions found in the database.")
        return

    print("\n" + "="*65)
    print("      GOOSE TOKEN USAGE & COST ESTIMATOR REPORT")
    print("="*65)
    print(f"  Generated     : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Sessions      : {len(sessions)}")
    print(f"  Default Model : {default_model}")
    print("  Token Data    : Read directly from Goose sessions database")
    print("="*65)

    print("\n PER SESSION BREAKDOWN\n")

    total_input = 0
    total_output = 0
    total_cost_all = 0

    for s in sessions:
        input_tok = s["input_tokens"] or 0
        output_tok = s["output_tokens"] or 0
        provider = s["provider_name"] or default_model
        model_key = resolve_model_key(provider, pricing, default_model)

        input_cost, output_cost, total_cost = calculate_cost(input_tok, output_tok, pricing, model_key)

        print(f"  Session  : {s['id']}")
        print(f"  Name     : {s['name'] or 'Unnamed'}")
        print(f"  Provider : {provider}")
        print(f"  Priced As: {model_key}")
        print(f"  Dir      : {s['working_dir']}")
        print(f"  Input    : {input_tok:,} tokens  (${input_cost:.6f})")
        print(f"  Output   : {output_tok:,} tokens  (${output_cost:.6f})")
        print(f"  Total    : {input_tok + output_tok:,} tokens  (${total_cost:.6f})")
        print("-"*65)

        total_input += input_tok
        total_output += output_tok
        total_cost_all += total_cost

    print(f"\n{'='*65}")
    print("  CUMULATIVE TOTAL ACROSS ALL SESSIONS")
    print(f"{'='*65}")
    print(f"  Total Input Tokens  : {total_input:,}")
    print(f"  Total Output Tokens : {total_output:,}")
    print(f"  Total Tokens        : {total_input + total_output:,}")
    print(f"  Estimated Cost      : ${total_cost_all:.6f}")
    print(f"{'='*65}")

    print(f"\n{'='*65}")
    print("  COST COMPARISON ACROSS PROVIDERS")
    print(f"{'='*65}")
    print(f"  {'Provider':<25} {'Input Cost':>12} {'Output Cost':>12} {'Total Cost':>12}")
    print(f"  {'-'*61}")

    for model in all_models:
        ic, oc, tc = calculate_cost(total_input, total_output, pricing, model)
        marker = " <-- active" if model == default_model else ""
        print(f"  {model:<25} ${ic:>10.6f} ${oc:>10.6f} ${tc:>10.6f}{marker}")

    print(f"{'='*65}\n")

def save_markdown_report(pricing, default_model):
    sessions = get_all_sessions()
    all_models = [k for k in pricing.keys() if k != "default"]
    os.makedirs(REPORT_DIR, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(REPORT_DIR, f"cost_report_{timestamp}.md")

    total_input = sum(s["input_tokens"] or 0 for s in sessions)
    total_output = sum(s["output_tokens"] or 0 for s in sessions)
    _, _, total_cost = calculate_cost(total_input, total_output, pricing, default_model)

    lines = []
    lines.append("# Goose Token Usage & Cost Estimator Report\n")
    lines.append(f"- **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- **Active Model:** {default_model}")
    lines.append(f"- **Total Sessions:** {len(sessions)}")
    lines.append("- **Token Data:** Read directly from Goose sessions database\n")
    lines.append("---\n")
    lines.append("## Per Session Breakdown\n")
    lines.append("| Session ID | Name | Provider | Priced As | Input Tokens | Output Tokens | Total Tokens | Est. Cost |")
    lines.append("|------------|------|----------|-----------|-------------|--------------|-------------|-----------|")

    for s in sessions:
        input_tok = s["input_tokens"] or 0
        output_tok = s["output_tokens"] or 0
        provider = s["provider_name"] or default_model
        model_key = resolve_model_key(provider, pricing, default_model)
        _, _, cost = calculate_cost(input_tok, output_tok, pricing, model_key)
        lines.append(f"| {s['id']} | {s['name'] or 'Unnamed'} | {provider} | {model_key} | {input_tok:,} | {output_tok:,} | {input_tok + output_tok:,} | ${cost:.6f} |")

    lines.append("\n---\n")
    lines.append("## Cumulative Total\n")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total Input Tokens | {total_input:,} |")
    lines.append(f"| Total Output Tokens | {total_output:,} |")
    lines.append(f"| Total Tokens | {total_input + total_output:,} |")
    lines.append(f"| Estimated Total Cost | ${total_cost:.6f} |")
    lines.append("\n---\n")
    lines.append("## Cost Comparison Across Providers\n")
    lines.append("| Provider | Input Cost | Output Cost | Total Cost | Note |")
    lines.append("|----------|-----------|------------|-----------|------|")

    for model in all_models:
        ic, oc, tc = calculate_cost(total_input, total_output, pricing, model)
        note = "Active" if model == default_model else ""
        lines.append(f"| {model} | ${ic:.6f} | ${oc:.6f} | ${tc:.6f} | {note} |")

    lines.append("\n---\n")
    lines.append("_Report generated by Goose Token Cost Estimator - SENG 691 Phase 2 Enhancement_\n")

    with open(filename, "w") as f:
        f.write("\n".join(lines))

    print(f"  Markdown report saved to: {filename}\n")
    return filename

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Goose Token Usage & Cost Estimator")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Pricing model to use for the cumulative cost total (default: {DEFAULT_MODEL}). "
             "Must match a key in pricing.json.",
    )
    args = parser.parse_args()

    pricing = load_pricing()

    if args.model not in pricing:
        valid = [k for k in pricing if k != "default"]
        print(f"Warning: model '{args.model}' not found in pricing.json. "
              f"Valid options: {', '.join(valid)}. Using default '{DEFAULT_MODEL}'.")
        args.model = DEFAULT_MODEL

    print_terminal_report(pricing, args.model)
    save_markdown_report(pricing, args.model)
