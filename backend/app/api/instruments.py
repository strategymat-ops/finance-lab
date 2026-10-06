"""
Financial Instruments API — QuantLib
=====================================
All pricing is done via QuantLib — the industry standard used by
Goldman Sachs, JP Morgan, Morgan Stanley, and every major derivatives desk.

No custom pricing formulas. QuantLib handles:
  - Bond pricing (fixed/floating)
  - Interest rate swaps
  - European/American options (Black-Scholes, Binomial, MC)
  - Credit default swaps
  - Exotic derivatives
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────

class BondPriceRequest(BaseModel):
    face_value: float = Field(100.0)
    coupon_rate: float = Field(0.05, description="Annual coupon rate")
    maturity_years: int = Field(5)
    yield_rate: float = Field(0.04, description="Market yield to discount at")
    frequency: str = Field("semiannual", description="semiannual | annual | quarterly")
    evaluation_date: str = Field("2026-10-06", description="YYYY-MM-DD")


class OptionPriceRequest(BaseModel):
    spot: float = Field(100.0, description="Current underlying price")
    strike: float = Field(105.0, description="Strike price")
    risk_free_rate: float = Field(0.05, description="Risk-free interest rate")
    volatility: float = Field(0.2, description="Implied volatility")
    maturity_years: float = Field(1.0, description="Time to expiry in years")
    option_type: str = Field("call", description="'call' or 'put'")
    exercise: str = Field("european", description="'european' or 'american'")
    method: str = Field(
        "analytic",
        description="'analytic' (Black-Scholes), 'binomial' (CRR), 'monte_carlo'",
    )
    dividend_yield: float = Field(0.0, description="Continuous dividend yield")
    mc_paths: int = Field(100000, description="Number of MC paths (if method=monte_carlo)")


class SwapRequest(BaseModel):
    notional: float = Field(1_000_000.0)
    fixed_rate: float = Field(0.04)
    tenor_years: int = Field(5)
    floating_spread: float = Field(0.0, description="Spread over floating index")
    evaluation_date: str = Field("2026-10-06")
    flat_yield: float = Field(0.03, description="Flat yield for discounting")


# ── Bond Pricing ───────────────────────────────────────────────────────────

@router.post("/bond/price")
async def price_bond(req: BondPriceRequest):
    """
    Price a fixed-rate bond using QuantLib's DiscountingBondEngine.
    Returns: NPV, clean price, dirty price, accrued interest, duration, convexity.
    """
    try:
        import QuantLib as ql
    except ImportError:
        raise HTTPException(503, "QuantLib not installed")

    parts = req.evaluation_date.split("-")
    today = ql.Date(int(parts[2]), int(parts[1]), int(parts[0]))
    ql.Settings.instance().evaluationDate = today

    calendar = ql.UnitedStates(ql.UnitedStates.GovernmentBond)
    day_counter = ql.Actual360()

    freq_map = {
        "annual": ql.Annual,
        "semiannual": ql.Semiannual,
        "quarterly": ql.Quarterly,
    }
    freq = freq_map.get(req.frequency, ql.Semiannual)

    issue_date = today
    maturity = calendar.advance(today, ql.Period(req.maturity_years, ql.Years))

    schedule = ql.Schedule(
        issue_date, maturity, ql.Period(freq),
        calendar, ql.Unadjusted, ql.Unadjusted,
        ql.DateGeneration.Backward, False,
    )

    bond = ql.FixedRateBond(0, req.face_value, schedule, [req.coupon_rate], day_counter)

    yield_curve = ql.YieldTermStructureHandle(
        ql.FlatForward(today, req.yield_rate, day_counter)
    )
    engine = ql.DiscountingBondEngine(yield_curve)
    bond.setPricingEngine(engine)

    return {
        "npv": round(bond.NPV(), 6),
        "clean_price": round(bond.cleanPrice(), 6),
        "dirty_price": round(bond.dirtyPrice(), 6),
        "accrued_interest": round(bond.accruedAmount(), 6),
        "yield_to_maturity": round(
            bond.bondYield(day_counter, ql.Compounded, freq), 6
        ),
        "duration_macaulay": round(
            ql.BondFunctions.duration(bond, req.yield_rate, day_counter, ql.Compounded, freq, ql.Duration.Macaulay),
            6,
        ),
        "duration_modified": round(
            ql.BondFunctions.duration(bond, req.yield_rate, day_counter, ql.Compounded, freq, ql.Duration.Modified),
            6,
        ),
        "convexity": round(
            ql.BondFunctions.convexity(bond, req.yield_rate, day_counter, ql.Compounded, freq),
            6,
        ),
        "engine": "QuantLib DiscountingBondEngine",
    }


# ── Option Pricing ─────────────────────────────────────────────────────────

@router.post("/option/price")
async def price_option(req: OptionPriceRequest):
    """
    Price an option using QuantLib.
    
    Methods:
    - analytic: Black-Scholes-Merton (European only)
    - binomial: Cox-Ross-Rubinstein tree (European & American)
    - monte_carlo: Monte Carlo simulation (European)
    
    Returns: price, delta, gamma, vega, theta, rho.
    """
    try:
        import QuantLib as ql
    except ImportError:
        raise HTTPException(503, "QuantLib not installed")

    today = ql.Date(6, 10, 2026)
    ql.Settings.instance().evaluationDate = today

    day_counter = ql.Actual365Fixed()
    calendar = ql.UnitedStates(ql.UnitedStates.NYSE)

    maturity_date = calendar.advance(
        today,
        ql.Period(int(req.maturity_years * 365), ql.Days),
    )

    opt_type = ql.Option.Call if req.option_type.lower() == "call" else ql.Option.Put

    # Exercise type
    if req.exercise.lower() == "european":
        exercise = ql.EuropeanExercise(maturity_date)
    else:
        exercise = ql.AmericanExercise(today, maturity_date)

    payoff = ql.PlainVanillaPayoff(opt_type, req.strike)
    option = ql.VanillaOption(payoff, exercise)

    # Market data
    spot_handle = ql.QuoteHandle(ql.SimpleQuote(req.spot))
    rate_handle = ql.YieldTermStructureHandle(
        ql.FlatForward(today, req.risk_free_rate, day_counter)
    )
    dividend_handle = ql.YieldTermStructureHandle(
        ql.FlatForward(today, req.dividend_yield, day_counter)
    )
    vol_handle = ql.BlackVolTermStructureHandle(
        ql.BlackConstantVol(today, calendar, req.volatility, day_counter)
    )

    bsm_process = ql.BlackScholesMertonProcess(
        spot_handle, dividend_handle, rate_handle, vol_handle
    )

    # Pricing engine
    if req.method == "analytic":
        if req.exercise.lower() == "american":
            raise HTTPException(
                400,
                "Analytic (Black-Scholes) only supports European options. "
                "Use 'binomial' for American options."
            )
        engine = ql.AnalyticEuropeanEngine(bsm_process)
    elif req.method == "binomial":
        steps = 500
        engine = ql.BinomialVanillaEngine(bsm_process, "crr", steps)
    elif req.method == "monte_carlo":
        if req.exercise.lower() == "american":
            raise HTTPException(400, "MC pricing for American options not supported. Use binomial.")
        engine = ql.MCEuropeanEngine(
            bsm_process, "pseudorandom",
            timeSteps=100,
            requiredSamples=req.mc_paths,
            seed=42,
        )
    else:
        raise HTTPException(400, f"Unknown method: {req.method}")

    option.setPricingEngine(engine)

    result = {
        "price": round(option.NPV(), 6),
        "method": req.method,
        "engine": "QuantLib",
    }

    # Greeks (available for analytic engine)
    try:
        result["delta"] = round(option.delta(), 6)
    except Exception:
        pass
    try:
        result["gamma"] = round(option.gamma(), 6)
    except Exception:
        pass
    try:
        result["vega"] = round(option.vega() / 100, 6)  # per 1% vol change
    except Exception:
        pass
    try:
        result["theta"] = round(option.theta() / 365, 6)  # per day
    except Exception:
        pass
    try:
        result["rho"] = round(option.rho() / 100, 6)  # per 1% rate change
    except Exception:
        pass

    return result


# ── Interest Rate Swap ─────────────────────────────────────────────────────

@router.post("/swap/price")
async def price_swap(req: SwapRequest):
    """
    Price a vanilla interest rate swap using QuantLib.
    Payer swap: pays fixed, receives floating.
    """
    try:
        import QuantLib as ql
    except ImportError:
        raise HTTPException(503, "QuantLib not installed")

    parts = req.evaluation_date.split("-")
    today = ql.Date(int(parts[2]), int(parts[1]), int(parts[0]))
    ql.Settings.instance().evaluationDate = today

    calendar = ql.UnitedStates(ql.UnitedStates.GovernmentBond)
    day_counter = ql.Actual360()

    yield_curve = ql.YieldTermStructureHandle(
        ql.FlatForward(today, req.flat_yield, day_counter)
    )

    index = ql.USDLibor(ql.Period(3, ql.Months), yield_curve)

    swap = ql.MakeVanillaSwap(
        ql.Period(f"{req.tenor_years}Y"),
        index,
        req.fixed_rate,
        ql.Period("2D"),
        nominal=req.notional,
    )

    engine = ql.DiscountingSwapEngine(yield_curve)
    swap.setPricingEngine(engine)

    return {
        "npv": round(swap.NPV(), 2),
        "fair_rate": round(swap.fairRate(), 6),
        "fair_spread": round(swap.fairSpread(), 6),
        "fixed_leg_npv": round(swap.fixedLegNPV(), 2),
        "floating_leg_npv": round(swap.floatingLegNPV(), 2),
        "fixed_leg_bps": round(swap.fixedLegBPS(), 2),
        "engine": "QuantLib DiscountingSwapEngine",
    }


# ── Implied Volatility Surface ─────────────────────────────────────────────

@router.post("/option/implied-vol")
async def implied_volatility(
    spot: float = Query(100.0),
    market_price: float = Query(10.0),
    strike: float = Query(100.0),
    risk_free_rate: float = Query(0.05),
    maturity_years: float = Query(1.0),
    option_type: str = Query("call"),
):
    """
    Calculate implied volatility from a market option price using QuantLib.
    """
    try:
        import QuantLib as ql
    except ImportError:
        raise HTTPException(503, "QuantLib not installed")

    today = ql.Date(6, 10, 2026)
    ql.Settings.instance().evaluationDate = today
    day_counter = ql.Actual365Fixed()
    calendar = ql.UnitedStates(ql.UnitedStates.NYSE)

    maturity_date = calendar.advance(
        today, ql.Period(int(maturity_years * 365), ql.Days)
    )
    opt_type = ql.Option.Call if option_type == "call" else ql.Option.Put
    payoff = ql.PlainVanillaPayoff(opt_type, strike)
    exercise = ql.EuropeanExercise(maturity_date)
    option = ql.VanillaOption(payoff, exercise)

    spot_handle = ql.QuoteHandle(ql.SimpleQuote(spot))
    rate_handle = ql.YieldTermStructureHandle(
        ql.FlatForward(today, risk_free_rate, day_counter)
    )
    dividend_handle = ql.YieldTermStructureHandle(
        ql.FlatForward(today, 0.0, day_counter)
    )
    vol_handle = ql.BlackVolTermStructureHandle(
        ql.BlackConstantVol(today, calendar, 0.2, day_counter)
    )

    process = ql.BlackScholesMertonProcess(
        spot_handle, dividend_handle, rate_handle, vol_handle
    )

    try:
        implied_vol = option.impliedVolatility(market_price, process)
        return {
            "implied_volatility": round(implied_vol, 6),
            "market_price": market_price,
            "engine": "QuantLib",
        }
    except Exception as e:
        raise HTTPException(400, f"Could not compute implied vol: {str(e)}")
