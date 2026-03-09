"""GIS helper utilities."""
import numpy as np
from rasterio.transform import xy


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

# def flood_area_km2(mask, profile):
#     transform = profile["transform"]
#     px_w = transform.a
#     px_h = -transform.e
#     return mask.sum() * px_w * px_h / 1e6

# import numpy as np
# from rasterio.transform import xy

# def flood_area_km2(mask, profile):
#     t = profile["transform"]
#     h, w = mask.shape

#     m_per_deg_lat = 111_320.0

#     # широти центрів рядків
#     # rasterio.transform.xy повертає (x, y)=(lon, lat)
#     rows = np.arange(h)
#     _, lats = xy(t, rows, np.zeros(h, dtype=int), offset="center")
#     lats = np.asarray(lats)

#     m_per_deg_lon = 111_320.0 * np.cos(np.deg2rad(lats))

#     px_w_m_per_row = abs(t.a) * m_per_deg_lon   # (h,)
#     px_h_m = abs(t.e) * m_per_deg_lat           # константа

#     flooded_per_row = mask.sum(axis=1).astype(float)  # (h,)
#     area_m2 = np.sum(flooded_per_row * px_w_m_per_row * px_h_m)
#     return area_m2 / 1e6
