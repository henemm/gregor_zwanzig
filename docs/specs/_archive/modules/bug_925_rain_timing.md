---
issue: "#925"
workflow: bug-925-rain-timing
status: draft
created: 2026-06-30
---

# Spec: bug-925-rain-timing — SMS-Stunden-Token deckungsgleich mit E-Mail

## Architektur-Entscheidung (ADR)

keine neue Richtung — Bugfix, der den SMS-Pfad an die bereits existierende
per-Stunde-Logik des Trend-Pfads (`_build_stage_trend`) angleicht. Token-Format
(`render_threshold_peak_value`, sms_format.md §5) bleibt unverändert.

## Kontext

`src/formatters/sms_trip.py::build_forecast` baut je Etappe genau **ein**
Sample: `HourlyValue(local_hour(seg.start_time), agg.precip_sum_mm)` — Wert =
Etappen-Summe, Stunde = Etappen-Start. Die E-Mail-Stundentabelle zeigt dagegen
pro Stunde `precip_1h_mm`. Ergebnis: SMS `R5.1@10` (Summe @ Etappenstart) vs.
E-Mail erster relevanter Regen @11 — scheinbarer Widerspruch.

Fix: SMS füttert per-Stunde-Samples aus `seg.timeseries.data` in das vorhandene
`render_threshold_peak_value` (Onset@h + Peak@h). Einheitlich für Regen, Wind,
Böen, Regenwahrscheinlichkeit.

## Acceptance Criteria

**AC-1:** Given eine Etappe, die um 10:00 (Ortszeit) startet, aber erst ab 11:00 Regen über der Schwelle führt, When die Trip-SMS gebaut wird, Then nennt das Regen-Token als Onset-Stunde **11** (nicht 10) — also die erste Stunde mit `precip_1h_mm >= threshold`, identisch zur ersten Regen-Stunde der E-Mail-Tabelle.

**AC-2:** Given dieselbe Etappe, When SMS und E-Mail aus DENSELBEN Segment-Daten gerendert werden, Then stimmt die im SMS-Regen-Token genannte Onset-Stunde mit der ersten Stunde der E-Mail-Tabelle überein, deren Regenwert die Schwelle erreicht (kein Stunden-Versatz, kein Summen-vs-Stundenwert-Widerspruch).

**AC-3:** Given eine Etappe mit Regen-Spitze in einer späteren Stunde als dem Onset, When das SMS-Token gebaut wird, Then erscheint Format `R{onset}@{onset_h}({peak}@{peak_h})` mit dem **Stundenwert** (`precip_1h_mm`) der jeweiligen Stunde — nicht der Etappen-Summe.

**AC-4:** Given Wind, Böen und Regenwahrscheinlichkeit, When die SMS gebaut wird, Then werden auch deren @-Stunden aus per-Stunde-Samples (`seg.timeseries.data`) abgeleitet — kein Token mehr an die Etappen-Startzeit mit Etappen-Aggregat gehängt.

## Technische Hinweise

- Vorbild: `trip_report_scheduler._build_stage_trend` Z. 1022–1036 (per-Stunde `HourlyValue(hour=local_hour(dp.ts, tz), value=dp.<feld>)`).
- dp-Felder: `precip_1h_mm`, `wind10m_kmh`, `gust_kmh`, `pop_pct`.
- `seg.timeseries` kann `None` sein (Provider-Fehler) → fail-soft, Etappe überspringen.
- Schwellen aus der bestehenden Token-Builder-Logik (sms_threshold pro Metrik) unverändert.
- Test ohne Mocks: echte Segment-Domänenobjekte mit Stunden-Timeseries bauen, SMS UND E-Mail rendern, Onset-Stunde vergleichen.

## Risiko / Regression

- Bestehende SMS-Format-Tests (`tests/.../sms*`) können sich ändern, da @-Stunden jetzt Onset statt Etappenstart sind. Erwartete Werte anpassen, wo sie das alte Etappenstart-Verhalten festschrieben.
- Längen-Budget SMS (<=160): Onset+Peak-Format ist bereits der Default (§5), kein neuer Längen-Druck.
