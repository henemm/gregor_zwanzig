---
entity_id: feat_864_859_alert_presets
type: feature
created: 2026-06-23
updated: 2026-06-23
status: draft
version: "1.0"
tags: [alerts, frontend, backend, auto-save, per-metric, presets]
---

# Per-Metrik-Alert-Presets + Auto-Save Alerts-Tab (#864 + #859)

## Approval

- [ ] Approved

## Purpose

Ersetzt den globalen Alert-Preset-Dropdown (ein Wert für alle Metriken) durch per-Metrik-Segmented-Controls mit vier Stufen (Aus · Entspannt · Standard · Sensibel) im Alerts-Tab. Gleichzeitig entfällt der manuelle Speichern-Button zugunsten des etablierten Auto-Save-Patterns (`saveController.schedule()`), das bereits in BriefingScheduleTab und WeatherMetricsTab genutzt wird. Das Backend liest beim Alert-Versand ab sofort die neuen pro-Metrik-Stufen aus `display_config.metric_alert_levels` statt des alten globalen `alert_preset`.

## Source

**Frontend:**
- `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` — Haupt-Tab-Komponente (MODIFY)
- `frontend/src/lib/components/alerts-tab/AlertMetricLevelRow.svelte` — neue Zeilen-Komponente (CREATE)
- `frontend/src/lib/components/alerts-tab/AlertMetricLevelTable.svelte` — neuer Container + Global-Quickset (CREATE)
- `frontend/src/lib/components/alerts-tab/alertMetricTable.ts` — METRIC_PRESETS + Migrationsfunktionen (MODIFY)
- `frontend/src/lib/types.ts` — `metric_alert_levels?` in `DisplayConfig` (MODIFY)
- `frontend/src/lib/components/trip-detail/TripTabs.svelte` — `saveController` an AlertsTab weitergeben (MODIFY)

**Python-Backend:**
- `src/app/models.py` — `metric_alert_levels` in `DisplayConfig` (MODIFY)
- `src/services/trip_alert.py` — Prioritätskette: metric_alert_levels → alert_preset → alert_rules → catalog (MODIFY)
- `src/services/alert_preset.py` — neue Funktion `expand_per_metric_levels()` (MODIFY)

**Nicht verändern:** Go-Backend (`api/`, `internal/`, `cmd/`), `AlertPreviewCard`, `AlertCooldownCard`, `AlertQuietHoursCard`

## Estimated Scope

- **LoC:** ~300
- **Files:** 9
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/alerts-tab/alertMetricTable.ts` | interne Abhängigkeit | METRIC_PRESETS-Tabelle enthält bereits die korrekten Delta-Schwellwerte pro Metrik und Stufe |
| `frontend/src/lib/utils/saveController.ts` | Nutzung (bestehendes Pattern) | Auto-Save-Mechanismus, bereits in BriefingScheduleTab + WeatherMetricsTab genutzt |
| `src/services/alert_service.py` | Aufrufer | Ruft `trip_alert.py` auf — muss die erweiterte Prioritätskette transparent durchlaufen |
| `src/app/models.py` — `DisplayConfig` | Datenmodell | Neues Feld `metric_alert_levels` wird hier ergänzt |
| `frontend/src/lib/types.ts` — `DisplayConfig` | Datenmodell (FE) | Entsprechendes TypeScript-Interface |

## Implementation Details

### Datenstruktur

```typescript
// frontend/src/lib/types.ts
type SensLevel = 'off' | 'entspannt' | 'standard' | 'sensibel';
type AlertMetric = 'wind_gust' | 'precipitation_sum' | 'thunder_level' | 'snow_line'
  | 'temperature_min' | 'temperature_max' | 'temperature_change'
  | 'wind_change' | 'precipitation_change' | 'fresh_snow' | 'cape'
  | 'visibility' | 'humidity';

interface DisplayConfig {
  // ... bestehende Felder ...
  metric_alert_levels?: Record<AlertMetric, SensLevel>;
}
```

```python
# src/app/models.py
class DisplayConfig(BaseModel):
    # ... bestehende Felder ...
    metric_alert_levels: dict[str, str] | None = None  # AlertMetric → SensLevel
```

### Migration beim Tab-Load (Backward-Compat)

```typescript
// alertMetricTable.ts — neue Exportfunktion
export function migrateAlertPreset(displayConfig: DisplayConfig): Record<AlertMetric, SensLevel> {
  if (displayConfig.metric_alert_levels) {
    return displayConfig.metric_alert_levels;
  }
  // Legacy: altes globales alert_preset auf alle Metriken anwenden
  const globalLevel = displayConfig.alert_preset ?? 'standard';
  const level = globalLevel === 'off' ? 'off' : globalLevel as SensLevel;
  return Object.fromEntries(
    ALERTABLE_METRICS.map(m => [m, level])
  ) as Record<AlertMetric, SensLevel>;
}
```

### Schwellwert-Anzeige (aus METRIC_PRESETS — keine Änderung, nur Nutzung)

12 von 13 Metriken nutzen **Delta-Schwellen** (Alert wenn sich der Wert um ≥ X ändert).
**Sichtweite** (`visibility`) ist die Ausnahme: `AlertRuleKind.THRESHOLD_CROSSING` —
Alert wenn der absolute Wert *unter* den Schwellwert fällt (< X m).

```typescript
// alertMetricTable.ts — levelToThreshold()
// THRESHOLD_CROSSING-Metriken brauchen ein anderes Anzeigeformat.
const THRESHOLD_CROSSING_METRICS: ReadonlySet<AlertMetric> = new Set(['visibility']);

export function levelToThreshold(metric: AlertMetric, level: SensLevel): string | null {
  if (level === 'off') return null;
  const preset = METRIC_PRESETS[metric];
  const value = preset[level]; // entspannt | standard | sensibel
  if (THRESHOLD_CROSSING_METRICS.has(metric)) {
    return `< ${value} ${preset.unit}`; // z.B. "< 1000 m"
  }
  return `Δ ≥ ${value} ${preset.unit}`; // z.B. "Δ ≥ 20 km/h"
}

// Bestehende METRIC_PRESETS (Auszug — keine Änderung):
// wind_gust:          entspannt=35, standard=20, sensibel=12 (km/h) — Delta
// precipitation_sum:  entspannt=20, standard=10, sensibel=5  (mm)   — Delta
// thunder_level:      1/1/1  (Stufen)                                — Delta
// snow_line:          600/400/200 (m, Richtung ↓)                   — Delta (Frostgrenze sinkt)
// temperature_min:    8/5/3  (°C)                                   — Delta
// temperature_max:    10/6/4 (°C)                                   — Delta
// temperature_change: 14/10/6 (°C)                                  — Delta
// wind_change:        35/25/15 (km/h)                               — Delta
// precipitation_change: 15/7/3 (mm)                                 — Delta
// fresh_snow:         20/8/2  (cm)                                   — Delta
// cape:               1200/600/200 (J/kg)                           — Delta
// visibility:         500/1000/3000 (m)                             — THRESHOLD_CROSSING (< X m)
// humidity:           25/15/10 (%)                                  — Delta
```

### Dynamische Metrik-Liste (Alerts-Tab)

```typescript
// AlertsTab.svelte — nur alertable und im Wetter-Metriken-Tab aktiv gewählte Metriken
$: alertableActiveMetrics = trip.display_config?.selected_metrics
  ?.filter(m => ALERTABLE_METRICS.includes(m as AlertMetric)) ?? [];
```

Wenn `alertableActiveMetrics.length === 0`: leerer Zustand mit Hinweis "Keine alertable Metriken aktiv. Wähle Metriken im Wetter-Metriken-Tab."

### UI-Layout Desktop

```
Eyebrow: ALERTS · SOFORT-MELDUNG
H2: Sofort-Meldung zwischen den Briefings

Globaler Quickset: "Alle Metriken auf:"
  [Aus][Entspannt][Standard][Sensibel]  "N von X aktiv [· gemischt]"

Tabelle:
  Spalten: METRIK | EMPFINDLICHKEIT | SCHWELLWERT
  Pro Zeile (AlertMetricLevelRow):
    - Metrik-Label
    - Segmented-Control (4 Stufen)
    - Schwellwert: "Δ ≥ 20 km/h" (Delta) oder "< 1000 m" (Sichtweite) oder "—" bei Aus
    - Zeile gedimmt (opacity: 0.6) wenn Stufe = Aus

Cooldown + Stille Stunden (gedimmt wenn alle Metriken Aus)
AlertPreviewCard (unverändert)
```

### UI-Layout Mobile (max-width: 899px)

```
Labels im Segmented-Control: Aus / Entsp. / Std. / Sens.
Metrik-Zeile gestapelt:
  Zeile 1: Metrik-Label + Schwellwert
  Zeile 2: Segmented-Control (full-width)
Touch-Targets: ≥ 44px
Input font-size: 16px (verhindert iOS-Zoom)
Kein horizontales Scrollen
```

### Global-Quickset Logik

```typescript
// AlertMetricLevelTable.svelte
$: allSameLevel = alertableActiveMetrics.every(m => levels[m] === levels[alertableActiveMetrics[0]]);
$: quicksetActiveLevel = allSameLevel && alertableActiveMetrics.length > 0
  ? levels[alertableActiveMetrics[0]]
  : null; // null → kein Segment aktiv → "gemischt"
$: activeCount = alertableActiveMetrics.filter(m => levels[m] !== 'off').length;
$: counterLabel = allSameLevel
  ? `${activeCount} von ${alertableActiveMetrics.length} aktiv`
  : `${activeCount} von ${alertableActiveMetrics.length} · gemischt`;
```

### Auto-Save (#859)

```typescript
// TripTabs.svelte — saveController weitergeben
<AlertsTab {trip} {onTripUpdate} {saveController} />

// AlertsTab.svelte — keine Speichern-Schaltfläche; bei Änderung:
function onLevelChange(metric: AlertMetric, level: SensLevel) {
  currentLevels = { ...currentLevels, [metric]: level };
  saveController?.schedule(buildSaveFn());
}

function buildSaveFn() {
  return async () => {
    await fetch(`/api/trips/${trip.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        display_config: {
          ...trip.display_config,
          metric_alert_levels: currentLevels
        }
      })
    });
  };
}
```

Tab-Wechsel-Warnung wenn `saveController?.hasPending`:
```typescript
// TripTabs.svelte — vor Tab-Wechsel
if (saveController?.hasPending) {
  const ok = window.confirm('Nicht gespeicherte Änderungen gehen verloren. Trotzdem wechseln?');
  if (!ok) return;
}
```

### Backend — Prioritätskette (trip_alert.py)

```python
# src/services/trip_alert.py
def get_alert_rules_for_trip(trip: Trip) -> list[AlertRule]:
    dc = trip.display_config or {}

    # Priorität 1: neue per-Metrik-Stufen
    if dc.get('metric_alert_levels'):
        return expand_per_metric_levels(dc['metric_alert_levels'])

    # Priorität 2: altes globales alert_preset
    if dc.get('alert_preset'):
        return expand_global_preset(dc['alert_preset'])

    # Priorität 3: explizite alert_rules-Liste (sehr legacy)
    if trip.alert_rules:
        return trip.alert_rules

    # Priorität 4: Catalog-Defaults
    return get_catalog_defaults()
```

### Backend — expand_per_metric_levels (alert_preset.py)

```python
# src/services/alert_preset.py

_PRESET_TABLE: dict[str, dict[str, float]] = {
    'wind_gust':            {'entspannt': 35, 'standard': 20, 'sensibel': 12},
    'precipitation_sum':    {'entspannt': 20, 'standard': 10, 'sensibel': 5},
    'thunder_level':        {'entspannt': 1,  'standard': 1,  'sensibel': 1},
    'snow_line':            {'entspannt': 600,'standard': 400,'sensibel': 200},
    'temperature_min':      {'entspannt': 8,  'standard': 5,  'sensibel': 3},
    'temperature_max':      {'entspannt': 10, 'standard': 6,  'sensibel': 4},
    'temperature_change':   {'entspannt': 14, 'standard': 10, 'sensibel': 6},
    'wind_change':          {'entspannt': 35, 'standard': 25, 'sensibel': 15},
    'precipitation_change': {'entspannt': 15, 'standard': 7,  'sensibel': 3},
    'fresh_snow':           {'entspannt': 20, 'standard': 8,  'sensibel': 2},
    'cape':                 {'entspannt': 1200,'standard': 600,'sensibel': 200},
    'visibility':           {'entspannt': 500,'standard': 1000,'sensibel': 3000},
    'humidity':             {'entspannt': 25, 'standard': 15, 'sensibel': 10},
}

def expand_per_metric_levels(levels: dict[str, str]) -> list[AlertRule]:
    """
    Konvertiert metric_alert_levels (metric → SensLevel) in AlertRule-Liste.
    Level 'off' wird übersprungen — keine Regel für diese Metrik.
    """
    rules = []
    for metric, level in levels.items():
        if level == 'off':
            continue
        thresholds = _PRESET_TABLE.get(metric)
        if not thresholds or level not in thresholds:
            continue
        # visibility nutzt THRESHOLD_CROSSING, alle anderen DELTA
        THRESHOLD_CROSSING = {'visibility'}
        kind = AlertRuleKind.THRESHOLD_CROSSING if metric in THRESHOLD_CROSSING else AlertRuleKind.DELTA
        rules.append(AlertRule(
            metric=metric,
            threshold=thresholds[level],
            kind=kind,
        ))
    return rules
```

## Expected Behavior

- **Input:** Trip mit `display_config.metric_alert_levels` (neu) oder `alert_preset` (legacy) sowie der aktiven Metrik-Auswahl aus dem Wetter-Metriken-Tab
- **Output:** Alerts-Tab zeigt pro aktiv-alertable Metrik ein Segmented-Control (4 Stufen), Änderungen werden automatisch gespeichert; Backend-Alert-Scheduler nutzt die per-Metrik-Stufen
- **Side effects:** Altes `alert_preset`-Feld wird weiter gelesen (Backward-Compat), aber nicht mehr geschrieben. Tab-Wechsel mit ausstehender Speicherung löst Bestätigungsdialog aus.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit aktiven Wetter-Metriken (davon mindestens eine Metrik die in der ALERTABLE_METRICS-Liste steht), When der authentifizierte Nutzer den Alerts-Tab öffnet, Then zeigt der Tab exakt die im Wetter-Metriken-Tab aktiv gewählten und alertable Metriken als Tabellenzeilen — keine eigene Verwaltungsmöglichkeit für die Metrik-Liste selbst, kein manueller Hinzufügen-Button.
  - Test: Playwright E2E — prüfe Anzahl der Tabellenzeilen gegen die Anzahl der aktiven alertable Metriken im Trip-State via GET `/api/trips/{id}`

- **AC-2:** Given die Metrik-Liste im Alerts-Tab mit mindestens einer Zeile, When der Nutzer eine Metrik-Zeile betrachtet, Then enthält jede Zeile ein Segmented-Control mit genau 4 Stufen in der Reihenfolge Aus · Entspannt · Standard · Sensibel, und die Default-Stufe bei neuen Trips ist Standard — kein Zahlen-Input, kein Threshold-Eingabefeld.
  - Test: Playwright E2E — prüfe für eine frische Zeile dass genau 4 Segmente vorhanden und das Segment "Standard" initial selektiert ist

- **AC-3:** Given eine Metrik-Zeile mit aktiver Stufe (nicht Aus), When die Zeile gerendert wird, Then zeigt die Schwellwert-Spalte den zur Stufe gehörenden Schwellwert im metrik-spezifischen Format: Delta-Metriken als "Δ ≥ {wert} {einheit}" (z.B. "Δ ≥ 20 km/h" für Böen Standard), Sichtweite als "< {wert} m" (z.B. "< 1000 m" für Standard).
  - Test: Playwright E2E — wähle Stufe "Standard" bei Böen, erwarte Text "Δ ≥ 20 km/h"; wähle Stufe "Standard" bei Sichtweite, erwarte Text "< 1000 m"

- **AC-4:** Given eine Metrik-Zeile mit Stufe = Aus, When die Zeile gerendert wird, Then ist die gesamte Zeile optisch gedimmt (visuell erkennbar reduzierte Opazität) und die Schwellwert-Spalte zeigt "—" statt eines numerischen Werts.
  - Test: Playwright E2E — setze eine Zeile auf Aus, prüfe dass Schwellwert-Text "—" ist und computed style opacity < 1 für die Zeile

- **AC-5:** Given mehrere Metriken auf gemischten Stufen (z.B. eine Entspannt, eine Standard), When der Globale Quickset gerendert wird, Then ist kein Quickset-Segment aktiv (kein Segment hervorgehoben) und der Zähler-Text enthält "gemischt"; wenn alle Metriken dieselbe Stufe haben, ist das entsprechende Segment aktiv und "gemischt" erscheint nicht.
  - Test: Playwright E2E — setze zwei Metriken auf verschiedene Stufen, prüfe Quickset-Zustand; setze alle auf Standard, prüfe dass Standard-Segment aktiv

- **AC-6:** Given ein Trip bei dem alle sichtbaren Metrik-Zeilen auf Stufe Aus stehen, When der Alerts-Tab gerendert wird, Then sind die Cooldown- und Stille-Stunden-Felder optisch gedimmt und nicht editierbar (disabled oder visually subdued).
  - Test: Playwright E2E — setze alle Metriken auf Aus, prüfe disabled-Attribut oder opacity der Cooldown-Input-Felder

- **AC-7:** Given der Nutzer ändert die Stufe einer Metrik-Zeile, When die Änderung durch Klick auf ein Segment-Control erfolgt, Then wird die Änderung automatisch gespeichert ohne dass der Nutzer einen Speichern-Button drücken muss; ein anschließender GET `/api/trips/{id}` liefert den aktualisierten `metric_alert_levels`-Wert im `display_config`.
  - Test: Playwright E2E — klicke Stufe "Sensibel" für eine Metrik, warte auf Auto-Save-Signal, rufe GET `/api/trips/{id}` auf und prüfe dass `display_config.metric_alert_levels[metric] === 'sensibel'`

- **AC-8:** Given die mobile Ansicht (Viewport max-width 899px), When der Alerts-Tab gerendert wird, Then sind die Segmented-Labels auf "Aus/Entsp./Std./Sens." gekürzt, die Metrik-Zeilen sind gestapelt (Label + Schwellwert oben, Segmented-Control darunter), alle Touch-Targets sind mindestens 44px hoch, und kein horizontales Scrollen ist erforderlich.
  - Test: Playwright E2E mit Viewport 390×844 — prüfe dass kein horizontaler Overflow vorhanden ist und alle Segment-Labels die Kurzform verwenden

- **AC-9:** Given ein Trip mit altem `display_config.alert_preset: 'standard'` (globaler Wert, kein `metric_alert_levels`), When der Nutzer den Alerts-Tab öffnet, Then werden alle angezeigten Metrik-Zeilen mit der Stufe Standard vorbelegt — kein Datenverlust, kein leerer Zustand.
  - Test: Playwright E2E — lade einen Trip mit Fixture `alert_preset: 'entspannt'` (kein `metric_alert_levels`), prüfe dass alle Zeilen auf "Entspannt" stehen

- **AC-10:** Given der Nutzer hat eine Metrik-Stufe geändert und der Auto-Save ist noch ausstehend (saveController.hasPending = true), When der Nutzer auf einen anderen Tab klickt, Then erscheint ein Bestätigungsdialog der vor dem Verlust ungespeicherter Änderungen warnt; bei Abbruch bleibt der Alerts-Tab aktiv.
  - Test: Playwright E2E — ändere eine Stufe, klicke sofort auf anderen Tab bevor Auto-Save abgeschlossen ist, prüfe dass dialog erscheint und bei Cancel der Alerts-Tab weiter sichtbar bleibt

- **AC-11 (Backend):** Given ein Trip mit `display_config.metric_alert_levels: {'wind_gust': 'standard', 'precipitation_sum': 'off'}`, When der Alert-Scheduler via `trip_alert.py` die Alert-Regeln für diesen Trip lädt, Then enthält die zurückgegebene Regel-Liste eine Regel für `wind_gust` mit `threshold=20` (Standard-Delta), aber keine Regel für `precipitation_sum`.
  - Test: pytest Integrationstest — echter HTTP-POST auf Alert-Check-Endpoint oder direkter Aufruf von `get_alert_rules_for_trip()` mit präpariertem Trip-Objekt; prüfe Rückgabeliste ohne Mock

## Known Limitations

- `thunder_level` hat für alle drei aktiven Stufen denselben Delta-Schwellwert (1) — das ist beabsichtigt (Gewitter ist binär, jede Abweichung relevant). Der Quickset-Zähler zählt diese Zeile korrekt als "aktiv".
- `visibility` nutzt `AlertRuleKind.THRESHOLD_CROSSING` (absolut: Alert wenn Sichtweite < X m); `snow_line` nutzt Delta (Frostgrenze sinkt um ≥ X m). Die Schwellwert-Spalte zeigt für `visibility` "< X m", für alle anderen "Δ ≥ X einheit".
- Das Auto-Save Pattern überschreibt `display_config` als Ganzes — andere concurrent Änderungen an `display_config` (z.B. aus einem anderen Tab) können bei Race-Condition verloren gehen. Das ist eine bestehende Einschränkung des saveController-Patterns (nicht neu durch dieses Feature).
- Altes `alert_preset`-Feld wird nach Migration nicht aktiv gelöscht — es bleibt als totes Feld in `display_config` stehen, bis der Nutzer den Tab einmal öffnet und speichert.

## Changelog

- 2026-06-23: Initial spec created (Issues #864 + #859)
