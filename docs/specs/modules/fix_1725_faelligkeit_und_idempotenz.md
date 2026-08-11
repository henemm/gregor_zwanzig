---
entity_id: fix_1725_faelligkeit_und_idempotenz
type: bugfix
created: 2026-08-11
updated: 2026-08-11
status: draft
workflow: fix-1725-faelligkeit-idempotenz
version: "1.0"
tags: [issue-1725, epic-1722, timezone, adr-0051, adr-0044, scheduler, briefing, idempotenz]
---

# Fix #1725 — Briefing-Fälligkeit als Fenster + Idempotenz-Schlüssel

## Approval

- [ ] Approved

## Purpose

Die Fälligkeitsprüfung des Trip-Briefings vergleicht heute zwei Stunden auf **Gleichheit**:
`self._get_morning_hour(trip) == self._trip_local_hour(trip, now_utc)` bzw. dieselbe Prüfung
für den Abend-Slot (`src/services/trip_report_scheduler.py:372,375`). Das setzt voraus, dass
jede Ortsstunde eines Tages genau einmal existiert. An Zeitumstellungstagen stimmt das nicht:
am Frühjahrstag fehlt eine Ortsstunde ersatzlos (ein auf 02:00 gestelltes Briefing entfällt),
am Herbsttag existiert sie zweimal (das Briefing geht zweimal raus). Ursache ist zusätzlich,
dass der stündliche Go-Cron-Tick an genau diesen Tagen selbst eine Stunde auslässt bzw.
verdoppelt (`internal/scheduler/scheduler.go:112`, Bibliotheksverhalten von
`robfig/cron/v3`) — unabhängig von der Trip-Zone, weltweit für alle Nutzer.

Diese Spec ersetzt die Gleichheitsprüfung durch ein **Fälligkeitsfenster** von 3 Stunden
kombiniert mit einem **Idempotenz-Schlüssel** `(trip_id, ortstag, slot)`: ein Trip ist fällig,
solange die Ortsstunde die konfigurierte Stunde erreicht oder überschritten hat, aber noch
innerhalb des Fensters liegt, UND für den Schlüssel noch kein Vermerk existiert. Der Fehler
entsteht **erst durch die Verbesserung aus #1724 (S2)** — vorher lief die Rechnung in einer
festen Zone und war damit zufällig umstellungs-immun.

## Source

- **File:** `src/services/trip_report_scheduler.py`
- **Identifier:** `_collect_due_trips`, `_send_trip_report_outcome`
- Epic #1722, Kontext-Dokument `docs/context/fix-1725-faelligkeit-idempotenz.md`
- ADR-0051 (drei Zeitbegriffe, Zone an den Daten — Status Vorgeschlagen), ADR-0044
  (Kalendertag folgt der Ortszeit)
- Setzt voraus: #1724 (S2), live seit `e21f4f48`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/specs/modules/fix_1724_faelligkeit_in_der_ortszone.md` | spec | Direkte Vorlage; AC-7 dort ist der Test, der hier planmäßig auf Zielverhalten umgeschrieben wird; AC-8 (Compare bit-identisch), AC-9 (ein `now_utc` je Lauf) gelten unverändert fort |
| `src/services/trip_day.py` (`trip_local_now`, `trip_local_today`) | module | Liefert Ortsstunde und Ortstag; unverändert genutzt, kein zweiter Auflöser |
| `src/services/dispatch_orchestrator.py` (`TripDispatchStrategy`) | module | Aufrufkette `collect_due` → `pre_pass` → `dispatch_one`; hier docken die zwei neuen Zeilen an |
| `src/services/throttle_store.py` | module | Vorbild für Schreibmuster (`fcntl`-Lock + `tempfile`+`os.replace`); Fehlerrichtung wird bewusst **umgekehrt** (fail-closed statt fail-open) |
| `internal/store/log.go`, `internal/handler/briefing_history.go`, `internal/handler/cockpit.go` | Go | Lesen `briefing_log.json` nur; keine Schema-Änderung an dieser Datei nötig, da der Vermerk in einem eigenen Speicher entsteht |
| ADR-0051, ADR-0044 | adr | Regelgrundlage; siehe „Architektur-Entscheidung" unten |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/services/briefing_slots.py` | CREATE | Neuer Speicher `data/users/<uid>/briefing_slots.json`: reserve-then-release, `fcntl`-Lock, atomarer Schreibvorgang (`tempfile`+`os.replace`), fail-closed bei Sperren-Timeout, Rückwärts-Ableitung aus `briefing_log.json` beim ersten Lesen ohne eigene Datei |
| `src/services/trip_report_scheduler.py` | MODIFY | `_collect_due_trips`: Gleichheit → Fensterbedingung + Vermerk-Filter; neuer Wrapper `_dispatch_due_item()` um `_send_trip_report_outcome`, der den Vermerk je nach Outcome setzt |
| `src/services/dispatch_orchestrator.py` | MODIFY | Zwei Zeilen **innerhalb** `TripDispatchStrategy`: `pre_pass` (3-Tupel-Entpackung unverändert) und `dispatch_one` ruft den neuen Wrapper statt direkt `_send_trip_report_outcome` |
| `tests/tdd/test_briefing_slot_idempotenz.py` | CREATE | T1–T14, Verhaltensname statt Issue-Nummer (`test_naming_gate.py`) |
| `tests/tdd/test_briefing_faelligkeit_ortszone.py` | MODIFY | AC-7-Test (`:312-348`) wird von „0 Treffer / 2 Treffer" auf „1 Treffer / 1 Treffer" umgeschrieben — planmäßiges RED dieser Datei ist Teil des Vorhabens |

### Estimated Changes

- Files: 5 (3 Produktivcode, 2 Tests)
- LoC: ~170 Produktivcode (`briefing_slots.py` ~110, `trip_report_scheduler.py` ~55,
  `dispatch_orchestrator.py` ~6); Testcode zählt nicht gegen das Limit von 250

## Problem/Kontext

Der heutige Vergleich prüft **Stundengleichheit**, nicht **Fälligkeit**. Das war unauffällig,
solange die Uhr eine feste Zone (Wien) war — mit #1724 läuft sie nun je Trip in dessen
Ortszone, und dort existiert die Ortsstunde an Umstellungstagen nicht immer genau einmal:

- **Frühjahr** (Europe/Paris, 2026-03-29): Ortsstunde 02 existiert nicht. Ein auf 02:00
  gestelltes Briefing wird an diesem Tag **nie** fällig — heute: 0 Treffer.
- **Herbst** (2026-10-25): Ortsstunde 02 existiert zweimal. Dasselbe Briefing wird **zweimal**
  fällig — heute: 2 Treffer, doppelter Versand an echte Empfänger.

Ein zweiter, unabhängiger Fehler auf derselben Ebene: Der Go-Cron läuft in einer
**prozessweiten** Zone (`GZ_SCHEDULER_TIMEZONE`, Default `Europe/Vienna`,
`internal/config/config.go:20,52`) und nutzt `robfig/cron/v3`, dessen eigene Dokumentation
und Testsuite belegen, dass ein stündlicher Job an der Frühjahrs-Umstellung eine Stunde
**auslässt** und an der Herbst-Umstellung **zweimal** feuert
(`scheduler.go:112`; Bibliotheks-`spec_test.go:117-121,139-141`). Das betrifft **alle**
Nutzer weltweit an diesem Tag, nicht nur Trips in DST-Zonen — auch ein Trip in Auckland
verliert an diesem Tag einen Tick.

Heute existiert **kein** Fälligkeits-Idempotenz-Schutz überhaupt: Ein zweiter Lauf in
derselben Stunde (Neustart, manueller Trigger) hätte keinen Schutz gegen Doppelversand. Der
einzige Schutz ist strukturell, dass der Cron einmal pro Stunde feuert.

## Ziel

Fälligkeit wird durch ein **Fenster + Idempotenz-Schlüssel** ersetzt:

```
fällig ⟺ konfigurierte_stunde <= ortsstunde < konfigurierte_stunde + 3
          UND kein Vermerk für (trip_id, ortstag, slot)
```

Das erreicht drei Dinge gleichzeitig:

1. **Frühjahr korrekt:** Ortsstunde springt von 01 auf 03 (die 02 existiert nicht); 03 erfüllt
   `3 >= 2 and 3 < 5` → genau ein Treffer statt keinem.
2. **Herbst korrekt:** Ortsstunde 02 kommt zweimal vor; das erste Vorkommen setzt den Vermerk,
   das zweite wird durch ihn gefiltert → genau ein Treffer statt zwei.
3. **Ausgefallener Cron-Tick wird aufgefangen:** Verpasst der Tick eine Stunde (Umstellungstag,
   gescheiterter HTTP-Post ohne Retry, `scheduler.go:547`), sieht der nächste Lauf den Trip
   weiterhin als fällig, solange er innerhalb der 3 Stunden liegt.

## Nicht-Ziele (Abgrenzung)

- **Der Ortsvergleichs-Pfad wird nicht umgestellt.** `CompareDispatchStrategy.collect_due`
  (`dispatch_orchestrator.py:86-171`) behält seine eigene Stundengleichheit
  (`compare_slot_scheduler.py:152,154`) und die feste Zone
  `NOCH_NICHT_ORTSZEIT_SIEHE_1726 = "Europe/Vienna"` — das ist #1726. AC-8 aus #1724 (bit-
  identisches Compare-Verhalten) gilt fort und wird hier erneut nachgewiesen (AC-11/T11).
- **`_send_trip_report_outcome:905` liest weiter seine eigene Uhr**, statt den im Sammellauf
  gebildeten Zeitpunkt zu übernehmen. Das ist bekannte Drift zwischen Sammel- und
  Versandzeitpunkt (2,0 s Pause je Element, `dispatch_orchestrator.py:216-219`) und gehört zu
  #1726. Für die Idempotenz ist sie wirkungslos, weil der Schlüssel bereits im Sammellauf
  gebildet und durchgereicht wird.
- **#1557 wird nicht behoben.** Der Versand meldet dort fälschlich `sent`, obwohl kein Wetter
  verfügbar war (erwartet: `no_weather`). Die hier getroffene Outcome-Wahl ist gegen diesen
  Fehler **indifferent**: `sent` und `no_weather` landen beide in der Vermerk-Menge (siehe
  Entwurf unten), also führt eine Fehlklassifikation zwischen den beiden zum selben Ergebnis.
  Eine Regel „Vermerk nur bei `sent`" wäre es **nicht** — sie würde unter #1557 ein
  inhaltsleeres Briefing als erledigt abhaken UND zusätzlich keinen Marker schreiben, also
  auch die Nachholung über den Pending-Marker verhindern.
- **Der ausfallende Go-Cron-Tick wird nicht repariert**, sondern durch das Nachhol-Fenster
  **aufgefangen**. Eine Behebung in `robfig/cron` oder ein eigener Nachtrag-Mechanismus auf
  Go-Seite ist nicht Teil dieser Scheibe.
- **Retention/Prune für `briefing_slots.json`** ist nicht Teil dieser Scheibe. Die Datei wächst
  unbegrenzt; Bereinigung folgt als eigene, kleine Nachfolge-Arbeit (siehe Known Limitations).

## Entwurf/Umbau

### Prüfort = Wirkort: Check in der Sammel-Phase, nicht im Versand

Der Fälligkeits- und Vermerk-Filter sitzt in `_collect_due_trips`
(`trip_report_scheduler.py`), nicht erst in `_send_trip_report_outcome`. Drei Gründe:

1. Der bestehende Test aus #1724 ruft `_collect_due_trips` direkt
   (`tests/tdd/test_briefing_faelligkeit_ortszone.py:93`) — Prüfort und Wirkort müssen
   übereinstimmen.
2. `run_briefing_dispatch` schläft 2,0 s je Element der `due`-Liste
   (`dispatch_orchestrator.py:216-219`); eine unehrlich lange Liste kostet reale Laufzeit.
3. `_process_pending_markers` (`trip_report_scheduler.py:445-448`) räumt den #1012-
   Nachliefer-Marker weg, sobald der Trip in `due_trip_ids_now` steht. Stünde dort mit `>=`
   ohne Filter **jede Stunde** jeder Trip, würde der gesamte Nachliefermechanismus lautlos
   stillgelegt — ohne dass ein sichtbarer Versandfehler entsteht.

### Eigener Speicher statt Wiederverwendung

`briefing_log.json` scheidet als Träger aus: #1007 F001 verbietet dort Einträge mit
`channels=[]` (`:1234-1246`), weil sonst die Cockpit-Kachel #393 einen Versand vortäuscht —
vier der fünf Vermerk-Fälle (`no_stage`, `no_weather`, `no_channels`, Ausnahme) haben aber
keine Kanäle. `throttle_state.json` ist semantisch fremd (Cooldown-Fenster, kein
Slot-Schlüssel) und **fail-open** bei Sperren-Timeout — für eine Idempotenz-Quittung wäre das
die falsche Fehlerrichtung. `pending_briefings.json` ist eine Warteschlange offener Arbeit, die
nach Auflösung **verschwindet** — kein Sende-Protokoll.

Es entsteht `data/users/<uid>/briefing_slots.json`, Schema
`{"entries": [{"trip_id", "slot", "local_day", "recorded_at", "outcome"}]}`:

- **Schreibmuster** wie `throttle_store._update()`: `fcntl`-Lock über
  `services.file_lock.acquire_exclusive`, `tempfile`+`os.replace`.
- 🔴 **Fehlerrichtung umgekehrt:** `throttle_store` ist fail-open, weil ein zu grober Cooldown
  nur einen doppelten Hinweis kostet. Hier heißt „Sperre nicht erhalten" = potenzieller
  Doppelversand, inklusive kostenpflichtiger Premium-SMS — also **fail-closed**: gelingt die
  Reservierung nicht, wird **nicht** gesendet (AC-13).
- **Reserve-then-release:** Der Vermerk wird **vor** dem Versandversuch geschrieben und nur bei
  `channels_unreachable` oder einer Ausnahme wieder zurückgenommen. Stirbt der Prozess mitten
  im Versand, bleibt der Vermerk stehen — nie doppelt, im schlimmsten Fall ein ausgelassener
  Slot, der über das Nachhol-Fenster in der nächsten Stunde erneut versucht wird (sofern noch
  im Fenster).
- **Keine Migration nötig** (Datei existiert noch nicht). Stattdessen **Rückwärts-Ableitung
  beim ersten Lesen ohne eigene Datei:** fehlt ein Vermerk in `briefing_slots.json`, gilt der
  Slot als bereits erledigt, wenn `briefing_log.json` einen Eintrag mit passender `trip_id` +
  `kind` (= Slot) trägt, dessen `sent_at` in den aktuellen Ortstag fällt. Das verhindert den
  einzigen realistischen Doppelversand-Fall: ein Deploy mitten im Nachhol-Fenster.

### Vermerk je Outcome

| Outcome | Vermerk | Begründung |
|---|---|---|
| `sent` | ja | zugestellt |
| `no_stage` | ja | nichts zu senden; ein Wiederholungsversuch ändert daran nichts |
| `no_weather` | ja | Ohne Vermerk: stündliche „keine Daten"-Mail, stündlicher voller Wetterabruf (Kontingent #1329) — der bestehende #1012-Pending-Marker deckt die Nachholung bereits ab; ein zweiter, konkurrierender Wiederholpfad wäre der Fehler |
| `no_channels` | ja | Konfigurationszustand, ändert sich nicht binnen Stunden; der Wetterabruf läuft **vor** dieser Prüfung, ohne Vermerk verbrennt das Kontingent für nichts |
| `channels_unreachable` | **nein** | genau der beabsichtigte Nachholfall — per Definition (`sent=bool(sent_channels)`) hat niemand etwas bekommen |
| Ausnahme | nein | fällt durch reserve-then-release automatisch heraus |

### Nachhol-Fenster: 3 Stunden

`konfigurierte_stunde <= ortsstunde < konfigurierte_stunde + 3`. Deckt den ausfallenden
Cron-Tick (1 Stunde) mit Reserve für einen gescheiterten, nicht wiederholten HTTP-Post. Eine
Deckelung am Tagesende ist nicht nötig: für Slot 22 sind es die Ortsstunden 22 und 23; ab
Ortsmitternacht wechselt der Ortstag, und `0 >= 22` ist falsch. Eine Alternative „bis Tagesende"
wurde verworfen, weil sie neu angelegte oder aus `paused_until` zurückkehrende Trips
**rückwirkend** feuern ließe — `_get_active_trips` (`:656-657`) prüft nur die Etappe, nicht das
Anlagedatum (AC-10).

### Compare bleibt unberührt

Geändert werden ausschließlich `trip_report_scheduler.py`, `TripDispatchStrategy`
(`dispatch_orchestrator.py:35-83`) und das neue Modul `briefing_slots.py`. **Verboten:** jeder
neue Hook im geteilten Skelett von `run_briefing_dispatch` (`:180-221`, insbesondere ein
`already_sent(item)` vor `dispatch_one:212`), eine gemeinsame Basisklasse für beide Strategien,
oder ein Antasten von `compare_slot_scheduler.presets_due_for_hour` — das ist #1726.

### On-Demand-Pfade: weder lesen noch schreiben

Manueller Test-Versand (`api/routers/scheduler.py:230`), Inbound-Kommandos „heute"/„morgen"
(`trip_command_processor.py:575`) und „report" (`:1018`) sowie die Legacy-CLI berühren den
Vermerk nicht: nicht schreiben (sonst nimmt eine Nutzeranfrage dem Nutzer sein reguläres
Briefing weg), nicht lesen (sonst wäre der Test-Knopf nach dem regulären Versand tot). Die
Trennung entsteht über den **Aufrufer**: Der Vermerk sitzt in einem neuen Wrapper
`_dispatch_due_item()`, der ausschließlich von `TripDispatchStrategy.dispatch_one` gerufen
wird — kein zusätzliches Flag nötig (AC-12).

### Zwei Commits in einem PR — der gefährliche Zustand wird unerreichbar

Der riskanteste Zwischenschritt wäre `>=` **ohne** wirksamen Vermerk: das führt zu
stündlichem Serienversand an echte Empfänger, inklusive kostenpflichtiger Premium-SMS. Die
Umsetzung wird deshalb in zwei Commits geschnitten, beide im selben PR:

- **Commit A (verhaltensneutral):** Speicher, Rückwärts-Ableitung und Vermerk-Filter werden
  gebaut und in `_collect_due_trips` verdrahtet — **die Fälligkeit bleibt `==`**. Ein Slot
  feuert bei `==` ohnehin genau einmal, der neue Filter ist dabei ein No-op. Der Schreibpfad
  ist nach diesem Commit bewiesen (T1/T2/T5-T14 laufen bereits gegen ihn, soweit sie nicht die
  Fensterbreite selbst prüfen).
- **Commit B (Verhaltensänderung):** `==` wird zu `>=` mit `NACHHOL_FENSTER_STUNDEN = 3`
  (`:372,375`).

Weil Commit A den Vermerk bereits scharf schaltet, bevor Commit B die Fensteröffnung vornimmt,
ist jeder Zwischenstand auslieferbar — ein Revert oder ein Bisect zwischen den beiden Commits
landet nie im gefährlichen Zustand „offenes Fenster ohne Schutz".

## Acceptance Criteria

- **AC-1 (Frühjahrs-Umstellung — Slot fällt nicht mehr aus):** Given ein Trip in
  `Europe/Paris` mit Morgen-Briefing 02:00 und ein Sammellauf am 29.03.2026, an dem die
  Ortsstunde 02 nicht existiert / When der Versandlauf den Ortstag abschreitet / Then wird der
  Trip **genau einmal** als fällig gesammelt (bei Ortsstunde 03, weil `3 >= 2 und 3 < 5`) —
  heute entfällt der Versand ersatzlos.
  - Test: T1 in `test_briefing_slot_idempotenz.py`.

- **AC-2 (Herbst-Umstellung — keine Doppelzustellung):** Given derselbe Trip an einem
  Sammellauf am 25.10.2026, an dem die Ortsstunde 02 zweimal existiert / When beide Vorkommen
  der Ortsstunde 02 im Lauf durchschritten werden / Then wird der Trip **genau einmal** als
  fällig markiert — das erste Vorkommen setzt den Vermerk, das zweite wird durch ihn gefiltert;
  heute geht das Briefing zweimal raus.
  - Test: T2.

- **AC-3 (Normaler Tag — nur die konfigurierte Stunde trifft):** Given ein Trip mit
  Morgen-Briefing 07:00 an einem Tag ohne Zeitumstellung / When jede der 24 Ortsstunden dieses
  Tages einzeln durchlaufen wird / Then ist der Trip in genau der Stunde fällig, in der die
  Ortsstunde 07 erreicht wird, und in keiner der übrigen 23.
  - Test: T3.

- **AC-4 (Nachhol-Fenster — beide Grenzen zugleich):** Given Slot-Stunde H fällt aus, weil der
  stündliche Tick nicht lief (Umstellungstag oder gescheiterter HTTP-Post ohne Retry) / When
  der nächste Lauf in Ortsstunde H+1 stattfindet / Then wird der Trip nachträglich als fällig
  gesammelt; findet der nächste Lauf dagegen erst in Ortsstunde H+3 statt, ist er **nicht mehr**
  fällig — das Nachhol-Fenster umfasst genau 3 Stunden, in beide Richtungen geprüft.
  - Test: T4 — einziger Test, der die Fensterbreite in beide Richtungen festnagelt.

- **AC-5 (Schlüssel braucht den Slot):** Given ein Trip mit Morgen- **und** Abend-Briefing,
  beide auf 07:00 gestellt / When die Ortsstunde 07 erreicht wird / Then werden **beide** Slots
  unabhängig voneinander als fällig gesammelt und unabhängig vermerkt — der Vermerk des einen
  Slots blockiert den anderen nicht.
  - Test: T5.

- **AC-6 (Schlüssel braucht den Ortstag):** Given ein Trip, dessen Morgen-Briefing an zwei
  aufeinanderfolgenden Ortstagen fällig wird / When der Lauf am zweiten Ortstag ausgeführt wird
  / Then ist der Trip erneut fällig — der Vermerk vom Vortag blockiert den neuen Tag nicht.
  - Test: T6.

- **AC-7 (Schlüssel braucht die Trip-ID):** Given zwei verschiedene Trips in derselben Zone
  mit identischer Briefing-Stunde / When diese Ortsstunde erreicht wird / Then werden **beide**
  Trips unabhängig voneinander als fällig gesammelt und vermerkt — der Vermerk des einen Trips
  darf den anderen nicht blockieren.
  - Test: T7.

- **AC-8 (Outcome-Matrix entscheidet über den Vermerk):** Given ein Versandversuch endet mit
  einem der vier Ausgänge `sent`, `no_stage`, `no_weather` oder `no_channels` / When der
  Versuch abgeschlossen ist / Then wird für alle vier ein Vermerk gesetzt, sodass dieser Slot
  an diesem Ortstag **nicht erneut** verarbeitet wird — auch nicht in den verbleibenden
  Stunden des Nachhol-Fensters; nur beim Ausgang `channels_unreachable` bleibt der Vermerk
  aus, sodass der nächste Lauf innerhalb des Fensters einen weiteren Versuch unternimmt.
  - Test: T8.

- **AC-9 (Rollout ohne Doppelversand beim Deploy):** Given `briefing_slots.json` existiert
  noch nicht (frischer Rollout dieser Änderung), aber `briefing_log.json` enthält für den Trip
  bereits einen Eintrag mit passender Trip-ID und Slot-Art, dessen Sendezeitpunkt in den
  aktuellen Ortstag fällt / When die Fälligkeit geprüft wird / Then gilt der Slot als bereits
  erledigt und wird **nicht** erneut fällig.
  - Test: T9.

- **AC-10 (Kein rückwirkendes Feuern bei neuen/reaktivierten Trips):** Given ein Trip wird neu
  angelegt oder kehrt aus einer Pause (`paused_until`) zurück, seine erste Etappe liegt heute,
  die konfigurierte Morgen-Stunde liegt aber mehr als 3 Stunden zurück / When der erste
  Sammellauf danach stattfindet / Then wird der Trip **nicht** rückwirkend als fällig behandelt
  — das Nachhol-Fenster schließt diesen Fall strukturell aus.
  - Test: T10.

- **AC-11 (Ortsvergleich bleibt bit-identisch):** Given der Ortsvergleichs-Pfad
  (`CompareDispatchStrategy.collect_due`) mit unveränderter Konfiguration / When derselbe
  Versandlauf über 24 Stunden ausgeführt wird wie vor dieser Änderung / Then ist sein
  Fälligkeitsergebnis **bit-identisch** zum Stand davor — der Idempotenz-Check wirkt
  ausschließlich im Trip-Pfad, nicht im geteilten Skelett.
  - Test: T11.

- **AC-12 (On-Demand-Versand ist vom Vermerk unabhängig):** Given ein Nutzer fordert per
  SMS-Kommando „heute" oder über den Test-Versand-Knopf ein Briefing außerhalb des regulären
  Slots an / When dieser On-Demand-Versand ausgeführt wird / Then setzt er **keinen** Vermerk
  für den regulären Slot, und er liest auch **keinen** — der reguläre Slot bleibt zur Stunde H
  weiterhin fällig, und der Test-Knopf funktioniert nach einem regulären Versand weiter.
  - Test: T12.

- **AC-13 (Sperre nicht erhältlich → kein Versand, fail-closed):** Given die Schreibsperre auf
  `briefing_slots.json` ist innerhalb der konfigurierten Zeit nicht zu bekommen (z.B. gehaltene
  Sperre in einem parallelen Prozess) / When ein Trip zum Versand ansteht / Then wird **nicht**
  gesendet, statt ohne wirksamen Vermerk zu senden — die Fehlerrichtung ist bewusst umgekehrt
  zu `throttle_store`, das bei Sperren-Timeout fail-open ist.
  - Test: T13 (Machbarkeit als ausdrückliche Lücke markiert, siehe Known Limitations).

- **AC-14 (`Australia/Lord_Howe` — 24,5-Stunden-Tag unauffällig):** Given ein Trip in der Zone
  `Australia/Lord_Howe` (Halbstunden-Versatz, an ihren eigenen Umstellungstagen 24,5 Stunden
  lang) mit konfigurierter Briefing-Stunde / When der Sammellauf über den vollständigen Ortstag
  läuft / Then wird der Trip genau einmal fällig, ohne Lücke und ohne Dopplung — der
  Halbstunden-Versatz bricht die Fälligkeitsprüfung nicht.
  - Test: T14.

## Nachweis-Strategie

Kern-Schicht, deterministisch: kein Netz, kein echtes Postfach. Zeit wird als Parameter
hereingereicht (Muster aus #1724: `_faellig(scheduler, now_utc)` ruft `_collect_due_trips`
direkt), nicht per Patch auf die Systemuhr. Neue Datei
`tests/tdd/test_briefing_slot_idempotenz.py` (Verhaltensname, nicht Issue-Nummer —
`test_naming_gate.py` blockt sonst).

🔴 **Falle, die die Testfälle vorwegnehmen:** Bei funktionierendem Vermerk liefert **jede**
Fensterbreite an einem normalen Tag genau einen Treffer. Ein Test, der nur Treffer zählt, kann
die Fensterbreite selbst nicht sehen — sie ist ausschließlich an einem ausgefallenen Tick
beobachtbar (T4), deshalb ist T4 der einzige Test, der beide Fenstergrenzen zugleich prüft.

| # | AC | Testfall | Verfälschung, die ihn rot macht |
|---|---|---|---|
| T1 | AC-1 | Europe/Paris, `morning=02:00`, 2026-03-29 → genau 1 | `>=` zurück auf `==` → 0 Treffer |
| T2 | AC-2 | dito 2026-10-25 (Doppelstunde) → genau 1 | Vermerk-Filter entfernen → 2 Treffer |
| T3 | AC-3 | Normaler Tag, jede einzelne Ortsstunde gezählt → nur Stunde 07 trifft | Fälligkeit auf `<=` drehen → 8 Treffer |
| T4 | AC-4 | Stunde H ausgelassen → H+1 fällig, H+3 nicht mehr | Fenster 3→1 macht ersten Teil rot, 3→„bis Tagesende" macht zweiten Teil rot |
| T5 | AC-5 | `morning=07:00` und `evening=07:00` → beide fällig | `slot` aus dem Schlüssel entfernen → nur einer feuert |
| T6 | AC-6 | Zwei aufeinanderfolgende Ortstage → an beiden fällig | `local_day` aus dem Schlüssel entfernen → Tag 2 bleibt stumm |
| T7 | AC-7 | Zwei Trips, gleiche Zone, gleiche Stunde → beide fällig | `trip_id` aus dem Schlüssel entfernen → nur einer feuert |
| T8 | AC-8 | Outcome-Matrix: vier setzen Vermerk, `channels_unreachable` nicht | `channels_unreachable` in die Vermerk-Menge schieben → nächste Stunde bleibt still, Test rot |
| T9 | AC-9 | `briefing_slots.json` fehlt, `briefing_log.json` trägt passenden Eintrag im Ortstag → nicht fällig | Rückwärts-Ableitung entfernen → fällig (Doppelversand beim Deploy) |
| T10 | AC-10 | Trip mit Etappe heute, `morning=07:00`, erstmals um Ortsstunde 20 ausgewertet → nicht fällig | Fenster auf „bis Tagesende" → fällig |
| T11 | AC-11 | `CompareDispatchStrategy.collect_due` über 24 h unverändert | Filter ins geteilte Skelett verschieben → Compare-Zahl ändert sich |
| T12 | AC-12 | Nach `send_on_demand_report` ist der reguläre Slot zur Stunde H weiterhin fällig | Vermerk in `_send_trip_report_outcome` statt im Wrapper setzen → rot |
| T13 | AC-13 | Sperre nicht erhältlich → kein Versand statt Versand ohne Vermerk | fail-open wie `throttle_store:139-150` → rot |
| T14 | AC-14 | `Australia/Lord_Howe`: Ortsstundenfolge ohne Loch und ohne Dopplung → unauffällig | schließt die bisher unbelegte Repo-Lücke |

Zusätzlich wird der bestehende Test `test_briefing_faelligkeit_ortszone.py:312-348`
(`test_ac7_sommerzeit_luecke_ist_gemessen_nicht_behauptet`) planmäßig umgeschrieben: von
„0 Treffer am 29.03. / 2 Treffer am 25.10." auf „1 Treffer / 1 Treffer" — sein
Docstring sagt bereits, dass #1725 ihn rot macht und auf das Zielverhalten umstellt.

**Mutations-Gegenprobe (Pflicht, `.claude/agents/implementation-validator.md` Schritt 3b):**
mindestens die vier in der Analyse benannten Mutationen sind gegenzuprüfen: Fenster 3→1 und
3→24, Schlüssel um je ein Glied kürzen (Slot/Ortstag/Trip-ID einzeln), Filter ins geteilte
Skelett verschieben, Vermerk nach `_send_trip_report_outcome` statt in den Wrapper verlegen.

## Estimated Scope

- **LoC:** ~170 Produktivcode über drei Dateien (`briefing_slots.py` CREATE ~110,
  `trip_report_scheduler.py` MODIFY ~55, `dispatch_orchestrator.py` MODIFY ~6); Testcode zählt
  nicht gegen das Limit.
- **Files:** 3 Produktivdateien, 2 Testdateien (1 neu, 1 geändert).
- **Effort:** medium — die einzelnen Änderungen sind klein, aber die Reihenfolge (zwei Commits,
  siehe Entwurf) und die Fehlerrichtung des neuen Speichers sind sicherheitskritisch und
  brauchen sorgfältige Mutations-Gegenprobe.
- **Limit-Reserve:** 250/Workflow reicht, aber nicht komfortabel (~170/250). Bei Überlauf ist
  die Schnittkante Retention/Prune für `briefing_slots.json` (~20 LoC) — die gehört ohnehin
  nicht in diese Scheibe (s.u.). **Nicht** herausschneidbar: Rückwärts-Ableitung und
  fail-closed-Sperre, beide sind Teil der Sicherheitsargumentation.

## Known Limitations

- **T13 (fail-closed bei Sperren-Timeout) ist als machbar eingeschätzt, aber nicht
  verifiziert.** Ein mockfreier Aufbau (gehaltener `flock`-Filedescriptor im selben Prozess,
  verkürztes `LOCK_TIMEOUT_SECONDS` für den Testlauf) gilt als plausibel, ist aber nicht vorab
  gebaut worden. Sollte er sich als unverhältnismäßig teuer erweisen, ist das im PR explizit zu
  benennen — die Fehlerrichtung selbst bleibt die sicherheitskritischste Einzelentscheidung
  des Vorhabens und darf nicht ungeprüft bleiben.
- **`fold` wird bewusst nicht gebraucht.** Es wird nie eine mehrdeutige Wanduhrzeit
  konstruiert — die Ortsstunde entsteht immer aus einem eindeutigen UTC-Zeitpunkt
  (`trip_day.py:74`). Die Doppelstunde im Herbst erscheint als zwei unterscheidbare
  UTC-Zeitpunkte und wird über den Vermerk getrennt, nicht über Wanduhr-Disambiguierung.
- **`skip_next` würde still mitverändert, wenn der neue Filter vor `_get_active_trips`
  gezogen würde.** `skip_next` wird bei jedem Sammellauf konsumiert (`:678-683`), unabhängig
  von der Fälligkeit. Solange der Filter **nach** `_get_active_trips` sitzt, bleibt das
  Verhalten unverändert — wer ihn zum Sparen davorzieht, ändert `skip_next` ungewollt mit. Das
  ist eine Implementierungsreihenfolge, kein separater Test, weil sie nicht als beobachtbares
  Verhalten isolierbar ist, ohne den ganzen Sammellauf nachzubauen.
- **Retention/Prune für `briefing_slots.json`** ist nicht Teil dieser Scheibe. Die Datei wächst
  unbegrenzt mit jedem Sammellauf-Vermerk; eine Bereinigungsstrategie (z.B. Einträge älter als
  N Tage) folgt als eigene, kleine Nachfolge-Arbeit.
- **`data/` muss untracked bleiben** — die neue Datei `briefing_slots.json` darf nie committet
  werden.
- **Kontingent-Nebenwirkung bewusst in Kauf genommen:** `channels_unreachable` löst bis zu drei
  Wetterabrufe statt einem aus (#1329), weil dort kein Vermerk entsteht. Begrenzt auf den
  Nachholfall, nicht Gegenstand dieser Scheibe.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0051, ADR-0044
- **Rationale:** ADR-0051 (Status: Vorgeschlagen) beschreibt in Regel 3 „Keine Umgebungsuhr —
  ‚Jetzt' wird als Zeitpunkt-Parameter hereingereicht" und nennt den Idempotenz-Schlüssel
  `(trip_id, ortstag, slot)` bereits wörtlich (`:89-95`) — diese Spec ist die konkrete
  Umsetzung dieser bereits formulierten Regel, kein neuer Grundsatz. ADR-0044 legt fest, dass
  jedes Tagesfenster seine Länge **berechnen** muss statt sie zu setzen (`:46-49`) und dass
  zwei zeitzonenbehaftete Zeitpunkte vor einem Vergleich nach UTC umgerechnet werden müssen
  (`:59-67`) — beide Regeln werden hier angewendet, nicht verändert. Ein **neues** ADR ist
  deshalb nicht nötig: Es entsteht keine neue Entscheidungsfläche, sondern die Umsetzung einer
  bereits vorgeschlagenen Regel im Briefing-Pfad. Wird ADR-0051 im Zuge dieser oder einer
  Folge-Scheibe von „Vorgeschlagen" auf „Akzeptiert" gehoben, ist diese Spec einer seiner
  ersten praktischen Nachweise.

## Changelog

- 1.0 (2026-08-11): Initial spec created, aus `docs/context/fix-1725-faelligkeit-idempotenz.md`
  auf Basis der Vorlage `fix_1724_faelligkeit_in_der_ortszone.md`.
