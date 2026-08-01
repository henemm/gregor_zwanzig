---
entity_id: feat_1435_e1a2_alarme_reiter_register
type: feature
created: 2026-07-31
updated: 2026-07-31
status: draft
version: "1.0"
tags: [metric-catalog, alerts, compare, trip-compare-sharing, naming]
workflow: feat-1435-e1a2-alarme-reiter-register
---

# Feature #1435 Etappe E1a-2 — Der Alarme-Reiter liest das zentrale Register

> **Teilweise ueberholt seit 2026-08-01 (Issue #1406 Scheibe B).** Der
> Ortsvergleich-Stundenverlauf hat kein eigenes Zehner-Vokabular mehr: der
> Vorrat kommt aus dem zentralen Wetterkatalog (22 Wert-Spalten), die einzige
> Zuordnung liegt in `src/output/renderers/compare_hourly_metric_ids.py`. Die
> Frontend-Bezeichner `ALL_HOURLY_METRICS`, `HOURLY_KEY_TO_CATALOG_ID` und
> `resolveHourlyMetricLabel` sowie die Datei `compareHourlyCatalogIds.ts` gibt
> es nicht mehr. Wo dieses Dokument sie als Ist-Stand nennt, gilt
> `docs/specs/modules/feat_1406b_stundenverlauf_katalog.md`.


## Approval

- [ ] Approved

## Purpose

E1a-1 (`98d1a1f6`, live) hat die Alarmfähigkeit einer Wettergröße als
Eigenschaft des zentralen Wetter-Namensregisters hinterlegt und über
`GET /api/compare/metrics` (Feld `alertMetric`) bereits ausgeliefert. Der
Alarme-Reiter des Ortsvergleichs kennt dieses Feld aber noch nicht — er
entscheidet weiterhin über eine eigene, sechs Einträge umfassende
Frontend-Liste (`COMPARE_TO_ALERT_METRIC`), welche Alarm-Zeilen in der
Empfindlichkeits-Tabelle erscheinen. Diese Etappe stellt die Verbindung her:
die Empfindlichkeits-Tabelle liest künftig ausschließlich das Register. Das
macht drei bereits heute technisch alarmfähige Größen (Temperatur-Minimum,
Gewitterenergie, Nullgradgrenze) erstmals bedienbar und löst eine
Fehlzuordnung auf — wer „Wind" auswählt, sieht heute fälschlich die Zeile
„Böen"; „Böen" selbst erzeugt gar keine Zeile.

## Source

> **Schicht-Hinweis:** reine Frontend-Änderung (SvelteKit), keine Go-, keine
> Python-Beteiligung. Das Register und seine Auslieferung (`GET /api/metrics`,
> `GET /api/compare/metrics`) sind bereits produktiv (E1a-1) und werden
> ausschließlich lesend konsumiert.

- **File:** `frontend/src/lib/components/shared/alarme-tab/compareMetricMapping.ts`
- **Identifier:** ganze Datei entfällt (`COMPARE_TO_ALERT_METRIC`, `deriveActiveAlertMetrics`)
- **File:** `frontend/src/lib/components/shared/AlarmeTab.svelte`
- **Identifier:** Vergleichs-Zweig von `effectiveActiveMetrics` (Zeilen ~107-111)
- **File:** `frontend/src/lib/components/shared/weather-metrics-tab/compareMetricSelection.ts`
- **Identifier:** `CompareSelectionEntry` (Zeilen 7-16), `toCompareSelectionEntries()` (Zeilen 27-49)
- **File:** `frontend/src/lib/components/compare/CompareTabs.svelte`
- **Identifier:** `hydrateAlarmeTab()` (Zeilen 597-606), `<AlarmeTab>`-Instanziierung (Zeile 1416)
- **File:** `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` *(RED-Phase-Befund 2026-07-31)*
- **Identifier:** zwei `<AlarmeTab context="vergleich">`-Einbettungen (Zeilen 386, 471) — die Anlege-Seite lädt den Compare-Katalog heute **gar nicht**; ohne Ladeweg + Durchreichen zeigt der Alarme-Reiter unter `/compare/new` nach der Umstellung **null Zeilen** (echte Regression, in der ursprünglichen Spec übersehen)
- **File:** `frontend/src/lib/utils/alertMetricLabels.ts` *(AC-9, PO-Entscheidung 2026-07-31)*
- **Identifier:** `ALERT_METRIC_LABELS` — `temperature_change`/`wind_change`/`precipitation_change` (Zeilen 26-28)
- **File:** `frontend/src/lib/components/alerts-tab/AlertPresetSelector.svelte` *(AC-9)*
- **Identifier:** eigene Beschriftungs-Dublette (Zeilen 22-23) — Wortlaut angleichen, Auseinanderlaufen per Test sichern

## Estimated Scope

- **LoC:** ~80-115 Produktivcode (Typ-Erweiterung + neue Ableitungsfunktion +
  Component-Wiring + 5 Beschriftungs-Zeilen aus AC-9, abzüglich der 27
  gelöschten Zeilen `compareMetricMapping.ts`) + ~130-190 Testcode
  (node:test, Fixture-basiert, inkl. Ratsche-Test gegen die gelöschte Datei
  und Gleichlauf-Test der Beschriftungs-Dublette) → **~210-290 Netto-Zeilen
  gesamt**. Liegt am oberen Rand des 250-Zeilen-Budgets; falls überschritten,
  ist der Überhang wie in E1a-1 Testcode — Override nur mit PO-Zustimmung.
- **Files:** 7 Produktivdateien geändert (`types.ts`, `compareMetricSelection.ts`,
  `AlarmeTab.svelte`, `CompareTabs.svelte`, `CompareNewEditor.svelte`,
  `alertMetricLabels.ts`, `AlertPresetSelector.svelte`), 1 neu
  (`alarme-tab/activeAlertMetricsFromCatalog.ts`), 1 Kommentar-Anpassung
  (`compareHourlyCatalogIds.ts`), 1 gelöscht (`compareMetricMapping.ts`),
  3 Testdateien neu + 1 Bestandstest nachgezogen
  (`alertMetricCatalogIds.test.ts`, Wortlaute aus AC-9).
- **Invariante aus dem RED-Befund:** **jede** `<AlarmeTab context="vergleich">`-
  Einbettung muss den geladenen Katalog durchreichen — heute drei Stellen
  (`CompareTabs.svelte:1416`, `CompareNewEditor.svelte:386,471`). Der
  Touren-Zweig (`AlarmeScheduleTab.svelte:46`) bleibt unberührt.
- **Effort:** medium.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/renderers/compare_metric_catalog.py::get_compare_metric_catalog()` | READ (bereits live seit E1a-1) | Liefert `alertMetric` je Katalog-Eintrag über `GET /api/compare/metrics` — diese Etappe konsumiert nur |
| `frontend/src/lib/components/alerts-tab/alertMetricTable.ts::ALERTABLE_METRICS` | READ (Referenz-Vokabular) | Reihenfolge und Filter der Empfindlichkeits-Zeilen, unverändert |
| `frontend/src/lib/components/alerts-tab/alertMetricTable.ts::CATALOG_TO_ALERT_METRICS` | UNVERÄNDERT | Touren-Zweig bleibt hartkodiert (E1a-1-Spec AC-3) — nicht Teil dieser Etappe |
| `frontend/src/lib/components/shared/corridor-editor/compareMetricCatalogLoader.ts::loadCompareSelectionEntries` (geteilter Promise-Cache) | READ | Bereits heute der Ladeweg, den `hydrateAlarmeTab()` nutzt — kein neuer Fetch nötig |
| `src/services/compare_alert.py`, `src/services/weather_change_detection.py`, `src/services/alert_preset.py` | UNVERÄNDERT (Harte Auflage #1435) | Alarm-Auswertung; diese Etappe ist reine Anzeige-/Auswahl-Arbeit, keine Auswertungsänderung |
| `docs/specs/modules/feat_1435_e1a_alarmfaehigkeit_register.md` | REFERENZ | Vorgänger-Etappe, liefert `alertMetric` aus, Beleg-/Teststil-Vorbild |
| `docs/reference/api_contract.md` (Section 15/15.1) | REFERENZ | `alertMetric`-Feld bereits dokumentiert (E1a-1) |

## Implementation Details

### 1. Katalog-Typ um `alertMetric` ergänzen

`CompareSelectionEntry` (`compareMetricSelection.ts:7-16`) bekommt ein neues
optionales Feld, analog dem bestehenden Muster für `metric_id`/`aggregation`
(#1373) und `aggregation_label` (#1401 A1):

```ts
export interface CompareSelectionEntry {
	metric: string;
	label: string;
	metric_id?: string;
	aggregation?: string;
	aggregation_label?: string;
	alertMetric?: string | null;   // neu (E1a-2) — Feld aus dem Register-Backend
}
```

`toCompareSelectionEntries()` reicht das Feld **konditional** durch
(`...(m.alertMetric !== undefined ? { alertMetric: m.alertMetric } : {})`),
damit der strikte deepEqual-Vergleich aus #1350 nicht bricht — identisches
Muster zu den drei bestehenden optionalen Feldern in derselben Funktion.
`CompareMetricCatalogEntry` (`types.ts:448-473`) bekommt dasselbe Feld auf
Typ-Ebene (die Rohantwort trägt `alertMetric` bereits seit E1a-1, nur der
Frontend-Typ kennt es noch nicht).

### 2. Neue Ableitungsfunktion (Ersatz für `compareMetricMapping.ts`)

Reine Funktion, liest `alertMetric` direkt aus dem bereits geladenen
Compare-Katalog statt aus einer eigenen Übersetzungstabelle:

```ts
export function deriveActiveAlertMetricsFromCatalog(
	activeMetricKeys: string[],
	catalog: CompareSelectionEntry[]
): AlertMetric[] {
	const byKey = new Map(catalog.map((e) => [e.metric, e]));
	const seen = new Set<AlertMetric>();
	for (const key of activeMetricKeys) {
		const am = byKey.get(key)?.alertMetric;
		if (am) seen.add(am as AlertMetric);
	}
	return ALERTABLE_METRICS.filter((m) => seen.has(m));
}
```

Reihenfolge und Filter laufen weiterhin über `ALERTABLE_METRICS` — unverändert
zum bisherigen Verhalten von `deriveActiveAlertMetrics()`.

### 3. Ladezeitpunkt — Katalog als Prop, NICHT als Modul-Getter im `$derived`

**Zentrale Auflage dieser Etappe:** `registeredCompareMetricCatalog()`
(`compareMetricSelection.ts:78-80`) ist eine einfache Modulvariable, keine
reaktive Größe. Ein `$derived` in `AlarmeTab.svelte`, das diesen Getter
aufruft, würde nach einem späteren (asynchronen) Laden **nicht** neu
rechnen — das Muster ist strukturell gleich dem Risiko, das
`WeatherMetricsTab.svelte:174-176,419-432` bereits löst: dort wird der
geladene Katalog in einer **komponenteneigenen** `$state`-Variable
(`compareCatalog`) gehalten und dann weitergereicht, nicht über den
Modul-Getter im laufenden Rendering nachgeschlagen.

`AlarmeTab.svelte` bekommt daher eine neue Prop (Vergleichs-Zweig, Analogie
zu `CompareOutlookLayoutControls.svelte:37,43`):

```ts
interface Props {
	// ... bestehende Props unverändert ...
	catalog?: CompareSelectionEntry[];   // neu, nur context="vergleich"
}
```

`effectiveActiveMetrics` (Zeilen ~107-111) liest im Vergleichs-Zweig künftig
`deriveActiveAlertMetricsFromCatalog(materializeActiveMetricKeys(wiz?.activeMetricKeys
?? null), catalog ?? [])` statt der gelöschten `deriveActiveAlertMetrics(...)`
— `catalog` ist eine Prop, also reaktiv: ändert `CompareTabs.svelte` den
weitergereichten Wert später, rechnet `$derived` korrekt neu.

`CompareTabs.svelte::hydrateAlarmeTab()` (Zeilen 597-606) lädt den Katalog
bereits heute **vor** dem Setzen von `alarmeHydrated = true`
(`await loadCompareSelectionEntries()`), nur landet das Ergebnis bisher in
einer lokalen Variable innerhalb der Funktion. Diese Etappe hebt das Ergebnis
in eine komponentenweite `$state`-Variable (z. B. `alarmeCatalog`) und reicht
sie an die bestehende `<AlarmeTab context="vergleich" wiz={wizardState}>`
-Instanz (Zeile 1416) als `catalog={alarmeCatalog}` durch. Da `AlarmeTab` erst
hinter `{#if alarmeHydrated}` gemountet wird (Zeile 1407) und `alarmeHydrated`
erst **nach** dem Laden gesetzt wird, ist der Katalog beim ersten Rendern
bereits vollständig geladen (s. AC-5).

### 4. Löschung

`frontend/src/lib/components/shared/alarme-tab/compareMetricMapping.ts`
entfällt vollständig (27 Zeilen). Der einzige Aufrufer
(`AlarmeTab.svelte:39`, Import von `deriveActiveAlertMetrics`) wird auf die
neue Funktion umgestellt. Der Kommentarverweis in
`frontend/src/lib/components/compare/compareHourlyCatalogIds.ts:4` (nennt
`COMPARE_TO_ALERT_METRIC` als Muster) wird auf die neue Funktion umgeschrieben
— reine Kommentarpflege, kein Verhaltensbezug.

### 5. Touren-Zweig — unangetastet

`context="route"` liest `activeMetrics` weiterhin ausschließlich aus der
gleichnamigen Prop (Zeile ~110: `(activeMetrics ?? [])`), berührt weder
`catalog` noch die neue Ableitungsfunktion. `CATALOG_TO_ALERT_METRICS`
(`alertMetricTable.ts`) bleibt unverändert hartkodiert (E1a-1-Spec AC-3).

## Expected Behavior

- **Input:** Ein Nutzer öffnet im Ortsvergleich den Reiter *Wetter-Metriken*
  und aktiviert dort „Böen", „Temperatur" (Minimum) und „Wind"; danach öffnet
  er den Reiter *Alarme*.
- **Output:** Der Reiter zeigt eine Zeile „Böen" (statt bisher fälschlich
  unter „Wind" einsortiert), eine Zeile „Wind (Änderung)" für die aktivierte
  Größe Wind, und neu eine Zeile „Temperatur (Minimum)". Für einen Trip
  (kein Vergleich) ändert sich inhaltlich nichts — dort ändert sich nur der
  Wortlaut der drei Änderungs-Alarme (AC-9).
- **Side effects:** Bereits gespeicherte Alarm-Schwellen bleiben unverändert
  erhalten — nur welche Zeilen angeboten werden, ändert sich. Kein zweiter
  Netzwerk-Request: der Katalog wird über den bereits bestehenden geteilten
  Promise-Cache geladen.

## PO-Entscheidung 2026-07-31 (erledigt, war „Zur Freigabe vorgelegt")

**Frage war:** Wer im Ortsvergleich „Wind (Maximum)" auswählt, sieht künftig
die Alarm-Zeile für den Änderungs-Alarm statt — wie heute, fälschlich — „Böen".
Ist das gewünscht, und wie soll die Zeile heißen?

**Entschieden:** Die Zeile erscheint (kein Rückbau der Bedienbarkeit) und heißt
**„Wind (Änderung)"** statt bisher „Windänderung". Der PO hat auf Konsistenz
der Beschriftungen hingewiesen; die neue Form folgt dem bereits vorhandenen
Stil `Temperatur (Minimum)` / `Temperatur (Maximum)`.

**Folge (Scope-Zuwachs, bewusst mitgenommen):** Die beiden übrigen
Änderungs-Alarme ziehen mit, sonst entsteht innerhalb derselben Tabelle ein
Stilbruch:

| bisher | neu |
|---|---|
| Windänderung | **Wind (Änderung)** |
| Temperaturänderung | **Temperatur (Änderung)** |
| Niederschlagsänderung | **Niederschlag (Änderung)** |

Das betrifft auch den **Touren**-Bereich, weil die Beschriftungen aus einer
gemeinsamen Tabelle stammen (`alertMetricLabels.ts:26-28`). Dort ändert sich
ausschließlich der Wortlaut — welche Zeilen erscheinen und was sie auslösen,
bleibt unangetastet (s. AC-7). Der Grund für die Entscheidung gegen das
kürzere „Wind": diese Zeile warnt bei starker **Änderung** des Windes, nicht
bei hohem Wind; „Wind" allein hätte in einem Werkzeug für Tourenentscheidungen
einen Sturm-Alarm suggeriert, den sie nicht liefert.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer aktiviert im Ortsvergleich eine oder mehrere
  Wetter-Metriken / When er den Reiter *Alarme* öffnet / Then zeigt die
  Empfindlichkeits-Tabelle genau die Alarm-Zeilen, die das zentrale
  Wetter-Namensregister für die ausgewählten Größen als alarmfähig
  ausweist — keine eigene, separat gepflegte Liste entscheidet mehr darüber.
  - Test: `deriveActiveAlertMetricsFromCatalog()` gegen ein realistisches
    Katalog-Fixture (Struktur wie die echte Antwort von
    `GET /api/compare/metrics`, siehe bereits existierendes
    `REAL_CATALOG_FIXTURE`-Muster in
    `compareMetricSelection.test.ts`, ergänzt um `alertMetric`-Werte)
    liefert für eine Auswahl aus mehreren Größen exakt die dazugehörigen
    Alarm-Identitäten, gelesen aus dem Katalog-Feld — nicht aus einer
    zweiten, im Test erfundenen Mini-Tabelle.

- **AC-2:** Given ein Nutzer aktiviert die Wetter-Metrik „Wind (Maximum)" /
  When er den Reiter *Alarme* öffnet / Then erscheint dafür die Zeile
  „Windänderung", NICHT mehr die Zeile „Böen" — wer stattdessen
  „Böen (Maximum)" aktiviert, sieht die Zeile „Böen". Heute zeigt „Wind"
  fälschlich „Böen", während „Böen" selbst gar keine Zeile erzeugt.
  - Test: `deriveActiveAlertMetricsFromCatalog(['wind_max_kmh'], fixture)`
    enthält `'wind_change'`, NICHT `'wind_gust'`;
    `deriveActiveAlertMetricsFromCatalog(['gust_max_kmh'], fixture)` enthält
    `'wind_gust'`, NICHT `'wind_change'`; beide Größen gleichzeitig aktiv
    liefert beide Zeilen, keine verdrängt die andere.

- **AC-3:** Given ein Nutzer aktiviert eine der vier neu hinzugekommenen
  Wetter-Metriken (Böen, Temperatur Minimum, Gewitterenergie/CAPE,
  Nullgradgrenze) / When er im Reiter *Alarme* eine Empfindlichkeit für die
  entsprechende Zeile einstellt und speichert / Then wertet die
  Alarm-Prüfung diese Einstellung tatsächlich aus — die Zeile ist kein
  wirkungsloses Bedienelement, sondern hat dieselbe Wirkung wie jede
  bestehende Alarm-Zeile.
  - Test: für alle vier Ziel-Identitäten (`wind_gust`, `temperature_min`,
    `cape`, `freezing_level`) liefert `deriveActiveAlertMetricsFromCatalog`
    bei aktivierter zugehöriger Wetter-Metrik genau diese Identität; ergänzend
    ein Verweis-Test auf die bereits in E1a-1 verifizierte
    Auswertbarkeits-Tabelle (kein erneuter Python-Nachweis nötig, da
    Auswertung in dieser Etappe unverändert bleibt).

- **AC-4:** Given ein Nutzer hat eine der fünf unveränderten Wetter-Metriken
  (Neuschnee, Sichtweite, Niederschlag, Temperatur Maximum, Gewitter)
  aktiviert / When er den Reiter *Alarme* öffnet / Then zeigt sich exakt
  dieselbe Alarm-Zeile wie vor dieser Änderung — keine dieser fünf
  Zuordnungen ändert sich (Regressionsschutz).
  - Test: für alle fünf Größen liefert `deriveActiveAlertMetricsFromCatalog`
    exakt dieselbe Alarm-Identität wie zuvor `deriveActiveAlertMetrics()`
    (Vorher/Nachher-Assertion je Größe, gegen dasselbe Fixture).

- **AC-5:** Given ein Nutzer öffnet den Reiter *Alarme* eines Ortsvergleichs
  mit bereits aktiven Wetter-Metriken / When die Seite den Reiter zum ersten
  Mal rendert / Then zeigt die Empfindlichkeits-Tabelle zu keinem Zeitpunkt
  fälschlich „keine Metriken", obwohl tatsächlich aktive Metriken vorhanden
  sind — auch nicht kurzzeitig während des Ladens (Fehlerklasse #1320).
  - Test: struktureller Nachweis, dass `AlarmeTab.svelte` erst gemountet
    wird, nachdem der Katalog geladen ist (Prop statt Modul-Getter im
    `$derived`, s. Implementation Details Punkt 3) — ergänzend ein
    Unit-Test, der belegt, dass `effectiveActiveMetrics` bei einem leeren
    initialen `catalog`-Prop-Wert, gefolgt von einer Aktualisierung der Prop,
    korrekt neu berechnet (Beweis der Reaktivität, nicht nur des
    Anfangszustands).

- **AC-6:** Given ein Nutzer hat bereits eine Empfindlichkeit für eine
  Alarm-Zeile gespeichert, die nach dieser Änderung nicht mehr angezeigt
  wird (weil die zugehörige Wetter-Metrik nicht mehr aktiv ist oder ihre
  Zuordnung sich geändert hat) / When die Änderung ausgeliefert wird, ohne
  dass der Nutzer etwas tut / Then bleibt der gespeicherte Wert unverändert
  erhalten — nur das Bedienelement dafür ist vorübergehend nicht sichtbar,
  keine Nutzerdaten gehen verloren.
  - Test: Roundtrip-Test mit einer Preset-Fixture, die einen Schwellenwert
    für eine nicht mehr angezeigte Alarm-Identität trägt — nach Anwendung
    der geänderten Ableitung bleibt der gespeicherte Wert byteidentisch
    (kein Persistenz-Code-Pfad ist in dieser Etappe angefasst).

- **AC-7:** Given ein Trip (kein Ortsvergleich) mit denselben aktiven
  Wetter-Metriken wie vor dieser Änderung / When der Reiter *Alarme* im
  Trip-Kontext gerendert wird / Then erscheinen exakt dieselben Alarm-Zeilen
  wie zuvor und sie lösen dasselbe aus — für Touren ändert sich inhaltlich
  nichts; einzige Ausnahme ist der in AC-9 beschriebene Wortlaut der drei
  Änderungs-Alarme.
  - Test: bestehende Tests (`alertMetricTable.test.ts`,
    `issue_864_alert_metric_levels.test.ts`) bleiben unverändert grün; ein
    ergänzender Struktur-Check bestätigt, dass `AlarmeTab.svelte` im
    `context="route"`-Zweig ausschließlich die `activeMetrics`-Prop liest
    (kein neuer Katalog-Fetch, keine Referenz auf die neue Ableitung in
    diesem Zweig).

- **AC-8:** Given der Programmcode nach Auslieferung dieser Änderung / When
  man nach der alten, handgepflegten Zuordnungs-Liste sucht, die früher
  entschied, welche Alarm-Zeile zu welcher Wetter-Metrik gehört / Then
  existiert diese Liste nicht mehr — jede künftige Änderung an dieser
  Zuordnung muss zwingend über das zentrale Register laufen, kein neues,
  eigenes Vokabular kann daneben entstehen (Ratsche gegen Nachwachsen,
  #1435).
  - Test: struktureller Nachweis (Datei-Existenz-Prüfung), dass
    `compareMetricMapping.ts` nicht mehr existiert, UND dass
    `AlarmeTab.svelte` keinen Import aus dieser Datei mehr enthält.

- **AC-9:** Given ein Nutzer öffnet den Reiter *Alarme* — im Ortsvergleich
  oder bei einer Tour / When er die Zeilen liest, die bei einer starken
  Änderung des Wetters warnen / Then heißen sie „Wind (Änderung)",
  „Temperatur (Änderung)" und „Niederschlag (Änderung)" — einheitlich im
  selben Stil wie die bereits vorhandenen Zeilen „Temperatur (Minimum)" und
  „Temperatur (Maximum)", und an jeder Stelle der Oberfläche gleich
  geschrieben. Ausgelöst wird davon unverändert dasselbe wie zuvor; es
  ändert sich nur der angezeigte Text.
  - Test: `ALERT_METRIC_LABELS` führt die drei neuen Wortlaute (bestehende
    Zusicherungen in `alertMetricCatalogIds.test.ts:97-107` werden auf die
    neuen Wortlaute nachgezogen — sie prüfen weiterhin dieselbe Eigenschaft);
    ergänzend ein Test, der die Voreinstellungs-Auswahl
    (`AlertPresetSelector.svelte:22-23`, führt dieselben Beschriftungen ein
    zweites Mal) gegen `ALERT_METRIC_LABELS` abgleicht und rot wird, sobald
    die beiden Stellen auseinanderlaufen.
  - Abgrenzung: Die Zusammenführung dieser zweiten Beschriftungs-Liste in die
    zentrale Tabelle ist NICHT Teil dieser Etappe (sie trägt zugleich
    Schwellwerte und gehört damit zu #1435 E4) — hier wird nur der Wortlaut
    angeglichen und die Dublette per Test gegen weiteres Auseinanderlaufen
    gesichert.

## Known Limitations

- **Die vierte Liste `_ALERT_METRIC_TO_CATALOG_ID` bleibt bestehen.**
  Wie bereits in der E1a-1-Spec beschrieben: das Abweichungs-Alert-Subsystem
  (`weather_change_detection.py`) wird durch diese Etappe nicht angefasst
  und bleibt die maßgebliche Auswertbarkeits-Quelle — ausdrücklicher
  Kandidat für eine spätere #1435-Etappe.
- **`temperature_cold` wird nicht abgeschafft.** Der interne
  Kältealarm-Eintrag bleibt bestehen; das sichtbare Register-Feld
  `alertMetric` sitzt auf der sichtbaren Größe `temperature` (beide
  Richtungen, min UND max) — unverändert zu E1a-1.
- **Der Touren-Zweig bleibt hartkodiert.**
  `alertMetricTable.ts::CATALOG_TO_ALERT_METRICS` wird von dieser Etappe
  nicht angefasst (E1a-1-Spec AC-3) — Konsolidierung des Touren-Zweigs ist
  ausdrücklich nicht Teil von E1a-2.
- **Die Beschriftungs-Dublette bleibt bestehen.**
  `AlertPresetSelector.svelte:22-23` führt die Alarm-Beschriftungen (samt
  Voreinstellungs-Schwellwerten) ein zweites Mal neben
  `alertMetricLabels.ts::ALERT_METRIC_LABELS`. AC-9 gleicht nur den Wortlaut
  an und sichert den Gleichlauf per Test; die Zusammenführung gehört zu
  #1435 E4 (Schwellen), weil dort die Zahlen mitwandern. Nebenbefund-Triage:
  Sammel-Eintrag in #1199, kein eigenes Issue (kein nutzersichtbares
  Fehlverhalten, solange der Gleichlauf-Test steht).
- **Im Ortsvergleich bleibt der Zugang zu Änderungsraten-Alarmen auf Wind
  beschränkt.** `temperature_change`/`precipitation_change` sind im
  Ortsvergleich weiterhin nicht über eine eigene Wetter-Metrik erreichbar
  (nur `wind_change` entsteht, weil die Größe Wind keine eigene absolute
  Alarm-Identität hat und deshalb auf ihren Änderungs-Alarm zurückfällt) —
  das ist identisch zum heutigen Verhalten, kein Rückschritt dieser Etappe.
- **Harte Auflage #1435 eingehalten:** `compare_alert.py`,
  `weather_change_detection.py` und `alert_preset.py` werden von dieser
  Etappe nicht verändert. E1a-2 ist reine Anzeige-/Auswahl-Arbeit im
  Frontend, keine Änderung an der Alarm-Auswertung selbst.
- **Renderer-Mail-Gate (#811) nicht betroffen:** keine Datei dieser Etappe
  liegt unter `src/output/renderers/email/*.py` o. ä.
- **Kein automatisierter Cross-Language-Wächter** zwischen dieser
  Frontend-Ableitung und dem Python-Register — die Vollständigkeits-/
  Auswertbarkeits-Wächter dafür laufen bereits in E1a-1
  (`test_alert_metric_register_declaration.py`) und werden hier nicht
  erneut geführt, da diese Etappe das Register selbst nicht ändert.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Diese Spec setzt das in E1a-1 bereits etablierte,
  PO-freigegebene Prinzip „eine zentrale Registerquelle statt redaktionell
  duplizierter Vokabulare" auf den letzten verbliebenen Frontend-Konsumenten
  (Alarme-Reiter, Vergleichs-Zweig) fort — keine neue Grundsatzentscheidung
  im Sinne der CLAUDE.md-ADR-Trigger (Kanäle, Provider, Auth,
  Editor-Paradigma, Test-/Deploy-Strategie unberührt).

## Changelog

- 2026-07-31: Initial spec created (Feature #1435 Etappe E1a-2, Fortsetzung
  von E1a-1/`98d1a1f6`). Belegstellen gegen den aktuellen Code verifiziert
  (`AlarmeTab.svelte`, `compareMetricSelection.ts`, `CompareTabs.svelte`,
  `WeatherMetricsTab.svelte`, `compareMetricMapping.ts`), nicht aus dem
  Kontextdokument übernommen.
