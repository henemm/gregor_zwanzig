# Context: perf-3209-pytest-laufzeit

## Request Summary
Issue #3209 (Teil von Epic #1196 Testsuite-Sanierung): Der Python-Offline-Volllauf dauert ~41 min
(24.223 Tests, Bestandsaufnahme #1196-Kommentar 2026-11-20). Ziel: spürbar schneller, ohne
Prüfschärfe zu verlieren. Abschluss: Vorher/Nachher-Laufzeit im Issue belegt, Kern-Schicht 100 %
grün, kein Kern-Test stillschweigend entfernt.

## Ist-Stand (gemessen 2026-11-22)
- `--collect-only` (sichere Offline-Form): 1.719 Dateien, **24.934 Tests** (ohne `tests/red/`).
- Verteilung Testdateien: 181 direkt in `tests/`, 1.623 eine Ebene tiefer (`tdd/`, `unit/`,
  `integration/`, `spec/`, `refactor/`, `visual/`, `e2e/` …), 8 zwei Ebenen tiefer.
- CI-Job `test` (GitHub-Runner ubuntu-24.04, 4 Kerne): ~30 min (Lauf 44961923965: 23:28→23:57)
  und damit **längster CI-Job** (e2e ~22 min, frontend-test ~10 min) — kritischer Pfad jedes PR.
- Server: 4 vCPU, 8 GB RAM, teilt sich die Maschine mit Prod und Staging.
- Grobe Kostentreiber (Dateizählung, nicht gemessen): 146 Testdateien starten Subprozesse,
  70 nutzen `time.sleep`, 130 `TestClient`/uvicorn, 30 Playwright; `tests/conftest.py` hat
  **20 autouse-Fixtures**, viele function-scoped (laufen 25.000× je Test).
- Messlauf „vorher" mit `--durations=0 --durations-min=0.3 --junitxml` läuft
  (Ablage Scratchpad, Ergebnis kommt in die Analyse).

## Related Files
| File | Relevance |
|------|-----------|
| `pyproject.toml` (`[tool.pytest.ini_options]`, `[dependency-groups].dev`) | addopts, globaler `timeout = 30`, Marker; hier käme `pytest-xdist` dazu |
| `tests/conftest.py` (836 Z.) | 20 autouse-Fixtures: Datenwurzel-Isolation (`_isolate_data_root`, session-Materialisierung `_materialize_real_data_root_fixtures`), Egress-Wächter, Cache-Resets, `_patch_testclient_with_core_auth` |
| `conftest.py` (Root, 51 Z.) | Root-Konfiguration |
| `tests/_loopback_port_guard.py` | Plugin hinter `--loopback-own-ports` (Ports je Testprozess — relevant für xdist-Worker) |
| `.github/workflows/ci.yml` (Job `test`) | CI-Aufruf: `--disable-socket … --ignore=tests/red/ $TDD_EXCLUDES --tb=short -rfE` |
| `.github/ci_tdd_excludes.txt` | Ratsche offline-roter tdd-Dateien (aktuell 1 Eintrag) |
| `.claude/hooks/broad_test_run_gate.py` | Gate „Breiter Testlauf gesperrt" (#1477/#1755): vergleicht die sichere Offline-Form **exakt als Rohstring** — jedes Zusatz-Flag (z. B. `-n auto`, `--durations`) blockt |
| `docs/reference/gates_und_ratschen.md` (Abschnitt „Breiter Testlauf gesperrt", Test-Politik) | dokumentierte Pflichtform des Volllaufs, „Läuft ca. 42 min" |
| `tests/tdd/test_broad_test_run_gate*.py` | Fang-Nachweise des Gates — müssen bei einer erweiterten erlaubten Form mitgezogen werden |

## Existing Patterns
- Langläufer deklarieren `@pytest.mark.timeout(N)` statt die globale Schwelle aufzuweichen (#1210).
- Live/Staging/E-Mail-Tests per Marker aus dem Default-Lauf ausgeschlossen (`addopts -m 'not email and not live and not staging'`) — „in die Live-Schicht verschieben" heißt Marker setzen.
- Datenwurzel-Isolation pro Test über `tmp_path_factory` (#1133/#2226) — bei Parallelisierung je Worker eigener Session-Ordner (tmp_path_factory ist xdist-fähig).
- Zeit-Abhängigkeit über `freezegun` (dev-Dependency) statt echter Wartezeit.

## Dependencies
- Upstream: pytest ≥8.4, pytest-timeout, pytest-socket, freezegun, Playwright (visual), Go-Binary in einigen Tests (Subprozess).
- Downstream: CI-Job `test` (Pflicht-Check für jeden PR), Gate `broad_test_run_gate.py`, Doku-Form des sicheren Volllaufs, Agenten/Workflows, die den Volllauf in `/60-validate` nutzen.

## Existing Specs
- Keine Modul-Spec für die Testsuite-Infrastruktur; Regeln in `docs/reference/gates_und_ratschen.md`.
- Epic #1196 (Testsuite-Sanierung), Schwester-Issues zu Wackel-Tests: #3054, #2911, #2898, #3108, #3053, #2889, #2940.

## Risks & Considerations
- **Sicherheitsgate:** Eine schnellere Form (xdist `-n`) muss als neue exakt erlaubte Form ins Gate, ohne die #1477-Sicherheit (Egress-Sperre, Loopback nur eigene Ports) aufzuweichen; Gate-Code = hohes Risiko → Adversary 2 Runden.
- **Reihenfolge-/Zustandsabhängigkeit:** Module- und session-scoped Fixtures, globale Caches (Radar, Wetter, Telegram-Rate-Limit), Uhrzeit-abhängige Tests (#2911, #3053) und die Prozess-Ports von `--loopback-own-ports` können unter xdist anders laufen.
- **Gemeinsame Dateien:** Tests, die `real_data_root` / echtes `data/users/` oder feste Pfade/Ports nutzen, kollidieren bei parallelen Workern.
- **Shared Server:** Ein lokaler Lauf mit 4 Workern konkurriert mit Prod; Worker-Zahl begrenzen.
- **Prüfschärfe:** Beschleunigen darf keine Zusicherung schwächen; Verschieben in die Live-Schicht nur mit fachlicher Begründung und sichtbar (kein stilles Entfernen).
- Messung selbst ist durch das Gate eingeschränkt (`--durations` nicht in der exakten Form erlaubt); Messlauf läuft über die erlaubte Form „Dateien benennen" (Glob über alle `test_*.py`) mit denselben Sicherheits-Flags.

## Messlauf „vorher" (für /20-analyse)
- Gestartet 2026-11-22 ~06:55 im Worktree `wise-sauteeing-frost`, Dauer erwartet ~45 min.
- Ausgabe: `/tmp/claude-1000/-home-hem-gregor-zwanzig/cd9e6853-e296-4a1a-87e2-b625add2f1b8/scratchpad/vorher_lauf.txt`
  (inkl. `/usr/bin/time -v`-Gesamtzeit und `--durations`-Liste ≥0,3 s) und `vorher_junit.xml` (Zeit je Test).
- Kommando: `uv run pytest tests/test_*.py tests/*/test_*.py tests/*/*/test_*.py <sichere Offline-Flags> --ignore=tests/red/ --deselect tests/red/test_issue_435_format_modes.py --durations=0 --durations-min=0.3 --junitxml=… -p no:cacheprovider`
- Fehlt die Datei oder ist sie unvollständig (Sitzung beendet), Messlauf in derselben Form neu starten.
- Neustart 2026-11-22 05:50 UTC (Vorlauf war nicht durchgelaufen), selbe Ausgabedatei.

### Ergebnis Messlauf „vorher" (2026-11-22 05:50–06:46 UTC, Worktree, Server unter Normallast)
- **Wanduhr 56:17 min**; CPU-Zeit 26,3 min user + 2,8 min sys; **CPU-Auslastung 51 %** eines Kerns → rund die Hälfte der Zeit wartet der Lauf (Subprozesse, Sleeps, I/O). Max. RSS 0,9 GB.
- Ergebnis: 24.874 passed, **9 failed, 2 errors**, 38 skipped, 728 deselected, 15 xfailed. Rot: `test_preview_trend_laeuft_nebenlaeufig.py::test_ac3…`, `golden/test_inbound_golden.py` (3), `refactor/test_epic_129a_3_ui_removed.py::test_ac7_collection_clean` (30 s Timeout), `test_authentication_results_parsing.py::…test_h4_resend_is_accepted`, `test_inbound_email_sender_authentication.py::…test_ac13_h4_resend_is_accepted`, `test_issue_1014_live_optin.py::…sources_env`, `unit/test_secret_output_gate_werkzeugname.py::…`; ERROR `test_thunder_scale_local_copy_guard.py` (2, Setup-Timeout 30 s). Gegenprobe: CI-Lauf 44961923965 auf **demselben Commit 43a5c0df1 ist grün** → die Roten sind lokale Umgebungs-/Lastartefakte (Server-.env, 30-s-Timeout unter geteilter Last), kein main-Befund. Konsequenz: lokaler Volllauf ist auf dem geteilten Server nicht als Grün-Nachweis tauglich; Nachher-Vergleich lokal unter gleicher Form messen, Grün-Nachweis über CI.
- `--durations` (≥0,3 s): 1.988 Einträge = 38,6 min; Rest (~23.000 Tests <0,3 s + Sammeln) ≈ 17,5 min.
  - ≥30 s: 7 Einträge, 4,3 min · 10–30 s: 15, 4,0 min · 3–10 s: 87, 7,4 min · 1–3 s: 341, 9,0 min · 0,3–1 s: 1.531, 13,8 min.
  - Die 50 langsamsten zusammen nur ≈ 12–13 min; das Mittelband (0,3–3 s, 1.872 Einträge, 22,8 min) verteilt sich auf **366 Dateien** → Einzeloptimierung erreicht den Großteil nicht.
  - Top-Dateien: `tdd/test_einstellung_gleich_mail_validatoren.py` 200 s (131 Einträge à ~1,2 s), `tdd/test_pytest_collection_and_timeout_safety.py` 166 s (startet eigene pytest-Subprozesse), `test_befehl_antwortzeit.py` 67 s, `tdd/test_alarm_totalausfall_wird_wiederholt.py` 66 s, `tdd/test_design_diff_requires_authenticated_page.py` 64 s (2× ~32 s), `test_versand_lang_durchreichen.py` 62 s, `tdd/test_fixture_wallclock_ratchet.py` 57 s, `tdd/test_thunder_scale_local_copy_guard.py` 48 s, `tdd/test_trip_fixtures_laufen_unter_gestellter_uhr.py` 46 s, `tdd/test_dwd_thunder_parallel_fetch.py` 46 s.
  - Familie „Repo-Scanner-Ratschen" (parsen den ganzen `tests/`-Baum je Test neu): `fixture_wallclock_ratchet`, `repo_path_hardcoding_ratchet`, `test_suite_passes_user_id_explicitly`, `trips_pfad_rueckbau`, `trip_fixtures_laufen_unter_gestellter_uhr`, `thunder_scale_local_copy_guard`, `epic_129a_3_ui_removed` → zusammen ≈ 4 min; Kandidat für einen gemeinsamen, session-gecachten Parse.
  - Echte Wartezeiten: `dwd_thunder_parallel_fetch::…endet_nach_etwa_10s` (10,8 s), `radar_nowcast_segment_wanduhr_unabhaengig` (Mehrfachläufe 15–18 s).
- **Messfehler:** In 13 Dateien (u. a. `test_alarmlauf_einheit_abschottung.py`, `test_trip_briefing_aufbau*.py`, `test_radar_alarmlauf_fairness.py`, `test_alert_hour_rows.py`, `test_freezegun_stapel_reparatur.py`) liefert `--durations` absurde Werte (10⁹ s): freezegun verstellt die von pytest genutzte Uhr. Diese Dateien bei der Nachher-Messung per Wanduhr einzeln messen.
- Rohdaten: `/tmp/claude-1000/-home-hem-gregor-zwanzig/cd9e6853-e296-4a1a-87e2-b625add2f1b8/scratchpad/vorher_lauf.txt`, `vorher_junit.xml`; Auswerteskript `/tmp/claude-1000/-home-hem-gregor-zwanzig--claude-worktrees-wise-sauteeing-frost/c6e3affe-11df-4d5f-b3a9-63b29e51de8d/scratchpad/agg.py`.

## Analyse-Zwischenbefunde (Explore-Agenten 2026-11-22, in ## Analysis zu überführen)

### Gate `broad_test_run_gate.py`
- Erlaubte Volllauf-Formen = Literal-Konstanten `_OFFLINE_CALLS` (L89-96), Rohstring-Vergleich `_offline_form_is_safe` (L288); optional ` > <pfad> 2>&1`.
- `-n` steht weder in `_SAFE_FLAGS` noch `_VALUE_OPTIONS` → heute blockiert. Erweiterung = neue Literal-Form(en) + Blockmeldung `_block` (L344-347).
- Gate-Tests: `tests/tdd/test_broad_test_run_gate_offline_form.py` (Freigaben L64-88, Blockliste L95-177, Blockmeldung L366/L472), `tests/tdd/test_broad_test_run_gate_ignores_override.py` (`ALLOWED` L178-184). Neu nötig: Positiv-/Negativfälle für die xdist-Form (Zusatzflags, `;`/`&&`, `PYTEST_ADDOPTS=`, ohne Loopback-Flags); Sync-Test Doku↔Konstante fehlt heute.
- Fundstellen Form/„42 min": `docs/reference/gates_und_ratschen.md:252,262`, `broad_test_run_gate.py:39,91`, `tests/_loopback_port_guard.py:9`, `docs/specs/modules/fix_1755_offline_volllauf.md:104,129`.
- CI (`ci.yml:66-72`) nutzt eigene Form (ohne `--loopback-own-ports`, mit `$TDD_EXCLUDES`, `--tb=short -rfE`), vom Gate unberührt.
- `pytest-xdist` fehlt in `pyproject.toml` und `uv.lock` → neue dev-Dependency.

### Autouse-Fixtures (22 Stück)
- Alle function-scoped Fixtures <1 ms, kein Subprozess. Einziger nennenswerter Kostenpunkt: `_isolate_data_root` (conftest.py:484) mit zwei `os.walk` von `data/users` je Test — skaliert mit Dateizahl im echten Baum (im Worktree leer, auf Hauptcheckout ggf. relevant; messen).
- Fixture-Hochstufung bringt höchstens µs je Test → **kein relevanter Hebel**; Caches (F9-F13) dürfen nicht hochgestuft werden (Isolation).

### xdist-Tauglichkeit
- Ports unkritisch: alle Stub-Server binden `:0`; `_loopback_port_guard` arbeitet je Prozess (eigenes Port-Set je Worker).
- **Kritisch:** `_guard_repo_data_users_session` (conftest.py:275) und `_isolate_data_root` (:484) vergleichen Fingerprints des **echten** `data/users` — schreibt ein anderer Worker dorthin (`real_data_root`-Tests, 42 Dateien), schlagen fremde Tests fälschlich fehl. `_materialize_real_data_root_fixtures` (:310) kopiert ohne Lock in den echten Baum (Race). `_raeume_budget_spur_bei_real_data_root` (:388) ebenso.
- Relative `Path("data/users")`-Zugriffe mit `rmtree` fester user_ids u. a. in `tests/integration/test_issue_221_validator_endpoints.py`, `test_issue_448_…`, `test_issue_918_…`, `tests/tdd/test_onset_*`, `test_issue_846_alert_preset.py`, `test_issue_731_unified_commands.py`.
- Feste /tmp-Namen: `tests/tdd/test_bug305_mobile_email.py:297,546`.
- Timing-empfindlich unter Last: `test_alert_run_fairness.py`, `test_radar_alarmlauf_fairness.py`, `unit/test_parallel_fetch_deadline.py`, `test_alert_preview_hours_budget.py`, `test_preview_trend_laeuft_nebenlaeufig.py`; globaler `timeout = 30`.
- Keine Reihenfolge-Abhängigkeit (kein pytest-order) gefunden.
- Ansatz: `real_data_root`- und Echt-`data/`-Tests per `xdist_group` in **einen** Worker (`--dist loadgroup`) und Echtbaum-Guards so umbauen, dass sie nur Schreibzugriffe ihres eigenen Workers/außerhalb dieser Gruppe werten — oder diese Tests seriell vorab laufen lassen.

## Analysis

### Type
Feature/Rework (Test-Infrastruktur, keine Produktänderung)

### Entscheidung Zuschnitt (Tech Lead, 2026-11-22)
Strategische Bewertung (Plan/Sonnet), geschätzte Laufzeiten:

| Variante | Lokal (geteilter Server) | CI (4 Kerne) | Kern |
|---|---|---|---|
| A: nur Einzeloptimierung (Scanner-Cache, echte Waits) | ~50 min | ~26–28 min | greift nur ~10 % der Laufzeit |
| B: xdist (`-n 4` CI, `--dist loadgroup`) | ~22–28 min (mit -n 3) | ~10–14 min | überlappt die ~50 % Wartezeit; Mittelband auf 366 Dateien |
| C: A + B | ~18–23 min | ~8–11 min | |

**#3209 = Variante B in CI** (größter Hebel, kritischer Pfad jedes PR, Sicherheits-Gate unberührt). Abgespalten als eigene Sub-Issues von #1196:
- **#3278** lokale parallele Volllauf-Form im Gate (`-n 2/3`, Fang-Nachweise, 2 Adversary-Runden), setzt #3209 voraus.
- **#3279** Repo-Scanner-Ratschen (gemeinsamer gecachter Parse) und echte Wartezeiten (Variante A).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `pyproject.toml`, `uv.lock` | MODIFY | dev-Dependency `pytest-xdist` |
| `tests/conftest.py` | MODIFY | Echtbaum-Wächter worker-fest: `_guard_repo_data_users_session` (:275) und Fingerprint in `_isolate_data_root` (:484) dürfen Schreibzugriffe anderer Worker nicht als eigene werten; `_materialize_real_data_root_fixtures` (:310) einmalig bzw. per Dateisperre; `_raeume_budget_spur_bei_real_data_root` (:388) prüfen; automatische `xdist_group("echtdaten")` für alle `real_data_root`-Tests (`pytest_collection_modifyitems`) |
| Tests mit relativem `Path("data/users")`/`rmtree` fester user_ids (u. a. `tests/integration/test_issue_221_validator_endpoints.py`, `test_issue_448_…`, `test_issue_918_…`, `tests/tdd/test_onset_*`, `test_issue_846_alert_preset.py`, `test_issue_731_unified_commands.py`, `test_issue_991_…`, `test_alert_rules_model.py`, `test_alert_preview_input_validation.py`, `test_issue_612_…`) | MODIFY | Marker `real_data_root` (→ serielle Gruppe) oder Umstellung auf `tmp_path` |
| `tests/tdd/test_bug305_mobile_email.py` | MODIFY | feste `/tmp`-Namen → `tmp_path` |
| neue Ratsche (z. B. `tests/tdd/test_xdist_echtbaum_ratsche.py`) | CREATE | meldet Testdateien, die den echten `data/`-Baum berühren, ohne in der seriellen Gruppe zu sein |
| Worker-Sicherheitstest | CREATE | Egress-Sperre und Loopback-Port-Guard greifen in jedem xdist-Worker (Subprozess-Lauf mit `-n 2` über Beispieldateien) |
| `.github/workflows/ci.yml` (Job `test`) | MODIFY | `-n 4 --dist loadgroup` |
| `docs/reference/gates_und_ratschen.md` | MODIFY | CI parallel; Regel „Echtbaum-Tests nur mit `real_data_root`" |

### Scope Assessment
- Files: ~15–20 (davon ~12 Testdateien mit Kleinständerungen)
- Estimated LoC: +250/−60
- Risk Level: MEDIUM-HIGH (zentrale Test-Fixtures; Wächter dürfen nicht aufgeweicht werden; Fehlalarme unter Parallelität)

### Technical Approach
1. `pytest-xdist` als dev-Dependency.
2. Serielle Gruppe: jeder `real_data_root`-Test bekommt automatisch `xdist_group("echtdaten")`; Tests mit relativen Echtbaum-Zugriffen werden markiert oder auf `tmp_path` umgestellt; Ratsche verhindert Neuzugänge.
3. Wächter worker-fest: Materialisierung genau einmal (Dateisperre), Session-Vergleich nur dort, wo er eindeutig ist, Per-Test-Fingerprint wertet keine Änderungen fremder Worker (Detaillösung in der Spec).
4. Mutations-Gegenprobe: ein absichtlich in den echten Baum schreibender Test ohne Marker muss weiterhin rot werden, seriell UND unter xdist.
5. CI-Job `test` auf `-n 4 --dist loadgroup`; Abnahme: 3 aufeinanderfolgende grüne CI-Läufe, Jobdauer vorher (~30 min, Lauf 44961923965) / nachher im Issue.
6. Lokale Gate-Form bleibt unverändert seriell (→ #3278).

### Dependencies
- Upstream: pytest ≥8.4, pytest-timeout (je Worker aktiv), pytest-socket, `tests/_loopback_port_guard.py` (je Prozess eigenes Port-Set, Stub-Server binden `:0` → unkritisch).
- Downstream: CI-Pflichtcheck `test` jedes PR.
- Offene Wackel-Issues (alle OPEN): #3054, #2911, #2898, #3108, #3053, #2889, #2940. Betroffene Dateien unter xdist beobachten; bei Parallel-Artefakt in die serielle Gruppe statt Zusicherung lockern.

### Befunde gegen den Plan
- Lokaler Messwert (56 min) lief unter Serverlast, nicht mit CI vergleichbar → Vorher/Nachher an der **CI-Jobdauer** (selbe Umgebung), lokal nur ergänzend.
- Timing-Tests (`test_alert_run_fairness.py`, `test_radar_alarmlauf_fairness.py`, `unit/test_parallel_fetch_deadline.py`, `test_alert_preview_hours_budget.py`, `test_preview_trend_laeuft_nebenlaeufig.py`) unter 4 Workern anfälliger; globales `timeout = 30` bleibt, Anhebung nur einzeln per `@pytest.mark.timeout(N)` begründet.
- `--durations` ist in 13 freezegun-Dateien unbrauchbar → Messung über Jobdauer.

### Open Questions
- Keine Produktfrage offen (reine Test-Infrastruktur, Tech-Lead-Entscheidung).
