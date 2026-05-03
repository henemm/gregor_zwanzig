---
issue: 111
title: GR221-Trip-JSON fehlt display_config-Block (test_alert_enabled scheitert)
status: phase1-context
---

# Context: Issue #111 — display_config fehlt auf Trip-JSON

## Request Summary

`tests/e2e/test_e2e_friendly_format_config.py::test_alert_enabled` scheitert mit `KeyError: 'display_config'`, weil `data/users/default/trips/gr221-mallorca.json` (und auch `zillertal-mit-steffi.json`) keinen `display_config`-Block hat. Der Trip wird mit `display_config=None` geladen und der Test greift dann auf `trip.display_config.metrics` zu.

## Symptom & Root Cause

**Symptom:** Test wirft `KeyError`/`AttributeError` weil `trip.display_config is None`.

**Root Cause:** Der Loader in `src/app/loader.py:136-140` erzeugt nur dann ein `UnifiedWeatherDisplayConfig`, wenn entweder `display_config` ODER das Legacy-`weather_config` im JSON steht. Beide gr221-mallorca.json und zillertal-mit-steffi.json haben weder das eine noch das andere → `display_config = None`.

Die Recovery-Aktion aus Issue #102 hat die GR221-Stages wiederhergestellt, aber den `display_config`-Block nicht. Da der Test (und produktive Code-Pfade wie `WeatherChangeDetectionService.from_display_config`) ein nicht-None `display_config` erwarten, scheitert es.

## Related Files

| Datei | Relevanz |
|------|----------|
| `data/users/default/trips/gr221-mallorca.json` | Betroffenes Trip-JSON ohne display_config |
| `data/users/default/trips/zillertal-mit-steffi.json` | Auch betroffen — gleicher Defekt |
| `src/app/loader.py:136-140` | Loader injiziert keinen Default wenn display_config + weather_config fehlen |
| `src/app/loader.py:580-603` | `_trip_to_dict()` schreibt display_config nur, wenn nicht None — propagiert das Problem zurück |
| `src/app/trip.py:181` | `display_config: Optional[UnifiedWeatherDisplayConfig] = None` — kein default_factory |
| `src/app/models.py:443-526` | `MetricConfig`- und `UnifiedWeatherDisplayConfig`-Definitionen |
| `src/services/weather_change_detection.py:96-123` | `from_display_config()` greift auf `display_config.metrics` zu — crasht wenn None |
| `tests/e2e/test_e2e_friendly_format_config.py:272-322` | Der scheiternde Test |
| `internal/model/trip.go:27` | Go-Backend: `DisplayConfig map[string]interface{} json:"display_config,omitempty"` — opaque |
| `internal/store/store.go` | Persistenz im Go-Backend — KEIN Merge, schreibt was es bekommt |

## Existing Patterns

- **Optional-mit-None statt default_factory:** Trip-Modell verwendet konsequent `Optional[X] = None` für nachträglich eingeführte Felder (Feature 2.6: display_config, report_config). Default-Werte werden in den Service-Konsumenten erwartet — funktioniert nicht, wenn der Service None nicht behandelt.
- **MetricConfig-Defaults:** `MetricConfig` hat sinnvolle Default-Werte (`use_friendly_format=True`, `alert_enabled=False`). Eine Default-`UnifiedWeatherDisplayConfig` ohne Metriken wäre aber funktionslos — die produktive Default-Liste muss aus einem Metric-Catalog kommen.
- **Read-Modify-Write bei Schema-Reworks (CLAUDE.md):** „Bei Aenderungen an Persistenz-Strukturen MUESSEN Bestandsdaten erhalten bleiben." → Wir dürfen weder das JSON-Schema brechen noch beim nächsten Save Felder verlieren. Schema-Backup-Hook greift automatisch (`.backups/data-pre-rework-*.tar.gz`).

## Dependencies

- **Upstream:** `loader.py` ist die zentrale JSON→Trip-Brücke; alle Services laden Trips über `load_all_trips()`.
- **Downstream:** `WeatherChangeDetectionService.from_display_config`, E-Mail-Renderer, Scheduler — alle erwarten `trip.display_config != None`.

## Existing Specs

- `docs/specs/modules/` — KEIN Spec für `display_config` oder `loader` vorhanden (vorbestehende Lücke). Eventuell im Zuge der Lösung anlegen.
- `docs/features/architecture.md` — Pipeline `Provider → Normalizer → Risk Engine → Formatter → Channel`; display_config wirkt im Formatter und in der Risk Engine.

## Risks & Considerations

1. **Datenverlust-Risiko:** Wenn wir `display_config` in JSON nachträglich schreiben, MUSS das Schema-Backup-Hook (`data_schema_backup.py`) vor der Aktion laufen. Bei Migrations-Skripten Roundtrip-Test pflicht.
2. **Go/Python-Drift:** Beide Backends lesen/schreiben dieselben JSON-Files. Wenn Python `display_config` injiziert und Go beim nächsten Save (Trip-Edit aus UI) das Feld nicht erhält → erneuter Datenverlust. → Lösung muss Go-Pfad mitberücksichtigen.
3. **Default-Inhalt von display_config:** Eine leere Liste `metrics=[]` macht den Test trotzdem fehlschlagen (cape/wind nicht in thresholds). Default-Liste muss aus dem `MetricCatalog` kommen — diesen Catalog suchen/verwenden.
4. **Test-Roboustness vs. Daten-Korrektur:** Test robust machen (Option d) löst das Symptom, nicht die Ursache. Produktive Pfade wie der WeatherChangeDetectionService würden weiter crashen.
5. **Zillertal-Trip:** Auch betroffen — Lösung muss beide Trips abdecken.

## Phase-2-Befunde (Recherche-Ergebnisse)

### MetricCatalog ist da
- `src/app/metric_catalog.py:351` `build_default_display_config(trip_id)` — generic, alle 29 Metriken, nur 8 enabled by default.
- `src/app/metric_catalog.py:450` `build_default_display_config_for_profile(trip_id, profile)` — profile-aware (Wintersport/Wandern/Skitouren/etc.), bereits per-Profil-Liste in `WEATHER_TEMPLATES` definiert.
- Beide Funktionen nehmen einen `str` als ersten Parameter, der in `UnifiedWeatherDisplayConfig.trip_id` landet — wir können den Trip-`id` direkt durchreichen.

### Profile am Trip
- GR221 und Zillertal haben beide `aggregation.profile = "wintersport"` im JSON.
- Falls Profile fehlt → Fallback `ActivityProfile.ALLGEMEIN`.

### Go-Backend ist SAFE
- `internal/handler/trip.go:126-196` macht echtes Read-Modify-Write Merge: nur Felder die im PUT-Body gesetzt sind, werden überschrieben.
- `internal/handler/trip_write_test.go:228-243` `TestUpdateTripHandlerPreservesDisplayConfig` beweist: minimaler PUT (nur name+stages) erhält display_config aus dem Disk-State.
- Frontend (`frontend/src/lib/components/edit/TripEditView.svelte:44-51`) sendet immer das **vollständige** Trip-Objekt (Spread-Pattern) → display_config wird mit jedem Save mitgesendet.
- **→ Kein Datenverlust-Risiko**, wenn Loader display_config zur Laufzeit injiziert.

### Backfill ist NICHT nötig
- Sobald der Loader Default-display_config injiziert, ist es zur Laufzeit immer da.
- Beim ersten Trip-Edit aus der UI wird der Default automatisch persistiert (Frontend sendet `display_config` mit, Go schreibt es in JSON).
- JSON-Files werden also **organisch** repariert, ohne riskante Migration.

## Empfehlung (Tech-Lead)

**Loader-Default-Injection ohne Backfill.** Konkret:

In `src/app/loader.py` nach Zeile 140 ein `else`-Branch ergänzen:
```python
else:
    from app.metric_catalog import build_default_display_config_for_profile
    from app.activity_profile import ActivityProfile
    profile = (
        aggregation.profile if aggregation and aggregation.profile
        else ActivityProfile.ALLGEMEIN
    )
    display_config = build_default_display_config_for_profile(data["id"], profile)
```

Begründung:
1. Behebt Ursache zentral, nicht nur das Symptom.
2. Auch zukünftige Trips ohne explizites display_config sind robust.
3. Verwendet bereits vorhandene Catalog-Funktion → keine Duplikat-Logik.
4. Go-Backend verhält sich beweisbar Merge-sicher → keine Daten-Migration nötig.
5. Test `test_alert_enabled` wird grün, ohne den Test selbst anzufassen.

## Scope

- **Dateien:** 2 (loader.py + neuer Unit-Test)
- **LoC:** ~40 (10 Code, 30 Test)
- Beide gut unter den Limits (5 Dateien / 250 LoC).

## Risiken

1. **`aggregation` kann None sein** → Fallback auf `ActivityProfile.ALLGEMEIN` muss explizit getestet werden.
2. **Existing Tests** könnten implizit von `display_config is None` abhängen → ein voller `uv run pytest`-Lauf vor Implementation prüfen.
3. **Profile-Wert kann unbekannt sein** → `WEATHER_TEMPLATES.get(profile.value, WEATHER_TEMPLATES["allgemein"])` fängt das schon ab (siehe `metric_catalog.py:457`).

## Nächster Schritt

`/3-write-spec` — formale Spec für `loader_display_config_default` erstellen.
