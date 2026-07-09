# Context: feat-1142-geosphere-fallback

## Request Summary
Slice AT von Epic #1127: Den bereits als Stub verdrahteten Direktprovider `at_direct` durch den **echten** GeoSphere-Provider ersetzen. Dazu: (1) empirische Coverage-Bounds für GeoSphere bestimmen und im Router (#1141) so registrieren, dass Koordinaten außerhalb GeoSphere NICHT als Kandidat wählen; (2) im Fallback-Modus die versteckte Open-Meteo-Wolken-Abhängigkeit abschalten (`include_cloud_layers=False`); (3) Adversary-Nebenbefund F001 aus #1141 mit abfangen (echter Provider kann jetzt `ProviderRequestError`/`ProviderNotFoundError` werfen).

## Related Files
| File | Relevance |
|------|-----------|
| `src/providers/regional_stubs.py` | `make_at_direct` (Stub) → muss durch GeoSphere-Backed-Factory ersetzt/ergänzt werden |
| `src/providers/base.py:181-184` | Registry: `register_provider("at_direct", make_at_direct)` → Umhängen auf GeoSphere-Variante |
| `src/providers/geosphere.py:172-208` | `fetch_forecast` — Protocol-Entry; delegiert an `fetch_combined(..., include_snow=True)` OHNE `include_cloud_layers` → default `True` (versteckter Open-Meteo-Call) |
| `src/providers/geosphere.py:406-465` | `fetch_combined(..., include_cloud_layers=True)` — hier sitzt der Cloud-Enrich-Zweig |
| `src/providers/geosphere.py:336-405` | `_fetch_openmeteo_clouds` → direkter `api.open-meteo.com`-Call, genau die im Total-Ausfall wegfallende Infrastruktur |
| `src/providers/region_routing.py:33-46` | AT-Region-Box (46.3–49.1 / 9.5–17.2) → **Gate für AC-2**; muss GeoSphere-Coverage widerspiegeln |
| `src/providers/openmeteo.py:864-892` | Cross-Provider-Einhängepunkt; fängt aktuell NUR `ProviderNotImplementedError` → **F001-Lücke** |
| `src/providers/brightsky.py:25-46` | Vorbild-Muster `within_radolan_coverage(lat, lon)` für Coverage-Funktion |

## Existing Patterns
- **Coverage-Funktion:** `brightsky.within_radolan_coverage(lat, lon)` — Bounding-Box-Konstanten + reine Prüffunktion. Analog für GeoSphere.
- **Bounds empirisch bestimmen:** `openmeteo.py:145-153` dokumentiert Grenzwerte über echte Diagnose-Calls (Kommentar mit Datum + Begründung). Gleiches Vorgehen für GeoSphere-Coverage.
- **Provider-Registry:** `base.register_provider(name, factory)`; `get_provider(name)` ruft `factory()` (No-Arg). Factories via `functools.partial` (siehe `regional_stubs`).
- **Fallback-Seam:** `openmeteo.fetch_forecast` ruft `get_provider(direct_name).fetch_forecast(...)` und setzt `meta.fallback_reason`/`fallback_model`.

## Dependencies
- **Upstream (was wir nutzen):** `geosphere.GeoSphereProvider.fetch_combined`, `region_routing.direct_provider_for`, `base.get_provider`/`register_provider`.
- **Downstream (was uns nutzt):** Der Total-Ausfall-Seam in `openmeteo.fetch_forecast`. **Wichtig:** `GeoSphereProvider` (Name `"geosphere"`) wird regulär von `comparison_engine` (Alpen), `radar_service`, Trip-Services genutzt — deren Verhalten (mit Wolken) darf sich NICHT ändern. Der Fallback braucht eine **separate, wolkenlose Variante**, nicht eine Verhaltensänderung an GeoSphere selbst.

## Existing Specs
- `docs/specs/modules/issue_1141_cross_provider_routing.md` — Routing-Unterbau (Vorgänger-Slice)
- `docs/specs/modules/api_retry.md` — GeoSphere Retry-Verhalten (unverändert lassen, AC-4)
- `docs/features/epic-1127-cross-provider-fallback.md` — Epic-Plan (Slice-Reihenfolge, AC-Vorlagen Z.179-181)

## Risks & Considerations
- **R1 — Coverage-Box vs. Region-Box (Kern-Design-Entscheidung):** `region_routing` AT-Box ist bewusst eine grobe Länder/Alpen-Box (Kommentar Z.8-13), war für den Stub okay. Jetzt entscheidet sie real, ob GeoSphere gewählt wird. Ist die Box weiter als GeoSphere-Coverage, wird für Koordinaten dazwischen GeoSphere gewählt und schlägt fehl → widerspricht AC-2. **Entscheidung für Spec/Analyse:** AT-Region-Box auf empirische GeoSphere-Coverage setzen (bzw. zweistufige Prüfung Region→Coverage).
- **R2 — Wolken-Abschaltung ohne Kollateralschaden:** Sauberste Lösung ist ein dünner Adapter (`fetch_forecast` → `fetch_combined(..., include_cloud_layers=False)`) als `at_direct`-Factory, statt eine Verhaltensänderung an der geteilten `GeoSphereProvider.fetch_forecast`. Vermeidet Regress bei `comparison_engine`/`radar_service`.
- **R3 — F001 (Exception-Propagation):** Seam fängt nur `ProviderNotImplementedError`. Echter GeoSphere kann `ProviderRequestError` (5xx/Timeout) werfen; `get_provider` kann `ProviderNotFoundError` werfen. Beide müssen so gefangen werden, dass `raise last_error` (Segment `has_error`) greift — kein neuer Crash-Exception-Typ. AC-4.
- **R4 — Keine Mocks:** Coverage-Bounds und Fehlerpfade müssen mit **echten** GeoSphere-API-Calls (inkl. Grenzwert-Koordinaten und einem echten 5xx/Timeout-Szenario am Seam) belegt werden.
- **R5 — Fehlzitat #288/enrich_ensemble** aus dem Epic-Body ist KEIN Bug und NICHT Teil dieses Slices (GeoSphere hat keine Ensemble-API; `enrich_ensemble` wird korrekt ignoriert).
