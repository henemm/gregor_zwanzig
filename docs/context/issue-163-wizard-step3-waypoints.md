---
workflow: issue-163-wizard-step3-waypoints
phase: phase1_context
created: 2026-05-10
issue: 163
parent_epic: 136
related_master_spec: epic_136_trip_wizard
related_sub_spec: epic_136_step3_waypoints
predecessor_issues: [161, 162]
---

# Context: Issue #163 — Wizard Step 3: KI-Waypoints bestaetigen

## Request Summary

Schritt 3 des Trip-Wizards: pro Etappe (aus Step 2) zeigen wir die vom Backend
gelieferten Wegpunkte als KI-Vorschlaege. Layout: links Etappen-Liste (Auswahl),
rechts Confirm-UI mit Hoehenprofil + Waypoint-Liste mit Bestaetigen/Verwerfen.
KI-Vorschlaege werden orange-gestrichelt visualisiert; bestaetigte Wegpunkte
solid. Pausentage (`waypoints.length === 0`) bleiben unberuehrt.

## Master-Spec Vertrag

`docs/specs/modules/epic_136_trip_wizard.md` (approved 2026-05-09) garantiert:

1. `Waypoint.suggested?: boolean` ist als transient typisiert (`types.ts` Z. 16–24).
2. `WizardState.toTripPayload()` strippt `suggested` aus jedem Waypoint
   (`wizardState.svelte.ts` Z. 263–266 `stripSuggested`).
3. `Stage.waypoints[]` ist die Single Source of Truth — Vorschlaege werden mit
   `suggested: true` ins Array gesetzt; Verwerfen = aus Array entfernen;
   Bestaetigen = Flag entfernen.
4. Step 3 darf optional `canAdvanceStep3` als zusaetzlichen Getter ergaenzen
   (additiv, gleicher Pattern wie `canAdvanceStep1` Z. 80–87 + `canAdvanceStep2`
   Z. 97–99). Master-Spec §4 Vertraege erlauben diese Erweiterung mit
   Changelog-Eintrag.

## Konfliktpunkt: Wo werden Waypoints als `suggested` markiert?

Master-Spec §3.4 sagt: "Step 3 ruft den Endpoint pro Etappe auf, erhaelt
Vorschlaege, fuegt sie mit `suggested: true` ins `waypoints`-Array ein."

**Realitaet:** Der `POST /api/gpx/parse`-Aufruf passiert bereits in Step 2
(`uploadGpx` in `frontend/src/lib/api.ts` Z. 27–50). Die zurueckgelieferten
Waypoints landen ohne `suggested`-Flag in `state.stages` (siehe `addStage` in
`wizardState.svelte.ts` Z. 134–139). Ein zweiter Endpoint-Aufruf in Step 3
waere doppelte Arbeit + unterschiedliche Ergebnisse moeglich (Indeterminismus
der Wetterscheiden-Erkennung waere selten, aber moeglich).

**Tech-Lead-Empfehlung fuer die Spec-Phase (Phase 3 entscheidet final):**
Variante A — `WizardState.addStage()` markiert Waypoints aus GPX-Upload mit
`suggested: true`. Step 3 liest und mutiert nur. Vorteil: zentral, Single
Ingest Point. Nachteil: implizit fuer Step 2-Implementierung. Bestehende Tests
muessen angepasst werden.

Variante B — Step 3 markiert beim ersten Mount alle Waypoints, deren
`suggested === undefined`, als `suggested: true`. Vorteil: Step 3
self-contained. Nachteil: Versteckte Mutation auf Mount, Re-Mount-Verhalten
muss bedacht werden.

In Phase 2 / 3 wird das mit User entschieden.

## Render-Konzept "gestrichelte KI-Pins"

Quellen:
- Issue-Body: "Hoehenprofil + Waypoint-Liste, Bestaetigen/Verwerfen-Buttons,
  gestrichelte KI-Pins"
- Stub `epic_136_step3_waypoints.md`: "Wegpunkte mit `suggested === true` werden
  orange-gestrichelt gerendert"
- Master-Spec §3.4: "orange-gestrichelte Pins fuer `suggested === true`,
  durchgehende Pins fuer bestaetigte Wegpunkte"

KEIN Map-Rendering in dieser Sub-Spec — die Karte ist Epic #137 (Wegpunkt-
Editor). „Pins" hier = visuelle Marker an einem Hoehenprofil ODER in der
Waypoint-Liste. In Phase 2 entscheiden:

- Pins als Marker an einer groesseren ProfileChart-SVG (analog Step-2-
  ElevSparkline, aber breiter + mit Marker-Overlay)
- Pins als Status-Badge in der Waypoint-Liste-Row (orange-dashed Border)

ElevSparkline (`$lib/components/ui/elev-sparkline/ElevSparkline.svelte`) ist
heute 120x24px — zu klein fuer ein „Hoehenprofil mit Pins" als rechte
Confirm-UI. Vermutlich braucht Step 3 eine neue `ProfileChart.svelte` (Phase 2).

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/trip-wizard/steps/Step3Waypoints.svelte` | EDIT — heute 8-Zeilen-Stub |
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` | EDIT — `canAdvanceStep3`-Getter; ggf. `addStage` markiert `suggested: true`; Confirm/Reject-Methoden |
| `frontend/src/lib/components/trip-wizard/wizardHelpers.ts` | LESE — `isPauseStage` (Pause-Stages ueberspringen) |
| `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` | LESE — `state.canAdvanceCurrent` switch erweitern (Z. 105–116) |
| `frontend/src/lib/types.ts` | LESE — `Waypoint.suggested?` ist da, `Stage`, `Trip` |
| `frontend/src/lib/components/ui/elev-sparkline/ElevSparkline.svelte` | LESE — vorhandene Sparkline (zu klein fuer Step 3); ggf. neue ProfileChart |
| `frontend/src/lib/components/ui/btn/Btn.svelte` | LESE — Bestaetigen/Verwerfen-Buttons |
| `frontend/src/lib/components/ui/g-card/GCard.svelte` | LESE — Container links + rechts |
| `frontend/src/lib/components/ui/pill/Pill.svelte` | LESE — Etappen-Pill T01 in linker Liste |
| `frontend/e2e/helpers.ts` | EDIT — neuer `fillStep3`-Helper (Confirm-All-Default + per-Waypoint Aktionen) |
| `frontend/e2e/trip-wizard-shell.spec.ts` | EDIT — AC-Tests, die durch Step 3 navigieren, brauchen `fillStep3` |
| `frontend/e2e/trip-wizard-step3.spec.ts` | NEU — E2E-Tests fuer Step 3 |
| `src/web/pages/gpx_upload.py` | LESE — `compute_full_segmentation`, `segments_to_trip` (liefert Waypoints) |
| `src/web/pages/trips.py` | LESE — `gpx_to_stage_data` (Z. 32–77) liefert die Waypoint-Dicts ohne `suggested`-Flag |
| `api/routers/gpx.py` | LESE — `POST /api/gpx/parse` Pipeline-Einstieg |

## Existing Patterns

- **canAdvanceStepN-Getter:** `wizardState.svelte.ts` Z. 80–116 — Pattern aus
  Step 1 + 2; Step 3 ergaenzt analog.
- **Sub-Spec-Aufbau:** `epic_136_step2_stages.md` als Template (Layout-Wireframe,
  TestID-Inventar, fillStepN-Helper, AC-Liste).
- **Pause-Stage-Filterung:** `isPauseStage(stage)` in `wizardHelpers.ts`.
- **Save-Pipeline-Strip:** `stripSuggested(wp)` und `stripDateOverridden(stage)`
  in `wizardState.svelte.ts` — bewaehrtes Muster fuer transiente Flags.
- **Lucide-Icons:** `import Check from '@lucide/svelte/icons/check'`,
  `Trash2` etc. — bereits in Step 2 genutzt.

## Dependencies

| Upstream (Step 3 nutzt) | Zweck |
|---|---|
| `state.stages` aus Step 2 | Etappen-Liste mit Waypoints |
| `state.currentStep` | Switch im `canAdvanceCurrent` |
| `wizardHelpers.isPauseStage` | Pause-Filterung |
| Atom-Komponenten (Epic #133) | Btn, GCard, Pill, Eyebrow, Input |

| Downstream (Step 3 liefert an) | Zweck |
|---|---|
| `state.stages[i].waypoints` ohne `suggested:true` | Step 4 Save-Pipeline strippt Flag, persistiert nur bestaetigte |

## Phase-2-Entscheidungen (User, 2026-05-10)

1. **Pin-Render:** Hoehenprofil + Liste mit gestrichelten Pins (Empfohlen) — neue
   `ProfileChart.svelte` mit Marker-Overlay; Liste mit Bestaetigen/Verwerfen
   pro Wegpunkt.
2. **`canAdvanceStep3 = true` immer.** Pragmatisch: User muss nur explizit
   verwerfen, was er nicht will; Rest wird beim Save automatisch akzeptiert
   (`stripSuggested` greift sowieso). Keine Mindest-Bestaetigung erzwungen.
3. **Keine Bulk-Aktion** „Alle bestaetigen" — Folge-Issue falls Bedarf.
4. **`suggested`-Markierung in `addStage()`** (Variante A, vom Recherche-Agent
   empfohlen): zentralisiert, kein Mount-Hook, funktioniert auch fuer
   zukuenftige Pfade (#165 Templates).

## Tech-Konsolidierung

- **Pin-Style:** `stroke="var(--g-warning)" stroke-dasharray="3,3"` fuer
  `suggested === true`; solid `stroke="var(--g-ink-strong)"` fuer
  bestaetigte Wegpunkte. Token `--g-warning: #c8882a` ist in
  `frontend/src/app.css:48` etabliert.
- **`ProfileChart.svelte` (NEU):** SVG ~360×120px, Polyline aus
  `stage.waypoints[].elevation_m` (Reihenfolge entspricht Stages-Reihenfolge);
  Pins als `<circle>` an x = `(i / N) * width`, y = elevation-skaliert.
  Klick auf Pin selektiert Waypoint in der Liste (optional, in Spec-Phase
  abwaegen).
- **`WaypointRow.svelte` (NEU):** Row mit Pin-Indikator, Wegpunkt-Name,
  Hoehe, Zeit, Bestaetigen/Verwerfen-Buttons (Lucide `check` / `x`).

## Risks & Considerations
2. **Re-Upload eines GPX in Step 2 nach Step-3-Aktionen.** Wenn der User in
   Step 2 zurueckgeht und ein GPX austauscht, gehen seine Confirm/Reject-
   Aktionen fuer diese Etappe verloren — bewusst akzeptiert (UI-Logik ist „neu
   parsen = neuer Vorschlag"). `addStage` setzt `suggested: true` neu.
3. **Performance bei vielen Wegpunkten** — pro Etappe koennen 10–30 Wegpunkte
   anfallen. Bei 14 Etappen + 20 Waypoints/Etappe = ~280 Items. Layouts (Liste
   links + Detail rechts) sollten virtualisierte Renderings unterstuetzen,
   sind aber bei dieser Groessenordnung nicht zwingend.
4. **Kein Map-Render** — der Issue-Text spricht von „Pins"; das ist visuell
   am Hoehenprofil (oder Liste), nicht auf einer Karte. Karte ist Epic #137.
5. **Auswahl-State („welche Etappe ist gerade rechts geoeffnet")** ist
   ausserhalb `WizardState` (UI-only). In Phase 3 als `Step3Waypoints.svelte`-
   lokales `$state<string>(activeStageId)` modellieren.
6. **Pausentage in der linken Liste** sollten gerendert werden (User sieht den
   Trip vollstaendig), aber NICHT klickbar/auswaehlbar — sie haben keine
   Wegpunkte zum Bestaetigen.
7. **Keine Backend-Aenderung** — der Endpoint `POST /api/gpx/parse` liefert
   bereits Waypoints; das `suggested`-Flag ist rein Frontend-Convention.
8. **A11y** — Bestaetigen/Verwerfen muss Tastatur-bedienbar sein
   (`Enter` / `Space`); orange-dashed Pins brauchen Text-Aequivalent
   (`aria-label="Vorschlag (unbestaetigt)"`).
9. **Bulk-Aktionen?** Issue erwaehnt nur per-Waypoint. „Alle bestaetigen"
   waere ein nice-to-have, sollte in Phase 2 gegen User entschieden werden.
10. **`canAdvanceStep3`-Definition.** Ueberlegung: Soll der User Step 3
    weiterschalten duerfen, ohne mindestens einen Wegpunkt zu bestaetigen?
    Strikt: nein (sonst landen alle Vorschlaege als suggested-leer im Save —
    aber suggested wird ja gestrippt, also waeren sie alle „bestaetigt"
    durch Default). Pragmatisch: ja, akzeptiere alle Vorschlaege als
    Default. In Phase 3 final entscheiden.

## Existing Specs

| Spec | Bezug |
|---|---|
| `docs/specs/modules/epic_136_trip_wizard.md` | Master-Spec — Datenmodell, WizardState §3.1, Save §1.4 |
| `docs/specs/modules/epic_136_step3_waypoints.md` | Stub — wird in Phase 3 ausgefuellt |
| `docs/specs/modules/epic_136_step2_stages.md` | Vorgaenger-Sub-Spec — Pattern-Vorlage |
| `docs/specs/modules/epic_136_step1_profile.md` | Vorgaenger-Sub-Spec — `canAdvanceStepN`-Pattern |
| `docs/specs/modules/elevation_analysis.md` | Backend Wetterscheiden-Erkennung |
| `docs/specs/modules/hybrid_segmentation.md` | Backend Segmentierungs-Pipeline |
| `docs/specs/modules/gpx_upload.md` | Backend GPX-Parsing |

## Issue & Verweise

- [#163 — Wizard Step 3: KI-Waypoints bestaetigen](https://github.com/henemm/gregor_zwanzig/issues/163)
- [#136 — EPIC 4 Trip-Wizard](https://github.com/henemm/gregor_zwanzig/issues/136)
- Vorgaenger: #161 (Step 1, closed), #162 (Step 2, closed)
- Folge: #164 (Step 4 Briefings), #165 (Vorlagen)
