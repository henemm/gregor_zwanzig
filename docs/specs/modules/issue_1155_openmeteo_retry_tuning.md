---
entity_id: issue_1155_openmeteo_retry_tuning
type: bugfix
created: 2026-07-09
updated: 2026-07-09
status: draft
version: "1.0"
tags: [provider, weather, open-meteo, retry, fallback, bugfix, testing]
---

# Fix #1155 (+ #1154 + #1160): Open-Meteo Modell-Fallback-Retry begrenzen

## Approval

- [x] Approved

## Purpose

Begrenzt die Retry-Attempts pro Modell-Kandidat in der #1115-Fallback-Kette (`src/providers/openmeteo.py::fetch_forecast()`), damit die Gesamt-Failover-Zeit bei Totalausfaellen nicht kaskadiert (bisher ~30s x N Kandidaten). Nur der erste tatsaechlich angefragte (Primaer-)Kandidat behaelt den vollen Retry; Folge-Kandidaten werden mit reduziertem Retry angefragt. Ergaenzt zwei #1128-Folgefehler: einen fehlenden `httpx.ReadTimeout`-Prädikat-Test (#1154) und eine Praezisierung der #1128-Spec-Formulierung (#1154 F001), sowie einen fehlenden Retry-Backoff-Neutralisierer im #1115-Test-Seam (#1160), der seit #1128 real durch das volle tenacity-Backoff laeuft.

## Source

- **File:** `src/providers/openmeteo.py`
- **Identifier:** `def fetch_forecast(...)` — Modell-Fallback-Schleife (Z.841-867), `def _request(...)` (Z.478-518), `RETRY_ATTEMPTS`/`RETRY_WAIT_MIN`/`RETRY_WAIT_MAX` (Z.94-98)

**Schicht:** Python-Core / Domain-Backend (`src/providers/`) — korrekt zugeordnet, kein Frontend/Go betroffen. Test-Aenderungen liegen unter `tests/unit/` bzw. `tests/tdd/`, Doku-Praezisierung unter `docs/specs/modules/`.

## Estimated Scope

- **LoC:** ~50 gesamt (Produktivcode ~15, Testcode ~30, Doku ~5) — weit unter dem 250-LoC-Workflow-Limit
- **Files:** 4 (3 MODIFY, 1 CREATE — diese Spec)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `tenacity.retry` / `Retrying.retry_with()` | library | Tenacity-natives Per-Call-Override der Retry-Konfiguration (`stop`, `wait`) fuer einzelne Aufrufe von `_request`, ohne den globalen `@retry`-Decorator zu aendern |
| `ProviderRequestError` (`src/providers/base.py`) | class | Traegt `status_code`; unveraendert genutzt fuer 4xx-vs-5xx-Unterscheidung in der Fallback-Schleife |
| `issue_1128_openmeteo_retry_fix` (`docs/specs/modules/issue_1128_openmeteo_retry_fix.md`) | spec | Vorgaenger-Fix: `_is_retryable_error()` erkennt 5xx/Connect-Error/Read-Timeout ueberhaupt erst als retryable — Voraussetzung dafuer, dass Retry-Timing in diesem Bereich ueberhaupt spuerbar wird |
| `issue_1115_openmeteo_model_fallback` (Spec zu #1115) | spec | Definiert die Fallback-Kette selbst (Kandidatenliste, `fallback_model`/`fallback_reason`, AC-2 4xx-kein-Fallback) — dieser Fix aendert nur das Retry-Timing innerhalb dieser Kette, nicht ihre fachliche Logik |
| `test_issue_1141_cross_provider_fallback.py::_total_outage_seam` | test-pattern | Bewaehrtes Muster fuer Retry-Neutralisierung in Tests (`wait_none()` + `stop_after_attempt(1)` auf `._request.retry`) — Vorlage fuer #1160 |
| `test_openmeteo_retry.py::test_wrapped_connect_error_cause_is_retryable` | test-pattern | Vorlage fuer den #1154-ReadTimeout-Test |

## Implementation Details

### #1155 — Retry-Begrenzung pro Fallback-Kandidat (Prod-Change)

**Ist-Zustand:** In der Modell-Fallback-Schleife (`fetch_forecast()`, Z.841-867) durchlaeuft jeder Kandidat den vollen `tenacity`-Retry auf `self._request(...)` (5 Attempts, `wait_exponential(min=2, max=60)`, ~30s Wartezeit im Worst Case), **bevor** bei einem 5xx/transienten Fehler zum naechsten Kandidaten gewechselt wird (`continue`, Z.863). Bei einem Totalausfall aller Modelle kaskadiert das auf ~30s x N Kandidaten (N=5 inkl. ECMWF), was den kritischen Failover-Pfad spuerbar verzoegert (Incident 07./08.07.).

**Soll-Zustand (PO-Entscheidung, Tech-Lead-Mechanik):** Der **erste tatsaechlich angefragte Kandidat** (nach Endpoint-Dedup, Z.842-844) behaelt den vollen Retry (5 Attempts, exponentieller Backoff 2-60s) — ein einzelner 503-Blip auf dem feinsten Modell soll nicht sofort zu einem Downgrade auf ein groeberes Modell fuehren. **Jeder Folge-Kandidat** in der Kette wird nur noch mit einem reduzierten Retry angefragt: neue Modul-Konstante `FALLBACK_RETRY_ATTEMPTS = 1` (kein Backoff, `wait_none()`).

**Mechanismus:** Ein `first_request`-Flag (initial `True`, nach dem ersten tatsaechlich unternommenen Request auf `False` gesetzt) unterscheidet Primaer- von Folge-Kandidat innerhalb der Schleife. Fuer Folge-Kandidaten wird `_request` mit reduzierter Konfiguration aufgerufen:

```python
if first_request:
    response_data = self._request(cand_endpoint, params)
    first_request = False
else:
    response_data = self._request.retry_with(
        stop=stop_after_attempt(FALLBACK_RETRY_ATTEMPTS),
        wait=wait_none(),
    )(cand_endpoint, params)
```

`retry_with()` ist eine tenacity-native Methode auf dem dekorierten Callable, die eine neue `Retrying`-Instanz mit ueberschriebenen Parametern liefert, aber `reraise=True` und das Retry-Praedikat (`retry_if_exception(_is_retryable_error)`) unveraendert uebernimmt (verifiziert verfuegbar in der im Projekt gepinnten tenacity-Version). Kein Mock, keine Kopie der Retry-Logik.

**Unveraenderte Invarianten:**
- 4xx-Fehler fuehren weiterhin sofort zu `raise` (kein Fallback, AC-2 aus #1115) — unabhaengig von Primaer/Folge.
- 5xx/transiente Fehler fuehren weiterhin zum naechsten Kandidaten (`continue`).
- `ts.meta.fallback_model`/`fallback_reason="model_5xx"` werden bei erfolgtem Fallback weiterhin gesetzt (Non-Concealment, unveraendert).
- Die Cross-Provider-Weiche aus #1141 (Z.869-891, greift wenn ALLE Kandidaten scheitern) ist unberuehrt.
- Andere `_request`-Aufrufer (`:280` Availability-Check, `:648` Air-Quality, `:980` Ensemble) behalten den vollen Retry (5 Attempts, Backoff 2-60s) — nur der Aufruf innerhalb der Fallback-Schleife wird pro Folge-Kandidat reduziert.

**Effekt:** Die Failover-Gesamtzeit bei Totalausfall aller N Kandidaten sinkt von ~30s x N auf ~30s (Primaer-Kandidat) + ~0s x (N-1) (Folge-Kandidaten, kein Backoff).

### #1154 — Test-Luecke + Spec-Praezisierung (kein Prod-Bug)

**F002 (Test-Luecke):** `_is_retryable_error()` hat einen `httpx.ReadTimeout`-Erkennungszweig (Z.199 in `issue_1128`-Kontext), der bislang nicht durch einen eigenen Unit-Test abgedeckt ist — nur `httpx.ConnectError` wird getestet (`test_wrapped_connect_error_cause_is_retryable`, `tests/unit/test_openmeteo_retry.py:171-183`). Neuer Test `test_wrapped_read_timeout_cause_is_retryable` nach demselben Muster, aber mit `httpx.ReadTimeout` als `__cause__` der gewrappten `ProviderRequestError`.

**F001 (Spec-Praezisierung):** `docs/specs/modules/issue_1128_openmeteo_retry_fix.md:74` formuliert aktuell "Input ist immer eine ProviderRequestError, da `_request()` alle `httpx`-Exceptions vor dem Reraise wrapped". Das ist nicht literal wahr: Ein `json.JSONDecodeError` aus `response.json()` (Z.508) wird von keinem der beiden `except`-Zweige (`httpx.HTTPStatusError`, `httpx.RequestError`) abgefangen und erreicht `_is_retryable_error()` roh und ungewrappt — die Funktion liefert dafuer sicher `False` (kein `isinstance`-Match, kein Crash), aber die Formulierung "immer ProviderRequestError" ist praezisierungsbeduerftig. Der betroffene Satz wird auf sinngemaess "alle `httpx`-Exceptions werden gewrappt (JSON-Decodefehler nicht, dort greift `_is_retryable_error` sicher mit `False`)" geaendert. Reine Doku-Aenderung, kein Code-Change.

### #1160 — Fehlender Retry-Backoff-Neutralisierer im #1115-Test-Seam (reiner Test-Fix)

`tests/tdd/test_issue_1115_model_fallback.py::_provider_seam` (Z.185-196) hat — anders als das aequivalente `_total_outage_seam` aus #1141 (`tests/tdd/test_issue_1141_cross_provider_fallback.py:146-169`) — **keinen** Neutralisierer fuer das tenacity-Retry-Backoff. Seit #1128 (Retry-Praedikat greift jetzt tatsaechlich) laufen die #1115-Fehlerinjektions-Tests real durch das volle Backoff (~30s pro dauerhaft fehlschlagendem Endpoint), was Testlaufzeiten unnoetig aufblaeht und Timeout-Risiken in der CI erzeugt. Fix: dasselbe Muster aus #1141 in `_provider_seam` uebernehmen:

```python
monkeypatch.setattr(OpenMeteoProvider._request.retry, "wait", tenacity.wait_none())
monkeypatch.setattr(OpenMeteoProvider._request.retry, "stop", tenacity.stop_after_attempt(1))
```

**Wichtig — keine Redundanz zu #1155:** #1160 wird durch #1155 nicht ueberfluessig. Die #1115-Fehlerinjektions-Tests setzen typischerweise den **Primaer**-Kandidaten dauerhaft auf 503, und dessen Retry bleibt bei #1155 unveraendert voll (5 Attempts, Backoff 2-60s) — der Neutralisierer wird also weiterhin gebraucht, unabhaengig davon, dass Folge-Kandidaten nach #1155 selbst kein Backoff mehr haben.

## Expected Behavior

- **Input:** Wiederholte HTTP-Anfragen an mehrere Open-Meteo-Modell-Endpoints innerhalb einer `fetch_forecast()`-Ausfuehrung, wobei ein oder mehrere Kandidaten mit 5xx/transienten Fehlern antworten.
- **Output:** Der Primaer-Kandidat wird bis zu 5-mal mit exponentiellem Backoff versucht; jeder Folge-Kandidat wird hoechstens `FALLBACK_RETRY_ATTEMPTS` (=1) mal ohne Wartezeit versucht. Das fachliche Endergebnis (welches Modell liefert, `fallback_model`/`fallback_reason`, Cross-Provider-Fallback bei Totalausfall) ist identisch zum Vorzustand — nur das Timing aendert sich.
- **Side effects:** Deutlich kuerzere Reaktionszeit bei degradiertem/ausgefallenem Open-Meteo-Verteiler; andere `_request`-Aufrufer (Availability, Air-Quality, Ensemble) sind von der Aenderung nicht betroffen.

## Acceptance Criteria

- **AC-1:** Given ein echter lokaler HTTP-Testserver liefert fuer den Primaer-Kandidaten dauerhaft HTTP 503 und fuer alle Folge-Kandidaten ebenfalls dauerhaft HTTP 503 / When `fetch_forecast()` gegen diesen Server laeuft / Then werden die Folge-Kandidaten jeweils ohne mehrfache Wiederholung und ohne spuerbare Wartezeit zwischen den Versuchen angefragt (Gesamtzeit fuer alle Folge-Kandidaten zusammen bleibt klar unter der Zeit, die ein einziger voller Retry-Zyklus bräuchte), waehrend fuer den Fallback insgesamt weiterhin alle konfigurierten Kandidaten kontaktiert werden.
  - Test: `tests/tdd/test_issue_1115_model_fallback.py`, echter lokaler Fault-Server (kein Mock) mit Status-Map `{alle Endpoints: 503}`; Assertion auf Gesamtlaufzeit des Testfalls (Obergrenze deutlich unter "Primaer-Retry-Zeit x Anzahl Kandidaten") UND auf die Anzahl der tatsaechlich kontaktierten Endpoints (server.contacted).

- **AC-2:** Given ein echter lokaler HTTP-Testserver liefert fuer den Primaer-Kandidaten beim ersten und zweiten Aufruf HTTP 503 und beim dritten Aufruf HTTP 200 / When `fetch_forecast()` laeuft / Then liefert der Primaer-Kandidat am Ende erfolgreich, weil fuer ihn weiterhin mehrere Wiederholungsversuche stattfinden (unveraendertes Retry-Verhalten fuer den ersten Kandidaten).
  - Test: `tests/tdd/test_issue_1115_model_fallback.py`, echter lokaler Fault-Server mit Antwortsequenz 503/503/200 auf dem Primaer-Endpoint; Assertion auf Rueckgabewert (Modell = Primaer-Kandidat) UND auf die Anzahl der Requests, die der Server fuer diesen Endpoint gezaehlt hat (>=3).

- **AC-3:** Given ein echter lokaler Testserver liefert fuer den Primaer-Kandidaten dauerhaft HTTP 404 / When `fetch_forecast()` laeuft / Then wird sofort eine `ProviderRequestError` geworfen, ohne dass irgendein Folge-Kandidat kontaktiert wird, und ohne dass ein Retry auf dem Primaer-Kandidaten stattfindet (4xx-Invariante aus #1115 AC-2 bleibt unveraendert bestehen).
  - Test: `tests/tdd/test_issue_1115_model_fallback.py`, echter lokaler Fault-Server mit konstant 404 auf dem Primaer-Endpoint; Assertion auf geworfene Exception UND dass `server.contacted` nur den Primaer-Endpoint mit genau einem Aufruf enthaelt (keine Folge-Kandidaten, kein Retry).

- **AC-4:** Given ein echter lokaler Testserver liefert fuer den Primaer-Kandidaten dauerhaft 503 und fuer einen Folge-Kandidaten HTTP 200 / When `fetch_forecast()` laeuft und erfolgreich auf dem Folge-Kandidaten liefert / Then traegt das zurueckgegebene Ergebnis weiterhin `meta.fallback_model` gesetzt auf den erfolgreichen Folge-Kandidaten und `meta.fallback_reason == "model_5xx"` (Non-Concealment-Invariante unveraendert).
  - Test: `tests/tdd/test_issue_1115_model_fallback.py`, echter lokaler Fault-Server; Assertion direkt auf die `meta`-Felder des zurueckgegebenen `TimeSeries`-Objekts.

- **AC-5:** Given `OpenMeteoProvider._request` wird ausserhalb der Fallback-Schleife aufgerufen (z.B. ueber den Availability-Check oder den Air-Quality- bzw. Ensemble-Pfad) und der zugrundeliegende Server liefert wiederholt 503 gefolgt von 200 / When dieser Aufruf laeuft / Then durchlaeuft er weiterhin den vollen Retry (bis zu 5 Versuche mit exponentiellem Backoff) — die Reduktion aus #1155 betrifft ausschliesslich den Aufruf innerhalb der Fallback-Schleife.
  - Test: bestehender bzw. neuer Test in `tests/unit/test_openmeteo_retry.py` gegen einen echten lokalen HTTP-Server, der `_request()` direkt (nicht ueber `fetch_forecast()`) aufruft; Assertion auf Rueckgabewert nach mehrfachem 503 UND auf die Anzahl der beim Server eingegangenen Requests (>=2, konsistent mit unveraendertem `RETRY_ATTEMPTS=5`).

- **AC-6:** Given eine `ProviderRequestError`-Instanz, deren `__cause__` ein echter `httpx.ReadTimeout` ist / When `_is_retryable_error()` auf diese Instanz angewendet wird / Then liefert die Funktion `True`.
  - Test: `tests/unit/test_openmeteo_retry.py::test_wrapped_read_timeout_cause_is_retryable`, analog zu `test_wrapped_connect_error_cause_is_retryable` (Z.171-183), aber mit `httpx.ReadTimeout` statt `httpx.ConnectError` als geworfene Ursprungs-Exception; reiner Funktionstest ohne externe Abhaengigkeit, kein Mock noetig.

- **AC-7:** Given die #1115-Fehlerinjektions-Tests in `tests/tdd/test_issue_1115_model_fallback.py`, die den `_provider_seam`-Kontextmanager nutzen und einen dauerhaft fehlschlagenden Endpoint simulieren / When diese Tests nach der Aenderung laufen / Then ist die Laufzeit des einzelnen Testfalls klar unterhalb der Zeit, die das volle unveraenderte tenacity-Backoff (5 Attempts, bis zu ~62s) beanspruchen wuerde, weil `_provider_seam` denselben Retry-Neutralisierer (`wait_none()` + `stop_after_attempt(1)`) wie `_total_outage_seam` aus #1141 anwendet.
  - Test: bestehende Tests in `tests/tdd/test_issue_1115_model_fallback.py`, die `_provider_seam` verwenden; Assertion auf tatsaechliche Testlaufzeit (z.B. via `pytest --durations` oder expliziter Zeitmessung im Test) als Regressionsschutz gegen erneutes Weglassen des Neutralisierers.

## Known Limitations

- `FALLBACK_RETRY_ATTEMPTS = 1` bedeutet: ein einzelner transienter Blip auf einem Folge-Kandidaten fuehrt sofort zum Weiterschalten, ohne einen zweiten Versuch auf demselben Kandidaten. Bewusste Design-Entscheidung (PO/Tech-Lead): bei einem bereits degradierten Provider zaehlt schnelles Durchreichen zum naechsten Kandidaten mehr als ein zusaetzlicher Versuch auf dem aktuellen; die Cross-Provider-Weiche (#1141) und der naechste Briefing-Zyklus fangen verbleibende Restfaelle ab.
- Die Known-Limitation aus `docs/specs/modules/issue_1128_openmeteo_retry_fix.md` ("~62s-Verzoegerung pro 5xx-Kandidat vor Fallback") gilt nach diesem Fix nur noch fuer den Primaer-Kandidaten; Folge-Kandidaten sind davon nicht mehr betroffen. Diese Spec ersetzt die entsprechende Aussage funktional, die #1128-Spec selbst wird nur um den F001-Satz praezisiert (siehe Implementation Details), nicht strukturell umgeschrieben.
- `retry_with()` erzeugt bei jedem Folge-Kandidaten-Aufruf eine neue `Retrying`-Instanz zur Laufzeit — das ist tenacity-nativer, dokumentierter Mechanismus und kein Workaround, aber ein Implementierungsdetail, das bei zukuenftigen tenacity-Major-Upgrades erneut verifiziert werden sollte.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Feinjustierung eines bestehenden, bereits spezifizierten Retry-/Fallback-Mechanismus (#1115/#1128), keine neue Architektur-Entscheidung. Der Mechanismus (`retry_with()` als Per-Call-Override) folgt einem bereits im Projekt etablierten Pattern (Retry-Neutralisierung in Tests, #1141) und aendert keine Schnittstellen oder Datenmodelle. Geprueft gegen `docs/adr/` — kein bestehendes Retry-relevantes ADR vorhanden.

## Changelog

- 2026-07-09: Initial spec created — Buendel #1154/#1155/#1160
