import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import sqlite3
import os

# --- PAGE CONFIG ---
st.set_page_config(page_title="Go-Kart Engineering Suite", layout="wide")

# --- DATABASE LOAD ---
@st.cache_resource
def load_db():
    conn = sqlite3.connect(':memory:', check_same_thread=False)
    pd.read_csv('all_bikez_curated.csv', usecols=['Model', 'Power (hp)', 'Torque (Nm)']).to_sql('engines', conn, index=False)
    pd.read_csv('Data.csv').to_sql('materials', conn, index=False)
    return conn

conn = load_db()

# --- SIDEBAR ---
st.sidebar.header("🛠️ Engineering Inputs")
with st.sidebar.form("eng_form"):
    eng_mod = st.text_input("Engine Model", "pulsar 150")
    mat_choices = pd.read_sql("SELECT DISTINCT Material FROM materials", conn)
    mat_choice = st.selectbox("Frame Material", mat_choices['Material'])
    
    st.subheader("Chassis & Weights")
    l_base = st.number_input("Wheelbase L (m)", 1.05)
    w_track = st.number_input("Track Width W (m)", 1.2)
    h_cg = st.number_input("CG Height (m)", 0.28)
    tube_od = st.number_input("Tube Outer Diameter (m)", 0.030)
    tube_wall = st.number_input("Tube Wall Thickness (m)", 0.002)
    
    st.subheader("Steering Geometry")
    caster = st.number_input("Caster Angle (deg)", 12.0)
    kpi = st.number_input("Kingpin Inclination (deg)", 10.0)
    steer_angle = st.slider("Max Steer Angle (deg)", 15, 35, 25)
    
    st.subheader("Gearing")
    driven_t = st.number_input("Driven Teeth", 60)
    driver_t = st.number_input("Driver Teeth", 12)
    
    submit = st.form_submit_button("Calculate Full Engineering Suite")

if submit:
    # --- 1. DATA EXTRACTION & SAFETY ---
    mat = pd.read_sql(f"SELECT * FROM materials WHERE Material = '{mat_choice}' LIMIT 1", conn).iloc[0]
    E = float(mat['E']) * 1e6  # MPa to Pa
    Sy = float(mat['Sy']) * 1e6 # Yield Strength Pa
    
    eng = pd.read_sql(f"SELECT * FROM engines WHERE Model LIKE '%{eng_mod}%' LIMIT 1", conn)
    hp = float(eng.iloc[0,1]) if not eng.empty and pd.notnull(eng.iloc[0,1]) else 15.0
    trq = float(eng.iloc[0,2]) if not eng.empty and pd.notnull(eng.iloc[0,2]) else 13.0
    
    # --- 2. CALCULATIONS ---
    total_m = 75.0 + 85.0 # Driver + Kart
    W_total = total_m * 9.81
    
    # Chassis Mechanics
    max_bm = (W_total * l_base) / 4 
    # Moment of Inertia for tubing
    I_val = (np.pi/64) * (tube_od**4 - (tube_od - 2*tube_wall)**4)
    # Torsional Rigidity
    J_polar = 2 * I_val
    G = E / (2 * (1 + 0.3)) # Shear Modulus (approx Poisson's ratio 0.3)
    torsional_k = (G * J_polar) / l_base
    fos = Sy / ((max_bm * (tube_od/2)) / I_val)
    nat_freq = (1/(2*np.pi)) * np.sqrt(torsional_k / total_m)
    
    # Steering & Jacking
    r_turn = l_base / np.sin(np.radians(steer_angle))
    # Tire Jacking: H_lift = L_kingpin * sin(Steer) * sin(Caster)
    jacking_lift = (0.10 * np.sin(np.radians(steer_angle)) * np.sin(np.radians(caster))) * 1000 # in mm
    
    # Powertrain
    gr = driven_t / driver_t
    v_top = (((hp * 745.7 * 0.85) / (0.5 * 1.225 * 0.5 * 0.45))**(1/3)) * 3.6
    
    # Braking
    mu_tire = 0.8
    stop_dist = ((v_top/3.6)**2) / (2 * mu_tire * 9.81)
    heat_diss = 0.5 * total_m * (v_top/3.6)**2

    # --- 3. UI DISPLAY ---
    st.title(f"🚀 Comprehensive Engineering Report: {eng_mod}")
    
    tab1, tab2, tab3 = st.tabs(["📊 Performance Metrics", "📈 2D Analysis", "📐 Dynamics"])
    
    with tab1:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.subheader("🏗️ Chassis Mechanics")
            st.metric("Bending Moment", f"{max_bm:.1f} Nm")
            st.metric("Torsional Rigidity", f"{torsional_k:.1f} Nm/rad")
            st.metric("Factor of Safety", f"{fos:.2f}")
            st.metric("Natural Freq", f"{nat_freq:.2f} Hz")
        
        with c2:
            st.subheader("🎡 Steering & Jacking")
            st.metric("Turning Radius", f"{r_turn:.2f} m")
            st.metric("Inside Wheel Lift", f"{jacking_lift:.2f} mm")
            st.write(f"Caster: {caster}° | KPI: {kpi}°")
            
        with c3:
            st.subheader("🛑 Braking & Energy")
            st.metric("Stopping Dist", f"{stop_dist:.1f} m")
            st.metric("Kinetic Energy", f"{heat_diss/1000:.1f} kJ")
            st.write(f"Max Velocity: {v_top:.1f} km/h")

    with tab2:
        g1, g2 = st.columns(2)
        with g1:
            v_range = np.linspace(5, v_top + 20, 20)
            ke_range = 0.5 * total_m * (v_range/3.6)**2 / 1000
            fig1 = go.Figure(go.Scatter(x=v_range, y=ke_range, name="Heat Dissipation", fill='tozeroy', line=dict(color='red')))
            fig1.update_layout(title="Kinetic Energy (Heat Load) vs Speed", xaxis_title="Speed (km/h)", yaxis_title="Energy (kJ)", template="plotly_dark")
            st.plotly_chart(fig1)
            
        with g2:
            load_range = np.linspace(0, W_total * 1.5, 10)
            deflection = (load_range * l_base**3) / (48 * E * I_val) * 1000 # mm
            fig2 = go.Figure(go.Scatter(x=load_range, y=deflection, name="Frame Flex", line=dict(color='cyan')))
            fig2.update_layout(title="Chassis Deflection vs Load", xaxis_title="Load (N)", yaxis_title="Deflection (mm)", template="plotly_dark")
            st.plotly_chart(fig2)

    with tab3:
        st.subheader("Tire Slip Surface (Handling Stability)")
        s, a = np.linspace(5, 30, 20), np.linspace(5, 30, 20)
        z_slip = [[(total_m * 0.4 * (v**2 / (l_base / np.sin(np.radians(ang))))) / 1600 for v in s] for ang in a]
        fig3d = go.Figure(data=[go.Surface(z=z_slip, x=s*3.6, y=a, colorscale='Viridis')])
        fig3d.update_layout(scene=dict(xaxis_title='Speed (km/h)', yaxis_title='Steer Angle', zaxis_title='Slip Angle'), template="plotly_dark")
        st.plotly_chart(fig3d, use_container_width=True)

else:
    st.info("👈 Use the sidebar to input engineering parameters and hit 'Calculate'.")