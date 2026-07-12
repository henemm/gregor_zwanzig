# Context: #1214 Scheibe 5 — Kanal-Renderer (comparison/narrow/compact_summary)

## Request Summary

Issue #1214 Scheibe 5: Die drei verbleibenden Kanal-Renderer `comparison.py`,
`narrow.py`, `compact_summary.py` auf das `metric_format`-Modul umstellen —
verhaltensneutral (wie Scheibe 3). Skalen-Vereinheitlichung ist explizit
Scheibe 6 (PO-Entscheidung).

## Zentraler Analysebefund — Migrationspotential ist kleiner als der Issue-Plan suggeriert

Alle drei Dateien sind **lebendig** (anders als Scheibe 4):
- `comparison.py::render_compare_email` ← `compare_subscription.py:54`, `scheduler_dispatch_service.py:233` (Compare-Versand)
- `narrow.py::render_telegram_bubbles` ← `trip_report.py:189` (Telegram-Briefing)
- `compact_summary.py::CompactSummaryFormatter` ← `trip_report.py:707` (compact-Mail)

Aber der Zahl-für-Zahl-Katalog-Abgleich ergibt: **Nur `comparison.py` hat echte,
byte-identisch migrierbare Formatierungs-Duplikate.** `narrow.py` und
`compact_summary.py` bestehen aus genuinen Sonderregeln (Kategorie b/c der
Scheibe-3-Klassifikation) — dort ist der Liefergegenstand die dokumentierte
Ausnahme-Klassifikation, keine Code-Migration.

## Zahl-für-Zahl-Abgleich comparison.py (Übersichts-Zeilen, Zeilen 88–105)

| Zeile | Hartcodierung | Katalog | Verdict |
|---|---|---|---|
| temp_max | `f"{v:.0f}°C"` | `temperature` decimals=0, unit=°C (ohne Leerzeichen) | ✅ MATCH → `format_value("temperature", v, style="plain")` |
| wind_max | `f"{v:.0f} km/h"` | `wind` decimals=0, unit=km/h (mit Leerzeichen) | ✅ MATCH → `format_value("wind", v, style="plain")` |
| sunny_hours | `f"{v}h"` (int, KEIN Leerzeichen) | `sunshine` decimals=None→0, unit=h — plain ergäbe `"5 h"` | ⚠️ nur via `format_value("sunshine", v, style="bare") + "h"` (Feld ist `Optional[int]`, user.py:170 — bare-Rundung verhaltensneutral) |
| cloud_avg | `f"{v}%"` (int) | `cloud_total` decimals=None→0, unit=% (ohne Leerzeichen) | ✅ MATCH → `format_value("cloud_total", v, style="plain")` (Feld `Optional[int]`, user.py:165) |
| snow_depth_cm | `f"{v:.0f} cm"` | `snow_depth` decimals=0, unit=cm | ✅ MATCH → `format_value("snow_depth", v, style="plain")` |
| snow_new_cm | `f"{v:.0f} cm"` | **kein Katalog-Eintrag** (`snow_new` fehlt) | ❌ Ausnahme — bleibt hartcodiert; Katalog-Lücke als Nebenbefund-Kandidat |

Die Stundenverlaufs-Zeilen (comparison.py:121–127, Kurzformat `"12°"`/`"Gef."`)
sind Kompakt-Spezialsyntax (Grad ohne C, eigene Spalten-Kürzel) — Kategorie b,
keine Migration.

`comparison.py` hat KEINE Ampel-Logik (Plain-Text) — `severity_for` ist hier
nicht anwendbar.

## narrow.py — `_LABELS` (Zeile 246–252) ist KEINE Katalog-Kopie

Delta-Vergleichs-Vokabular für die „Ggü. Vortag"-Telegram-Zeile:
`("precip_sum", "Regen", "mm")` etc. — Abgleich mit Katalog-`label_de`:
`precip_sum`→„Regen" ≠ „Niederschlag", `temp_max`→„Temp max" ≠ „Temperatur",
`temp_min`→„Temp min" ≠ „Temperatur". Nur wind/gust/thunder matchen zufällig.
Zudem: Delta-Werte werden ROH ausgegeben (`f"{delta}{unit}"`, keine Rundung,
Einheit OHNE Leerzeichen) — `format_value` würde runden und Leerzeichen setzen.
**Bewusst kurzes Telegram-Delta-Vokabular = Kategorie b (echte Ausnahme).**
Migration würde Verhalten ändern → nur Klassifikations-Kommentar mit
Katalog-Verweis.

## compact_summary.py — narrative Orchestrierung (Kategorie c)

Alle 5 `_format_*`-Methoden (Zeilen 126, 143, 164, 264, 325) sind
natürlichsprachliche Zusammenfassungs-Logik: Temp-RANGE (`"5–12°C"`,
en-dash, int(round)), eigene Wolken-Emoji-Skala (<20/40/60/80 — weicht von
helpers ≤10/30/70/90 ab, Angleichung = **Scheibe 6/PO**), Regen-Adjektive +
Zeitfenster-Muster (`"trocken, Regen ab 14:00"`), Wind-Adjektive, Thunder-Wörter.
Nichts davon ist katalog-ableitbare Zahl+Einheit-Formatierung.
→ Keine Migration; Klassifikations-Kommentar (Kopf der Formatter-Klasse) mit
Verweis auf metric_format + Scheibe-6-Abgrenzung.

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/renderers/comparison.py:88-105` | Einziger echter Migrations-Kandidat (5 von 6 Zeilen) |
| `src/output/renderers/narrow.py:246-252` | Ausnahme-Klassifikation (Kommentar) |
| `src/output/renderers/compact_summary.py` | Ausnahme-Klassifikation (Kommentar); renderer_mail_gate-Datei! |
| `src/output/metric_format.py` | Ziel-Modul — KEINE Änderung nötig (bare+plain existieren) |
| `src/app/user.py:157-170` | Feld-Typen ComparisonResult (int-Garantien für cloud_avg/sunny_hours) |

## Tests (Bestand, müssen grün bleiben)

- comparison: `test_compare_render_options_resolver.py`, `test_issue_1106_hourly_metrics_config.py`, `test_issue_1105_compare_snow_metric.py`, `test_issue_1107_compare_sections.py`, `test_issue_236_remaining_templates.py`
- compact_summary: `tests/integration/test_compact_summary.py`, `test_issue_807_reproduction.py`
- narrow/Telegram: `test_issue_1001_telegram_bubbles.py`, `test_day_comparison_integration.py`, `test_telegram_footer_metric_gating.py`, `test_multi_day_trend.py`

## Existing Patterns

- Scheibe 2 (`compare_html.py`): `severity_for`-Import + kanonisches→lokales
  Vokabular-Mapping; CV2_METRICS blieb lokal.
- Scheibe 3 (`helpers.fmt_val`): `style="bare"` für nackte Zahlen; Zweig-
  Klassifikation a/b/c in der Spec dokumentiert.

## Risks & Considerations

- **renderer_mail_gate greift** bei compact_summary.py UND comparison.py?
  comparison.py steht NICHT in der Gate-Liste (nur email/*, trip_report,
  sms_trip, compact_summary, alert/*, channels/email). compact_summary.py-Edit
  (auch nur Kommentar) triggert das Gate → Matrix-Test + briefing_mail_validator
  nötig. Operative Fallen: reference_renderer_mailgate_precommit_send_validate
  (Ergänzungen 2026-07-12).
- Verhaltensneutralität beweisen: Vorher/Nachher-Vergleich der gerenderten
  Compare-Plain-Mail (Zeichen-identisch) als Kern-AC.
- `snow_new`-Katalog-Lücke: NICHT in dieser Scheibe nachrüsten (Katalog-Eintrag
  hätte Folgewirkung auf alle Kanäle) — Nebenbefund.
- Kommentar-only-Änderungen an narrow.py/compact_summary.py bewusst minimal
  halten (kein Refactoring-Anreiz).
