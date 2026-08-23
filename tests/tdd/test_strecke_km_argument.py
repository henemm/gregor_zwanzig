"""TDD RED — Issue #2051 Scheibe S4: optionales km-Argument von `/strecke`
(E5) -- neue Punktbildung `points_from_km()`, Bereichspruefung, Dezimalwerte.

SPEC: docs/specs/modules/feat_2051_s4_strecke_kommando.md — AC-13, AC-14,
AC-15, AC-16.

RED-Ursache: `services.trip_segments.points_from_km` existiert noch nicht ->
ImportError; `TripCommandProcessor._show_strecke` existiert noch nicht ->
AttributeError.

Mock-frei: echte `Trip`/`TripSegment`-Aufloesung
(`tests/helpers/strecke_fixtures.py::active_three_point_trip`, echte
`resolve_current_segment()`), echte aufzeichnende `RadarNowcastService`-
Unterklasse fuer den Nowcast-Spion (kein `Mock()`/`patch()`).
"""
from __future__ import annotations

from datetime import datetime, timezone

from services.trip_command_processor import TripCommandProcessor
from services.trip_segments import resolve_current_segment
from tests.helpers.strecke_fixtures import (
    active_three_point_trip,
    fresh_trip_id,
    nass,
    recording_radar_service_type,
)

_KANAL = "telegram"


def _aktives_segment(trip):
    """`(active, segment_date)` fuer den 'jetzt' der Fixture --
    `active_three_point_trip()` legt Segment 2 (WP1->WP2) als echt
    zeitaktiv an."""
    now_utc = datetime.now(timezone.utc)
    resolved = resolve_current_segment(trip, now_utc, trip.stages[0].date)
    assert resolved is not None, (
        "Testvoraussetzung: die Fixture muss ein aktives Segment liefern"
    )
    return resolved


# --------------------------------------------------------------------------
# AC-13: der erste Punkt liegt bei der GENANNTEN km-Zahl, nicht an der
#        Planposition.
# --------------------------------------------------------------------------

def test_ac13_erster_punkt_liegt_bei_der_genannten_km_zahl():
    """AC-13 GIVEN ein aktives Segment mit start_point.km=3.0,
    end_point.km=8.0, distance_measured=True UND dem Kommando '/strecke 5'
    WHEN die Abfragepunkte gebildet werden THEN liegt der ERSTE Punkt bei
    distance_from_start_km == 5.0 -- NICHT an der ueber position_at_time
    bestimmten Planposition."""
    from services.trip_segments import points_from_km

    trip_id = fresh_trip_id("ac13")
    trip = active_three_point_trip(trip_id, 3.0, 8.0)
    active, segment_date = _aktives_segment(trip)
    assert active.start_point.distance_from_start_km == 3.0, (
        f"Testvoraussetzung: start_point muss km 3.0 tragen, erhalten "
        f"{active.start_point.distance_from_start_km}"
    )
    assert active.end_point.distance_from_start_km == 8.0, (
        f"Testvoraussetzung: end_point muss km 8.0 tragen, erhalten "
        f"{active.end_point.distance_from_start_km}"
    )
    assert active.distance_measured is True, "Testvoraussetzung: distance_measured muss True sein"

    punkte = points_from_km(trip, active, segment_date, 5.0)

    assert punkte[0].distance_from_start_km == 5.0, (
        f"AC-13: der erste Punkt muss bei km 5.0 liegen (dem genannten "
        f"Argument), erhalten km {punkte[0].distance_from_start_km}"
    )
    # Gegenprobe "Form statt Wert": die Planposition (Segmentmitte/-anfang,
    # NICHT km 5) darf hier nicht durchscheinen.
    assert punkte[0].distance_from_start_km != active.start_point.distance_from_start_km, (
        "AC-13: der erste Punkt darf NICHT am Segmentanfang (km 3.0) liegen"
    )


# --------------------------------------------------------------------------
# AC-14: km == end_point-km (oberer Rand eingeschlossen) -> genau 1 Punkt,
#        gueltige, entartete Anfrage, KEINE Fehlermeldung.
# --------------------------------------------------------------------------

def test_ac14_oberer_rand_ist_eingeschlossen_und_ergibt_einen_punkt(monkeypatch):
    """AC-14 GIVEN dasselbe Segment wie AC-13, Kommando '/strecke 8' (exakt
    end_point-km) WHEN verarbeitet wird THEN entsteht GENAU EIN Punkt bei km
    8.0 (Reststrecke=0 innerhalb des Segments) -- gueltige, wenn auch
    entartete Anfrage, KEINE Fehlermeldung."""
    from services.trip_segments import points_from_km

    trip_id = fresh_trip_id("ac14")
    trip = active_three_point_trip(trip_id, 3.0, 8.0)
    active, segment_date = _aktives_segment(trip)

    punkte = points_from_km(trip, active, segment_date, 8.0)
    assert len(punkte) == 1, (
        f"AC-14: erwartet genau 1 Punkt bei km==end_point, erhalten "
        f"{len(punkte)}: {punkte!r}"
    )
    assert punkte[0].distance_from_start_km == 8.0, (
        f"AC-14: der eine Punkt muss bei km 8.0 liegen, erhalten "
        f"{punkte[0].distance_from_start_km}"
    )

    # Draht-Test: `_show_strecke` selbst darf hier KEINE Fehlermeldung
    # liefern -- der obere Rand ist eine gueltige, entartete Anfrage.
    now_utc = datetime.now(timezone.utc)
    calls: list = []
    monkeypatch.setattr(
        "services.radar_service.RadarNowcastService",
        recording_radar_service_type(calls, script=lambda idx: nass(10, 20)),
    )
    result = TripCommandProcessor()._show_strecke(trip, "8", now_utc, trip_id, _KANAL)
    assert result.success is True, (
        f"AC-14: der obere Rand ist eine gueltige Anfrage, "
        f"result.success muss True sein, war {result.success} -- "
        f"Antwort: {result.confirmation_body!r}"
    )
    assert "Ungültige km-Angabe" not in result.confirmation_body, (
        f"AC-14: keine Fehlermeldung erwartet -- Antwort:\n"
        f"{result.confirmation_body}"
    )


# --------------------------------------------------------------------------
# F005 (Adversary-Befund team-lead): AC-14 deckt nur den OBEREN Rand des
# gueltigen Bereichs -- kein Test nutzt den unteren Rand
# (start_point-km) als GUELTIGES Argument. Kippunkt UND je ein Wert knapp
# innerhalb/ausserhalb, damit eine verschobene Grenze (nicht nur ein
# vertauschtes >=/>) auffiele.
# --------------------------------------------------------------------------

def test_f005_unterer_rand_ist_eingeschlossen_und_ergibt_reguläre_punkte(monkeypatch):
    """F005 GIVEN dasselbe Segment wie AC-13/AC-14 (gueltiger Bereich 3-8 km)
    WHEN '/strecke 3' (exakt start_point-km, Kippunkt) UND '/strecke 3.01'
    (knapp innerhalb) verarbeitet werden THEN sind BEIDE gueltige Anfragen
    (kein 'Ungültige km-Angabe'), waehrend '/strecke 2.99' (knapp
    ausserhalb) weiterhin abgelehnt wird."""
    from services.trip_segments import points_from_km

    trip_id = fresh_trip_id("f005")
    trip = active_three_point_trip(trip_id, 3.0, 8.0)
    active, segment_date = _aktives_segment(trip)

    # Kippunkt exakt am unteren Rand: regulaerer (nicht entarteter) Fall,
    # da die Reststrecke im Segment (5 km) ueber der Punktabstand-Schwelle
    # liegt -- anders als AC-14, das entartet auf 1 Punkt zurueckfaellt.
    punkte = points_from_km(trip, active, segment_date, 3.0)
    assert punkte[0].distance_from_start_km == 3.0, (
        f"F005: der erste Punkt muss exakt bei km 3.0 liegen (unterer "
        f"Rand), erhalten {punkte[0].distance_from_start_km}"
    )
    assert len(punkte) > 1, (
        f"Testvoraussetzung: am unteren Rand mit 5 km Restsegment muessen "
        f"mehrere Punkte entstehen (kein entarteter Einzelfall wie AC-14), "
        f"erhalten {len(punkte)}"
    )

    now_utc = datetime.now(timezone.utc)
    monkeypatch.setattr(
        "services.radar_service.RadarNowcastService",
        recording_radar_service_type([], script=lambda idx: nass(10, 20)),
    )

    kippunkt = TripCommandProcessor()._show_strecke(trip, "3", now_utc, trip_id, _KANAL)
    assert kippunkt.success is True and "Ungültige km-Angabe" not in kippunkt.confirmation_body, (
        f"F005: der Kippunkt (km 3, exakt der untere Rand) ist eine "
        f"gueltige Anfrage -- Antwort: {kippunkt.confirmation_body!r}"
    )

    knapp_innerhalb = TripCommandProcessor()._show_strecke(trip, "3.01", now_utc, trip_id, _KANAL)
    assert knapp_innerhalb.success is True and "Ungültige km-Angabe" not in knapp_innerhalb.confirmation_body, (
        f"F005: '3.01' (knapp innerhalb) ist eine gueltige Anfrage -- "
        f"Antwort: {knapp_innerhalb.confirmation_body!r}"
    )

    knapp_ausserhalb = TripCommandProcessor()._show_strecke(trip, "2.99", now_utc, trip_id, _KANAL)
    assert "Ungültige km-Angabe" in knapp_ausserhalb.confirmation_body, (
        f"F005: '2.99' (knapp ausserhalb) muss weiterhin abgelehnt werden "
        f"-- Antwort: {knapp_ausserhalb.confirmation_body!r}"
    )


# --------------------------------------------------------------------------
# AC-15: ungueltige Eingaben -- ausserhalb des Bereichs, nicht-numerisch.
#        Immer dieselbe Ablehnung, NIE ein Nowcast-Abruf.
# --------------------------------------------------------------------------

def _unerwarteter_aufruf(idx: int) -> Exception:
    return AssertionError(
        "get_nowcast() haette bei ungueltigem km-Argument nicht gerufen "
        "werden duerfen"
    )


def _spion(monkeypatch) -> list:
    calls: list = []
    monkeypatch.setattr(
        "services.radar_service.RadarNowcastService",
        recording_radar_service_type(calls, script=_unerwarteter_aufruf),
    )
    return calls


_ERWARTETE_ABLEHNUNG = "Ungültige km-Angabe. Gültiger Bereich für die aktuelle Etappe: 3–8 km."


def test_ac15_ueber_der_oberen_grenze_wird_abgelehnt(monkeypatch):
    """AC-15 Fall 1: '/strecke 8.1' liegt ueber der oberen Grenze (8 km)."""
    trip_id = fresh_trip_id("ac15a")
    trip = active_three_point_trip(trip_id, 3.0, 8.0)
    now_utc = datetime.now(timezone.utc)
    nowcast_spy = _spion(monkeypatch)

    result = TripCommandProcessor()._show_strecke(trip, "8.1", now_utc, trip_id, _KANAL)

    assert result.confirmation_body == _ERWARTETE_ABLEHNUNG, (
        f"AC-15 (8.1): erwartet {_ERWARTETE_ABLEHNUNG!r}, erhalten "
        f"{result.confirmation_body!r}"
    )
    assert len(nowcast_spy) == 0, (
        f"AC-15 (8.1): KEIN get_nowcast()-Aufruf erwartet, erhalten "
        f"{len(nowcast_spy)}"
    )


def test_ac15_unter_der_unteren_grenze_wird_abgelehnt(monkeypatch):
    """AC-15 Fall 2: '/strecke 2.9' liegt unter der unteren Grenze (3 km)."""
    trip_id = fresh_trip_id("ac15b")
    trip = active_three_point_trip(trip_id, 3.0, 8.0)
    now_utc = datetime.now(timezone.utc)
    nowcast_spy = _spion(monkeypatch)

    result = TripCommandProcessor()._show_strecke(trip, "2.9", now_utc, trip_id, _KANAL)

    assert result.confirmation_body == _ERWARTETE_ABLEHNUNG, (
        f"AC-15 (2.9): erwartet {_ERWARTETE_ABLEHNUNG!r}, erhalten "
        f"{result.confirmation_body!r}"
    )
    assert len(nowcast_spy) == 0, (
        f"AC-15 (2.9): KEIN get_nowcast()-Aufruf erwartet, erhalten "
        f"{len(nowcast_spy)}"
    )


def test_ac15_nicht_numerisch_wird_abgelehnt(monkeypatch):
    """AC-15 Fall 3: '/strecke abc' ist nicht-numerisch."""
    trip_id = fresh_trip_id("ac15c")
    trip = active_three_point_trip(trip_id, 3.0, 8.0)
    now_utc = datetime.now(timezone.utc)
    nowcast_spy = _spion(monkeypatch)

    result = TripCommandProcessor()._show_strecke(trip, "abc", now_utc, trip_id, _KANAL)

    assert result.confirmation_body == _ERWARTETE_ABLEHNUNG, (
        f"AC-15 (abc): erwartet {_ERWARTETE_ABLEHNUNG!r}, erhalten "
        f"{result.confirmation_body!r}"
    )
    assert len(nowcast_spy) == 0, (
        f"AC-15 (abc): KEIN get_nowcast()-Aufruf erwartet, erhalten "
        f"{len(nowcast_spy)}"
    )


def test_ac15_positivkontrolle_gueltiges_argument_ruft_den_nowcast(monkeypatch):
    """AC-15 Positivkontrolle (Abwesenheits-Zusicherung braucht ihr
    Gegenstueck): dasselbe Segment, ein GUELTIGES Argument ('5') MUSS
    tatsaechlich einen get_nowcast()-Aufruf ausloesen -- sonst waere der
    'kein Aufruf'-Nachweis der drei Ablehnungsfaelle oben trivial wahr
    (Spy wuerde nie zaehlen, egal was passiert)."""
    from tests.helpers.strecke_fixtures import nass

    trip_id = fresh_trip_id("ac15d")
    trip = active_three_point_trip(trip_id, 3.0, 8.0)
    now_utc = datetime.now(timezone.utc)

    calls: list = []
    monkeypatch.setattr(
        "services.radar_service.RadarNowcastService",
        recording_radar_service_type(calls, script=lambda idx: nass(10, 20)),
    )

    result = TripCommandProcessor()._show_strecke(trip, "5", now_utc, trip_id, _KANAL)

    assert len(calls) >= 1, (
        f"AC-15 Positivkontrolle: ein gueltiges Argument muss mindestens "
        f"einen get_nowcast()-Aufruf ausloesen, erhalten {len(calls)} -- "
        f"Antwort: {result.confirmation_body!r}"
    )
    assert result.confirmation_body != _ERWARTETE_ABLEHNUNG


# --------------------------------------------------------------------------
# AC-16: Dezimalwerte werden akzeptiert, nicht auf ganze km gerundet.
# --------------------------------------------------------------------------

def test_ac16_dezimalwert_wird_nicht_gerundet():
    """AC-16 GIVEN dasselbe Segment, Kommando '/strecke 5.5' WHEN
    verarbeitet wird THEN liegt der erste erzeugte Punkt exakt bei km 5.5 --
    Dezimalwerte werden akzeptiert und NICHT auf ganze km gerundet."""
    from services.trip_segments import points_from_km

    trip_id = fresh_trip_id("ac16")
    trip = active_three_point_trip(trip_id, 3.0, 8.0)
    active, segment_date = _aktives_segment(trip)

    punkte = points_from_km(trip, active, segment_date, 5.5)

    assert punkte[0].distance_from_start_km == 5.5, (
        f"AC-16: der erste Punkt muss exakt bei km 5.5 liegen (kein "
        f"Runden auf ganze km), erhalten {punkte[0].distance_from_start_km}"
    )


# --------------------------------------------------------------------------
# F006 (Adversary-Befund team-lead, MEDIUM -- inhaltlich wichtigster der
# drei Nachtraege): AC-16 belegt nur, dass die INTERNE `GPXPoint`-
# Kilometrierung fraktional bleibt -- kein Test prueft, wie diese Zahl in
# einer TEXTAUSGABE gerundet wird ("aus km 5,5 wird eine 5 oder eine 6").
# Beide Text-Bildungsstellen benutzen `int(round(...))`: die Zonen-Zeile
# (Renderer) UND die Geprueft-Zeile (`_show_strecke`) -- dieser End-to-End-
# Test deckt BEIDE gleichzeitig ab, mit der Erwartung aus `round()`
# ABGELEITET statt hingeschrieben.
# --------------------------------------------------------------------------

def test_f006_fraktionale_km_werden_in_der_textausgabe_gerundet_nicht_abgeschnitten(monkeypatch):
    """F006 GIVEN dasselbe Segment (3-8 km), Kommando '/strecke 5.5' -- die
    beiden erzeugten Punkte liegen bei km 5.5 UND 7.5 (fraktional, s.
    AC-16), beide liefern eine Nass-Zone WHEN '/strecke' verarbeitet wird
    THEN erscheinen sowohl die Zonen-Zeile ALS AUCH die Geprueft-Zeile mit
    den GERUNDETEN (nicht abgeschnittenen) km-Werten -- `round(5.5) == 6`,
    `round(7.5) == 8`, waehrend Abschneiden `5` bzw. `7` ergaebe."""
    from services.trip_segments import points_from_km

    trip_id = fresh_trip_id("f006")
    trip = active_three_point_trip(trip_id, 3.0, 8.0)
    active, segment_date = _aktives_segment(trip)
    punkte = points_from_km(trip, active, segment_date, 5.5)
    assert [p.distance_from_start_km for p in punkte] == [5.5, 7.5], (
        f"Testvoraussetzung: die zwei Punkte muessen fraktional bei km "
        f"5.5/7.5 liegen, erhalten {[p.distance_from_start_km for p in punkte]}"
    )
    von_gerundet, bis_gerundet = round(5.5), round(7.5)
    von_abgeschnitten, bis_abgeschnitten = int(5.5), int(7.5)
    assert (von_gerundet, bis_gerundet) != (von_abgeschnitten, bis_abgeschnitten), (
        "Testvoraussetzung: Runden und Abschneiden muessen bei dieser "
        "Fixture unterschiedliche Werte ergeben, sonst waere die Pruefung "
        "unten wirkungslos"
    )

    now_utc = datetime.now(timezone.utc)
    monkeypatch.setattr(
        "services.radar_service.RadarNowcastService",
        recording_radar_service_type([], script=lambda idx: nass(10, 20)),
    )

    result = TripCommandProcessor()._show_strecke(trip, "5.5", now_utc, trip_id, _KANAL)

    zonen_zeile_erwartet = f"km {von_gerundet}-{bis_gerundet}"
    assert zonen_zeile_erwartet in result.confirmation_body, (
        f"F006: die Zonen-Zeile muss die GERUNDETEN km-Werte "
        f"{zonen_zeile_erwartet!r} tragen, Antwort:\n"
        f"{result.confirmation_body}"
    )
    geprueft_erwartet = f"Geprüft: km {von_gerundet}-{bis_gerundet}."
    assert geprueft_erwartet in result.confirmation_body, (
        f"F006: die Geprueft-Zeile muss ebenfalls die GERUNDETEN km-Werte "
        f"{geprueft_erwartet!r} tragen, Antwort:\n{result.confirmation_body}"
    )
    zonen_zeile_abgeschnitten = f"km {von_abgeschnitten}-{bis_abgeschnitten}"
    assert zonen_zeile_abgeschnitten not in result.confirmation_body, (
        f"F006: die ABGESCHNITTENE Schreibweise {zonen_zeile_abgeschnitten!r} "
        f"darf NICHT erscheinen -- Antwort:\n{result.confirmation_body}"
    )
