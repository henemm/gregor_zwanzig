"""TDD-RED: Issue #1948 Scheibe S2 — AC-9 Seiteneffektfreiheit und AC-10
Mandantentrennung fuer die NEUEN Payload-Typen (``official``,
``nowcast_frames``) am Preview-Endpoint.

SPEC: docs/specs/modules/alarm_testeinspeisung.md

AC-9: kein Versand, kein ``alert_log``-Eintrag, keine Throttle-Markierung --
fuer ``official`` UND ``nowcast_frames`` genauso wie fuer die Alt-Typen.
AC-10: fremder User -> 404; jeder eigene User bekommt fuer BEIDE neuen Typen
ein korrektes Rendering.

RED-Grund: beide neuen Typen liefern heute 422 (unbekanntes Feld, leere
Alt-Felder) statt 200 -- die Seiteneffekt-Pruefung waere ohne den
vorgeschalteten Status-200-Nachweis trivial erfuellt (auf einer 422-Antwort
passiert nie etwas). Jede Testfunktion assertet deshalb ZUERST 200, bevor
sie Abwesenheit von Seiteneffekten behauptet.

Kein Mock — echter FastAPI-TestClient, echte Trip-Fixtures, echte
Dateisystem-Pruefung von ``alert_log.json``/``alert_throttle.json``.
"""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.loader import get_data_dir

pytestmark = pytest.mark.real_data_root

OFFICIAL_PAYLOAD = {
    "source": "geosphere_warn", "hazard": "thunderstorm", "level": 3,
    "label": "Gewitter", "segment_ids": ["1"],
}


@pytest.fixture
def client():
    from api.routers import validator
    app = FastAPI()
    app.include_router(validator.router)
    return TestClient(app)


def _write_stub_trip(user_id: str, trip_id: str, name: str) -> None:
    trip_dir = Path("data/users") / user_id / "briefings"
    trip_dir.mkdir(parents=True, exist_ok=True)
    (trip_dir / f"{trip_id}.json").write_text(json.dumps({
        "id": trip_id, "name": name, "stages": [],
    }))


def _nowcast_body() -> dict:
    now = datetime.now(timezone.utc)
    return {"nowcast_frames": {
        "source": "radar",
        "frames": [
            {"timestamp": (now + timedelta(minutes=15)).isoformat(),
             "precip_mm_h": 2.0, "is_convective": False},
        ],
    }}


@pytest.fixture
def two_users():
    uid_a = f"test_1948s2ac9a_{uuid.uuid4().hex[:8]}"
    uid_b = f"test_1948s2ac9b_{uuid.uuid4().hex[:8]}"
    trip_a, trip_b = "trip-a", "trip-b"
    _write_stub_trip(uid_a, trip_a, "Trip A")
    _write_stub_trip(uid_b, trip_b, "Trip B")
    yield (uid_a, trip_a), (uid_b, trip_b)
    shutil.rmtree(Path("data/users") / uid_a, ignore_errors=True)
    shutil.rmtree(Path("data/users") / uid_b, ignore_errors=True)


class TestAC9_NoSideEffects:
    @pytest.mark.parametrize(
        "body_factory,label",
        [
            (lambda: {"official": [OFFICIAL_PAYLOAD]}, "official"),
            (_nowcast_body, "nowcast_frames"),
        ],
        ids=["official", "nowcast_frames"],
    )
    def test_no_alert_log_or_throttle_write_for_new_payload_types(
        self, client, two_users, body_factory, label,
    ):
        (uid_a, trip_a), _ = two_users
        alert_log = get_data_dir(uid_a) / "alert_log.json"
        throttle = get_data_dir(uid_a) / "alert_throttle.json"
        assert not alert_log.exists(), "Fixtur-Schutz: kein Alt-Log vorhanden"
        assert not throttle.exists(), "Fixtur-Schutz: keine Alt-Throttle-Datei vorhanden"

        resp = client.post(
            f"/api/trips/{trip_a}/alert-preview",
            params={"user_id": uid_a}, json=body_factory(),
        )
        assert resp.status_code == 200, (
            f"AC-9 ({label}): Request muss 200 liefern, sonst prueft der "
            f"Seiteneffekt-Nachweis nichts (leere Menge waere trivial wahr). "
            f"War {resp.status_code}: {resp.text[:300]}"
        )
        assert not alert_log.exists(), (
            f"AC-9 ({label}): alert_log.json wurde geschrieben -- "
            "verbotener Seiteneffekt eines zustandslosen Preview-Requests."
        )
        assert not throttle.exists(), (
            f"AC-9 ({label}): alert_throttle.json wurde geschrieben -- "
            "verbotener Seiteneffekt eines zustandslosen Preview-Requests."
        )


class TestAC10_MandantentrennungFuerNeueTypen:
    def test_cross_user_denied_and_each_user_self_access_renders_correctly(
        self, client, two_users,
    ):
        (uid_a, trip_a), (uid_b, trip_b) = two_users

        cross_resp = client.post(
            f"/api/trips/{trip_b}/alert-preview",
            params={"user_id": uid_a}, json={"official": [OFFICIAL_PAYLOAD]},
        )
        assert cross_resp.status_code == 404, (
            f"AC-10: Nutzer A darf den Trip von Nutzer B nicht sehen, bekam "
            f"{cross_resp.status_code}: {cross_resp.text[:200]}"
        )

        for uid, trip_id, name in ((uid_a, trip_a, "Trip A"), (uid_b, trip_b, "Trip B")):
            resp_official = client.post(
                f"/api/trips/{trip_id}/alert-preview",
                params={"user_id": uid}, json={"official": [OFFICIAL_PAYLOAD]},
            )
            assert resp_official.status_code == 200, (
                f"AC-10: Self-Access 'official' fuer {uid} muss 200 "
                f"liefern, war {resp_official.status_code}: "
                f"{resp_official.text[:300]}"
            )
            assert f"[{name}]" in resp_official.json()["subject"], (
                f"AC-10: Betreff muss den EIGENEN Trip-Namen '{name}' "
                f"tragen: {resp_official.json()['subject']!r}"
            )

            resp_nowcast = client.post(
                f"/api/trips/{trip_id}/alert-preview",
                params={"user_id": uid}, json=_nowcast_body(),
            )
            assert resp_nowcast.status_code == 200, (
                f"AC-10: Self-Access 'nowcast_frames' fuer {uid} muss 200 "
                f"liefern, war {resp_nowcast.status_code}: "
                f"{resp_nowcast.text[:300]}"
            )
            assert resp_nowcast.json().get("onset_detected") is True, (
                f"AC-10: Onset muss fuer {uid}s eigenen Trip erkannt "
                f"werden: {resp_nowcast.json()!r}"
            )
