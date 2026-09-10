---
entity_id: fix_2240_rolling_trip_test_versandsperre
type: module
created: 2026-09-10
updated: 2026-09-10
status: draft
version: "1.0"
tags: [testing, pytest, staging-marker, versandrisiko, infrastructure]
---

<!-- Issue #2240 — herausgelöst aus Sammelprojekt #1196 (Triage 2026-09-08). Klasse #1477: Versand aus einem Testlauf. -->

# Rolling-Trip-Test: kein Versand aus dem Kern (Issue #2240)

## Approval

- [ ] Approved (Behebungsweg ist im Issue-Text vom PO vorgegeben, Abschnitt „Behebung (klein)"; diese Spec setzt ihn 1:1 um und ergänzt nur die Wächter-Mechanik)

## Purpose

`tests/tdd/test_issue_937_staging_rolling_trip.py::test_rolling_trip_send_returns_sent_true`
liegt in der Kernschicht ohne `live`/`staging`-Marker und feuert bei jedem lokalen
Volllauf auf dem Server (Port 8001 = `gregor-python-staging`) einen **echten
Briefing-Versand**. Zusätzlich steht `_staging_scheduler_reachable()` im
`skipif`-Ausdruck und wird zur **Collect-Zeit** ausgewertet — schon das Einsammeln
der Datei öffnet einen Socket. Beides wird beseitigt: modul-weiter `staging`-Marker
(raus aus Kern und Standardlauf) und Skip zur Laufzeit statt zur Collect-Zeit.
Der bestehende Kollektions-Wächter (`test_pytest_collection_and_timeout_safety.py`)
wird ERWEITERT, nicht nachgebaut (Muster #1211a).

## Source

> Test-Infrastruktur — kein Frontend-, Go-API- oder Python-Core-Domain-Code betroffen.

- **File (MODIFY):** `tests/tdd/test_issue_937_staging_rolling_trip.py`
  - `pytestmark = pytest.mark.staging` auf Modulebene
  - `_staging_scheduler_reachable()` raus aus `@pytest.mark.skipif(...)`, rein in den
    Testkörper von `test_rolling_trip_send_returns_sent_true` als `pytest.skip(...)`
  - Erreichbarkeitsprobe wird ein `GET /health` (auth-frei, `api/routers/health.py`)
    statt eines `POST .../__reachability_probe__/send` — eine Probe darf nicht selbst
    den Versand-Endpunkt anfassen
- **File (MODIFY):** `tests/tdd/test_pytest_collection_and_timeout_safety.py`
  - Konstante `_ROLLING_TRIP_DIALER = "tests/tdd/test_issue_937_staging_rolling_trip.py"`
  - Neue Wächter-Tests (siehe Acceptance Criteria), Nachweis ausschließlich über
    echte Subprozesse

### Befund zur Gegenprobe aus dem Issue

`pytest-socket` sperrt Sockets erst in `pytest_runtest_setup`
(`.venv/.../pytest_socket/__init__.py:170`), **nicht während der Collection**.
`uv run pytest <datei> --collect-only --disable-socket` (ohne `--allow-hosts`)
sammelt heute 2 Tests ohne Fehler, obwohl der Probe-POST real abgesetzt wird
(empirisch geprüft 2026-09-10). Die im Issue vorgeschlagene Gegenprobe ist deshalb
kein Nachweis. Der Wächter blockiert den Socket daher **selbst** vor dem Start von
pytest (Bootstrap-Skript patcht `socket.socket.connect`, dann `pytest.main`).

## Estimated Scope

- **LoC:** ~60 (Testdatei ~10, Wächter ~50)
- **Files:** 2
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `pyproject.toml` `addopts = "-m 'not email and not live and not staging'"` | intern | Einzige Ausschlussmechanik für den Standardlauf; `staging` ist registriert |
| `tests/tdd/test_pytest_collection_and_timeout_safety.py` | intern | Bestehender Kollektions-Wächter (#1210/#1211), wird erweitert |
| `tests/conftest.py` Egress-Wächter (#1337) | intern | Greift nur im Kern (`not live/email/staging`); nach dem Marker ist die Datei außerhalb |
| `.github/ci_tdd_excludes.txt` | Ratsche | Datei ist dort NICHT gelistet — bleibt so (Marker statt Ausschlussliste) |
| Issue #1477 / #1755 / #1196 | GitHub Issue | Versand-aus-Testlauf-Klasse, Offline-Volllauf, Sammelprojekt |

## Implementation Details

```
1. RED — Wächter erweitern (test_pytest_collection_and_timeout_safety.py):
   a) test_rolling_trip_dialer_excluded_from_default(default_collect)
      -> _collected_counts(default) enthält _ROLLING_TRIP_DIALER nicht (0).
      Heute rot: Datei ohne Marker, 2 gesammelt.
   b) test_rolling_trip_dialer_collected_under_staging(staging_collect)
      -> unter `-m staging` >= 1 Test der Datei (Marker verschiebt, löscht nicht).
      Heute rot: 0 unter -m staging.
   c) test_rolling_trip_collection_opens_no_socket()
      -> Subprozess `python - <<bootstrap>>`: patcht socket.socket.connect und
      connect_ex auf eine RuntimeError-Unterklasse, ruft dann
      pytest.main(["--collect-only", "-q", "-o", "addopts=", "-p", "no:cacheprovider",
      _ROLLING_TRIP_DIALER]). Erwartung: returncode 0, beide Test-IDs gesammelt,
      kein "ERROR" in der Ausgabe. Heute rot: skipif-Ausdruck ruft httpx ->
      RuntimeError -> Collection-Error (Exit 2).
   d) test_rolling_trip_send_skips_at_runtime_when_port_closed()
      -> Subprozess wie c), aber connect wirft ConnectionRefusedError (OSError,
      von httpx zu ConnectError gemappt); Aufruf
      pytest.main(["-q", "-o", "addopts=", "-p", "no:cacheprovider", "-rs",
      f"{_ROLLING_TRIP_DIALER}::test_rolling_trip_send_returns_sent_true"]).
      Erwartung: returncode 0, "1 skipped", weder "passed" noch "failed"/"error".
      Auf JEDEM Host sicher: der Socket ist gepatcht, es kann nichts versendet werden.

2. GREEN — test_issue_937_staging_rolling_trip.py:
   - `pytestmark = pytest.mark.staging`
   - `_staging_scheduler_reachable()`: httpx.get(f"{URL}/health", timeout=3)
   - `@pytest.mark.skipif(...)` entfernen; im Testkörper:
     if not _staging_scheduler_reachable(): pytest.skip("Interner Staging-Scheduler-Port 8001 ... nicht erreichbar")
   - Der eigentliche Send-POST bleibt unverändert (Staging-Lane-Verhalten unberührt).

3. Nachweis nur per Subprozess; der Send-Test wird zu keinem Zeitpunkt mit
   offenem Socket ausgeführt.
```

## Expected Behavior

- **Input:** `uv run pytest` (Standardlauf) bzw. `uv run pytest -m staging <datei>`
- **Output:**
  - Standardlauf/CI-Kern: Datei komplett deselektiert (0 Tests)
  - `-m staging`: beide Tests sammelbar; Send-Test skippt zur Laufzeit, wenn Port 8001
    zu ist, und läuft nur auf dem Server in der Staging-Lane
  - `--collect-only` der Datei öffnet keinen Socket mehr
- **Side effects:** Keine im Produktivcode. `test_setup_script_exists_and_is_importable`
  wandert mit dem Modul-Marker ebenfalls in die Staging-Lane (PO-Vorgabe „Modulebene").

## Acceptance Criteria

- **AC-1:** Given die pytest-Standard-Selektion (`addopts`, `not email and not live and not staging`) / When `pytest --collect-only -q` die volle Suite sammelt / Then erscheint `tests/tdd/test_issue_937_staging_rolling_trip.py` mit 0 gesammelten Tests.
  - Test: `test_rolling_trip_dialer_excluded_from_default` — echter Subprozess-Collect (Fixture `default_collect`), zählt Test-IDs der Datei.

- **AC-2:** Given `pytest --collect-only -q -m staging` / When es läuft / Then erscheint die Datei mit mindestens einem gesammelten Test — der Marker verschiebt, löscht nicht.
  - Test: `test_rolling_trip_dialer_collected_under_staging` — echter Subprozess-Collect (Fixture `staging_collect`).

- **AC-3:** Given ein Python-Prozess, in dem `socket.socket.connect` vor dem pytest-Start jeden Verbindungsaufbau mit einer Exception abweist / When pytest die Datei nur sammelt (`--collect-only -o addopts=`) / Then endet die Collection mit Exit 0 und beiden Test-IDs, ohne Collection-Error — kein Netzaufruf zur Collect-Zeit.
  - Test: `test_rolling_trip_collection_opens_no_socket` — Subprozess mit Socket-Bootstrap, prüft returncode und Test-IDs.

- **AC-4:** Given derselbe Bootstrap, aber `connect` wirft `ConnectionRefusedError` (Port 8001 zu) / When der Send-Test gezielt ausgeführt wird (`-o addopts=` hebt den Marker-Filter auf) / Then wird er als **skipped** gemeldet (nicht passed, nicht failed, nicht error) und der Prozess endet mit Exit 0.
  - Test: `test_rolling_trip_send_skips_at_runtime_when_port_closed` — Subprozess, parst die pytest-Kurzzusammenfassung.

- **AC-5:** Given die Erreichbarkeitsprobe / When sie ausgeführt wird / Then trifft sie ausschließlich `GET /health` (auth-frei) und nie einen `/send`-Endpunkt.
  - Test: mitabgedeckt durch AC-4 (Bootstrap protokolliert keine Verbindung) plus Adversary-Review des Diffs; kein Dateiinhalt-Check.

## Known Limitations

- Der Send-Test selbst wird in dieser Änderung nie mit offenem Socket ausgeführt; sein
  Verhalten gegen den echten Staging-Scheduler (HTTP 409/Timeout laut Issue) ist
  ausdrücklich NICHT Gegenstand — das ist Staging-Lane-Verhalten und ggf. ein
  eigener Befund in #1199.
- `test_setup_script_exists_and_is_importable` ist offline lauffähig, verlässt mit dem
  Modul-Marker aber den Kern (PO-Vorgabe „Modulebene", Issue-Text). Kein Verlust an
  Produktabsicherung: das Setup-Script ist Staging-Infrastruktur.
- Die Egress-Sperre von `pytest-socket` bleibt unverändert; Collect-Zeit-Egress wird
  nur für diese Datei bewacht, nicht suite-weit (Kandidat für #1196, wenn ein zweiter
  Fall auftaucht).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (lokale Test-Infrastruktur-Konvention, analog #1210/#1211)
- **Rationale:** `staging` statt `live`, weil der Test einen Staging-Dienst auf demselben
  Host anspricht — konsistent mit Liste A aus #1211a. Marker statt Eintrag in
  `ci_tdd_excludes.txt`, weil die Ratsche nur schrumpfen darf und der Marker die
  Datei in die richtige Schicht verschiebt statt sie zu verstecken.

## Changelog

- 2026-09-10: Initial spec created (Issue #2240)
- 2026-09-10: Adversary (implementation-validator) VERIFIED/HOLDS — AC-1..AC-5 bestätigt; Mutationen M1 (Marker weg), M2 (Collect-Zeit-skipif), M3 (Laufzeit-Skip weg) werden je von einem Wächter gefangen. M4 (Probe zurück auf POST /send) nicht gefangen = bewusst Review-only laut AC-5; M5 (`except Exception` in der Probe) nicht gefangen = LOW, gebucht in #1199.
