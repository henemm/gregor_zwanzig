# Context: fix-1486-outlook-silent-exit

Issue: [#1486](https://github.com/henemm/gregor_zwanzig/issues/1486) · Label `bug`, `priority:high`, `area:trips`, `area:reports`
Eigenständiger Rest aus #1388 (dort geschlossen, weil der gemeldete Ausfall an den Etappendaten lag → #1389).

## Request Summary

Der Ausblick-Block („Nächste Etappen") verschwindet an fünf Stellen wortlos aus dem Briefing. Für
den Empfänger sehen alle fünf identisch aus — eine leere Stelle. Er soll stattdessen **seinen
Zustand benennen**, unterscheidbar nach Ursache, und die Störfälle sichtbar protokollieren.

## Der Befund: fünf stille Ausstiege

Alle in `_build_stage_trend()`, `src/services/trip_report_scheduler.py:1370-1458`:

| # | Zeile | Code | Grund | Nutzer-Klasse |
|---|-------|------|-------|---------------|
| 1 | `:1381` | `if not future_stages: return None` | keine Etappe nach Zieldatum | **Information** |
| 2 | `:1387` | `is_within_forecast_horizon(...)` → `continue` | jenseits Vorhersagehorizont (`OPENMETEO_MAX_FORECAST_DAYS`); nur `logger.debug` | **Information** |
| 3 | `:1395` | `if not segments: continue` | Etappe ohne auflösbare Segmente | **Störung** |
| 4 | `:1399` | `if not seg_weather: continue` | keine Wetterdaten (Kontingent erschöpft, #1329/#1348) | **Störung** ⚠️ |
| 5 | `:1425` | `except Exception: logger.warning; continue` | beliebiger Fehler beim Zeilenbau | **Störung** |

Schlusszeile `:1428` `return trend if trend else None` — der Block entfällt ersatzlos.

**Fall 4 ist der gefährlichste:** Bei Kontingent-Engpässen fällt der Ausblick still aus, während
die übrige Mail normal aussieht. Zusammen mit dem Protokoll-Blindfleck des Python-Kerns
(INFO/DEBUG landet nirgends) ist der Ausfall auch im Nachhinein nicht nachweisbar.

## ⚠️ Konflikt mit der Bestands-Spec — PO-Entscheidung nötig

`docs/specs/modules/multi_day_trend.md` (v4.0, Status `implementing`) sagt heute das **Gegenteil**
von dem, was #1486 verlangt:

- **AC-3** (`:37`): „Given eine Tour deren letzte Etappe morgen ist / Then erscheint **kein**
  Trend-Block (kein leeres Heading, kein leerer Block)."
- **C5** (`:109`): „Leerer Trend (0 Etappen) → Block entfällt komplett"
- Edge Cases (`:118`): „0 Etappen → Block entfällt (kein Heading)"

Die Spec deckt ausschließlich Fall 1 ab (0 Etappen) und entscheidet ihn bewusst gegen einen
Hinweis. Die Fälle 2–5 sind dort **gar nicht** behandelt. Diese Spec muss mit dem Fix geändert
werden (Version 5.0) — ein stiller Widerspruch wäre Spec-Erosion.

## Related Files

### Erzeugung
| File | Relevanz |
|------|-----------|
| `src/services/trip_report_scheduler.py:1370-1458` | `_build_stage_trend()` — alle fünf Ausstiege |
| `src/services/trip_report_scheduler.py:879-880` | Aufrufer Versandweg, Gate `render_options.show_multi_day_trend` |
| `src/services/preview_service.py:190-192` | Aufrufer Vorschau-Weg (ADR-0025 / #1297: MUSS identisch bleiben) |
| `src/services/trip_report_scheduler.py:1605` | `_build_thunder_forecast_from_trend_or_fetch` — nutzt Trend-Zeilen wieder (#1275) |
| `src/providers/openmeteo.py` | `is_within_forecast_horizon`, `OPENMETEO_MAX_FORECAST_DAYS` |
| `src/providers/call_log.py:35` | `("_build_stage_trend", "trend")` — Call-Counter-Zuordnung |

### Darstellung — fünf Ausgabewege, alle prüfen auf `if multi_day_trend:`
| File | Zeile | Verhalten heute bei leer/None |
|------|-------|-------------------------------|
| `src/output/renderers/email/html.py` | `1269`, `1305`, `1487` | `trend_html = ""` → Block weg; bei `not multi_day_trend` wird stattdessen `stability_html` gerendert |
| `src/output/renderers/email/plain.py` | `275`, `286-290` | `outlook_active = show_outlook and bool(...)` → Block weg |
| `src/output/renderers/email/compact.py` | `216` | `if multi_day_trend:` → Block weg |
| `src/output/renderers/narrow.py` | `647-650` | Telegram: Ausblick-Bubble entfällt |
| `src/output/renderers/trip_report.py` | `156` | `effective_trend = multi_day_trend if multi_day_trend else None` |
| `src/output/renderers/email/outlook.py` | `build_outlook_row`, `render_outlook_table`, `render_outlook_plain` | geteilte Bausteine (Epic #1301 B4, Trip/Compare) |
| `src/output/renderers/email/__init__.py` | `45`, `107`, `146`, `179` | reicht `multi_day_trend` an html/plain/compact durch |

**Konsequenz:** Ein neuer Zustand muss durch die gesamte Kette gereicht werden
(`_build_stage_trend` → Scheduler/Preview → `trip_report.py` → `email/__init__.py` → 4 Renderer).

## Existing Patterns — das Vorbild ist schon gebaut

**`src/output/renderers/email/unavailable_hint.py`** (Issue #1348/#1349) löst exakt dieselbe
Aufgabe für amtliche Warnungen und ist die Vorlage (DRY-Zwang #1481):

- `any_official_alerts_unavailable(segments)` — Flag-Auswertung, `getattr`-Default fail-soft
- `render_official_alerts_unavailable_html()` — Danger-Box, Tokens `G_BOX_DANGER_BG`/`G_DANGER`,
  bewusst **kein** `G_INK_FAINT` (Design-Leitprinzip Lesbarkeit)
- `render_official_alerts_unavailable_plain(ascii_safe=…)` — `⚠️` für plain, `!!` für compact
- Spec: `docs/specs/modules/warn_unavailable_hint.md`
- Test: `tests/tdd/test_official_alerts_unavailable_hint.py` (echte Objekte statt Mocks)
- Eingebunden in: `html.py:1550`, `plain.py:237`, `compact.py:192`, `narrow.py:589`

Weitere Formulierungs-Vorbilder: `html.py:1125` „Segment N: Wetterdaten nicht verfuegbar",
`radar_service.py:260` „Gewitter-Check nicht verfügbar.",
`trip_command_processor.py:247` „…: Wetterdaten aktuell nicht verfügbar — …"

**Unterschied zum Vorbild:** Dort ist es ein binäres Flag (verfügbar / nicht). Hier gibt es
**drei Nutzer-Klassen** (keine Etappen · zu weit voraus · Störung), die unterschiedlich formuliert
werden sollen.

## Dependencies

- **Upstream:** `trip.get_future_stages()`, `is_within_forecast_horizon()`, `_convert_trip_to_segments()`,
  `_fetch_weather()`, `aggregate_stage()`, `build_outlook_row()`
- **Downstream:** 4 Renderer + `_build_thunder_forecast_from_trend_or_fetch` (#1275 — liest Trend-Zeilen
  per Datum wieder; ein geänderter Rückgabetyp darf das nicht brechen) + `format_trend_tokens` (SMS `TH+:`)
- **Konfiguration:** `report_config_resolver.py:139/151` → `show_multi_day_trend` aus
  `multi_day_trend_reports` (Default `["evening"]`), Modell `src/app/models.py:808`

## Existing Specs

| Spec | Bezug |
|------|-------|
| `docs/specs/modules/multi_day_trend.md` | v4.0 — **muss geändert werden** (AC-3, C5, Edge Cases) |
| `docs/specs/modules/warn_unavailable_hint.md` | Vorbild-Spec für den Hinweis-Baustein |
| Epic #1374, Invariante 2 | „kein stilles Verwerfen" — gilt hier laut Issue genauso |

## Testlücke (aus #1388 übernommen)

- **Kein** Test sichert, dass der Ausblick im **Morgen**-Briefing bei
  `multi_day_trend_reports=["morning"]` erscheint — Golden-Mails decken nur den Abend.
- `tests/integration/test_multi_day_trend.py` — deckt `get_future_stages` inkl. leer (`:320`),
  aber nicht das Mail-Ergebnis.
- `tests/tdd/test_bug_353_trend_horizon.py:139` — **wird durch den Fix rot**: erwartet heute
  `result is None` für Fall 2. Muss auf den neuen Zustand umgestellt werden (kein Löschen —
  die dahinterliegende Zusicherung „kein API-Call für ferne Etappen", `:154`, bleibt gültig).
- `tests/test_output_timezone_guard.py:517-518` — Ausnahme-Schlüssel nennen `_build_stage_trend`
  mit Zeilennummern-Historie; Signaturänderung kann diesen Wächter berühren.

## Risks & Considerations

1. **Spec-Konflikt (s.o.)** — AC-3/C5 sagen das Gegenteil. Ohne PO-Entscheidung kein Fix.
2. **Rückgabetyp-Änderung** trifft zwei Aufrufer und den Thunder-Reuse-Pfad (#1275). Die Vorschau
   (`preview_service.py`) muss zeichengleich bleiben (ADR-0025 / #1297), sonst divergiert sie wieder.
3. **Renderer-Commit-Gate #811** greift: `email/*.py` und `trip_report.py` sind geschützt →
  `tests/tdd/test_issue_811_mode_matrix.py` + `briefing_mail_validator.py` müssen frisch grün sein.
4. **Trip/Compare-Teilung** — `outlook.py` ist ein geteilter Baustein (Epic #1301 B4). Ein
   Compare-Pendant des Hinweises ist zu prüfen, bevor etwas Trip-eigenes entsteht.
5. **`narrow.py` (Telegram)** liegt außerhalb des Mail-Gates, wird aber leicht vergessen.
6. **Protokollierung** — Issue verlangt WARNING statt DEBUG für Fälle 2–5. Memory-Befund:
   der Python-Kern loggt INFO/DEBUG nirgends hin; ob WARNING wirklich ankommt, ist zu messen,
   nicht anzunehmen.
7. **Fall 2 ist keine Störung, sondern Normalfall** bei langen Touren (Etappe 20 liegt immer
   jenseits von today+15). Ein Danger-Styling wäre hier falsch — Formulierung/Optik muss die
   drei Klassen unterscheiden.
