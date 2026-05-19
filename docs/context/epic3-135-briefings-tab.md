# Context: Epic #135 — Briefing-Zeitplan-Tab (letzter offener Punkt)

## Request Summary

Epic #135 (Trip-Übersicht Haupt-Bühne) hat 5 von 6 Tabs vollständig implementiert. Der
**Briefing-Zeitplan-Tab** zeigt noch einen Platzhalter-Text. Das ist der einzige fehlende
Baustein zum Abschluss des Epics.

## Lücke: `briefings`-Tab in TripTabs.svelte

**Datei:** `frontend/src/lib/components/trip-detail/TripTabs.svelte`

| Tab | Status |
|-----|--------|
| Übersicht | ✅ `TripOverview.svelte` |
| Etappen & Wegpunkte | ✅ `WaypointsPanel.svelte` |
| Wetter-Metriken | ✅ `WeatherMetricsTab.svelte` |
| **Briefing-Zeitplan** | ❌ Platzhalter (Z. 44: "Inhalt folgt mit Issue #159") |
| Alerts | ✅ `AlertsTab.svelte` |
| Vorschau | ✅ `EmailIframe` + `SmsPhoneFrame` |

## Was gebaut werden muss

**Neue Datei:** `frontend/src/lib/components/briefings-tab/BriefingsTab.svelte`

Umschließt die bereits vollständige `EditReportConfigSection.svelte` mit:
- Lokalem State für `reportConfig` (Deep Copy von `trip.report_config`)
- Speichern via `PUT /api/trips/{id}` mit `{ report_config: reportConfig }`
- Inline-Feedback (Erfolg-Flash + Fehlertext) — identisches Muster wie `AlertsTab.svelte`

**Anpassen:** `TripTabs.svelte`
- Import `BriefingsTab` hinzufügen
- `{:else if tab.value === 'briefings' && trip}` Branch einbauen
- `briefings`-Eintrag aus `PLACEHOLDERS` entfernen

## Schlüssel-Komponenten

| Datei | Rolle |
|-------|-------|
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` | Vollständiger Editor (Morning/Evening-Time, Kanäle, Multi-Day-Trend, Erweitert) — **wiederverwenden** |
| `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` | **Referenz-Muster**: State-Init, API-Call, Inline-Feedback |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Einbindungspunkt (Z. 94–119) |
| `frontend/src/lib/types.ts` | `ReportConfig`-Interface (bereits vollständig typisiert) |
| `internal/handler/trip.go` | `PUT /api/trips/{id}` Read-Modify-Write — `report_config` bereits unterstützt |

## ReportConfig — Felder die EditReportConfigSection pflegt

```typescript
interface ReportConfig {
  enabled?, morning_enabled?, evening_enabled?,
  morning_time?, evening_time?,
  send_email?, send_signal?, send_telegram?, send_sms?,
  alert_on_changes?, show_compact_summary?, show_daylight?,
  wind_exposition_min_elevation_m?,
  multi_day_trend_morning?, multi_day_trend_evening?, multi_day_trend_reports?
}
```

**Read-Modify-Write:** `EditReportConfigSection` bewahrt bereits `originalReportConfig` intern
und merged alle unbekannten Felder (change_threshold_*) — der Tab-Container muss nur den
`reportConfig`-Prop als bindable State bereitstellen.

## Existing Patterns

- **AlertsTab.svelte:** `$state` + `api.put()` + `saving/saveSuccess/saveError` — identisch anwenden
- **API-Client:** `import { api } from '$lib/api'` → `await api.put('/api/trips/{id}', payload)`
- **Go-Handler:** `report_config` wird bereits via Read-Modify-Write persistiert (`internal/handler/trip.go`)
- **TripEditView.svelte:** Zeigt wie `EditReportConfigSection` als `bind:reportConfig={reportConfig}` eingebunden wird

## Scope

- **In Scope:** `BriefingsTab.svelte` + `TripTabs.svelte` Update + PLACEHOLDER-Cleanup
- **Out of Scope:** Änderungen an `EditReportConfigSection.svelte`, Backend-Änderungen, SMS-Tab-Content

## Risks & Considerations

- **Kein neuer Backend-Code nötig:** `PUT /api/trips/{id}` mit `report_config`-Feld bereits vollständig im Handler
- **Read-Modify-Write ist in EditReportConfigSection eingebaut:** Der `$effect` schreibt Read-Modify-Write-konforme Updates zurück — kein Datenverlust-Risiko
- **Kein Schema-Rework:** `report_config` ist bereits `map[string]interface{}` im Go-Modell
- **LoC-Schätzung:** ~60 LoC für BriefingsTab.svelte + ~5 LoC TripTabs-Änderung
