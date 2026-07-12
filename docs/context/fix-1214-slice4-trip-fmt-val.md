# Context: #1214 Scheibe 4 — trip_report.py::_fmt_val

## Request Summary

Issue #1214 Scheibe 4 sollte laut Plan `trip_report.py::_fmt_val` zum Thin-Wrapper über
`metric_format.format_value`/`severity_for` machen und dabei drei dokumentierte Divergenzen
beheben (2-Stufen-Highlight statt 4-Stufen-Ampel, toter CAPE-friendly-Pfad, englische
visibility-Wörter entgegen #814 AC-5).

## Zentraler Analysebefund (Root Cause) — ändert den Scheiben-Zuschnitt

**`_fmt_val` ist vollständig toter Code.** Beweiskette:

1. `TripReportFormatter.format_email` delegiert seit beta3 an `render_email()`
   (`trip_report.py:149`) — der echte Trip-Briefing-Pfad (HTML/Plain/Telegram) läuft über
   `src/output/renderers/email/` und nutzt das bereits in Scheibe 3 migrierte
   `helpers.fmt_val`.
2. `_fmt_val` (trip_report.py:695) wird nur von `_render_html_table` (:928) und
   `_render_text_table` (:953) aufgerufen — und **diese beiden haben keinerlei Aufrufer**
   (kein `self._render_html_table`/`self._render_text_table` außerhalb der Definitionen,
   kein Modul-externer Aufruf; `email/html.py::_render_html_table` ist eine eigene,
   lebendige Modul-Funktion, kein Bezug).
3. Issue #778 (Spec `issue_783_776_778_briefing_fixes.md` AC-5) verlangte bereits die
   **ersatzlose Löschung** von fünf toten Methoden: `_fmt_val`, `_render_html_table`,
   `_render_text_table`, `_format_daylight_html`, `_format_daylight_plain`.
4. Die Löschung wurde nie vollzogen. Zwei Blocker:
   - `tests/tdd/test_issue_623_trend_channels.py::test_render_html_table_still_present`
     fordert die Existenz der Methode („still used" — **heute nachweislich falsch**).
   - Ein erheblicher Test-Korpus unit-testet `_fmt_val` direkt (s.u.).
5. `tests/tdd/test_issue_778_dead_code.py::test_dead_formatter_methods_removed` ist
   **vorbestehend kaputt**: prüft den nicht mehr existierenden Pfad
   `src/formatters/trip_report.py` → `FileNotFoundError` (Datei liegt seit dem
   Umzug unter `src/output/renderers/trip_report.py`). Verstößt gegen die
   Kern-Schicht-Regel „nie als vorbestehend rot liegenlassen".
6. #1222 hat den CAPE-friendly-Zweig bereits als tot markiert, aber wegen des
   623-Guards nicht gelöscht (Kommentar trip_report.py:781-784).

**Konsequenz:** Die drei im Intake genannten „Bugs" liegen ausschließlich in totem Code —
kein Nutzer sieht sie. Ein Thin-Wrapper-Umbau (ursprünglicher Scheibe-4-Plan) würde tote
Methoden künstlich am Leben halten. Die korrekte Scheibe 4 ist der **Vollzug von #778**:
ersatzlose Löschung + Triage des anhängenden Test-Korpus.

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/renderers/trip_report.py:695-810, 833-981` | Tote Methoden (5): `_fmt_val`, `_render_html_table`, `_render_text_table`, `_format_daylight_html`, `_format_daylight_plain` — zu löschen. Lebendig bleiben: `format_email` (delegiert an `render_email`), `_generate_compact_summary` (:816, Aufrufer :127), `_should_merge_wind_dir` |
| `src/output/renderers/email/helpers.py::fmt_val` | Kanonische, lebendige Formatierung (Scheibe 3 bereits auf `metric_format` migriert) — Ziel für portierte Tests |
| `src/output/metric_format.py` | Scheibe-1-3-Modul (`format_value`, `severity_for`, style="bare") — hier KEINE Änderung nötig |
| `tests/tdd/test_issue_778_dead_code.py` | Pfad-Fix nötig (`src/formatters/` → `src/output/renderers/`); wird nach Löschung der GREEN-Nachweis |
| `tests/tdd/test_issue_623_trend_channels.py:437` | Veralteter Existenz-Guard `test_render_html_table_still_present` — prüft überholtes Verhalten → löschen (Kern-Schicht-Regel erlaubt das explizit) |

## Test-Korpus, der direkt an den toten Methoden hängt (Triage nötig)

Direkt `formatter._fmt_val(...)`-aufrufende Dateien (Unit-Tests gegen die tote Kopie):

| Testdatei | Hits | Geprüftes Verhalten |
|---|---|---|
| `tests/unit/test_weather_metrics_ux.py` | ~52 | Cloud-Emoji-Skala, CAPE/visibility level-based |
| `tests/integration/test_friendly_format_and_alerts_config.py` | ~25 | friendly-Toggle pro Metrik, visibility-Rundung |
| `tests/integration/test_friendly_format_email_and_alerts.py` | ~14 | dito, plus Alert-Teil (Alert-Teil lebt) |
| `tests/unit/test_configurable_thresholds.py` | ~11 | Gust/Precip-Highlight aus Katalog-Schwellen |
| `tests/tdd/test_issue_623_trend_channels.py` | 4 | Existenz-Guard (veraltet) |
| `tests/integration/test_config_persistence.py` | 3 | visibility/cloud-Format |
| `tests/integration/test_units_legend.py` | 3 | visibility-Rundung |
| `tests/unit/test_issue_347_sunshine_hours.py` | 3+ | Sonnenstunden `"x.x h"` |
| `tests/tdd/test_utc_localtime.py` | 1 | (prüfen: vermutlich Randnutzung) |

Triage-Regel (Analyse-Entscheidung): Verhalten bereits gegen den lebendigen Pfad
(`helpers.fmt_val` / `render_email`) getestet → Duplikat-Test löschen; einzigartig
abgedecktes echtes Produkt-Verhalten → auf `helpers.fmt_val` portieren (Signatur nahezu
identisch: `fmt_val(key, val, friendly_keys=…, html=…, row=…)`); Alt-Verhalten, das nur
die tote Kopie hatte (englische visibility-Wörter, 2-Stufen-Gust-Highlight,
CAPE-Kreis/Dot-friendly) → ersatzlos löschen.

## Vorbestehend roter Test (Intake-Annahme widerlegt)

`tests/red/test_issue_435_format_modes.py::TestAC6SimplifiedWindKuerzel` ruft zwar
`TripReportFormatter().format_email(...)` auf, rendert damit aber über den **echten**
Pfad `render_email` → `helpers.fmt_val`. Er ist rot, weil der simplified-Modus im
**HTML**-Pfad kein Adjektiv-Kürzel rendert (helpers.py: `if mode == "simplified" and not
html`). Das ist ein #435-Feature-Rest, **unabhängig von `_fmt_val`** — Scheibe 4 macht
ihn NICHT grün. Separater Befund für die Nebenbefund-Triage.

## Existing Patterns

- Scheibe-1-3-Architektur (Koexistenz, `style="bare"`, `severity_for`-Vokabular) —
  bleibt unberührt, Scheibe 4 fügt dem Modul nichts hinzu.
- Dead-Code-Löschungen mit Regressionsschutz: Muster in
  `tests/refactor/test_dead_code_scheibe1.py` und `test_issue_778_dead_code.py`
  (Verhaltens-Test vor+nach Löschung grün, Struktur-Test als `# doc-compliance-test`).

## Dependencies

- Upstream (lebendig, bleibt): `render_email`, `helpers.fmt_val`, `metric_format`,
  `compact_summary`.
- Downstream: `notification_service.py:17` und `preview_service.py:202` importieren
  `TripReportFormatter`, nutzen aber nur den lebendigen `format_email`-Pfad — unberührt.

## Existing Specs

- `docs/specs/modules/issue_1214_metric_format_slice3.md` — Scheibe 3 (Known Limitation
  verweist auf Scheibe 4)
- `docs/specs/modules/issue_1214_metric_format_slice1_2.md` — Modul-Spec
- `docs/specs/modules/issue_783_776_778_briefing_fixes.md` AC-5 — ursprüngliches
  Löschungs-Mandat
- `docs/specs/modules/issue_814_ampel_einfach_roh.md` — Verbot englischer Wörter (Z. 114)

## Risks & Considerations

- **Renderer-Mail-Gate #811 greift** (trip_report.py ist Mail-Inhalts-Datei): Mode-Matrix-
  Test + frischer `briefing_mail_validator.py`-Lauf gegen echte Staging-Test-Mail vor Commit.
- Test-Umbau berührt bis zu 9 Testdateien — LoC-Delta beobachten (Löschungen dominieren).
- `test_friendly_format_email_and_alerts.py` mischt toten `_fmt_val`-Teil mit lebendigem
  Alert-Teil — nur chirurgisch die _fmt_val-Klassen anfassen.
- Verhaltens-Regressionsschutz: `test_format_email_renders_after_dead_code_removal`
  (existiert, grün) beweist Unabhängigkeit des echten Pfads von den toten Methoden.
