---
entity_id: fix_1724_faelligkeit_in_der_ortszone
type: bugfix
created: 2026-08-11
updated: 2026-08-11
status: draft
workflow: fix-1724-faelligkeit-in-der-ortszone
version: "1.0"
tags: [issue-1724, epic-1722, timezone, adr-0049, adr-0044, scheduler, briefing]
---

# Fix #1724 — Briefing-Fälligkeit je Trip in seiner Ortszone

## Approval

- [ ] Approved — PO-Freigabe der Akzeptanzkriterien steht aus.

## Purpose

Der Versand entscheidet Fälligkeit heute an **einer globalen Uhr**: `api/routers/scheduler.py:34`
bildet `datetime.now(ZoneInfo("Europe/Vienna")).hour` und reicht diese Stunde als `current_hour`
durch bis `_collect_due_trips`, wo sie gegen `trip.report_config.morning_time.hour` verglichen
wird.

`Europe/Vienna` ist dabei eine feste Konstante ohne fachliche Herleitung — keine Stelle leitet
sie aus einer Eigenschaft des Trips ab. Dass sie sich zufällig mit der Zone des Betreibers deckt,
macht sie nicht richtig; es erklärt nur, warum der Fehler lange unbemerkt blieb.

Gemessen für ein auf 07:00 gestelltes Morgen-Briefing am 20.08.2026:

| Zone | Ankunft Ortszeit | Versatz | Inhalt-Tag (`date.today()`) | Ortstag |
|---|---|---|---|---|
| Europe/Paris | 07:00 | ±0 h | 2026-08-20 | 2026-08-20 |
| Atlantic/Canary | 06:00 | −1 h | 2026-08-20 | 2026-08-20 |
| America/Denver | 23:00 | −8 h | 2026-08-20 | **2026-08-19** |
| America/Los_Angeles | 22:00 | −9 h | 2026-08-20 | **2026-08-19** |
| Pacific/Auckland | 17:00 | +10 h | 2026-08-20 | 2026-08-20 |
| Asia/Kathmandu | 10:45 | +3,75 h | 2026-08-20 | 2026-08-20 |

Zwei getrennte Fehler in einer Kette: die **Uhrzeit** stammt aus Wien, der **Kalendertag** aus der
Prozess-Zeitzone (`Etc/UTC`). Auf dem PCT trifft das „Morgenbriefing" um 22:00 des Vortages ein
und trägt den Inhalt des folgenden Weltzeit-Tages.

Umgesetzt wird Regel 2 aus **ADR-0049**: die Zone gehört an die Daten. Die Frage kehrt sich um —
statt „es ist 07:00 in Wien, welche Trips passen?" gilt „für jeden Trip: wie spät ist es in
*seiner* Zone?".

## Source

- Epic #1722, Analyse `docs/analysis/zeitzonen-architektur-2026-08.md`
- ADR-0049 (drei Zeitbegriffe, Zone an den Daten), ADR-0044 (Kalendertag folgt der Ortszeit)
- Offener Rest aus #1697: `_get_target_date`, `_get_active_trips`, `save_dated`

## Affected Files

| Datei | Änderung |
|---|---|
| `src/services/dispatch_orchestrator.py` | `collect_due(hour: int)` → `collect_due(now_utc: datetime)` auf beiden Strategien; `run_briefing_dispatch` reicht den Zeitpunkt durch |
| `src/services/trip_report_scheduler.py` | `_collect_due_trips` vergleicht je Trip die **Ortsstunde**; `send_reports_for_hour` nimmt einen Zeitpunkt; `_get_target_date`/`_get_active_trips`/`save_dated` folgen dem Ortstag |
| `api/routers/scheduler.py` | `ZoneInfo("Europe/Vienna")` entfällt; Endpunkt reicht `datetime.now(timezone.utc)` durch |
| `src/services/scheduler_dispatch_service.py` | `ZoneInfo("Europe/Vienna")`-Auswertung (`:164`) entfällt zugunsten des durchgereichten Zeitpunkts |
| `src/services/trip_day.py` | unverändert genutzt — kein zweiter Auflöser |

## Zuschnitt: was NICHT in dieser Scheibe ist

**Der Ortsvergleich bleibt vorerst auf der Wiener Uhr.** `CompareDispatchStrategy.collect_due`
teilt die Signatur und wird deshalb mitgeändert, rechnet die Wiener Stunde aber weiterhin selbst
aus — sichtbar als benannte Konstante mit Verweis auf **#1726**, nicht versteckt. Grund: der
Ortsvergleich hat eine eigene, offene Produktfrage (welche Zone gilt bei Orten in mehreren Zonen?)
und braucht einen eigenen Nachweis. Ein „nebenbei mitgefixt" wäre genau die Vermischung, die
#1722 auflösen soll.

**Stundengleichheit bleibt in dieser Scheibe erhalten.** Der Ersatz durch Fälligkeit +
Idempotenz-Schlüssel ist **#1725** und setzt diese Scheibe voraus. Folge: an einem
Sommerzeit-Umstellungstag bleibt das bekannte Verhalten (fehlende Ortsstunde → Briefing entfällt;
doppelte Ortsstunde → zwei Versuche). Das ist eine **bewusst offene Lücke**, die durch diese
Änderung von der Wiener auf die Ortszone wandert, aber nicht entsteht und nicht wächst — AC-7
misst sie, damit sie nicht stillschweigend als behoben gilt.

**Ruhezeit und Tageszähler** bleiben unberührt (#1726).

## Estimated Scope

~150–200 LoC Produktivcode über vier Dateien, überwiegend Signatur-Durchreichung. Der
Standard-Rahmen von 250 reicht; Testcode zählt nicht.

## Acceptance Criteria

- **AC-1 (Kernwirkung — Ankunftszeit):** Given ein Trip mit Etappen in `Pacific/Auckland` und
  konfiguriertem Morgen-Briefing 07:00 / When der stündliche Versandlauf über alle 24 vollen
  Stunden eines Tages läuft / Then wird der Trip **genau in der Stunde** als fällig gesammelt, in
  der es an seinen Wegpunkten 07:00 Ortszeit ist — und in keiner anderen.
  - Test: parametrisierter Lauf über 24 Zeitpunkte, Assert auf die Menge der fälligen
    `(trip, report_type)`-Paare je Stunde.

- **AC-2 (Kernwirkung — beide Vorzeichen):** Given je ein Trip in `America/Los_Angeles` (westlich),
  `Pacific/Auckland` (östlich), `Asia/Kathmandu` (halbstündiger Versatz) und `Europe/Paris`, alle
  mit Morgen-Briefing 07:00 / When derselbe Versandlauf über 24 Stunden läuft / Then ist jeder
  Trip genau einmal fällig, und zwar zu seiner eigenen Ortsstunde 07:00 — vier verschiedene
  Weltzeit-Stunden.

- **AC-3 (Der Kalendertag folgt mit):** Given der Trip aus AC-1 ist fällig / When das Briefing
  erzeugt wird / Then ist der Zieltag des Inhalts der **Ortstag** dieses Trips
  (`trip_day.trip_local_today`), nicht `date.today()` der Serveruhr.
  - Damit ist der in #1697 ausdrücklich offen gelassene Briefing-Pfad
    (`_get_target_date`, `_get_active_trips`, `save_dated`) abgedeckt; #1697 kann erst mit dieser
    Scheibe geschlossen werden.

- **AC-4 (Bestandsschutz Mitteleuropa):** Given ein Trip auf Korsika (`Europe/Paris`) mit
  Morgen-Briefing 07:00 und Abend-Briefing 18:00 / When der Versandlauf über 24 Stunden läuft /
  Then ist das Ergebnis **identisch** zum Verhalten vor dieser Änderung — gleiche Stunden, gleicher
  Zieltag. (Ausnahme und Teil der Behebung: bei Konfig-Stunden 00:00 und 01:00 weicht der Zieltag
  jetzt ab, weil er vorher falsch war.)

- **AC-5 (Keine geratene Zone mehr im Briefing-Pfad):** Given der Produktivcode nach dieser
  Änderung / When `api/routers/scheduler.py`, `trip_report_scheduler.py` und der Trip-Zweig von
  `dispatch_orchestrator.py` durchsucht werden / Then enthält keine dieser Stellen ein festes
  Zonen-Literal, und `send_reports_for_hour` nimmt keine vorberechnete Stunde mehr entgegen.
  - Test: AST-Prüfung, kein Datei-Inhalts-`assert 'xyz' in read_text()`.

- **AC-6 (Trip ohne Wegpunkte fällt sichtbar zurück):** Given ein Trip ohne Wegpunkte (Zone nicht
  auflösbar) / When der Versandlauf läuft / Then wird er nach dem dokumentierten UTC-Rückfall aus
  `trip_day.trip_tz` behandelt und **nicht übersprungen** — der Nutzer verliert sein Briefing
  nicht, weil eine Zone fehlt.

- **AC-7 (Sommerzeit — gemessen, nicht behauptet):** Given ein Trip in `Europe/Paris` mit
  Briefing-Stunde 02:00 / When der Lauf am 29.03.2026 (Ortsstunde 02 existiert nicht) und am
  25.10.2026 (Ortsstunde 02 existiert zweimal) durchgeführt wird / Then hält der Test das
  **tatsächliche** Verhalten fest: am 29.03. keine Fälligkeit, am 25.10. zwei.
  - Dieser Test ist bewusst ein Fest-Nageln der bekannten Lücke, kein Nachweis ihrer Behebung.
    Er wird von **#1725** rot gemacht und dort auf das Zielverhalten umgeschrieben.

- **AC-8 (Ortsvergleich unverändert):** Given ein Ortsvergleichs-Preset mit konfigurierter
  Slot-Stunde / When der Versandlauf läuft / Then ist sein Fälligkeitsverhalten **bit-identisch**
  zum Stand vor dieser Änderung — der Compare-Pfad wird von dieser Scheibe nicht verhaltensmäßig
  berührt (#1726).

- **AC-9 (Ein Zeitpunkt für den ganzen Lauf):** Given ein Versandlauf über mehrere Trips / When
  die Fälligkeit ermittelt wird / Then sehen alle Trips **denselben** „Jetzt"-Zeitpunkt — kein
  Trip darf eine andere Sekunde sehen als der nächste (Muster aus #1697: `now_utc` einmal vor der
  Schleife, Zone je Trip innerhalb).

## Nachweis-Strategie

Kern-Schicht, deterministisch: kein Netz, keine echten Postfächer. Zeit wird als Parameter
hereingereicht (Regel 3 aus ADR-0049), nicht per Patch auf die Systemuhr — die Tests bewachen
damit dieselbe Eigenschaft, die der Produktivcode zusichert.

**Mutations-Gegenprobe ist Pflicht** und hier besonders wichtig: #1697 fand dreimal in Folge
korrekten Produktivcode, den kein Test bewachte. Für jede Stelle, die eine Zone auflöst oder
einen Ortstag rechnet, ist zu belegen, welcher Test rot wird, wenn man sie auf die alte Fassung
zurückdreht. Leitfrage: **ist die Zusicherung dort geprüft, wo sie wirkt — oder nur dort, wo der
Code steht?**

Testdatei nach Verhalten benannt: `tests/tdd/test_briefing_faelligkeit_ortszone.py` (keine
Issue-Nummer im Dateinamen, `test_naming_gate.py`).

## Known Limitations

- **Trips über mehrere Zeitzonen.** Restfehler = Zonendifferenz zweier benachbarter Etappen
  (ADR-0044, PO-Entscheidung, unverändert).
- **Sommerzeit-Umstellungstage** — siehe AC-7, Behebung in #1725.
- **`TimezoneFinder` wird je Trip statt je Lauf gefragt.** Bei vielen Trips messbar; die
  Auflösung ist zu bündeln, sobald sie auffällt. Kein Vorab-Optimieren ohne Messung.

## Architektur-Entscheidung (ADR)

ADR-0049 (Regel 2: Zone an den Daten), ADR-0044 (Kalendertag folgt der Ortszeit). Diese Spec
führt beide im Briefing-Pfad aus, ohne von ihnen abzuweichen.

## Changelog

- 1.0 (2026-08-11) — Erstfassung, Freigabe ausstehend.
