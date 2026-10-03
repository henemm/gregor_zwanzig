---
entity_id: fix_2239_loader_konsistenz
type: bugfix
created: 2026-10-03
updated: 2026-10-03
status: draft
version: "1.0"
workflow: fix-2239-loader-divergenz
issue: 2239
epic: 2260
tags: [loader, trips, archiv, bewachungstest, known-issues]
---

# Loader-Konsistenz: `load_all_trips` deckt sich mit `load_trip` (#2239)

## Approval

- [ ] Approved

## Purpose

Issue #2239 (Eintrag C1-83 aus #1199) meldete, `load_all_trips('validator-issue110')` liefere 0 Trips, obwohl `load_trip` acht Dateien dieses Kontos einzeln laden könne — ein verdächtiger stiller Verlust gültiger Trips. Die Analyse ergibt: Das ist **kein Defekt**, sondern das gewollte Archiv-Filterverhalten (#824). Alle acht Validator-Trips tragen `archived_at` (Seed `scripts/seed_validator_archive.py`); `load_all_trips` blendet archivierte per Default aus, `load_trip` filtert nicht. Die Juli-Messung war zusätzlich eine Fehlmessung (Nutzer `hem`, relativer `data`-Fallback bzw. veralteter Baum im Prod-Arbeitsverzeichnis). Diese Spec ändert deshalb **keinen Produktivcode**, sondern schließt die verbleibende Bewachungslücke: Es gab keinen Test, der die Invariante „Menge der einzeln ladbaren Trip-Dateien == `load_all_trips`" bewacht. Dazu kommen ein Root-Cause-Eintrag in `known_issues.md` und der Ticket-Abschluss.

### Evidenz-Ebene (ehrlich)

- **Prod-Inhalt wurde NICHT gelesen** (Lesezugriff auf das Prod-Datenverzeichnis wurde gesperrt). Nichts in dieser Spec behauptet „auf Prod verifiziert".
- **Nur Metadaten Prod:** 8 Dateien unter `validator-issue110/briefings/`, mtime 16.07. 04:11 (Tag des S7a-Deploys), je exakt +19 Byte gegenüber der Fixture — das entspricht der Zeile `"kind": "route",`. Das ist ein Indiz, kein Inhaltsbeweis.
- **Reproduziert an einer Fixture-Kopie** (migriert nach `briefings/`, `kind: route`): `load_trip` 8/8 ok, `load_all_trips()` = 0, `load_all_trips(include_archived=True)` = 8.
- **Nicht gemessen:** Vergleich beider Ladewege über alle Prod-Nutzer.

## Source

- **File:** `src/app/loader.py` (nur gelesen, **nicht geändert** — auch kein Docstring, damit keine Code-Lieferkette ausgelöst wird)
- **Identifier:** `load_trip` (Z. 411-467), `load_all_trips` (Z. 1600-1646)

> **Schicht:** Python-Core (`src/app/`) ist der Prüfling; geändert werden ausschließlich `tests/tdd/` und `docs/`. Kein Go, kein Frontend.

## Estimated Scope

- **LoC:** ~+130 (Test ~110, Doku ~20); produktiv 0
- **Files:** 2 geändert/neu (`tests/tdd/test_load_all_trips_deckt_sich_mit_load_trip.py` neu, `docs/project/known_issues.md` erweitert) plus Ticket-Kommentare
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/loader.py::load_all_trips` / `load_trip` | Prüfling | Beide Ladewege, werden nur aufgerufen |
| `tests/tdd/test_bug_824_archived_trip_filter.py` | Bestandstest | Bewacht Archiv-Filter allein; neuer Test ergänzt die Invariante gegen `load_trip` |
| `tests/tdd/test_null_list_fields.py` | Bestandstest | Prüft „Skipping corrupt trip" punktuell; neuer Test ergänzt „Rest lädt trotzdem" |
| `tests/conftest.py` (`_materialize_real_data_root_fixtures`) | Test-Infrastruktur | Spiegelt `trips/*.json` additiv nach `briefings/` mit `kind=route`; deshalb bleibt die Fixture `validator-issue110/trips/` unverändert |
| `src/services/trip_report_scheduler.py::record_corrupt_trip_observability` | Bestandscode | Macht den echten Verlustpfad „kaputte Datei" per MQ sichtbar (nur Verweis) |
| `.github/ci_tdd_excludes.txt` | CI-Konfig | Neue `tests/tdd`-Datei läuft automatisch im `test`-Job, **solange sie dort nicht eingetragen ist** (Bedingung für diese Spec) |
| `scripts/seed_validator_archive.py` | Bestandsskript | Quelle der 8 archivierten Validator-Trips (Erklärung des Befunds) |

## Implementation Details

**1. Neuer Kern-Test** `tests/tdd/test_load_all_trips_deckt_sich_mit_load_trip.py` (deterministisch, kein Netz, **kein Mock/patch**):

- Isolierter Daten-Root: `tmp_path` als Daten-Root, gesetzt über dieselbe Redirect-Mechanik, die die übrigen tdd-Tests nutzen (`GZ_DATA_DIR` per `monkeypatch.setenv` bzw. `loader._DATA_ROOT`; der Entwickler prüft in `tests/conftest.py` und `test_bug_824_archived_trip_filter.py`, welche Variante dort gilt, und folgt ihr). Echte JSON-Dateien unter `users/<user>/briefings/`.
- Prüfling wird über Import des Pakets (`from src.app.loader import ...`) aufgelöst, nie über einen festen Hauptrepo-Pfad (sonst falsches Grün im Worktree).
- Szenario für Nutzer A: mehrere `kind=route`-Dateien (teils mit `archived_at`, teils ohne), eine `kind=vergleich`-Datei, eine kaputte `kind=route`-Datei (z. B. ungültiges Stage-Datum, löst `ValueError` in `_parse_trip` aus). Nutzer B hat im selben Root eigene Trips (andere IDs).
- Referenzmenge „einzeln ladbar": pro Datei `load_trip(<Pfad>)` (Pfad-Zweig); Erfolg zählt, Ausnahme zählt als „nicht ladbar". Vergleichs-Datei: Referenz nur über Dateien mit `kind=route`.
- Hilfs-Trip-JSON analog `_make_trip_json` im Test #824 (Stage mit Wegpunkt, optional `archived_at`, `kind: "route"`).

**2. `docs/project/known_issues.md`:** Root-Cause-Eintrag C1-83 (Archiv-Filter #824 + Fehlmessung durch relativen `data`-Fallback/veralteten Baum; kein Datenverlust; Evidenz-Ebene wie oben).

**3. Abschluss (Orchestrierer, nach Merge):** Kommentar in #2239; C1-83 in #1199 abhaken; der relative `data`-Fallback bzw. veraltete `data/users`-Baum im Prod-Arbeitsverzeichnis als Checkbox-Zeile in #1199 (kein eigenes Issue, Nebenbefund-Triage).

**4. Korrektur der Analyse:** Die Analyse nannte die Fixture `tests/fixtures/data_root/users/validator-issue110/trips/` „tot" und schlug eine Verschiebung nach `briefings/` vor. Das ist falsch: `tests/conftest.py::_materialize_real_data_root_fixtures` spiegelt `trips/*.json` additiv nach `briefings/` mit `kind=route`. Eine Verschiebung brächte keinen Nutzen und wird **nicht** durchgeführt.

### RED-Nachweis per Pflicht-Mutation (Bewachungstest)

Weil am Loader nichts geändert wird, ist der neue Test gegen den **unveränderten** Code **grün** — er ist ein Bewachungstest, kein Bug-Reproduktionstest. Der RED-Nachweis in `/40` erfolgt daher ausschließlich per Mutation: Jede Verfälschung wird per **String-Ersetzung mit externer Sicherungskopie** (Kopie im Scratchpad, **nie** `git checkout/stash/reset`) in `src/app/loader.py` eingespielt, der Test muss ROT werden, danach wird das Original zurückkopiert und per Diff gegen die Sicherung bestätigt.

| Mutation | Verfälschung in `load_all_trips` | Erwartet rot |
|---|---|---|
| M1 | Archiv-Filter (`if not include_archived and trip.archived_at is not None: continue`) entfernen | Test zu AC-2 |
| M2 | `logger.error(...)` im `except`-Zweig entfernen | Test zu AC-4 (Log-Teil) |
| M3 | `continue` im `except`-Zweig durch `return trips` ersetzen (Abbruch) | Test zu AC-4 („Rest lädt trotzdem") |
| M4 | `kind`-Filter (`if raw.get("kind") == "vergleich": continue`) entfernen | Test zu AC-3 |

Für jede Mutation wird protokolliert, **welcher** Test rot wurde; ein roter Test aus anderem Grund (z. B. Folgefehler) zählt nicht als Nachweis. Wird bei einer Mutation kein Test rot, ist das ein Finding.

## Expected Behavior

- **Input:** Daten-Root mit `users/<user>/briefings/*.json` (route, vergleich, kaputt, teils archiviert) für zwei Nutzer.
- **Output:** `load_all_trips(user_id, include_archived=True)` entspricht exakt der Menge der einzeln fehlerfrei ladbaren `kind=route`-Dateien; ohne Flag fehlen genau die archivierten.
- **Side effects:** keine (reine Lese-Aufrufe auf `tmp_path`); `logger.error` bei kaputter Datei.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer mit mehreren `kind=route`-Dateien (teils archiviert) und einer kaputten Datei / When `load_all_trips(user_id, include_archived=True)` aufgerufen wird / Then ist die Menge der zurückgegebenen Trip-IDs identisch mit der Menge der `kind=route`-Dateien, die `load_trip` einzeln fehlerfrei lädt.
  - Test: Datei für Datei `load_trip(<Pfad>)` aufrufen, Erfolge sammeln und mit `{t.id for t in load_all_trips(user, include_archived=True)}` vergleichen.

- **AC-2:** Given dasselbe Szenario / When `load_all_trips(user_id)` ohne Flag aufgerufen wird / Then ist das Ergebnis genau die Menge aus AC-1 abzüglich der Trips mit `archived_at` (nicht leer, wenn nicht archivierte Trips existieren).
  - Test: erwartete Menge = ladbare route-Trips mit `archived_at is None`; Gleichheit prüfen, zusätzlich Nicht-Leere. Mutation M1 muss rot werden.

- **AC-3:** Given eine `kind=vergleich`-Datei im selben `briefings/`-Verzeichnis / When beide Ladeaufrufe (mit und ohne `include_archived`) laufen / Then taucht deren ID in keinem der beiden Ergebnisse auf.
  - Test: ID der Vergleichs-Datei gegen beide Ergebnismengen prüfen. Mutation M4 muss rot werden.

- **AC-4:** Given eine kaputte `kind=route`-Datei (ungültiges Datum) neben gültigen Trips / When `load_all_trips` aufgerufen wird / Then fehlt nur die kaputte Datei im Ergebnis, alle übrigen gültigen Trips werden trotzdem geladen (kein Abbruch), und es wird ein ERROR-Log „Skipping corrupt trip" mit dem Dateinamen der kaputten Datei geschrieben.
  - Test: `caplog` auf Level ERROR; Nachricht enthält „Skipping corrupt trip" und den Dateinamen; Ergebnismenge enthält alle gültigen IDs. Mutationen M2 und M3 müssen rot werden.

- **AC-5:** Given zwei Nutzer A und B mit eigenen Trips im selben Daten-Root / When `load_all_trips` für A aufgerufen wird / Then enthält das Ergebnis keine Trips von B (und umgekehrt).
  - Test: IDs beider Nutzer disjunkt gewählt; Ergebnis für A enthält keine B-ID, Ergebnis für B keine A-ID.

- **AC-6:** Given der Abschluss des Workflows / When `docs/project/known_issues.md` gelesen wird / Then enthält sie einen Root-Cause-Eintrag zu C1-83 mit Archiv-Filter (#824), Fehlmessung, „kein Datenverlust" und der ehrlichen Evidenz-Ebene (Prod-Inhalt nicht gelesen).
  - Test: Dokumentations-Kriterium, nicht per Test geprüft (Review).

## Known Limitations

- **Bewachungstest statt Bug-Reproduktion:** Der Test ist gegen den unveränderten Code grün; sein Wert wird ausschließlich durch die Mutationen M1-M4 belegt.
- **Prod-Datenbestand nicht verifiziert:** Der Nachweis der Archiv-Ursache stützt sich auf Code, Seed-Skript, Fixture-Reproduktion und Metadaten-Indizien.
- **Deploy-Einordnung:** Reine Test-/Doku-Änderung ohne Code in `src/`, `api/`, `internal/`, `frontend/`, `cmd/` ⇒ Staging-Validierung und Prod-Deploy entfallen laut CLAUDE.md-Ausnahme. Ein PR mit grüner CI-Ampel (alle 6 Checks) bleibt Pflicht.

### Ausdrücklich außerhalb des Scopes

- **Go `LoadTrips` (`internal/store/trip.go`):** listet archivierte Trips — gewollt für die Archivansicht, nur Dokumentation (Python-Core blendet sie per Default aus, #824).
- **Fehlendes `briefings/`-Verzeichnis ⇒ `[]` ohne Log:** korrekt für neue Nutzer; ein Log wäre Lärm.
- **Relativer `data`-Fallback in `get_data_root`:** Prod und Staging setzen `GZ_DATA_DIR`; als Checkbox in #1199 gebucht, keine Codeänderung.
- **Fixture `validator-issue110/trips/` verschieben:** entfällt (siehe Korrektur der Analyse oben).
- **Vergleich beider Ladewege über alle Prod-Nutzer:** nicht gemessen (Zugriff gesperrt). Der echte Verlustpfad „kaputte Datei" ist durch `logger.error` und MQ-Observability (`record_corrupt_trip_observability`) sichtbar.
- **Docstring-Hinweis in `loader.py`:** bewusst nicht ergänzt, um keine Code-Lieferkette (Staging/Prod) auszulösen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Es wird keine Entscheidung getroffen oder geändert; das Archiv-Filterverhalten (#824) bleibt unverändert, der Test bewacht lediglich den Ist-Zustand.

## Changelog

- 2026-10-03: Initial spec created (Issue #2239, Epic #2260)
