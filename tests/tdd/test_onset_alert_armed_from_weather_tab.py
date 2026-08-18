"""Issue #1468 — Wird der Beginn-Alarm in der REALISTISCHEN Ausgangslage
ueberhaupt scharf?

SPEC: docs/specs/modules/feat_1468_onset_verschiebung_alarm.md
KONTEXT: docs/context/feat-1468-onset-verschiebung.md

WARUM DIESE DATEI ZUSAETZLICH ZU `test_onset_shift_alert.py` EXISTIERT:

Dort setzt JEDER Test die Empfindlichkeitsstufe der Beginn-Groesse selbst
(`expand_per_metric_levels({"thunder_onset": "standard"})`). In Produktion
tut das niemand: `metric_alert_levels` eines Trips enthaelt genau die
Groessen, die der Nutzer im Alarme-Reiter angefasst hat -- eine gerade erst
eingefuehrte Groesse steht dort NIE. Scharf wird sie ausschliesslich ueber
die Nachfuell-Regel in `expand_per_metric_levels()` (Issue #961,
"Aktivieren-Luecke"): die Schleife ueber `_ALERT_METRIC_TO_CATALOG_ID`, die
jede Wetter-Tab-aktive Groesse ohne eigenen Eintrag implizit auf "standard"
setzt.

Damit haengt die gesamte Wirksamkeit des Tickets an einem Pfad, den die
neun AC-Tests nicht beruehren. Bleibt er stumm -- weil `_fields_for()` fuer
die Beginn-Groessen nichts liefert und der Zweig
`if metric_fields and not remaining: continue` die Regel unterdrueckt, oder
weil `is_alert_metric_active()` sie nicht als aktiv fuehrt --, sind alle
zehn Tests dort gruen UND der Alarm in Produktion trotzdem tot. Genau das
verbietet die Invariante aus `rework_1467_s2_aenderungsalarm.md`: *"Der
gefaehrlichste Fehler ist der ausbleibende Alarm."*

PRUEFORT = WIRKORT. Der Test faehrt die echte Kette
`expand_per_metric_levels(levels, display_config)` ->
`WeatherChangeDetectionService.from_alert_rules()` -> `detect_changes()`.
Keine handgesetzte Regel-Liste, kein Mock (CLAUDE.md, Kern-Schicht).

Pfadregel #1409: der Prueling wird RELATIV ZU DIESER DATEI aufgeloest.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.models import (  # noqa: E402
    ForecastMeta, GPXPoint, MetricConfig, NormalizedTimeseries, Provider,
    SegmentWeatherData, SegmentWeatherSummary, TripSegment,
    UnifiedWeatherDisplayConfig,
)
from services.alert_preset import expand_per_metric_levels  # noqa: E402
from services.weather_change_detection import (  # noqa: E402
    WeatherChangeDetectionService,
)

TH_ONSET_FELD = "thunder_onset_utc"
RAIN_ONSET_FELD = "precip_heavy_onset_utc"
TH_ONSET_METRIK = "thunder_onset"
RAIN_ONSET_METRIK = "precipitation_heavy_onset"

TAG = date(2026, 8, 20)


def _utc(stunde: int) -> datetime:
    return datetime(TAG.year, TAG.month, TAG.day, stunde, 0)


def _wetter_reiter(**aktiv: bool) -> UnifiedWeatherDisplayConfig:
    """Ein ECHT konfigurierter Wetter-Reiter.

    Bewusst mit MEHREREN Eintraegen: ein leeres `metrics[]` gilt in
    `is_alert_metric_active()` als "nie konfiguriert" und damit konservativ
    als aktiv (Finding F002) -- der Test wuerde dann gruen, ohne dass die
    Aktivierung je geprueft waere. Erst ein gefuelltes `metrics[]` zwingt zur
    echten Einzelpruefung.
    """
    return UnifiedWeatherDisplayConfig(
        trip_id="onset-scharf",
        metrics=[
            MetricConfig(metric_id="temperature", enabled=True),
            MetricConfig(metric_id="wind", enabled=True),
            *[MetricConfig(metric_id=mid, enabled=an) for mid, an in aktiv.items()],
        ],
    )


def _segment(segment_id: int = 1) -> TripSegment:
    return TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=47.0, lon=12.0, elevation_m=1000.0,
                             distance_from_start_km=0.0),
        end_point=GPXPoint(lat=47.1, lon=12.1, elevation_m=1200.0,
                           distance_from_start_km=8.0),
        start_time=_utc(6).replace(tzinfo=timezone.utc),
        end_time=_utc(18).replace(tzinfo=timezone.utc),
        duration_hours=12.0, distance_km=8.0, ascent_m=500.0, descent_m=200.0,
    )


def _data(**summary) -> SegmentWeatherData:
    return SegmentWeatherData(
        segment=_segment(),
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test",
                              grid_res_km=1.0),
            data=[],
        ),
        aggregated=SegmentWeatherSummary(**summary),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _regel(regeln, metrik: str):
    return next((r for r in regeln if str(r.metric) == metrik), None)


# --------------------------------------------------------------------------
# Der Nachfuell-Pfad stellt die Beginn-Groessen scharf
# --------------------------------------------------------------------------

def test_aktiver_wetter_reiter_stellt_beide_beginn_groessen_ohne_eintrag_scharf():
    """Gewitter UND Niederschlag sind im Wetter-Reiter aktiv,
    `metric_alert_levels` enthaelt KEINEN Eintrag fuer die Beginn-Groessen.

    Erwartet: der Nachfuell-Pfad erzeugt fuer BEIDE eine Regel auf
    "standard" -- genau das, was in Produktion passiert, wenn ein Nutzer den
    Alarme-Reiter nach dem Rollout nie wieder anfasst.
    """
    dc = _wetter_reiter(thunder=True, precipitation=True)
    # Die Stufen-Groesse hat der Nutzer angefasst, die Beginn-Groesse nicht.
    regeln = expand_per_metric_levels({"thunder_level": "standard"}, dc)

    th = _regel(regeln, TH_ONSET_METRIK)
    rain = _regel(regeln, RAIN_ONSET_METRIK)
    assert th is not None, (
        "Der Gewitterbeginn wird nie scharf: der Nachfuell-Pfad "
        "(expand_per_metric_levels, Aktivieren-Luecke #961) erzeugt keine "
        f"Regel. Erzeugt wurden: {sorted(str(r.metric) for r in regeln)!r}"
    )
    assert rain is not None, (
        "Der Starkregenbeginn wird nie scharf. Erzeugt wurden: "
        f"{sorted(str(r.metric) for r in regeln)!r}"
    )
    for name, regel in ((TH_ONSET_METRIK, th), (RAIN_ONSET_METRIK, rain)):
        assert regel.enabled, f"{name}: Regel entsteht, ist aber nicht scharf."
        assert getattr(regel, "sensitivity_level", None) == "standard", (
            f"{name}: die nachgefuellte Regel traegt die Stufe nicht mit "
            f"({getattr(regel, 'sensitivity_level', '<fehlt>')!r}) -- ohne sie "
            "findet der Detektor kein Schwellenpaar und meldet nie."
        )


def test_nachgefuellte_regel_meldet_eine_echte_verschiebung():
    """Dieselbe Ausgangslage, aber bis zum Alarm durchgefahren.

    Eine Regel, die entsteht und trotzdem nichts ausloest, waere derselbe
    stille Ausfall -- die Existenzpruefung oben allein genuegt nicht.
    Verschiebung 17:00 -> 15:00 (2 h vorgezogen) liegt bei "standard" ueber
    der Schwelle "ab 1 h frueher".
    """
    dc = _wetter_reiter(thunder=True, precipitation=True)
    regeln = expand_per_metric_levels({"thunder_level": "standard"}, dc)
    detektor = WeatherChangeDetectionService.from_alert_rules(regeln)

    changes = detektor.detect_changes(
        _data(**{TH_ONSET_FELD: _utc(17), RAIN_ONSET_FELD: _utc(17)}),
        _data(**{TH_ONSET_FELD: _utc(15), RAIN_ONSET_FELD: _utc(15)}),
        include_absolute=False,
    )
    gemeldet = {c.metric for c in changes}
    assert TH_ONSET_FELD in gemeldet, (
        "Der Gewitterbeginn verschiebt sich um 2 h nach vorn und es entsteht "
        f"kein Alarm. Gemeldet wurde: {sorted(gemeldet)!r}"
    )
    assert RAIN_ONSET_FELD in gemeldet, (
        "Der Starkregenbeginn verschiebt sich um 2 h nach vorn und es "
        f"entsteht kein Alarm. Gemeldet wurde: {sorted(gemeldet)!r}"
    )


# --------------------------------------------------------------------------
# Gegenprobe: ohne aktive Register-Groesse bleibt der Beginn stumm
# --------------------------------------------------------------------------

def test_ohne_gewitter_im_wetter_reiter_entsteht_keine_beginn_regel():
    """Gewitter ist im Wetter-Reiter ABGEWAEHLT, Niederschlag bleibt aktiv.

    Erwartet: keine Gewitterbeginn-Regel und kein Gewitterbeginn-Alarm (die
    Aktivierungs-Kopplung aus den Known Limitations der Spec: wer Gewitter
    nicht beobachtet, will auch keinen Gewitterbeginn-Alarm). Der
    Starkregenbeginn bleibt als Positivkontrolle scharf -- ohne sie waere der
    Test auch dann gruen, wenn der Nachfuell-Pfad gar nichts mehr erzeugt.
    """
    dc = _wetter_reiter(thunder=False, precipitation=True)
    regeln = expand_per_metric_levels({}, dc)

    assert _regel(regeln, RAIN_ONSET_METRIK) is not None, (
        "Positivkontrolle: der Starkregenbeginn muss bei aktivem Niederschlag "
        f"scharf sein. Erzeugt wurden: {sorted(str(r.metric) for r in regeln)!r}"
    )
    assert _regel(regeln, TH_ONSET_METRIK) is None, (
        "Gewitter ist abgewaehlt, trotzdem entsteht eine Gewitterbeginn-Regel "
        f"-- die Aktivierungs-Kopplung greift nicht: "
        f"{sorted(str(r.metric) for r in regeln)!r}"
    )

    detektor = WeatherChangeDetectionService.from_alert_rules(regeln)
    changes = detektor.detect_changes(
        _data(**{TH_ONSET_FELD: _utc(17)}),
        _data(**{TH_ONSET_FELD: _utc(15)}),
        include_absolute=False,
    )
    assert not [c for c in changes if c.metric == TH_ONSET_FELD], (
        "Gewitter ist im Wetter-Reiter abgewaehlt, es entsteht trotzdem ein "
        f"Gewitterbeginn-Alarm: {changes!r}"
    )
