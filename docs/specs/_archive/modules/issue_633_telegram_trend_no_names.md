---
entity_id: issue_633_telegram_trend_no_names
type: module
created: 2026-06-06
updated: 2026-06-06
status: draft
version: "1.0"
tags: [reports, telegram, trend, renderer]
---

# #633 Telegram-Trend ohne Etappennamen (wie SMS)

## Approval

- [ ] Approved

## Purpose

Lange reale Etappennamen brechen im Telegram-Mehrtages-Trend um. PO-Entscheidung:
„so wie SMS" — SMS zeigt keinen Etappen-Bezeichner, nur Wochentag + Werte. Der
Telegram-Trend lässt den Etappennamen weg (kein Name, keine Nummer).

## Source

- **File:** `src/output/renderers/narrow.py`
- **Identifier:** Telegram-Trend-Zeilenbau in `render_narrow`

## Estimated Scope

- **LoC:** ~3 produktiv + Test-Anpassung
- **Files:** `narrow.py`, zugehörige Trend-Tests
- **Effort:** low

## Acceptance Criteria

**AC-1:** Given der Telegram-Mehrtages-Trend, When eine Etappenzeile gerendert
wird, Then enthält sie KEINEN Etappennamen (und keine Nummer), sondern nur
`{Wochentag}  {Temp}  {Regen}  {Wind}  {⚡-Token}` — analog zur SMS-Logik.

**AC-2:** Given lange Etappennamen im Trip, When der Telegram-Trend gerendert
wird, Then bricht keine Etappenzeile mehr wegen des Namens um (Zeile ≤ Telegram-
Breite ohne namensbedingten Umbruch).

**AC-3:** Given Überschrift und Risiko-Hinweis, When der Trend gerendert wird,
Then bleiben „Nächste Etappen" und die optionale `↳`-Hinweiszeile erhalten, und
der Gewitter-Token bleibt `⚡…` (NICHT `GEW-`, das ist SMS-spezifisch).

**AC-4:** Given E-Mail-Trend und SMS-Trend, When #633 umgesetzt ist, Then sind
beide unverändert (E-Mail behält Etappennamen gemäß #561-Design; SMS wie gehabt).

## Out of Scope

- E-Mail-Trend, SMS-Trend, sonstige narrow-Logik (Signal bleibt ohne Trend).

## Test-Strategie

Mock-frei: `render_narrow("telegram", multi_day_trend=[...])` mit echtem Trend-Dict
inkl. langem Namen → Assertion: Name NICHT im Output, Wochentag + Werte vorhanden,
keine namensbedingte Umbruchzeile. Gegenprobe E-Mail-Renderer: Name weiterhin
vorhanden.
