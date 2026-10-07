---
entity_id: fix_2441_etappennummer_status
type: bugfix
created: 2026-10-07
updated: 2026-10-07
status: draft
workflow: fix-2441-etappennummer-status
version: "1.0"
tags: [kanal-paritaet, etappennummer, status, epic-2506]
---

# Fix #2441: STATUS und Verschiebe-Bestätigung nennen dieselbe Etappennummer wie das Briefing

## Approval

- [ ] Approved

## Purpose

Der Befehl `status` gibt für jede Etappe den rohen Namen aus, den der Autor vergeben hat
(z.B. „02: Obstansersee-Hütte nach Porzehütte"), während `heute`, Briefing und Vorschau die
gezählte chronologische Nummer nennen („Etappe 4" bzw. „E4"). Dieselbe Etappe trägt damit je
nach Befehl zwei verschiedene Zahlen. Dieser Fix stellt die gezählte Nummer (Spec #760) als
einzige Wahrheit durch: Ein vom Autor im Namen vergebenes Zahlenpräfix wird wie „Etappe N"
ersetzt, nicht addiert, und `status` sowie die Bestätigungen der STARTDATUM-Verschiebung nutzen
dieselbe Bezeichnung auf allen vier Kanälen (Epic #2506, Refs #2417 AC-27).

## Source

- **File:** `src/app/trip.py`
- **Identifier:** `_STAGE_PREFIX_RE` (Z.33-36), `Trip.numbered_stage_label` (Z.294-309)
- **File:** `src/services/trip_command_processor.py`
- **Identifier:** `TripCommandProcessor._show_status` (Z.2542, Ausgabezeile Z.2562), StageShift-Bau
  (Z.2402, Z.2519) und -Ausgabe (Z.2450, Z.2533)
- **File:** `src/output/renderers/sms_trip.py`
- **Identifier:** `_sms_stage_prefix` (Z.50-55) — bleibt UNVERÄNDERT

> Schicht: Python-Core (`src/app/`, `src/services/`). Keine Go-/Frontend-Änderung.

## Estimated Scope

- **LoC:** ca. +35 / -6 Produktivcode, ca. 150 Tests
- **Files:** 2 MODIFY (Produktiv) + 1 CREATE (Testdatei)
- **Effort:** low-medium (Risiko MEDIUM: `numbered_stage_label` ist eine geteilte Funktion)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/specs/modules/issue_760_stage_number.md` | spec | Nummer = 1-basierte chronologische Position (`sorted(stages, key=date)`), „zwingend" |
| `docs/specs/modules/fix_2122_etappen_praefix_kurzform.md` | spec | Alarm-Kurzform `S{N}` mit derselben Zählung; darf sich nicht ändern |
| `docs/specs/modules/feat_2417_kurzform_englisch.md` | spec | EN-Ausgabe von STATUS über `self._en`, GSM-7-Strich |
| `src/services/trip_report_scheduler.py` (Z.1547), `src/services/preview_service.py` (Z.203) | module | Briefing/Vorschau rufen `numbered_stage_label` — Regressionsfläche |
| `src/services/notification_service.py` (Z.404) | module | Alarm-Etappennummer, gleiche Zählung — Regressionsfläche |
| `tests/tdd/_befehl_e2e_fixtures.py` | test | Befehle durch den echten Eingang (Memory #2417) |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/app/trip.py` | MODIFY | `_STAGE_PREFIX_RE` um ein eng gefasstes Zahlenpräfix erweitern |
| `src/services/trip_command_processor.py` | MODIFY | `_show_status` und beide StageShift-Ausgaben nutzen `trip.numbered_stage_label(stage)` statt `stage.name` |
| `tests/tdd/test_etappennummer_status_paritaet.py` | CREATE | Wächter für alle ACs (vom /40-Schritt erstellt) |

`src/output/renderers/sms_trip.py::_sms_stage_prefix` bleibt unverändert: Es liest aus dem bereits
normalisierten Label „Etappe N: …" dieselbe Zahl.

## Implementation Details

```
Muster (Erweiterung von _STAGE_PREFIX_RE, zusätzliche Alternative):

  ^\s*\d{1,2}\s*[:\-–—]\s+       (Leerraum nach dem Trennzeichen ist PFLICHT)
  ODER ... \d{1,2}\s*[:\-–—]\s*$    (nur Präfix, leerer Rest)

  trifft:        "02: X"   "02 – X"   "2 - X"   "03:" (leerer Rest)
  trifft NICHT:  "2 Seen Runde"   "1.5 km Runde"   "1. Pass"   "2. X"   "02:X" (kein Leerraum nach
                 dem Trennzeichen -> bleibt unverändert)
  Bestand:       "Etappe N"/"Tag N" verhält sich wie bisher (erste Alternative)

Anzeige (kein Schreibzugriff, keine Persistenz):

  Label = trip.numbered_stage_label(stage)  ->  "Etappe {N}: {Rest}"  oder "Etappe {N}"
  N = Position in sorted(trip.stages, key=date) + 1  (unverändert)

  _show_status:  f"  {datum} {strich} {trip.numbered_stage_label(stage)}"
                 strich bleibt "-" bei self._en, sonst "–" (GSM-7)
  StageShift:    Ausgabe nutzt das Label, das beim Bau (Z.2402/Z.2519) ermittelt wird;
                 stage.name in den Daten bleibt unverändert.
```

Entscheidung „1. Pass" (PO 07.10.: ohne Punkt): Der Punkt ist KEIN Trenner. „1. Pass" und „2. X"
bleiben unverändert („Etappe N: 1. Pass"), weil sie von einem gewöhnlichen Namen nicht zu
unterscheiden sind und die Regel in einer geteilten Funktion (Briefing, Vorschau, Alarm) sitzt.
„1.5 km Runde" und „2 Seen Runde" bleiben ebenfalls unverändert. Die Zahl im Namen wird nie als Etappennummer
übernommen; maßgeblich ist immer die gezählte Position.

## Expected Behavior

- **Input:** Befehl `status` (oder `heute`, oder eine STARTDATUM-Verschiebung) auf einem Trip, dessen
  Etappennamen teils ein vom Autor vergebenes Zahlenpräfix tragen.
- **Output:** Jede Etappe erscheint als „Etappe N: Rest" mit der gezählten Nummer; dieselbe Zahl wie
  in `heute` (`E{N}`), Briefing, Vorschau und Alarm (`S{N}`).
- **Side effects:** Keine. Keine Persistenzänderung, Zählung unverändert.

## Acceptance Criteria

- **AC-1:** Given ein Trip, dessen vierte Etappe „02: Obstansersee-Hütte nach Porzehütte" heißt, und
  deren Datum heute ist / When der Nutzer über den echten Befehlseingang `status` und danach
  `heute` sendet / Then nennen beide Antworten für diese Etappe dieselbe Zahl (4), `status` als
  „Etappe 4: …" und `heute` als „E4".
  - Test: Beide Befehle durch den echten Eingang (`_befehl_e2e_fixtures`), die Zahl aus beiden
    Antworten extrahieren und vergleichen; die erwartete 4 wird aus der Trip-Position abgeleitet,
    nicht als Literal im Aufbau gesetzt.

- **AC-2:** Given Etappennamen „02: X" und „02 – X" an Position 4 / When `status` den Trip
  auflistet / Then steht dort „Etappe 4: X" und die im Namen vergebene Zahl erscheint nicht
  zusätzlich (keine Form „Etappe 4: 02: X").
  - Test: Drei Trips bzw. drei Etappen, Ausgabezeile exakt vergleichen; Gegenprobe, dass „02" nicht
    in der Zeile vorkommt.

- **AC-3:** Given die Etappennamen „2 Seen Runde", „1.5 km Runde", „1. Pass", „2. X" und „03:" / When `status`
  sie auflistet / Then bleibt „2 Seen Runde" als „Etappe N: 2 Seen Runde" und „1.5 km Runde" als
  „Etappe N: 1.5 km Runde" erhalten, „1. Pass" und „2. X" als „Etappe N: 1. Pass" bzw. „Etappe N: 2. X" (Punkt ist kein Trenner), und der leere Rest „03:"
  wird zu „Etappe N" ohne Doppelpunkt.
  - Test: Parametrisierter Test über die vier Namen mit exakter Erwartung je Zeile.

- **AC-4:** Given ein Trip mit Zahlenpräfix-Namen und eine STARTDATUM-Verschiebung / When der Nutzer
  die Verschiebung über den echten Befehlseingang ausführt (Vorschau und Bestätigung) / Then nennen
  beide Bestätigungen je Etappe „Etappe N: Rest" mit derselben Nummer wie `status`, mit
  unverändertem Datumsteil.
  - Test: Beide StageShift-Ausgaben (Z.2450, Z.2533) gegen die `status`-Nummern der Etappen prüfen.

- **AC-5:** Given Trips mit Namen ohne Präfix, mit „Etappe N"-Präfix und mit „Tag N"-Präfix / When
  Briefing-Mail, Vorschau und Alarm-Kurzform erzeugt werden / Then bleiben deren Bezeichnungen und
  Nummern byte-identisch zum Bestand (insbesondere Alarm-`S{N}` und Briefing „Etappe N: Rest").
  - Test: Bestehende Tests `test_issue_760_stage_number.py`, `test_issue_762_stage_suffix.py`,
    `test_alert_etappen_praefix_kurzform.py`, `test_preview_render_options_parity.py` bleiben grün;
    zusätzlich eingefrorener Vergleichstext für einen Namen ohne Präfix.

- **AC-6:** Given der Nutzer schreibt auf einem Kurzform-Kanal (EN-Ausgabe, `self._en`) / When er
  `status` sendet / Then trägt die Antwort „Etappe N: Rest" bzw. die EN-Form von #2417, den
  ASCII-Strich „-" statt „–", und enthält ausschließlich GSM-7-Zeichen; auf der E-Mail-Langform
  bleibt der Strich „–".
  - Test: Antwort auf SMS-Kanal gegen den GSM-7-Zeichensatz prüfen (Muster `test_trip_sms_gsm7_charset.py`),
    E-Mail-Antwort auf „–" prüfen.

- **AC-7:** Given derselbe Trip und dieselbe Etappe / When `status` über E-Mail, Telegram, SMS und
  Premium-SMS gesendet wird / Then nennen alle vier Antworten für die Etappe dieselbe Zahl und
  denselben Rest.
  - Test: Vier Kanal-Eingänge nacheinander, extrahierte Zahl und Rest paarweise vergleichen.

- **AC-8:** Given Etappen mit Zahlenpräfix-Namen / When `status` oder eine Verschiebung ausgeführt wurde
  / Then sind die gespeicherten Etappennamen im Datenbestand danach unverändert (Anzeige-Normalisierung,
  keine Persistenz).
  - Test: Trip vor und nach den Befehlen laden und `stage.name` je Etappe byte-identisch vergleichen.

- **AC-9:** Given ein Trip mit Etappen in nicht chronologischer Listenreihenfolge / When `status`
  aufgelistet wird / Then entspricht die genannte Nummer weiterhin der chronologischen Position nach
  Datum (Zählung unverändert), nicht der Listenposition und nicht der im Namen stehenden Zahl.
  - Test: Etappenliste mit vertauschter Reihenfolge und irreführenden Namenszahlen, Nummern gegen
    `sorted(stages, key=date)` prüfen.

- **AC-10:** Given die fertige Implementierung / When in `_show_status` `numbered_stage_label(stage)`
  durch `stage.name` ersetzt wird (Mutations-Gegenprobe, Sicherungskopie extern) / Then wird
  mindestens der Test zu AC-1 über den echten Befehlseingang rot.
  - Test: Mutation per String-Ersetzung, protokolliert wird, welcher Test anschlägt.

## Test Plan

Testdatei: `tests/tdd/test_etappennummer_status_paritaet.py` (neu, vom /40-Schritt erstellt).
Befehle laufen durch den echten Eingang (`tests/tdd/_befehl_e2e_fixtures.py`), keine Mocks.

| AC | Testgegenstand |
|----|----------------|
| AC-1, AC-7 | `status` vs. `heute`, vier Kanäle, gleiche Zahl |
| AC-2, AC-3, AC-9 | Präfix-Muster, Randfälle, chronologische Zählung |
| AC-4, AC-8 | StageShift-Bestätigungen, Namen im Bestand unverändert |
| AC-5 | Regression über bestehende Tests (#760, #762, Alarm S{N}, Vorschau-Parität) |
| AC-6 | EN-Ausgabe, GSM-7-Zeichensatz, „–" vs. „-" |
| AC-10 | Mutations-Gegenprobe (Adversary-Schritt) |

## Known Limitations

- Ein Name, der mit „Zahl + Doppelpunkt/Strich + Leerraum" beginnt, wird immer als vergebenes
  Etappenpräfix gelesen. Der Punkt als Trenner („2. X") wird bewusst NICHT erkannt (PO 07.10.):
  ein so geschriebenes Autorpräfix erscheint weiter doppelt („Etappe 4: 2. X"); bei Bedarf später
  mit eigenem Test nachziehen.
- Zahlen mit mehr als zwei Stellen am Namensanfang werden nicht als Präfix gelesen.
- Der Etappenname in den Daten wird nicht bereinigt; ein Autor sieht die Rohform weiterhin im Editor.
- Drei Schreibweisen derselben Nummer (`Etappe N`, `E{N}`, `S{N}`) bleiben bestehen; angeglichen wird
  nur die Zahl, nicht die Schreibweise.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Bestätigung von Spec #760 (gezählte Nummer ist maßgeblich); keine neue
  Entscheidungsfläche, keine Datenmodell-Änderung. Die Erweiterung ist rein anzeigeseitig.

## Changelog

- 2026-10-07: Initial spec created (#2441, Epic #2506)
