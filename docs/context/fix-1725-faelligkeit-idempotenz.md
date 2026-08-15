# Context: fix-1725-faelligkeit-idempotenz

Issue **#1725** — S3 von Epic #1722 (Zeitzonen-Architektur). Setzt **#1724 (S2)** voraus;
S2 ist seit `e21f4f48` live und geschlossen.

## Request Summary

Die Briefing-Fälligkeit wird heute über **Stundengleichheit** entschieden
(`konfigurierte_stunde == trip_lokale_stunde`). Ein Ortstag hat aber nicht immer 24 Stunden:
am Frühjahrs-Umstellungstag fehlt eine Ortsstunde (ein auf 02:00 gestelltes Briefing entfällt
ersatzlos), am Herbsttag existiert sie zweimal (das Briefing geht zweimal raus). Gleichheit
wird ersetzt durch **Fälligkeit + Idempotenz-Schlüssel**: fällig, wenn die Ortsstunde die
konfigurierte erreicht oder überschritten hat **und** für `(trip_id, ortstag, slot)` noch
nichts vermerkt ist; nach Versand wird genau dieser Schlüssel vermerkt.

Der Fehler entsteht **erst durch die Verbesserung aus S2** — vorher war die Rechnung
umstellungs-immun, weil sie in einer festen Zone lief.

## Der Versandpfad — vollständige Kette

| Schritt | Ort |
|---|---|
| Go-Cron `"0 * * * *"`, Job `briefing_dispatch` | `internal/scheduler/scheduler.go:141` |
| → `tripReports()` → `runForAllUsers("trip_reports_hourly", "/api/scheduler/trip-reports")` | `scheduler.go:271,280,190` |
| HTTP-Einstieg Python, `now_utc = datetime.now(timezone.utc)` (ohne `at`-Param) | `api/routers/scheduler.py:26,44` |
| `TripReportSchedulerService(user_id).send_due_reports(now_utc)` | `api/routers/scheduler.py:53-56` |
| → `run_briefing_dispatch("route", user_id, now_utc, settings)` | `src/services/trip_report_scheduler.py:350-352` |
| Strategie-Auflösung `_STRATEGY["route"] → TripDispatchStrategy` | `src/services/dispatch_orchestrator.py:174-177,204` |
| `strategy.collect_due(now_utc)` → **`_collect_due_trips`** | `dispatch_orchestrator.py:59-60` → `trip_report_scheduler.py:354` |
| `strategy.pre_pass(...)` → `_process_pending_markers` | `dispatch_orchestrator.py:62-66` → `trip_report_scheduler.py:389` |
| Schleife `strategy.dispatch_one(item)` → `_send_trip_report_outcome`, 2,0 s Pause zwischen Items | `dispatch_orchestrator.py:68-80,217-218` |
| Kanäle E-Mail/SMS/Premium-SMS/Telegram in **einem** Aufruf, je eigenes `try/except` | `src/services/notification_service.py:309-521` |

**Die heutige Fälligkeitsprüfung** — die zu ersetzende Stelle:

```
if self._get_morning_hour(trip) == self._trip_local_hour(trip, now_utc):   # :372
if self._get_evening_hour(trip) == self._trip_local_hour(trip, now_utc):   # :375
```

`_trip_local_hour` (`:379-387`) = `trip_local_now(trip, now_utc).hour` — derselbe Auflöser,
den der Alarm-Pfad seit #1697 benutzt.

## Outcome-Werte: fünf, und nur einer heißt „gesendet"

`_send_trip_report_outcome` (`trip_report_scheduler.py:871-1303`) gibt zurück:

| Wert | Zeile | Bedeutung |
|---|---|---|
| `no_stage` | :919-921 | keine Etappe am Zieltag — früher Return **vor** jedem Versandversuch |
| `no_weather` | :1028 | Totalausfall Wetterdaten (Schwelle `OUTAGE_WITHHOLD_RATIO = 0.75`, :1004) — früher Return |
| `no_channels` | :1287-1290 | kein Kanal konfiguriert |
| `channels_unreachable` | :1291-1302 | konfiguriert, aber keiner erreicht |
| `sent` | :1303 | Default-Return am Funktionsende |

`result.sent` entsteht als **`sent=bool(sent_channels)`** (`notification_service.py:515`) — „gesendet"
heißt „**mindestens ein** Kanal hat zugestellt", nicht „alle". Gelingt E-Mail und scheitert
Premium-SMS, ist der Outcome `sent`; der Ausfall ist nur am Fehlen in `sent_channels` sichtbar.

**Folge für den Schlüssel:** Es gibt bereits genau **einen** Outcome je
`(trip, report_type, target_date)` — ein Pro-Kanal-Schlüssel würde eine Unterscheidung
einführen, die im übrigen Code nirgends existiert.

## Kandidaten für den Idempotenz-Träger

Es gibt **heute keinen Fälligkeits-Idempotenz-Check überhaupt**. Der einzige Schutz gegen
Doppelversand ist strukturell: der Cron feuert einmal pro Stunde. Ein zweiter Lauf in
derselben Stunde (Neustart, manueller Trigger) hätte heute keinen Schutz.

| Kandidat | Form | Schreibsicherung | Passung |
|---|---|---|---|
| **`briefing_log.json`** (`internal/store/log.go:10-15`, geschrieben `trip_report_scheduler.py:1452-1470`) | `{trip_id, kind, sent_at, channels[]}` — `kind` **ist** der Slot | 🔴 weder atomar (`path.write_text()`, :1470) noch gesperrt | Grundform stimmt, **scheidet aber aus** (s. Analyse): #1007 F001 verbietet Einträge mit `channels=[]` (:1234-1246), weil die Cockpit-Kachel #393 sonst einen Versand vortäuscht — vier der fünf Vermerk-Fälle haben keine Kanäle. Bleibt als **Rückwärts-Ableitung** beim Rollout nützlich |
| `throttle_state.json` (`src/services/throttle_store.py`) | `{scope: {key: iso}}`, zweistufig | ✅ stärkste: `fcntl`-Lock + `tempfile`+`os.replace` (:103-158) | Semantisch fremd — Cooldown-**Fenster** („innerhalb N Minuten"), nicht exakte Slot-Identität. Tripel nur als zusammengesetzter Key-String = Formatbruch |
| `pending_briefings.json` | `{trip_id, report_type, date, slot_hour, failed_segment_ids, attempts, created_at, reason?}` | atomar, aber **kein** Lock | Felder passen, **Semantik nicht**: ein „offene Arbeit"-Marker, der bei Auflösung **verschwindet** — nach erfolgreichem Versand existiert kein Nachweis mehr. Als alleiniger Idempotenz-Träger ungeeignet |

Die Issue-Annahme „die pending marker sind bereits die halbe Miete" trägt damit **nicht**:
sie sind eine Warteschlange offener Arbeit, kein Sende-Protokoll.

**Ergebnis der Analyse: keiner der drei taugt als Träger** — es entsteht ein eigener,
schmaler Speicher (`briefing_slots.json`). Begründung unten unter „Analysis".

Zur Go-Seite: `briefing_log.json` wird von Go **nur gelesen**
(`internal/handler/cockpit.go:21`, `internal/handler/briefing_history.go:25`,
`internal/store/log.go:98`) und in keinem Produktivpfad geschrieben. Eine Schema-Erweiterung
hätte dort also keine Parität erzwungen — `encoding/json` ignoriert unbekannte Felder.

## Zeit-Infrastruktur

- `src/services/trip_day.py`: `trip_tz` (:29), `display_tz` (:45), `anchor_tz` (:55),
  **`trip_local_now`** (:74, seit #1724 — Tag *und* Uhrzeit aus **einer** Zonen-Auflösung),
  `trip_local_today` (:90). Zone via TimezoneFinder (`utils/timezone.py:29-37`), Lazy-Singleton.
- **Fallback bei Auflösungs-Fehlschlag, zwei Ebenen:** `tz_for_coords` → `ZoneInfo("UTC")`
  (`utils/timezone.py:35-37`); `trip_tz` ohne Wegpunkte → importierte `UTC`-Konstante.
- **`local_dt(dt, tz)`** (`utils/timezone.py:81-83`) = `_as_utc(dt).astimezone(tz)`; `_as_utc`
  (:74-78) markiert naive Zeitstempel **erst** explizit als UTC, statt `.astimezone()` die
  Prozess-Zone raten zu lassen.
- `_get_target_date` (`trip_report_scheduler.py:689-713`) liefert bereits den **Ortstag** —
  der `ortstag`-Teil des Schlüssels ist vorhanden, nicht neu zu erfinden.

### ADR-0044 — die Falle, die dieses Issue ausdrücklich nennt

`docs/adr/0044-kalendertage-folgen-der-ortszeit.md:59-67`, wörtlich gemessen:

```
2026-03-29: gleiche tzinfo-Subtraktion=24.0  über UTC=23.0
2026-10-25: gleiche tzinfo-Subtraktion=24.0  über UTC=25.0
```

> „Tragen zwei zeitzonenbehaftete Zeitpunkte dasselbe `tzinfo`-Objekt, rechnet Python auf den
> nackten Wanduhr-Werten und ignoriert den Offset-Wechsel — an jedem Tag 24,0. Beide
> Zeitpunkte müssen erst nach UTC umgerechnet werden, im Projekt über `local_dt(dt, UTC)`."

Ebenda `:46-49`: „Jedes Tagesfenster muss seine Länge **berechnen** statt sie zu setzen. Eine
Signatur mit `hours: int` ist damit falsch."

### ADR-0051 (Status: **Vorgeschlagen**, nicht Akzeptiert)

- **Regel 2:** „Die Zone gehört an die Daten, nicht an den Server."
- **Regel 3:** „Keine Umgebungsuhr. `date.today()`, `datetime.now()` ohne `tz` … sind im
  Produktivcode verboten. ‚Jetzt' wird als Zeitpunkt-Parameter hereingereicht."
- `:89-95` beschreibt den Idempotenz-Schlüssel bereits wörtlich so, wie #1725 ihn verlangt.

## 🔴 Wächter-Fallen beim Anfassen dieser Dateien

`tests/test_output_timezone_guard.py` scannt seit #1723 auch `src/services/**` und `api/**` —
`trip_report_scheduler.py` ist **doppelt** erfasst.

- **Löst aus:** `date.today()` (immer), `datetime.now()` ohne `tz`, `ZoneInfo("<Zone ≠ UTC>")`,
  rohes `x.astimezone(...)`.
- **Löst nicht aus:** `local_dt(...)`/`local_hour(...)` aus `utils.timezone` (Datei ist vom
  Scan ausgenommen, `:97-100`), `datetime.now(tz=...)`, `.utcnow()`, `ZoneInfo("UTC")`.
- **🔴 Ordinal-Falle:** `KNOWN_VIOLATIONS`-Schlüssel sind `pfad::funktion::ordinal` — das
  Ordinal ist die Position **innerhalb der Funktion**. `_send_trip_report_outcome::0` ist
  gelistet (heute `:932`). Wird davor ein weiterer Treffer eingefügt, **verschiebt sich das
  Ordinal des Altbestands, ohne dass ein Test rot wird** — die hinterlegte Begründung
  beschreibt dann die falsche Stelle. Genau das ist in #1723 einmal passiert.

## Test-Muster: Zeit wird hereingereicht, nicht gepatcht

`tests/tdd/test_briefing_faelligkeit_ortszone.py:13-15`, `:87-98` — `_faellig(scheduler, now_utc)`
ruft `_collect_due_trips(now_utc)` mit synthetisch konstruierten Zeitpunkten. `freeze_time`
kommt nur vor, um im **Testcode** einen exakten Zeitpunkt zu erzeugen, der dann explizit
weitergereicht wird (`tests/unit/test_trip_local_today.py:159-162`).

### Der Test, der planmäßig rot wird

`tests/tdd/test_briefing_faelligkeit_ortszone.py:312-348`
(`test_ac7_sommerzeit_luecke_ist_gemessen_nicht_behauptet`) nagelt das heutige Fehlverhalten
fest: `treffer_am(2026-03-29) == 0`, `treffer_am(2026-10-25) == 2`. Er schreitet den Ortstag
korrekt von Ortsmitternacht zu Ortsmitternacht ab. Der Test-Docstring sagt selbst, dass #1725
ihn rot macht und auf das Zielverhalten umzuschreiben hat.

**🔴 Prüfort = Wirkort:** Dieser Test ruft **`_collect_due_trips`**, nicht den Versand. Sitzt
der Idempotenz-Check nur in `_send_trip_report_outcome`, meldet die Sammlung nach der
`>=`-Umstellung ab der konfigurierten Stunde **jede** Stunde bis Mitternacht als fällig, und
dieser Test kann das nicht sehen. Der Check gehört in die Sammel-Phase.

### Was an DST-Tests fehlt

- `tests/unit/test_trip_local_today.py:145-199` prüft nur die **Stabilität des Kalendertags**
  eine Minute vor/nach der Umstellung — nicht die Häufigkeit der Doppelstunde.
- **Kein `fold`-Handling im Repo** (`grep` über `tests/`, `trip_day.py`, `utils/timezone.py`
  ohne Treffer) — die doppelte Herbststunde wird nirgends disambiguiert.
- **Kein Test mit `Australia/Lord_Howe`** — der 24,5-h-Fall existiert nur als Text in ADRs und
  einem Docstring (`trip_command_processor.py:204-206`).

## 🔴 Die Tick-Zustellung hat denselben Fehler — eine Ebene tiefer

Nachgemessen am Bibliothekscode, nicht angenommen.

- Der Go-Cron läuft in **einer prozessweiten Zone**: `cron.New(cron.WithLocation(loc))`
  (`internal/scheduler/scheduler.go:112`), `loc = time.LoadLocation(cfg.SchedulerTimezone)`
  (`:106`), `SchedulerTimezone` = `GZ_SCHEDULER_TIMEZONE`, **Default `Europe/Vienna`**
  (`internal/config/config.go:20,52`). Im Worktree ist die Variable nirgends gesetzt.
- `github.com/robfig/cron/v3 v3.0.1` (`go.mod:13`) sagt in der eigenen Doku
  (`doc.go:169-170`): *„Be aware that jobs scheduled during daylight-savings leap-ahead
  transitions will not be run!"* Die eigene Testsuite der Bibliothek belegt es für einen
  stündlichen Job (`spec_test.go:117-121`, America/New_York 2012-03-11):
  `01:00-0500` → next `03:00-0400` — **der 02:00-Slot fällt ersatzlos aus**. Umgekehrt
  (`spec_test.go:139-141`) feuert er an der Rückstellung **zweimal**. Der Mechanismus in
  `spec.go` (`Next()` über echte `time.Duration`-Addition) ist zonenunabhängig.

**Folge:** An der Wiener Frühjahrs-Umstellung fehlt **eine Tick-Stunde für alle Nutzer
weltweit** — auch für einen Trip in Auckland, wo an dem Tag gar keine Umstellung ist. Der
Fehler ist damit nicht auf Trips in DST-Zonen beschränkt, wie das Issue annimmt.

Genau das repariert die vorgeschlagene Lösung mit: Der nächste Tick sieht den Trip weiterhin
als fällig (`ortsstunde >= konfigurierte_stunde`, kein Vermerk) und holt nach — **aber nur,
wenn das Nachhol-Fenster mindestens eine Stunde zulässt.** Das ist ein starkes fachliches
Argument in der offenen Frage 1.

**Weitere Befunde derselben Ebene:**

- **Go schickt keinen Zeitpunkt mit.** `triggerEndpointForUser` postet
  `pythonURL + path + "?user_id=" + uid` (`scheduler.go:546-547`); der Parameter `at` in
  `api/routers/scheduler.py:26` existiert, wird von Go aber nie befüllt — Python nimmt seine
  **Ankunftszeit** (`:43-44`), nicht den Solltermin. Für eine `>=`-Prüfung ist das
  unproblematisch, für die heutige `==`-Prüfung ist jede Verzögerung über die Stundengrenze
  ein verlorener Slot.
- **Kein Retry, kein Nachtrag.** Genau ein `client.Post` (`scheduler.go:547`), kein
  Backoff-Loop. Fehler landen als `status:"error"` in `s.lastRuns` (`:519-523`); der Tick ist
  weg. Overlap-Skip lässt `lastRuns[jobID]` **bewusst unverändert** (`:497`).
- **Neustart holt nichts nach.** `lastRuns`/`overlapState` sind In-Memory (`:104-165`);
  `cron.run()` berechnet `entry.Next` frisch ab dem aktuellen `now`.
- **`last_run` taugt nicht zur Lückenerkennung.** `Status()` (`:676-736`) liest nur
  `cron.Entries()` und die In-Memory-Map — keine Persistenz. Ein übersprungener Slot ist
  darüber nicht von „war nicht fällig" unterscheidbar.

### Andere Einstiegspunkte, die denselben Vermerk berühren

| Pfad | Ort | Umgeht die Fälligkeitsprüfung |
|---|---|---|
| Manueller Test-Versand `POST /api/scheduler/trips/{id}/send` | `api/routers/scheduler.py:204-205,230-232` | ja (#695) |
| Inbound-Kommando „heute"/„morgen" → `send_on_demand_report` | `src/services/trip_command_processor.py:575` | ja |
| Inbound-Kommando „report" → `send_test_report` | `src/services/trip_command_processor.py:1018` | ja |
| Legacy-CLI `--report morning/evening` | `src/app/cli.py` | eigener Pfad, laut CLAUDE.md kein Produktivpfad |

**Fachliche Konsequenz:** Ein per SMS angefordertes „heute" darf dem Nutzer **nicht** sein
reguläres Briefing wegnehmen — On-Demand-Versand darf also keinen Vermerk setzen. Das ist in
der Spec zu entscheiden, nicht implizit zu lassen.

## Compare-Pfad: getrennt, aber über ein gemeinsames Skelett erreichbar

`CompareDispatchStrategy` (`dispatch_orchestrator.py:86-171`) hat eine **eigene**
Fälligkeitsprüfung in `src/services/compare_slot_scheduler.py:102-156` (`presets_due_for_hour`)
— mit derselben Stundengleichheit (`:152,154`) und der festen Zone
`NOCH_NICHT_ORTSZEIT_SIEHE_1726 = "Europe/Vienna"` (`dispatch_orchestrator.py:117,134`).

Geteilt ist nur das Skelett in `dispatch_orchestrator.py`: Strategie-Dispatch, `smtp_guard`,
`pre_pass`-Hook, die `due`-Schleife, das `(sent, failed)`-Format.

**🔴 Abgrenzung:** Änderungen in `trip_report_scheduler.py` berühren Compare strukturell
nicht. Wandert der Idempotenz-Check dagegen als neuer Hook **ins Skelett** (etwa ein
`already_sent(item)` vor `dispatch_one`), verändert er den Compare-Pfad automatisch mit —
vor #1726 und ohne Nachweis. AC-8 von #1724 verlangt für Compare bit-identisches Verhalten.

## Berührungspunkt mit offener Arbeit: #1557

**#1557 ist offen:** Der Versand meldet `sent`, obwohl kein Wetter verfügbar war
(erwartet: `no_weather` / HTTP 422). Ein Vermerk, der an `outcome == "sent"` hängt, hakt in
diesem Fall ein inhaltlich leeres Briefing als erledigt ab — und der Nachholmechanismus,
der genau dafür gedacht ist, greift nie. Die Spec muss das auflösen oder ausdrücklich
abgrenzen.

Immerhin: `_append_briefing_log` wird bereits **nur** bei `result.sent` und konfiguriertem
Kanal geschrieben (`:1237-1246`) — das Sende-Protokoll ist an dieser Stelle ehrlicher als der
Outcome-String.

## Dependencies

- **Upstream:** `trip_day.trip_local_now`/`trip_local_today`, `utils.timezone.local_dt`,
  `_get_target_date`, `load_all_trips`, `get_data_dir`, `NotificationService.send_trip_report`.
- **Downstream:** `dispatch_orchestrator.run_briefing_dispatch` (auch Compare),
  `api/routers/scheduler.py`, Go-Seite `internal/store/log.go` +
  `internal/handler/briefing_history.go` (liest `briefing_log.json` — **Schema-Parität nötig,
  wenn ein Feld hinzukommt**), `internal/store/pending_briefings.go`.

## Existing Specs & ADRs

| Dokument | Bezug |
|---|---|
| `docs/specs/modules/fix_1724_faelligkeit_in_der_ortszone.md` | S2, direkte Vorlage; AC-7 ist der Test, der hier rot wird; AC-8 (Compare bit-identisch), AC-9 (ein `now_utc` für den ganzen Lauf) |
| `docs/adr/0051-drei-zeitbegriffe-zone-an-den-daten.md` | Regeln 1–3; beschreibt den Schlüssel bereits wörtlich; Status **Vorgeschlagen** |
| `docs/adr/0044-kalendertage-folgen-der-ortszeit.md` | Ortstag-Definition, die `tzinfo`-Falle, „Tagesfenster berechnen statt setzen" |
| `docs/analysis/zeitzonen-architektur-2026-08.md:132-157` | Herleitung der Scheibe, Umstellungstag-Messtabelle |
| `docs/specs/modules/fix_1723_zeitzonen_waechter_entscheidung.md` | Wächter-Fläche und `KNOWN_VIOLATIONS`-Mechanik |

## Risks & Considerations

1. **`>=` ohne wirksamen Vermerk = stündlicher Serienversand** an echte Empfänger, inklusive
   kostenpflichtiger Premium-SMS. Das ist die gefährlichste Änderung des Vorhabens; der
   Vermerk muss **vor** der Umstellung stehen und in der Sammel-Phase greifen.
2. **Prüfort = Wirkort** — siehe oben: Check in `_collect_due_trips`, nicht nur im Versand.
3. **Nachhol-Fenster ist fachlich ungeklärt** (Issue lässt es offen). Ein Briefing, das um
   23:00 Ortszeit eintrifft, ist wertlos bis irreführend.
4. **Ein Vermerk-Speicher muss atomar und gesperrt schreiben** — Vorbild `throttle_store`,
   aber mit umgekehrter Fehlerrichtung (s. Analyse: fail-closed statt fail-open).
5. **Ordinal-Verschiebung im Zeitzonen-Wächter** (s.o.) — still, kein Test wird rot.
6. **Compare-Pfad darf sich nicht mitverändern** (#1726, AC-8 aus #1724).
7. 🔴 **`_process_pending_markers` ist der eigentliche Sprengsatz.**
   `trip_report_scheduler.py:445-448` räumt den Nachliefer-Marker weg, sobald der Trip in
   `due_trip_ids_now` steht. Mit `>=` und ohne wirksamen Filter steht dort **jede Stunde**
   jeder Trip — der gesamte #1012-Nachliefermechanismus wird stillgelegt, ohne dass ein
   Versand sichtbar schiefgeht. Erst in der Analyse gefunden.
8. **Kein `fold`-Handling im Repo** — die doppelte Herbststunde ist bisher nirgends
   disambiguiert; der Nachweis muss die Stundenhäufigkeit zählen, nicht Zeilen.
9. **Mandantentrennung:** `get_data_dir(user_id="default")` und
   `TripReportSchedulerService(user_id="default")` tragen beide einen `"default"`-Default —
   jeder neue Speicherzugriff muss die echte `user_id` durchreichen.

10. **Der Tick selbst fällt an Umstellungstagen aus** (s.o.) — für **alle** Nutzer, nicht nur
    für Trips in DST-Zonen. Die Lösung deckt das mit ab, aber nur bei ausreichendem
    Nachhol-Fenster.
11. **Andere Einstiegspunkte** (Test-Versand, Inbound-Kommandos) umgehen die
    Fälligkeitsprüfung heute vollständig — ihr Verhältnis zum Vermerk ist zu entscheiden.

## Offene Fragen für die Spec (PO-Entscheid)

1. **Wie weit darf nachgeholt werden?** Bis Ende des Ortstags, N Stunden, oder gar nicht?
   Das Tick-Ergebnis oben verschiebt die Antwort: mindestens eine Stunde ist nötig, damit der
   an Umstellungstagen ausfallende Cron-Tick überhaupt aufgefangen wird.
2. **Welcher Outcome erzeugt den Vermerk?** Nur `sent` — oder auch `no_stage` (dauerhaft
   nichts zu senden) und `no_channels` (Konfigurationsfrage, kein Datenproblem)?
3. **Trägt `briefing_log.json` den Vermerk** (ein Feld mehr, Go-Parität, Härtung des
   Schreibmusters) oder entsteht ein eigener Speicher?
4. **Setzt ein On-Demand-Versand („heute" per SMS, Test-Versand) den Vermerk?** Vorschlag:
   nein — sonst nimmt eine Nutzeranfrage dem Nutzer sein reguläres Briefing weg.

---

# Analysis

**Typ:** Bug (Label `bug`, `area:trips`). Der Fehler entsteht durch die Verbesserung aus S2.

## Technischer Ansatz

### Der Check sitzt in der Sammel-Phase

`_collect_due_trips(self, now_utc) -> List[Tuple[Trip, str, date]]` — das dritte Element ist
der **Ortstag des Laufs** (`trip_local_today(trip, now_utc)`), ausdrücklich **nicht**
`target_date` (bei `evening` ist das Ortstag + 1, `trip_report_scheduler.py:709-713`).

Drei unabhängige Gründe gegen einen Check erst im Versand:

1. Prüfort = Wirkort — der bestehende Test ruft `_collect_due_trips`
   (`tests/tdd/test_briefing_faelligkeit_ortszone.py:93`).
2. `run_briefing_dispatch` schläft **2,0 s je Element** (`dispatch_orchestrator.py:216-219`);
   eine unehrliche `due`-Liste kostet reale Laufzeit.
3. `pre_pass` konsumiert `due_trip_ids_now` (`dispatch_orchestrator.py:64-66`) → Risiko 7.

Nebenbefund zu AC-9: `_send_trip_report_outcome` liest bei `:905` seine **eigene** Uhr. Bei
2 s/Element und Mitternachtsnähe kann der dort abgeleitete Tag vom Sammelzeitpunkt abweichen.
Wird der Schlüssel im Sammellauf gebildet und mitgereicht, ist die Drift für die Idempotenz
wirkungslos. `:905` selbst bleibt unangetastet (gehört zu #1726).

### Eigener Speicher: `data/users/<uid>/briefing_slots.json`

Schema: `{"entries": [{"trip_id", "slot", "local_day", "recorded_at", "outcome"}]}`

`briefing_log.json` scheidet aus, weil #1007 F001 Einträge mit `channels=[]` verbietet
(`:1234-1246`) — sonst täuscht die Cockpit-Kachel #393 einen Versand vor. Vier der fünf
Vermerk-Fälle haben keine Kanäle. Es sind **zwei verschiedene Aussagen**: „wurde zugestellt"
(Protokoll) gegen „Slot ist abgearbeitet" (Quittung).

- **Schreibmuster** nach `throttle_store._update()` (`:116-158`): `fcntl` über
  `services.file_lock.acquire_exclusive` (`file_lock.py:28`), `tempfile` + `os.replace`,
  Sperre auf einer Sidecar-Datei.
- 🔴 **Aber mit umgekehrter Fehlerrichtung.** `throttle_store` ist bei Sperren-Timeout
  **fail-open** (`:139-150`). Für eine Idempotenz-Quittung heißt „nicht geschrieben"
  = Doppelversand in der nächsten Stunde, inklusive kostenpflichtiger Premium-SMS. Der neue
  Speicher ist **fail-closed**: gelingt die Reservierung nicht, wird nicht gesendet.
- **reserve-then-release:** Vermerk **vor** dem Versand schreiben, nur bei
  `channels_unreachable` oder Ausnahme zurücknehmen. Stirbt der Prozess mitten im Versand,
  bleibt der Vermerk stehen — nie doppelt.
- **Keine Migration** (Datei existiert noch nicht), stattdessen **Rückwärts-Ableitung beim
  Lesen**: fehlt ein Vermerk, gilt der Slot als erledigt, wenn `briefing_log.json` einen
  Eintrag mit passendem `trip_id` + `kind` trägt, dessen `sent_at` in den Ortstag fällt.
  Beseitigt den einzigen echten Doppelversand-Fall: den Deploy mitten im Nachhol-Fenster.

### Nachhol-Fenster: 3 Stunden

Bedingung: `konfigurierte_stunde <= ortsstunde < konfigurierte_stunde + 3`.

| Option | Trade-off |
|---|---|
| bis Ende des Ortstags | Fängt jeden Ausfall — aber Morgen-Briefing um 23:00. Schlimmer: ein neu angelegter oder aus `paused_until` (`:671-677`) zurückkehrender Trip feuert **rückwirkend**, weil `_get_active_trips` nur die Etappe prüft (`:656-657`) |
| **N = 3 Stunden** | Deckt den ausfallenden Cron-Tick (1 h) mit Reserve für einen gescheiterten HTTP-Post ohne Retry (`scheduler.go:547`). Rückwirkendes Feuern strukturell ausgeschlossen. Eine Konstante, in beide Richtungen testbar |
| bis zum nächsten Slot | Bei nur aktiviertem Morgen-Slot degeneriert es zur ersten Option — zwei Slot-Konfigurationen, zwei Verhalten |

Eine Deckelung am Tagesende erübrigt sich: für Slot 22 sind es die Ortsstunden 22 und 23; ab
Ortsmitternacht wechselt der Ortstag und `0 >= 22` ist falsch. **DST fällt korrekt aus:**
Frühjahr, Slot 02:00 → Ortsstunde 03 erfüllt `3 >= 2 and 3 < 5` → genau einmal. Herbst,
Ortsstunde 02 doppelt → erstes Vorkommen vermerkt, zweites gefiltert → genau einmal.

### Vermerk je Outcome

| Outcome | Vermerk | Begründung |
|---|---|---|
| `sent` (`:1303`) | **ja** | zugestellt |
| `no_stage` (`:921`) | **ja** | nichts zu senden; Wiederholen ändert nichts |
| `no_weather` (`:1028`) | **ja** | 🔴 **Umkehrung der ursprünglichen Annahme.** Ohne Vermerk: stündliche „keine Daten"-Hinweis-Mail (`:1010`), stündlicher voller Wetterabruf (Kontingent #1329) — und der #1012-Marker wird jede Stunde weggeräumt (`:445-448`). Die Nachholung für diesen Fall **existiert bereits** und ist getestet (`:470-497`): der Marker prüft stündlich, ob die Daten da sind, und liefert mit Präfix nach. Zwei konkurrierende Wiederholpfade wären der Fehler |
| `no_channels` (`:1287-1290`) | **ja** | Konfigurationszustand, ändert sich nicht binnen Stunden. Der Wetterabruf läuft **vor** dieser Prüfung — ohne Vermerk verbrennt das dreimal Kontingent für nichts |
| `channels_unreachable` (`:1291-1302`) | **nein** | genau der Nachholfall. Kein Doppelversand möglich: per Definition hat niemand etwas bekommen (`sent = bool(sent_channels)`) |
| Ausnahme (`:1204-1209`) | **nein** | fällt durch reserve-then-release automatisch heraus |

**Gegen #1557 indifferent:** Meldet der Versand fälschlich `sent` statt `no_weather`, führen
beide Zweige zum selben Ergebnis — Vermerk gesetzt, Nachholung über den Pending-Marker. Eine
Regel „Vermerk nur bei `sent`" wäre es nicht: sie hakte unter #1557 ein inhaltsleeres
Briefing als erledigt ab **und** schriebe keinen Marker.

### Compare bleibt unberührt

**Sicher:** `trip_report_scheduler.py` · `TripDispatchStrategy`
(`dispatch_orchestrator.py:35-83`) · neues Modul `briefing_slots.py`.

**Verboten:** jeder neue Hook in `run_briefing_dispatch` (`:180-221`), insbesondere ein
`already_sent(item)` vor `dispatch_one` (`:212`) · eine gemeinsame Basisklasse für beide
Strategien · `compare_slot_scheduler.presets_due_for_hour` (`:102-156`) — das ist #1726.

Nötig sind exakt zwei Zeilen in `dispatch_orchestrator.py`, beide **innerhalb** von
`TripDispatchStrategy`: `pre_pass` (`:65`, 3-Tupel-Entpackung) und `dispatch_one` (`:74`).

### On-Demand-Pfade: weder lesen noch schreiben

Test-Versand (`api/routers/scheduler.py:230`), „heute"/„morgen"
(`trip_report_scheduler.py:822`), „report" (`:774`), Legacy-CLI ignorieren den Vermerk
vollständig — nicht schreiben (sonst nimmt eine Nutzeranfrage das reguläre Briefing weg),
nicht lesen (sonst ist der Test-Knopf nach dem regulären Versand tot).

**Kein Flag nötig:** Sitzt der Vermerk in einem neuen Wrapper `_dispatch_due_item()`, der nur
von `TripDispatchStrategy.dispatch_one` gerufen wird, entsteht die Trennung durch den
**Aufrufer**.

## Affected Files

| Datei | Art | Produktiv-LoC |
|---|---|---|
| `src/services/briefing_slots.py` | CREATE | ~110 |
| `src/services/trip_report_scheduler.py` | MODIFY | ~55 |
| `src/services/dispatch_orchestrator.py` | MODIFY | ~6 |
| `tests/tdd/test_briefing_slot_idempotenz.py` | CREATE | zählt nicht |
| `tests/tdd/test_briefing_faelligkeit_ortszone.py` | MODIFY (AC-7 umschreiben) | zählt nicht |

**Summe ≈ 170 / 250 LoC.** Reicht, aber nicht komfortabel. Schnittkante bei Überlauf:
Retention/Prune (~20 LoC) in eine zweite Scheibe. **Nicht** herausschneiden:
Rückwärts-Ableitung und fail-closed-Sperre.

**Kein `KNOWN_VIOLATIONS`-Eintrag, keine Ordinal-Verschiebung:** `_collect_due_trips` bekommt
nur `trip_local_now`/`trip_local_today` (ausgenommen), der Wrapper ist ein eigener
Funktionsraum, und `briefing_slots.py` bleibt sauber, solange es `datetime.now(tz=...)`
benutzt und kein `ZoneInfo("<Zone>")`/rohes `.astimezone()`.

## Risk Level: HIGH — entschärft durch die Schnittführung

**Der gefährliche Zustand `>=` ohne wirksamen Vermerk wird durch zwei Commits in einem PR
unerreichbar:**

- **Commit A:** neuer Speicher + Rückwärts-Ableitung + Vermerk wird geschrieben und gefiltert
  — **Fälligkeit bleibt `==`**. Verhaltensneutral, weil ein Slot bei `==` ohnehin genau
  einmal feuert; der Filter ist ein No-op. Der Schreibpfad ist danach bewiesen.
- **Commit B:** `==` → `>=` + 3-h-Fenster (`:372,375`).

Jeder Zwischenstand ist auslieferbar; Revert oder Bisect landet nie im gefährlichen Zustand.

Weitere Risiken:

- **`skip_next` wird in `_get_active_trips` (`:678-683`) bei jedem Sammellauf konsumiert**,
  unabhängig von der Fälligkeit. Bleibt unverändert, **solange der Filter nach
  `_get_active_trips` sitzt**. Wer ihn zum Sparen davorzieht, ändert `skip_next` still mit.
- **Kontingent:** `channels_unreachable` zieht bis zu drei Wetterabrufe statt einem (#1329).
  Bewusst, begrenzt.
- **`data/` muss untracked bleiben** — die neue Datei nie committen.

## Nachweis-Strategie

Neue Datei `tests/tdd/test_briefing_slot_idempotenz.py` (Verhaltensname, nicht Issue-Nummer —
`test_naming_gate.py` blockt sonst). Zeit durchgehend als Parameter.

🔴 **Die Falle vorweg:** Bei funktionierendem Vermerk liefert **jede** Fensterbreite an einem
normalen Tag genau einen Treffer. Ein Test, der nur Treffer zählt, kann die Fensterbreite
**nicht sehen** — sie ist nur an einem ausgefallenen Tick beobachtbar (T4).

| # | Testfall | Verfälschung, die ihn rot macht |
|---|---|---|
| T1 | Europe/Paris, `morning=02:00`, 2026-03-29, Ortstag abgeschritten → **genau 1** | `>=` zurück auf `==` → 0 |
| T2 | dito 2026-10-25 (Doppelstunde) → **genau 1** | Vermerk-Filter entfernen → 2 |
| T3 | Normaler Tag, **jede einzelne Ortsstunde** gezählt → nur Stunde 07 trifft | Fälligkeit auf `<=` drehen → 8 Treffer |
| **T4** | **Tick-Ausfall:** Stunde H auslassen, dann H+1 → fällig; H+3 → nicht fällig | Fenster 3→1 macht Teil 1 rot, 3→„bis Tagesende" macht Teil 2 rot. **Einziger Test, der die Fensterbreite in beide Richtungen festnagelt** |
| T5 | `morning=07:00` **und** `evening=07:00` → beide fällig in derselben Stunde | `slot` aus dem Schlüssel entfernen → nur einer |
| T6 | Zwei aufeinanderfolgende Ortstage → an beiden fällig | `local_day` aus dem Schlüssel entfernen → Tag 2 stumm |
| T7 | Zwei Trips, gleiche Zone, gleiche Stunde → beide fällig | `trip_id` aus dem Schlüssel entfernen → nur einer |
| T8 | Outcome-Matrix: vier setzen Vermerk, `channels_unreachable` nicht → nächste Stunde erneut fällig | `channels_unreachable` in die Vermerk-Menge schieben → rot |
| T9 | `briefing_slots.json` fehlt, `briefing_log.json` trägt passenden Eintrag im Ortstag → **nicht** fällig | Rückwärts-Ableitung entfernen → fällig (Doppelversand beim Deploy) |
| T10 | Trip mit Etappe heute, `morning=07:00`, erstmals um Ortsstunde 20 ausgewertet → **nicht** fällig | Fenster → „bis Tagesende" → fällig |
| **T11** | `CompareDispatchStrategy.collect_due` über 24 h unverändert (AC-8 aus #1724) | Filter ins geteilte Skelett verschieben → Compare-Zahl ändert sich |
| **T12** | Nach `send_on_demand_report` ist der reguläre Slot zur Stunde H **weiterhin** fällig | Vermerk in `_send_trip_report_outcome` statt in den Wrapper → rot |
| T13 | Sperre nicht erhältlich → **kein** Versand statt Versand ohne Vermerk | fail-open wie `throttle_store:139-150` → rot |
| T14 | `Australia/Lord_Howe` (24,5 h): Ortsstundenfolge ohne Loch und ohne Dopplung → unauffällig | schließt die notierte Repo-Lücke |

**Ausdrücklich markierte Lücke — T13:** ein mockfreier Aufbau (gehaltener `flock`-fd im
selben Prozess, verkürztes `LOCK_TIMEOUT_SECONDS`) gilt als machbar, ist aber **nicht
verifiziert**. Falls teuer, trotzdem als Kern-Test bauen — die Fehlerrichtung ist die
sicherheitskritischste Einzelentscheidung des Vorhabens.

**`fold` wird nicht gebraucht:** Es wird nie eine mehrdeutige Wanduhrzeit konstruiert; die
Ortsstunde entsteht immer aus einem eindeutigen UTC-Zeitpunkt (`trip_day.py:74`). Die
Doppelstunde erscheint als zwei unterscheidbare UTC-Zeitpunkte und wird vom Vermerk getrennt.

## Umsetzungsreihenfolge

1. Spec + PO-Freigabe (drei Entscheidungen: Fenster 3 h, Outcome-Matrix, On-Demand)
2. RED: T1–T14; `test_briefing_faelligkeit_ortszone.py:312-348` auf 1/1 statt 0/2 umschreiben
3. Commit A (GREEN, verhaltensneutral), Fälligkeit bleibt `==`
4. Commit B: `==` → `>=` + `NACHHOL_FENSTER_STUNDEN = 3`
5. Adversary mit Pflichtmutationen: Fenster 3→1 und 3→24 · Schlüssel um je ein Glied kürzen ·
   Filter ins geteilte Skelett verschieben · Vermerk nach `_send_trip_report_outcome` verlegen
6. Ein PR, zwei Commits, A vor B
