# Context: fix-1155-openmeteo-retry-tuning (#1154 + #1155 + #1160)

## Request Summary

Bündel dreier #1128-Folge-Issues im openmeteo-Retry-/#1115-Fallback-Bereich:
- **#1154** — fehlenden `httpx.ReadTimeout`-Unit-Test ergänzen + Spec-Satz „Input ist immer ProviderRequestError" präzisieren (kein Prod-Bug).
- **#1160** — #1115-Fehlerinjektions-Tests laufen seit #1128 real durch das volle tenacity-Backoff (~30s/Endpoint); Test-Seam mit `wait_none()`/`stop_after_attempt(1)` neutralisieren (Muster aus #1141). Reiner Test-Fix.
- **#1155** — **PO-Entscheidung Option b**: Retry-Attempts pro Modell-Kandidat in der #1115-Fallback-Kette begrenzen, damit die Gesamt-Failover-Zeit bei Totalausfällen nicht kaskadiert (~30–51s pro Kandidat).

## Related Files

| File | Relevance |
|------|-----------|
| `src/providers/openmeteo.py:94-98` | Retry-Konstanten: `RETRY_ATTEMPTS=5`, `RETRY_WAIT_MIN=2`, `RETRY_WAIT_MAX=60`, `RETRY_STATUS_CODES={502,503,504}` |
| `src/providers/openmeteo.py:471-480` | `@retry`-Dekoration auf `_request()` (tenacity, reraise=True) — **Kern von #1155** |
| `src/providers/openmeteo.py:190-201` | `_is_retryable_error()` — ReadTimeout-Zweig existiert (`:199`), aber untestet (#1154 F002) |
| `src/providers/openmeteo.py:509-518` | except-Wrapping: httpx→`ProviderRequestError from e`; JSONDecodeError wird NICHT gewrappt (#1154 F001) |
| `src/providers/openmeteo.py:841-867` | **#1115-Fallback-Schleife** in `fetch_forecast()` — pro Kandidat voller `_request`-Retry, dann `continue` bei 5xx/transient — **Angriffspunkt #1155** |
| `src/providers/openmeteo.py:410-440` | `_candidate_models()` — Kandidatenliste (feinstes zuerst, ECMWF zuletzt) |
| `tests/unit/test_openmeteo_retry.py:171-183` | `test_wrapped_connect_error_cause_is_retryable` — Vorbild für #1154-ReadTimeout-Test |
| `tests/tdd/test_issue_1115_model_fallback.py:185-196` | `_provider_seam` — **KEIN** Backoff-Neutralisierer → Ziel von #1160 |
| `tests/tdd/test_issue_1141_cross_provider_fallback.py:147-169` | `_total_outage_seam` — bewährtes `wait_none()`/`stop_after_attempt(1)`-Muster (Vorlage #1160) |
| `docs/specs/modules/issue_1128_openmeteo_retry_fix.md:74,92-94` | F001-Satz + Known-Limitation-~62s-Latenz (#1154/#1155 präzisieren) |

## Existing Patterns

- **Retry-Neutralisierung in Tests (#1141):** `monkeypatch.setattr(OpenMeteoProvider._request.retry, "wait", tenacity.wait_none())` + `"stop", tenacity.stop_after_attempt(1)`. Mock-frei, echte tenacity-Config, ändert nur Timing. Direkt in #1115-Seam (`_provider_seam`) übertragbar → #1160.
- **Prädikat-Unit-Test (#1128):** `raise httpx.X ... except → raise ProviderRequestError from cause → assert _is_retryable_error(wrapped)`. #1154 = exakt dieser Test mit `httpx.ReadTimeout`.
- **Fallback-Schleife:** iteriert `candidates`, `try: _request; except ProviderRequestError: 4xx→raise, 5xx/None→continue`. Non-concealment via `meta.fallback_model`/`fallback_reason="model_5xx"`.

## Dependencies

- **Upstream:** `_request()` nutzt tenacity `@retry`; Konstanten `RETRY_*`. Aufrufer von `_request`: `:280` (Availability), `:648` (Air-Quality), `:851` (Fallback-Schleife), `:980` (Ensemble).
- **Downstream:** `fetch_forecast()` → Risk Engine → Formatter. #1141-Cross-Provider-Fallback (`direct_provider_for`) greift, wenn ALLE Kandidaten scheitern (`:869-891`).

## Existing Specs

- `docs/specs/modules/issue_1128_openmeteo_retry_fix.md` — Retry-Fix + Known Limitation (zu präzisieren)
- `docs/specs/modules/api_retry.md` — Retry-Backoff-Referenz (~62s-Herleitung)

## Risks & Considerations

- **#1155 Kern-Design-Frage (für Analyse/Spec):** Wie Retry-Attempts *pro Kandidat in der Kette* begrenzen, ohne den globalen `_request`-Retry für Einzel-Provider-Nutzung (Availability, Air-Quality, Ensemble) zu schwächen? Kandidaten-Optionen für die Analyse-Phase:
  1. Voller Retry nur für den **Primär-Kandidaten**; Folge-Kandidaten mit reduziertem/keinem Backoff (Annahme: bei bereits degradiertem Provider ist schnelles Durchreichen wertvoller).
  2. Globales **Zeitbudget** für die gesamte Fallback-Kette.
  3. Reduzierte `stop_after_attempt` ab dem 2. Kandidaten.
  Da `@retry` ein fester Decorator ist, braucht per-Aufruf-Variation einen Mechanismus (z.B. interner `_request_once`/Parameter oder laufzeit-`.retry`-Anpassung analog #1141-Seam). **Muss in Analyse geklärt werden.**
- **#1155 berührt kritischen Failover-Pfad** (Incident 07./08.07.) → Adversary-Runde zwingend; Regressionsschutz für „Primär-5xx führt weiter zu korrektem Fallback + `fallback_reason`".
- **#1154 F001:** `json.JSONDecodeError` aus `response.json()` wird nicht gewrappt, erreicht `_is_retryable_error` roh → liefert `False` (sicher, kein Crash). Nur Spec-Formulierung präzisieren, KEIN Code-Change.
- **#1160 reiner Test-Fix** — darf Prod-Verhalten nicht ändern, nur Test-Timing. **NICHT** redundant nach #1155: Die #1115-Tests setzen den **Primär**-Kandidaten dauerhaft auf 503, und der Primär-Retry bleibt bei #1155 unverändert voll (5 Attempts, ~30s) → Seam-Neutralisierer weiterhin nötig.

## Analysis

### Type
Bündel: 1× Prod-Change (#1155), 2× Test-/Doku (#1154, #1160). Alle #1128-Folgen.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/providers/openmeteo.py` | MODIFY | #1155: Fallback-Schleife (`:841-867`) — Primär-Kandidat voller Retry, Folge-Kandidaten reduzierter Retry via `_request.retry_with(...)`; neue Konstante `FALLBACK_RETRY_ATTEMPTS` |
| `tests/tdd/test_issue_1115_model_fallback.py` | MODIFY | #1160: `_provider_seam` (`:185-196`) — `wait_none()`/`stop_after_attempt(1)`-Neutralisierer (Muster #1141); #1155: Regressions-Test „Failover-Zeit bei N Kandidaten bleibt beschränkt" |
| `tests/unit/test_openmeteo_retry.py` | MODIFY | #1154 F002: `test_wrapped_read_timeout_cause_is_retryable` analog `:171-183` |
| `docs/specs/modules/issue_1128_openmeteo_retry_fix.md` | MODIFY | #1154 F001: Satz `:74` präzisieren (JSONDecodeError-Ausnahme); Known-Limitation `:92-94` auf #1155-Verhalten aktualisieren |
| `docs/specs/modules/issue_1155_openmeteo_retry_tuning.md` | CREATE | Neue Spec fürs Bündel mit AC-N |

### Scope Assessment
- Files: 5 (3 MODIFY Code/Test, 1 MODIFY Spec, 1 CREATE Spec)
- Estimated LoC: +50 / -5 (unter 250-Limit)
- Risk Level: MEDIUM — berührt kritischen Failover-Pfad, aber bounded, `retry_with` mock-frei, Regressionsschutz vorhanden

### Technical Approach (#1155 — Tech-Lead-Entscheidung)
**Policy:** Der **erste tatsächlich angefragte** (Primär-)Kandidat behält den vollen Retry (5 Attempts, 2–60s) — schützt die Normalfall-Resilienz (ein einzelner 503-Blip auf dem feinsten Modell soll NICHT sofort auf ein gröberes Modell downgraden). **Jeder Folge-Kandidat** in der Kette wird nur noch mit `FALLBACK_RETRY_ATTEMPTS` (= 1, kein Backoff) angefragt.

**Mechanismus:** `self._request.retry_with(stop=stop_after_attempt(FALLBACK_RETRY_ATTEMPTS), wait=wait_none())(cand_endpoint, params)` für Folge-Kandidaten — tenacity-natives, mock-freies Per-Call-Override; `reraise=True` bleibt erhalten. Ein `first_request`-Flag unterscheidet Primär vs. Folge (nach Endpoint-Dedup).

**Effekt:** Failover-Gesamtzeit bei Totalausfall sinkt von ~30s × N Kandidaten auf ~30s (Primär) + ~0s × (N−1) Folge-Kandidaten. Verhalten (Fallback bei 5xx, 4xx→raise, `fallback_reason`) unverändert.

### Dependencies
- `_request` weiter zentral; `retry_with` ändert nur den Aufruf in der `fetch_forecast`-Schleife. Andere `_request`-Aufrufer (`:280`, `:648`, `:980`) unberührt → voller Retry.
- #1141-Cross-Provider-Weiche (`:869-891`) unberührt.

### Open Questions
- [x] Mechanismus für per-Kandidat-Retry → `retry_with` (verifiziert verfügbar)
- [x] Redundanz #1160 nach #1155 → nein, beide nötig (Primär-Retry unverändert)
- [ ] `FALLBACK_RETRY_ATTEMPTS`-Wert: Vorschlag **1** (kein Retry auf Folge-Kandidaten). Alternativ 2 (ein Retry für seltenen Folge-Blip). Empfehlung: 1 — bei bereits degradiertem Provider zählt schnelles Durchreichen; Cross-Provider-Fallback + nächster Briefing-Zyklus fangen Rest. → in AC-Freigabe ratifizieren.
