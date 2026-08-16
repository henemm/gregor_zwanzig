# Context: fix-1912-scheduler-briefing-timeout

Issue: #1912 — Go-Scheduler meldet Trip-Briefing-Totalausfall (#1346), obwohl der Versand
erfolgreich war. Aufgenommen 2026-08-16.

## Request Summary

Der Go-Scheduler ruft `/api/scheduler/trip-reports` synchron im Python-Core auf und bricht
nach 120 s mit `context deadline exceeded` ab. Der Python-Prozess läuft unbeeindruckt weiter
und verschickt das Briefing erfolgreich — der Scheduler wertet seinen eigenen Timeout
trotzdem als Fehlschlag, setzt `trip_reports_hourly` auf `status: error` und feuert den
MQ-Alarm „Trip-Briefing-Totalausfall (#1346)" mit `priority=high` an `infra`.

Gemessen am 2026-08-16: Generierung 18:00:00 → 18:04:38 = **278 s** bei 4 Trips / 1 Nutzer.
Timeout-Alarm um 18:02:00, erfolgreicher Versand um 18:04:38.

## Related Files

| Datei | Relevanz |
|---|---|
| `internal/scheduler/scheduler.go:115` | **Der Defekt.** `client: &http.Client{Timeout: 120 * time.Second}` |
| `internal/scheduler/scheduler.go:271-304` | `tripReports()` — ok→error-Flanke, löst den #1346-MQ-Alarm aus |
| `internal/scheduler/scheduler.go:190-230` | `runForAllUsers()` — Schleife über Nutzer, Rangfolge error > partial > ok (#1447 S2a) |
| `internal/scheduler/scheduler.go:481-510` | `recordRun()` — setzt `lastRuns[jobID].Status`, trägt die Overlap-Sperre |
| `internal/scheduler/briefing_health.go` | **Vorbild:** liest Diagnosedaten direkt vom Dateisystem, nicht über HTTP |
| `internal/store/store.go:3-11` | `Store` — user-scoped JSON-Zugriff unter `DataDir`; der Scheduler hält bereits einen |
| `src/services/briefing_slots.py:197-209` | `record_outcome()` — schreibt `outcome` **nach** dem Versandversuch |
| `src/services/briefing_slots.py:130-176` | Claim-Reservierung, Verwaisten-Übernahme (#1897) |
| `internal/handler/proxy.go:277` | Präzedenz #1756: 120 s → 300 s im Sofortversand-Pfad |
| `internal/scheduler/scheduler_test.go` | Testmuster: `httptest`-Server + injizierbarer `notifier` |

## Kernbefunde der Recherche

### 1. Der Slot taugt als Positivkontrolle — nachgemessen, nicht angenommen

Die entscheidende Frage war, ob `outcome` **vor** oder **nach** dem Versand gesetzt wird. Ein
Vorab-Vermerk wäre als Erfolgsnachweis wertlos.

`record_outcome()` (`src/services/briefing_slots.py:197-209`) wird nach dem Versandversuch
gerufen und schreibt den Ausgang per Read-Modify-Write. Beim Lauf-Start entsteht lediglich ein
**Claim** mit `outcome: null` (`briefing_slots.py:153-176`). Ein `outcome: "sent"` ist damit
echter Erfolgsnachweis.

Der Mechanismus stammt aus #1897 und behandelt verwaiste Claims bereits: stirbt der Prozess
zwischen Versand und `record_outcome`, schließt `_log_traegt_versand()` den Claim aus
`briefing_log.json` nachträglich mit `sent` ab (`briefing_slots.py:162-164`).

### 2. Es braucht KEINEN neuen HTTP-Endpunkt

Ursprüngliche Annahme im Intake war, dass ein Abfrage-Endpunkt im Python-Core gebaut werden
muss — `grep` über `api/` nach `briefing_slots|briefing-slots|briefing_health` liefert nichts.

Das ist aber der falsche Weg: `internal/scheduler/briefing_health.go` zeigt, dass der
Go-Scheduler Diagnosedaten **direkt vom Dateisystem** liest (`data/diagnostics/openmeteo_calls.jsonl`,
geschrieben von `src/providers/call_log.py`) und dafür `internal/store` benutzt. Derselbe Weg
steht für `briefing_slots.json` offen. Go liest die Datei heute noch nicht — `grep -rn
"briefing_slots" internal/ --include="*.go"` ist leer.

**Folge für den Zuschnitt:** reiner Go-Anteil, kein Python-Anteil, deutlich weniger LoC als im
Intake veranschlagt.

### 3. Der 120s-Timeout ist strukturell zu kurz, nicht nur knapp

`internal/handler/proxy.go:277` trägt seit #1756 (AC-8) 300 s mit dem Kommentar: *„der
reguläre Erfolgsfall (vollständiger Mehrtages-Ausblick) braucht 3-4 Minuten."* Drei bis vier
Minuten sind dort also der **Normalfall**. Der Scheduler wartet 120 s — er war nie lang genug,
der Fehlalarm war nur eine Frage der Trip-Anzahl.

### 4. Ein Client, drei Jobs

`s.client` (Zeile 115) wird an drei Stellen benutzt: `scheduler.go:415`, `:547`, `:594`. Eine
Timeout-Änderung wirkt daher auf Trip-Reports **und** Alert-Checks **und** Compare-Presets.
Das ist kein Unfall, sondern muss bewusst entschieden und in der Spec benannt werden.
Daneben ein zweiter, unabhängiger Client mit 5 s (`scheduler.go:618`).

### 5. Was der #1346-Wachhund eigentlich fangen soll

Laut Kommentar (`scheduler.go:265-270`): *„ein Totalausfall (alle Touren scheitern am
Wetterabruf) muss aktiv an infra gemeldet werden statt still zu bleiben, weil der Heartbeat
allein den Ausfall nicht mehr sichtbar macht."*

Ein abgelaufener Client-Timeout ist **nicht** dieser Fall. Der Wachhund wurde also nicht
falsch gebaut, er bekommt nur ein Ereignis vorgesetzt, für das er nie gedacht war.

## Existing Patterns

- **Direktes Lesen der Datenwurzel aus Go** — `briefing_health.go`, über `internal/store`
- **Edge-Trigger für MQ-Alarme** — `tripReports()`, Vorbild `dataWriteSelftest()`; Alarm nur
  auf der ok→error-Flanke, Recovery-Notiz auf error→ok
- **Rangfolge bei Mehr-Nutzer-Läufen** — error > partial > ok (#1447 S2a, `scheduler.go:214-217`)
- **Testbarkeit** — `httptest`-Server für den Python-Core, `sched.notifier` als Funktionsfeld
  injizierbar (`scheduler_test.go:339, 368, 400, 428`). Ein RED-Test ist ohne Netz machbar.

## Dependencies

- **Upstream:** `internal/store` (Nutzerliste via `ListUserIDs()`, user-scoped Dateizugriff),
  `internal/notify/mq.go` (MQ-Versand), Python-Core über HTTP
- **Downstream:** `/api/scheduler/status` (Job-Status je Job), MQ-Alarme an `infra`,
  BetterStack-Heartbeats

## Risks & Considerations

- **🔴 Der Wachhund darf nicht blind werden.** Die Regel muss lauten: *Entwarnung nur mit
  Positivkontrolle.* Kein nachweisbares `sent`, Slot-Datei nicht lesbar, Slot unbekannt →
  Alarm bleibt. Nur ein positiv belegtes `sent` für **diesen** Slot und **diesen** Ortstag
  darf unterdrücken. Die Mutation, die kein Test fangen darf: „unterdrückt auch ohne `sent`".
- **Timeout-Anhebung allein reicht nicht.** 278 s bei 4 Trips / 1 Nutzer; das Produkt ist
  mandantenfähig. 300 s verschieben die Schwelle, sie beseitigen den Fehlalarm nicht.
- **Ortstag-Falle.** Der Slot ist nach **Ortstag** geschlüsselt (`evening/2026-08-16`), der
  Scheduler denkt in Serverzeit. Ein Vergleich über den falschen Tag findet nichts und würde
  fälschlich alarmieren (verwandt: #1697).
- **Mehr-Nutzer-Fall.** `runForAllUsers` bricht nicht bei einem Timeout ab; die Positivkontrolle
  muss je Nutzer und je Trip erfolgen, nicht global.
- **Die Timeout-Konstante ist dreifach verstreut** (`scheduler.go:115`, `proxy.go:108`,
  `compare_preset.go:676` mit je 120 s, `proxy.go:277` mit 300 s). Eine gemeinsame Quelle wäre
  sauberer — gehört aber als Nebenbefund in #1199, nicht in diese Scheibe.
- **Ops-Nachtrag:** MQ-Nachricht 65181 an `infra` ist der Fehlalarm vom 2026-08-16 18:02 und
  steht noch offen; nach dem Fix abhaken.

## Abgrenzung

Die Wirkung des #1897-Fixes steht nicht in Frage — Reihenfolge (Briefing vor Alarm) und
`outcome`-Verbuchung waren am Abend des 2026-08-16 korrekt.

---

# Analysis

## Type

**Bug** — nutzersichtbares Fehlverhalten: ein `priority=high`-Alarm meldet einen Ausfall, den
es nicht gab.

## 🔴 Der Zeitpunkt kippt den naiven Ansatz

Der Intake-Vorschlag lautete: „bei Timeout nachfragen, ob der Slot `sent` trägt". Am realen
Ablauf gemessen funktioniert das **nicht**:

| Zeit | Ereignis |
|---|---|
| 18:02:00 | Timeout — hier würde nachgefragt |
| **18:04:38** | Versand fertig, `outcome: "sent"` wird erst **jetzt** geschrieben |

Eine Nachfrage im Moment des Timeouts findet den Slot noch **ohne** `outcome` und alarmiert
weiterhin — der Fix wäre wirkungslos. Die Positivkontrolle braucht also nicht nur einen
Nachweis, sondern einen **späteren Zeitpunkt**.

Das ist genau die Klasse Fehler, die eine reine Codelektüre nicht zeigt: die Zusicherung wäre
an der Stelle geprüft worden, an der der Code steht — nicht an der, an der sie wirkt.

## Technischer Ansatz (Empfehlung)

Zwei Teile, beide nötig; einer allein löst es nicht.

**Teil 1 — Timeout 120 s → 300 s** (`scheduler.go:115`), analog #1756 und mit dessen
Begründung: 3–4 Minuten sind der reguläre Erfolgsfall. Das deckt den Normalfall ab und macht
den Timeout wieder zum Ausnahmeereignis. Allein genügt es nicht: 278 s bei 4 Trips / 1 Nutzer,
das Produkt ist mandantenfähig.

**Teil 2 — Alarm bei Timeout aufschieben statt sofort feuern.** Läuft der Aufruf trotz 300 s
in den Timeout, wird der Lauf als *unentschieden* vermerkt, nicht als `error`. Die Entscheidung
fällt **verzögert** über die Positivkontrolle am Slot:

- Jeder Trip, den dieser Lauf angefasst hat, hat einen **Claim** in `briefing_slots.json`
  (angelegt beim Lauf-Start, `briefing_slots.py:153-176`). Der Lauf weiß damit exakt, welche
  Trips zu prüfen sind — kein Raten, welche Briefings „fällig" waren.
- Trägt später **jeder** dieser Claims `outcome: "sent"` → kein Alarm.
- Trägt **einer** ihn nicht, ist die Datei nicht lesbar, oder ist der Slot unbekannt →
  **Alarm bleibt.**

Für die Verzögerung ist ein begrenztes Nachfassen der schlankere Weg (nach dem Timeout in
Intervallen erneut lesen, harte Obergrenze), verglichen mit „erst beim nächsten stündlichen
Tick entscheiden" — Letzteres verschöbe einen echten Ausfall um bis zu eine Stunde und
erforderte Zustand über Läufe hinweg.

## Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `internal/scheduler/scheduler.go` | MODIFY | Timeout 120→300 s (Z. 115); `tripReports()` (Z. 271-304): Alarm erst nach Positivkontrolle |
| `internal/scheduler/briefing_slots.go` | CREATE | Slot-Datei je Nutzer lesen, Claims des Laufs auf `sent` prüfen (Muster: `briefing_health.go`) |
| `internal/scheduler/briefing_slots_test.go` | CREATE | Positivkontrolle inkl. Negativfälle |
| `internal/scheduler/scheduler_test.go` | MODIFY | Timeout-Pfad: Alarm ja/nein je nach Slot-Zustand |

## Scope Assessment

- Dateien: 4 (2 neu, 2 geändert), **reiner Go-Anteil, kein Python**
- Geschätzt: +180/-15 LoC Produktivcode **plus Tests** — der Nachweis kostet hier mehr als der
  Mechanismus, realistisch **~250–300 LoC gesamt**. Das LoC-Limit (250) wird voraussichtlich
  gerissen; Override ist dann beim PO einzuholen, nicht selbst zu setzen.
- Risiko: **HIGH** — Monitoring-/Alarmpfad. Fehler in die falsche Richtung macht den Wachhund
  blind.

## Risiken

- **Wachhund-Blindheit** (siehe oben) — die Mutation „unterdrückt auch ohne `sent`" MUSS ein
  Test fangen.
- **Geteilter Client:** der Timeout wirkt auch auf Alert-Checks (`scheduler.go:547`) und
  Compare (`:594`). Die Overlap-Sperre in `recordRun()` (`TryLock`, Z. 481-499) fängt
  überlappende Ticks ab und zählt sie, ein längerer Timeout blockiert also keinen Folgetick —
  aber es ist eine bewusste Entscheidung, keine Nebenwirkung.
- **Ortstag:** Slots sind nach Ortstag geschlüsselt, der Scheduler denkt in Serverzeit. Ein
  Vergleich über den falschen Tag findet nichts und alarmiert fälschlich (verwandt #1697).
- **Testbarkeit der Wartezeit:** Nachfassen braucht eine injizierbare Zeitquelle, sonst wird
  der Test langsam oder flaky.

## Open Questions (für die Spec-Freigabe)

- [ ] Obergrenze des Nachfassens — Vorschlag: bis 120 s nach dem Timeout, Intervall 15 s.
- [ ] Job-Status bei „Timeout, aber `sent` belegt": `ok` oder `partial`? Vorschlag: **`partial`**
      — der Lauf war fachlich erfolgreich, aber nicht sauber, und das soll in
      `/api/scheduler/status` sichtbar bleiben statt als glattes `ok` zu verschwinden.
