# Context: fix-1360-compare-tab-konzept

## Request Summary

Auslöser ist #1360 (Layout-Tab des Ortsvergleichs: Orts-Chips und Kanal-Pillen sind
bedienlose Attrappen mit falscher „max 8"-Aussage). Der PO hat die Einzelbehebung
abgelehnt und ein **Gesamtkonzept** verlangt: welcher Tab regelt was, stimmig über
die ganze Fläche — „kein Stückelweg, indem nur ein Tab betrachtet wird".

## Ausgangslage: eine Familie, kein Einzelfall

Aus dem PO-Audit vom 2026-07-24 stammen fünf offene Meldungen zur selben Fläche:

| Nr. | Tab | Kern |
|---|---|---|
| #1359 | Orte / Metriken | Reihenfolge nicht einstellbar, Orte-Drag&Drop wirkungslos (Mail sortiert alphabetisch) |
| #1360 | Layout | Orts-Chips + Kanal-Pillen ohne Handler; „max 8" ist ein Trip-Spaltenbudget, falsch auf Orte angewandt |
| #1361 | Layout (Stundenverlauf) | Zeitfenster wirkungslos, 3-Tages-Block nicht konfigurierbar, stille Fallbacks |
| #1362 | Wetter-Metriken | Telegram/SMS geben nur 6 von 26 wählbaren Metriken aus |
| #1366 | Wetter-Metriken | leere Metrik-Auswahl liefert in der Mail ALLE Metriken statt keiner |

Epic **#1301** (geschlossen, PO-Freigabe 2026-07-17) hatte für genau diese Fläche
bereits das Zielbild und die Ziel-Tab-Reihe festgeschrieben; Scheibe C2 verlangte
wörtlich „Attrappen raus" und für `channel_layouts`/`top_n`: raus aus der
**Bedienung**, nicht aus der **Persistenz**. Der Layout-Tab hat die echte
Stundenverlauf-Steuerung bekommen — die Attrappen daneben blieben stehen.

## Strukturbefund: der Layout-Tab ist der einzige Compare-Sondertab

| | Tabs |
|---|---|
| **Trip** (`trip-detail/TripTabs.svelte:78-84`) | Übersicht · Etappen & Wegpunkte · Wetter-Metriken · Wertebereiche · Alarme · Versand · Vorschau — **7, kein Layout-Tab** |
| **Vergleich** (`compare/compareTabsResolve.ts:7-21`) | Übersicht · Orte · Wetter-Metriken · Wertebereiche · **Layout** · Alarme · Versand · Vorschau — **8** |

Nach der Trip/Compare-Teilungs-Invariante (CLAUDE.md) ist eine Compare-eigene
Fläche ohne Trip-Pendant der dokumentierte Default-Fehler. Der Layout-Tab ist die
einzige verbliebene solche Fläche.

Wie der Trip die Frage „wie kommt es je Kanal an" beantwortet: **gerendert, nicht
behauptet** — `WeatherV2MailPreview` im Wetter-Metriken-Tab
(`shared/WeatherMetricsTab.svelte:954,1129`), Kanal-Umschalter, Sheet „So kommt es an".
Der Vergleich hat dafür sogar einen eigenen Tab **Vorschau**
(`CompareTabs.svelte:1438-1470`): echte Ausgabe je Kanal + Test-Versand.

## Zielbild (PO 2026-07-24) — festgeschrieben als Epic #1372

> Als Nutzer wähle ich **einmal** aus, welche Wettergrößen mich grundsätzlich
> interessieren. Anschließend bestimme ich, welche davon in den **Vergleich**, in
> die **Stundentabelle** und in den **Ausblick** kommt. Anschließend **sortiere**
> ich jeweils.

**Ursache, die das nötig macht** (PO: „Warum gibt es zwei unterschiedliche Listen
von Wettermetriken. Das ist fatal!!!!"): Es gibt sachlich EINEN Katalog
(`src/app/metric_catalog.py`, 26 Größen), und jeder Eintrag kennt beide
Erscheinungsformen — `dp_field` (Stundenwert) und `summary_fields`
(Tagesauswertungen min/max/Ø). Benutzt wird er nirgends vollständig:

| Fläche | Liste | Problem |
|---|---|---|
| Vergleichstabelle | `compare_metric_catalog.py` / `compare_metric_ids.py` | Auswertung steckt im Namen — „Temperatur max"/„Temperatur min" sind zwei Einträge statt einer Größe mit zwei Auswertungen (26 Einträge für ca. 15 Größen) |
| Stundentabelle | `compare_hourly_metric_ids.py:12-27` | dritte, disjunkte Liste mit 10 Einträgen, ohne Bezug zu den anderen |
| Trip | `MetricConfig.aggregations` | Feld existiert, **kein Renderer liest es** (#1357), keine Auswahlfläche |

Dokumentiert als „vier inkompatible Metrik-Vokabulare"
(`docs/context/fix-1094-compare-config.md`). Fehlerklasse daraus: Größen wandern
durch Übersetzungstabellen; fehlt ein Eintrag, verschwindet der Wert **still**
(#1285, #1296, #1324, #1362, #1361 Befund 3).

**Scheiben (Epic #1372):** S1 #1360+#1361 (Layout-Reiter auflösen, Stundenverlauf
ehrlich) · S2 #1373 (ein Katalog für die Oberfläche) · S3 #1361 Befund 2 + #1366
(Zuordnung je Ausgabe) · S4 #1357 (Auswertung wählbar, geteilt) · S5 #1362, #1356
(Kanal-Treue) · S6 #1371, #1359.

**Invarianten:** kein Element ohne Wirkung · kein stilles Verwerfen · geteilt
bauen · Datenerhalt (Felder raus aus der Bedienung, nicht aus der Persistenz).

## PO-Entscheidungen 2026-07-24 (verbindlich)

**Zuständigkeit je Reiter — der Vertrag:**

| Reiter | Zuständigkeit (ein Satz) |
|---|---|
| Übersicht | Nur lesen: Zustand + Sprungmarken. Keine Einstellung. |
| Orte | Welche Orte verglichen werden — und in welcher Reihenfolge (#1359) |
| **Wetter-Metriken** | **Welche Werte erscheinen und in welcher Folge — für BEIDE Tabellen: Tagesvergleich und Stundenverlauf** |
| Wertebereiche | Wie Werte gelesen werden: **markieren**. „Warnen" entfällt (#1371) |
| ~~Layout~~ | **entfällt** |
| Alarme | Wann außer der Reihe etwas rausgeht: Empfindlichkeit, Ruhezeiten, Kanäle |
| Versand | Wer, wann, über welche Kanäle |
| Vorschau | Prüfen: echte Ausgabe je Kanal + Test-Versand |

1. **Layout-Reiter auflösen.** Die Stundenverlauf-Steuerung wird zum zweiten Block
   im Reiter Wetter-Metriken — mit einstellbarer Reihenfolge und Kanal-Vorschau,
   analog zum Tagesvergleich. Orts-Chips, Kanal-Pillen und die falsche
   „max 8"-Aussage fallen ersatzlos. Danach haben Vergleich und Trip dieselben
   sieben Reiter.
2. **„Warnen"-Häkchen entfernen** (→ neues Issue **#1371**, beide Kontexte).
3. **Paketschnitt:** #1360 + #1361 zusammen; #1362/#1366 und #1359 folgen als
   eigene Lieferungen im selben Rahmen.

**Belegte Befunde, die zu diesen Entscheidungen geführt haben:**

- Die Spaltenfolge der **Stundentabelle** ist heute nicht einstellbar, aber
  wirksam: `applyHourlyMetricToggle` (`compareHourlyMetricDefs.ts:59-73`) hängt
  neu Angehaktes hinten an, `_visible_hour_metrics`
  (`compare_html.py:609-622`) folgt exakt dieser Klick-Liste. Die Reihenfolge
  entsteht also aus der Bedien-Historie.
- Die **Matrix**-Reihenfolge ist dagegen sauber gelöst: Abschnitt `reihenfolge`
  im geteilten Metrik-Tab (`weatherMetricsTabSections.ts:33-38`, seit #1359 für
  beide Kontexte), Renderer folgt `enabled_metrics`
  (`compare_html.py:475-490`) — inklusive echter Kanal-Vorschau
  (`LayoutTab` + `WeatherV2MailPreview`, `WeatherMetricsTab.svelte:934-975`).
- **`Corridor.notify` („Warnen") hat keinen Konsumenten**: gespeichert
  (`loader.py:228,1506`, `internal/model/trip.go:74`), im Alarme-Tab
  zusammengefasst (`alarmeTabSections.ts:38-41`), aber von keinem Alert-Service
  gelesen. Alarme sind seit PO-Entscheidung 2026-06-14 (#813) Δ-Abweichungs-
  Wächter mit Vorlagen-Schwellen (`alert_preset.py`).

## Related Files

| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/compare/CompareTabs.svelte` | Hub mit allen 8 Panels; `LAYOUT_LIMIT_PILLS:774-775`, Layout-Panel `1292-1345`, Vorschau-Panel `1438ff` |
| `frontend/src/lib/components/compare/compareTabsResolve.ts` | Single Source of Truth der Compare-Tab-Liste |
| `frontend/src/lib/components/molecules/CompareLayoutRow.svelte` | Attrappen-Zeile: `<Pill>` ohne Handler (`:68-70`), Konstante `CHANNEL_CONSTRAINT:26` mit „max 8" |
| `frontend/src/lib/components/compare/channelChipCount.ts` | wendet Trip-Spaltenbudget auf Orte an |
| `frontend/src/lib/components/trip-detail/metricsEditor.ts:226-230` | `CHANNEL_COL_BUDGET` — Budget für **Metrik-Spalten**, nicht Orte |
| `frontend/src/lib/components/shared/CompareHourlyLayoutControls.svelte` | die **einzige** echte Einstellung im Layout-Tab |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | geteilter Metrik-Tab (Trip + Vergleich + beide Anlege-Seiten) |
| `frontend/src/lib/components/compare/CompareInhaltSection.svelte` | toter Bestand: nirgends importiert, enthält u.a. die `top_n`-Bedienung |
| `src/services/report_config_resolver.py:192-208` | löst `top_n_details` auf (Default 3, Clamp 1..10) |
| `src/output/renderers/email/compare_html.py:1089` | verwirft `top_n_details` ausdrücklich |
| `src/output/renderers/comparison.py:370-467` | Telegram-Vergleich: **alle** Orte, 7 Metrikwerte je Ort, 4096-Zeichen-Grenze mit ausgewiesenem Rest |
| `src/output/renderers/comparison.py:540ff` | SMS-Vergleich: alle Orte flach, Kürzung nach Zeichenbudget mit Marker |

## Existing Patterns

- **Geteilte Tab-Organismen** in `shared/`: `WeatherMetricsTab`, `VersandTab`,
  `AlarmeTab`, `ChannelToggle`, `AlertChannelPicker`, `TelegramKurzstilToggle`,
  `CompareHourlyLayoutControls` — Aufrufer jeweils Trip-Detail **und** Compare-Hub
  bzw. die beiden Anlege-Seiten (`TripNewEditor`, `CompareNewEditor`).
- **Attrappen-Verbot** ist im Compare-Editor bereits ausgesprochen
  (`WeatherMetricsTab.svelte:741-743`: jedes sichtbare Element hat Mail-Wirkung).
- **Kanal-Wirklichkeit gerendert statt behauptet**: `WeatherV2MailPreview`,
  Compare-Vorschau-Tab.
- **Datenerhalt**: Read-Modify-Write mit Merge (`compareEditorSave.ts`,
  `unknownCorridors`-Muster) — Felder dürfen aus der Bedienung verschwinden,
  nicht aus der Persistenz (BUG-DATALOSS-GR221 / #102).

## Existing Specs

- `docs/features/epic-1273-compare-one-surface.md` — eine Fläche statt Hub+Editor
- `docs/specs/modules/feat_1301_f2a_compare_new_trip_pattern.md` — Anlege-Seite nach Trip-Muster, § AC-7 Stundenverlauf-Extraktion
- `docs/specs/modules/feat_1256_s8c_hub_fidelity.md` — Layout-Tab-Optik (Quelle der Limit-Pillen)
- `docs/specs/modules/compare_hub_hourly_metrics.md` — Stundenverlauf im Hub
- `docs/specs/modules/compare_weather_metrics_tab.md` — Metrik-Tab im Vergleich

## Risks & Considerations

- **Bestandsdaten**: `top_n`, `channel_layouts`, `hour_from`/`hour_to`,
  `forecast_hours` liegen in gespeicherten Presets. Entfernen aus Bedienung und
  Auflösung ja — aus der Persistenz nein.
- **Parallele Arbeit**: #1359 hat einen eigenen laufenden Workflow
  (`fix-1359-orts-reihenfolge`, Scheibe 1 bereits live). Reihenfolge-Fragen des
  Orte-Tabs gehören dorthin, nicht hierher.
- **Regel-Budget**: ein neuer Kontrakt-Test (jedes sichtbare Bedienelement →
  gespeichertes Feld → Lesestelle im Renderer) braucht Prüfdatum +90 Tage.
- **Deploy-Umfang**: Frontend-Änderung plus kleiner Backend-Rückbau (`top_n`),
  also Voll-Deploy, kein Frontend-only.
