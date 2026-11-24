# Adversary Dialog — rework-3279-testsuite-tempo
Spec: docs/specs/modules/rework_3279_scanner_ratschen_tempo_s1.md
Datum: 2026-11-24 08:22

## Checkliste
- [x] **Input:** Lauf der drei Scanner-Dateien (lokal oder CI) gegen den echten `tests/`-Baum bzw. `tmp_path`.
- [x] **Output:** dieselben Funde wie vorher, spürbar kürzere Laufzeit, kein Test der drei Dateien reisst auf dem Mac mehr das 30-s-Netz.
- [x] **Side effects:** keine; kein Produktcode, keine Timeout-Anhebung, `KNOWN_VIOLATIONS` unverändert.
- [x] **AC-1:** Given der echte `tests/`-Baum auf einem festen Commit / When die drei Scanner einmal gefiltert und einmal ungefiltert laufen / Then liefern beide je Scanner dieselben Funde (wallclock direkt 1, indirekt 0, gestellte_uhr 10 auf Stand der Messung) und `KNOWN_VIOLATIONS` bleibt unverändert.
- [x] **AC-2:** Given je Scanner eine gepflanzte Testdatei mit echtem Verstoß in `tmp_path` / When der gefilterte Scanner läuft / Then wird der Verstoß gefunden, beim indirekten Scanner auch bei Alias-Import von `Stage`.
- [x] **AC-3:** Given je Scanner eine gepflanzte Datei, deren Bezeichner in Nicht-ASCII-Schreibweise steht (Fullwidth-Buchstaben, NFKC-gleich) / When der gefilterte Scanner läuft / Then wird sie trotzdem gefunden.
- [x] **AC-4:** Given ein künstlich verfälschter Filter (falscher Name, UND statt ODER, NFKC weg, immer False) bzw. ein verfälschter Cache (liefert leere Liste oder wirkt auf `tmp_path`) / When die Tests der jeweiligen Ratsche laufen / Then ist je Verfälschung mindestens ein Test rot, belegt je umgebauter Ratsche.
- [x] **AC-5:** Given der Cache der beiden Cache-Dateien / When zwei `tmp_path`-Läufe mit unterschiedlichem Inhalt laufen, eine zurückgegebene Liste verändert wird und der echte Baum mehrfach abgefragt wird / Then liefert jeder Lauf seine eigenen Funde, der nächste Aufruf bleibt unverändert, und der echte Baum wird je Regel im Prozess nur einmal gescannt.
- [x] **AC-6:** Given eine `.py` unter der Wurzel ist kaputt (Syntaxfehler, Nullbyte, ungültiges UTF-8, nicht lesbar) / When die Parsebarkeits-Prüfung läuft / Then wird sie rot und nennt den Dateinamen, je Fehlerart ein Fall; auf dem echten Baum ist sie grün.
- [x] **AC-7:** Given die drei umgebauten Scanner-Dateien / When sie vorher und nachher im selben Zeitfenster seriell auf dem Mac gemessen werden / Then überschreitet kein Test dieser Dateien mehr das 30-s-Netz, ohne dass ein Timeout angehoben wurde.
- [x] **AC-8:** Given die beiden Cache-Dateien tragen je eine eigene `xdist_group` / When sie mit `-n 2 --dist loadgroup` laufen / Then laufen alle Tests jeder Datei in einem Worker und der Lauf ist grün.

## Dialog

### Runde 1
**Adversary:** Eigene Beweise (nicht die Entwickler-Nachweise); Befehle und Ausgaben in `docs/artifacts/rework-3279-testsuite-tempo/adversary-test-output.txt`.

1. Testlauf der vier Dateien seriell: 100 passed. Mit `-n 4 --dist loadgroup`: 100 passed in 24 s. Verschachtelter xdist-Lauf (`-n 2` im `-n 4`-Lauf) sauber; `PYTEST_XDIST*` wird im inneren Lauf entfernt. Zwei zufaellige Testreihenfolgen (82 Tests der drei Scanner-Dateien) gruen, kein Reihenfolgeeinfluss. Modul-Globals werden nur per `monkeypatch.setitem` umgeleitet und zurueckgestellt.
2. Verlustfreiheit (AC-1, eigener Beweis): Scanner der Basis 74afd3391 (aus der Historie ausgelesen) gegen die neuen auf dem echten Baum: direkt 1/1, indirekt 0/0, gestellte_uhr 10/10, Funde identisch; `KNOWN_VIOLATIONS`, `KNOWN_VIOLATIONS_INDIREKT` und beide `EXPIRY` gleich. Weil indirekt 0 gegen 0 ein leerer Vergleich ist, zusaetzlich mit entschaerften Regeln (Haertungs-Helfer aus, Wanduhr-Datum, Anfaelligkeit und Datenstruktur-Fluss immer wahr): indirekt 229/229, direkt 176/176 identisch. Dazu 10 gepflanzte Randfaelle (Modulimport mit Alias, Klammerimport, relativer Import, Fullwidth in Modul und Aufruf, BOM, CRLF, `Stage` ueber Attribut), je beide Scanner: alt und neu in allen Paaren identisch. Regeln der Scanner im Original gelesen: jede Fundbedingung verlangt den Bezeichner (`strftime` als Attribut, `Stage` als Name/Alias/Attribut plus Alarmpfad als Teilstring eines importierten Modulnamens, `make_trip` und `save_trip` als Aufruf, `get_trips_dir` als Aufruf); keiner kann ohne den Text im NFKC-Quelltext entstehen. Kein meldepflichtiger Fall wird ausgeschlossen.
3. Fehlerbehandlung: `quelltext_mit_bezeichnern` (tests/helpers/bezeichner_vorfilter.py:19) liest strikt UTF-8 und wirft; wallclock und gestellte_uhr fangen `(SyntaxError, UnicodeDecodeError)` wie vorher; trips_pfad wirft weiter (`test_kaputte_kandidatendatei_bleibt_rot`). Die Parsebarkeits-Pruefung `unparsbare_dateien` (:36) ist durch H9 bis H12 und H14 bis H16 bewacht.
4. Cache am Verbraucher: Mutationen W16 bis W19, U9, U10 (Aufrufer des Caches auf direkten Scan) fangen `test_echtbaum_pruefungen_nutzen_den_cache`; W20 nicht (F001).
5. Mutationsbilanz: 61 Verfaelschungen per String-Ersetzung mit externer Sicherung (Protokoll im Scratchpad `mut_log.txt`): 55 rot, 6 ueberlebt (H13, W14, U3 gleichwertig bzw. unschaedlich; W20, T5, V3 echte Luecken), dazu 2 Zusatzproben (MA ueberlebt, MD gruen wie gewollt, Kandidatenzaehlung unabhaengig). Hash-Stand aller fuenf Dateien nach dem Rueckspielen identisch zur Sicherung.
6. Zeitnetz (AC-7): `test_echter_testbaum_ohne_fehlalarm_der_zweiten_regel` 13,6 s bis 14,7 s, `test_jede_testdatei_ist_parsbar` 8,8 s bis 10,5 s, Rest unter 7 s. Bei 20 Rechenprozessen auf 10 Kernen (2fach ueberbucht, `-n 4`) rissen 5 Tests das 30-s-Netz (Kaskade, F004); in Laeufen 1 bis 3 kein Reissen.

**Implementierer:** (nicht anwesend; Antwort im Fix-Loop)

### Runde 2
**Adversary:** Nachgebohrt an den Stellen, die der Nutzer (CI) erreicht.
- Der teuerste Cache-Verbraucher ist `test_echter_testbaum_ohne_fehlalarm_der_zweiten_regel` (tests/tdd/test_fixture_wallclock_ratchet.py:1395). Ersetze ich dort `funde_echtbaum_indirekt()` durch den direkten Baumlauf (W20), bleibt alles gruen: die Zusicherung "je Regel nur einmal gescannt" ist dort ungeprueft, der Scan (ca. 9 s) liefe ein zweites Mal. F001.
- AC-8: der innere Lauf hat `-k scanner` (tests/tdd/test_bezeichner_vorfilter.py:98), prueft also nur Scanner-Faelle, nicht die Echtbaum-Tests, die der Cache bedient. Eine zusaetzliche `xdist_group("fremd")` an `test_known_violations_der_neuen_regel_ist_leer` (MA) bleibt gruen; die Pruefung `len({worker ...}) == 1` (:106) ist durch `>= 1` ersetzbar ohne Rot (V3), weil die Gruppen-Suffix-Pruefung daneben schon greift. F002.
- Spec-Abweichung: AC-8 sagt "alle Tests jeder Datei", der Nachweis deckt die Modul-Markierung (`pytestmark`, ueber `importlib` geprueft) plus die Scanner-Teilmenge. Konsistent mit der Spec-Begruendung (inneres Netz 28 s), aber nicht der Wortlaut.
- Heap-Last: Scan mit 0 / 3 Mio. / 8 Mio. lebenden Objekten im Prozess (Muster "Worker nach tausenden Tests"): indirekt 9,5 / 9,1 / 7,8 s, kein GC-Aufschlag. Entwarnung.
- Nachbar-Ratschen, die `tests/` scannen (user_id-Wachen, Pfad-Ratsche, Import-Konvention, i18n, PII, Egress u. a., 2168 Tests): gruen; `tests/tdd/test_xdist_echtbaum_ratsche.py` 21 passed.
- Bestehende Tests nicht abgeschwaecht: der Diff gegen die Basis zeigt nur das Ersetzen des Scans durch den Cache-Aufruf, neue Tests und die Fehlermeldung in trips_pfad (Schluessel jetzt relativ zu `tests/`, nur Anzeige). Keine Assertion gelockert, kein Timeout angehoben, kein Produktcode beruehrt.
- Ablauf-Hinweis: ein Hilfsskript von mir startete wegen eines Parsefehlers kurz einen Lauf ohne Dateinamen; nach Sekunden beendet, Arbeitsbaum unveraendert, keine Datenaenderung.

**Implementierer:** (nicht anwesend)

### Runde 3 (Nachpruefung nach Fix-Loop 1, Dateistand neu, frische Sicherung `orig2`)
**Adversary:** Geaendert: Kandidatenzaehlung als `_waypoint_kandidaten(tests_root)` (tests/tdd/test_fixture_wallclock_ratchet.py:1375) mit Aufruf am echten Baum (:1388), vierter Verbraucher im Cache-Test (:1569, Aufruf mit ersetzter Zaehlung :1584), neuer Gruppen-Test (tests/tdd/test_bezeichner_vorfilter.py:116), neuer Wurzel-Test (tests/test_trips_pfad_rueckbau.py:173). Helfer und gestellte_uhr-Datei byteidentisch zum Stand davor.
- F001 geschlossen: W20-Wiederholung (N1, direkter Baumlauf in `test_echter_testbaum_ohne_fehlalarm_der_zweiten_regel`) ist jetzt rot durch `test_echtbaum_pruefungen_nutzen_den_cache`. Auslagerung schwaecht nichts: `>= 20` wirkt weiter (N8 `>=3` Waypoint, N11 Liste gekappt, N12 Baum auf `unit` verengt: alle rot durch den echten Aufruf :1388). Die ersetzte Zaehlung im Cache-Test (Stand-in mit 20 Eintraegen) verdeckt nichts: N13 (Stand-in leer) ist rot, der Cache-Test sieht also die Floor-Pruefung. Offen bleibt, wie schon vor der Scheibe, dass das Entfernen der Floor-Zeile selbst (N9 `>= 0`) bzw. das Ersetzen der Zaehlung durch eine Konstante (N10) kein Test faengt; das ist eine Mutation der Pruefung selbst, die Zaehlung wird durch N8, N11, N12, W23 bewacht. LOW, siehe F006.
- F002 geschlossen: Gruppe nur an einem Echtbaum-Test geaendert (N3 wallclock `fremd`, N4 gestellte_uhr `fremd`, N5 gestellte_uhr `echtdaten`, K1 mit `name=`-Schluesselwort, K2 zusaetzliches Argument) alle rot durch den neuen Gruppen-Test; Einschraenkung des Unterlaufs auf `-k scanner` (G4) rot. V3 (`== 1` zu `>= 1`) ueberlebt weiter, ist aber jetzt durch den Gruppen-Test redundant bewacht (jede fremde Gruppe faellt dort auf); die Reste G1, G2, G3, G5, G7 sind Abschaltungen der Pruefung selbst im neuen Test (Einzelmutation ohne gleichzeitig fremde Gruppe nicht beobachtbar; mit fremder Gruppe sind sie die Faelle N3 bis N5, K1, K2, die greifen). Zeit des Subprozesses 2,4 s bis 2,5 s (Netz 28 s), kein Flackern in zwei `-n 4`-Laeufen.
- F003 geschlossen: Baumlauf auf `unit` (N6) oder auf die Repo-Wurzel (N7) ist rot durch `test_echtbaum_pruefung_durchsucht_den_ganzen_testbaum`.
- Zeit/Flackern: seriell 102 passed in 40,9 s; `-n 4 --dist loadgroup` zweimal 102 passed in 25,9 s und 25,3 s; teuerster Test 15,5 s bis 15,7 s (Faktor 1,9 zum Netz, F004 unveraendert). Zwei Subprozess-Tests: Wurzel/Worker 6,4 s bis 6,8 s, Gruppen 2,4 s bis 2,5 s, im verschachtelten Lauf sauber.
- Mutationsbilanz Runde 3: 22 neue Verfaelschungen (N1 bis N13, G1 bis G5, G7, V3, K1, K2): 13 rot (N1, N3 bis N8, N11 bis N13, G4, K1, K2), 9 ueberlebt (N2, N9, N10, G1, G2, G3, G5, G7, V3 sind Abschaltungen der jeweiligen Pruefung selbst bzw. Entfernen des zusaetzlichen Aufrufs ohne anderes Defektbild, siehe F006). Alles zurueckgespielt, Hashes gegen `orig2.sha` identisch, keine Hintergrundprozesse.

**Implementierer:** (nicht anwesend)

## Findings

Finding F001  [ERGEBNIS NACH FIX-LOOP 1: GESCHLOSSEN, N1 rot]
- ID: F001
- Severity: MEDIUM
- Category: edge_case
Code reference: tests/tdd/test_fixture_wallclock_ratchet.py:1395
- Description: `test_echter_testbaum_ohne_fehlalarm_der_zweiten_regel` ruft `funde_echtbaum_indirekt()`. Mutation W20 ersetzt das durch `scan_indirekte_wanduhr_fixtures(TESTS_ROOT)`; alle Tests bleiben gruen.
- Spec requirement: AC-5 (der echte Baum wird je Regel im Prozess nur einmal gescannt)
- Conflict: `test_echtbaum_pruefungen_nutzen_den_cache` (:1569) ruft nur drei der vier Verbraucher auf, nicht den vierten und teuersten. Ein Rueckfall dort verdoppelt ca. 9 s Scan unbemerkt und gefaehrdet das 30-s-Netz.
- Remediation: in `test_echtbaum_pruefungen_nutzen_den_cache` auch `test_echter_testbaum_ohne_fehlalarm_der_zweiten_regel()` aufrufen (die Kandidatenzaehlung kostet ca. 4 s) oder die Zahl der Baumlaeufe per Zaehler absichern.

Finding F002  [ERGEBNIS NACH FIX-LOOP 1: GESCHLOSSEN, N3 bis N5, K1, K2 rot]
- ID: F002
- Severity: MEDIUM
- Category: edge_case
Code reference: tests/tdd/test_bezeichner_vorfilter.py:98
- Description: Der AC-8-Test laeuft nur mit `-k scanner` und prueft die Worker-Einheitlichkeit (:106) so, dass `== 1` durch `>= 1` ersetzbar ist (V3 ueberlebt). Eine fremde `xdist_group` an einem einzelnen Echtbaum-Test der Cache-Datei (MA) bleibt gruen.
- Spec requirement: AC-8 (alle Tests jeder Datei laufen in einem Worker)
- Conflict: Die Zusicherung wird an Scanner-Faellen geprueft, die den Cache nicht nutzen, nicht an den Tests, fuer die die Gruppe da ist.
- Remediation: im Test zusaetzlich die Gruppe jedes gesammelten Items beider Dateien pruefen (`--collect-only` im Unterprozess oder `iter_markers` ueber die Items) und die Worker-Einheitlichkeit mit einer Gegenprobe absichern.

Finding F003  [ERGEBNIS NACH FIX-LOOP 1: GESCHLOSSEN, N6, N7 rot]
- ID: F003
- Severity: LOW
- Category: edge_case
Code reference: tests/test_trips_pfad_rueckbau.py:144
- Description: Mutation T5 (`aufrufer_von_get_trips_dir(_TESTS_DIR / "unit")`) bleibt gruen. Bestandsluecke (vor der Scheibe identisch).
- Spec requirement: AC-2 (Baumlauf ueber `tests/`)
- Conflict: keine Untergrenze fuer die Zahl der besuchten Dateien auf dem echten Baum.
- Remediation: optional Untergrenze (mehr als 1000 `.py`) oder gepflanzter Aufruf im echten Wurzelverzeichnis.

Finding F004
- ID: F004
- Severity: LOW
- Category: edge_case
Code reference: tests/tdd/test_fixture_wallclock_ratchet.py:1375
- Description: Dieser Test braucht bei mir 13,6 s bis 14,7 s (Entwickler: 7,7 s), davon ca. 9 s Cache-Fuellung. Reisst er unter Last das 30-s-Netz, fuellt `functools.cache` bei einer Ausnahme nichts, und die folgenden Verbraucher scannen jeweils selbst und reissen ebenfalls (Lauf 4: 5 Tests rot bei 2facher CPU-Ueberbuchung).
- Spec requirement: AC-7 (kein Test reisst das 30-s-Netz)
- Conflict: Abstand zum Netz nur etwa Faktor 2 bei der schwersten Pruefung; ohne Ueberbuchung kein Reissen.
- Remediation: Kandidatenzaehlung und Cache-Fuellung in getrennte Tests oder Modul-Fixture; keinen Timeout anheben.

Finding F005
- ID: F005
- Severity: LOW
- Category: anti_pattern
Code reference: tests/helpers/bezeichner_vorfilter.py:44
- Description: Gleichwertige oder unschaedliche Ueberlebende. H13 (`ValueError` durch `UnicodeDecodeError`) ist auf Python 3.12 (CI) gleichwertig, weil ein Nullbyte dort `SyntaxError` ist; auf 3.10/3.11 (laut `requires-python` zulaessig) faengt der Fall `nullbyte`. W14 (kein NFKC im Waypoint-Vorab-Filter, tests/tdd/test_fixture_wallclock_ratchet.py:1356) ist auf dem echten Baum gleichwertig und kann nur die Untergrenze der Zaehlung beeinflussen, nie einen Fund. U3 (`"save_tri"`) ist ein Teilstring und damit gleichwertig.
- Spec requirement: Spec "Implementation Details" (Filter wie Scanner, NFKC)
- Conflict: keiner; Beurteilung H13 gleichwertig auf 3.12, W14 unschaedlich, U3 gleichwertig.
- Remediation: keine.

Finding F006
- ID: F006
- Severity: LOW
- Category: anti_pattern
Code reference: tests/tdd/test_fixture_wallclock_ratchet.py:1388
- Description: Ersetzt man `_waypoint_kandidaten(TESTS_ROOT)` durch eine Konstante mit 20 Eintraegen (N10) oder die Floor-Zeile `>= 20` durch `>= 0` (N9), bleibt alles gruen. Die Zaehlung selbst ist durch N8, N11, N12 und W23 bewacht; die Luecke bestand vor der Scheibe ebenso.
- Spec requirement: Test Plan "Kandidatenzaehlung (>= 20) bleibt wirksam"
- Conflict: Das Entfernen der Floor-Pruefung faengt kein Test.
- Remediation: optional, kein Blocker.

## Bestaetigungen

Confirmation: Input
Code reference: tests/tdd/test_fixture_wallclock_ratchet.py:545
- Evidence: Scanner laufen gegen echten Baum und `tmp_path` (Laeufe 1 bis 3 gruen).
- Status: CONFIRMED

Confirmation: Output
Code reference: tests/tdd/test_trip_fixtures_laufen_unter_gestellter_uhr.py:84
- Evidence: Funde 1/0/10 identisch zur Basis, auch bei entschaerften Regeln (176/229) identisch; kein Netzreissen ohne Ueberbuchung (Einschraenkung F004).
- Status: CONFIRMED

Confirmation: Side effects
Code reference: tests/test_trips_pfad_rueckbau.py:125
- Evidence: nur die fuenf Dateien geaendert; `KNOWN_VIOLATIONS`, `KNOWN_VIOLATIONS_INDIREKT`, `EXPIRY` per Skript gleich zur Basis; `pyproject.toml` unberuehrt (timeout = 30).
- Status: CONFIRMED

Confirmation: AC-1
Code reference: tests/helpers/bezeichner_vorfilter.py:19
- Evidence: eigener Vergleich alt/neu (echter Baum, entschaerfte Regeln, 10 gepflanzte Faelle) identisch.
- Status: CONFIRMED

Confirmation: AC-2
Code reference: tests/test_trips_pfad_rueckbau.py:181
- Evidence: gepflanzte Faelle je Scanner inkl. Alias-Import; Mutationen W1 bis W5, U1, U2, T1 bis T4 rot.
- Status: CONFIRMED

Confirmation: AC-3
Code reference: tests/tdd/test_fixture_wallclock_ratchet.py:1496
- Evidence: Mutationen H1, H2, H6 (NFKC weg, NFC, Normtext) rot, je Scanner mit eigenem Fullwidth-Fall.
- Status: CONFIRMED

Confirmation: AC-4
Code reference: tests/tdd/test_trip_fixtures_laufen_unter_gestellter_uhr.py:84
- Evidence: verfaelschter Filter (Name, UND/ODER, NFKC, immer None, Alarmpfade) und Cache (leer, auf tmp_path, ohne Cache) je Ratsche rot; Ausnahmen F001, F005.
- Status: CONFIRMED (mit F001)

Confirmation: AC-5
Code reference: tests/tdd/test_fixture_wallclock_ratchet.py:1545
- Evidence: Zaehler, frische Liste, tmp_path ungecacht (W6 bis W11, W21, U4 bis U6, U11 rot); Luecke beim vierten Verbraucher.
- Status: CONFIRMED (F001 geschlossen)

Confirmation: AC-6
Code reference: tests/tdd/test_bezeichner_vorfilter.py:83
- Evidence: vier Fehlerarten je rot mit Dateiname (H9 bis H16), echter Baum gruen (8,8 s).
- Status: CONFIRMED

Confirmation: AC-7
Code reference: tests/tdd/test_fixture_wallclock_ratchet.py:1375
- Evidence: seriell und `-n 4` je Test unter 15 s, ohne Timeout-Anhebung; bei 2facher Ueberbuchung Reissen (F004).
- Status: CONFIRMED (mit F004)

Confirmation: AC-8
Code reference: tests/tdd/test_bezeichner_vorfilter.py:88
- Evidence: innerer `-n 2 --dist loadgroup`-Lauf gruen; W12, W13, U7, U8, V1, V2 rot.
- Status: CONFIRMED (F002 geschlossen)

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

Vorbedingungen: Basis-Commit 74afd3391 (Scanner im Original aus der Historie), RED-Commit 57b3dc04f, Python 3.12.15 (CI ebenfalls 3.12), 10 Kerne Mac; Sicherungskopien und Hashes im Scratchpad (`orig/`, `orig.sha`).

## Verdict

VERDICT: VERIFIED

F001, F002, F003 sind unabhaengig als geschlossen belegt (je Verfaelschung rot, siehe Runde 3). Offen nur LOW (F004 Zeitabstand Faktor 1,9, F005 gleichwertige Mutanten, F006 Floor-Pruefung nicht gegen Selbstabschaltung bewacht), alle ohne Blockade. Tests: 102 passed, 0 failed (seriell und `-n 4 --dist loadgroup`, zweimal). Der Filter ist verlustfrei, `KNOWN_VIOLATIONS` und `EXPIRY` unveraendert. Mutationsbilanz gesamt: 83 Verfaelschungen, 68 rot, 15 ueberlebt (gleichwertig oder Selbstabschaltung einer Pruefung: H13, W14, U3, N2, N9, N10, G1, G2, G3, G5, G7, V3; Reste T5, W20 und MA sind durch N6, N1, N3 geschlossen).

## Geprüfte Dateien

- sha256:8bb3ba8d4c78faf53eea21012b4b88926e3b9195be5d8c9ad753139fc4b86cdd  tests/helpers/bezeichner_vorfilter.py
- sha256:18bcb17b994cd0981181fd285a179353e22d33eb4ab9b87f5cba847d573550ce  tests/tdd/test_bezeichner_vorfilter.py
- sha256:0a2ebe54ec115601ffb3b5c7ec18fb73b388bae90fbb4b98bbd6f621daae41ac  tests/tdd/test_fixture_wallclock_ratchet.py
- sha256:2c76ca9f310a402dc3ca0c1777b5daf9f7315539f5f72c3cffcc7d2ccd1164f0  tests/tdd/test_trip_fixtures_laufen_unter_gestellter_uhr.py
- sha256:c7280a4e3e2664f74a31447805f7746533c4e9eb39d9382687afdaca4201d126  tests/test_trips_pfad_rueckbau.py

## Prüfbasis

- base: 74afd33915a6660d88bd22816a381259b395fc8e
- blob:feace31e689391780dddd2b97b4477f7fa8dc157  tests/helpers/bezeichner_vorfilter.py
- blob:aee3132205d7a7a22625358ce7ac201e23064f74  tests/tdd/test_bezeichner_vorfilter.py
- blob:663fd0672b84bba23f925e5d4e30a7430766c145  tests/tdd/test_fixture_wallclock_ratchet.py
- blob:f4fbdcf584776e4f4bc3e69d134b146bd2ff9651  tests/tdd/test_trip_fixtures_laufen_unter_gestellter_uhr.py
- blob:0f18a36a864ec2fe9ba0c3eb84e52aa07d4acd15  tests/test_trips_pfad_rueckbau.py
