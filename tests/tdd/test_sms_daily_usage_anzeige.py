"""TDD RED — SMS-/Premium-SMS-Tageskontingent im Account sichtbar (S4b,
Sammel-Issue #2153, Einzel-Issue #2412, Epic #2138).

SPEC: docs/specs/modules/sms_daily_usage_anzeige.md (AC-1, AC-3, AC-4, AC-6)

RED heute, warum:
- `services.sms_daily_limit.get_daily_usage` existiert nicht -> `AttributeError`
  in den beiden direkten Funktionstests.
- `GET /api/_internal/sms/daily-usage` ist im Router noch nicht registriert
  -> 404 in allen Endpoint-Tests (inkl. dem 422-Pflichtparameter-Test, der
  ohnehin nur mit einer existierenden Route sinnvoll ist).

Muster: `tests/tdd/test_sms_tageslimit.py` (`_kennung`, `_nutzer_anlegen`,
`_zaehler_schreiben`, Zeilen 195-222) fuer Zaehler-Fixtures und eindeutige
`user_id` je Test; `tests/test_sms_verification_code_endpoint.py` (Zeilen
80-108) fuer den `TestClient`-Aufbau nur mit dem `internal`-Router (ohne
`X-GZ-Core-Auth`-Middleware aus `api/main.py`).

Ausfuehren:
  uv run pytest tests/tdd/test_sms_daily_usage_anzeige.py -v -rA --disable-socket
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.loader import get_data_dir  # noqa: E402


# ---------------------------------------------------------------------------
# Nutzer-/Zaehler-Helfer (Muster tests/tdd/test_sms_tageslimit.py:195-222)
# ---------------------------------------------------------------------------


def _kennung(praefix: str) -> str:
    """Mandantenkennung OHNE "tdd"/"test" (sonst erzwingt `is_test_user_id`
    `Settings.for_testing()` und leitet Konfigurationswerte um)."""
    return f"smsanzeige-{praefix}-{uuid.uuid4().hex[:8]}"


def _nutzer_anlegen(uid: str, tier: str) -> None:
    d = get_data_dir(uid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "user.json").write_text(json.dumps({"id": uid, "tier": tier}))


def _zaehler_pfad(uid: str) -> Path:
    return get_data_dir(uid) / "sms_daily_count.json"


def _heute_utc() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _zaehler_schreiben(
    uid: str, *, sms: int = 0, premium_sms: int = 0, datum: str | None = None,
) -> None:
    pfad = _zaehler_pfad(uid)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(
        {"date": datum or _heute_utc(), "sms": sms, "premium_sms": premium_sms}
    ))


def _zaehler_korrupt_schreiben(uid: str) -> None:
    pfad = _zaehler_pfad(uid)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text("{kein gueltiges JSON")


# ---------------------------------------------------------------------------
# AC-6: Direkter Funktionstest gegen `sms_daily_limit.get_daily_usage`
# ---------------------------------------------------------------------------


def test_get_daily_usage_liefert_fail_open_bei_korrupter_zaehlerdatei():
    """AC-6: eine kaputte `sms_daily_count.json` darf `get_daily_usage` NIE
    werfen lassen -- neutraler Fallback `used=0`, `limit` weiterhin aus dem
    Tarif ermittelt."""
    from services import sms_daily_limit

    uid = _kennung("ac6")
    _nutzer_anlegen(uid, "standard")
    _zaehler_korrupt_schreiben(uid)

    ergebnis = sms_daily_limit.get_daily_usage(uid, datetime.now(timezone.utc))

    assert ergebnis["sms"]["used"] == 0, (
        f"AC-6: korrupte Zaehlerdatei muss used=0 liefern, bekommen {ergebnis['sms']}"
    )
    assert ergebnis["sms"]["limit"] == 10, (
        f"AC-6: Tarif-Limit bleibt trotz kaputter Zaehlerdatei ermittelbar, bekommen {ergebnis['sms']}"
    )


def test_get_daily_usage_liefert_dict_schema_je_kanal():
    """Grundwerte-Schema: `sms`/`premium_sms` mit `used`/`limit`/`reserve`,
    `premium_sms` zusaetzlich `reply_overshoot`."""
    from services import sms_daily_limit

    uid = _kennung("schema")
    _nutzer_anlegen(uid, "premium")
    _zaehler_schreiben(uid, sms=2, premium_sms=1)

    ergebnis = sms_daily_limit.get_daily_usage(uid, datetime.now(timezone.utc))

    assert set(ergebnis.keys()) == {"sms", "premium_sms"}
    assert ergebnis["sms"] == {"used": 2, "limit": 10, "reserve": 2}
    assert ergebnis["premium_sms"]["used"] == 1
    assert ergebnis["premium_sms"]["limit"] == 15
    assert ergebnis["premium_sms"]["reserve"] == 3
    assert ergebnis["premium_sms"]["reply_overshoot"] == 3


# ---------------------------------------------------------------------------
# Endpoint-Tests: `GET /api/_internal/sms/daily-usage`
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.routers import internal

    app = FastAPI()
    app.include_router(internal.router)
    return TestClient(app)


PFAD = "/api/_internal/sms/daily-usage"


def test_endpoint_liefert_standard_nutzer_kontingent(client):
    """AC-1: Standard-Nutzer, 3 von 10 SMS verbraucht, keine Premium-SMS-Berechtigung."""
    uid = _kennung("ac1")
    _nutzer_anlegen(uid, "standard")
    _zaehler_schreiben(uid, sms=3, premium_sms=0)

    antwort = client.get(PFAD, params={"user_id": uid})

    assert antwort.status_code == 200, (
        f"AC-1: erwartet 200, bekommen {antwort.status_code}: {antwort.text}"
    )
    daten = antwort.json()
    assert daten["sms"]["used"] == 3
    assert daten["sms"]["limit"] == 10
    assert daten["sms"]["reserve"] == 2
    assert daten["premium_sms"]["limit"] == 0, (
        "AC-1: Standard-Tier hat keinen Premium-SMS-Zugriff -- limit muss 0 sein"
    )


def test_endpoint_liefert_premium_nutzer_reply_overshoot(client):
    """AC-3: Premium-Nutzer mit Reply-Overshoot (17 verbraucht, Grundlimit 15)."""
    uid = _kennung("ac3")
    _nutzer_anlegen(uid, "premium")
    _zaehler_schreiben(uid, sms=0, premium_sms=17)

    antwort = client.get(PFAD, params={"user_id": uid})

    assert antwort.status_code == 200, (
        f"AC-3: erwartet 200, bekommen {antwort.status_code}: {antwort.text}"
    )
    daten = antwort.json()
    assert daten["premium_sms"]["used"] == 17, (
        f"AC-3: der volle Zaehlerstand muss unkommentiert durchgereicht werden, bekommen {daten['premium_sms']}"
    )
    assert daten["premium_sms"]["limit"] == 15


def test_endpoint_trennt_mandanten_strikt(client):
    """AC-4 (PFLICHT nach CLAUDE.md): zwei Nutzer, zwei Zaehlerstaende --
    jeder sieht ausschliesslich seinen eigenen Wert, kein Cross-User-Leck."""
    uid_a = _kennung("ac4a")
    uid_b = _kennung("ac4b")
    _nutzer_anlegen(uid_a, "standard")
    _nutzer_anlegen(uid_b, "standard")
    _zaehler_schreiben(uid_a, sms=8, premium_sms=0)
    _zaehler_schreiben(uid_b, sms=1, premium_sms=0)

    antwort_a = client.get(PFAD, params={"user_id": uid_a})
    antwort_b = client.get(PFAD, params={"user_id": uid_b})

    assert antwort_a.status_code == 200 and antwort_b.status_code == 200
    daten_a = antwort_a.json()
    daten_b = antwort_b.json()
    assert daten_a["sms"]["used"] == 8, f"AC-4: Nutzer A muss seinen eigenen Stand sehen, bekommen {daten_a}"
    assert daten_b["sms"]["used"] == 1, f"AC-4: Nutzer B muss seinen eigenen Stand sehen, bekommen {daten_b}"
    assert daten_a["sms"]["used"] != daten_b["sms"]["used"], (
        "AC-4: unterschiedliche Nutzer duerfen niemals denselben Zaehlerstand liefern"
    )


def test_endpoint_user_id_ist_pflicht_ohne_default(client):
    """Kein `"default"`-Fallback (CLAUDE.md-Pflicht): fehlender `user_id`-Query-
    Parameter muss 422 liefern, Muster `loaded_trip`/`stages_weather`."""
    antwort = client.get(PFAD)

    assert antwort.status_code == 422, (
        f"user_id ist Pflicht-Query-Parameter ohne Default, erwartet 422, bekommen {antwort.status_code}: {antwort.text}"
    )
