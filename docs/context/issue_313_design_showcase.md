# Context: Issue #313 — /_design Showcase vervollständigen

## Request Summary
Die `/_design`-Seite zeigt aktuell nur ~30 % der UI-Komponenten. Sie soll alle Komponenten aus `frontend/src/lib/components/ui/` mit allen Varianten und States zeigen, damit visuelle Verifikation ohne App-Navigation möglich ist.

## Betroffene Datei
`frontend/src/routes/_design/+page.svelte` (aktuell 166 Zeilen)

## Aktuell gezeigte Komponenten
- `Btn` — Variants, Sizes, States (kein Loading-State)
- `Pill` — 6 Tones (kein Outlined-Variant)
- `Dot` — 6 Wetter-Tones (fehlen: semantic tones, alle Sizes)
- `GCard` — mit Wetter-Demo
- `TopoBg` — einfacher Demo-Block
- `ElevSparkline` — Normal + Edge-Cases
- Aktivitätsprofile via `profileSignature`

## Noch fehlende Komponenten (UI-Ordner)

| Komponente | Datei | Props/Varianten |
|-----------|-------|-----------------|
| `Badge` | `ui/badge/badge.svelte` | variant: default, secondary, destructive, outline, ghost, link |
| `Checkbox` | `ui/checkbox/Checkbox.svelte` | checked, unchecked, indeterminate (n/a), disabled |
| `Input` | `ui/input/input.svelte` | default, disabled, aria-invalid (error) |
| `Label` | `ui/label/label.svelte` | default, required-Marker |
| `Select` | `ui/select/Select.svelte` | default, disabled |
| `Dialog` | `ui/dialog/*.svelte` | Trigger → Content mit Header/Body/Footer, Danger-Variante |
| `Table` | `ui/table/*.svelte` | Header, Rows, Footer, leerer Zustand |
| `Wordmark` | `ui/wordmark/Wordmark.svelte` | size: sm, md, lg |
| `Segmented` | `ui/segmented/Segmented.svelte` | Option-Toggle |
| `WIcon` | `ui/wicon/WIcon.svelte` | alle 8 kinds (sun/cloud/rain/thunder/snow/wind/moon/flashlight) |
| `Card` (shadcn) | `ui/card/*.svelte` | Card.Root + Header + Content + Description + Footer + Action |
| `AccordionSection` | `components/edit/AccordionSection.svelte` | Closed, Open (liegt in edit/, nicht ui/) |
| `Sidebar` + `TopAppBar` + `BottomNav` | `ui/sidebar/*.svelte` | Vorschau-Box (nicht interaktiv, Props schwer zu mocken) |

## Fehlende States bei bestehenden Komponenten

| Komponente | Fehlender State |
|-----------|----------------|
| `Btn` | Loading-State (kein loading-Prop in Btn.svelte — müsste manuell simuliert werden: disabled + Spinner-Icon) |
| `Pill` | Outlined-Variante (Issue #284 — prüfen ob in app.css vorhanden) |
| `Dot` | Semantic tones (success, warning, danger, info) + alle 3 Sizes (xs, sm, md) |

## Fehlende Muster-Abschnitte (als neue Sections)
- Form-Muster: Feld mit Fehler, Feld mit Erfolg, Formular-Submit
- Zustands-Muster: Ladevorgang (Spinner/Skeleton), Leerer Zustand (EmptyState), Fehler-Zustand

## Technische Details zu den Komponenten

### Badge
- `tailwind-variants` basiert, kein gz-Präfix
- Props: `variant`, `href` (anchor vs span)

### Checkbox  
- gz-Präfix-Styling, kein indeterminate-Prop (nur checked/unchecked/disabled)
- bind:checked = $bindable

### Input
- shadcn-basiert mit bits-ui, `aria-invalid` für Error-State
- kein eigener gz-Stil — verwendet Tailwind-Klassen

### Select
- gz-Präfix-Styling mit custom Chevron SVG
- keine Disabled-State-Klasse nötig, CSS via `.gz-select select:disabled`

### Dialog
- bits-ui basiert, Dialog.Root + Dialog.Trigger + Dialog.Content + Header/Title/Description/Footer/Close
- benötigt $state(open) zum Demo

### Table
- shadcn-basiert: Table.Root > Table.Header > Table.Row > Table.Head / Table.Body > Table.Row > Table.Cell

### Wordmark
- 3 Sizes: sm (14px), md (18px + Subtitle), lg (24px + Subtitle)
- immer als Link (href-Prop), Demo href="/_design"

### Segmented
- options: Array<{value, label}>, selected: string, onselect: callback

### WIcon
- kind: WIconKind, size?: number (default 20), color?: string
- 8 kinds: sun, cloud, rain, thunder, snow, wind, moon, flashlight

### AccordionSection (nicht in ui/, in edit/)
- id, title, open: boolean, onToggle: () => void, children
- benötigt $state(open) für interaktiven Demo

### Sidebar / TopAppBar / BottomNav
- Sidebar benötigt userId, currentPath, darkMode, ontoggleDark, mobileMenuOpen
- TopAppBar benötigt mobileMenuOpen, darkMode, ontoggleDark
- BottomNav: nutzt $app/state (page.url.pathname) — schwer zu isolieren
- Empfehlung: Screenshot/Vorschau-Hinweis statt Live-Demo

## Risiken & Überlegungen

1. **Sidebar/BottomNav**: Benötigt page-Context ($app/state). Im Design-Showcase schwer zu isolieren. Lösung: nur TopAppBar/BottomNav als statische Preview-Box (overflow:hidden, pointer-events:none).
2. **Dialog**: Braucht interaktiven State (open/close). Mit $state() in +page.svelte lösbar.
3. **AccordionSection**: liegt in `edit/`, nicht `ui/` — ist also keine "primitive UI-Komponente", aber laut Issue erwünscht.
4. **Loading-State Btn**: Kein natives loading-Prop. Demo: disabled + Spinner-Icon (z.B. Lucide `loader-2` mit Spin-Animation).
5. **Pill Outlined**: Issue #284 — in app.css prüfen ob `data-slot="pill"][data-outlined]` definiert ist.
6. **Seitenumfang**: Derzeit 166 Zeilen. Mit allen Komponenten wird die Datei erheblich größer (~600-700 Zeilen). Kein Problem für eine Showcase-Seite.

## Verwandte Specs
- `docs/specs/modules/issue_293_wordmark.md` — Wordmark-Spec
- `docs/specs/modules/issue_322_wicon_komponente.md` — WIcon-Spec
- `docs/specs/modules/issue_284_alert_rules_restyle.md` — Pill Outlined-Variant
