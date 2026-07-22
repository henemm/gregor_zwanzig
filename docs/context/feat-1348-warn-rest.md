# Context: feat-1348-warn-rest (AC-11 von #1348 — die 4 übrigen Warn-Dienste)

## Request Summary
Dieselbe Verbrauchs-Behandlung wie MeteoAlarm (Scheibe 2a) für die vier übrigen
Warn-Dienste: 30-Min-Cache + 429-Rückzug + Egress-Zähler über den bereits
gelieferten geteilten Helfer `warn_egress`. Reine Erweiterung des freigegebenen
2a-Musters, kein neues Design.

## Ist-Stand der Cache-Formen (Code)
| Dienst | Datei | Cache-Fetch-Fn | Cache-Form | TTL heute |
|---|---|---|---|---|
| Météo-France Vigilance | `vigilance.py:78` `_get_cached_cartevigilance` | **flach** `{"data","fetched_at","ttl"}` (ein National-Call) | **SONDERFALL** | 300/60s |
| GeoSphere Warn | `geosphere_warn.py:68` `_get_cached_warnings(lat,lon)` | `_cache={}` keyed by gerundete Koord, Entry `{"data","fetched_at","ttl"}` | wie MeteoAlarm | 300/60s |
| Météo-Forêts | `meteo_forets.py:70` `_get_cached_departement(dept)` | `_cache={}` keyed by Département | wie MeteoAlarm | 300/60s |
| Massif-Closure | `massif_closure.py:95` `_get_cached_daily_json(src)` | `_cache={}` keyed by Source-DEPT | wie MeteoAlarm | 300/60s |

- **3 Dienste (GeoSphere-Warn, Forêts, Massif):** strukturell identisch zu
  `meteoalarm._get_cached_index` (2a) → identische Migration auf
  `warn_egress.cached_fetch(cache=_cache, cache_key=<koord/dept/src>, ...)`.
- **Vigilance (Sonderfall):** flacher Ein-Eintrag-Cache statt keyed. Adapter:
  fester `cache_key="national"` in einem Dict-Wrapper — minimal, kein neuer
  Helfer nötig.
- Vorbild-Migration: `meteoalarm.py` (2a, live). Helfer: `warn_egress.cached_fetch`
  + `log_warn_service_call` (existiert, unverändert).

## Scope
- **DIESE Scheibe:** die 4 Dienste auf `warn_egress` migrieren — Erfolgs-TTL
  300→1800s, 429-Rückzug (Retry-After), Egress-Zähler (je Dienst korrekter
  `service`-Name + `host`). Failure-TTL 60s bleibt.
- **NICHT:** Test/Staging-Isolation (2b), Briefing-Hinweis (#811), async/Go.

## Risks & Considerations
- **Regressionsarm:** bestehende Tests der 4 Dienste müssen grün bleiben (außer
  weniger echten Abrufen). Charakterisierungs-Anker vor Umbau je Dienst bzw.
  gemeinsam.
- **Vigilance-Adapter** ist die einzige Nicht-Trivialität — der feste Key darf
  das „ein National-Call bedient alle Lookups"-Verhalten nicht brechen.
- Kein Live-Netz im Kern-Test: TTL/429/Zähler deterministisch (aufgezeichnete
  429-Response + Fake-Clock + Netz-Sentinel), wie in `test_warn_service_egress.py`.
- Zähl-Datei-Isolation greift bereits global (`conftest._isolate_warn_calls_path`
  aus 2a) — die neuen Zähler-Aufrufe der 4 Dienste sind dadurch automatisch
  test-isoliert.
- LoC-Limit 250: 4 kleine Migrationen; falls eng, Reihenfolge nach Nutzen
  (GeoSphere-Warn/Forêts/Massif trivial, Vigilance separat).
