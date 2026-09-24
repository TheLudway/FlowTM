"""
src/flowtm/presentation/dashboard/app.py
FlowTM - Digital Twin Engine (Operations Control Center)
"""

import streamlit as st
import polars as pl
import pandas as pd
import pydeck as pdk
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
import sys
import datetime

# System path setup
ROOT_DIR = Path(__file__).resolve().parents[4]
if str(ROOT_DIR / "src") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "src"))

from flowtm.domain.state import ScheduleState
from flowtm.simulation.engine import SimuladorCorredor
from flowtm.optimization.simulated_annealing import SimulatedAnnealingOptimizer

escenario_dir = ROOT_DIR / "data/scenarios/piloto"

st.set_page_config(
    page_title="FlowTM - OCC Digital Twin",
    page_icon="🚍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------
# STYLES (Deluxe OCC Theme)
# -----------------
st.markdown("""
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
""", unsafe_allow_html=True)

# -----------------
# DATA LOADING (CACHED)
# -----------------
@st.cache_data
def load_telemetry(scenario_path, name):
    path = scenario_path / name
    if not path.exists():
        return None, None
    buses_df = pl.read_parquet(path / "telemetria_buses.parquet").to_pandas()
    colas_df = pl.read_parquet(path / "historial_colas.parquet").to_pandas()
    return buses_df, colas_df

@st.cache_data
def load_topology(scenario_path):
    return pl.read_parquet(scenario_path / "estaciones_piloto.parquet").to_pandas()

# -----------------
# SIDEBAR CONTROLS
# -----------------
with st.sidebar:
    st.markdown("### 🎛️ Centro de Control (OCC)")
    franja_opcion = st.selectbox(
        "Ventana Operativa",
        [
            "06:00 - 09:00 (Hora Pico Mañana)",
            "11:00 - 14:00 (Valle Mediodía)",
            "17:00 - 20:00 (Hora Pico Tarde)",
            "04:00 - 23:00 (Día Completo)"
        ]
    )

    if "Mañana" in franja_opcion:
        hora_ini, hora_fin = 6, 9
    elif "Mediodía" in franja_opcion:
        hora_ini, hora_fin = 11, 14
    elif "Tarde" in franja_opcion:
        hora_ini, hora_fin = 17, 20
    else:
        hora_ini, hora_fin = 4, 23

    frecuencias_oficiales = {"B10": 4.5, "B27": 6.0, "H20": 5.0}

    btn_correr = st.button("🚦 Iniciar Simulación Oficial GTFS", use_container_width=True, type="primary")
    
    st.divider()
    st.markdown("### 🧠 Motor IA (Simulated Annealing)")
    activar_ia = st.toggle("Activar Agente Racional (FlowTM)", value=False)
    btn_optimizar = st.button("⚡ Ejecutar Optimización", use_container_width=True) if activar_ia else False

# -----------------
# SIMULATION EXECUTION
# -----------------
if btn_correr or "resultado_base" not in st.session_state:
    with st.spinner(f"Simulando operaciones base ({hora_ini:02d}:00 - {hora_fin:02d}:00)..."):
        simulador = SimuladorCorredor(escenario_dir)
        res_base = simulador.simular(frecuencias_oficiales, hora_inicio=hora_ini, hora_fin=hora_fin)
        simulador.collector.exportar_telemetria(escenario_dir / "telemetria_base")
        st.session_state["resultado_base"] = res_base
        st.session_state["hora_ini"] = hora_ini
        st.session_state["hora_fin"] = hora_fin
        st.session_state["ia_ejecutada"] = False
        st.rerun()

if btn_optimizar:
    with st.spinner(f"Agente Racional optimizando frecuencias ({hora_ini:02d}:00 - {hora_fin:02d}:00)..."):
        optimizador = SimulatedAnnealingOptimizer(escenario_dir, iteraciones=20, temp_inicial=50.0, cooling_rate=0.88)
        mejor_estado, _ = optimizador.optimizar(ScheduleState(frecuencias=frecuencias_oficiales))
        
        sim_opt = SimuladorCorredor(escenario_dir)
        res_opt = sim_opt.simular(mejor_estado.frecuencias, hora_inicio=hora_ini, hora_fin=hora_fin)
        sim_opt.collector.exportar_telemetria(escenario_dir / "telemetria_opt")
        
        st.session_state["resultado_opt"] = res_opt
        st.session_state["mejor_estado"] = mejor_estado
        st.session_state["ia_ejecutada"] = True
        st.rerun()

# -----------------
# DASHBOARD STATE PREP
# -----------------
res_base = st.session_state["resultado_base"]
h_ini = st.session_state["hora_ini"]
h_fin = st.session_state["hora_fin"]
ia_activa = st.session_state.get("ia_ejecutada", False)

df_topo = load_topology(escenario_dir)
if ia_activa:
    buses_df, colas_df = load_telemetry(escenario_dir, "telemetria_opt")
    mode_label = "🟢 Escenario Optimizado (FlowTM IA)"
else:
    buses_df, colas_df = load_telemetry(escenario_dir, "telemetria_base")
    mode_label = "🔴 Escenario Oficial (GTFS Actual)"

if buses_df is not None and colas_df is not None and len(buses_df) > 0:
    min_time = float(buses_df["tiempo_seg"].min())
    max_time = float(buses_df["tiempo_seg"].max())
    
    # --- MASTER CLOCK & SCRUBBER ---
    st.markdown(f"<h2 style='text-align: center; color: #E6EDF3;'>🌐 Centro de Control Operativo (OCC)</h2>", unsafe_allow_html=True)
    
    dt_start = datetime.datetime(2023, 1, 1, h_ini, 0, 0)
    min_dt = dt_start + datetime.timedelta(seconds=min_time)
    max_dt = dt_start + datetime.timedelta(seconds=max_time)
    
    # Auto-play state management
    if "auto_play" not in st.session_state:
        st.session_state.auto_play = False
    if "current_scrubber_dt" not in st.session_state:
        st.session_state.current_scrubber_dt = min_dt
        
    col_play, col_step, col_slider = st.columns([1.5, 2, 6.5], vertical_alignment="bottom")
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
        step_mins = st.number_input("Salto (min/frame)", min_value=1, max_value=60, value=5, disabled=st.session_state.auto_play)

    with col_slider:
        current_dt = st.slider(
            "Línea de Tiempo Operacional", 
            min_value=min_dt, 
            max_value=max_dt, 
            value=st.session_state.current_scrubber_dt, 
            step=datetime.timedelta(seconds=30),
            format="hh:mm:ss a",
            label_visibility="collapsed"
        )
        
    # If the user manually drags the slider, update the state
    if current_dt != st.session_state.current_scrubber_dt and not st.session_state.auto_play:
        st.session_state.current_scrubber_dt = current_dt
        
    current_time = (st.session_state.current_scrubber_dt - dt_start).total_seconds()
    formatted_time = st.session_state.current_scrubber_dt.strftime("%I:%M:%S %p")
    
    # Auto-play loop execution (advances time and reruns)
    if st.session_state.auto_play:
        import time
        time.sleep(0.3) # Faster playback sleep
        next_time = st.session_state.current_scrubber_dt + datetime.timedelta(minutes=step_mins)
        if next_time > max_dt:
            st.session_state.auto_play = False
            st.session_state.current_scrubber_dt = max_dt
        else:
            st.session_state.current_scrubber_dt = next_time
        st.rerun()
    
    st.markdown(f"<h3 style='text-align: center; color: #58A6FF; margin-top:-15px; margin-bottom: 25px;'>🕒 Reloj Maestro: {formatted_time} &mdash; {mode_label}</h3>", unsafe_allow_html=True)
    
    # --- REAL-TIME DATA FILTERING (Instant t) ---
    # We look back up to 90 seconds to catch the latest telemetry broadcast
    df_buses_curr = buses_df[
        (buses_df["tiempo_seg"] <= current_time) & 
        (buses_df["tiempo_seg"] >= current_time - 90.0)
    ].drop_duplicates(subset=["id_bus"], keep="last")
    
    df_colas_curr = colas_df[
        (colas_df["tiempo_seg"] <= current_time) & 
        (colas_df["tiempo_seg"] >= current_time - 90.0)
    ].drop_duplicates(subset=["codigo_estacion"], keep="last")
    
    st_data = pd.merge(
        df_topo, 
        df_colas_curr[["codigo_estacion", "cola_pasajeros"]], 
        left_on="codigo", 
        right_on="codigo_estacion", 
        how="left"
    )
    st_data["cola"] = st_data["cola_pasajeros"].fillna(0)
    
    # --- INSTANTANEOUS KPIs ---
    active_buses = len(df_buses_curr)
    total_stranded = int(st_data["cola"].sum())
    mean_occupancy = (df_buses_curr["pasajeros"].mean() / 160.0) * 100 if active_buses > 0 else 0
    
    critical_station = "N/A"
    critical_val = 0
    if total_stranded > 0:
        crit_row = st_data.loc[st_data["cola"].idxmax()]
        critical_station = crit_row["nombre"]
        critical_val = int(crit_row["cola"])
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🚌 Flota Activa en Vía", f"{active_buses} buses")
    c2.metric("🧍 Demanda Represada Global Q(t)", f"{total_stranded:,} pax")
    c3.metric("🚨 Mayor Cuello de Botella", f"{critical_station}", f"{critical_val} pax", delta_color="inverse")
    c4.metric("👥 Factor de Carga Promedio", f"{mean_occupancy:.1f}%")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # --- DEEP ANALYTICS TABS ---
    tab_map, tab_bus, tab_estaciones, tab_ia = st.tabs([
        "🗺️ Gemelo Digital en Vivo & Monitor",
        "🚍 Perfil de Carga y Flota",
        "🚉 Evolución de Colas $Q(t)$",
        "🧠 Comparador IA & GTFS"
    ])
    
    # TABS 1: LIVE TWIN & INCIDENT MONITOR
    with tab_map:
        col_map, col_tel = st.columns([7, 3])
        
        with col_map:
            # Map Infrastructure Layer
            df_topo_sorted = df_topo.sort_values(by=["secuencia"]) if "secuencia" in df_topo.columns else df_topo
            path_data = pd.DataFrame([{"path": df_topo_sorted[["lon", "lat"]].values.tolist(), "color": [255, 255, 255, 90]}])
            infra_layer = pdk.Layer("PathLayer", data=path_data, get_path="path", get_color="color", width_scale=20, width_min_pixels=5, get_width=5)
            
            # Map Buses Layer
            route_colors = {"B10": [66, 165, 245, 255], "B27": [102, 187, 106, 255], "H20": [239, 83, 80, 255]}
            bus_layer = None
            if active_buses > 0:
                df_buses_curr["color"] = df_buses_curr["ruta"].map(lambda x: route_colors.get(x, [255, 204, 0, 255]))
                df_buses_curr["radius"] = df_buses_curr["pasajeros"].apply(lambda p: min(250, max(60, (p / 160.0) * 200)))
                df_buses_curr["tooltip_text"] = df_buses_curr.apply(lambda r: f"🚍 Bus {r['id_bus']} ({r['ruta']})\nCarga: {r['pasajeros']}/160 pax ({(r['pasajeros']/160)*100:.1f}%)", axis=1)
                bus_layer = pdk.Layer(
                    "ScatterplotLayer", data=df_buses_curr.dropna(subset=["lat", "lon"]),
                    get_position=["lon", "lat"], get_color="color", get_radius="radius",
                    pickable=True, opacity=1.0, stroked=True, get_line_color=[0, 0, 0, 255], line_width_min_pixels=2
                )
                
            # Map Stations Layer
            def q_color(q):
                if q < 50: return [67, 160, 71, 150]
                elif q < 150: return [251, 140, 0, 180]
                else: return [229, 57, 53, 220]
                
            st_data["color"] = st_data["cola"].apply(q_color)
            st_data["radius"] = st_data["cola"].apply(lambda q: min(600, max(120, q * 3.5)))
            st_data["tooltip_text"] = st_data.apply(lambda r: f"🚉 Estación {r['nombre']}\nDemanda Q(t): {int(r['cola'])} pax", axis=1)
            station_layer = pdk.Layer("ScatterplotLayer", data=st_data, get_position=["lon", "lat"], get_color="color", get_radius="radius", pickable=True)

            layers = [infra_layer, station_layer]
            if bus_layer: layers.append(bus_layer)
            
            view_state = pdk.ViewState(latitude=df_topo["lat"].mean(), longitude=df_topo["lon"].mean(), zoom=11.5, pitch=40)
            
            # Static Legends Above Map
            col_leg1, col_leg2 = st.columns(2)
            with col_leg1:
                st.markdown("""
                <div style='background-color:#161B22; border:1px solid #30363D; border-radius:6px; padding:10px; margin-bottom:10px;'>
                <div style='font-weight:bold; border-bottom:1px solid #444; margin-bottom:8px; padding-bottom:4px;'>Ficha Técnica de Rutas</div>
                <div style='margin-bottom:4px;'><span class='legend-dot' style='background-color:#42A5F5;'></span>B10 (Corriente)</div>
                <div style='margin-bottom:4px;'><span class='legend-dot' style='background-color:#66BB6A;'></span>B27 (Expreso)</div>
                <div><span class='legend-dot' style='background-color:#EF5350;'></span>H20 (Troncal)</div>
                </div>
                """, unsafe_allow_html=True)
            with col_leg2:
                st.markdown("""
                <div style='background-color:#161B22; border:1px solid #30363D; border-radius:6px; padding:10px; margin-bottom:10px;'>
                <div style='font-weight:bold; border-bottom:1px solid #444; margin-bottom:8px; padding-bottom:4px;'>Semáforo Andén Q(t)</div>
                <div style='margin-bottom:4px;'><span class='legend-dot' style='background-color:#43A047;'></span>Normal (&lt; 50 pax)</div>
                <div style='margin-bottom:4px;'><span class='legend-dot' style='background-color:#FB8C00;'></span>Congestión (50-150 pax)</div>
                <div><span class='legend-dot' style='background-color:#E53935;'></span>Saturación (&gt; 150 pax)</div>
                </div>
                """, unsafe_allow_html=True)
                
            st.pydeck_chart(pdk.Deck(
                layers=layers, 
                initial_view_state=view_state, 
                map_style=pdk.map_styles.CARTO_DARK, 
                tooltip={"text": "{tooltip_text}", "style": {"color": "white", "backgroundColor": "#161B22", "border": "1px solid #30363D"}}
            ), use_container_width=True)
            
        with col_tel:
            st.markdown("### 🚨 Auditoría de Incidentes")
            st.markdown(f"<div style='color: #8B949E; margin-top:-10px; margin-bottom:15px;'>Corte instantáneo: {formatted_time}</div>", unsafe_allow_html=True)
            
            st.markdown("<div class='incident-panel'>", unsafe_allow_html=True)
            # 1. Collapse Monitor (Q > 150)
            st.markdown("#### 🚉 Estaciones Colapsadas")
            alert_stations = st_data[st_data["cola"] >= 150].sort_values(by="cola", ascending=False)
            if len(alert_stations) > 0:
                for _, r in alert_stations.iterrows():
                    st.markdown(f"<div class='incident-item'><b>{r['nombre']}</b>: {int(r['cola'])} pasajeros esperando evacuación.</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='incident-item incident-warning' style='border-color:#43A047;'>Capacidad de andén bajo control operativo.</div>", unsafe_allow_html=True)
                
            # 2. Bursting Buses (Pax >= 152)
            st.markdown("<h4 style='margin-top:20px;'>🚍 Flota en Sobrecupo Crítico (≥95%)</h4>", unsafe_allow_html=True)
            if active_buses > 0:
                full_buses = df_buses_curr[df_buses_curr["pasajeros"] >= 152].sort_values(by="pasajeros", ascending=False)
                if len(full_buses) > 0:
                    for _, r in full_buses.iterrows():
                        color = "#42A5F5" if r["ruta"]=="B10" else "#66BB6A" if r["ruta"]=="B27" else "#EF5350"
                        st.markdown(f"<div class='incident-item'><span style='color:{color}; font-weight:bold;'>{r['ruta']}</span> (ID: {r['id_bus']}): {r['pasajeros']}/160 pax ({(r['pasajeros']/160)*100:.1f}%)</div>", unsafe_allow_html=True)
                else:
                    st.markdown("<div class='incident-item incident-warning' style='border-color:#43A047;'>Sin eventos de hacinamiento crítico registrados.</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='incident-item incident-warning' style='border-color:#8B949E;'>No hay telemetría de vehículos rodando en este momento.</div>", unsafe_allow_html=True)
            
            st.markdown("</div>", unsafe_allow_html=True)
            
        st.divider()
        st.markdown("### 📜 Bitácora Histórica de Incidentes (Post-Mortem del Escenario)")
        st.markdown("Auditoría agregada de todos los eventos críticos ocurridos durante la franja operativa simulada, aislando los picos máximos de saturación para evitar analizar minuto a minuto.")
        
        col_hist_est, col_hist_bus = st.columns(2)
        
        with col_hist_est:
            st.markdown("#### 🚉 Colapsos en Andén (Q > 150 pax)")
            # Aggregate station incidents
            df_incidentes_est = colas_df[colas_df["cola_pasajeros"] >= 150].copy()
            if len(df_incidentes_est) > 0:
                hist_est = df_incidentes_est.groupby("codigo_estacion").agg(
                    Pico_Maximo=("cola_pasajeros", "max"),
                    Inicio_Colapso=("tiempo_seg", "min"),
                    Fin_Colapso=("tiempo_seg", "max")
                ).reset_index()
                hist_est = pd.merge(hist_est, df_topo[["codigo", "nombre"]], left_on="codigo_estacion", right_on="codigo", how="left")
                hist_est["Inicio_Colapso"] = hist_est["Inicio_Colapso"].apply(lambda s: (dt_start + datetime.timedelta(seconds=s)).strftime("%I:%M:%S %p"))
                hist_est["Fin_Colapso"] = hist_est["Fin_Colapso"].apply(lambda s: (dt_start + datetime.timedelta(seconds=s)).strftime("%I:%M:%S %p"))
                hist_est = hist_est[["nombre", "Pico_Maximo", "Inicio_Colapso", "Fin_Colapso"]].rename(columns={"nombre": "Estación", "Pico_Maximo": "Máx Pasajeros"})
                st.dataframe(hist_est.sort_values(by="Máx Pasajeros", ascending=False), hide_index=True, use_container_width=True)
            else:
                st.success("Operación Perfecta: Ninguna estación superó el umbral de 150 pasajeros en todo el escenario.")
                
        with col_hist_bus:
            st.markdown("#### 🚍 Sobrecupos de Flota (Carga > 95%)")
            df_incidentes_bus = buses_df[buses_df["pasajeros"] >= 152].copy()
            if len(df_incidentes_bus) > 0:
                hist_bus = df_incidentes_bus.groupby(["id_bus", "ruta"]).agg(
                    Pico_Ocupacion=("pasajeros", "max"),
                    Inicio_Sobrecupo=("tiempo_seg", "min"),
                    Fin_Sobrecupo=("tiempo_seg", "max")
                ).reset_index()
                hist_bus["Inicio_Sobrecupo"] = hist_bus["Inicio_Sobrecupo"].apply(lambda s: (dt_start + datetime.timedelta(seconds=s)).strftime("%I:%M:%S %p"))
                hist_bus["Fin_Sobrecupo"] = hist_bus["Fin_Sobrecupo"].apply(lambda s: (dt_start + datetime.timedelta(seconds=s)).strftime("%I:%M:%S %p"))
                hist_bus = hist_bus[["ruta", "id_bus", "Pico_Ocupacion", "Inicio_Sobrecupo", "Fin_Sobrecupo"]].rename(columns={"ruta": "Ruta", "id_bus": "ID Bus", "Pico_Ocupacion": "Máx Pax"})
                st.dataframe(hist_bus.sort_values(by="Máx Pax", ascending=False), hide_index=True, use_container_width=True)
            else:
                st.success("Operación Confortable: Ningún bus alcanzó el 95% de su capacidad instalada (152 pax).")

    # TABS 2: BUS LOAD PROFILE
    with tab_bus:
        st.markdown("### Auditoría Físico-Estadística de Carga por Ruta")
        active_res = st.session_state["resultado_opt"] if ia_activa else st.session_state["resultado_base"]
        
        if hasattr(active_res, "perfil_carga_rutas") and len(active_res.perfil_carga_rutas) > 0:
            ruta_sel = st.selectbox("Seleccione la Ruta a auditar:", list(active_res.perfil_carga_rutas.keys()))
            df_perfil = pl.DataFrame(active_res.perfil_carga_rutas[ruta_sel]).to_pandas()
            
            fig_carga = px.line(
                df_perfil, x="estacion", y="promedio_a_bordo", markers=True,
                title=f"Perfil Histórico de Ocupación Promedio: {ruta_sel} a lo largo de la Troncal",
                template="plotly_dark",
                color_discrete_sequence=["#58A6FF"]
            )
            # Maximum Physical Capacity & Critical Crowding Zone
            fig_carga.add_hline(y=160, line_dash="dash", line_color="#E6EDF3", annotation_text="Límite Físico del Chasis (160 pax)")
            fig_carga.add_hrect(y0=152, y1=180, line_width=0, fillcolor="#E53935", opacity=0.15, annotation_text="⚠️ Hacinamiento Crítico (>95%)", annotation_position="top left")
            
            fig_carga.update_traces(
                hovertemplate="<b>%{x}</b><br>Ocupación Promedio: %{y:.1f} pax<br>Factor de Carga: %{customdata:.1f}%<extra></extra>",
                customdata=(df_perfil["promedio_a_bordo"]/160.0)*100
            )
            
            fig_carga.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis_tickangle=-45, yaxis_range=[0, 180], yaxis_title="Pasajeros Promedio A Bordo")
            st.plotly_chart(fig_carga, use_container_width=True)
        else:
            st.warning("No se detectó un perfil de carga válido en la memoria del motor.")

    # TABS 3: QUEUE DYNAMICS
    with tab_estaciones:
        st.markdown("### Serie Temporal: Acumulación vs Evacuación en Andén $Q(t)$")
        selected_station = st.selectbox("Auditar Estación Específica:", df_topo["nombre"].tolist())
        st_code = df_topo[df_topo["nombre"] == selected_station].iloc[0]["codigo"]
        
        df_cola_hist = colas_df[colas_df["codigo_estacion"] == st_code].copy()
        
        if len(df_cola_hist) > 0:
            df_cola_hist["hora_dt"] = df_cola_hist["tiempo_seg"].apply(lambda s: dt_start + datetime.timedelta(seconds=s))
            
            fig_q = px.line(
                df_cola_hist, x="hora_dt", y="cola_pasajeros", 
                title=f"Evolución Matemática de $Q(t)$ en {selected_station}",
                template="plotly_dark",
                color_discrete_sequence=["#FB8C00"]
            )
            fig_q.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", yaxis_title="Volumen Q(t) [Pasajeros]", xaxis_title="Reloj Operativo (HH:MM:SS)")
            
            # Scrubber Time marker
            fig_q.add_vline(x=current_dt.timestamp() * 1000, line_dash="solid", line_width=2, line_color="#58A6FF", annotation_text="▶ Instante de Inspección Actual")
            # Saturation thresholds
            fig_q.add_hline(y=150, line_dash="dash", line_color="#E53935", opacity=0.5, annotation_text="Riesgo de Colapso (>150 pax)")
            
            st.plotly_chart(fig_q, use_container_width=True)
        else:
            st.warning("No hay datos históricos para esta estación en la franja seleccionada.")

    # TABS 4: AI COMPARISON
    with tab_ia:
        st.markdown("### Contraste Científico Operacional: $S_{base}$ vs $S_{opt}$")
        if ia_activa:
            res_opt = st.session_state["resultado_opt"]
            opt_estado = st.session_state["mejor_estado"]
            
            col_l_ia, col_r_ia = st.columns(2)
            with col_l_ia:
                st.markdown("<div style='background-color:#21262d; padding:20px; border-radius:8px; border-left:4px solid #E53935;'>", unsafe_allow_html=True)
                st.markdown("#### 🔴 Operación Original (GTFS Oficial)")
                st.write(f"**Frecuencias Estáticas:** {frecuencias_oficiales}")
                st.write(f"**Tiempo de Espera Promedio:** {res_base.tiempo_espera_promedio_min:.2f} minutos")
                st.write(f"**Pasajeros Represados Totales:** {res_base.pasajeros_quedados_en_cola:,} personas")
                st.write(f"**Tasa de Sobrecupo Crítico:** {res_base.porcentaje_buses_sobrecupo:.1f}%")
                st.write(f"**Volumen de Flota Inyectada:** {res_base.total_buses_despachados} buses")
                st.markdown("</div>", unsafe_allow_html=True)

            with col_r_ia:
                st.markdown("<div style='background-color:#21262d; padding:20px; border-radius:8px; border-left:4px solid #43A047;'>", unsafe_allow_html=True)
                st.markdown("#### 🟢 Agente FlowTM (Simulated Annealing)")
                st.write(f"**Frecuencias Optimizadas:** {opt_estado.frecuencias}")
                st.write(f"**Tiempo de Espera Promedio:** {res_opt.tiempo_espera_promedio_min:.2f} minutos")
                st.write(f"**Pasajeros Represados Totales:** {res_opt.pasajeros_quedados_en_cola:,} personas")
                st.write(f"**Tasa de Sobrecupo Crítico:** {res_opt.porcentaje_buses_sobrecupo:.1f}%")
                st.write(f"**Volumen de Flota Inyectada:** {res_opt.total_buses_despachados} buses")
                st.markdown("</div>", unsafe_allow_html=True)
                
            st.divider()
            st.markdown("### 📥 Pipeline de Integración GTFS (`frequencies.txt`)")
            df_gtfs = pl.DataFrame([
                {"route_id": r, "start_time": f"{h_ini:02d}:00:00", "end_time": f"{h_fin:02d}:00:00", "headway_secs": int(m * 60), "exact_times": 0}
                for r, m in opt_estado.frecuencias.items()
            ])
            st.dataframe(df_gtfs.to_pandas(), hide_index=True, use_container_width=True)
            st.download_button(
                label="Descargar GTFS frequencies.txt (Horario Óptimo FlowTM)",
                data=df_gtfs.write_csv(),
                file_name="frequencies.txt",
                mime="text/csv",
                type="primary"
            )
        else:
            st.info("💡 Activa el **Agente Racional (IA)** en el panel lateral para computar la solución óptima y desbloquear el análisis comparativo.")

else:
    st.info("El Centro de Control está inactivo. Configura la ventana operativa y ejecuta la simulación en el panel lateral para comenzar.")
