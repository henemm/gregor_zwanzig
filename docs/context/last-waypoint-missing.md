# Context: BUG-01 — Letzter Waypoint fehlt in Trip-Report

**Workflow:** last-waypoint-missing
**Phase:** Analyse (2)
**Datum:** 2026-02-16

## Symptom

Trip-Report zeigt kein Wetter fuer den letzten Waypoint (Zielort) jeder Etappe.
Beispiel: GR221 Tag 2 hat G1→G2→G3, aber nur G1 und G2 bekommen Wetter.
G3 (Soller, Ziel) fehlt.

## Root Cause

`segment_weather.py:116-123` erstellt Location nur aus `segment.start_point`.

Segmente werden aus aufeinanderfolgenden Waypoints gebildet:
- G1→G2 = Segment 1 (Wetter an G1)
- G2→G3 = Segment 2 (Wetter an G2)
- G3 ist nur end_point des letzten Segments — wird nie als start_point verwendet.

## Betroffene Dateien

| Datei | Rolle |
|-------|-------|
| `src/services/trip_report_scheduler.py:365-441` | Erzeugt Segmente, kein Ziel-Segment |
| `src/services/segment_weather.py:116-123` | Fragt nur start_point ab |
| `src/formatters/trip_report.py` | Rendert Segmente, kennt kein "Ziel" |

## Fix-Empfehlung: Option 1 — Ziel-Segment

In `trip_report_scheduler.py` nach den normalen Segmenten ein zusaetzliches
Ziel-Segment erzeugen:
- `start_point = end_point` des letzten Waypoints
- Kurzes Zeitfenster (Ankunftszeit → Ankunft + 2h)
- `segment_id = "Ziel"` oder aehnlich
- Formatter erkennt Ziel-Segment und rendert es speziell

Kein Change in `segment_weather.py` noetig — das Ziel-Segment hat den Zielort
als start_point, wird also korrekt abgefragt.

## Scope

- 2-3 Dateien, ~50-80 LOC
- Risiko: Niedrig (additiv, kein Breaking Change)
- Bestehende Segmente bleiben identisch
