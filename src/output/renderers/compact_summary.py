"""
F2 Kompakt-Summary — Natural-language weather summary per stage.

SPEC: docs/specs/modules/compact_summary.md v1.1

Generates 1-2 line summaries with temporal qualification
(peak times, rain start/end, gust peaks, thunder windows).
"""
from __future__ import annotations

import re
from typing import Optional
from zoneinfo import ZoneInfo

from utils.geo import degrees_to_compass
from utils.timezone import local_hour

from app.models import (
    ForecastDataPoint,
    NormalizedTimeseries,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    UnifiedWeatherDisplayConfig,
)
from services.weather_metrics import aggregate_stage
from output.renderers.day_window import build_day_window_points


# Klassifikation Issue #1214 Scheibe 5, Kategorie c: KEINE Migration auf
# metric_format.format_value. Die _format_*-Methoden erzeugen narrative
# Zusammenfassungssaetze (Temp-Spanne mit En-Dash, Regen-/Wind-Adjektive
# mit Zeitfenster-Mustern, Gewitter-Woerter) statt katalog-ableitbarer
# Zahl+Einheit-Formatierung. Die eigene Wolken-Emoji-Skala (<20/40/60/80)
# weicht bewusst von der Katalog-/helpers.py-Skala (<=10/30/70/90) ab —
# Angleichung ist PO-pflichtige Entscheidung, Gegenstand von Scheibe 6.
class CompactSummaryFormatter:
    """Generates natural-language weather summary per stage with temporal analysis."""

    _RAIN_DETECT = 0.1  # mm — threshold for "rain" vs "dry"

    def format_stage_summary(
        self,
        segments: list[SegmentWeatherData],
        stage_name: str,
        dc: UnifiedWeatherDisplayConfig,
        tz: Optional[ZoneInfo] = None,
        night_weather: Optional[NormalizedTimeseries] = None,
    ) -> str:
        """Wrapper ``context="route"`` (Trip/Etappe) um den geteilten Kern.

        Trip-spezifisch ist nur die Vorbereitung: Segmente -> Aggregat +
        Stundenliste, Etappenname -> Kurzform. Der Satz selbst entsteht im
        kontextneutralen ``format_weather_summary()`` (Issue #1278).

        ``night_weather``: Issue #1317 / Epic #1319 — Rohdaten Ankunft→06:00
        am Ziel, damit die Stundenliste dasselbe Tagesfenster 04-19 abdeckt
        wie SMS/Pillen/Telegram-Fusszeile (ADR-0025-Konsistenz).
        """
        effective_tz = tz or ZoneInfo("UTC")
        return self.format_weather_summary(
            self._aggregate(segments),
            self._collect_hourly_data(segments, night_weather, effective_tz),
            self._shorten_stage_name(stage_name),
            dc,
            tz,
        )

    def format_weather_summary(
        self,
        summary: Optional[SegmentWeatherSummary],
        hourly: list[ForecastDataPoint],
        title: str,
        dc: UnifiedWeatherDisplayConfig,
        tz: Optional[ZoneInfo] = None,
    ) -> str:
        """Kontextneutraler Kern (Issue #1278): ``(summary, hourly, titel, dc,
        tz) -> Fliesstext``.

        Kennt weder Etappen noch Orte — nur ein Aggregat, eine Stundenliste und
        einen bereits fertigen Titel. Beide Aufrufkontexte (``route`` = Etappe,
        ``vergleich`` = Ort) teilen sich diesen Code; es gibt KEINE zweite
        Text-Formatierungslogik (Trip/Compare-Teilungs-Invariante, CLAUDE.md).
        Der Titel wird hier NICHT mehr veraendert — die Etappen-Kuerzungsregel
        gehoert in den Trip-Wrapper, ein Ortsname darf nicht danach aussehen,
        als waere er ein Etappenname (AC-8).
        """
        self._tz = tz or ZoneInfo("UTC")
        short_name = title
        enabled = {mc.metric_id: mc for mc in dc.metrics if mc.enabled}

        parts: list[str] = []

        if "temperature" in enabled:
            t = self._format_temperature(summary, enabled["temperature"].use_friendly_format)
            if t:
                parts.append(t)

        if "cloud_total" in enabled:
            c = self._format_clouds(summary, enabled["cloud_total"].use_friendly_format)
            if c:
                parts.append(c)

        if "precipitation" in enabled or "rain_probability" in enabled:
            p = self._format_precipitation(summary, hourly, enabled.get("precipitation"))
            if p:
                parts.append(p)

        wind_enabled = "wind" in enabled or "gust" in enabled
        if wind_enabled:
            friendly = enabled.get("wind", enabled.get("gust"))
            w = self._format_wind(
                summary,
                hourly,
                friendly.use_friendly_format if friendly else True,
                wind_dir_enabled="wind_direction" in enabled,
            )
            if w:
                parts.append(w)

        if "thunder" in enabled:
            th = self._format_thunder(hourly, enabled["thunder"].use_friendly_format)
            if th:
                parts.append(th)

        weather = ", ".join(parts) if parts else ""
        if weather:
            return f"{short_name}: {weather}"
        return short_name

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    @staticmethod
    def _aggregate(segments: list[SegmentWeatherData]) -> Optional[SegmentWeatherSummary]:
        valid = [s for s in segments if not getattr(s, "has_error", False) and s.aggregated]
        if not valid:
            return None
        if len(valid) == 1:
            return valid[0].aggregated
        return aggregate_stage(valid)

    # ------------------------------------------------------------------
    # Hourly data collection
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_hourly_data(
        segments: list[SegmentWeatherData],
        night_weather: Optional[NormalizedTimeseries] = None,
        tz: Optional[ZoneInfo] = None,
    ) -> list[ForecastDataPoint]:
        """Stundenliste im Tagesfenster 04-19 (Issue #1317 / Epic #1319).

        Ortsgenau via geteiltem ``day_window``-Modul: bis zur Ankunft aus der
        Segment-Zeitreihe, danach aus ``night_weather`` am Ziel.
        """
        points = build_day_window_points(segments, night_weather, tz or ZoneInfo("UTC"))
        points.sort(key=lambda dp: dp.ts)
        return points

    # ------------------------------------------------------------------
    # Temperature
    # ------------------------------------------------------------------

    @staticmethod
    def _format_temperature(summary: Optional[SegmentWeatherSummary], friendly: bool) -> Optional[str]:
        if summary is None:
            return None
        t_min = summary.temp_min_c
        t_max = summary.temp_max_c
        if t_min is None and t_max is None:
            return None
        if t_min is not None and t_max is not None:
            return f"{int(round(t_min))}–{int(round(t_max))}°C"
        val = t_min if t_min is not None else t_max
        return f"{int(round(val))}°C"

    # ------------------------------------------------------------------
    # Clouds
    # ------------------------------------------------------------------

    @staticmethod
    def _format_clouds(summary: Optional[SegmentWeatherSummary], friendly: bool) -> Optional[str]:
        if summary is None or summary.cloud_avg_pct is None:
            return None
        pct = summary.cloud_avg_pct
        if friendly:
            # Issue #1214 Scheibe 6: kanonische Skala (PO-Entscheidung
            # 2026-07-12, statt der bisherigen lokalen <20/40/60/80-Stufen).
            from output.metric_format import cloud_emoji
            return cloud_emoji(pct)
        return f"Wolken {pct}%"

    # ------------------------------------------------------------------
    # Precipitation with temporal qualification
    # ------------------------------------------------------------------

    def _format_precipitation(
        self,
        summary: Optional[SegmentWeatherSummary],
        hourly: list[ForecastDataPoint],
        mc: Optional[object],
    ) -> Optional[str]:
        if summary is None:
            return None
        if not hourly:
            return None
        precip = sum(dp.precip_1h_mm or 0.0 for dp in hourly)
        if precip < self._RAIN_DETECT:
            return "trocken"

        adj = self._precip_adjective(precip)
        pattern = self._find_rain_pattern(hourly)

        if not pattern:
            return adj

        kind = pattern.get("kind")
        if kind == "throughout":
            return adj
        if kind == "peak":
            return f"{adj} max {pattern['peak_hour']}:00"
        if kind == "starts_later":
            return f"trocken, Regen ab {pattern['start_hour']}:00"
        if kind == "ends_early":
            end_h = pattern["end_hour"]
            dry_h = pattern.get("dry_from_hour", end_h + 1)
            return f"{adj} bis {end_h}:00, trocken ab {dry_h}:00"
        if kind == "window":
            return f"{adj} {pattern['start_hour']}:00–{pattern['end_hour']}:00"

        return adj

    @staticmethod
    def _precip_adjective(mm: float) -> str:
        if mm > 10:
            return "starker Regen"
        if mm > 2:
            return "mäßiger Regen"
        return "leichter Regen"

    def _find_rain_pattern(self, hourly: list[ForecastDataPoint]) -> Optional[dict]:
        if not hourly:
            return None

        rain_hours: list[int] = []
        dry_hours: list[int] = []
        peak_hour = None
        peak_val = 0.0

        for dp in hourly:
            p = dp.precip_1h_mm if dp.precip_1h_mm is not None else 0.0
            h = local_hour(dp.ts, self._tz)
            if p >= self._RAIN_DETECT:
                rain_hours.append(h)
                if p > peak_val:
                    peak_val = p
                    peak_hour = h
            else:
                dry_hours.append(h)

        if not rain_hours:
            return None

        all_hours = sorted(set(local_hour(dp.ts, self._tz) for dp in hourly))
        first_rain = min(rain_hours)
        last_rain = max(rain_hours)
        first_hour = min(all_hours)
        last_hour = max(all_hours)

        # All hours are rain → throughout (but check for significant peak)
        if len(rain_hours) >= len(all_hours):
            avg_rain = sum(dp.precip_1h_mm or 0 for dp in hourly) / len(hourly)
            if peak_hour is not None and avg_rain > 0 and peak_val >= avg_rain * 2:
                return {"kind": "peak", "peak_hour": peak_hour}
            return {"kind": "throughout"}

        # Dry-hour context around the rain block.
        dry_before_rain = [h for h in dry_hours if h < first_rain]
        dry_after_rain = [h for h in dry_hours if h > last_rain]
        isolated_before = len(dry_before_rain) >= 2 and first_rain > first_hour + 1
        isolated_after = len(dry_after_rain) >= 2 and last_rain < last_hour - 1

        # Isolated multi-hour shower (dry before AND after) → explicit window,
        # never "starts_later" alone (would hide that it stops again) nor
        # "ends_early" alone (would hide that it wasn't raining from the start).
        if isolated_before and isolated_after and first_rain != last_rain:
            return {"kind": "window", "start_hour": first_rain, "end_hour": last_rain + 1}

        # Dry start, rain continues to (near) window end → starts_later
        if isolated_before and not isolated_after:
            return {"kind": "starts_later", "start_hour": first_rain}

        # Rain present from (near) window start, stops early → ends_early
        if isolated_after and not isolated_before:
            return {
                "kind": "ends_early",
                "end_hour": last_rain,
                "dry_from_hour": last_rain + 1,
            }

        # Has a clear peak
        if peak_hour is not None and peak_val > 0:
            return {"kind": "peak", "peak_hour": peak_hour}

        return {"kind": "throughout"}

    # ------------------------------------------------------------------
    # Wind with temporal qualification
    # ------------------------------------------------------------------

    def _format_wind(
        self,
        summary: Optional[SegmentWeatherSummary],
        hourly: list[ForecastDataPoint],
        friendly: bool,
        wind_dir_enabled: bool = True,
    ) -> Optional[str]:
        if summary is None:
            return None
        if not hourly:
            return None
        wind_max = max((dp.wind10m_kmh or 0.0 for dp in hourly), default=None)
        gust_max = max((dp.gust_kmh or 0.0 for dp in hourly), default=None)

        if wind_max is None and gust_max is None:
            return None

        speed = wind_max if wind_max is not None else gust_max

        # Adjective
        if speed > 60:
            adj = "Sturmböen"
        elif speed > 35:
            adj = "starker Wind"
        elif speed > 15:
            adj = "mäßiger Wind"
        else:
            adj = "schwacher Wind"

        # Direction
        compass = ""
        if wind_dir_enabled and summary.wind_direction_avg_deg is not None and friendly:
            compass = f" {degrees_to_compass(summary.wind_direction_avg_deg)}"

        # Speed
        speed_str = f" {int(round(speed))} km/h" if speed is not None else ""

        # Gust peak time
        gust_peak = self._find_wind_peak(hourly)
        gust_part = ""
        if gust_peak and gust_max and speed and gust_max > speed * 1.3:
            gust_part = f", Böen bis {int(round(gust_max))} km/h ab {gust_peak['hour']}:00"

        return f"{adj}{compass}{speed_str}{gust_part}"

    def _find_wind_peak(self, hourly: list[ForecastDataPoint]) -> Optional[dict]:
        if not hourly:
            return None
        peak_hour = None
        peak_val = 0.0
        for dp in hourly:
            g = dp.gust_kmh if dp.gust_kmh is not None else 0.0
            if g > peak_val:
                peak_val = g
                peak_hour = local_hour(dp.ts, self._tz)
        if peak_hour is not None and peak_val > 0:
            return {"hour": peak_hour, "gust_kmh": peak_val}
        return None

    # ------------------------------------------------------------------
    # Thunder with time window
    # ------------------------------------------------------------------

    def _format_thunder(
        self,
        hourly: list[ForecastDataPoint],
        friendly: bool,
    ) -> Optional[str]:
        # ADR-0025 Entscheidung 1: kein ungefenstertes Aggregat als Tor für
        # nutzersichtbare Kanal-Aussagen. Die gefensterten Stundenwerte selbst
        # entscheiden, ob Gewitter gemeldet wird (Issue #1275).
        thunder_hours = []
        for dp in hourly:
            if dp.thunder_level and dp.thunder_level != ThunderLevel.NONE:
                thunder_hours.append(local_hour(dp.ts, self._tz))

        if not thunder_hours:
            return None

        start_h = min(thunder_hours)
        end_h = max(thunder_hours) + 1

        if friendly:
            return f"⚡ möglich {start_h}:00–{end_h}:00"
        return f"Gewitter möglich {start_h}:00–{end_h}:00"

    # ------------------------------------------------------------------
    # Stage name shortening
    # ------------------------------------------------------------------

    @staticmethod
    def _shorten_stage_name(name: str, max_len: int = 40) -> str:
        """Shorten 'Tag 3: von Sóller nach Tossals Verds' → 'Sóller → Tossals Verds'."""
        m = re.match(r"(?:Tag\s+\d+[:\s]*)?von\s+(.+?)\s+nach\s+(.+)", name, re.IGNORECASE)
        if m:
            short = f"{m.group(1)} → {m.group(2)}"
            return short[:max_len] if len(short) > max_len else short
        return name[:max_len] if len(name) > max_len else name

    # ------------------------------------------------------------------
    # Compass direction helper
    # ------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Wrapper context="vergleich" (Orts-Vergleich, Issue #1278)
# ---------------------------------------------------------------------------

def _location_tz(loc) -> Optional[ZoneInfo]:
    """``SavedLocation.timezone`` ist optional; fehlt/ungueltig -> None, der
    Kern faellt dann wie der Trip-Pfad auf UTC zurueck (keine neue
    Fehlerklasse, s. Spec "Known Limitations")."""
    name = getattr(loc.location, "timezone", None)
    if not name:
        return None
    try:
        return ZoneInfo(name)
    except Exception:
        return None


def format_location_summary(loc, enabled_metrics: Optional[set] = None) -> str:
    """Wrapper ``context="vergleich"``: ein ``LocationResult`` -> derselbe
    Fliesstext-Satz wie im Trip (geteilter Kern ``format_weather_summary``).

    - Titel = VOLLER Ortsname (keine Etappen-Kuerzung, AC-8).
    - Metrik-Quelle = ``enabled_metrics`` (Compare-Renderer-IDs), uebersetzt in
      das Trip-Vokabular ueber ``RENDERER_TO_TRIP_METRIC_ID``. Nur Zeilen mit
      Trip-Pendant landen im Satz (AC-5/AC-6).
    - ``enabled_metrics=None`` ("nie ausgewaehlt") = alles zeigen (AC-17).
    - Aggregat = ``summarize_points()`` (kanonische Trip-Rechenregeln, AC-7/15).
    - Fehler-Ort / keine Stundendaten -> "" (Aufrufer reiht leere Bloecke nicht
      ein, Anti-Erosion/AC-9).
    """
    from app.models import MetricConfig
    from output.renderers.compare_metric_ids import RENDERER_TO_TRIP_METRIC_ID
    from services.weather_metrics import summarize_points

    hourly = list(loc.hourly_data or [])
    if loc.error is not None or not hourly:
        return ""
    metric_ids = [
        trip_id for renderer_id, trip_id in RENDERER_TO_TRIP_METRIC_ID.items()
        if enabled_metrics is None or renderer_id in enabled_metrics
    ]
    if not metric_ids:
        return ""
    summary = summarize_points(hourly)
    if summary is None:
        return ""
    # use_friendly_format: bewusst der MetricConfig-Default (models.py:506,
    # `use_friendly_format: bool = True`) — der Ort-Wrapper verhaelt sich wie
    # ein frisch angelegter Trip. Der Compare-Pfad hat keine eigene Quelle
    # dafuer (kein UnifiedWeatherDisplayConfig je Ort).
    dc = UnifiedWeatherDisplayConfig(
        trip_id="vergleich",
        metrics=[MetricConfig(metric_id=m, enabled=True) for m in metric_ids],
    )
    return CompactSummaryFormatter().format_weather_summary(
        summary, hourly, loc.location.name, dc, _location_tz(loc),
    )

