"""TDD-RED: Issue #2069 -- Alarm-Vorschau rendert echte Trip-Segmente.

SPEC: docs/specs/modules/alert_preview_echte_segmente.md (AC-1 bis AC-7, AC-9)

Die Alarm-Vorschau (``POST /api/trips/{id}/alert-preview``, dieselbe Logik
hinter der Beispiel-Warnung im Alarme-Reiter) soll zeigen, was versendet
wuerde: echte Etappen-Segmente des Bezugstags (heute, sonst naechste, sonst
letzte Etappe) statt Platzhaltern mit Distanz 0, gemessene km-Spanne auch im
Zweig ``official``, und keine stille Annahme erfundener Segment-Kennungen.

Kein Mock: echter FastAPI-TestClient auf ``api.main:app``, echte Trip-Dateien
im isolierten Daten-Root (``tests.helpers.vorschau_umgebung.env``), echte
Nutzerkennungen (nie ``"default"``). Ohne Anker im Nutzerspeicher beschafft
``trip_preview_series`` nichts (kein Netz). Erwartete km-Spannen entstehen
ueber DIESELBE Produktions-Segmentierung (``convert_trip_to_segments`` +
``measured_segment_km``), nicht von Hand.

Die Etappe ist vermessen (``distance_from_start_km`` an jedem Wegpunkt, je
Teilstrecke >= Luftlinie, Issue #2036) -- nur dann darf die km-Spanne die
Segmentnummer als Ortsangabe verdraengen. Mit Platzhalter-Segmenten zeigt die
Vorschau ``Segment 2``, mit echten ``km 8-17``.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, time, timedelta

import pytest
from fastapi.testclient import TestClient

from app.loader import get_briefings_dir, get_data_dir

from tests.helpers.ortstag import ortstag
from tests.helpers.vorschau_umgebung import env  # noqa: F401  (Fixture)

LAT, LON = 47.0, 11.0
KANAELE = ("subject", "email_plain", "telegram", "sms")

GUST_CHANGE = {
    "metric": "gust_max_kmh", "old_value": 25.0, "new_value": 72.0, "delta": 47.0,
    "threshold": 60.0, "severity": "major", "direction": "increase", "segment_id": "2",
}
OFFICIAL = {
    "source": "geosphere_warn", "hazard": "thunderstorm", "level": 3,
    "label": "Gewitter", "segment_ids": ["2"],
}


def _wegpunkte(km: tuple[float, float, float] = (0.0, 8.0, 17.0)) -> list[dict]:
    return [
        {"id": "G1", "name": "Start", "lat": LAT, "lon": LON, "elevation_m": 1000,
         "distance_from_start_km": km[0], "arrival_override": "08:00"},
        {"id": "G2", "name": "Joch", "lat": 47.05, "lon": 11.05, "elevation_m": 1400,
         "distance_from_start_km": km[1], "arrival_override": "10:00"},
        {"id": "G3", "name": "Ziel", "lat": 47.1, "lon": 11.1, "elevation_m": 900,
         "distance_from_start_km": km[2], "arrival_override": "12:00"},
    ]


def _heute() -> date:
    return ortstag(LAT, LON)


def _trip_anlegen(uid: str, trip_id: str, etappen_tage: list[int], *,
                  km: tuple[float, float, float] = (0.0, 8.0, 17.0),
                  name: str = "Echt-Trip") -> list[date]:
    """Trip mit je einer vermessenen Etappe pro Tagesversatz (relativ zum Ortstag)."""
    tage = [_heute() + timedelta(days=d) for d in etappen_tage]
    ordner = get_briefings_dir(uid)
    ordner.mkdir(parents=True, exist_ok=True)
    stages = [
        {"id": f"T{i + 1}", "name": f"Etappe {i + 1}", "date": tag.isoformat(),
         "waypoints": _wegpunkte(km)}
        for i, tag in enumerate(tage)
    ]
    (ordner / f"{trip_id}.json").write_text(
        json.dumps({"id": trip_id, "name": name, "stages": stages}), encoding="utf-8")
    return tage


def _trip_ohne_etappen(uid: str, trip_id: str) -> None:
    ordner = get_briefings_dir(uid)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / f"{trip_id}.json").write_text(
        json.dumps({"id": trip_id, "name": "Leer-Trip", "stages": []}), encoding="utf-8")


def _sprache(uid: str, lang: str) -> None:
    ordner = get_data_dir(uid)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "user.json").write_text(
        json.dumps({"id": uid, "language": lang}), encoding="utf-8")


def _erwartete_spanne(uid: str, trip_id: str, tag: date, segment_id: str = "2") -> str:
    """Ortsangabe ``km a-b`` aus der Produktions-Segmentierung des Tages."""
    from api.routers.validator import _load_trip_for_validator
    from services.trip_segments import convert_trip_to_segments, measured_segment_km

    trip = _load_trip_for_validator(uid, trip_id)
    spannen = measured_segment_km(convert_trip_to_segments(trip, tag))
    assert segment_id in spannen, f"Fixtur-Schutz: Etappe muss vermessen sein, bekam {spannen!r}"
    a, b = spannen[segment_id]
    assert int(round(a)) != int(round(b)), "Fixtur-Schutz: Spanne muss Information tragen"
    return f"km {int(round(a))}-{int(round(b))}"


@pytest.fixture
def client():
    from api.main import app

    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def uid(env):  # noqa: F811
    _sprache(env, "de")
    return env


def _post(client, uid: str, trip_id: str, body: dict):
    return client.post(f"/api/trips/{trip_id}/alert-preview",
                       params={"user_id": uid}, json=body)


def _changes_body(segment_id: str = "2", *, mit_zeiten: bool = True) -> dict:
    body = {"changes": [{**GUST_CHANGE, "segment_id": segment_id}]}
    if mit_zeiten:
        body["segment_times"] = [{"segment_id": segment_id, "start": "10:00", "end": "12:00"}]
    return body


# --------------------------------------------------------------------- AC-1

@pytest.mark.parametrize("mit_zeiten", [True, False], ids=["segment_times", "synthetisiert"])
def test_ac1_heute_ohne_anker_zeigt_echte_km_spanne_in_allen_kanaelen(client, uid, mit_zeiten):
    """Etappe heute, kein Anker: alle Kanaele und der Betreff nennen die echte
    gemessene km-Spanne der Etappe statt der Platzhalter-Ortsangabe."""
    (heute,) = _trip_anlegen(uid, "trip-heute", [0])
    erwartet = _erwartete_spanne(uid, "trip-heute", heute)

    antwort = _post(client, uid, "trip-heute", _changes_body(mit_zeiten=mit_zeiten))
    assert antwort.status_code == 200, antwort.text[:300]
    daten = antwort.json()
    for kanal in KANAELE:
        assert erwartet in daten[kanal], f"{kanal}: {daten[kanal]!r}"
    assert daten.get("stundenreihe") is False, daten.keys()


# --------------------------------------------------------------------- AC-2

def test_ac2_geplanter_trip_nutzt_naechste_etappe_als_bezugstag(client, uid):
    """Trip startet in 5 Tagen: 200, ``bezugstag`` = Etappendatum, echte Werte."""
    (etappe,) = _trip_anlegen(uid, "trip-geplant", [5])
    erwartet = _erwartete_spanne(uid, "trip-geplant", etappe)

    antwort = _post(client, uid, "trip-geplant", _changes_body())
    assert antwort.status_code == 200, antwort.text[:300]
    daten = antwort.json()
    assert daten.get("bezugstag") == etappe.isoformat(), daten.get("bezugstag")
    for kanal in KANAELE:
        assert erwartet in daten[kanal], f"{kanal}: {daten[kanal]!r}"


def test_ac2_geplanter_trip_ohne_segment_times_synthetisiert_aus_bezugstag(client, uid):
    """Ohne ``segment_times``: Synthese aus der naechsten Etappe statt 422."""
    _trip_anlegen(uid, "trip-geplant", [5, 6])

    antwort = _post(client, uid, "trip-geplant", _changes_body(mit_zeiten=False))
    assert antwort.status_code == 200, antwort.text[:300]


def test_ac2_vergangener_trip_nutzt_letzte_etappe(client, uid):
    """Alle Etappen vorbei: ``bezugstag`` = letzte Etappe."""
    tage = _trip_anlegen(uid, "trip-vorbei", [-6, -4])

    antwort = _post(client, uid, "trip-vorbei", _changes_body())
    assert antwort.status_code == 200, antwort.text[:300]
    daten = antwort.json()
    assert daten.get("bezugstag") == tage[-1].isoformat(), daten.get("bezugstag")
    erwartet = _erwartete_spanne(uid, "trip-vorbei", tage[-1])
    assert erwartet in daten["email_plain"], daten["email_plain"]


def test_ac2_heute_hat_vorrang_vor_naechster_etappe(client, uid):
    """Heute laeuft eine Etappe, morgen die naechste: Bezugstag ist heute."""
    tage = _trip_anlegen(uid, "trip-laeuft", [0, 1])

    antwort = _post(client, uid, "trip-laeuft", _changes_body())
    assert antwort.status_code == 200, antwort.text[:300]
    assert antwort.json().get("bezugstag") == tage[0].isoformat()


# --------------------------------------------------------------------- AC-3

@pytest.mark.parametrize("versatz", [0, 5], ids=["heute", "geplant"])
def test_ac3_official_zeigt_gemessene_km_spanne_wie_der_versand(client, uid, versatz):
    """``official`` reicht ``segment_km`` der Bezugstag-Segmente durch: die
    amtliche Warnung nennt dieselbe km-Spanne wie der Versand."""
    (tag,) = _trip_anlegen(uid, "trip-amtlich", [versatz])
    erwartet = _erwartete_spanne(uid, "trip-amtlich", tag)

    antwort = _post(client, uid, "trip-amtlich", {"official": [OFFICIAL]})
    assert antwort.status_code == 200, antwort.text[:300]
    daten = antwort.json()
    for kanal in KANAELE:
        assert erwartet in daten[kanal], f"{kanal}: {daten[kanal]!r}"


def test_ac3_official_identisch_zum_direkten_renderaufruf_mit_segment_km(client, uid):
    """Fidelity: Text der Vorschau == direkter Aufruf mit ``measured_segment_km``."""
    from api.routers.validator import _load_trip_for_validator
    from output.renderers.alert.official_alerts import (
        build_official_alert_notices, render_official_alert_sms,
    )
    from services.official_alerts.models import OfficialAlert
    from services.trip_segments import convert_trip_to_segments, measured_segment_km
    from services.validator_render_service import _alert_tz_for_trip

    (tag,) = _trip_anlegen(uid, "trip-amtlich", [2])
    trip = _load_trip_for_validator(uid, "trip-amtlich")
    notices = build_official_alert_notices(
        trip,
        [(OfficialAlert(source="geosphere_warn", hazard="thunderstorm", level=3,
                        label="Gewitter"), ["2"])],
        segment_km=measured_segment_km(convert_trip_to_segments(trip, tag)),
    )
    erwartet_sms = render_official_alert_sms(notices, tz=_alert_tz_for_trip(trip))

    antwort = _post(client, uid, "trip-amtlich", {"official": [OFFICIAL]})
    assert antwort.status_code == 200, antwort.text[:300]
    assert antwort.json()["sms"] == erwartet_sms


def test_ac3_official_ohne_segment_ids_bleibt_200(client, uid):
    _trip_anlegen(uid, "trip-amtlich", [3])
    antwort = _post(client, uid, "trip-amtlich", {"official": [{**OFFICIAL, "segment_ids": []}]})
    assert antwort.status_code == 200, antwort.text[:300]


# --------------------------------------------------------------------- AC-4

@pytest.mark.parametrize("zweig", ["changes", "changes_ohne_zeiten", "official"])
def test_ac4_erfundene_segment_id_bei_geplantem_trip_wird_abgelehnt(client, uid, zweig):
    """Trip laeuft nicht heute: erfundene ``segment_id`` ``99`` -> 422
    ``segment_unbekannt``, nie eine stille Vorschau."""
    _trip_anlegen(uid, "trip-geplant", [4])
    body = {
        "changes": _changes_body("99"),
        "changes_ohne_zeiten": _changes_body("99", mit_zeiten=False),
        "official": {"official": [{**OFFICIAL, "segment_ids": ["99"]}]},
    }[zweig]

    antwort = _post(client, uid, "trip-geplant", body)
    assert antwort.status_code == 422, antwort.text[:300]
    assert antwort.json().get("code") == "segment_unbekannt"


# --------------------------------------------------------------------- AC-5

@pytest.mark.parametrize("zweig", ["changes", "official"])
def test_ac5_trip_ohne_etappen_mit_segment_id_ergibt_trip_ohne_segmente(client, uid, zweig):
    _trip_ohne_etappen(uid, "trip-leer")
    body = _changes_body("1") if zweig == "changes" else {"official": [{**OFFICIAL, "segment_ids": ["1"]}]}

    antwort = _post(client, uid, "trip-leer", body)
    assert antwort.status_code == 422, antwort.text[:300]
    assert antwort.json().get("code") == "trip_ohne_segmente"


def test_ac5_trip_ohne_etappen_official_ohne_segment_ids_bleibt_200(client, uid):
    _trip_ohne_etappen(uid, "trip-leer")
    antwort = _post(client, uid, "trip-leer", {"official": [{**OFFICIAL, "segment_ids": []}]})
    assert antwort.status_code == 200, antwort.text[:300]


def test_ac5_trip_ohne_segmente_meldung_in_kontosprache_de_und_en(client, env):  # noqa: F811
    """Gleicher Code in beiden Sprachen, Text aus dem Katalog (kein Schluessel)."""
    texte = {}
    for lang in ("de", "en"):
        nutzer = f"{env}-{lang}"
        _sprache(nutzer, lang)
        _trip_ohne_etappen(nutzer, "trip-leer")
        antwort = _post(client, nutzer, "trip-leer", _changes_body("1"))
        assert antwort.status_code == 422, antwort.text[:300]
        daten = antwort.json()
        assert daten.get("code") == "trip_ohne_segmente", daten
        assert "api.fehler" not in daten["detail"], daten["detail"]
        texte[lang] = daten["detail"]
    assert texte["de"] != texte["en"], texte


# --------------------------------------------------------------------- AC-6

def test_ac6_tagesbezug_wie_versand_am_bezugstag(client, uid):
    """Trip startet in 3 Tagen; eine Beginn-Verschiebung auf 14:00 des
    Bezugstags lautet wie ein Versand AM Bezugstag: kein ``in 3 Tagen``, kein
    ``morgen``, kein Wochentagskuerzel vor der Uhrzeit."""
    from utils.timezone import tz_for_coords

    (tag,) = _trip_anlegen(uid, "trip-tagesbezug", [3])
    tz = tz_for_coords(LAT, LON)
    alt = datetime.combine(tag, time(11, 0), tzinfo=tz).timestamp()
    neu = datetime.combine(tag, time(14, 0), tzinfo=tz).timestamp()
    body = {
        "changes": [{
            "metric": "thunder_onset_utc", "old_value": alt, "new_value": neu,
            "delta": neu - alt, "threshold": 3600.0, "severity": "major",
            "direction": "increase", "segment_id": "2",
        }],
        "segment_times": [{"segment_id": "2", "start": "10:00", "end": "12:00"}],
    }

    antwort = _post(client, uid, "trip-tagesbezug", body)
    assert antwort.status_code == 200, antwort.text[:300]
    daten = antwort.json()
    from output.renderers.alert.project import _de_weekday_short

    wochentag = _de_weekday_short(datetime.combine(tag, time(14, 0), tzinfo=tz))
    for kanal in ("email_plain", "telegram"):
        text = daten[kanal]
        assert "14:00" in text, text
        assert "in 3 Tagen" not in text, f"{kanal}: {text!r}"
        assert "morgen" not in text.lower(), f"{kanal}: {text!r}"
        assert f"{wochentag} 14:00" not in text, f"{kanal}: {text!r}"


# --------------------------------------------------------------------- AC-7

def test_ac7_antwort_traegt_neue_felder_und_alle_altfelder(client, uid):
    (etappe,) = _trip_anlegen(uid, "trip-felder", [2])
    antwort = _post(client, uid, "trip-felder", _changes_body())
    assert antwort.status_code == 200, antwort.text[:300]
    daten = antwort.json()
    for alt in ("subject", "email_html", "email_plain", "telegram", "sms"):
        assert isinstance(daten.get(alt), str) and daten[alt], alt
    assert daten.get("bezugstag") == etappe.isoformat()
    assert daten.get("stundenreihe") is False


def test_ac7_mit_anker_und_stundenreihe_ist_stundenreihe_true(env, monkeypatch, tmp_path):  # noqa: F811
    """Anker-Pfad #1737: mit Anker und frischer Reihe meldet die Antwort
    ``stundenreihe: true`` und den heutigen Bezugstag."""
    from api.routers.validator import AlertPreviewBody, alert_preview
    from tests.tdd.test_alert_hour_rows import TRIP_LAT, TRIP_LON, TRIP_STURM, _plant, _trip_anker_schreiben
    from tests.tdd.test_alert_preview_real_stage_ids import _body_wie_oberflaeche, _trip_mit_echter_etappe

    trip = _trip_mit_echter_etappe(env)
    _trip_anker_schreiben(monkeypatch, tmp_path, env, trip, {}, "anker-2069")
    _plant(tmp_path, monkeypatch, "sturm", TRIP_STURM)

    vorschau = alert_preview(
        trip.id, AlertPreviewBody.model_validate(_body_wie_oberflaeche("1")), user_id=env)
    assert vorschau.get("stundenreihe") is True
    assert vorschau.get("bezugstag") == ortstag(TRIP_LAT, TRIP_LON).isoformat()


def test_ac7_onset_zweig_bleibt_ohne_bezugstag(client, uid):
    """``onset`` braucht keinen Bezug: ``bezugstag`` ist ``null``."""
    _trip_anlegen(uid, "trip-onset", [2])
    antwort = _post(client, uid, "trip-onset", {"onset": {
        "onset_minutes": 30, "onset_time": "10:00", "km_from": 1.0, "km_to": 3.0,
        "is_convective": False, "intensity_label": "kräftig", "source_label": "Radar",
    }})
    assert antwort.status_code == 200, antwort.text[:300]
    daten = antwort.json()
    assert "bezugstag" in daten and daten["bezugstag"] is None, daten.keys()


# --------------------------------------------------------------------- AC-9

def test_ac9_zwei_nutzer_sehen_je_eigene_segmente(client, env):  # noqa: F811
    """Gleiche Trip-ID, verschiedene Etappen: jeder Nutzer sieht seine eigene
    km-Spanne und seinen eigenen Bezugstag; fremde Trip-ID bleibt 404."""
    a, b = f"{env}-a", f"{env}-b"
    for n in (a, b):
        _sprache(n, "de")
    (tag_a,) = _trip_anlegen(a, "trip-x", [2], km=(0.0, 8.0, 17.0))
    (tag_b,) = _trip_anlegen(b, "trip-x", [4], km=(0.0, 11.0, 23.0))
    _trip_anlegen(a, "nur-a", [2])

    for nutzer, tag, fremd in ((a, tag_a, tag_b), (b, tag_b, tag_a)):
        antwort = _post(client, nutzer, "trip-x", _changes_body())
        assert antwort.status_code == 200, antwort.text[:300]
        daten = antwort.json()
        assert daten.get("bezugstag") == tag.isoformat()
        assert daten.get("bezugstag") != fremd.isoformat()
        assert _erwartete_spanne(nutzer, "trip-x", tag) in daten["email_plain"]

    assert "km 11-23" not in _post(client, a, "trip-x", _changes_body()).json()["email_plain"]
    assert _post(client, b, "nur-a", _changes_body()).status_code == 404
