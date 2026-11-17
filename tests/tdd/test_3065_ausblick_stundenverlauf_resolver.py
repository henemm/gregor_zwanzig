"""Ausblick- und Stundenverlauf-Liste im Kanal-Listen-Resolver (Issue #3065,
Phase 2b von Epic #3047, ADR-0121 Nachtrag 2b).

SPEC: docs/specs/modules/feat_3065_ausblick_stundenverlauf_resolver.md (AC-1..AC-10).

Kern-Schicht, deterministisch, ohne Netz, ohne ``Mock()``/``patch()``: echte
``display_config``-Dicts, der echte Loader-Parser und die echten Altfunktionen
als Orakel (``tests/helpers/kanal_liste_orakel.py``), nie der Resolver selbst.

Vertrag, den diese Tests festlegen:

* ``MailViewModel`` traegt zusaetzlich ``outlook`` und ``hourly`` (Default
  ``None``), je ein ``tuple`` von ``ChannelRow`` in Anzeigefolge (``order``
  ab 0, ``enabled=True``) oder ``None``.
* ``metric_id`` ist dort die KATALOG-Kennung (``"temperature"``), nicht die
  Renderer-Kennung der Orte-Kanaele.
* ``None`` = Renderer-Vorgabemenge, ``()`` = Block entfaellt.
* Ausblick-``format``: wahr -> ``simplified``, ausdruecklich falsch ->
  ``raw``, sonst ``None``. Stundenverlauf-``format`` immer ``None``.
* Trip: ``hourly`` immer ``None``; ``outlook`` aus dem ungekollabierten Modell.

RED heute: ``MailViewModel`` hat weder ``outlook`` noch ``hourly``.
"""
from __future__ import annotations

import builtins
import copy
import dataclasses
import io
import itertools
import os
from typing import Optional

import pytest

from app.loader import _parse_display_config
from app.metric_catalog import get_metric
from tests.helpers.kanal_liste_orakel import (
    alt_compare_ausblick,
    alt_compare_stundenverlauf,
    alt_format_aus_flag,
    alt_trip_ausblick,
)

REPORT_TYPEN = ("morning", "evening")


def _resolver():
    from services.channel_list_resolver import resolve_channel_lists

    return resolve_channel_lists


def _liste(vm, feld: str):
    """Liest ``outlook``/``hourly`` und prueft die Grundform (tuple oder None)."""
    assert hasattr(vm, feld), f"MailViewModel hat kein Feld {feld!r} (#3065)"
    zeilen = getattr(vm, feld)
    assert zeilen is None or isinstance(zeilen, tuple), (
        f"{feld}: muss tuple oder None sein, nicht {type(zeilen)!r}"
    )
    return zeilen


def _ids(zeilen) -> Optional[list[str]]:
    return None if zeilen is None else [z.metric_id for z in zeilen]


def _form_fehler(name: str, zeilen) -> list[str]:
    if zeilen is None:
        return []
    fehler = []
    if [z.order for z in zeilen] != list(range(len(zeilen))):
        fehler.append(f"{name}: order {[z.order for z in zeilen]} != 0..n-1")
    if not all(z.enabled is True for z in zeilen):
        fehler.append(f"{name}: nicht jede Zeile enabled=True")
    return fehler


# ---------------------------------------------------------------------------
# Orte-Kombinationen
# ---------------------------------------------------------------------------

AKTIV_ORTE = [
    {"metric_id": "temperature", "aggregation": "max"},
    {"metric_id": "wind", "aggregation": "max"},
    {"metric_id": "gust", "aggregation": "max"},
    {"metric_id": "precipitation", "aggregation": "sum"},
    {"metric_id": "rain_probability", "aggregation": "max"},
]
GRUND_ORTE = {
    "fehlt": None,
    "leer": [],
    "gefuellt": AKTIV_ORTE,
    "eng": [{"metric_id": "visibility", "aggregation": "min"}],
    "nur_richtung": [{"metric_id": "wind_direction", "aggregation": "avg"}],
}
AUSBLICK_ORTE = {
    "fehlt": None,
    "leer": [],
    "gefuellt": ["precipitation", "temperature", "wind"],
    # Totalschnitt gegen AKTIV_ORTE: keine Groesse liegt in der Grundauswahl.
    "totalschnitt": ["visibility", "humidity"],
}
# #3047 R9: von Hand aus editor_standard.json (Orte-Ausblick "nie_eingestellt").
VORGABE_ORTE_AUSBLICK = ["temperature", "precipitation", "rain_probability", "wind", "gust", "thunder"]
STUNDEN_ORTE = {
    "fehlt": None,
    "leer": [],
    "gefuellt": ["wind", "temperature", "wind"],
    "kurzschluessel": ["temp_c", "gust_kmh", "wind_dir_deg"],
    "totalschnitt": ["humidity"],
    "richtung": ["wind_direction", "temperature"],
    "ausgenommen_unbekannt": ["sunshine", "foo", "precipitation"],
}
FORMATE = {
    "fehlt": None,
    "gemischt": {"wind": True, "gust": False, "temperature": True,
                 "precipitation": "ja", "cloud_total": True},
}


def _orte_dc(grund: str, ausblick: str, stunden: str, formate: str) -> dict:
    dc: dict = {}
    for schluessel, tabelle, zustand in (
        ("active_metrics", GRUND_ORTE, grund),
        ("outlook_metrics", AUSBLICK_ORTE, ausblick),
        ("hourly_metrics", STUNDEN_ORTE, stunden),
        ("outlook_metric_formats", FORMATE, formate),
    ):
        if tabelle[zustand] is not None:
            dc[schluessel] = copy.deepcopy(tabelle[zustand])
    return dc


def _orte_kombinationen():
    for grund, ausblick, stunden, formate in itertools.product(
        GRUND_ORTE, AUSBLICK_ORTE, STUNDEN_ORTE, FORMATE,
    ):
        yield f"g={grund}|a={ausblick}|s={stunden}|f={formate}", \
            _orte_dc(grund, ausblick, stunden, formate)


# ---------------------------------------------------------------------------
# AC-1 -- Orte-Ausblick = resolve_compare_outlook_metrics
# ---------------------------------------------------------------------------

def test_ac1_orte_ausblick_gleich_altpfad_ueber_alle_kombinationen():
    """GIVEN Orts-Vergleiche mit Ausblick None/[]/gefuellt/Totalschnitt, je mit
    fehlender, leerer, gefuellter und enger Grundauswahl
    WHEN der Resolver die Orte-Ausblick-Liste liefert
    THEN sind Auswahl und Folge exakt die des Altpfads (None bleibt None,
    [] bleibt leer, Totalschnitt faellt zurueck und ist nicht leer)."""
    resolve = _resolver()
    fehler: list[str] = []
    gesehen = {"none": 0, "leer": 0, "totalschnitt_rueckfall": 0}
    for name, dc in _orte_kombinationen():
        alt_ids, _formate = alt_compare_ausblick(copy.deepcopy(dc))
        zeilen = _liste(resolve(copy.deepcopy(dc), "compare"), "outlook")
        if _ids(zeilen) != alt_ids:
            fehler.append(f"{name}: Resolver {_ids(zeilen)} != alt {alt_ids}")
            continue
        fehler.extend(_form_fehler(name, zeilen))
        # #3047 R9 (Abnahme 8): Altbestand ohne Grundauswahl und ohne Ausblick
        # loest nicht mehr zu None (fester Zweig, HTML Temp Tief/Hoch getrennt)
        # auf, sondern zur Vorgabemenge, die der Editor als aktiv zeigt
        # (editor_standard.json, Orte-Ausblick "nie_eingestellt").
        if "g=fehlt|a=fehlt" in name:
            gesehen["none"] += 1
            if alt_ids != VORGABE_ORTE_AUSBLICK:
                fehler.append(f"{name}: Vorgabemenge erwartet, nicht {alt_ids!r}")
        elif alt_ids == []:
            gesehen["leer"] += 1
            if zeilen != ():
                fehler.append(f"{name}: leer muss () sein, nicht {zeilen!r}")
        if "a=totalschnitt" in name and "g=gefuellt" in name:
            gesehen["totalschnitt_rueckfall"] += 1
            if not zeilen:
                fehler.append(f"{name}: Totalschnitt darf nicht leer sein")
    assert all(gesehen.values()), f"Kombinationen decken nicht alles ab: {gesehen}"
    assert not fehler, f"{len(fehler)} Abweichungen, erste: {fehler[:5]}"


def test_ac1_orte_ausblick_traegt_katalog_kennungen():
    """GIVEN Grundauswahl in Paar-Form (Renderer-Kennungen temp_max, ...)
    WHEN der Ausblick nie eingestellt ist
    THEN stehen Katalog-Kennungen in der Folge der Grundauswahl im Ausblick."""
    vm = _resolver()({"active_metrics": copy.deepcopy(AKTIV_ORTE)}, "compare")
    assert _ids(_liste(vm, "outlook")) == [
        "temperature", "wind", "gust", "precipitation", "rain_probability",
    ]


# ---------------------------------------------------------------------------
# AC-2 -- Trip-Ausblick = resolve_trip_outlook_metrics (ungekollabiert)
# ---------------------------------------------------------------------------

GRUND_TRIP = [
    {"metric_id": "temperature", "enabled": True, "bucket": "primary", "order": 0},
    {"metric_id": "wind", "enabled": True, "bucket": "primary", "order": 1},
    {"metric_id": "gust", "enabled": True, "bucket": "primary", "order": 2},
    {"metric_id": "precipitation", "enabled": True, "bucket": "secondary", "order": 0,
     "morning_enabled": False},
    {"metric_id": "thunder", "enabled": False, "bucket": "secondary", "order": 1,
     "evening_enabled": True},
    {"metric_id": "cloud_total", "enabled": True, "bucket": "secondary", "order": 2},
]
ENGE_EMAIL = [{"metric_id": "temperature", "bucket": "primary", "order": 0}]
AUSBLICK_TRIP = {
    "fehlt": None,
    "leer": [],
    "gefuellt": ["cloud_total", "wind", "temperature"],
    "totalschnitt": ["uv_index", "humidity"],
}


def _trip_dict(grund, ausblick: str, eng: bool, formate: str) -> dict:
    dc: dict = {"trip_id": "t-3065"}
    if grund is not None:
        dc["metrics"] = copy.deepcopy(grund)
    if eng:
        dc["channel_layouts"] = {"email": copy.deepcopy(ENGE_EMAIL)}
    if AUSBLICK_TRIP[ausblick] is not None:
        dc["outlook_metrics"] = copy.deepcopy(AUSBLICK_TRIP[ausblick])
    if FORMATE[formate] is not None:
        dc["outlook_metric_formats"] = copy.deepcopy(FORMATE[formate])
    return dc


def _trip_kombinationen():
    for grund, ausblick, eng, formate in itertools.product(
        (GRUND_TRIP, None), AUSBLICK_TRIP, (False, True), FORMATE,
    ):
        yield f"g={grund is not None}|a={ausblick}|eng={eng}|f={formate}", \
            _trip_dict(grund, ausblick, eng, formate)


@pytest.mark.parametrize("eingabe", ["rohform", "modell"])
def test_ac2_trip_ausblick_gleich_altpfad_je_report_typ(eingabe):
    """GIVEN Trips mit/ohne Grundauswahl (Altbestand ohne metrics), mit/ohne
    enge E-Mail-Liste und Ausblick None/[]/gefuellt/Totalschnitt
    WHEN der Resolver den Trip-Ausblick fuer morning und evening liefert
    THEN entspricht die Liste dem Altpfad auf dem ungekollabierten Modell."""
    resolve = _resolver()
    fehler: list[str] = []
    for name, roh in _trip_kombinationen():
        # #3048: Referenz ist der Trip-Ladepfad.
        modell = _parse_display_config(copy.deepcopy(roh), trip_standard_bei_leer=True)
        for report_type in REPORT_TYPEN:
            alt_ids, _f = alt_trip_ausblick(modell, report_type)
            arg = copy.deepcopy(roh) if eingabe == "rohform" else modell
            zeilen = _liste(resolve(arg, "trip", report_type), "outlook")
            if _ids(zeilen) != alt_ids:
                fehler.append(f"{name}/{report_type}: {_ids(zeilen)} != alt {alt_ids}")
            fehler.extend(_form_fehler(f"{name}/{report_type}", zeilen))
    assert not fehler, f"{len(fehler)} Abweichungen, erste: {fehler[:5]}"


@pytest.mark.parametrize("report_type", REPORT_TYPEN)
def test_ac2_enge_email_liste_schneidet_den_ausblick_nicht(report_type):
    """GIVEN ein Trip mit enger channel_layouts.email (nur temperature) und
    nie eingestelltem Ausblick
    WHEN der Resolver aufgeloest wird
    THEN ist der Ausblick laenger als die E-Mail-Liste und gleich dem Altpfad."""
    roh = _trip_dict(GRUND_TRIP, "fehlt", True, "fehlt")
    vm = _resolver()(copy.deepcopy(roh), "trip", report_type)
    # #3048: Referenz ist der Trip-Ladepfad.
    alt_ids, _f = alt_trip_ausblick(
        _parse_display_config(copy.deepcopy(roh), trip_standard_bei_leer=True), report_type,
    )
    email = [z.metric_id for z in vm.email if z.enabled]
    ausblick = _ids(_liste(vm, "outlook"))
    # Der Loader ergaenzt zu ``temperature`` die Tagesrichtungs-Begleiter
    # (temperature_night/_day_low/_day_high); eng heisst: keine weitere Groesse.
    assert email[0] == "temperature" and "wind" not in email, email
    assert ausblick == alt_ids
    ausserhalb = [m for m in ausblick if m not in email]
    assert ausserhalb, f"Ausblick {ausblick} von E-Mail-Liste {email} geschnitten"


# ---------------------------------------------------------------------------
# AC-3 -- Roh/Einfach je Ausblick-Zeile
# ---------------------------------------------------------------------------

def test_ac3_format_orte_ueber_alle_kombinationen():
    """GIVEN die Orte-Kombinationen mit und ohne Format-Zuordnung
    WHEN der Resolver die Ausblick-Zeilen liefert
    THEN traegt jede Zeile das Format aus ``resolve_compare_outlook_formats``."""
    resolve = _resolver()
    fehler: list[str] = []
    for name, dc in _orte_kombinationen():
        _ids_alt, formate = alt_compare_ausblick(copy.deepcopy(dc))
        zeilen = _liste(resolve(copy.deepcopy(dc), "compare"), "outlook") or ()
        for z in zeilen:
            soll = alt_format_aus_flag(formate, z.metric_id)
            if z.format != soll:
                fehler.append(f"{name}/{z.metric_id}: {z.format!r} != {soll!r}")
    assert not fehler, f"{len(fehler)} Abweichungen, erste: {fehler[:5]}"


def test_ac3_format_trip_ueber_alle_kombinationen():
    resolve = _resolver()
    fehler: list[str] = []
    for name, roh in _trip_kombinationen():
        # #3048: Referenz ist der Trip-Ladepfad.
        modell = _parse_display_config(copy.deepcopy(roh), trip_standard_bei_leer=True)
        for report_type in REPORT_TYPEN:
            _ids_alt, formate = alt_trip_ausblick(modell, report_type)
            zeilen = _liste(resolve(copy.deepcopy(roh), "trip", report_type), "outlook") or ()
            for z in zeilen:
                soll = alt_format_aus_flag(formate, z.metric_id)
                if z.format != soll:
                    fehler.append(f"{name}/{report_type}/{z.metric_id}: {z.format!r} != {soll!r}")
    assert not fehler, f"{len(fehler)} Abweichungen, erste: {fehler[:5]}"


ERWARTETE_FORMATE = {
    "wind": "simplified",       # wahr
    "gust": "raw",              # ausdruecklich falsch
    "temperature": None,        # wahr, aber nicht ausblick-faehig
    "precipitation": None,      # kein boolescher Wert
}


def test_ac3_format_drei_faelle_orte_und_trip_gleich():
    """GIVEN wahr / ausdruecklich falsch / kein Eintrag / nicht ausblick-faehig
    WHEN Orte und Trip mit derselben Zuordnung aufgeloest werden
    THEN steht simplified / raw / None / None, fuer beide Flaechen gleich."""
    resolve = _resolver()
    orte = resolve({"active_metrics": copy.deepcopy(AKTIV_ORTE),
                    "outlook_metric_formats": copy.deepcopy(FORMATE["gemischt"])}, "compare")
    trip = resolve(_trip_dict(GRUND_TRIP, "fehlt", False, "gemischt"), "trip", "evening")
    for flaeche, vm in (("orte", orte), ("trip", trip)):
        formate = {z.metric_id: z.format for z in _liste(vm, "outlook")}
        for metric_id, soll in ERWARTETE_FORMATE.items():
            assert formate.get(metric_id, "FEHLT") == soll, (
                f"{flaeche}/{metric_id}: {formate.get(metric_id, 'FEHLT')!r} != {soll!r}"
            )
    orte_ohne = resolve({"active_metrics": copy.deepcopy(AKTIV_ORTE)}, "compare")
    assert {z.format for z in _liste(orte_ohne, "outlook")} == {None}


# ---------------------------------------------------------------------------
# AC-4 -- Stundenverlauf = resolve_hourly_metrics (ueber dp_field)
# ---------------------------------------------------------------------------

def test_ac4_orte_stundenverlauf_gleich_altpfad_ueber_alle_kombinationen():
    """GIVEN Orts-Vergleiche mit Stundenverlauf None/[]/gefuellt/Kurzschluessel/
    Totalschnitt/wind_direction/ausgenommen, je Grundauswahl
    WHEN der Resolver die Stundenverlauf-Liste liefert
    THEN bilden ihre Katalog-IDs per dp_field exakt das Altergebnis ab,
    und format ist bei jeder Zeile None."""
    resolve = _resolver()
    fehler: list[str] = []
    gesehen = {"none": 0, "leer": 0, "gefuellt": 0}
    for name, dc in _orte_kombinationen():
        alt = alt_compare_stundenverlauf(copy.deepcopy(dc))
        zeilen = _liste(resolve(copy.deepcopy(dc), "compare"), "hourly")
        if zeilen is None or alt is None:
            if zeilen is not None or alt is not None:
                fehler.append(f"{name}: Resolver {_ids(zeilen)} != alt {alt}")
            else:
                gesehen["none"] += 1
            continue
        try:
            abgebildet = [get_metric(z.metric_id).dp_field for z in zeilen]
        except Exception as exc:  # noqa: BLE001 - Katalog-ID erwartet
            fehler.append(f"{name}: keine Katalog-ID in {_ids(zeilen)} ({exc})")
            continue
        if abgebildet != alt:
            fehler.append(f"{name}: dp_field {abgebildet} != alt {alt}")
            continue
        gesehen["leer" if alt == [] else "gefuellt"] += 1
        if any(z.format is not None for z in zeilen):
            fehler.append(f"{name}: Stundenverlauf mit format {[z.format for z in zeilen]}")
        fehler.extend(_form_fehler(name, zeilen))
    assert all(gesehen.values()), f"Kombinationen decken nicht alles ab: {gesehen}"
    assert not fehler, f"{len(fehler)} Abweichungen, erste: {fehler[:5]}"


def test_ac4_wind_direction_bleibt_im_stundenverlauf():
    """GIVEN Stundenverlauf mit wind_direction (Merge-only) ohne Grundauswahl
    WHEN der Resolver aufgeloest wird
    THEN steht wind_direction als Katalog-ID in der Liste (nicht gefiltert)."""
    vm = _resolver()({"hourly_metrics": ["wind_direction", "temperature"]}, "compare")
    assert _ids(_liste(vm, "hourly")) == ["wind_direction", "temperature"]
    assert [z.format for z in vm.hourly] == [None, None]


# ---------------------------------------------------------------------------
# AC-5 -- None-Vertrag
# ---------------------------------------------------------------------------

def test_ac5_none_heisst_vorgabemenge_leeres_tupel_heisst_block_entfaellt():
    resolve = _resolver()
    nie = resolve({}, "compare")
    # #3047 R9: Orte-Ausblick "nie eingestellt" (ohne Grundauswahl) = die
    # Vorgabemenge als Liste, wie der Editor sie zeigt -- nicht mehr None.
    assert _ids(_liste(nie, "outlook")) == VORGABE_ORTE_AUSBLICK
    assert _liste(nie, "hourly") is None
    leer = resolve({"active_metrics": copy.deepcopy(AKTIV_ORTE),
                    "outlook_metrics": [], "hourly_metrics": []}, "compare")
    assert _liste(leer, "outlook") == ()
    assert _liste(leer, "hourly") == ()


def test_ac5_trip_stundenverlauf_ist_immer_none():
    """GIVEN Trips jeder Art (auch mit gefuellten Kanal-Listen und Ausblick)
    WHEN der Resolver aufgeloest wird
    THEN ist ``hourly`` None -- eine eigene Trip-Stundenliste gibt es nicht."""
    resolve = _resolver()
    for name, roh in _trip_kombinationen():
        roh = {**roh, "hourly_metrics": ["temperature"],
               "channel_layouts": {"email": copy.deepcopy(ENGE_EMAIL),
                                   "sms": copy.deepcopy(ENGE_EMAIL)}}
        for report_type in REPORT_TYPEN:
            assert _liste(resolve(copy.deepcopy(roh), "trip", report_type), "hourly") is None, name


# ---------------------------------------------------------------------------
# AC-6 -- resolve_hourly_metrics nach dem Split unveraendert
# ---------------------------------------------------------------------------
# Eingabe-/Ausgabe-Tabelle, festgehalten am Stand VOR dem Split (Commit
# fd15736d1, 2026-11-16) -- (hourly_metrics, enabled_metrics, Rueckgabe).

VOR_SPLIT = [
    (None, None, None),
    (None, [], []),
    (None, ['temp_max', 'wind_max', 'gust_max', 'precip_sum', 'pop_max'], ['t2m_c', 'wind10m_kmh', 'gust_kmh', 'precip_1h_mm', 'pop_pct']),
    (None, ['visibility_min'], ['visibility_m']),
    (None, ['wind_direction_avg'], None),
    (None, ['wind_direction_avg', 'visibility_min'], ['wind_direction_deg', 'visibility_m']),
    ('temperature', None, None),
    ('temperature', [], []),
    ('temperature', ['temp_max', 'wind_max', 'gust_max', 'precip_sum', 'pop_max'], ['t2m_c', 'wind10m_kmh', 'gust_kmh', 'precip_1h_mm', 'pop_pct']),
    ('temperature', ['visibility_min'], ['visibility_m']),
    ('temperature', ['wind_direction_avg'], None),
    ('temperature', ['wind_direction_avg', 'visibility_min'], ['wind_direction_deg', 'visibility_m']),
    ({'x': 1}, None, None),
    ({'x': 1}, [], []),
    ({'x': 1}, ['temp_max', 'wind_max', 'gust_max', 'precip_sum', 'pop_max'], ['t2m_c', 'wind10m_kmh', 'gust_kmh', 'precip_1h_mm', 'pop_pct']),
    ({'x': 1}, ['visibility_min'], ['visibility_m']),
    ({'x': 1}, ['wind_direction_avg'], None),
    ({'x': 1}, ['wind_direction_avg', 'visibility_min'], ['wind_direction_deg', 'visibility_m']),
    ([], None, []),
    ([], [], []),
    ([], ['temp_max', 'wind_max', 'gust_max', 'precip_sum', 'pop_max'], []),
    ([], ['visibility_min'], []),
    ([], ['wind_direction_avg'], []),
    ([], ['wind_direction_avg', 'visibility_min'], []),
    (['temperature', 'wind'], None, ['t2m_c', 'wind10m_kmh']),
    (['temperature', 'wind'], [], []),
    (['temperature', 'wind'], ['temp_max', 'wind_max', 'gust_max', 'precip_sum', 'pop_max'], ['t2m_c', 'wind10m_kmh']),
    (['temperature', 'wind'], ['visibility_min'], ['visibility_m']),
    (['temperature', 'wind'], ['wind_direction_avg'], ['wind_direction_deg']),
    (['temperature', 'wind'], ['wind_direction_avg', 'visibility_min'], ['visibility_m']),
    (['wind', 'temperature', 'wind'], None, ['wind10m_kmh', 't2m_c']),
    (['wind', 'temperature', 'wind'], [], []),
    (['wind', 'temperature', 'wind'], ['temp_max', 'wind_max', 'gust_max', 'precip_sum', 'pop_max'], ['wind10m_kmh', 't2m_c']),
    (['wind', 'temperature', 'wind'], ['visibility_min'], ['visibility_m']),
    (['wind', 'temperature', 'wind'], ['wind_direction_avg'], ['wind_direction_deg']),
    (['wind', 'temperature', 'wind'], ['wind_direction_avg', 'visibility_min'], ['visibility_m']),
    (['temp_c', 'gust_kmh', 'wind_dir_deg'], None, ['t2m_c', 'gust_kmh', 'wind_direction_deg']),
    (['temp_c', 'gust_kmh', 'wind_dir_deg'], [], []),
    (['temp_c', 'gust_kmh', 'wind_dir_deg'], ['temp_max', 'wind_max', 'gust_max', 'precip_sum', 'pop_max'], ['t2m_c', 'gust_kmh']),
    (['temp_c', 'gust_kmh', 'wind_dir_deg'], ['visibility_min'], ['visibility_m']),
    (['temp_c', 'gust_kmh', 'wind_dir_deg'], ['wind_direction_avg'], ['wind_direction_deg']),
    (['temp_c', 'gust_kmh', 'wind_dir_deg'], ['wind_direction_avg', 'visibility_min'], ['wind_direction_deg']),
    (['sunshine'], None, []),
    (['sunshine'], [], []),
    (['sunshine'], ['temp_max', 'wind_max', 'gust_max', 'precip_sum', 'pop_max'], []),
    (['sunshine'], ['visibility_min'], []),
    (['sunshine'], ['wind_direction_avg'], []),
    (['sunshine'], ['wind_direction_avg', 'visibility_min'], []),
    (['foo'], None, []),
    (['foo'], [], []),
    (['foo'], ['temp_max', 'wind_max', 'gust_max', 'precip_sum', 'pop_max'], []),
    (['foo'], ['visibility_min'], []),
    (['foo'], ['wind_direction_avg'], []),
    (['foo'], ['wind_direction_avg', 'visibility_min'], []),
    (['sunshine', 'foo', 'precipitation'], None, ['precip_1h_mm']),
    (['sunshine', 'foo', 'precipitation'], [], []),
    (['sunshine', 'foo', 'precipitation'], ['temp_max', 'wind_max', 'gust_max', 'precip_sum', 'pop_max'], ['precip_1h_mm']),
    (['sunshine', 'foo', 'precipitation'], ['visibility_min'], ['visibility_m']),
    (['sunshine', 'foo', 'precipitation'], ['wind_direction_avg'], ['wind_direction_deg']),
    (['sunshine', 'foo', 'precipitation'], ['wind_direction_avg', 'visibility_min'], ['visibility_m']),
    (['wind_direction'], None, ['wind_direction_deg']),
    (['wind_direction'], [], []),
    (['wind_direction'], ['temp_max', 'wind_max', 'gust_max', 'precip_sum', 'pop_max'], ['t2m_c', 'wind10m_kmh', 'gust_kmh', 'precip_1h_mm', 'pop_pct']),
    (['wind_direction'], ['visibility_min'], ['visibility_m']),
    (['wind_direction'], ['wind_direction_avg'], ['wind_direction_deg']),
    (['wind_direction'], ['wind_direction_avg', 'visibility_min'], ['wind_direction_deg']),
    (['visibility', 'uv_index'], None, ['visibility_m', 'uv_index']),
    (['visibility', 'uv_index'], [], []),
    (['visibility', 'uv_index'], ['temp_max', 'wind_max', 'gust_max', 'precip_sum', 'pop_max'], ['t2m_c', 'wind10m_kmh', 'gust_kmh', 'precip_1h_mm', 'pop_pct']),
    (['visibility', 'uv_index'], ['visibility_min'], ['visibility_m']),
    (['visibility', 'uv_index'], ['wind_direction_avg'], ['wind_direction_deg']),
    (['visibility', 'uv_index'], ['wind_direction_avg', 'visibility_min'], ['visibility_m']),
    (['humidity'], None, ['humidity_pct']),
    (['humidity'], [], []),
    (['humidity'], ['temp_max', 'wind_max', 'gust_max', 'precip_sum', 'pop_max'], ['t2m_c', 'wind10m_kmh', 'gust_kmh', 'precip_1h_mm', 'pop_pct']),
    (['humidity'], ['visibility_min'], ['visibility_m']),
    (['humidity'], ['wind_direction_avg'], ['wind_direction_deg']),
    (['humidity'], ['wind_direction_avg', 'visibility_min'], ['visibility_m']),
]


@pytest.mark.parametrize("hourly, enabled, erwartet", VOR_SPLIT)
def test_ac6_resolve_hourly_metrics_unveraendert(hourly, enabled, erwartet):
    from output.renderers.compare_hourly_metric_ids import resolve_hourly_metrics

    assert resolve_hourly_metrics(copy.deepcopy(hourly), copy.deepcopy(enabled)) == erwartet


def test_ac6_signatur_unveraendert():
    import inspect

    from output.renderers.compare_hourly_metric_ids import resolve_hourly_metrics

    parameter = list(inspect.signature(resolve_hourly_metrics).parameters.values())
    assert [p.name for p in parameter] == ["hourly_metrics", "enabled_metrics"]
    assert parameter[1].default is None


# ---------------------------------------------------------------------------
# AC-7 -- rein, eingefroren, ohne Dateizugriff
# ---------------------------------------------------------------------------

def test_ac7_eingabe_unveraendert_und_felder_eingefroren():
    resolve = _resolver()
    vm = None
    for name, dc in _orte_kombinationen():
        kopie = copy.deepcopy(dc)
        vm = resolve(dc, "compare")
        assert dc == kopie, name
    for name, roh in _trip_kombinationen():
        kopie = copy.deepcopy(roh)
        resolve(roh, "trip", "morning")
        assert roh == kopie, name
    _liste(vm, "outlook")
    _liste(vm, "hourly")
    with pytest.raises(dataclasses.FrozenInstanceError):
        vm.outlook = ()  # type: ignore[misc,union-attr]
    with pytest.raises(dataclasses.FrozenInstanceError):
        vm.hourly = ()  # type: ignore[misc,union-attr]


def test_ac7_kein_datei_zugriff(monkeypatch, tmp_path):
    resolve = _resolver()
    orte = _orte_dc("gefuellt", "gefuellt", "kurzschluessel", "gemischt")
    trip = _trip_dict(GRUND_TRIP, "gefuellt", True, "gemischt")
    erwartet_orte = resolve(copy.deepcopy(orte), "compare")
    erwartet_trip = resolve(copy.deepcopy(trip), "trip", "evening")
    assert _liste(erwartet_orte, "outlook") and _liste(erwartet_orte, "hourly")

    def kein_io(*_a, **_k):
        raise AssertionError("Resolver darf keine Datei oeffnen")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(builtins, "open", kein_io)
    monkeypatch.setattr(io, "open", kein_io)
    monkeypatch.setattr(os, "open", kein_io)
    assert resolve(copy.deepcopy(orte), "compare") == erwartet_orte
    assert resolve(copy.deepcopy(trip), "trip", "evening") == erwartet_trip


# ---------------------------------------------------------------------------
# AC-9 -- bestehende Aufrufer
# ---------------------------------------------------------------------------

def test_ac9_konstruktion_ohne_neue_felder_liefert_none():
    from services.channel_list_resolver import ChannelRow, MailViewModel

    zeile = ChannelRow("temperature", True, None, 0)
    vm = MailViewModel(email=(zeile,), telegram=(), sms=None, premium_sms=None)
    assert vm.layout_channels == ()
    assert getattr(vm, "outlook", "FEHLT") is None
    assert getattr(vm, "hourly", "FEHLT") is None


# ---------------------------------------------------------------------------
# AC-10 -- ADR-0121 Nachtrag 2b
# ---------------------------------------------------------------------------

def test_ac10_adr_0121_nachtrag_2b():  # doc-compliance-test
    from pathlib import Path

    adr = Path(__file__).resolve().parents[2] / "docs" / "adr"
    text = next(adr.glob("0121-*.md")).read_text(encoding="utf-8")
    assert "Nachtrag 2b" in text
    for begriff in ("outlook", "hourly", "Katalog", "hourly_enabled", "outlook_enabled"):
        assert begriff in text.split("Nachtrag 2b", 1)[1], f"Nachtrag 2b ohne {begriff!r}"
