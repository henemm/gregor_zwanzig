"""TDD RED — Issue #2406: interner Versand-Endpunkt fuer den SMS-Bestaetigungscode.

Spec: docs/specs/modules/sms_nummer_verifikation.md §8 —
`POST /api/_internal/sms/verification-code` mit `{"user_id","to","code"}`.
Der Go-Prozess erzeugt und prueft den Code, Python bleibt der einzige
seven.io-Transport (ADR-0062/ADR-0076).

Echte FastAPI-App mit dem echten Router (Muster
tests/tdd/test_internal_loaded_endpoint.py); der seven.io-Transport
(`httpx.post`) ist ein Sentinel, der Kopfzeilen und Nutzlast festhaelt und eine
echte httpx-Antwort zurueckgibt — kein Netz, aber der vollstaendige Kanal-Code
davor laeuft (beide Sandbox-Sperren, Empfaengeraufloesung, Absender).

RED heute: die Route existiert nicht → 404.

Ausfuehren:
  uv run pytest tests/test_sms_verification_code_endpoint.py -v -rA --disable-socket
"""
from __future__ import annotations

import json

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.loader import get_data_dir

PFAD = "/api/_internal/sms/verification-code"
ZIEL = "+491511234567"
CODE = "428913"
SANDBOX = "sandbox-key-2406"


@pytest.fixture
def transport(monkeypatch):
    """Sentinel auf `httpx.post`: haelt jeden Aufruf fest und antwortet wie
    seven.io im Erfolgsfall ("100")."""
    aufrufe: list[dict] = []

    def _sentinel(url, headers=None, data=None, timeout=None, **kwargs):
        aufrufe.append({"url": url, "headers": headers or {}, "data": data or {}})
        return httpx.Response(200, text="100", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", _sentinel)
    return aufrufe


@pytest.fixture
def umgebung(monkeypatch):
    """seven.io-Zugang aus der Umgebung (das Modul baut sein `Settings()`
    selbst) — bewusst Fantasie-Schluessel, Sandbox == API-Key, damit die beiden
    seven.io-Sperren durchlaufen und der Test die Endpunkt-Logik misst."""
    monkeypatch.setenv("GZ_SMS_GATEWAY_URL", "https://gateway.seven.io/api/sms")
    monkeypatch.setenv("GZ_SEVEN_API_KEY", SANDBOX)
    monkeypatch.setenv("GZ_SEVEN_SANDBOX_KEY", SANDBOX)
    monkeypatch.setenv("GZ_ENV", "production")


@pytest.fixture
def client(umgebung):
    from api.routers import internal

    app = FastAPI()
    app.include_router(internal.router)
    return TestClient(app)


def _profil(user_id: str, **felder) -> None:
    pfad = get_data_dir(user_id) / "user.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    profil = {"id": user_id, "display_name": f"Konto {user_id}", "tier": "standard"}
    profil.update(felder)
    pfad.write_text(json.dumps(profil, indent=2), encoding="utf-8")


def test_endpunkt_versendet_code_an_die_uebergebene_nummer(client, transport):
    """§8: die Zielnummer kommt aus dem Aufruf, nicht aus dem Profil — bei
    `pending_sms_to` steht sie noch gar nicht als `sms_to` in user.json."""
    _profil("intsms1", sms_to="", pending_sms_to=ZIEL)

    antwort = client.post(PFAD, json={"user_id": "intsms1", "to": ZIEL, "code": CODE})
    assert antwort.status_code == 200, (
        f"§8: erwartet 200, bekommen {antwort.status_code}: {antwort.text}"
    )
    assert antwort.json() == {"status": "sent"}
    assert len(transport) == 1, f"§8: genau ein seven.io-Aufruf erwartet, bekommen {transport}"
    nutzlast = transport[0]["data"]
    assert nutzlast["to"] == ZIEL, (
        f"§8: der Code muss an die uebergebene Nummer gehen, ging an {nutzlast['to']!r}"
    )
    assert CODE in nutzlast["text"], (
        f"§8: die Nachricht muss den Bestaetigungscode tragen, bekommen {nutzlast['text']!r}"
    )


def test_endpunkt_adressiert_nie_die_im_profil_gespeicherte_fremde_nummer(client, transport):
    """Gegenprobe zur Mandantentrennung: ein im Profil stehendes `sms_to` darf
    den uebergebenen Wert nicht ueberschreiben."""
    _profil("intsms2", sms_to="+499999999999", sms_verified_number="+499999999999")

    antwort = client.post(PFAD, json={"user_id": "intsms2", "to": ZIEL, "code": CODE})
    assert antwort.status_code == 200, f"bekommen {antwort.status_code}: {antwort.text}"
    assert transport[0]["data"]["to"] == ZIEL, (
        "§8: model_copy(update={'sms_to': req.to}) muss die Zielnummer bestimmen, "
        f"gesendet an {transport[0]['data']['to']!r}"
    )


def test_endpunkt_meldet_fehlende_sms_konfiguration_mit_422(monkeypatch, transport):
    """§8: ohne sendefaehige Konfiguration 422 `sms_not_configured`, kein Versand."""
    monkeypatch.setenv("GZ_SMS_GATEWAY_URL", "")
    monkeypatch.setenv("GZ_SEVEN_API_KEY", "")
    monkeypatch.setenv("GZ_SEVEN_SANDBOX_KEY", "")
    monkeypatch.setenv("GZ_ENV", "production")
    from api.routers import internal

    app = FastAPI()
    app.include_router(internal.router)
    c = TestClient(app)

    antwort = c.post(PFAD, json={"user_id": "intsms3", "to": ZIEL, "code": CODE})
    assert antwort.status_code == 422, (
        f"§8: ohne SMS-Konfiguration erwartet 422, bekommen {antwort.status_code}: {antwort.text}"
    )
    assert antwort.json().get("error") == "sms_not_configured"
    assert transport == [], f"§8: ohne Konfiguration darf nichts versandt werden: {transport}"


def test_endpunkt_meldet_transportfehler_mit_502(client, monkeypatch):
    """§8: scheitert seven.io, antwortet der Endpunkt 502 `sms_send_failed`
    (der Code bleibt in Go gueltig, der Nutzer kann „erneut senden")."""
    def _fehler(url, headers=None, data=None, timeout=None, **kwargs):
        return httpx.Response(500, text="nope", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", _fehler)
    _profil("intsms4", sms_to="", pending_sms_to=ZIEL)

    antwort = client.post(PFAD, json={"user_id": "intsms4", "to": ZIEL, "code": CODE})
    assert antwort.status_code == 502, (
        f"§8: seven.io-Fehler erwartet 502, bekommen {antwort.status_code}: {antwort.text}"
    )
    assert antwort.json().get("error") == "sms_send_failed"


def test_endpunkt_behaelt_die_staging_sandbox_weiche(monkeypatch, transport):
    """§8: die `env == staging`-Sandbox-Weiche aus `with_user_profile` bleibt
    erhalten — auf Staging geht der Aufruf mit dem SANDBOX-Schluessel raus,
    auch wenn ein anderer API-Key konfiguriert ist."""
    monkeypatch.setenv("GZ_SMS_GATEWAY_URL", "https://gateway.seven.io/api/sms")
    monkeypatch.setenv("GZ_SEVEN_API_KEY", "prod-key-darf-nicht-rausgehen")
    monkeypatch.setenv("GZ_SEVEN_SANDBOX_KEY", SANDBOX)
    monkeypatch.setenv("GZ_ENV", "staging")
    from api.routers import internal

    app = FastAPI()
    app.include_router(internal.router)
    c = TestClient(app)
    _profil("intsms5", sms_to="", pending_sms_to=ZIEL)

    antwort = c.post(PFAD, json={"user_id": "intsms5", "to": ZIEL, "code": CODE})
    assert antwort.status_code == 200, f"bekommen {antwort.status_code}: {antwort.text}"
    assert transport[0]["headers"].get("X-Api-Key") == SANDBOX, (
        "§8: auf Staging muss der Sandbox-Schluessel verwendet werden, benutzt wurde "
        f"{transport[0]['headers'].get('X-Api-Key')!r}"
    )
