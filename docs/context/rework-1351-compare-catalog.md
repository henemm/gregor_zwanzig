# Context: rework-1351-compare-catalog

## Request Summary
Scheibe 3 der Compare-Metrik-Angleichung (#1351, Epic #1230): (1) gefühlte **Höchst**temperatur
(`wind_chill_max_c`, intern längst berechnet) in Trip + Compare wählbar/anzeigbar machen — analog
Temperatur min/max; (2) den Umgang mit `channel_layouts` im Compare-Kontext bereinigen (keine tote
Fläche / keine stille Divergenz).

## TEIL 1 — Gefühlte Höchsttemperatur wählbar (Aufwand: MITTEL)

### Related Files
| File | Relevanz |
|------|----------|
| `src/app/metric_catalog.py:101-112` | `wind_chill` hat nur `default_aggregations=("min",)` + `summary_fields={"min":"wind_chill_min_c"}`. Vorbild `temperature:77-86` hat min/max/avg als je eigene `summary_fields`. |
| `src/services/weather_metrics.py:766,783-784` | `wind_chill_max_c` wird bereits berechnet und in `aggregation_config` geführt — Wert existiert, wird nur nicht ausgespielt. |
| `src/output/renderers/compare_metric_catalog.py:31-84` | Handgepflegte `COMPARE_METRIC_CATALOG`, keyed nach summary_field. `temp_max_c`+`temp_min_c` je eigener Eintrag (Muster). Nur `wind_chill_min_c` (Z.65), max fehlt. |
| `src/output/renderers/compare_metric_ids.py:15,45` | `FRONTEND_TO_RENDERER_METRIC_ID` + `wind_chill_min_c→wind_chill_min`. Drift-assert (`compare_metric_catalog.py:92-97`) erzwingt Gleichlauf beider Kataloge. |
| `src/app/user.py:133` | `LocationResult` hat nur `wind_chill_min`, kein `wind_chill_max`. |
| `src/services/comparison_engine.py:145-147,250,314,461-465` | max wird Z.461-465 zwar berechnet, aber nur `wind_chill_min` in `LocationResult` verdrahtet (Z.250,314). |
| `src/output/renderers/email/helpers.py:1233-1242` | Trip-Pill: hartkodierter `if metric_id=="wind_chill"`-Zweig, nur `min`. |
| `src/output/renderers/email/compare_html.py:245` | Compare-HTML: fester Eintrag `wind_chill_min`, Label „Gefühlte Temp. min". |
| `src/output/renderers/comparison.py:150-152` | Compare-Plain/SMS: nur `wind_chill_min`. |

### Fluss in die Auswahl (SSoT #1350)
- **Trip:** `GET /api/metrics` (`api/routers/config.py:58-83`) emittiert **keine** Aggregationen; Trip-UI wählt nur an/aus. Aggregationen serverseitig aus `build_default_display_config()` (`metric_catalog.py:483-489`).
- **Compare:** `GET /api/compare/metrics` (`api/routers/compare.py`) → `get_compare_metric_catalog()`. Frontend rendert `compareCatalog` direkt (`WeatherMetricsTab.svelte:763-773`). **→ Ein neuer Backend-Katalog-Eintrag `wind_chill_max_c` erscheint automatisch in der Compare-Auswahl** — kein FE-Listen-Nachzug für die Auswahl-UI nötig. Aber Renderer + Datenpfad müssen ergänzt werden.

### Existing Patterns
- min+max-Muster: `temperature` (77-86), `snowfall_limit` (274), `freezing_level` (399) — je eigener `summary_fields`-Eintrag pro Aggregation.
- `wind_chill` ist Vorboten-Metrik (ADR-0010, `is_precursor`, `default_change_threshold=None`) — beim Erweitern erhalten.

## TEIL 2 — channel_layouts im Compare (Befund ändert das Framing!)

**Kernbefund:** `channel_layouts` ist im Compare-Editor **GAR NICHT vorhanden** — nicht bloß ignoriert,
sondern bewusst als Attrappe entfernt (#1287/#1291, `docs/reference/api_contract.md:2978-2983`). Es gibt
also **keine sichtbare tote Fläche** im Compare.

| File | Relevanz |
|------|----------|
| `src/services/report_config_resolver.py:227-234` | Compare-Resolver liest nur `active_metrics`+`hourly_metrics`; `CompareRenderOptions` (147-165) hat kein channel_layouts-Feld. |
| `src/app/models.py:595,639-676` | `per_channel_layouts` + Kaskade `get_metrics_for_channel()` — nur Trip. |
| `src/output/renderers/trip_report.py:116`, `channel_layout.py:55-59` | Trip wertet channel_layouts via `get_metrics_for_channel` aus. |
| `frontend/.../WeatherMetricsTab.svelte:740-783` | context `vergleich` = flache An/Aus-Liste (mutiert nur `active_metrics`); `:853-855` LayoutTab nur `context="route"`. |
| `frontend/.../compareEditorSave.ts:88-89`, `compareWizardState.svelte.ts:132`, `compareHubWizardBridge.ts:111` | channel_layouts wird im Compare nur **unsichtbar round-getrippt** (Datenerhalt), von keinem Compare-`.svelte` geschrieben. |

**Konsequenz:** Da der Compare-Editor channel_layouts nicht schreibt, kann die vom Issue befürchtete
„stille Divergenz" über die UI gar nicht entstehen. Es bleibt nur unsichtbarer Round-Trip-Ballast im
geteilten `display_config`-Modell.

### PO-ENTSCHEIDUNG (2026-07-24): Unsichtbaren Rest ENTFERNEN
Der Round-Trip-Ballast wird im Compare-Pfad **entfernt**:
- **Frontend:** Compare-Bridge/Save/State hören auf, `channelLayouts` zu round-trippen
  (`compareEditorSave.ts:88-89`, `compareWizardState.svelte.ts:132`, `compareHubWizardBridge.ts:111`).
- **Backend:** einmalige **idempotente Migration** entfernt `channel_layouts` aus bestehenden
  Vergleichs-Presets (`briefings/` kind=vergleich). Automatisches Backup via `data_schema_backup.py`
  (tar.gz nach `.backups/`), da Persistenz-Änderung. Keine aktiven Produktiv-Nutzer → Feld überall leer.
- **Absicherung:** Guard-Test hält fest, dass gespeicherte Vergleichs-Presets kein `channel_layouts`
  mehr tragen und der Compare-Resolver es (weiterhin) ignoriert — verhindert stilles Zurückkehren.
- Das gemeinsame `display_config`-Modell/Trip bleibt unberührt (channel_layouts ist Trip-only-Funktion).

## Dependencies
- Upstream: `metric_catalog.py` ist SSoT für Trip **und** Compare (seit #1350) — Änderungen wirken auf beide.
- Downstream: Compare-Renderer (HTML/Plain/SMS), Compare-Engine, `LocationResult`, `/api/compare/metrics`.

## Existing Specs / Entscheidungen
- #1350 (Compare-Metrik-SSoT, fertig), #1335 (Scheibe 1), Epic #1230 (Trip/Compare-Konvergenz).
- #1287/#1291: channel_layouts als Attrappe aus Compare-Bedienung entfernt, round-trippt weiter (kein Feldverlust). ADR-0010 (Vorboten-Metriken).

## Risks & Considerations
- **Drift-assert** (`compare_metric_catalog.py:92-97`): neuer max-Eintrag MUSS in beiden Katalogen (compare_metric_catalog + compare_metric_ids) stehen, sonst Import-Fehler.
- **Renderer sind hartkodiert** auf min — kein generischer summary_fields-Iterator; jeder min-Zweig braucht einen max-Zweig.
- **Teil 2 ist im Kern eine Entscheidung, kein großer Code:** „konsistent auswerten" würde eine neue Editier-UI erfordern (widerspricht #1287/#1291 + Konvergenz-zu-einfach); „nicht anbieten" ist bereits Ist-Zustand.
- Keine aktiven Produktiv-Nutzer → channel_layouts ist überall leer; Risiko real ~0.
