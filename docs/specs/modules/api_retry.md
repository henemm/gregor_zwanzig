---
entity_id: api_retry
type: module
created: 2026-01-02
updated: 2026-01-02
status: draft
version: "1.0"
tags: [resilience, api, geosphere]
---

# API Retry Logic

## Approval

- [ ] Approved

## Purpose

Automatische Wiederholung von fehlgeschlagenen API-Aufrufen bei transienten Fehlern (502 Bad Gateway, 503 Service Unavailable, 504 Gateway Timeout, Connection Errors). Verhindert, dass temporaere API-Ausfaelle zu unvollstaendigen E-Mails fuehren.

**Hintergrund:** Am 02.01.2026 um 07:00 lieferte die GeoSphere API fuer 4 von 5 Locations `502 Bad Gateway`. Die E-Mail enthielt nur 1 Skigebiet statt 5.

## Source

- **File:** `src/providers/geosphere.py`
- **Identifier:** `GeoSphereProvider._request()`, `_RetryableHTTPError` (private)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `geosphere.py` | module | HTTP-Client fuer API-Aufrufe |
| `httpx` | library | HTTP-Client mit Timeout-Support |
| `tenacity` | library (NEU) | Retry-Logik mit Backoff |

## Implementation Details

### 1. Retry-Decorator fuer `_request()`

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
import httpx

# Retry-Konfiguration
RETRY_ATTEMPTS = 5
RETRY_WAIT_MIN = 2   # Sekunden
RETRY_WAIT_MAX = 60  # Sekunden (1 Minute)
RETRY_STATUS_CODES = {502, 503, 504}

class RetryableHTTPError(Exception):
    """HTTP-Fehler der einen Retry rechtfertigt."""
    pass

@retry(
    stop=stop_after_attempt(RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=RETRY_WAIT_MIN, max=RETRY_WAIT_MAX),
    retry=retry_if_exception_type((RetryableHTTPError, httpx.ConnectError, httpx.ReadTimeout)),
)
def _request(self, endpoint, lat, lon, parameters, start=None, end=None):
    # ... bestehender Code ...
    response = self._client.get(url)

    # Pruefe auf retryable Status Codes
    if response.status_code in RETRY_STATUS_CODES:
        raise RetryableHTTPError(f"HTTP {response.status_code}: {response.text[:100]}")

    response.raise_for_status()
    return response.json()
```

### 2. Logging bei Retry-Versuchen

```python
import logging

logger = logging.getLogger("geosphere")

# In _request():
@retry(
    ...,
    before_sleep=lambda retry_state: logger.warning(
        f"GeoSphere API retry {retry_state.attempt_number}/{RETRY_ATTEMPTS} "
        f"nach {retry_state.outcome.exception()}"
    ),
)
```

### 3. Warnung bei fehlenden Locations

In `src/web/pages/compare.py` bei `run_comparison_for_subscription()`:

```python
def run_comparison_for_subscription(sub, all_locations):
    # ... bestehender Code ...

    # Nach ComparisonEngine.run():
    failed_locations = [
        loc for loc in selected_locs
        if loc not in [r.location for r in result.locations if r.score is not None]
    ]

    if failed_locations:
        # Warnung in E-Mail-Header einfuegen
        warning = f"WARNUNG: {len(failed_locations)} Location(s) nicht verfuegbar: "
        warning += ", ".join(loc.name for loc in failed_locations[:3])
        # In HTML-Header einfuegen
```

## Expected Behavior

### Input
- HTTP-Request an GeoSphere API
- Transiente Fehler (502, 503, 504, Connection Error)

### Output
- **Erfolg nach Retry:** Normale Antwort, Log-Warnung ueber Retry
- **Fehler nach 5 Versuchen:** Exception wird weitergereicht, Location fehlt in E-Mail
- **E-Mail mit Warnung:** Falls Locations trotz Retry fehlen

### Retry-Ablauf (Exponential Backoff)

```
Attempt 1: 502 Bad Gateway
  -> Warte 2 Sekunden
Attempt 2: 502 Bad Gateway
  -> Warte 4 Sekunden
Attempt 3: 502 Bad Gateway
  -> Warte 8 Sekunden
Attempt 4: 502 Bad Gateway
  -> Warte 16 Sekunden
Attempt 5: 200 OK
  -> Erfolg nach ~30 Sekunden
```

**Maximale Wartezeit pro Location:** 2 + 4 + 8 + 16 + 32 = ~62 Sekunden (gecapped auf 60s)

### Log-Output

```
2026-01-02 07:00:05 - geosphere - WARNING - GeoSphere API retry 1/5 nach HTTP 502
2026-01-02 07:00:09 - geosphere - WARNING - GeoSphere API retry 2/5 nach HTTP 502
2026-01-02 07:00:17 - geosphere - WARNING - GeoSphere API retry 3/5 nach HTTP 502
2026-01-02 07:00:33 - geosphere - WARNING - GeoSphere API retry 4/5 nach HTTP 502
2026-01-02 07:01:05 - geosphere - INFO - Request erfolgreich nach 4 Retries
```

## Side Effects

- Laengere Request-Zeiten bei transienten Fehlern (max ~60 Sekunden pro Location)
- Mehr Log-Eintraege bei API-Problemen
- Neue Dependency: `tenacity` (optional, kann auch manuell implementiert werden)

## Known Limitations

- Kein Retry bei 4xx Client-Fehlern (400, 401, 403, 404) - diese sind nicht transient
- Kein Retry bei invaliden Antworten (JSON Parse Error)
- Maximale Verzoegerung: 5 Versuche mit max 60s Wartezeit = ~2 Minuten pro Location
- Bei 5 Locations mit je 2 Minuten: Max 10 Minuten zusaetzliche Wartezeit (worst case)
- Fuer Scheduler-E-Mails akzeptabel (E-Mail kommt 07:10 statt 07:00)

## Konfiguration (Optional)

Falls gewuenscht, koennen die Retry-Parameter in `config.ini` konfigurierbar sein:

```ini
[api]
retry_attempts = 5
retry_wait_min = 2
retry_wait_max = 60
retry_status_codes = 502,503,504
```

## Testplan

1. **Unit Test:** Mock HTTP 502, pruefe dass 5 Versuche gemacht werden
2. **Unit Test:** Mock Erfolg nach 3. Versuch, pruefe Log-Output
3. **Unit Test:** Pruefe exponential backoff Timing (2s, 4s, 8s, ...)
4. **Integration Test:** Echte API mit kuenstlichem Timeout
5. **E2E Test:** Scheduler-Email mit allen Locations pruefen

## Changelog

- 2026-01-02: Initial spec created nach API-Ausfall am Morgen
- 2026-01-02: Retry-Konfiguration angepasst (5 Versuche, max 60s Wartezeit)
