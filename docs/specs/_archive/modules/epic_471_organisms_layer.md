---
entity_id: epic_471_organisms_layer
type: module
created: 2026-05-31
updated: 2026-05-31
status: implemented
version: "1.0"
tags: [frontend, atomic-design, organisms, epic-471, issue-471]
---

<!-- Issue #471 — EPIC · Organisms-Schicht — Atomic Design Ebene 3 aufbauen -->

# Epic #471 — Organisms-Schicht `lib/components/organisms/`

## Approval

- [x] Approved

## Zweck

`frontend/src/lib/components/organisms/` ist Ebene 3 des Atomic-Design-Stacks und fasst komplexe Zusammenbauten aus Atoms und Molecules unter einem kanonischen Barrel zusammen. Der Barrel-Ansatz (Re-Exporte ohne physischen Move der `.svelte`-Dateien) stellt sicher, dass bestehende interne Imports nicht brechen und die Organisms dennoch über einen einheitlichen Pfad (`$lib/components/organisms`) erreichbar sind. Durch die explizite Schicht-Trennung wird verhindert, dass screen-nahe Komponenten direkt auf `$lib/components/ui/`-Primitive zugreifen, was die Austauschbarkeit und Testbarkeit der Bausteine langfristig sichert.

## Quelle / Source

**Neue Dateien:**
- `frontend/src/lib/components/organisms/index.ts` (Barrel-Re-Export für alle 3 Organisms)
- `frontend/src/lib/components/organisms/organisms.test.ts` (Source-Inspection, node:test, keine Mocks)

**Re-exportierte Organisms (physischer Pfad unverändert):**
- `frontend/src/lib/components/trip-detail/TripHeader.svelte`
- `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte`
- `frontend/src/lib/components/alert-rules-editor/AlertRulesEditor.svelte`
- `frontend/src/lib/components/shared/OutputLayoutEditor.svelte` (Issue #475)

**Geänderte Dateien (Konsumenten-Imports + Barrel-Bereinigung):**
- `frontend/src/routes/trips/[id]/+page.svelte` (TripHeader-Import auf organisms/)
- `frontend/src/routes/trips/new/+page.svelte` (TripWizardShell-Import auf organisms/)
- `frontend/src/lib/components/edit/TripEditView.svelte` (AlertRulesEditor-Import auf organisms/)
- `frontend/src/lib/components/trip-wizard/steps/Step4Briefings.svelte` (AlertRulesEditor-Import auf organisms/)
- `frontend/src/lib/components/trip-detail/index.ts` (TripHeader-Export entfernen)
- `frontend/src/lib/components/compare/steps/Step4Layout.svelte` (OutputLayoutEditor-Import auf organisms/, Issue #475)
- `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` (OutputLayoutEditor-Import auf organisms/, Issue #475)
- `frontend/src/lib/components/trip-wizard/steps/Step4Layout.svelte` (OutputLayoutEditor-Import auf organisms/, Issue #475)

> **Schicht-Hinweis:** Reine Frontend-Änderung (SvelteKit `frontend/src/lib/components/`). Keine Go/Python-Schicht betroffen.

## Estimated Scope

- **LoC:** ~78 netto
- **Files:** 7
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/atoms/` (#371) | Atom-Schicht | Basis-Bausteine, die TripHeader/TripWizardShell/AlertRulesEditor nutzen |
| `frontend/src/lib/components/molecules/` (#372) | Molecule-Schicht | TripHeader nutzt Stat-Molecule |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | Organism-Quelle | Physische Quelle, wird per Re-Export in Barrel aufgenommen |
| `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` | Organism-Quelle | Physische Quelle, wird per Re-Export in Barrel aufgenommen |
| `frontend/src/lib/components/alert-rules-editor/AlertRulesEditor.svelte` | Organism-Quelle | Physische Quelle, wird per Re-Export in Barrel aufgenommen |
| `frontend/src/lib/components/trip-detail/index.ts` | Barrel (zu bereinigen) | TripHeader-Export muss entfernt werden, um doppelte Quelle zu vermeiden |
| `frontend/src/lib/contrast-audit.test.ts` (#377) | Kontrast-Schutznetz | WCAG-AA-Text-Kontrast — greift beim Build/Rebase |

## Implementation Details

### Schritt 1: `organisms/index.ts` anlegen

```typescript
// frontend/src/lib/components/organisms/index.ts
export { default as TripHeader } from '../trip-detail/TripHeader.svelte';
export { default as TripWizardShell } from '../trip-wizard/TripWizardShell.svelte';
export { default as AlertRulesEditor } from '../alert-rules-editor/AlertRulesEditor.svelte';
```

Kein physischer Move der `.svelte`-Dateien — die Dateien verbleiben in ihren Ursprungsordnern. Der Barrel ist die einzige neue Datei, die den Pfad `$lib/components/organisms` kanonisiert.

### Schritt 2: `organisms.test.ts` anlegen (Source-Inspection, node:test)

Die Test-Datei prüft per statischer Quellcode-Inspektion (Regex auf Import-Zeilen), dass keiner der 3 Organisms direkt `$lib/components/ui/` importiert. Analog zu `atoms.test.ts`. Struktur:

```typescript
// frontend/src/lib/components/organisms/organisms.test.ts
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));

const organisms = [
  { name: 'TripHeader', path: '../trip-detail/TripHeader.svelte' },
  { name: 'TripWizardShell', path: '../trip-wizard/TripWizardShell.svelte' },
  { name: 'AlertRulesEditor', path: '../alert-rules-editor/AlertRulesEditor.svelte' },
];

describe('organisms — AC-1: alle 3 im Barrel', () => {
  it('index.ts re-exportiert alle 3', () => {
    const barrel = readFileSync(join(__dirname, 'index.ts'), 'utf-8');
    for (const o of organisms) {
      assert.ok(barrel.includes(o.name), `${o.name} fehlt im Barrel`);
    }
  });
});

describe('organisms — AC-2: kein direkter ui/-Import', () => {
  for (const o of organisms) {
    it(`${o.name} importiert kein $lib/components/ui/`, () => {
      const src = readFileSync(join(__dirname, o.path), 'utf-8');
      assert.ok(
        !src.includes('$lib/components/ui/'),
        `${o.name} hat verbotenen ui/-Import`
      );
    });
  }
});
```

### Schritt 3: Konsumenten-Imports aktualisieren (4 Dateien)

| Datei | Alte Import-Quelle | Neue Import-Quelle |
|-------|-------------------|-------------------|
| `frontend/src/routes/trips/[id]/+page.svelte` | `$lib/components/trip-detail` (TripHeader) | `$lib/components/organisms` — TripTabs bleibt auf trip-detail |
| `frontend/src/routes/trips/new/+page.svelte` | direkter Pfad `../lib/components/trip-wizard/TripWizardShell.svelte` | `$lib/components/organisms` |
| `frontend/src/lib/components/edit/TripEditView.svelte` | direkter Pfad `../alert-rules-editor/AlertRulesEditor.svelte` | `$lib/components/organisms` |
| `frontend/src/lib/components/trip-wizard/steps/Step4Briefings.svelte` | direkter Pfad `../../TripWizardShell.svelte` | `$lib/components/organisms` |

Für +page.svelte (trips/[id]): Der Zeile-7-Import wird aufgesplittet — TripHeader kommt aus organisms, TripTabs weiterhin aus trip-detail.

### Schritt 4: `trip-detail/index.ts` bereinigen

TripHeader-Export-Zeile aus `frontend/src/lib/components/trip-detail/index.ts` entfernen. Alle anderen Exports (TripTabs etc.) bleiben unverändert.

### Schritt 5: Build-Verifikation

```bash
cd frontend && npm run build
```

Muss ohne Fehler durchlaufen. Anschließend organisms.test.ts via `node --test` ausführen.

### Nicht in diesem Epic (explizite Ausschlüsse)

- **CompareMatrix** (`compare/CompareMatrix.svelte`): importiert `$lib/components/ui/card` und `$lib/components/ui/table` → verletzt AC-2. Bleibt in `compare/`.

## Expected Behavior

- **Input:** keiner zur Laufzeit (reine Komponenten und Barrel-Datei).
- **Output:** `import { TripHeader, TripWizardShell, AlertRulesEditor, OutputLayoutEditor } from '$lib/components/organisms'` liefert alle 4 Organisms; `npm run build` ist grün; organisms.test.ts läuft ohne Fehler.
- **Side effects:** TripHeader ist nach Abschluss nicht mehr über `$lib/components/trip-detail` erreichbar (trip-detail barrel bereinigt). OutputLayoutEditor wird aus `$lib/components/organisms` importiert (physischer Pfad bleibt `shared/`). Bestehende Funktionalität der 4 Organisms bleibt unverändert (kein Code-Move, nur Import-Kanonisierung).

## Acceptance Criteria

**AC-1:** Given das Verzeichnis `frontend/src/lib/components/organisms/` / When man es auflistet / Then existieren `index.ts` und `organisms.test.ts`, und der Barrel re-exportiert exakt TripHeader, TripWizardShell und AlertRulesEditor.
  - Test: (populated after /tdd-red)

**AC-2:** Given die Quellcode-Dateien der 3 Organisms / When `organisms.test.ts` via Source-Inspection läuft / Then findet keine der 3 Dateien einen direkten `$lib/components/ui/`-Import — nur atoms/, molecules/ oder andere organisms/ sind erlaubt.
  - Test: (populated after /tdd-red)

**AC-3:** Given das Frontend-Projekt / When `cd frontend && npm run build` ausgeführt wird und alle bestehenden Tests laufen / Then schlägt kein Build-Schritt fehl und organisms.test.ts meldet 0 Fehler.
  - Test: (populated after /tdd-red)

**AC-4:** Given die 4 Konsumenten-Dateien (`+page.svelte` trips/[id], `+page.svelte` trips/new, `TripEditView.svelte`, `Step4Briefings.svelte`) / When man ihre Import-Zeilen prüft / Then importieren alle TripHeader/TripWizardShell/AlertRulesEditor ausschließlich aus `$lib/components/organisms`.
  - Test: (populated after /tdd-red)

**AC-5:** Given `frontend/src/lib/components/trip-detail/index.ts` / When man den Barrel-Inhalt prüft / Then ist TripHeader dort nicht mehr exportiert; alle anderen trip-detail-Exporte sind unverändert vorhanden.
  - Test: (populated after /tdd-red)

## Known Limitations

- OutputLayoutEditor und CompareMatrix erfüllen AC-2 derzeit nicht (direkter `ui/`-Import). Sie sind bewusst ausgeschlossen und benötigen ein eigenes Folge-Issue für die ui/-Abhängigkeitsauflösung, bevor sie in die Organisms-Schicht aufgenommen werden können.
- Der physische Pfad der `.svelte`-Dateien bleibt in den jeweiligen Feature-Ordnern — das ist gewollt (Barrel-Pattern), bedeutet aber, dass `organisms/` kein vollständig eigenständiger Ordner mit allen Quellen ist.

## Changelog

- 2026-05-31: OutputLayoutEditor hinzugefügt (Issue #475, ui/card-Abhängigkeit aufgelöst, 4. Organism)
- 2026-05-31: Initial spec created (Epic #471, Organisms-Schicht Atomic Design Ebene 3)
