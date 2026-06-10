---
entity_id: issue_721_email_outlook
type: module
created: 2026-06-10
updated: 2026-06-10
status: draft
version: "1.0"
tags: [email, outlook, ausblick, confidence, stability, issue-709, issue-721]
---

# E-Mail-Ausblick — Großwetterlage + nächste Etappen + Vorhersage-Sicherheit

## Approval

- [x] Approved

## Purpose

Verschmilzt drei bisher getrennte E-Mail-Konzepte (Großwetterlage, kompakte
Zusammenfassung, Highlights) zu **einem** kohärenten Ausblick-Block, der nach
vorne schaut: Großwetterlage als Rahmen, darunter die nächsten Etappen mit
Uhrzeiten (wann reißt ein Schwellwert) und Vorhersage-Sicherheit in Prozent.
Slice 1 von Issue #709 (E-Mail-Inhalt radikal eindampfen).

## Source

- **File:** `src/output/renderers/email/html.py` (Trend-Block „05 · Ausblick", `render_stability_label_html`)
- **File:** `src/output/renderers/email/plain.py` (Plain-Text-Äquivalent)
- **File:** `src/services/trip_report_scheduler.py` (`_build_stage_trend` — Trend-dict-Aufbau)
- **File:** `src/app/models.py` (`TripReportConfig` — neues Feld `show_outlook`)
- **Identifier:** Trend-Renderer + Stabilitäts-Label-Verschmelzung, `confidence_pct` pro Etappe

Schicht: **Python-Backend** (E-Mail-Renderer + Scheduler-Datenaufbau).
Frontend-UI für den `show_outlook`-Schalter ist NICHT Teil von Slice 1 — kommt
in Slice 3 (#723). Slice 1 setzt nur einen sinnvollen Default und rendert.

## Estimated Scope

- **LoC:** ~180–230
- **Files:** 4 (html.py, plain.py, trip_report_scheduler.py, models.py) + Tests
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `WeatherPatternService` (`weather_pattern.py`) | upstream | Liefert `StabilityResult` (STABIL/WECHSELHAFT/FRAGIL) aus confidence_pct |
| `SegmentWeatherSummary.confidence_pct_min` | upstream | Vorhersage-Sicherheit pro Segment (bis T+96/120h) |
| `format_trend_tokens` (`helpers.py`) | upstream | Liefert @-Uhrzeiten pro Etappe (#640) — unverändert weiterverwendet |
| `render_stability_label_html` (`html.py`) | wird verschoben | Großwetterlage-Box, künftig Kopf des Ausblicks |

## Implementation Details

```
Aktueller Zustand (vor Slice 1):
  - stability_html  → eigener Block, gesteuert durch show_stability, oberhalb gerendert
  - Trend-Block „05 · Ausblick / Nächste Etappen" → Tabelle TEMP/REGEN/WIND/GEWITTER
    pro Etappe, @-Uhrzeiten aus #640, gesteuert durch multi_day_trend
  - confidence_pct → existiert in Daten, NICHT im Trend-dict, nur vager Plain-Hinweis
    (build_confidence_hint: „Ab Donnerstag weniger verlässlich")

Slice 1 (verschmelzen):
  1. Neues Feld  TripReportConfig.show_outlook: bool = True
     - steuert den GESAMTEN Ausblick-Block (Großwetterlage + nächste Etappen)
     - Default True (sinnvolle Voreinstellung; UI-Schalter erst Slice 3)
  2. Großwetterlage als KOPF in den Ausblick-Block integrieren
     (render_stability_label_html-Inhalt wandert in den „05 · Ausblick"-Container,
      VOR die Etappen-Tabelle). Kein separater Block mehr an alter Position.
  3. confidence_pct pro Etappe ins Trend-dict aufnehmen (_build_stage_trend)
     und im Trend-Renderer pro Etappe als „Sicherheit NN%" anzeigen.
     - Wert aus confidence_pct_min des jeweiligen Stage-Segments.
     - Fehlt der Wert → keine Prozent-Angabe (kein „0%", keine Erfindung).
  4. Uhrzeiten: unverändert über format_trend_tokens (#640). Nur wo Stundendaten
     vorliegen erscheint ein @-Zeitstempel; bei ferneren Etappen Tageswert ohne Uhrzeit.

Bestandsdaten / Schema:
  - show_stability, show_compact_summary, show_highlights bleiben im Modell
    erhalten (forward-compatible, kein Feld-Removal).
  - show_outlook ist additiv. Read-Modify-Write erhält alle Fremdfelder.
```

## Expected Behavior

- **Input:** Trip mit kommenden Etappen, `report_config.show_outlook` (Default True),
  pro Segment `confidence_pct_min`, `StabilityResult` aus dem Pattern-Service.
- **Output:** E-Mail mit EINEM Ausblick-Block: Großwetterlage-Einordnung als Kopf,
  darunter Tabelle der nächsten Etappen mit Uhrzeiten (wo verfügbar) und
  Vorhersage-Sicherheit in %.
- **Side effects:** Keine. Reine Render-/Datenaufbereitung. Persistenz unverändert
  (additives Feld).

## Acceptance Criteria

- **AC-1:** Given ein Trip mit mehreren kommenden Etappen und berechneter Großwetterlage / When der Abend-Report mit `show_outlook=true` gerendert wird / Then beginnt der Ausblick-Block mit der Großwetterlage-Einordnung (STABIL, WECHSELHAFT oder FRAGIL) und darunter folgt die Tabelle der nächsten Etappen — beides im selben Block, in dieser Reihenfolge.
  - Test: E-Mail eines Test-Trips rendern, im Ausblick-Bereich verifizieren, dass das Wetterlage-Label UND die Etappen-Tabelle erscheinen, das Label oberhalb der Tabelle steht. Kein separater Stabilitäts-Block an der alten Position.

- **AC-2:** Given kommende Etappen mit gesetztem `confidence_pct_min` / When der Ausblick gerendert wird / Then zeigt jede Etappe ihre Vorhersage-Sicherheit als Prozentwert an (z.B. „Sicherheit 82%").
  - Test: Test-Trip mit Etappen unterschiedlicher Lead-Time rendern; im Ausblick die pro-Etappe-Prozentwerte ablesen; nahe Etappe höhere %, fernere niedrigere % (entsprechend den propagierten confidence-Werten).

- **AC-3:** Given eine nahe Etappe mit Stundendaten und eine fernere Etappe ohne Stundenauflösung / When der Ausblick gerendert wird / Then trägt die nahe Etappe einen Uhrzeit-Stempel an gerissenen Schwellwerten (z.B. Gewitter/Regen mit „@HH:00"), die fernere Etappe zeigt nur Tageswerte ohne erfundene Uhrzeit.
  - Test: Trip mit naher Schwellwert-Etappe (Stundendaten) und fernerer Etappe; im gerenderten Ausblick verifizieren, dass die nahe Etappe einen @-Zeitstempel enthält und die fernere keinen.

- **AC-4:** Given `show_outlook=false` / When der Report gerendert wird / Then erscheint weder die Großwetterlage noch die Tabelle der nächsten Etappen in der E-Mail.
  - Test: Identischen Trip einmal mit `show_outlook=true` und einmal mit `false` rendern; im false-Fall fehlt der gesamte Ausblick-Block (kein Label, keine Tabelle, kein leerer Platzhalter).

- **AC-5:** Given ein gespeicherter Trip mit gesetzten Altfeldern (`show_stability`, `show_compact_summary`, `show_highlights`) / When dessen `report_config` geladen, `show_outlook` ergänzt und wieder gespeichert wird / Then bleiben die Altfelder unverändert erhalten (kein Datenverlust, keine harte Schema-Löschung).
  - Test: Round-Trip — Trip mit Altfeldern laden → speichern (mit show_outlook) → neu laden → die Altfelder sind byte-identisch vorhanden.

## Known Limitations

- Letzte Etappe eines Trips: Gibt es keine „nächsten Etappen" mehr, zeigt der
  Ausblick nur die Großwetterlage (kein leerer Tabellen-Block). Fehlt auch die
  Stabilität, entfällt der Block ganz.
- Vorhersage-Sicherheit setzt voraus, dass die Ensemble-Anreicherung
  (`_enrich_ensemble_for_trip`) gelaufen ist; ohne `confidence_pct` entfällt die
  Prozent-Angabe pro Etappe (Großwetterlage und Etappen-Werte bleiben).
- Frontend-Schalter für `show_outlook` folgt in Slice 3 (#723). Slice 1 nutzt den
  Default True.

## Changelog

- 2026-06-10: Initial spec created (Slice 1 von #709 / #721)
