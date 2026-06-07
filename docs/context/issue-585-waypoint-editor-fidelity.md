# Kontext: #585 Waypoint-Editor-Fidelity — als überholt geschlossen

**Auslöser:** Issue #585 „Design-Fidelity: Waypoint-Editor 1:1 nach `screen-waypoint-editor.jsx`"
(Epic #575). Code längst auf `main`/live, Issue blieb am `design-compliance`-Close-Gate hängen.

## Befund

Der von #585 gebaute Etappen-/Waypoint-Editor ist **1:1 live**. Live-Render-Pfad nach #616:
`/trips/<id>?tab=stages` → `TripTabs` → `EditStagesSection` → `EditStagesPanelNew` (+ die
#585-Komponenten `EtappenStrip`/`StageCard`/`WaypointCard`). Commits `97b8746a` (feat) +
`485a9b67` (Staging-Fixes F001/F002/F003), 26 Tests grün.

`fresh-eyes-inspector` (Mode 2) bestätigt die #585-Komponenten als **„korrekt umgesetzt"**:
Eyebrow „ETAPPEN · DRAG ZUM SORTIEREN · + PAUSE ZWISCHEN", Drag-Handle, ×-Button, T-Badges,
Akzent-Rahmen der aktiven Karte, horizontaler Karten-Strip.

## Warum überholt (SOLL stale)

Die #585-SOLL `J-waypoint-editor-etappen-tab.png` zeigt die **alte separate „Bearbeiten"-Seite**
(`TripEditView`, 5 Tabs *Route / Etappen & Wegpunkte / Wetter / Reports / Alarmregeln*,
Breadcrumb „… / **Bearbeiten**", Sub-Zeile „TRIP **BEARBEITEN**"). Diese Seite wurde durch
**#616** stillgelegt (PO-Entscheidung „EINE Trip-Seite", `/trips/[id]/edit` → Redirect). Die
Live-Seite ist die vereinte Trip-Seite mit **6 Tabs** (*Übersicht / Etappen & Wegpunkte /
Wetter-Metriken / Briefing-Zeitplan / Alerts / Vorschau*).

Ein „1:1 zur SOLL"-Nachbau hieße, die alte 5-Tab-Bearbeiten-Seite zurückzuholen → **Regression
gegen #616**. Identisches Muster wie Schwester-Issues #581/#582/#643.

## Pixel-Diff (Beleg, nicht maßgeblich)

Eigenständiges Treiber-Skript (`docs/artifacts/issue-585-waypoint-editor/render_diff_585.py`,
importiert das geteilte `design_fidelity_diff.py` ohne es zu ändern) gegen vier verschiedene
Staging-Trips: konsistenter Boden **~11,75 %** (khw-402), 12–13 % (übrige). Konstanter Boden über
4 Trips = irreduzible Daten-/SOLL-Divergenz (kein „KHW 403"-Trip mit GPX auf Staging, anderer
Sidebar-Nutzer, datums-bedingte „beendet/ARCHIVIERT"-Badges), **kein** Komponenten-Drift.

## Entscheidung (PO 2026-06-07)

#585 als „not planned/superseded" schließen, `design-compliance`-Label entfernen, frischen
SOLL-Design-Request anlegen (`docs/design-requests/issue_585_waypoint_editor_soll_refresh.md`).
