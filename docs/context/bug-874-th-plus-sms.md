# Context: bug-874-th-plus-sms

## Request Summary

Der Fix aus #869 hat `thunder_forecast["+1"] → format_sms() → TH+:` verdrahtet,
aber kein Test prüft diesen Pfad end-to-end. Zusätzlich wurde nie erkannt, dass
das Abendbriefing Daten braucht, die 2 Tage in der Zukunft liegen.

## Zwei Lücken

### Lücke 1: Layer A komplett ungetestet
- `build_token_line()` (Layer B) ist via Golden Tests / Unit Tests abgedeckt
- Die Glue-Schicht in `sms_trip.py` (Layer A) — `thunder_forecast` dict →
  `DailyForecast(thunder_hourly=...)` → `NormalizedForecast(days[1])` — ist nie
  via `format_sms()` end-to-end getestet worden

### Lücke 2: Abendbriefing braucht 2-Tage-Vorschau
| Briefing | target_date | TH: | TH+: |
|---|---|---|---|
| Morgen | heute | thunder heute | thunder morgen (+1 Tag) |
| Abend | **morgen** | thunder morgen | thunder **übermorgen** (+2 von heute) |

`_build_thunder_forecast(segment, target_date, tz)` scannt `target_date+1` für
`"+1"`. Für Abend ist `target_date=morgen`, also wird `übermorgen` aus der
Timeseries benötigt. Kein Test prüft diesen Fall.

## Related Files

| File | Relevance |
|------|-----------|
| `src/formatters/sms_trip.py` | Layer A: `format_sms()`, thunder_forecast-Injektion (Z.165-174) |
| `src/output/tokens/builder.py` | Layer B: `build_token_line()`, `days[1]` → `TH+:` (Z.190-195) |
| `src/services/trip_report_scheduler.py` | `_get_target_date()` (Z.305-319), `_build_thunder_forecast()` (Z.1078-1137) |
| `src/formatters/trip_report.py` | Übergibt `thunder_forecast` an `format_sms()` (Z.209, 221) |
| `src/app/models.py` | `ThunderLevel`, `SegmentWeatherData`, `NormalizedTimeseries` |
| `tests/golden/test_sms_golden.py` | Golden tests: testen Layer B direkt, nicht Layer A |
| `tests/unit/test_token_builder.py` | Unit tests für Builder mit `days=(today, tomorrow)` |
| `tests/tdd/test_bug_397_output_localtime.py` | Referenz-Pattern für `SegmentWeatherData`-Fixtures |

## Existing Patterns

- `_segment_weather(start_hour, end_hour, data_points)` in `test_bug_397_output_localtime.py`
  ist das Referenz-Pattern für minimale `SegmentWeatherData`-Fixtures
- `ThunderLevel.MED` / `ThunderLevel.HIGH` / `ThunderLevel.NONE` sind die drei Levels
- `thunder_forecast["+1"]` = `{"date": "DD.MM.YYYY", "level": ThunderLevel, "text": "..."}`
- `HourlyValue(hour, float_value)` — Level-Mapping: NONE=0, MED=1, HIGH=2

## Dependencies

- Upstream: `SegmentWeatherData` (Formatter-Input), `thunder_forecast` dict (Scheduler-Output)
- Downstream: `NormalizedForecast`, `DailyForecast`, `build_token_line()`, `render_sms()`

## Existing Specs

- `docs/reference/sms_format.md` v2.3 — Single Source of Truth für SMS-Format
  - §3.2: `TH+:{level}@{h}` = Gewitter Folgetag
  - Kein `TH++:` für +2 in der Spec — nur `TH+:` ist definiert

## Analysis

### Type
Bug (Test-Coverage-Gap + Evening-Briefing-Verhalten nie verifiziert)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `tests/tdd/test_bug_874_th_plus_sms.py` | CREATE | 4 neue Testfälle: Layer-A-Pfad durch format_sms() |

### Scope Assessment
- Files: 1 (nur neues Test-File)
- Estimated LoC: +60/-0
- Risk Level: NIEDRIG — rein additiv, kein Produktions-Code wird geändert (es sei denn die Tests fallen rot → dann ist ein Code-Fix nötig)

### Technical Approach
1. Minimale `SegmentWeatherData`-Fixture analog `test_bug_397_output_localtime.py`
2. `SMSTripFormatter().format_sms(segments, thunder_forecast={"+1": {...}})` aufrufen
3. Assert `"TH+:M@"` oder `"TH+:H@"` im SMS-String (je nach Level)
4. Grenzfälle: `ThunderLevel.NONE` → `TH+:-`, kein `"+1"`-Key → `TH+:-`, `thunder_forecast=None` → `TH+:-`
5. Abend-Kontext: semantisch identischer Test, explizit als Abend-Szenario dokumentiert (der Code-Pfad ist derselbe — der Unterschied liegt im Scheduler, nicht im Formatter)

### Open Questions
- Keine — der Scope ist klar.

## Risks & Considerations

- Der Bug betrifft nur den Test-Coverage-Gap; der Code in `sms_trip.py` ist logisch korrekt
- Kein Code-Fix an `sms_trip.py` nötig, wenn Tests grün werden — sonst doch
- Hard-codierte Stunde 12 in `HourlyValue(12, ...)` ist bekannte Vereinfachung (keine Regression)
- `thunder_forecast["+1"]["level"] == ThunderLevel.NONE` → `lvl_val=0` → keine Injektion → `TH+:-` (korrekt)
