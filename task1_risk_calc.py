def print_allocation_chart(assets: list):
    """
    Bonus: Visualises the allocation breakdown as a simple CLI bar chart.
    Uses no external plotting libraries.
    """
    print("\n" + "="*45)
    print(" PORTFOLIO ALLOCATION BREAKDOWN")
    print("="*45)
    
    # Sort assets by allocation percentage descending for better visualization
    sorted_assets = sorted(assets, key=lambda x: x["allocation_pct"], reverse=True)
    
    for asset in sorted_assets:
        name = asset["name"]
        alloc_pct = asset["allocation_pct"]
        # Use a block character; 1 block = 2% allocation to fit within standard terminal width
        bar = "█" * int(alloc_pct / 2) 
        print(f"{name:<10} | {bar:<20} {alloc_pct}%")
    print("="*45 + "\n")


def compute_risk_metrics(portfolio: dict) -> dict:
    """
    Computes key risk metrics for a given portfolio to assess its safety.
    """
    total_value = portfolio.get("total_value_inr", 0)
    monthly_expenses = portfolio.get("monthly_expenses_inr", 0)
    assets = portfolio.get("assets", [])

    post_crash_value = 0
    moderate_post_crash_value = 0
    
    max_risk_magnitude = -1
    largest_risk_asset = None
    concentration_warning = False

    for asset in assets:
        name = asset["name"]
        alloc_pct = asset["allocation_pct"]
        crash_pct = asset["expected_crash_pct"]

        # --- Base Metrics Calculation ---
        
        # 1. Concentration Warning: True if any single asset > 40% of portfolio
        if alloc_pct > 40:
            concentration_warning = True

        # 2. Largest Risk Asset: highest (allocation * crash magnitude)
        # Using abs() to handle the magnitude since crash_pct is typically negative
        risk_magnitude = alloc_pct * abs(crash_pct)
        if risk_magnitude > max_risk_magnitude:
            max_risk_magnitude = risk_magnitude
            largest_risk_asset = name

        # --- Value Calculations ---
        
        # Current monetary value of this specific asset
        asset_value = total_value * (alloc_pct / 100)

        # Scenario A: Severe Crash (100% of expected crash magnitude)
        # E.g., if crash is -80%, we retain 20% of the value.
        asset_crash_value = asset_value * (1 + (crash_pct / 100))
        post_crash_value += asset_crash_value

        # Scenario B: Moderate Crash (Bonus - 50% of expected crash magnitude)
        moderate_crash_pct = crash_pct / 2
        moderate_asset_crash_value = asset_value * (1 + (moderate_crash_pct / 100))
        moderate_post_crash_value += moderate_asset_crash_value

    # --- Runway & Ruin Calculations ---
    
    # Handle the edge case where monthly expenses are 0 to avoid division by zero
    if monthly_expenses > 0:
        runway_months = post_crash_value / monthly_expenses
        moderate_runway_months = moderate_post_crash_value / monthly_expenses
    else:
        runway_months = float('inf')
        moderate_runway_months = float('inf')

    # Ruin test: 'PASS' if runway > 12 months, 'FAIL' otherwise
    ruin_test = 'PASS' if runway_months > 12 else 'FAIL'
    moderate_ruin_test = 'PASS' if moderate_runway_months > 12 else 'FAIL'

    # Print the bonus CLI bar chart
    print_allocation_chart(assets)

    # Return the exact dictionary structure required, plus the moderate scenario
    return {
        "post_crash_value": round(post_crash_value, 2),
        "runway_months": round(runway_months, 1),
        "ruin_test": ruin_test,
        "largest_risk_asset": largest_risk_asset,
        "concentration_warning": concentration_warning,
        
        # Bonus: Side-by-side moderate scenario
        "moderate_scenario": {
            "post_crash_value": round(moderate_post_crash_value, 2),
            "runway_months": round(moderate_runway_months, 1),
            "ruin_test": moderate_ruin_test
        }
    }


# --- Execution and Testing Block ---
if __name__ == "__main__":
    sample_portfolio = {
        "total_value_inr": 10_000_000,
        "monthly_expenses_inr": 80_000,
        "assets": [
            {"name": "BTC", "allocation_pct": 30, "expected_crash_pct": -80},
            {"name": "NIFTY50", "allocation_pct": 40, "expected_crash_pct": -40},
            {"name": "GOLD", "allocation_pct": 20, "expected_crash_pct": -15},
            {"name": "CASH", "allocation_pct": 10, "expected_crash_pct": 0},
        ]
    }

    results = compute_risk_metrics(sample_portfolio)
    
    print("--- SEVERE CRASH SCENARIO (BASE) ---")
    print(f"Post-Crash Value:      ₹{results['post_crash_value']:,.2f}")
    print(f"Runway Months:         {results['runway_months']}")
    print(f"Ruin Test (>12m):      {results['ruin_test']}")
    print(f"Largest Risk Asset:    {results['largest_risk_asset']}")
    print(f"Concentration Warning: {results['concentration_warning']}")
    
    print("\n--- MODERATE CRASH SCENARIO (BONUS) ---")
    print(f"Post-Crash Value:      ₹{results['moderate_scenario']['post_crash_value']:,.2f}")
    print(f"Runway Months:         {results['moderate_scenario']['runway_months']}")
    print(f"Ruin Test (>12m):      {results['moderate_scenario']['ruin_test']}")