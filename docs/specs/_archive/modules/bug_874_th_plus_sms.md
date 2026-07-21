---
entity_id: bug_874_th_plus_sms
type: bugfix
created: 2026-06-24
updated: 2026-06-24
status: draft
version: "1.0"
tags: [sms, thunder, tdd, test-coverage]
---

# Bug #874: TH+: SMS-Token — fehlende E2E-Tests + Evening-Briefing-Lücke

## Approval

- [ ] Approved

## Purpose

Der Fix aus #869 hat die Verdrahtung `thunder_forecast["+1"] → format_sms() →
TH+:` eingebaut, aber kein Test prüft diesen Pfad end-to-end. Tests werden
hinzugefügt, die das tatsächliche Verhalten durch `SMSTripFormatter.format_sms()`
beweisen — für Morgen- und Abendbriefing-Kontext.

> **Nachtrag (2026-07-16, Fix #1275):** Die hier getestete Format-Layer-Verdrahtung
> (`thunder_forecast`-Dict → `TH+:`) bleibt unverändert; die *Beschaffung* dieses
> Dicts in `trip_report_scheduler.py` wurde jedoch korrigiert — sie aggregiert
> jetzt über alle Segmente der tatsächlichen Folge-Etappe statt nur die
> Restdaten des letzten Segments von heute zu prüfen. Details:
> `docs/specs/bugfix/fix_1275_sms_th_mismatch.md`.

## Source

- **File:** `tests/tdd/test_bug_874_th_plus_sms.py` (CREATE)
- **Identifier:** `SMSTripFormatter.format_sms()`

## Estimated Scope

- **LoC:** ~80
- **Files:** 1 (nur neues Test-File; kein Produktions-Code sofern Tests grün)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/formatters/sms_trip.py` | MODIFY ggf. | Layer A: thunder_forecast → NormalizedForecast.days[1] |
| `src/app/models.py` | READ | ThunderLevel, SegmentWeatherData |
| `src/output/tokens/builder.py` | READ | Layer B (unverändert) |

## Implementation Details

Minimal-Fixture für `SegmentWeatherData` (analog `test_bug_397_output_localtime.py`):
- Ein TripSegment mit UTC-Zeitfenster
- Leere Timeseries (keine Stundenwerte nötig für TH+:-Test)
- `aggregated=SegmentSummary(...)` mit Null-Werten

`thunder_forecast`-Dict-Format:
```python
{"+1": {"date": "25.06.2026", "level": ThunderLevel.MED, "text": "Gewitter möglich ab 14:00"}}
```

Level-Mapping in `sms_trip.py`: `NONE=0, MED=2, HIGH=3` (Builder-System: 1=L, 2=M, 3=H). Wert > 0 → Injektion als
`HourlyValue(12, float(lvl_val))` — Stunde 12 ist bewusste Vereinfachung.

## Expected Behavior

- **Input:** `format_sms(segments, thunder_forecast={"+1": {"level": ThunderLevel.MED, ...}})`
- **Output:** SMS-String enthält `TH+:M@12`
- **Input:** `format_sms(segments, thunder_forecast={"+1": {"level": ThunderLevel.NONE, ...}})`
- **Output:** SMS-String enthält `TH+:-`
- **Input:** `format_sms(segments, thunder_forecast=None)` oder `thunder_forecast={}`
- **Output:** SMS-String enthält `TH+:-`

## Acceptance Criteria

**AC-1:** Given ein Segment-Set und `thunder_forecast={"+1": {"level": ThunderLevel.MED, "date": "25.06.2026", "text": "..."}}` / When `SMSTripFormatter().format_sms(segments, report_type="morning", thunder_forecast=thunder_forecast)` aufgerufen / Then enthält der zurückgegebene SMS-String den Teilstring `"TH+:M@"`

**AC-2:** Given ein Segment-Set und `thunder_forecast={"+1": {"level": ThunderLevel.HIGH, "date": "25.06.2026", "text": "..."}}` / When `SMSTripFormatter().format_sms(segments, report_type="evening", thunder_forecast=thunder_forecast)` aufgerufen / Then enthält der zurückgegebene SMS-String den Teilstring `"TH+:H@"` — beweist den Abend-Pfad (TH+ = Gewitter übermorgen)

**AC-3:** Given ein Segment-Set und `thunder_forecast={"+1": {"level": ThunderLevel.NONE, "date": "25.06.2026", "text": "..."}}` / When `SMSTripFormatter().format_sms(segments, thunder_forecast=thunder_forecast)` aufgerufen / Then enthält der zurückgegebene SMS-String den Teilstring `"TH+:-"` und nicht `"TH+:M"` oder `"TH+:H"`

**AC-4:** Given ein Segment-Set und `thunder_forecast=None` oder `thunder_forecast={}` (kein `"+1"`-Schlüssel) / When `SMSTripFormatter().format_sms(segments, thunder_forecast=thunder_forecast)` aufgerufen / Then enthält der zurückgegebene SMS-String den Teilstring `"TH+:-"` (kein Gewitter-Token für den Folgetag)
