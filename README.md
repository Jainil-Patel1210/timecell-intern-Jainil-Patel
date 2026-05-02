# timecell-intern-Jainil-Patel

**Timecell.ai · Summer Internship 2025 · Technical Assessment**  
4 tasks · Python 3.10+ · Gemini 2.5 Flash · Terminal-native

---

## Setup

```bash
pip install yfinance requests google-genai
export GEMINI_API_KEY="your-key-here"   
```
---

## Task 01 — Portfolio Risk Calculator

```bash
python task01_portfolio_risk.py
```

### What it does
Takes a portfolio dict and computes:

| Metric | Description |
|--------|-------------|
| `post_crash_value` | Portfolio value after a worst-case crash |
| `runway_months` | How many months of expenses remain post-crash |
| `ruin_test` | PASS if runway > 12 months, FAIL otherwise |
| `largest_risk_asset` | Asset with highest allocation × crash magnitude |
| `concentration_warning` | True if any single asset exceeds 40% |

### Bonus features
- **Side-by-side comparison table** — Full crash (100%) vs Moderate crash (50%) shown as a two-column table, not separate blocks
- **CLI bar chart** — Unicode block-element allocation chart, zero external libraries
- **Edge case demos** — 100% cash portfolio and zero monthly expenses

### Approach
Risk score per asset = `allocation % × |crash %|`. This is a simple but intuitive proxy for expected dollar loss — the asset that would hurt the most in a crash. Survival factor = `1 + (crash_pct / 100)`, applied per asset then summed.

---

## Task 02 — Live Market Data Fetch

```bash
python task02_market_data.py
```

### What it does
Fetches live prices for three assets and prints a formatted table:

| Asset | Source | Notes |
|-------|--------|-------|
| BTC | CoinGecko (free, no key) | Price in USD + INR equivalent |
| NIFTY50 | yfinance `^NSEI` | INR |
| GOLD | yfinance `GC=F` | USD/troy oz → converted to INR/gram |

USD/INR rate is fetched once at startup via ExchangeRate-API (free tier) and reused. Falls back to ₹83.5 if that fetch fails.

### Error handling
Each asset has its own independent fetcher wrapped in `try/except`. One failure logs an error and continues — the table renders with whatever data is available. A summary at the end tells you how many fetches succeeded.

---

## Task 03 — AI-Powered Portfolio Explainer

```bash
python task03_ai_explainer.py
```

### What it does
Uses **Gemini 2.5 Flash** to generate a plain-English portfolio risk explanation. On startup you pick:
1. A portfolio — 4 preloaded samples or enter a custom one interactively
2. A tone — Beginner / Experienced / Expert

### Output
- **Risk Summary** — 3-4 sentence plain-English overview
- **Doing Well** — one specific strength with reasoning
- **Consider Changing** — one specific recommendation and why
- **Verdict** — Aggressive / Balanced / Conservative

### Bonus
A second Gemini call acts as a critic — it reviews the first explanation for mathematical accuracy, fairness, and actionability, and returns APPROVED or NEEDS_REVISION with a note.

### Prompt engineering
**Iteration 1:** Asked the model to "explain this portfolio." Got unstructured prose.  
**Iteration 2:** Added JSON output requirement. Model added preamble text that broke `json.loads()`.  
**Iteration 3 (final):** Put the JSON schema *before* the portfolio data — the model has the output format in mind while reading the input. Added a `parse_json_response()` helper that strips markdown fences before parsing.

The tone system injects a completely different instruction block per audience — beginner gets analogies and zero jargon, expert gets VaR / CVaR / tail risk language.

---

## Task 04 — The Open Problem

```bash
# Normal live mode
python task04_portfolio_monitor.py

# Simulate a 10% price spike to test alerts without waiting for market moves
python task04_portfolio_monitor.py --test-alerts

# Custom settings
python task04_portfolio_monitor.py --refresh 10 --threshold 3.0
```

### What I built and why
Timecell runs in a terminal. Its clients are Indian HNI families whose primary communication channel is WhatsApp. The gap between "AI analysed my portfolio" and "my advisor told me what to do" is where value leaks.

This monitor closes that gap — it runs in the background, catches significant moves, and generates a WhatsApp-ready briefing that a wealth manager can copy-paste directly to a client.

### Features
- **Live dashboard** — refreshes every 30s, fetches real prices for BTC, NIFTY50, GOLD
- **Alert engine** — fires when any asset moves ≥5% since the last cycle
- **Smart briefing** — AI briefing only regenerates when alerts fire, not every cycle. A cached briefing is reused with its original timestamp so you always know if it's fresh. This avoids burning Gemini tokens every 30 seconds for a quiet market
- **`--test-alerts` flag** — fakes previous prices to be 10% lower so every asset triggers an alert on cycle 1. Built specifically for weekend/holiday testing when markets are closed and prices are frozen

### Why this has product potential
The alert-driven briefing model is strictly better than a scheduled one — it contacts the client only when something actually changed, which builds trust rather than noise.

---


## AI Tools Used

| Tool | How |
|------|-----|
| **Gemini 2.5 Flash** | Portfolio explanation, critic review, WhatsApp briefing (Tasks 03, 04) |
| **Claude (claude.ai)** | Code review, edge-case identification, prompt iteration advice |

---

## Hardest Part

Task 03 prompt engineering. Getting Gemini to return valid JSON on every call — without preamble text, without markdown fences, without omitted fields — required three full iterations of the prompt and a defensive parser. The key insight: putting the output schema before the portfolio data means the model has the format loaded into attention while it processes the input. Documented every iteration in this README as required.