---
entity_id: issue_222_w2_frontend_alert_konfigurator
type: module
created: 2026-05-14
updated: 2026-05-14
status: draft
version: "1.0"
tags: [alerts, frontend, wizard, trip-detail, issue-222, workflow-2]
---

<!-- Issue #222 (Workflow 2: Frontend Wizard-Save + AlertsPreviewCard) -->

# Issue 222 — Workflow 2: Frontend Alert-Konfigurator

## Approval

- [ ] Approved

## Purpose

Workflow 1 hat den Backend-Pfad live geschaltet: `TripAlertService` liest
`trip.alert_rules`. Workflow 2 schließt die User-sichtbare Lücke:

1. **Neuer Trip-Wizard (`/trips/new`) Step 4** schreibt `alert_rules` parallel
   zu `report_config.alert_thresholds` (W1-Architektur: beides erhalten).
2. **`AlertsPreviewCard.svelte`** rendert pro `enabled=true`-Rule eine Zeile
   mit Metric-Label, Schwellwert+Unit, korrektem Vergleichssymbol und
   Severity-Pill.

Out of Scope: Edit-Pfad `/trips/[id]/edit` (eigener Component-Stack
`TripEditView` mit `WizardStep4ReportConfig` — bekommt eigenes Folge-Issue).

## Source

- **File:** `frontend/src/lib/utils/alertMapping.ts` (NEU, ~40 LoC) — pure Function
  `mapBriefingsToAlertRules(thresholds): AlertRule[]`
- **File:** `frontend/src/lib/utils/alertMetricLabels.ts` (NEU, ~30 LoC) — Map
  `AlertMetric → {label_de, unit, comparison}` und `AlertSeverity → tone`
- **File:** `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` (MODIFY, ~10 LoC)
  — `toTripPayload()` ruft `mapBriefingsToAlertRules` und setzt `payload.alert_rules`
- **File:** `frontend/src/lib/components/trip-detail/AlertsPreviewCard.svelte`
  (REWRITE Skeleton, ~50 LoC) — Iteration über `trip.alert_rules` filtered auf
  `enabled`, Empty-State bleibt, Edit-Link entfernt
- **File:** `frontend/src/lib/components/trip-detail/AlertRow.svelte` (NEU, ~40 LoC)
  — eine Zeile pro Rule mit Pill und Comparison-Symbol
- **Tests:** `frontend/src/lib/utils/alertMapping.test.ts` (NEU, ~50 LoC),
  `frontend/src/lib/components/trip-wizard/__tests__/wizardState.test.ts` (MODIFY, ~30 LoC),
  `frontend/e2e/trip-detail-overview-right.spec.ts` (MODIFY, ~20 LoC),
  `frontend/e2e/trip-wizard-step4.spec.ts` (MODIFY, ~15 LoC)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `AlertRule`, `AlertRuleKind`, `AlertMetric`, `AlertSeverity` | TS-Type | Issue #205, in `frontend/src/lib/types.ts:41-79` |
| `Trip.alert_rules` | `AlertRule[] | undefined` | Issue #205, in `frontend/src/lib/types.ts:76` |
| `BriefingConfig.thresholds` | TS-Type | in `wizardState.svelte.ts:25-30` (gust_kmh, precip_mm, thunder_level, snow_line_m) |
| `Pill.svelte` | Svelte | UI-Komponente, `tone="info|warning|danger|..."`, token-basiert via `app.css:278-292` |
| `Eyebrow.svelte`, `GCard` | Svelte | Card-Container, schon im Skeleton genutzt |
| `crypto.randomUUID()` | Browser-API | ID-Generierung für neue Rules |

## Implementation Details

### 1. `alertMetricLabels.ts` — zentrale Map

```typescript
export const ALERT_METRIC_LABELS: Record<AlertMetric, {
    label_de: string;
    unit: string;
    comparison: '>' | '≥' | '<';
}> = {
    wind_gust:           { label_de: 'Böen',              unit: 'km/h', comparison: '>' },
    precipitation_sum:   { label_de: 'Niederschlag',      unit: 'mm',   comparison: '>' },
    thunder_level:       { label_de: 'Gewitter',          unit: '',     comparison: '≥' },
    snow_line:           { label_de: 'Schneefallgrenze',  unit: 'm',    comparison: '>' },
    temperature_min:     { label_de: 'Tiefsttemperatur',  unit: '°C',   comparison: '<' },
    temperature_max:     { label_de: 'Höchsttemperatur',  unit: '°C',   comparison: '>' },
    temperature_change:  { label_de: 'Temperaturänderung', unit: '°C',  comparison: '>' },
    wind_change:         { label_de: 'Windänderung',      unit: 'km/h', comparison: '>' },
    precipitation_change: { label_de: 'Niederschlagsänderung', unit: 'mm', comparison: '>' },
};

export const ALERT_SEVERITY_TONE: Record<AlertSeverity, 'info' | 'warning' | 'danger'> = {
    info:     'info',
    warning:  'warning',
    critical: 'danger',
};

// THUNDER_LEVEL Threshold → menschenlesbare Stufe (für AlertRow-Anzeige)
export function thunderLevelLabel(threshold: number): string {
    if (threshold >= 2.0) return 'HOCH';
    if (threshold >= 1.0) return 'MITTEL';
    return 'KEINE';
}
```

Reason: Single Source of Truth für Labels, Units, Comparison-Symbole und
Severity→Pill-Tone-Mapping. Wird sowohl von `AlertRow` als auch vom
Wizard-Mapper benutzt.

### 2. `alertMapping.ts` — Wizard → AlertRule[]

```typescript
import type { AlertRule, AlertSeverity } from '$lib/types';

interface Thresholds {
    gust_kmh: number | null;
    precip_mm: number | null;
    thunder_level: 'NONE' | 'MED' | 'HIGH' | null;
    snow_line_m: number | null;
}

export function mapBriefingsToAlertRules(t: Thresholds): AlertRule[] {
    const rules: AlertRule[] = [];
    const base = (id_suffix: string) => ({
        id: crypto.randomUUID(),
        kind: 'absolute' as const,
        severity: 'warning' as AlertSeverity,
        enabled: true,
    });

    if (t.gust_kmh !== null) {
        rules.push({ ...base('gust'), metric: 'wind_gust', threshold: t.gust_kmh, unit: 'km/h' });
    }
    if (t.precip_mm !== null) {
        rules.push({ ...base('precip'), metric: 'precipitation_sum', threshold: t.precip_mm, unit: 'mm' });
    }
    if (t.thunder_level === 'MED') {
        rules.push({ ...base('thunder'), metric: 'thunder_level', threshold: 1.0, unit: '' });
    } else if (t.thunder_level === 'HIGH') {
        rules.push({ ...base('thunder'), metric: 'thunder_level', threshold: 2.0, unit: '' });
    }
    // thunder_level === 'NONE' oder null → keine Rule (User möchte keinen Gewitter-Alarm)
    if (t.snow_line_m !== null) {
        rules.push({ ...base('snow'), metric: 'snow_line', threshold: t.snow_line_m, unit: 'm' });
    }

    return rules;
}
```

Reason: `thunder_level='NONE'` ist semantisch "keine Alert-Regel anlegen" —
nicht eine Regel mit threshold=0. Pure Function, deterministisch (außer
`crypto.randomUUID()`).

### 3. `wizardState.svelte.ts` — `toTripPayload` erweitern

```typescript
// Nach dem report_config-Mapping (Zeile ~370):
import { mapBriefingsToAlertRules } from '$lib/utils/alertMapping';

const alertRules = mapBriefingsToAlertRules(b.thresholds);
if (alertRules.length > 0) {
    payload.alert_rules = alertRules;
}
```

Reason: `report_config` bleibt unverändert geschrieben (W1-Architektur,
Source-of-Truth für Scheduler/Channels). `alert_rules` wird nur angehängt,
wenn mindestens eine Schwelle gesetzt ist — sonst kein leeres Array, damit
Bestandsverhalten der Tests nicht bricht.

### 4. `AlertsPreviewCard.svelte` — Neues Rendering

```svelte
<script lang="ts">
    import type { Trip } from '$lib/types';
    import GCard from '$lib/components/g-card/GCard.svelte';
    import Eyebrow from '$lib/components/eyebrow/Eyebrow.svelte';
    import AlertRow from './AlertRow.svelte';

    let { trip }: { trip: Trip } = $props();

    let enabledRules = $derived(
        (trip.alert_rules ?? []).filter(r => r.enabled)
    );
</script>

<GCard data-testid="right-card-alerts">
    <Eyebrow>Alerts</Eyebrow>
    {#if enabledRules.length === 0}
        <p class="empty-state" data-testid="right-card-alerts-empty">
            Noch keine Alerts konfiguriert
        </p>
    {:else}
        <ul class="rules-list" data-testid="right-card-alerts-rules">
            {#each enabledRules as rule (rule.id)}
                <li><AlertRow {rule} /></li>
            {/each}
        </ul>
    {/if}
</GCard>

<style>
    .empty-state {
        font-size: 0.875rem;
        color: var(--g-ink-faint, #6b7280);
        margin: 0;
    }
    .rules-list { list-style: none; padding: 0; margin: 0; }
    .rules-list li { padding: 0.25rem 0; }
</style>
```

**Edit-Link entfernt** (siehe Analyse-Entscheidung A): kein
`right-card-alerts-edit-link`, kein `href="#alerts"`. Wiedereinführung mit
echtem Edit-Pfad im Folge-Issue.

### 5. `AlertRow.svelte` — Eine Zeile pro Rule

```svelte
<script lang="ts">
    import type { AlertRule } from '$lib/types';
    import Pill from '$lib/components/ui/pill/Pill.svelte';
    import {
        ALERT_METRIC_LABELS, ALERT_SEVERITY_TONE, thunderLevelLabel
    } from '$lib/utils/alertMetricLabels';

    let { rule }: { rule: AlertRule } = $props();

    let info = $derived(ALERT_METRIC_LABELS[rule.metric]);
    let valueText = $derived(
        rule.metric === 'thunder_level'
            ? thunderLevelLabel(rule.threshold)
            : `${rule.threshold} ${info.unit}`.trim()
    );
</script>

<div class="alert-row" data-testid="alert-row">
    <span class="label">{info.label_de}</span>
    <span class="threshold">{info.comparison} {valueText}</span>
    <Pill tone={ALERT_SEVERITY_TONE[rule.severity]}>{rule.severity}</Pill>
</div>

<style>
    .alert-row {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-size: 0.875rem;
    }
    .label { flex: 0 0 auto; font-weight: 500; }
    .threshold { flex: 1; color: var(--g-ink-muted); }
</style>
```

Reason: Flexbox-Layout — `Label  ≥ MITTEL  [warning]` in einer Zeile.
THUNDER_LEVEL bekommt menschenlesbares "MITTEL"/"HOCH" statt "1.0"/"2.0".

## Expected Behavior

- **Input Wizard:** `briefings.thresholds = { gust_kmh: 50, precip_mm: 20, thunder_level: 'MED', snow_line_m: null }`
- **Output Wizard:** POST-Body enthält `alert_rules: [...]` mit drei Rules
  (gust, precip, thunder); `snow_line` fehlt; alle severity=warning, enabled=true.
- **Input Card:** Trip mit `alert_rules = [gust, precip, thunder]`, alle enabled
- **Output Card:** Drei `AlertRow` mit Pill — kein Empty-State sichtbar
- **Input Card (Empty):** Trip mit `alert_rules = []` ODER nur disabled
- **Output Card (Empty):** `<p>Noch keine Alerts konfiguriert</p>`

## Acceptance Criteria

- **AC-1:** Given Wizard mit `briefings.thresholds.gust_kmh = 50`, When User Step 4 abschließt und speichert, Then enthält der POST-Body `alert_rules` mit genau einer AlertRule `{kind: 'absolute', metric: 'wind_gust', threshold: 50, unit: 'km/h', severity: 'warning', enabled: true}`.
  - Test: (populated after /tdd-red)

- **AC-2:** Given Wizard mit allen vier Thresholds gesetzt (`gust_kmh=50, precip_mm=20, thunder_level='MED', snow_line_m=2500`), When `toTripPayload()` aufgerufen wird, Then enthält `payload.alert_rules` vier Rules in dieser Reihenfolge: wind_gust, precipitation_sum, thunder_level (threshold=1.0), snow_line.
  - Test: (populated after /tdd-red)

- **AC-3:** Given Wizard mit allen Thresholds = null UND `thunder_level = 'NONE'`, When `toTripPayload()` aufgerufen wird, Then enthält `payload` KEIN `alert_rules`-Feld (oder leeres Array — keine Rule).
  - Test: (populated after /tdd-red)

- **AC-4:** Given Trip mit `alert_rules = [{enabled: true, metric: 'wind_gust', threshold: 50, severity: 'warning', ...}]`, When `AlertsPreviewCard` rendert, Then ist genau eine `[data-testid="alert-row"]` sichtbar mit Text "Böen" + "> 50 km/h" + Pill mit Tone "warning".
  - Test: (populated after /tdd-red)

- **AC-5:** Given Trip mit `alert_rules = []` ODER `alert_rules = [{enabled: false, ...}]`, When `AlertsPreviewCard` rendert, Then ist `[data-testid="right-card-alerts-empty"]` sichtbar mit Text "Noch keine Alerts konfiguriert", und KEINE `[data-testid="alert-row"]` ist sichtbar.
  - Test: (populated after /tdd-red)

- **AC-6:** Given Trip mit `alert_rules = [{enabled: true, metric: 'thunder_level', threshold: 2.0, severity: 'critical', ...}]`, When `AlertsPreviewCard` rendert, Then enthält die Row "Gewitter" + "≥ HOCH" + Pill mit Tone "danger" (critical→danger Mapping).
  - Test: (populated after /tdd-red)

- **AC-7:** Given Wizard mit `gust_kmh=50`, When gespeichert, Then bleibt `payload.report_config.alert_thresholds.gust_kmh = 50` parallel bestehen (W1-Fallback erhalten).
  - Test: (populated after /tdd-red)

## Known Limitations

- **Edit-Link entfernt:** Trips können in dieser Iteration nur über den neuen
  Wizard (`/trips/new`) eine Rule schreiben. Bestandstrips zeigen ihre
  migrierten Rules (Issue #205) korrekt an, lassen sich aber nicht editieren
  — Folge-Issue.
- **TEMPERATURE_MIN-Kältealarm:** Backend unterstützt es (W1), aber der
  Wizard hat heute kein UI-Feld dafür. Folge-Issue mit erweitertem
  Threshold-Editor.
- **Severity-Auswahl:** Wizard-Default ist `warning` für alle Rules. Pro-Rule-
  Severity-Editor (info/critical) ist Folge-Issue.
- **`thunder_level='NONE'` erzeugt keine Rule:** semantisch "kein Alert
  gewünscht" — wenn der User später eine NONE-Rule mit `severity` für
  Reporting will, muss das Datenmodell den Fall vorsehen.

## Status Update

**Hinweis (seit Issue #224, 2026-05-15):** Die Bridge-Funktion `mapBriefingsToAlertRules()` (definiert in dieser Spec) wurde mit Issue #224 abgebaut. Der Wizard schreibt jetzt direkt `alert_rules` ohne Bridge-Layer (`report_config.alert_thresholds` entfällt).

Diese Spec bleibt als historische Referenz für die Zweit-Architektur (W1↔W2-Bridge). Die aktuelle Implementierung folgt dem Issue-#224-Muster.

## Changelog

- 2026-05-14: Initial spec für Workflow 2 (Frontend) erstellt
- 2026-05-15: Bridge-Funktion durch Issue #224 abgebaut (mapBriefingsToAlertRules entfernt, alertRules als direkter State)
