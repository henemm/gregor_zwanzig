# Mini-Spec: fix-867-870-871-test-hygiene

## Was ändert sich
- `frontend/src/lib/components/alerts-tab/alertMetricTable.test.ts` Zeile 30: Erwartungswert `9` → `13`
- Kommentar Zeile 26: `9 Eintraege` → `13 Eintraege`
- Issues #870 und #871 als "bereits behoben" schließen

## Was darf sich nicht ändern
- Die anderen 34 Tests in `alertMetricTable.test.ts`
- Kein Produktionscode

## Manuelle Test-Schritte
1. `cd frontend && node --experimental-strip-types --test src/lib/components/alerts-tab/alertMetricTable.test.ts`
2. Ergebnis: 35/35 pass, 0 fail

## Acceptance Criteria

**AC-1:** Given alertMetricTable.test.ts nach #846 / When node --test ausgeführt wird / Then pass 35/35, kein fail.

## Inline-Test
- [x] `METRIC_DEFAULTS > hat genau 13 Eintraege` grün
