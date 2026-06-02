# Context: Bug #505 — Gleichzeitige "Speichern" + "Bearbeiten" Buttons

## Request Summary
Auf der Trip-Detail-Seite (`/trips/[id]`) erscheinen gleichzeitig ein "Bearbeiten"-Button (im Header)
und "Speichern"-Buttons (in den Tabs). Das ist für den Nutzer widersprüchlich: Bin ich im
Bearbeitungs-Modus oder nicht?

## Problem-Analyse

### Wo die Buttons herkommen

| Button | Quelle | Zeigt immer? |
|--------|--------|-------------|
| "Bearbeiten" | `TripHeader.svelte:148` | Ja — immer sichtbar im Header |
| "Etappen speichern" | `EditStagesPanelNew.svelte:320` (via `TripTabs.svelte:117` mit `showSave={true}`) | Nur im Etappen-Tab sichtbar |
| "Speichern" (Wetter) | `WeatherMetricsTab.svelte:305` | Nur im Wetter-Tab sichtbar |

### Was "Bearbeiten" tut
Navigiert zu `/trips/${trip.id}/edit` — eine separate Edit-Seite (`TripEditView.svelte`).

### Was die Edit-Seite ZUSÄTZLICH bietet (nicht in den Tabs der Detail-Seite)
- **Route-Tab**: Trip-Name bearbeiten + Route/GPX-Verwaltung (`EditRouteSection.svelte`)
- Wetter: `WeatherSummaryCard` (andere Komponente als `WeatherMetricsTab`)

### Was BEREITS auf der Detail-Seite editierbar ist
- Etappen & Wegpunkte (Tab 2) — direkt mit "Etappen speichern" Button
- Wetter-Metriken (Tab 3) — direkt mit "Speichern" Button
- Briefing-Zeitplan (Tab 4) — BriefingsTab
- Alerts (Tab 5) — AlertsTab

## Widerspruch im UX
- "Bearbeiten" im Header → signalisiert: *Ich bin im View-Modus*
- "Etappen speichern" / "Speichern" in Tabs → signalisiert: *Ich bin bereits im Edit-Modus*

## Related Files
| File | Relevanz |
|------|---------|
| `frontend/src/lib/components/trip-detail/TripHeader.svelte:136-162` | "Bearbeiten"-Button (Zeile 145-152) |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte:117` | `EditStagesPanelNew` mit `showSave={true}` |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte:317-325` | "Etappen speichern" save-bar |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte:305` | "Speichern" Button |
| `frontend/src/routes/trips/[id]/+page.svelte:111` | Einbindung TripHeader + TripTabs |
| `frontend/src/routes/trips/[id]/edit/+page.svelte` | Separate Edit-Seite (delegiert an TripEditView) |
| `frontend/src/lib/components/edit/TripEditView.svelte` | Vollständige Edit-Maske (Route+Etappen+Wetter+Reports+Alarmregeln) |

## Lösungsoptionen

### Option A: "Bearbeiten" aus Header entfernen (empfohlen)
- Detail-Seite ist bereits die primäre Edit-Oberfläche
- Für Name/Route: z.B. Edit-Icon neben H1, oder Route-Tab zur Detail-Seite hinzufügen
- Vorteil: Kein Widerspruch mehr, kein Page-Wechsel nötig
- Risiko: Name/Route-Editing muss neu platziert werden

### Option B: Detail-Seite read-only machen
- "Speichern" aus allen Detail-Tabs entfernen, alles nur über "Bearbeiten" erreichbar
- Vorteil: Klare Trennung View vs. Edit
- Nachteil: Mehr Klicks für Nutzer, inline-Editing geht verloren

### Option C: "Bearbeiten" umbenennen
- Z.B. "Route & Name" statt "Bearbeiten"
- Minimal-Eingriff, zeigt Nutzern was der Button wirklich tut
- Nachteil: Löst den Widerspruch nicht wirklich

## Risks & Considerations
- Die separate Edit-Seite (`/trips/[id]/edit`) enthält Route/Name-Bearbeitung — bei Option A muss dieser Use-Case erhalten bleiben
- `showSave={false}` wird in `TripEditView.svelte:166` korrekt gesetzt — nur in den Detail-Tabs ist es `true`
- Tests für TripHeader: `TripHeader.spacing.test.ts`, `TripHeader.mobile-metrics.test.ts`
