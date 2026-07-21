---
entity_id: issue_640_trend_threshold_times
type: module
created: 2026-06-07
updated: 2026-06-07
status: draft
version: "1.0"
tags: [reports, trend, telegram, email, sms, thresholds, timing]
---

# #640 Mehrtages-Trend: Schwellwert-Zeiten (erste Überschreitung @ + Peak @)

## Approval

- [ ] Approved

## Purpose

Im Mehrtages-Trend pro threshold-Metrik die Zeiten ergänzen: wann der Schwellwert
erstmals überschritten wird und wann das Maximum liegt — `{erst}@{Std}({Peak}@{Std})`.
INLINE in der Hauptzeile, je Kanal angepasst; die `↳`-Hinweiszeile bleibt kompakt.
Wiederverwendet die bestehende SMS-Mechanik (`render_threshold_peak_value`, #624).

## Source

- **File:** `src/services/trip_report_scheduler.py` (`_build_stage_trend` — Stundenwerte
  je Folge-Etappe durchreichen statt wegaggregieren), `src/output/renderers/email/helpers.py`
  (`format_trend_tokens`), `narrow.py`/`html.py`/`sms_trip.py` (Trend-Render je Kanal).
- **Identifier:** Trend-Zeit-Tokens via `render_threshold_peak_value`.

## Estimated Scope

- **LoC:** ~150 produktiv
- **Files:** trip_report_scheduler.py, helpers.py, narrow.py, html.py, sms_trip.py, Tests
- **Effort:** medium

## Datengrundlage

`_build_stage_trend` holt pro Folge-Etappe bereits das volle Stundenwetter (`seg_weather`)
und aggregiert es via `aggregate_stage` weg. Für #640 werden daraus je threshold-Metrik
Stundenproben (`HourlyValue`: value + lokale Stunde) gebildet und an
`render_threshold_peak_value(symbol, samples, threshold, is_level=)` übergeben. **Kein
zusätzlicher API-Call.**

## Schwellwerte

Pro Metrik: `MetricConfig.sms_threshold` (#624) wenn gesetzt, sonst Default:
Regen ≥ 0,5 mm · Regenwahrsch. ≥ 50 % · Wind ≥ 30 km/h · Böe ≥ 50 km/h · Gewitter ≥ MED.
Temperatur bleibt Spanne (`12–15°C`), KEIN @ (kein Schwellwert-Konzept).

## Format je Kanal (Soll)

**Telegram (Hauptzeile inline; ↳ kompakt):**
```
Di  12–15°C  R0.5@10(6@15)  W17@16  ⚡MID@14(HIGH@16)
    ↳ Gewitter möglich
```
Trockener Tag bleibt kompakt: `Mo  12–15°C  R–  W12  ⚡–` (kein @ wenn Schwelle nie überschritten).

**E-Mail (Trend-Tabelle, @ in den Zellen; Hinweiszeile kompakt):**
| Temp | Regen | Wind | Gewitter |
|------|-------|------|----------|
| 12–15°C | 0,5@10 (6@15) | 17@16 | MID@14 (HIGH@16) |

**SMS-Trend (längenkritisch, knapp adaptiert):** nur Peak@Std, kein Erst-Wert:
`Di 12-15 R6@15 W17@16 GEW-HIGH@16`

## Acceptance Criteria

**AC-1:** Given eine Folge-Etappe mit Stundenwetter, When der Trend gebaut wird, Then
liefert er je threshold-Metrik (Regen/Wind/Böe/Gewitter) ein Zeit-Token nach
`render_threshold_peak_value`: `{erst}@{Std}` bzw. `{erst}@{Std}({Peak}@{Std})`,
Stunden-granular (lokale Zeit), aus den bereits geholten Stundenwerten — ohne
zusätzlichen Wetter-Abruf.

**AC-2:** Given ein Schwellwert, When er bestimmt wird, Then gilt
`MetricConfig.sms_threshold` (falls gesetzt), sonst der Default je Metrik
(Regen 0,5 mm · Wind 30 · Böe 50 · Gewitter MED).

**AC-3:** Given der Telegram-Trend, When eine Etappe Schwellwert-Überschreitungen hat,
Then erscheinen die @-Zeiten INLINE in der Hauptzeile (Regen/Wind/Gewitter); die
`↳`-Hinweiszeile bleibt kompakt (Worte, keine wiederholten Zeiten). Temp bleibt Spanne.

**AC-4:** Given der Telegram-Trend, When eine Metrik den Schwellwert NIE überschreitet,
Then bleibt sie kompakt (`R–` / einfacher Wert), kein `@`.

**AC-5:** Given der E-Mail-Trend, When er gerendert wird, Then stehen die @-Zeiten in
den jeweiligen Zellen (Regen/Wind/Gewitter); die optionale Hinweiszeile bleibt kompakt.

**AC-6:** Given der SMS-Trend, When er gerendert wird, Then zeigt er knapp `{Peak}@{Std}`
(nur Peak, kein Erst-Wert), und die Gesamt-SMS überschreitet das Längenlimit nicht.

**AC-7:** Given die Zeit-Tokens, When sie über alle Kanäle erzeugt werden, Then stammen
sie aus EINER gemeinsamen Quelle (Erweiterung von `format_trend_tokens` bzw. der
Trend-Dict-Felder) — kein Kanal berechnet Erst/Peak/Schwelle selbst nach.

**AC-8:** Given E-Mail-Haupttabelle, SMS-Hauptbericht und der Mehrtages-Trend-Kopf,
When #640 umgesetzt ist, Then sind sie unverändert; nur die Trend-Werte gewinnen die
@-Zeiten.

**AC-9:** Given Telegram-Klartext (proportional), When eine Trend-Hauptzeile mit @-Zeiten
lang wird, Then bricht sie höchstens am `_TG_PROSE_WIDTH`-Limit sauber um (kein
erzwungener Mitten-im-Wort-Umbruch); Format bleibt so kompakt wie möglich.

## Edge Cases

| Fall | Verhalten |
|------|-----------|
| Metrik überschreitet Schwelle nie | kompakter Wert/`–`, kein @ |
| erst == peak (eine Stunde) | nur `{wert}@{Std}` (kein Klammer-Teil) |
| keine Stundenwerte (nur Aggregat) | Fallback: bisheriger Aggregat-Wert ohne @ |
| Gewitter NONE durchgehend | `⚡–`, kein @ |
| SMS zu lang trotz Peak-only | bestehende SMS-Kürzungslogik greift |

## Out of Scope

- Minuten-Granularität (`@15:30`) — nur volle Stunden.
- @-Zeiten im E-Mail-Haupt-Stundenteil / SMS-Hauptbericht (haben bereits Stundenbezug).
- Temperatur-@ (bleibt Spanne).

## Test-Strategie (mock-frei)

- Trend-Dict-Bau: echte Stundenwerte rein → Token `{erst}@{h}({peak}@{h})` raus
  (über `render_threshold_peak_value`), inkl. erst==peak und „nie überschritten".
- Pro Kanal: echte Renderer-Aufrufe mit Trend-Dict → Assertion auf @-Tokens in
  Telegram-Hauptzeile / E-Mail-Zelle / SMS-Peak-only; ↳ kompakt; Temp ohne @.
- Gegenproben: E-Mail-Haupttabelle/SMS-Hauptbericht/Trend-Kopf unverändert.
