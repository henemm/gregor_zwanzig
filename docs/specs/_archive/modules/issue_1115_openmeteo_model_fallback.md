---
entity_id: issue_1115_openmeteo_model_fallback
type: module
created: 2026-07-08
updated: 2026-07-08
status: approved
version: "1.0"
tags: [providers, openmeteo, reliability, fallback, briefing]
---

# Intra-Open-Meteo-Modell-Fallback bei Quell-Ausfall (#1115)

## Approval

- [x] Approved (PO 'go' 2026-07-08 auf AC-1..AC-5)

## Purpose

Beim Incident 07./08.07. (14 h, 203× HTTP 503 **ausschließlich** auf dem DWD-Kanal `/v1/dwd-icon`, während Météo-France/MetNo/ECMWF parallel 200 lieferten) fielen **alle** Trip-Briefings aus, weil `fetch_forecast` stur beim ausgefallenen Modell-Endpoint blieb. Dieses Modul lässt Gregor bei Server-Fehler (5xx) oder Timeout eines Modell-Endpoints automatisch auf das nächstbeste abdeckende Modell der Prioritätskette ausweichen (feinste Auflösung zuerst, bis globales ECMWF) — **ohne** den Ausfall zu kaschieren: jedes Ausweichen wird in den Daten markiert, protokolliert und im Health-Status sichtbar; ein persistenter Ausfall eskaliert mit der Dauer.

**Kern-Prinzip (PO):** Zuverlässigkeit und maximale Datenqualität sind der Kern von Gregor Zwanzig. Ausweichen darf niemals einen Fehler verstecken.

## Source

- **File:** `src/providers/openmeteo.py` (Python-Core / Domain-Backend)
- **Identifier:** `OpenMeteoProvider.fetch_forecast`, neue `_candidate_models`
- **File:** `src/providers/base.py` — `ProviderRequestError`
- **File:** `src/app/models.py` — `ForecastMeta`
- **File:** `internal/scheduler/briefing_health.go` (Go-API) — Health-Aggregat für AC-4

## Estimated Scope

- **LoC:** ~120–180 (Python-Core + Go-Health-Signal), LoC-Override 500 gesetzt
- **Files:** 3 Python + 1 Go + Tests
- **Effort:** medium-high (kritischer Datenpfad aller Briefings)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `REGIONAL_MODELS` (openmeteo.py:103) | data | Prioritätskette der Modell-Endpoints |
| `_is_retryable_error` (openmeteo.py:190) | function | 5xx/Timeout- vs. 4xx-Unterscheidung (Wiederverwendung) |
| `ForecastMeta.fallback_model` (models.py:83) | field | existiert bereits (WEATHER-05b), wird wiederverwendet |
| `openmeteo_calls.jsonl` (call_log.py) | log | pro Call-Protokoll, Grundlage `last_provider_error_at` |
| `BriefingHealth()` (briefing_health.go:28) | function | Health-Aggregat, um Degradierungs-Signal erweitern |

## Implementation Details

```
# openmeteo.py
_candidate_models(lat, lon) -> List[(id, grid_res_km, endpoint)]:
    # reine Extraktion der Bounds-Filter-Logik (wie select_model Z.393-398),
    # sortiert nach priority.

fetch_forecast(...):
    candidates = _candidate_models(lat, lon)
    seen_endpoints = set()          # icon_d2 & icon_eu teilen /v1/dwd-icon → dedup
    primary_id = candidates[0].id   # ursprünglich gewähltes Modell (Referenz)
    for (model_id, grid_res, endpoint) in candidates:
        if endpoint in seen_endpoints: continue
        seen_endpoints.add(endpoint)
        try:
            response = _request(endpoint, params)   # params modellunabhängig
        except ProviderRequestError as e:
            if e.status_code and 500 <= e.status_code < 600 or <transient/timeout>:
                logger.warning("Model fallback: %s (5xx) -> next", model_id)
                continue                     # -> nächster Endpoint
            raise                            # 4xx -> sofort re-raise, kein Modell hilft
        # Erfolg: model_id/grid_res sind die des TATSÄCHLICH erfolgreichen Modells
        timeseries = _parse_response(response, model_id, grid_res)
        if model_id != primary_id:
            timeseries.meta.fallback_model = model_id     # Nicht-Kaschieren
        return timeseries   # WEATHER-05b-Block danach nutzt erfolgreiches model_id

# base.py
class ProviderRequestError:
    def __init__(self, provider, message, status_code: Optional[int] = None): ...

# openmeteo.py _request: beim Wrap status_code=e.response.status_code setzen

# briefing_health.go: Degradierungs-Signal ergänzen, das mit Ausfalldauer wächst
# (fallback-in-Benutzung/persistente Provider-Fehler sichtbar, nicht nur Totalausfälle)
```

## Expected Behavior

- **Input:** Briefing-Wetterabruf pro Segment; Open-Meteo-Modell-Endpoint antwortet 5xx/Timeout/4xx/200.
- **Output:** `NormalizedTimeseries` vom nächstbesten verfügbaren Modell; `meta.fallback_model` gesetzt bei Ausweichen.
- **Side effects:** `logger.warning` je Endpoint-Wechsel; `_log_api_call` protokolliert jeden Versuch (auch 5xx) nach `openmeteo_calls.jsonl`; Health-Status spiegelt degradierten Dauerzustand wider.

## Acceptance Criteria

- **AC-1:** Given das regional gewählte Modell (z. B. DWD/`dwd-icon`) antwortet mit Server-Fehler (5xx) oder Timeout / When ein Briefing-Wetterabruf läuft / Then weicht Gregor automatisch auf das nächstbeste abdeckende Modell der Kette aus (feinste Auflösung zuerst, bis globales ECMWF) und liefert Daten, statt das Segment als Ausfall zu markieren.
  - Test: Echter `fetch_forecast`-Call gegen eine Test-Seam, bei der der Primär-Endpoint 503 liefert; Ergebnis enthält gültige Timeseries vom Ersatzmodell (kein `has_error`).

- **AC-2:** Given die Anfrage scheitert mit einem inhaltlichen Fehler (4xx, z. B. Datum außerhalb Vorhersagehorizont Bug #353) / When der Abruf läuft / Then wird **nicht** ausgewichen und der Fehler bleibt unverändert sichtbar/gemeldet (kein Quell-Roulette).
  - Test: Primär-Endpoint liefert 400; `fetch_forecast` re-raised sofort `ProviderRequestError`, keine weiteren Endpoint-Versuche (nachweisbar über Call-Protokoll: nur 1 Endpoint kontaktiert).

- **AC-3:** Given ein Briefing wurde mit einem Ersatzmodell erstellt / When die Timeseries erzeugt/gespeichert wird / Then ist in den Daten festgehalten, welches Modell einsprang (`meta.fallback_model` = erfolgreiches Modell ≠ primär gewähltes), und das Briefing ist als „degradiert" erkennbar.
  - Test: Nach erzwungenem Fallback ist `result.meta.fallback_model` gesetzt und ungleich dem primär gewählten Modell; bei Erfolg ohne Fallback bleibt es `None`.

- **AC-4:** Given ein Primärmodell fällt wiederholt/länger aus, **auch wenn Briefings dank Ausweichen weiter rausgehen** / When der Health-Status (`/api/scheduler/status`) abgefragt wird / Then existiert ein Signal, das mit der Ausfalldauer wächst (Grundlage für externe Alarmierung bis zur Maximalstufe) — ein still degradierter Dauerzustand ist ausgeschlossen.
  - Test: Nach protokollierten Provider-Fehlern (Fallback benutzt) meldet `BriefingHealth()` ein nicht-null Degradierungs-/Fehlersignal, dessen Alters-/Dauerwert mit der Zeit seit erstem Fehler wächst.

- **AC-5:** Given mehrere Modelle decken einen Ort ab / When ausgewichen wird / Then immer auf das nach Auflösung/Qualität nächstbeste, nie auf ein beliebiges (Kette bleibt nach `priority`/`grid_res_km` sortiert).
  - Test: Bei einem Ort, der von AROME (1,3 km) und ICON-D2 (2 km) und ECMWF (40 km) abgedeckt wird, führt ein 503 auf AROME zum nächstfeineren (ICON-D2), nicht direkt zu ECMWF.

## Out of Scope (Folge-Issues)

- **#1127** — Infrastruktur-unabhängiger Cross-Provider-Fallback (Météo-France/DWD/GeoSphere direkt) für Open-Meteo-Totalausfall.
- **#1128** — ✅ behoben: `_request` retryte 5xx/Connect-Error/Read-Timeout faktisch nie (tenacity-Wrap-Reihenfolge); siehe `docs/specs/modules/issue_1128_openmeteo_retry_fix.md`. Folge: Retry läuft jetzt vor diesem Fallback und verzögert ihn bei andauerndem 5xx messbar (#1155).
- BetterStack-Eskalationsleiter (Infra-Repo; Koordination per MQ an `infra`, sobald AC-4-Signal steht).

## Known Limitations

- Der Fallback wirkt nur bei Ausfall **einzelner** Open-Meteo-Modell-Kanäle, nicht bei Open-Meteo-Totalausfall (→ #1127).
- Bei Downgrade auf gröberes Modell (z. B. AROME 1,3 km → ECMWF 40 km) sinkt die räumliche Auflösung — bewusst akzeptiert als „beste verfügbare Daten statt Totalausfall", sichtbar via `fallback_model`.
