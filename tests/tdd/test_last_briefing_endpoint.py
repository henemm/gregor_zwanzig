"""#2346 S4: ``GET /api/_internal/next-briefings`` liefert ``last_briefing`` je Trip
und Ortsvergleich, abgeleitet aus dem Briefing-Log (#2281) -- nichts Neues persistiert.

Spec: docs/specs/modules/feat_2346_cockpit_paritaet.md (AC-13, AC-14)

Echte Dateien im isolierten Daten-Root (autouse ``_isolate_data_root``), echte
FastAPI-App, Zeit per ``freeze_time``. Zwei Nutzer mit GLEICHEN Kennungen und
verschiedenen Log-Eintraegen: liest der Endpoint den Log eines anderen Nutzers
(oder von ``"default"``), kippt die Antwort.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from freezegun import freeze_time

PFAD = "/api/_internal/next-briefings"
USER_A, USER_B = "lb-user-a", "lb-user-b"
TRIP_ID, PRESET_ID, ORT_ID = "geteilte-trip-id", "geteilte-preset-id", "ort-1"
D23, D24 = date(2026, 10, 23), date(2026, 10, 24)
JETZT = datetime(2026, 10, 23, 8, tzinfo=ZoneInfo("Europe/Paris")).astimezone(timezone.utc)
PARIS = (42.30, 8.93)

A_TRIP_ALT, A_TRIP_NEU = "2026-10-21T05:00:00+00:00", "2026-10-22T05:00:00+00:00"
A_HAND = "2026-10-22T16:30:00+00:00"       # Handversand (on_demand) zaehlt
A_PRESET = "2026-10-22T06:00:00+00:00"
B_TRIP, B_PRESET = "2026-10-10T05:00:00+00:00", "2026-10-11T06:00:00+00:00"


def _trip_json(trip_id: str) -> dict:
    return {
        "id": trip_id, "name": f"Trip {trip_id}",
        "stages": [
            {"id": f"{trip_id}-s{i}", "name": f"Etappe {i}", "date": d.isoformat(),
             "waypoints": [
                 {"id": f"{trip_id}-w{i}a", "name": "Start", "lat": PARIS[0],
                  "lon": PARIS[1], "elevation_m": 800},
                 {"id": f"{trip_id}-w{i}b", "name": "Ziel", "lat": PARIS[0] + 0.05,
                  "lon": PARIS[1] + 0.05, "elevation_m": 1200},
             ]}
            for i, d in enumerate((D23, D24))
        ],
        "report_config": {"enabled": True, "morning_time": "07:00:00",
                          "evening_time": "18:00:00"},
    }


def _preset_json(preset_id: str) -> dict:
    return {
        "id": preset_id, "kind": "vergleich", "name": f"Vergleich {preset_id}",
        "schedule": "daily", "weekday": None, "location_ids": [ORT_ID],
        "morning_enabled": True, "morning_time": "07:00:00",
        "evening_enabled": True, "evening_time": "18:00:00",
    }


def _anlegen(user_id: str, trip_id: str = TRIP_ID, preset_id: str = PRESET_ID) -> None:
    from app.loader import get_briefings_dir, save_location
    from app.user import SavedLocation

    ordner = get_briefings_dir(user_id)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / f"{trip_id}.json").write_text(json.dumps(_trip_json(trip_id)), encoding="utf-8")
    (ordner / f"{preset_id}.json").write_text(json.dumps(_preset_json(preset_id)), encoding="utf-8")
    save_location(SavedLocation(id=ORT_ID, name="Ort", lat=PARIS[0], lon=PARIS[1],
                                elevation_m=100), user_id)


def _log(user_id: str, eintraege: list) -> None:
    from app.loader import get_data_dir

    pfad = get_data_dir(user_id) / "briefing_log.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps({"entries": eintraege}), encoding="utf-8")


def _eintrag(typ: str, kennung: str, sent_at: str, on_demand: bool = False,
             alt: bool = False) -> dict:
    e = {"kind": "morning", "sent_at": sent_at, "channels": ["email"], "on_demand": on_demand}
    if alt:  # Alt-Eintrag vor #2281: nur trip_id, kein entity_*
        e["trip_id"] = kennung
    else:
        e.update({"entity_id": kennung, "entity_type": typ})
        if typ == "trip":
            e["trip_id"] = kennung
    return e


def _hole(user_id: str, **params) -> dict:
    from api.main import app

    with freeze_time(JETZT):
        resp = TestClient(app).get(PFAD, params={"user_id": user_id, **params})
    assert resp.status_code == 200, f"{resp.status_code}: {resp.text[:300]}"
    return resp.json()


def _gleicher_zeitpunkt(a: str | None, b: str) -> bool:
    return a is not None and datetime.fromisoformat(a) == datetime.fromisoformat(b)


def test_last_briefing_je_trip_und_vergleich_ist_der_juengste_eintrag():
    """AC-13: maximales ``sent_at`` je (Art, Kennung); Handversand zaehlt mit."""
    _anlegen(USER_A)
    _log(USER_A, [
        _eintrag("trip", TRIP_ID, A_TRIP_NEU),
        _eintrag("trip", TRIP_ID, A_TRIP_ALT),     # nicht chronologisch gespeichert
        _eintrag("trip", TRIP_ID, A_HAND, on_demand=True),
        _eintrag("compare", PRESET_ID, A_PRESET),
    ])
    out = _hole(USER_A)
    assert "last_briefing" in out["trips"][TRIP_ID], out
    assert _gleicher_zeitpunkt(out["trips"][TRIP_ID]["last_briefing"], A_HAND)
    assert _gleicher_zeitpunkt(out["compare"][PRESET_ID]["last_briefing"], A_PRESET)


def test_ohne_eintrag_oder_ohne_log_ist_last_briefing_null_aber_vorhanden():
    """AC-13: ``null`` = nie versendet -- der Schluessel fehlt nie, auch ohne Datei."""
    _anlegen(USER_A)
    out = _hole(USER_A)  # kein briefing_log.json
    assert "last_briefing" in out["trips"][TRIP_ID], out
    assert out["trips"][TRIP_ID]["last_briefing"] is None
    assert out["compare"][PRESET_ID]["last_briefing"] is None
    _log(USER_A, [_eintrag("trip", TRIP_ID, A_TRIP_NEU)])
    out = _hole(USER_A)
    assert _gleicher_zeitpunkt(out["trips"][TRIP_ID]["last_briefing"], A_TRIP_NEU)
    assert out["compare"][PRESET_ID]["last_briefing"] is None


def test_gleiche_kennung_trip_und_vergleich_wird_nach_art_getrennt():
    """Ein Trip-Eintrag darf nie als Vergleich-Versand erscheinen (Schluessel = Art+Kennung)."""
    _anlegen(USER_A, trip_id="gleich", preset_id="gleich")
    _log(USER_A, [_eintrag("trip", "gleich", A_TRIP_NEU)])
    out = _hole(USER_A)
    assert _gleicher_zeitpunkt(out["trips"]["gleich"]["last_briefing"], A_TRIP_NEU)
    assert out["compare"]["gleich"]["last_briefing"] is None


def test_alt_eintrag_ohne_entity_felder_gilt_als_trip():
    """Spiegel der Go-Leseregel: ``entity_id := trip_id``, ``entity_type := "trip"``."""
    _anlegen(USER_A)
    _log(USER_A, [_eintrag("trip", TRIP_ID, A_TRIP_ALT, alt=True)])
    out = _hole(USER_A)
    assert _gleicher_zeitpunkt(out["trips"][TRIP_ID]["last_briefing"], A_TRIP_ALT)
    assert out["compare"][PRESET_ID]["last_briefing"] is None


def test_zwei_nutzer_gleiche_kennungen_je_eigene_werte():
    """AC-14: A sieht nur A-Zeitpunkte, B nur B-Zeitpunkte (Gegenprobe: gleiche IDs)."""
    for uid in (USER_A, USER_B):
        _anlegen(uid)
    _log(USER_A, [_eintrag("trip", TRIP_ID, A_TRIP_NEU), _eintrag("compare", PRESET_ID, A_PRESET)])
    _log(USER_B, [_eintrag("trip", TRIP_ID, B_TRIP), _eintrag("compare", PRESET_ID, B_PRESET)])
    a, b = _hole(USER_A), _hole(USER_B)
    assert _gleicher_zeitpunkt(a["trips"][TRIP_ID]["last_briefing"], A_TRIP_NEU)
    assert _gleicher_zeitpunkt(a["compare"][PRESET_ID]["last_briefing"], A_PRESET)
    assert _gleicher_zeitpunkt(b["trips"][TRIP_ID]["last_briefing"], B_TRIP)
    assert _gleicher_zeitpunkt(b["compare"][PRESET_ID]["last_briefing"], B_PRESET)
    assert B_TRIP not in json.dumps(a) and A_TRIP_NEU not in json.dumps(b)


def test_nutzer_ohne_eigenen_log_bekommt_nichts_von_einem_anderen():
    """AC-14: B hat KEINEN Log -- ein Rueckfall auf ``default`` oder einen fremden Log zeigte A-Werte."""
    for uid in (USER_A, USER_B):
        _anlegen(uid)
    _log(USER_A, [_eintrag("trip", TRIP_ID, A_TRIP_NEU)])
    b = _hole(USER_B)
    assert "last_briefing" in b["trips"][TRIP_ID], b
    assert b["trips"][TRIP_ID]["last_briefing"] is None
    assert A_TRIP_NEU not in json.dumps(b)


def test_filter_trip_id_liefert_last_briefing_nur_fuer_diesen_trip():
    _anlegen(USER_A)
    _log(USER_A, [_eintrag("trip", TRIP_ID, A_TRIP_NEU)])
    out = _hole(USER_A, trip_id=TRIP_ID)
    assert out["compare"] == {}
    assert _gleicher_zeitpunkt(out["trips"][TRIP_ID]["last_briefing"], A_TRIP_NEU)


def test_defekter_log_ist_fail_soft_und_wird_nicht_angefasst():
    """Kein 500, ``null``, die Datei bleibt byte-gleich liegen (rein lesend, nichts beiseitegelegt)."""
    from app.loader import get_data_dir

    _anlegen(USER_A)
    pfad = get_data_dir(USER_A) / "briefing_log.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text("{kaputt", encoding="utf-8")
    out = _hole(USER_A)
    assert "last_briefing" in out["trips"][TRIP_ID], out
    assert out["trips"][TRIP_ID]["last_briefing"] is None
    assert pfad.read_text(encoding="utf-8") == "{kaputt"
    assert [p.name for p in pfad.parent.iterdir() if "briefing_log" in p.name] == ["briefing_log.json"]


def test_helfer_letzte_briefings_liefert_art_kennung_schluessel():
    """AC-13: Helfer ``letzte_briefings(user_id)`` -> ``{(art, kennung): sent_at_iso}``."""
    from services.briefing_log import letzte_briefings

    _log(USER_A, [
        _eintrag("trip", TRIP_ID, A_TRIP_ALT), _eintrag("trip", TRIP_ID, A_TRIP_NEU),
        _eintrag("compare", PRESET_ID, A_PRESET),
        _eintrag("trip", "alt-trip", A_TRIP_ALT, alt=True),
    ])
    erg = letzte_briefings(USER_A)
    assert set(erg) == {("trip", TRIP_ID), ("compare", PRESET_ID), ("trip", "alt-trip")}
    assert _gleicher_zeitpunkt(erg[("trip", TRIP_ID)], A_TRIP_NEU)
    assert letzte_briefings(USER_B) == {}
