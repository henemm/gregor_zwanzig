"""#3441 (S5b): Beispiel-Alarm mit echten Werten (``services.alert_test_service``).

Spec: docs/specs/modules/feat_3441_test_alarm.md (AC-9, AC-11, AC-12).

VERTRAG für den Developer:
    AlertTestService(user_id=<uid>).beispiel_aenderungen(subscription) -> list[WeatherChange]
        subscription = ``app.trip.Trip`` (kind route) oder Compare-Preset-Rohdict (kind vergleich).
        Je aktiver Regel bzw. Alarm-Metrik eine Änderung: new = Schwelle×1.2, old = Schwelle×0.8,
        bei Delta-Regeln old = 0 (Vorbild ``alertPreviewHelpers.ts``); keine aktive ⇒ Fallback-Metrik.

Kein Mock: echte Trip-/Vergleichsdateien im isolierten Datenbaum, echte Loader. Die Stundenreihe
entsteht wie in ``test_alert_hour_rows.py`` (Anker im Nutzerspeicher, Frisch-Abruf über die
Fixture-Naht ``GZ_TEST_FIXTURE_DIR``); Versand nur bis zum Transport-Aufzeichner.
"""
from __future__ import annotations

import pytest

from tests.helpers.transport_mitschrift import aufzeichner_installieren
from tests.helpers.vorschau_umgebung import env, mittagsuhr  # noqa: F401  (Fixtures)
from tests.tdd import _handversand_fixtures as hv
from tests.tdd._compare_kette_fixtures import (
    ORTSNAMEN, engine_naht, nutzer_anlegen, preset_laden, transport_einrichten,
)
from tests.tdd.test_alert_hour_rows import TRIP_LAT, TRIP_LON, TRIP_STURM, _erwartete_zeilen, _plant, _rows, _trip_welt
from tests.tdd.test_briefings_test_alert_endpoint import REGELN, _trip, _vergleich


def _service(uid: str):
    from services.alert_test_service import AlertTestService

    return AlertTestService(user_id=uid)


def _trip_laden(uid: str, tid: str):
    from app.loader import load_all_trips

    return next(t for t in load_all_trips(user_id=uid) if t.id == tid)


def _werte(changes) -> dict:
    return {c.metric: (c.old_value, c.new_value, c.threshold) for c in changes}


def _regel_treu(changes) -> None:
    assert changes, "kein Beispiel erzeugt"
    for c in changes:
        assert c.new_value == pytest.approx(c.threshold * 1.2), c
        assert c.old_value in (pytest.approx(c.threshold * 0.8), 0), c


@pytest.fixture
def mit(monkeypatch):
    transport_einrichten(monkeypatch)
    return aufzeichner_installieren(monkeypatch)


# --------------------------------------------------------------------------- AC-11


def test_ac11_trip_je_aktiver_regel_eine_beispiel_aenderung_exakt_aus_der_schwelle():
    uid = nutzer_anlegen()
    regeln = REGELN + [{"id": "r-aus", "kind": "absolute", "metric": "precipitation_sum",
                        "threshold": 10.0, "severity": "info", "enabled": False}]
    tid = _trip(uid, rules=regeln)

    werte = _werte(_service(uid).beispiel_aenderungen(_trip_laden(uid, tid)))

    assert werte == {
        "gust_max_kmh": (pytest.approx(40.0), pytest.approx(60.0), 50.0),
        "wind_max_kmh": (0, pytest.approx(24.0), 20.0),
    }, werte


def test_ac11_vergleich_aktive_alarm_metriken_mit_standardschwelle():
    uid = nutzer_anlegen()
    vid = _vergleich(uid)

    _regel_treu(_service(uid).beispiel_aenderungen(preset_laden(uid, vid)))


def test_ac12_trip_ohne_aktive_regel_bekommt_fallback_beispielmetrik():
    uid = nutzer_anlegen()
    tid = _trip(uid, rules=[])

    _regel_treu(_service(uid).beispiel_aenderungen(_trip_laden(uid, tid)))


def test_ac11_vergleich_nachricht_nennt_die_echten_orte(mit, monkeypatch):
    engine_naht(monkeypatch)
    uid = nutzer_anlegen()
    vid = _vergleich(uid)

    r = hv.client().post(f"/api/briefings/{vid}/test-alert", params={"user_id": uid, "kind": "vergleich"})

    assert r.status_code == 200, r.text
    text = mit.sendungen("email")[0]["plain_text_body"] or ""
    assert all(name in text for name in ORTSNAMEN), text


# --------------------------------------------------------------------------- AC-11 / AC-12 Stundenreihe


def _stunden_trip(monkeypatch, tmp_path, uid: str, anker: dict | None) -> str:
    from app.loader import save_trip
    from app.models import AlertRule, AlertRuleKind, AlertMetric, AlertSeverity

    trip = _trip_welt(monkeypatch, tmp_path, uid, anker_boeen=anker)
    trip.alert_rules = [AlertRule(id="r-boe", kind=AlertRuleKind.ABSOLUTE, metric=AlertMetric.WIND_GUST,
                                  threshold=50.0, severity=AlertSeverity.WARNING, enabled=True)]
    save_trip(trip, user_id=uid)
    _plant(tmp_path, monkeypatch, "sturm", TRIP_STURM)
    return trip.id


def _test_alarm(uid: str, tid: str):
    return hv.client().post(f"/api/briefings/{tid}/test-alert", params={"user_id": uid, "kind": "route"})


def test_ac11_trip_test_alarm_traegt_die_stundenzeilen_der_echten_reihe(mittagsuhr, env, monkeypatch, tmp_path, mit):  # noqa: F811
    from utils.timezone import tz_for_coords

    uid = nutzer_anlegen()
    tid = _stunden_trip(monkeypatch, tmp_path, uid, anker={})

    r = _test_alarm(uid, tid)

    assert r.status_code == 200, r.text
    erwartet = _erwartete_zeilen(tz_for_coords(TRIP_LAT, TRIP_LON), TRIP_STURM, {})
    assert _rows(mit.sendungen("email")[0]["plain_text_body"]) == erwartet, mit


def test_ac12_ohne_stundenreihe_nachricht_ohne_stundenzeilen_kein_fehler(mittagsuhr, env, monkeypatch, tmp_path, mit):  # noqa: F811
    uid = nutzer_anlegen()
    tid = _stunden_trip(monkeypatch, tmp_path, uid, anker=None)

    r = _test_alarm(uid, tid)

    assert r.status_code == 200, r.text
    mail = mit.sendungen("email")
    assert len(mail) == 1 and mail[0]["subject"].startswith("[TEST]"), mit
    assert _rows(mail[0]["plain_text_body"]) == [], mail[0]["plain_text_body"]


# --------------------------------------------------------------------------- AC-9 Kontingent


def test_ac9_kontingent_manueller_abruf_erschoepft_429_ohne_versand_b_unberuehrt(
    mittagsuhr, env, monkeypatch, tmp_path, mit,  # noqa: F811
):
    from tests.tdd.test_abruf_kontingent_manuell import GRENZE_JE_NUTZER, _schreibe_global, _schreibe_nutzer

    a, b = nutzer_anlegen(), nutzer_anlegen()
    tid_a = _stunden_trip(monkeypatch, tmp_path, a, anker={})
    tid_b = _stunden_trip(monkeypatch, tmp_path, b, anker={})
    _schreibe_global(calls=GRENZE_JE_NUTZER, aktive=[a, b], manuell=GRENZE_JE_NUTZER)
    _schreibe_nutzer(a, GRENZE_JE_NUTZER)

    r = _test_alarm(a, tid_a)
    assert r.status_code == 429, r.text
    assert hv.body(r).get("code") == "kontingent_erschoepft", r.text
    assert mit.kanaele == [], mit

    rb = _test_alarm(b, tid_b)
    assert rb.status_code == 200, rb.text
    assert mit.empfaenger("email") == [f"{b}@example.invalid"], mit
