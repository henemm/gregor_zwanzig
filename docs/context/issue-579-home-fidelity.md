# Context: #579 Home-Screen Design-Fidelity (Drift-Korrektur, Epic #575)

## Request Summary
Wiedereröffnetes Issue: Home-Screen soll 1:1 zu `screen-home.jsx` stehen, Pixel-Diff < 10 %
für die drei Modi (trip/compare/planning). Erst-Implementierung (d586dd56) deckte die
strukturellen ACs, die Drift-Korrektur fehlt noch.

## Aktuelle Baseline (gegen Staging, 2026-06-07)
| Screen | diff_pct | Threshold | Status |
|--------|----------|-----------|--------|
| D-home-trip | 13,82 % | 20 % (Override #578) | passt Override, NICHT 10 % |
| D-home-compare | 14,40 % | 10 % | FAIL |
| D-home-planning | 13,29 % | 10 % | FAIL |

## Kernbefunde
1. **Staging-Konto ist im Compare-Modus** (1 Vergleich, kein Trip) → nur `D-home-compare`
   ist Apfel-mit-Apfel. trip/planning teilen dieselbe URL `/` und sind gegen das
   Einzelzustands-Konto nie messbar.
2. **SOLL ist veraltet:** zeigt durchgehend den **Signal-Kanal** (Pills, Versandzeilen),
   der per PO-Entscheidung #610 app-weit entfernt wurde → exaktes <10 % strukturell
   unmöglich (gleiche Lage wie Schwester #582, im Threshold-Map dokumentiert).
3. **Daten-Divergenz:** SOLL zeigt datenreiche Demo (KHW-403-Trip, 8 Archiv-Trips, Region,
   Briefing-Historie); Staging-Konto ist dünn (1 Vergleich, keine Region, kein Archiv).

## Echte Implementierungs-Drift vs JSX (fixbar, datenunabhängig)
- **Compare-Modus „Einrichten / Kein Trip geplant"-Empty-State fehlt** (JSX 340–360):
  Live rendert stattdessen generisch „Archiv / Frühere Trips" (Zeile 783), nur `{#if archive>0}`.
  JSX-Soll im Compare: Eyebrow „Einrichten", Titel „Kein Trip geplant", Kicker „Sobald ein
  Mehrtages-Trip ansteht…", rechts **primary** „Neuer Trip"-Button.
- **Hero-Untertitel Compare:** Live `{region} · N Orte verglichen` — JSX hat zusätzlich
  `· Vorhersage {horizon}` (fehlt).
- **Eyebrow-Naming:** Live „Archiv" vs JSX „Einrichten" (auch Trip-Modus, JSX 326).

## Related Files
| File | Relevanz |
|------|----------|
| frontend/src/routes/+page.svelte | Home, 908 Z., 3 Mode-Blöcke + geteilte Archiv-Sektion |
| frontend/src/lib/components/organisms/HomeHeroTrip/Compare.svelte | Hero-Organismen |
| frontend/src/routes/_home/cockpitHelpers.js | archivedTrips, plannedBriefings |
| claude-code-handoff/current/jsx/screen-home*.jsx | bindende Quelle |
| .claude/hooks/design_fidelity_diff.py | Gate-Tool, SCREEN_THRESHOLD_MAP (D-home-trip=20) |

## Risiken
- Threshold-Override ohne echte 1:1-Verifikation = Issue durchdrücken (Memory verbietet).
- 3 Modi / 1 URL: nur 1 Modus live messbar → trip/planning brauchen anderen Verifikationsweg.
