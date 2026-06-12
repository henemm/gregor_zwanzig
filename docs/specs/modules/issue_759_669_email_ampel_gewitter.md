---
entity_id: issue_759_669_email_ampel_gewitter
type: module
created: 2026-06-11
updated: 2026-06-11
status: draft
version: "1.0"
tags: [email, renderer, ampel, gewitter, design-compliance]
---

# E-Mail: 4-Stufen-Ampelpunkte für Wetter-Metriken (#759) + Gewitter-Badge im Ausblick (#669)

## Approval

- [x] Approved (PO 'go' 2026-06-12)

## Purpose

Die Briefing-Mail soll Wetter-Metriken auf einen Blick erfassbar machen:
1. **#759** — Wind, Böen, Regen und Regenwahrscheinlichkeit erscheinen in der HTML-Mail als **4-stufiger Ampelpunkt** 🟢🟡🟠🔴 (Schema von CAPE übernommen), statt als Zahl bzw. uneinheitlicher Farb-Tint.
2. **#669** — Folge-Etappen mit erwartetem Gewitter zeigen im Ausblick einen **roten ⚡-Badge mit Zeitfenster** („⚡ Gewitter möglich 15:00–16:00").

## Source

- **File:** `src/app/metric_catalog.py` — `display_thresholds` (Ampel-Schwellen, SSoT)
- **File:** `src/output/renderers/email/helpers.py` — `fmt_val()` (Zellen-Rendering), neuer Helper `ampel_dot()`
- **File:** `src/output/renderers/email/html.py` — `trend_rows`/Ausblick-Block (#669 Badge)
- **Schicht:** Python-Backend (E-Mail-Renderer). Kein Frontend, kein Go.

## Estimated Scope

- **LoC:** ~80
- **Files:** 3 (metric_catalog.py, helpers.py, html.py)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `metric_catalog.get_metric().display_thresholds` | data | SSoT der Ampel-Schwellen |
| `fmt_val()` | function | Zentrale Zellen-Formatierung (html=True → Ampel, html=False → Zahl) |
| `format_trend_tokens().thunder_token` | data | Liefert @-Stunden fürs #669-Zeitfenster |

## Implementation Details

### #759 — Ampel-Schwellen (display_thresholds, 4 Bänder = 3 Grenzen)

```
wind:             {"yellow": 30, "orange": 50, "red": 70}
gust:             {"yellow": 50, "orange": 65, "red": 80}   # 50/80 wie heute, orange neu
precipitation:    {"yellow": 1,  "orange": 5,  "red": 10}   # ersetzt {"blue": 5}
rain_probability: {"yellow": 30, "orange": 60, "red": 80}   # ersetzt {"blue": 80}
```

Banding (`ampel_dot`):
```
value is None  → "–"
value >= red    → "🔴"   (U+1F534)
value >= orange → "🟠"   (U+1F7E0)
value >= yellow → "🟡"   (U+1F7E1)
sonst           → "🟢"   (U+1F7E2)
```

In `fmt_val()` für `key in {"wind","gust","precip","pop"}`:
- `html=True`  → `ampel_dot(val, get_metric(<id>).display_thresholds)` (ersetzt Zahl/Tint)
- `html=False` → unverändert numerisch (Plain-Text-Mail + Monospace-Kompaktgrid bleiben ASCII/Zahl)

`format_modes`-Verhalten: Der Ampelpunkt ist im HTML-Pfad die Standard-Darstellung dieser vier Metriken; der bisherige `simplified`-Adjektiv-Pfad (Issue #435) wird im HTML von der Ampel überlagert. Plain-Text-Pfad unverändert.

### #759 — Legende

Eine knappe Ampel-Legende im Footer-/Legenden-Bereich erklärt:
`🟢 unkritisch · 🟡 Achtung · 🟠 Warnung · 🔴 Gefahr`

### #669 — Gewitter-Badge im Ausblick

Im `trend_rows`-Loop (html.py) wird die GEWITTER-Spalte für Folge-Etappen mit Gewitter durch einen roten Badge ersetzt. Zeitfenster aus `thunder_token`:
- `MED@15`          → „⚡ Gewitter möglich 15:00"
- `MED@15(HIGH@16)` → „⚡ Gewitter möglich 15:00–16:00"
- `-` (kein Gewitter) → **kein Badge**, weiterhin das neutrale Quadrat/„kein" wie bisher (kein leerer Platzhalter, kein roter Badge).

Badge-Stil: inline-Hex (Outlook-fest), rot = `G_WX_THUNDER`/`G_DANGER`, Monospace-Zeitfenster, ⚡-Präfix. Vorbild: bestehendes „⚡ Gewitter-Vorschau"-Muster.

## Expected Behavior

- **Input:** SegmentWeatherData / Stundenzeilen (#759), `multi_day_trend`-Stages mit `hourly_thunder` (#669).
- **Output:** HTML-Mail-Body mit Ampelpunkten in den vier Metrik-Spalten; Ausblick mit ⚡-Badge je Gewitter-Etappe.
- **Side effects:** keine. Plain-Text-Mail und Monospace-Kompaktgrid bleiben numerisch/ASCII.

## Acceptance Criteria

- **AC-1:** Given eine HTML-Briefing-Mail mit Wind-Werten 20/40/60/75 km/h in vier Stundenzeilen / When die Mail gerendert wird / Then zeigen die Wind-Zellen 🟢/🟡/🟠/🔴 (kein km/h-Zahlwert in der Zelle).
  - Test: Realer Render der HTML-Mail-Tabelle mit konstruierten Stundenwerten, Prüfung der vier Zellinhalte auf die korrekten Ampel-Emojis gemäß Schwellen wind 30/50/70.
- **AC-2:** Given Böen-Werte 40/55/70/85 km/h / When die HTML-Mail gerendert wird / Then zeigen die Böen-Zellen 🟢/🟡/🟠/🔴 — die rote Stufe beginnt unverändert bei ≥80 km/h (Katalog-Eckwert bewahrt).
  - Test: Realer Render; assert dot bei 79→🟠 und 80→🔴 (Grenzfall ≥80).
- **AC-3:** Given Regen-Werte 0/2/6/12 mm/h / When die HTML-Mail gerendert wird / Then zeigen die Regen-Zellen 🟢/🟡/🟠/🔴 gemäß Schwellen 1/5/10.
  - Test: Realer Render; assert vier Ampel-Emojis in den precip-Zellen.
- **AC-4:** Given Regenwahrscheinlichkeit-Werte 10/40/65/85 % / When die HTML-Mail gerendert wird / Then zeigen die pop-Zellen 🟢/🟡/🟠/🔴 gemäß Schwellen 30/60/80.
  - Test: Realer Render; assert vier Ampel-Emojis in den pop-Zellen.
- **AC-5:** Given dieselben Wetterdaten / When die **Plain-Text**-Variante derselben Mail gerendert wird / Then bleiben Wind/Böen/Regen/Regenwahrscheinlichkeit numerische Werte (keine Emoji), und der Plain-Part ist `isascii()`-konform.
  - Test: Realer Plain-Render; assert numerische Strings vorhanden, assert kein Ampel-Emoji, assert `body.isascii()` (ASCII-Daten).
- **AC-6:** Given ein gerenderter HTML-Mail-Body mit aktiven Ampel-Metriken / When die Mail angezeigt wird / Then enthält sie eine Ampel-Legende, die 🟢/🟡/🟠/🔴 als unkritisch/Achtung/Warnung/Gefahr erklärt.
  - Test: Realer Render; assert Legenden-Text mit allen vier Emojis und ihren Bedeutungs-Labels.
- **AC-7:** Given eine Folge-Etappe im Ausblick mit Gewitter ab Stunde 15 und Spitze Stunde 16 / When die HTML-Mail gerendert wird / Then erscheint in der GEWITTER-Spalte ein roter ⚡-Badge „⚡ Gewitter möglich 15:00–16:00".
  - Test: Realer Render eines `multi_day_trend` mit `hourly_thunder`-Samples; assert Badge-String inkl. Zeitfenster und roter Inline-Farbe.
- **AC-8:** Given eine Folge-Etappe mit Gewitter nur in einer Stunde (z.B. 14) / When gerendert wird / Then zeigt der Badge ein einzelnes Zeitfenster „⚡ Gewitter möglich 14:00" (kein Bindestrich-Bereich).
  - Test: Realer Render mit Single-Hour-Thunder; assert „14:00" ohne „–".
- **AC-9:** Given eine Folge-Etappe ohne erwartetes Gewitter / When gerendert wird / Then erscheint **kein** ⚡-Badge und kein leerer Platzhalter (die Spalte bleibt im bisherigen neutralen Zustand).
  - Test: Realer Render ohne Thunder; assert kein „Gewitter möglich"-Badge in dieser Zeile.
- **AC-10:** Given derselbe Ausblick-Block / When gerendert wird / Then bleiben die übrigen Spalten (TEMP/REGEN/WIND) und Inhalte des Ausblicks unverändert gegenüber dem Status quo.
  - Test: Realer Render; assert TEMP/REGEN/WIND-Zellen des Ausblicks unverändert vorhanden.
- **AC-11 (E2E):** Given ein Test-Trip auf Staging mit einer Folge-Etappe mit Gewitter und Stundenwerten in allen vier Ampel-Metriken / When die Briefing-Mail an `gregor-test@henemm.com` versendet und per IMAP abgerufen wird / Then enthält der HTML-Part die Ampelpunkte und den ⚡-Badge, und `briefing_mail_validator.py` endet mit Exit 0.
  - Test: Echter Versand über Staging-Scheduler, IMAP-Abruf aus Stalwart-Test-Postfach, `briefing_mail_validator.py` Exit 0.

## Non-Goals

- Keine Änderung an Plain-Text-Mail-Werten (bleiben numerisch).
- Keine Änderung am Monospace-Kompaktgrid (#636) — bleibt numerisch (Emoji-Breite bricht Monospace-Ausrichtung).
- Keine neue Datenquelle für Gewitter-Zeitfenster (nutzt vorhandenen `thunder_token`).
- CAPE, Gewitter-Spalte der Stundentabelle, Temperatur: unverändert.
