"""Ein Vokabular fuer Metrik-Kennungen in Orte-Kanaelen (Issue #3101, Epic #3058).

SPEC: docs/specs/modules/feat_3101_ein_vokabular.md (AC-1 bis AC-8).

Kern-Schicht, ohne Netz, ohne Mock: echte ``display_config``-Dicts durch den
echten ``resolve_channel_lists`` bzw. ``resolve_compare_render_options``; fuer
die Bytegleichheit der vier Kanaele der echte Versandweg
(``send_one_compare_preset`` -> ``NotificationService`` -> Transport-
Mitschrift), Naht nur Wetter und Transport. Die Erwartungen stehen von Hand
im Test.

Vertrag nach #3101 (Variante A): jede Zeile der Orte-Kanallisten
(``email``/``telegram``/``sms``/``premium_sms``, auch die Layout-Kanaele) traegt
``metric_id`` = Katalog-ID (``temperature``) und ``aggregation`` (``max``),
1:1 zu einer Renderer-Zeile. Renderer-Kennungen (``temp_max``) entstehen erst
im Adapter vor dem Renderer: ``compare_metric_ids.renderer_kennung`` und die
Rueckrichtung ``compare_metric_ids.katalog_paar``.

Bytegleichheits-Orakel (AC-4/AC-5): ``tests/fixtures/ein_vokabular_3101/``
haelt den Stand VOR der Umstellung fest (geschrieben mit
``EIN_VOKABULAR_GOLDEN_SCHREIBEN=1`` auf dem Ausgangsstand, danach nie
wieder). Die bestehenden Golden-Dateien in
``tests/fixtures/einstellung_gleich_mail/`` bleiben unberuehrt und werden von
``test_einstellung_gleich_mail_orte.py::test_ac11_altbestand_golden`` geprueft.
"""
from __future__ import annotations

import copy
import json
import os
from datetime import timedelta
from pathlib import Path

import pytest

GOLDEN_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "ein_vokabular_3101"
SCHREIBEN = os.environ.get("EIN_VOKABULAR_GOLDEN_SCHREIBEN") == "1"

#: Renderer-Kennungen, die nach #3101 in keiner Orte-Kanalliste mehr stehen
#: duerfen (von Hand, Auszug aus ``FRONTEND_TO_RENDERER_METRIC_ID``).
RENDERER_KENNUNGEN = {
    "temp_max", "temp_min", "wind_max", "gust_max", "precip_sum", "pop_max",
    "sunny_hours", "cloud_avg", "visibility_min", "uv_max", "humidity_avg",
    "wind_chill_min", "wind_chill_max", "snow_new_cm", "snow_depth_cm",
}

KANAELE = ("email", "telegram", "sms", "premium_sms")


def _am(*paare) -> list[dict]:
    return [{"metric_id": m, "aggregation": a} for m, a in paare]


def _vm(dc, report_type="evening", **kw):
    from services.channel_list_resolver import resolve_channel_lists

    return resolve_channel_lists(dc, "compare", report_type, **kw)


def _paare(vm, kanal) -> list[tuple[str, str]]:
    zeilen = getattr(vm, kanal)
    assert zeilen is not None, f"{kanal}: Vorbedingung, Liste gesetzt"
    return [(z.metric_id, z.aggregation) for z in zeilen if z.enabled]


GRUND_TEMP_WIND = _am(("temperature", "max"), ("temperature", "min"), ("wind", "max"))
SOLL_TEMP_WIND = [("temperature", "max"), ("temperature", "min"), ("wind", "max")]


# ---------------------------------------------------------------------------
# Adapter: (Katalog-ID, Aggregation) <-> Renderer-Kennung
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("katalog_id, aggregation, renderer", [
    ("temperature", "max", "temp_max"),
    ("temperature", "min", "temp_min"),
    ("wind", "max", "wind_max"),
    ("wind_chill", "min", "wind_chill_min"),
    ("wind_chill", "max", "wind_chill_max"),
    ("precipitation", "sum", "precip_sum"),
    ("rain_probability", "max", "pop_max"),
    ("sunshine", "sum", "sunny_hours"),
    ("cloud_total", "avg", "cloud_avg"),
    ("fresh_snow", "sum", "snow_new_cm"),
])
def test_adapter_hin_und_zurueck(katalog_id, aggregation, renderer):
    from output.renderers.compare_metric_ids import katalog_paar, renderer_kennung

    assert renderer_kennung(katalog_id, aggregation) == renderer
    assert katalog_paar(renderer) == (katalog_id, aggregation)


def test_adapter_deckt_den_ganzen_vergleichs_katalog_ab():
    """Jede Zeile des Vergleichs-Katalogs ist eindeutig ueber (Katalog-ID,
    Aggregation) adressierbar -- sonst koennte das View-Model eine
    Renderer-Zeile nicht ausdruecken."""
    from output.renderers.compare_metric_catalog import COMPARE_METRIC_CATALOG
    from output.renderers.compare_metric_ids import (
        FRONTEND_TO_RENDERER_METRIC_ID, katalog_paar, renderer_kennung,
    )

    paare = [(e["metric_id"], e["aggregation"]) for e in COMPARE_METRIC_CATALOG]
    assert len(set(paare)) == len(paare), "Vorbedingung: Paare eindeutig"
    for e in COMPARE_METRIC_CATALOG:
        rid = FRONTEND_TO_RENDERER_METRIC_ID[e["key"]]
        assert renderer_kennung(e["metric_id"], e["aggregation"]) == rid
        assert katalog_paar(rid) == (e["metric_id"], e["aggregation"])


def test_adapter_unbekanntes_paar_ergibt_none():
    from output.renderers.compare_metric_ids import renderer_kennung

    assert renderer_kennung("temperature", "avg") is None
    assert renderer_kennung("gibt_es_nicht", "max") is None


# ---------------------------------------------------------------------------
# AC-1: alle Orte-Kanallisten tragen Katalog-ID + Aggregation
# ---------------------------------------------------------------------------

def _orte_dc_altpfad() -> dict:
    """Bisheriger Pfad ohne Tabelle: Grundauswahl, Telegram per
    ``channel_active_metrics``, SMS per ``channel_layouts`` (Layout-Kanal)."""
    return {
        "active_metrics": GRUND_TEMP_WIND,
        "channel_active_metrics": {"telegram": _am(("wind", "max"), ("temperature", "max"))},
        "channel_layouts": {"sms": [{"metric_id": "temperature"}, {"metric_id": "wind"}]},
    }


def _orte_dc_tabelle() -> dict:
    return {
        "active_metrics": GRUND_TEMP_WIND,
        "placements": {"version": 1, "rows": [
            {"metric_id": "temperature", "places": {"telegram": False}},
            {"metric_id": "wind"},
        ]},
    }


@pytest.mark.parametrize("dc_bauen", [_orte_dc_altpfad, _orte_dc_tabelle],
                         ids=["altpfad", "tabelle"])
def test_ac1_alle_kanallisten_tragen_katalog_ids_samt_aggregation(dc_bauen):
    vm = _vm(dc_bauen())
    for kanal in KANAELE:
        zeilen = getattr(vm, kanal)
        assert zeilen, f"{kanal}: Vorbedingung, Zeilen vorhanden"
        for z in zeilen:
            assert z.metric_id not in RENDERER_KENNUNGEN, (
                f"{kanal}: Renderer-Kennung {z.metric_id!r} im View-Model")
            assert z.aggregation in {"max", "min", "sum", "avg"}, (
                f"{kanal}/{z.metric_id}: Aggregation fehlt ({z.aggregation!r})")
    assert set(vm.layout_channels) <= set(KANAELE)


def test_ac1_altpfad_kanallisten_konkret():
    vm = _vm(_orte_dc_altpfad())
    assert _paare(vm, "email") == SOLL_TEMP_WIND
    assert _paare(vm, "telegram") == [("wind", "max"), ("temperature", "max")]
    assert _paare(vm, "sms") == SOLL_TEMP_WIND
    assert "sms" in vm.layout_channels
    assert _paare(vm, "premium_sms") == _paare(vm, "sms")


def test_ac1_tabelle_kanallisten_konkret():
    vm = _vm(_orte_dc_tabelle())
    assert _paare(vm, "email") == SOLL_TEMP_WIND
    assert _paare(vm, "telegram") == [("wind", "max")]
    assert _paare(vm, "sms") == SOLL_TEMP_WIND
    # Ausblick/Stundenverlauf/rows tragen schon Katalog-IDs (Bestand).
    assert [z.metric_id for z in vm.rows][:2] == ["temperature", "wind"]


# ---------------------------------------------------------------------------
# AC-2: Teilauswahl je Kanal bleibt erhalten
# ---------------------------------------------------------------------------

def test_ac2_sms_nur_hoechstwert_email_beide_altpfad():
    dc = {"active_metrics": GRUND_TEMP_WIND,
          "channel_active_metrics": {"sms": _am(("temperature", "max"))}}
    vm = _vm(dc)
    assert _paare(vm, "sms") == [("temperature", "max")]
    assert _paare(vm, "email") == SOLL_TEMP_WIND


def test_ac2_grundauswahl_nur_hoechstwert_tabelle():
    """Tabellen-Zeile 'temperature' bei einer Grundauswahl nur mit dem
    Hoechstwert: nur die Zeile Temperatur-Maximum."""
    dc = {"active_metrics": _am(("temperature", "max"), ("wind", "max")),
          "placements": {"version": 1, "rows": [{"metric_id": "temperature"}]}}
    vm = _vm(dc)
    assert _paare(vm, "email") == [("temperature", "max"), ("wind", "max")]


def test_ac2_windchill_nur_tiefstwert():
    dc = {"active_metrics": _am(("wind_chill", "min"), ("wind", "max"))}
    vm = _vm(dc)
    assert _paare(vm, "email") == [("wind_chill", "min"), ("wind", "max")]


# ---------------------------------------------------------------------------
# AC-3: Reihenfolge Hoechstwert, Wind, Tiefstwert -- im View-Model und nach
# dem Adapter in den Render-Optionen
# ---------------------------------------------------------------------------

FOLGE = _am(("temperature", "max"), ("wind", "max"), ("temperature", "min"))


def _preset(dc: dict) -> dict:
    return {"id": "p-3101", "display_config": dc, "hourly_enabled": True,
            "morning_enabled": True, "evening_enabled": True}


def test_ac3_reihenfolge_im_view_model():
    dc = {"active_metrics": GRUND_TEMP_WIND, "channel_active_metrics": {"email": FOLGE}}
    vm = _vm(dc)
    assert _paare(vm, "email") == [("temperature", "max"), ("wind", "max"),
                                   ("temperature", "min")]


def test_ac3_reihenfolge_nach_dem_adapter():
    from services.report_config_resolver import resolve_compare_render_options

    dc = {"active_metrics": GRUND_TEMP_WIND, "channel_active_metrics": {"email": FOLGE}}
    opts = resolve_compare_render_options(_preset(dc), report_type="evening")
    assert opts.enabled_metrics_by_channel["email"] == ["temp_max", "wind_max", "temp_min"]
    assert opts.enabled_metrics_by_channel["sms"] == ["temp_max", "temp_min", "wind_max"]


def test_ac3_layout_kanal_nach_dem_adapter_mit_format():
    from services.report_config_resolver import resolve_compare_render_options

    dc = {"active_metrics": GRUND_TEMP_WIND, "channel_layouts": {"telegram": [
        {"metric_id": "wind", "format": "simplified"}, {"metric_id": "temperature"}]}}
    vm = _vm(dc)
    assert _paare(vm, "telegram") == [("wind", "max"), ("temperature", "max"),
                                      ("temperature", "min")]
    opts = resolve_compare_render_options(_preset(dc), report_type="evening")
    assert opts.enabled_metrics_by_channel["telegram"] == ["wind_max", "temp_max", "temp_min"]
    assert opts.channel_rows_by_channel["telegram"] == [
        ("wind_max", True), ("temp_max", False), ("temp_min", False)]


# ---------------------------------------------------------------------------
# AC-6: Alt/Neu-Vergleich -- Max/Min-Doppelzeilen fallen auf eine Katalog-ID
# ---------------------------------------------------------------------------

def test_ac6_katalog_id_der_kanalzeile_ist_die_eigene_kennung():
    """``katalog_id`` wird fuer Orte trivial: die Zeile traegt sie schon."""
    from services.channel_list_resolver import katalog_id, vm_lists

    vm = _vm({"active_metrics": GRUND_TEMP_WIND})
    listen = vm_lists(vm, "compare")
    assert [m for m, _f in listen["email"]] == ["temperature", "temperature", "wind"]
    assert {katalog_id("compare", m) for m, _f in listen["email"]} == {"temperature", "wind"}


def test_ac6_alt_und_neusicht_mit_doppelzeilen_ohne_unterschied():
    """Umrechnung des Altbestands (Max/Min der Temperatur in allen Kanaelen)
    und Neusicht ueber die Tabelle zeigen in keinem Kanal einen Unterschied."""
    from services.placements import placements_from_legacy

    dc = {"active_metrics": GRUND_TEMP_WIND}
    umrechnung = placements_from_legacy(dc, "compare")
    assert [a for a in umrechnung.changes if a.stelle in KANAELE] == []
    neu = _vm({**dc, "placements": umrechnung.placements})
    assert _paare(neu, "email") == SOLL_TEMP_WIND


def test_ac6_gemeldete_aenderung_nennt_die_katalog_id():
    """SMS bisher nur mit dem Hoechstwert: die Umrechnung koppelt beide
    Auswertungen (Spec #3122 Nr. 2) und meldet das -- im einen Vokabular,
    also mit der Katalog-ID, nicht mit ``temp_min``."""
    from services.placements import placements_from_legacy

    dc = {"active_metrics": GRUND_TEMP_WIND,
          "channel_active_metrics": {"sms": _am(("temperature", "max"), ("wind", "max"))}}
    sms = [a for a in placements_from_legacy(dc, "compare").changes if a.stelle == "sms"]
    assert sms, "Vorbedingung: die Kopplung wird gemeldet"
    assert {a.metric_id for a in sms} <= {"temperature", None}, sms


# ---------------------------------------------------------------------------
# AC-7: zwei Nutzer, keine Vermischung
# ---------------------------------------------------------------------------

def test_ac7_zwei_konfigurationen_keine_vermischung():
    from services.report_config_resolver import resolve_compare_render_options

    a = {"active_metrics": _am(("temperature", "max"), ("wind", "max"))}
    b = {"active_metrics": _am(("precipitation", "sum"), ("wind_chill", "min"))}
    vm_a, vm_b = _vm(a), _vm(b)
    assert _paare(vm_a, "email") == [("temperature", "max"), ("wind", "max")]
    assert _paare(vm_b, "email") == [("precipitation", "sum"), ("wind_chill", "min")]
    opts_a = resolve_compare_render_options(_preset(a), report_type="evening")
    opts_b = resolve_compare_render_options(_preset(b), report_type="evening")
    assert opts_a.enabled_metrics_by_channel["email"] == ["temp_max", "wind_max"]
    assert opts_b.enabled_metrics_by_channel["email"] == ["precip_sum", "wind_chill_min"]


# ---------------------------------------------------------------------------
# AC-4: Bytegleichheit Mail (HTML + Klartext), Telegram, SMS, Premium-SMS
# ---------------------------------------------------------------------------

def _golden(name: str) -> Path:
    return GOLDEN_DIR / f"{name}.golden.json"


def _vergleichen(name: str, ist: dict) -> None:
    if SCHREIBEN:
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        _golden(name).write_text(
            json.dumps(ist, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    soll = json.loads(_golden(name).read_text(encoding="utf-8"))
    for teil in sorted(soll):
        assert ist[teil] == soll[teil], f"{name}/{teil} weicht vom Stand vor #3101 ab"
    assert set(ist) == set(soll)


GOLDEN_GRUND = [("temperature", "max"), ("temperature", "min"), ("wind", "max"),
                ("gust", "max"), ("precipitation", "sum"), ("rain_probability", "max"),
                ("sunshine", "sum"), ("cloud_total", "avg"), ("wind_chill", "min")]

#: Konfigurationen mit Teilauswahl, eigener Folge und Format je Kanal.
GOLDEN_FAELLE = {
    "altpfad_kanalauswahl": {
        "active_metrics": _am(*GOLDEN_GRUND),
        "channel_active_metrics": {
            "sms": _am(("temperature", "max"), ("wind", "max"), ("temperature", "min")),
            "telegram": _am(("wind_chill", "min"), ("temperature", "max"), ("gust", "max")),
        },
    },
    "altpfad_layouts": {
        "active_metrics": _am(*GOLDEN_GRUND),
        "channel_layouts": {
            "email": [{"metric_id": "wind", "format": "simplified"},
                      {"metric_id": "temperature"}, {"metric_id": "cloud_total",
                                                     "format": "simplified"}],
            "sms": [{"metric_id": "temperature"}, {"metric_id": "precipitation"},
                    {"metric_id": "wind", "enabled": False}],
        },
    },
    "tabelle": {
        "active_metrics": _am(*GOLDEN_GRUND),
        "placements": {"version": 1, "outlook_reports": ["morning"], "rows": [
            {"metric_id": "gust", "formats": {"telegram": "simplified"}},
            {"metric_id": "temperature", "places": {"sms": False}},
            {"metric_id": "wind_chill"},
            {"metric_id": "cloud_total", "places": {"telegram": False},
             "formats": {"email": "simplified"}},
            {"metric_id": "precipitation"},
            {"metric_id": "wind", "places": {"email": False}},
        ]},
    },
}


@pytest.fixture
def mit(monkeypatch):
    from tests.helpers.transport_mitschrift import aufzeichner_installieren
    from tests.tdd._compare_kette_fixtures import transport_einrichten

    transport_einrichten(monkeypatch)
    return aufzeichner_installieren(monkeypatch)


def _senden(mit, dc: dict) -> dict:
    from app.loader import get_data_root, load_all_locations
    from services.scheduler_dispatch_service import send_one_compare_preset
    from tests.helpers.einstellung_gleich_mail_orte import (
        ZIELTAG, orte_anlegen, preset_dict, wetter_naht,
    )
    from tests.tdd._compare_kette_fixtures import (
        nutzer_anlegen, preset_ablegen, preset_laden, settings_fuer,
    )

    p = preset_dict("basis")
    p["id"] = "orte-3101"
    p["display_config"] = copy.deepcopy(dc)
    p.update(send_telegram=True, send_sms=True, send_premium_sms=True,
             morning_enabled=True, evening_enabled=True,
             alert_channels={"email": True, "telegram": False, "sms": False,
                             "premium_sms": False})
    uid = nutzer_anlegen("premium")
    orte_anlegen(uid)
    preset_ablegen(uid, copy.deepcopy(p))
    mit.leeren()
    with wetter_naht():
        send_one_compare_preset(
            preset_laden(uid, p["id"]), settings_fuer(uid), uid, str(get_data_root()),
            all_locations_cache=load_all_locations(user_id=uid),
            target_date=ZIELTAG, tage_ab_ortstag=0,
        )
    mail = mit.sendungen("email")
    assert len(mail) == 1, f"Vorbedingung: genau eine Mail, {mit!r}"
    aus = {"email_html": mail[0]["body"], "email_text": mail[0]["plain_text_body"]}
    for kanal in ("telegram", "sms", "premium_sms"):
        sendungen = mit.sendungen(kanal)
        assert len(sendungen) == 1, f"Vorbedingung: genau eine {kanal}-Sendung, {mit!r}"
        aus[kanal] = sendungen[0]["body"]
    # Die Nutzerkennung ist je Lauf frisch -- sie ist nicht Teil des Vertrags.
    return {k: v.replace(uid, "<uid>") if isinstance(v, str) else v for k, v in aus.items()}


@pytest.mark.parametrize("name", sorted(GOLDEN_FAELLE))
def test_ac4_vier_kanaele_bytegleich_zum_stand_vor_der_umstellung(mit, name):
    _vergleichen(f"versand_{name}", _senden(mit, GOLDEN_FAELLE[name]))


def test_ac4_bestehende_golden_dateien_unveraendert():
    """Die Golden-Dateien des Pruefkatalogs bleiben, wie sie sind (Inhalt
    geprueft von ``test_ac11_altbestand_golden``)."""
    import hashlib

    ordner = Path(__file__).resolve().parents[1] / "fixtures" / "einstellung_gleich_mail"
    ist = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
           for p in sorted(ordner.glob("*golden*"))}
    if SCHREIBEN:
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        (GOLDEN_DIR / "pruefkatalog_golden.sha256.json").write_text(
            json.dumps(ist, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    soll = json.loads((GOLDEN_DIR / "pruefkatalog_golden.sha256.json").read_text("utf-8"))
    assert ist == soll


# ---------------------------------------------------------------------------
# AC-5: B2b-Tabelle ("Was steht wo") unveraendert
# ---------------------------------------------------------------------------

def _b2b_orte(uid: str, kennung: str, dc: dict) -> None:
    from app.loader import get_data_root

    def schreibe(ordner, k, daten):
        pfad = Path(get_data_root()) / "users" / uid / ordner / f"{k}.json"
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_text(json.dumps(daten), encoding="utf-8")

    ids = []
    for i, name in enumerate(("Innsbruck", "Lienz", "Kufstein")):
        ort_id = f"{kennung}-ort{i}"
        ids.append(ort_id)
        schreibe("locations", ort_id, {"id": ort_id, "name": name, "lat": 47.27 - 0.2 * i,
                                       "lon": 11.39 + 0.3 * i, "elevation_m": 600 + 100 * i})
    schreibe("briefings", kennung, {
        "id": kennung, "name": "Orte " + kennung, "kind": "vergleich", "location_ids": ids,
        "schedule": "daily", "profil": "ALLGEMEIN", "forecast_hours": 48, "empfaenger": [],
        "created_at": "2026-09-01T00:00:00Z", "morning_enabled": True,
        "morning_time": "07:00:00", "evening_enabled": False, "evening_time": "18:00:00",
        "corridors": [], "hourly_enabled": True, "official_alerts_enabled": True,
        "display_config": copy.deepcopy(dc),
    })


@pytest.mark.parametrize("name", sorted(GOLDEN_FAELLE))
def test_ac5_b2b_tabelle_unveraendert(name):
    from services.placements_view_service import build_placements_view

    uid = "nutzer-3101-b2b"
    kennung = f"o-3101-{name.replace('_', '-')}"
    _b2b_orte(uid, kennung, GOLDEN_FAELLE[name])
    antwort = build_placements_view("vergleich", kennung, uid)
    _vergleichen(f"b2b_{name}", json.loads(json.dumps(antwort, ensure_ascii=False)))
