---
entity_id: issue_180_alert_metric_table
type: module
created: 2026-05-18
updated: 2026-05-18
status: draft
version: "1.0"
tags: [frontend, alerts, svelte, epic-139, issue-180]
parent: epic-139-alert-konfigurator
---

# Issue #180 — Alert-Konfigurator: Schwellwert-Tabelle

## Approval

- [x] Approved (2026-05-18)

## Purpose

Ersetzt den Platzhalter-Text im Alerts-Tab (`/trips/[id]#alerts`) mit einer
vollständigen Konfigurations-UI. Zeigt alle 9 AlertMetrics als fixe Tabellenzeilen
mit Toggle, Schwellwert-Inputs und Schweregrad-Auswahl. Darunter: die zwei
Einstellungs-Karten aus Issue #181 (AlertCooldownCard + AlertQuietHoursCard).

Kein Backend-Change — dasselbe `alert_rules: AlertRule[]`-Datenmodell wird
genutzt, `PUT /api/trips/{id}` ist bereits vorhanden.

## Source

- **Files:** `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` (NEU),
  `frontend/src/lib/components/alerts-tab/AlertMetricTable.svelte` (NEU),
  `frontend/src/lib/components/alerts-tab/AlertMetricRow.svelte` (NEU),
  `frontend/src/lib/components/trip-detail/TripTabs.svelte` (geändert)

## Dependencies

| Abhängigkeit | Art |
|---|---|
| `frontend/src/lib/utils/alertMetricLabels.ts` | ALERT_METRIC_LABELS, ALERT_SEVERITY_TONE |
| `frontend/src/lib/components/alert-rules-editor/alertRuleDefaults.ts` | DELTA_ONLY_METRICS |
| `frontend/src/lib/components/alerts-tab/AlertCooldownCard.svelte` | Vorhanden (Issue #181) |
| `frontend/src/lib/components/alerts-tab/AlertQuietHoursCard.svelte` | Vorhanden (Issue #181) |
| `frontend/src/lib/api.ts` | api.put() für Save |
| `frontend/src/lib/types.ts` | AlertRule, AlertMetric, AlertSeverity, Trip |
| `PUT /api/trips/{id}` | Backend-Endpoint (vorhanden) |

## Expected Behavior

- **Input:** `trip: Trip` mit optionalem `alert_rules: AlertRule[]`, `alert_cooldown_minutes`, `alert_quiet_from`, `alert_quiet_to`
- **Output:** Tabellarische Ansicht aller 9 AlertMetrics; nach Speichern sind die Werte in `alert_rules` persistiert
- **Side effects:** `PUT /api/trips/{id}` wird beim Speichern aufgerufen; bei Erfolg: Inline-Bestätigung; bei Fehler: Inline-Fehlermeldung

## Scope

**Nur Frontend.** 4 Dateien:
- Neu: `frontend/src/lib/components/alerts-tab/AlertsTab.svelte`
- Neu: `frontend/src/lib/components/alerts-tab/AlertMetricTable.svelte`
- Neu: `frontend/src/lib/components/alerts-tab/AlertMetricRow.svelte`
- Geändert: `frontend/src/lib/components/trip-detail/TripTabs.svelte`

Die zwei Svelte-Karten aus #181 existieren bereits:
`alerts-tab/AlertCooldownCard.svelte`, `alerts-tab/AlertQuietHoursCard.svelte`

## Data Model

### Row State (intern, nicht persistiert)

Jede Zeile der Tabelle verwaltet:
```typescript
interface MetricRowState {
  absEnabled: boolean;        // Absolut-Regel aktiv?
  absThreshold: number;       // Absolut-Schwellwert (default aus ALERT_METRIC_LABELS)
  deltaEnabled: boolean;      // Delta-Regel aktiv?
  deltaThreshold: number;     // Delta-Schwellwert (default aus ALERT_METRIC_LABELS)
  severity: AlertSeverity;    // Gemeinsamer Schweregrad (default: 'warning')
}
```

Delta-only-Metriken (`temperature_change`, `wind_change`, `precipitation_change`):
`absEnabled` bleibt immer `false`, kein Absolut-Input wird gerendert.

### Mapping: `alert_rules` → Row State (beim Laden)

```
Für jede metric in ALERT_METRIC_LABELS:
  absRule  = alert_rules.find(r => r.metric === metric && r.kind === 'absolute')
  deltaRule = alert_rules.find(r => r.metric === metric && r.kind === 'delta')

  absEnabled    = absRule?.enabled ?? false
  absThreshold  = absRule?.threshold ?? defaultThreshold(metric)
  deltaEnabled  = deltaRule?.enabled ?? false
  deltaThreshold = deltaRule?.threshold ?? defaultThreshold(metric)
  severity      = absRule?.severity ?? deltaRule?.severity ?? 'warning'
```

### Mapping: Row State → `alert_rules` (beim Speichern)

```
result: AlertRule[] = []
Für jede metric:
  if absEnabled (und nicht Delta-only):
    result.push({ id: existing-abs-id or UUID, kind: 'absolute', metric, threshold: absThreshold, unit, severity, enabled: true })
  if deltaEnabled:
    result.push({ id: existing-delta-id or UUID, kind: 'delta', metric, threshold: deltaThreshold, unit, severity, enabled: true })
```

Deaktivierte Zeilen erzeugen keine Einträge in `alert_rules` (sauberes Array).

## Components

### AlertsTab.svelte

Container-Komponente für den gesamten Alerts-Tab-Inhalt.

**Props:** `trip: Trip`

**Aufgaben:**
- Hält `localTrip` als Deep Copy in `$state` (für Speichern ohne Page-Reload)
- Enthält `<AlertMetricTable>` mit bind:alertRules
- Enthält `<AlertCooldownCard>` mit bind:cooldown_minutes
- Enthält `<AlertQuietHoursCard>` mit bind:quiet_from und bind:quiet_to
- Speichern-Button: sammelt alle Werte, ruft `PUT /api/trips/{id}` auf
- Erfolgs-Feedback: "Gespeichert!" Toast oder Inline-Meldung nach erfolgreichem Save
- Fehler-Feedback: Fehlermeldung bei API-Fehler

**Save-Payload:**
```typescript
{
  alert_rules: AlertRule[],        // aus AlertMetricTable
  alert_cooldown_minutes: number | null,
  alert_quiet_from: string | null,
  alert_quiet_to: string | null
}
```

### AlertMetricTable.svelte

**Props:**
- `alertRules: AlertRule[]` — eingehende Regeln (aus Trip)
- `bind:alertRules` — nach innen: Bindung der berechneten Regeln für AlertsTab

**Aufgaben:**
- Initialisiert Row-State aus `alertRules` beim Mount
- Rendert eine `<AlertMetricRow>` pro metric (Reihenfolge: ALERT_METRIC_LABELS)
- Kein eigener Speichern-Button (liegt in AlertsTab)

**Kein `data-testid` für den Table-Container nötig.**

### AlertMetricRow.svelte

**Props:**
- `metric: AlertMetric`
- `bind:state: MetricRowState`

**Layout je Zeile:**
```
[Label]  [Abs-Toggle] [Abs-Input] [Unit]  [Delta-Toggle] [Δ-Input] [Unit]  [Severity-Select]
```

Für Delta-only-Metriken: Abs-Toggle und Abs-Input entfallen (nicht gerendert).

**UI-Details:**
- Label: `ALERT_METRIC_LABELS[metric].label_de`
- Unit: `ALERT_METRIC_LABELS[metric].unit`
- Inputs: `<input type="number" step="0.1" min="0">`
- Inputs werden disabled wenn der zugehörige Toggle deaktiviert ist
- Severity-Select: `<select>` mit Optionen info / warning / critical
- `thunder_level`: step="1", min="1" (nur ganzzahlige Level)

**data-testids:**
- `data-testid="alert-metric-row-{metric}"` — Zeile
- `data-testid="alert-metric-abs-toggle-{metric}"` — Absolut-Toggle
- `data-testid="alert-metric-abs-threshold-{metric}"` — Absolut-Input
- `data-testid="alert-metric-delta-toggle-{metric}"` — Delta-Toggle
- `data-testid="alert-metric-delta-threshold-{metric}"` — Delta-Input
- `data-testid="alert-metric-severity-{metric}"` — Severity-Select

## Acceptance Criteria

**AC-1:** Given der User öffnet `/trips/[id]#alerts` /
When der Tab gerendert wird /
Then sind alle 9 AlertMetric-Zeilen sichtbar, jede mit dem deutschen Label aus `ALERT_METRIC_LABELS` (z.B. "Böen", "Gewitter", "Schneefallgrenze") — kein Platzhalter-Text mehr.

**AC-2:** Given die drei Delta-only-Metriken (`temperature_change`, `wind_change`, `precipitation_change`) /
When die Tabelle rendert /
Then zeigen diese Zeilen keinen Absolut-Toggle und keinen Absolut-Input — nur Delta-Toggle, Delta-Input und Severity.

**AC-3:** Given ein Trip hat eine Alert-Regel: `{kind:'absolute', metric:'wind_gust', threshold:70, severity:'critical', enabled:true}` /
When der Alerts-Tab geöffnet wird /
Then zeigt die `wind_gust`-Zeile: Absolut-Toggle=on, Absolut-Schwellwert=70, Severity=critical.

**AC-4:** Given der User aktiviert den Delta-Toggle für `precipitation_sum` und gibt 5 ein /
When er auf Speichern klickt /
Then wird `PUT /api/trips/{id}` aufgerufen mit einer neuen delta-Regel für `precipitation_sum` mit `threshold=5`.

**AC-5:** Given der Alerts-Tab zeigt eine aktive `wind_gust`-Zeile (threshold=50) /
When der User den Absolut-Toggle deaktiviert und speichert /
Then enthält die gespeicherte `alert_rules`-Liste keine Regel mehr für `wind_gust`.

**AC-6:** Given ein Trip hat `alert_cooldown_minutes=60` /
When der Alerts-Tab geöffnet wird /
Then zeigt `AlertCooldownCard` den Wert 60 im Input.

**AC-7:** Given ein Trip hat `alert_quiet_from="22:00"` und `alert_quiet_to="07:00"` /
When der Alerts-Tab geöffnet wird /
Then zeigt `AlertQuietHoursCard` die Aktiviert-Checkbox als checked und "22:00"/"07:00" in den Zeit-Inputs.

**AC-8:** Given der User ändert Cooldown auf 30 und klickt Speichern /
When der API-Call abgesetzt wird /
Then enthält der Payload `alert_cooldown_minutes: 30`.

**AC-9:** Given der API-Call schlägt fehl /
When Speichern geklickt wird /
Then erscheint eine inline Fehlermeldung — kein Absturz, kein leerer Screen.

## Implementation Details

### Default-Schwellwerte (wenn keine Regel existiert)

```typescript
const METRIC_DEFAULTS: Record<AlertMetric, number> = {
  wind_gust: 50,
  precipitation_sum: 10,
  thunder_level: 1,
  snow_line: 2000,
  temperature_min: -5,
  temperature_max: 35,
  temperature_change: 10,
  wind_change: 20,
  precipitation_change: 5,
};
```

### Speichern-Logik (in AlertsTab.svelte)

```typescript
async function save() {
  saving = true;
  error = null;
  try {
    await api.put(`/api/trips/${trip.id}`, {
      alert_rules: computedRules,
      alert_cooldown_minutes: cooldownMinutes ?? null,
      alert_quiet_from: quietFrom || null,
      alert_quiet_to: quietTo || null,
    });
    saveSuccess = true;
  } catch (e) {
    error = e.message;
  } finally {
    saving = false;
  }
}
```

### Reihenfolge der Zeilen

Immer in der Reihenfolge der Keys in `ALERT_METRIC_LABELS` (via `Object.keys()`):
1. wind_gust, 2. precipitation_sum, 3. thunder_level, 4. snow_line,
5. temperature_min, 6. temperature_max, 7. temperature_change, 8. wind_change,
9. precipitation_change.

### TripTabs.svelte — Änderung

Bestehender else-Block rendert Platzhalter-Text. Für den alerts-Tab:

```svelte
{:else if tab.value === 'alerts' && trip}
  <AlertsTab {trip} />
```

Dazu `import AlertsTab from '$lib/components/alerts-tab/AlertsTab.svelte';` hinzufügen.

## Affected Files

| Datei | Änderung |
|-------|---------|
| `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` | NEU |
| `frontend/src/lib/components/alerts-tab/AlertMetricTable.svelte` | NEU |
| `frontend/src/lib/components/alerts-tab/AlertMetricRow.svelte` | NEU |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | alerts-Branch ersetzen |

## LoC Estimate

~190 LoC (AlertsTab ~40, AlertMetricTable ~30, AlertMetricRow ~80, TripTabs +5).

## Changelog

- 2026-05-18: Initial (Issue #180 — Schwellwert-Tabelle im Alerts-Tab).
