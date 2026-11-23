---
entity_id: perf_3209_pytest_xdist_ci
type: module
created: 2026-11-22
updated: 2026-11-22
status: draft
version: "1.0"
workflow: perf-3209-pytest-laufzeit
tags: [testsuite, ci, xdist, performance, epic-1196]
---

# Parallele Python-Kern-Testsuite in CI (pytest-xdist)

## Approval

- [ ] Approved

## Purpose

Der CI-Job `test` (Python-Kern-Suite, ca. 24.900 Tests) dauert rund 30 Minuten und ist der laengste Pflicht-Check jedes Pull Requests. Diese Spec fuehrt in CI parallele Ausfuehrung mit `pytest-xdist` ein (`-n 4 --dist loadgroup`), ohne Pruefschaerfe zu verlieren: Echtbaum-Waechter bleiben scharf, Tests am echten `data/`-Baum laufen gemeinsam in einer Worker-Gruppe. Issue #3209 (Teil von Epic #1196).

## Source

- **File:** `.github/workflows/ci.yml` (Job `test`), `tests/conftest.py`, `pyproject.toml`
- **Identifier:** CI-Aufruf von pytest; Fixtures `_guard_repo_data_users_session`, `_isolate_data_root`, `_materialize_real_data_root_fixtures`, `_raeume_budget_spur_bei_real_data_root`

> **Schicht-Hinweis:** Reine Test-Infrastruktur (CI, `tests/`, Doku). Keine Aenderung in Frontend, Go-API oder Python-Produktcode. Keine Nutzerdaten-Bewegung im Produkt, Mandantentrennung und Kanaele sind nicht beruehrt (Querschnitts-Pruefpunkte entfallen).

## Estimated Scope

- **LoC:** ca. +250/-60
- **Files:** ca. 15-20 (davon rund 12 Testdateien mit Kleinstaenderungen)
- **Effort:** medium-high (Risiko MEDIUM-HIGH: zentrale Fixtures, Waechter duerfen nicht aufgeweicht werden)

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `pyproject.toml`, `uv.lock` | MODIFY | dev-Dependency `pytest-xdist` |
| `tests/conftest.py` | MODIFY | Echtbaum-Waechter worker-fest; Materialisierung einmalig per Dateisperre; automatische `xdist_group("echtdaten")` fuer alle `real_data_root`-Tests (`pytest_collection_modifyitems`); `_raeume_budget_spur_bei_real_data_root` geprueft |
| Tests mit relativem `Path("data/users")` bzw. `rmtree` fester user_ids (u. a. `tests/integration/test_issue_221_validator_endpoints.py`, `test_issue_448_*`, `test_issue_918_*`, `tests/tdd/test_onset_*`, `test_issue_846_alert_preset.py`, `test_issue_731_unified_commands.py`, `test_issue_991_*`, `test_alert_rules_model.py`, `test_alert_preview_input_validation.py`, `test_issue_612_*`) | MODIFY | Marker `real_data_root` (serielle Gruppe) oder Umstellung auf `tmp_path` |
| `tests/tdd/test_bug305_mobile_email.py` | MODIFY | feste `/tmp`-Namen (Z. 297, 546) auf `tmp_path` |
| `tests/tdd/test_xdist_echtbaum_ratsche.py` | CREATE | Ratsche: Testdatei am echten `data/`-Baum ausserhalb der seriellen Gruppe wird rot |
| `tests/tdd/test_xdist_worker_sicherheit.py` | CREATE | Subprozess-Laeufe mit `-n 2` auf Beispieldateien: Egress-Sperre, Loopback-Port-Guard, Waechter-Mutation, Gruppenbildung |
| `.github/workflows/ci.yml` | MODIFY | Job `test`: `-n 4 --dist loadgroup` |
| `docs/reference/gates_und_ratschen.md` | MODIFY | CI parallel; Regel "Echtbaum-Tests nur mit `real_data_root`" |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `pytest-xdist` | dev-Dependency (neu) | parallele Worker, `--dist loadgroup` |
| `pytest-timeout` | bestehend | globaler `timeout = 30` je Worker unveraendert |
| `pytest-socket` | bestehend | `--disable-socket` muss in jedem Worker greifen |
| `tests/_loopback_port_guard.py` | bestehend | je Prozess eigenes Port-Set; Stub-Server binden `:0` |
| `.claude/hooks/broad_test_run_gate.py` | bestehend, unveraendert | lokale sichere Offline-Form bleibt seriell (Rohstring-Vergleich) |
| #3278 | Folge-Issue | lokale parallele Gate-Form (Out of Scope) |
| #3279 | Folge-Issue | Scanner-Ratschen-Cache, echte Wartezeiten (Out of Scope) |
| #3054, #2911, #2898, #3108, #3053, #2889, #2940 | offene Wackel-Issues | Behebung Out of Scope; bei Parallel-Artefakt Test in die serielle Gruppe |

## Implementation Details

Entscheidung (Tech Lead, Analyse `docs/context/perf-3209-pytest-laufzeit.md`): Variante B, xdist in CI. Gemessen: lokaler Lauf nutzt nur ca. 51 % eines Kerns (Subprozesse, Sleeps, I/O), die Zeit verteilt sich auf ca. 366 Dateien im Mittelband; Einzeloptimierung wuerde nur ca. 10 % heben.

1. **Dependency:** `pytest-xdist` in `[dependency-groups].dev`, `uv.lock` aktualisieren.
2. **Serielle Gruppe:** In `pytest_collection_modifyitems` erhaelt jeder Test mit Fixture/Marker `real_data_root` automatisch `pytest.mark.xdist_group("echtdaten")`. Mit `--dist loadgroup` laufen alle in demselben Worker, nacheinander. Tests mit relativem Echtbaum-Zugriff werden entweder mit `real_data_root` markiert oder auf `tmp_path` umgestellt.
3. **Waechter worker-fest, nicht lockerer:**
   - `_materialize_real_data_root_fixtures` kopiert genau einmal, geschuetzt durch eine Dateisperre (kein Race zwischen Workern).
   - Der Per-Test-Fingerprint in `_isolate_data_root` und der Session-Vergleich in `_guard_repo_data_users_session` werten Aenderungen am echten Baum nur dann als Verstoss, wenn sie nicht aus der seriellen Gruppe stammen koennen: ausserhalb der Gruppe bleibt jede Aenderung ein Fehler. Konkreter Mechanismus (z. B. Worker-Kennung der Gruppe / Sperrdatei als Marke "Gruppe schreibt gerade") wird im Developer-Schritt gewaehlt, muss aber AC-3 und AC-4 erfuellen.
   - `_raeume_budget_spur_bei_real_data_root` wird auf Parallel-Sicherheit geprueft.
4. **Ratsche:** Statische Pruefung (AST/Regex ueber `tests/`) meldet Testdateien mit relativem `Path("data/users")`, `rmtree` fester user_ids o. ae. ohne `real_data_root`. Neuzugaenge werden rot.
5. **Hygiene:** Feste `/tmp`-Namen in `test_bug305_mobile_email.py` auf `tmp_path`.
6. **CI:** Job `test` ergaenzt `-n 4 --dist loadgroup`; `--disable-socket`, `--ignore=tests/red/`, `$TDD_EXCLUDES`, `--tb=short -rfE` bleiben.
7. **Wackel-Tests:** Zeigt ein Test ein reines Parallel-Artefakt, kommt er in die serielle Gruppe. Zusicherungen werden nie gelockert; der globale `timeout = 30` bleibt, Anhebung nur einzeln per `@pytest.mark.timeout(N)` mit Begruendung.
8. **Nachweise** laufen als echte pytest-Subprozesse auf Beispieldateien (kein Mock-Theater).
9. **Doku:** `gates_und_ratschen.md` beschreibt CI parallel und die Regel fuer Echtbaum-Tests; lokale Gate-Form bleibt als seriell dokumentiert.

## Expected Behavior

- **Input:** Pull Request loest CI-Job `test` aus.
- **Output:** Dieselben Kern-Tests laufen auf 4 Workern; Jobdauer deutlich unter 30 min (Richtwert <= 15 min), Ergebnis gruen.
- **Side effects:** Keine. Kein Gate-Config-Change, keine Produktaenderung, lokaler Volllauf unveraendert seriell.

## Acceptance Criteria

- **AC-1:** Given der CI-Job `test` ist auf `-n 4 --dist loadgroup` umgestellt / When die Testsammlung vor und nach der Umstellung verglichen wird (`--collect-only`, Zahl und Knotenliste, ohne `tests/red/`) / Then ist die Zahl der gesammelten Kern-Tests identisch bis auf die neu hinzugefuegten Wachtests, und kein bisheriger Test fehlt in der Knotenliste.
  - Test: Vergleich der `--collect-only`-Knotenlisten vorher (main) und nachher; Differenz enthaelt ausschliesslich neue Tests; im Issue belegt.

- **AC-2:** Given der parallele CI-Job laeuft auf dem 4-Kern-Runner / When drei aufeinanderfolgende CI-Laeufe der Umstellung ausgewertet werden / Then sind alle drei Laeufe des Jobs `test` gruen und die Jobdauer liegt deutlich unter den bisherigen ca. 30 Minuten (Richtwert 15 Minuten oder weniger).
  - Test: Jobdauer vorher (Lauf 44961923965, ca. 30 min) und nachher (drei Laeufe) im Issue #3209 belegt; lokaler Messwert nur ergaenzend, weil unter Serverlast nicht vergleichbar.

- **AC-3:** Given ein Beispieltest schreibt absichtlich in den echten `data/users`-Baum und traegt keinen `real_data_root`-Marker / When die Beispieldatei in einem pytest-Subprozess einmal seriell und einmal mit `-n 2 --dist loadgroup` laeuft / Then schlaegt der Test in beiden Faellen durch die Echtbaum-Waechter fehl.
  - Test: Mutations-Gegenprobe per Subprozesslauf auf eine Beispieldatei; erwartet Exit-Code ungleich 0 und Waechter-Meldung, seriell und parallel.

- **AC-4:** Given Tests mit `real_data_root` schreiben in den echten Baum und andere Tests ohne Marker laufen gleichzeitig auf anderen Workern / When ein xdist-Lauf mit beiden Testarten ausgefuehrt wird / Then laufen alle `real_data_root`-Tests automatisch in derselben `xdist_group`, kein fremder Test bekommt einen Waechter-Fehler, und die Materialisierung der Echtdaten-Fixtures geschieht nur einmal ohne Race.
  - Test: Subprozesslauf mit `-n 2` auf Beispieldateien; Pruefung der Gruppenzugehoerigkeit (gleicher Worker fuer alle `real_data_root`-Tests) und Gruenlauf der unbeteiligten Tests; Materialisierung genau einmal (Zaehler/Sperrdatei).

- **AC-5:** Given eine Testdatei beruehrt den echten `data/`-Baum (relativer `Path("data/users")` oder `rmtree` fester user_ids) ohne `real_data_root` bzw. Zugehoerigkeit zur seriellen Gruppe / When die Echtbaum-Ratsche laeuft / Then wird der Ratschen-Test rot und nennt die Datei; ohne solche Datei bleibt er gruen.
  - Test: Ratsche gegen eine Beispieldatei im Tmp-Verzeichnis (rot) und gegen eine konforme Datei (gruen); Gegenprobe auf dem echten `tests/`-Baum ist gruen.

- **AC-6:** Given der Lauf nutzt `--disable-socket` und den Loopback-Port-Guard / When ein pytest-Subprozess mit `-n 2` Beispieltests ausfuehrt, die ausgehende Verbindungen bzw. fremde Loopback-Ports oeffnen wollen / Then werden diese Verbindungen in jedem Worker blockiert und nur eigene Ports bleiben erlaubt.
  - Test: Subprozesslauf mit `-n 2`; beide Worker melden Blockade des Egress-Versuchs, eigener `:0`-Port funktioniert.

- **AC-7:** Given die Umstellung ist umgesetzt / When die lokale sichere Offline-Form des Volllaufs durch `broad_test_run_gate.py` geprueft wird / Then bleibt das Gate unveraendert (kein Gate-Config-Change), die Form laeuft seriell, und ein Aufruf mit `-n` wird weiterhin blockiert (lokale parallele Form ist #3278).
  - Test: bestehende Gate-Tests (`test_broad_test_run_gate*.py`) bleiben gruen; ein Gate-Aufruf mit `-n 4` liefert weiterhin die Sperrmeldung.

- **AC-8:** Given `tests/tdd/test_bug305_mobile_email.py` nutzt feste `/tmp`-Namen und die Doku nennt noch einen seriellen CI-Lauf / When die Datei auf `tmp_path` umgestellt und `docs/reference/gates_und_ratschen.md` aktualisiert ist / Then verwendet der Test keine festen `/tmp`-Pfade mehr und laeuft parallel kollisionsfrei, und die Doku beschreibt den parallelen CI-Lauf sowie die Regel "Echtbaum-Tests nur mit `real_data_root`".
  - Test: Test laeuft zweifach gleichzeitig (`-n 2`) ohne Kollision gruen; Doku-Abschnitt als `# doc-compliance-test` nur fuer die Regel-Auffindbarkeit, Verhalten ueber AC-3 bis AC-5 belegt.

## Scope

- **In Scope:** Parallele Ausfuehrung der Python-Kern-Suite im CI-Job `test` (`-n 4 --dist loadgroup`); worker-feste Echtbaum-Waechter; automatische serielle Gruppe fuer `real_data_root`-Tests; Echtbaum-Ratsche; Umstellung fester `/tmp`-Namen; Doku in `gates_und_ratschen.md`.
- **Out of Scope:** lokale parallele Gate-Form (#3278); Scanner-Ratschen-Cache und echte Wartezeiten (#3279); Behebung der Wackel-Issues #3054, #2911, #2898, #3108, #3053, #2889, #2940; jede Produktaenderung; Aenderung der Gate-Config.

## Definition of Done

- AC-1 bis AC-8 erfuellt und durch die Tests im Test Plan belegt.
- Drei aufeinanderfolgende CI-Laeufe mit Job `test` gruen; Jobdauer vorher (Lauf 44961923965, ca. 30 min) und nachher im Issue #3209 belegt.
- `--collect-only`-Vergleich vorher/nachher im Issue belegt: kein Kern-Test entfernt.
- Mutations-Gegenprobe: ein unmarkierter Echtbaum-Schreiber wird seriell und parallel rot.
- Doku `gates_und_ratschen.md` aktualisiert; Folge-Issues #3278 und #3279 bleiben offen verlinkt.

## Test Plan

- `tests/tdd/test_xdist_worker_sicherheit.py` (neu): pytest-Subprozesslaeufe auf Beispieldateien im Tmp-Verzeichnis, seriell und mit `-n 2 --dist loadgroup`:
  - Waechter-Mutation: unmarkierter Schreiber in echtes `data/users` wird rot (AC-3).
  - Gruppenbildung und kein Fehlalarm: alle `real_data_root`-Tests im selben Worker, unbeteiligte Tests gruen, Materialisierung genau einmal (AC-4).
  - Egress-Sperre und Loopback-Port-Guard je Worker (AC-6).
- `tests/tdd/test_xdist_echtbaum_ratsche.py` (neu): Ratsche rot gegen Verstoss-Beispieldatei, gruen gegen konforme Datei und gegen den echten `tests/`-Baum (AC-5).
- Bestehende Gate-Tests `tests/tdd/test_broad_test_run_gate*.py` bleiben gruen; `-n` lokal weiterhin gesperrt (AC-7).
- `tests/tdd/test_bug305_mobile_email.py` laeuft mit `-n 2` kollisionsfrei (AC-8).
- CI-Nachweis: `--collect-only`-Knotenlisten-Vergleich (AC-1) und Jobdauer dreier gruener Laeufe (AC-2).
- Kein Mock-Theater: alle Nachweise ueber echte pytest-Subprozesse.

## Known Limitations

- Lokaler Messwert (56 min, 51 % CPU-Auslastung) entstand unter Serverlast und ist mit CI nicht vergleichbar; Vorher/Nachher gilt ueber die CI-Jobdauer.
- `--durations` ist in 13 freezegun-Dateien unbrauchbar (verstellte Uhr, absurde Werte); Einzelmessung dort per Wanduhr.
- Timing-empfindliche Tests (`test_alert_run_fairness.py`, `test_radar_alarmlauf_fairness.py`, `unit/test_parallel_fetch_deadline.py`, `test_alert_preview_hours_budget.py`, `test_preview_trend_laeuft_nebenlaeufig.py`) sind unter 4 Workern anfaelliger; bei Parallel-Artefakt wandern sie in die serielle Gruppe, Zusicherungen werden nicht gelockert.
- Unter xdist entschuldigt der Per-Test-Waechter eine Aenderung am echten Baum, wenn ein Prozess der Gruppe `echtdaten` denselben Pfad bzw. Teilbaum im selben Zeitfenster (Karenz 1 s) journalisiert hat. Ein unmarkierter Schreiber, der zeitgleich exakt dorthin schreibt, faellt daher erst im Controller-Netto-Vergleich (ohne Ausnahme) oder in der statischen Echtbaum-Ratsche auf; der serielle Lauf bleibt ohne Ausnahme strikt.
- Zwei gleichzeitige pytest-Laeufe im selben Checkout (z. B. zwei Pruefagenten) sehen gegenseitig ihre Echtbaum-Schreibzugriffe und werden rot; das ist gewollte Waechter-Wirkung, kein Parallelisierungsfehler. In CI laeuft je Job ein Lauf.
- Einzelne Timeout-Anhebung wegen Parallel-Last in CI (Liste in `docs/reference/gates_und_ratschen.md`): `tests/refactor/test_epic_129a_3_ui_removed.py::test_ac7_collection_clean` auf 120 s (Sammlung der ganzen Suite per Subprozess, seriell ca. 16 s; erster CI-Lauf riss 30 s).
- Tests an festen, nicht umlenkbaren Repo-Pfaden ausserhalb von `data/users` laufen in je einer eigenen seriellen Gruppe pro Ressource: `repo_backups` (`.backups/`, `test_issue_991_start_time_migration.py`, Backup-Ziel der Migration ist fest verdrahtet) und `repo_validator_env` (`.claude/validator.env` wird von `test_external_validator_auth.py` voruebergehend umbenannt). Ein Neuzugang dieser Art wird nicht statisch erkannt (die Echtbaum-Ratsche deckt nur `data/users` ab).
- Out of Scope: #3278 (lokale parallele Gate-Form), #3279 (Scanner-Ratschen-Cache, echte Wartezeiten), Behebung der Wackel-Issues #3054, #2911, #2898, #3108, #3053, #2889, #2940.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine CI-/Test-Infrastruktur ohne Aenderung an Kanaelen, Providern, Datenmodell oder Auth; die Test-Politik (zwei Schichten, Wachter) bleibt, es wird nur die Ausfuehrungsform in CI parallelisiert.

## Changelog

- 2026-11-22: Initial spec created (Workflow perf-3209-pytest-laufzeit, Issue #3209)
- 2026-11-23: Umsetzung größer als geschätzt (70 Dateien, +2789/-130, davon 0 Produktcode); zusätzlich tests/helpers/echtbaum_ratsche.py und tests/probes_xdist/* (Subprozess-Sonden); einige Lesetests lesen die committete Quelle tests/fixtures/data_root statt der materialisierten Kopie; test_issue_1013 nutzt xdist_group("echtdaten") direkt (gleiche Wirkung wie real_data_root).
- 2026-11-23: Fix-Loop 3: geteilte feste Repo-Pfade (z. B. .backups/) per xdist_group serialisiert. CI-Befund: zwei Tests aus test_issue_991 sahen bzw. loeschten parallel die Backup-Archive des Nachbar-Workers. Gruppen `repo_backups` und `repo_validator_env`; Durchsicht aller Kern-Tests auf feste geteilte Pfade (/tmp, Path.home(), .claude/, docs/artifacts, .backups, logs) ergab keine weiteren Treffer (staging/live-Tests sind in CI abgewaehlt). Kein Produktcode geaendert.
