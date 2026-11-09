# FlowTM - BRT Corridor Digital Twin and Optimization Engine
# Copyright (C) 2026 FlowTM Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from flowtm.api import app as api


@pytest.fixture
def client(synthetic_scenario_dir: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(api, "SCENARIO_DIR", synthetic_scenario_dir)
    monkeypatch.setattr(api, "_simulator", None)
    monkeypatch.setattr(api, "HOLDOUT_SEEDS", (7, 8))
    return TestClient(api.app)


def read_events(client: TestClient, job_id: str) -> list[dict]:
    events = []
    with client.stream("GET", f"/api/agente/{job_id}/eventos") as response:
        for line in response.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[len("data: ") :]))
    return events


def test_scenario_endpoint_exposes_fleet_and_routes(client: TestClient):
    body = client.get("/api/escenario").json()
    assert body["rutas_optimizables"] == ["R1", "R2", "R3"]
    assert body["flota_base"] == body["flota_maxima"] == 33
    assert set(body["algoritmos"]) == {
        "busqueda_aleatoria",
        "hill_climbing",
        "recocido_simulado",
    }


def test_simulate_reports_feasibility(client: TestClient):
    ok = client.post("/api/simular", json={"headways": {"R1": 6.0}}).json()
    assert ok["factible"] is True
    assert ok["kpis"]["total_dispatched_buses"] > 0
    too_many = client.post("/api/simular", json={"headways": {"R1": 2.0}}).json()
    assert too_many["factible"] is False


def test_simulate_rejects_unknown_route_and_bounds(client: TestClient):
    assert (
        client.post("/api/simular", json={"headways": {"BG1": 5.0}}).status_code == 422
    )
    assert (
        client.post("/api/simular", json={"headways": {"R1": 1.0}}).status_code == 422
    )


def test_agent_streams_iterations_and_result(client: TestClient):
    job = client.post(
        "/api/agente",
        json={
            "algoritmo": "hill_climbing",
            "presupuesto": 5,
            "semillas": 1,
            "pesos": {"espera": 1, "sobrecupo": 0, "varados": 0, "flota": 0},
        },
    ).json()
    events = read_events(client, job["job_id"])
    kinds = [e["tipo"] for e in events]

    assert kinds[0] == "inicio"
    assert "iteracion" in kinds
    assert kinds[-1] == "resultado", events[-1]
    result = events[-1]
    assert result["mejor"]["fleet_used"] <= 33
    assert result["validacion"]["espera_min"]["semillas"] == 2
    assert result["replay"]["bus_trajectories"]
    assert result["replay"]["summary"]["total_stations"] == 8


def test_agent_repairs_schedule_when_fleet_bound_is_lowered(client: TestClient):
    job = client.post(
        "/api/agente",
        json={
            "algoritmo": "busqueda_aleatoria",
            "presupuesto": 5,
            "semillas": 1,
            "flota_maxima": 25,
        },
    ).json()
    events = read_events(client, job["job_id"])
    start, result = events[0], events[-1]
    assert start["flota_maxima"] == 25
    assert result["tipo"] == "resultado", result
    assert result["mejor"]["fleet_used"] <= 25
