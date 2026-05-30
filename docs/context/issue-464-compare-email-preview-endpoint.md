# Context: Issue #464 — Compare-E-Mail Observability-Endpoint

## Request Summary

Neuer Endpoint `POST /api/_validator/compare-email-preview`, der den Compare-HTML-Renderer
direkt aufruft und das gerenderte HTML zurückgibt — damit der Validator AC-1..4 per `curl | grep`
prüfen kann, ohne einen echten Scheduler-Lauf abzuwarten.

## Scope

Go-API (Proxy-Handler + Router-Eintrag) + Python FastAPI (Request-Body-Modell + Handler in `validator.py`).
Kein Frontend, keine Datenbank-Zugriffe.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `api/routers/validator.py` | Ziel: neuer Python-Handler hier eintragen |
| `cmd/server/main.go` Zeile 141-143 | Ziel: neuer Go-Router-Eintrag (`r.Post`) |
| `internal/handler/proxy.go` Zeile 262-301 | Muster: `AlertPreviewProxyHandler` — identisches Pattern nutzen |
| `src/output/renderers/email/compare_html.py` Zeile 552 | `render_compare_html()` — die Funktion, die aufgerufen wird |
| `src/app/user.py` Zeile 147-197 | `LocationResult` + `ComparisonResult` Datenstrukturen |
| `src/app/profile.py` | `ActivityProfile` Enum (wintersport, wandern, summer_trekking, allgemein) |

## Existing Patterns

### Go-Proxy (analog `AlertPreviewProxyHandler`)
```go
func XxxProxyHandler(pythonURL string) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        // Kein URLParam, kein user_id-Injection nötig (kein Trip-Kontext)
        url := pythonURL + "/api/_validator/compare-email-preview"
        req, _ := http.NewRequestWithContext(r.Context(), http.MethodPost, url, r.Body)
        req.Header.Set("Content-Type", r.Header.Get("Content-Type"))
        client := &http.Client{Timeout: 30 * time.Second}
        // resp durchleiten...
    }
}
```

### Python-Handler (analog `alert_preview`)
```python
@router.post("/api/_validator/compare-email-preview")
async def compare_email_preview(body: CompareEmailPreviewBody):
    result = _build_stub_comparison_result(body)
    html = render_compare_html(result, profile=profile, winner_tags=body.winner_tags)
    return {"html": html}
```

### Bestehende `_validator`-Endpoints in main.go
```
GET  /api/_validator/format-metric
GET  /api/_validator/detector-thresholds
GET  /api/_validator/metrics-for-channel
```
Neue Zeile wird: `r.Post("/api/_validator/compare-email-preview", handler.CompareEmailPreviewProxyHandler(cfg.PythonCoreURL))`

## Request Body (laut Issue)

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

Kein `locations`-Array im Request — der Handler baut intern einen Stub-`ComparisonResult`
mit 1-2 Dummy-`LocationResult`s, damit `render_compare_html()` die Winner-Card + Matrix
rendert.

## Stub-Strategie für ComparisonResult

`render_compare_html()` braucht ein `ComparisonResult` mit mind. einem `LocationResult` (für `winner`-Property).
Minimalstub:
- 1 `LocationResult` mit `score=100`, `temp_max=15.0`, restliche Felder `None`
- `time_window` + `target_date` aus Request
- `winner_tags` direkt an `render_compare_html()` weitergeben (werden nicht aus `LocationResult` generiert)

## AC-Farbe (AC-2)
```python
# In compare_html.py:
_TAG_COLORS = {
    "good": {"bg": "#dcf2e1", ...},  # Das ist der Prüfwert aus AC-2
    "warn": {"bg": "#fde6cc", ...},
}
```
Wenn `winner_tags` mit `tone: "good"` übergeben wird → `#dcf2e1` muss im HTML erscheinen.

## AC-3: Nur unter `_validator/` erreichbar

Das ist bereits durch den Pfad `/api/_validator/compare-email-preview` garantiert.
Kein separater Auth-Guard nötig — alle `_validator/`-Routen sind intern dokumentiert als
"nicht für Produktions-User-Routing" (kein Frontend-Link, kein Public-Docs-Eintrag).

## Dependencies

- **Upstream:** `render_compare_html()` aus `compare_html.py`, `ActivityProfile` Enum
- **Downstream:** Validator-Tests (Issue #460 Follow-up)

## Risks & Considerations

1. **Stub-Daten müssen render-kompatibel sein** — `render_compare_html()` erwartet `LocationResult.location` (ein `SavedLocation`-Objekt). Stub muss valides `SavedLocation` bauen.
2. **Go-Proxy braucht kein user_id** — Endpoint ist rein renderer-seitig, kein DB-Zugriff → kein Auth-Kontext nötig (analog `format-metric` GET).
3. **Go braucht kein `chi.URLParam`** — Pfad ist statisch (kein `{id}`).
4. **Kein Heartbeat, kein BetterStack** — rein interner Validator-Endpoint.
