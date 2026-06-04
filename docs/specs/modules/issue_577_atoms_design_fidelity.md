# Spec: Issue #577 — Atoms 1:1 nach atoms.jsx (Design-Fidelity Rework)

**Issue:** #577
**Workflow:** issue-577-atoms-neuimplementierung
**Typ:** Rework / Design-Compliance
**Upstream:** #576 (Tokens-Sync, bereits abgeschlossen)
**Downstream:** #578 (Molecules), #579–#588 (Screens)

---

## Überblick

Die Svelte-Atom-Implementierungen wurden **nicht** 1:1 aus `atoms.jsx` gebaut.
Sie verwenden einen CSS-Klassen-Ansatz (`data-slot` + `app.css`), der in fünf
Punkten von der Handoff-Vorlage abweicht. Dieses Issue korrigiert alle
Divergenzen, ohne das restliche Design zu verändern.

**Kanonische Quelle:**
`claude-code-handoff/handoff-2026-06-04-v3/claude-code-handoff/current/jsx/atoms.jsx`

---

## Betroffene Änderungen

### 1 · WIcon — Lucide → Custom Inline-SVG (KRITISCH)

**IST:** `WIcon.svelte` importiert Lucide-Icons (`Sun`, `Cloud`, `CloudRain`,
`CloudLightning`, `CloudSnow`, `Wind`, `Moon`, `Flashlight`).

**SOLL (atoms.jsx):** 8 eigene Inline-SVG-Pfade, alle `viewBox="0 0 24 24"`,
`fill="none"`, `stroke={color}`, `strokeWidth="1.5"`.

| kind | SVG-Inhalt |
|---|---|
| `sun` | `strokeLinecap="round"` · `<circle cx="12" cy="12" r="3.5"/>` · `<path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M5.6 18.4l1.4-1.4M17 7l1.4-1.4"/>` |
| `cloud` | `strokeLinejoin="round"` · `<path d="M7 17h10a4 4 0 0 0 0.5-7.97A6 6 0 0 0 6.1 11 4 4 0 0 0 7 17z"/>` |
| `rain` | `strokeLinecap="round" strokeLinejoin="round"` · Cloud-Pfad (y=14/8) · `<path d="M9 17l-1 3M13 17l-1 3M17 17l-1 3"/>` |
| `thunder` | `strokeLinecap="round" strokeLinejoin="round"` · Cloud-Pfad (y=14/8) · `<path d="M12 14l-2 4h3l-2 4"/>` |
| `snow` | `strokeLinecap="round"` · `<path d="M12 3v18M5 7l14 10M5 17l14-10"/>` |
| `wind` | `strokeLinecap="round"` · `<path d="M3 8h11a3 3 0 1 0-3-3M3 12h16a3 3 0 1 1-3 3M3 16h9"/>` |
| `moon` | `strokeLinejoin="round"` · `<path d="M20 14a8 8 0 1 1-10-10 6 6 0 0 0 10 10z"/>` |
| `headlamp` | `strokeLinejoin="round" strokeLinecap="round"` · `<rect x="7" y="9" width="10" height="6" rx="1.5"/>` · `<path d="M17 12l4-1.5v3L17 12zM9 9V7a3 3 0 0 1 6 0v2"/>` |

Default `color` im JSX ist `"var(--g-ink-2)"` — der Svelte-Default bleibt
`currentColor` (weil Svelte-Konsumenten color als Prop setzen oder via CSS
erben). Wer `color` nicht übergibt, bekommt `currentColor`.

Lucide-Imports werden vollständig entfernt.

---

### 2 · Pill — Farb-Tints + Typografie (KRITISCH)

**IST (`app.css`):**
- Ton-Farben sind opake Semantic-Tokens (`var(--g-success)`, `var(--g-warning)`, etc.)
- Keine Mono-Schrift, kein `letter-spacing`, kein `uppercase` in den Basis-Regeln
- Tone-Keys: `default`, `success`, `warning`, `danger`, `info`, `accent`, `ghost`

**SOLL (atoms.jsx):**
- Semi-transparente Hintergründe (kein opakes Grün / Rot)
- `font-family: var(--g-font-mono)`, `letter-spacing: 0.04em`, `text-transform: uppercase`, `font-size: 11px`
- Tone-Keys: `neutral`, `accent`, `good`, `warn`, `bad`, `ghost`

**Neue Tone-Werte:**

| Ton | background | color |
|---|---|---|
| `neutral` | `rgba(26,26,24,0.06)` | `var(--g-ink-2)` |
| `accent` | `var(--g-accent-tint)` | `var(--g-accent-deep)` |
| `good` | `rgba(61,107,58,0.10)` | `var(--g-good)` |
| `warn` | `rgba(192,138,26,0.12)` | `var(--g-warn-deep)` ¹ |
| `bad` | `rgba(168,50,50,0.10)` | `var(--g-bad)` |
| `ghost` | `transparent` | `var(--g-ink-3)`, `border: 1px solid var(--g-rule)` |

¹ Das JSX verwendet den rohen Hex `#8a6210` (dunkleres Amber). Da rohes Hex
verboten ist, wird ein neues Token `--g-warn-deep: #8a6210` in `app.css` unter
den semantischen Farben (Zeile ~29) ergänzt.

**Anpassungen in `app.css`:**
- Basis `[data-slot="pill"]`: `font-family` auf `var(--g-font-mono)` ändern,
  `font-size` auf `11px`, `letter-spacing` auf `0.04em`, `text-transform` auf
  `uppercase` hinzufügen
- Vorhandene Tone-Rules durch neue Tones ersetzen (Mapping-Tabelle oben)
- Bestehende Nicht-atoms.jsx-Tones (`success`, `warning`, `danger`, `info`) als
  Legacy-Aliases **behalten** (andere Komponenten nutzen sie möglicherweise —
  kein Breaking Change)

---

### 3 · QuickAction — ASCII-Glyphen → Inline-SVG (KRITISCH)

**IST (`QuickAction.svelte`):** Funktion `quickActionGlyph()` gibt ASCII-Strings
zurück (`->`, `##`, `>>`, `[]`, `/!`, `||`).

**SOLL (molecules.jsx `QuickActionGlyph`):** Pro `glyph`-Kind ein eigenes
Inline-SVG, `viewBox="0 0 24 24"`, `fill="none"`, `stroke`, `strokeWidth="1.5"`,
`strokeLinecap="round"`, `strokeLinejoin="round"`.

| glyph | SVG-Pfad(e) |
|---|---|
| `pause` | `<rect x="7" y="5" width="3.4" height="14" rx="1"/>` · `<rect x="13.6" y="5" width="3.4" height="14" rx="1"/>` |
| `metrics` | `<path d="M4 8h10M18 8h2M4 16h2M10 16h10"/>` · `<circle cx="16" cy="8" r="2.2"/>` · `<circle cx="8" cy="16" r="2.2"/>` |
| `clock` | `<circle cx="12" cy="12" r="8.5"/>` · `<path d="M12 7.5V12l3 2"/>` |
| `bell` | `<path d="M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6z"/>` · `<path d="M10 19a2 2 0 0 0 4 0"/>` |
| `send` | `<path d="M21 4L3 11l6 2.5L11.5 20 21 4z"/>` · `<path d="M9 13.5L21 4"/>` |
| `eye` | `<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/>` · `<circle cx="12" cy="12" r="2.6"/>` |
| `route` (default) | `<circle cx="6" cy="6" r="2.2"/>` · `<circle cx="18" cy="18" r="2.2"/>` · `<path d="M6 8.5v3a4 4 0 0 0 4 4h0a4 4 0 0 1 4-4 4 4 0 0 0 4-4"/>` |

SVG-Größe: `19×19` (md) / `21×21` (lg), entsprechend `size`-Prop.
SVG-Farbe: `isAccent ? "var(--g-accent-deep)" : "var(--g-ink)"`.

Die `quickActionGlyph()` Hilfsfunktion und der `symbol`-Span werden entfernt.
Stattdessen rendert ein neues `QuickActionGlyph`-Snippet (oder inline `{#if}`)
das SVG direkt.

---

### 4 · Eyebrow — Typografie-Korrektur

**IST (`app.css` Zeile 426–434):**
```css
font-size: 0.625rem;  /* =10px */
font-weight: 400;
letter-spacing: 0.1em;
color: var(--g-ink-muted);
```

**SOLL (atoms.jsx Zeile 52–53):**
```
fontSize: 11          /* =11px */
fontWeight: 500
letterSpacing: "var(--g-track-caps)"   /* =0.12em laut tokens */
color: var(--g-ink-3)                  /* default; PO-Scope: Farbe bleibt ink-muted */
```

Korrekturen in `app.css`:
- `font-size: 0.625rem` → `font-size: 11px` (entspricht `var(--g-text-xs)`)
- `font-weight: 400` → `font-weight: 500`
- `letter-spacing: 0.1em` → `letter-spacing: var(--g-track-caps)` (0.12em)

Die `color` bleibt `var(--g-ink-muted)` (PO-bestätigt im Issue-Scope — keine
Kontraständerung hier).

---

### 5 · Btn ghost + Card — Border-Korrektur

**Btn ghost IST:** `border-color: transparent`

**SOLL (atoms.jsx Zeile 137):** `border: "1px solid var(--g-rule)"`

Korrektur in `app.css`:
```css
[data-slot="btn"][data-variant="ghost"] {
  border-color: var(--g-rule);   /* war: transparent */
}
```

**Card IST (`Card.svelte`):**
- `style:border-left` nur bei non-accent → 1px solid var(--g-rule), kein top/right/bottom
- `style:overflow="hidden"` gesetzt

**SOLL (atoms.jsx Zeile 84–89):**
```js
border: "1px solid var(--g-rule)",                           /* alle 4 Seiten */
borderLeft: accent ? "3px solid var(--g-accent)" : "1px solid var(--g-rule)"
/* kein overflow: hidden */
```

Korrekturen in `Card.svelte`:
- `style:border-left` → durch vollständige `style:border="1px solid var(--g-rule)"`
  ersetzen (gilt immer), Accent-Override bleibt additiv als `style:border-left`
- `style:overflow="hidden"` entfernen

---

## Nicht im Scope

- `ElevSparkline` — Defaults (`width=280`, `height=60`, `showArea=true`) stimmen
  bereits mit atoms.jsx überein; keine Änderung nötig
- `PageSection`, `PageTileGrid`, `Tile`, `PageEmpty` — nicht in atoms.jsx
- `BrandWordmark` / `BrandIcon` — bereits korrekt implementiert
- `color`-Default von WIcon (`currentColor` vs. `var(--g-ink-2)`) — bewusste
  Abweichung zugunsten CSS-Vererbung; kein API-Breaking-Change

---

## Betroffene Dateien

| Datei | Änderung |
|---|---|
| `frontend/src/lib/components/ui/wicon/WIcon.svelte` | Lucide-Imports entfernen, 8 Inline-SVG-Cases |
| `frontend/src/app.css` | Pill-Typografie + Tone-Farben, Eyebrow-Typografie, Btn-ghost-Border, `--g-warn-deep` Token |
| `frontend/src/lib/components/atoms/Card.svelte` | Vollständiger 4-seitiger Border, `overflow:hidden` entfernen |
| `frontend/src/lib/components/molecules/QuickAction.svelte` | ASCII-Glyphen → Inline-SVG |

**Geschätzter Scope:** ~120 LoC netto · 4 Dateien · Aufwand: medium

---

## Acceptance Criteria

**AC-1:** Given `WIcon` mit `kind="sun"` / `kind="headlamp"` /
`kind="thunder"` / `kind="snow"`, When die Komponente gerendert wird, Then
enthält der DOM ein `<svg>`-Element mit dem exakten `d`-Attribut aus atoms.jsx
— kein Lucide-Import mehr in `WIcon.svelte`.

**AC-2:** Given `[data-slot="pill"][data-tone="good"]`, When ein Pill-Element
im Browser dargestellt wird, Then hat der Hintergrund den Wert
`rgba(61,107,58,0.10)` und die Schriftfarbe `var(--g-good)` — kein opakes
Grün, Mono-Font, Uppercase-Text.

**AC-3:** Given `[data-slot="pill"][data-tone="warn"]`, When ein Pill-Element
gerendert wird, Then hat der Hintergrund `rgba(192,138,26,0.12)` und die
Textfarbe den Wert von `--g-warn-deep` (`#8a6210`).

**AC-4:** Given `[data-slot="pill"]` (Basis-Regel), When der Computed Style
ausgelesen wird, Then gelten: `font-family = var(--g-font-mono)`,
`letter-spacing = 0.04em`, `text-transform = uppercase`, `font-size = 11px`.

**AC-5:** Given `[data-slot="eyebrow"]`, When der Computed Style ausgelesen
wird, Then gelten: `font-size = 11px`, `font-weight = 500`,
`letter-spacing = var(--g-track-caps)` (0.12em).

**AC-6:** Given `[data-slot="btn"][data-variant="ghost"]`, When der Computed
Style ausgelesen wird, Then gilt `border-color = var(--g-rule)` (nicht
`transparent`).

**AC-7:** Given `<Card accent={false}>`, When das Element im DOM betrachtet
wird, Then hat es `border: 1px solid var(--g-rule)` auf allen 4 Seiten und
kein `overflow: hidden`.

**AC-8:** Given `<Card accent={true}>`, When das Element im DOM betrachtet
wird, Then hat die linke Seite `border-left: 3px solid var(--g-accent)` und
die anderen 3 Seiten `1px solid var(--g-rule)`.

**AC-9:** Given `<QuickAction glyph="route" ...>`, When die Komponente
gerendert wird, Then enthält der Glyph-Tile ein `<svg>`-Element (kein
Text-Span mit ASCII) mit dem route-Pfad aus molecules.jsx.

**AC-10:** Given `<QuickAction glyph="metrics" ...>` und
`<QuickAction glyph="clock" ...>` und `<QuickAction glyph="bell" ...>`, When
jede Komponente gerendert wird, Then enthält jeder Glyph-Tile das korrekte
Inline-SVG aus molecules.jsx (kein doppelter `>>` für clock und send).

**AC-11:** Given alle 4 geänderten Dateien, When `cd frontend && npm run
build` ausgeführt wird, Then Exit-Code 0, kein TypeScript-Fehler, kein
fehlender Import.

---

## Nicht-Ziele (explizit)

- Keine Änderung an Komponenten, die `<WIcon>` konsumieren (sie übergeben
  `kind` bereits als Prop)
- Keine Änderung an bestehenden Legacy-Pill-Tones (`success`, `warning`,
  `danger`, `info`) — diese bleiben als Aliases erhalten
- Kein Refactoring der `data-slot`-Architektur auf reines Inline-Style

## Changelog

- 2026-06-04: Spec erstellt (Workflow issue-577-atoms-neuimplementierung)
