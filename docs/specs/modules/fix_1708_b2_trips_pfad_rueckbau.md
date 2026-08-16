---
entity_id: fix_1708_b2_trips_pfad_rueckbau
type: module
created: 2026-08-16
updated: 2026-08-16
status: draft
version: "1.1"
tags: [tests, issue-1708, trips-pfad, rueckbau]
---

# Fix #1708 B2 — Toten `trips/`-Pfad aus Testdateien und Loader entfernen

## Approval

- [x] Approved — Product Owner, 2026-08-16 („approved")

## Purpose

Der Pfad `data/users/<uid>/trips/<id>.json` ist seit #1250 Scheibe 7a (ADR-0023) tot;
Scheibe A hat den Produktivcode bereits gesäubert. B2 räumt den Rest: Neun Testdateien
rufen den toten Pfad noch real auf und wirken dadurch entweder wirkungslos (No-Op-Aufräumung
ins Leere) oder — in einem Fall — verlieren eine echte Zusicherung an eine Adresse, die nie
beschrieben wird. `get_trips_dir()` fällt aus `src/app/loader.py`, ebenso die eine
Wächter-Ausnahme, die genau diese Funktion bisher deckte. Zusätzlich werden alle verbliebenen
Kommentar-/Docstring-Stellen korrigiert, die `get_trips_dir()` fälschlich als existierend oder
als tatsächlichen Ablageort von Trip-Daten beschreiben — genau diese Fehlerklasse (falsche
Doku über Datenpfade) hat #1708 überhaupt erzeugt (Beleg: Scheibe A fand in
`api/routers/preview.py:10` einen Docstring, der einen aus `trips/` lesenden Owner-Check
behauptete, während der Code längst aus `briefings/` las).

Scheibe B2 ist **Teilarbeit** und schließt #1708 **nicht**. Sie baut auf B1 auf (stillgelegte
Tests am toten Pfad reaktiviert) und wird von C gefolgt (14 tote Bestandsdateien löschen,
schließt #1708).

## Source

- **File:** `src/app/loader.py:1155-1163` (`get_trips_dir()` — das Entfernungsziel)
- **File:** `tests/test_trips_path_revival_guard.py:91` (`KNOWN_VIOLATIONS`-Eintrag), `:459-462` (Docstring-Erwartung)
- **File:** `tests/test_briefing_route_cutover.py` (Ausnahme — bleibt am Legacy-Pfad)
- **File:** `tests/tdd/test_issue_731_unified_commands.py:403`
- **File:** `tests/tdd/test_issue_1001_telegram_bubbles.py:858,437`
- **File:** `tests/tdd/test_issue_612_report_on_demand.py:155,293,327`
- **File:** `tests/tdd/test_inbound_gate_errors.py:48`
- **File:** `tests/tdd/test_trip_command_processor.py:73`
- **File:** `tests/tdd/test_issue_882_pause_skip.py:69`
- **File:** `tests/tdd/test_feature_656_radar_nowcast.py:188,215,302`
- **File:** `tests/tdd/test_feature_660_convective_stage.py:234`
- **File:** `tests/tdd/test_issue_818_radar_briefing_integration.py:97,102` (Doku-Hygiene, siehe AC-7)
- **File:** `tests/tdd/test_issue_822_radar_nowcast_segment.py:101,105` (Doku-Hygiene, siehe AC-7)
- **File:** `tests/tdd/test_bundle_791_847_844_alerts.py:72` (Doku-Hygiene, siehe AC-7)
- **File:** `tests/tdd/test_issue_363_signal_telegram_preview.py:28` (Doku-Hygiene, siehe AC-7)
- **File:** `tests/tdd/test_loader_display_config_default.py:244` (Doku-Hygiene, siehe AC-7)
- **File:** `tests/tdd/test_issue_1133_testdata_cleanup.py:41,58,60,62,63` (Doku-Hygiene, siehe AC-7)

Schicht: **Python-Core / Domain-Backend** (`src/app/loader.py`, schema-relevant — löst den
Pre-Snapshot-Backup-Hook aus) plus **Testschicht** (`tests/`). Kein Go-Code betroffen — die
Go-Seite des Wächters ist bereits leer (gemessen, siehe Dependencies).

## Estimated Scope

- **LoC:** ~140 im ungünstigen Fall (Wegfall `get_trips_dir()` ~-10 · 9 Testdateien
  Umstellung/Aufräumung ~35 · Ausnahme+Docstring im Wächter ~10 · Trefferkraft-Nachweis ~30 ·
  Doku-Hygiene in 6 zusätzlichen Dateien + Wächter-Docstring ~25, Puffer für Nacharbeit
  aufgerundet ~30)
- **Files:** 17 (1 Produktiv, 16 Test — davon 6 ausschließlich Doku-Hygiene ohne Code-Änderung)
- **Effort:** medium — mechanischer Teil klein, teuer ist der Trefferkraft-Nachweis (siehe R1
  im Kontextdokument) und die Prüfung, ob `test_issue_731:403` nach der Umstellung grün bleibt

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/loader.py:1166` `get_briefings_dir()` | Funktion | der lebende Pfad, auf den umgestellt wird |
| `src/app/loader.py:1133` `get_data_dir()` | Funktion | öffentlich, bleibt bestehen; trägt die testlokale Legacy-Pfadbildung in `test_briefing_route_cutover.py` |
| `tests/test_trips_path_revival_guard.py:91` `KNOWN_VIOLATIONS` | Konstante | die eine Ausnahme, die im selben Commit wie `get_trips_dir()` entfällt |
| `tests/test_trips_path_revival_guard.py:72` `REPO_ROOT` | Modul-Global | Scan-Wurzel; per `monkeypatch` umbiegbar, trägt den neuen Trefferkraft-Nachweis |
| `tests/test_trips_path_revival_guard.py:409-419` `test_ac7_known_violations_only_shrink` | Test | einzige heutige Positivkontrolle am echten Bestand; wird durch den neuen Nachweis ersetzt |
| `tests/conftest.py:81` | Fixture-Spiegelung | spiegelt `trips/` → `briefings/` für `real_data_root`-Tests — **Invariante, bleibt unangetastet** |
| `tests/tdd/test_issue_818_radar_briefing_integration.py::test_ac7_mandantentrennung_isolated` (~:585) | Test | gehört Parallelsitzung #1697 — **Invariante, bleibt unangetastet**, nur Zeile 97/102 derselben Datei sind unser Gegenstand |
| `.github/ci_tdd_excludes.txt` | Liste | betrifft B2 nicht direkt (die CI-ausgeschlossenen K3-Dateien haben keinen echten Aufruf) |

## Implementation Details

### Der gemeinsame Umbau

Neun Testdateien rufen `get_trips_dir()` heute real auf. Zwei Gruppen, unterschiedliche
Behandlung:

**K1 — echte Fixture-Schreiber (2 Dateien):**
- `tests/test_briefing_route_cutover.py` — **Ausnahme, nicht auf `get_briefings_dir()`
  umbiegen.** Nur Zeile 110 (dort wird `briefings/` umständlich als
  `get_trips_dir(...).parent / "briefings"` konstruiert) wechselt auf
  `get_briefings_dir(uid)`. Die Zeilen 130/149/171 legen absichtlich eine abweichende
  Alt-Version am Legacy-Pfad an, um zu beweisen, dass `load_all_trips`/`load_trip` sie
  ignorieren und `save_trip` sie byte-unverändert lässt — sie bilden den Legacy-Pfad
  weiterhin **testlokal literal** über `loader.get_data_dir(uid) / "trips"`.
- `tests/tdd/test_issue_1001_telegram_bubbles.py:858` — echter Schreiber (`mkdir` +
  `write_text`), wird auf `get_briefings_dir()` umgebogen.

**K2 — greift ins Leere, reine No-Op-Aufräumung (7 Dateien, 10 Stellen):** alle laufen unter
der autouse-Isolation (`tests/conftest.py:120 _isolate_data_root`) in einer leeren
tmp-Wurzel; `save_trip` schreibt seit #1250 nach `briefings/`. Diese Stellen finden nie
etwas und räumen entsprechend nie etwas auf. Ersatzlos streichen oder auf
`get_briefings_dir()` umziehen, je nachdem was die Datei lesbarer macht:
`test_issue_612_report_on_demand.py:155,293,327` · `test_inbound_gate_errors.py:48` ·
`test_trip_command_processor.py:73` · `test_issue_882_pause_skip.py:69` ·
`test_feature_656_radar_nowcast.py:188,215,302` · `test_feature_660_convective_stage.py:234` ·
`test_issue_1001_telegram_bubbles.py:437`.

Ausnahme innerhalb K2: `test_issue_731_unified_commands.py:403` (plus die zugehörige
Aufräumung `:184`) ist **kein** No-Op — sie ist der einzige inhaltliche Fund unter K2 (siehe
unten).

### `get_trips_dir()` entfernen

`src/app/loader.py:1155-1163` fällt vollständig. Gemessen: kein Produktivaufrufer
(`grep -rn "get_trips_dir" src/ api/ internal/ cmd/ scripts/ .claude/` liefert nur die
Definition; Positivkontrolle mit `get_briefings_dir` auf demselben Befehl: 12 Treffer, echte
Aufrufer). Die Funktion unterscheidet sich von `get_briefings_dir()` ausschließlich im
Verzeichnisnamen — kein `mkdir`, kein sonstiger Seiteneffekt.

### `KNOWN_VIOLATIONS` leeren, im selben Commit

`test_ac7_known_violations_only_shrink` (`test_trips_path_revival_guard.py:409-419`)
verlangt heute, dass der Scanner exakt den Ausnahme-Schlüssel
`src/app/loader.py::get_trips_dir::0` findet. Entfernt man `get_trips_dir()` ohne die
Ausnahme zu leeren, wird dieser Test rot. Beides muss daher **im selben Commit** landen. Die
Obergrenze `<= 1` (`:422`) bleibt bei 0 Funden gültig, keine Anpassung nötig. Der
Ausnahme-Kommentar selbst (`:92-93`, behauptet fälschlich „12 Testdateien", gemessen sind es
9) verschwindet mit dem Eintrag und braucht keine eigene Korrektur.

### Trefferkraft-Nachweis ergänzen

Mit leerer `KNOWN_VIOLATIONS` verliert der Wächter seine einzige Positivkontrolle am echten
Bestand — kein Test würde mehr beweisen, dass der Scanner auf realen Dateien überhaupt etwas
zurückliefert (ein verschluckter Lesefehler oder eine kaputte Pfadauflösung wäre danach
lautlos grün). Ersatz: ein neuer Test legt in `tmp_path` zwei echte Verstoß-Dateien an — eine
Go-Datei mit Slice-Zugriff, eine Python-Datei mit Divisions-Form, beide dem realen
Scan-Muster nachgebildet — biegt `REPO_ROOT` per `monkeypatch.setattr` auf diesen
temporären Baum um und erwartet, dass der Scanner **beide** Funde meldet. Trägt, weil
`REPO_ROOT` ein Modul-Global ist, das die Scan-Funktionen bei jedem Aufruf neu aus dem
globalen Zustand auflösen (nicht als Signaturparameter) — deshalb per `monkeypatch` umbiegbar,
ohne den Scanner selbst anzufassen. Deckt beide Sprachpfade ab (die verlorene Kontrolle bewies
nur die Python-Seite).

Zusätzlich wird die Docstring-Erwartung von `test_keine_unlisted_trips_pfad_funde()`
(`:459-462`) angepasst: sie beschreibt heute noch die RED-Phase aus Scheibe A („src/app/loader.py:1163
(get_trips_dir) ist über KNOWN_VIOLATIONS gedeckt und erscheint NICHT in der Fehlermeldung") —
nach B2 gibt es die Funktion gar nicht mehr, die Formulierung muss das widerspiegeln statt eine
überholte Deckungs-Aussage stehen zu lassen.

### `test_issue_731_unified_commands.py:403` wirksam machen

`TestAC10UserIsolation.test_weiter_only_affects_own_trip` (`:392-405`) lässt zwei reale
Nutzer A/B je einen deaktivierten Trip anlegen, führt `WEITER` als Nutzer A aus und prüft
danach, dass `users/default/` unberührt bleibt. Am toten `trips/`-Pfad kann diese Prüfung nie
fehlschlagen — ein echtes Leck nach `users/default/briefings/` bliebe ungefangen. Die
Umstellung auf `get_briefings_dir()` macht die Zusicherung erstmals wirksam.

### Doku-Hygiene — verbliebene Erwähnungen korrigieren

Sechs weitere Testdateien rufen `get_trips_dir()` nicht auf, beschreiben die Funktion aber in
Kommentar oder Docstring als existierend bzw. als den Ort, an dem Trip-Daten tatsächlich
liegen. Nach dem Wegfall der Funktion sind diese Stellen sachlich falsch und werden korrigiert
(Formulierung auf „existiert nicht mehr"/„entfernter Altbestand" bzw. Präteritum umgestellt,
kein Code-Verhalten ändert sich):

- `tests/tdd/test_issue_818_radar_briefing_integration.py:97` (Docstring) und `:102`
  (Variablenname `trips_dir`, zeigt bereits auf `get_briefings_dir()`). **Ausschließlich**
  diese zwei Stellen sind unser Gegenstand — `test_ac7_mandantentrennung_isolated`
  (~Zeile 585) gehört Parallelsitzung #1697 und bleibt unangetastet.
- `tests/tdd/test_issue_822_radar_nowcast_segment.py:101` (Kommentar) und `:105`
  (Variablenname `trips_dir`, gleiches Muster).
- `tests/tdd/test_bundle_791_847_844_alerts.py:72` (Docstring, beschreibt `get_trips_dir()`
  aktuell als den Pfad, den auch `TripAlertService` liest).
- `tests/tdd/test_issue_363_signal_telegram_preview.py:28` (Kommentar, bezeichnet die reale
  committete Fixture `data/users/default/trips/gr221-mallorca.json` als „echten
  get_trips_dir()-Pfad" — die physische Fixture-Datei selbst gehört zu Scheibe C und wird hier
  nicht angefasst, nur die Beschreibung).
- `tests/tdd/test_loader_display_config_default.py:244` (Kommentar, bereits korrekt im
  Sinne von „liest seit dem Cutover get_briefings_dir(), nicht mehr get_trips_dir()" — wird
  geprüft, ob nach dem Wegfall noch eine Anpassung nötig ist, da die Funktion dann nicht mehr
  existiert statt nur nicht mehr gelesen zu werden).
- `tests/tdd/test_issue_1133_testdata_cleanup.py:41,58,60,62,63` (Docstring von
  `test_ac1_fixture_isolation_path_resolution_and_roundtrip` — beschreibt den Wegfall von
  `get_trips_dir()` bereits vorausschauend im Futur; nach B2 auf Präteritum/Ist-Zustand
  umstellen).

## Expected Behavior

- **Input:** ein regulärer Testlauf (`uv run pytest <datei>`) der 16 betroffenen Testdateien
  sowie `tests/test_trips_path_revival_guard.py`, ohne Marker-Override
- **Output:** die 9 real aufrufenden Dateien greifen auf `get_briefings_dir()` zu bzw. haben
  ihre wirkungslose Aufräumung ersatzlos verloren — mit der einen dokumentierten Ausnahme
  `test_briefing_route_cutover.py`, deren drei Stellen weiterhin testlokal den Legacy-Pfad
  bilden. `get_trips_dir()` existiert nicht mehr. Der Wächter-Scanner hat keine tote Ausnahme
  mehr und weist stattdessen aktiv nach, dass er auf echten Dateien noch Funde liefert. Sechs
  weitere Dateien ohne Code-Änderung beschreiben `get_trips_dir()` nicht mehr als existierend.
- **Side effects:** keine Änderung an Produktivverhalten — `get_trips_dir()` hatte keinen
  Produktivaufrufer. Kein Schreibzugriff auf den echten `data/users/`-Baum während der Tests.

## Acceptance Criteria

- **AC-1:** Given neun Testdateien rufen heute den toten Pfad `get_trips_dir()` wirklich auf
  (ein echter Fixture-Schreiber, acht reine Aufräum-/Prüfstellen) / When diese Dateien
  umgestellt werden / Then greift keine dieser neun Dateien mehr auf `get_trips_dir()` zu —
  entweder weil sie jetzt `get_briefings_dir()` verwendet, oder weil die wirkungslose
  Aufräumung ersatzlos entfernt wurde, sodass sie tatsächlich aufräumt statt ins Leere zu
  greifen.
  - Test: `grep -rn "get_trips_dir" tests/` liefert nach der Umstellung in diesen neun Dateien
    keine echten Aufrufe mehr (Kommentare/Docstrings ausgenommen).

- **AC-2:** Given `tests/test_briefing_route_cutover.py` legt absichtlich eine abweichende
  Alt-Version am toten Pfad an, um zu beweisen, dass der lebende Lesepfad sie ignoriert und der
  Schreibpfad sie unangetastet lässt / When B2 abgeschlossen ist / Then bildet diese Datei den
  Legacy-Pfad weiterhin testlokal selbst, nur die Ermittlung des lebenden Pfads wechselt auf
  `get_briefings_dir()`; alle 7 Tests der Datei laufen unverändert grün.
  - Test: die bestehenden 7 Tests der Datei laufen nach der Änderung ohne Anpassung ihrer
    Erwartungen grün durch.

- **AC-3:** Given `get_trips_dir()` in `src/app/loader.py` hat gemessen keinen
  Produktivaufrufer / When die Funktion entfernt wird / Then läuft der Produktivbetrieb
  unverändert weiter, und keine Datei außerhalb der Testschicht referenziert die Funktion mehr.
  - Test: eine erneute Suche über den Produktivbestand (`src/`, `api/`, `internal/`, `cmd/`,
    `scripts/`, `.claude/`) nach dem Funktionsnamen liefert keinen Treffer mehr.

- **AC-4:** Given der Wächter-Test `test_ac7_known_violations_only_shrink` verlangt heute
  genau den Ausnahme-Eintrag für `get_trips_dir()` im Scan-Ergebnis / When `get_trips_dir()`
  entfernt und der Ausnahme-Eintrag im selben Commit gestrichen wird / Then bleibt dieser Test
  grün, weil Funktion und Ausnahme gemeinsam verschwinden — kein Zwischenzustand, in dem nur
  eines von beiden geändert ist.
  - Test: der bestehende Wächter-Testlauf nach dem Commit ist vollständig grün, ohne die
    Erwartung `<= 1` anzuheben.

- **AC-5:** Given nach dem Leeren der Ausnahme-Liste gibt es keinen Test mehr, der beweist,
  dass der Wächter-Scanner auf echten Dateien überhaupt etwas findet / When ein neuer Test
  zwei echte Verstoß-Dateien (eine im Go-, eine im Python-Muster) in einen eigens dafür
  angelegten Verzeichnisbaum legt und den Scanner darauf ansetzt / Then meldet der Scanner für
  beide Dateien einen Fund — ein Scanner, der auf echten Dateien nichts mehr findet, muss
  diesen Testlauf rot machen, nicht grün durchlaufen lassen.
  - Test: der neue Nachweis-Test schlägt fehl, sobald die Fund-Erkennung des Scanners
    absichtlich außer Kraft gesetzt wird (Mutationsprobe).

- **AC-6:** Given die Zusicherung in `test_issue_731_unified_commands.py:403` prüfte bisher
  am toten Pfad, dass ein `WEITER`-Befehl von Nutzer A keine Daten unter `users/default/`
  hinterlässt, und konnte dort nie fehlschlagen / When die Zusicherung auf den lebenden
  `briefings/`-Pfad umgestellt wird / Then bleibt der Test grün — es gibt kein Cross-User-Leck
  — und dieselbe Prüfung würde jetzt tatsächlich fehlschlagen, wenn ein Leck entstünde.
  - Test: der Test läuft nach der Umstellung grün; eine Gegenprobe mit umgedrehter Erwartung
    (Datei müsste existieren) schlägt fehl, was belegt, dass die Prüfung wirklich etwas misst
    und nicht nur ins Leere greift.

- **AC-7:** Given `get_trips_dir()` existiert nach dieser Scheibe nicht mehr / When jemand die
  verbliebenen Erwähnungen des Namens im Testbestand durchsieht / Then beschreibt keine
  Kommentar- oder Docstring-Stelle die Funktion mehr als existierend oder als den Ort, an dem
  Trip-Daten tatsächlich liegen; verbliebene Nennungen (etwa der historische Fund-Beleg in
  `test_trips_path_revival_guard.py`) benennen sie ausdrücklich als entfernten Altbestand.
  - Test: eine Durchsicht der sechs in Source/Implementation Details gelisteten Doku-Stellen
    plus der Wächter-Docstring bei `:459-462` zeigt für jede, dass der Text nach der Änderung
    nicht mehr im Präsens behauptet, die Funktion existiere oder werde aktuell gelesen.

## Known Limitations

- **Ein-Commit-Regel:** Entfernung von `get_trips_dir()`, Leeren von `KNOWN_VIOLATIONS` und
  Ergänzung des Trefferkraft-Nachweises müssen atomar in einem Commit landen. Ein
  Zwischenzustand ließe `test_ac7_known_violations_only_shrink` vorübergehend rot laufen und
  öffnete eine Lücke, in der kein Test den Scanner am echten Bestand prüft.
- **Reihenfolge:** die neun real aufrufenden Testdateien müssen vor oder mit der Entfernung
  von `get_trips_dir()` umgestellt sein, sonst bricht die Testsammlung an einem
  Namens-/Importfehler. Die sechs reinen Doku-Hygiene-Dateien (AC-7) haben keine
  Reihenfolge-Abhängigkeit, da sie die Funktion nicht aufrufen.
- **`tests/conftest.py:81`** (Spiegelung `data/users/*/trips/*.json` → `briefings/` für
  `real_data_root`-Tests) ist **nicht Teil dieser Scheibe** und darf nicht versehentlich
  mitgerissen werden — sie hängt am Verzeichnisnamen im Fixture-Baum, nicht an der Funktion.
- **`test_ac7_mandantentrennung_isolated`** (~`test_issue_818_radar_briefing_integration.py:585`)
  gehört Parallelsitzung #1697 und bleibt unangetastet — nur die Docstring-Zeile 97 und der
  Variablenname bei 102 derselben Datei sind Gegenstand dieser Scheibe (AC-7).
- **Nicht Teil von B2:** die 14 toten Bestandsdateien unter
  `data/users/*/trips/*.json.TOT-legacy-1250-nicht-lesen` sowie die reale Fixture-Datei
  `data/users/default/trips/gr221-mallorca.json` selbst — nur deren fehlerhafte Beschreibung
  in `test_issue_363_signal_telegram_preview.py:28` wird korrigiert. Das Löschen der Datei
  gehört zu Scheibe C, die #1708 schließt.
- Wird beim Umstellen ein weiterer echter Fehlschlag sichtbar (über `test_issue_731:403`
  hinaus), ist das ein eigenständiger Befund — er wird gemeldet und nicht durch Abschwächen
  der Erwartung beseitigt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Es wird keine Grundsatzentscheidung geändert. ADR-0023 (Cutover
  `trips/` → `briefings/`) wird bestätigt und zu Ende geführt, nicht revidiert — B2 entfernt
  lediglich die letzten toten Verweise auf den bereits abgelösten Pfad, inklusive der Doku, die
  ihn noch als existierend beschreibt.

## Changelog

- 2026-08-16: Initial spec created (#1708 Scheibe B2)
- 2026-08-16: AC-7 (Doku-Hygiene) ergänzt nach Team-Lead-Entscheidung — Wegfall von
  `get_trips_dir()` macht sechs weitere Kommentar-/Docstring-Stellen sachlich falsch; Affected
  Files und Estimated Scope entsprechend erweitert.
