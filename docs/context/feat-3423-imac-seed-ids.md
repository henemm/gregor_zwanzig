# Context: feat-3423-imac-seed-ids

Issue #3423 (Punkt 4: echter Ticket-Durchlauf vom iMac ohne Rückfrage). Vorarbeit PR #3428 (Doku `/e2e-verify` „Außerhalb des Servers“).

## Request Summary

Probe am 2026-11-27 auf dem iMac (Staging = main 413cb7647):
- `ssh henemm-pruefen rev gregor-staging` → Exit 0, ohne Rückfrage.
- `ssh henemm-pruefen mail-pruefen trip de` → Validator Exit 0 (PASS).
- `ssh henemm-pruefen spec-run playwright.3441-test-alarm.staging.config.ts e2e/hub-test-alarm.staging.spec.ts`
  → Exit 1: `Vorbedingung: Seed-ID für route` (ELEMENTLISTE_TRIP_ID leer), 7 Tests nicht gelaufen.

Ursache: Specs auf den Prüfkonto-Beispieldaten erwarten (a) `ELEMENTLISTE_TRIP_ID`/`ELEMENTLISTE_ORTE_ID`
aus der stdout des Seed-Skripts und (b) `GZ_AUTH_USER/PASS` = Prüfkonto. Auf dem Server setzt der Mensch/Agent
beides von Hand (Runbook `docs/runbooks/staging_pruefkonto_seed.md:41-44`). Der Prüfzugang `spec-run`
(henemm-infra `scripts/imac-pruefzugang.py:388-398`) reicht nur Staging-`.env` + `.claude/validator.env` durch:
dort ist `GZ_AUTH_*` das geteilte Konto `default`, `GZ_PRUEFKONTO_*` vorhanden, `ELEMENTLISTE_*` nicht.
Bei `--lang en` überschreibt der Wrapper `GZ_AUTH_*` mit `GZ_E2E_EN_*`.

## Related Files

- `frontend/e2e/hub-test-alarm.staging.spec.ts:18,24-37` — IDS aus env, Login mit GZ_AUTH_*
- `frontend/e2e/hub-send-menue.staging.spec.ts:27-28,45-46` — gleiches Muster
- `frontend/e2e/elementliste-abgleich.staging.spec.ts:394-398` — gleiches Muster (Abgleich-Werkzeug)
- `frontend/e2e/wsw-abnahme-3037.staging.spec.ts` — nur GZ_AUTH_*/GZ_ZWEITKONTO_*, keine Seed-IDs (nicht betroffen? prüfen)
- `frontend/e2e/stagingZugang.ts` — bestehender Helfer `ausUmgebung()` für Basic-Auth-Zugang
- `scripts/staging_pruefkonto_mockupdaten.py:60,65,581-582` — Namen „GR221 Mallorca“ / „Münsterland“, Ausgabe der IDs
- `.claude/commands/e2e-verify.md:360-…` — Abschnitt „Außerhalb des Servers“
- henemm-infra `scripts/imac-pruefzugang.py` (fremdes Repo, nur lesen)

## Existing Patterns

- `stagingZugang.ts` liest Zugangsdaten mit Fallback-Kette aus env (`ausUmgebung(primär, ersatz)`).
- Seed ist idempotent und persistent; Prüfkonto-Daten liegen dauerhaft auf Staging.
- Trip-/Vergleichslisten per `GET /api/trips` bzw. `GET /api/compare…` nach Login abrufbar.

## Lösungsrichtung (für Analyse)

Gemeinsamer e2e-Helfer „Prüfkonto-Zugang“: Zugangsdaten bevorzugt `GZ_PRUEFKONTO_*` (Fallback `GZ_AUTH_*`),
IDs bevorzugt aus env, sonst nach Login per Name aus der Liste des Prüfkontos (nicht archiviert).
Die drei Specs nutzen ihn. Alternative (verworfen, fremdes Repo + Server-Schreibrecht): Wrapper ruft Seed.

## Dependencies / Dependents

- Server-Sitzungen, die Runbook-Weg nutzen, dürfen nicht brechen (env-IDs haben Vorrang).
- EN-Lauf: Wrapper setzt GZ_AUTH_* auf EN-Konto — Verhalten der betroffenen Specs bei `--lang en` klären.

## Risks

- Falsches Konto (default statt Prüfkonto) → Scheinabweichungen / Schreiben ins geteilte Konto.
- Kein Seed auf Staging → klare Fehlermeldung statt Leer-ID.
- Specs müssen eingecheckt sein; Prüfung nur per spec-run nach Merge/Deploy des Branches auf Staging möglich.

## Analysis

**Type:** Feature (Test-Infrastruktur), kein Produktcode.

**Befund ergänzt:** Betroffen sind vier Staging-Specs, nicht drei: `wsw-abnahme-3037.staging.spec.ts:124-129`
(`seedId()`) nutzt ebenfalls `ELEMENTLISTE_*` und braucht zusätzlich `GZ_ZWEITKONTO_*`
(= geteiltes Konto). Seed-IDs: Trip fest `gz2967-gr221-mallorca` (Seed-Skript Z. 59), Orts-Vergleich
server-vergeben, Treffer per Name „Münsterland“ aus `GET /api/compare/presets` (Seed-Skript Z. 459-460).

### Affected Files

| Datei | Change |
|---|---|
| `frontend/e2e/pruefkontoZugang.ts` | CREATE: `pruefkontoZugang(env)` (User/Pass: `GZ_PRUEFKONTO_*` vor `GZ_AUTH_*`), `zweitkontoZugang(env)` (`GZ_ZWEITKONTO_*`, sonst `GZ_AUTH_*`, wenn ≠ Prüfkonto), `seedIds(api, env)` (env vor API-Lookup; Fehler mit klarer Meldung, wenn Seed fehlt) |
| `frontend/e2e/pruefkontoZugang.test.ts` | CREATE: Unit-Tests der reinen Auswahl-Logik (Konto-Wahl, Vergleich per Name, env-Vorrang) |
| `frontend/e2e/hub-test-alarm.staging.spec.ts` | MODIFY: Login + IDS über Helfer |
| `frontend/e2e/hub-send-menue.staging.spec.ts` | MODIFY: dito |
| `frontend/e2e/elementliste-abgleich.staging.spec.ts` | MODIFY: dito |
| `frontend/e2e/wsw-abnahme-3037.staging.spec.ts` | MODIFY: `seedId()`/Zweitkonto über Helfer |
| `.claude/commands/e2e-verify.md` | MODIFY (Doku, 2-3 Zeilen): Prüfkonto-Specs laufen über `spec-run` ohne Seed-Variablen |

Scope: 7 Dateien (2 neu, 4 Specs je ~5 Zeilen, 1 Doku), ~120 LoC. Liegt über der 5-Dateien-Leitlinie, aber
die Spec-Änderungen sind mechanisch gleich; Aufteilen würde den Nachweis (Punkt 4) nur verzögern → ein Ticket.

### Technical Approach

- Reihenfolge: Helfer + Unit-Tests (RED) → Specs umstellen → Doku.
- env-IDs behalten Vorrang ⇒ Server-Runbook-Weg unverändert.
- `--lang en`: Wrapper setzt `GZ_AUTH_*` auf EN-Konto; Prüfkonto-Specs nehmen trotzdem das Prüfkonto (nur dort liegen die Seed-Daten); Sprache stellen die Specs selbst über das Profil.
- Kein Schreiben: Lookup nur lesend (GET). Kein Seed-Lauf über den Prüfzugang (Seed braucht Core-Secret/Loopback).
- Nachweis: nach Merge+Staging-Deploy `ssh henemm-pruefen spec-run playwright.3441-test-alarm.staging.config.ts e2e/hub-test-alarm.staging.spec.ts` grün, danach `write-verdict` vom iMac → das ist der echte Durchlauf (Punkt 4).

### Risks

- Fallback auf `GZ_AUTH_*` (geteiltes Konto) ohne Prüfkonto-Variablen: Lookup findet keinen Seed → klarer Fehler statt Scheinabweichung.
- Zweitkonto-Fallback darf nie gleich dem Prüfkonto sein (bestehende Prüfung bleibt).

### Open Questions

Keine Produktfrage; rein technisch.
