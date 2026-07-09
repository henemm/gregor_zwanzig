---
entity_id: issue_1133_testdata_cleanup
type: bugfix
created: 2026-07-09
updated: 2026-07-09
status: implemented
workflow: fix-1133-testdata-cleanup
---

# Testdaten-Cleanup + isolierter Test-Daten-Root (#1133 + Baustein-B-Rest #1147)

## Approval

- [ ] Approved

## Purpose

Python-Tests schreiben heute in den echten `data/users/`-Baum (Prod: 124 von 139
Verzeichnissen, Staging: ~152 von 153 sind Test-Residuen), weil `get_data_dir()` den
Daten-Root hart auf `Path("data/users")` konstruiert und dabei den bereits
existierenden `_DATA_ROOT`-Override ignoriert. Dieser Fix behebt die Ursache
(umlenkbarer Daten-Root für alle Python-Tests) und räumt einmalig die
angesammelten Test-Residuen aus Prod und Staging auf, mit Backup und
PO-freigegebener Positivliste echter Nutzer.

## Source

- **File:** `src/app/loader.py:774-791` — `get_data_dir()` / `get_trips_dir()` /
  `get_locations_dir()` / `get_snapshots_dir()`
- **Identifier:** `def get_data_dir(user_id: str = "default") -> Path`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `loader._DATA_ROOT` (Modul-Global, `loader.py:206`) | intern | bestehender Override-Mechanismus, bisher nur von `get_compare_subscriptions_file` respektiert (`loader.py:1292-1298`) — Vorbild für `get_data_dir()` |
| `os.environ["GZ_DATA_DIR"]` | Env-Var (neu) | Symmetrie zum Go-seitigen `DATA_DIR`-Envconfig (`internal/config/config.go:9`); alternative Override-Quelle neben `_DATA_ROOT` |
| `tmp_path_factory` (pytest-Fixture) | stdlib/pytest | liefert pro Testsession ein isoliertes Temp-Verzeichnis als Ziel-Root für die neue autouse-Fixture |
| `tests/conftest.py:_use_fixture_provider` (Zeile 18) | intern | bestehendes autouse-Fixture-Muster (Issue #346) — Vorbild für die neue Daten-Root-Fixture |
| `pytest.mark` (Custom-Marker `real_data_root`) | pytest | Opt-out für Tests, die bewusst den echten Baum lesen (z.B. `test_alert_rules_model.py` AC-9, `test_issue_991_roundtrip_extra_fields.py` AC-2) |
| `tarfile` (stdlib) | stdlib | Pre-Cleanup-Backup nach `.backups/`, analog zum Muster in `.claude/hooks/data_schema_backup.py` |

## Scope

### Affected Files
| File | Change Type | Description |
|------|-------------|-------------|
| `src/app/loader.py` | MODIFY | `get_data_dir()` respektiert `_DATA_ROOT` **und** `GZ_DATA_DIR`-Env-Var (Vorbild: `get_compare_subscriptions_file`) |
| `tests/conftest.py` | MODIFY | Neue autouse-Fixture `_isolate_data_root`: lenkt `loader._DATA_ROOT` für jeden Test auf ein `tmp_path_factory`-Verzeichnis um; Tests mit `@pytest.mark.real_data_root` oder `@pytest.mark.live` bleiben unangetastet |
| `pyproject.toml` | MODIFY | Neuer Marker `real_data_root` in `[tool.pytest.ini_options].markers` registriert |
| `tests/tdd/conftest.py` | MODIFY | Zeilen 48-56 (`_clear_tdd_638_throttle`): hartkodierter `Path(__file__).../data/users` durch `loader.get_data_dir(...).parent`-basierte Auflösung ersetzt, damit der Throttle-Cleanup dem umgelenkten Root folgt |
| `tests/tdd/test_alert_rules_model.py` | MODIFY | AC-9-Roundtrip-Test (Zeile ~276) mit `@pytest.mark.real_data_root` markiert (liest bewusst den echten Baum via direkter `Path("data/users").glob(...)`-Konstruktion) |
| `tests/tdd/test_issue_991_roundtrip_extra_fields.py` | MODIFY | AC-2-Roundtrip-Test (Zeile ~82-89), analog mit `@pytest.mark.real_data_root` markiert |
| `tests/unit/test_issue_1133_data_root_isolation.py` | CREATE | Beweist echtes Isolationsverhalten: `save_trip()` ohne `data_dir=` landet nach der Fixture im Temp-Root, der echte Baum bleibt unverändert; Opt-out-Marker-Test |
| `scripts/cleanup_1133_testdata.py` | CREATE | Einmaliges, idempotentes Cleanup-Script (Backup, Positivliste, Dry-Run-Default, `--execute`) |
| `tests/unit/test_cleanup_1133_testdata.py` | CREATE | Testet das Cleanup-Script gegen eine Kopie-Baum-Fixture unter `tmp_path` — Positivlisten-User überleben, Residuen verschwinden, Dry-Run löscht nichts |
| `docs/project/known_issues.md` | MODIFY | Eintrag zu #1133 (Root Cause, Fix, Known Limitations) |

### Estimated Changes
- Files: 10
- LoC: ~+320/-10 (überschreitet das Standard-Budget von 250; Grund: neues
  Cleanup-Script (~140 LoC) + zwei neue Testdateien (~145 LoC) zusätzlich zum
  eigentlichen Ursachen-Fix (~35 LoC). Ein `loc_limit_override` wird in der
  Implementierungsphase vermutlich nötig — Freigabe dafür liegt beim PO, nicht
  bei dieser Spec.)

## Implementation Details

### Teil 1 — Ursachen-Fix

`get_data_dir()` übernimmt exakt das Override-Muster, das `get_compare_subscriptions_file`
bereits nutzt (`loader.py:1292-1298`), erweitert um eine Env-Var als zweite Quelle:

```python
def get_data_dir(user_id: str = "default") -> Path:
    import os as _os
    import sys as _sys
    _root = getattr(_sys.modules[__name__], "_DATA_ROOT", None) or _os.environ.get("GZ_DATA_DIR")
    if _root:
        return Path(_root) / "users" / user_id
    return Path("data/users") / user_id
```

`get_trips_dir`/`get_locations_dir`/`get_snapshots_dir` bleiben unverändert (sie
delegieren bereits an `get_data_dir()`) und erben den Override automatisch.
`save_trip()` (`loader.py:1246-1249`) ruft `get_trips_dir(user_id)` nur auf, wenn
kein explizites `data_dir=` übergeben wird — genau der Pfad, den die ~37
Testdateien nutzen, die heute ungeschützt in den echten Baum schreiben.

Die neue autouse-Fixture in `tests/conftest.py` (Vorbild: `_use_fixture_provider`,
Zeile 18) setzt vor jedem Test `loader._DATA_ROOT` auf ein frisches
`tmp_path_factory.mktemp("data_root")`-Verzeichnis und setzt es danach zurück.
Tests mit `@pytest.mark.real_data_root` oder `@pytest.mark.live` werden
übersprungen (kein Override) — sie lesen weiterhin bewusst den echten Baum.
HTTP-Tests gegen laufende Server (Staging/localhost) sind von der Fixture nicht
betroffen: der Server-Prozess hat seinen eigenen Datenraum, die Umlenkung wirkt
nur im pytest-Client-Prozess.

`tests/tdd/conftest.py:48-56` (Throttle-Cleanup für `tdd-638-*`-User) wird von
einer hartkodierten `Path(__file__)...`-Konstruktion auf eine Auflösung über
`loader.get_data_dir(uid).parent` umgestellt, damit der Cleanup demselben
(umgelenkten) Root folgt wie die Tests, die er bereinigt.

Zwei Tests, die bewusst den kompletten realen Baum als Vertragsprobe lesen
(`test_alert_rules_model.py` AC-9, `test_issue_991_roundtrip_extra_fields.py`
AC-2 — beide konstruieren `Path("data/users").glob(...)` direkt, nicht über
`get_data_dir()`), erhalten den `@pytest.mark.real_data_root`-Marker. Das ist
primär Dokumentation/Signalwirkung, da diese Tests wegen der direkten
Pfad-Konstruktion ohnehin nicht von der Fixture erfasst würden — der Marker
macht die Absicht explizit und verhindert versehentliches Nachrüsten der
Fixture-Logik auf diese Tests in einem Folge-Refactor.

### Teil 2 — Einmaliger Cleanup

`scripts/cleanup_1133_testdata.py` läuft pro Host (Prod, Staging) als
`claude-gregor`, idempotent, Dry-Run per Default:

1. tar.gz-Backup des kompletten `data/users/`-Baums nach `.backups/` (dauerhaft
   aufbewahrt, kein Retention-Limit wie bei `data_schema_backup.py`).
2. Positivliste pro Host (Prod: `admin`, `default`, `henning`, `steffi`;
   Staging: `default`) — alle übrigen User-Verzeichnisse werden gelöscht,
   inklusive `validator-issue110` (PO-Entscheid 2026-07-09: löschen, Backup
   bleibt als Sicherungsnetz).
3. Konservative In-User-Bereinigung (PO-Entscheid 2026-07-09): innerhalb der
   Positivlisten-User werden nur eindeutige Muster (`e2e-*`, `adv-test-*`,
   `validator-*`, `test-trip*`) in `trips/` und `weather_snapshots/` gelöscht;
   alles andere (echte Trips wie `gr221-mallorca`, Hash-IDs) bleibt unberührt.
4. Dry-Run (Default): gibt vollständigen Löschplan aus (Pfade, Anzahl
   Verzeichnisse/Dateien), schreibt nichts.
5. `--execute`: führt Backup + Löschung tatsächlich aus. Wiederholtes Ausführen
   ohne Zustandsänderung ist sicher (bereits gelöschte Pfade werden übersprungen,
   kein Fehler).

## Out of Scope / Was sich nicht ändert

- **Go-Code:** bereits sauber (`internal/config/config.go:9` `DATA_DIR`-Env,
  `t.TempDir()` in Store-Tests) — keine Änderung nötig.
- **Hartkodierte `Path("data/users/...")` in Services** (`src/services/trip_alert.py:79,556,821`,
  `trip_report_scheduler.py:257,330,937`, `user_tier.py:6,22`,
  `alert_daily_limit.py:23`, `gpx_processing.py:37-38`, `src/app/config.py:259`)
  — nicht Teil dieses Fixes (LoC-Budget), siehe Known Limitations.
- **Die ~23 Testdateien, die `Path("data/users/...")` direkt konstruieren**
  (statt über `get_data_dir()`), werden nicht refactored — nur die zwei
  bekannten Vertragstests erhalten den Opt-out-Marker als Dokumentation.
- **Housekeeping-Cron** für laufende Neuentstehung von Residuen ist optional
  und wird nicht in diesem Workflow eingeführt (Folge-Issue).
- **Baustein-B-Prozessteil** (Playbook + Memory-Eintrag für Daten-Migration)
  ist bereits live aus #1147 — dieser Workflow liefert nur noch Cleanup +
  Ursachen-Fix.

## Expected Behavior

- **Input:** Ein Python-Test ruft `save_trip(trip, user_id=...)` ohne
  explizites `data_dir=` auf, während die autouse-Fixture aktiv ist.
- **Output:** Die Trip-Datei landet unter dem `tmp_path_factory`-Temp-Root, der
  echte `data/users/`-Baum zeigt vor und nach dem Testlauf identische
  mtime/Inhalt für alle vorher existierenden Dateien.
- **Side effects:** Für das Cleanup-Script: tar.gz-Backup vor jeder Löschung;
  Positivlisten-Verzeichnisse bleiben vollständig erhalten; Residuen (ganze
  Test-User-Verzeichnisse sowie eindeutige In-User-Testmuster) werden entfernt.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN die neue autouse-Fixture ist aktiv (kein `real_data_root`-Marker)
  WHEN ein Test `save_trip(trip, user_id="synthetic-1133")` ohne `data_dir=`
  aufruft THEN liegt die resultierende JSON-Datei unter dem Temp-Root der
  Fixture (nachweisbar über `loader._DATA_ROOT`), NICHT unter dem echten
  `data/users/synthetic-1133/trips/`-Pfad — geprüft durch Existenzcheck an
  beiden Orten nach dem Aufruf.

- [ ] Test 2: GIVEN ein Test trägt `@pytest.mark.real_data_root` WHEN er
  `get_data_dir("default")` aufruft THEN liefert die Funktion den echten Pfad
  `data/users/default` (kein Override aktiv) — geprüft durch direkten
  Pfad-Vergleich gegen `Path("data/users/default").resolve()`.

- [ ] Test 3: GIVEN das Cleanup-Script läuft im Dry-Run-Modus (Default) gegen
  eine Kopie-Baum-Fixture unter `tmp_path` mit Positivliste `["default"]` und
  drei zusätzlichen Test-User-Verzeichnissen WHEN das Script ausgeführt wird
  THEN existieren nach dem Lauf weiterhin alle vier Verzeichnisse unverändert
  (kein Dateisystem-Write), und die Ausgabe listet die drei zu löschenden
  Pfade auf.

- [ ] Test 4: GIVEN dieselbe Kopie-Baum-Fixture WHEN das Script mit
  `--execute` läuft THEN existiert nach dem Lauf nur noch `default`, die drei
  Residuen-Verzeichnisse sind entfernt, und unter `.backups/` liegt ein
  tar.gz mit dem vollständigen Vor-Zustand.

- [ ] Test 5: GIVEN eine Kopie-Baum-Fixture mit einem Positivlisten-User, der
  sowohl einen echten Trip (`gr221-mallorca.json`) als auch Residuen-Trips
  (`e2e-foo.json`, `adv-test-bar.json`) in `trips/` enthält WHEN das Script
  mit `--execute` läuft THEN bleibt `gr221-mallorca.json` unverändert erhalten,
  während `e2e-foo.json` und `adv-test-bar.json` gelöscht sind.

## Acceptance Criteria

- **AC-1:** Given die neue autouse-Fixture ist aktiv und ein Test ruft
  `save_trip()` ohne `data_dir=`-Override auf / When der Test läuft / Then
  landet die geschriebene Trip-Datei ausschließlich im temporären Fixture-Root,
  und der echte `data/users/`-Baum bleibt für diesen Test unverändert
  (mtime-Vergleich vor/nach Lauf identisch).

- **AC-2:** Given ein Test ist mit `@pytest.mark.real_data_root` markiert /
  When er `get_data_dir()` oder eine darauf aufbauende Funktion aufruft / Then
  wird der echte `data/users/`-Pfad zurückgegeben — kein Fixture-Override
  greift für diesen Test.

- **AC-3:** Given `GZ_DATA_DIR` ist als Umgebungsvariable gesetzt (ohne
  aktiven `_DATA_ROOT`-Modul-Override) / When `get_data_dir()` aufgerufen wird
  / Then wird der Pfad relativ zum Wert von `GZ_DATA_DIR` aufgelöst, analog
  zum Go-seitigen `DATA_DIR`-Envconfig.

- **AC-4:** Given `tests/tdd/conftest.py`s Throttle-Cleanup-Fixture für
  `tdd-638-*`-User läuft unter der neuen Daten-Root-Isolation / When ein
  Test aus dieser Gruppe ausgeführt wird / Then wird die Throttle-Datei im
  jeweils aktiven (umgelenkten) Root zurückgesetzt, nicht mehr zwingend im
  echten Baum — keine Regression im Throttle-Reset-Verhalten.

- **AC-5:** Given das Cleanup-Script läuft im Dry-Run-Modus (Default, ohne
  `--execute`) gegen eine Kopie-Baum-Fixture / When es ausgeführt wird / Then
  wird keine einzige Datei oder kein Verzeichnis gelöscht, aber ein
  vollständiger Löschplan mit allen betroffenen Pfaden wird ausgegeben.

- **AC-6:** Given das Cleanup-Script läuft mit `--execute` gegen eine
  Prod-Positivliste (`admin`, `default`, `henning`, `steffi`) auf einer
  Kopie-Baum-Fixture, die zusätzlich `validator-issue110` und weitere
  Test-Residuen enthält / When der Lauf abgeschlossen ist / Then existieren
  ausschließlich die vier Positivlisten-Verzeichnisse, `validator-issue110`
  und alle anderen Residuen sind entfernt, und ein tar.gz-Backup des
  Vor-Zustands liegt unter `.backups/`.

- **AC-7:** Given ein Positivlisten-User enthält sowohl echte Trip-Dateien
  (z.B. `gr221-mallorca.json`) als auch Residuen-Muster (`e2e-*`,
  `adv-test-*`, `validator-*`, `test-trip*`) in `trips/` oder
  `weather_snapshots/` / When das Cleanup-Script mit `--execute` läuft / Then
  werden ausschließlich die Muster-Treffer gelöscht, alle anderen Dateien
  bleiben inhaltlich und in der mtime unverändert.

- **AC-8:** Given das Cleanup-Script wurde bereits einmal erfolgreich mit
  `--execute` ausgeführt (Residuen bereits entfernt) / When es ein zweites
  Mal mit `--execute` gegen denselben Baum läuft / Then bricht es nicht mit
  einem Fehler ab (bereits gelöschte Pfade werden als "nichts zu tun"
  übersprungen) — idempotentes Verhalten.

## Known Limitations

- Hartkodierte `Path("data/users/...")`-Konstruktionen in Services
  (`src/services/trip_alert.py`, `trip_report_scheduler.py`, `user_tier.py`,
  `alert_daily_limit.py`, `gpx_processing.py`, `src/app/config.py`) bleiben
  unverändert — bewusster Nicht-Scope wegen LoC-Budget, Folge-Issue empfohlen.
- Die ~23 Testdateien, die `Path("data/users/...")` direkt statt über
  `get_data_dir()` konstruieren, profitieren NICHT von der neuen
  Isolations-Fixture — sie lesen/schreiben weiterhin den echten Baum,
  unabhängig vom `real_data_root`-Marker. Nur die zwei bekannten
  Vertragstests werden markiert (Dokumentation der Absicht).
- Staging-Re-Pollution durch echte E2E-Läufe gegen den laufenden
  Staging-Server ist weiterhin erwartbar und in Ordnung — das sind
  serverseitige Schreibzugriffe (Go-API-Prozess), kein pytest-Leak, und
  daher kein Ziel dieses Fixes.
- Housekeeping-Cron für laufende Neubereinigung wird nicht eingeführt —
  optionales Folge-Issue.
- `validator-issue110` wird laut PO-Entscheid (2026-07-09) gelöscht; das
  tar.gz-Backup bleibt dauerhaft erhalten, falls sich die Daten später doch
  als relevant erweisen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Additiver Fix eines bestehenden, bereits etablierten
  Override-Musters (`_DATA_ROOT`, seit `get_compare_subscriptions_file`) auf
  eine weitere Funktion (`get_data_dir()`), plus eine autouse-Test-Fixture
  nach bestehendem Vorbild (`_use_fixture_provider`). Keine neue
  Architekturentscheidung, kein neuer Kommunikationsweg, kein neues
  Datenformat. Der Cleanup-Teil ist ein einmaliger Ops-Vorgang ohne
  Architektur-Auswirkung.

## Changelog

- 2026-07-09: Initial spec created
- 2026-07-09: Implementierung abgeschlossen — `get_data_dir()` respektiert
  `_DATA_ROOT`/`GZ_DATA_DIR`, autouse-Fixture `_isolate_data_root` in
  `tests/conftest.py`, `scripts/cleanup_1133_testdata.py` erstellt. Adversary
  Verification: 3 Runden (F001-F007) → Verdict VERIFIED.
