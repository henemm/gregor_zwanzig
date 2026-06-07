---
entity_id: issue_641_remove_dead_sms_trend
type: module
created: 2026-06-07
updated: 2026-06-07
status: draft
version: "1.0"
tags: [sms, cleanup, dead-code]
---

# #641 Toten SMS-Trend-Pfad entfernen

## Approval

- [ ] Approved

## Purpose

Der `Trend 3T:`-Block in `format_sms` (#623 AC-4, erweitert in #640) wird von keinem
produktiven Pfad aufgerufen — kein Aufrufer übergibt `multi_day_trend` (SMS-Vorschau
und telegram_kurzform übergeben es nicht). Toter Code, in dem zuletzt der #640-Off-by-One
(MED→„L") unbemerkt steckte. Entfernen — output-erhaltend (echte SMS unverändert).

## Source

- **File:** `src/formatters/sms_trip.py`
- **Identifier:** `_sms_peak_only`, `format_sms`-Trend-Block + `multi_day_trend`-Param

## Estimated Scope

- **LoC:** ~ −40 (Entfernung) produktiv
- **Files:** `sms_trip.py`, SMS-Trend-Tests in test_issue_623/test_issue_640
- **Effort:** low

## Behalten (NICHT anfassen — live)

- `render_threshold_peak_value` (Haupt-SMS #624 via builder.py + Telegram/E-Mail-Trend)
- `format_trend_tokens` precip/wind/gust/thunder-Tokens (Telegram + E-Mail-Trend live)

## Acceptance Criteria

**AC-1:** Given `format_sms`, When der Rückbau abgeschlossen ist, Then existiert kein
`multi_day_trend`-Parameter, kein `Trend 3T:`-Block und keine `_sms_peak_only`-Funktion
mehr in `src/formatters/sms_trip.py`.

**AC-2:** Given die echte SMS-Vorschau (`render_sms_preview`), When sie vor und nach dem
Rückbau für denselben Trip/Report erzeugt wird, Then ist die Ausgabe **bit-identisch**
(der entfernte Pfad lief ohnehin nie → kein Verhaltens-Change).

**AC-3:** Given Telegram- und E-Mail-Trend, When der Rückbau abgeschlossen ist, Then sind
sie unverändert (helpers.py-Tokens + `render_threshold_peak_value` bleiben).

**AC-4:** Given die Testsuite, When die SMS-Trend-spezifischen Tests (#623/#640 SMS-Teile)
entfernt sind, Then bleibt die übrige Suite grün; der Haupt-SMS-Test (mit `@`-Zeiten via
#624) bleibt erhalten und grün.

## Out of Scope

- Echter SMS-Versand (#608) — dort wird der SMS-Trend bei Bedarf gegen das echte
  160-Zeichen-Limit neu gebaut.
- Telegram-/E-Mail-Trend, Haupt-SMS-Format.

## Test-Strategie (mock-frei)

- Behavior-Preservation: `render_sms_preview` Output vor==nach (bit-identisch).
- Suite grün nach Entfernen der SMS-Trend-Tests; Haupt-SMS-Test grün.

### Geplante Tests (RED → GREEN)

Laufzeit-Introspektion des echten Vertrags (kein Datei-Text-Scan):

- `test_format_sms_has_no_multi_day_trend_param` — `format_sms` hat keinen
  `multi_day_trend`-Parameter mehr (toter SMS-Trend-Pfad entfernt). AC-1.
- `test_sms_peak_only_helper_removed` — Helfer `_sms_peak_only` ist entfernt. AC-1.
