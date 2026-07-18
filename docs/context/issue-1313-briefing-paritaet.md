# Context: issue-1313-briefing-paritaet

## Request Summary

Issue #1313 (PO-Entscheidungen 2026-07-18): **E1** — die Sektion „⚡ Gewitter-Vorschau" entfällt in E-Mail-Briefings, wenn die Mehrtages-Ausblick-Tabelle in derselben Mail aktiv ist (Dopplung seit #1275, gleiche Datenquelle). **E2** — die Sektion „🌙 Nacht am Ziel" erscheint auch im Morgenbriefing (bisher hart auf `report_type == "evening"` gegated).

## Related Files

| File | Relevance |
|------|-----------|
| `src/services/trip_report_scheduler.py:830` | E2: Fetch-Gate `report_type == "evening"` für `night_weather` (`_fetch_night_weather`) — entfernen |
| `src/output/renderers/trip_report.py:109` | E2: Render-Gate `report_type == "evening" and night_weather and dc.show_night_block` — Report-Typ-Bedingung entfernen |
| `src/output/renderers/email/html.py:1084-1097` | E1: `if thunder_forecast:` rendert Gewitter-Vorschau unconditional → um `not outlook_active` erweitern |
| `src/output/renderers/email/html.py:1271-1279` | E1: `show_outlook`-Handling — `trend_html` wird bei `show_outlook=False` zurückgesetzt; Quelle für `outlook_active = show_outlook and bool(multi_day_trend)` |
| `src/output/renderers/email/plain.py:235-244` | E1: Plain-Text-Pendant der Gewitter-Vorschau — gleiche Suppression |
| `src/services/trip_report_scheduler.py:1495` | Kontext: `_build_thunder_forecast_from_trend_or_fetch` (#1275) — bleibt UNVERÄNDERT (kanalübergreifende Quelle für SMS/Telegram) |
| `src/services/report_config_resolver.py:131` | Kontext: `show_multi_day_trend` pro Report-Typ, Default `["evening"]` (`src/app/loader.py:835`) — kein Änderungsbedarf |
| `src/services/preview_service.py:184-219` | Beobachtung: ruft Renderer identisch zum Versand (#1297) — E1 wirkt automatisch durch; `night_weather` wird dort NICHT übergeben → Vorschau-Lücke = eigenes Issue #1315, NICHT in #1313 |
| `src/output/renderers/sms_trip.py` | NICHT ändern: TH+-Token nutzt `thunder_forecast["+1"]` (Vertrag #874); SMS hat keine Ausblick-Tabelle als Ersatz |
| `src/output/renderers/narrow.py` | NICHT ändern: Telegram-Bubbles bekommen weder `thunder_forecast` noch Nachtdaten — bereits paritätisch |

## Existing Patterns

- **Vorschau = Versand** (#1297): `preview_service.py` ruft dieselben Render-Funktionen wie der Versand — Renderer-Änderungen wirken automatisch in der Vorschau; keine Parallel-Logik bauen.
- **Eine Gewitter-Datenquelle** (#1275): `thunder_forecast` wird EINMAL im Scheduler gebaut (aus Trend-Zeilen, Fallback Einzel-Fetch) und an alle Kanäle gereicht. Suppression darf deshalb NICHT im Scheduler passieren, sonst verliert SMS/Telegram das TH+-Token ersatzlos.
- **Report-Typ-Schalter über Resolver** (#1208): `show_multi_day_trend` läuft über `report_config_resolver.py`; `show_night_block` dagegen ist ein einfaches `UnifiedWeatherDisplayConfig`-Feld (Default True), gilt für beide Report-Typen identisch — kein neues Config-Feld nötig.
- **Zieldatum:** `_get_target_date()` (scheduler.py:525-539) — morning=HEUTE, evening=MORGEN. `_fetch_night_weather()` ist generisch (letztes Segment der jeweiligen Etappe) — für morning automatisch die Nacht nach heutiger Ankunft.

## Dependencies

- **Upstream:** Renderer konsumieren `thunder_forecast` (dict `{"+1","+2"}`), `night_weather` (NormalizedTimeseries), `multi_day_trend` (Trend-Zeilen), `show_outlook`/`dc.show_night_block` (Config).
- **Downstream:** `notification_service.py` (reicht Parameter durch), `preview_service.py` (gleiche Renderer), SMS-/Telegram-Renderer (thunder_forecast — unverändert lassen), `briefing_mail_validator.py` (Mail-Gate prüft Briefing-Mails — Renderer-Commit-Gate #811 greift: html.py/plain.py sind Mail-Inhalts-Dateien!).

## Existing Specs

- `docs/specs/modules/trip_report_formatter_v2.md` — Renderer-Verhalten (Nachtblock, Gewitter-Vorschau) — aktualisieren
- `docs/specs/modules/trip_report_scheduler.md` — Scheduler-Verhalten (night_weather-Fetch) — aktualisieren
- Workflow-Spec mit AC-N + ADR-Nr.: neu unter `docs/specs/modules/` (Phase 3)

## Risks & Considerations

- **Renderer-Commit-Gate #811:** `email/html.py` + `email/plain.py` sind Mail-Inhalts-Dateien → vor Commit müssen `tests/tdd/test_issue_811_mode_matrix.py` grün UND `briefing_mail_validator.py` frisch erfolgreich sein (echte Staging-Mail).
- **Bestehende Tests:** `test_issue_956_night_rows_date_bug.py`, `test_issue_956_email_pixel_diff.py` (Nacht-Rendering), `test_thunder_forecast_stage_consistency.py`, `test_thunder_forecast_trend_reuse.py`, `test_issue_721_email_outlook.py`, `test_preview_thunder_matches_sent.py` (thunder/Ausblick) — Golden-Anpassungen möglich, wenn Ausblick+Gewitter-Vorschau kombiniert getestet wird.
- **Kostenfolge E2:** ein zusätzlicher Provider-API-Call pro Trip/Tag für Morgenbriefings (PO-akzeptiert).
- **Abendbriefing-Regression:** E1 greift auch abends (Ausblick-Default evening) — dort verschwindet die Gewitter-Vorschau-Sektion, das IST gewollt (Dopplung). AC-6 sichert den Rest des Abend-Pfads ab.
- **Scoping:** 4 Dateien, je 1-4 Zeilen Logik + Tests — deutlich unter 250 LoC.
