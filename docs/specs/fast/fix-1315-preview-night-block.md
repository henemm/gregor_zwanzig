# Mini-Spec: #1315 — Vorschau zeigt „Nacht am Ziel" (Vorschau = Versand)

- **Status:** Draft
- **created:** 2026-07-22
- **Workflow:** fix-1315-preview-night-block (Bug fast-track)
- **Issue:** #1315

## Problem

`preview_service.py::_render_email` (Z.241) ruft `TripReportFormatter.format_email()`
**ohne `night_weather`** auf → die Web-Vorschau baut die Sektion „🌙 Nacht am Ziel"
**nie**, obwohl die versendete Mail sie zeigt (Abend- und Morgenbriefing seit #1313).
Verletzt „Vorschau = Versand" (gleiche Klasse wie #1297, Gewitter-Vorschau).

## Was ändert sich

1. **Geteilte Funktion (Konsolidierung, kein Duplikat):** `_fetch_night_weather`
   (aktuell privat in `trip_report_scheduler.py:1235`, hängt nur an `last_segment`)
   wird in ein geteiltes Modul extrahiert (z.B. `services/night_weather.py` oder
   `services/segment_weather.py`) als `fetch_night_weather(last_segment)`. Der
   Scheduler ruft die geteilte Funktion (Verhalten identisch).
2. **Vorschau beschafft `night_weather`:** `preview_service` holt via der geteilten
   Funktion das Nacht-Wetter (aus dem letzten Segment) — **nur wenn**
   `trip.display_config.show_night_block` (gleiche Schalter-Logik wie der Versand) —
   und reicht es an `format_email(..., night_weather=...)` durch. Für Morgen- UND
   Abendbriefing (#1313-Semantik).

## Was darf sich NICHT ändern

- Versand-Verhalten (Scheduler): die extrahierte Funktion ist verhaltensgleich.
- `has_gap` in der Vorschau bleibt False (bewusst, #1331 — keine Über-Flaggung ohne
  echten Versand-Kontext).
- Fehlt `night_weather` (Fetch scheitert / `show_night_block=false`): Vorschau wie bisher.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit `show_night_block=true`, When die E-Mail-Vorschau
  (`render_email_preview`) für ein Abend- ODER Morgenbriefing gerendert wird, Then
  enthält die Vorschau die Sektion „Nacht am Ziel" — genau dann und mit denselben
  Stunden, wie sie die versendete Mail zeigen würde.
- **AC-2:** Given `show_night_block=false`, When die Vorschau gerendert wird, Then
  erscheint KEINE Nacht-Sektion (Parität mit Versand).
- **AC-3 (Konsolidierung):** Given der Fix, Then existiert die Nacht-Wetter-Beschaffung
  als EINE geteilte Funktion, die Scheduler und Vorschau nutzen (kein dupliziertes
  `_fetch_night_weather`); das Scheduler-Versandverhalten ist unverändert (Bestandstests grün).
- **AC-4 (Test):** Given der Fix, When der Kern-Test läuft, Then reproduziert er, dass
  die Vorschau die Nacht-Sektion enthält, wenn `show_night_block` + Nacht-Daten vorliegen —
  rot vor Fix, grün nach Fix.

## Manuelle Test-Schritte / Staging

- Staging-Vorschau (`render_email_preview`, evening) eines Trips mit show_night_block:
  Nacht-Sektion sichtbar, plausibel Ankunft→06:00.
