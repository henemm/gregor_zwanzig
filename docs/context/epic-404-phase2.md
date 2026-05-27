# Context: Epic #404 Phase 2 — IST-Screenshots erzeugen

## Request Summary
Phase 2 des SOLL-IST-Audits: Playwright fährt alle SvelteKit-Routen gegen Staging
(eingeloggt, echte Daten) ab und erstellt IST-Screenshots in Desktop (1440px) und
Mobile (390px) — als Basis für den SOLL-IST-Vergleich in Phase 3.

## Voraussetzungen — alle erfüllt ✅
- #392 (organisms.jsx/metrics-editor): CLOSED
- #396 (Archiv-Statistiken): CLOSED
- #402 (Trips Atomic Migration): CLOSED
- #403 (TripTabs Segmented): CLOSED

## Phase-1-Ergebnis (SOLL-Screenshots)
- Verzeichnis: `claude-code-handoff/soll-audit-2026-05-27/soll-screenshots/`
- 50 PNGs: desktop-*, mobile-m-*, komponenten-*
- Script: `claude-code-handoff/soll-audit-2026-05-27/take-soll-screenshots.js`

## Staging
- URL: `https://staging.gregor20.henemm.com`
- Status: HTTP 200 ✅
- Login: user=`default`, pass=`ZfDOKJTre8udPtG` (aus `frontend/.env.playwright`)
- Login-Mechanismus: `POST /login` (global.setup.ts Muster)

## Playwright-Setup
- Binary: `frontend/node_modules/.bin/playwright` ✅
- Konfig: `frontend/playwright.config.ts` (baseURL localhost:4173 — für IST-Audit anpassen auf Staging)
- Login-State: `frontend/playwright/.auth/admin.json`
- E2E-Tests: `frontend/e2e/*.spec.ts` (Referenz für Login + Navigation)

## Zu erfassende Routes (IST-Screens)
| Route | Screen-Name | Notes |
|-------|-------------|-------|
| `/` | home | Startseite/Cockpit |
| `/trips` | trips-list | Trips-Übersicht |
| `/trips/[id]` | trip-detail | Mit realem Trip |
| `/trips/new` | trip-wizard | Step 1–4 |
| `/compare` | compare | Orts-Vergleich |
| `/archiv` | archiv | Archivierte Touren |
| `/settings` | settings | Einstellungen |
| `/locations` | locations | (optional) |

## IST-Output-Verzeichnis
`claude-code-handoff/soll-audit-2026-05-27/ist-screenshots/`

## Script-Ansatz
Neues Script analog `take-soll-screenshots.js`:
- Playwright gegen Staging (nicht localhost)
- Login via Credentials aus `.env.playwright`
- Jede Route in Desktop (1440×900) + Mobile (390×844)
- Screenshot: fullPage für lange Seiten, viewport für Screens mit Scroll

## Referenz-Patterns
- `frontend/e2e/global.setup.ts` — Login + Storage-State
- `frontend/e2e/helpers.ts` — Navigation-Helfer
- `claude-code-handoff/soll-audit-2026-05-27/take-soll-screenshots.js` — SOLL-Script-Muster
- `.claude/hooks/e2e_browser_test.py` — Playwright Python-Wrapper

## Risiken
- Trip-Detail braucht echte Trip-ID → muss aus API gelesen werden
- Trip-Wizard läuft durch Steps 1–4 → Navigation erforderlich
- Login-Session muss persistiert werden (storageState)
- Staging könnte gecachte Komponenten haben — vor Start Deploy-Status prüfen
