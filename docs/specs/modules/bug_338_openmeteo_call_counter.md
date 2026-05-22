---
entity_id: bug_338_openmeteo_call_counter
type: bugfix
created: 2026-05-22
updated: 2026-05-22
status: draft
version: "1.0"
tags: [bugfix, observability, open-meteo, api-limit, diagnostics, issue-338]
---

<!-- Issue #338 — Diagnose-Zähler: jeden ausgehenden Open-Meteo-Aufruf mit Quelle protokollieren, um die Erschöpfung des Tageslimits zu lokalisieren. -->

# Issue #338 — Open-Meteo Abruf-Zähler (Diagnose)

## Approval

- [ ] Approved

## Zweck

Briefing-Mails kommen ohne Wetterdaten an, weil Open-Meteo die Server-IP mit `429 - Daily API request limit exceeded` blockt. Die instrumentierte Messung der regulären Pfade ergab nur ~2.500–3.800 gewichtete Einheiten/Tag — **weit unter dem 10.000-Limit**. Die tatsächliche Quelle der Erschöpfung ist nicht beweisbar, weil (1) erfolgreiche Abrufe nicht protokolliert werden und (2) das Limit ein gleitendes 24h-Fenster ist.

Dieser Fix fügt einen **reinen Diagnose-Zähler** ein: Jeder ausgehende Open-Meteo-HTTP-Aufruf wird mit Zeitstempel, Endpoint, HTTP-Status und **Auslöser-Quelle** (Briefing / Alarm / Trend / Ensemble / UV / Vorschau / Vergleich / unbekannt) in eine append-only-Datei protokolliert. Nach 24h Laufzeit liefert die Auswertung die exakte Quelle. **Keine Verhaltensänderung** an den Abrufen selbst.

## Quelle / Source

**Geänderte Dateien:**

- `src/providers/openmeteo.py` — zentraler HTTP-Punkt `_request()` (Forecast + Air-Quality/UV) und `_fetch_ensemble_spread()` (separater Client-Call) protokollieren jeden Aufruf via neuem Helfer `_log_api_call(endpoint, status, error)`. Quelle wird via `inspect.stack()` aus den Aufrufer-Frame-Namen abgeleitet.

**Neue Dateien:**

- `tests/tdd/test_bug_338_openmeteo_call_counter.py` — Tests (echte Provider-Aufrufe, kein Mock)
- `scripts/analyze_openmeteo_calls.py` — Auswertungs-Skript (zählt nach Quelle / Endpoint / Stunde)

**Laufzeit-Artefakt (nicht eingecheckt):**

- `data/diagnostics/openmeteo_calls.jsonl` — append-only JSONL, eine Zeile pro Abruf (in `.gitignore`)

> **Schicht-Hinweis:** Nur Python-Provider-Layer. Die Go-API ist nachweislich aktuell fast inaktiv (heute 0× `/api/compare/run`, 25× `/stages/weather`) — daher Out of Scope für diesen ersten Diagnose-Schritt (siehe Out of Scope).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/providers/openmeteo.py` | Python-Klasse | `_request()` ist der zentrale HTTP-Punkt für Forecast + Air-Quality; `_fetch_ensemble_spread()` macht einen separaten Client-Call |
| `inspect` (stdlib) | Python-Modul | Aufrufer-Frame-Auswertung zur Quellen-Bestimmung ohne Signatur-Durchreichung |
| `data/diagnostics/` | Verzeichnis | Ziel der JSONL-Logdatei (wird bei Bedarf erzeugt) |

## Implementation Details

### 1. Quellen-Bestimmung via Stack-Auswertung

Neuer Helfer in `OpenMeteoProvider`:

```python
# Mapping: Aufrufer-Funktionsname (im Stack) -> Diagnose-Quelle
_CALL_SOURCE_MARKERS = [
    ("_fetch_fresh_weather", "alarm"),
    ("_build_stage_trend", "trend"),
    ("_enrich_ensemble_for_trip", "ensemble"),
    ("_fetch_ensemble_spread", "ensemble"),
    ("_fetch_uv_data", "uv"),
    ("_fetch_night_weather", "briefing_nacht"),
    ("_fetch_weather", "briefing"),
    ("preview", "vorschau"),
    ("compare", "vergleich"),
]

def _resolve_call_source(self) -> str:
    import inspect
    names = [f.function for f in inspect.stack()[:25]]
    for marker, source in self._CALL_SOURCE_MARKERS:
        if any(marker in n for n in names):
            return source
    return "unbekannt"
```

Reihenfolge der Marker = Priorität (spezifischste zuerst: Alarm/Trend vor generischem Briefing).

### 2. Logging-Helfer (fail-soft)

```python
DIAGNOSTICS_PATH = Path("data/diagnostics/openmeteo_calls.jsonl")

def _log_api_call(self, endpoint: str, status: Optional[int], error: Optional[str] = None) -> None:
    try:
        DIAGNOSTICS_PATH.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "endpoint": endpoint,
            "status": status,
            "source": self._resolve_call_source(),
            "error": error,
        })
        with DIAGNOSTICS_PATH.open("a") as fh:
            fh.write(line + "\n")
    except Exception:
        pass  # Diagnose darf den Abruf NIE beeinträchtigen
```

### 3. Einbau in `_request()` und `_fetch_ensemble_spread()`

In `_request()`: Nach dem `self._client.get(...)` den Aufruf protokollieren — sowohl im Erfolgs- als auch im Fehlerfall (HTTPStatusError mit `e.response.status_code`, RequestError mit `error=str(e)`). Endpoint = `f"{base_host}{endpoint}"` (host+path, ohne Query-Parameter).

In `_fetch_ensemble_spread()`: Analog nach dem separaten `self._client.get(...)` protokollieren.

Der `@retry`-Decorator auf `_request` bleibt unverändert — jeder Versuch (auch Retry bei 502/503/504) wird einzeln protokolliert, was die echte Abruf-Last korrekt abbildet.

### 4. Auswertungs-Skript `scripts/analyze_openmeteo_calls.py`

Liest die JSONL und gibt aus: Gesamtzahl, Aufschlüsselung nach `source`, nach `endpoint`, nach Stunde, sowie Erfolg/429/sonstige-Fehler-Quote. Keine Abhängigkeiten außer stdlib.

### 5. LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `src/providers/openmeteo.py` | ~40 | ja |
| `tests/tdd/test_bug_338_openmeteo_call_counter.py` | ~50 | ja |
| `scripts/analyze_openmeteo_calls.py` | ~40 | ja |
| **Gesamt** | **~130** | **< 250** |

## Expected Behavior

- **Input:** Bestehende Abruf-Pfade ohne Änderung am Aufrufer.
- **Output:** Bei jedem ausgehenden Open-Meteo-Aufruf (Forecast, Air-Quality/UV, Ensemble) wird genau eine JSONL-Zeile mit `ts`, `endpoint`, `status`, `source`, `error` angehängt — unabhängig von Erfolg oder 429.
- **Side effects:** Keine Änderung an den Wetterdaten, am Versand oder am Fehlerverhalten. Logging ist fail-soft (Schreibfehler werden geschluckt).

## Acceptance Criteria

- **AC-1:** Given ein erfolgreicher oder mit 429 fehlschlagender `fetch_forecast()`-Aufruf / When der Aufruf durch `_request()` läuft / Then wird genau eine Zeile an `data/diagnostics/openmeteo_calls.jsonl` angehängt, die `ts`, `endpoint` (host+path ohne Query), `status` und `source` enthält.
  - Test: (populated after /tdd-red)

- **AC-2:** Given ein Abruf, der aus dem Alarm-Pfad (`_fetch_fresh_weather`) stammt / When `_log_api_call()` die Quelle bestimmt / Then ist `source == "alarm"`; und ein Abruf aus dem Mehrtages-Trend (`_build_stage_trend`) liefert `source == "trend"`.
  - Test: (populated after /tdd-red)

- **AC-3:** Given das Diagnose-Verzeichnis ist nicht beschreibbar (z.B. Schreibfehler) / When `_log_api_call()` aufgerufen wird / Then wird die Ausnahme geschluckt und der ursprüngliche Forecast-Abruf läuft unverändert weiter (kein Crash, kein verändertes Rückgabeverhalten).
  - Test: (populated after /tdd-red)

- **AC-4:** Given eine befüllte `openmeteo_calls.jsonl` / When `scripts/analyze_openmeteo_calls.py` ausgeführt wird / Then gibt es eine Aufschlüsselung der Gesamt-Abrufe nach `source`, nach `endpoint` und nach Stunde aus.
  - Test: (populated after /tdd-red)

## Known Limitations

- **Stack-basierte Quellen-Heuristik:** Die Zuordnung beruht auf Aufrufer-Funktionsnamen. Bei unerwarteten Aufrufpfaden ist `source == "unbekannt"` möglich — das ist akzeptabel und selbst ein verwertbares Signal.
- **Nur Python-Provider:** Go-seitige Abrufe (`/api/forecast`, `/stages/weather`, `/compare/run`) werden nicht erfasst. Falls die Python-Auswertung das Limit nicht erklärt, folgt die Go-Instrumentierung als zweiter Schritt.
- **Temporäres Diagnose-Werkzeug:** Nach Lokalisierung der Quelle wird der Zähler wieder entfernt oder hinter ein Flag gelegt (Folge-Issue).

## Out of Scope

- Behebung der eigentlichen Limit-Erschöpfung (eigener Folge-Issue nach Auswertung)
- Instrumentierung des Go-Providers
- Sofort-Entlastung (Staging-Scheduler pausieren) — separate, sofortige Maßnahme
- Forecast-Ergebnis-Caching, Reduktion des Mehrtages-Trends, Alarm-Cache-Fix

## Changelog

- 2026-05-22: Initial spec. Reiner Diagnose-Zähler in `src/providers/openmeteo.py` (`_request` + `_fetch_ensemble_spread`) plus Auswertungs-Skript. Erfasst Quelle via Stack-Auswertung, fail-soft, append-only JSONL.
