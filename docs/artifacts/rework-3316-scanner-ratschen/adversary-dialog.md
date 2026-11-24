# Adversary Dialog — rework-3316-scanner-ratschen
Spec: docs/specs/modules/rework_3316_scanner_ratschen_tempo_s2.md
Datum: 2026-11-24 16:59

## Checkliste
- [x] **Input (PROVEN, 185 passed lokal):** Lauf der vier Testdateien (lokal oder CI) gegen den echten `tests/`-Baum bzw. `tmp_path`.
- [x] **Output (PROVEN lokal; CI-Reserve offen, siehe AC-10):** dieselben Funde wie vorher, kürzere Laufzeit, mehr Reserve zum 30-s-Netz in CI.
- [x] **Side effects (PROVEN: kein Produktcode, kein timeout( in den 4 Dateien, ALTLASTEN unveraendert):** keine; kein Produktcode, kein Timeout angehoben, `KNOWN_VIOLATIONS` und Altlasten unverändert.
- [x] **AC-1 (PROVEN):** Given die fünf Behauptungs-Alternativen von Regel D / When Filter und Muster gebildet werden / Then stammen beide aus derselben Liste, jedes Filterwort ist nicht leer und ohne Leerzeichen, und das Muster erkennt genau dieselben Wortlaute wie vor dem Umbau.
- [x] **AC-2 (PROVEN):** Given gepflanzte D-Verstöße in `tmp_path` (jede der 5 Alternativen einzeln inkl. `oe`/`ö`, `ae`/`ä`, beide „unverändert"-Formen, Phrase über Zeilenbruch, Variante mit `ı`, Kommentar über der Anweisung und Zeilenkommentar) / When `scan_tree` mit `rules=("D",)` läuft / Then wird jeder Verstoß gefunden.
- [x] **AC-3 (PROVEN):** Given eine gepflanzte Datei ohne Filterwort im Kommentar, aber mit Verstoß gegen Regel A / When `scan_tree` mit A+B+C+D, A+B+C, A+D und mit `("D",)` läuft / Then wird der Verstoß bei jeder Regelmenge mit A gefunden, und nur bei `("D",)` steht die Datei in `besucht`, aber nicht in `geparst`.
- [x] **AC-4 (PROVEN):** Given der echte Testbaum / When der Baumlauf mit Regel D läuft / Then ist `besucht` gleich der `rglob`-Sollmenge, `geparst` nicht leer, echte Teilmenge von `besucht` und enthält eine bekannte echte Datei.
- [x] **AC-5 (PROVEN):** Given die Backend-Läufe der Gewitterskala / When die Duldungsfunktion aus einem Rohlauf die Fixtures „ohne Basislinie" und „ohne Whitelist" ableitet / Then sind sie gleich dem Ergebnis der bisherigen Einzelläufe, der AC-12-Lauf bleibt ein echter `scan_tree`-Lauf, und es laufen 3 statt 4 Scans.
- [x] **AC-6 (PROVEN):** Given alle drei Cache-Dateien tragen je eine eigene `xdist_group` / When sie mit `-n 2 --dist loadgroup` laufen / Then laufen alle Tests jeder Datei in einem Worker, der Lauf ist grün und führt keinen Echtbaum-Scan aus.
- [x] **AC-7 (PROVEN):** Given `_module_constants` mit einmal gesammelten Zuweisungen / When ein Tausch `A, B = B, A`, eine Kette bis zum Fixpunkt und der echte Baum aufgelöst werden / Then entstehen dieselben Konstanten in derselben Reihenfolge wie vorher, und eine umgekehrte Reihenfolge oder nur eine Runde macht mindestens einen Test rot.
- [x] **AC-8 (PROVEN):** Given gepflanzte Verstöße in `tmp_path` (Name-Aufruf, Attribut-Aufruf, Fullwidth-Name) / When `_sammle_verstoesse(tmp_path)` mit Filter läuft / Then werden alle gefunden, der Pfad der Funde wird auch für `tmp_path` ausgegeben, `_SELBST` bleibt ausgenommen, und eine Datei mit `SyntaxError` unter den gefilterten bleibt rot.
- [x] **AC-9 (PROVEN):** Given künstlich verfälschte Filter oder Sammlung (falsches Filterwort, verschärfte `#`-Bedingung, Filter immer falsch, Wurzel ignoriert, umgekehrte Reihenfolge, nur eine Runde, Duldungsfunktion ohne Whitelist, ohne Altlasten, duldet alles) / When die Tests der jeweiligen Ratsche laufen / Then ist je Verfälschung mindestens ein Test rot.
- [x] **AC-10 (nur lokaler Teil PROVEN; CI-Teil siehe ## Offene Punkte):** lokal belegt: kein `timeout(180)` mehr in den vier Dateien (grep leer), gemessen 17,5 s seriell für alle vier (längster Einzeltest 4,5 s). Der grüne CI-Job `test` ist hier NICHT Teil des Häkchens.

## Dialog

### Runde 1
**Adversary:** Eigene Beweise (nicht aus den Artefakten uebernommen):
- Testlauf der 4 Dateien: 185 passed, 17,5 s (docs/artifacts/rework-3316-scanner-ratschen/adversary-test-output.txt).
- Differential-Fuzz gegen die ECHTE `_kommentarblock_ueber`: 300.000 Zufallsquellen aus Fragmenten (Trenner \r, \r\n, \x0b, \x0c, \x1c-\x1e, \x85, U+2028/2029; Raute im String, Tabs, Doppelraute, `1#:1`, `wortw#oert`, Unicode-Faelle ı/ſ/K, Grossschreibung), je Zeilennummer: 23.352 Faelle, in denen das Muster auf dem Kommentarblock trifft; in 0 Faellen sagt `_kann_paritaet_behaupten` False. Der Filter ist nie strenger. Begruendung im Code: `zeilen` kommt aus `splitlines()` (feiner als `split("\n")`), gelesen wird nur Text ab der ersten Raute einer Teilzeile; Filterwoerter enthalten keinen Leerraum, `#`->Leerzeichen und `\s+`-Normalisierung koennen kein Filterwort erzeugen oder zerstoeren.
- Regel D kann nur ueber `_kommentarblock_ueber` feuern (thunder:697), nicht ueber Docstring/Marker/andere Texte; Docstring-Text ohne Raute wird nie gelesen, Raute im String ist nur zu grosszuegig (kein Verlust).
- Regelmenge: `set(rules) == {"D"}` (thunder:~829): Liste/Tupel/Duplikate ("D","D") filtern, ("A","D"), (), ("D","X") filtern nicht. AC-3-Test deckt ABCD/ABC/AD/D.
- `_ist_geduldet` (thunder:792) ist logisch dieselbe Duldung wie der alte Inline-Code (any Whitelist, any Altlast); die Duldungs-Unit-Tests rotten bei je einer Verfaelschung (T10-T13). 3 Backend-Scans: backend_rohlauf (1086), AC-12 (1109), Marker (1287).
- Fixtures: `backend_rohlauf` ist modulweit, die zwei Ableitungen sind neue Listen (List-Comprehension), kein `.sort/.append/.remove` auf Fixturewerte (grep).
- user_id-Filter: Echtbaum filtriert 8 = ungefiltert 8, gleiche Liste (selbst gerechnet mit `_MARKER` ausgeschaltet). Filter sucht NFKC-normalisiert Zielnamen; der Sammler matcht `Name.id`/`Attribute.attr` (Python normalisiert Bezeichner ebenfalls NFKC), Fullwidth getestet (und per Helper-Mutation H1 als gueltig bewiesen). Import-Alias/Dekorator: der Sammler findet nur Call-Knoten mit Name/Attribut auf Zielnamen, ein Alias `from x import f as g` wird auch im alten Sammler nicht gefunden (kein Regress); Backslash-Zeilenfortsetzung und Unicode-Escapes koennen einen Bezeichner nicht zerlegen.
- Kaputte gefilterte Datei: `test_kaputte_kandidaten_bleiben_rot` (SyntaxError, UnicodeDecodeError rot); kaputte Datei ohne Zielname wird uebersprungen und von `test_jede_testdatei_ist_parsbar` gedeckt (Spec).
- `_module_constants`: Zaehltest (1 Durchlauf), Tausch/Fixpunkt/letzte Bindung/Ebenenweise/AnnAssign+Kette; Mutationen R1-R6 alle rot.
**Implementierer:** (nicht beteiligt, Kontextisolation)

### Runde 2
**Adversary:** Gezielte Randfaelle und Mutations-Gegenprobe (Sicherungskopie in scratchpad/bak, Verfaelschung per String-Ersetzung, Wiederherstellung per Byte-Schreiben, kein git checkout/stash/reset/restore).
Mutationen (39 eigene + 5 + 1 = 45, alle ausser zwei gefangen):
- thunder: T1 Filter ohne 5. Alternative ROT; T2 letzte statt erste Raute ROT; T3 Filter immer an ROT; T4 nie an ROT; T5 `"D" in rules` ROT; T6 scan_tree duldet nichts ROT (AC-12); T7 scan_tree ohne Altlasten ROT (`test_scan_tree_wendet_die_altlasten_basislinie_selbst_an`); T8 duldet alles ROT; T9 geparst vor Filter ROT; T10-T13 je Duldungsbedingung ROT; T14 Rohlauf mit Whitelist ROT; T15 Baumlauf A+D ROT; T16 xdist_group "echtdaten" ROT; T17 Filter ohne IGNORECASE ROT; T18 any->all ROT; T19 Filter ab Zeilenanfang ROT; T21 besucht nach Filter ROT; T22/T26 scan_tree ueberspringt Dateien still ROT; T23 `_ist_geduldet` immer True ROT; T24 Raute irgendwo ROT; T25 nur erste Zeile ROT.
- repo_path: R1 umgekehrt, R2 eine Runde, R3 AnnAssign weg, R4 nur erstes Ziel, R5 zwei Runden, R6 nur Modulebene: alle ROT.
- user_id: U1 Wurzel ignoriert, U2 Filter aus, U3/U4 Filter nur Name/nur Attribut, U5 _SELBST nicht ausgenommen, U6 SyntaxError verschluckt, U7 Pfad immer relativ, U8 Filter lehnt alles ab, U10 UnicodeDecodeError verschluckt: alle ROT. Helper H1 ohne NFKC ROT (fullwidth).
- Gruppen: V1 thunder aus CACHE_DATEIEN ROT, V2 innerer Lauf inkl. Echtbaum ROT.
- Ueberlebt: T20 (Assertion `besucht == rglob` aus dem TEST geloescht) und U9 (Assertion "Register nicht leer" geloescht). Beides Mutationen der Zusicherung selbst, keine Code-Verfaelschung: die ersetzende Code-Verfaelschung (T22/T26 Dateien still ueberspringen; leeres Register => gepflanzter Fall findet nichts) wird von anderen Tests gefangen. Kein Finding (aequivalent bzw. redundante Absicherung).
- Wiederherstellung: SHA-256 der vier Dateien vor und nach allen Mutationen identisch (`diff` leer); Helper tests/helpers/bezeichner_vorfilter.py ebenfalls identisch zur Sicherung.
AC-5 (Pkt 4): Bei leerem ALTLASTEN ist "Altlasten ignoriert macht AC-12 rot" tatsaechlich unmoeglich. Absicht belegt: T7 (scan_tree reicht `()` statt `altlasten` an die Duldung) macht `test_scan_tree_wendet_die_altlasten_basislinie_selbst_an` rot; T6/T8 machen AC-12 bzw. die Leerlauf-Tests rot. Die Ersatzzusicherung deckt die Spec-Absicht (beweist, dass scan_tree die Funktion selbst benutzt).
AC-10: Lokal belegt: in den vier Dateien kein `timeout(` (grep leer); gemessen serielle Gesamtlaufzeit 17,5 s fuer alle vier (laengster Einzeltest repo_path AC-3 4,5 s, thunder Setup 2,0 s). AUSSTEHEND und NICHT bewiesen: gruener CI-Job `test` nach dem Push (30-s-Netz); bis dahin offen. Der PR-Merge verlangt ihn ohnehin.
**Implementierer:** (nicht beteiligt)

## Offene Punkte

- **AC-10, CI-Teil: NICHT bewiesen.** Der grüne CI-Job `test` des PR gegen das globale 30-s-Netz (bzw. `timeout(60)` mit Verweis, falls der Lauf das Netz reißt) steht aus. Nachweis erst nach dem Push möglich; grüner Serverlauf ist Bedingung für den Merge/die Übernahme.
- PO-Entscheidung 2026-11-24 (getippt, wörtlich): „ok, Serverlauf nachreichen" (Antwort auf: Serverlauf bleibt als benannter offener Punkt im Protokoll, Übernahme nur mit grünem Serverlauf).

## Findings
Keine HIGH/CRITICAL/MEDIUM-Findings. Beobachtung (LOW, kein Block): `quelltext_mit_bezeichnern` mit leerer `eines_aus` schaltet den Filter still ab (fail-open, nie blind); der Test `test_gepflanzter_verstoss...` sichert das Register zusaetzlich als nicht leer ab.
(Schema-Hinweis: Confirmations unten)

## Confirmations

Confirmation:
  AC: AC-1
  Code reference: tests/tdd/test_thunder_scale_local_copy_guard.py:665
  Evidence: Filter und Muster aus `_PARITAETS_ALTERNATIVEN` (Z. 250); Fuzz 0 Falschnegative; Mutationen T1/T2/T17-T19/T24/T25 rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-2/AC-3/AC-4
  Code reference: tests/tdd/test_thunder_scale_local_copy_guard.py:851
  Evidence: Gepflanzte Verstöße, 4 Regelmengen, besucht == rglob; T3/T4/T5/T9/T21/T26 rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: tests/tdd/test_thunder_scale_local_copy_guard.py:792
  Evidence: `_ist_geduldet` von scan_tree benutzt, 3 Backend-Scans (Rohlauf Z. 1082); T6-T14, T23 rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-6
  Code reference: tests/tdd/test_bezeichner_vorfilter.py:117
  Evidence: len(gruppen) == 3, CACHE_DATEIEN Z. 25; V1, V2, T16 rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-7
  Code reference: tests/tdd/test_repo_path_hardcoding_ratchet.py:558
  Evidence: Zuweisungen einmal gesammelt (Z. 547); R1-R6 rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-8
  Code reference: tests/test_test_suite_passes_user_id_explicitly.py:209
  Evidence: Filter per Bezeichner, Wurzel-Parameter (Z. 200); U1-U8, U10, H1 rot; Echtbaum 8 = 8.
  Status: CONFIRMED

Confirmation:
  AC: AC-9
  Code reference: tests/tdd/test_thunder_scale_local_copy_guard.py:851
  Evidence: Jede der genannten Verfälschungen macht mindestens einen Test rot (Runde 2).
  Status: CONFIRMED

Confirmation:
  AC: AC-10 (nur lokaler Teil)
  Code reference: tests/tdd/test_thunder_scale_local_copy_guard.py:95
  Evidence: Kein `timeout(` in den vier Dateien (grep), seriell 17,5 s gesamt. CI-Teil (grüner Job `test` nach Push) NICHT bewiesen, siehe Verdict.
  Status: OPEN

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Verdict

**AMBIGUOUS**

Begründung: Alle Punkte außer AC-10 sind bewiesen (185 passed, 45 Mutationen, 43 rot, die 2 überlebenden sind Löschungen der Zusicherung selbst und kein Finding; kein Finding über LOW). AC-10 verlangt einen grünen CI-Job `test` nach dem Push. Das ist vor dem Commit prinzipiell nicht beweisbar. Lokal belegt: kein `timeout(180)` mehr, 17,5 s für alle vier Dateien. Der CI-Teil bleibt offen und ist nicht abgehakt. Das Gate zählt nur bewiesene Punkte, daher AMBIGUOUS statt VERIFIED; der PR-Merge verlangt den grünen Check `test` unabhängig davon.
Tests: 185 passed, 0 failed. Regressions: keine.

## Geprüfte Dateien

- sha256:f37035dc00fb715f33a9d7b7463edcacb39d520e5304869764addb7aae927ef5  tests/tdd/test_bezeichner_vorfilter.py
- sha256:0fcc87d7c855ea21bf0c18005dff50f5aa5a459845125873f32182999fb89004  tests/tdd/test_repo_path_hardcoding_ratchet.py
- sha256:ee4fbbb878d327062a419afa8f4af2dff08830e6f81230d714c73bc47510f3d7  tests/tdd/test_thunder_scale_local_copy_guard.py
- sha256:9cb95e99385a4f24c95f4b9397a45142980909ccb06ceead345788e7249b8377  tests/test_test_suite_passes_user_id_explicitly.py

## Prüfbasis

- base: 6bd47a58c120dd0450b76378699b2a50ccc75748
- blob:c83c135f88c0a1f5fe2d7266ed6004a81553d6da  tests/tdd/test_bezeichner_vorfilter.py
- blob:c71df6fe702ba18bef723a08f909ca0aae23631e  tests/tdd/test_repo_path_hardcoding_ratchet.py
- blob:8597fc41b9f8044efccf1e73bb9ca2a155151d26  tests/tdd/test_thunder_scale_local_copy_guard.py
- blob:9f540d6062552bc4c40b7798ae646e885b17c583  tests/test_test_suite_passes_user_id_explicitly.py

## Geprüfte Dateien

- sha256:f37035dc00fb715f33a9d7b7463edcacb39d520e5304869764addb7aae927ef5  tests/tdd/test_bezeichner_vorfilter.py
- sha256:0fcc87d7c855ea21bf0c18005dff50f5aa5a459845125873f32182999fb89004  tests/tdd/test_repo_path_hardcoding_ratchet.py
- sha256:ee4fbbb878d327062a419afa8f4af2dff08830e6f81230d714c73bc47510f3d7  tests/tdd/test_thunder_scale_local_copy_guard.py
- sha256:9cb95e99385a4f24c95f4b9397a45142980909ccb06ceead345788e7249b8377  tests/test_test_suite_passes_user_id_explicitly.py

## Prüfbasis

- base: 6bd47a58c120dd0450b76378699b2a50ccc75748
- blob:c83c135f88c0a1f5fe2d7266ed6004a81553d6da  tests/tdd/test_bezeichner_vorfilter.py
- blob:c71df6fe702ba18bef723a08f909ca0aae23631e  tests/tdd/test_repo_path_hardcoding_ratchet.py
- blob:8597fc41b9f8044efccf1e73bb9ca2a155151d26  tests/tdd/test_thunder_scale_local_copy_guard.py
- blob:9f540d6062552bc4c40b7798ae646e885b17c583  tests/test_test_suite_passes_user_id_explicitly.py
