---
entity_id: fix_1708_a_trips_pfad_waechter
type: module
created: 2026-08-16
updated: 2026-08-16
status: draft
version: "1.0"
tags: [guard, ratsche, persistenz, issue-1708]
---

# Wächter gegen die Wiederkehr der toten Trip-Ablage (#1708, Scheibe A)

## Approval

- [x] Approved (PO, 2026-08-16)

## Purpose

Seit dem Cutover (ADR-0023) leben Trips ausschließlich in `data/users/<uid>/briefings/<id>.json`.
Der Pfad `data/users/<uid>/trips/<id>.json` ist tot — aber er sieht vollständig und plausibel aus und hat
nachweislich vier Fehlaussagen und zwei Datenänderungen ins Leere verursacht. Diese Scheibe errichtet den
Test, der rot wird, sobald Produktivcode den toten Pfad wieder bildet, und entfernt die beiden Go-Stellen,
die ihn laufend neu herstellen.

**Der Wächter ist der Gegenstand, nicht die Löschung.** Die Warnung existierte bereits als Notiz und wurde
trotzdem zweimal in fünf Minuten umgangen. Eine Regel, die nur in einer Notiz steht, wird umgangen; eine,
die einen Test rot macht, nicht.

## Source

- **File:** `tests/test_trips_path_revival_guard.py` (neu)
- **Identifier:** `test_keine_unlisted_trips_pfad_funde`, `test_known_violations_only_shrink`
- **Mit geändert (Go-API-Schicht):** `internal/store/user.go`, `internal/store/trip.go`,
  `internal/handler/profile_test.go`
- **Ausdrücklich NICHT geändert (Python-Core):** `src/app/loader.py` — `get_trips_dir()` bleibt in dieser
  Scheibe als einziger Ausnahmeeintrag bestehen (Begründung unter Known Limitations)

## Estimated Scope

- **LoC:** ~+340 bis +380 zählbar (≈ 90 % Testcode); LoC-Limit für diesen Workflow auf 500 angehoben
- **Files:** 7 (2 CREATE, 4 MODIFY, 1 optional MODIFY)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| ADR-0023 | Entscheidung | Beschließt `briefings/<id>.json` als einzige Persistenz-Wahrheit |
| ADR-0031 | Entscheidung | Listet `trips/` bisher fälschlich als Teil des Nutzerverzeichnis-Layouts (`:16`) — wird korrigiert |
| `tests/test_egress_inventory_drift.py` | Vorbild | Go-Quelltext per Zeilen-/Textparse als Daten lesen (`:44-61`), Parser-Wirkungsnachweis (`:92`) |
| `tests/test_output_timezone_guard.py` | Vorbild | Restlisten-Schlüsselform, „nur schrumpfen"-Ratsche (`:696`), Scanflächen-Nachweis (`:659`) |
| `tests/test_success_status_guard.py` | Vorbild | Harte Obergrenze für Ausnahmen (`:3268-3286`), getesteter Scanflächen-Ausschluss (`:3293`) |
| `internal/store/briefingsDir()` | lebender Pfad | Das Ziel, auf das seit S7a gelesen und geschrieben wird |

## Implementation Details

### Warum die Regel am Literal bindet und nicht am Ausdruckskontext

`internal/store/user.go:84` baut den Pfad **nicht** in einem `filepath.Join`. Das Literal steht in einem
`[]string{"locations", "trips", "gpx", "weather_snapshots"}`-Slice; der Join passiert eine Zeile später mit
der Schleifenvariablen `sub`. Eine Regel der Form „Literal `trips` innerhalb eines `filepath.Join`, das auch
`users` enthält" übersieht **genau die Stelle, die die Falle laufend neu herstellt**.

### Erkennungsregel

Ein String-Literal `L` ist ein Fund, wenn:

```
R1:  L == "trips"
R2:  re.search(r"(?:^|/|\*/)trips(?:/|$)", L)  UND  ("*" in L oder "users" in L)
```

- **Go:** zeilenweise, Zeile am ersten `//` abgeschnitten, dann `"([^"]*)"` extrahieren, R1/R2 anwenden
- **Python:** `ast.walk` über `ast.Constant`(str) und `ast.JoinedStr`-Teile

### Scanfläche

Per `rglob` **berechnet**, nie als abgeschriebene Dateiliste (sonst läuft eine neue Datei unter
`internal/` stillschweigend nicht mit):

- Go: alle `*.go` unter `internal/` und `cmd/`, **ohne** `*_test.go`
- Python: alle `*.py` unter `src/` und `api/`
- Ausgeschlossen: `tests/`, `scripts/`, `frontend/`, `docs/`

### Gemessene Wirkung auf dem heutigen Bestand

292 Produktivdateien (91 Go, 201 Python) → **4 Funde, null Falsch-Positive**:
`internal/store/trip.go:15`, `internal/store/user.go:84`, `src/app/loader.py:1163`
und `api/routers/preview.py:10`.

**Der vierte Fund wurde erst beim RED-Lauf sichtbar** und ist ein echter Fang, kein Fehlalarm:
Der Modul-Docstring von `api/routers/preview.py` behauptet in Zeile 10
„Trip-Owner-Check: Loader-Pfad ist user-scoped (`data/users/<user>/trips/<id>.json`)".
Das ist **inhaltlich falsch** — der `PreviewService` liest aus `briefings/`
(`src/services/preview_service.py:18,67`, dessen eigener Docstring `:55-56` es korrekt beschreibt).
Die Falschaussage steht ausgerechnet an der Stelle, die den Sicherheitsmechanismus für den
Trip-Owner-Check erklärt — genau die Klasse plausibler, vollständig aussehender Fehlaussage über den
Ablageort, die #1708 erzeugt hat.

**Konsequenz:** keine zweite Ausnahme, keine Verschärfung von R1/R2. Docstrings vom Scan auszunehmen
würde künftige Fänge dieser Art blind machen. Der Docstring wird richtiggestellt (AC-13).

Nicht getroffen (alle real im Bestand, als Negativnachweis zu verankern): die 13 Routen-Strings
`"/api/trips/…"` (`internal/router/router.go:141-167`), `"corrupt_trips.json"`
(`internal/scheduler/briefing_health.go:374` — enthält `users` **und** `*`, aber `corrupt_trips` ist kein
`trips`-Segment; eine Substring-Regel hätte hier falsch angeschlagen), die URL-Strings in
`trip_report_scheduler.py:1707` und `trip_command_processor.py:1328`, sowie
`internal/scheduler/selftest.go:42` (Variable heißt `tripsDir`, Literal ist `"briefings"`).

### Restliste

Schlüsselform `pfad::symbol::ordinal` (Hausnorm, `tests/test_guard_findings_survive_line_shifts.py:52`).
Genau ein Eintrag:

```
"src/app/loader.py::get_trips_dir::0":
  "UEBERGANG #1708 Scheibe B — 12 Testdateien rufen sie; entfaellt mit deren
   Umstellung auf get_briefings_dir(). KEINE Dauerausnahme."
```

**Kein Inline-Ausnahmeventil.** Anders als `internal/handler/store_scope_guard_test.go:653` erlaubt dieser
Wächter keine Stilllegung per Kommentar an der Fundzeile — eine Ausnahme wäre sonst in der Täterdatei
unsichtbar mitzuschmuggeln. Wer eine Ausnahme will, muss die Wächterdatei anfassen, und das sieht ein Reviewer.

### Umsetzungsreihenfolge (zwei echte ROTs)

| Schritt | Erwartung |
|---|---|
| A — Wächter zuerst, Restliste = nur der Python-Eintrag | **ROT**: benennt `trip.go:15` und `user.go:84`, bevor irgendetwas gelöscht ist |
| B — `internal/handler/profile_test.go` umstellen | **ROT**: `trips/` entsteht noch. Zweiter, unabhängiger RED-Beleg |
| C — `"trips"` aus `user.go:84`, `TripsDir()` aus `trip.go:14-16` | A und B werden grün |
| D — `docs/adr/0031-…:16` korrigieren | zählt nicht auf LoC |

Umgekehrte Reihenfolge (erst löschen) macht den Wächter **grün geboren** — dann ist unbewiesen, dass er
überhaupt trifft.

## Expected Behavior

- **Input:** der Quelltextbestand unter `internal/`, `cmd/`, `src/`, `api/`
- **Output:** Testlauf grün, solange kein Produktivcode den toten Pfad bildet; rot mit Nennung von
  Datei, Symbol und Fundtext, sobald er es tut
- **Side effects:** Neu registrierte Nutzer erhalten kein `trips/`-Verzeichnis mehr. Kein Produktivcode
  liest oder schreibt dort — die Änderung ist für den laufenden Betrieb ohne Wirkung.

## Acceptance Criteria

- **AC-1:** Given eine Go-Quelldatei enthält die Slice-Form `[]string{"locations", "trips", "gpx"}` mit
  Verzeichnis-Join in einer Folgezeile / When der Wächter über diese Quelle läuft / Then meldet er genau
  einen Fund mit dem Symbol, in dem das Literal steht
  - Test: Der Erkenner wird gegen einen synthetischen Quelltext-String im Speicher aufgerufen (nicht gegen
    eine echte Datei, sonst meldet der Wächter sich selbst) und muss den Fund liefern. Dies ist die Form,
    die die Falle real neu herstellt — bliebe sie unerkannt, wäre der ganze Wächter wirkungslos.

- **AC-2:** Given eine Go-Quelldatei bildet den Pfad als `filepath.Join(s.DataDir, "users", s.UserID, "trips")`
  / When der Wächter läuft / Then meldet er genau einen Fund
  - Test: synthetischer Quelltext-String, Erkenner liefert genau einen Fund.

- **AC-3:** Given eine Python-Quelldatei bildet `get_data_dir(uid) / "trips"` oder
  `root.glob("*/trips/*.json")` / When der Wächter läuft / Then meldet er je einen Fund
  - Test: synthetischer Python-Quelltext, per AST gescannt, zwei Fälle je ein Fund.

- **AC-4:** Given der Quelltext enthält die realen Bestandsformen `"/api/trips/{id}"`,
  `"https://gregor20.henemm.com/trips/"`, `"corrupt_trips.json"` und `"briefings"` / When der Wächter läuft
  / Then meldet er null Funde
  - Test: jede der vier Formen einzeln gegen den Erkenner; jede muss null liefern. Verhindert, dass der
    Wächter beim ersten Falsch-Positiv per Ausnahme entschärft wird.

- **AC-5:** Given eine Go-Zeile besteht vollständig aus dem Kommentar `// filepath.Join(dir, "trips")` /
  When der Wächter läuft / Then meldet er null Funde; und Given dieselbe Zeile trägt echten Code mit einem
  Kommentar dahinter / Then meldet er genau einen Fund
  - Test: beide Zeilenformen gegen den Go-Parser. Belegt, dass der Kommentar-Abschnitt wirkt und nicht
    versehentlich echten Code verschluckt.

- **AC-6:** Given die Scanfläche wird zur Laufzeit berechnet / When der Wächter startet / Then bricht er mit
  verständlicher Meldung ab, wenn er weniger als 80 Go- oder weniger als 180 Python-Produktivdateien findet,
  und ebenso, wenn `internal/store/user.go`, `internal/store/trip.go` oder `src/app/loader.py` nicht
  namentlich in der gescannten Menge liegen
  - Test: Untergrenzen und Trägernachweis werden als eigene Testfunktionen geprüft. Eine reine Zählung
    fängt keinen Pfad-Tippfehler, der nur einen Teilbaum verliert — deshalb beides.

- **AC-7:** Given die Restliste enthält einen Eintrag, dessen Fundstelle im Code nicht mehr existiert /
  When der Wächter läuft / Then wird er rot; und Given jemand fügt der Restliste einen zweiten Eintrag hinzu
  / Then wird er ebenfalls rot
  - Test: „nur schrumpfen"-Ratsche und harte Obergrenze `len(KNOWN_VIOLATIONS) <= 1` als zwei getrennte
    Tests. **Reichweite, präzise:** Die Obergrenze fängt *akzidentelles* Wachstum — jemand trägt einen
    Fund ein und zieht die Zahl nicht mit. Gegen eine *koordinierte* Manipulation in einem Commit
    (Wiederbelebung + passender Restlisten-Eintrag + angehobene Obergrenze) schützt sie **nicht**, weil
    Liste und Schranke in derselben, editierbaren Datei liegen. Dagegen wirken zwei andere Dinge: der
    unabhängige Go-Verhaltenstest `TestRegisterCreatesNoLegacyTripsDir`, der am Wirkort misst statt am
    Quelltext (nachgewiesen: er fängt diesen Fall), und die Review-Pflicht — wer eine Ausnahme will, muss
    die Wächterdatei anfassen, und das sieht ein Reviewer. Nachgewiesen durch Adversary-Mutation M7b
    (#1708 A, 2026-08-16).

- **AC-8:** Given `tests/` und `scripts/` liegen bewusst außerhalb der Scanfläche / When der Wächter läuft /
  Then werden die dortigen legitimen `trips`-Vorkommen nicht gemeldet, und dieser Ausschluss ist als eigener
  Test festgeschrieben
  - Test: eigener Test prüft, dass die Scanflächen-Berechnung keine Datei unter `tests/` oder `scripts/`
    zurückgibt. Schützt `tests/test_briefing_route_cutover.py`, das den Cutover per Lockvogel-Datei beweist,
    und die 9 Migrations-Skripte, deren Aufgabe der Altpfad ist.

- **AC-9:** Given ein Nutzer registriert sich neu / When die Registrierung erfolgreich abschließt / Then
  existiert unter seinem Nutzerverzeichnis **kein** `trips/`-Verzeichnis, während `locations/`, `gpx/` und
  `weather_snapshots/` weiter angelegt werden
  - Test: Go-Test `TestRegisterCreatesNoLegacyTripsDir` in `internal/handler/profile_test.go` — eigener,
    benannter Test statt nur einer gelöschten Zeile, damit der Schutz im Lauf-Protokoll sichtbar bleibt.
    Der Bestandstest `TestRegisterCreatesUserDirs` behält die drei übrigen Verzeichnisse als echte Zusicherung.

- **AC-10:** Given ein Entwickler sucht die Methode `Store.TripsDir()` / When er den Go-Code durchsucht /
  Then existiert sie nicht mehr, und der Go-Testlauf bleibt vollständig grün
  - Test: `go build ./...` und `go test ./internal/...` laufen grün. Die Methode hat null Aufrufer im
    gesamten Repo (nachgemessen), die Löschung kann nichts brechen.

- **AC-11:** Given der Wächter soll ein Auslieferungs-Tor sein / When die CI läuft / Then wird er im Job
  `test` gesammelt und ausgeführt
  - Test: `uv run pytest tests/test_trips_path_revival_guard.py --collect-only` zeigt die Testfunktionen.
    Begründung: `.github/workflows/ci.yml:414` — `deploy: needs: [test, lint]`; der Job `go-test` steht
    **nicht** in `needs`. Ein rein Go-seitiger Wächter hätte den PR rot gemacht, aber den Deploy nicht blockiert.

- **AC-12:** Given ADR-0031 beschreibt das Nutzerverzeichnis-Layout / When die Änderung ausgeliefert ist /
  Then nennt `docs/adr/0031-persistenz-dateibasiert-data-users.md:16` `trips/` nicht mehr als Bestandteil
  - Test: Sichtprüfung der ADR-Zeile im Review. Ohne diese Korrektur widerspricht das ADR dem Code, und die
    nächste Sitzung liest die alte Aussage als gültig — genau der Mechanismus, der #1708 erzeugt hat.

- **AC-13:** Given der Modul-Docstring von `api/routers/preview.py` beschreibt den Ablageort, aus dem der
  Trip-Owner-Check liest / When ein Entwickler ihn liest / Then nennt er `briefings/<id>.json` statt des
  toten `trips/<id>.json`, und der Wächter meldet die Datei nicht mehr
  - Test: `test_keine_unlisted_trips_pfad_funde` wird für diese Datei grün — der Wächter selbst ist der
    Nachweis. Die Aussage ist heute falsch (`src/services/preview_service.py:18,67` liest über
    `get_briefings_dir`), und sie steht an der Stelle, die den Sicherheitsmechanismus erklärt.

## Known Limitations

### Bekannte Umgehungen des Wächters (gehören wörtlich in den Docstring)

1. **Konstante/Variable** in einer ausgeschlossenen Datei, importiert in Produktivcode
2. **Konkatenation/Formatierung:** `"tri" + "ps"`, `fmt.Sprintf("tri%s", "ps")`
3. **Konfiguration/Umgebung:** Verzeichnisname aus `config.ini` oder Env
4. **Go-Rohstrings** (Backticks) werden vom `"…"`-Regex nicht erfasst
5. **Go-Blockkommentare** `/* … */` werden nicht abgeschnitten — Falsch-Positiv-Richtung, harmlos
6. **Schema-Umbenennung:** ein wiederbelebter Altpfad namens `trip_files/` fällt per Bauart durch
7. **Neuer Top-Level-Baum** außerhalb `internal/`, `cmd/`, `src/`, `api/`

Keine davon ist versehentlich erreichbar — alle erfordern bewusste Arbeit. Der reale Rückfall (jemand fügt
`"trips"` wieder in die `ProvisionUserDirs`-Liste ein) wird getroffen.

### Weitere Grenzen

- Der Python-Prozess bemerkt **nicht**, wenn eine Go-Datei syntaktisch kaputt ist — er sieht nur Text.
  Abgefangen wird das durch die Scanflächen-Untergrenze und den Trägernachweis (AC-6), nicht durch einen Parser.
- `src/app/loader.py:get_trips_dir()` bleibt in dieser Scheibe bestehen. Grund: 12 Testdateien rufen sie,
  darunter zwei, die **kein** toter Aufräum-Code sind — `tests/tdd/test_issue_1133_testdata_cleanup.py:61`
  nutzt sie als Sonde für die Datenwurzel-Isolation (#1133 AC-1), und
  `tests/tdd/test_issue_346_fixture_provider.py:29` steuert über die Existenz im toten Pfad die
  Fixture-Auswahl. Deren Umstellung ist Untersuchungsarbeit mit offenem Ausgang und gehört in Scheibe B.
  Der Abbau ist durch AC-7 erzwungen: sobald `get_trips_dir` verschwindet, wird der Eintrag stale und der
  Test rot; die Obergrenze von 1 verhindert, dass die Ausnahme sich vermehrt.

### Nicht Teil dieser Scheibe

- Die 12 Testdateien auf `briefings/` umstellen und je Datei belegen, warum sie heute grün ist → **Scheibe B**
- Die 14 toten Produktivdateien unter `/var/lib/gregor/users/*/trips.TOT-legacy-1250-nicht-lesen`
  archivieren und löschen → **Scheibe C** (schließt #1708)

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; setzt ADR-0023 durch und korrigiert ADR-0031
- **Rationale:** Die Entscheidung „`briefings/` ist die einzige Persistenz-Wahrheit" ist mit ADR-0023 bereits
  getroffen. Diese Scheibe fügt keine neue Entscheidungsfläche hinzu, sondern macht die bestehende
  durchsetzbar. ADR-0031 wird korrigiert, weil es dem Beschluss inhaltlich widerspricht.

## Regel-Budget

Neue Pflicht-Ratsche → Prüfdatum **2026-11-14** (+90 Tage). Am Prüfdatum gilt: kein nachweisbarer Fang und
Restliste leer → Rückbau erwägen. Ersetzt keine bestehende Regel; die bisherige „Regel" war eine
Gedächtnisnotiz ohne Durchsetzung — und wurde nachweislich zweimal in fünf Minuten umgangen.

## Changelog

- 2026-08-16: Initial spec created (#1708 Scheibe A)
