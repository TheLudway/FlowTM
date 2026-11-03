# FlowTM - BRT Corridor Digital Twin and Optimization Engine
# Copyright (C) 2026 FlowTM Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
flowtm.infrastructure.frontend_payload
======================================
Converts simulator telemetry into the JSON contracts consumed by the OCC
frontend (bus trajectories, queue timeline, summary KPIs). Shared by the static
exporter (``scripts/export_frontend_data.py``) and the live API.
"""

from collections.abc import Iterable, Mapping
from typing import Any

from flowtm.simulation.scenario import SOUTH_SINK_CODE, CorridorScenario


def bus_trajectories(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Group bus position records into one keyframed trajectory per trip."""
    trajectories: dict[str, dict[str, Any]] = {}
    for row in records:
        trip = trajectories.setdefault(
            row["bus_id"],
            {
                "bus_id": row["bus_id"],
                "route": row["route"],
                "start_time": float(row["time_sec"]),
                "end_time": float(row["time_sec"]),
                "keyframes": [],
            },
        )
        t = float(row["time_sec"])
        trip["start_time"] = min(trip["start_time"], t)
        trip["end_time"] = max(trip["end_time"], t)
        trip["keyframes"].append(
            {
                "t": t,
                "lat": float(row["lat"]),
                "lon": float(row["lon"]),
                "occ": float(row["occupancy_pct"]),
                "pax": int(row["passengers"]),
            }
        )
    for trip in trajectories.values():
        trip["keyframes"].sort(key=lambda keyframe: keyframe["t"])
    return list(trajectories.values())


def queue_timeline(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Station queue sizes grouped by sampling instant."""
    by_time: dict[int, dict[str, int]] = {}
    for row in records:
        by_time.setdefault(int(row["time_sec"]), {})[row["station_code"]] = int(
            row["queue_size"]
        )
    return [{"t": t, "queues": queues} for t, queues in sorted(by_time.items())]


def station_names(scenario: CorridorScenario) -> dict[str, str]:
    """Display names by station code, including the south sink."""
    names = {
        code: name.title()
        for code, name in scenario.topology.select("codigo", "nombre").iter_rows()
    }
    names[SOUTH_SINK_CODE] = "Sur (fuera del corredor)"
    return names


def summary_payload(
    run_metrics: Mapping[str, Any],
    max_queue: int,
    scenario: CorridorScenario,
) -> dict[str, Any]:
    """Summary KPIs in the ``summary*.json`` contract of the frontend."""
    names = station_names(scenario)
    return {
        "total_dispatched_buses": run_metrics["total_dispatched_buses"],
        "total_passengers_served": run_metrics["total_passengers_served"],
        "avg_waiting_time_min": run_metrics["avg_waiting_time_min"],
        "avg_occupancy_pct": run_metrics["avg_occupancy_pct"],
        "overcrowded_buses_pct": run_metrics["overcrowded_buses_pct"],
        "stranded_passengers_in_queue": run_metrics["stranded_passengers_in_queue"],
        "max_queue_station": max_queue,
        "avg_dispatch_delay_min": run_metrics.get("avg_dispatch_delay_min", 0.0),
        "od_top": [
            {
                **pair,
                "origin_name": names.get(pair["origin"], pair["origin"]),
                "destination_name": names.get(pair["destination"], pair["destination"]),
            }
            for pair in run_metrics.get("od_top", [])
        ],
        "active_routes": len(scenario.services),
        "optimizable_routes": len(scenario.optimizable_routes),
        "total_stations": scenario.topology.height,
        "sim_duration_sec": 10800,
        "start_hour": 6,
    }
