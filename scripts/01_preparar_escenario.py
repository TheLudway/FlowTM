
"""
scripts/01_preparar_escenario.py
Extractor de Demanda de Dia Completo (04:00 a 23:00) y Distancias Metricas
Troncal Autonorte - Caracas | FlowTM - Digital Twin Engine
"""

import math
from pathlib import Path
import polars as pl

# 1. Rutas del proyecto con rutas canonicas a validacionesy salidas
ROOT_DIR = Path(__file__).resolve().parent.parent
dir_clean_val = ROOT_DIR / "data/processed/validaciones_salidas/validacion_troncal"
dir_clean_sal = ROOT_DIR / "data/processed/validaciones_salidas/salidas_troncal"
dir_scenario = ROOT_DIR / "data/scenarios/piloto"
dir_scenario.mkdir(parents=True, exist_ok=True)

print("=" * 80)
print("EXTRACTOR DE DIA COMPLETO (04:00 - 23:00) Y DISTANCIAS - FlowTM")
print("=" * 80)

# 2. Topologia y Distancias Reales desde Coordenadas de Infraestructura
ESTACIONES_GEO = [
    {"codigo": "02000", "nombre": "PORTAL NORTE", "secuencia": 1,  "lat": 4.7544, "lon": -74.0460},
    {"codigo": "02101", "nombre": "TOBERIN",      "secuencia": 2,  "lat": 4.7458, "lon": -74.0489},
    {"codigo": "02102", "nombre": "CALLE 161",    "secuencia": 3,  "lat": 4.7397, "lon": -74.0506},
    {"codigo": "02103", "nombre": "MAZUREN",      "secuencia": 4,  "lat": 4.7314, "lon": -74.0532},
    {"codigo": "02104", "nombre": "CALLE 146",    "secuencia": 5,  "lat": 4.7237, "lon": -74.0555},
    {"codigo": "02200", "nombre": "ALCALA",       "secuencia": 6,  "lat": 4.7153, "lon": -74.0579},
    {"codigo": "02201", "nombre": "PRADO",        "secuencia": 7,  "lat": 4.7061, "lon": -74.0577},
    {"codigo": "02204", "nombre": "PEPE SIERRA",  "secuencia": 8,  "lat": 4.6983, "lon": -74.0571},
    {"codigo": "02205", "nombre": "CALLE 106",    "secuencia": 9,  "lat": 4.6920, "lon": -74.0570},
    {"codigo": "02300", "nombre": "CALLE 100",    "secuencia": 10, "lat": 4.6853, "lon": -74.0583},
    {"codigo": "02302", "nombre": "VIRREY",       "secuencia": 11, "lat": 4.6739, "lon": -74.0607},
    {"codigo": "02303", "nombre": "CALLE 85",     "secuencia": 12, "lat": 4.6677, "lon": -74.0620},
    {"codigo": "02304", "nombre": "HEROES",       "secuencia": 13, "lat": 4.6622, "lon": -74.0634},
    {"codigo": "09122", "nombre": "CALLE 72",     "secuencia": 14, "lat": 4.6558, "lon": -74.0623},
    {"codigo": "09127", "nombre": "FLLORES",       "secuencia": 15, "lat": 4.6493, "lon": -74.0637},
    {"codigo": "09120", "nombre": "CALLE 63",     "secuencia": 16, "lat": 4.6428, "lon": -74.0655},
    {"codigo": "09117", "nombre": "CALLE 45",     "secuencia": 17, "lat": 4.6325, "lon": -74.0681},
]

def dist_haversine(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1) * math.cos(p2) * math.sin(dl/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

for i in range(len(ESTACIONES_GEO)):
    if i < len(ESTACIONES_GEO) - 1:
        d = dist_haversine(ESTACIONES_GEO[i]["lat"], ESTACIONES_GEO[i]["lon"], ESTACIONES_GEO[i+1]["lat"], ESTACIONES_GEO[i+1]["lon"])
        ESTACIONES_GEO[i]["distancia_siguiente_m"] = round(d, 1)
        ESTACIONES_GEO[i]["tiempo_viaje_seg"] = round((d / 6.11) + 15.0, 1)
    else:
        ESTACIONES_GEO[i]["distancia_siguiente_m"] = 0.0
        ESTACIONES_GEO[i]["tiempo_viaje_seg"] = 0.0

df_topo = pl.DataFrame(ESTACIONES_GEO)
df_topo.write_parquet(dir_scenario / "estaciones_piloto.parquet")

# 3. Demanda Dinamica (04:00 a 23:00) con filtro de Dias Habiles (Dia 1) y Factor de Oferta alpha = 0.25
pattern_val = str(dir_clean_val / "*_clean.parquet")
codigos_corredor = [e["codigo"] for e in ESTACIONES_GEO]
FACTOR_OFERTA_RUTAS = 0.25

lazy_val = (
    pl.scan_parquet(pattern_val)
    .filter(pl.col("Day_Group_Type") == "Dia 1")
    .filter(pl.col("CODIGO_ESTACION").is_in(codigos_corredor))
    .with_columns([
        pl.col("Fecha_Transaccion").dt.date().alias("fecha"),
        pl.col("Fecha_Transaccion").dt.hour().alias("hora"),
        (pl.col("Fecha_Transaccion").dt.minute() // 15 * 15).alias("minuto")
    ])
    .filter((pl.col("hora") >= 4) & (pl.col("hora") < 23))
)

# Conteo de dias habiles presentes en el conjunto limpio para obtener la demanda diaria promedio
n_dias_habiles = max(1, lazy_val.select(pl.col("fecha").n_unique()).collect().item())

df_demanda_dia = (
    lazy_val
    .group_by(["CODIGO_ESTACION", "hora", "minuto"])
    .agg(pl.len().alias("total_validaciones_periodo"))
    .with_columns([
        (pl.col("total_validaciones_periodo") / n_dias_habiles).alias("pasajeros_15m_totales"),
        ((pl.col("total_validaciones_periodo") / n_dias_habiles) * FACTOR_OFERTA_RUTAS).alias("pasajeros_15m_rutas"),
        (((pl.col("total_validaciones_periodo") / n_dias_habiles) * FACTOR_OFERTA_RUTAS) / 900.0).alias("lambda_segundo"),
        pl.col("hora").cast(pl.Int8).alias("hora_del_dia"),
        pl.datetime(2026, 8, 24, pl.col("hora"), pl.col("minuto"), 0).alias("franja_15m")
    ])
    .sort(["franja_15m", "CODIGO_ESTACION"])
    .collect()
)
df_demanda_dia.write_parquet(dir_scenario / "demanda_lambda_dia_completo.parquet")

# 4. Pesos Reales de Descenso calibrados desde salidas_troncal (*_clean.parquet)
pattern_sal = str(dir_clean_sal / "*_clean.parquet")
df_descenso = (
    pl.scan_parquet(pattern_sal)
    .filter(pl.col("CODIGO_ESTACION").is_in(codigos_corredor))
    .group_by("CODIGO_ESTACION")
    .agg(pl.col("Salidas_S").sum().alias("total_salidas"))
    .collect()
)

total_s = max(1, df_descenso["total_salidas"].sum())
df_pesos = df_descenso.with_columns(res_peso = (pl.col("total_salidas") / total_s)).select(["CODIGO_ESTACION", pl.col("res_peso").alias("peso_atraccion")])
df_pesos.write_parquet(dir_scenario / "pesos_descenso.parquet")

print(f"[EXITO!Topologia guardada: {len(ESTACIONES_GEO)} estaciones incluidas.")
print(f"[EXITO!Demanda generada para dias habiles: {len(df_demanda_dia)} franjas.")
print(f"[EXITO!Pesos de descenso calibrados desde salidas clean parquets.")
print("=" * 80)
