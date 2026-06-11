# Context: Issue #762 — Etappen-Nummer-Dedup verschluckt Sub-Etappen-Suffix

## Request Summary
Die in #760 eingeführte Dedup-Regex `_STAGE_PREFIX_RE` greift bei Sub-Etappen-Namen
wie `Etappe 3a` zu gierig: `\d+` matcht nur `3`, das Suffix `a` landet im `rest` →
`Etappe 2: a`. Das ursprüngliche `3a` geht verloren (kosmetischer Inhaltsverlust,
LOW).

## Related Files
| File | Relevance |
|------|-----------|
| `src/app/trip.py:33` | `_STAGE_PREFIX_RE` — die zu fixende Regex |
| `src/app/trip.py:240` | `numbered_stage_label()` — konsumiert die Regex |
| `tests/tdd/test_issue_760_stage_number.py` | Bestehende Dedup-Test-Tabelle (Vorbild, no-mock) |
| `src/services/trip_alert.py:654` | Call-Site (stage_name) — unverändert, profitiert automatisch |
| `src/services/trip_report_scheduler.py:419` | Call-Site (stage_name) — unverändert |
| `src/services/preview_service.py:117` | Call-Site (stage_name) — unverändert |
| `docs/specs/modules/issue_760_stage_number.md` | Bestehende Spec (#760) |

## Existing Patterns
- Dedup über `_STAGE_PREFIX_RE.match(name)`, `rest = m.group("rest")`.
- Tests nutzen echte `Trip`/`Stage`-Objekte, keine Mocks; parametrische Fall-Tabelle.

## Root Cause
`r"^\s*(?:Etappe|Tag)\s*\d+\s*[:.\-–—]?\s*(?P<rest>.*)$"`
Bei `Etappe 3a`: `\d+` → `3`, kein Separator, `rest` → `a`.

## Fix-Ansatz (laut Issue empfohlen)
Wortgrenze `\d+\b` einfügen: `r"^\s*(?:Etappe|Tag)\s*\d+\b\s*[:.\-–—]?\s*(?P<rest>.*)$"`.
Bei `Etappe 3a` scheitert `\b` (keine Grenze zwischen `3` und `a`) → kein Match →
Original-Name bleibt erhalten → `Etappe 2: Etappe 3a`. Alle bestehenden #760-Fälle
(`Tag 1: …`, `Etappe 3 - …`, `Etappe 4`) bleiben unberührt (Grenze nach Ziffer zu
Space/Separator/Stringende existiert).

## Dependencies
- Upstream: `re` (stdlib).
- Downstream: 3 Call-Sites leiten `stage_name` ab; konsumieren nur das Ergebnis →
  automatisch korrekt, keine Änderung nötig.

## Risks & Considerations
- Edge `Etappe 3.5`: `.` ist Separator → würde `rest="5"`. Extrem-Sonderfall, nicht
  in Scope (#762 betrifft Buchstaben-Suffixe 3a/3b).
- Regress-Risiko: alle 8 bestehenden #760-Dedup-Tests müssen grün bleiben.
