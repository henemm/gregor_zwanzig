---
entity_id: report_formatter
type: module
created: 2025-12-27
updated: 2025-12-27
status: draft
version: "1.0"
tags: [report, formatter, output]
---

# Report Formatter

## Approval

- [ ] Approved

## Purpose

Generiert lesbare Reports aus Forecast-DTOs und Risk-Assessment. Unterstuetzt SMS (<=160 Zeichen) und E-Mail (lang-form mit Tabellen).

## Source

- **File:** `src/formatter/report.py` (geplant)
- **Identifier:** `class ReportFormatter`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| NormalizedTimeseries | dto | Wetterdaten |
| RiskAssessment | dto | Risiko-Bewertung |
| DebugBuffer | class | Debug-Informationen |

## Implementation Details

```
Report-Typen:
- evening: Prognose fuer naechste Etappe
- morning: aktualisierte Prognose
- alert: Untertagswarnung bei Verschlechterung

SMS-Format (<=160 chars):
Monte: N15 D25 R- PR20%@14 W22@14(28@16) G35@14(48@17) TH:M@14 DBG[MET MED]

E-Mail-Format:
- Token-Line (identisch zu SMS)
- Human-readable Summary
- Etappen-Tabellen
- Debug-Block (identisch zu Console)
```

## Expected Behavior

- **Input:** Forecast DTOs, RiskOutput, DebugBuffer
- **Output:** Formatierter Report-String
- **Side effects:** Keine

## Known Limitations

- SMS: GSM-7 only, keine Umlaute

## Changelog

- 2025-12-27: Initial spec created (planned module)
