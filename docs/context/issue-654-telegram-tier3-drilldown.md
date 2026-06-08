# Context: Issue #654 — Telegram Tier-3 Single-Metric-Drilldown (Gewitter stündlich)

## Request Summary
Teil 5/6 von Epic #639. Formatiere die stündliche Drilldown-Serie **einer** Metrik
(primär Gewitterrisiko) und sende sie via Telegram — inkl. „Zurück"-Button. Datenschicht
(#652) und Button-Serialisierung (#650) sind bereits live.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/weather_extractor.py` | **Datenquelle** — `WeatherExtractor.drilldown(trip_id, metric, from_time, hours)` liefert `DrilldownResult` mit `DrilldownPoint(ts, value)` je Stunde (#652, fertig). |
| `src/services/trip_command_processor.py` | **Dispatch** — `### key`-Befehle, `_VALID_COMMANDS`. Vorbild `_show_now` (#656). Hier kommt der `hg`-Befehl + Formatter rein. `CommandResult` muss ein optionales `reply_markup`-Feld bekommen. |
| `src/services/inbound_telegram_reader.py` | **Telegram-Trigger** — eigene `_VALID_COMMANDS`-Whitelist (enthält `now` NICHT!). Muss `hg` aufnehmen und `result.reply_markup` an `send()` durchreichen. |
| `src/outputs/telegram.py` | **Ausgabe** — `send(subject, body, reply_markup=None)` unterstützt Inline-Keyboards bereits (#650). `MAX_MESSAGE_LENGTH=4096`. |
| `src/app/models.py:85` | `ForecastDataPoint.thunder_level: Optional[ThunderLevel]` — **Feldname für Gewitter** ist `thunder_level`. Enum: `NONE / MED / HIGH`. |
| `api/routers/webhook.py` | Interner Webhook-Endpoint (Go → Python), ruft `InboundTelegramReader._process_update` auf (#637). Kein Polling mehr. |

## Existing Patterns
- **Flacher `### key`-Befehl** statt epic-Aspirational `### query: d_thunder_today`. #656 hat `### now` flach umgesetzt — dem folgen wir (Konsistenz mit ausgeliefertem Code schlägt nie-implementierte Epic-Syntax).
- **`_show_now` (#656)** als Bauplan: Trip-Lookup → Service-Aufruf → `format_*_text` → `CommandResult`.
- **Telegram-Formatter** (`radar_service.format_now_text`): kompakte deutsche Zeilen, Emojis, Quellen-Label.
- **Mock-frei (KRITISCH):** RED über lokalen `http.server` (echter Socket) für deterministisches Send-Capture; Drilldown-Logik gegen echte Snapshot-Fixtures.

## Dependencies
- **Upstream:** `WeatherExtractor.drilldown` (#652), `TelegramOutput.send(reply_markup=)` (#650), `WeatherSnapshotService` (Snapshots je `trip.id`).
- **Downstream:** Der „Zurück"-Button trägt `callback_data` — **klickbar erst mit #655** (callback_query + editMessageText, noch offen). AC-2 verlangt nur die *Präsenz* des Buttons, nicht dessen Funktion → in #654 erfüllbar.

## Existing Specs
- `docs/specs/modules/weather_extractor.md` v1.0 (#652)
- `docs/specs/modules/radar_nowcast.md` (#656, Vorbild Telegram-Formatter)
- `docs/specs/modules/trip_command_processor.md` v2.1
- Neu anzulegen: `docs/specs/modules/telegram_tier3_drilldown.md`

## Risks & Considerations
- **Dependency-Spannung:** `/hg`-Slash-Befehle (#651) und Button-Klicks (#655) sind **beide offen**. #654 verdrahtet daher einen eigenen Trigger (`### hg` / `hg` Freitext, leading `/` toleriert) — minimal, self-contained, ohne in #651s vollen Befehlssatz vorzugreifen.
- **`reply_markup` in `CommandResult`:** Kanal-agnostisches DTO bekommt ein optionales Telegram-Feld. E-Mail/SMS ignorieren es. Vertretbar, da `None`-Default = bit-identisch für Bestandskanäle.
- **Zeitfenster:** `from_time = received_at` → „nächste 6–12 h ab Anfrage" (AC-1). `hours=12`.
- **„Auch wenn verborgen":** Drilldown liest `thunder_level` direkt aus der Zeitreihe, unabhängig von Display-Config → AC-1 by design erfüllt.
- **Leerzustand:** Kein Snapshot / keine Stundendaten → klare Meldung statt leerer Liste.
- **Multi-User:** `WeatherExtractor(user_id)` + Trip-Lookup user-scoped; kein `default`-Fallback im authentifizierten Pfad.
