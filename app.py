import streamlit as st
import streamlit.components.v1 as components
import numpy as np
import pathlib
import pandas as pd

import plotly.express as px

from src.loader import load_dem, get_ipcc_projections
from src.model import FloodModel
from src.gis_utils import flood_area_km2, generate_geojson_in_memory
from src.plots import (
    build_folium_map,
    create_elevation_histogram,
    create_ipcc_projections_chart,
    create_main_map_figure,
)

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
# STREAMLIT SETUP
# =========================================================
st.set_page_config(page_title="Flood Risk Odessa", page_icon="🌊", layout="wide")


@st.cache_resource
def init_system():
    path = pathlib.Path("data/raw/OSNOVA.tif")
    if not path.exists():
        path = pathlib.Path("data/raw/FULL_ODESSA.tif")
    if not path.exists():
        return None, None, None, None, None, None

    dem, profile, bounds = load_dem(str(path))
    model = FloodModel(dem)
    try:
        sea_bias = model.calibrate_sea_level()
    except Exception:
        sea_bias = 0.0
    base_mask = model.calculate_flood(sea_bias)
    return dem, model, profile, bounds, sea_bias, base_mask


with st.spinner("Завантаження системи..."):
    dem, model, profile, bounds, sea_bias, base_mask = init_system()
    f_min, f_mid, f_max, ipcc_years, interp_funcs = get_ipcc_projections()

if dem is None:
    st.error("Файл DEM не знайдено.")
    st.stop()

# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.title("Налаштування")

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

        water_rise = st.slider(
            "Підняття рівня (м):",
            0.0, 5.0, round(v_m, 2), 0.01,
            key=f"water_rise_slider_{year}"
        )
        show_naive = st.checkbox(" Показати помилки наївної моделі", False)
        st.caption(f"Sea bias: {sea_bias:.3f} m")

        st.divider()
        st.subheader("3. Геофізичні фактори")

        TECTONIC_RATE_CM_PER_YEAR = 0.36
        tectonic_years = year - 2000
        h_tectonic = (TECTONIC_RATE_CM_PER_YEAR * tectonic_years) / 100

        use_tectonic = st.checkbox(
            f"Враховувати рух земної кори ({h_tectonic:.3f} м)",
            value=True
        )

        surge = st.slider(
            "Штормовий нагін (м):",
            0.0, 2.0, 0.0, 0.01,
            key="surge_slider"
        )

        st.divider()
        st.button(" Перейти до статистики", on_click=switch_to_stats, use_container_width=True)

    else:
        st.info("Ви знаходитесь у режимі розширеної аналітики.")
        st.button("⬅ Повернутися до карти", on_click=switch_to_map, use_container_width=True)

# =========================================================
# СТОРІНКА 1: КАРТА
# =========================================================
if st.session_state.page == 'map':
    # 1. ОБЧИСЛЕННЯ РІВНЯ ВОДИ ТА МОДЕЛЮВАННЯ ЗАТОПЛЕННЯ

    total_level = sea_bias + water_rise + (h_tectonic if use_tectonic else 0.0) + surge
    
    bfs_mask = model.calculate_flood(total_level)
    
    # Відфільтровуємо території, які вже є водою (base_mask), щоб отримати лише НОВІ зони ризику.
    risk_mask = bfs_mask & (~base_mask)
    
    # Розрахунок аналітичних метрик для дашборду
    area_km2 = flood_area_km2(risk_mask, profile, bounds)
    pixels_count = int(np.count_nonzero(risk_mask))

    # 2. ОПТИМІЗАЦІЯ РОБОТИ З ДАНИМИ (БАГАТОКОРИСТУВАЦЬКИЙ РЕЖИМ)
    # --- GeoJSON генерується в пам'яті для поточної сесії ---
    geojson_str, geojson_count = generate_geojson_in_memory(
        dem, risk_mask, model, total_level, profile
    )

    st.title("Аналіз ризиків затоплення: Одеса")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Рівень води", f"+{water_rise:.2f} м", delta=f"{water_rise - v_m:+.2f} м")
    c2.metric("Площа ризику", f"{area_km2:.2f} км²")
    c3.metric("Затоплені пікселі", f"{pixels_count:,}")
    c4.metric("Статус", "Наївна модель" if show_naive else "BFS Модель")

    # Розділення контенту на логічні вкладки для зручності
    tab_map, tab_export = st.tabs([" Карта Затоплення", " Експорт"])

    with tab_map:
        st.subheader("Фізична карта затоплення (DEM)")

        fig = create_main_map_figure(dem, base_mask, risk_mask, show_naive, water_rise, model, total_level)
        st.plotly_chart(fig, use_container_width=True, key="main_map_figure")


        # 6. ІНТЕРАКТИВНА КАРТА FOLIUM
        # Інтеграція звичайної веб-карти (OSM/Google Maps стилю) поверх згенерованих полігонів
        st.subheader("Інтерактивна карта затоплення ")
        folium_html = build_folium_map(geojson_str)
        components.html(folium_html, height=500, scrolling=False)

    # 7. ФУНКЦІОНАЛ ЕКСПОРТУ ДАНИХ
    with tab_export:
        st.subheader("Експорт")
        if risk_mask.sum() > 0 and geojson_str:
            # Передаємо рядок з пам'яті напряму — без читання файлу з диску.
            # Це дозволяє швидко завантажити результати моделювання у ГІС-системи (QGIS, ArcGIS).
            st.download_button(
                "⬇ Завантажити поточний GeoJSON",
                geojson_str,
                f"flood_{water_rise:.2f}m.geojson",
                "application/geo+json"
            )
            st.info(f"Файл містить дані для рівня **+{water_rise:.2f} м**.")
        else:
            st.info("Немає зон затоплення.")

# =========================================================
# СТОРІНКА 2: СТАТИСТИКА
# =========================================================
elif st.session_state.page == 'stats':
    st.title("Аналітичний звіт")

    st.header("1. Показники растру (DEM)")
    with st.container():
        col1, col2, col3 = st.columns(3)
        width = dem.shape[1]
        height = dem.shape[0]
        total_px = width * height
        valid_px = np.count_nonzero(~np.isnan(dem))

        if profile["crs"] and profile["crs"].is_geographic:
            lat = (bounds.top + bounds.bottom) / 2
            px_w_deg = profile['transform'][0]
            px_h_deg = -profile['transform'][4]
            px_w_m = px_w_deg * 111_320 * np.cos(np.deg2rad(lat))
            px_h_m = px_h_deg * 111_320
            res_text = f"{px_w_m:.1f} м (X) × {px_h_m:.1f} м (Y)"
        else:
            res_text = f"{profile['transform'][0]:.1f} × {-profile['transform'][4]:.1f} м"

        col1.metric("Розмір сітки", f"{width} x {height}")
        col2.metric("Розмір пікселя", res_text)
        col3.metric("Заповненість даними", f"{valid_px/total_px*100:.1f}%")
    st.divider()

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
        fig_hist = create_elevation_histogram(dem)
        st.plotly_chart(fig_hist, use_container_width=True, key="elevation_histogram")
    st.divider()

    st.header("3. Сценарії IPCC AR6 (Дані)")
    with st.expander("Розгорнути таблицю значень", expanded=False):
        display_years = list(range(2020, 2151, 10))
        df_ipcc = pd.DataFrame({"Рік": display_years})
        for name, fn in interp_funcs.items():
            df_ipcc[name] = np.maximum(0, fn(display_years)).round(3)
        st.dataframe(
            df_ipcc.style.format("{:.3f} м", subset=list(interp_funcs.keys())),
            use_container_width=True
        )
    st.divider()

    st.header("4. Динаміка підняття рівня моря")
    fig_ipcc = create_ipcc_projections_chart(ipcc_years, interp_funcs)
    st.plotly_chart(fig_ipcc, use_container_width=True, key="ipcc_projections_chart")
    st.divider()

    st.header("5. Порівняння площі затоплення")
    st.write("Аналіз втрати території для різних сценаріїв.")

    comp_year = st.selectbox("Оберіть рік для аналізу:", [2030, 2050, 2100, 2150], index=2)

    if st.button(f"Розрахувати для {comp_year} року"):
        with st.spinner("Моделювання BFS для SSP1-1.9, SSP2-4.5, SSP5-8.5..."):
            results = []
            target_scenarios = ['SSP1-1.9', 'SSP2-4.5', 'SSP5-8.5']

            for scenario_name in target_scenarios:
                rise_val = float(max(0, interp_funcs[scenario_name](comp_year)))
                lvl = sea_bias + rise_val
                mask = model.calculate_flood(lvl) & (~base_mask)
                area_km2_val = flood_area_km2(mask, profile, bounds)

                results.append({
                    "Сценарій": scenario_name,
                    "Площа (м²)": area_km2_val * 1_000_000,
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
            fig_bar.update_traces(
                marker_color="royalblue",
                texttemplate='%{text:.3s} м²',
                textposition='outside'
            )
            fig_bar.update_layout(height=500)
            st.plotly_chart(fig_bar, use_container_width=True, key=f"flood_area_comparison_{comp_year}")

        for _, row in df_res.iterrows():
            st.warning(
                f"За сценарієм **{row['Сценарій']}** затопить "
                f"**{row['Площа (м²)']:,.0f} м²** території."
            )
