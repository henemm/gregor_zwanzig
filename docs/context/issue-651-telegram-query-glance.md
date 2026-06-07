# Context: #651 — Telegram-Abfrage-Befehle (`/s /h /m /hg`) + Tier-1-Glance

## Request Summary
Teil 2/6 von Epic #639. Ergänzt **lesende** (non-destruktive) Telegram-Abfrage-Befehle —
`/s` (Status/Glance), `/h` (heute), `/m` (morgen), `/hg` (heute Gewitter) plus
`### query: <key>`-Langform — und eine **Tier-1-Glance**-Textzusammenfassung der heute
**und** morgen aktiven Etappe, inkl. Buttons „Timeline heute" / „Timeline morgen" (aus #650).

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_command_processor.py` | `TripCommandProcessor` — kennt nur **verändernde** Befehle. Hier kommen die lesenden Query-Handler rein. DTOs `InboundMessage` (hat `received_at`!), `CommandResult`. |
| `src/services/inbound_telegram_reader.py` | `_parse_command` + `_VALID_COMMANDS` — Freitext→Befehl. Hier muss `/s /h /m /hg` gemappt werden. `_process_update` baut `InboundMessage` und ruft `TelegramOutput.send(subject, body)`. |
| `src/outputs/telegram.py` | `TelegramOutput.send(subject, body, reply_markup=None)` — Buttons aus #650 bereits vorhanden (additiv). Keyboard-Format: `{"inline_keyboard": [[{"text":..., "callback_data":...}]]}`. |
| `src/services/weather_extractor.py` | `WeatherExtractor` (#652) — `timeline(trip_id, target_date)` liefert `TimelinePoint`s (arrival_time, elevation_m, `metrics: SegmentWeatherSummary`). Datenquelle für die Glance. **Hinweis:** `target_date` wird aktuell NICHT gefiltert (kommt in #653). |
| `src/services/weather_snapshot.py` | `WeatherSnapshotService.load(trip_id)` → `list[SegmentWeatherData]` (echte Datei-I/O, kein Mock). |
| `src/app/trip.py` | `Trip.stages` → `Stage(id="T1", name, date, waypoints)`. Aktive Etappe = Stage mit `date == received_at.date()`; morgen = +1 Tag. |
| `src/app/models.py` | `SegmentWeatherSummary` (temp_min/max, wind/gust_max, precip_sum, `thunder_level_max`, `pop_max_pct` …). `TripSegment.end_time` (UTC), `segment_id`. |
| `src/services/inbound_email_reader.py` | Nutzt `CommandResult.confirmation_subject/body` — additive Felder (z.B. `reply_markup`) müssen rückwärtskompatibel bleiben (Email ignoriert sie). |
| `api/routers/webhook.py` | `/api/internal/telegram-webhook` → `_reader._process_update`. Verarbeitet nur `message`, KEIN `callback_query` (Button-Klicks = #655). |

## Existing Patterns
- **Read-only beweisen (AC-2):** verändernde Befehle schreiben `command_log.json` (`_append_command_log`) und rufen `save_trip`. Lesende Befehle dürfen **beides nicht** tun.
- **Additive DTO-Erweiterung:** `send(reply_markup=None)` (#650) und `sms_threshold` (#624) zeigen das Muster — neues optionales Feld, Default = Altverhalten bit-identisch.
- **Snapshot-Tests ohne Mock (#652):** `WeatherSnapshotService` mit `svc._snapshots_dir = tmp_path`, echte `save`/`load`-Roundtrips. `WeatherExtractor` analog (`ex._snapshots._snapshots_dir = tmp_path`).
- **Buttons (#650):** `callback_data`-String + Button-Text mit Emoji; Inline-Keyboard als verschachtelte Liste.

## Dependencies
- **Upstream:** #650 (Buttons/reply_markup) ✅ live, #652 (WeatherExtractor) ✅ live.
- **Downstream:** #653/#654 (Tier-2/3 = was die Buttons später auslösen), #655 (`callback_query`-Handling). Die Glance-Buttons sind in #651 nur **präsent**, ihr Klick wird erst in #655 verarbeitet.

## Existing Specs
- `docs/specs/modules/trip_command_processor.md` (v2.1) — wird erweitert.
- `docs/specs/modules/weather_extractor.md` (v1.0, #652).
- `docs/specs/modules/feature_650_telegram_inline_keyboards.md`.
- `docs/specs/modules/telegram_webhook_inbound.md` (#637).

## Offene Design-Entscheidungen (für Spec-Phase)
1. **`status` vs. neue Glance:** Altes `### status` listet alle Etappen (auch von Email genutzt). AC-1 will für `/s`/`/status` die Glance (heute+morgen+Buttons). → Telegram-`/s` auf neuen Glance-Handler routen, legacy `status` (Email) unangetastet lassen.
2. **Glance-Datenquelle:** Segmente nach `end_time`-Datum auf heute/morgen gruppieren und kompakt aggregieren (temp, wind, gewitter, niederschlag). Bei fehlendem Snapshot → klarer Hinweistext, trotzdem Buttons.
3. **reply_markup-Transport:** Optionales `reply_markup`-Feld auf `CommandResult` (None-Default, Email ignoriert) + Durchreichen in `inbound_telegram_reader`.

## Risks & Considerations
- **LoC:** Query-Handler + Glance-Formatter + Tests könnten >250 LoC werden → ggf. PO um höheres Limit fragen oder Slice.
- **Mandantentrennung:** `WeatherExtractor(user_id=...)` und alle Lookups user-scoped — niemals `"default"`-Fallback im Auth-Pfad.
- **Mock-Verbot:** Telegram-/Snapshot-Tests gegen echten lokalen HTTP-Server bzw. echte Datei-I/O (Muster #650/#652).
- **AC-2 hart testen:** vor/nach Query-Befehl `command_log.json` und Stage-Daten unverändert.
