# Mini-Spec: #1347 — Nacht-Tabelle Datums-Anker kanonisch

- **Status:** Draft
- **created:** 2026-07-22
- **Workflow:** fix-1347-night-table-date-anchor (Bug fast-track)
- **Issue:** #1347

## Problem

`TripReportFormatter._extract_night_rows` (src/output/renderers/trip_report.py:318)
leitet seinen Datums-Anker `first_date` aus `night_weather.data[0].ts` ab. Liefert
`WeatherCacheService.get()` über die „covers"-Regel eine breitere, ungetrimmte
Roh-Zeitreihe (früherer Fetch am selben Wegpunkt), liegt `data[0].ts` auf einem
FRÜHEREN Kalendertag als die echte Ankunft → die „Nacht am Ziel"-Tabelle zeigt den
falschen Tag (Abendstunden des Vortags + Frühstunden vor der Wanderung), die echten
Nachtstunden fehlen. Dieselbe Fehlerklasse wie der bereits behobene Kurzform-Bug
(day_window, Commit 0b2cc5ed) — dort wurde der Anker auf `segment.end_time` gesetzt.

## Was ändert sich

- `_extract_night_rows` bekommt das **kanonische Ankunftsdatum** (aus
  `segments[-1].segment.end_time`, lokale tz) als Parameter und nutzt es als
  `first_date` — statt es aus dem (kontaminierbaren) `night_weather.data[0].ts`
  abzuleiten. Der Aufrufer (trip_report.py ~127-132) hat `last_seg.segment.end_time`
  bereits (berechnet dort schon `arrival_hour`) und reicht das Datum durch.

## Was darf sich NICHT ändern

- Nacht-Fenster-Logik (Ankunft→06:00 Folgetag, 2h-Blöcke), #806/#856-Aggregation.
- Verhalten bei sauberem (nicht kontaminiertem) Cache bleibt identisch.

## Acceptance Criteria

- **AC-1:** Given `night_weather`, dessen `data[0].ts` auf einem früheren Kalendertag
  liegt als die Ankunft (`segments[-1].segment.end_time`) — Cache-„covers"-Kontamination,
  When `_extract_night_rows` die Nacht-Tabelle baut, Then verankert sie auf dem
  **Ankunftstag** (nicht auf `data[0].ts.date()`): die Blöcke zeigen Ankunft→06:00
  Folgetag des echten Ankunftstags, nicht Vortags-Stunden.
- **AC-2:** Given sauberes `night_weather` (data[0].ts == Ankunftstag), When gerendert,
  Then ist das Ergebnis **identisch** zum bisherigen Verhalten (keine Regression).
- **AC-3:** Given der Fix, When der Kern-Test läuft, Then reproduziert er die
  Kontamination (data[0].ts ein Tag zu früh) und assertiert die korrekten Anker-Tage —
  rot vor Fix, grün nach Fix.

## Manuelle Test-Schritte / Staging

- Staging-Test-Mail: Nacht-Block zeigt plausible Ankunft→06:00-Stunden des Ankunftstags;
  `briefing_mail_validator.py` Exit 0.
