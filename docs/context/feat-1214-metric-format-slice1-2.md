# Context: feat-1214-metric-format-slice1-2

## Request Summary
Issue #1214 verlangt die Konsolidierung der 6-8fach duplizierten Metrik-Formatierung/Ampel-Logik/Labels in ein gemeinsames Modul `src/output/metric_format.py`. Dieser Workflow deckt nur **Scheibe 1** (neues Modul + Tests, noch ohne Consumer) und **Scheibe 2** (`compare_html.py` auf das neue Modul umstellen) ab — Scheiben 3-6 sind spätere, separate Workflows.

## Related Files

| File | Relevance |
|------|-----------|
| `src/app/metric_catalog.py:24-70` | `MetricDefinition` — Single Source of Truth (label_de, unit, compact_label, col_label, decimals, display_thresholds, highlight_threshold + weitere Felder) |
| `src/app/metric_catalog.py:432,437` | `get_metric(metric_id)`, `get_metric_by_col_key` — bestehende Lookup-Funktionen, wiederverwendbar |
| `src/app/metric_catalog.py:693-726` | `format_metric_value(unit, value, *, signed=False)` — aktuell UNIT-keyed mit fest einprogrammierten Rundungsregeln (nicht aus Katalog-`decimals`) |
| `src/output/renderers/email/helpers.py:422-434` | `ampel_level(metric_id, value)` → `Optional[str]` aus `{green,yellow,orange,red}`, threshold-basiert über `_level_from_thresholds` (Z.380-397) |
| `src/output/renderers/email/helpers.py:450-595` | `fmt_val` — 140+ Zeilen Multiplexer mit ~15 metrikspezifischen Zweigen, Fallback `str(val)` (Z.595, vermuteter Bug-Ursprung) |
| `src/output/renderers/email/design_tokens.py` (52 Zeilen, komplett) | Reine Farbkonstanten, KEINE Level→Farbe-Funktion — `tone_css` muss neu ergänzt werden |
| `src/output/renderers/email/compare_html.py:42-46` | `_RISK_CELL` — 3-Werte-Tupel-Mapping (caution/warn/danger→(bg,fg)) |
| `src/output/renderers/email/compare_html.py:60-86` | 9 lokale `_sev_*`-Funktionen (temp/wind/gust/rain/uv/pop/visibility/thunder/rain_safe), je 4 Rückgabewerte (danger/warn/caution/ok) |
| `src/output/renderers/email/compare_html.py:64-65` | `_sev_wind`: hartcodiert `>40→danger, >30→warn, >20→caution` — weicht vom Katalog (`wind.display_thresholds={yellow:30,orange:50,red:70}`) real ab, nicht nur Zeilenversatz |
| `src/output/renderers/email/compare_html.py:89-98,153-163` | `CV2_METRICS`/`HOUR_METRICS` — Dict-Listen mit eigenen `key/label/unit/sev/fmt/decimals` |
| `src/output/renderers/email/compare_html.py:108-136,221-227` | 7 lokale `_fmt_*`-Funktionen + generisches `_fmt_metric` |
| `src/output/renderers/email/compare_html.py:102` | Kommentar „lokale Kopie statt Import" — Selbst-Eingeständnis der Duplikation |
| `src/output/renderers/email/helpers.py:763-765` | Aufrufer von `format_metric_value` (Trend-Deltas) |
| `src/output/renderers/alert/render.py:49,542-543` | Weitere Aufrufer von `format_metric_value` (Signatur darf für diese nicht brechen) |
| `src/output/renderers/email/html.py:574` | Aufrufer von `ampel_level` im Trip-Mail-Renderer (Zell-Tönung) |
| `.claude/hooks/renderer_mail_gate.py:42-48` | Blockiert Commit an `renderers/email/*.py` (matcht `compare_html.py`) ohne frische Matrix-Test + Validator-Nachweise. `metric_format.py` liegt AUSSERHALB dieses Musters — Scheibe 1 ist NICHT gegated |

## Existing Tests (dürfen nicht ungewollt brechen)
- `test_issue_131_alert_klarheit.py`, `test_952_alert_mail_design_fidelity.py` — feste Erwartungen an `format_metric_value(unit, value)` unit-keyed API (z.B. `format_metric_value("m", 12240.0) == "12.240 m"`)
- `test_issue_759_email_ampel.py`, `test_issue_810_raw_format_ampel.py`, `test_ampel_css_dots.py` — `ampel_level`-Verhalten
- `tests/tdd/test_compare_html_email.py` (351 Zeilen) — `compare_html.py`-Rendering
- `test_issue_914_slice1_foundation.py` — `sms_code/decimals/cmp` auf `MetricDefinition`

## Level-Vokabular-Klärung (technische Entscheidung, keine PO-Frage)
Drei scheinbar unterschiedliche Vokabulare erwiesen sich bei genauer Prüfung als kompatibel:
- Ampel (`helpers.ampel_level`): `green/yellow/orange/red` (4 Werte)
- Compare-lokal (`_sev_*`): `ok/caution/warn/danger` (ebenfalls 4 Werte, nicht 3 wie zunächst vermutet)
- 1:1-Mapping: `ok↔green, caution↔yellow, warn↔orange, danger↔red`

`severity_for()` gibt das kanonische Ampel-Vokabular (`green/yellow/orange/red`) zurück; `tone_css()` operiert darauf. Compare-Aufrufer übersetzen intern oder werden direkt auf die kanonischen Werte umgestellt. `_ALERT_LEVEL_CELL` (4 amtliche Warnstufen, separates System für Wetterwarnungen) bleibt unverändert — NICHT Teil dieser Konsolidierung.

## Risks & Considerations
- **Wind-Schwellen-Divergenz ist eine echte Verhaltensänderung, kein reiner Refactor:** Compare zeigt aktuell bei 45 km/h "rot" (>40 lokal), nach Umstellung auf Katalog-Schwellen (30/50/70) wird das "gelb" — genau das ist die vom Issue geforderte Korrektur (AC: "Wind-45-Fall als Regressionstest"), aber es ist eine sichtbare Verhaltensänderung für Nutzer, die aktuell rote Compare-Zellen sehen.
- **Rückwärtskompatibilität `format_metric_value`:** Bestehende Tests rufen die alte unit-keyed Signatur auf. Neues `format_value(metric_id, ...)` muss als zusätzliche Funktion existieren; die alte Funktion bleibt (ggf. als dünner Wrapper) erhalten, bis Scheiben 3-6 ihre Aufrufer umstellen — sonst brechen `helpers.py:763` und `alert/render.py:49,542`.
- **Gate-Sequenz für Scheibe 2:** Commit an `compare_html.py` braucht VOR dem Commit: (a) `uv run pytest tests/tdd/test_issue_811_mode_matrix.py` grün (registriert Matrix-Hash), (b) frischen `email_spec_validator.py`-Lauf gegen echte Test-Mail (`gregor-test@henemm.com`, IMAP `mail.henemm.com`) — beides im aktiven Workflow-State, sonst blockt `renderer_mail_gate.py` hart.
- Scope bewusst auf Scheibe 1+2 begrenzt — Scheibe 6 (Thunder-Ordinal + Wolken-Skala) bleibt separat, da sie laut Issue explizit eine PO-Entscheidung braucht (welche Skala gilt).

## Existing Specs
Keine dedizierte Spec zu Metrik-Formatierung bisher (`docs/specs/modules/` enthält keine `metric_format*`-Datei) — wird mit diesem Workflow neu angelegt.

Geprüfte verwandte Specs (kein Konflikt, keine Blockade): `metricspec.md`, `issue_435_metric_format_modes.md`, `issue_759_669_email_ampel_gewitter.md`, `issue_810_raw_format_ampel.md`, `configurable_thresholds.md`, `compare_email.md`. **`issue_444_format_mode_consolidation.md` (Status: draft) ist bereits IMPLEMENTIERT** — Code zeigt `"""Issue #444: thin wrapper — delegates to loader._resolve_format_mode."""` in `helpers.py:45-58`. Der Draft-Status ist veraltete Doku, keine echte Abhängigkeit (Nebenbefund → #1198 Doku-Sammel-Issue).

## Analysis

### Type
Feature (Rework/Konsolidierung)

### Technischer Ansatz (PO/Tech-Lead-Entscheidung, durch Plan-Agent bestätigt)
**Koexistenz statt Thin-Wrapper:** `format_metric_value(unit, value)` bleibt unverändert bestehen. `format_value(metric_id, value, style)` ist eine neue, eigenständige Implementierung, die `get_metric(metric_id).decimals`/`.unit` nutzt und `format_metric_value` intern NUR in Richtung metric_id→unit aufrufen darf (nie umgekehrt, da mehrere Metriken dieselbe Unit mit unterschiedlichen `decimals` teilen können — ein Rückschluss unit→metric_id wäre nicht eindeutig).

**Scheibe 2 Mapping-Schicht:** `HOUR_METRICS`/`CV2_METRICS` in `compare_html.py` bekommen ein explizites `"metric_id"`-Feld ergänzt (keine neue Katalog-Lookup-Funktion nötig). `severity_for()` gibt das kanonische Vokabular `green/yellow/orange/red` zurück; die Übersetzung auf Compares lokales `ok/caution/warn/danger` erfolgt an der Aufrufstelle in `compare_html.py` (nicht im neuen Modul — Compare-Vokabular bleibt dort lokal). `tone_css(level)` operiert ausschließlich auf dem kanonischen Vokabular und ersetzt `_RISK_CELL` — MUSS strikt getrennt bleiben von `_ALERT_LEVEL_CELL` (4 amtliche Warnstufen, eigenes System, NICHT Teil dieser Konsolidierung).

**Wind-Schwellen-Angleichung als eigener, sichtbarer Schritt:** Die Angleichung von Compares hartcodierten 40/30/20-Schwellen auf die Katalog-Schwellen (30/50/70) ist laut Issue-AC explizit gefordert (Wind-45-Fall als Regressionstest), aber eine für Nutzer sichtbare Verhaltensänderung (45 km/h zeigt künftig gelb statt rot). Sie erfolgt als eigener, klar benannter Schritt/Commit innerhalb Scheibe 2 mit explizitem Test — nicht als stille Nebenwirkung im generischen `_sev_*`→`severity_for`-Refactoring versteckt.

**Bekanntes Risiko:** `_fmt_metric`/`_fmt_visibility` haben Spezial-Rundungsregeln (z.B. Sicht in km mit variabler Nachkommastelle je nach Schwelle), die NICHT pauschal durch Katalog-`decimals` ersetzt werden dürfen — jede Metrik einzeln prüfen.

### Affected Files (Scheibe 1+2)
| File | Change Type | Description |
|------|-------------|--------------|
| `src/output/metric_format.py` | CREATE | Neues Modul: `format_value`, `severity_for`, `tone_css`-Re-Export, `label` (~120-150 LoC) |
| `src/output/renderers/email/design_tokens.py` | MODIFY | `tone_css(level)`-Funktion ergänzt (~15 LoC), operiert NUR auf kanonischem Ampel-Vokabular |
| `tests/tdd/test_metric_format.py` | CREATE | Tests für neues Modul (~150-200 LoC) |
| `src/output/renderers/email/compare_html.py` | MODIFY | Scheibe 2: 9 `_sev_*`- + 7 `_fmt_*`-Funktionen + `_RISK_CELL` durch neues Modul ersetzt; `HOUR_METRICS`/`CV2_METRICS` um `metric_id`-Feld ergänzt; Wind-Schwellen-Angleichung als expliziter Teilschritt (~netto -60 bis -120 LoC durch Konsolidierung + ~40-60 LoC neue Regressionstests inkl. `test_wind_45_kmh_yellow_not_red`) |

**Explizit NICHT angefasst in Scheibe 1+2** (bleiben unverändert, nur Regressions-Absicherung): `helpers.py::ampel_level`/`fmt_val`, `alert/render.py`, `html.py:574`, `narrow.py`, `compact.py`, `plain.py`, `comparison.py`, `weather_metrics.py`, `api/routers/validator.py` — diese sind Konsumenten der ALTEN Funktionen, die unverändert weiterlaufen.

### Scope Assessment
- Scheibe 1: ~300-350 LoC (neues Modul + Tests)
- Scheibe 2: ~200-250 LoC Diff (Migration + Regressionstests)
- Risk Level: MEDIUM-HIGH (produktiver Mail-Rendering-Pfad, historisch bug-anfälliges Muster, aber durch Full-Process + 2 Adversary-Runden abgesichert)

### Dependencies
- Scheibe 1 muss vollständig fertig + grün getestet sein, bevor Scheibe 2 beginnt (Scheibe 2 importiert direkt aus dem neuen Modul).
- Gate-Reihenfolge Scheibe 2: `tests/tdd/test_issue_811_mode_matrix.py` grün → `email_spec_validator.py` frisch gegen echte Test-Mail → erst dann Commit an `compare_html.py` möglich (`renderer_mail_gate.py`).

### Open Questions
- [x] Level-Vokabular geklärt (kanonisch green/yellow/orange/red, Compare übersetzt lokal)
- [x] Wind-Schwellen-Divergenz ist laut AC gewollte Korrektur, kein offener Punkt
- [x] #444-Abhängigkeit als Fehlalarm aufgelöst (bereits implementiert)
