# Flood & Climate Coursework

Моделювання затоплень для Одеси на основі DEM (SRTM) з алгоритмом зв'язаності та інтерактивною візуалізацією.

## Структура
- data/raw/ — сирі дані (архіви, вихідний DEM).
- data/processed/ — підготовлений odessa_dem.tif для моделювання.
- data/gis/ — проміжні/вихідні шари для картографії.
- notebooks/ — дослідження: 01_data_prep, 02_modeling, 03_mapping.
- src/ — ядро (loader, model, gis_utils, plots).
- dashboard.py — Streamlit-дашборд.
- main.py — місце для складання конвеєра (за потреби).

## Вимоги
```
pip install -r requirements.txt
```

## Як запустити
1. Підготовка DEM: відкрийте `notebooks/01_data_prep.ipynb` та збережіть `data/processed/odessa_dem.tif`.
2. Експеримент: у `notebooks/02_modeling.ipynb` порівняйте поріг vs зв'язаність для різних рівнів.
3. Візуалізація: у `notebooks/03_mapping.ipynb` побудуйте карти та, за бажання, експортуйте PNG для folium.
4. Інтерактивний фронтенд: `streamlit run dashboard.py` — оберіть рівень моря, перегляньте карти та площу затоплення.

## Примітки
- Алгоритм зв'язаності гарантує, що затоплені пікселі мають шлях до моря (NaN у DEM).
- Якщо `data/processed/odessa_dem.tif` відсутній, використовуйте сирий DEM з `data/raw/`.
