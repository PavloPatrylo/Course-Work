import os
import numpy as np
import rasterio

def load_dem(path: str):
    if not os.path.exists(path): # перевіряємо, чи існує файл за вказаним шляхом
        raise FileNotFoundError(path)

    with rasterio.open(path) as src: # відкриваємо файл за допомогою rasterio
        dem = src.read(1).astype(float) # читаємо перший бенд (зазвичай DEM має один бенд) і перетворюємо його на тип float
        profile = src.profile # Береться профіль файлу (profile) — це словник, який містить метадані: розмір растра, тип даних, координатну систему
        bounds = src.bounds # Береться bounding box (bounds) — це координати мінімальної та максимальної точки растра, які визначають його просторове розташування

    return dem, profile, bounds
