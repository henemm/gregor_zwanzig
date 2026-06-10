# Context: Issue #701 — Alerts-Tab metrik-gekoppelt (Backend Auto-Sync + Desktop TE2)

## Request Summary
Die Alerts-Tab soll nicht mehr frei editierbare Regeln anzeigen, sondern automatisch genau eine absolute AlertRule pro aktiver, alert-fähiger Metrik aus dem Wetter-Metriken-Tab. Das Backend synchronisiert die Regeln beim Speichern des WeatherConfig (Read-Modify-Write/Merge).

## Related Files

| File | Relevanz |
|------|----------|
| `internal/handler/trip.go` | `UpdateTripHandler` (PUT /api/trips/{id}) — Merge-Logik |
| `internal/handler/weather_config.go` | `PutTripWeatherConfigHandler` — **Hook-Punkt** für Alert-Sync |
| `internal/model/trip.go` | `AlertRule`, `AlertRuleKind`, `AlertMetric` — Datenmodell |
| `internal/store/store.go` | `SaveTrip` — Nil-Coercion, kein Sync hier |
| `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` | `btn-ghost-add` disabled, muss verschwinden; `alertRules` aus trip.alert_rules |
| `frontend/src/lib/components/alerts-tab/AlertCard.svelte` | Delta-Pfad/Kanal-Override entfernen |
| `frontend/src/lib/utils/alertMetricLabels.ts` | `ALERT_METRIC_LABELS` (alle 9 Metriken) |
| `frontend/src/lib/components/alert-rules-editor/alertRuleDefaults.ts` | `DELTA_ONLY_METRICS` = {temperature_change, wind_change, precipitation_change, thunder_level} |

## Existing Patterns

- **Read-Modify-Write:** `UpdateTripHandler` lädt `existing` via `s.LoadTrip`, patcht nur gesetzte Felder, speichert. Gleich muss die Alert-Sync-Funktion arbeiten.
- **Nil-Coercion in SaveTrip:** `if trip.AlertRules == nil { trip.AlertRules = []model.AlertRule{} }` — unveränderlich lassen.
- **AlertRule.ID:** `crypto/rand`-generierte UUID (8 Hex-Zeichen via `randomShortID()`).
- **WeatherConfig-Endpoint:** `PUT /api/trips/{id}/weather-config` → `PutTripWeatherConfigHandler` schreibt `trip.DisplayConfig`. Die Metriken liegen in `trip.display_config.metrics` (Array von `{metric_id, enabled, ...}`).

## Alert-fähige Metriken (absolute-capable)
Alle die NICHT in `DELTA_ONLY_METRICS` sind: `wind_gust`, `precipitation_sum`, `temperature_min`, `temperature_max`, `snow_line`.  
`thunder_level` ist in `DELTA_ONLY_METRICS` → kein Alert in der neuen Logik.  
`*_change` Metriken → kein Alert.

## Sync-Logik (Merge-Algorithmus)
```
syncAlertRules(existing []AlertRule, activeMetrics []string) []AlertRule:
  result = []
  for each alertable metric in activeMetrics:
    if existing rule with kind=absolute for this metric exists:
      result.append(existing rule)  // Schwellwert erhalten!
    else:
      result.append(newDefaultRule(metric))  // Default-Threshold
  return result
  // Metriken die nicht mehr aktiv sind → NICHT in result → implizit entfernt
```

## Default-Thresholds (Backend, Go)
Müssen neu definiert werden (analog zu `alertRuleDefaults.ts::newDefaultRule`):
- wind_gust: 50 km/h, warning
- precipitation_sum: 20 mm, warning
- temperature_min: -5 °C, warning
- temperature_max: 35 °C, info
- snow_line: 1500 m, info

## Dependencies

- **Upstream:** `trip.display_config.metrics` (WeatherMetricsTab speichert hier)
- **Downstream:** Python-Scheduler liest `trip.alert_rules` für Alert-Versand
- **Blocker gelöst:** #694 (onTripUpdate) und #690 (presets) sind deployed

## Risks & Considerations

- **Datenverlust-Schutz:** Nur nicht-aktive Metriken verlieren ihre Regel, nie bestehende absolute Schwellwerte aktiver Metriken (AC-4).
- **`thunder_level` als Sonderfall:** In DELTA_ONLY_METRICS → kein Alert-Sync. Wenn Nutzer thunder_level aktiviert hat, bekommt er KEINEN Auto-Alert. Das entspricht AC-2 (nur absolute).
- **Kanal-Vererbung (AC-5):** Kanäle sind read-only in der AlertCard. Frontend zeigt `activeChannels` aus `report_config`, keine Bearbeitungs-UI.
- **Mandantentrennung (AC-6):** `PutTripWeatherConfigHandler` nutzt bereits `s.WithUser(...)`, Alert-Sync läuft im gleichen Kontext — sicher.
- **Frontend-Abkopplung:** `alertRules` in AlertsTab.svelte wird weiterhin aus `trip.alert_rules` gelesen (vom Backend synced), aber der Add-Button entfällt komplett.
