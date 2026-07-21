---
entity_id: issue_338_go_geosphere_counter
type: bugfix
created: 2026-05-23
updated: 2026-05-23
status: draft
version: "1.0"
tags: [observability, open-meteo, api-limit, diagnostics, golang, geosphere, issue-338]
---

<!-- Issue #338 (Erweiterung) — Vollständige Abruf-Erfassung: Go-Provider + Geosphere-Clouds-Calls instrumentieren, damit ALLE Open-Meteo-Ausgangspunkte protokolliert werden. -->

# Issue #338 (Erweiterung) — Vollständige Open-Meteo-Abruf-Erfassung (Go + Geosphere)

## Approval

- [ ] Approved

## Zweck

Der erste Zähler (Commit bd8e1e2) erfasst nur den Python-`OpenMeteoProvider`. Es gibt zwei weitere, aktive, bislang **ungezählte** Open-Meteo-Ausgangspunkte:

1. **Go-Provider** (`internal/provider/openmeteo/provider.go`) — bedient `/api/forecast` (gemessen 804 Aufrufe am 20.05.), `/api/trips/{id}/stages/weather`, `/api/compare/run`. Jeder Aufruf macht Forecast + UV.
2. **Python-`GeoSphereProvider`** (`src/providers/geosphere.py`) — `_fetch_openmeteo_clouds()` ruft `api.open-meteo.com` direkt; aktiv im Compare-Pfad für Alpenraum-Koordinaten (`comparison_engine.py:271`).

Ohne diese beiden Pfade wäre die 24h-Messung irreführend (zeigt nur einen Bruchteil). Diese Erweiterung instrumentiert beide, sodass **jeder** ausgehende Open-Meteo-Abruf in die Auswertung fließt. Reine Observability, fail-soft, keine Verhaltensänderung.

## Quelle / Source

**Geänderte Dateien:**

- `internal/provider/openmeteo/provider.go` — in `doRequest()` (zentraler HTTP-Punkt für Forecast + UV) nach `p.client.Do(req)` einen fail-soft Logger aufrufen.
- `src/providers/geosphere.py` — in `_fetch_openmeteo_clouds()` nach `self._client.get(url)` den gemeinsamen Logger aufrufen.
- `src/providers/openmeteo.py` — `_log_api_call`/`_resolve_call_source` auf das neue gemeinsame Modul umstellen (Konsolidierung statt Duplikat).
- `scripts/analyze_openmeteo_calls.py` — beide JSONL-Quellen (Python + Go) einlesen und gemeinsam aggregieren.

**Neue Dateien:**

- `src/providers/call_log.py` — gemeinsames Python-Logging-Modul (`log_api_call`, `resolve_call_source`, `_CALL_SOURCE_MARKERS`).
- `internal/provider/openmeteo/calllog.go` — Go-Logging-Helfer.
- `tests/tdd/test_issue_338_go_geosphere_counter.py` — Python-Tests (Geosphere-Pfad, kein Mock).
- `internal/provider/openmeteo/calllog_test.go` — Go-Test (httptest-Server, kein externer Call).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/provider/openmeteo/provider.go` `doRequest` | Go-Methode | Einziger zentraler HTTP-Punkt; `FetchForecast` und `fetchUVData` laufen beide durch ihn |
| `src/providers/geosphere.py` `_fetch_openmeteo_clouds` | Python-Methode | Direkter `api.open-meteo.com`-Abruf (Cloud-Layer) |
| `src/providers/call_log.py` | Python-Modul (neu) | Gemeinsame Logging-Logik für OpenMeteo + Geosphere (DRY) |
| `data/diagnostics/` | Verzeichnis | Ziel der JSONL-Dateien |

## Implementation Details

### 1. Gemeinsames Python-Modul `src/providers/call_log.py`

Enthält die aus `openmeteo.py` extrahierte Logik:

```python
DIAGNOSTICS_PATH = Path("data/diagnostics/openmeteo_calls.jsonl")

_CALL_SOURCE_MARKERS = [
    ("_fetch_openmeteo_clouds", "geosphere_clouds"),  # NEU — vor allen anderen
    ("render_email_preview", "vorschau"),
    ("render_sms_preview", "vorschau"),
    ("_fetch_fresh_weather", "alarm"),
    ("_build_stage_trend", "trend"),
    ("_enrich_ensemble_for_trip", "ensemble"),
    ("_fetch_ensemble_spread", "ensemble"),
    ("_fetch_uv_data", "uv"),
    ("_fetch_night_weather", "briefing_nacht"),
    ("_fetch_weather", "briefing"),
    ("compare", "vergleich"),
]

def resolve_call_source() -> str: ...      # inspect.stack, wie bisher
def log_api_call(endpoint, status, error=None) -> None: ...  # fail-soft append JSONL
```

`openmeteo.py`: `_resolve_call_source`/`_log_api_call` werden zu Thin-Wrappern, die `call_log.*` aufrufen (Verhalten unverändert; bestehende 6 Tests bleiben grün).

### 2. Geosphere instrumentieren

In `_fetch_openmeteo_clouds()` nach `response = self._client.get(url, timeout=10.0)`:

```python
from providers.call_log import log_api_call
log_api_call("https://api.open-meteo.com/v1/forecast", response.status_code)
```

Die Stack-Auflösung erkennt `_fetch_openmeteo_clouds` → `source="geosphere_clouds"`. Bei Request-Fehler (vor Response) analoger Eintrag mit `error`.

### 3. Go-Logger `internal/provider/openmeteo/calllog.go`

```go
// logAPICall hängt fail-soft eine JSONL-Zeile an data/diagnostics/openmeteo_calls_go.jsonl.
func logAPICall(reqURL string, status int, errStr string) {
    defer func() { recover() }() // Diagnose darf den Abruf nie beeinträchtigen
    source := "go_forecast"
    if strings.Contains(reqURL, "/v1/air-quality") { source = "go_uv" }
    endpoint := reqURL
    if i := strings.IndexByte(reqURL, '?'); i >= 0 { endpoint = reqURL[:i] } // ohne Query
    line, _ := json.Marshal(map[string]interface{}{
        "ts": time.Now().UTC().Format(time.RFC3339Nano),
        "endpoint": endpoint, "status": status, "source": source, "error": errStr,
    })
    os.MkdirAll("data/diagnostics", 0o755)
    f, err := os.OpenFile("data/diagnostics/openmeteo_calls_go.jsonl", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
    if err != nil { return }
    defer f.Close()
    f.Write(append(line, '\n'))
}
```

Eigene Datei `openmeteo_calls_go.jsonl` (vermeidet Cross-Language-Schreibkonflikte mit Python).

### 4. Einbau in `doRequest`

Nach `resp, err := p.client.Do(req)`:
- Bei `err != nil`: `logAPICall(reqURL, 0, err.Error())` (Netzwerkfehler, kein Status), dann wie bisher `continue`/retry.
- Bei Erfolg: `logAPICall(reqURL, resp.StatusCode, "")` direkt nach Erhalt des Status.

Jeder Retry-Versuch wird einzeln protokolliert (bildet die echte Last ab). Endpoint ohne Query.

### 5. Auswertungs-Skript erweitern

`scripts/analyze_openmeteo_calls.py` liest beide Dateien (`openmeteo_calls.jsonl` + `openmeteo_calls_go.jsonl`), aggregiert gemeinsam nach `source`, `endpoint`, Stunde und Status. Quelle-Präfix `go_*` macht die Sprachherkunft sichtbar.

### 6. LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `src/providers/call_log.py` (neu) | ~30 | ja |
| `src/providers/openmeteo.py` (Umstellung) | ~-30/+8 | ja |
| `src/providers/geosphere.py` | ~5 | ja |
| `internal/provider/openmeteo/calllog.go` (neu) | ~25 | ja |
| `internal/provider/openmeteo/provider.go` | ~4 | ja |
| `scripts/analyze_openmeteo_calls.py` | ~15 | ja |
| Tests (Python + Go) | ~60 | ja |
| **Gesamt** | **~120** | **< 250** |

## Expected Behavior

- **Input:** Bestehende Abruf-Pfade, keine Aufrufer-Änderung.
- **Output:** Jeder Go-Open-Meteo-Abruf (Forecast/UV, inkl. Retry-Versuche) erzeugt eine JSONL-Zeile in `openmeteo_calls_go.jsonl` mit `source` `go_forecast`/`go_uv`. Jeder Geosphere-Clouds-Abruf erzeugt eine Zeile in `openmeteo_calls.jsonl` mit `source="geosphere_clouds"`. Bestehende Python-OpenMeteo-Protokollierung unverändert.
- **Side effects:** Keine. Beide Logger fail-soft. Go-Binary muss neu gebaut + deployed werden.

## Acceptance Criteria

- **AC-1:** Given ein Go-`FetchForecast`-Aufruf gegen einen httptest-Server, der 429 liefert / When `doRequest` den Aufruf ausführt / Then wird eine JSONL-Zeile an `openmeteo_calls_go.jsonl` angehängt mit `endpoint` (ohne Query), `status=429`, `source="go_forecast"`.
  - Test: (populated after /tdd-red)

- **AC-2:** Given ein Geosphere-`_fetch_openmeteo_clouds`-Aufruf (echt, 429 erwartet) / When der Abruf läuft / Then enthält `openmeteo_calls.jsonl` eine Zeile mit `source="geosphere_clouds"`.
  - Test: (populated after /tdd-red)

- **AC-3:** Given die bestehenden 6 Tests aus Commit bd8e1e2 / When `call_log` die Logik übernimmt / Then bleiben alle 6 grün (Konsolidierung verhält sich identisch; Python-OpenMeteo-Quellen unverändert).
  - Test: (populated after /tdd-red)

- **AC-4:** Given je eine befüllte `openmeteo_calls.jsonl` und `openmeteo_calls_go.jsonl` / When `scripts/analyze_openmeteo_calls.py` läuft / Then aggregiert es beide Dateien gemeinsam und weist `go_*`- und Python-Quellen getrennt aus.
  - Test: (populated after /tdd-red)

- **AC-5:** Given ein nicht-beschreibbares Diagnose-Ziel (Go) / When `logAPICall` aufgerufen wird / Then wird der Fehler verschluckt und `doRequest` liefert unverändert sein Ergebnis (kein Panic, kein verändertes Forecast-Verhalten).
  - Test: (populated after /tdd-red)

## Known Limitations

- **Go-Quelle nur grob (`go_forecast`/`go_uv`):** Welcher HTTP-Endpunkt (`/api/forecast` vs `/stages/weather` vs `/compare/run`) den Go-Call auslöste, wird nicht im JSONL unterschieden — das lässt sich bei Bedarf über Zeitkorrelation mit den Go-API-Access-Logs nachziehen. Endpoint-genaue Attribution via Context-Durchreichung wäre Folge-Arbeit.
- **Zwei JSONL-Dateien:** Python und Go schreiben getrennt (Cross-Language-Concurrency-Schutz); das Auswertungs-Skript führt sie zusammen.

## Out of Scope

- Behebung der Limit-Erschöpfung (Folge nach Auswertung)
- Endpoint-genaue Go-Quellenattribution via Context
- Caching/Reduktion von `/api/forecast`-Aufrufen

## Changelog

- 2026-05-23: Initial spec. Schließt die zwei Erfassungslücken (Go-Provider + Geosphere-Clouds) des Zählers aus bd8e1e2; konsolidiert Python-Logging in `call_log.py`.
