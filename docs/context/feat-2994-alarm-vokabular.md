# Context: feat-2994-alarm-vokabular (Issue #2994)

## Request Summary
Paritäts-Bestandsaufnahme #1986, Eintrag P16a/NEU-13: Das alarmfähige Metrik-Vokabular
(welche AlertMetric-Werte eine Alarmregel bekommen können) ist doppelt von Hand gepflegt:
Python `_ALERTABLE_METRIC_VALUES` und Go `AlertableMetrics`. Ziel: Go leitet sein Vokabular
aus einem von Python generierten, eingebetteten Artefakt ab (Muster ADR-0045), nur noch eine Quelle.
Kein Nutzerverhalten ändert sich.

## Related Files
- `src/services/weather_change_detection.py:126-137` — `_ALERTABLE_METRIC_VALUES` (Kommentar sagt heute: „Go-Vokabular gespiegelt" → Rolle kehrt sich um: Python wird Owner)
- `src/services/weather_change_detection.py:140-166` — `catalog_id_to_alert_metrics()` filtert auf dieses Vokabular
- `internal/model/trip.go:250-261` — `var AlertableMetrics` (Handliteral, 6 Einträge)
- `internal/model/trip.go:303-333` — bestehendes `go:embed alert_metric_mapping.generated.json` + `mustParseAlertMetricMapping` (Vorbild, panic bei kaputtem JSON)
- `internal/model/trip.go:368,408` — einzige Nicht-Test-Nutzer von `AlertableMetrics` (ActiveAlertableMetricIDs-Sicherheitsnetz, SyncAlertRules)
- `internal/model/trip.go:~264` — `DefaultDeltaThreshold` muss jede alarmfähige Metrik abdecken (sonst Null-Schwelle)
- `scripts/generate_alert_metric_mapping.py` — Erzeuger mit `write()`/`check()`; hier zweites Ziel ergänzen
- `internal/model/alert_metric_mapping.generated.json` — heutiges Artefakt (Format catalog_id → [metrics]; vom Frontend ebenfalls importiert, Format NICHT ändern)
- `tests/tdd/test_alert_metric_mapping_parity.py:32-39` — von Hand gespiegeltes `_ALERTABLE_METRIC_VALUES` im Test (Zeile 109 nennt es als bewusste Rest-Doppelung)
- Go-Tests: `internal/model/alert_sync_test.go`, `alert_delta_817_test.go`, `alert_metric_mapping_panic_test.go`

## Existing Patterns
- ADR-0045 „generiertes eingebettetes Artefakt für Cross-Stack-Abbildung": Python Owner, Skript serialisiert deterministisch, Go `go:embed`, Ratchet-Test `check()` als Drift-Wächter.
- Spec `docs/specs/modules/fix_1435_e5_alert_mapping_unify.md` (Known Limitations nennt genau diese Rest-Doppelung als offen).
- ADR-0130 (gemeinsamer Textkatalog Go/Python) — gleiches Prinzip.

## Lösungsrichtung (vorläufig)
Eigene generierte Datei `internal/model/alertable_metrics.generated.json` (sortierte Liste) aus `_ALERTABLE_METRIC_VALUES`,
vom selben Skript geschrieben/geprüft; Go embed + parse mit panic, `AlertableMetrics` daraus gebaut.
Verworfen: Ableitung als Vereinigung der Mapping-Werte — heute gleich, macht das Sicherheitsnetz aber tautologisch
und verliert eine alarmfähige Metrik ohne Katalog-ID.

## Dependencies / Dependents
- Python: keine weiteren Nutzer von `_ALERTABLE_METRIC_VALUES` außer dem Paritätstest.
- Go: nur `internal/model` (trip.go). Kein Frontend-Bedarf.

## Risks
- Leeres/kaputtes Artefakt → alle Alarmregeln würden still entfernt → panic bei Init (wie Vorbild).
- Neue alarmfähige Metrik in Python ohne `DefaultDeltaThreshold` in Go → Go-Test muss Abdeckung erzwingen.
- Generierung vergessen → Ratchet-Test `check()` muss rot werden.

## Analysis

**Type:** Feature (Refactoring einer Cross-Stack-Doppelung, kein Nutzerverhalten ändert sich). Score 1 → Kontext+Analyse kombiniert (Intake-Regel Summe 1–3).

### Affected Files (Change Type)
| Datei | Typ | Änderung |
|---|---|---|
| `scripts/generate_alert_metric_mapping.py` | MODIFY | zweites Ziel `internal/model/alertable_metrics.generated.json` (sortierte Liste aus `_ALERTABLE_METRIC_VALUES`) in `write()` und `check()` |
| `internal/model/alertable_metrics.generated.json` | CREATE | generiertes Artefakt `["precipitation_sum","snow_line","temperature_max","temperature_min","thunder_level","wind_gust"]` |
| `internal/model/trip.go` | MODIFY | `AlertableMetrics`-Handliteral → `go:embed` + `mustParseAlertableMetrics` (panic bei kaputtem JSON, leerer Liste, unbekanntem Wert ohne `DefaultDeltaThreshold`) |
| `src/services/weather_change_detection.py` | MODIFY | nur Kommentar: Python ist Owner, Go liest generierte Datei |
| `tests/tdd/test_alert_metric_mapping_parity.py` | MODIFY | Handspiegel `_ALERTABLE_METRIC_VALUES` durch Import ersetzen; Ratchet für neue Datei |
| `internal/model/alertable_metrics_test.go` | CREATE | Go: Parse-Fehlerfälle panic; jede alarmfähige Metrik hat `DefaultDeltaThreshold` |

### Scope / Risk
~5–6 Dateien (zwei davon Tests, eine generiert), ~90–120 LoC. Risiko mittel: Alarm-Pfad (SyncAlertRules entfernt Regeln nicht-alarmfähiger Metriken → leere Menge würde alle Alarmregeln still löschen). Abgesichert durch panic bei Init + Ratchet.

### Technical Approach
1. Generator erweitert (gleicher Serialisierungsstil: `indent=2`, sortiert, `\n`).
2. Go: `//go:embed alertable_metrics.generated.json`, `var AlertableMetrics = mustParseAlertableMetrics(raw)` — Typ `map[AlertMetric]struct{}` bleibt, Aufrufer (trip.go:368, :408) unverändert.
3. Validierung beim Parse: JSON gültig, Liste nicht leer, jeder Eintrag hat `DefaultDeltaThreshold` (sonst stille Null-Schwelle) → sonst panic mit Hinweis auf Dateinamen.
4. Python-Test: Spiegel entfällt, `check()` meldet Abweichung der neuen Datei konkret.

Verworfen: Vokabular als Vereinigung der Mapping-Werte ableiten (keine neue Datei) — macht das Sicherheitsnetz in `ActiveAlertableMetricIDs` tautologisch und koppelt zwei Begriffe. Verworfen: Format der bestehenden Mapping-Datei ändern — Frontend importiert sie.

### Dependencies
ADR-0045 (Mechanismus), Spec `fix_1435_e5_alert_mapping_unify.md` (Known Limitations wird erledigt). Kein neues ADR nötig (Anwendung des bestehenden Mechanismus); ADR-0045 ggf. um Anwendungsfall ergänzen ist nicht nötig.

### Open Questions
Keine Produktfragen.
