# Context: fix-2224-warn-journal-rotation

## Request Summary
`warn_service_calls.jsonl` (Diagnose-Journal aller Warn-Dienst-Abrufe + Zonen-Drift-Ereignisse) wird nur angehängt, nie rotiert. Prod 2026-11-09: 64,9 MB / 406.506 Zeilen seit 2026-07-22 (~3.700 Zeilen ≈ 600 KB pro Tag). Die Go-Zustandsprüfung liest die Datei bei jedem Scheduler-Status-Abruf komplett. Ziel: begrenztes Wachstum ohne Verlust der Aussagen, die der Monitor braucht.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/official_alerts/warn_egress.py:197-310` | Einziger Schreiber: `warn_calls_path()`, `log_warn_service_call()`, `log_zone_drift()`; append per `path.open("a")`, fail-soft |
| `internal/scheduler/warn_service_health.go` | Einziger Leser: `aggregateWarnServiceCalls(path)` scannt die ganze Datei, liefert je Dienst `last_attempt_at`, `last_success_at`, `self_throttled`, `zone_drift`-Zähler (kumulativ) + `journal_read_error` |
| `internal/scheduler/scheduler.go:1505` | hängt `warn_service_health` in die Scheduler-Status-Antwort |
| `/home/hem/henemm-infra/scripts/check-gregor20.sh:488-560` | Konsument: Alarm nur bei Versuch ≤3h ohne Erfolg ≤3h; Zonen-Drift nur bei Frische ≤24h (`ZONE_DRIFT_MAX_AGE_H`) — Zählerhöhe nur informativ |
| `tests/conftest.py:605-650` | biegt das Journal für jeden Test auf eine Wegwerfdatei um (`WARN_CALLS_PATH_OVERRIDE`) |
| `tests/tdd/test_warn_service_egress.py`, `test_dpc_zone_drift.py`, `test_warn_journal_felder.py`, `test_warn_service_health_journal.py`, `test_dwd_warnzellen_drift.py`, `test_warn_feed_single_flight.py`, `test_warn_services_rest.py` | bestehende Tests rund ums Journal |
| `internal/scheduler/warn_service_health_test.go` | Go-Tests des Lesers |

## Existing Patterns
- `fcntl.flock` mit `<datei>.lock`: `src/services/forecast_budget.py`, `alert_check_state.py`, `briefing_slots.py`.
- Tagesdateien + Löschen alter Tage: `src/services/forecast_capture.py:144` (`forecast_capture_YYYY-MM-DD.jsonl`).
- Begrenzung nach Bytes: `src/providers/thunder_window_cache.py` (`max_bytes`, nur im Speicher).
- Kein bestehender Helfer für rotierende JSONL-Journale.

## Dependencies
- Upstream: `app.loader.get_data_root()` (prod `/var/lib/gregor`, Env `GZ_DATA_DIR`).
- Downstream: Go `WarnServiceHealth()` → `/api/scheduler/status` → `check-gregor20.sh` (BetterStack-Heartbeat).

## Existing Specs
- `docs/specs/modules/fix_1422_warn_ausfall_alarm.md` — Rohdaten-Aggregation, Übergangsfenster
- `docs/specs/modules/fix_1434_dpc_zonen_drift.md` — Drift-Zeilen, kumulative Zähler + Zeitstempel je Kategorie
- `docs/specs/modules/fix_1633_datenwurzel_diagnose_journale.md` — Pfadauflösung
- `docs/specs/modules/warn_service_consumption*.md` — Egress-Journal

## Risks & Considerations
- **Kontinuität über die Rotation:** Liest Go nach Rotation nur die neue Datei, verschwindet ein seltener Dienst als Schlüssel (nie versucht → kein Alarm, unkritisch); ein Dienst mit Versuchen, aber letztem Erfolg nur in der alten Generation, sähe aus wie „kein Erfolg seit nie" → Fehlalarm. Lösung: Go liest Vorgänger-Generation + aktuelle Datei; Generation muss deutlich länger als das 3h-/24h-Fenster reichen.
- **Nebenläufigkeit:** ein uvicorn-Prozess, aber mehrere Threads/Tasks schreiben; Rotation (Prüfen + Umbenennen) braucht eine Sperre, sonst kann eine doppelte Umbenennung die Vorgänger-Generation überschreiben. Append während `rename` ist POSIX-sicher (offener Deskriptor schreibt in die umbenannte Datei).
- **Fail-soft bleibt Pflicht:** Rotation darf den Abruf nie beeinträchtigen.
- **Drift-Zähler** werden dadurch zu „Vorkommen im Aufbewahrungsfenster" statt „seit Juli" — Monitor wertet nur Frische aus, Doku in Go-Kommentar/Spec anpassen.
- **Bestand Prod:** 65-MB-Datei wird bei der ersten Rotation zur Vorgänger-Generation und fällt bei der zweiten weg; Go liest beim ersten Mal noch 65 MB — einmalig akzeptabel.
- **Schwesterjournale ebenfalls unrotiert (Nebenbefund):** `openmeteo_calls.jsonl` 22,5 MB, `enrichment_calls.jsonl` 5,6 MB — eigener Leser/Schreiber, nicht Teil dieses Issues; als Folge-Issue im Epic #2733 anlegen.
- Staging: Daten unter Staging-Datenwurzel; kein fachlicher Unterschied.

## Analysis

### Type
Bug (Betriebsrisiko: unbegrenztes Dateiwachstum, Go-Zustandsprüfung liest bei jedem Status-Abruf die ganze Datei)

### Messbefund Prod (2026-11-09)
- 406.506 Zeilen / 65 MB seit 2026-07-22, davon nur **32 Drift-Zeilen**; Masse sind Cache-Treffer-Zeilen (`meteoalarm_feed:XX`, `cache_hit=true`), die die Go-Aggregation ohnehin ignoriert.
- Prod-Python = ein uvicorn-Prozess (keine `--workers`), mehrere Threads/Tasks schreiben.
- Kein weiterer Code-Leser außer `warn_service_health.go` (grep über src/api/internal/scripts + henemm-infra).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/official_alerts/warn_egress.py` | MODIFY | Helfer `_rotate_if_needed(path)` vor jedem Append in `log_warn_service_call()` und `log_zone_drift()`: `stat` ≥ Schwelle → `fcntl.flock` auf `<datei>.lock` → Größe unter Sperre erneut prüfen → `os.replace(path, path.1)`; eigenes try/except (fail-soft). Schwelle als Modulkonstante, testbar überschreibbar |
| `internal/scheduler/warn_service_health.go` | MODIFY | Aggregation über zwei Dateien: **erst aktuelle Datei öffnen (fd halten), dann `.1`**; `.1` überspringen, wenn `os.SameFile` mit der bereits geöffneten aktuellen Datei (Rotation zwischen den Opens → keine Doppelzählung). Fehlende Datei(en) legitim, echte Lesefehler einer der beiden ⇒ `journal_read_error`. Kommentar zu Drift-Zählern: „Vorkommen im Aufbewahrungsfenster" statt kumulativ seit Beginn |
| `internal/scheduler/warn_service_health_test.go` | MODIFY | Fälle: nur `.1`, beide Dateien (letzter Erfolg nur in `.1`), keine `.1`, Lesefehler in `.1`, Hardlink `.1`=aktuell (SameFile) |
| `tests/tdd/test_warn_journal_rotation.py` | CREATE | Rotation bei Schwelle, genau eine Vorgänger-Generation, Inhalt bleibt erhalten, parallele Schreiber (Threads) → keine verlorene `.1`, fail-soft bei Rotationsfehler |
| `docs/specs/modules/fix_2224_warn_journal_rotation.md` | CREATE | Spec |

### Scope Assessment
- Files: 5
- Estimated LoC: ca. +160/-10 (Produktivcode ~50)
- Risk Level: LOW–MEDIUM (isolierte Diagnose-Datei; Risiko ist ein Fehlalarm des Warn-Ausfall-Monitors, nicht Nutzer-Funktion)

### Technical Approach (Empfehlung Plan-Bewertung, übernommen)
Variantenvergleich (~600 KB/Tag):

| Variante | Obergrenze Platte | Rückblick | Bewertung |
|---|---|---|---|
| Größe 5 MB, 1 Generation | ~10 MB | 8–16 Tage | ok, Drift-Historie knapp |
| **Größe 8 MB, 1 Generation** | **~16 MB** | **13–26 Tage** | **gewählt**: >10× das 24h-Monitorfenster, Go-Scan ≤16 MB |
| Tagesdateien (wie forecast_capture) | N Tage | exakt N | mehr Code (Glob/Sortierung in Go), mehr Dateien |
| Cache-Treffer nicht mehr loggen | — | — | ändert Journal-Semantik (#1397-Verbrauchsmessung), behebt Unbegrenztheit nicht; nicht in diesem Issue |

Entscheidung: größenbasierte Rotation, Schwelle 8 MB, genau eine Vorgänger-Generation `warn_service_calls.jsonl.1`.

**Lese-Reihenfolge Go (Race):** Würde Go erst `.1`, dann die aktuelle Datei lesen, und dazwischen rotiert Python, fehlen die gerade umbenannten Zeilen → möglicher Fehlalarm („kein Erfolg"). Daher aktuelle Datei zuerst öffnen; Doppel-Lesen bei Rotation dazwischen per `os.SameFile` vermeiden.

**Auslieferungsreihenfolge:** Prod-Datei ist 65 MB → der erste Schreibvorgang nach Deploy rotiert sofort. Go-Leser muss `.1` dann schon kennen; beide Teile im selben PR/Deploy. Restfenster (Python neu vor Go neu) liegt im Sekundenbereich und ist kleiner als das 3h-Monitorfenster, da Go nach eigenem Neustart `.1` liest — unkritisch. Erste Rotation: Go liest 65-MB-`.1` einmalig bis zur zweiten Rotation (~13 Tage) — akzeptiert.

### Dependencies
- Upstream: `app.loader.get_data_root()`; `WARN_CALLS_PATH_OVERRIDE` (Tests).
- Downstream: Go `WarnServiceHealth()` → `/api/scheduler/status` → `henemm-infra/scripts/check-gregor20.sh` (unverändert, wertet nur Frische aus).

### Nebenbefund
- Schwesterjournale `openmeteo_calls.jsonl` (22,5 MB), `enrichment_calls.jsonl` (5,6 MB) unrotiert → Folge-Issue #2883 (Epic #2733).

### Open Questions
- keine (keine Produktentscheidung betroffen; Monitor-Verhalten bleibt gleich)
