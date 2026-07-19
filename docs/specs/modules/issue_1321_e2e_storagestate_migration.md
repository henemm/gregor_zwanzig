---
entity_id: issue_1321_e2e_storagestate_migration
type: module
created: 2026-07-19
updated: 2026-07-19
status: draft
version: "1.0"
tags: [issue-1321, epic-1273, e2e, test-migration, compare, storagestate]
---

# Issue #1321 — Compare-E2E-Suite von Pro-Test-UI-Login auf storageState umstellen

## Approval

- [ ] Approved

## Purpose

Sechs Compare-E2E-Spec-Dateien im Projekt `chromium-login` von `frontend/playwright.1273-s4c.staging.config.ts` loggen sich aktuell **pro Test** per UI (`login(page)` aus `frontend/e2e/helpers.ts`) gegen Staging ein und stoßen dadurch das Rate-Limit des Login-Endpoints (30 Logins/Stunde/IP) an — zwei Volläufe hintereinander kollabieren mit 429-Fehlern und 20+ Minuten Wartezeit zwischen Verifikationsläufen. Diese Migration stellt die sechs Dateien auf das in derselben Config bereits produktiv laufende `chromium-storagestate`-Muster um (1x Login im Setup-Projekt, danach wiederverwendete Session), um Rate-Limit-Kollaps zu vermeiden und Staging-Verifikationsläufe wieder in unter 2 Minuten durchlaufen zu lassen.

## Source

- **Files:** 6 bestehende Playwright-E2E-Spezifikationsdateien unter `frontend/e2e/` (siehe Scope-Tabelle) + 1 Config-Datei `frontend/playwright.1273-s4c.staging.config.ts`. Kein Produktivcode-Identifier im Zentrum — reine Testinfrastruktur.

## Estimated Scope

- **LoC:** ca. -20/+10 netto (deutlich unter dem 250-LoC-Workflow-Limit, kein Override nötig)
- **Files:** 7 (6 Spec-Dateien + 1 Config-Datei)
- **Effort:** low (rein mechanisch, kein neues Verhalten, kein neuer Fachcode)
- **Risk Level:** LOW (reine Testinfrastruktur, kein Produktionscode betroffen)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/e2e/f1-1273-s4c.staging.setup.ts` | Test-Setup (unverändert) | Schreibt storageState via API-Login einmalig nach `frontend/playwright/.auth/staging-1273-s4c.json` |
| `internal/router/router.go:45` | Go-Produktivcode (nur Kontext, kein Change) | `loginLimiter := authmw.NewIPRateLimiter(30, time.Hour)` — Rate-Limit, das den Bug/die Notwendigkeit begründet |
| `frontend/e2e/helpers.ts` (Zeile 8-17) | Test-Helper (unverändert) | `login(page)`-Funktion, deren Import/Aufruf aus den 6 Zieldateien entfernt wird |
| `frontend/e2e/compare-editor-autosave.spec.ts` | Test (unverändert, Vorbild) | 1:1-Migrationsmuster — Teil des `chromium-storagestate`-Projekts, `beforeEach` (Zeile 143-145) enthält nur `page.setViewportSize(...)`, kein Login-Import, kein Login-Aufruf |
| `docs/specs/modules/epic_1273_s4c_e2e_migration.md` | Spec (Vorgänger, bereits live) | Migrierte dieselben 6 Dateien bereits von `/edit`-Route auf Hub/Create-Wizard-Routen — Login-Konsolidierung war dort bewusst NICHT im Scope |

## Implementation Details

### Ersetzungsmuster für die 6 Spec-Dateien

Fall A — `beforeEach` enthält weitere Anweisungen neben dem Login (z.B. `compare-radar-toggle.spec.ts`, `compare-alarm-config.spec.ts`, `versand-tab-vergleich.spec.ts`, `layout-tab-vergleich.spec.ts`, `issue-718-idealwert-validation.spec.ts`):

```
Alt (Zeile 22-23, 68-71 — Beispiel compare-radar-toggle.spec.ts)   Neu
──────────────────────────────────────────────────────────────────────────────
import { login } from './helpers.js';                              [Import entfernt]

test.beforeEach(async ({ page }) => {                              test.beforeEach(async ({ page }) => {
	await login(page);                                                  await page.setViewportSize({ width: 1280, height: 900 });
	await page.setViewportSize({ width: 1280, height: 900 });        });
});
```

Fall B — `beforeEach` enthält AUSSCHLIESSLICH den Login-Aufruf (`compare-legacy-fields-survive-save.spec.ts`, Zeile 39-40 Import, Zeile 82-84 Hook):

```
Alt                                                                 Neu
──────────────────────────────────────────────────────────────────────────────
import { login } from './helpers.js';                              [Import entfernt]

test.beforeEach(async ({ page }) => {                               [kompletter Block entfernt —
	await login(page);                                                  kein toter No-Op-Hook]
});
```

Referenzmuster (bereits produktiv, 1:1-Vorbild): `compare-editor-autosave.spec.ts` Zeile 143-145 — `beforeEach` enthält nur `page.setViewportSize(...)`, Session kommt vollständig aus dem geladenen storageState.

### Config-Verschiebungsmuster (`frontend/playwright.1273-s4c.staging.config.ts`)

Aktuell (Zeile 28-50): zwei Projekte, `chromium-login` mit den 6 `testMatch`-Regex-Einträgen ohne `dependencies`/`storageState`, und `chromium-storagestate` mit 2 Einträgen plus `dependencies: ['setup']` und `use: { storageState: 'playwright/.auth/staging-1273-s4c.json' }`.

```
Alt                                                                 Neu
──────────────────────────────────────────────────────────────────────────────
{ name: 'chromium-login', testMatch: [ 6 Einträge ] },              [Projekt-Objekt komplett entfernt]
{
  name: 'chromium-storagestate',
  testMatch: [ 2 Einträge ],                                        testMatch: [ 2 + 6 = 8 Einträge ],
  dependencies: ['setup'],                                          dependencies: ['setup'],
  use: { storageState: '...staging-1273-s4c.json' }                 use: { storageState: '...staging-1273-s4c.json' }
}                                                                    (unverändert, gilt automatisch
                                                                      für alle testMatch-Einträge)
```

Der Kopfkommentar (Zeile 7-11) beschreibt aktuell zwei Projekttypen (`chromium-login` und `chromium-storagestate`) und wird auf nur noch einen Testprojekt-Typ reduziert/korrigiert. Keine Änderung an `f1-1273-s4c.staging.setup.ts` (deckt bereits alle Dateien im `chromium-storagestate`-Projekt ab) und an `helpers.ts` (der `login()`-Helper bleibt für andere E2E-Suiten außerhalb dieser sechs Dateien bestehen).

## Expected Behavior

- **Input:** 6 bestehende Playwright-E2E-Spezifikationsdateien mit Pro-Test-UI-Login, 1 bestehende Staging-Config mit zwei getrennten Projekten.
- **Output:** Alle 6 Dateien laufen im Projekt `chromium-storagestate` derselben Config, nutzen ausschließlich die vom Setup-Projekt bereitgestellte Session, führen keinen eigenen UI-Login mehr aus. Das Projekt `chromium-login` existiert nicht mehr.
- **Side effects:** Der komplette Config-Lauf verbraucht statt bisher potenziell dutzenden Logins (1 pro Testfall der 6 Dateien) nur noch 1 Login (Setup-Projekt) für alle 8 Dateien im `chromium-storagestate`-Projekt zusammen.

## Acceptance Criteria

- **AC-1:** Given der komplette `playwright.1273-s4c.staging.config.ts`-Lauf gegen Staging / When er ausgeführt wird / Then verbraucht er insgesamt ≤2 Logins (1x Setup-Projekt-Login + höchstens 1 zusätzlicher, z.B. durch Retry) und läuft in unter 2 Minuten durch.
  - Test: Echter Staging-Lauf (`npx playwright test --config=playwright.1273-s4c.staging.config.ts`), IMAP/Server-Log-Auswertung der Login-Endpoint-Aufrufe während des Laufs zählen, Laufzeit messen.

- **AC-2:** Given zwei direkt aufeinanderfolgende Volläufe derselben Config gegen Staging / When der zweite Lauf startet, während das Rate-Limit-Fenster des ersten noch offen ist / Then bleibt auch der zweite Lauf komplett grün (kein 429 „bleibt auf /login hängen").
  - Test: Zwei Läufe direkt hintereinander im selben Staging-Verifikationsschritt ausführen, beide Exit-Codes und Testergebnisse prüfen.

- **AC-3:** Given die migrierten sechs Dateien / When der `chromium-storagestate`-Projekt-Testlauf startet / Then navigiert keiner der sechs migrierten Testfälle mehr über einen UI-Login-Formular-Flow (kein `page.fill('input[name="username"]')`-Aufruf mehr in den sechs Dateien), sondern nutzt ausschließlich die vom Setup-Projekt bereitgestellte Session.
  - Test: Grep-Nachweis auf `login(` und `input[name="username"]` in den 6 Dateien (0 Treffer) als Zusatzindiz, kombiniert mit einem echten funktionalen Testlauf gegen Staging, der ohne Login-Redirect direkt auf der Zielroute landet — der Grep allein ist kein Verhaltensnachweis, erst der grüne Lauf beweist, dass die Session tatsächlich trägt.

## Known Limitations

- Der generische `login()`-Helper in `helpers.ts` bleibt für andere E2E-Suiten bestehen, die außerhalb dieses Scopes liegen — das Rate-Limit-Problem ist für DIESE Config gelöst, nicht global für alle E2E-Configs im Repo.
- Größerer Fan-out auf denselben geteilten storageState (8 statt bisher 2 Dateien im `chromium-storagestate`-Projekt) — AC-2 (zwei Volläufe grün) ist der explizite Nachweis, dass das keine neue Flakiness durch Testdaten-/Session-Interferenz einführt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Testinfrastruktur-Konsolidierung nach einem bereits etablierten, produktiv erprobten Muster (storageState-Projekt existiert bereits in derselben Config) — keine neue Architekturentscheidung, keine schwer umkehrbare oder systemweite Änderung, kein Produktionscode betroffen.

## Changelog

- 2026-07-19: Initial spec created
