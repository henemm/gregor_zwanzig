---
entity_id: fix_2119_stagecard_km
type: fast
created: 2026-10-18
status: implemented
---

# Mini-Spec: fix-2119-stagecard-km

Issue #2119 — Etappen-Kachel zeigt Luftlinie statt GPX-Track-Distanz.

## Was ändert sich
- `StageCard.svelte` (Desktop-Kachel im Wegpunkt-Editor): `totalKm` nutzt `computeHeaderStats(stage).distanceKm` statt der eigenen Grad→km-Näherung. Ist die Etappe voll vermessen (`stageHasFullTrackDistance`), kommt die `distance_from_start_km`-Differenz, sonst der Haversine-Fallback aus `headerStats.ts`.
- `StageCardM.svelte` (mobile Kachel): dieselbe eigene Formel in `stats.km` wird auf dieselbe Regel umgestellt (Trip/Mobile-Parität, gleiche Zahl auf derselben Seite).
- Keine vierte Distanzformel: beide Kacheln verwenden `computeHeaderStats` aus `email-preview/headerStats.ts`.

## Was darf sich nicht ändern
- Anzeigeformat (`12.8 km · ↑666`), Höhenmeter-Berechnung, Pausen-Etappen, Kachel < 2 Wegpunkte zeigt weiterhin keine km.
- Keine Änderung an Persistenz, Gehzeit-Schätzung, Ankunftszeiten, Alarmen.
- Keine Änderung an der Trip-Konfiguration des PO.

## Acceptance Criteria
- **AC-1:** Given eine Etappe, deren Wegpunkte alle `distance_from_start_km` tragen, When die Etappen-Kachel (Desktop `StageCard`) gerendert wird, Then zeigt sie die Differenz letzter minus erster `distance_from_start_km` (z. B. 17.5 km) und nicht die Luftlinie.
- **AC-2:** Given dieselbe Etappe, When die mobile Kachel (`StageCardM`) gerendert wird, Then zeigt sie denselben km-Wert wie die Desktop-Kachel und der Trip-Header.
- **AC-3:** Given eine Etappe ohne vollständige `distance_from_start_km`, When die Kachel gerendert wird, Then zeigt sie weiterhin die Näherungs-Distanz (Fallback), ohne Fehler; bei weniger als 2 Wegpunkten erscheint keine km-Angabe.

## Manuelle Test-Schritte
1. Staging: Trip mit GPX-Etappe öffnen, `?tab=stages` — Kachel-km und Header-km der Etappe sind identisch.
2. Mobile-Ansicht derselben Etappe: gleiche km-Zahl.

## Inline-Test (wird während Implementierung geschrieben)
- [ ] Test für `StageCard`: vermessene Etappe → Track-km (AC-1), Fallback ohne Messwerte (AC-3)
- [ ] Test für `StageCardM`: vermessene Etappe → Track-km (AC-2)
