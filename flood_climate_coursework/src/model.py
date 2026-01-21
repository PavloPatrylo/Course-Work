import numpy as np
from collections import deque


class FloodModel:
    """
    Connectivity-based marine flood model on bathymetric DEM.
    Physically correct: water enters ONLY from the open sea point.
    """

    def __init__(self, dem: np.ndarray):
        self.dem = dem.astype(float)
        self.shape = self.dem.shape
        self.rows, self.cols = self.shape

    # ---------------------------------------------------------
    # SEA LEVEL CALIBRATION
    # ---------------------------------------------------------
    def calibrate_sea_level(self) -> float:
        """
        Robust sea level calibration.
        Uses a 10x10 window in bottom-right corner — guaranteed open sea.
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
        Naive flood mask: all cells below water level.
        """
        return self.dem <= water_level

    # ---------------------------------------------------------
    # CONNECTED MARINE FLOOD MODEL
    # ---------------------------------------------------------
    def calculate_flood(self, water_level: float) -> np.ndarray:
        """
        Physically correct marine flood fill.
        Seeding only from bottom-right corner.
        """
        flooded = np.zeros(self.shape, dtype=bool)
        visited = np.zeros(self.shape, dtype=bool)
        q = deque()

        sr, sc = self.rows - 1, self.cols - 1

        if self.dem[sr, sc] > water_level:
            raise RuntimeError("Bottom-right pixel is not sea. DEM clipped or corrupted.")

        flooded[sr, sc] = True
        visited[sr, sc] = True
        q.append((sr, sc))

        neighbors = [(-1, 0), (1, 0), (0, -1), (0, 1)]

        while q:
            r, c = q.popleft()

            for dr, dc in neighbors:
                nr, nc = r + dr, c + dc

                if 0 <= nr < self.rows and 0 <= nc < self.cols and not visited[nr, nc]:
                    visited[nr, nc] = True
                    if self.dem[nr, nc] <= water_level:
                        flooded[nr, nc] = True
                        q.append((nr, nc))

        return flooded

    # ---------------------------------------------------------
    # FLOOD DEPTH
    # ---------------------------------------------------------
    def calculate_depth(self, flood_mask: np.ndarray, water_level: float) -> np.ndarray:
        """
        Computes flood depth for flooded cells; others are NaN.
        """
        depth = np.full(self.shape, np.nan, dtype=float)
        flooded = flood_mask.astype(bool)
        depth[flooded] = water_level - self.dem[flooded]
        return depth
