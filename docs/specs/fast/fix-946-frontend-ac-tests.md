# Mini-Spec: #946 Frontend-ACs (AC-4, AC-5, AC-6)

## Was ändert sich
- Neue Playwright-E2E-Testdatei `frontend/e2e/issue-946-alerts-tab.spec.ts`
- 3 Tests für die 3 unbelegten Frontend-ACs von Issue #946

## Was darf sich nicht ändern
- Kein Produktionscode
- Bestehende Alert-Tests bleiben grün

## Acceptance Criteria

**AC-4:** Given Trip mit metric_alert_levels=null und alert_preset=null /
When Alerts-Tab geöffnet / Then `alerts-onboarding` sichtbar, `alert-metric-level-table` NICHT sichtbar

**AC-5:** Given Onboarding-Zustand / When "Standard-Konfiguration übernehmen" geklickt /
Then Tabelle erscheint, GET /api/trips/:id bestätigt metric_alert_levels != null

**AC-6:** Given Trip mit freezing_level als aktivierter Display-Metrik /
When Alerts-Tab geöffnet / Then `alert-metric-row-freezing_level` mit Text "Nullgradgrenze" sichtbar

## Inline-Tests
- [ ] AC-4: Onboarding-Zustand bei unkonfiguriertem Trip
- [ ] AC-5: "Standard-Konfiguration übernehmen" persistiert metric_alert_levels
- [ ] AC-6: freezing_level / "Nullgradgrenze" erscheint als Alert-Metrik
