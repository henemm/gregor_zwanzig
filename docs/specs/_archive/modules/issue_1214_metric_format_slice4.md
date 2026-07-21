---
entity_id: issue_1214_metric_format_slice4
type: module
created: 2026-07-12
updated: 2026-07-12
status: draft
version: "1.0"
tags: [metric-format, trip-briefing, dead-code, konsolidierung, issue-1214]
---

# Metric-Format-Konsolidierung — Scheibe 4 (Dead-Code-Vollzug `trip_report.py`)

## Approval

- [ ] Approved

## Purpose

Issue #1214 Scheibe 4 vollzieht die in Issue #778 (Spec `issue_783_776_778_briefing_fixes.md` AC-5) bereits mandatierte, aber nie durchgeführte ersatzlose Löschung von fünf toten Methoden aus `TripReportFormatter` (`src/output/renderers/trip_report.py`). `format_email` delegiert seit beta3 vollständig an `render_email()` (den in Scheibe 3 auf `metric_format`/`helpers.fmt_val` migrierten lebendigen Pfad); `_fmt_val` und die vier von ihr abhängigen Render-Methoden haben keinen einzigen Aufrufer mehr. Dies existiert, um totem Code nicht künstlich am Leben zu erhalten (ursprünglicher Plan war ein Thin-Wrapper-Umbau von `_fmt_val` — durch die Analyse widerlegt, siehe `docs/context/fix-1214-slice4-trip-fmt-val.md`) und den daran hängenden, teils vorbestehend kaputten Test-Korpus zu bereinigen.

## Source

- **File:** `src/output/renderers/trip_report.py`
- **Identifier:** `TripReportFormatter._fmt_val`, `_render_html_table`, `_render_text_table`, `_format_daylight_html`, `_format_daylight_plain`

**Schicht:** Python-Core/Domain-Backend (`src/output/`) — kein Frontend, keine Go-API betroffen.

## Estimated Scope

- **LoC:** `trip_report.py` ca. -250 LoC (reine Löschung, 5 Methoden Zeile 695-981 abzüglich der dazwischenliegenden lebendigen `_generate_compact_summary`/`_shorten_stage_name`, plus 2 ungenutzt werdende Imports); Test-Korpus ca. -300/+80 LoC über bis zu 9 Testdateien (Löschungen dominieren)
- **Files:** 1 Quelldatei + bis zu 9 Testdateien
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/renderers/email/helpers.py` (`fmt_val`) | module | Kanonischer, lebendiger Formatierungspfad (Scheibe 3) — Ziel für portierte Tests aus dem toten Test-Korpus |
| `src/output/metric_format.py` | module | Scheibe-1-3-Modul — bleibt in dieser Scheibe **unverändert** |
| `src/output/renderers/email/render_email` | module | Lebendiger Render-Pfad, an den `format_email` delegiert — bleibt unverändert, muss nach Löschung weiter fehlerfrei funktionieren |
| `tests/tdd/test_issue_778_dead_code.py` | test | Vorbestehend kaputt (`FileNotFoundError` auf `src/formatters/trip_report.py`) — Pfad-Fix macht ihn zum GREEN-Nachweis dieser Scheibe |
| `tests/tdd/test_issue_623_trend_channels.py` (`test_render_html_table_still_present`) | test | Veralteter Existenz-Guard — zu löschen |
| `tests/unit/test_weather_metrics_ux.py`, `tests/integration/test_friendly_format_and_alerts_config.py`, `tests/integration/test_friendly_format_email_and_alerts.py`, `tests/unit/test_configurable_thresholds.py`, `tests/integration/test_config_persistence.py`, `tests/integration/test_units_legend.py`, `tests/unit/test_issue_347_sunshine_hours.py`, `tests/tdd/test_utc_localtime.py` | test | Rufen `formatter._fmt_val(...)` direkt auf — Triage nötig (Duplikat löschen / auf `helpers.fmt_val` portieren / Alt-Verhalten ersatzlos löschen) |
| `.claude/hooks/renderer_mail_gate.py` | gate | Greift ECHT, da `trip_report.py` eine Mail-Inhalts-Datei ist (Renderer-Mail-Gate #811) — blockiert Commit ohne frischen `test_issue_811_mode_matrix.py`-Lauf + `briefing_mail_validator.py`-Nachweis gegen eine echte, frisch versendete Trip-Briefing-Test-Mail (Implementierungsdetail, kein AC) |
| `src/services/notification_service.py:17`, `src/services/preview_service.py:202` | module | Importieren `TripReportFormatter`, nutzen ausschließlich den lebendigen `format_email`-Pfad — unberührt von dieser Scheibe |

## Implementation Details

**Zu löschende tote Methoden in `trip_report.py`** (Beweiskette: `format_email` → `render_email()`, Zeile 149; keine der fünf Methoden hat einen Aufrufer außerhalb der Definitionen selbst):

| Methode | Zeilen (Ist-Stand) |
|---|---|
| `_fmt_val` | 695–810 |
| `_format_daylight_html` | 833–887 |
| `_format_daylight_plain` | 888–927 |
| `_render_html_table` | 928–943 |
| `_render_text_table` | 953–981 |

Dazwischenliegend bleiben **unverändert erhalten**: `_generate_compact_summary` (Zeile 816, Aufrufer Zeile 127), `_shorten_stage_name` (Zeile 944, außerhalb dieser Scheibe — nicht Teil der #778-Löschliste) und `format_email` selbst.

**Ungenutzt werdende Imports nach Löschung** (verifiziert: jeweils nur innerhalb der zu löschenden Methoden referenziert):
- `from utils.geo import degrees_to_compass` (Zeile 25) — einzige Nutzung Zeile 716 und 809, beide in `_fmt_val`.
- `from src.output.renderers.email.helpers import ampel_dot, build_friendly_keys` (Zeile 48) — `ampel_dot` einzige Nutzung Zeile 785 in `_fmt_val` → aus dem Import entfernen; `build_friendly_keys` bleibt (Aufrufer Zeile 101, außerhalb `_fmt_val`).

**Explizit NICHT zu entfernen:** `ThunderLevel` (weitere Aufrufer Zeile 360, 501), `local_fmt` (weitere Aufrufer u.a. Zeile 504, 525, 562, 632), `DaylightWindow` (Konstruktor-Parametertyp Zeile 70), `get_metric` (weitere Aufrufer u.a. Zeile 510, 547, 574, 585), `_visible_cols` (weiterer Aufrufer Zeile 457) — alle bleiben durch lebendige Aufrufstellen außerhalb der gelöschten Methoden erforderlich.

**`tests/tdd/test_issue_778_dead_code.py` Pfad-Fix:** `_TRIP_REPORT`-Konstante zeigt auf den nicht mehr existierenden Pfad `src/formatters/trip_report.py` (Umzug seit beta3) → korrigieren auf `src/output/renderers/trip_report.py`. Danach ist `test_dead_formatter_methods_removed` (aktuell `# doc-compliance-test`, RED weil Datei nicht gefunden wird) der Struktur-Nachweis der Löschung, `test_format_email_renders_after_dead_code_removal` der bereits grüne Verhaltens-Regressionsschutz.

**`tests/tdd/test_issue_623_trend_channels.py::test_render_html_table_still_present`** (Zeile 437-441, Klasse `TestDeadCodeRemoved`): behauptet `_render_html_table` sei „still used" — nachweislich falsch (siehe Beweiskette oben). Wird ersatzlos gelöscht; die beiden Schwester-Tests derselben Klasse (`test_render_html_method_gone`, `test_render_plain_method_gone`) bleiben unverändert bestehen.

**Test-Korpus-Triage** (9 Dateien, direkte `formatter._fmt_val(...)`-Aufrufe gegen die tote Kopie) nach der in der Analyse festgelegten Regel:
1. **Duplikat löschen** — Verhalten bereits identisch gegen den lebendigen Pfad (`helpers.fmt_val` / `render_email`) abgedeckt.
2. **Auf `helpers.fmt_val` portieren** — einzigartig abgedecktes echtes Produktverhalten ohne Äquivalent im lebendigen Pfad (Signatur nahezu identisch: `fmt_val(key, val, friendly_keys=…, html=…, row=…)`).
3. **Ersatzlos löschen** — Alt-Verhalten, das ausschließlich die tote Kopie hatte und im lebendigen Pfad bewusst anders/nicht existiert: englische visibility-Wörter (`good`/`fair`/`poor`/`⚠️ fog`, verstößt gegen #814 AC-5 Verbot englischer Wörter), 2-Stufen-Gust-Highlight (`_fmt_val` Zeile 720-724 vs. 4-Stufen-Ampel im lebendigen Pfad), toter CAPE-friendly-Dot-Pfad (`_fmt_val` Zeile 785, laut Kommentar Zeile 781-784 selbst schon als tot markiert, #1222).

Betroffene Dateien: `tests/unit/test_weather_metrics_ux.py`, `tests/integration/test_friendly_format_and_alerts_config.py`, `tests/integration/test_friendly_format_email_and_alerts.py` (nur die `_fmt_val`-Klassen anfassen, Alert-Teil bleibt unberührt), `tests/unit/test_configurable_thresholds.py`, `tests/integration/test_config_persistence.py`, `tests/integration/test_units_legend.py`, `tests/unit/test_issue_347_sunshine_hours.py`, `tests/tdd/test_utc_localtime.py` (Einzelfall-Prüfung, vermutlich Randnutzung).

**KEINE Änderung** an `src/output/metric_format.py` und keine Verhaltensänderung im echten Render-Pfad (`render_email` → `helpers.fmt_val`).

## Expected Behavior

- **Input:** `TripReportFormatter().format_email(...)` mit echten Segmentdaten (E-Mail HTML/Plain, Telegram-Trip-Briefing).
- **Output:** Identischer HTML-/Plain-/Telegram-Output wie vor der Löschung — `format_email` delegiert unverändert an `render_email()`, das nie über `_fmt_val` lief. Kein für Nutzer sichtbarer Unterschied.
- **Side effects:** Keine. `TripReportFormatter` verliert fünf nie aufgerufene Methoden; keine Instanzattribute, kein State, kein I/O betroffen.

## Acceptance Criteria

- **AC-1:** Given `src/output/renderers/trip_report.py` nach der Löschung / When die Datei nach den fünf toten Methodendefinitionen durchsucht wird / Then existiert keine der fünf `def`-Definitionen (`_fmt_val`, `_render_html_table`, `_render_text_table`, `_format_daylight_html`, `_format_daylight_plain`) mehr, während `format_email`, `_generate_compact_summary` und `_should_merge_wind_dir` unverändert vorhanden bleiben.
  - Test: `tests/tdd/test_issue_778_dead_code.py::test_dead_formatter_methods_removed` (nach Pfad-Fix auf `src/output/renderers/trip_report.py`) läuft grün.

- **AC-2:** Given ein echtes Segment mit Stundenreihe / When `TripReportFormatter().format_email(...)` vor UND nach der Löschung aufgerufen wird / Then entsteht in beiden Fällen identischer, nicht-leerer HTML- und Plain-Output ohne `AttributeError`/`KeyError` — der lebendige Render-Pfad hängt nachweislich nicht von den toten Methoden ab.
  - Test: `tests/tdd/test_issue_778_dead_code.py::test_format_email_renders_after_dead_code_removal` bleibt grün (bereits vor der Löschung grün, muss es danach bleiben).

- **AC-3:** Given die neun Testdateien, die vor dieser Scheibe direkt `formatter._fmt_val(...)` gegen die tote Kopie aufrufen / When die Triage abgeschlossen ist / Then ruft keine verbleibende Testdatei mehr `formatter._fmt_val` auf; einzigartiges Verhalten (2-Stufen-Gust-Highlight, CAPE-friendly-Dot, englische visibility-Wörter) ist entweder auf `helpers.fmt_val`-Äquivalente portiert oder als bewusst nicht mehr existierendes Alt-Verhalten dokumentiert-gelöscht.
  - Test: `grep -rn "\._fmt_val(" tests/` liefert keine Treffer mehr; die portierten Ersatztests (z.B. gegen `helpers.fmt_val` für Cloud-Emoji-Skala, Sonnenstunden `"x.x h"`, Gust/Precip-Highlight aus Katalog-Schwellen) laufen grün.

- **AC-4:** Given `tests/tdd/test_issue_623_trend_channels.py::TestDeadCodeRemoved` / When der veraltete Guard `test_render_html_table_still_present` gelöscht wird / Then bleiben die beiden Schwester-Tests `test_render_html_method_gone` und `test_render_plain_method_gone` unverändert grün.
  - Test: `tests/tdd/test_issue_623_trend_channels.py` läuft vollständig grün, ohne dass `test_render_html_table_still_present` noch existiert.

- **AC-5:** Given der gesamte Kern-Test-Korpus (deterministisch, ohne Netz/Live-Dienste) nach Abschluss aller Löschungen und Portierungen / When die betroffenen Testdateien sowie `tests/tdd/test_issue_811_mode_matrix.py` (Renderer-Mail-Gate #811) ausgeführt werden / Then sind alle grün, mit Ausnahme des vorbestehend roten, unabhängigen `tests/red/test_issue_435_format_modes.py::TestAC6SimplifiedWindKuerzel` (bekannter #435-Feature-Rest im lebendigen Pfad, nicht Teil dieser Scheibe).
  - Test: gezielter Lauf der in dieser Spec genannten Testdateien (Kern-Schicht, keine Vollsuite wegen bekannter Cross-Test-Pollution) zeigt 0 unerwartete Fehlschläge.

## Known Limitations

- `tests/red/test_issue_435_format_modes.py::TestAC6SimplifiedWindKuerzel` bleibt rot — er testet den echten `render_email`-Pfad (simplified-Kürzel im HTML nie implementiert für den HTML-Zweig, `helpers.py`: `if mode == "simplified" and not html`), unabhängig von `_fmt_val` und dieser Scheibe. Kein Scheibe-4-Blocker, separater Befund für die Nebenbefund-Triage.
- `_shorten_stage_name` (Zeile 944 in `trip_report.py`, zwischen `_render_html_table` und `_render_text_table`) hat ebenfalls keinen erkennbaren Aufrufer innerhalb der Datei (eigene Kopie existiert in `compact_summary.py`), ist aber nicht Teil der #778-Löschliste und wird in dieser Scheibe **nicht** angefasst — keine stille Scope-Erweiterung ohne eigene Analyse.
- Diese Scheibe fügt `src/output/metric_format.py` nichts hinzu und ändert keine Formatierungslogik im lebendigen Pfad — reine Dead-Code-Entfernung plus Test-Korpus-Bereinigung.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine [no-adr]
- **Rationale:** Reine ersatzlose Entfernung von nachweislich totem Code (kein Aufrufer, seit #778 mandatiert) plus begleitende Testbereinigung. Keine neue Abstraktion, keine Schnittstellenänderung, kein Verhaltenswechsel im lebendigen Render-Pfad, keine neue externe Abhängigkeit, keine Schema-/Persistenzänderung. Kein architekturrelevanter Entscheidungsbedarf.

## Changelog

- 2026-07-12: Initial spec created
