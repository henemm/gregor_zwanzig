# External Validator Report

**Spec:** `docs/specs/modules/epic_136_step0_shell.md`
**Datum:** 2026-05-10T (Validator-Run)
**Server:** https://staging.gregor20.henemm.com
**Test-Methode:** Curl (SSR-HTML-Inspektion) + Playwright Chromium (headless, Cookie-authentifiziert als `validator-issue110`)

## Setup

- Auth-Cookie `gz_session` gesetzt (Validator-User)
- Initial-Render via `curl -H "Cookie: gz_session=..." https://staging.gregor20.henemm.com/trips/new`
- Dynamik-Tests via Playwright mit Click-Sequenzen, `data-state`-Attributen und Network-Interception

## Checklist

| # | Expected Behavior | Beweis | Verdict |
|---|-------------------|--------|---------|
| 1 | `/trips/new` rendert `TripWizardShell` (alter `TripWizard` weg vom Mount-Pfad) | SSR-HTML enthaelt `data-testid="trip-wizard-shell"`; Playwright `locator.waitFor({state:'visible'})` PASS; Screenshot `screenshots/01-step1.png`. Alter `wizard-*` testid nicht mehr im Mount-Pfad. | **PASS** |
| 2 | `WizardState` wird in `+page.svelte` instanziiert (nicht als Modul-Singleton) und via `setContext('trip-wizard-state', state)` bereitgestellt | **Code-Inspektion ist Validator nicht erlaubt.** Behavioural Proof: Steps reagieren auf nextStep/prevStep, Step-Slot rendert Inhalt entsprechend `currentStep` — konsistent mit Context-Pattern. | **UNKLAR** (Code-Pfad nicht inspizierbar — siehe Findings) |
| 3 | Stepper rendert 4 Indikatoren mit `data-testid="trip-wizard-step-{1..4}"` und `data-state="done\|active\|pending"` | SSR-HTML zeigt alle 4 Indikatoren mit korrektem `data-state`-Attribut. Werte beobachtet: `s1=active s2=pending s3=pending s4=pending` initial; nach Weiter `s1=done s2=active`. | **PASS** |
| 4 | Step 1 ist initial aktiv (`data-state="active"`); Steps 2–4 pending | `s1=active s2=pending s3=pending s4=pending` | **PASS** |
| 5 | Klick auf "Weiter" wechselt zu Step 2; "Zurueck" auf Step 2 wechselt zurueck zu Step 1 | Eyebrow textContent "Schritt 1 von 4" → nach Weiter "Schritt 2 von 4" → nach Zurueck "Schritt 1 von 4". `[data-testid="trip-wizard-step2-stages"]` sichtbar nach Weiter. Screenshot `02-step2.png`. | **PASS** |
| 5a | Weiter-Button ist in Steps 1–3 enabled | `isEnabled()` PASS in Steps 1, 2; durch alle Steps durchnavigiert ohne Disabled. | **PASS** |
| 6 | Step-Indikatoren aktualisieren `data-state` nach Navigation | Nach 1×Weiter: Step 1 → `done` (mit `<span data-slot="dot" data-tone="success" data-size="md">`), Step 2 → `active`. | **PASS** |
| 7 | Cancel navigiert zu `/` | URL vor Klick `https://staging.gregor20.henemm.com/trips/new`, nach Klick `https://staging.gregor20.henemm.com/`. Screenshot `06-after-cancel.png`. | **PASS** |
| 8 | Speichern-Button erscheint nur in Step 4; Klick ruft `state.save()` | Step 4: `[data-testid="trip-wizard-save"]` `isVisible()=true`, `[data-testid="trip-wizard-next"]` count=0. Save-Klick erzeugt `POST https://staging.gregor20.henemm.com/api/trips` (Network-Interception). Screenshot `04-step4.png`, `05-save-clicked.png`. | **PASS** |
| 9 | Alte E2E-Tests in `trip-wizard.spec.ts` sind via `.skip()` deaktiviert mit Kommentar | **Validator darf `frontend/e2e/`-Tests nicht inspizieren.** Aus Production-Sicht keine Beobachtung moeglich. | **UNKLAR** |
| 10 | `npm run check` und `npm run build` im `frontend/` gruen | **Validator darf nicht builden.** Indirekter Indikator: Production-Build laeuft, Seite rendert ohne Hydration-Fehler in Console (Playwright keine Page-Errors waehrend Tests). | **UNKLAR** (positiv-indikativ, nicht direkt verifiziert) |
| 11 | Alle 4 Step-Slot-Container (`trip-wizard-step{N}-{name}`) sind in den jeweiligen Steps sichtbar mit Platzhaltertext | Step 1: "Inhalt folgt in Issue #161 — Profil & Eckdaten." (PASS). Step 2: "Inhalt folgt in Issue #162 — GPX-Import." (PASS). Step 3: "Inhalt folgt in Issue #163 — KI-Wegpunkt..." (PASS). Step 4: `[data-testid="trip-wizard-step4-briefings"]` sichtbar (PASS). | **PASS** |
| 12 | Stepper-Indikator nutzt Atom `Dot` fuer Done-Status (Token-konform) | Done-State HTML enthaelt `<span data-slot="dot" data-tone="success" data-size="md" aria-hidden="true">` — eindeutige Signatur des `Dot`-Atoms aus Epic #133. | **PASS** |

## Findings

### F1 — `WizardState`-Context-Bereitstellung nicht direkt verifizierbar
- **Severity:** LOW
- **Expected:** AC #2 fordert "Code-Inspektion + Step-Komponenten lesen via `getContext`".
- **Actual:** Validator-Rolle erlaubt kein Lesen von `src/`. Behavioural Proof (Step-Wechsel, Save-POST mit korrektem Body-Schema) ist konsistent mit der Spec, aber ein unabhaengiger Beweis "der Context-Aufruf existiert" ist nicht moeglich.
- **Evidence:** Konsistente Step-Navigation (Screenshots 01-step1, 02-step2, 04-step4) + erfolgreicher `POST /api/trips`-Klick.

### F2 — Save-Status-Region fehlt im idle-State im DOM
- **Severity:** LOW
- **Expected (Spec §5):** Wrapper-`<div data-testid="trip-wizard-save-status" role="status" aria-live="polite">` ist gemaess Code-Snippet **unkonditional**, mit konditionalem Inneren.
- **Actual:** In Step 4 (idle, vor Save-Klick) ist `[data-testid="trip-wizard-save-status"]` nicht im DOM (`count()=0`). Erst nach Save-Klick erscheint die Region (Validator-Run zeigte Inhalt "name required" als `saveError`).
- **Evidence:** Playwright `locator.count()=0` auf Step 4 idle; Save-Klick triggerte sichtbare Status-Region mit Backend-Fehlertext.
- **Bewertung:** Kein Acceptance-Criterion fordert die Region im idle-State explizit; Spec-Kommentar `<!-- saveStatus === 'idle': nichts rendern (display: none) -->` laesst beide Lesarten zu. Funktional: Bei aktivem Status (`saving`/`error`/`ok`) ist die Region korrekt vorhanden mit `role="status"` / `aria-live="polite"`.

### F3 — `npm run check` / `npm run build` und Test-Skip nicht direkt validierbar
- **Severity:** LOW
- **Expected:** AC #9, #10 fordern CI/Test-File-Verifikation.
- **Actual:** Liegt ausserhalb der Validator-Rechte (`src/`/`e2e/`/`Build`-Sperre). Production-Seite rendert ohne JS-Errors, was indirekt fuer einen erfolgreichen Build spricht.
- **Evidence:** Playwright-Run erzeugte keine Page-Errors; SSR liefert valides HTML.

### F4 — Eyebrow-CSS verwendet `text-transform: uppercase`
- **Severity:** INFO (kein Spec-Verstoss)
- **Beobachtung:** `textContent` liefert "Schritt 1 von 4" (matched Spec-Wortlaut), `innerText` liefert "SCHRITT 1 VON 4" (visueller Render durch Eyebrow-Atom-Style). Spec verlangt nur den Text-Inhalt — PASS.
- **Evidence:** `Eyebrow textContent: "Schritt 1 von 4"`.

## Beobachtete Side-Effects gemaess Spec

- **`POST /api/trips`** (Spec Side-effect): bei Save-Klick verifiziert; Backend antwortet mit Validation-Fehler (`name required`) — passt zu Known-Limitation der Spec ("schreibt unvollstaendigen Trip"; Spec-Erfuellung ist die Existenz/Verkabelung des Buttons, nicht ein gruener Save-Request).

## Verdict: VERIFIED

### Begruendung

Alle direkt beobachtbaren Acceptance Criteria (1, 3, 4, 5, 5a, 6, 7, 8, 11, 12) sind durch SSR-HTML, Playwright-Interaktion und Network-Interception eindeutig erfuellt. Die drei UNKLAR-Punkte (AC #2, #9, #10) liegen ausserhalb der Validator-Rechte (Code-/Testfile-/Build-Inspektion) und sind nicht inhaltlich strittig — die Behavioural Proofs (Save-POST funktioniert, Steps reagieren auf Navigation, kein Hydration-Error im Browser) decken sich konsistent mit den geforderten Implementierungs-Details.

Die einzige nennenswerte Abweichung (F2 Save-Status-Region im idle-State nicht im DOM) ist durch den ambivalenten Spec-Kommentar abgedeckt und beeinflusst kein Acceptance-Criterion. Die Region erscheint korrekt mit `role="status"`/`aria-live="polite"`-Semantik, sobald sie inhaltlich relevant ist.

**Verdict: VERIFIED** — Sub-Spec #160 (Trip-Wizard-Shell + 4-Schritt-Stepper) ist auf Staging korrekt implementiert. Drei Acceptance Criteria koennen aufgrund der Validator-Isolation nicht direkt verifiziert werden, sind aber durch Behavioural Proxies konsistent.
