"""TDD RED — Issue #2283 Scheibe S1, AC-4 (Python-Teil).

Spec: docs/specs/modules/shared_preview_tab.md

Route unter Test (Python-Core, Go proxied mit `appendUserID` darauf):
    GET /api/briefings/{entity_id}/preview?kind=route|vergleich&user_id=<uid>

Zwei echte, verschiedene Nutzer A und B, jeder mit eigenem Trip UND eigenem
Ortsvergleich. Fremde ID → 404 ohne Fremddaten, bei vergleich startet keine
Wetter-Berechnung. Ohne `user_id` gibt es keinen Rueckfall auf 'default'.
(Das Verwerfen eines Client-`user_id` macht der Go-Proxy — Go-Test
internal/handler/briefing_preview_test.go; der Python-Kern vertraut dem
injizierten Wert und muss dafuer user-scoped laden.)

Jeder Test prueft ZUERST die Gegenprobe „Eigentuemer bekommt 200 mit eigenem
Inhalt" — sonst waere „Fremder bekommt 404" heute schon gruen (Router-404
der fehlenden Route) und bewiese nichts.

RED-Grund: Route fehlt im Python-Core → 404 auch fuer den Eigentuemer.
"""
from __future__ import annotations

import uuid

import pytest

from app.user import SavedLocation

from tests.integration.test_briefing_preview_bundle import (
    COMPARE_DATE,
    TRIP_DATE,
    EngineCalls,
    _seed_trip,
    client,  # noqa: F401  (pytest-Fixture)
    env,  # noqa: F401  (pytest-Fixture, isolierter Daten-Root)
    install_recording_engine,
    seed_compare,
)

MARKER_A = "TripVonAnna2283"
MARKER_B = "GeheimTripBert2283"


@pytest.fixture
def two_users(env):  # noqa: F811
    suffix = uuid.uuid4().hex[:6]
    return f"tdd-2283-a-{suffix}", f"tdd-2283-b-{suffix}"


def _get(client, entity_id: str, kind: str, user_id: str | None, **extra):  # noqa: F811
    params = {"kind": kind, **extra}
    if user_id is not None:
        params["user_id"] = user_id
    return client.get(f"/api/briefings/{entity_id}/preview", params=params)


def test_trip_preview_of_other_user_is_404_without_foreign_data(two_users, client):  # noqa: F811
    """AC-4 (kind=route): GIVEN Nutzer A und B mit je eigenem Trip
    WHEN A die Buendel-Vorschau mit der ID von Bs Trip abruft
    THEN 404 und kein Inhalt von B — waehrend A seinen eigenen Trip sieht.

    RED: Route fehlt → auch A bekommt 404 (Gegenprobe schlaegt fehl)."""
    user_a, user_b = two_users
    _seed_trip(user_a, "trip-a", MARKER_A)
    _seed_trip(user_b, "trip-b", MARKER_B)
    opts = {"type": "morning", "date": TRIP_DATE, "demo": "true"}

    own = _get(client, "trip-a", "route", user_a, **opts)
    assert own.status_code == 200, (
        f"Gegenprobe: Eigentuemer A muss seine Vorschau bekommen, war "
        f"{own.status_code}: {own.text[:200]}"
    )
    assert MARKER_A in own.text, "Gegenprobe: A sieht seinen eigenen Trip-Namen nicht"

    foreign = _get(client, "trip-b", "route", user_a, **opts)
    assert foreign.status_code == 404, (
        f"AC-4: Fremder Trip muss 404 liefern, war {foreign.status_code}"
    )
    assert MARKER_B not in foreign.text, "AC-4: Antwort enthaelt Daten von Nutzer B"


def test_compare_preview_of_other_user_is_404_without_engine_run(
    two_users, client, monkeypatch,  # noqa: F811
):
    """AC-4 (kind=vergleich): GIVEN Nutzer A und B mit je eigenem Ortsvergleich
    WHEN A die Buendel-Vorschau mit der ID von Bs Vergleich abruft
    THEN 404, kein Ortsname von B in der Antwort und KEIN Engine-Lauf —
    waehrend A seinen eigenen Vergleich sieht.

    RED: Route fehlt → auch A bekommt 404."""
    user_a, user_b = two_users
    seed_compare(user_a, "cp-a", [
        SavedLocation(id="loc-a", name="Annaberg", lat=47.27, lon=11.39, elevation_m=574),
    ])
    seed_compare(user_b, "cp-b", [
        SavedLocation(id="loc-b", name="Bertsdorf", lat=46.50, lon=11.35, elevation_m=262),
    ])
    calls = EngineCalls()
    install_recording_engine(monkeypatch, calls)

    own = _get(client, "cp-a", "vergleich", user_a, date=COMPARE_DATE.isoformat())
    assert own.status_code == 200, (
        f"Gegenprobe: Eigentuemer A muss seine Vergleichs-Vorschau bekommen, war "
        f"{own.status_code}: {own.text[:200]}"
    )
    assert "Annaberg" in own.text

    calls.count = 0
    foreign = _get(client, "cp-b", "vergleich", user_a, date=COMPARE_DATE.isoformat())
    assert foreign.status_code == 404, (
        f"AC-4: Fremder Vergleich muss 404 liefern, war {foreign.status_code}"
    )
    assert "Bertsdorf" not in foreign.text, "AC-4: Antwort enthaelt Ortsnamen von Nutzer B"
    assert calls.count == 0, (
        f"AC-4: fuer einen fremden Vergleich darf keine Berechnung starten, "
        f"ComparisonEngine.run lief {calls.count}x"
    )


@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_kind_mismatch_does_not_cross_entities(two_users, client, monkeypatch, kind):  # noqa: F811
    """AC-4 (Rand): GIVEN Nutzer A besitzt einen Trip und einen Vergleich
    WHEN er die ID des jeweils ANDEREN kinds abruft
    THEN wird nichts still umgedeutet (kein 200 mit fremdem Typ) — Antwort ist
    ein Fehler (404/422), waehrend der richtige kind 200 liefert.

    RED: Route fehlt → der richtige kind liefert ebenfalls 404."""
    user_a, _ = two_users
    _seed_trip(user_a, "trip-a", MARKER_A)
    seed_compare(user_a, "cp-a", [
        SavedLocation(id="loc-a", name="Annaberg", lat=47.27, lon=11.39, elevation_m=574),
    ])
    install_recording_engine(monkeypatch, EngineCalls())
    own_id, other_id = ("trip-a", "cp-a") if kind == "route" else ("cp-a", "trip-a")
    opts = (
        {"type": "morning", "date": TRIP_DATE, "demo": "true"}
        if kind == "route" else {"date": COMPARE_DATE.isoformat()}
    )

    ok = _get(client, own_id, kind, user_a, **opts)
    assert ok.status_code == 200, f"Gegenprobe kind={kind}: {ok.status_code} {ok.text[:200]}"

    mismatch = _get(client, other_id, kind, user_a, **opts)
    assert mismatch.status_code in (404, 422), (
        f"AC-4: ID des anderen kinds darf nicht als kind={kind} gerendert werden, "
        f"war {mismatch.status_code}"
    )


def test_missing_user_id_never_falls_back_to_default(env, client):  # noqa: F811
    """AC-4 (nie 'default'): GIVEN unter 'default' liegt ein Trip mit derselben
    ID
    WHEN die Buendel-Vorschau OHNE user_id aufgerufen wird
    THEN lehnt der Kern ab (422, Pflichtparameter) und liefert keine Daten des
    'default'-Nutzers.

    RED: Route fehlt → 404 statt 422."""
    _seed_trip("default", "trip-x", "DefaultTripLeck2283")

    resp = _get(client, "trip-x", "route", None, date=TRIP_DATE, demo="true")
    assert "DefaultTripLeck2283" not in resp.text, "AC-4: Rueckfall auf 'default'-Daten"
    assert resp.status_code == 422, (
        f"AC-4: user_id ist Pflicht (vom Go-Proxy injiziert), erwartet 422, war "
        f"{resp.status_code}: {resp.text[:200]}"
    )
