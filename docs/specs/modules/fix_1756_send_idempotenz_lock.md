---
entity_id: fix_1756_send_idempotenz_lock
type: module
created: 2026-08-14
updated: 2026-08-14
status: draft
version: "1.0"
tags: [bug, scheduler, mandantenfaehigkeit]
---

# Send-Idempotenz-Lock für manuellen Trip-Versand (Issue #1756)

## Approval

- [ ] Approved

## Purpose

Der manuelle Sendeknopf im Trip-Editor liefert nach ~60s einen 502, obwohl der
Versand serverseitig 3–4 Minuten später trotzdem erfolgreich abschließt. Ohne
serverseitigen Schutz kann ein zweiter Klick (verleitet durch die
irreführende Fehlermeldung) während eines laufenden Versands einen echten
zweiten Versand desselben Briefings auslösen. Diese Spec führt einen
In-Process-Lock pro `(user_id, trip_id, report_type)` ein, der einen
zweiten gleichzeitigen Sendeversuch mit HTTP 409 abweist statt ihn parallel
auszuführen, plus eine moderate Anhebung der Timeout-Kette als Trittstein
für den regulären Erfolgsfall.

## Source

- **File:** `src/services/trip_report_scheduler.py`
- **Identifier:** `TripReportSchedulerService._send_trip_report_outcome`, `TripReportSchedulerService.send_test_report_outcome`, `TripReportSchedulerService.send_on_demand_report`

> **Schicht-Hinweis:** Diese Spec berührt alle drei Schichten:
> - **Python-Core / Domain-Backend** → `src/services/trip_report_scheduler.py` (Lock), `api/routers/scheduler.py` (409-Mapping)
> - **Go-API** → `internal/handler/proxy.go` (`SendTripReportProxyHandler`, Timeout-Anhebung, 409-Passthrough bereits generisch vorhanden)
> - **Frontend / User-UI** → `frontend/src/routes/trips/[id]/+page.svelte` (`handleTestBriefing`, 409-Meldungstext)
>
> Verifiziert per Grep der betroffenen Symbolnamen vor dem Schreiben dieser Spec (Zeilen unten mit Stand 2026-08-14).

## Estimated Scope

- **LoC:** ~60–90 (Hauptrepo, unter dem 250-LoC-Standard-Budget)
- **Files:** 5 im Hauptrepo (`src/services/trip_report_scheduler.py`, `api/routers/scheduler.py`, `internal/handler/proxy.go`, `frontend/src/routes/trips/[id]/+page.svelte`, `src/services/trip_command_processor.py` — Nachtrag Adversary-Runde, s. AC-9); 1 Follow-up außerhalb des Repos (`henemm-infra`, siehe „Cross-Repo-Follow-up")
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `threading.Lock` (stdlib) | library | Prozess-lokale Sperre pro Lock-Key, kein neuer Fremd-Baustein |
| `TripReportSchedulerService._send_trip_report_outcome` | internal | Kernpfad, der gesperrt wird — unverändert in seiner fachlichen Logik |
| `api/routers/scheduler.py: send_test_trip_report` | internal | Bestehendes 422-Fehler-Schema als Vorbild für den neuen 409-Zweig |
| `internal/handler/proxy.go: SendTripReportProxyHandler` | internal | Reicht `resp.StatusCode` bereits generisch durch — 409 braucht dort keine neue Fallunterscheidung, nur die Timeout-Konstante ändert sich |
| `frontend/.../+page.svelte: handleTestBriefing` | internal | Generischer 4xx-Zweig zeigt `body.detail` bereits an (siehe Implementation Details) — Änderungsbedarf ggf. nur im Backend-Text |
| `src/services/trip_command_processor.py: _on_demand_failure_body` | internal | Mappt Outcome → SMS-Antworttext für den On-Demand-Pfad (#1007); braucht einen Zweig für `already_in_progress`, sonst fällt der neue Outcome fälschlich auf den `no_stage`-Text zurück (Nachtrag Adversary-Runde) |

## Implementation Details

### 1. Lock im Python-Core (`src/services/trip_report_scheduler.py`)

Modul-weites (nicht instanz-gebundenes!) Lock-Register, da pro Request eine
neue `TripReportSchedulerService`-Instanz erzeugt wird
(`api/routers/scheduler.py:229`: `service = TripReportSchedulerService(user_id=user_id)`)
— ein Instanzattribut würde daher NIE mit sich selbst kollidieren:

```python
# Modul-Ebene, oberhalb der Klasse
_send_locks: Dict[Tuple[str, str, str], bool] = {}
_send_locks_guard = threading.Lock()


def _try_acquire_send_lock(user_id: str, trip_id: str, report_type: str) -> bool:
    key = (user_id, trip_id, report_type)
    with _send_locks_guard:
        if _send_locks.get(key):
            return False
        _send_locks[key] = True
        return True


def _release_send_lock(user_id: str, trip_id: str, report_type: str) -> None:
    key = (user_id, trip_id, report_type)
    with _send_locks_guard:
        _send_locks.pop(key, None)
```

`send_test_report_outcome()` und `send_on_demand_report()` (beide rufen
`_send_trip_report_outcome()` auf, Zeilen 908 und 936) klammern ihren
jeweiligen Aufruf:

```python
if not _try_acquire_send_lock(self._user_id, trip.id, report_type):
    return "already_in_progress"
try:
    return self._send_trip_report_outcome(...)
finally:
    _release_send_lock(self._user_id, trip.id, report_type)
```

`send_on_demand_report()` gibt `OnDemandErgebnis(outcome=..., zieltag=...)`
zurück — der `"already_in_progress"`-Zweig braucht dort einen Platzhalter-
`zieltag` (z. B. den bereits berechneten `zieltag` vor dem Lock-Versuch, da
`_get_target_date` keine teure/blockierende Operation ist und vor dem
Lock-Erwerb passieren kann, ohne die Sperrsemantik zu verändern).

**Freigabe ist PFLICHT per `finally`** — ein Fehler im Sendepfad (Exception,
Timeout) darf den Lock nicht dauerhaft belegt lassen, sonst wird aus dem
502-Bug ein permanentes 409 nach dem ersten Absturz.

### 2. Outcome-Mapping im Router (`api/routers/scheduler.py`)

Neuer Zweig in `send_test_trip_report`, analog zu den bestehenden
`no_stage`/`no_weather`/`no_channels`-422-Zweigen (Zeilen 219–260), aber mit
HTTP 409 statt 422 (Ressourcen-Konflikt, nicht Validierungsfehler):

```python
if outcome == "already_in_progress":
    raise HTTPException(
        status_code=409,
        detail=f"Versand für {report_type} läuft bereits — bitte warten",
    )
```

`send_on_demand_report()` wird über den Inbound-Kommandopfad
(`trip_command_processor`) aufgerufen, nicht über diesen HTTP-Router — dessen
Aufrufer muss den neuen Outcome-Wert `"already_in_progress"` ebenfalls kennen
(mindestens: nicht als Fehler loggen, sondern als erwarteten Kollisionsfall).

### 3. Go-Proxy-Timeout (`internal/handler/proxy.go`)

`SendTripReportProxyHandler` (Zeile ~254): `client := &http.Client{Timeout: 120 * time.Second}`
wird auf `300 * time.Second` angehoben. Das 409-Passthrough ist bereits
generisch implementiert (`w.WriteHeader(resp.StatusCode)`, Zeile ~289) —
hier ist **keine Codeänderung** nötig, nur eine Verifikation per Test/Review,
dass 409 unverändert durchgereicht wird.

### 4. Frontend-Meldung (`frontend/src/routes/trips/[id]/+page.svelte`)

`handleTestBriefing()` (Zeile 209 ff.) unterscheidet bereits zwischen
`res.status >= 500` (generische Serverfehler-Meldung, `detail` wird
absichtlich NICHT angezeigt) und dem `else`-Zweig, der `body.detail`
anzeigt, sofern vorhanden (Zeile ~232). Ein 409 fällt strukturell bereits in
diesen zweiten Zweig — die vom Backend gesetzte Detail-Meldung
("Versand für … läuft bereits — bitte warten") erscheint damit **ohne
weitere Frontend-Codeänderung**. Diese Spec verlangt trotzdem einen
Frontend-Test (AC-7), der das für den 409-Fall explizit absichert, damit ein
künftiges Refactoring dieses Zweigs den 409-Fall nicht versehentlich in die
generische 5xx-Meldung verschiebt. Kein automatischer Retry, kein Poll —
unverändert gegenüber dem bestehenden Verhalten.

## Expected Behavior

- **Input:** Zwei (quasi-)gleichzeitige `POST /api/trips/{id}/send`-Aufrufe
  für denselben `user_id`+`trip_id`+`report_type`, während der erste Aufruf
  noch läuft.
- **Output:** Erster Aufruf läuft wie bisher durch (`"sent"`/`"no_stage"`/…).
  Zweiter Aufruf erhält sofort HTTP 409 mit sprechendem Detail, OHNE dass ein
  zweiter echter Versand angestoßen wird. Nach Abschluss des ersten Aufrufs
  (Erfolg oder Fehler) ist ein neuer Versand für denselben Schlüssel wieder
  möglich.
- **Side effects:** Keine Persistenzänderung — der Lock lebt ausschließlich
  im Prozessspeicher (Dict), kein Datei-/DB-Zustand. Wirkt nur innerhalb
  eines Systemd-Prozesses (`gregor-python`/`-staging` laufen je als ein
  Prozess — siehe „Known Limitations").

## Acceptance Criteria

- **AC-1:** Given ein Testversand für Trip A (User X, `report_type=evening`) läuft bereits / When während dieser Laufzeit ein zweiter `send_test_report_outcome()`-Aufruf für denselben Trip A, User X und `report_type=evening` erfolgt / Then liefert der zweite Aufruf den Outcome `"already_in_progress"`, OHNE dass ein zweiter echter Versand (E-Mail/Telegram/SMS) ausgelöst wird.
  - Test: Zwei sequenzielle/simultane Aufrufe von `send_test_report_outcome()` im selben Prozess (Lock künstlich vorbelegt oder über einen blockierenden Mock im ersten Aufruf simuliert); prüfen, dass der Versand-Mock (Notification-Layer) nur EINMAL aufgerufen wird. Dies ist der Bug-Nachweis: rot vor Fix (heute läuft der zweite Aufruf ungehindert durch und ruft den Versand ein zweites Mal auf), grün nach Fix.

- **AC-2:** Given kein Versand für Trip A, User X, `report_type=evening` läuft gerade / When `send_test_report_outcome()` aufgerufen wird / Then läuft der Versand wie bisher unverändert durch (Outcome bleibt `"sent"`/`"no_stage"`/`"no_weather"`/`"no_channels"`/`"channels_unreachable"`, keine Regression am bestehenden Verhalten aus #695/#1325).
  - Test: Einzelner Aufruf ohne Lock-Kollision liefert denselben Outcome wie vor dieser Änderung (bestehende Tests aus #695/#1325 bleiben grün, ergänzt um einen expliziten „Lock wird danach wieder freigegeben"-Check).

- **AC-3:** Given ein zweiter Aufruf trifft auf einen belegten Lock / When der Router-Endpunkt `POST /api/scheduler/trips/{trip_id}/send` den Outcome `"already_in_progress"` erhält / Then antwortet der Router mit HTTP 409 und einem sprechenden Detail-Text (z. B. "Versand für evening läuft bereits — bitte warten"), unterscheidbar von den bestehenden 422-Fehlerzweigen.
  - Test: HTTP-Client-Test gegen den FastAPI-Router mit gemocktem `send_test_report_outcome()`-Rückgabewert `"already_in_progress"`; prüft Statuscode 409 und Vorhandensein eines nicht-leeren `detail`-Felds.

- **AC-4:** Given ein Versand ist abgeschlossen (egal ob erfolgreich oder mit Exception beendet) / When derselbe Lock-Schlüssel danach erneut angefragt wird / Then wird der Lock erfolgreich neu erworben (kein dauerhaftes Blockieren nach einem einzelnen abgeschlossenen oder fehlgeschlagenen Versand).
  - Test: `_send_trip_report_outcome()` wirft eine Exception (simuliert), anschließender zweiter Aufruf für denselben Schlüssel muss den Lock wieder frei vorfinden (nicht `"already_in_progress"` liefern) — beweist, dass die Freigabe per `finally` und nicht nur im Erfolgspfad passiert.

- **AC-5:** Given zwei verschiedene Nutzer (User X und User Y) lösen jeweils gleichzeitig einen Testversand für ihren jeweils eigenen Trip mit identischer `trip_id` und identischem `report_type` aus (Mandantentrennung: `trip_id`s sind pro Nutzer eigene IDs, ein Zusammentreffen ist über Test-Fixtures gezielt herbeigeführt) / When beide Aufrufe zeitgleich laufen / Then blockiert keiner der beiden Aufrufe den anderen — beide erhalten unabhängig voneinander den Outcome ihres eigenen Versands, keiner `"already_in_progress"` durch den jeweils anderen Nutzer.
  - Test: Zwei `TripReportSchedulerService`-Instanzen mit unterschiedlichem `user_id` (z. B. `"user_x"`, `"user_y"`), gleicher `trip_id`-String, gleicher `report_type`; beide Sendeversuche parallel/verschachtelt anstoßen und prüfen, dass beide durchlaufen (kein `"already_in_progress"` bei keinem der beiden). Pflicht-Zwei-Nutzer-Test gemäß CLAUDE.md-Mandantenfähigkeits-Vorgabe.

- **AC-6:** Given `send_on_demand_report()` (SMS "heute"/"morgen"-Inbound-Pfad) nutzt denselben `_send_trip_report_outcome()`-Kern / When während eines laufenden On-Demand-Versands für Trip A, User X, `report_type` ein zweiter On-Demand-Aufruf für denselben Schlüssel eintrifft / Then liefert `send_on_demand_report()` ein `OnDemandErgebnis` mit `outcome="already_in_progress"`, ohne einen zweiten echten Versand auszulösen — derselbe Lock-Schutz wie im Testversand-Pfad (AC-1), gemeinsamer Lock-Key-Raum über beide Aufrufer hinweg.
  - Test: Analog AC-1, aber über `send_on_demand_report()` statt `send_test_report_outcome()`; zusätzlich ein Test, der zeigt, dass ein laufender Testversand (`send_test_report_outcome`) einen gleichzeitigen On-Demand-Versand (`send_on_demand_report`) für denselben Schlüssel ebenfalls blockiert (geteilter Lock-Key-Raum, nicht zwei getrennte Register).

- **AC-7:** Given der Trip-Editor erhält HTTP 409 vom Sende-Endpunkt / When `handleTestBriefing()` die Antwort verarbeitet / Then zeigt die Oberfläche die vom Backend gelieferte Detail-Meldung an (unterscheidbar von der generischen 5xx-"Serverfehler"-Meldung), OHNE einen automatischen Retry oder Poll auszulösen.
  - Test: Frontend-Unit-/Component-Test mit gemocktem `fetch`, der 409 + `{"detail": "Versand für evening läuft bereits — bitte warten"}` zurückgibt; prüft, dass `testBriefingMessage` genau diesen Text (oder den Backend-Detail-Text) enthält und `testBriefingStatus` NICHT erneut `fetch` auslöst.

- **AC-8:** Given der Go-Proxy-Handler `SendTripReportProxyHandler` / When der Python-Upstream länger als die bisherigen 120s, aber innerhalb von 300s antwortet / Then liefert der Go-Proxy die tatsächliche Antwort (inkl. 409-Fälle unverändert durchgereicht) statt eines generischen 502 "upstream unreachable".
  - Test: Go-Test gegen `SendTripReportProxyHandler` mit einem simulierten Upstream, der z. B. nach 150s antwortet (oder Timeout-Konstante direkt inspiziert `client.Timeout == 300*time.Second`); zusätzlicher Test bestätigt, dass ein vom Upstream gelieferter 409-Statuscode unverändert im Response-StatusCode ankommt.

- **AC-9 (Nachtrag Adversary-Runde, 2026-08-14):** Given der SMS-Inbound-Pfad "heute"/"morgen" löst über `send_on_demand_report()` einen Kollisionsfall aus (`outcome="already_in_progress"`, s. AC-6) / When `_on_demand_failure_body()` in `src/services/trip_command_processor.py` diesen Outcome in SMS-Antworttext übersetzt / Then liefert die Funktion einen Text, der den Kollisionsfall benennt (z. B. "Versand läuft bereits — bitte kurz warten"), NICHT den bestehenden `no_stage`-Fallback-Text ("Keine Etappe geplant"), der fachlich falsch wäre.
  - Test: Direkter Unit-Test von `_on_demand_failure_body("already_in_progress", label, target_date)` (mock-frei, reine Mapping-Funktion, Muster: `tests/tdd/test_issue_1007_heute_voll_briefing.py`), prüft den zurückgegebenen Text auf Unterscheidbarkeit vom `no_stage`-Text.

## Known Limitations

- Der In-Process-Lock wirkt nur pro Systemd-Prozess. `gregor-python` und
  `gregor-python-staging` laufen laut Architektur je als **ein** Prozess —
  unkritisch heute, aber bei einem künftigen Wechsel auf Multi-Worker/
  Multi-Prozess-Deployment würde der Lock nicht mehr prozessübergreifend
  wirken. Als Kommentar im Code festhalten (siehe Implementation Details).
- Die Nginx-`proxy_read_timeout`-Anhebung (siehe „Cross-Repo-Follow-up") ist
  NICHT Teil dieses Workflows und muss separat in `henemm-infra` ausgeliefert
  werden, damit der Erfolgsfall auch am produktiven Reverse-Proxy nicht mehr
  vorzeitig abbricht. Der Lock allein löst bereits das Kernrisiko (Doppel-
  Versand); ohne die Infra-Änderung bleibt die irreführende 502-Meldung im
  Erfolgsfall vorerst bestehen, aber ohne Datenschaden.
- Kein Async-/Poll-Muster (Option B aus der Analyse) — die 3–4 Minuten
  Wartezeit für den Testversand bleiben bestehen. Bewusst nicht in dieser
  Scheibe adressiert (siehe `docs/context/fix-1756-send-timeout-502.md`,
  Abschnitt „Technical Approach").
- **Renderer-Commit-Gate (#811):** nicht betroffen — diese Änderung fasst
  keine Mail-Renderer-Dateien (`src/output/renderers/...`) an, nur den
  Versand-Orchestrierungspfad (Lock) und die Fehler-Mapping-/Proxy-/UI-
  Schicht darüber.
- **Pendant-Gate (#1481 B):** nicht betroffen — keine neuen Dateien in
  `frontend/src/lib/components/{compare,trip-detail,...}` oder in
  präfigierten Renderer-Pfaden; die geänderte Datei
  `frontend/src/routes/trips/[id]/+page.svelte` liegt außerhalb des vom
  Gate erfassten Komponentenbaums.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Der In-Process-Lock ist ein lokaler Implementierungsdetail-
  Fix innerhalb des bestehenden synchronen Sendepfads, keine Änderung an
  einer der in CLAUDE.md gelisteten Entscheidungsflächen (Kanäle, Provider,
  Datenmodell/Persistenz, Auth, Editor-Paradigma, Test-/Deploy-Strategie).
  Die Timeout-Anhebung ist eine Konfigurationsanpassung, keine
  Architekturentscheidung. Sollte ein künftiger Wechsel auf Multi-
  Prozess-Deployment den Lock-Mechanismus selbst ersetzen müssen (z. B.
  durch einen verteilten Lock), wäre DAS ein eigenes ADR-würdiges Thema —
  nicht diese Scheibe.

## Cross-Repo-Follow-up

Die Nginx-`proxy_read_timeout`-Einstellung in
`henemm-infra/nginx/gregor20.henemm.com.conf` (aktuell kein expliziter Wert
gesetzt → Nginx-Default 60s greift, siehe Root-Cause-Verifikation in
`docs/context/fix-1756-send-timeout-502.md`) liegt außerhalb dieses Repos
und ist **nicht Teil der ACs dieses Workflows**. Empfehlung: `proxy_read_timeout 300s;`
synchron zum neuen Go-Client-Timeout (AC-8) setzen, damit der Erfolgsfall
(3–4 Minuten Laufzeit durch den absichtlich vollständigen Mehrtages-
Ausblick) auch am produktiven Reverse-Proxy nicht mehr vorzeitig abbricht.
Diese Änderung ist unabhängig deploybar; der Lock (AC-1–AC-6) löst das
eigentliche Schadensrisiko (Doppelversand) bereits ohne sie. Nach Abschluss
dieses Workflows: MQ-Nachricht an die `infra`-Instanz mit Verweis auf diese
Spec und den empfohlenen Wert.

## Changelog

- 2026-08-14: Initial spec created (Issue #1756)
