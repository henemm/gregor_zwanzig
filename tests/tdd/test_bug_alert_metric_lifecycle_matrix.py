"""TDD RED — vollständige Vertrags-Matrix: Weather-Tab-Status × Alerts-Tab-Stufe.

Ergänzt `test_bug_alert_ignores_weather_tab_disable.py` (Issue #961). Jener Test
bewies NUR die Deaktivieren-Richtung (Metrik aus, aber Alarm feuert trotzdem).
Beim genaueren Hinsehen (PO-Feedback) zeigt sich eine ZWEITE, symmetrische Lücke
in der ENTGEGENGESETZTEN Richtung — beide zusammen ergeben erst den vollständigen
Vertrag, den Issue #864 als Kernprinzip verspricht:

    "Die Alerts-Liste ist eine Projektion der aktiven Trip-Metriken."

KORREKTUR (nach Adversary-Review): Der ursprüngliche GitHub-Issue-Text zu #864
enthielt eine Formulierung "Aktiviert der Nutzer eine neue Metrik, synchronisiert
das Backend eine neue AlertRule { level: standard }" — das ist aber NICHT Teil
der tatsächlich umgesetzten und verifizierten Spec
`docs/specs/modules/feat_864_859_alert_presets.md` (deren AC-7 etwas anderes
meint: Auto-Save beim Klicken, siehe Zeile 320). Die Anforderung "Aktivieren
synchronisiert automatisch einen Standard-Alarm" wurde also zwischen
Issue-Entwurf und finaler Spec stillschweigend fallengelassen, nie bewusst
verworfen und nie getestet. Die Erwartung unten (`should_fire = weather_tab_
enabled AND level != 'off'`) leitet sich daher NICHT aus einer geltenden
Akzeptanzkriterien-Nummer ab, sondern aus dem in AC-1 der Spec festgehaltenen
Kernprinzip ("Projektion der aktiven Trip-Metriken", `feat_864_859_alert_
presets.md:302`) konsequent zu Ende gedacht: Was angezeigt wird, sollte auch
das sein, was feuert — sonst zeigt die UI dem Nutzer einen Zustand ("Standard",
aktiv), der nicht der Realität entspricht.

Vollständiger Vertrag (was dieser Test beweist):

    EIN ALARM FEUERT GENAU DANN, WENN
        (a) die Metrik auf dem Weather-Tab AKTIV ist          UND
        (b) ihre Alerts-Tab-Stufe NICHT 'off' ist (explizit
            deaktiviert ODER implizit 'standard' als Default,
            wenn noch nie angefasst — UI-Anzeige-Default, siehe unten).

    should_fire = weather_tab_enabled AND level != 'off'

Zwei unabhängige Code-Lücken, die BEIDE diesen Vertrag brechen:

1. **Deaktivieren-Lücke (Issue #961):** `_select_change_detector()`
   (`src/services/trip_alert.py:238-253`) prüft `display_config.metrics[].enabled`
   NIE — ein verwaister `metric_alert_levels`-Eintrag für eine längst deaktivierte
   Metrik feuert unbegrenzt weiter (`should_fire=False`, Code liefert `True`).

2. **Aktivieren-Lücke (NEU, hier erstmals bewiesen):** Es gibt NIRGENDS im Code
   (weder Backend `src/app/loader.py`/`src/services/alert_preset.py` noch
   Frontend `AlertsTab.svelte`) einen automatischen Sync, der eine NEU auf dem
   Weather-Tab aktivierte Metrik mit `level: 'standard'` in `metric_alert_levels`
   einträgt. `AlertMetricLevelTable.svelte:97` zeigt zwar `level={levels[metric]
   ?? 'standard'}` — das ist aber NUR ein Anzeige-Default (Segmented-Control
   erscheint auf "Standard" vorausgewählt), der erst beim manuellen Anklicken
   tatsächlich in `currentLevels` geschrieben und gespeichert wird
   (`onLevelChange()`, Zeile 67-68 in `AlertsTab.svelte`). Ein Trip, der eine
   Metrik aktiviert, ohne dass der Nutzer je den Alerts-Tab anfasst, bekommt
   NIE einen Alarm dafür — obwohl die UI ihm "Standard" (aktiv) suggeriert.
   `should_fire=True` (aus AC-1-Prinzip abgeleitet), Code liefert `False`.

Diese Datei testet BEIDE Lücken zusammen, für 12 der 13 aktiven AlertMetric-
Kataloge (HUMIDITY bewusst ausgenommen — laut ADR-0010 absichtlich tot;
FREEZING_LEVEL bewusst ausgenommen — separat als Issue #959 verfolgt, eigene
Root Cause), über je 6 Zustandskombinationen (Weather-Tab an/aus × Alerts-Stufe
nicht-gesetzt/standard/off) = 72 Fälle. Keine Mocks — echte `Trip`/
`UnifiedWeatherDisplayConfig`/`MetricConfig`-Objekte, echter Aufruf von
`TripAlertService._select_change_detector()`.
"""
from __future__ import annotations

from datetime import date

import pytest

from app.models import MetricConfig, UnifiedWeatherDisplayConfig
from app.trip import Stage, Trip, Waypoint
from services.trip_alert import TripAlertService

# ───────────────────────── Metrik-Katalog für die Matrix ────────────────────
# alert_metric_key: (weather_tab_catalog_ids, kind, felder)
#   kind="delta"     → felder = Tuple von Summary-Feldnamen in `_thresholds`
#   kind="crossing"  → felder = None, geprüft wird Mitgliedschaft in
#                        `_threshold_crossing_rules`
METRIC_TABLE: dict[str, tuple[tuple[str, ...], str, tuple[str, ...] | None]] = {
    "wind_gust":            (("gust",),        "delta",    ("gust_max_kmh",)),
    "precipitation_sum":    (("precipitation",), "delta",  ("precip_sum_mm",)),
    "thunder_level":        (("thunder",),     "delta",    ("thunder_level_max",)),
    "snow_line":            (("snowfall_limit", "freezing_level"), "delta", ("freezing_level_m",)),
    "temperature_min":      (("temperature",), "delta",    ("temp_min_c",)),
    "temperature_max":      (("temperature",), "delta",    ("temp_max_c",)),
    "temperature_change":   (("temperature",), "delta",    ("temp_min_c", "temp_max_c")),
    "wind_change":          (("wind",),        "delta",    ("wind_max_kmh", "gust_max_kmh")),
    "precipitation_change": (("precipitation",), "delta",  ("precip_sum_mm",)),
    "fresh_snow":           (("fresh_snow",),  "delta",    ("snow_new_sum_cm",)),
    "cape":                 (("cape",),        "delta",    ("cape_max_jkg",)),
    "visibility":           (("visibility",),  "crossing", None),
}

STATE_COMBOS = [
    # (state_id, weather_tab_enabled, level_config)
    ("enabled__unset",   True,  None),      # Anzeige-Default 'standard': soll feuern
    ("enabled__standard", True,  "standard"),
    ("enabled__off",     True,  "off"),
    ("disabled__unset",  False, None),
    ("disabled__standard", False, "standard"),  # Issue #961: verwaister Eintrag
    ("disabled__off",    False, "off"),
]


def _stage() -> Stage:
    return Stage(
        id="stage-1",
        name="Etappe 1",
        date=date(2026, 7, 1),
        waypoints=[Waypoint(id="wp-1", name="Start", lat=46.0, lon=11.0, elevation_m=800)],
    )


def _trip(*, metrics: list[MetricConfig], metric_alert_levels: dict) -> Trip:
    config = UnifiedWeatherDisplayConfig(
        trip_id="tdd-bug-matrix",
        metrics=metrics,
        metric_alert_levels=metric_alert_levels,
    )
    return Trip(
        id="tdd-bug-matrix",
        name="TDD Bug Matrix: Weather-Tab x Alerts-Tab Vertrag",
        stages=[_stage()],
        display_config=config,
    )


def _fired(detector, kind: str, alert_metric_key: str, fields: tuple[str, ...] | None) -> bool:
    if kind == "delta":
        thresholds = dict(getattr(detector, "_thresholds", {}) or {})
        return any(f in thresholds for f in fields)
    # kind == "crossing"
    crossing = {str(r.metric) for r in (getattr(detector, "_threshold_crossing_rules", None) or [])}
    return alert_metric_key in crossing


@pytest.mark.parametrize("alert_metric_key", sorted(METRIC_TABLE.keys()))
@pytest.mark.parametrize("state_id, weather_tab_enabled, level_config", STATE_COMBOS)
def test_alert_fires_iff_active_on_weather_tab_and_not_off(
    state_id, weather_tab_enabled, level_config, alert_metric_key,
):
    """should_fire = weather_tab_enabled AND level != 'off' (AC-864/#946-Vertrag)."""
    catalog_ids, kind, fields = METRIC_TABLE[alert_metric_key]
    metrics = [MetricConfig(metric_id=cid, enabled=weather_tab_enabled) for cid in catalog_ids]
    levels = {} if level_config is None else {alert_metric_key: level_config}
    trip = _trip(metrics=metrics, metric_alert_levels=levels)

    service = TripAlertService()
    detector = service._select_change_detector(trip)
    fired = _fired(detector, kind, alert_metric_key, fields)

    should_fire = weather_tab_enabled and level_config != "off"

    assert fired == should_fire, (
        f"Metrik '{alert_metric_key}' [{state_id}]: Weather-Tab "
        f"{'AN' if weather_tab_enabled else 'AUS'} ({catalog_ids!r}), "
        f"Alerts-Stufe={level_config!r} → erwartet feuert={should_fire}, "
        f"tatsächlich feuert={fired}."
    )


# ───────────── Offene Design-Frage: gemischter Zustand bei Mehrfach-Mapping ──

def test_documents_open_question_mixed_snow_line_catalog_state():
    """SNOW_LINE hängt an ZWEI Weather-Tab-Metriken (snowfall_limit, freezing_level).

    Dieser Test STELLT KEINE Erwartung auf (kein Pass/Fail-Kriterium) — er
    dokumentiert nur das aktuelle Verhalten, wenn nur EINE der beiden Metriken
    aktiv ist. Ob "mind. eine aktiv" oder "beide aktiv" die richtige Regel ist,
    ist eine Produktentscheidung, die der Fix für Issue #961 explizit treffen muss
    (siehe auch Issue #959 zur snow_line/freezing_level-Verwechslung).
    """
    metrics = [
        MetricConfig(metric_id="snowfall_limit", enabled=True),
        MetricConfig(metric_id="freezing_level", enabled=False),
    ]
    trip = _trip(metrics=metrics, metric_alert_levels={"snow_line": "standard"})
    service = TripAlertService()
    detector = service._select_change_detector(trip)
    fired = _fired(detector, "delta", "snow_line", ("freezing_level_m",))
    print(
        f"\n[Beobachtung, kein Test-Kriterium] snowfall_limit=an, freezing_level=aus "
        f"→ snow_line feuert aktuell: {fired} (heute: True, da Weather-Tab-Status "
        f"komplett ignoriert wird — nach Fix von Issue #961 muss hier eine bewusste "
        f"Policy-Entscheidung stehen, kein Zufallsergebnis)."
    )


# ───────────── Finding F001: Feld-Kollision blockiert nur AKTIVE Metriken ────
#
# WICHTIG (Adversary-Auflösung F001 vs. AC-6): Der ursprünglich im Adversary-
# Report skizzierte F001-Repro (temperature_min='off' + temperature_max='off',
# aber temperature_change soll trotzdem feuern) ist mit AC-6 dieser Spec NICHT
# vereinbar: alle drei Temperatur-Alarme teilen sich die Summary-Felder temp_min_c/
# temp_max_c. temperature_change zu armieren armiert zwangsläufig genau die Felder,
# die temperature_min/_max='off' laut AC-6 stumm halten MÜSSEN. AC-6 (PO-approbiert,
# `state_id='enabled__off'` für alle 12 Metriken) hat Vorrang.
#
# Der real behebbare, AC-6-KONFORME Kern von F001: Ein `levels`-Eintrag für eine
# Weather-Tab-INAKTIVE Metrik ist ohnehin wirkungslos (wird gefiltert) — er darf
# den Backfill einer feld-teilenden, Weather-Tab-AKTIVEN dritten Metrik nicht
# blockieren. Genau das wird hier getestet.


def test_f001_inaktive_levelmetrik_blockiert_backfill_nicht():
    """Finding F001 (AC-6-konform): Ein `levels`-Eintrag für eine Weather-Tab-
    INAKTIVE Metrik darf den Backfill einer feld-teilenden, Weather-Tab-AKTIVEN
    dritten Metrik NICHT blockieren.

    Szenario: `wind` ist auf dem Weather-Tab aktiv, `gust` ist deaktiviert.
    `wind_gust` (Catalog-ID `gust`) hat einen verwaisten `levels`-Eintrag
    'standard' — ist aber Weather-Tab-inaktiv, feuert also selbst nicht (AC-1).
    `wind_change` (Catalog-ID `wind`, aktiv) hat KEINEN `levels`-Eintrag → soll per
    AC-2 gebackfillt werden. Es teilt sich das Feld `gust_max_kmh` mit `wind_gust`.
    Vor dem Fix hätte der verwaiste (inaktive) `wind_gust`-Eintrag den Backfill von
    `wind_change` unterdrückt; nach dem Fix belegt nur eine AKTIVE Metrik ihr Feld.
    """
    metrics = [
        MetricConfig(metric_id="wind", enabled=True),
        MetricConfig(metric_id="gust", enabled=False),
    ]
    trip = _trip(metrics=metrics, metric_alert_levels={"wind_gust": "standard"})
    service = TripAlertService()
    detector = service._select_change_detector(trip)
    thresholds = dict(getattr(detector, "_thresholds", {}) or {})

    # wind_change belegt wind_max_kmh UND gust_max_kmh → beide müssen scharf sein.
    assert "wind_max_kmh" in thresholds and "gust_max_kmh" in thresholds, (
        "wind_change ist Weather-Tab-aktiv und hat keinen levels-Eintrag → muss "
        "gebackfillt werden. Der verwaiste, Weather-Tab-INAKTIVE wind_gust-Eintrag "
        f"darf den Backfill NICHT blockieren. Gefundene Schwellen: {thresholds!r}"
    )
    # AC-1-Gegenkontrolle: wind_gust selbst (inaktiv) darf keine eigene Absolut-/
    # Crossing-Regel erzeugen — es feuert nicht, es blockiert nur nicht mehr.
    crossing = {str(r.metric) for r in (getattr(detector, "_threshold_crossing_rules", None) or [])}
    assert "wind_gust" not in crossing


def test_f001_aktive_offmetrik_blockiert_backfill_weiterhin_ac6():
    """Gegenprobe (AC-6-Schutz): Eine Weather-Tab-AKTIVE Metrik mit explizitem
    'off' belegt ihr Feld weiterhin — ein feld-teilender Backfill darf ihr
    bewusstes Opt-out NICHT aushebeln.

    `temperature` ist Weather-Tab-aktiv. `temperature_min='off'` (aktiv + off) muss
    temp_min_c stumm halten (AC-6). `temperature_change` (unset, aktiv) teilt sich
    temp_min_c → darf temp_min_c NICHT re-armieren.
    """
    metrics = [MetricConfig(metric_id="temperature", enabled=True)]
    trip = _trip(metrics=metrics, metric_alert_levels={"temperature_min": "off"})
    service = TripAlertService()
    detector = service._select_change_detector(trip)
    thresholds = dict(getattr(detector, "_thresholds", {}) or {})

    assert "temp_min_c" not in thresholds, (
        "temperature_min='off' bei aktivem Weather-Tab muss temp_min_c stumm halten "
        f"(AC-6). Der temperature_change-Backfill darf es nicht re-armieren: {thresholds!r}"
    )


# ───────────── Finding F004: Feld-granulare (nicht regel-granulare) Suppression ─
#
# Vor dem Fix war der Feld-Kollisions-Schutz REGEL-granular: sobald AUCH NUR EIN
# Feld einer Backfill-Metrik mit einer explizit gesetzten AKTIVEN Metrik kollidierte,
# wurde die GANZE Backfill-Regel übersprungen — auch ihre weiteren, nicht-
# kollidierenden Felder. Der Code-Kommentar versprach aber ausdrücklich FELD-
# granulare Unterdrückung ("armiert nur die Felder, die NICHT bereits belegt sind").
# Diese Tests fixieren den erfüllten Vertrag.


def test_f004_teilkollision_backfillt_freies_feld_unterdrueckt_belegtes():
    """Finding F004: Teil-Kollision → freies Feld wird gebackfillt, belegtes bleibt stumm.

    Szenario (vom Adversary verifiziert):
      metrics = wind + gust (beide Weather-Tab-aktiv)
      metric_alert_levels = {"wind_gust": "off"}

    `wind_gust` (Feld `gust_max_kmh`) ist explizit 'off' UND Weather-Tab-aktiv →
    beansprucht `gust_max_kmh` (AC-6: bleibt stumm).
    `wind_change` (Felder `wind_max_kmh` + `gust_max_kmh`, aktiv, kein levels-Eintrag)
    → muss per AC-2 gebackfillt werden — aber nur das FREIE Feld `wind_max_kmh`.

    Erwartet: `wind_max_kmh` scharf (keine Kollision), `gust_max_kmh` stumm (AC-6).
    Vor dem Fix (regel-granular): GANZE wind_change-Regel übersprungen → `_thresholds`
    komplett leer, auch `wind_max_kmh` fehlt.
    """
    metrics = [
        MetricConfig(metric_id="wind", enabled=True),
        MetricConfig(metric_id="gust", enabled=True),
    ]
    trip = _trip(metrics=metrics, metric_alert_levels={"wind_gust": "off"})
    service = TripAlertService()
    detector = service._select_change_detector(trip)
    thresholds = dict(getattr(detector, "_thresholds", {}) or {})

    assert "wind_max_kmh" in thresholds, (
        "wind_change ist Weather-Tab-aktiv, hat keinen levels-Eintrag → das "
        "nicht-kollidierende Feld wind_max_kmh MUSS gebackfillt werden. Die "
        "gust_max_kmh-Kollision mit wind_gust='off' darf NICHT die ganze Regel "
        f"unterdrücken (F004: feld-granular, nicht regel-granular): {thresholds!r}"
    )
    assert "gust_max_kmh" not in thresholds, (
        "wind_gust='off' bei aktivem Weather-Tab muss gust_max_kmh stumm halten "
        f"(AC-6). Der wind_change-Backfill darf es NICHT re-armieren: {thresholds!r}"
    )


def test_f004_vollkollision_unterdrueckt_regel_weiterhin_ac6():
    """Gegenprobe (AC-6-Schutz, akzeptierter Konflikt aus Runde 1): Wenn ALLE Felder
    einer Backfill-Metrik von expliziten AKTIVEN Metriken belegt sind, bleibt die
    Regel weiterhin KOMPLETT unterdrückt — das ist erwartetes Verhalten, kein Bug.

    `temperature` ist Weather-Tab-aktiv. `temperature_min='off'` belegt temp_min_c,
    `temperature_max='off'` belegt temp_max_c (beide AC-6). `temperature_change`
    (unset, aktiv) teilt sich BEIDE Felder → nach Abzug bleibt KEIN Feld übrig →
    Regel komplett übersprungen. Weder temp_min_c noch temp_max_c dürfen scharf sein.
    """
    metrics = [MetricConfig(metric_id="temperature", enabled=True)]
    trip = _trip(
        metrics=metrics,
        metric_alert_levels={"temperature_min": "off", "temperature_max": "off"},
    )
    service = TripAlertService()
    detector = service._select_change_detector(trip)
    thresholds = dict(getattr(detector, "_thresholds", {}) or {})

    assert "temp_min_c" not in thresholds and "temp_max_c" not in thresholds, (
        "temperature_min='off' UND temperature_max='off' belegen BEIDE temp-Felder "
        "(AC-6). temperature_change teilt sich beide → Regel bleibt komplett "
        f"unterdrückt (akzeptierter Konflikt-Fall aus Runde 1): {thresholds!r}"
    )
