# Context: fix-2239-loader-divergenz

## Request Summary
Issue #2239 (Epic #2260): `load_all_trips()` soll still gültige Trip-Briefings verwerfen, die `load_trip()` einzeln laden kann (Eintrag C1-83 aus #1199, Herkunft #1264/#1284, Konto `validator-issue110`). Nie reproduziert — erst reproduzieren, dann ggf. fixen.

## Ursprungsbefund (Wortlaut-Kern, #1199-Kommentar 2026-07-17)
Prod: `load_all_trips('validator-issue110')` = 0, obwohl 8 valide Briefings existieren, die `load_trip(<pfad>)` einzeln fehlerfrei lädt (z. B. `dachstein-2023.json`). Laut Kommentar nur das Validator-Konto betroffen, keine echten Nutzer. Der #1264-Kommentar derselben Minute nennt für einen Teil der Messung eine Fehlmessung als User `hem` (Daten gehören `claude-gregor`, Modus 770).

## Hypothese H1 (stärkste Spur, nur im Code belegt)
`scripts/seed_validator_archive.py:19-36,78-90` legt für `validator-issue110` genau 8 Trips an (ortler, zillertal, rofan, venediger, stubai, khw-402, gardasee, dachstein-2023) — **alle mit `archived_at`**. `load_all_trips` filtert archivierte per Default weg (`loader.py:1632`, Bug #824, gewollt), `load_trip` nicht. 0 vs. 8 wäre dann gewolltes Verhalten. Passt dazu: kein „Skipping corrupt trip"-Log bei Archiv-Filterung. **Auf Prod-Daten noch nicht verifiziert.**

## Related Files
| File | Relevance |
|------|-----------|
| `src/app/loader.py:411-467` | `load_trip` (per ID/data_dir, per dict, per Pfad) — kein Archiv-Filter, keine Exception-Unterdrückung |
| `src/app/loader.py:475ff` | `_parse_trip` — gemeinsamer Parser beider Pfade |
| `src/app/loader.py:1600-1646` | `load_all_trips` — kind-Filter, Archiv-Filter, `except Exception` → `logger.error("Skipping corrupt trip")` + `continue` |
| `src/app/loader.py:1226/1268/1290` | `get_data_root` → `get_data_dir` → `get_briefings_dir`; Fallback relatives `data` (cwd-abhängig); fehlendes Verzeichnis → still `[]` |
| `internal/store/trip.go:127-188` | Go `LoadTrips` — **kein Archiv-Filter** (Python↔Go-Divergenz beim Archiv) |
| `src/services/trip_report_scheduler.py:328-386` | `record_corrupt_trip_observability` — meldet unladbare Trips per MQ, dedupliziert in `diagnostics/corrupt_trips.json` |
| `scripts/seed_validator_archive.py` | Seed der 8 archivierten Validator-Trips |
| `docs/analysis/triage-1199-2026-09-08.md:41,286` | Triage-Eintrag C1-83 (Zeilenangaben 1442/1487 veraltet) |
| `docs/specs/_archive/modules/issue_1265_prod_testdata_cleanup.md:87,146` | `validator-issue110` als offener „Klärungsfall" |

## Downstream (Aufrufer von `load_all_trips`)
- Briefing-Scheduler `trip_report_scheduler.py:690,940` (aktive Trips)
- Alarme `trip_alert.py:945,1704`
- Inbound: `inbound_email_reader.py:390`, `inbound_sms_reader.py:342`, `inbound_telegram_reader.py:264,524,596`, `trip_command_processor.py:1366`, `trip_selection.py`
- Shortcode-Dedup `shortcode.py:16` (`include_archived=True`)
- API `scheduler.py:220`, `internal.py:55,88`, `debug.py:62`

## Existing Patterns
- Ein kaputter Trip darf den Load der übrigen nicht blockieren (#111) → skip + `logger.error` (#1244 AC-6) + MQ-Observability im Scheduler.
- Bereits entschärfte Parse-Fallen: `ActivityProfile(None)` (#111), null-Listen/`display_config: null` (#1244), Flach-String-Metriken (#1262).
- Verbleibende Exception-Kandidaten in `_parse_trip`: KeyError bei Pflichtfeldern, ValueError aus `fromisoformat` (Stage-Datum, Zeiten, `paused_until`, `updated_at`), Enum-Konstruktoren (`AggregationFunc`, `AlertRuleKind`), Nicht-dict-Einträge.

## Existing Tests
- `tests/test_briefing_route_cutover.py:129-308`
- `tests/tdd/test_bug_824_archived_trip_filter.py:123-274`
- `tests/tdd/test_null_list_fields.py`, `test_loader_display_config_default.py`, `test_legacy_flat_metrics_load.py`, `test_scheduler_corrupt_trip_observability.py`
- Fixtures `tests/fixtures/data_root/users/validator-issue110/trips/*.json` (8, alle archiviert, ohne `kind`, noch unter `trips/` statt `briefings/`)

## Existing Specs
- `docs/specs/modules/loader_display_config_default.md`, `trip_report_scheduler.md`, `validator_internal_loaded_endpoint.md`, `fix_1708_b2_trips_pfad_rueckbau.md`, `python_userid_integration.md`, `fix_2151_default_fallbacks_scheibe_c.md`
- Keine eigene Spec zur Divergenz.

## Risks & Considerations
- H1 nur im Code belegt — Analyse muss gegen echte Prod-/Staging-Daten messen (lesend). Datenbestand gehört `claude-gregor`; als `hem` evtl. nicht lesbar → Fehlmessung wie 2026-07 vermeiden.
- Wenn H1 zutrifft: kein Loader-Fix nötig; Restfrage, ob es weitere stille Verwerfungen gibt (alle Nutzer, beide Loader vergleichen).
- Echte stille Verlustpfade, die bleiben: `except Exception` + `continue` (nur Log/MQ), fehlendes `briefings/`-Verzeichnis → `[]` ohne Log, cwd-abhängiger `data`-Fallback.
- Python↔Go-Archiv-Divergenz: Go listet archivierte Trips, Python nicht — gewollt (#824), aber dokumentationswürdig.
- Fixtures für `validator-issue110` liegen noch unter `trips/` (Alt-Pfad).

## Analysis

### Type
Bug-Verdacht → **nicht reproduzierbar als Defekt.** Die gemeldete Divergenz (0 vs. 8) ist das gewollte Archiv-Filterverhalten (#824). Rest: Absicherung + Aufräumen.

### Befund (Evidenz-Ebene ehrlich benannt)
- **Prod-Inhalt NICHT gelesen** — Lesezugriff auf `/var/lib/gregor` (Prod `GZ_DATA_DIR`, Owner `claude-gregor`) wurde in dieser Sitzung gesperrt (PII/Production Reads). Kein „auf Prod verifiziert“.
- **Indizien Prod (nur Metadaten):** `validator-issue110/briefings/` enthält genau die 8 Seed-Trips, alle mtime **16.07. 04:11** (Tag des S7a-Deploys, Vortag des Befunds). Jede Datei ist **exakt +19 Byte** gegenüber der Fixture — entspricht genau der Zeile `"kind": "route",`, die die S7a-Migration ergänzt. ⇒ Inhalt = Seed-Daten aus `scripts/seed_validator_archive.py`, **alle mit `archived_at`**.
- **Zeitlinie passt auf die Juli-Messung:** Archiv-Filter in `load_all_trips` seit `1bef9abb6` (24.06., #824); Lesen aus `briefings/` seit `22732a1a7` (15.07., S7a). Beides galt am 17.07.
- **Ladeverhalten reproduziert** an migrierter Fixture-Kopie (`kind: route` ergänzt, unter `briefings/`): `load_trip` einzeln 8/8 ok, alle 8 archiviert; `load_all_trips` = 0, `load_all_trips(include_archived=True)` = 8. **Keine Divergenz.**
- **Wahrscheinliche Quelle der Juli-Fehlmessung:** neben dem `hem`-Fehlzugriff (#1264-Kommentar) liegt im Prod-Arbeitsverzeichnis `/home/hem/gregor_zwanzig/data/users/` ein veralteter, für `hem` lesbarer Baum (inkl. `validator-issue110/trips/` + `briefings/`). Ohne `GZ_DATA_DIR` fällt `get_data_root()` auf relatives `data` zurück ⇒ Messung lief leicht gegen den falschen Bestand.
- **Nicht gemessen:** Vergleich beider Ladewege über ALLE Prod-Nutzer (Zugriff gesperrt). Blockiert nicht: Ticket-Befund betrifft nur das Validator-Konto; der echte Verlustpfad „kaputte Datei“ ist bereits per `logger.error` + MQ-Observability (`record_corrupt_trip_observability`) sichtbar.

### Bewachung heute
- Archiv-Filter: `tests/tdd/test_bug_824_archived_trip_filter.py` (schreibt nach `briefings/`, prüft Default ohne / `include_archived=True` mit Archiv) — bewacht.
- Skip + Log kaputter Trip: `tests/tdd/test_null_list_fields.py` (prüft `Skipping corrupt trip`).
- **Lücke:** keine Invariante „Menge der einzeln ladbaren route-Dateien == `load_all_trips(include_archived=True)`; Default schließt genau die archivierten aus“. Genau diese Zusicherung ist Gegenstand des Tickets.
- **Totes Fixture:** `tests/fixtures/data_root/users/validator-issue110/trips/*.json` (8, ohne `kind`) liegt im Alt-Pfad `trips/`; keiner der ~10 Tests, die das Konto nennen, liest es über `load_all_trips`/`get_briefings_dir` — keine falsch-grünen Tests, aber irreführender Bestand.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `tests/tdd/test_loader_konsistenz.py` (Name nach Verhalten, final in Spec) | CREATE | Invariante load_trip-Menge ↔ load_all_trips (mit/ohne Archiv), kaputte Datei wird übersprungen + geloggt, Rest lädt; `kind: vergleich` ausgenommen |
| `tests/fixtures/data_root/users/validator-issue110/trips/*.json` → `briefings/` | MODIFY/MOVE | Fixture auf S7a-Stand: Pfad `briefings/`, `kind: "route"` |
| `src/app/loader.py` | — (keine Logikänderung) | ggf. nur Docstring-Hinweis in `load_all_trips`, dass archivierte bewusst fehlen |
| `docs/project/known_issues.md` | MODIFY | Root-Cause-Notiz C1-83: Archiv-Filter + Fehlmessung, kein Datenverlust |

### Scope Assessment
- Files: ~3 + 8 Fixture-Verschiebungen
- Estimated LoC: +60/-0 produktiv nahezu 0 (Test + Fixture + Doku)
- Risk Level: LOW — keine Änderung am Ladeverhalten

### Technical Approach
1. Kein Loader-Fix — Verhalten ist korrekt.
2. Invariantentest im Kern (deterministisch, isolierter Daten-Root): N route-Dateien (teils archiviert), 1 `kind: vergleich`, 1 kaputte Datei ⇒ (a) `load_all_trips(include_archived=True)` == Menge der einzeln mit `load_trip` ladbaren route-Dateien, (b) Default == davon die nicht archivierten, (c) kaputte Datei fehlt, Rest vollständig, `Skipping corrupt trip` geloggt.
3. Pflicht-Mutationen in `/50`: Archiv-Filter entfernen ⇒ rot; `except` ohne Log ⇒ rot; `continue` → `return trips` (bricht nach kaputter Datei ab) ⇒ rot.
4. Fixture `validator-issue110` nach `briefings/` + `kind` migrieren; vorher prüfen, dass `_materialize_real_data_root_fixtures` (conftest) keinen Pfad `trips/` erwartet.
5. Ticket-Abschluss: Root Cause in `known_issues.md`, Kommentar in #2239/#1199 (C1-83 abhaken).

### Bewusst NICHT im Scope (begründet)
- Go `LoadTrips` listet archivierte: gewollt (UI-Archivansicht), nur Doku.
- Fehlendes `briefings/` ⇒ `[]` ohne Log: korrekt für neue Nutzer, Log wäre Lärm.
- Relativer `data`-Fallback: Prod/Staging setzen `GZ_DATA_DIR`; der veraltete `data/users`-Baum im Prod-Arbeitsverzeichnis ist ein Fehlmessungs-Risiko → als Sammel-Eintrag in #1199 (kein nutzersichtbarer Fehler).

### Dependencies
`load_all_trips` speist Scheduler, Alarme, Inbound (E-Mail/SMS/Telegram), Shortcode-Dedup, API — durch Nicht-Änderung der Logik unberührt.

### Open Questions
- keine für den PO (technische Ausgestaltung entscheidet die Spec)
