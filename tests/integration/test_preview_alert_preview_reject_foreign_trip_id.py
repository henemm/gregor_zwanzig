"""TDD RED — Issue #2140 Scheibe 2 (Entitaets-Achse), Python-Kern. SPEC:
docs/specs/modules/fix_2140_entitaets_id_pfadsperre.md AC-9.

Vier Routen laden eine Trip-ID roh in einen Dateipfad (Guard fehlt noch in
preview_service.py/validator.py):
- GET  /api/preview/{trip_id}/email
- GET  /api/preview/{trip_id}/sms
- GET  /api/preview/{trip_id}/telegram
- POST /api/trips/{trip_id}/alert-preview

Getestet wird ueber den ECHTEN HTTP-Stack (FastAPI TestClient), nicht als
Unit-Test der internen Funktion — die AC beschreibt Draht-Verhalten.

EMPIRISCHER BEFUND (an den Team-Lead zurueckgemeldet, Details im
RED-Bericht): fuer KEINE der vier Routen kann eine Trip-ID mit echtem "/"
den Handler ueberhaupt erreichen — Starlettes Router matcht
``{trip_id}`` nur gegen EIN Pfadsegment:
  - unkodiert (echte "/"-Zeichen im Pfad) erzeugt zu viele Segmente ->
    404 "Not Found" VOM ROUTER, die Anwendung (preview_service.py,
    validator.py) wird nie aufgerufen.
  - prozent-kodiert (%2F, %2e%2e%2f, doppelt kodiert %252F) wird von
    Starlette VOR dem Routing dekodiert und erzeugt dadurch ebenfalls zu
    viele Segmente -> wieder 404 "Not Found" VOM ROUTER (drei Varianten
    empirisch mit TestClient gemessen, alle identisch).
  - "." und ".." werden von Starlette als RFC-3986-Dot-Segmente VOR dem
    Routing aufgeloest und verschwinden komplett aus dem Pfad -> ebenfalls
    404 "Not Found" VOM ROUTER (anders als bei chi/Go, das KEINE
    Dot-Segment-Aufloesung durchfuehrt, siehe
    internal/handler/entity_traversal_test.go).
  - NUR ein Segment ohne "/" das trotzdem gegen ValidEntityID/
    VALID_ENTITY_ID_RE verstoesst (z.B. "..." oder ".hidden", KEIN
    RFC-3986-Dot-Segment) erreicht die Anwendung ueberhaupt — dort liefert
    der (noch fehlende) Guard KEINEN Sicherheitsgewinn gegen Fremdzugriff
    (ein solches Segment kann wegen des reinen id+".json"-Joins ohnehin nie
    aus dem EIGENEN Nutzerverzeichnis ausbrechen), sondern nur sauberere
    Statuscodes/Konsistenz mit der Go-Seite.
Der Guard in preview_service.py/validator.py ist damit fuer DIESE VIER
ROUTEN Verteidigung in der Tiefe (schuetzt z.B. gegen kuenftige
Routing-Aenderungen oder andere, nicht HTTP-geroutete Aufrufer), nicht das
Schliessen einer heute ueber diese Routen erreichbaren Luecke — anders als
bei AC-1/AC-2 (Go, Request-Body) oder AC-8 (Go, direkter Store-Aufruf). Die
Tests unten pruefen deshalb das AC-9-Ergebnis ("keine Route liefert Inhalt
des fremden Trips zurueck") als Regressions-/Verteidigungsnachweis, keine
RED-erzeugende Pruefung — konsistent mit AC-11 auf der Go-Seite.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import loader

VICTIM_MARKER = "VICTIM_SECRET_MARKER_2140"


@pytest.fixture
def client():
    from api.routers import preview, validator

    app = FastAPI()
    app.include_router(preview.router)
    app.include_router(validator.router)
    # raise_server_exceptions=False: eine ungeschuetzte, aber unerwartete
    # Fehlerform (z.B. eine Exception tief im Loader) soll als HTTP-Antwort
    # sichtbar werden, statt den Test selbst zum Absturz zu bringen.
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def victim_trip():
    """Legt einen echten Trip fuer Nutzer 'bob' im isolierten Test-Datenbaum
    an (tests/conftest.py::_isolate_data_root leitet app.loader._DATA_ROOT
    fuer JEDEN Test ohne @pytest.mark.real_data_root automatisch auf ein
    Temp-Verzeichnis um — kein Zugriff auf echte Daten)."""
    victim_user = "bob"
    victim_trip_id = "geheimer-trip"
    victim_dir = loader.get_briefings_dir(victim_user)
    victim_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": victim_trip_id,
        "name": VICTIM_MARKER,
        "stages": [
            {
                "id": "S1", "name": "Tag 1", "date": "2026-05-01",
                "waypoints": [
                    {"id": "W1", "name": "Start", "lat": 47.0, "lon": 11.0, "elevation_m": 500},
                    {"id": "W2", "name": "Ziel", "lat": 47.1, "lon": 11.1, "elevation_m": 800},
                ],
            }
        ],
    }
    (victim_dir / f"{victim_trip_id}.json").write_text(json.dumps(payload), encoding="utf-8")
    return victim_user, victim_trip_id, victim_dir


def _relpath_attack_id(victim_dir: Path, victim_trip_id: str, attacker_id: str) -> str:
    """Rechnet die Ausbruchs-ID relativ zum EIGENEN Verzeichnis des
    Angreifers aus (Regel A: nicht als Literal hinschreiben) — der Weg von
    get_briefings_dir(attacker_id) zu victim_dir/victim_trip_id."""
    attacker_dir = loader.get_briefings_dir(attacker_id)
    attacker_dir.mkdir(parents=True, exist_ok=True)
    return os.path.relpath(victim_dir / victim_trip_id, start=attacker_dir)


PREVIEW_PATHS = ["email", "sms", "telegram"]


def test_preview_routes_reject_relpath_traversal_trip_id_AC9(client, victim_trip):
    """AC-9 (Vorschau-Routen): eine auf Bobs echten Trip zielende, aus dem
    EIGENEN Verzeichnis des Angreifers berechnete relative ID darf niemals
    dessen Inhalt (VICTIM_MARKER) zurueckliefern."""
    victim_user, victim_trip_id, victim_dir = victim_trip
    attack_id = _relpath_attack_id(victim_dir, victim_trip_id, "attacker")

    for kind in PREVIEW_PATHS:
        r = client.get(
            f"/api/preview/{attack_id}/{kind}",
            params={"user_id": "attacker", "demo": True},
        )
        assert r.status_code != 200, (
            f"AC-9 {kind}: erwartet Ablehnung, bekam 200 mit body={r.text[:200]!r}"
        )
        assert VICTIM_MARKER not in r.text, (
            f"AC-9 {kind}: fremder Trip-Inhalt ist in der Antwort sichtbar: {r.text[:200]!r}"
        )


def test_alert_preview_rejects_relpath_traversal_trip_id_AC9(client, victim_trip):
    """AC-9 (Alert-Vorschau): dieselbe Ausbruchs-ID gegen
    POST /api/trips/{trip_id}/alert-preview."""
    victim_user, victim_trip_id, victim_dir = victim_trip
    attack_id = _relpath_attack_id(victim_dir, victim_trip_id, "attacker")

    r = client.post(
        f"/api/trips/{attack_id}/alert-preview",
        params={"user_id": "attacker"},
        json={},
    )
    assert r.status_code != 200, (
        f"AC-9 alert-preview: erwartet Ablehnung, bekam 200 mit body={r.text[:200]!r}"
    )
    assert VICTIM_MARKER not in r.text, (
        f"AC-9 alert-preview: fremder Trip-Inhalt ist in der Antwort sichtbar: {r.text[:200]!r}"
    )


def test_preview_and_alert_preview_reject_encoded_and_dotsegment_ids_AC9(client, victim_trip):
    """AC-9 Zusatzmessung (Regel B, empirisch statt angenommen): prozent-
    kodierte Trenner UND reine RFC-3986-Dot-Segmente ('.', '..') werden von
    Starlette VOR dem Routing aufgeloest/dekodiert und erreichen die Route
    deshalb gar nicht (404 vom Router). Ein Segment mit fuehrendem Punkt,
    das KEIN Dot-Segment ist (z.B. '...', '.hidden'), erreicht die Route
    sehr wohl — bleibt aber mangels echtem Trenner strukturell im eigenen
    Verzeichnis (id+'.json'-Join). Alle Varianten muessen die Ablehnungs-
    invariante erfuellen."""
    victim_user, victim_trip_id, victim_dir = victim_trip

    reachable_but_invalid = ["...", ".hidden"]
    blocked_by_router = [
        "..%2F..%2Fbob%2Fbriefings%2Fgeheimer-trip",
        "%2e%2e%2f%2e%2e%2fbob%2fbriefings%2fgeheimer-trip",
        ".",
        "..",
    ]

    for trip_id in reachable_but_invalid + blocked_by_router:
        r = client.get(
            f"/api/preview/{trip_id}/email",
            params={"user_id": "attacker", "demo": True},
        )
        assert r.status_code != 200, (
            f"AC-9 (trip_id={trip_id!r}): erwartet Ablehnung, bekam 200: {r.text[:200]!r}"
        )
        assert VICTIM_MARKER not in r.text, (
            f"AC-9 (trip_id={trip_id!r}): fremder Trip-Inhalt sichtbar: {r.text[:200]!r}"
        )
