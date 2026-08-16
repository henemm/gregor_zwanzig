---
entity_id: fix_1708_b1_tote_fixture_befunde
type: module
created: 2026-08-16
updated: 2026-08-16
status: draft
version: "1.0"
tags: [tests, issue-1708, trips-pfad, stillgelegte-tests]
---

# Fix #1708 B1 — Stillgelegte Tests am toten `trips/`-Pfad reaktivieren

## Approval

- [x] Approved (PO, 2026-08-16, 'go' auf alle 8 ACs)

## Purpose

Drei Testdateien haengen am toten Pfad `data/users/<uid>/trips/<id>.json`. Sie tragen
Zusicherungen, die sie nicht bewachen — eine Datei laeuft in **keinem** Lauf, in einer weiteren
skippt der zentrale Test immer. Diese Scheibe macht die betroffenen Tests wieder wirksam und
belegt fuer jeden einzeln, warum er heute still ist.

Scheibe B1 ist **Teilarbeit** und schliesst #1708 **nicht**. Es folgen B2 (restliche Testdateien
umstellen, `get_trips_dir()` entfernen) und C (tote Dateien loeschen, schliesst #1708).

## Source

- **File:** `tests/tdd/test_bug_338_openmeteo_call_counter.py`
- **File:** `tests/tdd/test_issue_346_fixture_provider.py`
- **File:** `tests/tdd/test_issue_1133_testdata_cleanup.py`
- **File:** `tests/tdd/test_pytest_collection_and_timeout_safety.py`
- **File:** `tests/tdd/test_issue_338_go_geosphere_counter.py`
- **Identifier:** Testfunktionen und Modul-Marker der genannten Dateien

Schicht: ausschliesslich **Testschicht** (`tests/`). Kein Produktivcode in dieser Scheibe —
`src/app/loader.py::get_trips_dir()` faellt erst in B2, die Waechter-Ausnahme in
`tests/test_trips_path_revival_guard.py:91` bleibt unangetastet.

## Estimated Scope

- **LoC:** ~150 hinzugefuegt / ~40 entfernt (rund die Haelfte Nachweis: RED-Tests, Gegenproben)
- **Files:** 5
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `tests/conftest.py:18-33` `_use_fixture_provider` | Fixture | setzt `GZ_TEST_FIXTURE_DIR` fuer jeden nicht-`live`-Test; `live` entzieht ihn |
| `tests/conftest.py:121-146` `_isolate_data_root` | Fixture | isolierte Datenwurzel; steigt bei `live`/`real_data_root` aus |
| `src/app/loader.py:1166` `get_briefings_dir()` | Funktion | der lebende Pfad, auf den umgestellt wird |
| `src/services/trip_alert.py:1247-1249` | Produktivcode | Zeitfenster-Guard, an dem der Alarm-Test heute scheitert (nur lesend) |
| `src/providers/call_log.py:47` | Produktivcode | Stack-Zuordnung `_fetch_fresh_weather` → `"alarm"` (nur lesend) |
| `tests/test_briefing_route_cutover.py` | Test | Vorbildmuster: Trip-Fixture in der isolierten `briefings/`-Wurzel |
| `.github/ci_tdd_excludes.txt` | Liste | macht Stilllegungen sichtbar |

## Implementation Details

### Der gemeinsame Fehler

Alle drei Dateien suchen Trip-Bestand, statt ihn anzulegen. In der isolierten Datenwurzel gibt es
keinen Bestand — also skippen sie. Den Suchpfad von `trips/` auf `briefings/` umzubiegen behebt das
**nicht**; die Tests muessen ihre Fixture selbst schreiben.

```
# falsch (heute):   Bestand suchen, sonst skip
uid, tid = _find_test_trip()          # sucht in get_trips_dir() -> immer leer
if not uid: pytest.skip(...)

# richtig:          Fixture selbst anlegen, kein Skip moeglich
path = get_briefings_dir(uid) / f"{tid}.json"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(trip_dict))   # trip_dict enthaelt "kind": "route"
```

### Datei A — `test_bug_338_openmeteo_call_counter.py`

Drei getrennte Eingriffe:

1. **Modul-Marker faellt.** `pytestmark = pytest.mark.live` (`:24`) wird entfernt. Marker kommen
   nur noch an die Tests, die im Fixture-Modus **nachweislich** Netz brauchen — je Test mit
   Begruendung in derselben Zeile. Die Zugehoerigkeit wird gemessen
   (`--disable-socket --allow-hosts=127.0.0.1,::1`), nicht geschaetzt.
2. **Zeitabhaengigkeit beseitigen.** `_make_segment()` (`:39-52`) baut das Segment fest auf
   06:00–14:00 UTC des laufenden Tages; `trip_alert.py:1247-1249` ueberspringt es danach. Der
   Helfer konstruiert das Fenster kuenftig relativ zu `now_utc`, sodass zu jeder Tageszeit gilt:
   `start_time.date() <= heute` **und** `end_time > now_utc`.
3. **AC-2-Vorschau baut seine Fixture selbst** (`:199-241`) statt `get_trips_dir("henning")` zu
   befragen und zu skippen.

### Datei B — `test_pytest_collection_and_timeout_safety.py`

`_C2_KEEP_MODULE_LIVE` (`:155-162`) haelt den Modul-Marker aktiv fest. Die Begruendung
(„Voll-Dialer, per Probe/Code 100 % Netzcall", #1211 Scheibe 2c) ist widerlegt: gemessen laufen
`test_ac2_trend_path_sets_source_trend` und `test_ac4_analyze_script_breaks_down_by_source_endpoint_hour`
**ohne Socket** durch. Zusaetzlich war die Messung von damals zirkulaer — sie lief mit gesetztem
`live`-Marker, und genau dieser Marker entzieht den Offline-Fixture-Modus (`conftest.py:25-29`).

Der Eintrag wandert nach `_C2_SPLIT_FILES` mit exakter Erwartungszahl. Die neue Begruendung nennt
den Messweg, damit die naechste Sitzung sie nachpruefen kann statt sie zu glauben.

### Datei C — `test_issue_338_go_geosphere_counter.py`

`test_ac3_existing_six_tests_still_green` (`:84-114`) prueft `returncode == 0`. Ein geskippter Test
liefert ebenfalls 0 — der Waechter ist fuer genau den Fall blind, der hier vorlag. Er wird um eine
Skip-Erkennung ergaenzt (Subprozess-Ausgabe auf `skipped` pruefen bzw. `-W error` / `--strict`
gleichwertig) und verliert nach dem Marker-Split sein `-o addopts=`, weil die Zieltests dann reguleaer
laufen.

### Datei D — `test_issue_346_fixture_provider.py`

`_find_test_trip()` (`:24-32`) faellt ersatzlos; AC-6 (`:117-143`) legt seine Trip-Fixture selbst
unter `get_briefings_dir()` an. Die Zusicherung selbst — Vorschau im Fixture-Modus loest **null**
echte Open-Meteo-Calls aus — bleibt unveraendert.

### Datei E — `test_issue_1133_testdata_cleanup.py`

Die Isolationssonde (`:57-75`, AC-1) wird von `get_trips_dir()` auf `get_briefings_dir()`
umgehaengt. Beide Beweisteile bleiben: Teil A (absoluter Pfad, ausserhalb des Repo-Baums), Teil B
(echter `save_trip()`-Roundtrip).

## Expected Behavior

- **Input:** ein regulaerer Testlauf (`uv run pytest <datei>`) ohne Marker-Override, zu beliebiger
  Tageszeit, mit isolierter Datenwurzel und ohne vorhandenen Trip-Bestand
- **Output:** die betroffenen Tests werden gesammelt, laufen und pruefen ihre Zusicherung; kein
  Test skippt mangels Datenbestand
- **Side effects:** keine. Kein Schreibzugriff auf den echten `data/users/`-Baum, keine Mails,
  kein Versand. Netzzugriff nur in den Tests, die nachweislich Netz brauchen und dafuer markiert
  sind.

## Acceptance Criteria

- **AC-1:** Given `tests/tdd/test_bug_338_openmeteo_call_counter.py` traegt keinen Modul-weiten
  `live`-Marker mehr / When ein Standardlauf `uv run pytest tests/tdd/test_bug_338_openmeteo_call_counter.py --collect-only -q` ausgefuehrt wird /
  Then werden Tests gesammelt statt `no tests collected (6 deselected)` gemeldet, und jeder noch
  `live`-markierte Test traegt eine Begruendung in seiner Markerzeile.
  - Test: Kollektions-Test vergleicht die gesammelte Anzahl im Standardlauf gegen 0 und prueft, dass
    die Datei im Standardlauf ueberhaupt erscheint.

- **AC-2:** Given ein Test ist weiterhin `live`-markiert / When er mit
  `--disable-socket --allow-hosts=127.0.0.1,::1` im Fixture-Modus ausgefuehrt wird / Then scheitert
  er nachweislich an fehlendem Netzzugriff — ein Test, der offline besteht, darf den Marker nicht
  tragen.
  - Test: Messlauf ueber alle verbliebenen `live`-Tests der Datei; ein offline bestehender Test mit
    Marker ist ein Fehlschlag.

- **AC-3:** Given die Systemzeit liegt nach 14:00 UTC / When
  `test_ac2_alarm_path_sets_source_alarm` ausgefuehrt wird / Then besteht er und findet mindestens
  einen Log-Eintrag mit `source == "alarm"` — die heutige Kippkante um 14:00 UTC verschwindet.
  - Test: derselbe Test wird mit zwei verschiedenen gesetzten Uhrzeiten ausgefuehrt (eine vor, eine
    nach der alten Kippkante) und besteht beide Male.

- **AC-4:** Given es existiert kein Trip-Bestand in der isolierten Datenwurzel / When
  `test_ac2_preview_path_sets_source_vorschau` ausgefuehrt wird / Then legt der Test seine
  Trip-Fixture unter `get_briefings_dir()` selbst an, skippt nicht und belegt `source == "vorschau"`.
  - Test: Testlauf meldet fuer diesen Test weder `skipped` noch einen Zugriff auf `get_trips_dir`.

- **AC-5:** Given es existiert kein Trip-Bestand in der isolierten Datenwurzel / When
  `tests/tdd/test_issue_346_fixture_provider.py` ausgefuehrt wird / Then skippt **kein** Test der
  Datei, und AC-6 belegt, dass `render_email_preview` im Fixture-Modus null echte
  Open-Meteo-Calls ausloest.
  - Test: Lauf mit `-rs` meldet null `SKIPPED`; die Call-Log-Pruefung des AC-6-Tests bleibt in Kraft.

- **AC-6:** Given `get_trips_dir()` wird in Scheibe B2 entfernt / When
  `tests/tdd/test_issue_1133_testdata_cleanup.py` ausgefuehrt wird / Then besteht der
  Isolationsbeweis unveraendert, weil die Sonde ueber `get_briefings_dir()` laeuft.
  - Test: AC-1 der Datei prueft weiterhin absoluten Pfad, Lage ausserhalb des Repo-Baums und
    `save_trip()`-Roundtrip — jetzt ueber den lebenden Pfad.

- **AC-7:** Given ein Zieltest des Subprozess-Wrappers skippt / When
  `test_ac3_existing_six_tests_still_green` ausgefuehrt wird / Then schlaegt der Wrapper fehl statt
  den Exit-Code 0 eines Skips als Beweis zu nehmen.
  - Test: Gegenprobe — ein kuenstlich skippender Zieltest macht den Wrapper rot.

- **AC-8:** Given `tests/tdd/test_pytest_collection_and_timeout_safety.py` fuehrt
  `test_bug_338_openmeteo_call_counter.py` nicht mehr als Voll-Dialer / When der
  Kollektions-Waechter laeuft / Then ist die erwartete Testzahl der Datei exakt festgeschrieben und
  wird rot, sobald jemand den Modul-Marker zurueckholt.
  - Test: der bestehende Waechter mit aktualisiertem Eintrag; Gegenprobe durch Wiedereinsetzen des
    Modul-Markers.

## Known Limitations

- **Abgrenzung gemessen:** von 41 Testdateien mit Modul-weitem `pytestmark = pytest.mark.live`
  beruehrt **genau eine** zusaetzlich den toten `trips/`-Pfad —
  `test_bug_338_openmeteo_call_counter.py`. Die Doppel-Stilllegung ist ein Einzelfall, die Scheibe
  muss dafuer nicht erweitert werden. Ob es unter den uebrigen 40 Dateien Stilllegungen aus
  anderen Gruenden gibt, ist hier nicht untersucht.
- Diese Scheibe beruehrt die 9 Referenz-Fixturen unter `tests/fixtures/data_root/users/*/trips/`
  und die Spiegellogik in `tests/conftest.py:83-91` **nicht**. Sie speisen den Produktiv-Lesepfad
  fremder Tests und gehoeren nach B2.
- `src/app/loader.py::get_trips_dir()` bleibt bestehen; erst B2 entfernt sie samt der einen
  Waechter-Ausnahme.
- AC-2 legt die Marker-Zugehoerigkeit per Messung fest. Welche Tests nach dem Wegfall des
  Modul-Markers im Fixture-Modus noch Netz brauchen, ist heute nicht sicher bekannt — die heutige
  Messung entstand unter dem Marker, der den Fixture-Modus abschaltet. Die Zahl in AC-1/AC-8 wird
  in der RED-Phase gemessen und dort festgeschrieben.
- Wird beim Reaktivieren ein weiterer echter Fehlschlag sichtbar, ist das ein Befund. Er wird
  gemeldet und nicht durch Abschwaechen der Erwartung beseitigt; ob er in dieser Scheibe behoben
  oder als eigenes Issue gefuehrt wird, entscheidet sein Umfang.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Es wird keine Grundsatzentscheidung geaendert. Korrigiert wird eine
  Test-Schicht-Einstufung aus #1211 Scheibe 2c, die als Codekommentar in
  `test_pytest_collection_and_timeout_safety.py:155-162` steht: die Einstufung von
  `test_bug_338_openmeteo_call_counter.py` als „Voll-Dialer, 100 % Netzcall" ist durch Messung
  widerlegt. Die Korrektur wird an der Stelle begruendet, nicht still vorgenommen. ADR-0023
  (Cutover `trips/` → `briefings/`) wird bestaetigt, nicht beruehrt.

## Changelog

- 2026-08-16: Initial spec created (#1708 Scheibe B1)
