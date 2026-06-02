# Context: Bug #502 — alert-rules-editor.spec.ts AC-8 right-card-alerts-edit-link

## Request Summary

AC-8 im E2E-Test `frontend/e2e/alert-rules-editor.spec.ts` sucht nach `[data-testid="right-card-alerts-edit-link"]`, der im DOM nicht existiert. Root Cause klären und Test anpassen.

## Root Cause (bereits ermittelt)

**`AlertsPreviewCard` wurde in Issue #487 durch `DetailCard` in `TripOverview.svelte` ersetzt.**

Issue #487 hat das Trip-Detail-Overview von einem zweispaltigen Layout (rechte Spalte mit `AlertsPreviewCard`, `BriefingPreviewCard`, `WeatherMetricsPreviewCard`) auf ein kompaktes 2×2-Grid aus 4 `DetailCard`-Kacheln umgebaut.

- `AlertsPreviewCard.svelte` existiert noch in `frontend/src/lib/components/trip-detail/`, wird aber **nirgends mehr gerendert**
- Das zugehörige `data-testid="right-card-alerts-edit-link"` ist daher nicht im DOM
- Der Ersatz-Link befindet sich im `DetailCard` für Alerts in `TripOverview.svelte`

## Zweiter Befund: Inkonsistente href-Navigation in TripOverview.svelte

`TripOverview.svelte` verwendet für drei von vier Karten noch den alten `#hash`-Stil (vor Issue #516):

| Karte | actionHref aktuell | Korrekt (Issue #516) |
|-------|-------------------|----------------------|
| `card-reports` | `#briefings` | `?tab=briefings` |
| `card-alerts` | `#alerts` | `?tab=alerts` ← Betrifft AC-8 |
| `card-stages` | `?tab=stages` | `?tab=stages` ✓ |
| `card-schedule` | `#preview` | `?tab=preview` |

`TripTabs.svelte` navigiert via `goto('?tab=${value}')` (Issue #516), d.h. `#alerts` funktioniert als Anker nicht für den Tab-Switch. Nur `?tab=stages` ist bereits korrekt.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/e2e/alert-rules-editor.spec.ts` | Enthält AC-8 (Zeile 239–263) — Test muss angepasst werden |
| `frontend/src/lib/components/trip-detail/TripOverview.svelte` | Neues Overview-Grid mit DetailCard, actionHref="#alerts" muss auf `?tab=alerts` |
| `frontend/src/lib/components/trip-detail/DetailCard.svelte` | Rendert `data-testid="detail-card-action-{testid}"` → `detail-card-action-card-alerts` |
| `frontend/src/lib/components/trip-detail/AlertsPreviewCard.svelte` | Alte Komponente, nicht mehr gerendert, hat alten testid |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Tab-Navigation via `?tab=` (Issue #516), Wert `alerts` |

## Bestehende Patterns

- `DetailCard` rendert den Action-Link als `data-testid="detail-card-action-{testid}"` (Zeile 51)
- Alerts-`DetailCard` hat `testid="card-alerts"` → Action-Link: `data-testid="detail-card-action-card-alerts"`
- Tab-Navigation: `?tab=alerts` (via `TripTabs.svelte` → `goto('?tab=alerts')`)

## Konkrete Fix-Punkte

1. **`frontend/src/lib/components/trip-detail/TripOverview.svelte` Zeile 150:**
   - Vorher: `actionHref="#alerts"`
   - Nachher: `actionHref="?tab=alerts"`

2. **`frontend/e2e/alert-rules-editor.spec.ts` Zeile 257–259:**
   - Vorher: testid `right-card-alerts-edit-link`, href `/trips/${id}/edit#alerts`
   - Nachher: testid `detail-card-action-card-alerts`, href `?tab=alerts`

## Dritter Befund: TripOverview.issue487.test.ts hat passenden Unit-Test

`TripOverview.issue487.test.ts` Zeile 114–118 prüft ebenfalls `source.includes('#alerts')`. Wenn `TripOverview.svelte` auf `?tab=alerts` migriert wird, muss dieser Unit-Test mit angepasst werden.

## Scope: Out-of-Scope

- `#briefings` und `#preview` in `TripOverview.svelte` (gleiche Inkonsistenz, aber außerhalb von #502)
- `AlertsPreviewCard.svelte` bleibt unverändert (wird nicht mehr gerendert, aber auch nicht gelöscht — separates Cleanup-Issue)

## Risks & Considerations

- Keine Datenmodell-Änderungen
- Nur Test + 1 Zeile Produktionscode
- `TripOverview.svelte` hat eigene Unit-Tests in `TripOverview.issue487.test.ts` — muss geprüft werden ob dort href-Assertions vorhanden sind
