"""GIS helper utilities."""
import geopandas as gpd
import numpy as np
from rasterio.features import shapes
from rasterio.transform import xy
from shapely.geometry import shape


# def rc_to_lonlat(profile: dict, row: int, col: int):
#     """
#     Convert matrix indices (row, col) to geographic coordinates (lat, lon).
#     """
#     transform = profile["transform"]
#     x, y = xy(transform, row, col, offset="center")
#     # rasterio returns (x, y) = (lon, lat)
#     return y, x


 # отримуємо маску затоплення 0/1 враховуючи викревлення меркантора обчислюємо площу затоплення в км2
def flood_area_km2(mask, profile, bounds):
    transform = profile["transform"]

    lat = (bounds.top + bounds.bottom) / 2
    meters_per_degree = 111_320 * np.cos(np.deg2rad(lat))

    px_w = transform.a * meters_per_degree
    px_h = -transform.e * 111_320

    area_m2 = mask.sum() * px_w * px_h
    return area_m2 / 1e6


def generate_geojson_in_memory(dem, mask, model, water_level, profile):
    """
    Генерує GeoJSON із поточними даними затоплення ЛИШЕ В ПАМ'ЯТІ.
    Не пише жодних файлів на диск — немає race condition між сесіями.
    Повертає (geojson_str | None, кількість об'єктів).
    """
    if mask.sum() == 0:
        return None, 0

    depth_grid = model.calculate_depth(mask, water_level)
    features = []
    for geom, value in shapes(depth_grid, mask=mask, transform=profile["transform"]):
        if not np.isnan(value):
            features.append({
                "geometry": shape(geom),
                "properties": {"depth_m": round(float(value), 2)}
            })

    if not features:
        return None, 0

    gdf = gpd.GeoDataFrame.from_features(features, crs=profile["crs"])
    geojson_str = gdf.to_json()
    return geojson_str, len(gdf)
