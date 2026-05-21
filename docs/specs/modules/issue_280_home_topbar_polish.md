---
entity_id: issue_280_home_topbar_polish
type: module
created: 2026-05-21
updated: 2026-05-21
status: implemented
version: "1.0"
tags: [sveltekit, frontend, home, css, typography]
---

# Issue #280 — Home Topbar: tracking-tight für H1

## Approval

- [ ] Approved

## Purpose

Ergänzt `letter-spacing: -0.025em` (Tailwind `tracking-tight`) auf der H1 der Home-Seite. Entspricht dem in Issue #280 geforderten Typography-Polish und dem bestehenden Muster auf der Trips-Seite (`trips/+page.svelte:271`). Alle anderen Anforderungen aus #280 wurden bereits durch Issue #294 erledigt.

## Source

- **File:** `frontend/src/routes/+page.svelte`
- **Identifier:** `.home__title` (Zeile 62)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `--g-text-3xl` | CSS token | Schriftgröße (unverändert) |
| `trips/+page.svelte:271` | pattern | Referenz für `tracking-tight`-Muster in Page-H1s |

## Implementation Details

```css
/* vorher */
.home__title { font-size: var(--g-text-3xl); font-weight: 600; margin: 0; }

/* nachher */
.home__title { font-size: var(--g-text-3xl); font-weight: 600; letter-spacing: -0.025em; margin: 0; }
```

Kein weiterer Code. Keine neuen Token. Keine weiteren Dateien.

## Expected Behavior

- **Input:** User öffnet `/`
- **Output:** H1 "Startseite" wird mit engerem Buchstabenabstand gerendert
- **Side effects:** keine

## Acceptance Criteria

**AC-1:** Given die Home-Seite wird geladen / When der User `/` öffnet / Then hat das `.home__title`-Element den berechneten `letter-spacing`-Wert `−0.025em` (≈ `−0.4px` bei 16px Base)
- Test: (populated after /tdd-red)

## Known Limitations

- Keine Personalisierung ("Guten Tag, [Name]") — explizit so entschieden, "Startseite" bleibt
- `tracking-tight` ist ein direkter CSS-Wert, kein Design-Token — bewusst, da kein systemweites "H1-tracking"-Token existiert

## Changelog

- 2026-05-21: Implementation abgeschlossen — `letter-spacing: -0.025em` zu `.home__title` hinzugefügt, Status auf "implemented" aktualisiert
- 2026-05-21: Spec erstellt für Issue #280 (Restarbeiten nach #294)
