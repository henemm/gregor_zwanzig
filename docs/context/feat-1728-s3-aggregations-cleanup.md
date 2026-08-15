# Context: #1728 Scheibe 3 — `MetricConfig.aggregations` aus Modell/Loader/API entfernen

## Request Summary
S1 (Backend) und S2 (Editor) haben vier neue eigenständig wählbare Größen (`temperature_day_low/high`,
`wind_chill_day_low/high`) eingeführt und den alten Auswertungs-Schalter (`MetricConfig.aggregations`,
Editor-Abschnitt „05 — Auswertungen") an keinem Ausgabeort und keiner Bedienfläche mehr angebunden.
Scheibe 3 soll das jetzt tote Feld aus Modell, Loader und API entfernen. Issue #1728 bleibt danach offen
für #1848 (gemeinsames Vokabular Ortsvergleich/Ausblick).

## Related Files

### Backend
| File | Relevance |
|------|-----------|
| `src/app/models.py:613` | `MetricConfig.aggregations: list[str]` — das zu entfernende Feld |
| `src/app/loader.py:758-765` | `_DERIVED_METRIC_RULES` — **liest `mc.aggregations` weiterhin**, s. Risiko unten |
| `src/app/loader.py:768-798` | `_append_derived_metrics()` — Migrationslogik, die die vier neuen Größen für Alt-Trips ohne expliziten Eintrag ableitet |
| `src/app/loader.py:803-930` (ca.) | `_parse_display_config()` — 3 Stellen (global/channel_layouts/channel_layouts_per_report), je `aggregations=mc_data.get("aggregations", ["min","max"])` |
| `src/app/loader.py:975-1010` | Alt-Migration `TripWeatherConfig` → `UnifiedWeatherDisplayConfig` (sehr alter Pfad, `enabled_metrics` → `MetricConfig(aggregations=...)`) |
| `src/app/loader.py:160` | Serialisierung zurück ins Speicherformat (`"aggregations": mc.aggregations`) |
| `api/routers/config.py:75,112-119` | `GET /api/metrics` liefert `"aggregations"`-Metadaten aus `available_aggregations()` — **anderes Konzept** (Katalog-Möglichkeiten, nicht der gespeicherte Wert), aber seit S2 ebenfalls ohne Konsumenten im Frontend |
| `src/app/metric_catalog.py:901-921` | `available_aggregations()`, `pill_default_aggregations()` — Katalog-Funktionen; `pill_default_aggregations` ist laut S1-Notiz bereits ohne Aufrufer (#1199) |
| `src/output/renderers/email/helpers.py:1445,1903-1904` | Kommentare bestätigen: Pill-Rendering liest `MetricConfig.aggregations` seit S1 nicht mehr |

### Frontend
| File | Relevance |
|------|-----------|
| `frontend/src/lib/types.ts:191-225` | `MetricEntry.aggregations` (Katalog-Metadaten, API-Antwort) und `TripMetricConfig.aggregations?` (gespeicherter Wert) — zwei verschiedene Felder gleichen Namens |
| `frontend/src/lib/components/trip-detail/metricsEditor.ts:202,343,369` | `aggregationsMap`-Parameter, baut `{ aggregations: [...] }` ins Payload-Objekt je Metrik |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | State `aggregationsMap` (Zeile ~234), im Dirty-Check/Snapshot (~350-370), beim Laden aus `snap.aggregationsMap` (~827/844), fließt in `buildWeatherConfigMetrics(...)` für Payload (~858/883) |
| `frontend/src/lib/components/shared/weather-metrics-tab/aggregationSelection.ts` | Komplette Datei nur für den alten `mode='single'`-Pfad — **kein Produktiv-Aufrufer mehr** (nur noch ein Typ-Import in `AggregationMetricRow.svelte`) |
| `frontend/src/lib/components/shared/weather-metrics-tab/AggregationMetricRow.svelte` | `mode='single'` (alte Auswertungswahl) ist tot, `mode='multiple'` lebt weiter — wird jetzt für die S2-Schwellwert-Zeilen (K/D/FK/FD/FN) UND weiterhin für die Compare-Ausblick-Auswahl verwendet |

## Existing Patterns
- Read-Modify-Write mit Merge ist bei Schema-Änderungen Pflicht (`CLAUDE.md` „Daten-Schema-Reworks") — greift hier, da `aggregations` ein persistiertes Feld in `data/users/<id>/trips/*.json` ist.
- S1/S2 haben bereits das Muster etabliert: alte Felder bleiben als Lese-Kompatibilität bestehen, bis ein eigener Aufräum-Schritt sie entfernt (genau das ist diese Scheibe).
- `derived=True`-Metriken werden nie zurückgeschrieben (Vorbild `temperature_night`, `loader.py`).

## Dependencies
- **Upstream:** `MetricConfig.aggregations` wird beim Laden aus dem persistierten JSON gelesen (`loader.py`, 3+ Stellen) und beim Speichern zurückgeschrieben.
- **Downstream / kritisch:** `_append_derived_metrics()` (`loader.py:758-798`) **liest `mc.aggregations` immer noch aktiv**, um zu entscheiden, ob `temperature_day_low`/`_high`/`wind_chill_day_low`/`_high` für einen Alt-Trip ohne expliziten Eintrag als `enabled` abgeleitet werden. Das ist der Migrationspfad für die **16 von 17 Trips**, die laut S1-Notiz kein gespeichertes `aggregations`-Feld haben (Default `["min","max"]` greift) bzw. für den einen Trip (`gr221-mallorca.json`), der es explizit gesetzt hat.

## Existing Specs
- `docs/specs/modules/feat_1728_s1_temp_aufloesung.md` — Backend-Spec S1 (16 ACs)
- `docs/specs/modules/feat_1728_s2_editor.md` — Editor-Spec S2 (12 ACs)

## Risks & Considerations

### 🔴 Kernrisiko: `aggregations` ist NICHT vollständig wirkungslos — es speist noch die Migrations-Ableitung
Die Ausgangsannahme im Issue-Text („das Feld bleibt seit Scheibe 1 wirkungslos im Backend") stimmt für alle
**Ausgabeorte**, aber nicht für `_append_derived_metrics()`. Diese Funktion nutzt `mc.aggregations` als
Enable-Kriterium für die vier neuen Größen bei Trips, die noch keinen expliziten Eintrag dafür haben.
Wird das Feld ersatzlos aus `MetricConfig` entfernt, ohne diese Stelle anzupassen, bricht entweder der Code
(AttributeError) oder — falls nur `aggregations=[]`-Fallback verwendet würde — die Ableitung würde für
Alt-Trips STILL auf „nicht aktiviert" fallen, was das in S1 zugesicherte Verhalten (Bestandstrip mit
`temperature: ["min","max","avg"]` bekommt künftig Tief UND Hoch, PO-Entscheid E1) unbemerkt umkehren könnte.
**Muss in der Spec explizit geklärt werden:** entweder wird die Ableitungsregel auf ein anderes Signal
umgestellt (z.B. `enabled` allein, ohne `required_agg`-Filter) oder das Feld bleibt intern (nur für die
Migration) erhalten und wird nur aus API/Payload-Kontrakt entfernt.

### Frontend: totes vs. lebendiges `AggregationMetricRow`
`mode='single'` (alte Segmented-Control-Auswertungswahl) und `aggregationSelection.ts` sind vollständig ohne
Produktiv-Aufrufer — Kandidat für Entfernung in dieser Scheibe. `mode='multiple'` bleibt aktiv (S2-Schwellwert-
Zeilen UND Compare-Ausblick über `CompareOutlookLayoutControls.svelte` mit eigenem, unabhängigem Typ
`CompareAggregationOption`/`compareAggregationGrouping.ts` — **nicht** betroffen). `aggregationsMap` in
`WeatherMetricsTab.svelte` schreibt aktuell noch immer den (nie mehr bedienbaren) Altwert beim Speichern
zurück ins Payload — reiner Round-Trip-Ballast, der mit dem Backend-Feld zusammen entfernt werden sollte,
sonst bleibt eine Leiche auf der einen Seite der API stehen.

### Umfang der API-Metadaten (`GET /api/metrics` → `"aggregations"`-Array)
Andere Bedeutung als das Modellfeld (Katalog-Möglichkeiten statt gespeicherter Wert), aber ebenfalls seit S2
ohne Frontend-Konsumenten (`aggregationOptions()` in `aggregationSelection.ts` ist der einzige Aufrufer und
selbst tot). Zu entscheiden: mitentfernen (schlankerer Vertrag) oder als harmlose, ungenutzte Metadaten stehen
lassen (kleinerer Diff, geringeres Risiko).

### Testlage
11 Python-Tests konstruieren `MetricConfig(..., aggregations=...)` direkt (`tests/integration/`, `tests/tdd/`,
`tests/unit/`, `tests/red/`) — jeder davon muss angepasst oder als überholt geprüft werden. Frontend: 2 dedizierte
Tests (`buildWeatherConfigMetricsAggregations.test.ts`, `aggregation_row_multi_select.test.ts` — Namen prüfen,
ob letzterer wirklich `mode='single'` oder den weiterlebenden `mode='multiple'`-Pfad testet).

### Nebenbefund aus #1856 E7 (nicht automatisch Teil dieser Scheibe)
Kommentar vom 2026-08-15 auf #1728 meldet: die vier neuen Größen fehlen in `METRIC_PRIORITY`
(`channel_layout.py:60`) und bekommen Priorität 0 bei `auto_distribute` — ungeklärt, ob das im Briefing-Pfad
wirkt. Zusätzlich: veralteter Name `_NIGHT_SCALAR_IDS` in `docs/reference/metric_output_matrix.md` (Zeilen 107,
366) — bei dieser Gelegenheit mitziehbar, da der Worktree ohnehin hier arbeitet. Bewertung in der
Analyse-/Spec-Phase: mitnehmen oder nach #1199 auslagern.

### Datenschema-Pflicht
`models.py` ist schema-relevant → `data_schema_backup.py`-Hook greift automatisch bei Edits. Entfernen des
Feldes ist bei bestehenden JSON-Dateien unkritisch (überzählige Keys werden beim Parsen ignoriert, kein
Datenverlust), solange kein Code mehr versucht, das Attribut zu lesen/schreiben.

## Analysis

### Type
Feature (Aufräumen/Tech-Debt-Abbau, Standard-Track)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/app/models.py` | MODIFY | `MetricConfig.aggregations`-Feld entfernen |
| `src/app/loader.py` | MODIFY | `_append_derived_metrics()` umstellen (s. Empfehlung), alle `aggregations=mc_data.get(...)`-Stellen (3x `_parse_display_config`, 1x Alt-Migration, 1x Serialisierung) entfernen |
| `api/routers/config.py` | MODIFY | `"aggregations"`-Metadaten-Key aus `GET /api/metrics` entfernen (dead cluster, s.u.) |
| `src/app/metric_catalog.py` | MODIFY | `available_aggregations()` + `pill_default_aggregations()` entfernen — nach Entfernen des API-Keys ohne jeden Aufrufer |
| `frontend/src/lib/types.ts` | MODIFY | `TripMetricConfig.aggregations?` entfernen; `MetricEntry.aggregations` entfernen falls API-Metadaten mitentfernt werden |
| `frontend/src/lib/components/trip-detail/metricsEditor.ts` | MODIFY | `aggregationsMap`-Parameter entfernen |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | MODIFY | State `aggregationsMap`, Snapshot/Dirty-Check-Einträge, Payload-Aufrufe bereinigen |
| `frontend/src/lib/components/shared/weather-metrics-tab/aggregationSelection.ts` | DELETE | keine Produktiv-Aufrufer mehr |
| `frontend/src/lib/components/shared/weather-metrics-tab/AggregationMetricRow.svelte` | MODIFY | `mode='single'`-Zweig entfernen, `mode='multiple'` bleibt Default/einzige Form |
| ~11 Python-Testdateien (`tests/integration/`, `tests/tdd/`, `tests/unit/`, `tests/red/`) | MODIFY | `MetricConfig(aggregations=...)`-Konstruktionen anpassen |
| 2 Frontend-Testdateien (`weather-metrics-tab/__tests__/`) | MODIFY/DELETE | je nachdem ob sie toten oder lebenden Pfad prüfen (im RED klären) |
| `docs/reference/metric_output_matrix.md` | MODIFY | Nebenbefund aus #1856 E7 mitziehen (`_NIGHT_SCALAR_IDS` → aktueller Name, Zeilen 107/366) |

### Scope Assessment
- Files: ~16 (9 Produktivcode, ~2 Löschungen, ~5 Test/Doku)
- Estimated LoC: grob −150/+30 (überwiegend Löschungen: tote `aggregationSelection.ts`, tote Frontend-Plumbing, tote Katalogfunktionen)
- Risk Level: **MEDIUM** — kein kritischer Pfad/Auth, aber persistiertes Schema-Feld mit einer noch aktiven Downstream-Abhängigkeit (`_append_derived_metrics`), die zuerst entkoppelt werden muss

### Technical Approach
1. **`_append_derived_metrics()` zuerst entkoppeln, dann erst das Feld entfernen** (Reihenfolge wichtig,
   sonst AttributeError). Empfehlung: Die vier `day_low`/`day_high`-Regeln in `_DERIVED_METRIC_RULES` auf
   `required_agg=None` reduzieren (wie bei `temperature_night`/`wind_chill_night` bereits Praxis) — Ableitung
   dann ausschließlich über `mc.enabled` des Elternteils. Auswirkung: genau **ein** bekannter Trip
   (`gr221-mallorca.json`, `wind_chill: ["min"]`) verliert die Verfeinerung „nur wenn `max` explizit berechnet
   wurde" und bekäme `wind_chill_day_high` künftig als aktiviert abgeleitet, bis der Trip einmal über den
   S2-Editor gespeichert wird (dort ist die Größe seit S2 direkt und einzeln abwählbar). **PO-Entscheidung
   nötig, siehe offene Frage unten.**
2. Feld aus `MetricConfig` (`models.py`) entfernen, alle Lese-/Schreibstellen in `loader.py` bereinigen.
3. Toten API-Metadaten-Cluster (`GET /api/metrics` → `"aggregations"`, `available_aggregations()`,
   `pill_default_aggregations()`) mitentfernen — schließt den bereits in S1 als Nebenbefund vermerkten
   `pill_default_aggregations`-Fund (#1199) gleich mit ab, statt ihn erneut zu vertagen.
4. Frontend-Plumbing bereinigen: `aggregationsMap` (State + Payload-Bau), `aggregationSelection.ts` (Datei
   löschen), `mode='single'` in `AggregationMetricRow.svelte` (bleibt nur `mode='multiple'` — Compare-Ausblick
   und die S2-Schwellwert-Zeilen sind davon **nicht** betroffen, die nutzen bereits `mode='multiple'` mit dem
   unabhängigen `compareAggregationGrouping.ts`-Vokabular).
5. Migration/Bestandsdaten: kein aktiver Migrationslauf nötig — Read-Modify-Write ignoriert überzählige
   `aggregations`-Keys beim nächsten Laden automatisch, kein Datenverlust (Feld bleibt in alten JSON-Dateien
   einfach ungelesen liegen).

### Dependencies
- Reihenfolge intern: Schritt 1 (Loader-Entkopplung) MUSS vor Schritt 2 (Feld-Entfernung) passieren.
- Keine Abhängigkeit zu #1848 (das betrifft Compare/Ausblick-Vokabular, hier unberührt).

### Open Questions — PO-Entscheide 2026-08-15
- [x] **DEC-1:** `required_agg`-Verfeinerung entfällt, Ableitung nur noch über `enabled` des Elternteils
      (wie bei `temperature_night`/`wind_chill_night`). Bekannte Auswirkung: `gr221-mallorca.json` bekommt
      `wind_chill_day_high` künftig als aktiviert abgeleitet statt deaktiviert — korrigierbar per S2-Editor.
      **Akzeptiert.**
- [x] **DEC-2:** Toter API-Metadaten-Cluster (`GET /api/metrics` → `"aggregations"`-Array,
      `available_aggregations()`, `pill_default_aggregations()`) wird in dieser Scheibe mitentfernt — schließt
      #1199-Nebenbefund aus S1 gleich mit ab.
- [x] **DEC-3:** Doku-Nebenbefund #1856 E7 (`_NIGHT_SCALAR_IDS` → aktueller Name in
      `docs/reference/metric_output_matrix.md:107,366`) wird in dieser Scheibe mitgezogen.
