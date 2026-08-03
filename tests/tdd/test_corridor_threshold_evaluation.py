"""Auswertung von Wertebereichen (`services.corridor_threshold`).

Nachfolger von `test_corridor_threshold_alert.py` (Issue #1444 S1/S2a), das
mit Issue #1460 (P1a) entfallen ist: Der Wertebereich (`corridors[].notify`)
ist seit **ADR-0043** kein Alarm-Ausloeser mehr -- die Empfindlichkeitsstufe
ist der einzige Regler. Alles, was dort den Versand, die Entprellung und den
`has_active_rules`-Gate des Schwellen-Alarms geprueft hat, ist damit
gegenstandslos und geloescht.

Der Auswertungs-Baustein selbst bleibt bestehen (`evaluate_corridor_thresholds()`,
`resolve_corridor_summary_field()`, `CorridorHit`) -- und mit ihm die
Zusicherungen, die hier weitergefuehrt werden:

* ein Treffer benennt Groesse, Ist-Wert, gerissene Grenze und Etappe,
* eine eingehaltene Grenze liefert keinen Treffer (der Grenzwert selbst gilt
  als eingehalten),
* die Metrik-Kennung loest ueber BEIDE Namensraeume auf (alter
  AlertMetric-Namensraum und Vergleichs-Katalog, #1455) -- die beiden bleiben
  kollisionsfrei,
* eine Aufzaehlung ohne Ordinalskala erzeugt keinen Falschtreffer und bricht
  den Lauf nicht ab,
* eine obere Grenze auf einer Groesse mit `cmp="unter"` (Nullgradgrenze)
  laeuft ohne ValueError durch.

Keine Mocks: echte Modelle, echter Auswertungsbaustein, kein Versand, kein Netz.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models import (
    Corridor,
    ForecastMeta,
    NormalizedTimeseries,
    GPXPoint,
    PrecipType,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)

LAT, LON = 47.0, 11.0


def _segment(segment_id: int | str = 1) -> TripSegment:
    now = datetime.now(timezone.utc)
    return TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=LAT, lon=LON, elevation_m=1000, distance_from_start_km=12.0),
        end_point=GPXPoint(lat=LAT + 0.1, lon=LON + 0.1, elevation_m=1500,
                           distance_from_start_km=18.0),
        start_time=now - timedelta(hours=1),
        end_time=now + timedelta(hours=3),
        duration_hours=4.0,
        distance_km=6.0,
        ascent_m=500,
        descent_m=0,
    )


def _data(segment_id: int | str = 1, **summary_kwargs) -> SegmentWeatherData:
    return SegmentWeatherData(
        segment=_segment(segment_id),
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
            data=[],
        ),
        aggregated=SegmentWeatherSummary(**summary_kwargs),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


def _hits(stand: list[SegmentWeatherData], korridore: list[Corridor]) -> list:
    from services.corridor_threshold import evaluate_corridor_thresholds

    return evaluate_corridor_thresholds(stand, korridore)


# ───────────────── Treffer benennt Groesse, Wert, Grenze, Etappe ─────────────

def test_treffer_traegt_groesse_istwert_grenze_und_etappe():
    """GIVEN ein Wetterstand ueber der eingestellten Regen-Grenze
    WHEN der Auswertungs-Baustein laeuft
    THEN liefert er einen Treffer mit Groesse, Ist-Wert, gerissener Grenze
    und Etappe."""
    treffer = _hits(
        [_data(1, precip_sum_mm=9.0)],
        [Corridor(metric="precipitation_sum", range=[None, 1], notify=True)],
    )

    assert len(treffer) == 1, f"Erwartet genau 1 Treffer, erhalten: {treffer!r}"
    hit = treffer[0]
    assert hit.metric == "precipitation_sum"
    assert hit.value == 9.0, f"Der Ist-Wert fehlt oder ist falsch: {hit!r}"
    assert hit.bound == 1, f"Die gerissene Grenze fehlt oder ist falsch: {hit!r}"
    assert str(hit.segment_id) == "1", f"Die Etappe fehlt: {hit!r}"


# ───────────────────── Eingehaltene Grenzen melden nicht ─────────────────────

def test_eingehaltene_grenze_liefert_keinen_treffer():
    """GIVEN alle eingestellten Grenzen sind eingehalten
    WHEN der Auswertungs-Baustein laeuft
    THEN entsteht kein Treffer."""
    treffer = _hits(
        [_data(1, precip_sum_mm=0.2, gust_max_kmh=15.0,
               thunder_level_max=ThunderLevel.NONE)],
        [
            Corridor(metric="precipitation_sum", range=[None, 1], notify=True),
            Corridor(metric="wind_gust", range=[None, 60], notify=True),
            Corridor(metric="thunder_level", range=[None, 0], notify=True),
        ],
    )

    assert treffer == [], f"Eingehaltene Grenzen duerfen nicht treffen: {treffer!r}"


def test_grenzwert_selbst_gilt_als_eingehalten():
    """GIVEN der Wert liegt exakt auf der eingestellten Grenze
    WHEN der Auswertungs-Baustein laeuft
    THEN gilt die Grenze als eingehalten (kein Treffer)."""
    treffer = _hits(
        [_data(1, precip_sum_mm=1.0)],
        [Corridor(metric="precipitation_sum", range=[None, 1], notify=True)],
    )

    assert treffer == [], (
        f"Der Grenzwert selbst zaehlt als eingehalten, erhalten: {treffer!r}"
    )


# ──────────────────────── Beide Metrik-Namensraeume ──────────────────────────

def test_katalog_namensraum_loest_bei_ordinaler_groesse_auf():
    """GIVEN ein Gewitter-Wertebereich unter der KATALOG-Kennung
    `thunder_level_max` (nicht der alten Kennung `thunder_level`)
    WHEN der Auswertungs-Baustein laeuft
    THEN wird die Groesse aufgeloest und die gerissene Grenze getroffen."""
    treffer = _hits(
        [_data(1, thunder_level_max=ThunderLevel.MED)],
        [Corridor(metric="thunder_level_max", range=[None, 0], notify=True)],
    )

    assert [h.metric for h in treffer] == ["thunder_level_max"], (
        f"Die Katalog-Kennung muss aufloesen, erhalten: {treffer!r}"
    )


def test_katalog_namensraum_loest_bei_stetiger_groesse_auf():
    """GIVEN derselbe Fall an einer STETIGEN Groesse (`precip_sum_mm` statt
    der alten Kennung `precipitation_sum`) -- damit der Nachweis nicht an der
    Ordinalwandlung des Gewitters haengt
    WHEN der Auswertungs-Baustein laeuft
    THEN wird die Groesse aufgeloest und die gerissene Grenze getroffen."""
    treffer = _hits(
        [_data(1, precip_sum_mm=9.0)],
        [Corridor(metric="precip_sum_mm", range=[None, 1], notify=True)],
    )

    assert [h.metric for h in treffer] == ["precip_sum_mm"], (
        f"Die Katalog-Kennung muss aufloesen, erhalten: {treffer!r}"
    )
    assert treffer[0].value == 9.0


def test_alte_kennungen_loesen_unveraendert_auf():
    """GIVEN Wertebereiche unter den ALTEN AlertMetric-Kennungen `snow_line`
    (mit OBERER Grenze) und `wind_gust`, beide gerissen
    WHEN der Auswertungs-Baustein laeuft
    THEN treffen beide unveraendert -- der Rueckfall auf den Katalog-
    Namensraum darf den bestehenden Weg weder ueberschreiben noch verschieben.
    """
    treffer = _hits(
        [_data(1, freezing_level_m=3200, gust_max_kmh=95.0)],
        [
            Corridor(metric="snow_line", range=[1500, 2500], notify=True),
            Corridor(metric="wind_gust", range=[None, 60], notify=True),
        ],
    )

    assert sorted(h.metric for h in treffer) == ["snow_line", "wind_gust"], (
        f"Beide alten Kennungen muessen treffen, erhalten: {treffer!r}"
    )


def test_obere_grenze_auf_der_nullgradgrenze_laeuft_ohne_fehler_durch():
    """GIVEN die OBERE Grenze der Nullgradgrenze ist gerissen (Hitzewelle) --
    beide Katalog-Kandidaten von `snow_line` tragen `cmp="unter"`, ein
    "ueber"-Treffer fand vor dem Fix keine cmp-Uebereinstimmung
    WHEN der Auswertungs-Baustein laeuft
    THEN entsteht ein Treffer in Richtung "above", statt dass der Lauf mit
    einer ValueError abbricht (F001 aus #1444 S1)."""
    treffer = _hits(
        [_data(1, freezing_level_m=3200.0)],
        [Corridor(metric="snow_line", range=[1500, 2500], notify=True)],
    )

    assert [h.metric for h in treffer] == ["snow_line"], (
        f"Die gerissene obere Grenze muss treffen, erhalten: {treffer!r}"
    )
    assert treffer[0].direction == "above", (
        f"Die Richtung muss 'above' sein, erhalten: {treffer[0]!r}"
    )
    assert treffer[0].bound == 2500


def test_nicht_alarmfaehige_groesse_mit_zahlenwert_trifft():
    """GIVEN ein Wertebereich auf der Schneehoehe (`snow_depth_cm`) -- eine
    Groesse, die das Register NICHT als alarmfaehig fuehrt und die im alten
    Namensraum gar nicht existiert -- und ein Wert ueber der Grenze
    WHEN der Auswertungs-Baustein laeuft
    THEN entsteht ein Treffer: massgeblich ist NICHT `alarm_capable` (die
    Frage des Aenderungs-Waechters), sondern ob je Etappe ein Zahlenwert
    vorliegt."""
    treffer = _hits(
        [_data(1, snow_depth_cm=80.0)],
        [Corridor(metric="snow_depth_cm", range=[None, 20], notify=True)],
    )

    assert [h.metric for h in treffer] == ["snow_depth_cm"], (
        f"Die Schneehoehe muss treffen, erhalten: {treffer!r}"
    )


# ─────────────── Aufzaehlung ohne Ordinalskala: kein Falschtreffer ───────────

def test_aufzaehlung_ohne_ordinalskala_erzeugt_keinen_falschtreffer():
    """GIVEN ZWEI Wertebereiche: einer auf der Niederschlagsart
    (`precip_type_dominant`, eine Aufzaehlung OHNE Ordinalskala, Bereich
    "mindestens 1") und daneben einer auf Gewitter, dessen Grenze gerissen ist
    WHEN der Auswertungs-Baustein laeuft
    THEN trifft nur das Gewitter -- der Lauf bricht nicht ab und die
    Niederschlagsart erzeugt keinen Treffer.

    Eine Auswertung, die die Enum-Erkennung nicht auf `ThunderLevel` verengt,
    wandelt `PrecipType.SNOW` ueber `thunder_ordinal()` still in die 0
    (gemessen: kein ValueError, sondern der Default-Rueckgabewert) -- 0 liegt
    unter 1, es entstuende ein Falschtreffer auf einer Groesse ohne
    Ordinalskala. Genau den faengt dieser Test."""
    treffer = _hits(
        [_data(1, precip_type_dominant=PrecipType.SNOW,
               thunder_level_max=ThunderLevel.MED)],
        [
            Corridor(metric="precip_type_dominant", range=[1, None], notify=True),
            Corridor(metric="thunder_level_max", range=[None, 0], notify=True),
        ],
    )

    assert [h.metric for h in treffer] == ["thunder_level_max"], (
        "Die Niederschlagsart darf keinen Treffer erzeugen (keine "
        "Ordinalskala), das Gewitter daneben schon -- erhalten: "
        f"{[(h.metric, h.value) for h in treffer]!r}"
    )


# ──────────────── Die beiden Namensraeume bleiben getrennt ───────────────────

def test_aenderungs_waechter_loest_katalog_kennungen_nicht_auf():
    """GIVEN Regeln des AENDERUNGS-Waechters mit einer Kennung, die es nur im
    Katalog-Namensraum gibt (`thunder_level_max`)
    WHEN die Aenderungs-Erkennung darueber laeuft (echter `detect_changes()`-
    Aufruf mit einem Sprung von "kein Gewitter" auf "hoch")
    THEN bleibt sie wirkungslos: der Rueckfall auf den Katalog-Namensraum
    gehoert allein in die Wertebereichs-Auswertung.

    Zusatz-Assert in derselben Funktion (kein eigenes Gate): die beiden
    Namensraeume sind kollisionsfrei. Bricht ein kuenftiger Katalog-Eintrag
    die Kollisionsfreiheit, schlaegt dieser Test an, statt das Verhalten still
    zu verschieben."""
    from app.models import AlertRule, AlertRuleKind, AlertSeverity
    from output.renderers.compare_metric_catalog import COMPARE_METRIC_CATALOG
    from services.weather_change_detection import (
        _ALERT_METRIC_TO_SUMMARY_FIELD,
        WeatherChangeDetectionService,
    )

    assert _ALERT_METRIC_TO_SUMMARY_FIELD.get("thunder_level_max") is None, (
        "Die Katalog-Kennung darf im Register des Aenderungs-Waechters NICHT "
        "auftauchen -- der Rueckfall gehoert allein in die Wertebereichs-Auswertung"
    )

    regeln = [
        AlertRule(
            id="r-abs", kind=AlertRuleKind.ABSOLUTE, metric="thunder_level_max",
            threshold=1.0, severity=AlertSeverity.WARNING, enabled=True,
        ),
        AlertRule(
            id="r-delta", kind=AlertRuleKind.DELTA, metric="thunder_level_max",
            threshold=0.5, severity=AlertSeverity.WARNING, enabled=True,
        ),
    ]
    svc = WeatherChangeDetectionService.from_alert_rules(regeln)
    changes = svc.detect_changes(
        _data(1, thunder_level_max=ThunderLevel.NONE),
        _data(1, thunder_level_max=ThunderLevel.HIGH),
    )

    assert changes == [], (
        "Der Aenderungs-Waechter darf Katalog-Kennungen weiterhin NICHT "
        f"aufloesen, erhalten: {changes!r}"
    )

    katalog_keys = {eintrag["key"] for eintrag in COMPARE_METRIC_CATALOG}
    alt_keys = {getattr(k, "value", k) for k in _ALERT_METRIC_TO_SUMMARY_FIELD}
    kollision = katalog_keys & alt_keys
    assert kollision == set(), (
        "Die beiden Metrik-Namensraeume muessen kollisionsfrei bleiben, "
        f"kollidierende Kennungen: {sorted(kollision)!r}"
    )
