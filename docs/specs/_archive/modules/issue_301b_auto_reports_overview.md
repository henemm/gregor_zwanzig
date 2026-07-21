---
entity_id: issue_301b_auto_reports_overview
type: module
created: 2026-05-23
updated: 2026-05-23
status: draft
version: "1.0"
issue: 301
tags: [frontend, svelte, compare, subscriptions, auto-reports, grid, issue-301, lieferung-b]
---

# Issue #301 Lieferung B — AutoReportsOverview (Default-Content als Kachelraster)

## Approval

- [ ] Approved

## Purpose

Lieferung B schließt den letzten offenen AC von Issue #301: Der Default-Content
im Compare-Bereich (bisher `CompareSubscriptionsPanel` — schlichte Karten-Liste ohne
visuelles Gewicht) wird durch ein gestaltetes **Auto-Reports-Kachelraster** ersetzt.
Das neue `AutoReportsOverview` zeigt Eyebrow + H1-Typografie und ein responsives CSS-Grid
aus `AutoReportCard`-Kacheln mit immer anhängender `AddReportCard`. Rein additiver
Frontend-Umbau ohne Backend-Änderungen; setzt Lieferung A (Group-Entity-Verdrahtung,
`issue_301_sidebar_groups`) als abgeschlossen voraus.

## Source

**Schicht: Frontend ausschließlich.** Kein Go-/Python-Backend wird geändert.

- **NEU:** `frontend/src/lib/components/compare/AutoReportsOverview.svelte`
- **NEU:** `frontend/src/lib/components/compare/AutoReportCard.svelte`
- **NEU:** `frontend/src/lib/components/compare/AddReportCard.svelte`
- **MODIFY:** `frontend/src/routes/compare/+page.svelte`
- **DELETE:** `frontend/src/lib/components/compare/CompareSubscriptionsPanel.svelte`
- **optional NEU:** `frontend/src/lib/components/compare/subscriptionHelpers.ts` (falls Helper extrahiert)

## Dependencies

| Entity | Art | Zweck |
|--------|-----|-------|
| `CompareSubscriptionsPanel.svelte` | Svelte-Komponente (ersetzt) | Bisheriger Default-Content; Helper `scheduleLabel`, `locationsLabel`, `formatLastRun` werden übernommen |
| `Subscription` | `frontend/src/lib/types.ts` | Props-Typ für `AutoReportCard` und `AutoReportsOverview` |
| `Eyebrow` | `$lib/components/ui/eyebrow` | Rubrik-Beschriftung über H1 (Vorbild: `trip-detail/BriefingPreviewCard.svelte:23`) |
| `Card` (`Card.Root`) | `$lib/components/ui/card` | Kachel-Wrapper für `AutoReportCard` und `AddReportCard` |
| `Dot` | `$lib/components/ui/dot` | Status-Indikator (enabled→`success`, disabled→`default`) |
| `Pill` | `$lib/components/ui/pill` | Last-Status-Anzeige (`ok`→`success`, `error`→`danger`) |
| `Btn` | `$lib/components/ui/btn` | Aktionsbutton in `AddReportCard` |
| Lucide Icons | `lucide-svelte` | `PlusIcon` in `AddReportCard` — kein Emoji (AP-009) |
| `--g-s-*` Spacing-Tokens | Design-System (`app.css`) | Grid-Gap, Padding, Margin — kein Magic-Pixel (AP-008) |
| `frontend/src/routes/compare/+page.svelte` | Svelte-Route | Rendert Default-Content an zwei Stellen (mobil + Desktop); Import wird getauscht |

## Implementation Details

### 1. Helper aus `CompareSubscriptionsPanel.svelte` übernehmen

Die drei bestehenden Hilfsfunktionen aus `CompareSubscriptionsPanel.svelte` —
`scheduleLabel()`, `locationsLabel()`, `formatLastRun()` — werden entweder direkt
in `AutoReportsOverview.svelte` (inline) übernommen oder in eine separate
`subscriptionHelpers.ts` extrahiert.

**Entscheidungsregel:** Werden die Helper nur von `AutoReportCard.svelte` benötigt und
nirgends sonst, bleiben sie inline. Soll eine Helper-Unit-Test-Datei entstehen, wird
`subscriptionHelpers.ts` erstellt und dort isoliert getestet.

```typescript
// scheduleLabel: Subscription → lesbare Uhrzeit (z.B. "07:30 Uhr")
// locationsLabel: Subscription → "Alle Orte" | "N Orte"
// formatLastRun: Subscription → "–" | "Nie" | formatierte Zeit
```

### 2. `AutoReportsOverview.svelte` (NEU)

Drop-in-Ersatz für `CompareSubscriptionsPanel`. Identische Props-Signatur.

**Props:**
```typescript
let {
  subscriptions,     // Subscription[]
  onsavebriefing,   // () => void
}: {
  subscriptions: Subscription[];
  onsavebriefing: () => void;
} = $props();
```

**Layout:**
```svelte
<section class="auto-reports-overview" data-testid="auto-reports-overview">
  <Eyebrow>Orts-Vergleich · Auto-Reports</Eyebrow>
  <h1 class="overview-heading">Deine Auto-Reports</h1>

  <div class="reports-grid" data-testid="reports-grid">
    {#each subscriptions as sub (sub.id)}
      <AutoReportCard subscription={sub} />
    {/each}
    <!-- Immer letzte Kachel -->
    <AddReportCard onclick={onsavebriefing} />
  </div>

  {#if subscriptions.length === 0}
    <p class="empty-hint" data-testid="empty-hint">
      Noch kein Auto-Report angelegt. Starte mit dem Vergleich und speichere ihn.
    </p>
  {/if}
</section>
```

**CSS-Grid (nur `--g-s-*`-Tokens, kein Magic-Pixel):**
```css
.reports-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--g-s-4);
}

@media (min-width: 640px) {
  .reports-grid { grid-template-columns: repeat(2, 1fr); }
}

@media (min-width: 1024px) {
  .reports-grid { grid-template-columns: repeat(3, 1fr); }
}
```

### 3. `AutoReportCard.svelte` (NEU)

Reine Anzeige-Kachel pro Subscription. Kein Edit-Handler (Out of Scope).

**Props:**
```typescript
let { subscription }: { subscription: Subscription } = $props();
```

**Layout innerhalb `Card.Root`:**
- Header-Zeile: `Dot` (**`tone`**=`enabled ? 'success' : 'default'`, `size="sm"`) + Name (truncate, `data-testid="card-name-{subscription.id}"`)
- Mittlere Zeile: Schedule in **JetBrains-Mono** (`font-family: var(--g-font-mono)` o. ä. Mono-Token/Klasse) · `locationsLabel`
- Footer: „Letzter Lauf: {formatLastRun}" + `Pill` (**`tone`**=`last_status === 'ok' ? 'success' : 'danger'`; nur gerendert wenn `last_run` vorhanden)

**WICHTIG (Prop-Namen, gegen Bestand verifiziert):** `Dot` und `Pill` nutzen das Prop **`tone`** (NICHT `variant`). Dot: `tone` + `size`; Pill: `tone` ∈ `default|success|warning|danger|info|accent`. Vorbild: das zu ersetzende `CompareSubscriptionsPanel.svelte` (`<Dot tone=… size="sm" />`, `<Pill tone="success">`).

```svelte
<Card.Root data-testid="auto-report-card-{subscription.id}">
  <div class="card-header">
    <Dot tone={subscription.enabled ? 'success' : 'default'} size="sm" />
    <span class="card-name">{subscription.name}</span>
  </div>
  <div class="card-schedule">
    <span class="mono">{scheduleLabel(subscription)}</span>
    <span class="separator">·</span>
    <span>{locationsLabel(subscription)}</span>
  </div>
  {#if subscription.last_run}
    <div class="card-footer">
      <span class="last-run-label">Letzter Lauf: {formatLastRun(subscription)}</span>
      <Pill tone={subscription.last_status === 'ok' ? 'success' : 'danger'}>
        {subscription.last_status === 'ok' ? 'OK' : 'Fehler'}
      </Pill>
    </div>
  {/if}
</Card.Root>
```

### 4. `AddReportCard.svelte` (NEU)

Gestrichelte „+"-Kachel als feste letzte Position im Grid. Gleiche Grid-Zellgröße.

**Props:**
```typescript
let { onclick }: { onclick: () => void } = $props();
```

```svelte
<button
  class="add-report-card"
  {onclick}
  data-testid="add-report-card"
  aria-label="Neuer Auto-Report"
>
  <PlusIcon size={24} />
  <span>Neuer Auto-Report</span>
</button>
```

Styling: gestrichelter Rahmen (`border: 2px dashed var(--g-ink-faint)`), zentrierter
Inhalt, gleiche `min-height` wie `AutoReportCard`, Hover-State mit `--g-ink-faint`-
Hintergrund-Tint. Kein Emoji, kein Hex-Literal.

### 5. `+page.svelte` — Import-Swap an beiden Render-Stellen

```svelte
<!-- ALT: -->
import CompareSubscriptionsPanel from '$lib/components/compare/CompareSubscriptionsPanel.svelte';

<!-- NEU: -->
import AutoReportsOverview from '$lib/components/compare/AutoReportsOverview.svelte';
```

Beide Render-Stellen (mobil ~Z.326 + Desktop ~Z.473, Bedingung
`{#if !result && !loading && !weatherLocationId}`) werden getauscht. Props bleiben
identisch:

```svelte
<!-- ALT: -->
<CompareSubscriptionsPanel
  subscriptions={data.subscriptions}
  onsavebriefing={() => (showSaveAsSubDialog = true)}
/>

<!-- NEU: -->
<AutoReportsOverview
  subscriptions={data.subscriptions}
  onsavebriefing={() => (showSaveAsSubDialog = true)}
/>
```

`CompareSubscriptionsPanel.svelte` wird nach dem Tausch gelöscht — die Datei hat
nach dem Import-Swap keine Nutzer mehr.

## Expected Behavior

- **Input:** `subscriptions: Subscription[]` (aus `data.subscriptions`, geladen via `+page.server.ts`), `onsavebriefing: () => void` (öffnet `SubscriptionForm`-Dialog)
- **Output:**
  - Default-Content (keine Orts-Selektion, kein Vergleichsergebnis) zeigt `Eyebrow` „Orts-Vergleich · Auto-Reports" + `<h1>Deine Auto-Reports`
  - Subscriptions erscheinen als responsives CSS-Grid (1 / 2 / 3 Spalten), nicht als vertikale Liste
  - Jede Kachel: Status-`Dot` + Name + Schedule (Mono) · Orte + optionaler Footer mit Letzter-Lauf + `Pill`
  - Immer letzte Kachel: `AddReportCard` mit `PlusIcon` und Text „Neuer Auto-Report"
  - Klick auf `AddReportCard` → `onsavebriefing()` → `SubscriptionForm`-Dialog öffnet (keine Navigation)
  - Bei 0 Subscriptions: nur `AddReportCard` + dezenter Hinweistext; keine leere Grid-Fläche
- **Side effects:** Keine — reiner Render-Umbau, keine neuen API-Calls, kein verändertes State-Management

## Acceptance Criteria

**AC-1:** Given der Compare-Bereich hat keine aktive Selektion und kein Vergleichsergebnis /
When die Seite geladen wird /
Then ist das Element mit `data-testid="auto-reports-overview"` sichtbar, enthält die Eyebrow-Beschriftung „Orts-Vergleich · Auto-Reports" und die H1 „Deine Auto-Reports".

**AC-2:** Given mindestens eine Subscription existiert /
When `AutoReportsOverview` gerendert wird /
Then erscheinen alle Subscriptions als Kacheln im Element `data-testid="reports-grid"` (CSS `display: grid`), nicht als vertikale `<ul>`/`<li>`-Liste.

**AC-3:** Given eine Subscription hat `enabled=true` und `last_status='ok'` /
When `AutoReportCard` gerendert wird /
Then zeigt die Kachel einen `Dot` mit `tone="success"` und eine `Pill` mit `tone="success"`; der Schedule-Text ist in JetBrains-Mono dargestellt.

**AC-4:** Given eine Subscription hat `enabled=false` und `last_status='error'` /
When `AutoReportCard` gerendert wird /
Then zeigt die Kachel einen `Dot` mit `tone="default"` (neutral) und eine `Pill` mit `tone="danger"`.

**AC-5:** Given die Subscription hat kein `last_run`-Feld (noch nie gelaufen) /
When `AutoReportCard` gerendert wird /
Then ist der Footer-Bereich mit Letzter-Lauf und `Pill` nicht sichtbar; kein leerer Platzhalter.

**AC-6:** Given `subscriptions` ist ein leeres Array /
When `AutoReportsOverview` gerendert wird /
Then ist ausschließlich die `AddReportCard` (`data-testid="add-report-card"`) sichtbar, plus der dezente Hinweistext (`data-testid="empty-hint"`); kein `AutoReportCard`-Element ist im DOM.

**AC-7:** Given die `AddReportCard` ist im Grid sichtbar /
When der User auf die Kachel klickt /
Then wird `onsavebriefing()` aufgerufen und der `SubscriptionForm`-Dialog öffnet sich; es findet keine Navigation statt (URL bleibt `/compare`).

**AC-8:** Given das Design-System schreibt AP-007/AP-008/AP-009 vor /
When alle drei neuen Komponenten (`AutoReportsOverview`, `AutoReportCard`, `AddReportCard`) gerendert werden /
Then enthält keines der Elemente Hex-Farbliterale, Magic-Pixel-Werte (ausgenommen 0) oder Emoji-Zeichen; alle Farben kommen aus Design-Token-Variablen, alle Abstände aus `--g-s-*`.

**AC-9:** Given `+page.svelte` rendert den Default-Content an zwei Stellen (mobil und Desktop) /
When der Import-Swap abgeschlossen ist /
Then ist `CompareSubscriptionsPanel` in keiner Datei mehr importiert; `CompareSubscriptionsPanel.svelte` existiert nicht mehr im Dateisystem.

## Known Limitations

- **Subscription-Edit/Delete:** Keine Edit- oder Lösch-Aktion innerhalb von `AutoReportCard`. Bearbeiten von Auto-Reports bleibt ausschließlich über den bestehenden `SubscriptionForm`-Dialog (via `AddReportCard`-Klick oder anderen Einstiegspunkt). Out of Scope für Lieferung B.
- **Gruppen-Bezug auf Subscriptions:** `Subscription` hat keine `group_id`. Das „Group-Label" in `locationsLabel` zeigt „Alle Orte" / „N Orte" aus der bestehenden Locations-Liste — kein direkter Gruppen-Bezug. Wird erst relevant, wenn Subscriptions selbst Group-aware werden (anderes Issue).
- **Kein Drag-Reorder:** Kacheln werden in der Reihenfolge der `subscriptions`-Array-Einträge gerendert. Manuelles Umsortieren ist Out of Scope.

## Changelog

- 2026-05-23: Initial spec erstellt — Lieferung B, AutoReportsOverview-Default-Content (Issue #301, nach Lieferung A Group-Entity-Verdrahtung).
