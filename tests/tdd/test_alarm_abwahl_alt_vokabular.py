"""Issue #1981 — Alarm-Abwahl wirkt nicht, wenn `metric_alert_levels` einen
Alt-Schluessel im Summary-Vokabular (`temp_max_c` statt `temperature_max`) traegt.

SPEC:    docs/specs/modules/fix_1981_alarm_abwahl_alt_vokabular.md
KONTEXT: docs/context/fix-1981-alarm-abwahl-vokabular.md

WORUM ES GEHT:
`expand_per_metric_levels` verwirft unbekannte Schluessel still
(`AlertMetric(...)` -> ValueError -> continue). Steht die Abwahl unter
`temp_max_c: "off"`, sieht die Auswertung keinen Eintrag fuer
`temperature_max`; der #961-Backfill (Metrik in `active_metrics` aktiv) setzt
dort `standard` -> die Regel entsteht trotz Abwahl.

PRUEFORT = WIRKORT. Gefahren wird die echte Produktionskette wie in
`compare_preset_access.py:33`: Preset-Datei unter `briefings/<id>.json` ->
`load_compare_presets` -> `compare_preset_to_dict` (der Roh-Dict, den der
Alarm-Pfad liest) -> `CompareAlertService._build_eval_config` ->
`expand_per_metric_levels` mit denselben drei Argumenten wie
`DeviationAlertEngine._select_detector`. Kein `Mock()`/`patch()`.

Die Faelle fuer den Normalisierer (AC-4/5/9) stehen in der gemeinsamen Fixture
`tests/fixtures/metric_alert_levels_alt_vokabular/faelle.json`, die auch der
Go-Test liest (Go <-> Python-Paritaet).

RED (schlaegt HEUTE fehl):
  - test_temp_max_off_alt_schluessel_erzeugt_keine_regel          (AC-1)
  - test_temp_max_off_alt_schluessel_ohne_active_metrics          (AC-1, Rueckfallpfad)
  - test_gust_off_alt_schluessel_gilt_unter_alarm_namen           (AC-2)
  - test_neu_schluessel_gewinnt_alt_wird_entfernt                 (AC-3)
  - test_normalisierer_faelle_aus_gemeinsamer_fixture             (AC-4/AC-9)
  - test_normalisierer_zweiter_lauf_ist_no_op                     (AC-5)
  - test_nur_wind_chill_ergibt_leere_map_und_standard_satz        (AC-6, Map-Haelfte)
  - test_trip_ladepfad_uebersetzt_summary_und_snow_line           (AC-7)
  - test_cape_off_alt_schluessel_entfernt_cape_regel              (AC-10)

GUARD (HEUTE gruen, darf nicht kippen):
  - test_trip_ohne_alt_schluessel_bleibt_unveraendert             (AC-7, zweite Haelfte)
  - test_uebersetzungstabelle_deckt_sich_mit_katalog              (AC-8)
  - AC-6 Regel-Haelfte (Regelmenge == Standard-Satz) innerhalb des AC-6-Tests
  - AC-10 zweite Haelfte: bestehende
    `test_compare_alert_missing_active_metrics_with_levels.py` (CAPE bleibt)

Pfadregel #1409: Prueflinge und Fixture RELATIV ZU DIESER DATEI aufloesen.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "src"))

from app.config import Settings  # noqa: E402
from app.loader import (  # noqa: E402
    compare_preset_to_dict, load_compare_presets, load_trip_from_dict,
)
from app.metric_catalog import _METRICS_BY_ID, alert_metric_for  # noqa: E402
from services.alert_preset import expand_per_metric_levels  # noqa: E402
from services.compare_alert import CompareAlertService  # noqa: E402

_FIXTURE = _REPO / "tests" / "fixtures" / "metric_alert_levels_alt_vokabular" / "faelle.json"
_USER = "tdd-1981"

# Realistischer Editor-Stand: Temperatur, Boeen, CAPE usw. sind im
# Vergleich AKTIV -- genau dann setzt der #961-Backfill `standard` und die
# Alt-Abwahl wird wirkungslos (Le-Var-Maskierung ausgeschlossen).
_ACTIVE_ALLE = [
    "temp_max_c", "temp_min_c", "wind_max_kmh", "gust_max_kmh",
    "precip_sum_mm", "thunder_level_max", "visibility_min_m", "cape_max_jkg",
]


def _faelle() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def _schreibe_preset(data_root: Path, levels: dict | None,
                     active_metrics: list[str] | None, pid: str = "cp-1981") -> None:
    """Legt eine Vergleichsdatei so ab, wie Go sie unter `briefings/` schreibt."""
    display_config: dict = {}
    if levels is not None:
        display_config["metric_alert_levels"] = copy.deepcopy(levels)
    if active_metrics is not None:
        display_config["active_metrics"] = list(active_metrics)
    preset = {
        "id": pid, "name": pid, "user_id": _USER, "kind": "vergleich",
        "location_ids": [], "schedule": "daily", "hour_from": 9, "hour_to": 16,
        "empfaenger": ["gregor-test@henemm.com"],
    }
    if display_config:
        preset["display_config"] = display_config
    ordner = data_root / "users" / _USER / "briefings"
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / f"{pid}.json").write_text(json.dumps(preset), encoding="utf-8")


def _geladen(data_root: Path) -> dict:
    """Produktions-Ladepfad des Alarm-Dienstes (`compare_preset_access.py:33`)."""
    presets = [compare_preset_to_dict(p)
               for p in load_compare_presets(_USER, data_root=data_root)]
    assert len(presets) == 1, presets
    return presets[0]


def _geladene_levels(data_root: Path) -> dict:
    return (_geladen(data_root).get("display_config") or {}).get("metric_alert_levels")


def _regel_namen(data_root: Path) -> list[str]:
    """Regelmenge GENAU wie `DeviationAlertEngine._select_detector` sie bildet."""
    service = CompareAlertService(
        settings=Settings(smtp_host="dummy.invalid", smtp_user="dummy",
                          smtp_pass="dummy", mail_to="dummy@example.com"),
        user_id=_USER,
    )
    config = service._build_eval_config(_geladen(data_root), 120, {})
    regeln = expand_per_metric_levels(
        config.metric_alert_levels or {},
        display_config=config.display_config,
        supplement_missing_levels=config.supplement_missing_levels,
    )
    return sorted(str(r.metric) for r in regeln)


def _lade_levels_ueber_loader(tmp_path: Path, levels: dict, unterordner: str) -> dict:
    root = tmp_path / unterordner
    _schreibe_preset(root, levels, None)
    return _geladene_levels(root)


# ══════════════════════════════ AC-1 ═════════════════════════════════════════

def test_temp_max_off_alt_schluessel_erzeugt_keine_regel(tmp_path):
    """AC-1 GIVEN ein Vergleich mit `temp_max_c: "off"` (Alt-Vokabular) und
    aktiver Temperatur im Editor WHEN geladen und die Regelbildung am Wirkort
    laeuft THEN entsteht keine `temperature_max`-Regel."""
    _schreibe_preset(tmp_path, {"temp_max_c": "off"}, _ACTIVE_ALLE)

    namen = _regel_namen(tmp_path)

    assert "temperature_max" not in namen, (
        "Abwahl wirkt nicht: `temp_max_c: off` ist gespeichert, trotzdem "
        f"entsteht eine `temperature_max`-Regel. Regeln: {namen!r}"
    )


def test_temp_max_off_alt_schluessel_ohne_active_metrics(tmp_path):
    """AC-1 (Rueckfallpfad #1971) GIVEN Alt-Preset ohne `active_metrics` mit
    `temp_max_c: "off"` WHEN Regelbildung THEN keine `temperature_max`-Regel
    (das Nachfuellen `supplement_missing_levels` darf die Abwahl nicht
    ueberschreiben, nur weil sie unter dem Alt-Schluessel steht)."""
    _schreibe_preset(tmp_path, {"temp_max_c": "off"}, None)

    namen = _regel_namen(tmp_path)

    assert "temperature_max" not in namen, (
        "Abwahl wirkt im Rueckfallpfad nicht: `temp_max_c: off` gespeichert, "
        f"Nachfuellen erzeugt `temperature_max`. Regeln: {namen!r}"
    )


# ══════════════════════════════ AC-2 ═════════════════════════════════════════

def test_gust_off_alt_schluessel_gilt_unter_alarm_namen(tmp_path):
    """AC-2 (Python) GIVEN `gust_max_kmh: "off"` WHEN geladen THEN steht die
    gespeicherte Stufe unter `wind_gust` -- und genau diese Stufe wirkt."""
    _schreibe_preset(tmp_path, {"gust_max_kmh": "off"}, _ACTIVE_ALLE)

    levels = _geladene_levels(tmp_path)
    namen = _regel_namen(tmp_path)

    assert levels == {"wind_gust": "off"}, (
        f"Gespeicherte Stufe nicht unter dem Alarm-Namen: {levels!r}"
    )
    assert "wind_gust" not in namen, (
        f"`wind_gust` ist abgewaehlt, Regel entsteht trotzdem: {namen!r}"
    )


# ══════════════════════════════ AC-3 ═════════════════════════════════════════

def test_neu_schluessel_gewinnt_alt_wird_entfernt(tmp_path):
    """AC-3 GIVEN `temp_max_c: off` UND `temperature_max: standard` WHEN
    geladen THEN gewinnt `standard`, der Alt-Schluessel ist weg."""
    _schreibe_preset(
        tmp_path, {"temp_max_c": "off", "temperature_max": "standard"}, _ACTIVE_ALLE,
    )

    levels = _geladene_levels(tmp_path)

    assert levels == {"temperature_max": "standard"}, (
        f"Vorrang/Entfernen verletzt (#959-Muster): {levels!r}"
    )
    assert "temperature_max" in _regel_namen(tmp_path)


# ══════════════════════════════ AC-4 / AC-9 ══════════════════════════════════

def test_normalisierer_faelle_aus_gemeinsamer_fixture(tmp_path):
    """AC-4 + AC-9 (Python) GIVEN jeder Fall der gemeinsamen Fixture WHEN der
    Vergleich ueber den Produktions-Ladepfad geladen wird THEN entspricht
    `metric_alert_levels` exakt `erwartet` -- fremde Schluessel bleiben mit
    Wert erhalten (Merge, kein Neuaufbau). Derselbe Satz laeuft im Go-Test."""
    abweichungen = []
    for fall in _faelle()["faelle"]:
        ist = _lade_levels_ueber_loader(tmp_path, fall["eingabe"], fall["name"])
        if ist != fall["erwartet"]:
            abweichungen.append((fall["name"], fall["erwartet"], ist))

    assert not abweichungen, "Fixture-Faelle verletzt:\n" + "\n".join(
        f"  {name}: erwartet {soll!r}, erhalten {ist!r}"
        for name, soll, ist in abweichungen
    )


# ══════════════════════════════ AC-5 ═════════════════════════════════════════

def test_normalisierer_zweiter_lauf_ist_no_op(tmp_path):
    """AC-5 GIVEN das Ergebnis eines ersten Ladens WHEN es erneut gespeichert
    und geladen wird THEN ist es identisch (normalize(normalize(x)) == normalize(x))."""
    abweichungen = []
    for fall in _faelle()["faelle"]:
        erster = _lade_levels_ueber_loader(tmp_path, fall["eingabe"], fall["name"] + "-1")
        zweiter = _lade_levels_ueber_loader(tmp_path, erster or {}, fall["name"] + "-2")
        if erster != fall["erwartet"] or zweiter != erster:
            abweichungen.append((fall["name"], erster, zweiter))

    assert not abweichungen, "Nicht idempotent / nicht normalisiert:\n" + "\n".join(
        f"  {name}: 1. Lauf {a!r}, 2. Lauf {b!r}" for name, a, b in abweichungen
    )


# ══════════════════════════════ AC-6 ═════════════════════════════════════════

def test_nur_wind_chill_ergibt_leere_map_und_standard_satz(tmp_path):
    """AC-6 GIVEN nur `wind_chill_min_c: off` WHEN geladen und Regelbildung
    THEN ist die Map leer und die Regelmenge gleich der eines Presets ohne
    `metric_alert_levels` (Rueckfall `or _STANDARD_METRIC_LEVELS`)."""
    mit = tmp_path / "mit"
    ohne = tmp_path / "ohne"
    _schreibe_preset(mit, {"wind_chill_min_c": "off"}, None)
    _schreibe_preset(ohne, None, None)

    # GUARD-Haelfte: Regelmenge unveraendert gegenueber dem Standard-Satz.
    assert _regel_namen(mit) == _regel_namen(ohne)
    # RED-Haelfte: der Alt-Schluessel ohne Alarm-Identitaet ist verworfen.
    assert _geladene_levels(mit) == {}, (
        f"`wind_chill_min_c` haette verworfen werden muessen: {_geladene_levels(mit)!r}"
    )


# ══════════════════════════════ AC-7 ═════════════════════════════════════════

def _trip_dict(levels: dict) -> dict:
    return {
        "id": "trip-1981", "name": "Trip 1981", "stages": [],
        "display_config": {
            "trip_id": "trip-1981", "metrics": [],
            "metric_alert_levels": copy.deepcopy(levels),
        },
    }


def test_trip_ladepfad_uebersetzt_summary_und_snow_line():
    """AC-7 (Python) GIVEN ein Trip mit `snow_line` und `temp_max_c` WHEN
    geladen THEN `freezing_level` wie bisher (#959) UND `temperature_max`."""
    trip = load_trip_from_dict(_trip_dict({"snow_line": "sensibel", "temp_max_c": "off"}))

    assert trip.display_config.metric_alert_levels == {
        "freezing_level": "sensibel", "temperature_max": "off",
    }, trip.display_config.metric_alert_levels


def test_trip_ohne_alt_schluessel_bleibt_unveraendert():
    """AC-7 (GUARD) GIVEN ein Trip ohne Alt-Schluessel WHEN geladen THEN ist
    `metric_alert_levels` unveraendert."""
    levels = {"temperature_max": "off", "wind_gust": "sensibel", "zukunfts_metrik": "robust"}
    trip = load_trip_from_dict(_trip_dict(levels))

    assert trip.display_config.metric_alert_levels == levels


# ══════════════════════════════ AC-8 ═════════════════════════════════════════

def test_uebersetzungstabelle_deckt_sich_mit_katalog():
    """AC-8 GIVEN die Uebersetzungstabelle WHEN jeder Summary-Alt-Schluessel
    ueber den Katalog (`summary_fields` -> `alert_metric_for`) aufgeloest wird
    THEN ergibt sich derselbe Neu-Schluessel; `wind_chill_min_c` ist der
    einzige ohne Alarm-Identitaet. `snow_line` ist kein Summary-Feld (#959)
    und wird getrennt gefuehrt.

    Rueckwaerts ueber `summary_fields` statt `summary_field_for`: CAPE ist
    `selectable=False` und waere sonst unsichtbar."""
    tabelle = dict(_faelle()["tabelle"])
    assert tabelle.pop("snow_line") == "freezing_level"

    # Ein Summary-Feld kann mehreren Katalog-Groessen gehoeren (`temp_min_c`:
    # `temperature`/min UND die nicht waehlbare `temperature_cold`/min). Zaehlt
    # nur, dass es GENAU EINE Alarm-Identitaet gibt -- die der Tabelle.
    identitaeten: dict[str, set[str]] = {alt: set() for alt in tabelle}
    for metric_id, definition in _METRICS_BY_ID.items():
        for aggregation, feld in definition.summary_fields.items():
            if feld in identitaeten:
                neu = alert_metric_for(metric_id, aggregation)
                if neu is not None:
                    identitaeten[feld].add(neu)

    katalog = {alt: (next(iter(ids)) if len(ids) == 1 else (None if not ids else ids))
               for alt, ids in identitaeten.items()}
    assert katalog == tabelle, f"Tabelle {tabelle!r} != Katalog {katalog!r}"
    assert [alt for alt, neu in tabelle.items() if neu is None] == ["wind_chill_min_c"]


# ══════════════════════════════ AC-10 ════════════════════════════════════════

def test_cape_off_alt_schluessel_entfernt_cape_regel(tmp_path):
    """AC-10 GIVEN `cape_max_jkg: off` in einem Alt-Vergleich WHEN Regelbildung am
    Wirkort THEN fehlt die `cape`-Regel. (Dass Alt-Vergleiche OHNE
    `metric_alert_levels` CAPE behalten, bewacht der #1971-Bestandstest.)"""
    # Alt-Vergleich OHNE `active_metrics`: nur dort entsteht die CAPE-Regel
    # (#1971 AC-6) -- CAPE ist nicht waehlbar und fehlt im #961-Backfill, mit
    # `active_metrics` waere der Test schon vor dem Fix vakuum-gruen.
    kontrolle = tmp_path / "kontrolle"
    _schreibe_preset(kontrolle, {"wind_gust": "standard"}, None)
    assert "cape" in _regel_namen(kontrolle), "Kontrolle: CAPE-Regel muss entstehen"

    _schreibe_preset(tmp_path, {"cape_max_jkg": "off"}, None)

    namen = _regel_namen(tmp_path)

    assert "cape" not in namen, (
        f"`cape_max_jkg: off` gespeichert, `cape`-Regel entsteht trotzdem: {namen!r}"
    )
