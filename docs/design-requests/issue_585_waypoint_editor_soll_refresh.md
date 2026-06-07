# Design-Request: Frischer SOLL für Waypoint-/Etappen-Editor (vereinte Trip-Seite)

**Auslöser:** Issue #585 (Epic #575) — als „überholt" geschlossen, weil die SOLL-Vorlage den
Live-Stand nach #616 nicht mehr abbildet.

## Problem mit dem aktuellen Handoff

Der von #585 gebaute Etappen-/Waypoint-Editor ist bereits **live & 1:1** umgesetzt (von
`fresh-eyes-inspector` bestätigt) — aber auf der **vereinten Trip-Seite** (`/trips/[id]`,
Tab „Etappen & Wegpunkte"), nicht mehr auf einer separaten „Bearbeiten"-Seite.

Die Handoff-Quelle widerspricht diesem Live-Stand:

| Quelle | Problem |
|--------|---------|
| `soll/J-waypoint-editor-etappen-tab.png` | zeigt die **alte separate „Bearbeiten"-Seite**: 5 Tabs (*Route / Etappen & Wegpunkte / Wetter / Reports / Alarmregeln*), Breadcrumb „… / **Bearbeiten**", Sub-Zeile „TRIP BEARBEITEN". Diese Seite ist per **#616** stillgelegt (`/trips/[id]/edit` → Redirect). |

Ein „1:1"-Nachbau wäre eine **Regression**: er holte die separate 5-Tab-Bearbeiten-Seite
zurück, obwohl #616 bewusst auf **EINE** Trip-Seite mit 6 Tabs vereinheitlicht hat.

## Bitte um frischen SOLL

Für eine künftige echte Fidelity-Prüfung des **aktuellen Editors** wird benötigt:

1. **Frischer SOLL** `J-waypoint-editor-etappen-tab.png`, gerendert von der **vereinten
   Trip-Seite** (`/trips/[id]`, aktiver Tab „Etappen & Wegpunkte"):
   - 6-Tab-Leiste *Übersicht / Etappen & Wegpunkte / Wetter-Metriken / Briefing-Zeitplan /
     Alerts / Vorschau* (Stand #616).
   - Darunter der Etappen-Strip (Eyebrow „ETAPPEN · DRAG ZUM SORTIEREN · + PAUSE ZWISCHEN",
     T-Badges, Drag-Handle, ×) und der Karten-/Wegpunkt-Editor der aktiven Etappe.
2. Klärung Tab-Zähler-**Badge-Stil**: `fresh-eyes` bemängelte den großen orange Tab-Zähler-Badge
   (sitzt in #616s `TripTabs`, nicht in #585). Falls das ein echter Soll-Abweichung ist →
   bitte im neuen SOLL eindeutig zeigen; gehört dann zu einem Folge-Issue gegen #616.

Danach kann ein neues Fidelity-Issue mit Pixel-Diff-Gate `J-waypoint-editor-etappen-tab`
aufgesetzt werden.

## Hinweis Diff-Tool

`design_fidelity_diff.py` mappt `J-waypoint-editor-etappen-tab` aktuell auf `/trips` (Liste)
ohne Pre-Action. Für den Editor braucht es die URL `/trips/<id>?tab=stages` (Deep-Link in den
Etappen-Tab). Vorlage: das Wegwerf-Skript `docs/artifacts/issue-585-waypoint-editor/render_diff_585.py`.
Erst beim neuen Fidelity-Issue relevant, dann ins geteilte Tool mitziehen.
