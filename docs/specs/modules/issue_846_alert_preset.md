---
entity_id: issue_846_alert_preset
type: feature
created: 2026-06-22
updated: 2026-06-22
status: draft
version: "1.0"
tags: [alert, preset, alerts-tab, ui, epic-813, slice-3, python, frontend, new-metrics]
---

# Alert-Rework Slice 3: Preset-Dropdown + 4 neue Alert-Metriken

## Approval

- [x] Approved

## Purpose

Ersetzt die manuelle Schwellwert-Tabelle im Alerts-Tab (individuelle Zahlen-Inputs pro
Metrik) durch ein einfaches Preset-Dropdown mit 4 Optionen. Gleichzeitig werden 4 neue
Alert-Metriken (Neuschnee, CAPE, Sichtweite, Luftfeuchtigkeit) eingeführt. Das Ziel
ist maximale Einfachheit für Weitwanderer: eine Wahl genügt, keine Konfigurationsarbeit.

## Source

- **File:** `frontend/src/lib/components/alerts-tab/AlertMetricTable.svelte` — wird durch Preset-Selector ersetzt
- **File:** `frontend/src/lib/components/alerts-tab/alertMetricTable.ts` — METRIC_PRESETS hinzufügen
- **File:** `src/app/models.py` — 4 neue `AlertMetric`-Enum-Werte + `alert_preset`-Feld
- **File:** `src/services/weather_change_detection.py` — Mappings für 4 neue Metriken + Threshold-Crossing für Sichtweite

> **Schicht: Frontend (SvelteKit) + Python-Backend (`src/`)**
> Go-API (`api/`, `internal/`) bleibt unberührt — `SyncAlertRules` aus Slice 2 (#817)
> verarbeitet die konfigurierten Metriken bereits korrekt. Die Preset-Expansion findet
> im Python-Backend zur Laufzeit statt, nicht in Go.

## Estimated Scope

- **LoC:** ~200–280 (netto; Frontend ~120, Python-Backend ~100, generierte Dateien zählen nicht)
- **Files:** 6 (3 Frontend + 2 Python + 1 neue Svelte-Komponente)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/ui/Select.svelte` | upstream | Bestehende Select-Komponente für Preset-Dropdown |
| `src/app/models.py` — `AlertMetric` | upstream | Enum wird um 4 neue Werte erweitert |
| `src/services/weather_change_detection.py` — `_ALERT_METRIC_TO_SUMMARY_FIELD` | upstream | Mapping-Dict wird um 4 neue Metriken erweitert |
| `src/services/weather_change_detection.py` — `detect_changes` | upstream | Threshold-Crossing-Logik für Sichtweite ergänzen |
| `src/app/metric_catalog.py` | upstream | Prüfen ob `snow_new_sum_cm`, `cape_max_jkg`, `visibility_min_m`, `humidity_avg_pct` als Summary-Felder existieren |
| `internal/model/trip.go` — `AlertableMetrics`, `SyncAlertRules` | downstream | Go liest `alert_rules` aus User-Config; neue Enum-Werte müssen in Go bekannt sein (Folge-Issue #847 anlegen) |
| `frontend/src/lib/types.ts` — `AlertRule` | upstream | Type-Definitionen für Alert-Konfiguration |
| `frontend/src/lib/utils/alertMetricLabels.ts` | upstream | Labels und Einheiten für neue Metriken ergänzen |

## Implementation Details

### A — Preset-Tabelle (Frontend, TypeScript)

In `alertMetricTable.ts` wird eine neue Konstante `METRIC_PRESETS` definiert:

```
METRIC_PRESETS = {
  "deaktiviert": null,   // kein Alert-Versand
  "entspannt":  { ... }, // lockere Schwellen
  "standard":   { ... }, // Empfehlung, wird als Default gezeigt
  "sensibel":   { ... }, // enge Schwellen
}
```

Pro Preset eine Map von `AlertMetric` auf Schwellwert. Die bestehende
`METRIC_DEFAULTS`-Konstante bleibt als Fallback erhalten.

**Vollständige Schwellwert-Tabelle (alle 13 Metriken):**

| Metrik | AlertMetric | Summary-Feld | Art | Entspannt | Standard | Sensibel |
|--------|------------|--------------|-----|-----------|----------|---------|
| Böen | `wind_gust` | `wind_gust_max_kmh` | Delta ↑ | +35 km/h | +20 km/h | +12 km/h |
| Niederschlag | `precipitation_sum` | `precipitation_sum_mm` | Delta ↑ | +20 mm | +10 mm | +5 mm |
| Gewitter | `thunder_level` | `thunder_level` | Delta ↑ | +1 | +1 | +1 |
| Schneefallgrenze | `snow_line` | `freezing_level_m` | Delta ↓ | −600 m | −400 m | −200 m |
| Temp. Min. | `temperature_min` | `temperature_min_c` | Delta ↓ | −8 °C | −5 °C | −3 °C |
| Temp. Max. | `temperature_max` | `temperature_max_c` | Delta ↑ | +10 °C | +6 °C | +4 °C |
| Temp.-Änderung | `temperature_change` | `temperature_change_*` | Delta ↑ | +14 °C | +10 °C | +6 °C |
| Wind-Änderung | `wind_change` | `wind_change_*` | Delta ↑ | +35 km/h | +25 km/h | +15 km/h |
| Niederschlags-Änd. | `precipitation_change` | `precipitation_change_*` | Delta ↑ | +15 mm | +7 mm | +3 mm |
| Neuschnee | `fresh_snow` (NEU) | `snow_new_sum_cm` | Delta ↑ | +20 cm | +8 cm | +2 cm |
| CAPE | `cape` (NEU) | `cape_max_jkg` | Delta ↑ | +1200 J/kg | +600 J/kg | +200 J/kg |
| Sichtweite | `visibility` (NEU) | `visibility_min_m` | Threshold-Crossing ↓ | <500 m | <1000 m | <3000 m |
| Luftfeuchtigkeit | `humidity` (NEU) | `humidity_avg_pct` | Delta ↑ | +25 % | +15 % | +10 % |

### B — Preset-Selector Komponente (Frontend)

Neue Komponente `AlertPresetSelector.svelte` ersetzt `AlertMetricTable.svelte` im
Alerts-Tab. Aufbau:

```
[ Preset-Dropdown  ▼ ]  [ℹ]

Dropdown-Optionen:
  Deaktiviert
  Entspannt
  Standard   ← vorausgewählt wenn kein alert_preset in Config
  Sensibel
```

Das Info-Icon (ℹ) öffnet ein Popover (inline `<details>/<summary>` oder Svelte-Modal)
mit einer read-only Tabelle aller 13 Metriken × 3 Presets (ohne Deaktiviert-Spalte).

Der ausgewählte Preset-Name (`"deaktiviert"` / `"entspannt"` / `"standard"` / `"sensibel"`)
wird via `PUT /api/trips/{id}` in `display_config.alert_preset` persistiert.

Keine Einzel-Toggles, keine Zahlen-Inputs, keine Severity-Selects mehr.

### C — Backward Compatibility (Frontend)

Wenn `display_config.alert_preset` in der geladenen Trip-Config fehlt (alte Configs
mit `alert_rules`-Array), zeigt das Dropdown `"Standard"` als Auswahl an. Der Wert
wird erst beim expliziten Speichern nach `display_config` geschrieben.

Alte `alert_rules`-Arrays in Legacy-Configs werden durch das Python-Backend weiterhin
korrekt ausgewertet (bestehende Logik aus Slice 1/2 bleibt unverändert).

### D — Python-Backend: 4 neue AlertMetric-Enum-Werte

In `src/app/models.py` die `AlertMetric`-Enum-Klasse erweitern:

```
FRESH_SNOW = "fresh_snow"
CAPE       = "cape"
VISIBILITY = "visibility"
HUMIDITY   = "humidity"
```

(`SNOW_LINE` existiert bereits und bleibt unverändert — mappt auf `freezing_level_m`.)

### E — Python-Backend: Mappings + Threshold-Crossing

In `src/services/weather_change_detection.py`:

**`_ALERT_METRIC_TO_SUMMARY_FIELD` erweitern:**
```
AlertMetric.FRESH_SNOW: "snow_new_sum_cm",
AlertMetric.CAPE:       "cape_max_jkg",
AlertMetric.VISIBILITY: "visibility_min_m",
AlertMetric.HUMIDITY:   "humidity_avg_pct",
```

**Threshold-Crossing für Sichtweite:**
Sichtweite benutzt kein Delta sondern Threshold-Crossing. Der Alert feuert genau dann,
wenn die neue Vorhersage erstmals unter den Schwellwert fällt und das letzte Briefing
noch darüber lag:

```
feuert wenn: new_value < threshold AND old_value >= threshold
```

Diese Logik wird in `detect_changes` als neuer Zweig implementiert — separat von den
symmetrischen Delta-Vergleichen. Flagging via `direction="below_threshold"` o.Ä. um
Sichtweite-Changes eindeutig zu markieren (für Render-Pfad).

### F — Preset-Expansion zur Laufzeit

Wenn das Python-Backend einen Trip verarbeitet und `display_config.alert_preset`
gesetzt ist, wird der Preset-Name zur Laufzeit in eine `AlertRule`-Liste expandiert
(analog zu `SyncAlertRules` in Go). Die expandierten Regeln werden an
`WeatherChangeDetectionService.from_alert_rules` übergeben.

Die bestehende Detection-Logik (`detect_changes`, `from_alert_rules`) bleibt vollständig
unverändert — nur die Quelle der Regeln wechselt (Preset-Expansion statt gespeicherte
`alert_rules`-Array-Einträge).

Preset `"deaktiviert"` expandiert zu einer leeren Liste (kein Alert-Versand).

### G — Scope-Abgrenzung (KEIN Scope)

Folgendes ist NICHT Teil dieser Spec und muss in Folge-Issues spezifiziert werden:
- Go-Anpassungen in `internal/model/trip.go` für die 4 neuen AlertMetric-Enum-Werte
  (Go kennt derzeit nur die alten Werte — Folge-Issue anlegen)
- Dedizierter Alert-Mail-Validator für `deviation-alert`-Typ (war bereits als Folge-Issue
  aus Slice 1 dokumentiert)
- SMS-Kanal für Alerts

## Expected Behavior

- **Input:** User wählt im Alerts-Tab ein Preset aus dem Dropdown und speichert.
- **Output:** `display_config.alert_preset` wird im Trip-JSON persistiert. Beim nächsten
  Alert-Lauf expandiert das Python-Backend das Preset in AlertRules; der
  `WeatherChangeDetectionService` arbeitet mit diesen expandierten Regeln.
- **Side effects:**
  - Bei Preset `"deaktiviert"`: kein Alert-Versand für diesen Trip.
  - Alte `alert_rules`-Arrays bleiben im JSON erhalten (Backward Compatibility), werden
    aber ignoriert wenn `alert_preset` gesetzt ist.
  - Keine Änderung an `alert_state`, `alert_throttle` oder Snapshot-Logik.

## Acceptance Criteria

- **AC-1:** Given ein Trip ohne `alert_preset` in der gespeicherten Config (Legacy-Config
  mit `alert_rules`-Array) / When der User den Alerts-Tab öffnet / Then zeigt das
  Preset-Dropdown `"Standard"` als ausgewählte Option an — ohne Fehlermeldung, ohne
  Leer-Zustand. Kein einzelner Metrik-Toggle und kein Zahlen-Input ist sichtbar.
  - Test: Playwright E2E auf Staging, eingeloggter Nutzer, Trip mit Legacy-`alert_rules`
    aber ohne `alert_preset`; Alerts-Tab laden → Dropdown existiert mit Wert "Standard";
    kein `<input type="number">` im DOM des Alerts-Tab. Echter Browser-Test.

- **AC-2:** Given ein User wählt im Alerts-Tab das Preset `"Sensibel"` und speichert /
  When der Trip via `PUT /api/trips/{id}` gespeichert wird / Then enthält die
  gespeicherte Trip-Config `display_config.alert_preset == "sensibel"` und der nächste
  Alert-Lauf wertet die Senbibel-Schwellen aus (z.B. Böen-Δ-Schwelle 12 km/h statt
  Standard 20 km/h).
  - Test (Backend): Echter Python-Unittest — `expand_preset("sensibel")` liefert
    AlertRule für `wind_gust` mit `threshold == 12` und `kind == "delta"`. Kein Mock.
  - Test (E2E): Playwright wählt "Sensibel", speichert, lädt neu — Dropdown zeigt
    "Sensibel" nach Reload. Echter Browser-Test auf Staging.

- **AC-3:** Given ein User wählt Preset `"Deaktiviert"` und speichert / When der
  Alert-Scheduler für diesen Trip läuft / Then wird kein Alert verschickt (expandierte
  Regel-Liste ist leer, `check_and_send_alerts` beendet sich ohne Versand).
  - Test: Echter Python-Unittest — `expand_preset("deaktiviert")` liefert leere Liste.
    `WeatherChangeDetectionService.from_alert_rules([])` erzeugt Service ohne Thresholds;
    `detect_changes(...)` liefert leere Change-Liste unabhängig vom Wetter-Zustand.
    Kein Mock.

- **AC-4:** Given das Preset `"Standard"` ist aktiv und die frische Sichtweiten-Vorhersage
  fällt erstmals unter 1000 m (Threshold-Crossing) während das letzte Briefing noch
  über 1000 m lag / When `detect_changes` mit dem neuen Sichtweiten-Wert aufgerufen wird /
  Then enthält die Change-Liste genau einen Eintrag für `visibility_min_m` mit
  `direction="below_threshold"` (oder äquivalentem Marker) und der Alert wird verschickt.
  - Test: Echter Python-Unittest mit `old_value=2500`, `new_value=800`,
    `threshold=1000` für `visibility_min_m` — `detect_changes` liefert einen Change-Eintrag.
    Kontrollfall: `old_value=800, new_value=600` (beide unter Threshold) → kein erneuter
    Alert (Threshold-Crossing-Semantik, kein Delta). Kein Mock.

- **AC-5:** Given das Info-Icon (ℹ) neben dem Preset-Dropdown / When der User darauf
  klickt / Then öffnet sich ein Popover oder eingeblendeter Bereich mit einer Tabelle
  die alle 13 Metriken und die Schwellwerte für Entspannt, Standard und Sensibel
  anzeigt; das Popover ist mit einem weiteren Klick (oder Schließen-Button) wieder
  ausblendbar.
  - Test: Playwright E2E — Info-Icon klicken → Popover erscheint mit Text "Böen" und
    "20 km/h" (Standard-Schwelle); nochmals klicken → Popover verschwindet. Echter
    Browser-Test auf Staging.

- **AC-6:** Given ein neuer Trip bei dem `display_config.alert_preset == "entspannt"` /
  When Python-Backend `expand_preset("entspannt")` aufruft / Then enthält das Ergebnis
  Regeln für alle 13 Metriken (einschließlich der 4 neuen: `fresh_snow`, `cape`,
  `visibility`, `humidity`) mit den korrekten Entspannt-Schwellwerten aus der
  Preset-Tabelle (z.B. Neuschnee +20 cm, CAPE +1200 J/kg, Sichtweite <500 m,
  Luftfeuchtigkeit +25 %).
  - Test: Echter Python-Unittest — `expand_preset("entspannt")` liefert exakt 13 Regeln;
    je eine Assertion auf `fresh_snow` (threshold=20), `cape` (threshold=1200),
    `visibility` (threshold=500, kind="threshold_crossing"), `humidity` (threshold=25).
    Kein Mock.

- **AC-7:** Given zwei Nutzer (`user_a` mit Preset `"standard"`, `user_b` mit Preset
  `"sensibel"`) und je einem Trip / When der Alert-Scheduler für `user_a` läuft und
  Böen-Delta 18 km/h erkannt wird (Standard-Schwelle 20 nicht erreicht) / Then erhält
  `user_a` keinen Alert; `user_b` bleibt vollständig isoliert (kein Zugriff auf
  user_b-Trips, kein user_b-Alert).
  - Test: Echter Python-Unittest mit zwei `TripAlertService`-Instanzen unter
    `user_a`/`user_b`-TempDir — nach Lauf unter user_a existiert kein Alert-Log-Eintrag
    für user_a (Schwelle nicht erreicht) und `data/users/user_b/` bleibt unberührt.
    Mandantentrennung bewiesen mit echtem Dateisystem. Kein Mock.

- **AC-8:** Given ein Trip dessen `alert_rules`-Array bereits Slice-2-migrierte
  Delta-Regeln enthält, aber `alert_preset` auf `"standard"` gesetzt wird / When das
  Python-Backend die Regeln für den Alert-Lauf auflöst / Then werden die Preset-Schwellen
  verwendet (Preset hat Vorrang vor altem `alert_rules`-Array); das `alert_rules`-Array
  bleibt im JSON gespeichert aber ungenutzt.
  - Test: Echter Python-Unittest — Trip-Config mit `alert_rules=[{wind_gust, threshold=35}]`
    und `alert_preset="standard"` laden → `expand_preset` liefert wind_gust mit threshold=20
    (Standard). Das `alert_rules`-Array wird nicht als Quelle herangezogen. Kein Mock.

## Known Limitations

- Go-Backend (`internal/model/trip.go`) kennt die 4 neuen `AlertMetric`-Enum-Werte
  (`fresh_snow`, `cape`, `visibility`, `humidity`) noch nicht. `SyncAlertRules` wird
  diese Metriken daher bei einem Trip-Save entfernen. Dieses Folge-Problem muss in
  einem separaten Issue (#847 oder neu anlegen) behoben werden, bevor die neuen
  Metriken im Alert-Scheduler korrekt feuern können.
- Sichtweite nutzt Threshold-Crossing, nicht symmetrisches Delta. Der
  `briefing_mail_validator.py` und `renderer_mail_gate.py` sind nicht betroffen
  (kein Mail-Renderer-Eingriff in diesem Slice).
- Das Preset `"Deaktiviert"` setzt die Schwellen auf null — bestehende `alert_state`-
  Einträge werden dabei nicht automatisch geleert (kein Side-Effect auf Persistenz).
- SMS-Kanal bleibt weiterhin außerhalb des Alert-Scopes.
- Ein dedizierter Validator für `deviation-alert`-Mails (aus Slice 1 als Folge-Issue
  dokumentiert) ist nicht Teil dieser Spec.

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/alerts-tab/AlertMetricTable.svelte` | MODIFY | Tabellen-UI durch Preset-Selector-Aufruf ersetzen |
| `frontend/src/lib/components/alerts-tab/alertMetricTable.ts` | MODIFY | `METRIC_PRESETS`-Konstante mit 4 Optionen × 13 Metriken hinzufügen |
| `frontend/src/lib/components/alerts-tab/AlertPresetSelector.svelte` | CREATE | Neues Dropdown + Info-Popover |
| `frontend/src/lib/utils/alertMetricLabels.ts` | MODIFY | Labels + Einheiten für 4 neue Metriken ergänzen |
| `src/app/models.py` | MODIFY | 4 neue `AlertMetric`-Enum-Werte + `alert_preset`-Feld in Config |
| `src/services/weather_change_detection.py` | MODIFY | Mappings für 4 neue Metriken + Threshold-Crossing-Logik für Sichtweite |

### Estimated Changes

- Files: 6
- LoC: +200/−60

## Changelog

- 2026-06-22: v1.0 Initial spec created (Issue #846, Epic #813 Slice 3)
