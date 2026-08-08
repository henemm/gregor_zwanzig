"""SMS-Kurznachricht folgt der SMS-eigenen Metrikauswahl — #1575 Scheibe 3, AC-6.

Spec: docs/specs/modules/fix_1575_channel_metric_selection.md (Teil 1)
Kontext: docs/context/fix-1575-channel-metric-selection.md

Befund: ``TripReportFormatter.format_email()`` kollabiert ``dc.metrics`` in
Zeile 129-134 auf die **Email**-Auswahl (``get_metrics_for_channel("email",
...)``). Der SMS-Aufbau weiter unten (``_sms_thr`` Z. 282-286,
``active_metric_ids`` Z. 296) liest genau diese bereits kollabierte ``dc`` —
die SMS erbt dadurch strukturell die Email-Auswahl und kann nie eine eigene
haben, egal was unter ``per_channel_layouts["sms"]`` gespeichert ist.

Kern-Schicht (Test-Politik "Zwei Schichten", CLAUDE.md): kein Netz, kein
Versand, kein Mock/patch — echter Aufruf des Formatters mit praeparierten
``UnifiedWeatherDisplayConfig``-Objekten, Assertion auf den zusammengesetzten
SMS-Text (das tatsaechlich Zugestellte, s. src/output/channels/sms.py).

Die vier Faelle sind bewusst gemischt:
  * zwei ROT-Faelle (AC-6) — das Verhalten, das der Fix herstellen muss,
  * zwei GRUEN-Leitplanken — sie halten den Fix davon ab, den Fallback bzw.
    die global konfigurierten SMS-Schwellwerte zu zerstoeren, und belegen
    zugleich, dass die Assertion der ROT-Faelle ueberhaupt erfuellbar ist
    (Falsifizierbarkeit: ohne den Fallback-Fall waere unklar, ob die
    erwartete Symbolmenge vom Renderer je erzeugt werden KANN).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.models import (
    ForecastDataPoint, ForecastMeta, GPXPoint, MetricConfig,
    NormalizedTimeseries, Provider, SegmentWeatherData,
    SegmentWeatherSummary, ThunderLevel, TripSegment,
    UnifiedWeatherDisplayConfig,
)

TZ = ZoneInfo("Europe/Berlin")


# ---------------------------------------------------------------------------
# Fixture (Muster aus tests/unit/test_trip_empty_metric_selection.py)
# ---------------------------------------------------------------------------


def _build_segments() -> list[SegmentWeatherData]:
    tl = ThunderLevel.MED

    def _dp(h, temp, precip, gust, vis):
        return ForecastDataPoint(
            ts=datetime(2026, 7, 11, h, 0, tzinfo=timezone.utc),
            t2m_c=temp, wind10m_kmh=gust * 0.5, gust_kmh=gust,
            precip_1h_mm=precip, pop_pct=int(min(precip * 20, 100)),
            cloud_total_pct=60, thunder_level=tl,
            visibility_m=vis, freezing_level_m=2500,
        )

    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.13, lon=9.13, elevation_m=400.0),
        end_point=GPXPoint(lat=42.10, lon=9.18, elevation_m=1200.0),
        start_time=datetime(2026, 7, 11, 6, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc),
        duration_hours=4.0, distance_km=9.3, ascent_m=800.0, descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="demo", grid_res_km=1.3,
        run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
    )
    rows = [
        _dp(6, 12.0, 0.0, 10.0, 2000), _dp(7, 13.0, 1.0, 20.0, 1500),
        _dp(8, 14.0, 2.0, 30.0, 1200), _dp(9, 14.5, 0.5, 25.0, 1800),
    ]
    agg = SegmentWeatherSummary(
        temp_min_c=10.0, temp_max_c=14.5, temp_avg_c=12.0,
        wind_max_kmh=20.0, gust_max_kmh=30.0,
        precip_sum_mm=3.5, cloud_avg_pct=60, humidity_avg_pct=55,
        thunder_level_max=tl,
    )
    return [SegmentWeatherData(
        segment=seg, timeseries=NormalizedTimeseries(meta=meta, data=rows),
        aggregated=agg, fetched_at=datetime.now(timezone.utc), provider="demo",
    )]


def _render_sms(dc: UnifiedWeatherDisplayConfig, report_type: str = "morning") -> str:
    from output.renderers.trip_report import TripReportFormatter
    report = TripReportFormatter().format_email(
        segments=_build_segments(), trip_name="GR20 Test",
        report_type=report_type, display_config=dc, tz=TZ,
    )
    assert report.sms_text, "Fixture-Fehler: kein SMS-Text erzeugt"
    return report.sms_text


_TOKEN_SYMBOL = re.compile(r"^([A-Z]+\+?:?)")


def _sms_symbols(sms_text: str) -> set[str]:
    """Kuerzel der SMS-Token — 'K12' -> 'K', 'TH+:-' -> 'TH+:', 'W10@9(15@10)' -> 'W'.

    Bewusst KEIN ``in``-Test auf dem Rohtext: der Trip-Name ("GR20 Test")
    enthaelt selbst 'G' und 'R' und wuerde eine Symbol-Presence-Pruefung
    zufaellig gruen faerben.
    """
    body = sms_text.split(": ", 1)[1] if ": " in sms_text else sms_text
    out = set()
    for token in body.split():
        m = _TOKEN_SYMBOL.match(token)
        if m:
            out.add(m.group(1))
    return out


def _mc(metric_id: str, **kw) -> MetricConfig:
    return MetricConfig(metric_id=metric_id, enabled=True, **kw)


_GLOBAL_FIVE = ["temperature", "wind", "gust", "precipitation", "thunder"]


# ---------------------------------------------------------------------------
# AC-6 — ROT vor dem Fix
# ---------------------------------------------------------------------------


def test_sms_zeigt_nur_die_sms_eigene_auswahl():
    """AC-6: SMS-Layout {precipitation} -> ausschliesslich das Regen-Kuerzel.

    Heute erbt die SMS die (globale, ueber den Email-Zweig kollabierte)
    Auswahl und zeigt zusaetzlich K/D/W/G/TH.
    """
    dc = UnifiedWeatherDisplayConfig(
        trip_id="sms-eigene-auswahl",
        metrics=[_mc(m) for m in _GLOBAL_FIVE],
        per_channel_layouts={"sms": [_mc("precipitation")]},
    )
    sms = _render_sms(dc)
    assert _sms_symbols(sms) == {"R"}, (
        "AC-6 FAIL: die SMS-eigene Metrikauswahl (per_channel_layouts['sms'] = "
        f"['precipitation']) bleibt wirkungslos. SMS-Text: {sms!r}. Ursache: "
        "trip_report.py bildet active_metric_ids/_sms_thr aus der bereits "
        "email-kollabierten dc (Z. 129-134 vs. Z. 282-296) statt aus "
        "dc.get_metrics_for_channel('sms', report_type)."
    )


def test_sms_folgt_nicht_dem_email_layout():
    """AC-6: eigenes Email-Layout darf die SMS-Auswahl nicht ueberschreiben.

    Email = {temperature}, SMS = {wind, gust}. Heute zeigt die SMS 'K12 D14'
    (die Email-Auswahl) und kein einziges Wind-/Boeen-Kuerzel — der direkte
    Beweis, dass SMS die Email-Kaskade erbt statt der eigenen.
    """
    dc = UnifiedWeatherDisplayConfig(
        trip_id="email-vs-sms",
        metrics=[_mc(m) for m in _GLOBAL_FIVE],
        per_channel_layouts={
            "email": [_mc("temperature")],
            "sms": [_mc("wind"), _mc("gust")],
        },
    )
    sms = _render_sms(dc)
    symbols = _sms_symbols(sms)
    assert symbols == {"W", "G"}, (
        "AC-6 FAIL: die SMS zeigt nicht ihre eigene Auswahl {wind, gust}, "
        f"sondern die des Email-Kanals. SMS-Text: {sms!r}, Kuerzel: {sorted(symbols)}."
    )


# ---------------------------------------------------------------------------
# Leitplanken — heute GRUEN, muessen es nach dem Fix bleiben
# ---------------------------------------------------------------------------


def test_ohne_sms_layout_gilt_weiterhin_die_globale_auswahl():
    """Kaskadenebene 3 (Fallback) bleibt unveraendert.

    Zugleich der Falsifizierbarkeits-Beleg fuer die beiden ROT-Faelle: die
    Symbolmenge {'R'} IST vom Renderer erreichbar — die Assertion oben kann
    also grundsaetzlich erfuellt werden und scheitert nicht an der Fixture.
    """
    dc = UnifiedWeatherDisplayConfig(
        trip_id="kein-sms-layout", metrics=[_mc("precipitation")],
    )
    sms = _render_sms(dc)
    assert _sms_symbols(sms) == {"R"}, (
        "Leitplanke FAIL: ohne per_channel_layouts muss die SMS weiterhin der "
        f"globalen Auswahl folgen. SMS-Text: {sms!r}."
    )


def test_globaler_sms_schwellwert_wirkt_auch_bei_sms_eigener_auswahl():
    """AC-9-Leitplanke: ``sms_threshold`` bleibt eine GLOBALE Groesse.

    Die vom Editor geschriebenen Kanal-Layouts (``buildWeatherConfigMetrics``,
    metricsEditor.ts:332) fuehren KEIN ``sms_threshold``-Feld. Wird ``_sms_thr``
    im Fix naiv nur aus ``get_metrics_for_channel('sms', ...)`` gebildet, gehen
    die global konfigurierten Schwellwerte lautlos verloren und unterdrueckte
    Werte tauchen wieder auf ('W-' -> 'W10@9(15@10)'). Der Schwellwert muss
    weiterhin aus der globalen Metrikliste aufgeloest werden.
    """
    dc = UnifiedWeatherDisplayConfig(
        trip_id="globale-schwelle",
        metrics=[
            _mc("wind", sms_threshold=50.0),
            _mc("gust", sms_threshold=50.0),
            _mc("precipitation"),
        ],
        per_channel_layouts={
            "sms": [_mc("wind"), _mc("gust"), _mc("precipitation")],
        },
    )
    sms = _render_sms(dc)
    assert "W-" in sms.split() and "G-" in sms.split(), (
        "AC-9-Leitplanke FAIL: der global konfigurierte SMS-Schwellwert (50 km/h) "
        "unterdrueckt Wind/Boeen nicht mehr, sobald der SMS-Kanal eine eigene "
        f"Metrikliste hat. SMS-Text: {sms!r}."
    )
