---
entity_id: issue_1142_geosphere_direct_fallback
type: module
created: 2026-07-09
updated: 2026-07-09
status: draft
version: "1.0"
tags: [providers, geosphere, openmeteo, reliability, fallback, routing, briefing]
---

# Cross-Provider-Fallback — echter GeoSphere-Direktprovider für AT (#1142, Slice 1/4 von Epic #1127)

## Approval

- [ ] Approved

## Purpose

Der in #1141 verdrahtete Stub `at_direct` (wirft immer `ProviderNotImplementedError`) wird durch den **echten** GeoSphere-Provider ersetzt, damit der Cross-Provider-Fallback im Total-Ausfall-Fall für Koordinaten in Österreich tatsächlich Wetterdaten liefert statt weiterhin den Original-Fehler durchzureichen. Der neue `at_direct`-Adapter delegiert an die bestehende, produktiv genutzte `GeoSphereProvider`-Klasse, ruft sie aber bewusst **ohne** die versteckte Open-Meteo-Wolken-Abfrage auf (`include_cloud_layers=False`) — sonst würde der Fallback für einen Open-Meteo-Totalausfall ausgerechnet wieder Open-Meteo kontaktieren. Der Fallback-Seam in `openmeteo.py` fängt jetzt auch die Exceptions ab, die ein echter Provider werfen kann (`ProviderRequestError`, `ProviderNotFoundError`) — nicht mehr nur `ProviderNotImplementedError` (Adversary-Nebenbefund F001 aus #1141).

> **Empirischer Coverage-Befund (2026-07-09, echte GeoSphere-AROME-Grenzwert-Calls):** Die reale GeoSphere-Abdeckung **umschließt die AT-Region-Box aus #1141 (46,3–49,1 / 9,5–17,2) vollständig** — alle vier Ecken und Kantenmitten liefern HTTP 200 mit validen Daten, die Domain reicht weit darüber hinaus (Prag/Budapest/Venedig/Bern valide; echte `outside of dataset bounds`-400er erst bei Norddeutschland/Süditalien/Paris). **Konsequenz:** Es existiert KEINE Koordinate „innerhalb der Router-Box, aber außerhalb GeoSphere-Coverage". Die ursprünglich geplante Box-Schärfung und das darauf gestützte AC-2 sind damit gegenstandslos und wurden nach PO-Entscheidung (2026-07-09) aus diesem Slice entfernt. Die AT-Region-Box bleibt unverändert; `region_routing.py` wird NICHT angefasst.

## Source

- **File:** `src/providers/regional_stubs.py` (Python-Core / Domain-Backend) — `make_at_direct`-Factory wird durch eine GeoSphere-backed Factory ersetzt/ergänzt (Klasse `GeoSphereDirectAdapter` oder äquivalent)
- **File:** `src/providers/base.py:181-184` — Registry-Eintrag `register_provider("at_direct", ...)` wird auf die neue Factory umgehängt; Exception-Import bleibt (`ProviderNotImplementedError`, `ProviderRequestError`, `ProviderNotFoundError`)
- **File:** `src/providers/geosphere.py:172-211` — `GeoSphereProvider.fetch_forecast`/`fetch_combined` werden NICHT verändert (Wiederverwendung, kein Verhaltensbruch für `comparison_engine`/`radar_service`)
- **File:** `src/providers/region_routing.py` — **NICHT verändert** (AT-Box bleibt, empirisch als coverage-sicher bestätigt — s. Purpose)
- **File:** `src/providers/openmeteo.py:869-888` — Fallback-Seam: `except ProviderNotImplementedError` wird um `ProviderRequestError`/`ProviderNotFoundError` erweitert, sodass in allen drei Fällen `raise last_error` greift statt eines Crashs mit fremder Exception

> **Schicht-Hinweis:** Alle Änderungen liegen in Python-Core (`src/providers/`). Keine Go-API-Änderung, kein Frontend-Bezug.

## Estimated Scope

- **LoC:** ~45–70 Produktions-LoC (unter dem 250-LoC-Limit, kein Override nötig)
- **Files:** 2 Python geändert (`regional_stubs.py`, `openmeteo.py`) + `base.py` (Registry, ~5 LoC) + 1 Testdatei
- **Effort:** medium (dünner Adapter mit Exception-Übersetzung + Exception-Erweiterung am zentralen Seam)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `GeoSphereProvider.fetch_combined` (geosphere.py:406-465) | function | wird vom neuen `at_direct`-Adapter mit `include_cloud_layers=False` aufgerufen |
| `direct_provider_for` (region_routing.py:40-46) | function | Gate für `at_direct` — bleibt unverändert; empirisch bestätigt, dass die AT-Box vollständig innerhalb der GeoSphere-Coverage liegt |
| `ProviderRequestError`/`ProviderNotFoundError`/`ProviderNotImplementedError` (base.py:75-104) | class | müssen am Seam (openmeteo.py) alle drei so gefangen werden, dass `last_error` propagiert |
| `get_provider`/`register_provider` (base.py:111-172) | function | bestehende Registry, Umhängen des `at_direct`-Eintrags |
| `docs/specs/modules/issue_1141_cross_provider_routing.md` | spec | Vorgänger-Slice — Routing-Unterbau, Stub, Seam |
| `docs/specs/modules/api_retry.md` | spec | GeoSphere Retry-Verhalten (502/503/504, 5 Versuche) — bleibt unverändert (AC-4) |
| `comparison_engine`/`radar_service`/Trip-Services (nutzen `get_provider("geosphere")` direkt) | consumer | dürfen durch dieses Slice NICHT beeinflusst werden — Grund für den dünnen Adapter statt Verhaltensänderung an `GeoSphereProvider` |

## Implementation Details

**1. `src/providers/region_routing.py` — KEINE Änderung**

Empirisch (2026-07-09, echte GeoSphere-AROME-Grenzwert-Calls) bestätigt: die reale GeoSphere-Coverage umschließt die AT-Box (46.3–49.1 / 9.5–17.2) vollständig; es existiert keine Koordinate innerhalb der Box, die GeoSphere nicht abdeckt. Eine Box-Schärfung hätte kein Ziel und würde kein Verhalten ändern. Die Box bleibt unverändert. (Ursprüngliches AC-2 entfällt, PO-Entscheidung 2026-07-09.)

**2. `src/providers/regional_stubs.py` (MODIFY, ~30 LoC)**

Neue Adapter-Klasse (z. B. `GeoSphereDirectProvider`), Name bleibt `at_direct` (Registry-Key unverändert, damit #1141-Seam und -Tests unverändert funktionieren). `fetch_forecast` delegiert 1:1 an eine intern gehaltene `GeoSphereProvider`-Instanz:

```python
class GeoSphereDirectProvider:
    def __init__(self) -> None:
        self._inner = GeoSphereProvider()

    @property
    def name(self) -> str:
        return "at_direct"

    def fetch_forecast(self, location, start=None, end=None, enrich_ensemble=True):
        return self._inner.fetch_combined(
            lat=location.latitude, lon=location.longitude,
            start=start, end=end, include_cloud_layers=False,
        )
```

`fetch_combined` wirft bereits `ProviderRequestError` bei HTTP-Fehlern (via `fetch_nwp_forecast` → `_request` → `httpx.HTTPStatusError`/`RequestError`, dort in `fetch_forecast` von `GeoSphereProvider` gefangen — **Achtung:** `fetch_combined` selbst fängt diese NICHT, nur `GeoSphereProvider.fetch_forecast` tut das; der Adapter muss die gleiche try/except-Übersetzung übernehmen, sonst propagiert eine rohe `httpx`-Exception statt `ProviderRequestError`). `de_direct`/`fr_direct` bleiben unverändert der bisherige `RegionalStubProvider`-Stub (Out of Scope, #1143/#1144).

**3. `src/providers/base.py` (MODIFY, ~5 LoC)**

Registrierung in `_load_providers()` (Zeile 181-184) auf die neue Factory umhängen: `register_provider("at_direct", GeoSphereDirectProvider)` statt `make_at_direct`. `de_direct`/`fr_direct` bleiben bei den Stub-Factories.

**4. `src/providers/openmeteo.py` (MODIFY, ~15 LoC, Zeile 884)**

Der bestehende `except ProviderNotImplementedError: pass` wird erweitert, damit auch ein echter Provider-Fehler sauber zu `raise last_error` führt statt mit einer fremden Exception zu crashen (F001):

```python
except (ProviderNotImplementedError, ProviderRequestError, ProviderNotFoundError):
    pass  # Stub noch nicht angebunden ODER Direktprovider selbst
          # fehlgeschlagen -> Original-Fehler durchreichen (AC-5)
```

`ProviderRequestError`/`ProviderNotFoundError` werden zusätzlich zum bereits importierten `ProviderNotImplementedError` lokal importiert (gleiche Stelle, Zeile 874).

## Expected Behavior

- **Input:** Briefing-/Vergleichs-Wetterabruf via `fetch_forecast`; Open-Meteo hat bereits alle abdeckenden Modelle inkl. globalem ECMWF mit 5xx/Timeout ausgeschöpft (Total-Ausfall, #1141-Pfad); Koordinate liegt in Österreich.
- **Output:** Bei Koordinate innerhalb der AT-Router-Box (per #1141, alle innerhalb GeoSphere-Coverage): `NormalizedTimeseries` von GeoSphere (ohne Wolken-Enrichment) mit `meta.fallback_reason="cross_provider_total_outage"` und `meta.fallback_model="at_direct"`. Bei Koordinate außerhalb aller Router-Boxen: Router liefert `None`, ursprüngliche `ProviderRequestError` wird geworfen (unverändert zu #1141). Bei GeoSphere-eigenem Ausfall (5xx/Timeout nach Retry): ursprüngliche `ProviderRequestError` des zuletzt gescheiterten Open-Meteo-Modells wird geworfen, kein Crash mit GeoSphere-eigener Exception.
- **Side effects:** Kein zusätzlicher `api.open-meteo.com`-Call im Fallback-Pfad (Kernziel von `include_cloud_layers=False`). `GeoSphereProvider`-Verhalten für `comparison_engine`/`radar_service`/Trip-Services bleibt vollständig unverändert (separate Instanz im Adapter, keine geteilte Mutation).

## Acceptance Criteria

- **AC-1:** Given eine Koordinate innerhalb der AT-Router-Box (per #1141, alle innerhalb GeoSphere-Coverage), When der Cross-Provider-Fallback greift, Then liefert `fetch_forecast` ein valides `NormalizedTimeseries` mit befüllten `t2m_c`, `wind10m_kmh`, `precip_1h_mm`.
  - Test: Echter GeoSphere-API-Call für eine bekannte AT-Koordinate (z. B. Innsbruck) über den registrierten `at_direct`-Provider; Assertion auf nicht-leere `NormalizedTimeseries.data` mit gesetzten Feldern `t2m_c`/`wind10m_kmh`/`precip_1h_mm` für mindestens einen Datenpunkt.
  - **Hinweis:** `symbol` wurde aus AC-1 gestrichen (PO-Entscheidung 2026-07-09) — `ForecastDataPoint.symbol` ist `Optional[str] = None` und wird von KEINEM Provider befüllt (auch `openmeteo.py:719` setzt es auf `None`); der Nachweis brauchbarer Vorhersagedaten erfolgt über Temperatur/Wind/Niederschlag.

- **AC-2:** Given der Cross-Provider-Fallback-Modus ist aktiv (Open-Meteo-Totalausfall simuliert), When der GeoSphere-Abruf über `at_direct` läuft, Then erfolgt KEIN Call gegen `api.open-meteo.com` (`_fetch_openmeteo_clouds` wird nicht erreicht).
  - Test: Echter lokaler `ThreadingHTTPServer` (Vorbild `test_issue_1141_cross_provider_fallback.py`) simuliert den Open-Meteo-Totalausfall für alle Modell-Endpoints; parallel wird `api.open-meteo.com`-Zugriff über einen Netzwerk-Interception-Punkt nachweisbar gemacht (z. B. `providers.call_log.log_api_call`-Aufrufe zählen: vor dem Fallback-Call Zähler lesen, danach erneut lesen, Assertion `count_after == count_before` für den `geosphere_clouds`-Source-Tag). Kein Mock der GeoSphere-API selbst — nur Nachweis, dass der Wolken-Zweig nicht betreten wird.

- **AC-3:** Given GeoSphere selbst antwortet mit 5xx/Timeout (nach Ausschöpfung des bestehenden Retry-Verhaltens aus `api_retry.md`), When das Segment verarbeitet wird, Then bleibt das Fehler-Markierungs-Verhalten unverändert (Segment `has_error`, ursprüngliche `ProviderRequestError` wird sichtbar) und das Retry-Verhalten (5 Versuche, exponentielles Backoff 2-60s auf 502/503/504/Connection-Errors) wird nicht verändert.
  - Test: Echter lokaler `ThreadingHTTPServer` liefert für den GeoSphere-`at_direct`-Aufruf durchgehend 503 (alle Retry-Versuche ausgeschöpft, kein Mock); `monkeypatch.setattr` auf `providers.geosphere.BASE_URL` (analog zum Open-Meteo-Test-Vorbild), NICHT auf die Exception selbst. Assertion: `fetch_forecast` wirft am Ende die ursprüngliche `ProviderRequestError` des zuletzt gescheiterten Open-Meteo-Modells (nicht die GeoSphere-eigene), Segment bleibt `has_error`.

- **AC-4 (F001-Fix):** Given ein Direktanbieter (GeoSphere) antwortet am Seam mit 5xx/Timeout, When das Segment verarbeitet wird, Then wird die daraus resultierende `ProviderRequestError` im `except`-Block des Seams (openmeteo.py:884) gefangen und `raise last_error` greift — kein Crash mit einer unbehandelten `ProviderRequestError`/`ProviderNotFoundError` aus dem GeoSphere-Aufruf selbst.
  - Test: Gleicher Aufbau wie AC-3, zusätzlich ein zweiter Testfall mit absichtlich falsch registriertem/entferntem `at_direct`-Eintrag (`ProviderNotFoundError` via `get_provider`), der beweist, dass auch dieser Fehlerpfad ohne Crash zu `last_error` führt. Beide Testfälle prüfen explizit, dass KEINE `ProviderRequestError`/`ProviderNotFoundError` aus dem GeoSphere-Zweig den Aufrufer erreicht, sondern ausschließlich die ursprüngliche Open-Meteo-`last_error`.

## Test-Strategie (keine Mocks)

Vorbild: `tests/tdd/test_issue_1141_cross_provider_fallback.py`. Neue Datei: `tests/tdd/test_issue_1142_geosphere_direct_fallback.py`.

- **Echte GeoSphere-API-Calls** für AC-1 (Erfolgsfall) und AC-2 (kein Open-Meteo-Nebencall) — kein Mock der GeoSphere-Antwort.
- **Echter lokaler `ThreadingHTTPServer`** für AC-3/AC-4 (5xx/Timeout-Szenario am Seam), `monkeypatch.setattr("providers.geosphere.BASE_URL", <lokale URL>)` bzw. äquivalenter Patch-Punkt für den GeoSphere-Client — kein `Mock()`/`patch()` auf Python-Objektebene, sondern ein echter (fehlschlagender) HTTP-Server.
- Für den Open-Meteo-Totalausfall (Voraussetzung aller ACs) wird der bestehende `ThreadingHTTPServer`-Aufbau aus `test_issue_1141_cross_provider_fallback.py` wiederverwendet (alle Modell-Endpoints liefern 503).
- `AVAILABILITY_CACHE_PATH`/`DIAGNOSTICS_PATH` auf temporäre Pfade umgebogen (wie im #1141-Test), damit kein Produktionszustand berührt wird.
- AC-Test-Mapping (Pflicht, 1:1 in Testdatei als Docstring/Kommentar je Testfunktion):

| AC | Testfunktion (geplant) |
|----|------------------------|
| AC-1 | `test_at_direct_returns_valid_geosphere_timeseries` |
| AC-2 | `test_at_direct_skips_openmeteo_cloud_call` |
| AC-3 | `test_geosphere_5xx_preserves_original_error_and_retry` |
| AC-4 | `test_seam_catches_provider_request_and_not_found_error` |

## Known Limitations

- Nur `at_direct` wird in diesem Slice an einen echten Provider angebunden — `de_direct`/`fr_direct` bleiben unveränderte Stubs (`ProviderNotImplementedError`) bis #1144/#1143.
- **Keine explizite Coverage-Prüfung im Adapter:** Empirisch (2026-07-09) liegt die AT-Router-Box vollständig innerhalb der GeoSphere-AROME-Domain, daher kann `at_direct` keine unabgedeckte Koordinate erreichen. Ein GeoSphere-`outside of dataset bounds` (HTTP 400) ist für AT-Box-Koordinaten strukturell ausgeschlossen; sollte GeoSphere seine Domain künftig verkleinern, würde ein solcher Fehler über den Retry-/Seam-Pfad (AC-3/AC-4) als `ProviderRequestError` sichtbar und sauber behandelt — kein Crash, aber auch kein präventives Skippen.
- Der `enrich_ensemble`-Parameter wird von GeoSphere (wie bisher, Bug #288-Kommentar in `geosphere.py:189-190`) weiterhin ignoriert — kein Bug, keine Ensemble-API bei GeoSphere vorhanden, nicht Teil dieses Slices.
- Kein neues Alarmsignal für „GeoSphere-Direktfallback wurde benutzt" — Sichtbarkeit läuft weiterhin über `meta.fallback_reason`/`fallback_model` (#1141) und `provider_error_streak` (Go, unverändert).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine additive Erweiterung des in #1141 etablierten Registry-/Fallback-Musters — ein Stub wird durch einen dünnen Adapter auf einen bereits produktiv genutzten Provider ersetzt, keine neue Cross-Cutting-Entscheidung, kein neuer Layer. Die Design-Entscheidung „dünner Adapter statt Verhaltensänderung an `GeoSphereProvider`" ist lokal (ein Modul) und folgt einem bestehenden Muster (`RegionalStubProvider`), rechtfertigt daher kein eigenes ADR.

## Out of Scope (Folge-Issues)

- **#1143** — echter Météo-France-Direktprovider für Frankreich (`fr_direct`).
- **#1144** — echter DWD-Direktprovider für Deutschland (`de_direct`).
- Das im Epic-#1127-Body fälschlich zitierte „#288 / enrich_ensemble" ist KEIN Bug und NICHT Teil dieses Slices — siehe Known Limitations.

## Changelog

- 2026-07-09: Initial spec created
- 2026-07-09: AC-2 (Coverage-Box-Schärfung) entfernt nach empirischem Befund (GeoSphere-Coverage ⊇ AT-Router-Box) + PO-Entscheidung; ACs neu nummeriert (5→4); `region_routing.py` aus Scope entfernt.
- 2026-07-09: `symbol` aus AC-1 gestrichen (PO-Entscheidung) — Feld wird von keinem Provider befüllt; AC-1 prüft `t2m_c`/`wind10m_kmh`/`precip_1h_mm`.
