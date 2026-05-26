# Spec: Home-H1 Terminologie-Regression (Parallel-Session a8d30fd)

**Status:** Draft — wartet auf PO-Approval
**Created:** 2026-05-26
**Bezug:** #394 (Trip-Terminologie). Regression durch Parallel-Commit a8d30fd.

## Problem
Parallel-Session-Commit `a8d30fd` änderte die Startseiten-Überschrift „Startseite" → „Deine Touren & Vergleiche" und führte damit user-sichtbares „Touren" wieder ein. Der #394-Guard `trip-terminology.test.ts` ist dadurch auf `main` ROT (`routes/+page.svelte:98`). Verstößt gegen die freigegebene Regel „immer Trip".

## Lösung
`frontend/src/routes/+page.svelte`: „Deine Touren & Vergleiche" → „Deine Trips & Vergleiche" (H1). Begleit-Kommentar „Weitere Touren + Vergleiche" → „Weitere Trips + Vergleiche". Übrige a8d30fd-Änderungen (data-slot=g-card, Reports-Anzeige) bleiben unverändert.

## Acceptance Criteria
**AC-1:** Given der integrierte Stand, When `trip-terminology.test.ts` läuft, Then 0 Treffer (grün) — kein user-sichtbares „Touren" mehr in `+page.svelte`.
**AC-2:** Given die Startseite, When sie rendert, Then zeigt die H1 „Deine Trips & Vergleiche"; die a8d30fd-Verbesserungen (Kacheln/Reports) bleiben intakt.
**AC-3 (keine Regression):** homeCockpit 22/22, contrast-audit 5/5, home-loader-no-weather 3/3, svelte-check sauber, build grün.

## Test
RED-Beleg: Guard aktuell rot (`+page.svelte:98 „Touren"`). GREEN: nach Fix grün. Kein neuer Test nötig (Guard aus #394 deckt es ab).
