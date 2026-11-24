---
entity_id: rework_3316_scanner_ratschen_tempo_s2
type: refactor
created: 2026-11-24
updated: 2026-11-24
status: draft
version: "1.0"
workflow: rework-3316-scanner-ratschen
tags: [testsuite, ratschen, performance, epic-1196]
---

# Scanner-Ratschen beschleunigen, Scheibe 2 (Gewitterskala, Pfad-Wächter, user_id)

## Approval

- [ ] Approved

## Purpose

Drei weitere Wächter-Tests lesen und parsen den ganzen `tests/`-Baum und liegen in CI nahe am globalen 30-s-Netz (main-Lauf 45202617843 riss es im Setup von `tests_baum_scan`). Diese Scheibe lässt sie weniger parsen und weniger doppelt rechnen, ohne eine Zusicherung zu schwächen. Issue #3316 (Teil von Epic #1196), Scheibe 2 von 3, Nachfolger von #3279.

## Source

- **File:** `tests/tdd/test_thunder_scale_local_copy_guard.py`, `tests/tdd/test_repo_path_hardcoding_ratchet.py`, `tests/test_test_suite_passes_user_id_explicitly.py`, `tests/tdd/test_bezeichner_vorfilter.py`
- **Identifier:** `scan_tree`, `_regel_d`, `_PARITAETS_BEHAUPTUNG`, `_module_constants`, `_sammle_verstoesse`, `test_cache_dateien_laufen_je_in_einem_worker`

> **Schicht-Hinweis:** Reine Testinfrastruktur (`tests/`, Doku-Artefakte). Kein Produktcode in Frontend, Go-API oder Python-Core, keine Nutzerdaten, Mandantentrennung und Kanäle sind nicht berührt (Querschnitts-Prüfpunkte entfallen). Keine neue Abhängigkeit (nur stdlib `ast`, `re`, `functools` und der Helfer aus Scheibe 1).

## Estimated Scope

- **LoC:** ca. +180..230 / -60, zusammen 240..290; die Grenze von 250 (Summe) kann also reißen. Regel: Nach dem thunder-Commit wird gezählt; passen repo_path und user_id nicht mehr hinein, werden sie als eigene Scheibe (neues Issue) abgetrennt, zuerst user_id
- **Files:** 4 (plus Spec und Artefakte)
- **Effort:** medium (Risiko MEDIUM: ein zu strenger Filter macht einen Wächter still blind; daher je Ratsche gepflanzter Verstoß und Mutations-Gegenprobe)

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `tests/tdd/test_thunder_scale_local_copy_guard.py` | MODIFY | `#`-Filter für Regel D aus einer Datenstruktur, Set `geparst`, Duldungsfunktion, 3 statt 4 Backend-Läufe, `xdist_group`, `timeout(180)` entfällt |
| `tests/tdd/test_repo_path_hardcoding_ratchet.py` | MODIFY | nur `_module_constants` (ab Z. 538): Zuweisungen einmal sammeln |
| `tests/test_test_suite_passes_user_id_explicitly.py` | MODIFY | `_sammle_verstoesse(wurzel)`, Bezeichner-Filter, gepflanzte Verstöße |
| `tests/tdd/test_bezeichner_vorfilter.py` | MODIFY | Gruppen-Nachweis von zwei auf drei Dateien erweitern |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `tests/helpers/bezeichner_vorfilter.py` | bestehend (#3279) | `quelltext_mit_bezeichnern(datei, alle, eines_aus)` für user_id; `unparsbare_dateien` deckt nicht geparste Dateien |
| `ast`, `re`, `functools` | stdlib | Parsen, Kommentar-Filter, Konstanten-Sammlung |
| `pytest-xdist` (`--dist loadgroup`) | bestehend (#3209) | eigene Gruppe für thunder, damit Cache und Setup je Worker einmal laufen |
| `pytest-timeout` | bestehend | globaler `timeout = 30` bleibt Netz; kein Timeout wird angehoben |
| #3317 (Scheibe 3), #1199 (EXPIRY), #3279 (Scheibe 1) | Nachbar-Issues | Out of Scope bzw. Vorgänger |

## Implementation Details

**Messbasis (Mac, seriell, gleiches Zeitfenster):** thunder 12,8 s auf 5,9 s (Baum-Setup 6,97 auf 1,71 s, Backend-Läufe 5,8 auf ca. 4,2 s), repo_path AC-3 5,4 auf 4,2 s, user_id AC-10 3,2 auf 1,8 s; Summe ca. 21,3 auf ca. 11,9 s (aus Einzelwerten gerechnet). Der Mac ist derzeit 4-10-mal schneller als in Issue und Scheibe 1 gemeldet (Ursache ungeklärt); CI ist mehr als 4-mal langsamer als der Mac. Hauptnutzen ist daher die Reserve zum 30-s-Netz in CI.

**1. thunder Regel D, Filter.** Der Testbaum-Lauf nutzt nur noch `rules=("D",)`. Der Filter greift in `scan_tree` NUR, wenn die Regelmenge genau `{"D"}` ist; jede andere Regelmenge (AC-12-Lauf, AC-19 mit A+B+C+D) bleibt ungefiltert. Bedingung: Der Rohtext (kein NFKC, kein casefold) enthält hinter einem `#` derselben Zeile ein Wort der gemeinsamen Wortliste, `re.IGNORECASE`. Gesucht wird zeilenweise ab dem ersten `#` (nicht quadratisch bei vielen `#`). Notwendig, weil `_kommentarblock_ueber` nur Text hinter `#` derselben Quellzeile liest.

*Ausdrückliche Ausnahme zur Regel aus Scheibe 1 („nur Bezeichner als Filter"):* Hier ist das Filterwort Kommentartext. Kommentare kennen weder Escapes noch Verkettung, ein Wort steht dort immer zusammenhängend im Quelltext; die Zerlegungsgefahr, die String-Inhalte als Filter verbietet, besteht nicht. Gefiltert wird nie auf die ganze Phrase (sie darf über einen Zeilenbruch laufen), nur auf einzelne Wörter.

*Drift-Schutz:* Filterwörter und `_PARITAETS_BEHAUPTUNG` entstehen aus EINER Datenstruktur (je Alternative ein Paar `(filterwort, rest)`; Muster = `filterwort + rest`, Filter = nur `filterwort`, beides Regex-Stücke). So ist der Filter je Alternative per Konstruktion eine notwendige Bedingung; eine neue Alternative ohne Filterwort ist nicht formulierbar. Das Filterwort ist nie leer und enthält kein Leerzeichen (Zeilenbruch!). `_PARITAETS_BEHAUPTUNG` bleibt inhaltlich gleich (5 Alternativen, `1:1`, `wortwört`/`wortwoert`, `identische`, `eingefroren`, `unverändert`/`unveraendert`).

**2. thunder, Zusicherung statt „Regel A > 0".** `besucht` zählt weiter VOR dem Filter, ein neues Set `geparst` danach. Ersatz für die Positivkontrolle: `besucht` gleich der `rglob`-Sollmenge (Mengenvergleich), `geparst` nicht leer und enthält eine bekannte echte Datei. Der echte Baum hat für Regel D null Kandidaten (Behauptung plus mindestens 2 Token: 0), Fundgleichheit gefiltert/ungefiltert beweist dort nichts. Den Beweis liefern gepflanzte D-Verstöße in `tmp_path` über `scan_tree(rules=("D",))`: jede Alternative einzeln (inkl. `oe`/`ö`, `ae`/`ä`, beide „unverändert"-Formen), Phrase über Zeilenbruch, Variante mit `ı` (U+0131), Kommentar über der Anweisung UND Zeilenkommentar.

**3. thunder Backend: 3 statt 4 Läufe.** Die Duldung (Whitelist plus Altlasten) wird als eigene Funktion aus `scan_tree` herausgelöst, `scan_tree` benutzt sie selbst; der Test baut sie nie nach. Der AC-12-Lauf bleibt ein echter `scan_tree`-Lauf mit Standardwerten (keine Schwächung). Die beiden Fixtures „ohne Basislinie" und „ohne Whitelist" werden aus EINEM Rohlauf per dieser Funktion abgeleitet; der Marker-Lauf (anderer Marker) bleibt eigen. `_fund` liest nur `spec.marker`; `baseline` und `canonical_symbols` wirken nur in `scan_tree`. Ergebnisgleichheit zu vorher wird einmalig im Artefakt belegt.

**4. xdist_group und Gruppen-Nachweis.** thunder bekommt `pytestmark = pytest.mark.xdist_group("gewitterskala")` (kein `@`, nicht `echtdaten`). `test_cache_dateien_laufen_je_in_einem_worker` (`tests/tdd/test_bezeichner_vorfilter.py`) prüft heute `len(gruppen) == 2` hart, filtert mit `-k scanner` und setzt im zweiten Test `known_violations` im Testnamen voraus. Erweiterung auf drei Dateien mit je Datei passenden Auswahlkriterien (innerer Lauf: bei thunder Tests ohne Baumlauf, z. B. `ac18`; Echtbaum-Nachweis im zweiten Test: bei thunder der Test `..._echten_tests_baum_...`), ohne den Nachweis abzuschwächen (weiterhin: alle Tests einer Datei im selben Worker, Exit 0); der innere Lauf darf keinen Echtbaum-Scan ausführen.

**5. repo_path.** Nur `_module_constants` (ab Z. 538): Zuweisungen werden einmal in `ast.walk`-Reihenfolge gesammelt, jede Fixpunkt-Runde läuft über diese Liste statt `ast.walk` neu. Semantik unverändert: erst alle Werte auflösen, dann binden (Tausch `A, B = B, A`), Fixpunkt. Z. 1-537 werden nicht verschoben (Kommentar-Verweise anderer Dateien); ein ergänzter Test steht deshalb am Dateiende. Kein Filter möglich (ein Pfad ist aus Stücken zusammensetzbar). Mutation: umgekehrte Reihenfolge und nur eine Runde müssen rot werden; fehlt dafür ein Test, wird er ergänzt.

**6. user_id.** `_sammle_verstoesse(wurzel)` bekommt einen Wurzel-Parameter (heute ist kein gepflanzter Verstoß prüfbar). Filter über `quelltext_mit_bezeichnern(datei, eines_aus=<Namen aus _baue_ziel_register() zur Laufzeit>)`; beide Register werden als nicht leer zugesichert. `_SELBST` bleibt ausgenommen. `SyntaxError` und `UnicodeDecodeError` in gefilterten oder gelesenen Dateien bleiben rot; unparsbare, herausgefilterte Dateien deckt `test_jede_testdatei_ist_parsbar`. Die Pfad-Ausgabe muss auch für `tmp_path` funktionieren (heute `relative_to(_REPO)`). Gepflanzt: Name-Aufruf, Attribut-Aufruf, Fullwidth-Name, je in `tmp_path`.

**7. timeout(180).** Der Timeout an beiden thunder-Tests entfällt. Beleg ist der grüne CI-Lauf des PR mit dem 30-s-Netz; reißt er belegt das 30-s-Netz, steht dort 60 statt 180.

**8. Nachweise.** Kein dauerhafter Laufzeit-Assert (wackelt mit der Last). Artefakte in `docs/artifacts/rework-3316-scanner-ratschen/`: Vorher/Nachher je Datei im selben Zeitfenster; gefiltert gegen ungefiltert mit Fundgleichheit (user_id ohne Marker-Duldung 8 = 8; Regel D: 0 Kandidaten im echten Baum, daher Beweis allein über gepflanzte Verstöße, offen benannt); Mutationsprotokoll per String-Ersetzung mit externer Sicherungskopie, nie `git checkout/stash/reset`.

**9. Reihenfolge.** Drei eigene Commits: thunder, repo_path, user_id (jeder compiliert und ist grün).

## Expected Behavior

- **Input:** Lauf der vier Testdateien (lokal oder CI) gegen den echten `tests/`-Baum bzw. `tmp_path`.
- **Output:** dieselben Funde wie vorher, kürzere Laufzeit, mehr Reserve zum 30-s-Netz in CI.
- **Side effects:** keine; kein Produktcode, kein Timeout angehoben, `KNOWN_VIOLATIONS` und Altlasten unverändert.

## Acceptance Criteria

- **AC-1:** Given die fünf Behauptungs-Alternativen von Regel D / When Filter und Muster gebildet werden / Then stammen beide aus derselben Liste, jedes Filterwort ist nicht leer und ohne Leerzeichen, und das Muster erkennt genau dieselben Wortlaute wie vor dem Umbau.
  - Test: Verhaltenstest je Listeneintrag: ein Kommentar mit dem Wortlaut wird vom Muster UND vom Filter erkannt; Vergleich mit dem alten Muster über eine Wortlaut-Liste (Treffer und Nicht-Treffer).

- **AC-2:** Given gepflanzte D-Verstöße in `tmp_path` (jede der 5 Alternativen einzeln inkl. `oe`/`ö`, `ae`/`ä`, beide „unverändert"-Formen, Phrase über Zeilenbruch, Variante mit `ı`, Kommentar über der Anweisung und Zeilenkommentar) / When `scan_tree` mit `rules=("D",)` läuft / Then wird jeder Verstoß gefunden.
  - Test: parametrierter Test je Fall über `scan_tree(tmp_path, rules=("D",))`; Fund mit Dateiname erwartet.

- **AC-3:** Given eine gepflanzte Datei ohne Filterwort im Kommentar, aber mit Verstoß gegen Regel A / When `scan_tree` mit A+B+C+D, A+B+C, A+D und mit `("D",)` läuft / Then wird der Verstoß bei jeder Regelmenge mit A gefunden, und nur bei `("D",)` steht die Datei in `besucht`, aber nicht in `geparst`.
  - Test: `tmp_path`-Datei aus `faelle.py.txt` (`a1-enum-attribut-dict`), vier Läufe; AC-12 und AC-19 des Bestands bleiben grün.

- **AC-4:** Given der echte Testbaum / When der Baumlauf mit Regel D läuft / Then ist `besucht` gleich der `rglob`-Sollmenge, `geparst` nicht leer, echte Teilmenge von `besucht` und enthält eine bekannte echte Datei.
  - Test: Mengenvergleich `besucht` gegen `rglob("*.py")`; Zusicherungen auf `geparst`; ersetzt die Positivkontrolle „Regel A > 0".

- **AC-5:** Given die Backend-Läufe der Gewitterskala / When die Duldungsfunktion aus einem Rohlauf die Fixtures „ohne Basislinie" und „ohne Whitelist" ableitet / Then sind sie gleich dem Ergebnis der bisherigen Einzelläufe, der AC-12-Lauf bleibt ein echter `scan_tree`-Lauf, und es laufen 3 statt 4 Scans.
  - Test: Backend-Tests bleiben grün; Mutation der herausgelösten Funktion „Whitelist ignoriert“ macht den AC-12-Lauf rot, „Altlasten ignoriert“ macht `test_scan_tree_wendet_die_altlasten_basislinie_selbst_an` rot (`ALTLASTEN` ist leer, der AC-12-Lauf kann dort nicht rot werden; beide beweisen, dass `scan_tree` die Duldung selbst benutzt), Mutation „duldet alles“ macht die Leerlauf-Tests rot; Gleichheit zu vorher einmalig im Artefakt.

- **AC-6:** Given alle drei Cache-Dateien tragen je eine eigene `xdist_group` / When sie mit `-n 2 --dist loadgroup` laufen / Then laufen alle Tests jeder Datei in einem Worker, der Lauf ist grün und führt keinen Echtbaum-Scan aus.
  - Test: erweiterter Subprozess-Nachweis in `test_bezeichner_vorfilter.py` mit drei Dateien und je Datei passendem Auswahlkriterium; `len(gruppen) == 3`, Worker-Kennung je Datei einheitlich, Exit-Code 0.

- **AC-7:** Given `_module_constants` mit einmal gesammelten Zuweisungen / When ein Tausch `A, B = B, A`, eine Kette bis zum Fixpunkt und der echte Baum aufgelöst werden / Then entstehen dieselben Konstanten in derselben Reihenfolge wie vorher, und eine umgekehrte Reihenfolge oder nur eine Runde macht mindestens einen Test rot.
  - Test: Test für Tausch und Fixpunkt (ergänzt, falls er fehlt); einmaliger Vergleich der Konstanten über 1.946 Dateien (0 Abweichungen) und Mutationsprotokoll im Artefakt.

- **AC-8:** Given gepflanzte Verstöße in `tmp_path` (Name-Aufruf, Attribut-Aufruf, Fullwidth-Name) / When `_sammle_verstoesse(tmp_path)` mit Filter läuft / Then werden alle gefunden, der Pfad der Funde wird auch für `tmp_path` ausgegeben, `_SELBST` bleibt ausgenommen, und eine Datei mit `SyntaxError` unter den gefilterten bleibt rot.
  - Test: je ein Fall in `tmp_path`; Register aus `_baue_ziel_register()` als nicht leer zugesichert; ein `SyntaxError`-Fall erwartet rot; Echtbaum-Fundgleichheit gefiltert gegen ungefiltert (8 = 8) im Artefakt.

- **AC-9:** Given künstlich verfälschte Filter oder Sammlung (falsches Filterwort, verschärfte `#`-Bedingung, Filter immer falsch, Wurzel ignoriert, umgekehrte Reihenfolge, nur eine Runde, Duldungsfunktion ohne Whitelist, ohne Altlasten, duldet alles) / When die Tests der jeweiligen Ratsche laufen / Then ist je Verfälschung mindestens ein Test rot.
  - Test: Mutations-Gegenprobe per String-Ersetzung mit externer Sicherungskopie (kein `git checkout/stash/reset`), Ergebnis je Mutation im Artefakt-Ordner protokolliert.

- **AC-10:** Given die umgebauten Dateien und das globale 30-s-Netz / When der CI-Job `test` des PR läuft / Then ist er grün und kein Test der vier Dateien trägt mehr `timeout(180)`; nur falls ein CI-Lauf das 30-s-Netz belegt reißt, steht an den zwei thunder-Tests `timeout(60)` mit Verweis auf diesen Lauf.
  - Test: grüner CI-Lauf des PR als Beleg; Vorher/Nachher je Datei seriell auf dem Mac im selben Zeitfenster in `docs/artifacts/rework-3316-scanner-ratschen/`; bewusst kein Laufzeit-Assert als Dauertest.

## Test Plan

### Automated Tests (TDD RED)

- [ ] thunder: gepflanzte D-Verstöße je Alternative, Zeilenbruch, `ı`, beide Kommentarformen (AC-2); Regelmenge ungleich `{"D"}` ungefiltert (AC-3).
- [ ] thunder: Mengenvergleich `besucht`, `geparst` (AC-4); Datenstruktur-Test (AC-1); Duldungsfunktion, 3 Läufe (AC-5).
- [ ] Gruppen-Nachweis mit drei Dateien (AC-6).
- [ ] repo_path: Tausch und Fixpunkt in `_module_constants` (AC-7).
- [ ] user_id: Name-, Attribut-, Fullwidth-Fall, `SyntaxError` rot (AC-8).
- Einmalige Nachweise (Artefakt, kein Dauertest): Fundgleichheit, Mutationen (AC-9), Vorher/Nachher (AC-10).

## Scope

- **In Scope:** die vier genannten Testdateien, Spec, Artefakte.
- **Out of Scope:** Umbau von `_sammle`/`_resolve` in repo_path (ca. 3 s der 5,3 s); abgelaufene `EXPIRY`-Daten von thunder und repo_path (#1199); Scheibe 3 (#3317); jede Produktänderung.

## Definition of Done

- [ ] AC-1 bis AC-10 erfüllt, alle Tests der vier Dateien grün.
- [ ] Nachweise in `docs/artifacts/rework-3316-scanner-ratschen/`.
- [ ] Kein Timeout angehoben, `timeout(180)` entfernt (Ausnahme nur nach AC-10), kein Produktcode berührt.
- [ ] Alle CI-Pflicht-Checks grün.

## Known Limitations

- repo_path bleibt am engsten am 30-s-Netz (Hochrechnung aus „CI mehr als 4,3-mal lokal": mindestens 18 s nach, 23 s vor Umbau; nach oben unbelegt). Mehr bräuchte einen Umbau von `_sammle`/`_resolve`, nicht Teil von #3316.
- CI protokolliert keine Einzelzeiten (kein `--durations`); die Faktor-4-bis-10-Schwankung zwischen den Messungen ist ungeklärt, Vergleiche nur im selben Zeitfenster.
- Regel D hat im echten Baum 0 Kandidaten; der Beweis der Filter-Verlustfreiheit liegt allein bei den gepflanzten Verstößen.
- Gesamtwirkung ehrlich: lokal ca. 21,3 auf ca. 11,9 s (aus Einzelwerten gerechnet); Hauptnutzen ist die Reserve in CI.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Testinfrastruktur ohne Änderung an Kanälen, Providern, Datenmodell, Auth oder Test-Politik; die Wächter behalten ihre Zusicherungen, nur der Weg dorthin wird kürzer. Die Filterausnahme (Kommentartext statt Bezeichner) ist in dieser Spec begründet und führt keine neue Regel ein.

## Changelog

- 2026-11-24: Initial spec created (Workflow rework-3316-scanner-ratschen, Issue #3316, Scheibe 2)
- 2026-11-24: Validierung: Test-Zeile AC-5 an leeres `ALTLASTEN` angepasst (AC unverändert); PO-Ausnahme zum Umfang (410 Zeilen, keine Abtrennung) siehe Kommentar in #3316; Messwerte in `docs/artifacts/rework-3316-scanner-ratschen/laufzeiten.md` ersetzen die Schätzung aus der Messbasis
