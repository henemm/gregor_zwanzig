# Context: Issue #299 — EditReportConfigSection Polish

## Request Summary

Die `EditReportConfigSection.svelte` hat fünf visuelle Inkonsistenzen gegenüber dem Design-System: Quick-Chips mit Raw-Tailwind, Link-Farbe im Channel-Hinweis falsch, Advanced-Toggle als Plain-Button statt Ghost-Chevron, fehlendes `m`-Suffix beim Wind-Exposition-Input, und Section-Container ohne `Card.Root`.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` | Hauptdatei, alle 5 Änderungen hier |
| `frontend/src/lib/components/edit/EditStagesSection.svelte` | Referenz für `g-num-with-unit`/`g-num-unit` Scoped-Styles + `Card.Root`-Verwendung + Ghost-Btn |
| `frontend/src/lib/components/edit/AccordionSection.svelte` | Referenz: ChevronDown mit `rotate(N deg)` inline-style |
| `frontend/src/app.css` | Definiert `.g-num-input` (JetBrains Mono + tabular-nums), `--g-accent: #c45a2a` |

## Current State (IST)

1. **Quick-Chips** — Existieren bereits (`makeMorningTimeHandler`), aber mit Raw-Tailwind: `rounded-md border border-input bg-background px-2 py-1 text-xs hover:bg-accent` — kein Brand-Token
2. **Channel-Hinweis-Links** — `hover:text-primary` (Browser-Blau Fallback) statt `var(--g-accent)`
3. **Advanced-Toggle** — Plain `<button class="text-sm font-semibold text-primary hover:underline">` — kein Ghost-Chevron
4. **Wind-Exposition** — Nacktes `<input type="number">` ohne Einheit-Suffix
5. **Section-Container** — `rounded-md border border-input p-3` — kein `<Card.Root>`
6. **Checkboxen** — Bereits `<Checkbox>` ✓ (kein Handlungsbedarf)

## Existing Patterns

- **`g-num-with-unit` / `g-num-unit`** — Scoped `<style>` in `EditStagesSection.svelte` (Zeilen 193–210); muss 1:1 in `EditReportConfigSection.svelte` dupliziert werden
- **`g-num-input`** — In `app.css` global definiert, direkt verwendbar als CSS-Klasse auf `<input>`
- **Ghost-Btn mit Chevron** — `<Btn variant="ghost" size="sm">` + `ChevronDown` aus `@lucide/svelte/icons/chevron-down` mit `transform: rotate(Ndeg)` (Muster: `AccordionSection.svelte` + `Sidebar.svelte`)
- **Card.Root** — `import * as Card from '$lib/components/ui/card/index.js'` + `<Card.Root class="p-4">` (Muster: `EditStagesSection.svelte` Zeile 72)
- **Quick-Chip Brand-Style** — Issue schlägt `.g-quick-chip` Klasse vor mit `border: 1px solid var(--g-ink-faint)`, `border-radius: var(--g-radius-pill)`, `font-family: var(--g-font-data)`

## Dependencies

- Upstream: `$lib/types` (ReportConfig), `$lib/utils/time` (toHHMMSS), `/api/auth/profile`
- Downstream: `EditTripPage.svelte` / Briefing-Tab (konsumiert die Komponente), keine weiteren

## Conflicts mit aktiven Workflows

- `bug-317` berührt `alertRuleDefaults.ts` und `alertMetricLabels.ts` — **kein Overlap**
- `bug-320` berührt Sidebar-Navigation — **kein Overlap**

## Test-IDs (müssen erhalten bleiben)

`morning-master-switch`, `report-morning-time`, `report-morning-quickpick-07`, `report-morning-quickpick-18`, `report-morning-trend`, `evening-master-switch`, `report-evening-time`, `report-evening-quickpick-07`, `report-evening-quickpick-18`, `report-evening-trend`, `channel-email`, `channel-email-hint`, `channel-signal`, `channel-signal-hint`, `channel-telegram`, `channel-telegram-hint`, `report-show-advanced`, `report-compact-summary`, `report-show-daylight`, `report-wind-exposition`

## Risks & Considerations

- **iOS-Zoom-Schutz (Bug #272):** `g-num-input` darf keine `font-size` setzen — ist in `app.css` bereits korrekt gelöst. Beim `type="time"` Input denselben Schutz beachten (kein `font-size < 16px` auf Mobile).
- **g-num-with-unit als Scoped-Style:** Da es in `EditStagesSection.svelte` als `<style>` definiert ist (Svelte-Scoped, kein globales CSS), muss es in `EditReportConfigSection.svelte` nochmals definiert werden.
- **Card.Root vs. bestehende Sections:** Import `* as Card` und Wrapper um alle 3 Sections — dabei `data-testid` auf den inneren Elementen erhalten.
