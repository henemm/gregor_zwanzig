---
entity_id: bug_281_290_stagestrip
type: module
created: 2026-05-20
updated: 2026-05-20
status: draft
version: "1.0"
tags: [frontend, cockpit, stagestrip, css-tokens, design-system, bugfix]
---

# Bug 281 + 290 — StageStrip: Pill-Truncation und falscher Accent-Fallback

## Approval

- [ ] Approved

## Purpose

Zwei zusammenhängende Bugs im Cockpit-Bereich werden gemeinsam behoben. Bug #290 entfernt einen falschen Hex-Fallback `#3b82f6` (Tailwind Blue-500) aus `StageDetailRow.svelte`, der gegen die in Issue #277 etablierte Konvention verstößt — der Token `--g-accent` ist stets in `app.css` definiert und braucht keinen Fallback. Bug #281 behebt das Umbrechen langer Stage-Namen im `StageStrip`: Pills sollen auf einer Textzeile bleiben und überstehende Namen per Ellipsis kürzen, während der Strip horizontal scrollbar bleibt und am rechten Rand eine Fade-Maske zeigt.

## Source

- **Layer:** Frontend / User-UI (`frontend/src/`)
- **Scope:** 4 Dateien — 2 Cockpit-Routen-Komponenten, 1 globaler CSS-Block, 1 Trip-Detail-Komponente

### Betroffene Dateien

| Datei | Bug | Änderung |
|---|---|---|
| `frontend/src/lib/components/trip-detail/StageDetailRow.svelte` | #290 | Z. 230: Fallback `#3b82f6` entfernen |
| `frontend/src/app.css` | #281 | `[data-slot="pill"]`-Block: `max-width`, `min-width`, `white-space` ergänzen |
| `frontend/src/routes/_cockpit/StagePill.svelte` | #281 | Label-Truncation + `title`-Tooltip + active-Weight |
| `frontend/src/routes/_cockpit/StageStrip.svelte` | #281 | Strip-Wrapper + Fade-Mask |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/app.css` | Upstream | Definiert `--g-accent`, `--g-paper` und den globalen `[data-slot="pill"]`-Block |
| `frontend/src/lib/components/ui/pill/Pill.svelte` | Shared Component | Rendert den `[data-slot="pill"]`-Span; Änderung an `app.css` wirkt auf alle Pill-Nutzer |
| `docs/reference/design_system.md` | Referenz | Design-Regeln für Token-Nutzung ohne Fallbacks |

## Implementation Details

### Fix #290 — Falscher Hex-Fallback in StageDetailRow (1 Zeile)

```diff
# frontend/src/lib/components/trip-detail/StageDetailRow.svelte, Z. 230
- background: var(--g-accent, #3b82f6);
+ background: var(--g-accent);
```

`--g-accent: #c45a2a` ist unter `:root` und `[data-theme="light"]` in `app.css` definiert. Ein Fallback-Argument ist laut Issue-#277-Konvention verboten, wenn der Token immer aufgelöst wird.

### Fix #281 — Pill-Truncation und Strip-Fade

**Schritt 1: `app.css` — `[data-slot="pill"]`-Block (Z. 309–317)**

```diff
  [data-slot="pill"] {
    display: inline-flex;
    align-items: center;
    padding: 0.125rem 0.5rem;
    border-radius: var(--g-radius-pill);
    font-family: var(--g-font-ui);
    font-size: 0.75rem;
    font-weight: 500;
+   max-width: 100%;
+   min-width: 0;
+   white-space: nowrap;
  }
```

`min-width: 0` erlaubt dem `inline-flex`-Container, unter seine intrinsische Breite zu schrumpfen. `white-space: nowrap` verhindert Zeilenumbruch innerhalb der Pill. `max-width: 100%` stellt sicher, dass Pill den Parent nicht sprengt. Diese Werte sind für alle Pill-Instanzen unbedenklich, da Chips/Tags systemweit einzeilige Labels tragen.

**Schritt 2: `StagePill.svelte` — Label-Truncation und Tooltip**

```diff
- <span data-testid="stage-pill" class={muted ? 'opacity-50' : ''}>
-   <Pill {tone}>
-     {label}
-   </Pill>
- </span>
+ <span
+   data-testid="stage-pill"
+   class="stage-pill"
+   class:muted
+   class:active
+   title={label}
+ >
+   <Pill {tone}>
+     <span class="stage-pill__label">{label}</span>
+   </Pill>
+ </span>
+
+ <style>
+   .stage-pill { flex: 0 0 auto; max-width: 180px; }
+   .stage-pill__label {
+     display: inline-block;
+     overflow: hidden;
+     text-overflow: ellipsis;
+     white-space: nowrap;
+     max-width: 100%;
+     vertical-align: middle;
+   }
+   .stage-pill.muted { opacity: 0.5; }
+   .stage-pill.active .stage-pill__label { font-weight: 600; }
+ </style>
```

`flex: 0 0 auto` verhindert, dass Pills im Strip-Flexbox schrumpfen oder wachsen. `max-width: 180px` ist lokal auf StagePill gescopet und wirkt nicht auf andere Pill-Nutzer. Der native `title`-Tooltip liefert den vollständigen Stage-Namen beim Hover ohne zusätzliche Komponente.

**Schritt 3: `StageStrip.svelte` — Fade-Mask**

```diff
- <div data-testid="stage-strip" class="flex gap-2 overflow-x-auto pb-2">
-   {#each stages as stage (stage.id || stage.date || stage.name)}
-     <StagePill ... />
-   {/each}
- </div>
+ <div class="strip-wrap">
+   <div data-testid="stage-strip" class="flex gap-2 overflow-x-auto pb-2 scroll-smooth">
+     {#each stages as stage (stage.id || stage.date || stage.name)}
+       <StagePill ... />
+     {/each}
+   </div>
+   <div class="strip-fade-right" aria-hidden="true"></div>
+ </div>
+
+ <style>
+   .strip-wrap { position: relative; }
+   .strip-fade-right {
+     position: absolute; top: 0; right: 0; bottom: 0;
+     width: 32px;
+     background: linear-gradient(to right, transparent, var(--g-paper));
+     pointer-events: none;
+   }
+ </style>
```

Die Fade-Maske nutzt `var(--g-paper)` — identisch mit dem Seitenhintergrund der Cockpit-Ansicht. `pointer-events: none` stellt sicher, dass die Maske Scroll-Interaktionen nicht blockiert. `aria-hidden="true"` hält das Element aus dem Accessibility-Tree heraus.

### Umsetzungsreihenfolge

1. Bug #290: `StageDetailRow.svelte` Z. 230 — 1-Zeilen-Fix
2. Bug #281a: `app.css` Pill-Block — globale CSS-Ergänzung
3. Bug #281b: `StagePill.svelte` — Label-Span + Scoped Styles
4. Bug #281c: `StageStrip.svelte` — Wrapper + Fade-Mask

## Expected Behavior

- **Input:** StageStrip erhält eine Liste von Stages, deren Namen beliebig lang sein können (z.B. "KHW_00a: Von Troblach Bhf nach Helmhotel")
- **Output:** Alle Pills erscheinen einzeilig; Namen werden ab ca. 180px mit Ellipsis gekürzt; der Strip scrollt horizontal; am rechten Rand ist eine Fade-Maske sichtbar; aktive Pills zeigen das Label in `font-weight: 600`; beim Hover über eine gekürzte Pill erscheint der vollständige Name als nativer Tooltip
- **Side effects:** `white-space: nowrap` im globalen `[data-slot="pill"]`-Block wirkt auf alle Pill-Nutzer im Frontend — unbedenklich, da alle existierenden Pill-Labels einzeilig sind (LocationsRail-Chips, AlertRuleRow-Badges, TripStatusBadge)

## Acceptance Criteria

- **AC-1:** Given der Quelltext von `StageDetailRow.svelte` / When `grep "var(--g-accent, #3b82f6)"` ausgeführt wird / Then ist die Trefferanzahl 0
  - Test: `grep -c "var(--g-accent, #3b82f6)" frontend/src/lib/components/trip-detail/StageDetailRow.svelte` → `0`

- **AC-2:** Given Stage-Pills im StageStrip mit langen Namen (>20 Zeichen) / When die Cockpit-Ansicht gerendert wird / Then überschreitet keine Pill eine Textzeile — Label endet mit `…` statt umzubrechen
  - Test: Playwright: `page.locator('[data-testid="stage-pill"] .stage-pill__label')` → `offsetHeight <= 20` (einzeilig) + `textContent` endet mit `…` bei gekürztem Label

- **AC-3:** Given eine Stage-Pill mit gekürztem Label / When der Mauszeiger über die Pill bewegt wird / Then erscheint der vollständige Stage-Name als nativer Browser-Tooltip (`title`-Attribut)
  - Test: Playwright: `page.locator('[data-testid="stage-pill"]').getAttribute('title')` → enthält vollständigen Stage-Namen

- **AC-4:** Given die aktive Stage-Pill (accent-Hintergrund, `tone='accent'`) / When die Pill gerendert wird / Then hat das Label `font-weight: 600`
  - Test: Playwright: `page.locator('[data-testid="stage-pill"].active .stage-pill__label')` → computed `fontWeight === '600'`

- **AC-5:** Given mehr Stage-Pills als in der Strip-Breite sichtbar / When der Strip gerendert wird / Then ist am rechten Rand eine Fade-Maske (transparent → `--g-paper`) sichtbar
  - Test: Visuelle Sichtprüfung (kein automatisierter Test — akzeptiert, da rein visuelles CSS-Feature)

- **AC-6:** Given alle anderen Pill-Nutzer im Frontend (LocationsRail, AlertRuleRow, TripStatusBadge) / When die Seiten gerendert werden / Then zeigen diese Komponenten keine visuelle Regression durch die `app.css`-Änderung
  - Test: Manuelle Sichtprüfung auf `/compare`, Trip-Detail-Alerts-Tab und Trip-Übersichtsseite

## Known Limitations

- AC-5 und AC-6 sind visuelle Verifikationen ohne automatisierten Test — manuelle Sichtprüfung oder Playwright-Screenshot nötig
- Die Fade-Maske ist immer sichtbar, auch wenn alle Pills in den sichtbaren Bereich passen (kein JavaScript-Check auf Overflow-State). Akzeptiert für diese Bugfix-Phase.
- `max-width: 180px` auf StagePill ist ein fixer Wert; bei sehr kleinen Viewports könnten Pills trotzdem eng wirken — Mobile-Optimierung ist in Issue #267/#269 adressiert, nicht hier

## Changelog

- 2026-05-20: Initial spec created (Bugs #281 + #290)
