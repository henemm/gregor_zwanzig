"""TDD RED -- plausibler GPS-Fix uebersteuert die Planposition
(Issue #2327, AC-3 bis AC-9; ADR-0102).

SPEC: docs/specs/modules/feat_2327_gps_etappenfortschritt.md

VERTRAG fuer /50 (in der Spec offen gelassen, hier festgeschrieben):

* ``services.position_fix.record_position_fix(user_id: str, lat: float,
  lon: float, observed_at: datetime) -> <beliebig>`` -- ``observed_at`` ist
  zonenbewusst (Journal-Zeitstempel). Die Heute-Etappe wird je Trip des
  Nutzers zum Zeitpunkt ``observed_at`` bestimmt (Ortstag der Etappe); der
  Track kommt aus ``data/users/<uid>/gpx/``. Ergebnis wird hier NICHT
  ausgewertet -- geprueft wird ausschliesslich die WIRKUNG (Fix-Datei,
  Positionsquelle). Leere ``user_id``: kein Schreibvorgang (ein
  ``ValueError`` ist erlaubt).
* Fix-Datei: ``data/users/<uid>/position_fix.json`` (Spec "Affected
  Files"). Ihr Schema ist frei; die Tests lesen sie nicht aus, sondern
  pruefen Existenz und (AC-6) Unveraendertheit der Bytes.
* ``trip_segments.position_at_time``, ``points_with_passage_times`` und
  ``points_along_remaining_route`` bekommen ein Keyword ``user_id: str |
  None = None``. Ohne ``user_id`` (``None``) bleibt alles bit-identisch zum
  Stand vor dieser Scheibe -- es wird NIE ueber Nutzergrenzen hinweg nach
  einem Fix gesucht. Mit ``user_id`` und gueltigem Fix fuer diesen Trip und
  dieses Etappen-Datum ist der erste Punkt bei Abfrage zum Meldezeitpunkt
  (``at <= observed_at``) der gesnappte Fix; bei spaeterer Abfrage ist er um
  den Planfortschritt zwischen ``observed_at`` und ``at`` (Plan-Tempo der
  Etappe, begrenzt auf das Etappenende) entlang der Strecke weitergewandert
  -- der Fix friert die Position NICHT ein (Spec AC-4, Changelog 26.10.).
  Die Folgepunkte laufen wie bei ``points_from_km`` ab dieser
  fortgeschriebenen Position entlang der Reststrecke (Punktabstand
  ``RADAR_ZONE_POINT_SPACING_KM``). Soll-Werte rechnet
  ``tests.helpers.position_fix_fixtures.fortgeschrieben`` geschlossen.
  Tests, die NICHT den Fortschritt pruefen (AC-3/5/6/7/9), fragen genau zum
  Meldezeitpunkt ab -- dort ist die Position der Fix selbst.
  BEGRUENDUNG: ``position_at_time(trip, active, segment_date, at)`` kennt
  heute keinen Nutzer, und ``Trip`` traegt keinen Eigentuemer -- die
  Fix-Datei liegt aber je Nutzer. Ein Lookup nur ueber ``trip.id`` waere ein
  Cross-User-Leck (AC-9 prueft das mit GLEICHER Trip-ID bei zwei Nutzern).
  ACHTUNG: das widerspricht der Spec-Formulierung "keine Aenderung in den
  fuenf Konsumenten" -- die Konsumenten muessen ``user_id`` durchreichen.
  Der Konsumenten-Test
  ``test_ac4_radar_misst_an_der_fortgeschriebenen_position_im_echten_alarmlauf``
  geht deshalb durch den ECHTEN ``check_radar_alerts()`` (der besitzt eine
  ``user_id``) und haengt nicht davon ab, WIE der Lookup gebaut wird.
* Verworfene Fixes (zu weit, mehrdeutig) werden aus ``position_fix.py``
  heraus geloggt (geprueft ueber ``record.pathname``, nicht ueber Wortlaut).

RED-GRUND (Fortschreibung, 26.10.): die Positionsquelle liefert bei
spaeterer Abfrage weiter den eingefrorenen Fix statt Fix + Planfortschritt
(``test_ac4_*_fortgeschrieben*``, ``test_ac4_folgepunkte_*``,
``test_ac4_radar_*``, ``test_ac8_*``, ``test_ac4_begrenzt_*``). Die
Meldezeitpunkt-Tests (``test_ac4_*_zum_meldezeitpunkt*``) und AC-3/5/6/7/9
sind schon gruen und bleiben es.

Jeder Verwerfungs-Test traegt eine POSITIVE KONTROLLE im selben Test (ein
plausibler Fix wirkt), damit ein Stub, der nie etwas tut, nicht gruen wird.

AC-8-Mutationsgegenprobe: wird der Fix-Zweig in ``position_at_time``
entfernt, werden ``test_ac4_position_zum_meldezeitpunkt_ist_der_gesnappte_fix``
und der Radar-Test rot; die Gleichheit ``points_with_passage_times()[0] ==
points_along_remaining_route()[0] == position_at_time()`` bewacht, dass es
EINE Positionsquelle gibt und keine zweite Kopie.

Kein Mock-Theater: echte Trips/GPX unter dem isolierten Datenbaum
(``tests/conftest.py::_isolate_data_root``), echte Positionsquelle, echter
Alarmlauf mit einer ``RadarNowcastService``-UNTERKLASSE am DI-Seam, die nur
mitschreibt. Uhr per ``freeze_time``.
"""
from __future__ import annotations

import logging
import uuid
from datetime import timedelta

import pytest
from freezegun import freeze_time

from app.loader import get_data_dir, get_data_root
from services.trip_segments import (
    RADAR_ZONE_MAX_POINTS,
    RADAR_ZONE_POINT_SPACING_KM,
    points_along_remaining_route,
    points_with_passage_times,
    position_at_time,
    resolve_current_segment,
)
from tests.helpers.nowcast_gate_fixtures import (
    aufzeichnender_radar_dienst,
    reset_radar_cache,
    settings_email_only,
)
from tests.helpers.position_fix_fixtures import (
    ECHT_HEUTE_KOORD,
    FAHRPLAN_RAST,
    FAHRPLAN_ZWEI,
    GAP_MITTE_LAT,
    GAP_NORD_LAT,
    GAP_SUED_LAT,
    ROUTE_LON,
    START_LAT,
    START_ZEIT,
    TAG,
    ZIEL_LAT,
    ZIEL_ZEIT,
    ZONE,
    abstand_m,
    alle_fix_dateien,
    anderer_track_punkte,
    fix_datei,
    fortgeschrieben,
    gpx_schreiben,
    heute_track_punkte,
    kreuz_track_punkte,
    lade_trip,
    ortszeit,
    plan_lat_bei,
    planposition,
    planzeit_bei,
    punkt_neben_route,
    toleranz_fortschreibung,
    trip_schreiben,
    trip_schreiben_fahrplan,
)

_SNAP_TOL_M = 5.0
_DEUTLICH_M = 1000.0


def _uid(tag: str) -> str:
    return f"gz2327-{tag}-{uuid.uuid4().hex[:6]}"


def _nutzer_mit_trip(tag: str, *, trip_id: str | None = None, mit_folgetag: bool = False):
    uid = _uid(tag)
    tid = trip_id or f"trip-2327-{uuid.uuid4().hex[:6]}"
    gpx_schreiben(uid, "heute", heute_track_punkte())
    trip_schreiben(uid, tid, mit_folgetag=mit_folgetag)
    return uid, tid


def _record(uid: str, punkt, observed_at, *, jetzt=None) -> None:
    from services.position_fix import record_position_fix

    with freeze_time(jetzt or observed_at):
        record_position_fix(uid, punkt[0], punkt[1], observed_at)


def _quelle(uid: str, tid: str, at, *, user_id="__gleich__"):
    """(position_at_time, points_with_passage_times, points_along_remaining_route)
    so, wie ein Konsument sie bildet: Trip aus ``load_all_trips(uid)``,
    Segmentwahl ueber ``resolve_current_segment`` am Ortstag von ``at``.
    ``user_id=None`` -> Aufruf OHNE Keyword (Stand vor dieser Scheibe)."""
    trip = lade_trip(uid, tid)
    with freeze_time(at):
        resolved = resolve_current_segment(trip, at, at.astimezone(ZONE).date())
        assert resolved is not None, f"Testaufbau: kein Segment um {at}"
        active, seg_date = resolved
        if user_id is None:
            return (
                position_at_time(trip, active, seg_date, at),
                points_with_passage_times(trip, active, seg_date, at),
                points_along_remaining_route(trip, active, seg_date, at),
            )
        kw = {"user_id": uid if user_id == "__gleich__" else user_id}
        return (
            position_at_time(trip, active, seg_date, at, **kw),
            points_with_passage_times(trip, active, seg_date, at, **kw),
            points_along_remaining_route(trip, active, seg_date, at, **kw),
        )


def _position(uid, tid, at, **kw):
    return _quelle(uid, tid, at, **kw)[0]


def _logs_aus_position_fix(caplog) -> list:
    return [r for r in caplog.records if r.pathname.endswith("position_fix.py")]


# ══════════════════════════════════ AC-3 ══════════════════════════════════


def test_ac3_99m_neben_dem_langen_abschnitt_wird_uebernommen():
    uid, tid = _nutzer_mit_trip("ac3-99")
    p99 = punkt_neben_route(GAP_MITTE_LAT, 99.0)
    naechster_trackpunkt_m = min(
        abstand_m(p99, (GAP_SUED_LAT, ROUTE_LON)), abstand_m(p99, (GAP_NORD_LAT, ROUTE_LON)),
    )
    assert naechster_trackpunkt_m > 500.0, "Testaufbau: Punkt muss weit von Trackpunkten liegen"

    _record(uid, p99, ortszeit(8, 55), jetzt=ortszeit(9, 0))

    assert fix_datei(uid).exists(), "AC-3: 99-m-Fix wurde nicht gespeichert"
    pos = _position(uid, tid, ortszeit(8, 55))  # Meldezeitpunkt: Position == Fix
    lot = (GAP_MITTE_LAT, ROUTE_LON)
    assert abstand_m(pos, lot) <= _SNAP_TOL_M, (
        f"AC-3: erster Punkt {pos} ist nicht das Lot {lot} des 99-m-Fixes auf die Strecke"
    )


def test_ac3_101m_wird_verworfen_und_geloggt(caplog):
    caplog.set_level(logging.DEBUG)
    uid, tid = _nutzer_mit_trip("ac3-101")
    vorher = _quelle(uid, tid, ortszeit(9, 0), user_id=None)

    _record(uid, punkt_neben_route(GAP_MITTE_LAT, 101.0), ortszeit(8, 50), jetzt=ortszeit(9, 0))

    assert not fix_datei(uid).exists(), "AC-3: 101-m-Fix darf nicht gespeichert werden"
    assert _quelle(uid, tid, ortszeit(9, 0)) == vorher, (
        "AC-3: 101-m-Fix hat die Positionsquelle veraendert"
    )
    assert _logs_aus_position_fix(caplog), "AC-3: verworfener Fix wurde nicht geloggt"

    # Positive Kontrolle: derselbe Nutzer, ein 99-m-Punkt wirkt.
    _record(uid, punkt_neben_route(GAP_MITTE_LAT, 99.0), ortszeit(8, 55), jetzt=ortszeit(9, 0))
    assert abstand_m(_position(uid, tid, ortszeit(8, 55)), (GAP_MITTE_LAT, ROUTE_LON)) <= _SNAP_TOL_M


def test_ac3_punkt_mitten_auf_dem_langen_abschnitt_wird_akzeptiert():
    """Abstand zur STRECKE, nicht zum naechsten Trackpunkt: der Punkt liegt
    ~2,5 km von beiden Trackpunkten entfernt, aber 0 m von der Strecke."""
    uid, tid = _nutzer_mit_trip("ac3-mitte")
    mitte = (GAP_MITTE_LAT, ROUTE_LON)
    assert abstand_m(mitte, (GAP_SUED_LAT, ROUTE_LON)) > 2000.0

    _record(uid, mitte, ortszeit(8, 55), jetzt=ortszeit(9, 0))

    assert fix_datei(uid).exists()
    assert abstand_m(_position(uid, tid, ortszeit(8, 55)), mitte) <= _SNAP_TOL_M


# ══════════════════════════════════ AC-4 / AC-8 ═══════════════════════════


_ZIEL = (ZIEL_LAT, ROUTE_LON)


def _unterscheidbar(erwartet, *, fix, at) -> None:
    """Testaufbau: die Soll-Position muss sich von den drei Fehlbildern
    deutlich unterscheiden -- eingefrorener Fix, Planposition zur Zeit ``at``
    und Etappenende -- sonst wird eine falsche Implementierung zufaellig
    gruen."""
    for name, falsch in (("eingefrorener Fix", fix), ("Planposition", planposition(at)), ("Etappenende", _ZIEL)):
        assert abstand_m(erwartet, falsch) > _DEUTLICH_M, (
            f"Testaufbau: Soll {erwartet} liegt zu nah am Fehlbild '{name}' {falsch}"
        )


def test_ac4_position_zum_meldezeitpunkt_ist_der_gesnappte_fix():
    """AC-4, erster Halbsatz: bei Abfrage zum Meldezeitpunkt (``at ==
    observed_at``) ist der erste Messpunkt der gesnappte Fix; eine Abfrage
    VOR dem Meldezeitpunkt schreibt nicht rueckwaerts fort (Spec: ``at <=
    observed_at`` -> Fix selbst)."""
    uid, tid = _nutzer_mit_trip("ac4-pos")
    meldung, frueher = ortszeit(9, 0), ortszeit(8, 50)
    plan = _position(uid, tid, meldung, user_id=None)
    assert abstand_m(plan, ECHT_HEUTE_KOORD) > _DEUTLICH_M, (
        f"Testaufbau: Planposition {plan} muss deutlich neben dem Fix liegen"
    )

    _record(uid, ECHT_HEUTE_KOORD, meldung)

    pos = _position(uid, tid, meldung)
    assert abstand_m(pos, ECHT_HEUTE_KOORD) <= _SNAP_TOL_M, (
        f"AC-4: position_at_time liefert zum Meldezeitpunkt {pos} statt des Fixes "
        f"{ECHT_HEUTE_KOORD} (Planposition waere {plan})"
    )
    pos_frueher = _position(uid, tid, frueher)
    assert abstand_m(pos_frueher, ECHT_HEUTE_KOORD) <= _SNAP_TOL_M, (
        f"AC-4: Abfrage vor dem Meldezeitpunkt liefert {pos_frueher} statt des Fixes "
        f"(rueckwaerts fortgeschrieben?)"
    )


def test_ac4_spaetere_abfrage_ist_um_den_planfortschritt_fortgeschrieben():
    """AC-4, zweiter Halbsatz: Fix 09:00, Abfrage 12:00 -> Fix + 3 h
    Plan-Tempo (~4,2 km) entlang der Strecke, NICHT der eingefrorene Fix.
    (12:00 statt 14:00: mit dem echten Fix laege 14:00 nur ~55 m vor dem
    Etappenende und waere von der Begrenzung nicht zu unterscheiden.)"""
    uid, tid = _nutzer_mit_trip("ac4-fort")
    meldung, abfrage = ortszeit(9, 0), ortszeit(12, 0)
    erwartet = fortgeschrieben(ECHT_HEUTE_KOORD[0], meldung, abfrage)
    _unterscheidbar(erwartet, fix=ECHT_HEUTE_KOORD, at=abfrage)
    plan = _position(uid, tid, abfrage, user_id=None)
    assert abstand_m(plan, planposition(abfrage)) <= _SNAP_TOL_M, (
        f"Testaufbau: geschlossene Planposition {planposition(abfrage)} != Pruefling {plan}"
    )

    _record(uid, ECHT_HEUTE_KOORD, meldung)

    pos = _position(uid, tid, abfrage)
    assert abstand_m(pos, erwartet) <= toleranz_fortschreibung(erwartet, ECHT_HEUTE_KOORD), (
        f"AC-4: Abfrage 12:00 liefert {pos} statt Fix + Planfortschritt {erwartet} -- "
        f"{abstand_m(pos, ECHT_HEUTE_KOORD):.0f} m vom Fix (0 m = eingefroren)"
    )
    assert pos.lat > ECHT_HEUTE_KOORD[0], "AC-4: Position liegt nicht strecken-weiter als der Fix"


def test_ac4_begrenzt_die_fortschreibung_auf_das_etappenende():
    """Fix 09:00 kurz vor dem Ziel (~1,1 km), Abfrage 14:00 (noch im
    Zeitfenster der Etappe, Plan-Ankunft 16:00): Fix + 5 h Plan-Tempo laege
    ~5,8 km HINTER dem Ziel -> begrenzt auf das Etappenende, eine
    Reststrecke gibt es nicht mehr. Nach 16:00 gilt AC-5 (Rueckfall auf die
    Planposition) -- hier mitgeprueft, damit beide Regeln zusammenpassen."""
    uid, tid = _nutzer_mit_trip("ac4-ende", mit_folgetag=True)
    fix = (46.6900, ROUTE_LON)  # Trackpunkt, ~1,1 km vor dem Ziel
    meldung, abfrage, nach_ankunft = ortszeit(9, 0), ortszeit(14, 0), ortszeit(17, 0)
    assert fortgeschrieben(fix[0], meldung, abfrage) == _ZIEL, "Testaufbau: muss begrenzt werden"
    assert abstand_m(fix, _ZIEL) > _DEUTLICH_M and abstand_m(planposition(abfrage), _ZIEL) > _DEUTLICH_M
    nach_ankunft_plan = _quelle(uid, tid, nach_ankunft, user_id=None)

    _record(uid, fix, meldung)

    pos, mit_zeit, _ = _quelle(uid, tid, abfrage)
    assert abstand_m(pos, _ZIEL) <= _SNAP_TOL_M, (
        f"AC-4: Abfrage 14:00 liefert {pos} statt des Etappenendes {_ZIEL} -- "
        f"{abstand_m(pos, fix):.0f} m vom Fix (0 m = eingefroren)"
    )
    assert all(p.lat <= ZIEL_LAT + 1e-9 for p, _t in mit_zeit), f"AC-4: Punkt hinter dem Ziel: {mit_zeit}"
    assert len(mit_zeit) == 1, f"AC-4: am Etappenende gibt es keine Reststrecke: {mit_zeit}"
    assert _quelle(uid, tid, nach_ankunft) == nach_ankunft_plan, (
        "AC-5: nach Etappenende wirkt der Fix noch -- erwartet bit-identisch zur Planposition"
    )


def test_ac4_folgepunkte_laufen_ab_der_fortgeschriebenen_position():
    """Fix 09:00, Abfrage 10:00: erster Punkt = Fix + 1 h Plan-Tempo
    (~46.6495), Folgepunkte im Abstand ``RADAR_ZONE_POINT_SPACING_KM``
    entlang der Reststrecke AB DORT -- 3 Punkte (ab dem eingefrorenen Fix
    waeren es 4, ab der Planposition ebenfalls andere)."""
    uid, tid = _nutzer_mit_trip("ac4-folge")
    meldung, abfrage = ortszeit(9, 0), ortszeit(10, 0)
    start = fortgeschrieben(ECHT_HEUTE_KOORD[0], meldung, abfrage)
    _unterscheidbar(start, fix=ECHT_HEUTE_KOORD, at=abfrage)

    def _anzahl(ab) -> int:
        rest_km = abstand_m(ab, _ZIEL) / 1000.0
        return min(RADAR_ZONE_MAX_POINTS, int(rest_km // RADAR_ZONE_POINT_SPACING_KM) + 1)

    erwartet = _anzahl(start)
    assert erwartet >= 2 and erwartet != _anzahl(ECHT_HEUTE_KOORD), "Testaufbau: Anzahl muss unterscheiden"
    _, plan_punkte, _ = _quelle(uid, tid, abfrage, user_id=None)

    _record(uid, ECHT_HEUTE_KOORD, meldung)

    _, punkte_mit_zeit, _ = _quelle(uid, tid, abfrage)
    punkte = [p for p, _t in punkte_mit_zeit]
    assert punkte != [p for p, _t in plan_punkte], "AC-4: Folgepunkte unveraendert ab Planposition"
    assert abstand_m(punkte[0], start) <= toleranz_fortschreibung(start, ECHT_HEUTE_KOORD), (
        f"AC-4: erster Punkt {punkte[0]} statt der fortgeschriebenen Position {start} -- "
        f"{abstand_m(punkte[0], ECHT_HEUTE_KOORD):.0f} m vom Fix (0 m = eingefroren)"
    )
    assert len(punkte) == erwartet, (
        f"AC-4: {len(punkte)} Punkte statt {erwartet} fuer die Reststrecke ab {start}"
    )
    for vorher, p in zip(punkte, punkte[1:]):
        assert abstand_m(p, (p.lat, ROUTE_LON)) <= _SNAP_TOL_M, f"Folgepunkt {p} nicht auf der Strecke"
        assert vorher.lat < p.lat <= ZIEL_LAT + 1e-9, "Folgepunkte laufen nicht Richtung Ziel"
        assert abstand_m(vorher, p) == pytest.approx(RADAR_ZONE_POINT_SPACING_KM * 1000.0, abs=50.0)


def test_ac8_eine_positionsquelle_fuer_alle_pfade():
    """Briefing/Befehl (``position_at_time``), Alarm/Radar
    (``points_with_passage_times``) und ``strecke``
    (``points_along_remaining_route``) liefern denselben ersten Punkt -- auch
    bei SPAETERER Abfrage die fortgeschriebene Position (eine Quelle, die nur
    in einem der Pfade fortschreibt, fiele hier auf). Keine kanalspezifische
    Positionslogik."""
    uid, tid = _nutzer_mit_trip("ac8")
    meldung, abfrage = ortszeit(9, 0), ortszeit(12, 0)
    erwartet = fortgeschrieben(ECHT_HEUTE_KOORD[0], meldung, abfrage)
    _record(uid, ECHT_HEUTE_KOORD, meldung)

    pos, mit_zeit, entlang = _quelle(uid, tid, abfrage)
    assert mit_zeit[0][0] == pos == entlang[0]
    assert abstand_m(pos, erwartet) <= toleranz_fortschreibung(erwartet, ECHT_HEUTE_KOORD), (
        f"AC-8/AC-4: gemeinsamer erster Punkt {pos} statt {erwartet} -- "
        f"{abstand_m(pos, ECHT_HEUTE_KOORD):.0f} m vom Fix (0 m = eingefroren)"
    )
    pos_m, mit_zeit_m, entlang_m = _quelle(uid, tid, meldung)
    assert mit_zeit_m[0][0] == pos_m == entlang_m[0]
    assert abstand_m(pos_m, ECHT_HEUTE_KOORD) <= _SNAP_TOL_M


class _TrockeneQuelle:
    """Echter ``frame_source`` (kein Mock): liefert keine Frames (trocken),
    damit kein Alarm entsteht -- gemessen wird nur, WO abgefragt wird."""

    def __init__(self) -> None:
        self.calls: list[tuple[float, float]] = []

    def __call__(self, lat: float, lon: float) -> list:
        self.calls.append((lat, lon))
        return []


def _radarlauf(uid: str, jetzt) -> list[dict]:
    from services.trip_alert import TripAlertService

    reset_radar_cache()
    dienst = aufzeichnender_radar_dienst(_TrockeneQuelle())
    mails: list = []
    with freeze_time(jetzt):
        TripAlertService(
            settings=settings_email_only(), user_id=uid, throttle_hours=2,
            radar_service=dienst, mail_sink=lambda s, b: mails.append((s, b)),
        ).check_radar_alerts()
    assert dienst.calls, "Testaufbau: der Alarmlauf hat keinen Nowcast abgerufen"
    return dienst.calls


def test_ac4_radar_misst_an_der_fortgeschriebenen_position_im_echten_alarmlauf():
    """Konsumenten-Nachweis durch den ECHTEN ``check_radar_alerts()``: der
    Alarmlauf misst zur Zeit ``jetzt + RADAR_MEASURE_OFFSET_MIN`` (also immer
    NACH der Meldung) -- der erste Nowcast-Abruf liegt deshalb am Fix plus
    Planfortschritt seit der Meldung, weder an der Planposition noch am
    eingefrorenen Fix."""
    from services import radar_service as radar_service_mod

    # Kontrolle als EIGENER Nutzer mit identischem Trip: ein zweiter Alarmlauf
    # desselben Nutzers misst wegen Laufzustand (Stempel) andere Punkte --
    # gemessen 26.10. -- und taugte deshalb nicht als Vorher-Wert.
    kontrolle, _ = _nutzer_mit_trip("ac4-radar-kontrolle")
    uid, _tid = _nutzer_mit_trip("ac4-radar")
    meldung, jetzt = ortszeit(8, 30), ortszeit(9, 0)
    gemessen_um = jetzt + timedelta(minutes=radar_service_mod.RADAR_MEASURE_OFFSET_MIN)
    erwartet = fortgeschrieben(ECHT_HEUTE_KOORD[0], meldung, gemessen_um)
    _unterscheidbar(erwartet, fix=ECHT_HEUTE_KOORD, at=gemessen_um)
    ohne_fix = _radarlauf(kontrolle, jetzt)[0]
    assert abstand_m((ohne_fix["lat"], ohne_fix["lon"]), erwartet) > _DEUTLICH_M, (
        f"Testaufbau: ohne Fix muss der Messpunkt deutlich neben dem Soll liegen: {ohne_fix}"
    )

    _record(uid, ECHT_HEUTE_KOORD, meldung, jetzt=jetzt)

    mit_fix = _radarlauf(uid, jetzt)[0]  # erster Lauf DIESES Nutzers
    ist = (mit_fix["lat"], mit_fix["lon"])
    assert abstand_m(ist, erwartet) <= toleranz_fortschreibung(erwartet, ECHT_HEUTE_KOORD), (
        f"AC-4: Nowcast-Abruf an {mit_fix} statt an Fix + Planfortschritt {erwartet} -- "
        f"{abstand_m(ist, ECHT_HEUTE_KOORD):.0f} m vom Fix (0 m = eingefroren; ohne Fix: {ohne_fix})"
    )


# ═══════════════ AC-4: Fortschreibung -- Raender und Segmente ═══════════════
#
# Adversary-Durchgang 2 (F001-F005, F008): die Fortschreibung haengt an den
# SEGMENTZEITEN der Etappe. Sollwerte geschlossen ueber ``planzeit_bei`` /
# ``plan_lat_bei`` (Fahrplan -> Breite, Meridian-Geometrie), nie ueber den
# Pruefling.

_FAHRPLAN_EINS = ((START_LAT, START_ZEIT), (ZIEL_LAT, ZIEL_ZEIT))
_ZEIT_TOL_S = 60.0


def _nutzer_mit_fahrplan(tag: str, fahrplan):
    uid = _uid(tag)
    tid = f"trip-2327-{uuid.uuid4().hex[:6]}"
    gpx_schreiben(uid, "heute", heute_track_punkte())
    trip_schreiben_fahrplan(uid, tid, fahrplan)
    return uid, tid


def _aktives_segment(uid, tid, at):
    trip = lade_trip(uid, tid)
    with freeze_time(at):
        active, _ = resolve_current_segment(trip, at, at.astimezone(ZONE).date())
    return active


def test_ac4_fortschreibung_hinter_das_etappenende_ist_exakt_der_zielpunkt():
    """F001: Fix 09:00 kurz vor dem Ziel, Abfrage 14:00 (bewegtes Segment
    noch aktiv) -> Position ist EXAKT der Ziel-Wegpunkt, nicht nur in seiner
    Naehe; die einzige Durchgangszeit ist die Abfragezeit."""
    uid, tid = _nutzer_mit_trip("f001-ziel")
    meldung, abfrage = ortszeit(9, 0), ortszeit(14, 0)
    assert isinstance(_aktives_segment(uid, tid, abfrage).segment_id, int)

    _record(uid, (46.6900, ROUTE_LON), meldung)

    pos, mit_zeit, entlang = _quelle(uid, tid, abfrage)
    assert (pos.lat, pos.lon) == (ZIEL_LAT, ROUTE_LON), f"F001: {pos} ist nicht exakt das Ziel"
    assert mit_zeit == [(pos, abfrage)] and entlang == [pos]


def test_ac4_planzeit_in_einer_rast_steht_am_rastort():
    """F002: Fix 09:00 bei 46.645 (Planzeit 09:48), Abfrage 09:15 ->
    Planzeit 10:03 faellt in die Rast (10:00-11:00, Segment ohne Strecke).
    Soll: Position am Rastort, Reststrecke und -zeit ab dort (nicht davor):
    3 Punkte, Durchgangszeiten = Planzeiten ab 11:00, auf 09:15 verschoben."""
    uid, tid = _nutzer_mit_fahrplan("f002-rast", FAHRPLAN_RAST)
    meldung, abfrage = ortszeit(9, 0), ortszeit(9, 15)
    fix = (46.6450, ROUTE_LON)
    planzeit = planzeit_bei(FAHRPLAN_RAST, fix[0]) + (abfrage - meldung)
    assert ortszeit(10, 0) < planzeit < ortszeit(11, 0), "Testaufbau: Planzeit muss in der Rast liegen"
    assert isinstance(_aktives_segment(uid, tid, abfrage).segment_id, int)

    _record(uid, fix, meldung)

    pos, mit_zeit, _ = _quelle(uid, tid, abfrage)
    assert abstand_m(pos, (GAP_NORD_LAT, ROUTE_LON)) <= _SNAP_TOL_M, f"F002: {pos} nicht am Rastort"
    assert len(mit_zeit) == 3, f"F002: {len(mit_zeit)} Punkte -- Reststrecke nicht ab dem Rastort: {mit_zeit}"
    assert mit_zeit[0][1] == abfrage
    for p, t in mit_zeit[1:]:  # hinter dem Rastort: Planzeit ab Rast-Ende 11:00
        soll = abfrage + (planzeit_bei(FAHRPLAN_RAST, p.lat) - ortszeit(11, 0))
        assert abs((t - soll).total_seconds()) <= _ZEIT_TOL_S, f"F002: Durchgang {t} statt {soll} bei {p}"


def test_ac4_durchgangszeiten_ab_dem_fix_folgen_der_planrestzeit():
    """F003: Fix 09:00 (Planzeit ~10:58, also voraus), Abfrage 10:00. Erster
    Punkt um 10:00, danach streng steigend; jeder Durchgang = Abfragezeit +
    Planzeit-Abstand des Punkts zur fortgeschriebenen Planzeit -- nicht die
    Wanduhr-Restzeit bis zur Plan-Ankunft und nicht die volle Segmentdauer."""
    uid, tid = _nutzer_mit_trip("f003-zeit")
    meldung, abfrage = ortszeit(9, 0), ortszeit(10, 0)
    planzeit = planzeit_bei(_FAHRPLAN_EINS, ECHT_HEUTE_KOORD[0]) + (abfrage - meldung)

    _record(uid, ECHT_HEUTE_KOORD, meldung)

    _, mit_zeit, _ = _quelle(uid, tid, abfrage)
    assert len(mit_zeit) >= 2, f"Testaufbau: zu wenige Punkte {mit_zeit}"
    zeiten = [t for _p, t in mit_zeit]
    assert zeiten[0] == abfrage, f"F003: erster Punkt um {zeiten[0]} statt {abfrage}"
    assert all(a < b for a, b in zip(zeiten, zeiten[1:])), f"F003: Zeiten nicht steigend {zeiten}"
    assert zeiten[-1] <= ortszeit(16, 0) + (abfrage - planzeit) + timedelta(seconds=_ZEIT_TOL_S)
    for p, t in mit_zeit:
        soll = abfrage + (planzeit_bei(_FAHRPLAN_EINS, p.lat) - planzeit)
        assert abs((t - soll).total_seconds()) <= _ZEIT_TOL_S, f"F003: Durchgang {t} statt {soll} bei {p}"


@pytest.mark.parametrize(
    "fix_lat, meldung, abfrage",
    [
        pytest.param(46.6700, (9, 0), (9, 30), id="fix_auf_spaetem_segment"),
        pytest.param(46.6450, (9, 0), (10, 0), id="sprung_ins_folgesegment"),
        pytest.param(46.6200, (8, 30), (8, 45), id="innerhalb_des_ersten_segments"),
    ],
)
def test_ac4_mehrsegment_fortschreibung_folgt_den_segmentzeiten(fix_lat, meldung, abfrage):
    """F004/F005: zwei bewegte Segmente mit verschiedenem Tempo (08-10 Uhr
    schnell, 10-16 Uhr langsam). Der Fix wird auf das NAECHSTGELEGENE Segment
    projiziert (auch ein spaeteres als das aktive), seine Planzeit laeuft um
    den Vorlauf weiter und darf ins Folgesegment springen."""
    uid, tid = _nutzer_mit_fahrplan("f004", FAHRPLAN_ZWEI)
    meldung, abfrage = ortszeit(*meldung), ortszeit(*abfrage)
    planzeit = planzeit_bei(FAHRPLAN_ZWEI, fix_lat) + (abfrage - meldung)
    soll = (plan_lat_bei(FAHRPLAN_ZWEI, planzeit), ROUTE_LON)
    for name, falsch in (("Fix", (fix_lat, ROUTE_LON)), ("Zwischenpunkt", (GAP_NORD_LAT, ROUTE_LON)),
                         ("Ziel", _ZIEL)):
        assert abstand_m(soll, falsch) > 300.0, f"Testaufbau: Soll {soll} zu nah an {name}"

    _record(uid, (fix_lat, ROUTE_LON), meldung)

    pos = _position(uid, tid, abfrage)
    assert abstand_m(pos, soll) <= toleranz_fortschreibung(soll, (fix_lat, ROUTE_LON)), (
        f"F004: {pos} statt {soll} (Planzeit {planzeit.astimezone(ZONE):%H:%M})"
    )


def test_ac4_fix_genau_im_plan_schreibt_wie_die_planposition_fort():
    """F002 (Segmentrand): Fix 08:00 am Start = Planposition. Jede spaetere
    Abfrage muss dann die Planposition samt Folgepunkten liefern -- auch
    10:00, wo die Planzeit EXAKT auf dem Ende des ersten Segments liegt
    (dort hat die Planposition keine Reststrecke im aktiven Segment)."""
    uid, tid = _nutzer_mit_fahrplan("f002-rand", FAHRPLAN_ZWEI)
    meldung = ortszeit(8, 0)
    abfragen = (ortszeit(9, 0), ortszeit(10, 0), ortszeit(12, 0))
    plaene = [_quelle(uid, tid, at, user_id=None)[1] for at in abfragen]

    _record(uid, (START_LAT, ROUTE_LON), meldung)

    for at, plan in zip(abfragen, plaene):
        ist = _quelle(uid, tid, at)[1]
        assert len(ist) == len(plan), f"F002 {at:%H:%M}: {ist} statt {plan}"
        for (p, t), (q, u) in zip(ist, plan):
            assert abstand_m(p, q) <= _SNAP_TOL_M and abs((t - u).total_seconds()) <= _ZEIT_TOL_S, (
                f"F002 {at:%H:%M}: {(p, t)} statt Planpunkt {(q, u)}"
            )


def test_ac4_zum_meldezeitpunkt_gilt_der_fix_auf_dem_track_nicht_auf_der_wegpunktlinie():
    """F007: der Track macht zwischen den Wegpunkten einen Knick 80 m
    neben die Wegpunkt-Linie; der Fix liegt genau im Knick. Bei Abfrage zum
    Meldezeitpunkt und davor ist der erste Punkt der Fix selbst -- nicht sein
    Lot auf die gerade Linie zwischen den Wegpunkten."""
    uid = _uid("f007-knick")
    tid = f"trip-2327-{uuid.uuid4().hex[:6]}"
    knick = punkt_neben_route(GAP_NORD_LAT, 80.0)
    punkte = [knick if round(lat, 4) == GAP_NORD_LAT else (lat, ROUTE_LON)
              for lat in (round(START_LAT + i * 0.01, 4) for i in range(11))]
    gpx_schreiben(uid, "knick", punkte)
    trip_schreiben(uid, tid)
    meldung = ortszeit(9, 0)

    _record(uid, knick, meldung)

    assert fix_datei(uid).exists(), "Testaufbau: Fix im Knick wurde nicht gespeichert"
    for at in (meldung, ortszeit(8, 50)):
        pos = _position(uid, tid, at)
        assert abstand_m(pos, knick) <= _SNAP_TOL_M, (
            f"F007 {at:%H:%M}: {pos} statt des Fixes {knick} (Lot auf die Wegpunkt-Linie?)"
        )


def test_ac4_fix_wirkt_auch_waehrend_einer_geplanten_rast():
    """Rast-Fall (Spec AC-5 nennt als Rueckfall NUR Etappenende und
    Tageswechsel): Rast 10:00-11:00 am Zwischenpunkt (Segment ohne Strecke).
    Der Wanderer ist hinter dem Plan -- Fix 10:15 bei 46.62, waehrend der
    Plan ihn in der Rast sieht. Abfrage 10:30 (aktiv: Rast-Segment) -> Fix +
    15 min Plan-Tempo (46.62625), NICHT der Rastort der Planposition."""
    uid, tid = _nutzer_mit_fahrplan("rast-fix", FAHRPLAN_RAST)
    meldung, abfrage = ortszeit(10, 15), ortszeit(10, 30)
    fix = (46.6200, ROUTE_LON)
    aktiv = _aktives_segment(uid, tid, abfrage)
    assert isinstance(aktiv.segment_id, int) and aktiv.distance_km == 0.0, (
        f"Testaufbau: um 10:30 muss das Rast-Segment aktiv sein, ist {aktiv.segment_id}"
    )
    planzeit = planzeit_bei(FAHRPLAN_RAST, fix[0]) + (abfrage - meldung)
    soll = (plan_lat_bei(FAHRPLAN_RAST, planzeit), ROUTE_LON)
    plan = _position(uid, tid, abfrage, user_id=None)
    assert abstand_m(plan, (GAP_NORD_LAT, ROUTE_LON)) <= _SNAP_TOL_M
    assert abstand_m(soll, plan) > _DEUTLICH_M and abstand_m(soll, fix) > 300.0

    _record(uid, fix, meldung)

    pos, mit_zeit, entlang = _quelle(uid, tid, abfrage)
    assert mit_zeit[0][0] == pos == entlang[0]
    assert abstand_m(pos, soll) <= toleranz_fortschreibung(soll, fix), (
        f"Rast: {pos} statt Fix + Planfortschritt {soll} (Planposition Rastort: {plan})"
    )


def test_ac5_fix_nach_der_plan_ankunft_wirkt_nicht_auf_das_ziel_segment():
    """F008: Fix 16:30 (Plan-Ankunft 16:00) auf der Strecke vor dem Ziel.
    Abfrage 16:30 -- aktiv ist das Ziel-Segment -> bit-identisch zur
    Planposition. Positive Kontrolle: um 15:30 (bewegtes Segment, vor der
    Meldung) wirkt derselbe Fix."""
    uid, tid = _nutzer_mit_trip("f008-ziel")
    meldung, vorher = ortszeit(16, 30), ortszeit(15, 30)
    fix = (46.6900, ROUTE_LON)
    assert not isinstance(_aktives_segment(uid, tid, meldung).segment_id, int)
    plan = _quelle(uid, tid, meldung, user_id=None)

    _record(uid, fix, meldung)

    assert fix_datei(uid).exists(), "Testaufbau: Fix wurde nicht gespeichert"
    assert abstand_m(_position(uid, tid, vorher), fix) <= _SNAP_TOL_M, "Kontrolle: Fix wirkt nicht"
    assert _quelle(uid, tid, meldung) == plan, "F008: Fix wirkt auf das Ziel-Segment"


def test_ac9_ohne_user_id_bleibt_die_planposition_trotz_fix_datei():
    """F008: liegt ein Fix fuer den Trip vor, liefert der Aufruf OHNE
    ``user_id`` trotzdem die Planposition (bit-identisch); mit ``user_id``
    wirkt der Fix (positive Kontrolle)."""
    uid, tid = _nutzer_mit_trip("f008-ohne")
    meldung = ortszeit(9, 0)
    plan = _quelle(uid, tid, meldung, user_id=None)

    _record(uid, ECHT_HEUTE_KOORD, meldung)

    assert abstand_m(_position(uid, tid, meldung), ECHT_HEUTE_KOORD) <= _SNAP_TOL_M
    assert _quelle(uid, tid, meldung, user_id=None) == plan


# ══════════════════════════════════ AC-5 ══════════════════════════════════


def _fix_wirkt_mittags(uid, tid) -> None:
    """Positive Kontrolle: mitten in der Etappe gilt der Fix (Abfrage zum
    Meldezeitpunkt -- AC-5 prueft den Rueckfall, nicht die Fortschreibung)."""
    _record(uid, ECHT_HEUTE_KOORD, ortszeit(9, 30), jetzt=ortszeit(10, 0))
    assert abstand_m(_position(uid, tid, ortszeit(9, 30)), ECHT_HEUTE_KOORD) <= _SNAP_TOL_M


def test_ac5_nach_etappenende_bitidentisch_zum_lauf_ohne_fix():
    uid, tid = _nutzer_mit_trip("ac5-ende", mit_folgetag=True)
    nach_ankunft = ortszeit(17, 0)  # Ankunft 16:00 -> Ziel-Segment aktiv
    vorher = _quelle(uid, tid, nach_ankunft, user_id=None)

    _fix_wirkt_mittags(uid, tid)

    assert _quelle(uid, tid, nach_ankunft) == vorher, (
        "AC-5: nach Etappenende wirkt der Fix noch -- erwartet bit-identisch zur Planposition"
    )


def test_ac5_am_folgetag_bitidentisch_zum_lauf_ohne_fix():
    from datetime import timedelta

    uid, tid = _nutzer_mit_trip("ac5-folgetag", mit_folgetag=True)
    folgetag = ortszeit(10, 0, tag=TAG + timedelta(days=1))
    vorher = _quelle(uid, tid, folgetag, user_id=None)

    _fix_wirkt_mittags(uid, tid)

    assert _quelle(uid, tid, folgetag) == vorher, (
        "AC-5: der Fix vom Vortag beeinflusst die naechste Etappe"
    )


# ══════════════════════════════════ AC-6 ══════════════════════════════════

_FIX_VORNE = ECHT_HEUTE_KOORD          # km ~4,1
_FIX_HINTEN = (46.6100, ROUTE_LON)     # km ~1,1, hinter _FIX_VORNE


def test_ac6_neuerer_fix_gewinnt_auch_rueckwaerts():
    """Abfragen je zum Meldezeitpunkt des geltenden Fixes (AC-6 prueft die
    Reihenfolge, nicht die Fortschreibung). Der HINTERE Fix ist 09:45
    gemeldet: dort liegt die Planposition ~1,3 km entfernt (um 09:30 waeren
    es nur ~970 m)."""
    uid, tid = _nutzer_mit_trip("ac6-rueck")
    t_vorne, t_hinten = ortszeit(9, 0), ortszeit(9, 45)
    assert abstand_m(_position(uid, tid, t_hinten, user_id=None), _FIX_HINTEN) > _DEUTLICH_M

    _record(uid, _FIX_VORNE, t_vorne, jetzt=ortszeit(9, 50))
    assert abstand_m(_position(uid, tid, t_vorne), _FIX_VORNE) <= _SNAP_TOL_M
    _record(uid, _FIX_HINTEN, t_hinten, jetzt=ortszeit(9, 50))

    assert abstand_m(_position(uid, tid, t_hinten), _FIX_HINTEN) <= _SNAP_TOL_M, (
        "AC-6: der neuere Fix (rueckwaerts auf der Strecke) gilt nicht"
    )


def test_ac6_aelterer_eintrag_ueberschreibt_juengeren_nicht():
    uid, tid = _nutzer_mit_trip("ac6-alt")
    abfrage = ortszeit(9, 30)  # Meldezeitpunkt des juengeren (geltenden) Fixes

    _record(uid, _FIX_HINTEN, ortszeit(9, 30), jetzt=ortszeit(9, 40))
    assert fix_datei(uid).exists()
    stand = fix_datei(uid).read_bytes()
    _record(uid, _FIX_VORNE, ortszeit(9, 0), jetzt=ortszeit(9, 40))

    assert fix_datei(uid).read_bytes() == stand, (
        "AC-6: ein aelterer Journal-Eintrag hat den juengeren Fix ueberschrieben"
    )
    assert abstand_m(_position(uid, tid, abfrage), _FIX_HINTEN) <= _SNAP_TOL_M


# ══════════════════════════════════ AC-7 ══════════════════════════════════


def test_ac7_eindeutige_strecke_wirkt_nur_auf_diesen_trip():
    uid, t1 = _nutzer_mit_trip("ac7-eindeutig")
    t2 = f"trip-2327-b-{uuid.uuid4().hex[:6]}"
    gpx_schreiben(uid, "anders", anderer_track_punkte())
    trip_schreiben(uid, t2, route="anders", name="Anderer Trip")
    t2_vorher = _quelle(uid, t2, ortszeit(9, 0), user_id=None)

    _record(uid, ECHT_HEUTE_KOORD, ortszeit(8, 55), jetzt=ortszeit(9, 0))

    assert abstand_m(_position(uid, t1, ortszeit(8, 55)), ECHT_HEUTE_KOORD) <= _SNAP_TOL_M
    assert _quelle(uid, t2, ortszeit(9, 0)) == t2_vorher, "AC-7: Fix wirkt auf den falschen Trip"


def test_ac7_ueberlappende_strecken_verwerfen_den_fix(caplog):
    caplog.set_level(logging.DEBUG)
    uid, t1 = _nutzer_mit_trip("ac7-kreuz")
    t2 = f"trip-2327-x-{uuid.uuid4().hex[:6]}"
    gpx_schreiben(uid, "kreuz", kreuz_track_punkte())
    trip_schreiben(uid, t2, route="kreuz", name="Kreuz-Trip")
    jetzt = ortszeit(9, 0)
    t1_vorher = _quelle(uid, t1, jetzt, user_id=None)
    t2_vorher = _quelle(uid, t2, jetzt, user_id=None)

    _record(uid, ECHT_HEUTE_KOORD, ortszeit(8, 55), jetzt=jetzt)  # liegt auf BEIDEN

    assert _quelle(uid, t1, jetzt) == t1_vorher, "AC-7: mehrdeutiger Fix wirkt auf Trip 1"
    assert _quelle(uid, t2, jetzt) == t2_vorher, "AC-7: mehrdeutiger Fix wirkt auf Trip 2"
    assert not fix_datei(uid).exists(), "AC-7: mehrdeutiger Fix wurde gespeichert"
    assert _logs_aus_position_fix(caplog), "AC-7: verworfener Fix wurde nicht geloggt"

    # Positive Kontrolle: ein Punkt NUR auf Trip 1 wirkt nur dort.
    nur_t1 = (46.6600, ROUTE_LON)
    _record(uid, nur_t1, ortszeit(8, 58), jetzt=jetzt)
    assert abstand_m(_position(uid, t1, ortszeit(8, 58)), nur_t1) <= _SNAP_TOL_M
    assert _quelle(uid, t2, jetzt) == t2_vorher


# ══════════════════════════════════ AC-9 ══════════════════════════════════


def test_ac9_fix_von_a_aendert_nutzer_b_nicht():
    """B hat dieselbe Trip-ID und dieselbe Strecke wie A -- ein Lookup nur
    ueber ``trip.id`` (ohne Nutzer) wuerde hier lecken."""
    gleiche_id = f"trip-2327-gleich-{uuid.uuid4().hex[:6]}"
    uid_a, _ = _nutzer_mit_trip("ac9-a", trip_id=gleiche_id)
    uid_b, _ = _nutzer_mit_trip("ac9-b", trip_id=gleiche_id)
    jetzt = ortszeit(9, 0)
    b_vorher = _quelle(uid_b, gleiche_id, jetzt, user_id=None)
    a_plan = _position(uid_a, gleiche_id, jetzt, user_id=None)

    _record(uid_a, ECHT_HEUTE_KOORD, ortszeit(8, 55), jetzt=jetzt)

    assert abstand_m(_position(uid_a, gleiche_id, ortszeit(8, 55)), ECHT_HEUTE_KOORD) <= _SNAP_TOL_M
    assert _quelle(uid_b, gleiche_id, jetzt) == b_vorher, "AC-9: Fix von A wirkt bei B"
    assert fix_datei(uid_a).exists(), "AC-9: Fix-Datei fehlt unter A"
    assert not fix_datei(uid_b).exists(), "AC-9: Fix-Datei liegt unter B"
    assert not (get_data_dir("default") / "position_fix.json").exists(), "AC-9: Datei unter default"
    # Ohne user_id wird nie nutzeruebergreifend geraten.
    assert _position(uid_a, gleiche_id, jetzt, user_id=None) == a_plan


def test_ac9_ohne_user_id_wird_keine_datei_geschrieben():
    uid, tid = _nutzer_mit_trip("ac9-leer")
    try:
        _record("", ECHT_HEUTE_KOORD, ortszeit(8, 55), jetzt=ortszeit(9, 0))
    except ValueError:
        pass
    assert alle_fix_dateien(get_data_root()) == [], "AC-9: Fix ohne Zuordnung gespeichert"

    # Positive Kontrolle: mit Zuordnung entsteht genau die Datei des Nutzers.
    _record(uid, ECHT_HEUTE_KOORD, ortszeit(8, 55), jetzt=ortszeit(9, 0))
    assert alle_fix_dateien(get_data_root()) == [fix_datei(uid)]


def test_ac9_leere_user_id_faellt_nie_auf_default_zurueck():
    """Adversary F001: ein Nutzer ``default`` MIT Heute-Etappe auf genau dieser
    Strecke -- ein Rueckfall ``""``/``None`` -> ``"default"`` in
    ``record_position_fix`` oder ``load_position_fix`` wuerde hier sichtbar
    (ohne Trip unter ``default`` liefe ein solcher Rueckfall ins Leere)."""
    from services.position_fix import load_position_fix

    tid = f"trip-2327-default-{uuid.uuid4().hex[:6]}"
    gpx_schreiben("default", "heute", heute_track_punkte())
    trip_schreiben("default", tid)
    jetzt = ortszeit(9, 0)
    plan = _quelle("default", tid, jetzt, user_id=None)

    for leer in ("", None):
        try:
            _record(leer, ECHT_HEUTE_KOORD, ortszeit(8, 55), jetzt=jetzt)
        except ValueError:
            pass
    assert alle_fix_dateien(get_data_root()) == [], "AC-9: Fix ohne Zuordnung gespeichert"
    assert _quelle("default", tid, jetzt, user_id="default") == plan, (
        "AC-9: Fix ohne Zuordnung wirkt auf den Trip des Nutzers 'default'"
    )

    # Positive Kontrolle: ein ausdruecklich zugeordneter Fix fuer "default" wirkt --
    # der Aufbau ist also scharf.
    _record("default", ECHT_HEUTE_KOORD, ortszeit(8, 55), jetzt=jetzt)
    assert fix_datei("default").exists()
    assert abstand_m(
        _quelle("default", tid, ortszeit(8, 55), user_id="default")[0], ECHT_HEUTE_KOORD,
    ) <= _SNAP_TOL_M
    assert load_position_fix("default", tid, TAG) is not None

    # Lesen ohne Zuordnung findet die Datei von "default" nie.
    assert load_position_fix("", tid, TAG) is None, "AC-9: leere user_id liest den Fix von 'default'"
    assert load_position_fix(None, tid, TAG) is None, "AC-9: user_id=None liest den Fix von 'default'"
