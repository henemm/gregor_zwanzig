"""TDD RED — Issue #2051 Scheibe S4: die drei ehrlichen Sonderfaelle (E6) und
die geprueften Streckenspanne (E7) des `/strecke`-Kommandos.

SPEC: docs/specs/modules/feat_2051_s4_strecke_kommando.md — AC-17, AC-18,
AC-19, AC-21, AC-22.

RED-Ursache: `TripCommandProcessor._show_strecke` existiert noch nicht ->
AttributeError.

Mock-frei: echte `Trip`/`TripSegment`-Aufloesung
(`tests/helpers/strecke_fixtures.py`), echte aufzeichnende
`RadarNowcastService`-Unterklasse (kein `Mock()`/`patch()`).

Hinweis zur Fixture-Wahl AC-19/AC-21: die Spec illustriert beide Szenarien
mit Punkten bei km 2/4/6/8. Strukturell liefert `resolve_current_segment()`
fuer den ARGUMENTLOSEN Pfad (`points_along_remaining_route`) den ERSTEN
Punkt nur dann EXAKT am Segmentanfang (p=0, keine Zeitanteils-Drift), wenn
dieses Segment das ERSTE der Etappe ist -- dessen Kilometrierung ist nach
`stage_measured_distances()` IMMER auf 0 normiert (Etappenstart). Die Tests
nutzen deshalb dieselbe Vier-Punkte-Kardinalitaet (km 0/2/4/6, Reststrecke
6 km) wie die Spec-Skizze, aber bei 0 beginnend -- der Sollwert der
'Geprueft:'-Zeile wird in JEDEM Test aus den tatsaechlichen Fixture-Punkten
ABGELEITET, nicht abgeschrieben.
"""
from __future__ import annotations

from datetime import datetime, timezone

from services.trip_command_processor import TripCommandProcessor
from tests.helpers.strecke_fixtures import (
    fresh_trip_id,
    future_two_point_trip,
    nass,
    no_active_segment_trip,
    recording_radar_service_type,
    trocken,
    unmeasured_future_trip,
)

_KANAL = "telegram"


# --------------------------------------------------------------------------
# AC-17: Kilometrierung bleibt unvermessen (auch nach Backfill-Versuch) --
#        zwei Varianten, IMMER vor jedem Nowcast-Aufruf geprueft.
# --------------------------------------------------------------------------

def test_ac17a_unvermessen_ohne_argument(monkeypatch):
    """AC-17 (a) GIVEN ein aktives Segment, das auch nach dem
    Backfill-Versuch `distance_measured=False` bleibt, '/strecke' OHNE
    Argument WHEN verarbeitet wird THEN liefert die Antwort exakt
    'Kilometrierung für die heutige Etappe nicht verfügbar — keine
    Streckenangabe möglich.' UND es erfolgt KEIN get_nowcast()-Aufruf UND
    KEINE 'Geprüft:'-Zeile."""
    trip_id = fresh_trip_id("ac17a")
    trip = unmeasured_future_trip(trip_id)
    now_utc = datetime.now(timezone.utc)

    calls: list = []
    monkeypatch.setattr(
        "services.radar_service.RadarNowcastService",
        recording_radar_service_type(calls, script=lambda idx: nass(10, 20)),
    )

    result = TripCommandProcessor()._show_strecke(trip, None, now_utc, trip_id, _KANAL)

    erwartet = (
        "Kilometrierung für die heutige Etappe nicht verfügbar — keine "
        "Streckenangabe möglich."
    )
    assert result.confirmation_body == erwartet, (
        f"AC-17 (a): erwartet {erwartet!r}, erhalten "
        f"{result.confirmation_body!r}"
    )
    assert len(calls) == 0, f"AC-17 (a): KEIN get_nowcast()-Aufruf erwartet, erhalten {len(calls)}"
    assert "Geprüft:" not in result.confirmation_body, (
        f"AC-17 (a): keine Geprueft-Zeile erlaubt -- nichts wurde "
        f"gemessen: {result.confirmation_body!r}"
    )


def test_ac17b_unvermessen_mit_argument(monkeypatch):
    """AC-17 (b) dieselbe Etappe, '/strecke 5' MIT Argument WHEN verarbeitet
    wird THEN liefert die Antwort exakt 'Kilometrierung für die heutige
    Etappe nicht verfügbar — die km-Angabe kann nicht ausgewertet werden.'
    UND es erfolgt KEIN get_nowcast()-Aufruf UND KEINE 'Geprüft:'-Zeile."""
    trip_id = fresh_trip_id("ac17b")
    trip = unmeasured_future_trip(trip_id)
    now_utc = datetime.now(timezone.utc)

    calls: list = []
    monkeypatch.setattr(
        "services.radar_service.RadarNowcastService",
        recording_radar_service_type(calls, script=lambda idx: nass(10, 20)),
    )

    result = TripCommandProcessor()._show_strecke(trip, "5", now_utc, trip_id, _KANAL)

    erwartet = (
        "Kilometrierung für die heutige Etappe nicht verfügbar — die "
        "km-Angabe kann nicht ausgewertet werden."
    )
    assert result.confirmation_body == erwartet, (
        f"AC-17 (b): erwartet {erwartet!r}, erhalten "
        f"{result.confirmation_body!r}"
    )
    assert len(calls) == 0, f"AC-17 (b): KEIN get_nowcast()-Aufruf erwartet, erhalten {len(calls)}"
    assert "Geprüft:" not in result.confirmation_body, (
        f"AC-17 (b): keine Geprueft-Zeile erlaubt: {result.confirmation_body!r}"
    )


# --------------------------------------------------------------------------
# AC-18: kein aufloesbarer Standort -- wortidentisch zu _show_now.
# --------------------------------------------------------------------------

def test_ac18_kein_standort_ist_wortidentisch_zu_show_now():
    """AC-18 GIVEN keinen aufloesbaren Standort fuer heute
    (`resolve_current_segment` liefert `None`) WHEN '/strecke' verarbeitet
    wird THEN ist `result.confirmation_body` TEXTIDENTISCH zu dem Text, den
    `_show_now` in derselben Situation liefert -- insbesondere ohne jede
    'Geprüft:'-Zeile."""
    trip_id = fresh_trip_id("ac18")
    trip = no_active_segment_trip(trip_id)
    now_utc = datetime.now(timezone.utc)

    prozessor = TripCommandProcessor()
    strecke_ergebnis = prozessor._show_strecke(trip, None, now_utc, trip_id, _KANAL)
    now_ergebnis = prozessor._show_now(trip, now_utc)

    assert now_ergebnis.success is False, (
        "Testvoraussetzung: _show_now muss in dieser Situation ebenfalls "
        f"scheitern (kein heutiger Standort), war success={now_ergebnis.success}"
    )
    assert strecke_ergebnis.confirmation_body == now_ergebnis.confirmation_body, (
        f"AC-18: /strecke muss denselben Text wie /jetzt liefern.\n"
        f"/strecke: {strecke_ergebnis.confirmation_body!r}\n"
        f"/jetzt:   {now_ergebnis.confirmation_body!r}"
    )
    # Wortlaut auch gegen die bekannte, feste Textstelle abgesichert (die
    # `_show_now` heute schon traegt) -- kein zufaelliger Gleichklang zweier
    # unabhaengig gewachsener Texte.
    erwartet = (
        "Keine heutige Etappe gefunden. Aktueller Position/Standort "
        "unbekannt — bitte Etappenplan prüfen."
    )
    assert strecke_ergebnis.confirmation_body == erwartet, (
        f"AC-18: erwartet {erwartet!r}, erhalten "
        f"{strecke_ergebnis.confirmation_body!r}"
    )
    assert "Geprüft:" not in strecke_ergebnis.confirmation_body


# --------------------------------------------------------------------------
# AC-19: alle geplanten Punkte liefern Daten, alle trocken -- eigener,
#        vom geprueften Abschnitt sprechender Hinweis.
# --------------------------------------------------------------------------

def test_ac19_alle_punkte_trocken_nennt_den_geprueften_abschnitt(monkeypatch):
    """AC-19 GIVEN ein vermessenes aktives Segment mit 4 geplanten Punkten,
    bei denen ALLE ein Ergebnis liefern und ALLE trocken sind WHEN
    '/strecke' verarbeitet wird THEN enthaelt die Antwort exakt 'Kein Regen
    entlang des geprüften Abschnitts erkannt. Geprüft: km {von}-{bis}.' --
    mit dem AUS DEN FIXTURE-PUNKTEN abgeleiteten von/bis, nicht pauschal
    'die Reststrecke'."""
    trip_id = fresh_trip_id("ac19")
    trip = future_two_point_trip(trip_id, 6.0)  # -> 4 Punkte bei km 0/2/4/6
    now_utc = datetime.now(timezone.utc)

    calls: list = []
    monkeypatch.setattr(
        "services.radar_service.RadarNowcastService",
        recording_radar_service_type(calls, script=lambda idx: trocken()),
    )

    result = TripCommandProcessor()._show_strecke(trip, None, now_utc, trip_id, _KANAL)

    assert len(calls) == 4, f"Testvoraussetzung: 4 Punkte erwartet, erhalten {len(calls)}"
    # Die km-Werte selbst stehen nicht in `calls` (nur lat/lon) -- die
    # Fixture ist Aequator-linear konstruiert, die geplanten km sind daher
    # exakt 0/2/4/6 (S2a-Deckelformel bei Reststrecke 6 km).
    erwartet = "Kein Regen entlang des geprüften Abschnitts erkannt. Geprüft: km 0-6."
    assert result.confirmation_body == erwartet, (
        f"AC-19: erwartet {erwartet!r}, erhalten {result.confirmation_body!r}"
    )
    assert "konnte nicht ermittelt werden" not in result.confirmation_body, (
        "AC-19: der Wortlaut muss sich klar von AC-7 (Ausdehnung nicht "
        f"ermittelbar) unterscheiden: {result.confirmation_body!r}"
    )
    assert "Kilometrierung" not in result.confirmation_body, (
        "AC-19: der Wortlaut muss sich klar von AC-17 (Kilometrierung "
        f"fehlt) unterscheiden: {result.confirmation_body!r}"
    )


# --------------------------------------------------------------------------
# AC-21 (E7): die Geprueft-Spanne stammt aus den ERFOLGREICH abgefragten
#            Punkten, NICHT aus dem geplanten Maximum.
# --------------------------------------------------------------------------

def test_ac21_geprueft_spanne_aus_erfolgreichen_nicht_geplanten_punkten(monkeypatch):
    """AC-21 GIVEN 4 geplante Punkte (km 0/2/4/6), von denen der LETZTE (km
    6) eine Exception wirft, die uebrigen drei (km 0/2/4) liefern Daten
    (mindestens einer nass) WHEN '/strecke' verarbeitet wird THEN nennt die
    Antwort exakt 'Geprüft: km 0-4.' -- abgeleitet aus dem kleinsten und
    groessten km-Wert der ERFOLGREICH abgefragten Punkte (0 und 4), NICHT
    aus dem geplanten Maximum (6)."""
    trip_id = fresh_trip_id("ac21")
    trip = future_two_point_trip(trip_id, 6.0)  # -> 4 Punkte bei km 0/2/4/6
    now_utc = datetime.now(timezone.utc)

    def _skript(idx: int):
        if idx == 3:  # letzter Punkt (km 6)
            return RuntimeError("Nowcast fuer den letzten Punkt fehlgeschlagen")
        return nass(10 + idx, 25 + idx)

    calls: list = []
    monkeypatch.setattr(
        "services.radar_service.RadarNowcastService",
        recording_radar_service_type(calls, script=_skript),
    )

    result = TripCommandProcessor()._show_strecke(trip, None, now_utc, trip_id, _KANAL)

    assert len(calls) == 4, f"Testvoraussetzung: 4 geplante Punkte, erhalten {len(calls)}"
    assert "Geprüft: km 0-4." in result.confirmation_body, (
        f"AC-21: erwartet die Teilzeile 'Geprüft: km 0-4.' (abgeleitet aus "
        f"den erfolgreichen Punkten 0/2/4, nicht dem geplanten Maximum 6), "
        f"Antwort:\n{result.confirmation_body}"
    )
    assert "km 0-6" not in result.confirmation_body, (
        f"AC-21: die Bildungsstelle darf NICHT aus dem geplanten Maximum "
        f"(km 6, das fehlgeschlagen ist) gespeist werden: "
        f"{result.confirmation_body!r}"
    )
    # F002-Gegenprobe (Adversary-Befund team-lead): die Geprueft-Spanne
    # dieses Falls ist bei korrektem UND bei vertauschtem Zweig identisch
    # (0-4) -- die obige Substring-Pruefung allein wuerde eine faelschlich
    # in den AC-7-Zweig ("Ausdehnung ... konnte nicht ermittelt werden")
    # gerutschte Weiche NICHT bemerken. Diese Negativ-Pruefung trennt die
    # beiden Zweige zusaetzlich ueber den Wortlaut.
    assert "konnte nicht ermittelt werden" not in result.confirmation_body, (
        f"AC-21: mit >1 erfolgreichem Punkt darf NICHT der AC-7-Ausfalltext "
        f"erscheinen -- Antwort:\n{result.confirmation_body}"
    )


# --------------------------------------------------------------------------
# AC-22 (E7, Positivkontrolle): Geprueft-Zeile erscheint NUR, wenn
#        tatsaechlich gemessen wurde -- echte Weiche, kein Zufall.
# --------------------------------------------------------------------------

def test_ac22_geprueft_zeile_nur_bei_tatsaechlicher_messung(monkeypatch):
    """AC-22 GIVEN zwei Faelle mit identischem Aufbau bis auf einen
    Unterschied: (a) `distance_measured=False` (kein Nowcast-Abruf), (b)
    `distance_measured=True` (mindestens 1 Punkt liefert Daten) WHEN beide
    Antworten erzeugt werden THEN enthaelt Antwort (a) KEINE 'Geprüft:'-
    Zeile, waehrend Antwort (b) eine 'Geprüft: km'-Zeile mit dem erwarteten
    Wert traegt -- belegt im SELBEN Test, dass das Fehlen in (a) eine echte
    Weiche ist."""
    now_utc = datetime.now(timezone.utc)

    # (a) unvermessen
    trip_a_id = fresh_trip_id("ac22a")
    trip_a = unmeasured_future_trip(trip_a_id)
    calls_a: list = []
    monkeypatch.setattr(
        "services.radar_service.RadarNowcastService",
        recording_radar_service_type(calls_a, script=lambda idx: nass(10, 20)),
    )
    ergebnis_a = TripCommandProcessor()._show_strecke(trip_a, None, now_utc, trip_a_id, _KANAL)

    assert len(calls_a) == 0, (
        f"Testvoraussetzung (a): kein Nowcast-Abruf bei unvermessener "
        f"Etappe, erhalten {len(calls_a)}"
    )
    assert "Geprüft:" not in ergebnis_a.confirmation_body, (
        f"AC-22 (a): keine Geprueft-Zeile bei unvermessener Etappe: "
        f"{ergebnis_a.confirmation_body!r}"
    )

    # (b) vermessen, identischer Aufbau bis auf die Kilometrierung
    trip_b_id = fresh_trip_id("ac22b")
    trip_b = future_two_point_trip(trip_b_id, 1.5)  # -> genau 1 Punkt (S2a-Regime)
    calls_b: list = []
    monkeypatch.setattr(
        "services.radar_service.RadarNowcastService",
        recording_radar_service_type(calls_b, script=lambda idx: nass(10, 20)),
    )
    ergebnis_b = TripCommandProcessor()._show_strecke(trip_b, None, now_utc, trip_b_id, _KANAL)

    assert len(calls_b) >= 1, (
        f"Testvoraussetzung (b): mindestens ein Punkt muss Daten liefern, "
        f"erhalten {len(calls_b)}"
    )
    assert "Geprüft: km 0-0." in ergebnis_b.confirmation_body, (
        f"AC-22 (b): erwartet die Teilzeile 'Geprüft: km 0-0.' (degenerierte "
        f"Spanne bei genau 1 Punkt), Antwort:\n{ergebnis_b.confirmation_body}"
    )
