---
entity_id: issue_704_telegram_interactive_navigation
type: module
created: 2026-06-10
updated: 2026-06-10
status: draft
version: "1.0"
tags: [telegram, navigation, drilldown, nowcast, interactive]
---

# Telegram: Interaktive Stunden-Navigation + 2h-Nowcast (Issue #704)

## Approval

- [ ] Approved

## Purpose

Drei Erweiterungen am Telegram-Bot, die den Weg zu stündlichen Wetterdaten und zum Nowcast von 3 Schritten auf 1 reduzieren: (1) `/now` als sichtbarer Menübefehl, (2) Inline-Buttons direkt auf `/heute`/`/morgen`, (3) neue stündliche Kompakttabelle `dd_hours_today/tomorrow`.

## Source

- **Dateien:** `src/services/trip_command_processor.py`, `src/services/inbound_telegram_reader.py`, `src/outputs/telegram.py`
- **Schicht:** Python-Backend

## Estimated Scope

- **LoC:** ~150
- **Files:** 3
- **Effort:** low

## Dependencies

- `WeatherExtractor.drilldown(trip_id, metric, from_time, hours)` — liefert stündliche Punkte für `t2m_c`, `wind10m_kmh`, `precip_1h_mm`, `thunder_level`
- `RadarNowcastService.get_nowcast(lat, lon)` + `format_now_text(result)` — bereits fertig
- `TelegramOutput.send(reply_markup=)` + `edit_message_text()` — bereits fertig
- Lifespan-Hook `set_my_commands()` — wird beim Staging-/Prod-Service-Start automatisch aufgerufen

## Slice-Übersicht

### Slice 3 — `/now` als Menübefehl (~30 LoC)

`now` existiert als interner Befehl (`_VALID_COMMANDS`, `_show_now()`), ist aber nicht im Menü sichtbar und hat keinen Aktualisieren-Button.

**Änderungen:**
- `src/outputs/telegram.py`: `BOT_COMMANDS` + Eintrag `{"command": "now", "description": "🌂 Nowcast — Regen/Gewitter in den nächsten 2h"}`
- `src/services/inbound_telegram_reader.py`: `_SHORTCUT_MAP` + `/now` → `now`, `/n` → `now`; `_VALID_COMMANDS` + `"now"`; `_CALLBACK_QUERY_MAP` + `"now": "### now"`
- `src/services/trip_command_processor.py`: `_show_now()` bekommt `reply_markup` mit Aktualisieren-Button `{"text": "🔄 Aktualisieren", "callback_data": "now"}`

### Slice 1 — Buttons auf `/heute` und `/morgen` (~40 LoC)

`_handle_query` liefert für `heute`/`morgen` kein `reply_markup` — die Befehle sind Sackgassen.

**Änderungen:**
- `src/services/trip_command_processor.py`: Neue Konstante `_HEUTE_BUTTONS_TODAY` / `_MORGEN_BUTTONS_TOMORROW` mit 3 Zeilen:
  - Zeile 1: `⏱ Stunden`, `⛈ Gewitter`, `💨 Wind`, `🌧 Regen`
  - Zeile 2: `🕐 Timeline`
  - `dd_hours_today` / `dd_thunder_today` / `dd_wind_today` / `dd_precip_today` als callback_data
- `_handle_query` bei `heute`: `reply_markup=_HEUTE_BUTTONS_TODAY`
- `_handle_query` bei `morgen`: `reply_markup=_MORGEN_BUTTONS_TOMORROW`

**Wichtig:** `dd_thunder/wind/precip_today/tomorrow` sind bereits implementiert und funktionsfähig — nur der Einstiegsweg fehlt.

### Slice 2 — Stündliche Kompaktansicht `dd_hours_*` (~80 LoC)

Neue Drilldown-Ansicht die 4 Metriken pro Stunde in einer Zeile kombiniert.

**Format (Monospace):**
```
📅 Stunden · Heute (10.06)

Zeit  Temp    Wind    Regen  ⛈
08   17–19°C  22km/h  0.0mm  —
09   19–21°C  25km/h  0.0mm  —
10   21–22°C  28km/h  0.2mm  🟡
11   20–21°C  35km/h  1.2mm  🔴
12   18–20°C  30km/h  0.8mm  🟡
```

**Änderungen:**
- `src/services/inbound_telegram_reader.py`: `_CALLBACK_DRILLDOWN_PATTERN` um `hours` erweitern ODER neuen Map-Eintrag in `_CALLBACK_QUERY_MAP`: `"dd_hours_today": "### dd_hours_today"`, `"dd_hours_tomorrow": "### dd_hours_tomorrow"` — und `_process_callback_query` entsprechend dispatchen
- `src/services/trip_command_processor.py`:
  - `_DRILLDOWN_PATTERN` oder neues `_HOURS_PATTERN = re.compile(r"^dd_hours_(today|tomorrow)$")`
  - Neue Methode `_handle_hours_drilldown(trip, day_token, received_at, user_id)`:
    - Ruft `WeatherExtractor.drilldown()` für `t2m_c`, `wind10m_kmh`, `precip_1h_mm`, `thunder_level` ab
    - Aligned-Monospace-Tabelle (feste Spaltenbreite)
    - Zeitfenster: today = jetzt + 12h, tomorrow = 00:00 + 24h
  - Button: `⬅️ /heute` (→ `### query: heute`) oder `⬅️ /morgen`

**Hinweis Temp-Feld:** `ForecastDataPoint.t2m_c` ist ein Einzelwert (keine Min/Max). Für die Tabelle: `drilldown(field="t2m_c")` → Wert als `{val:.0f}°C` darstellen (kein Min-Max-Bereich).

## Acceptance Criteria

**AC-1:** Given `/now` gesendet, When kein aktiver Trip oder kein Provider verfügbar, Then Fehlertext ohne Absturz — kein Stack-Trace.

**AC-2:** Given `/now` gesendet mit aktiver Etappe, When Nowcast erfolgreich, Then Antwort enthält Onset-Timing oder "Kein Niederschlag" und einen `🔄 Aktualisieren`-Button.

**AC-3:** Given `🔄 Aktualisieren`-Button geklickt, When Callback `now` empfangen, Then Nachricht wird in-place ersetzt (editMessageText) mit frischen Nowcast-Daten.

**AC-4:** Given `/heute` gesendet, When Antwort kommt, Then enthält sie mindestens 2 Zeilen Inline-Buttons mit `⏱ Stunden`, `⛈ Gewitter`, `💨 Wind`, `🌧 Regen` in Zeile 1 und `🕐 Timeline` in Zeile 2.

**AC-5:** Given `/morgen` gesendet, When Antwort kommt, Then enthält sie dieselben Buttons mit `_tomorrow`-Varianten als callback_data.

**AC-6:** Given `⛈ Gewitter`-Button auf `/heute` geklickt, When Callback `dd_thunder_today` empfangen, Then erscheint die bereits funktionierende stündliche Gewitter-Liste (kein neuer Code — Regression-Check).

**AC-7:** Given `⏱ Stunden`-Button auf `/heute` geklickt (Callback `dd_hours_today`), When Snapshot vorhanden, Then erscheint Monospace-Tabelle mit Spalten Zeit | Temp | Wind | Regen | ⛈ für die nächsten 12h.

**AC-8:** Given `⏱ Stunden`-Button auf `/morgen` geklickt (Callback `dd_hours_tomorrow`), When Snapshot vorhanden, Then erscheint Tabelle für morgen 00:00–24:00.

**AC-9:** Given `⏱ Stunden` geklickt aber kein Snapshot, When on-demand Fetch fehlschlägt, Then Fehlertext "Keine stündlichen Daten verfügbar." ohne Absturz.

**AC-10:** Given `/now` im Bot-Menü (getMyCommands), When nach Deploy geprüft, Then erscheint `/now` in der Befehlsliste des Bots.

## Betroffene Dateien

| Datei | Änderung |
|-------|---------|
| `src/outputs/telegram.py` | BOT_COMMANDS + `now` |
| `src/services/inbound_telegram_reader.py` | `_SHORTCUT_MAP` + `/now`/`/n`; `_VALID_COMMANDS` + `now`; `_CALLBACK_QUERY_MAP` + `now` + `dd_hours_*` |
| `src/services/trip_command_processor.py` | `_show_now` reply_markup; `_handle_query` heute/morgen reply_markup; `_handle_hours_drilldown` neu; dispatch für `dd_hours_*` |

## Changelog

- 2026-06-10: Spec erstellt
