# Spec · Token-Bridge (Issue #369, Epic #368)

**Status:** Entwurf · wartet auf Approval
**Created:** 2026-05-25
**Quelle:** `docs/design-requests/issue_15_atomic_design/spec/tokens.css` (Sandbox) + `spec/TOKEN-MAPPING.md`

## Kontext

Die Atomic-Design-Bibliothek (Epic #368) wird 1:1 aus der Claude-Design-Sandbox übernommen. Deren Bausteine referenzieren Design-Tokens, deren **Namen und teils Werte** von unserer ausgelieferten `frontend/src/app.css` abweichen. Ohne Brücke zeigen die neuen Bausteine auf nicht existierende Tokens → kein Rendering (body-15 §C1).

## Ziel

Additive Ergänzung der Sandbox-Tokens in `frontend/src/app.css`, sodass die übernommenen Bausteine **pixeltreu zum Design** rendern, **ohne** bestehende Tokens oder die 142 Bestands-Komponenten zu verändern.

## Vorgehen

1. Neuer, klar kommentierter Block in `app.css` (`@layer base { :root { … } }`, Abschnitt „Atomic-Design-Bridge (#369)").
2. Pro Sandbox-Token die in `TOKEN-MAPPING.md` festgelegte Bridge-Aktion:
   - **NEU (Sandbox-Wert):** `--g-card`, `--g-card-alt`, `--g-rule`, `--g-ink-2/3/4`, `--g-accent-deep/soft/tint`, `--g-good/warn/bad`, `--g-weather-rain/snow/sun/cloud`, `--g-r-3/4`, `--g-shadow-1..3`.
   - **Alias (Wert identisch):** `--g-font-sans→var(--g-font-ui)`, `--g-font-mono→var(--g-font-data)`, `--g-r-1→var(--g-radius-xs)`, `--g-r-2→var(--g-radius-sm)`, `--g-r-pill→var(--g-radius-pill)`, `--g-weather-thunder→var(--g-wx-thunder)`.
   - **Nichts (schon vorhanden, identisch):** `--g-paper`, `--g-ink`, `--g-accent`, `--g-s-*`, `--g-text-*`, `--g-track-*`.
   - **Kollision → unseren Wert behalten:** `--g-info`, `--g-paper-deep`, `--g-rule-soft` (nicht überschreiben).
3. `.dark`-Theme: dieselben Bridge-Tokens, soweit die Sandbox Dark-Werte vorgibt; sonst von Light erben.
4. Keine Änderung an bestehenden `--g-surface-*`, `--g-success/warning/danger`, `--g-wx-*`, `--g-radius-*`, `--g-elev-*`, `--g-font-ui/data`.

## Acceptance Criteria

**AC-1:** Given die neue Bridge ist in `app.css` ergänzt, When eine Komponente `var(--g-card)` nutzt, Then liefert der Token `#ffffff` (Sandbox-Wert), nicht das beige `--g-surface-1`.

**AC-2:** Given alle in `TOKEN-MAPPING.md` mit „NEU"/„Alias" markierten Tokens, When man sie in `app.css` ausliest, Then ist jeder unter seinem Sandbox-Namen auflösbar (kein `var()`-Fallback greift).

**AC-3:** Given die drei Kollisions-Tokens (`--g-info`, `--g-paper-deep`, `--g-rule-soft`), When die Bridge angewandt ist, Then behalten sie ihren bisherigen Produktionswert (kein Überschreiben).

**AC-4:** Given die bestehenden Tokens (`--g-surface-*`, `--g-success/warning/danger`, `--g-wx-*`, `--g-radius-*`, `--g-elev-*`), When die Bridge angewandt ist, Then sind ihre Definitionen byte-gleich wie zuvor.

**AC-5:** Given die laufende App, When man Sidebar, Trips-Liste, Trip-Detail und Compare lädt, Then ist die Darstellung visuell unverändert gegenüber vor der Bridge (Stichprobe, keine Regression).

**AC-6:** Given `--g-accent-deep/soft/tint` und `--g-weather-cloud`, When sie ergänzt sind, Then tragen sie exakt die Sandbox-Werte (`#8c3e1a` / `#f3d9c8` / `rgba(196,90,42,0.08)` / `#9a958a`).

## Out of Scope

- App-weite Umstellung bestehender Screens auf Sandbox-Werte (z. B. weiße Karten überall) — offene Design-Entscheidung, eigenes Issue.
- Langfristiger Token-Rename (`app.css` → Sandbox-Namen über 142 Dateien) — eigenes Issue.
- Dark-Mode-Feinabstimmung der neuen Tokens, falls Sandbox keine Dark-Werte liefert.

## Test / Nachweis

- Snapshot der relevanten `app.css`-Zeilen vor/nach (Diff zeigt nur Additionen + unveränderte Bestands-Tokens).
- Showcase-Route (#374) rendert später alle Tokens sichtbar — dort finaler visueller Abgleich.
- Manuelle Stichprobe der vier Bestands-Screens (AC-5).
