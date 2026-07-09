---
entity_id: issue_1141_cross_provider_routing
type: module
created: 2026-07-08
updated: 2026-07-08
status: draft
version: "1.0"
tags: [providers, openmeteo, reliability, fallback, routing, briefing]
---

# Cross-Provider-Fallback — Routing-Unterbau + Total-Ausfall-Erkennung (#1141, Slice 0/4 von Epic #1127)

## Approval

- [x] Approved (PO, 2026-07-08)

## Purpose

Wenn Open-Meteo als Verteiler **komplett** ausfällt (alle abdeckenden Modelle inkl. globalem ECMWF mit 5xx/Timeout erschöpft — der intra-Open-Meteo-Fallback aus #1115 also selbst gescheitert ist), soll Gregor auf einen infrastruktur-unabhängigen Direkt-Provider der betroffenen Region ausweichen können, statt das Segment sofort als Ausfall zu markieren. Dieses Slice liefert den **Unterbau**: eine Region→Provider-Weiche, einen einzigen zentralen Einhängepunkt im bestehenden Fetch-Pfad, eine sichtbare Nicht-Kaschieren-Markierung sowie einen Stub-Direktprovider je Region (AT/DE/FR). **Kein echter neuer Wetter-Provider** in diesem Slice — die tatsächliche Anbindung (GeoSphere AT, DWD DE, Météo-France FR) folgt in den Folge-Slices #1142/#1143/#1144.

## Source

- **File:** `src/providers/openmeteo.py` (Python-Core / Domain-Backend) — Einhängepunkt in `OpenMeteoProvider.fetch_forecast`, Zeile 864 (`if response_data is None: raise last_error`)
- **File:** `src/providers/region_routing.py` (NEU) — `direct_provider_for(lat, lon) -> Optional[str]`
- **File:** `src/providers/regional_stubs.py` (NEU) — parametrisierter Stub-Provider je Region
- **File:** `src/providers/base.py` — `ProviderNotImplementedError`, Registrierung `at_direct`/`de_direct`/`fr_direct`
- **File:** `src/output/renderers/email/plain.py` — Footer-Fix leere `fallback_metrics` (Zeile 286-288)
- **File:** `src/app/models.py` — `ForecastMeta` (kein Schema-Change, nur neuer String-Wert `fallback_reason="cross_provider_total_outage"`)

> **Schicht-Hinweis:** Alle Änderungen liegen in Python-Core (`src/providers/`, `src/output/renderers/`, `src/app/models.py`). Keine Go-API-Änderung (siehe „AC-6 ohne Go-Code" unten), kein Frontend-Bezug.

## Estimated Scope

- **LoC:** ~95–135 Produktions-LoC (unter dem 250-LoC-Limit, kein Override nötig)
- **Files:** 3 Python neu/geändert produktiv (`region_routing.py`, `regional_stubs.py`, `openmeteo.py`, `base.py`, `plain.py` = 5 Dateien) + 1 Testdatei
- **Effort:** medium (Eingriff im zentralen Fetch-Pfad, aber additiv nur im Total-Ausfall-Zweig)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `OpenMeteoProvider.fetch_forecast` (openmeteo.py:864) | function | einziger Einhängepunkt für das Cross-Provider-Routing, NACH dem bestehenden #1115-Modell-Fallback |
| `ProviderRequestError` (base.py:82) | class | wird bei Region-Ausfall/Stub-Ausfall unverändert weitergereicht (`last_error`) |
| `ProviderError` (base.py:67) | class | Basisklasse für neue `ProviderNotImplementedError` |
| `get_provider`/`_load_providers`/`register_provider` (base.py:97-172) | function | bestehende Registry, Heimat für Stub-Registrierung |
| `ForecastMeta.fallback_model`/`fallback_reason`/`fallback_metrics` (models.py) | field | existiert bereits (#1115), wird mit neuem `fallback_reason`-Wert wiederverwendet |
| `_log_api_call` → `openmeteo_calls.jsonl` (openmeteo.py:501) | log | persistiert 5xx-Calls bereits vor dem Einhängepunkt; Grundlage für `provider_error_streak` (AC-6) |
| `BriefingHealth()`/`provider_error_streak` (internal/scheduler/briefing_health.go) | signal | wird NICHT verändert; muss weiter gefüttert werden (AC-6) |
| `docs/specs/modules/issue_1115_openmeteo_model_fallback.md` | spec | Fundament — Nicht-Kaschieren-Muster, dasselbe Einhängeprinzip |

## Implementation Details

**1. `src/providers/region_routing.py` (NEU, ~55 LoC)**

Eigenständige Bounds-Tabelle (Land/Alpen-Rechtecke, bewusst getrennt von `REGIONAL_MODELS` in `openmeteo.py`, die Modell-Domänen und keine Länder-Grenzen beschreiben). Prüfreihenfolge AT → DE → FR, erste treffende Region gewinnt (macht Überlappungen — z. B. Alpengrenze DE/AT, Oberrhein FR/DE — deterministisch; Alpenraum als Wander-Kernfall fällt bewusst an AT).

| Region | min_lat | max_lat | min_lon | max_lon | Direkt-Provider |
|--------|---------|---------|---------|---------|-----------------|
| AT | 46.3 | 49.1 | 9.5 | 17.2 | `at_direct` |
| DE | 47.2 | 55.1 | 5.8 | 15.1 | `de_direct` |
| FR | 41.3 | 51.1 | -5.2 | 8.3 | `fr_direct` |

Funktion `direct_provider_for(lat: float, lon: float) -> Optional[str]` gibt den Provider-Namen der ersten treffenden Region zurück oder `None`, wenn die Koordinate außerhalb aller drei Regionen liegt.

**Import-Regel (Zyklus-Vermeidung):** `region_routing.py` darf `openmeteo.py` NICHT importieren (nur die umgekehrte Richtung ist erlaubt).

**2. `src/providers/regional_stubs.py` (NEU, ~35 LoC)**

EIN parametrisierter Stub-Provider (Klasse mit `name`-Property und `fetch_forecast`, erfüllt strukturell das `WeatherProvider`-Protocol aus `base.py`), instanziiert mit dem jeweiligen Provider-Namen (`at_direct`/`de_direct`/`fr_direct`). `fetch_forecast` wirft in diesem Slice immer `ProviderNotImplementedError(name, "...")` — bewusst NICHT `ProviderRequestError`, um „Stub noch nicht angebunden" von „Direkt-Provider technisch ausgefallen" zu unterscheiden (relevant für spätere Slices, die die Stubs durch echte Provider ersetzen).

**3. `src/providers/base.py` (MODIFY, ~12 LoC)**

- Neue Exception-Klasse `ProviderNotImplementedError(ProviderError)`.
- `_load_providers()`: die drei Stub-Namen registrieren (analog zum bestehenden `try/except ImportError`-Muster für `geosphere`/`openmeteo`/`brightsky`).

**4. `src/providers/openmeteo.py` (MODIFY, ~18 LoC, Zeile 864)**

Am bestehenden Einhängepunkt `if response_data is None: raise last_error` — **ausschließlich hier**, nachdem der komplette #1115-Modellfallback bereits gescheitert ist (kein früherer Eingriff, sonst wird #1115 unterlaufen):

```
if response_data is None:
    direct_name = direct_provider_for(location.latitude, location.longitude)
    if direct_name is not None:
        try:
            timeseries = get_provider(direct_name).fetch_forecast(
                location, start, end, enrich_ensemble
            )
            timeseries.meta.fallback_reason = "cross_provider_total_outage"
            timeseries.meta.fallback_model = direct_name
            return timeseries
        except ProviderNotImplementedError:
            pass  # Stub noch nicht angebunden -> Original-Fehler durchreichen (AC-5)
    raise last_error
```

`region_routing` und `get_provider`/`ProviderNotImplementedError` werden lokal importiert, um Modul-Ladereihenfolge und Zirkularität zu vermeiden.

**5. `src/output/renderers/email/plain.py` (MODIFY, ~5 LoC, Zeile 286-288)**

Footer-Fix: leere `fallback_metrics` darf keinen führenden Doppelpunkt (`"Fallback : x"`) erzeugen.

```
if fb.fallback_metrics:
    lines.append(f"Fallback {', '.join(fb.fallback_metrics)}: {fb.fallback_model}")
else:
    lines.append(f"Fallback: {fb.fallback_model}")
```

**6. `src/app/models.py` — kein Schema-Change.** `ForecastMeta.fallback_reason` existiert bereits (#1115); dieses Slice führt nur den neuen zulässigen String-Wert `"cross_provider_total_outage"` ein.

**AC-6 ohne Go-Code:** `_log_api_call` (openmeteo.py:501) persistiert jeden 5xx-Call bereits **vor** Zeile 864 in `openmeteo_calls.jsonl`. Die Go-Health-Logik (`briefing_health.go`) liest diese Datei unverändert weiter — `_request`/`_log_api_call` werden nicht angefasst, keine Log-Zeilen gelöscht, also wird `provider_error_streak` beim Total-Ausfall automatisch weiter gefüttert statt zurückgesetzt. Keine Go-Änderung in diesem Slice.

## Expected Behavior

- **Input:** Briefing-/Vergleichs-Wetterabruf via `fetch_forecast`; Open-Meteo hat bereits alle abdeckenden Modelle inkl. globalem ECMWF mit 5xx/Timeout ausgeschöpft (Total-Ausfall).
- **Output:** Bei bekannter Region (AT/DE/FR) und funktionierendem Direkt-Provider: `NormalizedTimeseries` des Direkt-Providers mit `meta.fallback_reason="cross_provider_total_outage"` und `meta.fallback_model=<region_direct>`. Bei unbekannter Region oder Stub/Ausfall: unveränderte ursprüngliche `ProviderRequestError` (identisches Verhalten wie vor diesem Slice).
- **Side effects:** Kein zusätzliches Logging über das bestehende `_log_api_call`-Protokoll hinaus in diesem Slice; keine Änderung an `provider_error_streak`-Berechnung (Go), nur weiterhin gefütterte Rohdaten.

## Acceptance Criteria

- **AC-1:** Given Open-Meteo hat alle abdeckenden Modelle (inkl. globalem ECMWF) mit 5xx/Timeout erschöpft, When `fetch_forecast` läuft, Then wird die Region der Koordinate bestimmt und ein registrierter Direkt-Provider für diese Region aufgerufen.
  - Test: Echter lokaler `ThreadingHTTPServer` liefert für ALLE Open-Meteo-Modell-Endpoints 503; ein registrierter (Test-)Direkt-Provider für die Zielregion liefert erfolgreich; `fetch_forecast` gibt dessen `NormalizedTimeseries` zurück statt eine Exception zu werfen.

- **AC-2:** Given keine Region-Zuordnung existiert (Koordinate außerhalb FR/DE/AT), When der Total-Ausfall eintritt, Then wird weiterhin die ursprüngliche `ProviderRequestError` geworfen (kein Verhaltensbruch außerhalb der drei Regionen).
  - Test: Total-Ausfall-Setup mit Koordinate außerhalb aller drei Bounds-Rechtecke (z. B. Skandinavien); `fetch_forecast` wirft dieselbe `ProviderRequestError`, die auch ohne dieses Slice geworfen würde (Regressionsschutz für alle Nicht-AT/DE/FR-Nutzer).

- **AC-3:** Given ein Direkt-Provider liefert erfolgreich ein `NormalizedTimeseries`, When das Ergebnis zurückkommt, Then trägt `meta.fallback_reason` den Wert `"cross_provider_total_outage"` und `meta.fallback_model` den Namen des genutzten Direkt-Providers.
  - Test: Nach erzwungenem Total-Ausfall mit erfolgreichem Direkt-Provider prüft der Test `result.meta.fallback_reason == "cross_provider_total_outage"` und `result.meta.fallback_model == "<region>_direct"`.

- **AC-4:** Given ein Cross-Provider-Fallback lief (leere `fallback_metrics`), When die Plain-Text-Mail gerendert wird, Then erscheint ein Footer-Hinweis ohne führendes Doppelpunkt-Artefakt.
  - Test: `render_plain_email` (bzw. die entsprechende Footer-Funktion) mit einer Timeseries, deren `fallback_model` gesetzt und `fallback_metrics` leer ist; der gerenderte Footer-String enthält `"Fallback: <model>"`, NICHT `"Fallback : <model>"` oder `"Fallback , : <model>"`.

- **AC-5:** Given der Regions-Direktprovider ist noch Stub, When der Total-Ausfall für diese Region eintritt, Then wird die ursprüngliche `ProviderRequestError` unverändert weitergereicht (kein Stub-Crash, keine Ersatz-Exception).
  - Test: Total-Ausfall-Setup für eine Koordinate innerhalb einer Region, deren Direkt-Provider der unveränderte Stub ist (wirft `ProviderNotImplementedError`); `fetch_forecast` wirft am Ende exakt die ursprüngliche `ProviderRequestError` des zuletzt gescheiterten Open-Meteo-Modells, nicht `ProviderNotImplementedError` und keine neue Ersatz-Exception.

- **AC-6:** Given Open-Meteo UND der Direkt-Provider fallen aus (bzw. Stub), When das Segment verarbeitet wird, Then bleibt das Segment sichtbar fehlerhaft (`has_error`) und das bestehende `provider_error_streak`-Signal wird weiter gefüttert (nicht zurückgesetzt).
  - Test: Nach dem AC-5-Szenario wird geprüft, dass die 5xx-Calls wie bisher in `openmeteo_calls.jsonl` protokolliert sind (identisches Verhalten zu #1115 ohne dieses Slice) — kein Log-Eintrag wird unterdrückt oder entfernt, sodass die bestehende Go-Health-Logik (`provider_error_streak`) unverändert weiterläuft. Kein Go-Test nötig, da keine Go-Datei geändert wird — der Python-Test verifiziert nur, dass die Log-Grundlage erhalten bleibt.

## Test-Strategie (keine Mocks)

Vorbild: `tests/tdd/test_issue_1115_model_fallback.py`. Neue Datei: `tests/tdd/test_issue_1141_cross_provider_fallback.py`.

- Echter lokaler `ThreadingHTTPServer`, `monkeypatch.setattr("providers.openmeteo.BASE_HOST", <lokale URL>)`.
- `AVAILABILITY_CACHE_PATH` und `DIAGNOSTICS_PATH` auf temporäre Pfade umgebogen (wie im #1115-Test), damit kein Produktionszustand berührt wird.
- ALLE Open-Meteo-Modell-Endpoints liefern 503 → echter Total-Ausfall ohne echten Incident, keine gemockte Exception.
- Für AC-1/AC-3/AC-4 wird ein Test-Direktprovider (nicht der finale Stub) via `register_provider` temporär registriert, der erfolgreich eine minimale `NormalizedTimeseries` zurückgibt — damit das Routing/Meta-Verhalten unabhängig vom (noch nicht existierenden) echten Provider bewiesen werden kann.
- Für AC-5/AC-6 wird der reale `regional_stubs`-Stub verwendet (kein Test-Double, sondern der produktive Stub-Code selbst).
- AC-Test-Mapping (Pflicht, 1:1 in Testdatei als Docstring/Kommentar je Testfunktion):

| AC | Testfunktion (geplant) |
|----|------------------------|
| AC-1 | `test_total_outage_routes_to_region_direct_provider` |
| AC-2 | `test_total_outage_outside_regions_raises_original_error` |
| AC-3 | `test_successful_direct_provider_sets_fallback_meta` |
| AC-4 | `test_plain_email_footer_no_leading_colon_on_empty_metrics` |
| AC-5 | `test_stub_provider_reraises_original_error` |
| AC-6 | `test_total_outage_keeps_feeding_error_log` |

## Known Limitations

- Dieses Slice liefert **keinen echten** Direktprovider — AT/DE/FR sind bis zu den Folge-Slices (#1142/#1143/#1144) technisch Stubs, die immer `ProviderNotImplementedError` werfen; Nutzer in diesen Regionen profitieren erst mit den Folge-Slices vom Cross-Provider-Fallback.
- Die Coverage-Bounds sind bewusst grobe Rechtecke (nicht exakte Landesgrenzen) — Überlappungen (Alpengrenze DE/AT, Oberrhein FR/DE) werden über die feste Prüfreihenfolge AT → DE → FR deterministisch, aber nicht geografisch exakt aufgelöst.
- Koordinaten außerhalb AT/DE/FR (der ganz überwiegende Teil der Weltkarte) profitieren nicht von diesem Fallback — Verhalten bleibt dort identisch zu vor #1141.
- Kein neuer Eskalationsmechanismus: die Sichtbarkeit eines Total-Ausfalls läuft weiterhin ausschließlich über das bestehende `provider_error_streak`-Signal (Go), keine zusätzliche Alarmstufe für „Cross-Provider-Fallback wurde benutzt".

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine additive Erweiterung des bestehenden Provider-Registry-/Fallback-Musters aus #1115 (ADR-0018 gilt bereits für das Nicht-Kaschieren-Prinzip, das hier 1:1 fortgeführt wird). Kein neuer Architektur-Grundsatz, kein neuer Layer, keine neue Cross-Cutting-Entscheidung — daher kein eigenes ADR nötig.

## Out of Scope (Folge-Issues)

- **#1142** — echter GeoSphere-Direktprovider für Österreich (`at_direct`).
- **#1143** — echter Météo-France-Direktprovider für Frankreich (`fr_direct`).
- **#1144** — echter DWD-Direktprovider für Deutschland (`de_direct`).
- **#1145** — eigenständiges Bug-Issue für den kosmetischen `"Fallback : icon_eu"`-Footer-Bug aus #1115 (dieses Slice fixt ihn nur soweit AC-4 es zwingend erfordert, schließt #1145 aber nicht automatisch).

## Changelog

- 2026-07-08: Initial spec created
