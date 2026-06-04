# Context: Issue #582 — Compare-Screen Design-Fidelity

## Request Summary
Compare-Screen (Liste, Hub/Detail, Wizard) 1:1 aus den JSX-Vorlagen neu implementieren — alle Inline-Styles auf `var(--g-*)` Tokens, kein rohes Hex/px, keine eigenen Design-Entscheidungen.

## Quellen (bindend)
| Datei | Zeilen | Inhalt |
|-------|--------|--------|
| `claude-code-handoff/current/jsx/screen-compare-list.jsx` | 95 | Kachel-Übersicht |
| `claude-code-handoff/current/jsx/screen-compare-detail.jsx` | 432 | Hub mit 6 Tabs |
| `claude-code-handoff/current/jsx/screen-compare-wizard.jsx` | 1037 | 5-Step-Wizard (Create + Edit) |
| `claude-code-handoff/current/soll/G-compare-*.png` | 7 Bilder | Optische Referenz |

## Aktuelle Svelte-Dateien (zu ändern)
| Datei | Zeilen | Delta |
|-------|--------|-------|
| `frontend/src/routes/compare/+page.svelte` | 95 | Neufassung nach JSX |
| `frontend/src/routes/compare/[id]/+page.svelte` | 177 | Hub-Layout anpassen |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | 777 | Tab-Buttons + Inhalt nach JSX |
| `frontend/src/lib/components/compare/CompareWizard.svelte` | 336 | CW_EditHeader + Stepper |
| `frontend/src/routes/compare/new/+page.svelte` | 18 | ggf. keine Änderung |

## Wichtigste visuelle Abweichungen (IST → SOLL)

### Compare-Liste
- **Padding:** `p-8 max-w-5xl` → `padding: 32px 40px 60px` (kein max-width container)
- **Eyebrow:** `"WORKSPACE · ORTS-VERGLEICHE"` (Caps) → `"Workspace · Orts-Vergleiche"` (Mixed Case)
- **Stats:** Rohe HTML-Divs → `<Stat>` Molecule mit `tone="accent"` + `mono`
- **Suche:** Nur bei >3 Vergleichen → immer sichtbar
- **Footer:** fehlt → `N von M Vergleichen` (mono, ink-4)
- **Leerzustand:** Einfacher Text → `<Card>` mit zentriertem Text

### Compare-Detail Hub
- **Layout:** `p-8 max-w-5xl mx-auto` → `padding: 22px 40px 0` full-width + `borderBottom: 1px solid var(--g-rule)`
- **Breadcrumb:** `<nav>` + Eyebrow → plain `<a>` Links in mono + `/` Separator
- **Tab-Leiste:** `<Segmented>` Komponente → individuelle `<button>` mit `borderBottom: 2px solid var(--g-accent)` für aktiv
- **Content:** `p-8` → `padding: 28px 40px 80px, maxWidth: 1320`
- **Übersicht-Tab:** CSS-Klassen → Inline-Styles, CHub_SummaryCard Pattern
- **Vorschau-Tab:** fehlt (nur Loading-State) → vollständig (CompareChannelSwitch + CompareBriefingPreview)

### Compare-Wizard
- **Edit-Header:** Eyebrow + H1 zusammen → `CW_EditHeader` (Name fett, Status-Pill, Save/Cancel-Buttons)
- **Stepper:** `<Stepper>` Trip-Wizard-Komponente → eigene `CW_Stepper` Implementierung mit `done/current/upcoming` States
- **Step-Titel:** Immer sichtbar → im Create-Mode über Stepper, im Edit-Mode unter Stepper

## Existing Patterns (Referenz)
- `screen-trips.jsx` → `frontend/src/routes/trips/+page.svelte` (gleiches Design-Fidelity Issue #580)
- Hub-Tabs analog TripTabs: Button mit underline-Indikator (analog `screen-compare-detail.jsx`)
- `Stat` Molecule: `frontend/src/lib/components/molecules/` (bereits vorhanden)

## Abhängigkeiten
- **Voraussetzung:** Issue #578 (Molecules + Organisms) — laut Issue-Body abgeschlossen
- **Parallel:** #579–#581, #583–#588 (andere Screens, unabhängig)
- **Tests:** Bestehende Tests in `compare/__tests__/` + `molecules/issue_489_compare_rows.test.ts` müssen grün bleiben

## Risiken
- `CompareTabs.svelte` (777 Zeilen) ist komplex — vorsichtiges Tab-für-Tab Vorgehen
- LoC-Limit 250 wird überschritten → Override auf 500 oder höher nötig
- Vorschau-Tab hat Svelte-Logik (`previewHtml`, `previewLoading`) — die bleibt, nur Styling ändert sich
- Mobile-Layout in `[id]/+page.svelte` (L99–177) bleibt unverändert (kein mobiler SOLL-Screenshot)
