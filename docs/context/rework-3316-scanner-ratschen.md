# Context: rework-3316-scanner-ratschen

## Request Summary
#3316 = Scheibe 2 zu #3279 (Epic #1196): drei Wächter, die den Testbaum lesen und parsen, beschleunigen, ohne eine
Zusicherung zu schwächen: Gewitterskala (thunder), Pfad-Wächter (repo_path), user_id.
Der PO rief `/00-intake #3279` auf. Scheibe 1 ist gemergt (#3325), Scheibe 3 (#3317) bearbeitet Sitzung gregor-zwanzig-36
(Worktree `rework-3279-testsuite-tempo`), also bleibt #3316. Branch `rework-3316-scanner-ratschen` auf origin/main 3ea65a10d.
Keine Dateiüberschneidung mit dem #3317-Branch (Stand 14:19 geprüft).

Intake: Scope 1, Blast Radius 1, Unsicherheit 1 = **Summe 3**. `AUTONOMY=auto`.

## Messung 2026-11-24 14:19–14:20 (Mac, seriell, 3 Läufe, Last 3,8–4,9, alles grün, 1.946 Testdateien)
| Test | Lauf 1 / 2 / 3 | Scheibe-1-Kontext (früher am selben Tag) |
|---|---|---|
| thunder Setup `tests_baum_scan` (A+D) | 6,8 / 7,3 / 7,1 s | 61,6 s |
| thunder 4 Backend-Läufe | je 1,3–1,6 s, zusammen ca. 5,5 s | 10,6–13,3 s je Lauf |
| repo_path AC-3 | 5,4 / 5,5 / 5,6 s | 30,2 s (Timeout) / 38,3 s |
| user_id AC-10 | 2,9 / 2,9 / 3,0 s | 21,3 s |

🔴 **Faktor 4–10 schneller als die Zahlen in Issue und Scheibe-1-Kontext, ohne dass diese drei Tests umgebaut wurden.**
Ursache nicht untersucht (Last/Drosselung des Macs ist nur eine Vermutung). Folgen:
- Das Problem „reißt das 30-s-Netz“ ist lokal derzeit NICHT nachstellbar; Summe ca. 20 s.
- Vorher/Nachher nur im selben Zeitfenster; alte Absolutwerte nicht als Vorher verwenden.
- **Offen für die Analyse:** CI-Zeiten (der CI-Job `test` ist der eigentliche Nutznießer; Kommentar im Code: „CI seit 2026-11-23
  rot“). Im Intake nicht ausgewertet: Befehl wurde vom Worktree-Schutz abgelehnt, also `gh run view` als einzelne Befehle.
  Ergibt CI wenig Zeit, ist ein kleinerer Schnitt zu empfehlen (nur thunder).

## Related Files
| File | Relevance |
|------|-----------|
| `tests/tdd/test_thunder_scale_local_copy_guard.py` (1733 Z.) | `_PARITAETS_BEHAUPTUNG` :237 (5 Alternativen, IGNORECASE); `_regel_d` :663; `_kommentarblock_ueber` :638; `scan_source` :723 (setzt `kind.parent`); `scan_tree` :768 (`besucht`, `baseline`, `canonical_symbols`); Backend-Läufe: Fixture :1045, Test :1054, Fixture :1179, Test :1226 (anderer Marker); Testbaum-Fixture :1335, Tests mit `timeout(180)` :1347 und :1363 |
| `tests/tdd/test_repo_path_hardcoding_ratchet.py` (691 Z.) | `_module_constants` :538 läuft je Fixpunkt-Runde (max. 25) `ast.walk` neu; `_sammle` :635; `scan_for_hardcoded_repo_paths` :667 (unlesbare Datei ⇒ `warnings.warn`, fängt ValueError nicht); AC-3 :135 |
| `tests/test_test_suite_passes_user_id_explicitly.py` (225 Z.) | `_baue_ziel_register` :138ff; `_sammle_verstoesse` ~:196 **ohne Wurzel-Parameter**, daher heute **kein gepflanzter Verstoß prüfbar**; `_SELBST` ausgenommen; nur ein Test (AC-10) |
| `tests/helpers/bezeichner_vorfilter.py` | Helfer aus Scheibe 1: `quelltext_mit_bezeichnern(datei, alle, eines_aus)`, `unparsbare_dateien(wurzel)` |
| `tests/tdd/test_bezeichner_vorfilter.py` | Parsebarkeits-Prüfung über den ganzen Testbaum (deckt die künftig nicht geparsten Dateien) |
| `tests/fixtures/thunder_scale_guard_cases/faelle.py.txt`, `tests/fixtures/ratchet_cases/faelle.py.txt` | Vorlagen mit echten Verstößen |

## Existing Patterns (aus Scheibe 1, zu übernehmen)
- Vorfilter auf Bezeichner im NFKC-Text vor `ast.parse`; `functools.cache` nur für den echten Baum, intern Tupel, Aufrufer bekommt Kopie.
- `pytestmark = pytest.mark.xdist_group("<eigener Name>")` je Cache-Datei, einzelne Marke, kein `@`, nicht `echtdaten`.
- Scan-Funktion mit Wurzel-Parameter, damit `tmp_path` den gefilterten Pfad beweist.
- Artefakte: gefiltert/ungefiltert, Mutationsprotokoll, Vorher/Nachher (`docs/artifacts/rework-3279-testsuite-tempo/`).

## Dependencies
- Upstream: stdlib (`ast`, `re`, `functools`), `bezeichner_vorfilter`, pytest-timeout (global 30 s), pytest-xdist (`--dist loadgroup`).
- Downstream: CI-Pflicht-Check `test`, Commit-Gate, Volllauf. Kein Modul importiert die drei Dateien (gesucht in
  tests/, .claude/, scripts/); andere Dateien verweisen nur in Kommentaren mit Zeilennummern darauf
  (`test_repo_path_hardcoding_ratchet.py:339/346-352/351/52/180`): Zeilen oberhalb ~360 dort möglichst nicht verschieben.

## Existing Specs
- `docs/specs/modules/rework_3279_scanner_ratschen_tempo_s1.md` (Vorgänger), `docs/specs/modules/thunder_scale_guard.md`
- `docs/specs/modules/fix_2151_default_fallbacks_scheibe_c.md` (AC-10 user_id)
- Analyse und Auflagen der Gegenprüfung: `docs/context/rework-3279-testsuite-tempo.md`; Doku der Ratschen: `docs/reference/gates_und_ratschen.md` (Z. 201, 450, 934)

## Risks & Considerations
1. Zu strenger Filter macht einen Wächter still blind: je Ratsche gepflanzter Verstoß im gefilterten Lauf plus Mutation.
2. thunder Regel D: Filter als `re.IGNORECASE` auf dem **Rohtext** (`ı` U+0131!), alle 5 Alternativen. Phrase darf über Zeilen
   brechen (Test :1318): Filter nur auf einzelne Wörter, nie auf die ganze Phrase. `besucht` zählt VOR dem Filter.
3. thunder Positivkontrolle „Regel A > 0 auf tests/“ (:1364) beweist heute auch, dass wirklich geparst wird. Ersatz:
   Mengenvergleich der besuchten Dateien UND gepflanzte D-Fundstelle im gefilterten Baumlauf.
4. Backend-Läufe 1–3: `baseline`/`canonical_symbols` wirken nur in `scan_tree`, also einmal roh scannen; Lauf 4 (Marker) bleibt eigen.
   Prüfen, dass `_fund` nichts davon liest.
5. user_id: Namen zur Laufzeit aus `_baue_ziel_register()`; Wurzel-Parameter nötig; `_SELBST` bleibt ausgenommen;
   `SyntaxError` in gefilterter Datei bleibt rot.
6. repo_path: kein Filter möglich; Zuweisungen einmal in `ast.walk`-Reihenfolge sammeln (reihenfolgegleich).
7. `timeout(180)` nur mit Messung zurücknehmen; wegen der Schwankung auch CI-Wert heranziehen.
8. Umfang: 3 Testdateien, Scheibe 1 wuchs von +200 auf +487 Zeilen; ±250 im Blick behalten, sonst schneiden.
9. `EXPIRY` von thunder (2026-11-01) und repo_path (2026-10-27) ist überschritten: gehört nach #1199, nicht hierher.

## Analysis

### Type
Feature (Rework, reine Testdateien, kein Produktcode)

### Messung 2026-11-24 14:23–14:26 (Mac, seriell, Last 2,2–3,2, ein Prozess, Wanduhr ≈ CPU)
| Scanner | Ist | Prototyp | Gleichheit |
|---|---|---|---|
| thunder tests/ (A+D) | 6,97 s | D ungefiltert 4,88 · Wort im Rohtext 3,65 (974 Dateien) · **Wort hinter `#` 1,71 (414)** | 0 = 0, siehe Warnung |
| thunder Backend, 4 Läufe | 5,8 s | 2 Läufe ca. 2,9 s (gerechnet, Rohlauf 1,44 s mit 9 Funden) | Ableitung noch nicht verglichen |
| repo_path AC-3 | 5,37 s (davon `_module_constants` 2,1) | **4,22 s** | Konstanten inkl. Reihenfolge: 0 Abweichungen bei 1946 Dateien |
| user_id AC-10 | 3,15 s | **1,80 s** (731 Dateien) | ohne Marker-Duldung 8 = 8 identische Funde |
| reines Parsen tests/ (Untergrenze) | 1,67 s | | |

Summe ca. 21,3 → ca. 10,6 s (gerechnet aus den Einzelwerten).

- 🔴 **Regel D hat im echten Testbaum null Kandidaten**, auch ohne Positionsprüfung (Behauptung + ≥2 Token: 0; Listen mit
  ≥2 Token überhaupt: 51). Gleichheit gefiltert/ungefiltert auf dem echten Baum beweist dort nichts; der Nachweis
  braucht gepflanzte D-Verstöße (alle 5 Alternativen, Zeilenbruch, `ı`) im gefilterten Baumlauf.
- **CI-Beleg:** main-Lauf 45202617843 (2026-11-23 15:12 UTC) riss das 30-s-Netz im Setup von `tests_baum_scan`, beide
  Tests auf demselben Worker gw1, beide per Timeout. CI ist also >4× langsamer als dieser Mac. Danach kam `timeout(180)`
  (bbd5b716e). CI protokolliert keine Einzelzeiten (kein `--durations`), mehr ist aus CI nicht zu holen.
- Speicherlast/GC als Ursache der Schwankung: nicht bestätigt (6 Mio. Zusatzobjekte ändern nichts; GC aus: 6,9 → 5,7 s).
- `_fund` liest nur `spec.marker`; `baseline`/`canonical_symbols` wirken nur in `scan_tree` (Risiko 4 geklärt).
- `#`-Filter: `_kommentarblock_ueber` nimmt nur Text hinter `#` derselben Quellzeile, `splitlines()` trennt feiner als `\n`,
  also ist `#[^\n]*Wort` notwendige Bedingung (eigene Prüfung; Gegenprüfung läuft).
- Prototyp-Muster: `#[^\n]*(?:1:1|wortw(?:oe|ö)rt|identische|eingefroren|unver(?:ae|ä)ndert)`, IGNORECASE, Rohtext.

### Gegenprüfung (Plan-Agent, nur gelesen) und Entscheidungen des Tech Leads
Kein Gegenbeispiel gegen die drei Umbauten gefunden. Der `#`-Filter ist Obermenge der Regel-D-Treffer. Auflagen für die Spec:
1. **Filterausnahme ausdrücklich benennen:** S1 erlaubt nur Bezeichner als Filter; hier Kommentartext (kennt keine Escapes).
2. **Drift:** eine sechste Alternative in `_PARITAETS_BEHAUPTUNG` ohne Filteranpassung macht D still blind. Filter und Muster aus
   EINER Wortliste bauen, dazu parametrierter Test je Alternative (inkl. `ı`, Zeilenbruch).
3. **`geparst`-Set zusätzlich zu `besucht`:** `besucht` beweist nur Lesen. Prüfen: nicht leer, enthält eine bekannte echte Datei;
   dazu gepflanzter D-Verstoß im gefilterten Baumlauf (`tmp_path`). `besucht` zählt vor dem Filter (:806).
4. **Backend:** Duldungslogik aus `scan_tree` als Funktion herauslösen, die `scan_tree` selbst nutzt; nie im Test nachbauen.
   Entscheidung: **3 statt 4 Läufe**. AC-12 (:1054) bleibt echter `scan_tree`-Lauf mit Standardwerten (keine Schwächung),
   die Fixtures :1045 und :1179 kommen aus einem Rohlauf, Lauf 4 (Marker) bleibt eigen. Ergebnisgleichheit zu heute belegen.
5. **user_id:** Wurzel-Parameter vor Filter; `_SELBST` ausgenommen; Register nicht leer zusichern; pflanzen: Name-Aufruf,
   Attribut-Aufruf, Fullwidth-Name.
6. **repo_path:** nur `_module_constants` (ab :538); Reihenfolge der Anweisungen und Ziele erhalten (`A, B = B, A`); Z. 1–360 nicht
   verschieben (Verweise in test_mail_recipient_parity, test_output_timezone_guard, test_egress_single_dial_point).
7. **xdist_group für thunder:** `test_cache_dateien_laufen_je_in_einem_worker` (`tests/tdd/test_bezeichner_vorfilter.py:88-113`)
   kennt nur 2 Dateien, prüft `len(gruppen) == 2` hart und läuft mit `-k scanner`: miterweitern, sonst unbelegt.
8. Filter-Regex: quadratisches Verhalten bei Zeilen mit sehr vielen `#` beachten (zeilenweise oder nur ein Treffer je Zeile).
9. `timeout(180)` (:1347, :1363) zurücknehmen; Beleg ist der grüne CI-Lauf des PR mit 30-s-Netz. Wird er rot: 60 statt 180.

### Variantenvergleich (Mac, seriell, s; Backend mit 3 Läufen = 4,2 gerechnet)
| Variante | thunder | repo_path | user_id | Summe |
|---|---|---|---|---|
| nichts tun | 12,8 | 5,4 | 3,2 | 21,3 |
| nur thunder | 5,9 | 5,4 | 3,2 | 14,4 |
| **alle drei (gewählt)** | 5,9 | 4,2 | 1,8 | **11,9** |

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| tests/tdd/test_thunder_scale_local_copy_guard.py | MODIFY | `#`-Filter Regel D, `geparst`, Duldungsfunktion, Rohlauf, xdist_group, timeout(180) weg |
| tests/tdd/test_repo_path_hardcoding_ratchet.py | MODIFY | Zuweisungen einmal sammeln |
| tests/test_test_suite_passes_user_id_explicitly.py | MODIFY | Wurzel-Parameter, Bezeichner-Filter, gepflanzte Verstöße |
| tests/tdd/test_bezeichner_vorfilter.py | MODIFY | Gruppen-Nachweis um thunder erweitern |

### Scope Assessment
- Files: 4 (plus Spec/Artefakte). Estimated LoC: +180 bis +230 / ca. −60, knapp an ±250. Reihenfolge: thunder zuerst (trägt den
  größten Teil und das Timeout-Problem), dann repo_path, user_id als eigener Commit; bei Überschreitung diese zwei abtrennen.
- Risk Level: MEDIUM (stilles Blindwerden eines Wächters), kein Produktcode.

### Technical Approach
Wie oben. Mutationen je Ratsche: falsches Filterwort, `#`-Bedingung verschärft, Filter immer falsch, Wurzel ignoriert ⇒ je ein roter Test.
Ehrliche Grenze: repo_path bleibt am engsten am 30-s-Netz (Hochrechnung aus „CI > 4,3× lokal“: mindestens 18 s nach, 23 s vor
Umbau; nach oben unbelegt). Mehr gäbe nur ein Umbau von `_sammle`/`_resolve` (ca. 3 s der 5,3 s), nicht Teil von #3316.

### Open Questions
Keine Produktfrage offen.

## TDD RED (Stand 2026-11-24)
50 failed, 3 errors, 132 passed. Beleg: `docs/artifacts/rework-3316-scanner-ratschen/test-red-output.txt`.

Von den Tests festgelegte Symbole (GREEN liefert sie):
- thunder: `_PARITAETS_ALTERNATIVEN` (5 Paare `(filterwort, rest)`; Muster ist `"|".join(wort + rest)`),
  `_kann_paritaet_behaupten(quelle) -> bool`, `_ist_geduldet(fund, spec, altlasten) -> bool`,
  `scan_tree(..., geparst=set)`, Fixture `backend_rohlauf` (ohne Whitelist, ohne Basislinie; die zwei Bestands-Fixtures
  werden daraus abgeleitet), `pytestmark = pytest.mark.xdist_group("gewitterskala")`. `timeout(180)` ist schon entfernt.
- user_id: `_sammle_verstoesse(wurzel)`. repo_path: `_module_constants` liest den Baum genau einmal.

Bewusst schon gruen (halten bestehendes Verhalten fest, Beweis per Mutation in GREEN):
`test_konstanten_behalten_reihenfolge_und_fixpunkt` (5 Faelle), `test_scan_tree_wendet_die_altlasten_basislinie_selbst_an`.

Abweichungen/Befunde:
- AC-5 sagt, "Altlasten ignoriert" mache den AC-12-Lauf rot. `ALTLASTEN` ist leer, das kann dort nicht rot werden;
  den Nachweis fuehrt der gepflanzte Test `test_scan_tree_wendet_die_altlasten_basislinie_selbst_an`.
- 🔴 Umfang: allein RED ist +234/-34 (268; thunder 165, vorfilter 25, repo_path 36, user_id 42). Die Schnittregel der Spec
  (nach dem thunder-Commit zaehlen, zuerst user_id abtrennen) wird voraussichtlich greifen. Deshalb liegen die RED-Tests
  in drei getrennten Commits: abtrennen heisst den jeweiligen RED-Commit per `git revert` zuruecknehmen und neues Issue anlegen.
