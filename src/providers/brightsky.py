"""
BrightSky / DWD-RADOLAN Radar Provider.

Provides real-time precipitation data from DWD RADOLAN radar via BrightSky API.
Covers Germany and border regions (RADOLAN domain).

API: https://brightsky.dev/
No API key required.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from providers.base import ProviderRequestError

logger = logging.getLogger("brightsky")

BRIGHTSKY_BASE_URL = "https://api.brightsky.dev/radar"
TIMEOUT = 8.0

# RADOLAN bounding box (approximate DE coverage)
_RADOLAN_LAT_MIN = 47.0
_RADOLAN_LAT_MAX = 55.1
_RADOLAN_LON_MIN = 5.8
_RADOLAN_LON_MAX = 15.1


@dataclass
class RadarFrame:
    """Single radar frame with precipitation rate."""
    timestamp: datetime   # tz-aware UTC
    precip_mm_h: float    # mm/h
    is_convective: bool = False  # True when WMO code indicates thunderstorm/hail


def within_radolan_coverage(lat: float, lon: float) -> bool:
    """Return True if coordinates are within RADOLAN coverage area."""
    return (
        _RADOLAN_LAT_MIN <= lat <= _RADOLAN_LAT_MAX
        and _RADOLAN_LON_MIN <= lon <= _RADOLAN_LON_MAX
    )


class BrightSkyProvider:
    """DWD RADOLAN radar data via BrightSky API."""

    @property
    def name(self) -> str:
        return "brightsky"

    def fetch_radar(self, lat: float, lon: float) -> list[RadarFrame]:
        """
        Fetch radar precipitation frames for a coordinate.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            List of RadarFrame, sorted ascending by timestamp. Empty on error.

        Raises:
            ProviderRequestError: On HTTP errors (caller may catch).
        """
        url = f"{BRIGHTSKY_BASE_URL}?lat={lat}&lon={lon}&format=plain"
        try:
            with httpx.Client(timeout=TIMEOUT) as client:
                response = client.get(url)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            logger.warning(f"BrightSky HTTP error {e.response.status_code}: {e}")
            raise ProviderRequestError("brightsky", f"HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            logger.warning(f"BrightSky request error: {e}")
            return []

        # Determine grid position for the queried lat/lon
        # latlon_position gives fractional x/y into the 2D grid
        latlon_pos = data.get("latlon_position", {})
        grid_x = int(round(latlon_pos.get("x", 0)))
        grid_y = int(round(latlon_pos.get("y", 0)))

        radar_list = data.get("radar", [])
        frames: list[RadarFrame] = []
        for entry in radar_list:
            try:
                ts_str = entry.get("timestamp")
                precip_grid = entry.get("precipitation_5")
                if ts_str is None or precip_grid is None:
                    continue
                dt = datetime.fromisoformat(ts_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)

                # precipitation_5 is a 2D grid: [row][col]
                # latlon_position.y = row, .x = col
                if isinstance(precip_grid, list) and precip_grid:
                    if isinstance(precip_grid[0], list):
                        # 2D grid — extract the cell at (row=grid_y, col=grid_x)
                        row = min(grid_y, len(precip_grid) - 1)
                        col = min(grid_x, len(precip_grid[row]) - 1)
                        precip_raw = precip_grid[row][col]
                    else:
                        # 1D array — use grid_x as index
                        idx = min(grid_x, len(precip_grid) - 1)
                        precip_raw = precip_grid[idx]
                else:
                    precip_raw = precip_grid

                # 0.01 mm per 5 min -> mm/h = value / 100 * 12
                mm_h = float(precip_raw) / 100.0 * 12.0
                frames.append(RadarFrame(timestamp=dt, precip_mm_h=mm_h))
            except (ValueError, TypeError, KeyError, IndexError) as e:
                logger.debug(f"Skipping malformed radar entry: {e}")
                continue

        frames.sort(key=lambda f: f.timestamp)
        return frames
