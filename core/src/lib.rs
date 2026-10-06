// ============================================================================
// Finance Lab — Rust Core: PyO3 Module Root
// ============================================================================
// High-performance computation primitives exposed to Python.
// These are TOOLS, not models — the economic models live in Python
// using professional frameworks (Econpizza, HARK, QuantLib, etc.)
// ============================================================================

use pyo3::prelude::*;

mod orderbook;
mod monte_carlo;
mod market_engine;

/// Finance Lab Core — вычислительные примитивы
///
/// Это НЕ экономические модели. Это инфраструктура:
/// - Order Book: matching engine для рыночных экспериментов
/// - Monte Carlo: параллельные стохастические симуляции
/// - Market Engine: multi-asset matching и агрегация
///
/// Экономическая логика — в Python через:
/// - econpizza (DSGE)
/// - HARK / econ-ark (heterogeneous agents)
/// - gEconpy (optimization-based DSGE)
/// - QuantLib (derivatives, yield curves)
/// - pyfrbus (FRB/US model)
#[pymodule]
fn finlab_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Order Book Engine — matching engine for market experiments
    m.add_class::<orderbook::OrderBook>()?;
    m.add_class::<orderbook::Order>()?;
    m.add_class::<orderbook::Trade>()?;

    // Monte Carlo Engine — parallel stochastic simulations
    m.add_class::<monte_carlo::MonteCarloEngine>()?;
    m.add_class::<monte_carlo::SimulationResult>()?;

    // Market Engine — multi-asset coordination
    m.add_class::<market_engine::MarketEngine>()?;
    m.add_class::<market_engine::Asset>()?;

    Ok(())
}
