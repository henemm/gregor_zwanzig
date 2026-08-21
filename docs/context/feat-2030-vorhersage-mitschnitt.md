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

---

# Analysis

## Type

**Feature** — neue Diagnose-Fähigkeit, kein Fehlverhalten im Produkt.

## Der Zuschnitt-Entscheid: ein Einbaupunkt, nicht vier

`_aggregate_for_segment` (`src/services/segment_weather.py:234`) ist die einzige Stelle, die
**alle** relevanten Eigenschaften auf einmal hat:

- **Cache-Hit (`:148`) und Cache-Miss (`:232`) laufen beide hindurch.** Ein Mitschnitt am
  Netz-Abruf (`openmeteo.py:628`) sähe nur Misses und damit nicht, was das System im Moment
  der Alarm-Entscheidung glaubte.
- Sie deckt **alle vier alarm-/briefingrelevanten Konsumenten** ab: Trip-Δ-Alarm
  (`trip_alert.py:1602`), Compare-Abweichungsalarm (`compare_location_weather_source.py:174`),
  Briefing (`trip_report_scheduler.py:2026`, `stage_weather.py:56`).
- Sie hat **`fetched_at` bereits als Parameter** (`:236`): bei Cache-Treffer den echten
  Upstream-Abrufzeitpunkt (`weather_cache.py:56-63` — ausdrücklich nie `now()`), bei Miss den
  echten Abruf. „Wie alt war der Wert, als entschieden wurde" fällt damit ohne Zusatzlogik ab.

### Korrektur gegenüber der Kontext-Annahme: der Nowcast-Pfad gehört NICHT dazu

Die Kontext-Sektion vermutete, ein Mitschnitt ohne Nowcast-Pfad sei für den auslösenden
Vorfall blind. Das ist an den **Einheiten** widerlegt: die Zahlen aus #2020 (7,4 mm → 29,4 mm)
sind Vorhersage-**Tagessummen**, also `SegmentWeatherSummary.precip_sum_mm`
(`src/app/models.py:446`). Nowcast-Frames tragen `precip_mm_h` (`radar_service.py:733`) — eine
andere Größe. Der Vorfall war ein Regenfall, aber die unbeantwortbare Frage hängt am
Vorhersage-, nicht am Nowcast-Pfad.

Hinzu kommt: Der Nowcast-Pfad **hat** bereits einen Mitschnitt (`radar_service.py:228/242`).
Ihm fehlt nur die Aufbewahrung. Ein zweiter Writer dort wäre Doppelarbeit → eigene Mini-Scheibe
(siehe unten).

## Warum kein Umbau von `weather_snapshot`

Der Snapshot-Dienst hält pro Trip und **Zieltag genau eine** Datei
(`weather_snapshot.py:137`), geschlüsselt über das Zieldatum, nicht über den Schreibzeitpunkt —
der 15:30-Stand überschreibt den 05:00-Stand spurlos. Geschrieben wird nur beim Briefing (2×/Tag,
`trip_report_scheduler.py:1510`) und beim **zugestellten** Alarm (`trip_alert.py:905`). Die
15-Minuten-Alarmläufe, die den fraglichen Anstieg gesehen haben, schreiben nie. Zudem geht dort
die Wert-Frische verloren (`snapshot_at = now()`, `:101/:129/:252`).

Drei strukturelle Blocker also: überschreibendes Ein-Datei-Modell, Auslöser am Versand statt am
Verbrauch, Prune nach Dateizahl statt Alter. Dazu ein Risiko: `weather_snapshot` **ist** die
eingefrorene Alarm-Vergleichsbasis (ADR-0056, `trip_alert.py:678`; AC-11 in
`weather_snapshot.py:232-244`) — ein rollierender Schreibpfad darf sie nicht anfassen.
Wiederverwendet wird nur das **Prune-Muster** (`:182-200`), nicht der Dienst.

## Das Volumen-Problem und seine Lösung

Bedingungslos wären es ~15.000 Zeilen/Tag à ~530 B ≈ 5,5–8 MB/Tag. Regel stattdessen:

> **Schreiben, wenn sich die alarmrelevanten Werte gegenüber dem zuletzt geschriebenen Stand
> desselben Schlüssels geändert haben — ODER der letzte Eintrag für diesen Schlüssel älter als
> 60 Minuten ist.**

Der erzwungene Stunden-Takt löst die Mehrdeutigkeit, die reine Änderungserkennung erzeugt hätte:
Ohne ihn hieße „keine Zeile" *unverändert* ODER *Mitschnitt kaputt* ODER *nie abgerufen*. Mit ihm
ist eine Lücke > 60 min **eindeutig** ein Fehler oder ein nicht abgerufener Ort. Jede Zeile trägt
`grund: "aenderung" | "takt"`. Volumen danach: ~3.000–4.000 Zeilen/Tag ≈ 1 MB/Tag.

Zustandsspeicher ist ein prozessweites `dict` (Schlüssel → letzte Werte + Zeitstempel); zulässig,
weil der Python-Kern ein Langläufer ist (Präzedenz: `get_shared_weather_cache()`,
`weather_cache.py:305`). Nach einem Neustart schreibt jeder Schlüssel einmal — die gewünschte
Grundlinie.

## Identität eines Eintrags — bewusst ohne `trip_id`

`_aggregate_for_segment` bekommt **keine Trip-Kennung**, und das ist Absicht: der Docstring
(`segment_weather.py:245-251`, #1329 Adversary-Fund F001) hält ausdrücklich fest, dass „weder
Trip- noch Compare-Identität je in einen anderen Aufrufer sickert". Diese Trennung wird **nicht**
aufgebrochen.

| | Entscheidung |
|---|---|
| Dedup-Schlüssel | `lat_lon_startstunde` des Segmentfensters — analog `_nowcast_source_key` (`radar_service.py:719`), damit mit dem Nowcast-Mitschnitt korrelierbar |
| Zeile trägt zusätzlich | `segment_id`, Fensterzeiten, `day_window_*`, `provider`, `model`, `cache_hit` |
| Konsument | über `resolve_call_source()` (`call_log.py:87`) — sagt *welcher* Lauf (Briefing/Alarm/Compare) abgerufen hat, ohne Trip-Identität |

⚠️ **`resolve_call_source()` nutzt `inspect.stack()[:25]` (`call_log.py:100`) und ist teuer** —
darf erst **nach** bestandener Schreib-Prüfung aufgerufen werden, nie davor.

`segment_id` allein ist ein Laufindex (`trip_segments.py:230`, `i + 1`) und über Trips hinweg
nicht eindeutig — deshalb Beifeld, nicht Schlüssel. Wirklich stabile Kennungen (`Stage.id`,
`Waypoint.id`, `src/app/trip.py:72/97`) werden von `convert_trip_to_segments` nicht in
`TripSegment` übertragen; sie nachzurüsten berührt `models.py` (schema-relevant,
Snapshot-Hook) und ist **nicht** Teil dieser Scheibe. Folge: Verschiebt ein Nutzer einen
Wegpunkt, beginnt unter der neuen Koordinate eine neue Reihe — kein Datenverlust, nur eine
neue Grundlinie. Für einen verschobenen Punkt ist das fachlich korrekt.

## Ausfall-Sichtbarkeit (ADR-0018) — vier Zeilen, keine neue Infrastruktur

`internal/scheduler/enrichment_health.go:83-86` gruppiert nach `entry.Path` als **freiem
String**; ein neuer Pfad-Wert auf Python-Seite erscheint automatisch als eigener Schlüssel unter
`/api/scheduler/status.enrichment_health` — ausdrücklich zugesichert in
`src/providers/enrichment_health.py:22-25` (#1992 AC-8). Also: neue Konstante
`PATH_FORECAST_CAPTURE`, `log_enrichment_call(..., OUTCOME_OK)` nach Erfolg,
`OUTCOME_UNAVAILABLE` im `except`. **Gedrosselt auf ≤ 1×/15 min**, weil
`enrichment_calls.jsonl` bewusst keine Rotation hat und vom Go-Aggregator bei jedem
Status-Abruf komplett gescannt wird.

`check-gregor20.sh` bildet „jetzt − `last_success_at`" generisch — der Dauerausfall wird von
selbst wachsend sichtbar, ohne Schwellenentscheidung im Code.

Verworfen: Eintrag in `coreBriefingSources` (ADR-0018 schließt das aus, #1115 F002, Wächter-Test);
nur-bei-Fehler-Protokollieren (`last_success_at` bliebe für immer leer — genau der Kaschier-Modus,
den ADR-0018 verbietet); eigener Go-Endpunkt (teurer, kein Zusatznutzen).

Semantische Dehnung, offen benannt: `enrichment_health` war für degradierbare *Anreicherungs*-Pfade
gedacht. Vertretbar, weil #1992 die Erweiterbarkeit per neuem `path`-Wert ausdrücklich zusichert.

## Affected Files

| Datei | Art | Beschreibung |
|---|---|---|
| `src/services/forecast_capture.py` | CREATE | Writer, Dedup-/Takt-Regel, Tagesdatei, Prune, Kill-Switch (~105) |
| `src/services/segment_weather.py` | MODIFY | Aufruf am Ende von `_aggregate_for_segment`, eigenes `try/except` (~10) |
| `src/providers/enrichment_health.py` | MODIFY | Pfad-Konstante `forecast_capture` (~4) |
| `tests/unit/test_forecast_capture.py` | CREATE | Verhaltenstests (~105) |

## Scope Assessment

- Files: 2 CREATE, 2 MODIFY
- Geschätzte LoC: **~224 / 250** — passt ohne Override, aber ohne Reserve
- Risk Level: **MEDIUM** — heißer Pfad von Briefing *und* Alarm, zwei Tage vor Tourstart

## Zwingende Schutzmaßnahmen

| Risiko | Maßnahme |
|---|---|
| Mitschnitt kippt Briefing/Alarm | **Doppeltes `try/except`** — im Writer *und* an der Aufrufstelle (Muster `radar_service.py:727-741`; schützt zusätzlich gegen Importfehler) |
| Fehlverhalten in Prod ohne Deploy-Fenster | **Kill-Switch `GZ_FORECAST_CAPTURE=0` → No-Op**, Default an (Muster `meteoalarm_budget.py:88-101`). Einzige deploy-freie Rückzugsoption |
| An der Test-Isolation vorbei in echte Daten schreiben | Pfad bei **jedem** Aufruf über `get_data_root()` (#1633); Referenztest `tests/unit/test_diagnostics_path_resolution.py:38-58/134-149` |
| Prune löscht Nachbardateien | Enger Glob **plus** Datums-Regex (#1987, Vorbild `weather_snapshot.py:182-200`); Prune nur bei Datumswechsel, nicht bei jedem Schreiben |
| Zerrissene Zeilen (Schreiben aus `ThreadPoolExecutor`, `comparison_parallel.py:118`) | Zeilen < 4 KiB halten → nur Aggregat, **keine** Zeitreihe |
| `enrichment_calls.jsonl` wächst unrotiert | Health-Zeilen auf ≤ 1×/15 min drosseln |
| Plattenplatz | Tagesdatei + 30-Tage-Frist → obere Schranke strukturell, nicht per Disziplin |

## Aufbewahrung

**30 Tage**, Datei pro Tag: `<Datenwurzel>/diagnostics/forecast_capture_YYYY-MM-DD.jsonl`.
Tourdauer allein wäre zu knapp — die Aufklärung passiert nach der Tour (#2020 wurde am Folgetag
analysiert). Datei-pro-Tag statt In-Place-Rotation, weil Prune dann ein `unlink` ist statt eines
Read-Modify-Write der wachsenden Datei (`alert_log.py` ist das abschreckende Gegenbeispiel), weil
reines Anhängen ohne Sperre threadsicher bleibt und weil der Leser den Vorfallstag am Dateinamen
findet.

## Bekannte Grenzen (bewusst angenommen)

- Die frühen Rückgaben `segment_weather.py:160` (Budget-Drosselung) und `:207` (Provider-Fehler)
  laufen **nicht** durch `_aggregate_for_segment` und schreiben nichts. Beide Zustände sind
  anderswo protokolliert (`forecast_budget.py`-Zähler bzw. `call_log.py:107`). Drei Einbaupunkte
  im heißen Pfad wären ein schlechter Tausch.
- Keine Trip-Kennung in der Zeile (siehe oben) — Zuordnung über Koordinate + Zeitfenster.
- Kein Leser: kein Auswerte-Skript, kein Endpunkt, keine UI. Ausgewertet wird im Vorfall mit
  `grep`/`jq`.

## Abgetrennt: Nowcast-Aufbewahrung (eigene Mini-Scheibe, ~40 LoC)

`alert_input_capture._prune` (`:41`) begrenzt auf 50 Dateien **pro Branch-Verzeichnis**, und
`branch="nowcast"` ist für alle Orte gleich (`radar_service.py:728`) — faktische Aufbewahrung
rund eine Stunde. Fix: Prune **pro `source_key`** (Glob `f"{prefix}_*.json"`), und
`latest_capture_id` (`:136`) globt denselben Präfix statt `*.json` — der Lookup wird dabei sogar
schneller, weil er heute jede Datei im Verzeichnis liest. Aufbewahrung springt auf ~12 h pro Ort.

**Nicht** einfach `_MAX_FILES_PER_DIR` erhöhen: `latest_capture_id` liest jede Datei im
Verzeichnis: 50 → 2000 machte jeden Alarm-Check zu 2000 Lesevorgängen im heißen Pfad.

Getrennt, weil beides zusammen (~264 LoC) einen `loc_limit_override` erzwänge.

## Was NICHT in diese Scheibe gehört

Kein zweiter Nowcast-Writer · kein Mitschnitt am Ortsvergleichs-**Bericht**
(`comparison_engine.py:394` — daran hängt keine Alarmentscheidung) · keine Rohzeitreihe/Stundenwerte
· kein Leser/Endpunkt/UI · keine Go-Änderung · keine Nutzer-Skopierung (Systemablage wie
`call_log.py`) · keine Retention-Nachrüstung für `alert_log.py` · nicht Lücke **O3** · keine
Verallgemeinerung zu einem geteilten Journal-Framework · kein `config.ini`-Eintrag · keine
Rückrechnung aus der Previous-Runs-API.

## Open Questions

Keine offenen technischen Fragen. Der einzige PO-Punkt ist die Freigabe der Akzeptanzkriterien
in Phase 3.
