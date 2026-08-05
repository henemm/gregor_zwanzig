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

from app.metric_catalog import get_sms_code
from app.models import (
    ExposedSection, NormalizedTimeseries, RiskLevel, RiskType, SegmentWeatherData,
)
from services.risk_engine import RiskEngine
from utils.ascii_fold import fold_ascii
from utils.timezone import local_fmt, local_hour
from output.metric_format import hail_priority, thunder_label_value
from output.renderers.alert.official_alerts import official_alerts_to_sms_entries
from output.renderers.day_window import (
    DAY_WINDOW_END_HOUR, DAY_WINDOW_START_HOUR, build_day_window_points,
    collect_hiking_window_points, hiking_field_min_max,
    night_temp_min_c, night_wind_chill_min_c,
)
from output.renderers.sms import render_sms
from output.tokens.builder import build_token_line
from output.tokens.dto import (
    DailyForecast, HourlyValue, MetricSpec, NormalizedForecast,
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
#
# Issue #1435 E3b: keine gepflegte Kürzel-Liste mehr, sondern eine ABLEITUNG
# aus dem zentralen Wetter-Register (`metric_catalog.sms_code`). Damit kann
# diese Tabelle nicht mehr vom Register abdriften. Die Renderer-Schicht darf
# das Register lesen und tut es bereits (alert/render.py, comparison.py); die
# app-freie Formatschicht `output/tokens/` darf es nicht und führt die Kürzel
# dort weiterhin als Literale (Schichtgrenze, abgesichert durch die Ratsche
# tests/unit/test_sms_token_symbol_register_ratchet.py).
_SMS_SYMBOL_METRIC_IDS: tuple[str, ...] = (
    "precipitation",
    "rain_probability",
    "wind",
    "gust",
    "thunder",
    "snow_depth",
    "snowfall_limit",
    "fresh_snow",
)

# Benannte Ausnahme von der Register-Ableitung: 'TH:' ist Grammatikform (der
# Doppelpunkt trennt die Gewitter-Stufe vom Kürzel ab, builder.py:16), das
# Register kennt nur 'TH'. Ausdrücklich NICHT durch #1435 E3b aufgehoben.
# Fix #1450/Adversary-F001: 'fresh_snow' ebenso -- das Register-Kuerzel ist
# 'NS' (metric_catalog.py:524), der tatsaechlich gerenderte Wintersport-Token
# ist 'NS24+' (builder.py::_wintersport, '24+'-Suffix ist Grammatik fuer das
# 24-Stunden-Fenster). Ohne diese Ausnahme wuerde SMS_SYMBOL_BY_METRIC das
# falsche Symbol 'NS' fuehren, das nirgends mit dem gerenderten Token
# uebereinstimmt -- die Abwahl (#944) griffe dadurch weiterhin nicht.
_SMS_SYMBOL_GRAMMAR: dict[str, str] = {"thunder": "TH:", "fresh_snow": "NS24+"}

SMS_SYMBOL_BY_METRIC: dict[str, str] = {
    metric_id: _SMS_SYMBOL_GRAMMAR.get(metric_id) or get_sms_code(metric_id)
    for metric_id in _SMS_SYMBOL_METRIC_IDS
}

# Issue #1410: metric_id -> MEHRERE SMS-Kuerzel derselben Metrik. Eigene
# Zuordnung, weil eine Metrik hier mehrere Symbole traegt (Nacht/Tiefst/
# Hoechst) — SMS_SYMBOL_BY_METRIC bildet 1:1 ab und wird zusaetzlich fuer
# Schwellwerte gelesen (#624), wo diese Symbole nichts zu suchen haben.
# Fix #1450/Adversary-F001: 'WC' (Wintersport-Tageskennzahl, builder.py::
# _wintersport) ergaenzt -- ohne diesen Eintrag baut trip_report.py:283-287
# keinen disabled_specs-Eintrag fuer WC, und die Abwahl von "Gefuehlte
# Temperatur" im Trip-Editor wirkt sich nicht auf WC aus.
# Fix #1415 (PO-Entscheidung 2026-08-03): die GEMESSENE Temperatur folgt
# derselben Regel -- 'N'/'K'/'D' hingen an keinem Eintrag und erschienen
# deshalb auch bei abgewaehlter Metrik "Temperatur" (Beleg: Trip KHW 403,
# "K13 D16 FK13 FD16 ..." bei ausgeschalteter Temperatur). Register-Kuerzel
# taugen dafuer nicht: get_sms_code("temperature") == 'D' waere nur eines von
# dreien, get_sms_code("temperature_cold") == 'N' gehoert zur internen
# Alarm-Pseudogroesse (selectable=False), und ein Eintrag in
# SMS_SYMBOL_BY_METRIC wuerde zusaetzlich einen Schwellwert auf 'D' legen
# (#624), den es fuer Temperatur-Token gar nicht gibt. Daher hier, in der
# frueher 'FELT' benannten Mehrfach-Tabelle.
# Fix #1482: 'thunder' traegt ZWEI Kuerzel -- 'TH:' (berichtete Etappe) und
# 'TH+:' (Folge-Etappe). 'TH+:' hing an keinem Eintrag und blieb deshalb auch
# nach Abwahl der Metrik "Gewitter" in der Kurzform stehen. SMS_SYMBOL_BY_METRIC
# bildet 1:1 ab (nur 'TH:') und wird zusaetzlich fuer Schwellwerte gelesen
# (#624) -- ein zweiter Eintrag dort wuerde das Schwellwert-Dict verfaelschen.
SMS_MULTI_SYMBOLS_BY_METRIC: dict[str, tuple[str, ...]] = {
    "temperature": ("N", "K", "D"),
    "wind_chill": ("FN", "FK", "FD", "WC"),
    "thunder": ("TH:", "TH+:"),
}

# RiskType → SMS risk label (German, ultra-compact). Used by format_alert_sms.
_SMS_RISK_LABELS: dict[tuple[RiskType, RiskLevel], str] = {
    (RiskType.THUNDERSTORM, RiskLevel.HIGH): "Gewitter",
    (RiskType.THUNDERSTORM, RiskLevel.MODERATE): "Gewitter",
    # Issue #1474 (AC-12): deutsches Wort statt generischem englischen
    # Fallback ("Thunderstorm").
    (RiskType.THUNDERSTORM, RiskLevel.LOW): "Gewitter leicht",
    (RiskType.WIND, RiskLevel.HIGH): "Sturm",
    (RiskType.WIND, RiskLevel.MODERATE): "Wind",
    (RiskType.RAIN, RiskLevel.HIGH): "Regen",
    (RiskType.RAIN, RiskLevel.MODERATE): "Regen",
    (RiskType.WIND_CHILL, RiskLevel.HIGH): "Kaelte",
    (RiskType.POOR_VISIBILITY, RiskLevel.HIGH): "Nebel",
    (RiskType.WIND_EXPOSITION, RiskLevel.HIGH): "GratSturm",
    (RiskType.WIND_EXPOSITION, RiskLevel.MODERATE): "GratWind",
}


def _official_alert_entries(
    segments: list[SegmentWeatherData], tz: ZoneInfo,
    min_level: Optional[int] = None,
) -> tuple[tuple[str, str, Optional[int]], ...]:
    """Issue #1318/#1332: duenner Wrapper -- Segmente zu einer flachen
    Alert-Liste zusammenfassen, dann den geteilten Kern
    `official_alerts_to_sms_entries()` aufrufen (kein zweiter Katalog, keine
    duplizierte Filterlogik). Compare-SMS (`comparison.py::render_compare_sms`)
    ruft denselben Kern mit `LocationResult.official_alerts` auf.

    Issue #1461 S3b-2a: `min_level=None` (kein Aufrufer hat eine Trip-
    Kanal-Schwelle uebergeben) faellt auf den Trip-Startwert 'gering' (Stufe
    2) zurueck -- NICHT auf `MIN_SMS_LEVEL` (Stufe 3), das bliebe nur der
    Ortsvergleich (unveraendert, S3b-2b)."""
    import services.alert_urgency as alert_urgency

    if min_level is None:
        min_level = alert_urgency.min_official_level_for_threshold("LOW")
    alerts = [
        alert
        for seg in segments
        for alert in (getattr(seg, "official_alerts", None) or [])
    ]
    return official_alerts_to_sms_entries(alerts, tz, min_level=min_level)


def _segments_to_normalized_forecast(
    segments: list[SegmentWeatherData],
    *,
    tz: ZoneInfo,
    night_weather: Optional[NormalizedTimeseries] = None,
    has_gap: bool = False,
    day_window_start_hour: int = DAY_WINDOW_START_HOUR,
    day_window_end_hour: int = DAY_WINDOW_END_HOUR,
    report_type: str = "evening",
    sms_alert_min_level: Optional[int] = None,
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

    ``has_gap`` (Issue #1331/#1334 F008): einziger Berechnungspunkt ist
    ``notification_service.compute_has_gap()`` (aus dem echten Renderer-
    Ergebnis, ``build_day_window_points``) — wird hier 1:1 durchgereicht,
    Dieser Renderer rechnet die Luecke nicht selbst nach.

    Issue #1402: `tz` ist PFLICHTPARAMETER — der einzige Aufrufer
    (`format_sms`) hat selbst schon einen echten `ZoneInfo`-Wert (nie
    ``None``, s. dessen eigener Default).
    Ein has_error-Segment, dessen Stunden im gerenderten Fenster von
    Nachbarsegmenten gedeckt werden, fehlt in ``build_day_window_points``
    NICHT und darf deshalb auch keinen Fehlalarm ausloesen — ein echter
    Ausfall fehlt dort real und wird von ``compute_has_gap`` ohnehin erkannt.
    """
    if not segments:
        raise ValueError("Cannot build forecast: no segments")

    # Issue #1417: K/D/FK/FD kommen aus der GETEILTEN Gehzeit-Fensterung
    # (day_window.collect_hiking_window_points) -- exakt derselben Punktliste,
    # aus der die Mail-Kachelzeile ihre Spanne bildet. Vorher las diese Stelle
    # `s.aggregated.*`, das die Ankunftsstunde des letzten Etappenteils
    # ausschliesst (segment_weather.py:254-273) -- daher Mail `13-17°C` vs.
    # SMS `K13 D16` fuer dieselbe Etappe. Issue #1410 (gefuehlt) verhaelt sich
    # dabei weiterhin exakt wie die gemessene Temperatur (F3).
    _hiking_points = collect_hiking_window_points(segments)
    _temp_extrema = hiking_field_min_max(_hiking_points, "t2m_c")
    _felt_extrema = hiking_field_min_max(_hiking_points, "wind_chill_c")

    def _agg(field_min: str, field_max: str) -> tuple[Optional[float], Optional[float]]:
        """Fail-soft: kein Etappenteil mit verwertbarer Zeitreihe (z. B. alle
        has_error, Bug-#398-Rueckfall) -> bisheriges Segment-Aggregat."""
        lows = [getattr(s.aggregated, field_min) for s in segments
                if getattr(s.aggregated, field_min) is not None]
        highs = [getattr(s.aggregated, field_max) for s in segments
                 if getattr(s.aggregated, field_max) is not None]
        return (min(lows) if lows else None), (max(highs) if highs else None)

    if _temp_extrema is not None:
        day_min, day_max = _temp_extrema[0], _temp_extrema[1]
    else:
        day_min, day_max = _agg("temp_min_c", "temp_max_c")
    if _felt_extrema is not None:
        felt_min, felt_max = _felt_extrema[0], _felt_extrema[1]
    else:
        felt_min, felt_max = _agg("wind_chill_min_c", "wind_chill_max_c")
    # Issue #1319 Scheibe D (DEC-1): abends echte Nacht-Tiefsttemperatur am
    # Schlafplatz -- fail-soft auf den Gehzeit-Tiefstwert, wenn night_weather
    # fehlt oder das Nachtfenster keine Punkte liefert (AC-6 dort).
    # Issue #1410: der Nachtwert ueberschreibt `temp_min_c` NICHT mehr in-place
    # (das wuerde K zerstoeren), sondern wohnt in einem eigenen Feld. Analog
    # fuer die gefuehlte Temperatur (F4).
    night_min = None
    night_felt_min = None
    if report_type == "evening":
        night_min = night_temp_min_c(night_weather, segments, tz)
        if night_min is None:
            night_min = day_min
        night_felt_min = night_wind_chill_min_c(night_weather, segments, tz)
        if night_felt_min is None:
            night_felt_min = felt_min

    rain_samples: list[HourlyValue] = []
    wind_samples: list[HourlyValue] = []
    gust_samples: list[HourlyValue] = []
    pop_samples: list[HourlyValue] = []
    thunder_samples: list[HourlyValue] = []
    hail_values: list[Optional[bool]] = []

    # Bug #925: Stunden-Token aus der ECHTEN Stunden-Zeitreihe (Ortszeit)
    # ableiten — deckungsgleich mit der E-Mail-Tabelle. Onset@h(Peak@h) statt
    # Etappen-Summe @ Etappen-Start. Vorbild: _build_stage_trend.
    for dp in build_day_window_points(
        segments, night_weather, tz=tz,
        start_hour=day_window_start_hour, end_hour=day_window_end_hour,
    ):
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
        # Issue #1475 S5a: Hagel-Kennzeichen aus DERSELBEN gefensterten
        # Zeitreihe wie die Gewitterstufe -- die ROHEN Werte inkl. `None`
        # ("unbekannt") sammeln, die Prioritaet entscheidet unten.
        hail_values.append(getattr(dp, "hail_flag", None))

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
        # Issue #1475 S5a: derselbe Fail-soft-Rueckfall wie oben -- Segmente
        # ohne Stunden-Zeitreihe steuern ihr Etappen-Aggregat bei.
        hail_values.append(getattr(agg, "hail_flag", None))

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

    # Issue #1450: Tages-Aggregat der Wintersport-Groessen aus den Segmenten
    # ableiten. Ohne dies blieb `today.snow_depth_cm`/`snowfall_limit_m`/
    # `snow_new_24h_cm` IMMER None und der Wintersport-Block lief leer --
    # unabhaengig vom (inzwischen entfernten) Profil-Gate im Token-Builder.
    # AV (Lawinenstufe) hat in SegmentWeatherSummary keine Entsprechung --
    # bleibt unveraendert None (kein Provider liefert Lawinenbulletins, s.
    # trip_result.py:54). WC (gefuehlte Einzeltemperatur) nutzt denselben
    # bereits berechneten Gehzeit-Extremwert wie FK (`felt_min`) -- fuer
    # eine einzelne Tageskennzahl ist der Tiefstwert die konservativere,
    # sicherheitsrelevantere Wahl (analog zur Schneefallgrenze, die ebenfalls
    # MIN aggregiert, s. Kommentar oben).
    _snow_depths = [s.aggregated.snow_depth_cm for s in segments
                    if s.aggregated.snow_depth_cm is not None]
    # Issue #1391: Schneefallgrenze ist die kanonische Trip-Regel MIN.
    _snowfall_limits = [s.aggregated.snowfall_limit_m for s in segments
                         if s.aggregated.snowfall_limit_m is not None]
    _snow_new = [s.aggregated.snow_new_sum_cm for s in segments
                 if s.aggregated.snow_new_sum_cm is not None]
    day_snow_depth = max(_snow_depths) if _snow_depths else None
    day_snowfall_limit = float(min(_snowfall_limits)) if _snowfall_limits else None
    day_snow_new = sum(_snow_new) if _snow_new else None

    today = DailyForecast(
        temp_min_c=day_min,
        temp_max_c=day_max,
        wind_chill_min_c=felt_min,
        wind_chill_max_c=felt_max,
        night_temp_min_c=night_min,
        night_wind_chill_min_c=night_felt_min,
        rain_hourly=rain_samples_d,
        pop_hourly=pop_samples_d,
        wind_hourly=wind_samples_d,
        gust_hourly=gust_samples_d,
        thunder_hourly=thunder_samples_d,
        confidence_pct_min=day_confidence,
        has_data_gap=has_gap,
        snow_depth_cm=day_snow_depth,
        snowfall_limit_m=day_snowfall_limit,
        snow_new_24h_cm=day_snow_new,
        wind_chill_c=felt_min,
        # Issue #1475 S5a: Prioritaet ja > unbekannt > nein ueber die rohen
        # Werte -- der EINE geteilte Aggregations-Helfer (kein zweiter
        # Rechenweg neben `weather_metrics._compute_hail_flag`).
        hail_flag=hail_priority(hail_values),
    )
    # Issue #1349: Flag ueber die Segmente aggregieren (Muster identisch zum
    # E-Mail-Renderer, output/renderers/email/unavailable_hint.py) — die
    # Erkennung selbst lebt am Fail-soft-Pfad des Schedulers (#1348).
    unavailable = any(
        getattr(seg, "official_alerts_unavailable", False) for seg in segments
    )
    return NormalizedForecast(
        days=(today,),
        official_alerts=_official_alert_entries(segments, tz, sms_alert_min_level),
        official_alerts_unavailable=unavailable,
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
        has_gap: bool = False,
        day_window_start_hour: int = DAY_WINDOW_START_HOUR,
        day_window_end_hour: int = DAY_WINDOW_END_HOUR,
        sms_alert_min_level: Optional[int] = None,
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
            has_gap: Issue #1331/#1334 F003 — vom echten Versandpfad bereits
                per ``notification_service.compute_has_gap()`` (aus
                ``day_window.build_day_window_points()``) ermittelte
                Ziel-Datenluecke, explizit durchgereicht statt hier aus
                ``night_weather`` neu abgeleitet zu werden. Default False
                (Vorschau/Tests ohne echten Versandpfad).
            sms_alert_min_level: Issue #1461 S3b-2a — niedrigste amtliche
                Warnstufe, die dieser Trip-Bericht zeigt (aus der Kanal-
                Schwelle des Nutzers fuer SMS). ``None`` (kein Aufrufer hat
                eine Trip-Einstellung, z.B. Vorschau/direkter Testaufruf)
                faellt auf den Startwert 'gering' (Stufe 2) zurueck --
                NICHT auf das aeltere ``MIN_SMS_LEVEL`` (Stufe 3).

        Returns:
            v2.0 wire-format string, ≤ max_length chars.

        Raises:
            ValueError: empty segments.
        """
        if not segments:
            raise ValueError("Cannot format SMS with no segments")
        self._exposed_sections = exposed_sections
        self._tz = tz

        forecast = _segments_to_normalized_forecast(
            segments, tz=tz, night_weather=night_weather, has_gap=has_gap,
            day_window_start_hour=day_window_start_hour,
            day_window_end_hour=day_window_end_hour,
            report_type=report_type,
            sms_alert_min_level=sms_alert_min_level,
        )

        # Bug #874: TH+: immer als days[1] einbauen — TH+:- wenn kein Gewitter (Spec-Pflicht).
        # Issue #1275 / ADR-0025 Entscheidung 3: Level-Wert kommt aus der
        # kanonischen Render-Skala thunder_label_value() (NONE=0/MED=2/HIGH=3,
        # passend zu tokens/metrics.LEVELS) — NICHT aus thunder_ordinal(), das
        # ist die Sortier-Ordnung und wuerde MED als 'L' rendern.
        tomorrow_thunder: tuple = ()
        # Fix #1482: echte Datenluecke der Folge-Etappe (Etappe existiert, aber
        # weder Trend noch Fallback-Fetch lieferten Daten) -> "TH+:?" statt der
        # Fehl-Entwarnung "TH+:-". Der Marker steht bewusst NICHT unter "+1"/
        # "+2" selbst, weil die E-Mail-Renderer diese Schluessel iterieren und
        # dort 'date'/'text' erwarten (Spec, Mangel 2, Punkt 1).
        tomorrow_gap = False
        if thunder_forecast and "+1" in thunder_forecast:
            entry = thunder_forecast["+1"]
            lvl_val = thunder_label_value(entry.get("level"))
            hour = entry.get("hour")
            # ADR-0025 Entscheidung 4: Uhrzeiten werden durchgereicht, nie
            # erfunden. Fehlt die Stunde, entfaellt das Sample (TH+:-) — frueher
            # stand hier die hartkodierte 12, die wie eine Vorhersage aussah.
            if lvl_val > 0 and hour is not None:
                tomorrow_thunder = (HourlyValue(int(hour), float(lvl_val)),)
        elif thunder_forecast:
            tomorrow_gap = "+1" in (thunder_forecast.get("_gap_offsets") or ())
        tomorrow_day = DailyForecast(
            thunder_hourly=tomorrow_thunder, has_data_gap=tomorrow_gap,
            # Issue #1475 Nachbesserung (Punkt 4c): `today` trug das Hagel-
            # Kennzeichen schon (s.o.), `tomorrow` blieb strukturell leer --
            # die im Dict vorhandene Information wurde nie gerendert.
            hail_flag=(
                thunder_forecast.get("+1", {}).get("hail")
                if thunder_forecast else None
            ),
        )
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
        # hängen. Seit #1450 entstehen Wintersport-Token (SD/SL/NS24+/AV/WC)
        # regulär wie jeder andere Metrik-Block -- ohne diesen Eintrag würden
        # sie bei vorhandenen Schneedaten erscheinen. _visible(spec_with_
        # enabled_false) -> False unterdrückt sie genau wie jede andere Metrik.
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
        # Bug #398: Risiko-Stunde in Ortszeit. Issue #1402: kein stiller
        # UTC-Rueckfall mehr -- der einzige Aufrufer (`format_sms`, s.o.)
        # setzt `self._tz` immer VOR diesem Aufruf; ein Direktaufruf ohne
        # `format_sms()` soll jetzt sichtbar mit AttributeError scheitern
        # statt lautlos in Weltzeit zu rendern.
        time_str = local_fmt(seg_data.segment.start_time, self._tz, "%Hh")
        return (label, time_str)
