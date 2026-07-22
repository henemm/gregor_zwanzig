# Context: fix-1346-lauter-totalausfall

## Request Summary
Ein Briefing-Totalausfall (bzw. Ausfall einer Datenquelle) soll **laut** werden:
Lauf-Status = `error`, kein Heartbeat/„ok"-Signal, aktive Meldung an den
Betreiber. Auslöser: #1345 — zwischen 04:00–09:40 UTC am 2026-07-22 scheiterten
alle stündlichen Briefing-Läufe still; der PO entdeckte es selbst.

## Kernbefund (verändert die Diagnose aus dem Issue)
Der von #1346 vermutete Mechanismus **existiert bereits**:
- `dispatch_orchestrator.py:69–76` — Outcome `no_weather` (Totalausfall) zählt
  als `failed`, nicht als `sent` (Issue #1012 c).
- `api/routers/scheduler.py:42–44` — `/api/scheduler/trip-reports` gibt
  `{status:"partial", failed:N}` zurück, wenn `failed>0`.
- `internal/scheduler/scheduler.go:339–349` — Go wertet `failed>0` als Fehler
  → `recordRun` setzt `last_run.status="error"`.
- Heartbeat/Readiness ist bereits erfolgsgebunden (Go-Tests
  `scheduler_unify_test.go:230–321`: „compare fails → heartbeat not pinged").

⇒ Für den **regulären stündlichen Briefing-Pfad** ist der Totalausfall bereits
laut. #1346s Prämisse („nur logger.warning, gilt als Erfolg") trifft dort **nicht**.
Die tatsächliche(n) stille(n) Lücke(n) liegen woanders — Analyse-Phase muss den
echten 2026-07-22-Vorfall reproduzieren und den genauen Weg belegen.

## Verdächtige stille Lücken (für Analyse-Phase)
1. **Alert-/Radar-Check-Endpunkte ohne `failed`-Zähler**
   `api/routers/scheduler.py:53–94` (`alert-checks`, `radar-alert-checks`,
   `compare-alert-checks`, `compare-radar-alert-checks`,
   `compare-official-alert-checks`) geben **bedingungslos** `{status:"ok",count}`
   zurück. Ein Wetter-Totalausfall in diesen 15-Min-Jobs ist strukturell
   unsichtbar (Go sieht HTTP 200, `failed` fehlt → `status=ok`).
2. **MeteoAlarm/amtliche Warnungen werden verschluckt** (PO-Hinweis
   „open-meteo gefixt, MeteoAlarm nicht"): `trip_report_scheduler.py:797–809`
   fängt jeden Fehler beim Laden amtlicher Warnungen mit
   `logger.warning(...); official_alerts=[]`. Fällt MeteoAlarm aus, geht das
   Briefing **scheinbar erfolgreich ohne Warnungen** raus — Partial-Silent-Failure,
   den #1346 in heutiger Wortwahl („alle Wetterdaten fehlen") **nicht** abdeckt.
   → Scope-Frage für die Spec: Deckt #1346 nur Wetterdaten-Totalausfall oder auch
     Teil-Ausfall einer Datenquelle (Warnungen) ab?
3. **#1345-Crash-Pfad:** TypeError in `_aggregate_for_segment` (naive/aware ts).
   Statisch müsste er via `dispatch_orchestrator.py:76` (`except → failed+=1`)
   oder HTTP 500 laut werden — dennoch beobachtete der PO Stille. Analyse muss
   mit den echten Logs klären, ob (a) der Crash außerhalb der gezählten Schleife
   lag oder (b) ein anderer Pfad (Alert-Checks) die „All-failed"-Zeilen erzeugte.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_report_scheduler.py:797–835` | All-failed-Zweig (819), MeteoAlarm-Swallow (800), `no_weather`-Return |
| `src/services/dispatch_orchestrator.py:63–80` | outcome→(sent,failed)-Mapping, `no_weather`→failed |
| `api/routers/scheduler.py:40–94` | Endpunkte: trip-reports mit failed; Alert-Checks OHNE failed |
| `internal/scheduler/scheduler.go:188–353` | `recordRun`, `triggerEndpointForUser` (failed>0→error), briefingDispatch |
| `internal/scheduler/scheduler.go:238–274` | `dataWriteSelftest` — **Vorbild** für Edge-getriggerte MQ-an-infra bei ok→error |
| `internal/scheduler/scheduler_unify_test.go:230–321` | Heartbeat nur bei Erfolg (bestehendes Verhalten) |
| `src/lib/mq_notify.py` / `internal/notify/mq.go` | MQ-Benachrichtigung an `infra` |
| `api/routers/scheduler.py:207–217` | #1325: `no_weather` als echter Ausfall (Single-Trip-Pfad) |

## Existing Patterns
- **Edge-getriggerte Betreiber-Meldung:** `dataWriteSelftest` (scheduler.go:238)
  schickt MQ an `infra` **nur beim Statuswechsel** ok→error (kein Spam), mit
  Recovery-Notiz bei error→ok. Direkt übertragbares Muster für #1346.
- **Readiness-Heartbeat:** Ping/`status=ok` nur bei echtem fachlichem Erfolg
  (globale CLAUDE.md-Regel; oebb-Negativbeispiel).
- **`failed`-Zähler-Vertrag** zwischen Python-Endpoint und Go-Scheduler (#1012).

## Dependencies
- Upstream: `_fetch_weather` (Provider), `get_official_alerts_for_location` (MeteoAlarm)
- Downstream: Go-`recordRun`/`/api/scheduler/status`, externes Monitoring
  (`henemm-infra/check-gregor20.sh`), MQ→`infra`, BetterStack

## Risks & Considerations
- **Fehlalarm-Gefahr:** Zu aggressives „error" (z.B. „keine fälligen Trips" =
  (0,0)) darf NICHT als Fehler gelten — nur echter Datenausfall.
- **Prozess-Grenze Python↔Go:** Fix kann beide Seiten berühren (Endpoint-Vertrag
  + Go-Auswertung/MQ). Klein halten, LoC-Limit 250.
- **Scope-Disziplin:** Alert-Check-`failed`-Zähler und MeteoAlarm-Teilausfall
  sind eigene Fehlerflächen — in der Spec bewusst ein-/ausgrenzen, nicht
  ungeplant miterledigen.
- Kern-Test deterministisch (Fixture: erzwungener All-failed → `failed>0` +
  kein Heartbeat/`status=error`), kein Live-Netz.
