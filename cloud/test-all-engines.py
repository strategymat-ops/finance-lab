"""
Finance Lab — Comprehensive Automated Verification Suite
=========================================================
Tests all professional engines, economic relations models,
derivatives pricing, systemic risk clearing, and experiments.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Force UTF-8 stdout across all platforms (Windows cp1251 & Linux)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add backend directory to sys.path so we can import app modules directly
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_banner(title: str):
    print(f"\n{CYAN}{BOLD}======================================================================={RESET}")
    print(f"{CYAN}{BOLD}   {title.center(63)}   {RESET}")
    print(f"{CYAN}{BOLD}======================================================================={RESET}\n")


def test_section(name: str):
    print(f"\n{YELLOW}{BOLD}▶ Testing: {name}{RESET}")


def report_result(test_name: str, passed: bool, details: str, duration_ms: float):
    tag = f"{GREEN}[PASS]{RESET}" if passed else f"{RED}[FAIL]{RESET}"
    time_str = f"{duration_ms:.1f}ms"
    print(f"  {tag} {test_name:<46} ({time_str:>7}) : {details}")
    return passed


def main():
    print_banner("FINANCE LAB — INSTITUTIONAL ENGINE SELF-TEST")
    start_all = time.time()
    results = []

    # ── 1. FastAPI App Import & Health ────────────────────────────────────
    test_section("1. Core FastAPI Application & Routing")
    t0 = time.time()
    try:
        from app import app
        from app.api import dsge, fed, instruments, abm, data_sources, experiments
        route_count = len(app.routes)
        passed = route_count >= 15
        results.append(report_result(
            "FastAPI App & Routers Loaded",
            passed,
            f"{route_count} routes registered across all modules",
            (time.time() - t0) * 1000,
        ))
    except Exception as e:
        results.append(report_result("FastAPI App Load", False, str(e), (time.time() - t0) * 1000))

    # ── 2. Federal Reserve & Central Banking Engine ────────────────────────
    test_section("2. Federal Reserve Policy & Yield Curve Engine")
    t0 = time.time()
    try:
        from app.api.fed import taylor_rule, TaylorRuleRequest
        req = TaylorRuleRequest(inflation_rate=0.035, output_gap=-0.005)
        calc = taylor_rule(req)
        nominal_pct = calc.nominal_policy_rate * 100.0
        passed = 3.5 <= nominal_pct <= 6.5
        results.append(report_result(
            "Taylor Rule (1993) Policy Target",
            passed,
            f"π=3.5%, y=-0.5% => Rate = {nominal_pct:.2f}% (Taylor recommendation)",
            (time.time() - t0) * 1000,
        ))
    except Exception as e:
        results.append(report_result("Taylor Rule Policy Target", False, str(e), (time.time() - t0) * 1000))

    t0 = time.time()
    try:
        import asyncio
        from app.api.fed import get_yield_curve
        curve = asyncio.run(get_yield_curve())
        passed = len(curve.maturities) >= 7 and curve.rates[0] > 0
        spread_10y_2y = curve.rates[curve.maturities.index("10Y")] - curve.rates[curve.maturities.index("2Y")]
        results.append(report_result(
            "QuantLib US Treasury Curve Bootstrapping",
            passed,
            f"Bootstrapped {len(curve.maturities)} tenors. 10Y-2Y spread: {spread_10y_2y:.2f}%",
            (time.time() - t0) * 1000,
        ))
    except Exception as e:
        results.append(report_result("Yield Curve Bootstrapping", False, str(e), (time.time() - t0) * 1000))

    # ── 3. Derivatives Pricing (QuantLib Desk) ─────────────────────────────
    test_section("3. QuantLib Financial Derivatives & Greeks")
    t0 = time.time()
    try:
        import asyncio
        from app.api.instruments import price_option, OptionPriceRequest
        req = OptionPriceRequest(
            spot_price=100.0,
            strike_price=100.0,
            volatility=0.25,
            risk_free_rate=0.045,
            maturity_years=1.0,
            option_type="call",
            pricing_engine="black_scholes",
        )
        res = asyncio.run(price_option(req))
        passed = res.npv > 8.0 and res.delta is not None and 0.4 <= res.delta <= 0.7
        results.append(report_result(
            "European Option Valuation & Greeks",
            passed,
            f"Call NPV=${res.npv:.2f}, Delta={res.delta:.3f}, Gamma={res.gamma:.4f}, Vega={res.vega:.3f}",
            (time.time() - t0) * 1000,
        ))
    except Exception as e:
        results.append(report_result("Option Valuation & Greeks", False, str(e), (time.time() - t0) * 1000))

    # ── 4. Systemic Risk & Interbank Contagion ─────────────────────────────
    test_section("4. Interbank Contagion & Solvency Clearing (Eisenberg-Noe)")
    t0 = time.time()
    try:
        import asyncio
        from app.api.abm import run_eisenberg_noe_stress_test, EisenbergNoeRequest
        req = EisenbergNoeRequest(
            bank_names=["JPM", "BAC", "CITI", "GS", "MS"],
            liabilities_matrix=[
                [0, 50, 20, 10, 0],
                [40, 0, 30, 0, 15],
                [10, 30, 0, 25, 20],
                [5, 15, 20, 0, 35],
                [15, 0, 10, 30, 0],
            ],
            operating_cash_flows=[80, 55, 40, 45, 50],
            asset_shock_pct=0.30,  # 30% asset loss
        )
        res = asyncio.run(run_eisenberg_noe_stress_test(req))
        passed = len(res.clearing_vector) == 5 and res.contagion_rounds >= 1
        results.append(report_result(
            "Eisenberg-Noe 2001 Contagion Stress Test",
            passed,
            f"Converged in {res.contagion_rounds} rounds. Systemic loss: ${res.systemic_loss}M (SRI: {res.systemic_risk_index:.3f})",
            (time.time() - t0) * 1000,
        ))
    except Exception as e:
        results.append(report_result("Eisenberg-Noe Stress Test", False, str(e), (time.time() - t0) * 1000))

    # ── 5. AI in Economy: Algorithmic Collusion ────────────────────────────
    test_section("5. AI Algorithmic Pricing Collusion (Calvano et al. AER 2020)")
    t0 = time.time()
    try:
        import asyncio
        from app.api.abm import simulate_ai_algorithmic_collusion, AIPricingGameRequest
        req = AIPricingGameRequest(
            n_sellers=2,
            episodes=300,
            discount_factor=0.95,
            learning_rate=0.15,
        )
        res = asyncio.run(simulate_ai_algorithmic_collusion(req))
        passed = res.collusion_index >= 0.0 and len(res.price_trajectory) > 5
        results.append(report_result(
            "Autonomous AI Pricing Agents (Q-Learning)",
            passed,
            f"Collusion Index Δ={res.collusion_index:.3f} | Final Price=${res.final_average_price:.2f} (Nash=${res.nash_price:.2f}, Monopoly=${res.monopoly_price:.2f})",
            (time.time() - t0) * 1000,
        ))
    except Exception as e:
        results.append(report_result("AI Pricing Collusion", False, str(e), (time.time() - t0) * 1000))

    # ── 6. New Economic Relations: Programmable CBDC ───────────────────────
    test_section("6. New Economic Relations: Programmable CBDC with Demurrage")
    t0 = time.time()
    try:
        import asyncio
        from app.api.experiments import run_experiment, ExperimentConfig
        req = ExperimentConfig(
            experiment_type="programmable_cbdc",
            name="CBDC-Demurrage-Test",
            horizon_quarters=16,
            parameters={"cbdc_interest_rate": -0.015, "bank_deposit_rate": 0.03, "demurrage_enabled": True},
        )
        res = asyncio.run(run_experiment(req))
        passed = len(res.metrics["money_velocity"]) == 16 and len(res.economic_findings) >= 2
        results.append(report_result(
            "Silvio Gesell Currency Demurrage Simulator",
            passed,
            f"Velocity evolved from {res.metrics['money_velocity'][0]} to {res.metrics['money_velocity'][-1]}. {len(res.economic_findings)} equilibrium findings generated.",
            (time.time() - t0) * 1000,
        ))
    except Exception as e:
        results.append(report_result("CBDC Demurrage Simulator", False, str(e), (time.time() - t0) * 1000))

    # ── 7. Novel Instrument: AMM Concentrated Liquidity ────────────────────
    test_section("7. Novel Instrument: Concentrated Liquidity AMM (Uniswap v3)")
    t0 = time.time()
    try:
        import asyncio
        from app.api.experiments import run_experiment, ExperimentConfig
        req = ExperimentConfig(
            experiment_type="novel_instrument_amm",
            name="AMM-v3-Test",
            horizon_quarters=4,
            parameters={"current_price": 100.0, "range_lower": 80.0, "range_upper": 125.0},
        )
        res = asyncio.run(run_experiment(req))
        cap_eff = res.equilibrium_summary["capital_efficiency_multiplier"]
        passed = cap_eff > 1.0 and len(res.metrics["concentrated_portfolio_value"]) > 0
        results.append(report_result(
            "Concentrated Liquidity Invariant Evaluation",
            passed,
            f"Capital efficiency: {cap_eff}x over standard constant-product pool.",
            (time.time() - t0) * 1000,
        ))
    except Exception as e:
        results.append(report_result("Concentrated Liquidity Invariant", False, str(e), (time.time() - t0) * 1000))

    # ── 8. Compute-Backed Tokens (CBT) ─────────────────────────────────────
    test_section("8. Novel Instrument: Compute-Backed Tokens (CBT)")
    t0 = time.time()
    try:
        import asyncio
        from app.api.experiments import run_experiment, ExperimentConfig
        req = ExperimentConfig(
            experiment_type="compute_backed_token",
            name="CBT-Test",
            horizon_quarters=12,
            parameters={"cluster_cost_usd": 1_000_000, "gpu_price_per_hour": 2.50},
        )
        res = asyncio.run(run_experiment(req))
        cash_gen = res.equilibrium_summary["total_cash_generated"]
        passed = cash_gen > 100_000
        results.append(report_result(
            "Compute-Backed Token Cash Flow & NAV Model",
            passed,
            f"3-year total GPU compute cash flow: ${cash_gen:,.2f}",
            (time.time() - t0) * 1000,
        ))
    except Exception as e:
        results.append(report_result("Compute-Backed Tokens", False, str(e), (time.time() - t0) * 1000))

    # ── 9. AI Macroeconomic Transformation ─────────────────────────────────
    test_section("9. AI Macroeconomic Transformation & Labor Share")
    t0 = time.time()
    try:
        import asyncio
        from app.api.experiments import run_experiment, ExperimentConfig
        req = ExperimentConfig(
            experiment_type="ai_macro_transformation",
            name="AI-Macro-Test",
            horizon_quarters=24,
            parameters={"diffusion_rate": 0.12, "ai_dividend_tax": 0.20},
        )
        res = asyncio.run(run_experiment(req))
        gains = res.equilibrium_summary["final_output_gain_pct"]
        passed = gains > 50.0
        results.append(report_result(
            "AI Cognitive Automation & Universal Dividend",
            passed,
            f"Real output expansion: +{gains}%. Labor share compressed to {res.equilibrium_summary['final_labor_share']}%",
            (time.time() - t0) * 1000,
        ))
    except Exception as e:
        results.append(report_result("AI Macro Transformation", False, str(e), (time.time() - t0) * 1000))

    # ── 10. Official Data Sources (FRED & World Bank) ───────────────────────
    test_section("10. Macroeconomic Data Gateways (FRED / World Bank)")
    t0 = time.time()
    try:
        import asyncio
        from app.api.data_sources import get_fred_series
        res = asyncio.run(get_fred_series(series_id="DFF"))
        passed = len(res.data) > 0 and res.series_id == "DFF"
        results.append(report_result(
            "Federal Reserve Economic Data (FRED) Gateway",
            passed,
            f"Series {res.series_id} ({res.title}) returned {len(res.data)} observations",
            (time.time() - t0) * 1000,
        ))
    except Exception as e:
        results.append(report_result("FRED Gateway", False, str(e), (time.time() - t0) * 1000))

    # ── Summary Report ────────────────────────────────────────────────────
    total_time = (time.time() - start_all) * 1000
    passed_count = sum(1 for r in results if r)
    total_count = len(results)

    print("\n" + "=" * 71)
    if passed_count == total_count:
        print(f"{GREEN}{BOLD}[OK] ALL {total_count}/{total_count} QUANTITATIVE ENGINES VERIFIED SUCCESSFULLY ({total_time:.1f}ms){RESET}")
        print(f"{CYAN}  Finance Lab is 100% operational and ready for frontier economic research.{RESET}")
    else:
        print(f"{RED}{BOLD}[FAIL] {total_count - passed_count} of {total_count} CHECKS FAILED ({total_time:.1f}ms){RESET}")
    print("=" * 71 + "\n")

    sys.exit(0 if passed_count == total_count else 1)


if __name__ == "__main__":
    main()
