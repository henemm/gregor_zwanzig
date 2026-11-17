"""``placements`` ueber den echten Python-Ladeweg und Fix-Loop-Luecken (#3122 B1a).

SPEC: docs/specs/modules/feat_3122_was_steht_wo.md, Teil A Nr. 1/7/8, AC-14
(Python-Teil). Die Trip-Renderer uebergeben dem Resolver das GELADENE Modell
(``UnifiedWeatherDisplayConfig``); ``placements`` muss deshalb als
undurchsichtiges Roh-Objekt durch Laden und Speichern getragen werden.

Kern-Schicht, echte Dateien unter ``tmp_path``, ohne Mock.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "einstellung_gleich_mail"

PLACEMENTS = {
    "version": 1,
    "rows": [
        {"metric_id": "wind", "places": {"sms": False}, "formats": {"email": "raw"}},
        {"metric_id": "gust", "places": {"telegram": False}},
    ],
    "outlook_reports": ["morning", "evening"],
    "zukunft": {"unbekannt": [1, 2]},
}


def _resolve(dc, surface, report_type="evening", **kw):
    from services.channel_list_resolver import resolve_channel_lists

    return resolve_channel_lists(dc, surface, report_type, **kw)


def _trip_datei(tmp_path, user, trip_id, placements=None):
    roh = json.loads((FIXTURES / "trip_altbestand.json").read_text())
    roh["id"] = trip_id
    dc = roh["display_config"]
    dc["metrics"] = [{"metric_id": m, "enabled": True, "bucket": "primary", "order": i}
                     for i, m in enumerate(["wind", "gust", "precipitation"])]
    if placements is not None:
        dc["placements"] = copy.deepcopy(placements)
    ordner = tmp_path / "users" / user / "briefings"
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / f"{trip_id}.json").write_text(json.dumps(roh))
    return ordner / f"{trip_id}.json"


# ---------------------------------------------------------------------------
# Trip: Laden -> Modell -> Resolver; Speichern ueber den Python-Core
# ---------------------------------------------------------------------------

def test_trip_mit_placements_laden_und_ueber_das_modell_aufloesen(tmp_path):
    from app.loader import load_trip

    _trip_datei(tmp_path, "nutzer-a", "t-lade", PLACEMENTS)
    trip = load_trip("t-lade", data_dir=tmp_path, user_id="nutzer-a")
    assert trip.display_config.placements == PLACEMENTS
    vm = _resolve(trip.display_config, "trip")
    assert [z.metric_id for z in vm.sms] == ["gust", "precipitation"]
    assert [z.metric_id for z in vm.telegram] == ["wind", "precipitation"]
    assert vm.outlook_reports == ("morning", "evening")
    assert vm.hourly == ()


def test_trip_ohne_placements_modell_bleibt_im_bisherigen_pfad(tmp_path):
    from app.loader import load_trip

    _trip_datei(tmp_path, "nutzer-a", "t-alt")
    trip = load_trip("t-alt", data_dir=tmp_path, user_id="nutzer-a")
    assert trip.display_config.placements is None
    vm = _resolve(trip.display_config, "trip")
    assert [z.metric_id for z in vm.sms] == ["wind", "gust", "precipitation"]


def test_trip_speichern_laesst_placements_strukturgleich_und_sonst_alles_gleich(tmp_path):
    from app.loader import load_trip, save_trip

    pfad_mit = _trip_datei(tmp_path, "nutzer-a", "t-mit", PLACEMENTS)
    pfad_ohne = _trip_datei(tmp_path, "nutzer-a", "t-ohne")
    for trip_id in ("t-mit", "t-ohne"):
        save_trip(load_trip(trip_id, data_dir=tmp_path, user_id="nutzer-a"), "nutzer-a",
                  data_dir=tmp_path)
    mit, ohne = json.loads(pfad_mit.read_text()), json.loads(pfad_ohne.read_text())
    assert mit["display_config"].pop("placements") == PLACEMENTS
    for d in (mit, ohne):
        d.pop("id")
        d["display_config"].pop("updated_at", None)
        (d.get("report_config") or {}).pop("updated_at", None)
    assert mit == ohne, "placements darf kein anderes Feld beeinflussen"


def test_trip_speichern_ersetzt_placements_als_ganzes(tmp_path):
    """Kein tiefer Merge: ein im Modell geaenderter Stand ohne
    ``outlook_reports`` laesst keinen Rest vom Plattenstand stehen."""
    from app.loader import load_trip, save_trip

    pfad = _trip_datei(tmp_path, "nutzer-a", "t-neu", PLACEMENTS)
    trip = load_trip("t-neu", data_dir=tmp_path, user_id="nutzer-a")
    neu = {"version": 1, "rows": [{"metric_id": "gust"}]}
    trip.display_config.placements = copy.deepcopy(neu)
    save_trip(trip, "nutzer-a", data_dir=tmp_path)
    assert json.loads(pfad.read_text())["display_config"]["placements"] == neu


def test_trip_speichern_zwei_nutzer_getrennt(tmp_path):
    from app.loader import load_trip, save_trip

    pfad_a = _trip_datei(tmp_path, "nutzer-a", "t-1", PLACEMENTS)
    pfad_b = _trip_datei(tmp_path, "nutzer-b", "t-1")
    vorher_b = pfad_b.read_bytes()
    save_trip(load_trip("t-1", data_dir=tmp_path, user_id="nutzer-a"), "nutzer-a",
              data_dir=tmp_path)
    assert pfad_b.read_bytes() == vorher_b
    assert load_trip("t-1", data_dir=tmp_path, user_id="nutzer-b").display_config.placements is None
    assert json.loads(pfad_a.read_text())["display_config"]["placements"] == PLACEMENTS


# ---------------------------------------------------------------------------
# Orte: Laden ueber den Python-Core laesst placements unveraendert
# ---------------------------------------------------------------------------

def test_orte_laden_traegt_placements_unveraendert(tmp_path):
    from app.loader import compare_preset_to_dict, load_compare_presets
    from services.report_config_resolver import resolve_compare_render_options

    preset = json.loads((FIXTURES / "orte_basis.json").read_text())
    preset["kind"] = "vergleich"
    preset.setdefault("display_config", {})["placements"] = copy.deepcopy(PLACEMENTS)
    for user in ("nutzer-a", "nutzer-b"):
        ordner = tmp_path / "users" / user / "briefings"
        ordner.mkdir(parents=True)
        roh = copy.deepcopy(preset)
        if user == "nutzer-b":
            roh["display_config"].pop("placements")
        (ordner / f"{roh['id']}.json").write_text(json.dumps(roh))
    (geladen,) = load_compare_presets("nutzer-a", data_root=tmp_path)
    assert geladen.display_config["placements"] == PLACEMENTS
    assert compare_preset_to_dict(geladen)["display_config"]["placements"] == PLACEMENTS
    resolve_compare_render_options(compare_preset_to_dict(geladen))
    assert geladen.display_config["placements"] == PLACEMENTS, "Aufloesen mutiert nicht"
    (fremd,) = load_compare_presets("nutzer-b", data_root=tmp_path)
    assert "placements" not in fremd.display_config


# ---------------------------------------------------------------------------
# F1: Trip-Grundauswahl morgens/abends im neuen Eingang
# ---------------------------------------------------------------------------

def test_f1_trip_grundauswahl_je_briefing_typ_im_neuen_eingang():
    dc = {"trip_id": "t-f1", "metrics": [
        {"metric_id": "wind", "enabled": True, "order": 0},
        {"metric_id": "gust", "enabled": True, "order": 1, "morning_enabled": False},
        {"metric_id": "precipitation", "enabled": True, "order": 2, "evening_enabled": False},
    ], "placements": {"rows": [{"metric_id": "precipitation"}, {"metric_id": "gust"},
                               {"metric_id": "wind"}]}}
    morgens = _resolve(dc, "trip", "morning")
    abends = _resolve(dc, "trip", "evening")
    for stelle in ("email", "telegram", "sms"):
        assert [z.metric_id for z in getattr(morgens, stelle)] == ["precipitation", "wind"]
        assert [z.metric_id for z in getattr(abends, stelle)] == ["gust", "wind"]
    assert [z.metric_id for z in morgens.rows] == ["precipitation", "wind"]


# ---------------------------------------------------------------------------
# F2: Wegfall von Altzeilen an gesperrten Stellen wird gemeldet
# ---------------------------------------------------------------------------

def test_f2_wegfall_an_gesperrter_stelle_wird_gemeldet():
    from services.placements import placements_from_legacy

    dc = {"trip_id": "t-f2", "metrics": [
        {"metric_id": "temperature", "enabled": True, "order": 0},
        {"metric_id": "wind", "enabled": True, "order": 1}]}
    arten = {(c.kind, c.stelle, c.metric_id) for c in placements_from_legacy(dc, "trip").changes}
    for kind in ("temperature_night", "temperature_day_low", "temperature_day_high"):
        assert ("gesperrte_stelle_entfaellt", "email", kind) in arten
    assert not any(a[0] == "gesperrte_stelle_entfaellt" and a[2] == "wind" for a in arten)


# ---------------------------------------------------------------------------
# rows im bisherigen Pfad nur auf Anforderung
# ---------------------------------------------------------------------------

def test_altpfad_berechnet_rows_nur_auf_anforderung():
    dc = {"trip_id": "t-r", "metrics": [{"metric_id": "wind", "enabled": True}],
          "channel_layouts": {"sms": [{"metric_id": "wind"}]}}
    ohne = _resolve(dc, "trip")
    assert ohne.rows == () and ohne.outlook_reports == ()
    mit = _resolve(dc, "trip", with_rows=True)
    assert [z.metric_id for z in mit.rows] == ["wind"]
    assert mit.outlook_reports == ("evening",)
    assert (mit.email, mit.sms, mit.outlook) == (ohne.email, ohne.sms, ohne.outlook)
    orte = {"active_metrics": ["wind_max_kmh"]}
    assert _resolve(orte, "compare").rows == ()
    assert [z.metric_id for z in _resolve(orte, "compare", with_rows=True).rows] == ["wind"]


def test_neuer_eingang_setzt_rows_immer():
    dc = {"trip_id": "t-n", "metrics": [{"metric_id": "wind", "enabled": True}],
          "placements": {"rows": []}}
    assert [z.metric_id for z in _resolve(dc, "trip").rows] == ["wind"]
    assert _resolve(dc, "trip").outlook_reports == ("evening",)


# ---------------------------------------------------------------------------
# Kleine Luecken aus der Mutationsprobe
# ---------------------------------------------------------------------------

def test_sperre_keine_eigene_spalte_gilt_nur_beim_trip():
    from app.metric_catalog import stellen_sperre

    assert stellen_sperre("temperature_night", "email", "trip") == "keine_eigene_spalte"
    assert stellen_sperre("temperature_night", "email", "compare") is None


def test_outlook_applies_verlangt_mindestens_eine_metrik():
    from services.placements import StoredRow, outlook_applies, resolve_rows

    an = resolve_rows([StoredRow("wind")], ["wind"], "trip")
    aus = resolve_rows([StoredRow("wind", (("outlook", False),))], ["wind"], "trip")
    assert outlook_applies(an, ("evening",), "evening") is True
    assert outlook_applies(aus, ("evening",), "evening") is False
    assert outlook_applies((), ("evening",), None) is False


def test_read_placements_verwirft_unbekannt_nicht_waehlbar_und_nicht_bool():
    from services.placements import placements_dict, read_placements

    gelesen = read_placements({"rows": [
        {"metric_id": "gibt_es_nicht"},
        {"metric_id": "confidence"},
        {"metric_id": "cape"},
        {"metric_id": "wind", "places": {"email": "ja", "sms": 0, "telegram": False}},
    ]})
    assert placements_dict(gelesen.rows, gelesen.outlook_reports) == {
        "version": 1, "rows": [{"metric_id": "wind", "places": {"telegram": False}}]}


def test_resolve_rows_dedupliziert_die_grundauswahl():
    from services.placements import resolve_rows

    rows = resolve_rows([], ["wind", "gust", "wind"], "trip")
    assert [(z.metric_id, z.position) for z in rows] == [("wind", 0), ("gust", 1)]


@pytest.mark.parametrize("roh,erwartet", [
    ({"rows": []}, ("evening",)),
    ({"rows": [], "outlook_reports": ["noon"]}, ()),
])
def test_festlegungen_leere_zeilen_und_unbekannte_ausblick_werte(roh, erwartet):
    dc = {"trip_id": "t-x", "metrics": [{"metric_id": "wind", "enabled": True}],
          "placements": roh}
    vm = _resolve(dc, "trip")
    assert [z.metric_id for z in vm.sms] == ["wind"]
    assert vm.outlook_reports == erwartet
