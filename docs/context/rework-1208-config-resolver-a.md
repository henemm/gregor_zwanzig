# Context: rework-1208-config-resolver-a

Issue #1208 (Scheibe A von #1203) · erledigt #1102 mit · Track: Full Process · erstellt 2026-07-10

## Request Summary

Ein zentraler Config-Resolver (`src/services/report_config_resolver.py`) löst `report_config`/`display_config` eines Trips VOLLSTÄNDIG in ein explizites `ReportRenderOptions`-Objekt auf. Der Scheduler-Versandpfad konsumiert nur noch dieses Objekt (keine Hand-Durchreiche einzelner Felder mehr). Dazu ein parametrisierter Vertragstest über ALLE Config-Felder: Feldänderung muss Output ändern oder das Feld steht begründet auf einer `RENDER_NEUTRAL`-Liste.

## Related Files

| File | Relevance |
|------|-----------|
| `src/app/models.py:701-764` | `TripReportConfig` — alle Felder + Defaults (email_format, show_*, daily_summary_metrics, Zeiten, Kanäle, Alerts) |
| `src/app/models.py:552-650` | `UnifiedWeatherDisplayConfig` — Metrik-Auswahl, Kaskaden-Resolver `get_metrics_for_channel()` (618) |
| `src/app/loader.py:364-407, 480-598` | Parse/Persistenz beider Configs (Feld-für-Feld von Hand, inkl. Migrations-Fallbacks) — **Schema-relevant, Backup-Hook** |
| `src/services/trip_report_scheduler.py:637-921` | Scheduler-Pfad: Hand-Ableitung von multi_day_trend_reports (744), show_daylight (754), show_compact_summary-**Patch-Hack** (779), show_yesterday_comparison (784), wind_exposition (637), DTO-Bau (863-921) |
| `src/services/notification_service.py:54-92, 183-258` | `TripReportRequest`-DTO + `send_trip_report` → `format_email()` |
| `src/output/renderers/trip_report.py:56-171` | `TripReportFormatter.format_email()` — leitet 6 Toggles ab (129-139), **email_format + show_outlook fehlen** (Ursache #1102) |
| `src/output/renderers/email/__init__.py:32-59` | `render_email()`-Signatur; Defaults `email_format="full"`, `show_outlook=True`; schluckt 4 tote Toggles in `**_ignored` |
| `src/services/preview_service.py:120-168` | Vorschau-Pfad (Scheibe B — nur Abgrenzung; gleicher Patch-Hack Zeile 121) |
| `src/services/scheduler_dispatch_service.py:208-296` | Compare-Pfad (Scheibe B; liest Preset-`display_config`-Dict, nicht Trip-Modell) |

## Existing Patterns

- **Toggle-gegen-Output-Test:** `tests/tdd/test_issue_621_email_toggles.py` (mock-frei gegen render_html/plain) — deckt aber die Forwarding-Lücke NICHT ab, weil er die Renderer direkt aufruft.
- **Voller render_email-Pfad-Test:** `tests/tdd/test_issue_811_mode_matrix.py` (Format×Modus-Matrix, echtes `render_email`, `_make_dp()`-Segment-Fabrik) — bestes Vorbild für den Vertragstest.
- **AST-/Struktur-Tests:** `tests/tdd/test_765_backend_hygiene_compliance.py` u.a. (`ast.parse`/`ast.walk`) — Vorbild für AC-3 (Struktur-Assertion „kein Direktzugriff").
- **Resolve→Options-Muster:** `resolve_enabled_metrics()` (`compare_metric_ids.py:23`), `get_metrics_for_channel()`-Kaskade; DTO-Stil: frozen dataclass wie `StabilityResult` (`models.py:832`), `TripReportRequest`.
- **Fixtures:** KEINE aufgezeichneten Wetterdaten-Fixtures vorhanden — Tests bauen Segmente per Helper-Fabrik. Für den Vertragstest ist eine versionierte Fixture (echte aufgezeichnete Daten) erwünscht (Issue-Text) oder Segment-Fabrik nach 811-Vorbild.

## Kernbefunde (Lücken, die der Resolver schließen muss)

1. **`email_format` + `show_outlook`** werden im gesamten Versand-/Vorschau-Pfad NIE aus `report_config` gelesen → Defaults greifen immer (#1102 live bewiesen: `X-GZ-Format: full` trotz persistiertem `compact`).
2. **Tote Toggles seit #790:** `show_quick_take_tags`, `show_highlights`, `daily_summary_metrics`, `show_metrics_summary` werden von `format_email` übergeben, aber `render_email` schluckt sie in `**_ignored` (html.py:776, plain.py:99: bewusst absorbiert). → Kandidaten für `RENDER_NEUTRAL`-Liste ODER PO-Entscheidung (Toggle-Leichen entfernen = eher #1215/Scheibe B).
3. **Patch-Hack:** `trip.display_config.show_compact_summary = trip.report_config.show_compact_summary` mutiert das Config-Objekt an 2 Stellen (scheduler 779, preview 121).
4. **SMS/Telegram** laufen durch denselben `format_email`, konsumieren aber nur `display_config` (dc.metrics), keine `report_config`-Toggles — Scheiben-Schnitt beachten: Scheibe A = E-Mail-Zuleitung + Options-Objekt, das SMS/Telegram-Felder bereits trägt oder bewusst ausklammert.

## Dependencies

- **Upstream (Resolver liest):** `TripReportConfig`, `UnifiedWeatherDisplayConfig`, ggf. `report_type` (morning/evening).
- **Downstream (konsumiert Options):** `trip_report_scheduler` → `TripReportRequest` → `notification_service` → `TripReportFormatter.format_email` → `render_email`.
- **Nicht-Scope (Scheibe B / #1131):** preview_service, send_one_compare_preset, CLI (liest ohnehin keine Config).

## Existing Specs

- `docs/specs/modules/report_options_migration.md` — DisplayConfig→TripReportConfig-Migration (Vorläufer)
- `docs/specs/modules/trip_report_formatter_v2.md`, `output_channel_renderers.md` — format_email→render_email-Adapter
- `docs/specs/modules/email_toggles_621.md`, `issue_722_email_compact_format.md`, `issue_956_email_format.md`, `issue_721_email_outlook.md` — Einzel-Toggles
- `docs/specs/modules/trip_report_scheduler.md`, `scheduler_multi_user.md` — Versandpfad
- `docs/specs/modules/loader_display_config_default.md` — Default-Auflösung beim Laden

## Risks & Considerations

- **Blast Radius hoch:** kompletter Briefing-Versand (E-Mail/Telegram/SMS) hängt am Pfad → Renderer-Mailgate greift (`trip_report.py` ist gelistete Mail-Inhalts-Datei): `test_issue_811_mode_matrix.py` grün + `briefing_mail_validator.py` gegen echte Staging-Mail Pflicht vor Commit.
- **LoC-Limit 250:** Resolver + Vertragstest + Scheduler-Umbau könnte knapp werden — Override nur mit PO-Erlaubnis.
- **Tote Toggles:** Vertragstest zwingt zur expliziten Entscheidung pro Feld (wirksam vs. RENDER_NEUTRAL mit Begründung) — PO-sichtbare Liste in der Spec nötig.
- **Verhaltensänderung durch Fix:** Sobald `email_format` durchgereicht wird, bekommen Trips mit persistiertem `compact` erstmals wirklich Compact-Mails (gewollt, AC-1) — Staging-Verifikation per IMAP wie in #1102 dokumentiert.
- **AC-1 ist Live-Schicht:** Staging-Mail mit `X-GZ-Format: compact` via `POST /api/trips/{id}/send` + IMAP-Check (gregor-test@henemm.com).
- **Testdatei-Namensregel:** Vertragstest nach Verhalten benennen (z.B. `test_report_config_contract.py`), NICHT nach Issue-Nummer (test_naming_gate).

## Analysis

### Type
Feature (Rework/Struktur-Fix, `type:rework`) — erledigt Bug #1102 mit.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/report_config_resolver.py` | CREATE | `ReportRenderOptions` (frozen dataclass, 8 render-wirksame Felder + opakes `display_config`), `RENDER_NEUTRAL`-Deklaration (19 Felder mit Begründung), `resolve_report_render_options()` (~90–110 LoC) |
| `src/output/renderers/trip_report.py` | MODIFY | `format_email` bekommt optionalen `render_options`-Parameter mit internem Resolver-Fallback; Hand-Ableitungen (129-139) ersetzt; `email_format`/`show_outlook` an `render_email` durchgereicht (~20 LoC) — **Mailgate-Trigger** |
| `src/services/trip_report_scheduler.py` | MODIFY | Resolver einmal aufrufen; 5 Direktzugriffe (637, 744-756, 779-780 Patch-Hack raus, 784, DTO-Bau) auf `options.X` (~30–35 LoC) |
| `src/services/notification_service.py` | MODIFY | `render_options`-Feld im `TripReportRequest`-DTO + Durchreichen (~8 LoC) |
| `tests/tdd/test_report_config_render_contract.py` | CREATE | Vertragstest: `dataclasses.fields()`-parametrisiert, Ebene `format_email`-Ausgabe (nicht Renderer direkt!), Vorbild test_issue_811 |
| Struktur-Test (AC-3) | CREATE | AST-Assertion: Scheduler-Pfad ohne `report_config.`-Direktzugriffe, Vorbild test_765 |

### Scope Assessment
- Files: 4 src + 2 Test
- Estimated src-LoC: ~150–175 (unter Limit 250)
- Risk Level: HIGH (kompletter Briefing-Versand; gewollte Live-Verhaltensänderung: persistiertes `compact` wird erstmals wirksam)

### Technical Approach (Empfehlung Plan-Agent)
- `format_email(render_options=None)` mit Fallback `resolve_report_render_options(...)` intern → Resolver ist der EINZIGE Ableitungspfad; `preview_service` (Scheibe B) bleibt unangefasst kompatibel (Fallback = heutiges Verhalten).
- Tote Toggles seit #790 (`show_quick_take_tags`, `show_highlights`, `daily_summary_metrics`, `show_metrics_summary`) → RENDER_NEUTRAL, NICHT reaktivieren (wäre Verhaltensänderung außerhalb des Issues).
- `display_config` bleibt opak eingebettet (wird heute schon als Ganzes durchgereicht, Lücke existiert nur bei report_config) — PO-Scope-Entscheidung in Spec festhalten.
- `notification_service._send_email` braucht KEINE Änderung: `mail_format` folgt bereits `bool(report.email_html)`; sobald `email_format="compact"` ankommt, wird `X-GZ-Format: compact` automatisch gesetzt.
- Render-wirksam (8): email_format, show_outlook, show_stage_stats, show_stability, show_compact_summary, show_daylight, multi_day_trend_reports→show_multi_day_trend, show_yesterday_comparison. Für show_daylight/show_multi_day_trend liegt das Gate im Scheduler → Vertragstest bildet den Gate-Einzeiler nach (voller Scheduler nicht mock-frei testbar).
- Implementierungs-Reihenfolge: (1) Resolver+RENDER_NEUTRAL → (2) Contract-Test Resolver-Ebene → (3) format_email-Wiring (Mailgate!) → (4) Scheduler+DTO → (5) AC-3-Struktur-Test → (6) Contract-Test auf format_email-Ebene → (7) finaler Mailgate-Nachweis vor Commit.

### Dependencies
- `format_email`-Produktionsaufrufer: genau 2 (`notification_service.py:188`, `preview_service.py:157`) + ~115 Testaufrufe (alle kwargs → additiver Parameter bricht nichts).
- `render_email`-Produktionsaufrufer: genau 1 (`trip_report.py:142`); keine Signaturänderung nötig.

### Open Questions (→ Spec / PO)
- [ ] `_send_service_error_email` (`notification_service.py:802-804`) liest `report_config.send_sms/send_email` direkt — von AC-3 („Scheduler-Pfad") mitziehen oder bewusst auslassen?
- [ ] Bestätigung: `display_config` opak lassen (kein Feld-Aufsplitten) — Scope-Entscheidung.
- [ ] Bestätigung: tote #790-Toggles bleiben tot (RENDER_NEUTRAL), Reaktivierung/Entfernung ist Scheibe B bzw. #1215.
