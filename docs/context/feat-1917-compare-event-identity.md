# Context: feat-1917-compare-event-identity

## Request Summary
Issue #1917: Die quellenübergreifende Ereignis-Identitäts-Entdopplung (verhindert, dass Nowcast und amtliche Warnung zum selben Ereignis beide zugestellt werden) ist auf der Trip-Fläche bereits verdrahtet (#1467 S4b-1), auf dem Ortsvergleich (Compare) aber nicht. Dort können Radar-Nowcast und amtliche Warnung zum selben Gewitter weiterhin doppelt zugestellt werden. Der Baustein selbst wurde entitätsparametrisiert gebaut — es fehlt nur die Verdrahtung auf zwei Compare-Services.

## Related Files

| File | Relevance |
|------|-----------|
| `src/services/alert_gate.py:560-654` | `check_event_identity_gate()` + `record_event_identity()` — der wiederzuverwendende Baustein, unverändert zu lassen |
| `src/services/compare_radar_alert.py` | Zustellpfad Nowcast/Compare — Gate-Aufruf fehlt komplett; EIN gebündelter Versand für alle getriggerten Orte (`send_multi_location_radar_alert`, Z. 207-211) |
| `src/services/compare_official_alert.py` | Zustellpfad amtliche Warnung/Compare — Gate-Aufruf fehlt komplett; EIN gebündelter Versand für die gesamte `tagged_alerts`-Liste (Z. 193-199) |
| `src/services/trip_alert.py:1305-1406` | Vorbild Nowcast-Verdrahtung (Trip): Gate unmittelbar vor `send_radar_alert`, `record_event_identity` nach `result.sent` |
| `src/services/trip_alert.py:1671-1803` | Vorbild amtlich-Verdrahtung (Trip), inkl. **Batch-Teilfilterung** Z. 1704-1744: pro Alert eigener Gate-Aufruf, `_official_urgency` NACH dem Filtern neu berechnet, leere `_filtered_notices` → `return False` |
| `docs/specs/modules/rework_1467_s4b_entdopplung.md` | S4b-1-Spec (Trip). Compare (S4b-2) dort explizit als Nicht-Ziel ausgewiesen (Z. 426-429) — kein eigenes Spec-Dokument für #1917 vorhanden, muss neu geschrieben werden |

## Existing Patterns

- **Fail-soft Richtung Zustellung**: jede Unsicherheit (fehlender Zeitbezug, leere Ortskennung, unbekannte Gefahrenart, kaputtes Registerformat) → `_ALLOWED`, nie Unterdrückung. Gilt unverändert für Compare.
- **Prüfreihenfolge**: Eskalation (V2, immer zuerst) → V1-Ausnahme → Unterdrückung. Gate ist LETZTE Stufe vor Zustellung (AC-12).
- **Registrierung nur nach Erfolg**: `record_event_identity()` wird ausschließlich NACH erfolgreicher Zustellung aufgerufen (Symmetrie zu `record_nowcast_sent`), nie vorher.
- **Batch-Teilfilterung** (Trip-Amtlich-Vorbild): bei mehreren Alerts/Orten in einem Lauf wird JEDER einzeln geprüft — ein Duplikat unterdrückt, andere gehen durch (AC-17). Ein globales Alles-oder-nichts-Gate wäre falsch.
- **Bereits vorhandene Entitätstrennung in Compare**: Beide Compare-Services nutzen für ihr JEWEILIGES eigenes Dedup-Gedächtnis (Radar-Onset bzw. amtliches Melde-Gedächtnis) bereits `entity_id = f"{preset_id}:{loc_id}"` — eine eigene Registerdatei pro Ort (`compare_radar_alert.py:277`, `compare_official_alert.py:260/324`). `entity_id` ist im Baustein selbst ein freier String (kein Enum, `alert_state.py:58-59`) — Symmetrie zu Trip ist damit strukturell bereits gedeckt.

## Dependencies

- **Upstream:** `check_event_identity_gate()` / `record_event_identity()` (`alert_gate.py`) — unverändert, keine Signaturänderung nötig (AC-20 aus S4b-1 gilt sinngemäß weiter).
- **Downstream:** keine bekannten Konsumenten der beiden Compare-Services außerhalb des Schedulers (`scheduler_dispatch_service.py` o.ä. — im Detail in der Spec-Phase zu prüfen, falls relevant für ACs).

## Existing Specs
- `docs/specs/modules/rework_1467_s4b_entdopplung.md` (Trip/S4b-1) — Vorlage für ACs, NICHT der Geltungsbereich für Compare.

## Design-Entscheidung: `segment_ids` bei Compare (verifiziert am Code, NICHT mehr offen)

Bei der Trip-Seite läuft die Ortstrennung über den `segment_ids`-Parameter INNERHALB einer gemeinsamen Registerdatei (`entity_id = trip.id`). Bei Compare läuft die Ortstrennung bereits über die Dateigrenze (`entity_id = f"{preset_id}:{loc_id}"`, eine Datei pro Ort) — die naheliegende erste Annahme war deshalb, `segment_ids` beim Compare-Aufruf leer zu lassen.

**Das ist falsch und wäre ein stiller No-Op-Bug.** Verifiziert in `alert_gate.py:492-541` (`_find_matching_entry`): Zeile 508-510 —
```python
new_segments = {s for s in (segment_ids or []) if s}
if not new_segments:
    return None
```
Eine leere `segment_ids`-Menge — aktuell ODER im Registereintrag gespeichert — führt **immer** zu „kein Match" (Docstring nennt das ausdrücklich „AC-5 Bruchstelle"). Würde Compare mit `segment_ids=[]` aufrufen (sowohl beim Check als auch bei `record_event_identity`), fände die Entdopplung NIE ein Match — der Gate-Aufruf sähe verdrahtet aus, würde aber nie unterdrücken. Exakt das Muster aus [[reference_gestubbte_naht_verdeckt_alles_darunter]].

**Entscheidung:** `segment_ids=[loc.id]` (einelementige Liste mit der Ortskennung) bei JEDEM Compare-Aufruf — sowohl `check_event_identity_gate` als auch `record_event_identity`. Die Ortstrennung bleibt primär über `entity_id` (Dateigrenze), `segment_ids=[loc.id]` erfüllt zusätzlich die Nicht-Leer-Bedingung des Bausteins und macht `new_segments.isdisjoint(entry_segments)` innerhalb derselben Ortsdatei stets `False` (beide Seiten `{loc.id}`) — genau das gewünschte Verhalten. Muss als eigene AC in die Spec (Pendant zu keiner der 22 Trip-ACs, da dort die Mehrfach-Segment-Semantik über `segment_ids` selbst läuft).

`compare_official_alert.py` hat zusätzlich eine Eigenheit gegenüber dem Trip-Vorbild: `tagged_alerts` sind `(alert, loc_ids)`-Paare — ein Alert kann MEHRERE Orte betreffen. Batch-Teilfilterung braucht dort ggf. mehrere Gate-Aufrufe pro Alert (einen je betroffenem Ort), nicht einen Aufruf mit Orts-Liste wie beim Trip (`segment_ids`-Iterable).

## Risks & Considerations

- **Blast Radius:** Live-Zustellpfad für alle Ortsvergleichs-Nutzer (Multi-Tenant) — Mandantentrennung (AC-18-Äquivalent) ist Pflichtprüfung.
- **Fail-soft-Richtung ist sicherheitskritisch**: ein Fehler darf NIE dazu führen, dass ein Alarm fälschlich unterdrückt wird — nur zu viel senden ist die tolerierte Fehlerrichtung.
- **Kein neues Spec-Dokument existiert** — eigene Spec nötig, ACs gespiegelt aus der 22-AC-Vorlage (S4b-1), reduziert auf die im Issue als "besonders zu spiegeln" genannten (Kernfall, Eskalation, Fail-soft, Registrierung-nach-Erfolg, Wiring, Batch-Teilfilterung).
- **Testvorlagen vorhanden**: `tests/tdd/test_alert_gate.py` (Baustein), `tests/tdd/test_issue_1088_official_alert_triggers.py::TestS4bEventIdentityWiring` (Wiring/Order-Spion-Muster, WICHTIG: Patch auf Aufrufer-Modul-Namespace wegen benanntem Import), `tests/tdd/test_alert_state_briefing_reset.py` (Reset-Regression). Bestehende Compare-Testdateien als Namensvorbild: `test_compare_official_alert.py`, `test_compare_radar_alert.py` u. a. in `tests/tdd/`.

## Analysis

### Type
Feature (Verdrahtung eines bestehenden, unveränderten Bausteins auf zwei neue Aufrufstellen — keine neue Kernlogik).

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/compare_radar_alert.py` | MODIFY | Gate-Aufruf pro getriggertem Ort vor `send_multi_location_radar_alert`, Teilfilterung der Zielliste, `record_event_identity` je erfolgreich zugestelltem Ort nach dem Versand |
| `src/services/compare_official_alert.py` | MODIFY | Gate-Aufruf pro `(alert, loc_id)`-Kombination (ein Alert kann mehrere Orte betreffen) vor `send_multi_location_official_alert`, Teilfilterung, `record_event_identity` je erfolgreich zugestelltem `(alert, loc)`-Paar nach dem Versand |
| `tests/tdd/test_compare_radar_alert_event_identity.py` | CREATE | Wiring + Kernfall + Fail-soft + Mandantentrennung + Batch-Teilfilterung, gespiegelt aus `test_issue_1088_official_alert_triggers.py::TestS4bEventIdentityWiring` und `test_alert_gate.py` |
| `tests/tdd/test_compare_official_alert_event_identity.py` | CREATE | Dasselbe für den amtlichen Pfad, inkl. Mehrfach-Ort-pro-Alert-Fall |
| `tests/tdd/test_alert_state_briefing_reset.py` | MODIFY | Regressionstest: Reset erfasst `event_identity:`-Präfix auch für Compare-Entitäten (Pendant AC-14) |
| `docs/specs/modules/rework_1917_s4b2_compare_entdopplung.md` | CREATE | Eigene Spec, ACs aus der 22-AC-Vorlage (S4b-1) reduziert/angepasst, plus die neue `segment_ids=[loc.id]`-AC |
| `docs/adr/0021-shared-deviation-alert-engine.md` | MODIFY (klein) | Datierter Nachtrag, analog AC-21 aus S4b-1 |

### Scope Assessment
- Files: 7 (2 Produktivdateien, 3 Testdateien, 1 Spec, 1 ADR-Nachtrag)
- Estimated LoC: +120/-10 (Produktivcode ~40-60 Zeilen netto in beiden Services zusammen; Tests größter Anteil)
- Risk Level: MEDIUM — Live-Zustellpfad für alle Ortsvergleichs-Nutzer, aber fail-soft-Konstruktion begrenzt den Schaden einer Fehlfunktion auf "zu viel senden", nie "zu wenig"

### Technical Approach
1. `compare_radar_alert.py`: Nach `_detect_triggered_locations()`, vor dem gebündelten Versand — pro getriggertem Ort `check_event_identity_gate(entity_id=f"{preset_id}:{loc.id}", hazard_class="wet", segment_ids=[loc.id], ...)`. Nicht-zugelassene Orte aus der Zielliste filtern (Protokolleintrag wie Trip-Vorbild), nur die verbleibende Teilmenge zustellen. Nach Versand: `record_event_identity(..., segment_ids=[loc.id])` je erfolgreich zugestelltem Ort.
2. `compare_official_alert.py`: Analog, aber pro `(alert, loc_id)`-Paar, da `tagged_alerts` bereits `(alert, loc_ids)`-Listen sind — ein Alert kann mehrere Orte betreffen, jeder Ort wird einzeln geprüft. `_official_urgency`-Neuberechnung NACH dem Filtern (Reihenfolge-Fehler aus Trip-Vorbild vermeiden, dort Z. 1749-1752 als Lehre dokumentiert).
3. `segment_ids=[loc.id]` an BEIDEN Aufrufstellen (Check und Record) — siehe Design-Entscheidung oben, sonst No-Op-Bug.
4. `hazard_class`-Bestimmung: vermutlich vorhandene `resolve_hazard_class()`-Hilfsfunktion wiederverwenden (im Trip-Pfad genutzt) — in der Spec-Phase exakte Fundstelle klären.

### Dependencies
- Upstream: `alert_gate.py` bleibt unverändert (kein Signatur-Change nötig).
- Downstream: keine bekannten Konsumenten außer dem Scheduler — keine Breaking Changes an öffentlichen Schnittstellen.

### Open Questions
- [ ] Exakte Fundstelle/Name der `hazard_class`-Auflösung für Compare-Alerts (Trip nutzt vermutlich `resolve_hazard_class` — muss in Spec-Phase verifiziert werden, ob Compare dieselbe Funktion nutzen kann oder eine eigene Ableitung braucht).
- [ ] Muss `record_event_identity` bei `compare_official_alert.py` pro `(alert, loc)`-Paar EINZELN aufgerufen werden, oder gibt es eine Batch-Variante? (Trip-Vorbild ruft in einer Schleife auf — vermutlich identisch für Compare.)
