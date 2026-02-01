import streamlit as st
import numpy as np
import pathlib
import geopandas as gpd
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

import plotly.express as px
import plotly.graph_objects as go
from plotly.colors import make_colorscale

from scipy.interpolate import interp1d
from rasterio.features import shapes
from shapely.geometry import shape

# === ІМПОРТ ВАШИХ МОДУЛІВ ===
from src.loader import load_dem
from src.model import FloodModel
from src.gis_utils import flood_area_km2

# =========================================================
# УПРАВЛІННЯ СТАНОМ СТОРІНОК
# =========================================================
if 'page' not in st.session_state:
    st.session_state.page = 'map'

def switch_to_stats():
    st.session_state.page = 'stats'

def switch_to_map():
    st.session_state.page = 'map'

# =========================================================
# НАЛАШТУВАННЯ КОЛЬОРІВ
# =========================================================
terrain_like = make_colorscale([
    "#3366cc", "#66ccff", 
    "#66ff66", "#cccc66", 
    "#996633", "#ffffff"
])
WATER_COLOR = "#17175C"
ERROR_COLOR = "red"

# =========================================================
# ДАНІ IPCC AR6
# =========================================================
def get_ipcc_projections():
    years = [2020, 2030, 2050, 2100, 2150]
    
    data = {
        'SSP1-1.9': [0.0, 0.09, 0.18, 0.38, 0.57],
        'SSP2-4.5': [0.0, 0.09, 0.20, 0.56, 0.92],
        'SSP5-8.5': [0.0, 0.10, 0.23, 0.77, 1.32],
        'SSP5-8.5 (Low Conf)': [0.0, 0.10, 0.24, 0.88, 1.98], 
        'High-Impact': [0.0, 0.3, 0.6, 1.80, 4.80]
    }
    
    f_min = interp1d(years, data['SSP1-1.9'], kind='quadratic', fill_value="extrapolate")
    f_mid = interp1d(years, data['SSP2-4.5'], kind='quadratic', fill_value="extrapolate")
    f_max = interp1d(years, data['SSP5-8.5'], kind='quadratic', fill_value="extrapolate")
    
    return f_min, f_mid, f_max, years, data

def generate_geojson(dem, mask, model, water_level, profile):
    if mask.sum() == 0: return None, 0
    depth_grid = model.calculate_depth(mask, water_level)
    features = []
    for geom, value in shapes(depth_grid, mask=mask, transform=profile["transform"]):
        if not np.isnan(value):
            features.append({"geometry": shape(geom), "properties": {"depth_m": round(float(value), 2)}})
    if not features: return None, 0
    gdf = gpd.GeoDataFrame.from_features(features, crs=profile["crs"])
    return gdf.to_json(), len(gdf)

# =========================================================
# STREAMLIT SETUP
# =========================================================
st.set_page_config(page_title="Flood Risk Odessa", page_icon="🌊", layout="wide")

@st.cache_resource
def init_system():
    path = pathlib.Path("data/raw/OSNOVA.tif")
    if not path.exists(): path = pathlib.Path("data/raw/Suvorov.tif")
    if not path.exists(): return None, None, None, None, None, None

    dem, profile, bounds = load_dem(str(path))
    model = FloodModel(dem)
    try: sea_bias = model.calibrate_sea_level()
    except: sea_bias = 0.0
    base_mask = model.calculate_flood(sea_bias)
    return dem, model, profile, bounds, sea_bias, base_mask

with st.spinner("Завантаження системи..."):
    dem, model, profile, bounds, sea_bias, base_mask = init_system()
    f_min, f_mid, f_max, ipcc_years, ipcc_data = get_ipcc_projections()

if dem is None:
    st.error(" Файл DEM не знайдено.")
    st.stop()

# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.title(" Налаштування")
    
    if st.session_state.page == 'map':
        st.subheader("1. Сценарій IPCC")
        year = st.selectbox("Рік прогнозу:", [2030, 2050, 2100, 2150], index=1)
        
        v_l = float(f_min(year))
        v_m = float(f_mid(year))
        v_h = float(f_max(year))
        
        st.markdown(f"""
        <div style="background-color:#f0f2f6; padding:10px; border-radius:5px;">
            🟢 Low: <b>{v_l:.2f} m</b><br>
            🟡 Mid: <b>{v_m:.2f} m</b><br>
            🔴 High: <b>{v_h:.2f} m</b>
        </div>
        """, unsafe_allow_html=True)
        
        st.divider()
        st.subheader("2. Симуляція")
        
        # Зелений слайдер
        slider_max = 5.0
        pct_low = (v_l / slider_max) * 100
        pct_high = (v_h / slider_max) * 100
        slider_css = f"""
        <style>
        div.stSlider > div[data-baseweb="slider"] > div > div > div:nth-child(1) {{
            background: linear-gradient(to right, lightgray 0%, lightgray {pct_low}%, #2E8B57 {pct_low}%, #2E8B57 {pct_high}%, lightgray {pct_high}%, lightgray 100%) !important;
        }}
        div.stSlider > div[data-baseweb="slider"] > div > div > div > div[role="slider"] {{
            background-color: #2E8B57 !important;
            border-color: #2E8B57 !important;
        }}
        </style>
        """
        st.markdown(slider_css, unsafe_allow_html=True)
        
        water_rise = st.slider("Підняття рівня (м):", 0.0, 5.0, round(v_m, 2), 0.01)
        show_naive = st.checkbox("🔍 Показати помилки наївної моделі", False)
        st.caption(f"Sea bias: {sea_bias:.3f} m")
        
        st.divider()
        st.button("📊 Перейти до статистики", on_click=switch_to_stats, use_container_width=True)

    else:
        st.info("Ви знаходитесь у режимі розширеної аналітики.")
        st.button("⬅ Повернутися до карти", on_click=switch_to_map, use_container_width=True)

# =========================================================
# СТОРІНКА 1: КАРТА
# =========================================================
if st.session_state.page == 'map':
    total_level = sea_bias + water_rise
    bfs_mask = model.calculate_flood(total_level)
    risk_mask = bfs_mask & (~base_mask)
    area_km2 = flood_area_km2(risk_mask, profile, bounds)
    pixels_count = int(np.count_nonzero(risk_mask))

    st.title(" Аналіз ризиків затоплення: Одеса")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Рівень води", f"+{water_rise:.2f} м", delta=f"{water_rise - v_m:+.2f} м")
    c2.metric("Площа ризику", f"{area_km2:.2f} км²")
    c3.metric("Затоплені пікселі", f"{pixels_count:,}") 
    c4.metric("Статус", "Наївна модель" if show_naive else "BFS Модель")

    tab_map, tab_export = st.tabs(["🗺️ Карта Затоплення", "💾 Експорт"])

    with tab_map:
        fig = px.imshow(dem, color_continuous_scale=terrain_like, origin="upper", zmin=0, zmax=60, aspect="equal", title=f"Карта ризиків (+{water_rise:.2f} м)",
                                labels=dict(x="X", y="Y", color="Висота (м)"))
        if bfs_mask.any():
            fig.add_trace(go.Heatmap(z=np.where(bfs_mask, 1, np.nan), colorscale=[[0, WATER_COLOR], [1, WATER_COLOR]], opacity=0.6, showscale=False, name="Затоплення (BFS)", hoverinfo='skip'))
        if show_naive:
            naive_mask = model.simple_threshold(total_level)
            fps = naive_mask & (~bfs_mask)
            if fps.sum() > 0:
                fig.add_trace(go.Heatmap(z=np.where(fps, 1, np.nan), colorscale=[[0, ERROR_COLOR], [1, ERROR_COLOR]], opacity=0.9, showscale=False))
        fig.update_layout(dragmode="pan", margin=dict(l=0, r=0, t=40, b=0), height=650, coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)

    with tab_export:
        st.subheader("Експорт")
        if risk_mask.sum() > 0:
            if st.button("🚀 Згенерувати GeoJSON"):
                with st.spinner("Векторизація..."):
                    geojson, cnt = generate_geojson(dem, risk_mask, model, total_level, profile)
                if geojson:
                    st.success(f"Готово! {cnt} об'єктів.")
                    st.download_button("⬇ Завантажити", geojson, f"flood_{water_rise:.2f}m.geojson", "application/geo+json")
        else:
            st.info("Немає зон затоплення.")

# =========================================================
# СТОРІНКА 2: СТАТИСТИКА
# =========================================================
elif st.session_state.page == 'stats':
    st.title("📊 Аналітичний звіт")
    
    # --- 1. ПОКАЗНИКИ РАСТРУ  ---
    st.header("1. Показники растру (DEM)")
    with st.container():
        col1, col2, col3 = st.columns(3)
        width = dem.shape[1]
        height = dem.shape[0]
        total_px = width * height
        valid_px = np.count_nonzero(~np.isnan(dem))
        
        if profile["crs"] and profile["crs"].is_geographic:
            # Географічні координати (градуси)
            lat = (bounds.top + bounds.bottom) / 2
            px_w_deg = profile['transform'][0]
            px_h_deg = -profile['transform'][4]
            
            # Конвертація
            px_w_m = px_w_deg * 111_320 * np.cos(np.deg2rad(lat))
            px_h_m = px_h_deg * 111_320
            
            res_text = f"{px_w_m:.1f} м (X) × {px_h_m:.1f} м (Y)"
        else:
            res_text = f"{profile['transform'][0]:.1f} × {-profile['transform'][4]:.1f} м"
        # =======================================

        col1.metric("Розмір сітки", f"{width} x {height}")
        col2.metric("Розмір пікселя", res_text)
        col3.metric("Заповненість даними", f"{valid_px/total_px*100:.1f}%")
    st.divider()  
    # --- 2. ПОКАЗНИКИ РЕЛЬЄФУ ---
    st.header("2. Показники рельєфу")
    with st.container():
        min_elev = np.nanmin(dem)
        max_elev = np.nanmax(dem)
        mean_elev = np.nanmean(dem)
        median_elev = np.nanmedian(dem)
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Мін. висота", f"{min_elev:.2f} м")
        c2.metric("Макс. висота", f"{max_elev:.2f} м")
        c3.metric("Середня", f"{mean_elev:.2f} м")
        c4.metric("Медіана", f"{median_elev:.2f} м")
        
        fig_hist = px.histogram(
            dem.flatten()[::10], 
            nbins=100,
            title="Гістограма розподілу висот",
            labels={'value': 'Висота (м)'},
            color_discrete_sequence=['green']
        )
        fig_hist.update_layout(showlegend=False, height=300)
        st.plotly_chart(fig_hist, use_container_width=True)
    st.divider()

    # --- 3. ТАБЛИЦЯ IPCC ---
    st.header("3. Сценарії IPCC AR6 (Дані)")
    with st.expander("Розгорнути таблицю значень", expanded=False):
        df_ipcc = pd.DataFrame(ipcc_data)
        df_ipcc.insert(0, "Рік", ipcc_years)
        st.dataframe(
            df_ipcc.style.format("{:.2f} м", subset=list(ipcc_data.keys())),
            use_container_width=True
        )
    st.divider()

    # --- 4. ГРАФІК ДИНАМІКИ ---
    st.header("4. Динаміка підняття рівня моря")
    x_smooth = np.linspace(min(ipcc_years), max(ipcc_years), 200)
    fig_ipcc = go.Figure()

    f_low = interp1d(ipcc_years, ipcc_data['SSP1-1.9'], kind='quadratic')
    f_high = interp1d(ipcc_years, ipcc_data['SSP5-8.5'], kind='quadratic')
    
    fig_ipcc.add_trace(go.Scatter(x=x_smooth, y=f_high(x_smooth), mode='lines', line=dict(width=0), showlegend=False, hoverinfo='skip'))
    fig_ipcc.add_trace(go.Scatter(x=x_smooth, y=f_low(x_smooth), mode='lines', line=dict(width=0), 
                    fill='tonexty', fillcolor='rgba(52, 152, 219, 0.2)', name='Коридор (Low ... High)'))

    colors = {'SSP1-1.9': '#27ae60', 'SSP2-4.5': '#7f8c8d', 'SSP5-8.5': '#c0392b', 
              'SSP5-8.5 (Low Conf)': '#352bc0', 'High-Impact': '#8e44ad'}
    dashes = {'SSP1-1.9': 'solid', 'SSP2-4.5': 'solid', 'SSP5-8.5': 'solid', 
              'SSP5-8.5 (Low Conf)': 'dot', 'High-Impact': 'dot'}

    for name, vals in ipcc_data.items():
        f = interp1d(ipcc_years, vals, kind='quadratic')
        fig_ipcc.add_trace(go.Scatter(x=x_smooth, y=f(x_smooth), mode='lines', 
            line=dict(color=colors[name], width=3, dash=dashes[name]), name=name))

    fig_ipcc.update_layout(height=500, xaxis_title="Рік", yaxis_title="Підняття (м)", hovermode="x unified")
    st.plotly_chart(fig_ipcc, use_container_width=True)
    st.divider()

    # --- 5. ПОРІВНЯННЯ ВПЛИВУ  ---
    st.header("5. Порівняння площі затоплення")
    st.write("Аналіз втрати території для різних сценаріїв.")
    
    comp_year = st.selectbox("Оберіть рік для аналізу:", [2030, 2050, 2100, 2150], index=2)
    
    if st.button(f" Розрахувати для {comp_year} року"):
        with st.spinner("Моделювання BFS для SSP1-1.9, SSP2-4.5, SSP5-8.5..."):
            y_idx = ipcc_years.index(comp_year)
            results = []
            
            target_scenarios = ['SSP1-1.9', 'SSP2-4.5', 'SSP5-8.5']
            
            for scenario_name in target_scenarios:
                values = ipcc_data[scenario_name]
                rise_val = values[y_idx]
                lvl = sea_bias + rise_val
                mask = model.calculate_flood(lvl) & (~base_mask)
                
                area_km2_val = flood_area_km2(mask, profile, bounds)
                area_m2_val = area_km2_val * 1_000_000
                
                results.append({
                    "Сценарій": scenario_name,
                    "Площа (м²)": area_m2_val, 
                    "Рівень (м)": rise_val
                })
            
            df_res = pd.DataFrame(results)
            
            fig_bar = px.bar(
            df_res, 
            x="Сценарій", 
            y="Площа (м²)", 
            text="Площа (м²)",
            title=f"Прогноз затоплення ({comp_year} рік)"
            )

            fig_bar.update_traces(marker_color="royalblue", texttemplate='%{text:.3s} м²', textposition='outside')
            fig_bar.update_layout(height=500)

            st.plotly_chart(fig_bar, use_container_width=True)

        for _, row in df_res.iterrows():
            st.warning(f"За сценарієм **{row['Сценарій']}** затопить **{row['Площа (м²)']:,.0f} м²** території.")
