---
entity_id: bug_716_test_briefing_silent_fail
type: bugfix
created: 2026-06-10
updated: 2026-06-10
status: implemented
version: "1.0"
tags: [backend, frontend, test, email]
---

# Spec: Bug #716 — Test-Briefing: stiller Versagensfall + IMAP-Verifikation

## Approval

- [x] Approved (2026-06-10, Implementierung abgeschlossen)

**Issue:** #716  
**Workflow:** bug-716-test-briefing-silent-fail  
**Typ:** Bug-Fix (Backend + Test)  
**Folge-Bug aus:** #695 (Trip-spezifischer Endpunkt), #594 (Feedback-Toast)

## Source

- **Files:** `src/services/trip_report_scheduler.py`, `api/routers/scheduler.py`, `frontend/src/routes/trips/[id]/+page.svelte`
- **Identifier:** `send_test_trip_report`, `_send_trip_report`, `send_test_report`, `handleTestBriefing`

---

## Problem

### Problem 1 — Stiller Versagensfall
`POST /api/trips/{id}/send` gibt HTTP 200 + `{"status":"ok"}` zurück, auch wenn keine
E-Mail verschickt wurde. Das passiert immer dann, wenn `_send_trip_report()` einen
stillen Frühabbruch ausführt:

```python
# src/services/trip_report_scheduler.py
if not segments:
    return        # ← keine Exception, kein Signal — Endpoint gibt trotzdem 200
if not segment_weather:
    return        # ← dto.
```

`send_test_report()` gibt das `None` weiter. Der Endpoint fängt nur `ValueError` —
alle stillen Rückgaben enden mit `{"status": "ok"}` und HTTP 200. Das Frontend
liest `res.ok == true` → Erfolgs-Toast.

### Problem 2 — Test ohne Beweiskraft
`tests/tdd/test_issue_695_test_briefing_send.py::TestFrontendFeedback` prüft, ob
`data-testid`-Attribute im Svelte-Quelltext vorhanden sind. Das ist ein erlaubter
`# doc-compliance-test`, sagt aber nichts darüber aus, ob eine E-Mail tatsächlich
zugestellt wird. Ein Test der Zustellung per IMAP fehlt.

---

## Acceptance Criteria

**AC-1:** Given SMTP konfiguriert und Trip existiert, aber hat keine Etappen für das Zieldatum /
When `POST /api/scheduler/trips/{id}/send?user_id=default` aufgerufen wird /
Then antwortet das Backend mit HTTP 422 und `detail` enthält „Kein Briefing für" (nicht HTTP 200).

**AC-2:** Given SMTP konfiguriert und Trip existiert, und hat Etappen + Wetterdaten für das Zieldatum /
When `POST /api/trips/{id}/send` aufgerufen wird /
Then antwortet das Backend mit HTTP 200 + `{"status":"ok","sent":true}`.

**AC-3:** Given ein Test sendet ein echtes Test-Briefing an `gregor-test@henemm.com` /
When der Versand abgeschlossen ist /
Then findet sich eine E-Mail mit dem Trip-Namen im Betreff per IMAP in `gregor-test@henemm.com` nachweislich im Posteingang
(`@pytest.mark.email` — deselected in normalen Läufen).

**AC-4:** Given der API-Call auf `/api/trips/{id}/send` gibt 4xx zurück /
When die Antwort im Frontend ankommt /
Then zeigt der Fehler-Toast die konkrete Fehlermeldung aus dem `detail`-Feld der API-Antwort
(statt dem generischen „Fehler beim Senden").

---

## Dependencies

| Abhängigkeit | Typ | Bemerkung |
|-------------|-----|----------|
| `src/services/trip_report_scheduler.py` | intern | Kernservice — `_send_trip_report` + `send_test_report` |
| `api/routers/scheduler.py` | intern | FastAPI-Endpoint |
| `frontend/src/routes/trips/[id]/+page.svelte` | intern | Error-Toast |

---

## Expected Behavior

| Input | Output |
|-------|--------|
| `POST /api/scheduler/trips/{id}/send` — Trip ohne Etappen für Zieldatum | HTTP 422 + `{"detail": "Kein Briefing für <type> — keine Etappendaten…"}` |
| `POST /api/scheduler/trips/{id}/send` — Trip mit Etappe + Wetterdaten | HTTP 200 + `{"status":"ok","sent":true}` |
| API-Antwort 4xx im Frontend | Fehler-Toast zeigt `body.detail` statt generisches „Fehler beim Senden" |

---

## Betroffene Dateien

| Datei | Änderung |
|-------|---------|
| `src/services/trip_report_scheduler.py` | `_send_trip_report` → `bool`; `send_test_report` → `bool` |
| `api/routers/scheduler.py` | Endpoint prüft `sent`, 422 wenn `False` |
| `frontend/src/routes/trips/[id]/+page.svelte` | Error-Toast liest `detail` aus Response-Body |
| `tests/tdd/test_bug_716_test_briefing_silent_fail.py` | Neue Datei: AC-1-/AC-3-Tests |

**Nicht geändert:**
- `tests/tdd/test_issue_695_test_briefing_send.py` — valide Verhaltenstests bleiben erhalten
- `frontend/src/lib/issue_594_598_feedback_dialoge.test.ts` — valide doc-compliance-tests bleiben

---

## Implementierung

### 1. `_send_trip_report` → `bool`

`_send_trip_report` gibt jetzt `True` zurück wenn E-Mail tatsächlich gesendet wurde,
`False` bei Frühabbruch:

```python
def _send_trip_report(self, trip, report_type: str) -> bool:
    ...
    if not segments:
        logger.warning(f"No segments for trip {trip.id}")
        return False           # ← statt return
    ...
    if not segment_weather:
        logger.warning(f"No weather data for trip {trip.id}")
        return False           # ← statt return
    ...
    # 7a. Email senden (unverändert)
    ...
    return True
```

### 2. `send_test_report` → `bool`

```python
def send_test_report(self, trip, report_type: str) -> bool:
    if report_type not in ("morning", "evening"):
        raise ValueError(f"Invalid report_type: {report_type}")
    return self._send_trip_report(trip, report_type)
```

### 3. Endpoint (`api/routers/scheduler.py`)

```python
sent = service.send_test_report(trip, report_type)
if not sent:
    raise HTTPException(
        status_code=422,
        detail=f"Kein Briefing für {report_type} — keine Etappendaten für das aktuelle Datum",
    )
return {"status": "ok", "trip_id": trip_id, "report_type": report_type, "sent": True}
```

### 4. Frontend (`+page.svelte`)

```javascript
async function handleTestBriefing() {
    ...
    const res = await fetch(`/api/trips/${trip.id}/send`, { method: 'POST' });
    if (res.ok) {
        testBriefingStatus = 'ok';
        testBriefingMessage = null;
    } else {
        testBriefingStatus = 'error';
        try {
            const body = await res.json();
            testBriefingMessage = body.detail ?? 'Fehler beim Senden';
        } catch {
            testBriefingMessage = 'Fehler beim Senden';
        }
    }
    ...
}
```

Error-Span rendert `testBriefingMessage` statt des statischen Textes.

### 5. Test (`tests/tdd/test_bug_716_test_briefing_silent_fail.py`)

**AC-1-Test (FastAPI TestClient, kein Mark):**
- Erstellt einen Trip ohne Etappen (oder mit Etappen für ein weit vergangenes Datum)
- Ruft `POST /api/scheduler/trips/{id}/send?user_id=default` auf
- Erwartet HTTP 422 mit `detail` das „Kein Briefing für" enthält

**AC-3-Test (`@pytest.mark.email`):**
- Erstellt temporäres Test-User-Profil mit `mail_to = "gregor-test@henemm.com"`
- Trip mit Etappe, deren Datum dynamisch auf morgen (evening) gesetzt ist
- Ruft `TripReportSchedulerService.send_test_report(trip, "evening")` direkt auf
- Liest IMAP-Postfach `gregor-test` per `imaplib`, sucht nach E-Mail mit Trip-Namen
  im Betreff (max. 60s Polling mit 5s-Intervall)
- `Settings().for_testing()` stellt sicher, dass Stalwart-Credentials verwendet werden

---

## Abgrenzung

- Kein IMAP-Check im Produktions-Sende-Pfad (synchroner Overhead nicht vertretbar)
- `_send_trip_report` im Scheduler-Loop: bestehender Aufruf ignoriert `bool` → rückwärtskompatibel
- Kein Retry-Mechanismus für „keine Etappendaten" — das ist kein temporärer Fehler
- Telegram-Pfad unverändert (Issue verweist nur auf E-Mail)

---

## Changelog

- 2026-06-10: Erstellt (Issue #716)
