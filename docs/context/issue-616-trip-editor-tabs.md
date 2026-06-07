# Context: #616 Trip-Editor IA — kanonisches 5-Tab-Set + direkter Bearbeiten-Modus

## Request Summary
Der Trip-Editor (`TripEditView.svelte`) wird auf das kanonische 5-Tab-Set
`Übersicht · Etappen & Wegpunkte · Wetter-Metriken · Briefing-Zeitplan · Alerts`
umgestellt, öffnet direkt im Bearbeiten-Modus (kein read-only-Zwischenschritt) und
erhält einen neuen Übersicht-Tab (Cockpit mit „Bearbeiten →"-Links pro Sektion).
Foundation-Slice 1/4 des Pakets „Trip bearbeiten" (#575), Quelle: `screen-trip-edit-v2-main.jsx`.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/edit/TripEditView.svelte` | **Kern** — Tab-Leiste + Tab-Content, hier liegt das alte 5-Tab-Set |
| `docs/design-requests/trip-anlegen-2026-06-06/screen-trip-edit-v2-main.jsx` | Verbindliche JSX-Vorlage (TE2_TabBar, TE2_UebersichtTab) |
| `frontend/src/routes/trips/[id]/edit/+page.svelte` | Edit-Route, rendert TripEditView |
| `frontend/src/routes/trips/[id]/+page.svelte` | Read-only Detail-Seite (TripTabs) — der „Zwischenschritt" |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Detail-Tabs haben über #529/#516 BEREITS das kanonische 5+1-Set (inkl. Vorschau) |
| `frontend/src/lib/components/edit/EditRouteSection.svelte` | Aktueller „Route"-Tab (Name + GPX-Upload) — entfällt, Inhalt geht auf |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | Etappen-Tab-Content |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Wetter-Metriken (geteilt Detail+Edit) |
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` | Reports → wird „Briefing-Zeitplan" |
| `frontend/src/lib/components/organisms` (AlertRulesEditor) | Alarmregeln → wird „Alerts" |
| `frontend/src/routes/trips/+page.svelte` | Trips-Liste: Row-Click → `/trips/[id]` (Detail), „Bearbeiten" → `/edit` |

## Existing Patterns
- Tab-Leiste in TripEditView ist bereits eine eigene Inline-Implementierung analog `TE2_TabBar` (data-testid `edit-tab-<id>`).
- Read-Modify-Write: `makeSaveHandler` reicht `...trip` durch, überschreibt nur UI-Felder — `display_config` bleibt unangetastet (#345).
- Factory-Pattern für Handler (Safari-Closure-Schutz, CLAUDE.md).
- Detail-Seite nutzt `?tab=`-Query (#516) für Tab-Vorauswahl.

## Dependencies
- Upstream: `Trip`-Typ, `api.put`, `computeTripStats`, `formatDateRange`, `getReportSchedule`.
- Downstream: Folge-Slices 2/4–4/4 von #575 bauen auf dieser Tab-Shell auf; Harmonisierung Detail↔Edit ist **#620** (separat).

## Existing Specs
- Kein dediziertes Spec-File für TripEditView; JSX-Vorlage ist die Design-Wahrheit.

## Risks & Considerations
- **Doppelstruktur Detail↔Edit:** `/trips/[id]` (read-only TripTabs, kanonische Tabs) vs. `/trips/[id]/edit` (TripEditView, alte Tabs). Volle Zusammenführung = #620. #616 = Editor auf kanonische Shell bringen.
- **Pre-existing file-content-Tests** (`issue_581_trip_detail_jsx.test.ts` AC-6/AC-7) prüfen TripEditView per `read_text()`-String-Match — diese verbieten u.a. EditStagesPanelNew bzw. fordern EtappenStrip. Beim Umbau auf Kollision prüfen (ggf. nachziehen). Solche Datei-Inhalt-Checks sind laut CLAUDE.md eigentlich verboten — neue Tests müssen Verhalten beweisen (Playwright/Staging).
- **Übersicht-Tab als Default:** Darf KEIN read-only-Block sein — Cockpit mit „Bearbeiten →"-Links, restliche Tabs direkt editierbar.
- **Terminologie:** Trip · Etappe · Wegpunkt durchgängig (Guard aus #394 aktiv).
- **LoC-Limit 250:** Übersicht-Tab + Tab-Restructure könnten knapp werden; ggf. Übersicht-Inhalt in Helper/Subkomponente.
- **Navigation „direkter Bearbeiten-Modus":** Row-Click in Trips-Liste geht heute auf die Detail-Seite. Ob #616 das auf `/edit` umbiegt oder das #620 überlässt = Scope-Entscheidung (PO).
