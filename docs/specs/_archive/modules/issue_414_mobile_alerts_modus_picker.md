---
entity_id: issue_414_mobile_alerts_modus_picker
type: module
created: 2026-05-27
updated: 2026-05-27
status: implemented
version: "1.0"
issue: 414
tags: [alerts-tab, frontend, mobile, modus-picker, fixed-footer, alertmetrictable, svelte, issue-414]
---

# Issue #414 — Mobile Alerts-Tab: Auslöse-Modus-Selektor (Δ / Schwellwert / Beides) + fixierter Footer

## Approval

- [ ] Approved

## Purpose

Der Alerts-Tab im Trip-Detail zeigt auf Mobile (≤899px) bisher nur die rohe `AlertMetricTable` ohne Kontext — kein erklärender Header, kein Hinweis, was die Schalter bewirken, kein Schnellzugriff zum Speichern. Dieses Feature ergänzt einen erklärenden Header, einen Auslöse-Modus-Selektor (Δ-Änderung / Schwellwert / Beides), der den Row-State der AlertMetricTable steuert, sowie einen fixierten Footer mit "Test-Alert senden" und "Speichern"-Buttons — alles ausschließlich auf Mobile; der Desktop-Alerts-Tab bleibt unverändert.

## Source

- **MODIFY:** `frontend/src/lib/components/alerts-tab/alertMetricTable.ts` — `deriveAlertMode()` + `applyModeToRowState()`
- **MODIFY:** `frontend/src/lib/components/alerts-tab/AlertMetricTable.svelte` — neuer `requestedMode?`-Prop + `$effect`
- **MODIFY:** `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` — Header, Modus-Picker (3 Radio-Karten), fixierter Mobile-Footer, `selectedMode`-State, Scroll-Padding
- **MODIFY:** `frontend/src/lib/components/alerts-tab/alertMetricTable.test.ts` — neue Unit-Tests für `deriveAlertMode()` und `applyModeToRowState()`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `AlertsTab.svelte` | Svelte-Komponente (`alerts-tab/AlertsTab.svelte`) | Wird um Header, Modus-Picker und fixierten Mobile-Footer erweitert |
| `AlertMetricTable.svelte` | Svelte-Komponente (`alerts-tab/AlertMetricTable.svelte`) | Erhält neuen `requestedMode?`-Prop; wendet Modus-Wechsel via `$effect` auf `RowStateMap` an |
| `alertMetricTable.ts` | TS-Modul (`alerts-tab/alertMetricTable.ts`) | Erhält zwei neue Pure Functions: `deriveAlertMode()` und `applyModeToRowState()` |
| `alertMetricTable.test.ts` | Test-Datei (`alerts-tab/alertMetricTable.test.ts`) | Erhält neue Tests für die beiden neuen Funktionen |
| `RowStateMap` / `MetricRowState` | TS-Typen (`alertMetricTable.ts`) | Datenmodell, das `applyModeToRowState()` in-place mutiert |
| `DELTA_ONLY_METRICS` | TS-Konstante (`alert-rules-editor/alertRuleDefaults.ts`) | Guard-Liste; `applyModeToRowState()` setzt kein `absEnabled=true` für diese Metriken |
| `AlertRule` | TS-Interface (`frontend/src/lib/types.ts`) | Quelle für `deriveAlertMode()`; liest `kind`-Felder aus den persistierten Regeln |
| `api.put()` | `$lib/api` | Speichern-Logik im Footer; identisch zur bestehenden `save()`-Funktion in AlertsTab |

## Implementation Details

### 1. Neue Pure Functions in `alertMetricTable.ts`

**`deriveAlertMode(rules: readonly AlertRule[]): 'absolute' | 'delta' | 'both'`**

Leitet den aktuellen Modus aus den persistierten `alert_rules` ab:

```typescript
export function deriveAlertMode(rules: readonly AlertRule[]): 'absolute' | 'delta' | 'both' {
  const hasAbs   = rules.some(r => r.kind === 'absolute' && r.enabled);
  const hasDelta = rules.some(r => r.kind === 'delta'    && r.enabled);
  if (hasAbs && hasDelta) return 'both';
  if (hasDelta)           return 'delta';
  return 'both'; // Default: 'both' (auch bei leerem Array und nur-absolute)
}
```

Default-Rückgabe ist `'both'` — entspricht dem empfohlenen Modus für neue/leere Trips.

**`applyModeToRowState(state: RowStateMap, mode: 'absolute' | 'delta' | 'both'): void`**

Mutiert `state` in-place; setzt `absEnabled`/`deltaEnabled`-Flags entsprechend dem gewählten Modus. Threshold-Werte (`absThreshold`, `deltaThreshold`) werden nicht verändert.

```typescript
export function applyModeToRowState(
  state: RowStateMap,
  mode: 'absolute' | 'delta' | 'both'
): void {
  for (const metric of ALL_ALERT_METRICS) {
    const row = state[metric];
    if (!row) continue;
    const isDeltaOnly = DELTA_ONLY_METRICS.has(metric);
    switch (mode) {
      case 'absolute':
        row.absEnabled   = !isDeltaOnly; // DELTA_ONLY_METRICS: absEnabled bleibt false
        row.deltaEnabled = false;
        break;
      case 'delta':
        row.absEnabled   = false;
        row.deltaEnabled = true;
        break;
      case 'both':
        row.absEnabled   = !isDeltaOnly;
        row.deltaEnabled = true;
        break;
    }
  }
}
```

### 2. `AlertMetricTable.svelte` — `requestedMode`-Prop + `$effect`

Neuer optionaler Prop `requestedMode?: 'absolute' | 'delta' | 'both'`. Ein `$effect` ruft `applyModeToRowState` auf, wenn sich der Prop ändert, und löst damit einen reaktiven Re-Render der Tabelle aus:

```typescript
let { alert_rules = $bindable([]), requestedMode }:
  { alert_rules: AlertRule[]; requestedMode?: 'absolute' | 'delta' | 'both' } = $props();

$effect(() => {
  if (requestedMode !== undefined) {
    applyModeToRowState(rowState, requestedMode);
  }
});
```

`rowState` ist der interne `$state`-Wert, den `AlertMetricTable` bereits verwaltet (aus `alertRulesToRowState(alert_rules)`). Durch die direkte Mutation + das `$effect`-Tracking löst Svelte 5 automatisch einen Re-Render aus.

### 3. `AlertsTab.svelte` — Header, Modus-Picker, fixierter Footer

**Neuer State:**
```typescript
import { deriveAlertMode } from './alertMetricTable.js';
let selectedMode = $state<'absolute' | 'delta' | 'both'>(
  deriveAlertMode(trip.alert_rules ?? [])
);
```

**Template-Struktur (Mobile-only-Blöcke via CSS):**

```svelte
<!-- Mobile-Header (display: none auf Desktop) -->
<div class="mobile-header">
  <h1 class="mobile-h1">Wann soll ein Alert ausgelöst werden?</h1>
  <p class="mobile-subtext">Alerts kommen zwischen Morgen- und Abend-Briefing. Wähle den Modus.</p>
</div>

<!-- Modus-Picker (3 Radio-Karten, Mobile-only) -->
<div class="mode-picker" role="radiogroup" aria-label="Auslöse-Modus">
  {#each MODES as m}
    <button
      role="radio"
      aria-checked={selectedMode === m.id}
      class="mode-card"
      class:active={selectedMode === m.id}
      onclick={() => selectedMode = m.id}
      data-testid="mode-card-{m.id}"
    >
      <span class="mode-eyebrow">{m.eyebrow}</span>
      <span class="mode-title">{m.title}</span>
      <span class="mode-desc">{m.desc}</span>
      <span class="mode-example">{m.example}</span>
    </button>
  {/each}
</div>

<!-- Metriken-Section-Heading (Mobile-only) -->
<p class="section-heading" data-testid="metrics-section-heading">
  METRIKEN & SCHWELLEN
</p>

<!-- Bestehende AlertMetricTable — erhält requestedMode -->
<AlertMetricTable bind:alert_rules={alertRules} requestedMode={selectedMode} />
```

**`MODES`-Konstante (im `<script>`-Block):**
```typescript
const MODES = [
  { id: 'delta'    as const, eyebrow: 'REAKTIV',     title: 'Δ-Änderung',  desc: 'Wert ändert sich seit letztem Report stark',       example: 'z.B. Wind +20 km/h'      },
  { id: 'absolute' as const, eyebrow: 'ABSOLUT',     title: 'Schwellwert', desc: 'Wert über-/unterschreitet eine Grenze',             example: 'z.B. Wind > 50 km/h'     },
  { id: 'both'     as const, eyebrow: 'EMPFOHLEN',   title: 'Beides',      desc: 'Δ und absolut kombiniert',                         example: 'Standard für aktive Trips' },
] as const;
```

**Fixierter Footer (Mobile-only, z-index: 55):**
```svelte
<div class="mobile-footer" data-testid="alerts-tab-mobile-footer">
  <button type="button" class="btn-ghost" disabled data-testid="alerts-tab-test-alert">
    Test-Alert senden
  </button>
  <button
    type="button"
    class="btn-primary"
    data-testid="alerts-tab-save"
    disabled={saving}
    onclick={save}
  >{saving ? 'Speichere…' : 'Speichern'}</button>
  {#if saveSuccess}
    <span class="success-msg" data-testid="alerts-tab-save-success">Gespeichert.</span>
  {/if}
  {#if saveError}
    <span class="error-msg" data-testid="alerts-tab-save-error">{saveError}</span>
  {/if}
</div>
```

**CSS — Mobile-Breakpoint (≤899px):**
```css
@media (max-width: 899px) {
  .alerts-tab {
    padding-bottom: 120px; /* Scroll-Padding: fixierter Footer überlagert sonst Inhalte */
  }
  .mobile-footer {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 55; /* BottomNav hat z-50=50, Footer liegt darüber */
    display: flex;
    align-items: center;
    gap: var(--g-s-3);
    padding: var(--g-s-3) var(--g-s-4);
    padding-bottom: calc(var(--g-s-4) + env(safe-area-inset-bottom, 0px));
    background: var(--g-paper);
    border-top: 1px solid var(--g-ink-faint);
  }
  .mobile-header,
  .mode-picker,
  .section-heading { display: block; }
}
@media (min-width: 900px) {
  .mobile-header,
  .mode-picker,
  .section-heading,
  .mobile-footer { display: none; }
}
```

**Aktive Modus-Karte (orange Outline):**
```css
.mode-card.active {
  border-color: var(--g-accent);
  box-shadow: 0 0 0 1px var(--g-accent) inset;
}
```

**Desktop-`save`-Feedback:** Der bestehende `.actions`-Block mit Speichern-Button, Success-Flash und Error-Message bleibt für Desktop (≥900px) unverändert erhalten. Der neue Mobile-Footer-Speichern-Button ruft dieselbe `save()`-Funktion auf.

### 4. Tests in `alertMetricTable.test.ts`

Neue Tests für die beiden Pure Functions (mock-frei, laufen unter `node --test`):

- `deriveAlertMode([])` → `'both'` (leeres Array = Default)
- `deriveAlertMode([abs-rule])` → `'both'` (nur absolute = Default)
- `deriveAlertMode([delta-rule])` → `'delta'`
- `deriveAlertMode([abs-rule, delta-rule])` → `'both'`
- `applyModeToRowState(state, 'absolute')` → `absEnabled=true` für alle Nicht-DELTA_ONLY-Metriken, `deltaEnabled=false` für alle
- `applyModeToRowState(state, 'delta')` → `absEnabled=false` für alle, `deltaEnabled=true` für alle
- `applyModeToRowState(state, 'both')` → `absEnabled=true` für Nicht-DELTA_ONLY, `deltaEnabled=true` für alle
- `applyModeToRowState(state, 'absolute')` mit DELTA_ONLY-Metrik → `absEnabled` bleibt `false`
- Threshold-Werte bleiben nach `applyModeToRowState` unverändert (kein Reset)

## Expected Behavior

- **Input:** Nutzer öffnet Alerts-Tab auf Mobile, wählt einen der drei Modus-Buttons ("Δ-Änderung", "Schwellwert", "Beides"), scrollt zur Metrik-Tabelle, tippt auf "Speichern" im fixierten Footer.
- **Output:**
  - Klick auf Modus-Karte: `selectedMode` wechselt → `requestedMode`-Prop von `AlertMetricTable` ändert sich → `$effect` ruft `applyModeToRowState` auf → alle Zeilen in der Tabelle aktualisieren ihre `absEnabled`/`deltaEnabled`-Flags reaktiv.
  - Threshold-Werte (z.B. Wind-Grenzwert 50 km/h) bleiben beim Modus-Wechsel erhalten.
  - Modus-Karte "Beides" wird bei Trip ohne `alert_rules` (oder nur absolute Rules) als Vorauswahl (orange Outline) gezeigt.
  - Fixierter Footer überlagert BottomNav; Seiteninhalt scrollt vollständig (padding-bottom: 120px).
  - Klick "Speichern" im Footer: `PUT /api/trips/{id}` mit `alert_rules` aus aktuellem Row-State.
- **Side effects:**
  - Desktop (≥900px): keinerlei sichtbare Änderung; Mobile-Header, Modus-Picker und fixierter Footer sind per CSS ausgeblendet.
  - DELTA_ONLY_METRICS (`temperature_change`, `wind_change`, `precipitation_change`, `thunder_level`): `applyModeToRowState` setzt nie `absEnabled=true` für diese Metriken, auch bei Modus "Schwellwert" und "Beides".

## Acceptance Criteria

- **AC-1:** Given Mobile-Viewport (≤899px) + Alerts-Tab offen / When der Tab gerendert wird / Then erscheint ein H1 "Wann soll ein Alert ausgelöst werden?" sichtbar oberhalb des Modus-Pickers.
  - Test: (populated after /tdd-red)

- **AC-2:** Given Alerts-Tab auf Mobile / When der Tab gerendert wird / Then sind 3 Modus-Karten mit `data-testid="mode-card-delta"`, `data-testid="mode-card-absolute"` und `data-testid="mode-card-both"` sichtbar.
  - Test: (populated after /tdd-red)

- **AC-3:** Given Trip ohne `alert_rules` (leeres Array) / When der Tab gerendert wird / Then trägt `data-testid="mode-card-both"` das Attribut `aria-checked="true"` (orange Outline = Vorauswahl).
  - Test: (populated after /tdd-red)

- **AC-4:** Given "Beides" ist aktiv / When Nutzer auf "Schwellwert" klickt / Then werden alle `deltaEnabled`-Flags auf `false` gesetzt und alle `absEnabled`-Flags auf `true` — außer für DELTA_ONLY_METRICS.
  - Test: (populated after /tdd-red)

- **AC-5:** Given "Beides" ist aktiv / When Nutzer auf "Δ-Änderung" klickt / Then werden alle `absEnabled`-Flags auf `false` gesetzt und alle `deltaEnabled`-Flags auf `true`.
  - Test: (populated after /tdd-red)

- **AC-6:** Given Modus "Schwellwert" ist aktiv und `absThreshold` für Wind-Böen ist 70 / When Nutzer auf "Beides" wechselt / Then bleibt `absThreshold` für Wind-Böen bei 70 (kein Reset durch Modus-Wechsel).
  - Test: (populated after /tdd-red)

- **AC-7:** Given Mobile-Viewport / When der Tab gerendert wird / Then erscheint ein Element mit `data-testid="alerts-tab-mobile-footer"` mit zwei Buttons: `data-testid="alerts-tab-test-alert"` (disabled) und `data-testid="alerts-tab-save"` (aktiv).
  - Test: (populated after /tdd-red)

- **AC-8:** Given fixierter Footer auf Mobile / When Nutzer auf `data-testid="alerts-tab-save"` klickt / Then wird `PUT /api/trips/{id}` mit dem aktuellen `alert_rules`-Array ausgeführt (identisch zur bestehenden Desktop-Speichern-Logik).
  - Test: (populated after /tdd-red)

- **AC-9:** Given fixierter Footer und ScrollInhalt darunter / When der Tab auf Mobile gerendert wird / Then hat `.alerts-tab` ein `padding-bottom` von mindestens 100px, sodass der gesamte Seiteninhalt erreichbar bleibt.
  - Test: (populated after /tdd-red)

- **AC-10:** Given Desktop-Viewport (≥900px) / When der Alerts-Tab gerendert wird / Then sind weder Mobile-Header (`mobile-header`) noch Modus-Picker (`mode-picker`) noch fixierter Footer (`alerts-tab-mobile-footer`) im DOM sichtbar (CSS `display: none`).
  - Test: (populated after /tdd-red)

- **AC-11:** Given DELTA_ONLY_METRICS (temperature_change, wind_change, precipitation_change, thunder_level) / When Nutzer Modus "Schwellwert" wählt / Then bleibt `absEnabled` für diese Metriken `false` (DELTA_ONLY Guard bleibt wirksam).
  - Test: (populated after /tdd-red)

## Known Limitations

- **"Test-Alert senden"-Button dauerhaft disabled:** Der Button ist im Footer sichtbar, aber für dieses Issue nicht funktional implementiert. Fachliche Implementierung (tatsächliches Versenden eines Test-Alerts) ist Out of Scope.
- **Modus-Ableitung bei nur-absolute Rules:** `deriveAlertMode()` gibt `'both'` zurück wenn ausschließlich absolute Rules vorhanden sind — da absolute-only ein ungewöhnlicher Zustand ist und "Beides" der empfohlene Modus ist. Bei Bedarf kann dies in einem Folge-Issue auf `'absolute'` geändert werden.
- **Kein visuelles Feedback bei Modus-Wechsel in Tabelle:** Die Row-State-Mutation ist reaktiv; es gibt keinen animierten Übergang zwischen den Zuständen.

## Files to Change

| # | Datei | Schicht | Aktion | LoC (netto) |
|---|-------|---------|--------|-------------|
| 1 | `frontend/src/lib/components/alerts-tab/alertMetricTable.ts` | Frontend | MODIFY — `deriveAlertMode()` + `applyModeToRowState()` | ~30 |
| 2 | `frontend/src/lib/components/alerts-tab/AlertMetricTable.svelte` | Frontend | MODIFY — `requestedMode?`-Prop + `$effect` | ~10 |
| 3 | `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` | Frontend | MODIFY — Header, Modus-Picker (MODES-Konstante + 3 Radio-Karten), `selectedMode`-State, fixierter Footer, CSS | ~90 |
| 4 | `frontend/src/lib/components/alerts-tab/alertMetricTable.test.ts` | Frontend/Test | MODIFY — 9 neue Unit-Tests | ~60 |

**Gesamt:** ~190 LoC netto, 4 Dateien (alle bestehend geändert, keine neuen Komponenten)

## Changelog

- 2026-05-27: Initial spec für Issue #414 — Mobile Alerts-Tab Modus-Picker (Δ/Schwellwert/Beides), `deriveAlertMode()` + `applyModeToRowState()` als Pure Functions, `requestedMode`-Prop auf AlertMetricTable, fixierter Footer (z-index 55 > BottomNav z-50), Scroll-Padding, Desktop unverändert, 11 Acceptance Criteria im AC-N Given/When/Then-Format.
