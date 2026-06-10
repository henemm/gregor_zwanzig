# Context: Issue #687 — Alerts: Soll-Ist-Abgleich

## Request Summary
Issue besteht nur aus zwei Screenshots (kein Text), Titel „Alerts: Soll - Ist Abgleich", Labels `priority:high`, `type:bug`. Die Screenshots zeigen den **Alert-Regel-Editor** im Edit-Modus (ModeCards Absolut/Δ/Beides + Editor-Zeile mit Metrik-Select, Wert, **Severity-Dropdown Info/Warnung/Kritisch**, Aktiv, Speichern). Der PO vergleicht diesen Editor („Ist") mit dem in Issue #638 neu eingeführten Alerts-Karten-Modell („Soll") und stellt fest: sie laufen auseinander.

## Kernbefund: zwei parallele, divergierende Alert-UIs

| Aspekt | **SOLL** — `AlertsTab` + `AlertCard` (#638) | **IST** — `AlertRulesEditor` + `AlertRuleRow` (#223/#179/#297) |
|--------|----------------------------------------------|---------------------------------------------------------------|
| Wo verwendet | Trip-Detail → Tab „Alerts" (Ansicht) | Trip **anlegen** (`TripNewEditor`), Trip **bearbeiten** (`TripEditView`), **Wizard** Step 4 (`Step4Briefings`) — = die Screenshots |
| Severity-Auswahl | **entfernt** (Spec #638: „in der UI nicht mehr editiert") | **noch vorhanden** (Select Info/Warnung/Kritisch, Zeile 235–242) |
| Kanal pro Alert | Kanal-Chips (email/telegram/sms) pro Regel | **fehlt** |
| Modell-Darstellung | Karte: Metrik · Bedingung (mono), Switch | ModeCards (Absolut/Δ/Beides) + flache Editor-Zeile |
| Alert hinzufügen | Button `disabled` (Hinzufügen passiert im Editor) | „+ Regel hinzufügen" aktiv |

Der eigentliche **Erstell-/Bearbeitungs-Pfad** für Alarmregeln läuft über den alten `AlertRulesEditor` — dort wurde die #638-Entscheidung (keine Severity-Auswahl, Kanal pro Alert) **nicht nachgezogen**. #638 hat ausschließlich den Anzeige-Tab umgebaut.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte` | IST-Editor; Severity-Select Z.235–242, ModeCards, Thunder-Level-Dropdown MITTEL/HOCH Z.168–176 |
| `frontend/src/lib/components/alert-rules-editor/AlertRulesEditor.svelte` | Container (Liste + „+ Regel hinzufügen") |
| `frontend/src/lib/components/alert-rules-editor/ModeCard.svelte` | Die „ABSOLUT/Schwellwert"- & „ÄNDERUNG/Δ Differenz"-Karten + „1 Feld/2 Felder"-Badges (statische Beispiel-Copy) |
| `frontend/src/lib/components/alert-rules-editor/alertRuleDefaults.ts` | `newDefaultRule`, `expandRules`, `DELTA_ONLY_METRICS` |
| `frontend/src/lib/components/alerts-tab/AlertCard.svelte` | SOLL-Karte (#638): kein Severity, Kanal-Chips, Switch |
| `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` | SOLL-Tab (#638) |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | nutzt AlertRulesEditor |
| `frontend/src/lib/components/edit/TripEditView.svelte` | nutzt AlertRulesEditor |
| `frontend/src/lib/components/trip-wizard/steps/Step4Briefings.svelte` | nutzt AlertRulesEditor (Wizard) |
| `frontend/src/lib/utils/alertMetricLabels.ts` | `SEVERITY_LABEL_DE`, `thunderLevelLabel`, `ALERT_METRIC_LABELS` |
| `frontend/src/lib/types.ts` | `AlertRule` (severity, channels, kind, threshold) |
| `internal/model/trip.go` / `src/app/models.py` | AlertRule-Schema (severity bleibt im Schema, nicht mehr send-relevant) |
| `docs/specs/modules/issue_638_alerts_redesign.md` | Soll-Definition: keine Severity-UI, Kanal pro Alert |

## Existing Patterns
- #638 hat Severity nur als **Label/Metadatum** belassen (Schema + Cockpit-Token), aber aus Versand-Entscheidung UND UI entfernt.
- Migration-Treue (BUG-DATALOSS-GR221): `severity` bleibt parsebar (`d.get("severity","warning")`), `channels` defaultet auf `[]` = „erbe Briefing-Kanäle".
- Kanal-Vorbelegung: aus `report_config.send_email/telegram/sms`.

## Risks & Considerations
- **Scope-Frage (PO):** Nur Severity-Auswahl aus dem Editor entfernen (minimal, deckt #638-Soll) — oder zusätzlich Kanal-pro-Alert-Auswahl in den Editor bringen (volle Vereinheitlichung)?
- `severity` bleibt im Schema; beim Entfernen des Selects muss `newDefaultRule()` weiter eine gültige Default-Severity setzen (kein Schemabruch, kein Datenverlust).
- Drei Einbau-Orte (anlegen/bearbeiten/Wizard) müssen konsistent bleiben.
- `thunder_level` ist delta-only; ModeCard „Absolut" für Gewitter ist semantisch widersprüchlich (sekundär).

## Existing Specs
- `docs/specs/modules/issue_638_alerts_redesign.md` — Soll-Modell
- `docs/specs/modules/issue_223_alert_rules_editor.md` — Ist-Editor
- `docs/specs/modules/issue_179_alert_konfigurator_modus_toggle.md` — ModeCards
- `docs/specs/modules/issue_297_alert_beides_mode.md` — Beides-Modus / Felder
