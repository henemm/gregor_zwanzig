---
entity_id: fix_1425_s2b_gewitter_skala
type: bugfix
created: 2026-07-31
updated: 2026-07-31
status: draft
version: "1.0"
tags: [trip, corridor-editor, metric-catalog, thunder, migration, wertebereiche]
---

# Trip-Wertebereiche: Gewitter-Skala vereinheitlichen — Markierung war invertiert (#1425 Schritt 2, Teil 2, Scheibe B)

## Approval

- [x] Approved (PO, 2026-07-31)

## Purpose

Der Trip fuehrt Gewitter im Wertebereiche-Editor als Prozent 0-100 (Vorgabe
„bis 40"), der zentrale Metrik-Katalog dagegen dreistufig ordinal
(kein/mittel/hoch). Weil der Renderer den Stundenwert immer als Ordinal
(0/1/2) liefert, ist `corridor_inside(0|1|2, None, 40)` strukturell **immer
wahr** — ein Gewitter-Wertebereich markiert dadurch gerade **dann**, wenn
Gewitter herrscht, nicht wenn es fehlt. Das ist eine Umkehrung, kein bloss
wirkungsloser Schalter. Diese Spec zieht Gewitter auf den bereits
existierenden Katalog-Eintrag `thunder_level_max` (ordinal) um, reicht den
im Ortsvergleich bereits fertigen Ordinal-Zweig des Editors unveraendert in
den Trip-Kontext durch, und schluesselt gespeicherte Alt-Korridore beim
Laden verlustfrei um.

Schritt 2, Teil 2, **Scheibe B** von Issue #1425 (Kind von Epic #1372,
Dach-Epic #1374). Scheibe A (Markier-Wirkung fuer 20 von 23 Groessen,
`b3995b17`) und Scheibe C (Banner-Text, `f6286910`) sind bereits live; diese
Scheibe schliesst die letzte offene Teil-2-Scheibe.

## Source

- **File:** `frontend/src/lib/components/shared/corridor-editor/corridorEditorState.ts`
- **Identifier:** `ROUTE_METRIC_DEFS` (Zeile 31-38, Eintrag `thunder_level`),
  `ROUTE_CORRIDOR_CATALOG_IDS` (Zeile 98-105, Eintrag `thunder`),
  `buildRoutePool()` (Zeile 133-173)

> **Schicht-Hinweis:** Ueberwiegend SvelteKit-Frontend
> (`frontend/src/lib/components/shared/corridor-editor/corridorEditorState.ts`
> und `compareMetricCatalogLoader.ts`). Ein einzeiliger Python-Core-Eingriff
> (`src/output/renderers/email/html.py::TRIP_CORRIDOR_METRIC_TO_COL_KEY`,
> Eintrag entfernen — die katalogbasierte Aufloesung in
> `build_trip_corridor_id_map()` deckt `thunder_level_max` bereits seit
> Scheibe A automatisch ab). Kein Go-API-Eingriff.
> `CorridorEditor.svelte`/`CorridorEditorMobile.svelte` (Praesentation),
> `corridor_mark.py`, `corridor_match.py`, `compare_html.py` bleiben
> unveraendert — der Ordinal-Zweig und die Match-Logik sind bereits
> generisch (`row.kind === 'ordinal'`) und werden nur erreichbar, nicht neu
> gebaut.

## Estimated Scope

- **LoC:** ~150-250 (ueberwiegend Tests, inkl. Migrations- und
  Bridge-Testfaelle)
- **Files:** ~8
- **Effort:** medium (kleiner fachlicher Kern, aber eine dokumentierte
  Namensraum-Kollision mit dem Alarm-Bridge-Drift-Waechter muss sauber
  aufgeloest werden, s. Implementation Details Punkt 4)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `compare_metric_catalog.COMPARE_METRIC_CATALOG` (`src/output/renderers/compare_metric_catalog.py:92-95`) | data | Liefert `thunder_level_max` bereits mit `kind:"ordinal"`, `ordinalLabels:["kein","mittel","hoch"]`, `metric_id:"thunder"`, `aggregation:"max"` — unveraendert, nur Konsument neu |
| `build_trip_corridor_id_map()` (`src/output/renderers/email/html.py:572-614`, aus Scheibe A) | function | Loest `thunder_level_max` bereits **heute** ueber die Katalog-Route auf (`aggregation != "sum"`, `kind != "enum"`) — keine Codeaenderung an dieser Funktion noetig, nur der tote Alt-Eintrag faellt aus dem expliziten Dict |
| `corridor_mark.is_marked()` (`src/output/renderers/email/corridor_mark.py:49-57`) | function | Wandelt den `ThunderLevel`-Stundenwert bereits per `thunder_ordinal()` in 0/1/2, bevor `corridor_inside()` vergleicht — der Fix wirkt allein dadurch, dass `corridor.range` jetzt ebenfalls Ordinalwerte traegt |
| `_COMPARE_DEFAULTS['thunder_level_max']` (`corridorEditorState.ts:370`) | data | Liefert bereits `{defaultMin:null, defaultMax:0}` — der Neuanlegen-Default fuer Scheibe B kommt kostenlos mit, sobald `thunder_level_max` durch `buildRouteMetricDefsFromCatalog()` laeuft |
| `buildCompareMetricDefs()` (`compareMetricCatalogLoader.ts:47-74`) | function | Vorbild fuer die ordinal-bewusste `scale`-Berechnung (`kind==='ordinal' ? [0, labels.length-1] : [rangeMin,rangeMax]`), die `buildRouteMetricDefsFromCatalog()` bisher NICHT hat |
| `tests/tdd/test_alert_metric_mapping_parity.py` | gate | Drift-Waechter Katalog-ID -> AlertMetric (Python `catalog_id_to_alert_metrics()` vs. TS `ROUTE_CORRIDOR_CATALOG_IDS`) — braucht eine begruendete, eng gefasste Ausnahme fuer `thunder` (s. Implementation Details Punkt 4), sonst faelschlich rot |
| `frontend/.../__tests__/routeCorridorPoolCatalogExpansion.test.ts:73-80,168-186,402` | test | Bestehende Tests behaupten explizit, `thunder_level_max` erscheine NICHT im Zusatz-Pool (AC-3 aus Teil 1) — diese Behauptung kehrt sich mit dieser Scheibe bewusst um |
| `frontend/.../__tests__/weatherMetricsTabCorridorCoupling.test.ts:164-166` | test | Regressions-Anker „`buildRoutePool([])` ohne Filter -> 6 im Pool" wird zu 5 (ein Fixpunkt weniger, seit `thunder_level` aus `ROUTE_METRIC_DEFS` faellt) |
| `tests/tdd/test_trip_mail_corridor_mark.py` | test | Bestehende Regressionsbasis fuer die (nach dieser Scheibe 4) uebrigen alten Route-Keys — muss unveraendert gruen bleiben, plus neuer Umkehrungs-Nachweis fuer Gewitter |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/lib/components/shared/corridor-editor/corridorEditorState.ts` | MODIFY | (1) `ROUTE_METRIC_DEFS`: `thunder_level`-Eintrag (Prozent) entfernt — 6 wird 5 fest verdrahtete Route-Groessen. (2) `ROUTE_CORRIDOR_CATALOG_IDS`: `thunder`-Schluessel entfernt (der Ausschluss aus dem Zusatz-Pool faellt strukturell weg, s. Implementation Details Punkt 1). (3) `RouteMetricDef`: optionale Felder `kind?: 'range'\|'ordinal'` und `ordinalLabels?: string[]` ergaenzt. (4) `buildRoutePool()`: neue Vorverarbeitung migriert gespeicherte `thunder_level`-Korridore auf `thunder_level_max` (s. Punkt 3) BEVOR die Pool-Zuordnung laeuft, UND uebernimmt `def.kind`/`def.ordinalLabels` beim Bau der `CorridorRowState` (Zeile ~161-165). (5) `addRow()`: dieselbe Uebernahme (Zeile ~192-197). |
| `frontend/src/lib/components/shared/corridor-editor/compareMetricCatalogLoader.ts` | MODIFY | `buildRouteMetricDefsFromCatalog()` (Zeile 130-154): uebernimmt jetzt `kind`/`ordinalLabels` aus dem Katalog-Eintrag und berechnet `scale` ordinal-bewusst (`kind==='ordinal' ? [0, ordinalLabels.length-1] : [rangeMin,rangeMax]`) — bisher wurde `kind` verworfen und `scale` blind auf `[rangeMin??0, rangeMax??100]` gesetzt (fuer `thunder_level_max`, das keine `rangeMin/rangeMax` traegt, waere das `[0,100]` statt `[0,2]` gewesen). Kommentarpflege bei `_ROUTE_COVERED_METRIC_IDS`: der Satz „thunder faellt dadurch automatisch mit heraus" beschreibt nach dieser Scheibe das Gegenteil. |
| `src/output/renderers/email/html.py` | MODIFY | `TRIP_CORRIDOR_METRIC_TO_COL_KEY` (Zeile 563-569): Eintrag `"thunder_level": "thunder"` entfernt (5 wird 4 explizite Eintraege). `build_trip_corridor_id_map()` selbst bleibt unveraendert — sie loest `thunder_level_max` bereits seit Scheibe A automatisch ueber die Katalog-Route auf (`entry["key"]="thunder_level_max"`, `aggregation="max"`, `kind="ordinal"` — beide Ausschlussfilter greifen nicht). |
| `tests/tdd/test_alert_metric_mapping_parity.py` | MODIFY | `thunder` wird eine dokumentierte, eng begruendete Ausnahme in `test_frontend_bridge_matches_python_forward_mapping()`: die Wertebereiche-Bruecke (`ROUTE_CORRIDOR_CATALOG_IDS`) zielt nach dieser Scheibe fuer Gewitter nicht mehr auf `thunder_level`, weil die Wertebereiche-Zeile auf den Katalog-Eintrag `thunder_level_max` umzieht — die Alarm-Sync-Seite (`catalog_id_to_alert_metrics()["thunder"] == {"thunder_level"}`, `AlertMetric.THUNDER_LEVEL`) bleibt bewusst unveraendert (eigene, von `trip.corridors[]` entkoppelte Persistenz `metric_alert_levels`, s. Implementation Details Punkt 4). Die bestehende `_FE_BRIDGE_EXCEPTIONS`-Ausnahme passt NICHT (die dortige Begruendung ist „nicht selectable", Gewitter bleibt selectable) — eine zweite, eigens begruendete Ausnahme wird ergaenzt. |
| `frontend/.../__tests__/routeCorridorPoolCatalogExpansion.test.ts` | MODIFY | Zeile 73-80/168-186/402: bisherige „`thunder_level_max` erscheint NICHT" Assertions kehren sich um (kommt jetzt im Zusatz-Pool, mit `kind:'ordinal'`, `ordinalLabels`, `scale:[0,2]`, `defaultMin:null/defaultMax:0`). Neu: Migrationsfaelle (`thunder_level`/`[null,40]` -> `thunder_level_max`/`[null,1]`; Grenzwerte 0/1/2 bleiben unveraendert; `null` bleibt `null`). |
| `frontend/.../__tests__/weatherMetricsTabCorridorCoupling.test.ts` | MODIFY | Zeile 164-166: Regressions-Anker „`buildRoutePool([])` -> 6 im Pool" wird auf 5 korrigiert (ein `ROUTE_METRIC_DEFS`-Eintrag weniger). |
| `frontend/src/lib/components/shared/corridor-editor/corridorEditorState.test.ts` | MODIFY | **In der RED-Phase nachgetragen** (lag ausserhalb `__tests__/` und war beim Spec-Schreiben uebersehen): 85 Tests schreiben den ALTEN Stand fest. Vier Stellen drehen sich um — Z. 77-88 (Liste „genau die 6 AlertableMetrics" -> 5, ohne `thunder_level`), Z. 103 (`poolLeft.length` 5 -> 4), Z. 110 (6 -> 5), Z. 185-190 (`addRow(..., 'thunder_level', ...)` -> andere Groesse). Ohne diese Datei bleibt die Umsetzung rot. |
| `tests/tdd/test_trip_mail_corridor_mark.py` | MODIFY | Neuer Kern-Nachweis: Korridor `thunder_level_max`/`[null,0]` markiert eine `NONE`-Stunde, NICHT eine `HIGH`-Stunde (Umkehrung behoben). Bestehende Faelle fuer die verbleibenden 4 alten Route-Keys laufen unveraendert gruen (Regressionsschutz). |

**Explizit NICHT geaendert:**
`CorridorEditor.svelte`/`CorridorEditorMobile.svelte` — der Ordinal-Zweig
(`row.kind === 'ordinal'` -> drei Beschriftungs-Buttons statt Zahlen-Eingabe,
`CorridorEditor.svelte:366-392`, `CorridorEditorMobile.svelte:359-363`)
existiert bereits und wird unveraendert wiederverwendet (Teilungs-Invariante,
Anti-Pattern-Referenz #1170 — keine Route-eigene Kopie). `corridor_mark.py`,
`services/corridor_match.py`, `compare_html.py`, `compare_metric_catalog.py`
(die Katalog-Tabelle selbst traegt `thunder_level_max` bereits korrekt seit
Einfuehrung des Katalogs). `weather_change_detection.py`,
`internal/model/trip.go` (Alarm-Schwellen 1.0/2.0), `alertMetricLabels.ts`,
Telegram-Renderer (`narrow.py`) — alle vier anderen Gewitter-Skalen bleiben
unangetastet (s. Implementation Details Punkt 4).

## Implementation Details

**1. Warum der Ausschluss faellt (Zusatz-Pool statt fester 6er-Liste):**
`ROUTE_METRIC_DEFS` verliert den `thunder_level`-Eintrag. Damit ist Gewitter
in `ROUTE_METRIC_DEF_BY_ID` nicht mehr vertreten — die feste
Uebergangs-Bruecke `ROUTE_CORRIDOR_CATALOG_IDS['thunder']` (bisher
`['thunder_level']`) hat kein gueltiges Ziel mehr und wird entfernt.
`compareMetricCatalogLoader.ts::_ROUTE_COVERED_METRIC_IDS` (abgeleitet aus
den Schluesseln von `ROUTE_CORRIDOR_CATALOG_IDS`) enthaelt danach
automatisch kein `thunder` mehr — `buildRouteMetricDefsFromCatalog()` lässt
den Katalog-Eintrag `thunder_level_max` (`metric_id:"thunder"`) folglich
durch. In `buildRoutePool()` ist `thunder_level_max` damit ein `extraDef` wie
die anderen 17 Katalog-Groessen aus Teil 1 — das `activeCatalogMetrics`-Gating
gilt fuer `extraDefs` bereits heute nicht (bestehender Kommentar
`corridorEditorState.ts:117-123`), Gewitter ist also immer im „+ Metrik"-Pool
verfuegbar, unabhaengig vom Wetter-Metriken-Tab.

**2. `kind`/`ordinalLabels` bis in die Zeile durchreichen:**
`buildRouteMetricDefsFromCatalog()` mappt bisher nur
`rangeMin`/`rangeMax`/`step`. Analog `buildCompareMetricDefs()`
(`compareMetricCatalogLoader.ts:51-54`) wird `kind` uebernommen und `scale`
ordinal-bewusst berechnet — sonst bekaeme `thunder_level_max` (kein
`rangeMin`/`rangeMax` im Katalog-Eintrag) den irrefuehrenden Fallback
`[0,100]`. `buildRoutePool()`/`addRow()` uebernehmen `def.kind`/
`def.ordinalLabels` in die gebaute `CorridorRowState` (analog
`buildComparePool()`/`addCompareRow()`, die das fuer den Vergleichs-Kontext
bereits tun). Der vorhandene Ordinal-Zweig in `CorridorEditor.svelte:366`
liest exakt diese beiden Felder — sobald sie im Zeilenzustand ankommen,
greift er im Trip-Kontext ohne weitere Aenderung.

**3. Migration gespeicherter Alt-Korridore (Sicherheitsnetz, kein
Massen-Rework):** `buildRoutePool()` bekommt eine Vorverarbeitung, die JEDEN
`corridors`-Eintrag mit `metric === 'thunder_level'` VOR dem Pool-Aufbau
umschluesselt:

```
metric -> 'thunder_level_max'
je Grenzwert (min, max) unabhaengig:
  null            -> null
  0 | 1 | 2       -> unveraendert (schon ordinal)
  >2 (Prozent):
    0-33   -> 0   ("kein")
    34-66  -> 1   ("mittel")
    67-100 -> 2   ("hoch")
```

Die alte Vorgabe „bis 40" (`range:[null,40]`) wird damit `[null,1]` = „bis
mittel" — genau die im Kontext-Dokument genannte Beispielumrechnung. Die
Vorverarbeitung muss VOR der `present`-Map-Bildung laufen (F001-Analogie aus
Teil 1): sonst wuerde `thunder_level` als „unbekannte Metrik" in
`unknownCorridors` landen und beim naechsten Speichern **zusaetzlich** zur
neuen Zeile persistiert (Doppel-Speicherung, Risk #2 im Kontext-Dokument).

**4. Der Namensraum-Konflikt mit dem Alarm-Bridge-Drift-Waechter (wichtigste
Nebenwirkungs-Klaerung dieser Scheibe):** `ROUTE_CORRIDOR_CATALOG_IDS` diente
bisher EINER Bedeutung fuer ZWEI Verbraucher: (a) welche Wertebereiche-Zeile
zu einer Katalog-ID gehoert (`buildRoutePool`, dieser Datei), UND (b) — rein
als Drift-Nachweis, kein Laufzeit-Verbrauch — ob dieselbe Zuordnung mit
Pythons `catalog_id_to_alert_metrics()` uebereinstimmt (Δ-Alarm-Sync-Pfad,
Issue #1257, uebersetzt `display_config.metrics[]` in `AlertMetric`-Werte
fuer `alert_rules`). Bislang war fuer JEDE Katalog-ID beides identisch (der
String `thunder_level` diente sowohl als `Corridor.metric` als auch als
`AlertMetric`-Wert). Diese Scheibe trennt das fuer Gewitter bewusst: die
Wertebereiche-Zeile heisst ab jetzt `thunder_level_max`, die
Alarm-Empfindlichkeit bleibt unter dem Schluessel `thunder_level` in
`metric_alert_levels` (SensLevel-Dict) — einer voellig eigenen, von
`trip.corridors[]` bereits seit Issue #1371 entkoppelten Persistenz (belegt:
`buildCorridorSavePayload()`, `corridorEditorState.ts:287-299`, gibt
`metric_alert_levels` als reinen Pass-Through von `originalLevels` zurueck,
liest es NIE aus `rows`). Der Δ-Alarm-Pfad selbst (`weather_change_detection.py`,
`AlertMetric.THUNDER_LEVEL`, Go `AlertMetricThunderLevel = "thunder_level"`)
liest `trip.corridors[]` fuer Gewitter an keiner Stelle — er ist von dieser
Aenderung faktisch unberuehrt. Der Drift-Waechter muss das nur noch
**wissen**: `thunder` wird eine zweite, eigens benannte und begruendete
Ausnahme in `test_alert_metric_mapping_parity.py` (die vorhandene
`_FE_BRIDGE_EXCEPTIONS` passt nicht, da deren Pruefung „nicht selectable"
verlangt — Gewitter bleibt im Wetter-Metriken-Tab waehlbar).

## Datenlage

Alle Datenwurzeln durchsucht (`data/users/*/briefings`, `data/users/*/trips`,
`compare_presets.json` — Messung im Kontext-Dokument
`docs/context/fix-1425-s2b-gewitter-skala.md`): der lebende Pfad
(`briefings/`) enthaelt **keinen einzigen** Gewitter-Korridor; zwei Funde mit
dem alten Prozent-Schluessel liegen ausschliesslich im toten Altbestand
`trips/` (seit #1250 nicht mehr gelesen). Die Migration in
`buildRoutePool()` betrifft real **null** Datensaetze — sie ist ein
Sicherheitsnetz fuer den Fall, dass zwischen heute und dem Deploy dieser
Scheibe jemand einen Gewitter-Korridor mit der alten Prozent-Vorgabe anlegt,
nicht der Risikotreiber dieser Scheibe. Der eigentliche Aufwand liegt in der
sauberen Trennung von Wertebereiche-Namensraum und Alarm-Namensraum (Punkt 4
oben), nicht in der Datenmigration selbst.

## Expected Behavior

- **Input:** Trip mit einem Gewitter-Wertebereich, entweder neu angelegt
  (`thunder_level_max`, Default `[null,0]`) oder als Alt-Korridor
  (`thunder_level`, Prozent) aus einem frueheren Stand.
- **Output:** Der Trip-Editor zeigt fuer Gewitter drei
  Beschriftungs-Buttons (kein/mittel/hoch) statt eines Prozent-Schiebereglers.
  Die Trip-Mail markiert eine Stundenzelle genau dann, wenn der
  ordinale Stundenwert im eingestellten Bereich liegt — ein Korridor „bis
  kein Gewitter" markiert ausschliesslich gewitterfreie Stunden, nicht mehr
  jede Stunde. Ein gespeicherter Alt-Korridor erscheint nach dem Laden
  bereits als ordinaler Wertebereich und wird beim naechsten Speichern unter
  dem neuen Schluessel abgelegt.
- **Side effects:** Die Vergleichs-Mail und die Gewitter-Δ-Alarme sind von
  dieser Aenderung unberuehrt (getrennte Namensraeume, s. Punkt 4). Keine
  Migration ausserhalb von `buildRoutePool()` (kein Batch-Skript, kein
  Server-Migrations-Job noetig — die Datenlage rechtfertigt das nicht).

## Acceptance Criteria

- **AC-1:** Given ein Trip-Korridor `thunder_level_max` mit Bereich `[null, 0]`
  ("bis kein Gewitter") und `mark: true`, sowie eine Trip-Stunde mit
  `ThunderLevel.HIGH` und eine zweite Stunde mit `ThunderLevel.NONE`, When
  die Trip-Mail gerendert wird, Then traegt NUR die gewitterfreie Stunde die
  `corridor-mark`-Auszeichnung — die bisherige Umkehrung (auch HIGH wurde
  markiert) ist behoben.
  - Test: `tests/tdd/test_trip_mail_corridor_mark.py`, neuer Fall mit beiden
    Stundenwerten gegen denselben Korridor, prueft das gerenderte HTML auf
    An-/Abwesenheit der Marken-Signatur je Zelle.

- **AC-2:** Given der Trip-Editor (`context='route'`) zeigt eine
  Gewitter-Zeile, When die Zeile gerendert wird, Then erscheinen drei
  Beschriftungs-Buttons ("kein"/"mittel"/"hoch") statt eines
  Zahlen-Schiebereglers — derselbe Ordinal-Zweig wie im Ortsvergleich, ohne
  eine neue, Route-eigene Darstellung.
  - Test: Frontend-Unit-Test rendert `CorridorEditor.svelte` mit einer Zeile
    `{metric:'thunder_level_max', kind:'ordinal', ordinalLabels:[...]}` in
    `context='route'` und prueft auf die Ordinal-Button-Gruppe
    (`data-testid="corridor-ordinal-max-thunder_level_max"`).

- **AC-3:** Given ein gespeicherter Trip-Korridor `{metric:"thunder_level",
  range:[null,40]}` (Altbestand, Vorgabe „bis 40"), When der
  Wertebereiche-Editor laedt (`buildRoutePool`), Then erscheint er als
  `{metric:"thunder_level_max", range:[null,1]}` ("bis mittel") — kein
  Datenverlust, korrekte proportionale Drittelung.
  - Test: `frontend/.../__tests__/routeCorridorPoolCatalogExpansion.test.ts`,
    neuer Migrationsfall inkl. Grenzfaellen (0/1/2 bleiben unveraendert,
    `null` bleibt `null`).

- **AC-4:** Given eine neue, bisher ungespeicherte Gewitter-Zeile wird ueber
  "+ Metrik" im Trip hinzugefuegt, When die Zeile erscheint, Then betraegt
  ihr Standardwert `[null, 0]` ("bis kein Gewitter") — identisch zum
  Standardwert derselben Groesse im Ortsvergleich-Editor.
  - Test: Frontend-Unit-Test ruft `addRow()` mit `metric='thunder_level_max'`
    aus dem Katalog-Zusatz-Pool auf und prueft `min===null, max===0`.

- **AC-5:** Given identische Korridor- und Wetterdaten wie vor dieser
  Aenderung, When die Vergleichs-Mail gerendert UND die
  Gewitter-Δ-Alarmpruefung (`AlertMetric.THUNDER_LEVEL`,
  `metric_alert_levels`) ausgefuehrt werden, Then ist die Vergleichs-Mail
  (HTML + Klartext) byte-identisch (sha256) und die Alarm-Ergebnisse fuer
  Gewitter unveraendert — der Schluesselwechsel im Trip-Wertebereich wirkt
  sich nicht auf die getrennt persistierte Alarm-Empfindlichkeit aus.
  - Test: bestehender sha256-Vergleichstest der Vergleichs-Mail sowie die
    bestehende `weather_change_detection.py`-Testsuite fuer Gewitter laufen
    unveraendert gruen.

- **AC-6:** Given der Eintrag `"thunder_level": "thunder"` ist aus
  `TRIP_CORRIDOR_METRIC_TO_COL_KEY` entfernt und ein Trip traegt zusaetzlich
  einen Korridor mit einer nicht aufloesbaren Metrik-Kennung, When die
  Trip-Mail gerendert wird, Then loest `build_trip_corridor_id_map()`
  `thunder_level_max` weiterhin korrekt auf die Spalte "thunder" auf (ueber
  die bereits bestehende katalogbasierte Route), und der nicht aufloesbare
  Korridor wird still uebersprungen statt zum Absturz zu fuehren.
  - Test: `tests/tdd/test_trip_mail_corridor_mark.py`, Fixture mit gemischter
    Korridor-Liste (ein gueltiger `thunder_level_max`-Korridor plus eine
    unbekannte Metrik-Kennung).

## Known Limitations

- Die Prozent-Reste ausserhalb des Korridor-Systems (`html.py:173-178`
  Zahlen-Fallback, `html.py:275,294-299,345` Mobil-Stundenliste mit
  `{thunder_val:.0f}%`) werden von dieser Scheibe **nicht** angefasst —
  gefundene Altlast der frueheren Prozent-Interpretation, Sammel-Eintrag
  #1199.
- Der Rueckbau von `TRIP_CORRIDOR_METRIC_TO_COL_KEY` ist auch nach dieser
  Scheibe **nicht vollstaendig** moeglich: die vier uebrigen Eintraege
  (`wind_gust`, `temperature_min`, `temperature_max`, `snow_line`) bleiben
  bestehen, weil Bestandsdaten diese Route-Keys tragen und sie keine
  Katalog-Keys sind. Nur der `thunder_level`-Eintrag konnte fallen, weil
  Gewitter als einzige der 5 alten Groessen einen 1:1-Katalog-Ersatz
  (`thunder_level_max`) hat.
- Kein serverseitiges Enum fuer `Corridor.Metric` (Go,
  `internal/model/trip.go:72`) — ein alter `thunder_level`-Wert, der NIE den
  Trip-Editor durchlaeuft (z.B. direkter API-Zugriff), bleibt bis zum
  naechsten Laden ueber den Editor unmigriert. Kein Server-seitiger
  Migrations-Job, weil die Datenlage (null lebende Datensaetze) das nicht
  rechtfertigt.
- Die Trennung von Wertebereiche- und Alarm-Namensraum fuer Gewitter
  (Implementation Details Punkt 4) ist ab dieser Scheibe die erste
  Katalog-ID, bei der beide Bruecken auseinanderlaufen — sollte ein
  kuenftiger Refactor `ROUTE_CORRIDOR_CATALOG_IDS` erneut anfassen, muss
  diese Ausnahme erneut dokumentiert (nicht stillschweigend entfernt)
  werden.

## Nicht Teil dieser Spec

- **Alarme:** `thunder_ordinal` (0/1/2, Sortier-/Vergleichsordnung),
  `thunder_label_value` (0/2/3, ausschliesslich SMS-Token), das
  `ThunderLevel`-Enum selbst (Risk Engine, Ausblick), sowie die
  Alarm-Schwellen 1.0/2.0 (Go-Defaults, FE-Beschriftung) — alle vier bleiben
  unveraendert (s. Implementation Details Punkt 4).
- **Rueckbau der uebrigen 4 Eintraege** in `TRIP_CORRIDOR_METRIC_TO_COL_KEY`
  — kein 1:1-Katalog-Ersatz vorhanden, kein Folge-Workflow angekuendigt.
- **Prozent-Reste** in `html.py` ausserhalb des Korridor-Systems (Zahlen-
  Fallback, Mobil-Stundenliste) — Sammel-Eintrag #1199.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Additive Vereinheitlichung auf ein bereits im Katalog
  vorhandenes, bereits im Ortsvergleich produktiv genutztes Ordinal-Schema.
  Kein neuer Provider, kein neuer Kanal, keine neue
  Auth-/Persistenz-Entscheidung — der `Corridor`-Datentyp und sein
  Speicherformat (`{metric, range, notify, mark}`) bleiben unveraendert,
  nur der zulaessige `metric`-Wert fuer Gewitter wechselt. Die
  Namensraum-Trennung Wertebereiche vs. Alarme (Punkt 4) ist eine lokale
  Implementierungsentscheidung innerhalb des bereits etablierten
  "ein zentraler Katalog"-Ansatzes (vgl. `docs/specs/modules/fix_1425_s2_corridor_pool.md`,
  `docs/specs/modules/fix_1425_s2b_markier_wirkung.md`).

## Changelog

- 2026-07-31: Initial spec created
