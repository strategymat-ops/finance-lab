"""
Finance Lab — FastAPI Application
================================
Orchestration layer for professional economic simulation tools.
This is a THIN wrapper — the real work is done by:
  - econpizza (DSGE)
  - HARK/econ-ark (heterogeneous agents)
  - gEconpy (optimization-based DSGE)
  - QuantLib (derivatives & yield curves)
  - Mesa/abce (agent-based models)
  - pyfrbus (FRB/US model — when available)
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import dsge, fed, instruments, abm, data_sources, experiments
from app.ws.simulation_stream import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    # TODO: init DB pool, Redis, load models
    print("╔══════════════════════════════════════════╗")
    print("║  Finance Lab — Economics Research Engine  ║")
    print("╚══════════════════════════════════════════╝")
    yield
    print("Finance Lab shutting down.")


app = FastAPI(
    title="Finance Lab",
    description=(
        "Research platform for testing economic relationships, "
        "financial instruments, central bank policy, and AI in economics. "
        "Powered by: econpizza, HARK, gEconpy, QuantLib, Mesa, PyFRB/US."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API Routes ─────────────────────────────────────────────────────────────
app.include_router(dsge.router, prefix="/api/dsge", tags=["DSGE Models"])
app.include_router(fed.router, prefix="/api/fed", tags=["Federal Reserve"])
app.include_router(instruments.router, prefix="/api/instruments", tags=["Financial Instruments"])
app.include_router(abm.router, prefix="/api/abm", tags=["Agent-Based Models"])
app.include_router(data_sources.router, prefix="/api/data", tags=["Data Sources"])
app.include_router(experiments.router, prefix="/api/experiments", tags=["Experiments"])
app.include_router(ws_router)


from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Mount static files
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def root():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {
        "name": "Finance Lab",
        "status": "running",
        "dashboard": "/static/index.html",
    }

@app.get("/api/status")
async def api_status():
    return {
        "name": "Finance Lab",
        "status": "running",
        "engines": {
            "dsge": ["econpizza", "gEconpy", "pydsge"],
            "heterogeneous_agents": ["HARK (econ-ark)"],
            "financial_engineering": ["QuantLib"],
            "agent_based": ["Mesa", "abce"],
            "central_bank": ["pyfrbus (FRB/US)"],
            "data": ["FRED", "World Bank", "Yahoo Finance"],
            "ai": ["PyTorch", "PettingZoo", "Stable-Baselines3"],
        },
    }


@app.get("/health")
async def health():
    """Check which engines are available."""
    status = {}

    try:
        import econpizza
        status["econpizza"] = econpizza.__version__
    except ImportError:
        status["econpizza"] = "not installed"

    try:
        import HARK
        status["HARK"] = HARK.__version__
    except ImportError:
        status["HARK"] = "not installed"

    try:
        import QuantLib
        status["QuantLib"] = QuantLib.__version__
    except (ImportError, AttributeError):
        status["QuantLib"] = "not installed"

    try:
        import mesa
        status["mesa"] = mesa.__version__
    except ImportError:
        status["mesa"] = "not installed"

    try:
        import gEconpy
        status["gEconpy"] = "available"
    except ImportError:
        status["gEconpy"] = "not installed"

    try:
        import statsmodels
        status["statsmodels"] = statsmodels.__version__
    except ImportError:
        status["statsmodels"] = "not installed"

    try:
        import torch
        status["torch"] = torch.__version__
        status["torch_cuda"] = torch.cuda.is_available()
    except ImportError:
        status["torch"] = "not installed"

    try:
        import fredapi
        status["fredapi"] = "available"
    except ImportError:
        status["fredapi"] = "not installed"

    return {"engines": status}
