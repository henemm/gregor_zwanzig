# Context: Feature #656 — Radar-Nowcasting für Ad-hoc-Abfragen & Alerts

## Request Summary
Einführung eines Radar-/Nowcast-Services, der echte Kurzfrist-Daten (RADOLAN-Radar, INCA, minutely_15) nutzt, um die Frage „Fängt es in den nächsten 20 Minuten an zu regnen/zu gewittern?" als kompakten Text zu beantworten — sowohl auf Abruf (`### now` via Inbound-Kanal) als auch proaktiv (Radar-Alert bei Zelle auf Kollisionskurs).

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_command_processor.py` | Inbound-`### key`-Befehle. `_VALID_COMMANDS`-Whitelist (Z.66) + Dispatch (Z.117). Hier wird `now` registriert. **Kein Trip-Lookup-freier Pfad für `now` mit Positionsbezug — Positionsermittlung neu.** |
| `src/services/inbound_email_reader.py:140` | Ruft `processor.process(inbound)` — Email-Verdrahtung steht. |
| `src/services/inbound_telegram_reader.py:139` | Ruft `TripCommandProcessor().process(inbound)` — Telegram-Verdrahtung steht. |
| `src/providers/geosphere.py:315` | **`fetch_nowcast(lat,lon)` existiert bereits** — INCA `nowcast-v1-15min-1km`, 3h voraus, Params t2m/ff/fx/rr/pt/rh2m. Deckt den GeoSphere-Teil des Issues weitgehend ab. |
| `src/providers/base.py` | `WeatherProvider`-Protocol + Registry (`register_provider`/`get_provider`). Neuer BrightSky-Provider registriert sich hier. |
| `src/providers/openmeteo.py` | Bestehender globaler Provider; Basis für `minutely_15`-Fallback (global, deckt Korsika/GR20). |
| `src/services/trip_alert.py` | Alert-Engine (`check_all_trips`, Throttle, QuietHours, alert_log). Andockpunkt für proaktive Radar-Alerts (AC-4). |
| `src/app/trip.py:219` | `get_stage_for_date(today)` → aktuelle Etappe; Stage.waypoints liefern lat/lon/elevation für Positionsermittlung. |
| `src/app/models.py` | `NormalizedTimeseries`, `NOWCASTMIX`-Modell-Enum. |

## Existing Patterns
- **Provider-Protocol + Registry:** Neue Datenquellen registrieren sich über `register_provider(name, factory)` und implementieren `WeatherProvider`. BrightSky passt hier rein (ggf. mit Spezial-Methode `fetch_radar`, analog zu GeoSphere `fetch_nowcast`, die außerhalb des Standard-`fetch_forecast` liegt).
- **Channel-agnostische Befehle:** `### key: value` → `CommandResult(confirmation_subject, confirmation_body)`; Reader sendet Antwort auf gleichem Kanal zurück. `now` fügt sich nahtlos ein.
- **Service-Layer:** Logik in `src/services/*`, dünn, testbar als reine Funktionen (vgl. `_select_change_detector`).
- **Alert-Mechanik:** Throttle pro Trip (JSON), QuietHours, alert_log für Cockpit — alles wiederverwendbar.
- **Mandantentrennung:** `user_id` wird konsequent durchgereicht (InboundMessage.user_id, Service-Konstruktoren).

## Dependencies
- **Upstream (genutzt):** `httpx` (Provider-HTTP), `NormalizedTimeseries`, `get_stage_for_date`, Inbound-Reader.
- **Downstream (Nutzer):** Inbound-Reader (Email/Telegram) für `### now`; Scheduler für proaktive Alerts.

## Existing Specs
- `docs/specs/modules/trip_command_processor.md` (v2.1) — Befehls-Whitelist & DTOs; muss um `now` erweitert werden.
- `docs/specs/modules/trip_alert.md` (v2.0) — Alert-Engine.
- `docs/specs/data_sources.md` — Daten-Governance (welche API-Parameter erlaubt). **Pflicht-Check bei neuer Datenquelle BrightSky.**

## Risks & Considerations
- **GEOGRAFISCHE ABDECKUNG (kritisch, produktrelevant):** Flagship-Use-Case ist der **GR20 = Korsika/Frankreich**. Dort hat **weder DWD-RADOLAN** (BrightSky: nur Deutschland + Grenzregionen) **noch GeoSphere INCA** (nur Österreich) Abdeckung. Nur der globale **Open-Meteo `minutely_15`**-Pfad funktioniert dort. → Empfehlung: minutely_15 als **primärer** Nowcast (global), BrightSky/INCA als **regionale Präzisions-Aufwertung** wo abgedeckt. Reihenfolge im Issue (BrightSky primär) ist für die eigene Zielgruppe suboptimal.
- **Scope:** Das Issue umfasst 4 ACs über 3 Module + Alert-Engine — deutlich >250 LoC, kein Ein-Workflow-Feature. Split empfohlen (siehe PO-Frage).
- **Bewegungsvektor/„Kollisionskurs":** Echte Zell-Tracking-Vektoren sind aufwändig und oft nicht direkt in der API. MVP: Distanz-/Trend-Check (kommt Niederschlag im Raster näher), kein voll-physikalisches Tracking.
- **Latenz-AC (`<10s`):** Live-API-Aufruf im synchronen Inbound-Pfad — Timeout/Fallback-Kette nötig.
- **KEINE Mocks:** Provider-Tests müssen echte API-Calls machen (BrightSky/Open-Meteo sind frei & ohne Key).
- **Positionsermittlung:** Trip hat Etappen mit Datum + Waypoints, aber **keine Live-GPS-Position**. „Aktuelle Position" = repräsentativer Punkt der heutigen Etappe (`get_stage_for_date(today)`), nicht echtes GPS.
