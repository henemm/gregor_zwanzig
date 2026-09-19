"""Kern-Schicht: drei sendende Python-Routen verlangen ``user_id`` als Pflicht,
statt still auf ``"default"`` zurueckzufallen (#2151 Scheibe A).

Spec: docs/specs/modules/fix_2151_default_fallbacks_scheibe_a.md (AC-3, AC-4, AC-5)

Betroffen:
  * ``POST /api/scheduler/trips/{trip_id}/send``         (``user_id: str = "default"``)
  * ``POST /api/scheduler/compare-presets/{id}/send``    (``Query("default")``)
  * ``POST /api/debug/trigger-radar-alert``              (``user_id="default"``)

Nachweisform "nichts versendet" (AC-3): die 422 muss aus der FastAPI-
PARAMETERVALIDIERUNG stammen (``detail[].loc == ["query", "user_id"]``) --
die laeuft VOR dem Handler, also vor Trip-Lookup, SMTP-Check und Versand.
Beim Vergleichs-Versand zeichnet zusaetzlich eine echte Aufzeichner-Funktion
an der Versand-Naht auf (Muster ``test_antwort_an_den_fragenden.py``), dass
kein Versand startete; sie versendet selbst nie.

AC-4/AC-5 sind Regressionssicherungen (gruen vor UND nach dem Fix): in exakt
der Aufrufform des Go-Proxys (``?user_id=<id>`` als Query, kein Body,
``proxy.go:~264``/``compare_preset.go:~571``) erreicht der Request den
Handler -- fuer ``default`` wie fuer einen anderen echten Nutzer. Der
Handler-Nachweis nutzt einen Trip OHNE Etappen: der Handler antwortet mit
seinem eigenen 422 "keine Etappen" (Trip des richtigen Nutzers gefunden),
BEVOR irgendein Versand moeglich ist.

Kein ``Mock()``/``patch()``: echte Router in einer FastAPI-App, isolierte
Datenwurzel (``tests/conftest.py::_isolate_data_root``).
"""
from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import debug, scheduler
from app.loader import get_data_dir


@pytest.fixture
def client(monkeypatch):
    # Debug-Route ist staging-only; ausserhalb Staging antwortet der HANDLER
    # mit 404. GZ_ENV explizit setzen (ueberstimmt eine lokale .env).
    monkeypatch.setenv("GZ_ENV", "production")
    app = FastAPI()
    app.include_router(scheduler.router)
    app.include_router(debug.router)
    return TestClient(app)


@pytest.fixture
def vergleichs_versand(monkeypatch) -> list[tuple[str, str]]:
    """Echte Aufzeichner-Funktion an der Versand-Naht des Vergleichs-Routers
    (``scheduler.send_compare_preset``): zeichnet ``(user_id, preset_id)`` auf
    und versendet NICHTS -- auch vor dem Fix kann so keine echte Mail an eine
    lokal konfigurierte Adresse gehen. Kein ``Mock()``."""
    aufgerufen: list[tuple[str, str]] = []

    def _aufzeichner(user_id, preset_id, *args, **kwargs):
        aufgerufen.append((user_id, preset_id))
        return {"status": "aufgezeichnet", "preset_id": preset_id}

    monkeypatch.setattr(scheduler, "send_compare_preset", _aufzeichner)
    return aufgerufen


def _trip_ohne_etappen(user_id: str, trip_id: str) -> None:
    ordner = get_data_dir(user_id) / "briefings"
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / f"{trip_id}.json").write_text(json.dumps({
        "id": trip_id, "name": f"Stub {trip_id}", "stages": [],
    }))


def _ist_fehlender_user_id_parameter(resp) -> bool:
    if resp.status_code != 422:
        return False
    detail = resp.json().get("detail")
    return isinstance(detail, list) and any(
        list(d.get("loc", [])) == ["query", "user_id"] and d.get("type") == "missing"
        for d in detail
    )


# ═══════════════════════════ AC-3 ════════════════════════════════════════════


def test_ac3_trip_versand_ohne_user_id_ist_422_aus_der_validierung(client):
    """AC-3 (Trip-Versand).

    GIVEN beim Konto ``default`` liegt ein Trip ``t-leck``
    WHEN  ``POST /api/scheduler/trips/t-leck/send`` OHNE ``user_id`` eintrifft
    THEN  antwortet die Parametervalidierung mit 422 (fehlendes ``user_id``)
          -- der Handler (Trip-Lookup, SMTP-Check, Versand) laeuft nie.

    RED heute: der stille Default ``"default"`` findet den Trip und der
    Handler laeuft (Etappen-422 aus dem Handler, nicht aus der Validierung).
    """
    _trip_ohne_etappen("default", "t-leck")

    resp = client.post("/api/scheduler/trips/t-leck/send")

    assert _ist_fehlender_user_id_parameter(resp), (
        f"AC-3: ohne user_id muss die Parametervalidierung 422 liefern "
        f"(loc=['query','user_id']); erhalten {resp.status_code} {resp.text[:200]}"
    )


def test_ac3_vergleichs_versand_ohne_user_id_ist_422_ohne_versand(
    client, vergleichs_versand,
):
    """AC-3 (Vergleichs-Versand).

    RED heute: ``Query("default")`` ruft den Versand mit ``("default", …)``.
    """
    resp = client.post("/api/scheduler/compare-presets/cp-leck/send")

    assert _ist_fehlender_user_id_parameter(resp), (
        f"AC-3: ohne user_id muss die Parametervalidierung 422 liefern; "
        f"erhalten {resp.status_code} {resp.text[:200]}"
    )
    assert vergleichs_versand == [], (
        f"AC-3: ohne user_id darf kein Vergleichs-Versand starten: {vergleichs_versand}"
    )


def test_ac3_radar_debug_ausloeser_ohne_user_id_ist_422(client):
    """AC-3 (Debug-Radar-Ausloeser).

    RED heute: ``user_id="default"`` -- der Handler laeuft und antwortet
    (ausserhalb Staging) mit seinem eigenen 404 statt der Validierungs-422.
    """
    resp = client.post("/api/debug/trigger-radar-alert")

    assert _ist_fehlender_user_id_parameter(resp), (
        f"AC-3: ohne user_id muss die Parametervalidierung 422 liefern, bevor "
        f"der Handler laeuft; erhalten {resp.status_code} {resp.text[:200]}"
    )


# ═══════════════════ AC-4 / AC-5 (Regressionssicherung) ══════════════════════


@pytest.mark.parametrize("user_id", ["default", "nutzer-proxy"])
def test_ac4_ac5_trip_versand_in_proxy_aufrufform_erreicht_den_handler(client, user_id):
    """AC-4/AC-5: ``?user_id=<id>`` (Go-Proxy-Form) erreicht den Handler mit
    genau diesem Nutzer -- fuer ``default`` wie fuer einen anderen Nutzer.
    Der Trip liegt NUR bei ``user_id``; der Handler findet ihn (sonst 404) und
    antwortet mit seinem Etappen-422."""
    _trip_ohne_etappen(user_id, "t-proxy")

    resp = client.post(f"/api/scheduler/trips/t-proxy/send?user_id={user_id}")

    assert resp.status_code == 422 and "keine Etappen" in resp.text, (
        f"AC-4/5: ?user_id={user_id} muss den Handler mit dem Trip dieses "
        f"Nutzers erreichen; erhalten {resp.status_code} {resp.text[:200]}"
    )


def test_ac5_trip_versand_liest_nur_den_trip_des_uebergebenen_nutzers(client):
    """AC-5 (Gegenprobe): liegt der Trip nur beim anderen Nutzer, findet ein
    Aufruf mit ``?user_id=default`` ihn NICHT (404)."""
    _trip_ohne_etappen("nutzer-proxy", "t-nur-fremd")

    resp = client.post("/api/scheduler/trips/t-nur-fremd/send?user_id=default")

    assert resp.status_code == 404, (
        f"AC-5: Trip von nutzer-proxy darf fuer user_id=default nicht sichtbar "
        f"sein; erhalten {resp.status_code} {resp.text[:200]}"
    )


@pytest.mark.parametrize("user_id", ["default", "nutzer-proxy"])
def test_ac4_ac5_vergleichs_versand_in_proxy_aufrufform_erreicht_den_handler(
    client, vergleichs_versand, user_id,
):
    """AC-4/AC-5: ``?user_id=<id>`` gibt genau diese Kennung an den
    Vergleichs-Versand weiter (Aufzeichner, kein echter Versand)."""
    resp = client.post(f"/api/scheduler/compare-presets/cp-proxy/send?user_id={user_id}")

    assert resp.status_code == 200, (
        f"AC-4/5: ?user_id={user_id} muss den Handler erreichen; "
        f"erhalten {resp.status_code} {resp.text[:200]}"
    )
    assert vergleichs_versand == [(user_id, "cp-proxy")], (
        f"AC-4/5: der Handler muss mit user_id={user_id!r} dispatchen: "
        f"{vergleichs_versand}"
    )


@pytest.mark.parametrize("user_id", ["default", "nutzer-proxy"])
def test_ac4_radar_debug_ausloeser_mit_user_id_erreicht_den_handler(client, user_id):
    """AC-4: mit explizitem ``user_id`` laeuft der Handler (ausserhalb Staging
    antwortet ER mit 404 -- keine Validierungs-422)."""
    resp = client.post(f"/api/debug/trigger-radar-alert?user_id={user_id}")

    assert resp.status_code == 404, (
        f"AC-4: mit user_id={user_id} muss der Handler laufen (Staging-Guard "
        f"404); erhalten {resp.status_code} {resp.text[:200]}"
    )
