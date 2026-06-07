---
entity_id: issue_635_telegram_weather_readable
type: module
created: 2026-06-06
updated: 2026-06-06
status: draft
version: "1.0"
tags: [reports, telegram, narrow, readability]
---

# #635 Telegram-Wetter lesbar: Zeitblock-Zeilen statt Stundentabelle

## Approval

- [ ] Approved

## Purpose

Das Telegram-Briefing rendert pro Segment eine dichte Stundentabelle (bis 7 Metrik-
Spalten) plus kryptische Kürzel-Zeilen — in der schmalen Chat-Blase unlesbar. Diese
Spec ersetzt das **nur für Telegram** durch eine lesbare Zeile pro 2h-Segment plus
eine Klartext-Fußzeile. E-Mail (HTML-Tabelle), SMS und der Mehrtages-Trend bleiben
unverändert.

## Source

- **File:** `src/output/renderers/narrow.py`
- **Identifier:** `render_narrow` (Telegram-Segment-Rendering)

## Estimated Scope

- **LoC:** ~120 produktiv (neue Zeilen-/Footer-Builder; alte Tabellen-Pfad für
  Telegram ersetzen)
- **Files:** `narrow.py` (+ ggf. kleiner Helper), Tests
- **Effort:** medium

## Dependencies

- `seg_tables: list[list[dict]]` (stündliche Zeilen je Segment) für Start→Ende-Temp,
  Wind-Spanne, Richtung.
- `SegmentWeatherSummary`: `temp_min_c/max_c, wind_max_kmh, precip_sum_mm,
  cloud_avg_pct, thunder_level_max, visibility_min_m, freezing_level_m`.
- Wolken-Emoji-Skala wie `email/helpers.py` (☀️≤10 · 🌤️≤30 · ⛅≤70 · 🌥️≤90 · ☁️>90).

## Format (Soll, echte KHW-403-Werte)

```
KHW 403 · Abend · Sa 07.06
KHW_06 → Zollnersee Hütte

☀️ 08–10h  13→16°C · Wind 4 NE · trocken
🌥️ 12–14h  15→14°C · Wind 9–17 S · trocken
🌧️ 16–18h  14°C · Wind 18 SW · Regen

⚡ kein · Sicht gut · 0°C-Grenze 3300 m
```

## Acceptance Criteria

**AC-1:** Given ein Telegram-Briefing mit Wetter-Segmenten, When der Body erzeugt
wird, Then erscheint **pro Segment genau eine** Zeile im Format
`{Emoji} {HH}–{HH}h  {Temp} · Wind {Wind} {Richtung} · {Regen}` — und KEINE
stündliche Zahlentabelle und KEINE Kürzel-Zeilen (TF/C/V/0G/SG/CL/CE) mehr.

**AC-2:** Given die Temperatur eines Segments, When die Zeile gebaut wird, Then zeigt
sie den Verlauf `Start→Ende°C` (gerundet, aus erster/letzter Stundenzeile); bei
Differenz < 1 °C einen einzelnen Wert `N°C`.

**AC-3:** Given der Wind eines Segments, When die Zeile gebaut wird, Then zeigt sie
`min–max` km/h (gerundet) + dominante Himmelsrichtung; bei min == max einen
einzelnen Wert.

**AC-4:** Given der Niederschlag eines Segments (`precip_sum_mm`), When die Zeile
gebaut wird, Then erscheint qualitativ: `trocken` (< 0,2 mm), `etwas Regen`
(0,2–2 mm), `Regen` (≥ 2 mm); bei `thunder_level_max >= MED` zusätzlich/stattdessen
`Gewitter`.

**AC-5:** Given das Segment-Emoji, When die Zeile gebaut wird, Then ist es 🌧️ bei
Regen (≥ 0,5 mm), sonst die Wolken-Emoji-Skala aus `cloud_avg_pct` (gleiche
Schwellen wie E-Mail-Renderer).

**AC-6:** Given die Tageswerte, When der Body erzeugt wird, Then schließt eine
Fußzeile in Klartext an: `⚡ {kein|MED|HIGH} · Sicht {gut|mäßig|schlecht} ·
0°C-Grenze {N} m` (Gewitter = Maximum, Sicht = Minimum über Segmente; fehlende
Werte werden weggelassen, kein leeres Feld).

**AC-7:** Given Kopf und Mehrtages-Trend, When der Telegram-Body erzeugt wird, Then
bleiben Trip-/Report-Kopf, der Befehls-Hinweis (#612) und der Mehrtages-Trend-Block
(#623/#633, „Nächste Etappen") erhalten und unverändert.

**AC-8:** Given E-Mail-, SMS- und Signal-Ausgabe, When #635 umgesetzt ist, Then sind
sie unverändert (E-Mail behält die HTML-Stundentabelle; SMS unverändert; Signal
ohne Wetter-Block, Kanal entfernt).

**AC-9:** Given die Telegram-Zeilen, When sie gerendert werden, Then bleibt jede
Zeile innerhalb der Telegram-Bubble-Breite ohne durch lange Inhalte erzwungenen
Umbruch (Format ist von vornherein kompakt).

## Edge Cases

| Fall | Verhalten |
|------|-----------|
| Segment ohne Stundenzeilen | Fallback auf `temp_min/max` aus Summary |
| `precip_sum_mm` None/0 | `trocken` |
| `cloud_avg_pct` None | neutrales Wolken-Emoji (⛅) |
| `visibility_min_m`/`freezing_level_m` None | jeweiliges Fußzeilen-Feld weglassen |
| nur 1 Segment | genau 1 Zeile + Fußzeile |
| Gewitter in einem Segment | Zeile zeigt `Gewitter`, Fußzeile `⚡ MED/HIGH` |

## Out of Scope

- E-Mail-/SMS-Format, Mehrtages-Trend, Metriken-Editor-Anbindung für Telegram-Wetter
  (Telegram-Wetter ist bewusst kuratiert/fest, nicht konfigurierbar).
- Zusammenfassen von Segmenten zu groben Tagesblöcken (PO: eine Zeile pro Segment).

## Test-Strategie (mock-frei)

- `render_narrow("telegram", …)` mit echten Segment-/seg_tables-Dicts → Assertion auf
  tatsächlichen Output: Zeilenformat, Temp-Verlauf, Wind-Spanne, Regen-Wort, Emoji,
  Fußzeile; KEINE Stundentabelle/Kürzel mehr.
- Gegenproben: E-Mail-Renderer weiter mit Tabelle; SMS unverändert; Trend-Block
  weiter vorhanden.
