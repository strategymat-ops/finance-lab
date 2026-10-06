// ============================================================================
// Finance Lab — Multi-Asset Market Engine
// ============================================================================
// Manages multiple order books and handles cross-asset operations,
// market microstructure, and aggregate statistics.
// ============================================================================

use pyo3::prelude::*;
use std::collections::HashMap;
use crate::orderbook::OrderBook;

/// Описание актива
#[pyclass]
#[derive(Clone, Debug)]
pub struct Asset {
    #[pyo3(get)]
    pub symbol: String,
    #[pyo3(get)]
    pub name: String,
    #[pyo3(get)]
    pub asset_type: String,  // "equity", "bond", "commodity", "currency", "derivative", "synthetic"
    #[pyo3(get)]
    pub initial_price: f64,
    #[pyo3(get)]
    pub tick_size: f64,
    #[pyo3(get)]
    pub lot_size: f64,
}

#[pymethods]
impl Asset {
    #[new]
    #[pyo3(signature = (symbol, name, asset_type, initial_price, tick_size=0.01, lot_size=1.0))]
    fn new(
        symbol: String,
        name: String,
        asset_type: String,
        initial_price: f64,
        tick_size: f64,
        lot_size: f64,
    ) -> Self {
        Asset {
            symbol,
            name,
            asset_type,
            initial_price,
            tick_size,
            lot_size,
        }
    }

    fn __repr__(&self) -> String {
        format!(
            "Asset({} '{}' type={} price={:.2})",
            self.symbol, self.name, self.asset_type, self.initial_price
        )
    }
}

/// Multi-Asset Market Engine
///
/// Управляет множественными книгами ордеров и агрегирует рыночные данные.
/// Поддерживает: акции, облигации, деривативы, синтетические активы,
/// кастомные экспериментальные инструменты.
#[pyclass]
pub struct MarketEngine {
    /// Книги ордеров по символам
    orderbooks: HashMap<String, OrderBook>,
    /// Метаданные активов
    assets: HashMap<String, Asset>,
    /// Глобальный тик
    global_tick: u64,
    /// Статистика: объём торгов по активам
    volume_history: HashMap<String, Vec<f64>>,
    /// Статистика: цены по активам
    price_history: HashMap<String, Vec<f64>>,
}

#[pymethods]
impl MarketEngine {
    #[new]
    fn new() -> Self {
        MarketEngine {
            orderbooks: HashMap::new(),
            assets: HashMap::new(),
            global_tick: 0,
            volume_history: HashMap::new(),
            price_history: HashMap::new(),
        }
    }

    /// Зарегистрировать новый актив и создать книгу ордеров
    fn register_asset(&mut self, asset: Asset) -> bool {
        if self.assets.contains_key(&asset.symbol) {
            return false;
        }
        let symbol = asset.symbol.clone();
        self.orderbooks.insert(symbol.clone(), OrderBook::new(symbol.clone()));
        self.volume_history.insert(symbol.clone(), Vec::new());
        self.price_history.insert(symbol.clone(), vec![asset.initial_price]);
        self.assets.insert(symbol, asset);
        true
    }

    /// Подать лимитный ордер на актив
    fn submit_order(
        &mut self,
        symbol: &str,
        price: f64,
        quantity: f64,
        side: &str,
        agent_id: &str,
    ) -> Vec<crate::orderbook::Trade> {
        if let Some(ob) = self.orderbooks.get_mut(symbol) {
            ob.submit_limit_order(price, quantity, side, agent_id)
        } else {
            Vec::new()
        }
    }

    /// Подать рыночный ордер
    fn submit_market_order(
        &mut self,
        symbol: &str,
        quantity: f64,
        side: &str,
        agent_id: &str,
    ) -> Vec<crate::orderbook::Trade> {
        if let Some(ob) = self.orderbooks.get_mut(symbol) {
            ob.submit_market_order(quantity, side, agent_id)
        } else {
            Vec::new()
        }
    }

    /// Получить текущую цену актива
    fn get_price(&self, symbol: &str) -> Option<f64> {
        self.orderbooks.get(symbol).and_then(|ob| ob.mid_price())
    }

    /// Получить снимок книги ордеров
    fn get_orderbook_snapshot(&self, symbol: &str) -> PyResult<Option<pyo3::Py<pyo3::types::PyDict>>> {
        if let Some(ob) = self.orderbooks.get(symbol) {
            Ok(Some(ob.snapshot()?))
        } else {
            Ok(None)
        }
    }

    /// Список всех активов
    fn list_assets(&self) -> Vec<Asset> {
        self.assets.values().cloned().collect()
    }

    /// Количество зарегистрированных активов
    fn num_assets(&self) -> usize {
        self.assets.len()
    }

    /// Продвинуть время на один тик для всех книг
    fn advance_tick(&mut self) {
        self.global_tick += 1;
        for (symbol, ob) in self.orderbooks.iter_mut() {
            ob.advance_tick();

            // Записываем текущую цену в историю
            if let Some(price) = ob.mid_price() {
                if let Some(hist) = self.price_history.get_mut(symbol) {
                    hist.push(price);
                }
            }
        }
    }

    /// Получить историю цен актива
    fn get_price_history(&self, symbol: &str) -> Vec<f64> {
        self.price_history
            .get(symbol)
            .cloned()
            .unwrap_or_default()
    }

    /// Текущий тик
    fn current_tick(&self) -> u64 {
        self.global_tick
    }

    /// Полный снимок рынка
    fn market_snapshot(&self) -> PyResult<pyo3::Py<pyo3::types::PyDict>> {
        Python::with_gil(|py| {
            let dict = pyo3::types::PyDict::new(py);
            dict.set_item("tick", self.global_tick)?;
            dict.set_item("num_assets", self.assets.len())?;

            let assets_dict = pyo3::types::PyDict::new(py);
            for (symbol, ob) in &self.orderbooks {
                let asset_info = pyo3::types::PyDict::new(py);
                asset_info.set_item("mid_price", ob.mid_price())?;
                asset_info.set_item("best_bid", ob.best_bid())?;
                asset_info.set_item("best_ask", ob.best_ask())?;
                asset_info.set_item("spread", ob.spread())?;
                asset_info.set_item("trade_count", ob.trade_count())?;
                asset_info.set_item("bid_volume", ob.total_bid_volume())?;
                asset_info.set_item("ask_volume", ob.total_ask_volume())?;
                assets_dict.set_item(symbol.as_str(), asset_info)?;
            }
            dict.set_item("assets", assets_dict)?;

            Ok(dict.into())
        })
    }

    /// Сброс всех книг ордеров
    fn reset(&mut self) {
        self.global_tick = 0;
        for ob in self.orderbooks.values_mut() {
            ob.clear();
        }
        for hist in self.price_history.values_mut() {
            hist.clear();
        }
        for hist in self.volume_history.values_mut() {
            hist.clear();
        }
    }

    fn __repr__(&self) -> String {
        format!(
            "MarketEngine(assets={}, tick={})",
            self.assets.len(),
            self.global_tick
        )
    }
}
