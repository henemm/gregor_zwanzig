# Context: fix-1708-b1-tote-fixture-befunde

Issue: **#1708 Scheibe B1** (Teilarbeit — schliesst #1708 nicht; das tut Scheibe C).
Vorgaenger: Scheibe A (`05086722` + Doku-PR #1907), beide in `origin/main`.

## Request Summary

Drei Testdateien haengen am toten Pfad `data/users/<uid>/trips/<id>.json`. Fuer jede ist zu
**belegen**, warum sie heute gruen bzw. still ist, und das dahinterliegende Deckungsloch zu
schliessen. Nicht "Pfad umschreiben" — die drei Faelle sind drei verschiedene Fehlerbilder.

## Gemessener Befund je Datei

### A. `tests/tdd/test_bug_338_openmeteo_call_counter.py` — laeuft NIRGENDS

Zwei unabhaengige Ausschluesse uebereinander:

| # | Mechanismus | Beleg |
|---|---|---|
| 1 | `pytestmark = pytest.mark.live` auf **Modulebene** deselektiert die ganze Datei | `test_bug_338_openmeteo_call_counter.py:24` · gemessen: `uv run pytest <datei> --collect-only` → **`no tests collected (6 deselected)`** |
| 2 | AC-2 steigt zusaetzlich per `pytest.skip` aus, wenn `get_trips_dir("henning")/"5f534011.json"` fehlt | `:211-213` (einziger `skip` der Datei) |

Die Datei steht **nicht** auf `.github/ci_tdd_excludes.txt` (87 Zeilen, kein Treffer) — der
Ausschluss ist damit unsichtbar. `/e2e-verify` faehrt nur `tests/tdd/test_issue_686_telegram_functional_live.py`
(`.claude/commands/e2e-verify.md:114`), also auch nicht diese Datei.

Der einzige Aufrufer ist ein Wrapper: `tests/tdd/test_issue_338_go_geosphere_counter.py:84-114`
(`test_ac3_existing_six_tests_still_green`) startet die Datei im Subprozess mit `-o addopts=`,
um die Marker-Filterung zu neutralisieren, und prueft `returncode == 0`. Der Wrapper traegt
selbst `@pytest.mark.live` (`:84`) — laeuft also ebenfalls in keinem regulaeren Lauf. Und selbst
wenn er liefe: ein **geskippter** Test liefert Exit 0. Der Wrapper kann den Skip aus (2) also
grundsaetzlich nicht sehen.

`henning/5f534011` existiert in **keiner** Testfixture (weder unter `trips/` noch `briefings/`) —
der Skip aus (2) feuert damit auch im Live-Lauf immer.

**Verlorene Zusicherung:** AC-2 — dass `PreviewService.render_email_preview` `source == "vorschau"`
liefert (nicht `"briefing"`), obwohl intern `_fetch_weather` laeuft. Plus die uebrigen 5 Tests
der Datei, die pauschal mit deselektiert werden.

### B. `tests/tdd/test_issue_346_fixture_provider.py` — skippt deterministisch

Gemessen: `uv run pytest <datei> -q -rs` → `9 passed, 1 skipped`, Grund
`SKIPPED [1] :121: Kein echter Test-Trip in data/users vorhanden`.

`_find_test_trip()` (`:24-32`) sucht `henning/5f534011` und `default/gr221-mallorca` **im toten
Pfad** via `get_trips_dir(uid)`. Unter der autouse-Isolation (`tests/conftest.py:121`) zeigt die
Datenwurzel auf ein leeres tmp-Verzeichnis → `(None, None)` → Skip. Das passiert bei **jedem**
Lauf, auch schon vor der Umbenennung der Produktivablage.

**Verlorene Zusicherung:** AC-6 (`:117`) — dass `render_email_preview` mit gesetztem
`GZ_TEST_FIXTURE_DIR` **offline** laeuft und keinen einzigen echten Open-Meteo-Call ausloest.
Das ist die Kernzusage des gesamten FixtureProvider-Features; sie ist unbewacht.

### C. `tests/tdd/test_issue_1133_testdata_cleanup.py` — gruen, aber falsch verankert

Gemessen: `13 passed`, keine Skips. Der Test ist **nicht** aus falschem Grund gruen.

`get_trips_dir()` dient dort als **Sonde** fuer die Datenwurzel-Isolation (`:57-75`, ein Test,
AC-1): Teil A prueft, dass der Pfad absolut ist und nicht in den Repo-Baum zeigt; Teil B macht
einen echten `save_trip()`-Roundtrip. Der Beweis haengt nicht an `trips` — jedes ueber
`app.loader` aufgeloeste Unterverzeichnis der Datenwurzel leistet dasselbe.

**Risiko:** Faellt `get_trips_dir()` in Scheibe B2 weg, faellt der Isolationsbeweis mit — es sei
denn, die Sonde wird vorher auf `get_briefings_dir()` umgehaengt.

## Der gemeinsame Untergrund: die Referenz-Fixturen liegen selbst im toten Pfad

`tests/fixtures/data_root/users/*/trips/*.json` — **9 versionierte Trip-Dateien**
(`default/gr221-mallorca.json`, 8x `validator-issue110/*`). Kein einziges `briefings/`-Verzeichnis
dort.

`tests/conftest.py:52-91` (`_materialize_real_data_root_fixtures`, Session-autouse) kopiert sie in
den **echten** `<repo>/data/`-Baum und spiegelt danach jede `*/trips/*.json` zusaetzlich nach
`*/briefings/<id>.json` (`:83-91`, ADR-0023). Der tote Pfad ist hier also **kein Leichnam, sondern
die Saatgutquelle** des Spiegels — eine Umstellung muss Quelle und Spiegellogik zusammen anfassen.

In den **isolierten** tmp-Wurzeln passiert diese Materialisierung nicht. Deshalb findet B nie etwas,
und deshalb hilft es dort nicht, den Suchpfad auf `briefings/` zu drehen — der Test muss seine
Fixture selbst anlegen.

## Related Files

| Datei | Relevanz |
|------|-----------|
| `tests/tdd/test_bug_338_openmeteo_call_counter.py` | Fall A — Modul-`live` + Skip, 6 Tests laufen nirgends |
| `tests/tdd/test_issue_338_go_geosphere_counter.py:84-114` | Wrapper, der A's Gruenheit behauptet; selbst `live`, blind fuer Skips |
| `tests/tdd/test_issue_346_fixture_provider.py` | Fall B — AC-6 skippt deterministisch |
| `tests/tdd/test_issue_1133_testdata_cleanup.py:57-75` | Fall C — Isolationssonde, muss umgehaengt werden |
| `tests/conftest.py:52-91` | Materialisierung + `trips/`→`briefings/`-Spiegel |
| `tests/conftest.py:121-146` | `_isolate_data_root`; steigt bei `live`/`real_data_root` aus |
| `tests/fixtures/data_root/users/*/trips/*.json` | 9 Referenz-Trips, liegen im toten Pfad |
| `src/app/loader.py:1155` `get_trips_dir()` | toter Pfad; faellt in B2 |
| `src/app/loader.py:1166` `get_briefings_dir()` | der lebende Ersatz |
| `tests/test_trips_path_revival_guard.py:91` | traegt genau **einen** Ausnahmeeintrag fuer `get_trips_dir()` |
| `.github/ci_tdd_excludes.txt` | 87 Zeilen; keine der drei Dateien steht drin |

## Existing Patterns

- **Trip-Fixture nach `briefings/` schreiben:** Vorbild `tests/conftest.py:83-91` — `kind`-Default
  setzen, dann `get_briefings_dir(uid)/<id>.json`. Auch `tests/test_briefing_route_cutover.py:108-110`
  leitet `briefings` aus der Datenwurzel ab.
- **Marker auf Funktionsebene, nicht aufs Modul** — Lehre aus #1667 S2: ein Modul-`live` reisst
  unschuldige Waechter mit und schaltet zusaetzlich die Daten-Isolation ab.
- **Ausschluss sichtbar machen:** wer eine Datei aus dem regulaeren Lauf nimmt, traegt sie in
  `.github/ci_tdd_excludes.txt` ein — sonst ist die Stilllegung unsichtbar.

## Dependencies

- **Upstream:** `app.loader.get_data_root/get_briefings_dir`, `tests/conftest.py`-Fixtures
  (`_materialize_real_data_root_fixtures`, `_isolate_data_root`), `services.preview_service`,
  `providers.fixture`/`providers.call_log`.
- **Downstream:** `tests/tdd/test_issue_338_go_geosphere_counter.py` (Subprozess-Wrapper auf A);
  Scheibe **B2** haengt an C (Sonde umhaengen) und an der Fixture-Quelle, bevor `get_trips_dir()`
  entfernt werden kann.

## Existing Specs

- `docs/specs/modules/fix_1708_a_trips_pfad_waechter.md` — Scheibe A, definiert die Ausnahmeliste
- `docs/specs/_archive/modules/bug_338_openmeteo_call_counter.md` + `_archive/tests/…_tests.md`
- `docs/specs/_archive/tests/issue_346_fixture_provider_tests.md`
- `docs/adr/` — ADR-0023 (Cutover `trips/` → `briefings/`)

## Risks & Considerations

1. **Ein reaktivierter Test kann echt rot werden.** #338 AC-2 und #346 AC-6 laufen seit ihrer
   Entstehung nie. Wird die Zusicherung heute verletzt, ist das ein **Befund**, kein Grund, den
   Test wieder abzuschwaechen. Kernschicht-Regel: sofort fixen oder loeschen — nicht liegenlassen.
2. **Modul-`live` bei A entfernen aendert die Laufzeit-Schicht.** 6 Tests kommen neu in den
   Commit-Gate-Lauf. Sie duerfen dann keine echten API-Calls machen — der FixtureProvider-Modus
   (`GZ_TEST_FIXTURE_DIR`) ist der vorgesehene Weg. Ob alle 6 offline laufen, ist zu messen, nicht
   anzunehmen.
3. **Fixture-Quelle anfassen beruehrt Fremdtests.** Die 9 Dateien unter
   `tests/fixtures/data_root/users/*/trips/` speisen den Spiegel in `conftest.py`. Wer sie
   verschiebt, muss die Spiegellogik mitziehen, sonst laufen unbeteiligte `real_data_root`-Tests
   ins Leere.
4. **Gruener Testlauf beweist nichts.** Fuer jeden reparierten Test ist per Mutations-Gegenprobe
   zu zeigen, dass er die Zusicherung **am Wirkort** bewacht — sonst ist der Skip nur durch ein
   trivial gruenes Assert ersetzt.
5. **LoC-Limit 250.** Drei Testdateien + ggf. Fixture-Umzug + Gegenproben; der Nachweis kostet
   mehr als der Eingriff. Zuschnitt eng halten.
6. **Kein Produktivcode in B1.** `get_trips_dir()` bleibt bis B2 stehen; die Wächter-Ausnahme
   bleibt unangetastet.

---

# Analysis

## Type

**Bug** — Tests, die eine Zusicherung tragen sollen, laufen nicht bzw. skippen still. Kein
Produktivfehler gefunden (siehe Befund 3 unten).

## Die drei Befunde, alle gemessen

### Befund 1 — `test_bug_338` ist doppelt stillgelegt, und der Wrapper kann es nicht sehen

`pytestmark = pytest.mark.live` (`:24`) ⇒ `no tests collected (6 deselected)`. Nicht auf
`.github/ci_tdd_excludes.txt`, nicht in `/e2e-verify` (`.claude/commands/e2e-verify.md:114` faehrt
nur `test_issue_686_…`). Der einzige Aufrufer `test_issue_338_go_geosphere_counter.py:84-114`
prueft `returncode == 0` eines Subprozesses mit `-o addopts=` — ein **geskippter** Test liefert
Exit 0, der Wrapper ist fuer den Skip aus `:211-213` konstruktionsbedingt blind. Der Wrapper traegt
selbst `@pytest.mark.live` (`:84`), laeuft also ebenfalls nie.

**Tatsaechlicher Zustand, wenn man sie laufen laesst** (`-o addopts= --timeout=180`):
`4 passed, 1 failed, 1 skipped`. Mit dem Standard-Timeout 30 s zusaetzlich instabil
(`2 failed/3 passed`, dann `3 failed/2 passed`) — Timeout-Artefakte echter Netzaufrufe
(`src/providers/dwd.py:227` braucht laenger als 30 s).

### Befund 2 — die Begruendung des Marker-Waechters ist zirkulaer

`tests/tdd/test_pytest_collection_and_timeout_safety.py:155-162` haelt den Modul-Marker per
`_C2_KEEP_MODULE_LIVE` aktiv fest, Begruendung: „6 Voll-Dialer-Dateien (per Probe/Code 100 %
Netzcall)" (#1211 Scheibe 2c).

Nachgemessen mit `--disable-socket --allow-hosts=127.0.0.1,::1`:

| Test | braucht Netz? |
|---|---|
| `test_ac1_fetch_forecast_appends_one_jsonl_line` | **ja** |
| `test_ac2_alarm_path_sets_source_alarm` | nein (scheitert an der Uhr, s. Befund 3) |
| `test_ac2_trend_path_sets_source_trend` | **nein** — passed ohne Socket |
| `test_ac2_preview_path_sets_source_vorschau` | unbekannt (skippt) |
| `test_ac3_unwritable_log_target_is_swallowed` | **ja** |
| `test_ac4_analyze_script_breaks_down_by_source_endpoint_hour` | **nein** — reine Dateiarbeit |

**Praezisierung (2026-08-16, nach der GREEN-Messung):** Die Spalte oben ist irrefuehrend, weil sie
**mit** gesetztem Modul-Marker gemessen wurde — also mit echtem `OpenMeteoProvider`. Dass Trend
ohne Socket besteht, liegt daran, dass `_log_api_call` den Eintrag **auch beim gescheiterten
Aufruf** schreibt; die Zusicherung wird dabei echt geprueft. Schaltet man den Marker ab, liefert
`get_provider("openmeteo")` den `FixtureProvider` — und der ruft `call_log` **nirgends** auf
(`src/providers/fixture.py`, verifiziert). Dann steht ueberhaupt kein Eintrag im Log und die drei
Quellen-Tests scheitern, unabhaengig vom Netz. Richtig gelesen heisst die Tabelle also: „braucht
einen echten Provider-**Aufrufversuch**", nicht „braucht eine erreichbare Gegenstelle".

„100 % Netzcall" ist damit widerlegt. Schwerer wiegt: die Messung von damals lief **mit** gesetztem
`live`-Marker — und `tests/conftest.py:25-29` entzieht `live`-Tests genau den Offline-Fixture-Modus.
Der Marker stellt die Bedingung her, mit der er begruendet wird. Ohne ihn setzt
`tests/conftest.py:33` `GZ_TEST_FIXTURE_DIR` automatisch und `tests/conftest.py:143-146` gibt die
Datenwurzel-Isolation zurueck — beide Defekte der Datei haengen an derselben Zeile.

### Befund 3 — der eine harte Fehler ist Zeitabhaengigkeit, kein Produktivfehler

`test_ac2_alarm_path_sets_source_alarm` scheitert deterministisch in 0,5 s ohne Netz:
`Erwartete source 'alarm' aus _fetch_fresh_weather, sah: set()`.

Ursache: `src/services/trip_alert.py:1247-1249` ueberspringt Segmente mit
`cached.segment.end_time < now_utc`. Der Helfer `_make_segment()`
(`test_bug_338_openmeteo_call_counter.py:39-52`) baut das Segment fest auf **06:00–14:00 UTC des
laufenden Tages**. Gemessen um 15:15 UTC ⇒ `continue` ⇒ kein Provider-Aufruf ⇒ leeres Log.

**Kippkante 14:00 UTC** — vormittags gruen, nachmittags rot. Der Alarm-Pfad selbst ist intakt; die
`source`-Zuordnung `("_fetch_fresh_weather", "alarm")` steht unveraendert in
`src/providers/call_log.py:47`. Der Schwestertest Trend ist nicht betroffen, weil
`_make_trend_trip()` (`:74-86`) ein Datum in der Zukunft setzt statt einer Tageszeit.

### Befund 4 — `test_issue_346` AC-6 skippt deterministisch, nicht zufaellig

`_find_test_trip()` (`:24-32`) sucht ueber `get_trips_dir(uid)` und findet unter der
autouse-Isolation nie etwas ⇒ `(None, None)` ⇒ Skip an `:121`. Betroffen ist **AC-6**
(`:117-143`): dass `render_email_preview` mit `GZ_TEST_FIXTURE_DIR` offline laeuft und **keinen**
echten Open-Meteo-Call ausloest. Das ist die Kernzusage des FixtureProvider-Features.

Den Pfad auf `briefings/` umzubiegen genuegt **nicht** — die isolierte tmp-Wurzel enthaelt
ueberhaupt keine Fixturen (`_materialize_real_data_root_fixtures`, `tests/conftest.py:52-91`,
schreibt nur in den echten Baum). Der Test muss seine Fixture selbst anlegen. Vorbild:
`tests/test_briefing_route_cutover.py` (gemessen: 7 passed).

### Befund 5 — `test_issue_1133` ist korrekt gruen, aber falsch verankert

`13 passed`, keine Skips. `get_trips_dir()` dient dort an genau einer Stelle (`:57-75`, AC-1) als
Sonde fuer die Datenwurzel-Isolation. Der Beweis haengt nicht an `trips`; er faellt aber mit
Scheibe B2, wenn er nicht vorher auf `get_briefings_dir()` (`src/app/loader.py:1166`) umgehaengt
wird.

## Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `tests/tdd/test_bug_338_openmeteo_call_counter.py` | MODIFY | Modul-`live` faellt; Marker nur noch auf die Tests, die nachweislich waehlen, mit Begruendung an der Zeile. Zeitabhaengigkeit in `_make_segment()` beseitigen (Segment relativ zu `now` im Fenster). AC-2-Vorschau baut seine Trip-Fixture selbst unter `get_briefings_dir()`. |
| `tests/tdd/test_pytest_collection_and_timeout_safety.py` | MODIFY | Eintrag von `_C2_KEEP_MODULE_LIVE` (`:161`) nach `_C2_SPLIT_FILES` mit exakter Erwartungszahl; Begruendung am Eintrag ersetzt die widerlegte „100 % Netzcall"-Aussage. |
| `tests/tdd/test_issue_338_go_geosphere_counter.py` | MODIFY | Wrapper `:84-114`: `-o addopts=` wird nach dem Split ueberfluessig; Exit-Code-Pruefung um eine Skip-Erkennung ergaenzen, damit sie nicht weiter blind ist. |
| `tests/tdd/test_issue_346_fixture_provider.py` | MODIFY | `_find_test_trip()` ersetzen: Fixture selbst unter `get_briefings_dir()` anlegen statt im toten Pfad suchen. AC-6 laeuft damit. |
| `tests/tdd/test_issue_1133_testdata_cleanup.py` | MODIFY | Sonde `:57-75` von `get_trips_dir()` auf `get_briefings_dir()` umhaengen, Beweiskraft (absolut + ausserhalb Repo-Baum + Roundtrip) unveraendert. |

**Nicht angefasst in B1:** `src/app/loader.py` (`get_trips_dir()` faellt erst in B2), die
Waechter-Ausnahme in `tests/test_trips_path_revival_guard.py:91`, die 9 Referenz-Fixturen unter
`tests/fixtures/data_root/users/*/trips/` samt Spiegellogik (`tests/conftest.py:83-91`) — die
gehoeren zu B2, weil sie den Produktiv-Lesepfad und Fremdtests beruehren.

## Scope Assessment

- Files: **5** (alle unter `tests/`)
- Estimated LoC: **+150 / -40** — davon rund die Haelfte Nachweis (RED-Tests, Gegenproben)
- Risk Level: **MEDIUM** — 6 bisher stillgelegte Tests kommen in den Commit-Gate-Lauf; jeder
  Fehlschlag dort ist ein Befund, kein Grund zum Abschwaechen

## Technical Approach

1. **Zuerst den Ausschluss aufheben, dann die Tests reparieren** — solange die Datei deselektiert
   ist, beweist kein gruener Lauf etwas. Reihenfolge: Marker splitten → messen, was rot wird →
   jede Roete einzeln als Befund behandeln.
2. **Marker auf Funktionsebene, mit Begruendung an der Zeile.** Lehre aus #1667 S2. Wer eine
   Datei stilllegt, traegt sie ausserdem in `.github/ci_tdd_excludes.txt` ein.
3. **Zeitabhaengigkeit an der Quelle beheben:** `_make_segment()` konstruiert das Fenster relativ
   zu `now_utc`, sodass `start_time.date() <= heute` und `end_time > now` zu **jeder** Tageszeit
   gelten. Nicht die Erwartung abschwaechen — den Messwert neu verankern.
4. **Fixturen selbst anlegen statt suchen.** Beide Faelle (338 AC-2-Vorschau, 346 AC-6) schreiben
   ihren Trip nach `get_briefings_dir(uid)/<id>.json` in der isolierten Wurzel. Damit ist der Test
   unabhaengig von jedem Bestand — das ist der eigentliche Fix, nicht der Pfadwechsel.
5. **Sonde umhaengen, nicht loeschen** (1133).
6. **Mutations-Gegenprobe je repariertem Test:** die bewachte Eigenschaft verfaelschen und
   nachweisen, dass der Test rot wird. Ein Skip durch ein trivial gruenes Assert zu ersetzen waere
   derselbe Fehler in neuer Form.

## Open Questions

Keine offenen Fragen an den PO. Eine Entscheidung wird bewusst korrigiert und ist in der Spec zu
begruenden: die Einstufung von `test_bug_338_openmeteo_call_counter.py` als „Voll-Dialer" aus
#1211 Scheibe 2c ist durch Messung widerlegt (Befund 2). Das ist keine ADR-Ebene, sondern eine
Test-Schicht-Einstufung in einem Codekommentar — sie wird ersetzt, nicht still umgangen.
