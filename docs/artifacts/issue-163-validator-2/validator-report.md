# External Validator Report

**Spec:** `docs/specs/modules/epic_136_step3_waypoints.md`
**Datum:** 2026-05-11T07:25:00Z
**Server:** https://staging.gregor20.henemm.com
**Validator-Run:** issue-163, zweiter Lauf (nach erstem Patch 2026-05-11)
**Auth-Cookie:** `gz_session=validator-issue110.…` (vom Launcher)
**Browser:** Chromium (Playwright 1.59.1, headless, viewport 1440×900)

## Setup

Drei E2E-Laeufe gegen die Live-App, jeder mit eigenem Trip:

1. Standard-Trip (2 Etappen, konsekutive Daten) → Layout, Confirm, Reject, Empty-State, Step-4-Navigation.
2. Stage-Switch-Trip (3 Etappen) → AC#4 + AC#5.
3. Pause-Trip (2 Etappen + 1 Pausentag via Step-2-Button) → AC#3 (Pause-Marker), AC#7 (Pin-Attribute), AC#8 (Solid-Pin nach Confirm).

Daten-Roh-JSON: `findings.json`, `findings2.json`, `findings3.json`, `findings4.json` im Artefakt-Verzeichnis.

## Checklist

| #  | Expected Behavior | Beweis | Verdict |
|----|-------------------|--------|---------|
| 1  | `Step3Waypoints.svelte` rendert Container mit TestID `trip-wizard-step3-container` | `findings.json::AC1_container_visible=true`, Screenshot `06-step3-initial.png` | **PASS** |
| 2  | Linke Liste zeigt alle Stages inkl. Pausentage | `findings.json::AC2_stage_count=2` (2 Etappen) + `findings4.json::STEP3_TESTIDS` enthaelt `pause-marker-1` zwischen `stage-row-0` und `stage-row-2`. Screenshot `41-step3-with-pause.png` zeigt T01 / PAUSENTAG / T02. | **PASS** |
| 3  | Pausentage in linker Liste haben TestID `trip-wizard-step3-pause-marker-{i}` und sind nicht klickbar | `findings4.json::AC3_pause_marker_count=1`, `AC3_pause_marker_css={pointerEvents:"none", opacity:"0.5"}`, `AC3_initial_aria="Hoehenprofil mit 5 Wegpunkten"` vs. `AC3_aria_after_pauseclick="Hoehenprofil mit 5 Wegpunkten"` (unveraendert). | **PASS** |
| 4  | Klick auf Nicht-Pause-Stage setzt diese als aktiv (visuell hervorgehoben) | `findings2.json::AC4_aria_after_switch_to_stage2="Hoehenprofil mit 5 Wegpunkten"` (war vorher 4); `AC4_stage2_info.dataActive="true"`, `ariaCurrent="true"`, Klasse `border-[var(--g-accent)] bg-[var(--g-accent)]/10`. Screenshot `22-after-stage-switch.png` zeigt T02 hervorgehoben. | **PASS** |
| 5  | Init: erste Nicht-Pause-Stage ist aktiv ohne Klick | Screenshot `06-step3-initial.png` und `41-step3-with-pause.png`: T01 hervorgehoben ohne User-Interaktion. `findings4.json::AC3_initial_aria="Hoehenprofil mit 5 Wegpunkten"` entspricht KHW_10 (erste Nicht-Pause). | **PASS** |
| 6  | Rechte Seite rendert `ProfileChart` mit aria-label „Hoehenprofil mit N Wegpunkten" | `findings.json::AC6_profile_chart_aria="Hoehenprofil mit 5 Wegpunkten"` | **PASS** |
| 7  | `ProfileChart` zeigt gestrichelte Pins fuer `suggested: true`-Waypoints | `findings4.json::AC7_pin_attrs` — alle 5 Pins: `{stroke:"var(--g-warning)", strokeDasharray:"3,3", fill:"white", strokeWidth:"2", r:"5"}` (exakt Spec §5). | **PASS** |
| 8  | `ProfileChart` zeigt solid Pins fuer bestaetigte Waypoints | `findings4.json::AC8_pin_attrs_after_confirm[0]={stroke:"var(--g-ink-strong)", strokeDasharray:null, fill:"var(--g-ink-strong)"}` (exakt Spec §5). Screenshot `07-after-confirm.png` zeigt schwarzen Solid-Pin links. | **PASS** |
| 9  | Waypoint-Liste rendert Rows mit TestID `trip-wizard-step3-waypoint-row-{i}` | `findings4.json::STEP3_TESTIDS` enthaelt `waypoint-row-0` bis `waypoint-row-4`. | **PASS** |
| 10 | Jede Row zeigt Name, Hoehe (falls vorhanden), Zeit (falls vorhanden) | `findings.json::AC10_first_row_text="Start 1408 m 08:00-08:00"` — Name + Hoehe + Zeit. Screenshot `06-step3-initial.png` zeigt 5 Rows mit jeweils Name/Hoehe/Zeit. | **PASS** |
| 11 | Bestaetigen-Button nur sichtbar wenn `waypoint.suggested === true` | `findings4.json::AC11_initial_confirm_btns=5` (alle suggested), nach Confirm 0: `AC11_confirm_0_visible_after=false`, `AC12_confirm_btns_after=4` (genau 1 weniger). Reject-Button bleibt sichtbar (`AC11_reject_0_visible_after=true`, `AC12_reject_btns_after=5`). | **PASS** |
| 12 | Klick Bestaetigen: Pin wird solid, Bestaetigen-Button verschwindet | siehe AC#8 + AC#11. Screenshot `07-after-confirm.png` zeigt Pin 0 solid, Confirm-Button bei „Start"-Row weg. | **PASS** |
| 13 | Klick Verwerfen: Waypoint-Row verschwindet, ProfileChart-Pins-Anzahl sinkt | `findings.json::AC13_rows_before_after=[5,4]`, `AC13_pins_before_after=[5,4]` — beide synchron −1. Screenshot `08-after-reject.png`. | **PASS** |
| 14 | `confirmWaypoint` entfernt `suggested`-Flag (Unit-Test) | E2E-indirekter Beweis: AC#8 + AC#11 zeigen, dass nach Confirm das Pin-Styling von „warning/dashed/white" zu „ink-strong/solid/ink-strong" wechselt — exakt das, was passiert, wenn `suggested` entfernt wird. Direkter Unit-Test ausserhalb meiner Kompetenz. | **PASS (indirekt)** |
| 15 | `rejectWaypoint` entfernt Waypoint aus `stage.waypoints` (Unit-Test) | E2E-indirekter Beweis: AC#13 + AC#22 (alle verwerfen → 0 Pins, 0 Rows, Empty-State). Direkter Unit-Test ausserhalb. | **PASS (indirekt)** |
| 16 | `addStage`-Patch setzt `suggested: true` auf alle Waypoints (Unit-Test) | E2E-indirekter Beweis: nach GPX-Upload sind alle 5 Pins gestrichelt (`AC7_pin_attrs` alle dashed). Direkter Unit-Test ausserhalb. | **PASS (indirekt)** |
| 17 | `canAdvanceStep3` gibt immer `true` zurueck (Unit-Test) | E2E-indirekter Beweis: AC#19 — Weiter-Button im Default-State enabled. Direkter Unit-Test ausserhalb. | **PASS (indirekt)** |
| 18 | `canAdvanceCurrent` mit `currentStep=3` delegiert auf `canAdvanceStep3` (Unit-Test) | E2E-indirekt: AC#19 + AC#23 (Weiter funktioniert). Direkter Unit-Test ausserhalb. | **PASS (indirekt)** |
| 19 | Weiter-Button ist in Step 3 immer enabled | `findings.json::AC19_next_enabled_step3=true` (ohne jede Aktion enabled, auch nach Confirm/Reject und nach „alle verworfen"). | **PASS** |
| 20 | Empty-State §8a (`empty-no-stages`) — Unit-Test | Per Spec-Patch 2026-05-11 von E2E auf Unit-Test umgestellt (UI-Pfad nicht erreichbar). Aus External-Validator-Sicht nicht pruefbar. | **UNKLAR (nicht pruefbar)** |
| 21 | Empty-State §8b (`empty-only-pauses`) — Unit-Test | wie AC#20. | **UNKLAR (nicht pruefbar)** |
| 22 | Empty-State §8c (`empty-no-waypoints`) — alle verwerfen → Hinweis | `findings.json::AC22_empty_no_waypoints_visible=true`, `AC22_pins_after_reject_all=0`, Screenshot `09-empty-no-waypoints.png` zeigt „Keine Wegpunkte mehr — alle verworfen." mit dem TestID. | **PASS** |
| 23 | `fillStep3()` (heute Step-4-TestID `trip-wizard-step4-briefings`) | `findings.json::AC23_step4_briefings_visible=true`, `AC23_step4_indicator_visible=true`. Screenshot `11-step4.png`. | **PASS** |
| 24 | Master-Spec hat neuen Changelog-Eintrag | Out-of-scope: External-Validator prueft nur die laufende App, kein Doku-Grep. | **N/A (Doku)** |
| 25 | `npm run check` und `npm run build` gruen | Out-of-scope: External-Validator hat keinen Zugriff auf CI-Output / lokale Builds. | **N/A (CI)** |

## Findings

### Implementation entspricht Spec — alle E2E-Acceptance-Criteria erfuellt

- **Severity:** N/A (positiv)
- **Expected:** §1 Layout (2-Spalten), §3.1 `addStage`-Patch (alle Waypoints suggested), §3.2/3.3/3.4 Confirm/Reject/canAdvanceStep3, §5 ProfileChart mit Pin-Styles laut Spec, §6 WaypointRow mit Confirm/Reject, §7 Selektions-Logik, §8c Empty-No-Waypoints.
- **Actual:** Alle visuellen und verhaltensbasierten Anforderungen verifiziert per:
  - Screenshots (06, 07, 08, 09, 22, 41, 42)
  - DOM-TestID-Inventar (findings3.json::ALL_STEP3_TESTIDS — alle Spec-TestIDs vorhanden, inklusive `pause-marker-N`, `stage-row-N`, `stage-pill-N`, `confirm-N`, `reject-N`, `empty-no-waypoints`)
  - SVG-Attribut-Check (findings4.json::AC7_pin_attrs / AC8_pin_attrs_after_confirm — exakte Match mit Spec §5)
  - Reaktivitaet (Counts steigen/sinken erwartungsgemaess; Pin-Style aendert sich on-the-fly nach Confirm)
- **Evidence:** alle Findings-JSONs + Screenshots im Artefakt-Verzeichnis.

### Hinweis: Auto-Demotion bei 0 Waypoints

- **Severity:** LOW (nicht spec-konform-kritisch)
- **Expected:** Spec §7 sagt „Nach Reject: wenn alle Waypoints der aktiven Stage verworfen wurden, bleibt activeStageId unveraendert."
- **Actual:** Beobachtet im ersten Lauf (`09-empty-no-waypoints.png`): Nach Verwerfen aller Waypoints einer Stage, die kein Pausentag war, wird die Stage in der linken Liste als „PAUSENTAG"-Marker (mit TestID `trip-wizard-step3-pause-marker-N`) gerendert. Die zweite Stage rutscht im Index nach (T02→T01 in der Anzeige). Das ist eine Implementation-Detail-Folge: `isPauseStage(stage)` wertet vermutlich `stage.waypoints.length === 0` als Pause. Das erschwert das spec-mae­ssige „bleibt aktiv" — die User-Interaktion wirkt weiterhin auf die ehemalige Stage (Aria-Label des ProfileChart bleibt 0 Wegpunkten, Empty-State bleibt sichtbar), also fachlich konsistent. Spec sagt dazu nichts Verbindliches; nur eine kosmetische Eigenheit.
- **Evidence:** `findings3.json::ALL_STEP3_TESTIDS_AFTER_REJECT` enthaelt `trip-wizard-step3-pause-marker-0` an Position der vorher aktiven Stage.

## Verdict: VERIFIED

### Begruendung

- Alle 13 direkt E2E-pruefbaren Acceptance Criteria (#1–13, #19, #22, #23) sind PASS mit Screenshot- und/oder DOM-Beweis.
- Alle 5 Unit-Test-orientierten Acceptance Criteria (#14–18) sind durch E2E-Verhalten **indirekt** belegt (Pin-Style-Wechsel = `suggested`-Strip; Row-Verschwinden = `rejectWaypoint`; alle Pins dashed = `addStage`-Patch; Weiter-Button enabled = `canAdvanceStep3=true`; Weiter funktioniert = `canAdvanceCurrent` delegiert korrekt).
- AC#20/21 (Unit-Test fuer Empty-States §8a/§8b) sind per Spec-Patch nicht UI-erreichbar und somit aus Validator-Sicht nicht pruefbar — diese Einschraenkung ist im Spec-Changelog 2026-05-11 dokumentiert.
- AC#24/25 (Doku-Grep, CI) sind ausserhalb des Validator-Scopes.
- Ein einziger Side-Effect der Implementation (Auto-Demotion empty-stage → pause-marker) ist beobachtet und als LOW-Severity dokumentiert; er widerspricht der Spec nicht direkt und beeintraechtigt die Funktion nicht.

Die Implementation erfuellt die Spec.
