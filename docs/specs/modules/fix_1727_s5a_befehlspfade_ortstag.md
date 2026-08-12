---
entity_id: fix_1727_s5a_befehlspfade_ortstag
type: bugfix
created: 2026-08-12
updated: 2026-08-12
status: draft
version: "1.0"
tags: [timezone, telegram, trip-command-processor, issue-1727, issue-1722, adr-0044, adr-0051]
workflow: fix-1727-s5a-befehlspfade
---

# Fix #1727 S5a — Befehlspfade folgen dem Ortstag der Tour

## Approval

- [ ] Approved

## Purpose

Die Befehlspfade `/status`, `/jetzt`, `### ruhetag` und die Tourauswahl `_find_active_trip`
bestimmen „welcher Kalendertag gemeint ist" weiterhin über die Serveruhr (`date.today()`) bzw.
den UTC-Tag der eingehenden Nachricht (`msg.received_at.date()`) statt über den Ortstag der
Tour — ein Verstoß gegen die bereits akzeptierte ADR-0044. Diese Scheibe (S5a von #1727, Epic
#1722) schließt vier der dort namentlich als „noch nicht umgesetzt" gelisteten Stellen, indem
sie an allen vieren den geteilten Baustein `trip_local_today(trip, now_utc)` aus
`services/trip_day.py` einsetzt — keine eigene Kopie der Zonen-Auflösung.

## Source

- **File:** `src/services/trip_command_processor.py`
  **Identifier:** `command_date` (Zeile 429, Dispatch für `### ruhetag`), `_show_status`
  (Zeile 1074–1086), `_show_now` (Zeile 1224–1257)
- **File:** `src/services/inbound_telegram_reader.py`
  **Identifier:** `_find_active_trip` (Zeile 352–375)
- **Zonen-Auflösung (unverändert nutzen):** `src/services/trip_day.py::trip_local_today(trip,
  now_utc)` (Zeile 90–96)

## Estimated Scope

- **LoC:** ~45–55 Produktivcode / ~105–145 Testcode (Limit 250, passt mit Puffer)
- **Files:** 2 Produktivdateien MODIFY, 1 Wächterdatei MODIFY, 3 Bestandstestdateien MODIFY
  (Signaturanpassung `_find_active_trip`), 1 neue Testdatei CREATE, `tests/tdd/conftest.py`
  MODIFY (Zwei-Zonen-Fixtur heben)
- **Effort:** medium — die Rechnung selbst ist klein (ruft nur einen bestehenden, bereits
  getesteten Baustein auf), das Risiko liegt im Blast Radius: `_find_active_trip` sitzt vor
  **jedem** Telegram-Befehl, `### ruhetag` schreibt Etappendaten

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/trip_command_processor.py` | MODIFY | `command_date` (:429) über `trip_local_today`; `_show_status`/`_show_now` bekommen `now_utc: datetime` als Pflichtparameter, `today` über `trip_local_today(trip, now_utc)`. `_handle_query` bleibt unberührt (s. „Nicht in dieser Scheibe"). |
| `src/services/inbound_telegram_reader.py` | MODIFY | `_find_active_trip` bekommt `now_utc: datetime` als Pflichtparameter, Ortstag-Auflösung wandert **in** die Schleife, je Tour. Beide Aufrufer (:187, :314) ziehen `datetime.now(tz=timezone.utc)` einmal vor den Aufruf und reichen denselben Wert später an `received_at` der `InboundMessage` weiter — bisher zwei potenziell verschiedene Zeitpunkte, künftig einer. |
| `tests/test_output_timezone_guard.py` | MODIFY | Drei `KNOWN_VIOLATIONS`-Einträge entfernen: `:619` `_find_active_trip`, `:627` `_show_now`, `:628` `_show_status` |
| `tests/tdd/test_inbound_telegram_reader.py` | MODIFY | Drei Aufrufstellen `_find_active_trip()` (:78, :108, :130) auf neue Signatur |
| `tests/tdd/test_bug_824_archived_trip_filter.py` | MODIFY | Aufrufstelle `_find_active_trip(two_trip_env)` (:198) auf neue Signatur |
| `tests/tdd/_telegram_live_fixture.py` | MODIFY | Aufrufstelle `_find_active_trip(user_id)` (:344) auf neue Signatur |
| `tests/tdd/conftest.py` | MODIFY | `_trip_two_zones` aus `test_drilldown_day_window_local_date.py:415-431` heben (Wellington + Korsika); Altnutzer auf den Import umziehen |
| `tests/tdd/test_<neuer-name>.py` | CREATE | Verhaltenstests für alle vier Fundstellen, nach Verhalten benannt |

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `services.trip_day.trip_local_today(trip, now_utc)` | module function | Ersetzt `date.today()`/`received_at.date()` an allen vier Stellen dieser Scheibe |
| ADR-0044 (Akzeptiert) | decision | Verlangt Ortstag statt Servertag/UTC für Kalendertage; die vier Stellen dieser Scheibe stehen dort namentlich unter „Noch nicht umgesetzt" |
| ADR-0051 Regel 3 (Vorgeschlagen) | decision | Verbietet Systemuhr-Default — `now_utc` wird an allen vier Stellen als Pflichtparameter hereingereicht, nie mit Default auf `datetime.now()` |
| `trip_report_scheduler._get_active_trips` (#1724) | pattern | Vorbild für „Tagesbestimmung IN der Schleife, je Trip", Docstring `:729-740` |
| `tests/test_output_timezone_guard.py::test_known_violations_only_shrink` | guard | Die drei Einträge `:619`/`:627`/`:628` müssen im selben Commit entfallen, sonst wird der Wächter rot |
| `tests/tdd/test_drilldown_day_window_local_date.py::_trip_two_zones` | test fixture | Wird nach `tests/tdd/conftest.py` gehoben statt ein drittes Mal gebaut |

## Implementation Details

**`### ruhetag` (Zeile 429):**
```python
command_date = trip_local_today(trip, msg.received_at)
```

**`_show_status`/`_show_now`** bekommen `now_utc: datetime` als Pflichtparameter; die Dispatch-
Stellen (:439/:441) reichen `msg.received_at` durch:
```python
def _show_status(self, trip: Trip, now_utc: datetime) -> CommandResult:
    today = trip_local_today(trip, now_utc)
    ...

def _show_now(self, trip: Trip, now_utc: datetime) -> CommandResult:
    today = trip_local_today(trip, now_utc)
    ...
```
`trip_local_today` wird zum bestehenden Modul-Import `from services.trip_day import anchor_tz,
display_tz` (Zeile 23) ergänzt.

**`_find_active_trip`** bekommt `now_utc: datetime` als Pflichtparameter (vor `user_id`, analog
`_get_active_trips(report_type, now_utc)`); die Tagesbestimmung wandert **in** die Schleife, je
Tour über deren eigene Zone — wortgleiches Muster zu `_get_active_trips`
(`trip_report_scheduler.py:722-779`, Docstring `:729-740`), inklusive des Fallback-Zweigs
„frühester zukünftiger Trip", der ebenfalls je Trip rechnet statt gegen einen einmal
berechneten Wert. Beide Aufrufer (`inbound_telegram_reader.py:187`, `:314`) ziehen
`datetime.now(tz=timezone.utc)` einmal vor den Aufruf und verwenden denselben Wert für
`received_at` der später gebauten `InboundMessage` — das ist eine Nebenwirkung des
Pflichtparameters, kein zusätzlicher Scope-Punkt: Trip-Auswahl und Nachrichtenstempel beziehen
sich damit garantiert auf denselben Augenblick statt auf zwei knapp versetzte
`datetime.now()`-Aufrufe wie heute.

## Nicht in dieser Scheibe

- **`_handle_query` (:499) und die Timeline-Familie** `glance`/`heute_gewitter`/
  `timeline_heute`/`timeline_morgen` → **Issue #1795**. `today`/`tomorrow` werden dort **einmal**
  berechnet (:499-500) und speisen **alle sechs** Zweige; eine zweite `today`-Definition allein
  für den `/heute`/`/morgen`-Fehlertext wäre genau die verbotene „zweite Kopie der
  Zonen-Auflösung in derselben Funktion" (ADR-0044). Der saubere Fix ist ein anderer:
  `send_on_demand_report` soll den benutzten Tag **zurückgeben**, statt dass der Aufrufer ihn
  errät — das gehört zu #1795.
- **Die Go-Seite**, `preview_service.py`, `comparison_engine.py`, `gpx_processing.py`,
  `openmeteo.py`, `api/routers/debug.py`, `tools/weather_validation.py` → Folgescheiben
  S5b/S5c.
- **Ein Koordinaten-Cache für `tz_for_coords`.** Bewusste Nicht-Entscheidung: `tz_for_coords`
  hat kein Ergebnis-Caching, nur der `TimezoneFinder` selbst ist ein Lazy-Singleton. Ein
  `.timezone_at()` je Tour und Aufruf ist linear und billig. S5a ist eine Korrekturscheibe,
  kein Ort für eine Optimierung ohne gemessenen Engpass.

## Expected Behavior

- **Input:** ein eingehender Telegram- oder Mail-Befehl (`msg.received_at`, ein UTC-Zeitpunkt)
  für `/status`, `/jetzt`, `### ruhetag` oder die vorgelagerte Tourauswahl.
- **Output:** Der Tagesbezug (Etappenfilter, Etappenwahl, Tourauswahl, Idempotenzschlüssel)
  entspricht dem **Ortstag der betroffenen Tour** zum Zeitpunkt `received_at` — nicht dem
  Servertag (`Etc/UTC`) und nicht dem rohen UTC-Datum der Nachricht.
- **Side effects:** `command_log.json`-Einträge tragen künftig den Ortstag statt des
  UTC-Tages; Bestandseinträge (falls vorhanden) bleiben unangetastet, keine Migration.

## Acceptance Criteria

- **AC-1:** Given eine Tour liegt in einer Zone mit negativem UTC-Offset (z. B. US-Westküste,
  UTC−8) mit einer Etappe für den heutigen Ortstag / When `/status` zwischen 00:00 und 08:00
  UTC abgefragt wird — der Ortstag ist dort noch der Vortag des UTC-Kalendertages / Then bleibt
  die heutige Etappe in der Liste sichtbar; vor dem Fix fiel sie durch den Filter
  `stage.date >= today`, weil `today` fälschlich schon den UTC-Folgetag trug.
  - Test: `freeze_time` in diesem Fenster, Trip-Fixtur mit Wegpunkt in der Zielzone,
    Etappe datiert auf den Ortstag; Assertion auf die Etappe in `confirmation_body`.

- **AC-2:** Given eine Tour liegt in einer Zone mit positivem UTC-Offset (z. B. Neuseeland,
  UTC+12) mit einer bereits lokal abgeschlossenen Etappe / When `/status` zwischen 12:00 und
  24:00 UTC abgefragt wird — der Ortstag ist dort schon der UTC-Folgetag / Then verschwindet die
  bereits abgeschlossene Etappe aus der Liste; vor dem Fix blieb sie sichtbar, weil der
  Servertag sie noch als „heute oder später" einstufte.
  - Test: `freeze_time` in diesem Fenster, Etappe auf den (aus Ortssicht) vergangenen Tag
    datiert; Assertion, dass sie NICHT mehr in `confirmation_body` erscheint.

- **AC-3:** Given eine Tour steht kurz vor oder nach der Ortsmitternacht (z. B. Korsika,
  Nachricht 22:30 UTC = 00:30 Ortszeit des Folgetags) mit einer Etappe für heute und einer für
  morgen / When `/jetzt` abgefragt wird / Then bestimmt `_show_now` die Etappe des
  **Ortstages** für die Nowcast-Standortwahl (Wegpunkt der Folgetags-Etappe), nicht die des
  Servertages — #1402 hatte hier bereits nur die Uhrzeit im Onset-Text ortsrichtig gemacht, der
  zugrunde liegende Tag blieb Servertag.
  - Test: Assertion auf die für `get_nowcast(lat, lon, ...)` übergebenen Koordinaten — sie
    müssen vom Wegpunkt der Ortstag-Etappe stammen, nicht vom Vortag.

- **AC-4:** Given eine Tour auf Korsika (UTC+2) hat eine Etappe für den Ortstag D / When
  `### ruhetag` einmal um 00:30 Ortszeit (= 22:30 UTC am Vortag) und einmal um 14:00 Ortszeit
  desselben Ortstages (= 12:00 UTC) gesendet wird / Then bleibt die Etappe von D in **beiden**
  Fällen unverschoben — vor dem Fix wanderte sie um 00:30 Ortszeit mit, weil `command_date` noch
  den Vortag trug (`D > command_date` wurde fälschlich wahr).
  - Test: zwei `freeze_time`-Läufe gegen dieselbe Trip-Fixtur, Etappe D in `shifts` beider
    Antworten NICHT enthalten.

- **AC-5:** Given eine Tour hat nur noch die heutige Etappe (Ortstag D, keine späteren
  Etappen) — der Randfall, in dem `shifts` nach dem Fix leer wird / When `### ruhetag`
  innerhalb des Mismatch-Fensters gesendet wird (z. B. 22:30 UTC am Vortag auf Korsika) / Then
  meldet die Antwort „Keine zukuenftigen Etappen zum Verschieben" (`success=False`) statt
  „Ruhetag eingetragen" — vor dem Fix hätte die (fälschlich D−1 zugeordnete) heutige Etappe
  noch als verschiebbar gegolten.
  - Test: Ein-Etappen-Trip-Fixtur, `freeze_time` im Mismatch-Fenster, Assertion auf
    `success is False` und den genannten Text.

- **AC-6:** Given `### ruhetag` wird erfolgreich angewendet / When `_append_command_log` den
  Eintrag schreibt / Then trägt das Feld `date` den **Ortstag** (`trip_local_today`-Ergebnis),
  nicht `msg.received_at.date()` — ein zweiter Versuch mit demselben Ortstag, aber leicht
  verschobenem UTC-Zeitstempel im selben Mismatch-Fenster, wird von `_is_already_applied`
  weiterhin als Duplikat erkannt. Keine Migration nötig: Bestand enthält (nachgemessen, weder
  im Worktree- noch im Hauptrepo-`data/`) keine `command_log.json`; Prod/Staging sind dazu nicht
  gemessen (kein Lesezugriff). Ein hypothetischer Altbestandseintrag mit UTC-Datum würde von der
  neuen Ortstag-Logik einmalig — nur bei einem Umstellungstag im Mismatch-Fenster — nicht als
  Duplikat seines Ortstag-Gegenstücks erkannt: kein Datenverlust, höchstens eine überflüssige
  Zweitausführung.
  - Test: `freeze_time` im Mismatch-Fenster, `### ruhetag` zweimal mit unterschiedlicher
    Sekunde, aber gleichem Ortstag senden; zweiter Versuch liefert `success=False` „bereits
    eingetragen".

- **AC-7:** Given zwei Touren liegen in unterschiedlichen Zonen und tragen zum selben `now_utc`
  unterschiedliche Ortstage (z. B. Wellington und Korsika, zwölf Stunden auseinander) — eine der
  beiden ist per Ortstag bereits beendet, die andere per Ortstag aktiv / When
  `_find_active_trip(now_utc, user_id)` beide Touren prüft / Then liefert die Funktion die per
  Ortstag aktive Tour. Das ist die Pflicht-Probe gegen die gemessene Nachweis-Lücke: eine
  Mutation, die die Tagesbestimmung **vor** die Schleife zieht und einen einzigen, aus nur einer
  Tour abgeleiteten Tag für alle wiederverwendet, muss diesen Test rot machen — genau diese
  Regression hat #1724 bereits einmal in `_get_active_trips` behoben, und kein bestehender Test
  von `_find_active_trip` fängt sie.
  - Test: Zwei-Touren-Fixtur mit den oben beschriebenen Eigenschaften; zusätzlich eine
    Mutationsprobe (Tagesbestimmung testweise vor die Schleife gezogen) im Bericht belegen, dass
    sie den Test bricht.

- **AC-8:** Given zwei aneinandergrenzende Touren in Mitteleuropa (UTC+2) — Tour A endet an
  Ortstag D, Tour B beginnt an Ortstag D+1 — der Blast-Radius-Grenzfall an der Tourgrenze / When
  eine Telegram-Nachricht um 22:30 UTC eintrifft (= 00:30 Ortszeit des Folgetags D+1) / Then
  wählt `_find_active_trip` bereits Tour B, weil lokal schon D+1 ist — vor dem Fix hätte der
  Servertag D noch Tour A gewählt, und ein bereits abgelaufener Trip hätte den Befehl fälschlich
  beantwortet.
  - Test: `freeze_time` 22:30 UTC, Tourenliste [A endend D, B beginnend D+1], Assertion auf
    `_find_active_trip(...) is B`.

- **AC-9:** Given ein neuer Test für eine der vier Fundstellen dieser Scheibe wird geschrieben,
  dessen Fixtur behauptet, dass Ortstag und Servertag auseinanderfallen — der
  Vorbedingungs-Anker ist Pflicht, keine Kür / When der Test die Hauptzusicherung prüft / Then
  belegt er das **zuvor** mit einer eigenen Vorbedingungs-Assertion (Muster
  `tests/unit/test_trip_local_today.py:60-63`) — ohne sie ist die Hauptzusicherung strukturell
  nie falsifizierbar, die Fixturen-Falle aus #1726 F002.
  - Test: nicht automatisierbar; im QA-Bericht zu belegen, dass jede neue Testfunktion dieser
    Scheibe eine solche Vorbedingungs-Assertion trägt (Muster: fix_1470 AC-4).

- **AC-10:** Given die Umstellung auf `trip_local_today(trip, now_utc)` — ein `ast.Call` auf
  `ast.Name`, kein `ast.Attribute` mehr — ist an allen drei betroffenen Stellen abgeschlossen,
  der Wächter also aktualisiert / When
  `tests/test_output_timezone_guard.py::test_known_violations_only_shrink` läuft / Then sind
  die Einträge `src/services/inbound_telegram_reader.py::_find_active_trip::0`,
  `src/services/trip_command_processor.py::_show_now::0` und
  `src/services/trip_command_processor.py::_show_status::0` aus `KNOWN_VIOLATIONS` entfernt, und
  der Test bleibt grün.
  - Test: `tests/test_output_timezone_guard.py::test_known_violations_only_shrink`.

## Nachweisführung

Vollständig offline belegbar (Kern-Schicht): `freeze_time` (freezegun, vorgemacht in
`tests/unit/test_trip_local_today.py:24/52`) plus In-Memory-`Trip`/`Stage`/`Waypoint`. **Keine
Staging-Mail nötig** — der Versand selbst ist unberührt, alle vier Stellen sind reine
Anzeige-/Auswahllogik. Ein exemplarischer Sommerzeit-Umstellungstag statt einer vollen Matrix:
die reine Datumsbestimmung ist bereits über `trip_local_today`s eigene AC-7-Tests (beide
Wechseltage, `tests/unit/test_trip_local_today.py`) abgedeckt — diese Scheibe prüft die
**Verdrahtung** der vier Aufrufstellen, nicht erneut die Zonenrechnung in voller Schärfe.

## Testfixtur

Es gibt zwei Zwei-Zonen-Fixturen, beide unteilbar in Testmodulen verankert: `_trip_two_zones`
(`tests/tdd/test_drilldown_day_window_local_date.py:415-431`, Wellington + Korsika, zwölf
Stunden auseinander) und `trip_zwei_zonen` (`tests/tdd/test_ruhezeit_und_zaehler_folgen_der_ortszone.py:1553`).
Diese Scheibe hebt `_trip_two_zones` nach `tests/tdd/conftest.py` und zieht den bestehenden
Nutzer in `test_drilldown_day_window_local_date.py` auf den Import um — eine dritte Kopie wäre
genau der Fehler, den ADR-0044 für die Zonen-Auflösung selbst verbietet.

## Testbenennung

Testdateien nach Verhalten benennen, nicht nach Issue-Nummer — durchgesetzt von
`test_naming_gate.py`, das neue issue-nummerierte Testdateien hart blockiert. Vorschlag:
`tests/tdd/test_befehlspfade_folgen_ortszone.py` als Sammel-Datei für alle vier Fundstellen;
eine Aufteilung je Fundstelle ist ebenso zulässig, solange kein `test_issue_1727*`-Name
entsteht.

## Known Limitations

**Bekannte Grenzen dieser Scheibe:**

- Im Mismatch-Fenster (Größe = `|UTC-Offset|` Stunden ab Ortsmitternacht) nennen `/status`
  (künftig: Ortstag) und `glance`/`heute_gewitter`/`timeline_heute`/`timeline_morgen` (weiterhin:
  UTC-Tag, bis #1795) unterschiedliche Tage. Das ist **Anzeige-Divergenz ohne gemeinsamen
  Datenträger** — kein Datenverlust, keine still fehlschlagende Zusicherung, strukturell anders
  als die Persistenz-Kopplung, vor der #1697 warnt. Kein neuer Bruch: Drilldown (#1470,
  ortszonenrichtig) und `_handle_query` (UTC) nennen schon heute unterschiedliche Tage.
- **Mehrzonen-Touren:** Restfehler = Zonendifferenz zweier benachbarter Etappen, wenn der
  Wanderer an genau dem betreffenden Tag die Zeitzone wechselt (ADR-0044, PO-Entscheidung,
  unverändert, bewusst offen).
- **`command_log.json`:** Bestand nicht gemessen auf Prod/Staging (`/var/lib/gregor*`, kein
  Lesezugriff als `hem`, kein sudo verwendet). Sollten dort Einträge mit UTC-Datum existieren,
  greift die Doppelausführungssperre für sie einmalig im Mismatch-Fenster eines
  Umstellungstages nicht — kein Datenverlust, keine Migration nötig oder vorgesehen.
- **Kein Koordinaten-Cache** für `tz_for_coords` — bewusste Nicht-Entscheidung, s. „Nicht in
  dieser Scheibe".

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0044 (Akzeptiert), ADR-0051 (Vorgeschlagen, Regel 3)
- **Rationale:** Setzt die bereits akzeptierte ADR-0044-Entscheidung an vier der dort namentlich
  ausgegrenzten Stellen um — keine offene Produktfrage, ein Bug gegen eine getroffene
  Entscheidung. Folgt zusätzlich Regel 3 aus ADR-0051 (`now_utc` als Pflichtparameter, kein
  Systemuhr-Default), obwohl jenes ADR noch „Vorgeschlagen" ist: Regel 3 ist an anderer Stelle
  (#1724, #1726) bereits umgesetzt und dort als bindendes Muster etabliert, an dem sich diese
  Scheibe ausdrücklich orientiert (Docstring-Vorbild `trip_report_scheduler.py:738-740`).

## Changelog

- 2026-08-12: Spec erstellt nach Kartierung `docs/context/fix-1727-s5a-befehlspfade.md`
  (Basis-HEAD `77229550`).
