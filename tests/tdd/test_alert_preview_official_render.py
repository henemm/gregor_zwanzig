"""TDD-RED: Issue #1948 Scheibe S2 — AC-4/AC-5 Zweig b (amtliche Warnung)
am Preview-Endpoint.

SPEC: docs/specs/modules/alarm_testeinspeisung.md

AC-4: ``official``-Payload liefert alle fuenf Kanal-Felder nicht-leer, mit
Inhalten die hazard/level/label widerspiegeln (Struktur-/Wertevergleich
gegen bekannte Renderer-Vokabeln, kein geratener String-Contains).

AC-5 (Fidelity): dieselbe ``OfficialAlert``-Eingabe ueber den Preview-
Endpoint UND direkt ueber ``build_official_alert_notices`` + die vier
Vorlagen-Renderer (#1929-Sperrzone bleibt unangetastet, wird nur
AUFGERUFEN) muessen byte-identische SMS-/Telegram-/HTML-/Plain-Ausgaben
liefern.

RED-Grund: ``AlertPreviewBody`` kennt heute kein ``official``-Feld (Pydantic
ignoriert es); mit leerem ``changes``/``onset`` liefert der Endpunkt 422
statt 200.

Kein Mock — echter FastAPI-TestClient, echte Renderer-Aufrufe, echte
Trip-Fixture.
"""
from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

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


@pytest.fixture
def stub_trip():
    user_id = f"test_1948s2ac4_{uuid.uuid4().hex[:8]}"
    trip_id = "trip-ac4"
    trip_dir = Path("data/users") / user_id / "briefings"
    trip_dir.mkdir(parents=True, exist_ok=True)
    (trip_dir / f"{trip_id}.json").write_text(json.dumps({
        "id": trip_id, "name": "AC-4 Trip", "stages": [],
    }))
    yield user_id, trip_id
    shutil.rmtree(Path("data/users") / user_id, ignore_errors=True)


class TestAC4_OfficialRenderAllFiveFields:
    def test_official_payload_renders_all_five_fields_reflecting_hazard_level_label(
        self, client, stub_trip,
    ):
        from output.tokens.hazard_symbols import HAZARD_SMS_SYMBOLS
        from output.renderers.alert.official_alerts import _LEVEL_WORDS

        user_id, trip_id = stub_trip
        resp = client.post(
            f"/api/trips/{trip_id}/alert-preview",
            params={"user_id": user_id},
            json={"official": [OFFICIAL_PAYLOAD]},
        )
        assert resp.status_code == 200, f"Body: {resp.text[:300]}"
        data = resp.json()
        for field in ("subject", "email_html", "email_plain", "telegram", "sms"):
            assert field in data, f"Feld '{field}' fehlt in der Antwort: {list(data)}"
            assert isinstance(data[field], str) and data[field], (
                f"AC-4: '{field}' darf nicht leer sein: {data[field]!r}"
            )

        level_word = _LEVEL_WORDS[OFFICIAL_PAYLOAD["level"]][1]  # "ORANGE" fuer Stufe 3
        sms_symbol = HAZARD_SMS_SYMBOLS[OFFICIAL_PAYLOAD["hazard"]]  # "TH" fuer thunderstorm

        assert data["subject"].startswith("["), (
            f"Betreff muss mit '[<Trip>]' beginnen: {data['subject']!r}"
        )
        assert level_word in data["subject"], (
            f"AC-4: Betreff muss die Warnstufe '{level_word}' (Stufe "
            f"{OFFICIAL_PAYLOAD['level']}) nennen: {data['subject']!r}"
        )
        assert OFFICIAL_PAYLOAD["label"] in data["telegram"], (
            f"AC-4: Telegram muss das Label '{OFFICIAL_PAYLOAD['label']}' "
            f"nennen: {data['telegram']!r}"
        )
        assert OFFICIAL_PAYLOAD["label"] in data["email_plain"], (
            f"AC-4: email_plain muss das Label '{OFFICIAL_PAYLOAD['label']}' "
            f"nennen: {data['email_plain']!r}"
        )
        assert re.search(rf"\b{sms_symbol}\b|{sms_symbol}!", data["sms"]), (
            f"AC-4: SMS muss das Hazard-Kuerzel '{sms_symbol}' "
            f"(thunderstorm) tragen: {data['sms']!r}"
        )


class TestAC5_FidelityWithDirectRenderPath:
    def test_official_preview_matches_direct_renderer_calls_byte_identical(
        self, client, stub_trip,
    ):
        user_id, trip_id = stub_trip
        resp = client.post(
            f"/api/trips/{trip_id}/alert-preview",
            params={"user_id": user_id},
            json={"official": [OFFICIAL_PAYLOAD]},
        )
        assert resp.status_code == 200, f"Body: {resp.text[:300]}"
        data = resp.json()

        from api.routers.validator import _load_trip_for_validator
        from output.renderers.alert.official_alerts import (
            build_official_alert_notices, render_official_alert_mail_plain,
            render_official_alert_sms, render_official_alert_subject,
            render_official_alert_telegram, render_warn_block,
        )
        from services.notification_service import (
            _official_source_label_for, _official_source_url_for,
        )
        from services.official_alerts.models import OfficialAlert
        from services.validator_render_service import _alert_tz_for_trip
        from utils.timezone import local_fmt

        trip_obj = _load_trip_for_validator(user_id, trip_id)
        assert trip_obj is not None, "Fixtur-Schutz: Trip muss ladbar sein"

        alert = OfficialAlert(
            source=OFFICIAL_PAYLOAD["source"], hazard=OFFICIAL_PAYLOAD["hazard"],
            level=OFFICIAL_PAYLOAD["level"], label=OFFICIAL_PAYLOAD["label"],
        )
        dto_notices = build_official_alert_notices(
            trip_obj, [(alert, OFFICIAL_PAYLOAD["segment_ids"])],
        )
        source_label = _official_source_label_for(dto_notices)
        source_url = _official_source_url_for(dto_notices)
        alert_tz = _alert_tz_for_trip(trip_obj)
        stand_at = local_fmt(datetime.now(timezone.utc), alert_tz)

        expected_subject = render_official_alert_subject(
            dto_notices, prefix=trip_obj.name, tz=alert_tz,
        )
        expected_html = render_warn_block(
            dto_notices, variant="standalone", source_label=source_label,
            source_url=source_url, stand_at=stand_at, tz=alert_tz,
            context_label=trip_obj.name,
        )
        expected_plain = render_official_alert_mail_plain(
            dto_notices, source_label=source_label, stand_at=stand_at,
            tz=alert_tz, context_label=trip_obj.name,
        )
        expected_telegram = render_official_alert_telegram(
            dto_notices, prefix=trip_obj.name, source_label=source_label, tz=alert_tz,
        )
        expected_sms = render_official_alert_sms(
            dto_notices, sms_prefix=trip_obj.name, tz=alert_tz,
        )

        def _strip_stand(text: str) -> str:
            """Neutralisiert 'Stand: heute HH:MM' -- Wanduhr-Ratsche: die
            direkt gerechnete Erwartung und der Endpoint-Aufruf koennen
            theoretisch ueber eine Minutengrenze hinweg auseinanderfallen;
            der Rest der Ausgabe bleibt strikt byte-identisch."""
            return re.sub(r"Stand:\s*heute\s*\d{2}:\d{2}", "Stand: heute <ZEIT>", text)

        assert data["subject"] == expected_subject, (
            f"AC-5: Betreff weicht vom direkten Renderer-Aufruf ab.\n"
            f"Endpoint: {data['subject']!r}\nDirekt:   {expected_subject!r}"
        )
        assert data["sms"] == expected_sms, (
            f"AC-5: SMS weicht vom direkten Renderer-Aufruf ab.\n"
            f"Endpoint: {data['sms']!r}\nDirekt:   {expected_sms!r}"
        )
        assert data["telegram"] == expected_telegram, (
            f"AC-5: Telegram weicht vom direkten Renderer-Aufruf ab.\n"
            f"Endpoint: {data['telegram']!r}\nDirekt:   {expected_telegram!r}"
        )
        assert _strip_stand(data["email_html"]) == _strip_stand(expected_html), (
            f"AC-5: HTML weicht vom direkten Renderer-Aufruf ab (Stand-"
            f"Zeitstempel neutralisiert).\nEndpoint: {data['email_html'][:400]!r}\n"
            f"Direkt:   {expected_html[:400]!r}"
        )
        assert _strip_stand(data["email_plain"]) == _strip_stand(expected_plain), (
            f"AC-5: email_plain weicht vom direkten Renderer-Aufruf ab "
            f"(Stand-Zeitstempel neutralisiert).\n"
            f"Endpoint: {data['email_plain'][:400]!r}\n"
            f"Direkt:   {expected_plain[:400]!r}"
        )
