---
entity_id: fix_1329_e2e_data_hygiene
type: module
created: 2026-07-20
updated: 2026-07-20
status: draft
version: "1.0"
tags: [e2e, staging, cleanup, playwright]
---

# E2E-Datenhygiene: selbstraeumende Playwright-Suites + einmaliger Staging-Raeumlauf (#1329 Massnahme B)

## Approval

- [x] Approved (PO-Freigabe 2026-07-20, vollständiger Migrations-Scope)

## Purpose

Playwright-E2E-Laeufe gegen Staging legen ueber `/api/locations`, `/api/compare/presets` und
`/api/trips` Wegwerf-Objekte an, deren Aufraeumen bislang unvollstaendig, dupliziert und
fehlertolerant-verschluckend implementiert ist. Dadurch haeufen sich Waisen-Datensaetze auf
Staging an (aktuell 706 Orte / 429 Presets gegenueber 31/19 auf Prod) und verbrauchen u.a.
Anteil am taeglichen open-meteo-Kontingent. Dieses Modul haertet die Suite so, dass jeder Lauf
seine eigenen Testdaten unter einem reservierten Praefix restlos entfernt — inklusive
Sicherheitsnetz fuer abbrechende Tests — und bereinigt einmalig den bestehenden Bestand.

## Source

- **File:** `frontend/e2e/helpers.ts`
- **Identifier:** neue Funktionen `createTestLocation()`, `createTestComparePreset()`,
  `createTestTrip()` (geteilter, auto-registrierender Helfer)

> Schicht: **Frontend / E2E-Testinfrastruktur** — `frontend/e2e/*.ts` (Playwright,
> nicht Teil der produktiven SvelteKit-Oberflaeche). Kein Go-/Python-Code betroffen.
> Der Scheduler-Pfad (`internal/scheduler/`, `cmd/server/main.go`) ist explizit
> AUSSERHALB des Scopes — Massnahme A hat `SchedulerEnabled = Env != "staging"`
> bereits umgesetzt und deckt das Polling-Kontingent-Ziel ab.

## Estimated Scope

- **LoC:** ~150-220 fuer Helfer + `global.teardown.ts` + Config-Verdrahtung; **zusaetzlich
  ~80-150 LoC** fuer die Migration ALLER betroffenen Dateien. Gesamt realistisch **230-370 LoC**.
  **PO-Entscheidung 2026-07-20: VOLLSTAENDIGE Migration** (alle 12 Dateien mit dupliziertem
  `createLocation()` PLUS die ~10 garantierten-Leak-Dateien) — `loc_limit_override` auf 400
  gesetzt (PO-Freigabe liegt vor). Keine reduzierte Fallback-Variante.
- **Files:** 1 neu (`frontend/e2e/global.teardown.ts`), 1 erweitert (`frontend/e2e/helpers.ts`),
  `frontend/playwright.config.ts` + 4 `frontend/e2e/playwright.*.staging.config.ts`
  (globalTeardown verdrahten), 12 Spec-Dateien mit dupliziertem `createLocation()`
  (auf Helfer migrieren), 8-10 Spec-/Setup-Dateien mit unregistrierten Leaks
  (`compare-editor-slice3/4`, `issue-682/718/758/951`, `feat-880`, `versand-tab-vergleich`,
  `layout-tab-vergleich`, `orts-vergleich-c4`) migrieren.
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `POST/DELETE /api/locations` (Go-Handler `internal/handler/location.go`) | REST-API | Helfer legt Test-Orte an/loescht sie |
| `POST/GET/DELETE /api/compare/presets` (Go-Handler) | REST-API | Helfer legt Test-Presets an/loescht sie; Praesenz-Referenz auf Ort verursacht 409 bei falscher Loeschreihenfolge |
| `POST/DELETE /api/trips` (Go-Handler) | REST-API | Helfer legt Test-Trips an/loescht sie |
| `frontend/e2e/global.setup.ts` | Bestand | Vorbild-Struktur (Auth + Seed), unveraendert; `global.teardown.ts` ist das fehlende Gegenstueck |
| `frontend/e2e/prodUrlGuard.ts` (`assertNotProdBaseURL`) | Bestand | Muss auch im Teardown greifen — nie gegen Prod loeschen |

## Implementation Details

**1. Geteilter Helfer (`frontend/e2e/helpers.ts`):**
`createTestLocation(request, opts)`, `createTestComparePreset(request, opts)`,
`createTestTrip(request, opts)` — jede Funktion generiert einen Namen/ID mit reserviertem
Praefix `E2E-GZ-` + Zeitstempel/Random-Suffix (kollisionsfrei, ersetzt `Loc-Mobile-A`-Stil),
ruft die passende REST-API auf und traegt die erzeugte ID in ein modul-internes Set ein
(`registerForCleanup(kind, id)`). Ein optionaler `afterEach`-Hook (oder expliziter
`cleanupNow()`-Export fuer Specs, die pro Testfall raeumen wollen) leert das Set und loescht
in der Reihenfolge Presets/Trips → Orte. DELETE-Fehler werden geloggt, nicht mehr stillschweigend
verschluckt (kein `.catch(() => {})` ohne Log-Zeile).

**2. `frontend/e2e/global.teardown.ts`** (neu, Vorbild `global.setup.ts`): laeuft als
`globalTeardown` nach Abschluss der gesamten Suite (auch bei Testfehlern/Abbruch — Playwright
fuehrt `globalTeardown` unabhaengig vom Testergebnis aus). Guard `assertNotProdBaseURL` zuerst.
Danach: `GET /api/compare/presets` + `GET /api/trips` + `GET /api/locations`, filtert auf
reserviertes Praefix `E2E-GZ-`, loescht in Reihenfolge Presets → Trips → Orte (referenzierende
Objekte zuerst, behebt die 409-Waisen aus Root-Cause #3/#4).

**3. Config-Verdrahtung:** `globalTeardown: './e2e/global.teardown.ts'` (bzw. relativer Pfad je
Config) in `frontend/playwright.config.ts` UND den 4 bestehenden
`frontend/e2e/playwright.*.staging.config.ts`. `frontend/playwright.config.ts` ist trotz
lokaler `baseURL` relevant, weil dessen Default `GZ_API_BASE=http://localhost:8091` real gegen
die Staging-Go-API proxied (dokumentierter Bestand, kein neuer Fund) — die Haupt-Suite ist damit
mit-verantwortlich fuer den Waisen-Zuwachs, nicht nur die vier expliziten Staging-Configs.

**4. Migration:** die 12 Dateien mit dupliziertem `createLocation()` rufen stattdessen
`createTestLocation()` aus `helpers.ts` auf (Funktionskoerper entfernen, Import ergaenzen,
Aufrufstellen anpassen). Die 8-10 garantierten-Leak-Dateien (kein Cleanup vorhanden) werden auf
denselben Helfer umgestellt, wodurch sie automatisch am Teardown-Set teilnehmen.

**5. Einmaliger Raeumlauf (Ops-Schritt, kein Code):** auf dem Staging-Host als `claude-gregor`
Backup ziehen, dann per REST-Skript (nicht Teil dieser Spec als Testcode, sondern als
dokumentierter Befehlsablauf im Validierungs-Abschnitt) Allowlist-erhaltend loeschen: die 3
`global.setup.ts`-Seeds (`e2e-loc-innsbruck/stubai/zillertal`), das Validator-Konto und dessen
Objekte bleiben, der Rest wird entfernt (Presets vor Orten, Trips vor Orten).

## Expected Behavior

- **Input:** Playwright-Testlauf (lokal gegen Staging-API oder explizite `*.staging.config.ts`),
  der ueber die neuen Helfer Orte/Presets/Trips anlegt.
- **Output:** Nach Abschluss des gesamten Laufs (Erfolg oder Abbruch) existieren auf dem
  Server keine Objekte mit Praefix `E2E-GZ-` mehr ausser den drei fest geseedeten
  `global.setup.ts`-Orten (die tragen bewusst kein `E2E-GZ-`-Praefix und sind vom Scope
  dieser Spec unberuehrt).
- **Side effects:** Reduzierter Datenbestand auf Staging (Speicher, API-Antwortzeiten fuer
  Listen-Endpoints, Anteil am open-meteo-Tageskontingent bei Wetter-Abrufen fuer Testorte).

## Acceptance Criteria

- **AC-1:** Given eine Playwright-Suite legt ueber `createTestLocation()`/`createTestComparePreset()` mehrere Orte und ein referenzierendes Preset an / When die Suite regulaer durchlaeuft und `globalTeardown` abschliesst / Then liefert `GET /api/locations` und `GET /api/compare/presets` fuer den Testnutzer 0 Objekte mit Praefix `E2E-GZ-`.
  - Test: Vor dem Lauf und nach Abschluss von `globalTeardown` wird `GET /api/locations` bzw. `GET /api/compare/presets` real aufgerufen und die Anzahl der Praefix-Treffer verglichen (0 nach Lauf) — kein Quelltext-Scan.

- **AC-2:** Given ein Testfall bricht absichtlich nach dem Anlegen eines Test-Orts mit einer fehlschlagenden Assertion ab / When die Suite trotzdem beendet wird (Playwright fuehrt `globalTeardown` unabhaengig vom Testergebnis aus) / Then ist der zuvor angelegte Ort danach ueber `GET /api/locations/{id}` nicht mehr auffindbar (404).
  - Test: Ein dedizierter E2E-Testfall legt einen Ort an, wirft danach absichtlich `expect(false).toBeTruthy()`, die Suite wird regulaer beendet; anschliessend wird per REST-Aufruf `GET /api/locations/{id}` auf 404 geprueft — beweist, dass das Sicherheitsnetz auch bei Testfehlern greift.

- **AC-3:** Given ein Testfall legt einen Ort UND ein Compare-Preset an, das diesen Ort referenziert / When `globalTeardown` bzw. der Helfer-Cleanup laeuft / Then wird zuerst das Preset, danach der Ort geloescht, ohne dass die Ort-Loeschung mit HTTP 409 fehlschlaegt.
  - Test: `DELETE /api/locations/{id}` wird nach Ablauf des Cleanups fuer diesen konkreten Ort ausgefuehrt und liefert 404 (bereits weg) statt 409 (referenziert) — der Statuscode wird real geprueft, kein geloggter Fehler wird stillschweigend hingenommen.

- **AC-4 (Ops, manuell auf Staging verifiziert):** Given der Staging-Bestand vor dem Raeumlauf enthaelt 706 Orte und 429 Presets / When der einmalige Allowlist-erhaltende Raeumlauf (mit vorherigem Backup) als `claude-gregor` durchgefuehrt wird / Then faellt `GET /api/locations` (Admin-/Validator-Sicht) auf die Allowlist-Groesse (3 Seed-Orte + Validator-Konto-Objekte), und ein anschliessender regulaerer Login samt Trip-Cockpit-Aufruf funktioniert unveraendert.
  - Test: `curl` gegen `GET /api/locations` (mit Validator-Basic-Auth) vor und nach dem Raeumlauf, Anzahl-Vergleich; zusaetzlich manueller Login-Smoke-Test auf `https://staging.gregor20.henemm.com`, dass Seeds und Validator-Konto weiterhin funktionieren. Dieser AC ist ein einmaliger Ops-Schritt, kein automatisierter Testfall in der CI-Suite.

## Known Limitations

- Die Migration in dieser Spec deckt (PO-Wahl: vollstaendig) ALLE 12 Dateien mit dupliziertem
  `createLocation()` und ALLE ~8-10 garantierten-Leak-Dateien ab. Weitere, bislang nicht
  identifizierte Alt-Spec-Dateien mit eigenem, abweichendem Anlage-Code werden NICHT einzeln
  migriert —
  fuer sie greift ausschliesslich das `global.teardown.ts`-Sicherheitsnetz (per Praefix-Scan),
  sofern sie den reservierten Praefix tatsaechlich verwenden. Specs, die Objekte ganz ohne
  Praefix anlegen, bleiben ausserhalb der Reichweite dieser Massnahme (Altlast, nicht
  rueckwirkend behebbar ohne Einzelaudit — vgl. Root-Cause Punkt 5 im Kontext-Dokument).
- Das reservierte Praefix `E2E-GZ-` muss so gewaehlt sein, dass es mit keinem denkbaren
  echten Nutzer-Ortsnamen kollidiert (Grossschreibung + Bindestrich-Suffix, kein natuerliches
  Ortsnamen-Muster).
- Der Scheduler-Namespace-Skip ist bewusst NICHT Teil dieser Spec (siehe Purpose/Source) —
  durch Massnahme A bereits redundant.
- AC-4 ist ein manueller, einmaliger Ops-Schritt und wird nicht durch eine automatisierte
  Testdatei abgedeckt; die Verifikation erfolgt in der manuellen Staging-Validierung vor
  Deploy-Freigabe.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** `globalTeardown` ist ein etabliertes, dokumentiertes Playwright-Kernfeature
  (Gegenstueck zu `globalSetup`, hier `global.setup.ts`) und wird lediglich analog zum
  bestehenden Muster eingefuehrt. Keine neue Architekturentscheidung, keine neue Technologie,
  keine Cross-Cutting-Concern-Einfuehrung — reine Testinfrastruktur-Konsolidierung.

## Changelog

- 2026-07-20: Initial spec created
