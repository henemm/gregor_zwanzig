---
entity_id: bug_272_ios_input_font_size
type: bugfix
created: 2026-05-20
updated: 2026-05-20
status: completed
version: "1.0"
tags: [bugfix, ios, safari, mobile, font-size, zoom, tailwind, frontend, issue-272]
---

<!-- Issue #272 — Bug: Eingabefelder – Font-Size < 16 px löst iOS-Auto-Zoom aus -->

# Issue #272 — Bug-Fix: iOS-Auto-Zoom bei Eingabefeldern mit font-size < 16 px verhindern

## Approval

- [x] Approved (2026-05-20)

## Zweck

iOS Safari zoomt die Seite automatisch ein, sobald ein Eingabeelement (`<input>`, `<select>`, `<textarea>`) fokussiert wird, das eine `font-size` unter 16 px hat. Zahlreiche Seiten und Komponenten im Frontend nutzen Tailwind-Klassen `text-sm` (13 px) oder `text-xs` (11 px) direkt auf Raw-Elementen ohne responsiven Modifier, was auf iPhone-Viewports zu unerwünschtem Zoom und schlechter UX führt. Der Fix setzt per globaler unlayered Media Query alle Eingabefelder auf exakt 16 px bei Viewports ≤ 767 px — Desktop bleibt bei `text-sm`.

Die Komponente `input.svelte` macht es bereits korrekt mit `text-base md:text-sm`. Der `SavePresetDialog.svelte` benötigt einen zusätzlichen Scoped-Override, weil sein Scoped CSS eine höhere Spezifität (0-1-1) als globale Regeln (0-0-1) hat.

## Quelle / Source

**Geänderte Dateien:**
- `frontend/src/app.css` — unlayered `@media (max-width: 767px)`-Regel am Ende der Datei (nach allen `@layer`-Blöcken) setzt `input, select, textarea { font-size: 16px }`
- `frontend/src/lib/components/trip-detail/SavePresetDialog.svelte` — bestehender `<style>`-Block um Scoped `@media (max-width: 767px) { .field textarea { font-size: 16px } }` ergänzen

**NICHT ändern:**
- `frontend/src/lib/components/ui/input/input.svelte` — nutzt bereits `text-base md:text-sm` (korrekt)
- Alle übrigen Komponenten und Seiten mit Raw-`<select>`/`<input>`/`<textarea>` — werden durch die globale Regel in `app.css` abgedeckt

> **Schicht-Hinweis:** Alle Änderungen liegen ausschließlich im Frontend-Layer (`frontend/src/`). Kein Go-API-Code, kein Python-Backend-Code betroffen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/app.css` | CSS-Datei | Single Source of Truth für globale Styles; unlayered Regeln gewinnen über `@layer`-Blocks ohne `!important` (Tailwind v4) |
| `frontend/src/lib/components/trip-detail/SavePresetDialog.svelte` | Svelte-Komponente | Scoped CSS `.field textarea { font-size: 0.875rem }` hat Spezifität 0-1-1 → übersteuert globale Regel; braucht eigenen Mobile-Override |
| Tailwind v4 (`@import "tailwindcss"`) | CSS-Framework | Unlayered Regeln in `app.css` gewinnen automatisch über alle `@layer utilities`-Definitionen — kein `!important` notwendig |

## Implementation Details

### 1. `frontend/src/app.css` — unlayered Media Query anhängen

Die Regel wird **nach** dem letzten schließenden `}` aller `@layer`-Blöcke eingefügt (aktuell Zeile ~332), damit sie als unlayered CSS automatisch eine höhere Priorität als alle Tailwind-Layer-Regeln besitzt:

```css
@media (max-width: 767px) {
  input, select, textarea {
    font-size: 16px;
  }
}
```

Dieser Selector greift auf alle Raw-HTML-Elemente dieser Typen in der gesamten Anwendung — ohne Ausnahme bei Desktop-Breakpoints (≥ 768 px), da die Regel nur unterhalb 767 px aktiv ist.

### 2. `frontend/src/lib/components/trip-detail/SavePresetDialog.svelte` — Scoped Override

Im bestehenden `<style>`-Block (ab Zeile ~163) am Ende folgende Regel ergänzen:

```css
@media (max-width: 767px) {
  .field textarea {
    font-size: 16px;
  }
}
```

Die Spezifität dieser Scoped-Regel (0-1-1 durch `.field textarea`) ist identisch mit der bestehenden Regel `{ font-size: 0.875rem }` — bei gleicher Spezifität gewinnt die spätere Deklaration im Stylesheet, daher muss die Mobile-Override-Regel nach der bestehenden `font-size`-Regel stehen.

### 3. LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `frontend/src/app.css` | +4 | nein (Frontend-Asset) |
| `frontend/src/lib/components/trip-detail/SavePresetDialog.svelte` | +4 | nein (Frontend-Asset) |
| **Gesamt (zählend)** | **0** | **< 250 LoC-Limit** |

## Expected Behavior

- **Input:** Kein Laufzeit-Input — reine CSS-Änderungen
- **Output:** Alle `<input>`, `<select>` und `<textarea>`-Elemente haben auf Viewports ≤ 767 px eine `font-size` von mindestens 16 px; auf ≥ 768 px bleibt `text-sm` (13 px) unverändert
- **Side effects:** Keine Laufzeit-Seiteneffekte. Die Schriftgröße auf Mobile ist geringfügig größer als bisher (16 px statt 13 px), was im Wireframe der mobilen Nutzung entspricht. Desktop-Layout ist nicht betroffen.

## Acceptance Criteria

- **AC-1:** Given iOS Safari auf einem 375px-Viewport, When ich ein `<select>`-Element in der Briefings-Sektion fokussiere, Then zoomt die Seite NICHT automatisch ein
  - Test: (populated after /tdd-red)

- **AC-2:** Given iOS Safari auf einem 390px-Viewport, When ich ein `<input>` auf der Login-Seite fokussiere, Then zoomt die Seite NICHT automatisch ein
  - Test: (populated after /tdd-red)

- **AC-3:** Given Desktop-Browser bei 900px+, When ich ein Formularfeld fokussiere, Then bleibt die Font-Size bei `text-sm` (13 px) — kein visueller Unterschied zum Ist-Zustand
  - Test: (populated after /tdd-red)

- **AC-4:** Given die `SavePresetDialog`-Textarea auf einem 375px-Viewport, When sie fokussiert wird, Then zoomt die Seite NICHT automatisch ein
  - Test: (populated after /tdd-red)

- **AC-5:** Given ein neu erstelltes `<select>`-Element in einer künftigen Komponente mit Tailwind `text-sm`, When es auf Mobile fokussiert wird, Then greift die globale Regel in `app.css` und verhindert den Zoom — ohne Einzeländerung an der Komponente
  - Test: (populated after /tdd-red)

## Known Limitations

- **Kein automatisierter iOS-Zoom-Test möglich:** iOS-Safari-spezifisches Zoom-Verhalten lässt sich mit Playwright/jsdom nicht zuverlässig nachbilden. Die ACs sind als manuelle Browser-Tests auf echtem iOS-Gerät oder Xcode-Simulator zu verifizieren. CSS-Struktur-Tests (Datei-Inhalt-Prüfung) können die Regel-Existenz automatisiert bestätigen.
- **Breakpoint 767 px statt 768 px:** Tailwinds `md`-Breakpoint ist `≥ 768 px`. Die Media Query verwendet `max-width: 767px` (entspricht `< 768 px`) — damit greift sie exakt bei allen Viewports, die Tailwind als mobile einstuft.
- **`input.svelte`-Wrapper nicht betroffen:** Die Wrapper-Komponente nutzt bereits `text-base md:text-sm` und ist damit auf iOS korrekt. Die globale Regel schadet ihr nicht — `text-base` (16 px) entspricht ohnehin dem gesetzten Minimum.

## Out of Scope

- Änderungen an `input.svelte` — bereits korrekt
- Einzelne Klassen-Overrides pro Komponente — die globale Regel übernimmt das
- SMS-/E-Mail-Templates — betrifft nur das SvelteKit-Frontend
- Backend-Änderungen jeglicher Art

## Changelog

- 2026-05-26: Bug #382 behebt latente Regression bei Select.svelte (14 Einsatzorte triggern iOS-Zoom, weil Komponenten-CSS höhere Spezifität als globaler Guard hat). Pattern: scoped @media in Select.svelte wie in SavePresetDialog.
- 2026-05-20: Initial spec erstellt. Behebt iOS-Auto-Zoom durch zwei CSS-Ergänzungen: globale unlayered Media Query in app.css + Scoped Override in SavePresetDialog.svelte. 2 Dateien, ~8 LoC.
