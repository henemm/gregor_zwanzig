# Context: Issue #448 — Validator-Endpoint für Kaskaden-Logik

## Request Summary

Neuer Read-only-Endpoint `GET /api/_validator/metrics-for-channel` der die
dreistufige Kaskaden-Logik von `get_metrics_for_channel()` von außen prüfbar
macht. Folge-Issue aus #434 (External-Validator konnte AC-3, AC-4, AC-7 nicht
verifizieren, weil kein Endpoint die berechnete Metriken-Liste zurückgibt).

## Ziel-Response laut Issue

```json
{ "source": "per_report|per_channel|global", "metric_ids": [...] }
```

Parameter: `trip=<id>`, `channel=<email|telegram|...>`, `report=<morning|evening>`

## Related Files

| Datei | Relevanz |
|-------|----------|
| `src/app/models.py:595` | `UnifiedWeatherDisplayConfig.get_metrics_for_channel()` — die Kaskaden-Funktion selbst (3 Ebenen) |
| `src/app/models.py:506` | `_filter_metrics_by_report_type()` — Shared Helper für morning/evening-Flags |
| `api/routers/validator.py` | Bestehender Validator-Router — hier wird der neue Endpoint eingefügt |
| `api/routers/validator.py:59` | `_load_trip_for_validator()` — kann direkt wiederverwendet werden |
| `api/main.py` | Router-Einbindung (validator.router bereits registriert) |
| `internal/handler/proxy.go` | Go-Proxy-Handler (neue Handler-Funktion analog zu `ValidatorFormatMetricProxyHandler`) |
| `cmd/server/main.go:138` | Go-Route-Registrierung (analog zu bestehenden `_validator`-Routen) |
| `tests/integration/test_issue_221_validator_endpoints.py` | Muster für Integrationstests der Validator-Endpoints |
| `tests/tdd/test_issue_434_per_report_layouts.py` | Kaskaden-Tests (AC-3, AC-4, AC-7) — die neuen Tests müssen diese ACs beweisen |
| `docs/specs/modules/issue_221_validator_observability_endpoints.md` | Vorbild-Spec für neue Validator-Endpoint-Spec |

## Bestehende Kaskaden-Logik (dreistufig)

```python
# src/app/models.py:595 — get_metrics_for_channel(channel, report_type)
# Ebene 1: per_report_layouts[report_type][channel]  (höchste Prio, #434)
# Ebene 2: per_channel_layouts[channel]              (#429)
# Ebene 3: get_metrics_for_report_type(report_type) (globaler Fallback)
```

Der Endpoint muss zusätzlich zur Liste auch die `source` zurückgeben, damit
der Validator die aktive Kaskadenebene erkennt.

## Source-Label-Logik (Analogie zu `config_source_from_raw`)

| Bedingung | source-Wert |
|-----------|-------------|
| `per_report_layouts[report_type][channel]` trifft zu | `"per_report"` |
| `per_channel_layouts[channel]` trifft zu | `"per_channel"` |
| globaler Fallback | `"global"` |

## Existing Patterns

- **`_load_trip_for_validator(user_id, trip_id)`** — bereits in `validator.py` vorhanden, wiederverwendbar.
- **`appendUserID`** in `proxy.go` — Anti-Spoofing-Pattern, user_id immer via Go-Proxy injiziert.
- Alle `_validator`-Endpunkte: cookie-geschützt via globale `AuthMiddleware`, nicht auf Whitelist.
- Go-Proxy-Handler: immer analog zu `ValidatorFormatMetricProxyHandler` — proxied direkt an Python-URL.
- Response-Struktur: einfaches JSON, kein Paging, kein Wrapper-Objekt.

## Dependencies

- **Upstream:** `src.app.models.UnifiedWeatherDisplayConfig.get_metrics_for_channel` — die Funktion existiert bereits und ist voll implementiert.
- **Upstream:** `api/routers/validator._load_trip_for_validator` — wiederverwendbar.
- **Downstream:** External-Validator-Skript (`.claude/hooks/`) — konsumiert den neuen Endpoint.

## Existing Specs

- `docs/specs/modules/issue_221_validator_observability_endpoints.md` — Vorbild-Spec

## Umfang (Schätzung)

- Python-Endpoint in `api/routers/validator.py`: ~20 LoC
- Go-Proxy-Handler in `internal/handler/proxy.go`: ~20 LoC
- Go-Route-Registrierung in `cmd/server/main.go`: ~2 LoC
- Integrationstest: ~40–60 LoC (gegen echte Fixtures, keine Mocks)
- Spec: ~1 neue Spec-Datei

Gesamt: ~100–120 LoC, überschaubar, analog zu bestehenden Validator-Endpoints.

## Risks & Considerations

- Keine Mocks: Der Test muss eine echte Trip-Fixture anlegen und per HTTP testen (Muster: `test_issue_221_validator_endpoints.py`).
- `source`-Ermittlung: Nicht delegierbar an `get_metrics_for_channel()` selbst (die Funktion gibt nur die Liste zurück). Entweder eigene Hilfsfunktion oder Inspektion der `display_config`-Felder vorab.
- `per_report_layouts` mit leerer Liste (`[]`) = expliziter User-Wunsch (`source="per_report"`, `metric_ids=[]`). Edge Case im Test abdecken.
- `per_channel_layouts` mit leerer Liste = analog.
