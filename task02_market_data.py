"""
task02_market_data.py
=====================
Timecell.ai — Engineering Intern Assessment · Task 02
Live Market Data Fetch (20 pts)

Fetches current prices for:
  1. BTC       — crypto    (via CoinGecko free API)
  2. NIFTY50   — index     (via yfinance)
  3. GOLD      — commodity (via yfinance — GC=F futures, price in USD, converted to INR/g)

Prints a formatted table to the terminal.
Handles errors gracefully — a failed fetch is logged and skipped.

Dependencies:
  pip install yfinance requests

Author : <your-name>
AI Tools: Claude (claude.ai) used to cross-check API endpoint details
"""

import logging
import sys
from datetime import datetime, timezone, timedelta
from typing import Optional

# Third-party — install with: pip install yfinance requests
try:
    import requests
except ImportError:
    sys.exit("❌  'requests' not installed. Run: pip install requests")

try:
    import yfinance as yf
except ImportError:
    sys.exit("❌  'yfinance' not installed. Run: pip install yfinance")


# ---------------------------------------------------------------------------
# Logging — INFO level, clean format
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# CoinGecko public endpoint — no API key required
COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"

# USD → INR approximate rate (fallback if live rate fetch fails)
FALLBACK_USD_INR = 83.5

# Troy ounce to grams conversion (gold is priced per troy oz)
TROY_OZ_TO_GRAMS = 31.1035

# IST = UTC + 5:30
IST = timezone(timedelta(hours=5, minutes=30))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fetch_usd_inr_rate() -> float:
    """
    Fetch the live USD/INR exchange rate via the free ExchangeRate-API endpoint.
    Falls back to FALLBACK_USD_INR on any error.
    """
    try:
        resp = requests.get(
            "https://api.exchangerate-api.com/v4/latest/USD",
            timeout=8,
        )
        resp.raise_for_status()
        rate = resp.json()["rates"]["INR"]
        logger.info(f"USD/INR rate fetched: {rate:.2f}")
        return float(rate)
    except Exception as exc:
        logger.warning(f"Could not fetch USD/INR rate ({exc}). Using fallback: {FALLBACK_USD_INR}")
        return FALLBACK_USD_INR


def fetch_btc_price(usd_inr: float) -> Optional[dict]:
    """
    Fetch BTC/USD price from CoinGecko (free, no API key).
    Returns a dict compatible with the table renderer, or None on failure.
    """
    try:
        resp = requests.get(
            COINGECKO_URL,
            params={"ids": "bitcoin", "vs_currencies": "usd"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        price_usd = data["bitcoin"]["usd"]

        return {
            "asset":    "BTC",
            "price":    price_usd,
            "currency": "USD",
            "note":     f"≈ ₹{price_usd * usd_inr:,.0f}",
        }
    except Exception as exc:
        logger.error(f"BTC fetch failed: {exc}")
        return None


def fetch_nifty50_price() -> Optional[dict]:
    """
    Fetch the latest NIFTY50 index price using yfinance (ticker: ^NSEI).
    Returns a dict compatible with the table renderer, or None on failure.
    """
    try:
        ticker = yf.Ticker("^NSEI")
        # fast_info is lighter than full history download
        info = ticker.fast_info
        price = info.last_price

        if price is None or price != price:   # NaN check
            raise ValueError("Received null/NaN price for NIFTY50")

        return {
            "asset":    "NIFTY50",
            "price":    price,
            "currency": "INR",
            "note":     "NSE Index",
        }
    except Exception as exc:
        logger.error(f"NIFTY50 fetch failed: {exc}")
        return None


def fetch_gold_price(usd_inr: float) -> Optional[dict]:
    """
    Fetch GOLD price via yfinance (GC=F — COMEX gold futures, USD/troy oz).
    Converts to INR per gram for Indian wealth management context.
    Returns a dict compatible with the table renderer, or None on failure.
    """
    try:
        ticker = yf.Ticker("GC=F")
        info = ticker.fast_info
        price_usd_per_oz = info.last_price

        if price_usd_per_oz is None or price_usd_per_oz != price_usd_per_oz:
            raise ValueError("Received null/NaN price for GOLD")

        # Convert: USD/troy oz → INR/gram
        price_inr_per_gram = (price_usd_per_oz * usd_inr) / TROY_OZ_TO_GRAMS

        return {
            "asset":    "GOLD",
            "price":    price_inr_per_gram,
            "currency": "INR/g",
            "note":     f"≈ ${price_usd_per_oz:,.2f}/oz",
        }
    except Exception as exc:
        logger.error(f"GOLD fetch failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# Table renderer — pure Python, no external libs
# ---------------------------------------------------------------------------

def print_price_table(results: list[dict], fetch_time: datetime) -> None:
    """
    Render a clean box-drawing table of asset prices to stdout.

    Parameters
    ----------
    results    : list of result dicts (may be None entries are already filtered)
    fetch_time : the datetime when fetching started
    """
    # ---- Header ----
    ist_str = fetch_time.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S IST")
    print(f"\nAsset Prices — fetched at {ist_str}\n")

    if not results:
        print("  ⚠  No data could be fetched. Check your network connection.")
        return

    # ---- Column widths ----
    col_asset    = max(len("Asset"),    max(len(r["asset"])    for r in results))
    col_price    = max(len("Price"),    max(len(f"{r['price']:,.2f}") for r in results))
    col_currency = max(len("Currency"), max(len(r["currency"]) for r in results))
    col_note     = max(len("Note"),     max(len(r.get("note", "")) for r in results))

    # Padding
    pad = 2
    w_a = col_asset    + pad
    w_p = col_price    + pad
    w_c = col_currency + pad
    w_n = col_note     + pad

    def sep(left, mid, right, fill="─"):
        return (
            left
            + fill * (w_a + 2) + mid
            + fill * (w_p + 2) + mid
            + fill * (w_c + 2) + mid
            + fill * (w_n + 2)
            + right
        )

    def row(a, p, c, n):
        return f"│ {a:<{w_a}} │ {p:>{w_p}} │ {c:<{w_c}} │ {n:<{w_n}} │"

    # ---- Render ----
    print(sep("┌", "┬", "┐"))
    print(row("Asset", "Price", "Currency", "Note"))
    print(sep("├", "┼", "┤"))
    for r in results:
        price_str = f"{r['price']:,.2f}"
        print(row(r["asset"], price_str, r["currency"], r.get("note", "")))
    print(sep("└", "┴", "┘"))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    fetch_time = datetime.now(timezone.utc)

    print("=" * 55)
    print("  TIMECELL.AI — LIVE MARKET DATA FETCH")
    print("=" * 55)
    print("  Fetching prices… (errors will be logged below)\n")

    # Shared exchange rate — fetched once and reused by assets priced in USD
    usd_inr = fetch_usd_inr_rate()

    # ---- Fetch each asset independently so one failure doesn't break others ----
    raw_results = [
        fetch_btc_price(usd_inr),
        fetch_nifty50_price(),
        fetch_gold_price(usd_inr),
    ]

    # Filter out failed fetches (None)
    successful = [r for r in raw_results if r is not None]
    failed_count = len(raw_results) - len(successful)

    # ---- Print table ----
    print_price_table(successful, fetch_time)

    # ---- Summary ----
    if failed_count > 0:
        print(f"\n  ⚠  {failed_count} asset(s) could not be fetched. "
              "See [ERROR] lines above for details.")
    else:
        print(f"\n  ✓ All {len(successful)} assets fetched successfully.")

    print(f"  Exchange rate used: 1 USD = ₹{usd_inr:.2f}\n")


if __name__ == "__main__":
    main()
