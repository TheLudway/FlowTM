# FlowTM - BRT Corridor Digital Twin and Optimization Engine
# Copyright (C) 2026 FlowTM Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
flowtm.domain.models
====================
Core domain entities representing passengers, stations, buses,
and aggregated simulation metrics for the Bus Rapid Transit (BRT) corridor.
"""

from dataclasses import dataclass, field


@dataclass
class Passenger:
    """
    Represents an individual passenger within the BRT transit system.

    Attributes:
        passenger_id: Unique numerical identifier for the passenger.
        origin_station: 5-digit station code where passenger enters the system.
        destination_station: 5-digit station code where passenger exits.
        arrival_time_sec: Simulation timestamp (in seconds) when passenger arrives at the platform.
        boarding_time_sec: Simulation timestamp when passenger boards a bus (None if still waiting).
    """

    passenger_id: int
    origin_station: str
    destination_station: str
    arrival_time_sec: float
    boarding_time_sec: float | None = None

    @property
    def waiting_time_sec(self) -> float | None:
        """Calculates total waiting time if passenger has boarded."""
        if self.boarding_time_sec is None:
            return None
        return self.boarding_time_sec - self.arrival_time_sec


@dataclass
class Station:
    """
    Represents a BRT station platform and its dynamic passenger queue.

    A passenger only boards a bus whose stop pattern (from the GTFS) serves their
    destination, so express services naturally skip intermediate stations.

    Attributes:
        station_code: Canonical 5-digit string identifier matching GTFS stops.
        name: Human-readable official station name.
        sequence: Positional index along the corridor (1-based from North to South).
        lat: Latitude coordinate.
        lon: Longitude coordinate.
        next_distance_m: Distance in meters to the next downstream station.
        travel_time_sec: Nominal running time to the next station in free-flow conditions.
        current_arrival_rate: Poisson parameter lambda(s, t) in passengers per second.
        waiting_queue: Active list of passengers currently standing on the platform.
        cumulative_waiting_time_sec: Total aggregated passenger waiting time for KPIs.
        total_arrivals: Cumulative number of passengers that arrived at this platform.
        total_boardings: Cumulative number of passengers that successfully boarded a bus.
        total_alightings: Cumulative number of passengers that alighted at this station.
    """

    station_code: str
    name: str
    sequence: int
    lat: float
    lon: float
    next_distance_m: float
    travel_time_sec: float
    current_arrival_rate: float = 0.0
    waiting_queue: list[Passenger] = field(default_factory=list)
    cumulative_waiting_time_sec: float = 0.0
    total_arrivals: int = 0
    total_boardings: int = 0
    total_alightings: int = 0

    def register_arrival(self, passenger: Passenger) -> None:
        """Registers a new passenger arriving at the platform queue."""
        self.waiting_queue.append(passenger)
        self.total_arrivals += 1

    def board_passengers(
        self, bus_scheduled_stops: list[str], available_capacity: int
    ) -> list[Passenger]:
        """
        Filters and boards eligible passengers whose destination is served by the arriving bus.

        Args:
            bus_scheduled_stops: List of station codes served by the bus.
            available_capacity: Maximum number of passengers the bus can admit.

        Returns:
            List of passengers that boarded the vehicle.
        """
        boarded: list[Passenger] = []
        remaining: list[Passenger] = []

        for p in self.waiting_queue:
            if (
                len(boarded) < available_capacity
                and p.destination_station in bus_scheduled_stops
            ):
                boarded.append(p)
            else:
                remaining.append(p)

        self.waiting_queue = remaining
        self.total_boardings += len(boarded)
        return boarded


@dataclass
class Bus:
    """
    Represents an articulated BRT vehicle operating on a specific trunk route.

    Attributes:
        bus_id: Unique trip identifier (e.g. 'H13_1').
        route: Official GTFS route code (e.g. 'H13').
        max_capacity: Nominal capacity in passengers.
        vehicle_id: Physical vehicle operating the trip (reused across cycles).
        onboard_passengers: Active list of passengers currently inside the vehicle.
        scheduled_stops: Ordered list of station codes where this service is scheduled to stop.
        occupancy_history: Historical occupancy fraction [0.0, 1.0] recorded at each stop.
        passenger_profile_by_stop: Telemetry records detailing boardings, alightings, and load per stop.
    """

    bus_id: str
    route: str
    max_capacity: int = 160
    onboard_passengers: list[Passenger] = field(default_factory=list)
    scheduled_stops: list[str] = field(default_factory=list)
    occupancy_history: list[float] = field(default_factory=list)
    passenger_profile_by_stop: list[dict] = field(default_factory=list)
    vehicle_id: str = ""

    @property
    def total_passengers(self) -> int:
        """Current number of passengers onboard."""
        return len(self.onboard_passengers)

    @property
    def available_capacity(self) -> int:
        """Remaining passenger capacity before reaching maximum limit."""
        return max(0, self.max_capacity - self.total_passengers)

    @property
    def occupancy_rate(self) -> float:
        """Load factor ratio (onboard / max_capacity) between 0.0 and 1.0+."""
        return (
            self.total_passengers / self.max_capacity if self.max_capacity > 0 else 0.0
        )


@dataclass
class SimulationResult:
    """
    Consolidated performance metrics and telemetry output of a corridor simulation run.

    Attributes:
        avg_waiting_time_min: Mean passenger wait time at platforms in minutes.
        avg_occupancy_rate: Mean fleet occupancy ratio across the entire run.
        overcrowded_bus_pct: Percentage of bus arrivals operating at >= 95% capacity.
        total_transported_passengers: Total number of passengers completed or in transit.
        stranded_passengers_in_queue: Passengers remaining on platforms when the simulation ended.
        total_dispatched_buses: Total vehicle trips dispatched across all routes.
        station_metrics: Per-station summary metrics (arrivals, boardings, wait time).
        route_load_profiles: Per-route load profiles along the corridor stops.
        avg_dispatch_delay_min: Mean delay of optimizable-route departures caused by
            vehicles not yet back at the terminal (physical fleet shortage).
        od_counts: Simulated trips per (origin, destination) pair.
    """

    avg_waiting_time_min: float
    avg_occupancy_rate: float
    overcrowded_bus_pct: float
    total_transported_passengers: int
    stranded_passengers_in_queue: int
    total_dispatched_buses: int
    station_metrics: list[dict] = field(default_factory=list)
    route_load_profiles: dict[str, list[dict]] = field(default_factory=dict)
    avg_dispatch_delay_min: float = 0.0
    od_counts: dict[tuple[str, str], int] = field(default_factory=dict)
