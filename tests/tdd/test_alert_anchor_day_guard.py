"""TDD RED — Issue #1661 Teil A + C: der Abweichungs-Alarm einer Tour vergleicht
gegen einen Anker vom FALSCHEN TAG, ohne es zu bemerken oder zu melden.

SPEC: docs/specs/modules/fix_1661_anker_vom_falschen_tag.md — AC-1..AC-6,
AC-11, AC-13..AC-15. (AC-7..AC-10: test_compare_anchor_target_date.py;
AC-12/AC-16 sind Go.)

Der Defekt in einem Satz: ``TripAlertService._get_cached_weather``
(``src/services/trip_alert.py:509``) gibt den undatierten Rueckfall-Anker
``svc.load(trip.id)`` UNGEPRUEFT zurueck — obwohl in der Datei steht, fuer
welchen Tag sie gilt (``target_date``). Am 08.08.2026 stammte sie vom Vortag;
die Wache der Tour „KHW 403" lief 16 h ins Leere (~28 stille Laeufe).

Kern-Schicht, deterministisch (kein Netz, kein Versand), mock-frei: echte
JSON-Dateien unter der pytest-isolierten ``get_data_dir()``-Basis (#1133),
echter ``TripAlertService``/``WeatherExtractor``, Transport ueber die
vorhandene ``mail_sink``-Naht. Log-Zusicherungen ueber ``caplog``, nie ueber
Dateiinhalt-String-Suche.
"""
from __future__ import annotations

import contextlib
import json
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.loader import get_data_dir, get_snapshots_dir, save_trip
from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    MetricConfig,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripReportConfig,
    TripSegment,
    UnifiedWeatherDisplayConfig,
)
from app.trip import Stage, Trip, Waypoint

from tests.helpers.alert_log_fixtures import LAT, LON, settings_email_only
from tests.helpers.briefing_zeiten import briefing_zeiten_fuer_trip

# Bewusst absurd hoch: das Delta gegen JEDE reale Vorhersage reisst damit die
# Boeen-Standardschwelle (20 km/h). Ob ein Alarm rausgeht, haengt so nur noch
# daran, OB der falsche Anker benutzt wird — nicht an Fixture-Zahlen.
ANKER_BOE_KMH = 200.0

# Diagnose-Gruende aus der Spec (Teil C).
GRUND_FALSCHER_TAG = "wrong_day"
GRUND_ZU_ALT = "too_old"
GRUND_FEHLT = "missing"


# ───────────────────────────── Fixtur-Bausteine ─────────────────────────────

def nutzer() -> str:
    return f"tdd-1661-{uuid.uuid4().hex[:8]}"


def _segment(segment_id: str) -> TripSegment:
    """Etappe, deren Ende in der ZUKUNFT liegt — ``_fetch_fresh_weather``
    (``trip_alert.py:1007``) ueberspringt absolvierte Segmente, ein Segment in
    der Vergangenheit machte den Lauf mangels Frisch-Daten stumm."""
    jetzt = datetime.now(timezone.utc)
    return TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=LAT, lon=LON, elevation_m=1000,
                             distance_from_start_km=0.0),
        end_point=GPXPoint(lat=LAT + 0.1, lon=LON + 0.1, elevation_m=1500,
                           distance_from_start_km=6.0),
        start_time=jetzt - timedelta(hours=1),
        end_time=jetzt + timedelta(hours=3),
        duration_hours=4.0, distance_km=6.0, ascent_m=500, descent_m=0,
    )


def _wetter(boe_kmh: float) -> SegmentWeatherData:
    """Segment MIT Stundenreihe — die braucht AC-6 (``drilldown()`` liest
    ausschliesslich ``timeseries``)."""
    stunde = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    punkte = [
        ForecastDataPoint(ts=stunde + timedelta(hours=h), t2m_c=12.0 + h,
                          wind10m_kmh=boe_kmh / 2, gust_kmh=boe_kmh,
                          precip_1h_mm=0.0)
        for h in range(4)
    ]
    return SegmentWeatherData(
        segment=_segment("1"),
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test",
                              grid_res_km=1.0),
            data=punkte,
        ),
        aggregated=SegmentWeatherSummary(
            gust_max_kmh=boe_kmh, wind_max_kmh=boe_kmh / 2,
            temp_max_c=15.0, temp_min_c=8.0, precip_sum_mm=0.0,
        ),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


def boeen_trip(trip_id: str, tage: list[date]) -> Trip:
    """Tour mit scharfer Boeen-Delta-Regel (Standard-Schwelle 20 km/h), Aufbau
    wie ``alert_log_fixtures.gust_alert_trip`` — nur mit frei waehlbaren
    Etappentagen (AC-13/AC-14 unterscheiden sich genau darin)."""
    stages = [
        Stage(id=f"T{i}", name=f"Tag {i}", date=tag,
              waypoints=[Waypoint(id=f"G{i}", name="Start", lat=LAT, lon=LON,
                                  elevation_m=1000.0)])
        for i, tag in enumerate(tage, start=1)
    ]
    trip = Trip(
        id=trip_id, name="Anker-Tour", stages=stages,
        official_warnings=None, corridors=[],
        display_config=UnifiedWeatherDisplayConfig(
            trip_id=trip_id,
            metrics=[MetricConfig(metric_id="gust", enabled=True)],
            metric_alert_levels={"wind_gust": "standard"},
        ),
    )
    # Issue #1594: Briefing-Zeiten ausserhalb des Vorlauf-Fensters — sonst
    # unterdrueckt die Sperre den Alarm aus einem zweiten Grund und diese
    # Datei misst nicht mehr den Anker. Vorbedingung, keine Zusicherung.
    morgen, abend = briefing_zeiten_fuer_trip(trip)
    trip.report_config = TripReportConfig(trip_id=trip_id, send_email=True,
                                          alert_on_changes=True,
                                          morning_time=morgen, evening_time=abend)
    trip.alert_cooldown_minutes = 0
    trip.official_alert_triggers_enabled = False
    return trip


def undatierten_anker_schreiben(
    user_id: str, trip_id: str, *, target_date: date | None,
    alter: timedelta = timedelta(hours=1),
) -> Path:
    """Legt ``weather_snapshots/{trip_id}.json`` an — den Rueckfall-Anker.

    Geschrieben ueber den ECHTEN ``WeatherSnapshotService.save()``; danach
    werden gezielt nur die beiden Felder gesetzt, um die es hier geht.
    ``target_date=None`` entfernt das Feld ganz (Absicherungsfall AC-3/AC-4:
    beschaedigte oder unvollstaendige Datei).
    """
    from services.weather_snapshot import WeatherSnapshotService

    WeatherSnapshotService(user_id=user_id).save(
        trip_id, [_wetter(ANKER_BOE_KMH)], date.today(),
    )
    pfad = get_snapshots_dir(user_id) / f"{trip_id}.json"
    daten = json.loads(pfad.read_text())
    if target_date is None:
        daten.pop("target_date", None)
    else:
        daten["target_date"] = target_date.isoformat()
    daten["snapshot_at"] = (datetime.now(timezone.utc) - alter).isoformat()
    pfad.write_text(json.dumps(daten, indent=2))
    return pfad


def diagnose_zeilen(user_id: str) -> list[dict]:
    """Die Diagnose-Spur ``diagnostics/alert_anchor_rejected.jsonl`` (Teil C).
    Leere Liste, wenn es sie nicht gibt — genau das ist heute der Zustand."""
    pfad = get_data_dir(user_id) / "diagnostics" / "alert_anchor_rejected.jsonl"
    if not pfad.exists():
        return []
    return [json.loads(z) for z in pfad.read_text(encoding="utf-8").splitlines() if z.strip()]


def warnungen_zu(caplog, trip_id: str) -> list[str]:
    return [r.getMessage() for r in caplog.records
            if r.levelno >= logging.WARNING and trip_id in r.getMessage()]


def throttle_abbild(user_id: str) -> str:
    """Roher Inhalt der Sperrzeit-Ablage (``throttle_state.json``)."""
    treffer = sorted(get_data_dir(user_id).glob("**/*throttle*.json"))
    return json.dumps({p.name: p.read_text() for p in treffer}, sort_keys=True)


def alarm_lauf(user_id: str) -> tuple[object, list[tuple[str, str]]]:
    """Ein vollstaendiger Alarm-Lauf ueber den ECHTEN Produktionspfad.

    ``check_all_trips()`` enthaelt das eigentliche Tor (``if not cached``, das
    seit der Spec-Korrektur 2026-08-10 NUR noch den Abweichungs-Alarm
    ueberspringt) — nur dieser Weg beweist die WIRKUNG des Verwerfens statt
    bloss den Rueckgabewert einer Methode.
    """
    from services.trip_alert import TripAlertService

    mails: list[tuple[str, str]] = []
    ergebnis = TripAlertService(
        settings=settings_email_only(), user_id=user_id,
        mail_sink=lambda subject, body: mails.append((subject, body)),
    ).check_all_trips()
    return ergebnis, mails


def cached_weather(user_id: str, trip: Trip):
    """Der Δ-Pfad — und nur der traegt die Tages-Pruefung (Spec-Korrektur 2026-08-10)."""
    from services.trip_alert import TripAlertService

    return TripAlertService(
        settings=settings_email_only(), user_id=user_id,
    )._get_cached_weather(trip, tagesgleicher_anker_noetig=True)


# ═════════════════════════════════ AC-1 ══════════════════════════════════════

def test_ac1_anker_vom_vortag_wird_verworfen_und_gemeldet(caplog):
    """AC-1 (Bug-Nachweis) — der gemessene Produktivfall vom 08.08.2026.

    GIVEN kein datierter Anker fuer heute und ein undatierter Rueckfall mit
    ``target_date`` von GESTERN
    WHEN der Abweichungs-Alarm-Lauf fuer diese Tour startet
    THEN wird der Anker verworfen (``None``) UND es erscheint eine WARNUNG mit
    Tour-Kennung und Grund „falscher Tag" statt eines stillen Durchlaufs.

    HEUTE ROT: ``trip_alert.py:509`` gibt ``svc.load()`` ungeprueft zurueck.
    """
    user_id, trip_id = nutzer(), "trip-1661-ac1"
    gestern = date.today() - timedelta(days=1)
    undatierten_anker_schreiben(user_id, trip_id, target_date=gestern)

    with caplog.at_level(logging.DEBUG):
        ergebnis = cached_weather(user_id, boeen_trip(trip_id, [date.today()]))

    assert ergebnis is None, (
        f"AC-1: Der Rueckfall-Anker traegt target_date={gestern.isoformat()} "
        "(gestern) und es gibt keinen datierten Anker fuer heute — er MUSS "
        f"verworfen werden. Zurueckgekommen sind {len(ergebnis or [])} "
        "Segmente: der Alarm vergleicht heutige Vorhersagen gegen einen "
        "Referenzwert von gestern (Produktivfall 08.08.2026)."
    )
    treffer = warnungen_zu(caplog, trip_id)
    assert any(GRUND_FALSCHER_TAG in m or "falscher tag" in m.lower() for m in treffer), (
        f"AC-1: Das Verwerfen muss SICHTBAR sein — WARNUNG mit Tour-Kennung "
        f"({trip_id}) und Grund '{GRUND_FALSCHER_TAG}'. Gefunden: {treffer}"
    )


def test_ac1_wirkung_kein_alarm_gegen_den_anker_von_gestern(caplog):
    """AC-1 (Wirkung am Tor, nicht am Rueckgabewert).

    GIVEN denselben Aufbau, mit einem Anker-Boeenwert von 200 km/h — das Delta
    gegen JEDE frische Vorhersage reisst die Schwelle von 20 km/h
    WHEN der vollstaendige Lauf ``check_all_trips()`` laeuft
    THEN geht KEIN Alarm raus; der Vergleich gegen den falschen Tag findet gar
    nicht erst statt.

    HEUTE ROT: der Anker von gestern wird benutzt und es wird zugestellt. Ein
    Fix, der nur den Rueckgabewert aendert, aber am Tor
    (``trip_alert.py:435-437``) vorbeigeht, faellt hier auf.
    """
    user_id, trip_id = nutzer(), "trip-1661-ac1-wirkung"
    undatierten_anker_schreiben(
        user_id, trip_id, target_date=date.today() - timedelta(days=1),
    )
    save_trip(boeen_trip(trip_id, [date.today()]), user_id=user_id)

    with caplog.at_level(logging.DEBUG):
        ergebnis, mails = alarm_lauf(user_id)

    assert not mails, (
        "AC-1: Aus dem Vergleich gegen einen Anker vom falschen Tag darf kein "
        f"Alarm entstehen. Zugestellt: {[s for s, _ in mails]}."
    )
    assert ergebnis.alerts_sent == 0, (
        f"AC-1: {ergebnis.alerts_sent} Alarm(e) versandt — der Lauf hat den "
        "Anker von gestern als gueltige Vergleichsbasis benutzt."
    )


# ═════════════════════════════════ AC-2 ══════════════════════════════════════

def test_ac2_regression_undatierter_anker_von_heute_bleibt_gueltig(caplog):
    """AC-2 (REGRESSIONSSCHUTZ — heute bereits korrektes Verhalten, GRUEN).

    GIVEN kein datierter Anker fuer heute und einen undatierten Rueckfall mit
    ``target_date = heute``
    WHEN der Alarm-Lauf startet
    THEN dient der Rueckfall weiterhin als Vergleichsbasis, ohne WARNUNG.

    Sichert gegen Verschlimmbesserung: der undatierte Rueckfall ist der
    REGULAERE Nachtpfad (``load_dated`` greift zwischen Mitternacht und dem
    ersten Tageslauf grundsaetzlich ins Leere), kein Ausnahmefall.
    """
    user_id, trip_id = nutzer(), "trip-1661-ac2"
    undatierten_anker_schreiben(user_id, trip_id, target_date=date.today())

    with caplog.at_level(logging.DEBUG):
        ergebnis = cached_weather(user_id, boeen_trip(trip_id, [date.today()]))

    assert ergebnis, (
        "AC-2: Ein Rueckfall mit target_date=heute ist gueltig und muss "
        "Vergleichsbasis bleiben — sonst verstummt der Alarm jede Nacht."
    )
    assert ergebnis[0].aggregated.gust_max_kmh == ANKER_BOE_KMH
    assert not warnungen_zu(caplog, trip_id), (
        f"AC-2: Ein gueltiger Anker darf keine WARNUNG erzeugen: "
        f"{warnungen_zu(caplog, trip_id)}"
    )


# ═════════════════════════════════ AC-3 ══════════════════════════════════════

def test_ac3_regression_fehlendes_datum_unter_26_stunden_bleibt_gueltig(caplog):
    """AC-3 (REGRESSIONSSCHUTZ — Altersnetz greift nicht zu frueh, GRUEN).

    GIVEN einen Rueckfall OHNE lesbares ``target_date`` (Absicherungsfall:
    beschaedigte/unvollstaendige Datei), ``snapshot_at`` = jetzt minus 10 h
    WHEN der Alarm-Lauf startet
    THEN wird der Rueckfall weiterhin verwendet.

    Bewacht, dass das neue Altersnetz Auffangnetz bleibt und nicht Fallbeil
    wird.
    """
    user_id, trip_id = nutzer(), "trip-1661-ac3"
    undatierten_anker_schreiben(user_id, trip_id, target_date=None,
                                alter=timedelta(hours=10))

    with caplog.at_level(logging.DEBUG):
        ergebnis = cached_weather(user_id, boeen_trip(trip_id, [date.today()]))

    assert ergebnis, (
        "AC-3: Ein Anker ohne lesbares target_date, aber juenger als 26 h, "
        "bleibt gueltig."
    )
    assert ergebnis[0].aggregated.gust_max_kmh == ANKER_BOE_KMH
    assert not warnungen_zu(caplog, trip_id)


# ═════════════════════════════════ AC-4 ══════════════════════════════════════

def test_ac4_fehlendes_datum_ueber_26_stunden_wird_verworfen(caplog):
    """AC-4 (Altersnetz verwirft ausserhalb der Grenze).

    GIVEN einen Rueckfall OHNE lesbares ``target_date`` UND ``snapshot_at`` =
    jetzt minus 27 h
    WHEN der Alarm-Lauf startet
    THEN wird er verworfen, es erscheint eine WARNUNG mit Grund „zu alt", und
    die Diagnose-Spur traegt eine Zeile mit ``reason="too_old"``.

    HEUTE ROT: auf der Trip-Seite gibt es ueberhaupt keine Altersprüfung. Im
    gemessenen Produktivbestand liegen Anker bis zu 57 Tage zurueck.
    """
    user_id, trip_id = nutzer(), "trip-1661-ac4"
    undatierten_anker_schreiben(user_id, trip_id, target_date=None,
                                alter=timedelta(hours=27))

    with caplog.at_level(logging.DEBUG):
        ergebnis = cached_weather(user_id, boeen_trip(trip_id, [date.today()]))

    assert ergebnis is None, (
        "AC-4: Ein Anker ohne target_date und aelter als 26 h taugt nicht mehr "
        f"als Vergleichsbasis (ADR-0009). Zurueck kamen {len(ergebnis or [])} "
        "Segmente."
    )
    treffer = warnungen_zu(caplog, trip_id)
    assert any(GRUND_ZU_ALT in m or "zu alt" in m.lower() for m in treffer), (
        f"AC-4: WARNUNG mit Tour-Kennung ({trip_id}) und Grund "
        f"'{GRUND_ZU_ALT}' erwartet. Gefunden: {treffer}"
    )
    gruende = [z.get("reason") for z in diagnose_zeilen(user_id)]
    assert GRUND_ZU_ALT in gruende, (
        f"AC-4: alert_anchor_rejected.jsonl braucht eine Zeile mit "
        f"reason='{GRUND_ZU_ALT}'. Gefundene Gruende: {gruende}"
    )


# ═════════════════════════════════ AC-5 ══════════════════════════════════════

def test_ac5_verworfener_anker_ruehrt_gedaechtnis_und_ankerdatei_nicht_an(caplog):
    """AC-5 (verworfener Anker ruehrt Melde-Gedaechtnis/Cooldown nie an).

    GIVEN einen Anker, der verworfen wird (Fall AC-1), und ein vorbelegtes
    Melde-Gedaechtnis
    WHEN der vollstaendige Alarm-Lauf diesen Fall durchlaeuft
    THEN bleiben ``alert_state`` und Cooldown exakt unveraendert UND die
    undatierte Anker-Datei wird NICHT neu geschrieben.

    HEUTE ROT: der Anker von gestern wird benutzt, der Alarm feuert und
    schreibt ``alert_state`` fort.

    Mutations-Gegenprobe (Lehre ``fix_1584c`` AC-7): schriebe der Fix beim
    Verwerfen den Anker neu oder setzte ``alert_state`` zurueck, MUSS dieser
    Test rot werden — sonst wird aus Unterdrueckung Dauerstille.
    """
    from services.alert_state import AlertStateService

    user_id, trip_id = nutzer(), "trip-1661-ac5"
    anker_pfad = undatierten_anker_schreiben(
        user_id, trip_id, target_date=date.today() - timedelta(days=1),
    )
    save_trip(boeen_trip(trip_id, [date.today()]), user_id=user_id)

    gedaechtnis = {"gust:1": {"last_reported_value": 42.0,
                              "reported_at": datetime.now(timezone.utc).isoformat()}}
    state_svc = AlertStateService(user_id=user_id)
    state_svc.save(trip_id, gedaechtnis)

    vorher_datei = anker_pfad.read_bytes()
    vorher_mtime = anker_pfad.stat().st_mtime_ns
    vorher_throttle = throttle_abbild(user_id)

    with caplog.at_level(logging.DEBUG):
        alarm_lauf(user_id)

    assert state_svc.load(trip_id) == gedaechtnis, (
        "AC-5: Ein verworfener Anker darf das Melde-Gedaechtnis NICHT "
        f"anfassen. Vorher: {gedaechtnis}, nachher: {state_svc.load(trip_id)}."
    )
    assert throttle_abbild(user_id) == vorher_throttle, (
        "AC-5: Ein verworfener Anker darf den Cooldown NICHT fortschreiben — "
        "sonst gilt die Aenderung als gemeldet und aus der zeitweiligen "
        "Unterdrueckung wird Dauerstille."
    )
    assert anker_pfad.read_bytes() == vorher_datei, (
        "AC-5: Der verworfene Anker darf NICHT neu geschrieben werden — der "
        "naechste regulaere Briefing-Lauf stellt ihn wieder her (ADR-0009)."
    )
    assert anker_pfad.stat().st_mtime_ns == vorher_mtime, (
        "AC-5: Die Anker-Datei wurde angefasst (Zeitstempel geaendert)."
    )


# ═════════════════════════════════ AC-6 ══════════════════════════════════════

def test_ac6_regression_anzeigepfad_zeigt_denselben_snapshot_weiterhin():
    """AC-6 (REGRESSIONSSCHUTZ — Anzeigepfade unangetastet, GRUEN).

    GIVEN denselben Snapshot wie AC-1 (``target_date`` = gestern), den der
    Alarm-Pfad soeben verworfen haette
    WHEN die Anzeigepfade der Kommandos ``/heute``/``/morgen``
    (``WeatherExtractor.timeline()``/``.drilldown()``) ihn lesen
    THEN zeigen sie ihn trotzdem an (``available=True``).

    Bewacht Entscheidung A1 der Spec: die Pruefung gehoert NICHT in
    ``WeatherSnapshotService.load()``, sonst wuerden diese beiden
    Anzeigepfade still mitverschaerft — sie sollen „was auch immer da ist"
    zeigen.
    """
    from services.weather_extractor import WeatherExtractor

    user_id, trip_id = nutzer(), "trip-1661-ac6"
    undatierten_anker_schreiben(
        user_id, trip_id, target_date=date.today() - timedelta(days=1),
    )

    extractor = WeatherExtractor(user_id=user_id)
    timeline = extractor.timeline(trip_id)
    drilldown = extractor.drilldown(trip_id, "gust_kmh")

    assert timeline.available and timeline.points, (
        "AC-6: /heute (timeline) muss den vorhandenen Snapshot weiterhin "
        f"zeigen. available={timeline.available}, message={timeline.message!r}"
    )
    assert drilldown.available and drilldown.points, (
        "AC-6: /morgen (drilldown) muss den vorhandenen Snapshot weiterhin "
        f"zeigen. available={drilldown.available}, message={drilldown.message!r}"
    )


# ════════════════════════════════ AC-11 ══════════════════════════════════════

def test_ac11_verworfener_anker_erzeugt_diagnose_eintrag():
    """AC-11 (Teil C — verworfener Anker wird sichtbar).

    GIVEN ein Anker wird verworfen (Fall „falscher Tag", AC-1)
    WHEN das passiert
    THEN entsteht in ``diagnostics/alert_anchor_rejected.jsonl`` eine Zeile mit
    ``ts``, Tour-Kennung und Grund — nicht nur eine Logzeile, die im
    Dauerrauschen untergeht (R5: ein Signal ohne Leser versandet).

    HEUTE ROT: ``record_alert_anchor_rejected`` gibt es noch nicht.

    Die Go-Haelfte von AC-11 (``analyzeAlertAnchorRejections``,
    ``recentCount >= 1``) wird mit AC-12/AC-16 neben dem Go-Code geprueft.
    """
    user_id, trip_id = nutzer(), "trip-1661-ac11"
    undatierten_anker_schreiben(
        user_id, trip_id, target_date=date.today() - timedelta(days=1),
    )

    cached_weather(user_id, boeen_trip(trip_id, [date.today()]))

    zeilen = diagnose_zeilen(user_id)
    assert zeilen, (
        "AC-11: Der verworfene Anker muss eine Zeile in "
        "diagnostics/alert_anchor_rejected.jsonl erzeugen — sonst bleibt der "
        "Ausfall so unsichtbar wie am 08.08.2026 (16 h, ~28 stille Laeufe)."
    )
    eintrag = zeilen[-1]
    assert datetime.fromisoformat(str(eintrag.get("ts"))), (
        f"AC-11: Die Diagnose-Zeile braucht einen lesbaren ts: {eintrag}"
    )
    assert eintrag.get("reason") == GRUND_FALSCHER_TAG, (
        f"AC-11: reason='{GRUND_FALSCHER_TAG}' erwartet, gefunden: {eintrag}"
    )
    assert eintrag.get("entity_id") == trip_id, (
        f"AC-11: entity_id='{trip_id}' erwartet, gefunden: {eintrag}"
    )


# ════════════════════════════════ AC-13 ══════════════════════════════════════

def test_ac13_laufende_tour_ohne_jeden_anker_eskaliert(caplog):
    """AC-13 (Teil C — laufende Tour ohne jeden Anker eskaliert).

    GIVEN eine Tour mit ``start_date <= heute <= end_date``, aber weder
    datierter noch undatierter Anker-Datei
    WHEN der Alarm-Lauf sie prueft
    THEN ist das ein Eskalationsfall: WARNUNG UND Diagnose-Eintrag mit
    ``reason="missing"`` — nicht nur eine leise Logzeile.

    HEUTE ROT: es passiert gar nichts. Eine laufende Tour ohne jedes Briefing
    bliebe komplett unsichtbar blind.
    """
    user_id, trip_id = nutzer(), "trip-1661-ac13"
    trip = boeen_trip(trip_id, [date.today() - timedelta(days=1), date.today(),
                                date.today() + timedelta(days=1)])
    assert trip.start_date <= date.today() <= trip.end_date, "Fixtur-Schutz"

    with caplog.at_level(logging.DEBUG):
        ergebnis = cached_weather(user_id, trip)

    assert ergebnis is None, "Fixtur-Schutz: es darf gar kein Anker da sein."
    treffer = warnungen_zu(caplog, trip_id)
    assert treffer, (
        "AC-13: Eine LAUFENDE Tour ohne jeden Anker muss eine WARNUNG mit "
        f"Tour-Kennung ({trip_id}) erzeugen — die Wache ist dort komplett "
        "blind, und genau das soll auffallen."
    )
    gruende = [z.get("reason") for z in diagnose_zeilen(user_id)]
    assert GRUND_FEHLT in gruende, (
        f"AC-13: Diagnose-Zeile mit reason='{GRUND_FEHLT}' erwartet. "
        f"Gefunden: {gruende}"
    )


# ════════════════════════════════ AC-14 ══════════════════════════════════════

def test_ac14_noch_nicht_gestartete_tour_ohne_anker_bleibt_leise(caplog):
    """AC-14 (Teil C — noch nicht gestartete Tour ist der harmlose Normalfall).

    GIVEN eine Tour mit ``start_date > heute`` und weder datierter noch
    undatierter Anker-Datei
    WHEN der Alarm-Lauf sie prueft
    THEN erscheint NUR eine sichtbare Logzeile (DEBUG-Ebene) — KEIN
    Diagnose-Eintrag, keine Eskalation.

    HEUTE ROT: ``trip_alert`` protokolliert in diesem Zweig gar nichts (die
    einzige DEBUG-Zeile dort haengt am ``except``-Pfad). Geprueft ueber
    ``caplog``, nicht ueber Dateiinhalt-String-Suche.

    Scheitert bei zu aggressiver Eskalation: ohne diese Unterscheidung wuerde
    JEDE noch nicht gestartete Tour taeglich Dauerrauschen erzeugen (#1199).
    """
    user_id, trip_id = nutzer(), "trip-1661-ac14"
    trip = boeen_trip(trip_id, [date.today() + timedelta(days=2)])
    assert trip.start_date > date.today(), "Fixtur-Schutz"

    with caplog.at_level(logging.DEBUG):
        ergebnis = cached_weather(user_id, trip)

    assert ergebnis is None, "Fixtur-Schutz: es darf gar kein Anker da sein."
    assert not diagnose_zeilen(user_id), (
        "AC-14: Eine noch nicht gestartete Tour ohne Anker ist der harmlose "
        "Normalfall und darf KEINEN Diagnose-Eintrag erzeugen."
    )
    eigene = [r.getMessage() for r in caplog.records if r.name == "trip_alert"]
    assert [m for m in eigene if trip_id in m], (
        "AC-14: Der Fall muss trotzdem SICHTBAR sein — eine Logzeile des "
        f"trip_alert-Loggers mit der Tour-Kennung ({trip_id}). Alle "
        f"trip_alert-Zeilen: {eigene}"
    )
    assert not warnungen_zu(caplog, trip_id), (
        f"AC-14: ...aber KEINE WARNUNG: {warnungen_zu(caplog, trip_id)}"
    )


# ════════════════════════════════ AC-15 ══════════════════════════════════════

def test_ac15_diagnose_schreiber_scheitert_alarm_lauf_bricht_nicht_ab(caplog):
    """AC-15 (Teil C — Diagnose-Schreiber ist fail-soft).

    GIVEN der Diagnose-Schreiber kann nicht schreiben, weil an der Stelle des
    ``diagnostics``-Verzeichnisses eine DATEI liegt (``mkdir(exist_ok=True)``
    wirft darauf ``FileExistsError`` — ein echter, deterministischer OSError
    ohne Rechte-Gebastel und ohne Mock)
    WHEN gleichzeitig ein Anker verworfen wird (Fall AC-1)
    THEN bricht der Alarm-Lauf NICHT zusaetzlich ab: Rueckgabe ``None``,
    WARNUNG mit Grund „falscher Tag" — nur der Diagnose-Eintrag fehlt.

    HEUTE ROT: der Anker wird gar nicht erst verworfen.

    Die WARNUNG ist hier die eigentliche Zusicherung: ``_get_cached_weather``
    faengt heute JEDE Ausnahme und gibt ``None`` zurueck — ein durchgereichter
    Schreibfehler saehe von aussen aus wie korrektes Verwerfen. Nur die
    Warnung beweist, dass der Verwerfen-Pfad zu Ende gelaufen ist.
    """
    user_id, trip_id = nutzer(), "trip-1661-ac15"
    undatierten_anker_schreiben(
        user_id, trip_id, target_date=date.today() - timedelta(days=1),
    )
    sperre = get_data_dir(user_id) / "diagnostics"
    sperre.parent.mkdir(parents=True, exist_ok=True)
    sperre.write_text("kein Verzeichnis, sondern eine Datei")

    with caplog.at_level(logging.DEBUG):
        ergebnis = cached_weather(user_id, boeen_trip(trip_id, [date.today()]))

    assert ergebnis is None, (
        "AC-15: Auch mit defektem Diagnose-Schreiber muss der Anker vom "
        "falschen Tag verworfen werden."
    )
    treffer = warnungen_zu(caplog, trip_id)
    assert any(GRUND_FALSCHER_TAG in m or "falscher tag" in m.lower() for m in treffer), (
        "AC-15: Der Verwerfen-Pfad muss trotz Schreibfehler zu Ende laufen — "
        f"die WARNUNG mit Grund '{GRUND_FALSCHER_TAG}' fehlt. Gefunden: {treffer}"
    )
    assert sperre.is_file(), "Fixtur-Schutz: die Sperre muss eine Datei bleiben."


# ══════════════ Grenze des Altersnetzes (Korrekturrunde 2026-08-10) ══════════
#
# AC-3 misst 10 h, AC-4 misst 27 h — JEDER Wert dazwischen besteht beide. Eine
# Mutation der Konstante auf 20 h liess die ganze Datei gruen: die Zahl 26 war
# ueberhaupt nicht bewacht, nur ihre grobe Groessenordnung (dieselbe Luecke wie
# #1629 Adversary-Finding F002). Die beiden Tests unten klemmen die Grenze mit
# literalen Werten ein, Vorbild `fix_1584c` AC-6a/AC-6b.

def test_altersnetz_grenze_25h50_wird_noch_verwendet(caplog):
    """Grenze 26 h, UNTERE Seite — 25 h 50 min alt, kein ``target_date``.

    GIVEN einen Rueckfall ohne lesbares ``target_date``, 10 Minuten VOR der
    26-Stunden-Grenze
    WHEN der Abweichungs-Alarm-Lauf startet
    THEN wird er noch verwendet — die Grenze liegt nicht frueher.

    Faellt, sobald jemand die Grenze senkt (z.B. auf 20 h).
    """
    user_id, trip_id = nutzer(), "trip-1661-grenze-unter"
    undatierten_anker_schreiben(user_id, trip_id, target_date=None,
                                alter=timedelta(hours=25, minutes=50))

    with caplog.at_level(logging.DEBUG):
        ergebnis = cached_weather(user_id, boeen_trip(trip_id, [date.today()]))

    assert ergebnis, (
        "Ein Anker ohne target_date, 25 h 50 min alt, liegt INNERHALB der "
        "26-Stunden-Grenze und muss weiterhin als Vergleichsbasis dienen. "
        "Er wurde verworfen — die Grenze wurde gesenkt."
    )
    assert ergebnis[0].aggregated.gust_max_kmh == ANKER_BOE_KMH
    assert not warnungen_zu(caplog, trip_id), (
        f"Innerhalb der Grenze darf keine WARNUNG stehen: {warnungen_zu(caplog, trip_id)}"
    )


def test_altersnetz_grenze_26h10_wird_verworfen(caplog):
    """Grenze 26 h, OBERE Seite — 26 h 10 min alt, kein ``target_date``.

    GIVEN denselben Aufbau, 10 Minuten NACH der 26-Stunden-Grenze
    WHEN der Abweichungs-Alarm-Lauf startet
    THEN wird der Anker verworfen, mit Grund „zu alt".

    Faellt, sobald jemand die Grenze anhebt. Zusammen mit dem Test darueber ist
    die Zahl 26 damit beidseitig eingeklemmt.
    """
    user_id, trip_id = nutzer(), "trip-1661-grenze-ueber"
    undatierten_anker_schreiben(user_id, trip_id, target_date=None,
                                alter=timedelta(hours=26, minutes=10))

    with caplog.at_level(logging.DEBUG):
        ergebnis = cached_weather(user_id, boeen_trip(trip_id, [date.today()]))

    assert ergebnis is None, (
        "Ein Anker ohne target_date, 26 h 10 min alt, liegt AUSSERHALB der "
        f"26-Stunden-Grenze und muss verworfen werden. Zurueck kamen "
        f"{len(ergebnis or [])} Segmente — die Grenze wurde angehoben."
    )
    gruende = [z.get("reason") for z in diagnose_zeilen(user_id)]
    assert gruende == [GRUND_ZU_ALT], (
        f"Genau eine Diagnose-Zeile mit reason='{GRUND_ZU_ALT}' erwartet, "
        f"gefunden: {gruende}"
    )


# ═══════ Abgelaufene Tour im Meldepfad (Korrekturrunde 2026-08-10) ═══════════

def test_abgelaufene_tour_ohne_anker_bleibt_leise(caplog):
    """AC-14-Schwester: eine ABGELAUFENE Tour ohne Anker eskaliert nicht.

    GIVEN eine Tour, deren Laufzeitraum vorbei ist (``end_date < heute``), und
    weder datierte noch undatierte Anker-Datei
    WHEN der Alarm-Lauf sie prueft
    THEN bleibt es leise: KEIN Diagnose-Eintrag, KEINE WARNUNG — nur die
    sichtbare Logzeile.

    AC-14 bewacht bisher nur die eine Seite (``start_date > heute``). Ein
    verdrehter Vergleich in ``_report_missing_anchor`` (z.B. ``today <=
    end_date`` zu ``today <= start_date``) bliebe sonst unbemerkt und wuerde
    jede laengst beendete Tour zur Dauer-Eskalation machen.
    """
    user_id, trip_id = nutzer(), "trip-1661-abgelaufen"
    trip = boeen_trip(trip_id, [date.today() - timedelta(days=5),
                                date.today() - timedelta(days=4)])
    assert trip.end_date < date.today(), "Fixtur-Schutz: die Tour muss vorbei sein."

    with caplog.at_level(logging.DEBUG):
        ergebnis = cached_weather(user_id, trip)

    assert ergebnis is None, "Fixtur-Schutz: es darf gar kein Anker da sein."
    assert not diagnose_zeilen(user_id), (
        "Eine abgelaufene Tour ohne Anker ist genauso harmlos wie eine noch "
        "nicht gestartete (es laeuft dort schlicht keine Wache mehr) und darf "
        f"KEINEN Diagnose-Eintrag erzeugen: {diagnose_zeilen(user_id)}"
    )
    assert not warnungen_zu(caplog, trip_id), (
        f"...und KEINE WARNUNG: {warnungen_zu(caplog, trip_id)}"
    )
    eigene = [r.getMessage() for r in caplog.records if r.name == "trip_alert"]
    assert [m for m in eigene if trip_id in m], (
        f"...aber sichtbar bleiben muss der Fall trotzdem. Zeilen: {eigene}"
    )


# ════ Die Pruefung gilt NUR dem Δ-Pfad (Spec-Korrektur 2026-08-10) ═══════════

class _FesteAmtlicheQuelle:
    """Echte Quelle (kein Mock), zustaendig fuer den Fixtur-Punkt."""

    def __init__(self, alert) -> None:
        self._alert = alert

    @property
    def name(self) -> str:
        return "tdd-1661-amtlich"

    def covers(self, lat: float, lon: float) -> bool:
        return abs(lat - LAT) < 0.2 and abs(lon - LON) < 0.2

    def fetch(self, lat: float, lon: float):
        return [self._alert]


def test_verworfener_delta_anker_schaltet_amtliche_warnung_NICHT_stumm(caplog):
    """Spec-Korrektur 2026-08-10 — gemessen am Wirkort ``check_all_trips()``.

    GIVEN eine Tour mit amtlichem Trigger und einem Rueckfall-Anker vom
    FALSCHEN TAG (genau die Lage einer bereits gebrieften, aber noch nicht
    gestarteten Tour: ihr undatierter Anker traegt den Starttag)
    WHEN der vollstaendige Alarm-Lauf laeuft
    THEN geht die amtliche Warnung trotzdem raus — verworfen wird NUR der
    Abweichungs-Vergleich.

    Bewacht beides zusammen: den Parameter ``tagesgleicher_anker_noetig=False``
    am amtlichen Pfad UND die Reihenfolge in ``check_all_trips`` (stuende das
    Tor ``if not cached`` wieder VOR dem amtlichen Check, wuerde ein Anker vom
    falschen Tag auch die Unwetterwarnung verschlucken — genau in den Tagen vor
    dem Aufbruch, in denen sie am meisten zaehlt).
    """
    import services.official_alerts.base as basis
    from services.official_alerts import OfficialAlert, register_official_alert_source

    user_id, trip_id = nutzer(), "trip-1661-amtlich"
    undatierten_anker_schreiben(
        user_id, trip_id, target_date=date.today() + timedelta(days=1),
    )
    trip = boeen_trip(trip_id, [date.today()])
    trip.official_alert_triggers_enabled = True
    save_trip(trip, user_id=user_id)

    jetzt = datetime.now(timezone.utc)
    sicherung = list(basis._REGISTERED_SOURCES)
    basis._REGISTERED_SOURCES.clear()
    try:
        register_official_alert_source(_FesteAmtlicheQuelle(OfficialAlert(
            source="tdd-1661", hazard="thunderstorm", level=3,
            label="Gewitterwarnung (#1661)", region_label="Testregion",
            valid_from=jetzt - timedelta(hours=1),
            valid_to=jetzt + timedelta(hours=6),
        )))
        with caplog.at_level(logging.DEBUG):
            ergebnis, mails = alarm_lauf(user_id)
    finally:
        basis._REGISTERED_SOURCES.clear()
        basis._REGISTERED_SOURCES.extend(sicherung)

    assert mails, (
        "Der Δ-Anker traegt den falschen Tag und wird zu Recht verworfen — die "
        "AMTLICHE Warnung muss trotzdem zugestellt werden. Es ging nichts raus: "
        "die Tages-Pruefung wirkt faelschlich auch auf den amtlichen Pfad."
    )
    assert ergebnis.alerts_sent == 1, (
        f"Genau ein Versand erwartet (der amtliche), gezaehlt: {ergebnis.alerts_sent}"
    )
    assert any(GRUND_FALSCHER_TAG in z.get("reason", "") for z in diagnose_zeilen(user_id)), (
        "Fixtur-Schutz: der Δ-Anker MUSS in diesem Lauf wegen falschen Tages "
        f"verworfen worden sein, sonst prueft der Test nichts. Diagnose: "
        f"{diagnose_zeilen(user_id)}"
    )


# ═════════ Issue #1699: Anker OHNE BRIEFING (Abfrage-Anker) ══════════════════
#
# SPEC: docs/specs/modules/fix_1699_anker_ohne_briefing.md — AC-1..AC-4, AC-6,
# AC-7. Eine reine Abfrage (``glance`` u.a.) schreibt bei fehlendem Anker einen
# Snapshot direkt ueber ``save()`` (``trip_command_processor.py:308``) — vorbei
# am geteilten Baustein ``write_anchor_and_reset_memory()``, der bei On-Demand
# aussteigt (#1007). Der Anker traegt ``target_date = heute`` und besteht die
# #1661-Pruefung: der Vergleichspunkt wird nicht verschoben, sondern ERFUNDEN.

GRUND_OHNE_BRIEFING = "not_briefing_backed"

_ENTFERNEN = object()


def abfrage_trip(trip_id: str) -> Trip:
    """Wie ``boeen_trip`` (heute + morgen), aber mit ZWEI Wegpunkten je Etappe:
    unter zwei Wegpunkten liefert ``convert_trip_to_segments`` GAR KEINE
    Segmente (``trip_segments.py:121-123``), die Abfrage schriebe dann keinen
    Snapshot. Vorbedingung, keine Zusicherung."""
    trip = boeen_trip(trip_id, [date.today(), date.today() + timedelta(days=1)])
    for stage in trip.stages:
        stage.waypoints.append(Waypoint(id=f"{stage.id}-Z", name="Ziel",
                                        lat=LAT + 0.1, lon=LON + 0.1,
                                        elevation_m=1500.0))
    return trip


def abfrage_glance(user_id: str, trip: Trip):
    """``### query: glance`` durch den ECHTEN Inbound-Pfad: TripCommandProcessor
    -> ``_handle_query`` -> ``_fetch_and_save_snapshot`` -> ``_fetch_weather``
    auf dem Offline-``FixtureProvider`` (autouse-Fixture, #346). Genau dieser
    Weg schreibt den Anker, um den es geht — kein Mock, kein Netz."""
    from services.trip_command_processor import InboundMessage, TripCommandProcessor

    return TripCommandProcessor().process(InboundMessage(
        channel="telegram", trip_name=trip.name, body="### query: glance",
        sender="tdd-1699", received_at=datetime.now(timezone.utc),
        user_id=user_id,
    ))


def anker_pfad(user_id: str, trip_id: str) -> Path:
    return get_snapshots_dir(user_id) / f"{trip_id}.json"


def herkunft_setzen(pfad: Path, wert) -> None:
    """Setzt bzw. entfernt (``_ENTFERNEN``) ``briefing_backed`` in einer bereits
    ueber ``save()`` geschriebenen Anker-Datei — Bauart wie das Nachziehen von
    ``target_date`` in ``undatierten_anker_schreiben``."""
    daten = json.loads(pfad.read_text())
    if wert is _ENTFERNEN:
        daten.pop("briefing_backed", None)
    else:
        daten["briefing_backed"] = wert
    pfad.write_text(json.dumps(daten, indent=2))


def geometrie_weather(user_id: str, trip: Trip):
    """Der AMTLICHE Pfad — ``tagesgleicher_anker_noetig=False``, ``:630-632``."""
    from services.trip_alert import TripAlertService

    return TripAlertService(
        settings=settings_email_only(), user_id=user_id,
    )._get_cached_weather(trip, tagesgleicher_anker_noetig=False)


def test_ac1_abfrage_anker_ohne_briefing_ist_keine_vergleichsbasis(caplog):
    """AC-1 (Bug-Nachweis am echten Abfrage-Pfad).

    GIVEN eine Tour ohne jeden Snapshot (es lief nie ein Briefing) / WHEN der
    Nutzer ``/glance`` sendet und danach der Abweichungs-Alarm laeuft / THEN
    wird der dabei entstandene Anker verworfen (``None``), sichtbar als WARNUNG.
    Vor dem Fix gruen durchgelaufen: er traegt ``target_date = heute`` und
    besteht die #1661-Pruefung anstandslos.

    Positivkontrolle im selben Test: derselbe Snapshot wird ueber den AMTLICHEN
    Pfad sehr wohl geliefert — sonst koennte das ``None`` auch von einer leeren
    oder korrupten Datei kommen.
    """
    from services.trip_day import trip_local_today
    from services.weather_snapshot import WeatherSnapshotService

    user_id, trip_id = nutzer(), "trip-1699-ac1"
    trip = abfrage_trip(trip_id)
    save_trip(trip, user_id=user_id)
    pfad = anker_pfad(user_id, trip_id)
    assert not pfad.exists(), "Vorbedingung: es darf noch kein Anker da sein."

    antwort = abfrage_glance(user_id, trip)

    assert pfad.exists(), f"Fixtur-Schutz: die Abfrage MUSS schreiben. {antwort!r}"
    heute = trip_local_today(trip, datetime.now(timezone.utc))
    assert WeatherSnapshotService(user_id=user_id).load_target_date(trip_id) == heute, (
        "Fixtur-Schutz: der Abfrage-Anker traegt den HEUTIGEN Tag und besteht "
        "die #1661-Pruefung — nur so misst dieser Test die HERKUNFT."
    )
    assert geometrie_weather(user_id, trip), (
        "Positivkontrolle: fuer die Geometrie ist derselbe Snapshot einwandfrei."
    )

    with caplog.at_level(logging.DEBUG):
        ergebnis = cached_weather(user_id, trip)

    assert ergebnis is None, (
        "AC-1: Der Snapshot stammt aus einer reinen ABFRAGE, nicht aus einem "
        f"Briefing — keine Vergleichsbasis. Zurueck kamen {len(ergebnis or [])} "
        "Segmente: ab jetzt gilt der Abfragezeitpunkt als Normalzustand."
    )
    treffer = warnungen_zu(caplog, trip_id)
    assert any(GRUND_OHNE_BRIEFING in m or "briefing" in m.lower() for m in treffer), (
        f"AC-1: WARNUNG mit Tour-Kennung ({trip_id}) und Grund "
        f"'{GRUND_OHNE_BRIEFING}' erwartet. Gefunden: {treffer}"
    )


def test_ac1_wirkung_kein_abweichungsalarm_gegen_anker_ohne_briefing():
    """AC-1 (Wirkung am Tor ``check_all_trips()``, nicht am Rueckgabewert).

    GIVEN einen Anker ``target_date = heute``, Boeen 200 km/h, NICHT
    briefing-gestuetzt / WHEN der vollstaendige Alarm-Lauf laeuft / THEN geht
    KEIN Abweichungsalarm raus. Vor dem Fix ging einer raus — das
    Herkunftsmerkmal wurde nicht ausgewertet.

    Bewusst der deterministische Anker-Schreiber statt der echten Abfrage: die
    schreibt REALE Fixture-Werte, gegen die der frische Abruf kein Delta ergibt
    — der Test waere trivial gruen. Positivkontrolle ist ``test_ac4_...``:
    identischer Aufbau, einziger Unterschied ist die Herkunft, dort geht ein
    Alarm raus.
    """
    user_id, trip_id = nutzer(), "trip-1699-ac1-wirkung"
    pfad = undatierten_anker_schreiben(user_id, trip_id, target_date=date.today())
    herkunft_setzen(pfad, False)
    save_trip(boeen_trip(trip_id, [date.today()]), user_id=user_id)

    ergebnis, mails = alarm_lauf(user_id)

    assert not mails and ergebnis.alerts_sent == 0, (
        "AC-1: Aus einem Anker ohne zugrundeliegendes Briefing darf kein "
        f"Abweichungsalarm entstehen. Zugestellt: {[s for s, _ in mails]}."
    )


def test_ac2_diagnose_nennt_anker_ohne_briefing_beim_namen():
    """AC-2 (Teil C — der vierte Ablehnungsgrund).

    GIVEN die Lage aus AC-1 / WHEN der Abweichungs-Alarm laeuft / THEN traegt
    ``diagnostics/alert_anchor_rejected.jsonl`` eine Zeile mit
    ``reason="not_briefing_backed"`` — nicht ``missing`` (es gibt einen Anker),
    nicht ``wrong_day`` (sein Datum stimmt). Vor dem Fix gab es den Grund
    nicht und es wurde gar nichts protokolliert. Ohne ihn sind „es gab nie einen
    Anker" und „ein Anker wurde verworfen" von aussen nicht unterscheidbar.
    """
    user_id, trip_id = nutzer(), "trip-1699-ac2"
    trip = abfrage_trip(trip_id)
    save_trip(trip, user_id=user_id)
    abfrage_glance(user_id, trip)
    assert not diagnose_zeilen(user_id), "Vorbedingung: noch keine Diagnose-Zeile."

    cached_weather(user_id, trip)

    zeilen = diagnose_zeilen(user_id)
    assert zeilen, "AC-2: Der verworfene Abfrage-Anker braucht eine Diagnose-Zeile."
    eintrag = zeilen[-1]
    assert eintrag.get("reason") == GRUND_OHNE_BRIEFING, (
        f"AC-2: reason='{GRUND_OHNE_BRIEFING}' erwartet (nicht "
        f"'{GRUND_FEHLT}', nicht '{GRUND_FALSCHER_TAG}'). Gefunden: {eintrag}"
    )
    assert eintrag.get("entity_id") == trip_id, f"AC-2: falsche Kennung: {eintrag}"
    assert datetime.fromisoformat(str(eintrag.get("ts"))), f"AC-2: ts: {eintrag}"


def _amtlicher_lauf_mit_anker_ohne_briefing(user_id: str, trip_id: str):
    """Aufbau fuer AC-3: amtliche Warnung + Anker OHNE Briefing, ``target_date
    = heute`` (damit die #1661-Pruefung als Ursache ausscheidet)."""
    import services.official_alerts.base as basis
    from services.official_alerts import OfficialAlert, register_official_alert_source

    herkunft_setzen(
        undatierten_anker_schreiben(user_id, trip_id, target_date=date.today()), False,
    )
    trip = boeen_trip(trip_id, [date.today()])
    trip.official_alert_triggers_enabled = True
    save_trip(trip, user_id=user_id)

    jetzt = datetime.now(timezone.utc)
    sicherung = list(basis._REGISTERED_SOURCES)
    basis._REGISTERED_SOURCES.clear()
    try:
        register_official_alert_source(_FesteAmtlicheQuelle(OfficialAlert(
            source="tdd-1699", hazard="thunderstorm", level=3,
            label="Gewitterwarnung (#1699)", region_label="Testregion",
            valid_from=jetzt - timedelta(hours=1),
            valid_to=jetzt + timedelta(hours=6),
        )))
        return alarm_lauf(user_id)
    finally:
        basis._REGISTERED_SOURCES.clear()
        basis._REGISTERED_SOURCES.extend(sicherung)


def test_ac3_amtliche_warnung_geht_trotz_anker_ohne_briefing_raus():
    """AC-3 (ZENTRALE NICHT-REGRESSION — heute schon korrekt, GRUEN).

    GIVEN eine Tour mit amtlichem Trigger, deren einziger Anker NICHT
    briefing-gestuetzt ist / WHEN der volle Alarm-Lauf laeuft / THEN geht die
    amtliche Warnung raus: fuer sie zaehlt nur die GEOMETRIE, und die ist bei
    einem Abfrage-Anker einwandfrei (``trip_alert.py:630-632``).

    Mutations-Gegenprobe (nachgestellt und bestaetigt): sitzt die neue
    Herkunftspruefung VOR Zeile 630 statt danach, liefert der amtliche
    Aufrufer ``None``, findet keine Geometrie und verstummt — dieser Test wird
    dann rot. Verstummende amtliche Warnungen sind die von #1701 verbotene
    Gegenrichtung.
    """
    user_id, trip_id = nutzer(), "trip-1699-ac3"

    ergebnis, mails = _amtlicher_lauf_mit_anker_ohne_briefing(user_id, trip_id)

    assert mails and ergebnis.alerts_sent == 1, (
        "AC-3: Der Δ-Anker ist nicht briefing-gestuetzt und wird zu Recht "
        "verworfen — die AMTLICHE Warnung muss trotzdem zugestellt werden "
        f"(genau 1 Versand). Gezaehlt: {ergebnis.alerts_sent}."
    )


def test_ac3_amtliche_warnung_ueberlebt_auch_die_stufe_2_weiche():
    """AC-3 (Stufe-2-Variante — Fix-Loop F001).

    Der Waechter darueber laesst die #1916-Stufe 2 GAR NICHT durchlaufen: ohne
    vorbestehenden rollierenden Anker liefert ``load_alarm_anchor()`` ``None``,
    die Kette springt direkt auf Stufe 3, und eine faelschlich an den amtlichen
    Ausstieg von Stufe 2 (``trip_alert.py:667-669``) gehaengte Herkunftspruefung
    bleibt unbemerkt.

    GIVEN eine Tour mit amtlichem Trigger, einem GUELTIGEN rollierenden Anker
    von heute (Stufe 2 greift) und einem undatierten Rueckfall mit
    ``briefing_backed=False`` / WHEN der amtliche Pfad die Geometrie holt /
    THEN liefert er sie — die amtliche Warnung wird ausgeloest.

    Gemessen am ``check_official_alert_triggers()``-Ergebnis statt am
    Mail-Versand: bei gueltiger Stufe 2 feuert der Abweichungsalarm ohnehin und
    buendelt die Warnung mit ein — „es kam Post" unterschiede die Quellen nicht.
    """
    import services.official_alerts.base as basis
    from services.official_alerts import OfficialAlert, register_official_alert_source
    from services.trip_alert import TripAlertService
    from services.weather_snapshot import WeatherSnapshotService

    user_id, trip_id = nutzer(), "trip-1699-ac3-stufe2"
    herkunft_setzen(
        undatierten_anker_schreiben(user_id, trip_id, target_date=date.today()), False,
    )
    trip = boeen_trip(trip_id, [date.today()])
    trip.official_alert_triggers_enabled = True
    save_trip(trip, user_id=user_id)
    svc = WeatherSnapshotService(user_id=user_id)
    svc.save_alarm_anchor(trip_id, date.today(), [_wetter(ANKER_BOE_KMH)], "email")

    assert svc.alarm_anchor_target_date(trip_id, "email") == date.today(), (
        "Fixtur-Schutz: nur ein TAGESGLEICHER rollierender Anker laesst die "
        "Kette ueberhaupt in die Stufe-2-Weiche laufen."
    )
    assert svc.load_briefing_backed(trip_id) is False, (
        "Fixtur-Schutz: der undatierte Rueckfall muss nicht briefing-gestuetzt "
        "sein, sonst haette eine Herkunftspruefung nirgends etwas zu verwerfen."
    )

    jetzt = datetime.now(timezone.utc)
    sicherung = list(basis._REGISTERED_SOURCES)
    basis._REGISTERED_SOURCES.clear()
    try:
        register_official_alert_source(_FesteAmtlicheQuelle(OfficialAlert(
            source="tdd-1699", hazard="thunderstorm", level=3,
            label="Gewitterwarnung (#1699 Stufe 2)", region_label="Testregion",
            valid_from=jetzt - timedelta(hours=1),
            valid_to=jetzt + timedelta(hours=6),
        )))
        meldungen = TripAlertService(
            settings=settings_email_only(), user_id=user_id,
        ).check_official_alert_triggers(trip)
    finally:
        basis._REGISTERED_SOURCES.clear()
        basis._REGISTERED_SOURCES.extend(sicherung)

    assert meldungen, (
        "AC-3: Fuer amtliche Warnungen zaehlt allein die GEOMETRIE — die "
        "liefert bei gueltigem rollierendem Anker die Stufe 2. Eine dort "
        "angehaengte Herkunftspruefung wuerde jede Tour mit rollierendem Anker "
        "UND Abfrage-Rueckfall verstummen lassen (#1701)."
    )


def test_ac3_kopplung_der_anker_ohne_briefing_wurde_in_diesem_lauf_verworfen():
    """AC-3 (Kopplung — der Waechter oben misst die Lage, die er zu messen
    behauptet).

    GIVEN denselben Aufbau / WHEN derselbe Lauf laeuft / THEN steht in der
    Diagnose eine Zeile ``not_briefing_backed``. Vor dem Fix rot — deshalb
    getrennt vom Waechter oben, der schon vorher gruen war. Ohne diese
    Zusicherung bliebe der auch dann gruen, wenn der Anker im Δ-Pfad gar nicht
    faellt.
    """
    user_id, trip_id = nutzer(), "trip-1699-ac3-kopplung"

    _amtlicher_lauf_mit_anker_ohne_briefing(user_id, trip_id)

    gruende = [z.get("reason") for z in diagnose_zeilen(user_id)]
    assert GRUND_OHNE_BRIEFING in gruende, (
        f"AC-3: Der Δ-Anker MUSS wegen fehlenden Briefings verworfen worden "
        f"sein. Gefundene Gruende: {gruende}"
    )


def test_ac4_briefing_anker_bleibt_gueltig_und_alarmiert(caplog):
    """AC-4 (REGRESSIONSSCHUTZ + Positivkontrolle zu AC-1, GRUEN).

    GIVEN einen regulaer geschriebenen Anker (``save()`` ohne Herkunftsangabe),
    ``target_date = heute``, Boeen 200 km/h / WHEN der Alarm laeuft / THEN
    bleibt er Vergleichsbasis, ein Alarm geht raus, keine Diagnose-Zeile.

    Doppelrolle: Waechter gegen die Fehlerrichtung „zu streng" (ein Fix, der
    jeden undatierten Anker verwirft, faellt hier auf) UND Positivkontrolle zu
    ``test_ac1_wirkung_...``, ohne die dessen „kein Alarm" nichts bewiese.
    """
    user_id, trip_id = nutzer(), "trip-1699-ac4"
    undatierten_anker_schreiben(user_id, trip_id, target_date=date.today())
    trip = boeen_trip(trip_id, [date.today()])
    save_trip(trip, user_id=user_id)

    with caplog.at_level(logging.DEBUG):
        segmente = cached_weather(user_id, trip)
        ergebnis, mails = alarm_lauf(user_id)

    assert segmente and segmente[0].aggregated.gust_max_kmh == ANKER_BOE_KMH, (
        "AC-4: Ein regulaer geschriebener Anker bleibt Vergleichsbasis."
    )
    assert mails and ergebnis.alerts_sent == 1, (
        "AC-4: Gegen einen briefing-gestuetzten Anker MUSS der Abweichungsalarm "
        f"weiter feuern. Versandt: {ergebnis.alerts_sent}."
    )
    assert not diagnose_zeilen(user_id), (
        f"AC-4: gueltiger Anker, keine Diagnose-Zeile: {diagnose_zeilen(user_id)}"
    )


def test_ac5_altbestand_ohne_herkunftsfeld_bleibt_gueltiger_anker(caplog):
    """AC-5 (Altbestand-Auslegung am WIRKORT, GRUEN).

    GIVEN eine vor dem Deploy geschriebene Anker-Datei OHNE das Feld
    ``briefing_backed``, ``target_date = heute`` / WHEN der Alarm laeuft / THEN
    gilt sie als briefing-gestuetzt: normaler Betrieb, keine Diagnose-Zeile,
    keine WARNUNG.

    Freigegebene PO-Auslegung: fehlendes Feld heisst „briefing-gestuetzt", nicht
    „unbekannt" — die strenge Gegenauslegung verwuerfe beim ersten Lauf nach dem
    Deploy JEDEN legitim geschriebenen Altanker. Lesemethoden-Teil von AC-5:
    ``tests/integration/test_weather_snapshot.py``.
    """
    user_id, trip_id = nutzer(), "trip-1699-ac5"
    pfad = undatierten_anker_schreiben(user_id, trip_id, target_date=date.today())
    herkunft_setzen(pfad, _ENTFERNEN)
    assert "briefing_backed" not in json.loads(pfad.read_text()), "Fixtur-Schutz"

    with caplog.at_level(logging.DEBUG):
        segmente = cached_weather(user_id, boeen_trip(trip_id, [date.today()]))

    assert segmente and segmente[0].aggregated.gust_max_kmh == ANKER_BOE_KMH, (
        f"AC-5: Altbestand OHNE Herkunftsfeld gilt als briefing-gestuetzt. "
        f"Zurueck kamen {len(segmente or [])} Segmente."
    )
    assert not diagnose_zeilen(user_id) and not warnungen_zu(caplog, trip_id), (
        f"AC-5: Altbestand darf weder Diagnose-Zeile noch WARNUNG erzeugen: "
        f"{diagnose_zeilen(user_id)} / {warnungen_zu(caplog, trip_id)}"
    )


def test_ac6_anzeigepfade_nach_abfrage_ohne_briefing_bleiben_vollstaendig():
    """AC-6 (REGRESSIONSSCHUTZ — Anzeige und Ankerwirkung sind getrennt, GRUEN).

    GIVEN eine Tour ohne jeden Snapshot / WHEN der Nutzer ``/glance`` sendet /
    THEN antwortet das Kommando mit Daten UND ``WeatherExtractor.timeline()``
    zeigt denselben Snapshot (``available=True``) — obwohl der Alarm ihn
    verwirft. Bewacht die Trennung: die Herkunftspruefung gehoert in den
    Alarm-Pfad, NICHT in ``load()`` und nicht in den Schreibpfad der Abfrage —
    ohne den Fetch antworteten ``glance`` & Co. ohne Briefing gar nicht mehr.
    """
    from services.weather_extractor import WeatherExtractor

    user_id, trip_id = nutzer(), "trip-1699-ac6"
    trip = abfrage_trip(trip_id)
    save_trip(trip, user_id=user_id)

    antwort = abfrage_glance(user_id, trip)

    assert antwort.success and antwort.confirmation_body.strip(), (
        f"AC-6: Die Abfrage muss weiterhin antworten: {antwort!r}"
    )
    timeline = WeatherExtractor(user_id=user_id).timeline(trip_id)
    assert timeline.available and timeline.points, (
        f"AC-6: Der Anzeigepfad muss den Snapshot zeigen. "
        f"available={timeline.available}, message={timeline.message!r}"
    )


def test_ac7_regulaeres_briefing_heilt_den_abfrage_anker(caplog):
    """AC-7 (Selbstheilung).

    GIVEN einen durch eine Abfrage entstandenen, NICHT briefing-gestuetzten
    Anker / WHEN danach ein regulaeres Briefing ihn neu schreibt — derselbe
    Aufruf wie in ``trip_report_scheduler.py:1509`` (``_write_briefing_anchor``:
    ``save(trip.id, segment_weather, target_date)``, ohne Herkunftsangabe) /
    THEN ist der Anker wieder gueltig und es entsteht KEINE neue Diagnose-Zeile.

    Vor dem Fix fiel schon der Fixtur-Schutz — die Abfrage schrieb kein
    Herkunftsmerkmal, es gab nichts zu heilen. Ohne diesen Test bliebe
    unbewacht, ob die Unterdrueckung endet (Lehre ``fix_1584c`` AC-7:
    aus zeitweiliger Stille wuerde Dauerstille).
    """
    from services.weather_snapshot import WeatherSnapshotService

    user_id, trip_id = nutzer(), "trip-1699-ac7"
    trip = abfrage_trip(trip_id)
    save_trip(trip, user_id=user_id)
    abfrage_glance(user_id, trip)

    roh = json.loads(anker_pfad(user_id, trip_id).read_text())
    assert roh.get("briefing_backed") is False, (
        "Fixtur-Schutz: die Abfrage MUSS den Anker als nicht briefing-gestuetzt "
        f"markieren, sonst gibt es nichts zu heilen. Felder: {sorted(roh)}"
    )
    vorher = len(diagnose_zeilen(user_id))

    WeatherSnapshotService(user_id=user_id).save(
        trip_id, [_wetter(ANKER_BOE_KMH)], date.today(),
    )

    with caplog.at_level(logging.DEBUG):
        segmente = cached_weather(user_id, trip)

    assert segmente, "AC-7: Nach dem Briefing ist der Anker wieder gueltig."
    assert len(diagnose_zeilen(user_id)) == vorher, (
        f"AC-7: keine neue Diagnose-Zeile: {diagnose_zeilen(user_id)[vorher:]}"
    )


# ───────── AC-10: Naht zu #1916 (rollierender Alarm-Anker, ADR-0056) ─────────
#
# Ordnungs-Zusicherung ohne eigenen Codepfad: faellt die Basis in Stufe 3 wegen
# ``not_briefing_backed``, ist ``cached`` in ``check_all_trips()`` falsy —
# ``check_and_send_alerts()`` laeuft nicht an, also koennen auch die beiden
# #1916-Schreibtrigger nicht laufen. Aufbau mit dem deterministischen
# Anker-Schreiber (200 km/h) statt der echten Abfrage: nur so ergaebe die
# verworfene Basis ueberhaupt ein Delta, das Trigger (a) ausloesen WUERDE.
def rollierender_anker_pfad(user_id: str, trip_id: str) -> Path:
    return get_snapshots_dir(user_id) / f"{trip_id}_alarm_anchor_email.json"


def _ac10_lauf(user_id: str, trip_id: str, *, herkunft):
    """Tour, deren EINZIGE Basis der undatierte Anker ist (kein datierter, kein
    rollierender) — ``herkunft=False`` macht sie zum Abfrage-Anker."""
    herkunft_setzen(
        undatierten_anker_schreiben(user_id, trip_id, target_date=date.today()),
        herkunft,
    )
    save_trip(boeen_trip(trip_id, [date.today()]), user_id=user_id)
    return alarm_lauf(user_id)


def test_ac10_positivkontrolle_gueltige_basis_schreibt_rollierenden_anker():
    """AC-10 (POSITIVKONTROLLE): GIVEN denselben Aufbau mit GUELTIGER Basis /
    WHEN ``check_all_trips()`` laeuft / THEN geht ein Alarm raus UND Trigger (a)
    legt den rollierenden Anker an. Ohne sie bewiese das „nichts entstanden"
    im Test darunter nichts."""
    user_id, trip_id = nutzer(), "trip-1699-ac10-positiv"

    ergebnis, mails = _ac10_lauf(user_id, trip_id, herkunft=True)

    assert mails and ergebnis.alerts_sent == 1, (
        f"Positivkontrolle: gegen eine gueltige Basis MUSS ein Alarm rausgehen, "
        f"sonst kann Trigger (a) nie feuern. Versandt: {ergebnis.alerts_sent}."
    )
    assert rollierender_anker_pfad(user_id, trip_id).exists(), (
        "Positivkontrolle: der versendete Alarm MUSS den rollierenden Anker "
        "schreiben (#1916 Trigger (a)) — sonst misst der Test darunter nichts."
    )


def test_ac10_verworfene_basis_erzeugt_keinen_rollierenden_alarm_anker():
    """AC-10 (Naht zu #1916): GIVEN eine Tour, deren einzige Vergleichsbasis in
    Stufe 3 wegen ``not_briefing_backed`` faellt (kein Briefing-Anker, kein
    rollierender) / WHEN ``check_all_trips()`` laeuft / THEN entsteht KEIN
    rollierender Alarm-Anker — weder ueber Trigger (a) noch (b).

    Sonst floesse eine als untauglich verworfene Basis ueber die
    #1916-Stufe-2-Mechanik ungeprueft zurueck: der rollierende Anker traegt
    selbst KEIN ``briefing_backed``-Feld und kaeme an der neuen
    Herkunftspruefung vorbei."""
    from services.weather_snapshot import WeatherSnapshotService

    user_id, trip_id = nutzer(), "trip-1699-ac10"

    ergebnis, mails = _ac10_lauf(user_id, trip_id, herkunft=False)

    assert WeatherSnapshotService(user_id=user_id).load_alarm_anchor(trip_id, "email") is None, (
        "AC-10: Aus einer wegen fehlenden Briefings verworfenen Basis darf kein "
        "rollierender Alarm-Anker entstehen."
    )
    assert not mails and ergebnis.alerts_sent == 0, (
        f"AC-10 (Kopplung): der Lauf darf gar nicht bis zum Versand kommen. "
        f"Zugestellt: {[s for s, _ in mails]}."
    )


def _dienst_mit_aufrufzaehler(user_id: str, mails: list):
    """Die ECHTE Dienstklasse, nur um ein Protokoll zweier Naehte erweitert: beide
    ueberschriebenen Methoden reichen unveraendert an ihre Originalfassung weiter,
    der Lauf bleibt der echte (kein Mock, keine Rueckgabe-Attrappe).

    ``besucht`` haelt die REIHENFOLGE fest, in der der Lauf die Touren erreicht
    (nur der Δ-Aufruf, nicht der amtliche) — ohne sie waere eine Aussage ueber
    „laeuft nach einer verworfenen Tour weiter" von der zufaelligen Sortierung
    aus ``load_all_trips()`` abhaengig."""
    from services.trip_alert import TripAlertService

    class _MitAufrufzaehler(TripAlertService):
        aufrufe: list = []
        besucht: list = []

        def _get_cached_weather(self, trip, *, tagesgleicher_anker_noetig, **kwargs):
            if tagesgleicher_anker_noetig:
                self.besucht.append(trip.id)
            return super()._get_cached_weather(
                trip, tagesgleicher_anker_noetig=tagesgleicher_anker_noetig, **kwargs,
            )

        def check_and_send_alerts(self, trip, cached_weather, *args, **kwargs):
            self.aufrufe.append(trip.id)
            return super().check_and_send_alerts(
                trip, cached_weather, *args, **kwargs,
            )

    dienst = _MitAufrufzaehler(
        settings=settings_email_only(), user_id=user_id,
        mail_sink=lambda subject, body: mails.append((subject, body)),
    )
    dienst.aufrufe, dienst.besucht = [], []
    return dienst


def test_ac10_verworfene_basis_ruft_check_and_send_alerts_gar_nicht_erst_auf():
    """AC-10 (Mechanismus statt Ergebnis — Fix-Loop F002).

    Die Spec begruendet AC-10 damit, dass ``check_and_send_alerts()`` bei
    verworfener Basis „gar nicht erst aufgerufen wird". Das pruefte bisher kein
    Test: beobachtet wurde nur die FOLGE (kein Versand, kein rollierender
    Anker), und die stellt sich auch dann ein, wenn die Methode sehr wohl laeuft
    und intern an ``cached_weather=None`` abstuerzt — den ``TypeError``
    verschluckt das ``except Exception`` in ``check_all_trips()``. Ein spaeteres
    ``cached_weather or []`` liesse die Zusicherung lautlos kippen, im
    Extremfall mit einem Alarm gegen eine LEERE Basis.

    GIVEN zwei Touren im selben Lauf — die VERWORFENE zuerst, danach eine mit
    gueltiger Basis / WHEN ``check_all_trips()`` laeuft / THEN steht nur die
    gueltige im Aufrufprotokoll, und der Lauf erreicht sie ueberhaupt. Die
    zweite Tour ist die Positivkontrolle: ohne sie waere das Protokoll auch dann
    leer, wenn es ueberhaupt nichts mehr aufzeichnet.

    Die Reihenfolge ist die eigentliche Zusicherung (Fix-Loop F006): das
    Verwerfen darf den Lauf nur fuer DIESE Tour beenden (``continue``), nicht
    fuer alle folgenden (``break``). Kaeme die verworfene Tour zuletzt, waere
    ein Abbruch von einem Weiterlaufen nicht unterscheidbar. ``load_all_trips()``
    liefert die Touren UNSORTIERT (``Path.glob()``, ``loader.py:1403``): die
    Reihenfolge ist umgebungsabhaengig und aus den Namen NICHT vorhersagbar —
    auch nicht alphabetisch. Die Namenswahl stellt sie hier guenstig, aber
    verlassen darf sich der Test darauf nicht: ``besucht[:1]`` prueft sie bei
    jedem Lauf nach, sodass eine andere Reihenfolge den Test rot macht statt
    blind.
    """
    verworfen, gueltig = "trip-1699-f002-a-verworfen", "trip-1699-f002-b-gueltig"
    user_id = nutzer()
    herkunft_setzen(
        undatierten_anker_schreiben(user_id, verworfen, target_date=date.today()), False,
    )
    undatierten_anker_schreiben(user_id, gueltig, target_date=date.today())
    save_trip(boeen_trip(verworfen, [date.today()]), user_id=user_id)
    save_trip(boeen_trip(gueltig, [date.today()]), user_id=user_id)

    mails: list = []
    dienst = _dienst_mit_aufrufzaehler(user_id, mails)
    dienst.check_all_trips()

    assert dienst.besucht[:1] == [verworfen], (
        "Fixtur-Schutz (F006): die VERWORFENE Tour muss zuerst drankommen, "
        "sonst kann dieser Test einen Schleifen-Abbruch danach gar nicht sehen. "
        f"Besuchte Reihenfolge: {dienst.besucht}"
    )
    assert gueltig in dienst.besucht, (
        "F006: Ein verworfener Anker legt NUR die betroffene Tour stumm — der "
        "Lauf muss mit der naechsten weitermachen (``continue``, nicht "
        f"``break``). Besuchte Reihenfolge: {dienst.besucht}"
    )
    assert gueltig in dienst.aufrufe, (
        "Positivkontrolle: fuer die Tour mit gueltiger Basis MUSS "
        f"check_and_send_alerts() laufen — sonst zaehlt das Protokoll nichts. "
        f"Aufgezeichnet: {dienst.aufrufe}"
    )
    assert verworfen not in dienst.aufrufe, (
        "AC-10: Bei wegen fehlenden Briefings verworfener Basis darf "
        "check_and_send_alerts() gar nicht erst aufgerufen werden — sonst "
        "haengt die Zusicherung nur daran, dass ein Absturz verschluckt wird. "
        f"Aufgezeichnet: {dienst.aufrufe}"
    )


def test_ac10_abgelaufener_rollierender_anker_bleibt_unveraendert():
    """AC-10 (Variante mit Bestand — Uebergangsfenster nach dem Deploy): GIVEN
    zusaetzlich einen rollierenden Anker vom VORTAG, den Stufe 2 an seinem
    Tagesbezug zu Recht verwirft, sodass die Kette auf die nicht
    briefing-gestuetzte Stufe 3 zurueckfaellt / WHEN der Lauf stattfindet /
    THEN bleibt seine Datei unveraendert (kein neuer ``snapshot_at``)."""
    from services.weather_snapshot import WeatherSnapshotService

    user_id, trip_id = nutzer(), "trip-1699-ac10-bestand"
    herkunft_setzen(
        undatierten_anker_schreiben(user_id, trip_id, target_date=date.today()), False,
    )
    save_trip(boeen_trip(trip_id, [date.today()]), user_id=user_id)
    WeatherSnapshotService(user_id=user_id).save_alarm_anchor(
        trip_id, date.today() - timedelta(days=1), [_wetter(ANKER_BOE_KMH)],
        "email",
    )
    pfad = rollierender_anker_pfad(user_id, trip_id)
    vorher = pfad.read_text()

    alarm_lauf(user_id)

    assert pfad.read_text() == vorher, (
        "AC-10: Der abgelaufene rollierende Anker darf aus einer verworfenen "
        "Basis heraus nicht fortgeschrieben werden — sonst waere die Tour ab "
        "sofort dauerhaft gegen einen erfundenen Vergleichspunkt bewacht."
    )


# ───── Fix-Loop R2: die Torbedingung in ``check_all_trips`` als KLASSE ───────
#
# Ausgezaehlt am Torcode (``trip_alert.py:540-547``): das Tor entscheidet aus
# genau ZWEI Groessen — ``cached`` (Δ-Basis gueltig / verworfen) und
# ``official_notices`` (amtliche Warnung liegt vor / nicht), also VIER
# Kombinationen. Einzeln nachgezogen hat das zweimal die naechste
# Nachbar-Kombination uebersehen (F002 ohne, F005 mit amtlicher Warnung).
#
# Der rollierende #1916-Anker ist KEINE dritte Achse DIESES Tors: er aendert
# nur, WORAUS ``cached`` entsteht (Stufe 2 statt 3), nicht die Torentscheidung
# — fuer das Tor steckt er in „Basis gueltig". Seine eigenen Naehte bewachen
# ``test_ac3_amtliche_warnung_ueberlebt_auch_die_stufe_2_weiche`` und
# ``test_ac10_abgelaufener_rollierender_anker_bleibt_unveraendert``. Positiv-
# kontrollen stecken in der Parametrisierung: jede Zusicherung „passiert NICHT"
# hat eine Matrixzeile, in der dieselbe Beobachtung „passiert" liefert.

@contextlib.contextmanager
def _amtliche_quelle(aktiv: bool):
    """Echte Quellen-Fixtur nur wenn gebraucht; Registrierung danach wieder her."""
    import services.official_alerts.base as basis
    from services.official_alerts import OfficialAlert, register_official_alert_source

    sicherung = list(basis._REGISTERED_SOURCES)
    basis._REGISTERED_SOURCES.clear()
    try:
        if aktiv:
            jetzt = datetime.now(timezone.utc)
            register_official_alert_source(_FesteAmtlicheQuelle(OfficialAlert(
                source="tdd-1699", hazard="thunderstorm", level=3,
                label="Gewitterwarnung (Matrix)", region_label="Testregion",
                valid_from=jetzt - timedelta(hours=1),
                valid_to=jetzt + timedelta(hours=6),
            )))
        yield
    finally:
        basis._REGISTERED_SOURCES.clear()
        basis._REGISTERED_SOURCES.extend(sicherung)


@pytest.mark.parametrize("amtlich", [True, False])
@pytest.mark.parametrize("basis_gueltig", [True, False])
def test_torbedingung_matrix_basis_mal_amtliche_warnung(basis_gueltig, amtlich):
    """Die Torbedingung ueber BEIDE Achsen (Fix-Loop F002 + F005).

    GIVEN eine Tour, deren Δ-Basis entweder briefing-gestuetzt oder wegen
    ``not_briefing_backed`` verworfen ist, mit oder ohne vorliegende amtliche
    Warnung / WHEN ``check_all_trips()`` laeuft / THEN gilt fuer jede der vier
    Kombinationen:

    * ``check_and_send_alerts()`` laeuft GENAU DANN, wenn die Basis gueltig ist
      — die Zusicherung, auf die AC-10 sich beruft, unabhaengig von einer
      gleichzeitig vorliegenden amtlichen Warnung;
    * zugestellt wird genau dann, wenn eine der beiden Quellen etwas hergibt;
    * ein rollierender Anker (#1916) entsteht NUR aus gueltiger Basis — ein
      amtlicher Alleinversand schreibt keinen;
    * ``not_briefing_backed`` steht genau bei verworfener Basis in der Diagnose.

    Der Refactor ``if not cached and not official_notices:`` — plausibel als
    „einheitlichere Behandlung" — reisst die erste Zusicherung.
    """
    from services.weather_snapshot import WeatherSnapshotService

    user_id = nutzer()
    trip_id = f"trip-1699-matrix-{int(basis_gueltig)}{int(amtlich)}"
    pfad = undatierten_anker_schreiben(user_id, trip_id, target_date=date.today())
    if not basis_gueltig:
        herkunft_setzen(pfad, False)
    trip = boeen_trip(trip_id, [date.today()])
    trip.official_alert_triggers_enabled = amtlich
    save_trip(trip, user_id=user_id)

    mails: list = []
    dienst = _dienst_mit_aufrufzaehler(user_id, mails)
    with _amtliche_quelle(amtlich):
        ergebnis = dienst.check_all_trips()

    lage = f"Basis gueltig={basis_gueltig}, amtliche Warnung={amtlich}"
    assert (trip_id in dienst.aufrufe) is basis_gueltig, (
        f"{lage}: check_and_send_alerts() muss genau bei gueltiger Basis laufen "
        f"— eine verworfene Basis darf auch NEBEN einer amtlichen Warnung nicht "
        f"durchgereicht werden. Aufgezeichnet: {dienst.aufrufe}"
    )
    versand = basis_gueltig or amtlich
    assert bool(mails) is versand and ergebnis.alerts_sent == (1 if versand else 0), (
        f"{lage}: genau {1 if versand else 0} Versand erwartet, gezaehlt "
        f"{ergebnis.alerts_sent}, zugestellt {[s for s, _ in mails]}"
    )
    rollierend = WeatherSnapshotService(user_id=user_id).load_alarm_anchor(trip_id, "email")
    assert (rollierend is not None) is basis_gueltig, (
        f"{lage}: ein rollierender Alarm-Anker darf NUR aus gueltiger Basis "
        f"entstehen (#1916 Trigger (a)) — ein amtlicher Alleinversand keinen."
    )
    gruende = [z.get("reason") for z in diagnose_zeilen(user_id)]
    assert (GRUND_OHNE_BRIEFING in gruende) is not basis_gueltig, (
        f"{lage}: Diagnose-Gruende {gruende} passen nicht zur Lage."
    )


