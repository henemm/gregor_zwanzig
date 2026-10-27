"""TDD RED -- Feature #1539 (S0), AC-7: Dauer je Trip und je Etappe im Log.

SPEC: docs/specs/modules/feat_1539_s0_s1a_beobachtbarkeit_atomare_schreiber.md
(Abschnitt B, AC-7)

Heute loggt ``TripAlertService.check_all_trips()`` nur die Gesamtdauer
("Lauf beendet nach ..."). Die 10-30-s-Luecke je Etappen-Abruf ist
unprotokolliert. Verlangt: je Trip EINE Dauerzeile und je Etappe EINE
Dauerzeile; das Gesamtergebnis (checked/skipped/alerts_sent) bleibt gleich.

Erwartetes Zeilenmuster (bewusst NICHT der exakte Wortlaut, nur Bestandteile):
  Trip-Zeile:    enthaelt den Trip-NAMEN und eine Dauerzahl mit Einheit "s"
                 (Spec-Beispiel: "Trip <name>: geprueft in 0.123 s")
  Etappen-Zeile: enthaelt "Etappe <n>" (n = segment_id) und eine Dauerzahl
                 mit Einheit "s" (Spec-Beispiel: "Etappe <n>: Abruf in 0.123 s")
Die bestehende Gesamtzeile "Lauf beendet nach" zaehlt NICHT als Dauerzeile.

Echter ``TripAlertService`` und echte Snapshot-/Trip-Dateien im isolierten
Daten-Root (conftest); Wetterabruf ueber den offline ``FixtureProvider``
(``GZ_TEST_FIXTURE_DIR``, conftest-autouse); kein Netz, kein Versand
(``mail_sink`` DI-Naht). Kein Mock/patch.
"""
from __future__ import annotations

import logging
import re
import uuid

from app.loader import save_trip
from services.trip_alert import TripAlertService

# Wiederverwendete Aufbau-Helfer des Zeitgrenzen-Tests (#1447): gleiche Naht,
# gleiche Fixture-Daten, damit der Aufbau nicht doppelt gepflegt wird.
from tests.tdd.test_alert_run_deadline import (  # noqa: F401
    LAT,
    LON,
    _active_trip,
    _isolated_official_alert_sources,  # autouse Fixture (Registry leeren)
    _save_cached,
    _settings,
    _weather_data,
)

TRIP_NAME = "Dauerlog-Trip-Alpha"
ETAPPEN = (1, 2, 3)
# Dauerzahl mit Einheit s: "0.123 s", "0.123s", "12 s"
_DAUER = r"\d+(?:\.\d+)?\s*s\b"


def _lauf(caplog):
    """Ein Trip mit drei Etappen (gecachtes Wetter), ein echter Alarmlauf."""
    user_id = f"tdd-1539-dauer-{uuid.uuid4().hex[:6]}"
    trip = _active_trip(f"trip-{uuid.uuid4().hex[:6]}")
    trip.name = TRIP_NAME
    save_trip(trip, user_id=user_id)
    _save_cached(
        user_id,
        trip.id,
        [
            _weather_data(n, lat=LAT + 0.01 * n, lon=LON + 0.01 * n, precip_sum_mm=2.0)
            for n in ETAPPEN
        ],
    )
    service = TripAlertService(
        settings=_settings(), user_id=user_id, mail_sink=lambda *_: None
    )
    with caplog.at_level(logging.INFO):
        result = service.check_all_trips()
    return result, [r.getMessage() for r in caplog.records]


def _dauerzeilen(zeilen, muster):
    return [z for z in zeilen if "Lauf beendet nach" not in z and re.search(muster, z)]


def test_trip_alarmlauf_loggt_dauerzeile_je_trip(caplog):
    """AC-7: Given ein Trip-Alarmlauf ueber einen Trip mit drei Etappen /
    When der Lauf endet / Then steht im Log GENAU EINE Dauerzeile fuer den
    Trip (Trip-Name + Dauerzahl in s).

    RED (heute): es gibt nur die Gesamtzeile "Lauf beendet nach", keine
    Trip-Zeile.
    """
    result, zeilen = _lauf(caplog)
    assert result.checked == 1, f"Setup: Trip muss geprueft werden, checked={result.checked}"
    treffer = _dauerzeilen(zeilen, re.escape(TRIP_NAME) + r".*" + _DAUER)
    assert len(treffer) == 1, (
        f"Erwartet genau eine Trip-Dauerzeile mit '{TRIP_NAME}' und Dauer in s, "
        f"gefunden: {treffer!r}"
    )


def test_trip_alarmlauf_loggt_dauerzeile_je_etappe(caplog):
    """AC-7: Given derselbe Lauf mit den Etappen 1, 2, 3 / When der Lauf endet /
    Then steht je Etappe GENAU EINE Dauerzeile ("Etappe <n>" + Dauerzahl in s).

    RED (heute): der Etappen-Abruf in ``_fetch_fresh_weather`` misst und loggt
    nichts.
    """
    result, zeilen = _lauf(caplog)
    assert result.checked == 1, f"Setup: Trip muss geprueft werden, checked={result.checked}"
    for n in ETAPPEN:
        treffer = _dauerzeilen(zeilen, rf"Etappe\s+{n}\b.*" + _DAUER)
        assert len(treffer) == 1, (
            f"Erwartet genau eine Dauerzeile fuer Etappe {n}, gefunden: {treffer!r}"
        )


def test_dauermessung_aendert_das_gesamtergebnis_nicht(caplog):
    """AC-7 (Gegenprobe): Given derselbe Aufbau / When der Lauf endet / Then
    sind checked, skipped und alerts_sent die Werte des heutigen Laufs ohne
    Messung (1 geprueft, 0 uebersprungen), kein Deadline-Abbruch.

    Regressionsanker, heute GRUEN gedacht: haelt den Ist-Stand fest, den die
    Messung nicht veraendern darf. Der RED-Beleg sind die zwei Tests oben.
    """
    result, _ = _lauf(caplog)
    assert (result.checked, result.skipped) == (1, 0)
    assert result.alerts_sent == 0
    assert result.hit_deadline is False
