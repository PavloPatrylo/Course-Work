import json

import folium
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from matplotlib.colors import LightSource


terrain_like = [
    [0.000, "#17175C"],
    [0.077, "#17175C"],
    [0.078, "#1a5c2a"],
    [0.20,  "#4caf50"],
    [0.40,  "#a5d96a"],
    [0.60,  "#d4b483"],
    [0.80,  "#996633"],
    [0.92,  "#c8a96e"],
    [1.00,  "#f5f5f5"],
]
WATER_COLOR  = "#12125B"
LAKE_COLOR   = "#0C59AB"
FLOOD_COLOR  = "#FF6600"   # помаранчевий — нові зони затоплення
ERROR_COLOR  = "red"


def build_folium_map(geojson_str=None):
    """
    Будує Folium-карту. Якщо передано geojson_str — накладає шар затоплення.
    Повертає HTML-рядок карти.
    """
    m = folium.Map(location=[46.4925, 30.7233], zoom_start=12)

    if geojson_str:
        try:
            geojson_data = json.loads(geojson_str)
            if geojson_data.get("features"):
                folium.GeoJson(
                    geojson_data,
                    name="Зони затоплення",
                    style_function=lambda x: {
                        'fillColor':  '#0000ff',
                        'color':  '#0000ff',
                        'weight': 1,
                        'fillOpacity': 0.5,
                    },
                    tooltip=folium.GeoJsonTooltip(
                        fields=['depth_m'],
                        aliases=['Глибина затоплення (м):']
                    )
                ).add_to(m)
        except Exception as e:
            st.warning(f"Не вдалося відобразити шар затоплення: {e}")

    folium.LayerControl().add_to(m)
    return m._repr_html_()


def create_main_map_figure(dem, base_mask, risk_mask, show_naive, water_rise, model, total_level):
    z_min = float(np.nanmin(dem))
    z_max = float(np.nanmax(dem))

    # 4. РЕНДЕРИНГ БАЗОВОЇ КАРТИ РЕЛЬЄФУ (Plotly)
    fig = px.imshow(
        dem,
        color_continuous_scale=terrain_like,
        origin="upper", zmin=z_min, zmax=z_max, aspect="equal",
        title=f"Карта ризиків (+{water_rise:.2f} м)",
        labels=dict(x="X", y="Y", color="Висота (м)")
    )

    # Додавання ефекту 3D-тіней (Hillshade) для кращого візуального сприйняття рельєфу
    dem_filled = np.where(np.isnan(dem), 0, dem)
    ls = LightSource(azdeg=315, altdeg=45)
    hillshade = ls.hillshade(dem_filled, vert_exag=4)
    fig.add_trace(go.Heatmap(
        z=hillshade,
        colorscale=[[0, "black"], [1, "white"]],
        opacity=0.25, showscale=False, hoverinfo='skip', name="Hillshade"
    ))

    # Відображення існуючих внутрішніх водойм та низин (озера/западини)
    landlocked_mask = ((dem <= -1) | (dem == 0)) & (~base_mask) & (~np.isnan(dem))
    if landlocked_mask.any():
        fig.add_trace(go.Heatmap(
            z=np.where(landlocked_mask, 1, np.nan),
            colorscale=[[0, LAKE_COLOR], [1, LAKE_COLOR]],
            opacity=1.0, showscale=False, hoverinfo='skip', name="Озера / западини"
        ))

    # Додавання топографічних ізоліній для оцінки крутизни схилів
    contour_step = max(1, int((z_max - max(z_min, 0)) / 12))
    fig.add_trace(go.Contour(
        z=dem,
        contours=dict(start=max(0, z_min), end=z_max, size=contour_step, coloring='none'),
        line=dict(color='rgba(60, 35, 10, 0.30)', width=0.6),
        showscale=False, hoverinfo='skip', name="Ізолінії"
    ))

    # 5. НАКЛАДАННЯ РЕЗУЛЬТАТІВ МОДЕЛЮВАННЯ ЗАТОПЛЕННЯ

    # Базові водойми (вже існували до симуляції) — темно-синім
    if base_mask.any():
        fig.add_trace(go.Heatmap(
            z=np.where(base_mask, 1, np.nan),
            colorscale=[[0, WATER_COLOR], [1, WATER_COLOR]],
            opacity=0.75, showscale=False, name="Базові водойми", hoverinfo='skip'
        ))

    # Нові зони затоплення (risk_mask = bfs_mask & ~base_mask) — помаранчевим
    if risk_mask.any():
        fig.add_trace(go.Heatmap(
            z=np.where(risk_mask, 1, np.nan),
            colorscale=[[0, FLOOD_COLOR], [1, FLOOD_COLOR]],
            opacity=0.80, showscale=False, name="Нові зони затоплення", hoverinfo='skip'
        ))

    # Режим порівняння (дебагу): показує зони, які "наївна" модель (просто по висоті) 
    # затопила б помилково, ігноруючи рельєфні перешкоди (напр. дамби)
    if show_naive:
        naive_mask = model.simple_threshold(total_level)
        bfs_mask = base_mask | risk_mask
        fps = naive_mask & (~bfs_mask) # False Positives
        if fps.sum() > 0:
            fig.add_trace(go.Heatmap(
                z=np.where(fps, 1, np.nan),
                colorscale=[[0, ERROR_COLOR], [1, ERROR_COLOR]],
                opacity=0.9, showscale=False
            ))
            
    fig.update_layout(
        dragmode="pan", margin=dict(l=0, r=0, t=40, b=0),
        height=650, coloraxis_showscale=False
    )
    return fig


def create_elevation_histogram(dem):
    fig_hist = px.histogram(
        dem.flatten()[::10],
        nbins=100,
        title="Гістограма розподілу висот",
        labels={'value': 'Висота (м)'},
        color_discrete_sequence=['green']
    )
    fig_hist.update_layout(showlegend=False, height=300)
    return fig_hist


def create_ipcc_projections_chart(ipcc_years, interp_funcs):
    x_smooth = np.linspace(min(ipcc_years), max(ipcc_years), 300)
    fig_ipcc = go.Figure()

    fig_ipcc.add_trace(go.Scatter(
        x=x_smooth, y=np.maximum(0, interp_funcs['SSP5-8.5'](x_smooth)),
        mode='lines', line=dict(width=0), showlegend=False, hoverinfo='skip'
    ))
    fig_ipcc.add_trace(go.Scatter(
        x=x_smooth, y=np.maximum(0, interp_funcs['SSP1-1.9'](x_smooth)),
        mode='lines', line=dict(width=0),
        fill='tonexty', fillcolor='rgba(52, 152, 219, 0.2)',
        name='Коридор (SSP1-1.9 … SSP5-8.5)'
    ))

    colors = {
        'SSP1-1.9': '#27ae60', 'SSP2-4.5': '#7f8c8d',
        'SSP5-8.5': '#c0392b', 'SSP5-8.5 (Low Conf)': '#352bc0',
        'High-Impact': '#8e44ad'
    }
    dashes = {
        'SSP1-1.9': 'solid', 'SSP2-4.5': 'solid',
        'SSP5-8.5': 'solid', 'SSP5-8.5 (Low Conf)': 'dot',
        'High-Impact': 'dot'
    }

    for name, fn in interp_funcs.items():
        fig_ipcc.add_trace(go.Scatter(
            x=x_smooth, y=np.maximum(0, fn(x_smooth)), mode='lines',
            line=dict(
                color=colors.get(name, '#333333'),
                width=3,
                dash=dashes.get(name, 'solid')
            ),
            name=name
        ))

    fig_ipcc.update_layout(
        height=500, xaxis_title="Рік",
        yaxis_title="Підняття (м)", hovermode="x unified"
    )
    return fig_ipcc
