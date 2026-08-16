---
entity_id: compare_endpoint_user_id
type: module
created: 2026-08-16
updated: 2026-08-16
status: draft
version: "1.0"
tags: [bugfix, security, mandantentrennung, compare]
---

# Compare-Endpoint: user_id-Pflichtparameter (Issue #1891)

## Approval

- [ ] Approved

## Purpose

`GET /api/compare` lädt Orte für den Sofortvergleich unabhängig vom eingeloggten
Nutzer immer über den Pseudo-Nutzer `"default"`, weil `run_comparison()`
`load_all_locations()` ohne `user_id`-Argument aufruft. Jeder eingeloggte Nutzer
bekommt beim Sofortvergleich die Orte des `default`-Nutzers statt seiner eigenen —
ein Cross-User-Datenleck und Verstoß gegen die in CLAUDE.md festgeschriebene
Mandantentrennungs-Pflicht. Diese Spec beschreibt den Fix: `user_id` als
Pflichtparameter aus dem Auth-Kontext (von Go injiziert) durchreichen, analog zu
16 anderen bereits korrekt implementierten Endpoints.

## Source

- **File:** `api/routers/compare.py`
- **Identifier:** `def run_comparison(...)` (Route `GET /api/compare`)

> **Schicht-Hinweis:** Python-Core / Domain-Backend (`api/routers/compare.py`,
> FastAPI Core über `api.main:app`). Keine Go-Änderung nötig — `internal/handler/proxy.go`
> (`CompareProxyHandler` + `appendUserID()`) injiziert `user_id` bereits korrekt in
> den Query-String, sobald der Python-Router den Parameter akzeptiert.

## Estimated Scope

- **LoC:** Produktivcode ~2-3 Zeilen; Testanpassungen ~8 Zeilen additiv (5 Bestandsdateien); neuer Test ~40-60 Zeilen
- **Files:** 6 Bestandsdateien (1 Produktivcode, 5 Bestandstests) + 1 neue Testdatei
- **Effort:** low-medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/loader.py::load_all_locations` | function | Nimmt `user_id`-Parameter bereits entgegen (Default `"default"`), muss nur mit echtem Wert aufgerufen werden |
| `internal/handler/proxy.go::CompareProxyHandler` | Go handler | Injiziert echte `user_id` bereits korrekt per `appendUserID()` in den Query-String — keine Änderung nötig |
| `internal/router/router.go` | Go router | Route liegt im authentifizierten Block (`AuthMiddleware`, Cookie-Pflicht) — kein anonymer Zugriff möglich |
| `api/routers/preview.py` | module | Referenzmuster für `user_id: str = Query(..., description=...)` als Pflichtparameter |

## Implementation Details

`api/routers/compare.py`, Funktion `run_comparison()` (Zeilen 25-38):

1. Signatur um `user_id: str = Query(..., description="Session-User (vom Go-Proxy injiziert)")` erweitern, analog `api/routers/preview.py:33`.
2. Aufruf `all_locations = load_all_locations()` → `all_locations = load_all_locations(user_id=user_id)`.

Kein Default-Wert (`Query(...)` statt z.B. `Query("default")`) — der einzige
Produktionsaufrufer ist `CompareProxyHandler` (Go), der `user_id` bereits
zuverlässig injiziert. Ein Default wie bei `api/routers/scheduler.py:291`
(`Query("default")`) würde den Fehler nur abschwächen statt strukturell
ausschließen und wird bewusst nicht übernommen.

Fünf Bestandstests rufen `GET /api/compare` derzeit ohne `user_id`-Query-Parameter
auf und brechen mit HTTP 422, sobald der Parameter Pflicht wird. Die Anpassung ist
additiv (`&user_id=...` an die jeweilige Aufruf-URL) — alle stubben
`load_all_locations` bereits mit `lambda *a, **kw: [...]`, keine
Stub-Signatur-Änderung nötig:

- `tests/tdd/test_hail_flag_metrics_catalog_and_compare_api.py:103`
- `tests/tdd/test_vorschau_anzeige_folgen_ortszone.py:477,521,597`
- `tests/tdd/test_sport_aware_scoring.py:251`
- `tests/unit/test_sofortvergleich_parallel.py:102-103` (Funktion `_abfrage()`)

## Expected Behavior

- **Input:** `GET /api/compare?location_ids=...&user_id=<session-user>` (weitere
  Query-Parameter wie `target_date`, `time_window_start/end`, `forecast_hours`,
  `activity_profile` unverändert)
- **Output:** Vergleichsergebnis (JSON) ausschließlich über die Orte des
  übergebenen `user_id`; ohne `user_id` HTTP 422 (FastAPI-Validierungsfehler bei
  fehlendem Pflichtparameter)
- **Side effects:** keine — reine Lesezugriff-Filterung, keine Persistenzänderung

## Acceptance Criteria

- **AC-1:** Given zwei Nutzer alice und bob mit jeweils eigenen, unterschiedlichen Orten in ihrer Persistenz / When beide `GET /api/compare` mit ihrer jeweiligen `user_id` aufrufen / Then bekommt jeder Nutzer ausschließlich seine eigenen Orte in der Antwort — nicht die Orte des jeweils anderen Nutzers und nicht die Orte des `default`-Nutzers.
  - Test: Zwei-Nutzer-Testfall (Kern-Schicht, ohne `live`/`real_data_root`-Marker) mit Stub für `load_all_locations`, der `user_id` tatsächlich auswertet (z.B. `lambda user_id=None, **kw: {"alice": [...], "bob": [...]}[user_id]`), und assertet, dass jede Antwort nur die zugehörigen Orte enthält.

- **AC-2:** Given der Endpoint `GET /api/compare` erwartet `user_id` als Pflichtparameter / When ein Aufruf ohne `user_id`-Query-Parameter erfolgt / Then antwortet der Server mit HTTP 422 (FastAPI-Validierungsfehler), da kein stiller Fallback auf `"default"` mehr möglich ist.
  - Test: Testfall ruft `GET /api/compare?location_ids=...` ohne `user_id` auf und prüft `response.status_code == 422`.

- **AC-3:** Given ein Nutzer mit gültiger `user_id` ruft den Sofortvergleich auf / When `GET /api/compare?location_ids=...&user_id=<gueltige-id>` mit sonst unveränderten Parametern aufgerufen wird / Then bleibt die Response-Struktur (Felder, Format) identisch zum Verhalten vor dem Fix, nur mit korrekt dem Nutzer zugeordneten Orten.
  - Test: Angepasste Bestandstests (5 Dateien, additiv um `&user_id=...` ergänzt) laufen weiterhin grün und prüfen weiterhin dieselben Response-Felder wie vor der Änderung.

## Known Limitations

- Der zweite in Issue #1891 gemeldete Befund (kein Limit auf die Anzahl der
  `location_ids`) ist laut PO-Entscheid bewusst nicht Teil dieser Spec und als
  Zeile im Sammel-Issue #1199 dokumentiert.
- Go-Seite (`internal/handler/proxy.go`) wird nicht verändert — sie injiziert
  `user_id` bereits korrekt; dieser Fix betrifft ausschließlich den Python-Core.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Bugfix-Konsistenz mit einem bereits etablierten, dokumentierten
  Muster (`user_id: str = Query(...)` als Pflichtparameter, angewendet in 16
  anderen authentifizierten Endpoints, z.B. `api/routers/preview.py`). Es wird
  keine neue Architekturentscheidung getroffen, sondern eine bestehende inkonsequent
  angewendete Regel nachträglich durchgesetzt.

## Changelog

- 2026-08-16: Initial spec created (Issue #1891)
