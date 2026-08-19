"""Issue #1971 — Fehlt `active_metrics`, waehrend `metric_alert_levels`
gesetzt ist, bleiben neu eingefuehrte Metriken still.

SPEC:    docs/specs/modules/issue_1971_legacy_preset_alarm_fallback.md
KONTEXT: docs/context/fix-1971-legacy-preset-alarm.md (Messungen M1-M8)

WORUM ES GEHT (M3):
`CompareAlertService._build_eval_config()` behandelt `metric_alert_levels`
heute als reines Entweder-Oder — entweder komplett aus dem Preset oder
komplett aus `_STANDARD_METRIC_LEVELS`. Steht im Preset ein
`metric_alert_levels`, das eine spaeter eingefuehrte Groesse (die
Beginn-Alarme aus #1468) nicht auffuehrt, UND fehlt zugleich
`display_config.active_metrics`, dann greift weder der Level-Fallback noch
der #961-Backfill (der haengt hinter `display_config is not None`). Genau
diese Groesse bekommt nie eine Regel und meldet nie.

PRUEFORT = WIRKORT. Gefahren wird die echte Kette
`CompareAlertService._build_eval_config(preset, ...)` ->
`DeviationAlertEngine._select_detector()` (der Produktions-Waehler, der
`expand_per_metric_levels` + `from_alert_rules` in sich traegt) ->
`detect_changes()`. Keine handgesetzte Regel-Liste, kein `Mock()`/`patch()`
(CLAUDE.md, Kern-Schicht).

RED (neues Verhalten, schlaegt HEUTE fehl):
  - test_onset_alarm_fires_without_active_metrics_key                (AC-1)
  - test_cape_rule_survives_missing_active_metrics_with_levels_set   (AC-6, zweite Haelfte)
  - test_explicit_off_survives_standard_levels_merge                 (AC-7)
  - test_explicit_off_metric_stays_silent_while_supplemented_metric_fires (AC-7)

GUARD (bestehendes Verhalten, HEUTE schon gruen, darf nicht kippen):
  - test_partial_active_metrics_only_selected_metric_fires           (AC-3)
  - test_legacy_preset_without_levels_unchanged_rule_count           (AC-4)
  - test_cape_rule_survives_missing_active_metrics                   (AC-6, erste Haelfte)

AC-2 hat bewusst KEINEN Test in dieser Datei — er ist durch den bestehenden
`test_compare_alert_metric_gating.py::test_f001a_empty_active_metrics_wind_delta_does_not_fire`
abgedeckt (Regressionsschutz #1191 F001a) und wird nur im Lauf mitgeprueft.

Pfadregel #1409: der Prueling wird RELATIV ZU DIESER DATEI aufgeloest.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.config import Settings  # noqa: E402
from app.models import (  # noqa: E402
    ForecastMeta, GPXPoint, NormalizedTimeseries, Provider, SegmentWeatherData,
    SegmentWeatherSummary, TripSegment,
)
from services.alert_preset import expand_per_metric_levels  # noqa: E402
from services.compare_alert import CompareAlertService  # noqa: E402
from services.deviation_alert_engine import DeviationAlertEngine  # noqa: E402

TAG = date(2026, 8, 20)

# Die drei Groessen, die ein Nutzer im Alarme-Reiter typischerweise angefasst
# hat, BEVOR es die Beginn-Groessen ueberhaupt gab (#1468).
LEVELS_OHNE_ONSET = {
    "wind_gust": "standard",
    "precipitation_sum": "standard",
    "thunder_level": "standard",
}


def _utc(stunde: int) -> datetime:
    return datetime(TAG.year, TAG.month, TAG.day, stunde, 0)


def _segment() -> TripSegment:
    return TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=47.0, lon=12.0, elevation_m=1000.0,
                             distance_from_start_km=0.0),
        end_point=GPXPoint(lat=47.1, lon=12.1, elevation_m=1200.0,
                           distance_from_start_km=8.0),
        start_time=_utc(6).replace(tzinfo=timezone.utc),
        end_time=_utc(18).replace(tzinfo=timezone.utc),
        duration_hours=12.0, distance_km=8.0, ascent_m=500.0, descent_m=200.0,
    )


def _data(**summary) -> SegmentWeatherData:
    return SegmentWeatherData(
        segment=_segment(),
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test",
                              grid_res_km=1.0),
            data=[],
        ),
        aggregated=SegmentWeatherSummary(**summary),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _preset(display_config: dict | None) -> dict:
    """Ein Vergleichs-Preset, wie es unter `briefings/<id>.json` liegt.

    `location_ids` bleibt leer: `_build_eval_config` leitet daraus nur die
    Zeitzone ab (UTC-Rueckfall, protokolliert) — fuer die Metrik-Auswahl,
    um die es hier geht, ist sie ohne Belang.
    """
    preset: dict = {
        "id": "cp-1971", "name": "cp-1971", "user_id": "tdd-1971",
        "location_ids": [], "schedule": "daily", "hour_from": 9, "hour_to": 16,
        "empfaenger": ["gregor-test@henemm.com"],
    }
    if display_config is not None:
        preset["display_config"] = display_config
    return preset


def _eval_config(display_config: dict | None):
    """Echte `_build_eval_config`-Auswertung — die Naht, an der der Fix wirkt."""
    service = CompareAlertService(
        settings=Settings(smtp_host="dummy.invalid", smtp_user="dummy",
                          smtp_pass="dummy", mail_to="dummy@example.com"),
        user_id="tdd-1971",
    )
    return service._build_eval_config(_preset(display_config), 120, {})


def _regeln(config):
    """Regelmenge GENAU so gebildet wie in `DeviationAlertEngine._select_detector`."""
    return expand_per_metric_levels(
        config.metric_alert_levels or {}, display_config=config.display_config
    )


def _namen(regeln) -> list[str]:
    return sorted(str(r.metric) for r in regeln)


def _gemeldet(config, alt: dict, neu: dict) -> set[str]:
    """Produktions-Detektorwahl + Δ-Auswertung (`include_absolute=False` wie
    im Alarm-Pfad, `DeviationAlertEngine._detect_all_changes`)."""
    detektor = DeviationAlertEngine._select_detector(config)
    return {
        c.metric for c in detektor.detect_changes(
            _data(**alt), _data(**neu), include_absolute=False
        )
    }


# ══════════════════════════════ AC-1 (RED) ═══════════════════════════════════

def test_onset_alarm_fires_without_active_metrics_key():
    """AC-1 (RED) GIVEN ein Preset OHNE `display_config.active_metrics`
    (Schluessel fehlt) und mit gesetztem `metric_alert_levels`, das die
    Beginn-Groessen nicht auffuehrt.

    WHEN der Gewitterbeginn um 2 h vorgezogen wird (17:00 -> 15:00, ueber der
    Standard-Schwelle "ab 1 h frueher").

    THEN entsteht eine `thunder_onset`-Regel UND der Sprung wird gemeldet.

    RED heute: `metric_alert_levels` gilt als Gesamtbild, der
    `_STANDARD_METRIC_LEVELS`-Fallback greift nicht, `display_config` bleibt
    `None` -> der #961-Backfill laeuft nicht -> 3 Regeln, keine Beginn-Regel,
    kein Alarm.

    Positivkontrolle im selben Lauf: der zeitgleiche Boeen-Sprung
    (20 -> 60 km/h) wird HEUTE wie NACH dem Fix gemeldet — ein leeres Ergebnis
    beweist damit einen stillen Beginn-Alarm und nicht bloss eine tote Fixture.
    """
    config = _eval_config({"metric_alert_levels": dict(LEVELS_OHNE_ONSET)})
    namen = _namen(_regeln(config))

    assert "thunder_onset" in namen, (
        "Gesetztes `metric_alert_levels` ohne Beginn-Eintrag plus fehlendes "
        "`active_metrics`: der Gewitterbeginn bekommt keine Regel. Erzeugt "
        f"wurden {len(namen)} Regeln: {namen!r}"
    )

    gemeldet = _gemeldet(
        config,
        alt={"thunder_onset_utc": _utc(17), "gust_max_kmh": 20.0},
        neu={"thunder_onset_utc": _utc(15), "gust_max_kmh": 60.0},
    )
    assert "gust_max_kmh" in gemeldet, (
        "Positivkontrolle gescheitert: der Boeen-Sprung 20 -> 60 km/h muesste "
        f"schon heute melden. Gemeldet wurde: {sorted(gemeldet)!r}"
    )
    assert "thunder_onset_utc" in gemeldet, (
        "Der Gewitterbeginn verschiebt sich um 2 h nach vorn und es entsteht "
        f"kein Alarm. Gemeldet wurde: {sorted(gemeldet)!r}"
    )


# ══════════════════════════════ AC-3 (GUARD) ═════════════════════════════════

def test_partial_active_metrics_only_selected_metric_fires():
    """AC-3 (GUARD) GIVEN eine Teil-Auswahl `active_metrics=["gust_max_kmh"]`
    (Boeen gewaehlt, Niederschlag abgewaehlt) ohne `metric_alert_levels`.

    WHEN Boeen (20 -> 60 km/h, Δ=40 > 20) und Niederschlag (2 -> 20 mm,
    Δ=18 > 10) ZEITGLEICH springen.

    THEN meldet nur der Boeen-Alarm, der Niederschlag bleibt still.

    GUARD: funktioniert heute bereits (der `else`-Zweig mit vorhandenem
    `active_metrics` wird vom Fix nicht angefasst) und darf nicht kippen —
    sonst waere der Fix zur Bevormundung geworden.
    """
    config = _eval_config({"active_metrics": ["gust_max_kmh"]})
    gemeldet = _gemeldet(
        config,
        alt={"gust_max_kmh": 20.0, "precip_sum_mm": 2.0},
        neu={"gust_max_kmh": 60.0, "precip_sum_mm": 20.0},
    )
    assert "gust_max_kmh" in gemeldet, (
        "Die im Editor GEWAEHLTE Boeen-Metrik meldet nicht — erwartet wurde "
        f"ein Alarm bei Δ=40. Gemeldet wurde: {sorted(gemeldet)!r}"
    )
    assert "precip_sum_mm" not in gemeldet, (
        "Die im Editor ABGEWAEHLTE Niederschlags-Metrik meldet trotzdem "
        f"(Δ=18). Gemeldet wurde: {sorted(gemeldet)!r}"
    )


# ══════════════════════════════ AC-4 (GUARD) ═════════════════════════════════

def test_legacy_preset_without_levels_unchanged_rule_count():
    """AC-4 (GUARD) GIVEN ein Preset OHNE `active_metrics` UND OHNE
    `metric_alert_levels` — der bereits vor dem Fix funktionierende Pfad (M2).

    THEN entstehen exakt 14 Regeln, darunter beide Beginn-Groessen UND `cape`.

    GUARD: der Level-Fallback ist heute schon richtig; der Fix darf ihn weder
    verkuerzen noch verlaengern. Die Zahl 14 ist gemessen (M2), nicht geraten.
    """
    config = _eval_config(None)
    namen = _namen(_regeln(config))

    assert len(namen) == 14, (
        f"Der Level-Fallback hat sich verschoben: erwartet 14 Regeln, "
        f"erhalten {len(namen)}: {namen!r}"
    )
    for metrik in ("thunder_onset", "precipitation_heavy_onset", "cape"):
        assert metrik in namen, (
            f"`{metrik}` fehlt im Legacy-Fallback (ohne active_metrics, ohne "
            f"metric_alert_levels). Erzeugt wurden: {namen!r}"
        )


# ══════════════════════════════ AC-6 ═════════════════════════════════════════

def test_cape_rule_survives_missing_active_metrics():
    """AC-6 (GUARD) GIVEN `active_metrics` ausdruecklich als `None` gesetzt
    (Schluessel vorhanden, Wert leer — die zweite von der Spec genannte Form)
    und kein `metric_alert_levels`.

    THEN bleibt eine `cape`-Regel bestehen.

    GUARD gegen den VERWORFENEN Loesungsweg: haette der Fix im `None`-Fall ein
    voll-aktiviertes `display_config` erzeugt, griffe der #961-Filter, und
    `is_alert_metric_active()` fuehrt CAPE seit #1585 (`selectable=False`) NIE
    als aktiv -> 14 Regeln wuerden zu 13, CAPE waere still (M6).
    """
    config = _eval_config({"active_metrics": None})
    namen = _namen(_regeln(config))

    assert config.display_config is None, (
        "Fehlendes `active_metrics` muss weiterhin `display_config=None` "
        "ergeben — sonst greift der #961-Filter und schaltet CAPE stumm "
        f"(verworfener Loesungsweg M6). Erhalten: {config.display_config!r}"
    )
    assert "cape" in namen, (
        f"Die CAPE-Regel ist verschwunden. Erzeugt wurden: {namen!r}"
    )


def test_cape_rule_survives_missing_active_metrics_with_levels_set():
    """AC-6 (RED, zweite Haelfte) GIVEN dasselbe fehlende `active_metrics`,
    diesmal MIT gesetztem `metric_alert_levels` (ohne CAPE-Eintrag).

    THEN enthaelt die Regelmenge trotzdem eine `cape`-Regel.

    RED heute: das gesetzte `metric_alert_levels` verdraengt den Standard-Satz
    vollstaendig -> nur die 3 dort genannten Groessen bekommen eine Regel,
    CAPE ist still. Die Spec verlangt CAPE ausdruecklich "sowohl mit als auch
    ohne gesetztes `metric_alert_levels`".
    """
    config = _eval_config({"metric_alert_levels": dict(LEVELS_OHNE_ONSET)})
    namen = _namen(_regeln(config))

    assert "cape" in namen, (
        "Bei gesetztem `metric_alert_levels` ohne `active_metrics` verschwindet "
        f"die CAPE-Regel. Erzeugt wurden {len(namen)} Regeln: {namen!r}"
    )


# ══════════════════════════════ AC-7 (RED) ═══════════════════════════════════

def test_explicit_off_survives_standard_levels_merge():
    """AC-7 (RED) GIVEN ein Preset ohne `active_metrics`, dessen
    `metric_alert_levels` `wind_gust` ausdruecklich auf `"off"` setzt und
    `precipitation_sum` auf `"standard"`.

    THEN entstehen 13 Regeln: der Standard-Satz ergaenzt die fehlenden
    Groessen (Beginn-Groessen, CAPE), `wind_gust` bleibt aber ABGEWAEHLT.

    RED heute: es entsteht genau 1 Regel (`precipitation_sum`) — die
    Ergaenzung gibt es noch nicht. Die 13 sind gemessen (Spec-Tabelle
    "Abwahl-Probe"), nicht geraten. Der Test sichert zugleich die
    Merge-Reihenfolge ab: wuerde spaeter jemand `_STANDARD_METRIC_LEVELS`
    ZULETZT mergen, kaeme `wind_gust` zurueck und der Test wird rot.
    """
    config = _eval_config({"metric_alert_levels": {
        "wind_gust": "off", "precipitation_sum": "standard",
    }})
    namen = _namen(_regeln(config))

    assert "wind_gust" not in namen, (
        "Die ausdrueckliche Abwahl `wind_gust: 'off'` wurde vom Standard-Satz "
        f"ueberschrieben — Bevormundung. Erzeugt wurden: {namen!r}"
    )
    for metrik in ("thunder_onset", "precipitation_heavy_onset", "cape"):
        assert metrik in namen, (
            f"`{metrik}` wurde nicht ergaenzt. Erzeugt wurden "
            f"{len(namen)} Regeln: {namen!r}"
        )
    assert len(namen) == 13, (
        f"Erwartet 13 Regeln (14 Standard-Groessen minus das abgewaehlte "
        f"`wind_gust`), erhalten {len(namen)}: {namen!r}"
    )


def test_explicit_off_metric_stays_silent_while_supplemented_metric_fires():
    """AC-7 (RED) — dieselbe Zusicherung, aber bis zum Alarm durchgefahren.

    GIVEN ein Preset ohne `active_metrics` mit `metric_alert_levels =
    {fresh_snow: "off", precipitation_sum: "standard"}`.

    WHEN Neuschnee (0 -> 40 cm, Δ=40 weit ueber der Standard-Schwelle 8) und
    die Nullgradgrenze (2500 -> 1500 m, Δ=1000 > 400) ZEITGLEICH springen.

    THEN meldet nur die vom Fix ERGAENZTE Nullgradgrenze; der ausdruecklich
    abgewaehlte Neuschnee bleibt still.

    RED heute: heute ist nur `precipitation_sum` scharf, die Nullgradgrenze
    also ebenfalls still -> die erste Zusicherung schlaegt fehl.

    WARUM NICHT `wind_gust` WIE IN DER SPEC-ILLUSTRATION: `wind_change` deckt
    laut `_ALERT_DELTA_METRIC_TO_FIELDS` DASSELBE Summary-Feld `gust_max_kmh`
    ab. Ein Boeen-Sprung meldet daher auch bei `wind_gust: "off"` — ueber die
    ergaenzte `wind_change`-Regel, nicht ueber eine kaputte Abwahl. Der
    Nachweis "abgewaehlt bleibt still" braucht deshalb eine Groesse mit
    EIGENEM Feld; `fresh_snow` (`snow_new_sum_cm`) und `freezing_level`
    (`freezing_level_m`) sind kollisionsfrei. Die Regelmengen-Zusicherung fuer
    `wind_gust` steht unveraendert im Test darueber.
    """
    config = _eval_config({"metric_alert_levels": {
        "fresh_snow": "off", "precipitation_sum": "standard",
    }})
    gemeldet = _gemeldet(
        config,
        alt={"snow_new_sum_cm": 0.0, "freezing_level_m": 2500.0},
        neu={"snow_new_sum_cm": 40.0, "freezing_level_m": 1500.0},
    )
    assert "freezing_level_m" in gemeldet, (
        "Die vom Standard-Satz ergaenzte Nullgradgrenze meldet nicht "
        f"(Δ=1000 m > 400 m). Gemeldet wurde: {sorted(gemeldet)!r}"
    )
    assert "snow_new_sum_cm" not in gemeldet, (
        "Der ausdruecklich abgewaehlte Neuschnee (`fresh_snow: 'off'`) meldet "
        f"trotzdem (Δ=40 cm). Gemeldet wurde: {sorted(gemeldet)!r}"
    )
