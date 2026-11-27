---
entity_id: feat_3423_pruefkonto_zugang_e2e
type: feature
created: 2026-11-27
updated: 2026-11-27
status: draft
workflow: feat-3423-imac-seed-ids
version: "1.0"
tags: [e2e, staging, pruefzugang, test-infrastruktur]
---

# Prüfkonto-Zugang und Seed-IDs für Staging-E2E-Specs

## Approval

- [ ] Approved

## Purpose

Die vier Staging-Specs auf den Prüfkonto-Beispieldaten sollen vom iMac über `ssh henemm-pruefen spec-run` ohne Handarbeit laufen. Dafür wählt ein gemeinsamer Helfer das Prüfkonto und die Seed-IDs selbst, statt `ELEMENTLISTE_*` und ein auf das Prüfkonto gesetztes `GZ_AUTH_*` vorauszusetzen (Issue #3423, Punkt 4).

## Source

- **File:** `frontend/e2e/pruefkontoZugang.ts`
- **Identifier:** `pruefkontoZugang`, `zweitkontoZugang`, `seedIds` (plus reine Auswahlfunktionen)

> Schicht: ausschließlich Test-Infrastruktur unter `frontend/e2e/` und Doku. Kein Produktcode (Frontend-UI, Go, Python unberührt). Kein Trip/Compare-Pendant, keine Nutzerdaten-Schreibzugriffe (Lookup nur per GET), keine Kanalinhalte betroffen.

## Estimated Scope

- **LoC:** ~120
- **Files:** 7 (2 neu, 4 Specs mechanisch je ~5 Zeilen, 1 Doku). Über der 5-Dateien-Leitlinie, bewusst in einem Ticket: die Spec-Änderungen sind gleichförmig, Aufteilen würde nur den Nachweis verzögern.
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/e2e/stagingZugang.ts` | module | Muster der Env-Helfer (`ausUmgebung`), Basic-Auth-Zugang |
| `scripts/staging_pruefkonto_mockupdaten.py` | script | Quelle der Seed-Namen/-IDs (`TRIP_ID`, `VERGLEICH_NAME`); wird nicht geändert |
| `docs/runbooks/staging_pruefkonto_seed.md` | runbook | Fehlermeldung verweist darauf; Server-Weg mit `ELEMENTLISTE_*` bleibt gültig |
| `GET /api/trips/{id}`, `GET /api/compare/presets` | API | Lesender Lookup nach Login |
| henemm-infra `imac-pruefzugang.py` (`spec-run`) | extern | Reicht Staging-`.env` + `validator.env` durch; nur lesen, nicht ändern |

## Implementation Details

Neuer Helfer `frontend/e2e/pruefkontoZugang.ts`, nach dem Muster von `stagingZugang.ts`; alle Funktionen nehmen `env` als Parameter (nicht `process.env` direkt), damit sie mit Klartext-Daten testbar sind:

- `pruefkontoZugang(env)`: User/Pass aus `GZ_PRUEFKONTO_USER/PASS`, sonst `GZ_AUTH_USER/PASS`. Fehlt beides: klare Fehlermeldung.
- `zweitkontoZugang(env)`: `GZ_ZWEITKONTO_USER/PASS`, sonst `GZ_AUTH_USER/PASS`, aber nur, wenn dieser User vom Prüfkonto-User verschieden ist; sonst Fehler (Zweitkonto darf nie das Prüfkonto sein).
- `seedIds(api, env)`: `ELEMENTLISTE_TRIP_ID` / `ELEMENTLISTE_ORTE_ID` aus `env` haben Vorrang. Sonst nach Login: Trip-ID fest `gz2967-gr221-mallorca`, per `GET /api/trips/{id}` auf Status 200 geprüft; Vergleichs-ID = Eintrag mit Name „Münsterland" aus `GET /api/compare/presets`. Fehlt ein Seed, wirft `seedIds` einen Fehler, der das Seed-Skript und das Runbook nennt.
- Reine Auswahllogik (Konto-Wahl, Name-Treffer in der Vergleichsliste, env-Vorrang) als separate exportierte Funktionen; Unit-Tests ohne Mocks der eigenen Annahmen, nur mit Klartext-Daten. Testlauf wie `e2eTestUserResolution.test.ts` (Node-Testrunner laut dessen Kopfzeile).

Die vier Specs `hub-test-alarm`, `hub-send-menue`, `elementliste-abgleich`, `wsw-abnahme-3037` (je `*.staging.spec.ts`) beziehen Login-Zugang und Seed-IDs (bei wsw zusätzlich Zweitkonto) über den Helfer. Verhalten auf dem Server (env gesetzt, `GZ_AUTH_*` = Prüfkonto) bleibt unverändert.

`--lang en` über den iMac-Wrapper setzt `GZ_AUTH_*` auf das EN-Konto; die Prüfkonto-Specs nehmen weiterhin das Prüfkonto (nur dort liegen die Seed-Daten), die Sprache stellen sie selbst über das Profil.

Doku: `.claude/commands/e2e-verify.md`, Abschnitt „Außerhalb des Servers": Prüfkonto-Specs laufen über `spec-run` ohne Seed-Variablen; der Seed muss einmalig auf dem Server gelaufen sein (er ist persistent).

## Expected Behavior

- **Input:** Umgebung des Prüfzugangs (Staging-`.env`, `validator.env`) ohne `ELEMENTLISTE_*`.
- **Output:** Spec meldet sich als Prüfkonto an und findet Trip- und Vergleichs-ID selbst.
- **Side effects:** keine; Lookup ist rein lesend, kein Seed-Lauf über den Prüfzugang.

## Scope

- **Drin:** neuer e2e-Helfer `frontend/e2e/pruefkontoZugang.ts` samt Unit-Test; Umstellung der vier Prüfkonto-Staging-Specs (hub-test-alarm, hub-send-menue, elementliste-abgleich, wsw-abnahme-3037) auf den Helfer; Hinweis im Abschnitt „Außerhalb des Servers“ von `.claude/commands/e2e-verify.md`.
- **Nicht drin:** henemm-infra-Prüfzugang (Wrapper), Seed-Lauf über den Prüfzugang, Produktcode, übrige Staging-Specs.

## Test Plan

### Automated Tests (TDD RED)

- [ ] `pruefkontoZugang`: GIVEN `GZ_PRUEFKONTO_*` und `GZ_AUTH_*` gesetzt WHEN Zugang gewählt THEN Prüfkonto; nur `GZ_AUTH_*` THEN dessen Werte; beides leer THEN Fehler.
- [ ] `zweitkontoZugang`: GIVEN `GZ_ZWEITKONTO_*` WHEN gewählt THEN diese; ohne THEN `GZ_AUTH_*`; GIVEN `GZ_AUTH_USER` = Prüfkonto-User THEN klarer Fehler.
- [ ] Vergleichs-Auswahl: GIVEN Preset-Liste mit „Münsterland" und anderen WHEN gewählt THEN dessen ID; ohne Treffer THEN Fehler mit Seed-Hinweis.
- [ ] `seedIds`: GIVEN `ELEMENTLISTE_*` gesetzt WHEN aufgerufen THEN diese IDs ohne API-Aufruf; Trip-Lookup mit 404 THEN Fehler mit Seed-Hinweis.
- [ ] Nachweis-Lauf (siehe AC-5) gegen Staging.

## Acceptance Criteria

- **AC-1:** Given Prüfkonto- und geteilte Konto-Variablen sind beide gesetzt / When ein Staging-Spec den Zugang bestimmt / Then meldet er sich mit dem Prüfkonto an, und ohne Prüfkonto-Variablen mit `GZ_AUTH_*`, bei fehlenden beiden bricht er mit klarer Meldung ab.
  - Test: Unit-Test der reinen Konto-Wahl mit Klartext-Umgebungen (drei Fälle).
- **AC-2:** Given das Zweitkonto wird für den WSW-Abnahmelauf benötigt / When `GZ_ZWEITKONTO_*` fehlt und `GZ_AUTH_*` dem Prüfkonto entspricht / Then bricht der Lauf mit klarem Fehler ab, statt das Prüfkonto als Zweitkonto zu nutzen.
  - Test: Unit-Test `zweitkontoZugang` mit identischem und verschiedenem User.
- **AC-3:** Given `ELEMENTLISTE_TRIP_ID` und `ELEMENTLISTE_ORTE_ID` sind gesetzt (Server-Weg) / When die Seed-IDs bestimmt werden / Then gelten genau diese Werte ohne API-Abfrage; sind sie nicht gesetzt, werden Trip `gz2967-gr221-mallorca` und der Vergleich „Münsterland" nach dem Login lesend gefunden.
  - Test: Unit-Test env-Vorrang und Name-Treffer in der Preset-Liste mit Klartext-Daten.
- **AC-4:** Given der Seed fehlt auf Staging / When ein Spec die IDs sucht / Then bricht er mit einer Meldung ab, die das Seed-Skript und das Runbook nennt, statt mit leerer ID weiterzulaufen.
  - Test: Unit-Test: Trip-Lookup liefert 404 bzw. Liste ohne „Münsterland" ergibt Fehlertext mit Skript- und Runbook-Verweis.
- **AC-5:** Given der Branch ist gemergt und auf Staging ausgerollt / When vom iMac `ssh henemm-pruefen spec-run playwright.3441-test-alarm.staging.config.ts e2e/hub-test-alarm.staging.spec.ts` läuft / Then endet der Lauf grün ohne Rückfrage, und `write-verdict` via `ssh henemm-pruefen` gelingt (Issue #3423 Punkt 4).
  - Test: echter Durchlauf vom iMac gegen Staging; Exit 0 beider Aufrufe ist der Nachweis.
- **AC-6:** Given die vier Specs laufen auf dem Server mit gesetzten `ELEMENTLISTE_*` und `GZ_AUTH_*` = Prüfkonto / When sie über den Helfer starten / Then verhalten sie sich wie zuvor (gleiche Konten, gleiche IDs).
  - Test: Lauf der Specs auf dem Server in `/e2e-verify`; Unit-Test env-Vorrang (AC-3).
- **AC-7:** Given ein Lauf mit `--lang en` setzt `GZ_AUTH_*` auf das EN-Konto / When ein Prüfkonto-Spec startet / Then nutzt er weiterhin das Prüfkonto.
  - Test: Unit-Test Konto-Wahl mit `GZ_PRUEFKONTO_*` neben abweichendem `GZ_AUTH_*`.
- **AC-8:** Given ein Entwickler liest den Abschnitt „Außerhalb des Servers" in `/e2e-verify` / When er ein Prüfkonto-Spec vom iMac starten will / Then steht dort, dass `spec-run` ohne Seed-Variablen genügt und der Seed einmalig auf dem Server gelaufen sein muss.
  - Test: `# doc-compliance-test` auf den Doku-Abschnitt.

## Definition of Done

- Alle ACs durch Unit-Tests bzw. Doku-Test grün belegt; vorher rot nachgewiesen.
- Adversary-Verdict VERIFIED inkl. Mutations-Gegenprobe.
- PR mit allen CI-Checks grün gemergt.
- AC-5: Nachweis-Lauf vom iMac über `ssh henemm-pruefen` (spec-run grün, write-verdict erfolgreich) ohne Rückfrage; Ergebnis in #3423 und henemm/henemm-infra#487 kommentiert, #3423 und #3402 geschlossen. #3415 ist bereits geschlossen (27.11.2026 als Duplikat von #3402); bei #3402 wird nur noch der Nachweis nachgetragen.

## Known Limitations

- Nachweis (AC-5) ist erst nach Merge und Staging-Deploy möglich.
- Der Seed selbst läuft weiter nur auf dem Server (braucht Core-Secret/Loopback); fehlt er, bricht der Lauf mit Hinweis ab.
- Außerhalb des Umfangs: Änderungen am henemm-infra-Wrapper, Seed-Lauf über den Prüfzugang, Produktcode.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Test-Infrastruktur im bestehenden Muster von `stagingZugang.ts`; keine Entscheidungsfläche (Kanäle, Provider, Datenmodell, Auth) betroffen.

## Changelog

- 2026-11-27: Initial spec created (Issue #3423)
