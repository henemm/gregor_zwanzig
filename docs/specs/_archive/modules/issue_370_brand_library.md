---
entity_id: issue_370_brand_library
type: module
created: 2026-05-25
updated: 2026-05-25
status: draft
version: "1.0"
tags: [frontend, design-system, brand, svelte, svg, wordmark, glyph, epic-368, issue-370, issue-279]
---

# Issue #370 — Brand-Bibliothek `lib/brand/` (Berg+Blitz-Glyph + Wordmark-Lockup)

## Approval

- [ ] Approved

## Purpose

Legt das kanonische Brand-Verzeichnis `frontend/src/lib/brand/` mit 6 Svelte-5-Komponenten an, die 1:1 aus der Designquelle `brand-kit.jsx` portiert werden. Das Modul liefert das einzige Logo/Glyph der App (kein zweites Geometry-System darf existieren), ersetzt die reine Text-Wordmark aus Issue #293 durch ein Lockup aus Berg+Blitz-Glyph und Mono-Typo und schließt damit zugleich Issue #279 (Sidebar zeigt endlich den Glyph statt reinen Text).

> **PFLICHT — Schicht-Hinweis:** Alle Dateien liegen ausschliesslich im Frontend-Layer (`frontend/src/`). Kein Go-API-Code und kein Python-Backend-Code ist betroffen. Schicht: **Frontend / SvelteKit**, Komponenten unter `frontend/src/lib/brand/`.

## Source

- **Neue Dateien:**
  - `frontend/src/lib/brand/BrandIcon.svelte`
  - `frontend/src/lib/brand/BrandIconSquare.svelte`
  - `frontend/src/lib/brand/BrandWordmark.svelte`
  - `frontend/src/lib/brand/BrandUserBadge.svelte`
  - `frontend/src/lib/brand/BrandSidebar.svelte`
  - `frontend/src/lib/brand/BrandShell.svelte`
  - `frontend/src/lib/brand/index.ts` (Barrel, optional aber empfohlen)
- **Geanderte Dateien:**
  - `frontend/src/lib/components/ui/wordmark/Wordmark.svelte` → Thin-Wrapper
  - `frontend/e2e/issue-293-wordmark.spec.ts` → Test-Update
- **Ungeanderte Dateien (erben automatisch den Glyph via Wrapper):**
  - `frontend/src/lib/components/ui/sidebar/Sidebar.svelte`
  - `frontend/src/lib/components/ui/sidebar/TopAppBar.svelte`
  - `frontend/src/routes/login/+page.svelte`
  - `frontend/src/routes/_design/+page.svelte`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `issue_369_token_bridge` | Upstream-Issue (Spec: `docs/specs/modules/issue_369_token_bridge.md`) | **PFLICHT vor Merge von #370.** Liefert 9 fehlende Tokens: `--g-ink-2`, `--g-ink-3`, `--g-ink-4`, `--g-font-mono`, `--g-font-sans`, `--g-r-3`, `--g-r-pill`, `--g-rule`, `--g-accent-deep`. Ohne diese Bridge rendert BrandWordmark mit Fallback-Font und falscher Punktfarbe. |
| `brand-kit.jsx` | Designquelle (`docs/design-requests/issue_15_atomic_design/spec/brand-kit.jsx`) | Kanonische Geometrie, Props, Massangaben und SVG-Pfade. Hoechste Autoritat — bei Widerspruch gewinnt diese Datei. |
| `body-15-atomic-design-library.md` | Master-Spec (`docs/design-requests/issue_15_atomic_design/spec/body-15-atomic-design-library.md`) | Migrations-Reihenfolge (Schritt 2), Constraints C1–C6, Test-Hooks, Edge Cases. |
| `frontend/src/app.css` | CSS-Datei (vorhanden) | Token-Quelle nach Merge von #369; liefert alle `--g-*`-Variablen die Brand-Komponenten benoetigen. |
| `frontend/src/lib/components/ui/wordmark/Wordmark.svelte` | Bestehende Komponente (Issue #293) | Wird zum Thin-Wrapper umgebaut. Alle 4 bestehenden Imports bleiben byte-gleich nutzbar. |
| `frontend/e2e/issue-293-wordmark.spec.ts` | E2E-Test (vorhanden) | Muss in #370 aktualisiert werden, da Caption-Case und Selektoren sich aendern (Test-Pflicht). |

## Implementation Details

### Konventionen (gelten fuer alle 6 Komponenten)

```
- <script lang="ts">
- interface Props { ... }
- let { prop = default, ... }: Props = $props();
- Inline-SVG direkt im Template, kein img/src
- Scoped <style>-Block fuer Layout-CSS, Token-Referenzen via var(--g-*)
- Kein Hex-Code ausser im SVG-Pfad-Fill des Blitzes (C1-Ausnahme: technisch nicht substituierbar)
- Konvention: wie frontend/src/lib/components/ui/btn/Btn.svelte und ui/dot/Dot.svelte
```

### 1. `BrandIcon.svelte`

Props:
```typescript
interface Props {
  size?: 'sm' | 'md' | 'lg' | number;  // SIZES: sm=18, md=24, lg=32; Default: 'md'
  color?: string;                        // Default: 'var(--g-ink)'
  accent?: string;                       // Default: 'var(--g-accent)'
}
```

SVG: viewBox `0 0 64 64`, width/height = px (berechnet aus size).
Stroke-Width: `sw = Math.max(1.6, px / 12)` — proportional, Floor gegen Hairline.
Test-Hook: `data-testid="brand-icon"` auf `<svg>`, `aria-label="Gregor Zwanzig"`.

Zwei SVG-Pfade, BYTE-GENAU aus brand-kit.jsx:
```
Blitz  (fill=accent, strokeLinejoin="miter", strokeMiterlimit="8"):
  d="M48 11 L41 23 L45 23 L43 29 L50 17 L46 17 Z"

Bergkamm  (stroke=color, strokeWidth=sw, strokeLinejoin="miter",
           strokeLinecap="square", strokeMiterlimit="8", fill="none"):
  d="M3 54 L18 22 L29 38 L38 26 L52 50 L61 54 Z"
```

### 2. `BrandIconSquare.svelte`

Props:
```typescript
interface Props {
  size?: number;    // Default: 96
  color?: string;   // Default: 'var(--g-ink)'
  accent?: string;  // Default: 'var(--g-accent)'
  bg?: string;      // Default: 'var(--g-paper)'
  bleed?: boolean;  // Default: false
}
```

Wrapper-Div: `width=size`, `height=size`, `background=bg`, `overflow=hidden`,
`borderRadius = bleed ? 0 : Math.max(2, size / 14)`.
`sw = Math.max(1.4, size / 36)`.

SVG viewBox `0 0 64 64`, preserveAspectRatio `xMidYMid meet`.
Pfade (selbe 2 wie BrandIcon) PLUS:
```
Sub-Kante  (nur wenn size >= 32, opacity=0.45):
  d="M3 54 L18 22 L25 32"  stroke=color, strokeWidth=sw, miter, square, fill=none

Horizont-Linie  (nur wenn size >= 28, opacity=0.3):
  <line x1="3" y1="58" x2="61" y2="58" stroke=color strokeWidth="1"/>
```

### 3. `BrandWordmark.svelte`

Props:
```typescript
interface Props {
  size?: 'sm' | 'md' | 'lg';         // Default: 'md'
  dark?: boolean;                      // Default: false
  caption?: string | null;             // Default: 'V0.20 · Wetter-Briefing'
  icon?: 'left' | 'only' | 'none';   // Default: 'left'
}
```

SIZES-Tabelle (aus brand-kit.jsx):
```
sm: row=14, sub=8,  gap=2, iconGap=8,  iconPx=20
md: row=18, sub=9,  gap=3, iconGap=10, iconPx=26
lg: row=24, sub=10, gap=4, iconGap=14, iconPx=34
```

Farb-Logik:
```
dark=true:  inkPrimary='var(--g-paper)',         inkDot='rgba(246,244,238,0.45)', inkCaption='rgba(246,244,238,0.55)'
dark=false: inkPrimary='var(--g-ink)',            inkDot='var(--g-ink-4)',          inkCaption='var(--g-ink-4)'
```

Typo-Block: `<span>gregor</span><span style:color=inkDot>.</span><span style:color="var(--g-accent)">zwanzig</span>`
Font: `var(--g-font-mono)`, fontWeight=500, letterSpacing=0.04em, color=inkPrimary.
Caption (wenn caption nicht null/leer): `var(--g-font-mono)`, letterSpacing=0.18em, text-transform=uppercase, color=inkCaption. Leere Caption → komplett weglassen, kein Whitespace.

Varianten:
- `icon="only"` → nur `<BrandIcon size={iconPx * 1.6} color={inkPrimary}/>`, kein Typo-Block.
- `icon="none"` → nur Typo-Block, kein Icon.
- `icon="left"` (Default) → inline-flex, BrandIcon (size=iconPx) + Typo-Block, gap=iconGap.

Test-Hook: `data-testid="brand-wordmark"` auf Root-Element.
Unbekannte size → Fallback `md`. Unbekanntes icon → Fallback `left`.

### 4. `BrandUserBadge.svelte`

Props:
```typescript
interface Props {
  name?: string;      // Default: 'Gregor Henemm'
  sub?: string | null; // Default: 'henemm.com'; null → einzeilig
  initials?: string;  // Default: auto aus name (erste 2 Wort-Anfaenge, upper)
  accent?: boolean;   // Default: false; true → Avatar-Bg in --g-accent statt --g-ink
}
```

Avatar: 28x28px, borderRadius=50%, bg=(accent ? `var(--g-accent)` : `var(--g-ink)`), color=`var(--g-paper)`, font=`var(--g-font-sans)`, fontWeight=600, fontSize=11.
Name: `var(--g-font-sans)`, 13px, fontWeight=500, color=`var(--g-ink)`, ellipsis overflow.
Sub (wenn nicht null): `var(--g-font-mono)`, 11px, color=`var(--g-ink-3)`, ellipsis overflow.
Initialen-Berechnung: `name.split(" ").map(p => p[0]).slice(0, 2).join("").toUpperCase()`.

### 5. `BrandSidebar.svelte`

Props:
```typescript
interface Props {
  active?: 'home' | 'trips' | 'compare' | 'archive'; // Default: 'home'
  counts?: Record<string, number>;                     // Default: {}
  onNavigate?: (id: string) => void;
  user?: { name?: string; sub?: string; accent?: boolean };
}
```

Kanonische Nav-Items (fest, in dieser Reihenfolge):
```
{ id: 'home',    label: 'Startseite',     icon: 'home'    }
{ id: 'trips',   label: 'Meine Touren',   icon: 'trip'    }
{ id: 'compare', label: 'Orts-Vergleich', icon: 'compare' }
{ id: 'archive', label: 'Archiv',         icon: 'archive' }
```

Aufbau: `<aside>` (width=220, bg=`var(--g-paper-deep)`, borderRight `1px solid var(--g-rule)`, flexDirection=column, padding-top=24px).
Header-Block: `<BrandWordmark size="md"/>` in Padding-Div (0 18px 24px).
Nav: flexColumn, gap=2, padding 0 12px; je Item ein BrandSidebarItem-Element.
Footer: borderTop `1px solid var(--g-rule-soft)`, padding 16px 18px; `<BrandUserBadge name={user?.name ?? 'Gregor Henemm'} sub={user?.sub ?? 'henemm.com'} accent={user?.accent ?? false}/>`.

BrandSidebarItem (intern, kein eigener Export): `<a>` mit padding 8px 12px, borderRadius=`var(--g-r-3)`,
- active: bg=`rgba(196,90,42,0.10)`, color=`var(--g-accent-deep)`, fontWeight=600
- inactive: bg=transparent, color=`var(--g-ink-2)`, fontWeight=500
- Badge-Count: `var(--g-font-mono)` 10px, borderRadius=`var(--g-r-pill)`, active: bg=`rgba(196,90,42,0.12)` / inactive: bg=`rgba(26,26,24,0.05)`.

BrandSidebarIcon (intern, 4 Lucide-artige Inline-SVGs, byte-genau aus brand-kit.jsx):
```
home:    <svg viewBox="0 0 24 24"><path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z"/></svg>
trip:    <svg viewBox="0 0 24 24"><path d="M3 19l5-9 4 6 4-3 5 6"/><circle cx="8" cy="10" r="1.2"/><circle cx="16" cy="13" r="1.2"/></svg>
compare: <svg viewBox="0 0 24 24"><path d="M5 8h7M5 12h5M5 16h7M14 8l4-3v14l-4-3"/></svg>
archive: <svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="4" rx="1"/><path d="M5 9v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9M10 13h4"/></svg>
```
Farbe: active → `var(--g-accent)`, inactive → `var(--g-ink-3)`. Kein Lucide-Import.

### 6. `BrandShell.svelte`

Props:
```typescript
interface Props {
  active?: string;
  counts?: Record<string, number>;
  user?: { name?: string; sub?: string; accent?: boolean };
  onNavigate?: (id: string) => void;
  children?: import('svelte').Snippet;
}
```

Aufbau: flex-row, width/height=100%, bg=`var(--g-paper)`, overflow=hidden.
Linke Seite: `<BrandSidebar {active} {counts} {user} {onNavigate}/>`.
Rechte Seite: `<main style="flex:1; min-width:0; height:100%; overflow:auto">{@render children?.()}</main>`.

### 7. Barrel `frontend/src/lib/brand/index.ts`

```typescript
export { default as BrandIcon }       from './BrandIcon.svelte';
export { default as BrandIconSquare } from './BrandIconSquare.svelte';
export { default as BrandWordmark }   from './BrandWordmark.svelte';
export { default as BrandUserBadge }  from './BrandUserBadge.svelte';
export { default as BrandSidebar }    from './BrandSidebar.svelte';
export { default as BrandShell }      from './BrandShell.svelte';
// Alias fuer Migration (Bestandscode kann WordmarkBrand nutzen)
export { default as WordmarkBrand }   from './BrandWordmark.svelte';
```

### 8. Backward-Compat: `Wordmark.svelte` → Thin-Wrapper

`frontend/src/lib/components/ui/wordmark/Wordmark.svelte` wird vollstaendig ersetzt durch einen Thin-Wrapper. Bestehende Props `size` und `href` bleiben; Link-Verhalten und aria-label werden HIER bewahrt (BrandWordmark selbst hat kein href):

```svelte
<script lang="ts">
  import BrandWordmark from '$lib/brand/BrandWordmark.svelte';
  interface Props { size?: 'sm' | 'md' | 'lg'; href?: string; }
  let { size = 'md', href = '/' }: Props = $props();
</script>

<a {href} aria-label="Gregor Zwanzig — Home" style="text-decoration:none;display:inline-block">
  <BrandWordmark {size} icon="left" />
</a>
```

Die 4 bestehenden Default-Imports (Sidebar.svelte:56, TopAppBar.svelte:34, login/+page.svelte:13, _design/+page.svelte:194-196) werden NICHT geaendert — sie erben den Glyph automatisch.

### 9. Test-Update: `frontend/e2e/issue-293-wordmark.spec.ts`

Aenderungen am bestehenden E2E-Test (KEINE neuen Tests erstellen, bestehende reparieren):
- Caption-Assertions von lowercase `"v0.20 · wetter-briefing"` auf UPPERCASE `"V0.20 · WETTER-BRIEFING"` (text-transform: uppercase in BrandWordmark).
- `data-testid="brand-icon"` muss innerhalb von `data-testid="brand-wordmark"` sichtbar sein (Sidebar + Login).
- Selektor `a[aria-label="Gregor Zwanzig — Home"]` bleibt unveraendert (Wrapper behaelt ihn).
- Klick auf Wordmark navigiert zu `/` — Assertion bleibt.
- Alte CSS-Klassen-Selektoren `.wordmark__zwanzig` / `.wordmark__dot` entfernen (Svelte scoped, nicht stabil in E2E).

### LoC-Budget

| Kategorie | Dateien | Schaetzung |
|-----------|---------|-----------|
| Neu `lib/brand/` | 6 Svelte-Dateien | ~370 LoC |
| Neu Barrel | `index.ts` | ~10 LoC |
| Umbau | `Wordmark.svelte` → Thin-Wrapper | ~20 LoC (netto: Reduktion) |
| Test-Update | `issue-293-wordmark.spec.ts` | ~40 LoC |
| **Summe** | **~9 Dateien** | **~440 LoC** |

**LoC-Limit-Override erforderlich:** `workflow.py set-field loc_limit_override 500` vor Implementierungsbeginn setzen.

## Expected Behavior

- **Input:** Props je Komponente (size, color, accent, dark, icon, caption, active, counts etc.) — alle mit sinnvollen Defaults, kein Pflicht-Prop.
- **Output:** Gerenderte SVG-Glyphen und typografische Lockup-Elemente als SSR-sichere Svelte-5-Komponenten. Sidebar/TopAppBar/Login zeigen nach Migration automatisch den Berg+Blitz-Glyph neben dem Wordmark.
- **Side effects:** Kein API-Aufruf, kein lokalem State der App beeinflusst. Thin-Wrapper bewahrt Link-Navigation zu `/`. E2E-Test issue-293-wordmark.spec.ts muss nach dem Update gruen sein.

## Acceptance Criteria

**AC-1:** Given `BrandWordmark` mit `icon="left"` (Default) in einem beliebigen Kontext / When die Komponente gerendert wird / Then ist `data-testid="brand-wordmark"` im DOM vorhanden, ein Kind-Element mit `data-testid="brand-icon"` ist sichtbar, und der Text-Bereich zeigt lowercase `gregor.zwanzig` in `var(--g-font-mono)` mit Akzent-orangem "zwanzig".
  - Test: (populated after /tdd-red)

**AC-2:** Given `BrandIcon.svelte` in jeder beliebigen Groesse / When der SVG-Quelltext der Komponente inspiziert wird / Then enthalten die path-`d`-Attribute byte-genau `M48 11 L41 23 L45 23 L43 29 L50 17 L46 17 Z` (Blitz) und `M3 54 L18 22 L29 38 L38 26 L52 50 L61 54 Z` (Bergkamm) — keine andere Geometrie.
  - Test: (populated after /tdd-red)

**AC-3:** Given `BrandWordmark` mit `icon="only"` / When die Komponente gerendert wird / Then ist ausschliesslich `data-testid="brand-icon"` im DOM, kein Text-Node mit "gregor" oder "zwanzig", kein Caption-Element.
  - Test: (populated after /tdd-red)

**AC-4:** Given `BrandWordmark` mit `icon="none"` / When die Komponente gerendert wird / Then ist kein `data-testid="brand-icon"` im DOM; mit `caption={null}` ist ausserdem kein Caption-Element vorhanden und kein leerer Whitespace-Node unterhalb des Typo-Blocks.
  - Test: (populated after /tdd-red)

**AC-5:** Given die Desktop-Sidebar auf Viewport >= 900px / When eine beliebige App-Route geladen wird / Then ist `data-testid="brand-icon"` im DOM sichtbar (Glyph erscheint, Issue #279 erledigt), und der Link `a[aria-label="Gregor Zwanzig — Home"]` navigiert bei Klick zu `/`.
  - Test: (populated after /tdd-red)

**AC-6:** Given der bestehende Import `import Wordmark from '$lib/components/ui/wordmark/Wordmark.svelte'` in Sidebar, TopAppBar, Login und _design / When dieser Import unveraendert verwendet wird / Then rendert er `BrandWordmark icon="left"` mit dem Berg+Blitz-Glyph — kein Compile-Fehler, keine Laufzeit-Ausnahme.
  - Test: (populated after /tdd-red)

**AC-7:** Given `BrandWordmark` mit `dark={true}` / When die Komponente gerendert wird / Then verwendet der Haupt-Text-Span `var(--g-paper)` als Farbe, der Punkt `rgba(246,244,238,0.45)` und die Caption `rgba(246,244,238,0.55)` — nicht die hellen Ink-Werte.
  - Test: (populated after /tdd-red)

**AC-8:** Given `BrandWordmark` mit einem unbekannten `size`-Wert (z. B. `size="xl"`) oder einem unbekannten `icon`-Wert (z. B. `icon="bottom"`) / When die Komponente gerendert wird / Then faellt sie auf `size="md"` bzw. `icon="left"` zurueck und wirft keinen Laufzeit-Fehler.
  - Test: (populated after /tdd-red)

**AC-9:** Given alle 6 Brand-Komponenten und der Thin-Wrapper in einer SvelteKit-Seite mit aktiviertem SSR / When die Seite serverseitig gerendert wird / Then enthaelt das initiale HTML den SVG-Glyph ohne JavaScript-Fehler (kein `window`-Zugriff ohne `browser`-Guard).
  - Test: (populated after /tdd-red)

**AC-10:** Given der E2E-Test `frontend/e2e/issue-293-wordmark.spec.ts` nach den in dieser Spec beschriebenen Anpassungen / When `npx playwright test issue-293-wordmark` ausgefuehrt wird / Then sind alle Assertions gruen — insbesondere Caption in UPPERCASE, `data-testid="brand-icon"` sichtbar in Sidebar und Login, Link navigiert zu `/`.
  - Test: (populated after /tdd-red)

## Known Limitations

- `BrandSidebar` und `BrandShell` werden in #370 nur als Library-Bausteine angelegt. Die produktive `frontend/src/lib/components/ui/sidebar/Sidebar.svelte` wird in #370 **nicht** auf `BrandSidebar` umgebaut — das ist Migrations-Schritt 3 aus `body-15` und ein eigenes Issue.
- Die Showcase-Route `/_design-system` (#374) ist nicht Teil von #370. BrandSidebar und BrandShell sind nach #370 vorhanden, aber nicht in einem offiziellen Showcase sichtbar.
- Das LoC-Budget von 250 wird durch die Anlage der 6 Komponenten inhaerent ueberschritten (~440 LoC). `loc_limit_override 500` muss vor Implementierungsbeginn gesetzt werden.
- `--g-font-mono` und `--g-ink-4` fehlen aktuell in `app.css` — sie werden durch #369 (Token-Bridge) geliefert. Wird #370 vor #369 gemergt, rendert BrandWordmark mit falscher Font und Punktfarbe. Reihenfolge: #369 → #370.
- Atoms (#371), Molecules (#372), Mobile (#373) und Showcase (#374) sind abhaengige Folge-Issues die auf `lib/brand/` als unterste Schicht aufbauen.

## Changelog

- 2026-05-25: Initial spec erstellt (Issue #370 — Brand-Bibliothek `lib/brand/`, Teil von Epic #368 Atomic-Design-Migration).
