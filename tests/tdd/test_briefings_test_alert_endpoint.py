"""#3441 (S5b): Test-Alarm ``POST /api/briefings/{id}/test-alert?kind=route|vergleich``.

Spec: docs/specs/modules/feat_3441_test_alarm.md (AC-2 bis AC-7, AC-10, AC-12 bis AC-14,
Python-Kern-Schicht). Echte Kette: TestClient gegen ``api.main.app`` -> Router -> Test-Alarm-
Baustein -> ``NotificationService`` -> Kanal-Ausgang. Einzige Naht: der geteilte Transport-
Aufzeichner (``tests/helpers/transport_mitschrift.py``) an der Kanalgrenze; Kanalauflösung,
Tarif-Gates, Tageskontingent und Renderer laufen echt. Nutzerdaten liegen als echte Dateien im
isolierten Datenbaum (Muster ``_handversand_fixtures``). Zwei-Nutzer-Pflicht: AC-13.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import pytest

from app.loader import get_data_dir
from tests.helpers.transport_mitschrift import aufzeichner_installieren
from tests.tdd import _handversand_fixtures as hv
from tests.tdd._compare_kette_fixtures import (
    engine_naht, fixture_dict, nutzer_anlegen, orte_anlegen, preset_ablegen,
    sms_tageslimit_erschoepfen, transport_einrichten,
)

PFAD = "/api/briefings/{id}/test-alert"
REGELN = [
    {"id": "r-boe", "kind": "absolute", "metric": "wind_gust", "threshold": 50.0,
     "severity": "warning", "enabled": True},
    {"id": "r-wind", "kind": "delta", "metric": "wind_change", "threshold": 20.0,
     "severity": "critical", "enabled": True},
]
ALLE_VIER = {"email": True, "telegram": True, "sms": True, "premium_sms": True}
#: Alarm-Zustand des Nutzers (AC-6): Melde-Gedächtnis, Protokoll, Tageslimit, Sperrzeit, Anker.
ZUSTAND = re.compile(r"^(alert_|compare_alert|radar_alert|throttle_state|weather_snapshots/|"
                     r"compare_weather_snapshots/)")


@pytest.fixture
def mit(monkeypatch):
    transport_einrichten(monkeypatch)
    engine_naht(monkeypatch)
    return aufzeichner_installieren(monkeypatch)


@pytest.fixture
def c():
    return hv.client()


def _ausloesen(c, eid: str, uid: str, kind: str):
    return c.post(PFAD.format(id=eid), params={"user_id": uid, "kind": kind})


def _trip(uid: str, tid: str = "trip-ta", *, email=True, telegram=False, sms=False,
          stages=True, override=None, rules=REGELN, **felder) -> str:
    pfad = hv.trip_anlegen(uid, tid, email=email, telegram=telegram, sms=sms, stages=stages)
    daten = json.loads(pfad.read_text())
    daten["alert_rules"] = rules
    if override is not None:
        daten["alert_channels"] = override
    daten.update(felder)
    pfad.write_text(json.dumps(daten))
    return tid


def _vergleich(uid: str, vid: str = "vgl-ta", *, override=None, **felder) -> str:
    roh = fixture_dict("basis")
    roh.update({"id": vid, "official_alerts_enabled": False, **felder})
    if override is not None:
        roh["alert_channels"] = override
    orte_anlegen(uid)
    preset_ablegen(uid, roh)
    return vid


def _anlegen(kind: str, uid: str, **kw) -> str:
    """Gleiche Kanallage für beide Arten: ``telegram``/``sms`` = Briefing-Kanäle."""
    if kind == "route":
        return _trip(uid, **kw)
    tg, sms = kw.pop("telegram", False), kw.pop("sms", False)
    kw.pop("rules", None)
    return _vergleich(uid, send_telegram=tg, send_sms=sms, **kw)


def _uebersprungen(b: dict) -> dict:
    return {e["channel"]: e["reason"] for e in b.get("skipped_channels") or []}


def _zustand(uid: str) -> dict:
    d = get_data_dir(uid)
    return {str(p.relative_to(d)): p.read_bytes() for p in d.rglob("*")
            if p.is_file() and ZUSTAND.match(str(p.relative_to(d)))}


def _zustand_belegen(uid: str, eid: str) -> None:
    """Sperrzeit aktiv, Tageslimit ausgeschöpft, Melde-Gedächtnis + Protokoll vorhanden."""
    d, jetzt = get_data_dir(uid), datetime.now(timezone.utc)
    heute = jetzt.date().isoformat()
    (d / "alert_state").mkdir(parents=True, exist_ok=True)
    (d / "alert_state" / f"{eid}.json").write_text(json.dumps(
        {"gust_max_kmh:1": {"last_reported_value": 60.0, "reported_at": jetzt.isoformat()}}))
    (d / "alert_daily_count.json").write_text(json.dumps(
        {"zones": {"Europe/Vienna": {"date": heute, "count": 999}}}))
    (d / "throttle_state.json").write_text(json.dumps({s: {eid: {"at": jetzt.isoformat()}}
                                                       for s in ("trip", "compare_preset")}))
    (d / "alert_log.json").write_text(json.dumps([{"entity_id": eid, "at": jetzt.isoformat()}]))


# --------------------------------------------------------------------------- AC-2 / AC-5


@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_ac2_genau_die_alarm_kanaele_des_nutzers_erhalten_den_test(mit, c, kind):
    uid = nutzer_anlegen()
    eid = _anlegen(kind, uid, telegram=True)

    r = _ausloesen(c, eid, uid, kind)

    assert r.status_code == 200, r.text
    assert sorted(hv.body(r).get("sent_channels") or []) == ["email", "telegram"], r.text
    assert mit.kanaele == ["email", "telegram"], mit
    assert mit.empfaenger("email") == [f"{uid}@example.invalid"], mit
    assert set(mit.empfaenger("telegram")) == {f"chat-{uid}"}, mit
    assert [s["mail_type"] for s in mit.sendungen("email")] == ["deviation-alert"], mit


@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_ac5_jeder_kanal_traegt_test_und_sms_bleibt_bei_140_zeichen(mit, c, kind):
    uid = nutzer_anlegen()
    lang = {"name": "Sehr langer Name einer Weitwanderung über alle Hochpässe der Alpen"}
    regeln = REGELN + [{"id": f"r-{m}", "kind": "absolute", "metric": m, "threshold": t,
                        "severity": "critical", "enabled": True}
                       for m, t in (("precipitation_sum", 10.0), ("temperature_max", 35.0),
                                    ("fresh_snow", 8.0), ("cape", 600.0))]
    eid = _anlegen(kind, uid, override=ALLE_VIER, rules=regeln, **lang)

    r = _ausloesen(c, eid, uid, kind)

    assert r.status_code == 200, r.text
    assert mit.kanaele == ["email", "sms", "premium_sms", "telegram"], mit
    assert all(s["subject"].startswith("[TEST]") for s in mit.sendungen("email")), mit
    assert all("[TEST]" in (s["body"] or "") for s in mit.sendungen("telegram")), mit
    for kanal in ("sms", "premium_sms"):
        for s in mit.sendungen(kanal):
            assert s["body"].startswith("[TEST]"), (kanal, s["body"])
            assert len(s["body"]) <= 140, (kanal, len(s["body"]), s["body"])


# --------------------------------------------------------------------------- AC-3 / AC-6


@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_ac3_ac6_regeln_ignoriert_und_alarm_zustand_bleibt_byte_gleich(mit, c, kind):
    """Radar aus, stille Stunden ganztägig, Sperrzeit aktiv, Tageslimit voll: der Test geht
    trotzdem raus -- dreimal -- und kein Alarm-Zustand ändert sich oder entsteht neu."""
    uid = nutzer_anlegen()
    eid = _anlegen(kind, uid, radar_alert_enabled=False, alert_quiet_from="00:00",
                   alert_quiet_to="23:59", alert_cooldown_minutes=1440)
    _zustand_belegen(uid, eid)
    vorher = _zustand(uid)

    for _ in range(3):
        r = _ausloesen(c, eid, uid, kind)
        assert r.status_code == 200, r.text
        assert hv.body(r).get("sent_channels") == ["email"], r.text

    assert len(mit.sendungen("email")) == 3, mit
    assert _zustand(uid) == vorher, "Test-Alarm hat Alarm-Zustand geschrieben"


# --------------------------------------------------------------------------- AC-4


@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_ac4_nur_effective_alert_channels_bestimmt_die_kanalmenge(mit, c, kind):
    """Briefing: Telegram aus, SMS an. Override: Telegram an, SMS aus."""
    uid = nutzer_anlegen()
    eid = _anlegen(kind, uid, telegram=False, sms=True,
                   override={"email": True, "telegram": True, "sms": False})

    r = _ausloesen(c, eid, uid, kind)

    assert r.status_code == 200, r.text
    assert sorted(hv.body(r).get("sent_channels") or []) == ["email", "telegram"], r.text
    assert mit.kanaele == ["email", "telegram"], f"nur im Briefing an darf nichts erhalten: {mit}"


@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_ac4_tarif_ohne_sms_meldet_sms_uebersprungen(mit, c, kind):
    uid = nutzer_anlegen(tier="free")
    eid = _anlegen(kind, uid, override={"email": True, "sms": True})

    r = _ausloesen(c, eid, uid, kind)

    assert r.status_code == 200, r.text
    assert hv.body(r).get("sent_channels") == ["email"], r.text
    assert _uebersprungen(hv.body(r)).get("sms"), f"SMS fehlt in skipped_channels: {r.text}"
    assert mit.kanaele == ["email"], mit


# --------------------------------------------------------------------------- AC-7 / AC-8


@pytest.mark.parametrize("kind", ["route", "vergleich"])
@pytest.mark.parametrize("lage", ["override_leer", "telegram_unbedienbar"])
def test_ac7_leere_kanalmenge_ergibt_keine_alarm_kanaele_ohne_versand(mit, c, monkeypatch, kind, lage):
    uid = nutzer_anlegen()
    if lage == "override_leer":
        override = {k: False for k in ALLE_VIER}
    else:
        override = {"telegram": True}
        hv.telegram_trip_unerreichbar(monkeypatch)
    eid = _anlegen(kind, uid, override=override)

    r = _ausloesen(c, eid, uid, kind)

    assert 400 <= r.status_code < 500, r.text
    assert hv.body(r).get("code") == "keine_alarm_kanaele", r.text
    assert len(hv.body(r).get("detail") or "") > 10, r.text
    assert mit.kanaele == [], mit


@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_ac8_unbedienbar_uebersprungen_zustellfehler_fehlgeschlagen(mit, c, monkeypatch, kind):
    uid = nutzer_anlegen()
    eid = _anlegen(kind, uid, override={"email": True, "telegram": True})
    versuche = hv.telegram_vergleich_scheitert(monkeypatch)

    b = hv.body(_ausloesen(c, eid, uid, kind))
    assert versuche, "Vorbedingung: Telegram-Ausgang wurde betreten"
    assert b.get("sent_channels") == ["email"], b
    assert [e["channel"] for e in b.get("failed_channels") or []] == ["telegram"], b

    hv.telegram_trip_unerreichbar(monkeypatch)
    b = hv.body(_ausloesen(c, eid, uid, kind))
    assert b.get("sent_channels") == ["email"], b
    assert _uebersprungen(b).get("telegram"), f"Telegram nicht als übersprungen gemeldet: {b}"
    assert not b.get("failed_channels"), b


# --------------------------------------------------------------------------- AC-10


@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_ac10_sms_tageskontingent_zaehlt_mit_und_erschoepft_wird_uebersprungen(mit, c, kind):
    uid = nutzer_anlegen()
    eid = _anlegen(kind, uid, override={"email": True, "sms": True})

    r = _ausloesen(c, eid, uid, kind)
    assert sorted(hv.body(r).get("sent_channels") or []) == ["email", "sms"], r.text
    zaehler = json.loads((get_data_dir(uid) / "sms_daily_count.json").read_text())
    assert zaehler.get("sms") == 1, f"Test-SMS zählt nicht gegen das Tageskontingent: {zaehler}"

    sms_tageslimit_erschoepfen(uid)
    mit.leeren()
    r = _ausloesen(c, eid, uid, kind)
    assert hv.body(r).get("sent_channels") == ["email"], r.text
    assert _uebersprungen(hv.body(r)).get("sms"), r.text
    assert mit.kanaele == ["email"], mit


# --------------------------------------------------------------------------- AC-12


@pytest.mark.parametrize("kind, felder, code", [
    ("route", {"stages": False}, "trip_ohne_segmente"),
    ("vergleich", {"location_ids": []}, "vergleich_ohne_orte"),
])
def test_ac12_ohne_segmente_bzw_orte_422_ohne_versand(mit, c, kind, felder, code):
    uid = nutzer_anlegen()
    eid = _anlegen(kind, uid, **felder)

    r = _ausloesen(c, eid, uid, kind)

    assert r.status_code == 422, r.text
    assert hv.body(r).get("code") == code, r.text
    assert mit.kanaele == [], mit


@pytest.mark.parametrize("fall", ["ohne_aktive_regeln", "etappe_nicht_heute"])
def test_ac12_randfaelle_trip_liefern_trotzdem_einen_test_alarm(mit, c, fall):
    uid = nutzer_anlegen()
    if fall == "ohne_aktive_regeln":
        eid = _trip(uid, rules=[{**REGELN[0], "enabled": False}])
    else:
        eid = _trip(uid)
        pfad = get_data_dir(uid) / "briefings" / f"{eid}.json"
        daten = json.loads(pfad.read_text())
        daten["stages"][0]["date"] = "2027-02-25"
        pfad.write_text(json.dumps(daten))

    r = _ausloesen(c, eid, uid, "route")

    assert r.status_code == 200, r.text
    assert len(mit.sendungen("email")) == 1, mit
    assert mit.sendungen("email")[0]["subject"].startswith("[TEST]"), mit


# --------------------------------------------------------------------------- AC-13 / AC-14


@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_ac13_zwei_nutzer_nur_b_erhaelt_fremde_id_404(mit, c, kind):
    a, b = nutzer_anlegen(), nutzer_anlegen()
    _anlegen(kind, a, telegram=True)
    eid = _anlegen(kind, b, telegram=True)
    fremd = _anlegen(kind, a, **({"tid": "nur-a"} if kind == "route" else {"vid": "nur-a"}))

    r = _ausloesen(c, eid, b, kind)
    assert r.status_code == 200, r.text
    assert mit.empfaenger("email") == [f"{b}@example.invalid"], mit
    assert set(mit.empfaenger("telegram")) == {f"chat-{b}"}, mit

    mit.leeren()
    for unbekannt in (fremd, "gibt-es-nicht-3441"):
        r = _ausloesen(c, unbekannt, b, kind)
        assert r.status_code == 404, r.text
        assert hv.body(r).get("code") == "not_found", r.text
    assert mit.kanaele == [], mit


def test_ac14_englischer_nutzer_bekommt_englischen_betreff_sms_bleibt_sprachneutral(mit, c):
    de, en = nutzer_anlegen(), nutzer_anlegen()
    pfad = get_data_dir(en) / "user.json"
    pfad.write_text(json.dumps({**json.loads(pfad.read_text()), "language": "en"}))
    betreff, sms = {}, {}
    for uid in (de, en):
        mit.leeren()
        eid = _trip(uid, override={"email": True, "sms": True})
        assert _ausloesen(c, eid, uid, "route").status_code == 200
        betreff[uid] = mit.sendungen("email")[0]["subject"]
        sms[uid] = mit.sendungen("sms")[0]["body"]

    assert betreff[en].startswith("[TEST]") and betreff[de].startswith("[TEST]"), betreff
    assert betreff[en] != betreff[de], f"Betreff nicht in der Sprache des Nutzers: {betreff}"
    assert sms[en] == sms[de], f"SMS-Token dürfen nicht übersetzt werden: {sms}"


# --------------------------------------------------------------------------- AC-5 Grenzlast (Fix-Loop F001)

#: Alle Schwellen-Metriken mit großen Schwellen: die Trip-SMS ohne Kürzung läge weit über 140.
VOLL_REGELN = [{"id": f"r-{m}", "kind": k, "metric": m, "threshold": t, "severity": "critical",
                "enabled": True}
               for m, k, t in (("wind_gust", "absolute", 120.0), ("wind_change", "delta", 90.0),
                               ("precipitation_sum", "absolute", 95.0),
                               ("precipitation_change", "delta", 80.0),
                               ("temperature_max", "absolute", 38.0),
                               ("temperature_min", "absolute", -25.0),
                               ("temperature_change", "delta", 15.0),
                               ("fresh_snow", "absolute", 85.0), ("cape", "absolute", 2500.0),
                               ("snow_line", "absolute", 2800.0),
                               ("freezing_level", "absolute", 3500.0),
                               ("visibility", "absolute", 9000.0),
                               ("thunder_level", "absolute", 2.0))]
#: Zusätzliche Orte für den Vergleich: je Ort eine eigene Gruppe in der SMS.
VIELE_ORTE = {f"loc-x{i}": (f"Ort Nummer {i} mit langem Namen", 47.0 + i / 10, 11.0 + i / 10)
              for i in range(8)}


def _vergleich_voll(uid: str) -> str:
    from app.loader import save_location
    from app.user import SavedLocation

    for lid, (name, lat, lon) in VIELE_ORTE.items():
        save_location(SavedLocation(id=lid, name=name, lat=lat, lon=lon, elevation_m=1000),
                      user_id=uid)
    vid = _vergleich(uid, override=ALLE_VIER)
    pfad = get_data_dir(uid) / "briefings" / f"{vid}.json"
    roh = json.loads(pfad.read_text())
    roh["location_ids"] = list(roh["location_ids"]) + list(VIELE_ORTE)
    pfad.write_text(json.dumps(roh))
    return vid


@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_ac5_grenzlast_test_praefix_kuerzt_das_sms_limit_vor_dem_rendern(mit, c, kind):
    """Fixture reizt das 140-Zeichen-Limit aus: ohne Abzug des „[TEST] "-Präfixes vom
    Render-Limit läge die SMS darüber. Prüfung am Transport (SMS und Premium-SMS)."""
    uid = nutzer_anlegen()
    if kind == "route":
        eid = _trip(uid, override=ALLE_VIER, rules=VOLL_REGELN)
    else:
        eid = _vergleich_voll(uid)

    r = _ausloesen(c, eid, uid, kind)

    assert r.status_code == 200, r.text
    for kanal in ("sms", "premium_sms"):
        sendungen = mit.sendungen(kanal)
        assert len(sendungen) == 1, (kanal, mit)
        body = sendungen[0]["body"]
        assert body.startswith("[TEST] "), (kanal, body)
        assert len(body) <= 140, (kanal, len(body), body)
