import os
import numpy as np
import rasterio

def load_dem(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    with rasterio.open(path) as src:
        dem = src.read(1).astype(float)
        profile = src.profile
        bounds = src.bounds

    return dem, profile, bounds
