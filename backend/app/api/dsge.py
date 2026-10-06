"""
DSGE Model API — econpizza, gEconpy, pydsge
============================================
Thin REST layer over professional DSGE frameworks.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

router = APIRouter()

# ── Schemas ────────────────────────────────────────────────────────────────

class EconpizzaRunRequest(BaseModel):
    """Run an econpizza DSGE model from YAML specification."""
    yaml_content: Optional[str] = Field(
        None,
        description="YAML model specification (econpizza format). "
                    "If not provided, use 'model_name' to load a built-in example.",
    )
    model_name: Optional[str] = Field(
        None,
        description="Built-in econpizza example name: 'dsge', 'hank', 'hank2', etc.",
    )
    shock_name: Optional[str] = Field(None, description="Name of the shock variable")
    shock_size: float = Field(0.01, description="Size of the shock (e.g. 0.01 = 1%)")
    periods: int = Field(300, description="Number of periods to simulate")


class GEconRequest(BaseModel):
    """Run a gEconpy model from .gcn specification."""
    gcn_content: str = Field(
        ...,
        description="GCN model specification (gEcon format with optimization blocks)",
    )
    calibration: dict[str, float] = Field(
        default_factory=dict,
        description="Parameter calibration overrides",
    )


class DSGEResponse(BaseModel):
    steady_state: dict[str, float]
    irfs: dict[str, list[float]]  # impulse response functions
    info: dict[str, Any]


# ── Econpizza endpoints ───────────────────────────────────────────────────

@router.get("/econpizza/examples")
async def list_econpizza_examples():
    """List all built-in econpizza model examples."""
    try:
        import econpizza as ep
        examples = {}
        for name in dir(ep.examples):
            if not name.startswith("_"):
                path = getattr(ep.examples, name, None)
                if path and isinstance(path, (str, Path)):
                    examples[name] = str(path)
        return {"examples": examples}
    except ImportError:
        raise HTTPException(503, "econpizza is not installed. Run: pip install econpizza")


@router.post("/econpizza/run", response_model=DSGEResponse)
async def run_econpizza_model(req: EconpizzaRunRequest):
    """
    Run a DSGE model using econpizza.
    
    econpizza solves nonlinear DSGE models including:
    - Representative Agent New Keynesian (RANK)
    - Heterogeneous Agent New Keynesian (HANK)
    - Models with occasionally binding constraints (ZLB)
    
    Provide either a YAML specification or a built-in model name.
    """
    try:
        import econpizza as ep
    except ImportError:
        raise HTTPException(503, "econpizza not installed")

    try:
        # Load model
        if req.yaml_content:
            # Write YAML to temp file and load
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yml", delete=False
            ) as f:
                f.write(req.yaml_content)
                f.flush()
                mod = ep.load(f.name)
        elif req.model_name:
            example_path = getattr(ep.examples, req.model_name, None)
            if example_path is None:
                raise HTTPException(
                    400,
                    f"Unknown example '{req.model_name}'. "
                    f"Use GET /api/dsge/econpizza/examples to list available models.",
                )
            mod = ep.load(str(example_path))
        else:
            raise HTTPException(400, "Provide either yaml_content or model_name")

        # Find steady state
        _ = mod.solve_stst()

        # Compute impulse responses if shock specified
        irfs = {}
        if req.shock_name:
            x, flag = mod.find_path(
                shock=(req.shock_name, req.shock_size, 0),
                T=req.periods,
            )
            if x is not None:
                var_names = mod["variables"]
                for i, name in enumerate(var_names):
                    irfs[name] = x[:, i].tolist()

        # Extract steady state
        stst = {}
        if hasattr(mod, "stst") and mod["stst"] is not None:
            var_names = mod["variables"]
            for i, name in enumerate(var_names):
                stst[name] = float(mod["stst"][i])

        return DSGEResponse(
            steady_state=stst,
            irfs=irfs,
            info={
                "variables": list(mod.get("variables", [])),
                "parameters": {
                    k: float(v) for k, v in mod.get("parameters", {}).items()
                },
                "solver": "econpizza",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Model error: {str(e)}")


@router.post("/econpizza/upload")
async def upload_econpizza_yaml(file: UploadFile = File(...)):
    """Upload a YAML model file and validate it."""
    try:
        import econpizza as ep
    except ImportError:
        raise HTTPException(503, "econpizza not installed")

    content = await file.read()
    with tempfile.NamedTemporaryFile(
        mode="wb", suffix=".yml", delete=False
    ) as f:
        f.write(content)
        f.flush()
        try:
            mod = ep.load(f.name)
            return {
                "status": "valid",
                "variables": list(mod.get("variables", [])),
                "parameters": list(mod.get("parameters", {}).keys()),
                "shocks": list(mod.get("shocks", {}).keys()),
            }
        except Exception as e:
            return {"status": "invalid", "error": str(e)}


# ── gEconpy endpoints ─────────────────────────────────────────────────────

@router.post("/geconpy/run")
async def run_geconpy_model(req: GEconRequest):
    """
    Run a DSGE model using gEconpy.
    
    gEconpy allows you to specify models as OPTIMIZATION PROBLEMS
    (utility functions + budget constraints) — it automatically derives
    the first-order conditions. This is how central banks specify models.
    
    Uses .gcn format (same as R's gEcon).
    """
    try:
        import gEconpy as ge
    except ImportError:
        raise HTTPException(503, "gEconpy not installed. Run: pip install gEconpy")

    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".gcn", delete=False
        ) as f:
            f.write(req.gcn_content)
            f.flush()
            model = ge.model_from_gcn(f.name)

        # Apply calibration
        if req.calibration:
            model.free_param = {**model.free_param, **req.calibration}

        # Solve steady state
        model.steady_state()

        # Solve model (perturbation)
        model.solve_model()

        result = {
            "steady_state": {
                str(k): float(v) for k, v in model.steady_state_dict.items()
            },
            "variables": [str(v) for v in model.variables],
            "parameters": {
                str(k): float(v) for k, v in model.free_param.items()
            },
            "solver": "gEconpy",
        }
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"gEconpy error: {str(e)}")


# ── pydsge endpoints ──────────────────────────────────────────────────────

@router.post("/pydsge/estimate")
async def estimate_pydsge(yaml_content: str):
    """
    Estimate a linear DSGE model using pydsge.
    
    pydsge specializes in:
    - Linear DSGE with occasionally binding constraints
    - Bayesian estimation (MCMC)
    - Filtering (Kalman)
    
    Used for modeling the Zero Lower Bound on interest rates.
    """
    try:
        import pydsge
    except ImportError:
        raise HTTPException(503, "pydsge not installed. Run: pip install pydsge")

    raise HTTPException(501, "pydsge estimation endpoint — TODO: requires data upload")


# ── Model files management ────────────────────────────────────────────────

@router.get("/models")
async def list_saved_models():
    """List all saved model specifications in the lab."""
    models_dir = Path(__file__).parent.parent.parent / "models"
    if not models_dir.exists():
        return {"models": []}

    models = []
    for f in models_dir.rglob("*"):
        if f.suffix in (".yml", ".yaml", ".gcn", ".mod"):
            models.append({
                "name": f.stem,
                "format": f.suffix,
                "path": str(f.relative_to(models_dir)),
                "framework": {
                    ".yml": "econpizza",
                    ".yaml": "econpizza",
                    ".gcn": "gEconpy",
                    ".mod": "Dynare",
                }.get(f.suffix, "unknown"),
            })
    return {"models": models}
