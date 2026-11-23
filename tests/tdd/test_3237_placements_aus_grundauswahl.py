"""#3275/#3237 (B6b-0/B6b-1): EINE Quelle der Tabelle "Was steht wo" ohne Altfelder.

SPEC: docs/specs/modules/feat_3237_altpfad_entfernen.md, AC-1, AC-2, AC-3,
AC-4, AC-7, AC-8, AC-10.

Nutzersicht: ein neues Abo (Trip oder Orts-Vergleich) traegt sofort die
volle Tabelle aus seiner Grundauswahl; ein Abo ohne Tabelle wird ueberall
(Karte, Versand, Validator, Soll-Hook) ueber DIESELBE Grundauswahl-Tabelle
gelesen -- Altfelder (``channel_layouts``, ``outlook_metrics``,
``outlook_metrics_formats``, ``channel_active_metrics``) wirken nicht mehr.

Orakel: die bleibenden Bausteine der Tabelle (``grundauswahl``,
``resolve_rows`` ohne gespeicherte Zeilen = "alles an, Standardform",
``resolve_outlook_reports`` ohne Angabe = Vorbelegung). Kern-Schicht: echte
Dateien in der isolierten Datenwurzel, echte Router, kein Mock.
"""
from __future__ import annotations

import copy
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.tdd.test_placements_tabelle_endpoint import (
    ORTE_GRUND, TRIP_GRUND, _orte, _trip,
)

NUTZER_A, NUTZER_B = "p3237-a", "p3237-b"

#: Widerspruechliche Altfelder: jede davon haette im Altpfad die Ausgabe
#: veraendert (Teilmenge je Kanal, Ausblick aus, andere Form).
TRIP_ALTFELDER = {
    "channel_layouts": {
        "email": [{"metric_id": "wind", "enabled": True}],
        "telegram": [{"metric_id": "gust", "enabled": True}],
        "sms": [{"metric_id": "precipitation", "enabled": True}],
    },
    "channel_layouts_per_report": {"morning": {"email": [{"metric_id": "wind"}]}},
    "outlook_metrics": [],
    "outlook_metric_formats": {"wind": False},
    "channel_active_metrics": {"sms": ["wind"]},
}
ORTE_ALTFELDER = {
    "channel_layouts": {
        "email": [{"metric_id": "wind_max", "enabled": True}],
        "telegram": [{"metric_id": "temp_max", "enabled": True}],
        "sms": [{"metric_id": "gust_max", "enabled": True}],
    },
    "outlook_metrics": ["wind_max"],
    "outlook_metrics_formats": {"wind_max": True},
    "channel_active_metrics": {"email": ["wind_max"]},
    "hourly_metrics": ["wind"],
}


def _quelle():
    from services.placements import placements_aus_grundauswahl

    return placements_aus_grundauswahl


def _trip_dc(grund=TRIP_GRUND, **extra) -> dict:
    dc = {"trip_id": "t", "metrics": [
        {"metric_id": m, "enabled": True, "bucket": "primary", "order": i}
        for i, m in enumerate(grund)]}
    dc.update(copy.deepcopy(extra))
    return dc


def _orte_dc(grund=ORTE_GRUND, **extra) -> dict:
    dc = {"active_metrics": copy.deepcopy(grund)}
    dc.update(copy.deepcopy(extra))
    return dc


#: Feste Soll-Folge der Orte-Grundauswahl ``ORTE_GRUND`` (Kennungen je
#: Metrik, Folge der Orte-Tabelle; keine abgeleiteten Zeilen).
ORTE_GRUND_IDS = [
    "temperature", "wind", "gust", "precipitation", "rain_probability", "sunshine",
    "cloud_total", "humidity", "visibility", "uv_index", "dewpoint", "pressure",
    "freezing_level", "cloud_low", "cloud_mid", "cloud_high", "snowfall_limit",
]


def _grund_ids(dc, surface):
    """Soll-Grundauswahl der Tabelle aus den TESTDATEN, nicht aus dem Code
    (Adversary Lauf 3 F001: der fruehere Spiegel der Produktionsfunktion
    konnte deren Fehler nicht sehen).

    Trip: die Metriken mit Abend-Haken in Eingabefolge, dahinter die
    nur-morgens gewaehlten (``evening_enabled=False``, Morgen an; #3154).
    Orts-Vergleich: feste Folge ``ORTE_GRUND_IDS``. Eltern: keine."""
    if surface == "trip":
        an = [m for m in dc["metrics"] if m.get("enabled", True)]
        abend = [m["metric_id"] for m in an if m.get("evening_enabled", True)]
        nur_morgen = [m["metric_id"] for m in an
                      if not m.get("evening_enabled", True) and m.get("morning_enabled", True)]
        return abend + nur_morgen, {}
    assert dc["active_metrics"] == ORTE_GRUND, "Orakel kennt nur ORTE_GRUND"
    return list(ORTE_GRUND_IDS), {}


def _zellen_je_metrik(placements: dict, dc, surface) -> dict:
    from services.placements import read_placements, resolve_rows

    ids, eltern = _grund_ids(dc, surface)
    gelesen = read_placements(placements)
    assert gelesen is not None, f"keine lesbare Tabelle: {placements!r}"
    return {r.metric_id: r.cells for r in resolve_rows(gelesen.rows, ids, surface, parents=eltern)}


def _heutige_form(surface: str, stelle: str, mid: str) -> str:
    """Form, die ohne Einstellung HEUTE erscheint (Spec #3122 Nr. 4; Korrektur
    /50-implement, red-hinweise.md): Trip-HTML-Mail Ampelgroessen Einfach,
    sonst Katalog-Standard; Ausblick und alle Orte-Stellen Roh."""
    from app.metric_catalog import AMPEL_METRIC_IDS, standard_form

    if surface != "trip" or stelle == "outlook":
        return "raw"
    if stelle == "email" and mid in AMPEL_METRIC_IDS:
        return "simplified"
    return standard_form(mid)


def _soll_zellen(dc, surface) -> dict:
    """Grundauswahl-Tabelle: ueberall an, Form wie heute ohne Einstellung."""
    from services.placements import FORMAT_STELLEN, StoredRow, resolve_rows

    ids, eltern = _grund_ids(dc, surface)
    zeilen = [StoredRow(m, (), tuple((s, _heutige_form(surface, s, m)) for s in FORMAT_STELLEN))
              for m in ids]
    return {r.metric_id: r.cells for r in resolve_rows(zeilen, ids, surface, parents=eltern)}


# ---------------------------------------------------------------------------
# AC-1 / AC-2: volle Tabelle aus der Grundauswahl, eine Quelle
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("surface,dc_fn", [("trip", _trip_dc), ("compare", _orte_dc)])
def test_ac1_ac2_volle_tabelle_aus_grundauswahl(surface, dc_fn):
    """GIVEN die Grundauswahl eines Abos WHEN die Anlage-Tabelle gebildet wird
    THEN je Metrik der Grundauswahl eine Zeile (in deren Folge), jede Stelle
    der Flaeche ausdruecklich belegt, Zustaende/Formen = Grundauswahl-Tabelle."""
    from services.placements import stellen_fuer

    dc = dc_fn()
    placements = _quelle()(dc, surface)

    assert placements["version"] == 1
    ids, _eltern = _grund_ids(dc, surface)
    assert [r["metric_id"] for r in placements["rows"]] == ids
    for zeile in placements["rows"]:
        assert set(zeile.get("places", {})) == set(stellen_fuer(surface)), zeile
        assert all(isinstance(v, bool) for v in zeile["places"].values()), zeile
    assert _zellen_je_metrik(placements, dc, surface) == _soll_zellen(dc, surface)


@pytest.mark.parametrize("surface,enabled,erwartet", [
    ("trip", None, ["evening"]),
    ("trip", ("morning",), ["morning"]),
    ("trip", ("morning", "evening"), ["evening"]),
    ("compare", ("morning",), ["morning"]),
    ("compare", ("evening",), ["evening"]),
])
def test_ac1_outlook_reports_nach_vorbelegung(surface, enabled, erwartet):
    """``outlook_reports`` steht ausdruecklich in der Tabelle (Vorbelegung Nr. 6)."""
    dc = _trip_dc() if surface == "trip" else _orte_dc()
    placements = _quelle()(dc, surface, enabled_reports=enabled)
    assert placements["outlook_reports"] == erwartet


def test_ac2_orte_ausblick_ausgeschaltet_ergibt_leere_briefings():
    """Orte mit ``outlook_enabled=false`` bei der Anlage: Ausblick aus (``[]``),
    wie bisher die Anlage-Marke der Go-Anlage (#3155)."""
    placements = _quelle()(_orte_dc(), "compare", enabled_reports=("morning",),
                           outlook_enabled=False)
    assert placements["outlook_reports"] == []


@pytest.mark.parametrize("surface,dc_fn,alt", [
    ("trip", _trip_dc, TRIP_ALTFELDER), ("compare", _orte_dc, ORTE_ALTFELDER),
])
def test_ac3_altfelder_wirken_nicht_auf_die_quelle(surface, dc_fn, alt):
    """GIVEN widerspruechliche Altfelder WHEN die Tabelle gebildet wird THEN
    ist sie identisch zur Tabelle ohne Altfelder."""
    sauber = _quelle()(dc_fn(), surface, enabled_reports=("morning", "evening"))
    mit_alt = _quelle()(dc_fn(**alt), surface, enabled_reports=("morning", "evening"))
    assert mit_alt == sauber


def test_quelle_veraendert_die_eingabe_nicht():
    dc = _trip_dc(**TRIP_ALTFELDER)
    vorher = copy.deepcopy(dc)
    _quelle()(dc, "trip")
    assert dc == vorher


# ---------------------------------------------------------------------------
# AC-3: Lesepfad ohne ``rows`` -- Versand (Resolver) und Karte
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("surface,dc_fn,alt", [
    ("trip", _trip_dc, TRIP_ALTFELDER), ("compare", _orte_dc, ORTE_ALTFELDER),
])
@pytest.mark.parametrize("report_type", ["morning", "evening"])
def test_ac3_versandweg_ohne_rows_liest_grundauswahl_tabelle(surface, dc_fn, alt, report_type):
    """GIVEN Abo ohne ``rows`` mit Altfeldern WHEN der Versand die Kanal-Listen
    aufloest THEN gleich der Aufloesung mit der Grundauswahl-Tabelle."""
    from services.channel_list_resolver import resolve_channel_lists

    alt_dc = dc_fn(**alt)
    mit_tabelle = dc_fn(placements=_quelle()(dc_fn(), surface,
                                             enabled_reports=("morning", "evening")))
    ist = resolve_channel_lists(alt_dc, surface, report_type,
                                enabled_reports=("morning", "evening"))
    soll = resolve_channel_lists(mit_tabelle, surface, report_type,
                                 enabled_reports=("morning", "evening"))
    for feld in ("email", "telegram", "sms", "premium_sms", "outlook", "hourly"):
        assert getattr(ist, feld) == getattr(soll, feld), feld


@pytest.fixture
def placements_client():
    from api.routers import placements

    app = FastAPI()
    app.include_router(placements.router)
    return TestClient(app)


def _trip_rc_beide() -> dict:
    return {"morning_enabled": True, "evening_enabled": True, "send_email": True}


@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_ac3_karte_ohne_rows_zeigt_grundauswahl_tabelle(placements_client, kind):
    """GIVEN Abo ohne ``rows`` mit Altfeldern WHEN die Karte gelesen wird THEN
    traegt die Antwort die Grundauswahl-Tabelle und jede Kanal-Zelle ist an."""
    if kind == "route":
        _trip(NUTZER_A, "k3237", rc=_trip_rc_beide())
        pfad_dc = TRIP_ALTFELDER
    else:
        _orte(NUTZER_A, "k3237", morgen=True, abend=False)
        pfad_dc = ORTE_ALTFELDER
    datei = _datei(NUTZER_A, "k3237")
    daten = json.loads(datei.read_text())
    daten["display_config"].update(copy.deepcopy(pfad_dc))
    datei.write_text(json.dumps(daten))

    antwort = placements_client.get("/api/briefings/k3237/placements",
                                    params={"kind": kind, "user_id": NUTZER_A})
    assert antwort.status_code == 200, antwort.text
    body = antwort.json()
    surface = "trip" if kind == "route" else "compare"
    enabled = ("morning", "evening") if kind == "route" else ("morning",)
    sauber = {k: v for k, v in daten["display_config"].items() if k not in pfad_dc}
    assert body["stored"] is False
    assert body["placements"] == _quelle()(sauber, surface, enabled_reports=enabled)
    for zeile in body["rows"]:
        for stelle in ("email", "telegram", "sms"):
            assert zeile["cells"][stelle]["state"] in ("on", "locked"), (zeile["metric_id"], stelle)


# ---------------------------------------------------------------------------
# AC-1/AC-2/AC-4/AC-10: Anlage-Endpunkt fuer die Go-Anlage
# ---------------------------------------------------------------------------

def _datei(user: str, kennung: str):
    from pathlib import Path

    from app.loader import get_data_root

    return Path(get_data_root()) / "users" / user / "briefings" / f"{kennung}.json"


def _trip_rc_nur_morgen() -> dict:
    return {"morning_enabled": True, "evening_enabled": False, "send_email": True}


@pytest.mark.parametrize("fall", ["route", "route_nur_morgen", "vergleich"])
def test_ac1_ac2_ac10_erstanlage_liefert_volle_tabelle_je_nutzer(placements_client, fall):
    """GIVEN zwei Nutzer mit je einem frisch angelegten Abo (ohne Tabelle)
    WHEN die Go-Anlage den Kern fragt THEN liefert er die volle Tabelle aus
    der Grundauswahl DIESES Nutzers, ohne Begleitfeld ``show_stability_off``
    und ohne etwas zu schreiben; ein fremder Nutzer bekommt 404.

    Ausblick-Vorbelegung (``resolve_outlook_reports``): Abend, ist nur das
    Morgen-Briefing eingeschaltet, Morgen -- fuer Trip (``route_nur_morgen``,
    Adversary Lauf 2 F003) wie Orts-Vergleich."""
    kind = "vergleich" if fall == "vergleich" else "route"
    if fall in ("route", "route_nur_morgen"):
        rc = _trip_rc_beide() if fall == "route" else _trip_rc_nur_morgen()
        _trip(NUTZER_A, "neu3237", rc=rc)
        _trip(NUTZER_B, "neu3237", grund=["wind", "gust"], rc=rc)
        surface = "trip"
        enabled = ("morning", "evening") if fall == "route" else ("morning",)
        ausblick = ["evening"] if fall == "route" else ["morning"]
    else:
        _orte(NUTZER_A, "neu3237", morgen=True, abend=False)
        _orte(NUTZER_B, "neu3237", grund=ORTE_GRUND[:3], morgen=True, abend=False)
        surface, enabled = "compare", ("morning",)
        ausblick = ["morning"]

    for nutzer in (NUTZER_A, NUTZER_B):
        datei = _datei(nutzer, "neu3237")
        vorher = datei.read_bytes()
        antwort = placements_client.get("/api/briefings/neu3237/placements/erstanlage",
                                        params={"kind": kind, "user_id": nutzer})
        assert antwort.status_code == 200, antwort.text
        body = antwort.json()
        assert "show_stability_off" not in body
        dc = json.loads(vorher)["display_config"]
        assert body["placements"] == _quelle()(dc, surface, enabled_reports=enabled)
        assert body["placements"]["outlook_reports"] == ausblick, body["placements"]
        assert datei.read_bytes() == vorher, "Erstanlage-Abfrage darf nichts schreiben"

    fremd = placements_client.get("/api/briefings/neu3237/placements/erstanlage",
                                  params={"kind": kind, "user_id": "p3237-niemand"})
    assert fremd.status_code == 404


@pytest.mark.parametrize("outlook_enabled,ausblick", [
    (False, []),
    (True, ["morning"]),
])
def test_ac2_erstanlage_vergleich_folgt_ausblick_schalter(
        placements_client, outlook_enabled, ausblick):
    """GIVEN ein Orts-Vergleich-Abo (nur Morgen) mit ``outlook_enabled``
    WHEN die Go-Anlage den Kern-Endpunkt ``.../placements/erstanlage`` fragt
    THEN traegt die Tabelle ``outlook_reports == []`` bei ausgeschaltetem
    Ausblick, sonst die Vorbelegung ``["morning"]``.

    Adversary Lauf 4 F001: der Schalter muss vom Abo bis in die Antwort
    durchgereicht werden (``outlook_enabled=None`` hiesse Vorbelegung).
    Trip-Abos kennen keinen eigenen Ausblick-Schalter."""
    _orte(NUTZER_A, "aus3237", morgen=True, abend=False,
          extra={"outlook_enabled": outlook_enabled})
    antwort = placements_client.get("/api/briefings/aus3237/placements/erstanlage",
                                    params={"kind": "vergleich", "user_id": NUTZER_A})
    assert antwort.status_code == 200, antwort.text
    placements = antwort.json()["placements"]
    assert placements["outlook_reports"] == ausblick, placements
    assert placements["rows"], "Tabelle muss Zeilen tragen"


# Adversary Lauf 5 F002: die Fehlerabbildung des Erstanlage-Wegs ist dort
# bewacht, wo sie wirkt (am Endpunkt, den die Go-Anlage ruft), nicht nur an der
# Karte. Unbekannte Art = 400 ``kind_required``; ungueltige Kennung oder
# ungueltige ``user_id`` = 404 ``not_found`` (kein Serverfehler, kein Pfadbau).
ERSTANLAGE_3237 = "/api/briefings/{kennung}/placements/erstanlage"


@pytest.mark.parametrize("params", [
    {"user_id": NUTZER_A},
    {"user_id": NUTZER_A, "kind": ""},
    {"user_id": NUTZER_A, "kind": "irgendwas"},
    {"user_id": NUTZER_A, "kind": "ROUTE"},
], ids=["fehlt", "leer", "unbekannt", "grossgeschrieben"])
def test_f002_erstanlage_ohne_gueltige_art_ist_400(placements_client, params):
    _trip(NUTZER_A, "k3237")
    antwort = placements_client.get(ERSTANLAGE_3237.format(kennung="k3237"), params=params)
    assert antwort.status_code == 400, antwort.text
    assert antwort.json()["code"] == "kind_required", antwort.json()


@pytest.mark.parametrize("kind", ["route", "vergleich"])
@pytest.mark.parametrize("kennung", ["%2E%2E", "x" * 300, "x" * 5000],
                         ids=["punktpunkt", "lang300", "lang5000"])
def test_f002_erstanlage_ungueltige_kennung_ist_404(placements_client, kind, kennung):
    antwort = placements_client.get(ERSTANLAGE_3237.format(kennung=kennung),
                                    params={"kind": kind, "user_id": NUTZER_A})
    assert antwort.status_code == 404, (kind, len(kennung), antwort.text)
    assert antwort.json()["code"] == "not_found", antwort.json()


@pytest.mark.parametrize("kind", ["route", "vergleich"])
@pytest.mark.parametrize("user_id", ["../p3237-a", "p3237 a", "p3237.a"],
                         ids=["pfad", "leerzeichen", "punkt"])
def test_f002_erstanlage_ungueltige_user_id_ist_404(placements_client, kind, user_id):
    _trip(NUTZER_A, "k3237")
    _orte(NUTZER_A, "k3237o")
    kennung = "k3237" if kind == "route" else "k3237o"
    antwort = placements_client.get(ERSTANLAGE_3237.format(kennung=kennung),
                                    params={"kind": kind, "user_id": user_id})
    assert antwort.status_code == 404, (kind, user_id, antwort.text)
    assert antwort.json()["code"] == "not_found", antwort.json()


@pytest.mark.parametrize("rc", [
    {"email_format": "full", "send_email": True},
    {"email_format": "full", "send_email": True, "show_stability": False},
    # #3237 F002 (AC-4/AC-6): der Haken "Grosswetterlage" schreibt show_stability;
    # das Altfeld show_outlook hat mit Tabelle keine Wirkung, in keiner Richtung.
    {"email_format": "full", "send_email": True, "show_stability": True, "show_outlook": False},
    {"email_format": "full", "send_email": True, "show_stability": False, "show_outlook": True},
], ids=["ohne_wunsch", "stabilitaet_aus", "stabilitaet_an_altfeld_aus", "stabilitaet_aus_altfeld_an"])
def test_ac4_trip_anlage_tabelle_aendert_grosswetterlage_nicht(rc):
    """GIVEN neuer Trip (mit bzw. ohne Stabilitaets-Wunsch) WHEN er mit der
    Anlage-Tabelle gespeichert, geladen und das Briefing erzeugt wird THEN
    zeigt die Mail die Grosswetterlage genau wie vor #3237: ohne Wunsch
    sichtbar (Loader-Standard ``show_stability=True``, ``show_outlook``
    unveraendert ``True`` -- vorher galt ``show_outlook and show_stability``),
    mit ``show_stability: false`` nicht. Die Tabelle schaltet nichts um."""
    from app.loader import load_trip_from_dict
    from app.models import StabilityResult
    from output.renderers.email.html import render_stability_label_html
    from output.renderers.trip_report import TripReportFormatter
    from tests.helpers.briefing_html_sprache_fixture import TZ, _nacht, _segment

    dc = _trip_dc(placements=_quelle()(_trip_dc(), "trip"))
    trip = load_trip_from_dict({
        "id": "s3237", "name": "S", "display_config": dc,
        "stages": [{"id": "T1", "name": "E", "date": "2026-07-14", "waypoints": [
            {"id": "W1", "name": "A", "lat": 47.0, "lon": 11.0, "elevation_m": 600}]}],
        "report_config": rc,
    })
    stabil = StabilityResult(label="WECHSELHAFT", confidence_pct=60)
    html = TripReportFormatter().format_email(
        [_segment()], "S", "evening", display_config=trip.display_config,
        report_config=trip.report_config, night_weather=_nacht(),
        stability_result=stabil, tz=TZ,
    ).email_html
    soll = rc.get("show_stability", True)
    assert trip.report_config.show_stability is soll
    assert (render_stability_label_html(stabil) in html) is soll


# ---------------------------------------------------------------------------
# AC-7: Validator-Endpoint metrics-for-channel
# ---------------------------------------------------------------------------

@pytest.fixture
def validator_client():
    from api.routers import validator

    app = FastAPI()
    app.include_router(validator.router)
    return TestClient(app)


@pytest.mark.parametrize("channel", ["email", "telegram", "sms", "outlook"])
def test_ac7_metrics_for_channel_quelle_tabelle_oder_grundauswahl(validator_client, channel):
    """GIVEN ein Trip mit Tabelle und einer ohne ``rows`` (mit Altfeldern)
    WHEN ``metrics-for-channel`` gefragt wird THEN ``source`` = ``placements``
    bzw. ``grundauswahl`` und ``metric_ids`` = Metriken der Tabelle an der Stelle.

    Adversary Lauf 3 F002: ``outlook`` ist eine eigene Spalte; die Tabelle
    weicht dort von der E-Mail ab (gust nicht im Ausblick), die Antwort muss
    der Ausblick-Spalte folgen, nicht der E-Mail-Liste."""
    from services.placements import metrics_at, read_placements, resolve_rows

    tabelle = {"version": 1, "rows": [
        {"metric_id": "gust",
         "places": {"email": True, "telegram": False, "sms": True, "outlook": False}},
        {"metric_id": "wind",
         "places": {"email": True, "telegram": True, "sms": False, "outlook": True}},
    ], "outlook_reports": ["evening"]}
    # Feste Erwartung je Spalte fuer die zwei gespeicherten Zeilen (die
    # uebrigen Grundauswahl-Metriken ohne gespeicherte Zeile sind ueberall an).
    fest = {"email": {"gust": True, "wind": True}, "telegram": {"gust": False, "wind": True},
            "sms": {"gust": True, "wind": False}, "outlook": {"gust": False, "wind": True}}
    _trip(NUTZER_A, "v-tab", placements=tabelle)
    _trip(NUTZER_A, "v-alt")
    alt = _datei(NUTZER_A, "v-alt")
    daten = json.loads(alt.read_text())
    daten["display_config"].update(copy.deepcopy(TRIP_ALTFELDER))
    alt.write_text(json.dumps(daten))

    for kennung, quelle, placements in (
        ("v-tab", "placements", tabelle),
        ("v-alt", "grundauswahl", _quelle()(_trip_dc(), "trip")),
    ):
        antwort = validator_client.get("/api/_validator/metrics-for-channel", params={
            "trip": kennung, "channel": channel, "report": "evening", "user_id": NUTZER_A})
        assert antwort.status_code == 200, antwort.text
        body = antwort.json()
        ids, eltern = _grund_ids(_trip_dc(), "trip")
        rows = resolve_rows(read_placements(placements).rows, ids, "trip", parents=eltern)
        assert body == {"source": quelle,
                        "metric_ids": [m for m, _f in metrics_at(rows, channel)]}, kennung
        if kennung == "v-tab":
            # Feste Werte je Spalte (nicht aus demselben Code abgeleitet).
            for mid, drin in fest[channel].items():
                assert (mid in body["metric_ids"]) is drin, (channel, mid, body)


# ---------------------------------------------------------------------------
# Adversary Lauf 3 F001: Groesse nur fuer das Morgen-Briefing (AC-1/AC-3/AC-7)
# ---------------------------------------------------------------------------

#: Grundauswahl mit ``wind`` nur morgens: die Tabelle traegt die Abend-Fassung,
#: dahinter die nur-morgens gewaehlte Groesse (#3154) -- feste Soll-Folge.
TRIP_MORGEN_ONLY_IDS = [m for m in TRIP_GRUND if m != "wind"] + ["wind"]


def _trip_dc_wind_nur_morgen() -> dict:
    dc = _trip_dc()
    for m in dc["metrics"]:
        if m["metric_id"] == "wind":
            m["morning_enabled"], m["evening_enabled"] = True, False
    return dc


def _trip_wind_nur_morgen(user: str, kennung: str):
    _trip(user, kennung, rc=_trip_rc_beide())
    datei = _datei(user, kennung)
    daten = json.loads(datei.read_text())
    daten["display_config"] = {**daten["display_config"],
                               "metrics": _trip_dc_wind_nur_morgen()["metrics"]}
    datei.write_text(json.dumps(daten))


def test_f001_anlage_tabelle_enthaelt_morgen_only_groesse():
    """GIVEN Trip-Grundauswahl mit ``wind`` nur morgens (``evening_enabled=False``)
    WHEN die Anlage-Tabelle gebildet wird THEN steht ``wind`` als Zeile darin
    (am Ende, nach der Abend-Fassung), mit Haken an allen Kanal-Stellen."""
    placements = _quelle()(_trip_dc_wind_nur_morgen(), "trip",
                           enabled_reports=("morning", "evening"))
    assert [r["metric_id"] for r in placements["rows"]] == TRIP_MORGEN_ONLY_IDS
    wind = next(r for r in placements["rows"] if r["metric_id"] == "wind")
    for stelle in ("email", "telegram", "sms"):
        assert wind["places"][stelle] is True, (stelle, wind)


@pytest.mark.parametrize("pfad", ["karte", "erstanlage"])
def test_f001_karte_und_erstanlage_zeigen_morgen_only_groesse(placements_client, pfad):
    """GIVEN gespeicherter Trip ohne Tabelle mit ``wind`` nur morgens WHEN die
    Karte bzw. die Go-Anlage den Kern fragt THEN enthaelt die Tabelle (und
    die Karten-Zeilen) ``wind``."""
    _trip_wind_nur_morgen(NUTZER_A, "mo3237")
    url = "/api/briefings/mo3237/placements" + ("/erstanlage" if pfad == "erstanlage" else "")
    antwort = placements_client.get(url, params={"kind": "route", "user_id": NUTZER_A})
    assert antwort.status_code == 200, antwort.text
    body = antwort.json()
    assert [r["metric_id"] for r in body["placements"]["rows"]] == TRIP_MORGEN_ONLY_IDS
    if pfad == "karte":
        assert body["stored"] is False
        assert [z["metric_id"] for z in body["rows"]] == TRIP_MORGEN_ONLY_IDS
        wind = next(z for z in body["rows"] if z["metric_id"] == "wind")
        for stelle in ("email", "telegram", "sms"):
            assert wind["cells"][stelle]["state"] in ("on", "locked"), (stelle, wind)


@pytest.mark.parametrize("channel", ["email", "telegram", "sms"])
def test_f001_metrics_for_channel_enthaelt_morgen_only_groesse(validator_client, channel):
    """GIVEN Trip ohne Tabelle mit ``wind`` nur morgens WHEN ``metrics-for-channel``
    gefragt wird THEN ``source=grundauswahl`` und ``wind`` steht in ``metric_ids``
    (E-Mail: die volle feste Folge)."""
    _trip_wind_nur_morgen(NUTZER_A, "mo3237v")
    antwort = validator_client.get("/api/_validator/metrics-for-channel", params={
        "trip": "mo3237v", "channel": channel, "report": "morning", "user_id": NUTZER_A})
    assert antwort.status_code == 200, antwort.text
    body = antwort.json()
    assert body["source"] == "grundauswahl"
    assert "wind" in body["metric_ids"], body
    if channel == "email":
        assert body["metric_ids"] == TRIP_MORGEN_ONLY_IDS, body


def test_ac7_f006_premium_sms_folgt_sms_unbekannter_kanal_422(validator_client):
    """Adversary Lauf 2 F006: GIVEN ein Trip mit Tabelle (SMS-Spalte weicht von
    E-Mail ab) WHEN ``metrics-for-channel`` fuer ``premium_sms`` gefragt wird
    THEN dieselbe Liste wie fuer ``sms`` (ADR-0049, keine eigene Spalte);
    ein Kanal ohne Tabellenspalte ergibt 422 statt einer leeren Liste."""
    tabelle = {"version": 1, "rows": [
        {"metric_id": "gust", "places": {"email": True, "telegram": False, "sms": True}},
        {"metric_id": "wind", "places": {"email": True, "telegram": True, "sms": False}},
    ], "outlook_reports": ["evening"]}
    _trip(NUTZER_A, "v-prem", placements=tabelle)

    def frage(channel):
        return validator_client.get("/api/_validator/metrics-for-channel", params={
            "trip": "v-prem", "channel": channel, "report": "evening", "user_id": NUTZER_A})

    sms, premium = frage("sms"), frage("premium_sms")
    assert sms.status_code == 200 and premium.status_code == 200, (sms.text, premium.text)
    assert "gust" in sms.json()["metric_ids"] and "wind" not in sms.json()["metric_ids"]
    assert premium.json() == sms.json()

    for unbekannt in ("signal", "hourly", "SMS", ""):
        antwort = frage(unbekannt)
        assert antwort.status_code == 422, (unbekannt, antwort.status_code, antwort.text)


# ---------------------------------------------------------------------------
# AC-8: Validator-Soll-Hook liest ohne Altzweige die Tabelle / Grundauswahl
# ---------------------------------------------------------------------------

def _soll_modul():
    import importlib
    import sys
    from pathlib import Path

    hooks = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
    if str(hooks) not in sys.path:
        sys.path.insert(0, str(hooks))
    return importlib.import_module("_soll_aus_konfiguration")


def _orte_preset(dc: dict) -> dict:
    return {"id": "s3237", "name": "S", "kind": "vergleich", "location_ids": [],
            "morning_enabled": True, "evening_enabled": False, "hourly_enabled": True,
            "display_config": dc}


def test_ac8_orte_soll_ohne_rows_folgt_grundauswahl_nicht_altfeldern():
    soll = _soll_modul()
    ohne_rows = soll.orte_soll(_orte_preset(_orte_dc(**ORTE_ALTFELDER)))
    mit_tabelle = soll.orte_soll(_orte_preset(_orte_dc(
        placements=_quelle()(_orte_dc(), "compare", enabled_reports=("morning",)))))
    assert ohne_rows == mit_tabelle


def test_ac8_orte_soll_mit_tabelle_ignoriert_altfelder():
    soll = _soll_modul()
    tabelle = _quelle()(_orte_dc(), "compare", enabled_reports=("morning",))
    tabelle["rows"][0]["places"]["email"] = False
    sauber = soll.orte_soll(_orte_preset(_orte_dc(placements=tabelle)))
    mit_alt = soll.orte_soll(_orte_preset(_orte_dc(placements=tabelle, **ORTE_ALTFELDER)))
    assert mit_alt == sauber


@pytest.mark.parametrize("report", ["morning", "evening"])
def test_ac8_trip_soll_ohne_rows_folgt_grundauswahl_nicht_altfeldern(report):
    soll = _soll_modul()

    def trip(dc):
        return {"id": "s3237", "name": "S", "display_config": dc, "stages": [],
                "report_config": {"email_format": "full", "send_email": True}}

    ohne_rows = soll.trip_soll(trip(_trip_dc(**TRIP_ALTFELDER)), report)
    mit_tabelle = soll.trip_soll(trip(_trip_dc(placements=_quelle()(_trip_dc(), "trip"))), report)
    assert ohne_rows == mit_tabelle
