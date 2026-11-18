"""Lese-Endpoint der Tabelle "Was steht wo" im Python-Core (#3122 B2).

SPEC: docs/specs/modules/feat_3122_was_steht_wo.md, Teil A Nr. 9, Teil B
Nr. 11/12; AC-16, AC-17, Tabellen-Teil von AC-7, AC-9, AC-18.

``GET /api/briefings/{id}/placements?kind=route|vergleich&user_id=...`` liest
das Abo des Nutzers aus der (isolierten) Datenwurzel und liefert Spalten,
Zeilen mit Zustand/Form/Beispielwert je Stelle, Marken, SMS-Beispiel,
``outlook_reports``, Block-Schalter und die Kuerzel-Legende.

Kern-Schicht: echte Dateien, echte Renderer, fester Beispiel-Datensatz, kein
Netz, kein Mock. Das Soll fuer "fehlt in der SMS" bildet der Test aus dem
Versandweg (TripReportFormatter bzw. compare_briefing_aufbau) und den
Kuerzeln des Katalogs, nicht aus der Antwort selbst.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

NUTZER_A, NUTZER_B = "p3122-b2-a", "p3122-b2-b"

#: Mehr Metriken, als in 160 Zeichen passen; ohne Temperatur, deren D/L-Token
#: zu einem Bereichs-Token verschmelzen (das Orakel unten bleibt so einfach).
TRIP_GRUND = [
    "wind", "gust", "rain_probability", "precipitation", "thunder", "cloud_total",
    "visibility", "freezing_level", "uv_index", "humidity", "dewpoint", "pressure",
    "cloud_low", "cloud_mid", "cloud_high", "precip_type", "snowfall_limit", "sunshine",
]
ORTE_GRUND = [
    {"metric_id": "temperature", "aggregation": "max"},
    {"metric_id": "temperature", "aggregation": "min"},
    {"metric_id": "wind", "aggregation": "max"},
    {"metric_id": "gust", "aggregation": "max"},
    {"metric_id": "precipitation", "aggregation": "sum"},
    {"metric_id": "rain_probability", "aggregation": "max"},
    {"metric_id": "sunshine", "aggregation": "sum"},
    {"metric_id": "cloud_total", "aggregation": "avg"},
    {"metric_id": "humidity", "aggregation": "avg"},
    {"metric_id": "visibility", "aggregation": "min"},
    {"metric_id": "uv_index", "aggregation": "max"},
    {"metric_id": "dewpoint", "aggregation": "avg"},
    {"metric_id": "pressure", "aggregation": "avg"},
    {"metric_id": "freezing_level", "aggregation": "min"},
    {"metric_id": "cloud_low", "aggregation": "avg"},
    {"metric_id": "cloud_mid", "aggregation": "avg"},
    {"metric_id": "cloud_high", "aggregation": "avg"},
    {"metric_id": "snowfall_limit", "aggregation": "min"},
]
ORTSNAMEN = ("Innsbruck", "Lienz", "Kufstein")


# ---------------------------------------------------------------------------
# Daten
# ---------------------------------------------------------------------------

def _root() -> Path:
    from app.loader import get_data_root

    return Path(get_data_root())


def _schreibe(user: str, ordner: str, kennung: str, daten: dict) -> Path:
    pfad = _root() / "users" / user / ordner / f"{kennung}.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(daten), encoding="utf-8")
    return pfad


def _trip(user: str, kennung: str, *, placements=None, grund=TRIP_GRUND, rc=None,
          warnungen=True) -> Path:
    dc = {"trip_id": kennung, "metrics": [
        {"metric_id": m, "enabled": True, "bucket": "primary", "order": i}
        for i, m in enumerate(grund)]}
    if placements is not None:
        dc["placements"] = placements
    daten = {
        "id": kennung, "name": "Trip " + kennung, "kind": "route",
        "stages": [{"id": "T1", "name": "Etappe 1", "date": "2026-07-14", "waypoints": [
            {"id": "W1", "name": "Start", "lat": 47.27, "lon": 11.40, "elevation_m": 600},
            {"id": "W2", "name": "Ziel", "lat": 47.29, "lon": 11.42, "elevation_m": 900}]}],
        "official_alerts_enabled": warnungen, "display_config": dc,
    }
    if rc is not None:
        daten["report_config"] = rc
    if not warnungen:
        daten["official_warnings"] = {"enabled": False}
    return _schreibe(user, "briefings", kennung, daten)


def _orte(user: str, kennung: str, *, anzahl=3, placements=None, grund=ORTE_GRUND,
          warnungen=True, morgen=True, abend=False, extra=None) -> Path:
    ids = []
    for i, name in enumerate(ORTSNAMEN[:anzahl]):
        ort_id = f"{kennung}-ort{i}"
        ids.append(ort_id)
        _schreibe(user, "locations", ort_id, {
            "id": ort_id, "name": name, "lat": 47.27 - 0.2 * i, "lon": 11.39 + 0.3 * i,
            "elevation_m": 600 + 100 * i})
    dc = {"active_metrics": grund}
    if placements is not None:
        dc["placements"] = placements
    daten = {
        "id": kennung, "name": "Orte " + kennung, "kind": "vergleich", "location_ids": ids,
        "schedule": "daily", "profil": "ALLGEMEIN", "forecast_hours": 48, "empfaenger": [],
        "created_at": "2026-09-01T00:00:00Z", "morning_enabled": morgen,
        "morning_time": "07:00:00", "evening_enabled": abend, "evening_time": "18:00:00",
        "corridors": [], "hourly_enabled": True, "official_alerts_enabled": warnungen,
        "display_config": dc, **(extra or {}),
    }
    if not warnungen:
        daten["official_warnings"] = {"enabled": False}
    return _schreibe(user, "briefings", kennung, daten)


@pytest.fixture
def client():
    from api.routers import placements

    app = FastAPI()
    app.include_router(placements.router)
    return TestClient(app)


def _get(client, kennung, kind, user=NUTZER_A):
    return client.get(f"/api/briefings/{kennung}/placements",
                      params={"kind": kind, "user_id": user})


def _ok(client, kennung, kind, user=NUTZER_A) -> dict:
    antwort = _get(client, kennung, kind, user)
    assert antwort.status_code == 200, antwort.text
    return antwort.json()


def _zeile(antwort, metric_id) -> dict:
    return next(z for z in antwort["rows"] if z["metric_id"] == metric_id)


# ---------------------------------------------------------------------------
# Versandweg-Orakel (aus demselben Beispiel-Datensatz)
# ---------------------------------------------------------------------------

def _trip_versand_sms(user: str, kennung: str) -> str:
    """SMS ueber den Renderer des Versands mit dem festen Beispiel-Datensatz."""
    from app.ampel import resolve_ampel
    from app.loader import get_data_root, load_trip
    from output.renderers.email.outlook import build_outlook_row
    from output.renderers.trip_report import TripReportFormatter
    from services import placements_beispiel as pb
    from services.weather_metrics import summarize_points

    trip = load_trip(kennung, data_dir=get_data_root(), user_id=user)
    dc = trip.display_config
    trend = [build_outlook_row(summarize_points(p), p, wd, pb.ZONE, trip_display_config=dc,
                               report_type="evening", context="route", ampel=resolve_ampel(trip))
             for wd, p in pb.ausblick_tage()]
    return TripReportFormatter().format_email(
        pb.trip_segmente(), trip.name, "evening", display_config=dc, multi_day_trend=trend,
        report_config=trip.report_config, trip=trip, tz=pb.ZONE,
        stage_name=trip.stages[0].name, lang="de",
    ).sms_text


def _orte_versand_sms(user: str, kennung: str) -> str:
    from app.ampel import profile_for_template, template_id_for
    from app.loader import compare_preset_to_dict, get_data_root, load_all_locations, load_compare_presets
    from services import compare_briefing_aufbau as aufbau
    from services import placements_beispiel as pb
    from services.report_config_resolver import resolve_compare_render_options

    preset = compare_preset_to_dict(next(
        p for p in load_compare_presets(user_id=user, data_root=get_data_root()) if p.id == kennung))
    orte = aufbau.order_locations_by_ids(load_all_locations(user), preset["location_ids"])
    kontext = {"preset": preset, "result": pb.orte_ergebnis(orte),
               "profile": profile_for_template(template_id_for(preset)),
               "opts": resolve_compare_render_options(preset), "name": preset["name"],
               "target_date": pb.TAG}
    return aufbau.compare_kanaltexte_rendern(kontext, lang="de")[0]


def _trip_symbole(metric_id: str) -> tuple[str, ...]:
    from output.renderers.sms_trip import SMS_MULTI_SYMBOLS_BY_METRIC, SMS_SYMBOL_BY_METRIC

    multi = SMS_MULTI_SYMBOLS_BY_METRIC.get(metric_id)
    if multi:
        return multi
    return (SMS_SYMBOL_BY_METRIC[metric_id],) if metric_id in SMS_SYMBOL_BY_METRIC else ()


def _trip_fehlt_in_sms(sms: str, metric_id: str) -> bool:
    from output.renderers.sms_trip import SMS_MULTI_SYMBOLS_BY_METRIC, SMS_SYMBOL_BY_METRIC

    alle = set(SMS_SYMBOL_BY_METRIC.values()) | {
        s for syms in SMS_MULTI_SYMBOLS_BY_METRIC.values() for s in syms}
    token = sms.split(": ", 1)[1].split(" ")

    def _symbol(tok: str) -> str | None:
        treffer = [s for s in alle if tok.startswith(s)]
        return max(treffer, key=len) if treffer else None

    vorhanden = {_symbol(t) for t in token}
    return not any(s in vorhanden for s in _trip_symbole(metric_id))


def _orte_fehlt_in_sms(sms: str, metric_id: str) -> bool:
    """Ein Ort-Teil der Orte-SMS: ``Name K1 Wert K2 Wert ...``; die Metrik
    fehlt, wenn keines ihrer Kuerzel im ersten Ort-Teil steht."""
    from app.metric_catalog import kurzform_kuerzel

    teil = sms.split(": ", 1)[1].split("; ")[0]
    kuerzel = {"temperature": ("D", "L")}.get(metric_id, (kurzform_kuerzel(metric_id),))
    return not any(re.search(rf"(^| ){re.escape(k)} ", teil) for k in kuerzel if k)


def _sms_an(antwort) -> list[str]:
    return [z["metric_id"] for z in antwort["rows"] if z["cells"]["sms"]["state"] == "on"]


# ---------------------------------------------------------------------------
# AC-16: Zeilen, Zustaende, Formen, Beispielwerte, "nur Tageswert"
# ---------------------------------------------------------------------------

TRIP_PLACEMENTS = {
    "version": 1,
    "rows": [
        {"metric_id": "gust", "places": {"telegram": False}, "formats": {"email": "raw"}},
        {"metric_id": "wind", "formats": {"email": "simplified", "telegram": "raw"}},
        {"metric_id": "precipitation", "places": {"email": False}},
        {"metric_id": "thunder", "places": {"sms": False}},
    ],
}


def test_ac16_trip_jede_metrik_in_einer_folge_mit_zustand_form_und_beispiel(client):
    from app.metric_catalog import get_metric

    _trip(NUTZER_A, "t-ac16", placements=TRIP_PLACEMENTS)
    antwort = _ok(client, "t-ac16", "route")

    ids = [z["metric_id"] for z in antwort["rows"]]
    assert ids[:4] == ["gust", "wind", "precipitation", "thunder"]
    assert sorted(ids) == sorted(TRIP_GRUND), "jede Metrik der Grundauswahl genau einmal"
    assert [z["position"] for z in antwort["rows"]] == list(range(len(ids)))
    assert [c["stelle"] for c in antwort["columns"]] == ["email", "telegram", "sms", "outlook"]
    assert antwort["stored"] is True
    assert antwort["placements"]["rows"][0] == TRIP_PLACEMENTS["rows"][0]

    assert _zeile(antwort, "wind")["name"] == get_metric("wind").label("de")
    assert _zeile(antwort, "gust")["cells"]["telegram"]["state"] == "off"
    assert _zeile(antwort, "gust")["cells"]["email"]["format"] == "raw"
    assert _zeile(antwort, "wind")["cells"]["email"]["format"] == "simplified"
    assert _zeile(antwort, "wind")["cells"]["telegram"]["format"] == "raw"
    assert _zeile(antwort, "precipitation")["cells"]["outlook"]["state"] == "not_in_email"
    assert _zeile(antwort, "thunder")["cells"]["sms"]["state"] == "off"
    assert _zeile(antwort, "visibility")["cells"]["email"]["format"] is None

    for zeile in antwort["rows"]:
        for stelle, zelle in zeile["cells"].items():
            if zelle["state"] != "on" or zelle["mark"] == "passt_nicht_mehr":
                continue
            if stelle == "outlook" and zeile["metric_id"] in ():
                continue  # Ausblick ohne Tageswert-Spalte im heutigen Renderer
            assert zelle["example"] or zelle["ampel"], f"{zeile['metric_id']}/{stelle}: Beispielwert fehlt"


def test_ac16_trip_beispielwerte_aus_dem_renderer(client):
    """Die Beispielwerte stammen aus der gerenderten Ausgabe: der SMS-Wert ist
    ein Token der SMS, der Telegram-Wert eine Zeile der Kurzuebersicht."""
    _trip(NUTZER_A, "t-ac16b", placements=TRIP_PLACEMENTS)
    antwort = _ok(client, "t-ac16b", "route")
    sms = antwort["sms_example"]["text"]
    wind = _zeile(antwort, "wind")["cells"]
    assert wind["sms"]["example"].startswith("W") and wind["sms"]["example"] in sms.split(" ")
    assert wind["telegram"]["example"].startswith("W ")
    # Zahl ohne Ampel in der Stundentabelle (Temperatur hat nur eine Form)
    temp = _zeile(antwort, "visibility")["cells"]["email"]
    assert re.fullmatch(r"\d+(\.\d)?", temp["example"]) and temp["ampel"] is None
    # Einfach in der HTML-Mail: Ampelpunkt mit Stufe
    assert wind["email"]["ampel"] in ("green", "yellow", "orange", "red")
    # Ausblick: Zelle der ersten Ausblick-Zeile
    assert _zeile(antwort, "gust")["cells"]["outlook"]["example"].endswith("km/h")


def test_ac16_trip_nur_tageswert_ab_der_achten_telegram_metrik(client):
    _trip(NUTZER_A, "t-tg", placements={"version": 1, "rows": []})
    antwort = _ok(client, "t-tg", "route")
    tg = [z for z in antwort["rows"] if z["cells"]["telegram"]["state"] == "on"]
    assert len(tg) > 7
    marken = [z["cells"]["telegram"]["mark"] for z in tg]
    assert marken[:7] == [None] * 7
    assert set(marken[7:]) == {"nur_tageswert"}
    for z in antwort["rows"]:
        assert z["cells"]["email"]["mark"] is None and z["cells"]["outlook"]["mark"] is None


@pytest.mark.parametrize("anzahl", [3, 1])
def test_ac16_orte_spalten_zeilen_formen_und_beispiele(client, anzahl):
    from app.metric_catalog import get_metric

    placements = {"version": 1, "rows": [
        {"metric_id": "wind", "places": {"hourly": False}, "formats": {"email": "simplified"}},
        {"metric_id": "temperature", "places": {"telegram": False}},
        {"metric_id": "sunshine", "places": {"email": False}},
    ]}
    _orte(NUTZER_A, f"o-ac16-{anzahl}", anzahl=anzahl, placements=placements)
    antwort = _ok(client, f"o-ac16-{anzahl}", "vergleich")

    assert [c["stelle"] for c in antwort["columns"]] == ["email", "telegram", "sms", "hourly", "outlook"]
    assert antwort["location_count"] == anzahl
    ids = [z["metric_id"] for z in antwort["rows"]]
    assert ids[:3] == ["wind", "temperature", "sunshine"]
    assert sorted(ids) == sorted({e["metric_id"] for e in ORTE_GRUND})
    assert _zeile(antwort, "temperature")["name"] == get_metric("temperature").label("de")
    wind = _zeile(antwort, "wind")["cells"]
    assert (wind["hourly"]["state"], wind["email"]["format"]) == ("off", "simplified")
    assert _zeile(antwort, "temperature")["cells"]["telegram"]["state"] == "off"
    sonne = _zeile(antwort, "sunshine")["cells"]
    assert (sonne["hourly"]["state"], sonne["hourly"]["reason"]) == ("locked", "kein_stundenwert")
    assert sonne["outlook"]["state"] == "not_in_email"
    for zeile in antwort["rows"]:
        assert zeile["cells"]["telegram"]["mark"] is None, "nur_tageswert gibt es nur beim Trip"
        for stelle, zelle in zeile["cells"].items():
            if zelle["state"] == "on" and zelle["mark"] != "passt_nicht_mehr":
                assert zelle["example"] or zelle["ampel"], f"{zeile['metric_id']}/{stelle}: Beispielwert fehlt"


# ---------------------------------------------------------------------------
# AC-17: SMS-Beispiel = Versand-SMS, Zeichenzahl, "passt nicht mehr"
# ---------------------------------------------------------------------------

def test_ac17_trip_sms_beispiel_gleich_versand_und_marken(client):
    _trip(NUTZER_A, "t-sms", placements={"version": 1, "rows": []})
    antwort = _ok(client, "t-sms", "route")
    versand = _trip_versand_sms(NUTZER_A, "t-sms")

    assert antwort["sms_example"]["text"] == versand
    assert antwort["sms_example"]["length"] == len(versand)
    assert antwort["sms_example"]["max_length"] == 160
    fehlend = {m for m in _sms_an(antwort) if _trip_fehlt_in_sms(versand, m)}
    assert fehlend, "Datensatz muss die SMS ueberlaufen lassen"
    markiert = {z["metric_id"] for z in antwort["rows"]
                if z["cells"]["sms"]["mark"] == "passt_nicht_mehr"}
    assert markiert == fehlend


@pytest.mark.parametrize("anzahl", [3, 1])
def test_ac17_orte_sms_beispiel_gleich_versand_und_marken(client, anzahl):
    kennung = f"o-sms-{anzahl}"
    _orte(NUTZER_A, kennung, anzahl=anzahl, placements={"version": 1, "rows": []})
    antwort = _ok(client, kennung, "vergleich")
    versand = _orte_versand_sms(NUTZER_A, kennung)

    assert antwort["sms_example"]["text"] == versand
    assert antwort["sms_example"]["length"] == len(versand)
    if anzahl == 1:
        teil = versand.split(": ", 1)[1]
        assert teil.startswith(ORTSNAMEN[0])
    fehlend = {m for m in _sms_an(antwort) if _orte_fehlt_in_sms(versand, m)}
    assert fehlend, "Datensatz muss die SMS ueberlaufen lassen"
    markiert = {z["metric_id"] for z in antwort["rows"]
                if z["cells"]["sms"]["mark"] == "passt_nicht_mehr"}
    assert markiert == fehlend


def test_ac17_hochziehen_aendert_marken(client):
    """Eine hinten stehende Metrik nach vorn gezogen passt danach in die SMS."""
    _trip(NUTZER_A, "t-zug", placements={"version": 1, "rows": []})
    vorher = _ok(client, "t-zug", "route")
    letzte = [z["metric_id"] for z in vorher["rows"]
              if z["cells"]["sms"]["mark"] == "passt_nicht_mehr"][-1]
    _trip(NUTZER_A, "t-zug", placements={"version": 1, "rows": [{"metric_id": letzte}]})
    nachher = _ok(client, "t-zug", "route")
    assert _zeile(nachher, letzte)["cells"]["sms"]["mark"] is None
    assert _zeile(nachher, letzte)["cells"]["sms"]["example"] in nachher["sms_example"]["text"]


# ---------------------------------------------------------------------------
# AC-7 (Tabellen-Teil): gesperrte Stellen mit Grund
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_ac7_jede_gesperrte_kombination_als_locked_mit_grund(client, kind):
    from app.metric_catalog import stellen_sperre

    if kind == "route":
        _trip(NUTZER_A, "t-lock", grund=TRIP_GRUND + ["temperature", "temperature_night"],
              placements={"version": 1, "rows": [
                  {"metric_id": "temperature_night", "places": {"email": True, "outlook": True}}]})
        antwort, surface = _ok(client, "t-lock", kind), "trip"
    else:
        _orte(NUTZER_A, "o-lock", placements={"version": 1, "rows": [
            {"metric_id": "sunshine", "places": {"hourly": True}}]})
        antwort, surface = _ok(client, "o-lock", kind), "compare"
    gesehen = 0
    for zeile in antwort["rows"]:
        for stelle, zelle in zeile["cells"].items():
            grund = stellen_sperre(zeile["metric_id"], stelle, surface)
            if grund:
                gesehen += 1
                assert (zelle["state"], zelle["reason"]) == ("locked", grund)
                assert zelle["example"] is None
            else:
                assert zelle["state"] != "locked"
    assert gesehen > 0


# ---------------------------------------------------------------------------
# AC-9 (Tabellen-Teil): outlook_reports und Block-Schalter
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("morgen,abend,erwartet", [
    (True, True, ["evening"]), (True, False, ["morning"]),
])
def test_ac9_vorbelegung_ausblick_trip_und_orte(client, morgen, abend, erwartet):
    ohne = {"version": 1, "rows": []}
    _trip(NUTZER_A, "t-ab", placements=ohne,
          rc={"enabled": True, "morning_enabled": morgen, "evening_enabled": abend})
    _orte(NUTZER_A, "o-ab", placements=ohne, morgen=morgen, abend=abend)
    for kennung, kind in (("t-ab", "route"), ("o-ab", "vergleich")):
        antwort = _ok(client, kennung, kind)
        assert antwort["outlook_reports"] == erwartet
        assert antwort["blocks"]["outlook"] == {
            "morning": "morning" in erwartet, "evening": "evening" in erwartet}


def test_bloecke_trip_und_orte_aus_dem_abo(client):
    _trip(NUTZER_A, "t-bl", placements={"version": 1, "rows": []},
          rc={"show_stage_stats": False, "email_format": "compact", "telegram_style": "kurzform"})
    _orte(NUTZER_A, "o-bl", placements={"version": 1, "rows": [], "outlook_reports": []},
          extra={"hourly_enabled": False})
    trip = _ok(client, "t-bl", "route")["blocks"]
    assert (trip["show_stage_stats"], trip["email_format"], trip["telegram_style"]) == (
        False, "compact", "kurzform")
    assert trip["show_yesterday_comparison"] is True and trip["show_night_block"] is True
    orte = _ok(client, "o-bl", "vergleich")
    assert orte["blocks"]["hourly"] is False
    assert orte["blocks"]["outlook"] == {"morning": False, "evening": False}
    spalten = {c["stelle"]: c for c in orte["columns"]}
    assert spalten["hourly"]["block_off"] is True and spalten["outlook"]["block_off"] is True
    assert {c["stelle"]: c for c in _ok(client, "t-bl", "route")["columns"]}[
        "telegram"]["rests"] == "kurzstil"


# ---------------------------------------------------------------------------
# AC-18 (Tabellen-Teil): Amtliche Warnungen als feste Zeile
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("an", [True, False])
def test_ac18_feste_zeile_nur_bei_eingeschalteten_warnungen(client, an):
    _trip(NUTZER_A, "t-w", placements={"version": 1, "rows": []}, warnungen=an)
    _orte(NUTZER_A, "o-w", placements={"version": 1, "rows": []}, warnungen=an)
    for kennung, kind in (("t-w", "route"), ("o-w", "vergleich")):
        feste = _ok(client, kennung, kind)["fixed_rows"]
        if an:
            assert feste == [{"id": "amtliche_warnungen",
                              "position": {"email": "first", "telegram": "first", "sms": "last"}}]
        else:
            assert feste == []


# ---------------------------------------------------------------------------
# Kuerzel-Legende (Spec Nr. 12)
# ---------------------------------------------------------------------------

def test_legende_kuerzel_genau_der_sms_metriken_und_feste_eintraege(client):
    from app.metric_catalog import get_metric

    _trip(NUTZER_A, "t-leg", placements={"version": 1, "rows": [
        {"metric_id": "wind"}, {"metric_id": "gust", "places": {"sms": False}}]})
    antwort = _ok(client, "t-leg", "route")
    legende = antwort["legend"]
    metriken = {e["metric_id"] for e in legende["metrics"]}
    soll = {m for m in _sms_an(antwort) if get_metric(m).kuerzel_bedeutung_de}
    assert metriken == soll and "gust" not in metriken
    wind = next(e for e in legende["metrics"] if e["metric_id"] == "wind")
    assert (wind["kuerzel"], wind["meaning"]) == next(iter(get_metric("wind").kuerzel_bedeutung_de.items()))
    assert [e["token"] for e in legende["fixed"]] == [
        "@14", "!TS:H@14", "L", "M", "H", "WG", "RA", "AV4", "X?"]


# ---------------------------------------------------------------------------
# Altbestand: Ergebnis der Umrechnung
# ---------------------------------------------------------------------------

def test_abo_ohne_tabelle_zeigt_die_umrechnung(client):
    from app.loader import get_data_root, load_trip
    from services.placements import placements_from_legacy

    _trip(NUTZER_A, "t-alt", grund=["wind", "gust", "precipitation"])
    antwort = _ok(client, "t-alt", "route")
    trip = load_trip("t-alt", data_dir=get_data_root(), user_id=NUTZER_A)
    soll = placements_from_legacy(trip.display_config, "trip", report_config=trip.report_config,
                                  enabled_reports=["morning", "evening"]).placements
    assert antwort["stored"] is False
    assert antwort["placements"] == soll
    assert [z["metric_id"] for z in antwort["rows"]] == [r["metric_id"] for r in soll["rows"]]


def test_orte_ohne_tabelle_zeigt_die_umrechnung(client):
    from services.placements import placements_from_legacy

    _orte(NUTZER_A, "o-alt", extra={"outlook_enabled": False})
    antwort = _ok(client, "o-alt", "vergleich")
    soll = placements_from_legacy({"active_metrics": ORTE_GRUND}, "compare",
                                  enabled_reports=["morning"], outlook_enabled=False).placements
    assert antwort["stored"] is False
    assert antwort["placements"] == soll
    assert antwort["outlook_reports"] == []


def test_get_schreibt_nichts(client):
    pfad = _trip(NUTZER_A, "t-ro", placements=TRIP_PLACEMENTS)
    vorher = pfad.read_bytes()
    _ok(client, "t-ro", "route")
    assert pfad.read_bytes() == vorher


# ---------------------------------------------------------------------------
# Mandantentrennung und Robustheit
# ---------------------------------------------------------------------------

def test_fremdes_abo_ist_nicht_lesbar(client):
    _trip(NUTZER_B, "t-fremd", placements=TRIP_PLACEMENTS)
    _orte(NUTZER_B, "o-fremd")
    assert _get(client, "t-fremd", "route", NUTZER_A).status_code == 404
    assert _get(client, "o-fremd", "vergleich", NUTZER_A).status_code == 404
    assert _get(client, "t-fremd", "route", NUTZER_B).status_code == 200


def test_robustheit_kind_kennung_und_user_id(client):
    _trip(NUTZER_A, "t-rob")
    falsch = _get(client, "t-rob", "irgendwas")
    assert falsch.status_code == 400 and falsch.json()["code"] == "kind_required"
    assert _get(client, "t-rob", "vergleich").status_code == 404, "Trip ist kein Orte-Abo"
    assert _get(client, "gibt-es-nicht", "route").status_code == 404
    assert _get(client, "..%2Fx", "route").status_code in (400, 404)
    ohne = client.get("/api/briefings/t-rob/placements", params={"kind": "route"})
    assert ohne.status_code == 422, "user_id ist Pflicht"
