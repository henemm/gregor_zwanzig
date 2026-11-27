"""#3441 (S5b): Beispiel-Alarm mit echten Werten (``services.alert_test_service``).

Spec: docs/specs/modules/feat_3441_test_alarm.md (AC-9, AC-11, AC-12); Beispiel-Formel
abgelöst durch docs/specs/modules/fix_3462_testalarm_beispielwerte.md (#3462).

VERTRAG für den Developer:
    AlertTestService(user_id=<uid>).beispiel_aenderungen(subscription) -> list[WeatherChange]
        subscription = ``app.trip.Trip`` (kind route) oder Compare-Preset-Rohdict (kind vergleich).
        Je aktiver Regel bzw. Alarm-Metrik eine Änderung, S = Schwelle (#3462):
        Richtung je Summary-Feld aus dem Katalog (ein Kandidat mit cmp "unter" ⇒ fallend).
        Betrag der Änderung immer 1.2×|S| (negative Schwellen, z. B. Kälte −25 °C).
        steigend: old = 0 bei Delta-Regeln, sonst 0.8×S; new = old + 1.2×|S|.
        fallend:  new = 0.8×S; old = new + 1.2×|S|.
        Gewitter ``thunder_level_max``: old = 0, new = min(3, max(2, ceil(1.2×S))).
        Einheit "%": new ≤ 100, old = max(0, new − 1.2×S).
        Je angezeigter Bezeichnung (``get_alert_label(_resolve_metric_id(…), "de")``) höchstens
        eine Änderung, erste Regel gewinnt (Kälte/Hitze heißen beide „Temp“).
        Keine aktive ⇒ Fallback-Metrik (Böen, S = 50: 40 → 100).

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


def _faellt(feld: str) -> bool:
    """Spec #3462: ein Katalog-Kandidat des Felds mit cmp "unter" ⇒ fallend."""
    from app.metric_catalog import _METRICS

    return any(m.cmp == "unter" for m in _METRICS if feld in m.summary_fields.values())


def _regel_treu(changes) -> None:
    import math

    from app.metric_catalog import get_alert_label, get_metric
    from output.renderers.alert.project import _resolve_metric_id

    assert changes, "kein Beispiel erzeugt"
    metriken = [_resolve_metric_id(c.metric, c.direction) for c in changes]
    bezeichnungen = [get_alert_label(m, "de") for m in metriken]
    assert len(bezeichnungen) == len(set(bezeichnungen)), f"Bezeichnung doppelt: {bezeichnungen}"
    for c, mid in zip(changes, metriken):
        s, betrag = c.threshold, 1.2 * abs(c.threshold)
        if c.metric == "thunder_level_max":
            assert (c.old_value, c.new_value) == (0, min(3, max(2, math.ceil(1.2 * s)))), c
        elif get_metric(mid).unit == "%":
            assert c.new_value <= 100 and c.old_value == pytest.approx(max(0.0, c.new_value - betrag)), c
        elif _faellt(c.metric):
            assert c.direction == "decrease", c
            assert c.new_value == pytest.approx(0.8 * s) and c.old_value == pytest.approx(c.new_value + betrag), c
        else:
            assert c.direction == "increase", c
            assert c.new_value - c.old_value == pytest.approx(betrag), c
            assert c.old_value in (pytest.approx(0.8 * s), 0), c


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
        "gust_max_kmh": (pytest.approx(40.0), pytest.approx(100.0), 50.0),
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


def _manuell_heute(uid: str) -> int:
    from services.forecast_budget import ForecastBudgetGate

    return ForecastBudgetGate(uid).snapshot()["user_manual_calls_today"]


@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_ac9_ein_klick_bucht_genau_eine_einheit_manueller_abruf(mit, monkeypatch, kind):
    """Fix-Loop F002: ohne Stundenreihe (kein Anker) entsteht kein Wetterabruf; der Klick
    selbst bucht genau EINE ``user_manual``-Einheit im echten Nutzerzähler (die
    Vorab-Schätzung wird beim Verlassen bis auf diese Einheit erstattet)."""
    engine_naht(monkeypatch)
    uid = nutzer_anlegen()
    eid = _trip(uid) if kind == "route" else _vergleich(uid)
    vorher = _manuell_heute(uid)

    r = hv.client().post(f"/api/briefings/{eid}/test-alert", params={"user_id": uid, "kind": kind})

    assert r.status_code == 200, r.text
    assert _manuell_heute(uid) - vorher == 1, (vorher, _manuell_heute(uid))
    r = hv.client().post(f"/api/briefings/{eid}/test-alert", params={"user_id": uid, "kind": kind})
    assert r.status_code == 200, r.text
    assert _manuell_heute(uid) - vorher == 2, "jeder Klick zählt genau einmal"


#: Mehr Anker-Segmente als die Schätzung des Zwei-Wegpunkt-Trips (7) Einheiten erlaubt.
_VIELE_SEGMENTE = 9


def _anker_mit_vielen_segmenten(uid: str, trip) -> None:
    """Tages-Anker mit ``_VIELE_SEGMENTE`` verschiedenen Segmenten (echter Abruf über die
    Fixture-Naht, wie ``_trip_anker_schreiben``): der Frisch-Abruf des Test-Alarms ruft jedes
    davon einzeln ab und übersteigt damit die Vorab-Schätzung."""
    from datetime import datetime, timedelta, timezone

    from app.models import GPXPoint, TripSegment
    from providers.base import get_provider
    from services.segment_weather import SegmentWeatherService
    from services.trip_day import trip_local_today
    from services.weather_cache import reset_shared_weather_cache_for_tests
    from services.weather_snapshot import WeatherSnapshotService
    from tests.tdd.test_alert_hour_rows import _heute0

    start, segmente = _heute0(), []
    for i in range(_VIELE_SEGMENTE):
        lat = TRIP_LAT + i * 0.01
        seg = TripSegment(
            segment_id=str(i + 1),
            start_point=GPXPoint(lat=lat, lon=TRIP_LON, elevation_m=600, distance_from_start_km=0.0),
            end_point=GPXPoint(lat=lat + 0.005, lon=TRIP_LON, elevation_m=700, distance_from_start_km=1.0),
            start_time=start, end_time=start + timedelta(hours=23, minutes=59), duration_hours=23.98,
            distance_km=1.0, ascent_m=100, descent_m=0,
        )
        w = SegmentWeatherService(get_provider("openmeteo")).fetch_segment_weather(
            seg, enrich_ensemble=False, enrich_snow=False, priority="alert_check", user_id=uid,
        )
        assert not w.has_error and w.timeseries, "Vorbedingung: Anker-Abruf über die Fixture-Naht"
        segmente.append(w)
    WeatherSnapshotService(uid).save_dated(trip.id, trip_local_today(trip, datetime.now(timezone.utc)), segmente)
    reset_shared_weather_cache_for_tests()


def test_ac9_gedrosselter_segment_abruf_bricht_trip_test_alarm_ohne_versand_ab(
    mittagsuhr, env, monkeypatch, tmp_path, mit,  # noqa: F811
):
    """Fix-Loop F003: die Vorab-Buchung passt genau noch ins Tageskontingent, der
    Frisch-Abruf braucht aber mehr Einheiten; der erste nachgebuchte Abruf wird gedrosselt
    (``melde_drosselung``) ⇒ 429 ``kontingent_erschoepft``, kein Kanal erhält etwas."""
    from app.loader import load_all_trips
    from services.manuelles_kontingent import schaetzung_trip
    from tests.tdd.test_abruf_kontingent_manuell import GRENZE_JE_NUTZER, _schreibe_global, _schreibe_nutzer

    a, b = nutzer_anlegen(), nutzer_anlegen()
    tid = _stunden_trip(monkeypatch, tmp_path, a, anker=None)
    trip = next(t for t in load_all_trips(user_id=a) if t.id == tid)
    _anker_mit_vielen_segmenten(a, trip)
    schaetzung = schaetzung_trip(trip)
    assert _VIELE_SEGMENTE > schaetzung, "Vorbedingung: Abruf übersteigt die Schätzung"
    stand = GRENZE_JE_NUTZER - schaetzung
    _schreibe_global(calls=stand, aktive=[a, b], manuell=stand)
    _schreibe_nutzer(a, stand)

    r = _test_alarm(a, tid)

    assert r.status_code == 429, r.text
    assert hv.body(r).get("code") == "kontingent_erschoepft", r.text
    assert mit.kanaele == [], mit
