---
entity_id: rework_1215_dead_code_scheibe1
type: module
created: 2026-07-10
updated: 2026-07-10
status: draft
version: "1.2"
tags: [cleanup, dead-code, python, root-cleanup]
---

<!-- Issue #1215 — Scheibe 1 von 3: Toten Code entfernen (Python + Root-Altlasten) -->

# Toten Code entfernen — Scheibe 1 (Python + Root-Altlasten)

## Approval

- [x] Approved (PO 'go' 2026-07-10)

## Purpose

Risikofreien toten Code aus dem Python-Backend und Repo-Root entfernen, um die
Wartbarkeit zu verbessern (Wartbarkeits-Audit 2026-07, Issue #1215). Es handelt
sich ausschließlich um Löschen/Verschieben von Code ohne externe Aufrufer bzw.
um untrackte Altlasten-Dateien — kein Produktions-Verhalten ändert sich.
Scheibe 1 von 3 (Frontend = Scheibe 2, Go `internal/compare/` = Scheibe 3,
eigene Workflows).

## Source

- **File:** `src/services/weather_metrics.py` — Legacy-Block ab Zeile ~1199
  (Klassen `HourlyCell` :1205, `CloudStatus` :1316, Funktionen `build_hourly_cell`,
  `hourly_cell_to_compact` :493, Cloud-Status-Methoden mit Selbst-Imports
  :545/:588/:619) — **Python-Core**, Domain-Backend
- **File:** `src/services/coordinates.py` — komplette Datei (57 LoC) — **Python-Core**
- **File:** `tests/refactor/test_epic_129a_2_module_structure.py` — Testfunktion
  `test_coordinates_module` (Zeilen 27-32) wird mitgelöscht
- **File:** `red_839_fmt_val_thresholds.txt` (Repo-Root) — gelöscht
- **File:** `atoms.jsx`, `brand-kit.jsx` (Repo-Root) — verschoben nach
  `docs/design-requests/archive/`
- **Lokaler Aufräum-Schritt (Hauptrepo, nicht Teil dieses Commits):** untrackte
  Altlasten im Hauptrepo-Arbeitsverzeichnis (`trip_report_old.py`,
  `red_654_drilldown_v2.txt`, `red_654_telegram_thunder_drilldown.txt`,
  `commit_hash.txt`, `staging_commit.txt`, `health.json`, 12 Sicherungskopien
  `.claude/validator.env.*`, alte Binaries `gregor_zwanzig` + `server`)

## Estimated Scope

- **LoC:** ca. -400 (negativ; reine Löschung: ~350 LoC `weather_metrics.py` +
  57 LoC `coordinates.py` + Testfunktion, abzüglich README-Notiz im Archiv)
- **Files:** 4 committete Änderungen (2 Löschungen Python + 1 Testdatei-Edit +
  1 Löschung `.txt`), 2 Verschiebungen (`atoms.jsx`, `brand-kit.jsx`), plus
  1 dokumentierter lokaler Aufräum-Schritt (20 untrackte Dateien inkl. 2 alter
  Binaries, kein Commit)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/weather_metrics.py` (verbleibender Teil, ~975 LoC) | Python-Modul | Aktive Metrik-Formatierung; Legacy-Block wird entfernt, Rest bleibt unverändert |
| `tests/integration/test_segment_weather_metrics.py` | Test | Muss nach Löschung weiterhin grün bleiben (prüft aktiven Teil von `weather_metrics.py`) |
| `tests/refactor/test_epic_129a_2_module_structure.py` | Test | Wird um `test_coordinates_module` gekürzt, restliche Tests bleiben unverändert grün |
| `docs/design-requests/archive/` | Verzeichnis | Etablierter Ablageort für eingefrorene Design-Artefakte |
| `.gitignore` (Zeilen 80-82) | Config | Deckt Go-Binaries (`gregor-api`, `gregor_zwanzig`, `/server`) bereits ab — wird nur nachgewiesen, nicht geändert |
| `gregor-api` (Prod-Binary) | Binary | **Darf unter keinen Umständen gelöscht werden** — laufende Produktions-Binary (systemd `ExecStart` zeigt direkt darauf) |
| `src/services/aggregation.py`, `src/services/trip_forecast.py` | Python-Modul | Explizit **NICHT** Teil dieser Scheibe — hängen am Legacy-CLI-Pfad (`src/app/cli.py:228`), Abbau ist eigene PO-Entscheidung |

## Implementation Details

### 1. Löschen per Commit (`weather_metrics.py`)

Entfernen des Legacy-Blocks (repo-weite Grep-Verifikation: `HourlyCell`,
`CloudStatus`, `build_hourly_cell`, `hourly_cell_to_compact` haben außerhalb
von `weather_metrics.py` selbst **keine** Aufrufer):

```
class HourlyCell                                          # Zeile 1205
class CloudStatus(str, Enum)                              # Zeile 1316
WeatherMetricsService.format_hourly_cell                  # Zeile 413 (Issue nannte sie "build_hourly_cell")
WeatherMetricsService.hourly_cell_to_compact              # Zeile 493
WeatherMetricsService.calculate_cloud_status              # Zeile 525
WeatherMetricsService.format_cloud_status                 # Zeile 575
WeatherMetricsService.get_cloud_status_emoji              # Zeile 607
```

**Bleiben erhalten (Korrektur zur groben Issue-Angabe „Block ab ~1199"):**
`aggregate_stage` (Zeile 1228) + Helfer `_circular_mean_deg` (Zeile 1308) —
echter Nutzer `tests/tdd/test_issue_721_email_outlook.py:287` (Confidence-
Propagation, „wie Scheduler es baut"). Datei sinkt von 1325 auf ca. 1080 LoC.
Kein anderer Modulteil referenziert die gelöschten Symbole (verifiziert per
repo-weitem Grep — einzige Treffer außerhalb sind veraltete Hinweistexte in
`.claude/hooks/architecture_guard.py`, die nur Neu-Definitionen andernorts
blocken; Hook wird laut Regel „Validator-Änderungen = eigener Workflow" hier
nicht angefasst → Nebenbefund-Eintrag in #1199).

### 2. Löschen per Commit (`coordinates.py`)

`src/services/coordinates.py` (57 LoC) komplett löschen. Einziger Importer ist
`tests/refactor/test_epic_129a_2_module_structure.py:29`
(`importlib.import_module("services.coordinates")` in `test_coordinates_module`,
Zeilen 27-32). Diese Testfunktion wird laut Test-Politik (veraltetes Verhalten
→ Test löschen, nicht liegenlassen) ebenfalls entfernt.

### 3. Löschen per Commit (Root-Altlast, getrackt)

`red_839_fmt_val_thresholds.txt` löschen (RED-Test-Artefakt eines
abgeschlossenen Workflows, keine Referenz mehr).

### 4. Verschieben per Commit (`atoms.jsx`, `brand-kit.jsx`)

Nach `docs/design-requests/archive/atoms.jsx` bzw.
`docs/design-requests/archive/brand-kit.jsx` verschieben. Beide Dateien werden
nur von `Soll-Mockups.html` (Root) und alten Kopien unter
`claude-code-handoff/` referenziert — keine aktive Code-Referenz. Am neuen
Ort als eingefroren markieren: README-Notiz in
`docs/design-requests/archive/README.md` (neu oder ergänzt), die klarstellt,
dass diese Dateien historische Design-Artefakte sind und nicht mehr aktiv
gepflegt werden.

### 5. Lokaler Aufräum-Schritt im Hauptrepo (kein Commit, dokumentierte Anleitung)

Diese Dateien existieren **nur untracked** im Hauptrepo-Arbeitsverzeichnis
(`/home/hem/gregor_zwanzig`), nicht im Worktree, und sind daher nicht
commit-bar. Löschung erfolgt als separater, expliziter `rm`-Aufruf mit
Dateiliste (kein Glob, um Treffer auf aktive Dateien zu vermeiden) **nach
Merge dieser Scheibe**, im Hauptrepo-Arbeitsverzeichnis:

```
trip_report_old.py
red_654_drilldown_v2.txt
red_654_telegram_thunder_drilldown.txt
commit_hash.txt
staging_commit.txt
health.json
.claude/validator.env.ac1_test_bak
.claude/validator.env.ac1test
.claude/validator.env.bak2
.claude/validator.env.bak3
.claude/validator.env.external_backup
.claude/validator.env.test
.claude/validator.env.test_backup
.claude/validator.env.validator_backup_1782205985
.claude/validator.env.validator_backup_1782319787
.claude/validator.env.validator_test_backup_1782289842
gregor_zwanzig
server
```

Die beiden letzten Einträge sind alte, nirgends referenzierte Build-Artefakte
(`gregor_zwanzig` vom 15.04., `server` vom 18.05.; kein systemd-Unit, kein
Script zeigt darauf) — Tech-Lead-Entscheidung 2026-07-10: mit aufräumen, da
jederzeit aus dem Code neu baubar.

**Explizit erhalten bleiben:** `.claude/validator.env` (aktiv genutzt) und
`.claude/validator.env.example` (getrackt, Vorlage).

### 6. Invarianten (nichts tun, nur nachweisen/dokumentieren)

- `gregor-api`, `gregor_zwanzig`, `server` sind **nicht eingecheckt** —
  `.gitignore:80-82` deckt sie bereits ab. Kein Änderungsbedarf an `.gitignore`,
  nur Nachweis im Rahmen dieser Spec/PR.
- `gregor-api` im Hauptrepo-Arbeitsverzeichnis ist die **laufende
  Prod-Binary** (systemd `ExecStart` zeigt direkt darauf) — darf unter
  keinen Umständen gelöscht werden, auch nicht im lokalen Aufräum-Schritt.
  `gregor_zwanzig` und `server` (alte, nicht mehr referenzierte Binaries)
  werden im lokalen Aufräum-Schritt (Abschnitt 5) mitgelöscht — kein
  systemd-Unit oder Script referenziert sie (Tech-Lead-Entscheidung
  2026-07-10).
- `src/services/aggregation.py` und `src/services/trip_forecast.py` werden
  **nicht** angefasst — sie hängen am Legacy-CLI-Pfad (`src/app/cli.py:228`)
  mit abweichender Aggregations-Semantik. Ihr Abbau ist eine eigene
  PO-Entscheidung (CLI-Zukunft) und wird als Folge-Punkt im Issue #1215
  dokumentiert, nicht in dieser Scheibe stillschweigend angeglichen.
- `compare_subscription.py` Alt-Pfad → eigenes Issue #1131, nicht Teil dieser
  Scheibe.

## Expected Behavior

- **Input:** Bestehender Python-Quellbaum mit totem Legacy-Code in
  `weather_metrics.py` und `coordinates.py`, sowie Root-Altlasten-Dateien
- **Output:** `weather_metrics.py` ohne Legacy-Block (~1080 statt 1325 LoC),
  `coordinates.py` existiert nicht mehr, Testsuite ohne
  `test_coordinates_module`, `red_839_fmt_val_thresholds.txt` gelöscht,
  `atoms.jsx`/`brand-kit.jsx` unter `docs/design-requests/archive/`
- **Side effects:** Keine Verhaltensänderung an Produktionscode. Kein Import
  von `services.coordinates` oder den gelöschten `weather_metrics`-Symbolen
  ist mehr möglich (führt zu `ImportError`/`AttributeError`, was erwünscht ist,
  da es keine echten Aufrufer mehr gibt)

## Acceptance Criteria

- **AC-1:** Given der Legacy-Block in `src/services/weather_metrics.py` (Klassen `HourlyCell`, `CloudStatus`, Methoden `format_hourly_cell`, `hourly_cell_to_compact`, `calculate_cloud_status`, `format_cloud_status`, `get_cloud_status_emoji`) ist gelöscht / When ein Import bzw. Attribut-Zugriff auf diese Symbole in `services.weather_metrics` versucht wird / Then schlägt der Zugriff mit `ImportError`/`AttributeError` fehl, und `weather_metrics.py` hat spürbar weniger Zeilen als vorher (~1080 statt 1325 LoC); `aggregate_stage` und `_circular_mean_deg` bleiben erhalten (echter Nutzer: `tests/tdd/test_issue_721_email_outlook.py:287`)
  - Test: Import/`hasattr`-Prüfung der gelöschten Symbole scheitert; `aggregate_stage` bleibt importierbar

- **AC-2:** Given `src/services/coordinates.py` ist gelöscht / When `importlib.import_module("services.coordinates")` aufgerufen wird / Then wirft der Import einen `ModuleNotFoundError`, und die Datei existiert nicht mehr im Dateisystem
  - Test: Fehlender Import wird geprüft; `test_coordinates_module` in `tests/refactor/test_epic_129a_2_module_structure.py` ist entfernt (keine tote Testreferenz auf ein gelöschtes Modul)

- **AC-3:** Given die deterministische Kern-Testsuite (ohne `live`/`email`/`staging`-Marker) lief vor der Änderung grün / When sie nach Löschung des Legacy-Blocks und von `coordinates.py` erneut ausgeführt wird / Then bleibt sie zu 100% grün, insbesondere `tests/integration/test_segment_weather_metrics.py` und die verbleibenden Tests in `tests/refactor/test_epic_129a_2_module_structure.py`
  - Test: `uv run pytest tests/integration/test_segment_weather_metrics.py tests/refactor/test_epic_129a_2_module_structure.py` und ein voller Kern-Testlauf enden mit Exit 0

- **AC-4:** Given `red_839_fmt_val_thresholds.txt` liegt im Repo-Root / When der Commit dieser Scheibe angewendet wird / Then existiert die Datei nicht mehr im Arbeitsverzeichnis und ist aus dem Git-Tracking entfernt
  - Test: `git show HEAD:red_839_fmt_val_thresholds.txt` liefert einen Fehler ("does not exist"); `ls red_839_fmt_val_thresholds.txt` im Repo-Root schlägt fehl

- **AC-5:** Given `atoms.jsx` und `brand-kit.jsx` liegen im Repo-Root / When der Commit dieser Scheibe angewendet wird / Then liegen beide Dateien unter `docs/design-requests/archive/` (per `git mv` nachweisbar, Inhalt unverändert), und eine README-Notiz im Archiv-Verzeichnis kennzeichnet sie als eingefroren
  - Test: `ls docs/design-requests/archive/atoms.jsx docs/design-requests/archive/brand-kit.jsx` existieren; `docs/design-requests/archive/README.md` enthält einen Hinweis auf den eingefrorenen Status dieser beiden Dateien; im Repo-Root existieren die Originaldateien nicht mehr

- **AC-6:** Given `.gitignore` Zeilen 80-82 decken `gregor-api`, `gregor_zwanzig` und `/server` bereits ab / When geprüft wird, ob diese Binaries im Git-Tracking auftauchen / Then liefert `git ls-files` für keine der drei Binaries einen Treffer — kein Änderungsbedarf an `.gitignore`, nur Nachweis
  - Test: `git ls-files | grep -E '^(gregor-api|gregor_zwanzig|server)$'` liefert keine Ausgabe

- **AC-7:** Given `gregor-api` ist die laufende Produktions-Binary (systemd `ExecStart` zeigt direkt auf `/home/hem/gregor_zwanzig/gregor-api`) / When der lokale Aufräum-Schritt (Abschnitt 5) im Hauptrepo ausgeführt wird / Then ist `gregor-api` in der zu löschenden Dateiliste **nicht enthalten**, und der laufende Produktions-Dienst bleibt nach dem Aufräum-Schritt unangetastet erreichbar
  - Test: Datei-Diff des Aufräum-Schritts zeigt keine Zeile mit `gregor-api`; `systemctl status gregor-api` bzw. HTTP-Smoke-Test gegen die laufende Instanz bleibt nach dem Schritt erfolgreich

- **AC-8:** Given `src/services/aggregation.py` und `src/services/trip_forecast.py` hängen am Legacy-CLI-Pfad (`src/app/cli.py:228`) / When diese Scheibe umgesetzt wird / Then bleiben beide Dateien byteidentisch unverändert, und Issue #1215 enthält einen dokumentierten Hinweis, dass ihr Abbau eine separate PO-Entscheidung ist
  - Test: `git diff` zu dieser Scheibe zeigt keine Änderung an `src/services/aggregation.py` oder `src/services/trip_forecast.py`

- **AC-9:** Given die untrackten Root-Altlasten (`trip_report_old.py`, `red_654_drilldown_v2.txt`, `red_654_telegram_thunder_drilldown.txt`, `commit_hash.txt`, `staging_commit.txt`, `health.json`, 12 `.claude/validator.env.*`-Sicherungskopien, alte Binaries `gregor_zwanzig` + `server`) sind im Hauptrepo-Arbeitsverzeichnis vorhanden / When der dokumentierte lokale Aufräum-Schritt nach dem Merge ausgeführt wird / Then existieren diese 20 Dateien danach nicht mehr, während `.claude/validator.env`, `.claude/validator.env.example` und die Prod-Binary `gregor-api` unverändert erhalten bleiben
  - Test: `ls` auf die explizite Dateiliste schlägt für alle 20 Dateien fehl; `ls .claude/validator.env .claude/validator.env.example gregor-api` funktioniert weiterhin

## Known Limitations

- Der lokale Aufräum-Schritt (Abschnitt 5) ist nicht Teil des Git-Commits
  dieser Scheibe, da die betroffenen Dateien untracked sind und nur im
  Hauptrepo-Arbeitsverzeichnis existieren (nicht im Worktree gespiegelt). Er
  wird als separater, expliziter Schritt nach dem Merge ausgeführt und ist
  daher nicht durch den normalen `git diff`/CI-Pfad nachweisbar — Nachweis
  erfolgt durch Vorher/Nachher-`ls` im Hauptrepo.
- `src/services/aggregation.py`/`trip_forecast.py`-Abbau ist explizit
  außerhalb dieser Scheibe und benötigt eine eigene PO-Entscheidung
  (CLI-Zukunft).
- Scheibe 2 (Frontend) und Scheibe 3 (Go `internal/compare/`) sind eigene,
  spätere Workflows und nicht Bestandteil dieser Spec.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Löschung/Verschiebung von totem Code ohne externe
  Aufrufer und ohne Änderung an Architektur, Datenmodell oder
  Produktionsverhalten — kein ADR-würdiger Entscheidungsraum.

## Changelog

- 2026-07-10: Initial spec erstellt — Issue #1215, Scheibe 1
- 2026-07-10: v1.1 — Tech-Lead-Entscheidung: alte Binaries `gregor_zwanzig` +
  `server` in den lokalen Aufräum-Schritt aufgenommen (AC-9: 20 Dateien)
- 2026-07-10: v1.2 — Fakten-Korrektur nach Tiefenprüfung (TDD-RED-Phase):
  echter Methodenname `format_hourly_cell` statt `build_hourly_cell`;
  `aggregate_stage`/`_circular_mean_deg` bleiben (echter Test-Nutzer #721);
  LoC-Ziel ~1080 statt ~975. Keine AC-Aufweichung — Löschumfang präzisiert.
