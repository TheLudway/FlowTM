# FlowTM - BRT Corridor Digital Twin and Optimization Engine
# Copyright (C) 2026 FlowTM Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
flowtm.infrastructure.gtfs_exporter
===================================
PEAS Model Actuator: Official GTFS Schedule Exporter.
Publishes standard 'frequencies.txt' for integration with TransMilenio
Fleet Management Systems (SAE - Sistema de Ayuda a la Explotación).

Specification (from Avance II Project Document, Section 3 - Actuators):
    Structured fields: (route_id, trip_id, start_time, end_time, headway_secs, exact_times=0)
"""

from pathlib import Path


def export_gtfs_frequencies(
    headways: dict[str, float],
    output_path: Path,
    start_time: str = "06:00:00",
    end_time: str = "09:00:00",
    exact_times: int = 0,
) -> Path:
    """
    Exports a dictionary of route headways (in minutes) to standard GTFS frequencies.txt.

    Args:
        headways: Dict mapping route_id to interval in minutes (e.g. {'B13': 2.0, ...}).
        output_path: Target path for frequencies.txt.
        start_time: Peak window start time formatted as HH:MM:SS.
        end_time: Peak window end time formatted as HH:MM:SS.
        exact_times: 0 for frequency-based headway dispatch, 1 for exact schedule times.

    Returns:
        The Path of the exported frequencies.txt file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    header = "route_id,trip_id,start_time,end_time,headway_secs,exact_times\n"
    lines = [header]

    for route_id, interval_min in sorted(headways.items()):
        headway_secs = round(interval_min * 60.0)
        trip_id = f"TRIP_{route_id}_PEAK"
        lines.append(
            f"{route_id},{trip_id},{start_time},{end_time},{headway_secs},{exact_times}\n"
        )

    with open(output_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    return output_path
