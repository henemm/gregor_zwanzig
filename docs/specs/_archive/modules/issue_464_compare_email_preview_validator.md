---
entity_id: issue_464_compare_email_preview_validator
type: module
created: 2026-05-30
updated: 2026-05-30
status: implemented
version: "1.0"
tags: [validator, api, observability, compare, email, tooling]
---

# Compare-E-Mail Preview Endpoint für Validator (Issue #464)

## Approval

- [x] Approved

## Purpose

Neuer Observability-Endpoint `POST /api/_validator/compare-email-preview`, der
den Compare-E-Mail-HTML-Render direkt zurückgibt — ohne echten Scheduler-Lauf,
ohne Wetterdaten-Fetch, ohne SMTP-Versand. Er schließt die Validator-Lücke aus
Issue #460 (Compare-E-Mail: Begründungs-Tags + Header-Sektion): Der External
Validator konnte bisher nicht maschinell prüfen, ob `winner_tags` mit dem Ton
`"good"` die korrekte Hintergrundfarbe `#dcf2e1` produzieren, weil kein
steuerbarer Render-Endpunkt existierte.

## Source

- **File:** `api/routers/validator.py`, `internal/handler/proxy.go`, `cmd/server/main.go`
- **Identifier:**
  - Python: `compare_email_preview` (neuer Endpoint in `validator.py`)
  - Go: `CompareEmailPreviewProxyHandler` (neuer Handler in `proxy.go`) + 1 neue Router-Zeile in `main.go`

## Estimated Scope

- **LoC:** ~56 (25 Python, 31 Go)
- **Files:** 3
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src.output.renderers.email.compare_html.render_compare_html` | aufgerufen | Einziger Renderer-Einstiegspunkt für Compare-E-Mail HTML; nimmt `ComparisonResult`, `profile`, `winner_tags`. |
| `src.app.user.ComparisonResult` | konsumiert | DTO für den Compare-Lauf; wird im Handler als Stub ohne echte Wetterdaten konstruiert. |
| `src.app.user.LocationResult` | konsumiert | Einzelnes Orts-Ergebnis innerhalb `ComparisonResult`; `error=None` muss explizit gesetzt werden, damit `result.winner` nicht None ist. |
| `src.app.user.SavedLocation` | konsumiert | Minimaler Stub-Ort (`id="preview-1"`, `name="Vorschau-Ort"`, `lat=47.0`, `lon=11.0`, `elevation_m=2000`). |
| `src.app.profile.ActivityProfile` | konsumiert | Enum für das übergebene `profile`-Feld (z. B. `"wintersport"` → `ActivityProfile.WINTERSPORT`). |
| `internal/handler/proxy.go::AlertPreviewProxyHandler` | Referenz | Vorbild-Pattern für Body-Forwarding-Proxy mit Auth und Timeout 10s; `CompareEmailPreviewProxyHandler` folgt exakt dieser Struktur. |
| `internal/middleware/auth.go::AuthMiddleware` | genutzt | Globale `gz_session`-Cookie-Auth — `/_validator/`-Pfad ist NICHT auf der Whitelist, daher automatisch geschützt. |
| `cmd/server/main.go` Zeilen 141–143 | Referenz | Bestehende `_validator`-Routen; neue Route wird unmittelbar dahinter eingehängt. |

## Implementation Details

### `api/routers/validator.py` — Neuer Endpoint

Pydantic-Modell `CompareEmailPreviewBody` aufnehmen, dann Handler:

```python
from datetime import date as date_type
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from src.app.profile import ActivityProfile
from src.app.user import ComparisonResult, LocationResult, SavedLocation
from src.output.renderers.email.compare_html import render_compare_html

class WinnerTag(BaseModel):
    tone: str   # "good" | "warn" | "bad" | "neutral"
    label: str

class CompareEmailPreviewBody(BaseModel):
    profile: str                    # ActivityProfile-Name, z. B. "wintersport"
    time_window: list[int]          # [start_hour, end_hour], z. B. [9, 16]
    target_date: str                # ISO-8601, z. B. "2026-05-31"
    winner_tags: list[WinnerTag] = []

@router.post("/api/_validator/compare-email-preview")
async def compare_email_preview(body: CompareEmailPreviewBody):
    profile_enum = ActivityProfile[body.profile.upper()]

    stub_location = SavedLocation(
        id="preview-1",
        name="Vorschau-Ort",
        lat=47.0,
        lon=11.0,
        elevation_m=2000,
    )
    loc_result = LocationResult(
        location=stub_location,
        score=85,
        error=None,           # KRITISCH: None → result.winner ist nicht None
    )
    result = ComparisonResult(
        locations=[loc_result],
        time_window=tuple(body.time_window),   # Pydantic liefert list → cast zu tuple
        target_date=date_type.fromisoformat(body.target_date),
    )

    winner_tags_raw = [{"tone": t.tone, "label": t.label} for t in body.winner_tags]
    html = render_compare_html(result, profile=profile_enum, winner_tags=winner_tags_raw)
    return {"html": html}
```

**Wichtige Randbedingungen:**
- `time_window` muss explizit als `tuple()` gecastet werden, weil Pydantic eine `list` liefert und `render_compare_html` intern `tuple`-Semantik erwartet.
- `error=None` auf `LocationResult` muss explizit gesetzt sein. Fehlt es, liefert `result.winner` `None`, und der Renderer erzeugt keinen Winner-Block — AC-2 würde nicht greifen.
- `winner_tags` wird als Liste von Dicts (`[{"tone": ..., "label": ...}]`) an den Renderer übergeben, weil `render_compare_html` dieses Format erwartet (kein Pydantic-Modell auf Python-Seite des Renderers).

### `internal/handler/proxy.go` — Neuer Proxy-Handler

Analog `AlertPreviewProxyHandler` (Zeile 265 in `proxy.go`). Kein `user_id`-Inject
(kein Trip-Kontext vorhanden). Body + `Content-Type` werden 1:1 durchgereicht.
Timeout 10 Sekunden. Es gibt keinen `proxyPost`-Helper — das Pattern wird wie bei
`AlertPreviewProxyHandler` ausgeschrieben:

```go
func CompareEmailPreviewProxyHandler(pythonURL string) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        url := pythonURL + "/api/_validator/compare-email-preview"
        req, err := http.NewRequestWithContext(r.Context(), http.MethodPost, url, r.Body)
        if err != nil {
            w.Header().Set("Content-Type", "application/json")
            w.WriteHeader(http.StatusInternalServerError)
            w.Write([]byte(`{"error":"proxy_error"}`))
            return
        }
        req.Header.Set("Content-Type", r.Header.Get("Content-Type"))
        client := &http.Client{Timeout: 10 * time.Second}
        resp, err := client.Do(req)
        if err != nil {
            w.Header().Set("Content-Type", "application/json")
            w.WriteHeader(http.StatusBadGateway)
            w.Write([]byte(`{"error":"upstream unreachable"}`))
            return
        }
        defer resp.Body.Close()
        ct := resp.Header.Get("Content-Type")
        if ct == "" { ct = "application/json" }
        w.Header().Set("Content-Type", ct)
        w.WriteHeader(resp.StatusCode)
        io.Copy(w, resp.Body)
    }
}

### `cmd/server/main.go` — Neue Router-Zeile

Unmittelbar nach den bestehenden `_validator`-Routen (Zeilen 141–143):

```go
r.Post("/api/_validator/compare-email-preview",
    handler.CompareEmailPreviewProxyHandler(cfg.PythonCoreURL))
```

## Expected Behavior

- **Input:** `POST /api/_validator/compare-email-preview` mit JSON-Body:
  ```json
  {
    "profile": "wintersport",
    "time_window": [9, 16],
    "target_date": "2026-05-31",
    "winner_tags": [
      {"tone": "good", "label": "1 Ort über Wolken"},
      {"tone": "warn", "label": "Böen 26 km/h"}
    ]
  }
  ```
  Gültiges `gz_session`-Cookie erforderlich (globale AuthMiddleware).
- **Output:** `200 OK` mit Body `{"html": "<!DOCTYPE html>..."}` — vollständiger
  HTML-String der Compare-E-Mail, identisch zum Production-Render-Pfad via
  `render_compare_html`.
- **Side effects:** Keine. Kein Wetterdaten-Fetch, kein SMTP-Call, kein
  Scheduler-State-Update, kein Datei-Write. Endpoint kann beliebig oft
  wiederholt werden, ohne den Production-Zustand zu ändern.
- **Fehlerfall 401:** Kein oder ungültiges `gz_session`-Cookie — globale
  `AuthMiddleware` antwortet vor dem Handler.
- **Fehlerfall 422:** Ungültiger Body (fehlendes Pflichtfeld, falsche Typen) —
  FastAPI-Standard-Validierungsfehler.

## Acceptance Criteria

- **AC-1:** Given ein eingeloggter Validator (gültiges `gz_session`-Cookie) und ein valider JSON-Body mit `profile`, `time_window`, `target_date` und optionalem `winner_tags` / When er `POST /api/_validator/compare-email-preview` aufruft / Then antwortet der Server mit `200 OK` und einem Body der Form `{"html": "..."}`, wobei der HTML-String mindestens `<!DOCTYPE html>` enthält und nicht leer ist.
  - Test: (populated after /tdd-red)

- **AC-2:** Given ein eingeloggter Validator und ein Body, in dem `winner_tags` mindestens ein Element mit `{"tone": "good", "label": "..."}` enthält / When er `POST /api/_validator/compare-email-preview` aufruft / Then enthält das zurückgegebene HTML die Farbe `#dcf2e1` (Hintergrundfarbe für `tone=good`-Begründungs-Tags gemäß Issue #460).
  - Test: (populated after /tdd-red)

- **AC-3:** Given der Endpoint ist im System registriert / When ein Client versucht, ihn über einen Pfad außerhalb von `/_validator/` zu erreichen (z. B. `POST /api/compare-email-preview`) / Then antwortet der Server mit `404 Not Found` — der Endpoint ist ausschließlich unter dem `/_validator/`-Präfix erreichbar und erscheint nicht im Production-User-Routing.
  - Test: (populated after /tdd-red)

## Known Limitations

- **Stub ohne echte Wetterdaten:** `LocationResult.score` ist fix auf `85` gesetzt.
  Der Renderer zeigt damit immer einen einzigen Stub-Ort als Winner. Für die
  Validator-Zwecke (Farb- und Struktur-Prüfung der Winner-Tags) ist das
  ausreichend — eine vollständige Mehrorts-Comparison ist nicht im Scope.
- **`profile`-Enum-Lookup via `ActivityProfile[body.profile.upper()]`:** Bei
  unbekanntem Profilnamen wirft Python `KeyError`, das FastAPI als `500` surfact.
  Eine sprechere `422`-Validierung wäre sauberer, ist aber kein Blocker für
  den Validator-Use-Case (Validator übergibt immer valide Profilnamen).
- **`render_compare_html`-Signatur:** Wenn sich die Signatur von `render_compare_html`
  ändert (insbesondere das `winner_tags`-Format), muss der Endpoint mitgezogen
  werden. Tests in Phase 5 sichern das ab.
- **Production-Verfügbarkeit:** Der Endpoint ist auf Prod erreichbar (gleicher
  Code-Pfad), aber ohne Validator-Session dort funktional irrelevant. Die
  Memory-Regel „Validator nur gegen Staging" gilt weiterhin.

## Changelog

- 2026-05-30: Initial spec — Issue #464 (Compare-E-Mail Observability-Endpoint)
