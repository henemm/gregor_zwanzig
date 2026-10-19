"""Issue #2283 S1, Adversary F005 + F006a (Python-Kern, direkt gegen den Core).

Spec: docs/specs/modules/shared_preview_tab.md (AC-1, AC-3)

Route unter Test: GET /api/briefings/{entity_id}/preview?kind=…&user_id=…

- F005a: der Python-Kern prueft `kind` selbst (Go prueft vorher ebenfalls,
  aber der Kern darf sich nicht darauf verlassen): leer/falsch → 400
  `kind_required`, fehlend → 422 (Pflicht-Query).
- F005b: `demo` wirkt nachweislich auf die Buendel-Antwort (kind=route).
  Damit demo=false netzfrei und deterministisch bleibt, zeigt
  `GZ_TEST_FIXTURE_DIR` (Offline-Testmodus, providers/base.py) auf eine
  KOPIE der Demo-Fixtures mit um +20 °C verschobenen Temperaturen — der
  Live-Weg liefert damit andere Werte als der Demo-Weg (FixtureProvider
  auf `fixtures/openmeteo`). Je demo-Wert muss das Buendel der Einzelroute
  mit demselben demo-Wert gleichen, und beide demo-Werte muessen sich
  unterscheiden.
- F006a: ein Trip mit mehreren Telegram-Nachrichten liefert sie im Buendel
  als Liste `telegram.bubbles` (wie die Einzelroute), `telegram.body`
  bleibt die kompatible Kette.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tests.integration.test_briefing_preview_bundle import (
    TRIP_DATE,
    _seed_trip,
    client,  # noqa: F401  (pytest-Fixture)
    env,  # noqa: F401  (pytest-Fixture, isolierter Daten-Root)
)

REPO = Path(__file__).resolve().parents[2]
DEMO_FIXTURES = REPO / "fixtures" / "openmeteo"
TRIP_ID = "trip-2283-f005"


@pytest.fixture
def live_fixture_dir(tmp_path, monkeypatch):
    """Offline-„Live"-Daten: Kopie der Demo-Fixtures, Temperaturen +20 °C."""
    target = tmp_path / "live-fixtures"
    shutil.copytree(DEMO_FIXTURES, target)
    for path in target.glob("*.json"):
        raw = json.loads(path.read_text(encoding="utf-8"))
        for point in raw.get("data", []):
            if isinstance(point.get("t2m_c"), (int, float)):
                point["t2m_c"] += 20
        path.write_text(json.dumps(raw), encoding="utf-8")
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", str(target))
    return target


def _bundle(client, user_id: str, demo: str, **extra):  # noqa: F811
    return client.get(
        f"/api/briefings/{TRIP_ID}/preview",
        params={"kind": "route", "user_id": user_id, "type": "morning",
                "date": TRIP_DATE, "demo": demo, **extra},
    )


def _single(client, user_id: str, channel: str, demo: str):  # noqa: F811
    resp = client.get(
        f"/api/preview/{TRIP_ID}/{channel}",
        params={"user_id": user_id, "type": "morning", "date": TRIP_DATE, "demo": demo},
    )
    assert resp.status_code == 200, f"Einzelroute {channel} demo={demo}: {resp.status_code} {resp.text[:200]}"
    return resp


# ---------------------------------------------------------------------------
# F005a — kind-Pruefung im Python-Kern
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["", "trip", "compare", "ROUTE", "Vergleich"])
def test_core_rejects_wrong_or_empty_kind_with_kind_required(env, client, kind):  # noqa: F811
    """GIVEN ein eigener Trip WHEN der Core mit leerem/falschem kind gerufen
    wird THEN 400 mit `kind_required` — waehrend kind=route 200 liefert."""
    user_id = env
    _seed_trip(user_id, TRIP_ID, "Kind-Trip 2283")

    ok = _bundle(client, user_id, "true")
    assert ok.status_code == 200, f"Gegenprobe kind=route: {ok.status_code} {ok.text[:200]}"

    resp = client.get(
        f"/api/briefings/{TRIP_ID}/preview",
        params={"kind": kind, "user_id": user_id, "date": TRIP_DATE, "demo": "true"},
    )
    assert resp.status_code == 400, f"kind={kind!r}: {resp.status_code} {resp.text[:200]}"
    assert resp.json().get("detail") == "kind_required", resp.text


def test_core_requires_kind_parameter(env, client):  # noqa: F811
    """GIVEN ein eigener Trip WHEN kind fehlt THEN 422 (Pflicht-Query)."""
    user_id = env
    _seed_trip(user_id, TRIP_ID, "Kind-Trip 2283")
    resp = client.get(
        f"/api/briefings/{TRIP_ID}/preview",
        params={"user_id": user_id, "date": TRIP_DATE, "demo": "true"},
    )
    assert resp.status_code == 422, f"{resp.status_code} {resp.text[:200]}"


# ---------------------------------------------------------------------------
# F005b — demo wirkt auf das Buendel
# ---------------------------------------------------------------------------


def test_bundle_honours_demo_flag_like_single_routes(env, client, live_fixture_dir):  # noqa: F811
    """GIVEN ein Trip, Demo-Fixtures und davon abweichende Offline-„Live"-Daten
    WHEN das Buendel mit demo=true bzw. demo=false abgerufen wird
    THEN gleicht es je demo-Wert der Einzelroute mit demselben demo-Wert, und
    die beiden Buendel unterscheiden sich (demo wird nicht ignoriert)."""
    user_id = env
    _seed_trip(user_id, TRIP_ID, "Demo-Trip 2283")

    from services.weather_cache import get_shared_weather_cache

    bundles = {}
    for demo in ("true", "false"):
        # Der prozessweite Wetter-Cache (#1329) schluesselt NICHT nach Provider
        # — ohne Leeren erbte der zweite demo-Wert die Daten des ersten (Bug
        # #2581, eigenes Ticket). Hier gemessen wird nur, ob `demo` bis zum
        # Provider durchgereicht wird.
        get_shared_weather_cache().clear()
        resp = _bundle(client, user_id, demo)
        assert resp.status_code == 200, f"Buendel demo={demo}: {resp.status_code} {resp.text[:200]}"
        bundle = resp.json()
        email = _single(client, user_id, "email", demo).text
        sms = _single(client, user_id, "sms", demo).json()
        assert bundle["email_html"] == email, f"demo={demo}: email_html weicht von der Einzelroute ab"
        assert bundle["sms"]["text"] == sms["token_line"], f"demo={demo}: SMS weicht ab"
        bundles[demo] = bundle

    assert bundles["true"]["email_html"] != bundles["false"]["email_html"], (
        "demo=true und demo=false liefern dasselbe E-Mail-HTML — demo wirkt nicht"
    )


# ---------------------------------------------------------------------------
# F006a — mehrere Telegram-Nachrichten als Liste
# ---------------------------------------------------------------------------


def test_bundle_returns_multiple_telegram_bubbles_as_list(env, client):  # noqa: F811
    """GIVEN ein Trip, dessen Telegram-Briefing aus mehreren Nachrichten besteht
    WHEN das Buendel (kind=route) abgerufen wird
    THEN steht jede Nachricht einzeln in `telegram.bubbles` (Liste, gleich der
    Einzelroute), und `telegram.body` ist die kompatible Kette daraus."""
    user_id = env
    _seed_trip(user_id, TRIP_ID, "Blasen-Trip 2283")

    resp = _bundle(client, user_id, "true")
    assert resp.status_code == 200, f"{resp.status_code} {resp.text[:200]}"
    telegram = resp.json()["telegram"]
    single = _single(client, user_id, "telegram", "true").json()

    bubbles = telegram.get("bubbles")
    assert isinstance(bubbles, list) and all(isinstance(b, str) and b for b in bubbles), telegram
    assert len(bubbles) > 1, f"Fixture-Probe: Trip muss mehrere Telegram-Nachrichten haben, war {len(bubbles)}"
    assert bubbles == single["bubbles"], "telegram.bubbles weicht von der Einzelroute ab"
    assert telegram["body"] == "\n\n---\n\n".join(bubbles) == single["body"], (
        "telegram.body ist nicht die kompatible Kette der Blasen"
    )
