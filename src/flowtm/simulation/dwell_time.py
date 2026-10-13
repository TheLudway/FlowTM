# FlowTM - BRT Corridor Digital Twin and Optimization Engine
# Copyright (C) 2026 FlowTM Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
flowtm.simulation.dwell_time
============================
Platform dwell time computation based on passenger boarding and alighting dynamics.
Follows standard Transit Capacity and Quality of Service Manual (TCQSM) formulations.
"""


def calculate_dwell_time_sec(boarding_count: int, alighting_count: int) -> float:
    """
    Computes vehicle dwell time at a platform bay based on non-linear passenger flow:
        T_dwell = T_doors + max(beta_board * boarding, beta_alight * alighting)

    Parameters:
        boarding_count: Number of passengers boarding through vehicle doors.
        alighting_count: Number of passengers alighting from the vehicle.

    Returns:
        Dwell time in seconds, clamped between operational bounds [12.0s, 75.0s].
    """
    door_operating_time_sec = 10.0
    passenger_flow_time_sec = max(boarding_count * 1.2, alighting_count * 1.0)
    total_dwell_sec = door_operating_time_sec + passenger_flow_time_sec

    # Clamped between minimum clearance (12s) and maximum operational threshold (75s)
    return min(75.0, max(12.0, total_dwell_sec))


# Backward compatibility alias
calcular_tiempo_parada_seg = calculate_dwell_time_sec
