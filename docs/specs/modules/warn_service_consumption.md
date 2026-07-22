---
entity_id: warn_service_consumption
type: module
created: 2026-07-22
updated: 2026-07-22
status: draft
version: "1.0"
tags: [official-alerts, egress, observability, meteoalarm]
workflow: feat-1348-warn-consumption
---

<!-- Issue #1348 — Scheibe 2a von #1337 -->

# Warn-Dienste: Verbrauch senken + sichtbar machen (Scheibe 2a von #1337)

## Approval

- [ ] Approved

## Purpose

MeteoAlarm (amtliche Warnungen AT/IT) liefert in Prod dauerhaft HTTP 429 —
Root-Cause-Analyse (`docs/context/feat-1348-warn-consumption.md`) zeigt: der
300s-Erfolgs-Cache ist kürzer als der 15-Minuten-Scheduler-Takt, daher löst
praktisch jeder Tick einen echten Abruf aus (~8/h bei 2 Ländern), und ein 429
wird heute unauffällig weiterverfolgt statt zurückzuweichen. Diese Scheibe
senkt den Verbrauch (warngerecht längerer Cache), macht Erschöpfung sichtbar
(429-bewusster Rückzug + lauter Log) und schafft Observability (Egress-Zähler)
für alle fünf Warn-Dienste — ohne Renderer- oder Test/Staging-Isolations-Arbeit
(diese folgen als Scheibe 2b bzw. eigene Scheibe).

## Source

- **File:** `src/services/official_alerts/warn_egress.py` (NEU) — geteilter
  Cache+429-Backoff+Zähler-Kern
- **Identifier:** `cached_fetch()`, `log_warn_service_call()`,
  `WARN_SUCCESS_TTL`, `WARN_FAILURE_TTL`

> **Schicht:** reines Python-Core-Backend (`src/services/official_alerts/`,
> FastAPI-Domäne). Kein Go-/Frontend-Anteil.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/providers/call_log.py` (`log_api_call`) | module | Vorbild für Struktur des Egress-Zählers (append-only jsonl, fail-soft, `data/diagnostics/`) |
| `httpx.Response` | lib | Statuscode-/Header-Auswertung (`Retry-After`) ohne `raise_for_status()` |
| `src/services/official_alerts/meteoalarm.py` (`_get_cached_index`) | module | Primärer Migrationsort (Live-Brand, alle beobachteten 429 liegen hier) |
| `src/services/official_alerts/vigilance.py` (`_get_cached_cartevigilance`) | module | Erweiterung, falls LoC-Rahmen reicht (AC-11) |
| `src/services/official_alerts/geosphere_warn.py` (`_get_cached_warnings`) | module | Erweiterung, falls LoC-Rahmen reicht (AC-11) |
| `src/services/official_alerts/meteo_forets.py` (`_get_cached_departement`) | module | Erweiterung, falls LoC-Rahmen reicht (AC-11) |
| `src/services/official_alerts/massif_closure.py` (`_get_cached_daily_json`) | module | Erweiterung, falls LoC-Rahmen reicht (AC-11) |
| `docs/specs/modules/egress_guard.md` (`INVENTORY`) | spec | Hosts bereits als `TEST_ACCESS` deklariert — diese Scheibe ändert das Inventar NICHT (Scheibe 2b) |

## Estimated Scope

- **LoC:** ~110 (warn_egress.py, neu) + ~-10 bis +15 netto je migriertem Dienst
  (Cache-Logik wird ersetzt, nicht addiert) + Tests. MUST-Scope (Helfer +
  MeteoAlarm) allein bleibt sicher im 250-LoC-Rahmen; SHOULD-Erweiterung
  (AC-11, vier weitere Dienste) kann den Rahmen sprengen — siehe „Priorisierung"
  unten und offene PO-Entscheidung.
- **Files:** 1 neu (`warn_egress.py`), 1 sicher geändert (`meteoalarm.py`),
  4 optional geändert (`vigilance.py`, `geosphere_warn.py`, `meteo_forets.py`,
  `massif_closure.py`), 2 Testdateien (1 neu, 1 erweitert; ggf. 4 weitere
  erweitert bei AC-11)
- **Effort:** medium

## Priorisierung (MUST vs. SHOULD)

**MUST (Kern dieser Spec):** `warn_egress.py` + vollständige Migration von
`meteoalarm.py` (Live-Brand, alle Prod-429 laufen über den Index-Endpunkt
dieses Diensts). Alle AC-1 bis AC-10 gelten für diesen Pfad und sind
verpflichtend.

**SHOULD (AC-11, nur falls LoC-Rahmen reicht):** dieselbe Migration für
`vigilance.py`, `geosphere_warn.py`, `meteo_forets.py`, `massif_closure.py` —
strukturell identisches Muster (Cache-Dict bleibt pro Modul, nur die
`_get_cached_*`-Funktionskörper werden auf `cached_fetch()` umgestellt). Wird
das LoC-Budget eng, implementiert der Developer nur MUST und öffnet ein
Folge-Issue für die restlichen vier Dienste (keine Sammel-Zeile — bewusste
Scope-Trennung, kein Nebenbefund). **Offene Entscheidung für PO/Freigabe:**
soll AC-11 in diesem Workflow verbindlich versucht werden, oder von vornherein
als Folge-Issue geplant werden? (Siehe Zusammenfassung am Ende.)

## Implementation Details

### Warngerechter Erfolgs-TTL

`WARN_SUCCESS_TTL = 1800.0` (30 Minuten), `WARN_FAILURE_TTL = 60.0`
(unverändert). Begründung: der externe Scheduler-Takt ist 15 Minuten (900s).
Mit der heutigen 300s-Erfolgs-TTL ist der Cache bei jedem Tick bereits
abgelaufen → praktisch jeder Tick löst einen echten Call aus. Mit 1800s
(= 2 Takte) trifft im Schnitt jeder zweite Tick den Cache → Halbierung des
Verbrauchs pro Dienst allein durch die TTL, unabhängig vom 429-Pfad. Amtliche
Warnungen ändern Onset/Expire im Stunden-, nicht Minutenbereich — 30 Minuten
Latenz bis eine neue/geänderte Warnung sichtbar wird ist für ein
Planungs-Briefing (kein Live-Sicherheitsdienst, s. `project_frontend_purpose`)
vertretbar. Modul-Alias `CACHE_TTL = WARN_SUCCESS_TTL` /
`FAILURE_CACHE_TTL = WARN_FAILURE_TTL` bleibt in jedem migrierten Dienst
erhalten, damit bestehende Tests, die auf den Modul-Attributnamen referenzieren
(z.B. `meteoalarm.CACHE_TTL`), unverändert funktionieren — der Wert ändert
sich, der Attributname und seine Rolle im Cache-Eintrag nicht.

### 429-bewusster Rückzug

`cached_fetch()` ruft `request_fn()` auf und inspiziert `resp.status_code`
**ohne** `raise_for_status()` (Statusfehler werden explizit verzweigt statt
generisch als Exception behandelt). Bei `429`:
`backoff = max(retry_after_sekunden or 0.0, WARN_SUCCESS_TTL)` — respektiert
den `Retry-After`-Header (nur numerisches Sekunden-Format, siehe „Known
Limitations"), sonst mindestens die volle Erfolgs-TTL (kein Dauerfeuer im
15-Minuten-Takt). Der Cache-Eintrag bekommt `ttl=backoff`, sodass der nächste
Aufruf erst nach Ablauf dieses Fensters wieder einen echten Call auslöst.
Alle anderen HTTP-Fehler (4xx/5xx außer 429) sowie Netzwerk-/Timeout-Fehler
bleiben beim bisherigen `WARN_FAILURE_TTL` (60s) — unverändertes Verhalten,
kein neues Risiko für bestehende Fail-soft-Tests.

### Lautes Logging

429 bekommt einen eigenen `logger.warning(...)`-Aufruf mit explizitem
`"HTTP 429"` und der berechneten Backoff-Dauer im Log-Text — unterscheidbar
von der generischen `"%s-Abruf fehlgeschlagen"`-Meldung für andere Fehler.
Kein Downgrade auf DEBUG, kein Verschlucken.

### Egress-Zähler

`log_warn_service_call(service, host, status, cache_hit, retry_after=None)`
hängt (fail-soft, analog `call_log.log_api_call`) eine JSONL-Zeile an
`data/diagnostics/warn_service_calls.jsonl` (bereits via `data/diagnostics/`
gitignored) mit Feldern `ts, service, host, status, cache_hit, retry_after`.
Wird bei JEDEM `cached_fetch()`-Durchlauf aufgerufen — sowohl bei Cache-Hit
(`status=None, cache_hit=True`, kein echter Call) als auch bei echtem Call
(Erfolg/Fehler/429, `cache_hit=False`).

### Geteilter Helfer statt 5× Copy-Paste

Alle fünf Warn-Dienste haben strukturell identische Cache-Einträge
(`{"data", "fetched_at", "ttl"}`) und identisches TTL-Muster — laut
Projektregel „Code-Duplikate konsolidieren" wird das EINMAL in
`cached_fetch()` gebaut. Jeder Dienst behält seinen eigenen Modul-Cache-Dict
(z.B. `meteoalarm._index_cache`, `vigilance._cache`) und übergibt ihn als
Parameter — kein globaler Cache-State, keine Kollision zwischen Diensten.
Dienst-spezifisch bleibt außerhalb des Helfers: URL-Bau, Query-Parameter,
Auth-Header, Antwort-Parsing (`parse_fn`) — der Helfer kennt keine
API-spezifische Struktur.

### Zeit-Injektion für deterministische Tests

`cached_fetch(..., clock: Callable[[], float] = time.monotonic)` — Tests
können entweder direkt eine Fake-Clock übergeben (reiner Unit-Test des
Helfers) oder `warn_egress.time.monotonic` per `monkeypatch` überschreiben
(Integrationstest über einen echten Dienstpfad, z.B. `meteoalarm.fetch()`),
um TTL-Ablauf/Backoff-Fenster ohne echtes Warten zu beweisen.

### Beispiel (MeteoAlarm-Migration, gekürzt)

```python
def _get_cached_index(country: str) -> Optional[dict]:
    key = os.environ.get("GZ_METEOALARM_APIKEY")
    ...  # url/start/end wie bisher
    def _do_request() -> httpx.Response:
        return httpx.get(url, params={...}, headers={...}, timeout=TIMEOUT)
    def _parse(resp: httpx.Response) -> dict:
        if resp.status_code == 204 or not resp.content.strip():
            return {"features": []}
        return resp.json()
    return cached_fetch(
        cache=_index_cache, cache_key=country, service="meteoalarm",
        host="api.meteoalarm.org", request_fn=_do_request, parse_fn=_parse,
    )
```

Die anderen vier Dienste (falls AC-11 im Scope) folgen demselben Muster mit
ihrem jeweiligen `cache`, `cache_key` (Land/Koordinate/Département/Source-DEPT)
und `request_fn`.

## Expected Behavior

- **Input:** wiederholte `fetch()`-Aufrufe der Warn-Dienste innerhalb
  unterschiedlicher Zeitfenster; HTTP-Antworten mit Status 2xx/204/429/4xx/5xx;
  Netzwerkfehler
- **Output:** deutlich weniger echte HTTP-Calls pro Zeiteinheit (TTL-Effekt);
  bei 429 ein langes, respektiertes Backoff-Fenster statt Taktfeuer; jede
  Cache-Entscheidung (Hit/Miss/429) als jsonl-Zeile sichtbar
- **Side effects:** append-only Datei `data/diagnostics/warn_service_calls.jsonl`
  (fail-soft, darf nie den eigentlichen Abruf beeinträchtigen)

## Test Plan

### TDD-Vorstufe (PFLICHT vor jeder Code-Änderung)

Charakterisierungstest des HEUTIGEN Verhaltens (`CACHE_TTL == 300.0`,
`FAILURE_CACHE_TTL == 60.0`, Cache-Hit im 300s-Fenster löst laut
Netz-Sentinel keinen echten Call aus) wird VOR dem Umbau geschrieben und
grün gegen den Ist-Stand ausgeführt — dient als Regressions-Anker, damit der
Umbau nachweisbar nur TTL-Werte/429-Pfad ändert, nicht die Cache-Mechanik
selbst. Dieser Test wird nach der Umstellung durch die neuen TTL-Tests
(AC-1/AC-3) ersetzt bzw. gelöscht — kein Bestandteil der finalen Suite, da er
absichtlich einen jetzt überholten Wert prüft.

### Automated Tests (TDD RED)

- [ ] `tests/tdd/test_warn_service_egress.py::test_cache_hit_within_ttl_makes_no_real_call` —
  AC-2: Cache-Hit-Pfad via Netz-Sentinel (request_fn wirft bei Aufruf) beweist,
  dass `cached_fetch()` bei einem Treffer NIE `request_fn()` aufruft.
- [ ] `tests/tdd/test_warn_service_egress.py::test_cache_miss_after_ttl_triggers_real_call` —
  AC-3: Fake-Clock über `WARN_SUCCESS_TTL` hinaus vorgespult, `request_fn`
  wird tatsächlich aufgerufen.
- [ ] `tests/tdd/test_warn_service_egress.py::test_429_with_retry_after_sets_backoff` —
  AC-4: echtes `httpx.Response(429, headers={"Retry-After": "120"})`-Objekt
  (kein Mock, real konstruiert), Backoff = `max(120, WARN_SUCCESS_TTL)`.
- [ ] `tests/tdd/test_warn_service_egress.py::test_429_without_retry_after_defaults_to_success_ttl` —
  AC-5: `httpx.Response(429)` ohne Header, Backoff == `WARN_SUCCESS_TTL`.
- [ ] `tests/tdd/test_warn_service_egress.py::test_429_logs_loudly` — AC-6:
  `caplog` enthält `"429"` und die Backoff-Dauer im Log-Text.
- [ ] `tests/tdd/test_warn_service_egress.py::test_real_call_appends_jsonl_line` —
  AC-7: echte Datei wird geschrieben (temp-`WARN_CALLS_PATH` via monkeypatch),
  Zeile enthält `service/host/status/cache_hit=false`.
- [ ] `tests/tdd/test_warn_service_egress.py::test_cache_hit_appends_jsonl_line_without_call` —
  AC-8: Zeile mit `cache_hit=true, status=null`, UND Netz-Sentinel beweist
  keinen echten Call.
- [ ] `tests/tdd/test_warn_service_egress.py::test_429_marked_in_jsonl` — AC-9:
  Zeile enthält `status=429`, `retry_after` gefüllt bzw. `null`.
- [ ] `tests/tdd/test_meteoalarm_source.py::test_ttl_ist_dreissig_minuten` —
  AC-1: `meteoalarm.CACHE_TTL == 1800.0`, `meteoalarm.FAILURE_CACHE_TTL == 60.0`.
- [ ] `tests/tdd/test_meteoalarm_source.py::test_429_lokaler_server_retry_after_respektiert` —
  AC-4/AC-6 End-zu-Ende über den echten `meteoalarm.fetch()`-Pfad: lokaler
  `http.server` (analog bestehendem `_BrokenJSONHandler`/`_EmptyBody204Handler`-
  Muster) liefert 429 + `Retry-After`, geprüft wird der resultierende
  `_index_cache`-TTL-Eintrag.
- [ ] Bestehende Tests bleiben unverändert grün (AC-10): insbesondere
  `test_leerer_index_204_ist_kein_fehler` (prüft bereits gegen das
  Modul-Attribut `meteoalarm.CACHE_TTL`, nicht gegen die Zahl 300 — bleibt
  daher ohne Änderung korrekt), `test_ac5a/b/c/d`, `test_ac1`..`test_ac7`.
- [ ] (AC-11, falls im Scope) je ein analoger TTL-Test in
  `test_issue_1035_vigilance_source.py` und den Testsuiten der übrigen drei
  Dienste; bestehende Suiten dieser vier Dienste bleiben unverändert grün.

Kein Mock-Theater: `cached_fetch()`-Tests konstruieren echte `httpx.Response`-
Objekte und einen echten Netz-Sentinel (request_fn, der bei ungewolltem Aufruf
wirft) — kein `Mock()`/`patch()`, das nur die eigene Annahme zurückspiegelt.
Die jsonl-Datei wird real geschrieben und real zurückgelesen. Zeit wird über
den `clock`-Parameter bzw. `monkeypatch` auf `time.monotonic` injiziert, kein
echtes Warten.

## Acceptance Criteria

- **AC-1:** Given `warn_egress.WARN_SUCCESS_TTL` und `meteoalarm.CACHE_TTL` / When das Modul importiert wird / Then ist der Wert 1800.0 Sekunden (30 Minuten), `FAILURE_CACHE_TTL` bleibt bei 60.0 Sekunden unverändert
  - Test: `test_meteoalarm_source.py::test_ttl_ist_dreissig_minuten`

- **AC-2:** Given ein Cache-Eintrag wurde vor weniger als 1800s erfolgreich gesetzt / When `cached_fetch()` erneut mit demselben `cache_key` aufgerufen wird / Then wird `request_fn()` NICHT aufgerufen (Netz-Sentinel-Beweis), die gecachten Daten werden zurückgegeben
  - Test: `test_warn_service_egress.py::test_cache_hit_within_ttl_makes_no_real_call`

- **AC-3:** Given ein Cache-Eintrag ist laut injizierter Fake-Clock älter als 1800s / When `cached_fetch()` erneut aufgerufen wird / Then wird `request_fn()` tatsächlich aufgerufen (echter Cache-Miss nach Ablauf)
  - Test: `test_warn_service_egress.py::test_cache_miss_after_ttl_triggers_real_call`

- **AC-4:** Given eine HTTP-429-Antwort mit `Retry-After: 120` / When `cached_fetch()` diese verarbeitet / Then wird das Backoff-Fenster auf `max(120, 1800) = 1800` Sekunden gesetzt (Retry-After respektiert, aber nie kürzer als die Erfolgs-TTL)
  - Test: `test_warn_service_egress.py::test_429_with_retry_after_sets_backoff`, `test_meteoalarm_source.py::test_429_lokaler_server_retry_after_respektiert`

- **AC-5:** Given eine HTTP-429-Antwort OHNE `Retry-After`-Header / When `cached_fetch()` diese verarbeitet / Then wird das Backoff-Fenster auf `WARN_SUCCESS_TTL` (1800s) gesetzt — kein 15-Minuten-Dauerfeuer im Scheduler-Takt
  - Test: `test_warn_service_egress.py::test_429_without_retry_after_defaults_to_success_ttl`

- **AC-6:** Given eine HTTP-429-Antwort tritt auf / When der Fehlerpfad durchlaufen wird / Then enthält der WARNING-Log-Eintrag explizit den Text "429" und die berechnete Backoff-Dauer, unterscheidbar von der generischen Fehler-Meldung anderer Statuscodes
  - Test: `test_warn_service_egress.py::test_429_logs_loudly`

- **AC-7:** Given ein Cache-Miss löst einen echten HTTP-Call aus / When die Antwort verarbeitet ist / Then wird eine Zeile mit `service, host, status, cache_hit=false` an `data/diagnostics/warn_service_calls.jsonl` angehängt
  - Test: `test_warn_service_egress.py::test_real_call_appends_jsonl_line`

- **AC-8:** Given ein Cache-Hit innerhalb der TTL / When `cached_fetch()` aufgerufen wird / Then wird eine Zeile mit `cache_hit=true, status=null` angehängt UND per Netz-Sentinel bewiesen, dass kein echter Call erfolgte
  - Test: `test_warn_service_egress.py::test_cache_hit_appends_jsonl_line_without_call`

- **AC-9:** Given ein 429 tritt auf / When die Zähler-Zeile geschrieben wird / Then enthält sie `status=429` und `retry_after` (Sekundenwert oder `null` bei fehlendem Header)
  - Test: `test_warn_service_egress.py::test_429_marked_in_jsonl`

- **AC-10:** Given die bestehende MeteoAlarm-Testsuite (204-Fall, fail-soft ohne ENV, kaputtes Index-JSON, kaputtes CAP-XML, Fehler-Isolation der Registry) vor dieser Umstellung / When der Umbau auf `cached_fetch()` erfolgt / Then bleiben alle diese Tests unverändert grün, ohne Anpassung ihrer Assertions
  - Test: vollständiger Lauf von `test_meteoalarm_source.py` (bestehende Tests, unverändert)

- **AC-11 (SHOULD, nur falls LoC-Rahmen reicht):** Given die vier übrigen Warn-Dienste (Vigilance/GeoSphere/MeteoForets/MassifClosure) nutzen ebenfalls `cached_fetch()` / When ihre bestehenden Testsuiten nach der Migration laufen / Then bleiben alle bestehenden Assertions grün UND ihre Erfolgs-TTL beträgt ebenfalls 1800s
  - Test: bestehende Suiten der vier Dienste (unverändert) + je ein neuer TTL-Wert-Test pro Dienst

## Known Limitations

- `Retry-After` wird NUR im numerischen Sekunden-Format ausgewertet — die
  alternative HTTP-Date-Form (`Retry-After: Wed, 21 Oct 2026 07:28:00 GMT`)
  wird als „kein Header" behandelt (Fallback auf `WARN_SUCCESS_TTL`). Bisher
  ist aus den Prod-429-Logs nicht belegt, ob MeteoAlarm überhaupt einen
  `Retry-After`-Header sendet — sobald ein echter Header live beobachtet
  wird, ggf. Fixture/Parsing nachziehen.
- Kein exaktes Alignment auf das nächste 15-Minuten-Takt-Vielfache (das
  Modul kennt den externen Scheduler-Takt nicht) — als praktikable Näherung
  wird mindestens die volle Erfolgs-TTL (1800s = 2 Takte) als Backoff
  verwendet.
- Migration der vier übrigen Warn-Dienste (AC-11) ist SHOULD, kein MUST —
  wird sie aus LoC-Gründen getrimmt, entsteht ein dediziertes Folge-Issue
  (bewusste Scope-Trennung, kein Sammel-Eintrag #1199).
- Test/Staging-Isolation der Warn-APIs (Guard-Inventar `TEST_ACCESS`→`BLOCKED`
  + Attrappen + `live`-Marker-Disziplin) ist explizit NICHT Teil dieser Spec —
  Scheibe 2b von #1337.
- Briefing-sichtbarer Hinweis „Warnungen nicht abrufbar" bei anhaltendem
  Ausfall (#1346-Prinzip) berührt Renderer + Renderer-Mail-Gate #811 und ist
  eine eigene, spätere Scheibe.
- `warn_egress.py` deckt nur die fünf `official_alerts`-Dienste ab, nicht die
  restlichen 14 Türen aus `reference_env_isolation_all_external_services`.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** reine Konsolidierung von Cache-/Backoff-/Observability-Logik
  innerhalb einer bestehenden Provider-Schicht (`official_alerts/`) — berührt
  keine der ADR-relevanten Entscheidungsflächen (Kanäle, Provider-Auswahl,
  Datenmodell/Persistenz, Auth, Editor-Paradigma, Test-/Deploy-Strategie).
  Kein neuer Provider, keine neue Datenquelle, keine Schema-Änderung.

## Changelog

- 2026-07-22: Initial spec erstellt — Issue #1348, Scheibe 2a von #1337
