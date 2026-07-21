---
entity_id: issue_475_outputlayouteditor_organisms_migration
type: module
created: 2026-05-31
updated: 2026-05-31
status: implemented
version: "1.0"
tags: [frontend, atomic-design, organisms, issue-475, outputlayouteditor]
---

<!-- Issue #475 — OutputLayoutEditor in Organisms-Schicht aufnehmen (ui/card-Abhängigkeit auflösen) -->

# Issue #475 — OutputLayoutEditor Organisms-Migration

## Approval

- [x] Implemented (2026-05-31)

## Purpose

`OutputLayoutEditor.svelte` importiert derzeit direkt aus `$lib/components/ui/card`, was die Schicht-Trennung der Organisms-Ebene (Epic #471, AC-2) verletzt. Diese Migration löst die verbotene `ui/`-Abhängigkeit auf, indem `Card` aus der `atoms/`-Schicht bezogen wird, und nimmt `OutputLayoutEditor` anschließend als vierten Eintrag in den Organisms-Barrel (`organisms/index.ts`) auf. Durch die Bereinigung werden alle drei Consumer-Dateien auf den kanonischen `organisms/`-Pfad umgestellt und `organisms.test.ts` um die entsprechenden Source-Inspection-Einträge erweitert.

## Source

- **File:** `frontend/src/lib/components/shared/OutputLayoutEditor.svelte`
- **Identifier:** `OutputLayoutEditor` (default export)

> **Schicht-Hinweis:** Reine Frontend-Änderung (SvelteKit `frontend/src/lib/components/`). Keine Go/Python-Schicht betroffen.

## Estimated Scope

- **LoC:** ~15 netto
- **Files:** 6
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/atoms/` (#371) | Atom-Schicht (upstream) | Liefert `Card`-Atom als Ersatz für den bisherigen `ui/card`-Import |
| `frontend/src/lib/components/atoms/index.ts` | Barrel (upstream) | `Card` muss dort exportiert sein (ist live seit Epic #371) |
| `frontend/src/lib/components/organisms/index.ts` | Barrel (upstream, ändern) | Erhält neuen Re-Export-Eintrag für `OutputLayoutEditor` |
| `frontend/src/lib/components/organisms/organisms.test.ts` | Test (ändern) | CONSUMERS-Array bekommt 3 neue Einträge für die Consumer-Dateien |
| `frontend/src/lib/components/compare/steps/Step4Layout.svelte` | Consumer (ändern) | Import auf `$lib/components/organisms` umstellen |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Consumer (ändern) | Import auf `$lib/components/organisms` umstellen |
| `frontend/src/lib/components/trip-wizard/steps/Step4Layout.svelte` | Consumer (ändern) | Import auf `$lib/components/organisms` umstellen |

## Implementation Details

### Schritt 1: `OutputLayoutEditor.svelte` — ui/card-Import ersetzen

Zeile 13 in `OutputLayoutEditor.svelte` lautet aktuell:

```typescript
import * as Card from '$lib/components/ui/card/index.js';
```

Ersetzen durch:

```typescript
import Card from '$lib/components/atoms/Card.svelte';
```

Anschließend an den zwei Verwendungsstellen (Zeile 108, Zeile 171) `<Card.Root>` durch `<Card>` ersetzen. Schließende `</Card.Root>`-Tags entsprechend auf `</Card>` ändern. Keine weiteren Card-Sub-Komponenten (`Card.Header`, `Card.Content` o.ä.) werden in der Datei verwendet — der Austausch ist ein 1:1-Tag-Rename.

### Schritt 2: `organisms/index.ts` — OutputLayoutEditor aufnehmen

Den bestehenden Barrel um eine vierte Export-Zeile ergänzen:

```typescript
export { default as OutputLayoutEditor } from '../shared/OutputLayoutEditor.svelte';
```

Die drei bestehenden Exports (TripHeader, TripWizardShell, AlertRulesEditor) bleiben unverändert.

### Schritt 3: Consumer-Imports auf `organisms/` umstellen (3 Dateien)

| Datei | Alter Import | Neuer Import |
|-------|-------------|-------------|
| `compare/steps/Step4Layout.svelte` | direkter Pfad auf `../../shared/OutputLayoutEditor.svelte` o.ä. | `import { OutputLayoutEditor } from '$lib/components/organisms'` |
| `trip-detail/WeatherMetricsTab.svelte` | direkter Pfad auf `../shared/OutputLayoutEditor.svelte` o.ä. | `import { OutputLayoutEditor } from '$lib/components/organisms'` |
| `trip-wizard/steps/Step4Layout.svelte` | direkter Pfad auf `../../shared/OutputLayoutEditor.svelte` o.ä. | `import { OutputLayoutEditor } from '$lib/components/organisms'` |

Den genauen Import-Pfad vor dem Edit per `grep -n OutputLayoutEditor` in jeder Consumer-Datei verifizieren.

### Schritt 4: `organisms.test.ts` — CONSUMERS-Array erweitern

Die drei Consumer-Dateien als neue Einträge in das bestehende CONSUMERS-Array aufnehmen. Struktur analog zu den vorhandenen Einträgen für TripHeader/TripWizardShell/AlertRulesEditor. Der Test prüft per Regex auf Import-Zeilen, dass jede Consumer-Datei `OutputLayoutEditor` ausschließlich aus `$lib/components/organisms` bezieht.

```typescript
{ name: 'Step4Layout (compare)', path: '../compare/steps/Step4Layout.svelte', organism: 'OutputLayoutEditor' },
{ name: 'WeatherMetricsTab', path: '../trip-detail/WeatherMetricsTab.svelte', organism: 'OutputLayoutEditor' },
{ name: 'Step4Layout (trip-wizard)', path: '../trip-wizard/steps/Step4Layout.svelte', organism: 'OutputLayoutEditor' },
```

### Nicht ändern

- `frontend/src/lib/components/shared/__tests__/OutputLayoutEditor.test.ts` — referenziert die physische Datei direkt, bleibt unberührt.
- `tests/tdd/issue_433_layout_dnd.test.ts` (oder analoger Pfad) — referenziert ebenfalls physischen Pfad, bleibt unberührt.
- Physischer Speicherort von `OutputLayoutEditor.svelte` (`shared/`) bleibt unverändert (Barrel-Pattern).

### Schritt 5: Build-Verifikation

```bash
cd frontend && npm run build
node --test src/lib/components/organisms/organisms.test.ts
```

Beide Schritte müssen ohne Fehler abschließen.

## Expected Behavior

- **Input:** keiner zur Laufzeit (reine Komponenten-Refaktorierung).
- **Output:** `import { OutputLayoutEditor } from '$lib/components/organisms'` liefert die Komponente; `npm run build` ist grün; `organisms.test.ts` läuft ohne Fehler; `OutputLayoutEditor.svelte` enthält keinen `ui/`-Import mehr.
- **Side effects:** Die drei Consumer-Dateien importieren `OutputLayoutEditor` fortan über den Organisms-Barrel. Bestehende Funktionalität bleibt unverändert — kein Code-Move, nur Import-Pfade und der eine Tag-Rename (`Card.Root` → `Card`).

## Acceptance Criteria

**AC-1:** Given `OutputLayoutEditor.svelte` in `shared/` / When man die Import-Zeilen der Datei prüft / Then findet sich kein Import aus `$lib/components/ui/` mehr, und `Card` wird ausschließlich aus der Atoms-Schicht bezogen.

**AC-2:** Given `organisms/index.ts` / When man den Barrel-Inhalt prüft / Then exportiert er `OutputLayoutEditor` (zusätzlich zu den drei bisherigen Organisms), und `organisms.test.ts` bestätigt dies per Source-Inspection ohne Fehler.

**AC-3:** Given die drei Consumer-Dateien (`compare/steps/Step4Layout.svelte`, `trip-detail/WeatherMetricsTab.svelte`, `trip-wizard/steps/Step4Layout.svelte`) / When man ihre Import-Zeilen prüft / Then importieren alle `OutputLayoutEditor` ausschließlich aus `$lib/components/organisms` und nicht mehr über einen direkten relativen Pfad.

**AC-4:** Given das gesamte Frontend-Projekt / When `cd frontend && npm run build` ausgeführt wird / Then schlägt kein Build-Schritt fehl und alle bestehenden Tests (inklusive `organisms.test.ts`) melden 0 Fehler.

## Known Limitations

- `CompareMatrix` (`compare/CompareMatrix.svelte`) verletzt ebenfalls AC-2 der Organisms-Schicht (direkter `ui/card`- und `ui/table`-Import) und ist nicht Teil dieses Issues. Sie benötigt ein separates Folge-Issue.
- Der physische Pfad von `OutputLayoutEditor.svelte` verbleibt in `shared/` — der Organisms-Barrel ist die kanonische Importquelle, aber nicht der physische Speicherort.

## Changelog

- 2026-05-31: Initial spec created (Issue #475, OutputLayoutEditor Organisms-Migration)
