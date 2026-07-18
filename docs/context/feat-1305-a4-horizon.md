# Context: feat-1305-a4-horizon

## Request Summary

Scheibe A4 aus Epic #1301 (Issue #1305): Der Ortsvergleich holt seit A2 (#1303) alle Daten über den weltweiten Dienst (max. 15 Tage), fordert aber weiterhin nur `forecast_hours=48` an. PO-Entscheid 2026-07-18: **Horizont auf 4 Tage (96 h)** anheben — synchron an Versand und Vorschau, über einen geteilten Weg (Divergenz = Fehlerklasse #1297). Die hartkodierte Kopf-Zelle `"+48h"` in der Vergleichs-Mail **entfällt** (PO-Entscheid, konsistent mit #1268-Begründung für die entfallene Zeitfenster-Zeile).

## Related Files

| File | Relevance |
|------|-----------|
| `src/services/scheduler_dispatch_service.py:351` | Versandpfad: `forecast_hours=48` fest (Kommentar #1268) |
| `src/services/compare_preview_service.py:152` | Vorschau: `forecast_hours=48` fest; Kommentar `:141-147` verlangt ausdrücklich Gleichheit mit Versand |
| `src/services/comparison_engine.py:45` | Default `forecast_hours: int = 48` in `ComparisonEngine.run` |
| `src/services/comparison_engine.py:308` | Default `hours: int = 48` in `fetch_forecast_for_location` |
| `src/output/renderers/email/compare_html.py:686` | `horizont_val = "+48h"` hartkodiert; Zellen-Einbau Desktop `:704-709` (4×25%), Mobile `:717` (Zeile 2: Horizont+Erstellt) |
| `src/providers/openmeteo.py:155` | `OPENMETEO_MAX_FORECAST_DAYS = 15` — API-Obergrenze; 96 h liegt weit darunter |
| `src/services/forecast.py:59-90` | `get_forecast(hours_ahead)` → `end = now + timedelta(hours=hours_ahead)` — Stunden werden 1:1 zum Abruffenster |

## Betroffene Bestandstests (schreiben 48 fest)

| Test | Was er festschreibt |
|------|--------------------|
| `tests/tdd/test_compare_html_email.py:384-406` (`test_ac6_header_zeigt_48h_horizont`) | `"+48h" in html` (Spec #1268 AC-6) — **kollidiert direkt** mit dem Entfall der Kachel; Test prüft veraltetes Verhalten → anpassen (Kachel weg, kein `+96h`-Ersatz) |
| `tests/tdd/test_compare_dispatch_fixed_window.py` | `recorded.forecast_hours == 48` (mehrfach) — Kernaussage „fest, Preset-Wert egal" bleibt, Zahl wird 96 |
| `tests/tdd/test_compare_preview_service.py:365` | Vorschau übergibt `forecast_hours == 48` — Zahl wird 96 |
| `tests/tdd/test_issue_764_compare_forecast_hours_consume.py` | Historie #764→#1268: Dispatch gibt unter allen Preset-Varianten fest 48 weiter — Zahl wird 96 |
| `tests/tdd/test_compare_preset_loader.py`, `test_compare_sun_hours_full_day_window.py`, `tests/unit/test_compare_matrix_metric_selection.py` | enthalten `forecast_hours=48` als Fixture-Beiwerk — prüfen, meist nur Testdaten |

## Existing Patterns

- **Geteilte Konstante gegen Drift:** `OPENMETEO_MAX_FORECAST_DAYS` (`openmeteo.py:155`) ist das Vorbild — Modul-Konstante mit Begründungs-Kommentar. A4 braucht eine Konstante `COMPARE_FORECAST_HOURS = 96` an EINER Stelle, die Versand + Vorschau (und sinnvollerweise die Engine-Defaults) beziehen.
- **Kachel-Entfall:** #1268 hat die Zeitfenster-Zeile im Kopf ersatzlos entfernt (Kommentar `compare_html.py:679-681`) — gleiche Begründung, gleiches Muster für die Horizont-Kachel. Layout: Desktop von 4×25% auf 3 Zellen, Mobile-Zeile 2 behält nur „Erstellt".
- **Vorschau = Versand:** Kommentar `compare_preview_service.py:141-147` (#1268 AC-11) verlangt wörtlich identische Werte — der geteilte Bezug ersetzt den Kommentar-Appell durch Struktur.

## Dependencies

- Upstream: `ForecastService.get_forecast(hours_ahead)` → `OpenMeteoProvider.fetch_forecast(start, end)`; API-Grenze 15 Tage (#353), 96 h unkritisch.
- Downstream: `ComparisonEngine.run` filtert `raw_data` auf `target_date` + Fenster (0,23) — mehr Stunden ändern die Zieltag-Auswertung NICHT, sie erweitern nur den abgedeckten Datumsbereich (Vorschau mit Zieldatum bis +3 Tage liefert dann Daten statt leer). Gewitter-Ausblick (#1297-Fix) bezieht sich aus derselben Quelle — profitiert mit.
- Mail-Validatoren: `email_spec_validator.py` prüft die Horizont-Kachel NICHT (verifiziert per grep) — kein Validator-Konflikt.

## Existing Specs

- `docs/specs/modules/`-Spec zu #1268 (fixe Fenster) — AC-6 („Kachel zeigt +48h") wird durch A4 bewusst abgelöst; in der neuen Spec dokumentieren.
- Epic-Plan: `~/.claude/plans/warum-verweist-du-immer-crispy-ladybug.md`, Abschnitt A4.

## Risks & Considerations

- **Renderer-Commit-Gate #811:** `compare_html.py` ist gestaged → Gate verlangt `test_issue_811_mode_matrix.py` grün + frischen `briefing_mail_validator.py`-Lauf VOR Commit (echte Staging-Test-Mail).
- **Datenvolumen:** 96 h statt 48 h ≈ doppelte Antwortgröße pro Ort — bei Open-Meteo kostenlos, Callzahl unverändert. Unkritisch.
- **Kein UI-Feld:** `forecast_hours` bleibt bewusst kein Editor-Feld (#1268/#1268-C2-Datenerhalt); persistierte Alt-Werte bleiben ignoriert. A4 ändert NUR den festen Wert.
- **Vier Nennungen der Zahl:** Versand, Vorschau, zwei Engine-Defaults — alle auf die geteilte Konstante ziehen, sonst bleibt Drift-Potential.
- **#1268 AC-6-Test:** muss im selben Commit angepasst werden, sonst Kern-Suite rot.
