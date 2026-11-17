"""#3047 Runde 7, Paket p11: Amtliche Warnungen bei der Neuanlage.

SPEC: docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md
(„Nachtrag Runde 7", PO 2026-11-16 „Amtliche Warnungen Neuanlage"; loest
#1258 AC-4 ab): neue Trips und Orts-Vergleiche bekommen amtliche Warnungen im
Briefing UND als Alarm; beide Felder werden ausdruecklich ``true`` geschrieben.

Echter Weg: die Anlege-Funktionen des Frontends (``tripNewLogic.ts``
``buildCreateTripPayload`` mit dem Start-Alarmzustand, wie ``TripNewEditor``
ihn sendet; ``compareEditorSave.ts`` ``buildNewComparePresetPayload`` mit dem
Standard-Feldsatz) bauen den POST-Rumpf. Er liegt als versionierte Fixture
``tests/fixtures/einstellung_gleich_mail/neuanlage_p11_payload.json`` vor;
``frontend/src/lib/components/trip-new/__tests__/p11_neuanlage_payload_fixture.test.ts``
(CI-Job ``frontend-test``) haelt sie byte-gleich zur echten Frontend-Ausgabe.
So laeuft diese Datei im CI-Job ``test`` ohne Node. Der Rumpf geht in
``load_trip`` -> Zeitplaner -> Transport-Mitschrift (zwei Nutzer, DE/EN) bzw.
in die geteilte Lese-Regel, die Briefing und Alarm steuert. Go-Anlage: siehe
``internal/handler/neuanlage_amtliche_warnungen_test.go``.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.loader import load_trip
from services.amtliche_warnungen_schalter import amtliche_warnungen_an_preset
from services.trip_alert import TripAlertService
from tests.helpers.transport_mitschrift import aufzeichner_installieren
from tests.tdd.test_einstellung_gleich_mail_runde7_katalog import (
    WARN_TEXT, _trip_roh, _zeitplaner_senden,
)

FIXTURE = (Path(__file__).resolve().parents[1] / "fixtures" / "einstellung_gleich_mail"
           / "neuanlage_p11_payload.json")

FELDER = ("official_alerts_enabled", "official_warnings", "official_alert_triggers_enabled")


@pytest.fixture(scope="module")
def anlage() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.mark.parametrize("art", ["trip", "vergleich"])
def test_p11_neuanlage_schreibt_beide_felder_true(anlage, art):
    p = anlage[art]
    assert p["official_alerts_enabled"] is True, f"{art}: Briefing-Feld {p}"
    assert p["official_warnings"]["enabled"] is True, f"{art}: Alarm-Feld {p}"
    assert amtliche_warnungen_an_preset(p) is True


def test_p11_neuer_trip_briefing_mit_warnung_und_alarm_zwei_nutzer(anlage, monkeypatch):
    mitschrift = aufzeichner_installieren(monkeypatch)
    uids = []
    for sprache in ("de", "en"):
        roh = _trip_roh()
        for k in FELDER:
            roh.pop(k, None)
            if k in anlage["trip"]:
                roh[k] = anlage["trip"][k]
        abrufe: list = []
        s, uid = _zeitplaner_senden(monkeypatch, roh, "evening", mitschrift=mitschrift,
                                    language=sprache, abrufe=abrufe)
        uids.append((uid, s["empfaenger"]))
        assert abrufe, f"{sprache}: Briefing holt bei Neuanlage keine amtlichen Warnungen"
        assert any(w in s["plain_text_body"] for w in WARN_TEXT), f"{sprache}: Warnung fehlt"
        trip = load_trip(roh, user_id=uid)
        assert TripAlertService._official_trigger_possible(trip) is True, f"{sprache}: Alarm aus"
    assert uids[0][0] != uids[1][0] and uids[0][1] != uids[1][1]
