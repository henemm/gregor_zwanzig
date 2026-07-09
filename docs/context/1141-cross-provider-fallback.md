# Context: 1141 Cross-Provider-Fallback — Routing-Unterbau + Total-Ausfall-Erkennung (Slice 0)

## Request Summary
Der gemeinsame Unterbau (Slice 0/4 von Epic #1127), der greift, wenn Open-Meteo als Verteiler
**komplett** ausfällt (alle Modelle inkl. globalem ECMWF erschöpft). Kein neuer echter Provider in
diesem Slice — nur Weiche (Region→Provider-Routing), ein zentraler Einhängepunkt, sichtbare
Markierung und Stub-Direktprovider je Region (AT/FR/DE).

## Related Files
| File | Relevance |
|------|-----------|
| `src/providers/openmeteo.py:864-867` | **Einhängepunkt**: `if response_data is None: raise last_error` — exakt der Total-Ausfall-Moment, an dem alle abdeckenden Modelle mit 5xx/Timeout gescheitert sind. Nur hier (nicht früher) einhängen, sonst wird #1115 unterlaufen. |
| `src/providers/openmeteo.py:872-875` | Bestehendes Nicht-Kaschieren-Muster (`fallback_model`/`fallback_reason="model_5xx"`) — Vorbild für neuen Wert. |
| `src/providers/openmeteo.py:103-144` | `REGIONAL_MODELS` mit `bounds` — **NICHT** blind kopieren (sind Modell-Domänen, keine Länder-Grenzen). Neue bewusste Routing-Bounds nötig. |
| `src/providers/base.py:18-64` | `WeatherProvider`-Protocol — Stub-Provider müssen es strukturell erfüllen (`name`, `fetch_forecast`). |
| `src/providers/base.py:82-94` | `ProviderRequestError` mit `status_code` (4xx vs. 5xx). |
| `src/providers/base.py:97-172` | Registry (`register_provider`/`get_provider`/`_load_providers`) — mögliche Heimat für Routing-Tabelle. |
| `src/app/models.py:74-88` | `ForecastMeta` mit `fallback_model`/`fallback_reason`/`fallback_metrics` — neuer Wert `"cross_provider_total_outage"`. |
| `src/output/renderers/email/plain.py:286-288` | Footer-Renderer. Bereits **heute** Bug: leere `fallback_metrics` → `"Fallback : icon_eu"` (führender Doppelpunkt). AC-4 muss das sauber machen; eigenständiger Bug ist #1145. |
| `tests/tdd/test_issue_1115_model_fallback.py` | Test-Vorbild: echter lokaler `ThreadingHTTPServer`, `monkeypatch` von `BASE_HOST` + `AVAILABILITY_CACHE_PATH` + `DIAGNOSTICS_PATH`, alle Kandidaten 503 → Total-Ausfall ohne echten Incident. Siehe `_provider_seam`. |

## Existing Patterns
- **Nicht-Kaschieren (#1115, ADR-0018):** Jedes Ausweichen wird in `ForecastMeta` markiert; 5xx/Timeout
  → ausweichen erlaubt, 4xx → sofort durchreichen (kein Quell-Roulette). Gilt 1:1 für #1127.
- **Lazy-Registry:** Provider registrieren sich in `_load_providers()`; `get_provider(name)` erzeugt Instanz.
- **Coverage-Bounds als Rechteck:** `{min_lat,max_lat,min_lon,max_lon}` — dasselbe Format für die
  Routing-Tabelle, aber mit **bewusst gewählten** Land/Alpen-Grenzen.
- **Mock-freier Test-Seam:** lokaler HTTP-Server + `monkeypatch.setattr("providers.openmeteo.BASE_HOST", url)`.

## Dependencies
- **Upstream (was fetch_forecast nutzt):** `_candidate_models`, `_request`, `ProviderRequestError`,
  `NormalizedTimeseries`/`ForecastMeta`.
- **Downstream (was fetch_forecast nutzt):** alle Kernpfade rufen `get_provider("openmeteo").fetch_forecast`
  (`trip_alert.py:885`, `trip_report_scheduler.py:986/1115/1175`, `comparison_engine.py:300`, u.a.).
  → **Einhängen INNERHALB `fetch_forecast`** lässt alle Aufrufstellen automatisch profitieren (kein 7-fach-Patch).

## Existing Specs
- `docs/specs/modules/issue_1115_openmeteo_model_fallback.md` — Intra-Open-Meteo-Modell-Fallback (Fundament).
- `docs/features/epic-1127-cross-provider-fallback.md` — Epic-Plan mit ACs-Rohfassung, Slice-Schnitt,
  offenen Fragen. Frage 8 (Eskalation) entschieden: bestehende Alarmkette via `provider_error_streak`.

## Risks & Considerations
- **#1115 nicht unterlaufen:** Einhängen NUR am Total-Ausfall-Punkt (Z. 864), nachdem der Modell-Fallback
  bereits gescheitert ist. Zu früh = Quell-Roulette statt geordnetem Modell-Fallback.
- **Routing-Bounds bewusst wählen** — nicht `REGIONAL_MODELS`-Bounds kopieren (Modell- ≠ Länder-Grenze).
- **Stub darf nicht crashen (AC-5):** Stub-Provider reicht ursprüngliche `ProviderRequestError` unverändert
  durch — kein neuer Crash, kein „Fallback fehlgeschlagen"-Ersatzfehler.
- **Footer-Robustheit (AC-4):** leere `fallback_metrics` darf kein `"Fallback : x"`-Artefakt erzeugen.
- **Eskalationssignal (AC-6):** `provider_error_streak` (Go, `briefing_health.go`) darf im Total-Ausfall
  **weiter gefüttert, nicht zurückgesetzt** werden — kein neuer Mechanismus.
- **LoC-Limit 250:** Routing + Registry + Renderer + neuer Reason + Stubs. Sollte es reißen, Registry-Umbau
  vom Renderer-Fix trennen statt Override.

## Analysis

### Type
Feature (Slice 0/4 des Epics #1127 — Fundament).

### Technical Approach (Plan/Sonnet, verifiziert)
Neues entkoppeltes Modul `src/providers/region_routing.py` kapselt bewusst gewählte Land/Alpen-Rechtecke
(getrennt von `REGIONAL_MODELS`) und liefert `direct_provider_for(lat, lon) -> Optional[str]`. Einziger
Einhängepunkt: `openmeteo.py:864` (`if response_data is None`). Dort Region bestimmen → Direkt-Provider via
bestehendes `get_provider` auflösen → aufrufen → bei Erfolg `meta.fallback_reason="cross_provider_total_outage"`
+ `meta.fallback_model=<name>` → bei Stub/fehlender Region/Ausfall wie bisher `raise last_error`. Alle
externen `get_provider("openmeteo")`-Aufrufstellen bleiben unberührt (Weiche liegt intern).

**Stub-Design:** EIN parametrisierter Stub, registriert unter `at_direct`/`fr_direct`/`de_direct`. Wirft neue
`ProviderNotImplementedError` (Subklasse von `ProviderError`, NICHT `ProviderRequestError` — hält „Stub" von
„Direkt-Provider ausgefallen" getrennt). Einhängepunkt fängt genau diese → `raise last_error` (AC-5).

**AC-6 ohne Go-Code:** `_request` → `_log_api_call` (`openmeteo.py:501`) persistiert jeden 5xx in
`openmeteo_calls.jsonl` **vor** Z. 864. Go-Health (`briefing_health.go:209-232`) scannt genau diese Datei.
Wir fassen weder `_request`/`_log_api_call` an noch löschen Log-Zeilen → `provider_error_streak` wird
automatisch weiter gefüttert. **Go-Änderung: NEIN.**

### Coverage-Bounds (bewusst gewählt, Prüfreihenfolge AT → DE → FR, erste Region gewinnt)
| Region | min_lat | max_lat | min_lon | max_lon | Direkt-Provider |
|--------|---------|---------|---------|---------|-----------------|
| AT | 46.3 | 49.1 | 9.5 | 17.2 | `at_direct` |
| DE | 47.2 | 55.1 | 5.8 | 15.1 | `de_direct` |
| FR | 41.3 | 51.1 | -5.2 | 8.3 | `fr_direct` |

Überlappungen bewusst (Alpengrenze DE/AT, Oberrhein FR/DE); Prüfreihenfolge macht Zuordnung deterministisch —
Alpenraum (Wander-Kernfall) fällt bei Grenzkoordinaten an AT.

### Affected Files (with changes)
| File | Change Type | Description | ~LoC |
|------|-------------|-------------|------|
| `src/providers/region_routing.py` | CREATE | Bounds-Tabelle + `direct_provider_for` | ~55 |
| `src/providers/regional_stubs.py` | CREATE | Parametrisierter Stub + `ProviderNotImplementedError`-Wurf | ~35 |
| `src/providers/openmeteo.py` | MODIFY | Einhängeblock Z. 864 | ~18 |
| `src/providers/base.py` | MODIFY | `ProviderNotImplementedError` + Stub-Registrierung in `_load_providers` | ~12 |
| `src/output/renderers/email/plain.py` | MODIFY | Footer-Fix (leere `fallback_metrics`, AC-4) | ~5 |
| `src/app/models.py` | — | Kein Schema-Change (nur neuer String-Wert) | 0 |
| `tests/tdd/test_issue_1141_cross_provider_fallback.py` | CREATE | Test nach #1115-Muster (lokaler HTTP-Server, alle Modelle 503) | ~120 (nicht LoC-limitiert) |

### Scope Assessment
- Produktions-LoC: ~95–135 → **unter 250-Limit**, kein Override nötig.
- Risk Level: MEDIUM (Eingriff im zentralen Fetch-Pfad, aber additiv nur im Total-Ausfall-Zweig).

### Offene Punkte / Hinweise
- **AC-4 vs. #1145:** Der Footer-Fix härtet die leere-`fallback_metrics`-Zeile — das behebt en passant auch
  den kosmetischen #1115-Bug (`"Fallback : icon_eu"`). #1145 bleibt als eigenständiges Bug-Issue bestehen;
  hier wird der Fix nur soweit gemacht, wie AC-4 ihn zwingend braucht.
- **Import-Zyklus vermeiden:** `region_routing.py` darf `openmeteo.py` NICHT importieren (nur umgekehrt).
- Keine blockierenden offenen Fragen — Design ist entscheidungsreif für die Spec.
