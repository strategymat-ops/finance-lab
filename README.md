# 🏛️ Finance Lab — Лаборатория Экономических Исследований

Институциональная количественная лаборатория для моделирования и тестирования:
1. **ФРС и Центральных Банков** (Правило Тейлора, кривые доходности Nelson-Siegel, баланс ФРС, стресс-тесты).
2. **Новых Экономических Отношений** (Программируемые CBDC с демерреджем Сильвио Гезелля, универсальный дивиденд от капитала ИИ, альтернативные клиринговые контуры).
3. **Новых Финансовых Инструментов** (Оценка деривативов в **QuantLib**, концентрированная ликвидность AMM Uniswap v3, обеспеченные вычислительными мощностями токены CBT).
4. **Роли ИИ в Будущей Экономике** (Макроэкономическая автоматизация когнитивного труда, алгоритмический сговор цен RL-агентов по модели Calvano et al. AER 2020).
5. **Системного Риска** (Межбанковский клиринг взаимных требований Eisenberg-Noe 2001).

---

## 🛠️ Используемый Инструментарий Мировых Институтов
В проекте **исключены любые игрушечные заглушки**. Вся аналитическая и вычислительная база опирается на профессиональный стек центральных банков, инвестиционных банков и академических исследователей:

- **QuantLib** — мировой золотой стандарт оценки финансовых инструментов и кривых ставок (используется Goldman Sachs, JP Morgan, Morgan Stanley).
- **econpizza & gEconpy** — современные DSGE-модели (Dynamic Stochastic General Equilibrium) с неоднородными агентами (HANK) и нулевой нижней границей ставок (ZLB).
- **HARK (Econ-ARK)** — среда моделирования гетерогенных потребителей и сбережений (используется исследователями ФРС, ЕЦБ и МВФ).
- **FRED API** — прямой доступ к официальной базе данных Федерального Резервного Банка Сент-Луиса.
- **Eisenberg-Noe Clearing** — официальный алгоритм Банка Международных Расчетов (BIS) и МВФ для межбанковского системного риска.
- **Rust Core (PyO3)** — высокопроизводительный стакан заявок (Order Book) и симуляция Монте-Карло.

---

## 🚀 Быстрый запуск в Google Cloud Shell (с дублированием терминала)

Лаборатория спроектирована для работы в мощной облачной среде Google Cloud с автоматическим пробросом портов и зеркалированием терминала.

### Шаг 1: Запуск в Google Cloud Shell
1. Откройте [Google Cloud Shell](https://shell.cloud.google.com).
2. Выполните инициализацию окружения:
```bash
git clone https://github.com/your-username/finance-lab.git
cd finance-lab
bash cloud/setup-vm.sh
```

### Шаг 2: Подключение и дублирование терминала на вашем компьютере
В вашем локальном PowerShell на Windows запустите коннектор:
```powershell
powershell -ExecutionPolicy Bypass -File .\cloud\cloudshell-launch.ps1
```
Скрипт автоматически:
- Пробросит порты `8000` (FastAPI + веб-дашборд), `8001` (WebSocket stream) и `8888` (Jupyter) на ваш `localhost`.
- Зеркалирует интерактивную командную строку Cloud Shell прямо в вашем локальном окне PowerShell.

---

## 💻 Локальный запуск (Docker или Python)

### Вариант А: Через Docker Compose
```bash
docker compose up --build
```
После запуска перейдите в браузере:
👉 **http://localhost:8000** (Интерактивная панель управления лабораторией)

### Вариант Б: Прямой запуск через Python
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 📂 Структура Проекта

```
finance-lab/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── fed.py            # ФРС, правило Тейлора, QuantLib yield curves, FRED
│   │   │   ├── instruments.py    # Оценка деривативов, Greeks, IRS свопы (QuantLib)
│   │   │   ├── dsge.py           # DSGE модели (econpizza, gEconpy)
│   │   │   ├── abm.py            # Системный риск Eisenberg-Noe, AI сговор цен
│   │   │   ├── data_sources.py   # Интеграция FRED, Yahoo Finance, World Bank
│   │   │   └── experiments.py    # CBDC с демерреджем, AMM v3, Compute-Backed Tokens
│   │   ├── ws/
│   │   │   └── simulation_stream.py # Real-time WebSocket стриминг
│   │   ├── static/               # Премиум-интерфейс дашборда (Chart.js, Dark Glass)
│   │   └── main.py               # Точка входа FastAPI
│   ├── db/
│   │   └── init.sql              # Схема PostgreSQL для экспериментов
│   ├── requirements.txt          # Полный профессиональный экономический стек
│   └── Dockerfile
│
├── cloud/
│   ├── cloudshell-launch.ps1     # Скрипт мгновенного запуска и проброса портов
│   ├── connect.ps1               # Менеджер подключения к Cloud Shell / VM
│   ├── setup-vm.sh               # Скрипт развертывания зависимостей в облаке
│   └── terminal-mirror.sh        # Двустороннее зеркалирование терминала (tmate)
│
├── core/                         # Вычислительное ядро на Rust (PyO3)
│   ├── Cargo.toml
│   └── src/                      # Order book, Monte Carlo, Market matching engine
│
└── docker-compose.yml
```
