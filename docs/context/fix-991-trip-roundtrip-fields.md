# Context: fix-991-trip-roundtrip-fields (#991)

## Aufgabe

`_trip_to_dict(load_trip(...))`-Roundtrip verliert die Top-Level-Keys
`accuracy_pct`, `headline`, `briefings_count`, `alerts_count`. Test rot auf main:
`tests/tdd/test_alert_rules_model.py::test_ac9_all_production_trips_load_with_additive_migration`.

## Root Cause (recherchiert)

- Der Test macht einen **reinen** Modell-Roundtrip (`_trip_to_dict(load_trip(json))`),
  **ohne** `save_trip`. Der #805-Merge (`_deep_merge_preserve_unknown`, `loader.py:1240`)
  greift daher NICHT — er wirkt nur beim Überschreiben derselben Datei in `save_trip`.
- Die vier Felder gehen verloren, weil das **Trip-Modell** (`src/app/trip.py:169`) sie nicht
  trägt und `_parse_trip`/`_trip_to_dict` (`loader.py`) sie nicht kennt.
- Bisheriges Muster war Whack-a-mole: pro Go-Feld ein eigenes Dataclass-Attribut
  (`region`/`archived_at` #805, `paused_at` #995, `official_alerts_enabled` #1087).
  #991 wäre der vierte Anbau — gleiche Datenverlust-Klasse wie BUG-DATALOSS-GR221 (#102).
- Die vier Keys existieren nirgends in `src/` — reine Go-/Legacy-Metadaten.

## Prod-JSON Top-Level-Keys (Beispiel dachstein-2023)
`{id, name, stages, alert_rules, archived_at, accuracy_pct, alerts_count, briefings_count, headline}`
Modelliert/erhalten: id, name, stages, alert_rules, archived_at. Verloren: die 4 Metadaten.

## Test-Vertrag
`data/users/*/trips/*.json` → `_trip_to_dict(load_trip(f))` → alle Top-Level-Keys müssen
überleben, AUSSER `alert_rules` und drift-tolerante Config-Maps
`{display_config, report_config, weather_config, aggregation}`.

## Design-Entscheidung (Tech Lead): generische Erhaltung statt Einzelfeld

Ein generisches `extra: dict`-Feld am Trip fängt beim Laden **alle** Top-Level-Keys auf,
die weder modelliert noch bekannt sind, und `_trip_to_dict` re-emittiert sie
(modellierte Keys gewinnen — `extra` füllt nur Lücken). Beendet die wiederkehrende
Whack-a-mole-Klasse (#805/#995/#1087/#991) an der Wurzel.

Bekannte Top-Level-Keys (Ausschluss-Set für `extra`): id, name, stages, avalanche_regions,
aggregation, shortcode, activity, region, archived_at, paused_at, official_alerts_enabled,
weather_config, display_config, report_config, alert_rules, alert_cooldown_minutes,
alert_quiet_from, alert_quiet_to, trip.

## Affected Files
- `src/app/trip.py` — `extra`-Feld am Trip-Dataclass
- `src/app/loader.py` — `_parse_trip` (extra befüllen), `_trip_to_dict` (extra re-emittieren)

## Verwandt
- #805 (save_trip-Merge, Pflaster nur für File-Level), #995, #1087. #991 löst das darunter.

## Tests
Echter Roundtrip gegen Prod-JSONs (keine Mocks). Bug-reproduzierender Test:
test_ac9 (rot vor Fix, grün nach Fix) + gezielter Test für die 4 Felder + einen synthetischen
unbekannten Key (Generik beweisen).
