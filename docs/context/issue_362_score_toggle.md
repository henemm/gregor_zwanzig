# Context: Issue #362 — ScoreToggle: Score-Zugehörigkeit pro Metrik im Orts-Vergleich

## Request Summary

Im Wetter-Metriken-Editor für **Orte** (`/locations`) und **Abonnements** (`/subscriptions`) soll jede Metrik einen `ScoreToggle` bekommen: „Im Score" / „Nicht im Score". Metriken, die „im Score" sind, fließen in den 0–100-Wert des Compare-Screens ein; andere erscheinen nur als Detail-Daten.

## Abhängigkeiten-Status

- **#345 (Wetter-Editor-Konsolidierung):** CLOSED. EditWeatherSection entfernt, `WeatherConfigDialog.svelte` ist jetzt der Editor für Ort + Abo.
- **#250 (Compare-Engine):** LIVE. `POST /api/compare/run` mit `ActivityProfile`-basiertem Scoring.
- **#364 (Bucket-Editor):** Teil von WeatherMetricsTab (Trip-Kontext) — hat `BucketWeatherConfigMetric` mit `bucket`/`order`.

## Relevante Dateien

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/WeatherConfigDialog.svelte` | Aktueller Editor für Ort/Abo — hier kommt ScoreToggle rein |
| `frontend/src/lib/types.ts:127` | `WeatherConfigMetric` — bekommt additiv `score_member?: boolean` |
| `frontend/src/lib/components/trip-detail/metricsEditor.ts:191` | `BucketWeatherConfigMetric` — Referenzmuster für additive Felder |
| `internal/model/metric_preset.go` | `DisplayMetric` Go-Struct — Referenz für Horizons-Muster |
| `internal/model/location.go` | `DisplayConfig map[string]interface{}` — JSON-passthrough, kein Go-Change nötig |
| `internal/model/subscription.go` | `DisplayConfig map[string]interface{}` — ditto |
| `internal/compare/scoring.go` | `ScoreRow()` + `profileMetrics()` — Scoring-Kern, muss `score_member` respektieren |
| `internal/compare/types.go` | `CompareRequest` — muss ggf. `LocationDisplayConfigs` tragen |
| `internal/compare/engine.go` | `Engine.Run()` — orchestriert fetch + score |
| `internal/handler/compare_run.go` | HTTP-Handler für Compare — Store-Zugriff nötig |
| `docs/design-requests/issue_345_assets/molecules.jsx:566` | `ScoreToggle`-Referenz-Implementierung (React/JSX) |
| `docs/design-requests/issue_345_assets/screen-weather-consolidation.jsx:598` | `MetricEditorRow` context="ort" — Design-Quelle |
| `frontend/src/routes/locations/+page.svelte:194` | Nutzt WeatherConfigDialog — Kontext: Ort |
| `frontend/src/routes/subscriptions/+page.svelte:262` | Nutzt WeatherConfigDialog — Kontext: Abo |

## Existierende Muster

### 1. Additives Feld-Muster (Referenz: BucketWeatherConfigMetric)
`metricsEditor.ts:191` zeigt, wie neue Felder (`bucket`, `order`) additiv zu `WeatherConfigMetric` hinzugefügt werden. `DisplayConfig` in Go ist `map[string]interface{}` — `score_member` reist ohne Go-Struct-Change durch.

### 2. ScoreToggle-Referenz (Design)
`molecules.jsx:566`: Ein Pill-Button „Im Score" / „Nicht im Score" mit Accent-Farbe bei aktiv. Erscheint in `MetricEditorRow` wo im Tour-Kontext `HorizonChips` stehen.

### 3. Compare-Scoring-Kern
`scoring.go:42` `profileMetrics()` liefert hard-coded `metricSpec[]` pro `ActivityProfile`. `ScoreRow()` iteriert sie und normalisiert 0–100. Die Engine lädt **keine** `DisplayConfig` der Locations — sie kennt nur die `LocationIDs` aus dem Request.

## Zentrale offene Design-Frage

**Wie verhält sich `score_member` gegenüber dem ActivityProfile-Gewicht?**

Das ActivityProfile (z.B. `SUMMER_TREKKING`) gewichtet Niederschlag mit 30 %. Wenn der User Niederschlag als „Nicht im Score" markiert, passiert aktuell nichts — die Engine kennt seine Konfiguration nicht.

**Zwei Optionen:**

| Option | Beschreibung | Aufwand | Tradeoff |
|--------|-------------|---------|----------|
| **A — Filter-Ansatz** | `score_member=false` entfernt die Metrik aus `profileMetrics()`, restliche Gewichte werden re-normalisiert (Summe bleibt 1.0). Engine lädt `DisplayConfig` der ersten Location als Referenz (oder aus Request). | Mittel | Einfach zu erklären: „was du deaktivierst, zählt nicht" |
| **B — Eigene Gewichte** | `score_member=true` Metriken ersetzen das ActivityProfile komplett. Gewichte gleichverteilt oder nutzerdefiniert. | Hoch | Flexibel, aber komplexer; ActivityProfile wird obsolet |

**Empfehlung:** Option A (Filter-Ansatz). Weniger Eingriff, ActivityProfile bleibt primäre Quelle, `score_member` filtert nur heraus. Kompatibel mit bestehendem Datenmodell.

## Score-Mitglied im Compare-Request

Die Engine muss die `DisplayConfig` kennen. Zwei Wege:
1. **Engine lädt selbst** aus dem Store (nach `LocationID`) — Problem: verschiedene Locations können unterschiedliche `score_member`-Konfigurationen haben.
2. **Frontend sendet mit** (neues Feld `display_configs` im `CompareRequest`) — klarer, aber Breaking Change.

**Empfehlung:** Engine lädt die DisplayConfig der ersten Location als Filter-Basis (Intersection aller enabled score_members als Tie-Breaker). Einfachste Implementierung ohne API-Änderung.

## Migration / Default

Existing Locations/Subscriptions ohne `score_member`-Feld: Default = **alle Metriken im Score** (alle als `true` behandelt). Entspricht dem aktuellen Verhalten. Kein Migration-Script nötig (additive JSON-Felder).

## Risiken

- **Datenverlust-Risiko:** LOW — `DisplayConfig` ist `map[string]interface{}` (JSON-passthrough). Kein Go-Struct-Change. Read-Modify-Write-Muster bereits vorhanden in `weather_config.go`.
- **Compare-Engine-Instabilität:** MEDIUM — `ScoreRow()` wird verändert. Bestehende Scores ändern sich, wenn `score_member=false` gesetzt ist. 
- **Test-Coverage:** Die Compare-Engine hat Unit-Tests (scoring_test.go?) — prüfen ob vorhanden.
