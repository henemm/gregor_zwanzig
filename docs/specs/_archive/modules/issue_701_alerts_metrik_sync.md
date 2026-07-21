---
entity_id: issue_701_alerts_metrik_sync
type: module
created: 2026-06-10
updated: 2026-06-10
status: draft
version: "1.0"
tags: [alerts, weather-config, backend, frontend, epic-700]
---

# Issue #701 — Alerts-Tab metrik-gekoppelt: Backend Auto-Sync + Desktop TE2

## Approval

- [ ] Approved

## Purpose

Das Backend synchronisiert `alert_rules` automatisch mit den aktiven Wetter-Metriken eines Trips (Read-Modify-Write/Merge). Die Alerts-Tab zeigt genau eine absolute Alert-Regel pro aktiver, alert-fähiger Metrik — kein manuelles Anlegen, kein Delta-Pfad, kein Kanal-Override in der UI.

## Source

- **Go-Handler:** `internal/handler/weather_config.go` — `PutTripWeatherConfigHandler` (Hook-Punkt)
- **Go-Model:** `internal/model/trip.go` — neue Hilfsfunktionen `SyncAlertRules`, `DefaultAlertThresholds`
- **Frontend:** `frontend/src/lib/components/alerts-tab/AlertsTab.svelte`, `AlertCard.svelte`

## Estimated Scope

- **LoC:** ~120–160
- **Files:** 4 (2 Go + 2 Svelte)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/model/trip.go` | Modify | Sync-Hilfsfunktionen + Default-Thresholds |
| `internal/handler/weather_config.go` | Modify | Sync-Aufruf nach DisplayConfig-Update |
| `AlertsTab.svelte` | Modify | Add-Button entfernen, Info-Text anpassen |
| `AlertCard.svelte` | Modify | Kanal-Chips read-only (kein Override) |

## Implementation Details

### Backend: Sync-Algorithmus

```go
// alertableMetrics sind die Metriken, die eine absolute Alert-Regel erhalten können.
// Ausgeschlossen: *_change-Metriken (delta-only), thunder_level (kein sinnvoller absoluter Schwellwert).
var AlertableMetrics = map[AlertMetric]struct{}{
    AlertMetricWindGust:         {},
    AlertMetricPrecipitationSum: {},
    AlertMetricTemperatureMin:   {},
    AlertMetricTemperatureMax:   {},
    AlertMetricSnowLine:         {},
}

// DefaultAlertThreshold liefert threshold + unit + severity für eine neue Regel.
var DefaultAlertThreshold = map[AlertMetric]struct{ Threshold float64; Unit string; Severity AlertSeverity }{
    AlertMetricWindGust:         {50, "km/h", AlertSeverityWarning},
    AlertMetricPrecipitationSum: {20, "mm", AlertSeverityWarning},
    AlertMetricTemperatureMin:   {-5, "°C", AlertSeverityWarning},
    AlertMetricTemperatureMax:   {35, "°C", AlertSeverityInfo},
    AlertMetricSnowLine:         {1500, "m", AlertSeverityInfo},
}

// SyncAlertRules berechnet die neue alert_rules-Liste.
// Invariante: für jede aktive alertable Metrik existiert genau eine absolute Regel.
// Bestehende absolute Regeln aktiver Metriken werden MIT ihrem Threshold erhalten.
// Delta-Regeln (*_change, thunder_level) werden entfernt.
// Nicht mehr aktive Metriken verlieren ihre Regel.
func SyncAlertRules(existing []AlertRule, activeMetricIDs []string) []AlertRule {
    // Index bestehender absoluter Regeln pro Metrik (erster Treffer gewinnt)
    existingByMetric := map[AlertMetric]AlertRule{}
    for _, r := range existing {
        if r.Kind == AlertRuleKindAbsolute {
            if _, seen := existingByMetric[r.Metric]; !seen {
                existingByMetric[r.Metric] = r
            }
        }
    }

    result := []AlertRule{}
    for _, id := range activeMetricIDs {
        m := AlertMetric(id)
        if _, alertable := AlertableMetrics[m]; !alertable {
            continue
        }
        if existing, ok := existingByMetric[m]; ok {
            result = append(result, existing)
        } else {
            def := DefaultAlertThreshold[m]
            result = append(result, AlertRule{
                ID:        randomShortID(),
                Kind:      AlertRuleKindAbsolute,
                Metric:    m,
                Threshold: def.Threshold,
                Unit:      def.Unit,
                Severity:  def.Severity,
                Enabled:   true,
            })
        }
    }
    return result
}
```

### Backend: Hook in PutTripWeatherConfigHandler

Nach `trip.DisplayConfig = cfg` und vor `s.SaveTrip(*trip)`:

```go
// Aktive Metrik-IDs aus der neuen DisplayConfig extrahieren
activeIDs := extractActiveMetricIDs(cfg)
trip.AlertRules = model.SyncAlertRules(trip.AlertRules, activeIDs)
```

`extractActiveMetricIDs` liest `cfg["metrics"]` als `[]interface{}`, extrahiert `metric_id` wo `enabled == true`.

### Frontend: AlertsTab.svelte

- `btn-ghost-add`-Button komplett entfernen (inkl. CSS `.btn-ghost-add`)
- Info-Text anpassen: „Alert-Regeln werden automatisch aus den aktiven Wetter-Metriken abgeleitet."

### Frontend: AlertCard.svelte

- Kanal-Chips: read-only dargestellt (keine Checkbox/Toggle mehr), zeigen nur `activeChannels`
- Delta-Pfad (Kind-Auswahl, delta_window, pair_id-Logik) aus der Card-UI entfernen
- Threshold-Feld bleibt editierbar (Nutzer kann Schwellwert anpassen und speichern)

## Expected Behavior

**Input:** `PUT /api/trips/{id}/weather-config` mit einem JSON-Body, der `metrics[]` enthält — jede Metrik hat `metric_id` und `enabled` (bool).

**Output:** `trip.alert_rules` enthält nach dem Speichern genau eine absolute `AlertRule` pro aktiver, alert-fähiger Metrik (`wind_gust`, `precipitation_sum`, `temperature_min`, `temperature_max`, `snow_line`). Delta-only-Metriken (`thunder_level`, `*_change`) erhalten keine Regel. Bestehende absolute Regeln für aktive Metriken bleiben unverändert erhalten (Threshold, ID, Enabled-Zustand). Regeln für inaktiv gewordene Metriken werden entfernt.

## Acceptance Criteria

**AC-1:** Given ein Trip mit aktiven Wetter-Metriken (wind_gust, precipitation_sum aktiv), When der Wetter-Metriken-Tab gespeichert wird (PUT /api/trips/{id}/weather-config), Then enthält `trip.alert_rules` danach genau eine absolute Regel für wind_gust und eine für precipitation_sum — und keinen „Regel hinzufügen"-Button in der Alerts-Tab.

**AC-2:** Given die Alerts-Tab eines Trips, When die Regeln angezeigt werden, Then gibt es ausschließlich absolute Schwellwert-Felder — keine Delta-Auswahl, kein Zeitfenster, keinen Kind-Toggle. `thunder_level` und `*_change`-Metriken erscheinen nicht als Alert-Regel.

**AC-3:** Given ein Trip ohne Alert-Regeln, When eine Metrik (z.B. wind_gust) im Wetter-Metriken-Tab aktiviert und gespeichert wird, Then legt das Backend automatisch eine absolute AlertRule für wind_gust mit Default-Threshold (50 km/h, warning, enabled) an — ohne manuelle Aktion des Nutzers.

**AC-4:** Given ein Trip mit einer absoluten Alert-Regel für wind_gust (Threshold nutzerseitig auf 70 gesetzt), When eine andere Metrik im Wetter-Tab geändert und gespeichert wird, Then bleibt der wind_gust-Threshold weiterhin 70 (kein Überschreiben durch Default).

**AC-5:** Given eine Alert-Regel in der Alerts-Tab, When die Kanal-Anzeige betrachtet wird, Then sind die Kanäle read-only (erben aus report_config) — kein per-Alert-Kanal-Override mehr editierbar.

**AC-6:** Given zwei Nutzer A und B mit je einem Trip und unterschiedlichen aktiven Metriken, When beide gleichzeitig ihren Wetter-Metriken-Tab speichern, Then arbeitet der Alert-Sync mandantengetrennt — jeder Nutzer bekommt nur seine eigenen Regeln synchronisiert (kein Cross-User-Datenleck).

## Changelog

- 2026-06-10: Initiale Spec (Issue #701, Epic #700 Slice 1/2)
