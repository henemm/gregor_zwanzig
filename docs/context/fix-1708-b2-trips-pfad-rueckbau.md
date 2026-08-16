# Context: fix-1708-b2-trips-pfad-rueckbau

Issue #1708, Scheibe B2. Erhoben 2026-08-16 durch drei parallele Explore-Agenten,
Befunde am Code bzw. am Testlauf gemessen (nicht aus Dokumentation abgeleitet).

## Request Summary

Der Pfad `data/users/<uid>/trips/<id>.json` ist tote Ablage (seit #1250 Scheibe 7a,
ADR-0023). Scheibe A hat den Produktivcode gesaeubert und einen Quelltext-Waechter
gebaut. B2 soll den Rest raeumen: `get_trips_dir()` aus `src/app/loader.py` entfernen,
die verbliebenen Testaufrufer umstellen, die eine Waechter-Ausnahme streichen.

## Ausgangslage, gemessen

`uv run pytest tests/test_trips_path_revival_guard.py` = 17 Tests gruen. Der Scanner
findet im gesamten Produktivbestand (91 Go-Dateien, 202 Python-Dateien) **genau einen**
Fund: `src/app/loader.py::get_trips_dir::0` (Zeile 1163) — deckungsgleich mit der einen
Ausnahme. Die Go-Seite ist bereits leer.

`get_trips_dir()` hat **keinen Produktivaufrufer**. Belegt:
`grep -rn "get_trips_dir" src/ api/ internal/ cmd/ scripts/ .claude/` liefert nur die
Definition. Positivkontrolle mit demselben Befehl auf `get_briefings_dir`: 12 Treffer,
echte Aufrufer u. a. in `src/services/trip_report_scheduler.py:315`,
`src/services/preview_service.py:18`, `api/routers/validator.py:23`. Die Suchmethode ist
nicht blind.

`get_trips_dir()` (`loader.py:1155`) und `get_briefings_dir()` (`loader.py:1166`)
unterscheiden sich **ausschliesslich** im Verzeichnisnamen: gleiche Signatur, gleicher
Default, kein `mkdir`, kein Seiteneffekt. Die im Docstring behauptete Rolle „historical
per-user directory bootstrap" hat kein Code-Gegenstueck — der Bootstrap sass in Go
(`internal/store/user.go`, in Scheibe A bereinigt).

## Related Files

| Datei | Relevanz |
|---|---|
| `src/app/loader.py:1155` | `get_trips_dir()` — das Ziel. Schema-relevante Datei, loest Backup-Hook aus |
| `tests/test_trips_path_revival_guard.py:91` | die eine `KNOWN_VIOLATIONS`-Ausnahme; :409 Stale-Ratsche; :422 Obergrenze |
| `tests/test_briefing_route_cutover.py` | K1 — die legitime Ausnahme, **darf nicht umgebogen werden** |
| `tests/tdd/test_issue_731_unified_commands.py:403` | **einziger inhaltlicher Fund** — Zusicherung am toten Pfad |
| `tests/tdd/test_issue_1001_telegram_bubbles.py:858` | echter Fixture-Schreiber, aber heute uebersprungen |
| `tests/conftest.py:81` | spiegelt `data/users/*/trips/*.json` -> `briefings/` fuer `real_data_root`-Tests |
| `tests/test_stillgelegte_testdateien.py:108` | B1-Sonde AC-6, nimmt den Wegfall bereits vorweg |

## Klassifizierung der 17 Testdateien

Positivkontrolle: `grep -rn 'get_trips_dir' tests/` trifft in allen 17 Dateien.
**9 Dateien rufen echt auf**, 7 nennen den Namen nur in Kommentar/Docstring/Variablenname.
Der Waechter-Kommentar behauptet „12 Testdateien" — gemessen sind es 9.

### K1 — echte Fixture-Schreiber am toten Pfad (2 Dateien)

- **`tests/test_briefing_route_cutover.py`** (Aufrufe :110, :130, :149, :171) — laeuft
  gruen, 7 Tests, keine Marker, keine Skips, nicht in `ci_tdd_excludes.txt`.
  🔴 **Umbiegen auf `get_briefings_dir()` waere hier falsch.** :130/:149/:171 legen
  absichtlich eine abweichende Alt-Version am Legacy-Pfad an, um zu beweisen, dass
  `load_all_trips`/`load_trip` sie ignorieren und `save_trip` sie byte-unveraendert laesst
  (AC-25/AC-26 des Cutovers). Umbiegen zerstoert die Aussage. Richtig: literale
  Pfadbildung ueber `loader.get_data_dir(uid) / "trips"`. Nur :110 ist ein Ausreisser —
  dort wird `briefings/` umstaendlich als `get_trips_dir(...).parent / "briefings"`
  konstruiert und kann direkt auf `get_briefings_dir(uid)`.
- **`tests/tdd/test_issue_1001_telegram_bubbles.py:858`** — echter Schreiber
  (`mkdir` + `write_text`). Umbiegen ist hier korrekt. Laeuft heute **nicht**:
  `@pytest.mark.skipif(not _LIVE_CREDS_AVAILABLE)` (:881). Liefe er, waere er
  vermutlich schon rot, weil der Leser aus `briefings/` liest.

### K2 — greift ins Leere (7 Dateien, 10 Stellen)

Alle laufen unter der autouse-Isolation (`tests/conftest.py:120 _isolate_data_root`) in
einer leeren tmp-Wurzel; `save_trip` schreibt seit #1250 nach `briefings/`. Diese Zeilen
finden nie etwas.

`test_issue_731_unified_commands.py:184,403` · `test_issue_612_report_on_demand.py:155,293,327` ·
`test_inbound_gate_errors.py:48` · `test_trip_command_processor.py:73` ·
`test_issue_882_pause_skip.py:69` · `test_feature_656_radar_nowcast.py:188,215,302` ·
`test_feature_660_convective_stage.py:234` · `test_issue_1001_telegram_bubbles.py:437`

🔴 **Genau eine dieser Stellen hat Substanz: `test_issue_731_unified_commands.py:403`** —
`assert not (trips/<id>.json).exists()` soll beweisen, dass WEITER nicht nach
`users/default/` schreibt. Am toten Pfad kann die Zusicherung **nie** fehlschlagen; ein
echtes Leck nach `users/default/briefings/` bliebe ungefangen. Umbiegen auf
`get_briefings_dir()` ist dort eine **Verhaltensaenderung und kann rot werden**.

Alle uebrigen sind No-Op-Aufraeumung (teardown, `rmtree`, `finally:`) — ersatzlos streichen
oder mitziehen, dann raeumen sie tatsaechlich auf.

### K3 — nur Kommentar/Variablenname (7 Dateien, 0 Aufrufe)

`test_stillgelegte_testdateien.py` · `test_trips_path_revival_guard.py` ·
`test_issue_1133_testdata_cleanup.py` · `test_loader_display_config_default.py` ·
`test_issue_818_radar_briefing_integration.py:97` ·
`test_issue_822_radar_nowcast_segment.py:101` · `test_bundle_791_847_844_alerts.py:72`

Die letzten drei stehen in `.github/ci_tdd_excludes.txt` (auf `origin/main` nachgeprueft,
Zeilen 61/77/78) — sie laufen derzeit nicht auf CI. Fuer B2 ohne Belang, da ohne Aufruf.
**Alle 9 echt aufrufenden Dateien laufen auf CI.**

Gegenprobe zur Fremdmessung einer Parallelsitzung (#1697): `818`/`822` legen ihre Trips
aktiv per `_save_trip_direct`/`save_trip` an, und `trips_dir` ist dort ein reiner
Variablenname auf `get_briefings_dir(user_id)` (818:102, 822:105). Kein Widerspruch.

## Risks & Considerations

### R1 — Der Waechter verliert seine einzige Positivkontrolle am echten Bestand

**Der wichtigste Befund.** Heute ist `test_ac7_known_violations_only_shrink` (:409-419)
der einzige Test, der beweist, dass der Scanner auf **echten** Dateien ueberhaupt etwas
zurueckliefert — er verlangt, dass der Ausnahme-Schluessel in `found` auftaucht. Alle
anderen Positivkontrollen (AC-1/AC-2/AC-3, :248-318) laufen gegen **synthetische**
Quellstrings; AC-6 prueft nur Pfad-Mitgliedschaft.

Wird die Ausnahme in B2 gestrichen, ist `KNOWN_VIOLATIONS` leer, `stale` trivial `[]` —
und **kein Test misst den Scanner mehr am echten Bestand**. Ein Scanner, der auf realen
Dateien lautlos nichts mehr liefert (verschluckter Lesefehler, kaputte Pfadaufloesung),
waere danach vollstaendig gruen. Das ist dieselbe Fehlerklasse, die #1708 ueberhaupt
erzeugt hat.

Erschwerend: nach B2 gibt es im Produktivbestand **null** `trips`-Fundstellen. Die
Hausnorm fuer Trefferkraft-Nachweise (`tests/test_success_status_guard.py:1762`,
`tests/test_resolution_loss_guard.py:818`) fuehrt eine spec-verankerte Liste **erwarteter
echter Fundstellen** — die gibt es hier per Definition nicht mehr. Der Nachweis muss
anders gebaut werden, z. B. Scanner gegen eine reale Datei im Dateisystem statt gegen
synthetische Strings.

### R2 — Ausnahme und Funktion muessen im selben Commit fallen

`test_ac7_known_violations_only_shrink` wird rot, sobald der Scanner die gelistete Stelle
nicht mehr findet. `get_trips_dir()` entfernen **und** `KNOWN_VIOLATIONS` leeren gehoeren
in einen Commit. Die Obergrenze `<= 1` (:422) bleibt bei 0 gueltig, keine Anpassung noetig.
`CARRIER_FILES` bleibt ebenfalls unveraendert: der Eintrag `src/app/loader.py` belegt nur,
dass `src/` gescannt wird — Positivkontrolle: `internal/store/trip.go` steht dort seit
Scheibe A ohne Funde und der Test ist gruen.

### R3 — `tests/conftest.py:81` haengt am Verzeichnisnamen, nicht an der Funktion

Die Session-Fixture spiegelt `data/users/*/trips/*.json` -> `briefings/` fuer
`real_data_root`-Tests. Wird der Quell-Fixture-Baum `tests/fixtures/data_root/users/*/trips/`
angefasst, laufen `test_issue_363_signal_telegram_preview` und
`test_issue_1001::TestAC7PreviewEndpointBubbles` ins 404. **Nicht Teil von B2**, aber die
Spiegelung darf nicht versehentlich mitgerissen werden.

### R4 — Zuschnitt und LoC

Der mechanische Teil ist klein (9 Dateien, ueberwiegend Zeilenloeschung). Teuer sind zwei
Nachweise: der Trefferkraft-Ersatz (R1) und die Frage, ob `test_issue_731:403` nach dem
Umbiegen rot wird — das waere ein echter Produktivbefund und muesste eigenstaendig
behandelt werden. LoC-Limit 250, Nachweis erfahrungsgemaess teurer als der Mechanismus.

## Dependencies

- **Upstream:** `get_data_dir()` (`loader.py:1133`, oeffentlich) — bleibt und traegt die
  testlokale Legacy-Pfadbildung fuer `test_briefing_route_cutover.py`.
- **Downstream:** kein Produktivcode. Nur die 9 Testdateien und der Waechter.
- **Parallelsitzung:** `gregor-zwanzig-dd` (#1697) aendert eine Zeile in
  `test_issue_818_radar_briefing_integration.py` (`test_ac7_mandantentrennung_isolated`)
  und holt `818`/`822` aus `ci_tdd_excludes.txt`. Abgesprochen: diese Zeile bleibt
  unangetastet; wer zuerst fertig ist, mergt, der andere rebased.

## Existing Specs

- `docs/specs/modules/fix_1708_a_trips_pfad_waechter.md` — Scheibe A, Waechter-Bauart
- `docs/specs/modules/fix_1708_b1_tote_fixture_befunde.md` — Scheibe B1
- `docs/adr/` — ADR-0023 (Cutover auf `briefings/`)

## Analysis

### Type

Bug — stillgelegte Zusicherungen und toter Code, kein neues Verhalten.

### R4 aufgeloest: `test_issue_731_unified_commands.py:403` traegt am lebenden Pfad

**Gemessen, nicht vermutet.** Betroffen ist `TestAC10UserIsolation.test_weiter_only_affects_own_trip`
(:392-405): zwei reale Nutzer A/B bekommen je einen deaktivierten Trip, `WEITER` laeuft als
Nutzer A durch `TripCommandProcessor().process(...)`, danach wird geprueft, dass
`users/default/` unberuehrt bleibt.

| Messung | Ergebnis |
|---|---|
| A — Bestand (`get_trips_dir`) | gruen |
| B — umgestellt auf `get_briefings_dir` | gruen, Gesamtdatei 18/18 |

Gegenprobe gegen falsches Gruen, zweifach: (1) Assertion umgedreht zu
`assert default_trip.exists()` auf dem briefings-Pfad -> **rot**, das Verzeichnis ist
wirklich leer und kein Vergleichsfehler. (2) Ad-hoc-Nachstellung ausserhalb pytest zeigt,
dass `briefings/<UserA>` und `briefings/<UserB>` nach dem `WEITER`-Aufruf **existieren**,
`briefings/default` und die Legacy-`trips/` dagegen nicht. Der Testkoerper erreicht den
echten Schreibpfad; die Negativpruefung ist eine echte Kontrollgruppe neben zwei
tatsaechlich beschriebenen Verzeichnissen.

**Folge:** Kein Cross-User-Leck. Das Umbiegen ist gefahrlos und macht die Zusicherung
erstmals wirksam — vorher bewachte sie ein Verzeichnis, in das seit #1250 Scheibe 7a
niemand mehr schreibt. Kein eigenes Issue noetig; die Reparatur ist Teil von B2.
Die im Planungsentwurf vorgesehene Rueckfalloption (`xfail` + eigenes Issue, falls die
Umstellung rot wird) entfaellt damit ersatzlos.

### R1 geloest: Trefferkraft-Nachweis ueber umgebogene Scan-Wurzel

**Gewaehlter Ansatz:** Der Test legt in `tmp_path` zwei echte Dateien mit echten
Verstoessen an — `internal/store/user.go` in Slice-Form und `src/app/loader.py` in
Divisions-Form — biegt `REPO_ROOT` per `monkeypatch.setattr` auf diesen Baum um, ruft
`_all_violations()` und erwartet **beide** Schluessel.

Traegt, weil `REPO_ROOT` ein Modul-Global ist (:72) und `_go_scan_files()`/`_py_scan_files()`
ihn bei **jedem Aufruf** als Global aufloesen (`REPO_ROOT / root_name`, :181/:194) — nicht
als Signaturparameter, aber deshalb per `monkeypatch` umbiegbar, ohne den Scanner
anzufassen.

Mutationsprobe, alle drei gefangen:

| Verfaelschung | Wirkung |
|---|---|
| `_py_scan_files()`/`_go_scan_files()` liefern `[]` | Fund fehlt -> rot |
| Wurzel-/Join-Berechnung kaputt (hartkodiert statt `REPO_ROOT`) | Fund fehlt -> rot |
| `_is_finding` immer `False` / Regex kaputt | Fund fehlt -> rot |

Prueft an echten Bytes, echter Wurzelaufloesung, echter Erkennung — Pruefort = Wirkort.
**Zugewinn gegenueber dem Ist-Zustand:** Die verlorene Kontrolle bewies nur die
Python-Seite (die Go-Seite war produktiv schon leer). Der neue Nachweis deckt beide
Sprachpfade ab.

Verworfene Ansaetze: **B** (Scanner gegen echte Repo-Datei mit bekanntem Inhalt) ist nach
B2 gegenstandslos — es gibt dann keine `trips`-Fundstelle mehr, und die abgeschwaechte
Variante dopplet nur `test_ac6_carrier_files_are_within_scan_area` (:390-401).
**C** (Datei waehrend des Laufs ins Repo schreiben) rekonstruiert live im Produktivbaum
genau das Muster, das der Waechter bekaempft, und ist bei parallelen Worktrees riskant —
ohne Vorteil gegenueber `tmp_path`. **D** (`get_trips_dir()` behalten) loest genau das ein,
was der Ausnahme-Eintrag als „KEINE Dauerausnahme" (:93) ausschliesst.

### Affected Files

| Datei | Aenderung | Beschreibung |
|---|---|---|
| `src/app/loader.py` | MODIFY | `get_trips_dir()` (:1155-1163) entfernen |
| `tests/test_trips_path_revival_guard.py` | MODIFY | `KNOWN_VIOLATIONS` leeren; Trefferkraft-Nachweis ergaenzen |
| `tests/test_briefing_route_cutover.py` | MODIFY | :110 -> `get_briefings_dir`; :130/:149/:171 auf literale Pfadbildung ueber `get_data_dir(uid) / "trips"` |
| `tests/tdd/test_issue_731_unified_commands.py` | MODIFY | :403/:405 auf `get_briefings_dir` (macht die Zusicherung wirksam); :184 Aufraeumung |
| `tests/tdd/test_issue_1001_telegram_bubbles.py` | MODIFY | :858 Fixture-Schreiber umbiegen; :437 Aufraeumung |
| `tests/tdd/test_issue_612_report_on_demand.py` | MODIFY | :155/:293/:327 Aufraeumung, Import |
| `tests/tdd/test_feature_656_radar_nowcast.py` | MODIFY | :188/:215/:302 `finally:`-Aufraeumung |
| `tests/tdd/test_inbound_gate_errors.py` | MODIFY | :48 teardown, Import |
| `tests/tdd/test_trip_command_processor.py` | MODIFY | :73 teardown, Import |
| `tests/tdd/test_issue_882_pause_skip.py` | MODIFY | :69 rmtree, Import |
| `tests/tdd/test_feature_660_convective_stage.py` | MODIFY | :234 `finally:`-Aufraeumung |

### Scope Assessment

- Dateien: 11 (1 Produktiv, 10 Test)
- Geschaetzte LoC: ~115 im ungünstigen Fall (Wegfall ~-10 · 9 Testdateien ~35 ·
  Ausnahme + Docstring ~10 · Trefferkraft-Nachweis ~30, doppelt gerechnet ~60)
- Budget 250 — **keine weitere Teilung noetig**
- Risiko: **LOW**. Kein Produktivverhalten aendert sich; `get_trips_dir()` hat keinen
  Produktivaufrufer. Die einzige inhaltliche Zusicherung wurde gemessen und traegt.

### Reihenfolge (ein Commit)

1. 9 Testdateien umstellen — **muss vor oder mit** der Entfernung, sonst bricht die
   Testsammlung an `NameError`/`ImportError`
2. `get_trips_dir()` entfernen
3. `KNOWN_VIOLATIONS` leeren
4. Trefferkraft-Nachweis ergaenzen

(2)+(3)+(4) muessen atomar sein (R2), sonst wird `test_ac7_known_violations_only_shrink`
zwischenzeitlich rot und es entstuende eine Luecke, in der kein Test echte Dateien prueft.
Da alles in ein Commit passt, ist das die einfachste Garantie.

### Open Questions

Keine offenen technischen Fragen. Beide Kernfragen sind empirisch beantwortet.

## Nebenbefunde (nicht Teil von B2)

- `internal/store/briefing_subscription.go:12,15,24` — Kommentare verweisen auf das
  entfernte `TripsDir()`. Sachlich veraltet, ohne Laufzeitwirkung.
- `internal/scheduler/selftest.go:42` — Variable heisst `tripsDir`, zeigt auf `briefings`.
- `tests/test_stillgelegte_testdateien.py:116-118` — AC-6-Docstring begruendet die
  Methodenwahl mit „conftest.py ruft an mehreren Stellen get_trips_dir()"; das stimmt
  nicht (`grep` liefert dort nichts). Methodenwahl bleibt gueltig, Begruendung ist falsch.
