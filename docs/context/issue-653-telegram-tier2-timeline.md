# Context: #653 — Telegram Tier-2 Vertikale Timeline je Etappe

## Request Summary
Formatiert die Extraktor-Daten (#652) als kompakte **vertikale Timeline einer Etappe**
(pro Wegpunkt: Naismith-Ankunftszeit + Höhe + Wetter-Metriken, emoji-gestützt) und
liefert sie als Telegram-Antwort mit **Drilldown-Buttons je kritischer Metrik** + „Zurück".
Teil 4/6 von Epic #639.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_command_processor.py` | Query-Dispatch + Formatter — hier kommt der Timeline-Handler + Button-Builder rein (Muster: `_handle_query`, `_fmt_glance`). |
| `src/services/inbound_telegram_reader.py` | Kurzbefehl-Mapping (`_SHORTCUT_MAP`, `_VALID_COMMANDS`) — neue Timeline-Shortcuts. |
| `src/services/weather_extractor.py` | `WeatherExtractor.timeline(trip_id)` → `TimelinePoint(arrival_time, elevation_m, label, metrics)`. Read-only Datenquelle (#652). |
| `src/app/models.py` | `SegmentWeatherSummary` (Metriken), `TripSegment` (end_time/end_point), `ThunderLevel`. |
| `api/routers/webhook.py` | Webhook-Eingang → `_process_update`. **Unverändert** (callback_query = #655). |
| `tests/tdd/test_issue_651_telegram_query_glance.py` | Test-Muster: echte Trips + echte Snapshots via `WeatherSnapshotService.save`, kein Mock. |

## Existing Patterns
- **Read-only Query-Pfad:** `_QUERY_KEYS` + `_handle_query()` → nie `save_trip`/`command_log`/`_delete_snapshot`.
- **Buttons via `CommandResult.reply_markup`** (additiv, Default None) → vom Inbound-Reader an `TelegramOutput.send(reply_markup=)` durchgereicht (#650/#651).
- **Glance-Buttons existieren bereits** (`_GLANCE_BUTTONS`: `tl_today`/`tl_tomorrow`, „📋 Timeline heute/morgen") — Verdrahtung der Klicks ist aber #655.
- **Tag-Filter:** `[p for p in timeline.points if p.arrival_time.date() == target_date]` (siehe `_aggregate_day`).

## Dependencies
- **Upstream:** `WeatherExtractor.timeline` (#652 ✅), `CommandResult.reply_markup` (#651 ✅), `TelegramOutput.send(reply_markup=)` (#650 ✅).
- **Downstream:** #655 (callback_query-Verdrahtung der Buttons), #654 (Tier-3 Drilldown-Handler hinter den `dd_*`-Buttons).

## Existing Specs
- `docs/specs/modules/issue_651_telegram_query_glance.md` — Tier-1, grenzt #653/#654/#655 explizit ab.
- `docs/specs/modules/weather_extractor.md` — Datenschicht.
- `docs/specs/modules/trip_command_processor.md` — Command-Processor.

## Design-Entscheidung (Scope-Abgrenzung)
- **Entry-Point = Text-Query-Keys** (`timeline_heute`/`timeline_morgen`, Shortcuts `/th` `/tm`, Langform `### query: timeline_heute`) — analog zu #651. So ist die Timeline **jetzt** End-to-End aus Nutzersicht testbar (RED→GREEN ohne Mock), ohne auf die callback_query-Verdrahtung (#655) zu warten. #655 brückt später nur die bestehenden Glance-Buttons auf dieselben Query-Keys.
- **Buttons definieren ≠ Buttons verarbeiten:** #653 setzt die `reply_markup`-Buttons (Drilldown `dd_<metric>_<day>` + „Zurück" `glance`) in die Antwort. Ihre Klick-Verarbeitung gehört zu #655/#654.

## Risks & Considerations
- **„Kritische Metrik" muss definiert sein** — sonst ist AC-2 (Drilldown-Buttons) nicht deterministisch testbar. Vorschlag: feste, dokumentierte Schwellen (Gewitter ≥ MED, Wind ≥ 40 km/h, Niederschlag pop ≥ 30 % oder precip ≥ 1 mm). Ohne kritische Metrik: nur „Zurück".
- **Snapshot kennt keine Waypoint-Namen** — `label` = `segment_id`. Timeline-Zeilen tragen Uhrzeit + Höhe + Metriken; das erfüllt AC-1 (Naismith-Zeit = `segment.end_time`, Höhe = `end_point.elevation_m`).
- **Read-only-Disziplin** (wie #651): kein Trip-Mutationspfad.
- **Worktree-Split-Brain:** Spec ins Hauptrepo UND Worktree spiegeln; Tests im Worktree committen.
- LoC-Budget 250 — Formatter + 2 Query-Keys + Button-Builder + Shortcuts passt (~120–150 LoC).
