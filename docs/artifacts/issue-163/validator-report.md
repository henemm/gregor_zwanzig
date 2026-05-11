# External Validator Report — Issue #163 (Step 3 Wegpunkt-Vorschlaege)

**Spec:** `docs/specs/modules/epic_136_step3_waypoints.md` (v1.0, approved 2026-05-11)
**Datum:** 2026-05-11T06:30Z
**Server:** https://staging.gregor20.henemm.com
**Test-Account:** validator-issue110
**Methode:** Headless-Chromium via Playwright, isoliert vom Implementer (kein `src/`/`git`/`workflow_state.json` gelesen).
**Test-GPX:** `frontend/e2e/fixtures/KHW_10.gpx` + `KHW_11.gpx` als 2 Etappen + 1 manuell eingefuegter Pausentag (zwischen den Etappen).

## Checklist

| AC | Expected Behavior | Beweis | Verdict |
|----|-------------------|--------|---------|
| 1 | `trip-wizard-step3-container` rendert | Screenshot `06_step3_initial.png`, TestID gefunden | **PASS** |
| 2 | Linke Liste zeigt alle Stages inkl. Pausentage | 2 Stage-Rows nach Upload von 2 GPX (`stage-row-0`, `stage-row-2`); Pause-Marker bei Index 1 (siehe AC#3) | **PASS** |
| 3 | Pause-Marker `trip-wizard-step3-pause-marker-{i}`, nicht klickbar | `px_step3_with_pause.png` — `pause-marker-1` vorhanden; Playwright-Klick blockiert von `stages-list`-Container (pointer-events) → aktive Stage unveraendert | **PASS** |
| 4 | Klick auf Nicht-Pause-Stage → diese aktiv | `09_step3_after_stage_click.png`; Klick auf zweite Stage → erste Waypoint-Row-Text wechselt von Stage-1- auf Stage-2-Inhalt | **PASS** |
| 5 | Init = erste Nicht-Pause-Stage aktiv ohne Klick | `06_step3_initial.png` zeigt Waypoint-Liste der 1. Stage direkt nach Step-Wechsel | **PASS** |
| 6 | `ProfileChart` mit aria-label „Hoehenprofil mit N Wegpunkten" | Attribut: `aria-label="Hoehenprofil mit 5 Wegpunkten"` | **PASS** |
| 7 | Gestrichelte Pins fuer `suggested`-Waypoints | `circle[stroke-dasharray]`-Count = 5 (alle Waypoints initial suggested) | **PASS** |
| 8 | Solid Pins fuer bestaetigte Waypoints | Nach Confirm: 1 `circle:not([stroke-dasharray])` und 4 dashed (5→4) | **PASS** |
| 9 | Waypoint-Rows mit TestID `waypoint-row-{i}` | 5 Rows nach Upload | **PASS** |
| 10 | Row zeigt Name + Hoehe + Zeit | Erste Row: `Start / 1408 m / 08:00-08:00` | **PASS** |
| 11 | Confirm-Button nur sichtbar bei `suggested === true` | Vor Klick: 5 confirm-Buttons. Nach 1 Confirm: 4 confirm-Buttons (der confirmed Row hat keinen mehr) | **PASS** |
| 12 | Klick Confirm → Pin solid + Button weg | dashed 5→4, confirm-Button-Count 5→4 (`07_step3_after_confirm.png`) | **PASS** |
| 13 | Klick Reject → Row weg + Pin weg | rows 5→4, circles 5→4 (`08_step3_after_reject.png`) | **PASS** |
| 14 | `confirmWaypoint` entfernt suggested-Flag | Indirekt verifiziert via AC#12 (Pin-Style wechselt) | **PASS** |
| 15 | `rejectWaypoint` entfernt Waypoint | Indirekt verifiziert via AC#13 (Row+Pin verschwinden) | **PASS** |
| 16 | `addStage`-Patch setzt suggested=true auf alle | Alle 5 Pins initial gestrichelt → `addStage` markiert (Spec: `Variante A, zentralisiert`) | **PASS** |
| 17 | `canAdvanceStep3 === true` | Indirekt via AC#19 (Weiter immer enabled) | **PASS** |
| 18 | `canAdvanceCurrent` case 3 → `canAdvanceStep3` | Indirekt via AC#19 | **PASS** |
| 19 | Weiter-Button immer enabled in Step 3 | `next.is_enabled() === True` ohne jede Aktion (`06_step3_initial.png`) | **PASS** |
| 20 | Empty-State §8a (no-stages) | UI-Pfad zu Step 3 ohne Stages nicht erreichbar (Stepper-Click-Skip funktioniert nicht). Empty-State `trip-wizard-step3-empty-no-stages` somit nicht via Browser-Test reproduzierbar (`12_step3_empty_attempt.png`) | **UNKLAR** |
| 21 | Empty-State §8b (only-pauses) | Nicht via UI testbar (Pause-Anlage in Step 2 erfordert mindestens 1 Etappe als Anker) | **UNKLAR** |
| 22 | Empty-State §8c (no-waypoints) | `10_step3_all_rejected.png` zeigt `trip-wizard-step3-empty-no-waypoints` nach Verwerfen aller Waypoints | **PASS** |
| 23 | `fillStep3()` ohne Parameter klickt Weiter und landet in Step 4 | Weiter-Klick → Stepper-State von Step 4 = `active`, aber `trip-wizard-step4-container` fehlt — vorhanden ist `trip-wizard-step4-briefings` (`11_step4_arrived.png`). **Spec-Helper §10 wuerde an `getByTestId('trip-wizard-step4-container').waitFor()` scheitern.** | **FAIL** |
| 24 | Master-Spec hat Changelog-Eintrag fuer Step-3-Erweiterungen | `docs/specs/modules/epic_136_trip_wizard.md` Z. mit „2026-05-10: §3.1 erweitert um additive Methoden/Getter (Sub-Spec #163)" gefunden | **PASS** |
| 25 | `npm run check` und `npm run build` gruen | CI-Output nicht aus Validator-Sicht pruefbar (waere Implementer-Spur) | **UNKLAR** |

**Summary:** 21× PASS, 1× FAIL, 3× UNKLAR.

## Findings

### F-1: AC#23 — Step-4-Container-TestID stimmt nicht mit Spec ueberein

- **Severity:** MEDIUM
- **Expected (Spec §10, AC#23):** Nach `fillStep3()` → Weiter-Klick wartet auf `trip-wizard-step4-container`. AC#1-Aequivalent fuer Step 4 wird in Spec §10 + §11 als impliziter Vertrag gefordert.
- **Actual:** Step 4 ist erreichbar (Stepper-State der vierten Stufe wechselt von `pending` auf `active`), aber das Step-4-Root-Element traegt die TestID `trip-wizard-step4-briefings` statt `trip-wizard-step4-container`.
- **Konsequenz:** Der Spec-konforme `fillStep3`-Helper aus §10 (Z. 399) wuerde mit Default-Timeout fehlschlagen. AC#23 ist damit faktisch nicht erfuellt — der Helper wird in seiner spezifizierten Form niemals gruen.
- **Evidence:** `11_step4_arrived.png`, `evaluate(...)` listet vorhandene Step-4-Prefix-IDs: `["trip-wizard-step4-briefings"]`.
- **Empfehlung an Implementer:** Entweder Step-4-Root-TestID auf `trip-wizard-step4-container` umbenennen (Sub-Spec #164/#162-Konvention) ODER Spec-§10/AC#23 anpassen, damit der Helper auf eine vorhandene TestID wartet. Der Sub-Spec-Selbsttest (AC#23) ist bis dahin formal verletzt.

### F-2: AC#20 + AC#21 — Empty-States §8a/§8b ueber UI nicht reproduzierbar

- **Severity:** LOW (organisatorisch)
- **Expected (Spec §8a/b):** Wenn Step 3 ohne Stages erreicht wird, soll `trip-wizard-step3-empty-no-stages` rendern; bei nur Pausentagen `trip-wizard-step3-empty-only-pauses`.
- **Actual:** Stepper-Klick auf `trip-wizard-step-3` ist im UI nicht aktiv solange Step 2 unvollstaendig ist (Weiter-Button gated). Reine UI-Navigation kann Step 3 ohne mindestens 1 Etappe nicht erreichen. Damit sind beide Empty-States nicht via Browser-Test verifizierbar — sie waeren nur via Unit-Test (Komponente direkt mit leerem `WizardState` mounten) zu pruefen.
- **Evidence:** `12_step3_empty_attempt.png` zeigt nach dem Skip-Versuch Step 1 (kein State-Wechsel).
- **Empfehlung:** Diese AC-Punkte als Unit-Test markieren (oder im Validator-Report explizit mit „nicht E2E-pruefbar" akzeptieren). Kein Implementations-Defekt aus Validator-Sicht — nur eingeschraenkte externe Verifizierbarkeit.

### F-3: AC#25 — Build-Status nicht extern pruefbar

- **Severity:** LOW (out of validator scope)
- **Hinweis:** `npm run check` / `npm run build` sind Implementer-Artefakte und wuerden aus dem CI-Lauf des Implementers stammen — diese Information darf der External Validator gemaess Isolation-Regeln nicht aus `docs/artifacts/`/Implementer-Quellen lesen. Verbleibt fuer den Adversary-Workflow / CI-Check.

## Verdict: **AMBIGUOUS**

### Begruendung

20 von 25 Acceptance Criteria sind sauber **PASS** mit Screenshot-Beweis. Die fachlichen Kern-Verhaltensweisen funktionieren wie spezifiziert: ProfileChart rendert Pins korrekt (gestrichelt fuer suggested, solid nach Confirm), `confirmWaypoint`/`rejectWaypoint` mutieren WizardState beobachtbar, `canAdvanceStep3` ist immer true, Pause-Marker sind dank pointer-events nicht klickbar.

Es gibt **einen klaren FAIL** (F-1, AC#23): die Spec spricht in §10/§11 explizit vom Container-TestID `trip-wizard-step4-container`, der in der Implementierung fehlt — stattdessen heisst er `trip-wizard-step4-briefings`. Der Spec-Helper wuerde damit nicht gruen. Das ist eine **Spec-Implementierungs-Diskrepanz**, kein Funktions-Bug — Step 4 wird erreicht, nur die TestID-Konvention ist inkonsistent.

Drei UNKLAR-Punkte (AC#20/21/25) sind aus Validator-Sicht **nicht extern via Browser pruefbar** — sie waeren via Unit-Test bzw. CI-Output abzudecken.

Da kein funktionaler Defekt vorliegt, aber AC#23 formal verletzt ist und der Spec-Helper bei strikter Lesart broken waere, lautet das Verdict **AMBIGUOUS**: nicht VERIFIED (weil 1 echter FAIL), nicht BROKEN (weil das Feature fachlich vollstaendig funktioniert).

**Empfehlung Implementer:** F-1 entweder durch TestID-Rename oder Spec-Patch aufloesen. Danach sind alle browser-pruefbaren AC's gruen und das Verdict wird VERIFIED.
