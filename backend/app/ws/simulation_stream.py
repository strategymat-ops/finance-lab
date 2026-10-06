"""
Simulation Streaming WebSocket Server
=====================================
Provides real-time bi-directional streaming for:
- Live macroeconomic state ticks (GDP, inflation, unemployment, Fed rate)
- Continuous order book depth & transaction tape
- Dynamic intervention: Central bank rate hikes, liquidity injections, AI shocks
"""

from __future__ import annotations

import asyncio
import json
import math
from typing import Any
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict[str, Any]):
        for connection in list(self.active_connections):
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                self.disconnect(connection)


manager = ConnectionManager()


@router.websocket("/ws/simulation")
async def websocket_simulation_endpoint(websocket: WebSocket):
    """
    Real-time simulation feed.
    Streams state updates every second and accepts client commands:
      - {"action": "set_rate", "rate": 0.05}
      - {"action": "inject_shock", "type": "productivity", "magnitude": 0.15}
      - {"action": "pause"}
      - {"action": "resume"}
    """
    await manager.connect(websocket)

    # Initial state
    t = 0
    paused = False
    policy_rate = 0.045
    inflation = 0.024
    gdp_index = 100.0
    unemployment = 0.041
    base_price = 150.0

    try:
        while True:
            # Check for incoming client messages without blocking indefinitely
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=0.8)
                msg = json.loads(data)
                action = msg.get("action")

                if action == "pause":
                    paused = True
                elif action == "resume":
                    paused = False
                elif action == "set_rate":
                    policy_rate = float(msg.get("rate", policy_rate))
                elif action == "inject_shock":
                    shock_type = msg.get("type")
                    mag = float(msg.get("magnitude", 0.1))
                    if shock_type == "inflation":
                        inflation += mag
                    elif shock_type == "productivity":
                        gdp_index *= (1.0 + mag)
            except asyncio.TimeoutError:
                pass  # Normal tick cycle

            if not paused:
                t += 1
                # Dynamic macro evolution
                inflation += float(np.random.normal(0, 0.0005))
                inflation = max(0.005, min(0.12, inflation))

                # Taylor rule adjustment pressure
                target_rate = 0.02 + inflation + 0.5 * (inflation - 0.02)
                policy_rate += 0.05 * (target_rate - policy_rate)

                # GDP growth responds to real rate (policy_rate - inflation)
                real_rate = policy_rate - inflation
                growth_rate = 0.005 - 0.08 * (real_rate - 0.015)
                gdp_index *= (1.0 + growth_rate)

                # Unemployment (Okun's law)
                unemployment = max(0.03, min(0.12, 0.04 + 0.3 * (100.0 - gdp_index) / 100.0))

                # Asset price evolution (Brownian motion with drift)
                base_price *= math.exp((0.08 - 0.5 * 0.2**2) * (1 / 252) + 0.2 * math.sqrt(1 / 252) * np.random.normal(0, 1))

                # Generate live order book depth snapshot
                spread = max(0.05, round(base_price * 0.001, 2))
                bids = [[round(base_price - (i + 1) * spread, 2), int(np.random.randint(10, 150))] for i in range(5)]
                asks = [[round(base_price + (i + 1) * spread, 2), int(np.random.randint(10, 150))] for i in range(5)]

                payload = {
                    "step": t,
                    "timestamp": asyncio.get_event_loop().time(),
                    "macro": {
                        "policy_rate_pct": round(policy_rate * 100.0, 3),
                        "inflation_pct": round(inflation * 100.0, 3),
                        "gdp_index": round(gdp_index, 2),
                        "unemployment_pct": round(unemployment * 100.0, 2),
                    },
                    "market": {
                        "last_price": round(base_price, 2),
                        "bids": bids,
                        "asks": asks,
                    },
                }

                await websocket.send_text(json.dumps(payload))

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
