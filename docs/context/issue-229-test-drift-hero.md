# Context: Issue #229 — Test-Drift trip-detail-hero AC-6

## Request Summary

Playwright-Test `AC-6` in `frontend/e2e/trip-detail-hero.spec.ts` erwartet
"Briefings deaktiviert", erhält aber "Nächstes Briefing heute, 06:00".
Ursache: Der Shared-Test-Trip `e2e-cockpit-test` (`global.setup.ts:50-55`)
hat inzwischen ein `report_config` mit `enabled: true`. Test-Kommentar
ist veraltet ("e2e-cockpit-test hat kein report_config gesetzt").

## Related Files

| Datei | Zeile | Rolle |
|-------|-------|-------|
| `frontend/e2e/trip-detail-hero.spec.ts` | 55-60 | AC-6 (drifteted Test) |
| `frontend/e2e/global.setup.ts` | 50-55 | Shared-Trip `e2e-cockpit-test` mit `report_config.enabled=true` |
| `frontend/e2e/trip-detail-overview-right.spec.ts` | 80-116 | Vorbild — legt eigenen `e2e-no-briefing-trip` per `request.post` an |

## Existing Patterns

- **Pattern: Eigener Test-Trip pro Edge-Case** — etabliertes Vorbild in
  `trip-detail-overview-right.spec.ts:85-102`. Test postet via
  `request.post('/api/trips', ...)` einen lokalen Trip ohne `report_config`,
  Cleanup wird durch Test-Isolation/Idempotenz des `POST /api/trips` getragen
  (überschreibt bei gleicher ID).
- Andere Hero-Tests (AC-3, AC-10, AC-11) bauen weiterhin auf `e2e-cockpit-test`
  auf — werden NICHT angefasst.

## Dependencies

- Shared-Trip-Felder, die andere Tests brauchen (`report_config`,
  `weather_config`, `aggregation`, Stages für gestern/heute/morgen). Nicht
  ändern, sonst kette von Test-Breaks. → Bestätigt Option B aus dem Issue.

## Risks & Considerations

- **Risiko sehr gering:** Reine E2E-Test-Datei, kein Komponenten-Code.
- **Test-Isolation:** `request.post` ist idempotent über die Trip-ID; bei
  parallelen Worker-Runs verwendet Playwright eigene Browser-Contexte aber
  das Backend ist geteilt — Trip-ID muss eindeutig sein (`e2e-hero-no-briefing-trip` o.ä.).
- **Aggregations-Drift (Out-of-Scope-Beobachtung):** `global.setup.ts:60`
  verwendet noch das alte Wire-Format `aggregation: { activity_profile: 'wandern' }`
  statt `profile`. Reader sind tolerant. Wäre eigener Issue (Test-Daten-Migration),
  hier nicht anfassen.

## Scope

1 File modifiziert (`trip-detail-hero.spec.ts`), ~10-15 LoC.
Keine Spec-Änderungen, kein Komponenten-Code.
