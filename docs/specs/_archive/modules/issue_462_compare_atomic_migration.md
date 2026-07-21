---
entity_id: issue_462_compare_atomic_migration
type: module
created: 2026-05-30
updated: 2026-05-30
status: active
version: "1.0"
tags: [compare, atomic-design, migration, refactoring, svelte, epic-368, issue-462]
---

# Issue #462 — Compare-Screen: Atomic-Migration (ui/ → atoms/)

## Approval

- [x] Approved

## Purpose

Die 14 compare/-Komponenten importieren `Btn`, `Eyebrow`, `Pill`, `Input` und `TopoBg` direkt aus ihren jeweiligen `ui/`-Unterordnern, obwohl seit Epic #371 ein kanonischer Atom-Barrel (`$lib/components/atoms`) mit transparenten Bridge-Wrappern für genau diese fünf Komponenten existiert. Diese Migration stellt alle 14 Dateien auf den Atom-Barrel um — rein auf Import-Pfad-Ebene, ohne Markup-, Logik- oder Verhaltensänderungen — und schließt damit den compare/-Zweig von Epic #368 Phase 2 (analog zu `trips/+page.svelte` in #402 und `archiv/+page.svelte` in #388).

> **Schicht-Hinweis:** Alle Änderungen liegen ausschließlich im Frontend-Layer
> (`frontend/src/lib/components/compare/`). Go-API und Python-Backend sind nicht betroffen.

## Source

- **Verzeichnis (geändert):** `frontend/src/lib/components/compare/` (11 Dateien) und `frontend/src/lib/components/compare/steps/` (3 Dateien)
- **Vorbild:** `frontend/src/routes/trips/+page.svelte` (#402) — gleiche Migrations-Methodik, gleiche Scope-Grenze (Komponenten ohne Atom-Pendant bleiben in `ui/`)

**Geänderte Dateien (14):**

| Datei | Migrierte Komponenten |
|-------|----------------------|
| `compare/AutoReportCard.svelte` | `Btn` |
| `compare/AutoReportsOverview.svelte` | `Eyebrow` |
| `compare/CompareWizard.svelte` | `Btn`, `Eyebrow`, `TopoBg` |
| `compare/CreateGroupDialog.svelte` | `Btn` |
| `compare/HourlyMatrix.svelte` | `Pill` |
| `compare/LocationPreviewMap.svelte` | `TopoBg` |
| `compare/LocationsRail.svelte` | `Btn`, `Pill` |
| `compare/NewLocationWizard.svelte` | `Btn`, `Input` |
| `compare/PresetHeader.svelte` | `Btn` |
| `compare/RecommendationBanner.svelte` | `Pill` |
| `compare/SavePresetDialog.svelte` | `Btn` |
| `compare/steps/Step3Idealwerte.svelte` | `Eyebrow` |
| `compare/steps/Step4Layout.svelte` | `Eyebrow` |
| `compare/steps/Step5Versand.svelte` | `Eyebrow` |

**Nicht geänderte Dateien (kein Atom-Pendant vorhanden):**

`CompareList.svelte`, `CompareMatrix.svelte`, `CompareRow.svelte`, `GroupSection.svelte`,
`steps/Step1Vergleich.svelte`, `steps/Step2Orte.svelte`, `AddReportCard.svelte` —
diese Dateien nutzen `Card`-Namespace, `Dialog`, `Table`, `Checkbox`, `GCard`, `Label`,
`Select` oder `EmptyState`, für die kein Atom-/Molecule-Pendant existiert.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `$lib/components/atoms` (Barrel) | Atoms (vorhanden, #371) | Exportiert `Btn`, `Eyebrow`, `Pill`, `Input`, `TopoBg` als Bridge-Wrapper über `ui/` — einzige neue Import-Quelle nach der Migration |
| `frontend/src/lib/contrast-audit.test.ts` | Test-Suite (vorhanden, read-only) | Source-Inspection-Tests; muss nach Migration mit identischer Pass/Fail-Bilanz grün bleiben |
| `frontend/e2e/compare-*.spec.ts` (5 Dateien) | Playwright-E2E-Tests (vorhanden) | Verhaltensprüfungen für den Compare-Bereich; dürfen durch reine Import-Pfad-Änderungen nicht beeinflusst werden |
| `ui/table`, `ui/dialog`, `ui/select`, `ui/g-card`, `ui/empty-state`, `ui/checkbox` | UI-Komponenten (vorhanden) | Bleiben in `ui/` — kein Atom-/Molecule-Pendant; analog zur #402-Scope-Grenze |

## Implementation Details

### 1. Import-Muster: Konsolidierung auf Atom-Barrel

Jede der 14 Dateien erhält einen einzigen konsolidierten Import für alle atom-migrierten
Komponenten statt separater `ui/`-Unterordner-Importe:

```svelte
<!-- Vorher (Beispiel CompareWizard.svelte) -->
import { Btn } from '$lib/components/ui/btn/index.js';
import { Eyebrow } from '$lib/components/ui/eyebrow/index.js';
import { TopoBg } from '$lib/components/ui/topo';

<!-- Nachher -->
import { Btn, Eyebrow, TopoBg } from '$lib/components/atoms';
```

Für Dateien mit nur einer migrierten Komponente:

```svelte
<!-- Vorher (Beispiel AutoReportCard.svelte) -->
import { Btn } from '$lib/components/ui/btn/index.js';

<!-- Nachher -->
import { Btn } from '$lib/components/atoms';
```

### 2. Datei-für-Datei-Änderungen

| Datei | Alte Import-Zeilen | Neue Import-Zeile |
|-------|-------------------|-------------------|
| `AutoReportCard.svelte` | `{Btn}` from `ui/btn/index.js` | `{Btn}` from `$lib/components/atoms` |
| `AutoReportsOverview.svelte` | `{Eyebrow}` from `ui/eyebrow/index.js` | `{Eyebrow}` from `$lib/components/atoms` |
| `CompareWizard.svelte` | `{Btn}` + `{Eyebrow}` + `{TopoBg}` (3 Zeilen) | `{Btn, Eyebrow, TopoBg}` from `$lib/components/atoms` (1 Zeile) |
| `CreateGroupDialog.svelte` | `{Btn}` from `ui/btn/index.js` | `{Btn}` from `$lib/components/atoms` |
| `HourlyMatrix.svelte` | `{Pill}` from `ui/pill/index.js` | `{Pill}` from `$lib/components/atoms` |
| `LocationPreviewMap.svelte` | `{TopoBg}` from `ui/topo` | `{TopoBg}` from `$lib/components/atoms` |
| `LocationsRail.svelte` | `{Btn}` from `ui/btn/index.js` + `{Pill}` from `ui/pill/index.js` | `{Btn, Pill}` from `$lib/components/atoms` |
| `NewLocationWizard.svelte` | `{Btn}` from `ui/btn/index.js` + `{Input}` from `ui/input/index.js` | `{Btn, Input}` from `$lib/components/atoms` |
| `PresetHeader.svelte` | `{Btn}` from `ui/btn/index.js` | `{Btn}` from `$lib/components/atoms` |
| `RecommendationBanner.svelte` | `{Pill}` from `ui/pill/index.js` | `{Pill}` from `$lib/components/atoms` |
| `SavePresetDialog.svelte` | `{Btn}` from `ui/btn/index.js` | `{Btn}` from `$lib/components/atoms` |
| `steps/Step3Idealwerte.svelte` | `{Eyebrow}` from `ui/eyebrow` | `{Eyebrow}` from `$lib/components/atoms` |
| `steps/Step4Layout.svelte` | `{Eyebrow}` from `ui/eyebrow` | `{Eyebrow}` from `$lib/components/atoms` |
| `steps/Step5Versand.svelte` | `{Eyebrow}` from `ui/eyebrow` | `{Eyebrow}` from `$lib/components/atoms` |

In `steps/Step5Versand.svelte` migriert nur `Eyebrow`; `GCard` (aus `ui/g-card`) bleibt
unverändert in `ui/`, da kein Atom-Pendant existiert.

### 3. Regressions-Sentinel (neuer Test)

Analog zu `routes/trips/issue_402.test.ts` und `routes/archiv/issue_388.test.ts`:
Ein Source-Inspection-Test prüft, dass alle 14 Dateien `Btn`/`Eyebrow`/`Pill`/`Input`/`TopoBg`
aus `$lib/components/atoms` importieren — und dass keiner dieser fünf Namen mehr direkt
aus einem `ui/`-Pfad importiert wird. Verhindert Zurückrutschen.

Datei: `frontend/src/lib/components/compare/issue_462.test.ts`

### 4. LoC-Budget

| Änderungstyp | Δ LoC (netto) | Zählt |
|---|---|---|
| 14 × Import-Zeilen-Umbau (1–3 Zeilen pro Datei) | ~30–40 | ja |
| Neuer Sentinel-Test `issue_462.test.ts` | ~25 | ja |
| **Gesamt (zählend)** | **~55–65** | **weit unter 250 LoC-Limit** |

## Expected Behavior

- **Input:** Render aller `/compare`-Routen und des Compare-Wizards mit bestehenden Daten;
  kein Eingriff in API-Calls, Store-Bindings oder Svelte-Logik.
- **Output:** Optisch und funktional identische Ausgabe aller Compare-Komponenten.
  Die Atoms sind transparente Bridge-Wrapper — Prop-API, Events und Slot-Struktur sind
  100 % kompatibel zu den bisherigen `ui/`-Komponenten.
- **Side effects:** Keine. Keine neuen Render-Pfade, keine geänderten CSS-Klassen,
  keine veränderten Prop-Signaturen.

## Acceptance Criteria

- **AC-1:** Given alle 14 Dateien in `compare/` und `compare/steps/` nach der Migration / When die Import-Deklarationen für `Btn`, `Eyebrow`, `Pill`, `Input` und `TopoBg` ausgewertet werden / Then stammen diese fünf Komponenten ausschließlich aus `$lib/components/atoms` und kein einziger dieser Namen erscheint mehr in einem direkten `$lib/components/ui/`-Importpfad innerhalb der 14 migrierten Dateien
  - Test: (populated after /tdd-red)

- **AC-2:** Given die Design-System-Showcase-Route `/_design-system` wird nach der Migration aufgerufen / When die Seite vollständig gerendert hat / Then treten keine JavaScript-Konsolenfehler und keine Svelte-Render-Fehler auf, die auf fehlende Atom-Exporte oder inkompatible Props zurückzuführen sind
  - Test: (populated after /tdd-red)

- **AC-3:** Given die Datei `frontend/src/lib/contrast-audit.test.ts` wird nach der Migration ausgeführt / When das Test-Ergebnis mit dem Ergebnis vor dem PR verglichen wird / Then ist die Anzahl bestandener und fehlgeschlagener Tests identisch — kein neuer Kontrast-Verstoß durch die Import-Migration eingeführt
  - Test: `node --experimental-strip-types --test src/lib/contrast-audit.test.ts`

- **AC-4:** Given alle Playwright-E2E-Tests in `frontend/e2e/compare-*.spec.ts` / When die Test-Suite nach der Migration ausgeführt wird / Then sind Pass/Fail-Ergebnisse identisch zum Stand vor dem PR — keine Regression durch die Import-Pfad-Änderungen
  - Test: (populated after /tdd-red)

## Known Limitations

- **Teil-Migration nach Bibliotheks-Abdeckung:** `Card`-Namespace, `Dialog`, `Table`,
  `Checkbox`, `GCard`, `Label`, `Select` und `EmptyState` haben kein Atom-/Molecule-Pendant
  und bleiben in `ui/` importiert. „Keine direkten `ui/`-Importe mehr in compare/" gilt
  ausschließlich für die fünf Komponenten mit vorhandenem Bridge-Wrapper — identische
  Scope-Grenze wie in #402 (trips) und #388 (archiv).
- **Kein visueller Diff:** Da Atoms transparente Wrapper sind, wird kein Screenshot-Vergleich
  vor/nach benötigt. Die Playwright-E2E-Tests decken Verhaltensregressions ab.

## Out of Scope

- Migration von `Card`/`Dialog`/`Table`/`Checkbox`/`GCard`/`EmptyState`/`Select`/`Label`
  (kein Pendant; eigene Issues wenn Bibliothek erweitert wird)
- Neue Atom- oder Molecule-Komponenten anlegen
- Markup-, Logik- oder CSS-Änderungen an den 14 Dateien
- Änderungen an SSR-Loader, Go-API oder Python-Backend
- Änderungen außerhalb von `frontend/src/lib/components/compare/`

## Changelog

- 2026-05-30: Initial spec erstellt. 14 compare/-Dateien auf `$lib/components/atoms`-Barrel
  umstellen (Btn/Eyebrow/Pill/Input/TopoBg); bewusste Scope-Grenze für Komponenten ohne
  Atom-Pendant (Card-Namespace, Dialog, Table, Checkbox, GCard, EmptyState); Regressions-Sentinel
  analog #402/#388; Epic #368 Phase 2 Compare-Zweig abgeschlossen.
