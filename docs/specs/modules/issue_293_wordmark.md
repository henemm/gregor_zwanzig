---
entity_id: issue_293_wordmark
type: module
created: 2026-05-20
updated: 2026-05-20
status: draft
version: "1.0"
tags: [frontend, design-system, ui-component, branding, typography, svelte, issue-293]
---

# Issue #293 — Sidebar: Wordmark "gregor.zwanzig" mit Mono-Akzent

## Approval

- [ ] Approved

## Purpose

Die Applikation zeigt bisher an mehreren Stellen den Klartextstring "Gregor 20" als einfaches Textelement ohne Markenbezug. Dieses Modul ersetzt alle diese Vorkommen durch eine wiederverwendbare `<Wordmark />`-Svelte-Komponente, die den Produktnamen typografisch mit JetBrains Mono darstellt: "gregor" in Ink-Farbe, ein Punkt in `--g-ink-faint`, "zwanzig" in `--g-accent` (Burnt Orange), und darunter eine Untertitel-Zeile "v0.20 · wetter-briefing" in versalisierten, weitgesperrten Mono-Lettern.

> **Schicht-Hinweis:** Alle Änderungen liegen ausschließlich im Frontend-Layer (`frontend/src/`). Kein Go-API-Code, kein Python-Backend-Code ist betroffen.

## Source

- **Files:**
  - `frontend/src/lib/components/ui/wordmark/Wordmark.svelte` (NEU)
  - `frontend/src/lib/components/ui/sidebar/Sidebar.svelte` (geändert, Z. 55)
  - `frontend/src/lib/components/ui/sidebar/TopAppBar.svelte` (geändert, Z. 33)
  - `frontend/src/app.html` (geändert — `<title>` ergänzen)
  - `frontend/src/routes/login/+page.svelte` (geändert, Z. 12)
  - `frontend/src/routes/trips/[id]/+page.svelte` (geändert, Z. 20)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/app.css` | CSS-Datei (vorhanden) | Liefert alle verwendeten Design-Token: `--g-font-data` (JetBrains Mono), `--g-ink`, `--g-ink-faint`, `--g-accent` |
| `frontend/src/lib/components/ui/sidebar/Sidebar.svelte` | Svelte-Komponente (vorhanden) | Einbindungsort auf Desktop (Size `md`) |
| `frontend/src/lib/components/ui/sidebar/TopAppBar.svelte` | Svelte-Komponente (vorhanden) | Einbindungsort auf Mobile (Size `sm`, ohne Untertitel) |
| `frontend/src/routes/login/+page.svelte` | SvelteKit-Route (vorhanden) | Ersetzt `<h1>Gregor 20</h1>` durch `<Wordmark size="lg" href="/" />` |
| `frontend/src/routes/trips/[id]/+page.svelte` | SvelteKit-Route (vorhanden) | Titelanpassung von "Gregor 20" → "Gregor Zwanzig" im `<title>`-Tag |
| `frontend/src/app.html` | SvelteKit-App-Shell (vorhanden) | Erhält `<title>Gregor Zwanzig</title>`, da aktuell kein Title-Tag vorhanden |

## Implementation Details

### Token-Mapping (Mockup → app.css)

```
--g-font-mono  →  --g-font-data   (JetBrains Mono, bereits in app.css definiert)
--g-ink-4      →  --g-ink-faint   (#9a958a)
--g-ink        →  --g-ink         (#1a1a18, unverändert)
--g-accent     →  --g-accent      (#c45a2a, unverändert)
```

### 1. `Wordmark.svelte` (NEU)

Props:
```typescript
interface Props {
  size?: 'sm' | 'md' | 'lg';  // default: 'md'
  href?: string;               // default: '/'
}
let { size = 'md', href = '/' }: Props = $props();
```

Größen-Mapping:
```
sm:  14px Schriftgröße, Untertitel ausgeblendet  → kompakt für TopAppBar
md:  18px Schriftgröße, Untertitel sichtbar      → Desktop-Sidebar
lg:  24px Schriftgröße, Untertitel sichtbar      → Login-Seite
```

Komponentenstruktur:
```svelte
<a {href} aria-label="Gregor Zwanzig — Home" class="wordmark wordmark--{size}">
  <div class="wordmark__row">
    <span class="wordmark__gregor">gregor</span>
    <span class="wordmark__dot">.</span>
    <span class="wordmark__zwanzig">zwanzig</span>
  </div>
  {#if size !== 'sm'}
    <div class="wordmark__subtitle">v0.20 · wetter-briefing</div>
  {/if}
</a>
```

CSS-Variablen im Scoped `<style>`-Block:
```css
.wordmark {
  display: inline-block;
  text-decoration: none;
}

.wordmark__row {
  font-family: var(--g-font-data);
  font-weight: 500;
  letter-spacing: 0.04em;
  color: var(--g-ink);
  display: flex;
  align-items: baseline;
  gap: 0;
}

.wordmark__dot   { color: var(--g-ink-faint); }
.wordmark__zwanzig { color: var(--g-accent); }

.wordmark__subtitle {
  font-family: var(--g-font-data);
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--g-ink-faint);
  margin-top: 3px;
}

/* Größen-Varianten */
.wordmark--sm .wordmark__row    { font-size: 14px; }

.wordmark--md .wordmark__row    { font-size: 18px; }
.wordmark--md .wordmark__subtitle { font-size: 9px; }

.wordmark--lg .wordmark__row    { font-size: 24px; }
.wordmark--lg .wordmark__subtitle { font-size: 10px; }
```

### 2. `Sidebar.svelte` — Änderung (Z. 55)

```diff
- <h1 class="mb-6 text-lg font-bold">Gregor 20</h1>
+ <div class="mb-6">
+   <Wordmark size="md" />
+ </div>
```

Import am Dateianfang ergänzen:
```svelte
import Wordmark from '$lib/components/ui/wordmark/Wordmark.svelte';
```

### 3. `TopAppBar.svelte` — Änderung (Z. 33)

```diff
- <span class="flex-1 text-sm font-bold">Gregor 20</span>
+ <span class="flex-1"><Wordmark size="sm" /></span>
```

Import ergänzen:
```svelte
import Wordmark from '$lib/components/ui/wordmark/Wordmark.svelte';
```

### 4. `app.html` — Title-Tag

```diff
- <head>
+ <head>
+   <title>Gregor Zwanzig</title>
```

(Sofern noch kein `<title>` vorhanden — vor dem Edit prüfen, ob `%sveltekit.head%` bereits einen Title injiziert.)

### 5. `login/+page.svelte` — Änderung (Z. 12)

```diff
- <h1 class="text-2xl font-bold">Gregor 20</h1>
+ <Wordmark size="lg" href="/" />
```

Import ergänzen:
```svelte
import Wordmark from '$lib/components/ui/wordmark/Wordmark.svelte';
```

### 6. `trips/[id]/+page.svelte` — Änderung (Z. 20)

```diff
- <title>{trip.name} — Gregor 20</title>
+ <title>{trip.name} — Gregor Zwanzig</title>
```

### LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `frontend/src/lib/components/ui/wordmark/Wordmark.svelte` | +55 (NEU) | ja |
| `frontend/src/lib/components/ui/sidebar/Sidebar.svelte` | +3 | ja |
| `frontend/src/lib/components/ui/sidebar/TopAppBar.svelte` | +3 | ja |
| `frontend/src/app.html` | +1 | ja |
| `frontend/src/routes/login/+page.svelte` | +2 | ja |
| `frontend/src/routes/trips/[id]/+page.svelte` | +1 | ja |
| **Gesamt** | **~65** | **< 250 LoC-Limit** |

## Expected Behavior

- **Input:** Keine externen Daten-Inputs; Props `size` und `href` steuern Darstellung und Link-Ziel
- **Output (visuell):**
  - Desktop-Sidebar: Wordmark in `md` — "gregor.zwanzig" (18px Mono) + Untertitel "v0.20 · wetter-briefing" (9px, versalisiert, weitgesperrt)
  - Mobile TopAppBar: Wordmark in `sm` — nur "gregor.zwanzig" (14px Mono), kein Untertitel
  - Login-Seite: Wordmark in `lg` — "gregor.zwanzig" (24px Mono) + Untertitel
  - "." in `--g-ink-faint` (#9a958a), "zwanzig" in `--g-accent` (#c45a2a), "gregor" in `--g-ink` (#1a1a18)
- **Side effects:** Klick auf Wordmark navigiert zur `href`-URL (Standard: `/`). Dokumenttitel zeigt "Gregor Zwanzig" statt "Gregor 20".

## Acceptance Criteria

**AC-1:** Given die Desktop-Sidebar auf einem Viewport ≥ 900px / When eine beliebige Route der App geladen wird / Then ist das Wordmark "gregor.zwanzig" mit Untertitel "v0.20 · wetter-briefing" sichtbar und der Punkt zwischen "gregor" und "zwanzig" hat die Farbe `--g-ink-faint` (#9a958a).
  - Test: (populated after /tdd-red)

**AC-2:** Given die Mobile TopAppBar auf einem Viewport < 900px / When eine beliebige Route der App geladen wird / Then ist das Wordmark "gregor.zwanzig" (14px) ohne Untertitel sichtbar — der Untertitel "v0.20 · wetter-briefing" ist nicht im DOM vorhanden.
  - Test: (populated after /tdd-red)

**AC-3:** Given das Wordmark in einem beliebigen Kontext / When der Farb-Token-Einsatz im CSS geprüft wird / Then verwendet "gregor" `var(--g-ink)`, "." `var(--g-ink-faint)` und "zwanzig" `var(--g-accent)` — keine Hex-Werte direkt im Scoped-CSS der Komponente.
  - Test: (populated after /tdd-red)

**AC-4:** Given das Wordmark auf einer beliebigen Seite / When der Nutzer darauf klickt / Then navigiert der Browser zur Route `/` (Startseite), weil das Wordmark als `<a href="/">` gerendert wird.
  - Test: (populated after /tdd-red)

**AC-5:** Given der Browser-Tab ohne aktive Route-Navigation / When eine beliebige Seite (außer Trip-Detail) geöffnet wird / Then lautet der Dokumenttitel "Gregor Zwanzig" und nicht mehr "Gregor 20".
  - Test: (populated after /tdd-red)

**AC-6:** Given die Login-Seite (`/login`) / When die Seite geladen wird / Then zeigt die Seite das Wordmark in Größe `lg` (24px) mit Untertitel anstelle des früheren `<h1>`-Elements mit Text "Gregor 20".
  - Test: (populated after /tdd-red)

**AC-7:** Given die Trip-Detail-Seite für einen Trip mit Name "GR20" / When die Seite geladen wird / Then lautet der Dokumenttitel "GR20 — Gregor Zwanzig" und nicht "GR20 — Gregor 20".
  - Test: (populated after /tdd-red)

**AC-8:** Given der Quelltext in `frontend/src/` / When `rg "Gregor 20"` auf alle `.svelte`- und `.html`-Dateien ausgeführt wird / Then ist die Trefferanzahl 0 — kein hartcodierter "Gregor 20"-String mehr im Frontend-Code.
  - Test: (populated after /tdd-red)

## Known Limitations

- `app.html` kann bereits via `%sveltekit.head%` einen dynamischen `<title>` injizieren — vor dem Edit prüfen, ob ein statischer `<title>` in `app.html` sinnvoll ist oder ob der Fallback-Wert in `+layout.svelte` gesetzt werden sollte. Beide Wege sind korrekt; der statische Weg in `app.html` wirkt nur so lange, bis SvelteKit den dynamischen Titel überschreibt.
- Die Wordmark enthält keinen `<img>`-Tag und kein SVG-Logo — bei einem zukünftigen Logozeichen-Bedarf muss die Komponente erweitert werden.
- AC-3 (Token-Prüfung) ist eine statische Code-Inspektion; ein automatisierter Playwright-Test prüft nur die gerenderte Farbe, nicht den Token-Namen im CSS.

## Changelog

- 2026-05-20: Initial spec erstellt (Issue #293 — Wordmark "gregor.zwanzig" mit Mono-Akzent, Variante B).
