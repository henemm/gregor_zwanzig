---
entity_id: fix_1912_scheduler_briefing_timeout
type: module
created: 2026-08-16
updated: 2026-08-16
status: draft
version: "2.0"
tags: [scheduler, monitoring, go, issue-1912]
---

# Scheduler: Briefing-Timeout meldet keinen Ausfall mehr

## Approval

- [x] Approved (PO, 2026-08-16, Fassung 2.0)

## Purpose

Ein abgelaufener HTTP-Timeout ist kein Beweis für einen Briefing-Ausfall. Der Go-Scheduler
soll aufhören, ihn als solchen zu werten, und den Alarm „Trip-Briefing-Totalausfall (#1346)"
nur noch bei einer **echten Fehlerantwort** des Python-Cores feuern. Die Erkennung eines
tatsächlichen Ausfalls übernimmt der bereits vorhandene Heartbeat.

## Source

- **File:** `internal/scheduler/scheduler.go` (Go-API)
- **Identifier:** `Scheduler.triggerEndpointForUser()`, `Scheduler.client`

Schicht: **Go-API** (`internal/`). Kein Python-, kein Frontend-Anteil.

## Estimated Scope

- **LoC:** ~60 Produktivcode, ~120 Tests → **~180 gesamt** (unter dem Limit von 250)
- **Files:** 2 (`scheduler.go`, `scheduler_test.go`)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `partialRunError` (`scheduler.go:48-53`) | genutzt | Bestehender Zustand „Teilerfolg" aus #1447 S1 |
| `briefingDispatch()` (`scheduler.go:250-263`) | genutzt | Pingt den Heartbeat nur, wenn beide Teil-Jobs `ok` sind |
| `internal/notify/mq.go` | genutzt | MQ-Alarm an `infra` |

## Implementation Details

### Warum Fassung 1.0 verworfen wurde

Die erste Fassung wollte bei Timeout am Slot nachfragen, ob `outcome: "sent"` steht. Zwei am
Code belegte Gründe kippen das:

1. **Gescheiterte Versuche hinterlassen keine Spur.** `trip_report_scheduler.py:607-614` ruft
   bei Ausnahme und bei jedem Ausgang außerhalb `VERMERK_AUSGAENGE` (z. B.
   `channels_unreachable`) `store.release(...)` — der Eintrag wird **gelöscht**. Ein Lauf, in
   dem alles scheiterte, hinterlässt null Einträge, und „alle Einträge tragen `sent`" ist über
   der leeren Menge trivial wahr. Die Regel hätte bei einem **echten Totalausfall entwarnt**.
2. **300 s hätten nicht gereicht.** `briefing_slots.py:44-50`: „Untergrenze aus 22 realen
   Versandläufen (längster **Einzelversand 319 s**)". Ein einzelner Trip überschreitet den
   vorgeschlagenen Wert bereits.

### Der Ansatz: Timeout ist kein Ausfallsignal

`triggerEndpointForUser()` (`scheduler.go:545-584`) gibt heute bei jedem Transportfehler
`fmt.Errorf("HTTP error: %w", err)` zurück; `runForAllUsers()` wertet das als harten Fehler,
`recordRun()` setzt `error`, `tripReports()` alarmiert.

Künftig wird **im Transportfehler unterschieden**:

```
Timeout (context.DeadlineExceeded bzw. net.Error mit Timeout() == true)
    → partialRunError  → Job-Status "partial" → KEIN MQ-Alarm
                                              → KEIN Heartbeat-Ping
alles andere (Verbindung verweigert, DNS, HTTP 5xx, failed > 0)
    → harter Fehler    → Job-Status "error"   → MQ-Alarm wie bisher
```

Der Unterschied ist inhaltlich, nicht formal: Ein Timeout heißt „der Core antwortet mir nicht
**rechtzeitig**" — er kann dabei erfolgreich arbeiten, wie am 2026-08-16 geschehen. Eine
verweigerte Verbindung heißt „der Core ist nicht da"; das ist ein echter Ausfall.

### Die Positivkontrolle bleibt erhalten — über den Heartbeat

`briefingDispatch()` pingt BetterStack **nur**, wenn `trip_reports_hourly` **und**
`compare_presets_daily` auf `ok` stehen (`scheduler.go:259-262`). Ein `partial` pingt nicht.
Ein dauerhaft hängender Core erzeugt also weiterhin einen Alarm — über den ausbleibenden
Heartbeat statt über eine MQ-Nachricht, die auf einer Fehlannahme beruht. Entwarnt wird
weiterhin nur bei echtem Erfolg.

### Der Timeout muss trotzdem hoch — sonst kippt es in den nächsten Fehlalarm

Bliebe der Timeout bei 120 s, liefe künftig **jeder** Lauf in `partial` (319 s Einzelversand),
der Heartbeat pingte **nie** und BetterStack meldete Dauerausfall. Der Wert steigt deshalb auf
**3000 s (50 min)** — knapp unter dem stündlichen Cron-Abstand. Die Overlap-Sperre in
`recordRun()` (`TryLock`, Z. 481-499) verhindert, dass ein langsamer Lauf den Folgetick
blockiert; sie zählt übersprungene Ticks stattdessen.

Damit wird ein Timeout wieder das, was er sein soll: ein Ausnahmeereignis, das „der Core hängt
seit fast einer Stunde" bedeutet.

### Geteilter Client

`s.client` bedient drei Jobs (`scheduler.go:415` Trip-Reports, `:547` Alert-Checks, `:594`
Compare). Beide Änderungen — höherer Timeout und Timeout-als-`partial` — wirken bewusst auf
alle drei: „Timeout ist kein Ausfallbeweis" gilt dort genauso.

## Expected Behavior

- **Input:** Ergebnis des HTTP-Aufrufs an `/api/scheduler/trip-reports` je Nutzer
- **Output:** Job-Status in `/api/scheduler/status` (`ok` | `partial` | `error`); MQ-Alarm nur
  bei `error` auf der ok→error-Flanke; Heartbeat-Ping nur bei `ok`
- **Side effects:** keine Dateizugriffe, keine Schreibvorgänge

## Acceptance Criteria

- **AC-1:** Given der Aufruf an den Python-Core läuft in den Timeout / When der Lauf endet /
  Then wird **kein** MQ-Alarm gesendet und der Job-Status ist `partial`, nicht `error`.
  - Test: Go-Test mit `httptest`-Server, der die Antwort über den Client-Timeout hinaus
    verzögert; injizierter `notifier` zählt Alarme — erwartet: 0, Status `partial`.

- **AC-2:** Given ein Lauf endete wegen Timeout als `partial` / When `briefingDispatch()` den
  Heartbeat auswertet / Then wird **nicht** gepingt — ein dauerhafter Ausfall bleibt über
  BetterStack sichtbar. Entwarnung gibt es weiterhin nur bei echtem Erfolg.
  - Test: Heartbeat-Ziel als `httptest`-Server; nach Timeout-Lauf erwartet: 0 Aufrufe.

- **AC-3:** Given der Python-Core antwortet mit HTTP 500 / When der Lauf endet / Then wird der
  Alarm „Trip-Briefing-Totalausfall (#1346)" mit `priority=high` an `infra` gesendet und der
  Status ist `error` — unverändert zu heute.
  - Test: `httptest`-Server mit Status 500; erwartet: genau 1 Alarm an `infra`.

- **AC-4:** Given der Python-Core ist nicht erreichbar (Verbindung verweigert, kein Timeout) /
  When der Lauf endet / Then wird alarmiert und der Status ist `error`. Ein toter Core ist ein
  echter Ausfall und darf **nicht** als `partial` durchgehen.
  - Test: geschlossener Port als `pythonURL`; erwartet: genau 1 Alarm.

- **AC-5:** Given die Antwort trägt `failed > 0` oder `status: "partial"` im Körper / When der
  Lauf endet / Then bleibt das bestehende Verhalten aus #1447 unverändert.
  - Test: bestehende Scheduler-Tests bleiben grün; zusätzlicher Test mit `failed: 2` erwartet
    weiterhin `error` plus Alarm.

- **AC-6:** Given der Client-Timeout / When ein regulärer Lauf 319 s oder länger dauert / Then
  läuft er **nicht** in den Timeout — der Wert liegt bei 3000 s statt 120 s.
  - Test: Der gesetzte Timeout-Wert wird über einen Lauf beobachtet, der länger als 120 s
    simuliert wird (verkürzte Zeitbasis im Test), und schlägt nicht fehl.

- **AC-7:** Given mehrere Nutzer / When der Lauf für Nutzer A erfolgreich und für Nutzer B im
  Timeout endet / Then ist der Gesamtstatus `partial` (Rangfolge error > partial > ok, #1447
  S2a) und es wird nicht alarmiert.
  - Test: zwei Nutzer im Store, einer schnell, einer verzögert; erwartet: 0 Alarme, `partial`.

- **AC-8:** Given ein Timeout-Lauf, gefolgt von einem echten Fehler-Lauf / When die Flanke
  ausgewertet wird / Then feuert der Alarm beim Übergang nach `error` — die Flankenerkennung
  bleibt funktionsfähig und wird durch den neuen `partial`-Zustand nicht verschluckt.
  - Test: zwei aufeinanderfolgende Läufe (erst Timeout, dann HTTP 500); erwartet: genau 1
    Alarm beim zweiten Lauf.

## Known Limitations

- Ein echter Totalausfall wird künftig **später** gemeldet: nicht mehr sofort per MQ, sondern
  über den ausbleibenden BetterStack-Heartbeat nach dessen `period`/`grace`. Das ist der
  bewusst eingegangene Preis dafür, dass der sofortige Alarm nachweislich falsch lag.
- Der Timeout bleibt eine feste Zahl. Läuft die Generierung künftig länger als 50 Minuten,
  greift er erneut — dann ist das aber ein echter Befund, kein Fehlalarm.
- Die Timeout-Konstante bleibt an vier Stellen verstreut (`scheduler.go:115`, `proxy.go:108`,
  `proxy.go:277`, `compare_preset.go:676`). Gemeinsame Quelle → Nebenbefund #1199.
- Ein **Teil**ausfall (einzelne Trips scheitern, Core antwortet aber sauber) wird von dieser
  Scheibe nicht berührt; dafür ist der bestehende `failed`-Pfad aus #1447 zuständig.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Keine Entscheidungsfläche berührt. Der Fix nutzt mit `partialRunError` und der
  Heartbeat-Konsolidierung ausschließlich Mechanik, die #1447 und #1346 bereits eingeführt
  haben.

## Changelog

- 2026-08-16: Initial spec created (#1912)
- 2026-08-16: **Fassung 2.0** — Ansatz gewechselt. Fassung 1.0 (Positivkontrolle am Slot nach
  Timeout) verworfen: gescheiterte Versuche löschen ihren Slot-Eintrag
  (`trip_report_scheduler.py:607-614`), damit hätte die Regel bei einem echten Totalausfall
  entwarnt; zudem reicht der dort vorgeschlagene Timeout von 300 s nicht (längster gemessener
  Einzelversand 319 s, `briefing_slots.py:48`). Neu: Timeout wird als `partial` gewertet, der
  Alarm hängt nur noch an echten Fehlerantworten, die Ausfallerkennung trägt der Heartbeat.
