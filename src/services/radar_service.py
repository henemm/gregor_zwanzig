"""
Radar Nowcasting Service.

Provides short-term precipitation forecasts ("fängt es in den nächsten
~20 Minuten an zu regnen?") as compact German text.

Sources (coordinate-based, automatic):
- BrightSky (RADOLAN) for Germany
- GeoSphere INCA for Austria
- Météo-France AROME-HD (via Open-Meteo) for France/Corsica/Benelux/NW-Italy
- Open-Meteo minutely_15 for global/fallback

Feature: Issue #656
SPEC: docs/specs/modules/radar_nowcast.md
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Callable, List, Optional

logger = logging.getLogger("radar_service")

# RADOLAN bounding box (DE)
_RADOLAN_LAT_MIN = 47.0
_RADOLAN_LAT_MAX = 55.1
_RADOLAN_LON_MIN = 5.8
_RADOLAN_LON_MAX = 15.1

# INCA bounding box (AT)
_INCA_LAT_MIN = 46.3
_INCA_LAT_MAX = 49.1
_INCA_LON_MIN = 9.5
_INCA_LON_MAX = 17.2

# AROME-HD bounding box (FR — incl. Corsica, FR-Alps, Pyrenees, Benelux, NW-Italy)
_AROME_FR_LAT_MIN = 41.0
_AROME_FR_LAT_MAX = 51.5
_AROME_FR_LON_MIN = -5.5
_AROME_FR_LON_MAX = 10.0

# ICON-D2 bounding box (Central Europe / Alps — DWD ICON-D2 ~2 km, Issue #761)
# Conservative rectangle; exact (rotated) grid fidelity comes from the all-None guard.
_ICON_D2_LAT_MIN = 44.0
_ICON_D2_LAT_MAX = 58.0
_ICON_D2_LON_MIN = 2.0
_ICON_D2_LON_MAX = 19.0

# Onset threshold: frames within 60 min from now considered "nowcast"
_NOWCAST_HORIZON_MIN = 60
_DRY_THRESHOLD_MM_H = 0.1

HTTPX_TIMEOUT = 8.0


@dataclass
class NowcastResult:
    """Result of a nowcast query."""
    onset_minutes: Optional[int]   # minutes until first wet frame, None if none
    intensity_label: str            # human-readable intensity
    source: str                     # "radar", "INCA", "AROME-FR", "minutely_15"
    frames: list = field(default_factory=list)
    is_convective: bool = False     # True when nowcast indicates thunderstorm/hail


class RadarNowcastService:
    """
    Coordinate-aware nowcasting service.

    DI-seam: pass frame_source=callable(lat,lon)->list[RadarFrame]
    for test injection (real data, no mocks).
    """

    def __init__(
        self,
        frame_source: Optional[Callable[[float, float], list]] = None,
    ) -> None:
        self._frame_source = frame_source

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def intensity_to_text(self, mm_per_h: float, is_convective: bool = False) -> str:
        """Map mm/h rate to German intensity label.

        Convective flag (thunderstorm/hail WMO 95/96/99) overrides all rate-based
        stages — even at very low precipitation rates.
        """
        if is_convective:
            return "Starker Hagel/Gewitter"
        # Guard: NaN or non-numeric input → treat as dry
        if not isinstance(mm_per_h, (int, float)) or mm_per_h != mm_per_h:
            return "Kein Niederschlag"
        if mm_per_h < _DRY_THRESHOLD_MM_H:
            return "Kein Niederschlag"
        if mm_per_h < 1.0:
            return "Leichter Regen"
        if mm_per_h < 4.0:
            return "Mäßiger Regen"
        return "Starker Regen"

    def _is_convective_weathercode(self, code) -> bool:
        """Return True if WMO weather code indicates convective activity (thunderstorm/hail)."""
        return code in (95, 96, 99)

    def get_nowcast(self, lat: float, lon: float) -> NowcastResult:
        """
        Fetch frames and derive nowcast result.

        If frame_source is injected, uses it (test DI seam).
        Otherwise uses coordinate-based source chain.
        """
        if self._frame_source is not None:
            frames = self._frame_source(lat, lon)
            source = "radar"
        else:
            frames, source = self._fetch_frames_with_fallback(lat, lon)

        return self._derive_result(frames, source)

    def format_now_text(self, result: NowcastResult) -> str:
        """Format nowcast result as 2-3 line German text."""
        lines: list[str] = []

        if result.onset_minutes is None:
            lines.append(result.intensity_label + ".")
            lines.append("In den nächsten 2 Stunden kein Regen erwartet.")
        else:
            now = datetime.now(tz=timezone.utc)
            onset_time = now + timedelta(minutes=result.onset_minutes)
            time_str = onset_time.astimezone().strftime("%H:%M")
            lines.append(f"{result.intensity_label} ab ca. {time_str} (in ~{result.onset_minutes} Min).")

        source_label = {
            "radar": "Radar (DWD)",
            "INCA": "INCA (GeoSphere AT)",
            "AROME-FR": "Météo-France AROME (1,5 km)",
            "ICON-D2": "DWD ICON-D2 (2 km)",
            "minutely_15": "Open-Meteo (global)",
        }.get(result.source, result.source)
        lines.append(f"Quelle: {source_label}.")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _fetch_frames_with_fallback(
        self, lat: float, lon: float
    ) -> tuple[list, str]:
        """Try source chain; return (frames, source_label)."""
        if _within_radolan(lat, lon):
            frames = self._fetch_brightsky(lat, lon)
            if frames:
                return frames, "radar"

        if _within_inca(lat, lon):
            frames = self._fetch_geosphere_inca(lat, lon)
            if frames:
                return frames, "INCA"

        if _within_arome_france(lat, lon):
            frames = self._fetch_arome_france_hd(lat, lon)
            if frames:
                return frames, "AROME-FR"

        if _within_icon_d2(lat, lon):
            frames = self._fetch_icon_d2(lat, lon)
            if frames:
                return frames, "ICON-D2"

        frames = self._fetch_openmeteo_minutely15(lat, lon)
        return frames, "minutely_15"

    def _fetch_brightsky(self, lat: float, lon: float) -> list:
        try:
            from providers.brightsky import BrightSkyProvider
            provider = BrightSkyProvider()
            return provider.fetch_radar(lat, lon)
        except Exception as e:
            logger.warning(f"BrightSky failed, falling back: {e}")
            return []

    def _fetch_geosphere_inca(self, lat: float, lon: float) -> list:
        try:
            from providers.geosphere import GeoSphereProvider
            from providers.brightsky import RadarFrame
            provider = GeoSphereProvider()
            ts = provider.fetch_nowcast(lat, lon)
            if not ts or not ts.data:
                return []
            frames = []
            for dp in ts.data:
                raw = dp.precip_1h_mm
                # Convert mm/interval to mm/h (INCA is 15-min steps); None -> dry frame
                mm_h = float(raw) * 4.0 if raw is not None else 0.0
                ts_val = dp.ts if dp.ts.tzinfo else dp.ts.replace(tzinfo=timezone.utc)
                frames.append(RadarFrame(timestamp=ts_val, precip_mm_h=mm_h))
            return frames
        except Exception as e:
            logger.warning(f"GeoSphere INCA failed, falling back: {e}")
            return []

    def _fetch_openmeteo_minutely15(self, lat: float, lon: float) -> list:
        return self._fetch_openmeteo_15(lat, lon)

    def _fetch_arome_france_hd(self, lat: float, lon: float) -> list:
        """Fetch AROME-HD (1.5 km) minutely_15 nowcast via Open-Meteo. Fail-soft -> []."""
        return self._fetch_openmeteo_15(lat, lon, models="arome_france_hd")

    def _fetch_icon_d2(self, lat: float, lon: float) -> list:
        """Fetch DWD ICON-D2 (~2 km) minutely_15 nowcast via Open-Meteo. Fail-soft -> []."""
        return self._fetch_openmeteo_15(lat, lon, models="icon_d2")

    def _fetch_openmeteo_15(
        self, lat: float, lon: float, models: Optional[str] = None
    ) -> list:
        """Shared Open-Meteo minutely_15 fetch/parse. Optional explicit model. Fail-soft -> []."""
        try:
            import httpx
            from providers.brightsky import RadarFrame
            model_param = f"&models={models}" if models else ""
            url = (
                f"https://api.open-meteo.com/v1/forecast"
                f"?latitude={lat}&longitude={lon}"
                f"{model_param}"
                f"&minutely_15=precipitation,weather_code"
                f"&timezone=UTC&forecast_minutely_15=96"
            )
            with httpx.Client(timeout=HTTPX_TIMEOUT) as client:
                resp = client.get(url)
                resp.raise_for_status()
                data = resp.json()
            m15 = data.get("minutely_15", {})
            times = m15.get("time", [])
            precip_vals = m15.get("precipitation", [])
            wcodes = m15.get("weather_code", [])
            # All-None guard: an explicit regional model (models set) returns
            # precipitation=[None, ...] for points outside its (rotated) grid — no
            # interpolation. Fall through to the global best_match instead of emitting
            # fake-zero frames. Global best_match (models=None) interpolates and never
            # returns all-None for land coords -> unchanged behavior (no regression).
            if models and precip_vals and all(v is None for v in precip_vals):
                return []
            frames = []
            for i, t_str in enumerate(times):
                dt = datetime.fromisoformat(t_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                raw = precip_vals[i] if i < len(precip_vals) else None
                if raw is None:
                    raw = 0.0
                # precipitation is mm per 15 min -> mm/h
                mm_h = float(raw) * 4.0
                code = wcodes[i] if i < len(wcodes) else None
                is_convective = self._is_convective_weathercode(code)
                frames.append(RadarFrame(timestamp=dt, precip_mm_h=mm_h, is_convective=is_convective))
            return frames
        except Exception as e:
            logger.warning(f"Open-Meteo minutely_15 (models={models}) failed: {e}")
            return []

    def _derive_result(self, frames: list, source: str) -> NowcastResult:
        """Derive onset_minutes and intensity_label from frames."""
        now = datetime.now(tz=timezone.utc)
        horizon = now + timedelta(minutes=_NOWCAST_HORIZON_MIN)

        # Filter to nowcast window
        window = [
            f for f in frames
            if f.timestamp >= now and f.timestamp <= horizon
        ]

        # onset_minutes: first frame with precip >= threshold
        onset_minutes: Optional[int] = None
        for frame in sorted(window, key=lambda f: f.timestamp):
            if frame.precip_mm_h >= _DRY_THRESHOLD_MM_H:
                delta = (frame.timestamp - now).total_seconds() / 60.0
                onset_minutes = max(0, round(delta))
                break

        # Max rate in window
        max_rate = max((f.precip_mm_h for f in window), default=0.0)

        # Convective flag: any wet frame in window with convective indicator
        is_convective = any(
            f.is_convective for f in window if f.precip_mm_h >= _DRY_THRESHOLD_MM_H
        )

        intensity_label = self.intensity_to_text(max_rate, is_convective=is_convective)

        return NowcastResult(
            onset_minutes=onset_minutes,
            intensity_label=intensity_label,
            source=source,
            frames=frames,
            is_convective=is_convective,
        )


def _within_radolan(lat: float, lon: float) -> bool:
    return (
        _RADOLAN_LAT_MIN <= lat <= _RADOLAN_LAT_MAX
        and _RADOLAN_LON_MIN <= lon <= _RADOLAN_LON_MAX
    )


def _within_inca(lat: float, lon: float) -> bool:
    return (
        _INCA_LAT_MIN <= lat <= _INCA_LAT_MAX
        and _INCA_LON_MIN <= lon <= _INCA_LON_MAX
    )


def _within_arome_france(lat: float, lon: float) -> bool:
    return (
        _AROME_FR_LAT_MIN <= lat <= _AROME_FR_LAT_MAX
        and _AROME_FR_LON_MIN <= lon <= _AROME_FR_LON_MAX
    )


def _within_icon_d2(lat: float, lon: float) -> bool:
    return (
        _ICON_D2_LAT_MIN <= lat <= _ICON_D2_LAT_MAX
        and _ICON_D2_LON_MIN <= lon <= _ICON_D2_LON_MAX
    )
