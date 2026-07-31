# Context: #1435 E1a-2 — Alarme-Reiter liest das Register

> Vorgänger: E1a-1 (`98d1a1f6`, live) — das Register hält die Alarmfähigkeit und
> liefert sie über `GET /api/compare/metrics` aus. Diese Etappe macht die
> Zusammenführung **sichtbar**.

## Request Summary

Der Alarme-Reiter des Ortsvergleichs entscheidet heute über eine eigene
6-Zeilen-Frontend-Liste (`compareMetricMapping.ts::COMPARE_TO_ALERT_METRIC`),
welche Alarm-Zeilen in der Empfindlichkeits-Tabelle erscheinen. Diese Liste soll
fallen; die Antwort kommt künftig aus dem Feld `alertMetric` der bereits
ausgelieferten Katalog-Antwort. Die in E1a-1 nur im Backend hergestellte
Entkreuzung „Wind → Böen" wird dadurch in der Oberfläche wirksam.

## Related Files

| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/shared/alarme-tab/compareMetricMapping.ts` | **Fällt.** 26 Zeilen, 6 Einträge, importiert `ALERTABLE_METRICS` für die Reihenfolge |
| `frontend/src/lib/components/shared/AlarmeTab.svelte:39,105-111` | Einziger Aufrufer von `deriveActiveAlertMetrics`; `effectiveActiveMetrics` speist `AlertMetricLevelTable` |
| `frontend/src/lib/types.ts:444-473` | `CompareMetricCatalogEntry` — kennt `alarmCapable`, **noch nicht** `alertMetric` |
| `frontend/src/lib/components/shared/weather-metrics-tab/compareMetricSelection.ts:7-16,27-49,69-80` | `CompareSelectionEntry` + Katalog-Registrierung (`registerCompareMetricCatalog` / `registeredCompareMetricCatalog`) — der naheliegende Träger für `alertMetric` |
| `frontend/src/lib/components/shared/corridor-editor/compareMetricCatalogLoader.ts` | Geteilter Promise-Cache `loadCompareSelectionEntries()` (ein Fetch pro Seiten-Load); E1a-1-Spec Zeile 120 sieht die Wiederverwendung durch AlarmeTab bereits vor |
| `frontend/src/lib/components/compare/CompareTabs.svelte:597-620` | `hydrateAlarmeTab()` lädt den Katalog **vor** dem Hydrieren der Alarm-Felder — der Ladeweg existiert also schon |
| `frontend/src/lib/components/alerts-tab/alertMetricTable.ts:202-217` | `ALERTABLE_METRICS` (13) — Anzeige-Reihenfolge und Filter; bleibt |
| `src/output/renderers/compare_metric_catalog.py:276-282` | Liefert `alertMetric` + `alarmCapable` (aus `alert_metric_for()`) |
| `internal/router/router.go:155` | Go ist **reiner Passthrough-Proxy** → **kein Go-Eingriff nötig** |
| `frontend/src/lib/components/compare/compareHourlyCatalogIds.ts:4` | Verweist im Kommentar auf `COMPARE_TO_ALERT_METRIC` als Muster — Kommentar zieht nach, Code nicht betroffen |

## Existing Patterns

- **Katalog-Feld ergänzen:** `metric_id`/`aggregation` (#1373) und
  `aggregation_label` (#1401 A1) wurden nach exakt demselben Muster ergänzt —
  optionales Feld in `CompareMetricCatalogEntry`, konditionales Durchreichen in
  `toCompareSelectionEntries()` (`...(x !== undefined ? {x} : {})`, damit der
  strikte deepEqual-Vergleich aus #1350 nicht bricht).
- **Katalog im Browser als Übersetzungsquelle:** `registeredCompareMetricCatalog()`
  ist bereits die *einzige* Quelle für die Übersetzung Auswahl-Schlüssel ↔
  Größe+Auswertung (#1373 S2 B). Eine zweite Übersetzung daneben wäre genau der
  Fehler, den #1435 abstellt.
- **Fallback-Muster bei ungeladenem Katalog:** `resolveHourlyMetricLabel()`
  (#1401 B) zeigt, wie mit „Katalog noch nicht da" umgegangen wird — Fläche
  bleibt bedienbar, alter Wortlaut greift.
- **Teilungs-Invariante:** `AlarmeTab.svelte` ist der geteilte Baustein für
  `context="route"|"vergleich"`. Nur der Vergleichs-Zweig geht über
  `deriveActiveAlertMetrics`; der Trip-Zweig bekommt `activeMetrics` als Prop.

## Dependencies

- **Upstream:** `GET /api/compare/metrics` (Python) → Go-Proxy → geteilter
  Promise-Cache → `registeredCompareMetricCatalog()`.
- **Downstream:** `AlertMetricLevelTable.svelte` (Empfindlichkeits-Tabelle),
  `wiz.metricAlertLevels` (Persistenz `display_config`), `compare_alert.py`
  (wertet die gespeicherten Level aus — **darf sich nicht ändern**).

## Was sich für den Nutzer ändert — gemessen, nicht geschätzt

Gegenüberstellung alte Frontend-Liste vs. Register-Feld, gegen den echten
Katalog gerechnet (26 Einträge):

| Compare-Schlüssel | heute | mit Register | Bewertung |
|---|---|---|---|
| Neuschnee, Sichtweite, Niederschlag, Temperatur Max, Gewitter | unverändert | unverändert | 5 × gleich |
| **Wind (Max)** | `wind_gust` (Böen!) | `wind_change` (Windänderung) | Kreuz-Verdrahtung fällt |
| **Böen (Max)** | — | `wind_gust` | neu, korrekt |
| **Temperatur Min** | — | `temperature_min` | neu |
| **Gewitterenergie (CAPE)** | — | `cape` | neu |
| **Nullgradgrenze** | — | `freezing_level` | neu |

Fünf Zeilen ändern sich, vier davon sind Zugewinn. Die Empfindlichkeits-Tabelle
im Ortsvergleich wächst also — jede neue Zeile entspricht einer Größe, die die
Alarm-Auswertung nachweislich beherrscht (E1a-1-Wirksamkeits-Wächter).

## Existing Specs

- `docs/specs/modules/feat_1435_e1a_alarmfaehigkeit_register.md` — Vorgänger,
  inkl. Known Limitations (vierte Liste `_ALERT_METRIC_TO_CATALOG_ID`,
  `temperature_cold`)
- `docs/specs/modules/fix_1401b_register_stundenverlauf_alarme.md` — Belegstil
  und Fallback-Muster
- `docs/specs/modules/issue_1258_alarme_tab_official_warnings.md` — Herkunft von
  `AlarmeTab.svelte` und `compareMetricMapping.ts`
- `docs/reference/api_contract.md` — trägt `alertMetric` bereits (E1a-1)

## Risks & Considerations

1. **Reaktivität / Ladezeitpunkt (Hauptrisiko).** `registeredCatalog` ist eine
   einfache Modulvariable, keine reaktive Größe. `effectiveActiveMetrics` ist ein
   `$derived` — wird der Katalog erst nach dem ersten Rendern registriert,
   aktualisiert sich die Tabelle nicht von selbst. `hydrateAlarmeTab()` lädt zwar
   vorher, aber der Reiter rendert währenddessen bereits. Fehlerbild wäre exakt
   #1320: „keine Metriken", obwohl welche aktiv sind. **Muss auf Staging gegen
   den echten Ladeweg geprüft werden, nicht nur im Unit-Test.**
2. **Gespeicherte Empfindlichkeiten.** `wiz.metricAlertLevels` ist nach
   Alarm-Identität geschlüsselt. Wer heute „Wind" aktiv hat, hat womöglich einen
   Wert unter `wind_gust` gespeichert. Nach der Umstellung erscheint dieselbe
   Zeile nur noch, wenn „Böen" aktiv ist. Zu klären: bleibt der gespeicherte Wert
   erhalten (Read-Modify-Write, keine Löschung) — Regel „Daten-Schema-Reworks".
3. **Ist „Windänderung" die richtige Antwort auf „Wind ausgewählt"?** Der
   Rückfall auf `change_alert_metric` ist bewusst so gebaut (E1a-1 F001), aber
   für die Oberfläche heißt es: die Tabelle zeigt eine Zeile „Windänderung", wo
   der Nutzer „Wind" ausgewählt hat. Das ist eine Produktfrage für die Spec.
4. **Trip-Zweig darf sich nicht bewegen.** `context="route"` nutzt eine andere
   Quelle (Props). Regressionsnachweis für beide Zweige nötig — die Komponente
   ist geteilt (Anti-Pattern-Referenz #1170).
5. **Alarm-Auswertung unangetastet.** Harte Auflage aus #1435: `compare_alert.py`
   und die Abweichungs-Engine ändern ihr Verhalten nicht. E1a-2 ist eine reine
   Anzeige-/Auswahl-Etappe.
6. **`ALERTABLE_METRICS` bleibt Reihenfolge-Quelle.** Die neue Ableitung muss
   weiter danach sortieren und dagegen filtern, sonst erscheinen Zeilen in
   zufälliger Katalogreihenfolge oder Identitäten, die die Tabelle nicht kennt.

---

## Analysis

### Type

Feature (Fortsetzung von E1a-1) — sichtbar wirksame Zusammenführung, keine
Fehlerbehebung im engeren Sinn, aber sie beseitigt eine falsche Zuordnung.

### Risiken 1 und 2 sind untersucht und aufgelöst

**Ladezeitpunkt (Risiko 1) — entschärft, mit Auflage.**
`CompareTabs.svelte:1407-1417` mountet `AlarmeTab` hinter `{#if alarmeHydrated}`;
`hydrateAlarmeTab()` (`:597-606`) `await`-et `loadCompareSelectionEntries()` **vor**
`hydrateAlarmFieldsFromPreset(...)` und setzt `alarmeHydrated` erst danach. Der
Katalog ist beim Mounten also geladen — ein kurzzeitiges „keine Metriken" ist
strukturell ausgeschlossen.
**Auflage:** `registeredCatalog` (`compareMetricSelection.ts:69`) ist eine reine
Modulvariable, **nicht reaktiv**. Ein `$derived`, das sie liest, würde nach einem
späteren Laden nicht neu rechnen. Der Katalog wird deshalb **als Übergabewert
(Prop/Parameter) hereingereicht**, nicht im Reiter über den Modul-Getter
nachgeschlagen — genau das Muster von `WeatherMetricsTab.svelte:174-176,419-432`
und `CompareOutlookLayoutControls.svelte:37,43`. Der heutige Trigger ist die
Neuzuweisung von `wiz.activeMetricKeys` (`compareHubWizardBridge.ts:494`,
bedingungslos frisches Array) — auf diesen Zufall darf sich die neue Ableitung
nicht verlassen.

**Persistenz (Risiko 2) — kein Verlustrisiko.**
Schreibpfad: `AlarmeTab.svelte:128` spreadet stets den vollen bisherigen Stand
(`{...wiz.metricAlertLevels, [metric]: level}`) → `compareEditorSave.ts:142-145`
(`display_config` per Spread erhalten) → Go `compare_preset.go:300` →
`config_merge.go:11-22` (feldweises Read-Modify-Write) → Datei
`data/users/<user_id>/briefings/<preset_id>.json`. Ein Wert für eine Identität
ohne sichtbare Zeile bleibt erhalten, nur nicht mehr über diese Zeile editierbar.
Kein Fall der Klasse BUG-DATALOSS-GR221 (#102).

**Vorbelegung.** `AlertMetricLevelTable.svelte:83` zeigt `levels[metric] ?? 'standard'`
— reiner Anzeige-Fallback, kein Schreibvorgang; das bloße Erscheinen einer Zeile
macht den Vergleich nicht „geändert". Serverseitig füllt `alert_preset.py:239-268`
ohnehin `standard` für aktive, nicht explizit gesetzte Größen nach.

### Der entscheidende Befund: kein Bedienelement ohne Wirkung

Alle fünf betroffenen Identitäten sind in der Auswertung **bereits vollständig
verdrahtet** — der Engpass war ausschließlich die Frontend-Liste:

| Identität | Compare-Auswertung | Alarm-Engine | Schwellwerte |
|---|---|---|---|
| `wind_gust` (Böen) | `compare_alert.py:46-57` `gust_max_kmh→"gust"` | `weather_change_detection.py:82-99` | `alert_preset.py:39-57` |
| `temperature_min` | `temp_min_c→"temperature_cold"` | `TEMPERATURE_MIN→("temperature_cold","temperature")` | ✓ |
| `cape` | `cape_max_jkg→"cape"` | `CAPE→("cape",)` | ✓ |
| `freezing_level` | `freezing_level_m→"freezing_level"` | `FREEZING_LEVEL→("freezing_level",)` | ✓ |
| `wind_change` | `wind_max_kmh→"wind"` | `WIND_CHANGE→("wind",)` | ✓ |

Das bestätigt die These von #1435 an einem konkreten Fall: die Fähigkeit war da,
nur die handgepflegte Liste davor kannte sie nicht.

**Lesefalle (für Adversary/Review):** `weather_change_detection.py:111-118`
(`_ALERTABLE_METRIC_VALUES`, nur 6 Werte) sieht wie eine engere Grenze aus,
betrifft aber allein die Go-Rücksynchronisation von `alert_rules` (#1257) — nicht
die Compare-Alarm-Auswertung.

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `frontend/src/lib/components/shared/alarme-tab/compareMetricMapping.ts` | DELETE | Die 6-Zeilen-Liste fällt; `deriveActiveAlertMetrics` zieht um bzw. wird umgebaut |
| `frontend/src/lib/components/shared/AlarmeTab.svelte` | MODIFY | Neue Prop für den Katalog; `effectiveActiveMetrics` leitet daraus ab |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | Reicht den bereits geladenen Katalog an `AlarmeTab` durch |
| `frontend/src/lib/types.ts` | MODIFY | `CompareMetricCatalogEntry.alertMetric?: string \| null` |
| `frontend/src/lib/components/shared/weather-metrics-tab/compareMetricSelection.ts` | MODIFY | `CompareSelectionEntry.alertMetric` + konditionales Durchreichen |
| `frontend/src/lib/components/compare/compareHourlyCatalogIds.ts` | MODIFY | Nur Kommentar-Verweis auf die gelöschte Datei |
| Tests (Frontend, `node:test`) | CREATE/MODIFY | Ableitung aus dem Katalog, Entkreuzung, Trip-Zweig unverändert |

**Nicht angefasst (bewusst):** `compare_alert.py`, `weather_change_detection.py`,
`alert_preset.py` (harte Auflage #1435), `alertMetricTable.ts::CATALOG_TO_ALERT_METRICS`
(Trip-Zweig, bleibt laut E1a-1-Spec AC-3 hartkodiert), Go (reiner Proxy).

### Scope Assessment

- Dateien: 6 Produktivdateien + Tests
- LoC: ~ +120 / −40 Produktivcode, Tests zusätzlich — LoC-Limit 250 wird knapp,
  Überschreitung nur bei Testumfang wahrscheinlich (wie E1a-1)
- Risiko: **MITTEL** — geteilter Baustein, aber der Trip-Zweig läuft über einen
  anderen Pfad und wird nicht berührt

### Technical Approach

1. `alertMetric` im Katalog-Typ ergänzen und in `toCompareSelectionEntries()`
   konditional durchreichen (Muster #1373/#1401 A1).
2. `deriveActiveAlertMetrics(activeKeys, catalog)` bekommt den Katalog als
   **Parameter** (statt eines Modul-Getters im `$derived`) und schlägt
   `entry.alertMetric` nach; Filter/Reihenfolge weiterhin über `ALERTABLE_METRICS`.
3. `AlarmeTab.svelte` erhält den Katalog als Prop; `CompareTabs.svelte` reicht den
   in `hydrateAlarmeTab()` bereits geladenen Katalog durch.
4. `compareMetricMapping.ts` löschen.

### Open Questions

- [ ] **Produktfrage (PO):** Wer im Ortsvergleich „Wind (Maximum)" auswählt, sieht
      künftig die Alarm-Zeile **„Windänderung"** statt fälschlich „Böen". Ist das
      die gewünschte Antwort — oder soll für „Wind" gar keine Alarm-Zeile
      erscheinen? Empfehlung: „Windänderung" zeigen (folgt dem Register, ist
      wirksam, und „gar keine Zeile" wäre gegenüber heute ein Verlust).
      → wird mit der Spec zur Freigabe vorgelegt.
- [x] Ladezeitpunkt — geklärt (Prop statt Modul-Getter)
- [x] Datenverlust — geklärt (kein Risiko)
- [x] Wirkung der neuen Zeilen — geklärt (alle wirksam)
