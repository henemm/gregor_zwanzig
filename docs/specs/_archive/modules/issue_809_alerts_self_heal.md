---
entity_id: issue_809_alerts_self_heal
type: module
created: 2026-06-14
updated: 2026-06-14
status: draft
version: "1.0"
tags: [go, alerts, store, self-heal, frontend, bug]
---

<!-- Issue #809 — Alerts-Tab Sackgasse: Self-Heal beim Laden + zentraler Sync + Frontend-Leerzustand -->

# Issue 809 — Alerts-Tab Self-Heal (Sackgasse beheben)

## Approval

- [ ] Approved

## Purpose

Der Alerts-Tab zeigt bei fast allen Bestandstrips keine Alert-Karten, weil `alert_rules` nur beim Speichern der Wetter-Metriken synchronisiert werden (`PutTripWeatherConfigHandler`), nicht beim Laden. Trips, deren Metriken seit Issue #701 nicht erneut gespeichert wurden, haben dauerhaft leere `alert_rules` — der Nutzer sieht die tote Meldung „Aktiviere mindestens eine Alert-Regel" ohne Möglichkeit, Regeln anzulegen (Add-Button wurde in #700 bewusst entfernt). Dieses Modul behebt die Sackgasse durch drei koordinierte Maßnahmen: In-Memory-Self-Heal beim Laden (kein Write-Back), zentralen Sync beim Speichern via `store.SaveTrip` und einen ehrlichen Frontend-Leerzustand für Trips ohne alert-fähige Metriken.

## Source

- **File:** `internal/store/store.go` — `LoadTrip` (Self-Heal) + `SaveTrip` (zentraler Sync)
- **File:** `internal/model/trip.go` — neue exportierte Funktion `ActiveAlertableMetricIDs(displayConfig map[string]interface{}) []string`
- **File:** `internal/handler/weather_config.go` — `extractActiveMetricIDs` wird nach der Zentralisierung redundant (darf vereinfacht werden, kein Verhaltensbruch)
- **File:** `frontend/src/lib/components/alerts-tab/AlertPreviewCard.svelte` — ehrlicher Leerzustand mit Verweis auf Wetter-Metriken-Tab

## Estimated Scope

- **LoC:** ~60–80 (Go) + ~15 (Svelte)
- **Files:** 4
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `model.SyncAlertRules(existing []AlertRule, activeIDs []string) []AlertRule` | intern (model/trip.go:135) | Kernfunktion, die Regeln synchronisiert und bestehende Schwellwerte per Merge erhält — wird von `LoadTrip` und `SaveTrip` gerufen |
| `model.AlertableMetrics` | intern (model/trip.go:110) | Definiert die fünf alert-fähigen Metriken (wind_gust, precipitation_sum, temperature_min, temperature_max, snow_line); schließt *_change und thunder_level aus |
| `model.DefaultAlertThreshold` | intern (model/trip.go:119) | Standardwerte für neu angelegte Regeln (Threshold, Unit, Severity) |
| `store.LoadTrip` | intern (store/store.go:130ff) | Leseendpunkt, der um In-Memory-Self-Heal erweitert wird |
| `store.SaveTrip` | intern (store/store.go:159ff) | Schreibendpunkt, der analog zu Issue #802 (`ComputeStageArrivals`) zentralen Sync erhält |
| `middleware.UserIDFromContext` | intern | Mandantentrennung — `user_id` aus Auth-Kontext, niemals `default`-Fallback |
| `extractActiveMetricIDs` (handler-Package) | intern (handler/weather_config.go:137) | Liest `cfg["metrics"]` und gibt IDs aktiver Metriken zurück — Logik wandert als `model.ActiveAlertableMetricIDs` ins model-Package |
| `AlertPreviewCard.svelte` | frontend (alerts-tab/) | Zeigt derzeit toten Leerzustand; wird um Unterscheidung erweitert: 0 Regeln nach Self-Heal = keine alert-fähigen Metriken → Hinweistext mit Tab-Verweis |

## Implementation Details

### Schritt 1 — `model.ActiveAlertableMetricIDs` (neues Export im model-Package)

Die bisherige private Funktion `extractActiveMetricIDs` im handler-Package liest `cfg["metrics"]` und gibt aktivierte Metric-IDs zurück. Damit `store.SaveTrip` und `store.LoadTrip` dieselbe Logik nutzen können, ohne einen Import-Zyklus (`store` → `handler`) einzuführen, wird eine äquivalente Funktion ins model-Package aufgenommen:

```go
// ActiveAlertableMetricIDs liest display_config["metrics"] und gibt die IDs
// aller enabled=true Metriken zurück, die in AlertableMetrics enthalten sind.
// Damit kann store.SaveTrip/LoadTrip SyncAlertRules zentral aufrufen,
// ohne das handler-Package importieren zu müssen.
func ActiveAlertableMetricIDs(displayConfig map[string]interface{}) []string {
    raw, ok := displayConfig["metrics"]
    if !ok {
        return nil
    }
    metrics, ok := raw.([]interface{})
    if !ok {
        return nil
    }
    var ids []string
    for _, m := range metrics {
        mm, ok := m.(map[string]interface{})
        if !ok {
            continue
        }
        enabled, _ := mm["enabled"].(bool)
        if !enabled {
            continue
        }
        id, _ := mm["metric_id"].(string)
        if id == "" {
            continue
        }
        if _, alertable := AlertableMetrics[AlertMetric(id)]; alertable {
            ids = append(ids, id)
        }
    }
    return ids
}
```

Diese Funktion filtert bereits auf `AlertableMetrics` — der Aufrufer übergibt sie direkt an `SyncAlertRules`.

### Schritt 2 — Self-Heal in `store.LoadTrip`

Direkt nach der bestehenden nil-Coercion (`if trip.AlertRules == nil → []`, Issue #205) wird Self-Heal eingebaut:

```go
// Issue #809: Self-Heal — alert_rules mit aktiven Metriken synchronisieren.
// In-Memory only, kein Write-Back (analog nil-Coercion Issue #205).
// Bewirkt: GET /api/trips/{id} liefert immer konsistente Regeln,
// auch wenn trip.json vor #701 zuletzt geschrieben wurde.
activeIDs := model.ActiveAlertableMetricIDs(trip.DisplayConfig)
trip.AlertRules = model.SyncAlertRules(trip.AlertRules, activeIDs)
```

Kein `s.SaveTrip`-Aufruf innerhalb von `LoadTrip` — das würde einen Write-Seiteneffekt beim Lesen erzeugen und ist verboten (Muster: Issue #802 Self-Heal im Scheduler).

### Schritt 3 — Zentraler Sync in `store.SaveTrip`

Analog zu `model.ComputeStageArrivals` (Issue #802, store.go:173ff) wird der Sync zentral in `SaveTrip` platziert — NACH der nil-Coercion, VOR `json.MarshalIndent`:

```go
// Issue #809: Compute-on-Save — alert_rules zentral synchronisieren,
// analog zu ComputeStageArrivals (Issue #802).
activeIDs := model.ActiveAlertableMetricIDs(trip.DisplayConfig)
trip.AlertRules = model.SyncAlertRules(trip.AlertRules, activeIDs)
```

Der vorhandene Aufruf in `PutTripWeatherConfigHandler` (weather_config.go:63-64) wird dadurch redundant. Er darf stehen bleiben (doppelter Sync ist idempotent) oder vereinfacht werden — in beiden Fällen kein Verhaltensbruch.

### Schritt 4 — Frontend: ehrlicher Leerzustand in `AlertPreviewCard.svelte`

Der aktuelle Leerzustand (`enabledRules.length === 0`) unterscheidet nicht zwischen:
- A) Trip hat aktive Metriken, aber alle Regeln sind deaktiviert (Nutzer-Entscheidung)
- B) Trip hat gar keine alert-fähigen Metriken (leere `alert_rules` nach Self-Heal)

Fall B braucht einen anderen Text: nicht die tote „Vorschau laden"-Box, sondern einen Hinweis mit Verweis auf den Tab „Wetter-Metriken". Die Komponente erhält einen neuen abgeleiteten Wert:

```svelte
// Prop: alertRules kommt bereits nach Self-Heal vom API-Response (trip.alert_rules)
// Ein trip mit alert-fähigen Metriken hat nach Self-Heal ≥1 Regel.
// Hat er 0 Regeln, fehlen alert-fähige Metriken im display_config.
const hasNoAlertableMetrics = $derived(alertRules.length === 0);
```

Template-Änderung:
```svelte
{#if hasNoAlertableMetrics}
    <p class="empty" data-testid="alert-preview-no-metrics">
        Keine alert-fähigen Wetter-Metriken aktiv. Aktiviere zuerst
        Wetter-Metriken (z.B. Windböen, Temperatur) im Tab
        <strong>Wetter-Metriken</strong>.
    </p>
{:else if enabledRules.length === 0}
    <p class="empty" data-testid="alert-preview-empty">
        Aktiviere mindestens eine Alert-Regel, um die Vorschau zu laden.
    </p>
    <button ... disabled>Vorschau laden</button>
{:else}
    <!-- vorhandener Vorschau-Button -->
{/if}
```

### Datenerhalt-Invariante (CLAUDE.md „Daten-Schema-Reworks")

`model.SyncAlertRules` erhält bereits bestehende absolute Regeln per Merge (model/trip.go:152: `existingByMetric[m]` überschreibt Default-Werte). Neue Felder wie `display_config`, `report_config`, `stages`, `activity` etc. werden durch den Self-Heal nicht berührt — es werden ausschließlich `trip.AlertRules` überschrieben. Der Roundtrip-Test (AC-2) muss dies explizit nachweisen.

### Abgrenzung Python-Seiteneffekte

Python-Alert-Versand (`src/services/trip_alert.py:182-192`) hat einen eigenen Fallback: Priorität `alert_rules` → `display_config` → defaults. Kein Python-Spiegel nötig. Der Self-Heal-Fix wirkt ausschließlich auf dem Go-Lesepfad.

## Expected Behavior

- **Input:** `GET /api/trips/{id}` für einen Bestandstrip, dessen `alert_rules` leer sind, der aber aktive alert-fähige Metriken in `display_config.metrics` hat
- **Output:** Response enthält `alert_rules` mit einer Regel pro aktiver alert-fähiger Metrik (Schwellwerte aus `DefaultAlertThreshold`); der AlertsTab zeigt die Karten
- **Side effects:** Kein Write-Back beim Laden (nur In-Memory). Beim nächsten `SaveTrip` (beliebiger Grund) werden die synchronisierten Regeln persistiert.

## Acceptance Criteria

**AC-1:** Given ein Bestandstrip mit aktiven alert-fähigen Wetter-Metriken (z.B. wind_gust enabled=true) und leeren `alert_rules` in der gespeicherten JSON / When der Nutzer den Alerts-Tab öffnet (GET `/api/trips/{id}`) / Then zeigt der AlertsTab mindestens eine AlertCard für die aktive Metrik — die Sackgasse „Aktiviere mindestens eine Alert-Regel" tritt nicht mehr auf

- Test: Echter GET-Request gegen Staging mit einem Trip, der `alert_rules=[]` aber `metrics[wind_gust].enabled=true` hat; Response-Body enthält `alert_rules` mit `metric=wind_gust`; Playwright-Check: `[data-testid="alert-cards-list"]` enthält ≥1 Kind-Element

**AC-2:** Given ein Trip mit einer manuell angepassten Alert-Regel (z.B. wind_gust Schwellwert 80 km/h statt Default 50) / When die Metriken erneut gespeichert oder der Trip geladen wird (Self-Heal) / Then bleibt der angepasste Schwellwert 80 km/h erhalten — er wird nicht durch den Default 50 km/h überschrieben

- Test: Echter Roundtrip via Go-Test: Trip mit gesetztem Schwellwert speichern → `SyncAlertRules` aufrufen → Ergebnis laden → `assert rule.Threshold == 80.0`; kein Mock

**AC-3:** Given ein beliebiger Trip / When `store.SaveTrip` aufgerufen wird (egal durch welchen Handler) / Then sind nach dem Speichern die `alert_rules` in der JSON-Datei mit den aktiven alert-fähigen Metriken aus `display_config` synchron — ohne separaten Aufruf von `SyncAlertRules` im Handler

- Test: Go-Integrationstest mit `t.TempDir`-Store: Trip mit `display_config` (wind_gust enabled) speichern, rohes JSON lesen, `alert_rules` auf Vorhandensein von wind_gust prüfen; kein Mock

**AC-4:** Given zwei verschiedene Nutzer (user_a, user_b), jeder mit eigenem Trip mit unterschiedlichen aktiven Metriken / When beide Trips geladen werden / Then enthält jeder Trip nur die Regeln seiner eigenen aktiven Metriken — keine Cross-User-Datenvermischung

- Test: Go-Integrationstest mit zwei `Store`-Instanzen (WithUser je user_a/user_b), getrennte `t.TempDir`-Daten; Trip-A hat wind_gust, Trip-B hat temperature_max; nach LoadTrip: Trip-A hat keine temperature_max-Regel, Trip-B hat keine wind_gust-Regel

**AC-5:** Given ein Trip ohne jegliche aktive alert-fähige Wetter-Metriken (alle deaktiviert oder keine alertable Metrik ausgewählt) / When der Nutzer den Alerts-Tab öffnet / Then zeigt `AlertPreviewCard` den Hinweis „Keine alert-fähigen Wetter-Metriken aktiv. Aktiviere zuerst Wetter-Metriken … im Tab Wetter-Metriken." mit `data-testid="alert-preview-no-metrics"` — statt der toten „Vorschau laden"-Box

- Test: Playwright gegen Staging: Trip ohne alert-fähige Metriken öffnen → Alerts-Tab → `[data-testid="alert-preview-no-metrics"]` ist sichtbar; `[data-testid="alert-preview-load-btn"]` existiert NICHT im DOM

**AC-6:** Given ein Trip mit gesetzten Feldern `display_config`, `report_config`, `stages`, `activity`, `alert_cooldown_minutes` / When `store.LoadTrip` den Self-Heal durchführt / Then sind alle genannten Felder nach dem Load byte-identisch mit den gespeicherten Werten — kein Datenverlust durch den Self-Heal

- Test: Go-Roundtrip-Test: Trip mit vollständigen Feldern speichern → laden → Felder mit `reflect.DeepEqual` oder JSON-Vergleich prüfen; nur `alert_rules` darf sich ändern (von leer auf synchronisiert)

## Known Limitations

- Der Self-Heal-Fix persistiert die synchronisierten Regeln erst beim nächsten `SaveTrip`. Ein Nutzer, der den Trip nur ansieht und nie speichert, erhält zwar korrekte Karten, aber das JSON bleibt auf dem alten Stand. Dies ist akzeptiert — ein Massen-Backfill ist explizit ausgeschlossen (Lehre aus Issue #802).
- Trips, die ausschließlich nicht-alertable Metriken aktiviert haben (z.B. nur `confidence`, `temperature_apparent` — keine der fünf in `AlertableMetrics`), zeigen nach Fix dauerhaft den Leerzustand mit Wetter-Metriken-Hinweis. Das ist korrekt, da für diese Metriken per Design keine Alert-Regeln existieren.
- `extractActiveMetricIDs` im handler-Package bleibt als private Funktion erhalten (oder kann intern auf `model.ActiveAlertableMetricIDs` delegieren). Kein Breaking Change an der Handler-API.

## Changelog

- 2026-06-14: Initial spec erstellt — Issue #809, Root Cause bewiesen (Debug702 vs. ortler-2025)
