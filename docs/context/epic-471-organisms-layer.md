# Context: Epic #471 — Organisms-Schicht aufbauen

## Request Summary
Atomic Design Ebene 3 (Organisms) einführen: `frontend/src/lib/components/organisms/` anlegen, passende Kandidaten dorthin verschieben, Imports aktualisieren.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | Kandidat A — 261 Zeilen, nutzt Atoms + Stat-Molecule |
| `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` | Kandidat B — 189 Zeilen, Wizard-Rahmen mit 5 Steps |
| `frontend/src/lib/components/compare/CompareMatrix.svelte` | Kandidat C — 191 Zeilen, importiert ui/ direkt (kein Atom) |
| `frontend/src/lib/components/alert-rules-editor/AlertRulesEditor.svelte` | Kandidat D — 99 Zeilen, grenzwertig klein |
| `frontend/src/lib/components/shared/OutputLayoutEditor.svelte` | Kandidat E — 337 Zeilen, 3 Konsumenten, importiert ui/ |
| `frontend/src/lib/components/atoms/index.ts` | Pattern-Referenz (Barrel-Export) |
| `frontend/src/lib/components/molecules/index.ts` | Pattern-Referenz (Barrel-Export) |
| `frontend/src/routes/trips/[id]/+page.svelte` | Konsument TripHeader |
| `frontend/src/routes/trips/new/+page.svelte` | Konsument TripWizardShell |
| `frontend/src/routes/compare/+page.svelte` | Konsument CompareMatrix |
| `frontend/src/lib/components/edit/TripEditView.svelte` | Konsument AlertRulesEditor |
| `frontend/src/lib/components/trip-wizard/steps/Step4Briefings.svelte` | Konsument AlertRulesEditor |
| `frontend/src/lib/components/compare/steps/Step4Layout.svelte` | Konsument OutputLayoutEditor |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Konsument OutputLayoutEditor |
| `frontend/src/lib/components/trip-wizard/steps/Step4Layout.svelte` | Konsument OutputLayoutEditor |

## Kandidaten-Analyse

| Kandidat | Zeilen | Atom-Importe | Molecule-Importe | ui/-Importe | Konsumenten | Urteil |
|----------|--------|-------------|-----------------|------------|------------|--------|
| TripHeader | 261 | Btn, Eyebrow | Stat | — | 1 | **ORGANISM** |
| TripWizardShell | 189 | Btn, Eyebrow, TopoBg | — | — | 1 | **ORGANISM** |
| CompareMatrix | 191 | — | — | Card, Table | 1+Test | **BORDERLINE** — verletzt AC-2 |
| AlertRulesEditor | 99 | Btn | — | — | 2 | **BORDERLINE** — sehr klein |
| OutputLayoutEditor | 337 | Btn, Eyebrow | — | Card | 3 | **ORGANISM** — größter, 3 Nutzer, AC-2-Problem |

## Kritischer Befund: AC-2-Problem

AC-2 verlangt: *Jeder Organism importiert nur aus atoms/, molecules/ oder organisms/ — nie direkt aus ui/.*

- **CompareMatrix** importiert: `$lib/components/ui/card/index.js`, `$lib/components/ui/table/index.js`
- **OutputLayoutEditor** importiert: `$lib/components/ui/card/index.js`

Zwei Optionen:
1. **AC-2 anpassen:** `ui/` erlauben (Pragmatismus — ui/ sind shadcn-Basis-Primitives, kein echtes Atomic-Design-Problem)
2. **Strikte Einhaltung:** CompareMatrix + OutputLayoutEditor erst ui/-Importe durch Atoms/Molecules ersetzen, dann verschieben (Mehraufwand ~+1 Issue)

**Empfehlung:** Option 1 (AC-2 präzisieren: `ui/` ist erlaubte Low-Level-Library, zählt nicht als Verstoß). Begründung: shadcn/ui ist die Basis-Komponentensammlung (wie HTML-Elemente), nicht ein Atomic-Design-Layer. Atoms/Molecules wrapppen ui/ — Organisms dürfen ui/ direkt nutzen solange sie keine Features-Module (trip-detail/, trip-wizard/etc.) importieren.

## Organisms-Empfehlung (Mindestens 3 für AC-1)

| Priorisierung | Komponente | Begründung |
|---|---|---|
| 1 (sicher) | TripHeader | Nutzt Atoms + Stat, vollständiger Seitenblock |
| 2 (sicher) | TripWizardShell | Orchestriert kompletten Wizard-Rahmen |
| 3 (sicher) | OutputLayoutEditor | 337 Zeilen, 3 Konsumenten, Trip-agnostisch = ideal für Wiederverwendung |
| 4 (optional) | AlertRulesEditor | Klein, aber 2 Konsumenten, klarer Wiederverwendungsfall |
| 5 (optional) | CompareMatrix | Einzelner Konsument, ui/-abhängig |

## Existierende Patterns

- `atoms/index.ts` — Barrel-Export aller Atome
- `molecules/index.ts` — Barrel-Export aller Molecules
- Organisms-Verzeichnis existiert NICHT — muss neu angelegt werden

## Dependencies

- **Upstream (was Organisms nutzen):** atoms/, molecules/, ui/ (shadcn), types, utils
- **Downstream (was Organisms konsumiert):** routes/*, lib/components/trip-detail/*, lib/components/trip-wizard/*, lib/components/compare/*, lib/components/edit/*

## Risiken & Überlegungen

1. **Import-Pfade in Konsumenten:** Alle Stellen, die die Komponenten bisher importieren, müssen auf `$lib/components/organisms/` umgestellt werden
2. **AC-2 — ui/ erlauben:** Spec muss klar definieren, ob ui/ als Low-Level-Primitive zählt oder nicht
3. **OutputLayoutEditor hat Abhängigkeit auf `trip-detail/`-Hilfsdateien** (BucketSection, metricsEditor etc.) — diese müssen entweder mitgezogen oder als "interne Helfer" im Feature-Ordner belassen werden. OutputLayoutEditor wird trotzdem Organism, weil er `shared/` war.
4. **Keine Tests zu verschieben** — Komponenten-Tests bleiben in ihren Feature-Ordnern (z.B. `compare/__tests__/`)

## Offene Spec-Frage für Phase 2

Welche genau 3+ Organisms sind definitiv drin? Empfehlung: TripHeader + TripWizardShell + OutputLayoutEditor + AlertRulesEditor (4 Stück, CompareMatrix optional als 5.)
