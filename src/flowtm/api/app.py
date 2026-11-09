# FlowTM - BRT Corridor Digital Twin and Optimization Engine
# Copyright (C) 2026 FlowTM Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
flowtm.api.app
==============
HTTP API that lets the OCC interact with the rational agent:

* ``GET  /api/escenario``                 scenario, routes, fleet bound, defaults.
* ``POST /api/simular``                   simulate a schedule (KPIs + feasibility).
* ``POST /api/agente``                    launch a search job with user parameters.
* ``GET  /api/agente/{job_id}/eventos``   Server-Sent Events: every iteration live,
                                          then the result (out-of-sample check and
                                          replay telemetry for the map).

Run: ``uv run uvicorn flowtm.api.app:app --port 8000``
"""

import asyncio
import json
import os
import queue
import threading
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from flowtm.domain.state import MAX_HEADWAY_MIN, MIN_HEADWAY_MIN, ScheduleState
from flowtm.infrastructure import frontend_payload as payload
from flowtm.optimization.evaluator import ScheduleEvaluator, holdout_comparison
from flowtm.optimization.search import ALGORITHMS
from flowtm.optimization.utility import UtilityCalculator
from flowtm.simulation.collector import build_summary_metrics
from flowtm.simulation.engine import CorridorSimulator

ROOT_DIR = Path(__file__).resolve().parents[3]
SCENARIO_DIR = Path(
    os.environ.get("FLOWTM_SCENARIO_DIR", ROOT_DIR / "data/scenarios/piloto")
)
REPLAY_SEED = 42
HOLDOUT_SEEDS = tuple(range(42, 52))
TRAINING_SEED_START = 1001
MAX_BUDGET = 300
MAX_TRAINING_SEEDS = 10

app = FastAPI(title="FlowTM API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_simulator: CorridorSimulator | None = None
_simulator_lock = threading.Lock()
_jobs: dict[str, "queue.Queue[dict[str, Any] | None]"] = {}


@app.get("/healthz")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


def simulator() -> CorridorSimulator:
    global _simulator
    if _simulator is None:
        _simulator = CorridorSimulator(SCENARIO_DIR)
    return _simulator


class UtilityWeights(BaseModel):
    """Weights of U(S); they are renormalized to sum 1."""

    espera: float = Field(0.40, ge=0)
    sobrecupo: float = Field(0.30, ge=0)
    varados: float = Field(0.15, ge=0)
    flota: float = Field(0.15, ge=0)

    def calculator(self, max_fleet: int) -> UtilityCalculator:
        total = self.espera + self.sobrecupo + self.varados + self.flota
        if total <= 0:
            raise HTTPException(
                422, "Al menos un peso de la utilidad debe ser positivo."
            )
        return UtilityCalculator(
            max_fleet=max_fleet,
            w_wait=self.espera / total,
            w_overcrowding=self.sobrecupo / total,
            w_stranded=self.varados / total,
            w_fleet=self.flota / total,
        )


class SimulateRequest(BaseModel):
    headways: dict[str, float]
    seed: int = REPLAY_SEED


class AgentRequest(BaseModel):
    algoritmo: Literal["recocido_simulado", "hill_climbing", "busqueda_aleatoria"] = (
        "recocido_simulado"
    )
    presupuesto: int = Field(60, ge=5, le=MAX_BUDGET)
    semillas: int = Field(5, ge=1, le=MAX_TRAINING_SEEDS)
    paso_min: float = Field(0.5, gt=0, le=3)
    semilla_busqueda: int = 42
    flota_maxima: int | None = Field(None, ge=1)
    pesos: UtilityWeights = Field(default_factory=UtilityWeights)


def _schedule_for(
    headways: dict[str, float], max_fleet: int | None = None
) -> ScheduleState:
    base = simulator().scenario.base_schedule()
    unknown = set(headways) - set(base.headways)
    if unknown:
        raise HTTPException(422, f"Rutas no optimizables: {sorted(unknown)}")
    for route, value in headways.items():
        if not MIN_HEADWAY_MIN <= value <= MAX_HEADWAY_MIN:
            raise HTTPException(
                422,
                f"Intervalo de {route} fuera de [{MIN_HEADWAY_MIN}, {MAX_HEADWAY_MIN}] min.",
            )
    state = base.with_headways({**base.headways, **headways})
    if max_fleet is not None:
        state.max_fleet = max_fleet
    return state


def _replay(state: ScheduleState) -> dict[str, Any]:
    """Telemetry of one run in the frontend contracts (for the map replay)."""
    replay = CorridorSimulator(SCENARIO_DIR)
    result = replay.simulate(state.headways, seed=REPLAY_SEED)
    queues = replay.collector.queue_history
    return {
        "bus_trajectories": payload.bus_trajectories(replay.collector.bus_telemetry),
        "station_queues": payload.queue_timeline(queues),
        "summary": payload.summary_payload(
            build_summary_metrics(result),
            max((q["queue_size"] for q in queues), default=0),
            replay.scenario,
        ),
    }


@app.get("/api/escenario")
def get_scenario() -> dict[str, Any]:
    scenario = simulator().scenario
    base = scenario.base_schedule()
    return {
        "metadata": scenario.metadata,
        "rutas_optimizables": scenario.optimizable_routes,
        "rutas_fondo": scenario.background_routes,
        "intervalos_base": base.headways,
        "flota_base": base.total_fleet_used(),
        "flota_maxima": base.max_fleet,
        "tiempos_tramo_min": base.leg_times,
        "flota_regreso": base.fixed_fleet,
        "limites_intervalo": [MIN_HEADWAY_MIN, MAX_HEADWAY_MIN],
        "pesos_por_defecto": UtilityWeights().model_dump(),
        "algoritmos": list(ALGORITHMS),
        "limites": {"presupuesto": MAX_BUDGET, "semillas": MAX_TRAINING_SEEDS},
    }


@app.post("/api/simular")
def simulate(request: SimulateRequest) -> dict[str, Any]:
    state = _schedule_for(request.headways)
    with _simulator_lock:
        result = simulator().simulate(state.headways, seed=request.seed)
    return {
        "intervalos": state.headways,
        "flota_usada": state.total_fleet_used(),
        "flota_maxima": state.max_fleet,
        "factible": state.is_fleet_feasible(),
        "kpis": build_summary_metrics(result),
    }


def _run_job(
    job_queue: "queue.Queue[dict[str, Any] | None]", request: AgentRequest
) -> None:
    try:
        scenario = simulator().scenario
        max_fleet = request.flota_maxima or scenario.max_fleet
        initial = _schedule_for({}, max_fleet=max_fleet)
        if not initial.is_fleet_feasible():
            initial = initial.repaired_to_fleet(step_min=request.paso_min)
        seeds = [TRAINING_SEED_START + k for k in range(request.semillas)]
        utility = request.pesos.calculator(max_fleet)

        job_queue.put(
            {
                "tipo": "inicio",
                "horario_inicial": initial.headways,
                "flota_maxima": max_fleet,
                "semillas": seeds,
            }
        )
        with ScheduleEvaluator(SCENARIO_DIR, seeds, utility=utility) as evaluator:
            kwargs: dict[str, Any] = {
                "budget": request.presupuesto,
                "seed": request.semilla_busqueda,
                "on_iteration": lambda entry: job_queue.put(
                    {"tipo": "iteracion", **entry}
                ),
            }
            if request.algoritmo != "busqueda_aleatoria":
                kwargs["step_min"] = request.paso_min
            result = ALGORITHMS[request.algoritmo](evaluator, initial, **kwargs)

        base_state = _schedule_for({}, max_fleet=max_fleet)
        holdout = holdout_comparison(
            SCENARIO_DIR, base_state, result.best_state, HOLDOUT_SEEDS
        )
        job_queue.put(
            {
                "tipo": "resultado",
                "algoritmo": result.algorithm,
                "parametros": result.params,
                "evaluaciones": result.evaluations,
                "inicial": {
                    "headways": result.initial.headways,
                    "utility": result.initial.utility,
                    "fleet_used": result.initial.fleet_used,
                    "metrics": result.initial.metrics,
                },
                "mejor": {
                    "headways": result.best.headways,
                    "utility": result.best.utility,
                    "utility_se": result.best.standard_error(),
                    "fleet_used": result.best.fleet_used,
                    "metrics": result.best.metrics,
                    "breakdown": result.best.breakdown,
                },
                "delta_utilidad": result.delta_utility,
                "validacion": holdout,
                "replay": _replay(result.best_state),
            }
        )
    except Exception as error:
        job_queue.put({"tipo": "error", "mensaje": str(error)})
    finally:
        job_queue.put(None)


@app.post("/api/agente")
def launch_agent(request: AgentRequest) -> dict[str, str]:
    job_id = uuid.uuid4().hex[:12]
    job_queue: queue.Queue[dict[str, Any] | None] = queue.Queue()
    _jobs[job_id] = job_queue
    threading.Thread(target=_run_job, args=(job_queue, request), daemon=True).start()
    return {"job_id": job_id}


@app.get("/api/agente/{job_id}/eventos")
async def agent_events(job_id: str) -> StreamingResponse:
    job_queue = _jobs.get(job_id)
    if job_queue is None:
        raise HTTPException(404, "Trabajo no encontrado.")

    async def stream() -> AsyncIterator[str]:
        try:
            while True:
                event = await asyncio.to_thread(job_queue.get)
                if event is None:
                    break
                yield f"event: {event['tipo']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
        finally:
            _jobs.pop(job_id, None)

    return StreamingResponse(stream(), media_type="text/event-stream")
