# Context: fix-3273-trip-grundauswahl-ohne-metrics

## Request Summary
Issue #3273 (Epic #3122): Das Validator-Soll (`--konfig`) leitet für einen Trip ohne
gespeicherte `display_config.metrics`, aber mit Tabelle (`display_config.placements`),
eine andere Grundauswahl ab als das Produkt. Folge: Fehlalarme der Mail-Prüfung.
Soll: Grundauswahl aus derselben Quelle wie das Produkt (Pendant zu #3242 AC-9 Orte).

## Ursache (belegt)
- Produkt `src/app/loader.py:611-631` (#3122 B2b): `display_config` besteht NUR aus
  `placements` (`_nur_placements`, loader.py:1040) bzw. fehlt ganz -> Grundauswahl wie bei
  fehlendem Schlüssel: `weather_config` migriert (`_migrate_weather_config`, loader.py:1251),
  sonst Profil-Standard `build_default_display_config_for_profile(id, aggregation.profile)`
  (`src/app/metric_catalog.py:1621`, Vorlage `WEATHER_TEMPLATES[profile]`, Rückfall `allgemein`).
  Nur wenn `display_config` weitere Schlüssel trägt und `metrics` fehlt/leer ist, gilt der
  Register-Standard (`trip_standard_bei_leer`, loader.py:1069).
- Validator `.claude/hooks/_soll_aus_konfiguration.py:382-390` (`_trip_display_config`):
  `metrics` fehlt/leer -> IMMER `_TRIP_STANDARD` (Register, `trip_default_rank`).
- Gemessen: Register-Standard = temperature, wind, gust, precipitation, thunder,
  freezing_level, visibility, temperature_day_low/high; Profil `allgemein` = temperature,
  temperature_night, wind, gust, precipitation, rain_probability, cloud_total, sunshine.
  Das erklärt den Befund (Produkt: Sun, Rain% ...; Soll: Thdr, 0°Line, Visib).

## Related Files
| File | Relevance |
|------|-----------|
| .claude/hooks/_soll_aus_konfiguration.py | `_trip_display_config`, `trip_soll`, `_mit_grundauswahl_tabelle` — Änderungsort |
| src/app/loader.py | Produktregel Grundauswahl (nur_tabelle / Profil / weather_config / Register) |
| src/app/metric_catalog.py | `build_default_display_config_for_profile`, `WEATHER_TEMPLATES` |
| src/services/channel_list_resolver.py | `tabellen_grundauswahl`/`grundauswahl` (Produktfolge, NICHT im Soll aufrufen — Spiegel-Verbot) |
| src/services/placements.py | `placements_aus_grundauswahl` (bereits im Soll erlaubt, #3237) |
| .claude/hooks/briefing_mail_validator.py, email_spec_validator.py | Aufrufer (lazy import) |
| tests/tdd/test_einstellung_gleich_mail_soll_placements.py, ..._auswahl.py | bestehende Soll-Tests (#3242/#3218) |

## Existing Patterns
- Orte AC-9 (#3242): nie eingestellt -> `orte_standardzeilen()` liest die Produkt-DATENquelle
  `CV2_ZEILEN` (Struktur, kein `resolve_*`). Analog hier: Vorlagen-Daten
  (`WEATHER_TEMPLATES` / Register / `_OLD_METRIC_MAP`), keine Auflösungsfunktion.
- Spiegel-Verbot (Spec #3242): kein `resolve_rows`, `resolve_channel_lists`, `placements_view`,
  `_cell`, `metrics_at` im Soll.

## Dependencies
- Upstream: `app.metric_catalog` (Register, Vorlagen), Trip-JSON wie die Go-API es liefert
  (Felder `aggregation.profile`, `weather_config`).
- Downstream: Briefing-Mail-Validator und E-Mail-Spec-Validator mit `--konfig`, Staging-Prüfkonto-Skripte.

## Existing Specs
- `docs/specs/modules/fix_3242_validator_soll_auswahl.md` (AC-9 Orte)
- `docs/specs/modules/feat_3122_was_steht_wo.md`

## Risks & Considerations
- Fallunterscheidung muss exakt der Loader-Regel folgen: `display_config` fehlt ODER nur
  `placements` -> Profil/weather_config; sonst Register-Standard (Bestandstests bleiben grün).
- `_trip_display_config` akzeptiert auch eine nackte display_config (ohne Trip-Hülle) —
  dann ist der Profil-Fall nicht erkennbar; bisheriges Verhalten beibehalten.
- Reihenfolge der Grundauswahl ohne bucket/order (Profil-MetricConfigs in Register-Folge)
  wirkt nur auf Größen ohne Tabellenzeile; in der Analyse gegen Produktfolge prüfen.
- Ungültiges/unbekanntes Profil: Produkt fällt auf `allgemein` zurück.

## Analysis

### Type
Bug (Prüfwerkzeug, Fehlalarm; keine Nutzer-Mail betroffen)

### Produktregel (Loader, exakt nachzubilden — Datenquellen, keine resolve-Funktion)
1. `display_config`-Schlüssel vorhanden und NICHT nur `{placements}` (auch `null`) -> wie bisher:
   `metrics` fehlt/`[]` = Register-Standard (`_TRIP_STANDARD`), sonst gespeicherte Liste.
2. `display_config` fehlt ODER besteht nur aus `placements`:
   a. `weather_config` vorhanden -> Altnamen über `_OLD_METRIC_MAP` (loader.py:1235) auf
      Katalog-IDs, eingeschaltet in Register-Folge (`get_all_metrics()`-Reihenfolge).
   b. sonst Profil `aggregation.profile` (fehlend/null/unbekannt -> `allgemein`), Vorlage
      `WEATHER_TEMPLATES[profil]` (Rückfall `allgemein`), eingeschaltet in Register-Folge.
   Die Tabelle `placements` bleibt erhalten.

### Messung Reihenfolge (Grundauswahl ohne bucket/order)
Produkt (`tabellen_grundauswahl`) liefert die Profil-Metriken in Register-Folge
(z. B. allgemein: temperature, temperature_night, wind, gust, precipitation, rain_probability,
cloud_total, sunshine). Der heutige Altformat-Pfad des Validators (`_altformat_folge`,
Register-PRIORITÄT) sortiert anders (temperature, wind, gust, rain_probability, ...), bei allen
4 Profilen abweichend. Deshalb erzeugt der neue Pfad Einträge MIT `order` = Register-Index
(`bucket: primary`), nicht über `_altformat_folge`. Wirkt nur auf Größen ohne Tabellenzeile.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| .claude/hooks/_soll_aus_konfiguration.py | MODIFY | `_trip_display_config`: Fall 2 (Profil / weather_config) nach Loader-Regel |
| tests/tdd/test_3273_trip_grundauswahl_ohne_metrics.py | CREATE | Soll-Tests mit von Hand notierten Listen + Gleichlauf mit echt geladenem Trip |
| docs/specs/modules/fix_3273_trip_grundauswahl_ohne_metrics.md | CREATE | Spec |

### Scope Assessment
- Files: 1 Code + 1 Test + Spec
- Estimated LoC: +40/-3
- Risk Level: LOW fachlich (nur Prüfwerkzeug); Adversary-Risiko HOCH (Hook-Code)

### Technical Approach
Fallunterscheidung in `_trip_display_config` anhand der rohen Trip-Hülle. Erkennung der
Hülle: Trip-JSON trägt `stages` oder `id`; eine nackte display_config (Aufrufer ohne Hülle)
behält das bisherige Verhalten. Quelle der Standardzeilen = Datentabellen des Produkts
(`WEATHER_TEMPLATES`, `_OLD_METRIC_MAP`, Register) — analog `CV2_ZEILEN` bei Orte AC-9,
kein `resolve_*` (Spiegel-Verbot bleibt). Gleichlauf-Test: Soll-Grundauswahl == Grundauswahl
des über den echten Loader geladenen Trips für alle Profile + weather_config + display_config
nur-placements/fehlend/null.

### Dependencies
`app.metric_catalog.WEATHER_TEMPLATES`, `app.loader._OLD_METRIC_MAP` (beides Daten).

### Open Questions
- keine (Produktentscheidung nicht berührt; Verhalten folgt der bestehenden Produktregel #3122 B2b)
