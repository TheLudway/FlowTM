"""
src/flowtm/simulation/engine.py
Motor de Simulación de Alta Fidelidad (SimPy)
FlowTM - Digital Twin Engine
"""

import random
import simpy
from pathlib import Path
import polars as pl
from flowtm.domain.models import Estacion, Bus, Pasajero, ResultadoSimulacion
from flowtm.simulation.dwell_time import calcular_tiempo_parada_seg
from flowtm.simulation.collector import MetricsCollector

class SimuladorCorredor:
    def __init__(self, ruta_escenario: Path):
        self.ruta_escenario = ruta_escenario
        self.df_topo = pl.read_parquet(self.ruta_escenario / "estaciones_piloto.parquet")
        self.codigos_ordenados = self.df_topo.sort("secuencia")["codigo"].to_list()

        # Cargar demanda de día completo
        self.df_demanda_full = pl.read_parquet(self.ruta_escenario / "demanda_lambda_dia_completo.parquet")

        # Cargar pesos reales de descenso
        df_descenso = pl.read_parquet(self.ruta_escenario / "pesos_descenso.parquet")
        self.pesos_dict = {r["CODIGO_ESTACION"]: r["peso_atraccion"] for r in df_descenso.iter_rows(named=True)}

        self.collector = MetricsCollector()
        self.pasajero_id_counter = 1

    def reiniciar_entorno(self, env: simpy.Environment, hora_inicio: int, hora_fin: int):
        self.df_demanda_ventana = self.df_demanda_full.filter(
            (pl.col("hora_del_dia") >= hora_inicio) & (pl.col("hora_del_dia") < hora_fin)
        )
        self.franjas_ventana = self.df_demanda_ventana["franja_15m"].unique().sort().to_list()

        self.estaciones_dict = {}
        for r in self.df_topo.iter_rows(named=True):
            est = Estacion(
                codigo=r["codigo"], nombre=r["nombre"], secuencia=r["secuencia"],
                lat=r["lat"], lon=r["lon"],
                distancia_siguiente_m=r["distancia_siguiente_m"],
                tiempo_viaje_seg=r["tiempo_viaje_seg"]
            )
            est.recurso_bahia = simpy.Resource(env, capacity=2)
            self.estaciones_dict[r["codigo"]] = est

        self.collector = MetricsCollector()
        self.pasajero_id_counter = 1

    def proceso_actualizador_demanda(self, env: simpy.Environment):
        idx = 0
        while True:
            if idx < len(self.franjas_ventana):
                franja_actual = self.franjas_ventana[idx]
                df_f = self.df_demanda_ventana.filter(pl.col("franja_15m") == franja_actual)
                for row in df_f.iter_rows(named=True):
                    if row["CODIGO_ESTACION"] in self.estaciones_dict:
                        self.estaciones_dict[row["CODIGO_ESTACION"]].lambda_actual = row["lambda_segundo"]
                idx += 1
            yield env.timeout(900.0)

    def proceso_llegada_pasajeros(self, env: simpy.Environment, estacion: Estacion, rng: random.Random):
        destinos = [c for c in self.codigos_ordenados if self.estaciones_dict[c].secuencia > estacion.secuencia]
        if not destinos:
            return
        pesos = [self.pesos_dict.get(c, 0.05) for c in destinos]

        while True:
            tasa = max(0.005, estacion.lambda_actual)
            delta_t = rng.expovariate(tasa)
            yield env.timeout(delta_t)

            destino = rng.choices(destinos, weights=pesos, k=1)[0]
            p = Pasajero(
                id_pasajero=self.pasajero_id_counter,
                estacion_origen=estacion.codigo,
                estacion_destino=destino,
                tiempo_llegada_seg=env.now
            )
            self.pasajero_id_counter += 1
            estacion.registrar_llegada(p)
            estacion.tiempo_espera_acumulado_seg += len(estacion.cola_pasajeros) * delta_t

    def proceso_bus(self, env: simpy.Environment, bus: Bus, rng: random.Random):
        for codigo in self.codigos_ordenados:
            estacion = self.estaciones_dict[codigo]

            if codigo not in bus.paradas_programadas:
                yield env.timeout(estacion.tiempo_viaje_seg)
                continue

            with estacion.recurso_bahia.request() as req:
                yield req

                bajan_pasajeros = [p for p in bus.pasajeros_a_bordo if p.estacion_destino == codigo]
                bus.pasajeros_a_bordo = [p for p in bus.pasajeros_a_bordo if p.estacion_destino != codigo]
                bajan = len(bajan_pasajeros)
                estacion.total_descensos += bajan

                cupo = bus.capacidad_disponible
                suben_pasajeros = estacion.obtener_pasajeros_aptos(bus.paradas_programadas, cupo)
                for p in suben_pasajeros:
                    p.tiempo_abordaje_seg = env.now
                bus.pasajeros_a_bordo.extend(suben_pasajeros)
                suben = len(suben_pasajeros)

                bus.historial_ocupacion.append(bus.factor_ocupacion)
                bus.perfil_pasajeros_por_parada.append({
                    "estacion": estacion.nombre,
                    "secuencia": estacion.secuencia,
                    "suben": suben,
                    "bajan": bajan,
                    "a_bordo": bus.total_pasajeros,
                    "ocupacion_pct": round(bus.factor_ocupacion * 100, 1)
                })

                self.collector.registrar_posicion_bus(
                    tiempo_seg=env.now, id_bus=bus.id_bus, ruta=bus.ruta,
                    lat=estacion.lat, lon=estacion.lon,
                    ocupacion=bus.factor_ocupacion, pasajeros=bus.total_pasajeros
                )

                t_parada = calcular_tiempo_parada_seg(suben, bajan)
                yield env.timeout(t_parada)

            yield env.timeout(estacion.tiempo_viaje_seg)

    def proceso_monitor_colas(self, env: simpy.Environment):
        while True:
            for est in self.estaciones_dict.values():
                self.collector.registrar_cola_estacion(env.now, est.codigo, est.nombre, len(est.cola_pasajeros))
            yield env.timeout(60.0)

    def simular(self, frecuencias: dict, hora_inicio: int = 6, hora_fin: int = 9, duracion_horas: float | None = None, semilla: int = 42) -> ResultadoSimulacion:
        if duracion_horas is not None:
            hora_fin = hora_inicio + int(duracion_horas)
        env = simpy.Environment()
        self.reiniciar_entorno(env, hora_inicio, hora_fin)
        self.buses_simulados = []
        sim_rng = random.Random(semilla)

        env.process(self.proceso_actualizador_demanda(env))
        env.process(self.proceso_monitor_colas(env))

        for est in self.estaciones_dict.values():
            env.process(self.proceso_llegada_pasajeros(env, est, sim_rng))

        bus_id = 1
        for ruta, intervalo_min in frecuencias.items():
            env.process(self._bucle_despacho(env, ruta, intervalo_min, bus_id, sim_rng))
            bus_id += 1000

        duracion_segundos = (hora_fin - hora_inicio) * 3600.0
        env.run(until=duracion_segundos)

        # Consolidar métricas globales
        total_transportados = sum(e.total_abordajes for e in self.estaciones_dict.values())
        total_llegaron = sum(e.total_llegadas for e in self.estaciones_dict.values())
        cola_remanente = sum(len(e.cola_pasajeros) for e in self.estaciones_dict.values())

        espera_total_seg = sum(e.tiempo_espera_acumulado_seg for e in self.estaciones_dict.values())
        espera_promedio_min = (espera_total_seg / max(1, total_llegaron)) / 60.0

        ocupaciones = [occ for b in self.buses_simulados for occ in b.historial_ocupacion]
        ocupacion_prom = sum(ocupaciones) / max(1, len(ocupaciones))
        sobrecupo_95 = sum(1 for occ in ocupaciones if occ >= 0.95) / max(1, len(ocupaciones)) * 100

        # Consolidar analítica detallada por estación
        stats_estaciones = [
            {
                "codigo": est.codigo,
                "nombre": est.nombre,
                "secuencia": est.secuencia,
                "llegadas_torniquete": est.total_llegadas,
                "abordajes_bus": est.total_abordajes,
                "descensos_torniquete": est.total_descensos,
                "cola_final": len(est.cola_pasajeros),
                "cola_corriente": est.cola_corriente,
                "cola_expreso": est.cola_expreso,
                "espera_promedio_min": round((est.tiempo_espera_acumulado_seg / max(1, est.total_llegadas)) / 60.0, 1)
            }
            for est in sorted(self.estaciones_dict.values(), key=lambda x: x.secuencia)
        ]

        # Consolidar perfil de carga promedio por ruta (100% inmune a buses que terminaron en tránsito)
        # Consolidar perfil de carga promedio por ruta (ordenando diccionarios directamente)
        perfiles = {}
        for r in frecuencias.keys():
            buses_ruta = [b for b in self.buses_simulados if b.ruta == r and b.perfil_pasajeros_por_parada]
            if buses_ruta:
                estacion_records = {}
                for b in buses_ruta:
                    for reg in b.perfil_pasajeros_por_parada:
                        nom = reg["estacion"]
                        if nom not in estacion_records:
                            estacion_records[nom] = {
                                "nombre": nom,
                                "secuencia": reg["secuencia"],
                                "a_bordo": [],
                                "suben": [],
                                "bajan": []
                            }
                        estacion_records[nom]["a_bordo"].append(reg["a_bordo"])
                        estacion_records[nom]["suben"].append(reg["suben"])
                        estacion_records[nom]["bajan"].append(reg["bajan"])

                paradas_stats = []
                # Ordenar directamente los diccionarios por 'secuencia' (sin tuplas)
                lista_ordenada = sorted(estacion_records.values(), key=lambda d: d["secuencia"])
                for data in lista_ordenada:
                    prom_bordo = sum(data["a_bordo"]) / max(1, len(data["a_bordo"]))
                    prom_suben = sum(data["suben"]) / max(1, len(data["suben"]))
                    prom_bajan = sum(data["bajan"]) / max(1, len(data["bajan"]))
                    paradas_stats.append({
                        "estacion": data["nombre"],
                        "secuencia": data["secuencia"],
                        "promedio_a_bordo": round(prom_bordo, 1),
                        "promedio_suben": round(prom_suben, 1),
                        "promedio_bajan": round(prom_bajan, 1),
                        "ocupacion_pct": round((prom_bordo / 160.0) * 100, 1)
                    })
                perfiles[r] = paradas_stats

        return ResultadoSimulacion(
            tiempo_espera_promedio_min=espera_promedio_min,
            factor_ocupacion_promedio=ocupacion_prom,
            porcentaje_buses_sobrecupo=sobrecupo_95,
            total_pasajeros_transportados=total_transportados,
            pasajeros_quedados_en_cola=cola_remanente,
            total_buses_despachados=len(self.buses_simulados),
            metricas_estaciones=stats_estaciones,
            perfil_carga_rutas=perfiles
        )

    def _bucle_despacho(self, env: simpy.Environment, ruta: str, intervalo_min: float, base_id: int, rng: random.Random):
        id_counter = base_id
        intervalo_seg = intervalo_min * 60.0
        
        if ruta == "B27":
            paradas = [c for c in ["02000", "02101", "02104", "02204", "02300", "02304", "09122", "09117"] if c in self.codigos_ordenados]
            if not paradas:
                paradas = self.codigos_ordenados
        else:
            paradas = self.codigos_ordenados

        while True:
            bus = Bus(id_bus=f"{ruta}_{id_counter}", ruta=ruta, capacidad_maxima=160, paradas_programadas=paradas)
            self.buses_simulados.append(bus)
            env.process(self.proceso_bus(env, bus, rng))
            id_counter += 1
            yield env.timeout(intervalo_seg)