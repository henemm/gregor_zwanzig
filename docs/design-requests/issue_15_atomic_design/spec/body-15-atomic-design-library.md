<!-- gregor-zwanzig-handoff: stable_id=atomic-design-component-library -->
# Issue 15 · Atomic-Design-Komponentenbibliothek (SvelteKit-Migration)

**Type:** Frontend Architecture · Refactor
**Priority:** High (Foundation für künftige Feature-Issues — alle UI-Issues bauen darauf auf)
**Design Reference:**
- Komponenten-Showcase: `Gregor 20 - Redesign v2.html` → Section "01 · Komponenten-System" → Artboard **Design-System** (Brand · Typografie · Farben · Bausteine · Molecules · Voice)
- Inventur + Migrations-Verlauf: `docs/atomic-design-inventory.md`
- Brand-Grundgesetz: `brand-kit.jsx`
- Atoms-Library: `atoms.jsx`
- Molecules-Library: `molecules.jsx`
- Mobile-Touch-Primitives: `mobile-shell.jsx`

---

## Problem

Die SvelteKit-Frontend-Codebase (`frontend/src/lib/components/`) hat heute weder eine konsistente Komponenten-Hierarchie noch ein Brand-Grundgesetz. Komponenten werden pro Screen neu erfunden, und das Wordmark / Logo unterscheidet sich zwischen Seiten.

Diese drift hat die Design-Sandbox (`henemm/gregor-zwanzig`) bereits aufgeräumt — diese Issue migriert die Sandbox-Library 1:1 in den SvelteKit-Code, sodass alle künftigen UI-Issues gegen **eine** Komponenten-Quelle implementiert werden.

---

## Konzept · Atomic Design in fünf Schichten

```
Brand   (brand-kit.jsx)       →  src/lib/brand/
Atoms   (atoms.jsx)           →  src/lib/components/atoms/
Molecules (molecules.jsx)     →  src/lib/components/molecules/
Templates (BrandShell etc.)   →  src/lib/components/templates/
Pages   (screen-*.jsx)        →  src/routes/*/+page.svelte
```

Regeln:
- **Pages dürfen Inline-Komponenten NIEMALS auf Atom/Molecule-Ebene definieren.** Wenn ein Screen ein Listen-Item braucht, das nicht in `molecules.jsx` existiert: erst die Molecule anlegen, dann verwenden.
- **Brand-Grundgesetz hat Vorrang.** Bei Konflikt gewinnt `brand-kit.jsx`. Dann `atoms.jsx`. Pages kehren die Hierarchie nie um.
- **Naming-Konvention:** Brand-only → `Brand*`. Mobile-only → `M*`. Templates → `*Shell` oder `*Layout`. Atoms/Molecules → sprechender Name ohne Prefix.

---

## Constraints

| ID  | Constraint                                                                                                            |
|-----|-----------------------------------------------------------------------------------------------------------------------|
| C1  | Tokens kommen aus `app.css` (`@layer base { :root { --g-* } }`). Komponenten dürfen keinen Hex-Code inline setzen, außer Brand-Glyphen (`#c45a2a` für den Blitz im SVG-Pfad, falls Token-Substitution dort technisch nicht möglich). |
| C2  | Jede Atom-/Molecule-Datei ist **eine** Svelte-Datei mit klarem Default-Export und typisierter Props-Definition (`<script lang="ts">`). |
| C3  | Mobile-Pendants existieren NUR als Touch-Primitives in `M*`-Komponenten. Listen-Item-Molecules (StagePill, ChannelRow, BriefingTimelineRow, etc.) bedienen Desktop UND Mobile über `dense` / `last` / `compact` / `size` Props. |
| C4  | Showcase-Route `/_design-system` rendert ALLE Atome + Molecules + Templates in jeweils allen Varianten. Diese Route ist gleichzeitig Regressionstest. |
| C5  | Brand-Wordmark IST der Lockup `BrandIcon` + Mono-Typo `gregor . zwanzig`. Variante `icon="only"` für Favicon / Avatar / quadratische Kontexte. Keine zweite Logo-Geometrie irgendwo. |
| C6  | Alle bisher verwendeten Komponentennamen aus dem Bestand bleiben backward-compatible (Wrapper-Aliase erlaubt). Bestehende Routes brechen nicht. |

---

## Komponenten-Katalog

### Brand · `src/lib/brand/`

| Svelte-Datei              | Spec-Quelle (JSX)                  | Props (zusammengefasst)                                                                          |
|---------------------------|------------------------------------|--------------------------------------------------------------------------------------------------|
| `BrandIcon.svelte`        | `brand-kit.jsx::BrandIcon`         | `size: 'sm'\|'md'\|'lg'\|number`, `color`, `accent`                                              |
| `BrandIconSquare.svelte`  | `brand-kit.jsx::BrandIconSquare`   | `size: number`, `color`, `accent`, `bg`, `bleed: boolean`                                        |
| `BrandWordmark.svelte`    | `brand-kit.jsx::BrandWordmark`     | `size: 'sm'\|'md'\|'lg'`, `dark: boolean`, `caption: string`, `icon: 'left'\|'only'\|'none'`     |
| `BrandUserBadge.svelte`   | `brand-kit.jsx::BrandUserBadge`    | `name`, `sub`, `initials`, `accent: boolean`                                                     |
| `BrandSidebar.svelte`     | `brand-kit.jsx::BrandSidebar`      | `active`, `counts`, `user`, `onNavigate`                                                         |
| `BrandShell.svelte`       | `brand-kit.jsx::BrandShell`        | `active`, `counts`, `user`, `onNavigate` + `<slot/>`                                             |

Die SVG-Pfade in `BrandIcon` / `BrandIconSquare` müssen **byte-genau** aus `brand-kit.jsx` übernommen werden — das ist die kanonische Geometrie.

### Atoms · `src/lib/components/atoms/`

| Svelte-Datei            | Spec-Quelle           | Schlüssel-Props                                                                                 |
|-------------------------|-----------------------|-------------------------------------------------------------------------------------------------|
| `Eyebrow.svelte`        | `atoms.jsx::Eyebrow`  | `color`                                                                                         |
| `Pill.svelte`           | `atoms.jsx::Pill`     | `tone: 'neutral'\|'accent'\|'good'\|'warn'\|'bad'\|'ghost'`                                     |
| `Card.svelte`           | `atoms.jsx::Card`     | `padding: number`, `accent: boolean`                                                            |
| `Btn.svelte`            | `atoms.jsx::Btn`      | `variant: 'primary'\|'accent'\|'ghost'\|'quiet'`, `size: 'xs'\|'sm'\|'md'\|'lg'`, `icon`        |
| `Input.svelte`          | `atoms.jsx::Input`    | `type`, `value`, `placeholder`, `leftIcon`, `error`, `mono: boolean`, `size: 'sm'\|'md'\|'lg'`  |
| `Switch.svelte`         | `atoms.jsx::Switch`   | `checked`, `size: 'sm'\|'md'\|'lg'`, `tone: 'good'\|'accent'\|'info'\|'warn'\|'bad'`, `disabled` |
| `Dot.svelte`            | `atoms.jsx::Dot`      | `tone`, `size: number`                                                                          |
| `WIcon.svelte`          | `atoms.jsx::WIcon`    | `kind: 'sun'\|'cloud'\|'rain'\|'thunder'\|'snow'\|'wind'\|'moon'\|'headlamp'`, `size`, `color`  |
| `ElevSparkline.svelte`  | `atoms.jsx::ElevSparkline` | `data: number[]`, `width`, `height`, `stroke`, `fill`, `showArea`                          |
| `SectionH.svelte`       | `atoms.jsx::SectionH` | `eyebrow`, `title`, `kicker`, `right`                                                           |
| `AvatarStack.svelte`    | `atoms.jsx::AvatarStack` | `users: {name, initials?, color?}[]`, `size`                                                 |
| `TopoBg.svelte`         | `atoms.jsx::TopoBg`   | `opacity`, `color`, `lines: number`, `density`                                                  |
| `KV.svelte`             | `atoms.jsx::KV`       | `label`, `value`, `mono: boolean` (Legacy — bevorzugt `DetailRow` Molecule)                     |

### Molecules · `src/lib/components/molecules/`

| Svelte-Datei                  | Spec-Quelle                   | Schlüssel-Props                                                                                      |
|-------------------------------|-------------------------------|------------------------------------------------------------------------------------------------------|
| `Field.svelte`                | `molecules.jsx::Field`         | `label`, `hint`, `error`, `side`, `dense: boolean` + `<slot/>`                                       |
| `DetailRow.svelte`            | `molecules.jsx::DetailRow`     | `label`, `value`, `sub`, `icon`, `right`, `mono`, `divider: 'dashed'\|'solid'\|'none'`               |
| `StagePill.svelte`            | `molecules.jsx::StagePill`     | `stage: {code, risk}`, `state: 'active'\|'done'\|'future'\|'muted'`                                  |
| `ChannelRow.svelte`           | `molecules.jsx::ChannelRow`    | `kind`, `target`, `active`, `sub`, `onToggle`, `dense: boolean`, `last: boolean`                     |
| `ChannelChip.svelte`          | `molecules.jsx::ChannelChip`   | `kind`, `active`, `compact: boolean`                                                                 |
| `BriefingTimelineRow.svelte`  | `molecules.jsx::BriefingTimelineRow` | `report: {when, kind, etappe, channels, status}`, `dense: boolean`                              |
| `BriefingScheduleRow.svelte`  | `molecules.jsx::BriefingScheduleRow` | `label`, `sub`, `time`, `enabled`, `onToggle`, `last: boolean`                                  |
| `ThresholdRow.svelte`         | `molecules.jsx::ThresholdRow`  | `label`, `value`, `divider`, `last`, `editable`, `onEdit`                                            |
| `Stat.svelte`                 | `molecules.jsx::Stat`          | `label`, `value`, `sub`, `unit`, `tone: 'default'\|'accent'`, `layout: 'stack'\|'inline'`, `size: 'sm'\|'md'\|'lg'`, `mono: boolean` |
| `AlertRow.svelte`             | `molecules.jsx::AlertRow`      | `alert: {kind, when, msg, channel?}`, `variant: 'icon'\|'dot'\|'plain'`, `divider`, `last`           |

### Mobile-Touch-Primitives · `src/lib/components/mobile/` (M*-Prefix)

Aus `mobile-shell.jsx`. Diese sind **nicht** Mobile-Varianten von Molecules — sie sind eigenständige Touch-Atome (z. B. 44 px Hit-Area).

| Svelte-Datei              | Schlüssel-Props                                                                                       |
|---------------------------|-------------------------------------------------------------------------------------------------------|
| `MBtn.svelte`             | `variant`, `size: 'md'\|'lg'\|'xl'`, `block`, `icon`                                                  |
| `MInput.svelte`           | `value`, `type`, `placeholder`, `leftIcon` (min font 16px gegen iOS-Zoom)                             |
| `MField.svelte`           | `label`, `sub` + `<slot/>` (Touch-Padding)                                                            |
| `MSwitch.svelte`          | `checked`, `label` (44 px Hit-Area)                                                                   |
| `MTab.svelte`             | `items`, `active`, `onChange`, `scrollable`                                                           |
| `MIcon.svelte`            | `kind: 'menu'\|'back'\|'close'\|'plus'\|'search'\|'bell'\|…`, `size`, `color`                          |
| `TopAppBar.svelte`        | `title`, `eyebrow`, `onMenu`, `leftIcon`, `right`, `dense`, `scrolled`                                |
| `BottomNav.svelte`        | `active`, `onChange`                                                                                  |
| `Drawer.svelte`           | `open`, `onClose`                                                                                     |
| `Sheet.svelte`            | `open`, `onClose`, `title`, `eyebrow`, `snap: 'full'\|'half'\|'peek'`, `footer`                       |
| `Toast.svelte`            | `kind: 'info'\|'success'\|'warn'\|'error'`, `msg`, `action`, `hint`                                   |
| `MobileShell.svelte`      | Template: TopAppBar + ScreenScroll + BottomNav + Drawer/Sheet/Toast-Slots                             |

---

## Showcase-Route (Acceptance-Gate)

```
src/routes/_design-system/+page.svelte
```

Rendert **alle** Komponenten in allen Varianten — direkt aus dem Spec-Showcase übernehmbar (`screen-design-system.jsx`). Diese Route ist die Regressions-Referenz für jeden künftigen UI-PR: bevor ein Pattern in einer normalen Route landet, muss es im Showcase sichtbar sein.

Sektionen:
1. **Brand** — Lockup in 3 Sizes, auf hell + dunkel, `icon="only"` für quadratische Kontexte, alle 3 `icon`-Prop-Varianten
2. **Typografie** — Type-Scale (xs/sm/md/lg/xl/2xl/3xl/4xl/5xl)
3. **Farben** — Surfaces / Ink / Accent / Semantic / Wetter-Farben
4. **Bausteine** — Pills, Buttons, Inputs (3 Sizes), Switches (3 Sizes × 5 Tones), WIcons
5. **Molecules** — Field, DetailRow, StagePill (alle 4 States), ChannelRow (Desktop + dense), ChannelChip (default + compact), Stat (stack + inline + 3 Sizes), AlertRow (3 Varianten), BriefingTimelineRow (default + dense), BriefingScheduleRow, ThresholdRow (default + divider="solid")
6. **Voice & Tonalität** — Tun-/Lassen-Beispiele

---

## Migration

### Schritt 1 · CSS-Tokens

`frontend/src/app.css` enthält bereits die Tokens (siehe Issue 00). Vor dieser Migration sicherstellen, dass alle `--g-*` Variablen vorhanden sind — sonst rendert nichts. Speziell prüfen: `--g-paper`, `--g-ink`, `--g-accent`, `--g-rule`, `--g-r-2`, `--g-r-3`, `--g-r-pill`, `--g-font-sans`, `--g-font-mono`, `--g-good`, `--g-warn`, `--g-bad`, `--g-info`, `--g-accent-deep`, `--g-accent-tint`.

### Schritt 2 · Brand zuerst, dann Atoms, dann Molecules

In dieser Reihenfolge bauen (Abhängigkeiten von unten nach oben):

1. `BrandIcon.svelte` — kein anderes Atom benötigt
2. `BrandWordmark.svelte` — verwendet `BrandIcon`
3. `BrandIconSquare.svelte` — kein anderes Atom benötigt
4. `BrandUserBadge.svelte`, `BrandSidebar.svelte`, `BrandShell.svelte`
5. Alle Atoms parallel (sie sind voneinander unabhängig außer `WIcon` von `Btn` Icon-Slot — kein Hard-Dep)
6. Molecules nutzen Atoms: `ChannelRow` → `Switch`, `BriefingScheduleRow` → `Switch`, `BriefingTimelineRow` → `Dot` + `ChannelChip`, `AlertRow` → `WIcon`, `Field` → keine, `Stat` → keine, etc.
7. Mobile-Atoms parallel zu Atoms (kein Hard-Dep)
8. Showcase-Route am Schluss

### Schritt 3 · Bestehende Screens auf neue Library umziehen

Nicht in einem PR. Ein Screen pro PR:

| Screen-Route             | Spec-Datei (JSX)                |
|--------------------------|---------------------------------|
| `/` (Home)               | `screen-home.jsx`               |
| `/trips`                 | `screen-trips.jsx`              |
| `/trips/[id]`            | `screen-trip-detail.jsx`        |
| `/trips/new`             | `screen-trip-wizard.jsx`        |
| `/compare`               | `screen-compare.jsx`            |
| `/archive`               | `screen-archive.jsx`            |
| `/_design-system`        | `screen-design-system.jsx`      |

Pro Screen: lokale Inline-Komponenten durch Library-Komponenten ersetzen. Jede gelöschte Inline-Definition im PR-Body benennen.

---

## Acceptance Criteria

- [ ] `src/lib/brand/` enthält 6 Svelte-Dateien (BrandIcon, BrandIconSquare, BrandWordmark, BrandUserBadge, BrandSidebar, BrandShell)
- [ ] `src/lib/components/atoms/` enthält die 13 Atome aus dem Katalog
- [ ] `src/lib/components/molecules/` enthält die 10 Molecules aus dem Katalog
- [ ] `src/lib/components/mobile/` enthält die 12 M*-Touch-Primitives
- [ ] `BrandWordmark` rendert mit Berg+Blitz-Glyph + lowercase Mono-Typo `gregor . zwanzig` + Caption `V0.20 · WETTER-BRIEFING`. Default `icon="left"` — der Glyph ist sichtbar.
- [ ] `BrandIcon` SVG-Pfad ist byte-genau identisch mit `brand-kit.jsx::BrandIcon`. Blitz: `M48 11 L41 23 L45 23 L43 29 L50 17 L46 17 Z`. Bergkamm: `M3 54 L18 22 L29 38 L38 26 L52 50 L61 54 Z`.
- [ ] `Switch`-Atom unterstützt `size: 'sm'|'md'|'lg'` und `tone: 'good'|'accent'|'info'|'warn'|'bad'`. `lg`-Größe trifft 44px Touch-Mindestmaß.
- [ ] `Input`-Atom in `size="lg"` setzt `font-size: 16px` (verhindert iOS-Auto-Zoom).
- [ ] `ChannelRow` ohne `dense`-Prop rendert Card-Layout (`--g-card-alt`, rounded). Mit `dense` rendert Reihen-Layout (kein Background, Bottom-Border `--g-rule-soft`).
- [ ] `BriefingTimelineRow` ohne `dense` zeigt Channel-Pills + "gesendet/geplant"-Suffix. Mit `dense` zeigt 24×24 `ChannelChip compact`-Tiles und keinen Suffix.
- [ ] `Stat` rendert in `layout="stack"` Label-oben / Value-unten, in `layout="inline"` Value-links-groß / Label-rechts-klein.
- [ ] `AlertRow` rendert 3 Varianten: `icon` mit `WIcon` links, `dot` mit Accent-Dot links, `plain` ohne Marker.
- [ ] `/_design-system` rendert alle Komponenten ohne Console-Errors. Liefert Screenshot-Vergleich gegen `screen-design-system.jsx` (Spec-Source).
- [ ] Bestehende Routes brechen NICHT. Stichprobe: Sidebar (Brand-Lockup sichtbar), Trips-Liste, Trip-Detail, Compare, Archive — alle laden ohne Layout-Schäden.
- [ ] `frontend/CLAUDE.md` (falls vorhanden) oder `frontend/README.md` enthält den Abschnitt "Atomic-Design-Disziplin" aus dem Sandbox-`CLAUDE.md` (Lese-Regel vor jeder UI-Arbeit + Naming-Konvention + Konflikt-Regel).

---

## Edge Cases

| Fall                                                                                                              | Erwartetes Verhalten                                                                                                |
|-------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------|
| Komponente bekommt unbekannte `size`-/`tone`-Variante                                                              | Fallback auf Default (`md` / `good`), kein Crash.                                                                   |
| `Stat value=""` oder `value={null}`                                                                                | Render einen Em-Dash `—` statt leerem Wert.                                                                          |
| `ChannelRow onToggle={undefined}` aber `active=true`                                                              | Switch rendert read-only (kein Click-Handler).                                                                       |
| `BrandWordmark caption={null}`                                                                                     | Caption-Zeile wird weggelassen, Wordmark rückt nach oben (kein leerer Whitespace).                                  |
| Inline-Style auf Svelte-Komponente von außen via `class:` oder `style:`                                            | Erlaubt — Komponenten dürfen `class={$$restProps.class || ''}` durchreichen, aber Tokens nicht überschreiben.       |
| Server-Side-Rendering (SSR) durch SvelteKit                                                                        | Alle Komponenten müssen SSR-fest sein — keine `window.*`-Zugriffe ohne `browser`-Guard.                              |
| Komponente in einer Mobile-Route gerendert (Viewport < 900px)                                                      | Atoms/Molecules verhalten sich identisch zu Desktop. Mobile-spezifisches Spacing geht über `dense`/`last`-Props.    |

---

## Out of Scope (Folge-Issues)

- **Promotions:** `TripRow` Molecule (aktuell Inline in `screen-trips.jsx`), `Tab` Atom als Desktop-Pendant zu `MTab`, `StatusBadge` als Pill-Variante. Werden opportunistisch beim Touch des jeweiligen Screens gemacht — eigenes Issue später.
- **Storybook:** Wenn gewünscht in einem Folge-Issue. Die Showcase-Route deckt den 80%-Use-Case schon ab.
- **Typografie-Tests:** Kein automatischer Visual-Regression-Test in diesem PR. Manueller Screenshot-Vergleich gegen die Sandbox reicht.
- **Email-themed Stat-Komponenten** (`EmailStat`, `SumStat`, `CEStat`) — bleiben bewusst hardcoded mit Email-Client-Farben und gehören NICHT in die Library.
- **Interaktiver Stepper-Editor** (`ThresholdRowM` mit −/+ Buttons in alert-config-mobile) — eigene Domäne, kein Drop-in für die read-only `ThresholdRow`.

---

## Test-Hooks für Playwright / Vitest

Erhalte bestehende `data-testid`-Attribute auf migrierten Komponenten. Zusätzlich für neue Library-Komponenten:

- `BrandWordmark`: `data-testid="brand-wordmark"` auf Root-Element. SVG-Child mit `data-testid="brand-icon"`.
- `Switch`: `data-testid="switch"`, `aria-checked` reflektiert `checked`-Prop, `role="switch"`.
- `Input`: `data-testid="input"`, `data-error={!!error}` für Tests gegen Error-State.
- `StagePill`: `data-state={state}` reflektiert den State-Prop.

---

## Referenz-Dateien

Diese Sandbox-Dateien sind die **kanonische Spec** für die Migration. Bei Widerspruch zwischen Dateien gewinnt die Reihenfolge unten (oben = höchste Autorität):

1. `brand-kit.jsx` — Brand-Grundgesetz (alle Brand-Komponenten)
2. `tokens.css` — alle Design-Tokens
3. `atoms.jsx` — Atom-Definitionen
4. `molecules.jsx` — Molecule-Definitionen
5. `mobile-shell.jsx` — Mobile-Touch-Primitives
6. `screen-design-system.jsx` — Showcase als Visualisierungsreferenz
7. `docs/atomic-design-inventory.md` — Inventur + Migrations-Verlauf
