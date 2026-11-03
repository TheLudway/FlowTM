# FlowTM - BRT Corridor Digital Twin and Optimization Engine
# Copyright (C) 2026 FlowTM Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
flowtm.simulation.engine
========================
Discrete Event Simulation (DES) of the southbound corridor on SimPy.

* Demand: non-homogeneous Poisson arrivals lambda(s, t) per station and 15-minute
  window, with destinations drawn from observed AM exits (gravity weights).
* Supply: every trunk service published in the GTFS for the corridor, with its
  real stop pattern. Optimizable routes run the headways under evaluation;
  background routes run their GTFS headway.
* Physical fleet: each optimizable route owns the vehicles given by the fleet
  rule of ``ScheduleState`` (both legs, Little's law). A vehicle is back at the
  terminal after its GTFS peak cycle (outbound + return + layovers); when none
  is available the dispatch is delayed, so fleet shortages emerge in the KPIs.
* Platforms: each station has as many docking bays as stopping positions
  (official wagon count / GTFS platforms); full bays make buses queue (bunching).
"""

import math
import random
from collections import Counter
from pathlib import Path

import polars as pl
import simpy

from flowtm.domain.models import Bus, Passenger, SimulationResult, Station
from flowtm.simulation.collector import SimulationCollector
from flowtm.simulation.dwell_time import calculate_dwell_time_sec
from flowtm.simulation.scenario import SOUTH_SINK_CODE, CorridorScenario, ServiceSpec

DEMAND_WINDOW_SEC = 900.0
QUEUE_SAMPLE_SEC = 60.0
OVERCROWDED_LOAD_FACTOR = 0.95


class CorridorSimulator:
    """Simulates passenger and fleet operations along the BRT corridor."""

    def __init__(self, scenario_dir: Path) -> None:
        self.scenario = CorridorScenario.load(Path(scenario_dir))
        self.df_topology = self.scenario.topology
        self.ordered_station_codes: list[str] = self.df_topology["codigo"].to_list()
        self.station_position = {
            code: index for index, code in enumerate(self.ordered_station_codes)
        }
        self.collector = SimulationCollector()
        self.stations: dict[str, Station] = {}
        self.bays: dict[str, simpy.Resource] = {}
        self.simulated_buses: list[Bus] = []
        self.dispatch_delays_sec: list[float] = []
        self.passenger_id_counter = 1
        self.passengers_exited_south = 0
        self.od_counts: Counter[tuple[str, str]] = Counter()

    # ------------------------------------------------------------------ setup
    def reset_environment(
        self, env: simpy.Environment, start_hour: int, end_hour: int
    ) -> None:
        """Initializes stations, docking bays and the demand windows."""
        demand = self.scenario.demand.filter(
            (pl.col("hora_del_dia") >= start_hour) & (pl.col("hora_del_dia") < end_hour)
        )
        self.window_intervals = demand["franja_15m"].unique().sort().to_list()
        self.rates_by_window = {
            window: dict(
                zip(group["CODIGO_ESTACION"], group["lambda_segundo"], strict=True)
            )
            for (window,), group in demand.group_by(["franja_15m"])
        }

        self.stations = {}
        self.bays = {}
        for row in self.df_topology.iter_rows(named=True):
            self.stations[row["codigo"]] = Station(
                station_code=row["codigo"],
                name=row["nombre"],
                sequence=row["secuencia"],
                lat=row["lat"],
                lon=row["lon"],
                next_distance_m=row["distancia_siguiente_m"],
                travel_time_sec=row["tiempo_viaje_seg"],
            )
            self.bays[row["codigo"]] = simpy.Resource(env, capacity=int(row["bahias"]))

        self.collector = SimulationCollector(start_hour=start_hour)
        self.simulated_buses = []
        self.dispatch_delays_sec = []
        self.passenger_id_counter = 1
        self.passengers_exited_south = 0
        self.od_counts = Counter()

    # ---------------------------------------------------------------- demand
    def demand_updater_process(self, env: simpy.Environment):
        """Updates the Poisson rates lambda(s, t) at every 15-minute window."""
        for window in self.window_intervals:
            rates = self.rates_by_window.get(window, {})
            for code, station in self.stations.items():
                station.current_arrival_rate = float(rates.get(code, 0.0))
            yield env.timeout(DEMAND_WINDOW_SEC)
        for station in self.stations.values():
            station.current_arrival_rate = 0.0

    def passenger_arrival_process(
        self, env: simpy.Environment, station: Station, rng: random.Random
    ):
        """Non-homogeneous Poisson arrivals with gravity-based destinations."""
        position = self.station_position[station.station_code]
        destinations = [*self.ordered_station_codes[position + 1 :], SOUTH_SINK_CODE]
        weights = [
            self.scenario.attraction_weights.get(code, 0.0) for code in destinations
        ]
        if sum(weights) <= 0:
            return

        while True:
            rate = station.current_arrival_rate
            if rate <= 0:
                # No observed demand in this window: wait for the next update.
                yield env.timeout(DEMAND_WINDOW_SEC - env.now % DEMAND_WINDOW_SEC)
                continue
            yield env.timeout(rng.expovariate(rate))
            passenger = Passenger(
                passenger_id=self.passenger_id_counter,
                origin_station=station.station_code,
                destination_station=rng.choices(destinations, weights=weights, k=1)[0],
                arrival_time_sec=env.now,
            )
            self.passenger_id_counter += 1
            station.register_arrival(passenger)
            self.od_counts[
                (passenger.origin_station, passenger.destination_station)
            ] += 1

    def queue_monitor_process(self, env: simpy.Environment):
        """Samples platform queue lengths Q(t) every 60 seconds."""
        while True:
            for station in self.stations.values():
                self.collector.record_station_queue(
                    time_sec=env.now,
                    station_code=station.station_code,
                    station_name=station.name,
                    queue_size=len(station.waiting_queue),
                )
            yield env.timeout(QUEUE_SAMPLE_SEC)

    # ---------------------------------------------------------------- supply
    def _record_position(
        self, env: simpy.Environment, bus: Bus, station: Station
    ) -> None:
        self.collector.record_bus_position(
            time_sec=env.now,
            bus_id=bus.bus_id,
            route=bus.route,
            lat=station.lat,
            lon=station.lon,
            occupancy=bus.occupancy_rate,
            passengers=bus.total_passengers,
            vehicle_id=bus.vehicle_id,
        )

    def bus_trip_process(self, env: simpy.Environment, bus: Bus, service: ServiceSpec):
        """Physical trip from the service's first to last corridor stop."""
        first = self.station_position[service.stops[0]]
        last = self.station_position[service.stops[-1]]
        stops = set(service.stops)
        served = service.served_destinations

        for position in range(first, last + 1):
            code = self.ordered_station_codes[position]
            station = self.stations[code]

            if code in stops:
                with self.bays[code].request() as bay:
                    yield bay
                    self._record_position(env, bus, station)

                    alighting = [
                        p
                        for p in bus.onboard_passengers
                        if p.destination_station == code
                    ]
                    bus.onboard_passengers = [
                        p
                        for p in bus.onboard_passengers
                        if p.destination_station != code
                    ]
                    station.total_alightings += len(alighting)

                    boarding = station.board_passengers(served, bus.available_capacity)
                    for passenger in boarding:
                        passenger.boarding_time_sec = env.now
                        station.cumulative_waiting_time_sec += (
                            env.now - passenger.arrival_time_sec
                        )
                    bus.onboard_passengers.extend(boarding)

                    bus.occupancy_history.append(bus.occupancy_rate)
                    bus.passenger_profile_by_stop.append(
                        {
                            "estacion": station.name,
                            "secuencia": station.sequence,
                            "suben": len(boarding),
                            "bajan": len(alighting),
                            "a_bordo": bus.total_passengers,
                            "ocupacion_pct": round(bus.occupancy_rate * 100, 1),
                        }
                    )
                    yield env.timeout(
                        calculate_dwell_time_sec(len(boarding), len(alighting))
                    )
                    self._record_position(env, bus, station)
            else:
                self._record_position(env, bus, station)

            if position < last:
                yield env.timeout(station.travel_time_sec)

        # Remaining passengers continue beyond the corridor (south sink).
        self.passengers_exited_south += bus.total_passengers
        bus.onboard_passengers = []

    def _return_vehicle(
        self,
        env: simpy.Environment,
        pool: simpy.Store,
        vehicle_id: str,
        delay_sec: float,
    ):
        yield env.timeout(max(0.0, delay_sec))
        yield pool.put(vehicle_id)

    def _run_trip(
        self,
        env: simpy.Environment,
        bus: Bus,
        service: ServiceSpec,
        pool: simpy.Store | None,
    ):
        departure = env.now
        yield env.process(self.bus_trip_process(env, bus, service))
        if pool is not None:
            corridor_time = env.now - departure
            env.process(
                self._return_vehicle(
                    env,
                    pool,
                    bus.vehicle_id,
                    service.cycle_time_min * 60.0 - corridor_time,
                )
            )

    def dispatch_loop(
        self,
        env: simpy.Environment,
        service: ServiceSpec,
        headway_min: float,
        fleet_size: int | None,
        rng: random.Random,
    ):
        """
        Dispatches trips every ``headway_min``. With a fleet pool, a trip waits for
        a free vehicle; the delay is recorded and the timetable is not shifted.
        """
        interval = headway_min * 60.0
        first_departure = rng.uniform(0.0, interval)
        pool: simpy.Store | None = None
        if fleet_size is not None:
            pool = simpy.Store(env)
            for index in range(fleet_size):
                pool.items.append(f"{service.route}-V{index + 1:03d}")

        trip_number = 0
        while True:
            scheduled = first_departure + trip_number * interval
            if env.now < scheduled:
                yield env.timeout(scheduled - env.now)
            trip_number += 1
            if pool is not None:
                vehicle_id = yield pool.get()
                self.dispatch_delays_sec.append(env.now - scheduled)
            else:
                vehicle_id = f"{service.route}-T{trip_number:03d}"

            bus = Bus(
                bus_id=f"{service.route}_{trip_number}",
                route=service.route,
                max_capacity=service.capacity,
                scheduled_stops=list(service.stops),
                vehicle_id=vehicle_id,
            )
            self.simulated_buses.append(bus)
            env.process(self._run_trip(env, bus, service, pool))

    # ------------------------------------------------------------ simulation
    def simulate(
        self,
        headways: dict[str, float],
        start_hour: int = 6,
        end_hour: int = 9,
        duration_hours: float | None = None,
        seed: int = 42,
    ) -> SimulationResult:
        """
        Run one simulation.

        Args:
            headways: Headway (minutes) per optimizable route. Routes not listed
                (background services) run their GTFS headway.
            start_hour: Simulation start hour (default 6 AM).
            end_hour: Simulation end hour (default 9 AM).
            duration_hours: Optional override for the simulated length.
            seed: Seed of the pseudo-random generator.
        """
        if duration_hours is not None:
            end_hour = start_hour + math.ceil(duration_hours)
        duration_seconds = (
            duration_hours * 3600.0
            if duration_hours is not None
            else (end_hour - start_hour) * 3600.0
        )

        env = simpy.Environment()
        self.reset_environment(env, start_hour, end_hour)
        rng = random.Random(seed)

        env.process(self.demand_updater_process(env))
        env.process(self.queue_monitor_process(env))
        for station in self.stations.values():
            env.process(self.passenger_arrival_process(env, station, rng))

        for route, service in self.scenario.services.items():
            if route in headways:
                headway = headways[route]
                fleet = (
                    math.ceil(service.leg_time_min / headway) + service.return_fleet
                    if service.is_optimizable
                    else None
                )
            else:
                headway, fleet = service.headway_gtfs_min, None
            env.process(self.dispatch_loop(env, service, headway, fleet, rng))

        env.run(until=duration_seconds)
        return self._build_result(env, list(headways))

    def _build_result(
        self, env: simpy.Environment, evaluated_routes: list[str]
    ) -> SimulationResult:
        stations = sorted(self.stations.values(), key=lambda s: s.sequence)
        # Passengers still waiting have waited until the end of the run.
        for station in stations:
            station.cumulative_waiting_time_sec += sum(
                env.now - p.arrival_time_sec for p in station.waiting_queue
            )

        total_arrivals = sum(s.total_arrivals for s in stations)
        total_wait_sec = sum(s.cumulative_waiting_time_sec for s in stations)
        occupancies = [
            occ for bus in self.simulated_buses for occ in bus.occupancy_history
        ]
        overcrowded_pct = (
            sum(occ >= OVERCROWDED_LOAD_FACTOR for occ in occupancies)
            / len(occupancies)
            * 100
            if occupancies
            else 0.0
        )

        station_metrics = [
            {
                "codigo": s.station_code,
                "nombre": s.name,
                "secuencia": s.sequence,
                "llegadas_torniquete": s.total_arrivals,
                "abordajes_bus": s.total_boardings,
                "descensos_torniquete": s.total_alightings,
                "cola_final": len(s.waiting_queue),
                "espera_promedio_min": round(
                    s.cumulative_waiting_time_sec / max(1, s.total_arrivals) / 60.0, 2
                ),
            }
            for s in stations
        ]

        return SimulationResult(
            avg_waiting_time_min=total_wait_sec / max(1, total_arrivals) / 60.0,
            avg_occupancy_rate=sum(occupancies) / max(1, len(occupancies)),
            overcrowded_bus_pct=overcrowded_pct,
            total_transported_passengers=sum(s.total_boardings for s in stations),
            stranded_passengers_in_queue=sum(len(s.waiting_queue) for s in stations),
            total_dispatched_buses=len(self.simulated_buses),
            station_metrics=station_metrics,
            route_load_profiles=self._route_load_profiles(evaluated_routes),
            od_counts=dict(self.od_counts),
            avg_dispatch_delay_min=(
                sum(self.dispatch_delays_sec) / len(self.dispatch_delays_sec) / 60.0
                if self.dispatch_delays_sec
                else 0.0
            ),
        )

    def _route_load_profiles(self, routes: list[str]) -> dict[str, list[dict]]:
        """Mean load, boardings and alightings per stop for each route."""
        profiles: dict[str, list[dict]] = {}
        for route in routes:
            records = [
                record
                for bus in self.simulated_buses
                if bus.route == route
                for record in bus.passenger_profile_by_stop
            ]
            if not records:
                continue
            capacity = self.scenario.services[route].capacity
            profile = (
                pl.DataFrame(records)
                .group_by(["estacion", "secuencia"])
                .agg(
                    pl.col("a_bordo").mean().round(1).alias("promedio_a_bordo"),
                    pl.col("suben").mean().round(1).alias("promedio_suben"),
                    pl.col("bajan").mean().round(1).alias("promedio_bajan"),
                )
                .with_columns(
                    (pl.col("promedio_a_bordo") / capacity * 100)
                    .round(1)
                    .alias("ocupacion_pct")
                )
                .sort("secuencia")
            )
            profiles[route] = profile.to_dicts()
        return profiles
