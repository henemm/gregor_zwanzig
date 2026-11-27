---
entity_id: fix_3470_amtlich_nachbarperioden
type: bugfix
created: 2026-11-27
updated: 2026-11-27
status: draft
version: "1.0"
workflow: fix-3470-amtlich-pingpong
issue: 3470
tags: [alert, official-alert, meteoalarm, revision, dedup]
---

# Fix #3470: Amtliche Warnung mit zwei Nachbarperioden wird nicht mehrfach gemeldet

## Approval

- [ ] Approved

## Purpose

Liefert der amtliche Feed (Meteoalarm) dieselbe Warnung als zwei gleichzeitig gueltige, aneinandergrenzende Perioden (A = 12-16 Uhr, B = 16-12 Uhr Folgetag), meldete Gregor sie im Wechsel immer wieder neu (Prod 27.11.2026: 7 Mails zu einer Kaeltewarnung). Dieser Fix sorgt dafuer, dass der Nutzer je Warnung genau eine Meldung bekommt und genau eine Entwarnung, ohne die PO-Entscheidungen #1657 und #1685 zu aendern.

## Source

- **File:** `src/output/renderers/alert/official_alerts.py`
- **Identifier:** `official_alert_revision_verdict` (Revisions-Entscheid), `build_official_allclear_notices` (Entwarnungs-Entdopplung)
- Aufrufer (geteilter Baustein): `src/services/trip_alert.py` (`check_official_alert_triggers`), `src/services/compare_official_alert.py` (`_detect`)

Schicht: Python-Core (`src/output/`, `src/services/`). Kein Frontend, keine Go-API.

**Querschnitts-Pruefpunkte:**
- **Trip/Ortsvergleich-Teilung:** Der Entscheid liegt in EINEM geteilten Baustein; beide Aufrufer reichen nur die Feed-Schluessel durch (Trip: gesamte Feed-Menge, Vergleich: je Ort). Keine einseitige Neuanlage.
- **Mandantentrennung:** Gedaechtnis liegt je Nutzer (`AlertStateService(user_id=...)`); Test mit zwei verschiedenen Nutzern (AC-9).
- **Kanaele:** Der Melde-Entscheid ist vor der Kanalwahl; E-Mail, Telegram, SMS und Premium-SMS bekommen dieselbe Entscheidung (eine Meldung je Warnung, eine Entwarnung je Warnung).

## Estimated Scope

- **LoC:** ca. +50 Produktivcode, ca. +150 Test
- **Files:** 3 Quelldateien, 1 Testdatei, 1 Spec
- **Effort:** low-medium

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/alert/official_alerts.py` | MODIFY | Exakter Schluesseltreffer zuerst, Parameter `feed_keys`, `stale_key=None`-Vertrag, Randberuehrungs-Unterdrueckung der Vorverlegung, Entwarnungs-Entdopplung |
| `src/services/trip_alert.py` | MODIFY | `feed_keys` aus den aktuellen Feed-Warnungen uebergeben; Gedaechtnis-Eintrag nur loeschen, wenn `stale_key` gesetzt |
| `src/services/compare_official_alert.py` | MODIFY | `feed_keys` je Ort uebergeben; Eintrag nur loeschen, wenn `stale_key` gesetzt |
| `tests/tdd/test_fix_3470_amtlich_nachbarperioden.py` | CREATE | Mehrlauf-Simulation, Trip und Vergleich, beide Feed-Reihenfolgen, Entwarnung |
| `docs/specs/modules/fix_3470_amtlich_nachbarperioden.md` | CREATE | Diese Spec |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `official_alert_state_key`, `_identity_hazard_prefix`, `official_alert_state_entry` | function | Schluessel und Eintrag der Warnung im Gedaechtnis |
| `AlertStateService` / `prune_expired_official` (`src/services/alert_state.py`) | module | Dateigedaechtnis je Nutzer, Aufraeumen nach `valid_to` |
| `detect_official_allclear` (`src/services/official_alert_allclear.py`) | module | Entwarnung; Nachbar im Feed haelt Eintrag "present" |
| `docs/specs/modules/fix_1685_warnfenster_revision.md` | spec | Stille Revision bei Neuausgabe (PO 2026-08-10), bleibt gueltig |
| `docs/specs/modules/fix_1657_warnfenster_identitaet.md` | spec | Beruehrung = Ueberlappung, Containment, 6h-Frische (PO 2026-08-17), bleibt gueltig |
| `docs/specs/modules/rework_1467_s4b_entdopplung.md` | spec | Bestehende Entdopplung, Nachbarbaustein |
| `tests/helpers/official_alert_gate_fixtures.py` | test helper | Feed-Fixtures fuer amtliche Warnungen |

## Implementation Details

Wurzelursache: Der Revisions-Entscheid sucht auch dann einen Kandidaten, wenn der eigene Schluessel exakt im Gedaechtnis steht. Die Aufrufer loeschen den gewaehlten Kandidaten. Bei zwei gleichzeitig gueltigen Nachbarperioden loescht B das gemeldete A; A (weiter im Feed) wird gegen B als "Vorverlegung ab 2 Stunden" neu gemeldet und nach Zustellung wieder eingetragen; im naechsten Lauf beginnt es von vorn.

Technischer Ansatz:

1. **Exakter Treffer zuerst:** Steht der eigene Schluessel im Gedaechtnis, entscheidet nur die Eskalation (hoehere Stufe) ueber eine Meldung. Keine Kandidatensuche, Eintrag bleibt unveraendert.
2. **`feed_keys`** (optional, `frozenset[str] | None`, Standard `None` = altes Verhalten): Ist der gewaehlte Kandidat selbst noch im Feed, wird er nicht verbraucht. Rueckgabe `(False, None, merged_entry)`; der Aufrufer legt nur den neuen Eintrag still daneben ab und loescht nur, wenn `stale_key` gesetzt ist.
3. **Randberuehrung:** Eine Vorverlegung wird unterdrueckt, wenn der Kandidat im Feed steht und nur an der Kante beruehrt (Ende des einen = Beginn des anderen). Echte Innenueberlappung und Kandidaten, die nicht mehr im Feed stehen, laufen wie bisher. Das verhindert den letzten Doppel-Alarm nach dem Deploy bei Bestandsgedaechtnis.
4. **Eskalation** meldet weiterhin immer, auch bei Nachbarperioden.
5. **Vergleich:** `feed_keys` wird je Ort gebildet, nie global.
6. **Entwarnung:** Im Notice-Builder werden Entwarnungen nach Identitaet und Gefahr (plus Ort/Quelle) entdoppelt (alte Stufe = Maximum, neue Stufe = Minimum). Die Senkung des Gedaechtnisses bleibt je Periode unveraendert.
7. **Fail-soft (F001):** Zeitvergleiche laufen im geschuetzten Block; bei fehlenden oder naiven Zeitangaben gilt das bisherige Verhalten, kein Absturz.

Verworfen: nur exakter Treffer (Ping-Pong bleibt bei Feed B,A), Verzicht auf Randberuehrungs-Regel (ein Doppel-Alarm nach Deploy), Vereinigungseintrag (aendert Schluesselmodell), Verzicht auf `feed_keys` (Flackern, schluckt echte Neuausgaben).

## Expected Behavior

- **Input:** Feed-Warnungen eines Laufs, Gedaechtnis des Nutzers (je Ort im Vergleich).
- **Output:** Melde-Entscheid je Warnung: genau eine Meldung bei Erstauftritt, Eskalation oder echter Vorverlegung; sonst still. Genau eine Entwarnung je Warnung.
- **Side effects:** Gedaechtnis behaelt beide Nachbarperioden, solange beide im Feed stehen; bei echter Neuausgabe wird die alte Periode wie in #1685/#1657 ersetzt.

## Test Plan

### Automated Tests (TDD RED)

Neue Datei `tests/tdd/test_fix_3470_amtlich_nachbarperioden.py`. Echtes Dateigedaechtnis (`AlertStateService` im tmp-Verzeichnis), Trip- und Vergleichs-Aufrufer real, kein Mock-Theater; Mehrlauf-Simulation mit Zustellung (Schreiben des Gedaechtnisses nach jedem Lauf).

- [ ] Test 1: GIVEN Feed A,B und Gedaechtnis {A} WHEN 4+ Laeufe in Reihenfolge A,B UND in Reihenfolge B,A THEN keine erneute Meldung nach der ersten; beide Perioden im Gedaechtnis.
- [ ] Test 2: GIVEN Bestandsgedaechtnis {B mit reported_at von A}, Feed A,B WHEN ein Lauf THEN keine Meldung.
- [ ] Test 3: GIVEN A gemeldet, A verschwindet aus dem Feed, B beruehrt/ueberlappt WHEN Lauf THEN stille Revision, A ersetzt (wie #1685/#1657).
- [ ] Test 4: GIVEN alte Periode, neue Periode mit Vorverlegung ab 2 h und Innenueberlappung, alte steht noch im Feed WHEN Lauf THEN Meldung.
- [ ] Test 5: GIVEN Nachbarperiode mit hoeherer Stufe WHEN Lauf THEN Meldung (Eskalation).
- [ ] Test 6: GIVEN exakter Schluesseltreffer WHEN Lauf THEN nur Eskalation meldet, Eintrag unveraendert.
- [ ] Test 7: GIVEN Ortsvergleich mit zwei Orten, Periode nur im Feed von Ort X WHEN Lauf THEN Eintrag von Ort Y wird nicht geschuetzt; Trip-Pfad verhaelt sich wie Vergleichspfad.
- [ ] Test 8: GIVEN beide Nachbarperioden im Gedaechtnis WHEN beide verschwinden (bzw. Herabstufung) THEN genau eine Entwarnung je Warnung.
- [ ] Test 9: GIVEN zwei verschiedene Nutzer mit derselben Warnung WHEN Laeufe THEN Gedaechtnis und Meldungen getrennt.
- [ ] Test 10: GIVEN fehlende Fensterangaben bzw. naive Zeitstempel WHEN Lauf THEN kein Absturz, Verhalten wie bisher.
- [ ] Bestandstests gruen: `tests/tdd/test_official_alert_revision_dedup.py`, `tests/tdd/test_official_alert_cooldown_entkopplung.py` (mit `feed_keys=None` altes Verhalten).

## Acceptance Criteria

- **AC-1:** Given der Feed enthaelt dieselbe Warnung als zwei gleichzeitig gueltige, aneinandergrenzende Perioden und im Gedaechtnis steht nur die zuerst gemeldete / When mindestens vier Laeufe nacheinander laufen, in beiden Feed-Reihenfolgen (A,B und B,A) / Then bekommt der Nutzer keine erneute Meldung zu dieser Warnung und beide Perioden bleiben im Gedaechtnis.
  - Test: Mehrlauf-Simulation mit echtem Dateigedaechtnis zaehlt zugestellte Meldungen je Reihenfolge (Trip-Pfad).

- **AC-2:** Given das Gedaechtnis stammt aus der Zeit vor dem Fix und enthaelt nur die Folgeperiode B mit dem Meldezeitpunkt von A / When der Feed A und B liefert / Then wird die Warnung nicht noch einmal gemeldet (kein letzter Doppel-Alarm nach dem Deploy).
  - Test: Lauf gegen praeparierten Bestandszustand, erwartet null Meldungen.

- **AC-3:** Given eine gemeldete Periode verschwindet aus dem Feed und eine neue Periode beruehrt oder ueberlappt sie (echte Neuausgabe) / When der naechste Lauf laeuft / Then bleibt es bei der stillen Revision, die alte Periode wird im Gedaechtnis durch die neue ersetzt und der Nutzer bekommt keine Meldung.
  - Test: Lauf mit Feed nur B, Gedaechtnis {A}; erwartet keine Meldung, Gedaechtnis {B}.

- **AC-4:** Given eine neue Periode beginnt mindestens zwei Stunden frueher als die gemeldete und ueberlappt sie im Inneren, auch wenn die alte Periode noch im Feed steht / When der Lauf laeuft / Then wird die Warnung als echte Vorverlegung gemeldet.
  - Test: Feed mit alter und vorverlegter Periode, erwartet genau eine Meldung.

- **AC-5:** Given die Nachbarperiode einer bereits gemeldeten Warnung hat eine hoehere Stufe / When der Lauf laeuft / Then wird die Eskalation gemeldet.
  - Test: Feed A (Stufe 2) und B (Stufe 3), Gedaechtnis {A}; erwartet eine Meldung mit Stufe 3.

- **AC-6:** Given der Schluessel der Warnung steht exakt im Gedaechtnis / When der Lauf laeuft / Then meldet nur eine Eskalation und der Gedaechtnis-Eintrag bleibt unveraendert, auch wenn eine Nachbarperiode im Feed steht.
  - Test: Lauf mit gleicher Stufe (keine Meldung, Eintrag byte-gleich) und mit hoeherer Stufe (Meldung).

- **AC-7:** Given dieselbe Konstellation tritt in einem Trip und in einem Ortsvergleich auf / When die Laeufe laufen / Then verhalten sich beide Pfade gleich, und im Ortsvergleich schuetzt eine Periode im Feed von Ort X nicht den Gedaechtnis-Eintrag von Ort Y.
  - Test: Gleiche Fixtures durch beide Aufrufer; Ortsvergleich mit zwei Orten, nur Ort X fuehrt die Periode im Feed.

- **AC-8:** Given beide Nachbarperioden einer Warnung stehen im Gedaechtnis / When sie beide aus dem Feed verschwinden (oder die Warnung herabgestuft wird) / Then bekommt der Nutzer genau eine Entwarnung je Warnung, nicht eine je Periode.
  - Test: Lauf mit leerem Feed bzw. niedrigerer Stufe; Anzahl Entwarnungen ist 1.

- **AC-9:** Given zwei verschiedene Nutzer haben dieselbe Warnung / When die Laeufe fuer beide laufen / Then bleiben Gedaechtnis und Meldungen je Nutzer getrennt und ein Nutzer beeinflusst die Meldungen des anderen nicht.
  - Test: Zwei `user_id`-Dateigedaechtnisse, Meldungen und Eintraege je Nutzer geprueft.

- **AC-10:** Given Fensterangaben fehlen oder Zeitstempel sind naiv (ohne Zeitzone) / When der Lauf laeuft / Then stuerzt nichts ab und es gilt das bisherige Verhalten (Fail-soft).
  - Test: Warnungen ohne `valid_from`/`valid_to` bzw. mit naiven Zeitstempeln; kein Fehler, Ergebnis wie vor dem Fix.

## Definition of Done

- AC-1 bis AC-10 durch `tests/tdd/test_fix_3470_amtlich_nachbarperioden.py` grün belegt; vorher rot nachgewiesen (Ping-Pong aus Nutzersicht reproduziert).
- Bestandstests `tests/tdd/test_official_alert_revision_dedup.py` und `tests/tdd/test_official_alert_cooldown_entkopplung.py` bleiben grün.
- Adversary-Verdict VERIFIED inkl. Mutations-Gegenprobe (Trip- und Vergleichspfad).
- PR mit allen CI-Checks grün gemergt, Staging-Nachweis und Prod-Selftest grün; Issue #3470 mit Ergebnis-Kommentar geschlossen.

## Known Limitations

- Erstauftritt mit leerem Gedaechtnis und beiden Perioden im selben Lauf liefert eine Meldung mit beiden Perioden (Ist-Verhalten, kein Ping-Pong).
- Ein totes Gedaechtnis-Eintrag, der beruehrt, aber nicht mehr im Feed steht, verfaellt ueber `prune_expired_official`.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Die PO-Entscheidungen #1657 (Beruehrung = dieselbe Gefahr) und #1685 (stille Revision bei Neuausgabe) bleiben unveraendert gueltig und werden nur konsequent auf den Fall "beide Perioden gleichzeitig im Feed" angewandt. Kein neues Entscheidungsfeld, daher kein neues ADR.

## Changelog

- 2026-11-27: Initial spec created (Issue #3470)
