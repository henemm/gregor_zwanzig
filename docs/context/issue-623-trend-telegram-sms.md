# Context: #623 Mehrtages-Trend in Telegram + SMS + Renderer-Konsolidierung

## Request Summary
Der Mehrtages-Trend (#561) erscheint bisher nur in der E-Mail (HTML + Text-Teil).
AC-7 verlangt ihn auch als Plain-Text für Telegram und SMS. Zusätzlich: fehlendes
E-Mail-Kontext-Label und Entfernung toter Doppel-Renderer.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_report_scheduler.py` | `_build_stage_trend` baut `multi_day_trend` (Liste Dicts), Z. 988-1025. Versand-Dispatch Z. 467-497 (nur Email + Telegram!). |
| `src/formatters/trip_report.py` | `format_email()` Z. 52: ruft `render_email` (mit Trend) + 2× `render_narrow` (OHNE Trend). Tote `_render_html`/`_render_text` Z. 906/1110. |
| `src/output/renderers/narrow.py` | Mono-Renderer Telegram/Signal — kennt KEINEN Trend. Andockpunkt für Telegram-Trend. `_LINE_WIDTH = {signal:26, telegram:40}`. |
| `src/output/renderers/email/html.py` | E-Mail-HTML-Trendblock Z. 430-526 (live, originalgetreu). Kontext-Label fehlt Z. 506-509. |
| `src/output/renderers/email/plain.py` | E-Mail-Text-Trend Z. 233-264 (live). |
| `src/formatters/sms_trip.py` / `src/output/renderers/sms/` | SMS-Token-Pipeline. `format_sms()` → `render_sms()`. Andockpunkt SMS-Trend. |
| `src/app/models.py` | `ThunderLevel` = NONE/MED/HIGH (KEIN LOW). |

## Existing Patterns
- **Format-Renderer pro Kanal** (HTML / Mono / SMS-flach) = korrektes Pattern, bleibt getrennt.
- Trend-Daten als `list[dict]` mit Keys: weekday, name, temp_lo, temp_hi, precip_mm, wind_dir, wind_kmh, thunder, note.
- Gewitter-Ampel HTML: Quadrat + Wort. Plain: `⚡–/⚡MED/⚡HIGH`. SMS (Design): `GEW-{LEVEL}`.

## Dependencies
- Upstream: `_build_stage_trend` (Scheduler) liefert Trend an `format_email()`.
- Downstream: `render_narrow` (Telegram-Body), `SMSTripFormatter` (Vorschau + telegram_kurzform "Tages-Max").

## Existing Specs
- `docs/specs/modules/issue_360_signal_channel_renderer.md` — narrow-Renderer.
- `docs/specs/modules/sms_format.md`, `output_channel_renderers.md` — SMS-Pipeline.

## Risks & Considerations
- **SMS ist KEIN aktiver Versandkanal für Trip-Reports.** Scheduler sendet nur Email + Telegram.
  SMS läuft nur über Vorschau + das ausstehende seven.io-Issue #608 (Status: Validation).
  → SMS-Trend-Format implementieren lohnt für Vorschau + #608-Readiness, erreicht aber bis
  #608-Launch keine Nutzer. **PO-Scope-Flag.**
- `telegram_kurzform` (#614) ruft `SMSTripFormatter.format_sms(max_length=4000)` und hängt das
  Ergebnis als "Tages-Max" an die Telegram-Nachricht. Wird der Trend in `SMSTripFormatter`
  ergänzt, taucht er dort doppelt auf (Telegram-Body + Tages-Max). → Trend im SMS-Formatter
  muss vom Tages-Max-Pfad ausgenommen oder bewusst nur im echten SMS-Pfad aktiv sein.
- Signal bewusst ausgenommen (#610, Kanal in Abbau).
- `LOW`-Gewitter: toter Code, NICHT implementieren.
- Tote `_render_html`/`_render_text` löschen — null Call-Sites verifiziert, aber vor Löschen
  final auf getattr/dynamische Dispatch prüfen.
