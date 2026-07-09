---
entity_id: issue_1128_openmeteo_retry_fix
type: bugfix
created: 2026-07-08
updated: 2026-07-08
status: draft
version: "1.0"
tags: [provider, weather, open-meteo, retry, bugfix]
---

# Fix #1128: Open-Meteo Retry-Praedikat greift nie (5xx + Connect-Error + Read-Timeout)

## Approval

- [ ] Approved

## Purpose

Behebt einen Bug in `src/providers/openmeteo.py`, durch den der `tenacity`-Retry-Decorator auf `_request()` transiente Fehler (HTTP 502/503/504, Connect-Errors, Read-Timeouts) faktisch nie wiederholt: Der `except`-Block wrapped die rohe `httpx`-Exception sofort in `ProviderRequestError`, bevor das Retry-Praedikat `_is_retryable_error()` sie pruefen kann — dieses matched nur auf die urspruenglichen `httpx`-Typen und liefert daher immer `False`.

## Source

- **File:** `src/providers/openmeteo.py`
- **Identifier:** `def _is_retryable_error(exception: Exception) -> bool` (Z.190-196)

**Schicht:** Python-Core / Domain-Backend (`src/providers/`) — korrekt zugeordnet, kein Frontend/Go betroffen.

## Estimated Scope

- **LoC:** ~15 Produktivcode, ~40-60 Testcode (weit unter dem 250-LoC-Workflow-Limit)
- **Files:** 2 (1 MODIFY, 1 CREATE)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ProviderRequestError` (`src/providers/base.py:82-94`) | class | Trägt bereits `status_code: Optional[int]` (aus #1115) — wird im Retry-Praedikat neu ausgewertet |
| `httpx` | library | HTTP-Client; liefert `HTTPStatusError`, `ConnectError`, `ReadTimeout` als ursprüngliche Exceptions |
| `tenacity` | library | Liefert `retry`, `retry_if_exception`, `stop_after_attempt`, `wait_exponential`, `before_sleep_log` — Retry-Mechanik selbst bleibt unveraendert, nur das Praedikat wird erweitert |
| `docs/specs/modules/provider_openmeteo.md` | spec | Beschreibt das eigentlich vorgesehene Retry-Zielverhalten (Soll-Zustand vor diesem Bug) |
| `docs/specs/modules/api_retry.md` | spec | Referenz-Retry-Pattern (GeoSphere-Provider), dort ohne dieses Wrap-Problem implementiert |
| `docs/specs/modules/issue_1115_openmeteo_model_fallback.md` | spec | Referenziert #1128 explizit als bewusst ausgeklammerten Folgefehler; Modell-Fallback-Logik faengt `ProviderRequestError` *nach* dem (mit diesem Fix nun greifenden) Retry ab |

## Implementation Details

Root-Cause: In `_request()` (Z.466-513) wrapped der `except`-Block sowohl `httpx.HTTPStatusError` (Z.504-509) als auch `httpx.RequestError`-Subklassen `ConnectError`/`ReadTimeout` (Z.510-513) sofort in `ProviderRequestError`, **bevor** `tenacity` das Retry-Praedikat `_is_retryable_error()` (Z.190-196) auf die Exception anwenden kann. Das Praedikat prueft aktuell ausschliesslich per `isinstance` auf die rohen `httpx`-Exception-Typen — die bereits gewrappte `ProviderRequestError` matched dort nie, Ergebnis ist immer `False`, also kein Retry. Betroffen sind laut Adversary-Review (`docs/context/fix-1128-openmeteo-retry.md`) **alle drei** urspruenglich vorgesehenen Retry-Faelle: 5xx, Connect-Error und Read-Timeout — nicht nur 5xx, wie im Issue urspruenglich vermutet.

`raise ... from e` (bereits vorhanden in Z.505-509 und Z.513) setzt `exception.__cause__` auf die urspruengliche `httpx`-Exception. Dieses Feld erlaubt es, den Connect-/Timeout-Fall am gewrappten `ProviderRequestError` rueckwirkend zu erkennen, ohne ein neues Feld auf `ProviderRequestError` einzufuehren.

Fix: `_is_retryable_error()` (Z.190-196) wird um einen `ProviderRequestError`-Zweig erweitert:

```python
def _is_retryable_error(exception: Exception) -> bool:
    """Check if exception is retryable."""
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in RETRY_STATUS_CODES
    if isinstance(exception, (httpx.ConnectError, httpx.ReadTimeout)):
        return True
    if isinstance(exception, ProviderRequestError):
        if exception.status_code in RETRY_STATUS_CODES:
            return True
        if isinstance(exception.__cause__, (httpx.ConnectError, httpx.ReadTimeout)):
            return True
    return False
```

`ProviderRequestError` ist bereits importiert in `openmeteo.py` (Z.45: `from providers.base import ProviderError, ProviderRequestError`). Das Feld `status_code` existiert bereits (siehe `src/providers/base.py:82-94`, eingefuehrt fuer #1115).

Kein struktureller Umbau von `_request()`: Der Alternativ-Ansatz aus dem Issue (`raise_for_status()` ausserhalb des wrappenden `except`-Blocks aufrufen) waere invasiver und wuerde das bestehende Error-Wrapping-Pattern aufbrechen, auf dem die #1115-Modell-Fallback-Logik bereits ueber `ProviderRequestError.status_code` aufbaut. Die bestehenden `httpx.*`-isinstance-Zweige (Z.192-195) bleiben als Absicherung erhalten, falls `_is_retryable_error` isoliert mit einer rohen `httpx`-Exception getestet wird — im echten `_request`-Ablauf ist nach dem Fix ausschliesslich der neue `ProviderRequestError`-Zweig der tatsaechlich greifende.

## Expected Behavior

- **Input:** Exception, die von `_request()` intern geworfen wird (immer eine `ProviderRequestError`, da `_request()` alle `httpx`-Exceptions vor dem Reraise wrapped)
- **Output:** `True`, wenn die Exception einen transienten Fehler repraesentiert (5xx-Status, Connect-Error oder Read-Timeout als Ursache); `False` bei 4xx-Client-Fehlern oder sonstigen Fehlern
- **Side effects:** Bei `True` fuehrt `tenacity` einen weiteren Request-Versuch mit exponentiellem Backoff durch (bis zu 5 Versuche, 2-60s Wartezeit); bei `False` propagiert `_request()` die `ProviderRequestError` sofort an den Aufrufer (u.a. die #1115-Modell-Fallback-Logik)

## Acceptance Criteria

- **AC-1:** Given ein echter lokaler HTTP-Server liefert beim ersten Aufruf HTTP 502 und beim zweiten Aufruf HTTP 200 / When `OpenMeteoProvider._request()` gegen diesen Server aufgerufen wird / Then liefert `_request()` am Ende die erfolgreiche 200-Antwort zurueck, weil der interne Retry gegriffen und einen zweiten Versuch ausgeloest hat.
  - Test: `tests/unit/test_openmeteo_retry.py`, echter lokaler HTTP-Server (kein Mock, kein `Mock()`/`patch()`), der pro Testfall die Antwortsequenz 502 dann 200 liefert; Assertion auf Rueckgabewert UND Anzahl der tatsaechlich empfangenen Requests am Server (>= 2).

- **AC-2:** Given ein echter lokaler Server ist beim ersten Verbindungsversuch nicht erreichbar (Connection-Refused, z.B. Server startet erst nach kurzer Verzoegerung oder liefert einen simulierten Connect-Error) und beim zweiten Versuch erreichbar mit HTTP 200 / When `OpenMeteoProvider._request()` aufgerufen wird / Then liefert `_request()` ebenfalls die erfolgreiche Antwort zurueck, weil Connect-Errors genauso wie 5xx-Fehler zu einem Retry fuehren, nicht nur HTTP-Statuscodes.
  - Test: `tests/unit/test_openmeteo_retry.py`, echter TCP-Socket-basierter Aufbau ohne Mock; Assertion auf erfolgreichen Rueckgabewert nach mindestens einem fehlgeschlagenen Verbindungsversuch.

- **AC-3:** Given ein echter lokaler HTTP-Server liefert bei jedem Aufruf dauerhaft HTTP 404 / When `OpenMeteoProvider._request()` aufgerufen wird / Then wirft `_request()` sofort nach dem ersten Versuch eine `ProviderRequestError`, ohne dass ein zweiter Request an den Server geht (kein Fehlalarm-Retry fuer Client-Fehler).
  - Test: `tests/unit/test_openmeteo_retry.py`, echter lokaler HTTP-Server liefert konstant 404; Assertion auf geworfene `ProviderRequestError` UND dass der Server genau einen Request-Zaehler von 1 aufweist (kein Retry stattgefunden).

- **AC-4:** Given eine `ProviderRequestError`-Instanz mit `status_code=502` sowie eine zweite Instanz mit `status_code=404` / When `_is_retryable_error()` auf beide Instanzen angewendet wird / Then liefert die Funktion fuer die 502-Instanz `True` und fuer die 404-Instanz `False`.
  - Test: `tests/unit/test_openmeteo_retry.py`, direkter Aufruf von `_is_retryable_error()` mit konstruierten `ProviderRequestError`-Objekten (reiner Funktionstest, kein Server noetig, kein Verstoss gegen die No-Mock-Regel da keine externe Abhaengigkeit simuliert wird).

## Known Limitations

- Bei andauerndem 5xx verzoegert die interne Retry-Kaskade (bis zu ~62s Backoff ueber 5 Attempts, siehe `docs/specs/modules/api_retry.md`) den Wechsel zum #1115-Modell-Fallback spuerbar. Die Reihenfolge "erst Retry auf Provider-Ebene, dann Modell-Fallback" ist laut Issue-Abgrenzung bewusst so gewollt — kein Verhaltens-Change im Rahmen dieses Fixes noetig.
- Kein Retry bei 4xx-Client-Fehlern (unveraendert, analog zum GeoSphere-Referenzpattern in `docs/specs/modules/api_retry.md`).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner Bugfix an einer bestehenden Retry-Praedikat-Funktion, keine neue Architektur-Entscheidung. Geprueft gegen `docs/adr/` — kein bestehendes Retry-relevantes ADR vorhanden (die dort dokumentierten ADRs betreffen andere Themen: Multi-Tenant-Isolation, Provider-Fallback ohne Kaschieren #1115/ADR-0018, Alert-Schwellenwerte etc.). Das bestehende Retry-Verhalten selbst (Attempts, Backoff, Status-Codes) ist bereits in `docs/specs/modules/api_retry.md` spezifiziert und bleibt unveraendert — dieser Fix stellt lediglich sicher, dass das spezifizierte Verhalten tatsaechlich eintritt.

## Changelog

- 2026-07-08: Initial spec created
