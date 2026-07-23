# Kontext: #1346 — Stiller Briefing-Totalausfall

## Analysis

### Type
Bug (Observability-Lücke im Scheduler-Alarmpfad)

### Symptom
Am 22.07. scheiterten zwischen 04:00–09:40 UTC **alle** Trip-Briefing-Läufe
(`All-failed weather data for trip …`). Das System versendete die Ersatzmail
„Wetterdaten nicht verfügbar", aber es gab **keinen aktiven Alarm**. Der PO
entdeckte den Ausfall selbst. Verstoß gegen die Heartbeat-Readiness-Regel.

### Root Cause (belegt, nicht spekuliert)

Der im Issue vermutete Ort (`src/services/trip_report_scheduler.py:819`,
„nur `logger.warning`") ist **nicht** mehr die Ursache. Belegte Kette:

1. **Python-Ebene korrekt:** `trip_report_scheduler.py:839` gibt bei Totalausfall
   `"no_weather"` zurück. `dispatch_orchestrator.py:71` zählt `no_weather` als
   `failed += 1` (Fix #1012c). Der Endpoint `/api/scheduler/trip-reports`
   (`api/routers/scheduler.py:43`) liefert `failed > 0`.
2. **Go-Statuserfassung korrekt:** `internal/scheduler/scheduler.go:340`
   (`triggerEndpointForUser`) wertet `failed > 0` aus HTTP-200-Body aus und gibt
   einen Fehler zurück → `recordRun` (`scheduler.go:295`) schreibt Status
   `"error"` für Job `trip_reports_hourly`. **Status-Endpoint ist also bereits
   korrekt** (Erwartung 1 des Issues teilweise erfüllt).
3. **LÜCKE 1 — kein Briefing-Heartbeat:** `tripReports()` (`scheduler.go:193`)
   ruft **nur** `recordRun` — **kein** `pingHeartbeat`. Der **einzige**
   überwachte Heartbeat hängt an `comparePresetsDaily()` (`scheduler.go:288`,
   `s.heartbeatComparePresets`). Solange der Ortsvergleich läuft, pingt
   BetterStack grün — der Trip-Briefing-Ausfall wird vom **fremden** Heartbeat
   verdeckt.
4. **LÜCKE 2 — keine aktive Meldung:** Kein MQ-/Betreiber-Alarm bei
   `trip_reports_hourly` ok→error. Vorbild existiert bereits:
   `dataWriteSelftest()` (`scheduler.go:236`) macht genau diesen
   edge-getriggerten MQ-Alarm (`s.notifier("gregor","infra","high",…)`).

**Fazit:** Ausfall ist im Status *sichtbar*, aber nirgends *laut*.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/scheduler/scheduler.go` | MODIFY | Heartbeat-Ping aus `comparePresetsDaily()` nach `briefingDispatch()` verlagern, gegated auf Status ok **beider** Jobs (`trip_reports_hourly` UND `compare_presets_daily`) |
| `internal/scheduler/scheduler.go` | MODIFY | Edge-getriggerter MQ-Alarm `infra` bei `trip_reports_hourly` ok→error (prio high) + Recovery-Notiz error→ok — analog `dataWriteSelftest` |
| `internal/scheduler/scheduler_unify_test.go` | MODIFY/CREATE | Kern-Tests: Trip-All-failed → Status error + kein Ping + MQ high; beide ok → genau 1 Ping, kein MQ; error→ok Recovery-Notiz |

**Kontingent-Lösung (PO 2026-07-23):** KEIN neuer BetterStack-Heartbeat (10er-Kontingent voll). Stattdessen **Konsolidierung**: der bestehende `HeartbeatComparePresets` (ENV `HEARTBEAT_COMPARE_PRESETS`, URL unverändert) wird zum **Briefing-Dispatch-Heartbeat** — pingt erst, wenn im selben Tick BEIDE Jobs ok. Heute (Bug) pingt er nur bei Ortsvergleich-ok und verdeckt so den Trip-Ausfall.

### Scope Assessment
- Files: 1 Code (+1 Testdatei)
- Estimated LoC: ~+55/-8 (Go), unter 250er-Limit
- Risk Level: LOW — Umzug + strengeres Gating eines bereits getesteten Heartbeat-Musters; MQ-Alarm 1:1 nach `dataWriteSelftest`. Kein Python-/Datenpfad, keine ENV-/Infra-Änderung nötig.

### Technical Approach (PO-bestätigt)
1. `briefingDispatch()`: nach `tripReports()` + `comparePresetsDaily()` beide `lastRuns`-Status lesen; nur wenn **beide** == `ok` → `pingHeartbeat("briefing_dispatch", s.heartbeatComparePresets)`. Ping-Aufruf aus `comparePresetsDaily()` **entfernen**.
2. Edge-getriggert (Vorzustand vs. jetzt, kein `sync.Once`) MQ an `infra` bei `trip_reports_hourly` ok→error (prio `high`) + Recovery error→ok.
3. Fail-soft: leere Heartbeat-URL → bestehendes `warnMissingHeartbeatOnce`; MQ-Alarm greift URL-unabhängig.

### Dependencies
- Keine Infra-Blocker mehr (MQ #53434: kein neuer Heartbeat). Optional kosmetisch: infra benennt BetterStack-Monitor-Label `compare-presets` → `briefing-dispatch` um (URL bleibt).
- Kein Bezug zu #1348/#1329 (die betreffen die *Ursache* der Ausfälle: Kontingent/429). Dieses Issue betrifft nur die *Stille*.

### Open Questions
- keine offen — Ansatz und Kontingent-Lösung PO-bestätigt.
