---
entity_id: issue_619_mail_elements_ui
type: module
created: 2026-06-06
updated: 2026-06-06
status: draft
version: "1.0"
tags: [frontend, editor, output, email]
---

# Issue #619 — Auswahl-/Schalter-UI für E-Mail-Elemente in Trip-Einstellungen

## Approval

- [ ] Approved

## Purpose

Stellt im Report-Konfigurations-Dialog pro Trip die Bedienelemente für die seit #621
existierenden Konfig-Felder bereit: vier An/Aus-Schalter für E-Mail-Elemente und eine
Mehrfachauswahl für die Tages-Summe-Kennzahlen. Reines Frontend-Anbinden — Backend-Felder,
Persistenz (Go opaque map) und Render-Gating sind bereits live.

## Source

- **File:** `frontend/src/lib/components/edit/EditReportConfigSection.svelte` (kanonischer
  Report-Editor, geteilt von Edit-Seite `/trips/[id]/edit` und BriefingsTab; #88-konsolidiert,
  Read-Modify-Write über `originalReportConfig`-Blob)
- **File (neu):** `frontend/src/lib/components/edit/reportConfigWrite.ts` (pure Helper für
  Metrik-Toggle + Write-Back-Merge der 5 Felder, node:test-bar)
- **File:** `frontend/src/lib/types.ts` (`ReportConfig`-Interface um 5 Felder erweitern)
- **Hinweis:** Der ältere `ReportConfigDialog.svelte` (Quick-Dialog auf /trips-Liste) ist NICHT
  Ziel — der Edit-Seiten-Abschnitt ist die maßgebliche Einstell-Oberfläche.

## Estimated Scope

- **LoC:** ~70
- **Files:** 2 (beide Frontend)
- **Effort:** low

## Dependencies

- #621 (Backend-Felder `show_stage_stats`, `show_quick_take_tags`, `show_stability`,
  `show_highlights`, `daily_summary_metrics` auf `TripReportConfig`) — bereits live (d57dc06c).
- Go-Handler `UpdateTripHandler` ersetzt `report_config` komplett (opaque map) → State muss
  alle Felder enthalten (read-modify-write).

## Acceptance Criteria

**AC-1:** Given ein eingeloggter Nutzer öffnet den Report-Konfigurations-Dialog eines Trips,
When der Dialog geladen ist, Then zeigt er einen Abschnitt mit vier An/Aus-Schaltern für die
E-Mail-Elemente: „Etappen-Kennzahlen", „Quick-Take-Chips", „Großwetterlage" und
„Zusammenfassung", die den gespeicherten Werten (`show_stage_stats`, `show_quick_take_tags`,
`show_stability`, `show_highlights`) entsprechen.

**AC-2:** Given derselbe Dialog ist offen, When der Nutzer den Tages-Summe-Abschnitt ansieht,
Then erscheint eine Mehrfachauswahl mit fünf Kennzahlen — Niederschlag, Wind, Sicht, Gewitter
und Temperatur — bei der die aktuell in `daily_summary_metrics` enthaltenen Kennzahlen
angehakt sind (Default: Niederschlag, Wind, Sicht, Gewitter aktiv; Temperatur aus).

**AC-3:** Given der Nutzer ändert die Schalter und/oder die Kennzahl-Auswahl und klickt
„Speichern", When der Dialog erneut geöffnet wird, Then sind exakt die zuvor gewählten Werte
wieder dargestellt (Persistenz über Speichern/Neu-Laden, keine Rückkehr auf Default).

**AC-4:** Given der Nutzer speichert die Report-Konfiguration, When der Speichervorgang die
`report_config` ersetzt, Then bleiben alle übrigen Report-Konfig-Felder (Zeiten, Kanäle,
Schwellwerte, `wind_exposition_min_elevation_m`, `multi_day_trend_reports`) unverändert
erhalten (read-modify-write, kein Feldverlust).

**AC-5:** Given ein Trip mit `daily_summary_metrics = ["precipitation", "thunder"]` und
aktivierter Tages-Summe, When die nächste Briefing-Mail gerendert wird, Then enthält der
Tages-Summe-Block ausschließlich Niederschlag und Gewitter (in fester Katalog-Reihenfolge),
nicht Wind/Sicht/Temperatur — verifiziert in einer Test-Mail.

## Out of Scope

- Änderung der Aggregations-Rechenart pro Kennzahl (fest: Regen Σ, Wind/Böe/Gewitter max,
  Sicht min, Temperatur min/max).
- Backend-/Render-Änderungen (existieren seit #613/#621).
- Reparatur der latenten `loader.py:_trip_to_dict()`-Serialisierungslücke (nicht auf dem
  aktiven Go-Save-Pfad; eigenes Issue falls nötig).

## Notes

- Render-Reihenfolge der Tages-Summe ist im Backend FEST (`_METRIC_ORDER`); die UI bildet nur
  die Mengen-Zugehörigkeit ab, nicht die Reihenfolge.
- Metrik-IDs (technisch → Label): `precipitation`→Niederschlag, `wind`→Wind,
  `visibility`→Sicht, `thunder`→Gewitter, `temperature`→Temperatur.
