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

import json
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

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
    trip.report_config = TripReportConfig(trip_id=trip_id, send_email=True,
                                          alert_on_changes=True)
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
