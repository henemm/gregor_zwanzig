# Context: Issue #179 — Alert-Konfigurator: Modus-Toggle (Δ / Absolut / Beides)

## Request Summary

Epic #139 — Alert-Konfigurator. AlertRulesEditor (Issue #223, #224) ist gebaut, aber `AlertRule.kind` ('absolute' | 'delta') ist in der UI nicht wählbar. Issue #179 führt 3 ModeCard-Komponenten (Radio-Auswahl) ein: **Δ (Delta/Änderung)** | **Absolut (Schwellwert)** | **Beides**. Jede Card zeigt Eyebrow + Title + Beschreibung + Beispiel.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/types.ts` | `AlertRule`, `AlertRuleKind` ('absolute' \| 'delta'), `AlertMetric`, `AlertSeverity` |
| `frontend/src/lib/components/alert-rules-editor/AlertRulesEditor.svelte` | Container für Alert-Regeln-Liste — kein Modus-Toggle vorhanden |
| `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte` | Zeile pro Regel — editiert Metric/Threshold/Severity, aber NICHT kind |
| `frontend/src/lib/components/alert-rules-editor/alertRuleDefaults.ts` | `newDefaultRule()` — Default-Generator, kind-Feld vorhanden |
| `frontend/src/lib/components/alert-rules-editor/alertRuleDefaults.test.ts` | Bestehende Unit-Tests — Muster für neue Tests |
| `frontend/src/lib/utils/alertMetricLabels.ts` | Labels, Units, Vergleichs-Symbole pro Metrik |
| `frontend/src/lib/components/trip-wizard/steps/Step4Briefings.svelte` | Wizard Step 4 mit AlertRulesEditor (Issue #224) |
| `frontend/src/lib/components/edit/TripEditView.svelte` | Edit-Pfad mit AlertRulesEditor |
| `frontend/src/lib/components/trip-detail/AlertsPreviewCard.svelte` | Leseanzeige der aktivierten Alert-Regeln |
| `internal/model/trip.go` | `AlertRule`, `AlertRuleKind` Enums im Go-Modell |
| `src/app/models.py` | `AlertRuleKind` Enum, `AlertRule` Dataclass |
| `docs/specs/modules/issue_223_alert_rules_editor.md` | Spec für AlertRulesEditor |
| `docs/specs/modules/issue_224_wizard_alert_rules_editor.md` | Spec für Wizard-Umstellung |

## Existing Patterns

- **AlertRule.kind** existiert im Datenmodell überall (Frontend TS, Go, Python) — aber die UI zeigt/editiert es nicht
- **AlertRuleRow** hat View/Edit-Modus-Pattern: inline Edit mit Save/Cancel
- **newDefaultRule()** erzeugt Rules mit fixem kind='absolute' — muss angepasst werden wenn Modus-Toggle eingeführt wird
- **Legacy-Migration:** Alte `report_config.change_threshold_*` → Delta-Rules (loader.py) — Bestandsdaten haben bereits kind='delta'
- **Design-System:** Pill, Eyebrow, GCard-Muster für Cards — ModeCard wäre neues Pattern

## Dependencies

- **Upstream:** Issue #223 (AlertRulesEditor), Issue #224 (Wizard-Umstellung) — beide done
- **AlertRule.kind-Feld** im Datenmodell vorhanden (TS/Go/Python) — keine Backend-Änderung nötig
- **Downstream:** Issue #180 (Schwellwert-Tabelle), #181 (Cooldown), #182 (Alert-Preview) — bauen auf #179 auf

## Open Questions

1. **Global vs. Pro-Regel:** Ist der Modus ein globaler Switch (alle neuen Regeln bekommen diesen Modus) oder pro Regel wählbar?
2. **UI-Platzierung:** Über AlertRulesEditor (vor der Regelliste) oder im AlertRuleRow-Edit-Modus?
3. **"Beides"-Semantik:** Bedeutet "Beides" = zwei separate Rules (eine absolute + eine delta) oder ein neuer kind-Wert 'both'?
4. **Beschreibungs-Texte + Beispiele:** Müssen im Issue oder der Spec definiert werden

## Risks & Considerations

- **newDefaultRule() muss Modus kennen** — wenn Global-Toggle, muss der erzeugte Default-Kind den gewählten Modus reflektieren
- **Backward Compatibility:** Bestehende Trips haben Rules mit kind='absolute' oder kind='delta' — UI muss diese korrekt anzeigen
- **Design-Muster ModeCard:** Noch nicht im Design-System — neues Komponenten-Pattern
- **"Beides"-Implementierung** ist komplex wenn es zwei Rules erzeugt statt eines neuen kind-Werts
