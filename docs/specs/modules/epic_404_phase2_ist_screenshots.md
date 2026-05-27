---
entity_id: epic_404_phase2_ist_screenshots
type: module
created: 2026-05-27
updated: 2026-05-27
status: draft
version: "1.0"
tags: [playwright, screenshots, audit, staging, epic-404, tooling]
---

<!-- Epic #404 Phase 2 — IST-Screenshots via Playwright gegen Staging für SOLL-IST-Vergleich -->

# Epic #404 Phase 2 — IST-Screenshot-Script (Playwright/Node.js)

## Approval

- [ ] Approved

## Zweck

Das Script `take-ist-screenshots.js` fährt via Playwright alle SvelteKit-Screens auf Staging automatisiert ab und speichert IST-Screenshots mit denselben Dateinamen wie die 50 SOLL-Screenshots aus Phase 1. Damit entsteht eine bildgenaue Grundlage für den SOLL-IST-Vergleich in Phase 3 des Audits (Epic #404): Jede Abweichung vom Design-Handoff wird sichtbar, ohne manuelles Durchklicken.

## Quelle / Source

- **Datei:** `claude-code-handoff/soll-audit-2026-05-27/take-ist-screenshots.js`
- **Identifier:** Node.js-Script (kein Modul-Export, direkt mit `node` ausführbar)

> **Schicht-Hinweis:** Reines Tooling-Script in `claude-code-handoff/` — außerhalb des produktiven Source-Trees (`frontend/`, `src/`, `api/`, `internal/`). Kein Deploy nötig, kein Einfluss auf Production oder Staging-Services. Playwright-Binaries werden aus `frontend/node_modules/playwright` konsumiert.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/node_modules/playwright` | npm-Paket (bereits installiert) | Chromium-Steuerung; wird per absolutem Pfad required |
| `https://staging.gregor20.henemm.com` | Externes System | Ziel-URL; muss beim Script-Aufruf erreichbar sein |
| `frontend/e2e/fixtures/test-trip.gpx` | Test-Fixture (bereits vorhanden) | GPX-Datei für Wizard-Step-3-Upload |
| `frontend/.env.playwright` | Konfigurationsdatei | Enthält Login-Credentials (user/pass) für Staging |
| `claude-code-handoff/soll-audit-2026-05-27/ist-screenshots/` | Ausgabeverzeichnis | Wird vom Script angelegt wenn nicht vorhanden |
| `claude-code-handoff/soll-audit-2026-05-27/take-soll-screenshots.js` | Referenz-Script (Phase 1) | Namenskonvention und Viewport-Konfiguration orientieren sich daran |

## Implementation Details

### Konstanten (Kopf des Scripts)

```javascript
const { chromium } = require('/home/hem/gregor_zwanzig/frontend/node_modules/playwright');
const path = require('path');
const fs   = require('fs');

const BASE_URL = 'https://staging.gregor20.henemm.com';
const OUT_DIR  = path.join(__dirname, 'ist-screenshots');
const CREDS    = { user: 'default', pass: 'ZfDOKJTre8udPtG' };
const TRIP_ID  = 'e2e-cockpit-test';
const GPX_FILE = '/home/hem/gregor_zwanzig/frontend/e2e/fixtures/test-trip.gpx';
```

`OUT_DIR` wird per `fs.mkdirSync(OUT_DIR, { recursive: true })` am Script-Start angelegt.

### Helper-Funktionen

**`login(page)`**
1. `page.goto(BASE_URL + '/login')`
2. Fill `[name="username"]` mit `CREDS.user`
3. Fill `[name="password"]` mit `CREDS.pass`
4. Click Submit-Button
5. `page.waitForURL(BASE_URL + '/')` — Erfolg = Session aktiv

**`seedTrip(page)`**
1. `GET /api/trips/${TRIP_ID}` via `page.request.get()`
2. Bei HTTP 200: kein Handlungsbedarf, Trip existiert bereits
3. Bei HTTP 404: `POST /api/trips` mit minimalem Trip-Body (Name, TRIP_ID als shortcode, 3 Stages: gestern/heute/morgen) — analog zu `global.setup.ts`

**`shot(page, name)`**
- `page.screenshot({ path: path.join(OUT_DIR, name), fullPage: false })`

**`wizardSteps(page, prefix, viewport)`**
Sequenz:
1. `page.goto(BASE_URL + '/trips/new')` + `waitForSelector('[data-testid="trip-wizard"]')`
2. Fill Step 1: Aktivitäts-Chip `trekking`, Name `"Audit Test"`, Startdatum = morgen (ISO-String)
3. Click `[data-testid="trip-wizard-next"]` + `waitForSelector('[data-testid="step2-container"]')`
4. `shot(page, prefix + 'wiz-2.png')`
5. `setInputFiles('[data-testid="gpx-upload"]', GPX_FILE)` + Click Bulk-Commit-Button + `waitForSelector('[data-testid="stage-row-0"]')`
6. Click Next + `waitForSelector('[data-testid="step3-container"]')`
7. `shot(page, prefix + 'wiz-3.png')`
8. Click Next + `waitForSelector('[data-testid="step4-container"]')`
9. `shot(page, prefix + 'wiz-4.png')`
10. Kein Save — Browser schließen beendet die Session sauber

### Desktop-Run (Viewport 1440×900)

`browser.newContext({ viewport: { width: 1440, height: 900 } })`

| Dateiname | Route | Wartebed. |
|---|---|---|
| `desktop-home.png` | `/` | `waitForSelector('body')` |
| `desktop-trips-list.png` | `/trips` | `waitForSelector('body')` |
| `desktop-trip-detail.png` | `/trips/${TRIP_ID}` | `waitForSelector('body')` |
| `desktop-metrics.png` | `/trips/${TRIP_ID}#weather` | `waitForTimeout(1000)` |
| `desktop-alerts.png` | `/trips/${TRIP_ID}#alerts` | `waitForTimeout(1000)` |
| `desktop-email-preview.png` | `/trips/${TRIP_ID}#preview` | `waitForTimeout(1000)` |
| `desktop-sms-preview.png` | `/trips/${TRIP_ID}#preview` + click SMS-Radio | `waitForTimeout(500)` nach click |
| `desktop-wp-editor.png` | `/trips/${TRIP_ID}/edit` | `waitForSelector('body')` |
| `desktop-wizard-step1.png` | `/trips/new` | `waitForSelector('[data-testid="trip-wizard"]')` |
| `desktop-wizard-step2.png` | Wizard Step 2 | via `wizardSteps()` |
| `desktop-wizard-step3.png` | Wizard Step 3 | via `wizardSteps()` |
| `desktop-wizard-step4.png` | Wizard Step 4 | via `wizardSteps()` |
| `desktop-compare-main.png` | `/compare` | `waitForSelector('body')` |
| `desktop-archive.png` | `/archiv` | `waitForSelector('body')` |
| `desktop-location-new.png` | `/locations` + click "Neuer Ort" | `waitForSelector('[data-testid="new-location-dialog"]')` |

### Mobile-Run (Viewport 390×844)

Separater `browser.newContext({ viewport: { width: 390, height: 844 } })`

| Dateiname | Route | Wartebed. |
|---|---|---|
| `mobile-m-home.png` | `/` | `waitForSelector('body')` |
| `mobile-m-trips.png` | `/trips` | `waitForSelector('body')` |
| `mobile-m-trip-detail.png` | `/trips/${TRIP_ID}` | `waitForSelector('body')` |
| `mobile-m-alerts.png` | `/trips/${TRIP_ID}#alerts` | `waitForTimeout(1000)` |
| `mobile-m-metrics.png` | `/trips/${TRIP_ID}#weather` | `waitForTimeout(1000)` |
| `mobile-m-wiz-1.png` | `/trips/new` | `waitForSelector('[data-testid="trip-wizard"]')` |
| `mobile-m-wiz-2.png` | Wizard Step 2 | via `wizardSteps()` |
| `mobile-m-wiz-3.png` | Wizard Step 3 | via `wizardSteps()` |
| `mobile-m-wiz-4.png` | Wizard Step 4 | via `wizardSteps()` |
| `mobile-m-compare.png` | `/compare` | `waitForSelector('body')` |
| `mobile-m-wp-editor.png` | `/trips/${TRIP_ID}/edit` | `waitForSelector('body')` |

### Tab-Navigation via Hash

SvelteKit wertet `#weather`, `#alerts`, `#preview` als `initialTab`-Parameter aus. Ablauf:
```javascript
await page.goto(BASE_URL + '/trips/' + TRIP_ID + '#weather');
await page.waitForTimeout(1000); // SvelteKit-Hash-Routing abwarten
await shot(page, 'desktop-metrics.png');
```

### Abschluss-Zusammenfassung

Am Ende gibt das Script aus:
```
IST-Screenshots fertig.
Verzeichnis: /path/to/ist-screenshots/
Anzahl Dateien: 26
Fehler: 0
```
Bei Fehlern: Name des fehlgeschlagenen Screenshots + Fehlermeldung; Exit-Code 1.

### LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `claude-code-handoff/soll-audit-2026-05-27/take-ist-screenshots.js` | ~240 (neu) | Nein (`docs/`-äquivalent: Tooling außerhalb src/) |
| **Gesamt (zählend)** | **0** | **kein Limit-Effekt** |

> Hinweis: `claude-code-handoff/` liegt außerhalb von `src/`, `api/`, `internal/`, `frontend/` und `cmd/` — analog zu `docs/`. Der LoC-Zähler des Workflow-Gates erfasst diese Dateien nicht.

## Expected Behavior

- **Input:** Keine CLI-Argumente; alle Parameter sind Konstanten im Script-Kopf
- **Output:** 26 PNG-Dateien in `claude-code-handoff/soll-audit-2026-05-27/ist-screenshots/` (15 Desktop + 11 Mobile), Konsolenausgabe mit Dateianzahl und etwaigen Fehlern
- **Side effects:**
  - Login-Session auf Staging (temporär, Kontext wird nach Lauf geschlossen)
  - `seedTrip()` kann Trip `e2e-cockpit-test` auf Staging anlegen, falls er fehlt
  - Kein Save am Wizard-Ende — kein Datenmüll auf Staging

## Acceptance Criteria

- **AC-1:** Given das Script wird mit `node take-ist-screenshots.js` ausgeführt / When Staging erreichbar ist und Login erfolgreich / Then werden alle Screenshots in `ist-screenshots/` abgelegt (kein Fehler, kein leerer Ordner).

- **AC-2:** Given Login mit Credentials aus den Konstanten im Script / When `page.goto('/login')` + Fill + Submit ausgeführt / Then landet die Session auf `/` (authentifiziert, kein Redirect auf `/login`).

- **AC-3:** Given Trip `e2e-cockpit-test` existiert nicht auf Staging / When `GET /api/trips/e2e-cockpit-test` liefert 404 / Then legt `seedTrip()` den Trip via POST an, bevor Screenshots gemacht werden.

- **AC-4:** Given Desktop-Run mit Viewport 1440×900 / When alle 15 Desktop-Routes durchlaufen / Then existieren 15 PNG-Dateien in `ist-screenshots/` mit Präfix `desktop-`.

- **AC-5:** Given Mobile-Run mit Viewport 390×844 / When alle 11 Mobile-Routes durchlaufen / Then existieren 11 PNG-Dateien in `ist-screenshots/` mit Präfix `mobile-m-`.

- **AC-6:** Given Wizard-Sequenz in `wizardSteps()` / When GPX-Upload via `setInputFiles(GPX_FILE)` + Bulk-Commit-Click + Next / Then zeigt Step 3 echte Wegpunkt-Vorschläge (Selektor `[data-testid="stage-row-0"]` vorhanden), Screenshot ist repräsentativ und nicht leer.

- **AC-7:** Given Script-Ende ohne Fehler / When alle Screenshots gespeichert / Then gibt das Script eine Zusammenfassung aus: Anzahl Screenshots, Verzeichnis-Pfad, Fehleranzahl 0; Exit-Code 0.

## Known Limitations

- **Selector-Fragilität:** `data-testid`-Attribute können bei UI-Umbauten fehlen. Fallback auf `waitForSelector('body')` verhindert einen Crash, liefert aber ggf. einen Ladescreen-Screenshot statt dem echten Screen.
- **Hash-Routing ist SvelteKit-intern:** `#weather`-Hash öffnet den Tab nur, wenn der SvelteKit-Router ihn als `initialTab` auswertet. Falls die Tab-Logik geändert wird, zeigen betroffene Screenshots immer den Default-Tab. `waitForTimeout(1000)` ist eine Heuristik, kein harter Wait.
- **Wizard-Cleanup:** Das Script bricht die Wizard-Session ohne Save ab. Wenn Staging einen serverseitigen Draft-Zustand speichert, könnte ein unvollständiger Wizard-Eintrag hängenbleiben. In der aktuellen Implementierung (clientseitiger State) ist das unbedenklich.
- **Keine Parallelisierung:** Desktop- und Mobile-Runs laufen sequenziell. Gesamtlaufzeit ca. 2–3 Minuten.

## Out of Scope

- Automatischer Diff mit SOLL-Screenshots (Phase 3)
- CI/CD-Integration (Aufruf ist manuell, Tooling-Script)
- Authentifizierung via ENV-Variable (Credentials sind Staging-only, kein Produktions-Risiko)
- Retry-Logik bei einzelnen fehlgeschlagenen Screenshots

## Test Coverage

Tests in `tests/tdd/test_epic_404_phase2_ist_screenshots.py`:

```
soll_screenshots_vorhanden
soll_naming_deckt_expected_desktop_ab
soll_naming_deckt_expected_mobile_ab
gpx_fixture_vorhanden
env_playwright_vorhanden
script_existiert
script_definiert_staging_url
script_definiert_trip_id
script_definiert_login_funktion
script_definiert_seed_trip_funktion
script_definiert_wizard_steps_funktion
script_enthaelt_gpx_upload_referenz
script_referenziert_alle_desktop_screenshots
script_referenziert_alle_mobile_screenshots
script_verwendet_desktop_viewport
script_verwendet_mobile_viewport
script_enthaelt_zusammenfassung
script_setzt_exit_code_bei_fehler
ist_screenshots_count_gesamt
```

## Changelog

- 2026-05-27: Initial spec erstellt. Playwright-Script für IST-Screenshots aller SvelteKit-Screens auf Staging; 15 Desktop- + 11 Mobile-Screenshots mit SOLL-konformer Namenskonvention; `seedTrip()` für Trip-Voraussetzung; Wizard-Sequenz mit GPX-Upload bis Step 4 ohne Save. Teil von Epic #404 Phase 2 von 5.
