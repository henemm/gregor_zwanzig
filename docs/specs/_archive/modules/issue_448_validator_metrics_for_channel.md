---
entity_id: issue_448_validator_metrics_for_channel
type: module
created: 2026-05-29
updated: 2026-05-29
status: active
version: "1.0"
tags: [validator, api, observability, metrics, channel, display-config]
---

# Validator Metrics-for-Channel Endpoint (Issue #448)

## Approval

- [x] Approved

## Purpose

Neuer Read-only-Endpoint `GET /api/_validator/metrics-for-channel`, der die dreistufige Kaskade von `get_metrics_for_channel(channel, report_type)` von außen prüfbar macht. Er existiert, damit der External Validator ohne Einblick in interne Python-State nachvollziehen kann, welche Metriken ein Trip für einen bestimmten Kanal und Report-Typ liefert und auf welcher Kaskadenstufe (per_report / per_channel / global) diese Konfiguration ermittelt wurde.

## Source

- **File:** `api/routers/validator.py` (neuer Endpoint + `_determine_cascade_source()`), `internal/handler/proxy.go` (neuer `MetricsForChannelProxyHandler`), `cmd/server/main.go` (neue Route-Zeile)
- **Identifier:**
  - Python: `metrics_for_channel` (FastAPI-Endpoint), `_determine_cascade_source`
  - Go: `MetricsForChannelProxyHandler`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src.app.models.UnifiedWeatherDisplayConfig.get_metrics_for_channel` | aufgerufen | Liefert die endgültige `List[MetricConfig]` nach Kaskade; `metric_ids` wird daraus via `[mc.metric_id for mc in metrics]` extrahiert. Keine Änderung an der Funktion selbst. |
| `api/routers/validator._load_trip_for_validator` | wiederverwendet | Bereits vorhandener modul-privater Helper (Issue #221) — liest Trip User-scoped, ohne Auto-Migrations-Side-Effects die den Kaskaden-Source verfälschen würden. |
| `api/routers/validator._load_trip_raw` | wiederverwendet | Liest die rohe Trip-JSON-Datei ohne Parsing. Wird von `_determine_cascade_source` genutzt, um den User-Intent aus dem rohen JSON zu lesen. |
| `internal/middleware/auth.AuthMiddleware` | genutzt | Globale `gz_session`-Cookie-Auth — `_validator/`-Pfade stehen nicht auf der Whitelist, kein zusätzlicher Eintrag nötig. |
| `internal/handler.appendUserID` | genutzt | Anti-Spoofing-Pattern (Bug #199) — Go-Proxy injiziert authentifizierten `user_id` als Query-Param, verhindert User-ID-Spoofing durch den Caller. |
| `src.app.models.UnifiedWeatherDisplayConfig` | konsumiert | Träger der Kaskaden-Konfiguration (`per_report_layouts`, `per_channel_layouts`). Wird aus dem hydrierten Trip gelesen. |
| `src.app.loader.get_trips_dir` | transitiv | Wird intern von `_load_trip_raw` genutzt, um den User-scoped Dateipfad aufzulösen. |

## Implementation Details

### Kaskaden-Logik und `_determine_cascade_source`

Die Kaskade spiegelt die Prioritätsreihenfolge, die `get_metrics_for_channel` intern anwendet:

1. `display_config.per_report_layouts[report_type][channel]` — höchste Priorität (Issue #434)
2. `display_config.per_channel_layouts[channel]` — zweite Stufe (Issue #429)
3. Globaler Fallback via `get_metrics_for_report_type(report_type)`

Eine leere Liste (`[]`) auf Stufe 1 oder 2 ist ein expliziter User-Wunsch — kein Fallback auf die nächste Stufe. `source` bleibt `"per_report"` bzw. `"per_channel"`, `metric_ids` ist `[]`.

Private Hilfsfunktion `_determine_cascade_source` in `api/routers/validator.py`:

```python
def _determine_cascade_source(
    dc: UnifiedWeatherDisplayConfig | None,
    channel: str,
    report_type: str,
) -> str:
    """Ermittelt, welche Kaskadenstufe get_metrics_for_channel für diesen
    channel+report_type anwendet. Gibt 'per_report', 'per_channel' oder
    'global' zurück. Kein Breaking Change an models.py."""
    if dc is None:
        return "global"
    per_report = (dc.per_report_layouts or {}).get(report_type, {})
    if channel in per_report:
        return "per_report"
    per_channel = dc.per_channel_layouts or {}
    if channel in per_channel:
        return "per_channel"
    return "global"
```

### `api/routers/validator.py` — neuer Endpoint

```python
@router.get("/api/_validator/metrics-for-channel")
async def metrics_for_channel(
    trip: str = Query(..., description="Trip-ID"),
    channel: str = Query(..., description="email|telegram|signal|sms"),
    report: str = Query(..., description="morning|evening"),
    user_id: str = Query(..., description="Vom Go-Proxy injiziert (Anti-Spoofing)"),
):
    """Macht die dreistufige get_metrics_for_channel-Kaskade von außen prüfbar."""
    trip_obj = _load_trip_for_validator(user_id, trip)
    if trip_obj is None:
        raise HTTPException(404, f"Trip {trip} nicht gefunden für User {user_id}")

    dc = trip_obj.display_config  # kann None sein (Loader injiziert Default)
    source = _determine_cascade_source(dc, channel, report)

    metrics = dc.get_metrics_for_channel(channel, report) if dc else []
    metric_ids = [mc.metric_id for mc in metrics]

    return {"source": source, "metric_ids": metric_ids}
```

### `internal/handler/proxy.go` — neuer Proxy-Handler

Analog zu `DetectorThresholdsProxyHandler` (Issue #221). Der Handler leitet alle Query-Parameter (inkl. `user_id`) unverändert weiter.

```go
// GET /api/_validator/metrics-for-channel?trip=<id>&channel=<ch>&report=<r>
func MetricsForChannelProxyHandler(pythonURL string) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        query := appendUserID(r.URL.RawQuery, middleware.UserIDFromContext(r.Context()))
        url := pythonURL + "/api/_validator/metrics-for-channel?" + query
        proxyGetRequest(w, r, url)
    }
}
```

### `cmd/server/main.go` — neue Route-Zeile

```go
r.Get("/api/_validator/metrics-for-channel", handler.MetricsForChannelProxyHandler(cfg.PythonCoreURL))
```

Diese Zeile wird nach den bestehenden `_validator`-Routen aus Issue #221 eingefügt.

## Expected Behavior

- **Input:** `GET /api/_validator/metrics-for-channel?trip=<id>&channel=<ch>&report=<r>` mit gültigem `gz_session`-Cookie. `user_id` wird vom Go-Proxy aus dem Auth-Context injiziert.
- **Output:**
  - `200 OK` mit Body `{"source": "per_report|per_channel|global", "metric_ids": ["temperature", ...]}`
  - `404 Not Found` wenn der Trip im User-Scope nicht existiert
  - `401 Unauthorized` bei fehlendem oder ungültigem `gz_session`-Cookie (durch globale `AuthMiddleware`)
- **Side effects:** Keine. Read-only-Endpoint, kein Schreiben, kein SMTP, kein Snapshot-Update.

## Acceptance Criteria

- **AC-1:** Given ein eingeloggter Validator und ein Trip ohne `display_config` (oder `display_config` ist None) / When er `GET /api/_validator/metrics-for-channel?trip=<id>&channel=email&report=morning` aufruft / Then antwortet der Server mit `200 OK` und Body `{"source": "global", "metric_ids": [...]}` — `metric_ids` enthält die globalen Fallback-Metriken für `morning`, `source` ist exakt `"global"`.
  - Test: (populated after /tdd-red)

- **AC-2:** Given ein eingeloggter Validator und ein Trip mit `display_config.per_channel_layouts["email"] = [MetricConfig(...)]` aber ohne Eintrag in `per_report_layouts` / When er `GET /api/_validator/metrics-for-channel?trip=<id>&channel=email&report=morning` aufruft / Then antwortet der Server mit `200 OK` und Body `{"source": "per_channel", "metric_ids": [...]}` — `metric_ids` spiegelt exakt den `per_channel_layouts["email"]`-Eintrag, `source` ist `"per_channel"`.
  - Test: (populated after /tdd-red)

- **AC-3:** Given ein eingeloggter Validator und ein Trip mit `display_config.per_report_layouts["morning"]["email"] = [MetricConfig(...)]` (und zusätzlich ein `per_channel_layouts["email"]`-Eintrag) / When er `GET /api/_validator/metrics-for-channel?trip=<id>&channel=email&report=morning` aufruft / Then antwortet der Server mit `200 OK` und Body `{"source": "per_report", "metric_ids": [...]}` — `per_report` schlägt `per_channel`, `source` ist `"per_report"`.
  - Test: (populated after /tdd-red)

- **AC-4:** Given ein eingeloggter Validator und ein Trip mit `display_config.per_report_layouts["morning"]["telegram"] = [...]` aber KEIN `["morning"]["email"]` und KEIN `per_channel_layouts["email"]` / When er `GET /api/_validator/metrics-for-channel?trip=<id>&channel=email&report=morning` aufruft / Then antwortet der Server mit `200 OK` und Body `{"source": "global", "metric_ids": [...]}` — der telegram-Eintrag in per_report hat keinen Einfluss auf email, Fallback auf global.
  - Test: (populated after /tdd-red)

- **AC-5:** Given ein eingeloggter Validator und ein Trip mit `display_config.per_report_layouts["morning"]["email"] = []` (leere Liste — expliziter User-Wunsch) / When er `GET /api/_validator/metrics-for-channel?trip=<id>&channel=email&report=morning` aufruft / Then antwortet der Server mit `200 OK` und Body `{"source": "per_report", "metric_ids": []}` — kein Fallback auf per_channel oder global, leere Liste wird respektiert.
  - Test: (populated after /tdd-red)

- **AC-6:** Given ein eingeloggter Validator und eine Trip-ID, die im User-Scope nicht existiert / When er `GET /api/_validator/metrics-for-channel?trip=nonexistent&channel=email&report=morning` aufruft / Then antwortet der Server mit `404 Not Found`.
  - Test: (populated after /tdd-red)

## Known Limitations

- **`display_config is None`:** Der Loader injiziert in der Regel eine Default-`display_config` — Trips ohne jede Konfiguration sind im Production-Betrieb selten. Der defensiv-Fallback `if dc else []` in der Implementierung deckt diesen Fall ab, ohne auf einen nicht-existenten Loader-Default angewiesen zu sein.
- **Kanal-Validierung:** Der Endpoint validiert `channel` und `report` nicht gegen eine Enum-Liste. Unbekannte Werte (`channel="fax"`) landen in `source="global"` — kein 422, weil `get_metrics_for_channel` mit unbekannten Kanälen ebenfalls auf global fällt.
- **`channel_layouts: {"email": []}` (nur leere per_channel-Liste, kein per_report):** Der Loader (`loader.py:439-448`) kollabiert absichtlich ein `channel_layouts`-Dict, in dem alle Kanal-Listen leer sind, auf `per_channel_layouts = None`. Konsequenz: `source="global"`, `metric_ids=[globale Metriken]` — **nicht** `source="per_channel"`. Das ist ein Loader-Design-Entscheid ("leer = keine Konfiguration = Fallback auf global"). Für das Adversary-Finding (F001, 2026-05-29): korrektes Verhalten bestätigt.

## Changelog

- 2026-05-29: Initial spec — Issue #448 (Validator-Endpoint für metrics-for-channel-Kaskade)
