# Context: fix-954-tg-footer-sms-preview

## Request Summary
Zwei eigenständige Bugs aus der #944-Nachprüfung: (A) die Telegram-Fußzeile
`⚡ … · Sicht … · 0°C-Grenze N m` ignoriert die Metriken-Auswahl und erscheint im
**echten** Versand auch für deaktivierte Metriken; (B) die SMS-**Vorschau** baut
ihren Token-Text divergent und ohne `disabled_specs`, weicht damit vom echten
Versand (mit #944-Fix) ab.

## Related Files
| File | Relevance |
|------|-----------|
| `src/output/renderers/narrow.py` | `_tg_day_footer()` (178–222) baut Fußzeile ungegated; Aufruf in `render_telegram_bubbles()` (402) — hat `dc` zur Hand |
| `src/services/preview_service.py` | `render_sms_preview()` (201–246) baut `token_line` redundant ohne `disabled_specs`; `render_telegram_preview()` (248–272) nutzt `report`-Feld bereits korrekt |
| `src/output/renderers/trip_report.py` | Referenz-Muster (219–234): `_disabled_sms_specs` + `sms_text` mit `disabled_specs`; baut auch `telegram_bubbles` für echten Versand |
| `src/app/models.py` | `UnifiedWeatherDisplayConfig.get_enabled_metric_ids()` (595) — Gating-API für Bug A |

## Existing Patterns
- **#944-Gating (SMS):** deaktivierte Metriken → `MetricSpec(symbol, enabled=False)` als `disabled_specs`, `_visible()` unterdrückt Token. `trip_report.py:219`.
- **Kurzübersicht-Bubble:** iteriert `dc.get_enabled_metric_ids()` (`narrow.py:400`) — die Fußzeile steht in **derselben** Bubble und sollte dieselbe Enabled-Notion nutzen (Konsistenz).
- **Vorschau = Versand-Feld:** `render_telegram_preview()` gibt `report.telegram_bubbles` zurück statt neu zu rendern → dasselbe Muster fehlt bei SMS.

## Dependencies
- Upstream: `TripReportFormatter.format_email()` erzeugt `report.sms_text` (mit `disabled_specs`) und `report.telegram_bubbles`.
- Downstream Bug A: echter Telegram-Versand via `format_email` → `telegram_bubbles`; Telegram-Vorschau nutzt dieselben Bubbles.
- Downstream Bug B: nur `/api/preview/{trip}/sms` (Vorschau), **nicht** der echte SMS-Versand.

## Existing Specs / Tests
- `docs/specs/modules/fix_944_threshold_metricfilter.md` (AC-4, Basis-Muster)
- `tests/tdd/test_issue_944_disabled_metrics_sms.py` (SMS-Versand bereits grün — nicht betroffen)
- `tests/tdd/test_issue_1001_telegram_bubbles.py` (deckt Fußzeile/Bubbles ab — Regressions-Risiko Bug A)

## Design-Entscheidung (für Spec)
- **Bug A:** Fußzeile pro Teil gaten anhand `dc.get_enabled_metric_ids()` — `thunder` → ⚡-Teil, `visibility` → Sicht-Teil, `freezing_level` → 0°C-Grenze-Teil. Konsistent mit der Kurzübersicht derselben Bubble. `dc` an `_tg_day_footer()` durchreichen (bisher nur `segments`).
- **Bug B:** `render_sms_preview()` gibt `report.sms_text` zurück (bereits korrekt gebaut) statt eigenem `SMSTripFormatter()`-Call → konsolidiert Duplikat, entfernt Divergenz.

## Risks & Considerations
- Bug A: `_tg_day_footer()`-Signatur ändert sich (dc-Parameter) → alle Aufrufer/Tests (`test_issue_1001`) prüfen.
- Bug A: Wenn ALLE drei Teile deaktiviert → Fußzeile `None` (kein leerer Separator-Rest). Bestehendes `if not parts: return None` deckt das ab.
- Bug B: `report.email_subject` bleibt Rückgabe-Teil 1 (unverändert), nur `token_line` → `report.sms_text`.
- Metriken-Namen exakt: `thunder`, `visibility`, `freezing_level` (Katalog-IDs verifizieren).
