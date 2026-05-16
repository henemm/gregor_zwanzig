# Context: Issue #231 — `report_config` Zeit-Format-Inkonsistenz

## Request Summary

`report_config.morning_time` / `evening_time` werden uneinheitlich formatiert:
manche Pfade schreiben `'HH:MM'` (5 Zeichen), andere `'HH:MM:SS'` (8 Zeichen).
Python-Backend `time.fromisoformat()` schluckt beides, also kein Funktionsbruch
— aber Daten-Drift, der Tests, Defaults und Wire-Format auseinanderhält.
Norm: **intern `HH:MM:SS`** (Python/ISO), HTML-`<input type='time'>` braucht
`HH:MM` als Display-Form (HTML-Standard).

## Related Files

| Datei | Zeile | Rolle |
|-------|-------|-------|
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` | 348-349 | Schreibt aktuell `'HH:MM'` ins `report_config` beim Save → muss konvertieren |
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` | 76-77, 124-125 | Liest mit `.slice(0,5)` (HH:MM:SS → HH:MM für UI), schreibt aktuell `'HH:MM'` zurück → muss beim Save konvertieren |
| `frontend/src/routes/trips/+page.svelte` | 41-42 | Defaults bereits korrekt `'HH:MM:SS'` — keine Änderung |
| `frontend/src/lib/utils/tripHero.ts` | 108-109 (`parseHHMM`) | Reader, tolerant gegen beide Formate — keine Änderung |
| `frontend/src/lib/utils/rightColumn.ts` | 65-66 | Reader, defensiver `unknown`-Cast — keine Änderung |

## Existing Patterns

- **Wizard-State** hält UI-State in `HH:MM` (kommt aus `<input type='time'>` und Quick-Pick-Handlern wie `makeMorningTimeHandler('07:00')`).
- **Edit-Dialog** macht dasselbe Schema: `$state('07:00')` als UI-Form.
- **Tests** in `tripHero.test.ts`, `rightColumn.test.ts` verwenden bereits konsequent `'07:00:00'` (HH:MM:SS).
- **Reader sind robust:** `parseHHMM` toleriert beide, defensive Stellen ebenfalls.

## Dependencies

- **Upstream:** Issue #207 (strukturiertes Typing für `ReportConfig`) — hat den Drift sichtbar gemacht.
- **Upstream:** Sub-Spec #164 (Wizard-Briefings-Mapping).

## Dependents

- Python-Backend (`time.fromisoformat()`): akzeptiert weiterhin beide Formate; Fix bricht hier nichts.
- Wenn das Backend künftig striktere ISO-Validierung einführt, wäre der jetzige UI-Schreib-Pfad mit `HH:MM` davon betroffen — Fix wäre dann zwingend.

## Risks & Considerations

- **Sehr klein:** 2 Schreib-Pfade konvertieren auf `${time}:00`.
- **Roundtrip-stabil:** Backend → `.slice(0,5)` → UI-State `HH:MM` → `${time}:00` → Backend `HH:MM:SS`. Stabil über beliebig viele Edit-Zyklen.
- **Quick-Pick-Strings (`'07:00'`)** bleiben unverändert — sind UI-Konvention, Konvertierung passiert nur am Save-Grenze.
- **Edge-Case leerer String:** `morning_time` ist im UI-State immer gesetzt (Default `'07:00'`), kein `undefined`-Fall. Aber für Robustheit: Konvertierung nur wenn `time && time.length === 5` (oder `match(/^\d{2}:\d{2}$/)`), sonst Original-Wert durchreichen.
- **Test-Strategie:** Roundtrip-Test via vorhandenes `wizardHelpers.test.ts` (Wizard) ergänzen oder im neuen kleinen Test überprüfen, dass `toTripPayload()` `'06:00:00'` schreibt. Edit-Dialog hat keine bestehenden Tests — Verifikation manuell über Staging.

## Scope

3 Files, ~6-8 LoC. Eindeutig unter 250-LoC-Limit.
