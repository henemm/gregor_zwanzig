# Context: fix-1257-alert-metric-mapping

## Request Summary

Alarm-Regeln (`alert_rules`) werden bei jedem Speichern/Laden eines Trips vernichtet,
weil zwei getrennte Namensräume für dieselben Wettergrößen existieren (Katalog-Vokabular
vs. AlertMetric-Vokabular) und im Go-Persistenzpfad kein Übersetzer dazwischen sitzt.
Ergebnis: 0 von 15 Prod-Trips haben Alarm-Regeln. PO-Entscheidung: rückwirkend materialisieren.

## Die zwei Vokabulare (Schnittmenge = leer)

| Wettergröße | Katalog-ID (`src/app/metric_catalog.py`) | AlertMetric (`internal/model/trip.go`) |
|---|---|---|
| Böen | `gust` (:155) | `wind_gust` (:39) |
| Niederschlag | `precipitation` (:185) | `precipitation_sum` (:40) |
| Temperatur warm | `temperature` (:78) | `temperature_max` (:42) |
| Temperatur kalt | `temperature_cold` (:92) | `temperature_min` (:41) |
| Schneefallgrenze | `snowfall_limit` (:266) | `snow_line` (:44) |
| Gewitter | `thunder` (:231) | `thunder_level` (:43) |
| Nullgradgrenze | `freezing_level` (:391) | `freezing_level` |

## Related Files

| File | Relevance |
|------|-----------|
| `internal/model/trip.go:180-217` | `ActiveAlertableMetricIDs()` — die kaputte Naht: schlägt Katalog-ID roh in `AlertableMetrics` (Alarm-Vokabular) nach (Zeile 210), matcht nie |
| `internal/model/trip.go:227-278` | `SyncAlertRules()` — baut Ergebnis nur aus `activeMetricIDs`; legt Default-Delta-Regel pro aktiver alarmfähiger Metrik an; bei leerer Eingabe → `[]` (Löschung) |
| `internal/model/trip.go:137-145` | `AlertableMetrics`-Map (Keys im Alarm-Vokabular) |
| `internal/model/trip.go:149-160` | `DefaultDeltaThreshold` — Default-Werte (gust 20 km/h, precip 10 mm, temp 5 °C, thunder 1, snow_line 200 m) |
| `internal/store/trip.go:113-116` | LoadTrip: Sync **in-memory** (kein Write-Back) |
| `internal/store/trip.go:139-141` | SaveTrip: Sync + **Persistenz** |
| `internal/handler/weather_config.go:71-72` | PUT weather-config: eigener Pfad via `extractActiveMetricIDs` (:145-170), gleiches Mismatch |
| `src/services/weather_change_detection.py:78-97` | **Bereits existierender Übersetzer** `_ALERT_METRIC_TO_CATALOG_ID` (AlertMetric → Katalog-IDs) — aber nur Python-seitig, nicht im Go-Pfad |
| `src/services/trip_alert.py:137,299` | `has_active_rules` liest `alert_rules` für Enable-Gating (neben `metric_alert_levels`/`alert_preset`) |
| `src/services/trip_alert.py:984-1002` | `_effective_alert_channels` liest `alert_rules` nur für Kanal-Wahl; Fallback auf Briefing-Kanäle |
| `internal/model/alert_sync_test.go` | Naht-Tests — rufen `SyncAlertRules` direkt mit **Alarm-Vokabular** auf, umgehen die echte Katalog-Naht |

## Existing Patterns

- **Übersetzer existiert schon (Python):** `_ALERT_METRIC_TO_CATALOG_ID` bildet AlertMetric → Tupel von Katalog-IDs ab. Wichtig: **many-to-many** — `TEMPERATURE_MIN → (temperature_cold, temperature)`, `TEMPERATURE_MAX → (temperature,)`, `SNOW_LINE → (snowfall_limit, freezing_level)`. Die Vorwärtsrichtung (Katalog→AlertMetric), die der Go-Pfad braucht, ist also mehrdeutig: `temperature` gehört zu min UND max.
- **Sync-on-Load/Save:** Regeln werden bei jedem Laden neu berechnet (in-memory) und beim nächsten Save persistiert — deshalb ist nach dem Fix kein separates Migrationsskript nötig; die Materialisierung greift lazy beim nächsten Save, für die Engine effektiv sofort beim Load.

## Dependencies

- Upstream (was `SyncAlertRules` konsumiert): `display_config.metrics[].metric_id` aus dem Katalog; `AlertableMetrics`- und `DefaultDeltaThreshold`-Maps.
- Downstream (wer `alert_rules` liest): Go-Store (Persistenz), Python `trip_alert.py` (Enable-Gating + Kanalwahl). **Nicht** der eigentliche Delta-Detektor — siehe Risiko.

## Existing Specs

- Kein dediziertes Spec-File für die Alert-Sync-Naht gefunden. Verwandt: #809/#817 (Delta-Alarm-Pfad), #701 (Alerts-Metrik-Sync), #846/#946 (`alert_preset`/`metric_alert_levels`).

## Risks & Considerations

1. **[HIGH] Der Fix stellt das Alarm-Verhalten evtl. nicht vollständig her.** Der Python-Delta-Detektor (`DeviationAlertEngine`, `trip_alert.py:172-277`) liest `alert_rules.metric` **nicht** — er läuft über `display_config` + `metric_alert_levels`. `alert_rules` steuert Python-seitig nur (a) `has_active_rules` (Enable-Gating) und (b) Kanal-Auswahl. Zu klären in der Analyse: Ist die Materialisierung der `alert_rules` das eigentliche Ziel, oder muss zusätzlich der Detektor-Pfad an `alert_rules` gehängt werden? (Der Issue-Titel „feuert nie" ist präziser: die Regeln verschwinden — ob ihr Wiederherstellen Alarme auslöst, ist die zweite Frage.)
2. **[HIGH] Vorwärts-Mapping ist mehrdeutig.** `temperature` → min oder max? Design-Entscheidung nötig: ordnet eine aktive `temperature`-Metrik im Katalog eine `temperature_max`-Regel zu, eine `temperature_min`-Regel, oder beide? Analog `freezing_level` (gehört zu snow_line UND freezing_level).
3. **[MEDIUM] Rückwirkende Materialisierung (PO-entschieden).** Sobald das Mapping greift, bekommen alle Bestands-Trips beim nächsten Save Default-Delta-Regeln. Bei `gr221-mallorca.json` sind das gleich mehrere (gust, precipitation, snowfall_limit, thunder). Prüfen: greift der Sync bei Load auch bei Trips, die aktuell gar kein `alert_rules`-Feld haben (fehlt komplett bei gr221)?
4. **[MEDIUM] Zwei Go-Pfade mit demselben Mismatch.** `ActiveAlertableMetricIDs` (Store) UND `extractActiveMetricIDs` (Handler) müssen beide über den neuen Übersetzer laufen — sonst bleibt einer kaputt.
5. **[MEDIUM] Die Naht-Tests maskieren den Bug.** `alert_sync_test.go` / `store_809_test.go` setzen `metric_id: "wind_gust"` (Alarm-Vokabular) in den display_config. Der neue Test MUSS echte Katalog-IDs (`gust`, `snowfall_limit`, `thunder`) durch `ActiveAlertableMetricIDs` schicken und die materialisierten Regeln prüfen.
6. **[LOW] Single-Source-Redundanz.** Die neue Go-Abbildung darf nicht ein drittes, drift-anfälliges Vokabular werden. Idealerweise EINE Definition (Go) plus ein Test, der sie gegen die Python-Bridge konsistent hält — oder klar dokumentierte einzige Wahrheit.

## Analysis

### Type
Bug (Datenverlust — `alert_rules` wird bei Save/Load vernichtet).

### Was der Fix WIRKLICH leistet (Prämissen-Korrektur zum Issue)

Der Issue-Text sagt „der Delta-Alarm feuert nie". Das ist zu stark. Verifiziert im Code:
- Der Live-Delta-Detektor (`DeviationAlertEngine`, `_select_detector`) liest `trip.alert_rules` an **keiner** Stelle. Er speist sich aus `metric_alert_levels` + `display_config` (`trip_alert.py:182-192`). Die Funktion `WeatherChangeDetectionService.from_alert_rules(...)` bekommt zur Laufzeit **erzeugte** Regeln aus `metric_alert_levels`, NICHT das persistierte `alert_rules`-Array.
- `trip.alert_rules` wird nur an zwei Stellen konsumiert: (1) Enable-Gate `has_active_rules` (`trip_alert.py:137/:299`), (2) Kanal-Wahl `_effective_alert_channels` (`:993-1006`).

**Folge — der Fix leistet genau:**
- **(i) Behebt den Datenverlust** (Round-Trip-Integrität): Regeln bleiben über Save/Load erhalten. Das ist der eigentliche Bug.
- **(ii) Behebt ein Fehl-Gating:** Trips, deren EINZIGE aktive Alarmquelle `alert_rules` ist (kein Preset, keine `metric_alert_levels`), werden nicht mehr fälschlich vom Prüf-Gate ausgeschlossen.
- **(iii) Verändert NICHT**, welche Metrik mit welcher Schwelle innerhalb eines geprüften Trips feuert — das ist zu 100 % `display_config`/`metric_alert_levels`-getrieben. Die materialisierten Default-Schwellen (`DefaultDeltaThreshold`) liest der Detektor nie.
- **(iv) Kanäle unverändert:** materialisierte Default-Regeln haben keine `Channels` → Legacy-Briefing-Kanal-Pfad bleibt.

→ **Spec darf NICHT versprechen** „Alarme für Metrik X werden aktiviert". Korrekt: „Alarm-Regeln überleben Save/Load; fälschliches Gate-Ausschließen entfällt."

### Technischer Ansatz (empfohlen)

1. **Go-Vorwärts-Abbildung** Katalog-ID → AlertMetric(s), definiert als **exakte Inverse** der bestehenden Python-Bridge `_ALERT_METRIC_TO_CATALOG_ID`, gefiltert auf `AlertableMetrics`:
   - `gust→{wind_gust}`, `precipitation→{precipitation_sum}`, `thunder→{thunder_level}`
   - `temperature→{temperature_min, temperature_max}` (beide — `temperature_cold` ist `selectable=False`, nie eigenständig im display_config; `temperature` ist der einzige User-Toggle für warm+kalt)
   - `snowfall_limit→{snow_line}`, `freezing_level→{snow_line}` (dedup; Go hat kein eigenes `AlertMetricFreezingLevel`)
2. **Zwei Go-Pfade zusammenlegen:** `extractActiveMetricIDs` (`weather_config.go:145-170`) löschen und `model.ActiveAlertableMetricIDs` wiederverwenden. Beseitigt einen latenten zweiten Bug und macht das Mapping Go-seitig single-source.
3. **Drift-Schutz:** Go-Golden-Test pinnt die erwartete Inverse; Python-Paritätstest assertet dieselbe Inverse gegen `_ALERT_METRIC_TO_CATALOG_ID`. Kein Codegen, keine geteilte Datei — gleiche Disziplin wie beim bestehenden „Cross-Lang-Wertekontrakt" (`trip.go:146-147`).
4. **Rückwirkende Materialisierung:** `LoadTrip` self-heilt bereits in-memory, `SaveTrip` persistiert. Nach dem Fix materialisiert der nächste Save automatisch (lazy). Für sofortiges On-Disk-Rewrite aller Bestands-Trips: optionaler einmaliger Batch-`SaveTrip`-Lauf (Deploy-Migrationsschritt). **← PO-Präzisierung offen (s.u.).**

### Affected Files (with changes)
| File | Change | Description |
|------|--------|-------------|
| `internal/model/trip.go` | MODIFY | Inverse-Map `catalogIDToAlertMetrics`; `ActiveAlertableMetricIDs` übersetzt vor Alertable-Filter (~25-40 LoC) |
| `internal/handler/weather_config.go` | MODIFY | `extractActiveMetricIDs` entfernen, `model.ActiveAlertableMetricIDs` wiederverwenden (~-20 LoC) |
| `internal/model/*_test.go` | CREATE/MODIFY | Golden-Mapping-Test inkl. temperature→{min,max}, freezing_level+snowfall_limit→snow_line-Dedup; Naht-Test mit ECHTEN Katalog-IDs durch `ActiveAlertableMetricIDs` (~50-70 LoC) |
| `tests/tdd/test_alert_metric_mapping_parity.py` | CREATE | Python-Paritätstest: Inverse von `_ALERT_METRIC_TO_CATALOG_ID` gegen Go-Erwartung (~30 LoC) |
| (optional) Deploy-Migrationsschritt | — | Batch-`SaveTrip` für sofortiges On-Disk-Rewrite, falls PO das will |

### Scope Assessment
- Files: 4 Code/Test + optional 1 Migration
- Estimated LoC: ~+130 / -20 (unter 250-Limit)
- Risk Level: MEDIUM (kritischer Pfad, aber enge Fläche; Firing-Verhalten bleibt per Befund A(iii) unverändert → geringes Regressionsrisiko)

### Open Questions (PO-entschieden 2026-07-15)
- [x] **Q1 – Erwartung geschärft:** Fix gilt als *Datenverlust-Fix* (Regeln überleben Save/Load), NICHT als „schaltet Alarme ein". Alarm-Feuern läuft über `metric_alert_levels`-Pfad (#809/#817), bleibt unangetastet. Spec formuliert entsprechend.
- [x] **Q2 – Rückwirkung: AKTIVER Rewrite.** Einmaliger Batch-`SaveTrip`-Migrationslauf beim Deploy schreibt Default-Regeln sofort on-disk in alle Bestands-Trips (0/15 → 15/15). Pflicht: vorheriges Backup (Persistenz-Änderung), idempotent, als `claude-gregor` pro Host (`operations_playbook.md`).
- [x] **Q3 – Scope-Grenze bestätigt:** Detektor wird NICHT an `alert_rules` gehängt — bleibt der `metric_alert_levels`-Pfad.
