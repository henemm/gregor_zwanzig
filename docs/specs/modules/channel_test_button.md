---
entity_id: channel_test_button
type: module
created: 2026-04-22
updated: 2026-04-22
status: draft
version: "1.0"
tags: [sveltekit, account, email, signal, telegram, notify, test]
---

# Kanal-Test-Button — "Testmeldung senden" auf der Account-Seite

## Approval

- [ ] Approved

## Purpose

Ergaenzt die `/account`-Seite um einen "Test senden"-Button neben jedem konfigurierten Benachrichtigungs-Kanal (E-Mail, Signal, Telegram). Beim Klick wird ueber den jeweiligen Kanal eine echte Testnachricht verschickt, sodass der Nutzer ohne Umweg pruefen kann, ob seine Kanal-Konfiguration korrekt und funktionsfaehig ist.

## Scope

### In Scope

- `api/routers/notify.py` — Neuer FastAPI-Router mit `POST /api/notify/test` **(NEU, ~40 LoC)**
- `api/main.py` — Router registrieren **(EDIT, +2 LoC)**
- `internal/handler/proxy.go` — `ProxyPostHandler` korrigieren: Request-Body an Python weiterleiten **(EDIT, ~20 LoC)**
- `cmd/server/main.go` — Route `/api/notify/test` registrieren **(EDIT, +1 LoC)**
- `frontend/src/routes/account/+page.svelte` — Test-Buttons + Handler + Status-Feedback **(EDIT, ~40 LoC)**

### Out of Scope

- SMS/Satelliten-Kanaele — kein Backend vorhanden
- Kanalverifizierung mit Bestaetiungs-Code (separates Feature)
- Nutzer-gespeicherte Test-Templates (separates Feature)

## Source

- **File:** `api/routers/notify.py` **(NEU)**
- **File:** `api/main.py` **(EDIT)**
- **File:** `internal/handler/proxy.go` **(EDIT)**
- **File:** `cmd/server/main.go` **(EDIT)**
- **File:** `frontend/src/routes/account/+page.svelte` **(EDIT)**
- **Identifier:** `test_notify` (Python), `ProxyPostHandler` / `ProxyBodyPostHandler` (Go), `sendTest` (Svelte)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/outputs/email.py` | Python-Modul | `send(subject, body)` fuer E-Mail-Kanal |
| `src/outputs/signal.py` | Python-Modul | `send(subject, body)` fuer Signal-Kanal |
| `src/outputs/telegram.py` | Python-Modul | `send(subject, body)` fuer Telegram-Kanal |
| `Settings.with_user_profile(user_id)` | Python-Konfiguration | Laedt nutzer-spezifische Credentials (MailTo, SignalPhone, SignalAPIKey, TelegramChatID) |
| `internal/model/user.go` | Go-Datenmodell | `MailTo`, `SignalPhone`, `SignalAPIKey`, `TelegramChatID` — spiegelt, welche Felder konfiguriert sein koennen |
| `internal/handler/proxy.go` — `ProxyPostHandler` | Go-Handler | Wird korrigiert: leitet Request-Body an Python-API weiter statt `nil` |
| `$lib/api.ts` — `api.post()` | SvelteKit helper | Client-seitige POST-Anfragen mit automatischer Cookie-Weiterleitung |

## Implementation Details

### Schritt 1: `api/routers/notify.py` (NEU, ~40 LoC)

Neuer FastAPI-Router, der einen einzelnen POST-Endpunkt bereitstellt.

```python
from fastapi import APIRouter, Query
from pydantic import BaseModel
from src.app.config import Settings
from src.outputs import email as email_out
from src.outputs import signal as signal_out
from src.outputs import telegram as telegram_out

router = APIRouter()

SUBJECT = "Gregor 20 — Testmeldung"
BODY    = "Dein Kanal funktioniert!"

class TestRequest(BaseModel):
    channel: str  # "email" | "signal" | "telegram"

@router.post("/api/notify/test")
async def test_notify(
    req: TestRequest,
    user_id: str = Query(...),
):
    settings = Settings().with_user_profile(user_id)
    try:
        if req.channel == "email":
            email_out.send(SUBJECT, BODY, settings=settings)
        elif req.channel == "signal":
            signal_out.send(SUBJECT, BODY, settings=settings)
        elif req.channel == "telegram":
            telegram_out.send(SUBJECT, BODY, settings=settings)
        else:
            return {"error": f"Unbekannter Kanal: {req.channel}"}
        return {"status": "ok"}
    except Exception as exc:
        return {"error": str(exc)}
```

Hinweis zur `send()`-Signatur: Falls die bestehenden Output-Module `settings` noch nicht als Parameter akzeptieren, muss die Signatur entsprechend angepasst werden — analog zur bestehenden Nutzung in `Settings.with_user_profile`. Vor der Implementierung pruefen.

### Schritt 2: `api/main.py` (EDIT, +2 LoC)

```python
from api.routers import notify
app.include_router(notify.router)
```

Einfuegen nach den bestehenden `include_router`-Aufrufen, Reihenfolge ist nicht relevant.

### Schritt 3: `internal/handler/proxy.go` (EDIT, ~20 LoC)

`ProxyPostHandler` uebergibt aktuell `nil` als Body an `http.NewRequest`. Das muss auf `r.Body` geaendert werden, damit JSON-Payloads durchgeleitet werden.

Entweder `ProxyPostHandler` direkt korrigieren (falls keine anderen Aufrufer betroffen sind) oder eine neue Funktion `ProxyBodyPostHandler` anlegen:

```go
func ProxyBodyPostHandler(targetBase, targetPath string) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        userID := r.Context().Value(middleware.UserIDKey).(string)
        url := fmt.Sprintf("%s%s?user_id=%s", targetBase, targetPath, userID)
        proxyReq, err := http.NewRequest(http.MethodPost, url, r.Body)
        if err != nil {
            http.Error(w, "proxy error", http.StatusInternalServerError)
            return
        }
        proxyReq.Header.Set("Content-Type", r.Header.Get("Content-Type"))
        resp, err := http.DefaultClient.Do(proxyReq)
        if err != nil {
            http.Error(w, "upstream error", http.StatusBadGateway)
            return
        }
        defer resp.Body.Close()
        w.Header().Set("Content-Type", "application/json")
        w.WriteHeader(resp.StatusCode)
        io.Copy(w, resp.Body)
    }
}
```

Konkrete Vorgehensweise (neuer Handler vs. Patch des bestehenden) bei der Implementierung entscheiden, nachdem `ProxyPostHandler`-Aufrufer in `cmd/server/main.go` geprueft wurden.

### Schritt 4: `cmd/server/main.go` (EDIT, +1 LoC)

```go
r.Post("/api/notify/test", handler.ProxyBodyPostHandler(cfg.PythonCoreURL, "/api/notify/test"))
```

Einfuegen nach den bestehenden `/api/`-Routen-Registrierungen.

### Schritt 5: `frontend/src/routes/account/+page.svelte` (EDIT, ~40 LoC)

**Neuer State (Svelte 5 Runes):**

```typescript
type TestStatus = 'idle' | 'loading' | 'ok' | 'error';

let testStatus = $state<Record<string, TestStatus>>({
    email: 'idle',
    signal: 'idle',
    telegram: 'idle',
});
let testError = $state<Record<string, string | null>>({
    email: null,
    signal: null,
    telegram: null,
});
```

**Handler-Funktion:**

```typescript
async function sendTest(channel: string) {
    testStatus[channel] = 'loading';
    testError[channel] = null;
    try {
        await api.post('/api/notify/test', { channel });
        testStatus[channel] = 'ok';
        setTimeout(() => (testStatus[channel] = 'idle'), 4000);
    } catch (e: unknown) {
        const body = (e as { detail?: string; error?: string });
        testError[channel] = body?.detail ?? body?.error ?? 'Senden fehlgeschlagen';
        testStatus[channel] = 'error';
    }
}
```

**Button-Markup** (Beispiel fuer E-Mail, analog fuer Signal und Telegram):

```html
{#if mailTo}
  <button
    onclick={() => sendTest('email')}
    disabled={testStatus.email === 'loading'}
    class="ml-2 text-sm text-blue-600 hover:underline disabled:opacity-50"
  >
    {testStatus.email === 'loading' ? '…' : 'Test senden'}
  </button>
  {#if testStatus.email === 'ok'}
    <span class="ml-2 text-sm text-green-600">Gesendet</span>
  {/if}
  {#if testStatus.email === 'error'}
    <span class="ml-2 text-sm text-red-600">{testError.email}</span>
  {/if}
{/if}
```

Der Button erscheint inline neben dem jeweiligen Label oder Input-Feld. Er ist nur sichtbar wenn das Kanal-Feld einen Wert enthaelt (`{#if mailTo}`, `{#if signalPhone}`, `{#if telegramChatId}`). Das Status-Feedback (Erfolg/Fehler) erscheint inline direkt neben dem Button.

## Expected Behavior

- **Input:** Nutzer klickt "Test senden" neben einem konfigurierten Kanal.
- **Output:** Eine Testnachricht mit dem Text "Gregor 20 — Testmeldung" / "Dein Kanal funktioniert!" wird ueber den gewaehlten Kanal gesendet. Die UI zeigt inline "Gesendet" (gruen, verschwindet nach 4 Sekunden) oder eine Fehlermeldung (rot, bleibt bis zum naechsten Klick).
- **Side effects:** Eine echte Nachricht wird an die konfigurierte Adresse/Nummer gesendet. Keine Aenderungen an Nutzerdaten oder Konfiguration.

### Fehlerszenarien

| Szenario | Verhalten |
|----------|-----------|
| Kanal nicht konfiguriert | Button wird nicht angezeigt (`{#if}`-Bedingung) |
| Falscher API Key / Zustellfehler | Python gibt `{"error": "..."}` zurueck; Fehlermeldung erscheint inline neben dem Button |
| Python nicht erreichbar | Go-Proxy liefert 502; `api.post()` wirft Exception; generische Fehlermeldung "Senden fehlgeschlagen" |
| Unbekannter Kanal-String | Python gibt `{"error": "Unbekannter Kanal: ..."}` zurueck |

## Known Limitations

- Die Testnachricht ist fest kodiert (kein nutzer-editierbarer Text) — ausreichend fuer Kanal-Verifikation.
- `signal_api_key` ist write-only: Das Frontend kann nicht pruefen, ob ein Key gespeichert ist. Der "Test senden"-Button fuer Signal erscheint nur wenn `signal_phone` gesetzt ist, nicht basierend auf dem Key.
- Kein Rate-Limiting auf dem Test-Endpoint — bei Missbrauch koennte der Kanal-Provider Limits verhaengen. Fuer den MVP akzeptabel.

## Changelog

- 2026-04-22: Initial spec (Kanal-Test-Button, GitHub Issue zu erstellen)
