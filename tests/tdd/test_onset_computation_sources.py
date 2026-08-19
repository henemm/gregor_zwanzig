"""Issue #1468 — Die BERECHNUNG der beiden Beginn-Zeitpunkte, am Wirkort.

SPEC: docs/specs/modules/feat_1468_onset_verschiebung_alarm.md

WARUM DIESE DATEI EXISTIERT (Mutations-Befund, 2026-08-18):

Die neun AC-Tests in `test_onset_shift_alert.py` setzen `thunder_onset_utc`/
`precip_heavy_onset_utc` als fertigen Wert direkt ins Tages-Aggregat — sie
pruefen den VERGLEICH, nicht die HERKUNFT der Zahl. Nur AC-4 faehrt
`compute_basis_metrics()` wirklich durch, und der prueft ausschliesslich
Gewitter.

Die Mutations-Gegenprobe hat das sichtbar gemacht: das Entfernen der
`precip_1h_mm`-Ersatzquelle in `_compute_precip_heavy_onset()` liess JEDEN
Test gruen. Damit war die PO-freigegebene Ergaenzung (2026-08-18) unbewacht —
und ausgerechnet sie traegt die gesamte Starkregen-Haelfte des Tickets beim
PRIMAERPROVIDER: Open-Meteo setzt `precip_rate_mmph` hart auf `None`
(`providers/openmeteo.py:885`), nur GeoSphere befuellt es
(`providers/geosphere.py:571`). Ohne die Ersatzquelle waere
`precip_heavy_onset_utc` fuer die Mehrheit aller Segmente strukturell immer
`None` — kein Fehlalarm, aber auch NIE ein Alarm.

Dieselbe Luecke bestand fuer die Gewitter-Schwelle: AC-4 nennt 14:00 auch
dann noch richtig, wenn die Schwelle von `LOW` auf `MED` verschoben wuerde
(seine Tagesstunden tragen MED). Der Test unten setzt deshalb eine Stunde
mit LOW VOR die MED-Stunde.

Kein Mock (CLAUDE.md, Kern-Schicht): Gewitterstufen entstehen ueber die
ECHTE Fusion aus CAPE-Rohwerten, wie in `test_onset_shift_alert.py`.
Pfadregel #1409: Prueling relativ zu DIESER Datei aufgeloest.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.day_window import DAY_WINDOW_END_HOUR, DAY_WINDOW_START_HOUR  # noqa: E402
from app.model_registry import (  # noqa: E402
    cape_ladder_thresholds_jkg, lpi_thresholds_jkg,
)
from app.models import (  # noqa: E402
    ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider,
    ThunderLevel,
)
from providers.thunder_enrichment import _fuse_thunder_levels  # noqa: E402
from providers.thunder_routing import thunder_region_for  # noqa: E402
from services.weather_metrics import WeatherMetricsService  # noqa: E402

TAG = date(2026, 8, 20)
ALPEN_LAT, ALPEN_LON, MODELL = 47.0, 12.0, "icon_d2"
UTC = ZoneInfo("UTC")
FENSTER = (DAY_WINDOW_START_HOUR, DAY_WINDOW_END_HOUR)

# Die Schwelle aus der Spec, hier als LITERAL — bewusst NICHT aus dem
# Prueling gezogen (`WeatherMetricsService._PRECIP_HEAVY_MMPH`), sonst
# verschoebe eine Aenderung der Konstante die Erwartung stillschweigend mit.
STARKREGEN_MMPH = 4.0


def _reihe(punkte) -> NormalizedTimeseries:
    return NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.OPENMETEO, model="test",
                          grid_res_km=1.0),
        data=list(punkte),
    )


def _dp(stunde: int, *, cape=None, rate=None, regen_mm=0.0) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(TAG.year, TAG.month, TAG.day, stunde, 0, tzinfo=timezone.utc),
        t2m_c=18.0, wind10m_kmh=10.0, gust_kmh=20.0,
        precip_1h_mm=regen_mm, precip_rate_mmph=rate,
        cloud_total_pct=40, humidity_pct=50, pop_pct=30,
        cape_jkg=cape, convective_inhibition_jkg=5.0 if cape else None,
    )


def _aggregat(punkte):
    return WeatherMetricsService().compute_basis_metrics(
        _reihe(punkte), tz=UTC,
        day_window_start_hour=FENSTER[0], day_window_end_hour=FENSTER[1],
    )


def _stunde(wert) -> int | None:
    return None if wert is None else wert.hour


# ==========================================================================
# Starkregen: BEIDE Quellen gegen DIESELBE Schwelle
# ==========================================================================

def test_starkregen_beginn_ohne_intensitaetsfeld_kommt_aus_der_stundenmenge():
    """Open-Meteo-Fall: `precip_rate_mmph` ist durchgaengig None, die
    Stundenmenge `precip_1h_mm` traegt den Wert.

    Ohne die Ersatzquelle bliebe der Beginn hier `None` — und weil Open-Meteo
    der Primaerprovider ist, waere die Starkregen-Haelfte des Tickets fuer die
    Mehrheit aller Segmente tot.
    """
    punkte = [
        _dp(8, regen_mm=0.4),
        _dp(9, regen_mm=STARKREGEN_MMPH - 0.1),   # knapp darunter: zaehlt nicht
        _dp(10, regen_mm=STARKREGEN_MMPH),        # erste Stunde >= Schwelle
        _dp(11, regen_mm=9.0),                    # spaeterer Hoehepunkt
    ]
    for p in punkte:
        assert p.precip_rate_mmph is None, (
            "Fixture-Vorbedingung: dieser Fall bildet Open-Meteo ab, dort ist "
            f"precip_rate_mmph immer None (bekommen: {p.precip_rate_mmph!r})"
        )

    onset = _aggregat(punkte).precip_heavy_onset_utc
    assert _stunde(onset) == 10, (
        "Der Starkregen-Beginn wird ohne Intensitaetsfeld nicht erkannt "
        f"(erwartet 10:00, bekommen {onset!r}) -- die Ersatzquelle "
        "`precip_1h_mm` greift nicht."
    )


def test_starkregen_beginn_nutzt_das_intensitaetsfeld_wenn_es_gesetzt_ist():
    """GeoSphere-Fall: `precip_rate_mmph` ist gesetzt und gewinnt.

    Die Stundenmenge zeigt hier absichtlich in die ANDERE Richtung (frueh
    hoch, spaet niedrig). Waeren beide Quellen gleich, bewiese der Test
    nicht, WELCHE gelesen wird.
    """
    punkte = [
        _dp(8, rate=0.2, regen_mm=9.0),                    # Menge hoch, Rate niedrig
        _dp(9, rate=STARKREGEN_MMPH - 0.1, regen_mm=9.0),
        _dp(10, rate=STARKREGEN_MMPH, regen_mm=0.1),       # nur die Rate reisst
    ]
    onset = _aggregat(punkte).precip_heavy_onset_utc
    assert _stunde(onset) == 10, (
        "Bei gesetztem `precip_rate_mmph` muss die Intensitaet entscheiden "
        f"(erwartet 10:00, bekommen {onset!r}). 08:00 hiesse, die Stundenmenge "
        "gewinnt gegen die Rate."
    )


def test_regen_unterhalb_der_schwelle_ergibt_keinen_starkregen_beginn():
    """Vakuum-Schutz: ohne diese Gegenprobe waeren die beiden Tests oben auch
    dann gruen, wenn die Schwelle gar nicht geprueft wird und JEDE Regenstunde
    als Beginn zaehlt."""
    punkte = [_dp(h, regen_mm=STARKREGEN_MMPH - 0.1) for h in (8, 10, 12)]
    onset = _aggregat(punkte).precip_heavy_onset_utc
    assert onset is None, (
        f"Regen knapp unter {STARKREGEN_MMPH} mm/h ist kein Starkregen, "
        f"trotzdem entsteht ein Beginn: {onset!r}"
    )


# ==========================================================================
# Gewitter: die Schwelle ist die UNTERSTE Stufe, nicht die mittlere
# ==========================================================================

def _mit_stufen(punkte):
    region = thunder_region_for(ALPEN_LAT, ALPEN_LON)
    _fuse_thunder_levels(punkte, cape_ladder_thresholds_jkg(MODELL, region),
                         lpi_thresholds_jkg(region))
    return punkte


def test_gewitterbeginn_zaehlt_ab_der_untersten_stufe():
    """Ein leichtes Gewitter um 10:00, ein mittleres um 14:00.

    Erwartet: 10:00. Wuerde die Schwelle auf die mittlere Stufe rutschen,
    stuende hier 14:00 — und der Wanderer bekaeme einen Beginn genannt, der
    vier Stunden nach dem tatsaechlichen liegt.
    """
    punkte = _mit_stufen([
        _dp(8, cape=200.0), _dp(10, cape=400.0), _dp(14, cape=800.0),
    ])
    stufen = {p.ts.hour: p.thunder_level for p in punkte}
    assert stufen[10] == ThunderLevel.LOW, (
        f"Fixture-Vorbedingung: 10:00 muss die UNTERSTE Stufe tragen: {stufen[10]!r}"
    )
    assert stufen[14] not in (None, ThunderLevel.NONE, ThunderLevel.LOW), (
        f"Fixture-Vorbedingung: 14:00 muss hoeher liegen als 10:00: {stufen[14]!r}"
    )

    onset = _aggregat(punkte).thunder_onset_utc
    assert _stunde(onset) == 10, (
        f"Der Gewitterbeginn wird erst ab einer hoeheren Stufe gezaehlt "
        f"(erwartet 10:00, bekommen {onset!r})."
    )


def test_ohne_gewitter_entsteht_kein_gewitterbeginn():
    """Vakuum-Schutz zur Schwelle oben: eine Reihe ganz ohne Gewitter darf
    keinen Beginn liefern."""
    punkte = _mit_stufen([_dp(h, cape=50.0) for h in (8, 10, 14)])
    onset = _aggregat(punkte).thunder_onset_utc
    assert onset is None, (
        f"Ohne jedes Gewitter entsteht trotzdem ein Beginn: {onset!r}"
    )
