"""#3273: Validator-Soll (``--konfig``) -- Trip ohne ``metrics`` mit Tabelle.

SPEC: docs/specs/modules/fix_3273_trip_grundauswahl_ohne_metrics.md (AC-1 .. AC-10)

Das Produkt (``app.loader``, #3122 B2b) liest bei einem Trip, dessen
``display_config`` fehlt oder nur die Tabelle ``placements`` traegt, die
Grundauswahl wie bei fehlendem Schluessel: ``weather_config`` (Altnamen),
sonst die Vorlage des Profils. Das Soll nahm stattdessen den Register-Standard
-> Fehlalarme (Issue #3273: 12 SOLL-Verletzungen).

Kern-Schicht, ohne Mock: Eingabe ist rohes Trip-JSON, geprueft wird das echte
Soll-Modul aus ``.claude/hooks``. Erwartete Listen stehen von Hand im Test;
nur der Gleichlauf-Test (AC-8) vergleicht zusaetzlich mit dem echten Loader.
"""
from __future__ import annotations

import ast
import copy
import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

#: Profil-Vorlagen in Register-Folge, von Hand (WEATHER_TEMPLATES, Katalogfolge).
ALLGEMEIN = ["temperature", "temperature_night", "wind", "gust", "precipitation",
             "rain_probability", "cloud_total", "sunshine"]
PROFILE = {
    "allgemein": ALLGEMEIN,
    "summer_trekking": ALLGEMEIN,
    "wandern": ["temperature", "temperature_night", "humidity", "wind", "gust", "precipitation",
                "rain_probability", "cloud_total", "sunshine", "uv_index"],
    "wintersport": ["temperature", "temperature_night", "wind_chill", "wind", "gust",
                    "precipitation", "cloud_total", "visibility", "sunshine", "snow_depth",
                    "fresh_snow"],
}
#: Register-Standard (``trip_default_rank``), von Hand -- bisheriges Soll ohne ``metrics``.
REGISTER = ["temperature", "wind", "gust", "precipitation", "thunder", "freezing_level",
            "visibility", "temperature_day_low", "temperature_day_high"]
#: weather_config mit Altnamen (ein unbekannter Name), erwartet in Register-Folge.
ALTNAMEN = ["temp_max_c", "cloud_avg_pct", "wind_max_kmh", "thunder_level_max", "gibt_es_nicht"]
AUS_ALTNAMEN = ["temperature", "wind", "thunder", "cloud_total"]


def _soll_modul():
    pfad = _ROOT / ".claude" / "hooks" / "_soll_aus_konfiguration.py"
    spec = importlib.util.spec_from_file_location("_soll_aus_konfiguration_3273", pfad)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def soll():
    return _soll_modul()


def _zeile(mid: str, email: bool = True) -> dict:
    return {"metric_id": mid, "places": {"email": email}}


#: Befundfall aus dem Issue: Tabelle mit umgekehrter Folge, zweite Zeile E-Mail aus.
BEFUND_ZEILEN = [_zeile("sunshine"), _zeile("cloud_total", email=False),
                 _zeile("rain_probability"), _zeile("precipitation"), _zeile("gust"),
                 _zeile("wind"), _zeile("temperature")]


def _trip(**extra) -> dict:
    trip = {"id": "t3273", "name": "Testtrip", "stages": []}
    trip.update(extra)
    return trip


def _nur_tabelle(rows: list | None = None) -> dict:
    return {"placements": {"rows": copy.deepcopy(rows if rows is not None else [])}}


def _wc(namen: list[str]) -> dict:
    return {"trip_id": "t3273", "enabled_metrics": list(namen),
            "updated_at": "2026-11-01T00:00:00+00:00"}


def _grund(soll, trip: dict) -> list[str]:
    """Grundauswahl des Solls (Abend), in der Folge, die das Soll ansetzt."""
    dc = soll._trip_display_config(trip)
    return [e["metric_id"] for e in soll._sortiert(
        [e for e in soll._eintraege(dc.get("metrics"))
         if soll._waehlbar(e.get("metric_id")) and soll._an(e, "evening")])]


# --------------------------------------------------------------------------- #
# AC-1: Befundfall
# --------------------------------------------------------------------------- #
def test_ac1_befundfall_spalten_wie_produkt(soll):
    """GIVEN Profil allgemein, display_config nur placements (umgekehrt, 2. Zeile E-Mail aus)
    WHEN Soll THEN Stundenspalten wie die Staging-Mail aus dem Issue."""
    trip = _trip(aggregation={"profile": "allgemein"}, display_config=_nur_tabelle(BEFUND_ZEILEN))
    s = soll.trip_soll(trip, "evening")
    assert s["stunden"] == ["Sun", "Rain%", "Rain", "Gust", "Wind", "Temp"]
    for falsch in ("Thdr", "0°Line", "Visib"):
        assert falsch not in s["stunden"]


def test_ac1_grundauswahl_profil_allgemein(soll):
    trip = _trip(aggregation={"profile": "allgemein"}, display_config=_nur_tabelle(BEFUND_ZEILEN))
    assert _grund(soll, trip) == ALLGEMEIN


# --------------------------------------------------------------------------- #
# AC-2: display_config fehlt -> Profil-Vorlage
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("profil", sorted(PROFILE))
def test_ac2_ohne_display_config_profilvorlage(soll, profil):
    trip = _trip(aggregation={"profile": profil})
    assert _grund(soll, trip) == PROFILE[profil]


# --------------------------------------------------------------------------- #
# AC-3: weather_config hat Vorrang vor dem Profil
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("dc", [None, "nur_tabelle"])
def test_ac3_weather_config_altnamen(soll, dc):
    trip = _trip(aggregation={"profile": "wandern"}, weather_config=_wc(ALTNAMEN))
    if dc == "nur_tabelle":
        trip["display_config"] = _nur_tabelle()
    assert _grund(soll, trip) == AUS_ALTNAMEN


# --------------------------------------------------------------------------- #
# AC-4: Profil fehlend / null / unbekannt -> allgemein
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("agg", [None, {"profile": None}, {"profile": "gibt_es_nicht"}, {}])
def test_ac4_profil_rueckfall_allgemein(soll, agg):
    trip = _trip(display_config=_nur_tabelle())
    if agg is not None:
        trip["aggregation"] = agg
    assert _grund(soll, trip) == ALLGEMEIN


# --------------------------------------------------------------------------- #
# AC-5: display_config null oder mit weiteren Schluesseln -> Register-Standard
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("dc", [None, {"placements": {"rows": []}, "show_night_block": True},
                                {"metrics": []}])
def test_ac5_register_standard_bleibt(soll, dc):
    trip = _trip(aggregation={"profile": "wandern"}, display_config=dc)
    assert _grund(soll, trip) == REGISTER


# --------------------------------------------------------------------------- #
# AC-6: nackte display_config (ohne Trip-Huelle) unveraendert
# --------------------------------------------------------------------------- #
def test_ac6_nackte_display_config_unveraendert(soll):
    assert _grund(soll, {"placements": {"rows": []}}) == REGISTER
    gespeichert = {"metrics": [{"metric_id": "wind", "enabled": True, "bucket": "primary", "order": 0},
                               {"metric_id": "gust", "enabled": True, "bucket": "primary", "order": 1}]}
    assert _grund(soll, gespeichert) == ["wind", "gust"]


# --------------------------------------------------------------------------- #
# AC-7: Tabelle bleibt erhalten
# --------------------------------------------------------------------------- #
def test_ac7_placements_bleibt_erhalten(soll):
    trip = _trip(aggregation={"profile": "allgemein"}, display_config=_nur_tabelle(BEFUND_ZEILEN))
    dc = soll._trip_display_config(trip)
    assert dc["placements"] == {"rows": BEFUND_ZEILEN}


# --------------------------------------------------------------------------- #
# AC-8: Gleichlauf mit dem echten Loader
# --------------------------------------------------------------------------- #
def _varianten():
    for profil in sorted(PROFILE):
        agg = {"profile": profil}
        yield f"{profil}-fehlt", _trip(aggregation=agg)
        yield f"{profil}-nur_tabelle", _trip(aggregation=agg, display_config=_nur_tabelle(BEFUND_ZEILEN))
        yield f"{profil}-null", _trip(aggregation=agg, display_config=None)
        yield f"{profil}-weather_config", _trip(aggregation=agg, weather_config=_wc(ALTNAMEN))
        yield f"{profil}-wc_nur_tabelle", _trip(aggregation=agg, weather_config=_wc(ALTNAMEN),
                                                 display_config=_nur_tabelle())


@pytest.mark.parametrize("name,trip", list(_varianten()), ids=[n for n, _t in _varianten()])
def test_ac8_gleichlauf_mit_echtem_loader(soll, name, trip):
    from app.loader import load_trip_from_dict
    from services.channel_list_resolver import grundauswahl

    geladen = load_trip_from_dict(copy.deepcopy(trip))
    produkt = list(grundauswahl(geladen.display_config, "trip", "evening").ids)
    assert _grund(soll, trip) == produkt, name


# --------------------------------------------------------------------------- #
# AC-10: Spiegel-Verbot im neuen Pfad
# --------------------------------------------------------------------------- #
def test_ac10_kein_resolve_im_trip_display_config():  # doc-compliance-test
    quelle = (_ROOT / ".claude" / "hooks" / "_soll_aus_konfiguration.py").read_text(encoding="utf-8")
    baum = ast.parse(quelle)
    verboten = {"resolve_rows", "resolve_channel_lists", "placements_view", "_cell", "metrics_at",
                "build_default_display_config_for_profile", "tabellen_grundauswahl",
                "grundauswahl", "_migrate_weather_config", "load_trip_from_dict"}
    funktionen = {n.name: n for n in ast.walk(baum) if isinstance(n, ast.FunctionDef)}
    pfad = funktionen["_trip_display_config"]
    aufrufe = {getattr(c.func, "id", getattr(c.func, "attr", None))
               for c in ast.walk(pfad) if isinstance(c, ast.Call)}
    # auch Hilfsfunktionen des Moduls, die der Pfad aufruft
    for name in list(aufrufe):
        if name in funktionen and name != "_trip_display_config":
            aufrufe |= {getattr(c.func, "id", getattr(c.func, "attr", None))
                        for c in ast.walk(funktionen[name]) if isinstance(c, ast.Call)}
    assert not (aufrufe & verboten), aufrufe & verboten
