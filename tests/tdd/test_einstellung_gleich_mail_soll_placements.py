"""#3218: das Validator-Soll (``--konfig``) liest ``display_config.placements``.

SPEC: docs/specs/modules/fix_3218_validator_soll_placements.md (AC-1 .. AC-13)

Das Soll der Mail-Validatoren leitet Roh/Einfach heute nur aus den Altfeldern
(``use_friendly_format``/``format_mode``, ``channel_layouts.email``,
``outlook_metric_formats``) ab. Der Renderer liest bei vorhandener Tabelle
allein ``placements.rows[].formats``. Ergebnis: Fehlalarme gegen korrekt
gerenderte Mails (#3156-Abnahme: 12 SOLL-Verletzungen).

Kern-Schicht, ohne Mock: Eingabe ist rohes Abo-JSON (Trip bzw. Orte-Preset),
geprueft wird die Soll-Struktur des echten Moduls aus ``.claude/hooks``. Die
erwarteten Formen stehen von Hand im Test (Katalog-Standard laut
``docs/reference``: Regen-W. Roh, Bewoelkung Einfach), nie aus einer
``resolve_*``-Produktfunktion. AC-12 laeuft zusaetzlich End-to-End: echte
Mail ueber den Versandweg, echter Validator-Prozess mit ``--konfig``.
"""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = _ROOT / "tests" / "fixtures" / "einstellung_gleich_mail"
#: Gesicherte Soll-Ausgabe VOR #3218 fuer Altbestand ohne Tabelle (AC-10).
GOLDEN_VORHER = _FIXTURES / "soll_ohne_tabelle_vorher_3218.json"

ZAHL, WORT, AMPEL = "zahl", "wort", "ampel"
#: Erwartete Zellformen der Trip-Stundentabelle, von Hand (Spec §2 Punkt 3).
AMPEL_EINFACH = {"HTML": (AMPEL,), "Klartext": (WORT,)}      # Regen-W. Einfach
EINFACH = {"HTML": (WORT, AMPEL), "Klartext": (WORT,)}        # Bewoelkung Einfach
ROH = {"HTML": (ZAHL,), "Klartext": (ZAHL,)}

#: Spaltenkuerzel (Register ``col_label``), von Hand.
RAIN_P, CLOUD, WIND, WDIR = "Rain%", "Cloud", "Wind", "WDir"
#: Zeilennamen der Orte-Vergleichstabelle (``label("de")``), von Hand.
ORTE_CLOUD, ORTE_RAIN_P = "Bewölkung", "Regenwahrscheinlichkeit"


def _soll_modul():
    """Das Soll-Modul der Validatoren direkt aus ``.claude/hooks`` (nur lesen)."""
    pfad = _ROOT / ".claude" / "hooks" / "_soll_aus_konfiguration.py"
    spec = importlib.util.spec_from_file_location("_soll_aus_konfiguration_3218", pfad)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def soll():
    return _soll_modul()


# --------------------------------------------------------------------------- #
# Bausteine (rohes Persistenzformat, feste Daten -> deterministisch)
# --------------------------------------------------------------------------- #
def _eintrag(mid: str, order: int, *, freundlich: bool = False, modus: str | None = None) -> dict:
    e = {"metric_id": mid, "enabled": True, "bucket": "primary", "order": order,
         "use_friendly_format": freundlich}
    if modus is not None:
        e["format_mode"] = modus
    return e


def _zeile(mid: str, **formate) -> dict:
    z: dict = {"metric_id": mid}
    if formate:
        z["formats"] = dict(formate)
    return z


def _trip(metriken: list[dict], *, zeilen: list[dict] | None = None, **display) -> dict:
    """Trip-JSON mit festen Etappen; ``zeilen`` = Tabelle ``placements``."""
    dc: dict = {"trip_id": "soll-3218", "metrics": copy.deepcopy(metriken)}
    if zeilen is not None:
        dc["placements"] = {"version": 1, "rows": copy.deepcopy(zeilen)}
    dc.update(copy.deepcopy(display))
    return {
        "id": "soll-3218", "name": "Soll 3218",
        "stages": [{"id": f"T{i}", "name": f"Etappe {i}", "date": f"2026-07-0{i + 1}",
                    "waypoints": [{"id": f"G{i}a", "name": "Start", "lat": 47.27, "lon": 11.40,
                                   "elevation_m": 600},
                                  {"id": f"G{i}b", "name": "Ziel", "lat": 47.29, "lon": 11.42,
                                   "elevation_m": 900}]} for i in range(3)],
        "official_alerts_enabled": False, "official_warnings": {"enabled": False},
        "display_config": dc,
        "report_config": {"trip_id": "soll-3218", "enabled": True,
                          "morning_time": "07:00:00", "evening_time": "18:00:00",
                          "send_email": True, "send_sms": False, "send_telegram": False,
                          "send_premium_sms": False, "email_format": "full"},
    }


def _orte(display: dict) -> dict:
    preset = json.loads((_FIXTURES / "orte_basis.json").read_text(encoding="utf-8"))
    preset["display_config"] = copy.deepcopy(display)
    return preset


def _orte_grund(*mids_agg) -> list[dict]:
    return [{"metric_id": m, "aggregation": a} for m, a in mids_agg]


_ORTE_GRUND = _orte_grund(("temperature", "max"), ("cloud_total", "avg"),
                          ("rain_probability", "max"), ("wind", "max"))


# --------------------------------------------------------------------------- #
# AC-1 / AC-2: Tabelle Einfach schlaegt Altfeld Roh (Trip-Stundentabelle)
# --------------------------------------------------------------------------- #
def test_ac1_ampel_groesse_tabelle_einfach_schlaegt_altfeld_roh(soll):
    """AC-1: Regen-W. ``formats.email=simplified``, Altfeld ``use_friendly_format=false``
    -> HTML Ampelpunkt, Klartext Wortstufe (nicht Zahl)."""
    trip = _trip([_eintrag("temperature", 0), _eintrag("rain_probability", 1)],
                 zeilen=[_zeile("temperature"), _zeile("rain_probability", email="simplified")])
    s = soll.trip_soll(trip, "evening")
    assert s["formen_stunden"][RAIN_P] == AMPEL_EINFACH, s["formen_stunden"]


def test_ac2_nicht_ampel_groesse_tabelle_einfach_schlaegt_altfeld_roh(soll):
    """AC-2: Bewoelkung (zwei Formen, keine Ampel) ``formats.email=simplified``,
    Altfeld Roh -> Einfach (Symbol/Wort), ohne Ampel-Sonderfall."""
    trip = _trip([_eintrag("temperature", 0), _eintrag("cloud_total", 1, modus="raw")],
                 zeilen=[_zeile("temperature"), _zeile("cloud_total", email="simplified")])
    s = soll.trip_soll(trip, "evening")
    assert s["formen_stunden"][CLOUD] == EINFACH, s["formen_stunden"]
    assert s["darstellung_stunden"]["cloud_total"] != "raw", s["darstellung_stunden"]


# --------------------------------------------------------------------------- #
# AC-3: Zeile ohne ``formats`` -> Katalog-Standard (Trip und Orte gleich)
# --------------------------------------------------------------------------- #
def test_ac3_trip_zeile_ohne_formats_gilt_katalog_standard(soll):
    """Altfelder stehen jeweils GEGEN den Standard: Regen-W. Einfach (Standard
    Roh), Bewoelkung Roh (Standard Einfach)."""
    trip = _trip([_eintrag("rain_probability", 0, freundlich=True, modus="simplified"),
                  _eintrag("cloud_total", 1, modus="raw")],
                 zeilen=[_zeile("rain_probability"), _zeile("cloud_total")])
    s = soll.trip_soll(trip, "evening")
    assert s["formen_stunden"][RAIN_P] == ROH, s["formen_stunden"]
    assert s["formen_stunden"][CLOUD] == EINFACH, s["formen_stunden"]


def test_ac3_orte_zeile_ohne_formats_gilt_katalog_standard(soll):
    preset = _orte({
        "active_metrics": _ORTE_GRUND,
        "channel_layouts": {"email": [
            {"metric_id": "temperature"}, {"metric_id": "cloud_total", "format": "raw"},
            {"metric_id": "rain_probability", "format": "simplified"}, {"metric_id": "wind"}]},
        "placements": {"version": 1, "rows": [
            _zeile("temperature"), _zeile("cloud_total"), _zeile("rain_probability"),
            _zeile("wind")]},
    })
    s = soll.orte_soll(preset, "de")
    assert ORTE_CLOUD in s["uebersicht_einfach"], s["uebersicht_einfach"]
    assert ORTE_RAIN_P not in s["uebersicht_einfach"], s["uebersicht_einfach"]


# --------------------------------------------------------------------------- #
# AC-4: Tabelle Roh schlaegt Altfeld Einfach
# --------------------------------------------------------------------------- #
def test_ac4_tabelle_roh_schlaegt_altfeld_einfach(soll):
    trip = _trip([_eintrag("rain_probability", 0, freundlich=True, modus="simplified"),
                  _eintrag("cloud_total", 1, freundlich=True)],
                 zeilen=[_zeile("rain_probability", email="raw"),
                         _zeile("cloud_total", email="raw")])
    s = soll.trip_soll(trip, "evening")
    assert s["formen_stunden"][RAIN_P] == ROH, s["formen_stunden"]
    assert s["formen_stunden"][CLOUD] == ROH, s["formen_stunden"]
    assert s["darstellung_stunden"]["cloud_total"] == "raw", s["darstellung_stunden"]


# --------------------------------------------------------------------------- #
# AC-5: Muellwerte in ``formats`` ohne Wirkung -> Katalog-Standard
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("formate", [{"foo": "raw"}, {"email": "bunt"}, {"email": None},
                                     {"email": ["simplified"]}])
def test_ac5_muellwerte_in_formats_gilt_katalog_standard(soll, formate):
    trip = _trip([_eintrag("rain_probability", 0, freundlich=True, modus="simplified"),
                  _eintrag("cloud_total", 1, modus="raw")],
                 zeilen=[{"metric_id": "rain_probability", "formats": dict(formate)},
                         {"metric_id": "cloud_total", "formats": dict(formate)}])
    s = soll.trip_soll(trip, "evening")
    assert s["formen_stunden"][RAIN_P] == ROH, (formate, s["formen_stunden"])
    assert s["formen_stunden"][CLOUD] == EINFACH, (formate, s["formen_stunden"])


# --------------------------------------------------------------------------- #
# AC-6: doppelte ``metric_id`` -> die erste Zeile gilt
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("erste, zweite, erwartet", [
    ("raw", "simplified", ROH),
    ("simplified", "raw", EINFACH),
])
def test_ac6_doppelte_metric_id_erste_zeile_gilt(soll, erste, zweite, erwartet):
    trip = _trip([_eintrag("cloud_total", 0, freundlich=True)],
                 zeilen=[_zeile("cloud_total", email=erste), _zeile("cloud_total", email=zweite)])
    s = soll.trip_soll(trip, "evening")
    assert s["formen_stunden"][CLOUD] == erwartet, s["formen_stunden"]


# --------------------------------------------------------------------------- #
# AC-7: Windrichtung Einfach laut Tabelle -> Wind-Verschmelzung bleibt
# --------------------------------------------------------------------------- #
def test_ac7_windrichtung_tabelle_einfach_verschmilzt_mit_wind(soll):
    trip = _trip([_eintrag("wind", 0), _eintrag("wind_direction", 1, modus="raw")],
                 zeilen=[_zeile("wind"), _zeile("wind_direction", email="simplified")])
    s = soll.trip_soll(trip, "evening")
    assert s["wind_richtung"] is True, s
    assert WDIR not in s["stunden"] and WIND in s["stunden"], s["stunden"]


def test_ac7_windrichtung_tabelle_roh_bleibt_eigene_spalte(soll):
    """Gegenprobe: Altfeld Einfach (Skala), Tabelle Roh -> eigene WDir-Spalte."""
    trip = _trip([_eintrag("wind", 0), _eintrag("wind_direction", 1, freundlich=True)],
                 zeilen=[_zeile("wind"), _zeile("wind_direction", email="raw")])
    s = soll.trip_soll(trip, "evening")
    assert s["wind_richtung"] is False, s
    assert WDIR in s["stunden"], s["stunden"]


# --------------------------------------------------------------------------- #
# AC-8: Orte-Vergleichstabelle folgt ``formats.email``, nicht ``channel_layouts.email``
# --------------------------------------------------------------------------- #
def test_ac8_orte_vergleichstabelle_folgt_tabelle(soll):
    preset = _orte({
        "active_metrics": _ORTE_GRUND,
        "channel_layouts": {"email": [
            {"metric_id": "temperature"}, {"metric_id": "cloud_total", "format": "raw"},
            {"metric_id": "rain_probability", "format": "simplified"}, {"metric_id": "wind"}]},
        "placements": {"version": 1, "rows": [
            _zeile("temperature"), _zeile("cloud_total", email="simplified"),
            _zeile("rain_probability", email="raw"), _zeile("wind")]},
    })
    s = soll.orte_soll(preset, "de")
    assert ORTE_CLOUD in s["uebersicht_einfach"], s["uebersicht_einfach"]
    assert ORTE_RAIN_P not in s["uebersicht_einfach"], s["uebersicht_einfach"]
    assert s["uebersicht_formen"][ORTE_RAIN_P] == ROH, s["uebersicht_formen"]


# --------------------------------------------------------------------------- #
# AC-9: Ausblick folgt ``formats.outlook`` statt ``outlook_metric_formats``
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("tabelle, altfeld, erwartet", [
    ("simplified", False, "einfach"),
    ("raw", True, "roh"),
])
def test_ac9_trip_ausblick_folgt_tabelle(soll, tabelle, altfeld, erwartet):
    trip = _trip([_eintrag("temperature", 0), _eintrag("cloud_total", 1)],
                 zeilen=[_zeile("temperature"), _zeile("cloud_total", outlook=tabelle)],
                 outlook_metrics=["temperature", "cloud_total"],
                 outlook_metric_formats={"cloud_total": altfeld})
    s = soll.trip_soll(trip, "evening")
    assert s["ausblick"]["darstellung"]["cloud_total"] == erwartet, s["ausblick"]
    assert s["ausblick"]["formen"][CLOUD] == (EINFACH if erwartet == "einfach" else ROH), s["ausblick"]


@pytest.mark.parametrize("tabelle, altfeld, erwartet", [
    ("simplified", False, "einfach"),
    ("raw", True, "roh"),
])
def test_ac9_orte_ausblick_folgt_tabelle(soll, tabelle, altfeld, erwartet):
    preset = _orte({
        "active_metrics": _ORTE_GRUND,
        "outlook_metrics": ["temperature", "cloud_total"],
        "outlook_metric_formats": {"cloud_total": altfeld},
        "placements": {"version": 1, "rows": [
            _zeile("temperature"), _zeile("cloud_total", outlook=tabelle),
            _zeile("rain_probability"), _zeile("wind")]},
    })
    s = soll.orte_soll(preset, "de")
    assert s["ausblick"]["darstellung"]["cloud_total"] == erwartet, s["ausblick"]


# --------------------------------------------------------------------------- #
# AC-10: Altbestand ohne Tabelle -> Soll bytegleich zu vorher
# --------------------------------------------------------------------------- #
def _kanon(obj):
    """Kanonische, JSON-faehige Form (Mengen sortiert, Tupel als Liste)."""
    if isinstance(obj, dict):
        return {str(k): _kanon(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_kanon(v) for v in obj]
    if isinstance(obj, (set, frozenset)):
        return sorted((_kanon(v) for v in obj), key=repr)
    return obj


def altbestand_eingaben() -> dict[str, dict]:
    """Abos OHNE Tabelle: alle Orte-/Trip-Fixtures des Pruefkatalogs ohne
    ``placements`` plus Trip-Varianten je Darstellung (roh/gemischt/einfach,
    Kanal-Liste, Ausblick-Formate, Windrichtung Skala)."""
    eingaben: dict[str, dict] = {}
    for pfad in sorted(_FIXTURES.glob("*.json")):
        daten = json.loads(pfad.read_text(encoding="utf-8"))
        if not isinstance(daten, dict) or "placements" in json.dumps(daten):
            continue
        if "location_ids" in daten or ("stages" in daten and "display_config" in daten):
            eingaben[pfad.stem] = daten
    basis = [("temperature", False, None), ("wind", False, None), ("gust", False, None),
             ("wind_direction", False, None), ("precipitation", False, None),
             ("rain_probability", False, None), ("cloud_total", False, None)]
    for name, einfach in (("roh", set()), ("einfach", {m for m, _f, _x in basis}),
                          ("gemischt", {"wind", "rain_probability", "cloud_total"})):
        metriken = [_eintrag(m, i, freundlich=m in einfach,
                             modus="simplified" if m in einfach and m in ("wind", "rain_probability")
                             else None) for i, (m, _f, _x) in enumerate(basis)]
        eingaben[f"trip_{name}"] = _trip(metriken)
        eingaben[f"trip_{name}_ausblick"] = _trip(
            metriken, outlook_metrics=["temperature", "wind", "cloud_total"],
            outlook_metric_formats={"wind": bool(einfach), "cloud_total": not einfach})
        eingaben[f"trip_{name}_kanal"] = _trip(metriken, channel_layouts={"email": [
            {"metric_id": "cloud_total", "use_friendly_format": not einfach},
            {"metric_id": "wind", "use_friendly_format": bool(einfach)},
            {"metric_id": "wind_direction", "format_mode": "scale" if einfach else "raw"}]})
    eingaben["orte_kanal_einfach"] = _orte({
        "active_metrics": _ORTE_GRUND,
        "channel_layouts": {"email": [{"metric_id": "cloud_total", "format": "simplified"},
                                      {"metric_id": "rain_probability", "use_friendly_format": True}]},
        "outlook_metrics": ["temperature", "cloud_total"],
        "outlook_metric_formats": {"cloud_total": True}})
    return eingaben


def soll_ohne_tabelle(soll_mod) -> dict[str, object]:
    return {name: _kanon(soll_mod.soll_aus_daten(copy.deepcopy(daten), "de"))
            for name, daten in altbestand_eingaben().items()}


def test_ac10_altbestand_ohne_tabelle_bytegleich_zu_vorher(soll):
    """Gesicherte Vorher-Ausgabe (erzeugt mit dem Stand vor #3218) gegen jetzt.
    Waechter: die Ueberlagerung darf nur hinter ``_hat_tabelle`` wirken."""
    vorher = GOLDEN_VORHER.read_text(encoding="utf-8")
    jetzt = json.dumps(soll_ohne_tabelle(soll), ensure_ascii=False, sort_keys=True, indent=1)
    assert len(json.loads(vorher)) >= 12, "Vorbedingung: Vorher-Ausgabe deckt den Altbestand ab"
    assert jetzt == vorher


# --------------------------------------------------------------------------- #
# AC-11: Huelle ``orte`` als Liste -> klare Fehlermeldung statt TypeError
# --------------------------------------------------------------------------- #
def test_ac11_orte_huelle_als_liste_klare_fehlermeldung(soll):
    preset = _orte({"active_metrics": _ORTE_GRUND})
    with pytest.raises(ValueError) as fehler:
        soll.soll_aus_daten({"preset": preset, "orte": ["loc-kronplatz", "loc-sulden"]}, "de")
    text = str(fehler.value)
    assert "orte" in text and "<Kennung>" in text and "<Name>" in text, text


def test_ac11_doku_beschreibt_huelle_und_restluecke():  # doc-compliance-test
    doku = (_ROOT / "docs" / "reference" / "mail_validators.md").read_text(encoding="utf-8")
    assert '"orte": {"<Kennung>": "<Name>"}' in doku, "Huelle fehlt in der Doku"
    assert "#3242" in doku and "placements" in doku, "Restluecke Auswahl/Folge (#3242) fehlt"


def test_ac11_validator_start_orte_liste_exit2_statt_traceback(tmp_path):
    """Echter Validator-Prozess: Huelle ``orte`` als Liste endet mit
    ``FEHLER`` und Exit 2 wie die Geschwister-Fehler, nie als Traceback."""
    from tests.helpers.mail_lang_fixture import validator_lauf

    preset = _orte({"active_metrics": _ORTE_GRUND})
    konfig = tmp_path / "orte_liste.json"
    konfig.write_text(json.dumps({"preset": preset, "orte": ["loc-a", "loc-b"]}),
                      encoding="utf-8")
    eml = b"Subject: x\r\nContent-Type: text/plain; charset=utf-8\r\n\r\nx\r\n"
    lauf, _log = validator_lauf(tmp_path, "email_spec_validator", eml,
                                "--konfig", str(konfig))
    aus = lauf.stdout + lauf.stderr
    assert "Traceback" not in aus, aus
    assert lauf.returncode == 2, aus
    assert "FEHLER" in aus and "<Kennung>" in aus, aus


def test_ac11_validator_start_orte_liste_mit_ortsdatei_exit2_statt_traceback(tmp_path):
    """Wie oben, aber zusaetzlich mit gueltiger ``--orte``-Namensdatei: die
    Huellen-Pruefung greift vor dem Zusammenfuehren, kein Traceback."""
    from tests.helpers.mail_lang_fixture import validator_lauf

    preset = _orte({"active_metrics": _ORTE_GRUND})
    konfig = tmp_path / "orte_liste.json"
    konfig.write_text(json.dumps({"preset": preset, "orte": ["loc-a", "loc-b"]}),
                      encoding="utf-8")
    orte = tmp_path / "ortsnamen.json"
    orte.write_text(json.dumps({"loc-a": "Ort A", "loc-b": "Ort B"}), encoding="utf-8")
    eml = b"Subject: x\r\nContent-Type: text/plain; charset=utf-8\r\n\r\nx\r\n"
    lauf, _log = validator_lauf(tmp_path, "email_spec_validator", eml,
                                "--konfig", str(konfig), "--orte", str(orte))
    aus = lauf.stdout + lauf.stderr
    assert "Traceback" not in aus, aus
    assert lauf.returncode == 2, aus
    assert "FEHLER" in aus and "<Kennung>" in aus, aus


# --------------------------------------------------------------------------- #
# AC-12: Abnahme-Fall #3156 -- echte Mail, echter Validator, keine SOLL-Verletzung
# --------------------------------------------------------------------------- #
def _abnahme_daten() -> dict:
    from tests.tdd.test_einstellung_gleich_mail_validatoren import _TRIP_FOLGE, _trip_daten

    daten = _trip_daten(_TRIP_FOLGE)
    dc = daten["display_config"]
    dc["metrics"] += [
        {"metric_id": "rain_probability", "enabled": True, "bucket": "primary", "order": 4,
         "use_friendly_format": False},
        {"metric_id": "cloud_total", "enabled": True, "bucket": "primary", "order": 5,
         "use_friendly_format": False},
    ]
    dc["placements"] = {"version": 1, "rows": [
        _zeile("gust"), _zeile("temperature"), _zeile("precipitation"), _zeile("wind"),
        _zeile("rain_probability", email="simplified"), _zeile("cloud_total")]}
    # Auswahl/Folge deckungsgleich zur Tabelle, weil das Soll sie bis #3242 aus Altfeldern liest.
    dc["outlook_metrics"] = ["gust", "temperature", "precipitation", "wind",
                             "rain_probability", "cloud_total"]
    return daten


def test_ac12_abnahme_3156_soll_formen(soll):
    s = soll.soll_aus_daten(_abnahme_daten(), "de")["je_report"]["evening"]
    assert s["formen_stunden"][RAIN_P] == AMPEL_EINFACH, s["formen_stunden"]
    assert s["formen_stunden"][CLOUD] == EINFACH, s["formen_stunden"]


def test_ac12_abnahme_3156_echte_mail_ohne_soll_verletzung(monkeypatch, tmp_path):
    from tests.tdd.test_einstellung_gleich_mail_validatoren import _konfig, _lauf, _trip_eml

    daten = _abnahme_daten()
    eml = _trip_eml(monkeypatch, daten)
    code, aus = _lauf(tmp_path, "briefing_mail_validator", eml, "--konfig",
                      _konfig(tmp_path, "abnahme_3156", daten))
    assert "soll Zahl (Roh) zeigen" not in aus, aus
    assert "SOLL: Darstellung" not in aus, aus
    assert code == 0, aus


# --------------------------------------------------------------------------- #
# AC-13: abgeleitete Groesse ohne eigene Zeile
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("eltern_zeile", [True, False])
def test_ac13_abgeleitete_groesse_ohne_eigene_zeile(soll, eltern_zeile):
    """Nachttief (Kind von Temperatur) ohne eigene Tabellenzeile. Mit
    Eltern-Zeile erbt es deren Form, ohne den Katalog-Standard; Temperatur
    kennt nur Roh, also in beiden Faellen Roh -- auch wenn das Altfeld des
    Kindes Einfach behauptet (Altfelder gelten mit Tabelle nicht)."""
    zeilen = [_zeile("wind")]
    if eltern_zeile:
        zeilen.insert(0, _zeile("temperature", email="simplified"))
    trip = _trip([_eintrag("temperature", 0), _eintrag("wind", 1),
                  _eintrag("temperature_night", 2, freundlich=True, modus="simplified")],
                 zeilen=zeilen)
    s = soll.trip_soll(trip, "evening")
    assert s["darstellung_stunden"]["temperature_night"] == "raw", s["darstellung_stunden"]
