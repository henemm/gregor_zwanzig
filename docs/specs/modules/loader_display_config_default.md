---
entity_id: loader_display_config_default
type: module
created: 2026-05-03
updated: 2026-05-03
status: draft
version: "1.1"
tags: [bugfix, loader, display_config, defaults]
issue: 111
---

# Loader Display-Config Default

## Approval

- [ ] Approved

## Purpose

Trip-JSONs ohne `display_config` (und ohne Legacy-`weather_config`) erzeugten bisher `Trip.display_config = None`, woraufhin nachgelagerte Konsumenten (`WeatherChangeDetectionService.from_display_config`, E-Mail-Renderer, `tests/e2e/test_e2e_friendly_format_config.py::test_alert_enabled`) mit `AttributeError` abstuerzten. Der Loader injiziert jetzt einen profil-abhaengigen Default via `build_default_display_config_for_profile`, sodass jeder geladene Trip garantiert eine `display_config` besitzt.

## Source

- **File:** `src/app/loader.py`
- **Identifier:** `_parse_trip` — neuer `else`-Zweig nach dem bestehenden `weather_config`-Migration-Block (aktuell Zeile 136-140)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `loader` | modifiziert | `_parse_trip` ergaenzt um Default-Fallback |
| `metric_catalog` | aufgerufen | `build_default_display_config_for_profile(trip_id, profile)` liefert den profil-spezifischen Default |
| `activity_profile` | importiert | `ActivityProfile.ALLGEMEIN` als Fallback wenn `aggregation` oder `aggregation.profile` fehlt |
| `models` | konstruiert | `UnifiedWeatherDisplayConfig` mit `MetricConfig`-Eintraegen wird vom Catalog erzeugt |

## Implementation Details

Der bestehende Block in `_parse_trip` wird um einen `else`-Zweig erweitert:

```python
# Parse unified display config (Feature 2.6 v2) or migrate from old weather_config
display_config = None
if "display_config" in data:
    display_config = _parse_display_config(data["display_config"])
elif weather_config is not None:
    display_config = _migrate_weather_config(weather_config)
else:
    # Issue #111: kein display_config + kein weather_config → profil-abhaengiger Default
    from app.metric_catalog import build_default_display_config_for_profile
    profile = (
        aggregation.profile
        if aggregation is not None and getattr(aggregation, "profile", None) is not None
        else ActivityProfile.ALLGEMEIN
    )
    display_config = build_default_display_config_for_profile(data["id"], profile)
```

Kein Go-Backend-Touch (`internal/handler/trip.go` ist bereits Read-Modify-Write-safe, abgesichert durch `TestUpdateTripHandlerPreservesDisplayConfig`).

**Zusaetzlich: Einmaliger JSON-Backfill (v1.1).** Der reine Loader-Default deckt den urspruenglichen Issue-Test `test_alert_enabled` nicht ab, weil dessen Helper `modify_metric_config` direkt das JSON-File auf der Platte mutiert (`data["display_config"]["metrics"]`) und am Loader vorbeigeht. Daher zusaetzlich einmaliger Backfill ueber `scripts/backfill_display_config_issue111.py`:

- Iteriert `data/users/*/trips/*.json`
- Skippt Files mit existierendem `display_config` oder Legacy-`weather_config`
- Bei Treffer: erzeugt Default-Block via gleicher Catalog-Funktion und mergt ihn JSON-direkt in das File (kein Read-Modify-Write durch Loader, alle anderen Felder bleiben byte-identisch unangetastet)
- Vorab manuelles `tar.gz`-Backup nach `.backups/data-pre-issue111-backfill-<ts>.tar.gz`

Das Skript ist idempotent — wiederholte Laeufe sind no-ops auf bereits gepatchten Files.

## Expected Behavior

- **Input:** Trip-JSON ohne `display_config`-Key und ohne Legacy-`weather_config`-Key (z.B. `data/users/default/trips/gr221-mallorca.json`, `zillertal-mit-steffi.json`).
- **Output:** `Trip.display_config = build_default_display_config_for_profile(trip_id, profile)` — niemals `None`. Profil wird aus `aggregation.profile` gelesen.
- **Edge:** Wenn `data["aggregation"]` fehlt oder `aggregation.profile is None` → `profile = ActivityProfile.ALLGEMEIN`.
- **Side effects:** Keine. Reine In-Memory-Konstruktion. Die JSON-Datei auf der Platte wird vom Loader nicht modifiziert.

## Known Limitations

- Der Default existiert nur In-Memory bis zum naechsten Trip-Save (typischerweise erste UI-Aktion, da das Frontend das vollstaendige Trip-Objekt zurueckschreibt). Solange kein Save erfolgt, wird der Default bei jedem Load neu berechnet.
- Der Default-`UnifiedWeatherDisplayConfig` enthaelt 29 Metriken, von denen pro Profil-Template nur ca. 10 `enabled=True` haben. Alle Metriken haben `alert_enabled=False` per Default — Alerts muss der User aktiv per UI einschalten.
- Bei Loader-Aufrufen ohne `data["id"]` (sollte nie vorkommen, da Pflichtfeld) wuerde `build_default_display_config_for_profile` mit `KeyError` scheitern. Bestehendes Verhalten — kein zusaetzlicher Schutz noetig.

## Changelog

- 2026-05-03: Initial spec — Issue #111 (Loader-Default fuer fehlende display_config).
- 2026-05-03 (v1.1): Backfill-Schritt ergaenzt — `scripts/backfill_display_config_issue111.py` schreibt den Default einmalig in bestehende JSON-Files, weil `test_alert_enabled` das File direkt mutiert und den Loader umgeht.
