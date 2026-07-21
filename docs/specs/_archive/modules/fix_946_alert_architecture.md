# Spec: Alert-Architektur — Single Source of Truth (#946)

**Issue:** https://github.com/henemm/gregor_zwanzig/issues/946
**ADR:** [no-adr] — Architektur-Bereinigung ohne neue externe Abhängigkeiten

## Kontext

Das Alert-System hat aktuell fünf Fallback-Schichten in `_select_change_detector()`:
1. `metric_alert_levels` (explizit, pro Metrik)
2. `alert_preset` (Legacy-Preset)
3. `alert_rules` (alter Regeleditor)
4. `from_display_config()` — erzeugt implizit Regeln aus ALLEN aktivierten Anzeige-Metriken
5. `from_trip_config()` — weiterer impliziter Fallback

Root-Cause von #940: Ein Nutzer ohne explizite Alerts-Konfiguration bekommt trotzdem Alerts,
weil der Code bei `from_display_config()` landet — transparent für den Nutzer, unkonfigurierbar im Frontend.

## Ziel-Architektur

**`metric_alert_levels` ist die einzige Datenquelle für Alerts.**

```
Alerts-Tab (Frontend) ←→ metric_alert_levels (JSON) ←→ _select_change_detector() ←→ Alert-Versand
```

Kein anderer Pfad. Kein implizites Verhalten.

## Acceptance Criteria

**AC-1:** Given ein Trip mit `metric_alert_levels = null` und `alert_preset = null` /
When der Alert-Scheduler den Trip prüft /
Then wird kein Alert gesendet und kein Detektor aktiviert (NoOp).

**AC-2:** Given ein Trip mit gesetztem `alert_preset` (z.B. "standard") aber ohne `metric_alert_levels` /
When das Migrations-Skript läuft /
Then ist `metric_alert_levels` in der Trip-JSON befüllt (Preset → per-Metrik-Levels) /
And `alert_preset` bleibt erhalten (backward compat, wird nur nicht mehr vom Alert-Engine gelesen).

**AC-3:** Given die Methode `_select_change_detector()` in `trip_alert.py` /
When sie für irgendeinen Trip aufgerufen wird /
Then wertet sie ausschließlich `metric_alert_levels` aus /
And `from_display_config()`, `from_trip_config()` und der `alert_preset`-Zweig werden nicht aufgerufen.

**AC-4:** Given der Alerts-Tab für einen Trip mit `metric_alert_levels = null` /
When ein Nutzer den Tab öffnet /
Then sieht er einen Onboarding-Zustand ("Keine Alerts konfiguriert") /
And einen Button "Standard-Konfiguration übernehmen" /
And keinen stillen Standard-Preset (kein `null ?? 'standard'`).

**AC-5:** Given der Onboarding-Zustand im Alerts-Tab /
When der Nutzer "Standard-Konfiguration übernehmen" klickt und speichert /
Then wird `metric_alert_levels` mit Standard-Werten auf dem Backend gespeichert /
And beim nächsten Tab-Öffnen erscheint die normale Konfigurations-Ansicht.

**AC-6:** Given ein Trip mit aktivierter `freezing_level`-Metrik in `display_config` /
When der Nutzer den Alerts-Tab öffnet /
Then erscheint "Nullgradgrenze" als konfigurierbare Alert-Metrik in der Tabelle /
(Umsetzung: `freezing_level` als `AlertMetric` im Frontend ergänzen,
 in `CATALOG_TO_ALERT_METRICS`, `ALERTABLE_METRICS`, `METRIC_LABELS`, `METRIC_PRESETS` und `METRIC_DEFAULTS`).

**AC-7:** Given ein Trip mit bereits gesetztem `metric_alert_levels` /
When der Alert-Scheduler läuft /
Then feuern Alerts genau wie konfiguriert (Regression: kein Behavior-Change).

**AC-8:** Given das Backend `expand_per_metric_levels()` /
When es `metric_alert_levels` mit einem `freezing_level`-Eintrag verarbeitet /
Then erzeugt es korrekte Alert-Regeln für die `freezing_level`-Metrik im Change-Detector.

## Betroffene Dateien

### Backend
- `src/services/trip_alert.py` — `_select_change_detector()` vereinfachen
- `src/services/alert_preset.py` — `expand_per_metric_levels()` um `freezing_level` erweitern
- `scripts/migrate_946_alert_levels.py` (neu) — Einmal-Migration

### Frontend
- `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` — Onboarding-Zustand
- `frontend/src/lib/components/alerts-tab/alertMetricTable.ts` — `freezing_level` in alle Exports
- `frontend/src/lib/utils/alertMetricLabels.ts` — Label "Nullgradgrenze"
- `frontend/src/lib/types.ts` — `AlertMetric` Union erweitern

## Migration

Das Skript `scripts/migrate_946_alert_levels.py`:
1. Durchläuft alle User-Directories `data/users/*/trips/*.json`
2. Für jeden Trip mit `alert_preset != null` und `metric_alert_levels == null`:
   - Konvertiert `alert_preset` → `metric_alert_levels` via `expand_preset()`-Logik
   - Schreibt die JSON zurück (atomarer Write, Backup in `.backups/`)
3. Für jeden Trip mit `alert_preset = null` und `metric_alert_levels = null`:
   - Kein Schreiben — bleibt null (= keine Alerts)
4. Ausführung vor Backend-Deployment (Step 4 im Post-Push-Workflow)

## Was explizit NICHT geändert wird

- Das `alert_preset`-Feld in der Trip-JSON (bleibt für Kompatibilität, wird nur nicht mehr gelesen)
- `WeatherChangeDetectionService.from_display_config()` selbst (kann für andere Zwecke genutzt werden)
- `WeatherChangeDetectionService.from_trip_config()` selbst
- Das Format und die Bedeutung von `metric_alert_levels`
- Alerts für Trips die bereits `metric_alert_levels` gesetzt haben (Regression-Schutz via AC-7)

## Scope-Einschätzung

- 5 Backend-Dateien (inkl. neues Migrations-Skript), ~4 Frontend-Dateien
- LoC-Schätzung: ~120 LoC Netto (Migration ~60, Backend ~20, Frontend ~40)
- Kein API-Schema-Change, kein Breaking Change im Produktionsbetrieb
