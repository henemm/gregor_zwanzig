# Context: Vortag-Vergleich F4 (#750) + F6 (#752)

## Request Summary
Den Vortag-Vergleich ans echte Briefing anschließen: F4 (#750) integriert ihn in den
Scheduler + E-Mail-Pfad, F6 (#752) ergänzt eine Telegram-Kurzform. Die Bausteine
F1 (#747 Snapshot-Speicher), F2 (#748 `DayComparisonService`) und F3 (#749 Renderer)
sind bereits in `origin/main` gemergt.

## Epic-Stand
| Slice | Issue | Status |
|-------|-------|--------|
| F1 datierter Snapshot-Speicher | #747 | ✅ closed (`save_dated`/`load_dated`) |
| F2 Delta-Berechnung (DTO) | #748 | ✅ closed (`DayComparisonService`) |
| F3 E-Mail-Renderer-Sektion | #749 | ✅ closed — aber Funktionen **verwaist** (s.u.) |
| **F4 Scheduler-Integration** | **#750** | **dieser Workflow** |
| F5 Frontend-Toggle | — | OOS |
| **F6 Telegram-Kurzform** | **#752** | **dieser Workflow** |

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_report_scheduler.py` | `_send_trip_report()` Z.351 — `save_dated` schon da (Z.552); muss Vortag **laden** + `DayComparisonService.compare()` aufrufen + `day_comparison` an `format_email` reichen |
| `src/formatters/trip_report.py` | `format_email()` Z.52 — neues optionales `day_comparison`-Arg, durch `render_email` (Z.134) **und** `render_narrow` (Z.176) durchreichen |
| `src/app/models.py` | `TripReportConfig` Z.680 — neues `show_yesterday_comparison: bool = True` (neben `show_outlook` Z.733) |
| `src/services/day_comparison.py` | F2-DTO: `DayComparison`, `DayComparisonEntry`, `MetricDelta`, `ComparisonDirection`, `DayComparisonService.compare(today, yesterday)` |
| `src/services/weather_snapshot.py` | `load_dated(trip_id, date)` Z.118 → `Optional[List[SegmentWeatherData]]` (None wenn fehlt) |
| `src/output/renderers/email/__init__.py` | `render_email()` Z.32 — kein `day_comparison`-Param; ruft `render_html`/`render_plain` |
| `src/output/renderers/email/html.py` | `render_day_comparison_html()` Z.852 — **verwaist** (nirgends aufgerufen) |
| `src/output/renderers/email/plain.py` | `render_day_comparison_plain()` Z.341 — **verwaist** |
| `src/output/renderers/narrow.py` | `render_narrow()` Z.313 — kein `day_comparison`-Param; F6 ergänzt "Vortag:"-Zeile |

## Existing Patterns
- **Toggle-Ableitung:** `format_email` liest Toggles defensiv aus `report_config` mit
  `... if report_config else <default>` (Z.120–131). Neues Toggle analog.
- **Optionale kwargs durchreichen:** `render_email` reicht alle Toggles als explizite
  kwargs an `render_html`/`render_plain` weiter (Z.97 ff.). Determinismus-Vertrag:
  gleiche Inputs → bit-identisches `(html, plain)`.
- **Snapshot-Mandantentrennung:** `WeatherSnapshotService(self._user_id)` — bereits so
  beim `save_dated` (Z.550). Laden muss denselben `user_id` nutzen.
- **fail-soft:** Snapshot-Save ist in `try/except` gekapselt (Z.548–554). Laden +
  Compare ebenso (kein Absturz, kein Log-Spam wenn Vortag fehlt).
- **Renderer = pure functions**, geben `''` zurück wenn `comparison is None`/leer
  (s. `render_day_comparison_plain` Z.349).

## Dependencies
- **Upstream:** `DayComparisonService` (#748), `load_dated` (#747), Renderer-Funktionen (#749).
- **Downstream:** E-Mail-HTML+Plain-Versand, Telegram-`telegram_text`. Beide laufen über
  `_send_trip_report`.

## Existing Specs / Tests
- `docs/specs/modules/issue_748_day_comparison_service.md` (F2)
- `tests/tdd/test_day_comparison_service.py`, `tests/tdd/test_day_comparison_renderer.py`
- Story: `docs/project/backlog/stories/story-vortag-vergleich.md`

## Risks & Considerations
1. **Verwaiste #749-Funktionen:** `render_day_comparison_html/plain` sind nirgends
   verdrahtet. F4 muss sie über `render_email → render_html/render_plain` einbinden —
   `#750`s "Betroffene Dateien" listet die Renderer **nicht**, ist also unvollständig.
   Ohne diese Verdrahtung erscheint die Sektion in der Mail nicht.
2. **AC-Wording-Drift #750:** Issue nennt `load_for_date()`; die reale Methode heißt
   `load_dated()`. Spec gegen Code abgleichen.
3. **Gemeinsame Compare-Berechnung:** Sowohl E-Mail (F4) als auch Telegram (F6) brauchen
   dieselbe `DayComparison`. Im Scheduler **einmal** berechnen und an `format_email`
   reichen, das sie an E-Mail-Renderer **und** `render_narrow` weitergibt.
4. **F6-Scope:** `render_narrow` braucht neuen `day_comparison`-Param + neue Logik
   (max 3 Metriken, absteigend nach Abweichung, entfällt komplett wenn None).
5. **Backward-Compat:** Alte `TripReportConfig` ohne neues Feld laden weiter (Default
   `True`). `day_comparison`-Arg überall optional mit Default `None`.
6. **LoC:** #750 ~60 + #752 ~50 = ~110 LoC < 250-Limit. Renderer-Verdrahtung kommt dazu.
