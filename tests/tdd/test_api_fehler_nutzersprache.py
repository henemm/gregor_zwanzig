"""API-Fehlermeldungen in der Kontosprache, mit stabilem ``code`` (Issue #2674).

SPEC: docs/specs/modules/i18n_p11_api_meldungen_ratsche_2674.md AC-1, AC-2,
AC-3, AC-8.

Echter FastAPI-Aufruf (TestClient auf ``api.main:app``), echte Router, echte
Dienste, echter Daten-Root je Test (``tests.helpers.vorschau_umgebung.env``).
Zwei Nutzer mit verschiedenen Sprachen (``user.json`` -> ``language``), niemals
``"default"``. Die deutschen Erwartungen sind die Texte der Ist-Fassung vor
der Umstellung (``git show origin/main:<datei>``, Stand 2175114cd).
"""
from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.loader import get_briefings_dir, get_data_dir
from app.user import SavedLocation

from tests.helpers.vorschau_umgebung import (
    TRIP_DATE,
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


@pytest.fixture
def client():
    from api.main import app

    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def nutzer(env):  # noqa: F811
    """Zwei echte Nutzer: ``en`` und ``de`` (Sprache aus ``user.json``)."""
    suffix = uuid.uuid4().hex[:6]
    paar = {"en": f"tdd-2674-en-{suffix}", "de": f"tdd-2674-de-{suffix}"}
    for lang, uid in paar.items():
        ordner = get_data_dir(uid)
        ordner.mkdir(parents=True, exist_ok=True)
        (ordner / "user.json").write_text(
            json.dumps({"id": uid, "language": lang}), encoding="utf-8")
    return paar


def _seed_trip_ohne_wegpunkte(user_id: str, trip_id: str) -> None:
    ordner = get_briefings_dir(user_id)
    ordner.mkdir(parents=True, exist_ok=True)
    payload = {"id": trip_id, "name": "Kurztrip", "stages": [{
        "id": "T1", "name": "Etappe 1", "date": TRIP_DATE,
        "waypoints": [{"id": "G1", "name": "Start", "lat": 47.27, "lon": 11.40,
                       "elevation_m": 600}],
    }]}
    (ordner / f"{trip_id}.json").write_text(json.dumps(payload), encoding="utf-8")


def _seed_compare_ohne_orte(user_id: str, preset_id: str) -> None:
    from tests.helpers.compare_briefings import write_compare_briefings

    write_compare_briefings(get_data_dir(user_id), [{
        "id": preset_id, "name": "Leer 2674", "user_id": user_id, "location_ids": [],
        "schedule": "daily", "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
        "forecast_hours": 48, "empfaenger": ["a@example.invalid"],
        "created_at": "2026-07-01T00:00:00Z",
    }])


def _compare_body(loc_id: str) -> dict:
    return {"changes": [{
        "location_id": loc_id, "metric": "gust_max_kmh", "old_value": 25.0,
        "new_value": 72.0, "delta": 47.0, "threshold": 60.0, "severity": "major",
        "direction": "increase",
    }]}


# --------------------------------------------------------------------- AC-1


def test_sms_vorschau_ohne_wegpunkte_in_kontosprache(client, nutzer):
    for uid in nutzer.values():
        _seed_trip_ohne_wegpunkte(uid, "kurz")
    en = client.get("/api/preview/kurz/sms", params={"user_id": nutzer["en"]})
    de = client.get("/api/preview/kurz/sms", params={"user_id": nutzer["de"]})
    assert en.status_code == de.status_code == 404, (en.text, de.text)
    assert en.json() == {
        "detail": "Trip 'kurz' has no stage with enough waypoints for a preview",
        "code": "vorschau_ohne_wegpunkte"}
    assert de.json() == {
        "detail": "Trip 'kurz' hat keine Etappe mit genug waypoints für eine Vorschau",
        "code": "vorschau_ohne_wegpunkte"}


def test_sms_vorschau_fremder_trip_404_in_kontosprache(client, nutzer):
    seed_trip(nutzer["de"], "nur-de", "GeheimTripDe")
    en = client.get("/api/preview/nur-de/sms", params={"user_id": nutzer["en"]})
    assert en.status_code == 404
    assert en.json() == {
        "detail": f"Trip 'nur-de' not found for user '{nutzer['en']}'",
        "code": "vorschau_trip_nicht_gefunden"}
    assert "GeheimTripDe" not in en.text


def test_sms_vorschau_ungueltiger_typ_in_kontosprache(client, nutzer):
    en = client.get("/api/preview/x/sms", params={"user_id": nutzer["en"], "type": "noon"})
    de = client.get("/api/preview/x/sms", params={"user_id": nutzer["de"], "type": "noon"})
    assert en.status_code == de.status_code == 422
    assert en.json() == {"detail": "Invalid type 'noon'", "code": "typ_ungueltig"}
    assert de.json() == {"detail": "Ungültiger type 'noon'", "code": "typ_ungueltig"}


# --------------------------------------------------------------------- AC-2


def test_vergleichs_alarm_vorschau_fremd_und_ohne_orte(client, nutzer):
    a, b = nutzer["en"], nutzer["de"]
    seed_compare(b, "cp-b", [SavedLocation(
        id="loc-b", name="Bertsdorf", lat=46.50, lon=11.35, elevation_m=262)])
    _seed_compare_ohne_orte(a, "cp-a-leer")
    _seed_compare_ohne_orte(b, "cp-b-leer")

    def post(eid, uid):
        return client.post(f"/api/briefings/{eid}/alert-preview",
                           params={"kind": "vergleich", "user_id": uid},
                           json=_compare_body("loc-b"))

    fremd = post("cp-b", a)
    assert fremd.status_code == 404
    assert fremd.json() == {
        "detail": f"Location comparison 'cp-b' not found for user '{a}'",
        "code": "vergleich_nicht_gefunden"}
    assert "Bertsdorf" not in fremd.text and "loc-b" not in fremd.text

    leer_en = post("cp-a-leer", a)
    assert leer_en.status_code == 422
    assert leer_en.json() == {
        "detail": "Invalid alert body: Location comparison 'cp-a-leer' has no locations "
                  "configured - there is nothing to compare.",
        "code": "vergleich_ohne_orte"}

    leer_de = post("cp-b-leer", b)
    assert leer_de.status_code == 422
    assert leer_de.json() == {
        "detail": "Ungültiger Alarm-Körper: Orts-Vergleich 'cp-b-leer' hat keine Orte "
                  "konfiguriert — es gibt nichts zu vergleichen.",
        "code": "vergleich_ohne_orte"}

    eigen_de = post("cp-b", b)
    assert eigen_de.status_code == 200, eigen_de.text[:300]


def test_vergleichs_alarm_vorschau_fremder_ort_behaelt_deutschen_text(client, nutzer):
    b = nutzer["de"]
    seed_compare(b, "cp-b", [SavedLocation(
        id="loc-b", name="Bertsdorf", lat=46.50, lon=11.35, elevation_m=262)])
    antwort = client.post("/api/briefings/cp-b/alert-preview",
                          params={"kind": "vergleich", "user_id": b},
                          json=_compare_body("loc-x"))
    assert antwort.status_code == 422
    assert antwort.json() == {
        "detail": "Ungültiger Alarm-Körper: Orte ['loc-x'] gehoeren nicht zu diesem "
                  "Orts-Vergleich",
        "code": "vergleich_orte_fremd"}


# --------------------------------------------------------------------- AC-3

_AC3 = [
    ({"changes": [{**TRIP_ALERT_BODY["changes"][0], "segment_id": "99"}]},
     "segment_unbekannt", "Unknown segment_id '99' in the trip",
     "Unbekannte segment_id '99' im Trip"),
    ({**TRIP_ALERT_BODY, "changes": [{**TRIP_ALERT_BODY["changes"][0], "metric": "foo"}]},
     "metrik_unbekannt", "Unknown metric 'foo' in changes",
     "Unbekannte Metrik 'foo' in changes"),
    ({**TRIP_ALERT_BODY, "onset": {
        "onset_minutes": 30, "onset_time": "10:00", "km_from": 0.0, "km_to": 1.0,
        "is_convective": False, "intensity_label": "x", "source_label": "y"}},
     "body_genau_einer",
     "Body must contain exactly one of 'onset', 'changes', 'official' or 'nowcast_frames'",
     "Body muss genau einen von 'onset', 'changes', 'official' oder 'nowcast_frames' "
     "enthalten"),
]


@pytest.mark.parametrize("body,code,text_en,text_de", _AC3)
def test_trip_alarm_vorschau_validierung_in_kontosprache(client, nutzer, body, code,
                                                          text_en, text_de):
    for lang, uid in nutzer.items():
        seed_trip(uid, "trip-x", "AlarmTrip")
        antwort = client.post("/api/trips/trip-x/alert-preview",
                              params={"user_id": uid}, json=body)
        assert antwort.status_code == 422, antwort.text[:300]
        erwartet = text_en if lang == "en" else text_de
        assert antwort.json() == {"detail": erwartet, "code": code}


def test_trip_alarm_vorschau_gueltig_und_pydantic_liste_unveraendert(client, nutzer):
    uid = nutzer["en"]
    seed_trip(uid, "trip-x", "AlarmTrip")
    ok = client.post("/api/trips/trip-x/alert-preview", params={"user_id": uid},
                     json=TRIP_ALERT_BODY)
    assert ok.status_code == 200, ok.text[:300]
    kaputt = client.post("/api/briefings/trip-x/alert-preview",
                         params={"kind": "route", "user_id": uid},
                         json={"changes": "kein-array"})
    assert kaputt.status_code == 422
    assert isinstance(kaputt.json()["detail"], list)
    assert kaputt.json()["detail"][0]["loc"] == ["changes"]


def test_validator_trip_nicht_gefunden_in_kontosprache(client, nutzer):
    en = client.get("/api/_validator/detector-thresholds",
                    params={"trip": "fehlt", "user_id": nutzer["en"]})
    de = client.get("/api/_validator/detector-thresholds",
                    params={"trip": "fehlt", "user_id": nutzer["de"]})
    assert en.status_code == de.status_code == 404
    assert en.json() == {"detail": f"Trip fehlt not found for user {nutzer['en']}",
                         "code": "trip_nicht_gefunden"}
    assert de.json() == {"detail": f"Trip fehlt nicht gefunden für User {nutzer['de']}",
                         "code": "trip_nicht_gefunden"}


# --------------------------------------------------------------------- AC-8


def test_fehler_ohne_code_behaelt_text(client, nutzer):
    antwort = client.get("/api/preview/.versteckt/sms", params={"user_id": nutzer["en"]})
    assert antwort.status_code == 422
    daten = antwort.json()
    assert isinstance(daten["detail"], str)
    assert daten == {"detail": "invalid trip_id: '.versteckt'", "code": "unbekannt"}


def test_gpx_nur_gpx_in_kontosprache(client, nutzer):
    for lang, erwartet in (("en", "Only .gpx files are allowed, not 'route.txt'"),
                           ("de", "Nur .gpx Dateien erlaubt, nicht 'route.txt'")):
        antwort = client.post("/api/gpx/parse", params={"user_id": nutzer[lang]},
                              files={"file": ("route.txt", b"<gpx/>", "text/plain")})
        assert antwort.status_code == 400, antwort.text[:300]
        assert antwort.json() == {"detail": erwartet, "code": "gpx_nur_gpx"}
