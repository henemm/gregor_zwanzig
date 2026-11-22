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


def _grund_ids(dc, surface):
    """Tabellen-Grundauswahl: Abend-Fassung, dahinter nur-morgens-Gewaehltes."""
    from services.channel_list_resolver import grundauswahl

    ids: list[str] = []
    eltern: dict = {}
    for rt in ("evening", "morning"):
        g = grundauswahl(dc, surface, rt)
        ids += [m for m in g.ids if m not in ids]
        eltern = {**g.parents, **eltern}
    return ids, eltern


def _zellen_je_metrik(placements: dict, dc, surface) -> dict:
    from services.placements import read_placements, resolve_rows

    ids, eltern = _grund_ids(dc, surface)
    gelesen = read_placements(placements)
    assert gelesen is not None, f"keine lesbare Tabelle: {placements!r}"
    return {r.metric_id: r.cells for r in resolve_rows(gelesen.rows, ids, surface, parents=eltern)}


def _soll_zellen(dc, surface) -> dict:
    """Grundauswahl-Tabelle: ohne gespeicherte Zeilen = ueberall an, Standardform."""
    from services.placements import resolve_rows

    ids, eltern = _grund_ids(dc, surface)
    return {r.metric_id: r.cells for r in resolve_rows((), ids, surface, parents=eltern)}


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


@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_ac1_ac2_ac10_erstanlage_liefert_volle_tabelle_je_nutzer(placements_client, kind):
    """GIVEN zwei Nutzer mit je einem frisch angelegten Abo (ohne Tabelle)
    WHEN die Go-Anlage den Kern fragt THEN liefert er die volle Tabelle aus
    der Grundauswahl DIESES Nutzers, ohne Begleitfeld ``show_stability_off``
    und ohne etwas zu schreiben; ein fremder Nutzer bekommt 404."""
    if kind == "route":
        _trip(NUTZER_A, "neu3237", rc=_trip_rc_beide())
        _trip(NUTZER_B, "neu3237", grund=["wind", "gust"], rc=_trip_rc_beide())
        surface, enabled = "trip", ("morning", "evening")
    else:
        _orte(NUTZER_A, "neu3237", morgen=True, abend=False)
        _orte(NUTZER_B, "neu3237", grund=ORTE_GRUND[:3], morgen=True, abend=False)
        surface, enabled = "compare", ("morning",)

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
        assert datei.read_bytes() == vorher, "Erstanlage-Abfrage darf nichts schreiben"

    fremd = placements_client.get("/api/briefings/neu3237/placements/erstanlage",
                                  params={"kind": kind, "user_id": "p3237-niemand"})
    assert fremd.status_code == 404


def test_ac4_trip_anlage_tabelle_schaltet_stabilitaet_nicht_ein():
    """GIVEN neuer Trip ohne Stabilitaets-Wunsch WHEN er mit der Anlage-Tabelle
    gespeichert und geladen wird THEN bleibt ``show_stability`` aus."""
    from app.loader import load_trip_from_dict

    dc = _trip_dc(placements=_quelle()(_trip_dc(), "trip"))
    trip = load_trip_from_dict({
        "id": "s3237", "name": "S", "display_config": dc,
        "stages": [{"id": "T1", "name": "E", "date": "2026-07-14", "waypoints": [
            {"id": "W1", "name": "A", "lat": 47.0, "lon": 11.0, "elevation_m": 600}]}],
        "report_config": {"email_format": "full", "send_email": True},
    })
    assert trip.report_config.show_stability is False


# ---------------------------------------------------------------------------
# AC-7: Validator-Endpoint metrics-for-channel
# ---------------------------------------------------------------------------

@pytest.fixture
def validator_client():
    from api.routers import validator

    app = FastAPI()
    app.include_router(validator.router)
    return TestClient(app)


@pytest.mark.parametrize("channel", ["email", "telegram", "sms"])
def test_ac7_metrics_for_channel_quelle_tabelle_oder_grundauswahl(validator_client, channel):
    """GIVEN ein Trip mit Tabelle und einer ohne ``rows`` (mit Altfeldern)
    WHEN ``metrics-for-channel`` gefragt wird THEN ``source`` = ``placements``
    bzw. ``grundauswahl`` und ``metric_ids`` = Metriken der Tabelle an der Stelle."""
    from services.placements import metrics_at, read_placements, resolve_rows

    tabelle = {"version": 1, "rows": [
        {"metric_id": "gust", "places": {"email": True, "telegram": False, "sms": True}},
        {"metric_id": "wind", "places": {"email": True, "telegram": True, "sms": False}},
    ], "outlook_reports": ["evening"]}
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
