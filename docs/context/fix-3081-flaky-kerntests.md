# Context: fix-3081-flaky-kerntests

## Request Summary
Issue #3081 (Teil von #1196): zwei Kern-Tests wackeln. (1) `test_alert_channel_threshold.py::test_ac11_…`
soll reihenfolgeabhängig rot sein (`alerts_sent=0`, E-Mail leer), (2) `test_radar_parallel_fetch.py`
flakt (`test_ac4_trip_grenzabbruch_im_worker…`, `test_ac9_trip_zwei_nutzer_gleichzeitig_getrennt`).
DoD: Ursache benannt, kein Retry/Skip, je 10 Läufe grün einzeln + im Batch + zufällige Reihenfolge,
Zusicherungen bleiben scharf (Mutations-Gegenprobe).

## Reproduktion (2026-11-16, Stand origin/main ad6d06b51)
- `test_radar_parallel_fetch.py` allein: 2 von 4 Läufen rot, jeweils `test_ac4_trip_grenzabbruch…`
  mit `hit_deadline=False`, `duration_s≈1000` (Uhrsprung hat stattgefunden, Abbruch kam nicht im Hauptfaden an).
- `tests/tdd/test_alert*.py` (92 Dateien) in Standardreihenfolge: grün (1 Lauf).
- AC-11 nach `test_radar_parallel_fetch.py`, `test_compare_official_alert.py`,
  `test_952_onset_alert_fidelity.py`, `test_avalanche_official_alert_channels.py`: jeweils grün.
  → Reihenfolge-Auslöser noch nicht gefunden; Analyse muss ihn suchen (z. B. per Bisektion über
  zufällige Reihenfolgen). Kein Zufallsreihenfolge-Plugin installiert (`pytest-randomly` fehlt);
  `freezegun 1.5.5` ist vorhanden.
- Hinweis Werkzeug: Ausgabe hat keine Summenzeile (`-q` + Projekt-addopts) → Exit-Code auswerten.
  `broad_test_run_gate` blockt pytest-Aufrufe ohne wörtlich benannte Dateien.

## Related Files
| File | Relevance |
|------|-----------|
| tests/tdd/test_radar_parallel_fetch.py | Flakender Test; `_Uhr` (echte monotonic + Versatz), `_warte_auf_worker`, `_Rand` mit `bei_anfrage`/`verzoegerung` (echte `time.sleep`) |
| src/services/radar_service.py:478-545 | `RadarDeadlineExceeded`, `_raise_if_deadline`, `hole_nowcasts` (fetch_ordered mit `deadline_at=frist`), `wirf_radar_grenze` (wirft nur bei `out.error` vom Typ RadarDeadlineExceeded) |
| src/services/parallel_fetch.py | `fetch_ordered`: `skipped="deadline"` (nicht gestartet) / `"timeout"` (lief noch bei Fristablauf) — Verdacht: Worker-Abbruch wird bei Fristablauf als `timeout` statt als Fehler eingesammelt ⇒ `wirf_radar_grenze` sieht ihn nicht |
| src/services/trip_alert.py:1847-1870, 2053-2110, 2334-2383 | `_radar_folgepunkte`, Radar-Lauf mit `hit_deadline`, Fristprüfung im Hauptfaden |
| tests/tdd/test_alert_channel_threshold.py:788-876 | AC-11: Compare-Amtswarnung + Trip mit Telegram-Schwelle; nutzt globale Registry `_REGISTERED_SOURCES` (Backup/Restore), Fixtures aus `test_compare_official_alert.py` |
| tests/tdd/test_compare_official_alert.py | Fixtures `_sources_backup`, `_FakeOfficialAlertSource`, `_write_presets`, `_clean_user` |
| src/services/compare_official_alert.py · src/services/official_alerts.py | Compare-Amtswarnungsdienst, Quellen-Registry (globaler Zustand), Dedupe/Throttle |

## Existing Patterns
- Uhr-Steuerung in Tests: `freeze_time` + eigene `_Uhr` für `time.monotonic` (Radar-Tests).
- Globale Registries werden per Backup/Restore im `try/finally` geschützt (`_sources_backup`).
- `parallel_fetch._reset_for_tests()`, `reset_shared_radar_cache_for_tests()` als Test-Resets.
- Nutzer-Isolation über eindeutige `uid` je Test + `_clean_user`.

## Dependencies
- Upstream: freezegun, ThreadPoolExecutor (`parallel_fetch`), Dateisystem unter `data/users/<uid>`.
- Downstream: CI-Job `test` (Kern-Schicht), Gates, die „main grün“ voraussetzen.

## Existing Specs
- Issue-Specs zu #1539 (Radar parallel fetch) und #2261 (Alarmlauf-Frist) unter `docs/specs/` — in der Analyse nachschlagen.
- Test-Politik: `docs/reference/gates_und_ratschen.md` (kein Mock-Theater, Kern 100 % grün).

## Risks & Considerations
- Radar-AC-4 kann ein echter Produktions-Race sein (Grenzabbruch im Worker geht als `timeout` verloren
  ⇒ Lauf wertet als nicht abgebrochen). Dann ist der Fix im Produktionscode, nicht im Test — Analyse
  muss das klären, bevor der Test „stabilisiert“ wird.
- AC-11-Auslöser nicht reproduziert: Analyse muss erst reproduzieren (Zufallsreihenfolge/Bisektion), sonst kein Fix auf Verdacht.
- Zusicherungen dürfen nicht aufgeweicht werden (Mutations-Gegenprobe Pflicht).

## Analysis

### Type
Bug (Test-Stabilität, Kern-Schicht). Zwei unabhängige Ursachen.

### Befund 1 — Radar AC-4 (`test_ac4_trip_grenzabbruch_im_worker_bricht_die_einheit_ab`): Wettlauf im Testaufbau
Reproduziert: Datei allein 3 von 8 Läufen rot (`hit_deadline=False`, `duration_s≈1000`).
Sonde auf `wirf_radar_grenze` (Outcomes je Lauf) zeigt den Mechanismus:

- `uhr.sprung(1000)` passiert im Worker (AROME-Anfrage des 3. Soll-Punkts), **während der Hauptfaden
  noch in der Einreich-Schleife von `fetch_ordered` steht** (Open-Meteo-Semaphore = 3 Slots, 4 Folgepunkte
  ⇒ der Hauptfaden wartet in `_acquire_slots` auf einen freien Slot).
- Danach: restliche Punkte `skipped="deadline"`, `wait(timeout=max(deadline-now,0)) = 0` ⇒ sofortiges Einsammeln.
- Ob der Worker, der `RadarDeadlineExceeded` wirft, zu diesem Zeitpunkt schon fertig ist, entscheidet der
  Zufall: grün, wenn gerade SEIN Slot-Freigeben den Hauptfaden geweckt hat (dann `error=RadarDeadlineExceeded`);
  rot, wenn ein anderer Worker den Slot freigab und der werfende noch in seiner 0,1-s-Verzögerung steckt
  (dann `skipped="timeout"` ⇒ Lücke, kein Neuwurf, Einheit wird ausgewertet ⇒ `hit_deadline=False`).
  Beobachtet grün: `[(0,err RDE),(1,timeout),(2,timeout),(3,deadline),(4,deadline)]`.
- Produktionscode verhält sich spec-konform: AC-8 (übersprungen/Zeitüberschreitung ⇒ Lücke) und AC-4
  (im Worker geworfener Grenzabbruch ⇒ Neuwurf) sind beide umgesetzt; welcher Zweig greift, hängt allein
  davon ab, ob der Abbruch VOR dem Einsammeln eintrifft. Der Test stellt diese Vorbedingung nicht her.
- **Ursache:** Testaufbau — der Uhrsprung ist nicht mit dem Zustand des Hauptfadens synchronisiert.

**Fix (nur Test):** Uhrsprung erst, wenn der Hauptfaden alle Aufgaben eingereicht hat und im Warten auf die
Ergebnisse steht. Umsetzung: dünne Naht `monkeypatch.setattr(parallel_fetch, "wait", _wait_mit_signal)`,
die ein `threading.Event` setzt und an das echte `concurrent.futures.wait` delegiert (kein Mock, echtes
Verhalten); `bei_anfrage` für Index 2/AROME wartet (mit Zeitlimit, Testaufbau-Assert bei Ablauf) auf das
Event und springt dann. Dann ist das Warte-Zeitlimit des Hauptfadens (vor dem Sprung berechnet) groß, der
werfende Worker liefert sicher `error=RadarDeadlineExceeded` ⇒ Neuwurf ⇒ Abbruch. Zusicherungen bleiben
wörtlich gleich; Mutation 6 der S4-Spec („RDE im Hauptfaden zu Lücke") muss weiterhin AC-4 rot machen.
Kein Deadlock: der wartende Worker hält 1 von 3 Slots, die übrigen Punkte laufen über die 2 anderen.
Gleiches Muster prüfen für `test_ac5_compare_grenzabbruch…` (gleicher Aufbau mit `time.sleep(0.4)` statt
Synchronisation — dort maskiert die Wartezeit den Wettlauf nur).

**Nebenbefund (eigenes Issue, nicht Teil dieses Fixes):** Unter echter Uhr endet `wait` genau an der Frist,
während ein Worker die Frist erst an der nächsten Kettengrenze bemerkt. Der AC-4-Zweig (Neuwurf ⇒ Einheit
abgebrochen, kein „erreicht"-Stempel) ist in Produktion daher praktisch unerreichbar; eine mitten in der
Parallelphase ablaufende Frist führt stets in den AC-8-Zweig (Lücken, Einheit wird mit Lücken ausgewertet
und als erreicht gestempelt). Keine falsche Entwarnung (Lücke ≠ trocken), aber Abweichung von der Absicht
aus ADR-0082. Bewertung/Entscheidung gehört in ein eigenes Issue (Strang A).

### Befund 2 — AC-11 (`test_ac11_ortsvergleich_alarm_unveraendert_trotz_trip_kanal_schwellen`): NOCH NICHT REPRODUZIERT
Stand 2026-11-16: Batch aller 92 `tests/tdd/test_alert*.py` + `test_compare_official_alert.py` +
`test_radar_parallel_fetch.py`, Seeds 0 (Standardreihenfolge), 11, 22, 33 (zufällig gemischt): AC-11 jedes Mal
GRÜN; rot war nur Radar-AC-4 (Befund 1). Seeds 44 und 55: komplett grün. Summe: 6 Batch-Läufe, AC-11 6× grün ⇒ zufälliges Mischen innerhalb der
`test_alert*`-Familie reproduziert nicht; nächster Schritt ist der gezielte Prüfweg unten (Importeure außerhalb der Familie).
Werkzeug (Scratchpad, nicht im Repo, ggf. neu anlegen): Plugin `mischen_3081.py` mit
`random.Random(int(os.environ["MISCH_SEED"])).shuffle(items)` in `pytest_collection_modifyitems`, geladen per
`PYTHONPATH=<dir>:src` und `-p mischen_3081`; alle Testdateien wörtlich benennen (Gate gegen breite Läufe),
daher Aufruf aus einem per Write erzeugten Skript mit ausgeschriebener Dateiliste.

Arbeitshypothese (ungeprüft, nächster Schritt): `test_compare_official_alert.py:49` fasst
`_NOW = datetime.now(timezone.utc)` **beim Modul-Import**; `_DEFAULT_VALID_FROM/TO` (Gültigkeit der
Testwarnung) hängen daran. AC-11 importiert das Modul **lazy im Test**. Wird es zum ersten Mal unter einer
eingefrorenen Uhr importiert — durch einen Test außerhalb der `test_alert*`-Familie, der es lazy importiert
(Kandidaten: `test_compare_alert_day_window.py:863ff` mit `_friere_uhr`, `test_alarmlauf_einheit_abschottung.py:279`,
`tests/unit/test_compare_*`) — liegt die Warnung später außerhalb des Fensters ⇒ kein Alarm, E-Mail leer.
Passt zum Symptom und erklärt, warum der reine `test_alert*`-Batch grün ist (dort importiert nur AC-11 selbst,
zur echten Zeit). Validierung #1767 lief vermutlich in einem breiteren Batch.
Prüfweg: Kandidaten-Datei(en) VOR `test_alert_channel_threshold.py` im selben Lauf, ohne
`test_compare_official_alert.py` (sonst Import bei der Sammlung zur echten Zeit); rot ⇒ Ursache belegt.
Fix-Richtung, falls bestätigt: Warnungszeiten je Aufruf aus der aktuellen Uhr bilden statt beim Import —
nur Testhilfen, Zusicherungen unverändert. Erst nach Reproduktion (DoD: kein Fix auf Verdacht).

Nachtrag 2026-11-16 (Sitzung 2):
- Hypothese „Modul-Import unter eingefrorener Uhr" VERWORFEN: die Kandidaten frieren nicht per freezegun ein,
  sondern patchen nur `datetime` im Dienst (`_freeze_compare_official_alert_now`) bzw. importieren vor dem Einfrieren;
  `datetime.now()` im Testmodul bleibt echt.
- Tageszeit-Abhängigkeit VERWORFEN: AC-11 allein unter freezegun (tick) um 03:00, 08:00, 12:00, 16:30, 19:00,
  21:30, 23:30 jeweils grün (Plugin `uhr_3081.py` im Scratchpad).
- Mögliche Pfade zu `alerts_sent=0` (aus dem Dienst gelesen): Ausnahme im Preset (→ failed=1, z. B. Abruf
  `skipped` über den globalen `parallel_fetch`-Executor/Semaphor „official_alerts"), Gate (Ruhezeit/Tageslimit),
  Briefing-Sperre, Identitäts-Gate. Nächster Prüfweg: breiter Batch (test_compare*/official*/alarm*/alert*/radar*/
  trip_alert*, 284 Dateien) mit AC-11 ans Ende sortiert (Plugin `ac11_zuletzt.py`).
- Breiter Batch (284 Dateien: tdd/test_compare*, official*, alarm*, alert*, radar*, trip_alert*; AC-11 ans Ende
  sortiert): komplett GRÜN (Exit 0), AC-11 grün, Radar-AC-4 in diesem Lauf ebenfalls grün.
- Gesamtbild AC-11: 6 Familien-Batches (4 gemischt), 1 breiter Batch, 7 Tageszeiten, Einzelläufe: nie rot.
  Seit der Beobachtung (#1767, geschlossen 2026-11-09) keine inhaltliche Änderung an AC-11, Fixtures,
  `compare_official_alert.py`, `parallel_fetch.py` (nur Kommentar in `alert_gate.py`).
- Plausibelster Mechanismus (aus dem Code, nicht reproduziert): `alerts_sent=0` bei leerer E-Mail entsteht u. a.,
  wenn das Preset scheitert (`failed=1`), z. B. weil der Warn-Abruf über den PROZESSWEITEN `parallel_fetch`-
  Executor (8 Worker) und das Semaphor `official_alerts` (3 Slots) läuft. Beide werden zwischen Tests NICHT
  zurückgesetzt (kein autouse-Reset in conftest); Worker früherer Tests, die nach Testende weiterlaufen
  (Radar-Tests mit `skipped="timeout"`, Parallel-Fixtures mit `Event.wait`/`sleep`), belegen Slots weiter.
  Da der Test heute nur „E-Mail leer" meldet, verrät ein Rotlauf seine Ursache nicht.

### Entscheidung (Tech Lead)
- Befund 1 (Radar AC-4, Ursache belegt): Testaufbau synchronisieren wie oben; dasselbe Muster bei AC-5 (Compare)
  statt `time.sleep(0.4)`.
- Befund 2 (AC-11, nicht reproduzierbar): KEIN Fix auf Verdacht an Fixtures oder Dienst. Stattdessen
  (a) Testhygiene nach etablierter Praxis: autouse-Fixture in `tests/conftest.py`, die `parallel_fetch._reset_for_tests()`
  nach jedem Test aufruft (prozessweiter Zustand gehört zwischen Tests zurückgesetzt, wie bereits bei 11 Dateien
  einzeln gemacht) — schließt den einzigen gefundenen testübergreifenden Kanal zum Compare-Warnabruf;
  (b) Diagnose schärfen, Zusicherung unverändert: Fehlermeldung von AC-11 nennt `last_failed_count` und
  `last_checked_count`, damit ein künftiger Rotlauf seine Ursache benennt;
  (c) DoD-Nachweis: je 10 Läufe einzeln, im Batch und gemischt (Plugin im Scratchpad), dokumentiert im Issue.

### Affected Files (geplant)
| File | Change Type | Description |
|------|-------------|-------------|
| tests/tdd/test_radar_parallel_fetch.py | MODIFY | AC-4: Uhrsprung an „Hauptfaden wartet" koppeln (Event-Naht an `parallel_fetch.wait`, delegiert an das echte `wait`) |
| tests/tdd/test_radar_parallel_fetch.py (AC-5) | MODIFY | gleiches Synchronisationsmuster statt fester Wartezeit |
| tests/conftest.py | MODIFY | autouse-Reset des prozessweiten Parallelabrufs nach jedem Test |
| tests/tdd/test_alert_channel_threshold.py | MODIFY | AC-11-Fehlermeldung nennt failed/checked (Zusicherung unverändert) |

### Scope Assessment
- Files: 3 (nur Tests) · Estimated LoC: +45/-8 · Risk Level: LOW (kein Produktionscode)

### Open Questions
- [x] AC-11 Reproduktion versucht (siehe Nachtrag): nicht reproduzierbar; Vorgehen siehe Entscheidung.
- [ ] AC-9-Trip-Flake: in 8 Einzel- und 4 Batch-Läufen nicht aufgetreten; nach AC-4-Fix 10× Datei-Lauf beobachten.
- [ ] Nebenbefund „AC-4-Zweig in Produktion praktisch unerreichbar" als eigenes Issue anlegen.
