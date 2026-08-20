# Context: feat-1848-a2-outlook-kennungen

Scheibe A2 von #1848 Teil A. Erstellt 2026-08-20, Phase 1.
Basis: Branch `feat-1848-a2-outlook-kennungen` auf `ddcacdbe` (enthaelt den A1-Merge `d4764b92`).

## Request Summary

Der 3-Tages-Ausblick speichert seine Spaltenauswahl heute als **Paare**
`{"metric_id": ..., "aggregation": ...}`. Er soll auf **reine Kennungen** umgestellt werden —
dasselbe Vokabular, das Kanal-An/Aus, Reihenfolge, SMS-Kuerzel und Schwellwerte ohnehin
benutzen. Damit verliert der Ausblick sein eigenes, viertes Vokabular und wird eine weitere
Flaeche derselben Metrik-Kaskade.

A1 (Gehzeit-Fenster + Spannen-Zelle) ist seit `d4764b92` in Produktion. A3 (Kanal-Modul im
Frontend) bleibt danach offen.

## 🟢 Der Befund, der die Scheibe traegt: nur ZWEI Groessen sind mehrdeutig

Gemessen gegen die echten Register (nicht aus dem Code abgeleitet):

| `metric_id` | `summary_fields` | `available_aggregations()` | im Compare-Katalog |
|---|---|---|---|
| `temperature` | `min`, `max`, `avg` | `["min","max","avg"]` | **nur `min` + `max`** — `avg` fehlt |
| `wind_chill` | `min`, `max` | `["min","max"]` | `min` + `max` |
| `precipitation` | `sum`, `onset` | `["sum"]` | nur `sum` |
| `thunder` | `max`, `onset` | `["max"]` | nur `max` |

`onset` ist kein Auswertungs-Vokabular (nicht in `_AGGREGATION_ORDER`, keine Katalogzeile) —
`_catalog_entry("precipitation","onset")` liefert `None`, der Eintrag wuerde verworfen.

⇒ **Von den waehlbaren Ausblick-Groessen tragen genau zwei mehr als eine Auswertung.** Bei allen
uebrigen bestimmt die Kennung ihr Datenfeld eindeutig. Die Ableitung „Kennung → alle Auswertungen
mit Katalogzeile" ist damit fuer `wind_chill` verlustfrei (2 von 2) und fuer `temperature`
ebenfalls, solange `avg` keine Compare-Katalogzeile hat.

Und genau diese beiden faltet A1s `_merge_min_max_pairs()` anschliessend wieder zu **einer**
Spannen-Spalte zusammen. Wer „Temperatur" waehlt, bekommt eine Spalte `9/27` — das vom PO
bestellte Verhalten, ohne neue Mechanik.

## 🔴 Der technische Kernpunkt

`_merge_min_max_pairs()` (`compare_outlook_metric_ids.py:167-178`, **A1-Neuzugang**) erkennt
„Tief und Hoch sind beide gewaehlt" **ausschliesslich an den beiden Paaren**:

```python
if col.get("kind") == "range" and col.get("aggregation") in ("min", "max"):
    by_metric.setdefault(col["metric_id"], {})[col["aggregation"]] = i
...
if "min" in aggs and "max" in aggs:
```

Die Information, die A2 aus dem **Speicherformat** entfernt, ist also genau die, an der A1 das
Zusammenfassen festmacht. Sie muss aus dem **Katalog** nachgeliefert werden
(`available_aggregations()` + `key_for()`), nicht aus der gespeicherten Auswahl.

## 🔴 Folge, die festgehalten werden muss: A1s Einzelwert-Zweig wird unerreichbar

A1 hat bewusst gebaut: „ist nur Tief **oder** nur Hoch gewaehlt, bleibt es beim Einzelwert"
(AC-5, Docstring `compare_outlook_metric_ids.py:162-166`). Nach A2 laesst sich fuer
`temperature`/`wind_chill` **keine halbe Auswahl mehr speichern** — der Zweig wird fuer diese
beiden Groessen toter Code.

Das ist die direkte Folge des PO-Entscheids („Der Nutzer waehlt Temperatur — eine Zeile, wie bei
den Kanaelen. Nur-das-Hoch-Zeigen entfaellt."), also **gewollt** — aber es darf nicht unbemerkt
liegenbleiben. Zu entscheiden ist im Zuschnitt, ob der Zweig entfernt oder als bewusst
unerreichbare Rueckfallebene dokumentiert wird.

## 🔴 Strukturelle Falle: Werte und Ueberschriften kommen aus ZWEI Aufrufen

`outlook_columns()` wird je Renderer **zweimal** aufgerufen — einmal fuer die Kopfzeile, einmal
fuer die Zellen — und beide werden nur ueber den **Listenindex** verbunden:

| Renderer | Kopf | Zellen |
|---|---|---|
| HTML | `outlook.py:131` | `outlook.py:729` (in `build_outlook_row`) |
| Klartext | `outlook.py:339` | dieselbe `cells`-Liste |
| Kompakt | `compact.py:278` → `:283-285` | dito |
| Telegram | `narrow.py:586` → `:591-593` | dito |

⇒ Die abgeleitete Spaltenmenge muss **streng deterministisch und reihenfolgestabil** sein.
Weicht sie zwischen den beiden Aufrufen ab, verrutschen Werte gegen Beschriftungen — **still**,
ohne Ausnahme.

## Related Files

### Persistenz / Datenmodell

| Datei | Zeilen | Rolle |
|---|---|---|
| `src/app/models.py` | 839-844 | **Feld-Definition** `outlook_metrics: Optional[list[dict]] = None` auf `UnifiedWeatherDisplayConfig` |
| `src/app/models.py` | 877-902 | `allowed_metric_ids_for_report_type()` — Grundauswahl-Schnitt (D4: leer ⇒ `None`, kein Schnitt) |
| `src/app/loader.py` | 948 | **Lesepfad** `data.get("outlook_metrics")` — roh, **ohne** Normalisierung/Validierung |
| `src/app/loader.py` | 1556-1561 | **Schreibpfad** — bedingt (`is not None`), roh; **einzige** Serialisierungsstelle |
| `src/services/report_config_resolver.py` | 189-193, 291-294 | `CompareRenderOptions.outlook_metrics`; `[]` ⇒ `outlook_enabled = False` |

### Renderpfad

| Datei | Zeilen | Rolle |
|---|---|---|
| `src/output/renderers/compare_outlook_metric_ids.py` | 45-75 | `resolve_outlook_metrics()` — **einziger Validierer**: Katalogpruefung, Dedup ueber `(metric_id, aggregation)`, Drop + `logger.warning` |
| dito | 78-109 | `resolve_trip_outlook_metrics()` — dito + Kaskaden-Schnitt (nur auf `metric_id`) |
| dito | 112-151 | `outlook_columns()` — Paar ⇒ Spaltenbeschreibung, dann Merge, dann Label-Kollisionsaufloesung |
| dito | 154-200 | `_merge_min_max_pairs()` — **A1**, faltet min+max zu `field_min`/`field_max` |
| dito | 238-269 | `format_outlook_range_cell()` — **A1**, `"9/27"`, ASCII-Schraegstrich, **ohne** Einheit |
| `src/output/renderers/email/outlook.py` | 128-155 / 157-170 | Katalog-Zweig vs. **feste 7-Spalten-Altform** |
| dito | 458-506 | **A1**: `_HIKING_FIELD_MAP`, `_hiking_or_summary()`, `_resolve_hiking_extrema()` |
| dito | 735-740 | `cells`-Schleife erkennt `field_min`/`field_max` ⇒ eine Zelle |
| `src/output/renderers/email/helpers.py` | 947 | **A1**: `temp_str = f"{tl}/{th}°C"` (Altform-Klartext, **mit** Einheit) |
| `src/output/renderers/trip_report.py` | 49, 209, 224, 308 | **Einzige** Aufloesung im Trip-Versandpfad, aus `_dc_uncollapsed` |
| `src/output/renderers/email/{html,plain,compact}.py`, `narrow.py`, `email/compare_html.py`, `comparison.py` | s. o. | Drei-Werte-Auswertung + Kopf/Zellen-Indexbindung |
| `src/services/{compare_preview_service,scheduler_dispatch_service}.py` | 204 / 500 | Vorschau und Versand teilen dieselbe aufgeloeste Liste |

### Kataloge

| Datei | Zeilen | Rolle |
|---|---|---|
| `src/app/metric_catalog.py` | 42, 899-910, 942-954 | `summary_fields`, `summary_field_for()`, `available_aggregations()` — **was gerechnet wird** |
| `src/output/renderers/compare_metric_catalog.py` | 87-178, 244-260, 262-336 | `COMPARE_METRIC_CATALOG` (26 Rohzeilen, 25 ausgeliefert), `key_for()` — **was waehlbar ist** |

### Go — vollstaendig transparent

`display_config` ist in Go ein opakes `map[string]interface{}` (`internal/model/trip.go:111`,
`compare_preset.go:48`, `location.go:16`). Der Merge ist ein **flacher Top-Level-Merge**
(`internal/handler/config_merge.go:11-22`) und inspiziert Listenelemente **nie**.
`outlookMetrics`/`OutlookMetrics`: 0 Treffer im gesamten Go-Code (die 25 `outlook`-Treffer
betreffen ausnahmslos `outlook_enabled`).

⇒ **Keine Go-Aenderung noetig** — aber auch **kein Go-seitiger Schutz**: eine Formatverletzung
wandert unbemerkt durch bis in den Python-Renderer.

## Existing Patterns

- **Drei-Werte-Semantik (ADR-0037/ADR-0055):** `None`/fehlt = feste 7 Spalten · `[]` = Block
  entfaellt ganz · gefuellt = gewaehlte Spalten. Sie wird **allein** durch den bedingten
  Schreibpfad (`loader.py:1556-1561`) aufrechterhalten und an **sechs** Stellen ausgewertet
  (html/plain/compact/narrow/report_config_resolver/compare_html).
- **„EINE Aufloesung, durchgereicht"** (ADR-0055 Punkt 4, Adversary-Finding F001 HIGH):
  `trip_report.py:209` loest genau einmal auf und gibt dieselbe Variable an Mail **und**
  Telegram. Nicht zweimal aufloesen.
- **Ungekollabierter `dc`:** Der Ausblick hat bewusst **keine** Kanal-Ebene (ADR-0053, AC-17) —
  `resolve_trip_outlook_metrics()` braucht `_dc_uncollapsed`.
- **Bestandsableitung:** Muster `_DERIVED_METRIC_RULES` / `_append_derived_metrics()`
  (`loader.py:751-767`) aus #1728 S1, inklusive Serialisierungsfilter beim Speichern.

## Dependencies

- **Upstream:** `metric_catalog` (`summary_fields`, `available_aggregations`),
  `compare_metric_catalog` (`key_for`), `models.allowed_metric_ids_for_report_type()`
- **Downstream:** vier Renderer (HTML/Klartext/Kompakt/Telegram) in **beiden** Flaechen,
  Loader-Persistenz, Frontend-Typ + Schreiber, `docs/reference/api_contract.md`

## Existing Specs & ADRs

- `docs/adr/0037-datengetriebener-ausblick-aus-metrik-katalog.md:48, 79` — Neuformat-Festlegung
- `docs/adr/0055-trip-ausblick-waehlbare-spalten.md:54-60, 77-88, 90-109` — Trip-Ausblick,
  Semantik-Uebertragung, „EINE Aufloesung"
- `docs/adr/0050-metrik-kaskade-verfeinerung-nicht-ersetzung.md:137` — Regel D4
- `docs/adr/0053-compare-kanal-eigene-metrikauswahl-uebersicht.md:50, 124` — Ausblick bewusst
  ohne Kanal-Ebene
- `docs/specs/modules/issue_1361_1368_ausblick_konfigurierbar.md` — Ursprung des Paar-Vokabulars
- `docs/specs/modules/feat_1720_s1_trip_ausblick_metriken.md` — AC-14/15/16 zur Kaskade
- `docs/context/feat-1848-a1-tagesfenster-kennungen.md` — A1-Zuschnitt, Messung, PO-Entscheide

## Risks & Considerations

**R-A2-1 — Der Merge haengt an der Information, die A2 entfernt.** Siehe Kernpunkt oben.
Die Ableitung muss aus dem Katalog kommen; ein Ableiten aus der gespeicherten Auswahl ist nach
A2 nicht mehr moeglich.

**R-A2-2 — Kopf/Zellen-Indexbindung.** Zwei getrennte `outlook_columns()`-Aufrufe, vier
Renderer, Verbindung nur ueber den Listenindex. Nichtdeterminismus in der Ableitung verschiebt
Werte gegen Beschriftungen, ohne dass irgendetwas auffaellt.

**R-A2-3 — Drei-Werte-Semantik kippt still.** Sie haengt an genau einem bedingten
Schreibpfad. Eine gefuellte, aber vollstaendig unaufloesbare Liste kollabiert heute schon zu
`[]` und wird dann wie „bewusst geleert" behandelt (Block verschwindet) statt wie „nie gewaehlt".
Bei der Formatumstellung ist genau das der wahrscheinlichste Fehlerpfad: Altbestand im
Paar-Format, den der neue Leser nicht versteht ⇒ Ausblick verschwindet stillschweigend.

**R-A2-4 — Kein Migrationsdruck, aber auch kein Netz.** Messung 2026-08-20 (frisch, mit
Positivkontrolle): **0** Dateien mit `outlook_metrics` in Produktion (18 JSON) und Staging;
`display_config` in je 2 Dateien vorhanden, der Suchpfad traegt also. Ein Fehler in der
Bestandsableitung kann heute keine echten Nutzerdaten zerstoeren — er faellt dafuer aber auch
nicht durch echte Daten auf.

**R-A2-5 — `docs/reference/api_contract.md:2056` ist bereits veraltet.** Er nennt
`CompareOutlookLayoutControls.svelte` als einzigen Schreiber und behauptet „der Trip bekommt
keine Auswahlflaeche, ADR-0037" — seit ADR-0055 (#1720 S1) schreibt der Trip ebenfalls. Bei der
Formataenderung sind **zwei** Stellen nachzuziehen (Vertragstext `:2056` und Changelog `:95`).

**R-A2-6 — Go schuetzt nichts.** Flacher Merge, opakes Blob. Ein Client, der weiter Paare
schickt, wird nirgends abgewiesen — die Vertraeglichkeit muss der Python-Leser herstellen.

**R-A2-7 — `avg` ist die bewegliche Kante.** `temperature/avg` hat heute keine
Compare-Katalogzeile und ist deshalb nicht waehlbar. Bekommt es in A3 eine, traegt `temperature`
plötzlich **drei** Auswertungen — dann greift laut A1-Docstring wieder die
Minimum-/Maximum-Disambiguierung, und die Ableitung „Kennung → alle Auswertungen" erzeugt eine
dritte Spalte. Die A2-Ableitung muss diesen Fall wenigstens definiert behandeln.

## 🟢 Frontend: das Paar existiert an GENAU EINER Stelle

Das Frontend rechnet **bereits durchgehend mit reinen Auswahl-Schluesseln** (`string[]`).
Das Paar entsteht ausschliesslich in der Uebersetzungsschicht beim Speichern:

| Datei | Zeile | Rolle |
|---|---|---|
| `.../shared/weather-metrics-tab/compareMetricSelection.ts` | 102 | `StoredActiveMetric = string \| {metric_id, aggregation}` — **String ist im Typ schon gleichberechtigt** |
| dito | 119-131 | `compareMetricKeyFromStored()` — Paar → Schluessel (liest) |
| dito | 144-150 | `normalizeStoredActiveMetrics()` — Lesenormalisierung |
| dito | **162-173** | `toStoredActiveMetrics()` — **EINZIGE Paar-Konstruktion** (schreibt) |
| `.../shared/WeatherMetricsTab.svelte` | 267 | `outlookMetricKeys = $state<string[]\|null>` — State ist rein Schluessel |
| dito | 888-890 | Trip-Speichern; `null` reicht den Altwert unveraendert durch |
| `.../shared/CompareOutlookLayoutControls.svelte` | 39, 44 | Props `metricKeys: string[]` — **kennt das Paar ueberhaupt nicht** |
| `.../compare/compareEditorSave.ts` | 170-176, 424-426 | Compare-Speichern (Hub + Neuanlage) |
| `.../compare/compareHubWizardBridge.ts` | 205-208, 719 | Compare-Lesen |
| `frontend/src/lib/types.ts` | 299 | Typdeklaration — **nur** die Trip-`DisplayConfig`; der Ortsvergleich haelt `display_config` als `Record<string, unknown>` (`:12`, `:636`), dort ist das Paar gar nicht typisiert |

**Praezedenzfall im Schwesterfeld:** `compareEditorSave.ts:167` schreibt
`displayConfig.hourly_metrics = edits.hourlyMetricKeys` — **ungewandelt, reine Strings**.
Der Stundenverlauf hat den Formatwechsel also schon hinter sich; der Ausblick ist das letzte
Feld, das noch durch `toStoredActiveMetrics()` laeuft.

**Eine Bedienstelle, zwei Mountpunkte:** `CompareOutlookLayoutControls.svelte` liegt in
`shared/` und wird in derselben Datei zweimal gemountet — `WeatherMetricsTab.svelte:1400`
(Ortsvergleich, mit Schalter) und `:1783` (Trip, ohne Schalter, AC-13). Getrennt sind nur die
**Speicherwege**; beide rufen dieselbe Uebersetzungsfunktion.

## 🔴 ZUSCHNITT-VERSCHIEBUNG: Frontend-Schluessel sind NICHT Kennungen

Der naheliegende Schluss „Frontend ist schon fertig, A2 ist reine Backend-Arbeit" **traegt
nicht**. Die Auswahl-Schluessel des Frontends sind **Compare-Katalog-Schluessel**, nicht
`metric_id`:

```
Frontend-Schluessel:  temp_max_c  ·  temp_min_c        (zwei Kaestchen)
Backend-Kennung:      temperature ·  temperature        (eine Kennung)
```

Die Min/Max-Unterscheidung lebt im Frontend also **bereits im Schluessel** — im Backend nach A2
aber nicht mehr. Daraus folgt unmittelbar:

**Waehlt der Nutzer nach A2 nur „Temperatur Maximum", speichert das System `temperature` und
rendert die volle Spanne `9/27`.** Die Oberflaeche zeigt ein Kaestchen an, das etwas anderes
verspricht, als herauskommt — die UI luegt im Zwischenzustand.

Genau das raeumt A3 auf (Kanal-Modul: eine Zeile „Temperatur" statt zweier Kaestchen). Zu
entscheiden ist im Zuschnitt, ob A2 eine **minimale** Frontend-Anpassung mitnimmt (die beiden
Temperatur-/Gefuehlte-Temperatur-Kaestchen zu je einem zusammenfassen), oder ob der luegende
Zwischenzustand bis A3 hingenommen wird. **Das ist die zentrale offene Frage der Analyse-Phase.**

## Tests: ~17 Dateien nageln das Paar-Format fest

Massstab: enthaelt ein Paar-**Literal** als Eingabe oder assertiert eine Paar-**Struktur**.

**Zentraler Hebel:** `tests/helpers/outlook_columns.py:70-80, 142-148, 179-181` baut die Paare
programmatisch (`compare_outlook_soll_paare()`) und wird von vier weiteren Testdateien genutzt.
Eine Umstellung dort traegt den groessten Teil.

| Bricht | Datei | Entscheidende Stelle |
|---|---|---|
| JA | `tests/tdd/test_compare_outlook_metric_selection.py` | `:35-36` Paar-Literale, `:412-421` gemischte Auswahl |
| JA | `tests/tdd/test_trip_outlook_metrics_persistence.py` | `:242` `_rohes_display_config(...)["outlook_metrics"] == auswahl` — **nagelt das Format AUF DER PLATTE fest** |
| JA | `tests/tdd/test_outlook_range_cell.py` | `:36-39` — die A1-Spanne **braucht** heute die Auswertungsebene |
| JA | `tests/tdd/test_trip_outlook_metric_selection.py` · `test_trip_outlook_dispatch_mail.py` · `test_trip_outlook_compact_telegram_dispatch.py` · `test_thunder_origin_outlook.py` · `test_vorschau_metrik_tagesfenster.py` · `test_outlook_uses_hiking_window.py` · `test_channel_metric_matrix.py` (`:2346`, `:2566-2571`) | Paar-Literale bzw. Struktur-Assertions |
| JA | `tests/unit/test_trip_metric_cascade_single_source.py` | `:194` assertiert die **Rueckgabe-Struktur** als Dict-Liste |
| JA | `tests/unit/test_gehzeit_metriken_bleiben_trip_exklusiv.py` | `:92-96` probiert je Kennung alle Auswertungen durch |
| JA | `tests/helpers/outlook_columns.py` · `trip_outlook_channels.py:54-55` | Paar-Erzeugung |
| JA | `frontend/.../compareOutlookMetricSelection.test.ts` | `:99-103`, `:199-205` `deepEqual(..., [{metric_id, aggregation}])` |
| JA | `frontend/e2e/compare-outlook-metric-selection.staging.spec.ts:484, 529` · `trip-outlook-metric-selection.staging.spec.ts:113-116` | E2E lesen das gespeicherte Paar |
| NEIN | `test_thunder_level_word_and_onset_hour.py` · `test_compare_outlook_state_named_not_silent.py` · `test_resolution_loss_guard.py` · `compareMetricOrder.test.ts` · `weatherMetricsTabSharing.test.ts` | nur `None`/`[]`/Kommentare |

**Keine Fixture-Datei enthaelt eine gespeicherte Paar-Auswahl.** Die Ausblick-Golden
(`tests/fixtures/trip_outlook_reference/*`, `outlook_trip_parity/*`) halten nur **gerendertes
Ergebnis** — sie brechen nur, wenn sich die Ausgabe aendert, nicht bei reiner Formatumstellung
der Eingabe.

**R-A2-8 — `test_api_contract_drift.py` bewacht die Ausblick-Zeile NICHT.**
`docs/reference/api_contract.md:2056` schreibt das Paarformat als Vertrag fest („ausschliesslich
`[{"metric_id": ..., "aggregation": ...}]`, KEIN Altformat"), aber der Drift-Test enthaelt keinen
`outlook`-Treffer. Die Doku faellt also **nicht** von selbst auf — sie muss von Hand nachgezogen
werden, sonst widerspricht der Vertrag nach A2 dem Code.

## Scope Assessment

- **Backend:** `models.py`, `loader.py`, `compare_outlook_metric_ids.py`,
  `report_config_resolver.py` + Doku (`api_contract.md` zwei Stellen, ADR-Nachtrag)
- **Frontend:** `types.ts:299` + `compareMetricSelection.ts:162-173` (eine Funktion) — **plus
  die offene Frage, ob die Kaestchen-Zusammenfassung schon in A2 gehoert**
- **Go:** keine Aenderung (opakes Blob, flacher Merge)
- **Tests:** ~17 Dateien, davon ein zentraler Helfer
- **Risk Level: MEDIUM-HIGH** — Persistenz-Schema, beide Flaechen, vier Renderer, stille
  Fehlerpfade, luegender Zwischenzustand in der Oberflaeche
