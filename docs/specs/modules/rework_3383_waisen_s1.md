---
entity_id: rework_3383_waisen_s1
type: refactor
created: 2026-11-26
updated: 2026-11-26
status: draft
workflow: rework-3383-waisen-s1
version: "1.1"
tags: [frontend, waisen, ratsche, loeschen, "#3383", "#3366", "#3122"]
---

# Rework #3383: Waisen-Scheibe S1 (weather-metrics-tab, trip-detail, reportConfigDirty, GrundauswahlLeerHinweis) und Selbstnachweis des Wächters

## Approval

- [ ] Approved

## Purpose

Scheibe S1 der Waisen-Löschung (Nachfolger von #3366 S2): 14 Frontend-Dateien ohne Produktionsaufrufer, die heute als Gruppe S1 in `BEKANNTE_WAISEN` des Waisen-Wächters stehen, werden gelöscht, samt der Tests, Prüfstand-Teile, Ratschenzahlen und Katalogschlüssel, die nur sie betreffen. Zusätzlich wird der Selbstnachweis des Wächters (Finding F001 aus #3366) um die bisher unbewiesenen Kantenarten erweitert, damit die Erreichbarkeitsrechnung dauerhaft abgesichert ist. Für Nutzer ändert sich nichts Sichtbares.

## Source

- **File:** `frontend/src/lib/__tests__/waisen_waechter.test.ts` (Pflege und Erweiterung), `frontend/src/lib/components/shared/weather-metrics-tab/`, `frontend/src/lib/components/trip-detail/`, `frontend/src/lib/components/shared/reportConfigDirty.ts`, `frontend/src/lib/components/molecules/GrundauswahlLeerHinweis.svelte` (Löschung)
- **Identifier:** Test `Waisen-Wächter` (Liste `BEKANNTE_WAISEN`, Konstante `OBERGRENZE_WAISEN`, Funktionen `findeWaisen`, `pruefeRatsche`, `miniBaum`)

Schicht: ausschließlich Frontend (`frontend/src/...`) plus Testdaten, Goldens und Ratschenzahlen. Kein Go-, kein Python-Produktionscode, keine Hook-Änderung (`.claude/hooks` bleibt unberührt). Trip/Vergleich-Teilung: es entsteht kein neuer Baustein; Mandantentrennung: keine Nutzerdaten betroffen; Kanäle: kein Briefing- oder Alarm-Inhalt betroffen.

## Zu löschende Dateien (14, genau die Gruppe S1 in `BEKANNTE_WAISEN`)

Alle Pfade unter `frontend/src/lib/`.

1. `components/molecules/GrundauswahlLeerHinweis.svelte`
2. `components/shared/reportConfigDirty.ts`
3. `components/shared/weather-metrics-tab/AggregationMetricRow.svelte`
4. `components/shared/weather-metrics-tab/MultiSymbolMetricRow.svelte`
5. `components/shared/weather-metrics-tab/ThresholdMetricRow.svelte`
6. `components/shared/weather-metrics-tab/WeatherV2Grundauswahl.svelte`
7. `components/shared/weather-metrics-tab/WeatherV2PresetBar.svelte`
8. `components/shared/weather-metrics-tab/compareAggregationGrouping.ts`
9. `components/shared/weather-metrics-tab/nurEinBericht.ts`
10. `components/shared/weather-metrics-tab/outlookFriendlyCapability.ts`
11. `components/shared/weather-metrics-tab/wertebereicheAnzeige.ts`
12. `components/trip-detail/AboutOutputLayout.svelte`
13. `components/trip-detail/WeatherV2Kanaele.svelte`
14. `components/trip-detail/weatherSaveGate.ts`

Hinweis zur Zahl: Die Analyse (`docs/context/rework-3366-waisen-loeschen.md`) nennt "15 Dateien"; die Gruppe S1 in `BEKANNTE_WAISEN` enthält 14 Einträge (9 weather-metrics-tab, 3 trip-detail, `reportConfigDirty.ts`, `GrundauswahlLeerHinweis.svelte`). Maßgeblich ist die Wächterliste, weil sie gegen den echten Importgraphen geprüft wird. `trip-detail/waypoints/WaypointPin.svelte` gehört zu S4 (#3384) und bleibt. `weatherMetricsCompareSave.ts` und `metricsEditor.ts` leben und bleiben.

## Estimated Scope

- **LoC:** Löschung ca. -1 330 Produktionszeilen (laut Analyse 1 329) plus mitgehende Tests, Goldens und Schlüssel (nach dem Löschen messen, nicht schätzen); neu ca. +80 (Selbstnachweis des Wächters, kleine Logikergänzung für die Array-Form)
- **Files:** 14 Produktionsdateien gelöscht, dazu die mitgezogenen Testdateien und Schlüssel (genaue Zahl wird nach dem Löschen gemessen)
- **Effort:** medium

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| 14 Dateien der Liste oben | DELETE | Waisen ohne Aufrufer |
| `frontend/src/lib/__tests__/waisen_waechter.test.ts` | MODIFY | S1-Einträge aus `BEKANNTE_WAISEN` streichen; `OBERGRENZE_WAISEN` 40 auf 26; Selbstnachweis um vier dauerhafte Fälle plus einen fünften Block für die Array-Form von `import.meta.glob` (muss rot sein) erweitern (F001); die exakte Mini-Baum-Zusicherung (heute Z. 250-253) wird beim Ergänzen der Mini-Baum-Dateien mitgeführt; der Test "outlookFriendlyCapability.ts ist bis S1 (#3383) bekannte Waise" (heute Z. 220-224) wird ENTFERNT (nicht umgewidmet), seine Stelle übernimmt der Eintrag in `GELOESCHT` des Lösch-Nachweises; Wächterlogik für die fail-closed-Meldung bei der Array-Form ergänzen |
| `frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts` | MODIFY | `outlookFriendlyCapability.ts` von `ERHALTEN` nach `GELOESCHT` (Eintrag in `ERHALTEN` entfällt); neuer Block `#3383` mit allen 14 Pfaden |
| `shared/__tests__/reportConfigDirty.test.ts`, `trip-detail/__tests__/weatherSaveGate.test.ts`, `weather-metrics-tab/__tests__/{compareAggregationGrouping,outlookFriendlyCapabilityDrift,thunderThresholdLevels,vorlage_speichern_karte_3190,aggregation_row_multi_select}.test.ts`, `components/__tests__/f13_ausdruck_offen_sprache.test.ts` | DELETE | Tests, die nur die gelöschten Dateien prüfen (je Datei nach dem Löschen per benanntem Testlauf bestätigt; Mischfälle werden umgebaut) |
| `frontend/src/lib/stores/__tests__/saveStatus.test.ts` | MODIFY | Fälle mit `weatherSaveGate` und `reportConfigChangedByUser` raus, übrige Fälle leben |
| `frontend/src/lib/components/shared/wetter-tab/__tests__/{vorlageName_render,fix2955_metrik_inhalte}.test.ts` | MODIFY | Fall "WeatherV2PresetBar: Chip-Text" raus; Schlüssel `wertebereiche.symbolzeile.*_night` nachziehen |
| `weather-metrics-tab/__tests__/f5KatalogAnker.ts` | MODIFY/DELETE | Anker der 22 Schlüssel `wertebereiche.*`; je nach Rest ganz oder teilweise entfernen (Messung) |
| `components/trip-detail/__tests__/f9Pruefstand.ts`, `f9KatalogAnker.ts` | MODIFY | Nur die Fälle von `WeatherV2Kanaele` entfernen (Waisen-Teil); `WaypointPin`, `WeatherSummaryCard`, `EditRouteSectionOffen` bleiben für S4; mehr als zehn lebende Tests importieren den Prüfstand |
| `tests/golden/f9_trip_flaechen/*` | MODIFY | Nur die betroffenen Goldens (`layout_bausteine.*`, `funktionen.*` soweit `WeatherV2Kanaele` betroffen) mit dem Projektwerkzeug neu erzeugen, DE und EN vorher/nachher gegenlesen; Goldens der S4-Fälle (`wegpunkte`, `edit_felder`) unverändert |
| `frontend/src/lib/__tests__/{bausteine_waechter_regeln.ts,ink4_waechter.test.ts}` | MODIFY | BESTAND-Einträge und `BESTAND_OBERGRENZE` sowie ink4-Einträge: Einträge der S1-Dateien, nach dem Löschen gemessen, im selben Commit senken; `GrundauswahlLeerHinweis` steht nicht in BESTAND, es darf kein verwaister Eintrag bleiben |
| `tests/unit/ein_katalog_ausnahmen.json`, `tests/unit/test_ein_katalog_eine_verarbeitung_ratsche.py` | MODIFY | Einträge `WeatherV2Grundauswahl`, `outlookFriendlyCapability`, `wertebereicheAnzeige` entfernen; `hoechststand` (JSON) und `HOECHSTSTAND` (Python) nach Messung an beiden Stellen im selben Commit senken (Einträge von `alertMetricCatalogIds`/`weatherEmoji` gehören zu S4 und bleiben) |
| `frontend/src/lib/i18n/__tests__/{keine_hartkodierten_nutzertexte,reaktivitaet_waechter,deutsch_unveraendert}.test.ts` | MODIFY | Dateilisten kürzen, Zählungen neu messen, Anker der entfernten Schlüssel nachziehen |
| `frontend/src/lib/i18n/messages/{de,en}/{trip,wertebereiche}.json` | MODIFY | Schlüssel ohne Verwender entfernen (laut Analyse `wertebereiche.*` 22, `trip.about/kanaele/wetter` 38; Liste durch `katalog_schluessel_haben_verwender.test.ts` gemessen, de und en gleiche Menge) |
| `frontend/e2e/feat3205_elementliste_vorlagen_je_art.test.ts` | MODIFY | Schlüssel `wertebereiche.preset.eigene` nachziehen |
| `tests/fixtures/einstellung_gleich_mail/fallliste_editor.json` | MODIFY | Hinweistext um Zeile 722 ("Waise, #3366") nach dem Löschen anpassen; Status bleibt ehrlich |
| `frontend/e2e/{epic-138-metriken-editor,weather-metrics-editor-day-range-kuerzel,trip-new-loads-without-effect-loop}.spec.ts` | KEEP (nur bedingt MODIFY) | Gehören zu #3374; hier nur angefasst, wenn sie eine gelöschte Datei importieren und dadurch Build oder CI brechen; keine Spec auf der CI-Positivliste betroffen |

Nicht angefasst: `components/molecules/EinstellTabelle.svelte` und ihr Test, `.claude/hooks`, jeder Produktionscode außerhalb der Löschmenge, die Scheiben S3 (#3385) und S4 (#3384), #3374 (Browser-Specs und Staging-Browserprüfungen, darunter `tests/tdd/test_issue_692_telegram_disabled_unconfigured.py`).

### Estimated Changes

- Files: 14 Produktionsdateien gelöscht, Rest Löschung/Pflege (nach Messung)
- LoC: +80 / -(ca. 1 330 Produktion + mitgehende Tests)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/rework-3383-waisen-s1.md`, `docs/context/rework-3366-waisen-loeschen.md` | doc | Analyse (Abschnitt S1): Dateiliste, Tests, f9, Ratschen, Schlüssel |
| `docs/specs/modules/rework_3366_waisen_waechter_layout_tab.md` | spec | Vorbild und Wächterdefinition (geliefert mit PR #3386) |
| `frontend/src/lib/__tests__/waisen_waechter.test.ts` | test | Wächter, Ratsche, Selbstnachweis |
| `frontend/src/lib/i18n/__tests__/katalog_schluessel_haben_verwender.test.ts` | test | Fundmechanismus für Katalogschlüssel ohne Verwender |
| `frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts` | test | Liste `GELOESCHT`/`ERHALTEN` |
| `frontend/src/lib/__tests__/bausteine_waechter_regeln.ts` | test | Literal-Obergrenze `BESTAND_OBERGRENZE` |
| `frontend/src/lib/components/trip-detail/__tests__/trip_hub_sprache.test.ts` | test | Golden-Vergleich der f9-Goldens (DE und EN) |
| Golden-Werkzeug des Projekts (f9-Goldens) | tooling | Goldens neu erzeugen, nie von Hand schreiben |
| `node --test`, `svelte-check`, Vite-Build | tooling | Nachweis keine sichtbare Änderung |

## Implementation Details

**Löschung S1.** Zuerst RED: Wächter-Liste um die 14 Einträge kürzen und `OBERGRENZE_WAISEN` auf 26 setzen, der Wächter meldet die 14 Dateien als neue Waisen. Dann die 14 Dateien löschen, danach die betroffenen Testdateien benannt laufen lassen (nie `uv run pytest` ohne Dateinamen); jede neu rote Datei ist ein Umbaufall, jede Datei, die nur Gelöschtes prüft, wird gelöscht. Zahlen (`BESTAND_OBERGRENZE`, `HOECHSTSTAND`/`hoechststand`, ink4, Zählung in `reaktivitaet_waechter`, Katalogschlüssel) werden nach dem Löschen gemessen und im selben Commit eingetragen.

**Prüfstände.** `f9Pruefstand.ts` und `f9KatalogAnker.ts` werden nur in ihrem `WeatherV2Kanaele`-Teil angefasst; `f5KatalogAnker.ts` gehört vollständig zu den gelöschten Wertebereichs-Komponenten und wird nach Messung entfernt oder gekürzt. Goldens werden ausschließlich mit dem Projektwerkzeug neu erzeugt und DE/EN vor und nach der Erzeugung gegengelesen; Goldens ohne Waisen-Bezug bleiben byte-gleich.

**Wächter.** Streichen der 14 Einträge der Gruppe S1 in `BEKANNTE_WAISEN`; `OBERGRENZE_WAISEN` sinkt um genau diese Zahl von 40 auf 26 (Rechnung: 19 S4 + 7 S3 = 26). Der heutige Test "outlookFriendlyCapability.ts ist bis S1 (#3383) bekannte Waise" (Z. 220-224) wird entfernt, weil die Datei nicht mehr existiert. An seine Stelle tritt der Eintrag von `outlookFriendlyCapability.ts` in `GELOESCHT` des Lösch-Nachweises (`trip_pfad_altfeld_loeschnachweis_3297.test.ts`); der Eintrag in `ERHALTEN` entfällt.

**Lösch-Nachweis.** `outlookFriendlyCapability.ts` wechselt in `trip_pfad_altfeld_loeschnachweis_3297.test.ts` von `ERHALTEN` nach `GELOESCHT`; alle 14 S1-Dateien stehen in einem eigenen Block `#3383` (`existsSync === false` und Regex-Scan auf Importe der Basisnamen im Produktionscode).

**F001: Selbstnachweis des Wächters.** Zuerst wird geklärt, ob die Wächterlogik die Fälle schon kann: Die Kantenerkennung (`KANTE`) enthält dynamischen Import, `import.meta.glob` (nur String-Argument, per `globRegex`) und `new URL('…', import.meta.url)`; `findeWaisen` schließt Tests als Wurzel und Aufrufer aus. Der Mini-Baum beweist bisher nur den dynamischen Import (in `+page.svelte`). Ergänzt wird dauerhaft im Mini-Baum, jeder Fall als eigener Testblock (vier Fälle plus fünfter Block für die Array-Form); die exakte Zusicherung auf die Mini-Baum-Waisenliste (`waisen_waechter.test.ts` Z. 250-253) wird beim Ergänzen der Mini-Baum-Dateien mitgeführt:
- dynamischer Import macht erreichbar (eigener Fall mit eigener Datei, unabhängig von `export * from`),
- `import.meta.glob('./x/*.ts')` macht die passenden Dateien erreichbar,
- `new URL('./x', import.meta.url)` gilt als Verweis,
- eine Datei, die nur von einer Testdatei unter `routes/` (z. B. `routes/foo/__tests__/x.test.ts` oder `routes/foo/x.test.ts`) importiert wird, gilt als Waise,
- fünfter Block: die Array-Form `import.meta.glob([...])` wird im echten Baum nicht verwendet (gemessen 26.11.) und ist nicht unterstützt: Trifft der Wächter auf sie, wird er laut rot mit dem Hinweis „Array-Form von import.meta.glob nicht unterstützt — Wächterlogik ergänzen“ (Entscheidung Tech Lead; fail-closed statt stiller Lücke).
Ergibt ein Fall rot, wird die Wächterlogik ergänzt, nicht der Test abgeschwächt.

## Expected Behavior

- **Input:** Quelltext von `frontend/src`.
- **Output:** Wächter grün, solange die Waisenmenge (ohne `AUSNAHMEN`) exakt `BEKANNTE_WAISEN` (26 Einträge) entspricht und `OBERGRENZE_WAISEN` (26) nicht überschritten wird; Löschung ohne Funktionsänderung.
- **Side effects:** Keine sichtbare Änderung für Nutzer; Ratschenzahlen und Katalog schrumpfen.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Wächter rot vor der Löschung: `waisen_waechter.test.ts` mit gekürzter Liste und `OBERGRENZE_WAISEN = 26` meldet die 14 S1-Dateien als neue, nicht gelistete Waisen (RED), nach der Löschung grün.
- [ ] Lösch-Nachweis rot vor der Löschung: `existsSync` der 14 Pfade ist noch `true`; nach der Löschung `false`, kein Importtreffer im Produktionscode.
- [ ] Selbstnachweis F001: je ein eigener Testblock für dynamischen Import, `import.meta.glob`, `new URL(…, import.meta.url)` und "nur von Test unter routes/ importiert", dazu ein fünfter Block für die Array-Form von `import.meta.glob`, die rot sein muss; alle fünf Blöcke werden einzeln durch Verfälschung der Wächterlogik als rot nachgewiesen (Mutations-Gegenproben).
- [ ] Betroffene Testdateien benannt laufen lassen: `waisen_waechter`, `trip_pfad_altfeld_loeschnachweis_3297`, `saveStatus`, `vorlageName_render`, `fix2955_metrik_inhalte`, `katalog_schluessel_haben_verwender`, `paritaet_de_en`, `deutsch_unveraendert`, `bausteine_waechter`, `ink4_waechter`, `reaktivitaet_waechter`, `keine_hartkodierten_nutzertexte`, `trip_hub_sprache` und die weiteren `f9Pruefstand`-Nutzer.
- [ ] Python (benannt): `tests/unit/test_ein_katalog_eine_verarbeitung_ratsche.py`, `tests/unit/test_2243_playwright_loeschscheibe.py` und der Verweiswächter für `tests/fixtures/einstellung_gleich_mail/` grün.
- [ ] Gesamt: Frontend-Suite (`node --test`), Vite-Build und `svelte-check` grün; die svelte-check-Baseline (Fehler/Warnungen) wird vor dem Löschen gemessen (Lauf auf dem Branch-Stand) und darf nachher nicht steigen; beide Zahlen stehen im Test-Artefakt.

## Acceptance Criteria

- **AC-1:** Given die 14 Dateien der Gruppe S1 (`weather-metrics-tab/*` neun, `trip-detail/{AboutOutputLayout,WeatherV2Kanaele,weatherSaveGate}`, `reportConfigDirty.ts`, `GrundauswahlLeerHinweis.svelte`) / When das Dateisystem nach S1 geprüft wird / Then existiert keine der 14 Dateien mehr, `weatherMetricsCompareSave.ts`, `metricsEditor.ts` und `WaypointPin.svelte` bestehen weiter, und kein Produktionscode importiert die gelöschten Basisnamen.
  - Test: `trip_pfad_altfeld_loeschnachweis_3297.test.ts` (`GELOESCHT` per `existsSync === false` plus Importscan, Block `#3383`; `ERHALTEN` als Regressionsschutz). Architektur-Wächter über den echten Importgraphen, kein Dateiinhalt-Check als Verhaltensnachweis; Nutzerverhalten belegt AC-7.

- **AC-2:** Given `outlookFriendlyCapability.ts` stand bisher in `ERHALTEN` des Lösch-Nachweises und als bekannte Waise im Wächter / When S1 umgesetzt ist / Then steht sie in `GELOESCHT` (nicht mehr in `ERHALTEN`), und der Test "outlookFriendlyCapability.ts ist bis S1 (#3383) bekannte Waise" in `waisen_waechter.test.ts` ist entfernt (an seine Stelle tritt der `GELOESCHT`-Eintrag), sodass kein Test eine nicht mehr vorhandene Datei erwartet.
  - Test: Lösch-Nachweis (`trip_pfad_altfeld_loeschnachweis_3297.test.ts`) grün mit der Datei in `GELOESCHT`; `waisen_waechter.test.ts` grün ohne den alten Sondertest.

- **AC-3:** Given der Waisen-Wächter mit den S1-Einträgen gestrichen / When er die Erreichbarkeit ab `routes/` und `src/*.ts` berechnet / Then ist die Waisenmenge (ohne `AUSNAHMEN`) genau `BEKANNTE_WAISEN` mit 26 Einträgen (19 S4, 7 S3), `OBERGRENZE_WAISEN` ist die feste Literal-Konstante 26 (um genau 14 gesenkt), und der Test ist grün; ohne Streichen der S1-Einträge oder ohne Löschung wäre er rot.
  - Test: `waisen_waechter.test.ts` gegen den echten Baum, im RED-Stand vor der Löschung rot mit den 14 Pfaden. Architektur-Wächter über den echten Importgraphen, kein Dateiinhalt-Check als Verhaltensnachweis; Nutzerverhalten belegt AC-7.

- **AC-4:** Given der Selbstnachweis des Wächters an einem erfundenen Mini-Baum / When er die Fälle (a) dynamischer Import, (b) `import.meta.glob`, (c) `new URL('./x', import.meta.url)` und (d) Datei, die nur von einer Testdatei unter `routes/` importiert wird, sowie (e) die Array-Form von `import.meta.glob` durchrechnet / Then gelten (a), (b) und (c) als erreichbar, (d) als Waise, und (e) führt zu einer roten Meldung „nicht unterstützt“ statt still durchzulaufen; jeder der fünf Fälle hat einen eigenen Testblock.
  - Test: fünf neue Testblöcke in `waisen_waechter.test.ts` am temporären Mini-Baum (inklusive Mitführen der exakten Mini-Baum-Liste); Mutations-Gegenprobe je Block (Kantenart aus `KANTE` entfernen, Test als Wurzel zulassen, fail-closed-Meldung entfernen) macht den passenden Block rot.

- **AC-5:** Given die Löschung der Wetter-Metriken- und Trip-Detail-Waisen / When die Tests, die nur diese Dateien prüfen, und die gemischten Prüfstände (`f5`, `f9`) bearbeitet sind / Then sind reine Waisentests gelöscht, Tests mit lebendem Anteil (`saveStatus`, `vorlageName_render`, `fix2955_metrik_inhalte`, `deutsch_unveraendert`, Nutzer von `f9Pruefstand`) nur um die Waisen-Fälle gekürzt und grün, und die f9-Goldens sind ausschließlich mit dem Projektwerkzeug neu erzeugt, wobei Goldens ohne Bezug zu `WeatherV2Kanaele` unverändert bleiben.
  - Test: Goldens werden mit dem Projektwerkzeug neu erzeugt; danach ist der Golden-Vergleichstest `frontend/src/lib/components/trip-detail/__tests__/trip_hub_sprache.test.ts` grün (er liest die f9-Goldens, DE und EN); zusätzlich die benannten Testdateien aus dem Test Plan grün.

- **AC-6:** Given die Löschung / When die Zahlenratschen (`BESTAND_OBERGRENZE`, ink4, `hoechststand`/`HOECHSTSTAND` ein_katalog, Zählung in `reaktivitaet_waechter`, Katalogschlüssel de/en) geprüft werden / Then stimmen alle Zahlen mit der Messung nach dem Löschen überein und sind nur gesunken, `hoechststand` (JSON) und `HOECHSTSTAND` (Python) sind identisch gesenkt, die entfernten Einträge in `ein_katalog_ausnahmen.json` gehören nur zu den S1-Dateien, de und en führen dieselbe Schlüsselmenge, und kein Schlüssel ohne Verwender bleibt im Katalog.
  - Test: `bausteine_waechter`, `ink4_waechter`, `reaktivitaet_waechter`, `katalog_schluessel_haben_verwender`, `paritaet_de_en`, `deutsch_unveraendert` und `tests/unit/test_ein_katalog_eine_verarbeitung_ratsche.py` grün.

- **AC-7:** Given die Seiten und Ansichten (insbesondere Trip-Editor, Vergleichs-Editor, Wetter-Metriken-Reiter, Trip-Detail) / When die gesamte Frontend-Suite, der Produktions-Build und `svelte-check` laufen / Then sind alle grün, die svelte-check-Zahlen (Fehler/Warnungen) wurden vor dem Löschen auf dem Branch-Stand gemessen und steigen nachher nicht, und für Nutzer gibt es keine sichtbare Änderung.
  - Test: Frontend-Suite per `node --test`, `npm run build`, `svelte-check` (beide Zahlen vorher/nachher im Test-Artefakt); Python-Verweiswächter für `tests/fixtures/einstellung_gleich_mail/` und `test_2243_playwright_loeschscheibe.py` grün.

- **AC-8:** Given die Scheiben S3 (#3385), S4 (#3384) und die Browser-Specs (#3374) sowie `EinstellTabelle.svelte` und `.claude/hooks` / When S1 geliefert ist / Then sind deren Dateien unverändert, die 26 verbleibenden Wächter-Einträge entsprechen genau den Scheiben S3 und S4, und keine Datei der Löschliste existiert mehr, ohne dass ein Import darauf zurückbleibt.
  - Test: Wächter grün mit genau den 26 Einträgen; der Lösch-Nachweis-Test (`trip_pfad_altfeld_loeschnachweis_3297.test.ts`) prüft, dass keine Datei der Löschliste existiert und kein Produktionscode darauf importiert.

## Definition of Done

- [ ] Spec freigegeben (`approved`/`freigabe`)
- [ ] RED-Nachweis: Wächter und Lösch-Nachweis rot vor der Löschung, grün danach
- [ ] 14 S1-Dateien gelöscht, mitgezogene Tests, Prüfstand-Teile, Goldens, Schlüssel, Ratschen im selben Commit gepflegt
- [ ] `outlookFriendlyCapability.ts` von `ERHALTEN` nach `GELOESCHT`, Block `#3383` angelegt, Sondertest im Wächter entfernt
- [ ] `OBERGRENZE_WAISEN` auf 26, `BEKANNTE_WAISEN` ohne Gruppe S1
- [ ] Selbstnachweis des Wächters um die vier F001-Fälle und den fünften Block (Array-Form, rot) erweitert, Mutations-Gegenprobe je Block
- [ ] Zahlen nach dem Löschen gemessen und eingetragen
- [ ] Frontend-Suite, Build, `svelte-check` und die benannten Python-Ratschentests grün (svelte-check vorher gemessen, nachher nicht höher)
- [ ] Adversary und Mutations-Gegenprobe am Wächter (Verfälschung der Erreichbarkeit und der Kantenarten wird gefangen)
- [ ] CI (6 Checks) grün, Deploy ohne sichtbare Änderung

## Known Limitations

- Die Analyse spricht von 15 Dateien, die Wächterliste führt 14 Einträge in Gruppe S1; die Spec folgt der Wächterliste. Ergibt die Messung nach dem Löschen eine weitere Waise, entscheidet der Wächter (rot) und die Zahl wird im Lieferbericht begründet nachgezogen.
- Die Einstufung "Test prüft nur die Waise" beruht auf Import-/Titelanalyse; sie wird je Datei per benanntem Testlauf nach dem Löschen bestätigt, Mischfälle werden umgebaut statt gelöscht.
- Der Wächter ist ein statischer Importgraph: Verwendung über berechnete Zeichenketten oder externe Registries würde er nicht sehen (laut Analyse gibt es keine). Die Array-Form von `import.meta.glob` ist nicht unterstützt; der Wächter schlägt bei ihr laut an (fail-closed).
- `tests/tdd/test_issue_692_telegram_disabled_unconfigured.py` (Browser-Prüfung gegen Staging) bleibt in S1 unangetastet; ihre Behandlung gehört zu #3374.
- Tote Exporte in lebenden Dateien (`weatherMetricsCompareSave.ts`, `metricsEditor.ts` u. a.) erfasst der Wächter nicht (Dateiebene).

## Out of Scope

- Scheibe S3 (#3385, versand-tab) und S4 (#3384, compare/edit/mobile/utils inklusive `WaypointPin`).
- #3374 (Browser-Specs, Playwright, Staging-Browserprüfungen wie `tests/tdd/test_issue_692_telegram_disabled_unconfigured.py`), außer ein Spec importiert eine gelöschte Datei und bricht Build oder CI.
- `EinstellTabelle.svelte` und ihr Test; `.claude/hooks`; Produktionscode außerhalb der Löschmenge; Barrels und `lib/index.ts`.
- Tote Exporte in lebenden Dateien (eigenes Nachlauf-Issue).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Aufräumarbeit nach bestehender Entscheidung (Löschung von Alt-Editor-Bausteinen, #3297/#3122/#3366) nach vorhandenem Muster; keine neue Entscheidungsfläche.

## Changelog

- 2026-11-26: Initial spec created
- 2026-11-26: Korrigiert nach Validierung (test_issue_692 nach #3374, svelte-check-Baseline gemessen statt behauptet, ink4 ohne Zahl, F001 fünf Testblöcke, Sondertest-Ersatz eindeutig, AC-5/AC-8 testbar)
