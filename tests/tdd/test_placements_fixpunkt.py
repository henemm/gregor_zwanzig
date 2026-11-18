"""Erstes Speichern der Tabelle "Was steht wo" tauscht nichts aus (#3122 B2b).

SPEC: docs/specs/modules/feat_3122_was_steht_wo.md Teil A Nr. 1, 3, 8, 9;
AC-11, AC-16.

Nutzersicht: Ein Abo ohne gespeicherte Tabelle (``stored: false``) zeigt das
Ergebnis der Umrechnung. Speichert die Oberflaeche genau dieses ``placements``
unveraendert (Go ``store.SaveBriefingPlacements``: nur
``display_config.placements`` wird gesetzt, fehlt ``display_config``, entsteht
es), muss der naechste Abruf dieselben Zeilen in derselben Folge mit denselben
Zustaenden und Formen zeigen (Fixpunkt) -- und das Briefing dieselben Metriken
tragen wie vorher (View-Model des Versandwegs gleich), ausser in den Faellen,
die ``placements_from_legacy`` als bewusste Aenderung meldet.

Kern-Schicht: echte Dateien in der isolierten Datenwurzel, echter Loader,
echter Resolver, kein Mock.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

NUTZER = "p3122-fix-a"
WEGPUNKTE = [
    {"id": "W1", "name": "Start", "lat": 47.27, "lon": 11.40, "elevation_m": 600},
    {"id": "W2", "name": "Ziel", "lat": 47.29, "lon": 11.42, "elevation_m": 900}]
TRIP_GEWAEHLT = ["wind", "gust", "precipitation", "thunder", "temperature", "cloud_total",
                 "visibility", "sunshine", "uv_index", "humidity"]
ORTE_GEWAEHLT = [
    {"metric_id": "temperature", "aggregation": "max"},
    {"metric_id": "temperature", "aggregation": "min"},
    {"metric_id": "wind", "aggregation": "max"}, {"metric_id": "gust", "aggregation": "max"},
    {"metric_id": "precipitation", "aggregation": "sum"},
    {"metric_id": "sunshine", "aggregation": "sum"},
    {"metric_id": "cloud_total", "aggregation": "avg"},
    {"metric_id": "uv_index", "aggregation": "max"},
]


def _metriken(ids, enabled=True) -> list[dict]:
    return [{"metric_id": m, "enabled": enabled, "bucket": "primary", "order": i}
            for i, m in enumerate(ids)]


#: Trip-Faelle: (Name, display_config oder None = Schluessel fehlt)
TRIP_FAELLE = {
    "nie_eingestellt_ohne_display_config": None,
    "nie_eingestellt_ohne_metrics": {"show_night_block": True},
    "bewusst_leer": {"metrics": _metriken(TRIP_GEWAEHLT, enabled=False)},
    "gewaehlt": {"metrics": _metriken(TRIP_GEWAEHLT)},
    "gewaehlt_mit_channel_layouts": {
        "metrics": _metriken(TRIP_GEWAEHLT),
        "channel_layouts": {
            "sms": [{"metric_id": m} for m in ("thunder", "gust", "wind", "precipitation")],
            "telegram": [{"metric_id": m} for m in ("wind", "temperature", "sunshine")],
            "email": [{"metric_id": m} for m in TRIP_GEWAEHLT[::-1]]}},
}

#: Orte-Faelle: display_config (None = Schluessel fehlt)
ORTE_FAELLE = {
    "nie_eingestellt_ohne_display_config": None,
    "nie_eingestellt_ohne_active_metrics": {"telegram_style": "rich"},
    "bewusst_leer": {"active_metrics": []},
    "gewaehlt": {"active_metrics": ORTE_GEWAEHLT},
    "gewaehlt_mit_channel_layouts": {
        "active_metrics": ORTE_GEWAEHLT,
        "channel_layouts": {
            "sms": [{"metric_id": m} for m in ("gust", "wind", "temperature")],
            "telegram": [{"metric_id": m} for m in ("sunshine", "wind")]}},
}


def _pfad(kennung: str) -> Path:
    from app.loader import get_data_root

    return Path(get_data_root()) / "users" / NUTZER / "briefings" / f"{kennung}.json"


def _schreibe(pfad: Path, daten: dict) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(daten), encoding="utf-8")


#: Trip-Abos ohne ``display_config`` mit anderer Herkunft der Grundauswahl
#: "nie eingestellt" (Loader: Profil-Default bzw. altes ``weather_config``).
TRIP_OHNE_DC_EXTRA = {
    "profil_wintersport": {"aggregation": {"profile": "wintersport"}},
    "altes_weather_config": {"weather_config": {
        "trip_id": "x", "enabled_metrics": ["temp_max_c", "wind_max_kmh", "precip_sum_mm"],
        "updated_at": "2026-01-01T00:00:00"}},
}


def _trip(kennung: str, dc, extra=None) -> None:
    daten = {"id": kennung, "name": "Trip " + kennung, "kind": "route",
             "stages": [{"id": "T1", "name": "Etappe 1", "date": "2026-07-14",
                         "waypoints": WEGPUNKTE}], **(extra or {})}
    if dc is not None:
        daten["display_config"] = dc
    _schreibe(_pfad(kennung), daten)


def _orte(kennung: str, dc, anzahl: int = 3) -> None:
    from app.loader import get_data_root

    ids = []
    for i in range(anzahl):
        ort = f"{kennung}-ort{i}"
        ids.append(ort)
        _schreibe(Path(get_data_root()) / "users" / NUTZER / "locations" / f"{ort}.json", {
            "id": ort, "name": ("Innsbruck", "Lienz", "Kufstein")[i],
            "lat": 47.27 - 0.2 * i, "lon": 11.39 + 0.3 * i, "elevation_m": 600 + 100 * i})
    daten = {"id": kennung, "name": "Orte " + kennung, "kind": "vergleich", "location_ids": ids,
             "schedule": "daily", "profil": "ALLGEMEIN", "forecast_hours": 48, "empfaenger": [],
             "created_at": "2026-09-01T00:00:00Z", "morning_enabled": True,
             "morning_time": "07:00:00", "evening_enabled": True, "evening_time": "18:00:00",
             "corridors": [], "hourly_enabled": True}
    if dc is not None:
        daten["display_config"] = dc
    _schreibe(_pfad(kennung), daten)


def go_put(kennung: str, placements) -> None:
    """Was ``store.SaveBriefingPlacements`` (Go) schreibt: Read-Modify-Write,
    nur ``display_config.placements`` ersetzt; fehlt/null ``display_config``,
    entsteht ein Objekt nur mit ``placements``."""
    doc = json.loads(_pfad(kennung).read_text(encoding="utf-8"))
    dc = doc.get("display_config")
    dc = dict(dc) if isinstance(dc, dict) else {}
    dc["placements"] = placements
    doc["display_config"] = dc
    _schreibe(_pfad(kennung), doc)


@pytest.fixture
def client():
    from api.routers import placements

    app = FastAPI()
    app.include_router(placements.router)
    return TestClient(app)


def _get(client, kennung: str, kind: str) -> dict:
    antwort = client.get(f"/api/briefings/{kennung}/placements",
                         params={"kind": kind, "user_id": NUTZER})
    assert antwort.status_code == 200, antwort.text
    return antwort.json()


def _tabelle(antwort: dict) -> list:
    """Zeilen mit Zustand, Form und Grund je Stelle (ohne Beispielwerte)."""
    return [(z["metric_id"], {s: (c["state"], c["format"], c["reason"])
                              for s, c in z["cells"].items()}) for z in antwort["rows"]]


# ---------------------------------------------------------------------------
# View-Model des Versandwegs
# ---------------------------------------------------------------------------

def _versand_listen(kennung: str, surface: str, outlook_reports: list) -> dict:
    """Je (Briefing-Typ, Stelle) die Liste ``[(kennung, format)]`` genau so,
    wie der Versandweg den Resolver ruft (Trip: geladenes Modell je Typ;
    Orte: ``resolve_compare_render_options`` ruft ohne Typ). Der Trip-Ausblick
    steht im bisherigen Pfad nur in den Briefings aus ``multi_day_trend_reports``
    (``report_config_resolver``) -- dieselbe Lesart wie ``_output_changes``."""
    from services.channel_list_resolver import resolve_channel_lists, vm_lists

    dc, _abo = _dc_und_abo(kennung, surface)
    if surface == "trip":
        out = {(rt, st): _form_gezeigt("trip", st, liste) for rt in ("morning", "evening")
               for st, liste in vm_lists(resolve_channel_lists(dc, "trip", rt), "trip").items()}
        for rt in ("morning", "evening"):
            if rt not in outlook_reports:
                out[(rt, "outlook")] = []
        return out
    return {(None, st): _form_gezeigt("compare", st, liste)
            for st, liste in vm_lists(resolve_channel_lists(dc, "compare"), "compare").items()}


def _form_gezeigt(surface: str, stelle: str, liste: list) -> list:
    """``None`` (Flaechen-Standard) und die ausdrueckliche Form, die er
    bedeutet, zeigen dasselbe: verglichen wird die gezeigte Form
    (``heutige_form``, dieselbe Regel wie die Umrechnung)."""
    from app.metric_catalog import zwei_formen_stellen
    from services.channel_list_resolver import katalog_id
    from services.placements import heutige_form

    out = []
    for mid, fmt in liste:
        kid = katalog_id(surface, mid)
        zwei = stelle in zwei_formen_stellen(kid)
        out.append((mid, heutige_form(surface, stelle, kid, fmt) if zwei else None))
    return out


def _dc_und_abo(kennung: str, surface: str):
    from app.loader import compare_preset_to_dict, get_data_root, load_compare_presets, load_trip

    if surface == "trip":
        trip = load_trip(kennung, data_dir=get_data_root(), user_id=NUTZER)
        return trip.display_config, trip
    preset = compare_preset_to_dict(next(
        p for p in load_compare_presets(user_id=NUTZER, data_root=get_data_root())
        if p.id == kennung))
    return preset.get("display_config") or {}, preset


def _gemeldete_stellen(kennung: str, surface: str) -> set:
    """(Briefing-Typ, Stelle) mit bewusster Aenderung laut Umrechnung."""
    from services.placements import placements_from_legacy

    dc, abo = _dc_und_abo(kennung, surface)
    if surface == "trip":
        changes = placements_from_legacy(dc, "trip", report_config=abo.report_config,
                                         enabled_reports=["morning", "evening"]).changes
        return {(c.report_type, c.stelle) for c in changes} | {
            (rt, c.stelle) for c in changes if c.report_type is None
            for rt in ("morning", "evening")}
    changes = placements_from_legacy(dc, "compare", enabled_reports=["morning", "evening"],
                                     outlook_enabled=abo.get("outlook_enabled")).changes
    return {(None, c.stelle) for c in changes}


def _fixpunkt(client, kennung: str, kind: str, surface: str) -> None:
    vorher = _get(client, kennung, kind)
    assert vorher["stored"] is False
    versand_vorher = _versand_listen(kennung, surface, vorher["outlook_reports"])
    gemeldet = _gemeldete_stellen(kennung, surface)

    go_put(kennung, vorher["placements"])
    nachher = _get(client, kennung, kind)

    assert nachher["stored"] is True
    assert _tabelle(nachher) == _tabelle(vorher), "erstes Speichern hat die Tabelle veraendert"
    assert nachher["outlook_reports"] == vorher["outlook_reports"]
    versand_nachher = _versand_listen(kennung, surface, nachher["outlook_reports"])
    for schluessel, liste in versand_vorher.items():
        if schluessel in gemeldet:
            continue
        assert versand_nachher[schluessel] == liste, (
            f"{schluessel}: Briefing nach dem ersten Speichern anders, ohne gemeldete Aenderung")


@pytest.mark.parametrize("fall", list(TRIP_FAELLE))
def test_trip_erstes_speichern_ist_fixpunkt(client, fall):
    kennung = f"t-fix-{fall}"
    _trip(kennung, TRIP_FAELLE[fall])
    _fixpunkt(client, kennung, "route", "trip")


@pytest.mark.parametrize("fall", list(TRIP_OHNE_DC_EXTRA))
def test_trip_ohne_display_config_anderer_herkunft_ist_fixpunkt(client, fall):
    kennung = f"t-fix-{fall}"
    _trip(kennung, None, extra=TRIP_OHNE_DC_EXTRA[fall])
    _fixpunkt(client, kennung, "route", "trip")


@pytest.mark.parametrize("fall", list(ORTE_FAELLE))
def test_orte_erstes_speichern_ist_fixpunkt(client, fall):
    kennung = f"o-fix-{fall}"
    _orte(kennung, ORTE_FAELLE[fall])
    _fixpunkt(client, kennung, "vergleich", "compare")


def test_trip_ohne_display_config_behaelt_die_grundauswahl_im_versand(client):
    """Kern der Beobachtung: ein Trip ohne ``display_config`` bekommt beim
    Speichern der Tabelle ein ``display_config`` nur mit ``placements``; die
    Grundauswahl "nie eingestellt" darf dadurch nicht wechseln."""
    from services.channel_list_resolver import grundauswahl

    _trip("t-fix-grund", None)
    vorher = grundauswahl(_dc_und_abo("t-fix-grund", "trip")[0], "trip", "evening").ids
    go_put("t-fix-grund", _get(client, "t-fix-grund", "route")["placements"])
    nachher = grundauswahl(_dc_und_abo("t-fix-grund", "trip")[0], "trip", "evening").ids
    assert nachher == vorher


@pytest.mark.parametrize("kind,fall", [
    ("route", "nie_eingestellt_ohne_display_config"), ("route", "gewaehlt"),
    ("route", "gewaehlt_mit_channel_layouts"),
    ("vergleich", "nie_eingestellt_ohne_display_config"), ("vergleich", "gewaehlt"),
    ("vergleich", "gewaehlt_mit_channel_layouts"),
])
def test_umgekehrte_folge_speichern_zeigt_dieselbe_menge_umgekehrt(client, kind, fall):
    kennung = f"{kind[0]}-rev-{fall}"
    if kind == "route":
        _trip(kennung, TRIP_FAELLE[fall])
    else:
        _orte(kennung, ORTE_FAELLE[fall])
    vorher = _get(client, kennung, kind)
    placements = dict(vorher["placements"])
    placements["rows"] = list(reversed(placements["rows"]))
    go_put(kennung, placements)
    nachher = _get(client, kennung, kind)
    erwartet = [z["metric_id"] for z in reversed(vorher["rows"])]
    assert [z["metric_id"] for z in nachher["rows"]] == erwartet
    assert dict(_tabelle(nachher)) == dict(_tabelle(vorher))


# ---------------------------------------------------------------------------
# "+" einer Metrik bei ``stored: false``: Tabelle = Versand
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kind,fall", [
    ("route", "gewaehlt"), ("route", "gewaehlt_mit_channel_layouts"),
    ("vergleich", "gewaehlt"), ("vergleich", "gewaehlt_mit_channel_layouts"),
])
def test_neue_metrik_ohne_tabelle_zeigt_die_haken_des_versands(client, kind, fall):
    """Kommt eine Metrik in die Grundauswahl, ohne dass die Tabelle gespeichert
    ist, zeigt die Tabelle an jeder Kanal-Stelle genau dann einen Haken, wenn
    der Versand die Metrik dort fuehrt. (Trip mit Kanal-Listen des Altbestands:
    dort steht sie NICHT -- die Tabelle sagt das, statt "ueberall an".)"""
    from services.channel_list_resolver import katalog_id

    kennung = f"{kind[0]}-plus-{fall}"
    surface = "trip" if kind == "route" else "compare"
    if kind == "route":
        dc = json.loads(json.dumps(TRIP_FAELLE[fall]))
        dc["metrics"] += _metriken(["pressure"])
        _trip(kennung, dc)
    else:
        dc = json.loads(json.dumps(ORTE_FAELLE[fall]))
        dc["active_metrics"] = dc["active_metrics"] + [
            {"metric_id": "pressure", "aggregation": "avg"}]
        _orte(kennung, dc)
    antwort = _get(client, kennung, kind)
    assert antwort["stored"] is False
    zellen = next(z for z in antwort["rows"] if z["metric_id"] == "pressure")["cells"]
    rt = "evening" if surface == "trip" else None
    versand = _versand_listen(kennung, surface, antwort["outlook_reports"])
    for stelle in ("email", "telegram", "sms"):
        im_versand = any(katalog_id(surface, m) == "pressure" for m, _f in versand[(rt, stelle)])
        assert (zellen[stelle]["state"] == "on") == im_versand, (stelle, zellen[stelle])
