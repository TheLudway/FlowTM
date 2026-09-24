import pytest
import pandas as pd
import datetime

def test_aggregate_station_incidents():
    # Mock telemetría de andenes (Q > 150)
    data = [
        {"codigo_estacion": "EST_01", "cola_pasajeros": 120, "tiempo_seg": 0},
        {"codigo_estacion": "EST_01", "cola_pasajeros": 155, "tiempo_seg": 30},
        {"codigo_estacion": "EST_01", "cola_pasajeros": 180, "tiempo_seg": 60},
        {"codigo_estacion": "EST_01", "cola_pasajeros": 140, "tiempo_seg": 90},
        {"codigo_estacion": "EST_02", "cola_pasajeros": 150, "tiempo_seg": 30},
        {"codigo_estacion": "EST_02", "cola_pasajeros": 150, "tiempo_seg": 120}
    ]
    colas_df = pd.DataFrame(data)
    
    # Lógica del dashboard:
    df_incidentes_est = colas_df[colas_df["cola_pasajeros"] >= 150].copy()
    
    assert len(df_incidentes_est) == 4, "Debe filtrar solo momentos con >= 150 pax"
    
    hist_est = df_incidentes_est.groupby("codigo_estacion").agg(
        Pico_Maximo=("cola_pasajeros", "max"),
        Inicio_Colapso=("tiempo_seg", "min"),
        Fin_Colapso=("tiempo_seg", "max")
    ).reset_index()
    
    # Verify EST_01 logic
    est_01_res = hist_est[hist_est["codigo_estacion"] == "EST_01"].iloc[0]
    assert est_01_res["Pico_Maximo"] == 180
    assert est_01_res["Inicio_Colapso"] == 30
    assert est_01_res["Fin_Colapso"] == 60

    # Verify EST_02 logic
    est_02_res = hist_est[hist_est["codigo_estacion"] == "EST_02"].iloc[0]
    assert est_02_res["Pico_Maximo"] == 150
    assert est_02_res["Inicio_Colapso"] == 30
    assert est_02_res["Fin_Colapso"] == 120


def test_aggregate_bus_incidents():
    # Mock telemetría de buses (pax >= 152)
    data = [
        {"id_bus": "B_01", "ruta": "B10", "pasajeros": 151, "tiempo_seg": 0},
        {"id_bus": "B_01", "ruta": "B10", "pasajeros": 155, "tiempo_seg": 30},
        {"id_bus": "B_01", "ruta": "B10", "pasajeros": 160, "tiempo_seg": 60},
        {"id_bus": "B_02", "ruta": "B27", "pasajeros": 90, "tiempo_seg": 30},
    ]
    buses_df = pd.DataFrame(data)
    
    df_incidentes_bus = buses_df[buses_df["pasajeros"] >= 152].copy()
    
    assert len(df_incidentes_bus) == 2
    
    hist_bus = df_incidentes_bus.groupby(["id_bus", "ruta"]).agg(
        Pico_Ocupacion=("pasajeros", "max"),
        Inicio_Sobrecupo=("tiempo_seg", "min"),
        Fin_Sobrecupo=("tiempo_seg", "max")
    ).reset_index()
    
    b_01_res = hist_bus[hist_bus["id_bus"] == "B_01"].iloc[0]
    assert b_01_res["ruta"] == "B10"
    assert b_01_res["Pico_Ocupacion"] == 160
    assert b_01_res["Inicio_Sobrecupo"] == 30
    assert b_01_res["Fin_Sobrecupo"] == 60
