---
entity_id: issue_373_mobile
type: module
created: 2026-05-26
updated: 2026-05-26
status: draft
version: "1.0"
tags: [frontend, atomic-design, mobile, touch-primitives, epic-368, issue-373]
---

<!-- Issue #373 — Mobile-Touch-Primitives lib/components/mobile/ (Bridge-Ansatz) -->

# Issue #373 — Mobile-Touch-Primitives `lib/components/mobile/`

## Approval

- [ ] Approved

## Zweck

`frontend/src/lib/components/mobile/` mit den 12 M*-Touch-Primitiven aus `mobile-shell.jsx` (Epic #368). Eigenständige Touch-Atome (44px Hit-Area), NICHT Mobile-Varianten der Molecules (C3). **Bridge-Ansatz (PO-bestätigt „schonend, nichts brechen", analog #371):** 10 Primitive neu bauen; TopAppBar/BottomNav (bereits aus #267 in `ui/sidebar/`) konsolidieren statt duplizieren (Re-Export + additive Prop-Angleichung). Erfüllt #312 (Toast/Sheet/Switch-Primitive) — #312 danach schließen.

## Quelle / Source

**Kanonische Vorlage:** `docs/design-requests/issue_15_atomic_design/spec/mobile-shell.jsx` (React/JSX → Svelte 5) + `body-15-atomic-design-library.md` §Mobile-Touch-Primitives.

**Neue Dateien (10 neue Primitive + interne Helfer):**
- `frontend/src/lib/components/mobile/MBtn.svelte`, `MInput.svelte`, `MField.svelte`, `MSwitch.svelte`, `MTab.svelte`, `MIcon.svelte`, `Drawer.svelte`, `Sheet.svelte`, `Toast.svelte`, `MobileShell.svelte`
- Interne Helfer (in `mobile/`, von M*-Primitiven genutzt): `IconBtn.svelte`, `NavIcon.svelte`, `DrawerGroup.svelte`, `DrawerItem.svelte`, `ScreenScroll.svelte`
- `frontend/src/lib/components/mobile/TopAppBar.svelte`, `BottomNav.svelte` — dünne Re-Export-Wrapper auf `ui/sidebar/`-Pendants.
- `frontend/src/lib/components/mobile/index.ts` (re-exportiert die 12 Primitive)

**Additive Erweiterungen an bestehenden #267-Komponenten (backward-compatible, falls Props fehlen):**
- `ui/sidebar/TopAppBar.svelte` — Props `eyebrow`, `leftIcon`, `right`, `dense`, `scrolled` ergänzen, falls nicht vorhanden.
- `ui/sidebar/BottomNav.svelte` — Props `active`, `onChange` prüfen/ergänzen.

**Neue Test-Datei:** `frontend/src/lib/components/mobile/mobile.test.ts` (Source-Inspection, node:test, keine Mocks).

**NICHT in die Bibliothek:** Demo-Rahmen `PhoneFrame`, `MobileStatusBar`, `HomeIndicator` (gehören in Showcase #374, nicht `mobile/`).

> **Schicht-Hinweis:** Reine Frontend-Änderung (SvelteKit `frontend/src/lib/components/`). Keine Go/Python-Schicht.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `mobile-shell.jsx` | Spec-Vorlage | Kanonische Definitionen der 12 Primitive (Props, Verhalten, Token-Nutzung) |
| `frontend/src/app.css` (#369 Bridge) | CSS-Tokens | Liefert alle `--g-*`; Primitive setzen keinen verbotenen Inline-Hex (C1) |
| `frontend/src/lib/components/ui/sidebar/{TopAppBar,BottomNav}.svelte` | Bestehend (#267) | Basis für 2 Re-Exporte + additive Angleichung |
| `frontend/src/lib/components/atoms/` (#371) | Atom-Schicht | MIcon/MSwitch dürfen Atom-Muster spiegeln; kein Hard-Dep |
| Epic #368 / body-15 §Mobile | Übergeordnete Spec | C3 (Touch-Primitive ≠ Molecule-Varianten), backward-compat C6 |

## Implementation Details

### Neue Primitive (1:1 aus mobile-shell.jsx, Svelte 5 `$props()`, Token-basiert, Touch-tauglich)
- **MBtn**: `variant`, `size` md|lg|xl, `block`, `icon`. lg/xl ≥ 44px Höhe.
- **MInput**: `value`, `type`, `placeholder`, `leftIcon`. font-size ≥ 16px (kein iOS-Zoom). `data-testid="m-input"`.
- **MField**: `label`, `sub` + Snippet (Touch-Padding).
- **MSwitch**: `checked`, `label`. Gesamt-Hit-Area ≥ 44px. `role="switch"`, `aria-checked`, `data-testid="m-switch"`.
- **MTab**: `items`, `active`, `onChange`, `scrollable`. `role="tablist"`.
- **MIcon**: `kind` (menu|back|close|plus|search|bell|…), `size`, `color`. Inline-SVG aus Vorlage.
- **Drawer**: `open`, `onClose`. Overlay + Slide-In. SSR-fest (Body-Scroll-Lock nur im `browser`-Guard).
- **Sheet**: `open`, `onClose`, `title`, `eyebrow`, `snap` full|half|peek, `footer`. Bottom-Sheet, snap-Höhen.
- **Toast**: `kind` info|success|warn|error, `msg`, `action`, `hint`. Token-Farben pro kind.
- **MobileShell**: Template — TopAppBar + ScreenScroll-Slot + BottomNav + Drawer/Sheet/Toast-Slots.

### Konsolidierung TopAppBar/BottomNav
`mobile/`-Wrapper rendern die `ui/sidebar/`-Pendants und reichen Props 1:1 durch; fehlende mobile-shell.jsx-Props additiv in `ui/sidebar/` ergänzen (keine Umbenennung).

### SSR & Token
Kein `window.*`/`document.*` ohne `browser`-Guard (Overlay-Komponenten). Unbekannte `variant`/`size`/`kind`/`snap`/`kind` → Default-Fallback, kein Crash.

## Expected Behavior

- **Input:** keiner zur Laufzeit (Komponenten).
- **Output:** `import { MBtn, Sheet, Toast, … } from '$lib/components/mobile'` liefert alle 12; SSR-fest, Token-basiert, Touch-tauglich.
- **Side effects:** keine; `ui/sidebar/`-Importe (#267) funktionieren unverändert.

## Acceptance Criteria

- **AC-1:** Given die Mobile-Schicht / When man `frontend/src/lib/components/mobile/` auflistet / Then existieren Dateien + `index.ts`-Re-Exporte für alle 12 Primitive (MBtn, MInput, MField, MSwitch, MTab, MIcon, TopAppBar, BottomNav, Drawer, Sheet, Toast, MobileShell).
  - Test: (populated after /tdd-red)

- **AC-2:** Given Touch-Mindestmaße / When MBtn `size="lg"`/`"xl"` bzw. MSwitch gerendert werden / Then ist die Hit-Area ≥ 44px, und MSwitch trägt `role="switch"`, `aria-checked`, `data-testid="m-switch"`.
  - Test: (populated after /tdd-red)

- **AC-3:** Given MInput / When gerendert / Then ist die Schriftgröße ≥ 16px (kein iOS-Auto-Zoom) und es trägt `data-testid="m-input"`.
  - Test: (populated after /tdd-red)

- **AC-4:** Given die Overlay-Primitive Drawer/Sheet/Toast und alle M*-Komponenten / When SSR durch SvelteKit / Then kein `window.*`/`document.*`-Zugriff ohne `browser`/onMount-Guard; unbekannte `variant`/`size`/`snap`/`kind` → Default-Fallback ohne Crash.
  - Test: (populated after /tdd-red)

- **AC-5:** Given die bestehenden #267-Komponenten `ui/sidebar/TopAppBar` + `BottomNav` / When bestehender Code sie weiter nutzt / Then funktionieren sie unverändert (additive Erweiterung, keine Umbenennung); die `mobile/`-Wrapper reichen Props korrekt durch.
  - Test: (populated after /tdd-red)

- **AC-6:** Given die Token-Disziplin (C1) / When man die neuen Primitive prüft / Then nutzen sie `var(--g-*)` (kein verbotener Inline-Hex außer von der Vorlage bewusst übernommene); Sheet `snap` full|half|peek, Toast `kind` info|success|warn|error rendern je distinct.
  - Test: (populated after /tdd-red)

## Known Limitations

- Demo-Rahmen (PhoneFrame, MobileStatusBar, HomeIndicator) bewusst NICHT in `mobile/` — gehören in Showcase #374.
- Visuelle Abnahme der Primitive erfolgt mit Showcase #374 (Bibliothek bis dahin inert, keine Route nutzt sie).
- Tiefere Vereinheitlichung (Mobile-Routes auf `mobile/` umstellen) → opportunistisch bei Screen-Migration (#368 Phase 2).
- Wrapper-Typ-Transparenz (analog #371-F003): typisierte Props als Folge-Verbesserung.

## Changelog

- 2026-05-26: Initial spec created (Issue #373, Mobile-Touch-Primitives, Bridge-Ansatz)
