---
entity_id: issue_371_atoms
type: module
created: 2026-05-25
updated: 2026-05-25
status: draft
version: "1.0"
tags: [frontend, atomic-design, atoms, epic-368, issue-371, components]
---

<!-- Issue #371 — Atomic-Design Atoms lib/components/atoms/ (Bridge-Ansatz, schonend) -->

# Issue #371 — Atoms-Schicht `lib/components/atoms/` (schonende Konsolidierung)

## Approval

- [ ] Approved

## Zweck

Kanonische Atom-Schicht `frontend/src/lib/components/atoms/` mit den 13 Atomen aus der Sandbox-Vorlage `atoms.jsx` (Teil Epic #368). **Bridge-Ansatz (PO-bestätigt 2026-05-25):** Die 9 bereits existierenden `ui/`-Atome werden behalten und nur additiv ergänzt (keine Umbenennung, keine Aufrufer-Migration); die 4 fehlenden Atome werden neu gebaut; `atoms/` re-exportiert alles als eine Quelle. Compound-Primitive (Card, Input) behalten ihre reichere, barrierefreie Form (Epic-#368-Vorgabe). Niedriges Risiko, kein Bruch bestehender Routes (C6).

## Quelle / Source

**Kanonische Vorlage:** `docs/design-requests/issue_15_atomic_design/spec/atoms.jsx` (React/JSX) + `body-15-atomic-design-library.md` §Atoms.

**Neue Dateien (4 neue Atome):**
- `frontend/src/lib/components/atoms/Switch.svelte`
- `frontend/src/lib/components/atoms/SectionH.svelte`
- `frontend/src/lib/components/atoms/AvatarStack.svelte`
- `frontend/src/lib/components/atoms/KV.svelte`
- `frontend/src/lib/components/atoms/index.ts` (re-exportiert alle 13)
- `frontend/src/lib/components/atoms/Eyebrow.svelte`, `Pill.svelte`, `Card.svelte`, `Btn.svelte`, `Input.svelte`, `Dot.svelte`, `WIcon.svelte`, `ElevSparkline.svelte`, `TopoBg.svelte` — **dünne Re-Export-Wrapper** auf die bestehenden `ui/`-Pendants.

**Additive Erweiterungen an bestehenden `ui/`-Atomen (backward-compatible, keine Umbenennung):**
- `ui/eyebrow/Eyebrow.svelte` — optionaler `color`-Prop (Default `var(--g-ink-3)`).
- `ui/pill/Pill.svelte` — `ghost`-Tone ergänzen; Sandbox-Tone-Namen (`neutral|good|warn|bad`) als zusätzliche Aliase auf bestehende (`default|success|warning|danger`) akzeptieren.
- `ui/btn/Btn.svelte` — `quiet`-Variante ergänzen.
- `ui/dot/Dot.svelte` — numerischen `size` (Zahl) zusätzlich zu String-Size akzeptieren; tone-Default `good`.
- `ui/wicon/WIcon.svelte` — `kind`-Default `cloud`; `color`-Default auf Token (`var(--g-ink-2)`) prüfen.
- `ui/elev-sparkline/ElevSparkline.svelte` — optionale `stroke`/`fill`/`showArea`-Props ergänzen.

**Neue Test-Datei:** `frontend/src/lib/components/atoms/atoms.test.ts` (Source-Inspection + Props, node:test, keine Mocks).

**NICHT ändern:**
- `ui/card/` (Compound-Primitive, Epic #368 — bleibt; `atoms/Card.svelte` ist Wrapper für den einfachen `padding`/`accent`-Fall, der auf `ui/card` aufsetzt).
- Bestehende Aufrufer / Routes (kein Umbau; tiefere Vereinheitlichung erst bei Screen-Migration, #368 Phase 2).
- Token-Namen (Bridge #369 deckt alle benötigten `--g-*` ab).

> **Schicht-Hinweis:** Reine Frontend-Änderung (SvelteKit `frontend/src/lib/components/`). Keine Go/Python-Schicht.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `atoms.jsx` | Spec-Vorlage | Kanonische Atom-Definitionen (Props, Varianten, Verhalten) |
| `frontend/src/app.css` (#369 Bridge) | CSS-Tokens | Liefert alle `--g-*` (inkl. Sandbox-Namen) — Atome setzen keinen Inline-Hex (C1) |
| `frontend/src/lib/components/ui/*` | Bestehende Atome | Basis für 9 Re-Exporte + additive Erweiterungen |
| Epic #368 / body-15 | Übergeordnete Spec | Compound-Primitive bleiben; Naming-Konvention; backward-compat C6 |

## Implementation Details

### Neue Atome (1:1 aus atoms.jsx, Svelte 5 `$props()`, `<script lang="ts">`, Token-basiert)

- **Switch** — `checked`, `size: 'sm'|'md'|'lg'`, `tone: 'good'|'accent'|'info'|'warn'|'bad'`, `disabled`. Sizes sm(28×16) md(36×20) lg(44×26). On-Farbe via tone-Token. `role="switch"`, `aria-checked`, `aria-disabled`, `data-testid="switch"`. Click → Svelte-Event/`bind:checked`. lg ≥ 44px Touch.
- **SectionH** — `eyebrow`, `title`, `kicker`, `right` (Snippet). Flex space-between, Eyebrow-Atom oben.
- **AvatarStack** — `users: {name, initials?, color?}[]`, `size` (Zahl). Überlappende Kreise (marginLeft negativ), Border `var(--g-card)`.
- **KV** — `label`, `value`, `mono` (Default true). Flex space-between, dashed bottom-border `var(--g-rule-soft)`. (Legacy — Doku-Hinweis: bevorzugt `DetailRow`.)

### Re-Export-Wrapper (`atoms/<Name>.svelte`)
Dünner Wrapper, der das bestehende `ui/`-Pendant rendert und Props 1:1 + Sandbox-Aliase durchreicht. `atoms/index.ts` exportiert alle 13 + die 4 neuen unter `default`.

### Additive Erweiterungen
Nur Props/Tones HINZUFÜGEN, bestehende Werte unverändert lassen. Unbekannte `size`/`tone` → Default-Fallback (kein Crash).

## Expected Behavior

- **Input:** keiner zur Laufzeit (reine Komponenten).
- **Output:** `import { Switch, Eyebrow, … } from '$lib/components/atoms'` liefert alle 13 Atome; rendern SSR-fest, Token-basiert.
- **Side effects:** keine. Bestehende `ui/`-Importe funktionieren unverändert weiter.

## Acceptance Criteria

- **AC-1:** Given die Atoms-Schicht / When man `frontend/src/lib/components/atoms/` auflistet / Then existieren Dateien + `index.ts`-Re-Exporte für alle 13 Atome (Eyebrow, Pill, Card, Btn, Input, Switch, Dot, WIcon, ElevSparkline, SectionH, AvatarStack, TopoBg, KV).
  - Test: (populated after /tdd-red)

- **AC-2:** Given das neue `Switch`-Atom / When es mit `size` sm|md|lg und `tone` good|accent|info|warn|bad gerendert wird / Then trägt es `role="switch"`, `aria-checked` reflektiert `checked`, `data-testid="switch"`, und `size="lg"` ergibt ≥ 44px Breite (Touch-Mindestmaß).
  - Test: (populated after /tdd-red)

- **AC-3:** Given das `Input`-Atom in `size="lg"` / When es gerendert wird / Then ist die Schriftgröße 16px (kein iOS-Auto-Zoom) und es trägt `data-testid="input"` sowie `data-error` im Fehlerzustand.
  - Test: (populated after /tdd-red)

- **AC-4:** Given ein Atom mit unbekannter `size`/`tone`-Variante / When gerendert / Then fällt es auf den Default (`md`/`good`) zurück ohne Crash, und alle Atome sind SSR-fest (keine `window.*`-Zugriffe ohne `browser`-Guard).
  - Test: (populated after /tdd-red)

- **AC-5:** Given die bestehenden `ui/`-Atom-Importpfade und ihre bisherigen Props/Tone-Namen / When bestehender Code sie weiter nutzt / Then funktionieren sie unverändert (additive Erweiterung, keine Umbenennung) — Stichprobe: bestehende Routes rendern ohne Fehler.
  - Test: (populated after /tdd-red)

- **AC-6:** Given die 3 weiteren neuen/erweiterten Atome / When geprüft / Then erfüllen `SectionH` (eyebrow/title/kicker/right), `AvatarStack` (überlappende Avatare aus `users[]`), `KV` (label/value, dashed divider) ihre body-15-Props; Compound-Primitive Card/Input behalten ihre reichere Form (kein monolithischer Neuschrieb).
  - Test: (populated after /tdd-red)

## Known Limitations

- **F003 (Adversary, LOW):** Die 9 Re-Export-Wrapper nutzen `let props = $props()` ohne typisiertes Interface → beim Import aus `atoms/` fehlt TypeScript-Prop-Completion (Laufzeit unbeeinflusst). Folge-Verbesserung: typisierte Props pro Wrapper (`let props: BtnProps = $props()`), sobald alle ui/-Komponenten einen Props-Type exportieren. Nicht in #371.
- Tiefere Vereinheitlichung (Aufrufer von `ui/` auf `atoms/` umstellen, tone-Namen projektweit) erfolgt opportunistisch bei der Screen-Migration (Epic #368 Phase 2) — nicht in #371.
- `KV` ist Legacy; neue Verwendung soll `DetailRow` (Molecule #372) bevorzugen.
- `Segmented` ist bereits als `ui/segmented` vorhanden und nicht Teil der 13 #371-Atome (separat).

## Changelog

- 2026-05-25: Initial spec created (Issue #371, Atoms-Schicht, Bridge-Ansatz PO-bestätigt)
