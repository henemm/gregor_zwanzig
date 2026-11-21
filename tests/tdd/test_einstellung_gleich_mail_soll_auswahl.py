"""#3242: das Validator-Soll (``--konfig``) folgt mit Tabelle der Tabelle
auch in Auswahl und Reihenfolge.

SPEC: docs/specs/modules/fix_3242_validator_soll_auswahl.md (AC-1 .. AC-14)

Vorgaenger #3218 hat die Darstellung (``rows[].formats``) umgestellt. Auswahl
(welche Groessen) und Reihenfolge je Stelle liest das Soll mit vorhandener
Tabelle ``display_config.placements`` aber noch aus den Altfeldern
(``channel_layouts``, ``outlook_metrics``, ``hourly_metrics``,
``active_metrics``-Folge, ``bucket``/``order``). Der Renderer verwendet allein
die Tabelle -> Fehlalarme, sobald im Editor Haken oder Folge geaendert werden.

Kern-Schicht, ohne Mock: Eingabe ist rohes Abo-JSON (Trip bzw. Orte-Preset),
geprueft wird die Soll-Struktur des echten Moduls aus ``.claude/hooks``. Das
erwartete Soll steht VON HAND im Test (Spaltenkuerzel ``col_label``,
Zeilennamen ``label("de")``, konkrete Folge) und wird nie aus
``resolve_rows``/``resolve_channel_lists``/``placements_view``/``metrics_at``
berechnet. Die Faelle sind so gewaehlt, dass Tabelle und Altfelder (bzw. die
Folge von ``metrics``/``active_metrics``) sichtbar voneinander abweichen.
"""
from __future__ import annotations

import copy
import importlib.util
import inspect
import json
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = _ROOT / "tests" / "fixtures" / "einstellung_gleich_mail"

#: Warnzeile der Vergleichstabelle (Fixture ``orte_basis``: Warnungen an).
WARN = "Amtliche Warnungen"


def _soll_modul():
    """Das Soll-Modul der Validatoren direkt aus ``.claude/hooks`` (nur lesen)."""
    pfad = _ROOT / ".claude" / "hooks" / "_soll_aus_konfiguration.py"
    spec = importlib.util.spec_from_file_location("_soll_aus_konfiguration_3242", pfad)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def soll():
    return _soll_modul()


# --------------------------------------------------------------------------- #
# Bausteine (rohes Persistenzformat, feste Daten -> deterministisch)
# --------------------------------------------------------------------------- #
def _eintrag(mid: str, order: int, **extra) -> dict:
    e = {"metric_id": mid, "enabled": True, "bucket": "primary", "order": order}
    e.update(extra)
    return e


def _zeile(mid: str, **places) -> dict:
    """Tabellenzeile; ``places`` z. B. ``email=False, outlook=True``."""
    z: dict = {"metric_id": mid}
    if places:
        z["places"] = dict(places)
    return z


def _trip(metriken: list[dict], *, zeilen: list[dict] | None = None, **display) -> dict:
    """Trip-JSON mit festen Etappen; ``zeilen`` = Tabelle ``placements``."""
    dc: dict = {"trip_id": "soll-3242", "metrics": copy.deepcopy(metriken)}
    if zeilen is not None:
        dc["placements"] = {"version": 1, "rows": copy.deepcopy(zeilen)}
    dc.update(copy.deepcopy(display))
    return {
        "id": "soll-3242", "name": "Soll 3242",
        "stages": [{"id": f"T{i}", "name": f"Etappe {i}", "date": f"2026-07-0{i + 1}",
                    "waypoints": [{"id": f"G{i}a", "name": "Start", "lat": 47.27, "lon": 11.40,
                                   "elevation_m": 600},
                                  {"id": f"G{i}b", "name": "Ziel", "lat": 47.29, "lon": 11.42,
                                   "elevation_m": 900}]} for i in range(3)],
        "official_alerts_enabled": False, "official_warnings": {"enabled": False},
        "display_config": dc,
        "report_config": {"trip_id": "soll-3242", "enabled": True,
                          "morning_time": "07:00:00", "evening_time": "18:00:00",
                          "send_email": True, "send_sms": False, "send_telegram": False,
                          "send_premium_sms": False, "email_format": "full"},
    }


def _orte(display: dict, **preset_felder) -> dict:
    preset = json.loads((_FIXTURES / "orte_basis.json").read_text(encoding="utf-8"))
    preset["display_config"] = copy.deepcopy(display)
    preset.update(preset_felder)
    return preset


def _grund(*mids_agg) -> list[dict]:
    return [{"metric_id": m, "aggregation": a} for m, a in mids_agg]


def _tabelle(*zeilen) -> dict:
    return {"version": 1, "rows": [copy.deepcopy(z) for z in zeilen]}


def _email_ids(s: dict) -> list[str]:
    """Folge der E-Mail-Liste des Trip-Solls (Schluessel von ``darstellung_stunden``)."""
    return list(s["darstellung_stunden"])


def _ausblick_html(s: dict) -> list[str] | None:
    return None if s["ausblick"] is None else list(s["ausblick"]["html"])


# --------------------------------------------------------------------------- #
# AC-1: Trip -- Folge und E-Mail-Haken der Tabelle, Altfelder alt
# --------------------------------------------------------------------------- #
_AC1_METRIKEN = [_eintrag("temperature", 0), _eintrag("wind", 1), _eintrag("precipitation", 2),
                 _eintrag("rain_probability", 3), _eintrag("cloud_total", 4)]
_AC1_ZEILEN = [_zeile("cloud_total", outlook=True), _zeile("rain_probability", outlook=False),
               _zeile("temperature", outlook=True), _zeile("wind", email=False),
               _zeile("precipitation")]
_AC1_ALT = {"channel_layouts": {"email": [{"metric_id": "temperature"}, {"metric_id": "wind"},
                                          {"metric_id": "precipitation"}]},
            "outlook_metrics": ["temperature", "wind"]}


def test_ac1_trip_email_folgt_tabelle_nicht_altfeldern(soll):
    """AC-1. GIVEN Trip mit Tabelle (umsortiert: Bewoelkung, Regen-W., Temp,
    Wind E-Mail aus, Niederschlag) und alten Altfeldern (``channel_layouts.email``
    = Temp, Wind, Niederschlag)
    WHEN das Soll abgeleitet wird
    THEN erwartet die Stundentabelle Folge und Auswahl der Tabelle, Wind fehlt."""
    s = soll.trip_soll(_trip(_AC1_METRIKEN, zeilen=_AC1_ZEILEN, **_AC1_ALT), "evening")
    assert s["stunden"] == ["Cloud", "Rain%", "Temp", "Rain"], s["stunden"]
    assert _email_ids(s) == ["cloud_total", "rain_probability", "temperature", "precipitation"], s
    assert s["ueberblick_folge"] == ["cloud_total", "rain_probability", "temperature",
                                     "precipitation"], s["ueberblick_folge"]


def test_ac1_trip_ausblick_folgt_tabelle_nicht_outlook_metrics(soll):
    """AC-1 (Ausblick, Regel 4). GIVEN dieselbe Tabelle; ``outlook_metrics`` =
    Temp, Wind (alt)
    WHEN das Soll abgeleitet wird
    THEN Ausblick = Zeilen mit outlook an UND E-Mail an, in Zeilenfolge:
    Bewoelkung, Temp, Niederschlag (Zeile ohne ``places`` = ueberall an);
    Regen-W. (outlook aus) und Wind (E-Mail aus) fehlen."""
    s = soll.trip_soll(_trip(_AC1_METRIKEN, zeilen=_AC1_ZEILEN, **_AC1_ALT), "evening")
    assert _ausblick_html(s) == ["Cloud", "Temp", "Rain"], s["ausblick"]


# --------------------------------------------------------------------------- #
# AC-2: Orte -- Vergleichstabelle, Stundenverlauf, Ausblick je Stelle
# --------------------------------------------------------------------------- #
_AC2_GRUND = _grund(("temperature", "max"), ("cloud_total", "avg"), ("rain_probability", "max"),
                    ("wind", "max"), ("gust", "max"))
_AC2_ZEILEN = [_zeile("gust", hourly=False), _zeile("rain_probability"),
               _zeile("wind", email=False), _zeile("temperature", outlook=False),
               _zeile("cloud_total")]


def _ac2_preset() -> dict:
    return _orte({
        "active_metrics": _AC2_GRUND,
        "channel_layouts": {"email": [{"metric_id": "temperature"}, {"metric_id": "wind"}]},
        "hourly_metrics": ["temperature", "wind"],
        "outlook_metrics": ["temperature", "wind"],
        "placements": _tabelle(*_AC2_ZEILEN),
    })


def test_ac2_orte_vergleichstabelle_folgt_tabelle(soll):
    """AC-2. GIVEN Orte mit Tabelle Boeen, Regen-W., Wind (E-Mail aus), Temp,
    Bewoelkung; Altfeld ``channel_layouts.email`` = Temp, Wind
    WHEN das Soll abgeleitet wird
    THEN Vergleichstabelle in Tabellenfolge ohne Wind."""
    s = soll.orte_soll(_ac2_preset(), "de")
    assert s["uebersicht"] == [WARN, "Böen", "Regenwahrscheinlichkeit", "Temperatur",
                               "Bewölkung"], s["uebersicht"]


def test_ac2_orte_stundenverlauf_folgt_tabelle(soll):
    """AC-2. Stundenverlauf = hourly an UND E-Mail an, Zeilenfolge: Boeen
    (hourly aus) und Wind (E-Mail aus) fehlen; ``hourly_metrics`` = Temp, Wind
    (alt) ohne Wirkung. Bewoelkung ohne ``places`` = an."""
    s = soll.orte_soll(_ac2_preset(), "de")
    assert s["stunden"] == ["Rain%", "Temp", "Cloud"], s["stunden"]


def test_ac2_orte_ausblick_folgt_tabelle(soll):
    """AC-2. Ausblick = outlook an UND E-Mail an, Zeilenfolge: Temp (outlook
    aus) und Wind (E-Mail aus) fehlen; ``outlook_metrics`` (alt) ohne Wirkung."""
    s = soll.orte_soll(_ac2_preset(), "de")
    assert _ausblick_html(s) == ["Gust", "Rain%", "Cloud"], s["ausblick"]


# --------------------------------------------------------------------------- #
# AC-3: ``rows: []`` -> ganze Grundauswahl, Standardfolge, ueberall an
# --------------------------------------------------------------------------- #
def test_ac3_trip_leere_zeilenliste_ganze_grundauswahl(soll):
    """AC-3. GIVEN Trip, Tabelle ``rows: []``, Grundauswahl (nach bucket/order)
    Wind, Niederschlag, Temp; Altfelder ``channel_layouts.email`` = Temp,
    ``outlook_metrics`` = Wind
    WHEN das Soll abgeleitet wird
    THEN E-Mail und Ausblick = ganze Grundauswahl in deren Folge."""
    trip = _trip([_eintrag("temperature", 2), _eintrag("wind", 0), _eintrag("precipitation", 1)],
                 zeilen=[], channel_layouts={"email": [{"metric_id": "temperature"}]},
                 outlook_metrics=["wind"])
    s = soll.trip_soll(trip, "evening")
    assert s["stunden"] == ["Wind", "Rain", "Temp"], s["stunden"]
    assert _ausblick_html(s) == ["Wind", "Rain", "Temp"], s["ausblick"]


def test_ac3_orte_leere_zeilenliste_ganze_grundauswahl(soll):
    """AC-3. GIVEN Orte, ``rows: []``, Grundauswahl Wind, Temp Max, Temp Min;
    Altfelder ``channel_layouts.email`` = Temp, ``hourly_metrics`` = Temp
    WHEN das Soll abgeleitet wird
    THEN Vergleichstabelle = ganze Grundauswahl (Doppelzeile Temp mit
    Auswertung), Stundenverlauf = Wind, Temp."""
    preset = _orte({
        "active_metrics": _grund(("wind", "max"), ("temperature", "max"), ("temperature", "min")),
        "channel_layouts": {"email": [{"metric_id": "temperature"}]},
        "hourly_metrics": ["temperature"],
        "placements": {"version": 1, "rows": []},
    })
    s = soll.orte_soll(preset, "de")
    assert s["uebersicht"] == [WARN, "Wind", "Temperatur Maximum", "Temperatur Minimum"], \
        s["uebersicht"]
    assert s["stunden"] == ["Wind", "Temp"], s["stunden"]


# --------------------------------------------------------------------------- #
# AC-4: alle E-Mail-Haken aus -> E-Mail leer (bis auf Fenstergroessen),
# Stundenverlauf und Ausblick leer
# --------------------------------------------------------------------------- #
def test_ac4_trip_alle_email_aus(soll):
    """AC-4. GIVEN Trip, alle Zeilen E-Mail aus (auch Tages-Hoechsttemperatur,
    eine Fenstergroesse mit eigener Zeile)
    WHEN das Soll abgeleitet wird
    THEN keine Stundenspalte, die E-Mail-Liste traegt nur die Fenstergroesse
    (``keine_eigene_spalte`` bleibt in der Ausgabe), kein Ausblick."""
    trip = _trip([_eintrag("temperature", 0), _eintrag("wind", 1), _eintrag("precipitation", 2),
                  _eintrag("temperature_day_high", 3)],
                 zeilen=[_zeile("temperature", email=False), _zeile("wind", email=False),
                         _zeile("precipitation", email=False),
                         _zeile("temperature_day_high", email=False)])
    s = soll.trip_soll(trip, "evening")
    assert s["stunden"] == [], s["stunden"]
    assert _email_ids(s) == ["temperature_day_high"], s["darstellung_stunden"]
    assert s["ausblick"] is None, s["ausblick"]


def test_ac4_orte_alle_email_aus(soll):
    """AC-4. GIVEN Orte, alle Zeilen E-Mail aus, hourly/outlook nicht gesetzt
    (= an); Altfelder ``hourly_metrics``/``outlook_metrics`` gefuellt
    WHEN das Soll abgeleitet wird
    THEN Vergleichstabelle nur Warnzeile, Stundenverlauf und Ausblick leer."""
    preset = _orte({
        "active_metrics": _grund(("temperature", "max"), ("wind", "max")),
        "hourly_metrics": ["temperature", "wind"],
        "outlook_metrics": ["temperature", "wind"],
        "placements": _tabelle(_zeile("temperature", email=False), _zeile("wind", email=False)),
    })
    s = soll.orte_soll(preset, "de")
    assert s["uebersicht"] == [WARN], s["uebersicht"]
    assert s["stunden"] == [], s["stunden"]
    assert s["ausblick"] is None, s["ausblick"]


# --------------------------------------------------------------------------- #
# AC-5: abgeleitete Groesse ohne eigene Zeile folgt der Eltern-Zeile
# --------------------------------------------------------------------------- #
_AC5_METRIKEN = [_eintrag("wind", 0), _eintrag("temperature", 1), _eintrag("precipitation", 2),
                 _eintrag("temperature_night", 3), _eintrag("temperature_day_low", 4)]


def test_ac5_abgeleitete_groesse_direkt_hinter_eltern_zeile(soll):
    """AC-5 (Eltern an). GIVEN Nachttief und Tages-Tiefsttemperatur (Kinder von
    Temperatur, ``_DERIVED_METRIC_RULES``) in der Grundauswahl ohne eigene
    Zeile; Tabelle Temp, Wind, Niederschlag; ``metrics``-Folge Wind, Temp,
    Niederschlag, Nacht, Tagestief
    WHEN das Soll abgeleitet wird
    THEN stehen die Kinder direkt hinter Temperatur (Geschwister in
    Grundauswahl-Folge hintereinander), danach Wind, Niederschlag."""
    trip = _trip(_AC5_METRIKEN, zeilen=[_zeile("temperature"), _zeile("wind"),
                                        _zeile("precipitation")])
    s = soll.trip_soll(trip, "evening")
    assert _email_ids(s) == ["temperature", "temperature_night", "temperature_day_low", "wind",
                             "precipitation"], s["darstellung_stunden"]
    assert s["stunden"] == ["Temp", "Wind", "Rain"], s["stunden"]


def test_ac5_eltern_zeile_email_aus(soll):
    """AC-5 (Eltern aus). GIVEN dieselbe Grundauswahl, Temperatur-Zeile E-Mail aus
    WHEN das Soll abgeleitet wird
    THEN fehlt Temperatur in der E-Mail-Liste; Stundenspalten Wind, Niederschlag.

    ANNAHME/OFFEN: AC-5 sagt "die abgeleitete Groesse ist ebenfalls aus". Alle
    abgeleiteten Groessen (``_DERIVED_METRIC_RULES``) sind zugleich
    Fenstergroessen; fuer die Trip-E-Mail gilt dort Regel 2 / AC-11
    (``keine_eigene_spalte`` bleibt in der Ausgabe, so auch das Produkt
    ``metrics_at``). Ob die Kinder dann in ``darstellung_stunden`` stehen, ist
    zwischen AC-5 und Regel 2 widerspruechlich und wird hier bewusst NICHT
    zugesichert -- nur das eindeutig Beobachtbare."""
    trip = _trip(_AC5_METRIKEN, zeilen=[_zeile("temperature", email=False), _zeile("wind"),
                                        _zeile("precipitation")])
    s = soll.trip_soll(trip, "evening")
    assert "temperature" not in s["darstellung_stunden"], s["darstellung_stunden"]
    assert s["stunden"] == ["Wind", "Rain"], s["stunden"]


# --------------------------------------------------------------------------- #
# AC-6: Trip morning vs. evening, gleiche Tabelle, je Report eigene Grundauswahl
# --------------------------------------------------------------------------- #
def test_ac6_trip_grundauswahl_je_report_folge_aus_tabelle(soll):
    """AC-6. GIVEN Grundauswahl: Wind nur abends (``morning_enabled: false``),
    Niederschlag nur morgens (``evening_enabled: false``); report-unabhaengige
    Tabelle Bewoelkung, Niederschlag, Wind, Temp
    WHEN das Soll je Report abgeleitet wird
    THEN Morgen = Bewoelkung, Niederschlag, Temp; Abend = Bewoelkung, Wind, Temp."""
    trip = _trip([_eintrag("temperature", 0), _eintrag("wind", 1, morning_enabled=False),
                  _eintrag("precipitation", 2, evening_enabled=False),
                  _eintrag("cloud_total", 3)],
                 zeilen=[_zeile("cloud_total"), _zeile("precipitation"), _zeile("wind"),
                         _zeile("temperature")])
    je = soll.soll_aus_daten(trip, "de")["je_report"]
    assert je["morning"]["stunden"] == ["Cloud", "Rain", "Temp"], je["morning"]["stunden"]
    assert je["evening"]["stunden"] == ["Cloud", "Wind", "Temp"], je["evening"]["stunden"]


# --------------------------------------------------------------------------- #
# AC-7: Windrichtung E-Mail aus -> keine Wind-Verschmelzung
# --------------------------------------------------------------------------- #
def test_ac7_windrichtung_email_aus_keine_verschmelzung(soll):
    """AC-7. GIVEN Wind und Windrichtung (Einfach laut Tabelle), Windrichtung
    E-Mail aus; Altfeld ``channel_layouts.email`` fuehrt Windrichtung (Skala)
    WHEN das Soll abgeleitet wird
    THEN keine verschmolzene Wind-Spalte, Windrichtung nicht in der Liste."""
    trip = _trip([_eintrag("wind", 0), _eintrag("wind_direction", 1)],
                 zeilen=[_zeile("wind"),
                         {"metric_id": "wind_direction", "places": {"email": False},
                          "formats": {"email": "simplified"}}],
                 channel_layouts={"email": [{"metric_id": "wind"},
                                            {"metric_id": "wind_direction",
                                             "format_mode": "scale"}]})
    s = soll.trip_soll(trip, "evening")
    assert s["wind_richtung"] is False, s
    assert "wind_direction" not in s["darstellung_stunden"], s["darstellung_stunden"]


def test_ac7_windrichtung_email_an_verschmilzt(soll):
    """AC-7 (Gegenprobe). GIVEN Windrichtung E-Mail an, Einfach laut Tabelle;
    Altfeld ``channel_layouts.email`` fuehrt nur Wind
    WHEN das Soll abgeleitet wird
    THEN verschmolzene Wind-Spalte, keine eigene WDir-Spalte."""
    trip = _trip([_eintrag("wind", 0), _eintrag("wind_direction", 1)],
                 zeilen=[{"metric_id": "wind_direction", "formats": {"email": "simplified"}},
                         _zeile("wind")],
                 channel_layouts={"email": [{"metric_id": "wind"}]})
    s = soll.trip_soll(trip, "evening")
    assert s["wind_richtung"] is True, s
    assert s["stunden"] == ["Wind"], s["stunden"]


# --------------------------------------------------------------------------- #
# AC-8: Orte-Doppelzeile (Temp Maximum/Minimum)
# --------------------------------------------------------------------------- #
def test_ac8_orte_doppelzeile_nur_ein_paar_in_grundauswahl(soll):
    """AC-8. GIVEN Grundauswahl Temp Maximum, Wind (Temp Minimum fehlt);
    Tabelle Wind, Temperatur
    WHEN das Soll abgeleitet wird
    THEN Vergleichstabelle Wind, Temperatur (nur das Maximum, ohne Zusatz)."""
    preset = _orte({
        "active_metrics": _grund(("temperature", "max"), ("wind", "max")),
        "placements": _tabelle(_zeile("wind"), _zeile("temperature")),
    })
    s = soll.orte_soll(preset, "de")
    assert s["uebersicht"] == [WARN, "Wind", "Temperatur"], s["uebersicht"]


def test_ac8_orte_doppelzeile_beide_paare_in_zeilenfolge(soll):
    """AC-8. GIVEN Grundauswahl Temp Maximum, Temp Minimum, Wind; Tabelle Wind,
    Temperatur
    WHEN das Soll abgeleitet wird
    THEN Wind, dann beide Temperatur-Zeilen (Maximum vor Minimum).

    ANNAHME: die Folge der Auswertungen innerhalb einer Katalog-ID ist Maximum
    vor Minimum; Grundauswahl und Compare-Katalog stimmen darin hier ueberein,
    der Test haengt also nicht an der Wahl der Quelle."""
    preset = _orte({
        "active_metrics": _grund(("temperature", "max"), ("temperature", "min"), ("wind", "max")),
        "placements": _tabelle(_zeile("wind"), _zeile("temperature")),
    })
    s = soll.orte_soll(preset, "de")
    assert s["uebersicht"] == [WARN, "Wind", "Temperatur Maximum", "Temperatur Minimum"], \
        s["uebersicht"]


# --------------------------------------------------------------------------- #
# AC-9: Orte ohne ``active_metrics`` mit Tabelle -> Standardzeilen
# --------------------------------------------------------------------------- #
def _ac9_preset() -> dict:
    return _orte({"placements": _tabelle(_zeile("gust"), _zeile("temperature", email=False),
                                         _zeile("precipitation"))})


def test_ac9_orte_nie_eingestellt_vergleichstabelle_aus_standardzeilen(soll):
    """AC-9. GIVEN Orte ohne ``active_metrics`` (nie eingestellt) mit Tabelle
    Boeen, Temperatur (E-Mail aus), Niederschlag
    WHEN das Soll abgeleitet wird
    THEN Grundauswahl = Standardzeilen der Vergleichstabelle: erst die
    Tabellenzeilen, dann die uebrigen Standardzeilen in Standardfolge;
    Temperatur (Max und Min) fehlt; Gefuehlte Temperatur als Doppelzeile."""
    s = soll.orte_soll(_ac9_preset(), "de")
    assert s["uebersicht"] == [
        WARN, "Böen", "Niederschlag", "Wind", "Regenwahrscheinlichkeit", "Gewitter",
        "Sonnenstunden", "Bewölkung", "UV-Index", "Sichtweite", "Schneehöhe", "Neuschnee",
        "Nullgradgrenze", "Windrichtung", "Gefühlte Temperatur Minimum",
        "Gefühlte Temperatur Maximum", "Tiefe Wolken", "Mittelhohe Wolken", "Hohe Wolken",
        "Luftfeuchte", "Taupunkt", "Luftdruck", "Niederschlagsart", "Schneefallgrenze",
    ], s["uebersicht"]


def test_ac9_orte_nie_eingestellt_ausblick_nicht_fest(soll):
    """AC-9. GIVEN wie oben
    WHEN das Soll abgeleitet wird
    THEN Ausblick aus den Standardzeilen in Tabellenfolge (outlook ueberall an,
    Temperatur E-Mail aus -> nicht im Ausblick), NICHT der feste ``_FEST``-Satz."""
    s = soll.orte_soll(_ac9_preset(), "de")
    assert _ausblick_html(s) == [
        "Gust", "Rain", "Wind", "Rain%", "Thdr", "Sun", "Cloud", "UV", "Visib", "SnowH",
        "NewSn", "0°Line", "WDir", "Feels", "CldLow", "CldMid", "CldHi", "Humid", "Dew",
        "Press", "PType", "SnowL",
    ], s["ausblick"]


# --------------------------------------------------------------------------- #
# AC-10: Zeilen ausserhalb der Grundauswahl ohne Wirkung
# --------------------------------------------------------------------------- #
def test_ac10_trip_fremde_zeilen_ohne_wirkung(soll):
    """AC-10. GIVEN Trip-Grundauswahl Temp, Wind; Tabelle Bewoelkung (fremd),
    Wind, Boeen (fremd), Temp
    WHEN das Soll abgeleitet wird
    THEN E-Mail und Ausblick = Wind, Temp; keine Spalte fuer fremde Zeilen."""
    trip = _trip([_eintrag("temperature", 0), _eintrag("wind", 1)],
                 zeilen=[_zeile("cloud_total"), _zeile("wind"), _zeile("gust"),
                         _zeile("temperature")])
    s = soll.trip_soll(trip, "evening")
    assert s["stunden"] == ["Wind", "Temp"], s["stunden"]
    assert _ausblick_html(s) == ["Wind", "Temp"], s["ausblick"]


def test_ac10_orte_fremde_zeilen_ohne_wirkung(soll):
    """AC-10. GIVEN Orte-Grundauswahl Temp Max, Wind; Tabelle Boeen (fremd),
    Wind, Bewoelkung (fremd), Temperatur
    WHEN das Soll abgeleitet wird
    THEN Vergleichstabelle und Ausblick nur Wind, Temperatur."""
    preset = _orte({
        "active_metrics": _grund(("temperature", "max"), ("wind", "max")),
        "placements": _tabelle(_zeile("gust"), _zeile("wind"), _zeile("cloud_total"),
                               _zeile("temperature")),
    })
    s = soll.orte_soll(preset, "de")
    assert s["uebersicht"] == [WARN, "Wind", "Temperatur"], s["uebersicht"]
    assert _ausblick_html(s) == ["Wind", "Temp"], s["ausblick"]


# --------------------------------------------------------------------------- #
# AC-11: Fenstergroesse bleibt in der Trip-E-Mail, nie im Ausblick; Sperren
# --------------------------------------------------------------------------- #
def test_ac11_trip_fenstergroesse_in_email_nie_im_ausblick(soll):
    """AC-11. GIVEN Trip mit Tages-Hoechsttemperatur (Fenstergroesse, eigene
    Zeile, E-Mail-Haken aus, outlook an); Tabelle Wind, Tageshoch, Temp
    WHEN das Soll abgeleitet wird
    THEN die Fenstergroesse steht an ihrer Zeilenstelle in der E-Mail-Liste
    (``keine_eigene_spalte``), ohne Stundenspalte, und fehlt im Ausblick
    (``kein_tageswert``)."""
    trip = _trip([_eintrag("temperature", 0), _eintrag("temperature_day_high", 1),
                  _eintrag("wind", 2)],
                 zeilen=[_zeile("wind"), _zeile("temperature_day_high", email=False, outlook=True),
                         _zeile("temperature")])
    s = soll.trip_soll(trip, "evening")
    assert _email_ids(s) == ["wind", "temperature_day_high", "temperature"], \
        s["darstellung_stunden"]
    assert s["stunden"] == ["Wind", "Temp"], s["stunden"]
    assert _ausblick_html(s) == ["Wind", "Temp"], s["ausblick"]


def test_ac11_orte_sonnenstunden_nie_im_stundenverlauf(soll):
    """AC-11. GIVEN Orte mit Sonnenstunden (Sperre ``kein_stundenwert``), hourly
    an; Tabelle Sonnenstunden, Temperatur; ``active_metrics``-Folge Temp, Sonne
    WHEN das Soll abgeleitet wird
    THEN Vergleichstabelle und Ausblick tragen Sonnenstunden in Tabellenfolge,
    der Stundenverlauf nicht."""
    preset = _orte({
        "active_metrics": _grund(("temperature", "max"), ("sunshine", "sum")),
        "placements": _tabelle(_zeile("sunshine", hourly=True), _zeile("temperature")),
    })
    s = soll.orte_soll(preset, "de")
    assert s["uebersicht"] == [WARN, "Sonnenstunden", "Temperatur"], s["uebersicht"]
    assert s["stunden"] == ["Temp"], s["stunden"]
    assert _ausblick_html(s) == ["Sun", "Temp"], s["ausblick"]


# --------------------------------------------------------------------------- #
# AC-12: ``hourly_enabled: false`` bleibt aus
# --------------------------------------------------------------------------- #
def test_ac12_orte_hourly_enabled_false_stundenverlauf_aus(soll):
    """AC-12 -- Regressionsschutz, schon gruen. GIVEN Orte mit
    ``hourly_enabled: false``, Tabelle mit hourly-Haken an
    WHEN das Soll abgeleitet wird
    THEN Stundenverlauf aus und leer."""
    preset = _orte({
        "active_metrics": _grund(("temperature", "max"), ("wind", "max")),
        "placements": _tabelle(_zeile("wind", hourly=True), _zeile("temperature", hourly=True)),
    }, hourly_enabled=False)
    s = soll.orte_soll(preset, "de")
    assert s["stunden_an"] is False, s
    assert s["stunden"] == [], s["stunden"]


# --------------------------------------------------------------------------- #
# AC-13: Altbestand ohne Tabelle unveraendert
# --------------------------------------------------------------------------- #
def test_ac13_altbestand_ohne_tabelle_unveraendert_zur_gesicherten_ausgabe(soll):
    """AC-13 -- Regressionsschutz, schon gruen. GIVEN die Altbestands-Abos ohne
    Tabelle aus #3218 (Fixtures plus Trip-Varianten)
    WHEN das Soll abgeleitet wird
    THEN ist es bytegleich zur gesicherten Vorher-Ausgabe."""
    from tests.tdd.test_einstellung_gleich_mail_soll_placements import (
        GOLDEN_VORHER, soll_ohne_tabelle,
    )

    vorher = GOLDEN_VORHER.read_text(encoding="utf-8")
    jetzt = json.dumps(soll_ohne_tabelle(soll), ensure_ascii=False, sort_keys=True, indent=1)
    assert jetzt == vorher


def test_ac13_trip_ohne_tabelle_folgt_weiter_altfeldern(soll):
    """AC-13 -- Regressionsschutz, schon gruen. GIVEN Trip ohne Tabelle mit
    ``channel_layouts.email`` = Niederschlag, Temp und ``outlook_metrics`` = Wind
    WHEN das Soll abgeleitet wird
    THEN E-Mail und Ausblick folgen den Altfeldern (sortiert nach bucket/order)."""
    trip = _trip([_eintrag("temperature", 0), _eintrag("wind", 1), _eintrag("precipitation", 2)],
                 channel_layouts={"email": [{"metric_id": "precipitation"},
                                            {"metric_id": "temperature"}]},
                 outlook_metrics=["wind"])
    s = soll.trip_soll(trip, "evening")
    assert s["stunden"] == ["Rain", "Temp"], s["stunden"]
    assert _ausblick_html(s) == ["Wind"], s["ausblick"]


# --------------------------------------------------------------------------- #
# AC-14: Spiegel-Verbot im neuen Pfad
# --------------------------------------------------------------------------- #
_VERBOTEN = ("resolve_rows", "resolve_channel_lists", "placements_view", "metrics_at", "_cell")


def test_ac14_tabellen_folge_ruft_keine_produkt_aufloesung():  # doc-compliance-test
    """AC-14. GIVEN der neue Helfer ``_tabellen_folge`` im Soll
    WHEN sein Quelltext geprueft wird
    THEN ruft er weder ``resolve_rows``, ``resolve_channel_lists``,
    ``placements_view``, ``metrics_at`` noch ``_cell`` auf (die einzige
    Ausnahme ``ausblick_briefings``, #3155, liegt ausserhalb)."""
    mod = _soll_modul()
    assert hasattr(mod, "_tabellen_folge"), "Helfer _tabellen_folge fehlt im Soll-Modul"
    quelltext = inspect.getsource(mod._tabellen_folge)
    treffer = [n for n in _VERBOTEN if re.search(r"(?<![\w.])" + re.escape(n) + r"\s*\(", quelltext)
               or re.search(r"\." + re.escape(n) + r"\s*\(", quelltext)]
    assert not treffer, f"Spiegel-Verbot verletzt: {treffer}"
