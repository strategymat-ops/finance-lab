// ============================================================================
// Finance Lab — Monte Carlo Simulation Engine
// ============================================================================
// Parallel Monte Carlo engine for pricing, risk analysis, and stochastic
// process simulation. Uses Rayon for multi-threaded execution.
// ============================================================================

use pyo3::prelude::*;
use rand::prelude::*;
use rand_distr::{Normal, LogNormal, Distribution};
use rayon::prelude::*;

/// Результат Monte Carlo симуляции
#[pyclass]
#[derive(Clone, Debug)]
pub struct SimulationResult {
    #[pyo3(get)]
    pub mean: f64,
    #[pyo3(get)]
    pub std_dev: f64,
    #[pyo3(get)]
    pub median: f64,
    #[pyo3(get)]
    pub percentile_5: f64,
    #[pyo3(get)]
    pub percentile_95: f64,
    #[pyo3(get)]
    pub min_val: f64,
    #[pyo3(get)]
    pub max_val: f64,
    #[pyo3(get)]
    pub var_95: f64,
    #[pyo3(get)]
    pub cvar_95: f64,
    #[pyo3(get)]
    pub num_paths: usize,
    #[pyo3(get)]
    pub paths: Vec<Vec<f64>>,
}

#[pymethods]
impl SimulationResult {
    fn __repr__(&self) -> String {
        format!(
            "SimResult(mean={:.4}, std={:.4}, VaR95={:.4}, paths={})",
            self.mean, self.std_dev, self.var_95, self.num_paths
        )
    }

    /// Вернуть все значения как словарь
    fn to_dict(&self) -> PyResult<pyo3::Py<pyo3::types::PyDict>> {
        Python::with_gil(|py| {
            let dict = pyo3::types::PyDict::new(py);
            dict.set_item("mean", self.mean)?;
            dict.set_item("std_dev", self.std_dev)?;
            dict.set_item("median", self.median)?;
            dict.set_item("percentile_5", self.percentile_5)?;
            dict.set_item("percentile_95", self.percentile_95)?;
            dict.set_item("min", self.min_val)?;
            dict.set_item("max", self.max_val)?;
            dict.set_item("var_95", self.var_95)?;
            dict.set_item("cvar_95", self.cvar_95)?;
            dict.set_item("num_paths", self.num_paths)?;
            Ok(dict.into())
        })
    }
}

/// Monte Carlo Simulation Engine
///
/// Высокопроизводительный движок для:
/// - Геометрическое броуновское движение (GBM)
/// - Модель Хестона (стохастическая волатильность)
/// - Процесс Орнштейна-Уленбека (mean-reverting)
/// - VaR/CVaR расчёты
/// - Ценообразование опционов
#[pyclass]
pub struct MonteCarloEngine {
    num_threads: usize,
    seed: u64,
}

#[pymethods]
impl MonteCarloEngine {
    #[new]
    #[pyo3(signature = (num_threads=0, seed=42))]
    fn new(num_threads: usize, seed: u64) -> Self {
        if num_threads > 0 {
            rayon::ThreadPoolBuilder::new()
                .num_threads(num_threads)
                .build_global()
                .ok();
        }
        MonteCarloEngine { num_threads, seed }
    }

    /// Geometric Brownian Motion (GBM)
    /// S(t+dt) = S(t) * exp((mu - sigma²/2)*dt + sigma*sqrt(dt)*Z)
    ///
    /// Используется для моделирования цен акций, валют, активов
    fn simulate_gbm(
        &self,
        s0: f64,           // начальная цена
        mu: f64,           // drift (ожидаемая доходность)
        sigma: f64,        // волатильность
        t: f64,            // время (в годах)
        num_steps: usize,  // количество временных шагов
        num_paths: usize,  // количество траекторий
        store_paths: bool, // сохранять ли полные пути
    ) -> SimulationResult {
        let dt = t / num_steps as f64;
        let drift = (mu - 0.5 * sigma * sigma) * dt;
        let diffusion = sigma * dt.sqrt();

        let results: Vec<(f64, Option<Vec<f64>>)> = (0..num_paths)
            .into_par_iter()
            .map(|i| {
                let mut rng = StdRng::seed_from_u64(self.seed + i as u64);
                let normal = Normal::new(0.0, 1.0).unwrap();
                let mut s = s0;
                let mut path = if store_paths {
                    vec![s]
                } else {
                    Vec::new()
                };

                for _ in 0..num_steps {
                    let z: f64 = normal.sample(&mut rng);
                    s *= (drift + diffusion * z).exp();
                    if store_paths {
                        path.push(s);
                    }
                }

                (s, if store_paths { Some(path) } else { None })
            })
            .collect();

        let mut final_values: Vec<f64> = results.iter().map(|(v, _)| *v).collect();
        let paths: Vec<Vec<f64>> = if store_paths {
            results.iter().filter_map(|(_, p)| p.clone()).collect()
        } else {
            Vec::new()
        };

        Self::compute_statistics(final_values, paths, num_paths)
    }

    /// Heston Stochastic Volatility Model
    /// dS = mu*S*dt + sqrt(V)*S*dW1
    /// dV = kappa*(theta - V)*dt + xi*sqrt(V)*dW2
    /// corr(dW1, dW2) = rho
    fn simulate_heston(
        &self,
        s0: f64,           // начальная цена
        v0: f64,           // начальная волатильность²
        mu: f64,           // drift
        kappa: f64,        // скорость возврата к среднему
        theta: f64,        // долгосрочный уровень волатильности
        xi: f64,           // vol of vol
        rho: f64,          // корреляция
        t: f64,
        num_steps: usize,
        num_paths: usize,
        store_paths: bool,
    ) -> SimulationResult {
        let dt = t / num_steps as f64;

        let results: Vec<(f64, Option<Vec<f64>>)> = (0..num_paths)
            .into_par_iter()
            .map(|i| {
                let mut rng = StdRng::seed_from_u64(self.seed + i as u64);
                let normal = Normal::new(0.0, 1.0).unwrap();
                let mut s = s0;
                let mut v = v0;
                let mut path = if store_paths { vec![s] } else { Vec::new() };

                for _ in 0..num_steps {
                    let z1: f64 = normal.sample(&mut rng);
                    let z2: f64 = rho * z1 + (1.0 - rho * rho).sqrt() * normal.sample(&mut rng);

                    let v_pos = v.max(0.0);
                    let sqrt_v = v_pos.sqrt();

                    s *= (mu * dt + sqrt_v * dt.sqrt() * z1).exp();
                    v += kappa * (theta - v_pos) * dt + xi * sqrt_v * dt.sqrt() * z2;
                    v = v.max(0.0); // ensure non-negative

                    if store_paths {
                        path.push(s);
                    }
                }

                (s, if store_paths { Some(path) } else { None })
            })
            .collect();

        let final_values: Vec<f64> = results.iter().map(|(v, _)| *v).collect();
        let paths: Vec<Vec<f64>> = if store_paths {
            results.iter().filter_map(|(_, p)| p.clone()).collect()
        } else {
            Vec::new()
        };

        Self::compute_statistics(final_values, paths, num_paths)
    }

    /// Ornstein-Uhlenbeck Process (Mean-Reverting)
    /// dX = theta*(mu - X)*dt + sigma*dW
    ///
    /// Используется для моделирования процентных ставок (Vasicek model)
    fn simulate_ou(
        &self,
        x0: f64,           // начальное значение
        mu: f64,           // долгосрочное среднее
        theta: f64,        // скорость возврата
        sigma: f64,        // волатильность
        t: f64,
        num_steps: usize,
        num_paths: usize,
        store_paths: bool,
    ) -> SimulationResult {
        let dt = t / num_steps as f64;

        let results: Vec<(f64, Option<Vec<f64>>)> = (0..num_paths)
            .into_par_iter()
            .map(|i| {
                let mut rng = StdRng::seed_from_u64(self.seed + i as u64);
                let normal = Normal::new(0.0, 1.0).unwrap();
                let mut x = x0;
                let mut path = if store_paths { vec![x] } else { Vec::new() };

                for _ in 0..num_steps {
                    let z: f64 = normal.sample(&mut rng);
                    x += theta * (mu - x) * dt + sigma * dt.sqrt() * z;
                    if store_paths {
                        path.push(x);
                    }
                }

                (x, if store_paths { Some(path) } else { None })
            })
            .collect();

        let final_values: Vec<f64> = results.iter().map(|(v, _)| *v).collect();
        let paths: Vec<Vec<f64>> = if store_paths {
            results.iter().filter_map(|(_, p)| p.clone()).collect()
        } else {
            Vec::new()
        };

        Self::compute_statistics(final_values, paths, num_paths)
    }

    /// Ценообразование European Call Option через Monte Carlo
    fn price_european_call(
        &self,
        s0: f64,           // текущая цена базового актива
        strike: f64,       // цена исполнения
        r: f64,            // безрисковая ставка
        sigma: f64,        // волатильность
        t: f64,            // время до экспирации
        num_paths: usize,
    ) -> f64 {
        let payoffs: Vec<f64> = (0..num_paths)
            .into_par_iter()
            .map(|i| {
                let mut rng = StdRng::seed_from_u64(self.seed + i as u64);
                let normal = Normal::new(0.0, 1.0).unwrap();
                let z: f64 = normal.sample(&mut rng);
                let st = s0 * ((r - 0.5 * sigma * sigma) * t + sigma * t.sqrt() * z).exp();
                (st - strike).max(0.0)
            })
            .collect();

        let mean_payoff: f64 = payoffs.iter().sum::<f64>() / num_paths as f64;
        (-r * t).exp() * mean_payoff
    }

    /// Ценообразование European Put Option через Monte Carlo
    fn price_european_put(
        &self,
        s0: f64,
        strike: f64,
        r: f64,
        sigma: f64,
        t: f64,
        num_paths: usize,
    ) -> f64 {
        let payoffs: Vec<f64> = (0..num_paths)
            .into_par_iter()
            .map(|i| {
                let mut rng = StdRng::seed_from_u64(self.seed + i as u64);
                let normal = Normal::new(0.0, 1.0).unwrap();
                let z: f64 = normal.sample(&mut rng);
                let st = s0 * ((r - 0.5 * sigma * sigma) * t + sigma * t.sqrt() * z).exp();
                (strike - st).max(0.0)
            })
            .collect();

        let mean_payoff: f64 = payoffs.iter().sum::<f64>() / num_paths as f64;
        (-r * t).exp() * mean_payoff
    }

    /// Симуляция портфеля с VaR/CVaR
    fn portfolio_risk(
        &self,
        weights: Vec<f64>,        // веса активов
        returns_mean: Vec<f64>,   // ожидаемые доходности
        returns_std: Vec<f64>,    // стандартные отклонения
        correlations: Vec<f64>,   // матрица корреляций (flattened)
        horizon_days: usize,      // горизонт (в днях)
        num_paths: usize,
        confidence: f64,          // уровень VaR (напр. 0.95)
    ) -> SimulationResult {
        let n_assets = weights.len();
        let dt = horizon_days as f64 / 252.0;

        let portfolio_returns: Vec<f64> = (0..num_paths)
            .into_par_iter()
            .map(|i| {
                let mut rng = StdRng::seed_from_u64(self.seed + i as u64);
                let normal = Normal::new(0.0, 1.0).unwrap();

                // Генерируем доходности для каждого актива
                let mut portfolio_return = 0.0;
                for j in 0..n_assets {
                    let z: f64 = normal.sample(&mut rng);
                    let asset_return = returns_mean[j] * dt + returns_std[j] * dt.sqrt() * z;
                    portfolio_return += weights[j] * asset_return;
                }
                portfolio_return
            })
            .collect();

        Self::compute_statistics(portfolio_returns, Vec::new(), num_paths)
    }

    fn __repr__(&self) -> String {
        format!("MonteCarloEngine(threads={}, seed={})", self.num_threads, self.seed)
    }
}

impl MonteCarloEngine {
    fn compute_statistics(
        mut values: Vec<f64>,
        paths: Vec<Vec<f64>>,
        num_paths: usize,
    ) -> SimulationResult {
        values.sort_by(|a, b| a.partial_cmp(b).unwrap());

        let n = values.len();
        let mean: f64 = values.iter().sum::<f64>() / n as f64;
        let variance: f64 = values.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / n as f64;
        let std_dev = variance.sqrt();

        let median = if n % 2 == 0 {
            (values[n / 2 - 1] + values[n / 2]) / 2.0
        } else {
            values[n / 2]
        };

        let p5_idx = ((n as f64) * 0.05) as usize;
        let p95_idx = ((n as f64) * 0.95) as usize;
        let percentile_5 = values[p5_idx.min(n - 1)];
        let percentile_95 = values[p95_idx.min(n - 1)];

        // VaR (95%) — потеря на уровне 5-го перцентиля
        let var_95 = -percentile_5;

        // CVaR (95%) — среднее потерь ниже VaR
        let cvar_values: Vec<f64> = values[..=p5_idx.min(n - 1)].to_vec();
        let cvar_95 = if !cvar_values.is_empty() {
            -(cvar_values.iter().sum::<f64>() / cvar_values.len() as f64)
        } else {
            var_95
        };

        SimulationResult {
            mean,
            std_dev,
            median,
            percentile_5,
            percentile_95,
            min_val: values[0],
            max_val: values[n - 1],
            var_95,
            cvar_95,
            num_paths,
            paths,
        }
    }
}
