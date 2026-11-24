# Context: rework-3317-wartezeiten

## Request Summary
Scheibe 3 zu #3279 (Teil von #1196): fünf Testdateien mit echten Wartezeiten und vielen Subprozessen beschleunigen. Abschluss: Vorher/Nachher-Zeit je Datei, keine Zusicherung geschwächt, Mutations-Gegenprobe je umgebautem Test. Intake-Summe 3 (Analyse kurz).

Stand der Befunde: durch Codelesen gewonnen. Die Einsparungen sind **Ansätze, noch nicht gemessen oder ausprobiert**.

## Related Files
| Datei | Befund |
|---|---|
| `tests/refactor/test_epic_129a_3_ui_removed.py` (Z. 146) | `test_ac7_collection_clean`: `uv run pytest tests/ --collect-only`, Voll-Sammlung; prüft Exit 0 und kein „error during collection" |
| `tests/tdd/test_pytest_collection_and_timeout_safety.py` | Modul-Fixtures `default_/email_/staging_/live_collect` = je eine Voll-Sammlung; dazu 3 Teil-Sammlungen (`-o addopts=`), eine zweite Voll-Sammlung (mtime-Test, Z. 373) und ein echter 30-s-Hänger (Z. 640) |
| `tests/tdd/test_dwd_thunder_parallel_fetch.py` (Z. 634) | `..._endet_nach_etwa_10s`: wartet den unveränderten Default `THUNDER_REQUEST_TIMEOUT` (10 s) real ab |
| `tests/tdd/test_radar_nowcast_segment_wanduhr_unabhaengig.py` (Z. 145) | je Messfall ein Kindprozess je Uhrzeit, nacheinander; Referenzzeit = erste Uhrzeit, wird zusätzlich ein zweites Mal gemessen |
| `tests/tdd/test_einstellung_gleich_mail_validatoren.py` | ca. 169 Textstellen `_lauf(`; je Test Kopie aller Hooks + `git init`, je Lauf ein neuer Python-Prozess |
| `tests/helpers/mail_lang_fixture.py` (Z. 151) | `validator_lauf`, der Prozessstart; weitere Nutzer vor Änderung prüfen |
| `tests/helpers/wanduhr_matrix.py` | `lauf_bei_uhrzeit`, `matrix_differenz`; weitere Nutzer: `test_prozesszonen_schalter`, `test_wanduhr_matrix`, `test_radar_onset_threshold_variance`, `test_fixture_wallclock_ratchet`, `tests/tdd/conftest.py` |
| `.claude/hooks/briefing_mail_validator.py`, `email_spec_validator.py` | Prüflinge, `main()` mit `sys.exit`; dürfen NICHT geändert werden |
| `src/providers/dwd.py` (Z. 162, 534, 615-634) | Timeout-Verdrahtung `_thunder_request` -> `capped_timeout_or_raise(base_timeout=THUNDER_REQUEST_TIMEOUT)`; unverändert lassen |

## Ansätze je Datei (für /20-analyse zu prüfen)
1. **Sammlung:** eine echte Standard-Sammlung, in der ein Plugin ausgewählte UND abgewählte Items mit Markern mitschreibt; `email`/`live`/`staging`/Gesamt daraus ableiten. Offen: `-m email` auf der Kommandozeile überschreibt die addopts-Auswahl; ob dieser Weg selbst zugesichert ist, entscheiden. mtime-Nachweis: vorher/nachher um dieselbe Sammlung legen statt zweiter Lauf; Achtung `xdist_group("echtdaten")`.
2. **`-n 4 --dist loadgroup` (CI):** Modul-Fixtures entstehen je Worker neu, die Datei hat (bis auf den Echtdaten-Test) keine Worker-Gruppe. Eigene `xdist_group` nach Muster Scheibe 1 (`docs/specs/modules/rework_3279_scanner_ratschen_tempo_s1.md`) erwägen.
3. **30-s-Hänger:** wirksamen Wert 30 aus der echten Konfiguration im Kindprozess belegen (z. B. Hook `pytest_timeout_set_timer`) und den Abbruch mit kurzem Wert belegen. Beide Zusicherungen nötig.
4. **`test_ac7`:** prüft dasselbe wie `test_full_suite_collection_still_exits_zero`; Unterschied `uv run`/`tests/`. Zusammenlegen nur, wenn eine Mutation (kaputter Import) dort nachweislich rot wird.
5. **DWD 10 s:** Konstante 10.0 prüfen plus den beim echten Request wirksamen Lese-Timeout ohne Patch mitschreiben. Das Verhalten (Abbruch am Timeout, kein Retry, Zelle None) prüft der Schwestertest mit 2 s (Z. 351). Mutationen: Konstante 30; Literal statt Konstante; Retry an.
6. **Radar:** Referenz aus der Matrix wiederverwenden; frische Prozesse gleichzeitig statt nacheinander (ein Prozess je Datenpunkt bleibt Pflicht, siehe Docstring `wanduhr_matrix`). Wirkung unter `-n 4` auf 4 Kernen messen.
7. **Mail-Validatoren:** Hook-Kopie + `git init` je Modul statt je Test teilen und/oder Validator im Prozess ausführen. Risiko: Modulzustand (`sys.path`, Sprache, Umgebung) sickert zwischen Läufen; mindestens ein echter Prozesslauf je Validator muss bleiben. Zeitanteile (Kopie, git, Import, Mailbau) erst messen.

## Existing Patterns
- Scheibe 1 (#3279): Vorfilter, `functools.cache` je Regel, eigene Worker-Gruppe, Mutations-Gegenprobe je Ratsche.
- Testbefehle: nur benannte Dateien (#1477); Live-/Staging-Marker nur sammeln, nie ausführen.

## Dependencies
- Upstream: pytest, pytest-timeout, pytest-xdist, freezegun, httpx.
- Downstream: CI-Check `test`; Laufzeit zählt dort unter `-n 4`.

## Existing Specs
- `docs/specs/modules/rework_3279_scanner_ratschen_tempo_s1.md`, `rework_1210_testsuite_s1.md`, `rework_1211a/b/c_*`, `fix_2240_rolling_trip_test_versandsperre.md`, `fix_2554_dwd_gewitterabruf_budget.md`, `fix_3217_flaky_thunder_ac3.md`, `feat_3047_einstellung_gleich_mail_pruefkatalog.md`

## Ausgangsmessung (24.11.2026, Mac, seriell, Stand 5a442bd41)
Gesamtlauf der fünf Dateien: 930,6 s; 187 grün, **1 rot**, 1 übersprungen, 4 abgewählt. Je Datei Summe der 45 langsamsten Phasen (**Untergrenze**, kein Vollwert; für Vorher/Nachher je Datei einzeln messen, am besten auch unter `-n 4`):

| Datei | Summe Top-45 | größte Posten |
|---|---|---|
| `test_pytest_collection_and_timeout_safety` | 258 s | Setup 90 + 83 s, mtime-Zweitlauf 43 s, Hänger 31 s |
| `test_einstellung_gleich_mail_validatoren` | 188 s | viele Fälle 7-12 s (Top-45 schneidet hier viel ab) |
| `test_dwd_thunder_parallel_fetch` | 73 s | ac1 40,8 s (Timeout, rot), 2x ac3 je ca. 10,6 s |
| `test_radar_nowcast_segment_wanduhr_unabhaengig` | 64 s | 33,8 + 31,4 s |
| `test_epic_129a_3_ui_removed` | 45 s | ac7 45,5 s |

Auch `test_ac3_haengender_download_...` (Timeout 2 s) dauert 10,5 s, obwohl die Zusicherung nur `dauer <= 5 s` misst: Rest außerhalb der Messung, vermutlich Raster-Vorab-Erzeugung (ungeprüft).

Serverwerte aus dem Issue: 30 / 166 / 200 / 10,8 (nur der eine DWD-Test) / 15-18 s. Zeitanteile von `validator_lauf` noch NICHT gemessen: das Kopieren von `.claude/hooks` per Bash hat das bash_gate abgewiesen; über den Testhelfer selbst messen.

## Offene Befunde vor Beginn
1. **Lokal rot, unverändert von uns:** `test_dwd_thunder_parallel_fetch::test_ac1_...` endet in 3 von 3 Läufen (Gesamtlauf + 2x Datei allein) am 40-s-Timeout, trotz Budget 8 s; Spur endet in `src/providers/dwd.py:857`. Im CI-Lauf 45372227336 nicht unter den Fehlern. Ursache unbekannt (lokal/macOS oder echter Fehler); klären, bevor die Datei umgebaut wird. Kein offenes Issue per Suche gefunden.
2. **main in CI rot** (Lauf 45372227336, Stand 5a442bd41): einziger Fehler `tests/test_3197_kanal_paritaet.py::test_etappe_3_mail_zeigt_die_neuen_wegpunkt_zeiten` (`'11:20' not in ...`). Gehört nicht zu #3317, blockiert aber den Merge unseres PR; Vermutung Uhrzeitabhängigkeit ungeprüft.

## Risks & Considerations
- Geschwächte Zusicherung durch Ableiten statt echtem Lauf (Sammlung, Timeout, Validator im Prozess).
- Umfang: fünf Dateien plus Helfer; LoC-Grenze 250, bei Überschreitung Scheiben bilden (Validatoren als eigene Scheibe naheliegend).
- Keine Produktdateien ändern.

## Analysis (24.11.2026)

### Type
Feature/Rework (reine Testinfrastruktur, keine Produktdateien).

### Gemessen (Mac, 10 Kerne, Last ca. 2,9; über benannte, danach gelöschte Probe-Datei, Einzelmessungen)
| Frage | Ergebnis |
|---|---|
| `test_dwd...::ac1` lokal rot | `socket.getfqdn("127.0.0.1")` (ruft `HTTPServer.server_bind` auf) dauert hier **35,0 s**; plus 8 s Budget > 40-s-Timeout. Nach vorab ausgelöstem getfqdn: Serverstart 0,0 s, Abruf 8,09 s. Kein Hinweis auf Produktfehler |
| ac1 ohne getfqdn-Anteil | lokal trotzdem rot zu erwarten: `sleep(0.2)` dauerte 0,395 s, nur 8-9 von 12 Zeitpunkten (gefordert >= 10). Ursache der langen Schlafzeit ungeklärt; Schwelle NICHT senken |
| 2-s-Test dauert 10,5 s | vermutlich derselbe getfqdn-Anteil (nicht einzeln gemessen) |
| `test_einstellung_gleich_mail_validatoren` ganz | **455 s**, 147 grün (bisher nur Untergrenze 188 s) |
| Hook-Kopie + `git init` | 0,03 + 0,04 s: Teilen **lohnt nicht**, dieser Teil von Ansatz 7 verworfen |
| Mailbau | 0,07-0,12 s (erster Orte-Bau 2,1 s) |
| `email_spec_validator` | Prozess ca. 1,1 s; im selben Prozess ab 2. Lauf 0,13-0,15 s: Rest (Start + Importe) ca. 0,9 s |
| `briefing_mail_validator` | Prozess 1,9-3,5 s; im selben Prozess ab 2. Lauf noch 1,65-1,76 s. Profil: 1,89 von 1,95 s in der Render-Prüfung `_check_rendered` (echter Chromium), davon 1,77 s in `sync_playwright` `__exit__`/Treiber |
| Läufe in der Datei | ca. 90 Textstellen Trip, 77 Orte (grep, nicht Laufzahl) |

### Entscheidungen je Datei (Vorschlag, Gegenprüfung durch Plan-Agent läuft)
1. **Sammlung:** EINE echte Standard-Sammlung mit Mitschreib-Plugin: `pytest_itemcollected` = Gesamt, `session.items` bei `pytest_collection_finish` = gewählt, je Item Marker. `email`/`live`/`staging`/Gesamt und die 3 Teil-Sammlungen daraus ableiten. Dazu ein echter kurzer `-m <marker>`-Lauf auf wenigen Dateien (Beleg: Kommandozeile ersetzt addopts-Auswahl). Vorher prüfen, ob ein `conftest.py` auf markexpr reagiert. mtime-Nachweis um dieselbe Sammlung legen. Worker-Gruppe: eigene oder ganze Datei in `echtdaten`, in der Spec entscheiden.
2. **30-s-Hänger:** wirksamen Wert 30 im Kindprozess aus der echten Konfiguration belegen UND Abbruch mit kurzem Wert belegen.
3. **`test_ac7`:** streichen zugunsten `test_full_suite_collection_still_exits_zero`, nur wenn die Mutation (kaputter Import) dort rot wird.
4. **DWD 10 s:** Konstante 10.0 plus Aufzeichnung des am echten httpx-Request wirksamen Lese-Timeouts; Verhalten prüft der 2-s-Test. Dazu `server_bind` des Testservers ohne getfqdn (nur Testdatei).
5. **Radar:** Referenzmessung aus der Matrix wiederverwenden (spart 1 von 5 bzw. 1 von 6 Läufen); Nebenläufigkeit nur, wenn unter `-n 4` gemessen schneller.
6. **Validatoren (eigene Scheibe B):** vorgewärmter Fork-Server in `validator_lauf` (Importe einmal, je Lauf ein echter geforkter Prozess, Validator frisch per `runpy`). Erwartung grob 455 -> 300 s, NICHT ausprobiert. Chromium bleibt echt; mindestens ein unveränderter Prozesslauf je Validator bleibt. Verworfen: Validator im Testprozess (Modulzustand sickert), Render-Prüfung abschalten (schwächt).

### Affected Files
| File | Change | Scheibe |
|---|---|---|
| `tests/tdd/test_pytest_collection_and_timeout_safety.py` | MODIFY | A |
| `tests/refactor/test_epic_129a_3_ui_removed.py` | MODIFY | A |
| `tests/tdd/test_dwd_thunder_parallel_fetch.py` | MODIFY | A |
| `tests/tdd/test_radar_nowcast_segment_wanduhr_unabhaengig.py`, `tests/helpers/wanduhr_matrix.py` | MODIFY | A |
| `tests/helpers/mail_lang_fixture.py` (evtl. neuer Helfer) | MODIFY/CREATE | B |

### Scope / Risiko
Schätzung: Scheibe A 5 Dateien, +150/-110 LoC; Scheibe B 1-2 Dateien, +80/-10. Risiko mittel: still geschwächte Zusicherung; Schutz ist die Mutations-Gegenprobe je Test.

### Dependencies
Nur vorhandene (pytest, pytest-timeout, pytest-xdist, httpx); keine neuen.

### Open Questions
- [ ] CI auf main rot (zwei Läufe auf 5a442bd41); Ursache in dieser Sitzung nicht ausgewertet, kein Issue gefunden. Blockiert den Merge, vor dem PR klären.
- [ ] Worker-Gruppe der Sammlungs-Datei (siehe Gegenprüfung, erst messen).
- Explore-Teilagenten ausgelassen (Context lag vor, Intake „Analyse kurz"); Gegenprüfung per Plan-Agent, s. u.

### Gegenprüfung (Plan-Agent, nur Codelesen) und maßgeblicher Stand
Geht bei Widerspruch den Entscheidungen 1-6 oben vor.
1. **Sammlung:** Das Mitschreib-Plugin läuft in EINEM echten Subprozess (`-p`), nie im Testprozess: dort gälten die CI-Optionen (`--ignore` aus `.github/ci_tdd_excludes.txt`), die Zahlen wichen ab. Exit 0 und „kein ERROR" dieses Laufs bleiben zugesichert. Beleg-Lauf mit echtem `-m email`, `-m live` UND `-m staging` auf je einer Datei ist Pflicht (Ableitung prüft sonst nicht, ob pytest `-m` richtig auswertet). Kein conftest wertet markexpr aus; `tests/conftest.py:907` setzt nur `xdist_group`.
2. **30-s-Hänger:** heutiger Test belegt nur `returncode != 0` (jeder Wert unter 60 s bestünde); der Ersatz mit zwei Teilen ist strenger.
3. **DWD:** Spion durchreichend an `httpx.Client.send` (aufgelöster Lese-Timeout), Server antwortet sofort, Budget weit weg, da `capped_timeout_or_raise` sonst deckelt. Mutationen: Konstante 30; Literal statt Konstante in `dwd.py:628` (fängt nur der Spion); Retry an (fängt der 2-s-Test). ac1 gilt lokal NICHT als repariert.
4. **Radar:** Referenz wiederverwenden: der Test sichert Reproduzierbarkeit der Referenz nicht eigens zu (Testdatei gelesen).
5. **Validatoren (Scheibe B):** nicht im selben PR. Zuerst Versuch mit Messung; Agent erwartet eher 350-390 s statt 300 s (beides ungemessen). Fallen: `os.environ` komplett ersetzen, `chdir` in die Kopie, Browser nie im Elternprozess, Server ohne Threads (macOS-fork), je xdist-Worker ein Server, Aufräumen; `src`-Module kämen aus dem Original statt aus der Kopie. Bringt er unter ca. 25 %, begründet belassen (Abschlusskriterium im Issue erlaubt das).
6. **Reihenfolge Scheibe A:** ac7 → DWD → Sammlung/Hänger → Radar, je mit Vorher/Nachher-Zeit und Mutations-Gegenprobe.
7. Worker-Gruppe: CI läuft `-n 4 --dist loadgroup`. Vorgabe ganze Datei in `echtdaten` (genau eine Sammlung samt mtime-Nachweis), falls die Datei danach kurz ist (Richtwert 20 s); sonst eigene Gruppe plus eigene Sammlung für den mtime-Test.

## Stand nach Spec-Freigabe (24.11.2026)
- Spec freigegeben; Folge-Issue Scheibe B: #3331 (nicht Teil dieses PR). Spec nicht mehr ändern (Briefing-Hash).
- Maßgeblich ist die Spec: Literal 10.0 an der Verdrahtung in `dwd.py` fängt voraussichtlich nur der 2-s-Test, Literal 30.0 der Spion (Punkt 3 der Gegenprüfung ist hier ungenau). Die 10,5 s des 2-s-Tests sind UNGEKLÄRT (nicht getfqdn: der Serverstart liegt in der Messung).
- Branch `rework-3317-wartezeiten`, Worktree-Ordner heißt `rework-3279-testsuite-tempo`.
- Vor dem PR zu klären: main in CI rot (`test_3197_kanal_paritaet`).

## Stand nach TDD RED (24.11.2026): Vertrag für die Umsetzung
Beleg: `docs/artifacts/rework-3317-wartezeiten/test-red-output.txt` (8 failed, 3 errors, 1 passed; nur die neuen/erweiterten Tests per `-k`). Die 3 errors sind die AC-2-Fälle (`fixture 'sammlung' not found`).
- **Sammlung** (`test_pytest_collection_and_timeout_safety.py`): Modul-Fixture `sammlung` mit `.gesamt` (Kennungen inkl. abgewählter) und `.mit_marker(name)` (dazu gewählt, Exit, Ausgabe, mtime vorher/nachher nach Bedarf). Alle Nutzer von `sammlung` (auch mittelbar) in EINER `xdist_group`. `default_/email_/staging_/live_collect` werden daraus abgeleitet; werden sie entfernt, die Parameter in `test_genau_eine_voll_sammlung_je_dateilauf` durch `sammlung` ersetzen. Im Ausweichfall (zwei Sammlungen) ist deren Erwartung 1 anzupassen; der Zähler läuft je Worker.
- Falle: `_XdistGruppenSuffix` in `tests/conftest.py` hängt `@<gruppe>` an Kennungen; prüfen, ob der Sammel-Kindprozess unter `-n 4` die Worker-Umgebung (`PYTEST_XDIST_WORKER`) erbt und Kennungen verfälscht.
- **Hänger**: `_wirksames_limit(konfiguration, tmp_path) -> float` (Kindprozess mit `-c`, Hook `pytest_timeout_set_timer`, `settings.timeout`), `_haenger_lauf(tmp_path, limit_s=, haenger_s=) -> CompletedProcess`. Muster der Timeout-Meldung `Timeout (>3.0s)` ist angenommen, beim Umsetzen an der echten Ausgabe prüfen. Danach `test_timeout_ini_default_kills_hanging_test` entfernen.
- **DWD**: `_Server.server_bind` ohne `getfqdn`. `test_ac3_default_timeout_10s_wirkt_am_gewitter_request` ist schon GRÜN (Ersatz für den 10-s-Test, Schutz sind die vier Mutationen aus AC-5); danach den alten 10-s-Test entfernen.
- **Radar**: `matrix_differenz(datei, uhrzeiten, *, vorhanden=None)` (Uhrzeit -> Messung); der Radar-Test übergibt `{referenzzeit: referenz}`. Zähler belegt heute 2 Starts für die Referenzzeit.
- **ac7**: kein eigener RED-Test, Entscheidung per Mutation (vor UND nach dem Umbau, AC-4).
- Offen für `/50-implement`: Vorher-Messung je Datei (AC-8) gegen Stand `5a442bd41` im selben Zeitfenster wie Nachher; Umfang beachten (RED-Tests bereits +190 Zeilen von ±250, Entfernungen zählen mit).
- Ruff meldet bis zur Umsetzung F821 (`_wirksames_limit`, `_haenger_lauf`): erwarteter RED-Zustand.
