"""TDD-RED #2219: Eingangspruefung der Alarm-Vorschau (C5-52, C5-28, C5-46,
C5-19) und Zonen-Regression der Stub-Segmente (C5-18).

SPEC: docs/specs/modules/fix_2219_alarm_vorschau_haerten.md
AC-1, AC-2, AC-3, AC-4, AC-6, AC-7, AC-10, AC-11, AC-13.

Echter FastAPI-Aufruf (TestClient auf ``api.main:app`` mit
``raise_server_exceptions=False``, damit ein Absturz als HTTP 500 sichtbar
wird statt als Test-Exception), echte Router, echte Renderer, isolierter
Daten-Root je Test. Zwei echte Nutzer mit verschiedener Sprache (``user.json``
-> ``language``), niemals ``"default"``. Kein Mock, kein patch.

RED-Grund heute: die vier Fehleingaben laufen bis in den Service und enden
dort als HTTP 500 (C5-52 ``ValueError``, C5-28 ``TypeError``/``ValueError``),
im Compare-Zweig als unspezifisches ``alarm_body_ungueltig`` (C5-52), oder
werden still gerendert (C5-46 Tagesbezug verschluckt, C5-19 "0 h früher").
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.loader import get_briefings_dir, get_data_dir
from app.user import SavedLocation
from services.alert_preset import ONSET_SHIFT_BOUNDS

from tests.helpers.vorschau_umgebung import (
    TRIP_DATE,
    env,  # noqa: F401  (pytest-Fixture, isolierter Daten-Root)
    seed_compare,
    seed_trip,
)

GUST_CHANGE = {
    "metric": "gust_max_kmh", "old_value": 25.0, "new_value": 72.0, "delta": 47.0,
    "threshold": 60.0, "severity": "major", "direction": "increase", "segment_id": "1",
}

# Ohne echte Segmente fuer heute (Etappe MORGEN) braucht `changes` explizite
# `segment_times` -- Muster TRIP_ALERT_BODY aus test_api_fehler_nutzersprache.py.
SEGMENT_TIMES = [{"segment_id": "1", "start": "08:00", "end": "12:00"}]

ERLAUBTE_SCHWEREN = ("minor", "moderate", "major")

# Kleinste Schwelle je Richtung ueber alle Stufen -- aus DERSELBEN Tabelle,
# die `weather_change_detection._onset_change` liest (AC-7: keine zweite
# Konstante, auch nicht im Test).
MIN_FRUEHER_S = min(b[0] for b in ONSET_SHIFT_BOUNDS.values()) * 3600
MIN_SPAETER_S = min(b[1] for b in ONSET_SHIFT_BOUNDS.values()) * 3600


@pytest.fixture
def client():
    from api.main import app

    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def nutzer(env):  # noqa: F811
    """Zwei echte Nutzer: ``de`` und ``en`` (Sprache aus ``user.json``)."""
    suffix = uuid.uuid4().hex[:6]
    paar = {"de": f"tdd-2219-de-{suffix}", "en": f"tdd-2219-en-{suffix}"}
    for lang, uid in paar.items():
        ordner = get_data_dir(uid)
        ordner.mkdir(parents=True, exist_ok=True)
        (ordner / "user.json").write_text(
            json.dumps({"id": uid, "language": lang}), encoding="utf-8")
        seed_trip(uid, "trip-2219", "Vorschau-Trip 2219")
    return paar


def _post_trip(client, uid: str, body: dict, trip_id: str = "trip-2219"):
    return client.post(f"/api/trips/{trip_id}/alert-preview",
                       params={"user_id": uid}, json=body)


def _assert_422_lokalisiert(antworten: dict, code: str) -> None:
    """Gemeinsame Zusicherung AC-13: 422, stabiler Code, Fehlerformat wie
    `metrik_unbekannt` (``{"detail": str, "code": str}``), Text je Sprache
    verschieden und nicht der rohe Schluessel."""
    for lang, resp in antworten.items():
        assert resp.status_code == 422, (
            f"[{lang}] erwartet 422 '{code}', bekam {resp.status_code}: {resp.text[:300]}"
        )
        data = resp.json()
        assert data.get("code") == code, f"[{lang}] falscher Grund: {data!r}"
        assert isinstance(data.get("detail"), str) and data["detail"].strip(), (
            f"[{lang}] Fehlerformat muss dem von metrik_unbekannt entsprechen "
            f"(detail als Text, kein pydantic-detail[]): {data!r}"
        )
        assert code not in data["detail"] and "api.fehler" not in data["detail"], (
            f"[{lang}] roher Katalogschluessel statt Text: {data!r}"
        )
    if {"de", "en"} <= antworten.keys():
        assert antworten["de"].json()["detail"] != antworten["en"].json()["detail"], (
            "AC-13: DE- und EN-Nutzer muessen den Text in ihrer Sprache bekommen: "
            f"de={antworten['de'].text!r} en={antworten['en'].text!r}"
        )


# ─────────────────────────────── AC-1 / AC-13 ────────────────────────────────


class TestAC1SchwereUnbekanntTrip:
    def test_severity_high_liefert_422_mit_erlaubten_werten(self, client, nutzer):
        """AC-1 GIVEN ein Trip / WHEN `changes[].severity="HIGH"` / THEN 422
        `schwere_unbekannt`, Text nennt die erlaubten Werte, kein HTTP 500."""
        body = {"changes": [{**GUST_CHANGE, "severity": "HIGH"}],
                "segment_times": SEGMENT_TIMES}
        antworten = {lang: _post_trip(client, uid, body) for lang, uid in nutzer.items()}
        _assert_422_lokalisiert(antworten, "schwere_unbekannt")
        for lang, resp in antworten.items():
            detail = resp.json()["detail"]
            for wert in ERLAUBTE_SCHWEREN:
                assert wert in detail, f"[{lang}] erlaubter Wert {wert!r} fehlt: {detail!r}"
            assert "HIGH" in detail, f"[{lang}] abgelehnter Wert fehlt im Text: {detail!r}"

    def test_severity_high_auch_ueber_briefing_delegate_route(self, client, nutzer):
        """AC-1 ueber `POST /api/briefings/{id}/alert-preview?kind=route` --
        derselbe Endpunktcode wie der Trip-Pfad."""
        resp = client.post(
            "/api/briefings/trip-2219/alert-preview",
            params={"kind": "route", "user_id": nutzer["de"]},
            json={"changes": [{**GUST_CHANGE, "severity": "HIGH"}],
                  "segment_times": SEGMENT_TIMES},
        )
        _assert_422_lokalisiert({"de": resp}, "schwere_unbekannt")

    @pytest.mark.parametrize("severity", ["Major", "MAJOR"])
    def test_severity_pruefung_ist_strikt_bei_gross_klein(self, client, nutzer, severity):
        """AC-1 (Adversary F001): die Pruefung ist strikt -- abweichende
        Gross-/Kleinschreibung eines erlaubten Werts ergibt 422."""
        body = {"changes": [{**GUST_CHANGE, "severity": severity}],
                "segment_times": SEGMENT_TIMES}
        antworten = {lang: _post_trip(client, uid, body) for lang, uid in nutzer.items()}
        _assert_422_lokalisiert(antworten, "schwere_unbekannt")

    @pytest.mark.parametrize("severity", ERLAUBTE_SCHWEREN)
    def test_gueltige_schweren_bleiben_200(self, client, nutzer, severity):
        """AC-11: die Pruefung darf keinen gueltigen Wert abweisen."""
        resp = _post_trip(client, nutzer["de"],
                          {"changes": [{**GUST_CHANGE, "severity": severity}],
                           "segment_times": SEGMENT_TIMES})
        assert resp.status_code == 200, f"{severity}: {resp.text[:300]}"
        assert resp.json().get("sms"), resp.text[:300]


# ─────────────────────────────────── AC-2 ────────────────────────────────────


class TestAC2SchwereUnbekanntVergleich:
    def test_vergleich_severity_high_liefert_schwere_unbekannt(self, client, nutzer):
        """AC-2 GIVEN ein Orts-Vergleich / WHEN `kind=vergleich` mit
        `severity="HIGH"` / THEN 422 `schwere_unbekannt` (dieselbe Pruefung wie
        im Trip-Zweig), weder 500 noch das unspezifische `alarm_body_ungueltig`."""
        antworten = {}
        for lang, uid in nutzer.items():
            seed_compare(uid, "cp-2219", [SavedLocation(
                id="loc-a", name="Arzl", lat=47.28, lon=11.42, elevation_m=600)])
            antworten[lang] = client.post(
                "/api/briefings/cp-2219/alert-preview",
                params={"kind": "vergleich", "user_id": uid},
                json={"changes": [{
                    "location_id": "loc-a", "metric": "gust_max_kmh",
                    "old_value": 25.0, "new_value": 72.0, "delta": 47.0,
                    "threshold": 60.0, "severity": "HIGH", "direction": "increase",
                }]},
            )
        _assert_422_lokalisiert(antworten, "schwere_unbekannt")
        for lang, resp in antworten.items():
            for wert in ERLAUBTE_SCHWEREN:
                assert wert in resp.json()["detail"], (lang, resp.text)


# ─────────────────────────────────── AC-3 ────────────────────────────────────


def _frames_mit(ts_nass: str) -> dict:
    jetzt = datetime.now(timezone.utc)
    return {"nowcast_frames": {
        "source": "radar", "km_from": 0.0, "km_to": 4.0,
        "frames": [
            {"timestamp": (jetzt + timedelta(minutes=5)).isoformat(),
             "precip_mm_h": 0.0, "is_convective": False},
            {"timestamp": ts_nass, "precip_mm_h": 2.5, "is_convective": False},
        ],
    }}


class TestAC3ZeitstempelOhneZone:
    @pytest.mark.parametrize("ts", [
        "2026-11-13T10:00:00",   # ISO, aber ohne Zone -> heute TypeError
        "gestern",               # kein ISO -> heute ValueError
    ])
    def test_zonenloser_oder_kaputter_zeitstempel_liefert_422(self, client, nutzer, ts):
        antworten = {lang: _post_trip(client, uid, _frames_mit(ts))
                     for lang, uid in nutzer.items()}
        _assert_422_lokalisiert(antworten, "zeitstempel_ohne_zone")
        assert ts in antworten["de"].json()["detail"], (
            f"Der beanstandete Zeitstempel muss im Text stehen: {antworten['de'].text!r}"
        )

    @pytest.mark.parametrize("form", ["iso_offset", "z_suffix"])
    def test_zonierte_zeitstempel_bleiben_200(self, client, nutzer, form):
        """AC-11: `+00:00` wie `Z` sind gueltige Zonen."""
        nass = datetime.now(timezone.utc) + timedelta(minutes=20)
        ts = nass.isoformat() if form == "iso_offset" else (
            nass.strftime("%Y-%m-%dT%H:%M:%S") + "Z")
        resp = _post_trip(client, nutzer["de"], _frames_mit(ts))
        assert resp.status_code == 200, f"{form}: {resp.text[:300]}"
        assert resp.json().get("onset_detected") is True, resp.text[:300]


# ─────────────────────────────────── AC-4 ────────────────────────────────────


def _onset(**over) -> dict:
    onset = {
        "onset_minutes": 25, "onset_time": "00:23", "km_from": 0.0, "km_to": 6.0,
        "is_convective": False, "intensity_label": "mäßiger Regen",
        "source_label": "Radar (DWD)", "onset_precip_mm": 0.8,
    }
    onset.update(over)
    return {"onset": onset}


class TestAC4TagesbezugUnvollstaendig:
    @pytest.mark.parametrize("over,feld", [
        ({"onset_day_offset": 1}, "onset_weekday"),
        ({"event_end_time": "00:38", "event_end_day_offset": 1}, "event_end_weekday"),
    ])
    def test_versatz_ohne_kuerzel_liefert_422(self, client, nutzer, over, feld):
        antworten = {lang: _post_trip(client, uid, _onset(**over))
                     for lang, uid in nutzer.items()}
        _assert_422_lokalisiert(antworten, "onset_tagesbezug_unvollstaendig")
        assert feld in antworten["de"].json()["detail"], (
            f"Das fehlende Feld {feld!r} muss im Text stehen: {antworten['de'].text!r}"
        )

    def test_versatz_mit_kuerzel_bleibt_200_und_zeigt_kuerzel(self, client, nutzer):
        """Kontrollfall AC-4/AC-11: vollstaendiger Tagesbezug -> 200 und
        `R0.8@Sa0:23` und Ende `@Sa0:38` (Kuerzel-Schreibweise aus feat_2054)."""
        resp = _post_trip(client, nutzer["de"], _onset(
            onset_day_offset=1, onset_weekday="Sa",
            event_end_time="00:38", event_end_day_offset=1, event_end_weekday="Sa",
        ))
        assert resp.status_code == 200, resp.text[:300]
        sms = resp.json()["sms"]
        assert "R0.8@Sa0:23" in sms and "@Sa0:38" in sms, sms


# ────────────────────────────── AC-6 / AC-7 ──────────────────────────────────


# Summary-Felder der beiden Beginn-Groessen (Katalog, Aggregation `onset`);
# `project._is_onset_change` erkennt sie ueber den Katalog.
GEWITTER_BEGINN = "thunder_onset_utc"
STARKREGEN_BEGINN = "precip_heavy_onset_utc"


def _onset_change(alt_s: float, neu_s: float, metric: str = GEWITTER_BEGINN) -> dict:
    return {"changes": [{
        "metric": metric, "old_value": alt_s, "new_value": neu_s,
        "delta": neu_s - alt_s, "threshold": 3600.0, "severity": "moderate",
        "direction": "decrease" if neu_s < alt_s else "increase", "segment_id": "1",
    }], "segment_times": SEGMENT_TIMES}


def _basis_epoche() -> float:
    """Volle Stunde, 6 h in der Zukunft -- gemeinsamer Bezugspunkt."""
    jetzt = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    return (jetzt + timedelta(hours=6)).timestamp()


class TestAC6BeginnVerschiebungNullOderUnterSchwelle:
    @pytest.mark.parametrize("metric", [GEWITTER_BEGINN, STARKREGEN_BEGINN])
    @pytest.mark.parametrize("verschiebung_s", [0, -1800, 1800])
    def test_null_oder_30_minuten_liefert_422(self, client, nutzer, metric, verschiebung_s):
        basis = _basis_epoche()
        body = _onset_change(basis, basis + verschiebung_s, metric)
        antworten = {lang: _post_trip(client, uid, body) for lang, uid in nutzer.items()}
        _assert_422_lokalisiert(antworten, "onset_shift_null")
        for resp in antworten.values():
            assert "0 h" not in resp.text, resp.text

    def test_zwei_stunden_frueher_bleibt_200(self, client, nutzer):
        """Kontrollfall AC-6/AC-11."""
        basis = _basis_epoche()
        resp = _post_trip(client, nutzer["de"], _onset_change(basis, basis - 7200))
        assert resp.status_code == 200, resp.text[:300]
        assert "2 h früher" in (resp.json().get("email_plain") or ""), resp.text[:600]


class TestAC7GrenzeAusDerSchwellenTabelle:
    @pytest.mark.parametrize("richtung,grenze_s", [
        ("frueher", MIN_FRUEHER_S), ("spaeter", MIN_SPAETER_S),
    ])
    def test_genau_auf_der_grenze_200_eine_sekunde_darunter_422(
        self, client, nutzer, richtung, grenze_s,
    ):
        vorzeichen = -1 if richtung == "frueher" else 1
        basis = _basis_epoche()
        auf = _post_trip(client, nutzer["de"],
                         _onset_change(basis, basis + vorzeichen * grenze_s))
        assert auf.status_code == 200, (
            f"{richtung}: Verschiebung genau auf der kleinsten Schwelle "
            f"({grenze_s} s) muss akzeptiert werden: {auf.text[:300]}"
        )
        drunter = _post_trip(client, nutzer["de"],
                             _onset_change(basis, basis + vorzeichen * (grenze_s - 1)))
        _assert_422_lokalisiert({"de": drunter}, "onset_shift_null")


# ─────────────────────────────────── AC-10 ───────────────────────────────────


def _seed_berlin_trip(user_id: str, trip_id: str) -> None:
    """Trip in Europe/Berlin (Garmisch/Zugspitzland). Etappe MORGEN -- fuer
    heute gibt es keine echten Segmente, die Vorschau baut Stub-Segmente
    (Zweig ohne frische Stundenreihen, Befund C5-18)."""
    ordner = get_briefings_dir(user_id)
    ordner.mkdir(parents=True, exist_ok=True)
    payload = {"id": trip_id, "name": "Berlin-Zonen-Trip", "stages": [{
        "id": "T1", "name": "Etappe 1", "date": TRIP_DATE,
        "waypoints": [
            {"id": "G1", "name": "Start", "lat": 47.4917, "lon": 11.0955,
             "elevation_m": 708},
            {"id": "G2", "name": "Ziel", "lat": 47.4210, "lon": 10.9850,
             "elevation_m": 2000},
        ],
    }]}
    (ordner / f"{trip_id}.json").write_text(json.dumps(payload), encoding="utf-8")


class TestAC10StubSegmenteInTripZone:
    def test_beginn_verschiebung_in_berliner_ortszeit(self, client, nutzer):
        """AC-10 (C5-18): war reproduzierbar und ist im Vorschau-Pfad behoben --
        die Stub-Segmente tragen die Koordinaten des ersten Wegpunkts statt
        0/0, damit `_tz_for_location` die Trip-Zone ergibt. Erwartung aus den Epochen hergeleitet, nicht aus der
        Implementierung abgeschrieben."""
        uid = nutzer["de"]
        _seed_berlin_trip(uid, "trip-berlin")
        basis = _basis_epoche()
        neu = basis - 7200
        resp = _post_trip(client, uid, _onset_change(basis, neu), trip_id="trip-berlin")
        assert resp.status_code == 200, resp.text[:300]
        plain = resp.json().get("email_plain") or ""

        berlin = ZoneInfo("Europe/Berlin")

        def hhmm(epoch: float, tz) -> str:
            return datetime.fromtimestamp(epoch, timezone.utc).astimezone(tz).strftime("%H:%M")

        assert hhmm(neu, berlin) != hhmm(neu, timezone.utc), "Positivkontrolle: Zonen muessen sich unterscheiden"
        for epoch in (basis, neu):
            assert hhmm(epoch, berlin) in plain, (
                f"Beginn muss in Berliner Ortszeit stehen ({hhmm(epoch, berlin)}), "
                f"nicht in UTC ({hhmm(epoch, timezone.utc)}): {plain!r}"
            )
