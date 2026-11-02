# Context: fix-2209-tmpmin-dublette

## Request Summary
Trip-Briefing-Mail zeigt in der Stundentabelle die Spalte „TmpMin" (`temperature_cold`) zusätzlich zu „Temp" — beide mit identischem `t2m_c`-Wert. `selectable=False` wird am echten Zeilenbau (`TripReportFormatter._dp_to_row`/`_aggregate_night_block`) nicht beachtet. Issue #2209 (Epic #2259, Strang C).

## Related Files
| File | Relevance |
|------|-----------|
| src/output/renderers/trip_report.py:688 `_dp_to_row`, `_aggregate_night_block` (~:607) | ECHTER Produktiv-Zeilenbau (Aufrufer :164, :299, :530, :586). Kein `selectable`-Guard. |
| src/output/renderers/email/helpers.py:105 `dp_to_row`, :160 `aggregate_night_block`, `NO_HOURLY_COLUMN_METRIC_IDS` | Zweiter Zeilenbau MIT `selectable`-Guard (:128/:186); laut Issue ohne Produktiv-Aufrufer, wird aber von ~14 Tests als Prüfling benutzt (falscher Choke-Point) |
| src/app/metric_catalog.py:172 | `temperature_cold`: label „Tiefsttemperatur-Alarm", col_label „TmpMin", `selectable=False` (#914), `col_key=temp_cold` |
| src/app/models.py:703-710 | `_SELECTABLE_GATE_EXEMPT = {"temperature_cold"}` — dokumentierter Bestand „gehört zu eigener Scheibe" = diese Scheibe |
| src/output/renderers/email/html.py:~526 | `remaining`-Zweig hängt TmpMin hinten an |
| tests/unit/test_mail_column_order.py:147 | `test_legacy_config_without_order_keeps_catalog_order` friert Baseline inkl. „TmpMin" ein → muss mit dem Fix angepasst werden |
| tests/unit/test_mail_plain_column_order.py | ebenfalls TmpMin-Bezug |
| tests/tdd/test_issue_715_confidence_not_selectable.py | prüft `helpers.dp_to_row` (nicht den Produktivpfad) |
| tests/test_resolution_loss_guard.py:687-856 | Ratsche über `_dp_to_row`/`_aggregate_night_block`/helpers-Pendants (Zählung der `continue`-Stellen) — jeder neue `continue` im Zeilenbau berührt sie |
| tests/integration/test_config_persistence.py, test_friendly_format_and_alerts_config.py | rufen `fmt._dp_to_row` direkt |

## Existing Patterns
- `helpers.dp_to_row` zeigt das Soll: `if not metric_def.selectable: continue` (Issue #710/#715, PO-Regel: nicht wählbare Metriken still ignorieren).
- `NO_HOURLY_COLUMN_METRIC_IDS` ist bereits „EINE Quelle" für die Trip-Zeilenbauer (Import in trip_report.py).
- Alarm-Pfade nutzen `temperature_cold` bewusst (cmp="unter", `alert_label`) — dürfen NICHT betroffen sein.

## Dependencies / Dependents
- Upstream: `get_metric`, `dc.metrics`, `build_default_display_config`.
- Downstream: HTML-/Plain-/Telegram-Briefing (`seg_tables`), `briefing_mail_validator`, Legende („TmpMin" → „Tiefsttemperatur-Alarm", Eintrag B1-21).

## Existing Specs
- docs/specs/modules/trip_report_formatter.md; Spec zu #715 (confidence not selectable)

## Risks & Considerations
- Renderer-Commit-Gate: Modus-Matrix-Test + `briefing_mail_validator` frisch grün nötig.
- Resolution-Loss-Ratsche zählt `continue`-Stellen → Soll-Zahl im Test nachziehen oder neuen `continue` vermeiden (Guard als gemeinsame Hilfsfunktion).
- Bestands-Baseline-Tests mit „TmpMin" ändern sich bewusst (Fix beseitigt die dokumentierte Abweichung); `_SELECTABLE_GATE_EXEMPT` darf nur schrumpfen → Eintrag entfällt ggf.
- Doppelter Zeilenbau (trip_report vs. helpers): Konsolidierung wäre größerer Scope; Mindestfix = Guard im Produktivpfad + Tests auf den Produktivpfad umstellen. Entscheidung in Analyse/Spec.
- Prüfen, ob die Legende „TmpMin" nach dem Fix noch vorkommt (B1-21 erledigt sich dann mit).

## Analysis

### Type
Bug (nutzersichtbar: ausgelieferte Trip-Mails; Epic #2259 Strang C; Einträge C2-76, B1-21, B1-07, B1-08 aus #1199)

### Root Cause (verifiziert im Code)
`TripReportFormatter._dp_to_row` (trip_report.py:688) und `_aggregate_night_block` (~:600) iterieren `dc.metrics` und prüfen nur `enabled`, Wind-Merge und `NO_HOURLY_COLUMN_METRIC_IDS` — **nicht** `metric_def.selectable`. `temperature_cold` (selectable=False, dp_field `t2m_c`, col_key `temp_cold`) steht in der Default-Konfiguration → eigene Zeilenspalte „TmpMin" mit identischem Wert wie „Temp". `email/helpers.dp_to_row/aggregate_night_block` haben den Guard (:122/:180), werden aber produktiv nicht gerufen (Tests prüfen den falschen Choke-Point). `_visible_cols` (trip_report:735 / helpers:302) filtert nur nach Zeilen-Keys → Fix an der Zeilenquelle genügt, HTML/Plain/Telegram erben ihn.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/output/renderers/trip_report.py | MODIFY | `selectable`-Guard in `_dp_to_row` und `_aggregate_night_block` (nach `get_metric`, vor Wertbildung) |
| src/app/models.py | MODIFY | `_SELECTABLE_GATE_EXEMPT` Eintrag `temperature_cold` + Kommentar entfernen (Bestand wird behoben; Set darf nur schrumpfen) — Auswirkung auf #1585-Gate vorher prüfen |
| tests/unit/test_mail_column_order.py | MODIFY | Baseline ohne „TmpMin" |
| tests/unit/test_mail_plain_column_order.py | MODIFY | ggf. TmpMin-Bezug |
| tests/test_resolution_loss_guard.py | MODIFY (ggf.) | Ratsche zählt `continue` je Funktion; Guard als `continue` verschiebt Soll-Zahl bewusst nachziehen |
| tests/tdd/test_issue_715_confidence_not_selectable.py + ~14 Tests | MODIFY/ERGÄNZEN | zusätzlicher Test gegen `TripReportFormatter._dp_to_row` (Produktivpfad) |
| tests (neu) | CREATE | Verhaltenstest: gerenderte Trip-Mail (HTML+Plain) enthält keine „TmpMin"-Spalte, „Temp" bleibt; Alarmpfade (cmp="unter") unverändert |

### Scope Assessment
- Files: ~4 Source/Konstanten + 3–5 Test-Dateien
- Estimated LoC: +~60/-~20 (überwiegend Tests)
- Risk Level: MEDIUM — Renderer-Commit-Gate (Modus-Matrix + `briefing_mail_validator` frisch grün), Ratsche, Baseline-Tests; Alarm-Pfade nutzen `temperature_cold` bewusst und dürfen nicht berührt werden (sie gehen nicht über `_dp_to_row`, vor Implementierung per Test absichern).

### Technical Approach
Mindestfix, keine Konsolidierung der zwei Zeilenbauer (größerer Scope → eigenes Ticket, nicht still mitnehmen): gleicher Guard wie in helpers (`if not metric_def.selectable: continue`, Muster #710/#715) in beiden Methoden des Produktivpfads. Tests auf `TripReportFormatter` umstellen/ergänzen. Legende (B1-21) erledigt sich, weil „TmpMin" nicht mehr im Kopf steht — per Test belegen. `remaining`-Zweig in html.py bleibt (harmlos).

### Dependencies
get_metric/dc.metrics/build_default_display_config; downstream HTML-/Plain-/Telegram-Briefing, briefing_mail_validator, Legende.

### Open Questions
- [ ] `_SELECTABLE_GATE_EXEMPT` komplett entfernen oder leer lassen? (Test #1585 prüfen; Tech-Lead-Entscheid in Spec: entfernen)
- [ ] Doppelter Zeilenbau (helpers vs. trip_report) Konsolidierung → Folge-Issue anlegen
