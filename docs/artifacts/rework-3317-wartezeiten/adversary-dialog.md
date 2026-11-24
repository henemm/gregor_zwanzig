# Adversary Dialog — rework-3317-wartezeiten
Spec: docs/specs/modules/rework_3317_wartezeiten_tempo_s1.md
Datum: 2026-11-24 16:58

## Checkliste
- [x] **Input:** Lauf der vier Testdateien der Scheibe A lokal oder in CI. Beleg: docs/artifacts/rework-3317-wartezeiten/adversary-test-output.txt, seriell 136 passed / 1 failed (DWD ac1: "nur 9 von 12 Zeitpunkten, erwartet >= 10", lokal erlaubt) / 1 skipped, 180,9 s; unter `-n 4 --dist loadgroup` 137 passed / 1 skipped, 49,0 s (ac1 dort grün). Eingeschlossen die vier weiteren Nutzer von `wanduhr_matrix`.
- [x] **Output:** dieselben Zusicherungen wie zuvor (zum Teil strenger), je Datei belegt kürzere oder begründet unveränderte Laufzeit. Beleg: Test-für-Test-Vergleich Alt (a6ccf6ca7) gegen Neu, siehe Runde 1; keine Zusicherung entfallen, die nicht an anderer Stelle belegt ist; Laufzeiten eigene Stichprobe (Sammlung setup 37,9 s + 32,6 s call, Radar 14,0 + 7,9 s, DWD-2-s-Test 7,1 s) stimmt mit messung.md überein.
- [x] **Side effects:** keine; kein Produktcode, kein angehobenes Timeout, `data/users/` bleibt unberührt. Beleg: git status zeigt nur die fünf Testdateien plus docs/context; `src/providers/dwd.py` und `pyproject.toml` hashgleich zur Sicherung; Timeout-Zählung alt/neu: `timeout=30` 3 auf 2, `=60` 4 auf 2, `=90` 5 auf 3, `_SUBPROC_TIMEOUT_SEC` 120 unverändert, DWD und Radar gleich; mtime-Test liest nur Zeitstempel (tests/tdd/test_pytest_collection_and_timeout_safety.py:440).
- [x] **AC-1:** Beleg: `test_genau_eine_voll_sammlung_je_dateilauf` (tests/tdd/test_pytest_collection_and_timeout_safety.py:854) grün seriell und unter `-n 4`; Mutation u6 (mtime-Sammlung ohne Plugin-Kennzeichen) und Dev sam11 (zweite Voll-Sammlung) rot; Exit-/ERROR-Prüfung bleibt in `test_full_suite_collection_still_exits_zero`, Mutation kaputter Import rot (Dev sam1/sam2, ac7_nachher).
- [x] **AC-2:** Beleg: `test_marker_auswahl_der_ableitung_deckt_sich_mit_pytest` (drei echte `-m`-Läufe, email/live/staging je gemischte Datei) grün; Dev-Mutationen sam3 bis sam6b, sam16 rot; Ableitung gegen echte Voll-Sammlung 122/450/152/25021/25715 gleich (mutationen.md). Einschränkung: der echte `-m`-Beleg gilt nur für drei Beispieldateien, sonst Ableitung (F003).
- [x] **AC-3:** Beleg: `test_wirksames_limit_aus_der_echten_konfiguration_ist_30` (:725) und `test_haenger_wird_am_limit_nachweislich_abgebrochen` (:739) grün; eigene Mutation u9 (Umgebung unbereinigt mit PYTEST_TIMEOUT=300) rot; Dev haenger1 bis haenger6.
- [x] **AC-4:** Beleg: Mutation „kaputter Import" in `tests/test_geosphere.py` macht `test_full_suite_collection_still_exits_zero` rot (Dev ac7_vorher_verbleibender_test und ac7_nachher_verbleibender_test); ac7 entfallen (tests/refactor/test_epic_129a_3_ui_removed.py:12 nur noch Verweis). Gleichwertigkeit gelesen: gleicher Exit-Code, ERROR-Zeile aus derselben Sammlung, keine Marker-Abhängigkeit des Importfehlers.
- [x] **AC-5:** Beleg: `test_ac3_default_timeout_10s_wirkt_am_gewitter_request` (tests/tdd/test_dwd_thunder_parallel_fetch.py:653) und `test_testserver_startet_ohne_namensaufloesung` (:642) grün; eigene Mutationen d5 (Frist 5 s im Spion-Test rot), d7 (Timeout x1,5 im Produktcode rot), d8 (Read-Timeout verdreifacht rot), d9 (`super().server_bind()` rot); Dev dwd1 bis dwd6. 2-s-Test unverändert, prüft weiter genau eine Anfrage, Zelle None, Dauer <= 5 s.
- [x] **AC-6:** Beleg: tests/helpers/wanduhr_matrix.py:150 und tests/tdd/test_radar_nowcast_segment_wanduhr_unabhaengig.py:234; Prozessstart-Zähler grün; vier weitere Nutzer von `wanduhr_matrix` grün (Ausgabe); eigene Mutationen u1 (geteilter Ausgabepfad der gleichzeitigen Läufe: `test_matrix_findet_die_kante` rot), u3 (doppelter Start: drei Tests rot), r2 (Referenz unter falscher Uhrzeit: rot), r3 (letzte Uhrzeit nicht gemessen: rot).
- [x] **AC-7:** Beleg: mutationen.md deckt Sammlung, Hänger, DWD, Radar und ac7 je mit rotem Test ab; ich habe 11 eigene Mutationen ergänzt (siehe Runde 2); Hash vor/nach identisch in jedem Lauf; Mutation nur per String-Ersetzung.
- [x] **AC-8:** Beleg: messung.md liefert je Datei Vorher/Nachher seriell und `-n 4`; meine Stichprobe der Neu-Zeiten liegt im selben Bereich (siehe Ausgabe). Einschränkung: Alt-Werte nicht neu gemessen (Alt-Stand ohne Eingriff in die Arbeitskopie nicht lauffähig), die Radar-Gleichzeitigkeit nur auf dem Mac gemessen, nicht auf 4-Kern-Runner.

## Dialog

### Runde 1
**Adversary:** Vergleich Alt und Neu je Test, Leitfrage „Zusicherung verschwunden oder schwächer?".
1. Sammlung: alle Alt-Tests wiedergefunden. `default_/email_/staging_/live_collect` und die Teil-Sammlungen (`-o addopts=`) sind durch das Plugin ersetzt. Alt: Gesamt aus echter `-o addopts=`-Sammlung, `-m email` und `-m live` als echte Läufe. Neu: Gesamt und Marker aus `pytest_itemcollected` bzw. `iter_markers()` zum Zeitpunkt `collection_finish` (nach allen modifyitems). Nur `xdist_group` wird in tests/conftest.py:931 nachträglich vergeben, kein Marker mit Auswahlwirkung; Abgleich 122/450/152 stimmt. Schwächer wäre nur: eine künftige Marker-Vergabe nach der `-m`-Auswahl fiele außerhalb der drei Beleg-Dateien nicht auf (LOW, F003).
2. Hänger: Alt = echter 30-s-Abbruch, nur `returncode != 0`. Neu = Wert 30 aus Konfiguration plus Abbruch bei 3 s mit Timeout-Meldung. Strenger, aber die Verkettung „30 s wirkt tatsächlich in einem Lauf ohne `--timeout`" ist zusammengesetzt, nicht am Stück belegt (laut Spec akzeptiert).
3. DWD: Alt prüfte reale Dauer 9,5 bis 13 s mit echtem Default und echter Standardfrist. Neu: Spion am `httpx.Client.send` sieht 10,0 bei Frist 600 s. Die Standardfrist (150 s) liegt über 10 s; ein Absenken unter 10 s wäre im Altstand rot (Dauer) und ist im Neustand unbemerkt (LOW, F004, kein Spec-Verstoß).
4. ac7: gleichwertig (siehe AC-4).
5. Radar: Alt maß die Referenz zweimal; die zweite Messung konnte eine Instabilität der Referenz sichtbar machen. Entfällt laut Spec. Gleichzeitigkeit: Kind-Prozesse teilen `data/users` (Materialisierung unter Dateisperre, atomar) und bekommen eigene `tmp_path_factory`-Wurzeln.
6. `_umgebung` (tests/tdd/test_pytest_collection_and_timeout_safety.py:304) bereinigt `PYTEST_*`: eigene Mutation u8 (Bereinigung entfernt, ganze Datei unter `-n 4`): 0 rot. Bestätigt Dev sam15. Der Schutz greift nur bei geerbtem `PYTEST_TIMEOUT` (u9 rot) oder `PYTEST_ADDOPTS`; für letzteres gibt es keinen Test (F001).
**Implementierer:** (nicht anwesend; Nachweise nur aus den Dateien mutationen.md und messung.md).

### Runde 2
**Adversary:** Eigene Mutationen, die der Entwickler nicht protokolliert hat (String-Ersetzung, Sicherungskopie im Scratchpad, Hash nach Rückspielen identisch):
- u1 geteilter Ausgabepfad der gleichzeitigen Messungen (wanduhr_matrix.py): ROT (`test_matrix_findet_die_kante`).
- u3 doppelter Prozessstart je Datenpunkt: ROT (3 Tests).
- r2 Referenz unter falscher Uhrzeit eingereicht: ROT (beide Radar-Fälle).
- r3 `matrix_differenz` ohne letzte Uhrzeit: ROT.
- u6 mtime-Sammlung ohne Plugin-Kennzeichen: ROT (`test_genau_eine_voll_sammlung_je_dateilauf`).
- u8 `_umgebung` ohne Bereinigung, ganze Datei `-n 4`: ÜBERLEBT (F001).
- u9 `_umgebung` ohne Bereinigung unter PYTEST_TIMEOUT=300: ROT.
- d5 Standardfrist im Spion-Test auf 5 s: ROT.
- d7 `base_timeout = THUNDER_REQUEST_TIMEOUT * 1.5` im Produktcode: ROT (Spion, auch ac2_budgetende).
- d8 Read-Timeout verdreifacht (`httpx.Timeout`): ROT.
- d9 `_Server.server_bind` ruft wieder `super().server_bind()`: ROT.
Nicht ausgeführt: vier `staging`-markierte Nutzer der Sammlung (Vorgabe: nicht live); ihre Logik gelesen, gegenüber Alt unverändert bis auf die Quelle der Zahlen.
Doku: docs/reference/gates_und_ratschen.md:316 nennt noch `test_ac7_collection_clean` als Timeout-Ausnahme (F002).
**Implementierer:** (nicht anwesend).

## Herkunft der Vorbedingungen

- kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Findings

Code reference: tests/tdd/test_pytest_collection_and_timeout_safety.py:304
Finding F001 (LOW, anti_pattern): `_umgebung` entfernt `PYTEST_*`; Mutation u8 (Bereinigung entfernt, ganze Datei unter `-n 4`) bleibt grün. Geschützt ist nur `PYTEST_TIMEOUT` (u9 rot), nicht `PYTEST_ADDOPTS`. Reproduktion: Zeile 306 `if not k.startswith("PYTEST_")}` zu `}` ändern, Datei mit `-n 4 --dist loadgroup` laufen lassen, 0 rot. Abhilfe: Test mit `monkeypatch.setenv("PYTEST_ADDOPTS", ...)` auf `_umgebung()`. Entspricht sam15; kein Blocker.

Code reference: docs/reference/gates_und_ratschen.md:314
Finding F002 (LOW, anti_pattern): ursprünglich nannte die Zeile `test_ac7_collection_clean` als Timeout-Ausnahme. Behoben: die neue Fassung (Zeilen 314-316) enthält keine ac7-Nennung mehr (grep: 0 Treffer) und nennt die Gruppe `sammlung`, die in tests/tdd/test_pytest_collection_and_timeout_safety.py:301 (`pytest.mark.xdist_group("sammlung")`) tatsächlich so heißt. Geprüft, erledigt.

Code reference: tests/tdd/test_pytest_collection_and_timeout_safety.py:381
Finding F003 (LOW, edge_case): Marker-Ableitung der Fixture `sammlung` ist nur an drei Dateien (AC-2-Test) gegen pytests echte `-m`-Auswahl belegt; Altstand sammelte `-m email`/`-m live` für alle Dateien echt. Heute kein Hook, der Marker nach der Auswahl vergibt (tests/conftest.py:931 nur `xdist_group`), Abgleich 122/450/152 stimmt. Spec sieht diese Form vor.

Code reference: tests/tdd/test_dwd_thunder_parallel_fetch.py:653
Finding F004 (LOW, edge_case): Spion-Test setzt die Frist auf 600 s; ein Absenken von `THUNDER_FETCH_DEADLINE_SECONDS` (heute 150 s) unter 10 s fiel im Altstand über die Dauer 9,5 bis 13 s auf, im Neustand nicht. Kein Spec-Verstoß.

## Geprüfte Stellen je geänderter Datei

Code reference: tests/helpers/wanduhr_matrix.py:150
Geprüft: `matrix_differenz` mit `vorhanden` und `ThreadPoolExecutor`; Mutationen u1, u3, r3 rot.

Code reference: tests/refactor/test_epic_129a_3_ui_removed.py:12
Geprüft: `test_ac7_collection_clean` entfernt, Verweis auf `test_full_suite_collection_still_exits_zero`; Mutation kaputter Import dort rot.

Code reference: tests/tdd/test_dwd_thunder_parallel_fetch.py:140
Geprüft: `server_bind` ohne `getfqdn`; Mutation d9 rot; Spion-Test :653 mit Mutationen d5, d7, d8 rot.

Code reference: tests/tdd/test_pytest_collection_and_timeout_safety.py:854
Geprüft: Zähler der Voll-Sammlungen; Mutationen u6 und sam11 rot; Hänger-Tests :725 und :739 mit u9 rot.

Code reference: tests/tdd/test_radar_nowcast_segment_wanduhr_unabhaengig.py:234
Geprüft: Referenz wird über `vorhanden={referenzzeit: referenz}` wiederverwendet, Prozessstart-Zähler :238; Mutationen r2, r3, u3 rot.

## Verdict
**VERIFIED** (keine CRITICAL, HIGH oder MEDIUM; F001 bis F004 LOW, F002 behoben)

## Geprüfte Dateien

- sha256:bc2807611fddd20bf0451b82af8c6950998b416a5129c58153240acea9630bfc  docs/reference/gates_und_ratschen.md
- sha256:0ff6c21bf7a7c2a04ab99708f5f3c4d419f5eced3202eb9229828560f3991efe  tests/helpers/wanduhr_matrix.py
- sha256:8c0463df1ccd691c883d15e856cd84cf56ef6ed24eae0225b71d95c9ce33b930  tests/refactor/test_epic_129a_3_ui_removed.py
- sha256:f05d4b66d805d4a47336293445d4621fe88471c40ff37488a3333a7eef5517f5  tests/tdd/test_dwd_thunder_parallel_fetch.py
- sha256:8b42790b231040ae5c85b8868d4647d9557239a35d8751eb3176b07bb0fda2bf  tests/tdd/test_pytest_collection_and_timeout_safety.py
- sha256:7a32e9b8beec3300140f3c3dd1fb88db6b725d98bd49a1ac2c06d10b513f954d  tests/tdd/test_radar_nowcast_segment_wanduhr_unabhaengig.py

## Prüfbasis

- base: a6ccf6ca7cdac41c87867ee1a2f90df048959597
- blob:ddc2e06e403acc8f1012fb7058a9511879e81371  docs/reference/gates_und_ratschen.md
- blob:a1679e34c37aa8c4f8bcf3be735771b695189a31  tests/helpers/wanduhr_matrix.py
- blob:96a3deb984035273c36309a7aca0a1c9517b20e6  tests/refactor/test_epic_129a_3_ui_removed.py
- blob:1a30a96fa726c7e33da1286e077143aa7391b464  tests/tdd/test_dwd_thunder_parallel_fetch.py
- blob:cb96c7adb01adb012eda4b03d4fcd6906cae547c  tests/tdd/test_pytest_collection_and_timeout_safety.py
- blob:a70cbc79339f548ce93337e8d0309c72f48ee65e  tests/tdd/test_radar_nowcast_segment_wanduhr_unabhaengig.py
