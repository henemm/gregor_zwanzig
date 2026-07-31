---
entity_id: feat_1435_e1a_alarmfaehigkeit_register
type: feature
created: 2026-07-31
updated: 2026-07-31
status: implemented
version: "1.1"
tags: [metric-catalog, alerts, compare, trip, trip-compare-sharing, naming]
workflow: feat-1435-e1a-alarmfaehigkeit-register
---

# Feature #1435 Etappe E1a — Alarmfähigkeit wird eine Eigenschaft des zentralen Registers

## Approval

- [ ] Approved

## Purpose

„Kann diese Wettergröße einen Alarm auslösen?" wird heute an drei Stellen
unabhängig voneinander beantwortet — mit unterschiedlichem, teils
widersprüchlichem Ergebnis (10 vs. 6 vs. 13 Größen, eine davon falsch
verdrahtet). Diese Etappe führt die Antwort auf **eine** Deklaration im
zentralen Wetter-Namensregister zurück: Alarmfähigkeit hängt am Paar
(Wettergröße, Auswertung) — z. B. „Temperatur, Minimum" —, nicht an der
Wettergröße allein. Der Ortsvergleichs-Katalog kennt dieses Paar bereits
(`metric_id`/`aggregation`); die Alarm-Seite modelliert dieselbe Sache
bislang als eigene Pseudo-Größe (`temperature_cold`). E1a beendet das für
den Ortsvergleichs-Zweig des Alarme-Reiters: eine handgepflegte 6er-Liste
fällt, drei bereits heute technisch alarmfähige Größen werden erstmals
bedienbar, eine falsch zugeordnete Alarmzeile (Wind zeigte „Böen") entkreuzt
sich als Wirkung der Konsolidierung.

**Zweite Invariante dieser Etappe (Tech-Lead-Korrektur, Epic #1374
Invariante 1 „kein Element ohne Wirkung"):** eine Alarm-Identität wird nur
dann registriert, wenn die Auswertungskette sie tatsächlich auswerten kann.
Das Register **erzeugt** damit keine Möglichkeiten, es **spiegelt** nur, was
die Auswertung bereits kann — ein Bedienelement ohne Wirkung wäre selbst ein
Fall dessen, was diese Etappe beheben soll. Konkrete Folge: Luftfeuchtigkeit
wird in E1a bewusst **nicht** alarmfähig (s. Abschnitt „Auswertbarkeits-
Prüfung").

## Source

> **Schicht-Hinweis:** Python-Core + Frontend, keine Go-Beteiligung.

- **File:** `src/app/metric_catalog.py`
- **Identifier:** `class MetricDefinition` — neue Felder `alert_metrics`,
  `change_alert_metric`; neue Funktion `alert_metric_for()`
- **File:** `src/output/renderers/compare_metric_catalog.py`
- **Identifier:** `get_compare_metric_catalog()` — `alarmCapable`/`alertMetric`-Ableitung
- **File:** `api/routers/config.py`
- **Identifier:** `get_metrics()` (`GET /api/metrics`)
- **File:** `frontend/src/lib/components/shared/alarme-tab/compareMetricMapping.ts`
- **Identifier:** ganze Datei entfällt (`COMPARE_TO_ALERT_METRIC`, `deriveActiveAlertMetrics`)
- **File:** `frontend/src/lib/components/shared/AlarmeTab.svelte`
- **Identifier:** Vergleichs-Zweig um `effectiveActiveMetrics` (Zeilen ~104-111)
- **File:** `frontend/src/lib/components/shared/corridor-editor/compareMetricCatalogLoader.ts`
- **Identifier:** `buildCompareMetricDefs()`
- **File:** `frontend/src/lib/types.ts`
- **Identifier:** `CompareMetricCatalogEntry`

## Estimated Scope

Zwei Register-Felder + ein Resolver + zwei Endpoint-Erweiterungen + eine
Frontend-Ableitung + ein **zweiteiliger** Vollständigkeits-/Wirksamkeits-
Wächter (Python) + ein expliziter Regressionsnachweis „Alarm-Auswertung
feuert unverändert" (Harte Auflage 1). Nach demselben Muster wie der
Vorgänger `fix_1401b_register_stundenverlauf_alarme.md` (dort 90-130
Produktivzeilen + 150-260 Testzeilen ≈ 240-390 gesamt) liegt auch diese
Etappe vermutlich über dem 250-Zeilen-Deckel, weil ein echter
Wirkungsnachweis (Wächter greift tatsächlich, Alarm-Evaluation bleibt
identisch, tote Deklarationen werden erkannt) mehr Testcode braucht als
Produktivcode.

- **LoC (Schätzung):** ~85-110 Produktivcode (Register-Felder + Resolver +
  zwei Endpoint-Erweiterungen + Frontend-Ableitung + Typ-Erweiterungen,
  abzüglich der 27 gelöschten Zeilen `compareMetricMapping.ts`) + ~260-360
  Testcode (**zweiteiliger** Wächter mit Wirkungsnachweis — Vollständigkeit/
  Eindeutigkeit UND Auswertbarkeit, analog
  `test_guard_actually_fails_when_a_catalog_metric_has_no_cv2_row`
  (`tests/unit/test_compare_metric_catalog_consistency.py:100-141`), API-
  Contract-Test für beide Endpoints, Regressionsnachweis Alarm-Auswertung,
  Frontend-Entkreuzungs-/Erreichbarkeits-Test) → **~340-470 Netto-Zeilen
  gesamt**, damit vermutlich über dem Deckel.
- **Files:** 4 Produktivdateien geändert (`metric_catalog.py`,
  `compare_metric_catalog.py`, `config.py`, `AlarmeTab.svelte`), 3 geändert
  (`compareMetricCatalogLoader.ts`, `corridorEditorState.ts`-Typ, `types.ts`),
  1 gelöscht (`compareMetricMapping.ts`), 1 neu (Ersatz-Ableitungsmodul),
  4-5 Testdateien (neu oder erweitert).
- **Effort:** medium.
- **Vorschlag bei Bestätigung der Überschreitung (statt Anhebung), je
  Teilscheibe geschätzt:**
  - **E1a-1 (Backend + Auslieferung + Wächter):** Register-Felder,
    `alert_metric_for()`, `compare_metric_catalog.py`-Ableitung,
    `GET /api/metrics`/`GET /api/compare/metrics`-Auslieferung,
    zweiteiliger Python-Wächter (Vollständigkeit/Eindeutigkeit UND
    Auswertbarkeit gegen `_ALERT_METRIC_TO_CATALOG_ID`) + Regressionsnachweis
    „Alarm-Auswertung unverändert". **~150-210 LoC.**
  - **E1a-2 (Frontend-Konsum + Wächter):** `compareMetricMapping.ts` fällt,
    neue Ableitungsfunktion, `AlarmeTab.svelte`-Wiring (Vergleichs-Zweig),
    Typ-Erweiterungen, Frontend-Wächter (keine unbekannte Alarm-Identität) +
    Entkreuzungs-/Erreichbarkeits-Nachweis für die drei echten Neuzugänge.
    **~190-260 LoC.**
  - Beide Scheiben sind unabhängig freigebbar (E1a-2 liest nur, was E1a-1
    ausliefert); ein Zwischenstand nach E1a-1 ändert kein sichtbares
    Verhalten (die Frontend-Konsumenten lesen weiterhin
    `compareMetricMapping.ts`, bis E1a-2 sie umstellt).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/metric_catalog.py::MetricDefinition` (`summary_fields`, `default_change_threshold`) | REFERENZ | Vorbild für die Feldform — `alert_metrics` ist strukturell parallel zu `summary_fields` (aggregation-keyed dict) |
| `frontend/src/lib/components/alerts-tab/alertMetricTable.ts::ALERTABLE_METRICS` | READ (Referenz-Vokabular) | Die 13 Ziel-Identitäten, gegen die der Wächter deklariert — frontend-seitig authoritativ, keine Python-Entsprechung existiert bisher |
| `frontend/src/lib/components/alerts-tab/alertMetricTable.ts::CATALOG_TO_ALERT_METRICS` | UNVERÄNDERT | Trip-Zweig bleibt hartkodiert (AC-3) — bewusst nicht Teil dieser Etappe, s. Known Limitations |
| `src/services/compare_alert.py::_SUMMARY_KEY_TO_CATALOG_ID` | UNVERÄNDERT | Die tatsächlich alarm-auslösende Compare-Crosswalk — bleibt unangetastet (Harte Auflage 1) |
| `src/services/weather_change_detection.py::_ALERT_METRIC_TO_CATALOG_ID` | **READ (Wächter-Quelle, neu)** | Der Python-Wächter (AC-5) liest diese Konstante aktiv, um Auswertbarkeit zu prüfen — der Code selbst bleibt unverändert, wird aber zur „vierten Liste" dieses Themenfelds erstmals maschinell mit dem Register abgeglichen, s. Known Limitations |
| `src/services/weather_change_detection.py::_ALERTABLE_METRIC_VALUES` | UNVERÄNDERT | Go-Sync-Vokabular (#1257) — separate, kleinere Teilmenge, nicht Teil dieser Etappe |
| `frontend/src/lib/components/shared/corridor-editor/compareMetricCatalogLoader.ts::loadCompareMetricCatalog` (geteilter Promise-Cache) | READ | Wird von `AlarmeTab.svelte` wiederverwendet statt eines eigenen Fetches — kein Doppel-Request |
| `docs/specs/modules/fix_1401b_register_stundenverlauf_alarme.md` | REFERENZ | Beleg-/Teststil-Vorbild dieser Etappe |
| `docs/context/fix-1401c-begruendung-fehlende-groesse.md` | REFERENZ | Ursprungs-Befund (Kaskade, Kreuz-Verdrahtung) — Scheibe C dort ist ersetzt durch #1435, Befunde bleiben gültig |

## Implementation Details

### 1. Register: zwei neue Felder auf `MetricDefinition`

```python
alert_metrics: dict[str, str] = field(default_factory=dict)   # aggregation -> AlertMetric-Kennung
change_alert_metric: Optional[str] = None                     # Änderungsraten-Alarm, KEINE Auswertung
```

**Entscheidung Delta-Metriken (offener Punkt aus dem Auftrag):** `temperature_change`/
`wind_change`/`precipitation_change` sind Änderungsraten, keine Auswertung
einer Größe — sie passen nicht in `alert_metrics` (dessen Schlüssel echte
Auswertungen sein müssen, damit ein künftiger Konsument `alert_metrics.keys()
⊆ available_aggregations(metric_id)` erwarten darf). Gewählt: **eigenes
Feld** `change_alert_metric`, orthogonal zu `alert_metrics`, gekoppelt an
das bereits existierende `default_change_threshold` (das für Temperatur/
Wind/Niederschlag bereits gesetzt ist — Zeilen 84, 165, 216). Ein
reservierter Auswertungs-Schlüssel (z. B. `"change"`) wurde verworfen: er
würde `_AGGREGATION_ORDER`/`available_aggregations()` verletzen, die nur
`min|max|avg|sum` kennen.

**Belegung — nur auswertbare Identitäten (12 von 13, s. Auswertbarkeits-
Prüfung unten; `humidity` bleibt bewusst bei den leeren Defaults):**

| Katalog-Größe (`id`) | `alert_metrics` | `change_alert_metric` |
|---|---|---|
| `gust` | `{"max": "wind_gust"}` | — |
| `precipitation` | `{"sum": "precipitation_sum"}` | `"precipitation_change"` |
| `thunder` | `{"max": "thunder_level"}` | — |
| `temperature` | `{"min": "temperature_min", "max": "temperature_max"}` | `"temperature_change"` |
| `wind` | `{}` | `"wind_change"` |
| `fresh_snow` | `{"sum": "fresh_snow"}` | — |
| `cape` | `{"max": "cape"}` | — |
| `visibility` | `{"min": "visibility"}` | — |
| `freezing_level` | `{"min": "freezing_level"}` | — |

Alle übrigen Größen (inkl. `humidity`) bleiben bei den leeren Defaults
(nicht alarmfähig). `temperature_cold` (Zeile 98-107, `selectable=False`,
interner Kältealarm-Eintrag) bekommt **kein** `alert_metrics` — die
sichtbare Größe `temperature` trägt beide Richtungen (min UND max), s. Known
Limitations.

Neue Resolver-Funktion (parallel zu `summary_field_for`):

```python
def alert_metric_for(metric_id: object, aggregation: object) -> Optional[str]:
    if not isinstance(metric_id, str) or not isinstance(aggregation, str):
        return None
    definition = _METRICS_BY_ID.get(metric_id)
    if definition is None or aggregation not in definition.summary_fields:
        return None
    direct = definition.alert_metrics.get(aggregation)
    if direct or definition.alert_metrics:
        return direct
    return definition.change_alert_metric
```

> **Nachtrag 2026-07-31 (Adversary-Fund F001, in derselben Lieferung geschlossen).**
> Der ursprünglich hier stehende Entwurf war `return m.alert_metrics.get(aggregation)
> or m.change_alert_metric` — ein **blinder** Rückfall. Er lieferte für
> `("temperature", "avg")` die Änderungsraten-Identität `"temperature_change"`,
> obwohl für diese Auswertung gar kein Alarm vorgesehen ist. Heute noch folgenlos
> (der einzige Aufrufer übergibt nur kuratierte Paare), aber ein künftiger zweiter
> Aufrufer hätte still eine falsche Alarm-Identität ausgeliefert — und der Wächter
> prüft Deklarationen, nicht Aufrufe. Der obige Code ist der ausgelieferte Stand:
> Rückfall nur, wenn die Auswertung in `summary_fields` steht **und** die Größe
> keine eigenen auswertungsspezifischen Identitäten deklariert hat.

Der `or`-Fallback auf `change_alert_metric` ist absichtlich: er löst die
Kreuz-Verdrahtung strukturell auf. `wind_max_kmh` (Katalog-Paar
`("wind","max")`) hat kein direktes `alert_metrics`-Ziel, fällt auf
`wind.change_alert_metric = "wind_change"` zurück — **nicht** mehr auf
`"wind_gust"` (das bleibt exklusiv `gust_max_kmh` vorbehalten, Katalog-Paar
`("gust","max")`). Das ist die eigentliche Regel hinter AC-1: eine Zeile
erscheint für **jede** zu einer aktivierten Größe gehörende Alarmart
(absolut UND Änderung), benannt nach der gewählten Größe — die Entkreuzung
von Böen/Wind ist nur die sichtbare Folge davon, kein Sonderfall.

### 2. Auswertbarkeits-Prüfung (Tech-Lead-Korrektur — neue, härtere Regel)

Eine Alarm-Identität wird nur dann registriert, wenn
`weather_change_detection.py::_ALERT_METRIC_TO_CATALOG_ID` sie tatsächlich
kennt — nur dann kann `is_alert_metric_active()` (Zeilen 171-211) je `True`
liefern; fehlt der Eintrag, liefert die Funktion strukturell **immer**
`False` (Zeile 205-206: `if not catalog_ids: return False`), unabhängig
davon, was der Nutzer im UI einstellt. Ein registriertes, aber
unauswertbares Alarm-Ziel wäre exakt das Bedienelement-ohne-Wirkung, das
diese Etappe beheben soll.

Geprüft (verifiziert am Code, nicht vermutet) für alle 13 `ALERTABLE_METRICS`
(`alertMetricTable.ts:202-216`):

| AlertMetric | Deklariert (Register, E1a) | Auswertbar (`_ALERT_METRIC_TO_CATALOG_ID`, `weather_change_detection.py:82-99`) | Differenz |
|---|---|---|---|
| `wind_gust` | Ja (`gust.alert_metrics["max"]`) | Ja (`("gust",)`) | keine |
| `precipitation_sum` | Ja (`precipitation.alert_metrics["sum"]`) | Ja (`("precipitation",)`) | keine |
| `thunder_level` | Ja (`thunder.alert_metrics["max"]`) | Ja (`("thunder",)`) | keine |
| `temperature_min` | Ja (`temperature.alert_metrics["min"]`) | Ja (`("temperature_cold","temperature")`) | keine |
| `temperature_max` | Ja (`temperature.alert_metrics["max"]`) | Ja (`("temperature",)`) | keine |
| `temperature_change` | Ja (`temperature.change_alert_metric`) | Ja (`("temperature",)`) | keine |
| `wind_change` | Ja (`wind.change_alert_metric`) | Ja (`("wind",)`) | keine |
| `precipitation_change` | Ja (`precipitation.change_alert_metric`) | Ja (`("precipitation",)`) | keine |
| `fresh_snow` | Ja (`fresh_snow.alert_metrics["sum"]`) | Ja (`("fresh_snow",)`) | keine |
| `cape` | Ja (`cape.alert_metrics["max"]`) | Ja (`("cape",)`) | keine |
| `visibility` | Ja (`visibility.alert_metrics["min"]`) | Ja (`("visibility",)`) — Verdacht aus dem Auftrag geprüft: `THRESHOLD_CROSSING`-Sonderpfad (`_THRESHOLD_CROSSING_METRICS`) nutzt denselben Summary-Field-Eintrag, kein zweiter, unabhängiger Pfad | keine |
| `freezing_level` | Ja (`freezing_level.alert_metrics["min"]`) | Ja (`("freezing_level",)`) | keine |
| `humidity` | **Nein — bewusst nicht deklariert** | **Nein** — kein Eintrag in `_ALERT_METRIC_TO_CATALOG_ID` (Issue #889/ADR-0010: Vorboten-Metrik, `is_precursor=True`); `is_alert_metric_active(HUMIDITY, …)` liefert daher unabhängig vom UI immer `False` | **12/13 stimmen überein — humidity ist die einzige unauswertbare Identität** und wird deshalb in E1a nicht registriert |

Ergebnis: **12 von 13** `ALERTABLE_METRICS` sind sowohl deklariert als auch
auswertbar. `humidity` ist die einzige tote Kandidatin — sie bleibt in E1a
unregistriert (kein `alert_metrics`/`change_alert_metric`-Eintrag), damit
`alarmCapable`/`alertMetric` für `humidity_avg_pct` weiterhin `False`/`null`
bleiben (unverändert zu heute). Die Delta-Größen und `visibility`, die der
Auftrag ausdrücklich als Verdachtsfälle nannte, sind beide sauber
auswertbar — keine weiteren toten Kandidaten gefunden.

**Konsequenz für den heutigen `alarmCapable`-Umfang:** Mit `humidity`
bewusst ausgeschlossen ergibt die register-abgeleitete `alarmCapable`-Menge
**exakt dieselben 10 Compare-Keys** wie heute (`_SUMMARY_KEY_TO_CATALOG_ID`,
`compare_alert.py:46-57`) — keine Differenz mehr zu benennen. Einzige
Änderung unterhalb der Boolean-Ebene: `wind_max_kmh`s Alarm-**Identität**
wird jetzt explizit `wind_change` statt implizit über die Katalog-ID
`"wind"` — der Wahrheitswert `alarmCapable=True` bleibt identisch.

### 3. Auslieferung

**`get_compare_metric_catalog()`** (`compare_metric_catalog.py:234-269`):
jeder Eintrag bekommt zusätzlich `"alertMetric": alert_metric_for(metric_id,
aggregation)` und `"alarmCapable"` wird jetzt aus diesem Wert abgeleitet
(`is not None`) statt aus `_SUMMARY_KEY_TO_CATALOG_ID.keys()`.
`_SUMMARY_KEY_TO_CATALOG_ID` (compare_alert.py) bleibt als Import UND als
bestehender Subset-Drift-Guard (`compare_metric_catalog.py:160-168`)
unverändert bestehen — sie ist weiterhin die einzige Quelle, die
tatsächlich Alarme auslöst (s. Harte Auflage 1).

**`GET /api/metrics`** (`api/routers/config.py:58-92`): jede
Auswertungs-Zeile bekommt `"alert_metric": m.alert_metrics.get(a)`
(`null` wenn keine), jeder Metrik-Eintrag zusätzlich
`"change_alert_metric": m.change_alert_metric` (`null` wenn keine).

### 4. Frontend-Konsum (Vergleichs-Zweig, Alarme-Reiter)

`compareMetricMapping.ts` entfällt vollständig (27 Zeilen, inkl.
`COMPARE_TO_ALERT_METRIC` und `deriveActiveAlertMetrics`). Ersatz: eine neue,
reine Funktion (Modulname nach Verhalten, z. B.
`deriveActiveAlertMetricsFromCatalog.ts`), die `alertMetric` direkt aus dem
bereits geladenen Compare-Katalog liest (`CompareMetricDef.alertMetric`,
neues optionales Feld, durchgereicht in `buildCompareMetricDefs()`
(`compareMetricCatalogLoader.ts:47-74`) analog zum bestehenden
`alarmCapable`-Feld):

```ts
export function deriveActiveAlertMetricsFromCatalog(
	activeMetricKeys: string[],
	defs: CompareMetricDef[]
): AlertMetric[] {
	const byKey = new Map(defs.map((d) => [d.metric, d]));
	const seen = new Set<AlertMetric>();
	for (const key of activeMetricKeys) {
		const am = byKey.get(key)?.alertMetric;
		if (am) seen.add(am);
	}
	return ALERTABLE_METRICS.filter((m) => seen.has(m));
}
```

`AlarmeTab.svelte` (Vergleichs-Zweig, Zeilen ~104-111): lädt den Compare-
Katalog über den bereits bestehenden geteilten Promise-Cache
(`loadCompareMetricCatalog()`) in einem `$effect`, fail-soft (analog dem
Muster aus `fix_1401b_register_stundenverlauf_alarme.md` Teil 1 — ein
fehlgeschlagener Ladevorgang darf den Alarme-Reiter nicht unbedienbar
machen; Fallback: leere `defs[]` → keine Zeilen sichtbar, kein Absturz).
`effectiveActiveMetrics` ruft `deriveActiveAlertMetricsFromCatalog()` statt
der gelöschten `deriveActiveAlertMetrics()`.

**Trip-Zweig bleibt unangetastet:** `activeMetrics`-Prop und
`CATALOG_TO_ALERT_METRICS` (`alertMetricTable.ts:280-304`) werden von
dieser Etappe nicht berührt (AC-3).

### 5. Wächter — zweiteilig (Vollständigkeit/Eindeutigkeit UND Auswertbarkeit)

**Python** (`tests/unit/test_alert_metric_register_declaration.py`, neu),
zwei Prüfungen, beide mit Wirkungsnachweis (analog
`test_guard_actually_fails_when_a_catalog_metric_has_no_cv2_row`,
`tests/unit/test_compare_metric_catalog_consistency.py:100-141`):

1. **Auswertbarkeit:** jede im Register deklarierte Alarm-Identität
   (`alert_metrics.values()` ∪ `change_alert_metric`-Werte) ist Element von
   `{m.value for m in weather_change_detection._ALERT_METRIC_TO_CATALOG_ID}`
   — sonst schlägt der Test fehl und nennt die tote Identität. Diese Prüfung
   ist der eigentliche Kern der Tech-Lead-Korrektur: sie hätte die
   ursprünglich vorgesehene `humidity`-Deklaration vor der Auslieferung
   abgefangen.
2. **Vollständigkeit/Eindeutigkeit:** die Vereinigung der deklarierten
   Identitäten ist exakt gleich dem Ziel-Vokabular = `ALERTABLE_METRICS`
   (literal, kommentiert gespiegelt aus `alertMetricTable.ts:202-216`)
   **geschnitten** mit `_ALERT_METRIC_TO_CATALOG_ID` (= den 12 auswertbaren
   Identitäten, s. Tabelle oben) — keine Identität fehlt, keine wird
   zweimal vergeben.

Wirkungsnachweis für (1): eine künstlich um `humidity → "humidity_avg_pct"`
ergänzte Kopie der Register-Deklaration muss den Test brechen. Wirkungsnachweis
für (2): eine künstlich reduzierte bzw. verdoppelte Kopie muss den Test
ebenso brechen.

**Frontend** (co-located mit dem neuen Ableitungsmodul, `node:test`): jeder
nicht-`null`-`alertMetric`-Wert im (Fixture-)Compare-Katalog ist Element von
`ALERTABLE_METRICS` — ergänzender Guard aus Konsumenten-Sicht (keine
unbekannte Identität erreicht die UI).

## Expected Behavior

- **Input:** Ein Nutzer öffnet im Ortsvergleich den Reiter *Wetter-Metriken*
  und aktiviert dort z. B. „Böen", „Temperatur" (Auswertung Minimum) und
  „Wind"; danach öffnet er den Reiter *Alarme*.
- **Output:** Der Reiter *Alarme* zeigt eine Zeile „Böen" (statt bisher
  fälschlich unter „Wind" einsortiert), eine Zeile „Windänderung" für die
  aktivierte Wettergröße Wind, und neu eine eigene Zeile „Temperatur
  (Minimum)" (heute: keine Zeile, obwohl die Auswertung sie bereits
  unterstützt). Aktiviert derselbe Nutzer zusätzlich „Luftfeuchtigkeit",
  erscheint dafür weiterhin **keine** Alarm-Zeile — bewusst, weil die
  Auswertung Luftfeuchtigkeit nicht alarmfähig macht (s. Auswertbarkeits-
  Prüfung; Erklärsatz dafür folgt in E1b). Für einen Trip (kein Vergleich)
  ändert sich nichts.
- **Side effects:** Bereits gespeicherte Alarm-Schwellen (`metric_levels`)
  bleiben unverändert erhalten — nur welche Zeilen angeboten werden, ändert
  sich. `GET /api/metrics` und `GET /api/compare/metrics` liefern zusätzliche,
  rein additive Felder (`alert_metric`/`change_alert_metric` bzw.
  `alertMetric`) — bestehende Konsumenten, die diese Felder ignorieren,
  verhalten sich identisch wie zuvor.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer aktiviert im Ortsvergleich eine Wetter-Metrik,
  die sowohl einen Schwellen- als auch einen Änderungs-Alarm kennt (Wind
  bzw. Böen) / When er den Reiter *Alarme* öffnet / Then erscheinen dort
  genau die Alarm-Zeilen, die zur **gewählten** Größe gehören — absolute wie
  Änderungs-Alarme —, jede benannt nach der Größe, die der Nutzer tatsächlich
  ausgewählt hat: „Böen" aktiviert ergibt eine Zeile „Böen" (nicht „Wind"),
  „Wind" aktiviert ergibt eine Zeile „Windänderung" (nicht „Böen"). Heute
  zeigt „Wind" fälschlich eine Zeile „Böen", während „Böen" selbst gar keine
  Zeile erzeugt.
  - Test: `deriveActiveAlertMetricsFromCatalog(['gust_max_kmh'], catalogFixture)`
    enthält `'wind_gust'`, NICHT `'wind_change'`; `deriveActiveAlertMetricsFromCatalog(['wind_max_kmh'], catalogFixture)`
    enthält `'wind_change'`, NICHT `'wind_gust'`; beide gleichzeitig aktiv
    liefert beide Zeilen (Regressionsschutz gegen die heutige
    Kreuz-Verdrahtung UND Nachweis, dass keine der beiden Zeilen die andere
    verdrängt).

- **AC-2:** Given ein Nutzer hat im Ortsvergleich eine der Wetter-Metriken
  „Temperatur" (Minimum), „Gewitterenergie (CAPE)" oder „Nullgradgrenze"
  aktiviert / When er den Reiter *Alarme* öffnet / Then erscheint für jede
  aktivierte Größe eine eigene, tatsächlich wirksame Alarm-Zeile — heute
  gibt es dafür keine Zeile, obwohl die Auswertung diese drei Größen bereits
  unterstützt (`compare_alert.py::_SUMMARY_KEY_TO_CATALOG_ID` enthält
  `temp_min_c`, `cape_max_jkg`, `freezing_level_m` schon heute).
  - Test: `deriveActiveAlertMetricsFromCatalog(['temp_min_c'], catalogFixture)`
    enthält `'temperature_min'`; analog `['cape_max_jkg']` → `'cape'`,
    `['freezing_level_m']` → `'freezing_level'`. Ergänzend ein Python-Test,
    der bestätigt, dass alle drei Ziel-Identitäten sowohl in
    `_ALERT_METRIC_TO_CATALOG_ID` als auch in der Zielmenge von
    `_SUMMARY_KEY_TO_CATALOG_ID` erreichbar sind — der Unterschied zu
    Luftfeuchtigkeit (AC-5) ist damit nicht nur behauptet, sondern geprüft.

- **AC-3:** Given ein Trip (kein Ortsvergleich) mit denselben aktiven
  Wetter-Metriken wie vor dieser Änderung / When der Reiter *Alarme* im
  Trip-Kontext gerendert wird / Then zeigt er exakt dieselben Alarm-Zeilen
  wie zuvor — die Trip-Ableitung bleibt unverändert.
  - Test: bestehende Tests `alertMetricTable.test.ts` und
    `issue_864_alert_metric_levels.test.ts` bleiben unverändert grün (kein
    Edit an `CATALOG_TO_ALERT_METRICS`/`activeAlertableMetrics`); zusätzlich
    ein Struktur-Check, dass `AlarmeTab.svelte` im `context="route"`-Zweig
    weiterhin ausschließlich die `activeMetrics`-Prop liest (kein neuer
    Katalog-Fetch in diesem Zweig).

- **AC-4:** Given ein Nutzer hat bereits eine Alarm-Schwelle für eine Größe
  gespeichert (z. B. „Böen" auf „sensibel") / When diese Änderung
  ausgeliefert wird, ohne dass der Nutzer etwas tut / Then bleibt der
  gespeicherte Schwellenwert unverändert erhalten — nur das Angebot an
  wählbaren Zeilen ändert sich, keine Nutzerdaten gehen verloren.
  - Test: Roundtrip-Test lädt eine Preset-/Trip-Fixture mit gesetzten
    `metric_alert_levels`, wendet die geänderten Katalog-/Register-Module an
    (kein Persistenz-Code-Pfad ist angefasst) und prüft, dass die geladenen
    Werte byteidentisch bleiben.

- **AC-5:** Given eine im Register deklarierte Alarm-Identität, die von der
  Auswertungskette nicht erreicht werden kann (z. B. weil sie in
  `weather_change_detection.py::_ALERT_METRIC_TO_CATALOG_ID` fehlt — wie
  Luftfeuchtigkeit), ODER eine der 12 auswertbaren Ziel-Größen fehlt im
  Register oder ist doppelt vergeben / When der Vollständigkeits-/
  Wirksamkeits-Wächter läuft / Then schlägt er fehl und benennt die
  betroffene Alarm-Identität konkret — ein Bedienelement ohne Wirkung wird
  so vor der Auslieferung erkannt, nicht erst im Betrieb.
  - Test: `test_alert_metric_register_declaration.py`, zwei Wirkungsnachweise
    auf künstlich veränderten Kopien (kein Mutieren der echten Registry):
    (a) eine künstlich um `humidity` ergänzte Deklaration lässt den
    Auswertbarkeits-Check rot werden; (b) eine künstlich reduzierte bzw.
    verdoppelte Kopie lässt den Vollständigkeits-/Eindeutigkeits-Check rot
    werden.

- **AC-6:** Given ein Ortsvergleichs-Preset mit denselben aktiven Metriken
  wie vor dieser Änderung (z. B. Böen, Regen) und derselben
  Wetterabweichung / When die Alarm-Auswertung läuft
  (`CompareAlertService.check_all_compare_presets()`) / Then löst sie exakt
  dieselben Treffer aus wie vor dieser Änderung — die tatsächlich
  alarmauslösenden Module (`compare_alert.py::_SUMMARY_KEY_TO_CATALOG_ID`,
  `weather_change_detection.py::_ALERT_METRIC_TO_CATALOG_ID`) sind durch
  diese Etappe unverändert.
  - Test: bestehende Fixtures/Muster aus
    `tests/tdd/test_compare_alert_metric_gating.py` (mock-freie
    `CompareAlertService`-Instanz, echte Preset-/Snapshot-Dateien) — Treffer-
    Anzahl und -Inhalt vor/nach dieser Änderung identisch; ergänzend ein
    Konstanten-Identitäts-Check der beiden genannten Module gegen den
    Vorzustand (kein Diff).

- **AC-7:** Given der Metrik-Katalog wird über `GET /api/metrics` bzw.
  `GET /api/compare/metrics` abgerufen / When die Antwort ausgewertet wird /
  Then trägt jede tatsächlich alarmfähige Größe ihre Alarm-Identität
  sichtbar in der Antwort (z. B. „Böen" → `wind_gust`, „Nullgradgrenze" →
  `freezing_level`) — nicht-alarmfähige Größen tragen `null`, **explizit
  einschließlich Luftfeuchtigkeit** (unverändert zu heute — kein neues
  „scheinbar alarmfähig, wirkt aber nicht"-Feld).
  - Test: API-Contract-Test (FastAPI TestClient) gegen beide Endpoints,
    stichprobenartig für alarmfähige, nicht-alarmfähige UND explizit für den
    Luftfeuchtigkeit-Eintrag (`null` bestätigt).

## Known Limitations

- **`temperature_cold` wird NICHT abgeschafft.** Der interne Kältealarm-
  Eintrag (`metric_catalog.py:98-107`, `selectable=False`) bleibt bestehen
  und wird weiterhin von der Alarm-Engine gelesen
  (`weather_change_detection.py::_ALERT_METRIC_TO_CATALOG_ID[TEMPERATURE_MIN]
  = ("temperature_cold", "temperature")`). Das neue Register-Feld
  `alert_metrics` sitzt auf der SICHTBAREN Größe `temperature` (beide
  Richtungen, min UND max) — der Rückbau der Pseudo-Größe ist ein späterer
  Schritt, nicht Teil von E1a.
- **Vierte Liste zum Thema bleibt bestehen — ausdrücklich als
  Fortsetzungs-Kandidat benannt.**
  `weather_change_detection.py::_ALERT_METRIC_TO_CATALOG_ID` (13 Einträge,
  aber mit `SNOW_LINE` statt `HUMIDITY` — ein Abweichungs-Alert-Subsystem für
  Wetter-Änderungserkennung, nicht das per-Metrik-Schwellen-System dieser
  Etappe) wird in E1a **nicht abgeschafft** — sie bleibt die maßgebliche
  Auswertbarkeits-Quelle und wird ab dieser Etappe erstmals **maschinell**
  vom Wächter gelesen (s. Implementation Details Punkt 5), aber nicht
  konsolidiert. Ebenso unangetastet: `_ALERTABLE_METRIC_VALUES` (6
  Einträge, Go-Sync-Vokabular für #1257). Eine echte Zusammenführung dieser
  vierten Liste mit dem neuen Register ist ein größerer, eigener Schnitt —
  **ausdrücklicher Kandidat für eine spätere Etappe von #1435**, damit er
  nicht in Vergessenheit gerät.
- **Luftfeuchtigkeit bleibt in E1a ohne Alarm-Zeile im Ortsvergleich —
  bewusst, nicht als Lücke.** Anders als in der ursprünglichen Fassung
  dieser Spec wird `humidity` **nicht** registriert (s. Auswertbarkeits-
  Prüfung): `weather_change_detection.py` kennt `AlertMetric.HUMIDITY` nicht
  (Issue #889/ADR-0010, Vorboten-Metrik), `is_alert_metric_active(HUMIDITY,
  …)` liefert daher strukturell immer `False`. Ein Bedienelement ohne
  Wirkung würde genau die Invariante verletzen, die diese Etappe herstellen
  soll (Epic #1374 Invariante 1). `humidity_avg_pct` bleibt entsprechend
  `alarmCapable=False`/`alertMetric=null` — identisch zu heute, keine
  Verhaltensänderung. Die Größe fällt in **E1b** unter den dort vorgesehenen
  Erklärsatz „für diese Größe gibt es keinen Alarm" — das ist der richtige
  Ort dafür, nicht ein scheinbar funktionierendes Bedienelement in E1a.
- **Renderer-Mail-Gate (#811) nicht betroffen:** `compare_metric_catalog.py`
  liegt außerhalb der Gate-Dateiliste (kein `src/output/renderers/email/*.py`,
  kein `alert/*.py`, keiner der drei benannten Renderer).
- **Kein automatisierter Cross-Language-Wächter** zwischen Python-Register
  und `ALERTABLE_METRICS` (TypeScript) — das 13er-Zielvokabular ist im
  Python-Wächter als literal benanntes, kommentiertes Set gespiegelt
  (analog `fix_1401b`s Teil 2, dort ebenfalls ohne automatisierten
  Cross-Language-Guard). Ändert sich `ALERTABLE_METRICS` künftig, muss der
  Python-Wächter von Hand nachgezogen werden.
- **E1b (Erklärsatz + Leerzustand-Hinweis):** erledigt in Etappe E1b
  (2026-07-31, Spec `feat_1435_e1b_alarm_erklaersatz.md`). Der
  Leerzustand-Hinweis nennt jetzt den
  korrekten Reiter-Namen „Wetter-Metriken" statt „Wertebereiche"; zusätzlich
  erscheint ein Erklärsatz, der namentlich aufzählt, welche gewählten Größen
  keinen Alarm auslösen können, statt sie kommentarlos wegzulassen. Im
  Tour-Kontext bleibt die Funktionalität begrenzt (dort gibt es keine
  Metrik-Auswahl als Datengrundlage).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Diese Spec setzt das bereits etablierte, PO-freigegebene
  Prinzip „eine zentrale Registerquelle statt redaktionell duplizierter
  Vokabulare" (A1/A2/ADR-0037, fortgeführt in `fix_1401b`) auf die
  Alarmfähigkeits-Frage fort. Die neue Modellierung „Alarmfähigkeit hängt am
  Paar (Größe, Auswertung), UND nur wenn die Auswertung sie tatsächlich
  erreicht" ist eine lokale Datenmodell-Verfeinerung innerhalb des bereits
  bestehenden Registers, keine neue Grundsatzentscheidung im Sinne der
  CLAUDE.md-ADR-Trigger (Kanäle, Provider, Auth, Editor-Paradigma, Test-/
  Deploy-Strategie unberührt). Die bewusste Nicht-Vereinheitlichung mit dem
  Abweichungs-Alert-Subsystem (`weather_change_detection.py`) ist eine
  Scope-Entscheidung dieser Spec (s. Known Limitations), kein Datenmodell-
  Grundsatzwechsel.

## Changelog

- 2026-07-31: **E1a-1 ausgeliefert** (Commit `98d1a1f6`, Adversary VERIFIED
  über 2 Runden, auf Staging verifiziert). Umfang wie unten spezifiziert
  implementiert: `MetricDefinition.alert_metrics`/`change_alert_metric`,
  Resolver `alert_metric_for()`, Auslieferung über `GET /api/metrics` und
  `GET /api/compare/metrics`, zweiteiliger Wächter
  (`tests/unit/test_alert_metric_register_declaration.py`). Verhaltensneutral
  bestätigt: register-abgeleitete `alarmCapable`-Menge = dieselben 10
  Compare-Keys wie vor der Änderung. Adversary-Befund F001 im selben Zug
  geschlossen: `alert_metric_for()` fiel bei einer nicht deklarierten
  Auswertung still auf die Änderungsraten-Identität der Größe zurück — der
  Rückfall greift jetzt nur noch, wenn die Auswertung in `summary_fields`
  steht **und** die Größe keine eigenen, auswertungsspezifischen
  Alarm-Identitäten deklariert hat (Details: Docstring
  `metric_catalog.alert_metric_for()`). Doku nachgezogen in
  `docs/reference/api_contract.md` (Section 15/15.1 + Changelog).
- 2026-07-31 (v1.1): Tech-Lead-Korrektur eingearbeitet. Der Wächter prüft ab
  jetzt zusätzlich Auswertbarkeit (nicht nur Vollständigkeit) — `humidity`
  wird deshalb in E1a NICHT registriert (Epic #1374 Invariante 1, „kein
  Element ohne Wirkung"). AC-2 ersetzt (Luftfeuchtigkeit → die drei echt
  funktionalen Neuzugänge temperature_min/cape/freezing_level). AC-1 zweite
  Hälfte umformuliert (allgemeine Regel „alle zur gewählten Größe gehörenden
  Alarme erscheinen, benannt nach der gewählten Größe" statt punktueller
  Tausch). Neue Tabelle „Auswertbarkeits-Prüfung" (alle 13
  `ALERTABLE_METRICS`, inkl. der vom Tech Lead angefragten Prüfung der
  Delta-Größen und von `visibility` — beide unauffällig). Konsequenz: die
  register-abgeleitete `alarmCapable`-Menge stimmt jetzt exakt mit den
  heutigen 10 Compare-Keys überein (keine Differenz mehr zu benennen,
  vorherige Fassung hatte `humidity_avg_pct` fälschlich als Neuzugang
  geführt). Vierte Liste (`_ALERT_METRIC_TO_CATALOG_ID`) explizit als
  Fortsetzungs-Kandidat für eine spätere #1435-Etappe benannt.
- 2026-07-31 (v1.0): Initial spec created. Alle Zahlen (13
  `ALERTABLE_METRICS`, 10 `_SUMMARY_KEY_TO_CATALOG_ID`, 6
  `COMPARE_TO_ALERT_METRIC`, 6 `_ALERTABLE_METRIC_VALUES`) gegen den
  aktuellen Code verifiziert, nicht aus dem Vorgänger-Kontextdokument
  übernommen.
