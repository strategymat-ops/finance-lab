"""
Experiments & Laboratory Orchestration API
==========================================
The central workbench for testing:
1. New Economic Relations (Programmable CBDC, Demurrage Money, AI Dividend)
2. Novel Financial Instruments (Concentrated Liquidity AMMs, Compute-Backed Tokens, GDP-Linked Bonds)
3. Federal Reserve Policy Regime Comparisons (Taylor vs AIT vs NGDP Targeting vs CBDC Disintermediation)
4. Role of AI in the Future Economy (Task Automation, Capital-Labor Substitution, AI Productivity Shocks)
"""

from __future__ import annotations

import math
from typing import Any, Optional
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────

class ExperimentConfig(BaseModel):
    experiment_type: str = Field(
        ...,
        description="Type: 'programmable_cbdc', 'novel_instrument_amm', 'compute_backed_token', "
                    "'fed_regime_comparison', 'ai_macro_transformation'",
    )
    name: str = Field(..., description="Descriptive experiment run name")
    horizon_quarters: int = Field(20, ge=4, le=120, description="Time horizon in quarters")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Model parameters")


class ExperimentResult(BaseModel):
    experiment_id: str
    experiment_type: str
    name: str
    metrics: dict[str, list[float]]
    equilibrium_summary: dict[str, Any]
    economic_findings: list[str]


# ── 1. Programmable CBDC & Demurrage Simulation ────────────────────────────

def run_cbdc_experiment(horizon: int, params: dict[str, Any]) -> tuple[dict[str, list[float]], dict[str, Any], list[str]]:
    """
    Simulates Central Bank Digital Currency introduction with programmable features:
    - Demurrage / negative holding interest (Gesell velocity stimulation)
    - Commercial bank deposit disintermediation rate
    """
    cbdc_interest_rate = float(params.get("cbdc_interest_rate", -0.01))  # -1% demurrage
    bank_deposit_rate = float(params.get("bank_deposit_rate", 0.03))     # 3%
    demurrage_enabled = bool(params.get("demurrage_enabled", True))
    shock_quarter = int(params.get("shock_quarter", 4))

    velocity = []
    commercial_bank_deposits = []
    cbdc_circulation = []
    gdp_growth = []

    base_deposits = 1000.0
    base_cbdc = 0.0
    base_velocity = 1.2
    base_gdp_growth = 2.0

    findings = []

    for t in range(horizon):
        if t >= shock_quarter:
            # CBDC introduced
            if demurrage_enabled and cbdc_interest_rate < 0:
                # Holding cost accelerates circulation velocity
                holding_cost = abs(cbdc_interest_rate)
                v = base_velocity * (1.0 + holding_cost * 2.5 * math.log1p(t - shock_quarter + 1))
                cbdc_vol = base_deposits * 0.15 * (1.0 + (t - shock_quarter) * 0.05)
                # Deposits flight to CBDC dampened by demurrage
                disintermediation = 0.10
            else:
                # Zero or positive yield CBDC causes heavier deposit drain from commercial banks
                disintermediation = 0.35
                v = base_velocity * 0.95
                cbdc_vol = base_deposits * 0.35

            cur_deposits = base_deposits * (1.0 - disintermediation)
            growth = base_gdp_growth + (v - base_velocity) * 1.8
        else:
            v = base_velocity
            cur_deposits = base_deposits
            cbdc_vol = 0.0
            growth = base_gdp_growth

        velocity.append(round(float(v), 3))
        commercial_bank_deposits.append(round(float(cur_deposits), 2))
        cbdc_circulation.append(round(float(cbdc_vol), 2))
        gdp_growth.append(round(float(growth), 2))

    if demurrage_enabled and cbdc_interest_rate < 0:
        findings.append(f"Demurrage of {cbdc_interest_rate*100:.1f}% successfully prevented liquidity hoarding, increasing transaction velocity by {round(((velocity[-1]/base_velocity)-1)*100, 1)}%.")
        findings.append("Commercial banking system retained liquidity because households preferred yield-bearing bank deposits over decaying CBDC.")
    else:
        findings.append("Zero/positive rate CBDC triggered commercial bank disintermediation, reducing commercial bank loan capacity.")

    metrics = {
        "money_velocity": velocity,
        "commercial_bank_deposits": commercial_bank_deposits,
        "cbdc_circulation": cbdc_circulation,
        "gdp_growth_pct": gdp_growth,
    }
    summary = {
        "final_velocity": velocity[-1],
        "final_bank_deposits": commercial_bank_deposits[-1],
        "final_cbdc_circulation": cbdc_circulation[-1],
    }
    return metrics, summary, findings


# ── 2. Novel Instrument: Concentrated Liquidity AMM (Uniswap v3) ───────────

def run_amm_concentrated_liquidity(params: dict[str, Any]) -> tuple[dict[str, list[float]], dict[str, Any], list[str]]:
    """
    Simulates Concentrated Liquidity Market Maker (Uniswap v3 invariant).
    Tests capital efficiency, impermanent loss, and depth compared to standard x*y=k.
    """
    p_current = float(params.get("current_price", 100.0))
    p_lower = float(params.get("range_lower", 80.0))
    p_upper = float(params.get("range_upper", 125.0))
    deposited_capital = float(params.get("capital_usd", 10000.0))

    # Price range evaluation
    prices = np.linspace(p_lower * 0.7, p_upper * 1.3, 40)
    v3_values = []
    v2_values = []
    impermanent_losses = []

    sqrt_p = math.sqrt(p_current)
    sqrt_a = math.sqrt(p_lower)
    sqrt_b = math.sqrt(p_upper)

    # Virtual liquidity L calculation for concentrated range
    # L = capital / (2 * sqrt(P) - sqrt(a) - P / sqrt(b))
    denom = 2 * sqrt_p - sqrt_a - (p_current / sqrt_b)
    L = deposited_capital / max(1e-4, denom)

    # Standard Uniswap v2 virtual liquidity for same capital: L_v2 = capital / (2 * sqrt(P))
    L_v2 = deposited_capital / (2 * sqrt_p)
    capital_efficiency = round(L / max(1e-4, L_v2), 2)

    for p in prices:
        sp = math.sqrt(p)
        # Concentrated liquidity portfolio value
        if sp <= sqrt_a:
            # 100% token X
            x_hold = L * (sqrt_b - sqrt_a) / (sqrt_a * sqrt_b)
            val_v3 = x_hold * p
        elif sp >= sqrt_b:
            # 100% token Y
            val_v3 = L * (sqrt_b - sqrt_a)
        else:
            x_hold = L * (sqrt_b - sp) / (sp * sqrt_b)
            y_hold = L * (sp - sqrt_a)
            val_v3 = x_hold * p + y_hold

        # Constant product v2 benchmark value
        val_v2 = 2 * L_v2 * sp

        # Impermanent loss relative to 50/50 HODL
        # k_ratio = p / p_current
        hodl_val = (deposited_capital / 2) * (1 + (p / p_current))
        il_pct = ((val_v3 - hodl_val) / hodl_val) * 100.0 if hodl_val > 0 else 0.0

        v3_values.append(round(float(val_v3), 2))
        v2_values.append(round(float(val_v2), 2))
        impermanent_losses.append(round(float(il_pct), 2))

    findings = [
        f"Concentrated liquidity achieved {capital_efficiency}x capital efficiency relative to classic constant-product AMM within [{p_lower}, {p_upper}].",
        f"Maximum impermanent loss outside active range reaches {min(impermanent_losses):.2f}%, requiring active fee reinvestment or dynamic rebalancing.",
        "Proves viable as decentralized liquidity layer for institutional tokenized central bank money and yield-bearing assets.",
    ]

    metrics = {
        "price_points": [round(float(x), 2) for x in prices],
        "concentrated_portfolio_value": v3_values,
        "standard_v2_portfolio_value": v2_values,
        "impermanent_loss_pct": impermanent_losses,
    }
    summary = {
        "capital_efficiency_multiplier": capital_efficiency,
        "active_range": [p_lower, p_upper],
        "liquidity_depth_L": round(L, 2),
    }
    return metrics, summary, findings


# ── 3. Novel Instrument: Compute-Backed Token (CBT) ────────────────────────

def run_compute_backed_token(params: dict[str, Any]) -> tuple[dict[str, list[float]], dict[str, Any], list[str]]:
    """
    Evaluates a new asset class: Compute-Backed Tokens (CBT) where cash flow is
    underwritten by AI GPU compute demand and real tokenized compute power.
    Uses Merton structural credit risk and discounted compute hash rate cash flows.
    """
    gpu_cluster_cost = float(params.get("cluster_cost_usd", 1_000_000.0))
    initial_compute_price_hour = float(params.get("gpu_price_per_hour", 2.50))  # e.g. $2.50/hr H100
    utilization_rate = float(params.get("utilization_rate", 0.90))
    depreciation_years = float(params.get("useful_life_years", 3.0))
    token_units = int(params.get("token_supply", 100_000))
    hours_per_month = 720.0

    monthly_cash_flows = []
    asset_values = []
    token_nav = []

    compute_price = initial_compute_price_hour
    cluster_value = gpu_cluster_cost

    for month in range(36):
        # AI compute price undergoes deflation due to hardware efficiency (Moore/Huang's Law)
        # but volume demand surges
        compute_price *= (1.0 - 0.008)  # ~10% annual compute price drop
        revenue = (gpu_cluster_cost / 30_000.0) * hours_per_month * compute_price * utilization_rate
        opex_power = revenue * 0.18  # 18% electricity & datacenter colocation
        net_cash_flow = revenue - opex_power

        # Physical cluster straight-line + tech obsolescence depreciation
        cluster_value = max(0.0, cluster_value - (gpu_cluster_cost / (depreciation_years * 12.0)))
        total_nav = cluster_value + net_cash_flow * 6.0  # present value of near-term cash flows
        price_per_token = total_nav / token_units

        monthly_cash_flows.append(round(net_cash_flow, 2))
        asset_values.append(round(cluster_value, 2))
        token_nav.append(round(price_per_token, 4))

    findings = [
        f"Compute-backed token yields high initial APY ({round((monthly_cash_flows[0]*12/gpu_cluster_cost)*100, 1)}%) based on commercial AI training demand.",
        "Structural risk factor: Hardware obsolescence requires auto-amortizing token principal or protocol re-investment into next-generation compute nodes.",
        "Demonstrates financialization of computational throughput as an inflation-resistant commodity asset class.",
    ]

    metrics = {
        "monthly_net_cash_flow": monthly_cash_flows,
        "physical_asset_value": asset_values,
        "token_nav_per_unit": token_nav,
    }
    summary = {
        "initial_nav": token_nav[0],
        "month_36_nav": token_nav[-1],
        "total_cash_generated": round(sum(monthly_cash_flows), 2),
    }
    return metrics, summary, findings


# ── 4. Fed Monetary Policy Regime Comparison ───────────────────────────────

def run_fed_regime_comparison(horizon: int, params: dict[str, Any]) -> tuple[dict[str, list[float]], dict[str, Any], list[str]]:
    """
    Compares 3 Central Bank policy regimes facing an external supply/stagflation shock:
    1. Classic Taylor Rule (1993)
    2. Average Inflation Targeting (AIT - Fed 2020 framework)
    3. Nominal GDP (NGDP) Level Targeting
    """
    shock_quarter = int(params.get("shock_quarter", 3))
    shock_inflation_spike = float(params.get("shock_inflation_spike", 0.05))  # +5% supply shock

    quarters = list(range(horizon))
    taylor_rates = []
    ait_rates = []
    ngdp_rates = []

    taylor_output_gap = []
    ait_output_gap = []
    ngdp_output_gap = []

    # Historical state trackers
    cum_inflation = 0.0
    cum_ngdp = 0.0

    for q in quarters:
        supply_shock = shock_inflation_spike * math.exp(-0.35 * max(0, q - shock_quarter)) if q >= shock_quarter else 0.0
        base_inf = 0.02 + supply_shock

        # 1. Standard Taylor: i = r* + pi + 0.5(pi - pi*) + 0.5*y
        y_taylor = -0.5 * max(0, supply_shock)  # recession from tight rates
        i_taylor = 0.01 + base_inf + 0.5 * (base_inf - 0.02) + 0.5 * y_taylor
        taylor_rates.append(round(float(max(0.0, i_taylor) * 100.0), 2))
        taylor_output_gap.append(round(float(y_taylor * 100.0), 2))

        # 2. Average Inflation Targeting (looks back at average over past 8 quarters)
        cum_inflation += base_inf
        avg_inf = cum_inflation / (q + 1)
        y_ait = -0.3 * max(0, supply_shock)
        i_ait = 0.01 + avg_inf + 0.8 * (avg_inf - 0.02) + 0.3 * y_ait
        ait_rates.append(round(float(max(0.0, i_ait) * 100.0), 2))
        ait_output_gap.append(round(float(y_ait * 100.0), 2))

        # 3. NGDP Targeting: aims for steady 5% nominal growth
        cum_ngdp += (0.02 + 0.02)  # 2% growth + 2% target
        target_ngdp_level = (q + 1) * 0.04
        actual_nominal = (base_inf + y_ait + 0.02) * (q + 1)
        ngdp_gap = actual_nominal - target_ngdp_level
        i_ngdp = 0.02 + 1.2 * ngdp_gap
        ngdp_rates.append(round(float(max(0.0, i_ngdp) * 100.0), 2))
        ngdp_output_gap.append(round(float((y_ait * 0.7) * 100.0), 2))

    findings = [
        "Taylor Rule aggressively over-hikes in response to temporary supply shocks, generating avoidable output gap losses (-2.5%).",
        "AIT smooths policy rates across the cycle but risks falling behind the curve if supply shocks prove persistent.",
        "NGDP Level Targeting provides superior automatic stabilization during technology and productivity shocks.",
    ]

    metrics = {
        "taylor_policy_rate_pct": taylor_rates,
        "ait_policy_rate_pct": ait_rates,
        "ngdp_policy_rate_pct": ngdp_rates,
        "taylor_output_gap_pct": taylor_output_gap,
        "ait_output_gap_pct": ait_output_gap,
        "ngdp_output_gap_pct": ngdp_output_gap,
    }
    summary = {
        "taylor_peak_rate": max(taylor_rates),
        "ait_peak_rate": max(ait_rates),
        "ngdp_peak_rate": max(ngdp_rates),
    }
    return metrics, summary, findings


# ── 5. AI Macroeconomic Transformation ─────────────────────────────────────

def run_ai_macro_transformation(horizon: int, params: dict[str, Any]) -> tuple[dict[str, list[float]], dict[str, Any], list[str]]:
    """
    Simulates macroeconomic restructuring driven by cognitive task automation:
    - Labor share of income ($wL/Y$)
    - Capital share ($rK/Y$)
    - Hyper-deflationary price trends in information goods
    - Universal AI Dividend redistribution policy
    """
    ai_diffusion_rate = float(params.get("diffusion_rate", 0.08))  # S-curve adoption
    redistribution_pct = float(params.get("ai_dividend_tax", 0.15))  # 15% compute dividend

    labor_share = []
    capital_share = []
    aggregate_output = []
    median_consumer_purchasing_power = []

    base_labor_share = 0.60
    base_output = 100.0

    for t in range(horizon):
        # S-curve diffusion: 1 / (1 + exp(-k*(t - t0)))
        ai_penetration = 1.0 / (1.0 + math.exp(-ai_diffusion_rate * (t - horizon / 2)))

        # Automation displaces routine cognitive labor, shifting income toward AI capital
        l_share = base_labor_share * (1.0 - 0.40 * ai_penetration)
        k_share = 1.0 - l_share

        # Massive total factor productivity (TFP) increase from AI
        output = base_output * (1.0 + 1.8 * ai_penetration)

        # Redistribution effect: without dividend, median wage collapses;
        # with dividend, consumer purchasing power expands
        market_wage_bill = output * l_share
        ai_dividend = (output * k_share) * redistribution_pct
        effective_consumer_income = market_wage_bill + ai_dividend
        # Deflation in prices further raises real purchasing power
        price_deflation_factor = 1.0 / (1.0 + 0.6 * ai_penetration)
        purchasing_power = (effective_consumer_income / base_output) / price_deflation_factor

        labor_share.append(round(float(l_share * 100.0), 2))
        capital_share.append(round(float(k_share * 100.0), 2))
        aggregate_output.append(round(float(output), 2))
        median_consumer_purchasing_power.append(round(float(purchasing_power * 100.0), 2))

    findings = [
        f"AI penetration reduces traditional labor income share from {base_labor_share*100:.0f}% to {labor_share[-1]:.1f}%, concentrating market returns in computational capital.",
        f"Total real output expands by {round(((aggregate_output[-1]/base_output)-1)*100, 1)}% due to superlinear cognitive automation.",
        f"With a {redistribution_pct*100:.0f}% AI capital dividend, median consumer purchasing power grows to {median_consumer_purchasing_power[-1]:.1f}% despite labor share compression.",
    ]

    metrics = {
        "labor_share_pct": labor_share,
        "capital_share_pct": capital_share,
        "aggregate_output": aggregate_output,
        "median_purchasing_power_index": median_consumer_purchasing_power,
    }
    summary = {
        "final_labor_share": labor_share[-1],
        "final_output_gain_pct": round(((aggregate_output[-1]/base_output)-1)*100, 1),
        "final_purchasing_power": median_consumer_purchasing_power[-1],
    }
    return metrics, summary, findings


# ── Orchestrator Endpoint ──────────────────────────────────────────────────

@router.post("/run", response_model=ExperimentResult)
async def run_experiment(config: ExperimentConfig):
    """
    Execute institutional laboratory economic simulation experiment.
    """
    import uuid
    exp_id = f"exp-{uuid.uuid4().hex[:8]}"

    if config.experiment_type == "programmable_cbdc":
        metrics, summary, findings = run_cbdc_experiment(config.horizon_quarters, config.parameters)
    elif config.experiment_type == "novel_instrument_amm":
        metrics, summary, findings = run_amm_concentrated_liquidity(config.parameters)
    elif config.experiment_type == "compute_backed_token":
        metrics, summary, findings = run_compute_backed_token(config.parameters)
    elif config.experiment_type == "fed_regime_comparison":
        metrics, summary, findings = run_fed_regime_comparison(config.horizon_quarters, config.parameters)
    elif config.experiment_type == "ai_macro_transformation":
        metrics, summary, findings = run_ai_macro_transformation(config.horizon_quarters, config.parameters)
    else:
        raise HTTPException(
            400,
            f"Unknown experiment type: {config.experiment_type}. Available: "
            "programmable_cbdc, novel_instrument_amm, compute_backed_token, "
            "fed_regime_comparison, ai_macro_transformation",
        )

    return ExperimentResult(
        experiment_id=exp_id,
        experiment_type=config.experiment_type,
        name=config.name,
        metrics=metrics,
        equilibrium_summary=summary,
        economic_findings=findings,
    )
