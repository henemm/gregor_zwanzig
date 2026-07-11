# Context: rework-1209-config-resolver-b

## Request Summary
Scheibe B von #1203: Vorschau-Pfad und Compare-Pfad auf den in Scheibe A (#1208)
gebauten `ReportRenderOptions`-Resolver umstellen, sodass Vorschau ≡ Versand, und
ein Struktur-Test verbietet fortan Direktzugriffe auf render-wirksame
`report_config`-Felder außerhalb des Resolvers.

## Related Files
| Datei | Relevanz |
|-------|----------|
| `src/services/report_config_resolver.py` | Scheibe-A-Resolver: `ReportRenderOptions` (frozen), `resolve_report_render_options()`, `RENDER_EFFECTIVE_FIELDS` (7), `RENDER_NEUTRAL` (20). Referenz für die Compare-Variante. |
| `src/services/preview_service.py` | **Ziel 1.** `_build_report` Zeile 120–121 mutiert `trip.display_config.show_compact_summary = trip.report_config.show_compact_summary` (Patch-Hack, F002). `_render_email` ruft `format_email(...)` OHNE `render_options`. |
| `src/services/trip_report_scheduler.py` | **Vorbild.** Zeile 636–639 resolved einmal, reicht `render_options=` an `format_email()` durch (Z. 816). Der frühere Patch-Hack an Z. 779 wurde in Scheibe A entfernt. |
| `src/output/renderers/trip_report.py` | `format_email(..., render_options=None)`; interner Fallback Z. 88 `options = render_options or resolve_report_render_options(...)` (AC-4). Konsumiert `options.show_compact_summary` etc. |
| `src/services/scheduler_dispatch_service.py` | **Ziel 2.** `send_one_compare_preset` Z. 252–276 zieht `top_n`/`active_metrics`/`hourly_metrics` inline aus dem rohen `preset["display_config"]`-Dict + `hourly_enabled` top-level. Braucht Compare-Variante des Options-Objekts. |
| `src/output/renderers/comparison.py` | `render_compare_email(...)` — Konsument der Compare-Optionen (unverändert). |

## Existing Patterns
- **Resolver-Verdrahtung (Scheibe A):** einmal `resolve_report_render_options(rc, dc, report_type)` am Anfang des Pfads, dann `render_options=` explizit durch alle Aufrufe reichen. `format_email` hat bereits den Fallback-Parameter.
- **Frozen Options-DTO:** `@dataclass(frozen=True)`, reine Funktion, keine I/O/Mutation. Fallback-Semantik identisch zum Bestandsverhalten.
- **Struktur-/AST-Test:** `tests/tdd/test_report_config_scheduler_structure.py` existiert schon (in `_SELF_EXEMPT` von test_765). Muster für den src-weiten Gate.
- **Compare-Metrik-Auflöser:** `resolve_enabled_metrics()` / `resolve_hourly_metrics()` (in `output/renderers/compare_metric_ids.py` / `compare_hourly_metric_ids.py`) — Bausteine, die die Compare-Variante bündeln kann.

## Dependencies
- **Upstream:** `app.models.TripReportConfig` + `UnifiedWeatherDisplayConfig`; `app.metric_catalog.build_default_display_config`.
- **Downstream:** Vorschau-Endpoints (`render_email_preview`/`render_sms_preview`/`render_telegram_preview`), Compare-Versand (`send_compare_preset`, Daily-Loop Z. 65).

## Existing Specs
- `docs/specs/modules/report_config_resolver.md` v1.1 — Resolver-Vertrag (Scheibe A).
- `docs/specs/modules/preview_service.md` — Preview-Sub-Spec.

## Direktzugriff-Inventar (für AC-3 Struktur-Gate)
**Render-wirksam → MUSS über Resolver (Gate-Ziel):**
- `preview_service.py:121` — `show_compact_summary` Patch-Hack (einziger render-wirksamer Direktzugriff im Preview-Pfad).

**NICHT render-wirksam → Whitelist (Gate darf NICHT anschlagen):**
- `stage_weather.py:93–94`, `trip_report_scheduler.py:645–646` — `wind_exposition_min_elevation_m` (Pre-Render-Service, RENDER_NEUTRAL).
- `trip_report_scheduler.py:374–381` — `morning_time`/`evening_time` (Scheduling, RENDER_NEUTRAL).
- `trip_alert.py:127–128,142,289–290,309` — `alert_on_changes`/`alert_preset` (separater Alert-Pfad, RENDER_NEUTRAL).
- `trip_report_scheduler.py:637` — der Resolver-Aufruf selbst (Whitelist).

**Compare-Pfad (Ziel 2):**
- `scheduler_dispatch_service.py:254,271,273` — `display_config.get(top_n/active_metrics/hourly_metrics)` aus rohem Preset-Dict.

## Risks & Considerations
- **Gate-Design ist der Knackpunkt:** Ein blankes Verbot von `report_config.`/`display_config.` würde legitime RENDER_NEUTRAL-Zugriffe (`morning_time`, `wind_exposition_min_elevation_m`, `alert_on_changes`, `alert_preset`) fälschlich rot färben → strukturell nie bestehbar → Gate-Erosion. Das Gate MUSS auf die **7 render-wirksamen Felder** (`RENDER_EFFECTIVE_FIELDS`) begrenzt sein, mit Whitelist Resolver/Loader/Modelle.
- **F001 (bekannt, #1199):** AST-Gate ist blind für `getattr(rc, "feld")` — dokumentierte Grenze aus Scheibe A, nicht in dieser Scheibe zu lösen.
- **Bug-Nachweis Preview:** Test muss zeigen, dass Vorschau ohne den Patch-Hack denselben `email_format`/`show_compact_summary` liefert wie der Versand — rot vor Umstellung (Hack mutiert Bestandsobjekt), grün nach Umstellung (explizites `render_options`).
- **Kein Mail-Gate-Trigger erwartet:** Weder `preview_service.py` noch `scheduler_dispatch_service.py` stehen in der `renderer_mail_gate.py`-Liste (nur `src/output/renderers/*` + `channels/email.py`). Renderer bleiben unangetastet.
- **#954 (Telegram/SMS-Fußzeilen):** opportunistisch, nur wenn LoC-Budget (250) reicht; sonst Rest an #954 zurückmelden.
- **LoC-Budget 250:** 2 Service-Umstellungen + 1 Compare-Options-DTO + 1 Struktur-Test — realistisch eng; #954 vermutlich außerhalb.
