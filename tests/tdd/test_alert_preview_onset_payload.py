"""Der DIREKTE Onset-Payload am Vorschau-Endpunkt traegt die Mengenangabe.

SPEC: docs/specs/modules/fix_2046_onset_menge.md — AC-10, Zweig „direkter
Vorschau-Payload" (`OnsetPayload` mit `onset_precip_mm`).

Warum eine eigene Datei: `test_alert_preview_nowcast_replay.py` deckt den
ZWEITEN Zweig desselben ACs ab (`nowcast_frames`-Replay) — und der laeuft
ueber einen `SimpleNamespace`, beruehrt den Pydantic-Validierungsweg des
Endpunkts also gar nicht. Der Adversary (Finding F002) konnte deshalb das
Feld `OnsetPayload.onset_precip_mm` vollstaendig entfernen, ohne dass ein
Test rot wurde: Pydantic verwirft ein unbekanntes Feld still, und die Zahl
verschwindet lautlos aus der Vorschau.

Kein Mock — echter FastAPI-TestClient, echter Endpunkt, echte Trip-Fixture
auf Platte, echter Renderer. Geprueft wird das Antwortfeld, das der Nutzer
in der Vorschau liest.
"""
from __future__ import annotations

import json
import re
import shutil
import uuid
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytestmark = pytest.mark.real_data_root


@pytest.fixture
def client():
    from api.routers import validator
    app = FastAPI()
    app.include_router(validator.router)
    return TestClient(app)


@pytest.fixture
def stub_trip():
    user_id = f"test_2046_onset_{uuid.uuid4().hex[:8]}"
    trip_id = "trip-2046-onset"
    trip_dir = Path("data/users") / user_id / "briefings"
    trip_dir.mkdir(parents=True, exist_ok=True)
    (trip_dir / f"{trip_id}.json").write_text(json.dumps({
        "id": trip_id, "name": "Vorschau-Trip", "stages": [],
    }))
    yield user_id, trip_id
    shutil.rmtree(Path("data/users") / user_id, ignore_errors=True)


def _onset_body(**overrides) -> dict:
    onset = {
        "onset_minutes": 25,
        "onset_time": "18:00",
        "km_from": 0.0,
        "km_to": 6.0,
        "is_convective": False,
        "intensity_label": "mäßiger Regen",
        "source_label": "Radar (DWD)",
    }
    onset.update(overrides)
    return {"onset": onset}


class TestAC10DirekterOnsetPayload:
    def test_onset_payload_mit_menge_erreicht_die_kurznachricht(
        self, client, stub_trip,
    ):
        """AC-10 GIVEN einen direkten Vorschau-Payload
        (`{"onset": {..., "onset_precip_mm": 3.1}}`, OHNE `nowcast_frames`)
        WHEN `POST /api/trips/{trip_id}/alert-preview` ihn rendert
        THEN traegt das Antwortfeld `sms` das Token `R3.1@18:00` — dieselbe
        Zahl-Grammatik wie der Produktivpfad; der Testeinspeiseweg verliert
        die Zahl nicht zwischen Pydantic-Modell und Renderer.

        Deckt Adversary-Finding F002: ohne diesen Test liesse sich das Feld
        `OnsetPayload.onset_precip_mm` ersatzlos streichen, ohne dass etwas
        rot wird — Pydantic verwirft den unbekannten Schluessel still.
        """
        user_id, trip_id = stub_trip
        resp = client.post(
            f"/api/trips/{trip_id}/alert-preview",
            params={"user_id": user_id},
            json=_onset_body(onset_precip_mm=3.1),
        )

        assert resp.status_code == 200, f"Body: {resp.text[:300]}"
        sms = resp.json().get("sms") or ""
        assert "R3.1@18:00" in sms, (
            "F002: der direkte Onset-Payload verliert die Mengenangabe auf dem "
            f"Weg zum Renderer: {sms!r}"
        )
        assert "R@18:00" not in sms, (
            f"Die zahlenlose Alt-Form steht noch in der Kurznachricht: {sms!r}"
        )

    def test_onset_payload_ohne_menge_bleibt_bei_der_alt_form(
        self, client, stub_trip,
    ):
        """AC-10/AC-11 GIVEN denselben Payload OHNE `onset_precip_mm`
        WHEN derselbe Endpunkt rendert
        THEN bleibt die zahlenlose Alt-Form `R@18:00` stehen — Gegenprobe,
        damit die Zusicherung oben nicht trivial aus einer beliebigen Zahl
        irgendwo im Text erfuellt wird, und Regressionsschutz fuer
        Alt-Aufrufer, die das optionale Feld nicht setzen.
        """
        user_id, trip_id = stub_trip
        resp = client.post(
            f"/api/trips/{trip_id}/alert-preview",
            params={"user_id": user_id},
            json=_onset_body(),
        )

        assert resp.status_code == 200, f"Body: {resp.text[:300]}"
        sms = resp.json().get("sms") or ""
        assert "R@18:00" in sms, (
            f"Ohne Mengenangabe muss die Alt-Form erhalten bleiben: {sms!r}"
        )
        assert not re.search(r"\bR\d", sms), (
            f"Ohne Mengenangabe darf keine Zahl hinter dem Kuerzel stehen: {sms!r}"
        )
