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
  dieses Etappen-Datum ist der erste Punkt der gesnappte Fix, die
  Folgepunkte laufen wie bei ``points_from_km`` ab der Fortschritts-km
  entlang der Reststrecke (Punktabstand ``RADAR_ZONE_POINT_SPACING_KM``).
  BEGRUENDUNG: ``position_at_time(trip, active, segment_date, at)`` kennt
  heute keinen Nutzer, und ``Trip`` traegt keinen Eigentuemer -- die
  Fix-Datei liegt aber je Nutzer. Ein Lookup nur ueber ``trip.id`` waere ein
  Cross-User-Leck (AC-9 prueft das mit GLEICHER Trip-ID bei zwei Nutzern).
  ACHTUNG: das widerspricht der Spec-Formulierung "keine Aenderung in den
  fuenf Konsumenten" -- die Konsumenten muessen ``user_id`` durchreichen.
  Der Konsumenten-Test ``test_ac4_radar_misst_am_fix_im_echten_alarmlauf``
  geht deshalb durch den ECHTEN ``check_radar_alerts()`` (der besitzt eine
  ``user_id``) und haengt nicht davon ab, WIE der Lookup gebaut wird.
* Verworfene Fixes (zu weit, mehrdeutig) werden aus ``position_fix.py``
  heraus geloggt (geprueft ueber ``record.pathname``, nicht ueber Wortlaut).

RED-GRUND (je Test): ``services.position_fix`` existiert nicht
(``ModuleNotFoundError`` -- Import im Test) bzw. ``position_at_time`` kennt
das Keyword ``user_id`` nicht (``TypeError``) bzw. -- im Radar-Test -- der
Messpunkt bleibt auf der Planposition.

Jeder Verwerfungs-Test traegt eine POSITIVE KONTROLLE im selben Test (ein
plausibler Fix wirkt), damit ein Stub, der nie etwas tut, nicht gruen wird.

AC-8-Mutationsgegenprobe: wird der Fix-Zweig in ``position_at_time``
entfernt, werden ``test_ac4_position_at_time_liefert_den_gesnappten_fix``
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

import pytest
from freezegun import freeze_time

from app.loader import get_data_dir, get_data_root
from services.trip_segments import (
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
    GAP_MITTE_LAT,
    GAP_NORD_LAT,
    GAP_SUED_LAT,
    ROUTE_LON,
    TAG,
    ZIEL_LAT,
    ZONE,
    abstand_m,
    alle_fix_dateien,
    anderer_track_punkte,
    fix_datei,
    gpx_schreiben,
    heute_track_punkte,
    kreuz_track_punkte,
    lade_trip,
    ortszeit,
    punkt_neben_route,
    trip_schreiben,
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
    pos = _position(uid, tid, ortszeit(9, 0))
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
    assert abstand_m(_position(uid, tid, ortszeit(9, 0)), (GAP_MITTE_LAT, ROUTE_LON)) <= _SNAP_TOL_M


def test_ac3_punkt_mitten_auf_dem_langen_abschnitt_wird_akzeptiert():
    """Abstand zur STRECKE, nicht zum naechsten Trackpunkt: der Punkt liegt
    ~2,5 km von beiden Trackpunkten entfernt, aber 0 m von der Strecke."""
    uid, tid = _nutzer_mit_trip("ac3-mitte")
    mitte = (GAP_MITTE_LAT, ROUTE_LON)
    assert abstand_m(mitte, (GAP_SUED_LAT, ROUTE_LON)) > 2000.0

    _record(uid, mitte, ortszeit(8, 55), jetzt=ortszeit(9, 0))

    assert fix_datei(uid).exists()
    assert abstand_m(_position(uid, tid, ortszeit(9, 0)), mitte) <= _SNAP_TOL_M


# ══════════════════════════════════ AC-4 / AC-8 ═══════════════════════════


def test_ac4_position_at_time_liefert_den_gesnappten_fix():
    uid, tid = _nutzer_mit_trip("ac4-pos")
    plan = _position(uid, tid, ortszeit(9, 0), user_id=None)
    assert abstand_m(plan, ECHT_HEUTE_KOORD) > _DEUTLICH_M, (
        f"Testaufbau: Planposition {plan} muss deutlich neben dem Fix liegen"
    )

    _record(uid, ECHT_HEUTE_KOORD, ortszeit(8, 55), jetzt=ortszeit(9, 0))

    pos = _position(uid, tid, ortszeit(9, 0))
    assert abstand_m(pos, ECHT_HEUTE_KOORD) <= _SNAP_TOL_M, (
        f"AC-4: position_at_time liefert {pos} statt des Fixes {ECHT_HEUTE_KOORD} "
        f"(Planposition waere {plan})"
    )


def test_ac4_folgepunkte_laufen_ab_dem_fix_entlang_der_reststrecke():
    uid, tid = _nutzer_mit_trip("ac4-folge")
    _, plan_punkte, _ = _quelle(uid, tid, ortszeit(9, 0), user_id=None)

    _record(uid, ECHT_HEUTE_KOORD, ortszeit(8, 55), jetzt=ortszeit(9, 0))

    _, punkte_mit_zeit, _ = _quelle(uid, tid, ortszeit(9, 0))
    punkte = [p for p, _t in punkte_mit_zeit]
    assert punkte != [p for p, _t in plan_punkte], "AC-4: Folgepunkte unveraendert ab Planposition"
    assert abstand_m(punkte[0], ECHT_HEUTE_KOORD) <= _SNAP_TOL_M
    rest_m = abstand_m(ECHT_HEUTE_KOORD, (ZIEL_LAT, ROUTE_LON))
    erwartet = min(6, int(rest_m / 1000.0 // RADAR_ZONE_POINT_SPACING_KM) + 1)
    assert len(punkte) == erwartet, (
        f"AC-4: {len(punkte)} Punkte statt {erwartet} fuer {rest_m:.0f} m Reststrecke ab dem Fix"
    )
    for vorher, p in zip(punkte, punkte[1:]):
        assert abstand_m(p, (p.lat, ROUTE_LON)) <= _SNAP_TOL_M, f"Folgepunkt {p} nicht auf der Strecke"
        assert vorher.lat < p.lat <= ZIEL_LAT + 1e-9, "Folgepunkte laufen nicht Richtung Ziel"
    assert abstand_m(punkte[0], punkte[1]) == pytest.approx(
        RADAR_ZONE_POINT_SPACING_KM * 1000.0, abs=200.0,
    )


def test_ac8_eine_positionsquelle_fuer_alle_pfade():
    """Briefing/Befehl (``position_at_time``), Alarm/Radar
    (``points_with_passage_times``) und ``strecke``
    (``points_along_remaining_route``) liefern denselben ersten Punkt -- den
    Fix. Keine kanalspezifische Positionslogik."""
    uid, tid = _nutzer_mit_trip("ac8")
    _record(uid, ECHT_HEUTE_KOORD, ortszeit(8, 55), jetzt=ortszeit(9, 0))

    pos, mit_zeit, entlang = _quelle(uid, tid, ortszeit(9, 0))
    assert mit_zeit[0][0] == pos == entlang[0]
    assert abstand_m(pos, ECHT_HEUTE_KOORD) <= _SNAP_TOL_M


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


def test_ac4_radar_misst_am_fix_im_echten_alarmlauf():
    """Konsumenten-Nachweis durch den ECHTEN ``check_radar_alerts()``: der
    erste Nowcast-Abruf liegt am gesnappten Fix, nicht an der Planposition."""
    # Kontrolle als EIGENER Nutzer mit identischem Trip: ein zweiter Alarmlauf
    # desselben Nutzers misst wegen Laufzustand (Stempel) andere Punkte --
    # gemessen 26.10. -- und taugte deshalb nicht als Vorher-Wert.
    kontrolle, _ = _nutzer_mit_trip("ac4-radar-kontrolle")
    uid, _tid = _nutzer_mit_trip("ac4-radar")
    jetzt = ortszeit(9, 0)
    ohne_fix = _radarlauf(kontrolle, jetzt)[0]
    assert abstand_m((ohne_fix["lat"], ohne_fix["lon"]), ECHT_HEUTE_KOORD) > _DEUTLICH_M, (
        f"Testaufbau: ohne Fix muss der Messpunkt deutlich neben dem Fix liegen: {ohne_fix}"
    )

    _record(uid, ECHT_HEUTE_KOORD, ortszeit(8, 55), jetzt=jetzt)

    mit_fix = _radarlauf(uid, jetzt)[0]  # erster Lauf DIESES Nutzers
    assert abstand_m((mit_fix["lat"], mit_fix["lon"]), ECHT_HEUTE_KOORD) <= _SNAP_TOL_M, (
        f"AC-4: Nowcast-Abruf an {mit_fix} statt am Fix {ECHT_HEUTE_KOORD} "
        f"(ohne Fix: {ohne_fix})"
    )


# ══════════════════════════════════ AC-5 ══════════════════════════════════


def _fix_wirkt_mittags(uid, tid) -> None:
    """Positive Kontrolle: mitten in der Etappe gilt der Fix."""
    _record(uid, ECHT_HEUTE_KOORD, ortszeit(9, 30), jetzt=ortszeit(10, 0))
    assert abstand_m(_position(uid, tid, ortszeit(10, 0)), ECHT_HEUTE_KOORD) <= _SNAP_TOL_M


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
    uid, tid = _nutzer_mit_trip("ac6-rueck")
    abfrage = ortszeit(9, 45)
    assert abstand_m(_position(uid, tid, abfrage, user_id=None), _FIX_HINTEN) > _DEUTLICH_M

    _record(uid, _FIX_VORNE, ortszeit(9, 0), jetzt=ortszeit(9, 40))
    assert abstand_m(_position(uid, tid, abfrage), _FIX_VORNE) <= _SNAP_TOL_M
    _record(uid, _FIX_HINTEN, ortszeit(9, 30), jetzt=ortszeit(9, 40))

    assert abstand_m(_position(uid, tid, abfrage), _FIX_HINTEN) <= _SNAP_TOL_M, (
        "AC-6: der neuere Fix (rueckwaerts auf der Strecke) gilt nicht"
    )


def test_ac6_aelterer_eintrag_ueberschreibt_juengeren_nicht():
    uid, tid = _nutzer_mit_trip("ac6-alt")
    abfrage = ortszeit(9, 45)

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

    assert abstand_m(_position(uid, t1, ortszeit(9, 0)), ECHT_HEUTE_KOORD) <= _SNAP_TOL_M
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
    assert abstand_m(_position(uid, t1, jetzt), nur_t1) <= _SNAP_TOL_M
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

    assert abstand_m(_position(uid_a, gleiche_id, jetzt), ECHT_HEUTE_KOORD) <= _SNAP_TOL_M
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
