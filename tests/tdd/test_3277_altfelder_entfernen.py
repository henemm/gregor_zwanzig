"""#3277: Altfelder aus Modell, Loader, Serialisierung und Renderern entfernen.

SPEC: docs/specs/modules/feat_3277_altfelder_entfernen.md (AC-1 bis AC-10).

Kern-Schicht: echte Dateien in ``tmp_path``, echte Lade-/Speicherfunktionen
(``load_trip``/``save_trip``/``update_trip``, ``load_all_locations``/
``save_location``, ``save_compare_preset_status`` als Python-Speicherpfad
der Ortsvergleiche), echte Renderer und Resolver. Kein ``Mock()``/
``patch()``/``MagicMock``. Nutzerkennungen sind echt und verschieden, nie
``"default"`` (Mandantentrennung, AC-4).

Die Vier-Kanal-Ausgabe (AC-1) laeuft ueber die Bausteine des Golden-Tests
``tests/tdd/test_3237_golden_vier_kanaele.py`` gegen dessen Schnappschuss.
"""
from __future__ import annotations

import copy
import dataclasses
import importlib.util
import inspect
import json
from pathlib import Path

import pytest

from tests.tdd import test_3237_golden_vier_kanaele as golden
from tests.tdd.test_3237_golden_vier_kanaele import _gestellte_uhr, orte_env  # noqa: F401, F811

WURZEL = Path(__file__).resolve().parents[2]

#: Die zehn Altfelder (Spec Scope, ADR-0124 Nr. 6).
ALTFELDER = (
    "channel_layouts", "channel_layouts_per_report", "channel_active_metrics",
    "outlook_metrics", "outlook_metric_formats", "hourly_metrics",
    "hourly_metric_formats", "show_outlook", "multi_day_trend_reports",
    "outlook_enabled",
)

#: Alle zehn Namen gesetzt, je an der Ebene, an der Bestandsdaten sie tragen.
DC_ALT = {
    "channel_layouts": {"email": [{"metric_id": "wind", "enabled": True}]},
    "channel_layouts_per_report": {"evening": {"telegram": [{"metric_id": "thunder"}]}},
    "channel_active_metrics": {"email": ["wind"]},
    "outlook_metrics": [],
    "outlook_metric_formats": {"gust": False},
    "hourly_metrics": ["wind"],
    "hourly_metric_formats": {"wind": True},
    "multi_day_trend_reports": [],
    "show_outlook": False,
    "outlook_enabled": False,
}
RC_ALT = {"show_outlook": False, "multi_day_trend_reports": []}
TOP_ALT = {"outlook_enabled": False, "multi_day_trend_reports": [], "show_outlook": False}

TABELLE = {"version": 1, "rows": [
    {"metric_id": "wind", "places": {"email": True, "telegram": True, "sms": True,
                                     "outlook": True},
     "formats": {"email": "simplified"}},
    {"metric_id": "temperature", "places": {"email": True, "telegram": False, "sms": True,
                                            "outlook": True}},
], "outlook_reports": ["evening"]}

ZUSATZ = {"zusatz_3277": {"bleibt": True}}


def _altnamen_in(daten: dict) -> list[str]:
    """Pfade aller Altfeld-Namen auf oberster Ebene, in ``display_config``
    und ``report_config``."""
    funde = [k for k in ALTFELDER if k in daten]
    for ebene in ("display_config", "report_config"):
        teil = daten.get(ebene) or {}
        funde += [f"{ebene}.{k}" for k in ALTFELDER if k in teil]
    return funde


# ---------------------------------------------------------------------------
# Bausteine: Bestandsdateien mit Altfeldern
# ---------------------------------------------------------------------------

def _trip_datei(root: Path, uid: str, trip_id: str = "trip-3277") -> Path:
    from tests.tdd._einstellung_gleich_mail_trip_fixtures import trip_json

    daten = trip_json(["temperature", "wind", "gust"], trip_id=trip_id,
                      report_config={**RC_ALT, **ZUSATZ},
                      display={"placements": copy.deepcopy(TABELLE),
                               **copy.deepcopy(DC_ALT), **ZUSATZ})
    daten.update(copy.deepcopy(TOP_ALT))
    daten.update(ZUSATZ)
    daten["kind"] = "route"
    pfad = root / "users" / uid / "briefings" / f"{trip_id}.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(daten, ensure_ascii=False, indent=2), encoding="utf-8")
    return pfad


def _vergleich_datei(root: Path, uid: str, preset_id: str = "cp-3277") -> Path:
    daten = {
        "id": preset_id, "name": "Vergleich 3277", "user_id": uid, "kind": "vergleich",
        "location_ids": ["ort-a", "ort-b"], "schedule": "daily", "profil": "ALLGEMEIN",
        "empfaenger": [f"{uid}@example.invalid"], "created_at": "2026-07-01T00:00:00Z",
        "morning_enabled": True, "evening_enabled": False,
        "display_config": {"placements": copy.deepcopy(TABELLE), **copy.deepcopy(DC_ALT),
                           **ZUSATZ},
        **copy.deepcopy(TOP_ALT), **ZUSATZ,
    }
    pfad = root / "users" / uid / "briefings" / f"{preset_id}.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(daten, ensure_ascii=False, indent=2), encoding="utf-8")
    return pfad


def _ort_datei(root: Path, uid: str, ort_id: str = "ort-3277") -> Path:
    daten = {
        "id": ort_id, "name": "Ort 3277", "lat": 47.27, "lon": 11.39, "elevation_m": 600,
        "activity_profile": "allgemein",
        "display_config": {"trip_id": ort_id, "metrics": [
            {"metric_id": "temperature", "enabled": True},
            {"metric_id": "wind", "enabled": True}],
            "placements": copy.deepcopy(TABELLE), **copy.deepcopy(DC_ALT)},
    }
    pfad = root / "users" / uid / "locations" / f"{ort_id}.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(daten, ensure_ascii=False, indent=2), encoding="utf-8")
    return pfad


def _lesen(pfad: Path) -> dict:
    return json.loads(pfad.read_text(encoding="utf-8"))


def _speicher_trip(root: Path, uid: str) -> None:
    from app.loader import load_trip, save_trip

    trip = load_trip("trip-3277", data_dir=root, user_id=uid)
    assert trip is not None
    save_trip(trip, uid, data_dir=root)


def _speicher_vergleich(root: Path, uid: str) -> None:
    from services.scheduler_dispatch_service import save_compare_preset_status

    assert save_compare_preset_status(uid, "cp-3277", "Ort A", data_root=str(root)) is True


# ---------------------------------------------------------------------------
# AC-1: vier Kanaele zeichengleich mit allen zehn Altfeldern
# ---------------------------------------------------------------------------

def _trip_mit_allen_altfeldern(tabelle: dict) -> dict:
    daten = golden._trip_daten(tabelle, alt=True)
    daten["display_config"].update(copy.deepcopy(DC_ALT))
    daten["report_config"].update(copy.deepcopy(RC_ALT))
    daten.update(copy.deepcopy(TOP_ALT))
    return daten


@pytest.mark.parametrize("report_type", ["morning", "evening"])
@pytest.mark.parametrize("name", sorted(golden.TRIP_TABELLEN))
def test_ac1_trip_alle_zehn_altfelder_gleich_golden(monkeypatch, name, report_type):
    ausgabe = golden._trip_ausgabe(
        monkeypatch, _trip_mit_allen_altfeldern(golden.TRIP_TABELLEN[name]), report_type)
    golden._vergleich(f"{name}_{report_type}", ausgabe)


def _orte_ausgabe_alle_altfelder(env: Path, tabelle: dict) -> dict[str, str]:
    """Wie ``golden._orte_ausgabe``, Preset zusaetzlich mit allen zehn Namen."""
    from app.config import Settings
    from app.user import SavedLocation
    from services import placements_beispiel as pb
    from services.scheduler_dispatch_service import send_one_compare_preset
    from tests.tdd.test_compare_premium_sms_versand import _nutzer

    uid = _nutzer("pgold-3237")
    orte = [SavedLocation(id=f"g3237-{i}", name=n, lat=47.27, lon=11.39 + 0.1 * i,
                          elevation_m=600) for i, n in enumerate(("Aabenraa", "Flensburg"))]
    preset = golden._orte_preset(uid, orte, tabelle, alt=True)
    preset["display_config"].update(copy.deepcopy(DC_ALT))
    preset.update(copy.deepcopy(TOP_ALT))
    gesehen: dict[str, list] = {"mail": [], "sms": [], "premium_sms": [], "telegram": []}
    send_one_compare_preset(
        preset, Settings(), uid, str(env), all_locations_cache=orte, target_date=pb.TAG,
        tage_ab_ortstag=0, mail_sink=lambda **k: gesehen["mail"].append(k),
        sms_sink=gesehen["sms"].append, premium_sms_sink=gesehen["premium_sms"].append,
        telegram_sink=gesehen["telegram"].append, report_type="morning",
    )
    assert len(gesehen["mail"]) == 1, gesehen
    mail = gesehen["mail"][0]
    aus = {"mail_html": mail.get("body") or "", "mail_text": mail.get("plain_body") or ""}
    for kanal in ("telegram", "sms", "premium_sms"):
        assert gesehen[kanal], f"Vorbedingung: {kanal} bedient ({gesehen!r})"
        aus[kanal] = "\n---\n".join(str(t) for t in gesehen[kanal])
    return aus


@pytest.mark.parametrize("name", sorted(golden.ORTE_TABELLEN))
def test_ac1_orte_alle_zehn_altfelder_gleich_golden(orte_env, name):  # noqa: F811
    golden._vergleich(name, _orte_ausgabe_alle_altfelder(orte_env, golden.ORTE_TABELLEN[name]))


# ---------------------------------------------------------------------------
# AC-2: Speichern verwirft die zehn Namen, alles andere bleibt
# ---------------------------------------------------------------------------

def test_ac2_save_trip_entfernt_altfelder_und_erhaelt_den_rest(tmp_path):
    uid = "nutzer-a3277"
    pfad = _trip_datei(tmp_path, uid)
    vorher = _lesen(pfad)
    _speicher_trip(tmp_path, uid)
    nachher = _lesen(pfad)
    assert _altnamen_in(nachher) == [], _altnamen_in(nachher)
    assert nachher["zusatz_3277"] == ZUSATZ["zusatz_3277"]
    assert nachher["display_config"]["zusatz_3277"] == ZUSATZ["zusatz_3277"]
    assert nachher["report_config"]["zusatz_3277"] == ZUSATZ["zusatz_3277"]
    assert nachher["display_config"]["placements"] == vorher["display_config"]["placements"]
    assert [s["id"] for s in nachher["stages"]] == [s["id"] for s in vorher["stages"]]


def test_ac2_update_trip_entfernt_altfelder(tmp_path):
    from app.loader import update_trip

    uid = "nutzer-b3277"
    pfad = _trip_datei(tmp_path, uid)
    update_trip(uid, "trip-3277", lambda trip: None, data_dir=tmp_path)
    nachher = _lesen(pfad)
    assert _altnamen_in(nachher) == [], _altnamen_in(nachher)
    assert nachher["zusatz_3277"] == ZUSATZ["zusatz_3277"]


def test_ac2_vergleich_speichern_entfernt_altfelder_und_erhaelt_den_rest(tmp_path):
    uid = "nutzer-c3277"
    pfad = _vergleich_datei(tmp_path, uid)
    vorher = _lesen(pfad)
    _speicher_vergleich(tmp_path, uid)
    nachher = _lesen(pfad)
    assert _altnamen_in(nachher) == [], _altnamen_in(nachher)
    assert nachher["zusatz_3277"] == ZUSATZ["zusatz_3277"]
    assert nachher["display_config"]["zusatz_3277"] == ZUSATZ["zusatz_3277"]
    for feld in ("location_ids", "empfaenger", "name"):
        assert nachher[feld] == vorher[feld], feld
    assert nachher["display_config"]["placements"] == vorher["display_config"]["placements"]
    assert nachher["top_ort_letzter_versand"] == "Ort A"


def test_ac2_save_location_schreibt_keine_altfelder(tmp_path, monkeypatch):
    from app import loader as app_loader

    monkeypatch.setattr(app_loader, "_DATA_ROOT", str(tmp_path))
    uid = "nutzer-d3277"
    pfad = _ort_datei(tmp_path, uid)
    vorher = _lesen(pfad)
    (ort,) = app_loader.load_all_locations(uid)
    app_loader.save_location(ort, uid)
    nachher = _lesen(pfad)
    assert _altnamen_in(nachher) == [], _altnamen_in(nachher)
    assert nachher["display_config"]["placements"] == vorher["display_config"]["placements"]
    assert (nachher["name"], nachher["lat"], nachher["lon"]) == ("Ort 3277", 47.27, 11.39)


# ---------------------------------------------------------------------------
# AC-3: Modell traegt keine Alt-Attribute
# ---------------------------------------------------------------------------

DC_ATTRIBUTE = ("multi_day_trend_reports", "outlook_metrics", "outlook_metric_formats",
                "per_channel_layouts", "per_report_layouts", "show_outlook")
RC_ATTRIBUTE = ("multi_day_trend_reports", "show_outlook")


def test_ac3_geladener_trip_traegt_keine_alt_attribute(tmp_path):
    from app.loader import load_trip

    uid = "nutzer-e3277"
    _trip_datei(tmp_path, uid)
    trip = load_trip("trip-3277", data_dir=tmp_path, user_id=uid)
    vorhanden = [a for a in DC_ATTRIBUTE if hasattr(trip.display_config, a)]
    vorhanden += [f"report_config.{a}" for a in RC_ATTRIBUTE if hasattr(trip.report_config, a)]
    assert vorhanden == [], vorhanden


def test_ac3_modellklassen_haben_keine_altfelder():
    from app.models import TripReportConfig, UnifiedWeatherDisplayConfig

    dc = {f.name for f in dataclasses.fields(UnifiedWeatherDisplayConfig)}
    rc = {f.name for f in dataclasses.fields(TripReportConfig)}
    assert sorted(dc & set(DC_ATTRIBUTE)) == []
    assert sorted(rc & set(RC_ATTRIBUTE)) == []


def test_ac3_geladener_ort_traegt_keine_alt_attribute(tmp_path, monkeypatch):
    from app import loader as app_loader

    monkeypatch.setattr(app_loader, "_DATA_ROOT", str(tmp_path))
    uid = "nutzer-f3277"
    _ort_datei(tmp_path, uid)
    (ort,) = app_loader.load_all_locations(uid)
    vorhanden = [a for a in DC_ATTRIBUTE if hasattr(ort.display_config, a)]
    assert vorhanden == [], vorhanden


# ---------------------------------------------------------------------------
# AC-4: zwei Nutzer, nur A wird bereinigt
# ---------------------------------------------------------------------------

def test_ac4_nur_dateien_von_nutzer_a_werden_bereinigt(tmp_path):
    a, b = "nutzer-a3277x", "nutzer-b3277x"
    dateien = {u: (_trip_datei(tmp_path, u), _vergleich_datei(tmp_path, u)) for u in (a, b)}
    b_vorher = [p.read_bytes() for p in dateien[b]]
    _speicher_trip(tmp_path, a)
    _speicher_vergleich(tmp_path, a)
    for pfad in dateien[a]:
        assert _altnamen_in(_lesen(pfad)) == [], (pfad, _altnamen_in(_lesen(pfad)))
    assert [p.read_bytes() for p in dateien[b]] == b_vorher
    assert not (tmp_path / "users" / "default").exists()


def test_ac4_zugriff_als_default_trifft_keine_nutzerdatei(tmp_path):
    from app.loader import load_trip
    from services.scheduler_dispatch_service import save_compare_preset_status

    a, b = "nutzer-a3277y", "nutzer-b3277y"
    dateien = [_trip_datei(tmp_path, u) for u in (a, b)] + [
        _vergleich_datei(tmp_path, u) for u in (a, b)]
    vorher = [p.read_bytes() for p in dateien]
    assert load_trip("trip-3277", data_dir=tmp_path, user_id="default") is None
    assert save_compare_preset_status("default", "cp-3277", "X",
                                      data_root=str(tmp_path)) is False
    assert [p.read_bytes() for p in dateien] == vorher


# ---------------------------------------------------------------------------
# AC-5: E-Mail-Renderer ohne show_outlook
# ---------------------------------------------------------------------------

def test_ac5_email_renderer_signaturen_ohne_show_outlook():
    from output.renderers.email import render_email
    from output.renderers.email.html import render_html
    from output.renderers.email.plain import render_plain
    from services.report_config_resolver import ReportRenderOptions

    mit = [f.__qualname__ for f in (render_email, render_html, render_plain)
           if "show_outlook" in inspect.signature(f).parameters]
    if "show_outlook" in {f.name for f in dataclasses.fields(ReportRenderOptions)}:
        mit.append("ReportRenderOptions")
    assert mit == [], mit


def _ausblick_in(text: str, html: bool) -> bool:
    hook = _soll_hook()
    return hook.name_im_text(text, hook.ausblick_name("de"), html)


@pytest.mark.parametrize("berichte,erwartet", [(["evening"], True), ([], False)])
def test_ac5_ausblick_folgt_allein_outlook_reports(monkeypatch, berichte, erwartet):
    tabelle = {**copy.deepcopy(TABELLE), "outlook_reports": berichte}
    aus = golden._trip_ausgabe(monkeypatch, golden._trip_daten(tabelle, alt=False), "evening")
    assert _ausblick_in(aus["mail_html"], html=True) is erwartet
    assert _ausblick_in(aus["mail_text"], html=False) is erwartet


# ---------------------------------------------------------------------------
# AC-6: outlook_enabled ohne Lesestelle
# ---------------------------------------------------------------------------

def _soll_hook():
    pfad = WURZEL / ".claude" / "hooks" / "_soll_aus_konfiguration.py"
    spec = importlib.util.spec_from_file_location("_soll_aus_konfiguration_3277", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_ac6_keine_parameter_outlook_enabled():
    from services.channel_list_resolver import resolve_channel_lists
    from services.placements import placements_aus_grundauswahl
    from services.placements_view_service import _Abo

    hook = _soll_hook()
    mit = [f.__name__ for f in (placements_aus_grundauswahl, resolve_channel_lists,
                                hook.ausblick_briefings)
           if "outlook_enabled" in inspect.signature(f).parameters]
    if "outlook_enabled" in {f.name for f in dataclasses.fields(_Abo)}:
        mit.append("_Abo")
    assert mit == [], mit


def _vergleich_ohne_rows(**extra) -> dict:
    return {"id": "cp-ohne", "kind": "vergleich", "morning_enabled": True,
            "evening_enabled": False, "hourly_enabled": True,
            "display_config": {"active_metrics": [
                {"metric_id": "temperature", "aggregation": "max"},
                {"metric_id": "wind", "aggregation": "max"}]}, **extra}


def test_ac6_briefing_ohne_rows_ignoriert_outlook_enabled():
    from services.report_config_resolver import resolve_compare_render_options

    sauber = resolve_compare_render_options(_vergleich_ohne_rows(), report_type="morning")
    alt = resolve_compare_render_options(_vergleich_ohne_rows(outlook_enabled=False),
                                         report_type="morning")
    assert sauber.outlook_enabled is True, "Vorbedingung: Grundauswahl traegt den Ausblick"
    assert (alt.outlook_enabled, alt.outlook_metrics) == (
        sauber.outlook_enabled, sauber.outlook_metrics)


def test_ac6_briefing_mit_rows_unveraendert():
    from services.report_config_resolver import resolve_compare_render_options

    mit = _vergleich_ohne_rows()
    mit["display_config"]["placements"] = copy.deepcopy(TABELLE)
    mit["display_config"]["placements"]["outlook_reports"] = ["morning"]
    sauber = resolve_compare_render_options(mit, report_type="morning")
    alt = resolve_compare_render_options({**mit, "outlook_enabled": True}, report_type="morning")
    assert (alt.outlook_enabled, alt.outlook_metrics) == (
        sauber.outlook_enabled, sauber.outlook_metrics)


def test_ac6_soll_hook_ohne_rows_ignoriert_outlook_enabled():
    hook = _soll_hook()
    sauber = hook.orte_ausblick_briefings(_vergleich_ohne_rows())
    alt = hook.orte_ausblick_briefings(_vergleich_ohne_rows(outlook_enabled=False))
    assert sauber.get("morning") is True, "Vorbedingung: Grundauswahl traegt den Ausblick"
    assert alt == sauber


# ---------------------------------------------------------------------------
# AC-9: Validator-Vorschau bleibt, Request-Felder ohne Store-Bezug
# ---------------------------------------------------------------------------

GOLDEN_3277 = Path(__file__).parents[1] / "fixtures" / "golden_3277"


def _vorschau(**felder) -> str:
    from api.routers.validator import CompareEmailPreviewBody
    from services.validator_render_service import render_compare_email_preview

    body = CompareEmailPreviewBody(profile="allgemein", time_window=[9, 16],
                                   target_date="2026-07-13", **felder)
    return golden._normalisiert(render_compare_email_preview(body))


VORSCHAU_FAELLE = {
    "ohne_felder": {},
    "mit_feldern": {"hourly_metrics": ["t2m_c", "wind10m_kmh"],
                    "hourly_metric_formats": {"wind10m_kmh": True}},
}


@pytest.mark.parametrize("fall", sorted(VORSCHAU_FAELLE))
def test_ac9_validator_vorschau_gleich_bisherigem_stand(fall):
    import os

    html = _vorschau(**VORSCHAU_FAELLE[fall])
    pfad = GOLDEN_3277 / f"validator_vorschau_{fall}.html"
    if os.environ.get("GZ_GOLDEN_3277_AUFNEHMEN") == "1":
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_text(html, encoding="utf-8")
    assert pfad.exists(), f"Schnappschuss fehlt: {pfad}"
    assert html == pfad.read_text(encoding="utf-8")


def test_ac9_request_felder_sind_im_waechter_begruendet_erlaubt():
    from tests import test_altfeld_namen_sperre as waechter

    for datei in ("api/routers/validator.py", "src/services/validator_render_service.py"):
        for name in ("hourly_metrics", "hourly_metric_formats"):
            assert (datei, name) in waechter.ERLAUBT, (datei, name)


# ---------------------------------------------------------------------------
# AC-10: Einmal-Skripte geloescht, Gate-Testmails ueber die Tabelle
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("skript", ["migrate_2454_derived_children.py",
                                    "backfill_display_config_issue111.py"])
def test_ac10_verbrauchte_einmal_skripte_sind_geloescht(skript):
    assert not (WURZEL / "scripts" / skript).exists(), skript


def test_ac10_gate_testmails_ohne_altfeld_namen():
    from tests import test_altfeld_namen_sperre as waechter

    pfad = WURZEL / "scripts" / "send_gate_test_mails.py"
    funde = waechter.verstoesse(pfad.read_text(encoding="utf-8"),
                                "scripts/send_gate_test_mails.py")
    assert funde == [], funde


def test_ac10_gate_testmail_vergleich_baut_weiter_mit_windrichtung():
    spec = importlib.util.spec_from_file_location(
        "send_gate_test_mails_3277", WURZEL / "scripts" / "send_gate_test_mails.py")
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    _betreff, html, plain = gate.build_compare_mail("tok3277")
    assert "Gatehausen Nord" in html and "Gatehausen Nord" in plain
    soll = gate.compare_windrichtung_soll()
    assert soll, "Vorbedingung: Windrichtungs-Soll vorhanden"
