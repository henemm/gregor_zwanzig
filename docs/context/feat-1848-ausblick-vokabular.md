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

## PO-Entscheid 2026-08-18 — Zuschnitt festgelegt

Aus R1 folgt: Scheibe A ist **nicht** mechanisch ausführbar. Vorgelegt wurden
drei Wege; der PO hat entschieden:

> **Nur die Doppelpflege beseitigen.** Die Auswahl bleibt für den Nutzer exakt
> wie heute — getrennte Minimum-/Maximum-Spalten im Ausblick bleiben möglich.
> Beseitigt wird ausschließlich, dass dieselbe Auswahlregel (ADR-0050) an zwei
> Stellen gepflegt wird. Dazu ein Wächter, der eine erneute Zweitschrift
> verhindert.

**Ausdrücklich NICHT Teil dieser Scheibe** (eigenes Ticket im Wetter-Register-
Epic #1435):

- Umstellung des Speicherformats `outlook_metrics` von Paaren auf Kennungen
- Neue Katalog-Kennungen je Auswertungsrichtung (`temperature_min` o. ä.)
- Rückführung des Ortsvergleich-Katalogs (Scheibe B des Issues)
- Jede Änderung an Frontend, API-Vertrag oder gespeicherten Daten

**Folge für die Risiken:** R1 entfällt (keine Vokabular-Änderung), R3/R4
entfallen (keine Migration — zusätzlich gemessen: auf Produktion und Staging
ist heute **keine einzige** `outlook_metrics`-Auswahl gespeichert, bei
positiver Gegenprobe über `display_config`), R5 entfällt (Frontend unberührt).
R2 und R6 bleiben als Beobachtung bestehen, ohne in dieser Scheibe behandelt
zu werden.

## Technischer Ansatz (Analyse)

Heute existiert die Kaskadenregel zweimal, verhaltensgleich:

| Ort | Eingabe | Schnittmenge |
|---|---|---|
| `models.py:898-921` `_clip_to_global_maximum()` | `list[MetricConfig]` | `mc.metric_id` |
| `compare_outlook_metric_ids.py:78-102` `resolve_trip_outlook_metrics()` | `list[dict]` | `e["metric_id"]` |

Beide bilden dieselben Regeln D1–D4 ab, nur über verschiedene Trägertypen.
Der gemeinsame Kern ist **die erlaubte Kennungsmenge**, nicht der Träger:

- **Eine Quelle:** `UnifiedWeatherDisplayConfig` erhält eine öffentliche
  Methode, die die erlaubte Kennungsmenge für einen Report-Typ liefert —
  einschließlich Regel D4 („keine Grundauswahl" ⇒ kein Maximum, ausgedrückt
  als eigener Rückgabewert, nicht als leere Menge; die Unterscheidung ist der
  ganze Punkt von D4).
- **Zwei Aufrufer:** `_clip_to_global_maximum()` und
  `resolve_trip_outlook_metrics()` filtern beide über diese Menge und
  enthalten selbst keine Regel mehr.
- Kein neuer Import in Richtung `models.py` nötig: der Ausblick-Resolver
  bekommt das `dc`-Objekt bereits übergeben.

### 🔴 Es gibt eine DRITTE Umsetzung — die NICHT eingemeindet werden darf

`src/output/renderers/compare_metric_ids.py:200-243`
`resolve_channel_enabled_metrics()` setzt dieselbe ADR-0050-Regel 1/2 für die
Kanal-Auswahl des **Ortsvergleichs** um und verweist im Docstring selbst auf
`_clip_to_global_maximum()`. Sie ist aber **nicht** wortgleich:

| Fall | Trip (`_clip_to_global_maximum`, D4) | Ortsvergleich (`resolve_channel_enabled_metrics`) |
|---|---|---|
| Grundauswahl fehlt (`None`) | nicht schneiden | nicht schneiden |
| Grundauswahl leer (`[]`) | **nicht schneiden** — „kein Maximum" | **auf leer schneiden** — „leer heißt leer" (#1366) |

Beim Trip sind `None` und `[]` beide falsy und laufen in denselben Zweig; beim
Ortsvergleich sind sie bewusst getrennt. Das ist kein Versehen, sondern zwei
verschiedene Zusagen an zwei verschiedenen Flächen (AC-16 aus #1720 S1 hier,
#1366 dort).

**Folge für diese Scheibe:** Zusammengelegt werden ausschließlich die **zwei
Trip-seitigen** Stellen (Kanal-Layout und Ausblick), die nachweislich
verhaltensgleich sind. `resolve_channel_enabled_metrics()` bleibt unangetastet
— eine Eingemeindung würde eine der beiden Zusagen brechen. Der Wächter muss
diese Fläche deshalb ausdrücklich **aussparen**, sonst zementiert er einen
Fehler.

**Wächter (Verhalten, nicht Dateiinhalt):** ein Test, der dieselben
Kaskaden-Fälle — inklusive D4 und des `selectable`-Gates — durch **beide**
Flächen schickt (Kanal-Layout und Ausblick) und identische Entscheidungen
verlangt. Die Erwartungswerte werden im Test fest hinterlegt und **nicht** aus
dem Prüfling abgeleitet, sonst bliebe die Mutations-Gegenprobe grün
(Lehre aus #1467: Test und Prüfling dürfen nicht dieselbe Quelle teilen).
