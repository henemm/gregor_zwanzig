# Issue #494 — Trip-Bearbeiten-Seite: Design-Analyse

## Ziel
Die `/trips/[id]/edit`-Seite ans Soll-Design (soll-flow2A-trip-editor-overview.png) angleichen.

## Kern-Befund

`+page.svelte:7` rendert direkt `WaypointEditorPage` (Karten-Editor). Das Soll-Design zeigt eine Tab-Übersicht als Einstieg. Der Karten-Editor ist im Soll ein "nächster Frame" (Subroute, folgt in separatem Issue).

## 7 konkrete Abweichungen
| Nr | Ist | Soll |
|----|-----|------|
| 1 | WaypointEditorPage direkt | Tab-Übersicht als Einstieg |
| 2 | Accordion-Navigation | Horizontale Tabs (Route/Etappen/Wetter/Reports/Alarmregeln) |
| 3 | Kein Breadcrumb | „MEINE TOUREN · TRIP BEARBEITEN" + große H1 |
| 4 | Buttons fixed-bottom | Buttons oben rechts im Header |
| 5 | Keine Statistik-Karte | km · Hm · Zeitraum · Tage · REPORTS-Badge |
| 6 | EtappenStrip + Karte | Etappen-Kacheln als horizontales Grid |
| 7 | Keine Tab-Badges | „Etappen 13" und „Alarmregeln 5" |

## Architektur-Entscheidung: WaypointEditor → Subroute (späteres Issue)

WaypointEditorPage.svelte bleibt unberührt. In #494 sind Etappen-Kacheln nicht klickbar (Hinweistext bleibt). Neue Route: `/trips/[id]/edit/[stageId]` folgt in Folge-Issue.

## Scope #494

| Datei | Aktion | LoC |
|-------|--------|-----|
| `edit/TripEditView.svelte` | ERSETZEN (komplett neu) | ~220 |
| `routes/.../edit/+page.svelte` | WaypointEditorPage → TripEditView | ~8 |
| `e2e/trip-edit.spec.ts` | Accordion-Testids → Tab-Testids | ~50 |
| `e2e/issue-407-waypoint-editor-screen.spec.ts` | test.skip() | ~5 |

**Gesamt: 4 Dateien, ~280 LoC**

## Verfügbare Bausteine (kein neuer Code nötig)
- `Segmented.svelte` — Tab-Control
- `computeTripStats(trip)` — kmTotal, ascentM, stages
- `formatDateRange(trip)` — Zeitraum-String
- `getReportSchedule(trip)` — Reports-Konfiguriert-Check
- `EditRouteSection`, `EditStagesPanelNew`, `WeatherSummaryCard`, `EditReportConfigSection`, `AlertRulesEditor` — alle Tab-Inhalte

## Daten für Statistik-Karte (alle vorhanden)
- Gesamtstrecke: `computeTripStats(trip).kmTotal`
- Höhenmeter: `computeTripStats(trip).ascentM`
- Zeitraum: `formatDateRange(trip)`
- Tage: `computeTripStats(trip).stages` (1 Stage = 1 Tag)
- REPORTS-Badge: `getReportSchedule(trip).enabled`

## Risiken
1. **trip-edit.spec.ts** — Accordion-Testids brechen; müssen im gleichen PR aktualisiert werden
2. **issue-407.spec.ts** — WaypointEditor nicht mehr auf /edit; test.skip() setzen
3. **Read-Modify-Write** — Save-Logik aus TripEditView.svelte 1:1 übernehmen (BUG-DATALOSS-Schutz)

## Alte Spec
`docs/specs/modules/trip_edit_view.md` (2026-05-01) — veraltet (beschreibt Accordion). Wird durch neue Spec für #494 überschrieben.
