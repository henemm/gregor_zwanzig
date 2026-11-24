# Mutations-Gegenprobe #3317 Scheibe A (24.11.2026, Mac, Python 3.12, pytest 9.2)

Verfahren: String-Ersetzung, externe Sicherungskopie im Sitzungs-Scratchpad, Zurückspielen per Kopie, SHA-256 (erste 16 Stellen) vorher/nachher. Kein `git checkout/stash/reset`. "ROT" heißt: mindestens ein Test FAILED oder ERROR.

**ac7-Entscheidung (AC-4):** Die Mutation "kaputter Import" ist in `test_full_suite_collection_still_exits_zero` vor UND nach dem Umbau rot (Exit-Code-Prüfung; die ERROR-Prüfung allein belegt sam1). `test_ac7_collection_clean` entfällt.

**Überlebt:**
- `sam6_live_ohne_einen_test`: Fehlbau der Mutation (der Präfix trifft keinen Test, also wirkungsgleich mit dem Original). Richtig gebaut als `sam6b`: rot.
- `sam15_umgebung_unbereinigt_n4`: ohne Bereinigung der `PYTEST_*`-Umgebung bleiben die Kennungen unter `-n 4` unverändert. Die Falle "`@<gruppe>` in den Kennungen des Kindprozesses" tritt heute nicht ein. Die Bereinigung bleibt, weil `haenger6` zeigt, dass sie gegen ein geerbtes `PYTEST_TIMEOUT` nötig ist; für die Kennungen ist sie reine Vorsorge. Würden Kennungen verfälscht, zeigten es die AC-2-Tests und der Abgleich mit pytests eigener Ausgabe.

**Nicht ausgeführt:** die vier `staging`-markierten Nutzer der Sammlung (Regel: Staging nur sammeln). Die staging-Ableitung ist durch den AC-2-Test und den Abgleich am Ende belegt.

**Stand der Testdateien:** alle Mutationen liefen gegen den Endstand; einzige spätere Änderung war das Zeitlimit des Kindprozesses in `_kindlauf` (120 auf 60 s gesenkt), danach wurden alle `haenger`-Mutationen wiederholt (die Hashes von `haenger*` gehören zum Endstand, die der übrigen zum Stand davor).

**Vorher-Lauf ac7_vorher_*:** gegen den Stand vor dem Umbau (RED-Commit; `default_collect` und Testrumpf identisch mit a6ccf6ca7).

### ac7_vorher_verbleibender_test (AC-4)
- Datei: `tests/test_geosphere.py`
- Verfälschung: `'import pytest' -> 'import pytest\nimport gz_modul_gibt_es_nicht_3317'`
- Befehl: `uv run pytest tests/tdd/test_pytest_collection_and_timeout_safety.py -k test_full_suite_collection_still_exits_zero -p no:cacheprovider`
- Erwartet: rot
- Tatsächlich: **ROT** (Exit 1; 1 failed, 25 deselected, 2 warnings in 45.65s); rot: test_full_suite_collection_still_exits_zero
- Hash vorher `de795beb4385ed20`, mutiert `0a58942f2f44041d`, nachher `de795beb4385ed20`, identisch: True

### ac7_vorher_ac7 (AC-4)
- Datei: `tests/test_geosphere.py`
- Verfälschung: `'import pytest' -> 'import pytest\nimport gz_modul_gibt_es_nicht_3317'`
- Befehl: `uv run pytest tests/refactor/test_epic_129a_3_ui_removed.py -k test_ac7 -p no:cacheprovider`
- Erwartet: rot
- Tatsächlich: **ROT** (Exit 1; 1 failed, 5 deselected, 2 warnings in 37.11s); rot: test_ac7_collection_clean
- Hash vorher `de795beb4385ed20`, mutiert `0a58942f2f44041d`, nachher `de795beb4385ed20`, identisch: True

### ac7_nachher_verbleibender_test (AC-4)
- Datei: `tests/test_geosphere.py`
- Verfälschung: `'import pytest' -> 'import pytest\nimport gz_modul_gibt_es_nicht_3317'`
- Befehl: `uv run pytest tests/tdd/test_pytest_collection_and_timeout_safety.py -k test_full_suite_collection_still_exits_zero -p no:cacheprovider`
- Erwartet: rot
- Tatsächlich: **ROT** (Exit 1; 1 failed, 24 deselected, 2 warnings in 41.12s); rot: test_full_suite_collection_still_exits_zero
- Hash vorher `de795beb4385ed20`, mutiert `0a58942f2f44041d`, nachher `de795beb4385ed20`, identisch: True

### dwd1_konstante_30 (AC-5)
- Datei: `src/providers/dwd.py`
- Verfälschung: `'THUNDER_REQUEST_TIMEOUT = 10.0' -> 'THUNDER_REQUEST_TIMEOUT = 30.0'`
- Befehl: `uv run pytest tests/tdd/test_dwd_thunder_parallel_fetch.py -k 'ac3 or testserver' -p no:cacheprovider`
- Erwartet: rot: Konstanten-Prüfung (Spion siehe dwd1b)
- Tatsächlich: **ROT** (Exit 1; 1 failed, 2 passed, 17 deselected, 2 warnings in 14.61s); rot: test_ac3_default_timeout_10s_wirkt_am_gewitter_request
- Hash vorher `67ec354953fa7074`, mutiert `ede762a1cfc9b5d4`, nachher `67ec354953fa7074`, identisch: True

### dwd2_literal_30 (AC-5)
- Datei: `src/providers/dwd.py`
- Verfälschung: `'base_timeout=THUNDER_REQUEST_TIMEOUT,' -> 'base_timeout=30.0,'`
- Befehl: `uv run pytest tests/tdd/test_dwd_thunder_parallel_fetch.py -k 'ac3 or testserver' -p no:cacheprovider`
- Erwartet: rot: Spion
- Tatsächlich: **ROT** (Exit 1; 2 failed, 1 passed, 17 deselected, 2 warnings in 20.44s); rot: test_ac3_default_timeout_10s_wirkt_am_gewitter_request, test_ac3_haengender_download_kostet_hoechstens_den_timeout_und_wird_nicht_wiederholt
- Hash vorher `67ec354953fa7074`, mutiert `b0ffca3cb2d856aa`, nachher `67ec354953fa7074`, identisch: True

### dwd3_literal_10 (AC-5)
- Datei: `src/providers/dwd.py`
- Verfälschung: `'base_timeout=THUNDER_REQUEST_TIMEOUT,' -> 'base_timeout=10.0,'`
- Befehl: `uv run pytest tests/tdd/test_dwd_thunder_parallel_fetch.py -k 'ac3 or testserver' -p no:cacheprovider`
- Erwartet: rot: 2-s-Test; Spion grün
- Tatsächlich: **ROT** (Exit 1; 1 failed, 2 passed, 17 deselected, 2 warnings in 20.20s); rot: test_ac3_haengender_download_kostet_hoechstens_den_timeout_und_wird_nicht_wiederholt
- Hash vorher `67ec354953fa7074`, mutiert `388662a5da8c78a2`, nachher `67ec354953fa7074`, identisch: True

### dwd4_retry_an (AC-5)
- Datei: `src/providers/dwd.py`
- Verfälschung: `'return isinstance(exception, httpx.ConnectError)' -> 'return isinstance(exception, (httpx.ConnectError, httpx.ReadTimeout))'`
- Befehl: `uv run pytest tests/tdd/test_dwd_thunder_parallel_fetch.py -k 'ac3 or testserver' -p no:cacheprovider`
- Erwartet: rot: 2-s-Test
- Tatsächlich: **ROT** (Exit 1; 1 failed, 2 passed, 17 deselected, 2 warnings in 17.94s); rot: test_ac3_haengender_download_kostet_hoechstens_den_timeout_und_wird_nicht_wiederholt
- Hash vorher `67ec354953fa7074`, mutiert `b930105795c316aa`, nachher `67ec354953fa7074`, identisch: True

### dwd5_spion_sieht_nichts (AC-5)
- Datei: `tests/tdd/test_dwd_thunder_parallel_fetch.py`
- Verfälschung: `'if any(f"/{p}/" in request.url.path for p in dwd.THUNDER_PARAMS):' -> 'if False:'`
- Befehl: `uv run pytest tests/tdd/test_dwd_thunder_parallel_fetch.py -k 'ac3 or testserver' -p no:cacheprovider`
- Erwartet: rot
- Tatsächlich: **ROT** (Exit 1; 1 failed, 2 passed, 17 deselected, 2 warnings in 14.25s); rot: test_ac3_default_timeout_10s_wirkt_am_gewitter_request
- Hash vorher `f05d4b66d805d4a4`, mutiert `71793f06d4afcca4`, nachher `f05d4b66d805d4a4`, identisch: True

### dwd6_server_bind_weg (AC-5)
- Datei: `tests/tdd/test_dwd_thunder_parallel_fetch.py`
- Verfälschung: `'TCPServer.server_bind(self)' -> 'super().server_bind()'`
- Befehl: `uv run pytest tests/tdd/test_dwd_thunder_parallel_fetch.py -k 'ac3 or testserver' -p no:cacheprovider`
- Erwartet: rot
- Tatsächlich: **ROT** (Exit 1; 1 failed, 2 passed, 17 deselected, 2 warnings in 13.67s); rot: test_testserver_startet_ohne_namensaufloesung
- Hash vorher `f05d4b66d805d4a4`, mutiert `bbf6b2485ce7bb3e`, nachher `f05d4b66d805d4a4`, identisch: True

### haenger1_konfiguration_300 (AC-3)
- Datei: `tests/tdd/test_pytest_collection_and_timeout_safety.py`
- Verfälschung: `'_PYPROJECT = _REPO_ROOT / "pyproject.toml"' -> "_PYPROJECT = Path('/private/tmp/claude-501/-Users-hem-Developer-gregor-zwanzig--claude-worktrees-rework-3279-testsuite-tempo/d6b655ec-58a3-4f43-9df2-b400514eacb2/scratchpad/pyproject_300/pyproject.toml')"`
- Befehl: `uv run pytest tests/tdd/test_pytest_collection_and_timeout_safety.py -k 'wirksames_limit or haenger' -p no:cacheprovider`
- Erwartet: rot
- Tatsächlich: **ROT** (Exit 1; 1 failed, 1 passed, 23 deselected, 2 warnings in 7.13s); rot: test_wirksames_limit_aus_der_echten_konfiguration_ist_30
- Hash vorher `8b42790b231040ae`, mutiert `a85c896e623870b6`, nachher `8b42790b231040ae`, identisch: True

### haenger2_wert_fest_verdrahtet (AC-3)
- Datei: `tests/tdd/test_pytest_collection_and_timeout_safety.py`
- Verfälschung: `'write(str(settings.timeout))' -> "write('30.0')"`
- Befehl: `uv run pytest tests/tdd/test_pytest_collection_and_timeout_safety.py -k 'wirksames_limit or haenger' -p no:cacheprovider`
- Erwartet: rot
- Tatsächlich: **ROT** (Exit 1; 1 failed, 1 passed, 23 deselected, 2 warnings in 8.05s); rot: test_wirksames_limit_aus_der_echten_konfiguration_ist_30
- Hash vorher `8b42790b231040ae`, mutiert `8a7149c17b3f7e1f`, nachher `8b42790b231040ae`, identisch: True

### haenger3_kein_kurzes_limit (AC-3)
- Datei: `tests/tdd/test_pytest_collection_and_timeout_safety.py`
- Verfälschung: `', f"--timeout={limit_s}")' -> ')'`
- Befehl: `uv run pytest tests/tdd/test_pytest_collection_and_timeout_safety.py -k 'wirksames_limit or haenger' -p no:cacheprovider`
- Erwartet: rot
- Tatsächlich: **ROT** (Exit 1; 1 failed, 1 passed, 23 deselected, 2 warnings in 34.90s); rot: test_haenger_wird_am_limit_nachweislich_abgebrochen
- Hash vorher `8b42790b231040ae`, mutiert `5df2d7cdf1a22bfc`, nachher `8b42790b231040ae`, identisch: True

### haenger4_timeout_plugin_aus (AC-3)
- Datei: `tests/tdd/test_pytest_collection_and_timeout_safety.py`
- Verfälschung: `', f"--timeout={limit_s}")' -> ', "-p", "no:timeout", "-o", "timeout=")'`
- Befehl: `uv run pytest tests/tdd/test_pytest_collection_and_timeout_safety.py -k 'wirksames_limit or haenger' -p no:cacheprovider`
- Erwartet: rot
- Tatsächlich: **ROT** (Exit 1; 1 failed, 1 passed, 23 deselected, 2 warnings in 63.76s (0:01:03)); rot: test_haenger_wird_am_limit_nachweislich_abgebrochen
- Hash vorher `8b42790b231040ae`, mutiert `85c96e3cc3e198c8`, nachher `8b42790b231040ae`, identisch: True

### haenger5_scheitert_ohne_abbruch (AC-3)
- Datei: `tests/tdd/test_pytest_collection_and_timeout_safety.py`
- Verfälschung: `'f"time.sleep({haenger_s})"' -> '"assert False"'`
- Befehl: `uv run pytest tests/tdd/test_pytest_collection_and_timeout_safety.py -k 'wirksames_limit or haenger' -p no:cacheprovider`
- Erwartet: rot
- Tatsächlich: **ROT** (Exit 1; 1 failed, 1 passed, 23 deselected, 2 warnings in 4.97s); rot: test_haenger_wird_am_limit_nachweislich_abgebrochen
- Hash vorher `8b42790b231040ae`, mutiert `3dcf362ea5d93244`, nachher `8b42790b231040ae`, identisch: True

### haenger6_umgebung_unbereinigt_mit_PYTEST_TIMEOUT_300 (AC-3)
- Datei: `tests/tdd/test_pytest_collection_and_timeout_safety.py`
- Verfälschung: `'for k, v in os.environ.items() if not k.startswith("PYTEST_")}' -> 'for k, v in os.environ.items()}'`
- Befehl: `uv run pytest tests/tdd/test_pytest_collection_and_timeout_safety.py -k 'wirksames_limit or haenger' -p no:cacheprovider`
- Erwartet: rot
- Tatsächlich: **ROT** (Exit 1; 1 failed, 1 passed, 23 deselected, 2 warnings in 7.47s); rot: test_wirksames_limit_aus_der_echten_konfiguration_ist_30
- Hash vorher `8b42790b231040ae`, mutiert `4c5eba67df6f881a`, nachher `8b42790b231040ae`, identisch: True

### radar1_vorhanden_ignoriert (AC-6)
- Datei: `tests/helpers/wanduhr_matrix.py`
- Verfälschung: `'vorhanden = vorhanden or {}' -> 'vorhanden = {}'`
- Befehl: `uv run pytest tests/tdd/test_radar_nowcast_segment_wanduhr_unabhaengig.py -p no:cacheprovider`
- Erwartet: rot
- Tatsächlich: **ROT** (Exit 1; 3 failed, 2 warnings in 30.07s); rot: test_matrix_verwendet_vorhandene_messung_wieder, test_radar_segment_tests_liefern_zu_jeder_wanduhrzeit_dasselbe_ergebnis
- Hash vorher `0ff6c21bf7a7c2a0`, mutiert `b01ddbdcd9d0f60c`, nachher `0ff6c21bf7a7c2a0`, identisch: True

### radar2_referenz_geht_nicht_ein (AC-6)
- Datei: `tests/helpers/wanduhr_matrix.py`
- Verfälschung: `'messungen = [vorhanden[u] for u in uhrzeiten if u in vorhanden] + list(neu)' -> 'messungen = list(neu)'`
- Befehl: `uv run pytest tests/tdd/test_radar_nowcast_segment_wanduhr_unabhaengig.py -p no:cacheprovider`
- Erwartet: rot
- Tatsächlich: **ROT** (Exit 1; 1 failed, 2 passed, 2 warnings in 29.57s); rot: test_matrix_verwendet_vorhandene_messung_wieder
- Hash vorher `0ff6c21bf7a7c2a0`, mutiert `bbb2a3e35d901f42`, nachher `0ff6c21bf7a7c2a0`, identisch: True

### radar3_leere_referenz_im_radartest (AC-6)
- Datei: `tests/tdd/test_radar_nowcast_segment_wanduhr_unabhaengig.py`
- Verfälschung: `'vorhanden={referenzzeit: referenz})' -> 'vorhanden={referenzzeit: {}})'`
- Befehl: `uv run pytest tests/tdd/test_radar_nowcast_segment_wanduhr_unabhaengig.py -p no:cacheprovider`
- Erwartet: rot
- Tatsächlich: **ROT** (Exit 1; 2 failed, 1 passed, 2 warnings in 30.42s); rot: test_radar_segment_tests_liefern_zu_jeder_wanduhrzeit_dasselbe_ergebnis
- Hash vorher `7a32e9b8beec3300`, mutiert `e22ad0e376be15f0`, nachher `7a32e9b8beec3300`, identisch: True

### radar4_leere_referenz_im_helfer (AC-6)
- Datei: `tests/helpers/wanduhr_matrix.py`
- Verfälschung: `'[vorhanden[u] for u in' -> '[{} for u in'`
- Befehl: `uv run pytest tests/tdd/test_radar_nowcast_segment_wanduhr_unabhaengig.py -p no:cacheprovider`
- Erwartet: rot
- Tatsächlich: **ROT** (Exit 1; 2 failed, 1 passed, 2 warnings in 30.25s); rot: test_radar_segment_tests_liefern_zu_jeder_wanduhrzeit_dasselbe_ergebnis
- Hash vorher `0ff6c21bf7a7c2a0`, mutiert `643b6660c52f2419`, nachher `0ff6c21bf7a7c2a0`, identisch: True

### radar5_ein_prozess_fuer_alle (AC-6)
- Datei: `tests/helpers/wanduhr_matrix.py`
- Verfälschung: `'offen = [uhrzeit for uhrzeit in uhrzeiten if uhrzeit not in vorhanden]' -> 'offen = [uhrzeit for uhrzeit in uhrzeiten if uhrzeit not in vorhanden][:1]'`
- Befehl: `uv run pytest tests/tdd/test_radar_nowcast_segment_wanduhr_unabhaengig.py -p no:cacheprovider`
- Erwartet: rot
- Tatsächlich: **ROT** (Exit 1; 2 failed, 1 passed, 2 warnings in 26.85s); rot: test_radar_segment_tests_liefern_zu_jeder_wanduhrzeit_dasselbe_ergebnis
- Hash vorher `0ff6c21bf7a7c2a0`, mutiert `77cf83577a82ec49`, nachher `0ff6c21bf7a7c2a0`, identisch: True

### sam1_exit_pruefung_weg_und_kaputter_import (AC-1)
- Datei: `tests/tdd/test_pytest_collection_and_timeout_safety.py`; zusätzlich in tests/test_geosphere.py: 'import pytest' -> 'import pytest\nimport gz_modul_gibt_es_nicht_3317'
- Verfälschung: `'assert default_collect.returncode == 0, default_collect.stderr\n    assert "ERROR" not in' -> 'assert "ERROR" not in'`
- Befehl: `uv run pytest tests/tdd/test_pytest_collection_and_timeout_safety.py -k 'full_suite' -p no:cacheprovider`
- Erwartet: rot
- Tatsächlich: **ROT** (Exit 1; 1 failed, 24 deselected, 2 warnings in 46.57s); rot: test_full_suite_collection_still_exits_zero
- Hash vorher `57ae8b3725b8f769`, mutiert `4e4794eb24488da7`, nachher `57ae8b3725b8f769`, identisch: True

### sam2_error_pruefung_weg_und_kaputter_import (AC-1)
- Datei: `tests/tdd/test_pytest_collection_and_timeout_safety.py`; zusätzlich in tests/test_geosphere.py: 'import pytest' -> 'import pytest\nimport gz_modul_gibt_es_nicht_3317'
- Verfälschung: `'assert "ERROR" not in default_collect.stdout, default_collect.stdout' -> ''`
- Befehl: `uv run pytest tests/tdd/test_pytest_collection_and_timeout_safety.py -k 'full_suite' -p no:cacheprovider`
- Erwartet: rot
- Tatsächlich: **ROT** (Exit 1; 1 failed, 24 deselected, 2 warnings in 46.83s); rot: test_full_suite_collection_still_exits_zero
- Hash vorher `57ae8b3725b8f769`, mutiert `1f61da8d415a8be0`, nachher `57ae8b3725b8f769`, identisch: True

### sam3_marker_ohne_modulmarker (AC-1/2)
- Datei: `tests/tdd/test_pytest_collection_and_timeout_safety.py`
- Verfälschung: `'for m in i.iter_markers()' -> 'for m in i.own_markers'`
- Befehl: `uv run pytest tests/tdd/test_pytest_collection_and_timeout_safety.py -k 'b1_live_leak or full_suite or email_marker or b3_ or c2_ or marker_auswahl or genau_eine' -p no:cacheprovider`
- Erwartet: rot
- Tatsächlich: **ROT** (Exit 1; 6 failed, 5 passed, 14 deselected, 2 warnings in 49.99s); rot: test_b3_module_files_excluded_from_default, test_b3_partial_files_partition, test_default_selection_excludes_b1_live_leak_files, test_email_marker_run_still_collects_b1_files, test_marker_auswahl_der_ableitung_deckt_sich_mit_pytest
- Hash vorher `57ae8b3725b8f769`, mutiert `5ffb12625254a24c`, nachher `57ae8b3725b8f769`, identisch: True

### sam4_ableitung_liefert_alles (AC-1/2)
- Datei: `tests/tdd/test_pytest_collection_and_timeout_safety.py`
- Verfälschung: `'for k, namen in marker.items() if name in namen}' -> 'for k, namen in marker.items()}'`
- Befehl: `uv run pytest tests/tdd/test_pytest_collection_and_timeout_safety.py -k 'b1_live_leak or full_suite or email_marker or b3_ or c2_ or marker_auswahl or genau_eine' -p no:cacheprovider`
- Erwartet: rot
- Tatsächlich: **ROT** (Exit 1; 6 failed, 5 passed, 14 deselected, 2 warnings in 52.16s); rot: test_b3_partial_files_partition, test_c2_returned_tests_in_default_selection, test_default_selection_excludes_b1_live_leak_files, test_marker_auswahl_der_ableitung_deckt_sich_mit_pytest
- Hash vorher `57ae8b3725b8f769`, mutiert `423f32f1b6903aae`, nachher `57ae8b3725b8f769`, identisch: True

### sam5_ableitung_liefert_nichts (AC-1/2)
- Datei: `tests/tdd/test_pytest_collection_and_timeout_safety.py`
- Verfälschung: `'for k, namen in marker.items() if name in namen}' -> 'for k, namen in marker.items() if False}'`
- Befehl: `uv run pytest tests/tdd/test_pytest_collection_and_timeout_safety.py -k 'b1_live_leak or full_suite or email_marker or b3_ or c2_ or marker_auswahl or genau_eine' -p no:cacheprovider`
- Erwartet: rot
- Tatsächlich: **ROT** (Exit 1; 8 failed, 3 passed, 14 deselected, 2 warnings in 55.51s); rot: test_b3_module_files_excluded_from_default, test_b3_partial_files_partition, test_c2_returned_tests_in_default_selection, test_default_selection_excludes_b1_live_leak_files, test_email_marker_run_still_collects_b1_files, test_marker_auswahl_der_ableitung_deckt_sich_mit_pytest
- Hash vorher `57ae8b3725b8f769`, mutiert `f1c491c4a8f74892`, nachher `57ae8b3725b8f769`, identisch: True

### sam6_live_ohne_einen_test (AC-2)
- Datei: `tests/tdd/test_pytest_collection_and_timeout_safety.py`
- Verfälschung: `'for k, namen in marker.items() if name in namen}' -> 'for k, namen in sorted(marker.items())[1:] if name in namen and not k.startswith("tests/tdd/test_issue_608_sms_seven_io.py::test_s")}'`
- Befehl: `uv run pytest tests/tdd/test_pytest_collection_and_timeout_safety.py -k 'b1_live_leak or full_suite or email_marker or b3_ or c2_ or marker_auswahl or genau_eine' -p no:cacheprovider`
- Erwartet: keine (Verfälschung wirkungslos gebaut: kein Test beginnt so), ersetzt durch sam6b
- Tatsächlich: **GRÜN (überlebt)** (Exit 0; 11 passed, 14 deselected, 2 warnings in 53.80s); rot: keiner
- Hash vorher `57ae8b3725b8f769`, mutiert `48bd94b96889ccd1`, nachher `57ae8b3725b8f769`, identisch: True

### sam7_gewaehlt_gleich_gesamt (AC-1)
- Datei: `tests/tdd/test_pytest_collection_and_timeout_safety.py`
- Verfälschung: `'for i in session.items]' -> 'for i in _items]'`
- Befehl: `uv run pytest tests/tdd/test_pytest_collection_and_timeout_safety.py -k 'b1_live_leak or full_suite or email_marker or b3_ or c2_ or marker_auswahl or genau_eine' -p no:cacheprovider`
- Erwartet: rot
- Tatsächlich: **ROT** (Exit 1; 14 deselected, 2 warnings, 11 errors in 43.79s); rot: test_b3_module_files_excluded_from_default, test_b3_partial_files_partition, test_c2_full_live_files_stay_excluded, test_c2_returned_tests_in_default_selection, test_default_selection_excludes_b1_live_leak_files, test_email_marker_run_still_collects_b1_files, test_full_suite_collection_still_exits_zero, test_genau_eine_voll_sammlung_je_dateilauf, test_marker_auswahl_der_ableitung_deckt_sich_mit_pytest
- Hash vorher `57ae8b3725b8f769`, mutiert `2073bfcf7d7d270b`, nachher `57ae8b3725b8f769`, identisch: True

### sam8_gewaehlt_unvollstaendig (AC-1)
- Datei: `tests/tdd/test_pytest_collection_and_timeout_safety.py`
- Verfälschung: `'for i in session.items]' -> 'for i in session.items[1:]]'`
- Befehl: `uv run pytest tests/tdd/test_pytest_collection_and_timeout_safety.py -k 'b1_live_leak or full_suite or email_marker or b3_ or c2_ or marker_auswahl or genau_eine' -p no:cacheprovider`
- Erwartet: rot
- Tatsächlich: **ROT** (Exit 1; 14 deselected, 2 warnings, 11 errors in 45.67s); rot: test_b3_module_files_excluded_from_default, test_b3_partial_files_partition, test_c2_full_live_files_stay_excluded, test_c2_returned_tests_in_default_selection, test_default_selection_excludes_b1_live_leak_files, test_email_marker_run_still_collects_b1_files, test_full_suite_collection_still_exits_zero, test_genau_eine_voll_sammlung_je_dateilauf, test_marker_auswahl_der_ableitung_deckt_sich_mit_pytest
- Hash vorher `57ae8b3725b8f769`, mutiert `dd04cfa593857260`, nachher `57ae8b3725b8f769`, identisch: True

### sam9_plugin_schreibt_nichts (AC-1)
- Datei: `tests/tdd/test_pytest_collection_and_timeout_safety.py`
- Verfälschung: `'def pytest_collection_finish(session):' -> 'def pytest_nie(session):'`
- Befehl: `uv run pytest tests/tdd/test_pytest_collection_and_timeout_safety.py -k 'b1_live_leak or full_suite or email_marker or b3_ or c2_ or marker_auswahl or genau_eine' -p no:cacheprovider`
- Erwartet: rot
- Tatsächlich: **ROT** (Exit 1; 14 deselected, 2 warnings, 11 errors in 38.66s); rot: test_b3_module_files_excluded_from_default, test_b3_partial_files_partition, test_c2_full_live_files_stay_excluded, test_c2_returned_tests_in_default_selection, test_default_selection_excludes_b1_live_leak_files, test_email_marker_run_still_collects_b1_files, test_full_suite_collection_still_exits_zero, test_genau_eine_voll_sammlung_je_dateilauf, test_marker_auswahl_der_ableitung_deckt_sich_mit_pytest
- Hash vorher `57ae8b3725b8f769`, mutiert `13399d5973d5844f`, nachher `57ae8b3725b8f769`, identisch: True

### sam10_plugin_schreibt_leer (AC-1)
- Datei: `tests/tdd/test_pytest_collection_and_timeout_safety.py`
- Verfälschung: `'"marker": {i.nodeid: sorted({m.name for m in i.iter_markers()}) for i in _items},\n            "gewaehlt": [i.nodeid for i in session.items],' -> '"marker": {}, "gewaehlt": [],'`
- Befehl: `uv run pytest tests/tdd/test_pytest_collection_and_timeout_safety.py -k 'b1_live_leak or full_suite or email_marker or b3_ or c2_ or marker_auswahl or genau_eine' -p no:cacheprovider`
- Erwartet: rot
- Tatsächlich: **ROT** (Exit 1; 14 deselected, 2 warnings, 11 errors in 44.69s); rot: test_b3_module_files_excluded_from_default, test_b3_partial_files_partition, test_c2_full_live_files_stay_excluded, test_c2_returned_tests_in_default_selection, test_default_selection_excludes_b1_live_leak_files, test_email_marker_run_still_collects_b1_files, test_full_suite_collection_still_exits_zero, test_genau_eine_voll_sammlung_je_dateilauf, test_marker_auswahl_der_ableitung_deckt_sich_mit_pytest
- Hash vorher `57ae8b3725b8f769`, mutiert `923d545a40f2ef03`, nachher `57ae8b3725b8f769`, identisch: True

### sam11_zweite_vollsammlung (AC-1)
- Datei: `tests/tdd/test_pytest_collection_and_timeout_safety.py`
- Verfälschung: `'return sammlung.lauf' -> 'return _collect(timeout=90)'`
- Befehl: `uv run pytest tests/tdd/test_pytest_collection_and_timeout_safety.py -k 'full_suite or genau_eine' -p no:cacheprovider`
- Erwartet: rot
- Tatsächlich: **ROT** (Exit 1; 1 failed, 1 passed, 23 deselected, 2 warnings in 92.15s (0:01:32)); rot: test_genau_eine_voll_sammlung_je_dateilauf
- Hash vorher `57ae8b3725b8f769`, mutiert `3e3e3a5ce61838d4`, nachher `57ae8b3725b8f769`, identisch: True

### sam13_ein_nutzer_ohne_gruppe (AC-1)
- Datei: `tests/tdd/test_pytest_collection_and_timeout_safety.py`
- Verfälschung: `'@_sammlungsgruppe\ndef test_full_suite' -> 'def test_full_suite'`
- Befehl: `uv run pytest tests/tdd/test_pytest_collection_and_timeout_safety.py -k 'full_suite or worker_gruppe' -p no:cacheprovider`
- Erwartet: rot
- Tatsächlich: **ROT** (Exit 1; 1 failed, 1 passed, 23 deselected, 2 warnings in 47.92s); rot: test_nutzer_der_sammlung_teilen_eine_worker_gruppe
- Hash vorher `57ae8b3725b8f769`, mutiert `70d855c7a7e7aea7`, nachher `57ae8b3725b8f769`, identisch: True

### sam14_sammlung_beruehrt_echtdaten (AC-1)
- Datei: `tests/test_geosphere.py`
- Verfälschung: `'import pytest' -> "import pathlib\n\nimport pytest\n\nfor _p in (pathlib.Path(__file__).parents[1] / 'data/users/default/trips').glob('*.json'):\n    _p.touch()"`
- Befehl: `uv run pytest tests/tdd/test_pytest_collection_and_timeout_safety.py -k 'footgun' -p no:cacheprovider`
- Erwartet: rot
- Tatsächlich: **ROT** (Exit 1; 1 failed, 24 deselected, 2 warnings, 1 error in 47.77s); rot: test_friendly_format_footgun_not_collected_by_default
- Hash vorher `de795beb4385ed20`, mutiert `ee1d8f98daf37a3e`, nachher `de795beb4385ed20`, identisch: True

### sam15_umgebung_unbereinigt_n4 (AC-1)
- Datei: `tests/tdd/test_pytest_collection_and_timeout_safety.py`
- Verfälschung: `'for k, v in os.environ.items() if not k.startswith("PYTEST_")}' -> 'for k, v in os.environ.items()}'`
- Befehl: `uv run pytest tests/tdd/test_pytest_collection_and_timeout_safety.py -k 'b1_live_leak or full_suite or email_marker or b3_ or c2_ or marker_auswahl or genau_eine' -p no:cacheprovider -n 4 --dist loadgroup`
- Erwartet: grün oder rot offen (Frage: verfälscht PYTEST_XDIST_WORKER die Kennungen?)
- Tatsächlich: **GRÜN (überlebt)** (Exit 0; 11 passed, 10 warnings in 56.12s); rot: keiner
- Hash vorher `57ae8b3725b8f769`, mutiert `71d87c6432292716`, nachher `57ae8b3725b8f769`, identisch: True

### sam16_m_option_fehlt_im_beleg (AC-2)
- Datei: `tests/tdd/test_pytest_collection_and_timeout_safety.py`
- Verfälschung: `'res = _collect("-v", "-m", marker, datei, timeout=90)' -> 'res = _collect("-v", datei, timeout=90)'`
- Befehl: `uv run pytest tests/tdd/test_pytest_collection_and_timeout_safety.py -k 'marker_auswahl' -p no:cacheprovider`
- Erwartet: rot
- Tatsächlich: **ROT** (Exit 1; 3 failed, 22 deselected, 2 warnings in 54.69s); rot: test_marker_auswahl_der_ableitung_deckt_sich_mit_pytest
- Hash vorher `57ae8b3725b8f769`, mutiert `b3d6da3b6393e44d`, nachher `57ae8b3725b8f769`, identisch: True

### dwd1b_konstante_30_nur_spion (AC-5)
- Datei: `src/providers/dwd.py`; zusätzlich in tests/tdd/test_dwd_thunder_parallel_fetch.py: 'assert dwd.THUNDER_REQUEST_TIMEOUT == 10.0' -> ''
- Verfälschung: `'THUNDER_REQUEST_TIMEOUT = 10.0' -> 'THUNDER_REQUEST_TIMEOUT = 30.0'`
- Befehl: `uv run pytest tests/tdd/test_dwd_thunder_parallel_fetch.py -k default_timeout_10s -p no:cacheprovider`
- Erwartet: rot im Spion
- Tatsächlich: **ROT** (Exit 1; 1 failed, 19 deselected, 2 warnings in 3.71s); rot: test_ac3_default_timeout_10s_wirkt_am_gewitter_request
- Hash vorher `67ec354953fa7074`, mutiert `ede762a1cfc9b5d4`, nachher `67ec354953fa7074`, identisch: True

### sam6b_live_ohne_einen_test (AC-2)
- Datei: `tests/tdd/test_pytest_collection_and_timeout_safety.py`
- Verfälschung: `'for k, namen in marker.items() if name in namen}' -> 'for k, namen in list(marker.items()) if name in namen and k != min(x for x, y in marker.items() if "live" in y and x.startswith("tests/tdd/test_issue_608_sms_seven_io.py"))}'`
- Befehl: `uv run pytest tests/tdd/test_pytest_collection_and_timeout_safety.py -k 'marker_auswahl or b3_partial' -p no:cacheprovider`
- Erwartet: rot
- Tatsächlich: **ROT** (Exit 1; 2 failed, 2 passed, 21 deselected, 2 warnings in 57.18s); rot: test_b3_partial_files_partition, test_marker_auswahl_der_ableitung_deckt_sich_mit_pytest
- Hash vorher `57ae8b3725b8f769`, mutiert `9b9eecce3a1d55e4`, nachher `57ae8b3725b8f769`, identisch: True

## Einmaliger Abgleich: Ableitung gegen echte Voll-Sammlungen (Mengen der Kennungen)

| Auswahl | pytest echt | Ableitung | Mengen gleich |
|---|---|---|---|
| `-m email` | 122 | 122 | ja |
| `-m live` | 450 | 450 | ja |
| `-m staging` | 152 | 152 | ja |
| Standardauswahl | 25021 | 25021 | ja |
| `-o addopts=` (Gesamt) | 25715 | 25715 | ja |

## Timeout-Meldung an der echten Ausgabe

`Failed: Timeout (>30.0s) from pytest-timeout.` (haenger3, Ausgabe oben); mit kurzem Limit `Timeout (>3.0s)`. Das Muster `Timeout \(>\s*3(\.0)?s\)` trifft die echte Ausgabe (Test grün) und nicht den 30-s-Abbruch (haenger3 rot).
