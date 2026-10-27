"""TDD RED — Issue #2283 Scheibe S4, AC-16 (Python-Teil).

Spec: docs/specs/modules/shared_preview_tab.md

Gewaehlte Python-Route (Go-Dispatcher `POST /api/briefings/{id}/alert-preview
?kind=` proxied 1:1 darauf, `user_id` injiziert der Go-Proxy):

    POST /api/briefings/{entity_id}/alert-preview?kind=route|vergleich&user_id=<uid>

- kind=route: Body und Antwort exakt wie die Alt-Route
  `POST /api/trips/{trip_id}/alert-preview` (die als Delegate unveraendert
  bleibt).
- kind=vergleich: orts-bezogener Body (Vertrag in
  tests/tdd/test_alert_preview_compare_paritaet.py), Antwort =
  `services.compare_alert_preview_service.render_compare_alert_preview(...)`.

Die Route darf im `preview`- oder `validator`-Router liegen — beide sind hier
eingebunden. `kind` ist Pflicht (Go antwortet vorher mit 400 `kind_required`;
der Kern lehnt einen fehlenden/falschen Wert ebenfalls ab).

Zwei echte Nutzer, beide kinds: Eigentuemer → 200 mit eigenem Inhalt
(Gegenprobe, heute ROT), fremde ID → 404 ohne Fremddaten.

RED-Grund: Route fehlt → 404 vom Router, auch fuer den Eigentuemer.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.user import SavedLocation

from tests.helpers.vorschau_umgebung import (
    env,  # noqa: F401  (pytest-Fixture, isolierter Daten-Root)
    seed_compare,
    seed_trip,
)

TRIP_ALERT_BODY = {
    "changes": [{
        "metric": "gust_max_kmh", "old_value": 25.0, "new_value": 72.0, "delta": 47.0,
        "threshold": 60.0, "severity": "major", "direction": "increase", "segment_id": "1",
    }],
    "segment_times": [{"segment_id": "1", "start": "08:00", "end": "12:00"}],
}


def _compare_body(loc_id: str) -> dict:
    return {"changes": [{
        "location_id": loc_id, "metric": "gust_max_kmh", "old_value": 25.0,
        "new_value": 72.0, "delta": 47.0, "threshold": 60.0, "severity": "major",
        "direction": "increase",
    }]}


@pytest.fixture
def client():
    from api.routers import preview, validator

    app = FastAPI()
    app.include_router(preview.router)
    app.include_router(validator.router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def two_users(env):  # noqa: F811
    suffix = uuid.uuid4().hex[:6]
    return f"tdd-2283-alarm-a-{suffix}", f"tdd-2283-alarm-b-{suffix}"


def _post(client, entity_id: str, kind: str | None, user_id: str, body: dict):
    params = {"user_id": user_id}
    if kind is not None:
        params["kind"] = kind
    return client.post(f"/api/briefings/{entity_id}/alert-preview", params=params, json=body)


def test_compare_alert_preview_owner_gets_preview_foreign_gets_404(two_users, client):
    """AC-16 (kind=vergleich): GIVEN Nutzer A und B mit je eigenem Ortsvergleich
    WHEN A die Alarm-Vorschau fuer seinen eigenen bzw. Bs Vergleich abruft
    THEN bekommt er fuer den eigenen 200 mit seinen Orten, fuer den fremden 404
    ohne Bs Ortsnamen.

    RED: Route fehlt → auch der Eigentuemer bekommt 404."""
    user_a, user_b = two_users
    seed_compare(user_a, "cp-a", [
        SavedLocation(id="loc-a", name="Annaberg", lat=47.27, lon=11.39, elevation_m=574),
    ])
    seed_compare(user_b, "cp-b", [
        SavedLocation(id="loc-b", name="Bertsdorf", lat=46.50, lon=11.35, elevation_m=262),
    ])

    own = _post(client, "cp-a", "vergleich", user_a, _compare_body("loc-a"))
    assert own.status_code == 200, (
        f"Gegenprobe: Eigentuemer A muss die Alarm-Vorschau bekommen, war "
        f"{own.status_code}: {own.text[:200]}"
    )
    data = own.json()
    for key in ("subject", "email_html", "telegram", "sms"):
        assert data.get(key), f"AC-16: Kanal '{key}' fehlt/leer: {sorted(data)}"
    assert "Annaberg" in own.text

    foreign = _post(client, "cp-b", "vergleich", user_a, _compare_body("loc-b"))
    assert foreign.status_code == 404, (
        f"AC-16: fremder Vergleich muss 404 liefern, war {foreign.status_code}"
    )
    assert "Bertsdorf" not in foreign.text, "AC-16: Antwort enthaelt Daten von Nutzer B"


def test_route_alert_preview_is_delegate_of_trip_alert_preview(two_users, client):
    """AC-16 (kind=route + Delegate): GIVEN Nutzer A und B mit je eigenem Trip
    WHEN A die neue Route mit kind=route fuer seinen Trip aufruft
    THEN entspricht die Antwort der unveraenderten Alt-Route
    POST /api/trips/{id}/alert-preview (gleiche Felder, gleicher Betreff/SMS);
    fuer Bs Trip gibt es 404 ohne Bs Trip-Namen; die Alt-Route bleibt 200.

    RED: neue Route fehlt → 404."""
    user_a, user_b = two_users
    seed_trip(user_a, "trip-a", "AlarmTripAnna")
    seed_trip(user_b, "trip-b", "AlarmTripBertGeheim")

    def _legacy():
        resp = client.post(
            "/api/trips/trip-a/alert-preview", params={"user_id": user_a},
            json=TRIP_ALERT_BODY,
        )
        assert resp.status_code == 200, (
            f"Fixture-Probe: Alt-Route muss heute 200 liefern, war {resp.status_code}: "
            f"{resp.text[:200]}"
        )
        return resp.json()

    # Alt → neu → Alt: das neue Ergebnis muss einer der beiden Alt-Antworten
    # gleichen (Minutenwechsel in der Stand-Zeile abgefangen).
    legacy_before = _legacy()
    new = _post(client, "trip-a", "route", user_a, TRIP_ALERT_BODY)
    legacy_after = _legacy()
    assert new.status_code == 200, (
        f"AC-16: neue Route (kind=route) muss 200 liefern, war {new.status_code}: "
        f"{new.text[:200]}"
    )
    assert sorted(new.json()) == sorted(legacy_before), "AC-16: Antwortform weicht ab"
    assert new.json() in (legacy_before, legacy_after), (
        "AC-16: kind=route muss dieselbe Vorschau wie die Alt-Route liefern"
    )

    foreign = _post(client, "trip-b", "route", user_a, TRIP_ALERT_BODY)
    assert foreign.status_code == 404, (
        f"AC-16: fremder Trip muss 404 liefern, war {foreign.status_code}"
    )
    assert "AlarmTripBertGeheim" not in foreign.text


@pytest.mark.parametrize("kind", [None, "", "trip", "compare"])
def test_alert_preview_rejects_missing_or_unknown_kind(two_users, client, kind):
    """AC-16 (kind Pflicht): GIVEN ein eigener Trip
    WHEN die Alarm-Vorschau ohne bzw. mit unbekanntem kind aufgerufen wird
    THEN lehnt der Kern ab (400/422), waehrend kind=route fuer denselben Trip
    200 liefert.

    RED: Route fehlt → die Gegenprobe mit kind=route liefert 404."""
    user_a, _ = two_users
    seed_trip(user_a, "trip-a", "AlarmTripAnna")

    ok = _post(client, "trip-a", "route", user_a, TRIP_ALERT_BODY)
    assert ok.status_code == 200, f"Gegenprobe kind=route: {ok.status_code} {ok.text[:200]}"

    bad = _post(client, "trip-a", kind, user_a, TRIP_ALERT_BODY)
    assert bad.status_code in (400, 422), (
        f"AC-16: kind={kind!r} muss abgelehnt werden, war {bad.status_code}"
    )
