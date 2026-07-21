---
entity_id: bug_327_triphero_font_tokens
type: bugfix
created: 2026-05-22
updated: 2026-05-22
status: draft
version: "1.1"
tags: [frontend, design-system, css, ap-017]
---

# Bug #327: Hardcodierte font-sizes im Trip-Kopfbereich → --g-text-* Tokens

## Approval

- [ ] Approved (v1.1 — Scope-Erweiterung um TripHeader.svelte)

## Purpose

AP-017 („Drift in der Schrift-Skala") verbietet `font-size`-Werte, die nicht aus der `--g-text-*` Token-Skala kommen. Der Trip-Kopfbereich enthält freie rem-Werte ohne Token-Anbindung in **zwei** Komponenten. Beide werden auf die definierte Skala gemappt. Keine Logik- oder Struktur-Änderung.

> **Hinweis zur Anti-Pattern-Nummer:** Issue #327 referenziert „AP-010". In `docs/design-system/ANTI-PATTERNS.md` ist AP-010 jedoch „Cockpit-Style Startseite". Der inhaltlich einschlägige Pattern ist **AP-017 „Drift in der Schrift-Skala"** (Z. 317–323). Diese Spec verwendet die korrekte Nummer.

> **Scope-Korrektur (v1.1):** Issue #327 nennt nur `TripHero.svelte`. Dieses Bauteil ist jedoch **toter Code** — es wird seit dem Trip-Detail-Redesign (Issue #302) von keiner Route/Komponente mehr gerendert, nur noch im Barrel `index.ts` re-exportiert. Der **tatsächlich auf `/trips/[id]` sichtbare** Tour-Kopf ist `TripHeader.svelte` (gerendert in `routes/trips/[id]/+page.svelte:110`) und enthält dieselbe Art von Verstößen (4 freie font-sizes). Auf PO-Entscheidung werden **beide** Komponenten in diesem Bugfix gemappt. (`TripHero.svelte` als toter Code → Kandidat für separates Cleanup-Issue, nicht Teil von #327.)

## Source

- **File 1 (toter Code):** `frontend/src/lib/components/trip-detail/TripHero.svelte` — `<style>` Z. 59, 64, 70, 86, 92
- **File 2 (live, gerendert):** `frontend/src/lib/components/trip-detail/TripHeader.svelte` — `<style>` Z. 158, 175, 187, 199

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/app.css` | CSS-Token-Quelle | Definiert `--g-text-*` Typografie-Skala (Z. 109–117) |

## Affected Files

| Datei | Schicht |
|-------|---------|
| `frontend/src/lib/components/trip-detail/TripHero.svelte` | Frontend (toter Code, nicht gerendert) |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | Frontend / User-UI (live auf `/trips/[id]`) |

## Token-Referenz (app.css Z. 109–117)

| Token | Wert |
|-------|------|
| `--g-text-xs` | 11px |
| `--g-text-sm` | 13px |
| `--g-text-md` | 15px |
| `--g-text-lg` | 17px |
| `--g-text-xl` | 20px |
| `--g-text-2xl` | 24px |
| `--g-text-3xl` | 32px |

## Implementation Details

Jede Ersetzung folgt der Mapping-Tabelle. Tokens werden **ohne** px-/rem-Fallback referenziert (Konsistenz mit Issue #277 / #323).

### Vollständige Ersetzungsliste — File 1: TripHero.svelte (toter Code)

| Datei:Zeile | Selektor | font-size (Ist) | font-size (Soll) | Token-px | Δ |
|-------------|----------|------------------|-------------------|----------|---|
| TripHero.svelte:59 | `.trip-hero-title` | `1.5rem` (24px) | `var(--g-text-2xl)` | 24px | 0 (exakt) |
| TripHero.svelte:64 | `.trip-hero-region` | `0.875rem` (14px) | `var(--g-text-sm)` | 13px | −1px (Snap an Skala) |
| TripHero.svelte:70 | `.trip-hero-date-range` | `0.875rem` (14px) | `var(--g-text-sm)` | 13px | −1px (Snap an Skala) |
| TripHero.svelte:86 | `.eyebrow` | `0.6875rem` (11px) | `var(--g-text-xs)` | 11px | 0 (exakt) |
| TripHero.svelte:92 | `.stat-value` | `1rem` (16px) | `var(--g-text-md)` | 15px | −1px (Snap an Skala) |

### Vollständige Ersetzungsliste — File 2: TripHeader.svelte (live, sichtbar)

| Datei:Zeile | Selektor | font-size (Ist) | font-size (Soll) | Token-px | Δ |
|-------------|----------|------------------|-------------------|----------|---|
| TripHeader.svelte:158 | `.trip-h1` (Tourname) | `2rem` (32px) | `var(--g-text-3xl)` | 32px | 0 (exakt) |
| TripHeader.svelte:175 | `.status-text` | `0.8125rem` (13px) | `var(--g-text-sm)` | 13px | 0 (exakt) |
| TripHeader.svelte:187 | `.meta-line` (Zeitraum) | `0.875rem` (14px) | `var(--g-text-sm)` | 13px | −1px (Snap an Skala) |
| TripHeader.svelte:199 | `.briefing-msg` | `0.875rem` (14px) | `var(--g-text-sm)` | 13px | −1px (Snap an Skala) |

## Expected Behavior

- **Input:** `TripHero.svelte` (5 freie rem-Werte) + `TripHeader.svelte` (4 freie rem-Werte).
- **Output:** Dieselben Selektoren mit `var(--g-text-*)` CSS-Custom-Properties; visuell gleichwertiges Ergebnis (≤1px Schrift-Delta an den betroffenen Stellen).
- **Side effects:** Keine — reine CSS-Änderung, keine Props-/Logik-/Markup-Anpassung. Bestehende `trip-detail-hero.spec.ts`-Tests (Sichtbarkeit, Text, H1) bleiben grün.

## Acceptance Criteria

**AC-1:** Given die beiden Dateien `TripHero.svelte` und `TripHeader.svelte` / When man `grep -nE 'font-size:\s*[0-9]'` gegen jede der beiden ausführt / Then liefert der Befehl in beiden Dateien keine Treffer mehr.

**AC-2:** Given `TripHeader.svelte` wird auf `/trips/[id]` (live, sichtbarer Tour-Kopf) gerendert / When man Tourname-H1, Status-Zeile, Meta-/Zeitraum-Zeile und Briefing-Hinweis visuell mit dem Vorzustand vergleicht / Then sehen alle Elemente gleichwertig aus (keine Layout-Brüche, kein Umbruch; akzeptabler Schrift-Delta von je −1px bei Meta-Zeile und Briefing-Hinweis durch Snap an die Token-Skala). `TripHero.svelte` ist toter Code und hat keine Live-Oberfläche — für dieses Bauteil entfällt die visuelle Prüfung; nur AC-1 + AC-3 gelten.

**AC-3:** Given die `--g-text-*` Tokens werden referenziert / When der Browser die CSS auswertet / Then werden keine px-/rem-Fallbacks im `var()`-Aufruf verwendet (z. B. `var(--g-text-sm)`, nicht `var(--g-text-sm, 0.875rem)`).

## Changelog

| Version | Datum | Änderung |
|---------|-------|----------|
| 1.0 | 2026-05-22 | Initiale Spec für Bug #327 — 5 hardcodierte font-sizes in TripHero.svelte |
| 1.1 | 2026-05-22 | Scope-Erweiterung (PO-Entscheidung): TripHero ist toter Code; live sichtbarer `TripHeader.svelte` (4 font-sizes) ergänzt. Beide Dateien werden gemappt. |

## Known Limitations

- Mehrere Werte verkleinern sich um je 1px (14px→13px bzw. 16px→15px), da `--g-text-sm`/`--g-text-md` 13px/15px sind. Das ist der intendierte Snap an die einheitliche Skala (AP-017), nicht ein Rendering-Fehler.
- `TripHero.svelte` ist toter Code (nicht gerendert). Der Fix darauf erfüllt AC-1/AC-3, ist aber für den Nutzer unsichtbar. Empfehlung: separates Cleanup-Issue zum Entfernen von `TripHero.svelte` + Barrel-Export — außerhalb von #327.
- 28+ weitere Komponenten enthalten ebenfalls hardcodierte `font-size`-Werte. Diese sind **außerhalb des Scope** von #327 (analog #322/#323/#324).
