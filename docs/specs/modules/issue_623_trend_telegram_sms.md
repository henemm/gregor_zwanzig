---
entity_id: issue_623_trend_telegram_sms
type: module
created: 2026-06-06
updated: 2026-06-06
status: draft
version: "1.0"
tags: [reports, renderers, trend, telegram, sms, consolidation]
---

# #623 Mehrtages-Trend in Telegram + SMS + Renderer-Konsolidierung

## Approval

- [ ] Approved

## Purpose

Der Mehrtages-Trend (#561) erscheint bisher nur in der E-Mail. Diese Spec rüstet
ihn für Telegram und SMS nach, ergänzt das fehlende E-Mail-Kontext-Label und
konsolidiert die Trend-Semantik in **eine** gemeinsame Funktion, sodass beim
Hinzufügen von Kanälen keine Logik-Duplikate (und kein „LOW"-artiger Drift)
entstehen. Tote Doppel-Renderer werden entfernt.

## Source

- **File:** `src/output/renderers/email/helpers.py` (neue gemeinsame Token-Funktion)
- **Identifier:** `format_trend_tokens()`

## Estimated Scope

- **LoC:** ~200 (produktiv; Cleanup entfernt zusätzlich Code)
- **Files:** 6 (helpers.py, html.py, plain.py, narrow.py, sms_trip.py/sms-renderer, trip_report.py)
- **Effort:** medium

## Dependencies

- Upstream: `_build_stage_trend` (`src/services/trip_report_scheduler.py`) liefert
  `multi_day_trend: list[dict]` mit Keys `weekday, name, temp_lo, temp_hi, precip_mm,
  wind_dir, wind_kmh, thunder ("NONE"|"MED"|"HIGH"), note`.
- Downstream: E-Mail-HTML, E-Mail-Text, Telegram (`render_narrow`), SMS-Formatter.

## Design-Referenz

`Gregor 20 - Issue 561 Mehrtages-Trend.html` (Design-Handoff X3DC38bPSDLUhbWyXCVUWg),
Plain-Text-Fallback-Panel + Tech-Lead-Flag (keine Wetter-Emoji in Spalten).

## Architektur-Entscheidung (Konsolidierung)

Eine gemeinsame `format_trend_tokens(stage: dict) -> TrendTokens` entscheidet **einmal**
alle Semantik: Temperatur-String, Niederschlags-String (`0 → "–"`), Regen-Hervorhebung,
Wind-String, Wind-Hervorhebung, Gewitter-Wort, Gewitter-Quadrat-Farbe (HTML),
Gewitter-Plain-Token (`⚡–/⚡MED/⚡HIGH`), SMS-Token (`GEW-MED`). Jeder Kanal-Renderer
konsumiert diese Tokens und macht **nur noch Layout**. Schwellen (Regen ≥1 mm,
Wind ≥30/≥50 km/h) und die Ampel-Map leben ausschließlich hier.

## Acceptance Criteria

**AC-1:** Given die Trend-Semantik (Schwellen, Ampel-Wörter, „–"-Regel), When ein
Renderer Trend-Werte darstellt, Then bezieht er alle entschiedenen Tokens aus der
einen gemeinsamen Funktion `format_trend_tokens` — keine zweite Stelle entscheidet
Gewitter-Wort, Niederschlags-Format oder Schwellen.

**AC-2:** Given der bestehende E-Mail-HTML- und E-Mail-Text-Trendblock, When er auf
die gemeinsame Token-Funktion umgestellt ist, Then bleibt das gerenderte Ergebnis
inhaltlich unverändert (gleiche Temperaturen, Niederschläge, Wind, Ampel, Hinweis)
gegenüber dem aktuellen Live-Stand.

**AC-3:** Given ein Abend-Briefing mit mindestens einer Folge-Etappe und konfiguriertem
Telegram-Kanal, When der Telegram-Body erzeugt wird, Then enthält er einen Trend-Block
„Nächste Etappen" als fluchtenden Monospace-Block (eine Zeile je Etappe mit Wochentag,
Etappenname, Temp, Regen, Wind, Gewitter-Token `⚡–/⚡MED/⚡HIGH`), dessen Zeilen die
Telegram-Bubble-Breite (40 Zeichen) respektieren.

**AC-4:** Given eine SMS-Kurzform des Trends, When sie erzeugt wird, Then erscheint ein
kompakter flacher Block (`Trend 3T:` plus je Etappe `<Wochentag> <temp> R<regen> W<wind>`,
Gewitter als `GEW-{LEVEL}` statt Blitz-Symbol), und die Gesamtausgabe überschreitet das
konfigurierte SMS-Längenlimit nicht.

**AC-5:** Given der E-Mail-HTML-Trendblock, When er gerendert wird, Then trägt der Kopf
oben rechts ein rechtsbündiges Monospace-Kontext-Label `3-Tage-Trend` mit der Sendezeit
(`gesendet <Wochentag> · <HH:MM>` in der Trip-Zeitzone).

**AC-6:** Given die toten Methoden `_render_html` und `_render_text` in
`src/formatters/trip_report.py` (null Call-Sites), When die Konsolidierung abgeschlossen
ist, Then sind sie entfernt und die gesamte Testsuite bleibt grün.

**AC-7:** Given ein Trip ohne Folge-Etappe (leerer/None-Trend), When ein Briefing für
einen beliebigen Kanal (E-Mail, Telegram, SMS) erzeugt wird, Then erscheint kein
Trend-Heading und kein leerer Block.

**AC-8:** Given der Signal-Kanal, When ein Briefing erzeugt wird, Then bleibt der
Signal-Body unverändert (kein Trend-Block), da Signal als Kanal im Abbau ist (#610).

**AC-9:** Given das reale Gewitter-Modell (`ThunderLevel` = NONE/MED/HIGH), When Tokens
gebildet werden, Then existiert keine „LOW"-Stufe im Code (kein toter Pfad); gültige
Stufen sind ausschließlich NONE, MED, HIGH.

## Edge Cases

| Fall | Verhalten |
|------|-----------|
| `precip_mm == 0` | Token zeigt `–`, nicht `0 mm` (alle Kanäle) |
| `thunder == NONE` durchgehend | Ampel/Token zeigt `kein`/`⚡–`/`GEW-–`, kein Hinweistext |
| > 3 Etappen | auf 3 begrenzt (bestehende `_build_stage_trend`-Logik) |
| Etappe jenseits Forecast-Horizont | bereits in `_build_stage_trend` übersprungen |
| SMS-Block zu lang | Etappennamen entfallen zuerst, Wochentag+Kernwerte haben Priorität |
| `telegram_kurzform` (#614) aktiv | SMS-„Tages-Max" enthält den Trend NICHT doppelt (Trend gehört in den Telegram-Body, nicht zusätzlich in den angehängten SMS-Block) |

## Out of Scope

- Echter SMS-Versand für Trip-Reports (seven.io, #608) — SMS-Trend-Format ist
  Vorarbeit, sichtbar zunächst nur in Vorschau + ab #608-Launch.
- Konfigurierbare Trend-Spalten (#561 Folge-Issue).
- Signal-Trend (Kanal in Abbau).

## Test-Strategie (mock-frei)

- `format_trend_tokens`: reine Funktion → echte Werte rein, Tokens raus (kein Mock).
- Telegram/SMS/HTML/Text: echte Renderer-Aufrufe mit echten Trend-Dicts, Assertion auf
  tatsächlichen Output (Wörter, Schwellen-Hervorhebung, Längenlimit, Label).
- Cleanup: Testsuite grün nach Entfernen der toten Methoden.
