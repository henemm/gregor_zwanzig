# Context: Issue #475 — OutputLayoutEditor nach organisms/ migrieren

## Request Summary
`OutputLayoutEditor.svelte` benutzt noch `ui/card` (verletzt AC-2 der Organisms-Schicht). Es soll auf `atoms/Card` umgestellt und in `organisms/index.ts` re-exportiert werden, analog zum Barrel-Pattern aus Epic #471.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/shared/OutputLayoutEditor.svelte` | Zu migrierendes Component — Zeile 13: `import * as Card from '$lib/components/ui/card/index.js'`, Zeile 108: `<Card.Root>`, Zeile 171: `</Card.Root>` |
| `frontend/src/lib/components/organisms/index.ts` | Barrel — OutputLayoutEditor hier eintragen |
| `frontend/src/lib/components/organisms/organisms.test.ts` | AC-2-Tests — neue Consumer-Checks für OutputLayoutEditor ergänzen |
| `frontend/src/lib/components/atoms/Card.svelte` | Ziel-Component — `children`-Snippet, `padding`, `accent`, `class`-Props |
| `frontend/src/lib/components/atoms/index.ts` | Exportiert schon `Card` — `import { Card }` direkt möglich |
| `frontend/src/lib/components/compare/steps/Step4Layout.svelte` | Consumer #1 — Zeile 18 |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Consumer #2 — Zeile 20 |
| `frontend/src/lib/components/trip-wizard/steps/Step4Layout.svelte` | Consumer #3 — Zeile 16 |
| `frontend/src/lib/components/shared/__tests__/OutputLayoutEditor.test.ts` | Kein Pfad-Update nötig — Datei bleibt in shared/ |
| `frontend/src/lib/components/trip-wizard/__tests__/issue_433_layout_dnd.test.ts` | Kein Pfad-Update nötig — referenziert shared/OutputLayoutEditor.svelte direkt |

## Existing Patterns

- **Barrel-Pattern (Epic #471):** Physische `.svelte`-Datei bleibt im Feature-Ordner (`shared/`). `organisms/index.ts` re-exportiert sie. Konsumenten importieren optional aus `organisms` statt dem direkten Pfad.
- **Atoms-Import:** `import { Btn, Eyebrow } from '$lib/components/atoms'` — Card wird ergänzt.
- **atoms/Card API:** Einfaches Wrapper-Div mit `children`-Snippet, kein `Card.Root`/`Card.Content`-Pattern.

## Konkrete Änderungen

### 1. `OutputLayoutEditor.svelte`
```diff
- import * as Card from '$lib/components/ui/card/index.js';
  import { Btn, Eyebrow } from '$lib/components/atoms';
+ import { Card } from '$lib/components/atoms';
```
Und in Template (2 Stellen):
```diff
- <Card.Root>
+ <Card>
...
- </Card.Root>
+ </Card>
```

### 2. `organisms/index.ts`
```diff
+ export { default as OutputLayoutEditor } from '../shared/OutputLayoutEditor.svelte';
```

### 3. Consumer-Imports (3 Dateien) — optional, aber issues-spec nennt es
Jede der 3 Consumer-Dateien:
```diff
- import OutputLayoutEditor from '$lib/components/shared/OutputLayoutEditor.svelte';
+ import { OutputLayoutEditor } from '$lib/components/organisms';
```

### 4. `organisms/organisms.test.ts` — neue Consumer-Checks
Die 3 neuen Consumers analog zu den bestehenden 4 CONSUMERS-Einträgen ergänzen.

## Dependencies

- **Upstream:** `atoms/Card` (bereits live, exportiert aus atoms/index.ts)
- **Downstream:** 3 Consumer-Files + organisms.test.ts

## Risks & Considerations

- `atoms/Card` ist ein einfaches `<div>` mit Snippet — kein `Card.Root/Content/Header`-Pattern. Die SMS-Sektion (Zeilen 108–171) ist ein einziger Block, der von `<Card.Root>` umschlossen ist → 1:1 auf `<Card>` ersetzen funktioniert, solange kein `Card.Content` etc. verwendet wird (→ Grep bestätigt: nur Root).
- Die Test-Dateien referenzieren `shared/OutputLayoutEditor.svelte` direkt über Dateisystem-Pfade → bleiben korrekt, da Datei nicht bewegt wird.
- `organisms.test.ts` hat AC-2-Checks nur für die 3 ursprünglichen Organisms — OutputLayoutEditor muss dort ergänzt werden, sonst bleibt AC-2-Verletzung unentdeckt.
