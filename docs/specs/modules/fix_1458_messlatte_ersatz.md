---
entity_id: fix_1458_messlatte_ersatz
type: refactor
created: 2026-08-18
updated: 2026-08-18
status: approved
version: "1.0"
tags: [alerts, epic-1458, doku, issue-triage]
---

# Messlatte des Epics #1458 ersetzen und Epic schließen

## Approval

- [x] Approved — PO (Henning), 2026-08-18

## Purpose

Epic #1458 („Alerts neu ordnen") hat alle fünf Scheiben geliefert. Sein einziges noch
offenes Erledigt-Kriterium — *„Juni 76 · Juli 31 · August 3 Meldungen. Ziel ist weniger
Wiederholung, nicht weniger echte Warnung — mit den Daten aus #1459 belegen."* — ist
strukturell nicht erfüllbar: Das Alarm-Protokoll (`src/services/alert_log.py:226-229`)
führt nur `metric_id` + `aggregation`, nicht den **Wert** der gemeldeten Größe. Ob 17×
„Gewitter" siebzehn echte Stufenwechsel waren oder siebzehnmal dieselbe Aussage, ist aus
dem Protokoll nicht auflösbar. Diese Arbeit ersetzt die unerfüllbare Messlatte durch zwei
prospektiv messbare Kennzahlen, dokumentiert den Befund als Kommentar an Epic #1458,
schließt das Epic und legt zwei Folge-Issues für die offenen Nebenbefunde an.

## Source

- **File:** `docs/context/epic-1458-messlatte.md` (Analyse, bereits vollständig, wird nur
  committet)
- **Identifier:** GitHub Issue #1458 (Kommentar + Close), zwei neue GitHub Issues

> **Schicht-Hinweis:** Diese Arbeit berührt keine Schicht des Produktivsystems (Frontend,
> Go-API, Python-Core). Sie ist reine Doku- und Issue-Pflege. Kein Datei-Edit in `src/`,
> `api/`, `internal/`, `frontend/`, `cmd/`.

## Estimated Scope

- **LoC:** 0 (Produktivcode)
- **Files:** 1 (`docs/context/epic-1458-messlatte.md`, bereits vorhanden — nur Commit)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #1458 | GitHub Issue (Epic) | Träger der alten Messlatte; bekommt Befund-Kommentar und wird geschlossen |
| #1459 | GitHub Issue (geschlossen) | Lieferte das Alarm-Protokoll, das als Datenquelle dieser Auswertung dient |
| `src/services/alert_log.py:226-229` | Code-Fundstelle | Beleg dafür, dass `metrics` nur `metric_id`+`aggregation` führt, keinen Wert |
| `src/services/alert_gate.py:143` | Code-Fundstelle | Beleg für Nebenbefund F3 (Ruhezeit-Sperre ohne Gewitter-Ausnahme) |

## Implementation Details

Vier Arbeitsschritte, keiner davon Produktivcode:

1. **Analyse-Dokument committen.** `docs/context/epic-1458-messlatte.md` existiert bereits
   fertig im Worktree und wird unverändert übernommen. Es enthält die vollständige
   Messmethodik, die Rohzahlen und die Schlussfolgerung, auf die der Issue-Kommentar
   verweist.

2. **Kommentar an Epic #1458.** Der Kommentar muss enthalten:
   - **Begründung**, warum die alte Messlatte (Juni 76 · Juli 31 · August 3) nicht
     erfüllbar ist: das Protokoll führt den Wert der gemeldeten Größe nicht
     (`alert_log.py:226-229`), daher ist eine Wiederholung fachlich nicht von einer neuen
     Information unterscheidbar.
   - Die **zwei Ersatzkennzahlen** K1 und K2 (siehe unten) inklusive Basislinie für K1:
     **66,7 %** (30 von 45 zugestellten Vorfällen, Zeitraum 2026-08-04 bis 2026-08-17,
     Nutzer `henning`).
   - Den **ausdrücklichen Hinweis auf die Artefakt-Falle**: die naive Kontrollprobe auf
     Juni/Juli liefert 85 %, ist aber kein Vergleichswert — im Altformat vor dem 02.08.
     fallen alle Signaturen auf `(None, (), ())` zusammen, wodurch fast jede zweite Meldung
     rechnerisch als „Wiederholung" erscheint, ohne es fachlich zu sein.
   - **Beleg, was das Epic erreicht hat:** vier eigenständige Bremsen mit gebuchtem Grund
     (`quiet_hours`, `channel_disabled`, `cooldown`, `below_channel_threshold` aus #1461,
     `event_duplicate` aus #1467 S4b-1), 68 vormals spurlose Unterdrückungen jetzt sichtbar
     in `not_delivered`, keine der drei Quellen (`forecast_change`/`nowcast`/
     `official_alert`) verstummt.

3. **Epic #1458 schließen**, erst nach dem Kommentar aus Schritt 2.

4. **Zwei neue Issues anlegen:**
   - **„Alarm-Protokoll hält den WERT der gemeldeten Größe fest"** — Labels `enhancement`,
     `area:alerts`, `session:alarm`. Setzt Befund B3 aus #1459 zu Ende (die Scheibe brachte
     *welche Größe*, nicht *welcher Wert*). Additive Erweiterung in
     `src/services/alert_log.py`, geschätzt ~20–40 LoC, kein Schemabruch. Ohne dieses Issue
     bleibt Kennzahl K1 dauerhaft nur teilweise messbar (Signatur ohne Wert).
   - **„Ruhezeit-Sperre kennt keine Ausnahme für akute Gefahr"** — Labels `bug`,
     `priority:high`, `area:alerts`, `session:alarm`. `check_nowcast_gate`
     (`src/services/alert_gate.py:143`) prüft die Ruhezeit zuerst und ohne
     Gewitter-Ausnahme; beide Nowcast-Pfade sind betroffen (`trip_alert.py:1120`,
     `compare_radar_alert.py:145`). Gemessen: 52 Vorfälle komplett unterdrückt, davon 48
     nachts zwischen 02 und 06 Uhr Ortszeit. #1310 hat den Akut-Override nur für die
     **Briefing**-Sperre gebaut, nicht für die Nowcast-Sperre. PO-Vorgabe 4 des Epics lautet
     „akute Gefahr muss durchkommen". **Wörtlich in die Issue-Beschreibung aufnehmen:**
     nicht verifiziert, ob unter den 52 unterdrückten Vorfällen konvektive Lagen waren —
     die unterdrückten Einträge tragen `metrics: []` (Lücke O3 aus
     `feat_1459_alert_protokoll.md`). Der Befund ist ein **belegter Verdacht**, keine
     bewiesene Fehlfunktion.

## Die zwei Ersatzkennzahlen (verbindlicher Wortlaut)

- **K1 „weniger Wiederholung":** Anteil der zugestellten Alarm-Vorfälle, die binnen 24 h
  dieselbe fachliche Aussage (`reason` + `metrics` + `hazards` + **Wert**) am selben
  Empfänger wiederholen. Basislinie **66,7 %** (30 von 45 Vorfällen, 2026-08-04 bis
  2026-08-17, Nutzer `henning`). Voll messbar erst nach der Protokoll-Erweiterung aus
  Issue 4a — bis dahin ist die Signatur unvollständig (Größe ohne Wert).
- **K2 „nicht weniger echte Warnung":** In jeder Kalenderwoche mit Alarmlage geht je
  Auslöser (`forecast_change`, `nowcast`, `official_alert`) mindestens ein Alarm
  zugestellt raus. Heute erfüllt und ohne weitere Änderung sofort messbar.

## Expected Behavior

- **Input:** die bereits abgeschlossene Analyse in `docs/context/epic-1458-messlatte.md`
  (Rohzahlen, Messmethodik, Schlussfolgerung).
- **Output:** committetes Analyse-Dokument · ein Kommentar an Issue #1458 mit den drei
  Pflichtinhalten (Begründung, Ersatzkennzahlen inkl. Basislinie, Beleg der Epic-Wirkung) ·
  Issue #1458 geschlossen · zwei neue GitHub Issues mit den oben spezifizierten Labels und
  Fundstellen.
- **Side effects:** keine. Kein Produktivcode wird verändert, keine Laufzeitdatei des
  Alarm-Systems wird angefasst, keine Konfiguration ändert sich.

## Was sich NICHT ändert

- **Kein Produktivcode.** Weder `src/services/alert_log.py` noch
  `src/services/alert_gate.py` werden in dieser Arbeit editiert — sie werden nur als
  Fundstellen zitiert. Die Änderung an `alert_log.py` ist Gegenstand des neuen Issues 4a,
  nicht dieser Spec.
- **Keine Alarm-Laufzeitdatei wird angefasst:** `trip_alert.py`, `compare_alert.py`,
  `compare_radar_alert.py`, `alert_log.py`, `alert_gate.py`, der Alarme-Reiter im Frontend.
- **Keine Migration, keine Schema-Änderung** am bestehenden `alert_log.json`.
- **Kein Verhalten des Alarm-Systems ändert sich** — weder Zustellung noch Unterdrückung
  noch Format einer Meldung.

## Acceptance Criteria

- **AC-1:** Given `docs/context/epic-1458-messlatte.md` liegt fertig im Worktree vor / When
  diese Arbeit abgeschlossen ist / Then ist die Datei im Repository committet und enthält
  unverändert die Basislinie 66,7 % sowie den Hinweis auf die Artefakt-Falle (85 %).
  - Test: `git log -- docs/context/epic-1458-messlatte.md` zeigt einen Commit; die Datei
    ist am Zielcommit vorhanden und lesbar.

- **AC-2:** Given die alte Messlatte („Juni 76 · Juli 31 · August 3") ist strukturell nicht
  erfüllbar / When der Nachweis abgeschlossen ist / Then trägt Issue #1458 einen Kommentar,
  der begründet, dass das Alarm-Protokoll (`alert_log.py:226-229`) den Wert der gemeldeten
  Größe nicht führt und deshalb Wiederholung nicht von neuer Information unterscheidbar ist.
  - Test: Kommentar-Text auf Issue #1458 nennt die Fundstelle `alert_log.py:226-229` und
    die Begründung "Wert nicht geführt".

- **AC-3:** Given die zwei Ersatzkennzahlen K1 und K2 / When der Kommentar verfasst wird /
  Then nennt der Kommentar beide Kennzahlen im oben festgelegten Wortlaut sowie die
  Basislinie 66,7 % mit Zeitraum (2026-08-04 bis 2026-08-17) und Nutzer (`henning`).
  - Test: Kommentar-Text enthält "66,7 %", "2026-08-04", "2026-08-17" und "henning" sowie
    beide Kennzahlnamen K1/K2.

- **AC-4:** Given die naive Kontrollprobe auf Juni/Juli liefert 85 % / When der Kommentar
  diese Zahl erwähnt / Then steht explizit dabei, dass diese Zahl ein Artefakt der
  zusammenfallenden Alt-Signaturen `(None, (), ())` ist und nicht als Vergleichswert
  verwendet werden darf.
  - Test: Kommentar-Text enthält den Begriff "Artefakt" im selben Absatz wie "85 %" und
    einen Hinweis, dass der Wert nicht zum Vergleich taugt.

- **AC-5:** Given der Kommentar aus AC-2 bis AC-4 ist auf Issue #1458 gepostet / When alle
  Pflichtinhalte vorhanden sind / Then ist Issue #1458 geschlossen.
  - Test: `gh issue view 1458 --json state` liefert `"CLOSED"`.

- **AC-6:** Given Befund B3 aus #1459 ist nur zur Hälfte geschlossen (Größe ja, Wert nein) /
  When die Analyse abgeschlossen ist / Then existiert ein neues GitHub Issue mit den Labels
  `enhancement`, `area:alerts`, `session:alarm`, das `alert_log.py:226-229` als Fundstelle
  und die unvollständige K1-Messbarkeit als Motivation nennt.
  - Test: `gh issue list --search "Wert" --label enhancement` zeigt ein Issue mit
    Fundstelle `alert_log.py:226-229` im Body.

- **AC-7:** Given der Ruhezeit-Befund F3 (52 unterdrückte Vorfälle, 48 davon nachts 02–06
  Uhr) / When die Analyse abgeschlossen ist / Then existiert der Befund als GitHub Issue mit
  den Labels `bug`, `priority:high`, `area:alerts`, `session:alarm`, das `alert_gate.py:143`
  als Fundstelle nennt und ausdrücklich vermerkt, dass nicht verifiziert ist, ob unter den
  52 unterdrückten Vorfällen konvektive Lagen waren — **und** der PO-Entscheid zu diesem
  Befund ist am Issue nachlesbar begründet, unabhängig davon, ob das Issue offen oder
  geschlossen ist.
  - Test: Ein Issue (beliebiger Zustand) mit diesen Labels enthält `alert_gate.py:143`, die
    Zahlen "52" und "48" sowie die Phrase "nicht verifiziert" im Body; zusätzlich ist in Body
    oder einem Kommentar ein begründeter PO-Entscheid nachlesbar.
  - Begründung für die Zustands-Unabhängigkeit: Ob das Issue offen bleibt oder geschlossen
    wird, entscheidet der PO — nicht diese Lieferung. Ein Kriterium, das „offen" verlangt,
    prüft damit einen Zustand außerhalb des Liefergegenstands. Prüfbar ist, was diese Arbeit
    zusichert: dass der Befund vollständig gebucht und der Umgang damit begründet ist.

## Known Limitations

- Die Kennzahl K1 ist bis zur Umsetzung des Folge-Issues 4a nur eingeschränkt aussagekräftig
  (Signatur ohne Wert), das ist bewusst akzeptiert und in Issue 4a dokumentiert.
- Der Nachweis ist eine Ein-Nutzer-Messung (`henning`) — die einzige Prod-Datenquelle mit
  durchgängiger August-Abdeckung. Das steht bereits im Analyse-Dokument und wird nicht
  erneut gemessen.
- Der Ruhezeit-Befund F3 ist ein belegter Verdacht, keine bewiesene Fehlfunktion — die
  Klärung, ob konvektive Lagen betroffen waren, ist Aufgabe des neuen Issues, nicht dieser
  Arbeit.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Diese Arbeit ändert keine Entscheidungsfläche (Kanäle, Provider,
  Datenmodell, Auth, Editor-Paradigma, Test-/Deploy-Strategie) — sie ersetzt ein
  unerfüllbares Erledigt-Kriterium eines Epics durch zwei messbare Kennzahlen und dokumentiert
  den Befund. Kein ADR nötig.

## Changelog

- 2026-08-18: Initial spec created
- 2026-08-18: AC-7 nach PO-Entscheid angepasst — geprüft wird nicht mehr ein **offenes**
  Issue, sondern dass der Befund als Issue existiert und der PO-Entscheid dort begründet
  nachlesbar ist. Grund: das ursprüngliche Kriterium prüfte einen Zustand, über den der PO
  entscheidet und nicht die Lieferung (#1955 wurde bewusst geschlossen, F3 revidiert).
