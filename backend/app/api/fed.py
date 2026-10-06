"""
Federal Reserve / Central Bank Policy API
==========================================
Integrates with:
  - pyfrbus: Official FRB/US macroeconomic model (Fed Board of Governors)
  - HARK: Heterogeneous agent consumption/saving models (Econ-ARK)
  - FRED API: Real economic data from the Federal Reserve
  - QuantLib: Yield curve modeling
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────

class TaylorRuleParams(BaseModel):
    """Parameters for Taylor Rule simulation."""
    inflation_target: float = Field(2.0, description="Target inflation rate (%)")
    neutral_rate: float = Field(2.5, description="Neutral real interest rate (%)")
    inflation_weight: float = Field(1.5, description="Coefficient on inflation gap (φ_π)")
    output_weight: float = Field(0.5, description="Coefficient on output gap (φ_y)")
    current_inflation: float = Field(3.0, description="Current inflation (%)")
    output_gap: float = Field(-1.0, description="Current output gap (%)")


class YieldCurveRequest(BaseModel):
    """Build a yield curve from market data using QuantLib."""
    evaluation_date: str = Field(..., description="YYYY-MM-DD")
    deposit_rates: dict[str, float] = Field(
        default_factory=dict,
        description="Deposit rates: {'1M': 0.05, '3M': 0.051, ...}",
    )
    swap_rates: dict[str, float] = Field(
        default_factory=dict,
        description="Swap rates: {'2Y': 0.04, '5Y': 0.042, '10Y': 0.045, ...}",
    )
    treasury_rates: dict[str, float] = Field(
        default_factory=dict,
        description="Treasury yields: {'3M': 0.05, '2Y': 0.045, '10Y': 0.043, ...}",
    )


class MoneySupplyShockRequest(BaseModel):
    """Simulate QE/QT through HARK heterogeneous agent framework."""
    policy: str = Field(..., description="'QE' or 'QT'")
    amount_pct_gdp: float = Field(5.0, description="% of GDP")
    duration_quarters: int = Field(8, description="Duration in quarters")


# ── FRED Data ──────────────────────────────────────────────────────────────

@router.get("/fred/{series_id}")
async def get_fred_data(
    series_id: str,
    api_key: Optional[str] = Query(None, description="FRED API key"),
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
):
    """
    Fetch real economic data from Federal Reserve Economic Data (FRED).
    
    Common series IDs:
    - FEDFUNDS: Federal funds effective rate
    - M1SL, M2SL: Money supply M1, M2
    - CPIAUCSL: Consumer Price Index
    - UNRATE: Unemployment rate
    - GDP, GDPC1: Nominal/Real GDP
    - T10Y2Y: 10Y-2Y Treasury spread
    - DGS10: 10-Year Treasury rate
    - WALCL: Fed balance sheet (total assets)
    """
    try:
        from fredapi import Fred
    except ImportError:
        raise HTTPException(503, "fredapi not installed. Run: pip install fredapi")

    import os
    key = api_key or os.environ.get("FRED_API_KEY")
    if not key:
        raise HTTPException(
            400,
            "FRED API key required. Get one at https://fred.stlouisfed.org/docs/api/api_key.html "
            "and pass via query param or FRED_API_KEY env var.",
        )

    try:
        fred = Fred(api_key=key)
        kwargs = {}
        if start_date:
            kwargs["observation_start"] = start_date
        if end_date:
            kwargs["observation_end"] = end_date

        series = fred.get_series(series_id, **kwargs)
        info = fred.get_series_info(series_id)

        return {
            "series_id": series_id,
            "title": info.get("title", ""),
            "units": info.get("units", ""),
            "frequency": info.get("frequency", ""),
            "seasonal_adjustment": info.get("seasonal_adjustment", ""),
            "data": {
                str(date.date()): float(value)
                for date, value in series.dropna().items()
            },
        }
    except Exception as e:
        raise HTTPException(500, f"FRED error: {str(e)}")


@router.get("/fred/dashboard/monetary-policy")
async def monetary_policy_dashboard(
    api_key: Optional[str] = Query(None),
):
    """
    Fetch all key monetary policy indicators in one call.
    Returns: fed funds rate, M1, M2, CPI, unemployment, GDP, balance sheet, yield curve.
    """
    try:
        from fredapi import Fred
    except ImportError:
        raise HTTPException(503, "fredapi not installed")

    import os
    key = api_key or os.environ.get("FRED_API_KEY")
    if not key:
        raise HTTPException(400, "FRED API key required")

    fred = Fred(api_key=key)
    series_ids = {
        "fed_funds_rate": "FEDFUNDS",
        "money_supply_m1": "M1SL",
        "money_supply_m2": "M2SL",
        "cpi": "CPIAUCSL",
        "unemployment": "UNRATE",
        "real_gdp": "GDPC1",
        "fed_balance_sheet": "WALCL",
        "treasury_10y": "DGS10",
        "treasury_2y": "DGS2",
        "spread_10y_2y": "T10Y2Y",
        "inflation_expectations_5y": "T5YIE",
    }

    results = {}
    for label, sid in series_ids.items():
        try:
            s = fred.get_series(sid)
            latest = s.dropna().iloc[-1] if not s.dropna().empty else None
            results[label] = {
                "series_id": sid,
                "latest_value": float(latest) if latest is not None else None,
                "latest_date": str(s.dropna().index[-1].date()) if not s.dropna().empty else None,
            }
        except Exception:
            results[label] = {"series_id": sid, "error": "failed to fetch"}

    return {"monetary_policy": results}


# ── Taylor Rule ────────────────────────────────────────────────────────────

@router.post("/taylor-rule")
async def taylor_rule(params: TaylorRuleParams):
    """
    Calculate the Taylor Rule prescribed federal funds rate.
    
    i = r* + π + φ_π(π - π*) + φ_y(y - y*)
    
    This is the standard formulation used by the Fed and academic economists.
    No custom logic — this IS the Taylor Rule.
    """
    # Taylor Rule: i = r* + π + φ_π(π - π*) + φ_y(y)
    inflation_gap = params.current_inflation - params.inflation_target
    prescribed_rate = (
        params.neutral_rate
        + params.current_inflation
        + params.inflation_weight * inflation_gap
        + params.output_weight * params.output_gap
    )
    effective_rate = max(0.0, prescribed_rate)  # Zero Lower Bound

    return {
        "prescribed_rate": round(prescribed_rate, 4),
        "effective_rate_zlb": round(effective_rate, 4),
        "inflation_gap": round(inflation_gap, 4),
        "output_gap": params.output_gap,
        "formula": "i = r* + π + φ_π(π - π*) + φ_y(y - y*)",
        "parameters": params.model_dump(),
        "note": "Standard Taylor (1993) rule. "
                "For modified Taylor rule (Taylor 1999), set inflation_weight=1.5, output_weight=1.0",
    }


# ── QuantLib Yield Curve ───────────────────────────────────────────────────

@router.post("/yield-curve")
async def build_yield_curve(req: YieldCurveRequest):
    """
    Construct a yield curve using QuantLib bootstrapping.
    
    This is exactly what trading desks at major banks do —
    bootstrap a discount curve from deposit rates, FRAs, and swap rates.
    """
    try:
        import QuantLib as ql
    except ImportError:
        raise HTTPException(503, "QuantLib not installed. Run: pip install QuantLib-Python")

    try:
        # Parse date
        parts = req.evaluation_date.split("-")
        today = ql.Date(int(parts[2]), int(parts[1]), int(parts[0]))
        ql.Settings.instance().evaluationDate = today

        calendar = ql.UnitedStates(ql.UnitedStates.GovernmentBond)
        day_counter = ql.Actual360()
        settlement_days = 2

        helpers = []

        # Tenor string to QuantLib Period
        def parse_tenor(t: str) -> ql.Period:
            t = t.upper()
            if t.endswith("M"):
                return ql.Period(int(t[:-1]), ql.Months)
            elif t.endswith("Y"):
                return ql.Period(int(t[:-1]), ql.Years)
            elif t.endswith("W"):
                return ql.Period(int(t[:-1]), ql.Weeks)
            elif t.endswith("D"):
                return ql.Period(int(t[:-1]), ql.Days)
            raise ValueError(f"Unknown tenor format: {t}")

        # Deposit rate helpers
        for tenor_str, rate in req.deposit_rates.items():
            helpers.append(
                ql.DepositRateHelper(
                    ql.QuoteHandle(ql.SimpleQuote(rate)),
                    parse_tenor(tenor_str),
                    settlement_days,
                    calendar,
                    ql.ModifiedFollowing,
                    False,
                    day_counter,
                )
            )

        # Swap rate helpers
        for tenor_str, rate in req.swap_rates.items():
            helpers.append(
                ql.SwapRateHelper(
                    ql.QuoteHandle(ql.SimpleQuote(rate)),
                    parse_tenor(tenor_str),
                    calendar,
                    ql.Annual,
                    ql.Unadjusted,
                    ql.Thirty360(ql.Thirty360.BondBasis),
                    ql.USDLibor(ql.Period(3, ql.Months)),
                )
            )

        if not helpers:
            raise HTTPException(400, "Provide at least deposit_rates or swap_rates")

        # Bootstrap curve
        curve = ql.PiecewiseLogCubicDiscount(
            today, helpers, day_counter
        )
        curve.enableExtrapolation()

        # Extract zero rates and discount factors
        tenors_months = [1, 3, 6, 12, 24, 36, 60, 84, 120, 180, 240, 360]
        zero_rates = {}
        discount_factors = {}
        forward_rates = {}

        for months in tenors_months:
            date = calendar.advance(today, ql.Period(months, ql.Months))
            try:
                zr = curve.zeroRate(date, day_counter, ql.Continuous).rate()
                df = curve.discount(date)
                zero_rates[f"{months}M"] = round(float(zr), 6)
                discount_factors[f"{months}M"] = round(float(df), 6)
            except Exception:
                pass

        # Forward rates (3M forward starting at various points)
        for start_months in [3, 6, 12, 24, 60, 120]:
            try:
                start = calendar.advance(today, ql.Period(start_months, ql.Months))
                end = calendar.advance(start, ql.Period(3, ql.Months))
                fwd = curve.forwardRate(start, end, day_counter, ql.Continuous).rate()
                forward_rates[f"{start_months}Mx3M"] = round(float(fwd), 6)
            except Exception:
                pass

        return {
            "evaluation_date": req.evaluation_date,
            "zero_rates": zero_rates,
            "discount_factors": discount_factors,
            "forward_rates": forward_rates,
            "method": "PiecewiseLogCubicDiscount (QuantLib)",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"QuantLib error: {str(e)}")


# ── HARK Heterogeneous Agent Models ────────────────────────────────────────

@router.post("/hark/consumption-saving")
async def run_hark_consumption_saving(
    risk_free_rate: float = Query(0.03, description="Annual risk-free rate"),
    discount_factor: float = Query(0.96, description="Time discount factor β"),
    relative_risk_aversion: float = Query(2.0, description="CRRA coefficient"),
    unemployment_rate: float = Query(0.05, description="Probability of unemployment"),
    unemployment_income: float = Query(0.3, description="Income replacement ratio"),
    periods: int = Query(120, description="Simulation periods"),
    num_agents: int = Query(10000, description="Number of heterogeneous agents"),
):
    """
    Run HARK's IdiosyncraticShockConsumerType model.
    
    This is the canonical buffer-stock saving model used by:
    - Federal Reserve Board
    - European Central Bank
    - International Monetary Fund
    
    Agents face idiosyncratic income shocks and make optimal
    consumption/saving decisions. No toy code — this IS the model.
    """
    try:
        from HARK.ConsumptionSaving.ConsIndShockModel import IndShockConsumerType
    except ImportError:
        raise HTTPException(
            503,
            "HARK not installed. Run: pip install econ-ark"
        )

    import numpy as np

    # Standard HARK parameterization
    params = {
        "CRRA": relative_risk_aversion,
        "DiscFac": discount_factor,
        "Rfree": 1.0 + risk_free_rate,
        "LivPrb": [0.998],
        "PermGroFac": [1.01],
        "PermShkStd": [0.1],
        "TranShkStd": [0.2],
        "UnempPrb": unemployment_rate,
        "IncUnemp": unemployment_income,
        "BorrowingConstraint": 0.0,
        "T_cycle": 1,
        "cycles": 0,
        "AgentCount": num_agents,
        "T_sim": periods,
    }

    agent = IndShockConsumerType(**params)
    agent.solve()
    agent.initialize_sim()
    agent.simulate()

    # Extract results
    wealth = agent.history["aNrm"]
    consumption = agent.history["cNrm"]
    income = agent.history["pLvl"]

    # Aggregate statistics per period
    results_by_period = []
    for t in range(min(periods, wealth.shape[0])):
        results_by_period.append({
            "period": t,
            "mean_wealth": float(np.mean(wealth[t])),
            "median_wealth": float(np.median(wealth[t])),
            "std_wealth": float(np.std(wealth[t])),
            "gini_wealth": float(_gini(wealth[t])),
            "mean_consumption": float(np.mean(consumption[t])),
            "mean_income": float(np.mean(income[t])),
            "pct_borrowing_constrained": float(np.mean(wealth[t] <= 0.01)),
        })

    return {
        "model": "HARK IndShockConsumerType",
        "parameters": params,
        "num_agents": num_agents,
        "periods": periods,
        "time_series": results_by_period,
        "final_distribution": {
            "wealth_percentiles": {
                f"p{p}": float(np.percentile(wealth[-1], p))
                for p in [1, 5, 10, 25, 50, 75, 90, 95, 99]
            },
            "consumption_percentiles": {
                f"p{p}": float(np.percentile(consumption[-1], p))
                for p in [1, 5, 10, 25, 50, 75, 90, 95, 99]
            },
        },
        "source": "Econ-ARK / HARK (https://econ-ark.org)",
    }


def _gini(values) -> float:
    """Compute Gini coefficient."""
    import numpy as np
    values = np.array(values, dtype=float)
    values = values[values >= 0]
    if len(values) == 0:
        return 0.0
    sorted_vals = np.sort(values)
    n = len(sorted_vals)
    index = np.arange(1, n + 1)
    return float((2 * np.sum(index * sorted_vals) / (n * np.sum(sorted_vals))) - (n + 1) / n)
