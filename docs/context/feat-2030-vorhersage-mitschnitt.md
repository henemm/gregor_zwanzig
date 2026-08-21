# Context: feat-2030-vorhersage-mitschnitt

Issue #2030 · Milestone „Tour KHW 2026-08" · Herkunft: PO-Entscheid 2026-08-21 aus der
Analyse zu #2020.

## Request Summary

Jeder Verbrauch einer Wettervorhersage soll festhalten, **was das System zu diesem Zeitpunkt
für welchen Ort und welchen Zeitraum erwartete** — als rollierende Aufzeichnung mit
Aufbewahrungsfrist. Ziel ist ausschließlich Nachvollziehbarkeit: Bei #2020 war die Kernfrage
„wann sprang die Vorhersage von 7,4 mm auf 29,4 mm?" mit keiner vorhandenen Quelle
beantwortbar, und damit nicht entscheidbar, ob die Auslöseschwelle zu hoch stand oder die
Vorhersage zu spät hochkam.

## Ausgangslage — was heute fehlt und was schon da ist

| Quelle | Was sie hält | Warum sie für #2030 nicht reicht |
|---|---|---|
| `src/services/alert_log.py` | die **Entscheidung** (ausgelöst/unterdrückt, Grund, Kanäle) | keine Vorhersagestände; Read-Modify-Write der ganzen Datei, **keine Retention** |
| `alert_input_capture.capture_user_scoped` (Zweig a, `trip_alert.py:355`) | die **Änderungsliste** eines Δ-Alarms | wird erst geschrieben, **wenn ein Alarm ausgelöst wurde**. Ein „Alarm hätte kommen müssen, kam aber nicht" hinterlässt nichts |
| `alert_input_capture.capture_system` (Zweig c, `radar_service.py:228/242`) | rohe **Nowcast-Frames**, bei Cache-Hit *und* -Miss | ⚠️ siehe unten — existiert, überlebt aber nur Stunden |
| `diagnostics/openmeteo_calls.jsonl` (`src/providers/call_log.py:107`) | **dass** ein Abruf stattfand (Zähl-/Health-Signal) | keine Vorhersagewerte |
| Open-Meteo Previous-Runs-API | Vortagesstände in 24-h-Schritten | untertägige Revisionen nicht ableitbar (belegt in #2020: 59,8 mm passt weder zu 7,4 noch 29,4) |

**Zentraler Befund dieser Recherche:** Der Nowcast-Eingangsmitschnitt aus #1948 (Zweig c)
schreibt nach `<Datenwurzel>/debug/alert_input/nowcast/` und wird von
`alert_input_capture._prune` (`:41`) auf **50 Dateien pro Verzeichnis** begrenzt — und
`branch="nowcast"` ist für **alle** Orte identisch (`radar_service.py:728`), alle teilen sich
also dieselben 50 Plätze. Bei 96 Radar-Alarmläufen/Tag über ~14 Trips landet die
Aufbewahrung in der Größenordnung **einer knappen Stunde**. Für die Aufklärung eines
Vorfalls vom Vortag ist das strukturell wertlos. Die Lücke ist damit doppelt: der
Vorhersage-Verbrauch wird **gar nicht** aufgezeichnet, und das, was aufgezeichnet wird,
**überlebt nicht lang genug**.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/segment_weather.py:78` (`fetch_segment_weather`) | breitester gemeinsamer Verbrauchspunkt: speist Trip-Briefing, Trip-Alarm und Compare-Abweichungsalarm. Zwei Rückgabezweige — Cache-Hit `:148-151`, Miss `:197-232` — laufen beide durch `_aggregate_for_segment` (`:234`) |
| `src/services/radar_service.py:228/242/727` | Nowcast-Pfad, umgeht `segment_weather` und `OpenMeteoProvider._request` vollständig (eigener `httpx.Client`, `:467`) |
| `src/services/comparison_engine.py:394` → `src/services/forecast.py:85` | vierter Pfad: Ortsvergleichs-**Bericht**, ohne Cache und ohne `segment_weather` |
| `src/providers/call_log.py:28/86/107` | Vorbild für Writer, Laufzeit-Pfadauflösung (`diagnostics_path()`) und Quellenzuordnung (`resolve_call_source()`, `override_call_source()` als ContextVar) |
| `src/services/alert_input_capture.py:32/41/95` | Vorbild für Prune; zugleich die Stelle, deren Aufbewahrung für dieses Volumen zu knapp ist |
| `src/services/weather_cache.py:305` | TTL 600 s vor dem Provider — ein Mitschnitt am Netz-Abruf sähe nur Cache-Misses |
| `src/services/forecast_budget.py:40-42` | `DAILY_BUDGET = 9000`, Zähler `record_cache_hit/miss/call` — Basis für die Volumenrechnung |
| `src/app/loader.py:1114/1144` | `get_data_root()/diagnostics/` (global) bzw. `get_data_dir(uid)/diagnostics/` (pro Nutzer) |

## Existing Patterns

- **JSONL-Anhängen, fail-soft** — vier fast identische Kopien: `call_log.py:107`,
  `alert_briefing_anchor.py:58/110`, `enrichment_health.py:49`, `warn_egress.py:313`.
  `call_log.py` ist die vollständigste Vorlage.
- **Pfad bei jedem Zugriff auflösen, nie als Modulkonstante** — Pflicht aus
  `docs/specs/modules/fix_1633_datenwurzel_diagnose_journale.md`; eine Import-Zeit-Konstante
  zeigt an der Test-Isolation vorbei auf die echte Datenwurzel.
- **Aufbewahrung** existiert nur datei-anzahl-basiert und nirgends zeitbasiert:
  `weather_snapshot.py:182` (max 7, Glob nach Datums-Suffix), `alert_input_capture.py:41`
  (max 50). Eine Frist **in Tagen** gibt es im Repo noch nicht.
- **Konfiguration** läuft nicht über `config.ini`, sondern als Modulkonstante mit optionalem
  `GZ_*`-Override — sauberstes Vorbild `meteoalarm_budget.py:88-101`. Einen An/Aus-Schalter
  für ein Diagnose-Feature gibt es bisher nirgends; alle Journale schreiben bedingungslos.
- **Test-Isolation** über die autouse-Fixture `_isolate_data_root`
  (`tests/conftest.py:121-171`) — Schreiber, die über `get_data_root()` auflösen, sind ohne
  Monkeypatch isoliert; ein Wächter (`:158-171`) lässt den Test scheitern, wenn unter dem
  echten `data/users` etwas entsteht. Referenztest für beide Auflösungswege:
  `tests/unit/test_diagnostics_path_resolution.py:38-58/134-149`.

## Volumen — die eigentliche Entwurfsgrenze

Scheduler-Takte (`internal/scheduler/scheduler.go:188-207`): `alert_checks`,
`compare_alert_checks`, `compare_official_alert_checks` je `*/15` (96/Tag),
`radar_alert_checks` + `compare_radar_alert_checks` je 4×/h (96/Tag), `briefing_dispatch`
stündlich (24/Tag).

Ein bedingungsloser Mitschnitt an jedem Verbrauch ergäbe in Produktion (14 Trips,
19 Compare-Presets, 31 Orte laut `fix_1329_forecast_cache_budget.md`) grob
**10.000–15.000 Einträge/Tag** aus dem Trip-Pfad plus 3.000–9.000 aus dem Compare-Pfad und
1.300–3.000 aus dem Nowcast-Pfad. Das ist der Mehr-MB-Bereich pro Tag und die Größe, an der
sich Format, Filterung und Aufbewahrungsfrist entscheiden — nicht der Writer selbst.

## Dependencies

- **Upstream:** `app.loader.get_data_root()/get_data_dir()`, `WeatherCacheService`
  (`CachedForecast.cached_at` trägt den Original-Fetch-Zeitpunkt, nicht `now()`),
  `providers.call_log.resolve_call_source()`.
- **Downstream:** heute niemand — die Aufzeichnung ist reine Nachschlagequelle. Optional
  später ein Health-Feld in `/api/scheduler/status` (Muster
  `internal/scheduler/enrichment_health.go`), im schlanken Zuschnitt **nicht** enthalten.

## Existing Specs

| Spec | Bezug |
|---|---|
| `docs/specs/modules/fix_1633_datenwurzel_diagnose_journale.md` | verbindliche Pfadregel für Diagnose-Journale |
| `docs/specs/modules/alarm_eingangsprotokoll.md` | #1948-Spec zu `alert_input_capture` — der nächste Verwandte, AC-1..AC-9 |
| `docs/specs/modules/feat_1459_alert_protokoll.md` | `alert_log.py`, protokolliert ausdrücklich die Entscheidung, nicht den Eingang |
| `docs/specs/modules/fix_1329_forecast_cache_budget.md` | Cache + Tagesbudget, liefert die Prod-Größenordnungen |
| `docs/specs/modules/weather_snapshot.md` | persistierte Tagesstände als Vergleichsbasis; Retention-Vorlage |

Eine Spec zu einem Vorhersage-Mitschnitt existiert **nicht**.

## Relevante Entscheidungen (ADR)

- **ADR-0018 „Provider-Fallback ohne Kaschieren"** — Folgepflicht: *„Neue degradierbare
  Datenpfade müssen dieselbe Nicht-Kaschieren-Invariante erfüllen (Marker in Daten +
  wachsendes Health-Signal)."* Alle bestehenden Journale schreiben fail-soft mit
  `except: pass`. Für #2030 heißt das: ein **dauerhaft** scheiternder Mitschnitt darf nicht
  stumm bleiben, sonst steht man beim nächsten Vorfall wieder ohne Daten da — genau das
  Muster, das ADR-0018 verbietet.

## Risks & Considerations

1. **Volumen/Plattenplatz** — ohne Filter und Frist wächst die Aufzeichnung unbegrenzt;
   `alert_log.json` ist im Haus bereits das abschreckende Beispiel (kein Prune).
2. **Kein einziger Choke-Point** — 3–4 parallele Verbrauchspfade. Der Zuschnitt „welche
   Pfade" entscheidet über den halben Aufwand. Da der auslösende Vorfall (#2020) ein
   Regen-/Nowcast-Fall war, wäre ein Mitschnitt ohne Nowcast-Pfad für genau diese Frage
   blind.
3. **Cache-Blindheit** — ein Mount am Netz-Abruf (`openmeteo.py:628`) protokolliert nur
   Cache-Misses und damit nicht, was das System im Moment der Alarm-Entscheidung glaubte.
   Der Mitschnitt gehört an die Verbrauchsstelle, mit dem echten Alter des Werts.
4. **Heißer Pfad zwei Tage vor Tourstart** (23.08.) — der Einbaupunkt liegt in der Kette, an
   der Briefing *und* Alarm hängen. Fail-soft ist Pflicht; ein Fehler im Mitschnitt darf
   niemals ein Briefing kippen.
5. **Prune-Falle #1987** — Glob eng fassen, sonst löscht die Bereinigung Nachbardateien.
6. **Nicht in Prod nachmessbar** — die Produktiv-Datenwurzel liegt seit #1595 unter
   `/var/lib/gregor` (Nutzer `claude-gregor`), `sudo` im automatischen Modus gesperrt. Die
   Wirkung ist nur über Staging belegbar. `data/users/` im Checkout enthält Alt-/Testdaten
   (KHW-Trip dort heißt `khw-402` mit Etappen aus Mai 2024).
7. **Nachbarschaft** — #2018 (`alert_log.py`, Tests), #2020 und #1818 arbeiten in
   `trip_alert.py`/Ausgabe; keiner der laufenden Stränge berührt `segment_weather.py` oder
   den Writer. Kollisionsrisiko gering, aber vor dem Merge gegen `origin/main` prüfen.

## Abgrenzung

- **Nicht** Teil von #2020 (dort wurde die Reparatur vorgezogen).
- **Verwandt, aber eigenständig:** Lücke **O3** — von rund elf Unterdrückungsstufen
  protokollieren nur drei ihre Unterdrückung (`append_suppressed_entry`,
  `src/services/alert_log.py`). O3 betrifft *Entscheidungen*, #2030 die *Eingangsdaten*.
- **Nebenbefund → #1199:** Der Docstring von `append_suppressed_entry` behauptet, amtliche
  Warnungen würden nicht protokolliert; seit #1467 S4b-1 (`trip_alert.py:1855`) stimmt das
  nicht mehr.
