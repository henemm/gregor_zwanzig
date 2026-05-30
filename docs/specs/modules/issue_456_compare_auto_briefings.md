---
entity_id: issue_456_compare_auto_briefings
type: module
created: 2026-05-30
updated: 2026-05-30
status: draft
version: "1.0"
issue: 456
tags: [compare, subscription, auto-briefing, manual-send, top-ort]
---

# Issue #456 — Orts-Vergleich · Auto-Briefings: Manueller Versand-Trigger + Top-Ort-Anzeige

## Approval

- [ ] Approved

## Purpose

Ergänzt das bestehende `CompareSubscription`-System um einen manuellen Versand-Trigger (`POST /api/subscriptions/{id}/send`) und das neue Feld `top_ort_letzter_versand`, das den Gewinner-Ort des letzten Versands persistiert. Das Sidepanel (`AutoReportCard`) zeigt diesen Top-Ort zusammen mit dem bestehenden `last_run`-Zeitstempel an, sodass der Nutzer auf einen Blick sieht, welcher Ort beim letzten Briefing vorne lag — ohne die Mail erneut aufrufen zu müssen.

> **Schicht-Zuordnung:** Alle vier Schichten betroffen: Go-API (`internal/`, `cmd/`), Python-Backend (`src/app/`, `src/services/`, `src/app/loader.py`, `api/routers/`), SvelteKit-Frontend (`frontend/src/`). Das neue Feld ist additiv mit `omitempty`/`Optional[str] = None` — bestehende JSONs bleiben fehlerfrei ladbar.

## Source

- **EDIT** `internal/model/subscription.go` — `CompareSubscription`-Struct um Feld `TopOrtLetzterVersand` erweitern
- **EDIT** `internal/handler/proxy.go` — neuer `SendSubscriptionProxyHandler` analog zu `AlertPreviewProxyHandler`
- **EDIT** `cmd/server/main.go` — Route `POST /api/subscriptions/{id}/send` registrieren
- **EDIT** `src/app/user.py` — `CompareSubscription`-Dataclass um Feld `top_ort_letzter_versand` erweitern
- **EDIT** `src/services/compare_subscription.py` — Return-Typ von `run_comparison_for_subscription()` auf 4-Tupel erweitern, 4. Element = Winner-Name
- **EDIT** `src/app/loader.py` — CompareSubscription-Deserialisierung liest `top_ort_letzter_versand`
- **EDIT** `api/routers/scheduler.py` — neuer Endpoint `POST /api/scheduler/subscriptions/{subscription_id}/send`; alle 4 Aufruf-Stellen von `run_comparison_for_subscription()` auf 4-Tupel anpassen; `_save_subscription` speichert `top_ort_letzter_versand`
- **EDIT** `frontend/src/lib/types.ts` — `Subscription`-Interface um `top_ort_letzter_versand?` erweitern
- **EDIT** `frontend/src/lib/components/compare/AutoReportCard.svelte` — Top-Ort-Anzeige im `{#if subscription.last_run}`-Block
- **EDIT** `tests/tdd/test_scheduler_triggers.py` — `len==3` auf `len==4` anpassen

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `CompareSubscription` (`internal/model/subscription.go`) | intern | Basis-Struct; wird additiv um `TopOrtLetzterVersand string` mit `omitempty` erweitert |
| `store.LoadSubscription` / `store.SaveSubscription` (`internal/store/store.go`) | intern | Read-Modify-Write für das neue Feld; bestehende Subscription-JSONs ohne das Feld bleiben valide |
| `AlertPreviewProxyHandler` (`internal/handler/proxy.go`) | intern | Referenz-Implementierung für den neuen `SendSubscriptionProxyHandler` — gleiche Proxy-Struktur |
| `run_comparison_for_subscription()` (`src/services/compare_subscription.py`) | intern | Ruft die Compare-Engine auf; Return-Typ wird von 3-Tupel auf 4-Tupel erweitert (4. = Winner-Name) |
| `_save_subscription()` (`api/routers/scheduler.py`) | intern | RMW-Funktion, die nach einem Lauf Status und Felder in die Subscription-JSON zurückschreibt; wird um `top_ort_letzter_versand` ergänzt |
| `_send_subscription()` (`api/routers/scheduler.py`) | intern | Versendet die Compare-Mail; wird im neuen manuellen Trigger-Endpoint aufgerufen |
| `CompareSubscription` (`src/app/user.py`) | intern | Python-Dataclass; neues optionales Feld `top_ort_letzter_versand: Optional[str] = None` |
| `load_compare_subscriptions()` (`src/app/loader.py`) | intern | Deserialisierung; liest `top_ort_letzter_versand` via `.get()` |
| `Subscription` Interface (`frontend/src/lib/types.ts`) | intern | TypeScript-Typen; optionales Feld `top_ort_letzter_versand?: string` |
| `AutoReportCard.svelte` (`frontend/src/lib/components/compare/AutoReportCard.svelte`) | intern | Bestehende Sidepanel-Karte; zeigt Top-Ort im `{#if subscription.last_run}`-Block an |
| `test_scheduler_triggers.py` (`tests/tdd/test_scheduler_triggers.py`) | intern | Bestehender Test, der auf Tupel-Länge 3 prüft; muss auf Länge 4 angepasst werden |

## Implementation Details

### §1 `internal/model/subscription.go` — 1 neues Feld

```go
type CompareSubscription struct {
    // ... bestehende Felder unverändert ...
    TopOrtLetzterVersand string `json:"top_ort_letzter_versand,omitempty"`
}
```

`omitempty` stellt sicher, dass bestehende JSONs ohne dieses Feld weiterhin fehlerfrei deserialisiert werden. Leerer String entspricht "noch kein Versand".

### §2 `internal/handler/proxy.go` — neuer Handler `SendSubscriptionProxyHandler`

Analog zu `AlertPreviewProxyHandler`:

```go
func SendSubscriptionProxyHandler(pythonURL string) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        id := chi.URLParam(r, "id")
        userID := middleware.GetUserID(r.Context())
        target := pythonURL + "/api/scheduler/subscriptions/" + id + "/send?user_id=" + userID

        client := &http.Client{Timeout: 120 * time.Second}
        resp, err := client.Post(target, "application/json", nil)
        if err != nil {
            http.Error(w, "upstream error", http.StatusBadGateway)
            return
        }
        defer resp.Body.Close()
        w.WriteHeader(resp.StatusCode)
        io.Copy(w, resp.Body)
    }
}
```

120s Timeout wegen potenziell langer Compare-Engine-Laufzeit.

### §3 `cmd/server/main.go` — Route registrieren

```go
r.Post("/api/subscriptions/{id}/send", handler.SendSubscriptionProxyHandler(cfg.PythonCoreURL))
```

Einzige Änderung in dieser Datei.

### §4 `src/app/user.py` — CompareSubscription Dataclass

```python
@dataclass
class CompareSubscription:
    # ... bestehende Felder unverändert ...
    top_ort_letzter_versand: Optional[str] = None
```

`Optional[str]` aus `typing` importieren falls noch nicht vorhanden. Default `None` = noch kein Versand gelaufen.

### §5 `src/services/compare_subscription.py` — Return-Typ erweitern

Return-Typ von `run_comparison_for_subscription()` bisher: `tuple[str, str, str]` (subject, body_text, body_html).

Neuer Return-Typ: `tuple[str, str, str, str | None]` — 4. Element = Winner-Name:

```python
winner_name = result.winner.location.name if result.winner else None
return subject, body_text, body_html, winner_name
```

### §6 `src/app/loader.py` — Deserialisierung erweitern

Bei `load_compare_subscriptions()` den neuen Feldwert lesen:

```python
top_ort_letzter_versand=sub_data.get("top_ort_letzter_versand"),
```

Kein Default-Wert nötig — `.get()` ohne zweites Argument gibt `None` zurück, was dem Dataclass-Default entspricht.

### §7 `api/routers/scheduler.py` — 4 Stellen + Save + neuer Endpoint

**7a. Alle 4 Aufruf-Stellen von `run_comparison_for_subscription()` anpassen:**

Jede Stelle, die das 3-Tupel entpackt:
```python
# vorher:
subject, body_text, body_html = run_comparison_for_subscription(sub)
# nachher:
subject, body_text, body_html, winner_name = run_comparison_for_subscription(sub)
```

**7b. `_save_subscription()` um `top_ort_letzter_versand` erweitern:**

Im RMW-Block (Subscription-JSON laden, Eintrag via `id` finden, Felder setzen, zurückschreiben):
```python
if winner_name is not None:
    entry["top_ort_letzter_versand"] = winner_name
```

`sub.top_ort_letzter_versand = winner_name` vor dem `_save_subscription()`-Aufruf setzen.

**7c. Neuer Endpoint `POST /api/scheduler/subscriptions/{subscription_id}/send`:**

```python
@router.post("/subscriptions/{subscription_id}/send")
async def manual_send_subscription(subscription_id: str, user_id: str = Query(...)):
    subs = load_compare_subscriptions(user_id)
    sub = next((s for s in subs if s.id == subscription_id), None)
    if sub is None:
        raise HTTPException(status_code=404, detail="Subscription not found")

    try:
        subject, body_text, body_html, winner_name = run_comparison_for_subscription(sub)
        _send_subscription(sub, subject, body_text, body_html)
        sub.last_run = datetime.utcnow().isoformat() + "Z"
        sub.last_status = "ok"
        sub.top_ort_letzter_versand = winner_name
        _save_subscription(user_id, sub)
        return {"status": "ok", "winner": winner_name}
    except Exception as e:
        sub.last_status = "error"
        _save_subscription(user_id, sub)
        raise HTTPException(status_code=500, detail=str(e))
```

### §8 `frontend/src/lib/types.ts` — Interface-Erweiterung

```typescript
interface Subscription {
  // ... bestehende Felder ...
  top_ort_letzter_versand?: string;
}
```

### §9 `frontend/src/lib/components/compare/AutoReportCard.svelte` — Top-Ort-Anzeige

Im bestehenden `{#if subscription.last_run}`-Block, nach der Statusanzeige:

```svelte
{#if subscription.top_ort_letzter_versand}
  <span class="winner-label" data-testid="top-ort-{subscription.id}">
    Top-Ort: {subscription.top_ort_letzter_versand}
  </span>
{/if}
```

CSS-Eigenschaften für `.winner-label`:
```css
font-size: 0.75rem;
color: var(--g-ink-muted);
font-weight: 500;
```

`data-testid` enthält die Subscription-ID für gezielte Test-Selektion bei mehreren Karten.

### §10 `tests/tdd/test_scheduler_triggers.py` — Tupel-Länge anpassen

Alle Stellen, die `len(result) == 3` oder Tupel-Entpacken mit 3 Variablen prüfen:
```python
# vorher:
assert len(result) == 3
# nachher:
assert len(result) == 4
```

Entpack-Zeilen analog auf 4 Variablen anpassen.

### §11 Scope-Tabelle

| Datei | Änderung | LoC |
|-------|---------|-----|
| `internal/model/subscription.go` | +1 Feld | +1 |
| `internal/handler/proxy.go` | +1 Handler `SendSubscriptionProxyHandler` | +28 |
| `cmd/server/main.go` | +1 Route | +1 |
| `src/app/user.py` | +1 Feld | +1 |
| `src/services/compare_subscription.py` | Return-Typ + Winner-Extraktion | +3 |
| `src/app/loader.py` | +1 `.get()`-Aufruf | +1 |
| `api/routers/scheduler.py` | 4 Tupel-Stellen + `_save_subscription` + neuer Endpoint | +35 |
| `frontend/src/lib/types.ts` | +1 optionales Feld | +1 |
| `frontend/src/lib/components/compare/AutoReportCard.svelte` | Top-Ort-Anzeige | +8 |
| `tests/tdd/test_scheduler_triggers.py` | `len==3` → `len==4` | +1 |
| **Summe** | | **~80 LoC** |

## Expected Behavior

- **Input:**
  - Bestehende `CompareSubscription`-JSONs ohne `top_ort_letzter_versand` (bleibt `None` / leer, kein Fehler)
  - `POST /api/subscriptions/{id}/send` mit `user_id` als Query-Parameter (Go-Proxy setzt diesen)
  - Scheduler-Lauf wie bisher (4 bestehende Aufruf-Stellen, jetzt mit Winner-Name)
- **Output:**
  - `POST /api/subscriptions/{id}/send` → HTTP 200 `{"status": "ok", "winner": "<Ortsname>"}` bei Erfolg; HTTP 404 bei unbekannter ID; HTTP 500 bei Laufzeitfehler
  - Nach jedem Versand (manuell oder automatisch) enthält die Subscription-JSON `top_ort_letzter_versand` mit dem Namen des Gewinner-Orts (leer wenn kein eindeutiger Gewinner)
  - `AutoReportCard` zeigt `Top-Ort: <Name>` mit `data-testid="top-ort-{id}"` wenn `top_ort_letzter_versand` gesetzt ist
- **Side effects:**
  - `_save_subscription()` schreibt direkt in `data/users/{user_id}/compare_subscriptions.json` (kein HTTP-Call, konsistent mit bisherigem Python-Scheduler-Pattern)
  - Kein bestehender API-Endpoint wird geändert oder entfernt
  - Bestehende Subscriptions ohne `top_ort_letzter_versand`-Feld sind weiterhin fehlerfrei ladbar — keine Migration erforderlich

## Acceptance Criteria

**AC-1:** Given ein Nutzer hat einen aktiven Vergleichs-Preset gespeichert / When er im Sidepanel auf „Jetzt senden" klickt (oder `handleSaveBriefing` → `/compare/new` aufruft) / Then kann er einen neuen Vergleich als Preset anlegen, ohne dass bestehende Presets verändert werden.
  - Test: (populated after /tdd-red)

**AC-2:** Given der Nutzer öffnet das Sidepanel mit mindestens einem gespeicherten Preset / When die AutoReportCard-Komponente einen Preset mit gesetztem `last_run` und `top_ort_letzter_versand` rendert / Then zeigt die Karte den formatierten `last_run`-Zeitstempel und darunter `Top-Ort: <Ortsname>` mit `data-testid="top-ort-{subscription.id}"`.
  - Test: (populated after /tdd-red)

**AC-3:** Given eine gültige `subscription_id` für den eingeloggten Nutzer / When `POST /api/subscriptions/{id}/send` aufgerufen wird / Then wird die Compare-Engine ausgeführt, eine Mail versendet, `last_run`/`last_status`/`top_ort_letzter_versand` in die JSON gespeichert, und die Antwort ist HTTP 200 `{"status": "ok", "winner": "<Ortsname>"}`. Bei unbekannter ID ist die Antwort HTTP 404.
  - Test: (populated after /tdd-red)

**AC-4:** Given ein automatischer oder manueller Versand wurde erfolgreich abgeschlossen / When die Subscription-JSON danach von `load_compare_subscriptions()` eingelesen wird / Then enthält das resultierende `CompareSubscription`-Objekt `top_ort_letzter_versand` mit dem Namen des Gewinner-Orts, und eine bestehende Subscription ohne dieses Feld wird ohne Fehler mit `top_ort_letzter_versand=None` deserialisiert.
  - Test: (populated after /tdd-red)

## Known Limitations

- **Kein Retry bei Fehler:** Schlägt `_send_subscription()` fehl, wird `last_status: "error"` gesetzt und `top_ort_letzter_versand` nicht aktualisiert. Kein automatischer Retry — der nächste reguläre oder manuelle Lauf überschreibt den Status.
- **Winner ist `None` bei Gleichstand:** Wenn `result.winner` `None` zurückgibt (kein eindeutiger Gewinner), bleibt `top_ort_letzter_versand` leer und die AutoReportCard zeigt keinen Top-Ort an. Kein Fehler, kein Platzhalter.
- **Kein Frontend-Trigger-Button in diesem Issue:** Das Sidepanel zeigt den Top-Ort an, aber ein UI-Button für den manuellen Trigger (`POST /api/subscriptions/{id}/send`) ist nicht Teil dieses Issues. Der Endpoint ist vollständig funktionsfähig und kann in einem Folge-Issue eingebunden werden.
- **120s Timeout am Go-Proxy:** Großzügig dimensioniert für die Compare-Engine. Bei sehr vielen Orten im Vergleich kann die Python-Verarbeitung länger dauern — in diesem Fall schlägt der Proxy mit 504 fehl, ohne dass der Python-Prozess abbricht.

## Changelog

- 2026-05-30: Initial spec — Issue #456. Manueller Versand-Trigger `POST /api/subscriptions/{id}/send`, neues Feld `top_ort_letzter_versand` additiv über alle 4 Schichten, AutoReportCard-Anzeige. 10 Dateien, ~80 LoC netto.
