"""TDD RED — Issue #2051 Scheibe S4: Abruf-Priorisierung (E1) des neuen
`/strecke`-Kommandos -- erster Punkt nie gedrosselt, Folgepunkte fail-soft.

SPEC: docs/specs/modules/feat_2051_s4_strecke_kommando.md — AC-4, AC-5, AC-6,
AC-7.

RED-Ursache: `TripCommandProcessor._show_strecke` existiert noch nicht ->
AttributeError.

Mock-frei: echte `Trip`/`TripSegment`-Aufloesung (Aequator-Geometrie,
`tests/helpers/strecke_fixtures.py`), echte `RadarNowcastService`-
Unterklassen (Aufzeichnung/Skript, kein `Mock()`/`patch()`), echte
`ForecastBudgetGate`-Datei fuer AC-4.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from services.trip_command_processor import TripCommandProcessor
from tests.helpers.strecke_fixtures import (
    fresh_trip_id,
    future_two_point_trip,
    nass,
    recording_radar_service_type,
    trocken,
    wrapping_radar_service_type,
)

_KANAL = "telegram"


def _write_budget(calls_openmeteo: int) -> None:
    """Echte forecast_budget.json unter der isolierten Datenwurzel (Muster
    `test_radar_nowcast_health_journal.py::_write_budget`)."""
    from app.loader import get_data_root

    pfad = get_data_root() / "diagnostics" / "forecast_budget.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps({
        "date": date.today().isoformat(),
        "calls": {"openmeteo": calls_openmeteo},
        "cache_hits": 0,
        "cache_misses": 0,
    }))


def _wet_frames(lat: float, lon: float) -> list:
    from providers.brightsky import RadarFrame

    now = datetime.now(timezone.utc)
    return [RadarFrame(timestamp=now + timedelta(minutes=5), precip_mm_h=1.0)]


# --------------------------------------------------------------------------
# AC-4: 85% Budget -- der ERSTE Punkt faehrt user_briefing (nie gedrosselt)
#       und liefert trotzdem ein Ergebnis.
# --------------------------------------------------------------------------

def test_ac4_erster_punkt_faehrt_user_briefing_trotz_budget_druck(monkeypatch):
    """AC-4 GIVEN ein aktives Segment mit Reststrecke 10 km (mehrere
    geplante Punkte) UND einem simulierten Budgetstand von 85%
    (`allow('polling')` waere `False`) WHEN `/strecke` verarbeitet wird THEN
    liefert der ERSTE Abfragepunkt trotzdem ein Ergebnis, UND dessen
    `get_nowcast()`-Aufruf traegt `priority='user_briefing'`."""
    trip_id = fresh_trip_id("ac4")
    trip = future_two_point_trip(trip_id, 10.0)
    now_utc = datetime.now(timezone.utc)

    _write_budget(7650)  # 7650 / 9000 = 0.85 >= POLLING_THRESHOLD (0.80)

    calls: list = []
    monkeypatch.setattr(
        "services.radar_service.RadarNowcastService",
        wrapping_radar_service_type(calls, _wet_frames),
    )

    result = TripCommandProcessor()._show_strecke(
        trip, None, now_utc, trip_id, _KANAL,
    )

    assert len(calls) >= 1, (
        f"Testvoraussetzung: mindestens ein get_nowcast()-Aufruf erwartet, "
        f"erhalten {len(calls)} -- Antwort: {result.confirmation_body!r}"
    )
    assert calls[0]["priority"] == "user_briefing", (
        f"AC-4: der ERSTE Abfragepunkt muss priority='user_briefing' "
        f"tragen (nie gedrosselt), erhalten {calls[0]['priority']!r}"
    )
    # Positivkontrolle: das Ergebnis des ersten Punkts ist tatsaechlich
    # durchgekommen (nicht durch die 85%-Budgetlage gedrosselt) -- ein
    # faelschlich mit priority="polling" gefahrener erster Aufruf waere bei
    # 85% Budgetlast throttled=True und traege onset_minutes=None.
    erstes_ergebnis = calls[0]["result"]
    assert erstes_ergebnis.throttled is False, (
        f"AC-4: der erste Punkt darf bei 85% Budgetlast NICHT gedrosselt "
        f"sein (belegt priority='user_briefing' wirkt wirklich), throttled="
        f"{erstes_ergebnis.throttled}"
    )
    assert erstes_ergebnis.onset_minutes is not None, (
        f"AC-4: der erste (nasse) Punkt muss einen Onset liefern, erhalten "
        f"onset_minutes={erstes_ergebnis.onset_minutes}"
    )


# --------------------------------------------------------------------------
# AC-5: Fail-soft -- Punkt 3 wirft, Punkt 2 und 4 werden TROTZDEM
#       (priority=polling) abgefragt, das Kommando bricht nicht ab.
# --------------------------------------------------------------------------

def test_ac5_einzelausfall_eines_folgepunkts_bricht_das_kommando_nicht_ab(monkeypatch):
    """AC-5 GIVEN 5 geplante Punkte (km 0/2/4/6/8), wobei Punkt 3 (km 4,
    nicht Punkt 1) eine Exception wirft und Punkt 5 (km 8) GENUIN TROCKEN
    ist (trennt die Zone) WHEN `/strecke` verarbeitet wird THEN werden
    Punkt 2/4/5 dennoch mit `priority='polling'` abgefragt, UND die Antwort
    enthaelt die aus den Punkten 1/2/4 gebildete Zone (km 0-6) -- das
    Kommando bricht wegen des Einzelausfalls NICHT ab.

    F001/F002-Korrektur (Adversary-Befund team-lead): der fuenfte,
    genuin trockene Punkt (km 8, gemessen, aber trocken) sorgt dafuer, dass
    die Geprueft-Spanne (0-8, alle ERFOLGREICHEN Punkte inkl. des trockenen)
    und die Zonen-Spanne (0-6, nur die NASSEN Punkte) STRUKTURELL
    auseinanderfallen -- vorher fiel bei Reststrecke 6 km beides zufaellig
    zusammen, wodurch die Geprueft-Zeile allein die 'km 0-6'-Pruefung
    haette tragen koennen, ohne dass der Zonentext ueberhaupt gerendert
    wurde. Zusaetzlich eine vom Zonentext exklusive Positivpruefung
    (Intensitaetswort, kann in der Geprueft-Zeile strukturell nicht
    auftreten) sowie die Negativ-Pruefung, dass NICHT der AC-7-Ausfalltext
    erscheint (F002)."""
    trip_id = fresh_trip_id("ac5")
    trip = future_two_point_trip(trip_id, 9.0)  # -> 5 Punkte bei km 0/2/4/6/8
    now_utc = datetime.now(timezone.utc)

    def _skript(idx: int):
        if idx == 2:  # Punkt 3 (0-basiert Index 2, km 4) -- Ausfall (Luecke)
            return RuntimeError("Nowcast fuer Punkt 3 fehlgeschlagen")
        if idx == 4:  # Punkt 5 (km 8) -- genuin trocken, trennt die Zone
            return trocken()
        return nass(10 + idx, 20 + idx)

    calls: list = []
    monkeypatch.setattr(
        "services.radar_service.RadarNowcastService",
        recording_radar_service_type(calls, script=_skript),
    )

    result = TripCommandProcessor()._show_strecke(
        trip, None, now_utc, trip_id, _KANAL,
    )

    assert len(calls) == 5, (
        f"AC-5: alle 5 geplanten Punkte muessen abgefragt werden (Fail-soft "
        f"bei Punkt 3), erhalten {len(calls)} Aufrufe: {calls!r}"
    )
    assert calls[0]["priority"] == "user_briefing", (
        f"AC-5: Punkt 1 muss user_briefing tragen, erhalten "
        f"{calls[0]['priority']!r}"
    )
    for idx in (1, 2, 3, 4):
        assert calls[idx]["priority"] == "polling", (
            f"AC-5: Folgepunkt {idx + 1} muss priority='polling' tragen, "
            f"erhalten {calls[idx]['priority']!r}"
        )
    assert "km 0-6" in result.confirmation_body, (
        f"AC-5: die Antwort muss die aus Punkt 1/2/4 gebildete Zone 'km "
        f"0-6' enthalten (der Ausfall von Punkt 3 trennt NICHT, s. S2a "
        f"AC-11) -- Antwort:\n{result.confirmation_body}"
    )
    assert "Mäßiger Regen" in result.confirmation_body, (
        f"AC-5: der Zonentext selbst (Intensitaetswort, in der "
        f"Geprueft-Zeile strukturell unmoeglich) muss tatsaechlich "
        f"gerendert sein -- Antwort:\n{result.confirmation_body}"
    )
    assert "Geprüft: km 0-8." in result.confirmation_body, (
        f"AC-5: die Geprueft-Spanne (alle ERFOLGREICHEN Punkte, auch der "
        f"trockene bei km 8) muss von der Zonen-Spanne (nur die nassen "
        f"Punkte, km 0-6) UNTERSCHEIDBAR sein -- Antwort:\n"
        f"{result.confirmation_body}"
    )
    assert "konnte nicht ermittelt werden" not in result.confirmation_body, (
        f"AC-5 (F002): mit mehreren erfolgreichen Punkten darf NICHT der "
        f"AC-7-Ausfalltext erscheinen -- Antwort:\n{result.confirmation_body}"
    )


# --------------------------------------------------------------------------
# AC-6: Reststrecke 1,5 km (genau 1 Punkt) -> normale Streckenangabe, KEIN
#       Hinweis auf nicht ermittelbare Ausdehnung.
# --------------------------------------------------------------------------

def test_ac6_ein_einzelner_punkt_unter_der_schwelle_ist_eine_normale_antwort(monkeypatch):
    """AC-6 (Positivkontrolle zu AC-7) GIVEN eine Reststrecke von 1,5 km
    (unter der 2-km-Schwelle, genau 1 geplanter Punkt), dieser liefert eine
    Nass-Zone WHEN `/strecke` verarbeitet wird THEN meldet die Antwort diese
    eine Zone als normale Streckenangabe, OHNE den Hinweis auf eine nicht
    ermittelbare Ausdehnung (AC-7-Text)."""
    trip_id = fresh_trip_id("ac6")
    trip = future_two_point_trip(trip_id, 1.5)
    now_utc = datetime.now(timezone.utc)

    calls: list = []
    monkeypatch.setattr(
        "services.radar_service.RadarNowcastService",
        recording_radar_service_type(calls, script=lambda idx: nass(15, 30)),
    )

    result = TripCommandProcessor()._show_strecke(
        trip, None, now_utc, trip_id, _KANAL,
    )

    assert len(calls) == 1, (
        f"Testvoraussetzung: bei Reststrecke 1,5 km darf es nur EINEN "
        f"geplanten Punkt geben (S2a-Regime), erhalten {len(calls)}"
    )
    assert calls[0]["priority"] == "user_briefing"
    assert "km 0-0" in result.confirmation_body, (
        f"AC-6: die eine Zone (degenerierter Einzelpunkt km 0-0) muss "
        f"erscheinen -- Antwort:\n{result.confirmation_body}"
    )
    # F001-Gegenprobe (Adversary-Befund team-lead): bei genau 1 Punkt sind
    # Zonen- und Geprueft-Spanne IMMER identisch (km 0-0) -- "km 0-0" allein
    # koennte also von der Geprueft-Zeile getragen werden, selbst wenn der
    # Zonentext gar nicht gerendert wurde. Das Intensitaetswort kann in der
    # Geprueft-Zeile strukturell nicht auftreten und belegt damit, dass der
    # Zonentext SELBST vorhanden ist.
    assert "Mäßiger Regen" in result.confirmation_body, (
        f"AC-6: der Zonentext selbst (Intensitaetswort) muss tatsaechlich "
        f"gerendert sein, nicht nur die Geprueft-Zeile -- Antwort:\n"
        f"{result.confirmation_body}"
    )
    assert "konnte nicht ermittelt werden" not in result.confirmation_body, (
        f"AC-6: der AC-7-Hinweistext ('Ausdehnung ... konnte nicht "
        f"ermittelt werden') darf hier NICHT erscheinen -- Antwort:\n"
        f"{result.confirmation_body}"
    )


# --------------------------------------------------------------------------
# AC-7: alle Folgepunkte fallen aus -> ehrlicher Hinweis mit degenerierter
#       Geprueft-Spanne, KEINE km-Zonen-Angabe.
# --------------------------------------------------------------------------

def test_ac7_alle_folgepunkte_fallen_aus_kein_zonenwert(monkeypatch):
    """AC-7 GIVEN 6 geplante Punkte bei km 0/2/4/6/8/10 (Reststrecke 12 km),
    von denen NUR der erste (km 0) ein Ergebnis liefert (Punkte 2-6 alle
    Exception) WHEN `/strecke` verarbeitet wird THEN enthaelt die Antwort
    EXAKT den Hinweistext mit der degenerierten Geprueft-Spanne km 0-0 UND
    KEINE km-Zonen-Angabe."""
    trip_id = fresh_trip_id("ac7")
    trip = future_two_point_trip(trip_id, 12.0)
    now_utc = datetime.now(timezone.utc)

    def _skript(idx: int):
        if idx == 0:
            return nass(10, 20)
        return RuntimeError(f"Nowcast fuer Folgepunkt {idx + 1} fehlgeschlagen")

    calls: list = []
    monkeypatch.setattr(
        "services.radar_service.RadarNowcastService",
        recording_radar_service_type(calls, script=_skript),
    )

    result = TripCommandProcessor()._show_strecke(
        trip, None, now_utc, trip_id, _KANAL,
    )

    assert len(calls) == 6, (
        f"Testvoraussetzung: bei Reststrecke 12 km muessen 6 Punkte geplant "
        f"sein (S2a-Deckel), erhalten {len(calls)}"
    )
    erwartet = (
        "Ausdehnung entlang der Reststrecke konnte nicht ermittelt werden "
        "— nur der Startpunkt lieferte Daten. Geprüft: km 0-0."
    )
    assert result.confirmation_body == erwartet, (
        f"AC-7: erwartet exakt {erwartet!r}, erhalten "
        f"{result.confirmation_body!r}"
    )
    assert "Nass km" not in result.confirmation_body, (
        f"AC-7: keine km-Zonen-Angabe erlaubt, wenn nur der Startpunkt "
        f"Daten liefert -- Antwort:\n{result.confirmation_body}"
    )


# --------------------------------------------------------------------------
# F004 (Adversary-Befund team-lead, CLAUDE.md-Mandantenpflicht): der
# SCHREIBENDE Seitenaufruf `backfill_stage_distances(trip, user_id, ...)`
# war mit KEINEM Nutzer belegt -- ein Regressionsfehler, der dort das
# Literal "default" statt der echten user_id einsetzt, faende kein Test
# (Cross-User-Datenleck-Regel, CLAUDE.md).
# --------------------------------------------------------------------------

def test_f004_backfill_erhaelt_die_echte_user_id_nicht_default(monkeypatch):
    """F004 GIVEN zwei VERSCHIEDENE, echte user_id-Werte (keiner davon
    'default') WHEN `/strecke` fuer beide Nutzer nacheinander verarbeitet
    wird THEN erhaelt `backfill_stage_distances()` in BEIDEN Aufrufen genau
    die user_id des jeweils aufrufenden Nutzers -- nie 'default', und die
    beiden Aufrufe duerfen nicht vertauscht sein (belegt im SELBEN Test,
    damit eine Verwechslung zwischen den Nutzern auffiele, nicht nur eine
    pauschale 'default' vs. 'nicht default'-Unterscheidung)."""
    import services.track_resolution as track_resolution_mod

    calls: list = []

    def _fake_backfill(trip, user_id, target_date, *, persist=True):
        calls.append((user_id, trip.id))
        return trip

    monkeypatch.setattr(track_resolution_mod, "backfill_stage_distances", _fake_backfill)
    monkeypatch.setattr(
        "services.radar_service.RadarNowcastService",
        recording_radar_service_type([], script=lambda idx: nass(10, 20)),
    )

    now_utc = datetime.now(timezone.utc)
    trip_a_id = fresh_trip_id("f004a")
    trip_a = future_two_point_trip(trip_a_id, 3.0)
    user_a = f"tdd-2051-s4-f004-nutzer-a-{trip_a_id[-6:]}"

    trip_b_id = fresh_trip_id("f004b")
    trip_b = future_two_point_trip(trip_b_id, 3.0)
    user_b = f"tdd-2051-s4-f004-nutzer-b-{trip_b_id[-6:]}"

    TripCommandProcessor()._show_strecke(trip_a, None, now_utc, user_a, _KANAL)
    TripCommandProcessor()._show_strecke(trip_b, None, now_utc, user_b, _KANAL)

    assert len(calls) == 2, (
        f"Testvoraussetzung: beide Aufrufe muessen backfill_stage_distances "
        f"erreichen, erhalten {len(calls)} Aufrufe: {calls!r}"
    )
    assert calls[0] == (user_a, trip_a.id), (
        f"F004: Nutzer A's Aufruf muss dessen eigene user_id tragen "
        f"({user_a!r}), erhalten {calls[0]!r}"
    )
    assert calls[1] == (user_b, trip_b.id), (
        f"F004: Nutzer B's Aufruf muss dessen eigene user_id tragen "
        f"({user_b!r}), erhalten {calls[1]!r}"
    )
    assert calls[0][0] != "default" and calls[1][0] != "default", (
        f"F004: kein Aufruf darf auf 'default' zurueckfallen -- {calls!r}"
    )
    assert calls[0][0] != calls[1][0], (
        f"F004: die beiden Nutzer-Aufrufe duerfen nicht dieselbe user_id "
        f"tragen (Verwechslungs-Gegenprobe) -- {calls!r}"
    )
