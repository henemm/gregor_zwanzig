---
entity_id: fix_1994_openmeteo_units
type: module
created: 2026-10-08
updated: 2026-10-08
status: draft
version: "1.0"
tags: [openmeteo, provider, einheiten, audit-b-04, bugfix]
workflow: fix-1994-openmeteo-units
---

# Fix #1994 - Explizite Einheiten-Parameter an allen Open-Meteo-Requests

## Approval

- [ ] Approved

## Purpose

Alle produktiven Open-Meteo-Anfragen sollen `wind_speed_unit=kmh`, `temperature_unit=celsius` und `precipitation_unit=mm` explizit mitsenden, statt sich auf die API-Defaults zu verlassen. Die Normalisierung (Python-Provider wie Go-Provider) nimmt km/h, Grad Celsius und mm an; aendert Open-Meteo einen Default oder liefert ein Proxy/Modell-Endpunkt andere Einheiten, wuerden Wind-, Temperatur- und Niederschlagswerte in Reports still falsch (Audit B-04).

## Source

- **File:** `src/providers/openmeteo.py`
- **Identifier:** `_koordinaten_params` (zentraler Params-Erbauer), `probe_model_availability`, `_fetch_uv_data`; Go: `internal/provider/openmeteo/provider.go` (URL-Bau der Forecast- und Air-Quality-Anfrage)

> **Schicht-Hinweis:** Python-Core (`src/providers/`, `src/services/`) und Go-API (`internal/provider/openmeteo/`). Kein Frontend.

### Vollstaendige Liste der Open-Meteo-Request-Stellen (Stand 2026-10-08, selbst geprueft)

Produktiv, Python:

| # | Datei:Zeile | Host / Pfad | Params-Bau heute | Behandlung |
|---|-------------|-------------|------------------|-----------|
| 1 | `src/providers/openmeteo.py:1051` (`fetch_forecast`), Abruf via `_request` :1115 | api.open-meteo.com, Modell-Endpunkt | `_punkt_params(...)` -> `_koordinaten_params` (:186) | Einheiten im Erbauer |
| 2 | `src/providers/openmeteo.py:1256` (Fallback-Modell `fb_params`), Abruf :1265 | api.open-meteo.com, Fallback-Endpunkt | `_punkt_params(...)` | Einheiten im Erbauer |
| 3 | `src/providers/openmeteo.py:766` (`_fetch_ensemble_spread`), Abruf :778 | ensemble-api.open-meteo.com `/v1/ensemble` | `_punkt_params(...)` | Einheiten im Erbauer |
| 4 | `src/providers/openmeteo.py:380` (`probe_model_availability`), Abruf :390 | api.open-meteo.com, Modell-Endpunkte | eigenes Dict-Literal (BEWUSSTE_AUSNAHME im Hoehen-Guard) | Einheiten explizit ergaenzen |
| 5 | `src/providers/openmeteo.py:879` (`_fetch_uv_data`), Abruf :889 | air-quality-api.open-meteo.com `/v1/air-quality` | eigenes Dict-Literal (BEWUSSTE_AUSNAHME) | Einheiten explizit ergaenzen (nur `uv_index` angefragt; Parameter sind unschaedlich, AC des Issues sagt "alle") |
| 6 | `src/providers/geosphere.py:580` (Wolken-Abruf, `get` :598) | api.open-meteo.com `/v1/forecast` | `_koordinaten_params(...)` (:587) | Einheiten im Erbauer |
| 7 | `src/services/radar_service.py:1017` (Nowcast, `get` :1020) | api.open-meteo.com `/v1/forecast` (`minutely_15`) | `_koordinaten_params(...)` (:1011) | Einheiten im Erbauer |

Gemeinsamer Senke: `OpenMeteoProvider._request` (:633, `get` :682) fuer 1, 2, 4, 5; direkter `self._client.get` fuer 3 (:778) und 6 (:598); `httpx.Client.get` fuer 7 (:1020).

Produktiv, Go (`internal/provider/openmeteo/provider.go`):

| # | Datei:Zeile | Host / Pfad | Params-Bau heute |
|---|-------------|-------------|------------------|
| 8 | `provider.go:112-119` (Forecast-URL, `BaseURL` + `m.Endpoint`) | api.open-meteo.com (`internal/config/config.go:32`) | `url.Values`: latitude, longitude, hourly, timezone, start_date, end_date |
| 9 | `provider.go:290-298` (UV, `AQURL` + `/v1/air-quality`) | air-quality-api.open-meteo.com (`internal/config/config.go:33`) | `url.Values` analog |

Nicht produktiv (Dev-/Analyse-Werkzeuge, siehe Offene Fragen): `tools/weather_validation.py:35` (`httpx.get` mit `params`, :27-34), `scripts/eichung_cape_schwelle.py:63` (`HISTORICAL_API`, historical-forecast-api.open-meteo.com). Reine Host-Allowlists/Konfiguration ohne Request: `src/app/egress_guard.py:33-34`, `internal/egress/inventory.go:23-24`, `internal/config/config.go:32-33`.

## Estimated Scope

- **LoC:** ~+60 (Python ~15, Go ~10, Tests ~35 netto im Produktivpfad-Anteil gerechnet; Tests zaehlen voll)
- **Files:** 4-5 (3 Produktiv, 2 Test)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `providers.openmeteo._koordinaten_params` | function | Einziger Params-Erbauer fuer Punkt-Requests (Issue #1991); Traeger der Einheiten |
| `tests/test_openmeteo_callsite_elevation_guard.py` | test | AST-Waechter ueber latitude-Dict-Literale; darf durch die Aenderung nicht rot werden |
| `httpx.MockTransport` | library | Echter `httpx.Request` wird abgesetzt, Test liest die kodierte Query (Vorbild `tests/tdd/test_wegpunkt_hoehe_im_request.py`) |
| `net/http/httptest` | library (Go) | Lokaler Fake-Server fuer den Go-Provider |
| `docs/reference/decision_matrix.md` | doc | Provider-Ist-Stand, ggf. Einheiten-Hinweis ergaenzen |

## Implementation Details

1. Neue Modulkonstante in `src/providers/openmeteo.py` (z. B. `OPENMETEO_EINHEITEN`) mit den drei Schluesseln `wind_speed_unit="kmh"`, `temperature_unit="celsius"`, `precipitation_unit="mm"`.
2. `_koordinaten_params` legt die Konstante in das zurueckgegebene Dict. Damit erben `fetch_forecast`, Fallback-Request, Ensemble-Request, Wolken-Abruf (`geosphere.py`) und Nowcast (`radar_service.py`) die Einheiten, ohne dass dort Code angefasst wird (Trip/Ortsvergleich nutzen denselben Pfad).
3. Die zwei Dict-Literal-Ausnahmen (`probe_model_availability`, `_fetch_uv_data`) erhalten die Konstante explizit (`params.update(OPENMETEO_EINHEITEN)` bzw. `**OPENMETEO_EINHEITEN` im Literal).
4. Go: im Provider eine Konstante/Helferfunktion, die `wind_speed_unit`, `temperature_unit`, `precipitation_unit` in beide `url.Values` setzt (:112 und :290).
5. Reihenfolge der Query ist irrelevant. Der Cache-Key (falls aus Params abgeleitet) muss geprueft werden: gleicher Request-Inhalt, nur zusaetzliche Keys -> einmaliger Cache-Miss ist akzeptiert.
6. Keine Umrechnung im Parser: die Werte bleiben km/h/Celsius/mm, es wird nur der heutige Default festgeschrieben (Verhalten unveraendert).

### Teststrategie (ohne Mock-Theater)

Passender Ansatz zum Bestand: Die vorhandenen Tests `tests/tdd/test_wegpunkt_hoehe_im_request.py` und `tests/tdd/test_ortsvergleich_hoehe_und_cache.py` ersetzen `provider._client` durch `httpx.Client(transport=httpx.MockTransport(handler))`. Der Prueffling (`OpenMeteoProvider`) setzt dabei einen ECHTEN `httpx.Request` ab, der Test liest dessen fertig kodierte Query per `parse_qs(request.url.query.decode(), keep_blank_values=True)`. Das ist ein Anfrage-Pfad-Wachter am Wirkort, kein Spiegeln einer Annahme; kein `patch()`/`MagicMock` fuer Logik. Dasselbe Vorbild (`_prepare_provider`, `_handler`) wird in der neuen Datei nachgebaut (Availability-Cache vorbefuellen, Retry neutralisieren via `monkeypatch.setattr` auf Modulkonstanten/tenacity wie im Vorbild).

- Python: `tests/tdd/test_openmeteo_explizite_einheiten.py` (Verhalten, nicht Issue-Nummer). Prueft alle Hosts: Haupt, Fallback, Ensemble, Probe, UV ueber den Provider; Wolken-Abruf ueber `GeoSphereProvider` mit MockTransport-Client; Nowcast in `radar_service` ueber den produktiven Request-Bau (Transport-Ersatz wie im Bestandstest `tests/unit/test_call_source_ueber_threadgrenze.py` bzw. Bestandsmuster pruefen; falls dort `httpx.Client` inline erzeugt wird, die Einheiten stattdessen ueber `_koordinaten_params` plus Anfangs-URL des Nowcast-Pfades pruefen).
- Go: Test in `internal/provider/openmeteo/provider_test.go` (oder neue Datei `units_test.go`) mit `httptest.NewServer`, `Config.BaseURL`/`AQURL` auf den Fake-Server; der Handler liest `r.URL.Query()`.
- Mutations-Gegenprobe (Adversary): jede der drei Einheiten einzeln aus Konstante entfernen bzw. auf `mph`/`fahrenheit`/`inch` aendern, sowie Einheiten aus `probe_model_availability` und `_fetch_uv_data` entfernen -> je ein Test muss rot werden. Zusaetzlich: Mutation, bei der nur `_request` (nicht der Ensemble-Pfad) Einheiten setzt, muss den Ensemble-Test faellen.
- Zusaetzlich ein Wachter gegen neue Open-Meteo-Request-Stellen ohne Einheiten: der bestehende AST-Waechter `tests/test_openmeteo_callsite_elevation_guard.py` erzwingt bereits, dass neue latitude-Dicts ueber `_koordinaten_params` laufen; die Einheiten kommen damit automatisch mit.

## Expected Behavior

- **Input:** Beliebiger Open-Meteo-Abruf (Forecast, Fallback, Ensemble, Probe, Air-Quality, Wolken, Nowcast; Python und Go).
- **Output:** Die abgesetzte Query enthaelt genau je einmal `wind_speed_unit=kmh`, `temperature_unit=celsius`, `precipitation_unit=mm`. Parsing und Report-Werte bleiben unveraendert.
- **Side effects:** Query wird um drei Parameter laenger; einmaliger Cache-Miss bei Query-abhaengigen Cache-Keys.

## Acceptance Criteria

- **AC-1:** Given ein Wegpunkt und ein OpenMeteoProvider mit Test-Transport / When `fetch_forecast` die Hauptvorhersage abruft / Then traegt die abgesetzte Anfrage an api.open-meteo.com die Parameter `wind_speed_unit=kmh`, `temperature_unit=celsius` und `precipitation_unit=mm` jeweils genau einmal.
  - Test: `test_hauptvorhersage_traegt_alle_drei_einheiten` liest die kodierte Query des vom Provider abgesetzten httpx.Request (Anfrage-Pfad).

- **AC-2:** Given ein Modell mit fehlenden Parametern, das den Fallback-Modell-Request ausloest / When der Fallback-Abruf an den Fallback-Endpunkt gesendet wird / Then enthaelt auch diese Anfrage `wind_speed_unit=kmh`, `temperature_unit=celsius` und `precipitation_unit=mm`.
  - Test: `test_fallback_modell_anfrage_traegt_einheiten` erzwingt den Fallback ueber einen Availability-Cache mit "unavailable"-Eintrag und prueft die zweite Anfrage.

- **AC-3:** Given der Ensemble-Spread-Abruf fuer einen Wegpunkt / When die Anfrage an ensemble-api.open-meteo.com `/v1/ensemble` gesendet wird / Then enthaelt sie `wind_speed_unit=kmh`, `temperature_unit=celsius` und `precipitation_unit=mm`.
  - Test: `test_ensemble_anfrage_traegt_einheiten` filtert die beobachteten Requests nach Host `ensemble-api.open-meteo.com`.

- **AC-4:** Given die Modell-Verfuegbarkeits-Probe und der UV-Abruf (Air-Quality-API) / When beide ihre Anfragen absetzen / Then tragen auch diese beiden Anfragen die drei Einheiten-Parameter mit den Werten `kmh`, `celsius` und `mm`.
  - Test: `test_probe_und_uv_anfrage_tragen_einheiten` prueft die Hosts api.open-meteo.com (Probe) und air-quality-api.open-meteo.com (UV).

- **AC-5:** Given der Wolken-Abruf ueber GeoSphereProvider und der Radar-Nowcast-Abruf / When beide Open-Meteo `/v1/forecast` ansprechen / Then enthaelt jede der beiden abgesetzten Anfragen die Parameter `wind_speed_unit=kmh`, `temperature_unit=celsius` und `precipitation_unit=mm`.
  - Test: `test_wolken_und_nowcast_anfrage_tragen_einheiten` beobachtet die Requests beider Aufrufer am Transport.

- **AC-6:** Given der Go-Provider mit lokalem Fake-HTTP-Server als BaseURL und AQURL / When Forecast und UV abgerufen werden / Then enthaelt die am Server ankommende Query beider Anfragen `wind_speed_unit=kmh`, `temperature_unit=celsius` und `precipitation_unit=mm`.
  - Test: Go-Test mit `httptest.NewServer`, der `r.URL.Query()` je Pfad auswertet (Anfrage-Pfad, nicht Lesepfad).

- **AC-7:** Given ein Wegpunkt mit gesetzter Hoehe / When die Hauptanfrage gebaut wird / Then bleiben `elevation`, `latitude`, `longitude` und der Fall "ohne Hoehe ohne leeren elevation-Parameter" unveraendert zusaetzlich zu den Einheiten erhalten.
  - Test: bestehende Tests `tests/tdd/test_wegpunkt_hoehe_im_request.py` und `tests/test_openmeteo_callsite_elevation_guard.py` bleiben gruen.

## Known Limitations

- Die Air-Quality-API fragt nur `uv_index` ab; die Einheiten-Parameter dort sind funktional wirkungslos, werden aber der Einheitlichkeit wegen gesendet (AC des Issues: "alle Requests"). Falls die API unbekannte Parameter ablehnen sollte, faellt das bei der Staging-Verifikation auf (siehe Offene Fragen).
- Dev-Werkzeuge (`tools/weather_validation.py`, `scripts/eichung_cape_schwelle.py`) sind nicht Teil des Produktivpfads und bleiben ausser Scope, sofern der PO nichts anderes entscheidet.
- Es wird nichts umgerechnet: die Aenderung schreibt den heutigen Default fest.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Festschreiben des bisherigen Default-Verhaltens in einer bestehenden Provider-Schicht; keine Aenderung von Kanaelen, Provider-Wahl, Datenmodell oder Persistenz. Kein Schema-Edit, kein Eingriff in Bestandsdaten.

## Changelog

- 2026-10-08: Initial spec created (Issue #1994, Audit B-04)
