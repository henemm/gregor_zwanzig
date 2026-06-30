---
entity_id: issue_917_alert_renderer
type: module
created: 2026-06-30
updated: 2026-06-30
status: draft
version: "1.0"
tags: [alert, renderer, sms, email, telegram, epic-914]
---

# Alert-Renderer — kanonischer Backend-Renderer (Betreff · Email · Telegram · SMS)

## Approval

- [ ] Approved

## Purpose

Vier reine Renderer, die einen ausgelösten Abweichungs-Alert generisch über die
Metrik-Registry in **Betreff · Email · Telegram · SMS** projizieren. Sie machen die
in #914 spezifizierten Formate sichtbar (informativer Betreff, Pfeil/Δ%/Schwellseite,
km-Spanne, severity-Sortierung, SMS-Token mit `+k`-Überlauf) und lösen die heute
verstreute Alert-Formatierung durch **eine** kanonische Quelle ab (ADR-0011).

## Source

- **File:** `src/output/renderers/alert/model.py` (CREATE) — `AlertEvent`, `AlertMessage`, reine Helfer
- **File:** `src/output/renderers/alert/project.py` (CREATE) — `to_alert_message(...)` Projektion
- **File:** `src/output/renderers/alert/render.py` (CREATE) — `render_subject/email/telegram/sms`
- **File:** `src/services/trip_alert.py` (MODIFY) — `_send_alert` auf neuen Renderer umstellen
- **File:** `src/services/weather_change_detection.py` (MODIFY, ~Z.519) — F003-RESIDUAL härten
- **File:** `src/app/metric_catalog.py` (MODIFY) — Temperatur-`sms_code` `T/TN` → `D/N`; ggf. `get_metric_id_for_field`-Helfer
- **File:** `src/output/renderers/email/alert_compact.py` (DELETE) — ersetzt
- **Identifier:** `to_alert_message`, `render_subject`, `render_email`, `render_telegram`, `render_sms`

Schicht: **Python-Backend** (`src/`). Kein Go, kein Frontend (Live-Vorschau = Slice 3).

## Estimated Scope

- **LoC:** ~235 Produktiv-neu (model ~70 · project ~55 · render ~110 · Integration/Härtung ~12 · Katalog ~6; DELETE −89). Knapp am Limit 250.
- **Files:** 7 (3 CREATE, 3 MODIFY, 1 DELETE)
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/metric_catalog.py` | upstream | Single Source: `get_sms_code`/`get_cmp`/`get_decimals`/`format_metric_value`; `summary_fields`-Map (field→metric_id) |
| `src/app/models.py` `WeatherChange` | upstream | Event-Quelle (metric=summary_field, old/new_value, delta, threshold, severity, direction, segment_id, occurred_at) |
| Segment-Geometrie (`segment.start_point/end_point.distance_from_start_km`) | upstream | km_from/km_to pro Event |
| `src/services/trip_alert.py` `_send_alert` | downstream | Versand Email+Telegram (SMS-Versand bleibt out-of-scope) |
| Renderer-Mail-Gate (`renderer_mail_gate.py`, Matrix-Test, Validator) | gate | Commit-Voraussetzung wegen Lösch-/Mail-Inhalts-Berührung |

## Implementation Details

### Datenmodell (kanonisch, ADR-0011)
```
@dataclass(frozen=True)
class AlertEvent:
    metric_id: str          # catalog metric_id (NICHT summary_field)
    value_from: float
    value_to: float
    threshold: float
    cmp: str                # "über"|"unter" — aus Katalog je metric_id
    occurred_at: str | None # "HH:MM"
    km_from: float
    km_to: float

@dataclass(frozen=True)
class AlertMessage:
    trip_short: str
    stand_at: str           # "HH:MM"
    events: tuple[AlertEvent, ...]   # ≥1
    source: str | None = None        # RESERVIERT für Radar-Konvergenz (#919); bei Deviation stets None
```

### Einmalige reine Helfer (auf AlertEvent)
```
direction(e)  = "up" if e.value_to >= e.value_from else "down"
arrow(e)      = "↑" if direction(e)=="up" else "↓"        # Unicode NUR Email/Telegram
delta_pct(e)  = round((e.value_to - e.value_from)/e.value_from*100)   # value_from==0 → Sonderfall: kein %/abgesichert
over_thr(e)   = e.value_to > e.threshold if e.cmp=="über" else e.value_to < e.threshold
side_label(e) = "über" if over_thr(e) else "unter"
severity(e)   = (e.value_to-e.threshold)/e.threshold if e.cmp=="über" else (e.threshold-e.value_to)/e.threshold
km_span(evs)  = (min(km_from), max(km_to))               # Union über alle Events
```
Sortierung der Events: `severity(e)` absteigend. Wert-Formatierung: `format_metric_value`
+ `get_decimals(metric_id)`. Kürzel: `get_sms_code(metric_id)`.

### Projektion `to_alert_message(changes, segments, trip_name, *, tz, stand_at)`
- field→metric_id via Reverse-Lookup über `_METRICS[].summary_fields`. **Disambiguierung** bei mehrdeutigem Feld (`temp_min_c` → `temperature` *und* `temperature_cold`): die Katalog-`cmp` muss zur `WeatherChange.direction` passen (decrease/Kältealarm → `temperature_cold` cmp="unter"). Kein stiller Fallback — unbekanntes Feld/leeres `cmp` → definierter Fehler.
- km aus `segment.start_point/end_point.distance_from_start_km` des per `segment_id` referenzierten Segments.
- `occurred_at` aus `WeatherChange.occurred_at` durchreichen.

### Renderer-Formate (aus #914)
**Betreff** (Reihenfolge fest Trip·km·Richtung·Metrik):
```
1 Event: [<trip>] km <a>–<b> · <arrow> <Kürzel>: <from>→<to>
≥2:      [<trip>] km <a>–<b> · <arrow> <N> über Schwelle: <K1> <to1>, <K2> <to2>, <K3> <to3>   (Top-3)
```
**Email** — H1 faktisch/generisch (KEINE abgeleiteten Wörter wie „halbiert"):
```
1 Event: <Kürzel> <delta_pct> seit dem Briefing
≥2:      <N> Werte über der Alarm-Schwelle
Datenblock (1 Zeile/Event, severity-sortiert): <Kürzel> · Schwelle <thr> <einheit>   <from> <arrow> <to> <einheit>  [über|unter]
Pfeil rot wenn over_thr, sonst grün (kodiert Schwellseite, nicht gut/schlecht).
Fußzeile: Stand: heute <stand_at> · verglichen mit dem letzten Briefing · km <a>–<b>
Kein Freitext „Was heißt das", keine Empfehlung.
```
**Telegram** — fette erste Zeile = Verdikt-Reihenfolge wie Betreff, Unicode-Pfeile, Datenblock wie Email-Plain.
**SMS** — ASCII/GSM-7, ≤140 Zeichen:
```
<trip-kompakt> km<a>-<b>: <sign><CODE><to>[%][@<hh>] <sign><CODE><to>[%][@<hh>] … [ +k]
sign = "+" wenn direction up sonst "-". Token severity-sortiert. Bei Längenüberlauf:
weglassen + Zähler " +k" anhängen (k = Anzahl weggelassener Tokens).
```

### Erweiterbarkeit pro Ereignis-Art (Vorsorge für #919)
Die Renderer erzeugen die Ereignis-Zeilen **pro Ereignis-Art**, statt „immer Abweichung"
anzunehmen. In #917 existiert nur die Art **Deviation** (`AlertEvent` mit value_from/to/
threshold/cmp). #919 ergänzt **additiv** eine zweite Art **Onset** (Radar-Nowcast) +
einen Render-Zweig; `AlertMessage.events` wird dafür auf eine Typ-Union erweitert. Die
gemeinsame Hülle (trip_short, stand_at, km_span, `source`, Vier-Kanal-Struktur,
SMS-Längenbudget) bleibt unverändert — die Konvergenz ist rein additiv, ohne Bruch der
Deviation-Darstellung.

### Integration `_send_alert`
Einmal `msg = to_alert_message(changes, weather, trip.name, tz=alert_tz, stand_at=…)`,
dann `subject = render_subject(msg)`, `html, plain = render_email(msg)`,
Telegram `body = render_telegram(msg)`. `render_sms` wird **gebaut + Fixture-getestet**,
aber **nicht** verdrahtet (`known_channels` bleibt `{email, telegram}`).

### F003-RESIDUAL
`weather_change_detection.py:519`: `_ALERT_METRIC_COMPARISON.get(rule.metric, "above")`
→ `_ALERT_METRIC_COMPARISON[rule.metric]` (KeyError-on-miss) — kein stiller `"above"`-Fallback.

## Expected Behavior

- **Input:** `changes: list[WeatherChange]`, `segments: list[SegmentWeatherData]`, `trip_name`, `tz`, `stand_at`.
- **Output:** vier Kanal-Strings (Email zusätzlich HTML), generisch aus Registry abgeleitet.
- **Side effects:** keine im Renderer (rein); Versand in `_send_alert` wie bisher (best-effort Email/Telegram).

## Acceptance Criteria

- **AC-1:** Given WeatherChange-Events (Metrik als summary_field, mit Segmenten) / When `to_alert_message(...)` aufgerufen wird / Then entsteht ein `AlertMessage`, in dem jedes Event die **catalog metric_id** (korrekt disambiguiert: `temp_min_c`+decrease → `temperature_cold`), die Katalog-`cmp`, `km_from/km_to` aus der Segment-Geometrie und `occurred_at` trägt; `source` ist `None`.
  - Test: Projektion mit echten WeatherChange/Segment-Fixtures bauen, Felder des AlertEvent prüfen (metric_id, cmp, km_from/km_to, occurred_at) + `source is None`.

- **AC-2:** Given ein AlertMessage mit 1 bzw. 3 Events / When `render_subject(msg)` aufgerufen wird / Then folgt der Betreff exakt der Reihenfolge Trip·km·Richtung·Metrik im 1-Event- bzw. „N über Schwelle: Top-3"-Format aus #914.
  - Test: `render_subject` für 1-Event- und 3-Event-Message; erwartete Strings (km-Spanne, Pfeil, Kürzel, Werte) assertieren.

- **AC-3:** Given ein AlertMessage mit mehreren Events / When `render_email(msg)` aufgerufen wird / Then ist die H1 faktisch-generisch (keine Deutungs-Wörter), der Datenblock nach `severity` absteigend sortiert, die Pfeilfarbe rot gdw. `over_thr` (sonst grün), die Fußzeile enthält Stand + km-Spanne, und es gibt **keinen** Empfehlungs-/Erklärsatz.
  - Test: `render_email` rendern; H1-Text, Zeilen-Reihenfolge nach severity, Farb-Attribut an `over_thr` gekoppelt, Fußzeile, Abwesenheit von Empfehlungstext prüfen.

- **AC-4:** Given ein AlertMessage / When `render_telegram(msg)` aufgerufen wird / Then beginnt die Nachricht mit einer fetten ersten Zeile in derselben Verdikt-Reihenfolge wie der Betreff, nutzt Unicode-Pfeile und listet je Event eine Datenzeile.
  - Test: `render_telegram` rendern; fette erste Zeile, Unicode-Pfeil, Event-Zeilen assertieren.

- **AC-5:** Given ein AlertMessage mit mehr Events als ins Längenbudget passen / When `render_sms(msg)` aufgerufen wird / Then ist die Ausgabe rein ASCII/GSM-7, ≤140 Zeichen, Tokens severity-sortiert im Format `<sign><CODE><to>[%][@hh]`, und weggelassene Tokens erscheinen als ` +k`.
  - Test: Property-Test — `result.isascii()`, `len(result) <= 140`, erwartete Tokens vorhanden, Überlauf erzeugt korrektes ` +k`.

- **AC-6:** Given die Metrik-Registry / When `get_sms_code("temperature")` bzw. `get_sms_code("temperature_cold")` aufgerufen wird / Then liefert sie `"D"` (Tageshoch) bzw. `"N"` (Nachttief), und alle `sms_code` bleiben global eindeutig + ASCII.
  - Test: `get_sms_code` für beide IDs assertieren; Eindeutigkeits-/ASCII-Invariante über alle Metriken prüfen (Slice-1-Test bleibt grün).

- **AC-7:** Given ein Trip mit erkannten Abweichungen und konfiguriertem Email-Kanal / When der Alert-Versand (`_send_alert`) läuft / Then trägt die zugestellte Nachricht den **dynamischen** Betreff und den neuen E-Mail-/Telegram-Inhalt des kanonischen Renderers (nicht den alten statischen Betreff / `alert_compact`-Body).
  - Test: Versandpfad gegen echte Staging-Mail (Stalwart-Postfach) auslösen, Betreff + Body-Plausibilität gegen das neue Format prüfen (kein Mock).

- **AC-8:** Given eine Absolut-Regel mit einer Metrik ohne Eintrag in `_ALERT_METRIC_COMPARISON` / When der Detector die Vergleichsrichtung bestimmt / Then wird ein `KeyError` ausgelöst (kein stiller `"above"`-Fallback).
  - Test: Detector mit unbekannter/nicht-gemappter Metrik aufrufen und `KeyError` (statt stillem „above") nachweisen.

- **AC-9:** Given der Briefing-SMS-Pfad (`SMS_SYMBOL_BY_METRIC`, Token-Builder) / When dieser Slice gebaut ist / Then sind die stehenden Briefing-Kürzel (`TH:`, `TH+`, `SFL`, …) unverändert und die bestehenden Briefing-SMS-Tests bleiben grün.
  - Test: `SMS_SYMBOL_BY_METRIC["thunder"] == "TH:"` (unverändert); `tests/tdd/test_issue_624_metric_thresholds.py` + `test_issue_872_threshold_ux.py` laufen grün.

## Known Limitations

- **SMS-Versand bleibt out-of-scope:** `render_sms` wird gebaut + Fixture-getestet, aber nicht zugestellt (`known_channels={email,telegram}`).
- **Radar-/Nowcast-Alert** bleibt vorerst auf eigenem Pfad (`outputs/radar_alert.py`); Konvergenz auf diesen Renderer inkl. Quelle-Zeile = Folge-Issue **#919**. Das `source`-Feld ist dafür reserviert, wird hier aber nicht befüllt/gerendert.
- **`delta_pct` bei `value_from == 0`:** kein sinnvoller Prozentwert → definierter Sonderfall (kein `%`, kein Crash).
- **Briefing-SMS-Konsolidierung** (ADR-0011 Ziel-3) bleibt für den Briefing-Pfad bewusst offen (PO: „stehende Kürzel sind Gesetz").

## Onset-Format (dokumentiertes Ziel für #919 — in #917 NICHT implementiert)

Festgehalten als Vorlage, damit die Radar-Konvergenz (#919) eine fertige Format-Vorgabe
hat. Wortwahl aus dem heutigen Radar-Pfad übernommen, im #914-Stil (faktisch, keine
Deutung). `<m>` = Minuten bis Onset, `<hh:mm>` = Onset-Uhrzeit, Quelle nur Email/Telegram.

```
BETREFF
  Regen:    [<trip>] km <a>–<b> · Regen in <m> Min
  Gewitter: [<trip>] km <a>–<b> · Gewitter in <m> Min      (convective: is_convective=True)

E-MAIL
  H1:       Regen in <m> Min        (convective: Gewitter in <m> Min)
  Zeile:    km <a>–<b> · Regen ab <hh:mm>
  Fußzeile: Stand: heute <stand_at> · km <a>–<b> · Quelle: <source-Label>
  (kein Empfehlungssatz)

TELEGRAM
  <trip> · km <a>–<b> · Regen in <m> Min       ← fett
  Regen ab <hh:mm>, im Briefing nicht angekündigt | jetzt akut
  Quelle: <source-Label>

SMS  (ASCII/GSM-7, ≤140)
  <trip-kompakt> km<a>-<b>: <CODE>!<m>
  Onset-Token = <CODE>!<m>  — "!" markiert "akut/Onset", <m> = Minuten bis Onset.
  Beispiele: Regen → R!15 · Gewitter → TH!15
  Kollisionsfrei zum Deviation-Token (<sign><CODE><wert>); Quelle in SMS NICHT.
```

Offen für #919: Convective-Kennzeichnung im SMS-Token (z.B. `TH!15` reicht, da `TH` =
Gewitter); finale Quelle-Labels via `radar_service.source_label`.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0011 (bestehend) + Präzisierungs-Notiz
- **Rationale:** Umsetzung von ADR-0011 (ein Backend-Renderer, Registry als Single Source). **Präzisierung (PO 2026-06-30):** ADR-0011 Ziel-3 („doppelte Mappings entfernen") gilt für den **Alert-`sms_code`**, **nicht** für die Briefing-SMS-Token-Grammatik (`SMS_SYMBOL_BY_METRIC` mit `:`/`+`-Suffixen) — diese ist eine bewusst getrennte Verantwortung und bleibt unangetastet. Zudem: `AlertMessage` ist **kanonisch** (nicht deviation-only), mit reserviertem `source`-Feld, damit der Radar-Pfad (#919) ohne Modell-Bruch konvergieren kann. ADR-0011 erhält eine entsprechende Konsequenz-Notiz.

## Changelog

- 2026-06-30: Initial spec created (Slice 2 zu #914; PO-Entscheidungen N/D, kein Briefing-Dedup, kanonischer Renderer + Radar-Folge-Issue #919)
- 2026-06-30: Onset-Format (4 Kanäle inkl. SMS-Token `R!15`) als dokumentiertes Ziel für #919 ergänzt + Erweiterbarkeits-Vorsorge pro Ereignis-Art (PO-Wunsch)
