# Context: feat-1373-s2-ein-katalog

Etappe **S2** von Epic #1372 (Kind von Dach-Epic #1374). Tickets: #1373, #1384.
Stand der Messung: 2026-07-26, drei parallele Recherchen (Backend, Frontend, Bestandsdaten).

## Request Summary

Der Ortsvergleich soll seine wählbaren Wettergrößen aus dem zentralen Katalog
(`src/app/metric_catalog.py`) beziehen statt aus einer parallel gepflegten Compare-Liste.
Gespeicherte Auswahl migrieren, Übersetzungstabellen zurückbauen, keine Verhaltensänderung
in der Mail.

## Was sich gegenüber der Ticketlage geändert hat (wichtig)

Die Tickets stammen vom 2026-07-24/25. Zwei ihrer Annahmen treffen den heutigen Code nicht mehr:

1. **Die Liste ist nicht mehr im Browser verdrahtet.** #1350 Teil 2/3 ist geliefert: Die
   Oberfläche lädt die Compare-Größen über `GET /api/compare/metrics`
   (`WeatherMetricsTab.svelte:378`), der Trip über `GET /api/metrics` (`:346`). Es sind
   **zwei Endpoints auf zwei Listen**, nicht eine Frontend-Konstante. Die Doppelung ist
   eine Ebene tiefer gewandert, nicht verschwunden.
2. **„26 Einträge für ca. 15 echte Größen" stimmt nicht.** Gemessen: alle **24** wählbaren
   Katalog-Größen haben genau eine Compare-Entsprechung. Die Differenz zu 26 sind exakt
   **zwei** Aufspaltungen (s. u.). Keine Katalog-Größe fehlt im Vergleich, keine
   Compare-Zeile ist ohne Katalog-Ursprung.

Ferner: `compare_metric_catalog.py:4,113` spricht von „25 Metriken" — es sind seit #1351
**26** (Testfixture `test_compare_metric_catalog_endpoint.py:96` friert 26 ein).

## Der eigentliche Befund: die Aufspaltungen sind zwei, nicht viele

| Zentrale Größe | Compare-Zeilen | Katalog-Auswertungen |
|---|---|---|
| `temperature` | `temp_max_c`, `temp_min_c` | min/max/avg |
| `wind_chill` | `wind_chill_max_c`, `wind_chill_min_c` | min/max |

Alle übrigen 22 Compare-Schlüssel tragen die Auswertung **ebenfalls im Namen**
(`wind_max_kmh`, `precip_sum_mm`, `visibility_min_m`, `sunny_hours_h`, `humidity_avg_pct`,
`cloud_avg_pct`, `thunder_level_max`, `snow_new_sum_cm`, `pop_max_pct`, …), haben aber je
nur **eine** Variante. Die Migration „Schlüssel → Größe + Auswertung" ist damit für alle 26
gleichförmig ableitbar (`FRONTEND_TO_RENDERER_METRIC_ID` + `MetricDefinition.summary_fields`),
nur bei zwei Größen entstehen zwei Auswertungen derselben Größe.

## Bestandsdaten (gemessen 2026-07-26, lesend)

| | Produktion | Staging |
|---|---|---|
| Vergleiche gesamt | 5 | 86 |
| davon mit `active_metrics` | 5 | 57 |
| mit `hourly_metrics` | 0 | 1 |

**Produktion, tatsächlich gespeicherte Kennungen** (Häufigkeit):
`temp_max_c` 5 · `wind_max_kmh` 5 · `precip_sum_mm` 5 · `visibility_min_m` 5 ·
`gust_max_kmh` 4 · `thunder_level_max` 4 · `temp_min_c` 3 · `snow_new_sum_cm` 3 ·
`cape_max_jkg` 3 · `freezing_level_m` 3 · `sunny_hours_h` 1 · `pop_max_pct` 1 ·
`wind_direction_deg` 1 · `humidity_avg_pct` 1 · `wind_chill_min_c` 1

**Betroffene Doppel-Fälle in echten Daten:** `temp_max_c`/`temp_min_c` (3 Vergleiche tragen
beide) und `wind_chill_min_c` (1). Der Migrationsumfang ist klein; Datenerhalt bleibt
trotzdem Pflicht (Read-Modify-Write mit Merge, #102).

Weitere `display_config`-Schlüssel im Bestand: `region`, `ideal_ranges`,
`metric_alert_levels`, `telegram_style`, `hourly_metrics`.

## Related Files

### Backend
| Datei | Relevanz |
|---|---|
| `src/app/metric_catalog.py` | Zentraler Katalog, 26 Einträge, 24 `selectable` (`temperature_cold`, `confidence` ausgenommen). `get_all_metrics():449` speist `/api/metrics` |
| `src/output/renderers/compare_metric_catalog.py` | 26 Einträge mit UI-Zusatzinfo (Wertebereiche, `higherIsBetter`, `kind`). Einziger Produktiv-Konsument: `api/routers/compare.py:20` |
| `src/output/renderers/compare_metric_ids.py` | `FRONTEND_TO_RENDERER_METRIC_ID` (:15-57) + zwei kleine Brücken. Konsumenten: `compact_summary.py:512`, `compare_html.py:30`, `report_config_resolver.py:216`, `compare_metric_catalog.py:26` |
| `src/output/renderers/compare_hourly_metric_ids.py` | Dritte Liste, 10 Einträge, Stundenverlauf. Konsument: `report_config_resolver.py:215` |
| `api/routers/config.py:58-83` | `GET /api/metrics` — nach Kategorie gruppiert, nur `selectable` |
| `api/routers/compare.py:11-22` | `GET /api/compare/metrics` — flach, 26 Einträge, keine Kategorien, dafür UI-Wertebereiche |
| `src/output/renderers/email/helpers.py:90-210` | **Zielmuster**: `dp_to_row()`/`aggregate_night_block()` lesen ausschließlich über `get_metric()` aus dem zentralen Katalog |

### Frontend
| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | Geteilter Reiter. Zwei getrennte Katalog-States (`catalog` / `compareCatalog`, Kommentar :148-151), zwei Fetches (:346 / :378), Markup-Verzweigung ab :821 |
| `.../weather-metrics-tab/compareMetricSelection.ts:17-24` | Mappt die Endpoint-Antwort in Auswahl-Einträge |
| `.../corridor-editor/corridorEditorState.ts` | `buildComparePool():397-419` — Vergleichs-Pool = **alle** Endpoint-Größen. `ROUTE_METRIC_DEFS:28-35` + `ROUTE_CORRIDOR_CATALOG_IDS:87-94` — Trip-Pool = 6 |
| `.../compare/compareHourlyMetricDefs.ts:29-44` | Vierte Liste (10 Einträge), Stundenverlauf-Vokabular im Browser |
| `.../corridor-editor/corridorEditorState.ts:309-316` | `COMPARE_METRIC_KEYS`, 26 Schlüssel, Alt-Default „nichts gespeichert = alles aktiv" |

## Speicherwege (die Wurzel der Drift, #1374)

- **Trip:** Selbst-Speichern in der Komponente. `scheduleAutoSave()` (`WeatherMetricsTab.svelte:615-630`)
  → **zwei** PUTs (`/api/trips/{id}/weather-config` und `/api/trips/{id}`).
- **Vergleich:** Kein Selbst-Speichern. Die Komponente mutiert nur den Assistenten-Zustand;
  persistiert wird im Hub (`CompareTabs.svelte:663 ff.`) über einen Schnappschuss-Vergleich
  (`weatherMetricsCompareSave.ts:71-98`) → **ein** PUT `/api/compare/presets/{id}`.

**Feldformate unterscheiden sich grundlegend:**
- Trip: `display_config.metrics[]` = Objekte `{metric_id, enabled, bucket?, order?, use_friendly_format, horizons, sms_threshold?}`
- Vergleich: `display_config.active_metrics` = reines String-Array, Reihenfolge = Zeilenfolge, kein `order`-Feld

## Dirty-Check-Falle (belegt)

Kein dynamisches Iterieren über geladene Schlüssel, sondern **hand-gepflegte Schnappschuss-Typen**.
Ein neues Feld in `display_config` (Vergleich) braucht **vier** Ergänzungen, sonst ist es
still unspeicherbar: `WeatherMetricsSnapshot` (`weatherMetricsCompareSave.ts:54-62`),
`currentWetterMetrikenSnapshot()` (`CompareTabs.svelte:636-643`), `norm()` (`:85-90`),
sowie `buildHubPutPayload` (`compareHubWizardBridge.ts:104-149`) **und**
`buildComparePresetSavePayload` (`compareEditorSave.ts:93-177`). Der Tagesfenster-Fall aus
S1b musste an genau diesen Stellen ergänzt werden. Kein Meta-Test sichert das ab.

## Die strukturelle Lücke, die S2 schließen soll

Es gibt **vier** Drift-Sicherungen, aber **keine einzige** prüft eine Beziehung zum zentralen
Katalog:

- `compare_metric_catalog.py:92-99` — Katalog-Keys == Resolver-Keys
- `compare_metric_catalog.py:105-109` — `alarmCapable` ⊆ Katalog-Keys
- `tests/unit/test_compare_metric_catalog_consistency.py:72-95` — Resolver-ID ↔ `CV2_METRICS`-Zeile
- `tests/tdd/test_compare_metric_catalog_endpoint.py:96` — 26 Einträge eingefroren

Folge: Eine neue Größe im zentralen Katalog (oder ein geändertes `dp_field`) erscheint im
Vergleich **nie**, und kein bestehender Test schlägt an.

## Ausdrücklich NICHT in S2

| Was | Warum nicht | Wohin |
|---|---|---|
| `CV2_METRICS`/`HOUR_METRICS` im Renderer (fest einprogrammierte Spaltentabellen mit eigenen `fmt`/`sev`-Funktionen; nur 12 von 27 Zeilen tragen überhaupt `metric_id`) | Renderer-Umbau, nicht Auswahlfläche | S3 (#1366, #1378) / S5 (#1377) |
| Auswertung **wählbar** machen | eigene Etappe | S4 (#1357) |
| Trip-Wertebereiche-Pool von 6 auf alle passenden erweitern | PO-Entscheidung 2026-07-26: „erst Wirkung, dann Auswahl" — solange Wertebereiche beim Trip nichts bewirken, verstößt mehr Auswahl gegen Invariante 1 | S6, zusammen mit #1371 |

**Messkorrektur zu #1384:** Die Begrenzung „5 von 24" existiert **nur im Trip-Zweig** des
geteilten Korridor-Editors (`ROUTE_METRIC_DEFS`). Im **Vergleich** ist der Pool bereits
vollständig (`buildComparePool()` nimmt alle Endpoint-Größen). #1384 ist damit sachlich ein
Trip-Ticket und wird von S2 nicht behoben.

## Risks & Considerations

1. **Funktionsverlust bei „Temperatur min".** Kollabiert man die zwei Compare-Zeilen auf
   eine Katalog-Größe, ohne die Auswertung mitzuführen, verliert der Nutzer die Wahl
   zwischen Höchst- und Tiefstwert — bis S4. Muss die Migration ausdrücklich verhindern.
2. **Datenerhalt.** 5 Vergleiche in Produktion, 57 in Staging mit Auswahl. Read-Modify-Write
   mit Merge, Migration idempotent, Sicherung vorher (#102, `data_schema_backup.py`).
3. **Vier Speicher-Ergänzungsstellen** (s. o.) — ein neues Auswertungs-Feld ist ohne alle
   vier still unwirksam. Nur ein echter Klickpfad-Nachweis zeigt das, kein Kern-Test.
4. **Zwei eingefrorene Testfixturen** (26 Einträge) brechen bei jeder Katalog-Änderung —
   beim Umbau bewusst nachziehen, nicht aufweichen.
5. **Mail-Verhalten muss identisch bleiben.** Nachweis über echte Staging-Mail vor/nach mit
   demselben Vergleich. Der Pflicht-Validator ist seit #1381 wieder brauchbar.
