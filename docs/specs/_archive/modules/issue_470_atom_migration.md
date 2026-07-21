# Spec: issue_470 — ui/-Atom-Importe auf atoms/ migrieren

## Kontext

Epic #368 hat die `atoms/`-Bibliothek aufgebaut. Die 9 Wrapper-Atome existieren
in `lib/components/atoms/`, aber Anwendungskomponenten importieren diese noch
direkt aus `ui/`. Ziel ist eine einzige kanonische Import-Quelle.

## Scope — Was wird migriert

Nur die **9 Wrapper-Atome** (die intern an `ui/` delegieren):

| Atom | Alter Import-Pfad (zu ersetzen) |
|------|---------------------------------|
| Btn | `$lib/components/ui/btn{/index.js,/Btn.svelte,}` |
| Eyebrow | `$lib/components/ui/eyebrow{/index.js,/Eyebrow.svelte,}` |
| Pill | `$lib/components/ui/pill{/index.js,/Pill.svelte,}` |
| Input | `$lib/components/ui/input{/index.js,/input.svelte,}` |
| Segmented | `$lib/components/ui/segmented{/Segmented.svelte,}` |
| Dot | `$lib/components/ui/dot{/Dot.svelte,}` |
| WIcon | `$lib/components/ui/wicon{/index.js,/WIcon.svelte,}` |
| ElevSparkline | `$lib/components/ui/elev-sparkline{/ElevSparkline.svelte,}` |
| TopoBg | `$lib/components/ui/topo{/TopoBg.svelte,}` |

**Neuer Import:** `import { Btn, Eyebrow, ... } from '$lib/components/atoms'`

## Was NICHT migriert wird (Compound-Primitive, bleiben auf ui/)

- Dialog, Table, Select, Checkbox, Label, Badge, G-Card, EmptyState
- Sidebar-Komponenten (TopAppBar, BottomNav)
- Wordmark, HorizonChip
- `ui/card/index.js` (Compound mit Card.Root/Header/Content — verschieden von atoms/Card)

## Migrations-Strategie

Für jede betroffene Datei:
1. Bestehende ui/-Atom-Imports entfernen
2. Namen in einen einzigen `import { ... } from '$lib/components/atoms'` zusammenführen
3. Falls bereits ein atoms-Import existiert: Namen ergänzen, kein Duplikat

## Acceptance Criteria

**AC-1:** Given eine Svelte-Datei außerhalb von `ui/` und `atoms/` / When sie
eines der 9 Wrapper-Atome nutzt / Then importiert sie ausschließlich aus
`$lib/components/atoms` (oder `$lib/components/atoms/index`), nie mehr aus
`$lib/components/ui/{atom-pfad}`.

**AC-2:** Given alle migrierten Dateien / When `cd frontend && npm run build`
ausgeführt wird / Then Exit-Code 0, keine TypeScript-Fehler.

**AC-3:** Given die App nach Migration / When `cd frontend && npm test` (node:test)
ausgeführt wird / Then alle bestehenden Tests grün, keine Regression.

## Nicht in Scope

- Organisms-Schicht (folgt als separates Epic)
- Visuelle Änderungen (keine)
- atoms/-Wrapper-Implementierungen selbst (keine Änderung nötig)
