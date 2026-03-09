import numpy as np
from collections import deque


class FloodModel:
    """
    Connectivity-based marine flood model on bathymetric DEM.
    Physically correct: water enters ONLY from the open sea point.
    """

    def __init__(self, dem: np.ndarray):
        self.dem = dem.astype(float) # Масив висот DEM (float)
        self.shape = self.dem.shape # Кортеж (rows, cols)
        self.rows, self.cols = self.shape #Кількість рядків DEM (по вертикалі/горизонталі)

    # ---------------------------------------------------------
    # SEA LEVEL CALIBRATION
    # ---------------------------------------------------------
    def calibrate_sea_level(self) -> float:
        """
        Калібрування рівня моря: використовуємо 10x10 вікно в правому нижньому куті — гарантовано відкрите море.
        """
        w = 10
        window = self.dem[self.rows - w:self.rows, self.cols - w:self.cols]

        if np.all(np.isnan(window)):
            raise RuntimeError("Sea calibration window contains only NaNs.")

        return float(np.nanmedian(window))

    # ---------------------------------------------------------
    # NAIVE THRESHOLD
    # ---------------------------------------------------------
    def simple_threshold(self, water_level: float) -> np.ndarray:
        """
        Наївна маска затоплення: затоплюються всі пікселі нижче рівня води.
        """
        return self.dem <= water_level

    # ---------------------------------------------------------
    # CONNECTED MARINE FLOOD MODEL
    # ---------------------------------------------------------
    def calculate_flood(self, water_level: float) -> np.ndarray:
        """
        Фізично правильне заповнення.
        Затоплення лише з правого нижнього кута.
        """
        flooded = np.zeros(self.shape, dtype=bool) # Ініціалізуємо маску затоплення (False - не затоплено, True - затоплено)
        visited = np.zeros(self.shape, dtype=bool) # Маска відвіданих пікселів для обходу
        q = deque() # Черга для обходу в ширину (BFS)

        sr, sc = self.rows - 1, self.cols - 1 

        if self.dem[sr, sc] > water_level: 
            raise RuntimeError("Bottom-right pixel is not sea. DEM clipped or corrupted.")

        flooded[sr, sc] = True 
        visited[sr, sc] = True
        q.append((sr, sc))

        neighbors = [(-1, 0), (1, 0), (0, -1), (0, 1)]

        while q: # Поки черга не порожня
            r, c = q.popleft() # Витягуємо поточний піксель

            for dr, dc in neighbors: # Перебираємо сусідів (вгору, вниз, вліво, вправо)
                nr, nc = r + dr, c + dc # Координати сусіднього пікселя

                if 0 <= nr < self.rows and 0 <= nc < self.cols and not visited[nr, nc]: # Перевіряємо, чи сусідній піксель в межах DEM і не відвіданий
                    visited[nr, nc] = True # Позначаємо сусідній піксель як відвіданий
                    if self.dem[nr, nc] <= water_level: # Якщо висота сусіднього пікселя нижча або дорівнює рівню води, він затоплений
                        flooded[nr, nc] = True # Позначаємо сусідній піксель як затоплений
                        q.append((nr, nc)) # Додаємо сусідній піксель до черги для подальшого обходу

        return flooded # Повертаємо маску затоплення (True - затоплено, False - не затоплено)

    # ---------------------------------------------------------
    # FLOOD DEPTH
    # ---------------------------------------------------------
    def calculate_depth(self, flood_mask: np.ndarray, water_level: float) -> np.ndarray:
        """
        Computes flood depth for flooded cells; others are NaN.
        """
        depth = np.full(self.shape, np.nan, dtype=float) # Ініціалізуємо масив глибин затоплення NaN (для незатоплених пікселів)
        flooded = flood_mask.astype(bool) # Маска затоплення (True - затоплено, False - не затоплено)
        depth[flooded] = water_level - self.dem[flooded] # Глибина затоплення для затоплених пікселів: різниця між рівнем води і висотою DEM
        return depth 
