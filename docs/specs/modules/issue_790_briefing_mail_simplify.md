---
entity_id: issue_790_briefing_mail_simplify
type: module
created: 2026-06-12
updated: 2026-06-12
status: draft
version: "1.0"
tags: [email, renderer, briefing, simplification]
---

# Briefing-Mail vereinfachen (#790)

## Approval

- [x] Approved (PO 'go' 2026-06-12 — autonome Durchführung freigegeben)

## Purpose

Die Trip-Briefing-Mail wird von Ballast befreit: vier veraltete/redundante Blöcke
werden **aus dem Render-Code entfernt** (nicht per Flag totgeschaltet), die doppelte
Antwort-Kommando-Liste auf einmal reduziert, der Metrik-Pill-Block zum einen festen
Wetterblock gemacht (immer, vollständig, mit Uhrzeit) und der Vortag-Vergleich von
einer unlesbaren Delta-pro-Segment-Tabelle am Ende zu **einer Einordnungszeile weit
oben** umgebaut.

## Source

- **File:** `src/output/renderers/email/html.py`
- **File:** `src/output/renderers/email/plain.py`
- **File:** `src/output/renderers/email/helpers.py`
- **File:** `src/output/renderers/email/__init__.py`
- **File:** `src/formatters/trip_report.py`
- **File:** `src/services/day_comparison.py`
- **Identifier:** `render_html`, `render_plain`, `render_day_comparison_html/plain`, `build_metrics_summary_pills`, `DayComparisonService`

## Estimated Scope

- **LoC:** ~250 Netto, überwiegend Löschungen (LoC-Override gesetzt)
- **Files:** ~6 Code-Dateien + ~50 Tests (großteils Löschen)
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `DayComparison` / `DayComparisonService` | service | liefert Vortag-Deltas pro Segment; wird um Gesamt-Einordnung erweitert |
| `build_metrics_summary_pills` | helper | bleibt — wird zum festen Metrik-Block |
| `briefing_mail_validator.py` | gate | prüft Metriken-Überblick als Pflichtblock (compact) — bleibt kompatibel |

## Implementation Details

```
ENTFERNEN (Render-Code raus, Helper-Funktionen löschen wo exklusiv):
  - Quick-Take-Chips:  helpers.build_quick_take_chips + html else-Zweig (Z.649-658)
  - Highlights:        html.py:611-618, plain.py:267-271, trip_report._compute_highlights
  - Tageslicht:        html._format_daylight_html, plain._format_daylight_plain + Aufrufe
  - Tages-Summe:       helpers.build_daily_aggregates + html.py:667-735, plain.py:289-320
  - Antwort-Kommandos: html.py rendert 2x (Block Z.856 + Footer-Span Z.874) -> Footer-Span raus

METRIK-PILLS (der eine Block, immer sichtbar):
  - show_metrics_summary-Gate entfernt: Pills werden IMMER gerendert
  - metric_ids = enabled dc.metrics; FALLS leer -> Default-Satz:
      [temperature, wind, gust, precipitation, thunder, freezing_level, visibility]
  - jede Pill mit Uhrzeit wie bisher in _pill_for_metric

VORTAG-VERGLEICH (eine Zeile, oben):
  - neue Service-Methode summarize(comparison) -> kurze natursprachliche Einordnung
  - Temp: avg(temp_max.delta) ueber Segmente: >+1.5 "waermer" / <-1.5 "kaelter" / sonst "aehnlich temperiert"
  - Regen: sum(precip_sum.delta): >+1mm "nasser" / <-1mm "trockener" / sonst gleich
  - Text: "Vortag: heute {temp} und {regen} als gestern"
    (bei beidem neutral: "Vortag: heute aehnliches Wetter wie gestern")
  - Position: direkt unter compact_summary (Eine-Zeile-Summary), VOR allen Detail-Bloecken
  - alte render_day_comparison_html/plain (Tabelle am Ende) entfernt
```

## Expected Behavior

- **Input:** Trip mit Wetterdaten, optional gestrigem Snapshot
- **Output:** schlanke Briefing-Mail (HTML full + plain) ohne die vier Altblöcke, mit
  festem Metrik-Pill-Block und einer Vortag-Einordnungszeile oben, Kommandos nur 1×
- **Side effects:** keine; entfernte `report_config`-Felder bleiben im Schema (Bestandsdaten)

## Acceptance Criteria

- **AC-1:** Given eine gerenderte Trip-Briefing-Mail (HTML full + plain) / When die Mail erzeugt wird / Then erscheinen **keine** Quick-Take-Chips mehr (kein `build_quick_take_chips`-Output), unabhängig von `show_quick_take_tags`.
  - Test: Mail mit Wetterdaten rendern, prüfen dass die alten Chip-Texte/Strukturen nicht im Output sind.

- **AC-2:** Given eine gerenderte Briefing-Mail / When die Mail erzeugt wird / Then erscheint **kein** Highlights-/Zusammenfassungs-Block (weder „Zusammenfassung"-Sektion HTML noch Plain), unabhängig von `show_highlights`.
  - Test: Mail mit Highlights-Daten rendern, prüfen dass kein Zusammenfassungs-Block erscheint.

- **AC-3:** Given eine gerenderte Briefing-Mail / When die Mail erzeugt wird / Then erscheint **kein** „Ohne Stirnlampe"/Tageslicht-Block, unabhängig von `show_daylight`.
  - Test: Mail mit Daylight-Window rendern, prüfen dass „Stirnlampe" nicht im Output ist.

- **AC-4:** Given eine gerenderte Briefing-Mail / When die Mail erzeugt wird / Then erscheint **kein** „Tages-Summe"-Block (HTML + Plain), unabhängig von `daily_summary_metrics`.
  - Test: Mail mit gesetzten daily_summary_metrics rendern, prüfen dass „Tages-Summe" nicht im Output ist.

- **AC-5:** Given eine gerenderte HTML-Briefing-Mail / When die Mail erzeugt wird / Then erscheint die Antwort-Kommando-Liste **genau einmal** (nicht zweimal).
  - Test: HTML rendern, Vorkommen des Kommando-Listings zählen == 1.

- **AC-6:** Given ein Trip dessen `display_config.metrics` leer ist / When die Briefing-Mail gerendert wird / Then erscheint der „Metriken-Überblick" mit einem Default-Satz an Pills (mind. Temperatur, Wind, Niederschlag, Gewitter), **jeweils mit Uhrzeit** — nicht nur die leere Überschrift. Bei gefüllter Metrik-Auswahl erscheinen genau diese Metriken als Pills.
  - Test: Trip mit leeren metrics rendern → mehrere Pills mit Uhrzeit vorhanden; Trip mit konkreter Auswahl → genau diese Pills.

- **AC-7:** Given ein Trip mit gestrigem Snapshot und heutigen Daten / When die Briefing-Mail gerendert wird / Then erscheint **eine einzige** Vortag-Einordnungszeile (z.B. „Vortag: heute wärmer und trockener als gestern") **oben** direkt unter der Eine-Zeile-Summary — **keine** Delta-pro-Segment-Tabelle am Ende.
  - Test: Mail mit gestern wärmer/heute kälter rendern → genau eine Einordnungszeile oben, kein „Segment 1:/Segment 2:"-Vergleichsblock am Ende.

- **AC-8:** Given eine gerenderte Briefing-Mail / When die Mail erzeugt wird / Then bleiben **Etappen-Kennzahlen, Großwetterlage, Confidence-Hinweis, Wetteränderungen, Stundentabellen, Gewitter-Vorschau und Ausblick/Nächste Etappen** unverändert erhalten (Regressionsschutz).
  - Test: Mail mit allen Daten rendern, prüfen dass diese Blöcke weiterhin erscheinen.

- **AC-9:** Given ein Bestands-Trip-JSON mit den (jetzt unbenutzten) Feldern `show_quick_take_tags`, `show_highlights`, `show_daylight`, `daily_summary_metrics` / When der Trip geladen und gespeichert wird / Then bleiben diese Felder erhalten (kein Schema-Removal, keine Datenverlust).
  - Test: Trip-Roundtrip (load → save → load), Felder unverändert vorhanden.

## Known Limitations

- Die `report_config`-Felder der entfernten Blöcke bleiben als tote Felder im Schema
  (Bestandsdaten-Kompatibilität, analog #710-Vorgehen bei `confidence`). Ein späteres
  Schema-Cleanup mit Migration ist möglich, aber nicht Teil dieses Issues.
- `show_metrics_summary` verliert seine Wirkung (Pills sind jetzt immer an); das Feld
  bleibt im Schema, wird aber im Render-Pfad ignoriert.

## Changelog

- 2026-06-12: Initial spec created (#790)
