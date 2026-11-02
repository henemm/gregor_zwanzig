---
entity_id: fix_2209_tmpmin_dublette
type: bugfix
created: 2026-11-02
updated: 2026-11-02
status: draft
version: "1.0"
severity: MEDIUM
tags: [trip-report, email, metric-catalog, selectable, epic-2259, issue-2209]
---

# Bugfix #2209: Trip-Mail zeigt Spalte „TmpMin" als Dublette zu „Temp"

## Approval

- [ ] Approved

## Purpose

Die Trip-Briefing-Mail (HTML und Plain) zeigt in der Stundentabelle und im Nacht-Block zusätzlich zu „Temp" eine Spalte „TmpMin" (`temperature_cold`) mit identischem Zahlenwert (beide lesen `t2m_c`). `temperature_cold` ist `selectable=False` (#914) und ein reiner Alarm-Baustein (Tiefsttemperatur-Alarm); nicht wählbare Metriken müssen beim Rendern still ignoriert werden (PO-Regel #710/#715). Der Guard fehlt im echten Zeilenbau. Epic #2259 Strang C (Einträge C2-76, B1-21, B1-07, B1-08 aus #1199).

## Source

- **File:** `src/output/renderers/trip_report.py`
- **Identifier:** `TripReportFormatter._dp_to_row` (Z. 688), `TripReportFormatter._aggregate_night_block` (Z. 591)
- **Schicht:** Python-Core (Renderer). Kein Frontend, keine Go-API betroffen.

Weitere Fundstellen (alle am Code geprüft):

| Datei | Stelle | Rolle |
|---|---|---|
| `src/output/renderers/email/helpers.py` | `dp_to_row` (Guard Z. 122-125), `aggregate_night_block` (Guard ~Z. 186) | Zweiter Zeilenbau MIT Guard; Muster-Vorbild, produktiv nicht der Pfad der Trip-Mail |
| `src/app/metric_catalog.py` | Z. 172-176 | `temperature_cold`: label „Tiefsttemperatur-Alarm", col_label „TmpMin", `col_key=temp_cold`, `selectable=False` |
| `src/app/models.py` | Z. 695-710 `_SELECTABLE_GATE_EXEMPT`, Z. 713 `_is_selectable`, Z. 736 `_filter_metrics_by_report_type` | Ausnahmeliste, deren einziger Eintrag diese Scheibe ist |
| `src/output/renderers/email/html.py` | `remaining`-Zweig | hängt aus `resolve_metric_col_order` herausgefallene Spalten hinten an; bleibt unverändert (harmlos, sobald die Zeile den Key nicht mehr trägt) |

## Estimated Scope

- **LoC:** ca. +60 / -20 (überwiegend Tests)
- **Files:** 2 Quell-Dateien (`trip_report.py`, `models.py`) + 4-6 Test-Dateien
- **Effort:** medium (Renderer-Gate und Ratsche erhöhen den Aufwand, nicht der Code)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `get_metric` / `MetricDefinition.selectable` | Katalog | Quelle der Regel „nicht wählbar" |
| `NO_HOURLY_COLUMN_METRIC_IDS` | Konstante (helpers.py) | Bereits „EINE Quelle" für beide Trip-Zeilenbauer; Muster für den Guard |
| `_visible_cols` (trip_report.py:735) | Methode | filtert nur nach Zeilen-Keys, erbt den Fix automatisch |
| `briefing_mail_validator.py` | Hook-Validator | Renderer-Gate: frisch grün gegen echte Staging-Mail |

## Implementation Details

```
trip_report.py, in _dp_to_row UND _aggregate_night_block, direkt nach get_metric():
    if not metric_def.selectable:
        continue          # PO-Regel #710/#715: nicht waehlbare Metriken still ignorieren
```

- Der Guard steht NACH dem `get_metric`-Lookup (er braucht `metric_def`) und VOR der Wertbildung. Er ist kein Katalog-Fehltreffer (kein `KeyError`), sondern eine bewusste, dokumentierte Auslassung wie in `helpers.py:122-125`.
- Resolution-Loss-Ratsche (`tests/test_resolution_loss_guard.py`, `KNOWN_VIOLATIONS` ab Z. 687): geführt sind `_aggregate_night_block::0` (A1) und `_dp_to_row::0` (A2), beide für den `except KeyError: continue` beim Katalog-Lookup. Der Scanner zählt `continue`-Stellen je Funktion mit Index. Der neue Guard steht NACH dem Lookup und ist eine Selektions-Auslassung ohne Mengenrelation zum Lookup; der Scanner behandelt den gleichartigen Guard in `helpers.py` bereits ohne Eintrag. Der Entwickler MUSS vor dem Commit `uv run pytest tests/test_resolution_loss_guard.py` laufen lassen: bleibt der Lauf grün, ist nichts zu tun; verschiebt sich ein Schlüssel-Index (`::0` → `::1`) oder meldet der Scanner einen neuen Fund, werden die `KNOWN_VIOLATIONS`-Schlüssel bewusst von Hand nachgezogen (Muster A4/A12/A13 im Kommentar) und im PR benannt. Die Ratsche darf nicht umgangen und die Zahl der bekannten Verstöße nicht erhöht werden.
- `_SELECTABLE_GATE_EXEMPT` (`models.py:710`) wird auf `frozenset()` verkleinert (oder samt Verzweigung in `_is_selectable` entfernt) und der zugehörige Kommentarblock Z. 695-709 gestrichen. Die Menge darf nur schrumpfen; die Begründung „gehört zu eigener, noch nicht begonnener Scheibe" ist mit dieser Scheibe erledigt.
- **Vorab zu prüfen (Gate-Test #1585, `tests/tdd/test_channel_metric_matrix.py`):** Die Datei importiert `_SELECTABLE_GATE_EXEMPT` (Z. 104). Betroffen sind:
  - `test_ac5_temperature_cold_mail_column_via_remaining_fallback` (Z. 634) behauptet „TmpMin" in der Kopfzeile und ist nach dem Fix absichtlich rot → wird zum Negativ-Test umgedreht („TmpMin" fehlt in `<thead>`).
  - `test_ac6_temperature_cold_hourly_duplicate_characterization` (Z. 663) fixiert die Dublette als Charakterisierung → wird zum Nachweis „Temp vorhanden, TmpMin fehlt" umgeschrieben.
  - `test_ac8_non_selectable_metrics_stay_out_unless_exempt` (Z. 709) überspringt `temperature_cold` per Exemption; mit leerer Menge läuft der Test für `temperature_cold` generisch mit und muss grün sein.
  - `test_ac3_temperature_cold_cold_alarm_stays_active` (Z. 592) sichert den Alarmpfad (läuft über die OR-Tupel-Abbildung `("temperature_cold", "temperature")`, liest die Exemption nicht) und muss unverändert grün bleiben.
  - `test_ac7_temperature_cold_absent_from_compare_catalog` bleibt unberührt.
- **Nebenwirkung der Exemption-Entfernung:** `_filter_metrics_by_report_type` (models.py:736) speist `get_metrics_for_channel` (E-Mail, SMS, Telegram, Alarm-Auflösung in `notification_service.py:584/614`). Ohne Exemption fällt `temperature_cold` dort überall heraus. Der Entwickler prüft per Test je Kanal (E-Mail · Telegram · SMS · Premium-SMS), dass kein Briefing- oder Alarm-Inhalt verloren geht, der heute aus `temperature_cold` stammt (SMS-Token „TN"/Nacht-Tiefsttemperatur laufen über die eigene wählbare Metrik `night_temperature` aus #1484, nicht über `temperature_cold`). Zeigt sich ein Inhaltsverlust in einem Kanal, bleibt die Exemption bestehen, AC-5 wird als nicht erfüllbar markiert und der Befund geht an den Main Context zurück; es wird nichts still abgeschwächt.

## Expected Behavior

- **Input:** Trip mit Default-Anzeigekonfiguration (`temperature_cold.enabled=True`, wie bei Bestands-Trips).
- **Output:** Stundentabelle und Nacht-Block (HTML, Plain, Telegram-Tabellenteil) tragen genau eine Temperatur-Spalte „Temp"; keine Spalte „TmpMin". Die Tabellenlegende führt keinen Eintrag „Tiefsttemperatur-Alarm" bzw. „TmpMin" mehr.
- **Side effects:** Bestands-Trips mit `temperature_cold` in der gespeicherten Konfiguration laden unverändert (kein Schema-/Datenumbau, kein Daten-Rewrite); der Eintrag wird nur beim Rendern still ignoriert. Alarmpfade bleiben wirksam.
- **Mandantentrennung:** n/a. Kein datenbewegender Endpoint, kein Zugriff auf Nutzerdaten außerhalb der übergebenen Anzeigekonfiguration. Getestet wird gegen Konfigurationen, nicht gegen `user_id`-Pfade.
- **Kanäle:** Betrifft die Briefing-Tabelle (E-Mail HTML+Plain, Telegram-Tabellenteil). SMS und Premium-SMS tragen keine Spalte „TmpMin"; ihr Inhalt darf sich nicht ändern (siehe AC-3, AC-5).

## Acceptance Criteria

- **AC-1:** Given ein Trip mit Default-Anzeigekonfiguration (`temperature_cold` aktiv) / When das Trip-Briefing über `TripReportFormatter` als HTML- und Plain-Mail gerendert wird / Then enthalten Stundentabelle UND Nacht-Block weder im HTML-`<thead>` noch im Plain-Tabellenkopf eine Spalte „TmpMin", die Spalte „Temp" ist weiterhin mit Wert vorhanden.
  - Test: Verhaltenstest gegen den echten Renderer, Kopfzeilen beider Formate auslesen; Mutation (Guard entfernen) macht ihn rot.

- **AC-2:** Given eine Anzeigekonfiguration mit einer aktivierten, aber nicht wählbaren Metrik (`selectable=False`, z. B. `temperature_cold`, `confidence`, `cape`) / When `TripReportFormatter._dp_to_row` und `TripReportFormatter._aggregate_night_block` die Zeile bauen / Then enthält das Zeilen-Dict keinen `col_key` dieser Metrik und es wird weder ein Fehler geworfen noch eine Meldung ausgegeben (stilles Ignorieren, gleiche Semantik wie `helpers.dp_to_row`).
  - Test: Direktaufruf der Produktiv-Methoden (nicht nur `email/helpers`) in einem neuen Test; bestehende Tests, die `fmt._dp_to_row` rufen, bleiben grün.

- **AC-3:** Given die Tiefsttemperatur-Alarmpfade (`AlertMetric.TEMPERATURE_MIN`, `cmp="unter"`, `alert_label`) / When ein Trip mit Default-Konfiguration geprüft und ein Kältealarm ausgelöst wird / Then bleibt der Alarm aktiv und liefert denselben Inhalt wie vor dem Fix, in allen vier Kanälen (E-Mail, Telegram, SMS, Premium-SMS).
  - Test: `test_ac3_temperature_cold_cold_alarm_stays_active` unverändert grün plus ein Alarm-Render-Test über Vorher/Nachher-Gleichheit; Alarmpfade laufen nicht über `_dp_to_row`.

- **AC-4:** Given eine nach dem Fix gerenderte Trip-Briefing-Mail mit Tabellenlegende / When die Legende gelesen wird / Then enthält sie keinen Eintrag „Tiefsttemperatur-Alarm" (Katalog-Label von `temperature_cold`) und keinen Verweis auf „TmpMin"; die Legende zu „Temp" bleibt unverändert.
  - Test: Verhaltenstest auf die gerenderte Legende (HTML und Plain); erledigt Eintrag B1-21.

- **AC-5:** Given `_SELECTABLE_GATE_EXEMPT` in `src/app/models.py` mit dem einzigen Eintrag `temperature_cold` / When der Fix umgesetzt ist / Then ist die Menge um diesen Eintrag verkleinert (leer oder samt Verzweigung entfernt), der Kommentarblock ist gestrichen, `test_channel_metric_matrix.py` (AC-5 umgedreht, AC-6 umgeschrieben, AC-8 läuft für `temperature_cold` mit, AC-3/AC-7 unverändert) ist grün, und kein Kanal verliert Briefing- oder Alarm-Inhalt, der heute aus `temperature_cold` stammt.
  - Test: Lauf von `tests/tdd/test_channel_metric_matrix.py`; Kanal-Vergleichstest vor/nach. Bei nachgewiesenem Inhaltsverlust bleibt die Exemption stehen und der Befund geht an den Main Context zurück.

- **AC-6:** Given die Bestands-Baseline-Tests, die „TmpMin" als dokumentierte Abweichung einfrieren (`tests/unit/test_mail_column_order.py::test_legacy_config_without_order_keeps_catalog_order` Z. 147 mit Baseline `[..., "Sun", "TmpMin"]`, `tests/unit/test_mail_plain_column_order.py` Z. 174-185 und Z. 224 „AC-5") und die Resolution-Loss-Ratsche / When der Fix umgesetzt ist / Then sind die Baselines bewusst auf die Reihenfolge ohne „TmpMin" nachgezogen (Docstrings: Abweichung behoben statt „Bestand"), `tests/test_resolution_loss_guard.py` ist ohne Erhöhung der bekannten Verstöße grün (Schlüssel gegebenenfalls von Hand nachgezogen), und das Renderer-Commit-Gate ist erfüllt: Modus-Matrix-Test und `briefing_mail_validator.py` frisch grün gegen eine echte Staging-Mail.
  - Test: genannte Testdateien einzeln benannt laufen lassen (kein nacktes `uv run pytest`); Validator-Exit 0 im E2E.

## Known Limitations

- **Out of Scope:** Konsolidierung der zwei Zeilenbauer (`trip_report.py` vs. `email/helpers.py`). Die Dopplung ist die Ursache, dass Tests den falschen Choke-Point prüften. Sie wird als Folge-Issue angelegt, nicht still mitgenommen. Mindestfix = Guard im Produktivpfad + zusätzliche Tests gegen den Produktivpfad.
- Der `remaining`-Zweig in `email/html.py` bleibt bestehen (wird für `temperature_cold` nicht mehr erreicht, kein Rückbau in dieser Scheibe).
- Die Test-Importe von `email/helpers.dp_to_row` in ca. 14 Tests werden nicht umgestellt, nur der Produktivpfad wird ergänzt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Setzt die bestehende PO-Regel „nicht wählbare Metriken still ignorieren" (#710/#715, #1585) an einer bisher übersehenen Stelle um; keine neue Entscheidungsfläche. `_SELECTABLE_GATE_EXEMPT` verkleinert sich wie vorgesehen („darf nur schrumpfen").

## Changelog

- 2026-11-02: Initial spec created (Issue #2209, Epic #2259 Strang C)
