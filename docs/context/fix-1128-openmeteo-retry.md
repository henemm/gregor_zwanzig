# Context: fix-1128-openmeteo-retry

## Request Summary

Issue #1128: In `src/providers/openmeteo.py::_request()` retryt der tenacity-Decorator HTTP-5xx-Fehler faktisch nie, weil `raise_for_status()` den `httpx.HTTPStatusError` innerhalb desselben Try-Blocks sofort in `ProviderRequestError` umwandelt — der Retry-Prädikat `_is_retryable_error` sieht nie den ursprünglichen `httpx.HTTPStatusError`, sondern nur die bereits gewrappte `ProviderRequestError`, für die `isinstance(exception, httpx.HTTPStatusError)` `False` liefert.

## Related Files

| File | Relevance |
|------|-----------|
| `src/providers/openmeteo.py:190-196` | `_is_retryable_error()` — Retry-Prädikat, prüft aktuell nur `httpx.HTTPStatusError`/`httpx.ConnectError`/`httpx.ReadTimeout` |
| `src/providers/openmeteo.py:466-513` | `_request()` mit `@retry`-Decorator; Except-Block Z.504-509 wrapped `HTTPStatusError` → `ProviderRequestError` **vor** dem Retry-Check |
| `src/providers/base.py:82-94` | `ProviderRequestError` — hat bereits `status_code: Optional[int]` Feld (eingeführt für #1115) |
| `src/providers/openmeteo.py:95-98` | Retry-Konstanten: `RETRY_ATTEMPTS=5`, `RETRY_WAIT_MIN=2`, `RETRY_WAIT_MAX=60`, `RETRY_STATUS_CODES={502,503,504}` |
| `src/providers/openmeteo.py:835-870` (ca.) | Modell-Fallback-Logik (#1115) fängt `ProviderRequestError` separat per `except`-Block außerhalb des Retry-Decorators ab und liest `e.status_code` — funktioniert unabhängig vom Retry-Bug (Abgrenzung laut Issue) |
| `docs/specs/modules/provider_openmeteo.md:228-249` | Spec beschreibt korrektes Zielverhalten: `_is_retryable_error` sollte direkt auf `raise_for_status()`-Exception angewendet werden, analog GeoSphere |
| `docs/specs/modules/api_retry.md` | Ursprungs-Spec für Retry-Pattern (GeoSphere-Provider), Referenzimplementierung ohne dieses Wrap-Problem |
| `docs/specs/modules/issue_1115_openmeteo_model_fallback.md:42,111` | Erwähnt `_is_retryable_error` als Wiederverwendung und referenziert #1128 explizit als bekannten, bewusst nicht mitgefixten Bug |

## Existing Patterns

- **GeoSphere-Provider** (`src/providers/geosphere.py`) implementiert das Retry-Pattern korrekt: Status-Code-Check passiert, bevor die Exception in einen Domain-Fehler gewrappt wird (siehe `api_retry.md`).
- **ProviderRequestError.status_code** existiert bereits als Feld (aus #1115) — kann direkt im Retry-Prädikat genutzt werden, ohne neue Felder einzuführen.
- **tenacity `retry_if_exception(_is_retryable_error)`**: Das Prädikat wird auf die Exception angewendet, die *innerhalb* der dekorierten Funktion geworfen wird — nicht auf die ursprüngliche `httpx`-Exception, wenn diese bereits vorher abgefangen und neu geworfen wurde.

## Dependencies

- **Upstream:** `httpx.Client.get()`, `response.raise_for_status()`, `tenacity` (`retry`, `retry_if_exception`, `stop_after_attempt`, `wait_exponential`, `before_sleep_log`)
- **Downstream:** Alle Aufrufer von `_request()` (Wetterdaten-Abruf, Metrik-Verfügbarkeits-Probe, Air-Quality, Modell-Fallback-Kette) profitieren von funktionierenden Retries bei transienten 5xx-Fehlern. Scheduler-Retry (#1113) und Modell-Fallback (#1115) mildern das Problem bereits auf höheren Ebenen ab — dieser Fix schließt die Lücke auf Provider-Ebene zusätzlich.

## Existing Specs

- `docs/specs/modules/provider_openmeteo.md` — Retry-Logic-Sektion beschreibt das korrekte Zielverhalten (Soll-Zustand vor diesem Bug)
- `docs/specs/modules/api_retry.md` — Referenz-Pattern (GeoSphere)
- `docs/specs/modules/issue_1115_openmeteo_model_fallback.md` — dokumentiert #1128 explizit als bewusst ausgeklammerten Folgefehler

## Risks & Considerations

- **Kritischer Datenpfad:** Änderung betrifft die Retry-Semantik für sämtliche Open-Meteo-API-Calls (alle Wettermodelle, Air-Quality, Ensemble-Spread, Metrik-Probe) — Fehlfunktion würde entweder zu viele oder zu wenige Retries auslösen.
- **Abgrenzung zu #1115:** Modell-Fallback-Logik (sofortiger Endpoint-Wechsel bei 5xx) läuft bereits *außerhalb* des Retry-Decorators und bleibt von diesem Fix unberührt — muss beim Fix beachtet werden, damit sich Retry (Provider-Ebene) und Fallback (Modell-Ebene) nicht gegenseitig aushebeln (z.B. 5x Retry mit Backoff, bevor überhaupt zum Fallback-Modell gewechselt wird → verlängerte Latenz).
- **Zwei mögliche Fix-Ansätze** (aus Issue):
  1. `raise_for_status()` außerhalb des wrappenden `except`-Blocks aufrufen (Status-Code-Check vor dem Wrap).
  2. Retry-Prädikat `_is_retryable_error` um Prüfung auf `ProviderRequestError.status_code in RETRY_STATUS_CODES` erweitern.
  - Ansatz 2 ist minimal-invasiv (nur `_is_retryable_error` ändern, `_request`-Struktur bleibt unverändert) und nutzt das bereits vorhandene `status_code`-Feld.
- **Kein bestehender Retry-Test:** Es gibt aktuell keinen Test, der das 5xx-Retry-Verhalten von `openmeteo._request()` verifiziert (nur Endpoint-Routing-Tests). RED-Test muss das reale Problem beweisen (z.B. echter lokaler HTTP-Server, der 502 liefert, dann Erfolg — kein Mock).
- **KEINE Mocked Tests** (Projektregel): Retry-Test muss gegen einen echten (lokalen) HTTP-Server laufen, der z.B. beim ersten Call 502 liefert und beim zweiten 200 — nicht gegen `Mock()`/`patch()`.

## Analysis

### Type
Bug

### Root-Cause-Verifikation (Adversary-Review durch analysis-challenger)

Root-Cause aus dem Issue **bestätigt**, aber **unvollständig**: Der Fix-Vorschlag aus dem Issue (`_is_retryable_error` um `ProviderRequestError.status_code`-Check erweitern) behebt **nur** den 5xx-Pfad (Z.504-509). Ein zweiter, identischer Wrap-Bug existiert bei Z.510-513: `except httpx.RequestError as e: ... raise ProviderRequestError(...) from e` — **ohne** `status_code` (bleibt `None`). `httpx.ConnectError`/`httpx.ReadTimeout` sind Subklassen von `httpx.RequestError` und werden dort ebenfalls **vor** dem Retry-Decorator gewrappt. Die `isinstance`-Prüfung in `_is_retryable_error` Z.194-195 auf `(httpx.ConnectError, httpx.ReadTimeout)` ist damit **genauso tot** wie die HTTPStatusError-Prüfung — betrifft alle drei ursprünglich vorgesehenen Retry-Fälle (5xx, Connect-Error, Read-Timeout), nicht nur 5xx.

**Rettungsanker:** `raise ... from e` setzt `exception.__cause__` auf die ursprüngliche `httpx`-Exception — dadurch lässt sich der Connect-/Timeout-Fall am gewrappten `ProviderRequestError` rückwirkend erkennen, ohne neues Feld: `isinstance(exception.__cause__, (httpx.ConnectError, httpx.ReadTimeout))`.

Kein 4xx-Fehlalarm-Risiko: `RETRY_STATUS_CODES = {502, 503, 504}` schließt 4xx korrekt aus.

**Interaktion mit #1115-Fallback:** Modell-Fallback-Schleife (Z.836-862 ca.) fängt `ProviderRequestError` *nach* dem (mit Fix nun greifenden) internen Retry ab. Bei andauerndem 5xx verzögert die interne Retry-Kaskade (Backoff bis zu ~62s worst-case über 5 Attempts) den Wechsel zum Fallback-Modell spürbar. Kein Korrektheits-Bug, aber eine Latenz-Nebenwirkung, die in den ACs benannt werden sollte.

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/providers/openmeteo.py` | MODIFY | `_is_retryable_error()` (Z.190-196) um `ProviderRequestError`-Fall erweitern: `status_code in RETRY_STATUS_CODES` ODER `__cause__` ist `ConnectError`/`ReadTimeout` |
| `tests/unit/test_openmeteo_retry.py` (neu) | CREATE | Echter lokaler HTTP-Server (kein Mock): 1. Call 502/Connect-Fehler, 2. Call 200 → beweist, dass Retry tatsächlich greift und Erfolg zurückgegeben wird |

### Scope Assessment
- Files: 2 (1 MODIFY, 1 CREATE)
- Estimated LoC: +~15 / -0 (Produktivcode ~8 Zeilen, Test ~40-60 Zeilen zählen nicht gegen harte Grenze da Test, aber LoC-Limit-Tool bewertet ggf. mit — bleibt weit unter 250)
- Risk Level: MEDIUM (kritischer Datenpfad, aber isolierte Funktion, keine Schnittstellenänderung)

### Technical Approach

`_is_retryable_error` wird erweitert, um zusätzlich `ProviderRequestError`-Instanzen zu erkennen:

```python
def _is_retryable_error(exception: Exception) -> bool:
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

Die bestehenden `httpx.*`-Zweige bleiben als Absicherung erhalten (z.B. falls `_is_retryable_error` isoliert mit einer rohen `httpx`-Exception getestet wird), sind aber im echten `_request`-Ablauf nach dem Fix weiterhin nie der greifende Zweig — der `ProviderRequestError`-Zweig ist der tatsächlich wirksame.

Kein struktureller Umbau von `_request()` nötig (Alternative aus dem Issue — `raise_for_status()` außerhalb des except aufrufen — wäre invasiver und würde das bestehende Error-Wrapping-Pattern aufbrechen, das an anderer Stelle (#1115-Fallback) bereits auf `ProviderRequestError.status_code` aufbaut).

### Dependencies
Siehe Context-Sektion oben. Keine neuen Dependencies.

### Open Questions
- [ ] Soll die AC explizit die Latenz-Interaktion mit dem #1115-Fallback benennen (Retry vor Fallback = bis zu ~62s Verzögerung pro Modell-Kandidat bei andauerndem 5xx)? → Empfehlung: ja, als "Known Limitation" in der Spec, kein Verhaltens-Change nötig, da Reihenfolge (erst Retry, dann Fallback) bereits laut Issue-Abgrenzung so gewollt ist.
