---
entity_id: issue_363_signal_telegram_preview
type: module
created: 2026-05-25
updated: 2026-05-25
status: draft
version: "1.0"
tags: [output, preview, signal, telegram, epic-331, issue-361]
---

# Signal/Telegram-Vorschau-Endpoints

## Approval

- [x] Approved (User, 2026-05-25)

## Purpose

Schritt A von #361 (Teil 2 von Epic #331). Stellt die Vorschau von Signal- und
Telegram-Briefings serverseitig bereit — über den bereits gebauten #360-Renderer
(`render_narrow` via `format_email`). Damit zeigt die spätere Live-Vorschau im Editor
(Schritt C, #365) exakt den schmalen Text, der beim Empfänger ankommt — ohne die
Renderer-Logik im Frontend zu duplizieren. Analog zu den vorhandenen email/sms-Endpoints,
ohne Versand.

## Source

- **Geändert:** `src/services/preview_service.py` — +`render_signal_preview()`, +`render_telegram_preview()` (nutzen die vorhandene `_build_report()`-Pipeline, geben `report.signal_text` / `report.telegram_text` + Stats zurück)
- **Geändert:** `api/routers/preview.py` — +`GET /api/preview/{trip_id}/signal`, +`.../telegram` (analog zu sms-Endpoint, JSON-Antwort)
- **Geändert:** `cmd/server/main.go` — +2 Routen `PreviewProxyHandler(cfg.PythonCoreURL, "signal"|"telegram")`
- **Unverändert genutzt:** `internal/handler/preview_proxy.go` (`PreviewProxyHandler` ist über `channel` parametrisiert)
- **Geändert:** `frontend/src/lib/components/preview/previewHelpers.ts` — `buildPreviewUrl` akzeptiert `'signal' | 'telegram'`

> Schicht: Python-Backend (`src/`, `api/`) + Go-API (`cmd/`) + Frontend-Helper (`frontend/`). Kein UI-Screen in diesem Schritt.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/renderers/narrow.py` `render_narrow` (#360) | module | erzeugt den schmalen Body; via `format_email` in `signal_text`/`telegram_text` |
| `PreviewService._build_report` | method | gemeinsame Pipeline segments→weather→format_email→TripReport |
| `PreviewProxyHandler` (Go) | handler | channel-parametrisierter Proxy → Python |

## Implementation Details

```python
# src/services/preview_service.py
def render_signal_preview(self, trip_id, *, user_id, report_type, target_date=None) -> tuple[str, str]:
    if report_type not in VALID_REPORT_TYPES:
        raise ValueError(...)
    report, _, _ = self._build_report(trip_id, user_id=user_id, report_type=report_type, target_date=target_date)
    return report.email_subject, (report.signal_text or "")

# render_telegram_preview analog → report.telegram_text
```

```python
# api/routers/preview.py — analog zum sms-Endpoint
@router.get("/api/preview/{trip_id}/signal")
async def preview_signal(trip_id, user_id=Query(...), type=Query("morning"), date=Query(None)):
    # type-Validierung; _build_service(user_id); render_signal_preview(...)
    return {"subject": subject, "body": body, "char_count": len(body),
            "max_line_width": max((len(l) for l in body.splitlines()), default=0)}
    # gleiche HTTPException-Mappings wie email/sms (404 FileNotFound/Lookup, 422 Value, 503 Runtime)
```

```go
// cmd/server/main.go — neben den email/sms-Zeilen
r.Get("/api/preview/{trip_id}/signal",   handler.PreviewProxyHandler(cfg.PythonCoreURL, "signal"))
r.Get("/api/preview/{trip_id}/telegram", handler.PreviewProxyHandler(cfg.PythonCoreURL, "telegram"))
```

```typescript
// previewHelpers.ts
export function buildPreviewUrl(channel: 'email'|'sms'|'signal'|'telegram', tripId, type, date?) { ... }
```

## Expected Behavior

- **Input:** `trip_id`, `user_id` (vom Proxy), `type` (morning|evening), optional `date`
- **Output:** Signal/Telegram → JSON `{subject, body, char_count, max_line_width}`, `body` = schmaler Monospace-Text aus `render_narrow`
- **Side effects:** keine (kein Versand, kein Persistieren)

## Acceptance Criteria

- **AC-1:** Given ein existierender Trip / When `GET /api/preview/{trip_id}/signal?type=morning` aufgerufen wird / Then antwortet der Python-Endpoint 200 mit `body == report.signal_text` und jede Zeile von `body` ist ≤26 Zeichen breit.
  - Test: (populated after /tdd-red)

- **AC-2:** Given ein existierender Trip / When `GET /api/preview/{trip_id}/telegram?type=evening` aufgerufen wird / Then antwortet 200 mit `body == report.telegram_text` (ungleich leer).
  - Test: (populated after /tdd-red)

- **AC-3:** Given derselbe Trip / When signal-, sms- und email-Vorschau abgerufen werden / Then unterscheidet sich der Signal-`body` vom sms-`token_line` und vom email-HTML (eigenständiges Kanal-Rendering, nicht der E-Mail-Text).
  - Test: (populated after /tdd-red)

- **AC-4:** Given ein ungültiger `type` bzw. eine unbekannte `trip_id` / When der signal/telegram-Endpoint aufgerufen wird / Then 422 (ungültiger type) bzw. 404 (unbekannter Trip), konsistent mit den email/sms-Endpoints.
  - Test: (populated after /tdd-red)

- **AC-5:** Given die Go-API / When `GET /api/preview/{id}/signal` bzw. `/telegram` über den Proxy läuft / Then wird an `<python>/api/preview/{id}/{channel}` weitergeleitet, `user_id` aus dem Auth-Context injiziert und Query (`type`,`date`) verbatim durchgereicht.
  - Test: (populated after /tdd-red)

- **AC-6:** Given `buildPreviewUrl` / When mit `'signal'` bzw. `'telegram'` aufgerufen / Then liefert es `/api/preview/{tripId}/signal?type=...` bzw. `.../telegram?...` (korrekt enkodiert).
  - Test: (populated after /tdd-red)

## Known Limitations

- Keine Demoted-Count-/Warn-Badge-Daten im Endpoint — der Überlauf-Hinweis (⚠ N Spalten) wird in Schritt C aus dem Editor-State berechnet, nicht aus der Vorschau.
- Pro-Kanal-Overrides bleiben out of scope (V2, vgl. #331).

## Changelog

- 2026-05-25: Initial spec created (Schritt A von #361 / Epic #331, Issue #363)
