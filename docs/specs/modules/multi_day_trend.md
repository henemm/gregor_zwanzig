---
entity_id: multi_day_trend
type: module
created: 2026-02-16
updated: 2026-08-04
status: implementing
version: "5.0"
tags: [weather-metrics, aggregation, trip-reports, trend, email-rendering]
extends: trip_report_scheduler, output_channel_renderers
---

# F3: Multi-Day Trend v4.0 — Spalten-Layout (Issue #561)

## Approval

- [x] Approved (Design: Claude Design, body-561-multiday-trend-email.md · PO-Freigabe: "implement")

## Purpose

Zeigt am Ende des Abend-Briefings (E-Mail, zwischen Gewitter-Vorschau und Highlights)
einen kompakten Block „Nächste Etappen" mit bis zu 3 Folge-Etappen.
Pro Etappe: Wochentag, Etappenname, Temp-Min–Max, Niederschlag, Wind, Gewitter-Ampel.

**v4.0 ersetzt v3.0** (CompactSummary-String-Format) durch ein fluchtend-spaltenbasiertes
Tabellen-Format — klarer scanbar, direkt vergleichbar über Tage.

## Acceptance Criteria

**AC-1:** Given ein Abendbericht für eine aktive Tour / When die Tour mindestens eine weitere
Etappe nach morgen hat / Then enthält der Bericht einen Block „Nächste Etappen" mit bis zu 3
Folge-Etappen (niemals mehr als 3, egal wie viele existieren).

**AC-2:** Given der Trend-Block / Then zeigt jede Etappe in zwei Zeilen: Zeile 1 = Wochentag +
Etappenname; Zeile 2 = fluchtende Spalten Temp (Lo–Hi °C) · Regen (mm oder –) · Wind (Richtung + km/h) ·
Gewitter-Ampel (Farb-Quadrat + Wort: kein/MED/HIGH).

**AC-3 (v5.0, ersetzt v4.0-Fassung — Fix #1486):** Given eine Tour deren letzte Etappe morgen ist
(keine weiteren Etappen nach dem Zieldatum) / When das Briefing gerendert wird / Then erscheint
statt des leeren, kommentarlosen Nichts der Hinweissatz „Keine weiteren Etappen — kein Ausblick."
(neutraler Fließtext, KEIN Warn-/Danger-Styling, KEIN Logging — normaler Tourabschluss ist kein
Fehler). Details, weitere Zustände (außerhalb Vorhersagehorizont / Störung) und die Herleitung:
`docs/specs/modules/fix_1486_outlook_silent_exit.md`.

**AC-4:** Given der Trend-Block / Then stammen die Werte aus echten API-Calls gegen die
konfigurierten Etappen-Koordinaten — keine statischen Demo-Daten.

**AC-5:** Given ein Regen-Wert von 0 mm / Then zeigt die Spalte „–" (ink-4) statt „0 mm".

**AC-6:** Given precip_mm > 1 / Then ist der Wert blau+fett (`#2c5a8c`, font-weight:700).
Given wind_kmh > 30 / Then ist der Wert accent+fett (`#c45a2a`, font-weight:700).

**AC-7:** Given thunder != NONE / Then erscheint ein optionaler Hinweis-Text unter der Metrik-Zeile.

**AC-8:** Given den Plain-Text-Renderer / Then gibt es ein fluchtend-mono Format (Signal/Telegram)
mit `⚡–` / `⚡MED` / `⚡HIGH` als Gewitter-Marker.

## Design-Entscheidungen (Claude Design, 2026-06-02)

| Frage | Entscheidung |
|---|---|
| Spalten oder Fließtext? | Spalten, 2-zeilig je Etappe |
| Abgesetzt oder eingebettet? | Leicht abgesetzt: 2px-Haarlinie + Paper-Tint `#f6f4ee` |
| Heading-Text | „Nächste Etappen" + Eyebrow „05 · Ausblick" |

**Tech-Lead-Flag:** Keine Wetter-Emoji in den fluchtenden Spalten (Mono-Bruch in Outlook/Gmail).
Gewitter = Farb-Quadrat (8×8px) + Wort-Text.

## Datenmodell (Trend-Dict)

```python
{
    "weekday": str,       # "Mo" | "Di" | ...
    "name": str,          # Etappenname
    "temp_lo": int|None,  # Grad C Min
    "temp_hi": int|None,  # Grad C Max
    "precip_mm": float,   # 0.0 zeigt als "-"
    "wind_dir": str,      # "W" | "NE" | ... (Kardinalrichtung)
    "wind_kmh": int,      # Max-Wind km/h
    "thunder": str,       # "NONE" | "MED" | "HIGH"
    "note": str|None,     # Hinweis wenn thunder != NONE oder wind > 40 oder precip > 5
}
```

## Gewitter-Ampel

| thunder | Quadrat-Farbe | Wort | Wort-Farbe | Plain-Text |
|---|---|---|---|---|
| NONE | `#9a958a` | kein | `#6b675c` | `⚡–` |
| MED  | `#c08a1a` | MED  | `#8c3e1a` | `⚡MED` |
| HIGH | `#a83232` | HIGH | `#a83232` | `⚡HIGH` |

## HTML-Struktur (table-only, inline styles)

- Wrapper: `background:#f6f4ee; border-top:2px solid #1a1a18; padding:22px 28px 24px`
- `table-layout:fixed`, Spaltenbreiten: Temp 120px · Regen 84px · Wind 112px · Gewitter rest
- Spaltenköpfe: mono 9px uppercase ink-4, border-bottom `1px solid #d8d3c2`
- Etappen-Trennlinie (außer erste): `border-top:1px solid #e7e2d3`

## Source Changes

| File | Change |
|------|--------|
| `src/services/trip_report_scheduler.py` | `_build_stage_trend()`: aggregate_stage statt CompactSummaryFormatter; max 3; neues Dict-Format; Hilfsfunktionen `_deg_to_compass()` + `_trend_note()` |
| `src/output/renderers/email/html.py` | Neues Spalten-Layout |
| `src/output/renderers/email/plain.py` | Mono-Block-Format für Signal/Telegram |

## Constraints

- C1: Nur `<table>/<div>` + inline styles — kein Grid/Flexbox
- C2: `table-layout:fixed` mit festen Spaltenbreiten
- C3: Max 3 Etappen — hart begrenzt in `_build_stage_trend()`
- C4: Optimiert für 600 px
- C5 (v5.0, ersetzt v4.0-Fassung — Fix #1486): Leerer Trend (0 Etappen, Klasse „keine weiteren
  Etappen") → Block entfällt NICHT mehr komplett, sondern zeigt den Hinweissatz „Keine weiteren
  Etappen — kein Ausblick." (neutral, kein Heading-Wechsel nötig). Details:
  `docs/specs/modules/fix_1486_outlook_silent_exit.md`.
- C6: Plain-Text für Signal/Telegram (Mono, fluchtend)
- C7: Gewitter-Ampel: Farb-Quadrat + Wort, nie Farbe allein
- C8: Keine Wetter-Emoji in den fluchtenden Spalten

## Edge Cases

| Fall | Verhalten |
|------|-----------|
| 0 Etappen | (v5.0, Fix #1486) Hinweissatz „Keine weiteren Etappen — kein Ausblick." statt Block-Entfall — Details: `docs/specs/modules/fix_1486_outlook_silent_exit.md` |
| nur 1 Folge-Etappe | Block mit 1 Zeile |
| > 3 Etappen | auf 3 begrenzen |
| precip_mm == 0 | zeigt `–` in ink-4 |
| thunder NONE für alle | Ampel-Spalte zeigt `▪ kein`, kein Hinweistext |

## Changelog

- 2026-02-16: v1.0 spec (Ankunftsort-only)
- 2026-02-17: v2.0 spec — Stage-basiert, aggregate_stage()
- 2026-02-18: v3.0 spec — CompactSummaryFormatter, Summary-String, 2-Zeilen-Layout
- 2026-06-02: v4.0 spec — Spalten-Layout (Design-Handoff #561), max 3, neue Dict-Struktur
- 2026-08-04 (Fix #1486): v5.0 — AC-3/C5 umgekehrt — PO-Entscheidung, Ausblick benennt seinen
  Zustand statt zu schweigen. Vormals implizite Stille war fünf nicht unterscheidbare stille
  Ausstiege, siehe #1486.
