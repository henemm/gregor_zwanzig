"""SMS-Beispiel der Trip-Karte "Was steht wo" gleich dem echten Versand (#3373).

SPEC: docs/specs/modules/feat_3373_sms_beispiel_karte.md (AC-1 bis AC-8).

Nutzersicht ist die Antwort des Karten-Endpunkts
``GET /api/briefings/{id}/placements?kind=route`` (``sms_example["text"]``,
Zeilen/Zellen). Das Soll entsteht aus dem Versandaufbau
(``trip_briefing_aufbau.trip_anreicherung_bauen``: nummerierte Etappe,
Nachtwetter, Folgetag-Gewitter aus der Scheduler-Ableitung) mit demselben
festen Beispiel-Datensatz -- nicht aus der Antwort selbst.

Kern-Schicht: echte Dateien, echte Renderer, kein Netz, kein Mock.

AC-6 (Versand-Invariante) vergleicht SMS, E-Mail und Telegram eines festen
Trips ueber den Versand-Render-Weg und die Orte-Karte mit einer VOR der
Aenderung festgehaltenen Referenz (``tests/fixtures/feat_3373/``). Die
Referenz wird nie aus dem Test heraus neu geschrieben.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.tdd.test_placements_tabelle_endpoint import (
    ORTE_GRUND, _beispiel_nacht, _orte, _schreibe, _trip_fehlt_in_sms,
    _trip_versand_bericht,
)

NUTZER_A, NUTZER_B = "p3373-a", "p3373-b"
REFERENZ = Path(__file__).resolve().parents[1] / "fixtures" / "feat_3373" / "versand_referenz.json"

#: Mehr Metriken, als in 160 Zeichen passen (wie ``TRIP_GRUND`` in
#: test_placements_tabelle_endpoint, dazu Temperatur und gefuehlte Temperatur).
VIELE = [
    "temperature", "wind_chill", "wind", "gust", "rain_probability", "precipitation",
    "thunder", "cloud_total", "visibility", "freezing_level", "uv_index", "humidity",
    "dewpoint", "pressure", "cloud_low", "cloud_mid", "cloud_high", "precip_type",
    "snowfall_limit", "sunshine",
]
#: Fester Trip der Versand-Invariante (AC-6).
REFERENZ_GRUND = [
    "temperature", "wind_chill", "wind", "gust", "thunder", "precipitation",
    "rain_probability", "cloud_total", "visibility", "freezing_level", "uv_index", "sunshine",
]
TEMPERATUR_SMS_AN = {"version": 1, "rows": [{"metric_id": "temperature", "places": {"sms": True}}]}


# ---------------------------------------------------------------------------
# Daten und Client
# ---------------------------------------------------------------------------

def _wegpunkte() -> list[dict]:
    return [{"id": "W1", "name": "Start", "lat": 47.27, "lon": 11.40, "elevation_m": 600},
            {"id": "W2", "name": "Ziel", "lat": 47.29, "lon": 11.42, "elevation_m": 900}]


def _trip(user: str, kennung: str, *, etappen=(("Tag 1", "2026-07-14"),), grund=VIELE,
          placements=None, rc=None, name=None) -> Path:
    """Trip mit Etappen ``(Name, Datum)`` in gespeicherter Reihenfolge."""
    dc = {"trip_id": kennung, "metrics": [
        {"metric_id": m, "enabled": True, "bucket": "primary", "order": i}
        for i, m in enumerate(grund)]}
    if placements is not None:
        dc["placements"] = placements
    daten = {
        "id": kennung, "name": name or ("Trip " + kennung), "kind": "route",
        "stages": [{"id": f"T{i + 1}", "name": n, "date": d, "waypoints": _wegpunkte()}
                   for i, (n, d) in enumerate(etappen)],
        "display_config": dc,
    }
    if rc is not None:
        daten["report_config"] = rc
    return _schreibe(user, "briefings", kennung, daten)


@pytest.fixture
def client():
    from api.routers import placements

    app = FastAPI()
    app.include_router(placements.router)
    return TestClient(app)


def _get(client, kennung, user=NUTZER_A, kind="route"):
    return client.get(f"/api/briefings/{kennung}/placements",
                      params={"kind": kind, "user_id": user})


def _ok(client, kennung, user=NUTZER_A, kind="route") -> dict:
    antwort = _get(client, kennung, user, kind)
    assert antwort.status_code == 200, antwort.text
    return antwort.json()


def _zeile(antwort, metric_id) -> dict:
    return next(z for z in antwort["rows"] if z["metric_id"] == metric_id)


def _token(sms: str, praefix: str) -> list[str]:
    """Token der SMS, die mit ``praefix`` und danach einer Ziffer, ``-`` oder
    ``:`` beginnen (``N10``, ``TH+:M@15``) -- nicht ``NE`` o. ae."""
    return [t for t in sms.split(" ") if re.match(re.escape(praefix) + r"[-\d:]", t)]


# ---------------------------------------------------------------------------
# AC-1: Kopf = nummerierte Etappe wie im Versand
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fall,etappen,kopf", [
    ("tag1", (("Tag 1", "2026-07-14"),), "E1"),
    ("freier_name", (("Huettenweg zum Gipfel", "2026-07-14"),), "E1"),
    # gespeichert unsortiert: die erste Etappe nach Datum steht an zweiter Stelle
    ("unsortiert", (("Gipfeltag", "2026-07-15"), ("Talweg", "2026-07-14")), "E1"),
])
def test_ac1_kopf_ist_die_nummerierte_erste_etappe_wie_im_versand(client, fall, etappen, kopf):
    kennung = f"t-3373-ac1-{fall}"
    _trip(NUTZER_A, kennung, etappen=etappen, grund=["wind", "gust"])
    beispiel = _ok(client, kennung)["sms_example"]["text"]
    versand = _trip_versand_sms_text(kennung)

    assert versand.split(" ")[0] == kopf, f"Vorbedingung Versand-Kopf: {versand!r}"
    assert beispiel.split(" ")[0] == kopf, (
        f"Kopf des SMS-Beispiels {beispiel.split(' ')[0]!r} statt {kopf!r} wie im Versand "
        f"({versand!r})")


def test_ac1_trip_ohne_etappen_beginnt_mit_dem_trip_namen(client):
    from output.renderers.sms_trip import _sms_stage_prefix
    from output.tokens.builder import _sanitize_stage_name

    kennung = "t-3373-ac1-ohne"
    _trip(NUTZER_A, kennung, etappen=(), grund=["wind", "gust"], name="Rundweg")
    beispiel = _ok(client, kennung)["sms_example"]["text"]
    kopf = _sanitize_stage_name(_sms_stage_prefix("Rundweg"))
    assert beispiel.startswith(kopf + " "), beispiel
    assert _trip_versand_sms_text(kennung).startswith(kopf + " ")


def _trip_versand_sms_text(kennung: str, user: str = NUTZER_A, report_type: str = "evening") -> str:
    return _trip_versand_bericht(user, kennung, report_type).sms_text


# ---------------------------------------------------------------------------
# AC-2: N = Nacht-Tiefstwert (nur abends), Spitzen bis Fensterende
# ---------------------------------------------------------------------------

def test_ac2_abend_n_ist_der_nacht_tiefstwert_und_spitzen_bis_fensterende(client):
    from services.weather_metrics import summarize_points

    kennung = "t-3373-ac2-abend"
    _trip(NUTZER_A, kennung, grund=["temperature", "wind", "gust"])
    beispiel = _ok(client, kennung)["sms_example"]["text"]
    versand = _trip_versand_sms_text(kennung)

    nacht_min = summarize_points(_beispiel_nacht().data).temp_min_c
    assert _token(versand, "N") == [f"N{round(nacht_min)}"], (
        f"Vorbedingung: Versand zeigt den Nacht-Tiefstwert ({versand!r})")
    assert _token(beispiel, "N") == _token(versand, "N"), (
        f"N im Beispiel {_token(beispiel, 'N')} statt Nacht-Tiefstwert {_token(versand, 'N')}")
    for kuerzel in ("W", "G"):
        assert _token(beispiel, kuerzel) == _token(versand, kuerzel), (
            f"Spitze {kuerzel}: Beispiel {_token(beispiel, kuerzel)} statt "
            f"Versand {_token(versand, kuerzel)} (Spitzen bis Fensterende nach Ankunft)")
    assert beispiel == versand


def test_ac2_morgen_fassung_ohne_n_und_gleich_versand(client):
    kennung = "t-3373-ac2-morgen"
    _trip(NUTZER_A, kennung, grund=["temperature", "wind", "gust"],
          rc={"enabled": True, "morning_enabled": True, "evening_enabled": False})
    beispiel = _ok(client, kennung)["sms_example"]["text"]
    versand = _trip_versand_sms_text(kennung, report_type="morning")

    assert _token(versand, "N") == [], f"Vorbedingung: Morgen-SMS ohne N ({versand!r})"
    assert _token(beispiel, "N") == [], beispiel
    assert beispiel == versand


# ---------------------------------------------------------------------------
# AC-3: TH+ aus dem Folgetag-Gewitter des Beispiel-Trends
# ---------------------------------------------------------------------------

def test_ac3_th_plus_aus_dem_folgetag_gewitter_wie_im_versand(client):
    from app.models import ThunderLevel

    kennung = "t-3373-ac3"
    _trip(NUTZER_A, kennung, grund=["thunder", "wind"])
    beispiel = _ok(client, kennung)["sms_example"]["text"]
    versand = _trip_versand_sms_text(kennung)

    assert _token(versand, "TH+") and _token(versand, "TH+") != ["TH+:-"], (
        f"Vorbedingung: Beispiel-Trend hat ein Folgetag-Gewitter ({versand!r})")
    assert _token(beispiel, "TH+") == _token(versand, "TH+"), (
        f"TH+ im Beispiel {_token(beispiel, 'TH+')} statt {_token(versand, 'TH+')} "
        "aus dem Folgetag-Gewitter")
    assert ThunderLevel.MED.value[0] in _token(versand, "TH+")[0]


# ---------------------------------------------------------------------------
# AC-4: zeichengleich, Laenge, "passt nicht mehr"
# ---------------------------------------------------------------------------

def test_ac4_beispiel_zeichengleich_mit_versand_und_marken(client):
    kennung = "t-3373-ac4"
    _trip(NUTZER_A, kennung, placements={"version": 1, "rows": []})
    antwort = _ok(client, kennung)
    versand = _trip_versand_sms_text(kennung)

    assert versand.startswith("E1 "), versand
    assert antwort["sms_example"]["text"] == versand
    assert antwort["sms_example"]["length"] == len(versand)
    assert len(versand) <= antwort["sms_example"]["max_length"] == 160

    from app.loader import _DERIVED_METRIC_RULES

    kinder = {kind for kind, _e, _a in _DERIVED_METRIC_RULES}
    sms_an = [z["metric_id"] for z in antwort["rows"]
              if z["cells"]["sms"]["state"] == "on" and z["metric_id"] not in kinder
              and z["metric_id"] != "temperature"]
    fehlend = {m for m in sms_an if _trip_fehlt_in_sms(versand, m)}
    assert fehlend, "Datensatz muss die SMS ueberlaufen lassen"
    markiert = {z["metric_id"] for z in antwort["rows"]
                if z["cells"]["sms"]["mark"] == "passt_nicht_mehr"}
    assert markiert == fehlend


# ---------------------------------------------------------------------------
# AC-5: Eltern-Zeile Temperatur gesperrt, kein doppeltes Token
# ---------------------------------------------------------------------------

def test_ac5_eltern_zeile_temperatur_gesperrt_und_ohne_token(client):
    kennung = "t-3373-ac5"
    _trip(NUTZER_A, kennung, grund=["temperature", "wind_chill", "wind"])
    antwort = _ok(client, kennung)
    sms = antwort["sms_example"]["text"].split(" ")

    eltern = _zeile(antwort, "temperature")["cells"]["sms"]
    assert (eltern["state"], eltern["reason"]) == ("locked", "kein_kuerzel"), eltern
    # Spec AC-5 (praezisiert): die Eltern-Zeile zeigt nur die Token der Kinder
    # ohne eigenes Beispiel -- den Tagesbereich ``D…`` --, kein ``N``.
    bereich = [t for t in sms if re.fullmatch(r"D-?\d+/-?\d+", t)]
    assert bereich, f"Vorbedingung: SMS traegt den Tagesbereich ({sms})"
    assert eltern["example"] == " ".join(bereich), (
        f"Eltern-Zeile zeigt {eltern['example']!r} statt nur Tagesbereich {bereich}")

    gefuehlt = _zeile(antwort, "wind_chill")["cells"]["sms"]
    assert gefuehlt["state"] == "on", f"wind_chill (Kuerzel TF) bleibt schaltbar: {gefuehlt}"

    nacht = _zeile(antwort, "temperature_night")["cells"]["sms"]["example"]
    assert nacht and nacht in sms and nacht.startswith("N"), nacht

    gesehen: dict[str, str] = {}
    for zeile in antwort["rows"]:
        beispiel = zeile["cells"]["sms"]["example"]
        for tok in (beispiel or "").split(" "):
            if not tok:
                continue
            assert tok in sms, (zeile["metric_id"], tok)
            assert tok not in gesehen, (
                f"Token {tok!r} steht doppelt: {gesehen[tok]} und {zeile['metric_id']}")
            gesehen[tok] = zeile["metric_id"]


# ---------------------------------------------------------------------------
# AC-6: Versand-Invariante (Waechter, gegen Referenz von VOR der Aenderung)
# ---------------------------------------------------------------------------

def _versand_texte(user: str, kennung: str, report_type: str) -> dict:
    """SMS, E-Mail und Telegram ueber den Versand-Render-Weg
    (``trip_anreicherung_bauen`` + ``trip_report_rendern``) mit dem festen
    Beispiel-Datensatz, fester Nachtreihe und festen Trend-Zeilen."""
    from datetime import datetime, timedelta, timezone

    from app.ampel import resolve_ampel
    from app.loader import get_data_root, load_trip
    from app.models import OutlookState, TrendResult
    from output.renderers.email.outlook import build_outlook_row
    from services import placements_beispiel as pb
    from services import trip_briefing_aufbau as aufbau
    from services.report_config_resolver import resolve_report_render_options
    from services.trip_report_scheduler import TripReportSchedulerService
    from services.weather_metrics import summarize_points

    trip = load_trip(kennung, data_dir=get_data_root(), user_id=user)
    dc = trip.display_config
    zeilen = []
    for i, (wd, punkte) in enumerate(pb.ausblick_tage()):
        zeile = build_outlook_row(summarize_points(punkte), punkte, wd, pb.ZONE,
                                  trip_display_config=dc, report_type=report_type,
                                  context="route", ampel=resolve_ampel(trip))
        zeile["date"] = pb.TAG + timedelta(days=i + 1)
        zeilen.append(zeile)
    segmente = pb.trip_segmente()
    optionen = resolve_report_render_options(trip.report_config, dc, report_type)
    an = aufbau.trip_anreicherung_bauen(
        TripReportSchedulerService(user_id=user), trip, pb.TAG, segmente,
        report_type=report_type, now_utc=datetime(2026, 7, 14, 4, 0, tzinfo=timezone.utc),
        trip_tz=pb.ZONE, render_options=optionen, night_weather=_beispiel_nacht(),
        trend_result=TrendResult(rows=zeilen, state=OutlookState.FOUND),
    )
    bericht = aufbau.trip_report_rendern(
        segment_weather=segmente, trip=trip, report_type=report_type, display_config=dc,
        profile=trip.aggregation.profile, report_config=trip.report_config,
        render_options=optionen, tz=pb.ZONE, stage_name=an.stage_name,
        stage_stats=an.stage_stats, stability_result=an.stability_result,
        night_weather=an.night_weather, thunder_forecast=an.thunder_forecast,
        multi_day_trend=an.multi_day_trend, outlook_state=an.outlook_state,
        outlook_horizon_days=an.outlook_horizon_days, stage_total=len(trip.stages),
        lang="de",
    )
    import hashlib

    # HTML als Pruefsumme (Groesse der Referenzdatei); Klartext, SMS und
    # Telegram woertlich, damit eine Abweichung lesbar ist.
    return {"sms": bericht.sms_text, "email_subject": bericht.email_subject,
            "email_html_sha256": hashlib.sha256(bericht.email_html.encode()).hexdigest(),
            "email_plain": bericht.email_plain,
            "telegram": list(bericht.telegram_bubbles or [])}


def _referenz_trips(user: str) -> None:
    etappen = (("Tag 1", "2026-07-14"), ("Tag 2", "2026-07-15"))
    _trip(user, "t-3373-ref", etappen=etappen, grund=REFERENZ_GRUND, name="Referenz")
    _trip(user, "t-3373-ref-temp-sms", etappen=etappen, grund=REFERENZ_GRUND,
          name="Referenz", placements=TEMPERATUR_SMS_AN)
    _orte(user, "o-3373-ref", anzahl=3, placements={"version": 1, "rows": []}, grund=ORTE_GRUND)


def _ist_stand(client, user: str) -> dict:
    """Alles, was AC-6 festhaelt (auch die Grundlage der Referenzdatei)."""
    from freezegun import freeze_time

    _referenz_trips(user)
    stand: dict = {"versand": {}}
    with freeze_time("2026-07-14T04:00:00+00:00"):
        for kennung in ("t-3373-ref", "t-3373-ref-temp-sms"):
            for rt in ("morning", "evening"):
                stand["versand"][f"{kennung}/{rt}"] = _versand_texte(user, kennung, rt)
        orte = _ok(client, "o-3373-ref", user, kind="vergleich")
    # Version des Beispiel-Datensatzes steigt gewollt (Spec: VERSION 2).
    orte.pop("example_version", None)
    stand["orte_karte"] = orte
    return stand


def test_ac6_versand_sms_mail_telegram_und_orte_karte_unveraendert(client):
    assert REFERENZ.is_file(), f"Referenz fehlt: {REFERENZ}"
    referenz = json.loads(REFERENZ.read_text(encoding="utf-8"))
    ist = _ist_stand(client, NUTZER_A)

    assert set(ist["versand"]) == set(referenz["versand"])
    for schluessel, texte in referenz["versand"].items():
        for kanal, soll in texte.items():
            assert ist["versand"][schluessel][kanal] == soll, (
                f"Versand {schluessel}/{kanal} weicht von der Referenz vor #3373 ab")
    assert ist["orte_karte"] == referenz["orte_karte"], "Orte-Karte hat sich geaendert"


def test_ac6_gespeichertes_temperatur_sms_an_aendert_den_versand_nicht(client):
    _referenz_trips(NUTZER_A)
    from freezegun import freeze_time

    with freeze_time("2026-07-14T04:00:00+00:00"):
        for rt in ("morning", "evening"):
            ohne = _versand_texte(NUTZER_A, "t-3373-ref", rt)
            mit = _versand_texte(NUTZER_A, "t-3373-ref-temp-sms", rt)
            assert mit["sms"] == ohne["sms"], (rt, mit["sms"], ohne["sms"])


# ---------------------------------------------------------------------------
# AC-7: Nacht im E-Mail- und Telegram-Beispiel bei Nachtblock
# ---------------------------------------------------------------------------

def _kurzuebersicht(bubbles: list[str], compact_label: str) -> str | None:
    import html

    from i18n import t

    kopf = t("telegram.kopf.zusammenfassung", "de")
    blase = next((b for b in bubbles if b.split("\n", 1)[0] == kopf), "")
    return next((html.unescape(z) for z in blase.split("\n")[1:]
                 if html.unescape(z).startswith(compact_label + " ")), None)


def test_ac7_telegram_und_email_beispiel_mit_nacht_wie_versand(client):
    from app.metric_catalog import get_metric

    kennung = "t-3373-ac7"
    _trip(NUTZER_A, kennung, grund=["temperature", "wind_chill", "wind", "gust"])
    antwort = _ok(client, kennung)
    assert antwort["blocks"]["show_night_block"] is True, "Vorbedingung: Nachtblock an"
    bericht = _trip_versand_bericht(NUTZER_A, kennung)

    # Telegram: Kurzuebersicht des Versands schliesst die Nacht ein (Tiefstwert
    # der Nacht, Spitzen bis Fensterende).
    for mid in ("temperature", "wind_chill", "wind", "gust"):
        soll = _kurzuebersicht(bericht.telegram_bubbles, get_metric(mid).compact_label)
        assert soll, f"Vorbedingung: Versand-Kurzuebersicht hat {mid}"
        ist = _zeile(antwort, mid)["cells"]["telegram"]["example"]
        assert ist == soll, f"Telegram-Beispiel {mid}: {ist!r} statt {soll!r} (mit Nacht)"

    # E-Mail: Beispielwerte der Karte aus derselben Mail wie der Versand.
    from services.placements_view_service import _html_stundentabelle, _mit_kuerzel

    ids = [z["metric_id"] for z in antwort["rows"]]
    soll_mail = _mit_kuerzel(_html_stundentabelle(bericht.email_html, ids))
    for mid, (text, ampel) in soll_mail.items():
        zelle = _zeile(antwort, mid)["cells"]["email"]
        assert (zelle["example"], zelle["ampel"]) == (text, ampel), mid


# ---------------------------------------------------------------------------
# AC-8: zwei Nutzer, Fremdzugriff abgewiesen
# ---------------------------------------------------------------------------

def test_ac8_zwei_nutzer_je_eigene_karte_und_fremdzugriff_abgewiesen(client):
    kennung = "t-3373-ac8"
    _trip(NUTZER_A, kennung, grund=["wind", "gust"])
    _trip(NUTZER_B, kennung, etappen=(), grund=["wind", "gust"], name="Bweg")
    _trip(NUTZER_B, "t-3373-nur-b", etappen=(), grund=["wind"], name="Geheim")

    a = _ok(client, kennung, NUTZER_A)["sms_example"]["text"]
    b = _ok(client, kennung, NUTZER_B)["sms_example"]["text"]
    assert a.split(" ")[0] == _trip_versand_sms_text(kennung, NUTZER_A).split(" ")[0] == "E1", a
    assert b.startswith("Bweg "), b
    assert a != b

    fremd = _get(client, "t-3373-nur-b", NUTZER_A)
    assert fremd.status_code in (403, 404), fremd.status_code
    assert "Geheim" not in fremd.text
