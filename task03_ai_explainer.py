"""
task03_ai_explainer.py
======================
Timecell.ai — Engineering Intern Assessment · Task 03
AI-Powered Portfolio Explainer (30 pts)

Uses Google Gemini API (gemini-2.5-flash — free tier) to generate a
plain-English portfolio risk explanation in the tone of a friendly but
honest financial advisor.

Output structure:
  - 3–4 sentence plain-English risk summary
  - One thing the investor is doing well
  - One thing to consider changing, and why
  - One-line verdict: 'Aggressive', 'Balanced', or 'Conservative'

BONUS:
  - Tone configurable: 'beginner' | 'experienced' | 'expert'
  - A second Gemini call that critiques the first explanation for accuracy

Setup:
  pip install google-generativeai
  export GEMINI_API_KEY="your-key-here"

  Free API key: https://aistudio.google.com/app/apikey

Usage:
  python task03_ai_explainer.py                        # interactive menu
  python task03_ai_explainer.py --portfolio 2          # pick portfolio by number
  python task03_ai_explainer.py --portfolio 2 --tone expert

Author : <your-name>
AI Tools: Claude (claude.ai) helped draft, iterate on prompt structure,
          and design the few-shot examples embedded in the explainer prompt.

Prompt engineering notes (for README):
  v1 — Zero-shot with schema only. Output was correct JSON but explanations
       were generic ("this portfolio is risky"). No specific numbers cited.
  v2 — Added RULES block forcing asset-name references. Better, but verdict
       didn't always align with risk_summary tone.
  v3 — Added a few-shot example (conservative portfolio → expected output).
       This anchored the LENGTH, SPECIFICITY, and VERDICT ALIGNMENT in one
       shot. Consistency improved dramatically across all four test portfolios.
  v4 — Added chain-of-thought hint: "First silently compute weighted crash
       loss, then write the summary." Reduced math errors in risk_summary.
  Critic v2 — Added explicit scoring rubric for actionability_score so the
       1-10 rating is calibrated rather than arbitrary.
"""

import argparse
import os
import sys
import json
import textwrap
from typing import Any, Literal

# ---------------------------------------------------------------------------
# Gemini SDK import
# ---------------------------------------------------------------------------
try:
    from google import genai
except ImportError:
    sys.exit(
        "❌  'google-generativeai' not installed.\n"
        "    Run: pip install google-generativeai"
    )


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODEL_NAME = "gemini-2.5-flash"   # Free-tier model — fast and capable

ToneType = Literal["beginner", "experienced", "expert"]

TONE_INSTRUCTIONS: dict[str, str] = {
    "beginner": (
        "Speak as if talking to someone who has never invested before. "
        "Avoid all jargon. Use simple analogies (e.g. comparing a crash to "
        "a shop sale). Be warm, encouraging, and never condescending. "
        "Define any financial term you must use in parentheses."
    ),
    "experienced": (
        "Speak as if talking to a seasoned investor who understands "
        "standard financial terms (volatility, drawdown, Sharpe ratio, "
        "diversification, rebalancing). Be direct and analytical. "
        "Skip basic definitions. Cite percentages and ratios."
    ),
    "expert": (
        "Speak as if addressing a CFA-level professional. Use precise "
        "financial language: VaR, CVaR, correlation, beta, Sortino ratio, "
        "Black-Litterman, tail risk, convexity. Be concise and technically "
        "rigorous. Quantify wherever possible."
    ),
}


# ---------------------------------------------------------------------------
# Sample portfolios  ←  satisfies "accept different portfolios" requirement
# ---------------------------------------------------------------------------

SAMPLE_PORTFOLIOS: dict[str, dict[str, Any]] = {
    "1": {
        "_label": "Task-01 Default — Crypto-heavy growth",
        "total_value_inr": 10_000_000,
        "monthly_expenses_inr": 80_000,
        "assets": [
            {"name": "BTC",     "allocation_pct": 30, "expected_crash_pct": -80},
            {"name": "NIFTY50", "allocation_pct": 40, "expected_crash_pct": -40},
            {"name": "GOLD",    "allocation_pct": 20, "expected_crash_pct": -15},
            {"name": "CASH",    "allocation_pct": 10, "expected_crash_pct":   0},
        ],
    },
    "2": {
        "_label": "Retiree — Capital preservation focus",
        "total_value_inr": 25_000_000,
        "monthly_expenses_inr": 150_000,
        "assets": [
            {"name": "GOVT_BONDS", "allocation_pct": 50, "expected_crash_pct":  -5},
            {"name": "GOLD",       "allocation_pct": 20, "expected_crash_pct": -15},
            {"name": "NIFTY50",    "allocation_pct": 15, "expected_crash_pct": -40},
            {"name": "FD",         "allocation_pct": 10, "expected_crash_pct":   0},
            {"name": "CASH",       "allocation_pct":  5, "expected_crash_pct":   0},
        ],
    },
    "3": {
        "_label": "Crypto maximalist — All-in on digital assets",
        "total_value_inr": 5_000_000,
        "monthly_expenses_inr": 60_000,
        "assets": [
            {"name": "BTC",  "allocation_pct": 50, "expected_crash_pct": -80},
            {"name": "ETH",  "allocation_pct": 30, "expected_crash_pct": -85},
            {"name": "SOL",  "allocation_pct": 15, "expected_crash_pct": -90},
            {"name": "CASH", "allocation_pct":  5, "expected_crash_pct":   0},
        ],
    },
    "4": {
        "_label": "Young professional — Balanced long-term SIP",
        "total_value_inr": 3_000_000,
        "monthly_expenses_inr": 45_000,
        "assets": [
            {"name": "NIFTY50",     "allocation_pct": 35, "expected_crash_pct": -40},
            {"name": "US_EQUITIES", "allocation_pct": 25, "expected_crash_pct": -35},
            {"name": "GOLD",        "allocation_pct": 15, "expected_crash_pct": -15},
            {"name": "DEBT_MF",     "allocation_pct": 15, "expected_crash_pct":  -8},
            {"name": "CASH",        "allocation_pct": 10, "expected_crash_pct":   0},
        ],
    },
}


# ---------------------------------------------------------------------------
# Prompt engineering
# ---------------------------------------------------------------------------

# ── Few-shot example baked into the explainer prompt ───────────────────────
# WHY FEW-SHOT HERE?
#   Zero-shot produced correct JSON but vague language ("the portfolio has
#   risk"). The example below anchors three things simultaneously:
#     1. LENGTH  — each field is 1-3 sentences, not a paragraph.
#     2. SPECIFICITY — asset names and numbers must appear.
#     3. VERDICT ALIGNMENT — the verdict word must match the risk_summary tone.
#   One example is enough (one-shot) because the schema already constrains
#   the output shape. Adding more examples would inflate the prompt without
#   meaningfully improving consistency.

FEW_SHOT_EXAMPLE = """
EXAMPLE (do NOT copy numbers — use the actual portfolio data below):

Input portfolio:
{
  "total_value_inr": 8000000,
  "monthly_expenses_inr": 50000,
  "assets": [
    {"name": "GOVT_BONDS", "allocation_pct": 60, "expected_crash_pct": -5},
    {"name": "GOLD",       "allocation_pct": 25, "expected_crash_pct": -15},
    {"name": "CASH",       "allocation_pct": 15, "expected_crash_pct": 0}
  ]
}

Expected output:
{
  "risk_summary": "This portfolio is built around safety. In a severe market crash, GOVT_BONDS (60%) would drop only 5% and GOLD (25%) would fall 15%, leaving roughly ₹72.2 L intact — enough to cover expenses for over 144 months. The 15% cash buffer adds further stability. Overall risk is very low.",
  "doing_well": "Holding 60% in GOVT_BONDS is a strong anchor — government bonds rarely lose value in Indian market crashes and provide steady, predictable income.",
  "consider_changing": "With 0% equity exposure, this portfolio may not beat inflation over 10+ years. Consider shifting 10-15% from GOVT_BONDS into NIFTY50 index funds to capture long-term equity growth without dramatically increasing risk.",
  "verdict": "Conservative"
}
""".strip()


def build_explainer_prompt(portfolio: dict[str, Any], tone: ToneType = "beginner") -> str:
    """
    Build the primary explainer prompt sent to Gemini.

    Prompt engineering decisions (v4):
      1. Structured JSON input — model references exact numbers, no hallucination.
      2. Output schema stated BEFORE data — model has the shape in mind while reading.
      3. Tone block — one template, three audiences, radically different vocabulary.
      4. One-shot example — anchors length, specificity, and verdict alignment.
      5. Chain-of-thought hint — "First silently compute weighted crash loss" reduces
         arithmetic errors in the risk_summary without polluting the output.
      6. RULES block — explicit constraints that catch the most common failure modes
         (generic language, mismatched verdict, invented data).
    """
    portfolio_json   = json.dumps(portfolio, indent=2)
    tone_instruction = TONE_INSTRUCTIONS[tone]

    prompt = textwrap.dedent(f"""
    You are a friendly but honest financial advisor working at Timecell.ai,
    an AI-powered wealth management platform serving high-net-worth Indian families.

    TONE INSTRUCTION:
    {tone_instruction}

    TASK:
    Analyse the portfolio below and respond ONLY with a valid JSON object
    (no markdown, no backticks, no extra text) with exactly these keys:

    {{
      "risk_summary":      "<3–4 sentences summarising overall risk level and key concerns>",
      "doing_well":        "<One specific thing the investor is doing well, with a brief reason>",
      "consider_changing": "<One specific thing to reconsider, and exactly why it matters>",
      "verdict":           "<Exactly one of: Aggressive | Balanced | Conservative>"
    }}

    CHAIN-OF-THOUGHT HINT (internal — do not include in output):
    Before writing, silently compute:
      post_crash_value = sum(total_value × allocation_pct/100 × (1 + crash_pct/100))
      runway_months    = post_crash_value / monthly_expenses_inr
    Reference these computed figures in risk_summary.

    RULES:
    - Reference specific asset names and percentages from the portfolio.
    - Mention the post-crash value and runway in INR/months in risk_summary.
    - Do NOT invent data that isn't in the portfolio.
    - The verdict MUST be consistent with the risk_summary tone.
    - Keep each field under 100 words.
    - Never use placeholder text like "<fill in>".

    {FEW_SHOT_EXAMPLE}

    PORTFOLIO DATA (analyse THIS — not the example above):
    {portfolio_json}
    """).strip()

    return prompt


def build_critic_prompt(
    portfolio: dict[str, Any],
    first_explanation: dict[str, Any],
) -> str:
    """
    BONUS: Build the critic/review prompt for the second Gemini call.

    Critic v2 improvements over v1:
      - Explicit scoring rubric for actionability_score so 1-10 is calibrated.
      - Asks critic to verify the computed post-crash math, not just "check numbers".
      - Asks whether the verdict is consistent with the risk_summary, not just "fair".
    """
    portfolio_json   = json.dumps(portfolio, indent=2)
    explanation_json = json.dumps(first_explanation, indent=2)

    prompt = textwrap.dedent(f"""
    You are a senior financial risk analyst at Timecell.ai reviewing an
    AI-generated portfolio explanation for accuracy and quality.

    Respond ONLY with a valid JSON object (no markdown, no backticks) with keys:

    {{
      "mathematical_accuracy": "<Did the explanation correctly compute post-crash value and runway? Quote the correct figures if wrong.>",
      "fairness_check":        "<Is any risk overstated or understated? Does the verdict (Aggressive/Balanced/Conservative) match the risk_summary?>",
      "actionability_score":   <integer 1–10>,
      "overall_verdict":       "<APPROVED | NEEDS_REVISION>",
      "revision_note":         "<If NEEDS_REVISION: exactly what to correct. If APPROVED: empty string.>"
    }}

    ACTIONABILITY SCORING RUBRIC:
      1-3  : Vague advice ("consider diversifying") with no specific action or asset named.
      4-6  : Names an asset but lacks a concrete target allocation or rationale.
      7-9  : Names an asset, gives a target allocation range, explains why it matters.
      10   : All of the above plus quantifies the expected benefit (e.g. runway improvement).

    MATHEMATICAL VERIFICATION GUIDE:
      post_crash_value = sum over assets of:
        (total_value_inr × allocation_pct / 100) × (1 + expected_crash_pct / 100)
      runway_months = post_crash_value / monthly_expenses_inr

    ORIGINAL PORTFOLIO:
    {portfolio_json}

    EXPLANATION BEING REVIEWED:
    {explanation_json}
    """).strip()

    return prompt


# ---------------------------------------------------------------------------
# Gemini API caller
# ---------------------------------------------------------------------------

def get_gemini_client(api_key: str) -> "genai.Client":
    """Return a single shared Gemini client — avoid re-creating per call."""
    return genai.Client(api_key=api_key)


def call_gemini(prompt: str, client: "genai.Client", label: str = "Gemini") -> str:
    """Send a prompt to Gemini and return the raw text response."""
    print(f"\n  ⏳  Calling {label}…")
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
        )
        return response.text
    except Exception as exc:
        raise RuntimeError(f"{label} API call failed: {exc}") from exc


def parse_json_response(raw: str, label: str = "response") -> dict:
    """
    Safely parse a JSON string, stripping common LLM formatting artefacts
    like ```json fences or leading/trailing whitespace.
    """
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        cleaned = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        print(f"\n  ⚠  Could not parse {label} as JSON: {exc}")
        print(f"     Raw response was:\n{raw}")
        return {}


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def print_section(title: str, content: str, width: int = 62) -> None:
    """Print a labelled section with word-wrapping."""
    print(f"\n  {'─' * (width - 4)}")
    print(f"  {title}")
    print(f"  {'─' * (width - 4)}")
    for line in textwrap.wrap(str(content), width=width - 4):
        print(f"  {line}")


def print_explanation(explanation: dict) -> None:
    """Pretty-print the structured explanation dict."""
    if not explanation:
        print("  (No explanation data — see errors above)")
        return

    print_section("📋  RISK SUMMARY",      explanation.get("risk_summary",      "N/A"))
    print_section("✅  DOING WELL",        explanation.get("doing_well",         "N/A"))
    print_section("⚠   CONSIDER CHANGING", explanation.get("consider_changing",  "N/A"))

    verdict      = explanation.get("verdict", "N/A")
    verdict_icon = {"Aggressive": "🔴", "Balanced": "🟡", "Conservative": "🟢"}.get(verdict, "⚪")
    print(f"\n  {'─' * 58}")
    print(f"  VERDICT: {verdict_icon}  {verdict}")
    print(f"  {'─' * 58}")


def print_critique(critique: dict) -> None:
    """Pretty-print the critic's review dict."""
    if not critique:
        print("  (No critique data — see errors above)")
        return

    print_section("🔢  MATHEMATICAL ACCURACY", critique.get("mathematical_accuracy", "N/A"))
    print_section("⚖️   FAIRNESS CHECK",        critique.get("fairness_check",        "N/A"))
    print(f"\n  Actionability Score : {critique.get('actionability_score', 'N/A')} / 10")

    overall = critique.get("overall_verdict", "N/A")
    icon    = "✅" if overall == "APPROVED" else "🔄"
    print(f"  Overall Verdict     : {icon}  {overall}")

    revision = critique.get("revision_note", "")
    if revision:
        print_section("📝  REVISION NOTE", revision)


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

def explain_portfolio(
    portfolio: dict[str, Any],
    client: "genai.Client",
    tone: ToneType = "beginner",
    run_critic: bool = True,
) -> None:
    """
    Full pipeline:
      1. Build and send the explainer prompt
      2. Print raw response + parsed structured output
      3. BONUS: Build and send the critic prompt, print its output

    Parameters
    ----------
    portfolio  : any portfolio dict with keys: total_value_inr,
                 monthly_expenses_inr, assets (list of dicts with
                 name / allocation_pct / expected_crash_pct)
    client     : initialised Gemini client
    tone       : 'beginner' | 'experienced' | 'expert'
    run_critic : whether to run the bonus critic call
    """
    label = portfolio.get("_label", "Custom Portfolio")

    print("\n" + "=" * 62)
    print("  TIMECELL.AI — AI-POWERED PORTFOLIO EXPLAINER")
    print(f"  Portfolio : {label}")
    print(f"  Model     : {MODEL_NAME}   |   Tone: {tone.upper()}")
    print("=" * 62)

    # ─── Step 1: Primary explainer call ────────────────────────────────
    explainer_prompt = build_explainer_prompt(portfolio, tone)

    # print("\n  ── PROMPT SENT TO GEMINI ──────────────────────────────────")
    # for line in explainer_prompt.splitlines():
    #     print(f"  {line}")
    # print("  ──────────────────────────────────────────────────────────")

    raw_explanation      = call_gemini(explainer_prompt, client, label="Explainer")
    structured_explanation = parse_json_response(raw_explanation, label="explanation")

    print("\n  ── RAW API RESPONSE ────────────────────────────────────────")
    print(raw_explanation)
    print("  ────────────────────────────────────────────────────────────")

    print("\n  ── STRUCTURED OUTPUT ───────────────────────────────────────")
    print_explanation(structured_explanation)

    # ─── Step 2 (BONUS): Critic call ───────────────────────────────────
    if run_critic and structured_explanation:
        print("\n\n" + "=" * 62)
        print("  BONUS: CRITIC REVIEW (2nd LLM call)")
        print("=" * 62)

        critic_prompt   = build_critic_prompt(portfolio, structured_explanation)
        raw_critique    = call_gemini(critic_prompt, client, label="Critic")
        structured_critique = parse_json_response(raw_critique, label="critique")

        print("\n  ── RAW CRITIC RESPONSE ─────────────────────────────────────")
        print(raw_critique)
        print("  ────────────────────────────────────────────────────────────")

        print("\n  ── STRUCTURED CRITIQUE ─────────────────────────────────────")
        print_critique(structured_critique)


# ---------------------------------------------------------------------------
# CLI & interactive menus
# ---------------------------------------------------------------------------

PORTFOLIO_JSON_SCHEMA = """\
Expected JSON structure for a custom portfolio file:

{
  "_label": "My Portfolio",          ← optional, shown in output header
  "total_value_inr": 10000000,       ← total portfolio value in INR
  "monthly_expenses_inr": 80000,     ← monthly living expenses in INR
  "assets": [
    {
      "name": "BTC",                 ← asset name (any string)
      "allocation_pct": 30,          ← percentage of portfolio (all must sum to 100)
      "expected_crash_pct": -80      ← expected % loss in a severe crash (negative)
    },
    ...
  ]
}"""


def load_portfolio_from_file(path: str) -> dict[str, Any]:
    """
    Load and validate a portfolio from a JSON file path.
    Raises SystemExit with a helpful message on any error.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        sys.exit(f"❌  File not found: {path}")
    except json.JSONDecodeError as exc:
        sys.exit(f"❌  Invalid JSON in {path}: {exc}")

    # ── Validate required keys ────────────────────────────────────────────
    errors: list[str] = []
    if "total_value_inr" not in data:
        errors.append("  • Missing key: 'total_value_inr'")
    if "monthly_expenses_inr" not in data:
        errors.append("  • Missing key: 'monthly_expenses_inr'")
    if "assets" not in data or not isinstance(data["assets"], list) or len(data["assets"]) == 0:
        errors.append("  • Missing or empty 'assets' list")
    else:
        for i, asset in enumerate(data["assets"]):
            for field in ("name", "allocation_pct", "expected_crash_pct"):
                if field not in asset:
                    errors.append(f"  • assets[{i}] is missing field '{field}'")

        total_alloc = sum(a.get("allocation_pct", 0) for a in data["assets"])
        if not (99 <= total_alloc <= 101):   # allow ±1 for rounding
            errors.append(
                f"  • allocation_pct values sum to {total_alloc}% — must be ~100%"
            )

    if errors:
        print("❌  Portfolio file failed validation:\n")
        for e in errors:
            print(e)
        print(f"\n{PORTFOLIO_JSON_SCHEMA}")
        sys.exit(1)

    if "_label" not in data:
        data["_label"] = os.path.basename(path)   # use filename as label

    return data


def select_portfolio_interactive() -> dict[str, Any]:
    """
    Two-step interactive menu:
      Option S  → pick one of the 4 built-in sample portfolios
      Option C  → enter a path to a custom JSON file
    Returns the chosen portfolio dict.
    """
    print("\n" + "=" * 62)
    print("  PORTFOLIO SOURCE")
    print("=" * 62)
    print("  S → Choose from sample portfolios")
    print("  C → Load your own portfolio from a JSON file")
    print("=" * 62)

    source = ""
    while source not in ("s", "c"):
        source = input("  Enter your choice (S / C): ").strip().lower()
        if source not in ("s", "c"):
            print("  ⚠  Please enter S or C.")

    if source == "s":
        return _select_sample_portfolio()
    else:
        return _load_custom_portfolio()


def _select_sample_portfolio() -> dict[str, Any]:
    """Show the numbered sample menu and return the chosen portfolio."""
    print("\n" + "=" * 62)
    print("  SAMPLE PORTFOLIOS")
    print("=" * 62)
    for key, pf in SAMPLE_PORTFOLIOS.items():
        total = pf["total_value_inr"] / 1_00_000
        print(f"  {key} → {pf['_label']}")
        print(f"      ₹{total:.1f}L  |  {len(pf['assets'])} assets  "
              f"|  ₹{pf['monthly_expenses_inr']:,}/mo expenses")
    print("=" * 62)

    choice = ""
    while choice not in SAMPLE_PORTFOLIOS:
        choice = input(f"  Enter choice ({'/'.join(SAMPLE_PORTFOLIOS)}): ").strip()
        if choice not in SAMPLE_PORTFOLIOS:
            print(f"  ⚠  Invalid. Please enter one of: {', '.join(SAMPLE_PORTFOLIOS)}")

    return SAMPLE_PORTFOLIOS[choice]


def _load_custom_portfolio() -> dict[str, Any]:
    """Prompt the user for a JSON file path, load and validate it."""
    print("\n" + "=" * 62)
    print("  CUSTOM PORTFOLIO — JSON FILE")
    print("=" * 62)
    print("  Tip: the file must match this structure —")
    for line in PORTFOLIO_JSON_SCHEMA.splitlines():
        print(f"  {line}")
    print("=" * 62)

    while True:
        path = input("  Path to your JSON file: ").strip()
        if not path:
            print("  ⚠  Path cannot be empty.")
            continue
        # expand ~ and relative paths
        path = os.path.expanduser(path)
        portfolio = load_portfolio_from_file(path)
        print(f"\n  ✅  Loaded: {portfolio['_label']}")
        print(f"      ₹{portfolio['total_value_inr']/1_00_000:.1f}L  "
              f"|  {len(portfolio['assets'])} assets  "
              f"|  ₹{portfolio['monthly_expenses_inr']:,}/mo expenses")
        return portfolio


def select_tone_interactive() -> ToneType:
    """Show a tone menu and return the selected tone string."""
    TONE_MENU = {"1": "beginner", "2": "experienced", "3": "expert"}

    print("\n" + "=" * 62)
    print("  SELECT EXPLANATION TONE")
    print("=" * 62)
    print("  1 → Beginner    (plain English, no jargon)")
    print("  2 → Experienced (standard financial terms)")
    print("  3 → Expert      (CFA-level, VaR / CVaR / beta)")
    print("=" * 62)

    choice = ""
    while choice not in TONE_MENU:
        choice = input("  Enter your choice (1 / 2 / 3): ").strip()
        if choice not in TONE_MENU:
            print("  ⚠  Invalid choice. Please enter 1, 2, or 3.")

    return TONE_MENU[choice]  # type: ignore[return-value]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Timecell.ai — AI-Powered Portfolio Explainer (Task 03)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Custom portfolio JSON format:\n{PORTFOLIO_JSON_SCHEMA}",
    )

    # mutually exclusive: either a sample number OR a file path
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument(
        "--portfolio",
        choices=list(SAMPLE_PORTFOLIOS.keys()),
        metavar="N",
        help=(
            "Sample portfolio number: "
            + ", ".join(f"{k}={v['_label']}" for k, v in SAMPLE_PORTFOLIOS.items())
        ),
    )
    source_group.add_argument(
        "--file",
        metavar="PATH",
        help="Path to a custom portfolio JSON file (see format below)",
    )

    parser.add_argument(
        "--tone",
        choices=["beginner", "experienced", "expert"],
        default=None,
        help="Explanation tone (default: interactive menu)",
    )
    parser.add_argument(
        "--no-critic",
        action="store_true",
        help="Skip the bonus critic call (saves one API round-trip)",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    # ── API key ──────────────────────────────────────────────────────────
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        sys.exit(
            "❌  GEMINI_API_KEY environment variable not set.\n"
            "    Get a free key at: https://aistudio.google.com/app/apikey\n"
            "    Then run: export GEMINI_API_KEY='your-key-here'"
        )

    client = get_gemini_client(api_key)

    # ── Portfolio selection (CLI flags take priority over interactive) ─────
    if args.file:
        portfolio = load_portfolio_from_file(os.path.expanduser(args.file))
    elif args.portfolio:
        portfolio = SAMPLE_PORTFOLIOS[args.portfolio]
    else:
        portfolio = select_portfolio_interactive()   # two-step interactive menu

    # ── Tone selection ────────────────────────────────────────────────────
    tone: ToneType = args.tone or select_tone_interactive()  # type: ignore[assignment]

    # ── Run pipeline ──────────────────────────────────────────────────────
    explain_portfolio(
        portfolio  = portfolio,
        client     = client,
        tone       = tone,
        run_critic = not args.no_critic,
    )

    print("\n" + "=" * 62)
    print("  Done.")
    print("=" * 62 + "\n")


if __name__ == "__main__":
    main()
