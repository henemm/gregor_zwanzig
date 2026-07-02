---
entity_id: fix_961_alert_weather_tab_gate
type: module
created: 2026-07-01
updated: 2026-07-01
status: draft
version: "1.0"
tags: [alerts, bugfix, weather-tab, metric_alert_levels]
---

# Fix #961: Alert-Regeln respektieren Weather-Tab-Aktivierungsstatus

## Approval

- [ ] Approved

## Purpose

Stellt den vollständigen Vertrag `should_fire = weather_tab_enabled AND level != 'off'`
zwischen dem Weather-Tab (`display_config.metrics[].enabled`) und den Alarm-Regeln
(`display_config.metric_alert_levels`) wieder her. Aktuell wertet
`TripAlertService._select_change_detector()` ausschließlich `metric_alert_levels`
aus und ignoriert dabei komplett, ob die zugehörige Metrik auf dem Weather-Tab
überhaupt aktiv ist — mit zwei symmetrischen Lücken (Deaktivieren-Lücke,
Aktivieren-Lücke), die real bereits einen Fehlalarm ausgelöst haben (Produktions-
Vorfall Trip 74de939c, "Lottis Abschiedfahrradtour").

## Source

- **File:** `src/services/weather_change_detection.py`
- **Identifier:** `_ALERT_METRIC_TO_CATALOG_ID`, neue Funktion `is_alert_metric_active()`
- **File:** `src/services/alert_preset.py`
- **Identifier:** `expand_per_metric_levels()`
- **File:** `src/services/trip_alert.py`
- **Identifier:** `TripAlertService._select_change_detector()`
- **File:** `src/app/models.py`
- **Identifier:** `AlertRule.suppressed_fields`

> **Schicht-Hinweis:** Reiner Python-Backend-Fix (`src/services/`, `src/app/models.py`
> MODIFY — siehe `AlertRule.suppressed_fields`, F004-Fix). Kein Go-API-, kein
> Frontend-Scope — die Frontend-Anzeige (`activeAlertableMetrics()` in
> `alertMetricTable.ts`) ist bereits korrekt und filtert schon nach
> Weather-Tab-Status.

## Estimated Scope

- **LoC:** ~45–65 (produktiv, Backend)
- **Files:** 4 (MODIFY: `weather_change_detection.py`, `alert_preset.py`, `trip_alert.py`, `models.py`)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `UnifiedWeatherDisplayConfig.is_metric_enabled()` (`src/app/models.py:578`) | upstream | Bereits vorhandener, bisher ungenutzter Baustein — liefert `bool` für eine einzelne Catalog-ID. Wird von der neuen Helper-Funktion aufgerufen. |
| `_ALERT_METRIC_TO_CATALOG_ID` (`src/services/weather_change_detection.py:69-77`) | modify | Bestehendes `AlertMetric → catalog_id`-Mapping (bisher `dict[AlertMetric, str]`, nur für Vergleichsrichtung genutzt) wird auf `dict[AlertMetric, tuple[str, ...]]` erweitert und zur kanonischen Rückrichtung ausgebaut. |
| `expand_per_metric_levels()` (`src/services/alert_preset.py:91-121`) | modify | Zentrale Konvertierungsfunktion `metric_alert_levels → AlertRule[]`; bekommt Filter- und Backfill-Logik. |
| `TripAlertService._select_change_detector()` (`src/services/trip_alert.py:238-253`) | modify | Ruft `expand_per_metric_levels()` auf; reicht `trip.display_config` zusätzlich durch. |
| `TripAlertService.check_all_trips()` (`src/services/trip_alert.py:255+`) | downstream | Realer Scheduler-Pfad (alle 30 Min) — nutzt `_select_change_detector()` transitiv für den Live-Alarmversand. Kein Code-Change hier nötig, aber Verhaltensänderung wirkt sich direkt aus. |
| `AlertRule.suppressed_fields` (`src/app/models.py`) | modify | F004-Fix: feld-granulare Kollisions-Unterdrückung — markiert Summary-/Delta-Felder, die bereits von einer explizit gesetzten (Weather-Tab-aktiven) Metrik belegt sind, damit eine Backfill-Regel nur die verbleibenden, nicht-kollidierenden Felder scharf schaltet. Rein transient, nicht persistiert. |
| Issue #946 (`docs/specs/modules/fix_946_alert_architecture.md`) | reference | `metric_alert_levels` bleibt Single Source of Truth für die *Konfiguration* — dieser Fix filtert/ergänzt nur zur Auswertungszeit, führt keine zweite Quelle ein. |
| Issue #864 / AC-1 (`docs/specs/modules/feat_864_859_alert_presets.md:302`) | reference | Projektions-Prinzip: "Alerts-Tab zeigt exakt die im Weather-Tab aktiven Metriken" — hier auf den Auswertungs-Pfad konsequent zu Ende geführt. |
| Issue #959 | out-of-scope | Separates, bereits gemeldetes Problem: `freezing_level`-Wiring generell kaputt. NICHT Teil dieses Fixes — wird hier nur als Konsument des neuen Mappings berührt, nicht ursächlich gelöst. |

## Implementation Details

### 1. `src/services/weather_change_detection.py`

`_ALERT_METRIC_TO_CATALOG_ID` von `dict[AlertMetric, str]` auf
`dict[AlertMetric, tuple[str, ...]]` erweitern. Fehlende Metriken ergänzen
(`VISIBILITY`, `PRECIPITATION_CHANGE`, `WIND_CHANGE`, `TEMPERATURE_CHANGE`,
`FREEZING_LEVEL` falls als eigener `AlertMetric`-Wert vorhanden — sonst nur
Dokumentations-Kommentar, dass `SNOW_LINE` beide Catalog-IDs abdeckt). `SNOW_LINE`
mappt auf `("snowfall_limit", "freezing_level")` (Mehrfach-Mapping, analog zum
bereits existierenden Frontend-Pendant `CATALOG_TO_ALERT_METRICS` in
`alertMetricTable.ts:279-323`).

Neue Funktion:

```python
def is_alert_metric_active(
    alert_metric: AlertMetric,
    display_config: "UnifiedWeatherDisplayConfig | None",
) -> bool:
    """True, wenn mindestens eine der Weather-Tab-Catalog-IDs, die auf
    `alert_metric` gemappt sind, aktiv ist (enabled=True).

    OR-Verknüpfung bei Mehrfach-Mapping (aktuell nur SNOW_LINE betroffen) —
    siehe 'snow_line-Policy' unten. None-safe: fehlende display_config oder
    unbekannter AlertMetric → False (konservativ, kein Alarm ohne Konfiguration).
    """
    if display_config is None:
        return False
    catalog_ids = _ALERT_METRIC_TO_CATALOG_ID.get(alert_metric)
    if not catalog_ids:
        return False
    return any(display_config.is_metric_enabled(cid) for cid in catalog_ids)
```

`_build_alert_metric_comparison()` (nutzt `_ALERT_METRIC_TO_CATALOG_ID.items()`)
muss auf das neue Tupel-Format angepasst werden — pro Metrik wird weiterhin nur
EINE `cmp`-Richtung aus der ERSTEN Catalog-ID abgeleitet (Vergleichsrichtung ist
pro `AlertMetric` eindeutig, unabhängig vom Aktivierungs-Mapping).

### 2. `src/services/alert_preset.py`

`expand_per_metric_levels()` bekommt zusätzlichen Parameter
`display_config: "UnifiedWeatherDisplayConfig | None" = None`:

```python
def expand_per_metric_levels(
    levels: dict[str, str],
    display_config: "UnifiedWeatherDisplayConfig | None" = None,
) -> list[AlertRule]:
    ...
```

Logik-Erweiterung:
- **Deaktivieren-Lücke schließen:** Für jeden `metric_str` in `levels` zusätzlich
  prüfen, ob `is_alert_metric_active(AlertMetric(metric_str), display_config)`
  `True` liefert (nur wenn `display_config is not None` — Abwärtskompatibilität
  für Aufrufer ohne `display_config`, siehe Known Limitations). Wenn `False`:
  Eintrag überspringen (kein `AlertRule` erzeugen), unabhängig vom gesetzten
  Level.
- **Aktivieren-Lücke schließen:** Zusätzlich über alle `AlertMetric`-Werte
  iterieren, die laut `_ALERT_METRIC_TO_CATALOG_ID` UND `is_alert_metric_active()`
  aktiv sind, aber NICHT (oder mit `level == 'off'` nur implizit) in `levels`
  vorkommen → für diese einen synthetischen `'standard'`-Level annehmen und
  ebenfalls in eine `AlertRule` expandieren (Backfill-Default). Explizit
  gesetztes `level: 'off'` bleibt ein Opt-out und wird NICHT überschrieben.
- `metric_alert_levels` selbst (die Trip-JSON) wird dabei **nicht** verändert —
  reine Auswertungs-Logik, keine Persistenz-Schreiboperation (siehe Known
  Limitations / CLAUDE.md "Daten-Schema-Reworks").

### 3. `src/services/trip_alert.py`

`_select_change_detector()` reicht `trip.display_config` durch:

```python
if trip.display_config and getattr(trip.display_config, "metric_alert_levels", None):
    from services.alert_preset import expand_per_metric_levels
    rules = expand_per_metric_levels(
        trip.display_config.metric_alert_levels,
        display_config=trip.display_config,
    )
    return WeatherChangeDetectionService.from_alert_rules(rules)
```

Zusätzlich: Wenn `metric_alert_levels` leer/None ist, aber `display_config.metrics`
aktive Metriken enthält, greift weiterhin der bestehende NoOp-Pfad (Issue #946 —
"kein Fallback, nicht konfiguriert = kein Alert"). Die Aktivieren-Lücke wird NUR
für Metriken geschlossen, die bereits mindestens einen (auch leeren)
`metric_alert_levels`-Kontext haben — siehe Known Limitations für den Sonderfall
"Trip hat noch nie irgendeine Alert-Stufe gesetzt".

### snow_line-Mehrfach-Mapping-Policy (Übergangslösung)

`SNOW_LINE` hängt an zwei Weather-Tab-Metriken (`snowfall_limit`,
`freezing_level`). Policy: **OR — mindestens eine der beiden aktiv genügt**, damit
`snow_line` als aktiv gilt. Begründung: konservativ im Sinne von "keine Alarme
grundlos verlieren", wenn der Nutzer z. B. nur `snowfall_limit` aktiv hat.
Dies ist explizit eine **Übergangslösung**: Issue #959 (separates
`freezing_level`-Wiring-Problem) wird die Beziehung zwischen `snow_line`,
`snowfall_limit` und `freezing_level` vermutlich grundlegend konsolidieren und
diese Policy dabei ablösen oder präzisieren. Referenz-Test für die Beobachtung
des gemischten Zustands:
`tests/tdd/test_bug_alert_metric_lifecycle_matrix.py::test_documents_open_question_mixed_snow_line_catalog_state`
(dokumentiert nur, stellt kein Pass/Fail-Kriterium).

## Expected Behavior

- **Input:** Ein `Trip` mit `display_config.metrics` (Weather-Tab-Aktivierungsliste,
  je `MetricConfig(metric_id, enabled)`) und `display_config.metric_alert_levels`
  (Alerts-Tab-Konfiguration, `dict[str, str]` von `AlertMetric.value` auf
  `'off' | 'entspannt' | 'standard' | 'sensibel'`).
- **Output:** `TripAlertService._select_change_detector(trip)` liefert einen
  `WeatherChangeDetectionService`, dessen Schwellen/Threshold-Crossing-Regeln
  GENAU die Metriken abdecken, für die `should_fire = weather_tab_enabled AND
  level != 'off'` wahr ist — unabhängig davon, ob der Nutzer den Alerts-Tab je
  manuell geöffnet hat.
- **Side effects:** Keine Schreiboperation auf die Trip-JSON
  (`metric_alert_levels` bleibt unverändert persistiert). Verhaltensänderung
  wirkt sich direkt auf den Live-Scheduler (`check_all_trips()`, alle 30 Min)
  aus: weniger Fehlalarme für deaktivierte Metriken, zusätzliche korrekte
  Alarme für neu aktivierte Metriken ohne manuellen Alerts-Tab-Besuch.
- **Nicht betroffen:** `HUMIDITY` (laut ADR-0010 bewusst tot, kein Feld-Mapping)
  und die grundsätzliche `freezing_level`-Wiring-Frage aus Issue #959 (separates
  Problem, wird durch diesen Fix nicht ursächlich gelöst — nur das neue
  Catalog-ID-Mapping macht `freezing_level` als Teil von `snow_line` erstmals
  im Backend adressierbar).

## Acceptance Criteria

- **AC-1 (Deaktivieren-Lücke geschlossen):** Given ein Trip hat für eine Metrik
  (z. B. `wind_gust`/Catalog-ID `gust`) einen `metric_alert_levels`-Eintrag
  `"standard"`, aber die zugehörige Weather-Tab-Metrik ist `enabled=False` /
  When `TripAlertService._select_change_detector(trip)` aufgerufen wird /
  Then enthält der resultierende Detektor KEINE Schwelle/Threshold-Crossing-
  Regel für diese Metrik mehr.
  - Test: `tests/tdd/test_bug_alert_ignores_weather_tab_disable.py::test_alert_threshold_respects_weather_tab_enabled_state` (Fälle `*_aus`), `::test_visibility_crossing_rule_respects_weather_tab_enabled_state[sichtweite_aus]`, `::test_reproduces_lottis_abschiedfahrradtour_incident` (realer Produktions-Vorfall Trip 74de939c nachgestellt) — alle müssen nach dem Fix grün sein.

- **AC-2 (Aktivieren-Lücke geschlossen):** Given ein Trip hat eine Metrik neu auf
  dem Weather-Tab aktiviert (`enabled=True`), aber `metric_alert_levels` enthält
  für diese Metrik noch KEINEN Eintrag (Nutzer hat den Alerts-Tab nie manuell
  angefasst) / When `_select_change_detector(trip)` aufgerufen wird / Then feuert
  der Detektor für diese Metrik so, als wäre implizit `'standard'` gesetzt (die
  UI zeigt "Standard" als Default an — das Backend muss dasselbe Verhalten
  liefern).
  - Test: `tests/tdd/test_bug_alert_metric_lifecycle_matrix.py::test_alert_fires_iff_active_on_weather_tab_and_not_off` mit `state_id="enabled__unset"` (für alle 12 Metriken in `METRIC_TABLE`) — muss nach dem Fix grün sein.

- **AC-3 (Vollständiger Vertrag über alle Zustandskombinationen):** Given eine
  beliebige Kombination aus Weather-Tab-Status (`enabled=True/False`) und
  Alerts-Tab-Stufe (nicht gesetzt / `'standard'` / `'off'`) für eine der 12
  geprüften Metriken (`wind_gust`, `precipitation_sum`, `thunder_level`,
  `snow_line`, `temperature_min`, `temperature_max`, `temperature_change`,
  `wind_change`, `precipitation_change`, `fresh_snow`, `cape`, `visibility`) /
  When `_select_change_detector(trip)` aufgerufen wird / Then entspricht das
  Feuern-oder-nicht exakt `should_fire = weather_tab_enabled AND level != 'off'`.
  - Test: `tests/tdd/test_bug_alert_metric_lifecycle_matrix.py::test_alert_fires_iff_active_on_weather_tab_and_not_off` (alle 72 Parametrisierungen: 12 Metriken × 6 Zustandskombinationen) — muss nach dem Fix vollständig grün sein.

- **AC-4 (snow_line OR-Policy bei gemischtem Zustand):** Given `snow_line` ist
  über `metric_alert_levels` konfiguriert und von den zwei zugehörigen
  Weather-Tab-Catalog-IDs (`snowfall_limit`, `freezing_level`) ist mindestens
  eine `enabled=True` (unabhängig davon welche) / When
  `_select_change_detector(trip)` aufgerufen wird / Then feuert `snow_line` wie
  bei vollständig aktivem Zustand (OR-Verknüpfung, nicht AND).
  - Test: `tests/tdd/test_bug_alert_metric_lifecycle_matrix.py::test_documents_open_question_mixed_snow_line_catalog_state` — dokumentiert das Verhalten nach der getroffenen Policy-Entscheidung (Test selbst stellt kein Pass/Fail-Kriterium, aber die Policy-Entscheidung MUSS im Code und in dieser Spec nachvollziehbar sein: OR, Übergangslösung, Verweis auf Issue #959).

- **AC-5 (Regressionsschutz — Positiv-Kontrolle bleibt grün):** Given ein Trip
  hat für eine Metrik sowohl Weather-Tab `enabled=True` als auch
  `metric_alert_levels` explizit `"standard"` gesetzt (der bereits vor dem Fix
  korrekt funktionierende Fall) / When `_select_change_detector(trip)`
  aufgerufen wird / Then feuert der Detektor unverändert wie vor dem Fix — der
  Fix darf keine bereits korrekt konfigurierten Trips beeinträchtigen.
  - Test: `tests/tdd/test_bug_alert_ignores_weather_tab_disable.py::test_alert_threshold_respects_weather_tab_enabled_state` (Fälle `*_an`), `::test_visibility_crossing_rule_respects_weather_tab_enabled_state[sichtweite_an]`, sowie `test_bug_alert_metric_lifecycle_matrix.py::test_alert_fires_iff_active_on_weather_tab_and_not_off` mit `state_id="enabled__standard"` — müssen vor UND nach dem Fix grün bleiben (waren bereits Teil der "49 passed"-Baseline).

- **AC-6 (Explizites Opt-out bleibt wirksam):** Given eine Metrik ist auf dem
  Weather-Tab aktiv (`enabled=True`), aber der Nutzer hat sie im Alerts-Tab
  explizit auf `level: 'off'` gesetzt / When `_select_change_detector(trip)`
  aufgerufen wird / Then feuert der Detektor NICHT für diese Metrik — das
  explizite Opt-out darf durch den neuen Backfill-Mechanismus (AC-2) nicht
  überschrieben werden.
  - Test: `tests/tdd/test_bug_alert_metric_lifecycle_matrix.py::test_alert_fires_iff_active_on_weather_tab_and_not_off` mit `state_id="enabled__off"` (für alle 12 Metriken) — muss nach dem Fix grün sein/bleiben.

## Known Limitations

- **Automatischer Backfill auch bei komplett leerem `metric_alert_levels`
  (PO-Entscheidung Option A, 2026-07-02):** `_select_change_detector()` greift den
  Backfill-Pfad bereits dann auf, wenn `display_config` mindestens eine
  Weather-Tab-aktive Alarm-Metrik enthält (`_has_active_alert_metric()`) — auch
  wenn `metric_alert_levels` komplett `None`/leer ist (der Nutzer hat den
  Alarme-Tab noch nie geöffnet). Für jede Weather-Tab-aktive Metrik wird implizit
  `'standard'` angenommen, exakt wie es die UI als Default anzeigt. Damit bekommt
  ein Trip, der nur auf dem Wetter-Tab konfiguriert wurde, automatisch sinnvolle
  Alarme, ohne dass der Nutzer den Alarme-Tab manuell besuchen muss. (Frühere
  Fassung dieser Spec beschrieb noch den strikten Issue-#946-NoOp-Pfad für leeres
  `metric_alert_levels` — durch die PO-Entscheidung überholt und hier korrigiert.)
- **F002-Backward-Compat — leeres `metrics[]`-Array:** Hat ein Trip Alarm-Level
  gesetzt, ohne je den Wetter-Tab zu berühren, ist `display_config.metrics` KOMPLETT
  leer (der Loader backfillt es NUR bei fehlendem `display_config`-Key). In diesem
  Zustand gilt jede Alarm-Metrik konservativ als AKTIV (`is_alert_metric_active`
  liefert True bei leerem `metrics[]`) — sonst würden Alt-Trips still alle Alarme
  verlieren. Erst ein NICHT-leeres `metrics[]` aktiviert die feingranulare
  Weather-Tab-Filterung (fehlender Einzel-Eintrag = inaktiv).
- **`expand_per_metric_levels()` ohne `display_config`-Argument:** Bleibt
  abwärtskompatibel nutzbar (Default `None`), verhält sich dann wie vor dem Fix
  (keine Filterung/kein Backfill) — betrifft ggf. andere, noch unbekannte
  Aufrufer außerhalb von `trip_alert.py` (laut Analyse aktuell keine vorhanden).
- **Keine Bereinigung der Trip-JSON:** Verwaiste `metric_alert_levels`-Einträge
  für deaktivierte Metriken werden NICHT aus der persistierten Trip-Datei
  gelöscht — nur zur Auswertungszeit gefiltert. Reaktiviert der Nutzer die
  Metrik später, erscheint automatisch wieder die zuletzt gesetzte Stufe (kein
  Datenverlust, siehe CLAUDE.md "Daten-Schema-Reworks").
- **`FREEZING_LEVEL`-Wiring bleibt separates Problem:** Issue #959 (falls
  `FREEZING_LEVEL` als eigenständiger `AlertMetric`-Wert existiert und eigene
  Bugs hat) wird durch diesen Fix nicht ursächlich gelöst — nur als Catalog-ID
  innerhalb des `SNOW_LINE`-Mehrfach-Mappings berührt.
- **snow_line-OR-Policy ist Übergangslösung**, siehe Abschnitt oben — wird
  voraussichtlich durch die Konsolidierung in Issue #959 abgelöst.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Bugfix-Schließung eines bereits an anderer Stelle
  spezifizierten Vertrags (Issue #864 AC-1, Issue #946 Single-Source-Prinzip).
  Kein neuer Architektur-Baustein, keine neue Richtungsentscheidung — nutzt
  ausschließlich bereits vorhandene Bausteine (`is_metric_enabled()`,
  bestehendes `_ALERT_METRIC_TO_CATALOG_ID`-Mapping) und erweitert deren
  Anwendung auf einen bisher übersehenen Pfad.

## Changelog

- 2026-07-01: Initial spec created (Issue #961)
- 2026-07-02: Adversary-Runde-2-Findings behoben. F002 (Regression): leeres
  `metrics[]`-Array gilt für Alert-Zwecke als "nie konfiguriert = aktiv" (kein
  stiller Alarmverlust für Alt-Trips ohne Wetter-Tab-Besuch). F001 (AC-6-konform):
  Feld-Kollisions-Schutz beim Backfill blockiert nur noch, wenn die
  beanspruchende Metrik Weather-Tab-AKTIV ist — ein verwaister Level-Eintrag einer
  inaktiven Metrik blockiert den Backfill einer feld-teilenden aktiven Metrik nicht
  mehr. F003 (Doku): Known Limitations auf PO-Entscheidung Option A nachgezogen.
  Anmerkung: Der ursprüngliche F001-Repro (temperature_min/_max beide 'off' →
  temperature_change soll feuern) ist mit AC-6 unvereinbar (geteilte Summary-Felder
  temp_min_c/temp_max_c); AC-6 hat Vorrang.
- 2026-07-02: Spec-Korrektur: models.py ist NICHT mehr read-only — `AlertRule.suppressed_fields`
  (F004-Fix) wurde nachträglich als Scope-Datei dokumentiert.
