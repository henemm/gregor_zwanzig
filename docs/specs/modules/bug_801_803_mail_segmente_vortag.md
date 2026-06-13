---
entity_id: bug_801_803_mail_segmente_vortag
type: module
created: 2026-06-13
updated: 2026-06-13
status: draft
version: "1.0"
tags: [bug, mail, snapshot, day-comparison, alert]
---

# Bug #801 + #803 — Alert-Mail Segment-km & Vortags-Zeile

## Approval

- [x] Approved (PO 'go' 2026-06-13)

## Purpose

Zwei Briefing-/Alert-Mail-Defekte beheben: (#801) Der Wetter-Snapshot persistiert die
Streckenposition der Segmente nicht, wodurch die Update-/Alert-Mail „km 0.0–0.0" zeigt;
(#803) die Vortags-Zeile trägt das missverständliche Label „Vortag:" und ist wegen grober
Spürbarkeitsschwellen oft inhaltsarm.

## Source

- **File:** `src/services/weather_snapshot.py` (#801, Schema-Datei)
- **Identifier:** `_serialize_segment`, `_reconstruct_segment`
- **File:** `src/services/day_comparison.py` (#803)
- **Identifier:** `summarize_day_comparison`, `_summarize_legacy`, `_summarize_metric_driven`, `_get_threshold`
- **File:** `src/output/renderers/narrow.py` (#803a Telegram-Konsistenz)
- **Identifier:** Vortag-Zeile (Z.361)

## Estimated Scope

- **LoC:** ~70 (Snapshot ~25, day_comparison ~20, narrow ~3, Tests ~20)
- **Files:** 3 Source + 2 Spec-Updates (weather_snapshot.md, issue_748_day_comparison_service.md)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app/models.py` GPXPoint | Datenmodell | hält `distance_from_start_km` (Default 0.0) |
| `app/metric_catalog.py` | Konfiguration | `default_change_threshold` (Salienz-Basis #803b) |
| `output/renderers/email/html.py` + `plain.py` | Konsument | rendern km-Zeile & Vortags-Zeile |

## Implementation Details

### #801 — Streckenpositionen im Snapshot persistieren
- `_serialize_segment`: zusätzlich serialisieren
  `start_distance_from_start_km`, `end_distance_from_start_km` (aus `seg.segment.start_point`/`end_point`)
  sowie `distance_km`, `ascent_m`, `descent_m`, `duration_hours` aus `seg.segment`.
- `_reconstruct_segment`: GPXPoint mit `distance_from_start_km=seg_data.get("start_distance_from_start_km", 0.0)`
  (bzw. end); TripSegment mit `distance_km`/`ascent_m`/`descent_m`/`duration_hours` aus `.get(..., 0.0)`.
- **Additiv & rückwärtskompatibel:** fehlt das Feld (Alt-Snapshot) → `.get` liefert 0.0, kein Crash.

### #803a — Label „Vergleich zum Vortag:"
- In `day_comparison.py` alle Rückgaben „Vortag: …" → „Vergleich zum Vortag: …".
- In `narrow.py` (Telegram) das Präfix „Vortag: " → kompakt, aber unmissverständlich
  „Ggü. Vortag: " (Platz-schonend, da Telegram-Zeile eng).

### #803b — Feinere Spürbarkeitsschwelle (entkoppelt von Alerts)
- Neue Konstante `_SALIENCE_FACTOR = 0.6` in `day_comparison.py`.
- `_get_threshold` für die Vortags-Zeile multipliziert die Katalog-Schwelle mit dem Faktor:
  Temp 5→3, Niederschlag 10→6, Wind 20→12 km/h.
- **Wichtig:** `metric_catalog.default_change_threshold` bleibt unverändert → Alert-Empfindlichkeit
  unberührt. Der Faktor wirkt ausschließlich im Anzeige-Pfad der Vortags-Zeile.

## Expected Behavior

- **Input:** gespeicherter Snapshot mit Segmenten / DayComparison mit ausgewählten Metriken.
- **Output:** Alert-Mail mit korrekten km-Bereichen; Vortags-Zeile mit neuem Label und mehr
  relevanten Metriken.
- **Side effects:** Snapshot-JSON enthält neue Felder (additiv).

## Acceptance Criteria

- **AC-1:** Given ein Snapshot wird mit Segmenten gespeichert, die `distance_from_start_km > 0`
  haben / When der Snapshot wieder geladen wird / Then tragen die rekonstruierten Segmente
  dieselben `start_point.distance_from_start_km` und `end_point.distance_from_start_km` wie vor
  dem Speichern (Roundtrip ohne Verlust).
  - Test: WeatherSnapshotService.save_dated → load_dated mit echten Segmenten (km ≠ 0); assert
    Start/End-km der geladenen Segmente == Original (kein 0.0-Fallback).

- **AC-2:** Given ein alter Snapshot ohne die neuen km-Felder / When er geladen wird / Then fällt
  `distance_from_start_km` sauber auf 0.0 zurück und es wird kein Fehler geworfen
  (Rückwärtskompatibilität).
  - Test: JSON-Datei ohne `start_distance_from_start_km` schreiben → load → assert km == 0.0,
    kein Exception, Segment vollständig.

- **AC-3:** Given eine Alert-/Update-Mail wird aus einem geladenen Snapshot mit echten
  Streckenpositionen gerendert / When die Segment-Kopfzeile erzeugt wird / Then zeigt sie den
  echten km-Bereich (z.B. „km 12.3–18.7"), nicht „km 0.0–0.0".
  - Test: Snapshot mit km > 0 laden → Plain-Renderer (`plain.py`) auf die Segmente anwenden →
    assert Segment-Kopfzeile enthält die echten km-Werte, nicht „0.0–0.0".

- **AC-4:** Given eine Vortags-Vergleichszeile in der Mail wird erzeugt / When die Zeile gerendert
  wird / Then beginnt sie mit „Vergleich zum Vortag:" statt „Vortag:".
  - Test: `summarize_day_comparison` mit DayComparison, deren Deltas die Schwelle überschreiten →
    assert Rückgabe startet mit „Vergleich zum Vortag:" und enthält NICHT „^Vortag:".

- **AC-5:** Given Segmente sind heute durchschnittlich 3,5 °C wärmer als gestern (über der neuen
  Salienz-Schwelle 3 °C, unter der alten 5 °C) / When die Vortags-Zeile erzeugt wird / Then
  erscheint „wärmer" in der Zeile (vorher fiel die Temperatur unter die Schwelle und fehlte).
  - Test: DayComparison mit avg temp-Delta = +3,5, selected_metrics inkl. „temperature" →
    assert „wärmer" in summarize_day_comparison(...); Kontrolle: avg = +2,0 → „wärmer" fehlt.

- **AC-6:** Given die Alert-Empfindlichkeit hängt an `metric_catalog.default_change_threshold` /
  When die Salienz-Schwelle für die Vortags-Zeile gesenkt wird / Then bleibt
  `default_change_threshold` für „temperature" unverändert bei 5.0 (Alerts feuern nicht häufiger).
  - Test: `get_metric("temperature").default_change_threshold == 5.0` nach der Änderung
    (Entkopplungs-Nachweis; markiert als Verhaltens-Invariante des Alert-Pfads).

## Known Limitations

- Salienz-Faktor 0,6 ist ein globaler Multiplikator; metrik-individuelle Feinkalibrierung
  (z.B. Niederschlag separat) ist out-of-scope, kann später folgen.
- #801 repariert nur künftige Snapshots; existierende Alt-Snapshots zeigen bis zum nächsten
  Versand weiterhin 0.0 (fail-soft, kein Crash).

## Changelog

- 2026-06-13: Initial spec created (#801 + #803)
