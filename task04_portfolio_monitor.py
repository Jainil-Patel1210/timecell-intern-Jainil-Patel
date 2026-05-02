"""
task04_portfolio_monitor.py
============================
Timecell.ai — Engineering Intern Assessment · Task 04
The Open Problem (20 pts) — No specification. That is the point.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  WHAT I BUILT & WHY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Timecell runs inside Claude Code — a terminal. Its users are
high-net-worth Indian families who care about one thing above
all else: "Is my wealth safe right now?"

I built a *Portfolio Health Monitor* — a terminal-native tool that:

  1. Fetches live market prices for portfolio assets (yfinance + CoinGecko)
  2. Recomputes risk metrics in real-time using the Task 01 engine
  3. Detects when a live asset price has moved more than a configurable
     threshold (default: 5%) compared to the last check
  4. Generates a Gemini-powered "daily briefing" — a short, human-friendly
     paragraph that a wealth manager could paste into a WhatsApp message
     to their client
  5. Displays a live-updating terminal dashboard (pure Python, no curses)
     that refreshes every N seconds

Why this has product potential:
  - Timecell's core value prop is *intelligent alerts*, not just dashboards.
  - Indian HNI clients want to be told "your portfolio is in danger" before
    they check — not after.
  - The daily briefing feature bridges the gap between AI analysis and the
    WhatsApp-first communication style of Indian wealth managers.

Dependencies:
  pip install yfinance requests google-genai

Author : <your-name>
AI Tools: Claude (claude.ai) co-designed the alert threshold logic and
          helped draft the briefing prompt.
"""

import os
import sys
import time
import json
import textwrap
import logging
import argparse
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

# ---- Third-party imports with friendly error messages ----
try:
    import requests
except ImportError:
    sys.exit("❌  Run: pip install requests")

try:
    import yfinance as yf
except ImportError:
    sys.exit("❌  Run: pip install yfinance")

try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠  google-genai not installed. Run: pip install google-genai")

# ---- Reuse the risk engine from Task 01 ----
# In a real project this would be `from task01_portfolio_risk import compute_risk_metrics`
# Here we inline it so this file is self-contained.

logging.basicConfig(level=logging.WARNING, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))
COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"
FALLBACK_USD_INR = 83.5
TROY_OZ_TO_GRAMS = 31.1035


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Risk Engine (inlined from Task 01)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def compute_risk_metrics(portfolio: dict) -> dict:
    """Compute portfolio risk metrics. See Task 01 for full documentation."""
    total_value      = portfolio.get("total_value_inr", 0)
    monthly_expenses = portfolio.get("monthly_expenses_inr", 0)
    assets           = portfolio.get("assets", [])

    if total_value <= 0 or not assets:
        return {"post_crash_value": 0, "runway_months": 0,
                "ruin_test": "FAIL", "largest_risk_asset": None,
                "concentration_warning": False}

    post_crash_value   = 0.0
    largest_risk_score = -1.0
    largest_risk_asset = None
    concentration_warning = False

    for asset in assets:
        alloc_pct  = asset.get("allocation_pct", 0)
        crash_pct  = asset.get("expected_crash_pct", 0)
        asset_value = total_value * (alloc_pct / 100)
        post_crash_value += asset_value * (1 + crash_pct / 100)
        risk_score = alloc_pct * abs(crash_pct)
        if risk_score > largest_risk_score:
            largest_risk_score = risk_score
            largest_risk_asset = asset.get("name", "UNKNOWN")
        if alloc_pct > 40:
            concentration_warning = True

    runway_months = (post_crash_value / monthly_expenses) if monthly_expenses > 0 else float("inf")
    return {
        "post_crash_value":      round(post_crash_value, 2),
        "runway_months":         round(runway_months, 2),
        "ruin_test":             "PASS" if runway_months > 12 else "FAIL",
        "largest_risk_asset":    largest_risk_asset,
        "concentration_warning": concentration_warning,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Live Price Fetcher
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def fetch_usd_inr() -> float:
    """Fetch live USD/INR rate, fallback to constant on error."""
    try:
        r = requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=6)
        r.raise_for_status()
        return float(r.json()["rates"]["INR"])
    except Exception:
        return FALLBACK_USD_INR


def fetch_live_prices(asset_names: list[str], usd_inr: float) -> dict[str, Optional[float]]:
    """
    Fetch current prices for a list of asset names.

    Supported tickers (case-insensitive):
      BTC, ETH         — CoinGecko crypto
      NIFTY50, ^NSEI   — NSE index via yfinance
      GOLD, GC=F       — COMEX gold futures via yfinance, returns INR/g
      Any NSE symbol   — via yfinance (append .NS suffix automatically)

    Returns dict: {asset_name: price_float or None}
    """
    prices = {}
    # Crypto: batch request to CoinGecko
    crypto_map = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana"}

    for name in asset_names:
        upper = name.upper()
        price = None

        # ── Crypto ────────────────────────────────────────────────────
        if upper in crypto_map:
            try:
                r = requests.get(
                    COINGECKO_URL,
                    params={"ids": crypto_map[upper], "vs_currencies": "usd"},
                    timeout=8,
                )
                r.raise_for_status()
                price = r.json()[crypto_map[upper]]["usd"]
            except Exception as e:
                logger.warning(f"{name} price fetch failed: {e}")

        # ── NIFTY50 ───────────────────────────────────────────────────
        elif upper in ("NIFTY50", "NIFTY", "^NSEI"):
            try:
                price = yf.Ticker("^NSEI").fast_info.last_price
            except Exception as e:
                logger.warning(f"{name} price fetch failed: {e}")

        # ── GOLD ──────────────────────────────────────────────────────
        elif upper in ("GOLD", "GC=F"):
            try:
                price_oz = yf.Ticker("GC=F").fast_info.last_price
                price    = (price_oz * usd_inr) / TROY_OZ_TO_GRAMS   # INR/gram
            except Exception as e:
                logger.warning(f"{name} price fetch failed: {e}")

        # ── Cash / stable assets — no fetch needed ────────────────────
        # Cash has no market price to fetch. It is always worth exactly
        # what it is — 1 INR per 1 INR. Attempting a yfinance lookup
        # for "CASH" or similar names causes unnecessary 404 errors.
        elif upper in ("CASH", "CASH_INR", "LIQUID", "FD", "SAVINGS"):
            price = 1.0   # symbolic: 1 unit = 1 INR, always stable

        # ── Bonds / fixed-income — treat as stable (no live price) ────
        elif upper in ("GOVT_BONDS", "BONDS", "T_BILLS", "TBILLS", "PPF", "EPF"):
            price = 1.0   # stable, not exchange-traded

        # ── Generic NSE stock (append .NS if needed) ──────────────────
        else:
            ticker_sym = upper if upper.endswith(".NS") else f"{upper}.NS"
            try:
                price = yf.Ticker(ticker_sym).fast_info.last_price
            except Exception as e:
                logger.warning(f"{name} ({ticker_sym}) fetch failed: {e}")

        prices[name] = price

    return prices


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Alert Engine
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def detect_alerts(
    current_prices:  dict[str, Optional[float]],
    previous_prices: dict[str, Optional[float]],
    threshold_pct:   float = 5.0,
) -> list[dict]:
    """
    Compare current vs previous prices and return a list of alert dicts
    for assets that moved more than threshold_pct.

    Each alert dict:
      {asset, previous, current, change_pct, direction}
    """
    alerts = []
    for asset, curr in current_prices.items():
        prev = previous_prices.get(asset)
        if curr is None or prev is None or prev == 0:
            continue
        change_pct = ((curr - prev) / prev) * 100
        if abs(change_pct) >= threshold_pct:
            alerts.append({
                "asset":      asset,
                "previous":   prev,
                "current":    curr,
                "change_pct": change_pct,
                "direction":  "UP ▲" if change_pct > 0 else "DOWN ▼",
            })
    return alerts


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Gemini Daily Briefing
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_daily_briefing(
    portfolio:      dict,
    risk_metrics:   dict,
    live_prices:    dict,
    alerts:         list,
    api_key:        str,
) -> str:
    """
    BONUS: Use Gemini to generate a short daily briefing paragraph
    suitable for a WhatsApp message from a wealth manager to their client.

    Prompt engineering notes:
      - We give the model the pre-computed risk metrics (not raw portfolio)
        so it doesn't need to do arithmetic — reduces hallucination risk.
      - We explicitly set a word count ceiling (≤80 words) to keep it
        concise enough for a WhatsApp message.
      - We include live alerts so the model can mention market movements.
    """
    prompt = textwrap.dedent(f"""
    You are a wealth manager at Timecell.ai. Write a WhatsApp-ready
    daily briefing for your client — friendly, honest, ≤80 words.
    No markdown, no bullet points, just a short paragraph.

    CURRENT RISK STATUS:
    {json.dumps(risk_metrics, indent=2)}

    LIVE PRICE ALERTS (assets that moved ≥5% since last check):
    {json.dumps(alerts, indent=2) if alerts else "No significant price movements."}

    PORTFOLIO OVERVIEW:
    Total Value: ₹{portfolio['total_value_inr']:,}
    Monthly Expenses: ₹{portfolio['monthly_expenses_inr']:,}

    Start with "Good morning" or "Good evening" depending on common sense.
    End with a clear action item or reassurance.
    """).strip()

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        return f"(Briefing generation failed: {e})"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Terminal Dashboard
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def clear_screen() -> None:
    """Clear terminal — works on both Unix and Windows."""
    print("\033[2J\033[H", end="")


def format_inr(val: float) -> str:
    return f"₹{val:,.0f}"


def render_dashboard(
    portfolio:      dict,
    live_prices:    dict,
    risk_metrics:   dict,
    alerts:         list,
    briefing:       str,
    briefing_at:    str,      # human-readable timestamp of when briefing was generated
    refresh_sec:    int,
    cycle:          int,
    test_mode:      bool = False,
) -> None:
    """Render the full terminal dashboard in one pass."""
    clear_screen()
    now = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")
    w   = 62   # dashboard width

    # ── Header ─────────────────────────────────────────────────────────
    print("=" * w)
    print(f"  TIMECELL.AI  |  PORTFOLIO HEALTH MONITOR  |  Cycle #{cycle}")
    print(f"  {now}")
    print("=" * w)

    # ── Portfolio overview ──────────────────────────────────────────────
    print(f"\n  Total Value     : {format_inr(portfolio['total_value_inr'])}")
    print(f"  Monthly Expense : {format_inr(portfolio['monthly_expenses_inr'])}")

    # ── Live prices ─────────────────────────────────────────────────────
    print(f"\n  {'─' * (w - 4)}")
    print(f"  {'ASSET':<12} {'LIVE PRICE':>18}  {'STATUS'}")
    print(f"  {'─' * (w - 4)}")
    for asset_info in portfolio["assets"]:
        name    = asset_info["name"]
        price   = live_prices.get(name)
        alloc   = asset_info["allocation_pct"]
        bar_len = int(alloc / 2.5)          # scale to ~40 chars max
        bar     = "█" * bar_len

        # Assets like CASH/BONDS return price=1.0 (symbolic) — label as
        # STABLE so the dashboard doesn\'t show a confusing "1.00" price.
        STABLE_ASSETS = {"CASH", "CASH_INR", "LIQUID", "FD", "SAVINGS",
                         "GOVT_BONDS", "BONDS", "T_BILLS", "TBILLS", "PPF", "EPF"}

        if price is None:
            price_str = "   FETCH FAILED"
        elif name.upper() in STABLE_ASSETS:
            price_str = "{:>16}".format("STABLE (no price)")
        else:
            price_str = f"{price:>16,.2f}"

        status = f"{alloc:>4.0f}% {bar}"
        print(f"  {name:<12} {price_str}  {status}")

    # ── Risk metrics ─────────────────────────────────────────────────────
    print(f"\n  {'─' * (w - 4)}")
    print("  CRASH SCENARIO METRICS")
    print(f"  {'─' * (w - 4)}")
    ruin_icon = "✅ PASS" if risk_metrics["ruin_test"] == "PASS" else "🔴 FAIL"
    print(f"  Post-Crash Value  : {format_inr(risk_metrics['post_crash_value'])}")
    print(f"  Runway            : {risk_metrics['runway_months']:.1f} months")
    print(f"  Ruin Test         : {ruin_icon}")
    print(f"  Biggest Risk      : {risk_metrics['largest_risk_asset']}")
    conc = "⚠ YES — rebalance advised" if risk_metrics["concentration_warning"] else "✓ No"
    print(f"  Concentration     : {conc}")

    # ── Alerts ───────────────────────────────────────────────────────────
    print(f"\n  {'─' * (w - 4)}")
    print("  PRICE MOVEMENT ALERTS (≥5% since last cycle)")
    print(f"  {'─' * (w - 4)}")
    if alerts:
        for a in alerts:
            print(f"  🔔 {a['asset']} moved {a['change_pct']:+.1f}% ({a['direction']})")
            print(f"       {a['previous']:,.2f}  →  {a['current']:,.2f}")
    else:
        print("  ✓  No significant movements detected.")

    # ── Daily briefing ────────────────────────────────────────────────────
    if briefing:
        print(f"\n  {'─' * (w - 4)}")
        print(f"  AI BRIEFING (Gemini)  —  generated at {briefing_at}")
        print(f"  {'─' * (w - 4)}")
        for line in textwrap.wrap(briefing, width=w - 4):
            print(f"  {line}")

    # ── Footer ───────────────────────────────────────────────────────────
    print(f"\n  {'─' * (w - 4)}")
    if test_mode:
        print("  ⚠   TEST MODE — prices are simulated to trigger alert logic")
    print(f"  Auto-refreshing every {refresh_sec}s  |  Press Ctrl+C to exit")
    print("=" * w)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Main loop
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main() -> None:
    # ── CLI argument parsing ─────────────────────────────────────────────
    parser = argparse.ArgumentParser(description="Timecell Portfolio Health Monitor")
    parser.add_argument(
        "--test-alerts",
        action="store_true",
        help=(
            "Run in test mode: fakes the previous-cycle prices so every asset "
            "appears to have moved by more than the alert threshold. "
            "Use this to verify alert firing without waiting for a real market move."
        ),
    )
    parser.add_argument(
        "--refresh",
        type=int,
        default=30,
        help="Refresh interval in seconds (default: 30)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=5.0,
        help="Alert threshold in percent (default: 5.0)",
    )
    args = parser.parse_args()

    REFRESH_SECONDS = args.refresh
    ALERT_THRESHOLD = args.threshold
    TEST_MODE       = args.test_alerts
    GEMINI_API_KEY  = os.environ.get("GEMINI_API_KEY", "")

    # ---- Portfolio ----
    portfolio = {
        "total_value_inr":      10_000_000,
        "monthly_expenses_inr":     80_000,
        "assets": [
            {"name": "BTC",     "allocation_pct": 30, "expected_crash_pct": -80},
            {"name": "NIFTY50", "allocation_pct": 40, "expected_crash_pct": -40},
            {"name": "GOLD",    "allocation_pct": 20, "expected_crash_pct": -15},
            {"name": "CASH",    "allocation_pct": 10, "expected_crash_pct":   0},
        ],
    }
    asset_names = [a["name"] for a in portfolio["assets"]]

    # ---- State ----
    previous_prices: dict[str, Optional[float]] = {}
    briefing        = ""
    briefing_at     = "—"   # timestamp label shown in dashboard
    cycle           = 0

    if TEST_MODE:
        print("\n  ⚠  TEST MODE active — alert thresholds will be triggered artificially.")
        print("  Run normally (without --test-alerts) for live market monitoring.\n")
    else:
        print("\n  Starting Timecell Portfolio Health Monitor…")

    print("  (Press Ctrl+C to exit)\n")
    import time as _time
    _time.sleep(1)

    while True:
        cycle += 1
        usd_inr      = fetch_usd_inr()
        live_prices  = fetch_live_prices(asset_names, usd_inr)
        risk_metrics = compute_risk_metrics(portfolio)

        # ── TEST MODE: fake previous prices to force alerts ──────────────
        # We set each asset's "previous" price to 10% below current so
        # every asset triggers the alert threshold, letting you see the
        # full alert UI without waiting for a real market move.
        if TEST_MODE and cycle == 1:
            previous_prices = {
                name: price * 0.90   # simulate price was 10% lower last cycle
                for name, price in live_prices.items()
                if price is not None
            }

        alerts = detect_alerts(live_prices, previous_prices, ALERT_THRESHOLD)

        # ── Briefing: only regenerate when something actually changed ────
        # Logic:
        #   - First cycle: always generate (need an initial briefing)
        #   - Subsequent cycles: ONLY regenerate if new alerts fired
        #     (no alerts = nothing changed = reuse existing briefing)
        # This avoids burning Gemini tokens every 30s for a static market.
        should_generate_briefing = (
            GEMINI_AVAILABLE
            and GEMINI_API_KEY
            and (cycle == 1 or len(alerts) > 0)
        )

        if should_generate_briefing:
            briefing = generate_daily_briefing(
                portfolio    = portfolio,
                risk_metrics = risk_metrics,
                live_prices  = live_prices,
                alerts       = alerts,
                api_key      = GEMINI_API_KEY,
            )
            # Record the time this briefing was generated for display
            briefing_at = datetime.now(IST).strftime("%H:%M:%S IST")

        elif not GEMINI_AVAILABLE or not GEMINI_API_KEY:
            briefing    = "(Set GEMINI_API_KEY to enable AI briefings)"
            briefing_at = "—"

        # If no condition matched: briefing and briefing_at remain unchanged
        # from the previous cycle — user sees the cached briefing with its
        # original timestamp, making it clear it has not been regenerated.

        render_dashboard(
            portfolio    = portfolio,
            live_prices  = live_prices,
            risk_metrics = risk_metrics,
            alerts       = alerts,
            briefing     = briefing,
            briefing_at  = briefing_at,
            refresh_sec  = REFRESH_SECONDS,
            cycle        = cycle,
            test_mode    = TEST_MODE,
        )

        # Save current prices as baseline for next cycle's alert comparison
        previous_prices = {k: v for k, v in live_prices.items() if v is not None}

        try:
            import time as _t
            _t.sleep(REFRESH_SECONDS)
        except KeyboardInterrupt:
            print("\n\n  Monitor stopped. Goodbye.\n")
            sys.exit(0)


if __name__ == "__main__":
    main()