# Context: bug-774-metriken-checkbox

## Request Summary
Issue #774 (critical bug): Im „Metriken"-Reiter eines Trips wird (1) ein
Einklapp-Element gewünscht entfernt und (2) die Checkbox „Metriken-Überblick"
nicht gespeichert (auswählen → speichern → neu laden → wieder leer).

## Root Cause
Die „E-Mail-Inhalt"-Karte (Format-Schalter + 3 Inhalts-Bausteine `show_metrics_summary`,
`show_outlook`, `show_stage_stats`) wird **nur** in `WeatherMetricsTab.svelte` gerendert
(`showMailContent={true}`). Deren `handleSave()` PUTtet jedoch ausschließlich
`display_config` an `/api/trips/{id}/weather-config`. Das per `bind:reportConfig`
lokal mutierte `report_config` (inkl. `show_metrics_summary`) wird **nie** ans Backend
gesendet → beim Reload verloren. Im `BriefingScheduleTab` (showMailContent=false) wird
`report_config` korrekt via `PUT /api/trips/{id}` gespeichert, aber dort ist die Karte
ausgeblendet — die Editierstelle und der Save-Pfad sind also entkoppelt.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Rendert E-Mail-Inhalt-Karte (Z.530), `handleSave` (Z.332-371) sendet kein report_config |
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` | Karte selbst; Einklapp-Toggle `report-content-modules-toggle` + `contentModulesExpanded` (Z.462-501) |
| `frontend/src/lib/components/trip-detail/BriefingScheduleTab.svelte` | Referenz: speichert report_config korrekt via PUT /api/trips/{id} (Z.48) |
| `frontend/src/lib/components/edit/reportConfigWrite.ts` | `countActiveContentModules`, `CONTENT_MODULE_DESCRIPTIONS` |
| `internal/handler/trip.go` | PUT-Handler merged report_config (Z.202-203, Replace der Map) |

## Existing Patterns
- Read-Modify-Write über `originalReportConfig`-Spread (Bestandsdaten-Schutz)
- Generische `report_config` als `map[string]interface{}` im Go-Modell → keine Feld-Whitelist
- Auto-Save-Muster für Kanäle in BriefingScheduleTab (`handleChannelChange`)

## Dependencies
- Upstream: `api.put`, Go-Trip-PUT-Handler (Merge)
- Downstream: E-Mail-Renderer konsumieren `show_metrics_summary` (#664)

## Risks & Considerations
- Zwei PUT-Endpunkte (`/weather-config` für Metriken, `/api/trips/{id}` für report_config).
  Fix muss beide konsistent halten ohne display_config zu überschreiben (Merge).
- `issue_693_email_config_cleanup.test.ts:185` prüft nur, dass `contentModulesExpanded`
  nicht persistiert wird — Entfernen des Toggles bricht das nicht.
- Mandantentrennung: Save läuft über bestehende user-getrennte Endpunkte — kein neuer Pfad.
