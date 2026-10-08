"""Ortsvergleich mit gelöschten Orten: sprechender Grund, Teilverlust sichtbar (#2216).

Spec: docs/specs/modules/fix_2216_ort_loeschen_sperre.md (AC-5, AC-6, AC-7)

Einstieg wie im Betrieb: das Preset liegt als rohes JSON im Nutzerverzeichnis,
der Versand läuft über die ECHTE Kette (HTTP-Router -> ``send_compare_preset``
-> ``send_one_compare_preset``). Naht nur am Wetter (echte Engine-Subklasse) und
am Transport (geteilter Aufzeichner) — kein Mock-Theater, kein Netz.

Jeder datenbewegende Test läuft mit ZWEI Nutzern: der zweite hat dieselbe
Preset-/Ort-Kennung, aber vollständige Orte und darf nie ``fehlende_orte`` sehen.
"""
from __future__ import annotations

import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import scheduler
from app.loader import get_data_root
from services.compare_preview_service import ComparePreviewService
from tests.helpers.transport_mitschrift import Kanalmitschrift, aufzeichner_installieren
from tests.tdd._compare_kette_fixtures import (
    TARGET_DATE,
    alle_orte,
    engine_naht,
    fixture_dict,
    nutzer_anlegen,
    orte_anlegen,
    preset_ablegen,
    preset_laden,
    settings_fuer,
    transport_einrichten,
)

GELOESCHT = "loc-geloescht"


@pytest.fixture
def mit(monkeypatch) -> Kanalmitschrift:
    transport_einrichten(monkeypatch)
    engine_naht(monkeypatch)
    return aufzeichner_installieren(monkeypatch)


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(scheduler.router)
    return TestClient(app)


def _preset(uid: str, location_ids: list[str]) -> str:
    roh = fixture_dict("basis")
    roh["location_ids"] = location_ids
    preset_ablegen(uid, roh)
    return roh["id"]


def _senden(client: TestClient, uid: str, preset_id: str):
    return client.post(
        f"/api/scheduler/compare-presets/{preset_id}/send", params={"user_id": uid},
    )


# --- AC-5: alle Orte weg -> 422 mit sprechendem Grund -----------------------------


def test_versand_alle_orte_geloescht_422_mit_klarem_grund(mit, client):
    uid, fremd = nutzer_anlegen(), nutzer_anlegen()
    orte_anlegen(uid)
    orte_anlegen(fremd)
    pid = _preset(uid, [GELOESCHT, "loc-weg-2"])
    _preset(fremd, ["loc-ibk", "loc-bz"])

    r = _senden(client, uid, pid)

    assert r.status_code == 422, r.text  # NICHT 409 (sendOutcome deutet 409 als "läuft bereits")
    detail = r.json()["detail"]
    assert "verweist auf gelöschte Orte" in detail, detail
    assert "Ersetze die Orte" in detail, detail
    assert not mit.kanaele(), "bei 422 darf nichts versendet worden sein"


def test_vorschau_alle_orte_geloescht_klarer_grund():
    uid = nutzer_anlegen()
    orte_anlegen(uid)
    pid = _preset(uid, [GELOESCHT])

    with pytest.raises(ValueError) as exc:
        ComparePreviewService().render_email_preview(pid, user_id=uid)

    assert "verweist auf gelöschte Orte" in str(exc.value)
    assert "Ersetze die Orte" in str(exc.value)


# --- AC-6: Teilverlust -> Versand läuft, fehlende_orte im Ergebnis ----------------


def test_teilverlust_router_reicht_fehlende_orte_durch(mit, client):
    uid, fremd = nutzer_anlegen(), nutzer_anlegen()
    orte_anlegen(uid)
    orte_anlegen(fremd)
    pid = _preset(uid, ["loc-ibk", GELOESCHT])
    _preset(fremd, ["loc-ibk", "loc-bz"])

    r = _senden(client, uid, pid)

    assert r.status_code == 200, r.text
    assert r.json()["fehlende_orte"] == [GELOESCHT]
    assert mit.kanaele(), "mit dem übrigen Ort muss der Versand weiterlaufen"

    r2 = _senden(client, fremd, pid)
    assert r2.status_code == 200, r2.text
    assert not r2.json().get("fehlende_orte"), "anderer Nutzer: nichts fehlt"


def test_vollstaendig_aufloesbar_ohne_fehlende_orte(mit, client):
    uid = nutzer_anlegen()
    orte_anlegen(uid)
    pid = _preset(uid, ["loc-ibk", "loc-bz"])

    r = _senden(client, uid, pid)

    assert r.status_code == 200, r.text
    assert not r.json().get("fehlende_orte")


# --- AC-7: Scheduler-Lauf schreibt Warnung mit Preset-ID und fehlenden IDs --------


def test_teilverlust_scheduler_lauf_warnt_mit_preset_und_ids(mit, caplog):
    from services.scheduler_dispatch_service import send_one_compare_preset

    uid = nutzer_anlegen()
    orte_anlegen(uid)
    pid = _preset(uid, ["loc-ibk", GELOESCHT])

    with caplog.at_level(logging.WARNING):
        send_one_compare_preset(
            preset_laden(uid, pid), settings_fuer(uid), uid, str(get_data_root()),
            all_locations_cache=alle_orte(uid),
            target_date=TARGET_DATE, tage_ab_ortstag=0,
        )

    treffer = [
        rec for rec in caplog.records
        if rec.levelno == logging.WARNING and pid in rec.getMessage() and GELOESCHT in rec.getMessage()
    ]
    assert treffer, f"keine Warnung mit Preset-ID und fehlender Orts-ID: {[r.getMessage() for r in caplog.records]}"
