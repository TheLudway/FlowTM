"""
src/flowtm/presentation/dashboard/app.py
FlowTM - Digital Twin Engine (Operations Control Center)
"""

import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import polars as pl
import pydeck as pdk
import streamlit as st

from flowtm.domain.state import ScheduleState
from flowtm.infrastructure.repositories.data_repository import ParquetDataRepository
from flowtm.optimization.simulated_annealing import SimulatedAnnealingOptimizer
from flowtm.presentation.dashboard.incidents import (
    aggregate_bus_incidents,
    aggregate_station_incidents,
)
from flowtm.simulation.engine import CorridorSimulator

ROOT_DIR = Path(__file__).resolve().parents[4]

scenario_dir = ROOT_DIR / "data/scenarios/piloto"

st.set_page_config(
    page_title="FlowTM - OCC Digital Twin",
    page_icon="🚍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------
# STYLES (Deluxe OCC Theme)
# -----------------
st.markdown(
    """
<style>
    /* Professional Dark Mode Palette */
    .stApp {
        background-color: #0E1117;
        color: #E6EDF3;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    .stSidebar {
        background-color: #161B22;
        border-right: 1px solid #30363D;
    }

    /* Tabular Monospace Numbers for Metrics */
    [data-testid="stMetricValue"] {
        font-family: 'SF Mono', 'Roboto Mono', 'Consolas', monospace !important;
        font-weight: 700;
        color: #FFFFFF !important;
    }
    [data-testid="stMetricDelta"] {
        font-family: 'SF Mono', 'Roboto Mono', 'Consolas', monospace !important;
    }

    h1, h2, h3, h4, h5 {
        color: #C9D1D9 !important;
        font-weight: 600 !important;
    }

    div[data-testid="metric-container"] {
        background-color: #161B22;
        border: 1px solid #30363D;
        border-radius: 6px;
        padding: 16px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.4);
        transition: transform 0.2s ease;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-2px);
        border-color: #58A6FF;
    }

    /* Live Audit Incident Panel */
    .incident-panel {
        background-color: #161B22;
        border: 1px solid #30363D;
        border-radius: 8px;
        padding: 15px;
        max-height: 500px;
        overflow-y: auto;
    }
    .incident-item {
        background-color: #0D1117;
        border-left: 4px solid #E53935;
        padding: 10px;
        margin-bottom: 8px;
        border-radius: 0 4px 4px 0;
        font-size: 0.9em;
    }
    .incident-warning {
        border-left: 4px solid #FB8C00;
    }

    /* Floating Map Legend */
    .map-legend {
        position: absolute;
        bottom: 30px;
        right: 30px;
        background-color: rgba(22, 27, 34, 0.85);
        backdrop-filter: blur(8px);
        border: 1px solid #30363D;
        padding: 15px;
        border-radius: 8px;
        font-size: 0.85em;
        z-index: 999;
        color: #E6EDF3;
        pointer-events: none;
    }
    .legend-dot {
        height: 12px;
        width: 12px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 8px;
    }

    /* Anti-flicker for Auto-Play Reruns */
    [data-testid="stAppViewContainer"] {
        transition: none !important;
    }
    div[data-testid="stAppViewBlockContainer"] {
        opacity: 1 !important;
        transition: none !important;
    }
</style>
""",
    unsafe_allow_html=True,
)


# -----------------
# DATA LOADING (REPOSITORY PATTERN)
# -----------------
@st.cache_resource
def get_repository(scenario_path):
    return ParquetDataRepository(scenario_path)


# -----------------
# SIDEBAR CONTROLS
# -----------------
with st.sidebar:
    st.markdown("### 🎛️ Centro de Control (OCC)")
    time_slot_option = st.selectbox(
        "Ventana Operativa",
        [
            "06:00 - 09:00 (Hora Pico Mañana)",
            "11:00 - 14:00 (Valle Mediodía)",
            "17:00 - 20:00 (Hora Pico Tarde)",
            "04:00 - 23:00 (Día Completo)",
        ],
    )

    if "Mañana" in time_slot_option:
        start_hour, end_hour = 6, 9
    elif "Mediodía" in time_slot_option:
        start_hour, end_hour = 11, 14
    elif "Tarde" in time_slot_option:
        start_hour, end_hour = 17, 20
    else:
        start_hour, end_hour = 4, 23

    official_headways = {"B10": 4.5, "B27": 6.0, "H20": 5.0}

    run_sim_btn = st.button(
        "🚦 Iniciar Simulación Oficial GTFS", use_container_width=True, type="primary"
    )

    st.divider()
    st.markdown("### 🧠 Motor IA (Simulated Annealing)")
    enable_ai = st.toggle("Activar Agente Racional (FlowTM)", value=False)
    optimize_btn = (
        st.button("⚡ Ejecutar Optimización", use_container_width=True)
        if enable_ai
        else False
    )

# -----------------
# SIMULATION EXECUTION
# -----------------
if run_sim_btn or "base_result" not in st.session_state:
    with st.spinner(
        f"Simulando operaciones base ({start_hour:02d}:00 - {end_hour:02d}:00)..."
    ):
        simulator = CorridorSimulator(scenario_dir)
        base_result = simulator.simulate(
            official_headways, start_hour=start_hour, end_hour=end_hour
        )
        simulator.collector.export_telemetry(scenario_dir / "telemetria_base")
        st.session_state["base_result"] = base_result
        st.session_state["start_hour"] = start_hour
        st.session_state["end_hour"] = end_hour
        st.session_state["ai_executed"] = False
        st.rerun()

if optimize_btn:
    with st.spinner(
        f"Agente Racional optimizando frecuencias ({start_hour:02d}:00 - {end_hour:02d}:00)..."
    ):
        optimizer = SimulatedAnnealingOptimizer(
            scenario_dir, iterations=20, initial_temp=50.0, cooling_rate=0.88
        )
        best_state, _ = optimizer.optimize(ScheduleState(headways=official_headways))

        opt_simulator = CorridorSimulator(scenario_dir)
        opt_result = opt_simulator.simulate(
            best_state.headways, start_hour=start_hour, end_hour=end_hour
        )
        opt_simulator.collector.export_telemetry(scenario_dir / "telemetria_opt")

        st.session_state["opt_result"] = opt_result
        st.session_state["best_state"] = best_state
        st.session_state["ai_executed"] = True
        st.rerun()

# -----------------
# DASHBOARD STATE PREP (VIA REPOSITORY)
# -----------------
base_result = st.session_state["base_result"]
session_start_hour = st.session_state["start_hour"]
session_end_hour = st.session_state["end_hour"]
is_ai_active = st.session_state.get("ai_executed", False)

repository = get_repository(scenario_dir)
topology_df = repository.get_topology()

if is_ai_active:
    buses_df, queues_df = repository.get_telemetry("opt")
    mode_label = "🟢 Escenario Optimizado (FlowTM IA)"
else:
    buses_df, queues_df = repository.get_telemetry("base")
    mode_label = "🔴 Escenario Oficial (GTFS Actual)"

if buses_df is not None and queues_df is not None and len(buses_df) > 0:
    min_time = float(buses_df["time_sec"].min())
    max_time = float(buses_df["time_sec"].max())

    # --- MASTER CLOCK & SCRUBBER ---
    st.markdown(
        "<h2 style='text-align: center; color: #E6EDF3;'>🌐 Centro de Control Operativo (OCC)</h2>",
        unsafe_allow_html=True,
    )

    dt_start = datetime.datetime(2023, 1, 1, session_start_hour, 0, 0)
    min_dt = dt_start + datetime.timedelta(seconds=min_time)
    max_dt = dt_start + datetime.timedelta(seconds=max_time)

    # Auto-play state management
    if "auto_play" not in st.session_state:
        st.session_state.auto_play = False
    if "current_scrubber_dt" not in st.session_state:
        st.session_state.current_scrubber_dt = min_dt

    col_play, col_step, col_slider = st.columns(
        [1.5, 2, 6.5], vertical_alignment="bottom"
    )
    with col_play:
        if st.session_state.auto_play:
            if st.button("⏸️ Pausa", use_container_width=True):
                st.session_state.auto_play = False
                st.rerun()
        else:
            if st.button("▶️ Play", use_container_width=True):
                st.session_state.auto_play = True
                st.rerun()

    with col_step:
        step_mins = st.number_input(
            "Salto (min/frame)",
            min_value=1,
            max_value=60,
            value=5,
            disabled=st.session_state.auto_play,
        )

    with col_slider:
        current_dt = st.slider(
            "Línea de Tiempo Operacional",
            min_value=min_dt,
            max_value=max_dt,
            value=st.session_state.current_scrubber_dt,
            step=datetime.timedelta(seconds=30),
            format="hh:mm:ss a",
            label_visibility="collapsed",
        )

    # If the user manually drags the slider, update the state
    if (
        current_dt != st.session_state.current_scrubber_dt
        and not st.session_state.auto_play
    ):
        st.session_state.current_scrubber_dt = current_dt

    current_time = (st.session_state.current_scrubber_dt - dt_start).total_seconds()
    formatted_time = st.session_state.current_scrubber_dt.strftime("%I:%M:%S %p")

    # Auto-play loop execution (advances time and reruns)
    if st.session_state.auto_play:
        import time

        time.sleep(0.3)  # Faster playback sleep
        next_time = st.session_state.current_scrubber_dt + datetime.timedelta(
            minutes=step_mins
        )
        if next_time > max_dt:
            st.session_state.auto_play = False
            st.session_state.current_scrubber_dt = max_dt
        else:
            st.session_state.current_scrubber_dt = next_time
        st.rerun()

    st.markdown(
        f"<h3 style='text-align: center; color: #58A6FF; margin-top:-15px; margin-bottom: 25px;'>🕒 Reloj Maestro: {formatted_time} &mdash; {mode_label}</h3>",
        unsafe_allow_html=True,
    )

    # --- REAL-TIME DATA FILTERING (Instant t) ---
    # We look back up to 90 seconds to catch the latest telemetry broadcast
    current_buses_df = buses_df[
        (buses_df["time_sec"] <= current_time)
        & (buses_df["time_sec"] >= current_time - 90.0)
    ].drop_duplicates(subset=["bus_id"], keep="last")

    current_queues_df = queues_df[
        (queues_df["time_sec"] <= current_time)
        & (queues_df["time_sec"] >= current_time - 90.0)
    ].drop_duplicates(subset=["station_code"], keep="last")

    station_data = pd.merge(
        topology_df,
        current_queues_df[["station_code", "queue_size"]],
        left_on="codigo",
        right_on="station_code",
        how="left",
    )
    station_data["queue_size"] = station_data["queue_size"].fillna(0)

    # --- INSTANTANEOUS KPIs ---
    active_buses = len(current_buses_df)
    total_stranded = int(station_data["queue_size"].sum())
    mean_occupancy = (
        (current_buses_df["passengers"].mean() / 160.0) * 100 if active_buses > 0 else 0
    )

    critical_station = "N/A"
    critical_val = 0
    if total_stranded > 0:
        critical_row = station_data.loc[station_data["queue_size"].idxmax()]
        critical_station = critical_row["nombre"]
        critical_val = int(critical_row["queue_size"])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🚌 Flota Activa en Vía", f"{active_buses} buses")
    c2.metric("🧍 Demanda Represada Global Q(t)", f"{total_stranded:,} pax")
    c3.metric(
        "🚨 Mayor Cuello de Botella",
        f"{critical_station}",
        f"{critical_val} pax",
        delta_color="inverse",
    )
    c4.metric("👥 Factor de Carga Promedio", f"{mean_occupancy:.1f}%")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- DEEP ANALYTICS TABS ---
    tab_map, tab_bus, tab_stations, tab_ia = st.tabs(
        [
            "🗺️ Gemelo Digital en Vivo & Monitor",
            "🚍 Perfil de Carga y Flota",
            "🚉 Evolución de Colas $Q(t)$",
            "🧠 Comparador IA & GTFS",
        ]
    )

    # TABS 1: LIVE TWIN & INCIDENT MONITOR
    with tab_map:
        col_map, col_tel = st.columns([7, 3])

        with col_map:
            # Map Infrastructure Layer
            sorted_topology_df = (
                topology_df.sort_values(by=["secuencia"])
                if "secuencia" in topology_df.columns
                else topology_df
            )
            path_data = pd.DataFrame(
                [
                    {
                        "path": sorted_topology_df[["lon", "lat"]].values.tolist(),
                        "color": [255, 255, 255, 90],
                    }
                ]
            )
            infra_layer = pdk.Layer(
                "PathLayer",
                data=path_data,
                get_path="path",
                get_color="color",
                width_scale=20,
                width_min_pixels=5,
                get_width=5,
            )

            # Map Buses Layer
            route_colors = {
                "B10": [66, 165, 245, 255],
                "B27": [102, 187, 106, 255],
                "H20": [239, 83, 80, 255],
            }
            bus_layer = None
            if active_buses > 0:
                current_buses_df["color"] = current_buses_df["route"].map(
                    lambda x: route_colors.get(x, [255, 204, 0, 255])
                )
                current_buses_df["radius"] = current_buses_df["passengers"].apply(
                    lambda p: min(250, max(60, (p / 160.0) * 200))
                )
                current_buses_df["tooltip_text"] = current_buses_df.apply(
                    lambda r: (
                        f"🚍 Bus {r['bus_id']} ({r['route']})\nCarga: {r['passengers']}/160 pax ({(r['passengers'] / 160) * 100:.1f}%)"
                    ),
                    axis=1,
                )
                bus_layer = pdk.Layer(
                    "ScatterplotLayer",
                    data=current_buses_df.dropna(subset=["lat", "lon"]),
                    get_position=["lon", "lat"],
                    get_color="color",
                    get_radius="radius",
                    pickable=True,
                    opacity=1.0,
                    stroked=True,
                    get_line_color=[0, 0, 0, 255],
                    line_width_min_pixels=2,
                )

            # Map Stations Layer
            def get_queue_color(queue_size: float) -> list[int]:
                """Return RGBA color based on queue size thresholds."""
                if queue_size < 50:
                    return [67, 160, 71, 150]
                if queue_size < 150:
                    return [251, 140, 0, 180]
                return [229, 57, 53, 220]

            station_data["color"] = station_data["queue_size"].apply(get_queue_color)
            station_data["radius"] = station_data["queue_size"].apply(
                lambda queue_size: min(600, max(120, queue_size * 3.5))
            )
            station_data["tooltip_text"] = station_data.apply(
                lambda r: (
                    f"🚉 Estación {r['nombre']}\nDemanda Q(t): {int(r['queue_size'])} pax"
                ),
                axis=1,
            )
            station_layer = pdk.Layer(
                "ScatterplotLayer",
                data=station_data,
                get_position=["lon", "lat"],
                get_color="color",
                get_radius="radius",
                pickable=True,
            )

            layers = [infra_layer, station_layer]
            if bus_layer:
                layers.append(bus_layer)

            view_state = pdk.ViewState(
                latitude=topology_df["lat"].mean(),
                longitude=topology_df["lon"].mean(),
                zoom=11.5,
                pitch=40,
            )

            # Static Legends Above Map
            col_leg1, col_leg2 = st.columns(2)
            with col_leg1:
                st.markdown(
                    """
                <div style='background-color:#161B22; border:1px solid #30363D; border-radius:6px; padding:10px; margin-bottom:10px;'>
                <div style='font-weight:bold; border-bottom:1px solid #444; margin-bottom:8px; padding-bottom:4px;'>Ficha Técnica de Rutas</div>
                <div style='margin-bottom:4px;'><span class='legend-dot' style='background-color:#42A5F5;'></span>B10 (Corriente)</div>
                <div style='margin-bottom:4px;'><span class='legend-dot' style='background-color:#66BB6A;'></span>B27 (Expreso)</div>
                <div><span class='legend-dot' style='background-color:#EF5350;'></span>H20 (Troncal)</div>
                </div>
                """,
                    unsafe_allow_html=True,
                )
            with col_leg2:
                st.markdown(
                    """
                <div style='background-color:#161B22; border:1px solid #30363D; border-radius:6px; padding:10px; margin-bottom:10px;'>
                <div style='font-weight:bold; border-bottom:1px solid #444; margin-bottom:8px; padding-bottom:4px;'>Semáforo Andén Q(t)</div>
                <div style='margin-bottom:4px;'><span class='legend-dot' style='background-color:#43A047;'></span>Normal (&lt; 50 pax)</div>
                <div style='margin-bottom:4px;'><span class='legend-dot' style='background-color:#FB8C00;'></span>Congestión (50-150 pax)</div>
                <div><span class='legend-dot' style='background-color:#E53935;'></span>Saturación (&gt; 150 pax)</div>
                </div>
                """,
                    unsafe_allow_html=True,
                )

            st.pydeck_chart(
                pdk.Deck(
                    layers=layers,
                    initial_view_state=view_state,
                    map_style=pdk.map_styles.CARTO_DARK,
                    tooltip={
                        "text": "{tooltip_text}",
                        "style": {
                            "color": "white",
                            "backgroundColor": "#161B22",
                            "border": "1px solid #30363D",
                        },
                    },
                ),
                use_container_width=True,
            )

        with col_tel:
            st.markdown("### 🚨 Auditoría de Incidentes")
            st.markdown(
                f"<div style='color: #8B949E; margin-top:-10px; margin-bottom:15px;'>Corte instantáneo: {formatted_time}</div>",
                unsafe_allow_html=True,
            )

            st.markdown("<div class='incident-panel'>", unsafe_allow_html=True)
            # 1. Collapse Monitor (Q > 150)
            st.markdown("#### 🚉 Estaciones Colapsadas")
            alert_stations = station_data[
                station_data["queue_size"] >= 150
            ].sort_values(by="queue_size", ascending=False)
            if len(alert_stations) > 0:
                for _, r in alert_stations.iterrows():
                    st.markdown(
                        f"<div class='incident-item'><b>{r['nombre']}</b>: {int(r['queue_size'])} pasajeros esperando evacuación.</div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown(
                    "<div class='incident-item incident-warning' style='border-color:#43A047;'>Capacidad de andén bajo control operativo.</div>",
                    unsafe_allow_html=True,
                )

            # 2. Bursting Buses (Pax >= 152)
            st.markdown(
                "<h4 style='margin-top:20px;'>🚍 Flota en Sobrecupo Crítico (≥95%)</h4>",
                unsafe_allow_html=True,
            )
            if active_buses > 0:
                full_buses = current_buses_df[
                    current_buses_df["passengers"] >= 152
                ].sort_values(by="passengers", ascending=False)
                if len(full_buses) > 0:
                    for _, r in full_buses.iterrows():
                        color = (
                            "#42A5F5"
                            if r["route"] == "B10"
                            else "#66BB6A"
                            if r["route"] == "B27"
                            else "#EF5350"
                        )
                        st.markdown(
                            f"<div class='incident-item'><span style='color:{color}; font-weight:bold;'>{r['route']}</span> (ID: {r['bus_id']}): {r['passengers']}/160 pax ({(r['passengers'] / 160) * 100:.1f}%)</div>",
                            unsafe_allow_html=True,
                        )
                else:
                    st.markdown(
                        "<div class='incident-item incident-warning' style='border-color:#43A047;'>Sin eventos de hacinamiento crítico registrados.</div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown(
                    "<div class='incident-item incident-warning' style='border-color:#8B949E;'>No hay telemetría de vehículos rodando en este momento.</div>",
                    unsafe_allow_html=True,
                )

            st.markdown("</div>", unsafe_allow_html=True)

        st.divider()
        st.markdown(
            "### 📜 Bitácora Histórica de Incidentes (Post-Mortem del Escenario)"
        )
        st.markdown(
            "Auditoría agregada de todos los eventos críticos ocurridos durante la franja operativa simulada, aislando los picos máximos de saturación para evitar analizar minuto a minuto."
        )

        col_station_history, col_bus_history = st.columns(2)

        with col_station_history:
            st.markdown("#### 🚉 Colapsos en Andén (Q > 150 pax)")
            # Aggregate station incidents
            station_history = aggregate_station_incidents(
                pl.from_pandas(queues_df)
            ).to_pandas()
            if len(station_history) > 0:
                station_history = pd.merge(
                    station_history,
                    topology_df[["codigo", "nombre"]],
                    left_on="station_code",
                    right_on="codigo",
                    how="left",
                )
                station_history["collapse_start"] = station_history[
                    "collapse_start"
                ].apply(
                    lambda s: (dt_start + datetime.timedelta(seconds=s)).strftime(
                        "%I:%M:%S %p"
                    )
                )
                station_history["collapse_end"] = station_history["collapse_end"].apply(
                    lambda s: (dt_start + datetime.timedelta(seconds=s)).strftime(
                        "%I:%M:%S %p"
                    )
                )
                station_history = station_history[
                    ["nombre", "peak_queue", "collapse_start", "collapse_end"]
                ].rename(
                    columns={
                        "nombre": "Estación",
                        "peak_queue": "Máx Pasajeros",
                        "collapse_start": "Inicio Colapso",
                        "collapse_end": "Fin Colapso",
                    }
                )
                st.dataframe(
                    station_history.sort_values(by="Máx Pasajeros", ascending=False),
                    hide_index=True,
                    use_container_width=True,
                )
            else:
                st.success(
                    "Operación Perfecta: Ninguna estación superó el umbral de 150 pasajeros en todo el escenario."
                )

        with col_bus_history:
            st.markdown("#### 🚍 Sobrecupos de Flota (Carga > 95%)")
            bus_history = aggregate_bus_incidents(pl.from_pandas(buses_df)).to_pandas()
            if len(bus_history) > 0:
                bus_history["overcrowding_start"] = bus_history[
                    "overcrowding_start"
                ].apply(
                    lambda s: (dt_start + datetime.timedelta(seconds=s)).strftime(
                        "%I:%M:%S %p"
                    )
                )
                bus_history["overcrowding_end"] = bus_history["overcrowding_end"].apply(
                    lambda s: (dt_start + datetime.timedelta(seconds=s)).strftime(
                        "%I:%M:%S %p"
                    )
                )
                bus_history = bus_history[
                    [
                        "route",
                        "bus_id",
                        "peak_passengers",
                        "overcrowding_start",
                        "overcrowding_end",
                    ]
                ].rename(
                    columns={
                        "route": "Ruta",
                        "bus_id": "ID Bus",
                        "peak_passengers": "Máx Pax",
                        "overcrowding_start": "Inicio Sobrecupo",
                        "overcrowding_end": "Fin Sobrecupo",
                    }
                )
                st.dataframe(
                    bus_history.sort_values(by="Máx Pax", ascending=False),
                    hide_index=True,
                    use_container_width=True,
                )
            else:
                st.success(
                    "Operación Confortable: Ningún bus alcanzó el 95% de su capacidad instalada (152 pax)."
                )

    # TABS 2: BUS LOAD PROFILE
    with tab_bus:
        st.markdown("### Auditoría Físico-Estadística de Carga por Ruta")
        active_res = (
            st.session_state["opt_result"]
            if is_ai_active
            else st.session_state["base_result"]
        )

        if (
            hasattr(active_res, "route_load_profiles")
            and len(active_res.route_load_profiles) > 0
        ):
            selected_route = st.selectbox(
                "Seleccione la Ruta a auditar:",
                list(active_res.route_load_profiles.keys()),
            )
            load_profile_df = pl.DataFrame(
                active_res.route_load_profiles[selected_route]
            ).to_pandas()

            load_profile_fig = px.line(
                load_profile_df,
                x="estacion",
                y="promedio_a_bordo",
                markers=True,
                title=f"Perfil Histórico de Ocupación Promedio: {selected_route} a lo largo de la Troncal",
                template="plotly_dark",
                color_discrete_sequence=["#58A6FF"],
            )
            # Maximum Physical Capacity & Critical Crowding Zone
            load_profile_fig.add_hline(
                y=160,
                line_dash="dash",
                line_color="#E6EDF3",
                annotation_text="Límite Físico del Chasis (160 pax)",
            )
            load_profile_fig.add_hrect(
                y0=152,
                y1=180,
                line_width=0,
                fillcolor="#E53935",
                opacity=0.15,
                annotation_text="⚠️ Hacinamiento Crítico (>95%)",
                annotation_position="top left",
            )

            load_profile_fig.update_traces(
                hovertemplate="<b>%{x}</b><br>Ocupación Promedio: %{y:.1f} pax<br>Factor de Carga: %{customdata:.1f}%<extra></extra>",
                customdata=(load_profile_df["promedio_a_bordo"] / 160.0) * 100,
            )

            load_profile_fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis_tickangle=-45,
                yaxis_range=[0, 180],
                yaxis_title="Pasajeros Promedio A Bordo",
            )
            st.plotly_chart(load_profile_fig, use_container_width=True)
        else:
            st.warning(
                "No se detectó un perfil de carga válido en la memoria del motor."
            )

    # TABS 3: QUEUE DYNAMICS
    with tab_stations:
        st.markdown("### Serie Temporal: Acumulación vs Evacuación en Andén $Q(t)$")
        selected_station = st.selectbox(
            "Auditar Estación Específica:", topology_df["nombre"].tolist()
        )
        station_code = topology_df[topology_df["nombre"] == selected_station].iloc[0][
            "codigo"
        ]

        station_queue_history = queues_df[
            queues_df["station_code"] == station_code
        ].copy()

        if len(station_queue_history) > 0:
            station_queue_history["clock_dt"] = station_queue_history["time_sec"].apply(
                lambda s: dt_start + datetime.timedelta(seconds=s)
            )

            queue_fig = px.line(
                station_queue_history,
                x="clock_dt",
                y="queue_size",
                title=f"Evolución Matemática de $Q(t)$ en {selected_station}",
                template="plotly_dark",
                color_discrete_sequence=["#FB8C00"],
            )
            queue_fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                yaxis_title="Volumen Q(t) [Pasajeros]",
                xaxis_title="Reloj Operativo (HH:MM:SS)",
            )

            # Scrubber Time marker
            queue_fig.add_vline(
                x=current_dt.timestamp() * 1000,
                line_dash="solid",
                line_width=2,
                line_color="#58A6FF",
                annotation_text="▶ Instante de Inspección Actual",
            )
            # Saturation thresholds
            queue_fig.add_hline(
                y=150,
                line_dash="dash",
                line_color="#E53935",
                opacity=0.5,
                annotation_text="Riesgo de Colapso (>150 pax)",
            )

            st.plotly_chart(queue_fig, use_container_width=True)
        else:
            st.warning(
                "No hay datos históricos para esta estación en la franja seleccionada."
            )

    # TABS 4: AI COMPARISON
    with tab_ia:
        st.markdown("### Contraste Científico Operacional: $S_{base}$ vs $S_{opt}$")
        if is_ai_active:
            opt_result = st.session_state["opt_result"]
            opt_state = st.session_state["best_state"]

            col_base_scenario, col_opt_scenario = st.columns(2)
            with col_base_scenario:
                st.markdown(
                    "<div style='background-color:#21262d; padding:20px; border-radius:8px; border-left:4px solid #E53935;'>",
                    unsafe_allow_html=True,
                )
                st.markdown("#### 🔴 Operación Original (GTFS Oficial)")
                st.write(f"**Frecuencias Estáticas:** {official_headways}")
                st.write(
                    f"**Tiempo de Espera Promedio:** {base_result.avg_waiting_time_min:.2f} minutos"
                )
                st.write(
                    f"**Pasajeros Represados Totales:** {base_result.stranded_passengers_in_queue:,} personas"
                )
                st.write(
                    f"**Tasa de Sobrecupo Crítico:** {base_result.overcrowded_bus_pct:.1f}%"
                )
                st.write(
                    f"**Volumen de Flota Inyectada:** {base_result.total_dispatched_buses} buses"
                )
                st.markdown("</div>", unsafe_allow_html=True)

            with col_opt_scenario:
                st.markdown(
                    "<div style='background-color:#21262d; padding:20px; border-radius:8px; border-left:4px solid #43A047;'>",
                    unsafe_allow_html=True,
                )
                st.markdown("#### 🟢 Agente FlowTM (Simulated Annealing)")
                st.write(f"**Frecuencias Optimizadas:** {opt_state.headways}")
                st.write(
                    f"**Tiempo de Espera Promedio:** {opt_result.avg_waiting_time_min:.2f} minutos"
                )
                st.write(
                    f"**Pasajeros Represados Totales:** {opt_result.stranded_passengers_in_queue:,} personas"
                )
                st.write(
                    f"**Tasa de Sobrecupo Crítico:** {opt_result.overcrowded_bus_pct:.1f}%"
                )
                st.write(
                    f"**Volumen de Flota Inyectada:** {opt_result.total_dispatched_buses} buses"
                )
                st.markdown("</div>", unsafe_allow_html=True)

            st.divider()
            st.markdown("### 📥 Pipeline de Integración GTFS (`frequencies.txt`)")
            df_gtfs = pl.DataFrame(
                [
                    {
                        "route_id": r,
                        "start_time": f"{session_start_hour:02d}:00:00",
                        "end_time": f"{session_end_hour:02d}:00:00",
                        "headway_secs": int(m * 60),
                        "exact_times": 0,
                    }
                    for r, m in opt_state.headways.items()
                ]
            )
            st.dataframe(df_gtfs.to_pandas(), hide_index=True, use_container_width=True)
            st.download_button(
                label="Descargar GTFS frequencies.txt (Horario Óptimo FlowTM)",
                data=df_gtfs.write_csv(),
                file_name="frequencies.txt",
                mime="text/csv",
                type="primary",
            )
        else:
            st.info(
                "💡 Activa el **Agente Racional (IA)** en el panel lateral para computar la solución óptima y desbloquear el análisis comparativo."
            )

else:
    st.info(
        "El Centro de Control está inactivo. Configura la ventana operativa y ejecuta la simulación en el panel lateral para comenzar."
    )
