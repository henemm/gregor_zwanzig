"""TDD RED — Staging-only Seed fuer den SMS-Tageszaehler, Python-Seite (#2423).

SPEC: docs/specs/modules/staging_seed_endpoint.md (AC-7, AC-8, AC-9, AC-10)

RED heute, warum:
- `services.sms_daily_limit.seed_daily_usage` existiert nicht -> `AttributeError`.
- `POST /api/_internal/sms/seed-daily-usage` ist nicht registriert -> 404
  (auch in Staging-Lage; die Positivkontrolle in AC-10 scheitert).

Der Endpoint muss `GZ_ENV` zur ANFRAGEZEIT auswerten (nicht erst beim Import),
damit dieselbe echte App in beiden Lagen pruefbar ist.

Ausfuehren:
  uv run pytest tests/tdd/test_staging_seed_endpoint.py -v -rA --disable-socket
"""
from __future__ import annotations

import json
import sys
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from api.routers import internal  # noqa: E402
from app.loader import get_data_dir  # noqa: E402
from services import sms_daily_limit  # noqa: E402

PFAD = "/api/_internal/sms/seed-daily-usage"


def _kennung(praefix: str) -> str:
    # Ohne "tdd"/"test" im Namen (is_test_user_id wuerde Konfiguration umleiten).
    return f"seedcore-{praefix}-{uuid.uuid4().hex[:8]}"


def _nutzer(uid: str, tier: str) -> None:
    d = get_data_dir(uid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "user.json").write_text(json.dumps({"id": uid, "tier": tier}))


def _zaehler(uid: str) -> dict:
    return json.loads((get_data_dir(uid) / "sms_daily_count.json").read_text())


def _jetzt() -> datetime:
    return datetime.now(timezone.utc)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(internal.router)
    return TestClient(app)


# --- AC-7 -------------------------------------------------------------------


def test_overshoot_ueber_limit_wird_nicht_gekappt():
    uid = _kennung("over")
    _nutzer(uid, "premium")
    sms_daily_limit.seed_daily_usage(uid, None, 17, _jetzt())
    u = sms_daily_limit.get_daily_usage(uid, _jetzt())
    assert u["premium_sms"]["used"] == 17, f"AC-7: erwartet 17, war {u['premium_sms']}"
    assert u["premium_sms"]["limit"] == 15, f"AC-7: Limit 15 erwartet, war {u['premium_sms']}"


def test_seed_gibt_neuen_stand_zurueck_und_ueberschreibt_nur_gesetzte_felder():
    uid = _kennung("rueck")
    _nutzer(uid, "premium")
    sms_daily_limit.seed_daily_usage(uid, 5, 2, _jetzt())
    stand = sms_daily_limit.seed_daily_usage(uid, 7, None, _jetzt())
    assert stand == {"sms": 7, "premium_sms": 2}, f"AC-7/8: nicht gesetztes Feld bleibt, war {stand}"


# --- AC-8 -------------------------------------------------------------------


def test_gesetzter_stand_faellt_am_folgetag_auf_null():
    uid = _kennung("tag")
    _nutzer(uid, "premium")
    jetzt = _jetzt()
    sms_daily_limit.seed_daily_usage(uid, 4, 6, jetzt)
    u = sms_daily_limit.get_daily_usage(uid, jetzt + timedelta(days=1))
    assert u["sms"]["used"] == 0 and u["premium_sms"]["used"] == 0, f"AC-8: {u}"


def test_seed_auf_gestriger_datei_setzt_datum_heute_und_nullt_das_andere_feld():
    uid = _kennung("gestern")
    _nutzer(uid, "premium")
    jetzt = _jetzt()
    gestern = (jetzt - timedelta(days=1)).date().isoformat()
    pfad = get_data_dir(uid) / "sms_daily_count.json"
    pfad.write_text(json.dumps({"date": gestern, "sms": 9, "premium_sms": 8}))
    sms_daily_limit.seed_daily_usage(uid, 4, None, jetzt)
    d = _zaehler(uid)
    assert d["date"] == jetzt.date().isoformat(), f"AC-8: Datum muss heute sein, war {d}"
    assert d["sms"] == 4 and d["premium_sms"] == 0, f"AC-8: erwartet 4/0, war {d}"


# --- AC-9 -------------------------------------------------------------------


def test_seed_beruehrt_fremden_zaehler_nicht():
    a, b = _kennung("a"), _kennung("b")
    _nutzer(a, "standard")
    _nutzer(b, "standard")
    sms_daily_limit.seed_daily_usage(b, 3, 1, _jetzt())
    vorher = (get_data_dir(b) / "sms_daily_count.json").read_bytes()
    sms_daily_limit.seed_daily_usage(a, 9, 9, _jetzt())
    assert (get_data_dir(b) / "sms_daily_count.json").read_bytes() == vorher, "AC-9: B veraendert"
    assert sms_daily_limit.get_daily_usage(b, _jetzt())["sms"]["used"] == 3


def test_paralleles_seeden_und_reservieren_hinterlaesst_gueltige_datei():
    uid = _kennung("par")
    _nutzer(uid, "standard")
    jetzt = _jetzt()
    fehler: list[Exception] = []

    def seed():
        try:
            for i in range(25):
                sms_daily_limit.seed_daily_usage(uid, i % 5, None, jetzt)
        except Exception as e:  # noqa: BLE001
            fehler.append(e)

    def reserve():
        for _ in range(25):
            try:
                sms_daily_limit.check_and_reserve(uid, "sms", "briefing", jetzt)
            except Exception:  # noqa: BLE001 -- Limit-Sperre ist hier erlaubt
                pass

    ts = [threading.Thread(target=seed), threading.Thread(target=reserve)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not fehler, f"AC-9: seed warf {fehler}"
    d = _zaehler(uid)  # muss gueltiges JSON sein
    assert isinstance(d["sms"], int) and isinstance(d["premium_sms"], int), f"AC-9: {d}"


# --- AC-10 ------------------------------------------------------------------


def test_internal_route_ist_ausserhalb_staging_404_und_schreibt_nichts(monkeypatch):
    monkeypatch.delenv("GZ_ENV", raising=False)
    uid = _kennung("prod")
    _nutzer(uid, "standard")
    antwort = _client().post(PFAD, json={"user_id": uid, "sms": 5})
    assert antwort.status_code == 404, f"AC-10: Produktionslage erwartet 404, war {antwort.status_code}"
    assert not (get_data_dir(uid) / "sms_daily_count.json").exists(), "AC-10: Zaehler geschrieben"


def test_internal_route_liefert_in_staging_200_und_schreibt(monkeypatch):
    monkeypatch.setenv("GZ_ENV", "staging")
    uid = _kennung("stag")
    _nutzer(uid, "standard")
    antwort = _client().post(PFAD, json={"user_id": uid, "sms": 5})
    assert antwort.status_code == 200, f"AC-10 Positivkontrolle: {antwort.status_code} {antwort.text}"
    assert antwort.json() == {"sms": 5, "premium_sms": 0}
    assert sms_daily_limit.get_daily_usage(uid, _jetzt())["sms"]["used"] == 5
