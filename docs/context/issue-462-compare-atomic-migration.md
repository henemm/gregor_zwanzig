# Context: Issue #462 — Atomic-Design Compare-Screen Migration (Phase 2)

## Request Summary

Alle Compare-Komponenten in `frontend/src/lib/components/compare/` sollen direkte `ui/`-Imports,
wo Atom-Äquivalente existieren, auf `atoms/` bzw. `molecules/` umstellen.
Das Ergebnis: einheitliche Nutzung der Atomic-Hierarchie, keine doppelten Imports-Pfade.

## Betroffene Dateien (21 Komponenten)

| Datei | ui/-Imports migrierbar | Verbleiben in ui/ |
|-------|------------------------|-------------------|
| `AutoReportCard.svelte` | `Btn` → atoms, `Card` (namespace) | `* as Card` |
| `AutoReportsOverview.svelte` | `Eyebrow` → atoms | — |
| `CompareList.svelte` | — | `* as Table`, `* as Dialog`, `EmptyState` |
| `CompareMatrix.svelte` | — | `* as Card`, `* as Table` |
| `CompareRow.svelte` | — | `* as Table`, `* as Dialog` |
| `CompareWizard.svelte` | `Btn`, `Eyebrow`, `TopoBg` → atoms | — |
| `CreateGroupDialog.svelte` | `Btn` → atoms | `* as Dialog`, `Select` |
| `GroupSection.svelte` | — | `Checkbox` |
| `HourlyMatrix.svelte` | `Pill` → atoms | `* as Card`, `* as Table` |
| `LocationPreviewMap.svelte` | `TopoBg` → atoms | — |
| `LocationsRail.svelte` | `Btn`, `Pill` → atoms | `Checkbox`, `EmptyState` |
| `NewLocationWizard.svelte` | `Btn`, `Input` → atoms | `Label`, `Select` |
| `PresetHeader.svelte` | `Btn` → atoms (Card schon molecules/Field drin) | `* as Card`, `Select` |
| `RecommendationBanner.svelte` | `Pill` → atoms | `* as Card` |
| `SavePresetDialog.svelte` | `Btn` → atoms | `* as Dialog`, `Select` |
| `steps/Step3Idealwerte.svelte` | `Eyebrow` → atoms | — |
| `steps/Step4Layout.svelte` | `Eyebrow` → atoms | — |
| `steps/Step5Versand.svelte` | `Eyebrow` → atoms | `GCard` |
| `AddReportCard.svelte` | (keine ui/-Importe) | — |
| `CompareList.svelte` | — | komplex |
| `steps/Step1/Step2` | (keine ui/-Importe) | — |

## Migrationsstatistik

- **23 Import-Zeilen** können auf atoms/molecules umgestellt werden
- **17 Import-Zeilen** bleiben in ui/ (Dialog, Table, Checkbox, Select, EmptyState, GCard, Label — keine Atom-Äquivalente)

## Atom-Äquivalente verfügbar

| ui/-Pfad | atoms-Äquivalent |
|----------|-----------------|
| `ui/btn` | `atoms/Btn` |
| `ui/eyebrow` | `atoms/Eyebrow` |
| `ui/pill` | `atoms/Pill` |
| `ui/input` | `atoms/Input` |
| `ui/topo` | `atoms/TopoBg` |

**KEIN Atom-Äquivalent (bleiben in ui/):**
- `ui/card` (Namespace Card.Root/Header/Content) ≠ atoms/Card (eigenständige div-Komponente, andere API)
- `ui/dialog`
- `ui/table`
- `ui/checkbox`
- `ui/label`
- `ui/select`
- `ui/empty-state`
- `ui/g-card`

## Wichtige Erkenntnisse

### atoms/Card vs. ui/card Namespace
Die `* as Card` (mit `Card.Root`, `Card.Header`, `Card.Content`, `Card.Title`) ist shadcn/ui-Namespace-Pattern.
`atoms/Card` ist eine eigenständige einfache div-Komponente mit anderer API (kein Namespace, kein Root/Header/Content).
→ Migration von `* as Card` würde komplette Markup-Umstrukturierung erfordern.
→ **Scope-Entscheidung nötig** (siehe Analyse-Phase): Out of Scope wie bei trips/+page.svelte.

### Referenz-Migration (trips/+page.svelte — BEREITS migriert)
- Nutzt `{ Btn, Input, Dot, Eyebrow, Pill }` aus atoms ✅
- Nutzt `* as Table`, `* as Dialog`, `{Checkbox}`, `{Select}`, `{EmptyState}` weiterhin aus ui/ ✅
→ Pattern: Atoms-Äquivalente migrieren, Rest in ui/ lassen.

### Vorläufer Issue #390 (CLOSED)
- Schmaler Scope: 3 Inline-Helfer → Pill/Field
- Ergebnis: PresetHeader hat bereits `Field` aus molecules
- Issue #462 ist die breite Migration ALLER verbleibenden ui/-Importe mit Atom-Pendant

## Existierende Specs

- `docs/specs/modules/issue_390_compare_atomic_migration.md` — Vorläufer (eng scoped, closed)
- `docs/design-system/COMPONENTS.md` — Atomic Component Reference

## Abhängigkeiten

- **Upstream:** atoms/index.ts (Btn, Eyebrow, Pill, Input, TopoBg), molecules/index.ts (Field)
- **Downstream:** `/compare`-Route nutzt alle diese Komponenten
- **Tests:** `contrast-audit.test.ts` (muss grün bleiben), atoms.test.ts, molecules.test.ts

## Risiken & Überlegungen

1. **AC-1 Interpretation:** "Keine direkte ui/-Verwendung" ist mit Dialog/Table/Select nicht erfüllbar ohne neue Atoms. Scope-Klarstellung in Spec nötig.
2. *** as Card Namespace:** Bleibt in ui/ (keine API-Kompatibilität mit atoms/Card).
3. **Visuell keine Abweichung (AC-4):** Da Atoms meist Wrapper auf ui/ sind (Bridge-Pattern), ist visueller Output identisch → kein Regressionsrisiko.
4. **LoC-Budget:** 23 Import-Zeilen × ~1 LoC-Änderung = ca. 30-40 LoC Netto-Delta, weit unter 250.
