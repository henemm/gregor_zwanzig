# Context: Issue #121 — Confidence Output (Workflow 2)

## Request Summary

Output-Schicht für Prognose-Konfidenz: SMS-Symbol pro Tag (`+`/`~`/`?`), E-Mail-Spalte „Sicherheit", Klartext-Hinweis bei < 60 % in T+0-72h. Backend-Daten (`ForecastDataPoint.confidence_pct`, `SegmentWeatherSummary.confidence_pct_min`) sind in Workflow 1 fertiggestellt und auf Production deployed (Commit `35c9190`).

## Master-Spec

`docs/specs/modules/forecast_confidence.md` — Akzeptanzkriterien **AC-9 bis AC-14** sind Scope dieses Workflows.

## Related Files

### SMS-Pfad

| Datei | Relevanz |
|------|----------|
| `src/output/tokens/dto.py` (Z. 20+) | `DailyForecast` — neues Optional-Feld `confidence_pct_min: Optional[int] = None` |
| `src/formatters/sms_trip.py` (Z. 79+) | SMS-Adapter — durchreichen `confidence_pct_min` aus `SegmentWeatherSummary` |
| `src/output/tokens/builder.py` (Z. 31–47, 127+) | `PRIORITY["C"]`, `POSITIONAL`-Ergänzung, Builder-Loop für C-Token |
| `src/output/tokens/render.py` (Z. 13–101) | Truncation-Logik — Schwellen-Symbol-Mapping `≥75=+/50-74=~/<50=?` |
| `tests/unit/test_token_builder.py` | Test-Vorbild für neue C-Token-Tests |

### E-Mail-Pfad

| Datei | Relevanz |
|------|----------|
| `src/app/metric_catalog.py` (Z. 55+) | Neue `MetricDefinition(id="confidence", dp_field="confidence_pct", col_key="confidence", col_label="Sicherheit", ...)` |
| `src/output/renderers/email/helpers.py` (Z. 59-79) | `dp_to_row()` befüllt automatisch `row["confidence"]` aus `dp.confidence_pct` — keine Änderung nötig |
| `src/output/renderers/email/html.py` (Z. 78-91, Klartext-Block nach Z. 221) | Klartext-Hinweis-Generator (Wochentag + Spread) |
| `src/output/renderers/email/plain.py` (analog Z. ~170-180) | Plain-Text-Variante des Hinweises |
| `tests/tdd/test_html_email.py` (`TestRealGmailE2E` ab Z. 92) | E2E-Test-Vorbild mit Gmail SMTP + IMAP |

### Reference & Validation

| Datei | Relevanz |
|------|----------|
| `docs/reference/sms_format.md` (v2.0) | Anhebung auf v2.1 — Symbol-Reservierung `+`/`~`/`?`, Token-Position nach `TH+:` |
| `docs/reference/renderer_email_spec.md` | E-Mail-Spalten-Reihenfolge dokumentieren, Hinweis-Regel |
| `.claude/hooks/email_spec_validator.py` | Eventuell erweitern für Spalten-Check |
| `docs/specs/modules/issue_121_confidence_output.md` | **Neu** — Sub-Spec, referenziert Master-Spec |

## Existing Patterns

1. **`dp_to_row()` über MetricCatalog** — eine neue `MetricDefinition` mit `dp_field="confidence_pct"` und `col_key="confidence"` reicht für HTML+Plain-Spalten. Renderer ziehen Header automatisch über `visible_cols()`.
2. **DTO-Erweiterung `DailyForecast`** — neue Optional-Felder mit Default `None`. Bestehende Konstruktoren (z.B. `sms_trip.py`) müssen das neue Feld nicht setzen (Optional).
3. **Token-Builder `PRIORITY` + `POSITIONAL`** — Symbol einreihen mit definierter Priorität für Truncation, Position für Render-Reihenfolge.
4. **E2E-E-Mail-Test mit `TestRealGmailE2E`** — echtes SMTP-Senden + IMAP-Roundtrip, KEIN Mock.
5. **Klartext-Hinweise in E-Mail-Body** — Pattern existiert für andere Wetter-Hinweise (z.B. Gewitter-Warnungen). Werden als separate Sektion zwischen `summary_html` und `changes_html` eingefügt.
6. **Produktiver Pfad: `SegmentWeatherData[]` → `format_email()`** — der Scheduler ruft `formatter.format_email(segments=...)`, NICHT `AggregatedSummary`. `seg.aggregated.confidence_pct_min` ist verfügbar.

## Dependencies

- **Upstream:** `ForecastDataPoint.confidence_pct`, `SegmentWeatherSummary.confidence_pct_min` (Workflow 1, fertig)
- **Downstream:** SMS-Renderer (`render.py`), E-Mail-Renderer (`html.py` + `plain.py`)
- **MetricCatalog:** zentrale Registry — eine Stelle, viele Renderer
- **Tests:** echte Gmail-Credentials in `Settings.for_testing()` Pattern

## Risks & Considerations

1. **Aggregation pro Tag ≠ pro Segment.** Für SMS-Token braucht's eine Pro-Tag-Konfidenz. Sub-Spec muss klären: min/max/avg über alle Segmente eines Tages? Empfehlung: `min` (worst-case wie Backend).
2. **MetricCatalog `summary_fields`-Eintrag.** Eintrag `summary_fields={"min": "confidence_pct_min"}` macht die Aggregation auch über `WeatherMetricsService` verfügbar.
3. **Spalten-Reihenfolge in E-Mail-Tabelle.** MetricCatalog ordnet Spalten nach Registrierungsreihenfolge. „Sicherheit" sollte rechts (nach allen Wettergrößen) erscheinen, da sie meta-Information ist.
4. **Klartext-Hinweis nur einmal pro E-Mail** — nicht pro Tag, nicht pro Segment. Logik: einmaliger Suchlauf über alle Stunden in T+0-72h.
5. **Wochentags-Berechnung im Hinweis.** Bei einem Trip am Wochenende sollte „Mittwoch" → „übermorgen"? Spec präzisieren, ob Wochentag oder relative Zeitangabe.
6. **email_spec_validator.py.** Falls die Validator-Checks die Spalten-Anzahl prüfen, muss er erweitert werden — andernfalls Exit 0 trotz neuer Spalte.
7. **SMS-Länge** — bei 7-Tage-Trip kostet C-Token pro Tag 1 Zeichen + Separator = ~14 Zeichen. Priorität in `PRIORITY` sauber setzen, damit es bei 160-Zeichen-Limit nicht andere wichtigere Tokens verdrängt.
8. **`_trip_result_to_normalized` Pfad** — CLI-Adapter über `AggregatedSummary`, der `confidence` NICHT hat. Da CLI-Pfad nicht produktiv für E-Mail/SMS, kann er ohne Confidence-Felder bleiben (out of scope) ODER nachgezogen werden falls CLI eine Confidence-Anzeige bekommen soll.
