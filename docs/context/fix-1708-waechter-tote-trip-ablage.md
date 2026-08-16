# Context: fix-1708-waechter-tote-trip-ablage

Issue: [#1708](https://github.com/henemm/gregor_zwanzig/issues/1708) — Scheibe A (Teilarbeit, schließt das Issue **nicht**)

## Request Summary

Seit #1250 Scheibe 7a (ADR-0023) leben Trips ausschließlich in `data/users/<uid>/briefings/<id>.json`.
Der Pfad `data/users/<uid>/trips/<id>.json` ist toter Bestand, sieht aber vollständig und plausibel aus
und hat nachweislich vier Fehlaussagen und zwei Datenänderungen ins Leere verursacht.
Scheibe A errichtet den Wächter, der die Falle nicht neu entstehen lässt, und entfernt die
Produktivstellen, die sie laufend neu herstellen.

## Related Files

### Go — Produktivcode (Scheibe A entfernt/ändert)

| Datei:Zeile | Relevanz |
|---|---|
| `internal/store/trip.go:14-16` | `TripsDir()` bildet den toten Pfad. **Null Aufrufer im gesamten Repo** — weder Produktiv noch Test, nur Kommentar-Erwähnungen. Risikofreie Löschung. |
| `internal/store/user.go:84` | `ProvisionUserDirs` legt `"trips"` für **jeden neuen Nutzer** an. Das ist die Stelle, die die Falle laufend neu herstellt. |

### Go — Aufrufer und Mitbetroffene

| Datei:Zeile | Relevanz |
|---|---|
| `internal/handler/auth.go:109`, `auth_oauth.go:220`, `auth_magic.go:222`, `passkey.go:568` | Die 4 Produktiv-Aufrufer von `ProvisionUserDirs` — alle vier Registrierungswege |
| `internal/handler/profile_test.go:378,395` | ⚠️ **Zementiert den Bestand:** `TestRegisterCreatesUserDirs` assertiert per `os.Stat`, dass `trips/` nach Registrierung existiert. Wird beim Entfernen rot und muss mit umgestellt werden. |
| `internal/scheduler/selftest.go:42` | Probt bereits gegen `briefings/`; nur die lokale Variable heißt noch `tripsDir`. Fehlendes Verzeichnis wird übersprungen (`:45-46`) — **kein** Fehlalarm zu erwarten. |
| `internal/handler/delete_account_test.go:21`, `internal/store/store_trip_briefings_test.go:30,98` | Legen `trips/` selbst per `os.MkdirAll` an, unabhängig von `ProvisionUserDirs` — kein Bruch, aber Wächter-relevant (Scanfläche darf Testcode nicht treffen). |

### Go — heutiger Lese-/Schreibpfad (Soll-Zustand, unverändert)

`internal/store/briefing_subscription.go:19` `briefingsDir()` · `:25` `BriefingsDir()` ·
`internal/store/trip.go:117` `LoadTrips` · `:178` `LoadTrip` · `:222` `SaveTrip` (Kommentar `:224`:
„trips/<id>.json wird NICHT mehr angefasst (Rollback-Faehigkeit, AC-26)") · `:265` `DeleteTrip`

### Python

| Datei:Zeile | Relevanz |
|---|---|
| `src/app/loader.py:1155-1163` | `get_trips_dir()` — **kein Aufrufer** in `src/`, `api/`, `scripts/`, `.claude/`. Docstring begründet den Verbleib mit „Rollback-Fähigkeit, AC-26" und „historical per-user directory bootstrap". |
| `src/app/loader.py:1166` | `get_briefings_dir()` — der lebende Pfad; Aufrufer in `loader.py:1409,1728,1771`, `src/services/preview_service.py:67`, `src/services/trip_report_scheduler.py:313`, `api/routers/validator.py:52` |
| `tests/conftest.py:121-172` | autouse `_isolate_data_root` (#1133): setzt `app.loader._DATA_ROOT` auf ein tmp-Verzeichnis; alle Helfer folgen automatisch. Vergleicht zusätzlich den echten `data/users`-Baum vor/nach (#1265 Teil C). |

### Python — die 17 Testdateien mit `get_trips_dir` (Scheibe **B**, hier nur zur Abgrenzung)

Nur **12** rufen die Funktion wirklich auf; 5 nennen sie in Kommentaren
(`test_bundle_791_847_844_alerts.py:72`, `test_issue_363_signal_telegram_preview.py:28`,
`test_issue_818_radar_briefing_integration.py:97`, `test_issue_822_radar_nowcast_segment.py:101`,
`test_loader_display_config_default.py:244`).

Von den 12 sind die meisten **toter Aufräum-Code** (`unlink()`/`rmtree` auf eine nie geschriebene Datei):
`test_feature_656_radar_nowcast.py:188,215,302` · `test_feature_660_convective_stage.py:234` ·
`test_inbound_gate_errors.py:48` · `test_issue_612_report_on_demand.py:155,293,327` ·
`test_issue_731_unified_commands.py:184` · `test_issue_882_pause_skip.py:69-72` ·
`test_trip_command_processor.py:73` · `test_issue_1001_telegram_bubbles.py:437`

**Verdachtsfälle „grün aus dem falschen Grund" (Scheibe B, echte Untersuchung nötig):**
- `test_bug_338_openmeteo_call_counter.py:211` — `if not trip_file.exists(): pytest.skip(...)` → der Test **skippt vermutlich immer**
- `test_issue_346_fixture_provider.py:29` — Existenz im toten Pfad steuert die **Fixture-Auswahl**
- `test_issue_1001_telegram_bubbles.py:858-862` — schreibt eine F003-Fixture nach `trips/`, die nie gelesen wird

**Legitime Ausnahme (bleibt):** `tests/test_briefing_route_cutover.py` — die Datei **beweist** den Cutover
(AC-25 Lockvogel `:130,:149`; AC-26 Byte-Identität nach `save_trip` `:171-173,:184-186`). Sie braucht
zwingend einen Zeiger auf `trips/`. Laut Issue soll dieser Zeiger dort **testlokal und unmissverständlich
benannt** gebaut werden.

## Existing Patterns

### Wächter-/Ratschen-Bauart im Repo (Vorbilder)

| Vorbild | Bauart |
|---|---|
| `tests/test_output_timezone_guard.py:101-103,148,526,680,696` | AST-Scan über Glob-Scanfläche; `KNOWN_VIOLATIONS: dict[str,str]` mit Schlüsselform `pfad::funktion::ordinal`; **zwei gekoppelte Tests** — „keine unlisted" + „Liste darf nur schrumpfen"; `test_scan_list_paths_all_exist` gegen stilles Grün |
| `tests/test_success_status_guard.py:1996,2032,3228,3268,3293` | dieselbe Bauart + zweite Ausnahmeliste mit **Begründungspflicht**; Go-Ausschluss ist selbst getestet |
| `tests/test_egress_inventory_drift.py:33-67,92` | **Go wird per Textsuche/Regex gelesen** und als Daten gegen die Python-Seite verglichen; Parser-Wirkungsnachweis `test_parser_ignores_commented_out_lines` |
| `internal/handler/store_scope_guard_test.go:71,359,37,650` | Go-seitiger AST-Wächter mit Mindestdatei-Schwelle (`ssgMindestDateien = 50`) gegen stilles Grün und Ausnahmeventil mit Begründungspflicht |
| `tests/test_guard_findings_survive_line_shifts.py:1-45` | Meta-Wächter: Schlüsselform muss Zeilenverschiebungen überstehen |

**Wichtig:** Die drei Python-Wächter (`test_output_timezone_guard`, `test_success_status_guard`,
`test_resolution_loss_guard`) schließen `internal/` **bewusst** aus ihrer Scanfläche aus. Für #1708 liegt
die Falle aber auf **beiden** Seiten — der Wächter muss Go mitprüfen. Das Vorbild dafür ist
`test_egress_inventory_drift.py` (Textparse von Go), nicht die AST-Wächter.

Wächter-Tests liegen **direkt unter `tests/`**, nicht in `tests/tdd/`.

## Dependencies

- **Upstream:** `ADR-0023` (`docs/adr/0023-briefing-subscription-shared-model.md`) — beschließt
  `briefings/<id>.json` als einzige Persistenz-Wahrheit für `kind="route"` und `kind="vergleich"`;
  S7 ist der atomare Cutover von Lese- UND Schreibpfad in Go und Python.
- **Downstream:** Alle vier Registrierungswege rufen `ProvisionUserDirs`; nach der Änderung entsteht
  für neue Nutzer kein `trips/` mehr. Kein Produktivcode liest oder statet den Pfad.

## Existing Specs

- `docs/adr/0023-briefing-subscription-shared-model.md` — der Cutover-Beschluss
- ⚠️ `docs/adr/0031-persistenz-dateibasiert-data-users.md:16` — listet `trips/` **weiterhin** als Bestandteil
  des Nutzerverzeichnis-Layouts. Muss in Scheibe A mit korrigiert werden, sonst widerspricht das ADR dem Code.
- Veraltete Prosa mit `get_trips_dir`: `docs/specs/modules/preview_service.md:35`,
  `docs/specs/modules/issue_221_validator_observability_endpoints.md:47,76`,
  `docs/features/weather_snapshot_service.md:96,143`

## Risks & Considerations

1. **Der Wächter ist der tragende Teil, nicht die Löschung.** Die Warnung existierte bereits als
   Gedächtnisnotiz und wurde trotzdem zweimal in fünf Minuten umgangen. Eine Regel, die nur in einer Notiz
   steht, wird umgangen; eine, die einen Test rot macht, nicht. Ein Wächter, der die Wiederkehr **nicht**
   fängt, macht Scheibe A wertlos — die Löschung allein ist in einem Commit rückgängig gemacht.

2. **Scanfläche vs. Testcode.** Der Wächter darf Produktivcode treffen, aber nicht die Tests, die
   `trips/` legitim als Lockvogel anlegen (`test_briefing_route_cutover.py`,
   `internal/store/store_trip_briefings_test.go:30,98`, `internal/handler/delete_account_test.go:21`).
   Ein Wächter mit zu weiter Scanfläche wird sofort per Allowlist entschärft und ist dann wirkungslos.

3. **Stilles Grün.** Ein Wächter, der wegen eines Pfad-Tippfehlers null Dateien scannt, ist grün und
   schützt nichts. Beide Vorbilder lösen das explizit (Mindestdatei-Schwelle bzw. „Region gefunden"-Nachweis)
   — das ist hier Pflicht, nicht Kür. Ebenso ein synthetischer Wirkungsnachweis: eine Datei, die den
   verbotenen Pfad bildet, MUSS den Wächter rot machen.

4. **Python-Seite in Scheibe A oder B?** `get_trips_dir()` hat keinen Produktivaufrufer, aber 12
   Testdateien rufen sie auf. Ein Entfernen in Scheibe A zieht die gesamte Untersuchungsarbeit von
   Scheibe B mit hinein (LoC-Limit, Risiko). Die etablierte Repo-Bauart erlaubt den sauberen Schnitt:
   eine einzige dokumentierte Ausnahme im Wächter, gedeckt durch die „Liste darf nur schrumpfen"-Ratsche,
   die Scheibe B dann zwingend abbaut. → Entscheidung gehört in `/20-analyse`.

5. **`profile_test.go:395` ist ein Bestandszementierer.** Der Test prüft heute genau das, was wir abschaffen.
   Er muss mit umgestellt werden — und die Umstellung muss so aussehen, dass sie das **neue** Soll prüft
   (`trips/` entsteht NICHT), nicht bloß die Zeile löschen.

6. **ADR-Konsistenz.** `ADR-0031:16` widerspricht nach der Änderung dem Code. `tests/test_adr_index_drift.py`
   erzwingt Index↔Datei-Konsistenz, aber nicht Inhalt↔Code — die Korrektur muss bewusst passieren.

## Analysis

### Type

**Bug** (Datenverlust-/Fehlentscheidungs-Risiko). Die Ursache ist bekannt und im Issue belegt;
die Analyse galt der **Bauart des Wächters**, nicht der Ursachensuche.

### Der entscheidende Messbefund

`internal/store/user.go:84` baut den Pfad **nicht** in einem `filepath.Join`. Das Literal `"trips"`
steht in einem `[]string{...}`-Slice; der Join passiert eine Zeile später mit der Schleifenvariablen `sub`.

**Jede Erkennungsregel der Form „String-Literal `trips` innerhalb eines `filepath.Join`, das auch `users`
enthält" übersieht genau die Stelle, die die Falle laufend neu herstellt.** Die Regel muss deshalb am
reinen Literal binden, nicht am Ausdruckskontext.

Gemessene Verteilung über 292 Produktivdateien (91 Go, 201 Python):

| Ort | Treffer auf das Literal `"trips"` |
|---|---|
| Go-Produktivcode (`internal/`, `cmd/`, ohne `_test.go`) | **genau 2** — `internal/store/trip.go:15`, `internal/store/user.go:84` |
| Python-Produktivcode (`src/`, `api/`) | **genau 1** — `src/app/loader.py:1163` |
| Go-Testcode | 4 Dateien (alle legitim, s. o.) |
| `scripts/` | 9 (Migrations-/Backfill-Archäologie, legitim) |

### Affected Files (with changes)

| File | Change Type | Description |
|---|---|---|
| `tests/test_trips_path_revival_guard.py` | **CREATE** | Der Wächter. Python-Test, liest **beide** Bäume — Go per Zeilen-/Textparse, Python per AST |
| `internal/handler/profile_test.go` | MODIFY | `"trips"` aus der Positivschleife `:395`; **neuer** Test `TestRegisterCreatesNoLegacyTripsDir`, der das neue Soll prüft |
| `internal/store/user.go` | MODIFY | `"trips"` aus der `ProvisionUserDirs`-Liste (Zeile 84) |
| `internal/store/trip.go` | MODIFY | `TripsDir()` entfernen (Zeilen 14-16, null Aufrufer) |
| `internal/scheduler/selftest.go` | MODIFY (optional) | lokale Variable `tripsDir` → `briefingsDir` (Zeilen 42,43,48,56) — sie probt längst gegen `briefings/` |
| `docs/adr/0031-persistenz-dateibasiert-data-users.md` | MODIFY | `trips/` aus der Layout-Aufzählung (`:16`) streichen — zählt nicht auf LoC |
| `docs/specs/modules/fix_1708_a_trips_pfad_waechter.md` | CREATE | Spec — zählt nicht auf LoC |

### Scope Assessment

- Dateien: 7 (davon 2 CREATE)
- Geschätzte LoC: **+320 bis +360** zählbar — davon ~90 % Testcode
- Risk Level: **LOW** für die Produktivänderung (null Aufrufer, ein einziger brechender Test),
  **MEDIUM** für die Wächter-Wirksamkeit (ein Wächter, der nicht trifft, macht Scheibe A wertlos)

### Technical Approach

**Ein einziger Python-Wächter, der Go mitliest** (`tests/test_trips_path_revival_guard.py`), nicht zwei
getrennte Wächter. Drei Gründe:

1. **Nur der Python-Job ist ein Auslieferungs-Tor.** `.github/workflows/ci.yml:414` — `deploy: needs: [test, lint]`.
   Der Job `go-test` (`:65`) steht **nicht** in `needs` (selbst nachgeprüft). Ein rein Go-seitiger Wächter
   macht den PR rot, blockiert aber den Deploy nicht. Bei einer Regel, die zweimal in fünf Minuten umgangen
   wurde, ist das ausschlaggebend.
2. **Ein Go-Wächter sähe nur sein eigenes Paket.** Go-Tests laufen im Paketverzeichnis
   (`internal/handler/store_scope_guard_test.go:359` liest `os.ReadDir(".")`). Ein Wächter in
   `internal/store/` sähe `user.go` und `trip.go`, aber **nicht** `internal/handler/`, wo alle vier
   `ProvisionUserDirs`-Aufrufer liegen und eine Wiederkehr genauso plausibel ist.
3. **Zwei Wächter = zwei Regeldefinitionen, zwei Ratschen, zwei Stille-Grün-Absicherungen** — doppelte LoC
   und genau die Driftklasse, gegen die `tests/test_egress_inventory_drift.py` gebaut wurde.

Die Go-Regel braucht **keine** AST-Auflösung: beide Produktivformen sind schlichte String-Literale.
Zeilenweiser Scan mit Abschnitt am ersten `//` — das Verfahren aus `test_egress_inventory_drift.py:44-61`.

**Erkennungsregel** (Scanfläche per `rglob` berechnet, nie als abgeschriebene Dateiliste):

```
R1:  L == "trips"
R2:  re.search(r"(?:^|/|\*/)trips(?:/|$)", L)  UND  ("*" in L oder "users" in L)
```

Gemessene Wirkung heute: **genau 3 Funde, null Falsch-Positive.** Ausdrücklich nicht getroffen und als
Negativnachweis zu verankern: die 13 Routen-Strings `"/api/trips/…"` (`internal/router/router.go:141-167`),
`"corrupt_trips.json"` (`internal/scheduler/briefing_health.go:374` — enthält `users` **und** `*`, aber
`corrupt_trips` ist kein `trips`-Segment; eine Substring-Regel hätte hier falsch angeschlagen), die
URL-Strings in `trip_report_scheduler.py:1707` / `trip_command_processor.py:1328`, und
`internal/scheduler/selftest.go:42` (Variable heißt `tripsDir`, Literal ist `"briefings"` — der Wächter
bindet an Literale, nicht an Bezeichner).

**Kein Inline-Ausnahmeventil.** `store_scope_guard_test.go:653` erlaubt Stilllegung per Kommentar an der
Fundzeile — das wird hier bewusst **nicht** übernommen: eine Ausnahme wäre dann in der Täterdatei
unsichtbar mitzuschmuggeln. Ausnahmen ausschließlich als Restliste **in der Wächterdatei**, damit ein
Reviewer sie sieht.

**`scripts/` bleibt ausgeschlossen** (per Test festgeschrieben, Vorbild `test_success_status_guard.py:3293`):
die 9 Treffer dort sind einmalige Migrations-Werkzeuge, deren Aufgabe der Altpfad *ist*. Sie in die
Restliste zu nehmen hieße 9 Einträge, die nie schrumpfen — die Ratsche würde zur Dauereinrichtung, und
genau so wird ein Wächter im Feld entschärft.

### Bekannte Grenzen des Wächters (gehören in den Docstring)

Konstante/Variable in ausgeschlossener Datei · Konkatenation (`"tri" + "ps"`) · Verzeichnisname aus
Config/Env · Go-Rohstrings (Backticks) · Go-Blockkommentare werden nicht abgeschnitten (Falsch-Positiv-
Richtung, harmlos) · Schema-Umbenennung auf einen anderen Namen · neuer Top-Level-Baum.
**Keine davon ist versehentlich erreichbar** — alle erfordern bewusste Arbeit. Der reale Rückfall
(jemand fügt `"trips"` wieder in die `ProvisionUserDirs`-Liste ein) wird getroffen.

### Selbstnachweise gegen stilles Grün (sieben, alle Pflicht)

1. Go-Scanfläche `>= 80` Dateien (heute 91), sonst Abbruch — Vorbild `store_scope_guard_test.go:37,381-384`
2. Python-Scanfläche `>= 180` (heute 201)
3. **Trägernachweis:** `internal/store/user.go`, `internal/store/trip.go`, `src/app/loader.py` müssen
   *namentlich* in der gescannten Menge liegen. Eine reine Zählung fängt keinen Tippfehler, der nur einen
   Teilbaum verliert — Vorbild `test_output_timezone_guard.py:659`
4. **Positivnachweis Go** an synthetischen In-Memory-Strings (nie an echten Dateien, sonst meldet der
   Wächter sich selbst): (a) die `filepath.Join`-Form, (b) **die Slice-Form** — (b) ist die wichtigere,
   sie ist die Form, die die Falle real neu herstellt
5. **Positivnachweis Python:** `get_data_dir(uid) / "trips"` und `root.glob("*/trips/*.json")`
6. **Negativnachweis** an den realen Bestandsformen (Routen, URL, `corrupt_trips.json`, `briefings`) →
   null Funde; dazu Go-Parserwirkung: Vollkommentarzeile → null Funde, Eintrag mit Inline-Kommentar → ein Fund
7. **Ratschen-Selbstnachweis:** `test_known_violations_only_shrink` **plus** harte Obergrenze
   `len(KNOWN_VIOLATIONS) <= 1`

Schlüsselform der Restliste: `pfad::symbol::ordinal` (Hausnorm, `tests/test_guard_findings_survive_line_shifts.py:52`).

### Reihenfolge — zwei echte ROTs

| Schritt | Erwartung |
|---|---|
| **A** Wächter zuerst, Restliste = nur der Python-Eintrag | **ROT** — benennt `trip.go:15` und `user.go:84`, **bevor** irgendetwas gelöscht ist |
| **B** `profile_test.go` umstellen | **ROT** — `trips/` entsteht noch. Zweiter, unabhängiger RED-Beleg |
| **C** Produktivstellen entfernen | A und B werden grün |
| **D** ADR-0031 korrigieren, Spec ablegen | zählt nicht auf LoC |

Umgekehrte Reihenfolge (erst löschen) macht den Wächter **grün geboren** — dann ist unbewiesen, dass er
überhaupt trifft. Genau dieser Wächter darf sich das nicht leisten.

### Dependencies

- Upstream: ADR-0023 (Cutover-Beschluss). Downstream: die vier Registrierungswege.
- CI: `.github/workflows/ci.yml:414` `deploy: needs: [test, lint]` — der Wächter muss im `test`-Job laufen,
  damit er ein Auslieferungs-Tor ist.

### Open Questions (PO-Entscheidung)

- [ ] **LoC-Override auf 400.** Geschätzt +320…+360, das 250er-Limit reißt. Bewusst: die sieben
  Selbstnachweise sind hier nicht Kür, sie sind der Gegenstand. Wer kürzt, kürzt zuerst an den
  Positiv-/Negativnachweisen — und liefert dann den Wächter aus, dessen Wirkung niemand geprüft hat.
- [ ] **Eine dokumentierte Ausnahme für `get_trips_dir()`** statt Entfernung in Scheibe A. Neu gefunden:
  `tests/tdd/test_issue_1133_testdata_cleanup.py:61` nutzt sie als **Sonde für AC-1 von #1133**
  (Datenwurzel-Isolation) — das ist kein Aufräum-Code, sondern eine lebende Zusicherung, deren Umstellung
  eine eigene Entscheidung braucht. Abbau erzwungen durch „nur schrumpfen" **plus** Obergrenze 1.

## Abgrenzung: was Scheibe A NICHT umfasst

- Die 12 Testdateien auf `briefings/` umstellen und je Datei belegen, warum sie heute grün ist → **Scheibe B**
- Die 14 toten Produktivdateien unter `/var/lib/gregor/users/*/trips.TOT-legacy-1250-nicht-lesen`
  archivieren und löschen → **Scheibe C** (schließt #1708)
