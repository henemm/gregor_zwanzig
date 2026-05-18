# Context: Issue #244 — SMS-Formatter: report_type nicht durchgereicht

## Request Summary
`SMSTripFormatter.format_sms()` ruft `build_token_line()` mit hardcoded `report_type="evening"` auf.
Der `report_type`-Parameter muss als optionaler Parameter (Default `"evening"`) durchgereicht werden,
damit `PreviewService.render_sms_preview()` ihn korrekt weitergibt.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `src/formatters/sms_trip.py:132` | **Bug-Stelle:** `build_token_line(..., report_type="evening")` hardcoded |
| `src/services/preview_service.py:126-155` | Aufrufer: `render_sms_preview()` übergibt `report_type` an `format_sms()` — fehlt noch |
| `src/output/tokens/builder.py:147-165` | `build_token_line()` — nimmt `report_type: ReportType` als Keyword-Arg |
| `src/output/tokens/dto.py:59-60` | `MetricSpec.morning_enabled / evening_enabled` — durch `report_type` gesteuert |
| `tests/unit/test_sms_trip.py` | Bestehende Unit-Tests für `format_sms()` |
| `tests/tdd/test_epic_140_preview_endpoints.py` | Tests für `render_sms_preview()` |
| `tests/e2e/test_e2e_story3_reports.py:256,267` | E2E-Tests rufen `format_sms()` ohne `report_type` auf |
| `tests/integration/test_wind_exposition_pipeline.py:310,324` | Integration-Tests ohne `report_type` |

## Existing Patterns

- `build_token_line()` erwartet `report_type` als Keyword-Only-Argument (`ReportType = Literal["morning", "evening"]`)
- `PreviewService.render_email_preview()` übergibt `report_type` korrekt durch die ganze Kette
- `render_sms_preview()` hat bereits `report_type`-Parameter — gibt ihn aber noch nicht an `format_sms()` weiter
- Alle anderen `format_sms()`-Aufrufer (Tests) nutzen keinen `report_type` → Default `"evening"` bewahrt Rückwärtskompatibilität

## Dependencies
- **Upstream:** `build_token_line()` in `src/output/tokens/builder.py` — erwartet `report_type`
- **Downstream:** `render_sms_preview()` in `PreviewService` — muss `report_type` übergeben

## Existing Specs
- `docs/specs/modules/output_channel_renderers.md` — §A3 Adapter-Vertrag für SMSTripFormatter
- `docs/specs/modules/issue_188_sms_preview_token_pipeline.md` — SMS-Preview-Pipeline

## Fix-Umfang (minimal)
1. `format_sms()` um Parameter `report_type: str = "evening"` erweitern
2. Diesen an `build_token_line(..., report_type=report_type, ...)` weiterreichen
3. `PreviewService.render_sms_preview()` übergibt `report_type` an `format_sms()`

## Risks & Considerations
- **Rückwärtskompatibilität:** Default `"evening"` sichert alle bestehenden Aufrufer ohne Anpassung
- **Kein Breaking Change** in Tests — kein Test übergibt `report_type` an `format_sms()` bisher
- **Kein Schema-Rework** — rein funktionale Änderung, keine Persistenz betroffen
