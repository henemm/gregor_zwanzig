"""TDD RED — Issue #2017 Scheibe B: Messpunkt des Starkregen-Kurzfristhinweises.

SPEC: docs/specs/modules/fix_2017_nowcast_messpunkt.md (AC-9, AC-12)
KONTEXT: docs/context/fix-2017-nowcast-messpunkt.md

Der zweite `get_nowcast()`-Aufrufer des Trip-Pfads sitzt in
`TripReportSchedulerService._build_starkregen_hint()`
(`trip_report_scheduler.py`, Abrufstelle ~:1809-1815). Er fragt heute
`active.start_point` ab — den Wegpunkt, den der Wanderer bereits verlassen
hat. Sein Fehlerfenster ist das GROESSERE der beiden: der Hinweis kennt
keinen Onset-Grenzwert und akzeptiert jeden Treffer im vollen
`NOWCAST_HORIZON_MIN`-Fenster (180 Min). Bei drei Stunden Vorlauf ist der
Wanderer regelmaessig ein bis zwei Segmente weiter.

Zielzustand (#2017): abgefragt wird die Position zur MITTE des
Vorwarnfensters, also `position_at_time(..., at=jetzt + NOWCAST_HORIZON_MIN
// 2)`. Der Alarm-Pfad benutzt denselben Baustein mit SEINEM eigenen Offset
(`RADAR_ONSET_THRESHOLD_MIN // 2`) — geteilt wird die Positionsberechnung,
nicht der Offset und nicht die Segmentwahl.

RED-Treiber:
- `test_ac9_...` (Fall B) und `test_ac12_...`: der Abruf erfolgt heute am
  Segment-Startpunkt statt am interpolierten Punkt.
- `test_ac9_...` (Fall A) ist ein REGRESSIONSSCHUTZ und heute bereits gruen:
  er haelt fest, dass dieser Pfad seine EIGENE, vorwaertsgerichtete
  Segmentwahl behaelt (kein Vortags-Rueckgriff, #1667 S3) — genau das darf
  die Aenderung nicht mitnehmen.

Warum diese Datei NEU ist: die Spec fuehrt sie als „bestehend, ergaenzt".
Das trifft nicht zu — es gab sie nicht. Der vorhandene Nachbar
`tests/tdd/test_starkregen_kurzfristhinweis.py` gehoert zu #1439 und prueft
die EINBINDUNG des Hinweises (Budget-Gate, Horizont-Guard, gerenderter Text);
der MESSPUNKT ist eine andere Zusicherung und bekommt deshalb eine eigene,
nach Verhalten benannte Datei. Die dortigen Bausteine werden importiert
statt nachgebaut.

Mock-frei (CLAUDE.md „Test-Politik"): kein `Mock()`/`patch()`/`MagicMock`.
`RadarNowcastService.get_nowcast` wird an der TRANSPORT-Grenze durch eine
echte Funktion ersetzt, die ein echtes `NowcastResult` liefert und die
tatsaechlich uebergebenen Argumente festhaelt (Muster
`test_starkregen_kurzfristhinweis.py::_install_fake_nowcast`, dort um
`elevation_m` erweitert). Der Erwartungswert wird ANALYTISCH aus den
Segmentgrenzen gerechnet, nicht durch Aufruf von `position_at_time()` —
sonst prueefte der Test den Prueefling gegen sich selbst.

🔴 Gestellte Uhr (`freeze_time`), bewusst nicht die Wanduhr: die Etappen
dieser Datei entstehen aus `arrival_override`-HH:MM-Angaben auf EINEM
Kalendertag. Ein Zieloffset von 90 Minuten ueber die Tagesgrenze haette
kein Segment mehr getroffen (der Fall prueefte dann die Vorwaertssuche statt
der Interpolation), und Fall A braucht zusaetzlich einen definierten Vortag.
Gewaehlt ist mittags — dasselbe Muster wie in
`test_radar_onset_threshold_variance.py` und
`test_radar_alert_segment_end_guard.py`. Island (`LAT`/`LON`, UTC+0
ganzjaehrig) macht die Ortszeit direkt aus der gestellten UTC-Zeit ablesbar.
Die Uhr wird NICHT zurueckgedreht.
"""
from __future__ import annotations

import uuid
from datetime import date as date_type
from datetime import datetime, timedelta, timezone

from freezegun import freeze_time

from app.models import TripReportConfig
from app.trip import Stage, Trip, Waypoint
from services.radar_service import INTENSITY_HEAVY, NowcastResult, RadarNowcastService

from tests.tdd.test_starkregen_kurzfristhinweis import (
    LAT, LON, _ReportRecorder, _run_briefing, _uid,
)

# Mittags, weit von jeder Tagesgrenze — s. Modul-Docstring.
_MITTAGS = "2026-08-18T12:00:00+00:00"

# Heutige Etappe: 11:30–15:30 Ortszeit (= UTC), also bei 12:00 aktiv.
# Die Wegpunkte liegen bewusst weit auseinander, damit sich drei Kandidaten
# eindeutig unterscheiden lassen:
#   Startpunkt (alter Messpunkt)            -> (64.0,   -22.0)
#   Offset des ALARM-Pfads (55 // 2 = 27)   -> ~(64.095, -21.905)
#   Offset des HINWEIS-Pfads (180 // 2 = 90)-> (64.2,   -21.8)
_HEUTE_START = (LAT, LON, 300.0)
_HEUTE_ENDE = (LAT + 0.4, LON + 0.4, 1500.0)

# Vortags-Etappe fuer Fall A: laeuft ueber Mitternacht und waere um 12:00
# noch aktiv. Koordinaten klar verschieden von der heutigen Etappe.
_GESTERN_START = (LAT - 1.0, LON - 1.0, 50.0)
_GESTERN_ENDE = (LAT - 0.9, LON - 0.9, 80.0)


def _wp(uid_: str, punkt, ankunft: str) -> Waypoint:
    lat, lon, hoehe = punkt
    return Waypoint(
        id=uid_, name=uid_, lat=lat, lon=lon, elevation_m=hoehe,
        arrival_override=ankunft,
    )


def _trip_mit_etappen(trip_id: str, stages: list[Stage]) -> Trip:
    trip = Trip(id=trip_id, name=f"#2017 {trip_id}", stages=stages,
                official_alerts_enabled=False)
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=False, send_telegram=False, send_sms=False,
    )
    return trip


def _heute_stage(tag: date_type, *, start: str, ende: str) -> Stage:
    return Stage(
        id="S-heute", name="Heute", date=tag,
        waypoints=[_wp("H0", _HEUTE_START, start), _wp("H1", _HEUTE_ENDE, ende)],
    )


def _hinweis_offset_minuten() -> int:
    """Zieloffset des HINWEIS-Pfads = halbes Vorhersagefenster.

    Ueber die MODUL-Referenz gelesen (nicht als `from ... import` gebunden),
    damit ein Nachziehen der Quelle hier nicht still an einer Kopie
    vorbeilaeuft — dieselbe Regel wie fuer `RADAR_ONSET_THRESHOLD_MIN`.
    """
    from services import radar_service as radar_service_mod

    return radar_service_mod.NOWCAST_HORIZON_MIN // 2


def _alarm_offset_minuten() -> int:
    from services import radar_service as radar_service_mod

    return radar_service_mod.RADAR_ONSET_THRESHOLD_MIN // 2


def _interpoliert(active, now_utc: datetime, offset_minuten: int):
    """(Zeitanteil p, (lat, lon, elevation_m)) — analytisch, ohne den Prueefling."""
    at = now_utc + timedelta(minutes=offset_minuten)
    spanne = (active.end_time - active.start_time).total_seconds()
    assert spanne > 0, "Testvoraussetzung: das Segment braucht eine echte Dauer"
    p = (at - active.start_time).total_seconds() / spanne
    sp, ep = active.start_point, active.end_point
    return p, (
        sp.lat + p * (ep.lat - sp.lat),
        sp.lon + p * (ep.lon - sp.lon),
        sp.elevation_m + p * (ep.elevation_m - sp.elevation_m),
    )


def _segmente(trip: Trip, tag: date_type) -> list:
    from services.trip_segments import convert_trip_to_segments

    return convert_trip_to_segments(trip, tag)


def _lokale_segmentwahl(segments: list, now_utc: datetime):
    """Die Auswahl, die `_build_starkregen_hint()` selbst trifft (aktiv,
    sonst Vorschau auf das erste) — hier nachgezogen, um die Erwartung zu
    rechnen. Sie wird NICHT als Ersatz fuer den Pruefling aufgerufen."""
    for seg in segments:
        if seg.start_time <= now_utc <= seg.end_time:
            return seg
    return segments[0] if segments and now_utc < segments[0].start_time else None


def _install_aufzeichnenden_nowcast(monkeypatch, calls: list) -> None:
    """Ersetzt `RadarNowcastService.get_nowcast` durch eine ECHTE Funktion mit
    echtem `NowcastResult` (Transport-Grenze, kein Netz, kein Mock-Objekt) und
    haelt lat/lon/elevation_m/priority jedes Aufrufs fest."""

    def _aufzeichnend(self, lat, lon, elevation_m=None, priority="user_briefing"):
        calls.append({
            "lat": lat, "lon": lon, "elevation_m": elevation_m,
            "priority": priority,
        })
        return NowcastResult(
            onset_minutes=100, intensity_label=INTENSITY_HEAVY,
            source="radar", is_convective=False,
        )

    monkeypatch.setattr(RadarNowcastService, "get_nowcast", _aufzeichnend)


# ══════════════════════════════════════ AC-9 ══════════════════════════════


def test_ac9_starkregen_hinweis_misst_am_eigenen_fenstermittelpunkt(monkeypatch):
    """AC-9: Der Starkregen-Kurzfristhinweis fragt an der zur Mitte SEINES
    Vorwarnfensters interpolierten Position ab und behaelt dabei seine eigene,
    unveraenderte Segmentwahl.

    Reihenfolge im Testkoerper: erst Fall A, dann Fall B. Fall B ist der
    RED-Treiber und wuerde sonst abbrechen, bevor Fall A ueberhaupt gelaufen
    ist — der Regressionsschutz waere dann bis GREEN unbelegt.

    Fall B (RED-Treiber) — eigener Offset:
      Given ein aktives Geh-Segment 11:30–15:30 und gestellte Uhr 12:00 /
      When der planmaessige Briefing-Pfad laeuft / Then traegt der
      `get_nowcast()`-Aufruf die Position zu `jetzt + NOWCAST_HORIZON_MIN //
      2` (= +90 Min, Zeitanteil 120/240 = 0,5) samt interpolierter Hoehe —
      nicht `active.start_point` und ausdruecklich auch nicht die Position
      zum Offset des ALARM-Pfads (`RADAR_ONSET_THRESHOLD_MIN // 2` = +27
      Min). Beide Pfade teilen die Berechnung, nicht den Offset.

    Fall A (REGRESSIONSSCHUTZ, heute bereits gruen) — eigene Segmentwahl:
      Given ein Trip, dessen VORTAGS-Etappe ueber Mitternacht laeuft und um
      12:00 noch aktiv waere, waehrend die heutige Etappe erst um 14:00
      beginnt / When der Briefing-Pfad laeuft / Then misst er an der HEUTIGEN
      Etappe (Vorschau, Fortschritt 0 = deren Startpunkt), waehrend die
      Auswahl des Alarm-Pfads (`resolve_current_segment`) die Vortags-Etappe
      liefert. Der Vortags-Rueckgriff aus #1667 S3 gehoert dem Alarm-Pfad und
      darf mit #2017 nicht in den Briefing-Pfad wandern.
    """
    # ── Fall A: eigene Segmentwahl, kein Vortags-Rueckgriff ──────────────
    with freeze_time(_MITTAGS):
        now_utc = datetime.now(timezone.utc)
        heute = date_type.today()
        gestern = heute - timedelta(days=1)
        stage_gestern = Stage(
            id="S-gestern", name="Gestern", date=gestern,
            waypoints=[
                _wp("G0", _GESTERN_START, "23:00"),
                _wp("G1", _GESTERN_ENDE, "13:00"),
            ],
        )
        trip_a = _trip_mit_etappen(
            f"trip-2017-ac9a-{uuid.uuid4().hex[:6]}",
            [stage_gestern, _heute_stage(heute, start="14:00", ende="18:00")],
        )

        # Testvoraussetzung: die beiden Auswahlverfahren MUESSEN hier
        # auseinanderlaufen — sonst ist der Regressionsschutz trivial wahr.
        from services.trip_day import trip_local_today
        from services.trip_segments import resolve_current_segment

        alarm_wahl = resolve_current_segment(
            trip_a, now_utc, trip_local_today(trip_a, now_utc),
        )
        assert alarm_wahl is not None, (
            "Testvoraussetzung: der Alarm-Pfad muss ein Segment finden"
        )
        assert abs(alarm_wahl[0].start_point.lat - _GESTERN_START[0]) < 1e-6, (
            f"Testvoraussetzung: der Alarm-Pfad muss ueber seinen "
            f"Vortags-Rueckgriff (#1667 S3) die GESTRIGE Etappe waehlen, "
            f"gewaehlt wurde aber lat={alarm_wahl[0].start_point.lat}"
        )

        calls_a: list = []
        _install_aufzeichnenden_nowcast(monkeypatch, calls_a)
        rec_a = _ReportRecorder()
        rec_a.install(monkeypatch)
        _run_briefing(rec_a, _uid("2017-ac9a"), trip_a)

        assert calls_a, (
            "Testvoraussetzung: der Briefing-Pfad hat get_nowcast nicht "
            "aufgerufen (die heutige Etappe beginnt in 120 Min, also "
            "innerhalb des Horizonts)"
        )
        ruf_a = calls_a[0]
        assert abs(ruf_a["lat"] - _HEUTE_START[0]) < 1e-6, (
            f"AC-9 (Fall A): der Briefing-Pfad misst an lat={ruf_a['lat']:.4f}; "
            f"erwartet die HEUTIGE Etappe (Vorschau, Fortschritt 0 = "
            f"lat {_HEUTE_START[0]}). lat {_GESTERN_START[0]} waere die "
            f"gestrige Etappe — der Vortags-Rueckgriff gehoert dem Alarm-Pfad "
            f"(#1667 S3) und darf hier nicht auftauchen."
        )

    # ── Fall B: eigener Offset ───────────────────────────────────────────
    with freeze_time(_MITTAGS):
        now_utc = datetime.now(timezone.utc)
        heute = date_type.today()
        trip_b = _trip_mit_etappen(
            f"trip-2017-ac9b-{uuid.uuid4().hex[:6]}",
            [_heute_stage(heute, start="11:30", ende="15:30")],
        )
        segmente = _segmente(trip_b, heute)
        active = _lokale_segmentwahl(segmente, now_utc)
        assert active is not None, (
            "Testvoraussetzung: um 12:00 muss das Segment 11:30–15:30 aktiv sein"
        )

        p_hinweis, (soll_lat, soll_lon, soll_hoehe) = _interpoliert(
            active, now_utc, _hinweis_offset_minuten(),
        )
        _p_alarm, (alarm_lat, alarm_lon, _ah) = _interpoliert(
            active, now_utc, _alarm_offset_minuten(),
        )
        sp = active.start_point

        assert 0.0 < p_hinweis < 1.0, (
            f"Testvoraussetzung: der Zieloffset muss INNERHALB des Segments "
            f"liegen, p={p_hinweis:.4f}"
        )
        assert abs(soll_lat - sp.lat) > 0.05, (
            f"Testvoraussetzung: interpolierter Punkt (lat {soll_lat:.4f}) und "
            f"Startpunkt (lat {sp.lat:.4f}) muessen sich messbar unterscheiden"
        )
        assert abs(soll_lat - alarm_lat) > 0.05, (
            f"Testvoraussetzung: die beiden Offsets muessen unterscheidbare "
            f"Punkte ergeben — Hinweis lat {soll_lat:.4f} vs. Alarm lat "
            f"{alarm_lat:.4f}; sonst belegt der Fall nicht, dass jeder Pfad "
            f"SEINEN Offset benutzt"
        )

        calls_b: list = []
        _install_aufzeichnenden_nowcast(monkeypatch, calls_b)
        rec_b = _ReportRecorder()
        rec_b.install(monkeypatch)
        _run_briefing(rec_b, _uid("2017-ac9b"), trip_b)

        assert calls_b, (
            "Testvoraussetzung: der Briefing-Pfad hat get_nowcast nicht "
            "aufgerufen — ohne Abruf ist nichts zu pruefen"
        )
        ruf = calls_b[0]
        assert abs(ruf["lat"] - soll_lat) < 1e-6 and abs(ruf["lon"] - soll_lon) < 1e-6, (
            f"AC-9 (Fall B): get_nowcast an ({ruf['lat']:.4f}, {ruf['lon']:.4f}); "
            f"erwartet der zur Mitte des 180-Minuten-Fensters interpolierte "
            f"Punkt ({soll_lat:.4f}, {soll_lon:.4f}), p={p_hinweis:.4f}. "
            f"({sp.lat:.4f}, {sp.lon:.4f}) waere der ALTE Messpunkt "
            f"(Segment-Startpunkt); ({alarm_lat:.4f}, {alarm_lon:.4f}) waere "
            f"der Offset des ALARM-Pfads — dieser Pfad hat seinen eigenen."
        )
        assert ruf["elevation_m"] is not None and abs(ruf["elevation_m"] - soll_hoehe) <= 0.5, (
            f"AC-9 (Fall B): elevation_m={ruf['elevation_m']}; erwartet die "
            f"mitgewanderte Hoehe {soll_hoehe:.2f} m (zwischen "
            f"{sp.elevation_m} m und {active.end_point.elevation_m} m). "
            f"{sp.elevation_m} m waere die Hoehe des verlassenen Startpunkts."
        )

# ══════════════════════════════════════ AC-12 ═════════════════════════════


def test_ac12_starkregen_hinweis_ruft_get_nowcast_genau_einmal(monkeypatch):
    """AC-12 (Budget-Invariante, Hinweis-Pfad): genau EIN `get_nowcast()`-
    Aufruf je Briefing-Lauf und Trip — und dieser eine am neuen Messpunkt.

    Die Zusicherung ist bewusst zweiteilig: die reine Zahl stimmt heute
    bereits, der ORT nicht. Ein iteratives Nachfassen an der Onset-Position
    (Variante 2, in der Spec ausdruecklich ausgeschlossen) risse die Zaehlung;
    ein unveraenderter Startpunkt die Ortsangabe. Erst zusammen bewachen sie
    „ein Abruf, und zwar am richtigen Ort".
    """
    with freeze_time(_MITTAGS):
        now_utc = datetime.now(timezone.utc)
        heute = date_type.today()
        trip = _trip_mit_etappen(
            f"trip-2017-ac12-{uuid.uuid4().hex[:6]}",
            [_heute_stage(heute, start="11:30", ende="15:30")],
        )
        active = _lokale_segmentwahl(_segmente(trip, heute), now_utc)
        assert active is not None, "Testvoraussetzung: aktives Segment noetig"
        p, (soll_lat, soll_lon, _h) = _interpoliert(
            active, now_utc, _hinweis_offset_minuten(),
        )

        calls: list = []
        _install_aufzeichnenden_nowcast(monkeypatch, calls)
        rec = _ReportRecorder()
        rec.install(monkeypatch)
        _run_briefing(rec, _uid("2017-ac12"), trip)

        assert len(calls) == 1, (
            f"AC-12: erwartet genau EIN get_nowcast() je Briefing-Lauf, "
            f"erhalten {len(calls)}: {calls!r}"
        )
        ruf = calls[0]
        assert abs(ruf["lat"] - soll_lat) < 1e-6 and abs(ruf["lon"] - soll_lon) < 1e-6, (
            f"AC-12: der EINE Abruf muss am neuen Messpunkt erfolgen — "
            f"({ruf['lat']:.4f}, {ruf['lon']:.4f}) statt erwartet "
            f"({soll_lat:.4f}, {soll_lon:.4f}), p={p:.4f}"
        )
        assert ruf["priority"] == "polling", (
            f"AC-12: der Briefing-Nowcast bleibt ein drosselbarer "
            f"Hintergrund-Abruf (`polling`, #1329 C2), war {ruf['priority']!r}"
        )
