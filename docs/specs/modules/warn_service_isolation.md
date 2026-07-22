---
entity_id: warn_service_isolation
type: module
created: 2026-07-22
updated: 2026-07-22
status: draft
version: "1.0"
tags: [egress, isolation, warn-services, staging, "1348", "1337"]
workflow: feat-1348-warn-isolation-2b
---

<!-- Issue #1348 Scheibe 2b — Test/Staging von den echten Warn-APIs abschneiden -->

# Warn-Dienst-Isolation (Scheibe 2b)

## Approval
- [ ] Approved

## Purpose
Test/Staging dürfen die echten amtlichen Warn-APIs nicht mehr erreichen
(Kontingent-Schonung des geteilten Server-IP/Key). Umsetzung im bestehenden
Egress-Wächter (Scheibe A): die 4 Warn-Host von `TEST_ACCESS` auf `BLOCKED`.
Nicht-Live-Tests, die die echten APIs treffen und Daten asserten, wandern auf
`@pytest.mark.live` (Live-Schicht). Kein neuer Mechanismus.

## Source
- **File:** `src/app/egress_guard.py` (INVENTORY), betroffene Test-Dateien
- **Betroffene Host:** `api.meteoalarm.org`, `warnungen.zamg.at`,
  `public-api.meteofrance.fr`, `www.risque-prevention-incendie.fr`

## Scope
### Affected Files
| File | Change | Description |
|------|--------|-------------|
| `src/app/egress_guard.py` | MODIFY | 4 Warn-Host `TEST_ACCESS`→`BLOCKED` (Kommentar: 2b) |
| `tests/tdd/test_isolation_warn_services.py` | CREATE | Isolations-Beweis: Guard aktiv → 4 Warn-Host blockiert |
| `tests/tdd/test_issue_1035/1036/1037/1085_*.py` | MODIFY | NUR die echten-API-Tests auf `@pytest.mark.live` (GREEN zeigt welche) |

### Estimated Changes
- Files: 1 Guard + 1 Test neu + bis zu 4 Test-Dateien (Marker-Zeilen)
- LoC: ~60–120 (Marker + Beweis-Test; Guard = 4 Zeilen)

## Test Plan
Kern deterministisch, kein Live-Netz. Beweis-Test nutzt den Netz-Sentinel wie
`test_egress_guard.py`: mit aktivem Guard (`is_test_mode`) an einen der 4
Warn-Host → `EgressBlockedError`, Sentinel-Transport nie erreicht. Regression
gezielt (4 Warn-Test-Dateien + `test_egress_guard`), NICHT Vollsuite.

## Acceptance Criteria

- **AC-1:** Given der Egress-Wächter ist aktiv (`is_test_mode`, Nicht-Live) / When ein Request an einen der 4 Warn-Host (`api.meteoalarm.org`, `warnungen.zamg.at`, `public-api.meteofrance.fr`, `www.risque-prevention-incendie.fr`) geht / Then wirft der Wächter `EgressBlockedError` und der echte Transport wird nie erreicht (Netz-Sentinel-Beweis)
  - Test: `test_isolation_warn_services.py::test_warn_hosts_blocked[<host>]`
- **AC-2:** Given `src/app/egress_guard.py` INVENTORY / When gelesen / Then stehen die 4 Warn-Host auf `IsolationKind.BLOCKED` (nicht `TEST_ACCESS`); die Wetter-/Radar-Host (geosphere.at/brightsky/protezionecivile) bleiben unverändert
  - Test: `test_isolation_warn_services.py::test_inventory_warn_hosts_blocked`
- **AC-3:** Given der deterministische Kern-Testlauf (`not live and not staging and not email`) / When er läuft / Then löst KEIN Kern-Test mehr einen echten Call an die 4 Warn-Host aus (die echten-API-Tests sind auf `@live` verschoben) — belegt dadurch, dass der Guard bei keinem Kern-Test einen `EgressBlockedError` aus einem ungewollten Warn-Call wirft
  - Test: gezielter Lauf der 4 Warn-Test-Dateien grün; verschobene Tests unter `-m live` weiterhin vorhanden
- **AC-4:** Given die auf `@live` verschobenen Tests / When ohne `-m live` gelaufen / Then sind sie deselektiert (nicht gelöscht — die Live-Schicht behält den echten-API-Nachweis)
  - Test: `pytest --collect-only -m "not live"` listet sie nicht; `-m live` listet sie
- **AC-5:** Given der deterministische Kern nach der Änderung / When gezielt gelaufen (4 Warn-Test-Dateien + test_egress_guard) / Then kein NEUER Failure gegenüber Baseline (Regressionsschutz)
  - Test: gezielter Vorher/Nachher-Diff grün

## Known Limitations
- **Staging zeigt danach keine echten amtlichen Warnungen** (immer leer) —
  Warnungs-Darstellung auf Staging nicht mehr prüfbar. Attrappe mit
  aufgezeichneten Warndaten = optionale Folge-Scheibe (neuer Mechanismus).
- Nur die 4 WARN-Host; Wetter-/Radar-Isolation bleibt bei `GZ_TEST_FIXTURE_DIR`.
- `@live`-Tests konsumieren beim expliziten Lauf weiter echtes Kontingent (Opt-in, selten).

## Regel-Budget
Keine neue Regel/Gate — Verschärfung bestehender Wächter-Deklaration. Kein Prüfdatum.

## Changelog
- 2026-07-22: Initial spec — Issue #1348 Scheibe 2b
