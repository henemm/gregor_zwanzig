---
entity_id: issue_223_alert_rules_editor
type: module
created: 2026-05-14
updated: 2026-05-14
status: draft
version: "1.0"
tags: [alerts, frontend, editor, trip-edit, issue-223]
---

<!-- Issue #223 — Edit-Pfad für alert_rules: Liste-basierter Editor -->

# Issue 223 — AlertRulesEditor (Liste-basierter Rule-Editor)

## Approval

- [ ] Approved

## Purpose

Heute haben wir **ein Datenmodell** (`Trip.alert_rules: AlertRule[]`) mit
**zwei verschiedenen UI-Konzepten** — Wizard zeigt Absolut-Schwellen,
Edit-Pfad zeigt Δ-Schwellen. Bestandstrips können ihre `alert_rules` nicht
editieren.

Dieser Workflow schafft die **langfristig richtige Architektur**: eine
wiederverwendbare `AlertRulesEditor`-Komponente, die das `alert_rules`-
Datenmodell direkt spiegelt — Liste von Regeln, pro Regel Edit/Delete/
Severity-Picker/Enabled-Toggle. Im Edit-Pfad wird sie als neuer
Accordion-Block "Alarmregeln" integriert. Der Wizard bleibt vorerst
unverändert (eigene Folge-Iteration).

## Source

- **NEU:** `frontend/src/lib/components/alert-rules-editor/AlertRulesEditor.svelte`
  (~110 LoC) — Container mit Empty-State, Liste und Add-Button.
- **NEU:** `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte`
  (~120 LoC) — Eine Zeile, zwei Modi (View / Edit).
- **MODIFY:** `frontend/src/lib/components/edit/TripEditView.svelte` (~30 LoC)
  — neuer Accordion-Block "Alarmregeln", `alertRules`-State, Save-Erweiterung.
- **MODIFY:** `frontend/src/lib/components/trip-detail/AlertsPreviewCard.svelte`
  (~10 LoC) — Edit-Link wieder ergänzen, zeigt auf `/trips/[id]/edit#alerts`.
- **NEU:** `frontend/src/lib/components/alert-rules-editor/AlertRulesEditor.test.ts`
  (Vitest, ~60 LoC) — Liste-Logik, Add/Delete.
- **NEU:** `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.test.ts`
  (Vitest, ~40 LoC) — View/Edit-Mode, Default-Generation.
- **MODIFY:** `frontend/e2e/trip-edit.spec.ts` (~30 LoC) — neuer Test für
  Add-Rule-Roundtrip (Add → Save → Reload → sichtbar).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `AlertRule`, `AlertRuleKind`, `AlertMetric`, `AlertSeverity` | TS-Type | `frontend/src/lib/types.ts:41-79` |
| `Trip.alert_rules` | `AlertRule[] | undefined` | Datenmodell aus Issue #205 |
| `ALERT_METRIC_LABELS`, `ALERT_SEVERITY_TONE`, `thunderLevelLabel` | aus `alertMetricLabels.ts` | W2-Helper, wiederverwendet |
| `Pill.svelte`, `Eyebrow.svelte`, `GCard` | Svelte-Komponenten | Design-System |
| `crypto.randomUUID()` | Browser-API | ID für neue Rules |

## Implementation Details

### 1. `AlertRulesEditor.svelte` — Container

```svelte
<script lang="ts">
    import type { AlertRule, AlertMetric } from '$lib/types';
    import AlertRuleRow from './AlertRuleRow.svelte';
    import { newDefaultRule } from './alertRuleDefaults';

    let { rules = $bindable<AlertRule[]>([]) }: { rules: AlertRule[] } = $props();

    function addRule() {
        rules = [...rules, newDefaultRule()];
    }

    function updateRule(index: number, updated: AlertRule) {
        rules = rules.map((r, i) => (i === index ? updated : r));
    }

    function deleteRule(index: number) {
        rules = rules.filter((_, i) => i !== index);
    }
</script>

<div class="alert-rules-editor" data-testid="alert-rules-editor">
    {#if rules.length === 0}
        <p class="empty-state" data-testid="alert-rules-editor-empty">
            Noch keine Alarmregeln konfiguriert.
        </p>
    {:else}
        <ul class="rules-list">
            {#each rules as rule, i (rule.id)}
                <li>
                    <AlertRuleRow
                        rule={rule}
                        onUpdate={(updated) => updateRule(i, updated)}
                        onDelete={() => deleteRule(i)}
                    />
                </li>
            {/each}
        </ul>
    {/if}
    <button
        type="button"
        data-testid="alert-rules-editor-add"
        class="add-button"
        onclick={addRule}
    >+ Regel hinzufügen</button>
</div>
```

### 2. `alertRuleDefaults.ts` — Helper für neue Rules

```typescript
import type { AlertRule } from '$lib/types';

export function newDefaultRule(): AlertRule {
    return {
        id: crypto.randomUUID(),
        kind: 'absolute',
        metric: 'wind_gust',
        threshold: 50,
        unit: 'km/h',
        severity: 'warning',
        enabled: true,
    };
}
```

Reason: Default = häufigster Use-Case (Wind-Böen 50 km/h). User editiert
sofort. Separate Funktion → unit-testbar.

### 3. `AlertRuleRow.svelte` — Zeile mit View/Edit-Modi

```svelte
<script lang="ts">
    import type { AlertRule, AlertMetric, AlertSeverity } from '$lib/types';
    import Pill from '$lib/components/ui/pill/Pill.svelte';
    import {
        ALERT_METRIC_LABELS, ALERT_SEVERITY_TONE, thunderLevelLabel
    } from '$lib/utils/alertMetricLabels';

    let {
        rule, onUpdate, onDelete
    }: {
        rule: AlertRule;
        onUpdate: (r: AlertRule) => void;
        onDelete: () => void;
    } = $props();

    let editing = $state(false);
    let draft = $state<AlertRule>({ ...rule });

    let info = $derived(ALERT_METRIC_LABELS[rule.metric]);
    let valueText = $derived(
        rule.metric === 'thunder_level'
            ? thunderLevelLabel(rule.threshold)
            : `${rule.threshold} ${info?.unit ?? ''}`.trim()
    );

    function startEdit() {
        draft = { ...rule };
        editing = true;
    }
    function saveEdit() {
        onUpdate(draft);
        editing = false;
    }
    function cancelEdit() {
        editing = false;
    }
</script>

{#if editing}
    <div class="alert-rule-edit" data-testid="alert-rule-edit">
        <select bind:value={draft.metric} data-testid="alert-rule-metric">
            <!-- Optionen für jede AlertMetric mit Label aus ALERT_METRIC_LABELS -->
        </select>
        {#if draft.metric === 'thunder_level'}
            <select bind:value={draft.threshold} data-testid="alert-rule-threshold">
                <option value={1.0}>MITTEL</option>
                <option value={2.0}>HOCH</option>
            </select>
        {:else}
            <input
                type="number"
                bind:value={draft.threshold}
                data-testid="alert-rule-threshold"
            />
        {/if}
        <select bind:value={draft.severity} data-testid="alert-rule-severity">
            <option value="info">Info</option>
            <option value="warning">Warnung</option>
            <option value="critical">Kritisch</option>
        </select>
        <label>
            <input type="checkbox" bind:checked={draft.enabled} />
            Aktiv
        </label>
        <button onclick={saveEdit} data-testid="alert-rule-save">Speichern</button>
        <button onclick={cancelEdit} data-testid="alert-rule-cancel">Abbrechen</button>
    </div>
{:else if info}
    <div
        class="alert-rule-view"
        data-testid="alert-rule-row"
        class:disabled={!rule.enabled}
    >
        <span class="label">{info.label_de}</span>
        <span class="threshold">{info.comparison} {valueText}</span>
        <Pill tone={ALERT_SEVERITY_TONE[rule.severity]}>{rule.severity}</Pill>
        <label class="enabled-toggle">
            <input
                type="checkbox"
                checked={rule.enabled}
                onchange={(e) => onUpdate({ ...rule, enabled: (e.target as HTMLInputElement).checked })}
            />
            Aktiv
        </label>
        <button onclick={startEdit} data-testid="alert-rule-edit-btn">Bearbeiten</button>
        <button onclick={onDelete} data-testid="alert-rule-delete">Löschen</button>
    </div>
{/if}
```

**Wichtig:** F004-Guard aus W2 wird hier wiederverwendet (`{#if info}` und
`info?.unit ?? ''`) — unbekannte Metric → kein Crash.

### 4. `TripEditView.svelte` — Integration

```typescript
// Z.15-24 erweitern:
let alertRules = $state<AlertRule[]>(
    Array.isArray(trip.alert_rules)
        ? (JSON.parse(JSON.stringify(trip.alert_rules)) as AlertRule[])
        : []
);

// Save-Handler Z.44-50:
const updated: Trip = {
    ...trip,
    name: tripName,
    stages,
    display_config: displayConfig,
    report_config: reportConfig,
    alert_rules: alertRules,  // NEU
};

// Accordion-Block (neu):
<AccordionSection id="alerts" title="Alarmregeln">
    <AlertRulesEditor bind:rules={alertRules} />
</AccordionSection>
```

Position des neuen Blocks: zwischen "Wetter" und "Reports".

### 5. `AlertsPreviewCard.svelte` — Edit-Link zurück

```svelte
<!-- nach dem Empty-State / Rules-List, vor </GCard>: -->
<a
    href={`/trips/${trip.id}/edit#alerts`}
    class="edit-link"
    data-testid="right-card-alerts-edit-link"
>Konfigurieren →</a>
```

TestID-Re-Aktivierung: bestehende E2E-Tests (AC-8, AC-9 aus
`trip-detail-overview-right.spec.ts`) waren in W2 entfernt worden — sie
können **nicht** einfach reaktiviert werden, weil AC-9 das Verhalten
"Klick → Hash + Tab-Wechsel" prüfte (Tab-Wechsel ist nicht im Scope von
#223). Neuer E2E-Test prüft nur Visibility + href-Ziel.

## Expected Behavior

- **Input:** Trip mit beliebigen `alert_rules` (auch leeres Array oder undefined)
- **Output Editor:** Liste mit allen Rules (auch disabled, visuell ausgegraut)
- **Add:** "+ Regel hinzufügen" erzeugt eine Default-Rule (wind_gust > 50,
  warning, enabled), die der User direkt editieren kann
- **Edit:** Inline-Form überschreibt die Rule beim Speichern
- **Delete:** Rule wird entfernt
- **Enabled-Toggle (im View-Mode):** Schaltet `enabled` direkt um — kein Edit-Submit nötig
- **Save (TripEditView):** PUT `/api/trips/{id}` mit `updated.alert_rules`

## Acceptance Criteria

- **AC-1:** Given Trip mit `alert_rules = []`, When `/trips/[id]/edit` geladen wird, Then ist der neue Accordion-Block "Alarmregeln" sichtbar, `[data-testid="alert-rules-editor-empty"]` zeigt "Noch keine Alarmregeln konfiguriert", und der Add-Button ist sichtbar.
  - Test: (populated after /tdd-red)

- **AC-2:** Given Trip mit `alert_rules = [{id:'r1', metric:'wind_gust', threshold:50, severity:'warning', enabled:true, kind:'absolute', unit:'km/h'}]`, When `/trips/[id]/edit` geladen wird, Then enthält `[data-testid="alert-rule-row"]` mit Text "Böen", "> 50 km/h" und Pill `tone="warning"`.
  - Test: (populated after /tdd-red)

- **AC-3:** Given offenen Editor mit 0 Rules, When User auf "+ Regel hinzufügen" klickt, Then erscheint genau eine neue Row mit Default-Werten (`metric='wind_gust'`, `threshold=50`, `severity='warning'`, `enabled=true`), und der View-Mode (nicht Edit) ist aktiv.
  - Test: (populated after /tdd-red)

- **AC-4:** Given Editor mit einer Rule, When User auf "Löschen" klickt, Then ist die Rule entfernt, und (bei 0 verbleibenden Rules) erscheint wieder der Empty-State.
  - Test: (populated after /tdd-red)

- **AC-5:** Given Editor mit einer Rule im View-Mode, When User auf "Bearbeiten" klickt, Then erscheinen Edit-Felder (`alert-rule-metric`, `alert-rule-threshold`, `alert-rule-severity`); User ändert `threshold` von 50 auf 60 und klickt "Speichern", Then zeigt die Row "> 60 km/h" und der Edit-Mode ist beendet.
  - Test: (populated after /tdd-red)

- **AC-6:** Given Editor mit einer Rule im Edit-Mode (gerade über "Bearbeiten" geöffnet), When User Änderungen macht und auf "Abbrechen" klickt, Then bleibt die Rule unverändert.
  - Test: (populated after /tdd-red)

- **AC-7:** Given Trip mit `alert_rules=[]`, When User über Editor eine Rule hinzufügt und auf "Speichern" (TripEditView-Save) klickt, Then enthält der PUT-Body `alert_rules` mit einer Rule (die Default-Werte), und beim erneuten Laden der Edit-Seite ist die Rule sichtbar.
  - Test: (populated after /tdd-red)

- **AC-8:** Given Trip mit ≥1 enabled Rule, When User die Trip-Detailseite öffnet, Then ist `[data-testid="right-card-alerts-edit-link"]` sichtbar in der `AlertsPreviewCard`, mit `href` der auf `/trips/[id]/edit#alerts` zeigt.
  - Test: (populated after /tdd-red)

- **AC-9:** Given Editor mit einer Rule und View-Mode, When User die Enabled-Checkbox toggled, Then ist der Rule-Zustand `enabled` umgeschaltet, ohne dass der Edit-Mode aktiviert wird.
  - Test: (populated after /tdd-red)

- **AC-10:** Given Editor mit Rule `metric='thunder_level', threshold=2.0`, When im View-Mode angezeigt, Then ist der Text "≥ HOCH" sichtbar (nicht "≥ 2"); im Edit-Mode ist das Threshold-Feld ein `<select>` mit Optionen "MITTEL" / "HOCH".
  - Test: (populated after /tdd-red)

## Known Limitations

- **Wizard bleibt unverändert** — `/trips/new` Step 4 zeigt weiter die 4
  Threshold-Felder. Umstellung auf `AlertRulesEditor` ist Folge-Iteration.
- **Δ-Felder in `WizardStep4ReportConfig` bleiben** — die alten
  `change_threshold_*`-Eingaben im Edit-Pfad Step 4 (Reports-Block) bleiben
  in `report_config`. User, die in beiden Blöcken (Reports und Alarmregeln)
  Werte setzen, haben effektiv beide Quellen aktiv. Backend-Priorität:
  `alert_rules` > `report_config` (W1). UI-Hinweis im Reports-Block in
  einer Folge-Iteration.
- **Vorlagen-Sets** (z.B. "Sommer-Wandern", "Winter-Skitour") sind nicht
  Teil dieses Issues — Folge-Iteration.
- **TEMPERATURE_MIN Kältealarm (Issue #224):** Der neue Editor unterstützt
  TEMPERATURE_MIN sofort (es ist eine AlertMetric in `ALERT_METRIC_LABELS`).
  Issue #224 wird damit teilweise hinfällig — User können Kältealarm
  direkt über den Editor anlegen. Eintrag in Issue #224 anpassen.

## Changelog

- 2026-05-14: Initial spec für Issue #223 (Option D — Liste-basierter Editor)
