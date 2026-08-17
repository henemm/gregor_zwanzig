# Context: fix-1714-compare-alert-dedup

## Request Summary
Das Ortsvergleich-Briefing zeigt amtliche Warnungen an, vermerkt sie aber nicht im
Melde-Gedächtnis. Der unabhängige Ortsvergleich-Prüfer (Alarm-Checker, alle 15 Min) kennt
diese Warnungen deshalb nicht als „bereits gemeldet" und verschickt dieselbe, unveränderte
Warnung kurz darauf erneut als eigenständigen Alarm. Der Trip-Pfad hat diese Lücke bereits
seit #1614 geschlossen — der Ortsvergleich-Pfad bekam das Gegenstück nie.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/scheduler_dispatch_service.py` (`send_one_compare_preset`, ~L350-580) | Versendet das Compare-Briefing. Ruft `NotificationService.send_compare_report(...)` **ohne den Rückgabewert zu erfassen** und danach `_anchor_and_reset()`. Genau hier fehlt der Aufruf von `record_official_alerts_reported` — das exakte Analogon zu `trip_report_scheduler.py:1638-1645`. |
| `src/services/alert_briefing_anchor.py` (`record_official_alerts_reported`, L312-343) | DIE geteilte Schreib-Logik fürs Melde-Gedächtnis (`official_alert:`-Namensraum). Signatur: `(*, user_id, entity_id, alerts)`. Fail-soft No-Op bei leerer Liste. Für Compare ist `entity_id = f"{preset_id}:{loc.id}"` (bereits das etablierte Kennungs-Schema für Compare-Anker, s. `_anchor_and_reset`). |
| `src/services/compare_official_alert.py` (`_record_state`, L313-322; `_detect`, L221-260) | Der ALARM-CHECKER-seitige Lesepfad. `_detect()` lädt State über `AlertStateService(user_id).load(f"{preset_id}:{loc_id}")` und entscheidet über `official_alert_revision_verdict()`, ob eine Warnung neu/eskaliert ist. `_record_state` ist eine **eigene Inline-Kopie** derselben Schreib-Logik wie `record_official_alerts_reported` — schreibt aber nur NACH eigenem Alarmversand, nie aus dem Briefing-Pfad. Genau diese fehlende zweite Schreibquelle ist der Bug. |
| `src/services/comparison_engine.py` (`run_comparison_parallel`, L300-340ff.) | Liefert `result.locations: list[LocationResult]`, jedes Element trägt `.official_alerts: list[OfficialAlert]` (leer wenn `official_alerts_enabled=False` oder Fetch-Fehler) und `.location.id`. Das ist die Quelle für die im Briefing gezeigten Warnungen je Ort. |
| `src/services/notification_service.py` (`send_compare_report`, L956ff., `NotificationResult`, L114ff.) | Gibt `NotificationResult` mit `.sent: bool` zurück — aktuell am Aufrufort verworfen. Muss erfasst werden, um (analog Trip) nur bei tatsächlichem Versand zu vermerken. |
| `src/services/trip_report_scheduler.py` (L1629-1646) | Vorbild-Pfad (Trip-Seite, #1614 Teil 1): `if result.sent and not on_demand: ... record_official_alerts_reported(user_id=..., entity_id=trip.id, alerts=all_official_alerts)` — direkt VOR `_anchor_and_reset()`. |
| `tests/tdd/test_alert_state_briefing_reset.py` | Test-Vorbild für die Trip-Seite: u. a. `test_briefing_meldet_unveraenderte_amtliche_warnung_danach_nicht_erneut`, `test_eskalierte_warnung_wird_trotz_bereits_gemeldeter_unveraenderter_warnung_weiterhin_gemeldet`, `test_ad_hoc_abruf_schreibt_das_melde_gedaechtnis_amtlicher_warnungen_nicht`, `test_fehlgeschlagener_versand_schreibt_das_melde_gedaechtnis_nicht`. Diese Namen/Fälle 1:1 auf Compare spiegeln (neue Testdatei oder Ergänzung, TDD-RED entscheidet Ablage). |

## Existing Patterns
- **Geteilter Schreibbaustein statt Kopie** (#1467 S2 AG5, PO-Vorgabe „verwende zwingend den
  gleichen Code"): `record_official_alerts_reported` und `reset_alert_memory` sind bereits die
  EINE Fassung für Trip UND Compare — nur der Aufruf-Ort im Compare-Briefing-Pfad fehlt.
- **`on_demand` schützt Ad-hoc-Abrufe** (#1007/#1467 S2 AG5): sowohl Trip als auch Compare
  dürfen bei Handversand (`on_demand=True`) das Melde-Gedächtnis nicht anfassen. Die neue
  Schreibung muss `not on_demand` genauso gaten wie `_anchor_and_reset()` es bereits tut.
- **Vor `_anchor_and_reset()`, im try-Block, nur bei `result.sent`**: Trip-Vorbild platziert
  den Record-Aufruf VOR dem Anker/Reset, gated auf tatsächlichen Versand — Fehlerpfad
  (Exception im Versand) darf nichts vermerken, sonst gälte eine nie zugestellte Warnung
  fälschlich als „gemeldet".
- **Kennungs-Schema Compare**: `f"{preset_id}:{loc.id}"` durchgängig für Alarm-State UND
  Delta-Anker (NICHT `preset_id` allein — das ist reserviert für die Briefing-Protokoll-Kennung,
  s. `briefing_entity_id=preset_id` in `_anchor_and_reset`).

## Dependencies
- Upstream: `send_one_compare_preset()` wird von zwei Stellen gerufen — dem Daily-Loop
  (`run_compare_presets_daily`, `on_demand` je nach Aufruf) und dem Einzelversand
  (`send_compare_preset`, IMMER `on_demand=True`, s. Docstring L590-593). Der Fix wirkt also
  automatisch nicht bei Handversand — korrekt nach Vorbild.
- Downstream: `compare_official_alert.py::_detect()` liest denselben State-Namensraum
  (`AlertStateService(user_id).load(f"{preset_id}:{loc_id}")`) über
  `official_alert_revision_verdict()`. Kein Code-Wechsel dort nötig — der Fix liefert dem
  Lesepfad nur zusätzliche Einträge.

## Existing Specs
- `docs/specs/modules/fix_1614_briefing_warnfenster.md` — Trip-seitiges Vorbild (#1614 Teil 1),
  ACs dort sind die Vorlage für die Compare-Spiegelung laut Issue-Text.
- `docs/specs/modules/rework_1467_s4b_entdopplung.md` — Ereignis-Identität-Entdopplung
  (anderer Mechanismus, thematisch benachbart, **kein** Überschneidungscode).

## Analysis

### Type
Bug (nutzersichtbares Fehlverhalten — Doppelversand derselben amtlichen Warnung).

Kein Subagenten-Dispatch nötig: Der Standard-Track kombiniert Context+Analyse (CLAUDE.md), und
die Kontext-Phase hat bereits den vollständigen, direkt am Code verifizierten Befund geliefert
(exakte Zeilen, exakter Vorbild-Pfad, exaktes Kennungs-Schema) — ein Re-Dispatch würde nur
dieselbe bereits gelesene Quelle erneut durchsuchen.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/scheduler_dispatch_service.py` | MODIFY | `send_one_compare_preset`: Rückgabewert von `NotificationService.send_compare_report(...)` erfassen (aktuell verworfen). Direkt danach, noch im try-Block, vor `_anchor_and_reset()`: bei `send_result.sent and not on_demand` je Ort mit gezeigten `official_alerts` `record_official_alerts_reported(user_id=..., entity_id=f"{preset_id}:{loc.id}", alerts=...)` aufrufen — analog `trip_report_scheduler.py:1638-1645`, aber PRO ORT statt einmal aggregiert (Compare-Kennung ist ortsbezogen). |
| `tests/tdd/test_compare_official_alert_briefing_reset.py` (neu) | CREATE | Spiegelt die relevanten Fälle aus `tests/tdd/test_alert_state_briefing_reset.py` auf den Compare-Pfad: unveränderte Warnung nach Briefing nicht erneut gemeldet · eskalierte Warnung trotzdem gemeldet · `on_demand=True` fasst das Melde-Gedächtnis nicht an · fehlgeschlagener Versand (Exception im try-Block) schreibt nichts · zwei Nutzer bleiben getrennt (Mandantentrennung, CLAUDE.md-Pflicht) · zwei Orte im selben Preset — ein still übersprungener Ort verliert sein Melde-Gedächtnis nicht (R3-Analogie). |

### Scope Assessment
- Files: 2 (1 MODIFY, 1 CREATE)
- Estimated LoC: production ~15-20 (Rückgabewert erfassen + Schleife über Orte + Gate),
  Tests ~150-220 (6 Fallgruppen, mehrere davon brauchen echten Preset-/Location-Fixture-Aufbau
  wie im Trip-Vorbild)
- Risk Level: MEDIUM — kein neuer Mechanismus (reine Verdrahtung eines bereits geteilten,
  produktiv erprobten Bausteins), aber Service-Schnittstelle mit Mandanten-Zustand und
  koordinierter Parallel-Arbeit an derselben Datei-Familie (#1657, Schlüsselformat)

### Technical Approach
1. `send_result = NotificationService(settings, user_id).send_compare_report(...)` — Rückgabewert
   binden statt verwerfen.
2. Direkt danach, noch innerhalb des bestehenden `try`-Blocks (Fehlerpfad bleibt dadurch
   automatisch ausgeschlossen — Exception springt vorher in den `except`-Zweig):
   ```python
   if send_result.sent and not on_demand:
       from services.alert_briefing_anchor import record_official_alerts_reported
       for loc_result in result.locations:
           if loc_result.official_alerts:
               record_official_alerts_reported(
                   user_id=user_id,
                   entity_id=f"{preset_id}:{loc_result.location.id}",
                   alerts=loc_result.official_alerts,
               )
   ```
3. Kein Eingriff in `compare_official_alert.py` (`_detect`/`_record_state` unverändert) — die
   Refactoring-Frage aus dem Issue („Kopie durch geteilte Fassung ersetzen?") wird NICHT
   mitgezogen, um die Scheibe minimal und den Blast Radius auf den Briefing-Aufrufpfad
   beschränkt zu halten.
4. Reihenfolge zu `_anchor_and_reset()`: VOR dem Aufruf, wie im Trip-Vorbild kommentiert
   („VOR write_anchor_and_reset_memory, damit ein Exception-Pfad dort das Record nicht
   verschluckt" — Reihenfolge-Invariante 1:1 übernehmen).

### Dependencies
Siehe Context-Abschnitt oben — keine neuen Abhängigkeiten, nur ein zusätzlicher Aufruf eines
bereits vorhandenen, geteilten Bausteins.

### Open Questions
- [ ] Test-Dateiname/-Ablage: neue Datei vs. Ergänzung in einer bestehenden Compare-Testdatei —
  wird in TDD-RED entschieden, nicht spec-relevant.
- [ ] Aus dem Issue übernommene, aber bewusst NICHT in dieser Scheibe behandelte Frage: soll
  `compare_official_alert.py::_record_state` künftig an `record_official_alerts_reported`
  delegieren (Teilungsregel, CLAUDE.md)? Empfehlung: separates Nebenbefund-Ticket (#1199), nicht
  Teil der Akzeptanz hier — Scope-Disziplin vor Perfektionismus.

## Risks & Considerations
- **Geteilter Zustand mit Parallel-Arbeit an #1657** (koordiniert, andere Session): #1657 ändert
  möglicherweise das Schlüsselformat in `official_alert_state_key()`
  (`valid_from`/`valid_to`-Anteil). Diese Scheibe ändert den Schlüssel NICHT, nur die
  Schreibhäufigkeit/-quelle — sollte orthogonal sein. Vor Commit an genau dieser Funktion:
  Rücksprache halten (bereits zugesagt).
- **Kein neuer State-Namensraum, keine Migration** — reine Verdrahtung, kein Schema-Rework.
- **Zwei Aufrufstellen von `send_one_compare_preset`**: Fix muss in der GEMEINSAMEN Funktion
  sitzen (nicht an einer der beiden Call-Sites), sonst gilt er nur für einen Pfad.
- **Mandantentrennung**: `record_official_alerts_reported` nimmt `user_id` explizit entgegen —
  `send_one_compare_preset` hat bereits `user_id` als Parameter. Test mit zwei Nutzern PFLICHT
  (CLAUDE.md-Vorgabe).
- **Batch-Teilfilterung nicht betroffen**: Diese Scheibe schreibt nur das Melde-Gedächtnis nach
  erfolgreichem Briefing-Versand — die im Issue erwähnte Frage „darf eine gesunde Warnung nicht
  mit einem Duplikat zusammen verschluckt werden" betrifft den ALARM-Checker-Batch-Pfad
  (`compare_official_alert.py`), der hier unverändert bleibt.
- **Kein Anlass, `_record_state` in `compare_official_alert.py` durch den geteilten Baustein zu
  ersetzen** — das im Issue als „zu prüfen" genannte Refactoring ist optional, nicht
  Teil der Akzeptanz. Bei Zeitdruck: nur verdrahten, Kopie unangetastet lassen; die Spec-Phase
  entscheidet verbindlich.
