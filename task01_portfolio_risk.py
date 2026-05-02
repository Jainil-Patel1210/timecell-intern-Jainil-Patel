"""
task01_portfolio_risk.py
========================
Timecell.ai — Engineering Intern Assessment · Task 01
Portfolio Risk Calculator (30 pts)

Computes key risk metrics for a given portfolio:
  - post_crash_value
  - runway_months
  - ruin_test
  - largest_risk_asset
  - concentration_warning

BONUS:
  - Moderate crash scenario (50% of expected crash magnitude)
  - CLI bar chart for allocation breakdown (no external plotting libs)

Author : <your-name>
AI Tools: Claude (claude.ai) used for code review and edge-case brainstorming
"""

from typing import Any


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def compute_risk_metrics(portfolio: dict[str, Any]) -> dict[str, Any]:
    """
    Compute risk metrics for a portfolio under a FULL crash scenario.

    Parameters
    ----------
    portfolio : dict
        Must contain:
          - "total_value_inr"    : float  — current total portfolio value in INR
          - "monthly_expenses_inr": float — monthly expenditure in INR
          - "assets"             : list[dict] — each asset has:
                "name"           : str
                "allocation_pct" : float  — percentage of portfolio (0-100)
                "expected_crash_pct": float — percentage loss during a crash (negative)

    Returns
    -------
    dict with keys:
        post_crash_value, runway_months, ruin_test,
        largest_risk_asset, concentration_warning
    """
    total_value       = portfolio.get("total_value_inr", 0)
    monthly_expenses  = portfolio.get("monthly_expenses_inr", 0)
    assets            = portfolio.get("assets", [])

    # ---- Guard: empty portfolio or zero value ----
    if total_value <= 0 or not assets:
        return {
            "post_crash_value":      0.0,
            "runway_months":         0.0,
            "ruin_test":             "FAIL",
            "largest_risk_asset":    None,
            "concentration_warning": False,
        }

    post_crash_value = 0.0
    largest_risk_score = -1.0
    largest_risk_asset = None
    concentration_warning = False

    for asset in assets:
        name           = asset.get("name", "UNKNOWN")
        alloc_pct      = asset.get("allocation_pct", 0)        # e.g. 30 means 30%
        crash_pct      = asset.get("expected_crash_pct", 0)    # e.g. -80 means -80%

        # Dollar value of this asset before crash
        asset_value = total_value * (alloc_pct / 100)

        # Value after crash: multiply by (1 + crash_pct/100)
        # crash_pct is negative, so (1 - 0.80) = 0.20 → retains 20%
        survival_factor = 1 + (crash_pct / 100)
        post_crash_value += asset_value * survival_factor

        # Risk score = allocation × |crash magnitude|  (higher → more dangerous)
        risk_score = alloc_pct * abs(crash_pct)
        if risk_score > largest_risk_score:
            largest_risk_score = risk_score
            largest_risk_asset = name

        # Concentration warning: any single asset exceeds 40% of portfolio
        if alloc_pct > 40:
            concentration_warning = True

    # Runway = post-crash portfolio ÷ monthly expenses
    # Guard against zero monthly expenses (100% cash, zero spending case)
    if monthly_expenses > 0:
        runway_months = post_crash_value / monthly_expenses
    else:
        runway_months = float("inf")   # infinite runway if no expenses

    ruin_test = "PASS" if runway_months > 12 else "FAIL"

    return {
        "post_crash_value":      round(post_crash_value, 2),
        "runway_months":         round(runway_months, 2),
        "ruin_test":             ruin_test,
        "largest_risk_asset":    largest_risk_asset,
        "concentration_warning": concentration_warning,
    }


def compute_moderate_crash_metrics(portfolio: dict[str, Any]) -> dict[str, Any]:
    """
    BONUS: Compute risk metrics under a MODERATE crash scenario.

    Each asset's expected_crash_pct is halved (50% of full crash magnitude).
    Returns the same structure as compute_risk_metrics().
    """
    # Deep-copy the portfolio and halve every crash magnitude
    import copy
    moderate_portfolio = copy.deepcopy(portfolio)

    for asset in moderate_portfolio.get("assets", []):
        asset["expected_crash_pct"] = asset.get("expected_crash_pct", 0) * 0.5

    return compute_risk_metrics(moderate_portfolio)


# ---------------------------------------------------------------------------
# BONUS: CLI bar chart
# ---------------------------------------------------------------------------

def print_allocation_bar_chart(portfolio: dict[str, Any], bar_width: int = 40) -> None:
    """
    BONUS: Print a simple ASCII / CLI bar chart of asset allocations.
    Uses no external plotting libraries — pure Python.

    Parameters
    ----------
    portfolio  : the standard portfolio dict
    bar_width  : maximum bar width in characters (default 40)
    """
    assets = portfolio.get("assets", [])
    if not assets:
        print("No assets to display.")
        return

    print("\n" + "=" * 55)
    print("  PORTFOLIO ALLOCATION BREAKDOWN")
    print("=" * 55)

    for asset in assets:
        name      = asset.get("name", "UNKNOWN")
        alloc_pct = asset.get("allocation_pct", 0)

        # Scale bar length proportionally to bar_width
        bar_len = int((alloc_pct / 100) * bar_width)
        bar     = "█" * bar_len + "░" * (bar_width - bar_len)

        # Right-pad the name so columns are aligned
        print(f"  {name:<10} │{bar}│ {alloc_pct:>5.1f}%")

    print("=" * 55)


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def format_inr(value: float) -> str:
    """Format a float as Indian Rupee string with comma separation."""
    # Python's locale module can be fiddly; simple manual formatting here
    return f"₹{value:,.2f}"


def print_metrics(label: str, metrics: dict[str, Any], total_value: float) -> None:
    """Pretty-print a single metrics dictionary to the terminal (used for edge cases)."""
    print(f"\n{'─' * 55}")
    print(f"  SCENARIO: {label}")
    print(f"{'─' * 55}")
    print(f"  Post-Crash Value      : {format_inr(metrics['post_crash_value'])}")
    print(f"  Loss from Current     : {format_inr(total_value - metrics['post_crash_value'])}")
    print(f"  Runway (months)       : {metrics['runway_months']:.1f}")
    print(f"  Ruin Test (>12 mths)  : {metrics['ruin_test']}")
    print(f"  Largest Risk Asset    : {metrics['largest_risk_asset']}")
    print(f"  Concentration Warning : {'⚠  YES' if metrics['concentration_warning'] else '✓  NO'}")
    print(f"{'─' * 55}")


def print_scenarios_side_by_side(
    full_metrics:     dict[str, Any],
    moderate_metrics: dict[str, Any],
    total_value:      float,
) -> None:
    """
    Print FULL crash and MODERATE crash results in a two-column comparison
    table so the user can instantly see the difference between scenarios.

    Layout:
      METRIC                │ FULL CRASH       │ MODERATE CRASH
      ──────────────────────┼──────────────────┼──────────────────
      Post-Crash Value      │ ₹5,700,000       │ ₹7,850,000
      ...
    """
    col_label = 22   # width of the left metric-name column
    col_val   = 20   # width of each scenario value column

    # Header row
    sep = f"  {'─' * col_label}┼{'─' * (col_val + 2)}┼{'─' * (col_val + 2)}"

    def header(left, mid1, mid2):
        return f"  {left:<{col_label}}│ {mid1:^{col_val}} │ {mid2:^{col_val}}"

    def row(label, val1, val2):
        return f"  {label:<{col_label}}│ {val1:>{col_val}} │ {val2:>{col_val}}"

    print(f"\n{'=' * 70}")
    print("  CRASH SCENARIO COMPARISON")
    print(f"{'=' * 70}")
    print(header("METRIC", "FULL CRASH (100%)", "MODERATE CRASH (50%)"))
    print(sep)

    # Post-crash value
    print(row(
        "Post-Crash Value",
        format_inr(full_metrics['post_crash_value']),
        format_inr(moderate_metrics['post_crash_value']),
    ))

    # Loss from current
    print(row(
        "Loss from Current",
        format_inr(total_value - full_metrics['post_crash_value']),
        format_inr(total_value - moderate_metrics['post_crash_value']),
    ))

    # Runway
    print(row(
        "Runway (months)",
        f"{full_metrics['runway_months']:.1f}",
        f"{moderate_metrics['runway_months']:.1f}",
    ))

    # Ruin test — add icon for quick visual scan
    def ruin_icon(r):
        return f"{'✅ PASS' if r == 'PASS' else '❌ FAIL'}"

    print(row(
        "Ruin Test (>12 mths)",
        ruin_icon(full_metrics['ruin_test']),
        ruin_icon(moderate_metrics['ruin_test']),
    ))

    # Largest risk asset
    print(row(
        "Largest Risk Asset",
        str(full_metrics['largest_risk_asset']),
        str(moderate_metrics['largest_risk_asset']),
    ))

    # Concentration warning
    def conc(c):
        return "⚠ YES" if c else "✓ NO"

    print(row(
        "Concentration Warn",
        conc(full_metrics['concentration_warning']),
        conc(moderate_metrics['concentration_warning']),
    ))

    print(f"{'=' * 70}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # ---- Sample portfolio from the task specification ----
    portfolio = {
        "total_value_inr":     10_000_000,   # 1 Crore INR
        "monthly_expenses_inr":    80_000,
        "assets": [
            {"name": "BTC",     "allocation_pct": 30, "expected_crash_pct": -80},
            {"name": "NIFTY50", "allocation_pct": 40, "expected_crash_pct": -40},
            {"name": "GOLD",    "allocation_pct": 20, "expected_crash_pct": -15},
            {"name": "CASH",    "allocation_pct": 10, "expected_crash_pct":   0},
        ],
    }

    print("\n" + "=" * 55)
    print("  TIMECELL.AI — PORTFOLIO RISK CALCULATOR")
    print("=" * 55)
    print(f"  Total Portfolio Value : {format_inr(portfolio['total_value_inr'])}")
    print(f"  Monthly Expenses      : {format_inr(portfolio['monthly_expenses_inr'])}")

    # ---- BONUS: Allocation bar chart ----
    print_allocation_bar_chart(portfolio)

    # ---- Full crash + Moderate crash — shown side by side ----
    full_metrics     = compute_risk_metrics(portfolio)
    moderate_metrics = compute_moderate_crash_metrics(portfolio)
    print_scenarios_side_by_side(full_metrics, moderate_metrics, portfolio["total_value_inr"])

    # ---- Edge-case demos ----
    print("\n\n  ─── EDGE CASE: 100% CASH PORTFOLIO ───")
    cash_portfolio = {
        "total_value_inr":     5_000_000,
        "monthly_expenses_inr": 100_000,
        "assets": [
            {"name": "CASH", "allocation_pct": 100, "expected_crash_pct": 0},
        ],
    }
    cash_metrics = compute_risk_metrics(cash_portfolio)
    print_metrics("FULL CRASH — All Cash", cash_metrics, cash_portfolio["total_value_inr"])

    print("\n  ─── EDGE CASE: ZERO MONTHLY EXPENSES ───")
    no_expense_portfolio = {
        "total_value_inr":      1_000_000,
        "monthly_expenses_inr":         0,   # no monthly expenses
        "assets": [
            {"name": "BTC", "allocation_pct": 100, "expected_crash_pct": -80},
        ],
    }
    no_exp_metrics = compute_risk_metrics(no_expense_portfolio)
    # inf runway is converted to a readable string for display
    display_metrics = dict(no_exp_metrics)
    if display_metrics["runway_months"] == float("inf"):
        display_metrics["runway_months"] = "∞ (no expenses)"
    print(f"\n  Post-Crash Value   : {format_inr(no_exp_metrics['post_crash_value'])}")
    print(f"  Runway (months)    : {display_metrics['runway_months']}")
    print(f"  Ruin Test          : {no_exp_metrics['ruin_test']}")


if __name__ == "__main__":
    main()