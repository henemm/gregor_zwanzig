# Context: fix-1911-thunder-katalog

Issue: [#1911](https://github.com/henemm/gregor_zwanzig/issues/1911) — Gewitter-Stufenliste in
`WeatherMetricsTab.svelte` ist eine lokale Kopie statt Backend-Katalog (#1488 Scheibe A2).
Track: Standard. Worktree `intake-1462`, Branch `worktree-intake-1462`.

## Request Summary

Die Gewitter-Stufenliste im Wetter-Metriken-Reiter soll nicht länger im Frontend hart codiert
stehen, sondern aus dem Backend-Katalog kommen — damit dieselben vier Wörter nicht an mehreren
Stellen von Hand gepflegt werden.

## 🔴 Drei Befunde, die die Ticket-Prämisse korrigieren

### B1 — Der Block ist ein Alarm-**Schwellen**wähler mit drei Einträgen, keine Anzeige-Skala mit vier

`WeatherMetricsTab.svelte:1634-1638` führt genau drei Einträge:

```js
{ id: 'leicht', label: 'Leicht', float: 1.0 },
{ id: 'mittel', label: 'Mittel', float: 2.0 },
{ id: 'hoch',   label: 'Hoch',   float: 3.0 }
```

Kein `kein` — und das ist **richtig so**: Der Block füttert `ThresholdMetricRow.svelte`, also die
Frage „ab welcher Stufe soll alarmiert werden?". „Ab Stufe *kein* alarmieren" ist keine sinnvolle
Einstellung. `thunderThresholdLevels.test.ts:83-126` sichert die Drei ausdrücklich ab (genau drei
Stufen, kein `kein`).

Der Katalog liefert dagegen **vier** Labels (`kein/leicht/mittel/hoch`, `scale [0,3]`).

**Folge für die Umsetzung:** Nicht „Liste ersetzen", sondern „Liste **ableiten**" — Katalog ohne
die Nullstufe, `float` = Ordinalindex. Die Ableitungsregel muss benannt und getestet sein, sonst
bricht die Umstellung einen bewussten Wächter und erzeugt eine fachlich unsinnige vierte Option.
Die Ticket-Formulierung „Diese Liste wurde in #1474b bereits … auf die korrekten 4 Stufen
korrigiert" trifft auf diesen Block nicht zu.

### B2 — Der Backend-Katalog ist selbst eine handgepflegte Kopie

`src/output/renderers/compare_metric_catalog.py:104-112` trägt `ordinalLabels` als **Literal**.
Die Datei importiert nichts aus `src/output/metric_format.py`; `THUNDER_LABEL_DE`,
`_THUNDER_ORDER` und `_THUNDER_LABEL_VALUE` (`metric_format.py:283-288`, re-exportiert aus
`src/app/thunder_scale.py:42-43`) werden dort **nicht referenziert**. Die Übereinstimmung der vier
Wörter entsteht durch Pflege, nicht durch Ableitung.

Der Kommentar an Ort und Stelle dokumentiert die bereits eingetretene Drift selbst:

> „eine dritte Stelle hier war seit der Ordinalverschiebung um eine Stufe zu kurz"

**Folge:** Stellt man nur das Frontend um, **wandert** die Kopie ins Backend, sie verschwindet
nicht. Die Zahl der handgepflegten Stellen sinkt von zwei auf eine — das Ticket-Ziel „kanonische
Quelle" ist damit nicht erreicht. Das ist die Entscheidung, die in die Spec gehört (siehe
„Offene Entscheidung" unten).

### B3 — Es gibt keinen trip-tauglichen Endpoint mit `ordinalLabels`

| Endpoint | Quelle | trägt `ordinalLabels`? | Zuschnitt |
|---|---|---|---|
| `GET /api/metrics` | `api/routers/config.py:72-115` → `metric_catalog.get_all_metrics()` | **nein** — `MetricDefinition` (`src/app/metric_catalog.py:27-90`) hat kein solches Feld | zentraler Trip-Katalog: `category`, `aggregations[]`, `sms_code`, `format_modes`, `selectable`-Filter |
| `GET /api/compare/metrics` | `api/routers/compare.py:11-24` → `compare_metric_catalog.py` | **ja** | Bedienstruktur für Schwellenregler: `kind`, `rangeMin/Max`, `ordinalLabels`, `enumValues` |

Der Go-Proxy (`internal/router/router.go:125,158`, `internal/handler/proxy.go:45-71`) ist reines
Byte-Passthrough und beschneidet nichts.

**Der gute Teil:** Der Weg ist bereits gebahnt. `WeatherMetricsTab.svelte` ruft
`loadCompareSelectionEntries()` (Z.514) **auch im Trip-Kontext** — der `context === 'route'`-Zweig
direkt darunter beweist es. `compareCatalog` steht im Trip-Kontext also schon zur Verfügung; das
Template greift nur daran vorbei. Der Loader hat mit `buildRouteMetricDefsFromCatalog` (Z.131) und
`loadRouteExtraMetricDefs` (Z.170) bereits ausdrücklich route-seitige Bausteine — der
Compare-Endpoint als Trip-Datenquelle ist im Repo etabliert, kein Präzedenzbruch.

## Related Files

| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:1634-1638` | der umzustellende Block; Katalog liegt bereits als `compareCatalog` (`$state`, Z.206) vor |
| `frontend/src/lib/components/shared/weather-metrics-tab/ThresholdMetricRow.svelte:28,40,44,46` | Verbraucher der `Level[]`-Form (`id`, `label`, `float`) |
| `frontend/src/lib/components/shared/corridor-editor/compareMetricCatalogLoader.ts` | Ladepfad (`/api/compare/metrics`, Promise-Cache Z.86-98); braucht einen Mapper `ordinalLabels → Level[]` |
| `src/output/renderers/compare_metric_catalog.py:104-112` | kanonische Quelle laut Ticket — faktisch handgepflegtes Literal (B2) |
| `src/output/metric_format.py:283-288` / `src/app/thunder_scale.py:42-43` | die *echte* kanonische Stufenquelle |
| `frontend/.../__tests__/thunderThresholdLevels.test.ts:35,49-70,83-126` | parst den hart codierten Block per Regex — wird durch die Umstellung obsolet, muss ersetzt statt gelöscht werden |
| `frontend/.../corridor-editor/__tests__/compareMetricCatalogParity.test.ts:37-51` | Vorbild: liest die Python-Quelle **live** per `execFileSync('uv', …)`; CI-seitig abgesichert (`.github/workflows/ci.yml:91-109`) |

## Existing Patterns

- **Katalog-Parität per Live-Read.** `compareMetricCatalogParity.test.ts` fährt einen echten
  Python-Prozess und vergleicht gegen den echten Katalog. Der CI-Job `frontend-test` installiert
  dafür bereits `uv` + `uv sync`. Das ist der erprobte Weg, eine Frontend-Zusicherung gegen die
  Backend-Wahrheit zu prüfen — und das Vorbild für den Test dieser Umstellung.
- **Ein geteilter Baustein, Parameter `context`.** CLAUDE.md „Trip/Ortsvergleich-Code-Teilung":
  eine neue trip-eigene Katalogkomponente wäre ein Verstoß.
- **Promise-Cache statt Mehrfach-Fetch** (`compareMetricCatalogLoader.ts:86-98`, Issue #1373).

## Dependencies

- **Upstream:** `/api/compare/metrics` (Python) über den Go-Proxy; `ThunderLevel` /
  `thunder_ordinal()` als Zählreferenz.
- **Downstream:** `ThresholdMetricRow.svelte`; die gespeicherten SMS-/Alarm-Schwellenwerte im
  Trip (`float`-Werte 1.0/2.0/3.0 — **Bestandsdaten**, die Ableitung muss dieselben Zahlen
  erzeugen, sonst verschieben sich gespeicherte Schwellen um eine Stufe).

## Existing Specs

| Spec | Bezug |
|---|---|
| `docs/specs/modules/compare_weather_metrics_tab.md` (AC ab Z.281) | Migration der Komponente nach `shared/`, Kontext `trip`\|`vergleich` |
| `docs/specs/modules/compare_metric_catalog_endpoint.md` (AC ab Z.118) | Ursprungsspec des Endpoints |
| `docs/specs/modules/compare_metric_ssot_final.md` (AC ab Z.241) | SSoT-Migration, enthält den Thunder-Ordinal-Sonderfall |
| `docs/specs/modules/rework_1351_compare_catalog.md` (AC ab Z.149) | Katalog-Erweiterung |

Keine Spec referenziert #1911.

## Risks & Considerations

1. **Bestandsdaten-Risiko (höchstes).** Die gespeicherten Schwellen sind `float`-Werte. Erzeugt
   die Ableitung andere Zahlen (z.B. 0/1/2 statt 1/2/3), verschieben sich alle gespeicherten
   Gewitter-Alarmschwellen still um eine Stufe. Genau dieser Fehlertyp ist in #1474 schon einmal
   passiert („um eine Stufe zu kurz").
2. **Der bewachende Test wird zum Hindernis.** `thunderThresholdLevels.test.ts` prüft heute die
   Existenz des hart codierten Literals per Regex. Er darf nicht ersatzlos gelöscht werden —
   sonst verliert die Zusicherung „genau drei Schwellen, kein `kein`" ihren Wächter. Er muss auf
   die Ableitung umgestellt werden (Vorbild: Parity-Test).
3. **Ladezustand.** `compareCatalog` ist asynchron. Das Template muss einen Zustand vor dem Laden
   überstehen, ohne eine leere Schwellenliste zu rendern (`compareCatalogLoaded`-Flag existiert).
   Fehlerfall: `compareCatalogError` wird gesetzt — was zeigt die Zeile dann?
4. **Sieben Montagepunkte**, davon vier im Trip-Kontext, drei im Compare-Kontext — die Änderung
   wirkt in beiden Flächen (`TripTabs.svelte:224`, `TripNewEditor.svelte:881/1113`,
   `CompareTabs.svelte:1396`, `CompareNewEditor.svelte:394/491`).
5. **Kollision:** Session `1848` fasst dieselbe Datei in ihrer Scheibe A3 an. Abgestimmt:
   #1911 zuerst, #1848 rebast danach.

## Nebenbefunde (nicht in diesem Scope)

- **`TripEditView.svelte` ist toter Code.** Kein Importpfad von `frontend/src/routes/`; die echte
  Trip-Detail-Route mountet `TripTabs.svelte`. Referenziert nur aus drei reinen
  Dateiinhalt-Tests. Es ist zugleich Montagepunkt Nr. 1 von `WeatherMetricsTab` (Z.201) — dieser
  Mount ist unerreichbar.
- **`AlertsPreviewCard.svelte`** hängt nur am Barrel `trip-detail/index.ts:8`, der selbst nirgends
  importiert wird. Verdacht bestätigt, aber `deadTripOverviewComponentsRemoved.test.ts` führt ihn
  nicht in seiner Löschliste.
- Beide sind Aufräumarbeit, nicht die Katalog-Frage. Vorschlag: als eigene Scheibe oder
  Sammel-Eintrag, nicht in diesen Workflow ziehen (LoC-Limit 250).

## 🔴 Offene Entscheidung für die Analyse-/Spec-Phase

**Reicht „Frontend liest Backend-Literal", oder muss `compare_metric_catalog.py` seine
`ordinalLabels` für `thunder_level_max` aus `THUNDER_LABEL_DE` ableiten?**

- **Nur Frontend:** kleiner Eingriff, erfüllt den Ticket-Wortlaut, lässt aber eine handgepflegte
  Kopie im Backend stehen — die, die nachweislich schon einmal gedriftet ist.
- **Frontend + Backend-Ableitung:** erfüllt das Ticket-Ziel („kanonische Quelle"), ist die
  Voraussetzung dafür, dass der Wächter aus #1480 später überhaupt etwas Sinnvolles bewachen
  kann, kostet aber Änderungen an einer Datei mit eigener Spec-Historie.
