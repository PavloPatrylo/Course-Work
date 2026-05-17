import os
import numpy as np
import pandas as pd
import pathlib
import rasterio
import streamlit as st
from scipy.interpolate import interp1d


IPCC_CSV_PATH = pathlib.Path("ipcc_scenarios.csv")

def load_dem(path: str):
    if not os.path.exists(path): # перевіряємо, чи існує файл за вказаним шляхом
        raise FileNotFoundError(path)

    with rasterio.open(path) as src: # відкриваємо файл за допомогою rasterio
        dem = src.read(1).astype(float) # читаємо перший бенд (зазвичай DEM має один бенд) і перетворюємо його на тип float
        profile = src.profile # Береться профіль файлу (profile) — це словник, який містить метадані: розмір растра, тип даних, координатну систему
        bounds = src.bounds # Береться bounding box (bounds) — це координати мінімальної та максимальної точки растра, які визначають його просторове розташування

    return dem, profile, bounds


def get_ipcc_projections():
    if not IPCC_CSV_PATH.exists():
        st.error(f"Файл {IPCC_CSV_PATH} не знайдено. Створіть його за зразком у README.")
        st.stop()

    df = pd.read_csv(IPCC_CSV_PATH)

    if "year" not in df.columns:
        st.error("CSV повинен мати колонку 'year'.")
        st.stop()

    anchor_years = df["year"].tolist()
    scenario_cols = [c for c in df.columns if c != "year"]

    interp_funcs = {
        name: interp1d(anchor_years, df[name].tolist(), kind='quadratic', fill_value="extrapolate")
        for name in scenario_cols
    }

    scenarios = list(interp_funcs.values())
    f_min = interp_funcs.get('SSP1-1.9', scenarios[0])
    f_mid = interp_funcs.get('SSP2-4.5', scenarios[1] if len(scenarios) > 1 else scenarios[0])
    f_max = interp_funcs.get('SSP5-8.5', scenarios[2] if len(scenarios) > 2 else scenarios[0])

    return f_min, f_mid, f_max, anchor_years, interp_funcs
