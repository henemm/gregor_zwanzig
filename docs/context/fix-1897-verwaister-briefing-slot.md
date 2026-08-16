# Context: fix-1897-verwaister-briefing-slot

Issue: [#1897](https://github.com/henemm/gregor_zwanzig/issues/1897) · `bug` · `priority:high` · `session:khw`
Phase 1 (Context Generation), erhoben 2026-08-16.

## Request Summary

Ein Briefing-Versand, der mitten im Lauf durch ein hartes Prozessende abbricht (Deploy,
SIGKILL, OOM, Crash), hinterlässt im Slot-Speicher einen Claim mit `outcome: null`. Dieser
Claim zählt heute als „erledigt". Folge sind zwei nutzersichtbare Defekte: das Briefing wird
für den restlichen Ortstag **nicht nachgeholt**, und die Alarm-Vorlauf-Sperre aus #1594
**hebt auf**, obwohl nie ein Briefing kam. Beide Defekte gehen durch dieselbe Methode
`BriefingSlotStore.is_recorded()`.

## Belegter Vorfall (Produktion, 2026-08-16, Trip KHW `5f534011`)

Die Prod-Datei `/var/lib/gregor/users/henning/briefing_slots.json` trägt 8 Einträge, davon
**zwei mit `outcome: null`** — und genau an diesen beiden Tagen fehlt das Briefing:

| local_day | slot | recorded_at | outcome |
|---|---|---|---|
| 2026-08-14 | evening | 16:00:00.28 UTC | **null** |
| 2026-08-15 | morning | 05:00:00.30 UTC | `sent` |
| 2026-08-15 | evening | 16:00:00.21 UTC | `sent` |
| 2026-08-16 | morning | 05:00:00.24 UTC | **null** |

Der Vorfall ist also kein Einzelfall, sondern ein Muster mit mindestens zwei Vorkommen.

Zwei ergänzend gemessene Fakten, die den Zuschnitt tragen:

1. **Der Nachhol-Takt existiert bereits.** Der Go-Cron-Eintrag `briefing_dispatch` läuft
   `0 * * * *` (`internal/scheduler/scheduler.go:141`). Bei `NACHHOL_FENSTER_STUNDEN = 3`
   (`src/services/trip_report_scheduler.py:106`) hätte es am 16.08. um 08:00 und 09:00
   Ortszeit zwei weitere Gelegenheiten gegeben. Verhindert hat sie allein der verbrannte
   Slot — es braucht **keinen neuen Auslöser**, nur eine korrekte Fälligkeits-Antwort.
2. **Der Briefing-Anker war im Vorfall nicht gesetzt.** `_anchor_and_reset()` steht erst
   nach dem Versandaufruf (`trip_report_scheduler.py:1521-1527`, beide Zweige). Ein
   Prozessende davor schreibt ihn nicht. Damit bleibt Bedingung 2 von
   `check_briefing_imminent()` („noch nicht versucht") korrekt — sobald Bedingung 1 wieder
   stimmt, greift die Alarm-Sperre im Crash-Fall wieder wie beabsichtigt.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/briefing_slots.py:68-80` | `is_recorded()` — der Wirkort beider Defekte. Zählt jeden gefundenen Eintrag als erledigt, ohne `outcome` anzusehen (`:78`). |
| `src/services/briefing_slots.py:82-101` | `reserve()` — schreibt den Claim mit `outcome=None` **vor** dem Versand. Findet `_find` einen Bestandseintrag, wird nicht reserviert (`:92-93`) — ein verwaister Claim blockiert also auch die Neu-Reservierung. |
| `src/services/briefing_slots.py:103-132` | `record_outcome()` / `release()` — die beiden Abschlusswege, die bei hartem Prozessende ausbleiben. |
| `src/services/briefing_slots.py:136-144` | `_eintrag()` — Schema. **Trägt bereits `recorded_at`**; für eine zeitbasierte Verwaisungs-Erkennung ist kein neues Feld und keine Bestandsdaten-Migration nötig (an den 8 Prod-Einträgen bestätigt). |
| `src/services/trip_report_scheduler.py:539-558` | `_collect_due_trips()` — Wirkort von **Defekt 1**: `is_recorded()` filtert den Slot für den Rest des Ortstags heraus (`:553-556`). |
| `src/services/trip_report_scheduler.py:180-201` | `trip_briefing_due_at()` — Wirkort von **Defekt 2**: dieselbe `is_recorded()`-Frage (`:196-199`) beendet das Fälligkeits-Prädikat. Der Kommentar `:191-195` sichert ausdrücklich das Gegenteil zu („Nach einem GESCHEITERTEN Versand trägt er nicht"). |
| `src/services/trip_report_scheduler.py:560-599` | `_dispatch_due_item()` — reserve-then-release. Der Docstring `:565-568` benennt den Crash-Fall bereits, zieht aber keine Konsequenz. |
| `src/services/trip_report_scheduler.py:94` | `VERMERK_AUSGAENGE = {"sent", "no_stage", "no_weather", "no_channels"}` — die vier Ausgänge, die einen Vermerk setzen dürfen. |
| `src/services/alert_gate.py:200-300` | `check_briefing_imminent()` — die UND-Bedingung aus #1594. Bedingung 1 fällt weg, sobald `briefing_due_at` False liefert. |
| `src/services/alert_briefing_anchor.py:215-230` | `last_briefing_at()` — Bedingung 2 der Sperre, im Crash-Fall korrekt leer (s. o.). |

## Existing Patterns

- **TTL + Aktivitätsprüfung ist das etablierte Verwaisungs-Muster im Repo.**
  `.claude/hooks/file_claim_gate.py:45,362-383`: `STALE_AFTER_SECONDS = 4 * 60 * 60`, Alter
  gegen `claimed_at_epoch`, **plus** eine zweite Prüfung („Claim ist offensichtlich beendet"),
  die nicht allein auf der Uhr beruht.
- **Es gibt im Repo KEINE persistierte Prozess- oder Startkennung** — keine Boot-ID, kein
  `run_id`, keine PID im Zustand, und in `api/main.py:88-101` (FastAPI-`lifespan`) auch
  keinen Recovery-Schritt, der beim Start alte Zustandsdateien aufräumt. Die im Issue als
  „naheliegend" genannte Prozesskennung wäre also Neuland; die Ablaufzeit-Variante nutzt
  Vorhandenes.
- **Fail-closed-Fehlerrichtung ist für diesen Speicher bewusst gewählt** (Modul-Docstring
  `briefing_slots.py:13-18`): „nicht geschrieben" heißt Doppelversand an echte Empfänger
  inklusive kostenpflichtiger Premium-SMS. Jede Lockerung muss diese Richtung respektieren.
- **In-Memory-Overlap-Schutz auf Go-Seite:** `internal/scheduler/scheduler.go:87-92,460-489`
  benutzt `TryLock()` je Job — ein zweiter Tick wird übersprungen, nicht gestapelt. Relevant
  als Randbedingung: zwei gleichzeitige Briefing-Läufe desselben Nutzers sind dadurch
  unwahrscheinlich, aber nicht prozessübergreifend ausgeschlossen.

## Dependencies

- **Upstream (was der Store benutzt):** `services/file_lock.acquire_exclusive`
  (Sidecar-Sperre, 2 s), `utils.timezone.local_dt`, `app.loader.get_data_dir`,
  `briefing_log.json` (Rückwärts-Ableitung nur solange `briefing_slots.json` fehlt).
- **Downstream (was vom Store abhängt):** ausschließlich `trip_report_scheduler.py` —
  bestätigt per Volltextsuche, `BriefingSlotStore` hat genau drei Aufrufstellen
  (`:181`, `:541`, `:583`). Über `trip_briefing_due_at` hängt indirekt `trip_alert.py:732-738`
  daran. **Der Ortsvergleichs-Pfad benutzt den Store heute NICHT** (`compare_alert.py`,
  `compare_official_alert.py` rufen `check_briefing_imminent` mit einem eigenen Prädikat).
- **Go-Seite unberührt:** `internal/handler/cockpit.go` liest `briefing_log.json`, nicht
  `briefing_slots.json`.

## Existing Specs

| Pfad | Relevanz |
|---|---|
| `docs/specs/modules/fix_1725_faelligkeit_und_idempotenz.md` | Ursprungs-Spec des Slot-Speichers: Schema, Fälligkeitsfenster, Outcome-Wahl (vier Ausgänge setzen den Vermerk, `channels_unreachable` und Ausnahmen nicht). Muss um die Verwaisungs-Regel ergänzt/abgelöst werden. |
| `docs/specs/modules/fix_1724_faelligkeit_in_der_ortszone.md` | Vorgänger: Fälligkeit in der Ortszone. |
| `docs/specs/modules/fix_1851_alarm_tests_vorlaufsperre.md` | Dokumentiert das 3-Stunden-Nachholfenster im Alarm-Zusammenhang. |
| `docs/adr/0051-drei-zeitbegriffe-zone-an-den-daten.md` | Regel 3: kein Systemuhr-Rückfall, Zeitpunkt ist Pflicht-Parameter. Bindend für jede neue Ablauf-Prüfung. |
| `docs/adr/0044-kalendertage-folgen-der-ortszeit.md` | `local_day` folgt der Ortszeit; Umstellungstage haben nicht 24 h. |
| `docs/context/fix-1725-faelligkeit-idempotenz.md` | Kontext-Dokument des Vorgängers (reserve-then-release, fail-closed). |

## Bestehende Tests (Ausgangslage)

| Datei | Umfang | Was sie bewacht |
|---|---|---|
| `tests/tdd/test_briefing_slot_idempotenz.py` | 18 Tests (T1–T15) | Fenster, Schlüssel-Vollständigkeit, Outcome-Wahl, Rückwärts-Ableitung, On-Demand-Abgrenzung, fail-closed ohne Sperre. |
| `tests/tdd/test_trip_alert_briefing_imminent.py` | 10+ Tests, u. a. R6 (`:529`) | R6: ein **gescheiterter** Versand darf das Nachholfenster nicht in Alarmstille verwandeln — nächster Nachbar der hier geplanten Änderung. |
| `tests/tdd/test_briefing_faelligkeit_ortszone.py` | ~8 Tests | Fälligkeit in der Ortszone. |
| `tests/helpers/briefing_imminent_fixtures.py` | Helfer | `briefing_versand_gescheitert()`, `trip_briefing_vermerk_setzen()`, `zustand_schnappschuss()` — wiederverwendbar für die RED-Phase. |

**Selbst nachgeprüft:** Kein bestehender Test erwartet, dass ein Eintrag mit `outcome: null`
als erledigt gilt. Die Tests fahren über eine echte Scheduler-Unterklasse und setzen dabei
stets einen Ausgang; die einzige direkte `reserve()`-Nutzung (`:979-983`) ruft unmittelbar
`record_outcome(..., "sent")`. Die Änderung zementiert also kein Bestandsverhalten weg —
umgekehrt heißt das aber auch: **das Fehlverhalten ist heute von keinem Test abgedeckt.**

## Risks & Considerations

1. **Doppelversand ist die teure Fehlerrichtung.** Eine zu großzügige Verwaisungs-Regel
   lässt einen noch laufenden Versand ein zweites Mal starten — an echte Empfänger,
   inklusive kostenpflichtiger Premium-SMS. Die Ablauffrist muss länger sein als jeder
   legitime Versandlauf und kürzer als der Abstand zweier Cron-Ticks (1 h), sonst wirkt sie
   nicht.
2. **`is_recorded()` beantwortet heute zwei verschiedene Fragen** — „darf ich neu senden?"
   (`_collect_due_trips`) und „ist das Briefing raus, sodass der Alarm wieder darf?"
   (`trip_briefing_due_at`). Ein offener Claim ist auf die erste Frage „nein, außer er ist
   verwaist" und auf die zweite „nein, es kam nichts raus". Die Zusammenlegung beider Fragen
   in einer Methode ist die eigentliche Wurzel; der Zuschnitt muss entscheiden, ob getrennt
   wird oder ob eine Antwort für beide Wirkorte genügt.
3. **Nachhol-Semantik am Fensterende.** Wird ein verwaister Claim freigegeben, greift wieder
   das reguläre 3-Stunden-Fenster. Ein um 07:00 abgebrochenes Morgen-Briefing kommt also um
   08:00 — ein um 09:30 abgebrochenes gar nicht mehr. Das ist vertretbar, muss aber in der
   Spec als bewusste Grenze stehen (das Issue nennt `NACHHOL_FENSTER_STUNDEN` ausdrücklich
   als Prüfpunkt).
4. **Gleichzeitigkeit.** Zwei Läufe dürfen einen verwaisten Claim nicht beide übernehmen.
   Die Übernahme muss innerhalb derselben `_update()`-Sperre geschehen wie die Reservierung,
   nicht als getrennter Lese-dann-Schreib-Schritt.
5. **ADR-0051 Regel 3:** die Ablaufprüfung braucht einen übergebenen Zeitpunkt, keinen
   `datetime.now()`-Rückfall — sonst ist sie im Test nicht steuerbar und verletzt die
   bestehende Zeit-Entscheidung.
6. **Abgrenzung Ortsvergleich:** der Compare-Pfad benutzt den Store noch nicht (#1777 ist
   die offene Scheibe dafür). Die Projektregel „Trip und Ortsvergleich teilen Code" ist
   gewahrt, indem die Korrektur **im geteilten Store** sitzt und nicht im Trip-Scheduler —
   dann trägt sie automatisch, sobald #1777 den Vergleich anschließt.
7. **Der auslösende Deploy-Zeitpunkt gehört nicht hierher** (henemm-infra). Dieses Issue
   bleibt unabhängig davon gültig, weil Crash/OOM/Neustart jederzeit eintreten können.

---

# Analysis (Phase 2)

## Type

**Bug.** Root Cause aus dem Issue durch eine unabhängige Gegenrede (`analysis-challenger`)
geprüft und in der Mechanik **bestätigt**; zwei von ihr benannte Lücken sind mit den
Produktions-Journalen nachträglich geschlossen worden.

## Was die Journale zusätzlich belegen

**(1) Die Reihenfolge Claim → Alarm-Gate ist belegt, nicht nur plausibel.**
Am 14.08. entstand der Claim um 16:00:00.28 UTC (`Generating evening report for trip: KHW 403`),
der Alarm-Lauf erkannte die Änderung erst um 16:00:38.92 und sendete 16:00:40.61 — also
rund 38 s **nach** dem Claim. Der Alarm-Lauf lief 40,5 s über 4 Trips; seine Gate-Prüfung für
KHW kann nicht vor dem Claim gelegen haben.

**(2) Der 14.08. belegt auch Defekt 2, nicht nur Defekt 1.** Der Alarm ging um 16:00:40 raus,
**bevor** der Deploy um 16:00:56 den Dienst stoppte — also im Normalbetrieb, nicht im
Abschaltfenster. Das Muster hat damit zwei vollständige Vorkommen (14.08. und 16.08.), nicht
nur eines.

**(3) Der teuerste Einzelwert: ein legitimer Briefing-Versand dauert real bis zu 5 Minuten.**
Gemessen über 22 Versandläufe des Trips KHW, 05.–15.08.:

| Zeitraum | kürzester | längster |
|---|---|---|
| 05.–10.08. | 54 s | 93 s |
| 11.–15.08. | 218 s | **319 s** (11.08. abends) |

Damit ist die Untergrenze für eine Verwaisungs-Frist **gemessen** und nicht geschätzt: sie
muss deutlich über 319 s liegen.

**(4) Ein bisher unbenannter Nebeneffekt derselben Wurzel.** Der Claim öffnet die Alarm-Sperre
nicht erst nach einem Absturz, sondern **schon in dem Moment, in dem der Versand beginnt** —
und der dauert real 1 bis 5 Minuten. In genau diesem Fenster prüft der parallel laufende
Alarm-Lauf sein Gate. Am 14.08. (16:00:40) und 16.08. (05:01:42) ist deshalb ein separater
Alarm rausgegangen, obwohl #1594 ihn dem Briefing überlassen wollte. Am 15.08. blieb es aus,
weil der Alarm-Lauf zufällig 0,074 s brauchte und damit **vor** dem Claim fertig war
(`trip_alert: Lauf beendet nach 0.074s`, 05:00:00.255 gegen Claim 05:00:00.307). Ob ein
Alarm doppelt rausgeht, hängt heute an einem Wettlauf von Millisekunden.

## Entwurfsentscheidung

Die tragende Einsicht ist bestätigt (`briefing_slots.py:92-93`): **der Doppelversand-Schutz
sitzt in `reserve()`, nicht in `is_recorded()`.** Eine Lockerung von `is_recorded()` fasst den
teuren Pfad also gar nicht an; das Risiko konzentriert sich allein auf die Frage, wann
`reserve()` einen fremden offenen Claim übernehmen darf.

Die Strategie-Bewertung empfahl daraufhin **eine** Bedeutung für `is_recorded()`
(„`outcome` gesetzt"). Diese Empfehlung wird **nicht übernommen** — sie übersieht eine
Kopplung, die der Code selbst als Gefahr benennt: `_collect_due_trips` speist über
`dispatch_orchestrator.py:66-67` die Menge `due_trip_ids_now`, an der
`_process_pending_markers` die #1012-Nachliefer-Marker verfallen lässt. Der Docstring
`trip_report_scheduler.py:531-537` warnt wörtlich, „eine unehrlich lange Liste legte den
Nachliefermechanismus lautlos still". Genau das entstünde: ein Trip mit frisch offenem Claim
stünde wieder in der Liste, `reserve()` verweigerte danach den Versand — und der Marker wäre
verfallen.

**Die beiden Wirkorte stellen tatsächlich zwei verschiedene Fragen:**

| Wirkort | Frage | Richtige Antwort bei offenem Claim |
|---|---|---|
| `_collect_due_trips` (`:553`) | „Wird jetzt ein Versand stattfinden?" | **frisch:** nein (läuft ja gerade) · **verwaist:** ja |
| `trip_briefing_due_at` (`:196`) | „Steht für diesen Slot noch ein Briefing aus?" | **immer ja** — es kam nichts raus |

Daraus folgt der Entwurf (drei Zustände statt zwei, Frist als Modul-Attribut wie
`LOCK_TIMEOUT_SECONDS`):

1. **`is_recorded(...)` = „abgeschlossen"** — Eintrag mit gesetztem `outcome`, plus die
   bestehende Rückwärts-Ableitung aus `briefing_log.json` (unverändert). Aufrufer:
   `trip_briefing_due_at`. Ein offener Claim heißt: Briefing steht aus, die Alarm-Sperre hält.
2. **Eine zweite, ausdrücklich benannte Frage = „abgeschlossen ODER lebendig in Arbeit"** —
   offener Claim jünger als `CLAIM_TTL`. Aufrufer: `_collect_due_trips`. Hält die
   Fälligkeitsliste ehrlich und den Nachliefer-Marker heil.
3. **`reserve(..., moment)` übernimmt** einen offenen Claim, der älter als `CLAIM_TTL` ist
   (neues `recorded_at`, `outcome` bleibt `null`); ein jüngerer blockiert weiter wie heute.
   Punkte 2 und 3 benutzen **dieselbe** interne Regel — Prüfort = Wirkort.

Verworfene Alternative: „verwaist, wenn `recorded_at` in einer früheren Cron-Stunde liegt".
Ein Claim von 12:59:58 gälte zwei Sekunden später als tot — weit unter jeder gemessenen
Versanddauer.

### `CLAIM_TTL`

- **Untergrenze (gemessen):** > 319 s, der längste reale Einzelversand (11.08. abends).
- **Obergrenze (abgeleitet):** < 1 h, der Cron-Abstand (`internal/scheduler/scheduler.go:141`)
  — darüber wirkt die Frist nie, weil der nächste Übernahme-Versuch erst dann stattfindet.
- **Gewählt: 900 s (15 min)** — knapp dreifacher Abstand zum gemessenen Maximum, und da der
  nächste Reserve-Versuch ohnehin erst zur vollen Stunde kommt, verhält sich jeder Wert
  zwischen 10 und 50 Minuten am nächsten Tick identisch. Als Modul-Attribut zur Laufzeit
  lesbar, damit Tests die Frist unterschreiten können.

## Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/briefing_slots.py` | MODIFY | `CLAIM_TTL`; `is_recorded()` = „abgeschlossen"; zweites Prädikat „abgeschlossen oder lebendig"; `reserve(..., moment)` mit Übernahme verwaister Claims |
| `src/services/trip_report_scheduler.py` | MODIFY | `_collect_due_trips` fragt das zweite Prädikat; `_dispatch_due_item` reicht `now_utc` an `reserve()` durch; Kommentar `:191-195` richtigstellen |
| `src/services/dispatch_orchestrator.py` | MODIFY | `now_utc` durch `dispatch_one` an `_dispatch_due_item` reichen |
| `tests/tdd/test_briefing_slot_idempotenz.py` | MODIFY | Outcome-Semantik, TTL-Grenzfall frisch/verwaist, Übernahme |
| `tests/tdd/test_trip_alert_briefing_imminent.py` | MODIFY | Alarm-Sperre hält bei offenem Claim (Defekt 2, Nutzersicht) |
| `docs/specs/modules/fix_1725_faelligkeit_und_idempotenz.md` | MODIFY | Verwaisungs-Regel nachtragen |

## Scope Assessment

- Dateien: 6 (3 Produktiv, 2 Test, 1 Spec)
- Geschätzte LoC: Produktiv ~55–80, Test ~90–140 → **~145–220**, unter dem 250er-Limit,
  aber ohne Reserve. Wird es enger, ist die Kürzung des Nachweises **nicht** der Ausweg —
  dann Rückfrage beim PO.
- Risiko: **MEDIUM** (der Doppelversand-Pfad wird berührt, aber nur um eine Alters-Bedingung
  ergänzt, unter derselben bestehenden Sperre)

## Risiken

1. **Doppelversand bei zu knapper Frist** — durch die Messung (319 s gegen 900 s) entschärft.
2. **Zugestellt, aber nicht vermerkt:** stirbt der Prozess zwischen erfolgreichem Versand und
   `record_outcome()`, wäre der Claim verwaist, obwohl die Mail draußen ist. Gegenmittel ohne
   neues Datenfeld: `briefing_log.json` trägt den Eintrag bereits **vor** dem Anker
   (`trip_report_scheduler.py:1623`) — die Übernahme muss diesen Nachweis prüfen. Der Leser
   dafür existiert schon (`_log_bezeugt_versand`).
3. **Gleichzeitigkeit:** Altersprüfung und Übernahme müssen in **derselben** `_op`-Closure
   unter der bestehenden Sidecar-Sperre liegen, sonst können zwei Läufe denselben verwaisten
   Claim übernehmen.
4. **Bewusste Folge, die der PO kennen muss:** Die Alarm-Sperre hält künftig auch während der
   1–5 Minuten, die ein Versand dauert, und nach einem abgebrochenen Versand bis zum
   Nachhol-Versuch der nächsten Stunde. Eine Änderungsmeldung kann dadurch bis zu einer Stunde
   später kommen — dafür kommt sie im nachgeholten Briefing an, statt dass das Briefing ganz
   ausfällt. Das ist die in ADR-0009/#1594 bereits getroffene Entscheidung („ERSETZT, nicht
   verschluckt"), hier nur konsequent angewendet.
5. **Nicht in diesem Zuschnitt:** der auslösende Deploy-Zeitpunkt (henemm-infra) und der
   Ortsvergleichs-Pfad (#1777, benutzt den Store noch nicht).

## Open Questions

Keine blockierenden. Die Frist ist gemessen begründet, beide Defekte gehören in einen
Zuschnitt (eine halbe Behebung ließe genau das ausfallende Briefing ungefixt).
