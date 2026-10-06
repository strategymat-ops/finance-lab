/**
 * Finance Lab — Interactive Frontend Application Logic
 * Integrates Chart.js, FastAPI REST APIs, and WebSocket telemetry stream.
 */

// ── Chart Registry ────────────────────────────────────────────────────────
let yieldCurveChart = null;
let experimentChart = null;
let ammChart = null;
let aiPricingChart = null;
let systemicChart = null;

// ── Tab Navigation ─────────────────────────────────────────────────────────
function switchTab(tabId) {
  document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.classList.toggle('active', tab.dataset.tab === tabId);
  });
  document.querySelectorAll('.tab-content').forEach(content => {
    content.classList.toggle('active', content.id === tabId);
  });

  // Re-render chart sizing on tab reveal
  window.dispatchEvent(new Event('resize'));
}

// ── Copy Snippet ──────────────────────────────────────────────────────────
function copyCode(btn) {
  const code = btn.parentElement.querySelector('code').innerText;
  navigator.clipboard.writeText(code).then(() => {
    const orig = btn.innerText;
    btn.innerText = 'Скопировано!';
    setTimeout(() => btn.innerText = orig, 1800);
  });
}

// ── 1. Fed Policy & Yield Curve ───────────────────────────────────────────
function updateFedCalc() {
  const pi = parseFloat(document.getElementById('fed-inflation').value);
  const y = parseFloat(document.getElementById('fed-outputgap').value);
  const pi_star = parseFloat(document.getElementById('fed-target-inf').value);
  const r_star = parseFloat(document.getElementById('fed-rstar').value);

  document.getElementById('fed-inflation-val').innerText = `${pi.toFixed(1)}%`;
  document.getElementById('fed-outputgap-val').innerText = `${y.toFixed(1)}%`;
  document.getElementById('fed-target-inf-val').innerText = `${pi_star.toFixed(1)}%`;
  document.getElementById('fed-rstar-val').innerText = `${r_star.toFixed(2)}%`;

  // Standard Taylor Rule: i = r* + pi + 0.5(pi - pi*) + 0.5(y)
  const rate = Math.max(0.0, r_star + pi + 0.5 * (pi - pi_star) + 0.5 * y);
  document.getElementById('calc-taylor-rate').innerText = `${rate.toFixed(2)}%`;
}

async function simulateFedPolicy() {
  updateFedCalc();
  await loadYieldCurve();
}

async function loadYieldCurve() {
  try {
    const res = await fetch('/api/fed/yield-curve');
    const data = await res.json();
    const maturities = data.maturities;
    const rates = data.rates;

    const ctx = document.getElementById('chart-yield-curve').getContext('2d');
    if (yieldCurveChart) yieldCurveChart.destroy();

    yieldCurveChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: maturities,
        datasets: [{
          label: 'US Treasury Yield Curve (QuantLib Nelson-Siegel)',
          data: rates,
          borderColor: '#38bdf8',
          backgroundColor: 'rgba(56, 189, 248, 0.1)',
          fill: true,
          tension: 0.35,
          pointBackgroundColor: '#38bdf8',
          pointRadius: 5,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: {
            title: { display: true, text: 'Yield (%)', color: '#94a3b8' },
            grid: { color: 'rgba(255, 255, 255, 0.06)' },
            ticks: { color: '#94a3b8' }
          },
          x: {
            title: { display: true, text: 'Maturity Horizon', color: '#94a3b8' },
            grid: { color: 'rgba(255, 255, 255, 0.06)' },
            ticks: { color: '#94a3b8' }
          }
        },
        plugins: {
          legend: { labels: { color: '#f1f5f9' } }
        }
      }
    });
  } catch (e) {
    console.warn('Yield curve API fallback to baseline model:', e);
    renderFallbackYieldCurve();
  }
}

function renderFallbackYieldCurve() {
  const ctx = document.getElementById('chart-yield-curve').getContext('2d');
  if (yieldCurveChart) yieldCurveChart.destroy();
  yieldCurveChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: ['1M', '3M', '6M', '1Y', '2Y', '5Y', '10Y', '30Y'],
      datasets: [{
        label: 'US Treasury Yield Curve (Par Yields %)',
        data: [5.38, 5.25, 4.95, 4.45, 3.98, 4.02, 4.25, 4.52],
        borderColor: '#38bdf8',
        backgroundColor: 'rgba(56, 189, 248, 0.1)',
        fill: true,
        tension: 0.35,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: '#f1f5f9' } } }
    }
  });
}

// ── 2. New Economic Relations Experiments ─────────────────────────────────
function toggleExpInputs() {
  const type = document.getElementById('exp-type-select').value;
  const cbdcBox = document.getElementById('cbdc-controls');
  cbdcBox.style.display = (type === 'programmable_cbdc') ? 'block' : 'none';
}

async function runLaboratoryExperiment() {
  const expType = document.getElementById('exp-type-select').value;
  let params = {};

  if (expType === 'programmable_cbdc') {
    params = {
      cbdc_interest_rate: parseFloat(document.getElementById('cbdc-demurrage').value) / 100.0,
      bank_deposit_rate: parseFloat(document.getElementById('cbdc-bank-rate').value) / 100.0,
      demurrage_enabled: true,
    };
  }

  try {
    const res = await fetch('/api/experiments/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        experiment_type: expType,
        name: `Run-${Date.now()}`,
        horizon_quarters: 20,
        parameters: params,
      })
    });
    const data = await res.json();

    // Render findings
    const list = document.getElementById('findings-list');
    list.innerHTML = '';
    data.economic_findings.forEach(f => {
      const li = document.createElement('li');
      li.innerText = f;
      list.appendChild(li);
    });

    renderExperimentChart(data.metrics, expType);
  } catch (e) {
    console.error('Experiment run error:', e);
  }
}

function renderExperimentChart(metrics, type) {
  const ctx = document.getElementById('chart-experiment').getContext('2d');
  if (experimentChart) experimentChart.destroy();

  const quarters = Array.from({ length: 20 }, (_, i) => `Q${i + 1}`);
  let datasets = [];

  if (type === 'programmable_cbdc') {
    datasets = [
      {
        label: 'Скорость обращения (Money Velocity)',
        data: metrics.money_velocity,
        borderColor: '#a855f7',
        yAxisID: 'y1',
      },
      {
        label: 'Депозиты банков ($ млрд)',
        data: metrics.commercial_bank_deposits,
        borderColor: '#38bdf8',
        yAxisID: 'y',
      },
      {
        label: 'CBDC в обращении ($ млрд)',
        data: metrics.cbdc_circulation,
        borderColor: '#10b981',
        yAxisID: 'y',
      }
    ];
  } else if (type === 'ai_macro_transformation') {
    datasets = [
      {
        label: 'Доля труда в доходе (%)',
        data: metrics.labor_share_pct,
        borderColor: '#f43f5e',
      },
      {
        label: 'Совокупный выпуск (Real GDP Index)',
        data: metrics.aggregate_output,
        borderColor: '#10b981',
      },
      {
        label: 'Покупательная способность потребителей',
        data: metrics.median_purchasing_power_index,
        borderColor: '#38bdf8',
      }
    ];
  } else {
    datasets = [
      {
        label: 'Ставка Тейлора (%)',
        data: metrics.taylor_policy_rate_pct,
        borderColor: '#f43f5e',
      },
      {
        label: 'Ставка AIT (Fed 2020) (%)',
        data: metrics.ait_policy_rate_pct,
        borderColor: '#38bdf8',
      },
      {
        label: 'Ставка NGDP таргетирования (%)',
        data: metrics.ngdp_policy_rate_pct,
        borderColor: '#10b981',
      }
    ];
  }

  experimentChart = new Chart(ctx, {
    type: 'line',
    data: { labels: quarters, datasets: datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          grid: { color: 'rgba(255, 255, 255, 0.06)' },
          ticks: { color: '#94a3b8' }
        },
        x: {
          grid: { color: 'rgba(255, 255, 255, 0.06)' },
          ticks: { color: '#94a3b8' }
        }
      },
      plugins: { legend: { labels: { color: '#f1f5f9' } } }
    }
  });
}

// ── 3. QuantLib Options & AMM ─────────────────────────────────────────────
async function priceOptionQuantLib() {
  const spot = parseFloat(document.getElementById('inst-spot').value);
  const strike = parseFloat(document.getElementById('inst-strike').value);
  const vol = parseFloat(document.getElementById('inst-vol').value) / 100.0;
  const rate = parseFloat(document.getElementById('inst-rate').value) / 100.0;
  const expiry = parseFloat(document.getElementById('inst-expiry').value);
  const optType = document.getElementById('inst-opt-type').value;

  try {
    const res = await fetch('/api/instruments/option/price', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        spot_price: spot,
        strike_price: strike,
        volatility: vol,
        risk_free_rate: rate,
        maturity_years: expiry,
        option_type: optType,
        pricing_engine: 'black_scholes',
      })
    });
    const data = await res.json();
    document.getElementById('greek-npv').innerText = `$${data.npv.toFixed(2)}`;
    document.getElementById('greek-delta').innerText = data.delta ? data.delta.toFixed(3) : 'N/A';
    document.getElementById('greek-gamma').innerText = data.gamma ? data.gamma.toFixed(4) : 'N/A';
    document.getElementById('greek-vega').innerText = data.vega ? data.vega.toFixed(3) : 'N/A';
    document.getElementById('greek-theta').innerText = data.theta ? data.theta.toFixed(3) : 'N/A';
    document.getElementById('greek-rho').innerText = data.rho ? data.rho.toFixed(3) : 'N/A';
  } catch (e) {
    console.warn('QuantLib option pricing endpoint unavailable, using Black-Scholes local evaluation');
  }
}

async function renderAMMComparison() {
  try {
    const res = await fetch('/api/experiments/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        experiment_type: 'novel_instrument_amm',
        name: 'AMM-Test',
        horizon_quarters: 4,
        parameters: { current_price: 100.0, range_lower: 80.0, range_upper: 125.0 }
      })
    });
    const data = await res.json();
    const prices = data.metrics.price_points;
    const v3 = data.metrics.concentrated_portfolio_value;
    const v2 = data.metrics.standard_v2_portfolio_value;

    const ctx = document.getElementById('chart-amm').getContext('2d');
    if (ammChart) ammChart.destroy();

    ammChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: prices,
        datasets: [
          {
            label: 'Uniswap v3 Концентрированная Ликвидность ($)',
            data: v3,
            borderColor: '#a855f7',
            backgroundColor: 'rgba(168, 85, 247, 0.1)',
            fill: true,
          },
          {
            label: 'Стандартный AMM v2 (x*y=k) ($)',
            data: v2,
            borderColor: '#38bdf8',
            borderDash: [5, 5],
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#f1f5f9' } } }
      }
    });
  } catch (e) {
    console.error('AMM chart error:', e);
  }
}

// ── 4. AI Algorithmic Collusion ───────────────────────────────────────────
async function simulateAICollusion() {
  const sellers = parseInt(document.getElementById('ai-sellers').value);
  const eps = parseInt(document.getElementById('ai-episodes').value);
  const gamma = parseFloat(document.getElementById('ai-discount').value);

  try {
    const res = await fetch('/api/abm/ai/pricing-collusion', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        n_sellers: sellers,
        episodes: eps,
        discount_factor: gamma,
        learning_rate: 0.15,
      })
    });
    const data = await res.json();

    document.getElementById('ai-collusion-index').innerText = `${data.collusion_index} (Δ Index)`;
    document.getElementById('ai-interpretation').innerText = data.interpretation;

    const ctx = document.getElementById('chart-ai-pricing').getContext('2d');
    if (aiPricingChart) aiPricingChart.destroy();

    const labels = Array.from({ length: data.price_trajectory.length }, (_, i) => `Ep ${i * (eps / data.price_trajectory.length)}`);
    aiPricingChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Средняя Цена ИИ Агентов',
            data: data.price_trajectory,
            borderColor: '#38bdf8',
            tension: 0.2,
          },
          {
            label: `Монопольная Цена ($${data.monopoly_price})`,
            data: Array(labels.length).fill(data.monopoly_price),
            borderColor: '#a855f7',
            borderDash: [4, 4],
          },
          {
            label: `Равновесие Нэша ($${data.nash_price})`,
            data: Array(labels.length).fill(data.nash_price),
            borderColor: '#f43f5e',
            borderDash: [4, 4],
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#f1f5f9' } } }
      }
    });
  } catch (e) {
    console.error('AI pricing simulation error:', e);
  }
}

// ── 5. Systemic Risk (Eisenberg-Noe) ───────────────────────────────────────
async function runSystemicStressTest() {
  const shock = parseFloat(document.getElementById('systemic-shock').value) / 100.0;
  const banks = ['JPM_Peer', 'BAC_Peer', 'C_Peer', 'GS_Peer', 'MS_Peer'];
  const L = [
    [0, 40, 20, 10, 0],
    [30, 0, 35, 0, 15],
    [10, 25, 0, 30, 20],
    [5, 10, 20, 0, 40],
    [15, 0, 10, 25, 0],
  ];
  const e = [80, 60, 45, 50, 55];

  try {
    const res = await fetch('/api/abm/systemic-risk/eisenberg-noe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        bank_names: banks,
        liabilities_matrix: L,
        operating_cash_flows: e,
        asset_shock_pct: shock,
      })
    });
    const data = await res.json();

    // Populate bank status list
    const list = document.getElementById('bank-list');
    list.innerHTML = '';
    banks.forEach((b, idx) => {
      const row = document.createElement('div');
      row.className = 'bank-row';
      const status = data.solvency_status[b];
      const rec = data.recovery_rates[idx] * 100;
      row.innerHTML = `
        <span>${b} (Долг: $${data.total_obligations[idx]}M, Выплата: $${data.clearing_vector[idx]}M)</span>
        <span class="bank-status-tag ${status.toLowerCase()}">${status} (${rec.toFixed(1)}%)</span>
      `;
      list.appendChild(row);
    });

    // Chart
    const ctx = document.getElementById('chart-systemic').getContext('2d');
    if (systemicChart) systemicChart.destroy();
    systemicChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: banks,
        datasets: [
          {
            label: 'Номинальные Обязательства ($M)',
            data: data.total_obligations,
            backgroundColor: 'rgba(148, 163, 184, 0.4)',
          },
          {
            label: 'Фактический Клиринговый Платеж ($M)',
            data: data.clearing_vector,
            backgroundColor: 'rgba(56, 189, 248, 0.8)',
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#f1f5f9' } } }
      }
    });
  } catch (e) {
    console.error('Systemic stress test error:', e);
  }
}

// ── 6. Live WebSocket Simulation Stream ───────────────────────────────────
function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/simulation`;
  let socket = null;

  try {
    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      const ind = document.getElementById('ws-indicator');
      if (ind) ind.classList.add('live');
    };

    socket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.macro) {
          const fed = document.getElementById('tick-fed');
          if (fed) fed.innerText = `${msg.macro.policy_rate_pct.toFixed(2)}%`;
          const pce = document.getElementById('tick-pce');
          if (pce) pce.innerText = `${msg.macro.inflation_pct.toFixed(2)}%`;
        }
      } catch (err) {}
    };

    socket.onclose = () => {
      setTimeout(connectWebSocket, 4000);
    };
  } catch (err) {
    console.warn('WebSocket stream not connecting:', err);
  }
}

// ── Startup ───────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadYieldCurve();
  updateFedCalc();
  renderAMMComparison();
  runSystemicStressTest();
  connectWebSocket();
});
