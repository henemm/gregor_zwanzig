---
entity_id: feat_2030_vorhersage_mitschnitt
type: feature
created: 2026-08-21
updated: 2026-08-21
status: draft
version: "1.0"
workflow: feat-2030-vorhersage-mitschnitt
tags: [observability, diagnostics, adr-0018, forecast]
---

<!-- Issue #2030 — PO-Entscheid 2026-08-21 aus der Analyse zu #2020, Milestone „Tour KHW 2026-08" -->

# Feature #2030 — Vorhersage-Mitschnitt am Verbrauchspunkt

## Approval

- [x] Approved — PO-„go" (Henning) 2026-08-21; die 12 Akzeptanzkriterien wurden auf Deutsch
      vorgelegt und freigegeben. Beleg als Kommentar an Issue #2030.

## Purpose

Bei #2020 war die Kernfrage „wann sprang die Vorhersage von 7,4 mm auf 29,4 mm?" mit keiner
im System vorhandenen Quelle beantwortbar — dadurch blieb unentscheidbar, ob die
Auslöseschwelle zu hoch stand oder die Vorhersage zu spät hochkam. Dieses Feature zeichnet
rollierend auf, **was das System zu einem gegebenen Zeitpunkt für welchen Ort und welches
Zeitfenster erwartete**, damit ein künftiger Vorfall dieser Art nach der Tour anhand von
Daten statt Vermutung aufklärbar ist. Zeitbezug: Tourstart Karnischer Höhenweg ist
2026-08-23 — die Lieferung liegt zwei Tage davor und muss den heißen Pfad von Briefing und
Alarm unangetastet lassen.

## Source

- **File:** `src/services/segment_weather.py` — Funktion `_aggregate_for_segment` (Zeile 234)
- **Identifier:** neue Datei `src/services/forecast_capture.py` (Writer, Dedup-/Takt-Regel,
  Prune, Kill-Switch)

Reiner Python-Core-Anteil (`src/services/`, `src/providers/`). Keine Go-Änderung, kein
Frontend-Anteil — `internal/scheduler/enrichment_health.go` gruppiert bereits generisch nach
`path` und braucht für einen neuen Pfad-Wert keine Anpassung.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.loader.get_data_root()` | intern | Kanonische, zur Laufzeit aufgelöste Datenwurzel (#1633) — nie Modulkonstante |
| `providers.call_log.resolve_call_source()` | intern | Ermittelt den aufrufenden Konsumenten (Briefing/Alarm/Compare) ohne Trip-Identität; teuer (`inspect.stack()`), daher erst nach bestandener Schreib-Prüfung |
| `providers.enrichment_health.log_enrichment_call()` | intern | Meldet Erfolg/Ausfall generisch nach `path` an `/api/scheduler/status` (ADR-0018) |
| `weather_cache.CachedForecast.cached_at` | intern | Trägt den echten Upstream-Abrufzeitpunkt eines Cache-Treffers, nie `now()` |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/services/forecast_capture.py` | CREATE | Writer, Dedup-/Takt-Regel (Änderung oder >60 Min), Tagesdatei-Append, 30-Tage-Prune, Kill-Switch `GZ_FORECAST_CAPTURE` |
| `src/services/segment_weather.py` | MODIFY | Aufruf des Mitschnitts am Ende von `_aggregate_for_segment`, eigenes `try/except` |
| `src/providers/enrichment_health.py` | MODIFY | Neue Pfad-Konstante `forecast_capture` |
| `tests/unit/test_forecast_capture.py` | CREATE | Verhaltenstests zu allen 12 Acceptance Criteria |

### Estimated Scope

- **LoC:** ~224 von 250 (kein `loc_limit_override` nötig, aber ohne Reserve)
- **Files:** 2 CREATE, 2 MODIFY
- **Effort:** medium — Risk Level MEDIUM, weil der Einbaupunkt im heißen Pfad von
  Trip-Briefing, Trip-Alarm und Compare-Abweichungsalarm liegt, zwei Tage vor Tourstart

## Implementation Details

**Einbaupunkt:** `_aggregate_for_segment` (`src/services/segment_weather.py:234`) ist die
einzige Stelle, die sowohl den Cache-Hit- als auch den Cache-Miss-Zweig durchläuft, alle vier
alarm-/briefingrelevanten Konsumenten abdeckt und bereits `fetched_at` als Parameter
mitführt.

**Dedup-/Takt-Regel** (löst das Volumenproblem: bedingungslos ~15.000 Zeilen/Tag, mit Regel
~3.000–4.000 Zeilen/Tag ≈ 1 MB/Tag): Es wird genau dann geschrieben, wenn sich mindestens
ein alarmrelevanter Wert gegenüber dem zuletzt geschriebenen Stand desselben
Dedup-Schlüssels geändert hat, **oder** wenn der letzte Eintrag für diesen Schlüssel älter
als 60 Minuten ist. Der erzwungene Takt macht eine fehlende Zeile eindeutig als Fehler oder
nicht abgerufenen Ort erkennbar — ohne ihn wäre „keine Zeile" mehrdeutig zwischen
unverändert, Mitschnitt kaputt und nie abgerufen. Jede Zeile trägt `grund: "aenderung" |
"takt"`.

**Dedup-Schlüssel:** `lat_lon_startstunde` des Segmentfensters, analog
`_nowcast_source_key` (`radar_service.py:719`) — damit mit dem bestehenden
Nowcast-Mitschnitt korrelierbar. Bewusst **keine** `trip_id` in der Zeile: der Docstring von
`_aggregate_for_segment` (#1329 Adversary-Fund F001) hält ausdrücklich fest, dass weder
Trip- noch Compare-Identität in einen anderen Aufrufer sickert; diese Trennung wird nicht
aufgebrochen.

**Zustandsspeicher:** prozessweites `dict` (Schlüssel → letzte Werte + Zeitstempel),
zulässig weil der Python-Kern ein Langläufer ist (Präzedenz `get_shared_weather_cache()`).
Nach einem Neustart schreibt jeder Schlüssel einmal — die gewünschte Grundlinie.

**Ablage:** `<Datenwurzel>/diagnostics/forecast_capture_YYYY-MM-DD.jsonl`, angehängt, eine
Datei pro Tag. Prune entfernt Tagesdateien älter als 30 Tage über engen Glob plus
Datums-Regex, ausgelöst nur beim Datumswechsel — nicht bei jedem Schreibvorgang, und ohne
Nachbardateien wie `openmeteo_calls.jsonl` zu berühren (#1987-Falle).

**Ausfall-Sichtbarkeit (ADR-0018):** neue Konstante `PATH_FORECAST_CAPTURE`,
`log_enrichment_call(..., OUTCOME_OK)` nach Erfolg, `OUTCOME_UNAVAILABLE` im
Fehlschlagfall, gedrosselt auf höchstens eine Meldung je 15 Minuten (weil
`enrichment_calls.jsonl` unrotiert bleibt und bei jedem Status-Abruf komplett gescannt
wird). `internal/scheduler/enrichment_health.go` gruppiert bereits generisch nach `path` als
freiem String — ein neuer Pfad-Wert erscheint automatisch unter
`/api/scheduler/status.enrichment_health`, keine Go-Änderung nötig.

**Fail-soft doppelt abgesichert:** ein `try/except` im Writer selbst und ein weiteres an der
Aufrufstelle in `_aggregate_for_segment` — schützt zusätzlich gegen Importfehler, Muster
`radar_service.py:727-741`.

**Kill-Switch:** `GZ_FORECAST_CAPTURE=0` deaktiviert Dateizugriff und Health-Eintrag
vollständig, Default ist eingeschaltet — einzige deploy-freie Rückzugsoption bei
Fehlverhalten in Produktion.

## Verworfene Alternativen

- **Umbau von `weather_snapshot`:** hält pro Trip und Zieltag genau eine Datei,
  geschlüsselt über das Zieldatum statt den Schreibzeitpunkt — der 15:30-Stand überschreibt
  den 05:00-Stand spurlos. Schreibt nur beim Briefing (2×/Tag) und beim zugestellten Alarm,
  die 15-Minuten-Alarmläufe schreiben nie. Zudem geht dort die Wert-Frische verloren
  (`snapshot_at = now()`). `weather_snapshot` ist zudem die eingefrorene
  Alarm-Vergleichsbasis (ADR-0056) und darf nicht angefasst werden.
- **Mitschnitt am Netz-Abruf statt an der Verbrauchsstelle:** ein Mount am Netz-Abruf sähe
  nur Cache-Misses und damit nicht, was das System im Moment der Alarm-Entscheidung
  tatsächlich glaubte.
- **Bedingungsloses Schreiben jedes Verbrauchs:** ergäbe ~15.000 Zeilen/Tag (5,5–8 MB/Tag)
  und wäre der Größenbereich, an dem Format, Filterung und Frist ohnehin hätten entschieden
  werden müssen — die Dedup-/Takt-Regel löst das strukturell statt per Disziplin.
- **Zweiter Writer für den Nowcast-Pfad:** der Nowcast-Pfad hat bereits einen Mitschnitt
  (`radar_service.py:228/242`), ihm fehlt nur die Aufbewahrung — das ist eine eigene,
  getrennte Mini-Scheibe (~40 LoC), kein Teil dieser Scheibe. Zusammen (~264 LoC) hätte
  einen `loc_limit_override` erzwungen. Zudem sind die Einheiten verschieden:
  `precip_sum_mm` (Vorhersage-Tagessumme) versus `precip_mm_h` (Nowcast) — der #2020-Vorfall
  hängt an der Vorhersage-, nicht der Nowcast-Größe.
- **Mitschnitt am Ortsvergleichs-Bericht** (`comparison_engine.py:394`): daran hängt keine
  Alarmentscheidung, also kein Mehrwert für den Zweck dieser Scheibe.
- **Eintrag in `coreBriefingSources`:** von ADR-0018 ausdrücklich ausgeschlossen (#1115 F002,
  Wächter-Test).
- **Nur-bei-Fehler-Protokollieren:** `last_success_at` bliebe für immer leer — genau der
  Kaschier-Modus, den ADR-0018 verbietet.

## Bekannte Grenzen

- Die frühen Rückgaben `segment_weather.py:160` (Budget-Drosselung) und `:207`
  (Provider-Fehler) laufen nicht durch `_aggregate_for_segment` und schreiben nichts — beide
  Zustände sind anderswo protokolliert (`forecast_budget.py`-Zähler bzw. `call_log.py:107`).
  Drei Einbaupunkte im heißen Pfad wären ein schlechter Tausch gewesen.
- Keine Trip-Kennung in der Zeile — Zuordnung erfolgt über Koordinate und Zeitfenster, nicht
  über Trip-Identität (bewusste Entscheidung, siehe Implementation Details).
- Kein Leser, kein Auswerte-Skript, kein Endpunkt, keine UI. Ausgewertet wird im Vorfall mit
  `grep`/`jq` direkt auf der Tagesdatei.

## Test Plan

Alle Tests in `tests/unit/test_forecast_capture.py`, benannt nach Verhalten statt
Issue-Nummer. Kein Mock-Theater: echte Dateien im isolierten Datenverzeichnis über die
autouse-Fixture `_isolate_data_root` (`tests/conftest.py:121-171`); keine
`assert "xyz" in file.read_text()`-Prüfung als alleiniger Verhaltensnachweis — geprüft wird
strukturiert geparste JSONL (Feldwerte, Zeilenzahl, Reihenfolge).

### Automated Tests (TDD RED)

- [ ] `test_change_writes_one_line_with_reason_aenderung` — GIVEN ein zuvor geschriebener
      Stand für einen Schlüssel WHEN ein neuer Verbrauch mit abweichendem alarmrelevantem
      Wert eintrifft THEN entsteht genau eine Zeile mit `grund: "aenderung"` (AC-1).
- [ ] `test_stale_entry_older_than_60min_writes_despite_unchanged_values` — GIVEN identische
      Werte, aber letzter Eintrag desselben Schlüssels älter als 60 Minuten WHEN erneut
      verbraucht wird THEN entsteht genau eine Zeile mit `grund: "takt"` (AC-2).
- [ ] `test_unchanged_and_fresh_writes_nothing` — GIVEN identische Werte und ein Eintrag
      jünger als 60 Minuten WHEN erneut verbraucht wird THEN entsteht keine Zeile (AC-3).
- [ ] `test_cache_hit_preserves_original_fetched_at` — GIVEN ein Cache-Treffer mit
      `cached_at` in der Vergangenheit WHEN eine Zeile geschrieben wird THEN trägt
      `fetched_at` den ursprünglichen Abrufzeitpunkt, nicht die aktuelle Uhrzeit, und
      `cache_hit` ist wahr (AC-4a).
- [ ] `test_cache_miss_records_fresh_fetch_and_cache_hit_false` — GIVEN ein frischer
      Provider-Abruf WHEN eine Zeile geschrieben wird THEN trägt `fetched_at` den echten
      Abrufzeitpunkt und `cache_hit` ist falsch (AC-4b).
- [ ] `test_line_is_appended_to_todays_daily_file` — GIVEN ein Schreibvorgang am aktuellen
      Datum WHEN die Zeile geschrieben wird THEN landet sie angehängt in
      `forecast_capture_YYYY-MM-DD.jsonl` des heutigen Tages, bestehende Zeilen bleiben
      erhalten (AC-5).
- [ ] `test_prune_removes_only_forecast_capture_files_older_than_30_days` — GIVEN
      Tagesdateien älter und jünger als 30 Tage sowie Nachbardateien wie
      `openmeteo_calls.jsonl` liegen im Verzeichnis WHEN ein Datumswechsel den Prune
      auslöst THEN werden ausschließlich zu alte `forecast_capture_*`-Dateien entfernt,
      Nachbardateien bleiben unangetastet (AC-6a).
- [ ] `test_prune_runs_only_on_date_change_not_every_write` — GIVEN mehrere Schreibvorgänge
      am selben Tag WHEN sie nacheinander erfolgen THEN wird die Prune-Logik nur einmal
      beim tatsächlichen Datumswechsel ausgelöst (AC-6b).
- [ ] `test_path_resolves_via_get_data_root_at_runtime` — GIVEN `GZ_DATA_DIR` bzw.
      `loader._DATA_ROOT` zeigen auf unterschiedliche temporäre Verzeichnisse WHEN der
      Writer aufgerufen wird THEN folgt der Schreibpfad in beiden Fällen der zur Laufzeit
      aufgelösten Datenwurzel, analog `tests/unit/test_diagnostics_path_resolution.py`
      (AC-7).
- [ ] `test_capture_failure_does_not_raise_and_forecast_result_unchanged` — GIVEN das
      Zielverzeichnis ist nicht beschreibbar WHEN `_aggregate_for_segment` aufgerufen wird
      THEN liefert die Funktion ihr reguläres Ergebnis zurück, ohne eine Ausnahme nach
      außen zu werfen (AC-8).
- [ ] `test_kill_switch_disables_capture_completely` — GIVEN `GZ_FORECAST_CAPTURE=0` WHEN
      ein Segment-Aggregat verbraucht wird THEN entsteht keine Datei und kein
      Health-Eintrag, das Wetterergebnis bleibt unverändert (AC-9).
- [ ] `test_success_and_failure_report_to_enrichment_health_throttled` — GIVEN
      aufeinanderfolgende Mitschnitt-Versuche innerhalb von 15 Minuten WHEN der erste
      erfolgreich ist und ein späterer fehlschlägt THEN wird jeweils höchstens eine
      Meldung je 15-Minuten-Fenster an `enrichment_health` mit Pfad `forecast_capture` und
      passendem Ausgang gemeldet (AC-10).
- [ ] `test_line_contains_required_fields_no_timeseries_no_trip_id_under_4kib` — GIVEN eine
      schreibwürdige Zeile WHEN sie aufgebaut wird THEN enthält sie Koordinaten,
      `segment_id`, Fensterzeiten, `day_window_*`, `provider`, `model`, `source`,
      `cache_hit` und die Aggregatwerte, aber keine Zeitreihe, keine Stundenwerte und keine
      Trip-Kennung, und die Zeile bleibt unter 4 KiB (AC-11).
- [ ] `test_resolve_call_source_called_only_after_write_decision` — GIVEN ein Verbrauch, der
      wegen unverändert-und-frisch keine Zeile auslöst WHEN die Prüfung abgeschlossen ist
      THEN wird `resolve_call_source()` nicht aufgerufen; erst im schreibwürdigen Fall wird
      es aufgerufen (AC-12).

## Acceptance Criteria

- **AC-1:** Given ein Segment-Aggregat wird über `_aggregate_for_segment` verbraucht
  When mindestens einer der alarmrelevanten Werte gegenüber dem zuletzt geschriebenen
  Stand desselben Dedup-Schlüssels (`lat_lon_startstunde`) abweicht
  Then wird genau eine Zeile mit `grund: "aenderung"` an die Tagesdatei angehängt.

- **AC-2:** Given die alarmrelevanten Werte sind identisch zum zuletzt geschriebenen Stand
  desselben Schlüssels, aber der letzte Eintrag für diesen Schlüssel liegt länger als
  60 Minuten zurück
  When der nächste Verbrauch desselben Schlüssels stattfindet
  Then wird genau eine Zeile mit `grund: "takt"` angehängt — dies macht eine fehlende
  Zeile eindeutig als Fehler oder nicht abgerufenen Ort erkennbar.

- **AC-3:** Given die alarmrelevanten Werte sind identisch zum zuletzt geschriebenen Stand
  desselben Schlüssels und der letzte Eintrag ist jünger als 60 Minuten
  When derselbe Schlüssel erneut verbraucht wird
  Then entsteht keine neue Zeile.

- **AC-4:** Given ein Wert kommt aus dem Zwischenspeicher (Cache-Treffer) bzw. wird frisch
  vom Provider abgerufen (Cache-Fehlschlag)
  When der jeweilige Verbrauch eine schreibwürdige Zeile auslöst
  Then trägt `fetched_at` in beiden Fällen den tatsächlichen Abrufzeitpunkt des Werts —
  beim Cache-Treffer den ursprünglichen Abrufzeitpunkt aus `CachedForecast.cached_at`
  (`weather_cache.py:56-63`), nicht die aktuelle Uhrzeit —, `written_at` den
  Verbrauchszeitpunkt, und `cache_hit` unterscheidet beide Fälle eindeutig.

- **AC-5:** Given ein Mitschnitt wird geschrieben
  When der Zielpfad aufgelöst wird
  Then landet die Zeile angehängt (append) in
  `<Datenwurzel>/diagnostics/forecast_capture_YYYY-MM-DD.jsonl` des aktuellen Tages,
  ohne dass eine bestehende Zeile überschrieben wird.

- **AC-6:** Given Tagesdateien liegen im `diagnostics`-Verzeichnis, darunter auch
  Nachbardateien wie `openmeteo_calls.jsonl` und `enrichment_calls.jsonl`
  When beim Wechsel des Kalendertags geprunt wird
  Then werden ausschließlich `forecast_capture_YYYY-MM-DD.jsonl`-Dateien älter als
  30 Tage entfernt (enger Glob plus Datums-Regex), Nachbardateien bleiben unangetastet,
  und der Prune-Lauf erfolgt nur beim Datumswechsel, nicht bei jedem Schreibvorgang.

- **AC-7:** Given `get_data_root()` löst über `GZ_DATA_DIR` oder die interne
  `loader._DATA_ROOT` unterschiedliche Verzeichnisse auf
  When der Mitschnitt-Writer auf beiden Wegen aufgerufen wird
  Then folgt der Schreibpfad in jedem Fall der zur Laufzeit aufgelösten Datenwurzel,
  nie einer beim Import gebundenen Modulkonstante — analog zum Referenztest
  `tests/unit/test_diagnostics_path_resolution.py`.

- **AC-8:** Given der Mitschnitt schlägt fehl — etwa weil das Zielverzeichnis nicht
  beschreibbar ist oder ein Importfehler auftritt
  When `_aggregate_for_segment` das Segment-Aggregat berechnet
  Then liefert die Wetterabfrage unverändert ihr Ergebnis zurück und wirft keine
  Ausnahme nach außen — abgesichert durch ein `try/except` im Writer UND ein weiteres
  an der Aufrufstelle.

- **AC-9:** Given die Umgebungsvariable `GZ_FORECAST_CAPTURE` ist auf `0` gesetzt
  When ein Segment-Aggregat verbraucht wird
  Then findet kein Dateizugriff und kein Health-Eintrag statt, und die Wetterabfrage
  liefert ihr Ergebnis unverändert; ohne gesetzte Variable ist der Mitschnitt aktiv
  (Default an).

- **AC-10:** Given ein Mitschnitt-Versuch findet statt
  When er erfolgreich war bzw. fehlschlägt
  Then meldet `log_enrichment_call` den Pfad `forecast_capture` mit Ausgang Erfolg bzw.
  „nicht verfügbar" an `enrichment_health`, gedrosselt auf höchstens eine Meldung je
  15 Minuten — Begründung: ADR-0018 verlangt ein wachsendes Health-Signal statt
  Kaschieren, und `internal/scheduler/enrichment_health.go` gruppiert bereits generisch
  nach `path`, sodass keine Go-Änderung nötig ist.

- **AC-11:** Given eine schreibwürdige Zeile entsteht
  When sie aufgebaut wird
  Then enthält sie Identität (Koordinaten, `segment_id`, Fensterzeiten, `day_window_*`),
  Herkunft (`provider`, `model`, `source`, `cache_hit`) und die alarmrelevanten
  Aggregatwerte, aber keine Zeitreihe, keine Stundenwerte und keine Trip-Kennung, und
  bleibt dabei unter 4 KiB — notwendig, weil aus mehreren Threads gleichzeitig
  angehängt wird (`comparison_parallel.py:118`).

- **AC-12:** Given die Dedup-/Takt-Prüfung eines Verbrauchs läuft
  When feststeht, ob eine Zeile geschrieben wird
  Then wird `resolve_call_source()` — das teure `inspect.stack()` nutzt — ausschließlich
  im schreibwürdigen Fall aufgerufen, nie vorher probehalber.

## Nicht in dieser Scheibe

- Kein zweiter Nowcast-Writer — die Aufbewahrung des bestehenden Nowcast-Mitschnitts
  (`alert_input_capture`) ist eine eigene, getrennte Mini-Scheibe (~40 LoC).
- Kein Mitschnitt am Ortsvergleichs-Bericht (`comparison_engine.py:394`).
- Keine Rohzeitreihe oder Stundenwerte in der Zeile.
- Kein Leser, kein Endpunkt, keine UI.
- Keine Go-Änderung.
- Keine Nutzer-Skopierung — Systemablage wie `call_log.py`, nicht `data/users/<user_id>/`.
- Keine Retention-Nachrüstung für `alert_log.py`.
- Nicht Lücke O3 (Protokollierung von Unterdrückungsstufen).
- Keine Verallgemeinerung zu einem geteilten Journal-Framework.
- Kein `config.ini`-Eintrag.
- Keine Rückrechnung aus der Open-Meteo Previous-Runs-API.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0018 (Provider-Fallback ohne Kaschieren)
- **Rationale:** ADR-0018 fordert für jeden neuen degradierbaren Datenpfad dieselbe
  Nicht-Kaschieren-Invariante (Marker in Daten + wachsendes Health-Signal). Der
  Mitschnitt selbst ist kein Provider-Fallback, aber er ist ein degradierbarer
  Diagnose-Pfad — ein dauerhaft scheiternder Mitschnitt darf nicht stumm bleiben, sonst
  steht man beim nächsten Vorfall wieder ohne Daten da. Die Umsetzung nutzt das
  bestehende, generische `enrichment_health`-Signal (#1992 AC-8) statt neuer
  Infrastruktur.

## Changelog

- 2026-08-21: Initial spec created
