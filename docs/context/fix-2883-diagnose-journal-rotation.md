# Context: fix-2883-diagnose-journal-rotation

## Request Summary
Die Diagnose-Journale `openmeteo_calls.jsonl` und `enrichment_calls.jsonl` wachsen unbegrenzt
(Prod 2026-11-09: 22,5 MB / 145 585 Zeilen seit 2026-05-22 bzw. 5,6 MB / 51 507 Zeilen seit
2026-08-20). Sie sollen wie das Warn-Dienst-Journal aus #2224 größenbasiert in genau eine
Vorgänger-Generation `.1` rotieren; alle Leser lesen aktuelle Datei + `.1`.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/official_alerts/warn_egress.py:215-242` | Vorbild `_rotate_if_needed` + `WARN_JOURNAL_MAX_BYTES` (8 MB, flock auf `<path>.lock`, Doppelprüfung unter Sperre, fail-soft). Kandidat zum Herauslösen in einen gemeinsamen Helfer |
| `src/providers/call_log.py:106-129` | Schreiber `log_api_call` → `openmeteo_calls.jsonl` (Pfad `diagnostics_path()`, Override `DIAGNOSTICS_PATH`) |
| `src/providers/enrichment_health.py:58-97` | Schreiber `log_enrichment_call` → `enrichment_calls.jsonl` (Pfad frisch über `get_data_root()`) |
| `internal/scheduler/warn_service_health.go:70-140` | Vorbild Go-Leser: `openWarnJournal`, `sameOpenFile`, Test-Naht `warnJournalBetweenOpens`; aktuelle Datei ZUERST öffnen, dann `.1`, `os.SameFile`-Dedupe |
| `internal/scheduler/enrichment_health.go:81-165` | Leser `aggregateEnrichmentCalls` — nur aktuelle Datei; Open-Fehler (auch Nicht-NotExist) setzt heute KEIN Fehler-Flag; Scan-Fehler → `journal_read_error` |
| `internal/scheduler/briefing_health.go:567-656` | Zwei Leser von `openmeteo_calls.jsonl`: `analyzeBriefingProviderErrors` (Streak + 24h-Zähler, sortiert selbst) und `findLastBriefingProviderError` (Maximum). Beide fail-soft ohne Fehler-Flag |
| `scripts/analyze_openmeteo_calls.py:34-52` | Manuelles Analyse-Skript, liest nur aktuelle Datei (`_load`) |
| `tests/tdd/test_warn_journal_rotation.py` | Vorbild-Tests (Schwelle per monkeypatch auf Modul-Konstante) |
| `internal/scheduler/warn_service_health_test.go` | Vorbild Go-Tests inkl. Rotation zwischen den Opens |
| `internal/scheduler/enrichment_health_test.go`, `briefing_health_test.go` | Bestehende Go-Tests der Leser (echte Dateien in `t.TempDir()`) |

## Existing Patterns
- #2224: Python rotiert vor dem Anhängen, Sperre nur oberhalb der Schwelle; Go öffnet aktuell → `.1`, dedupliziert per `SameFile`, fehlende Datei = legitimer Leerzustand, andere Open-/Scan-Fehler → Fehler-Flag bei erhaltenen Aggregaten.
- Alle Aggregationen der betroffenen Leser sind reihenfolgeunabhängig (Maxima, OR, `analyzeBriefingProviderErrors` sortiert); einzig `unitLatest` nutzt `>=` bei Gleichstand des Zeitstempels (Mikrosekunden, praktisch irrelevant).
- `forecast_capture._prune` löscht nur `forecast_capture_*.jsonl` mit Datum im Namen — `.jsonl.1`-Dateien sind nicht betroffen.

## Dependencies
- Upstream: `app.loader.get_data_root()`, `fcntl`, `os.replace`.
- Downstream: `/api/scheduler/status` → `briefing_health.provider_error_streak_since`, `provider_errors_recent_count`, `last_provider_error_at` und `enrichment_health.*` → `henemm-infra/scripts/check-gregor20.sh` (Fenster 24h/2h bzw. `ENRICHMENT_MAX_AGE_H=48`).

## Existing Specs
- `docs/specs/modules/fix_2224_warn_journal_rotation.md` — direktes Vorbild
- `docs/specs/modules/fix_1581_enrichment_health.md`, `fix_1633_datenwurzel_diagnose_journale.md`

## Risks & Considerations
- Aufbewahrung: bei 8 MB Schwelle reicht aktuelle Datei + `.1` (16 MB) bei heutigem Durchsatz (~130 KB/Tag bzw. ~70 KB/Tag) für Wochen–Monate; die Überwachungsfenster (≤48h) bleiben sicher abgedeckt. Ein selten benutzter Anreicherungspfad kann nach sehr langer Zeit ganz herausfallen → Key fehlt (Überwachung überspringt ihn ohnehin, wenn der letzte Versuch >48h alt ist).
- Erster Deploy: die 22,5-MB-Datei wird beim ersten Schreibvorgang komplett nach `.1` verschoben; die frühere `.1` gibt es noch nicht — kein Datenverlust beim Umstieg.
- `enrichment_health`: Nicht-NotExist-Open-Fehler werden nach Vereinheitlichung als `journal_read_error` gemeldet (bisher still) — bewusste Verbesserung, im Spec benennen.
- Herauslösen des Python-Helfers darf die bestehende monkeypatch-Naht `warn_egress.WARN_JOURNAL_MAX_BYTES` (#2224-Tests) nicht brechen.
- Go-Helfer ggf. generalisieren (`openWarnJournal`/`sameOpenFile` → gemeinsam), Test-Naht pro Leser oder gemeinsam.
- Außerhalb des Umfangs: `openmeteo_calls_go.jsonl` (Go-Schreiber, 1 238 Zeilen, klein), `track_resolution_health`-Journal.

## Analysis

### Type
Bug (Betriebsrisiko: zwei Diagnose-Journale wachsen unbegrenzt; jeder `/api/scheduler/status`-Abruf scannt sie komplett).

### Investigation (2026-11-09, direkt im Code verifiziert)
- Schreiber: `call_log.log_api_call` (openmeteo_calls.jsonl, Pfad über `diagnostics_path()`, Override `call_log.DIAGNOSTICS_PATH`) und `enrichment_health.log_enrichment_call` (enrichment_calls.jsonl, Pfad frisch über `get_data_root()`). Beide hängen nur an, beide fail-soft (`except Exception: pass`).
- Leser (vollständig, per grep über src/, internal/, scripts/, henemm-infra/scripts): Go `analyzeBriefingProviderErrors` + `findLastBriefingProviderError` (`briefing_health.go:567/633`), Go `aggregateEnrichmentCalls` (`enrichment_health.go:97`), Skript `scripts/analyze_openmeteo_calls.py` (`_load`). henemm-infra liest die Dateien NICHT direkt, nur über `/api/scheduler/status`.
- Python-Tests, die das Journal direkt lesen (z. B. `test_bug_353_trend_horizon`, `test_issue_1142_…`), schreiben weit unter 8 MB → unbeeinflusst.
- `forecast_capture.py:166` Kommentar „`enrichment_calls.jsonl` bleibt unrotiert“ wird nach dem Fix falsch → mit anpassen.
- `openmeteo.DIAGNOSTICS_PATH` ist ein toter Alt-Override (Tests patchen ihn noch); nicht im Umfang.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/utils/journal_rotation.py` | CREATE | Gemeinsamer Helfer `rotate_if_needed(path, max_bytes)` — 1:1 die #2224-Logik (schneller Pfad ohne Sperre, flock auf `<path>.lock`, Doppelprüfung unter Sperre, `os.replace` → `.1`, fail-soft) |
| `src/services/official_alerts/warn_egress.py` | MODIFY | `_rotate_if_needed(path)` bleibt als dünner Wrapper, liest `WARN_JOURNAL_MAX_BYTES` zur Aufrufzeit (monkeypatch-Naht der #2224-Tests bleibt) |
| `src/providers/call_log.py` | MODIFY | `OPENMETEO_JOURNAL_MAX_BYTES = 8 MiB`; Rotation vor dem Anhängen |
| `src/providers/enrichment_health.py` | MODIFY | `ENRICHMENT_JOURNAL_MAX_BYTES = 8 MiB`; Rotation vor dem Anhängen |
| `internal/scheduler/journal_rotation.go` | CREATE | `openJournalGenerations(path) ([]*os.File, readErr bool)`: aktuelle Datei ZUERST, dann `.1`, `os.SameFile`-Dedupe, NotExist = Leerzustand, sonst Fehler-Flag; gemeinsame Test-Naht `journalBetweenOpens` |
| `internal/scheduler/warn_service_health.go` | MODIFY | auf gemeinsamen Helfer umstellen (`openWarnJournal`/`sameOpenFile`/`warnJournalBetweenOpens` entfallen) |
| `internal/scheduler/warn_service_health_test.go` | MODIFY | Test-Naht-Name nachziehen (Verhalten unverändert) |
| `internal/scheduler/briefing_health.go` | MODIFY | beide openmeteo-Leser lesen aktuelle Datei + `.1`; Signatur und fail-soft (kein Fehler-Flag) bleiben |
| `internal/scheduler/enrichment_health.go` | MODIFY | `aggregateEnrichmentCalls` liest aktuelle Datei + `.1`; Nicht-NotExist-Open-Fehler setzen jetzt `journal_read_error` (bewusste Verbesserung) |
| `scripts/analyze_openmeteo_calls.py` | MODIFY | `_load` liest `<pfad>.1` + `<pfad>` |
| `src/services/forecast_capture.py` | MODIFY | Kommentar Z. 166 korrigieren |
| `tests/tdd/test_diagnose_journal_rotation.py` | CREATE | Python: Rotation je Schreiber, eine Generation, Parallel-Schreiber, fail-soft, Altdatei >Schwelle beim ersten Schreiben |
| `internal/scheduler/briefing_health_test.go`, `enrichment_health_test.go` | MODIFY | Go: Fehler/Erfolge in `.1` zählen mit, Streak über Rotationsgrenze, Rotation zwischen den Opens (kein Doppelzählen), Verzeichnis als `.1` → Fehler-Flag (nur enrichment) |
| `docs/specs/modules/fix_2883_diagnose_journal_rotation.md` | CREATE | Spec |

### Scope Assessment
- Files: ~10 Quell-/Skriptdateien + 3–4 Testdateien + Spec
- Estimated LoC: Quellcode ca. +110/−60, Tests ca. +300
- Risk Level: LOW–MEDIUM — reine Diagnose-Pfade, fail-soft; Risiko liegt in der Überwachung (`check-gregor20.sh` liest `provider_error_streak_since`, `provider_errors_recent_count`, `enrichment_health.*`): ein Leserfehler könnte Alarme verschlucken oder falsch auslösen. Abgesichert durch Go-Tests auf echten Dateien.

### Technical Approach
1. **Python-Helfer herauslösen** statt kopieren (DRY, drei Schreiber teilen dieselbe Rotationssemantik). Schwelle als Parameter; jeder Schreiber hat eigene Modul-Konstante (8 MiB), zur Aufrufzeit gelesen → monkeypatch-fähig in Tests.
2. **Go-Helfer generalisieren**: Öffnen beider Generationen in EINER Funktion; die Scan-Logik je Leser bleibt, läuft über beide Dateien. Alle Aggregationen sind reihenfolgeunabhängig (Maxima/OR; `analyzeBriefingProviderErrors` sortiert selbst) — Leseordnung beliebig.
3. **briefing_health bleibt ohne Fehler-Flag** (API-Felder unverändert, kein neues Feld); nur enrichment bekommt die Verschärfung, weil es das Feld `journal_read_error` schon hat.
4. **Schwelle 8 MiB für beide** (Konsistenz mit #2224). Aufbewahrung: openmeteo ~130 KB/Tag → aktuelle Datei ≈ 2 Monate, + `.1` ≈ 4 Monate; enrichment ~70 KB/Tag → noch länger. Überwachungsfenster ≤ 48 h bleiben immer abgedeckt.
5. **Umstieg:** erste Schreiboperation nach Deploy verschiebt die 22,5-MB-Datei nach `.1` → kein Datenverlust; die alte `.1` existiert nicht. Erst die übernächste Rotation (≈ 2 Monate später) verwirft die Altdaten.

### Befunde gegen den Plan
- Generalisierung des Go-Warn-Lesers berührt einen gerade erst ausgelieferten Pfad (#2224). Abwägung: zwei Kopien desselben Öffnen-Musters wären die schlechtere Wahl (Rennbedingungs-Logik an drei Stellen pflegen). Die bestehenden #2224-Go-Tests sichern das Verhalten ab.
- Selten genutzter Anreicherungspfad kann nach sehr langer Zeit ganz aus den Journalen fallen → Key fehlt in `enrichment_health`. Die Überwachung überspringt Pfade ohnehin, deren letzter Versuch > 48 h alt ist → kein Fehlalarm. Im Spec als bekannte Grenze benennen.

### Dependencies
- Upstream: `app.loader.get_data_root()`, `fcntl`, `os.replace`; Go `os`, `bufio`.
- Downstream: `/api/scheduler/status` → `henemm-infra/scripts/check-gregor20.sh` (keine Änderung nötig, Feldnamen bleiben).

### Open Questions
- keine (rein technisch; Schwelle und Generationenzahl folgen der PO-freigegebenen #2224-Entscheidung).
