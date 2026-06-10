# Context: #704 Telegram Interaktive Stunden-Navigation + 2h-Nowcast

## Request Summary
/heute und /morgen sind Sackgassen (keine Buttons), stündliche Daten brauchen 3 Klicks via Glance→Timeline→Drilldown. Der `/now`-Nowcast existiert intern aber ist nicht im Menü.

## Related Files

| Datei | Relevanz |
|-------|---------|
| `src/services/trip_command_processor.py` | `_QUERY_KEYS`, `_handle_query`, `_fmt_day`, `_fmt_gewitter`, `_handle_drilldown`, `_show_now`, `_timeline_buttons`, `_DRILLDOWN_METRICS`, `_GLANCE_BUTTONS` |
| `src/services/inbound_telegram_reader.py` | `_SHORTCUT_MAP`, `_VALID_COMMANDS`, `_CALLBACK_QUERY_MAP`, `_CALLBACK_DRILLDOWN_PATTERN`, `_process_callback_query` |
| `src/outputs/telegram.py` | `BOT_COMMANDS` (7 Einträge, kein `now`), `send/edit_message_text/set_my_commands/get_my_commands` |
| `src/services/weather_extractor.py` | `drilldown(trip_id, metric, from_time, hours)` — liefert `DrilldownResult[DrilldownPoint{ts, value}]` |
| `src/services/radar_service.py` | `RadarNowcastService.get_nowcast(lat, lon)` + `format_now_text(result)`, `NowcastResult{onset_minutes, intensity_label, is_convective}` |

## Existing Patterns

- **Buttons auf Nachrichten:** `reply_markup={"inline_keyboard": [[{text, callback_data}]]}` im `CommandResult`
- **Callback-Routing:** `_CALLBACK_QUERY_MAP` → `### query: X`, `_CALLBACK_DRILLDOWN_PATTERN` → `### dd_metric_day`
- **Query-Keys:** `_QUERY_KEYS` in `trip_command_processor.py` UND `inbound_telegram_reader.py` — beide Stellen müssen erweitert werden
- **_SHORTCUT_MAP:** Slash-Befehle + Kurzform-Aliases
- **Drilldown-Metriken:** `_DRILLDOWN_METRICS = {"thunder": (field, header, fmt), "wind": ..., "precip": ...}`
- **Timeline-Buttons:** `_timeline_buttons()` zeigt Drilldown-Buttons nur bei kritischen Werten (Thunder ≥ MED, Wind ≥ 40, Pop ≥ 30% / Precip ≥ 1mm)

## Was FEHLT (Deltas zum Ist-Zustand)

### Slice 1 — Buttons auf /heute und /morgen
- `_fmt_day()` gibt Text zurück, kein `reply_markup` → `_handle_query` bei `heute`/`morgen` liefert kein `reply_markup`
- Buttons die gebraucht werden: `⏱ Stunden`, `⛈ Gewitter`, `💨 Wind`, `🌧 Regen`, `🕐 Timeline`
- Callback-Daten für Stunden: `dd_hours_today` / `dd_hours_tomorrow` (noch nicht vorhanden)

### Slice 2 — Stündliche Kompaktansicht (dd_hours_today/tomorrow)
- `_DRILLDOWN_METRICS` hat nur `thunder`, `wind`, `precip` — kein `hours` (Multi-Metrik)
- `_DRILLDOWN_PATTERN` matcht nur `dd_(thunder|wind|precip)_(today|tomorrow)` — nicht `dd_hours_*`
- `_CALLBACK_DRILLDOWN_PATTERN` in `inbound_telegram_reader.py` ebenso
- Neue Methode `_handle_hours_drilldown()` nötig die mehrere Metriken kombiniert
- Format: Monospace-Tabelle (Zeit | Temp | Wind | Regen | ⛈)

### Slice 3 — /now im Menü
- `BOT_COMMANDS` enthält kein `now`
- `_SHORTCUT_MAP` hat kein `/now` / `/n`
- `_VALID_COMMANDS` in `inbound_telegram_reader.py` enthält kein `now`
- `_show_now()` gibt keinen `reply_markup` zurück (kein Aktualisieren-Button)
- `set_my_commands()` wird beim Startup aufgerufen — Änderung an BOT_COMMANDS ist ausreichend

## Abhängigkeiten

- `WeatherExtractor.drilldown()` — stündliche Daten für Temp, Wind, Precip, Thunder (ForecastDataPoint-Felder: `t2m_c`, `wind10m_kmh`, `precip_1h_mm`, `thunder_level`)
- `_QUERY_KEYS` muss in processor.py UND reader.py konsistent sein
- `_CALLBACK_DRILLDOWN_PATTERN` in reader.py muss `dd_hours_` matchen

## Risiken

- `dd_hours_today` braucht neues Pattern in reader.py — nicht durch `_CALLBACK_DRILLDOWN_PATTERN` gedeckt (matcht nur thunder|wind|precip)
- Temp-Drilldown-Feld heißt `t2m_c` in ForecastDataPoint, nicht `temp_*` — muss geprüft werden
- `set_my_commands()` läuft beim Startup → nach Deploy automatisch aktuell; kein manueller Ops-Schritt nötig (Issue #671 korrigiert)
