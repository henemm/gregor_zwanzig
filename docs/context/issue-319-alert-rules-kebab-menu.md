# Context: Issue #319 — Alarmregeln-Liste: Bearbeiten/Löschen in Kebab-Menü

## Request Summary
Im View-Modus von `AlertRuleRow.svelte` sind "Bearbeiten" und "Löschen" als direkte Text-Buttons sichtbar. Laut Design-System ANTI-PATTERN AP-005 gehören Sekundäraktionen in ein Kebab-Menü (`⋯`).

## IST vs. SOLL
- **IST (Screenshot 09):** `Böen > 51 km/h · Abs · warning · ✓ Aktiv · Bearbeiten · Löschen`
- **SOLL (Screenshot soll-flow6A):** `Böen · > 51 km/h · Abs · WARNUNG · ✓ Aktiv · ···`

## Betroffene Dateien

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte` | Primäre Änderung — View-Modus Z. 261–302 |
| `frontend/src/lib/components/alert-rules-editor/AlertRulesEditor.svelte` | Container, keine Änderung nötig |
| `frontend/src/routes/trips/+page.svelte` | Referenz-Implementierung des Kebab-Musters |

## Existierendes Kebab-Muster (trips/+page.svelte)

```svelte
<div class="relative">
  <Btn variant="ghost" size="icon-sm" title="Weitere Aktionen" aria-label="Weitere Aktionen"
    onclick={(e) => { e.stopPropagation(); kebabOpenId = kebabOpenId === trip.id ? null : trip.id; }}
  >⋯</Btn>
  {#if kebabOpenId === trip.id}
    <div role="menu" class="absolute right-0 top-full mt-1 z-50 min-w-[200px] rounded-md border bg-popover shadow-md py-1"
      tabindex="-1"
      onfocusout={(e) => { if (!(e.currentTarget).contains(e.relatedTarget)) kebabOpenId = null; }}
    >
      <button class="w-full text-left px-3 py-1.5 text-sm hover:bg-muted" onclick={...}>Bearbeiten</button>
      <button class="w-full text-left px-3 py-1.5 text-sm text-destructive hover:bg-muted" onclick={...}>Löschen</button>
    </div>
  {/if}
</div>
```

In `AlertRuleRow` ist kein globaler State nötig — lokaler `$state(false)` pro Zeile reicht, da jede Zeile eine eigene Komponente-Instanz ist.

## Notwendige Änderungen in AlertRuleRow.svelte

1. **State:** `let kebabOpen = $state(false);` hinzufügen
2. **View-Modus (Z. 262–301):** Zwei `<Btn>`-Elemente (Bearbeiten + Löschen) ersetzen durch Kebab-Button + Dropdown-Block
3. **Grid-Spalten (Z. 313):** `grid-template-columns` anpassen — statt 2 Button-Spalten nur 1 Icon-Spalte
4. **Unbekannte-Metric-Fallback (Z. 305–308):** Löschen-Button dort ebenfalls in Kebab wrappen

## Grid-Spalten Anpassung
- IST: `minmax(140px, 1fr) auto auto auto auto auto auto` (7 Spalten)
- SOLL: `minmax(140px, 1fr) auto auto auto auto auto` (6 Spalten — 2 Buttons → 1 Kebab)

## Dependencies
- `Btn`-Komponente aus `$lib/components/ui/btn` (bereits importiert)
- Kein neuer Import nötig
- `data-testid`-Attribute müssen erhalten bleiben:
  - `alert-rule-edit-btn` → im Kebab-Item "Bearbeiten"
  - `alert-rule-delete` → im Kebab-Item "Löschen"

## Risiken
- **Paar-Follower-Zeile:** Hat ebenfalls View-Modus — Kebab-Wrap gilt für alle View-Rows
- **Unbekannte Metric (F004-Guard):** Nur Löschen-Button vorhanden — dieser kommt ebenfalls ins Kebab
- **Keyboard/A11y:** `onfocusout`-Handler und `Escape`-Key sicherstellen (wie in trips/+page)

## E2E-Tests
Existierende Spec: `frontend/e2e/trip-detail-tabs.spec.ts` (Alerts-Tab)  
`data-testid="alert-rule-edit-btn"` und `data-testid="alert-rule-delete"` werden von Tests genutzt — müssen erhalten bleiben.
