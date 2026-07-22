---
entity_id: warn_service_consumption_rest
type: module
created: 2026-07-22
updated: 2026-07-22
status: draft
version: "1.0"
tags: [egress, warn-services, cache, backoff, "1348", "1337"]
workflow: feat-1348-warn-rest
---

<!-- Issue #1348 AC-11 — die 4 übrigen Warn-Dienste auf warn_egress -->

# Warn-Dienst-Verbrauch — Rest (Vigilance, GeoSphere-Warn, Météo-Forêts, Massif)

## Approval
- [ ] Approved

## Purpose
Dieselbe Verbrauchs-Behandlung wie MeteoAlarm (Scheibe 2a, live) für die vier
übrigen amtlichen Warn-Dienste: 30-Min-Erfolgs-Cache + 429-bewusster Rückzug +
Egress-Zähler, über den bereits gelieferten geteilten Helfer `warn_egress`. Reine
Erweiterung des freigegebenen 2a-Musters — kein neues Design, kein neuer Helfer.

## Source
- **Files:** `src/services/official_alerts/{vigilance,geosphere_warn,meteo_forets,massif_closure}.py`
- **Helfer (unverändert):** `warn_egress.cached_fetch`, `warn_egress.log_warn_service_call`
- **Vorbild:** `meteoalarm.py` (2a, live)

## Scope
### Affected Files
| File | Change | Description |
|------|--------|-------------|
| `geosphere_warn.py` | MODIFY | `_get_cached_warnings` auf `cached_fetch` (keyed by gerundete Koord), service="geosphere_warn" |
| `meteo_forets.py` | MODIFY | `_get_cached_departement` auf `cached_fetch` (keyed by Département), service="meteo_forets" |
| `massif_closure.py` | MODIFY | `_get_cached_daily_json` auf `cached_fetch` (keyed by Source-DEPT), service="massif_closure" |
| `vigilance.py` | MODIFY | `_get_cached_cartevigilance` auf `cached_fetch` mit festem `cache_key="national"` (Adapter für flachen Cache), service="vigilance" |
| `tests/tdd/test_warn_services_rest.py` | CREATE | TTL/429/Zähler/Regression je Dienst (parametrisiert wo möglich) |

### Estimated Changes
- Files: 4 MODIFY, 1 test CREATE
- LoC: ~180–230 (unter 250; generierte/Doku zählen nicht). Falls eng: Vigilance
  zuletzt (Sonderfall), Rest zuerst — begründet.

## Test Plan
Kern-Schicht deterministisch, kein Live-Netz (wie `test_warn_service_egress.py`):
aufgezeichnete/konstruierte 429-Response, Fake-Clock (injizierbare `clock`),
Netz-Sentinel für „kein echter Call bei Cache-Hit". Zähl-Datei-Isolation greift
bereits global (`conftest._isolate_warn_calls_path` aus 2a).

**TDD-Vorstufe:** Vor jeder Änderung ein Charakterisierungs-Test, der das heutige
Verhalten je Dienst festnagelt (Anker gegen Regression), danach ersetzt/entfernt.

## Acceptance Criteria

- **AC-1:** Given jeder der vier Dienste (vigilance, geosphere_warn, meteo_forets, massif_closure) / When das Modul importiert wird / Then ist der Erfolgs-Cache-TTL 1800.0s (über `warn_egress.WARN_SUCCESS_TTL`), Failure-TTL bleibt 60.0s
  - Test: `test_warn_services_rest.py::test_ttl_ist_dreissig_minuten[<service>]`
- **AC-2:** Given ein erfolgreicher Cache-Eintrag jünger als 1800s bei einem der vier Dienste / When die Cache-Fetch-Funktion erneut mit demselben Schlüssel aufgerufen wird / Then wird kein echter HTTP-Call ausgelöst (Netz-Sentinel-Beweis), die gecachten Daten kommen zurück
  - Test: `test_warn_services_rest.py::test_cache_hit_kein_call[<service>]`
- **AC-3:** Given eine HTTP-429-Antwort (mit und ohne `Retry-After`) bei einem der vier Dienste / When die Cache-Fetch-Funktion sie verarbeitet / Then wird das Backoff-Fenster auf `max(retry_after, 1800)` bzw. 1800s gesetzt (kein 15-Min-Dauerfeuer) und laut geloggt (Text enthält „429" + Backoff-Dauer)
  - Test: `test_warn_services_rest.py::test_429_backoff_laut[<service>]`
- **AC-4:** Given ein echter Call bzw. Cache-Hit bei einem der vier Dienste / When er über `cached_fetch` läuft / Then schreibt `warn_service_calls.jsonl` eine Zeile mit korrektem `service`-Namen (vigilance|geosphere_warn|meteo_forets|massif_closure), Host, `status`, `cache_hit`, `retry_after`
  - Test: `test_warn_services_rest.py::test_zaehler_service_name[<service>]`
- **AC-5:** Given Vigilance (flacher National-Cache, ein Call bedient alle Orts-Lookups) / When zwei Lookups für verschiedene Koordinaten im TTL-Fenster erfolgen / Then löst nur der erste einen echten Call aus, der zweite ist ein Cache-Hit (fester `cache_key` bewahrt das National-Call-Verhalten)
  - Test: `test_warn_services_rest.py::test_vigilance_ein_national_call_fuer_alle`
- **AC-6:** Given die bestehenden Tests der vier Dienste / When die Migration angewandt ist / Then bleiben sie unverändert grün (Regressionsschutz) — kein neuer Failure gegenüber Baseline
  - Test: bestehende `test_vigilance*.py`/`test_geosphere_warn*.py`/`test_meteo_forets*.py`/`test_massif*.py` grün

## Known Limitations
- Test/Staging-Isolation der Warn-APIs (Inventar BLOCKED + Attrappen) = Scheibe 2b, NICHT hier.
- Briefing-sichtbarer „Warnungen nicht abrufbar"-Hinweis (Renderer/#811) = eigene Scheibe.
- `Retry-After` nur numerische Sekunden (HTTP-Date = „kein Header") — vom Helfer geerbt (2a).

## Regel-Budget
Keine neue Regel/Gate — reine Anwendung des bestehenden 2a-Musters. Kein Prüfdatum nötig.

## Changelog
- 2026-07-22: Initial spec — Issue #1348 AC-11 (die 4 übrigen Warn-Dienste)
