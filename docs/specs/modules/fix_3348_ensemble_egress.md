---
entity_id: fix_3348_ensemble_egress
type: bugfix
created: 2026-11-26
updated: 2026-11-26
status: draft
version: "1.0"
tags: [egress, isolation, staging, ensemble, grosswetterlage]
workflow: fix-3348-ensemble-egress
---

# Ensemble-Host im Egress-Inventar (Bug #3348)

## Approval

- [ ] Approved

## Purpose

Der Egress-Wächter sperrt auf Staging den Ensemble-Host `ensemble-api.open-meteo.com`, weil er nicht im Inventar steht. Dadurch fehlen dort Großwetterlage, Verlässlichkeits-Hinweis und Ensemble-Gewitter-Mehrheit in jeder Trip-Mail. Der Host wird mit derselben Isolationsart wie `api.open-meteo.com` (TEST_ACCESS) deklariert.

## Source

- **File:** `src/app/egress_guard.py` (Zwilling: `internal/egress/inventory.go`)
- **Identifier:** `INVENTORY` (Python) bzw. Inventar-Map (Go)

> Schicht: Python-Core (`src/app/`) und Go-API (`internal/egress/`), keine Frontend-Änderung. Kein Trip/Ortsvergleich-Pendant, keine Nutzerdaten bewegt (keine Zwei-Nutzer-Prüfung nötig). Kanäle: Briefing-Inhalt (Großwetterlage) wird auf Staging wieder wie in Prod erzeugt; keine Änderung der Kanal-Formate.

## Estimated Scope

- **LoC:** ca. +60 (davon ca. 55 Test)
- **Files:** 4
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| egress_guard (Spec `docs/specs/modules/egress_guard.md`) | module | Inventar-Tabelle, Isolationsarten, Guard-Semantik |
| `src/providers/openmeteo.py` (`_fetch_ensemble_spread`) | module | Aufrufer des Ensemble-Hosts |
| `src/services/weather_pattern.py` | module | leitet Großwetterlage aus `confidence_pct` ab |
| `tests/test_egress_inventory_drift.py` | test | erzwingt Deckungsgleichheit Python/Go |
| `internal/egress/guard_test.go` | test | Go-Guard-Tests |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| src/app/egress_guard.py | MODIFY | `"ensemble-api.open-meteo.com": IsolationKind.TEST_ACCESS` im INVENTORY |
| internal/egress/inventory.go | MODIFY | gleicher Eintrag `TestAccess` (Drift-Test) |
| docs/specs/modules/egress_guard.md | MODIFY | Inventar-Tabelle um Zeile ergänzen |
| tests/tdd/test_issue_3348_ensemble_egress.py | CREATE | Verhaltenstest mit Sentinel-Transport |

## Implementation Details

Ursachenkette: `_fetch_ensemble_spread` ruft `{host}/v1/ensemble` per httpx. Der Guard wirft für undeklarierte Hosts `EgressBlockedError`; `openmeteo.py` fängt ihn ab (`Ensemble fetch failed`), `confidence_pct` bleibt `None`, `compute_stability` liefert `None`, die Mail enthält keinen Großwetterlage-Block.

Fix: Host als TEST_ACCESS in beiden Zwillingslisten eintragen (Muster `opendata.dwd.de`, #1457). Kein weiterer Code-Pfad ändert sich. Prod ist unberührt, weil `install_egress_guard` dort ein No-Op ist (Prod-Log: 0 Sperrmeldungen).

Test (TDD RED vor dem Fix): Guard im Test-Modus installieren, httpx-Sentinel wie in `tests/tdd/test_egress_guard.py`, dann den echten Ensemble-Abrufweg des Open-Meteo-Providers ausführen. Keine Mocks und kein `patch`.

## Expected Behavior

- **Input:** Ensemble-Abruf an `ensemble-api.open-meteo.com` bei installiertem Guard (Test/Staging).
- **Output:** Anfrage erreicht den Transport, `confidence_pct` wird gesetzt, Großwetterlage entsteht.
- **Side effects:** Staging macht zusätzliche kostenfreie Open-Meteo-Ensemble-Abrufe.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN Guard im Test-Modus installiert / WHEN der Ensemble-Abruf des Open-Meteo-Providers läuft / THEN feuert der Sentinel-Transport und kein `EgressBlockedError` wird geworfen (vorher rot).
- [ ] Test 2: GIVEN Guard installiert / WHEN ein undeklarierter Nachbar-Host gerufen wird / THEN `EgressBlockedError`, Sentinel feuert nicht.
- [ ] Test 3: GIVEN Warn-Hosts im Inventar / WHEN Inventar geprüft wird / THEN bleiben sie BLOCKED.
- [ ] Test 4: Drift-Test `tests/test_egress_inventory_drift.py` bleibt grün, Host in beiden Listen TEST_ACCESS.
- [ ] Test 5: GIVEN Prod-Modus / WHEN `install_egress_guard` läuft / THEN wird nichts gepatcht.
- [ ] Staging-E2E (`/e2e-verify`, `briefing_mail_validator`): siehe AC-5.

## Acceptance Criteria

- **AC-1:** Given der Egress-Wächter ist im Test-/Staging-Modus installiert / When der Open-Meteo-Provider den Ensemble-Abruf an `ensemble-api.open-meteo.com` ausführt / Then erreicht die Anfrage den Transport (Sentinel feuert), es wird kein `EgressBlockedError` geworfen und die `confidence`-Werte werden gesetzt.
  - Test: Verhaltenstest mit Sentinel-Transport über den echten Abrufweg des Providers, vorher rot.

- **AC-2:** Given der Egress-Wächter ist installiert / When ein nicht deklarierter Host oder ein Warn-Feed-Host gerufen wird / Then bleibt er gesperrt (`EgressBlockedError`, Transport wird nicht erreicht).
  - Test: Gegenprobe mit undeklariertem Nachbar-Host und einem Warn-Host, beide bleiben BLOCKED.

- **AC-3:** Given Python- und Go-Inventar des Wächters / When der Drift-Test beide Listen vergleicht / Then sind sie deckungsgleich und der Ensemble-Host steht in beiden als TEST_ACCESS.
  - Test: `tests/test_egress_inventory_drift.py` grün, plus Go-Guard-Test für den neuen Host.

- **AC-4:** Given die Produktion läuft ohne aktiven Wächter / When der Fix ausgeliefert ist / Then ändert sich in Prod nichts: Wächter bleibt No-Op und das Prod-Log zeigt weiterhin keine Sperrmeldung.
  - Test: Prod-Modus-Test (kein Patch installiert) und Prod-Log nach Deploy ohne `egress blocked`.

- **AC-5:** Given ein Staging-Trip mit Folge-Etappen / When die Trip-Mail mit `show_stability=true` bzw. `false` zugestellt wird / Then enthält die Mail mit `true` den Großwetterlage-Block, mit `false` nicht, und das Staging-Log zeigt nach dem Lauf keine neue Sperrmeldung für `ensemble-api`.
  - Test: Staging-E2E mit `briefing_mail_validator` gegen die echt zugestellte Mail, danach Staging-Log prüfen.

## Definition of Done

- AC-1 bis AC-3 durch automatische Tests belegt (vorher rot, nachher grün), Kern-Schicht grün
- AC-4: Prod-Log nach dem Deploy ohne `egress blocked`/`Ensemble fetch failed`, Selftest Exit 0
- AC-5: Staging-Mail per `briefing_mail_validator` geprüft, An- und Aus-Fall, Staging-Log ohne neue `ensemble-api`-Sperre; Ergebnis im Issue #3348 dokumentiert
- Adversary-Verdict VERIFIED, alle 6 CI-Checks grün, ausgeliefert

## Known Limitations

- Nutzerseitig wirksam nur auf Staging; Prod war nie betroffen.
- Weitere künftig neu gerufene Hosts brauchen weiterhin einen eigenen Inventar-Eintrag (Tripwire bleibt absichtlich streng).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Ergänzung des bestehenden Inventars nach etabliertem Muster (#1457); keine neue Entscheidungsfläche.

## Changelog

- 2026-11-26: Initial spec created
