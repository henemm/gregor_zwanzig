---
entity_id: issue_653_telegram_tier2_timeline
type: module
created: 2026-06-07
updated: 2026-06-07
status: draft
version: "1.0"
tags: [telegram, inbound, query, timeline, tier2, epic-639]
---

# #653 — Telegram Tier-2: Vertikale Timeline je Etappe (Wegpunkt-Mapping)

## Approval

- [ ] Approved (PO 'go')

## Purpose

Formatiert die Extraktor-Daten (#652) als **kompakte vertikale Timeline einer Etappe**
und liefert sie als Telegram-Antwort: pro geplantem Wegpunkt eine Zeile mit
Naismith-Ankunftszeit + Höhe + Wetter-Metriken, emoji-gestützt (sonnentauglich).
Die Antwort trägt **Kontext-Buttons**: Drilldown je kritischer Metrik (→ #654) und
„Zurück" zur Tier-1-Glance. Teil 4/6 von Epic #639 — erfüllt dessen AC-2
(Wegpunkt-genaue Info exakt für Zeiten und Höhen der geplanten Wegpunkte).

## Source

- **File:** `src/services/trip_command_processor.py` (neue Query-Handler `timeline_heute`/`timeline_morgen`, vertikaler Timeline-Formatter, Button-Builder)
- **File:** `src/services/inbound_telegram_reader.py` (Kurzbefehl-Mapping `/th` `/tm`, `_VALID_COMMANDS`-Erweiterung)
- **File:** `src/services/weather_extractor.py` (Datenquelle, #652 — read-only genutzt)
- **Identifier:** `TripCommandProcessor`, `InboundTelegramReader._parse_command`, `CommandResult`

> **Schicht:** Reines Python-Backend (`src/services/`). Kein Go, kein Frontend.
> Der Webhook-Eingang (`api/routers/webhook.py` → `_process_update`) bleibt unverändert;
> Button-**Klick**-Verarbeitung (`callback_query`, `editMessageText`) ist explizit
> NICHT Teil dieses Issues (→ #655). Das **Stunden-Drilldown** hinter den `dd_*`-Buttons
> ist ebenfalls NICHT Teil dieses Issues (→ #654).

## Estimated Scope

- **LoC:** ~120–160 (Timeline-Formatter, 2 Query-Handler, Button-Builder, Kurzbefehl-Mapping; Tests separat)
- **Files:** 2 Source (`trip_command_processor.py`, `inbound_telegram_reader.py`) + Tests
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `WeatherExtractor.timeline(trip_id)` | upstream (#652 ✅) | `TimelinePoint(arrival_time, elevation_m, label, metrics)` pro Segment-Ende = Wegpunkt-Ankunft |
| `CommandResult.reply_markup` | DTO (#651 ✅) | Buttons auf den Draht |
| `TelegramOutput.send(reply_markup=)` | upstream (#650 ✅) | Versand (vom Inbound-Reader durchgereicht) |
| `Trip.get_stage_for_date` / `Stage` | model | Etappen-Auflösung heute/morgen |

## Implementation Details

### 1. Neue read-only Query-Keys

| Query-Key | Bedeutung | Telegram-Kurzbefehl |
|-----------|-----------|---------------------|
| `timeline_heute`  | Vertikale Timeline der **heutigen** Etappe | `/th` |
| `timeline_morgen` | Vertikale Timeline der **morgigen** Etappe | `/tm` |

Langform ebenfalls: `### query: timeline_heute` / `### query: timeline_morgen`.
Beide laufen über den bestehenden read-only Pfad `_handle_query(...)` — **kein**
`save_trip`, **kein** `_append_command_log`, **kein** `_delete_snapshot`.
`_QUERY_KEYS` wird um beide Keys erweitert.

### 2. Vertikaler Timeline-Formatter

Aus `WeatherExtractor.timeline(trip.id)` die `TimelinePoint`s nach
`arrival_time`-Datum auf den Zieltag filtern und **nach `arrival_time` sortiert**
als vertikale Liste rendern — eine Zeile pro Wegpunkt:

```
📋 Timeline · <Stage-Name> (20.08)

🕐 10:00 · 1500 m
   🌡 13–18 °C  💨 22 km/h  🌧 0.0 mm  ⛈ kein
🕐 12:00 · 1500 m
   🌡 18–23 °C  💨 22 km/h  🌧 1.2 mm  ⛈ mäßig
```

- **Zeit:** `arrival_time` als `HH:MM` (Naismith — = `segment.end_time`).
- **Höhe:** `elevation_m` (m). Fehlt sie → ausgelassen.
- **Metriken:** Temperatur (min–max), Wind (max), Niederschlag (Summe), Gewitter
  (`thunder_level_max` → kein/mäßig/hoch). Fehlende Werte → „?" bzw. ausgelassen,
  nie Crash.
- Emoji-gestützt, kompakt (mobil/sonnentauglich).

### 3. Kritische Metrik & Kontext-Buttons (reply_markup)

Eine Metrik gilt für die Etappe als **kritisch**, wenn ihr aggregierter Tageswert
(über die Wegpunkte des Zieltags) eine dokumentierte Schwelle überschreitet:

| Metrik | Kritisch wenn | callback_data |
|--------|---------------|---------------|
| Gewitter | `thunder_level_max` ≥ `MED` | `dd_thunder_<day>` |
| Wind | `wind_max_kmh` ≥ 40 | `dd_wind_<day>` |
| Niederschlag | `pop_max_pct` ≥ 30 **oder** `precip_sum_mm` ≥ 1.0 | `dd_precip_<day>` |

`<day>` ∈ {`today`, `tomorrow`} (passend zum angefragten Tag — wird von #654/#655
zum Drilldown aufgelöst).

`reply_markup` enthält:
- je **kritischer** Metrik einen Drilldown-Button `{text:"🔍 <Metrik>", callback_data:"dd_<metric>_<day>"}`,
- **immer** einen „Zurück"-Button `{text:"⬅️ Zurück", callback_data:"glance"}`.

Gibt es keine kritische Metrik, enthält `reply_markup` nur den „Zurück"-Button.

### 4. Kurzbefehl-Mapping (inbound_telegram_reader)

`_SHORTCUT_MAP` um `/th → timeline_heute`, `/tm → timeline_morgen` erweitern;
`_VALID_COMMANDS` um beide Query-Keys ergänzen. Langform und nackte Query-Keys
werden über den bestehenden `_QUERY_KEYS`-Pfad als `### query: <key>` kodiert.

## Expected Behavior

- **Input:** Telegram-Text `/th`, `/tm` (oder `### query: timeline_heute` etc.).
- **Output:** Mehrzeilige vertikale Timeline-Textantwort + `reply_markup` mit
  Drilldown-Buttons (je kritischer Metrik) und „Zurück".
- **Side effects:** **KEINE** — kein Trip-Save, kein `command_log.json`-Eintrag,
  keine Snapshot-Löschung.

## Acceptance Criteria

**AC-1 (= #639 AC-2):** Given ein Nutzer fordert die Timeline einer Etappe an
(`### query: timeline_heute` bzw. `/th`), When der Bot antwortet, Then listet die
Antwort **pro geplantem Wegpunkt dieser Etappe** eine eigene Zeile mit der
Naismith-Ankunftszeit (`HH:MM` aus `segment.end_time`), der Höhe (m) und den
Wetter-Metriken — und zwar exakt für die Wegpunkte/Zeiten **dieses** Tages
(Werte anderer Tage tauchen nicht auf).
  - Test: Snapshot mit 2 Heute-Segmenten (Ende 10:00 @1500 m, max 18 °C; 12:00 @1500 m,
    max 23 °C) + 1 Morgen-Segment (max 11 °C) via echtem `WeatherSnapshotService.save`
    (kein Mock). `### query: timeline_heute` → Body enthält „10:00", „12:00", „18", „23"
    und ist mehrzeilig (≥ 2 Wegpunkt-Zeilen); „11" (Morgen-Wert) kommt NICHT vor.

**AC-2:** Given die Timeline-Antwort einer Etappe mit mindestens einer kritischen
Metrik, When der Bot antwortet, Then enthält `reply_markup.inline_keyboard` einen
Drilldown-Button je kritischer Metrik (`callback_data` beginnt mit `dd_`) **und**
einen „Zurück"-Button (`callback_data == "glance"`).
  - Test: Snapshot mit `thunder_level_max=HIGH` heute → `### query: timeline_heute`:
    mindestens ein Button mit Text der „Gewitter" enthält und `callback_data`
    `dd_thunder_today`; genau ein Button mit Text der „Zurück" enthält und
    `callback_data` `glance`.

**AC-3:** Given irgendeine Timeline-Abfrage (`/th /tm`), When sie verarbeitet wird,
Then bleibt der Trip-Zustand unverändert: kein neuer Eintrag in `command_log.json`
und keine Etappen-Datumsverschiebung (read-only, wie #651).
  - Test: vor/nach Verarbeitung alle `stage.date`-Werte identisch und
    `command_log.json` existiert nicht (echte Datei-I/O gegen `tmp_path`).

**AC-4:** Given `/tm` bzw. `timeline_morgen`, When verarbeitet, Then bezieht sich die
Timeline ausschließlich auf die **morgige** Etappe (heutige Werte tauchen nicht auf).
  - Test: `### query: timeline_morgen` → Body nennt den Morgen-Wert „11"; der
    Heute-Maximalwert „23" kommt NICHT vor.

**AC-5:** Given die Timeline-Kurzbefehle treffen über den Telegram-Inbound-Pfad ein,
When `_parse_command` sie verarbeitet, Then werden `/th`/`/tm` korrekt auf
`timeline_heute`/`timeline_morgen` gemappt (kein „Unbekannter Befehl"); der
bestehende verändernde Pfad (`ruhetag 2`) bleibt grün.
  - Test: `InboundTelegramReader._parse_command("/th")` → `("timeline_heute", None)`;
    `("/tm")` → `("timeline_morgen", None)`; `("ruhetag 2")` → `("ruhetag", "2")`.

**AC-6:** Given keine geplante Etappe für den Zieltag **oder** kein Wetter-Snapshot,
When eine Timeline angefragt wird, Then antwortet der Bot mit einem klaren
Hinweistext (kein Crash, kein leerer Body) und `reply_markup` enthält mindestens den
„Zurück"-Button.
  - Test: (a) kein `save` → `timeline_heute`-Body enthält Hinweis
    („kein Snapshot"/„keine Wetterdaten"/„keine Etappe"); `reply_markup` mit
    „Zurück"-Button vorhanden. (b) Snapshot vorhanden, aber kein Segment am Zieltag →
    Body nennt „Keine Etappe geplant", kein Crash.

## Non-Goals (explizit ausgeschlossen)

- **Button-Klick-Verarbeitung** (`callback_query`, `editMessageText`, Verdrahtung der
  bestehenden Glance-Buttons `tl_today`/`tl_tomorrow`) → #655.
- **Tier-3 Drilldown-Rendering** (stündliche Einzelmetrik hinter `dd_*`) → #654.
- Änderung des Email-`### status`-Verhaltens (bleibt Etappenliste).
- Speichern von Waypoint-Namen im Snapshot (Snapshot trägt nur `segment_id`; Zeile
  wird über Zeit + Höhe identifiziert).
