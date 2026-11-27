# Messprotokoll: Servermessung paralleler sicherer Offline-Volllauf (#3323)

Spec: `docs/specs/modules/testsuite_servermessung_parallel.md` · Abschlussnachweis zu #3278 (AC-7) · Epic #1196
Rohdaten: `docs/artifacts/feat-3323-servermessung/rohdaten/`

**Gesamt-Verdict: BESTANDEN.** #3278 kann geschlossen werden.

## Rahmen

| Angabe | Wert |
|---|---|
| Server | henemm (4 vCPU, ca. 7 GB RAM), neben laufendem Prod und Staging |
| Worktree | `~/gregor_zwanzig/.claude/worktrees/messung-3323` (eigener Worktree, nie im Prod-Checkout) |
| Commit | `cf1a2db0d127b0e4b30696e0473cfd9410aa4eeb` (detached, `origin/main` am 2026-11-27; `ablauf.log`) |
| Reihenfolge | streng nacheinander: erst seriell, dann parallel (`messen.sh`, `wait` je Lauf) |
| Messung | `/usr/bin/time -v` je Lauf; Abtastung alle 10 s über die Prozess-Session (`setsid`): Summe RSS, Summe CPU, Prozesszahl, `MemAvailable`, load1 |
| Abbruchschwelle | `MemAvailable` < 1 GB (1048576 kB) ⇒ Lauf abbrechen, „gescheitert (Speicher)"; **nicht ausgelöst** |

Ausgeführte Befehle (wörtlich aus `ablauf.log`, im Skript mit `/usr/bin/time -v -o … ` davor und ` > datei 2>&1` dahinter):

```bash
uv run pytest --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1,localhost --loopback-own-ports --ignore=tests/red/
nice -n 10 uv run pytest -n 2 --dist loadgroup --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1,localhost --loopback-own-ports --ignore=tests/red/
```

Beide Zeilen stimmen Zeichen für Zeichen mit den Literalen in `docs/reference/gates_und_ratschen.md` (Abschnitt „Sicherer Offline-Volllauf") überein.

## Ergebnisse

| Größe | Seriell | Parallel (`-n 2`) |
|---|---|---|
| Zeitraum (UTC) | 13:54:22 – 14:29:30 | 14:29:30 – 14:50:25 |
| Laufzeit (Wanduhr, time -v) | **35:04** | **20:48** |
| CPU (time -v) | 64 % | 116 % |
| user / sys | 1180,6 s / 182,5 s | 1288,1 s / 165,3 s |
| Max-RSS Einzelprozess (time -v) | 0,97 GB (1012096 kB) | 0,79 GB (830520 kB) |
| Summen-RSS-Spitze (Abtastung, 10 s) | 1,39 GB (1459300 kB, 14:21:39) | 2,11 GB (2210992 kB, 14:50:05; Controller + 2 Worker) |
| min. `MemAvailable` | 3,1 GB (3244016 kB, 14:21:39) | 2,05 GB (2152692 kB, 14:42:43) |
| Ergebnis | 17 failed, 26207 passed, 38 skipped, 708 deselected, 10 xfailed | 17 failed, 26207 passed, 37 skipped, 10 xfailed |
| Exit | 1 (wegen der 17 Roten) | 1 (wegen der 17 Roten) |

xdist meldet `deselected` nicht im Controller-Resümee; `passed` ist identisch. Der eine Skip mehr im seriellen Lauf (38 statt 37) berührt keinen Test des Rot/Grün-Vergleichs (F003); kein AC betroffen. Beide Resümees liegen als `seriell-zusammenfassung.txt` und `parallel-zusammenfassung.txt` bei.

**Laufzeitvergleich:** parallel 20:48 < seriell 35:04 (−41 %) auf demselben Commit und Server. Die Referenz 56:17 min vom 2026-11-22 stammt von einem anderen Commit und dient nur zur Einordnung.

**Messgrenze:** Die Spalte `cpu_summe_pct` der Abtastung ist `ps pcpu` (Lebensdurchschnitt je Prozess) und bei Kurzläufern verzerrt (Spitzen > 100 %). Maßgeblich ist CPU % aus `time -v`.

## Rote Tests

Je 17, Mengen identisch (`seriell-rote.txt` und `parallel-rote.txt`; Vergleich in beide Richtungen leer). Keine zusätzliche Rote im parallelen Lauf.

```
FAILED tests/golden/test_inbound_golden.py::test_deutsch_byte_gleich[de]
FAILED tests/golden/test_inbound_golden.py::test_deutsch_byte_gleich[None]
FAILED tests/golden/test_inbound_golden.py::test_englische_referenz_byte_gleich
FAILED tests/tdd/test_issue_1014_live_optin.py::test_with_optin_gate_returns_true_and_sources_env
FAILED tests/tdd/test_staging_gate.py::TestFix4VerdictWhitelistCaseSensitiveAndTrimmed::test_padded_correct_case_verified_is_accepted_and_passes_check_roundtrip
FAILED tests/tdd/test_staging_gate.py::TestGateWriteVerdictModeA::test_write_verdict_ambiguous_returns_exit0
FAILED tests/tdd/test_staging_gate.py::TestGateWriteVerdictModeA::test_write_verdict_verified_creates_file
FAILED tests/tdd/test_staging_gate.py::TestGateWriteVerdictModeA::test_write_verdict_verified_includes_timestamp
FAILED tests/tdd/test_touched_tests_gate.py::test_2503_ac7b_neuer_roter_frontend_test_ausserhalb_red_blockiert
FAILED tests/tdd/test_touched_tests_gate.py::test_2503_ac7_neuer_roter_frontend_test_in_phase_red_laesst_durch
FAILED tests/tdd/test_touched_tests_gate.py::test_2503_f001b_bestehender_test_im_describe_wird_rot_blockiert
FAILED tests/tdd/test_touched_tests_gate.py::test_2503_f001_neuer_roter_test_im_describe_in_phase_red_laesst_durch
FAILED tests/tdd/test_touched_tests_gate.py::test_2503_f003_flacher_frontend_test_aus_gruen_wird_rot_blockiert
FAILED tests/tdd/test_touched_tests_gate.py::test_2503_f006b_altes_blatt_zwei_ebenen_tief_wird_rot_blockiert
FAILED tests/tdd/test_touched_tests_gate.py::test_2503_f006_neuer_roter_test_zwei_ebenen_tief_in_phase_red_laesst_durch
FAILED tests/tdd/test_touched_tests_gate.py::test_2503_f007_bestehende_frontend_datei_bricht_beim_import_blockiert
FAILED tests/unit/test_secret_output_gate_werkzeugname.py::test_abbruchmeldung_zeigt_fragezeichen_wenn_keine_maskierung_moeglich
```

Einordnung: Der CI-Job `test` ist auf demselben Commit grün
(https://github.com/henemm/gregor_zwanzig/actions/runs/46006708021/job/140531573883). Die 17 sind daher
Server-Umgebungsartefakte, kein Befund auf `main`.

## Prod-Selftest (`prod_selftest.py`)

Aufruf `python3 .claude/hooks/prod_selftest.py` im Prod-Checkout (prüft Prod nur lesend über Commit-Abgleich und HTTP; schreibt wie bei jedem Deploy-Selbsttest seinen Bericht in die git-ignorierte Datei `docs/artifacts/unknown/prod-selftest.md` des Prod-Checkouts, Ordner besteht seit 2026-09-20; keine Prod-Daten berührt), Quelle `selftest.log`:

| Zeitpunkt (UTC) | Anlass | Exit | Verdict |
|---|---|---|---|
| 13:54:22 | Kontrolle vorher (ohne Last) | 0 | PASS |
| 14:39:31 | parallel, 10 min nach Start | 0 | PASS (`verified_commit` = HEAD; `selftest-parallel-10min.txt`) |
| 14:50:25 | Kontrolle nachher | 0 | PASS |

Der geplante Selftest nach 25 min entfiel, weil der parallele Lauf schon nach 20:48 endete.

## Bewertung je Acceptance Criterion

| AC | Ergebnis | Beleg |
|---|---|---|
| AC-1 Laufzeit parallel < seriell | erfüllt | 20:48 < 35:04, gleicher Commit, neben Prod/Staging (`*-time.txt`) |
| AC-2 keine zusätzlichen Roten | erfüllt | 17 = 17, Mengen identisch (`*-rote.txt`) |
| AC-3 Spitzen-RSS und CPU gemessen | erfüllt | time -v beider Läufe, Abtastung beider Läufe |
| AC-4 Prod-Selftest grün während Lauf | erfüllt | 14:39:31 exit 0, PASS; Kontrollen vorher/nachher exit 0 |
| AC-5 eigener Worktree, nacheinander, wörtliche Gate-Form | erfüllt | Worktree-Pfad, Commit, Befehle aus `ablauf.log` |
| AC-6 Summen-RSS Controller + Worker per Abtastung | erfüllt | 10-s-Abtastung, Maximum 2,11 GB, getrennt von time-v-Max-RSS 0,79 GB |
| AC-7 Abbruch bei `MemAvailable` < 1 GB | erfüllt | Prüfung in `messen.sh`; Minimum 2,05 GB, Schwelle nicht unterschritten |
| AC-8 Misserfolgspfad / Verdict | entfällt (Erfolg) | Verdict BESTANDEN, kein Folge-Issue; #3278 kann geschlossen werden |
| AC-9 Referenzdoku nennt Messwerte | erfüllt | `docs/reference/gates_und_ratschen.md`, Abschnitt „Sicherer Offline-Volllauf" |
