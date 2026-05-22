## Problem — semantischer Bug, nicht nur Styling

Wenn der User im Alert-Editor den Modus **„Beides"** wählt, zeigt das UI **nur EIN Threshold-Feld** (z.B. „50 km/h"). Das ist ambig:

> *„Wenn ‚Beides' ausgewählt ist: was beschreibt dann der Wert (z.B. 50 km/h)? Der ergibt m.E. keinen Sinn!"*
> — Product Owner, 2026-05-20

Tatsächlich erzeugt der Code (`alertRuleDefaults.ts → expandRules(rule, 'both')`) im Backend **zwei separate Regeln** aus einem „Beides"-Klick — beide mit demselben `threshold`. Das ist semantisch falsch: Absolut-Schwelle und Δ-Schwelle haben **unterschiedliche Einheiten** und Bedeutungen.

## Lösung

### A. „Beides" zeigt ZWEI Eingabefelder

Sobald der User „Beides" wählt, erscheinen im Edit-Form **zwei separate Threshold-Felder**:

1. **Absolut-Schwelle** — z.B. „> 80 km/h" (Einheit der Metrik)
2. **Änderungs-Schwelle** — z.B. „+30 km/h in 6 h" (Δ pro Zeitfenster)

Plus ein Zeitfenster-Select für die Änderungs-Schwelle (1h / 3h / 6h / 12h / 24h).

### B. Visuelle Sprache: „Beides = 2 Regeln"

Die UI kommuniziert klar dass „Beides" **zwei Regeln** anlegt. Im Mode-Selector steht ein Badge „2 Felder" / „1 Feld". Beim Speichern: Button-Label „Beide Regeln anlegen" / „Speichern (2 Regeln)".

### C. List-View: Paar-Markierung

In der Rule-Liste werden die zwei aus „Beides" hervorgegangenen Regeln visuell als Paar gekennzeichnet — mit einer Klammer / „paar"-Caption an der zweiten Zeile. So sieht der User sofort: das gehört zusammen.

## Files

- `src/lib/components/alert-rules-editor/AlertRuleRow.svelte`
- `src/lib/components/alert-rules-editor/ModeCard.svelte` (wird ersetzt durch `ModePill` mit Feld-Anzahl-Badge)
- `src/lib/components/alert-rules-editor/AlertRulesEditor.svelte`
- `src/lib/components/alert-rules-editor/alertRuleDefaults.ts` (`expandRules` muss zwei separate Thresholds aus dem Form bekommen)

## Dependencies

Voraussetzungen: Issues #00 (CSS-Tokens) + #01 (Form-Controls) — danach ist dieses Issue klein.

## Required changes

### 1. Form-State erweitern

```ts
// Edit form state
let editMode = $state<AlertRuleMode>('absolute');
let draftMetric = $state<AlertMetric>('wind_gust');
let draftAbsThreshold = $state<number>(80);             // for 'absolute' or 'both'
let draftDeltaThreshold = $state<number>(30);           // for 'delta' or 'both'
let draftDeltaWindow = $state<string>('6h');            // for 'delta' or 'both'
let draftSeverity = $state<AlertSeverity>('warning');
let draftEnabled = $state(true);
```

### 2. ModePill component (replaces ModeCard)

```svelte
<button class="mode-pill" class:selected
        role="radio" aria-checked={selected}
        onclick={onSelect}>
  <span class="mode-pill__label">{label}</span>
  <span class="mode-pill__sub">{sub}</span>
  <span class="mode-pill__badge">{inputs} Feld{inputs > 1 ? 'er' : ''}</span>
</button>
```

Three of them in a row:

| Label | Sub | inputs | Beschreibung |
|---|---|---|---|
| Absolut | Schwellwert | 1 | Wenn ein Wert eine harte Grenze überschreitet |
| Δ Änderung | Differenz | 1 | Wenn sich etwas stark verändert seit dem letzten Report |
| **Beides (empfohlen)** | Absolut + Δ | 2 | Erzeugt 2 Regeln — eine für Grenzwert, eine für Veränderung |

### 3. Conditional Threshold Inputs

```svelte
<div class="threshold-grid">
  <SelectField label="Metrik" bind:value={draftMetric}>
    {#each METRIC_OPTIONS as m}
      <option value={m}>{ALERT_METRIC_LABELS[m].label_de}</option>
    {/each}
  </SelectField>

  {#if editMode === 'absolute' || editMode === 'both'}
    <FieldLine label="Absolut-Schwelle" hint="Sofortige Warnung wenn dieser Wert erreicht wird">
      <ThresholdInput op=">" bind:value={draftAbsThreshold} unit={metricUnit} />
    </FieldLine>
  {/if}

  {#if editMode === 'delta' || editMode === 'both'}
    <FieldLine label="Änderungs-Schwelle" hint="Warnung wenn der Wert sich um diesen Betrag verändert">
      <div class="delta-row">
        <ThresholdInput op="Δ" bind:value={draftDeltaThreshold} unit={metricUnit} />
        <span class="delta-row__in">in</span>
        <Select bind:value={draftDeltaWindow}>
          <option value="1h">1 h</option>
          <option value="3h">3 h</option>
          <option value="6h">6 h</option>
          <option value="12h">12 h</option>
          <option value="24h">24 h</option>
        </Select>
      </div>
    </FieldLine>
  {/if}

  <SelectField label="Schweregrad" bind:value={draftSeverity}>
    <option value="info">Info</option>
    <option value="warning">Warnung</option>
    <option value="critical">Kritisch</option>
  </SelectField>
</div>
```

### 4. expandRules — accept two thresholds

```ts
// alertRuleDefaults.ts
export function expandRules(
  base: Omit<AlertRule, 'kind' | 'threshold'> & { metric: AlertMetric, severity: AlertSeverity, enabled: boolean },
  mode: AlertRuleMode,
  absThreshold: number,
  deltaThreshold: number,
  deltaWindow: string,
): AlertRule[] {
  const pairId = mode === 'both' ? crypto.randomUUID() : null;
  const rules: AlertRule[] = [];
  if (mode === 'absolute' || mode === 'both') {
    rules.push({ ...base, kind: 'absolute', threshold: absThreshold, pair_id: pairId });
  }
  if (mode === 'delta' || mode === 'both') {
    rules.push({ ...base, kind: 'delta', threshold: deltaThreshold, delta_window: deltaWindow, pair_id: pairId });
  }
  return rules;
}
```

Note `pair_id` — ergänze das auch im `AlertRule`-Type. Backend muss `pair_id` durchreichen.

### 5. List-View — Paar-Markierung

In `AlertRulesEditor.svelte`, beim Iterieren über `rules`, gruppiere nach `pair_id`:

```svelte
{#each rules as rule, i (rule.id)}
  {@const prev = i > 0 ? rules[i-1] : null}
  {@const isPairFollower = rule.pair_id && prev?.pair_id === rule.pair_id}
  <AlertRuleRow {rule} pairFollower={isPairFollower} … />
{/each}
```

And `AlertRuleRow`:

```svelte
{#if pairFollower}
  <span class="pair-marker" aria-hidden="true">
    <span class="pair-marker__corner"></span>
    <span class="pair-marker__caption">paar</span>
  </span>
{/if}
```

```css
.pair-marker {
  display: inline-flex; align-items: center; gap: 6px;
  padding-left: 14px; position: relative;
}
.pair-marker__corner {
  position: absolute; left: 0; top: -8px; bottom: 16px;
  width: 8px;
  border-left: 1.5px solid var(--g-accent);
  border-bottom: 1.5px solid var(--g-accent);
  border-bottom-left-radius: 4px;
}
.pair-marker__caption {
  font-family: var(--g-font-data); font-size: 9px;
  letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--g-accent-deep);
}
```

### 6. Visual restyle (depends on #00, #01)

After the token + control fixes land, ensure:

- ModePill selected state = `--g-accent` border + soft accent fill
- ThresholdInput in JetBrains Mono with tabular-nums
- SeverityPill = outlined (not filled), uses `--g-info` / `--g-warning` / `--g-danger`
- Severity-Label auf Deutsch (Info / Warnung / Kritisch — nicht das raw English)
- "Speichern"-Button = `<Btn variant="primary">` (ink-on-paper), kein blaues `.btn-primary`

## Acceptance criteria

- [ ] Wahl von „Beides" zeigt **zwei** Threshold-Eingaben (Absolut + Δ) plus ein Zeitfenster-Select.
- [ ] Mode-Buttons haben ein „N Feld(er)"-Badge.
- [ ] Beim Speichern mit Modus „Beides" werden zwei `AlertRule`-Objekte erzeugt (Backend mitkoordinieren wenn nötig).
- [ ] Die zwei Paar-Regeln tragen denselben `pair_id`.
- [ ] List-View markiert die zweite Regel eines Paars mit einer Klammer + „paar"-Caption.
- [ ] Severity-Labels auf Deutsch.
- [ ] Severity-Pill outlined, nicht filled.
- [ ] Alle Playwright-Tests grün — testen sowohl Single-Mode (vorher) als auch Beides-Mode (neu) Submission.

## 📎 Screenshots

**Soll: Anlege-Dialog mit „Beides" aktiv — ZWEI Eingabefelder**

![soll-alert-add](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-flow6B-add-rule.png)

**Soll: List-View mit Paar-Markierung**

![soll-alert-list](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-flow6A-list-inline-edit.png)

**Ist: ein Threshold-Feld bei „Beides" (ambig)**

![ist-alert-edit](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/08-alarmregeln-edit.png)