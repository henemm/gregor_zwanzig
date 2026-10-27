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
    """Ein Trip-Eintrag darf nie als Vergleich-Versand erscheinen (Schluessel = Art+Kennung).

    ``briefings/`` ist seit S7b der EINE Speicher beider Arten (eine Datei je Kennung),
    Trip und Vergleich koennen dort also nicht gleichzeitig dieselbe Kennung tragen.
    Der Log aber kann es: ein Trip-Eintrag mit der Kennung ``gleich`` (z.B. von einem
    geloeschten Trip) bleibt liegen, waehrend jetzt ein Vergleich ``gleich`` heisst.
    Schluege der Endpoint nur nach Kennung nach, erschiene der Trip-Versand am Vergleich.
    """
    _anlegen(USER_A, trip_id=TRIP_ID, preset_id="gleich")
    _log(USER_A, [_eintrag("trip", "gleich", A_TRIP_NEU)])
    out = _hole(USER_A)
    assert out["compare"]["gleich"]["last_briefing"] is None, out
    assert out["trips"][TRIP_ID]["last_briefing"] is None, out

    # Eigener Vergleich-Versand (aelter als der Trip-Eintrag): nur DER zaehlt.
    _log(USER_A, [_eintrag("trip", "gleich", A_TRIP_NEU),
                  _eintrag("compare", "gleich", A_TRIP_ALT)])
    out = _hole(USER_A)
    assert _gleicher_zeitpunkt(out["compare"]["gleich"]["last_briefing"], A_TRIP_ALT), out
    assert out["trips"][TRIP_ID]["last_briefing"] is None, out


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


def test_filter_preset_id_liefert_last_briefing_nur_fuer_diesen_vergleich():
    """Spiegel zum trip_id-Filter: nur der gewaehlte Vergleich, mit SEINEM Zeitpunkt."""
    _anlegen(USER_A, trip_id=TRIP_ID, preset_id=PRESET_ID)
    _anlegen(USER_A, trip_id=TRIP_ID, preset_id="anderer-vergleich")
    _log(USER_A, [
        _eintrag("trip", TRIP_ID, A_TRIP_NEU),
        _eintrag("compare", PRESET_ID, A_PRESET),
        _eintrag("compare", "anderer-vergleich", A_HAND),
    ])
    out = _hole(USER_A, preset_id=PRESET_ID)
    assert out["trips"] == {}, out
    assert set(out["compare"]) == {PRESET_ID}, out
    assert _gleicher_zeitpunkt(out["compare"][PRESET_ID]["last_briefing"], A_PRESET), out


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


def test_juengster_nach_zeitpunkt_nicht_nach_position_oder_zeichenkette():
    """AC-13: Maximum steht in der MITTE, Offsets gemischt.

    ``05:00-05:00`` (= 10:00Z) ist juenger als ``11:00+02:00`` (= 09:00Z), obwohl der
    Zeichenkettenvergleich ``11:00`` vorne saehe; der letzte Eintrag ist der aelteste.
    """
    neun_z, zehn_z = "2026-10-22T11:00:00+02:00", "2026-10-22T05:00:00-05:00"
    _anlegen(USER_A)
    _log(USER_A, [
        _eintrag("trip", TRIP_ID, neun_z),
        _eintrag("trip", TRIP_ID, zehn_z),                       # Maximum, Mitte
        _eintrag("trip", TRIP_ID, "2026-10-21T20:00:00+00:00"),  # aeltester, zuletzt
        _eintrag("compare", PRESET_ID, "2026-10-22T07:30:00+00:00"),
        _eintrag("compare", PRESET_ID, "2026-10-22T08:00:00-03:00"),  # 11:00Z, Mitte
        _eintrag("compare", PRESET_ID, "2026-10-22T12:00:00+02:00"),  # 10:00Z
    ])
    out = _hole(USER_A)
    assert _gleicher_zeitpunkt(out["trips"][TRIP_ID]["last_briefing"], zehn_z), out
    assert _gleicher_zeitpunkt(out["compare"][PRESET_ID]["last_briefing"],
                               "2026-10-22T08:00:00-03:00"), out


def test_log_wird_je_anfrage_genau_einmal_gelesen(monkeypatch):
    """AC-13: bei mehreren Trips und Vergleichen EIN Log-Lesen je Anfrage.

    Der Endpunkt importiert ``letzte_briefings`` zur Laufzeit aus
    ``services.briefing_log`` -- dort wird gezaehlt; der Zaehler ruft das Original,
    die Werte muessen weiterhin stimmen.
    """
    import services.briefing_log as bl

    original, aufrufe = bl.letzte_briefings, []

    def zaehler(user_id):
        aufrufe.append(user_id)
        return original(user_id)

    monkeypatch.setattr(bl, "letzte_briefings", zaehler)
    _anlegen(USER_A, trip_id="t1", preset_id="p1")
    _anlegen(USER_A, trip_id="t2", preset_id="p2")
    _log(USER_A, [_eintrag("trip", "t1", A_TRIP_NEU), _eintrag("trip", "t2", A_TRIP_ALT),
                  _eintrag("compare", "p1", A_PRESET), _eintrag("compare", "p2", B_PRESET)])
    out = _hole(USER_A)
    assert aufrufe == [USER_A], aufrufe
    assert set(out["trips"]) == {"t1", "t2"} and set(out["compare"]) == {"p1", "p2"}, out
    assert _gleicher_zeitpunkt(out["trips"]["t1"]["last_briefing"], A_TRIP_NEU)
    assert _gleicher_zeitpunkt(out["trips"]["t2"]["last_briefing"], A_TRIP_ALT)
    assert _gleicher_zeitpunkt(out["compare"]["p1"]["last_briefing"], A_PRESET)
    assert _gleicher_zeitpunkt(out["compare"]["p2"]["last_briefing"], B_PRESET)


def test_kaputte_eintraege_loeschen_die_gueltigen_nicht():
    """Einzelne Muellzeilen (``"kaputt"``, ``None``, Zahl) werden uebersprungen, die
    gueltigen Eintraege desselben und anderer Objekte bleiben sichtbar; ein naiver
    Zeitpunkt (ohne Offset) gilt als UTC und ist mit Offset-Zeitpunkten vergleichbar."""
    naiv = "2026-10-22T10:30:00"                 # als UTC: 10:30Z
    _anlegen(USER_A)
    _log(USER_A, [
        _eintrag("trip", TRIP_ID, "kaputt"),
        _eintrag("trip", TRIP_ID, A_TRIP_NEU),
        _eintrag("trip", TRIP_ID, None),
        _eintrag("trip", TRIP_ID, 1761112800),
        _eintrag("trip", TRIP_ID, "2026-10-20T05:00:00"),  # naiv, aelter
        _eintrag("compare", PRESET_ID, "2026-10-22T12:00:00+02:00"),  # 10:00Z
        _eintrag("compare", PRESET_ID, naiv),        # juenger nur bei UTC-Annahme
        _eintrag("compare", PRESET_ID, "kaputt"),
    ])
    out = _hole(USER_A)
    assert _gleicher_zeitpunkt(out["trips"][TRIP_ID]["last_briefing"], A_TRIP_NEU), out
    assert _gleicher_zeitpunkt(out["compare"][PRESET_ID]["last_briefing"], naiv), out


def test_listenelemente_ohne_objekt_loeschen_die_gueltigen_nicht():
    """Ganze Listenelemente, die kein Objekt sind (``"kaputt"``, ``null``, Zahl, Liste),
    werden uebersprungen; Trip UND Vergleich behalten ihr ``last_briefing`` statt dass
    der fail-soft-Pfad am Endpunkt alles auf ``null`` setzt."""
    _anlegen(USER_A)
    _log(USER_A, [
        "kaputt",
        _eintrag("trip", TRIP_ID, A_TRIP_NEU),
        None,
        42,
        _eintrag("compare", PRESET_ID, A_PRESET),
        [],
    ])
    out = _hole(USER_A)
    assert out["trips"][TRIP_ID]["last_briefing"] is not None, out
    assert out["compare"][PRESET_ID]["last_briefing"] is not None, out
    assert _gleicher_zeitpunkt(out["trips"][TRIP_ID]["last_briefing"], A_TRIP_NEU), out
    assert _gleicher_zeitpunkt(out["compare"][PRESET_ID]["last_briefing"], A_PRESET), out


def test_scheiternder_log_helfer_gibt_200_mit_null_und_intakten_next_feldern(monkeypatch):
    """Fail-soft am Endpunkt: wirft das Log-Lesen, bleibt die Antwort 200, jedes
    ``last_briefing`` ist ``null`` und die uebrigen Felder sind unveraendert."""
    import services.briefing_log as bl

    _anlegen(USER_A)
    _log(USER_A, [_eintrag("trip", TRIP_ID, A_TRIP_NEU), _eintrag("compare", PRESET_ID, A_PRESET)])
    vorher = _hole(USER_A)

    def wirft(user_id):
        raise RuntimeError("Log nicht lesbar")

    monkeypatch.setattr(bl, "letzte_briefings", wirft)
    nachher = _hole(USER_A)  # prueft 200
    for art, kennung in (("trips", TRIP_ID), ("compare", PRESET_ID)):
        assert "last_briefing" in nachher[art][kennung], nachher
        assert nachher[art][kennung]["last_briefing"] is None, nachher
        rest_vorher = {k: v for k, v in vorher[art][kennung].items() if k != "last_briefing"}
        rest_nachher = {k: v for k, v in nachher[art][kennung].items() if k != "last_briefing"}
        assert rest_vorher and rest_nachher == rest_vorher, (vorher, nachher)


def test_ohne_termin_bleibt_der_letzte_versand_sichtbar():
    """AC-15: Trip beendet (alle Etappen vorbei) und Vergleich pausiert -- ``at`` ist
    ``null``, ``reason`` traegt den Grund, ``last_briefing`` bleibt der Log-Zeitpunkt.
    Wer ``last_briefing`` nur bei vorhandenem ``at`` setzte, verloere ihn genau hier."""
    from app.loader import get_briefings_dir

    _anlegen(USER_A)
    ordner = get_briefings_dir(USER_A)
    trip = _trip_json(TRIP_ID)
    for i, stage in enumerate(trip["stages"]):
        stage["date"] = date(2026, 10, 10 + i).isoformat()   # vor JETZT -> beendet
    (ordner / f"{TRIP_ID}.json").write_text(json.dumps(trip), encoding="utf-8")
    preset = {**_preset_json(PRESET_ID), "paused_at": "2026-10-20T10:00:00+00:00"}
    (ordner / f"{PRESET_ID}.json").write_text(json.dumps(preset), encoding="utf-8")
    _log(USER_A, [_eintrag("trip", TRIP_ID, A_TRIP_NEU), _eintrag("compare", PRESET_ID, A_PRESET)])

    out = _hole(USER_A)
    t, c = out["trips"][TRIP_ID], out["compare"][PRESET_ID]
    assert t["at"] is None and t["reason"] == "ended", out
    assert c["at"] is None and c["reason"] == "paused", out
    assert _gleicher_zeitpunkt(t["last_briefing"], A_TRIP_NEU), out
    assert _gleicher_zeitpunkt(c["last_briefing"], A_PRESET), out
