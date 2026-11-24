---
entity_id: rework_3279_scanner_ratschen_tempo_s1
type: refactor
created: 2026-11-24
updated: 2026-11-24
status: draft
version: "1.0"
workflow: rework-3279-testsuite-tempo
tags: [testsuite, ratschen, performance, epic-1196]
---

# Scanner-Ratschen beschleunigen, Scheibe 1 (Bezeichner-Vorfilter und Ergebnis-Cache)

## Approval

- [ ] Approved

## Purpose

Drei Wächter-Tests lesen und parsen den ganzen `tests/`-Baum (1.937 Dateien) und reissen auf dem Mac das globale 30-s-Netz. Diese Scheibe lässt sie nur noch die Dateien parsen, die den gesuchten Bezeichner überhaupt enthalten, und merkt sich das Ergebnis je Prozess, ohne eine Zusicherung zu schwächen. Issue #3279 (Teil von Epic #1196), Scheibe 1 von 3.

## Source

- **File:** `tests/tdd/test_fixture_wallclock_ratchet.py`, `tests/tdd/test_trip_fixtures_laufen_unter_gestellter_uhr.py`, `tests/test_trips_pfad_rueckbau.py`, neu `tests/helpers/bezeichner_vorfilter.py`
- **Identifier:** `scan_wallclock_arrival_fixtures`, `scan_indirekte_wanduhr_fixtures`, `scan_ungestellte_uhr`, `test_no_test_file_still_calls_get_trips_dir`

> **Schicht-Hinweis:** Reine Testinfrastruktur (`tests/`, Doku-Artefakte). Kein Produktcode in Frontend, Go-API oder Python-Core, keine Nutzerdaten, Mandantentrennung und Kanäle sind nicht berührt (Querschnitts-Prüfpunkte entfallen). Keine neue Abhängigkeit (nur stdlib: `unicodedata`, `functools`, `ast`).

## Estimated Scope

- **LoC:** ca. +200/-30 (Grenze ±250)
- **Files:** 5
- **Effort:** medium (Risiko MEDIUM: ein zu strenger Filter macht einen Wächter still blind; daher je Scanner gepflanzter Verstoß und Mutations-Gegenprobe)

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `tests/helpers/bezeichner_vorfilter.py` | CREATE | liest Datei als UTF-8, normalisiert NFKC (ASCII-Kurzweg), sagt, ob notwendige Bezeichner vorkommen; verschluckt keine Lesefehler |
| `tests/tdd/test_bezeichner_vorfilter.py` | CREATE | Verhalten des Helfers plus ausdrückliche Parsebarkeits-Prüfung über jede `.py` unter `tests/` (Wurzel als Parameter) |
| `tests/tdd/test_fixture_wallclock_ratchet.py` | MODIFY | Filter, Cache und `xdist_group` für beide Scanner; eigener Vorab-Filter auf `Waypoint` in der Kandidatenzählung (ab Z. 1315) |
| `tests/tdd/test_trip_fixtures_laufen_unter_gestellter_uhr.py` | MODIFY | Filter `make_trip` UND `save_trip`, Cache, eigene `xdist_group` |
| `tests/test_trips_pfad_rueckbau.py` | MODIFY | Filter `get_trips_dir`; Baumlauf als Funktion mit Wurzel-Parameter herausgezogen |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `unicodedata`, `functools`, `ast` | stdlib | NFKC-Normalisierung, Ergebnis-Cache, Parsen |
| `pytest-xdist` (`--dist loadgroup`) | bestehend (#3209) | je Cache-Datei eine Worker-Gruppe, damit der Cache wirkt |
| `pytest-timeout` | bestehend | globaler `timeout = 30` bleibt, kein Timeout wird angehoben |
| `tests/conftest.py` (Z. 909-958) | bestehend | `xdist_group`-Namen ohne `@`; Gruppe `echtdaten` bleibt unberührt |
| `docs/artifacts/rework-3279-testsuite-tempo/messung_vorher.py` | bestehend | Messwerkzeug für Vorher/Nachher |
| #3316 (Scheibe 2), #3317 (Scheibe 3), #3278, #1199 | Folge-/Nachbar-Issues | Out of Scope, siehe unten |

## Implementation Details

**Filterregel: nur Bezeichner, nie String-Inhalte.** Python normalisiert Bezeichner per NFKC (`ｓｔｒｆｔｉｍｅ` ist derselbe Name wie `strftime`). Der Helfer sucht deshalb im NFKC-normalisierten Text (ASCII-Dateien nehmen einen Kurzweg ohne Normalisierung). String-Inhalte (`"%H:%M"`, Pfade) lassen sich durch Escapes oder Verkettung zerlegen und sind als Filter unzulässig. Der Helfer verschluckt keine Lesefehler; `UnicodeDecodeError`/`SyntaxError` behandelt jeder Scanner wie heute (wallclock und gestellte_uhr überspringen, trips_pfad wird rot).

Filter je Scanner (notwendige Bedingung):

- wallclock direkt: `strftime`
- wallclock indirekt: `Stage` UND mindestens ein Name aus `_ALARMPFADE_INDIREKT` (zur Laufzeit aus der Konstante; ein Alias-Import nennt `Stage` weiterhin)
- gestellte_uhr: `make_trip` UND `save_trip`
- trips_pfad: `get_trips_dir`

**Scanner-Signatur bleibt** `scan_*(tests_root)`; der Filter greift auch bei `tmp_path`, damit die gepflanzten Fälle den gefilterten Pfad beweisen. Die Kandidatenzählung in `test_echter_testbaum_ohne_fehlalarm_der_zweiten_regel` (Untergrenze >= 20) bleibt vom Helfer unabhängig und bekommt einen eigenen, im Test selbst stehenden Vorab-Filter auf `Waypoint`; ein kaputter Helfer reisst sie so nicht mit.

**Ergebnis-Cache:** `functools.cache` auf einer nullstelligen Funktion je Regel, nur für den echten `TESTS_ROOT`, nie für `tmp_path`. Intern wird ein Tupel gehalten; Aufrufer erhalten je Aufruf eine frische Liste (Vergleiche mit `funde == []`, Veränderung darf den Cache nicht berühren). Der Cache wirkt nur je Worker-Prozess, daher trägt jede der beiden Cache-Dateien per `pytestmark` eine eigene `xdist_group` (eigener Name, nicht `echtdaten`, kein `@`). `test_trips_pfad_rueckbau.py` braucht keinen Cache (ein Lauf).

**trips_pfad:** Der Baumlauf wird eine Funktion mit Wurzel-Parameter, damit ein gepflanzter Verstoß in `tmp_path` prüfbar ist. `SyntaxError` bleibt für gefilterte Dateien rot.

**Parsebarkeit (neu, ausdrücklich):** Weil gefilterte Scanner kaputte Dateien nicht mehr zwingend parsen, prüft ein eigener Test jede `.py` unter `tests/` (parsen, sofort verwerfen; gemessen ca. 8,6 s auf dem Mac, heute 0 kaputt von 1.937). `SyntaxError`, `ValueError` (Nullbytes, je nach Python-Version auch als `SyntaxError`), `UnicodeDecodeError`, `OSError` ergeben einen roten Befund mit Dateiname, keine Warnung. Die Prüffunktion nimmt die Wurzel als Parameter, damit `tmp_path` mit kaputten Dateien sie rot macht. Abweichung von der Gegenprüfung (sie wollte die Prüfung an `repo_path` hängen): der Pfad-Wächter AC-3 überschreitet auf dem Mac schon heute das 30-s-Netz (38,3 s), der Nachweis wäre lokal nicht führbar; `test_repo_path_hardcoding_ratchet.py` bleibt in Scheibe 1 unangetastet. `user_id` bleibt in Scheibe 1 ungefiltert und parst weiter alles; die Prüfung macht diese Garantie ausdrücklich und deckt Scheibe 2.

**Verworfene Varianten (Abweichung vom Issue-Text, der einen „session-gecachten AST-Index" vorschlägt):**

- A: session-gecachter AST-Index (Issue-Vorschlag). Verworfen: spart nur den Parse-Anteil (Parsen 8-10 s, der Rest ist Durchlaufen), hält ca. 839 MB und wird durch den GC selbst langsamer (24,2 s statt 8,3 s), wirkt unter xdist nur je Worker, und `kind.parent` verändert geteilte Bäume.
- B: Bezeichner-Vorfilter vor dem Parsen plus Ergebnis-Cache. Gewählt: spart Parsen und Durchlaufen.
- C: Timeout anheben oder GC abschalten. Verworfen: überdeckt nur.
- D: Cache auf Platte. Verworfen: ein frischer CI-Checkout hat nie einen.

Auch offen: Das Abschlusskriterium „je Datei" des Issues wird auf diese drei Scanner-Dateien begrenzt; die übrigen tragen die Folge-Issues #3316 und #3317.

Prototypwerte (Orientierung, einmal gemessen, Mac, Last schwankend): wallclock direkt 30,8 s auf 3,3 s; wallclock indirekt 30,9 s auf 9,4 s; gestellte_uhr 23,3 s auf 1,7 s; trips_pfad 16,1 s auf 0,4 s. Funde Prototyp = vorher (1 / 0 / 10 / 0).

## Expected Behavior

- **Input:** Lauf der drei Scanner-Dateien (lokal oder CI) gegen den echten `tests/`-Baum bzw. `tmp_path`.
- **Output:** dieselben Funde wie vorher, spürbar kürzere Laufzeit, kein Test der drei Dateien reisst auf dem Mac mehr das 30-s-Netz.
- **Side effects:** keine; kein Produktcode, keine Timeout-Anhebung, `KNOWN_VIOLATIONS` unverändert.

## Acceptance Criteria

- **AC-1:** Given der echte `tests/`-Baum auf einem festen Commit / When die drei Scanner einmal gefiltert und einmal ungefiltert laufen / Then liefern beide je Scanner dieselben Funde (wallclock direkt 1, indirekt 0, gestellte_uhr 10 auf Stand der Messung) und `KNOWN_VIOLATIONS` bleibt unverändert.
  - Test: einmaliger Messnachweis gefiltert gegen ungefiltert auf demselben Commit, abgelegt im Artefakt-Ordner `docs/artifacts/rework-3279-testsuite-tempo/`, bewusst kein Dauertest (er fräße die Einsparung auf).

- **AC-2:** Given je Scanner eine gepflanzte Testdatei mit echtem Verstoß in `tmp_path` / When der gefilterte Scanner läuft / Then wird der Verstoß gefunden, beim indirekten Scanner auch bei Alias-Import von `Stage`.
  - Test: je Scanner ein Fall in `tmp_path` (wallclock direkt, wallclock indirekt inkl. `from ... import Stage as ...`, gestellte_uhr, trips_pfad); Fund mit Dateiname und Funktion erwartet.

- **AC-3:** Given je Scanner eine gepflanzte Datei, deren Bezeichner in Nicht-ASCII-Schreibweise steht (Fullwidth-Buchstaben, NFKC-gleich) / When der gefilterte Scanner läuft / Then wird sie trotzdem gefunden.
  - Test: je Scanner ein Fall mit Fullwidth-Bezeichner in `tmp_path`; Fund erwartet. Der Helfer-Test deckt zusätzlich ASCII und Nichtvorkommen (Datei ohne Bezeichner ergibt „kein Treffer").

- **AC-4:** Given ein künstlich verfälschter Filter (falscher Name, UND statt ODER, NFKC weg, immer False) bzw. ein verfälschter Cache (liefert leere Liste oder wirkt auf `tmp_path`) / When die Tests der jeweiligen Ratsche laufen / Then ist je Verfälschung mindestens ein Test rot, belegt je umgebauter Ratsche.
  - Test: Mutations-Gegenprobe per String-Ersetzung mit externer Sicherungskopie (kein `git checkout/stash/reset`), Ergebnis je Mutation im Artefakt-Ordner protokolliert.

- **AC-5:** Given der Cache der beiden Cache-Dateien / When zwei `tmp_path`-Läufe mit unterschiedlichem Inhalt laufen, eine zurückgegebene Liste verändert wird und der echte Baum mehrfach abgefragt wird / Then liefert jeder Lauf seine eigenen Funde, der nächste Aufruf bleibt unverändert, und der echte Baum wird je Regel im Prozess nur einmal gescannt.
  - Test: Zwei `tmp_path`-Läufe mit verschiedenen Funden; `.append` auf die Rückgabe, danach Neuaufruf unverändert; Zähler (Aufrufe der Scan-Funktion) beim echten Baum gleich 1 nach mehreren Aufrufen.

- **AC-6:** Given eine `.py` unter der Wurzel ist kaputt (Syntaxfehler, Nullbyte, ungültiges UTF-8, nicht lesbar) / When die Parsebarkeits-Prüfung läuft / Then wird sie rot und nennt den Dateinamen, je Fehlerart ein Fall; auf dem echten Baum ist sie grün.
  - Test: vier Fälle in `tmp_path` (Syntaxfehler, Nullbyte, ungültiges UTF-8, `OSError` über einen ins Leere zeigenden Symlink `x.py`, weil Dateirechte unter root nicht greifen) erwarten rot mit Dateiname, unabhängig vom konkreten Ausnahmetyp; echte Wurzel `tests/` grün; ein parsbarer Baum bleibt grün.

- **AC-7:** Given die drei umgebauten Scanner-Dateien / When sie vorher und nachher im selben Zeitfenster seriell auf dem Mac gemessen werden / Then überschreitet kein Test dieser Dateien mehr das 30-s-Netz, ohne dass ein Timeout angehoben wurde.
  - Test: Vorher/Nachher je Datei im Artefakt-Ordner `docs/artifacts/rework-3279-testsuite-tempo/` belegt (Prototypwerte als Orientierung); bewusst kein Laufzeit-Assert als Dauertest, weil er mit der Last wackelt.

- **AC-8:** Given die beiden Cache-Dateien tragen je eine eigene `xdist_group` / When sie mit `-n 2 --dist loadgroup` laufen / Then laufen alle Tests jeder Datei in einem Worker und der Lauf ist grün.
  - Test: Subprozess-Lauf mit `-n 2 --dist loadgroup` auf beide Dateien; Worker-Kennung je Datei einheitlich, Exit-Code 0.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Helfer-Test: GIVEN ASCII-Datei, NFKC-Bezeichner-Datei, Datei ohne Bezeichner WHEN der Helfer fragt THEN Treffer, Treffer, kein Treffer.
- [ ] Parsebarkeit: GIVEN kaputte Dateien je Fehlerart in `tmp_path` WHEN die Prüffunktion läuft THEN rot mit Dateiname; echter Baum grün.
- [ ] je Scanner gepflanzter Verstoß und NFKC-Fall (AC-2, AC-3); wallclock indirekt zusätzlich Alias-Import.
- [ ] Cache: zwei `tmp_path`-Läufe, Listen-Veränderung, Einmal-Scan des echten Baums (AC-5).
- [ ] Kandidatenzählung (>= 20) bleibt grün mit eigenem Vorab-Filter auf `Waypoint`; ein verfälschter Helfer reisst sie nicht mit.
- [ ] `-n 2 --dist loadgroup` auf beide Cache-Dateien (AC-8).
- Einmalige Nachweise (Artefakt, kein Dauertest): AC-1, AC-4, AC-7.

## Scope

- **In Scope:** Helfer, Helfer-Test mit Parsebarkeits-Prüfung, Filter und Cache in wallclock (beide Regeln) und gestellte_uhr, Filter und Wurzel-Parameter in trips_pfad, Messnachweise.
- **Out of Scope:** Scheibe 2 = #3316 (thunder_scale, `repo_path`-Tempo, `user_id`); Scheibe 3 = #3317 (echte Wartezeiten, Sammel-Subprozesse, Validator-Fälle); lokale parallele Form #3278; abgelaufene `EXPIRY`-Daten (#1199); jede Produktänderung.

## Definition of Done

- [ ] AC-1 bis AC-8 erfüllt, alle Tests der fünf Dateien grün.
- [ ] Nachweise zu AC-1, AC-4 und AC-7 liegen in `docs/artifacts/rework-3279-testsuite-tempo/`.
- [ ] Kein Timeout angehoben, `KNOWN_VIOLATIONS` unverändert, kein Produktcode berührt.
- [ ] Alle CI-Pflicht-Checks grün.

## Known Limitations

- Der Filter ist nur verlustfrei, solange die Regel einen Bezeichner verlangt; ändert sich eine Regel, muss der Filter mitgeprüft werden (die gepflanzten Fälle in AC-2/AC-3 fangen das).
- Der Cache wirkt nur je Worker-Prozess; deshalb die eigene `xdist_group` je Cache-Datei.
- CI-Zeiten wurden nicht ausgewertet; Absolutzeiten schwanken auf dem Mac mit der Last (Vergleich nur im selben Zeitfenster).
- Die Parsebarkeits-Prüfung kostet ca. 8 s.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Testinfrastruktur ohne Änderung an Kanälen, Providern, Datenmodell, Auth oder Test-Politik; die Wächter behalten ihre Zusicherungen, nur der Weg dorthin wird kürzer.

## Changelog

- 2026-11-24: Initial spec created (Workflow rework-3279-testsuite-tempo, Issue #3279, Scheibe 1)
