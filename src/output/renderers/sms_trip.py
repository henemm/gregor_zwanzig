"""
SMS trip formatter — Adapter (β3 Channel-Renderer-Split).

SPEC: docs/specs/modules/output_channel_renderers.md §A3 (Adapter)
WIRE: docs/specs/modules/sms_format.md v2.0 §2/§3 (POSITIONAL)

Adapter-Vertrag (§A3):
  SMSTripFormatter bleibt importierbar, format_sms() delegiert intern an
  render_sms() (TokenLine-Pipeline). Output ist v2.0 (N12 D18 ..., Stage-
  Prefix '{Name}: '), kein Legacy 'E1:T12/18 | E2:...' mehr.

Domain-Logik (RiskEngine, Risk-Labels) bleibt für format_alert_sms() und
_detect_risk() erhalten (§A4 - Alert-Pfad nicht migriert in β3).
"""
from __future__ import annotations

import re
from dataclasses import replace
from typing import TYPE_CHECKING, Optional
from zoneinfo import ZoneInfo

from app.models import (
    ExposedSection, NormalizedTimeseries, RiskLevel, RiskType, SegmentWeatherData,
)
from services.risk_engine import RiskEngine
from utils.ascii_fold import fold_ascii
from utils.timezone import local_fmt, local_hour
from output.metric_format import thunder_label_value
from output.renderers.alert.official_alerts import dedupe_official_alerts
from output.renderers.day_window import build_day_window_points
from output.renderers.sms import render_sms
from output.tokens.builder import build_token_line
from output.tokens.dto import (
    DailyForecast, HourlyValue, MetricSpec, NormalizedForecast,
)
from output.tokens.hazard_symbols import (
    HAZARD_ORDER, LEVEL_LETTERS, LEVELLESS_HAZARDS,
    MIN_SMS_LEVEL, sms_symbol_for,
)

_ETAPPE_RE = re.compile(r'^Etappe\s+(\d+)', re.IGNORECASE)


def _sms_stage_prefix(name: str) -> str:
    """'Etappe N: subtitle' -> 'E{N}' for compact SMS prefix."""
    m = _ETAPPE_RE.match(name or "")
    if m:
        return f"E{m.group(1)}"
    return fold_ascii(name or "Etappe")[:10].rstrip(":")

if TYPE_CHECKING:
    from app.models import WeatherChange

# Issue #624: metric_id -> SMS-Symbol für threshold-fähige Metriken.
SMS_SYMBOL_BY_METRIC: dict[str, str] = {
    "precipitation": "R",
    "rain_probability": "PR",
    "wind": "W",
    "gust": "G",
    "thunder": "TH:",
    "snow_depth": "SN",
    "snowfall_limit": "SFL",
}

# RiskType → SMS risk label (German, ultra-compact). Used by format_alert_sms.
_SMS_RISK_LABELS: dict[tuple[RiskType, RiskLevel], str] = {
    (RiskType.THUNDERSTORM, RiskLevel.HIGH): "Gewitter",
    (RiskType.THUNDERSTORM, RiskLevel.MODERATE): "Gewitter",
    (RiskType.WIND, RiskLevel.HIGH): "Sturm",
    (RiskType.WIND, RiskLevel.MODERATE): "Wind",
    (RiskType.RAIN, RiskLevel.HIGH): "Regen",
    (RiskType.RAIN, RiskLevel.MODERATE): "Regen",
    (RiskType.WIND_CHILL, RiskLevel.HIGH): "Kaelte",
    (RiskType.POOR_VISIBILITY, RiskLevel.HIGH): "Nebel",
    (RiskType.WIND_EXPOSITION, RiskLevel.HIGH): "GratSturm",
    (RiskType.WIND_EXPOSITION, RiskLevel.MODERATE): "GratWind",
}


def _warn_hour(alert, tz: ZoneInfo) -> Optional[int]:
    """Beginn-Stunde einer amtlichen Warnung in Ortszeit — `None` bei
    ganztaegiger Gueltigkeit oder fehlendem Zeitraum (dann entfaellt `@h`
    ersatzlos). Ganztags-Erkennung wie `official_alerts._format_validity`."""
    vf, vt = alert.valid_from, alert.valid_to
    if not vf or not vt:
        return None
    vf_l, vt_l = vf.astimezone(tz), vt.astimezone(tz)
    if (vf_l.hour, vf_l.minute, vt_l.hour, vt_l.minute) == (0, 0, 23, 59):
        return None
    return vf_l.hour


def _official_alert_entries(
    segments: list[SegmentWeatherData], tz: ZoneInfo,
) -> tuple[tuple[str, str, Optional[int]], ...]:
    """Issue #1318: amtliche Warnungen aller Segmente -> Warn-Block-Tripel.

    Dedup ueber die geteilte `dedupe_official_alerts()` (kein eigener
    Dedup-Code), Filter auf Stufe >= orange, Kuerzel aus dem einzigen Katalog
    `hazard_symbols.py`. Sortierung: Stufe absteigend, bei Gleichstand
    Katalog-Reihenfolge — deterministisch, unabhaengig von `valid_from`.
    """
    tagged = [
        (alert, [])
        for seg in segments
        for alert in (getattr(seg, "official_alerts", None) or [])
    ]
    rows = []
    for alert, _ in dedupe_official_alerts(tagged):
        if alert.level < MIN_SMS_LEVEL:
            continue
        symbol = sms_symbol_for(alert.hazard)
        if alert.hazard in LEVELLESS_HAZARDS:
            entry = (symbol, "", None)
        else:
            entry = (symbol, LEVEL_LETTERS.get(alert.level, "H"), _warn_hour(alert, tz))
        rows.append((-alert.level, HAZARD_ORDER.get(alert.hazard, len(HAZARD_ORDER)), entry))
    rows.sort(key=lambda r: (r[0], r[1]))
    return tuple(entry for _lvl, _ord, entry in rows)


def _segments_to_normalized_forecast(
    segments: list[SegmentWeatherData],
    *,
    tz: ZoneInfo = ZoneInfo("UTC"),
    night_weather: Optional[NormalizedTimeseries] = None,
) -> NormalizedForecast:
    """Aggregate trip segments into a single-day NormalizedForecast.

    Pre-β3 the SMS used per-segment min/max; v2.0 uses one Tag-Min (N) /
    Tag-Max (D) for the whole day. We aggregate across all segments.
    Hourly samples are derived from segment aggregates (synthetic peaks
    placed at segment-start-hour) so the render_threshold_peak_value()
    path of the builder produces the right '{val}@{hour}h' tokens.

    Issue #1317 / Epic #1319 Scheibe A: R/PR/W/G/TH-Token kommen aus dem
    geteilten Tagesfenster 04:00-19:00 (``day_window.build_day_window_points``)
    statt nur aus der Wanderzeit — ortsgenau bis zur Ankunft entlang der
    Route, danach am Ziel (``night_weather``).
    """
    if not segments:
        raise ValueError("Cannot build forecast: no segments")

    temps_min = [s.aggregated.temp_min_c for s in segments
                 if s.aggregated.temp_min_c is not None]
    temps_max = [s.aggregated.temp_max_c for s in segments
                 if s.aggregated.temp_max_c is not None]
    day_min = min(temps_min) if temps_min else None
    day_max = max(temps_max) if temps_max else None

    rain_samples: list[HourlyValue] = []
    wind_samples: list[HourlyValue] = []
    gust_samples: list[HourlyValue] = []
    pop_samples: list[HourlyValue] = []
    thunder_samples: list[HourlyValue] = []

    # Bug #925: Stunden-Token aus der ECHTEN Stunden-Zeitreihe (Ortszeit)
    # ableiten — deckungsgleich mit der E-Mail-Tabelle. Onset@h(Peak@h) statt
    # Etappen-Summe @ Etappen-Start. Vorbild: _build_stage_trend.
    for dp in build_day_window_points(segments, night_weather, tz=tz):
        lh = local_hour(dp.ts, tz)
        if dp.precip_1h_mm is not None and dp.precip_1h_mm > 0:
            rain_samples.append(HourlyValue(lh, float(dp.precip_1h_mm)))
        if dp.wind10m_kmh is not None and dp.wind10m_kmh > 0:
            wind_samples.append(HourlyValue(lh, float(dp.wind10m_kmh)))
        if dp.gust_kmh is not None and dp.gust_kmh > 0:
            gust_samples.append(HourlyValue(lh, float(dp.gust_kmh)))
        pop = getattr(dp, "pop_pct", None)
        if pop is not None and pop > 0:
            pop_samples.append(HourlyValue(lh, float(pop)))
        # Issue #1275 / ADR-0025: Gewitter aus DERSELBEN gefensterten
        # Zeitreihe wie Regen/Wind/Boeen. Ohne diese Zeile bleibt
        # thunder_hourly leer und `TH:` ist strukturell immer "-".
        th_val = thunder_label_value(dp.thunder_level)
        if th_val > 0:
            thunder_samples.append(HourlyValue(lh, float(th_val)))

    # Fail-soft: Segmente ohne Stunden-Zeitreihe (Provider-Fehler) → Etappen-
    # Aggregat am Etappen-Start als Rückfall (Bug #398-Verhalten). Bleibt
    # unveraendert ausserhalb des Tagesfensters, da diese Segmente auch nicht
    # in build_day_window_points() einfliessen.
    for seg in segments:
        ts = seg.timeseries
        if ts is not None and ts.data:
            continue
        agg = seg.aggregated
        hour = local_hour(seg.segment.start_time, tz)
        if agg.precip_sum_mm is not None and agg.precip_sum_mm > 0:
            rain_samples.append(HourlyValue(hour, float(agg.precip_sum_mm)))
        if agg.wind_max_kmh is not None and agg.wind_max_kmh > 0:
            wind_samples.append(HourlyValue(hour, float(agg.wind_max_kmh)))
        if agg.gust_max_kmh is not None and agg.gust_max_kmh > 0:
            gust_samples.append(HourlyValue(hour, float(agg.gust_max_kmh)))
        if agg.pop_max_pct is not None and agg.pop_max_pct > 0:
            pop_samples.append(HourlyValue(hour, float(agg.pop_max_pct)))

    # Bug #925 / F002: Grenz-Stunden zwischen aufeinanderfolgenden Etappen
    # (seg1.end_h == seg2.start_h, beide inklusiv) können dieselbe Stunde doppelt
    # liefern. Pro Ortszeit-Stunde nur den Höchstwert behalten — deterministisch
    # und konsistent mit der Peak-/Onset-Logik.
    def _dedup_by_hour(samples: list[HourlyValue]) -> tuple[HourlyValue, ...]:
        best: dict[int, float] = {}
        for s in samples:
            if s.hour not in best or s.value > best[s.hour]:
                best[s.hour] = s.value
        return tuple(HourlyValue(h, best[h]) for h in sorted(best))

    rain_samples_d = _dedup_by_hour(rain_samples)
    wind_samples_d = _dedup_by_hour(wind_samples)
    gust_samples_d = _dedup_by_hour(gust_samples)
    pop_samples_d = _dedup_by_hour(pop_samples)
    thunder_samples_d = _dedup_by_hour(thunder_samples)

    # Issue #121: worst-case daily confidence aggregation over segments.
    confs = [s.aggregated.confidence_pct_min for s in segments
             if s.aggregated.confidence_pct_min is not None]
    day_confidence = min(confs) if confs else None

    today = DailyForecast(
        temp_min_c=day_min,
        temp_max_c=day_max,
        rain_hourly=rain_samples_d,
        pop_hourly=pop_samples_d,
        wind_hourly=wind_samples_d,
        gust_hourly=gust_samples_d,
        thunder_hourly=thunder_samples_d,
        confidence_pct_min=day_confidence,
    )
    return NormalizedForecast(
        days=(today,),
        official_alerts=_official_alert_entries(segments, tz),
    )


class SMSTripFormatter:
    """SMS trip-report formatter (Adapter, β3).

    format_sms() delegiert nach β3 an render_sms(); Output ist sms_format.md
    v2.0-konform. format_alert_sms() bleibt unverändert (§A4).
    """

    def format_sms(
        self,
        segments: list[SegmentWeatherData],
        max_length: int = 160,
        exposed_sections: Optional[list[ExposedSection]] = None,
        *,
        stage_name: Optional[str] = None,
        report_type: str = "evening",
        tz: ZoneInfo = ZoneInfo("UTC"),
        thresholds: Optional[dict[str, float]] = None,
        thunder_forecast: Optional[dict] = None,
        disabled_specs: Optional[list[MetricSpec]] = None,
        night_weather: Optional[NormalizedTimeseries] = None,
    ) -> str:
        """Generate v2.0 SMS via TokenLine pipeline.

        Args:
            segments: SegmentWeatherData list (Story 2)
            max_length: max SMS length (sms_format.md §1, default 160)
            exposed_sections: kept for API parity (Risk-Pfad rebuild)
            stage_name: prefix '{Name}: ' (v2.0 §2). Default: 'Etappe'.
            report_type: 'morning' or 'evening' (default 'evening').
            tz: Zielzeitzone für Stunden-Token (Bug #398). Default UTC
                (abwärtskompatibel: UTC→UTC = keine Verschiebung).
            thresholds: Issue #624 — optionale Map {SMS-Symbol: Schwellwert}.
                None = bisheriges DEFAULTS-Verhalten (bit-identisch).
            night_weather: Issue #1317 / Epic #1319 — Rohdaten Ankunft→06:00
                am Ziel; None = fail-soft, reine Segment-Fensterung (AC-9).

        Returns:
            v2.0 wire-format string, ≤ max_length chars.

        Raises:
            ValueError: empty segments.
        """
        if not segments:
            raise ValueError("Cannot format SMS with no segments")
        self._exposed_sections = exposed_sections
        self._tz = tz

        forecast = _segments_to_normalized_forecast(segments, tz=tz, night_weather=night_weather)

        # Bug #874: TH+: immer als days[1] einbauen — TH+:- wenn kein Gewitter (Spec-Pflicht).
        # Issue #1275 / ADR-0025 Entscheidung 3: Level-Wert kommt aus der
        # kanonischen Render-Skala thunder_label_value() (NONE=0/MED=2/HIGH=3,
        # passend zu tokens/metrics.LEVELS) — NICHT aus thunder_ordinal(), das
        # ist die Sortier-Ordnung und wuerde MED als 'L' rendern.
        tomorrow_thunder: tuple = ()
        if thunder_forecast and "+1" in thunder_forecast:
            entry = thunder_forecast["+1"]
            lvl_val = thunder_label_value(entry.get("level"))
            hour = entry.get("hour")
            # ADR-0025 Entscheidung 4: Uhrzeiten werden durchgereicht, nie
            # erfunden. Fehlt die Stunde, entfaellt das Sample (TH+:-) — frueher
            # stand hier die hartkodierte 12, die wie eine Vorhersage aussah.
            if lvl_val > 0 and hour is not None:
                tomorrow_thunder = (HourlyValue(int(hour), float(lvl_val)),)
        tomorrow_day = DailyForecast(thunder_hourly=tomorrow_thunder)
        # `replace` statt Neubau: der Warn-Block (#1318) darf beim Anhaengen
        # des Folgetags nicht verlorengehen.
        forecast = replace(forecast, days=(forecast.days[0], tomorrow_day))

        # Worst-case WIND_EXPOSITION aus allen Segmenten bestimmen
        we_label: Optional[str] = None
        for seg in segments:
            label, _ = self._detect_risk(seg)
            if label in ("GratSturm", "GratWind"):
                if label == "GratSturm":
                    we_label = "GratSturm"
                    break
                we_label = "GratWind"

        # MetricSpec-Config: WE-Label + Issue #624 per-Symbol-Schwellwerte.
        config: list[MetricSpec] = []
        if we_label is not None:
            config.append(MetricSpec(
                symbol="WE",
                use_friendly_format=True,
                friendly_label=we_label,
            ))
        # Issue #624: threshold-fähige Symbole mit konfiguriertem Schwellwert
        # als MetricSpec in die Config mergen (additiv, bestehende WE-Spec bleibt).
        if thresholds:
            existing_syms = {s.symbol for s in config}
            for sym, thr in thresholds.items():
                if sym in existing_syms:
                    # Bestehende Spec aktualisieren (threshold setzen, Rest erhalten).
                    config = [
                        MetricSpec(
                            symbol=s.symbol,
                            enabled=s.enabled,
                            morning_enabled=s.morning_enabled,
                            evening_enabled=s.evening_enabled,
                            threshold=thr if s.symbol == sym else s.threshold,
                            use_friendly_format=s.use_friendly_format,
                            friendly_label=s.friendly_label,
                            format_mode=s.format_mode,
                        )
                        for s in config
                    ]
                else:
                    config.append(MetricSpec(symbol=sym, threshold=thr))

        # Bug #944: explizit deaktivierte Metriken (enabled=False) ans Config-Ende
        # hängen. _visible(spec_with_enabled_false) -> False unterdrückt die Token
        # (z.B. SN/SFL) auch wenn Schneedaten in der Vorhersage vorhanden sind.
        if disabled_specs:
            existing_syms = {s.symbol for s in config}
            config.extend(s for s in disabled_specs if s.symbol not in existing_syms)

        token_line = build_token_line(
            forecast,
            config if config else None,
            report_type=report_type,
            stage_name=_sms_stage_prefix(stage_name or "Etappe"),
        )
        return render_sms(token_line, max_length=max_length)

    def format_alert_sms(
        self,
        changes: list["WeatherChange"],
        trip_name: str,
        max_length: int = 160,
    ) -> str:
        """Format weather change alert as compact SMS (§A4 — unchanged)."""
        from app.metric_catalog import get_compact_label_for_field

        if not changes:
            return f"[{trip_name}] No changes"

        _severity_order = {"major": 3, "moderate": 2, "minor": 1}
        sorted_changes = sorted(
            changes,
            key=lambda c: _severity_order.get(c.severity.value, 0),
            reverse=True,
        )

        header = f"[{trip_name}] ALERT:"
        result = header

        for change in sorted_changes:
            label = get_compact_label_for_field(change.metric)
            if label:
                compact_label, unit = label
                part = f"{compact_label}{change.delta:+.0f}{unit}"
            else:
                part = f"{change.metric}{change.delta:+.0f}"

            candidate = result + " " + part
            if len(candidate) <= max_length:
                result = candidate
            else:
                break

        return result

    def _detect_risk(
        self,
        seg_data: SegmentWeatherData,
    ) -> tuple[Optional[str], Optional[str]]:
        """Detect segment risk via RiskEngine. Kept for legacy callers."""
        engine = RiskEngine()
        assessment = engine.assess_segment(
            seg_data,
            exposed_sections=getattr(self, "_exposed_sections", None),
        )
        if not assessment.risks:
            return (None, None)
        top = assessment.risks[0]
        label = _SMS_RISK_LABELS.get(
            (top.type, top.level), top.type.value.title()
        )
        # Bug #398: Risiko-Stunde in Ortszeit (Default UTC im Legacy-Pfad).
        tz = getattr(self, "_tz", ZoneInfo("UTC"))
        time_str = local_fmt(seg_data.segment.start_time, tz, "%Hh")
        return (label, time_str)
