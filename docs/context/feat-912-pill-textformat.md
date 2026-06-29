# Context: feat-912-pill-textformat

## Request Summary
Das Pill-Textformat im METRIKEN-ÜBERBLICK der Briefing-Mail soll an die
JSX-Design-Vorlage (`screen-output-preview.jsx → EmailMetricsSummary`)
angeglichen werden. Konkret: Einheitliches `max/min <Wert> (<HH:00>)`-Muster,
Schwellen-Variante `>thr ab <HH> · max <Wert> (<HH>)`, Begriff „0°-Linie"
statt „0°-Grenze", Temperatur und Gefühlt bleiben zwei Pills (sind es schon).

## Related Files

| Datei | Relevanz |
|-------|----------|
| `src/output/renderers/email/helpers.py` | Enthält `_pill_for_metric`, `_event_with_peak`, `_range_pill`, `build_metrics_summary_pills` — alle Änderungen hier |
| `src/output/renderers/email/html.py` | Ruft `build_metrics_summary_pills` auf (keine inhaltliche Änderung nötig) |
| `src/output/renderers/email/compact.py` | Ruft `build_metrics_summary_pills` auf (keine inhaltliche Änderung nötig) |
| `src/output/renderers/email/plain.py` | Ruft `build_metrics_summary_pills` auf (keine inhaltliche Änderung nötig) |
| `tests/tdd/test_issue_664_metrics_summary.py` | Betroffene Tests — Formatstrings müssen angepasst werden |
| `tests/tdd/test_issue_807_reproduction.py` | Betroffene Tests |
| `tests/tdd/test_issue_808_sonne_pill.py` | Betroffene Tests (Sonne-Format unverändert) |
| `docs/context/911-pill-format-delta.md` | IST→SOLL-Delta-Tabelle (Single Source of Truth) |
| `docs/design-requests/issue_911_mail_vorschau/screen-output-preview.jsx` | JSX-Vorlage (SOLL-Optik, Mock-Daten) |

## Existing Patterns

### Aktuelle Pill-Klassen
- **Klasse 1** (Ereignis, mit Uhrzeit): Wind, Böen, Regen, Regenrisiko, Gewitter, Sicht, Feuchte
- **Klasse 2** (Bereich, ohne Uhrzeit): Temperatur, Gefühlt, Bewölkung, Tiefe Wolken, Nullgradgrenze, Taupunkt, UV, Sonne

### Aktuelle Formate (IST) → Neue Formate (SOLL)
| Metrik | IST | SOLL |
|--------|-----|------|
| Temperatur | `Temperatur min–max °C` | `min–max°C · Max HH:00` |
| Gefühlt | `Gefühlt min–max °C` | `gef. min X°C · HH:00` |
| Wind (ohne Schwelle) | `Wind ruhig` | `Wind max X km/h (HH:00)` |
| Wind (mit Schwelle) | `Wind ab HH:00 · Spitze X km/h um HH:00` | `Wind >thr km/h ab HH · max X (HH)` |
| Böen (analog Wind) | s.o. | s.o. |
| Regen | `Regen ab HH:00 · X mm gesamt, Spitze HH:00` | `Regen ab HH:00 · X mm` |
| Regenrisiko | `Regenrisiko ab HH:00 · Spitze X % um HH:00` | `Regen-W. >thr% ab HH · max X% (HH)` |
| Gewitter | `Gewitter ab HH:00 · stärkste HH:00` | **bleibt enum-basiert** (kein thunder_pct-Feld) |
| Bewölkung | `Bewölkung min–max %` | `min–max% bewölkt · Max HH:00` |
| Sicht (unter Schwelle) | `Sicht ab HH:00 unter 2 km · min X km` | `Sicht <2 km ab HH:00 · min X km (HH:00)` |
| Sicht (über Schwelle) | `gute Sicht` | `Sicht min X km (HH:00)` |
| UV | `UV bis X` | `UV max X.X (HH:00)` |
| Nullgradgrenze | `0°-Grenze min–max m` | `0°-Linie min–max m · Max HH:00` |
| Taupunkt | `Taupunkt min–max °C` | `Taupunkt min X°C (HH:00)` |
| Feuchte (unter Schwelle) | `Luft trocken` | `Feuchte min–max% · Max HH:00` |

## Analysis

### Type
Feature (Design-Compliance)

### Affected Files (with changes)

| Datei | Change-Typ | Beschreibung |
|-------|-----------|-------------|
| `src/output/renderers/email/helpers.py` | MODIFY | `_pill_for_metric` (alle 15 Metriken-Zweige), 2 neue Hilfsfunktionen (`_max_with_ts`, `_range_max_pill`) |
| `tests/tdd/test_issue_664_metrics_summary.py` | MODIFY | ~7 Tests mit alten Formatstrings aktualisieren |
| `tests/tdd/test_issue_795_briefing_quality.py` | MODIFY | 3 Konflikt-Tests aktualisieren (`test_wind_below_threshold_calm_form`, `test_wind_event_written_out_with_peak`, `test_temperature_range_no_time`) |
| `tests/tdd/test_issue_807_reproduction.py` | MODIFY | Segment-Fenster-Test ggf. anpassen |
| `tests/tdd/test_issue_833_gate.py` | NO CHANGE | Nutzt `"kein Regen"` — bleibt laut Delta-Tabelle erhalten |

### Scope Assessment
- Dateien: 4 MODIFY
- Geschätzte LoC: ~105 geändert + ~45 neu = ~150 LoC
- Risiko: **MITTEL** — zentrale Pill-Logik, mehrere Konflikt-Tests aus #795

### Technical Approach

**Schritt 1:** 2 neue Hilfsfunktionen in `helpers.py`:
- `_max_with_ts(vals, *, tz)` → `(peak_val, peak_hh)` — für Klasse-2-Uhrzeiten
- `_range_max_pill(label, unit, min_v, max_v, max_hh)` → `"min–max unit · Max HH:00"`

**Schritt 2:** Alle Klasse-2-Zweige in `_pill_for_metric` auf `(val, dp.ts)`-Extraktion umstellen und `_range_max_pill` aufrufen.

**Schritt 3:** Klasse-1-Metriken neue Formate:
- Wind ohne Schwelle: `Wind max X km/h (HH:00)` statt `Wind ruhig`
- Wind mit Schwelle: `Wind >thr km/h ab HH · max X (HH)`
- Precipitation: `Regen ab HH:00 · X mm` (kein "gesamt", kein "Spitze")
- Regenrisiko: Label `Regen-W.`, Format `>50% ab HH:00 · max 68% (HH:00)`
- Sicht gut: `Sicht min X km (HH:00)` statt `gute Sicht`
- Feuchte unter Schwelle: `Feuchte X–Y% · Max HH:00` statt `Luft trocken`

**Kritische Kollision (Test aus #795):**
`test_temperature_range_no_time` assertiert explizit KEIN `Max HH:00` für Temperatur.
Neues Design-SOLL verlangt genau das. Dieser Test muss als durch #912 überholt
markiert und invertiert werden.

### Dependencies
- Upstream: `ForecastDataPoint.ts` (Timestamps), `local_hour()` aus `utils.timezone`
- Downstream: 3 Mail-Renderer (html/compact/plain), alle Briefing-Mail-Tests

### Open Questions
- [x] Gewitter-Pill: kein thunder_pct → bleibt enum-basiert
- [x] "kein Regen" bleibt erhalten (Delta-Tabelle SOLL: "Regen ab ... / kein Regen")
- [x] `test_issue_833_gate.py` sicher — nutzt "kein Regen" der erhalten bleibt

## Risiko: Gewitter-Pill ohne thunder_pct
Der SOLL-Screenshot der JSX-Vorlage zeigt `Gewitter max 5% (12:00)` — eine
Prozentzahl. Das Datenmodell kennt nur `ThunderLevel` (NONE/MED/HIGH, Enum).
Ein `thunder_pct`-Feld existiert **nicht** im `ForecastDataPoint`.

**Entscheidung:** Gewitter-Pill bleibt enum-basiert (wie IST). Das JSX ist
Mock-Daten; keine neue Datenpipeline in diesem Scope.

## Dependencies
- Upstream: `app.models.ForecastDataPoint`, `app.metric_catalog`, `utils.timezone`
- Downstream: alle 3 Mail-Renderer (html/compact/plain), existierende Tests

## Existing Specs
- `docs/specs/modules/email_metrics_summary_664.md` — ursprüngliche Metriken-Überblick-Spec
- Impl-Kontext: Issue #664 (Grundimplementierung), #795 (Klassen-Split)

## Risks & Considerations
- **Renderer-Commit-Gate** (Issue #811) greift: `helpers.py` ist Mail-Content-Datei.
  Vor Commit müssen Modus-Matrix-Test + Briefing-Mail-Validator grün sein.
- Bestehende Tests für Pills müssen aktualisiert werden (Formatstrings ändern sich).
- Klasse-2-Metriken brauchen jetzt Uhrzeiten → benötigen `dp.ts` statt nur Werte.
  `_range_pill` ist nicht ausreichend; neue Zeitstempel-Logik nötig.
- Feuchte unter Schwelle: aktuell `Luft trocken` → SOLL: `Feuchte min–max% · Max HH:00`.
  IST-Klasse-1-Logik muss auf Klasse-2-Fallback für den Unter-Schwelle-Fall umgebaut werden.
