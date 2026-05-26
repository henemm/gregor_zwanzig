---
entity_id: issue_389_trip_detail_atomic
type: module
created: 2026-05-26
updated: 2026-05-26
status: draft
version: "1.0"
tags: [design-system, atomic-design, frontend, trip-detail, pill, status-badge]
---

# Issue 389 — Trip-Detail Atomic Migration (Phase 2 von 6)

## Approval

- [x] Approved

## Purpose

`TripStatusBadge.svelte` rendert den Aktivstatus eines Trips aktuell als gefüllte grüne Pill (`tone: 'success'`). Laut Soll-flow7B und Issue #302 soll der Status `active` als Burnt-Orange `outlined`-Pill erscheinen — konsistent mit dem Brand-Akzent und dem übrigen Design-System. Diese Spec beschreibt den minimalen Atomic-Migration-Schritt für die Trip-Detail-Route: Tone-Korrektur auf `accent` und Umstieg auf den `outlined`-Stil.

Die Migration ist Teil von Epic #368 (Atomic-Design-Angleichung, Phase 2: Trip-Detail-Route). Die Änderungen sind ausschließlich kosmetisch — Logik, Datenfluss und Komponentenstruktur bleiben unverändert.

## Source

- **Layer:** Frontend / User-UI (`frontend/src/`)
- **Scope:** 2 Dateien, ~4 geänderte Zeilen, kein Logic-Code

| Datei | Änderungstyp |
|---|---|
| `frontend/src/lib/components/trip-detail/TripStatusBadge.svelte` | Tone-Map + outlined-Attribut |
| `frontend/src/app.css` | 1 neue CSS-Rule für `accent`-outlined-Text-Farbe |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/ui/pill/Pill.svelte` | Upstream-Atom | Rendert Status-Pill; nimmt `tone` und `data-outlined` entgegen |
| `frontend/src/app.css` | Upstream | Definiert alle `--g-*` Token und `[data-outlined]`-Rules |
| `docs/specs/modules/issue_302_trip_detail_page.md` | Referenz-Spec | Legt Trip-Detail-Design einschließlich Status-Badge-Semantik fest |
| `claude-code-handoff/screenshots/soll-flow7B-trip-detail.png` | Design-Referenz | Visuelles Soll: active-Status als orange outlined Pill |
| `frontend/src/lib/components/ui/pill/Pill.svelte` | Constraint | Keine neuen Tone-Aliase nötig — `accent` ist bereits definiert |

## Implementation Details

### 1. `app.css` — neue outlined-Rule für accent-Tone

Ergänze nach dem letzten bestehenden `[data-outlined]`-Rule-Block (nach Z. 386):

```css
[data-slot="pill"][data-outlined][data-tone="accent"] { color: var(--g-accent-deep); }
```

Begründung: `--g-accent-deep` (#a34a22 oder equivalent dunkles Burnt-Orange) erfüllt WCAG-AA auf weißem Hintergrund ohne `audit:exempt`-Kommentar. `--g-accent` selbst (#c45a2a) hat nur 4.34:1 — knapp unter AA-large; `--g-accent-deep` liegt sicher darüber.

### 2. `TripStatusBadge.svelte` — Tone-Map + outlined

#### Tone-Map ändern

```diff
- const TONE_MAP: Record<TripStatus, 'info' | 'success' | 'warning' | 'default'> = {
-   active: 'success',
+ const TONE_MAP: Record<TripStatus, 'info' | 'accent' | 'warning' | 'default'> = {
+   active: 'accent',
    planned: 'info',
    paused: 'warning',
    archived: 'default',
  };
```

#### `<Pill>` Aufruf — outlined-Attribut ergänzen

```diff
- <Pill tone={TONE_MAP[status]} data-testid="trip-detail-status-badge">
+ <Pill tone={TONE_MAP[status]} data-outlined data-testid="trip-detail-status-badge">
```

`data-outlined` wird als boolesches HTML-Attribut gesetzt und via `{...rest}` an das Pill-Root-Element weitergegeben; `app.css` rendert dann transparenten Hintergrund mit farbigem Rahmen.

### Soll-Verhalten TripStatusBadge nach Änderung

| Trip-Status | Tone | Stil | Farbe |
|---|---|---|---|
| active | accent | outlined | Burnt-Orange Border + Text |
| planned | info | outlined | Info-Blau Border + Text |
| paused | warning | outlined | Warning-Gelb Border + Text |
| archived | default | outlined | Ink-Faint Border + Text |

### Keine Änderungen

- `Pill.svelte` — keine neuen Tone-Aliase nötig
- `TripTabs.svelte` — bits-ui Unterstrich-Tabs entsprechen bereits dem Soll-flow7B; `Segmented`-Atom würde visuell regressieren
- Edit-Seite, Segmented.svelte, alle anderen Trip-Detail-Komponenten

## Expected Behavior

- **Input:** Trip-Objekt mit `status: 'active' | 'planned' | 'paused' | 'archived'`
- **Output:** `<Pill>` mit korrektem Tone (`accent` für active), `data-outlined`-Attribut gesetzt, transparenter Hintergrund, farbiger Rahmen und Text in `--g-accent-deep`
- **Side effects:** Sichtbare Farbänderung im Trip-Header und in der Trips-Liste — active-Status wechselt von gefülltem Grün zu outlined Burnt-Orange; alle anderen Status unverändert

## Acceptance Criteria

- **AC-1:** Given `TripStatusBadge.svelte` im Quelltext / When `grep "active.*success"` ausgeführt wird / Then ist die Trefferanzahl 0 (der alte Tone-Wert `success` für active ist entfernt)
  - Test: (populated after /tdd-red)

- **AC-2:** Given ein Trip mit Status `active` in der Trip-Detail-Ansicht / When die Seite geladen wird / Then erscheint die Status-Pill mit transparentem Hintergrund, Burnt-Orange Rahmen und Burnt-Orange Text (outlined accent) statt gefülltem Grün
  - Test: (populated after /tdd-red)

- **AC-3:** Given Trips mit den Status `planned`, `paused` und `archived` / When die jeweilige Trip-Detail-Seite geladen wird / Then haben alle drei Status-Badges einen `data-outlined`-Stil und ihre bisherigen Tone-Zuordnungen (info / warning / default) unverändert
  - Test: (populated after /tdd-red)

- **AC-4:** Given `app.css` nach dem Change / When `rg '\[data-outlined\]\[data-tone="accent"\]'` ausgeführt wird / Then ist die Trefferanzahl >= 1 (neue Rule ist vorhanden)
  - Test: (populated after /tdd-red)

- **AC-5:** Given das Frontend nach dem Change / When `npm run build` im `frontend/`-Verzeichnis ausgeführt wird / Then gibt es 0 Build-Fehler und 0 svelte-check Fehler
  - Test: (populated after /tdd-red)

- **AC-6:** Given `contrast-audit.test.ts` nach dem Change / When die Test-Suite läuft / Then sind alle Kontrast-Checks grün (kein `--g-accent` als direkter Text-Farbwert ohne `audit:exempt`, da die neue Rule `--g-accent-deep` nutzt)
  - Test: (populated after /tdd-red)

## Known Limitations

- AC-2 und AC-3 sind visuelle Verifikationen; automatisierter Test via `contrast-audit.test.ts` prüft nur den Source-Text, nicht den gerenderten Browser-Output. Manuelle Sichtprüfung oder Playwright-Screenshot empfohlen.
- `data-outlined` wird als boolesches Attribut übergeben. Falls `Pill.svelte` das Attribut nicht via `{...rest}` an das Root-Element weitergibt, ist ein separates `outlined`-Prop nötig — vor Implementierung prüfen.

## Changelog

- 2026-05-26: Initial spec created (Issue #389, Epic #368 Phase 2)
