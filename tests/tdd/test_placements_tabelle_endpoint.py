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
          warnungen=True, etappe="Etappe 1") -> Path:
    dc = {"trip_id": kennung, "metrics": [
        {"metric_id": m, "enabled": True, "bucket": "primary", "order": i}
        for i, m in enumerate(grund)]}
    if placements is not None:
        dc["placements"] = placements
    daten = {
        "id": kennung, "name": "Trip " + kennung, "kind": "route",
        "stages": [{"id": "T1", "name": etappe, "date": "2026-07-14", "waypoints": [
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
          warnungen=True, morgen=True, abend=False, extra=None, namen=ORTSNAMEN) -> Path:
    ids = []
    for i, name in enumerate(namen[:anzahl]):
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

def _beispiel_nacht():
    """Nachtreihe des Beispiel-Datensatzes, unabhaengig vom Produktionscode
    gebildet (#3373): Ankunft 16 Uhr bis 06 Uhr Ortszeit am Folgetag, wie
    ``fetch_night_weather`` sie im Versand abdeckt (``Ziel``-Segment endet 16
    Uhr)."""
    from datetime import timedelta

    from app.models import NormalizedTimeseries
    from services import placements_beispiel as pb
    from utils.timezone import local_hour

    abend = [p for p in pb.tagespunkte(pb.TAG) if local_hour(p.ts, pb.ZONE) >= 16]
    morgen = [p for p in pb.tagespunkte(pb.TAG + timedelta(days=1))
              if local_hour(p.ts, pb.ZONE) <= 6]
    return NormalizedTimeseries(meta=pb._meta(), data=abend + morgen)


def _trip_versand_bericht(user: str, kennung: str, report_type: str = "evening", lang: str = "de"):
    """Bericht ueber den Versandaufbau mit dem festen Beispiel-Datensatz
    (#3373): Etappenkopf, Nachtwetter und Folgetag-Gewitter entstehen ueber
    ``trip_briefing_aufbau.trip_anreicherung_bauen`` -- denselben Baustein
    wie im Versand (``numbered_stage_label`` der Etappe am Zieltag,
    Gewitter-Ableitung des Schedulers aus den Trend-Zeilen). Zieltag ist die
    erste Etappe nach Datum. Trend-Zeilen tragen fuer die Ableitung ihr
    Kalenderdatum (wie ``_build_stage_trend``); so entsteht kein Wetterabruf."""
    from datetime import datetime, timedelta, timezone

    from app.ampel import resolve_ampel
    from app.loader import get_data_root, load_trip
    from app.models import OutlookState, TrendResult
    from output.renderers.email.outlook import build_outlook_row
    from output.renderers.trip_report import TripReportFormatter
    from services import placements_beispiel as pb
    from services import trip_briefing_aufbau as aufbau
    from services.report_config_resolver import resolve_report_render_options
    from services.trip_report_scheduler import TripReportSchedulerService
    from services.weather_metrics import summarize_points

    trip = load_trip(kennung, data_dir=get_data_root(), user_id=user)
    dc = trip.display_config
    trend = [build_outlook_row(summarize_points(p), p, wd, pb.ZONE, trip_display_config=dc,
                               report_type=report_type, context="route", ampel=resolve_ampel(trip))
             for wd, p in pb.ausblick_tage()]
    mit_datum = [{**zeile, "date": pb.TAG + timedelta(days=i + 1)} for i, zeile in enumerate(trend)]
    erste = min(trip.stages, key=lambda s: s.date) if trip.stages else None
    anreicherung = aufbau.trip_anreicherung_bauen(
        TripReportSchedulerService(user_id=user), trip, erste.date if erste else pb.TAG,
        pb.trip_segmente(), report_type=report_type,
        now_utc=datetime(pb.TAG.year, pb.TAG.month, pb.TAG.day, 4, 0, tzinfo=timezone.utc),
        trip_tz=pb.ZONE,
        render_options=resolve_report_render_options(trip.report_config, dc, report_type),
        night_weather=_beispiel_nacht(),
        trend_result=TrendResult(rows=mit_datum, state=OutlookState.FOUND),
    )
    return TripReportFormatter().format_email(
        pb.trip_segmente(), trip.name, report_type, display_config=dc, multi_day_trend=trend,
        report_config=trip.report_config, trip=trip, tz=pb.ZONE,
        stage_name=anreicherung.stage_name or trip.name,
        night_weather=anreicherung.night_weather,
        thunder_forecast=anreicherung.thunder_forecast, lang=lang,
    )


def _trip_versand_sms(user: str, kennung: str, report_type: str = "evening") -> str:
    """SMS ueber den Versandaufbau mit dem festen Beispiel-Datensatz."""
    return _trip_versand_bericht(user, kennung, report_type).sms_text


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


def _trip_fehlt_in_sms(sms: str, metric_id: str, rumpf: str | None = None) -> bool:
    """``rumpf``: Text hinter dem (vom Test woertlich bekannten) Kopf; ohne
    Angabe gilt der Kopf ``E<n> `` der Standard-Etappe (#3174: ohne ``:``)."""
    from output.renderers.sms_trip import SMS_MULTI_SYMBOLS_BY_METRIC, SMS_SYMBOL_BY_METRIC

    alle = set(SMS_SYMBOL_BY_METRIC.values()) | {
        s for syms in SMS_MULTI_SYMBOLS_BY_METRIC.values() for s in syms}
    token = (sms.split(" ", 1)[1] if rumpf is None else rumpf).split(" ")

    def _symbol(tok: str) -> str | None:
        treffer = [s for s in alle if tok.startswith(s)]
        return max(treffer, key=len) if treffer else None

    vorhanden = {_symbol(t) for t in token}
    return not any(s in vorhanden for s in _trip_symbole(metric_id))


def _orte_symbole() -> set[str]:
    from output.renderers.sms_trip import SMS_MULTI_SYMBOLS_BY_METRIC, SMS_SYMBOL_BY_METRIC

    return set(SMS_SYMBOL_BY_METRIC.values()) | {
        s for syms in SMS_MULTI_SYMBOLS_BY_METRIC.values() for s in syms}


def _orte_fehlt_in_sms(sms: str, metric_id: str, teil: str | None = None) -> bool:
    """Ein Ort-Teil der Orte-SMS (#3172, Token-Zeile der Trip-SMS:
    ``Name: D15/19 W30@10(43@16) ...``; bei genau einem Ort steht der Name im
    Kopf ``{Ort} TT.MM.:``, #3122 B5); die Metrik fehlt, wenn keines ihrer
    Kuerzel im ersten Ort-Teil steht (laengstes passendes Symbol je Token).
    ``teil``: die Token des ersten Orts, vom Test ueber woertliche Raender
    bestimmt. Temperatur steht als ``D``/``L`` (Bereich ``D15/19``), gefuehlte
    Temperatur als ``FL``/``FD``."""
    from output.renderers.sms_trip import SMS_MULTI_SYMBOLS_BY_METRIC, SMS_SYMBOL_BY_METRIC

    if teil is None:
        # #3172 (PO 2026-11-19): erster Ort ``O1 <Token>``, kein Kopf, keine Namen.
        from tests.helpers.orte_sms import orte_teile, orte_token

        teil = " ".join(orte_token(orte_teile(sms)[0]))
    alle = _orte_symbole()
    vorhanden = set()
    for tok in teil.split(" "):
        treffer = [s for s in alle if tok.startswith(s)]
        if treffer:
            vorhanden.add(max(treffer, key=len))
    kuerzel = {"temperature": ("D", "L"), "wind_chill": ("FL", "FD")}.get(metric_id) or (
        SMS_MULTI_SYMBOLS_BY_METRIC.get(metric_id) or (SMS_SYMBOL_BY_METRIC.get(metric_id),))
    return not any(k in vorhanden for k in kuerzel if k)


def _sms_an(antwort) -> list[str]:
    return [z["metric_id"] for z in antwort["rows"] if z["cells"]["sms"]["state"] == "on"]


# ---------------------------------------------------------------------------
# AC-16: Zeilen, Zustaende, Formen, Beispielwerte, "nur Tageswert"
# ---------------------------------------------------------------------------

#: #3283 B2 (Soll-Bild Fassung 4): abgeleitete SMS-Fenster-Kinder zeigen in der
#: SMS-Spalte kein Beispiel (Ausnahme ``temperature_night`` -> ``N…``).
_SMS_FENSTER_KINDER = ("temperature_day_low", "temperature_day_high",
                       "wind_chill_night", "wind_chill_day_low", "wind_chill_day_high")

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
            if stelle == "sms" and zeile["metric_id"] in _SMS_FENSTER_KINDER:
                continue  # #3283 B2: abgeleitete Fenster-Kinder ohne SMS-Beispiel
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
    # Zahl ohne Ampel in der Stundentabelle, mit Spaltenkuerzel davor (#3283 B3)
    temp = _zeile(antwort, "visibility")["cells"]["email"]
    assert re.fullmatch(r"Visib \d+(\.\d)?", temp["example"]) and temp["ampel"] is None
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


def test_abgewaehlte_telegram_metrik_zaehlt_nicht_zur_spaltengrenze(client):
    """#3020 R1 (G04, AC-12 der Altdatei): die Grenze von sieben Spalten zaehlt
    nur die in Telegram angehakten Metriken. Soll aus der echten Nachricht
    (#3373: ueber den Versandaufbau)."""
    from app.metric_catalog import get_metric

    folge = ["wind", "gust", "precipitation", "rain_probability", "cloud_total",
             "humidity", "uv_index", "thunder", "dewpoint"]
    ab = {"gust", "cloud_total"}

    def anlegen_und_lesen(user, abgewaehlt):
        _trip(user, "t-g04", grund=folge, placements={"version": 1, "rows": [
            {"metric_id": m, **({"places": {"telegram": False}} if m in abgewaehlt else {})}
            for m in folge]})
        antwort = _ok(client, "t-g04", "route", user)
        bericht = _trip_versand_bericht(user, "t-g04")
        blase = next(b for b in bericht.telegram_bubbles if "<pre>" in b)
        kopf = blase.split("<pre>", 1)[1].strip().split("\n", 1)[0].split()
        kuerzel = {get_metric(m).compact_label: m for m in folge}
        markiert = {z["metric_id"] for z in antwort["rows"]
                    if z["cells"]["telegram"]["mark"] == "nur_tageswert"}
        an = [z["metric_id"] for z in antwort["rows"] if z["cells"]["telegram"]["state"] == "on"]
        return an, markiert, [kuerzel[k] for k in kopf[1:]]

    # Nutzer B ohne Abwahl: die Grenze greift ab Platz 8 (sonst bewiese der Fall nichts).
    assert anlegen_und_lesen(NUTZER_B, set()) == (folge, set(folge[7:]), folge[:7])
    # Nutzer A: neun Metriken, zwei der ersten sieben in Telegram abgewaehlt.
    rest = [m for m in folge if m not in ab]
    assert anlegen_und_lesen(NUTZER_A, ab) == (rest, set(), rest)


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
    # Grenze des Versandwegs: trip_report.format_email ruft format_sms(max_length=160)
    # (SMS und Premium-SMS senden denselben report.sms_text).
    assert antwort["sms_example"]["max_length"] == 160
    assert len(versand) <= antwort["sms_example"]["max_length"]
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
    # Grenze des Versandwegs (#3172): 160 wie die Trip-SMS; die Premium-SMS
    # kuerzt ueber 153 Zeichen neu (#3100).
    from output.renderers.comparison import ORTE_SMS_MAX_ZEICHEN

    assert antwort["sms_example"]["max_length"] == ORTE_SMS_MAX_ZEICHEN == 160
    assert len(versand) <= antwort["sms_example"]["max_length"]
    # #3172: kein Kopf, keine Namen -- die SMS beginnt mit O1.
    assert versand.startswith("O1 ") and ORTSNAMEN[0] not in versand, versand
    fehlend = {m for m in _sms_an(antwort) if _orte_fehlt_in_sms(versand, m)}
    # #3172: ein Ort passt ohne Namen und Kopf ganz in 160 Zeichen; ab drei Orten laeuft sie ueber.
    assert fehlend or anzahl == 1, "Datensatz muss die SMS ueberlaufen lassen"
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
    # #3373: die Karte sperrt zusaetzlich die SMS-Zelle der Trip-Eltern-Zeile
    # Temperatur (``karten_sperre``); sie zeigt die Token ihrer Kinder ohne
    # eigene Zeile, alle uebrigen gesperrten Zellen bleiben ohne Beispiel.
    from app.metric_catalog import karten_sperre as stellen_sperre
    from app.metric_catalog import stellen_sperre as versand_sperre

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
                if versand_sperre(zeile["metric_id"], stelle, surface):
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
    assert metriken <= set(_sms_an(antwort)) and "gust" not in metriken
    wind = next(e for e in legende["metrics"] if e["metric_id"] == "wind")
    assert (wind["kuerzel"], wind["meaning"]) == next(iter(get_metric("wind").kuerzel_bedeutung_de.items()))
    assert [e["token"] for e in legende["fixed"]] == [
        "@14", "!TS:H@14", "L", "M", "H", "WG", "RA", "AV4", "X?"]


# ---------------------------------------------------------------------------
# Abo ohne Tabelle: Tabelle aus der Grundauswahl (#3237, vorher Umrechnung)
# ---------------------------------------------------------------------------

def test_abo_ohne_tabelle_zeigt_die_umrechnung(client):
    from app.loader import get_data_root, load_trip
    from services.placements import placements_aus_grundauswahl

    _trip(NUTZER_A, "t-alt", grund=["wind", "gust", "precipitation"])
    antwort = _ok(client, "t-alt", "route")
    trip = load_trip("t-alt", data_dir=get_data_root(), user_id=NUTZER_A)
    soll = placements_aus_grundauswahl(trip.display_config, "trip",
                                       enabled_reports=["morning", "evening"])
    assert antwort["stored"] is False
    assert antwort["placements"] == soll
    assert [z["metric_id"] for z in antwort["rows"]] == [r["metric_id"] for r in soll["rows"]]


def test_orte_ohne_tabelle_zeigt_die_umrechnung(client):
    from services.placements import placements_aus_grundauswahl

    # #3277: das Altfeld ``outlook_enabled`` wirkt nicht mehr (ADR-0124 Nr. 6);
    # die Umrechnung traegt die Vorbelegung des Ausblicks.
    _orte(NUTZER_A, "o-alt", extra={"outlook_enabled": False})
    antwort = _ok(client, "o-alt", "vergleich")
    soll = placements_aus_grundauswahl({"active_metrics": ORTE_GRUND}, "compare",
                                       enabled_reports=["morning"])
    assert antwort["stored"] is False
    assert antwort["placements"] == soll
    assert antwort["outlook_reports"] == ["morning"]


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


# ---------------------------------------------------------------------------
# Kuerzel-Legende = Kuerzel, die der SMS-Renderer der Flaeche wirklich sendet
# (Spec Teil B Nr. 12, AC-31), Deutsch und Englisch
# ---------------------------------------------------------------------------

def _sprache(user: str, lang: str) -> None:
    pfad = _root() / "users" / user / "user.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps({"id": user, "language": lang}), encoding="utf-8")


def _trip_kuerzel_in_sms(sms: str) -> set[str]:
    """Metrik-Kuerzel der Trip-SMS aus den Symboltabellen des Renderers
    (laengstes passendes Symbol, ohne Doppelpunkt, Warnblock ausgenommen)."""
    from output.renderers.sms_trip import SMS_MULTI_SYMBOLS_BY_METRIC, SMS_SYMBOL_BY_METRIC

    alle = set(SMS_SYMBOL_BY_METRIC.values()) | {
        s for syms in SMS_MULTI_SYMBOLS_BY_METRIC.values() for s in syms}
    out = set()
    for tok in sms.split(" ")[1:]:  # #3174: Kopf ``E<n>`` ohne ``:``
        treffer = [s for s in alle if tok.startswith(s)]
        if treffer and not tok.startswith("!"):
            out.add(max(treffer, key=len).rstrip(":"))
    return out


def _orte_kuerzel_in_sms(sms: str) -> set[str]:
    """Metrik-Kuerzel der Orte-SMS (#3172: Token-Zeile wie im Trip, laengstes
    passendes Symbol, ohne Doppelpunkt, Warnblock ausgenommen). Ein Bereich
    ``D15/19`` zaehlt nur als ``D`` -- ein eigenes ``L`` sendet die SMS dann
    nicht, die Legende nennt es nicht (#3284)."""
    alle = _orte_symbole()
    out = set()
    for tok in sms.split(" "):
        treffer = [s for s in alle if tok.startswith(s)]
        if treffer and not tok.startswith("!"):
            out.add(max(treffer, key=len).rstrip(":"))
    return out


@pytest.mark.parametrize("lang", ["de", "en"])
@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_legende_hat_jedes_gesendete_kuerzel_mit_bedeutung(client, kind, lang):
    from app.metric_catalog import get_metric

    _sprache(NUTZER_A, lang)
    if kind == "route":
        _trip(NUTZER_A, "t-kz", grund=["temperature"] + TRIP_GRUND[:8],
              placements={"version": 1, "rows": [{"metric_id": "uv_index", "places": {"sms": False}}]})
        antwort, gesendet_fn = _ok(client, "t-kz", kind), _trip_kuerzel_in_sms
    else:
        _orte(NUTZER_A, "o-kz", anzahl=1, placements={"version": 1, "rows": [
            {"metric_id": "uv_index", "places": {"sms": False}}]})
        antwort, gesendet_fn = _ok(client, "o-kz", kind), _orte_kuerzel_in_sms
    legende = antwort["legend"]["metrics"]
    gesendet = gesendet_fn(antwort["sms_example"]["text"])
    assert gesendet, "Beispiel-SMS ohne Metrik-Kuerzel"
    in_legende = {e["kuerzel"] for e in legende}
    assert gesendet <= in_legende, f"gesendet, aber nicht erklaert: {gesendet - in_legende}"
    assert all(e["meaning"] for e in legende)
    sms_an = set(_sms_an(antwort))
    assert {e["metric_id"] for e in legende} <= sms_an and "uv_index" not in sms_an
    if kind == "route":
        assert "T" not in in_legende, "Temperatur sendet kein T in der Trip-SMS"
    else:
        # #3284: Hoechst+Tiefst verschmelzen in der SMS zum Bereichs-Token D13/27
        assert "D" in in_legende and "L" not in in_legende, "Orte senden Bereich als D"
    # #3284: Bereichs-Token traegt die zusammengesetzte Bedeutung Tief/Hoch.
    bereich = {"de": "Tagestiefstwert/Tageshöchstwert", "en": "day min/day max"}[lang]
    for e in legende:
        if e["kuerzel"] == "D" and "L" not in in_legende:
            assert e["meaning"] == bereich, e
            continue
        # Kuerzel unuebersetzt, Bedeutung in der Sprache des Nutzers aus dem Katalog
        katalog = {}
        for m in (e["metric_id"], *_kuerzel_quellen(e["metric_id"])):
            d = get_metric(m)
            katalog.update(d.kuerzel_bedeutung_en if lang == "en" else d.kuerzel_bedeutung_de)
        assert e["meaning"] == katalog[e["kuerzel"]], e


def _kuerzel_quellen(metric_id: str) -> tuple[str, ...]:
    """Katalog-IDs, unter denen der Orte-Renderer die Kuerzel einer Zeile fuehrt
    (Temperatur -> Tageshoechst/-tiefst)."""
    from output.renderers.compare_metric_ids import _renderer_ids_for_kennung
    from output.renderers.comparison import _RENDERER_TO_CATALOG_METRIC_ID

    return tuple(_RENDERER_TO_CATALOG_METRIC_ID[r] for r in _renderer_ids_for_kennung(metric_id)
                 if r in _RENDERER_TO_CATALOG_METRIC_ID)


# ---------------------------------------------------------------------------
# Fix-Loop 2 (Adversary): Namen mit Trennzeichen, verschmolzene Token,
# ueberlange Kennung, echte App, fremde Orte, fester Datensatz
# ---------------------------------------------------------------------------

def _markiert(antwort) -> set[str]:
    return {z["metric_id"] for z in antwort["rows"]
            if z["cells"]["sms"]["mark"] == "passt_nicht_mehr"}


@pytest.mark.parametrize("etappe,kopf", [
    # #3373: der Versand nummeriert die Etappe (``numbered_stage_label``), der
    # Kopf ist ``E1`` -- auch bei Namen mit ``:`` oder kuerzelartigem Text.
    ("Tag 1: SU7", "E1 "), ("W: G5 R1", "E1 "),
])
def test_f001_etappenname_mit_trennzeichen_verfaelscht_nichts(client, etappe, kopf):
    """Der Kopf der Trip-SMS ist die nummerierte Etappe; steht im Namen
    ``: `` oder ein Text, der wie ein Kuerzel aussieht, bleiben Beispielwerte
    und Marken die der wirklichen Token."""
    _trip(NUTZER_A, "t-f001", placements={"version": 1, "rows": []}, etappe=etappe)
    antwort = _ok(client, "t-f001", "route")
    versand = _trip_versand_sms(NUTZER_A, "t-f001")
    assert versand.startswith(kopf), versand
    rumpf = versand[len(kopf):]
    token = rumpf.split(" ")

    assert antwort["sms_example"]["text"] == versand
    fehlend = {m for m in _sms_an(antwort) if _trip_fehlt_in_sms(versand, m, rumpf)}
    assert "sunshine" in fehlend, "Datensatz muss die SMS ueberlaufen lassen"
    assert _markiert(antwort) == fehlend
    for zeile in antwort["rows"]:
        beispiel = zeile["cells"]["sms"]["example"]
        if beispiel:
            assert set(beispiel.split(" ")) <= set(token), (zeile["metric_id"], beispiel)
    assert _zeile(antwort, "wind")["cells"]["sms"]["example"].startswith("W3")
    assert _zeile(antwort, "gust")["cells"]["sms"]["example"].startswith("G3")


@pytest.mark.parametrize("anzahl", [1, 3])
def test_f002_ortsname_mit_trennzeichen_verfaelscht_nichts(client, anzahl):
    namen = ("Wind 5: B; C", "Lienz", "Kufstein")
    kennung = f"o-f002-{anzahl}"
    _orte(NUTZER_A, kennung, anzahl=anzahl, placements={"version": 1, "rows": []}, namen=namen)
    antwort = _ok(client, kennung, "vergleich")
    versand = _orte_versand_sms(NUTZER_A, kennung)
    # #3172 (PO 2026-11-19): keine Namen in der SMS -- ein Name mit Trennzeichen
    # kann sie nicht mehr verfaelschen; der erste Ort steht als ``O1``.
    from tests.helpers.orte_sms import orte_teil, orte_token

    assert versand.startswith("O1 ") and "Wind 5" not in versand, versand
    teil = " ".join(orte_token(orte_teil(versand, 1)))

    assert antwort["sms_example"]["text"] == versand
    fehlend = {m for m in _sms_an(antwort) if _orte_fehlt_in_sms(versand, m, teil)}
    # #3172: ein Ort passt ohne Namen und Kopf ganz in 160 Zeichen.
    assert (fehlend or anzahl == 1) and len(fehlend) < len(_sms_an(antwort)), "weder alles noch nichts darf fehlen"
    assert _markiert(antwort) == fehlend
    wind = _zeile(antwort, "wind")["cells"]
    assert wind["sms"]["example"] == "W30@10(43@16)"  # #3172: Token der Token-Zeile
    assert wind["telegram"]["example"] == "Wind 43 km/h", "Ortsname ist keine Wind-Zelle"


def test_f003_ueberlange_kennung_ist_kein_serverfehler(client):
    _trip(NUTZER_A, "t-lang")
    for kind in ("route", "vergleich"):
        for laenge in (300, 5000):
            antwort = _get(client, "x" * laenge, kind)
            assert antwort.status_code == 404, (kind, laenge, antwort.status_code)
            assert antwort.json()["code"] == "not_found"


def test_f004_verschmolzenes_token_steht_bei_beiden_haelften(client):
    """``L``/``D`` und ``FL``/``FD`` verschmelzen in der SMS zu EINEM Bereichs-
    Token unter dem Hoechstwert-Kuerzel; die Tiefstwert-Zeile gilt nicht als
    'passt nicht mehr' -- auch als letzte SMS-Zeile. #3283 B2: die Fenster-
    Kinder zeigen in der Karte kein Beispiel mehr (Soll-Bild Fassung 4)."""
    _trip(NUTZER_A, "t-f004", grund=["temperature", "wind_chill", "wind"],
          placements={"version": 1, "rows": [
              {"metric_id": "temperature_day_high"}, {"metric_id": "wind_chill_day_high"},
              {"metric_id": "wind"}, {"metric_id": "wind_chill_day_low"},
              {"metric_id": "temperature_day_low"}]})
    antwort = _ok(client, "t-f004", "route")
    token = antwort["sms_example"]["text"].split(" ")[1:]  # #3174: Kopf ohne ``:``
    bereich = {"D": next(t for t in token if re.fullmatch(r"D-?\d+/-?\d+", t)),
               "FD": next(t for t in token if re.fullmatch(r"FD-?\d+/-?\d+", t))}
    assert not any(re.match(r"F?L-?\d", t) for t in token), "Vorbedingung: kein eigenes L/FL-Token"
    for tief, hoch, sym in (("temperature_day_low", "temperature_day_high", "D"),
                            ("wind_chill_day_low", "wind_chill_day_high", "FD")):
        for mid in (tief, hoch):
            zelle = _zeile(antwort, mid)["cells"]["sms"]
            assert bereich[sym] in token, "Vorbedingung: SMS traegt das Bereichs-Token"
            assert (zelle["state"], zelle["example"], zelle["mark"]) == ("on", None, None), mid
    assert _markiert(antwort) == set()


def test_t2_t6_echte_app_route_und_kern_geheimnis():
    """Die Route haengt in der echten FastAPI-App ``api.main`` und liegt
    hinter dem Kern-Geheimnis (ADR-0062)."""
    from api.main import CORE_AUTH_HEADER, app

    _trip(NUTZER_A, "t-app", placements=TRIP_PLACEMENTS)
    pfad, params = "/api/briefings/t-app/placements", {"kind": "route", "user_id": NUTZER_A}
    mit = TestClient(app)
    antwort = mit.get(pfad, params=params)
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["rows"][0]["metric_id"] == "gust"

    ohne = TestClient(app)
    del ohne.headers[CORE_AUTH_HEADER]
    assert ohne.get(pfad, params=params).status_code == 401
    falsch = TestClient(app)
    falsch.headers[CORE_AUTH_HEADER] = "falsches-geheimnis"
    abgewiesen = falsch.get(pfad, params=params)
    assert abgewiesen.status_code == 401 and "rows" not in abgewiesen.text


def test_t5_orte_nur_aus_dem_bestand_des_nutzers(client):
    """Ein Abo von A, das auf eine Orts-Kennung zeigt, die nur B besitzt,
    bekommt weder Name noch Daten von B."""
    _schreibe(NUTZER_B, "locations", "nur-b", {
        "id": "nur-b", "name": "GeheimerOrtVonB", "lat": 46.0, "lon": 10.0, "elevation_m": 2000})
    pfad = _orte(NUTZER_A, "o-t5", anzahl=1, placements={"version": 1, "rows": []})
    daten = json.loads(pfad.read_text())
    daten["location_ids"] = ["nur-b"] + daten["location_ids"]
    pfad.write_text(json.dumps(daten), encoding="utf-8")

    antwort = _get(client, "o-t5", "vergleich")
    assert antwort.status_code == 200, antwort.text
    assert "GeheimerOrtVonB" not in antwort.text
    assert antwort.json()["location_count"] == 1
    # #3172: keine Namen in der SMS -- genau ein Ort (der eigene) als O1.
    from tests.helpers.orte_sms import orte_nummern

    assert orte_nummern(antwort.json()["sms_example"]["text"]) == [1]

    daten["location_ids"] = ["nur-b"]
    pfad.write_text(json.dumps(daten), encoding="utf-8")
    nur_fremd = _get(client, "o-t5", "vergleich")
    assert nur_fremd.status_code == 200 and "GeheimerOrtVonB" not in nur_fremd.text
    assert (nur_fremd.json()["location_count"], nur_fremd.json()["sms_example"]) == (0, None)


@pytest.mark.parametrize("kind,kennung", [("route", "t-t7"), ("vergleich", "o-t7")])
def test_t7_antwort_haengt_nicht_am_tag_des_abrufs(client, kind, kennung):
    from freezegun import freeze_time

    _trip(NUTZER_A, "t-t7", placements={"version": 1, "rows": []})
    _orte(NUTZER_A, "o-t7", placements={"version": 1, "rows": []})
    with freeze_time("2026-01-05T07:30:00+00:00"):
        winter = _ok(client, kennung, kind)
    with freeze_time("2027-08-21T22:10:00+00:00"):
        sommer = _ok(client, kennung, kind)
    assert winter == sommer


#: Fingerabdruck der Beispieldaten je ``VERSION``. Wer die Daten aendert,
#: erhoeht ``placements_beispiel.VERSION`` und traegt den neuen Wert ein.
#: #3373: VERSION 2 = Nacht am Ziel dazu (Fingerabdruck schliesst sie ein).
BEISPIEL_FINGERABDRUCK = {2: "b2ac5cb70c220142ec4130ccb3a6467ef909f6c8a47f2c4947032318d6a72b07"}


def _beispiel_fingerabdruck() -> str:
    import dataclasses
    import hashlib

    from app.user import SavedLocation
    from services import placements_beispiel as pb

    orte = [SavedLocation(id=f"f{i}", name=f"F{i}", lat=47.0 + i, lon=11.0, elevation_m=500)
            for i in range(2)]

    def _roh(o):
        return dataclasses.asdict(o) if dataclasses.is_dataclass(o) else str(o)

    daten = [pb.trip_segmente(), pb.ausblick_tage(), pb.orte_ergebnis(orte), str(pb.ZONE), str(pb.TAG),
             pb.nacht_zeitreihe()]  # #3373: VERSION 2 traegt die Nacht
    return hashlib.sha256(json.dumps(daten, default=_roh, sort_keys=True).encode()).hexdigest()


def test_t7_beispieldaten_sind_an_die_version_gebunden():
    from services import placements_beispiel as pb

    assert pb.VERSION in BEISPIEL_FINGERABDRUCK, "neue VERSION ohne Fingerabdruck"
    assert _beispiel_fingerabdruck() == BEISPIEL_FINGERABDRUCK[pb.VERSION], (
        "Beispieldaten geaendert: placements_beispiel.VERSION erhoehen und den "
        "Fingerabdruck der neuen Version eintragen")


def test_t8_metrik_name_in_der_sprache_des_nutzers(client):
    from app.metric_catalog import get_metric

    assert get_metric("gust").label("en") != get_metric("gust").label("de")
    _trip(NUTZER_A, "t-en", placements=TRIP_PLACEMENTS)
    _sprache(NUTZER_A, "en")
    antwort = _ok(client, "t-en", "route")
    assert antwort["lang"] == "en"
    assert _zeile(antwort, "gust")["name"] == get_metric("gust").label("en")
    _sprache(NUTZER_A, "de")
    assert _zeile(_ok(client, "t-en", "route"), "gust")["name"] == get_metric("gust").label("de")


def test_t9_reines_morgen_abo_zeigt_das_morgen_briefing(client):
    """Beispiel = das Briefing, das der Nutzer bekommt: bei reinem Morgen-Abo
    das Morgen-Briefing, sonst das Abend-Briefing."""
    grund = ["temperature", "wind"]
    _trip(NUTZER_A, "t-morgen", grund=grund, placements={"version": 1, "rows": []},
          rc={"enabled": True, "morning_enabled": True, "evening_enabled": False})
    _trip(NUTZER_A, "t-beide", grund=grund, placements={"version": 1, "rows": []})
    morgen = _trip_versand_sms(NUTZER_A, "t-morgen", "morning")
    abend = _trip_versand_sms(NUTZER_A, "t-beide", "evening")
    assert morgen != abend, "Vorbedingung: Morgen- und Abend-SMS unterscheiden sich"
    assert _ok(client, "t-morgen", "route")["sms_example"]["text"] == morgen
    assert _ok(client, "t-beide", "route")["sms_example"]["text"] == abend


def test_t9_parent_nennt_die_eltern_zeile(client):
    _trip(NUTZER_A, "t-parent", grund=["temperature", "wind_chill", "wind"],
          placements={"version": 1, "rows": []})
    antwort = _ok(client, "t-parent", "route")
    assert _zeile(antwort, "temperature_night")["parent"] == "temperature"
    assert _zeile(antwort, "wind_chill_day_low")["parent"] == "wind_chill"
    assert _zeile(antwort, "temperature")["parent"] is None
    assert _zeile(antwort, "wind")["parent"] is None


#: Abo-Ampel mit tiefer Wind-Gelbgrenze (wie ``ABO_AMPEL`` in test_3172):
#: der Wind-Token haengt sichtbar an der Ampel DIESES Abos.
_ABO_AMPEL_WIND = {"template": "allgemein",
                   "metrics": {"wind": {"upper": {"yellow": 12, "orange": 40, "red": 60}}}}


def _wind_token_mit(ampel: dict, kennung: str) -> str:
    """Wind-Token des ersten Orts aus dem Beispiel-Datensatz mit ``ampel``."""
    from app.loader import load_all_locations
    from output.renderers.orte_sms import orte_token_reihen
    from services import placements_beispiel as pb

    ort = next(o for o in load_all_locations(NUTZER_A) if o.id == f"{kennung}-ort0")
    loc = pb.orte_ergebnis([ort]).locations[0]
    return " ".join(t.render() for t in orte_token_reihen(loc, ["wind_max"], None, ampel=ampel)[0])


def test_3172_f002_sms_beispielwert_folgt_der_abo_ampel(client):
    """#3172 Adversary F002: der SMS-Beispielwert der Karte entsteht mit der
    Ampel des Abos -- derselben, mit der die SMS rendert. Mit einer anderen
    Ampel (Standard-Vorlage) waere der Wind-Token ein anderer, stuende nicht
    in der SMS, und die Zeile hiesse faelschlich "passt nicht mehr"."""
    from app.ampel import resolve_ampel

    kennung = "o-f002-ampel"
    pfad = _orte(NUTZER_A, kennung, anzahl=1, placements={"version": 1, "rows": []},
                 grund=[{"metric_id": "wind", "aggregation": "max"}])
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    daten["display_config"]["ampel"] = _ABO_AMPEL_WIND
    pfad.write_text(json.dumps(daten), encoding="utf-8")

    antwort = _ok(client, kennung, "vergleich")
    sms = antwort["sms_example"]["text"]
    assert sms == _orte_versand_sms(NUTZER_A, kennung), sms
    abo = _wind_token_mit(resolve_ampel(daten), kennung)
    # Vorbedingung: die Abo-Ampel aendert den Token gegenueber der Standard-Vorlage.
    assert abo != _wind_token_mit(resolve_ampel({}), kennung), abo
    assert sms == f"O1 {abo}", sms
    zelle = _zeile(antwort, "wind")["cells"]["sms"]
    assert zelle["example"] == abo, (zelle, sms)
    assert zelle["mark"] is None, zelle
