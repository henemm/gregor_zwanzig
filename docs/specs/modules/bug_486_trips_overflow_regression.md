# Spec: bug_486_trips_overflow_regression

**Issue:** #486 (wieder geöffnet, Regression 2026-06-05)
**Created:** 2026-06-05
**Type:** Bug / Design-Fidelity-Regression (Frontend-only)
**Canonical source:** `claude-code-handoff/handoff-2026-06-04-v3/claude-code-handoff/current/jsx/screen-trips.jsx` (Commit 56f2c761)
**SOLL-Bild:** `current/soll/E-trips-list-variant.png`

## Problem

Die Desktop-Trips-Liste (`frontend/src/routes/trips/+page.svelte`, Desktop-Grid
Z. 371–439) rendert pro Zeile **sechs nackte Icon-Buttons** (Alert, Wetter, Play,
Vorschau, Bearbeiten, Löschen) — das „Icon-Geschwader", das mit dem neuen Design
verworfen wurde. Der Mobile-Pfad ist bereits korrekt (`⋯` → `TripActionsSheet`).

## Lösung

Desktop-Aktionszelle nach korrigierter JSX umbauen: ganze Zeile klickbar,
EINE inline Quick-Action nur beim aktiven Trip, alle weiteren Aktionen in ein
`⋯`-Overflow-Menü. Kein neues Datenmodell, keine Backend-Änderung, vorhandene
Handler wiederverwenden.

## Acceptance Criteria

**AC-1:** Given die Desktop-Trips-Liste mit mehreren Trips, When die Seite gerendert ist, Then zeigt jede Zeile in der Spalte „Aktionen" **keinerlei** Reihe von Einzel-Icon-Buttons mehr (kein Alert-/Wetter-/Vorschau-/Bearbeiten-/Löschen-Icon nebeneinander), sondern höchstens eine Quick-Action plus genau einen `⋯`-Button.

**AC-2:** Given eine Trip-Zeile auf Desktop, When der Nutzer irgendwo auf die Zeile (außerhalb der Aktionszelle) klickt, Then wird die Trip-Detail-/Setup-Seite des Trips geöffnet (`/trips/<id>`), und die Zeile ist als `role="button"` mit `tabIndex=0` per Tastatur fokussier- und auslösbar.

**AC-3:** Given eine Trip-Zeile, When der Trip-Status `aktiv` ist, Then erscheint links vom `⋯`-Button eine inline Ghost-Aktion „Briefing senden" (Play-Icon), die `runTestReport(trip, 7)` auslöst; ist der Status nicht `aktiv`, Then fehlt diese inline Aktion.

**AC-4:** Given eine Trip-Zeile, When der Nutzer den `⋯`-Button klickt, Then öffnet sich ein Overflow-Menü mit den Einträgen „Briefing jetzt senden", „Email-Vorschau", „Alert-Konfiguration", „Wetter-Metriken", „Bearbeiten" und — abgesetzt — „Löschen" (danger), die jeweils die bestehenden Handler auslösen.

**AC-5:** Given die geöffnete Aktionszelle (Quick-Action oder `⋯`-Menü), When der Nutzer dort klickt, Then löst der Klick **nicht** die Zeilen-Navigation aus (`stopPropagation`), und das Menü schließt bei Klick außerhalb oder nach Auswahl.

**AC-6:** Given die bestehenden Playwright-Selektoren, When die Liste umgebaut ist, Then bleibt `data-testid="trip-edit-btn"` (oder ein dokumentierter Nachfolger für „Bearbeiten") erreichbar, und der `⋯`-Trigger trägt einen stabilen `data-testid` (z. B. `trip-row-menu-btn`).

**AC-7:** Given das Design-Fidelity-Gate (#603), When der Pixel-Diff der gerenderten Desktop-Liste gegen `E-trips-list-variant.png` läuft, Then liegt der Diff unter der für diesen Screen gesetzten Schwelle (PASS).

**AC-8:** Given der Mobile-Pfad (`< desktop`-Breakpoint), When die Änderung deployt ist, Then bleibt das bestehende Mobile-Verhalten (`trip-card-menu-btn` → `TripActionsSheet`, ganze Karte klickbar) **unverändert** funktionsfähig.

## Out of Scope

- Datenmodell, Backend, Scheduler.
- Mobile-Layout (bereits korrekt).
- Sortier-/Filter-Logik, Summary-Stats, Suche (bleiben wie sie sind).

## Test-Strategie (mock-frei)

- Playwright-E2E gegen Staging als eingeloggter Nutzer: Desktop-Viewport, prüft
  Abwesenheit der Icon-Reihe, Zeilen-Klick-Navigation, `⋯`-Menü-Items,
  Quick-Action nur bei aktivem Trip, Mobile-Pfad unberührt.
- Design-Fidelity-Pixel-Diff gegen `E-trips-list-variant.png`.
