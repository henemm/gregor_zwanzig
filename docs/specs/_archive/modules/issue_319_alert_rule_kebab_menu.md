---
entity_id: issue_319_alert_rule_kebab_menu
type: module
created: 2026-05-22
updated: 2026-05-22
status: implemented
version: "1.0"
issue: 319
tags: [frontend, alert-rules, kebab-menu, alertrulerow, design-system, ap-005, issue-319]
---

# Issue #319 — AlertRuleRow: Aktions-Buttons ins Kebab-Menü

## Approval

- [ ] Approved

## Zweck

`AlertRuleRow.svelte` zeigt im View-Modus bisher zwei direkte Text-Buttons ("Bearbeiten", "Löschen") nebeneinander in der Zeile — ein Verstoß gegen Design-Anti-Pattern AP-005 ("zu viele direkte Aktions-Buttons pro Zeile"). Dieses Issue ersetzt die zwei direkten Buttons durch ein einzelnes Kebab-Dropdown-Menü (`⋯`), das sich per Klick öffnet und die Aktionen dahinter verbirgt. Dasselbe Muster wird bereits in der Trips-Liste (`/trips/+page.svelte`) verwendet und ist damit die etablierte Referenz-Implementierung im Projekt.

## Quelle / Source

- **MODIFY:** `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte` — primäre Änderung (Kebab-State, Dropdown-Block, Grid-Korrektur)
- **MODIFY:** `frontend/e2e/alert-rules-editor.spec.ts` — Klick-Sequenz um Kebab-Öffnen erweitern
- **MODIFY:** `frontend/e2e/issue-284-alert-rules-restyle.spec.ts` — Klick-Sequenz um Kebab-Öffnen erweitern
- **MODIFY:** `frontend/e2e/trip-wizard-step4.spec.ts` — Klick-Sequenz um Kebab-Öffnen erweitern

> **Schicht-Hinweis:** Alle Änderungen liegen ausschließlich im Frontend-Layer (`frontend/src/`). Kein Go-API-Code, kein Python-Backend-Code betroffen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte` | Svelte-Komponente | Primär geändert: Kebab-State + Dropdown-Block + CSS-Grid-Anpassung |
| `Btn` | Svelte-Komponente (`frontend/src/lib/components/ui/Btn.svelte`) | Wird für `⋯`-Trigger-Button (`variant="ghost" size="icon-sm"`) und Dropdown-Items verwendet |
| `frontend/src/routes/trips/+page.svelte` (Z. 376–427) | Referenz-Implementierung | Identisches Kebab-Muster: `kebabOpenId`, `onfocusout`-Schließen, `onkeydown Escape` — Vorlage für diese Implementierung |
| `frontend/e2e/alert-rules-editor.spec.ts` | E2E-Testdatei | Greift direkt auf `alert-rule-edit-btn` und `alert-rule-delete` zu — muss Kebab-Öffnen vorschalten |
| `frontend/e2e/issue-284-alert-rules-restyle.spec.ts` | E2E-Testdatei | Dasselbe — betroffen durch `data-testid`-Verschiebung ins Dropdown |
| `frontend/e2e/trip-wizard-step4.spec.ts` | E2E-Testdatei | Dasselbe — betroffen durch `data-testid`-Verschiebung ins Dropdown |
| Design-Anti-Pattern AP-005 | Design-System (CHARTER) | Verbot von >1 direktem Aktions-Button pro Zeile — Begründung für dieses Issue |

## Implementation Details

### 1. `AlertRuleRow.svelte` — Kebab-State im `<script>`

Eine neue State-Variable ans Ende der bestehenden `$state`-Deklarationen anhängen:

```typescript
let kebabOpen = $state(false);
```

Kein `kebabOpenId` nötig (anders als in `/trips/+page.svelte`), da es pro Zeile genau eine `AlertRuleRow`-Instanz gibt — ein boolescher State reicht.

### 2. View-Modus: Buttons ersetzen

Bestehender Abschnitt im `{:else}`-Zweig des `{#if editing}`-Blocks (View-Modus, `{#if info}`-Pfad), der aktuell zwei direkte Buttons enthält:

```svelte
<Btn variant="ghost" size="sm" type="button" onclick={startEdit}
     data-testid="alert-rule-edit-btn">Bearbeiten</Btn>
<Btn variant="ghost" size="sm" type="button" onclick={onDelete}
     data-testid="alert-rule-delete">Löschen</Btn>
```

Ersetzen durch:

```svelte
<div class="relative">
  <Btn variant="ghost" size="icon-sm" type="button"
       onclick={() => (kebabOpen = !kebabOpen)}
       aria-label="Aktionen"
       data-testid="alert-rule-kebab-trigger">⋯</Btn>

  {#if kebabOpen}
    <div
      class="kebab-dropdown"
      role="menu"
      onkeydown={(e: KeyboardEvent) => { if (e.key === 'Escape') kebabOpen = false; }}
      onfocusout={(e: FocusEvent) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node)) kebabOpen = false;
      }}
    >
      <button
        role="menuitem"
        onclick={() => { kebabOpen = false; startEdit(); }}
        data-testid="alert-rule-edit-btn"
      >Bearbeiten</button>

      <button
        role="menuitem"
        onclick={() => { kebabOpen = false; onDelete(); }}
        data-testid="alert-rule-delete"
      >Löschen</button>
    </div>
  {/if}
</div>
```

### 3. F004-Fallback-Pfad ebenfalls anpassen

Der `{:else}`-Block des äußeren `{#if info}`-Guards (unbekannte Metrik, F004-Fallback) enthält derzeit einen direkten "Löschen"-Button:

```svelte
<Btn variant="ghost" size="sm" onclick={onDelete} data-testid="alert-rule-delete">Löschen</Btn>
```

Diesen ebenfalls durch denselben Kebab-Block ersetzen wie in Schritt 2. Der F004-Dropdown enthält nur den "Löschen"-Eintrag (kein "Bearbeiten", da die Metrik unbekannt ist):

```svelte
<div class="relative">
  <Btn variant="ghost" size="icon-sm" type="button"
       onclick={() => (kebabOpen = !kebabOpen)}
       aria-label="Aktionen"
       data-testid="alert-rule-kebab-trigger">⋯</Btn>

  {#if kebabOpen}
    <div
      class="kebab-dropdown"
      role="menu"
      onkeydown={(e: KeyboardEvent) => { if (e.key === 'Escape') kebabOpen = false; }}
      onfocusout={(e: FocusEvent) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node)) kebabOpen = false;
      }}
    >
      <button
        role="menuitem"
        onclick={() => { kebabOpen = false; onDelete(); }}
        data-testid="alert-rule-delete"
      >Löschen</button>
    </div>
  {/if}
</div>
```

### 4. CSS-Grid: 7 → 6 Spalten

Der `grid-template-columns`-Wert in der CSS-Sektion enthält aktuell 7 `auto`-Einträge (einen für jeden sichtbaren Block). Da der Aktions-Block von 2 Buttons auf 1 `<div>` reduziert wird, einen `auto`-Eintrag entfernen:

```css
/* Vorher */
grid-template-columns: minmax(140px, 1fr) auto auto auto auto auto auto;

/* Nachher */
grid-template-columns: minmax(140px, 1fr) auto auto auto auto auto;
```

### 5. CSS: Kebab-Dropdown-Positionierung

Neuen Block in die `<style>`-Sektion aufnehmen:

```css
.kebab-dropdown {
  position: absolute;
  right: 0;
  top: 100%;
  z-index: 50;
  background: var(--g-surface);
  border: 1px solid var(--g-ink-faint);
  border-radius: 6px;
  min-width: 120px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.12);
  padding: 4px 0;
}

.kebab-dropdown button {
  display: block;
  width: 100%;
  padding: 8px 14px;
  text-align: left;
  background: none;
  border: none;
  cursor: pointer;
  font-size: var(--g-text-sm);
  color: var(--g-ink);
}

.kebab-dropdown button:hover {
  background: var(--g-surface-raised);
}
```

### 6. E2E-Tests — Kebab-Öffnen vorschalten

In allen drei betroffenen E2E-Dateien: jeder Klick auf `[data-testid="alert-rule-edit-btn"]` oder `[data-testid="alert-rule-delete"]` muss nun zuerst den `⋯`-Trigger klicken, damit das Dropdown sichtbar ist.

Muster (Playwright):

```typescript
// Vorher:
await page.getByTestId('alert-rule-edit-btn').click();

// Nachher:
await page.getByTestId('alert-rule-kebab-trigger').first().click();
await page.getByTestId('alert-rule-edit-btn').click();
```

Bei Tests, die mehrere Zeilen testen, den Trigger-Klick zeilenspezifisch über `.nth(index)` oder Kontext-Locator adressieren.

## Expected Behavior

- **Input:** View-Modus einer `AlertRuleRow` (Zeile nicht im Edit-Zustand), entweder mit bekannter Metrik (normaler Pfad) oder unbekannter Metrik (F004-Fallback).
- **Output:**
  - Nur der `⋯`-Button ist in der Zeile sichtbar — keine direkten Text-Buttons.
  - Klick auf `⋯` öffnet ein Dropdown mit "Bearbeiten" + "Löschen" (normaler Pfad) oder nur "Löschen" (F004-Fallback).
  - Klick auf "Bearbeiten" schließt Dropdown und öffnet Edit-Modus (wie bisher).
  - Klick auf "Löschen" schließt Dropdown und löscht die Regel (wie bisher).
  - `data-testid="alert-rule-edit-btn"` und `data-testid="alert-rule-delete"` bleiben auf den Dropdown-Einträgen erhalten (E2E-Kompatibilität).
- **Side effects:**
  - `kebabOpen` wird auf `false` gesetzt, wenn Fokus das Dropdown verlässt (`onfocusout`) oder Escape gedrückt wird.
  - Keine Änderungen am Datenmodell, kein API-Call durch diese Änderung.
  - CSS-Grid-Anpassung ändert das visuelle Layout der Zeile minimal (eine Spalte weniger).

## Acceptance Criteria

- **AC-1:** Given die Alert-Regeln-Liste im View-Modus / When die Seite gerendert wird / Then sind keine Buttons mit Text "Bearbeiten" oder "Löschen" direkt sichtbar — nur der `⋯`-Button (`data-testid="alert-rule-kebab-trigger"`) ist in jeder Zeile sichtbar.
  - Test: (populated after /tdd-red)

- **AC-2:** Given der `⋯`-Button in einer Alert-Regel-Zeile / When darauf geklickt wird / Then öffnet sich ein Dropdown (`role="menu"`) mit zwei Einträgen: "Bearbeiten" (`data-testid="alert-rule-edit-btn"`) und "Löschen" (`data-testid="alert-rule-delete"`).
  - Test: (populated after /tdd-red)

- **AC-3:** Given das offene Kebab-Dropdown / When "Bearbeiten" geklickt wird / Then schließt sich das Dropdown und die Zeile wechselt in den Edit-Modus (Threshold-Input sichtbar, Speichern-Button sichtbar).
  - Test: (populated after /tdd-red)

- **AC-4:** Given das offene Kebab-Dropdown / When "Löschen" geklickt wird / Then schließt sich das Dropdown und die Regel ist aus der Liste entfernt.
  - Test: (populated after /tdd-red)

- **AC-5:** Given das offene Kebab-Dropdown / When die Escape-Taste gedrückt oder der Fokus das Dropdown verlässt (`onfocusout` schlägt an) / Then schließt sich das Dropdown und der `⋯`-Button ist wieder alleinig sichtbar.
  - Test: (populated after /tdd-red)

- **AC-6:** Given der F004-Fallback-Pfad (unbekannte Metrik, `{:else}` im `{#if info}`-Guard) / When die Seite gerendert wird / Then zeigt auch diese Zeile nur den `⋯`-Button statt einem direkten "Löschen"-Button; das Dropdown enthält nur "Löschen" (kein "Bearbeiten").
  - Test: (populated after /tdd-red)

## Known Limitations

- **Kein Multi-Select:** Das Kebab-Muster schließt immer nach einer Aktion. Wenn in Zukunft Bulk-Aktionen (mehrere Regeln gleichzeitig löschen) gewünscht sind, ist ein anderes Interaktionsmodell nötig.
- **Fokus-Management:** Nach dem Schließen via Escape springt der Fokus nicht explizit auf den `⋯`-Trigger zurück — Basis-Accessibility ist gegeben, aber kein vollständiges ARIA-Keyboard-Navigation-Muster implementiert.
- **Nur View-Modus betroffen:** Die Edit-Modus-Buttons ("Speichern", "Abbrechen") bleiben direkte Buttons in der Zeile — das ist korrekt, da sie im aktiven Bearbeitungskontext stehen.

## Files to Change

| # | Datei | Schicht | Aktion | LoC (netto) |
|---|-------|---------|--------|-------------|
| 1 | `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte` | Frontend | MODIFY — Kebab-State, Dropdown-Block (×2 für normalen Pfad + F004), Grid-Korrektur, CSS | ~40 |
| 2 | `frontend/e2e/alert-rules-editor.spec.ts` | Frontend/E2E | MODIFY — Kebab-Öffnen vor Edit/Delete-Klicks vorschalten | ~10 |
| 3 | `frontend/e2e/issue-284-alert-rules-restyle.spec.ts` | Frontend/E2E | MODIFY — Kebab-Öffnen vorschalten | ~5 |
| 4 | `frontend/e2e/trip-wizard-step4.spec.ts` | Frontend/E2E | MODIFY — Kebab-Öffnen vorschalten | ~5 |

**Gesamt:** ~60 LoC netto, 4 Dateien (alle bestehend geändert)

## Changelog

- 2026-05-22: Initial spec erstellt. Ersetzt 2 direkte Aktions-Buttons in AlertRuleRow durch Kebab-Dropdown (`⋯`) gemäß AP-005 — Referenz-Implementierung aus `/trips/+page.svelte`. F004-Fallback-Pfad ebenfalls berücksichtigt. 4 Dateien, ~60 LoC.
