---
entity_id: i18n_f5_wertebereiche_tab_2654
type: module
created: 2026-10-30
updated: 2026-10-30
status: draft
version: "1.0"
tags: [i18n, epic-2644, issue-2654, frontend, model-haiku]
---

# i18n F5: Katalog-Migration Wertebereiche-Tab (WeatherMetricsTab, trip-metrics), Metrik-Namen nach Sprache aus dem Register

**Issue:** #2654 · **Epic:** #2644 · **Modell:** Haiku · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitt(e) 2, 3 (Frontend, `metricLabel`), 4 (Wettergrößen-Tabelle, Token-Wächter), 8

## Approval

- [ ] Approved

## Purpose

Der geteilte Wetter-Metriken-/Wertebereiche-Tab (Trip und Ortsvergleich, Parameter `context`) ist für englischsprachige Nutzer vollständig englisch. Metrik-Namen kommen nicht aus dem Frontend-Katalog, sondern aus dem Metrik-Register des Backends und wechseln nur in der vollen Form die Sprache; Kurzform (`col_label`) und Kürzel (`sms_code`) bleiben, damit die Dreier-Auflösung `Temperature · Temp · T` bestehen bleibt (ADR-0042). Deutsch bleibt wörtlich wie heute.

## Source

- **File:** `frontend/src/lib/components/shared/WeatherMetricsTab.svelte`, `frontend/src/lib/components/shared/weather-metrics-tab/**`, `frontend/src/lib/components/shared/trip-metrics/tripActiveMetricNames.ts`, `frontend/src/lib/components/shared/StandardwerteSpeichernKnopf.svelte`, `frontend/src/lib/i18n/metricLabel.ts` (neu), `frontend/src/lib/types.ts`
- **Identifier:** `metricLabel(def, lang)` (neu), `resolveTripMetricsOverviewState` (tripActiveMetricNames.ts), `MetricEntry`, `CompareMetricCatalogEntry` (types.ts), Katalog-Namensraum `wertebereiche.*`

> **Schicht-Hinweis:** Reines SvelteKit-Frontend. Der Metrik-Katalog kommt über `GET /api/metrics` aus dem Python-Core (Paket P1 #2662 liefert `label_en`, `alert_label_en`). Dieses Paket ändert **keinen** Python-/Go-Code und keine Tokens.

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `frontend/src/lib/i18n/metricLabel.ts` | CREATE | `metricLabel(def, lang)` und `metricAlertLabel(def, lang)`; eine Stelle für F5, F7, F8, F9, F10 |
| `frontend/src/lib/types.ts` | MODIFY | `label_en?`, `alert_label_en?` an `MetricEntry` und `CompareMetricCatalogEntry`; Typ `MetricLabelFields` |
| `frontend/src/lib/i18n/messages/de/wertebereiche.json` | MODIFY | deutsche Texte des Tabs (wörtlich) |
| `frontend/src/lib/i18n/messages/en/wertebereiche.json` | MODIFY | gleiche Schlüssel, englisch |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | MODIFY | Eyebrows, Hinweise, Schwellen-Zeilen (`label=`), Stufen, Dialoge, Lade-/Fehlertexte; Metrik-Namen über `metricLabel` |
| `frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2Reihenfolge.svelte` | MODIFY | Badges, Titel, „Aus in diesem Kanal", Hinweis zu Kürzeln |
| `frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2PresetBar.svelte` | MODIFY | Badge „Eigene" |
| `frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2Grundauswahl.svelte` | MODIFY | sichtbare Texte (falls vorhanden) |
| `frontend/src/lib/components/shared/weather-metrics-tab/DayWindowCard.svelte` | MODIFY | „Tagesfenster" und Untertitel |
| `frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte` | MODIFY | Titel, Platzhalter, Zusammenfassung, Schaltflächen |
| `frontend/src/lib/components/shared/weather-metrics-tab/{AggregationMetricRow,MultiSymbolMetricRow,ThresholdMetricRow}.svelte` | MODIFY | sichtbare Texte und `aria-label` |
| `frontend/src/lib/components/shared/weather-metrics-tab/{channelMetricLayouts,compareChannelMetricLayouts,compareMetricSelection,kuerzelMarken,kuerzelLegende,weatherMetricsTabSections}.ts` | MODIFY | nur Nutzertexte (Bezeichnungen, Hinweise) über `tr()`; Logik und IDs unverändert |
| `frontend/src/lib/components/shared/corridor-editor/compareMetricCatalogLoader.ts` | MODIFY | Anzeigename der Vergleichs-Metriken über `metricLabel` aus dem Register |
| `frontend/src/lib/components/shared/trip-metrics/tripActiveMetricNames.ts` | MODIFY | `names` über `metricLabel(entry, get(locale))` statt `entry.label` |
| `frontend/src/lib/components/shared/StandardwerteSpeichernKnopf.svelte` | MODIFY | nur sicherstellen, dass `standardwerte.knopf` auch in en existiert (Schlüssel bleibt) |
| `frontend/src/lib/i18n/hardcode_allowlist.json` | MODIFY | Einträge `shared/weather-metrics-tab`, `shared/trip-metrics`, `shared/WeatherMetricsTab.svelte`, `shared/StandardwerteSpeichernKnopf` entfernen |
| `frontend/src/lib/i18n/__tests__/metricLabel.test.ts` | CREATE | Auswahl und Fallback |
| `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/wertebereiche_sprache.test.ts` | CREATE | Tab de/en, zwei Nutzer, unveränderte Nutzlast |
| `tests/golden/f5_wertebereiche/*.de.html` | CREATE | Golden der deutschen Ausgabe |

> **Querschnitts-Prüfpunkte**
> - **Trip/Ortsvergleich-Teilung:** `WeatherMetricsTab.svelte` ist der geteilte Baustein (`context="route"|"vergleich"`). Es entsteht keine zweite Komponente; Texte, die nur im Nomen abweichen, nutzen zwei Schlüssel. Texte, die auch in F9/F10-Flächen vorkommen (Aktionen), bleiben einmal in diesem Bereich.
> - **Mandantentrennung:** Der Tab lädt und speichert die Einstellungen des angemeldeten Nutzers (`user_id` aus Auth-Kontext, unverändert). Anzeige-Texte dürfen **nie** in die gespeicherte Nutzlast gelangen. Test mit zwei Nutzern (AC-4).
> - **Kanäle:** Der Tab steuert, welche Metriken in E-Mail, Telegram, SMS und Premium-SMS erscheinen; Kanalnamen sind Eigennamen und bleiben.

## Estimated Scope

- **LoC:** ca. 260 Code-Zeilen (ohne Katalog und Tests): ca. 170 Textstellen in `WeatherMetricsTab.svelte` und `weather-metrics-tab/`, ca. 60 für `metricLabel` und Typen und Aufrufstellen, ca. 30 Hilfsdateien. Das liegt an der Grenze von 250: `workflow.py set-field loc_limit_override 500` einplanen.
- **Files:** 20 Code-/Katalogdateien plus 3 Tests plus Golden
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| #2662 (P1) | Paket | `GET /api/metrics` liefert `label_en`, `alert_label_en`; Fixture `metric_tokens_frozen.json` |
| #2647 (S2) | Paket | `t`, `tr`, `locale`, `Lang` |
| #2649 (S4) | Paket | Ratsche und Allowlist |
| #2655 (F6) / #2657 (F8) | Pakete (vorher) | F8 legt Schlüssel für den Korridor-Editor unter `layout.*` an; F5 verwendet sie weiter, wo gleichlautend |
| `tests/test_metric_tokens_eingefroren.py` | Test | bleibt unverändert grün; `col_label`, `compact_label`, `sms_code` werden nur durchgereicht |
| `docs/reference/i18n_glossar.md` | Doku | Wertebereiche = target ranges, Schwelle = threshold, Tagesfenster = day window, Kurzform = compact style |
| ADR-0104, ADR-0042 | adr | Klasse 2 „voll" wird sprachabhängig, Klasse 1 und `col_label` nie |

## Implementation Details

**1. `metricLabel`.** Neue Datei `frontend/src/lib/i18n/metricLabel.ts`:

```ts
export type MetricLabelFields = { label: string; label_de?: string; label_en?: string; alert_label?: string; alert_label_en?: string };
export function metricLabel(def: MetricLabelFields, lang: Lang): string   // en: label_en wenn nicht leer, sonst label_de ?? label; de: label_de ?? label
export function metricAlertLabel(def: MetricLabelFields, lang: Lang): string // en: alert_label_en, sonst alert_label; leer wenn beides fehlt
```

Das Feld der Backend-Antwort heißt heute `label` (= `label_de` des Registers, `api/routers/config.py`); `label_de` wird zusätzlich akzeptiert, falls P1 es mitliefert. Nie ein leerer Text: fehlt `label_en` (Altdaten), steht der deutsche Name. `col_label` und `sms_code` werden **nie** durch diese Funktion geführt.

**2. Beispiel-Schlüssel (de / en).**

| Schlüssel | de | en |
|---|---|---|
| `wertebereiche.tab.laedt` | Lade Metriken… | Loading metrics… |
| `wertebereiche.tab.wiederholen` | Wiederholen | Retry |
| `wertebereiche.tab.ungespeichert` | Ungespeicherte Änderungen | Unsaved changes |
| `wertebereiche.tab.verwerfen` | Verwerfen | Discard |
| `wertebereiche.schwelle.titel` | 04 — Schwellwerte | 04 — Thresholds |
| `wertebereiche.schwelle.boeen` | Böen (km/h) | Gusts (km/h) |
| `wertebereiche.schwelle.niederschlag` | Niederschlag (mm) | Precipitation (mm) |
| `wertebereiche.schwelle.stufe.sensibel` | Sensibel | Sensitive |
| `wertebereiche.tagesfenster.titel` | Tagesfenster | Day window |
| `wertebereiche.preset.anwenden` | Preset anwenden | Apply preset |
| `wertebereiche.preset.ueberschreiben` | Überschreiben | Overwrite |
| `wertebereiche.reihenfolge.aus_im_kanal` | Aus in diesem Kanal | Off in this channel |
| `wertebereiche.auswertung.max` | Maximum | Maximum |
| `wertebereiche.auswertung.avg` | Mittel | Average |
| `standardwerte.knopf` (besteht) | Mit Standardwerten speichern | Save with defaults |

Auswertungen (`min` Minimum/Minimum, `max` Maximum/Maximum, `avg` Mittel/Average, `sum` Summe/Total) werden über die Auswertungs-Kennung (`aggregation` bzw. `aggregations[].id`) auf `wertebereiche.auswertung.<id>` abgebildet, weil die Backend-Antwort `aggregation_label` nur deutsch liefert (Annahme A1).

**3. Beispiel-Umstellung vorher → nachher.**

- `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:1797` — vorher `<Eyebrow style="margin-bottom:8px">04 — Schwellwerte</Eyebrow>`, nachher `<Eyebrow style="margin-bottom:8px">{$t('wertebereiche.schwelle.titel')}</Eyebrow>`.
- `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:1822` — vorher `label="Böen (km/h)"`, nachher `label={$t('wertebereiche.schwelle.boeen')}`; die Stufen `{ id: 'sensibel', label: 'Sensibel', float: 30 }` bekommen `label: $t('wertebereiche.schwelle.stufe.sensibel')` (`id` und `float` unverändert).
- `frontend/src/lib/components/shared/trip-metrics/tripActiveMetricNames.ts:60` — vorher `.map((entry) => entry.label)`, nachher `.map((entry) => metricLabel(entry, get(locale)))`.
- `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:1182` (Vergleichs-Katalog) — vorher `label: e.label`, nachher `label: metricLabel(metricById[e.metric_id ?? ''] ?? e, $locale)`; ein Register-Eintrag mit `label_en` hat Vorrang, die Auswertung steht weiter als eigenes Element daneben.

**4. Was unverändert bleibt.** `id`-Werte, `float`-Schwellen, `data-testid`, `col_label`, `sms_code`, `compact_label`, Kürzel in `kuerzelMarken.ts` (nur umgebende Texte werden übersetzt), Reihenfolgen und die Struktur der gespeicherten Nutzlast. Die Ratsche `tripActiveMetricNames_noHardcodedVocabulary_structure` bleibt grün: es entsteht keine lokale Tabelle Metrik-ID → Name.

**5. Allowlist.** Aus `frontend/src/lib/i18n/hardcode_allowlist.json` die Einträge entfernen, die auf Dateien dieser Tabelle zeigen (laut Issue `shared/weather-metrics-tab`, `shared/trip-metrics`; die Datei `shared/WeatherMetricsTab.svelte` liegt eine Ebene höher und wird mit entfernt, falls sie dort einzeln steht).

**6. Golden-Fixture.** Mit `weather-metrics-tab/__tests__/fixtures/metric_catalog_selectable.json` und fester Zeit `2026-10-29T06:00+02:00` den Tab in beiden Kontexten (`route`, `vergleich`) für Nutzer `golden-de` per SSR nach `tests/golden/f5_wertebereiche/<fall>.de.html` schreiben, vor der Umstellung; danach byte-gleich vergleichen. `*.en.html` zur Review einchecken.

## Expected Behavior

- **Input:** Tab Wetter-Metriken/Wertebereiche in Trip- und Ortsvergleich-Hub und beim Anlegen, Nutzer mit `language=en` oder `de`, Katalogantwort mit oder ohne `label_en`.
- **Output:** Alle Beschriftungen in der Nutzersprache; Metrik-Name in voller Form in der Nutzersprache, Kurzform und Kürzel unverändert; fehlendes `label_en` → deutscher Name.
- **Side effects:** Keine. Die gespeicherte Nutzlast (Metrik-IDs, Buckets, Schwellen, Kanal-Layouts) ist in beiden Sprachen identisch.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer mit Sprache Englisch und ein Katalog mit `label` „Temperatur", `label_en` „Temperature", `col_label` „Temp", `sms_code` „T" / When der Tab lädt / Then erscheint die Metrik als „Temperature", daneben unverändert „Temp" und „T" (Dreier-Auflösung), und alle Beschriftungen des Tabs sind englisch.
  - Test: `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/wertebereiche_sprache.test.ts` — Render mit `locale.set('en')`, Prüfung über `metricLabel` und `tr()`-Werte; `col_label`/`sms_code` byte-gleich zur Eingabe.

- **AC-2:** Given ein Metrik-Eintrag ohne `label_en` (Altdaten) oder mit leerem `label_en` / When der Tab in Englisch angezeigt wird / Then steht der deutsche Name, nie ein leerer Text.
  - Test: `frontend/src/lib/i18n/__tests__/metricLabel.test.ts` — Fallback für fehlendes und leeres `label_en`, in beiden Sprachen.

- **AC-3:** Given Nutzer A mit Englisch und Nutzer B mit Deutsch, beide mit derselben Metrik-Auswahl / When beide den Tab öffnen, eine Metrik umschalten und speichern / Then ist die gespeicherte Nutzlast bei beiden identisch (keine Anzeige-Texte darin), und jeder sieht nur seine Auswahl in seiner Sprache.
  - Test: `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/wertebereiche_sprache.test.ts` — zwei Nutzer in einem Lauf, Vergleich der PUT-Nutzlast (Speichern-Pfad, wie `weatherConfigMetricsPayloadShape.test.ts`).

- **AC-4:** Given Trip- und Ortsvergleich-Hub in Englisch / When der Tab mit `context="route"` und mit `context="vergleich"` gerendert wird / Then sind beide mit demselben Baustein englisch, und nur die kontextbedingten Nomen unterscheiden sich („trip" / „comparison").
  - Test: `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/wertebereiche_sprache.test.ts` — beide Kontexte, ein Baustein, Textvergleich über `tr()`.

- **AC-5:** Given die deutsche Oberfläche / When der Tab mit dem Katalog `metric_catalog_selectable.json` für Nutzer `golden-de` gerendert wird / Then ist die Ausgabe Byte für Byte gleich zu `tests/golden/f5_wertebereiche/*.de.html`.
  - Test: `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/wertebereiche_sprache.test.ts` — Golden-Vergleich (deutsche Ausgabe unverändert).

- **AC-6:** Given das Metrik-Register / When die Wächter laufen / Then bleiben `col_label`, `compact_label` und `sms_code` aller Metriken byte-identisch zur eingefrorenen Fixture, und `tripActiveMetricNames_noHardcodedVocabulary_structure` ist weiterhin grün.
  - Test: `tests/test_metric_tokens_eingefroren.py` und `frontend/src/lib/components/shared/trip-metrics/__tests__/tripActiveMetricNames_noHardcodedVocabulary_structure.test.ts` — beide unverändert grün (Token-Wächter, Ratsche, `# doc-compliance-test`).

- **AC-7:** Given die Allowlist der Ratsche / When `keine_hartkodierten_nutzertexte.test.ts` und der Paritätstest laufen / Then gibt es keine Treffer mehr in den Dateien dieses Pakets, die Allowlist enthält keinen Eintrag mehr für `shared/weather-metrics-tab` und `shared/trip-metrics`, und `wertebereiche` hat in de und en identische Schlüssel- und Platzhaltermengen.
  - Test: `frontend/src/lib/i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts` und `paritaet_de_en.test.ts` — Ratschen-/Paritätstest (`# doc-compliance-test`).

## Known Limitations

- **A1 (Annahme):** `GET /api/metrics` und `GET /api/compare/metrics` liefern `aggregation_label` nur deutsch (P1 ergänzt es nicht). Die englischen Auswertungs-Namen kommen deshalb aus dem Frontend-Katalog über die Auswertungs-Kennung. Liefert P1 später `aggregation_label_en`, wird der Katalogschlüssel durch das Feld ersetzt.
- **A2 (Annahme):** `/api/compare/metrics` bekommt in P1 kein `label_en`; für den Vergleichs-Katalog wird der Name aus dem Register `/api/metrics` (`metricById`) bezogen, das der Tab im Vergleich ohnehin lädt (#1401). Fehlt der Eintrag, bleibt der deutsche Name.
- Die Metrik-Namen in den Trip-Hub-Bausteinen (`trip-detail/ActiveMetricRow`, `BucketSection`, `MetricGroup`, `HubOverview`) stellt F9 mit derselben Funktion `metricLabel` um.
- Wortgleiche Basis-Aktionen (Wiederholen, Verwerfen, Abbrechen) liegen bis zum Epic-Ende je Bereich einmal; die Zusammenführung nach `aktionen.*` ist ein Nebenbefund nach F10, kein Teil dieses Pakets.
- Die Schwellen-Zeilen tragen Einheiten im Text („Böen (km/h)"); die Einheiten sind in beiden Sprachen gleich und stehen mit im Katalogtext.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104 (zusätzlich ADR-0042)
- **Rationale:** Die volle Namensform wird sprachabhängig, Kurzform und Kürzel nie; Metrik-Namen haben eine einzige Quelle, das Register.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
