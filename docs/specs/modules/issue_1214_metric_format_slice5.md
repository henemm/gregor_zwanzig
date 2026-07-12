---
entity_id: issue_1214_metric_format_slice5
type: module
created: 2026-07-12
updated: 2026-07-12
status: draft
version: "1.0"
tags: [metric-format, compare, telegram, konsolidierung, issue-1214]
---

# Metric-Format-Konsolidierung — Scheibe 5 (Kanal-Renderer comparison/narrow/compact_summary)

## Approval

- [ ] Approved

## Purpose

Issue #1214 Scheibe 5 migriert die fünf byte-identisch migrierbaren Übersichts-Zeilen von `comparison.py::render_comparison_text` (Zeilen 88–105) auf `src/output/metric_format.py::format_value`, und dokumentiert für `narrow.py` sowie `compact_summary.py` explizit, warum dort **keine** Migration stattfindet. Dies existiert, um die in Scheibe 1–3 begonnene Konsolidierung so weit wie ohne Verhaltensänderung möglich auszudehnen, ohne — anders als der ursprüngliche Issue-Plan suggerierte — genuine Sonderregeln (Telegram-Delta-Vokabular, narrative Kompakt-Zusammenfassung) künstlich in den Katalog zu pressen. Skalen-Vereinheitlichung (z. B. compact_summary-Wolken-Skala) ist bewusst PO-Entscheidung und Gegenstand von Scheibe 6.

## Source

- **File:** `src/output/renderers/comparison.py` (Migration), `src/output/renderers/narrow.py` (Klassifikations-Kommentar), `src/output/renderers/compact_summary.py` (Klassifikations-Kommentar)
- **Identifier:** `render_comparison_text` (comparison.py), `_LABELS` in der Delta-Sammel-Funktion (narrow.py:246–252), `CompactSummaryFormatter` (compact_summary.py:28)

**Schicht:** Python-Core/Domain-Backend (`src/output/`) — kein Frontend, keine Go-API betroffen.

## Estimated Scope

- **LoC:** `comparison.py` ~15-25 LoC Diff (5 Zeilen umgestellt), `narrow.py` ~5-8 Kommentar-LoC, `compact_summary.py` ~5-8 Kommentar-LoC, neue Testdatei ~50-70 LoC
- **Files:** 3 Quelldateien + 1 neue Testdatei
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/metric_format.py` (`format_value`) | module | Scheibe-1-3-Modul — bleibt in dieser Scheibe **unverändert** (`style="plain"`/`style="bare"` existieren bereits) |
| `src/app/user.py:157-171` (`ComparisonResult`) | model | Feld-Typen-Referenz: `cloud_avg`/`sunny_hours` sind `Optional[int]`, `temp_max`/`wind_max`/`snow_depth_cm`/`snow_new_cm` sind `Optional[float]` |
| `compare_subscription.py:54`, `scheduler_dispatch_service.py:233` | caller | Lebendige Aufrufer von `render_comparison_text` (Compare-Versand) — dürfen nach der Migration keinen anderen Output erzeugen |
| `trip_report.py:189` (`render_telegram_bubbles`), `trip_report.py:707` (`CompactSummaryFormatter`) | caller | Lebendige Aufrufer von `narrow.py`/`compact_summary.py` — unberührt, da beide Dateien nur Kommentare erhalten |
| `.claude/hooks/renderer_mail_gate.py` | gate | Greift ECHT bei `compact_summary.py` (steht in der Gate-Dateiliste #811) — jede Änderung, auch reiner Kommentar, verlangt vor dem Commit einen frischen `test_issue_811_mode_matrix.py`-Lauf + `briefing_mail_validator.py`-Nachweis gegen eine echte, frisch versendete Trip-Briefing-Test-Mail (Implementierungsdetail, kein AC). `comparison.py` steht NICHT in der Gate-Liste. |

## Implementation Details

**Migration `comparison.py` render_comparison_text (Zeilen 88–105), Zahl-für-Zahl:**

| Zeile (Ist) | Feld | Bisherige Hartcodierung | Feldtyp | Neue Formulierung |
|---|---|---|---|---|
| 90 | `temp_max` | `f"{v:.0f}°C"` | `Optional[float]` | `format_value("temperature", v, style="plain")` |
| 93 | `wind_max` | `f"{v:.0f} km/h"` | `Optional[float]` | `format_value("wind", v, style="plain")` |
| 96 | `sunny_hours` | `f"{v}h"` (kein Leerzeichen vor „h") | annotiert `Optional[int]`, **zur Laufzeit float** | **bleibt unverändert** — Adversary-F001, s.u. |
| 99 | `cloud_avg` | `f"{v}%"` | `Optional[int]` | `format_value("cloud_total", v, style="plain")` |
| 102 | `snow_depth_cm` | `f"{v:.0f} cm"` | `Optional[float]` | `format_value("snow_depth", v, style="plain")` |
| 105 | `snow_new_cm` | `f"{v:.0f} cm"` | `Optional[float]` | **bleibt unverändert** — kein `snow_new`-Eintrag im Katalog (dokumentierte Ausnahme, siehe Known Limitations) |

Begründung `sunny_hours` (Fakten-Korrektur nach Adversary-F001, 2026-07-12): Die ursprüngliche Annahme „`Optional[int]`" (Typ-Annotation user.py:170) ist zur LAUFZEIT falsch — `WeatherMetricsService.calculate_sunny_hours()` (weather_metrics.py:298) liefert `float` mit 1 Dezimale und wird an beiden Zuweisungsstellen (comparison_engine.py:153/:466) ohne Cast übernommen. Die Live-Mail zeigt also z. B. `"4.7h"`/`"5.0h"`. `format_value("sunshine", ..., style="bare")` würde wegen Katalog-`decimals=None`→0 auf `"5h"` runden = sichtbare Verhaltensänderung (AC-1-Bruch). Die Zeile bleibt daher unmigriert (dokumentierte Ausnahme wie `snow_new_cm`); die Katalog-`decimals`-Lücke für `sunshine` ist Nebenbefund-Kandidat.

Die Zeilen-Labels (`"Temp max:"`, `"Wind:"`, `"Sonne:"`, `"Wolken:"`, `"Schneehöhe:"`, `"Neuschnee:"`) und die `if x is not None else "   Label: -"`-Fallback-Struktur bleiben **unverändert lokal** — sie sind Aggregat-Anzeige-Semantik (Vergleichsübersicht über mehrere Orte), keine Katalog-`label_de`-Duplikate. `render_comparison_text` hat keine Ampel-Logik (reiner Plain-Text-Report) — `severity_for` ist hier nicht anwendbar und wird nicht eingeführt.

Die Stundenverlaufs-Zeilen (comparison.py:121–127: `f"{dp.t2m_c:.0f}°"`, Kurzform ohne „C", `"Gef."`-Kürzel, `f"{dp.wind10m_kmh:.0f}"` ohne Einheit, `f"{dp.cloud_total_pct}%"`) sind Kompakt-Spezialsyntax für die kombinierte Mehr-Orte-Stundentabelle — Kategorie b der Scheibe-3-Klassifikation, **keine Migration**.

**`narrow.py` — Klassifikations-Kommentar, keine Codeänderung (Zeile 246–252):** `_LABELS` ist ein bewusst kurzes Telegram-Delta-Vokabular für die „Ggü. Vortag"-Zeile. Abgleich mit Katalog-`label_de` zeigt echte Divergenz: `precip_sum`→„Regen" ≠ Katalog „Niederschlag", `temp_max`/`temp_min`→„Temp max"/„Temp min" ≠ Katalog „Temperatur" (beide Richtungen teilen sich einen Katalog-Eintrag, das Label-Paar existiert nur lokal). Zusätzlich gibt der Code Delta-Werte roh aus (`f"{delta}{unit}"`, keine Rundung, Einheit ohne Leerzeichen) — `format_value` würde runden und ein Leerzeichen einfügen, also das Verhalten ändern. Ein kurzer Kommentar oberhalb von `_LABELS` verweist auf `metric_format.py` und begründet die bewusste Nicht-Migration.

**`compact_summary.py` — Klassifikations-Kommentar am Kopf von `CompactSummaryFormatter` (Zeile 28), keine Codeänderung:** Alle fünf `_format_*`-Methoden (Zeilen 126, 143, 164, 264, 325) erzeugen natürlichsprachliche Zusammenfassungssätze (Temp-Spanne mit En-Dash, Regen-/Wind-Adjektive mit Zeitfenster-Mustern, Gewitter-Wörter) statt katalog-ableitbarer Zahl+Einheit-Formatierung. Die eigene Wolken-Emoji-Skala (Schwellen <20/40/60/80) weicht bewusst von der Katalog/`helpers.py`-Skala (≤10/30/70/90) ab — die Angleichung ist eine PO-pflichtige Entscheidung und ausdrücklich Gegenstand von Scheibe 6, nicht dieser Scheibe. Ein Kommentar am Klassenkopf verweist auf `metric_format.py` und die Scheibe-6-Abgrenzung.

**KEINE Änderung** an `src/output/metric_format.py` — `style="bare"` (Scheibe 3) und `style="plain"` (Scheibe 1) existieren bereits und decken den Bedarf dieser Scheibe vollständig ab.

## Expected Behavior

- **Input:** `render_comparison_text(locations, ...)` mit einem repräsentativen `ComparisonResult`-Set (alle 6 Übersichts-Metriken befüllt, inkl. `float`-Werten mit Nachkommastellen, sowie mindestens ein Ort mit `None`-Werten).
- **Output:** Vor und nach der Migration ZEICHEN-IDENTISCHER Plain-Text-Report — keine für Nutzer sichtbare Änderung an der Compare-Mail. `narrow.py`/`compact_summary.py`-Rendering bleibt vollständig unangetastet (reine Kommentar-Diffs).
- **Side effects:** Keine — reine Formatierungsfunktionen ohne I/O, State oder Netzwerkzugriff.

## Acceptance Criteria

- **AC-1:** Given ein `ComparisonResult`-Set mit allen 6 Übersichts-Metriken befüllt (float-Werte mit Nachkommastellen, z. B. `temp_max=12.6`, `wind_max=34.7`, `snow_depth_cm=15.4`) sowie mindestens ein Ort mit `None`-Werten in allen 6 Feldern / When `render_comparison_text` vor und nach der Migration auf denselben Input aufgerufen wird / Then ist der zurückgegebene String in beiden Fällen zeichen-identisch (Golden-Vergleich).
  - Test: neue Testdatei `tests/tdd/test_metric_format_slice5_comparison.py` erfasst den Vorher-String (aus dem unmigrierten Code, als literaler Golden-String im Test) und vergleicht ihn nach der Migration exakt gegen den neuen Output.

- **AC-2:** Given `render_comparison_text` nach der Migration / When der Quellcode auf die vier migrierten Zeilen (`temp_max`, `wind_max`, `cloud_avg`, `snow_depth_cm`) durchsucht wird / Then ruft jede dieser vier Zeilen `metric_format.format_value(...)` auf, keine davon nutzt mehr eine hartcodierte `f"{v:.Nf}"`/`f"{v}"`-Formatierung. (Korrigiert von fünf auf vier nach Adversary-F001: `sunny_hours` ist zur Laufzeit float und bleibt als dokumentierte Ausnahme unmigriert.)
  - Test: `tests/tdd/test_metric_format_slice5_comparison.py` prüft per `inspect.getsource(render_comparison_text)` (oder äquivalentem Struktur-Check) das Vorhandensein von genau 4 `format_value(`-Aufrufen innerhalb der Funktion; der Golden-Test wird um ein float-Fixture (`sunny_hours=4.7` → `"Sonne: 4.7h"`) gehärtet.

- **AC-3:** Given `snow_new_cm` (comparison.py:105), die Stundenverlaufs-Zeilen (comparison.py:121–127), `narrow.py::_LABELS` (246–252) und alle fünf `_format_*`-Methoden in `compact_summary.py` / When Scheibe 5 abgeschlossen ist / Then bleibt ihr Verhalten vollständig unverändert und der bestehende Test-Korpus (`test_compare_render_options_resolver.py`, `test_issue_1106_hourly_metrics_config.py`, `test_issue_1105_compare_snow_metric.py`, `test_issue_1107_compare_sections.py`, `test_issue_236_remaining_templates.py`, `tests/integration/test_compact_summary.py`, `test_issue_1001_telegram_bubbles.py`, `test_day_comparison_integration.py`, `test_telegram_footer_metric_gating.py`, `test_multi_day_trend.py`) läuft grün ohne Anpassung der erwarteten Werte.
  - Test: gezielter Lauf aller genannten Testdateien zeigt 0 unerwartete Fehlschläge; `snow_new_cm`-Assertion im neuen Golden-Test aus AC-1 bestätigt zusätzlich, dass die hartcodierte Formatierung dort unverändert greift.

- **AC-4:** Given `narrow.py::_LABELS` und `compact_summary.py::CompactSummaryFormatter` / When die Dateien nach dieser Scheibe durchsucht werden / Then enthält jede Datei einen Klassifikations-Kommentar an der jeweils dokumentierten Stelle (oberhalb `_LABELS` bzw. am Kopf von `CompactSummaryFormatter`), der auf `metric_format.py` verweist und die bewusste Nicht-Migration begründet (Telegram-Delta-Vokabular bzw. narrative Orchestrierung + Scheibe-6-Verweis für die Wolken-Skala).
  - Test: `tests/tdd/test_metric_format_slice5_comparison.py::test_classification_comments_present` (`# doc-compliance-test`) prüft das Vorhandensein je eines Kommentars mit Verweis auf „metric_format" an beiden Stellen.

- **AC-5:** Given `src/output/metric_format.py` / When Scheibe 5 abgeschlossen ist / Then ist die Datei gegenüber dem Stand nach Scheibe 3 unverändert — kein neuer Stil, keine neue Funktion, keine Signaturänderung.
  - Test: `git diff` bzw. Diff-Review zeigt keine Änderung an `src/output/metric_format.py`.

## Known Limitations

- `sunny_hours` (comparison.py:96) bleibt hartcodiert (Adversary-F001): Laufzeit-Typ ist float mit 1 Dezimale (Annotation `Optional[int]` ist irreführend), Katalog-`sunshine` hat `decimals=None`→0 — eine Migration würde die sichtbare Anzeige runden („4.7h"→„5h"). Nebenbefund-Kandidaten: Katalog-`decimals` für `sunshine` klären (Trip-Briefing zeigt bereits `.1f`) + `LocationResult.sunny_hours`-Annotation korrigieren.
- `snow_new_cm` (comparison.py:105) bleibt hartcodiert, da `metric_catalog.py` keinen `snow_new`-Eintrag besitzt. Ein Katalog-Eintrag hätte Folgewirkung auf alle Kanäle und wird bewusst NICHT im Rahmen dieser Scheibe nachgerüstet — Katalog-Lücke ist Nebenbefund-Kandidat für die Sammel-Triage (#1199), kein Blocker.
- `narrow.py::_LABELS` bleibt vollständig unmigriert (nur Kommentar) — das Telegram-Delta-Vokabular ist eine genuine, bewusst kurze Sonderregel mit abweichenden Labels und ungerundeten Rohwerten; eine Migration würde sichtbares Verhalten ändern.
- `compact_summary.py`s eigene Wolken-Emoji-Skala (<20/40/60/80) bleibt unangetastet und divergiert weiterhin von der Katalog-/`helpers.py`-Skala (≤10/30/70/90). Die Angleichung ist explizit PO-pflichtige Entscheidung und Gegenstand von Scheibe 6, nicht dieser Scheibe.
- Die Stundenverlaufs-Zeilen in `comparison.py` (121–127) bleiben unverändert — Kompakt-Spezialsyntax für die Mehr-Orte-Stundentabelle, keine Katalog-Formatierung.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine [no-adr]
- **Rationale:** Reine additive Nutzung bereits bestehender `format_value`-Stile (`plain`/`bare`, beide aus Scheibe 1/3) auf fünf hartcodierte Formatierungs-Duplikate, ohne neue Abstraktion, ohne Signaturänderung, ohne neue externe Abhängigkeit. Die bewusste Nicht-Migration von `narrow.py`/`compact_summary.py` ist eine dokumentierte Scope-Entscheidung, keine Architekturentscheidung. Kein architekturrelevanter Entscheidungsbedarf.

## Changelog

- 2026-07-12: Initial spec created
- 2026-07-12: Fakten-Korrektur nach Adversary-F001 (CRITICAL): `sunny_hours` ist zur Laufzeit float (nicht `Optional[int]` wie annotiert) — Zeile bleibt unmigriert, AC-2 von 5 auf 4 `format_value`-Aufrufe korrigiert, Golden-Test um float-Fixture gehärtet. Kernziel AC-1 (Verhaltensneutralität) unverändert.
