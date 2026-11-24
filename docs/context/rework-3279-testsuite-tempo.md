# Context: rework-3279-testsuite-tempo

## Request Summary
#3279 (Teil von Epic #1196, Folge der Messung in #3209): Wächter, die den ganzen `tests/`-Baum lesen und parsen,
und Tests mit echten Wartezeiten schneller machen, ohne eine Zusicherung zu schwächen. Abschluss laut Issue:
Vorher/Nachher-Zeit je Datei belegt, Mutations-Gegenprobe je umgebauter Ratsche.

Intake: Summe 4 (voller Prozess, Kontext und Analyse getrennt). `AUTONOMY=auto`.

## Messung 2026-11-24 (Mac, Worktree auf origin/main, seriell, eine Messung)
Baum: 1.937 `.py`-Dateien unter `tests/`, 27,6 MB.

| Schritt | Zeit |
|---|---|
| alle Dateien lesen | 0,4 s |
| alle parsen (`ast.parse`) | **29,9 s** |
| ein `ast.walk` über alle Bäume (2,67 Mio. Knoten) | 7,4 s |
| Speicher, wenn alle Bäume gehalten werden | **839 MB RSS** (Prozess-Spitze) |

Das Parsen dominiert. Auf diesem Mac ist es langsamer als im Issue (Server); die Verhältnisse zählen, nicht die Absolutwerte.

Sechs Scanner-Dateien zusammen (`--durations=25`): **6 Tests rot** nach jeweils ca. 30 s. Das passt zum globalen
`timeout = 30` (setup + call ≈ 30,2–30,4 s); die Meldungstexte selbst wurden nicht ausgewertet (Ausgabe abgeschnitten).
Beim RED-Schritt bestätigen.
Wegen Abbruch sind diese Zeiten nur Untergrenzen:

| Test | gemessen |
|---|---|
| thunder_scale Setup `tests_baum_scan` (Regel A+D) | 61,6 s |
| thunder_scale Backend-Scans `src/`+`api/` (4 Läufe: 2 Tests, 2 Modul-Fixtures) | 13,3 / 12,9 / 11,3 / 10,6 s |
| fixture_wallclock: 5 Baumläufe in 5 Tests | 30,4 / 30,1 / 30,2 / 30,2 / 17,2 s (4 davon rot) |
| trip_fixtures_gestellte_uhr: 2 Baumläufe | 29,8 / 30,2 s (2. rot) |
| repo_path_hardcoding AC-3 | 30,2 s (rot) |
| user_id explizit AC-10 | 21,3 s |
| trips_pfad_rueckbau | 17,1 s |

Nicht gemessen: `refactor/test_epic_129a_3_ui_removed.py`, `test_pytest_collection_and_timeout_safety.py`,
`test_einstellung_gleich_mail_validatoren.py`, `test_dwd_thunder_parallel_fetch.py`, `test_radar_nowcast_segment_wanduhr_unabhaengig.py`
(Werte dazu stehen nur im Issue, Stand 22.11.).

## Related Files
| File | Relevance |
|------|-----------|
| tests/tdd/test_fixture_wallclock_ratchet.py:532, :1077 | zwei Scanner (direkt / indirekt), je Test neuer Baumlauf; 2. Regel hat billigen Vorab-Ausstieg (Alarmpfad-Import), aber erst NACH dem Parsen |
| tests/tdd/test_thunder_scale_local_copy_guard.py:723 (`scan_source`), :768 (`scan_tree`), :1044/:1178/:1334 (Modul-Fixtures) | setzt `kind.parent` auf den Baum (verändert ihn!); `besucht`-Set als Vertrag; Regel A auf tests/ ist nur Positivkontrolle |
| tests/tdd/test_trip_fixtures_laufen_unter_gestellter_uhr.py:72 | verlangt `make_trip` + `save_trip` in einer Funktion |
| tests/tdd/test_repo_path_hardcoding_ratchet.py:667, :135 (AC-3) | `_tracked_files` ist schon gecacht; unlesbare Datei ⇒ `warnings.warn`, nie still |
| tests/test_test_suite_passes_user_id_explicitly.py:196 | 1 Lauf, Register mit 38 Zielnamen |
| tests/test_trips_pfad_rueckbau.py:121 | 1 Lauf, sucht nur `get_trips_dir` |
| tests/refactor/test_epic_129a_3_ui_removed.py (`test_ac7_collection_clean`) | Subprozess `uv run pytest tests/ --collect-only`, `timeout(120)` |
| tests/tdd/test_pytest_collection_and_timeout_safety.py:272–337, :390 | bis zu 8 Sammel-Subprozesse als Modul-Fixtures, zweite Voll-Sammlung in :390 |
| tests/tdd/test_dwd_thunder_parallel_fetch.py:634 | echter 10-s-Default-Timeout als Zusicherung |
| tests/tdd/test_radar_nowcast_segment_wanduhr_unabhaengig.py:143 | Mehrfachläufe, `timeout(300)` |
| tests/tdd/test_einstellung_gleich_mail_validatoren.py | Validator je Fall über `validator_lauf` (`tests/helpers/mail_lang_fixture.py`) |

## Existing Patterns
- Lauf-Cache je Prozess: `functools.cache`/`lru_cache` in `tests/test_success_status_guard.py:1450`,
  `test_resolution_loss_guard.py:616`, `test_output_timezone_guard.py:425`, `test_guard_findings_survive_line_shifts.py:67`.
- Geteilte Scan-Helfer: `tests/helpers/metrik_listen_scan.py`, `katalog_verarbeitung_scan.py`, `echtbaum_ratsche.py`.
- Modul-Fixture statt Mehrfachlauf: thunder_scale (`tests_baum_scan`).
- Zeit-Anhebung nur einzeln per `@pytest.mark.timeout(N)` mit Begründung (`docs/reference/gates_und_ratschen.md`, Abschnitt „Parallele Kern-Suite in CI“).

## Dependencies
- Upstream: `ast`, `pathlib`, pytest-timeout (global 30 s), pytest-xdist (`-n 4 --dist loadgroup` in CI).
- Downstream: CI-Job `test` (Pflicht-Check jedes PR), Commit-Gate, lokaler Volllauf.

## Existing Specs
- `docs/specs/modules/perf_3209_pytest_xdist_ci.md` (Vorgänger, CI parallel)
- `docs/specs/modules/fix_1709_wallclock_ratsche_indirekt.md` (zweite Regel der Wanduhr-Ratsche)
- Lokale parallele Form ist **#3278**, nicht Teil hiervon.

## Risks & Considerations
1. **Ein „session-gecachter“ Index wirkt unter xdist nur je Worker-Prozess.** Ohne gemeinsame `xdist_group` parst jeder
   Worker neu; hält jeder alle Bäume, drohen bis zu 4 × ~0,8 GB. Der Issue-Vorschlag (AST-Index) ist deshalb nicht
   automatisch die beste Form.
2. **Alternative für die Analyse:** billiger Textfilter VOR `ast.parse` (z. B. Datei ohne `make_trip` kann keinen Fund
   liefern), dazu Ergebnis-Cache je Scanner im Prozess. Kein Speicherproblem, aber der Filter muss nachweislich
   verlustfrei sein (Alias-Importe, zusammengesetzte Namen, Umgehungsformen der Ratschen) – je Ratsche einzeln prüfen
   und per Mutation belegen (Filter zu streng ⇒ Test rot).
3. `scan_source` schreibt `kind.parent` in den Baum; `ast`-Bäume zwischen Scannern zu teilen verändert gemeinsamen Zustand.
4. Scanner müssen ihren Vertrag behalten: Aufruf mit `tmp_path`, unlesbare Datei sichtbar, `besucht` vollständig, keine Ausschlüsse.
5. Der thunder_scale-Ausfall im main-Lauf vom 23.11. 15:12 UTC ist inzwischen durch `timeout(180)` an den zwei Tests
   **überbrückt, nicht behoben**; nach dem Umbau Anhebung prüfen (zurücknehmen nur mit Messung).
6. **Umfang:** alle 11 Dateien überschreiten die Grenze (4–5 Dateien, ±250 Zeilen). Vorschlag für die Analyse:
   #3279 = Scanner-Ratschen; Wartezeiten/Subprozess-Sammlungen und Validator-Fälle als eigene Folge-Issues
   („Teil von #1196“, Label `strang:a-plattform`). Noch nicht angelegt.
7. Weitere rote main-Läufe vom 23.11. haben andere Ursachen (#3248; Go-Build-Timeout, notiert in #1196;
   `test_befehl_antwortzeit` AC-7) und gehören nicht hierher.

## Analysis

### Type
Rework (Testinfrastruktur), keine Produktwirkung.

### Korrektur der Kontext-Messung
„Das Parsen dominiert“ (oben, 29,9 s) gilt **nicht**: die 29,9 s entstanden, weil alle Bäume gehalten wurden
(Python-GC durchläuft dabei immer wieder den wachsenden Bestand). Nachgemessen 2026-11-24, gleicher Mac, Last ~5, je eine Messung:

| | gesamt |
|---|---|
| alle Bäume parsen und sofort verwerfen | 8,3 s |
| alle Bäume parsen und **halten**, GC an | 24,2 s |
| alle Bäume parsen und halten, GC aus | 8,2 s |

Je Scanner liegt die Zeit überwiegend im **Durchlaufen** der Bäume, nicht im Parsen (Werkzeug:
`docs/artifacts/rework-3279-testsuite-tempo/messung_vorher.py <repo>`):

| Scanner (ein Lauf) | vorher gesamt | davon parse | Prototyp | Funde vorher = Prototyp |
|---|---|---|---|---|
| wallclock direkt | 30,8 s | 9,6 | **3,3 s** | 1 = 1 |
| wallclock indirekt | 30,9 s | 9,4 | **9,4 s** | 0 = 0 |
| gestellte_uhr | 23,3 s | 9,2 | **1,7 s** | 10 = 10 |
| thunder `tests/` | 51,5 s (A+D) | 20,1 | **12,2 s** (nur D) | D: nicht getrennt gezählt = 0; A entfällt im Prototyp |
| thunder `src/`+`api/` (ein Lauf von vieren) | 10,7 s | 2,7 | nicht prototypisiert | – |
| repo_path | 38,3 s | 10,6 | **27,6 s** | 0 = 0 |
| user_id | 21,6 s | 10,3 | **11,7 s** | 0 = 0 |
| trips_pfad | 16,1 s | 8,9 | **0,4 s** | 0 = 0 |

0 = 0 beweist keine Verlustfreiheit; der Nachweis braucht gepflanzte Verstöße (RED/Mutation).

### Varianten
| Variante | Ergebnis |
|---|---|
| A: session-gecachter AST-Index (Issue-Vorschlag) | verworfen: spart nur den Parse-Anteil (Rest bleibt), hält 839 MB und wird durch GC selbst langsamer; unter xdist je Worker neu; `kind.parent` verändert geteilte Bäume |
| B: verlustfreier Textfilter VOR dem Parsen + Ergebnis-Cache je Modul | **empfohlen**: spart Parsen und Durchlaufen |
| C: `timeout` anheben / GC abschalten | verworfen: überdeckt nur |
| D: Cache auf Platte | verworfen: frischer CI-Checkout hat nie einen |

### Technical Approach
1. **Filterregel: nur Bezeichner, nie String-Inhalte.** Bezeichner stehen immer zusammenhängend im Quelltext, aber Python
   normalisiert sie per NFKC; der Filter muss deshalb auf NFKC-normalisiertem Text suchen (Kosten 0,27 s für den ganzen Baum).
   String-Inhalte (`"%H:%M"`, `"MED"`, Pfade) sind durch Escapes oder Verkettung zerlegbar und damit als Filter unzulässig.
   Ein gemeinsamer Helfer `tests/helpers/` liest, normalisiert und filtert.
2. Notwendige Bedingung je Scanner:
   - wallclock direkt: `strftime` · indirekt: `Stage` UND ein Name aus `_ALARMPFADE_INDIREKT` (Alias-Import nennt `Stage` weiterhin)
   - gestellte_uhr: `make_trip` UND `save_trip` · trips_pfad: `get_trips_dir` · user_id: ein Name aus dem Register (729 von 1.937 Dateien)
   - thunder Regel D: Behauptungs-Wort in einer Zeile hinter `#` (Kommentare kennen keine Escapes). Wörter einzeln suchen
     (`identische`, `eingefroren`, …), weil die Phrase über Zeilen brechen darf (414 Dateien geparst).
   - repo_path: **kein Filter möglich** (Pfad aus Stücken zusammensetzbar). Stattdessen Zuweisungen einmal sammeln statt je
     Fixpunkt-Runde neu zu laufen (verhaltensgleich).
3. **Ergebnis-Cache je Scanner** (`functools.cache` auf den echten `TESTS_ROOT`) für die Doppelläufe in wallclock und
   gestellte_uhr, nur für den echten Baum, nie für `tmp_path`; Rückgabe unveränderlich (Tupel).
   Unter xdist wirkt er nur je Worker: ein `xdist_group` je Datei ist zu entscheiden.
   Es gibt die Gruppe `echtdaten` schon; eigene Gruppennamen wählen, sonst hängt alles an einem Worker.
4. thunder: Positivkontrolle „Regel A > 0 auf tests/“ durch den Mengenvergleich der **besuchten** Dateien ersetzen (Muster AC-12,
   strenger). Achtung: Regel A prüft heute zugleich, dass wirklich geparst und gesucht wird; das muss eine gepflanzte
   D-Fundstelle weiter belegen. `besucht` zählt eine Datei vor dem Filter, sonst wäre der Vergleich falsch.
   Backend-Läufe 1–3 unterscheiden sich nur in `baseline`/`canonical_symbols` (wirken erst in `scan_tree`), also einmal roh
   scannen; Lauf 4 (anderer Marker) bleibt eigen. Danach `timeout(180)` per Messung prüfen.
5. **Parsebarkeit bleibt sichtbar:** user_id und trips_pfad werden heute bei einer kaputten Datei rot; mit Filter nur noch für
   gefilterte Dateien. repo_path parst weiter alles, warnt aber nur. Der Umbau muss dort einen roten Befund liefern
   (Warnungen des Pfad-Wächters in AC-3 ⇒ rot), im selben PR wie die Filter.
6. user_id: `NodeVisitor` durch `ast.walk` mit Sortierung nach Zeile ersetzen ist möglich, aber nicht gemessen; optional.

### Affected Files (with changes)
Schnitt wegen der Grenze 4–5 Dateien / ±250 Zeilen; jede Scheibe ein eigener PR:

| Scheibe | Dateien | geschätzt |
|---|---|---|
| **S1 (#3279)** | CREATE `tests/helpers/<vorfilter>.py`; MODIFY `tests/tdd/test_fixture_wallclock_ratchet.py`, `tests/tdd/test_trip_fixtures_laufen_unter_gestellter_uhr.py`, `tests/test_trips_pfad_rueckbau.py`, `tests/test_test_suite_passes_user_id_explicitly.py` | +170/−25 |
| **S2 (Folge-Issue)** | MODIFY `tests/tdd/test_thunder_scale_local_copy_guard.py`, `tests/tdd/test_repo_path_hardcoding_ratchet.py` | +110/−40 |
| **S3 (Folge-Issue)** | echte Wartezeiten, Sammel-Subprozesse, Validator-Fälle (5 Dateien; nicht analysiert) | offen |

Punkt 5 betrifft damit S1: die rote Parsebarkeits-Prüfung gehört in S1 (6. Datei `test_repo_path_hardcoding_ratchet.py`, wenige
Zeilen) oder als eigener billiger Test in den Helfer-Test. Empfehlung: in S1 in repo_path AC-3.
Folge-Issues noch NICHT angelegt (Label `strang:a-plattform`, „Teil von #1196“), bei der Spec anlegen.

### Scope Assessment
- Files S1: 5–6, Estimated LoC: +170/−25
- Risk Level: MEDIUM (ein zu strenger Filter macht einen Wächter still blind)

### Dependencies
Nur stdlib (`ast`, `unicodedata`, `functools`); keine neue Abhängigkeit.

### Befunde gegen den Plan
- Absolutzeiten schwanken auf diesem Mac stark mit der Last; Vorher/Nachher nur im selben Zeitfenster vergleichen. CI-Zeiten nicht ausgewertet.
- user_id (11,7 s) und wallclock indirekt (9,4 s) bleiben spürbar; repo_path (27,6 s) bleibt nahe am 30-s-Netz.
- Nebenbefund: `EXPIRY` von wallclock (2026-11-08), repo_path (2026-10-27) und thunder (2026-11-01) ist überschritten: Gate-Audit, gehört nach #1199.

### Open Questions
- [ ] Keine PO-Fragen. Technisch in der Spec festzulegen: `xdist_group` je Datei ja/nein.

### Gegenprüfung (Plan-Agent, 2026-11-24): Auflagen für die Spec
Kein Gegenbeispiel für wallclock direkt/indirekt, gestellte_uhr, trips_pfad, user_id; repo_path-Umbau (Zuweisungen einmal sammeln) ist reihenfolgegleich. Auflagen:
1. **thunder Regel D (S2):** Der Wortfilter läuft als `re.compile(..., re.IGNORECASE)` auf dem **Rohtext**, nie als Teilstring auf
   NFKC-/casefold-Text: `ı` (U+0131) trifft die heutige Regex, eine casefold-Suche verfehlt es. Der Prototyp sucht bereits auf
   Rohtext. Alle fünf Alternativen abdecken (`1:1` hat kein Wort). NFKC gilt nur für Bezeichner.
2. **user_id:** Filternamen zur Laufzeit aus `_baue_ziel_register()` nehmen, nie als feste Liste.
3. **Je Scanner ein gepflanzter Verstoß**, den der gefilterte Lauf findet, plus ein NFKC-Bezeichner-Fall; Mutation „Filter zu streng“ ⇒ rot.
4. **Parsebarkeit:** roter Befund (nicht Warnung) für SyntaxError, ValueError (Nullbytes), UnicodeDecodeError, OSError; in **S1**, an
   `scan_for_hardcoded_repo_paths` (parst ohnehin alles; fängt heute ValueError nicht ab). S1 hat damit 6 Dateien: in der Spec
   begründen oder user_id nach S2 ziehen (Empfehlung: user_id nach S2, dann S1 = 5 Dateien).
5. **Cache:** Aufrufer erhalten eine Liste (Vergleiche mit `== []`), je Aufruf eine Kopie. Eigene `xdist_group` je Datei ist laut Prüfung
   erlaubt (keine Ratsche dagegen, `@` im Namen verboten: `tests/conftest.py:909-958`) und für die Cache-Wirkung nötig: **ja, für
   wallclock und gestellte_uhr** (Doppelläufe) und thunder (S2).
Damit ist die offene Frage zu `xdist_group` entschieden. Scheiben-Schnitt neu: S1 = Helfer, wallclock, gestellte_uhr, trips_pfad,
repo_path (nur Parsebarkeit); S2 = thunder, repo_path (Tempo), user_id; S3 = Wartezeiten.
