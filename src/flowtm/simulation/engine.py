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
High-fidelity Discrete Event Simulation (DES) Engine implemented on SimPy.
Simulates non-homogeneous Poisson passenger arrivals, dynamic non-linear dwell times,
and simultaneous multi-route vehicle dispatches along the Caracas-Autonorte BRT corridor.
"""

import random
from pathlib import Path

import polars as pl
import simpy

from flowtm.domain.models import Bus, Passenger, SimulationResult, Station
from flowtm.simulation.collector import SimulationCollector
from flowtm.simulation.dwell_time import calculate_dwell_time_sec

# Canonical stop mapping for the 6 official trunk routes along the pilot corridor
# Stations ordered from North (Portal Norte 02000) to South (Calle 45 09117)
OFFICIAL_ROUTE_STOPS: dict[str, list[str]] = {
    # B13: High-frequency trunk spine connecting Portal Norte through Autonorte & Caracas to Calle 45
    "B13": [
        "02000",
        "02101",
        "02102",
        "02103",
        "02104",
        "02200",
        "02205",
        "02300",
        "02303",
        "09127",
        "09120",
        "09117",
    ],
    # B18: Express connecting Portal Norte to 20 de Julio via major transfer hubs and Caracas
    "B18": [
        "02000",
        "02101",
        "02200",
        "02204",
        "02300",
        "02302",
        "02304",
        "09122",
        "09127",
    ],
    # B23: Express connecting Portal Norte / Alcala to Eldorado via Prado, Pepe Sierra and Caracas
    "B23": [
        "02000",
        "02103",
        "02200",
        "02201",
        "02204",
        "02300",
        "02303",
        "09122",
        "09117",
    ],
    # B27: Heavy-spine high capacity trunk connecting Tunal through key hubs to Calle 45
    "B27": [
        "02000",
        "02101",
        "02104",
        "02200",
        "02300",
        "02302",
        "02304",
        "09122",
        "09117",
    ],
    # B74: High-capacity express connecting Universidades to Portal Norte
    "B74": [
        "02000",
        "02101",
        "02103",
        "02104",
        "02201",
        "02300",
        "02302",
        "02304",
        "09122",
        "09117",
    ],
    # B75: High-frequency trunk express serving Usme corridor via Caracas hubs
    "B75": [
        "02000",
        "02101",
        "02104",
        "02200",
        "02201",
        "02300",
        "02304",
        "09122",
        "09127",
        "09120",
        "09117",
    ],
}


class CorridorSimulator:
    """
    Simulates dynamic passenger and fleet operations along the BRT trunk corridor.
    """

    def __init__(self, scenario_dir: Path) -> None:
        self.scenario_dir = Path(scenario_dir)
        self.df_topology = pl.read_parquet(
            self.scenario_dir / "estaciones_piloto.parquet"
        )
        self.ordered_station_codes: list[str] = self.df_topology.sort("secuencia")[
            "codigo"
        ].to_list()

        # Full day arrival rate demand profile
        self.df_demand_full = pl.read_parquet(
            self.scenario_dir / "demanda_lambda_dia_completo.parquet"
        )

        # Empirical destination attraction weights calibrated from tap-out telemetry
        df_alightings = pl.read_parquet(self.scenario_dir / "pesos_descenso.parquet")
        self.attraction_weights: dict[str, float] = {
            row["CODIGO_ESTACION"]: row["peso_atraccion"]
            for row in df_alightings.iter_rows(named=True)
        }

        self.collector = SimulationCollector()
        self.passenger_id_counter = 1
        self.stations: dict[str, Station] = {}
        self.simulated_buses: list[Bus] = []

    def reset_environment(
        self, env: simpy.Environment, start_hour: int, end_hour: int
    ) -> None:
        """Initializes simulation entities, platform resources, and demand windows."""
        self.df_demand_window = self.df_demand_full.filter(
            (pl.col("hora_del_dia") >= start_hour) & (pl.col("hora_del_dia") < end_hour)
        )
        self.window_intervals = (
            self.df_demand_window["franja_15m"].unique().sort().to_list()
        )

        self.stations = {}
        for r in self.df_topology.iter_rows(named=True):
            station = Station(
                station_code=r["codigo"],
                name=r["nombre"],
                sequence=r["secuencia"],
                lat=r["lat"],
                lon=r["lon"],
                next_distance_m=r["distancia_siguiente_m"],
                travel_time_sec=r["tiempo_viaje_seg"],
            )
            # Physical platform docking bay capacity (2 articulated vehicles simultaneously)
            station.bay_resource = simpy.Resource(env, capacity=2)
            station.recurso_bahia = station.bay_resource
            self.stations[r["codigo"]] = station

        self.collector = SimulationCollector()
        self.passenger_id_counter = 1
        self.simulated_buses = []

    def demand_updater_process(self, env: simpy.Environment):
        """Periodically updates Poisson arrival rates lambda(s, t) every 15 minutes."""
        interval_idx = 0
        while True:
            if interval_idx < len(self.window_intervals):
                current_interval = self.window_intervals[interval_idx]
                df_interval = self.df_demand_window.filter(
                    pl.col("franja_15m") == current_interval
                )
                for row in df_interval.iter_rows(named=True):
                    code = row["CODIGO_ESTACION"]
                    if code in self.stations:
                        self.stations[code].current_arrival_rate = row["lambda_segundo"]
                interval_idx += 1
            yield env.timeout(900.0)

    def passenger_arrival_process(
        self, env: simpy.Environment, station: Station, rng: random.Random
    ):
        """Simulates stochastic passenger arrivals via Non-Homogeneous Poisson Process (NHPP)."""
        downstream_destinations = [
            code
            for code in self.ordered_station_codes
            if self.stations[code].sequence > station.sequence
        ]
        if not downstream_destinations:
            return

        destination_weights = [
            self.attraction_weights.get(code, 0.05) for code in downstream_destinations
        ]

        while True:
            rate = max(0.005, station.current_arrival_rate)
            delta_t = rng.expovariate(rate)
            yield env.timeout(delta_t)

            selected_destination = rng.choices(
                downstream_destinations, weights=destination_weights, k=1
            )[0]
            passenger = Passenger(
                passenger_id=self.passenger_id_counter,
                origin_station=station.station_code,
                destination_station=selected_destination,
                arrival_time_sec=env.now,
            )
            self.passenger_id_counter += 1
            station.register_arrival(passenger)
            station.cumulative_waiting_time_sec += len(station.waiting_queue) * delta_t

    def bus_trip_process(self, env: simpy.Environment, bus: Bus, rng: random.Random):
        """Models the physical trip of a vehicle traversing the corridor stations."""
        for code in self.ordered_station_codes:
            station = self.stations[code]

            # If skip-stop express service, bypass platform dwell time
            if code not in bus.scheduled_stops:
                self.collector.record_bus_position(
                    time_sec=env.now,
                    bus_id=bus.bus_id,
                    route=bus.route,
                    lat=station.lat,
                    lon=station.lon,
                    occupancy=bus.occupancy_rate,
                    passengers=bus.total_passengers,
                )
                yield env.timeout(station.travel_time_sec)
                continue

            with station.bay_resource.request() as bay_request:
                yield bay_request

                # Telemetry record 1: Platform Arrival (doors open, arriving load on board)
                # Bus arrives carrying the exact passengers that traveled from the previous station
                self.collector.record_bus_position(
                    time_sec=env.now,
                    bus_id=bus.bus_id,
                    route=bus.route,
                    lat=station.lat,
                    lon=station.lon,
                    occupancy=bus.occupancy_rate,
                    passengers=bus.total_passengers,
                )

                # 1. Alighting passengers
                alighting_passengers = [
                    p for p in bus.onboard_passengers if p.destination_station == code
                ]
                bus.onboard_passengers = [
                    p for p in bus.onboard_passengers if p.destination_station != code
                ]
                alighting_count = len(alighting_passengers)
                station.total_alightings += alighting_count

                # 2. Boarding passengers
                available_capacity = bus.available_capacity
                boarding_passengers = station.board_passengers(
                    bus.scheduled_stops, available_capacity
                )
                for p in boarding_passengers:
                    p.boarding_time_sec = env.now
                bus.onboard_passengers.extend(boarding_passengers)
                boarding_count = len(boarding_passengers)

                # Record load profile (post-exchange departing load for this stop)
                bus.occupancy_history.append(bus.occupancy_rate)
                bus.passenger_profile_by_stop.append(
                    {
                        "estacion": station.name,
                        "secuencia": station.sequence,
                        "suben": boarding_count,
                        "bajan": alighting_count,
                        "a_bordo": bus.total_passengers,
                        "ocupacion_pct": round(bus.occupancy_rate * 100, 1),
                    }
                )

                # 3. Dynamic dwell time (seconds stopped at station bay)
                dwell_sec = calculate_dwell_time_sec(boarding_count, alighting_count)
                yield env.timeout(dwell_sec)

                # Telemetry record 2: Platform Departure (doors closed, post-exchange load on board)
                self.collector.record_bus_position(
                    time_sec=env.now,
                    bus_id=bus.bus_id,
                    route=bus.route,
                    lat=station.lat,
                    lon=station.lon,
                    occupancy=bus.occupancy_rate,
                    passengers=bus.total_passengers,
                )

            yield env.timeout(station.travel_time_sec)

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
            yield env.timeout(60.0)

    def dispatch_loop(
        self,
        env: simpy.Environment,
        route: str,
        headway_min: float,
        base_id: int,
        rng: random.Random,
    ):
        """Continuously dispatches buses at the prescribed headway interval."""
        id_counter = base_id
        interval_sec = headway_min * 60.0

        scheduled_stops = OFFICIAL_ROUTE_STOPS.get(route, self.ordered_station_codes)
        # Ensure stops belong to this corridor slice
        corridor_stops = [
            code for code in scheduled_stops if code in self.ordered_station_codes
        ]
        if not corridor_stops:
            corridor_stops = self.ordered_station_codes

        while True:
            bus = Bus(
                bus_id=f"{route}_{id_counter}",
                route=route,
                max_capacity=160,
                scheduled_stops=corridor_stops,
            )
            self.simulated_buses.append(bus)
            env.process(self.bus_trip_process(env, bus, rng))
            id_counter += 1
            yield env.timeout(interval_sec)

    def simulate(
        self,
        headways: dict[str, float],
        start_hour: int = 6,
        end_hour: int = 9,
        duration_hours: float | None = None,
        seed: int = 42,
    ) -> SimulationResult:
        """
        Executes a discrete event simulation run for the given headway schedule.

        Args:
            headways: Dictionary mapping route codes to dispatch headways in minutes.
            start_hour: Simulation start hour (default 6 AM).
            end_hour: Simulation end hour (default 9 AM).
            duration_hours: Optional override for simulation length in hours.
            seed: Pseudo-random generator seed for reproducible stochastic runs.

        Returns:
            A SimulationResult object with aggregate KPIs and granular metrics.
        """
        if duration_hours is not None:
            end_hour = start_hour + int(duration_hours)

        env = simpy.Environment()
        self.reset_environment(env, start_hour, end_hour)
        sim_rng = random.Random(seed)

        env.process(self.demand_updater_process(env))
        env.process(self.queue_monitor_process(env))

        for station in self.stations.values():
            env.process(self.passenger_arrival_process(env, station, sim_rng))

        bus_id_base = 1
        for route_code, interval_min in headways.items():
            env.process(
                self.dispatch_loop(env, route_code, interval_min, bus_id_base, sim_rng)
            )
            bus_id_base += 1000

        duration_seconds = (end_hour - start_hour) * 3600.0
        env.run(until=duration_seconds)

        # Aggregate corridor performance metrics
        total_transported = sum(s.total_boardings for s in self.stations.values())
        total_arrivals = sum(s.total_arrivals for s in self.stations.values())
        remaining_queue = sum(len(s.waiting_queue) for s in self.stations.values())

        total_wait_sec = sum(
            s.cumulative_waiting_time_sec for s in self.stations.values()
        )
        avg_wait_min = (total_wait_sec / max(1, total_arrivals)) / 60.0

        all_occupancies = [
            occ for bus in self.simulated_buses for occ in bus.occupancy_history
        ]
        avg_occupancy = sum(all_occupancies) / max(1, len(all_occupancies))
        overcrowded_pct = (
            sum(1 for occ in all_occupancies if occ >= 0.95)
            / max(1, len(all_occupancies))
            * 100
            if all_occupancies
            else 0.0
        )

        # Granular per-station metrics
        station_metrics = [
            {
                "codigo": station.station_code,
                "nombre": station.name,
                "secuencia": station.sequence,
                "llegadas_torniquete": station.total_arrivals,
                "abordajes_bus": station.total_boardings,
                "descensos_torniquete": station.total_alightings,
                "cola_final": len(station.waiting_queue),
                "cola_corriente": station.local_queue_count,
                "cola_expreso": station.express_queue_count,
                "espera_promedio_min": round(
                    (
                        station.cumulative_waiting_time_sec
                        / max(1, station.total_arrivals)
                    )
                    / 60.0,
                    1,
                ),
            }
            for station in sorted(self.stations.values(), key=lambda s: s.sequence)
        ]

        # Consolidate load profiles per route
        route_profiles: dict[str, list[dict]] = {}
        for r in headways:
            route_buses = [
                b
                for b in self.simulated_buses
                if b.route == r and b.passenger_profile_by_stop
            ]
            if route_buses:
                station_records: dict[str, dict] = {}
                for b in route_buses:
                    for reg in b.passenger_profile_by_stop:
                        st_name = reg["estacion"]
                        if st_name not in station_records:
                            station_records[st_name] = {
                                "nombre": st_name,
                                "secuencia": reg["secuencia"],
                                "a_bordo": [],
                                "suben": [],
                                "bajan": [],
                            }
                        station_records[st_name]["a_bordo"].append(reg["a_bordo"])
                        station_records[st_name]["suben"].append(reg["suben"])
                        station_records[st_name]["bajan"].append(reg["bajan"])

                stats_list = []
                sorted_records = sorted(
                    station_records.values(), key=lambda d: d["secuencia"]
                )
                for data in sorted_records:
                    mean_load = sum(data["a_bordo"]) / max(1, len(data["a_bordo"]))
                    mean_board = sum(data["suben"]) / max(1, len(data["suben"]))
                    mean_alight = sum(data["bajan"]) / max(1, len(data["bajan"]))
                    stats_list.append(
                        {
                            "estacion": data["nombre"],
                            "secuencia": data["secuencia"],
                            "promedio_a_bordo": round(mean_load, 1),
                            "promedio_suben": round(mean_board, 1),
                            "promedio_bajan": round(mean_alight, 1),
                            "ocupacion_pct": round((mean_load / 160.0) * 100, 1),
                        }
                    )
                route_profiles[r] = stats_list

        return SimulationResult(
            avg_waiting_time_min=avg_wait_min,
            avg_occupancy_rate=avg_occupancy,
            overcrowded_bus_pct=overcrowded_pct,
            total_transported_passengers=total_transported,
            stranded_passengers_in_queue=remaining_queue,
            total_dispatched_buses=len(self.simulated_buses),
            station_metrics=station_metrics,
            route_load_profiles=route_profiles,
        )

    # Backward compatibility aliases
    def simular(
        self,
        frecuencias: dict,
        hora_inicio: int = 6,
        hora_fin: int = 9,
        duracion_horas: float | None = None,
        semilla: int = 42,
    ) -> SimulationResult:
        return self.simulate(
            headways=frecuencias,
            start_hour=hora_inicio,
            end_hour=hora_fin,
            duration_hours=duracion_horas,
            seed=semilla,
        )

    @property
    def estaciones_dict(self) -> dict[str, Station]:
        return self.stations

    @property
    def codigos_ordenados(self) -> list[str]:
        return self.ordered_station_codes

    @property
    def buses_simulados(self) -> list[Bus]:
        return self.simulated_buses


# Class alias for backward compatibility
SimuladorCorredor = CorridorSimulator
