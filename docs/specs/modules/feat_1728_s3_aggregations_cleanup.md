---
entity_id: feat_1728_s3_aggregations_cleanup
type: module
created: 2026-08-15
updated: 2026-08-15
status: draft
version: "1.0"
tags: [metrics, aggregations, cleanup, backend, frontend, api]
---

<!-- Issue #1728 Scheibe 3 — Entfernung des toten Feldes
     `MetricConfig.aggregations` aus Modell/Loader (Backend) und aus dem
     Trip-Editor-Speicherweg (Frontend), nachdem S1 (Backend-Ausgabeorte) und
     S2 (Editor-Bedienfläche) es bereits wirkungslos gemacht haben. -->

# Aufräum-Nachzug: `MetricConfig.aggregations` aus Modell/Loader/Editor-Payload entfernen

## Approval

- [x] Approved (2026-08-15, PO: „approved")

## 🔴 Korrektur gegenüber dem Kontext-Dokument (DEC-2 dort ist zu weitgehend)

Das Kontext-Dokument (`docs/context/feat-1728-s3-aggregations-cleanup.md`,
PO-Entscheid DEC-2, „Akzeptiert") verlangte, den **gesamten** API-Metadaten-
Cluster zu entfernen: `GET /api/metrics` → `"aggregations"`-Array,
`available_aggregations()` UND `pill_default_aggregations()`. Die Recherche
für diese Spec hat einen **echten, lebenden Verbraucher** dieses Arrays
gefunden, den die bisherige Analyse übersehen hat:

```
frontend/src/lib/components/shared/alarme-tab/tripAlertMetricsFromCatalog.ts:36
    for (const agg of entry?.aggregations ?? []) add(agg?.alert_metric);
```

Diese Funktion (`alertIdentitiesForMetricEntry`) wird von
`frontend/src/lib/components/trip-detail/AlarmeScheduleTab.svelte`
importiert — dem produktiven Alarme-Reiter des Trip-Editors (#1544/#1545,
#1435 E1a). Sie liest `MetricEntry.aggregations[].alert_metric`, um zu
bestimmen, welche Alarm-Zeilen zu einer aktivierten Wettergröße gehören.
Würde `"aggregations"` aus `GET /api/metrics` entfernt, verlöre der
Alarme-Reiter für jede Größe mit mehreren Auswertungen (Temperatur,
gefühlte Temperatur) ihre Alarm-Identitäten — ein echter Regress, den
`tests/unit/test_alert_metric_identity_delivery.py` sofort rot melden würde.

**Zwei verschiedene Konzepte, gleicher Feldname:**

| Feld | Bedeutung | Diese Scheibe |
|---|---|---|
| `MetricConfig.aggregations` (Modell, `models.py:613`) | **gespeicherter** Wert eines Trips — was S1/S2 abgeschaltet haben | **entfernen** (DEC-1) |
| `MetricEntry.aggregations` (Katalog-Metadaten, `GET /api/metrics`) | **Katalog-Angebot**: welche Auswertungen eine Größe überhaupt kennt, inkl. `alert_metric` je Auswertung | **bleibt unverändert** (DEC-3, korrigiert) |

**Einzige echte Leiche im API-Cluster:** `pill_default_aggregations()`
(`metric_catalog.py:914-921`) — verifiziert **null** Aufrufer in
`src/`, `api/`, `frontend/src`, `tests/`, `docs/` (nur ein Kommentarverweis
in der ohnehin zu löschenden `aggregationSelection.ts`). Diese Funktion wird
entfernt, `available_aggregations()` und der API-Key bleiben.

Die PO-Freigabe zu DEC-2 sollte bei der Spec-Freigabe explizit erneuert
werden — sie basiert jetzt auf einer anderen (kleineren) Änderung als im
Kontext-Dokument beschrieben.

## Purpose

S1 (`feat_1728_s1_temp_aufloesung`) und S2 (`feat_1728_s2_editor`) haben
`MetricConfig.aggregations` an jedem Ausgabeort und in der Bedienfläche
bereits wirkungslos gemacht — vier eigenständig wählbare Tagesrichtungs-
Größen ersetzen die alte Auswertungswahl. Diese Scheibe entfernt das jetzt
tote Feld aus Modell, Loader und Editor-Speicherweg, sowie eine tatsächlich
tote API-Katalogfunktion (`pill_default_aggregations()`). Issue #1728 bleibt
danach offen für #1848 (gemeinsames Vokabular Ortsvergleich/Ausblick).

## Source

Schicht: **Python-Core / Domain-Backend** (`src/app/`, `api/`) UND
**Frontend / User-UI** (`frontend/src/lib/components/shared/`,
`frontend/src/lib/components/trip-detail/`). Kein Go-API-Change.

### Backend

| File | Identifier | Change |
|---|---|---|
| `src/app/models.py:613` | `MetricConfig.aggregations: list[str]` | Feld entfernen |
| `src/app/loader.py:756-765` | `_DERIVED_METRIC_RULES` | die vier `required_agg`-Werte (`"min"`/`"max"` für `temperature_day_low/_high`, `wind_chill_day_low/_high`) auf `None` setzen — wie bei `temperature_night`/`wind_chill_night` bereits Praxis |
| `src/app/loader.py:768-798` | `_append_derived_metrics()` | `required_agg`-Zweig (`if required_agg is not None: ...`) entfernen — Ableitung nur noch über `enabled` |
| `src/app/loader.py:~830, ~906, ~955` (3×) | `_parse_display_config()` — global/`channel_layouts`/`channel_layouts_per_report` | je `aggregations=mc_data.get("aggregations", ["min", "max"])`-Zeile entfernen |
| `src/app/loader.py:975-1010` | `_migrate_weather_config()` (Alt-Migration `TripWeatherConfig`) | zwei `aggregations=...`-Zeilen entfernen |
| `src/app/loader.py:160` | `_metric_to_dict()` | `"aggregations": mc.aggregations`-Zeile entfernen |
| `src/app/metric_catalog.py:914-921` | `pill_default_aggregations()` | Funktion komplett entfernen (verifiziert 0 Aufrufer) |

**NICHT anfassen** (DEC-3, korrigiert): `api/routers/config.py:75,112-119`
(`"aggregations"`-Array in `GET /api/metrics`), `metric_catalog.py:901-911`
(`available_aggregations()`).

### Frontend

| File | Identifier | Change |
|---|---|---|
| `frontend/src/lib/types.ts:213-219` | `WeatherConfigMetric.aggregations?: string[]` | Feld entfernen |
| `frontend/src/lib/components/trip-detail/metricsEditor.ts:343,369` | `buildWeatherConfigMetrics(..., aggregationsMap)` | Parameter + Payload-Zeile entfernen |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | State `aggregationsMap` (`:234`), Dirty-Check/Snapshot (`:350,360,366,370`), Laden/Reset (`:434,451,827,844`), Payload-Aufrufe (`:858,883`) | State + alle 9 Referenzstellen entfernen |
| `frontend/src/lib/components/shared/weather-metrics-tab/aggregationSelection.ts` | komplette Datei (98 Zeilen) | löschen — letzter Aufrufer ist der `mode='single'`-Zweig in `AggregationMetricRow.svelte`, der mit dieser Scheibe entfällt |
| `frontend/src/lib/components/shared/weather-metrics-tab/AggregationMetricRow.svelte` | `mode='single'`-Zweig (`:49-51,66-77`), Props `choices`/`selectedChoiceId`/`onSelect`, Import `AggregationChoice` aus `aggregationSelection.ts` | entfernen; `mode='multiple'`-Zweig (`:78-93`) **unverändert** lassen |

**NICHT anfassen** (Korrektur DEC-3): `frontend/src/lib/types.ts:191-205`
(`MetricEntry.aggregations`, `AlertMetric`-Verweise) —
`tripAlertMetricsFromCatalog.ts`, `AlarmeScheduleTab.svelte`,
`activeAlertMetricsFromCatalog.ts` bleiben unverändert funktionsfähig.

> **Schicht-Hinweis beachtet:** Backend-Änderungen liegen ausschließlich in
> `src/app/`/`api/` (Python-Core), Frontend-Änderungen ausschließlich in
> `frontend/src/lib/components/{trip-detail,shared}/` (SvelteKit). Keine
> Go-API-Datei (`internal/`, `cmd/`) ist betroffen — `display_config` reist
> dort additiv als `map[string]interface{}` durch, ohne das Feld zu kennen.

## Estimated Scope

- **LoC produktiv:** grob −70/+10 (überwiegend Löschungen: totes Feld an
  6 Backend-Stellen, `pill_default_aggregations()` −8 Zeilen, Frontend-
  Plumbing `aggregationsMap` −9 Referenzstellen, `aggregationSelection.ts`
  −98 Zeilen als Löschung, `AggregationMetricRow.svelte` `mode='single'`
  −~20 Zeilen) — Budget 250, unkritisch
- **Files produktiv:** 4 Backend (`models.py`, `loader.py`,
  `metric_catalog.py`; `api/routers/config.py` **unberührt**, s. Korrektur),
  3 Frontend modifiziert (`types.ts`, `metricsEditor.ts`,
  `WeatherMetricsTab.svelte`, `AggregationMetricRow.svelte` — 4), 1 Frontend
  gelöscht (`aggregationSelection.ts`)
- **Test-LoC:** realistisch ~150–250 (Budget 500, kein Override erwartet) —
  überwiegend mechanische Entfernung von `aggregations=`-Kwargs, zwei Dateien
  mit echter Verhaltensänderung (s.u.), zwei Löschungen
- **Test-Files:** ~17 Python (Liste unten), 2 Frontend (1 gelöscht, 1
  Regressionsblock entfernt), 1 Doku
- **Effort:** medium — Backend-Reihenfolge ist strikt (Ableitung entkoppeln
  VOR Feldentfernung), Testfläche ist größer als im Kontext-Dokument
  geschätzt (dort „~11", real ~17, s. Testlage unten)
- **Risk Level:** MEDIUM — kein kritischer Pfad/Auth, aber zwei akzeptierte
  Verhaltensänderungen (DEC-1-Folge) und eine im Kontext-Dokument falsch
  eingeschätzte API-Abhängigkeit (korrigiert, s.o.)

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `feat_1728_s1_temp_aufloesung` | Spec | liefert `_DERIVED_METRIC_RULES`, die vier neuen Katalog-IDs — Voraussetzung dieser Scheibe |
| `feat_1728_s2_editor` | Spec | DEC-3 dort: `aggregationsMap` bleibt „bis Scheibe 3" im State — genau das löst diese Scheibe ein; DEC-2 dort: `AggregationMetricRow.svelte` bleibt unangetastet — diese Scheibe hebt das für `mode='single'` gezielt auf |
| Reihenfolge intern | — | Schritt „Ableitungsregel entkoppeln" (`_DERIVED_METRIC_RULES`) MUSS vor „Feld entfernen" (`models.py`) passieren — sonst `AttributeError` in `_append_derived_metrics()` |
| #1848 | — | KEINE Abhängigkeit — betrifft Compare/Ausblick-Vokabular, hier unberührt |

## Implementation Details

### DEC-1 — Ableitungsregel zuerst entkoppeln (Reihenfolge-Pflicht)

`_DERIVED_METRIC_RULES` (`loader.py:756-765`) wird von

```python
("temperature_day_low", "temperature", "min"),
("temperature_day_high", "temperature", "max"),
("wind_chill_day_low", "wind_chill", "min"),
("wind_chill_day_high", "wind_chill", "max"),
```

auf `required_agg=None` für alle vier reduziert (identisch zu
`temperature_night`/`wind_chill_night`, die das schon so haben). Der
`if required_agg is not None: ...`-Zweig in `_append_derived_metrics()`
(`loader.py:791-794`, liest `mc.aggregations`) wird entfernt — Ableitung
läuft danach ausschließlich über `mc.enabled` des Elternteils.

**Akzeptierte Verhaltensänderung (PO-bestätigt im Kontext-Dokument):**
`gr221-mallorca.json` (`wind_chill: ["min"]`, keine expliziten Einträge für
`wind_chill_day_low`/`_high`) bekommt `wind_chill_day_high` künftig als
`enabled=True` abgeleitet statt `False` — bis der Trip einmal über den
S2-Editor gespeichert wird (dort direkt und einzeln abwählbar).

### DEC-2 — Feld aus Modell/Loader entfernen (erst NACH DEC-1)

`MetricConfig.aggregations` aus `models.py` entfernen. In `loader.py`: die
drei `aggregations=mc_data.get("aggregations", ["min", "max"])`-Zeilen in
`_parse_display_config()` (global, `channel_layouts`,
`channel_layouts_per_report`), die zwei `aggregations=...`-Zeilen in der
Alt-Migration `_migrate_weather_config()`, und die
`"aggregations": mc.aggregations`-Zeile in `_metric_to_dict()` (Serialisierung)
entfernen.

**Kompatibilität:** eine alte JSON-Datei mit gespeichertem `"aggregations"`-
Key pro Metrik lädt weiterhin ohne Fehler (Key wird beim Parsen schlicht nie
gelesen — Read-Modify-Write-Grundsatz, überzählige Keys werden ignoriert).
Beim nächsten Speichern verschwindet der Key aus der Datei — das ist
gewolltes Verhalten der Feldentfernung, kein Merge-Verstoß (das Feld wird
bewusst abgeschafft, nicht versehentlich verworfen).

### DEC-3 (korrigiert) — Nur `pill_default_aggregations()` aus dem API-Cluster entfernen

S. Korrektur-Abschnitt oben. `available_aggregations()` und der
`"aggregations"`-Key in `GET /api/metrics` bleiben unverändert — sie
versorgen `tripAlertMetricsFromCatalog.ts` (Alarme-Reiter, Trip) live.

### DEC-4 — `WeatherConfigMetric.aggregations?` (Frontend-Typ) entfernen

`frontend/src/lib/types.ts:213-219` — das per-Trip gespeicherte Feld
(unterscheidet sich von `MetricEntry.aggregations`, DEC-3). Entfernen macht
`buildWeatherConfigMetrics()`s Rückgabetyp automatisch enger.

### DEC-5 — `metricsEditor.ts`: `aggregationsMap`-Parameter entfernen

`buildWeatherConfigMetrics(buckets, friendlyMap, horizonsMap, catalog,
aggregationsMap = {})` verliert den fünften Parameter; die Zeile
`...(aggregationsMap[id] !== undefined ? { aggregations: [...] } : {})` im
`emit()`-Helper entfällt. Bestandsaufrufer mit nur 4 Argumenten (die Mehrheit,
s. `metricsEditor.test.ts`) bleiben unverändert lauffähig.

### DEC-6 — `WeatherMetricsTab.svelte`: `aggregationsMap`-State entfernen

S2 hat den `onSelect`-Callback (die einzige Schreibstelle) mit dem
05-Block schon entfernt (DEC-7 der S2-Spec) — `aggregationsMap` selbst blieb
laut DEC-3 der S2-Spec bewusst als reiner Round-Trip-Ballast stehen. Diese
Scheibe entfernt jetzt: State-Deklaration (`$state`), die zwei Vorkommen im
Dirty-Vergleich/Snapshot-Objekt, die zwei Vorkommen beim Laden/Reset
(`snap.aggregationsMap` / `{}`), und die zwei Aufrufe von
`buildWeatherConfigMetrics(..., aggregationsMap)` (auf 4 Argumente kürzen).

### DEC-7 — `aggregationSelection.ts` löschen

98 Zeilen, letzter verbliebener Aufrufer ist der `mode='single'`-Zweig in
`AggregationMetricRow.svelte` (Typ-Import `AggregationChoice`) — der entfällt
mit DEC-8. Kein anderer Aufrufer im Repo (verifiziert).

### DEC-8 — `AggregationMetricRow.svelte`: `mode='single'`-Zweig entfernen

Entfernt: `{#if mode === 'single'} ... {:else}`-Verzweigung (nur der
`{:else}`-Zweig, also `mode='multiple'`, bleibt als einzige Form stehen),
Props `choices`, `selectedChoiceId`, `onSelect`, den Typ-Import aus
`aggregationSelection.ts`. **Unverändert:** der `mode='multiple'`-Zweig
selbst, `options`/`selectedChoiceIds`/`onToggle`/`testidPrefix` — diese
versorgen weiterhin die Compare-Grundauswahl (`WeatherMetricsTab.svelte:1308`)
und `CompareOutlookLayoutControls.svelte:161-164`.

### DEC-9 — Testlage (größer als im Kontext-Dokument geschätzt)

Das Kontext-Dokument nennt „~11 Python-Testdateien" — dieser Wert stammt aus
einem Grep auf `aggregations=` (mit Gleichheitszeichen) und übersieht Dateien,
die das Feld über `dict`-Fixtures (`"aggregations": [...]`) oder
`**kwargs`-Entpackung setzen. Reale Liste (per
`grep -rln 'MetricConfig(' tests/ --include='*.py' | xargs grep -l 'aggregations'`
nachvollziehbar, plus zwei API-seitige Treffer):

**Mechanisch anpassen** (nur die `aggregations=...`/`"aggregations": ...`-
Angabe entfernen, keine Assertion ändert ihren Sinn):

- `tests/integration/test_friendly_format_email_and_alerts.py`
- `tests/integration/test_compact_summary.py`
- `tests/integration/test_config_persistence.py` (9 Stellen, liest
  `mc.aggregations` beim Re-Serialisieren — Attribut existiert nach DEC-2
  nicht mehr)
- `tests/tdd/test_bug_801_803_mail_segmente_vortag.py`
- `tests/integration/test_friendly_format_and_alerts_config.py`
- `tests/tdd/test_reports_pro_typ.py`
- `tests/tdd/test_briefing_mail_inhalt.py`
- `tests/tdd/test_compact_summary_arrival_hour.py`
- `tests/red/test_issue_435_format_modes.py`
- `tests/unit/test_trip_summary_text.py`
- `tests/unit/test_weather_metrics_ux.py`
- `tests/tdd/test_temp_tagesrichtung_aufloesung.py` — `_dc()`-Helper
  (`aggs`-Parameter, `**({"aggregations": ...})`-Entpackung, Zeilen ~49-56)
  und die vier Aufrufstellen mit `aggs={...}` (Zeilen ~194,265) entfernen;
  die Assertions selbst (Span erscheint trotzdem) ändern sich **nicht** —
  die Tests bewiesen ohnehin, dass der Renderer das Feld schon ignoriert
  (S1). **Ausnahme in derselben Datei:**
  `TestApiMetricsExposesDayDirections::test_all_four_appear_with_empty_aggregations`
  bleibt wegen der DEC-3-Korrektur **komplett unverändert** — nicht anfassen.
- `tests/tdd/test_legacy_flat_metrics_load.py::test_dict_metrics_roundtrip_field_identical`
  — `"aggregations"`-Key aus den zwei Fixture-dicts UND aus dem
  `fields`-Tupel (Zeile ~160) entfernen
- `tests/test_compare_channel_layouts_migration.py`
- `tests/tdd/test_bug_805_789_roundtrip.py`
- `tests/tdd/test_issue_629_format_reduktion.py` (inkl. `mc.aggregations ==
  ["avg"]`-Assertion und `a.aggregations == b.aggregations`-Vergleich)
- `tests/tdd/test_issue_360_channel_renderer.py` (inkl. `mc.aggregations ==
  o.aggregations`-Vergleich)

**Löschen** (Prüfling ist exakt das jetzt entfernte Feld):

- `tests/test_metric_config_aggregations_roundtrip.py` (145 Zeilen, Docstring
  bestätigt selbst: prüft ausschließlich, dass `MetricConfig.aggregations`
  den Persistenzpfad übersteht — Prüfling verschwindet mit DEC-2)

**Verhaltensändernd** (Assertions kehren sich um, kein reines Mechanik-Delta):

- `tests/tdd/test_temp_tagesrichtung_bestandsableitung.py`:
  - `TestLoaderDerivesDayDirectionsFromParent::test_stored_min_only_yields_k_without_d`
    (bisher AC-8: `temperature: {aggregations:["min"]}` → D bleibt AUS) —
    Assertion dreht sich um: D ist jetzt AN (DEC-1-Folge), Docstring/Name
    anpassen (z.B. `test_stored_min_only_still_yields_both_now` o.ä.)
  - `TestRealLegacyTripKeepsItsTokens::test_gr221_mallorca_keeps_k_d_fk_and_loses_only_fd`
    (bisher AC-11: FD fehlt) — FD erscheint jetzt, erwartete Token-Menge wird
    um `FD` erweitert, Docstring/Testname anpassen
  - `TestRoundtripDoesNotMaterializeDerivedEntries::test_load_save_keeps_file_free_of_derived_ids`
    (AC-10) — der Feld-für-Feld-Vergleich `(gesp["enabled"],
    gesp["aggregations"]) == (eintrag["enabled"], eintrag["aggregations"])`
    muss auf `enabled` beschränkt werden; zusätzlich prüfen, dass
    `"aggregations"` im **gespeicherten** Ergebnis für JEDE Metrik fehlt
    (das Feld verlässt den Datenbestand beim nächsten Speichern endgültig —
    das ist die gewollte Wirkung von DEC-2, keine Regression)
  - `TestLoaderDerivesDayDirectionsFromParent::test_stored_default_keeps_both_felt_directions`
    (AC-9) und `TestCascadeKeepsDerivedDayDirections::*` (AC-13, beide
    Ebenen) bleiben **unverändert grün** — sie nutzen den Default
    (`["min","max"]`), dessen Ergebnis ändert sich durch DEC-1 nicht

**Frontend:**

- `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/buildWeatherConfigMetricsAggregations.test.ts`
  — löschen (der geprüfte Passthrough existiert nach DEC-5 nicht mehr;
  S2-DEC-4 kündigte diese Löschung bereits für „Scheibe 3" an)
- `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/aggregation_row_multi_select.test.ts`
  — NUR den Block „Regressionsschutz Trip (mode='single' bleibt bitidentisch)"
  (Zeilen ~130-164, importiert `aggregationChoices`/`choiceAggregations`/
  `defaultAggregations`/`selectedChoiceId` aus dem zu löschenden
  `aggregationSelection.ts`) entfernen. Die beiden Describe-Blöcke „AC-2"/
  „AC-3" (Zeilen 1-128, `compareAggregationGrouping`/`mode='multiple'`)
  **unverändert lassen**.

**Explizit NICHT anfassen** (DEC-3-Korrektur — im Kontext-Dokument fälschlich
als betroffen erwartet):

- `tests/unit/test_alert_metric_identity_delivery.py`
- `frontend/src/lib/components/shared/alarme-tab/__tests__/alert_identities_from_metric_entry.test.ts`
- `frontend/src/lib/components/shared/alarme-tab/__tests__/trip_active_alert_metrics_derivation.test.ts`
- `frontend/src/lib/components/shared/alarme-tab/__tests__/alarme_delivery_payload_preserves_inactive_levels.test.ts`

### DEC-10 — Doku-Nebenbefund #1856 E7 mitziehen

`docs/reference/metric_output_matrix.md`:
- Zeile 107: `_NIGHT_SCALAR_IDS` → `VISIBILITY_GATE_IDS`, zusätzlich die
  veraltete Referenz `channel_layout.py:88` → `channel_layout.py:75`
  (aktuelle Fundstelle von `VISIBILITY_GATE_IDS`)
- Zeile 366: `_NIGHT_SCALAR_IDS` → `VISIBILITY_GATE_IDS`

## Expected Behavior

- **Input:** ein Bestandstrip mit oder ohne gespeichertes `aggregations`-Feld
  je Metrik (Backend); ein Trip-Editor-Speichervorgang (Frontend).
- **Output:** Backend leitet die vier Tagesrichtungs-Größen ausschließlich
  über `enabled` des Elternteils ab (kein `aggregations`-Filter mehr);
  gespeicherte Trips verlieren das `aggregations`-Feld beim nächsten
  Speichern; `GET /api/metrics` liefert unverändert Katalog-Metadaten
  inklusive `aggregations[].alert_metric`; der Trip-Editor-Payload enthält
  kein `aggregations`-Feld je Metrik mehr.
- **Side effects:** ein bekannter, PO-akzeptierter Verhaltenswechsel für
  `gr221-mallorca.json` (`wind_chill_day_high` künftig aktiviert abgeleitet,
  s. DEC-1). Keine Wirkung auf den Alarme-Reiter (DEC-3-Korrektur).

## Acceptance Criteria

- **AC-1:** Given eine JSON-Trip-Datei mit einem veralteten `"aggregations"`-Key an einer Metrik (Bestandsdatei vor dieser Scheibe gespeichert) / When der Trip geladen wird / Then lädt er ohne Fehler — der Key wird beim Parsen ignoriert, kein `AttributeError`, kein Datenverlust an anderen Feldern.
  - Test: bestehender Lade-Test mit alter Fixture (z.B. `test_legacy_flat_metrics_load.py`) bleibt grün; ergänzend ein Kompatibilitäts-Check in `tests/integration/test_config_persistence.py`.

- **AC-2:** Given ein Bestandstrip mit `wind_chill: {enabled: true, aggregations: ["min"]}` (jetzt ignoriert) ohne eigene Tagesrichtungs-Einträge / When der Trip geladen wird / Then wird `wind_chill_day_high` als `enabled=True` abgeleitet (DEC-1: nur noch `enabled` des Elternteils zählt) — akzeptierte, dokumentierte Verhaltensänderung gegenüber S1.
  - Test: `tests/tdd/test_temp_tagesrichtung_bestandsableitung.py::TestLoaderDerivesDayDirectionsFromParent::test_stored_min_only_yields_k_without_d` (Assertions umgekehrt, D erscheint jetzt) und `::TestRealLegacyTripKeepsItsTokens::test_gr221_mallorca_keeps_k_d_fk_and_loses_only_fd` (FD erscheint jetzt in der Token-Menge).

- **AC-3:** Given die globale Metrik-Ebene mit `temperature: {enabled: true}` ohne expliziten `aggregations`-Eintrag (16 von 17 Bestandstrips, Default-Fall) / When geladen wird / Then bleiben `temperature_day_low` UND `temperature_day_high` weiterhin beide `enabled=True` (Regressionsschutz, Ergebnis unverändert durch DEC-1).
  - Test: `test_temp_tagesrichtung_bestandsableitung.py::TestLoaderDerivesDayDirectionsFromParent::test_stored_default_keeps_both_felt_directions` bleibt unverändert grün.

- **AC-4:** Given die Kanal-Ebene `channel_layouts.sms` eines Bestandstrips ohne die vier neuen IDs / When der SMS-Kanal geladen wird / Then bleiben die abgeleiteten Tagesrichtungen weiterhin im SMS-Schnitt erhalten (Regressionsschutz DEC-6b/ADR-0050, Ergebnis unverändert durch DEC-1).
  - Test: `test_temp_tagesrichtung_bestandsableitung.py::TestCascadeKeepsDerivedDayDirections::test_sms_channel_layout_without_new_ids_keeps_them` bleibt unverändert grün.

- **AC-5:** Given die Ebene `channel_layouts_per_report` eines Bestandstrips ohne die vier neuen IDs / When ein Report-Typ mit Sonderlayout geladen wird / Then bleiben die abgeleiteten Tagesrichtungen erhalten (dieselbe Ableitungsfunktion, dritte Ebene, Ergebnis unverändert durch DEC-1).
  - Test: `test_temp_tagesrichtung_bestandsableitung.py::TestCascadeKeepsDerivedDayDirections::test_per_report_layout_without_new_ids_keeps_them` bleibt unverändert grün.

- **AC-6:** Given ein Trip mit gespeicherten `aggregations`-Werten pro Metrik / When er geladen und unverändert wieder gespeichert wird (Roundtrip) / Then bleiben `enabled`, `bucket`, `order` und alle anderen Felder bit-identisch erhalten, UND die gespeicherte Datei enthält für keine Metrik mehr einen `"aggregations"`-Key (das Feld verlässt den Datenbestand beim ersten Speichern nach dieser Scheibe, kein Merge-Verstoß da bewusst abgeschafft).
  - Test: `test_temp_tagesrichtung_bestandsableitung.py::TestRoundtripDoesNotMaterializeDerivedEntries::test_load_save_keeps_file_free_of_derived_ids` (AC-10 dort), Vergleich auf `enabled` beschränkt plus neue Zusicherung „`aggregations` fehlt im gespeicherten Ergebnis".

- **AC-7:** Given `GET /api/metrics` / When die Antwort nach dieser Scheibe geprüft wird / Then liefert jede Metrik weiterhin ihr `aggregations`-Array mit `alert_metric` je Auswertung (UNVERÄNDERT, DEC-3-Korrektur) — NUR `pill_default_aggregations()` existiert nicht mehr in `metric_catalog.py` (repo-weit kein Aufrufer/Import mehr).
  - Test: `tests/unit/test_alert_metric_identity_delivery.py` (alle drei Tests) bleibt unverändert grün; `test_temp_tagesrichtung_aufloesung.py::TestApiMetricsExposesDayDirections::test_all_four_appear_with_empty_aggregations` bleibt unverändert grün; Python-Import `from app.metric_catalog import pill_default_aggregations` schlägt nach der Änderung fehl (`ImportError`).

- **AC-8:** Given `buildWeatherConfigMetrics(buckets, friendlyMap, horizonsMap, catalog)` ohne fünften Parameter (Signatur nach DEC-5 verkürzt) / When ein Metrik-Objekt für den Payload gebaut wird / Then enthält das Ergebnis-Objekt kein `aggregations`-Feld mehr, für keinen Bucket-Zustand.
  - Test: `frontend/src/lib/components/trip-detail/metricsEditor.test.ts` (bestehende `AC-7`/`AC-4`-Fälle, rufen bereits mit 4 Argumenten auf) bleibt unverändert grün; `buildWeatherConfigMetricsAggregations.test.ts` wird gelöscht (Prüfling entfällt).

- **AC-9:** Given der Trip-Editor (`WeatherMetricsTab.svelte`, `context='route'`) / When ein Trip gespeichert wird / Then referenziert der Quelltext keinen `aggregationsMap`-State mehr (Deklaration, Snapshot/Dirty-Check, Laden/Reset, Payload-Aufrufe — alle 9 Stellen entfernt), und `svelte-check` (CI-Pflicht-Check) meldet keinen Fehler durch eine verwaiste Referenz.
  - Test: `svelte-check` (bestehender CI-Check) grün; bestehende Editor-Speicher-Playwright-Specs (Regressionsschutz) bleiben grün.

- **AC-10:** Given der Ortsvergleich-Editor (Compare-Grundauswahl „02") und der 3-Tages-Ausblick (`CompareOutlookLayoutControls.svelte:161-164`) / When `AggregationMetricRow` dort mit `mode='multiple'` gerendert wird, nachdem `mode='single'` aus derselben Komponente entfernt wurde / Then funktionieren beide Aufrufer unverändert (Checkboxen unabhängig an-/abwählbar, identische Testids).
  - Test: `aggregation_row_multi_select.test.ts` (Describe-Blöcke „AC-2"/„AC-3", `mode='multiple'`) bleibt unverändert grün; `compareAggregationGrouping.test.ts` bleibt unverändert grün — reiner Nichtberühr-Nachweis.

- **AC-11:** Given `aggregationSelection.ts` wird gelöscht (kein Produktiv-Aufrufer mehr nach DEC-8) / When die Testsuite läuft / Then importiert keine verbliebene Testdatei diese Datei mehr — der Block „Regressionsschutz Trip (mode='single')" in `aggregation_row_multi_select.test.ts` ist ersatzlos entfernt, die restlichen Describe-Blöcke derselben Datei laufen unverändert grün.
  - Test: `aggregation_row_multi_select.test.ts` nach der Änderung; `grep -rn "aggregationSelection" frontend/src frontend/e2e` findet nach der Änderung keine Datei mehr außer der gelöschten selbst (leeres Ergebnis).

- **AC-12:** Given `docs/reference/metric_output_matrix.md` Zeilen 107 und 366 (veralteter Name `_NIGHT_SCALAR_IDS`, Zeile 107 zusätzlich veraltete Referenz `channel_layout.py:88`) / When die Datei nach dieser Scheibe geprüft wird / Then steht dort durchgängig `VISIBILITY_GATE_IDS` mit der aktuellen Fundstelle `channel_layout.py:75`.
  - Test: reine Dokupflege, kein funktionaler Test — Sichtprüfung im PR-Review (Nebenbefund-Triage, keine eigene Ratsche nötig für zwei Zeilen).

- **AC-13:** Given der Alarme-Reiter des Trip-Editors (`AlarmeScheduleTab.svelte` → `tripAlertMetricsFromCatalog.ts`) / When eine Wettergröße mit mehreren Auswertungen (z.B. Temperatur) aktiviert ist / Then zeigt der Reiter weiterhin alle zugehörigen Alarm-Identitäten (`temperature_min`, `temperature_max`, `temperature_change`) — UNVERÄNDERT durch diese Scheibe (DEC-3-Korrektur, expliziter Nichtregressions-Nachweis für den größten Risikopunkt dieser Spec).
  - Test: `frontend/src/lib/components/shared/alarme-tab/__tests__/alert_identities_from_metric_entry.test.ts` und `trip_active_alert_metrics_derivation.test.ts` bleiben unverändert grün.

## Known Limitations

- **Zwei-Nutzer-Test nicht erforderlich:** diese Scheibe berührt keinen neuen
  oder geänderten datenbewegenden Endpoint — reine Feldentfernung auf einem
  bestehenden Lade-/Speicherpfad, der bereits mandantenfähig ist (kein
  Cross-User-Risiko neu geschaffen).
- **`test_temp_tagesrichtung_aufloesung.py::TestApiMetricsExposesDayDirections`
  bleibt unverändert**, obwohl derselbe Datei-Name in mehreren anderen
  Klassen mechanisch angepasst wird — Verwechslungsgefahr für die
  Umsetzung, deshalb im DEC-9-Abschnitt explizit als Ausnahme benannt.
- **`available_aggregations()`/`GET /api/metrics`-Array bleiben dauerhaft
  bestehen**, auch wenn ihr ursprünglicher Zweck (Auswertungswahl im
  Trip-Editor) mit S1/S2 entfallen ist — sie tragen jetzt ausschließlich die
  Alarm-Identitäts-Auflösung. Eine Umbenennung/Neudokumentation dieses
  Zwecks ist NICHT Teil dieser Scheibe (kosmetisch, Sammel-Issue #1199 falls
  gewünscht).
- **Reale Testfläche vs. Schätzung:** die im Kontext-Dokument genannten
  „~11 Python-Testdateien" sind unvollständig (fehlten: Fixtures über
  `dict`-Literale und `**kwargs`-Entpackung statt literalem `aggregations=`).
  DEC-9 listet die vollständige, verifizierte Menge; die Umsetzung sollte
  trotzdem den in DEC-9 genannten Grep-Befehl selbst erneut laufen lassen,
  falls sich der Bestand zwischen Spec-Freigabe und Implementierung
  verändert hat.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** reine Aufräum-Scheibe innerhalb einer bereits in S1
  getroffenen Architekturentscheidung (Tagesrichtungs-Größen als
  eigenständige Katalog-IDs statt Auswertungswahl). Die Korrektur an DEC-2
  (API-Cluster bleibt größtenteils bestehen) ist keine neue
  Architekturentscheidung, sondern eine Tatsachenkorrektur einer vorherigen
  Analyse.

## Changelog

- 2026-08-15: Initial spec created (Issue #1728 Scheibe 3), DEC-2 aus dem
  Kontext-Dokument korrigiert (API-Metadaten-Cluster bleibt größtenteils
  bestehen — Live-Abhängigkeit `tripAlertMetricsFromCatalog.ts` gefunden)
