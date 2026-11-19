"""Kanonische Kanal-Liste und Resolver (Issue #3057, Phase 2a von Epic #3047, ADR-0121).

SPEC: docs/specs/modules/feat_3057_kanal_liste_resolver.md (AC-1..AC-9).

Kern-Schicht, deterministisch, ohne Netz, ohne ``Mock()``/``patch()``: echte
``display_config``-Dicts, der echte Loader-Parser und die echten Primitive.
Erwartungen kommen aus dem Altpfad-Orakel ``tests/helpers/kanal_liste_orakel.py``
(eingefrorene Kopie der Aufloesung vor #3057), nie aus dem Resolver selbst.

Vertrag des Resolvers, den diese Tests festlegen:

* ``resolve_channel_lists(display_config, surface, report_type=None)`` mit
  ``surface`` ``"trip"`` oder ``"compare"``. Trip nimmt das Modell
  ``UnifiedWeatherDisplayConfig`` ODER die Rohform (Dict wie gespeichert),
  Orte das rohe ``display_config``-Dict eines Presets.
* Rueckgabe ``MailViewModel`` (eingefroren) mit den Attributen ``email``,
  ``telegram``, ``sms``, ``premium_sms``; je Kanal ein ``tuple`` von
  ``ChannelRow(metric_id, enabled, format, order)`` in Anzeigefolge, oder
  ``None`` = "kein Filter" (nur Orte ohne Grundauswahl und ohne Kanal-Liste,
  heute ``enabled_metrics_by_channel[kanal] is None``).
* ``format`` in ``raw | simplified | None``; ``None`` = Standard der Flaeche
  (Trip Katalog-Standard, Orte Roh). Gelesen aus ``format`` vor
  ``format_mode`` vor ``use_friendly_format``.
* Gezeigt wird eine Zeile genau dann, wenn ``enabled`` wahr ist; der
  Resolver darf abgewaehlte Zeilen mitfuehren (fuer den Editor), sie zaehlen
  nicht zur Auswahl.

RED heute: ``services.channel_list_resolver`` existiert nicht.
"""
from __future__ import annotations

import builtins
import copy
import dataclasses
import io
import itertools
import json
import os
from pathlib import Path
from typing import Optional

import pytest

from app.loader import _parse_display_config
from tests.helpers.kanal_liste_orakel import (
    KANAELE_ORTE,
    alt_compare_kanaele,
    alt_compare_premium_zeilen,
    alt_katalog_paare,
    alt_trip_format,
    alt_trip_metrics_for_channel,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "einstellung_gleich_mail"
KANAELE_TRIP = ("email", "telegram", "sms")
REPORT_TYPEN = ("morning", "evening")


def _resolver():
    from services.channel_list_resolver import resolve_channel_lists

    return resolve_channel_lists


def _aktiv(zeilen) -> Optional[list[str]]:
    if zeilen is None:
        return None
    return [z.metric_id for z in zeilen if z.enabled]


def _paare(zeilen) -> Optional[list[tuple[str, str]]]:
    """Orte-Kanalzeilen im einen Vokabular (#3101): (Katalog-ID, Aggregation)."""
    if zeilen is None:
        return None
    return [(z.metric_id, z.aggregation) for z in zeilen if z.enabled]


def _zeilen(vm, kanal: str):
    zeilen = getattr(vm, kanal)
    assert zeilen is None or isinstance(zeilen, tuple), (
        f"{kanal}: Zeilen muessen ein unveraenderliches tuple sein, nicht {type(zeilen)!r}"
    )
    return zeilen


# ---------------------------------------------------------------------------
# Trip-Konfigurationen
# ---------------------------------------------------------------------------

GRUND_TRIP = [
    {"metric_id": "temperature", "enabled": True, "bucket": "primary", "order": 0},
    {"metric_id": "wind", "enabled": True, "bucket": "primary", "order": 1,
     "format_mode": "simplified"},
    {"metric_id": "gust", "enabled": True, "bucket": "primary", "order": 2,
     "use_friendly_format": False},
    {"metric_id": "precipitation", "enabled": True, "bucket": "secondary", "order": 0,
     "morning_enabled": False},
    {"metric_id": "thunder", "enabled": False, "bucket": "secondary", "order": 1,
     "evening_enabled": True},
    {"metric_id": "cloud_total", "enabled": True, "bucket": "secondary", "order": 2},
]

TRIP_LISTEN = {
    "leer": [],
    "gefuellt": [
        {"metric_id": "cloud_total", "bucket": "primary", "order": 0},
        {"metric_id": "gust", "bucket": "primary", "order": 1, "format_mode": "simplified"},
        {"metric_id": "wind", "bucket": "primary", "order": 2, "use_friendly_format": False},
        {"metric_id": "precipitation", "bucket": "primary", "order": 3},
        {"metric_id": "uv_index", "bucket": "secondary", "order": 0},
        {"metric_id": "temperature", "enabled": False, "bucket": "secondary", "order": 1},
    ],
    # Totalschnitt (#3047 AC-10): keine einzige Grundauswahl-Metrik.
    "ausserhalb": [
        {"metric_id": "uv_index", "bucket": "primary", "order": 0},
        {"metric_id": "humidity", "bucket": "primary", "order": 1},
    ],
}
ZUSTAENDE_TRIP = ("fehlt", "leer", "gefuellt", "ausserhalb")

PER_REPORT_VARIANTEN = (
    None,
    {"morning": {"email": TRIP_LISTEN["gefuellt"][::-1], "sms": []}},
    {"evening": {"telegram": TRIP_LISTEN["gefuellt"], "email": TRIP_LISTEN["ausserhalb"]},
     "morning": {"telegram": []}},
)


def _trip_dict(zustaende: dict[str, str], per_report, grund) -> dict:
    dc: dict = {"trip_id": "t-3057"}
    if grund is not None:
        dc["metrics"] = copy.deepcopy(grund)
    layouts = {
        kanal: copy.deepcopy(TRIP_LISTEN[zustand])
        for kanal, zustand in zustaende.items()
        if zustand != "fehlt"
    }
    if layouts:
        dc["channel_layouts"] = layouts
    if per_report is not None:
        dc["channel_layouts_per_report"] = copy.deepcopy(per_report)
    return dc


def _trip_kombinationen():
    for i, (zust, per_report, grund) in enumerate(itertools.product(
        itertools.product(ZUSTAENDE_TRIP, repeat=3),
        PER_REPORT_VARIANTEN,
        (GRUND_TRIP, None),
    )):
        zustaende = dict(zip(KANAELE_TRIP, zust))
        # Premium-SMS rotiert durch alle Zustaende (AC-5), ohne die Zahl der
        # Kombinationen zu vervielfachen.
        zustaende["premium_sms"] = ZUSTAENDE_TRIP[i % len(ZUSTAENDE_TRIP)]
        yield f"{zust}|pr{PER_REPORT_VARIANTEN.index(per_report)}|g{grund is not None}", \
            _trip_dict(zustaende, per_report, grund)


def _trip_fixture_dict() -> dict:
    return json.loads((FIXTURES / "trip_altbestand.json").read_text())["display_config"]


def _vergleiche_trip(name: str, dc_eingabe, dc_modell, report_type: str, fehler: list) -> None:
    vm = _resolver()(dc_eingabe, "trip", report_type)
    for kanal in KANAELE_TRIP:
        alt = alt_trip_metrics_for_channel(dc_modell, kanal, report_type)
        zeilen = _zeilen(vm, kanal)
        if zeilen is None:
            fehler.append(f"{name}/{report_type}/{kanal}: Trip-Kanal ist None")
            continue
        aktiv = [z for z in zeilen if z.enabled]
        if [z.metric_id for z in aktiv] != [mc.metric_id for mc in alt]:
            fehler.append(
                f"{name}/{report_type}/{kanal}: Auswahl/Folge "
                f"{[z.metric_id for z in aktiv]} != alt {[mc.metric_id for mc in alt]}"
            )
            continue
        formen = [z.format for z in aktiv]
        if formen != [alt_trip_format(mc) for mc in alt]:
            fehler.append(f"{name}/{report_type}/{kanal}: Format {formen} != alt "
                          f"{[alt_trip_format(mc) for mc in alt]}")
        ordnung = [z.order for z in zeilen]
        if ordnung != list(range(len(zeilen))):
            fehler.append(f"{name}/{report_type}/{kanal}: order {ordnung} != 0..n-1")


# ---------------------------------------------------------------------------
# AC-1 -- Trip: Resolver und get_metrics_for_channel = Altpfad
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("eingabe", ["rohform", "modell"])
def test_ac1_trip_resolver_gleich_altpfad_ueber_alle_kombinationen(eingabe):
    """GIVEN Trips mit fehlenden, leeren, gefuellten und total geschnittenen
    Kanal-Listen, mit/ohne per_report und mit/ohne Grundauswahl
    WHEN der Resolver je Report-Typ aufgeloest wird
    THEN sind Auswahl, Reihenfolge und Format je Kanal gleich dem Altpfad."""
    fehler: list[str] = []
    faelle = list(_trip_kombinationen()) + [("fixture-altbestand", _trip_fixture_dict())]
    for name, roh in faelle:
        # #3048: Referenz ist der Trip-Ladepfad (Altbestand -> Standardsatz).
        modell = _parse_display_config(copy.deepcopy(roh), trip_standard_bei_leer=True)
        eingabe_dc = copy.deepcopy(roh) if eingabe == "rohform" else modell
        for report_type in REPORT_TYPEN:
            _vergleiche_trip(name, eingabe_dc, modell, report_type, fehler)
    assert not fehler, f"{len(fehler)} Abweichungen, erste: {fehler[:5]}"


def test_ac1_get_metrics_for_channel_gleich_altpfad_und_leer_bleibt_leer():
    """GIVEN dieselben Kombinationen
    WHEN ``get_metrics_for_channel`` (Adapter ueber den Resolver) gerufen wird
    THEN ist das Ergebnis feldgleich (ganze MetricConfig) zum Altpfad, und
    eine leere Liste bleibt leer."""
    _resolver()  # der Adapter liest aus dem Resolver; ohne ihn kein GREEN
    fehler: list[str] = []
    leer_gesehen = 0
    for name, roh in _trip_kombinationen():
        dc = _parse_display_config(copy.deepcopy(roh))
        for report_type in REPORT_TYPEN:
            for kanal in KANAELE_TRIP:
                neu = dc.get_metrics_for_channel(kanal, report_type)
                alt = alt_trip_metrics_for_channel(dc, kanal, report_type)
                if neu != alt:
                    fehler.append(f"{name}/{report_type}/{kanal}")
                if roh.get("channel_layouts", {}).get(kanal) == [] and not (
                    roh.get("channel_layouts_per_report", {}).get(report_type, {}).get(kanal)
                ):
                    leer_gesehen += 1
                    if neu != []:
                        fehler.append(f"{name}/{report_type}/{kanal}: [] nicht leer")
    assert leer_gesehen > 0
    assert not fehler, f"{len(fehler)} Abweichungen, erste: {fehler[:5]}"


# ---------------------------------------------------------------------------
# AC-2 -- Orte: Resolver und resolve_compare_render_options = Altpfad
# ---------------------------------------------------------------------------

AKTIV_ORTE = [
    {"metric_id": "temperature", "aggregation": "max"},
    {"metric_id": "wind", "aggregation": "max"},
    {"metric_id": "gust", "aggregation": "max"},
    {"metric_id": "precipitation", "aggregation": "sum"},
    {"metric_id": "rain_probability", "aggregation": "max"},
]
GRUND_ORTE = {"fehlt": None, "leer": [], "gefuellt": AKTIV_ORTE}
CAM_ORTE = {
    "leer": [],
    "gefuellt": [{"metric_id": "precipitation", "aggregation": "sum"},
                 {"metric_id": "wind", "aggregation": "max"}],
    "ausserhalb": [{"metric_id": "visibility", "aggregation": "min"}],
}
LAYOUT_ORTE = {
    "leer": [],
    "gefuellt": [
        {"metric_id": "gust", "enabled": True, "use_friendly_format": True},
        {"metric_id": "temperature", "enabled": True, "use_friendly_format": True},
        {"metric_id": "wind", "enabled": False},
        {"metric_id": "precipitation", "use_friendly_format": False},
        {"metric_id": "visibility", "enabled": True},
    ],
    "alle_aus": [{"metric_id": k, "enabled": False}
                 for k in ("temperature", "wind", "gust", "precipitation", "rain_probability")],
}
ZUSTAENDE_LAYOUT = ("fehlt", "leer", "gefuellt", "alle_aus")
ZUSTAENDE_CAM = ("fehlt", "leer", "gefuellt", "ausserhalb")


def _orte_preset(grund: str, cam: dict[str, str], layout: dict[str, str]) -> dict:
    dc: dict = {}
    if GRUND_ORTE[grund] is not None:
        dc["active_metrics"] = copy.deepcopy(GRUND_ORTE[grund])
    cam_dc = {k: copy.deepcopy(CAM_ORTE[z]) for k, z in cam.items() if z != "fehlt"}
    if cam_dc:
        dc["channel_active_metrics"] = cam_dc
    lay_dc = {k: copy.deepcopy(LAYOUT_ORTE[z]) for k, z in layout.items() if z != "fehlt"}
    if lay_dc:
        dc["channel_layouts"] = lay_dc
    return {"id": "p-3057", "display_config": dc}


def _orte_kombinationen():
    for i, (grund, lay) in enumerate(itertools.product(
        GRUND_ORTE, itertools.product(ZUSTAENDE_LAYOUT, repeat=3),
    )):
        cam = {k: ZUSTAENDE_CAM[(i + j) % len(ZUSTAENDE_CAM)] for j, k in enumerate(KANAELE_ORTE)}
        yield f"{grund}|cam{tuple(cam.values())}|lay{lay}", \
            _orte_preset(grund, cam, dict(zip(KANAELE_ORTE, lay)))


def _orte_fixtures():
    for pfad in sorted(FIXTURES.glob("orte_*.json")):
        yield pfad.name, json.loads(pfad.read_text())


def _vergleiche_orte(name: str, preset: dict, fehler: list) -> None:
    from services.report_config_resolver import resolve_compare_render_options

    alt_enabled, alt_rows = alt_compare_kanaele(preset)
    vm = _resolver()(copy.deepcopy(preset.get("display_config") or {}), "compare")
    opts = resolve_compare_render_options(copy.deepcopy(preset))
    for kanal in KANAELE_ORTE:
        zeilen = _zeilen(vm, kanal)
        # #3101: das View-Model spricht (Katalog-ID, Aggregation), der Altpfad
        # Renderer-Kennungen -- je Zeile genau eine, in derselben Folge.
        soll = alt_katalog_paare(alt_enabled[kanal])
        if _paare(zeilen) != soll:
            fehler.append(f"{name}/{kanal}: Resolver {_paare(zeilen)} != alt {soll}")
        elif zeilen is not None:
            aktiv = [z for z in zeilen if z.enabled]
            if [z.order for z in zeilen] != list(range(len(zeilen))):
                fehler.append(f"{name}/{kanal}: order {[z.order for z in zeilen]} != 0..n-1")
            if alt_rows[kanal] is None:
                if any(z.format is not None for z in aktiv):
                    fehler.append(f"{name}/{kanal}: ohne channel_layouts muss format None sein")
            else:
                einfach = [e for _rid, e in alt_rows[kanal]]
                for z, alt_einfach in zip(aktiv, einfach):
                    if (z.format == "simplified") != alt_einfach:
                        fehler.append(f"{name}/{kanal}/{z.metric_id}: format {z.format!r} "
                                      f"!= alt einfach={alt_einfach}")
        if opts.enabled_metrics_by_channel.get(kanal) != alt_enabled[kanal]:
            fehler.append(f"{name}/{kanal}: enabled_metrics_by_channel weicht ab")
        if opts.channel_rows_by_channel.get(kanal) != alt_rows[kanal]:
            fehler.append(f"{name}/{kanal}: channel_rows_by_channel weicht ab")
        soll_formen = None if alt_rows[kanal] is None else dict(alt_rows[kanal])
        if opts.metric_formats(kanal) != soll_formen:
            fehler.append(f"{name}/{kanal}: metric_formats weicht ab")


def test_ac2_orte_resolver_und_render_options_gleich_altpfad():
    """GIVEN Orts-Vergleiche mit channel_layouts, nur channel_active_metrics
    oder keinem von beiden, mit fehlender/leerer/gefuellter Grundauswahl
    WHEN Resolver und ``resolve_compare_render_options`` aufgeloest werden
    THEN sind Auswahl, Zeilen und Formate je Kanal gleich dem Altpfad."""
    fehler: list[str] = []
    for name, preset in _orte_kombinationen():
        _vergleiche_orte(name, preset, fehler)
    assert not fehler, f"{len(fehler)} Abweichungen, erste: {fehler[:5]}"


def test_ac2_orte_phase1_fixtures_gleich_altpfad():
    """GIVEN alle Orte-Presets des Phase-1-Pruefkatalogs
    WHEN Resolver und Render-Optionen aufgeloest werden
    THEN gleich dem Altpfad."""
    fehler: list[str] = []
    namen = []
    for name, preset in _orte_fixtures():
        namen.append(name)
        _vergleiche_orte(name, preset, fehler)
    assert len(namen) >= 5, namen
    assert not fehler, f"{len(fehler)} Abweichungen, erste: {fehler[:5]}"


# ---------------------------------------------------------------------------
# AC-3 -- morning_enabled=False wirkt nur im Morgenbriefing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ebene", ["global", "kanal", "per_report", "nur_kanal"])
def test_ac3_morning_enabled_false_fehlt_nur_morgens(ebene):
    """GIVEN ein Trip, dessen Niederschlag ``morning_enabled=False`` traegt
    (in der Grundauswahl bzw. zusaetzlich in der Kanal-Liste; ``nur_kanal``:
    NUR in der Kanal-Liste -- sonst verdeckt der Schnitt gegen die
    Grundauswahl eine Kanal-Zweig-Mutation)
    WHEN Morgen- und Abendbriefing aufgeloest werden
    THEN fehlt Niederschlag nur morgens -- im Resolver UND im Adapter."""
    grund = [
        {"metric_id": "temperature", "enabled": True, "order": 0},
        {"metric_id": "precipitation", "enabled": True, "order": 1, "morning_enabled": False},
        {"metric_id": "wind", "enabled": True, "order": 2},
    ]
    if ebene == "nur_kanal":
        del grund[1]["morning_enabled"]
    roh: dict = {"trip_id": "t-ac3", "metrics": grund}
    kanal_liste = [
        {"metric_id": "wind", "order": 0},
        {"metric_id": "precipitation", "order": 1, "morning_enabled": False},
        {"metric_id": "temperature", "order": 2},
    ]
    if ebene in ("kanal", "nur_kanal"):
        roh["channel_layouts"] = {"email": kanal_liste}
    elif ebene == "per_report":
        roh["channel_layouts_per_report"] = {
            "morning": {"email": kanal_liste}, "evening": {"email": kanal_liste},
        }
    dc = _parse_display_config(copy.deepcopy(roh))
    resolve = _resolver()

    morgens = _aktiv(_zeilen(resolve(copy.deepcopy(roh), "trip", "morning"), "email"))
    abends = _aktiv(_zeilen(resolve(copy.deepcopy(roh), "trip", "evening"), "email"))
    assert "precipitation" not in morgens, morgens
    assert "precipitation" in abends, abends
    assert set(morgens) == set(abends) - {"precipitation"}

    adapter_m = [mc.metric_id for mc in dc.get_metrics_for_channel("email", "morning")]
    adapter_a = [mc.metric_id for mc in dc.get_metrics_for_channel("email", "evening")]
    assert adapter_m == morgens
    assert adapter_a == abends
    assert morgens == [mc.metric_id for mc in alt_trip_metrics_for_channel(dc, "email", "morning")]
    assert abends == [mc.metric_id for mc in alt_trip_metrics_for_channel(dc, "email", "evening")]


# ---------------------------------------------------------------------------
# AC-4 -- drei Schreibweisen des Formats, Standard ohne Angabe, Eingabe unveraendert
# ---------------------------------------------------------------------------

def _schluessel(d: dict) -> str:
    return json.dumps(d, sort_keys=True, ensure_ascii=False)


def _zeilentupel(zeilen):
    return [(z.metric_id, z.enabled, z.format) for z in zeilen]


@pytest.mark.parametrize("surface,wert,schreibweisen", [
    # Orte: so schreibt die Editor-Karte (#3042) -- use_friendly_format True = Einfach.
    ("compare", "simplified", [{"format": "simplified"}, {"format_mode": "simplified"},
                               {"use_friendly_format": True}]),
    ("compare", "raw", [{"format": "raw"}, {"format_mode": "raw"},
                        {"use_friendly_format": False}]),
    # Trip: use_friendly_format True heisst dort Katalog-Standard (loader), daher Roh.
    ("trip", "raw", [{"format": "raw"}, {"format_mode": "raw"},
                     {"use_friendly_format": False}]),
    ("trip", "simplified", [{"format": "simplified"}, {"format_mode": "simplified"}]),
])
def test_ac4_drei_schreibweisen_ergeben_dieselbe_darstellung(surface, wert, schreibweisen):
    resolve = _resolver()
    ergebnisse = []
    for schreibweise in schreibweisen:
        if surface == "compare":
            dc = {"active_metrics": copy.deepcopy(AKTIV_ORTE),
                  "channel_layouts": {"email": [
                      {"metric_id": "wind", "enabled": True, **schreibweise},
                      {"metric_id": "gust", "enabled": True, **schreibweise},
                  ]}}
        else:
            dc = {"trip_id": "t-ac4", "metrics": copy.deepcopy(GRUND_TRIP),
                  "channel_layouts": {"email": [
                      {"metric_id": "wind", "order": 0, **schreibweise},
                      {"metric_id": "gust", "order": 1, **schreibweise},
                  ]}}
        vorher = _schluessel(dc)
        vm = resolve(dc, surface, "evening")
        assert _schluessel(dc) == vorher, "Eingabe veraendert"
        # #3101: Orte- und Trip-Zeilen tragen beide die Katalog-ID.
        ids = ("wind", "gust")
        zeilen = [z for z in _zeilen(vm, "email") if z.metric_id in ids]
        assert zeilen and all(z.format == wert for z in zeilen), (schreibweise, zeilen)
        ergebnisse.append(_zeilentupel(zeilen))
    assert all(e == ergebnisse[0] for e in ergebnisse), ergebnisse


def test_ac4_vorrang_format_vor_format_mode_vor_use_friendly_format():
    dc = {"active_metrics": copy.deepcopy(AKTIV_ORTE), "channel_layouts": {"email": [
        {"metric_id": "wind", "format": "raw", "format_mode": "simplified",
         "use_friendly_format": True},
        {"metric_id": "gust", "format_mode": "raw", "use_friendly_format": True},
    ]}}
    zeilen = {z.metric_id: z.format for z in _zeilen(_resolver()(dc, "compare"), "email")}
    assert zeilen["wind"] == "raw"
    assert zeilen["gust"] == "raw"


@pytest.mark.parametrize("wert", ["raw", "simplified"])
def test_ac4_trip_modell_mit_format_mode_gleich_rohform_mit_format(wert):
    """Der Loader verwirft ``format`` (Known Limitation, #3058): als Modell ist
    nur ``format_mode`` lesbar. Modell mit ``format_mode`` = Rohform mit
    ``format`` -- dieselben Zeilen."""
    def _dc(schluessel: str) -> dict:
        return {"trip_id": "t-f002", "metrics": copy.deepcopy(GRUND_TRIP),
                "channel_layouts": {"email": [
                    {"metric_id": "wind", "order": 0, schluessel: wert},
                    {"metric_id": "gust", "order": 1, schluessel: wert},
                ]}}

    resolve = _resolver()
    modell = _parse_display_config(_dc("format_mode"))
    aus_modell = _zeilen(resolve(modell, "trip", "evening"), "email")
    aus_rohform = _zeilen(resolve(_dc("format"), "trip", "evening"), "email")
    assert aus_modell == aus_rohform
    assert [(z.metric_id, z.format) for z in aus_modell if z.metric_id in ("wind", "gust")] == [
        ("wind", wert), ("gust", wert)]


def test_ac4_ohne_angabe_gilt_flaechen_standard():
    """Orte ohne Format bleibt Roh (Adapter liefert einfach=False), Trip ohne
    Format ist ``None`` = Katalog-Standard."""
    from services.report_config_resolver import resolve_compare_render_options

    preset = {"display_config": {"active_metrics": copy.deepcopy(AKTIV_ORTE),
                                 "channel_layouts": {"email": [{"metric_id": "wind"}]}}}
    vm = _resolver()(copy.deepcopy(preset["display_config"]), "compare")
    aktiv = [z for z in _zeilen(vm, "email") if z.enabled]
    assert aktiv and all(z.format is None for z in aktiv), _zeilentupel(aktiv)
    formen = resolve_compare_render_options(preset).metric_formats("email")
    assert formen and not any(formen.values()), formen

    trip = {"trip_id": "t", "metrics": [{"metric_id": "cloud_total", "enabled": True}]}
    zeilen = _zeilen(_resolver()(trip, "trip", "evening"), "email")
    assert [(z.metric_id, z.format) for z in zeilen if z.enabled] == [("cloud_total", None)]


# ---------------------------------------------------------------------------
# AC-5 -- Premium-SMS
# ---------------------------------------------------------------------------

def test_ac5_premium_sms_ohne_eigene_liste_ist_sms_liste():
    resolve = _resolver()
    for name, roh in _trip_kombinationen():
        hat_eigene = "premium_sms" in roh.get("channel_layouts", {}) or any(
            "premium_sms" in kanaele for kanaele in roh.get("channel_layouts_per_report", {}).values()
        )
        if hat_eigene:
            continue
        for report_type in REPORT_TYPEN:
            vm = resolve(copy.deepcopy(roh), "trip", report_type)
            assert vm.premium_sms == vm.sms, f"{name}/{report_type}"
    for name, preset in itertools.chain(_orte_kombinationen(), _orte_fixtures()):
        vm = resolve(copy.deepcopy(preset.get("display_config") or {}), "compare")
        assert vm.premium_sms == vm.sms, name


def test_ac5_premium_sms_eigene_liste_wird_gelesen():
    resolve = _resolver()
    roh = {"trip_id": "t-ac5", "metrics": copy.deepcopy(GRUND_TRIP),
           "channel_layouts": {"sms": copy.deepcopy(TRIP_LISTEN["gefuellt"]),
                               "premium_sms": [{"metric_id": "wind", "order": 0},
                                               {"metric_id": "temperature", "order": 1}]}}
    dc = _parse_display_config(copy.deepcopy(roh))
    vm = resolve(roh, "trip", "evening")
    premium = _aktiv(_zeilen(vm, "premium_sms"))
    assert premium == [
        mc.metric_id for mc in alt_trip_metrics_for_channel(dc, "premium_sms", "evening")
    ]
    # Eigene Liste wird gelesen; der Loader haengt abgeleitete Temperatur-
    # Kennungen an (_append_derived_metrics), daher nur der Anfang literal.
    assert premium[:2] == ["wind", "temperature"], premium
    assert _aktiv(vm.premium_sms) != _aktiv(vm.sms)

    preset = {"display_config": {"active_metrics": copy.deepcopy(AKTIV_ORTE), "channel_layouts": {
        "premium_sms": [{"metric_id": "gust"}, {"metric_id": "temperature"}]}}}
    vm = resolve(copy.deepcopy(preset["display_config"]), "compare")
    assert _paare(_zeilen(vm, "premium_sms")) == alt_katalog_paare(
        alt_compare_premium_zeilen(preset))
    assert _paare(vm.premium_sms) != _paare(vm.sms)


# ---------------------------------------------------------------------------
# AC-6 -- amtliche Warnungen sind keine Zeilen; [] bleibt [] trotz Grundauswahl
# ---------------------------------------------------------------------------

def test_ac6_nur_katalog_metriken_und_leer_bleibt_leer():
    from app.metric_catalog import _METRICS_BY_ID
    from output.renderers.compare_metric_catalog import COMPARE_METRIC_CATALOG

    resolve = _resolver()
    warnung = {"metric_id": "official_alerts", "enabled": True}
    trip = {"trip_id": "t-ac6", "metrics": copy.deepcopy(GRUND_TRIP),
            "channel_layouts": {"email": [warnung, {"metric_id": "wind"}], "sms": []}}
    for report_type in REPORT_TYPEN:
        vm = resolve(copy.deepcopy(trip), "trip", report_type)
        for kanal in ("email", "telegram", "sms", "premium_sms"):
            ids = {z.metric_id for z in _zeilen(vm, kanal)}
            assert ids <= set(_METRICS_BY_ID), (kanal, ids - set(_METRICS_BY_ID))
        assert _aktiv(vm.sms) == []
        assert _aktiv(vm.premium_sms) == []

    orte = {"active_metrics": copy.deepcopy(AKTIV_ORTE),
            "channel_layouts": {"email": [warnung, {"metric_id": "wind"}]},
            "channel_active_metrics": {"sms": [], "telegram": []}}
    vm = resolve(orte, "compare")
    # #3101: Orte-Zeilen tragen Katalog-ID + Aggregation, je Paar eine
    # Vergleichs-Zeile -- die amtliche Warnung ist keine.
    katalog_paare = {(e["metric_id"], e["aggregation"]) for e in COMPARE_METRIC_CATALOG}
    for kanal in ("email", "telegram", "sms", "premium_sms"):
        paare = {(z.metric_id, z.aggregation) for z in _zeilen(vm, kanal)}
        assert paare <= katalog_paare, (kanal, paare - katalog_paare)
    assert _aktiv(vm.telegram) == []
    assert _aktiv(vm.sms) == []

    # #3047 Runde 7 B-K6 loest den frueheren Ist-Stand ab ("channel_layouts: []
    # haengt die Grundauswahl an"): eine ausdruecklich leere Kanal-Liste bleibt
    # leer wie beim Trip (Konzept: abwaehlen erlaubt, #2422). Der Resolver folgt
    # weiter dem Orakel (Altpfad), beide sind jetzt leer.
    preset = {"display_config": {"active_metrics": copy.deepcopy(AKTIV_ORTE),
                                 "channel_layouts": {"telegram": []}}}
    vm = resolve(copy.deepcopy(preset["display_config"]), "compare")
    alt_enabled, _alt_rows = alt_compare_kanaele(preset)
    assert _aktiv(vm.telegram) == alt_enabled["telegram"]
    assert alt_enabled["telegram"] == [], "channel_layouts [] bleibt leer (B-K6)"


# ---------------------------------------------------------------------------
# AC-7 -- Alarmpfad unveraendert
# ---------------------------------------------------------------------------

def test_ac7_alarm_format_modes_gleich_altpfad():
    """GIVEN Trips mit abweichenden Kanal-Listen
    WHEN der Alarmpfad seine Anzeigemodi je Kanal bildet
    THEN gleich dem Ergebnis ueber den Altpfad."""
    from app.metric_catalog import get_metric
    from output.renderers.email.helpers import _effective_format_mode
    from services.notification_service import _alert_format_modes

    _resolver()
    fehler = []
    for name, roh in _trip_kombinationen():
        dc = _parse_display_config(copy.deepcopy(roh))
        soll: dict = {}
        for kanal in ("email", "telegram"):
            modi: dict = {}
            for report_type in REPORT_TYPEN:
                for mc in alt_trip_metrics_for_channel(dc, kanal, report_type):
                    try:
                        col = get_metric(mc.metric_id).col_key
                    except KeyError:
                        continue
                    modi.setdefault(col, _effective_format_mode(mc))
            soll[kanal] = modi
        if _alert_format_modes(dc) != soll:
            fehler.append(name)
    assert not fehler, f"{len(fehler)} Abweichungen, erste: {fehler[:5]}"


# ---------------------------------------------------------------------------
# AC-9 -- rein, unveraenderlich, ohne Datei-I/O
# ---------------------------------------------------------------------------

def test_ac9_eingabe_unveraendert_und_view_model_eingefroren():
    resolve = _resolver()
    for name, roh in list(_trip_kombinationen())[:40]:
        kopie = copy.deepcopy(roh)
        vm = resolve(roh, "trip", "morning")
        assert roh == kopie, name
        modell = _parse_display_config(copy.deepcopy(roh))
        vorher = copy.deepcopy(modell)
        resolve(modell, "trip", "evening")
        assert modell == vorher, name
    for name, preset in _orte_kombinationen():
        dc = preset["display_config"]
        kopie = copy.deepcopy(dc)
        resolve(dc, "compare")
        assert dc == kopie, name

    with pytest.raises(dataclasses.FrozenInstanceError):
        vm.email = ()  # type: ignore[misc]
    zeile = next(z for z in vm.email)
    with pytest.raises(dataclasses.FrozenInstanceError):
        zeile.enabled = False  # type: ignore[misc]


def test_ac9_kein_datei_zugriff(monkeypatch, tmp_path):
    resolve = _resolver()
    roh = _trip_dict({"email": "gefuellt", "telegram": "leer", "sms": "fehlt",
                      "premium_sms": "fehlt"}, PER_REPORT_VARIANTEN[1], GRUND_TRIP)
    orte = _orte_preset("gefuellt", {"email": "gefuellt"}, {"telegram": "gefuellt"})["display_config"]
    erwartet_trip = resolve(copy.deepcopy(roh), "trip", "morning")
    erwartet_orte = resolve(copy.deepcopy(orte), "compare")

    def kein_io(*_a, **_k):
        raise AssertionError("Resolver darf keine Datei oeffnen")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(builtins, "open", kein_io)
    monkeypatch.setattr(io, "open", kein_io)
    monkeypatch.setattr(os, "open", kein_io)
    assert resolve(copy.deepcopy(roh), "trip", "morning") == erwartet_trip
    assert resolve(copy.deepcopy(orte), "compare") == erwartet_orte
