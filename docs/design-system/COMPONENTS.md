# COMPONENTS · Komponenten-Katalog

> Single Source of Truth für Komponenten-Namen, Props, Verwendung.
>
> **Vertrag:** Komponenten-Name im Mockup (`Soll-Mockups.html`-Frames) = Name im Code (Svelte) = Name in diesem Katalog. Wenn die drei nicht übereinstimmen, ist eines davon falsch.

## Lese-Reihenfolge

Die Datei ist in 7 Schichten gegliedert, von Token → Atom → Molekül → Page-Chrome → Mobile-Shell:

1. **Brand** — Wordmark, Sidebar, User-Badge
2. **Page-Chrome** — Seiten-Skelett (Header, Section, Tile-Grid, Empty)
3. **Atoms** — Btn, Eyebrow, Pill, Dot, KV, Card, Sparkline
4. **Forms** — Input, Field, Checkbox, Select, Switch, Segmented
5. **Feedback** — Toast, Dialog
6. **Overlay** — DropdownMenu, Sheet, Tooltip
7. **Mobile-Shell** — PhoneFrame, TopAppBar, BottomNav, Drawer, MInput, MBtn

## Tabellen-Konvention

| Komponente | Props (Pflicht **bold**) | Was sie tut |
|---|---|---|

Slots werden in der "Was sie tut"-Spalte erwähnt.

---

## 1 · Brand

| Komponente | Props | Was sie tut |
|---|---|---|
| `<BrandWordmark>` | `size: "sm" \| "md" \| "lg"` (default `md`), `dark: boolean`, `caption: string \| null` | Logo-Typografie. Quelle der Wahrheit für die `gregor.zwanzig`-Wordmark. **Niemand baut das neu.** |
| `<BrandUserBadge>` | `name: string`, `sub: string \| null`, `initials: string \| null`, `accent: boolean` | Avatar + Name unten in Sidebar. |
| `<BrandSidebar>` | `active: "home" \| "trips" \| "compare" \| "archive"`, `counts: Record<string, number>`, `user: BadgeProps`, `onNavigate(id)` | Die einzige Sidebar. 4 Nav-Items fix. |
| `<BrandShell>` | `active`, `counts`, `user`, `onNavigate` + Slot | Wrapper: Sidebar + `<main>` als Flex-Container. |

**Keine Varianten.** Variation passiert über Props, nicht durch Fork.

---

## 2 · Page-Chrome (NEU in Runde 1)

| Komponente | Props | Was sie tut |
|---|---|---|
| `<PageHeader>` | `eyebrow: string`, `title: string`, `sub: string \| null`, Slot `right` | **Der einzige** Page-Header. Eyebrow (Mono-Caps) + Title (Sans-Display) + optional Sub + Right-Slot für Primäraktion / Dropdown. |
| `<PageSection>` | `eyebrow: string`, `title: string`, `sub: string \| null`, Slot `right`, Slot default | Sub-Sektion innerhalb einer Seite. |
| `<PageTileGrid>` | `columns: 1 \| 2 \| 3` (default `3`), Slot default | CSS-Grid mit responsivem 1/2/3-Spalten-Verhalten. |
| `<Tile>` | `type: "trip" \| "compare" \| "archive" \| "template" \| "empty"`, `status: "active" \| "planned" \| "done" \| "paused" \| "error"`, `name: string`, `when: string`, `meta: string`, `href: string` | Kanonische Listen-Kachel. Klick auf gesamte Kachel = Navigation. |
| `<PageEmpty>` | `kind: "trips" \| "compares" \| "archive" \| "channels" \| "templates"`, optional `cta: { label: string, href: string }` | Empty-State. Copy aus `COPY.md §7`. |

---

## 3 · Atoms

| Komponente | Props | Was sie tut |
|---|---|---|
| `<Btn>` | `variant: "primary" \| "accent" \| "ghost" \| "quiet"`, `size: "xs" \| "sm" \| "md" \| "lg"`, `icon: ReactNode`, `onClick` | Der einzige Button. |
| `<Eyebrow>` | `color: string` (default `--g-ink-muted`) + Children | Mono-Caps-Label oberhalb von Titles. Default-Farbe via app.css-Regel `[data-slot="eyebrow"]`: `--g-ink-muted` (~6,91:1, WCAG-AA) — durchgesetzt vom Kontrast-Audit seit #377. (Frühere Katalog-Angabe `--g-ink-3` war eine Token-Namens-Divergenz; Code-Name gewinnt, siehe CLAUDE.md.) |
| `<Pill>` | `tone: "neutral" \| "accent" \| "good" \| "warn" \| "bad" \| "ghost"` | Status-Pill. |
| `<Dot>` | `tone: "good" \| "warn" \| "bad" \| "info" \| "neutral"`, `size: number` (default `8`) | Status-Indikator. |
| `<KV>` | `label: string`, `value: ReactNode`, `mono: boolean` (default `true`) | Key-Value-Zeile mit gestrichelter Trennlinie. |
| `<Card>` | `padding: number` (default `20`), `accent: boolean` + Children | Generischer Card-Container. |
| `<ElevSparkline>` | `data: number[]`, `width`, `height`, `stroke`, `fill`, `showArea` | Mini-Höhenprofil. |
| `<WIcon>` | `kind: "sun" \| "cloud" \| "rain" \| "thunder" \| "snow" \| "wind" \| "moon" \| "headlamp"`, `size`, `color` | Wetter-Line-Icon. |

---

## 4 · Forms

| Komponente | Props | Was sie tut |
|---|---|---|
| `<Field>` | `label: string`, `hint: string`, `error: string`, Slot `side` (Helper-Link) | Form-Field-Wrapper mit Label-Bar + Input + Hint/Error. |
| `<Input>` | `type`, `placeholder`, `value`, `error: boolean`, `mono: boolean`, `onChange` | Text-Input. **Ersetzt** native `<input>`. |
| `<Checkbox>` | `checked`, `label`, `onChange`, `disabled` | Brand-Checkbox. **Ersetzt** native checkbox. |
| `<Select>` | `value`, `options: Array<{id, label}>`, `placeholder`, `onChange` | Brand-Select. **Ersetzt** native `<select>`. |
| `<Switch>` | `checked`, `onChange`, `disabled`, `size: "sm" \| "md"` (default `md`) | On/Off Toggle. 44×24 default, 32×18 für `sm`. |
| `<SwitchRow>` | `label`, `sub`, `checked`, `onChange` | Switch als volle Zeile mit Label + Sub-Text. |
| `<Segmented>` | `items: Array<{id, label, badge?}>`, `value`, `onChange`, `size: "sm" \| "md"` | 2–3-Way-Toggle. |

---

## 5 · Feedback

| Komponente | Props | Was sie tut |
|---|---|---|
| `<Toast>` | `tone: "success" \| "error" \| "info"`, `msg: string`, `hint: string`, `action: string`, `onAction`, `duration: number` (default 4000) | Snackbar-Notification. Auto-Dismiss. Position fix: Desktop Bottom-Right, Mobile Bottom über Nav. |
| `<Dialog>` | `open`, `title`, `sub`, `onClose`, Slot default, Slot `footer` | Modal-Dialog für mehrstufige / destruktive Aktionen. |

---

## 6 · Overlay

| Komponente | Props | Was sie tut |
|---|---|---|
| `<DropdownMenu>` | `align: "start" \| "end"` (default `end`), Slot `trigger`, Slot default | Popover-Menü. Outside-Click + Esc schließen. |
| `<DropdownItem>` | `icon: string`, `danger: boolean`, `disabled: boolean`, `shortcut: string`, `onClick` | Menü-Eintrag. |
| `<DropdownDivider>` | — | Horizontale Trennlinie. |
| `<Sheet>` | `open`, `onClose`, `snap: "peek" \| "half" \| "full"`, `title`, `eyebrow`, Slot default, Slot `footer` | Bottom-Sheet (Mobile). Backdrop + Handle + Drag-to-Close. |
| `<Tooltip>` | `content: string`, `side: "top" \| "right" \| "bottom" \| "left"` + Slot trigger | Sparsam verwenden — bevorzugt visible Helper-Text. |

---

## 7 · Mobile-Shell

| Komponente | Props | Was sie tut |
|---|---|---|
| `<PhoneFrame>` | `width: number` (default 375), `height: number`, `theme: "light" \| "dark"`, `time: string` + Children | Statisches Mobile-Bezel im Design-Canvas. **Nicht** im Produktiv-Code. |
| `<MobileShell>` | `active`, `title`, `eyebrow`, `leftIcon`, `right`, Children, Footer, `drawerOpen`, `sheet`, `toast`, `onMenu` | Mobile Page-Wrapper: TopBar + Content + BottomNav. |
| `<TopAppBar>` | `title`, `eyebrow`, `onMenu`, `leftIcon: "menu" \| "back" \| "close"`, `right`, `scrolled` | Mobile-Top-Bar. Height 56. |
| `<BottomNav>` | `active`, `onChange` | Mobile Bottom-Nav. Height 64. Fix 4 Items. |
| `<Drawer>` | `open`, `onClose` | Hamburger-Drawer. Konto + Logout. |
| `<MInput>` | `type`, `placeholder`, `value`, `leftIcon`, `onChange` | Mobile-Input mit Min-Height 48, Body 16 px. |
| `<MField>` | `label`, `sub`, Children | Field-Wrapper Mobile. |
| `<MBtn>` | `variant`, `size: "md" \| "lg" \| "xl"`, `block`, `icon`, `onClick` | Mobile-Button mit Min-Height 48 (lg). |
| `<MTab>` | `items`, `active`, `onChange`, `scrollable: boolean` | Tab-Bar Mobile (scrollbar wenn nötig). |
| `<ScreenScroll>` | `padding`, `bg`, Children | Scrollbarer Mobile-Content-Bereich zwischen TopBar und BottomNav. |

---

## 8 · Domain-Komponenten (App-spezifisch)

Diese sind nicht Foundation, aber kanonisch:

| Komponente | Verwendung |
|---|---|
| `<WxHourlyTable>` | Stündliche Wetter-Tabelle (Wetter-Drill-Down). |
| `<WxThresholds>` | 5er-Grid mit Schwellwert-Cards. |
| `<WxDrillDownPanel>` | Slide-Panel (Desktop) / Bottom-Sheet (Mobile) für Wetter aus Trip-Detail / Compare. |
| `<TripStageCard>` | Etappen-Zeile in Trip-Detail. |
| `<MapEditor>` | Karten-Editor für Wegpunkte. Keine Lat/Lon-Inputs. |
| `<CompareMatrix>` | Kachel-Grid mit Score, Metrics, Winner-Highlight. |
| `<CompareLocationsRail>` | Linke 280-px-Sidebar mit Gruppen + Orten. |
| `<CompareRecBanner>` | Empfehlungs-Banner über der Matrix. |
| `<HourlyMatrix>` | 4 Orte × N Stunden, ausklappbar. |
| `<ChannelCard>` | Benachrichtigungs-Kanal mit Icon, Status, Test-Button. |
| `<WizardStepper>` | 4-Punkte-Stepper am Top des Wizards. |

---

## 9 · Verbotene Patterns (Cross-Reference)

Siehe `ANTI-PATTERNS.md`:

- AP-006: Keine lokalen Implementierungen der oben gelisteten Komponenten.
- AP-011: Page-Header **nur** via `<PageHeader>`.

---

## 10 · Erweiterungs-Prozess

Neue Komponente braucht:

1. Eintrag in dieser Datei (Name, Props, Was-sie-tut).
2. Implementierung in `soll-mockups/page-chrome.jsx` oder Mobile-Shell.
3. Verwendung in mindestens einem Mockup-Frame als Proof.
4. Wenn Svelte: Komponente unter `frontend/src/lib/components/<group>/<Name>.svelte`.

**Erfinden ohne Katalog-Eintrag = Drift = Bug.**

---

## Versionierung

| Version | Datum | Anmerkung |
|---|---|---|
| v1.0 | 2026-05-21 | Initialer Katalog — Runde 1 |
