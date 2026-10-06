---
entity_id: fix_2231_slot_reparatur
type: module
created: 2026-10-06
updated: 2026-10-06
status: draft
version: "1.0"
tags: [bug, versand-zuverlaessigkeit, briefing-slots, reparatur, epic-2505]
---

# Reparatur beschädigter Vermerk- und Versandprotokoll-Dateien (Issue #2231)

## Approval

- [ ] Approved

## Purpose

Eine beschädigte `briefing_slots.json` sperrt seit PR #2514 alle regulären Briefings
des betroffenen Nutzers auf Dauer, bis jemand die Datei von Hand repariert. Diese Spec
ersetzt die Dauersperre durch eine automatische, verlustfreie Reparatur: die kaputte
Datei wird beiseitegelegt, der Doppelversand-Schutz wird aus dem Versandprotokoll
(`briefing_log.json`) wiederhergestellt, und das Briefing läuft weiter.

## Abgelöste Festlegung

Diese Spec **ersetzt AC-5** von `docs/specs/modules/fail_closed_versand_defaults.md`
(„beschädigte `briefing_slots.json` ⇒ kein Versand, Datei bleibt byte-identisch“).
Begründung (PO-Entscheid 2026-10-06, „Reparatur nachliefern“): Die Dauersperre ist
für den Wanderer ein **stiller Totalausfall der Briefings** — Alarme laufen weiter,
das planmäßige Morgen- und Abend-Briefing bleibt stumm, und nur eine ERROR-Zeile im
Log verrät es. Ein Mensch müsste die Datei finden und löschen. Die Reparatur erhält
das Schutzziel der Sperre (kein Doppelversand, kein Datenverlust) und beendet den
Ausfall von selbst.

Unverändert gültig bleiben AC-1 bis AC-4 der main-Spec und deren Sinn von AC-6
(Mandantentrennung), hier als AC-8 neu gefasst. AC-5 der main-Spec gilt ab
Umsetzung dieser Spec nicht mehr; im Changelog der main-Spec ist darauf zu verweisen.

## Source

- **File:** `src/services/briefing_slots.py` · **Identifier:** `BriefingSlotStore` (`repair_if_corrupt`, `_load`, `_update`, `_log_bezeugt_versand`, `_log_traegt_versand`)
- **File:** `src/services/trip_report_scheduler.py` · **Identifier:** `TripReportSchedulerService._collect_due_trips`, `_append_briefing_log`

## Estimated Scope

- **LoC:** ~90 Produktivcode (briefing_slots ~65, trip_report_scheduler ~25) + Tests
- **Files:** 2 Produktivdateien, 3 Testdateien (1 angepasst, 2 neu)
- **Effort:** low (unter dem Limit von 250 LoC)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services.file_lock.acquire_exclusive` | Python | Sidecar-Sperre; Reparatur läuft unter derselben Sperre wie jeder Schreibvorgang |
| `briefing_log.json` | Datei | Versandprotokoll, Zeuge für den Doppelversand-Schutz nach der Reparatur |
| `BriefingSlotStore._log_traegt_versand` | Python | vorhandener Protokoll-Leser, wird um ERROR-Meldung bei beschädigtem Protokoll ergänzt |
| `docs/specs/modules/fail_closed_versand_defaults.md` | Spec | AC-5 wird hiermit abgelöst |

## Implementation Details

```
briefing_slots.py
  repair_if_corrupt(moment):
      unter Sidecar-Sperre; Datei fehlt oder lesbar => nichts tun, False
      unlesbar => os.rename(briefing_slots.json -> briefing_slots.json.corrupt-<UTC>)
                  (Kollision: -1, -2 ... anhaengen; NIE loeschen/ueberschreiben)
                  logger.error(Pfad, Beiseite-Pfad, Grund)
                  neue Datei {"entries": [], "rebuilt_from_log_at": moment.isoformat()}
      briefing_log.json unlesbar => ebenso beiseitelegen + ERROR (Protokoll startet neu)
  _update(): unlesbar => gleiche Reparatur statt "return False"
  Leser is_recorded / is_recorded_or_claimed: UNVERAENDERT (True, lock-frei, kein Rename)
  _log_bezeugt_versand(data): Ableitung nur wenn Datei fehlt ODER
      data["rebuilt_from_log_at"] gesetzt (PO 2026-08-11: gueltige Datei ohne Marker
      => altes Verhalten)
  _log_traegt_versand: unlesbares Protokoll => logger.error (statt stillem False)

trip_report_scheduler.py
  _collect_due_trips: store.repair_if_corrupt(moment=now_utc) VOR der Schleife
  _append_briefing_log: unlesbares Protokoll => beiseitelegen + ERROR + neu anlegen,
      statt Absturz nach dem Versand
```

Die Reparatur steht nur im Schreibpfad und im Scheduler-Einstieg, nie im lock-freien
Leser: zwei gleichzeitige Leser dürften sonst dieselbe Datei doppelt umbenennen.
Der Scheduler-Aufruf ist nötig, weil `is_recorded_or_claimed` bei beschädigter Datei
`True` liefert und der Trip sonst nie fällig würde — `reserve()` und damit die
Reparatur im Schreibpfad würden nie erreicht.

## Expected Behavior

- **Input:** beschädigte `briefing_slots.json` und/oder beschädigte `briefing_log.json`
- **Output:** Briefings laufen weiter; bereits versendete Slots des Tages gehen nicht erneut raus
- **Side effects:** Datei `*.corrupt-<UTC>` neben der Originalstelle (Beweismittel,
  unverändert), ERROR-Protokollzeile je beschädigter Datei, neue `briefing_slots.json`
  mit Marker `rebuilt_from_log_at`

## Acceptance Criteria

- **AC-1:** Given die `briefing_slots.json` eines Nutzers ist beschädigt (kein gültiges JSON, kein Objekt oder nicht lesbar) / When der Scheduler den nächsten Sammellauf macht / Then liegt die kaputte Datei unter `briefing_slots.json.corrupt-<UTC-Zeitstempel>` beiseite, es existiert eine neue gültige `briefing_slots.json` mit dem Marker `rebuilt_from_log_at`, und ein heute noch nicht versendetes Briefing wird im selben Lauf normal reserviert und versendet.
  - Test: echter `BriefingSlotStore` in `tmp_path` mit Inhalt `{"entries": [`, `[]`, `"text"` und mit einem Verzeichnis statt Datei; nach `repair_if_corrupt` existieren `.corrupt-*` und neue Datei mit Marker; `reserve(...)` für einen unversendeten Slot ist `True`.

- **AC-2:** Given die `briefing_slots.json` war beschädigt und `briefing_log.json` belegt, dass das Morgen-Briefing eines Trips heute schon rausging / When der Scheduler danach den Morgen-Slot dieses Trips prüft / Then geht das Morgen-Briefing nicht noch einmal raus, während der Abend-Slot desselben Trips und das Morgen-Briefing eines anderen Trips normal laufen.
  - Test: Protokoll mit Eintrag `trip=t1, kind=morning, sent_at=heute` (nicht `on_demand`) und kaputte Slot-Datei; nach Reparatur `is_recorded(t1, morning)` = True und `reserve(t1, morning)` = False; `reserve(t1, evening)` und `reserve(t2, morning)` = True; ein Protokolleintrag mit `on_demand: true` oder von gestern zählt nicht.

- **AC-3:** Given eine beschädigte `briefing_slots.json` wird repariert / When man die beiseitegelegte Datei mit dem Zustand vor der Reparatur vergleicht / Then ist sie byte-identisch, wurde also weder gelöscht noch verändert; tritt der Defekt später erneut auf, entsteht eine zweite `.corrupt-`-Datei und die erste bleibt unberührt.
  - Test: Bytes vor der Reparatur merken, nach der Reparatur `.corrupt-*`-Datei lesen und vergleichen; Defekt erneut erzeugen und gleichen Zeitstempel erzwingen (Uhr angehalten) ⇒ zwei verschiedene `.corrupt-*`-Dateien, erste unverändert.

- **AC-4:** Given eine gültige `briefing_slots.json` ohne Marker und ein Versandprotokoll, das für den Slot einen Versand heute zeigt / When der Scheduler den Slot prüft / Then gilt allein der Vermerk der Slot-Datei — die Ableitung aus dem Protokoll findet nicht statt (PO-Regel 2026-08-11), die Datei wird nicht umbenannt und nicht verändert.
  - Test: gültige Datei mit leerer Eintragsliste ohne Marker + Protokolleintrag heute ⇒ `is_recorded` = False, `reserve` = True; keine `.corrupt-*`-Datei, `repair_if_corrupt` liefert False. Gegenprobe: Datei fehlt ⇒ Ableitung greift weiter.

- **AC-5:** Given die `briefing_slots.json` ist beschädigt / When ein Leser ohne Sperre (`is_recorded`, `is_recorded_or_claimed`) fragt / Then antwortet er weiterhin „abgeschlossen“ (True), ohne die Datei umzubenennen oder zu verändern — repariert wird nur im Scheduler-Einstieg und im Schreibpfad unter der Sperre. Ein Alarm wird dadurch nicht für ein Briefing zurückgehalten, das nie kommt.
  - Test: beschädigte Datei, beide Leser = True, Dateiinhalt vorher == nachher, kein `.corrupt-*`; erst `repair_if_corrupt` erzeugt die Umbenennung.

- **AC-6:** Given die `briefing_log.json` eines Nutzers ist beschädigt / When nach einem Versand der Protokolleintrag geschrieben werden soll oder eine Reparatur der Slot-Datei das Protokoll als Zeugen braucht / Then stürzt der Versandlauf nicht ab: das kaputte Protokoll liegt als `briefing_log.json.corrupt-<UTC-Zeitstempel>` unverändert beiseite, ein neues Protokoll mit dem aktuellen Eintrag entsteht, und eine ERROR-Zeile nennt die Datei.
  - Test: `_append_briefing_log` mit beschädigtem Protokoll ⇒ keine Exception, neue Datei enthält genau den neuen Eintrag, `.corrupt-*` byte-identisch zum Original; ERROR im Log.

- **AC-7:** Given eine der beiden Dateien wird beschädigt vorgefunden / When die Reparatur läuft / Then steht je beschädigter Datei eine ERROR-Protokollzeile mit Dateipfad, Ziel der Beiseitelegung und Fehlergrund — die Reparatur ist also nie lautlos.
  - Test: `caplog` auf Logger `briefing_slots` und Scheduler-Logger; je Defekt genau eine ERROR-Zeile, die den ursprünglichen Dateinamen und den `.corrupt-`-Namen enthält.

- **AC-8:** Given zwei Nutzer, bei Nutzer A ist `briefing_slots.json` beschädigt, bei Nutzer B intakt / When für beide ein Slot fällig ist / Then wird nur A repariert (nur A bekommt `.corrupt-*` und Marker); B reserviert und versendet normal und seine Dateien bleiben unberührt.
  - Test: zwei `BriefingSlotStore`-Instanzen mit getrennten Verzeichnissen; Reparatur bei A, `reserve` bei A = True, bei B = True; B-Dateien byte-identisch, kein `.corrupt-*` in B.

- **AC-9:** Given ein verwaister Claim (Versand begonnen, Ausgang nie vermerkt) liegt vor und die `briefing_log.json` ist beschädigt / When der Scheduler den Claim übernehmen will / Then übernimmt er ihn nicht (kein Doppelversand ohne Protokollbeleg), schreibt eine ERROR-Zeile, und am nächsten Ortstag reserviert der Slot wieder regulär.
  - Test: verwaister Claim plus kaputtes Protokoll ⇒ `reserve` = False, Versandzahl 0, ERROR in `caplog`; am Folgetag `reserve` = True. Vorlage: alter Branch `worktree-spicy-shimmying-lake`, `tests/tdd/test_briefing_log_beschaedigt.py` (dort AC-15).

## Test Plan

Automatisierte Tests mit echtem `BriefingSlotStore` in `tmp_path`, ohne Mocks:

- GIVEN beschädigte Slot-Datei WHEN `repair_if_corrupt` THEN `.corrupt-*` beiseite, Marker gesetzt (AC-1, AC-3)
- GIVEN Protokoll bezeugt Versand WHEN Reparatur und `reserve` THEN False (AC-2)
- GIVEN gültige Datei ohne Marker WHEN Protokoll Versand zeigt THEN keine Ableitung (AC-4)
- GIVEN beschädigtes Protokoll WHEN `_append_briefing_log` THEN kein Absturz, Beiseitelegung (AC-6)
- GIVEN zwei Nutzer WHEN A beschädigt THEN B unberührt (AC-8)

**Bestehender Test `tests/test_briefing_slot_fail_closed.py`:**

- **Entfallen** (widersprechen dem neuen Verhalten, werden gelöscht/ersetzt):
  `test_corrupt_file_locks_slot_and_stays_byte_identical` (Erwartung `reserve` = False und
  Datei byte-identisch am Originalort) und `test_corrupt_file_unreadable_oserror_locks_slot`
  (Erwartung `reserve` = False beim Verzeichnis-Fall) und der `reserve is False`-Teil von
  `test_corruption_of_user_a_does_not_lock_user_b`. Ersetzt durch AC-1/AC-3 in
  `tests/test_briefing_slot_reparatur.py`.
- **Bleiben erhalten:** die lock-freien Leser liefern bei beschädigter Datei `True`, ohne
  Umbenennen (Teil von `test_corrupt_file_locks_slot_and_stays_byte_identical`, abgetrennt
  als eigener Test, AC-5); `test_missing_file_still_reserves`; die Mandantentrennung
  (Nutzer B reserviert normal), jetzt als AC-8 mit Reparatur bei A.
- Datei-Docstring auf diese Spec umstellen.

Neue Dateien: `tests/test_briefing_slot_reparatur.py` (AC-1..AC-5, AC-7, AC-8),
`tests/test_briefing_log_beschaedigt.py` (AC-6, AC-7 für das Protokoll).

## Known Limitations

- Sind **beide** Dateien beschädigt, fehlt der Protokoll-Zeuge: im selben Nachholfenster
  (3 Stunden) kann ein bereits versendetes Briefing einmal erneut rausgehen. Bewusst
  gegen den Dauerausfall abgewogen; ein Doppelbriefing ist ein Ärgernis, ein stummer
  Ausfall gefährdet die Trip-Planung.
- Ist nur das Protokoll beschädigt und die Slot-Datei gültig, bleibt die Slot-Datei der
  Zeuge; einen verwaisten Claim übernimmt der Scheduler in diesem Fall bewusst nicht (AC-9),
  das Briefing dieses einen Slots entfällt dann für diesen Ortstag.
- Die Beiseitegelegten `.corrupt-*`-Dateien werden nicht automatisch aufgeräumt; eine
  Retention wäre ein eigenes Folgeticket. Sichtbar ist die Reparatur nur über die ERROR-Zeile.
- Ein beschädigter Zustand, der zwischen Fälligkeitsprüfung und `reserve` entsteht,
  wird vom Schreibpfad repariert; der Leser liefert bis dahin `True`.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Keine neue Grundsatzentscheidung — Fehlerrichtung „kein Doppelversand,
  keine Datenverluste“ bleibt; lediglich ein Verfahren statt der Dauersperre. Ablösung
  von AC-5 der main-Spec ist hier dokumentiert.

## Changelog

- 2026-10-06: Initial spec created (Issue #2231, PO-Entscheid „Reparatur nachliefern“); ersetzt AC-5 von `fail_closed_versand_defaults`
