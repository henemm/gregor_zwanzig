---
entity_id: issue_616_trip_editor_tabs
type: module
created: 2026-06-06
updated: 2026-06-06
status: draft
version: "2.0"
tags: [frontend, trips, ia, rework, design-compliance]
---

# Trip-IA — EINE Trip-Seite + direkter Bearbeiten-Modus (#616)

## Approval

- [x] Approved (PO 'go' 2026-06-06 — „EINE Trip-Seite"-Zuschnitt)

## Purpose

Es gibt künftig **genau eine** Trip-Oberfläche (`/trips/[id]`, `TripTabs`) statt zweier
konkurrierender Seiten (Ansehen-Seite + separate `/edit`-Seite). Die kanonische
Tab-Leiste (`Übersicht · Etappen & Wegpunkte · Wetter-Metriken · Briefing-Zeitplan ·
Alerts · Vorschau`) wird zur einzigen Trip-Oberfläche: „Übersicht" ist das read-only
Cockpit (Rolle ANSEHEN), die übrigen Tabs sind je ein Editor (Rolle BEARBEITEN), pro
Tab gespeichert. Die alte separate `/edit`-Seite (`TripEditView.svelte`) wird stillgelegt.

Grundlage: `nav-map.jsx` (Single-Source der IA — „genau drei Oberflächen-Typen, KEIN
separater Bearbeiten-Modus-Screen"). Löst gemeinsam #503 (zwei Seiten) und #505
(Speichern-vs-Bearbeiten-Verwirrung), beide bereits teilkonsolidiert.

## Source

- **Primär:** `frontend/src/lib/components/trip-detail/TripTabs.svelte` (die EINE Oberfläche)
- **Stilllegen:** `frontend/src/routes/trips/[id]/edit/+page.svelte` (Redirect statt TripEditView)
- **Navigation umbiegen:** `frontend/src/routes/trips/+page.svelte` (Row-Click + „Bearbeiten" → `/trips/[id]`)
- **Echten Editor mitnehmen:** `frontend/src/lib/components/trip-detail/HubSchedule.svelte` (statisches Mockup) → ersetzt durch echten Briefing-Zeitplan-Editor (`EditReportConfigSection` + Pro-Tab-Save)
- **Trip-Name-Bearbeitung:** neuer Platz auf der Detail-Oberfläche (Übersicht/Header), da bisher nur auf `/edit` editierbar
- **Referenz-IA:** `claude-code-handoff/.../jsx/nav-map.jsx`

## Estimated Scope

- **LoC:** ~250–350 (Redirect + Nav + Briefing-Zeitplan-Editor mit Pro-Tab-Save + Name-Edit) — **ggf. über Default-Limit, PO-Freigabe/Split klären**
- **Files:** 4–6
- **Effort:** medium-high

## Dependencies

- Upstream: `TripTabs`, `HubOverview`, `EditReportConfigSection`, `api.put`.
- Geschwister-Slices (NICHT hier): #587 (Wetter-Metriken-Tab-Inhalt 2/4),
  #617 (Kanal-Verkettung in Briefing-Zeitplan + Alerts 3/4), #618 (Mobile 4/4).

## Acceptance Criteria

- **AC-1:** Given ein eingeloggter Nutzer auf `/trips` / When er eine Trip-Zeile oder „Bearbeiten" anklickt / Then landet er auf der EINEN Trip-Oberfläche `/trips/<id>` (`data-testid="trip-detail-tab-list"`) — es gibt keine separate `/edit`-Seite mehr, die als zweite Oberfläche erscheint.

- **AC-2:** Given ein Aufruf der alten URL `/trips/<id>/edit` (z.B. Bookmark/Deep-Link) / When die Seite lädt / Then leitet sie auf die kanonische Trip-Oberfläche `/trips/<id>` um (kein 404, kein Rendern der alten TripEditView).

- **AC-3:** Given die kanonische Trip-Oberfläche / When die Tab-Leiste rendert / Then zeigt sie exakt sechs Tabs in dieser Reihenfolge: `Übersicht`, `Etappen & Wegpunkte`, `Wetter-Metriken`, `Briefing-Zeitplan`, `Alerts`, `Vorschau`.

- **AC-4:** Given die frisch geöffnete Trip-Oberfläche / When kein Tab gewählt ist / Then ist `Übersicht` aktiv und zeigt das read-only Cockpit mit Sektions-Karten, jede mit „Bearbeiten →"; ein Klick darauf wechselt auf den zugehörigen Editor-Tab (Etappen/Wetter/Zeitplan/Alerts).

- **AC-5:** Given der `Briefing-Zeitplan`-Tab / When der Nutzer Morgen-/Abend-Zeit, Kanäle oder Schwellwerte ändert und speichert / Then wird `report_config` real per `PUT /api/trips/<id>` persistiert (kein statisches Mockup mehr) und alle nicht in der UI gepflegten Felder (insb. `change_threshold_*`) bleiben byte-genau erhalten (Read-Modify-Write).

- **AC-6:** Given der Trip-Name / When der Nutzer ihn auf der kanonischen Oberfläche bearbeitet und speichert / Then wird der neue Name persistiert und der Trip-Header zeigt ihn an — die Namens-Bearbeitung geht durch die Stilllegung von `/edit` nicht verloren.

- **AC-7:** Given die Editor-Tabs `Etappen & Wegpunkte`, `Wetter-Metriken`, `Alerts` / When der Nutzer sie öffnet / Then funktionieren ihre bestehenden Pro-Tab-Speicher-Wege unverändert (keine Regression durch die Konsolidierung).

- **AC-8:** Given die gesamte Trip-Oberfläche / When Texte rendern / Then ist die Terminologie durchgängig `Trip · Etappe · Wegpunkt` (kein „Tour"/„Reise"/„Waypoint" sichtbar).

## Expected Behavior

**EINE Oberfläche, Pro-Tab-Speichern:**
| Tab (value) | Rolle | Inhalt | Speichern |
|-------------|-------|--------|-----------|
| `overview` | ANSEHEN | `HubOverview` Cockpit + „Bearbeiten →" | — (read-only) |
| `stages` | BEARBEITEN | `EditStagesSection` (Karte+Wegpunkte) | eigener Save (vorhanden) |
| `weather` | BEARBEITEN | `WeatherMetricsTab` | `/weather-config` (vorhanden) |
| `briefings` | BEARBEITEN | **NEU: echter `EditReportConfigSection`** | `PUT /api/trips/<id>` (neu in #616) |
| `alerts` | BEARBEITEN | `AlertsTab` | `PUT /api/trips/<id>` (vorhanden) |
| `preview` | VERIFIZIEREN | Email/SMS-Vorschau | — |

- `/trips/[id]/edit/+page.svelte`: rendert nicht mehr `TripEditView`, sondern leitet auf `/trips/[id]` um (ggf. `?tab=`-Mapping).
- `TripEditView.svelte` wird nach Migration nicht mehr eingebunden (tote Datei → entfernen oder als deprecated markieren).
- Trip-Name-Edit: inline auf der Übersicht oder im Header, persistiert per `PUT /api/trips/<id>` (Read-Modify-Write).

## Out of Scope

- Visueller 1:1-Pixel-Abgleich der einzelnen Tab-Inhalte → Folge-Slices 2/4–4/4 (#587/#617/#618).
- Kanal-Verkettungs-Logik (Briefing-Zeitplan zeigt nur aktive Kanäle, Alerts erben Vorbelegung) → #617.
- Mobile-Adaption der Oberfläche → #618.
- Create-Flow „Neue Tour als Tab-Editor" → #622.

## Test Strategy

- **Playwright-E2E gegen Staging** als eingeloggter Nutzer (kein File-Content-Check):
  - Trips-Liste → Trip öffnen → genau EINE Oberfläche, 6 Tabs in Reihenfolge (AC-1/AC-3)
  - `/trips/<id>/edit` aufrufen → Redirect auf `/trips/<id>` (AC-2)
  - Übersicht ist Default + „Bearbeiten →" wechselt Tab (AC-4)
  - Briefing-Zeitplan: Zeit ändern → speichern → Reload → Wert persistent, `change_threshold_*` unverändert (AC-5)
  - Name ändern → speichern → Reload → persistent (AC-6)
  - Etappen/Wetter/Alerts speichern weiterhin (AC-7)
  - Terminologie-Scan im DOM (AC-8)
- Pre-existing file-content-Tests (`issue_581_trip_detail_jsx.test.ts` AC-6/7, `bug_505_edit_mode.test.ts`) bei Kollision nachziehen — Verhaltenstests sind führend.
