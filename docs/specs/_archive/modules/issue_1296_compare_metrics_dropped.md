---
entity_id: issue_1296_compare_metrics_dropped
type: bugfix
created: 2026-07-17
updated: 2026-07-17
status: draft
version: "1.0"
tags: [compare, metrics, mapping, bugfix, weather-metrics]
workflow: fix-1296-compare-metrics-dropped
---

# Vergleichs-Mail: vier weitere still verworfene Übersichts-Metriken (#1296, Folge zu #1285)

## Approval

- [ ] Approved

## Purpose

Wählt ein Nutzer im Compare-Editor **Temperatur min** (`temp_min_c`), **Böen**
(`gust_max_kmh`), **Gewitter-Energie/CAPE** (`cape_max_jkg`) oder
**Frostgrenze** (`freezing_level_m`), erscheint in der zugestellten
Vergleichs-Mail dafür **keine** Zeile — keine Meldung, keine Fehlerausgabe,
die Auswahl verpufft folgenlos. Root Cause ist identisch zu #1285: Die vier
IDs fehlen in `FRONTEND_TO_RENDERER_METRIC_ID`
(`src/output/renderers/compare_metric_ids.py:11-28`), `resolve_enabled_metrics`
verwirft nicht-mappbare IDs kommentarlos, und keiner der vier hat eine Zeile
in `CV2_METRICS` (`src/output/renderers/email/compare_html.py:193-210`). Anders
als bei #1285 sind die vier Metriken in **zwei Klassen** zu trennen: Für
**Temperatur min** und **Böen** existiert das Tages-Aggregat bereits als
`LocationResult`-Feld (`temp_min`/`gust_max`, `src/app/user.py:128/132`) —
reines Mapping. Für **CAPE** und **Frostgrenze** existiert weder ein
`LocationResult`-Feld noch eine Live-Ableitung; `summarize_points()`
(`src/services/weather_metrics.py:985-1013`, die von #1285 eingeführte
Level-1-Aggregation aus einer nackten Stundenliste) berechnet aktuell nur
Regen/Gewitter/Sicht (via `compute_basis_metrics`) sowie Regenwahrscheinlichkeit/
UV nach — CAPE und Frostgrenze fehlen dort, obwohl die kanonischen Trip-Regeln
(`_compute_cape`, `_compute_freezing_level`) bereits existieren und die
Rohfelder (`ForecastDataPoint.cape_jkg`/`.freezing_level_m`) vorliegen.

Zweiter Teil dieser Arbeit ist ein **struktureller Guard**: `resolve_enabled_metrics`
verwirft nicht-mappbare IDs bislang still. Ohne sichtbares Signal wiederholt
sich dieser Bug-Typ bei der nächsten neu eingeführten Frontend-Metrik ein
drittes Mal (#1285 → #1296 → ?). Ein Log-Warning plus ein Kern-Konsistenz-Test,
der den Editor-Katalog (`compareMetricDefs.ts::ALL_METRICS`, 15 IDs) gegen
`FRONTEND_TO_RENDERER_METRIC_ID` abgleicht, schließt diese Lücke strukturell.

**Eigene Verifikation über den Context hinaus:** Der Klartext-Renderer
(`src/output/renderers/comparison.py::render_comparison_text`) iteriert
**nicht** über `CV2_METRICS` — er schreibt Zeilen manuell in fester Reihenfolge
(`temp_max`, `wind_max`, dann die fünf #1285-Zeilen aus `_DAILY_PLAIN_ROWS`,
dann `sunny_hours`/`cloud_avg`/Schnee). Für `temp_min`/`gust_max`/`cape_max`/
`freezing_level` existiert dort **keine** Zeile, auch nicht implizit. Ohne
Anpassung dieser Datei bliebe die Klartext-Mail nach dem Fix weiterhin
lückenhaft (HTML zeigt die Zeile, Klartext nicht) — genau die Art von
HTML/Text-Asymmetrie, die bereits in `docs/specs/modules/compare_location_summary.md`
(#1285) bewusst vermieden wurde. `comparison.py` ist daher Teil dieses Fixes,
obwohl es im Analyse-Context (`docs/context/fix-1296-compare-metrics-dropped.md`)
nicht gelistet war.

## Source

- **File:** `src/output/renderers/compare_metric_ids.py` —
  `FRONTEND_TO_RENDERER_METRIC_ID` (Zeile 11-28) um vier Einträge erweitern;
  `resolve_enabled_metrics()` (Zeile 72-89) bekommt ein Log-Warning für
  verworfene IDs statt stiller Verwerfung.
- **File:** `src/output/renderers/email/compare_html.py` — `CV2_METRICS`
  (Zeile 193-210) bekommt vier neue Zeilen; `_DAILY_AGGREGATE_FIELD`
  (Zeile 326-332) bekommt zwei neue Einträge (nur Klasse B, s.
  Implementation Details).
- **File:** `src/services/weather_metrics.py` — `summarize_points()`
  (Zeile 985-1013) um `cape_max_jkg`/`freezing_level_m` erweitert, analog
  den bestehenden Zeilen 1011-1012 (`pop_max_pct`/`uv_index_max`).
- **File:** `src/output/renderers/comparison.py` — `render_comparison_text()`
  (Zeile 50 ff.) bekommt zwei direkte Zeilen (`temp_min`, `gust_max`, analog
  den bestehenden `temp_max`/`wind_max`-Zeilen 109-114) und zwei neue
  Einträge in `_DAILY_PLAIN_ROWS` (Zeile 41-47, analog den fünf #1285-Zeilen).
- **Identifier:** `resolve_enabled_metrics()`, `summarize_points()`,
  `CV2_METRICS`, `_DAILY_AGGREGATE_FIELD`, `_DAILY_PLAIN_ROWS`.

> **Schicht-Hinweis:** Reiner Python-Core-Fix (`src/output/renderers/`,
> `src/services/weather_metrics.py`). **Deploy-Scope: Python-Core, kein
> Frontend-Build nötig.** `frontend/src/lib/components/compare/compareMetricDefs.ts::ALL_METRICS`
> enthält alle vier IDs bereits (seit Issue #1191, "Idealwerte-Schalter" —
> verifiziert: Zeile 43-46/54-58, alle vier Konstanten `TEMP_MIN`, `GUST_MAX`,
> `CAPE`, `FREEZING_LVL` sind bereits Teil von `ALL_METRICS`). Genau diese
> Lücke — Frontend-Katalog existiert bereits, Backend-Mapping fehlt — ist der
> Bug; es ist keine neue Frontend-Arbeit nötig, nur die fehlende
> Backend-Verdrahtung.

## Estimated Scope

- **LoC:** ~90-130 Implementierung (4 Dateien, additive Einträge + kurze
  Erweiterungen) + ~180-230 Tests (neue Kern-Testdatei(en) mit echten
  `ForecastDataPoint`-Fixtures, analog `test_compare_matrix_metric_selection.py`) —
  geschätzt **~270-350 gesamt**. Nahe/leicht über dem 250-LoC-Default-Limit;
  falls überschritten, User vor `loc_limit_override` explizit fragen (CLAUDE.md
  "Kein LoC-Override ohne Permission"), nicht eigenmächtig setzen.
- **Files:** 4 geändert (`compare_metric_ids.py`, `compare_html.py`,
  `weather_metrics.py`, `comparison.py`), 1-2 neu (Test-Datei(en), s. Test Plan).
  Kein Go-, kein Frontend-Change.
- **Effort:** medium (zwei unterschiedliche Fix-Klassen + struktureller Guard,
  aber kein neues Konzept — folgt 1:1 dem #1285-Muster).

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/output/renderers/compare_metric_ids.py` | MODIFY | 4 neue Mapping-Einträge; `resolve_enabled_metrics()` loggt verworfene IDs statt sie stumm zu verwerfen |
| `src/output/renderers/email/compare_html.py` | MODIFY | 4 neue `CV2_METRICS`-Zeilen; 2 neue `_DAILY_AGGREGATE_FIELD`-Einträge (CAPE, Frostgrenze) |
| `src/services/weather_metrics.py` | MODIFY | `summarize_points()` liefert zusätzlich `cape_max_jkg`/`freezing_level_m` |
| `src/output/renderers/comparison.py` | MODIFY | Klartext-Pendant: 2 direkte Zeilen (Temp min, Böen) + 2 `_DAILY_PLAIN_ROWS`-Einträge (CAPE, Frostgrenze) — sonst HTML/Text-Asymmetrie |
| `tests/unit/test_compare_extra_daily_metrics.py` | CREATE | Kern-Tests AC-1 bis AC-5, AC-7 (Bug-Repro rot vor Fix + Trip-Gleichheit) |
| `tests/unit/test_compare_metric_catalog_consistency.py` | CREATE | Kern-Konsistenz-Test AC-6 (Guard gegen Wiederholung) |

**Frontend NICHT betroffen** — kein Eintrag in dieser Tabelle für
`frontend/`, kein Frontend-Build im Deploy-Schritt für diesen Fix nötig.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `FRONTEND_TO_RENDERER_METRIC_ID` / `resolve_enabled_metrics()` (`compare_metric_ids.py:11/72`) | Const/Function | Ziel der Mapping-Erweiterung + Log-Warning |
| `CV2_METRICS` / `_DAILY_AGGREGATE_FIELD` / `_metric_value()` / `_daily_summary()` (`compare_html.py:193/326/349/335`) | Const/Function | Übersichts-Matrix-Renderer (HTML); `_daily_summary` wird bereits EINMAL je Ort gecacht (`_render_overview_table`, Zeile 448-455) — die neue Ableitung profitiert automatisch davon, kein zusätzliches Caching nötig |
| `summarize_points()` (`weather_metrics.py:985`) | Function | Dünner Wrapper um `compute_basis_metrics`/`_compute_pop`/`_compute_uv_index`; MUSS um `_compute_cape`/`_compute_freezing_level` erweitert werden (identisches Muster zu den bestehenden Zeilen 1011-1012) |
| `WeatherMetricsService._compute_cape()` (`weather_metrics.py:868`) | Method | Kanonische Trip-Regel: `max(dp.cape_jkg für alle dp)` |
| `WeatherMetricsService._compute_freezing_level()` (`weather_metrics.py:841`) | Method | Kanonische Trip-Regel: gerundeter `avg(dp.freezing_level_m für alle dp)` |
| `LocationResult.temp_min` / `.gust_max` (`user.py:128/132`) | Field | Bereits von `ComparisonEngine.run()` (Zeile 222/226) UND `dict_to_comparison_result()` (Zeile 285/289) befüllt — **verifiziert**: Klasse A ist tatsächlich reines Mapping, kein `_DAILY_AGGREGATE_FIELD`-Eintrag nötig, weil Renderer-Key == Feldname (`getattr(loc, "temp_min")`/`getattr(loc, "gust_max")` funktioniert direkt über den `field is None`-Zweig von `_metric_value`) |
| `ForecastDataPoint.cape_jkg` (`models.py:106`) / `.freezing_level_m` (`models.py:120`) | Field | Rohfelder, Quelle für die neue Live-Ableitung |
| `SegmentWeatherSummary.cape_max_jkg` (`models.py:365`) / `.freezing_level_m` (`models.py:361`) | Field | Trip-Pendant, Zielfelder von `summarize_points()` — Konvergenz Trip/Vergleich (Epic #1230) |
| `_DAILY_PLAIN_ROWS` / `render_comparison_text()` (`comparison.py:41/50`) | Const/Function | Klartext-Pendant der Übersichts-Matrix — **nicht** im ursprünglichen Analyse-Context gelistet, aber verifiziert notwendig (s. Purpose) |
| `ALL_METRICS` (`compareMetricDefs.ts:54-58`) | Const (Frontend, unverändert) | Enthält alle vier IDs bereits (seit #1191); Referenz-Katalog für den Konsistenz-Test (AC-6) |
| `test_compare_matrix_metric_selection.py` (`tests/unit/`) | Test-Vorbild | Muster für Fixtures/Assertions dieser Arbeit: echte `ForecastDataPoint`, `resolve_enabled_metrics()`, HTML/Text-Extraktion, Gleichheits-Assert gegen `WeatherMetricsService` |

## Implementation Details

**1. `compare_metric_ids.py` — Mapping + Log-Warning:**

```python
FRONTEND_TO_RENDERER_METRIC_ID: dict[str, str] = {
    # ... bestehende 11 Eintraege unveraendert ...
    "temp_min_c": "temp_min",
    "gust_max_kmh": "gust_max",
    "cape_max_jkg": "cape_max",
    "freezing_level_m": "freezing_level",
}

logger = logging.getLogger(__name__)

def resolve_enabled_metrics(active_metrics):
    if not active_metrics:
        return None
    if not isinstance(active_metrics, list):
        return None
    unmapped = [m for m in active_metrics if m not in FRONTEND_TO_RENDERER_METRIC_ID]
    if unmapped:
        logger.warning(
            "resolve_enabled_metrics: %s ohne Renderer-Mapping — Auswahl "
            "wird ignoriert statt angezeigt (vgl. #1285/#1296)", unmapped,
        )
    resolved = {FRONTEND_TO_RENDERER_METRIC_ID[m] for m in active_metrics
                if m in FRONTEND_TO_RENDERER_METRIC_ID}
    return resolved or None
```

Die Renderer-ID-Strings (`temp_min`, `gust_max`, `cape_max`, `freezing_level`)
sind Implementierungsdetail — sie müssen nur eindeutig, konsistent zum
bestehenden Namensschema und in `CV2_METRICS`/`_DAILY_AGGREGATE_FIELD`/
`_DAILY_PLAIN_ROWS` korrekt gemappt sein.

**2. `compare_html.py` — Übersichts-Zeilen (HTML):**

```python
CV2_METRICS = [
    # ... bestehende Zeilen unveraendert ...
    {"key": "temp_min", "label": "Temp min", "unit": "°C"},
    {"key": "gust_max", "label": "Böen", "unit": "km/h", "sev": _sev_gust},
    {"key": "cape_max", "label": "CAPE", "unit": "J/kg"},
    {"key": "freezing_level", "label": "Frostgrenze", "unit": "m"},
]

_DAILY_AGGREGATE_FIELD: dict[str, str] = {
    # ... bestehende 5 Eintraege unveraendert ...
    "cape_max": "cape_max_jkg",
    "freezing_level": "freezing_level_m",
}
```

`temp_min`/`gust_max` brauchen **keinen** `_DAILY_AGGREGATE_FIELD`-Eintrag
(Klasse A, s. Dependencies) — `_metric_value()` liest sie über den
`field is None`-Zweig direkt per `getattr(loc, key)`. `cape_max`/`freezing_level`
brauchen den Eintrag (Klasse B), weil `LocationResult` dafür kein eigenes Feld
bekommt — der Wert kommt ausschließlich aus der Live-Ableitung
(`_daily_summary()` → `summarize_points()`), identisch zum ursprünglichen
`uv_max`-Muster vor #1285 (Issue #1110).

**Hinweis Severity:** `_sev_temp()` ist eine Hitze-Schwelle (`>=34/31/28`) und
darf **nicht** unverändert für `temp_min` übernommen werden — fachlich falsch
für eine Kälte-Kennzahl. Kein AC verlangt Severity-Färbung für die vier neuen
Zeilen; `sev` kann fehlen (wie bei `sunny_hours`/`cloud_avg` bereits heute).

**3. `weather_metrics.py` — `summarize_points()` erweitern:**

```python
def summarize_points(points: list) -> Optional[SegmentWeatherSummary]:
    ...
    summary = svc.compute_basis_metrics(ts)
    summary.pop_max_pct = svc._compute_pop(ts)
    summary.uv_index_max = svc._compute_uv_index(ts)
    summary.cape_max_jkg = svc._compute_cape(ts)
    summary.freezing_level_m = svc._compute_freezing_level(ts)
    return summary
```

**4. `comparison.py` — Klartext-Pendant:**

```python
_DAILY_PLAIN_ROWS = (
    # ... bestehende 5 Eintraege unveraendert ...
    ("cape_max", "CAPE", lambda v: f"{v:.0f} J/kg"),
    ("freezing_level", "Frostgrenze", lambda v: f"{v:.0f} m"),
)

# im Zeilen-Block direkt nach temp_max/wind_max (Zeile ~109-114):
if _metric_visible("temp_min"):
    temp_min = loc_result.temp_min
    lines.append(f"   Temp min: {format_value('temperature', temp_min, style='plain')}"
                 if temp_min is not None else "   Temp min: -")
if _metric_visible("gust_max"):
    gust_max = loc_result.gust_max
    lines.append(f"   Böen: {format_value('wind', gust_max, style='plain')}"
                 if gust_max is not None else "   Böen: -")
```

`temp_min`/`gust_max` lesen — wie `temp_max`/`wind_max` bereits heute — direkt
`loc_result.temp_min`/`.gust_max` (Klasse A, kein `_metric_value()`-Umweg
nötig). `cape_max`/`freezing_level` laufen über `_DAILY_PLAIN_ROWS` +
`_metric_value()`, identisch zu den fünf #1285-Zeilen (Klasse B).

**5. Struktureller Guard (AC-6), kein Code-Snippet:** Ein Kern-Test hält die
15 `ALL_METRICS`-Keys aus `compareMetricDefs.ts` (hart hinterlegt mit
Kommentar-Verweis auf die Quelldatei — Python kann kein TypeScript parsen)
gegen `FRONTEND_TO_RENDERER_METRIC_ID.keys()` und schlägt fehl, sobald eine
davon kein Mapping hat. Nach diesem Fix ist die Erwartung `set(FRONTEND_TO_RENDERER_METRIC_ID) == set(<15 ALL_METRICS-Keys>)` — 1:1-Deckung.

## Expected Behavior

- **Input:** `display_config.active_metrics` enthält eine oder mehrere der
  vier Frontend-IDs `temp_min_c`, `gust_max_kmh`, `cape_max_jkg`,
  `freezing_level_m` (einzeln oder in Kombination mit anderen Metriken).
- **Output:** Die zugestellte Vergleichs-Mail (HTML **und** Klartext) zeigt
  für jede gewählte dieser vier Metriken eine eigene Übersichts-Zeile mit
  einem echten Tageswert je Ort — nicht mehr stillschweigend nichts.
  `enabled_metrics=None` (keine Auswahl getroffen) zeigt weiterhin alle
  mappbaren Zeilen, jetzt inklusive der vier neuen.
- **Side effects:** Keine — reine Lese-/Formatierungslogik, `LocationResult`
  bleibt transient (kein Persistenz-Risiko trotz `app/user.py` als
  schema-relevanter Datei laut CLAUDE.md; identische Begründung wie in
  `docs/specs/modules/compare_location_summary.md`, Abschnitt
  "Datenschema-Sicherheit" — hier ohnehin unberührt, da Klasse A/B keine
  neuen `LocationResult`-Felder braucht).

## Acceptance Criteria

- **AC-1:** Given ein Nutzer hat im Compare-Editor „Temperatur min"
  (`temp_min_c`) ausgewählt, When die Vergleichs-Mail (HTML und Klartext)
  gerendert wird, Then erscheint für jeden Ort mit Stundendaten eine
  „Temp min"-Zeile mit dem Tages-Minimum aus `t2m_c`, und dieser Wert stimmt
  mit dem entsprechenden Trip-Pfad-Aggregat bei identischen Stundendaten
  überein.
  - Test: `resolve_enabled_metrics(["temp_min_c"])` → Matrix-Zeile „Temp min"
    mit echtem Wert; Wert == `WeatherMetricsService().compute_basis_metrics(...).temp_min_c`
    für dieselben `ForecastDataPoint`.

- **AC-2:** Given ein Nutzer hat „Böen" (`gust_max_kmh`) ausgewählt, When die
  Vergleichs-Mail gerendert wird, Then erscheint eine „Böen"-Zeile mit dem
  Tages-Maximum aus `gust_kmh`, Wert identisch zum Trip-Pfad-Aggregat bei
  gleichen Stundendaten.
  - Test: analog AC-1, gegen `.gust_max_kmh`.

- **AC-3:** Given ein Nutzer hat „Gewitter-Energie (CAPE)" (`cape_max_jkg`)
  ausgewählt, When die Vergleichs-Mail gerendert wird, Then erscheint eine
  CAPE-Zeile mit dem Tages-Maximum aus `cape_jkg` je Ort (dieselbe Regel wie
  `WeatherMetricsService._compute_cape`), Wert identisch zum Trip-Pfad.
  - Test: `resolve_enabled_metrics(["cape_max_jkg"])` → Zeile mit echtem Wert;
    Wert == `svc._compute_cape(ts)` für identische Stundendaten.

- **AC-4:** Given ein Nutzer hat „Frostgrenze" (`freezing_level_m`)
  ausgewählt, When die Vergleichs-Mail gerendert wird, Then erscheint eine
  „Frostgrenze"-Zeile mit dem gerundeten Tages-Durchschnitt aus
  `freezing_level_m` je Ort (dieselbe Regel wie `_compute_freezing_level`),
  Wert identisch zum Trip-Pfad.
  - Test: `resolve_enabled_metrics(["freezing_level_m"])` → Zeile mit echtem
    Wert; Wert == `svc._compute_freezing_level(ts)` für identische Stundendaten.

- **AC-5:** Given `hourly_data` eines Ortes enthält `cape_jkg`- und
  `freezing_level_m`-Werte, When `summarize_points()` für diese Stundenliste
  aufgerufen wird, Then liefert das Ergebnis zusätzlich zu den bereits
  bestehenden Feldern auch `cape_max_jkg` und `freezing_level_m`, berechnet
  nach denselben Regeln wie der Trip-Pfad — belegt durch einen
  Gleichheits-Assert zwischen `summarize_points(...)`-Ergebnis und
  `WeatherMetricsService._compute_cape`/`._compute_freezing_level` auf
  identischen Rohdaten.
  - Test: Reiner Unit-Test ohne Renderer-Umweg — `summarize_points(hourly).cape_max_jkg == svc._compute_cape(ts)` und analog für `freezing_level_m`.

- **AC-6 (struktureller Guard):** Given eine im Editor wählbare Metrik-ID hat
  keinen Eintrag in `FRONTEND_TO_RENDERER_METRIC_ID`, When
  `resolve_enabled_metrics()` diese Auswahl auflöst, Then erzeugt das System
  ein sichtbares Log-Warning statt der bisherigen stillen Verwerfung; und ein
  Kern-Konsistenz-Test vergleicht die 15 `ALL_METRICS`-Keys aus
  `compareMetricDefs.ts` gegen `FRONTEND_TO_RENDERER_METRIC_ID` und schlägt
  fehl, sobald künftig eine wählbare Metrik ohne Mapping hinzukommt. Dies ist
  ein Regressions-**Test** der Kern-Suite, kein neuer Commit-Hook/Prozess-Gate
  (Regel-Budget CLAUDE.md — kein neues Pflicht-Gate).
  - Test: `resolve_enabled_metrics(["nicht_gemappte_id"])` mit `caplog`/Logger-
    Capture prüft, dass eine WARNING-Zeile erzeugt wird; separater Test
    `set(FRONTEND_TO_RENDERER_METRIC_ID) == {<hart hinterlegte 15 Keys, mit
    Kommentar-Verweis auf compareMetricDefs.ts::ALL_METRICS>}`.

- **AC-7 (Invariante/Regressionsschutz):** Given die bereits gemappten 11
  Metriken (6 ursprüngliche + 5 aus #1285) und der Default „keine Auswahl =
  alle Zeilen sichtbar" (`enabled_metrics=None`), When die Vergleichs-Mail
  nach diesem Fix erneut gerendert wird, Then bleiben diese 11 Metriken
  unverändert sichtbar mit unveränderten Werten, und `enabled_metrics=None`
  zeigt weiterhin alle mappbaren Zeilen — jetzt inklusive der vier neuen,
  aber ohne dass eine bestehende Zeile verschwindet oder sich ihr Wert
  ändert.
  - Test: Regressionstest mit vorher aufgezeichneter Zeilen-/Werte-Liste bei
    fester Auswahl (`temp_max_c`, `wind_max_kmh`, `cloud_avg_pct` — analog
    dem bestehenden `test_unselected_new_metrics_leave_existing_matrix_unchanged`
    aus `test_compare_matrix_metric_selection.py`) vorher/nachher identisch.

## Known Limitations

- **Kein Zusammenfassungssatz-Pendant:** Wie bereits für Windrichtung/
  Sonnenstunden/Schnee in `docs/specs/modules/compare_location_summary.md`
  dokumentiert, kennt der geteilte Fließtext-Baustein
  (`CompactSummaryFormatter`) keine `_format_temp_min`/`_format_gust`/
  `_format_cape`/`_format_freezing_level`-Methode. `RENDERER_TO_TRIP_METRIC_ID`
  (`compare_metric_ids.py:38-45`) bleibt für diese vier Metriken unverändert
  ohne Eintrag — sie erscheinen in der Übersichts-Matrix, aber nicht im
  Zusammenfassungssatz je Ort. Kein Teil dieses Fixes.
- **Korridor-Markierung (`CORRIDOR_METRIC_TO_HOUR_KEY`) unverändert:** Enthält
  bereits `gust_max_kmh` → `gust_kmh` (Issue #1231, Stundenspalten-Korridor).
  `temp_min_c`/`cape_max_jkg`/`freezing_level_m` werden dort bewusst **nicht**
  ergänzt — dieselbe Begründung wie bei `precip_sum_mm`/`uv_index_max`/
  `visibility_min_m`: Tages-Aggregat gegen Einzelstundenwert wäre fachlich
  falsch. Nicht Teil dieses Fixes.
- **Severity-Färbung optional/unvollständig:** `cape_max` und `freezing_level`
  bekommen in dieser Arbeit keine Severity-Schwellen (kein `sev`-Key nötig
  laut ACs). `temp_min` darf **nicht** `_sev_temp` (Hitze-Schwelle) wiederver-
  wenden — entweder ohne Färbung oder mit einer neuen, eigenen Kälte-Schwelle,
  Entscheidung liegt bei der Implementierung.
- **Konsistenz-Test mit hart hinterlegter Kopie:** Die Kern-Schicht kann kein
  TypeScript parsen (CLAUDE.md Test-Politik: deterministisch, kein Cross-
  Language-Tooling). Der AC-6-Konsistenz-Test vergleicht gegen eine im Python-
  Test hart hinterlegte Kopie der 15 `ALL_METRICS`-Keys mit Kommentar-Verweis
  auf die Quelldatei — bei künftigen Änderungen an `compareMetricDefs.ts`
  muss diese Kopie von Hand nachgezogen werden. Akzeptierter Kompromiss, kein
  neues Prozess-Gate (Regel-Budget CLAUDE.md).

## Test Plan

Kern-Schicht (deterministisch, keine Mocks, echte aufgezeichnete
`ForecastDataPoint`-Fixtures — Vorbild: `tests/unit/test_compare_matrix_metric_selection.py`):

| Test | Datei | Deckt |
|---|---|---|
| `test_selected_temp_min_metric_appears_in_overview_matrix` (**rot vor Fix**) | `tests/unit/test_compare_extra_daily_metrics.py` | AC-1 |
| `test_selected_gust_max_metric_appears_in_overview_matrix` (**rot vor Fix**) | `tests/unit/test_compare_extra_daily_metrics.py` | AC-2 |
| `test_selected_cape_metric_appears_in_overview_matrix` (**rot vor Fix**) | `tests/unit/test_compare_extra_daily_metrics.py` | AC-3 |
| `test_selected_freezing_level_metric_appears_in_overview_matrix` (**rot vor Fix**) | `tests/unit/test_compare_extra_daily_metrics.py` | AC-4 |
| `test_summarize_points_yields_cape_and_freezing_level` | `tests/unit/test_compare_extra_daily_metrics.py` | AC-5 |
| `test_plaintext_shows_all_four_new_rows` (Klartext-Pendant, alle vier) | `tests/unit/test_compare_extra_daily_metrics.py` | AC-1 bis AC-4 (Klartext) |
| `test_unmapped_metric_logs_warning_instead_of_silent_drop` | `tests/unit/test_compare_metric_catalog_consistency.py` | AC-6 |
| `test_all_frontend_metric_ids_have_renderer_mapping` | `tests/unit/test_compare_metric_catalog_consistency.py` | AC-6 |
| `test_existing_eleven_metrics_unchanged_after_fix` (Regression, Bestandsschutz) | `tests/unit/test_compare_extra_daily_metrics.py` | AC-7 |

Bug-Nachweis (CLAUDE.md Test-Politik): Die vier `test_selected_*`-Tests
reproduzieren die stille Verwerfung wörtlich aus Nutzersicht — Auswahl
gesetzt, keine Meldung, Zeile fehlt (rot vor Fix, grün nach Fix), identisches
Muster zu `test_selected_rain_metric_appears_in_overview_matrix` aus #1285.

## Validierung

- **Renderer-Commit-Gate #811:** `compare_html.py` liegt unter
  `src/output/renderers/email/*.py` und ist damit gate-pflichtig — vor
  Commit MUSS `tests/tdd/test_issue_811_mode_matrix.py` grün sein UND ein
  `briefing_mail_validator.py`-Lauf gegen eine echt zugestellte Trip-Mail
  (Staging) vorliegen (Trip-Regression, AC-7 für den Trip-Pfad).
  `compare_metric_ids.py`, `weather_metrics.py` und `comparison.py` liegen
  **nicht** in der Gate-Dateiliste von #811.
- **Compare-Mail-Validierung (PFLICHT vor „E2E bestanden"):**
  `email_spec_validator.py` (Marker-Header `X-GZ-Mail-Type: compare`) gegen
  eine echt zugestellte Staging-Mail aus dem Stalwart-Test-Postfach
  (`gregor-test@henemm.com`) — deckt AC-1 bis AC-4 auf Ebene der
  tatsächlich ausgelieferten Mail ab (HTML **und** Klartext-Teil prüfen,
  wegen der in Purpose dokumentierten HTML/Text-Asymmetrie-Gefahr).
- `app/user.py` ist in dieser Arbeit **nicht** geändert (kein neues
  `LocationResult`-Feld nötig, s. Dependencies/Implementation Details) —
  `data_schema_backup.py` wird daher nicht ausgelöst.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Dieser Fix folgt exakt dem mit #1285 etablierten Muster
  (Mapping-Eintrag in `FRONTEND_TO_RENDERER_METRIC_ID` + `CV2_METRICS`-Zeile +
  optionale Live-Ableitung via `summarize_points()` für Metriken ohne eigenes
  `LocationResult`-Feld). Es wird kein neues Konzept, keine neue Abhängigkeit
  und keine strukturelle Entscheidung mit Tragweite eingeführt — lediglich
  vier weitere additive Einträge in bereits bestehenden Übersetzungstabellen
  und zwei weitere Zeilen in einer bereits bestehenden Level-1-Aggregations-
  funktion. Der strukturelle Guard (AC-6) ist ein Test, kein Architektur-
  Element.

## Changelog

- 2026-07-17: Initial spec created (Issue #1296, Folge zu #1285). Eigene
  Verifikation ergab: (a) Klasse A (`temp_min_c`/`gust_max_kmh`) ist
  tatsächlich reines Mapping — `ComparisonEngine.run()` UND
  `dict_to_comparison_result()` befüllen `LocationResult.temp_min`/`.gust_max`
  bereits, kein `_DAILY_AGGREGATE_FIELD`-Eintrag nötig; (b) `comparison.py`
  (Klartext-Renderer) ist zusätzlich zum ursprünglichen Context-Doc als
  betroffene Datei identifiziert worden — sonst bliebe die Klartext-Mail nach
  dem Fix weiterhin lückenhaft (HTML/Text-Asymmetrie); (c) `ALL_METRICS` im
  Frontend-Katalog enthält alle vier IDs bereits seit #1191, kein
  Frontend-Change nötig.
