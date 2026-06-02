---
entity_id: bug_505_speichern_bearbeiten
type: bugfix
created: 2026-06-02
updated: 2026-06-02
status: draft
version: "1.0"
tags: [frontend, trip-detail, header, edit-mode, svelte]
---

# Bug #505 — "Bearbeiten"- und "Briefing-Vorschau"-Button aus Trip-Header entfernen

## Approval

- [x] Approved

## Purpose

Der Trip-Detail-Header (`TripHeader.svelte`) zeigt derzeit zwei Buttons ("Bearbeiten" und "Briefing-Vorschau"), die laut Design-Vorgabe nicht in den Header gehören — Bearbeitung geschieht bereits inline in den vier Tabs der Seite, und die separate Edit-Seite leitet seit dem Umbau per `redirect(301)` ohnehin weiter. Diese Spec definiert die Entfernung beider Buttons samt ihrer Handler sowie Regressions-Tests, die sicherstellen, dass der Edit-Modus korrekt über die Tab-eigenen "Speichern"-Buttons abgebildet ist.

## Source

- **File:** `frontend/src/lib/components/trip-detail/TripHeader.svelte`
- **Identifier:** `TripHeader` (Svelte-Komponente, Zeile 137 + 148)

Zweite betroffene Datei (neue Tests):
- **File:** `frontend/src/lib/components/trip-detail/bug_505_edit_mode.test.ts`

## Estimated Scope

- **LoC:** ~60 (30 Entfernung in TripHeader, 30 neue Tests)
- **Files:** 2
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `TripHeader.svelte` | Frontend-Komponente | Enthält die zu entfernenden Buttons + Handler |
| `TripTabs.svelte` | Frontend-Komponente | Beherbergt die vier Edit-Tabs — wird in Tests als Kontext referenziert |
| `EditStagesPanelNew.svelte` | Frontend-Komponente | Etappen-Tab mit eigenem Speichern-Button (`showSave={true}`) |
| `WeatherMetricsTab.svelte` | Frontend-Komponente | Wetter-Tab mit `data-testid="weather-metrics-tab-save"` |
| `BriefingsTab.svelte` | Frontend-Komponente | Briefings-Tab mit `data-testid="briefings-tab-save"` |
| `AlertsTab.svelte` | Frontend-Komponente | Alerts-Tab mit `data-testid="alerts-tab-save"` |
| `/trips/[id]/edit/+page.server.ts` | SvelteKit Route | Macht bereits `redirect(301, ?tab=stages)` — separate Edit-Seite ist de facto abgebaut |

## Implementation Details

```
1. TripHeader.svelte — Buttons entfernen
   - Button mit data-testid="trip-detail-action-edit" (Z. 148) löschen
   - Button mit data-testid="trip-detail-action-preview" (Z. 137) löschen
   - Funktion handleEdit() löschen (navigiert zu /trips/${trip.id}/edit)
   - Funktion handlePreview() löschen (navigiert zu #preview)
   - Zugehörige Importe prüfen: falls goto/page nur durch diese Handler genutzt,
     ebenfalls entfernen (kein toter Import-Code zurücklassen)

2. Neue Testdatei: bug_505_edit_mode.test.ts
   - Prüft per DOM-Assertions (node:test + jsdom o.ä.),
     dass kein Element mit data-testid="trip-detail-action-edit" im gerenderten
     TripHeader existiert
   - Prüft, dass kein Element mit data-testid="trip-detail-action-preview"
     im gerenderten TripHeader existiert
   - Prüft für jeden der vier Tabs, dass der jeweilige tab-eigene Speichern-Button
     (data-testid-Werte: weather-metrics-tab-save, briefings-tab-save, alerts-tab-save)
     und EditStagesPanelNew mit showSave={true} vorhanden sind
   - KEINE Mocks — Tests laufen gegen echte Komponenten-Instanzen
```

## Expected Behavior

- **Input:** Trip-Detail-Seite `/trips/[id]` wird gerendert
- **Output:** Header zeigt ausschließlich "Pausieren", "Archivieren", "Test-Briefing senden" — kein "Bearbeiten"-, kein "Briefing-Vorschau"-Button
- **Side effects:** Navigations-Pfad `/trips/[id]/edit` bleibt per `redirect(301)` erreichbar, wird aber nicht mehr vom Header verlinkt; alle vier Tab-Panels behalten ihre eigenen Speichern-Buttons unverändert

## Acceptance Criteria

- **AC-1:** Given die Trip-Detail-Seite ist gerendert / When der Header auf alle Buttons untersucht wird / Then existiert kein Element mit `data-testid="trip-detail-action-edit"` im DOM.
  - Test: (populated after /tdd-red)

- **AC-2:** Given die Trip-Detail-Seite ist gerendert / When der Header auf alle Buttons untersucht wird / Then existiert kein Element mit `data-testid="trip-detail-action-preview"` im DOM.
  - Test: (populated after /tdd-red)

- **AC-3:** Given `TripHeader.svelte` nach der Änderung / When der Quellcode auf Handler-Funktionen geprüft wird / Then sind weder `handleEdit` noch `handlePreview` als Funktionen oder Event-Listener definiert.
  - Test: (populated after /tdd-red)

- **AC-4:** Given der Etappen-Tab der Trip-Detail-Seite ist aktiv / When `EditStagesPanelNew` eingebunden wird / Then wird die Komponente mit `showSave={true}` gerendert und enthält einen `api.put`-Aufruf für den Save-Call.
  - Test: (populated after /tdd-red)

- **AC-5:** Given der Wetter-Tab der Trip-Detail-Seite ist aktiv / When `WeatherMetricsTab` gerendert wird / Then existiert ein Button mit `data-testid="weather-metrics-tab-save"` im DOM.
  - Test: (populated after /tdd-red)

- **AC-6:** Given der Briefings-Tab der Trip-Detail-Seite ist aktiv / When `BriefingsTab` gerendert wird / Then existiert ein Button mit `data-testid="briefings-tab-save"` im DOM.
  - Test: (populated after /tdd-red)

- **AC-7:** Given der Alerts-Tab der Trip-Detail-Seite ist aktiv / When `AlertsTab` gerendert wird / Then existiert ein Button mit `data-testid="alerts-tab-save"` im DOM.
  - Test: (populated after /tdd-red)

## Known Limitations

- Die Testdatei prüft DOM-Struktur; tatsächliche API-Kommunikation (PUT-Call) wird strukturell per Code-Analyse (AC-4) abgedeckt, nicht per Netzwerk-Roundtrip.
- Die separate Route `/trips/[id]/edit` bleibt bestehen (Redirect), wird aber in dieser Spec nicht bereinigt — das ist ein eigenes Aufräum-Issue.

## Changelog

- 2026-06-02: Initial spec created for bug #505 — Entfernung veralteter Header-Buttons + Regressions-Tests für Tab-Edit-Modus
