# Context: feat-1848-ausblick-vokabular

Issue #1848, **Scheibe A** — 3-Tages-Ausblick: `outlook_metrics` auf reine
Katalog-Kennungen zurückführen. Erhoben 2026-08-18, Phase 1.

## Request Summary

Der 3-Tages-Ausblick speichert seine Spaltenauswahl als Paare
`{metric_id, aggregation}`, die Trip-Grundauswahl dagegen als reine
Katalog-Kennungen. Dadurch wird dieselbe Auswahl-Kaskade (ADR-0050) an zwei
Stellen gepflegt. Scheibe A soll den Ausblick auf das Kennungs-Vokabular
umstellen und die Zweitschrift der Kaskade entfallen lassen.

## Related Files

| File | Relevance |
|------|-----------|
| `src/app/models.py:811` | Feld `outlook_metrics: Optional[list[dict]] = None` in `UnifiedWeatherDisplayConfig`. Kein benannter Paar-Typ — Plain dicts |
| `src/app/models.py:898-921` | `_clip_to_global_maximum()` — die **Original**-Kaskade (ADR-0050, Regeln D1–D4) |
| `src/output/renderers/compare_outlook_metric_ids.py:78-102` | `resolve_trip_outlook_metrics()` — die **Zweitschrift** der Kaskade, bezeichnet sich im Docstring selbst als Nachbildung |
| `src/output/renderers/compare_outlook_metric_ids.py:45-75` | `resolve_outlook_metrics()` — Auflösung der Paare gegen den Compare-Katalog, Drei-Werte-Semantik |
| `src/output/renderers/compare_outlook_metric_ids.py:105-142` | `outlook_columns()` — baut Spaltenköpfe, dedupliziert gleiche Labels über `aggregation_label` |
| `src/output/renderers/compare_metric_catalog.py:76-162` | `COMPARE_METRIC_CATALOG`, 26 Einträge, jeder mit `{key, metric_id, aggregation}` |
| `src/output/renderers/compare_metric_ids.py:15-57` | `FRONTEND_TO_RENDERER_METRIC_ID`, 26 Einträge |
| `src/output/renderers/compare_metric_ids.py:67-74` | `RENDERER_TO_TRIP_METRIC_ID`, 6 Einträge |
| `src/app/metric_catalog.py` | 32 `MetricDefinition`, das Ziel-Vokabular (reine Kennungen) |
| `src/app/loader.py:942` | Lesepfad — `data.get("outlook_metrics")`, keine Transformation |
| `src/app/loader.py:1550-1555` | Schreibpfad — **bedingt**, nur wenn `not None`; erhält die Drei-Werte-Semantik |
| `src/app/loader.py:766-792` | `_append_derived_metrics()` — Vorbild „beim Laden ableiten, beim Speichern ausfiltern" (`derived=True`) |
| `scripts/migrate_1373_compare_active_metrics_format.py` | Vorbild Datenmigration: Read-Modify-Write, katalog-gestützt, Backup + Idempotenz, unbekannte Einträge bleiben unangetastet |
| `frontend/src/lib/types.ts:296` | `outlook_metrics?: { metric_id: string; aggregation: string }[]` |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:456,523,886` | Normalisierung beim Laden, Rückübersetzung beim Speichern |
| `frontend/src/lib/components/compare/CompareOutlookLayoutControls.svelte:142-180` | Auswahl-UI: je Auswertung ein eigenes Kästchen |
| `frontend/src/lib/components/compare/compareEditorSave.ts:170-176,424-426` | `outlookMetricKeys: string[]` → `toStoredActiveMetrics()` → Paare |
| `frontend/src/lib/components/compare/compareHubWizardBridge.ts:205-208,719,764` | Hub-Hydration und Flush |
| `docs/reference/api_contract.md:1992-2060` | Vertrag: Neuformat, Drei-Werte-Semantik, Spaltenköpfe aus `compare_metric_catalog.label` |

## Existing Patterns

- **Kaskade (ADR-0050):** Die Grundauswahl ist das Maximum; nachgelagerte
  Ebenen dürfen nur abwählen, nie hinzufügen. Regel D4: leere Grundauswahl
  = „kein Maximum definiert" ⇒ **nicht** schneiden.
- **Drei-Werte-Semantik:** `None`/fehlt = Standardspalten · `[]` = Block
  entfällt · gefüllt = gewählte Spalten in Auswahlreihenfolge. Wird durch
  bedingtes Schreiben (`loader.py:1550`) getragen.
- **Verlustfreie Ableitung:** beim Laden ergänzen (`derived=True`), beim
  Speichern ausfiltern (`loader.py:1561`).
- **Frontend hält Katalog-Keys**, nicht Paare: `outlookMetricKeys: string[]`
  (z. B. `temp_max_c`); Paare entstehen erst beim Speichern.

## Dependencies

- **Upstream:** `compare_metric_catalog` (Paar→Key), `metric_catalog`
  (`summary_field_for()`), `UnifiedWeatherDisplayConfig.get_metrics_for_report_type()`
- **Downstream (Produktivpfad):** `trip_report.py:209`,
  `email/outlook.py:129,334,491-495,594,642`, `narrow.py:586`,
  `email/compact.py:274`, `report_config_resolver.py:249,291`,
  `compare_preview_service.py`, `scheduler_dispatch_service.py`
- **Go:** kein typisiertes Pendant — `DisplayConfig map[string]interface{}`
  (`internal/model/location.go:16`), reines Durchreichen mit RMW-Merge

## Existing Specs

- `docs/specs/modules/feat_1720_s1_trip_ausblick_metriken.md` — direkte
  Vorgänger-Spec; **AC-14/15/16** sichern die Kaskade für den Ausblick zu
  (AC-16 bildet Regel D4 wortgleich nach). Diese Zusagen müssen den Umbau
  unverändert überleben.
- `docs/specs/modules/compare_metric_ssot_final.md`,
  `docs/specs/modules/rework_1351_compare_catalog.md` — Katalog-Historie
- `docs/adr/0050-metrik-kaskade-verfeinerung-nicht-ersetzung.md`

## Risks & Considerations

### R1 — 🔴 Kennungen können die heutige Auswahl NICHT verlustfrei abbilden

Vier Katalog-Kennungen tragen **mehrere** Auswertungen:

| Kennung | Auswertungen | heute als Ausblick-Spalten ausdrückbar |
|---|---|---|
| `temperature` | min, max, avg | Minimum **und** Maximum getrennt |
| `wind_chill` | min, max | getrennt |
| `snowfall_limit` | min, max | `summary_fields` nur für `min` |
| `freezing_level` | min, max | `summary_fields` nur für `min` |

Die Auswahl-Oberfläche zeigt „Temperatur Minimum" und „Temperatur Maximum"
heute als **zwei unabhängige Kästchen**
(`CompareOutlookLayoutControls.svelte:142-180`); der Nutzer wählt nie eine
Auswertung, sondern eine fertige Zeile. Ein reines Kennungs-Vokabular kann
diese Unterscheidung nicht tragen — beide Spalten fielen auf `temperature`
zusammen. **Das ist der eigentliche Knackpunkt der Scheibe, kein Detail.**

### R2 — Sechs Kennungen haben gar kein Paar-Pendant

`temperature_night`, `temperature_day_low`, `temperature_day_high`,
`wind_chill_night`, `wind_chill_day_low`, `wind_chill_day_high` besitzen
`summary_fields = None` — sie sind reine Sichtbarkeits-Gates für SMS-Token
und liefern keinen Tabellenwert. Ein reines Kennungs-Vokabular müsste sie
entweder anbieten (und leere Spalten rendern) oder aktiv aussperren.

### R3 — Bestandsdaten: Migration braucht die Server-Stände

Im Repo (Haupt-Checkout `data/users/`, Nutzer `default` und
`validator-issue110`) enthält **keine** Datei `outlook_metrics`. Das ist
kein Freibrief: die echten Nutzerdaten liegen auf Produktion und Staging,
nicht im Repo. Vor jeder Migration ist dort auszuzählen, wie viele Trips
und Presets betroffen sind und ob Paare mit gleicher Kennung, aber
verschiedener Auswertung vorkommen (genau die verlustgefährdeten Fälle aus
R1).

### R4 — Drei-Werte-Semantik ist bruchgefährdet

`None` vs. `[]` vs. gefüllt wird nur durch bedingtes Schreiben getragen.
Eine Migration, die unbedacht schreibt, verwandelt „nie gesetzt" in
„bewusst geleert" und lässt den Ausblick-Block verschwinden.
Bug-Muster BUG-DATALOSS-GR221 (#102).

### R5 — Frontend-Vokabular ist ein drittes

Das Frontend arbeitet weder mit Kennungen noch mit Paaren, sondern mit
Compare-Katalog-Keys (`temp_max_c`). Eine Umstellung des Speicherformats
zieht `types.ts`, `WeatherMetricsTab.svelte`, `compareEditorSave.ts`,
`compareHubWizardBridge.ts` und zwei Staging-E2E-Suiten nach.

### R6 — Doppelpflege bestünde teilweise fort

Der Ortsvergleich (Scheibe B) behält das Paar-Vokabular vorerst.
`outlook_columns()` und der Compare-Katalog werden weiter von beiden Flächen
benutzt — die Vereinheitlichung ist erst nach B abgeschlossen.

## Offene Entscheidung (PO)

Aus R1 folgt: Scheibe A ist **nicht** mechanisch ausführbar. Es braucht eine
Festlegung, wie „Temperatur Minimum" und „Temperatur Maximum" künftig als
zwei getrennte Ausblick-Spalten ausdrückbar bleiben — oder ob sie es nicht
mehr sein sollen. Siehe Analyse-Phase.
