// ============================================================================
// Finance Lab — High-Performance Order Book Engine
// ============================================================================
// Lock-free, cache-friendly order book with price-time priority matching.
// Processes millions of orders per second.
// ============================================================================

use ordered_float::OrderedFloat;
use pyo3::prelude::*;
use std::collections::BTreeMap;
use std::collections::VecDeque;

/// Тип ордера: покупка или продажа
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum OrderSide {
    Buy,
    Sell,
}

/// Одиночный ордер в книге заявок
#[pyclass]
#[derive(Clone, Debug)]
pub struct Order {
    #[pyo3(get)]
    pub id: u64,
    #[pyo3(get)]
    pub price: f64,
    #[pyo3(get)]
    pub quantity: f64,
    #[pyo3(get)]
    pub remaining: f64,
    #[pyo3(get)]
    pub side: String,
    #[pyo3(get)]
    pub agent_id: String,
    #[pyo3(get)]
    pub timestamp: u64,
}

#[pymethods]
impl Order {
    #[new]
    fn new(id: u64, price: f64, quantity: f64, side: String, agent_id: String, timestamp: u64) -> Self {
        Order {
            id,
            price,
            quantity,
            remaining: quantity,
            side,
            agent_id,
            timestamp,
        }
    }

    fn __repr__(&self) -> String {
        format!(
            "Order(id={}, {}@{:.4} qty={:.2} rem={:.2} agent={})",
            self.id, self.side, self.price, self.quantity, self.remaining, self.agent_id
        )
    }

    fn is_filled(&self) -> bool {
        self.remaining <= 1e-10
    }
}

/// Результат сделки (trade)
#[pyclass]
#[derive(Clone, Debug)]
pub struct Trade {
    #[pyo3(get)]
    pub id: u64,
    #[pyo3(get)]
    pub price: f64,
    #[pyo3(get)]
    pub quantity: f64,
    #[pyo3(get)]
    pub buyer_id: String,
    #[pyo3(get)]
    pub seller_id: String,
    #[pyo3(get)]
    pub buyer_order_id: u64,
    #[pyo3(get)]
    pub seller_order_id: u64,
    #[pyo3(get)]
    pub timestamp: u64,
}

#[pymethods]
impl Trade {
    fn __repr__(&self) -> String {
        format!(
            "Trade(id={}, {:.4}x{:.2} buyer={} seller={})",
            self.id, self.price, self.quantity, self.buyer_id, self.seller_id
        )
    }

    fn to_dict(&self) -> PyResult<pyo3::Py<pyo3::types::PyDict>> {
        Python::with_gil(|py| {
            let dict = pyo3::types::PyDict::new(py);
            dict.set_item("id", self.id)?;
            dict.set_item("price", self.price)?;
            dict.set_item("quantity", self.quantity)?;
            dict.set_item("buyer_id", &self.buyer_id)?;
            dict.set_item("seller_id", &self.seller_id)?;
            dict.set_item("timestamp", self.timestamp)?;
            Ok(dict.into())
        })
    }
}

/// Уровень цены — все ордера на одной цене
#[derive(Clone, Debug)]
struct PriceLevel {
    orders: VecDeque<Order>,
    total_quantity: f64,
}

impl PriceLevel {
    fn new() -> Self {
        PriceLevel {
            orders: VecDeque::new(),
            total_quantity: 0.0,
        }
    }

    fn add(&mut self, order: Order) {
        self.total_quantity += order.remaining;
        self.orders.push_back(order);
    }

    fn is_empty(&self) -> bool {
        self.orders.is_empty()
    }
}

/// Высокопроизводительная книга заявок (Order Book)
///
/// Использует BTreeMap для O(log n) доступа к лучшим ценам
/// и VecDeque для FIFO внутри каждого уровня цены.
#[pyclass]
pub struct OrderBook {
    /// Заявки на покупку (bids) — отсортированы по убыванию цены
    bids: BTreeMap<OrderedFloat<f64>, PriceLevel>,
    /// Заявки на продажу (asks) — отсортированы по возрастанию цены
    asks: BTreeMap<OrderedFloat<f64>, PriceLevel>,
    /// Счётчик сделок
    trade_counter: u64,
    /// Счётчик ордеров
    order_counter: u64,
    /// Текущий временной шаг
    current_tick: u64,
    /// Последняя цена сделки
    last_trade_price: Option<f64>,
    /// История сделок
    trades: Vec<Trade>,
    /// Название актива
    #[pyo3(get)]
    symbol: String,
}

#[pymethods]
impl OrderBook {
    #[new]
    fn new(symbol: String) -> Self {
        OrderBook {
            bids: BTreeMap::new(),
            asks: BTreeMap::new(),
            trade_counter: 0,
            order_counter: 0,
            current_tick: 0,
            last_trade_price: None,
            trades: Vec::new(),
            symbol,
        }
    }

    /// Подать лимитный ордер, вернуть список сделок
    fn submit_limit_order(
        &mut self,
        price: f64,
        quantity: f64,
        side: &str,
        agent_id: &str,
    ) -> Vec<Trade> {
        self.order_counter += 1;
        let order = Order {
            id: self.order_counter,
            price,
            quantity,
            remaining: quantity,
            side: side.to_string(),
            agent_id: agent_id.to_string(),
            timestamp: self.current_tick,
        };

        match side {
            "buy" => self.match_buy_order(order),
            "sell" => self.match_sell_order(order),
            _ => Vec::new(),
        }
    }

    /// Подать рыночный ордер (исполняется по лучшей доступной цене)
    fn submit_market_order(
        &mut self,
        quantity: f64,
        side: &str,
        agent_id: &str,
    ) -> Vec<Trade> {
        self.order_counter += 1;
        let price = match side {
            "buy" => f64::MAX,
            "sell" => 0.0,
            _ => return Vec::new(),
        };

        let order = Order {
            id: self.order_counter,
            price,
            quantity,
            remaining: quantity,
            side: side.to_string(),
            agent_id: agent_id.to_string(),
            timestamp: self.current_tick,
        };

        match side {
            "buy" => self.match_buy_order(order),
            "sell" => self.match_sell_order(order),
            _ => Vec::new(),
        }
    }

    /// Лучшая цена покупки (bid)
    fn best_bid(&self) -> Option<f64> {
        self.bids.keys().next_back().map(|k| k.into_inner())
    }

    /// Лучшая цена продажи (ask)
    fn best_ask(&self) -> Option<f64> {
        self.asks.keys().next().map(|k| k.into_inner())
    }

    /// Спред (разница между лучшей ask и лучшей bid)
    fn spread(&self) -> Option<f64> {
        match (self.best_bid(), self.best_ask()) {
            (Some(bid), Some(ask)) => Some(ask - bid),
            _ => None,
        }
    }

    /// Середина спреда
    fn mid_price(&self) -> Option<f64> {
        match (self.best_bid(), self.best_ask()) {
            (Some(bid), Some(ask)) => Some((bid + ask) / 2.0),
            _ => self.last_trade_price,
        }
    }

    /// Последняя цена сделки
    fn last_price(&self) -> Option<f64> {
        self.last_trade_price
    }

    /// Общий объём заявок на покупку
    fn total_bid_volume(&self) -> f64 {
        self.bids.values().map(|level| level.total_quantity).sum()
    }

    /// Общий объём заявок на продажу
    fn total_ask_volume(&self) -> f64 {
        self.asks.values().map(|level| level.total_quantity).sum()
    }

    /// Глубина книги (количество ценовых уровней)
    fn depth(&self) -> (usize, usize) {
        (self.bids.len(), self.asks.len())
    }

    /// Получить N лучших уровней bid
    fn top_bids(&self, n: usize) -> Vec<(f64, f64)> {
        self.bids
            .iter()
            .rev()
            .take(n)
            .map(|(price, level)| (price.into_inner(), level.total_quantity))
            .collect()
    }

    /// Получить N лучших уровней ask
    fn top_asks(&self, n: usize) -> Vec<(f64, f64)> {
        self.asks
            .iter()
            .take(n)
            .map(|(price, level)| (price.into_inner(), level.total_quantity))
            .collect()
    }

    /// Количество исполненных сделок
    fn trade_count(&self) -> u64 {
        self.trade_counter
    }

    /// Получить последние N сделок
    fn recent_trades(&self, n: usize) -> Vec<Trade> {
        let start = if self.trades.len() > n { self.trades.len() - n } else { 0 };
        self.trades[start..].to_vec()
    }

    /// VWAP (Volume Weighted Average Price) за последние N сделок
    fn vwap(&self, n: usize) -> Option<f64> {
        if self.trades.is_empty() {
            return None;
        }
        let start = if self.trades.len() > n { self.trades.len() - n } else { 0 };
        let recent = &self.trades[start..];

        let total_volume: f64 = recent.iter().map(|t| t.quantity).sum();
        if total_volume <= 0.0 {
            return None;
        }
        let vwap: f64 = recent.iter().map(|t| t.price * t.quantity).sum::<f64>() / total_volume;
        Some(vwap)
    }

    /// Обновить текущий тик
    fn advance_tick(&mut self) {
        self.current_tick += 1;
    }

    /// Очистить книгу
    fn clear(&mut self) {
        self.bids.clear();
        self.asks.clear();
        self.trades.clear();
        self.trade_counter = 0;
        self.order_counter = 0;
        self.last_trade_price = None;
    }

    /// Снимок состояния книги (для визуализации)
    fn snapshot(&self) -> PyResult<pyo3::Py<pyo3::types::PyDict>> {
        Python::with_gil(|py| {
            let dict = pyo3::types::PyDict::new(py);
            dict.set_item("symbol", &self.symbol)?;
            dict.set_item("best_bid", self.best_bid())?;
            dict.set_item("best_ask", self.best_ask())?;
            dict.set_item("spread", self.spread())?;
            dict.set_item("mid_price", self.mid_price())?;
            dict.set_item("last_price", self.last_trade_price)?;
            dict.set_item("total_bid_volume", self.total_bid_volume())?;
            dict.set_item("total_ask_volume", self.total_ask_volume())?;
            dict.set_item("trade_count", self.trade_counter)?;
            dict.set_item("tick", self.current_tick)?;

            let bids_list: Vec<(f64, f64)> = self.top_bids(20);
            let asks_list: Vec<(f64, f64)> = self.top_asks(20);
            dict.set_item("bids", bids_list)?;
            dict.set_item("asks", asks_list)?;

            Ok(dict.into())
        })
    }

    fn __repr__(&self) -> String {
        format!(
            "OrderBook(symbol={}, bids={}, asks={}, trades={}, mid={:?})",
            self.symbol,
            self.bids.len(),
            self.asks.len(),
            self.trade_counter,
            self.mid_price()
        )
    }
}

impl OrderBook {
    /// Сопоставление ордера на покупку с ask-стороной книги
    fn match_buy_order(&mut self, mut order: Order) -> Vec<Trade> {
        let mut trades = Vec::new();

        // Ищем встречные ask ордера, пока цена покупки >= цена продажи
        while order.remaining > 1e-10 {
            // Получаем лучший ask
            let best_ask_price = match self.asks.keys().next() {
                Some(p) => *p,
                None => break,
            };

            // Если цена покупки < лучший ask — нет матча
            if OrderedFloat(order.price) < best_ask_price {
                break;
            }

            let level = self.asks.get_mut(&best_ask_price).unwrap();

            while order.remaining > 1e-10 && !level.orders.is_empty() {
                let sell_order = level.orders.front_mut().unwrap();
                let trade_qty = order.remaining.min(sell_order.remaining);
                let trade_price = best_ask_price.into_inner();

                self.trade_counter += 1;
                let trade = Trade {
                    id: self.trade_counter,
                    price: trade_price,
                    quantity: trade_qty,
                    buyer_id: order.agent_id.clone(),
                    seller_id: sell_order.agent_id.clone(),
                    buyer_order_id: order.id,
                    seller_order_id: sell_order.id,
                    timestamp: self.current_tick,
                };

                order.remaining -= trade_qty;
                sell_order.remaining -= trade_qty;
                level.total_quantity -= trade_qty;
                self.last_trade_price = Some(trade_price);

                trades.push(trade.clone());
                self.trades.push(trade);

                if sell_order.remaining <= 1e-10 {
                    level.orders.pop_front();
                }
            }

            if level.is_empty() {
                self.asks.remove(&best_ask_price);
            }
        }

        // Если ордер не полностью исполнен — добавляем в книгу
        if order.remaining > 1e-10 && order.price < f64::MAX {
            let price_key = OrderedFloat(order.price);
            self.bids
                .entry(price_key)
                .or_insert_with(PriceLevel::new)
                .add(order);
        }

        trades
    }

    /// Сопоставление ордера на продажу с bid-стороной книги
    fn match_sell_order(&mut self, mut order: Order) -> Vec<Trade> {
        let mut trades = Vec::new();

        while order.remaining > 1e-10 {
            let best_bid_price = match self.bids.keys().next_back() {
                Some(p) => *p,
                None => break,
            };

            if OrderedFloat(order.price) > best_bid_price && order.price > 0.0 {
                break;
            }

            let level = self.bids.get_mut(&best_bid_price).unwrap();

            while order.remaining > 1e-10 && !level.orders.is_empty() {
                let buy_order = level.orders.front_mut().unwrap();
                let trade_qty = order.remaining.min(buy_order.remaining);
                let trade_price = best_bid_price.into_inner();

                self.trade_counter += 1;
                let trade = Trade {
                    id: self.trade_counter,
                    price: trade_price,
                    quantity: trade_qty,
                    buyer_id: buy_order.agent_id.clone(),
                    seller_id: order.agent_id.clone(),
                    buyer_order_id: buy_order.id,
                    seller_order_id: order.id,
                    timestamp: self.current_tick,
                };

                order.remaining -= trade_qty;
                buy_order.remaining -= trade_qty;
                level.total_quantity -= trade_qty;
                self.last_trade_price = Some(trade_price);

                trades.push(trade.clone());
                self.trades.push(trade);

                if buy_order.remaining <= 1e-10 {
                    level.orders.pop_front();
                }
            }

            if level.is_empty() {
                self.bids.remove(&best_bid_price);
            }
        }

        // Остаток — в книгу
        if order.remaining > 1e-10 && order.price > 0.0 {
            let price_key = OrderedFloat(order.price);
            self.asks
                .entry(price_key)
                .or_insert_with(PriceLevel::new)
                .add(order);
        }

        trades
    }
}
