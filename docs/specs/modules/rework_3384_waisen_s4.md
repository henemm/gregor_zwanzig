---
entity_id: rework_3384_waisen_s4
type: refactor
created: 2026-11-26
updated: 2026-11-26
status: draft
workflow: rework-3384-waisen-s4
version: "1.2"
tags: [frontend, waisen, ratsche, loeschen, "#3384", "#3366", "#3122", "#3383"]
---

# Rework #3384: Waisen-Scheibe S4 (compare, edit, mobile, utils, WaypointPin) und Findings F001/F002/F004 aus #3383

## Approval

- [ ] Approved

## Purpose

Scheibe S4 der Waisen-Löschung (Nachfolger von #3366 und #3383): 19 Frontend-Dateien ohne Produktionsaufrufer, die heute als Gruppe S4 in `BEKANNTE_WAISEN` des Waisen-Wächters stehen, werden gelöscht, samt der Tests, Prüfstand-Teile, Ratschenzahlen, Katalogschlüssel und Doku-Einträge, die nur sie betreffen. Zusätzlich werden drei Findings des Adversary aus #3383 behoben (Obergrenze exakt an Listenlänge binden, Array-Sperre auch für `import.meta.glob<T>([...])`, Verweise auf das gelöschte `ThresholdMetricRow` entfernen). Für Nutzer ändert sich nichts Sichtbares.

## Source

- **File:** `frontend/src/lib/__tests__/waisen_waechter.test.ts` (Pflege und Erweiterung), `frontend/src/lib/components/{compare,edit,mobile}/`, `frontend/src/lib/utils/`, `frontend/src/lib/components/trip-detail/waypoints/WaypointPin.svelte` (Löschung)
- **Identifier:** Test `Waisen-Wächter` (Liste `BEKANNTE_WAISEN`, Konstante `OBERGRENZE_WAISEN`, Funktionen `findeWaisen`, `pruefeRatsche`, `miniBaum`, Regexe `KANTE` und Array-Sperre)

Schicht: ausschließlich Frontend (`frontend/src/...`, eine E2E-Spec samt Config unter `frontend/e2e/`) plus Testdaten, Goldens, Ratschenzahlen, die CI-Positivliste, `ci.yml` und eine Referenz-Doku. Kein Go-, kein Python-Produktionscode, keine Hook-Änderung (`.claude/hooks` bleibt unberührt). Trip/Vergleich-Teilung: es entsteht kein neuer Baustein; Mandantentrennung: keine Nutzerdaten betroffen; Kanäle: kein Briefing- oder Alarm-Inhalt betroffen.

## Zu löschende Dateien (19, genau die Gruppe S4 in `BEKANNTE_WAISEN`)

Alle Pfade unter `frontend/src/lib/`.

1. `components/compare/AddReportCard.svelte`
2. `components/compare/CreateGroupDialog.svelte`
3. `components/compare/LocationPreviewMap.svelte`
4. `components/compare/layoutPreviewRows.ts`
5. `components/compare/versandPropsAus.ts`
6. `components/compare/wetterMetrikenPropsAus.ts`
7. `components/edit/EditRouteSection.svelte`
8. `components/edit/EditWeatherSection.svelte`
9. `components/edit/WeatherSummaryCard.svelte`
10. `components/edit/weatherSummary.ts`
11. `components/mobile/DrawerGroup.svelte`
12. `components/mobile/DrawerItem.svelte`
13. `components/mobile/NavIcon.svelte`
14. `components/trip-detail/waypoints/WaypointPin.svelte`
15. `utils/alertMetricCatalogIds.ts`
16. `utils/horizonHelpers.ts`
17. `utils/naturalSort.ts`
18. `utils/rightColumn.ts`
19. `utils/weatherEmoji.ts`

Hinweis zur Zahl: Das Issue #3384 und die Analyse (`docs/context/rework-3366-waisen-loeschen.md`) nennen "18 Dateien"; die Gruppe S4 in `BEKANNTE_WAISEN` enthält 19 Einträge (6 compare, 4 edit, 3 mobile, 5 utils, 1 `WaypointPin`). Maßgeblich ist die Wächterliste, weil sie gegen den echten Importgraphen geprüft wird; die Rechnung 26 − 19 = 7 (nur S3) geht damit auf. `WaypointPin.svelte` war in #3383 als `ERHALTEN` geführt, weil sie zu S4 gehört; sie wird hier gelöscht, nachdem vor dem Löschen erneut bestätigt ist, dass sie Waise ist (heute importieren sie nur Testdateien und der Prüfstand `f9Pruefstand.ts`, kein Produktionscode).

## Mitgelöschte Browser-Spec (Ausnahme zu #3374)

`frontend/e2e/issue-1093-unit.spec.ts` (3 Testfälle) importiert ausschließlich `layoutPreviewRows.ts` (Waise Nr. 4). Sie wird deshalb in S4 mitgelöscht (Tech-Lead-Entscheidung, Ausnahme „Spec importiert eine gelöschte Datei“). Die Positivliste `.github/ci_e2e_specs.txt` wird gezählt (Ratsche `E2E_MIN_SPECS`, Zeilenzählung per `grep -c '^e2e/'`). Mitgezogen werden, alle im selben Commit:

- `frontend/e2e/playwright.1093.unit.config.ts` (läuft nur diese Spec),
- `.github/ci_e2e_specs.txt`: Zeile 527 (Eintrag `e2e/issue-1093-unit.spec.ts`) entfernt, der Satz „issue-1093-unit bleibt (Nebenbefund #1199)“ (Z. 462) ersetzt durch den Vermerk „issue-1093-unit mit #3384 gelöscht“, die Zählkommentare Z. 480-483 (Dateien- und Fallzahlen) angepasst,
- `.github/workflows/ci.yml` Z. 328: `E2E_MIN_SPECS` von 86 auf 85 (Kommentar um „85 = 86 - 1 (issue-1093-unit gelöscht, #3384)“ ergänzt),
- `.github/workflows/ci.yml` Z. 329: `E2E_MIN_EXECUTED_HAUPT` von 760 um die Fallzahl der Datei (3) auf 757; die Zahl wird vor dem Löschen per `npx playwright test --list --project=tests` für die Datei gemessen und muss im Lieferstand stimmen,
- `tests/unit/test_2243_playwright_loeschscheibe.py`: Z. 262 (`len(eintraege) == 86` wird `== 85`), Z. 269 (`E2E_MIN_SPECS: 86` wird 85) und Z. 270 (`E2E_MIN_EXECUTED_HAUPT: 760` wird 757, Rechenkommentar um „- 3 (#3384)“ ergänzt),
- `tests/unit/test_e2e_positivliste_ratschen_bindung.py`: `S4_BLEIBT` (Z. 101) entfällt; die Testfunktion Z. 104-115 (heute „enthält die neuen und bleibenden Specs“) wird umgeschrieben. `S4_NEU` bleibt als Anwesenheits-Zusicherung (Datei existiert, Eintrag steht auf der Liste). Neu kommt eine Abwesenheits-Zusicherung für `e2e/issue-1093-unit.spec.ts`: Datei existiert nicht, Eintrag steht nicht auf der Positivliste (geführt als gelöscht mit #3384, analog `S4_RAUS`). Der Docstring Z. 107 („`issue-1093-unit` bleibt“) wird entsprechend angepasst.

`tests/unit/test_2243_playwright_loeschscheibe.py` muss danach grün sein. Die Abgrenzung zu #3374 gilt unverändert für alle anderen Browser-Specs.

## Estimated Scope

- **LoC:** Löschung ca. -1 340 Produktionszeilen (laut Analyse 1 342) plus mitgehende Tests, Goldens und Schlüssel (nach dem Löschen messen, nicht schätzen); neu ca. +70 (Wächter-Ergänzungen F001/F002, Lösch-Nachweis-Block, Wortscan F004, Abwesenheits-Zusicherung)
- **Files:** 19 Produktionsdateien gelöscht, dazu E2E-Spec samt Config und die mitgezogenen Testdateien und Schlüssel (genaue Zahl wird nach dem Löschen gemessen)
- **Effort:** medium

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| 19 Dateien der Liste oben | DELETE | Waisen ohne Aufrufer |
| `frontend/e2e/issue-1093-unit.spec.ts`, `frontend/e2e/playwright.1093.unit.config.ts` | DELETE | Spec importiert nur `layoutPreviewRows.ts`; Config läuft nur diese Spec |
| `.github/ci_e2e_specs.txt` | MODIFY | Z. 527 Eintrag entfernt, Z. 462 Vermerk ersetzt, Zählkommentare Z. 480-483 angepasst |
| `.github/workflows/ci.yml` | MODIFY | Z. 328 `E2E_MIN_SPECS` 86 auf 85; Z. 329 `E2E_MIN_EXECUTED_HAUPT` 760 auf 757 (gemessen) |
| `tests/unit/test_2243_playwright_loeschscheibe.py` | MODIFY | Z. 262 auf 85, Z. 269 auf 85, Z. 270 auf 757 |
| `tests/unit/test_e2e_positivliste_ratschen_bindung.py` | MODIFY | `S4_BLEIBT` entfällt, Testfunktion Z. 104-115 zur Anwesenheit für `S4_NEU` plus Abwesenheits-Zusicherung für `issue-1093-unit`; Docstring Z. 107 angepasst |
| `frontend/src/lib/__tests__/waisen_waechter.test.ts` | MODIFY | S4-Einträge aus `BEKANNTE_WAISEN` streichen; `OBERGRENZE_WAISEN` 26 auf 7; F001; F002; Kopfkommentar nachziehen; Datei enthält das Wort `ThresholdMetricRow` nicht |
| `frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts` | MODIFY | `WaypointPin.svelte` aus `ERHALTEN` (`ERHALTEN_3383`) streichen; neuer Block `#3384` mit allen 19 Pfaden; Wortscan F004 |
| `frontend/src/lib/__tests__/bausteine_waechter_regeln.ts` (bei Z. 716), `frontend/src/lib/components/shared/wetter-tab/compareMetricCatalogLoader.ts` (bei Z. 205), `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/thunderThresholdLevels.test.ts` (Z. 155 und Z. 274) | MODIFY | Verweise auf `ThresholdMetricRow` umformuliert (F004); Produktionslogik unverändert |

**Testdateien, die S4-Dateien importieren oder einlesen (je einzeln entschieden):**

| File (unter `frontend/src/lib/`) | Change Type | Grund |
|------|-------------|-------------|
| `components/compare/layoutPreviewRows.test.ts` | DELETE | reiner Waisentest (`selectPreviewRows`) |
| `utils/rightColumn.test.ts` | DELETE | reiner Waisentest |
| `utils/naturalSort.test.ts` | DELETE | reiner Waisentest |
| `utils/horizonHelpers.test.ts` | DELETE | reiner Waisentest |
| `utils/alertMetricCatalogIds.test.ts` | DELETE | reiner Waisentest |
| `components/edit/weatherSummary.test.ts` | DELETE | reiner Waisentest (`summarizeTripWeather`) |
| `utils/__tests__/hilfstexte_sprache.test.ts` | MODIFY | Fälle `computeHorizonSummary` und `rightColumn: Profil-Standard-Beschriftungen` samt Importen raus; übrige Fälle (`stageRisk`, `cockpitHelpers568`, `profileSignature`) leben |
| `utils/__tests__/report_slot_aktiv.test.ts` | MODIFY | Block „Naht 2a — getReportSchedule“ samt Import aus `rightColumn.ts` raus; übrige Nähte leben |
| `components/compare/__tests__/compare_feldsatz_roundtrip_datenerhalt.test.ts` | MODIFY | Fälle mit `versandPropsAus` raus, übrige Roundtrip-Fälle leben |
| `components/compare/__tests__/compare_versand_hydration_unter_wetter_metriken.test.ts` | MODIFY | Fälle mit `versandPropsAus` raus oder auf die lebende Quelle umgestellt; übrige leben |
| `components/shared/__tests__/versand_vergleich_premium_sms.test.ts` | MODIFY | Fälle mit `versandPropsAus` raus oder auf die lebende Quelle umgestellt; übrige leben |
| `components/shared/__tests__/hub_geteilte_felder_cooldown_quiet_konsistent.test.ts` | MODIFY | Fälle mit `versandPropsAus` raus oder auf die lebende Quelle umgestellt; übrige leben |
| `components/shared/__tests__/hub_reiter_gemeinsame_aufloesung.test.ts` | MODIFY | nur der Fall `#2727 AC-15` (dynamischer Import von `versandPropsAus`, Z. 432-465) wird umgebaut oder entfernt; alle übrigen Blöcke leben |
| `components/edit/issue_503_etappen_waypoints.test.ts` | MODIFY | Block „#522 WaypointPin Cleanup“ (Z. 277-310) und Konstante `WAYPOINT_PIN` raus; übrige Blöcke leben |
| `issue_523_suggested_flag_cleanup.test.ts` | MODIFY | die zwei `AC-7`-Fälle zu `WaypointPin.svelte` (Z. 62-76) raus; übrige leben |
| `__tests__/karten_dark.test.ts` | MODIFY | Fall „Ortsvergleich-Vorschau (LocationPreviewMap)“ und Import (Z. 165, 176) raus; übrige Karten leben |
| `components/compare/issue_462.test.ts` | MODIFY | Einträge `CreateGroupDialog.svelte` und `LocationPreviewMap.svelte` (Z. 41/42) raus, Zählung „12 Dateien“ nachgezogen |
| `components/compare/__tests__/compare_hourly_vocabulary_single_source.test.ts` | MODIFY | Eintrag `utils/alertMetricCatalogIds.ts` (Z. 151) raus |
| `components/shared/__tests__/infobox_nur_beim_anlegen.test.ts` | MODIFY | Fall „wetterMetriken-/alarme-/versandPropsAus liefern kein showInfobox-Feld“ (Z. 508-513) auf die lebende `alarmePropsAus` verkürzt |
| `components/shared/__tests__/reiter_sprunglinks_nur_neue_kennungen.test.ts` | MODIFY | Block „WeatherSummaryCard“ (Z. 128-) und Listeneintrag Z. 317 raus; übrige leben |
| `components/trip-detail/__tests__/deadTripOverviewComponentsRemoved.test.ts` | MODIFY | Block „AC-7: rightColumn.ts …“ samt Konstante `RIGHT_COLUMN_TS` raus; übrige Blöcke leben |
| `components/trip-detail/__tests__/f9Pruefstand.ts`, `f9KatalogAnker.ts`, `tests/golden/f9_trip_flaechen/*` | MODIFY | Nur Fälle von `WaypointPin`, `WeatherSummaryCard`, `EditRouteSection` (`wegpunkte`, `edit_felder`) entfernen; Goldens ausschließlich mit dem Projektwerkzeug neu erzeugt, DE und EN vorher/nachher gegengelesen |
| `components/compare/__tests__/f10Pruefstand.ts`, `f10KatalogAnker.ts` und zugehörige f10-Goldens | MODIFY | Nur die Teile, die gelöschte S4-Dateien rendern oder importieren (`AddReportCard`, `LocationPreviewMap`, `CreateGroupDialog`), fallen weg; Goldens nur dafür mit dem Projektwerkzeug neu erzeugt |
| `frontend/src/lib/components/shared/__tests__/` (Ordner) | MODIFY | enthält die vier Testdateien `hub_geteilte_felder_cooldown_quiet_konsistent`, `hub_reiter_gemeinsame_aufloesung`, `versand_vergleich_premium_sms`, `infobox_nur_beim_anlegen`, `reiter_sprunglinks_nur_neue_kennungen` aus der Tabelle oben |

Regel: Weitere Importeure, die beim Löschen auffallen, folgen derselben Regel (reiner Waisentest = DELETE, lebender Anteil = MODIFY) und werden im Lieferbericht genannt. Die Einstufung „MODIFY“ gilt, bis der benannte Testlauf nach dem Löschen etwas anderes zeigt; sie wird je Datei im Lieferbericht bestätigt.

**Weitere Pflege (Zahlen, Katalog, Doku):**

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/__tests__/{bausteine_waechter_regeln.ts,ink4_waechter.test.ts}` | MODIFY | BESTAND-Einträge (laut Analyse 12), `BESTAND_OBERGRENZE` (heute 177) und ink4-Einträge nach dem Löschen messen und im selben Commit senken |
| `tests/unit/ein_katalog_ausnahmen.json`, `tests/unit/test_ein_katalog_eine_verarbeitung_ratsche.py` | MODIFY | Einträge `alertMetricCatalogIds`, `weatherEmoji` entfernen; `hoechststand` (JSON, heute 430) und `HOECHSTSTAND` (Python) nach Messung an beiden Stellen im selben Commit senken |
| `frontend/src/lib/i18n/__tests__/{keine_hartkodierten_nutzertexte,reaktivitaet_waechter,deutsch_unveraendert}.test.ts` | MODIFY | Dateilisten kürzen, Zählungen neu messen |
| `frontend/src/lib/i18n/messages/{de,en}/*.json` | MODIFY | Schlüssel ohne Verwender entfernen (laut Analyse `vergleich.*`, `bausteine.*`, `trip.route.*` 13; Liste durch `katalog_schluessel_haben_verwender.test.ts` gemessen, de und en gleiche Menge) |
| `tests/` Python: `test_trip_alert_stage_name`, `test_issue_316_docs_cleanup` | MODIFY | Nur die Waisenpfade herausnehmen, übrige Fälle bleiben |
| `docs/reference/frontend_components.md` | MODIFY | Einträge der 19 gelöschten Komponenten entfernen |
| Elementliste (Projektwerkzeug) | MODIFY | Nach dem Löschen mit dem Projektwerkzeug neu erzeugt, nie von Hand |

Nicht angefasst: `components/molecules/EinstellTabelle.svelte` und ihr Test, `.claude/hooks`, Scheibe S3 (#3385, versand-tab), alle übrigen Browser-Specs (#3374, darunter `tests/tdd/test_issue_692_telegram_disabled_unconfigured.py`), jeder Produktionscode außerhalb der Löschmenge. Reine Kommentarnennungen von S4-Namen in anderen E2E-Specs (z. B. `hub-reiter-alt-kennungen-umleitung.spec.ts`) bleiben.

### Estimated Changes

- Files: 19 Produktionsdateien gelöscht, 2 E2E-Dateien gelöscht, 6 Testdateien gelöscht, rund 20 Testdateien gekürzt, Rest Pflege (nach Messung)
- LoC: +70 / -(ca. 1 340 Produktion + mitgehende Tests)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/rework-3384-waisen-s4.md`, `docs/context/rework-3366-waisen-loeschen.md` | doc | Analyse (Abschnitt S4): Dateiliste, Tests, f9/f10, Ratschen, Schlüssel |
| `docs/specs/modules/rework_3383_waisen_s1.md` | spec | Vorlage und Vorbild (geliefert mit PR #3387) |
| `frontend/src/lib/__tests__/waisen_waechter.test.ts` | test | Wächter, Ratsche, Selbstnachweis |
| `frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts` | test | Listen `GELOESCHT`/`ERHALTEN`, Wortscan |
| `frontend/src/lib/i18n/__tests__/katalog_schluessel_haben_verwender.test.ts` | test | Fundmechanismus für Katalogschlüssel ohne Verwender |
| `frontend/src/lib/components/trip-detail/__tests__/trip_hub_sprache.test.ts` | test | Golden-Vergleich der f9-Goldens (DE und EN) |
| `.github/ci_e2e_specs.txt`, `.github/workflows/ci.yml`, `tests/unit/test_e2e_positivliste_ratschen_bindung.py`, `tests/unit/test_2243_playwright_loeschscheibe.py` | ci/test | Positivliste und Ratschen für die mitgelöschte Spec |
| Golden- und Elementlisten-Werkzeug des Projekts | tooling | Goldens und Elementliste neu erzeugen, nie von Hand schreiben |
| `node --test`, `svelte-check`, Vite-Build | tooling | Nachweis keine sichtbare Änderung |

## Implementation Details

**Löschung S4.** Zuerst RED: Wächter-Liste um die 19 Einträge kürzen und `OBERGRENZE_WAISEN` auf 7 setzen, der Wächter meldet die 19 Dateien als neue Waisen. Vor dem Löschen wird `WaypointPin.svelte` gegen den echten Importgraphen erneut als Waise bestätigt und die Fallzahl von `issue-1093-unit.spec.ts` gemessen. Dann die 19 Dateien samt Spec und Config löschen, danach die betroffenen Testdateien benannt laufen lassen (nie `uv run pytest` ohne Dateinamen); jede neu rote Datei ist ein Umbaufall, jede Datei, die nur Gelöschtes prüft, wird gelöscht. Zahlen (`BESTAND_OBERGRENZE`, `hoechststand`/`HOECHSTSTAND`, ink4, Zählung in `reaktivitaet_waechter`, Katalogschlüssel) werden nach dem Löschen gemessen und im selben Commit eingetragen. Die Elementliste wird mit dem Projektwerkzeug erzeugt. Die svelte-check-Baseline wird vor dem Löschen auf dem Branch-Stand gemessen.

**Wächter.** Streichen der 19 Einträge der Gruppe S4; `OBERGRENZE_WAISEN` sinkt um genau diese Zahl von 26 auf 7 (es bleibt nur S3: 7 Einträge in `versand-tab`). Der Lösch-Nachweis erhält einen Block `#3384`; `WaypointPin.svelte` verlässt `ERHALTEN`.

**F001.** `pruefeRatsche` wird verschärft: Die Obergrenze muss exakt der Listenlänge entsprechen (Prüfung `bekannte.length !== obergrenze` statt `>`). Mini-Fall: Obergrenze größer als die Liste ergibt rot. Zusätzlich gilt die Zusicherung `OBERGRENZE_WAISEN === BEKANNTE_WAISEN.length` am echten Baum.

**F002.** Feste Regexe:
- Array-Sperre: `/import\.meta\.glob\s*(?:<[^>]*>)?\s*\(\s*\[/`
- Kantenregel String-Form ebenso mit optionalem Typparameter `(?:<[^>]*>)?` im Alternativzweig von `KANTE` (`import\.meta\.glob\s*(?:<[^>]*>)?\s*\(\s*['"]([^'"]+)['"]`).

Zwei eigene Mini-Baum-Blöcke: `import.meta.glob<T>([...])` wird laut rot (Meldung „Array-Form von import.meta.glob nicht unterstützt — Wächterlogik ergänzen“), `import.meta.glob<T>('./x/*.ts')` macht die passenden Dateien erreichbar. Die exakte Mini-Baum-Liste wird mitgeführt.

**F004.** Ein Scan über `frontend/src` (Endungen `.ts`, `.svelte`, `.js`) prüft das ganze Wort `ThresholdMetricRow` (`\bThresholdMetricRow\b`), egal ob in Code oder Kommentar; erlaubt sind 0 Treffer. Es gibt genau eine feste Ausnahme: `trip_pfad_altfeld_loeschnachweis_3297.test.ts`, weil sie den Namen als Gelöscht-Eintrag führt (heute Z. 178, gemessen). `waisen_waechter.test.ts` enthält das Wort nicht und ist keine Ausnahme. Keine Historien-Ausnahme. Änderungsziele fest: `bausteine_waechter_regeln.ts` (bei Z. 716), `compareMetricCatalogLoader.ts` (bei Z. 205), `thunderThresholdLevels.test.ts` (Z. 155 und Z. 274). Der Scan liegt im Lösch-Nachweis (`trip_pfad_altfeld_loeschnachweis_3297.test.ts`).

## Expected Behavior

- **Input:** Quelltext von `frontend/src`.
- **Output:** Wächter grün, solange die Waisenmenge (ohne `AUSNAHMEN`) exakt `BEKANNTE_WAISEN` (7 Einträge, S3) entspricht und `OBERGRENZE_WAISEN` (7) exakt der Listenlänge gleicht; Löschung ohne Funktionsänderung.
- **Side effects:** Keine sichtbare Änderung für Nutzer; Ratschenzahlen, Katalog, CI-Positivliste (85 Specs) und Doku schrumpfen.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Wächter rot vor der Löschung: `waisen_waechter.test.ts` mit gekürzter Liste und `OBERGRENZE_WAISEN = 7` meldet die 19 S4-Dateien als neue, nicht gelistete Waisen (RED), nach der Löschung grün.
- [ ] Lösch-Nachweis rot vor der Löschung: `existsSync` der 19 Pfade ist noch `true`; nach der Löschung `false`, kein Importtreffer im Produktionscode.
- [ ] F001: Mini-Fall mit Obergrenze größer als die Liste ist rot; Mutations-Gegenprobe (`!==` zurück auf `>`) macht den Block rot.
- [ ] F002: Mini-Baum-Blöcke `glob<T>([…])` (rot, Meldung „nicht unterstützt“) und `glob<T>('./x/*.ts')` (erreichbar); Mutations-Gegenprobe je Block (Typparameter-Teil `(?:<[^>]*>)?` aus Sperre bzw. Kantenregel entfernen) macht den jeweiligen Block rot.
- [ ] F004: Wortscan `ThresholdMetricRow` über `frontend/src` rot vor der Bereinigung (Fundstellen), danach 0 Treffer außerhalb der einen Ausnahmedatei; Mutation „Kommentar wieder einfügen“ ergibt rot.
- [ ] Betroffene Testdateien benannt laufen lassen: alle in der Tabelle oben genannten Dateien sowie `waisen_waechter`, `trip_pfad_altfeld_loeschnachweis_3297`, `katalog_schluessel_haben_verwender`, `paritaet_de_en`, `deutsch_unveraendert`, `bausteine_waechter`, `ink4_waechter`, `reaktivitaet_waechter`, `keine_hartkodierten_nutzertexte`, `trip_hub_sprache` und alle `f9Pruefstand`- und `f10Pruefstand`-Nutzer.
- [ ] Python (benannt): `test_trip_alert_stage_name`, `test_issue_316_docs_cleanup`, `tests/unit/test_ein_katalog_eine_verarbeitung_ratsche.py`, `tests/unit/test_e2e_positivliste_ratschen_bindung.py` (Anwesenheit `S4_NEU`, Abwesenheit `issue-1093-unit`), `tests/unit/test_2243_playwright_loeschscheibe.py` (85 Einträge, `E2E_MIN_SPECS: 85`, `E2E_MIN_EXECUTED_HAUPT: 757`) und der Verweiswächter für `tests/fixtures/einstellung_gleich_mail/` grün.
- [ ] Gesamt: Frontend-Suite (`node --test`), Vite-Build und `svelte-check` grün; die svelte-check-Baseline (Fehler/Warnungen) wird vor dem Löschen gemessen und darf nachher nicht steigen; beide Zahlen stehen im Test-Artefakt.

## Acceptance Criteria

- **AC-1:** Given die 19 Dateien der Gruppe S4 (`compare/*` sechs, `edit/*` vier, `mobile/*` drei, `utils/*` fünf, `trip-detail/waypoints/WaypointPin.svelte`) / When das Dateisystem nach S4 geprüft wird / Then existiert keine der 19 Dateien mehr, kein Produktionscode importiert die gelöschten Basisnamen, und `EinstellTabelle.svelte` besteht weiter.
  - Test: `trip_pfad_altfeld_loeschnachweis_3297.test.ts` (Block `#3384`, `existsSync === false` plus Importscan); `WaypointPin.svelte` ist aus `ERHALTEN` entfernt. Architektur-Wächter über den echten Importgraphen, kein Dateiinhalt-Check als Verhaltensnachweis; Nutzerverhalten belegt AC-8.

- **AC-2:** Given die Gruppe S4 in `BEKANNTE_WAISEN` gestrichen / When der Wächter die Erreichbarkeit ab `routes/` und `src/*.ts` berechnet / Then ist die Waisenmenge (ohne `AUSNAHMEN`) genau `BEKANNTE_WAISEN` mit 7 Einträgen (nur S3), `OBERGRENZE_WAISEN` ist die feste Literal-Konstante 7 (um genau 19 gesenkt), und der Test ist grün; ohne Streichen oder ohne Löschung wäre er rot.
  - Test: `waisen_waechter.test.ts` gegen den echten Baum, im RED-Stand vor der Löschung rot mit den 19 Pfaden. Architektur-Wächter, kein Dateiinhalt-Check als Verhaltensnachweis; Nutzerverhalten belegt AC-8.

- **AC-3 (F001):** Given `pruefeRatsche` mit Obergrenze und Liste / When die Obergrenze größer als die Listenlänge ist (etwa erhöht, ohne Eintrag hinzuzufügen) oder kleiner / Then wird der Wächter rot, weil die Obergrenze exakt der Listenlänge entsprechen muss; am echten Baum gilt `OBERGRENZE_WAISEN === BEKANNTE_WAISEN.length`.
  - Test: neuer Mini-Fall-Block (Obergrenze größer als die Liste, rot) und Zusicherung am echten Baum in `waisen_waechter.test.ts`; Mutations-Gegenprobe (Prüfung auf `>` zurücksetzen) macht den Block rot.

- **AC-4 (F002):** Given ein erfundener Mini-Baum mit `import.meta.glob<T>(['./x/*.ts'])` und ein zweiter mit `import.meta.glob<T>('./x/*.ts')` / When der Wächter die Erreichbarkeit berechnet / Then bricht er beim ersten laut mit „Array-Form von import.meta.glob nicht unterstützt — Wächterlogik ergänzen“ ab, und beim zweiten gelten die passenden Dateien als erreichbar; die Form ohne Typparameter bleibt unverändert rot (Array) bzw. erreichbar (String).
  - Test: zwei eigene Mini-Baum-Blöcke in `waisen_waechter.test.ts` (inklusive Mitführen der exakten Mini-Baum-Liste); Mutations-Gegenprobe je Block (Typparameter-Teil aus Sperre bzw. Kantenregel entfernen) macht den jeweiligen Block rot.

- **AC-5 (F004):** Given Verweise auf das gelöschte `ThresholdMetricRow` in Code und Kommentaren / When S4 umgesetzt ist / Then findet ein Scan über `frontend/src` (`.ts`, `.svelte`, `.js`) das ganze Wort `ThresholdMetricRow` nur noch in `trip_pfad_altfeld_loeschnachweis_3297.test.ts` (der einen festen Ausnahme, die den Namen als Gelöscht-Eintrag führt), und die Verweise in `bausteine_waechter_regeln.ts`, `compareMetricCatalogLoader.ts` und `thunderThresholdLevels.test.ts` sind entfernt.
  - Test: Wortscan im Lösch-Nachweis grün; vor der Bereinigung rot mit den Fundstellen; Mutation „Kommentar wieder einfügen“ ergibt rot.

- **AC-6:** Given die Löschung der compare/edit/mobile/utils-Waisen / When die in der Tabelle genannten Testdateien nach DELETE bzw. MODIFY bearbeitet und die Prüfstände (`f9`, `f10`) gekürzt sind / Then sind die sechs reinen Waisentests gelöscht, alle gemischten Tests nur um die Waisen-Fälle gekürzt und grün, in `f10Pruefstand.ts` fallen nur Teile weg, die gelöschte S4-Dateien rendern oder importieren, die f9-/f10-Goldens sind ausschließlich mit dem Projektwerkzeug neu erzeugt (Goldens ohne Bezug unverändert), die Python-Tests `test_trip_alert_stage_name` und `test_issue_316_docs_cleanup` laufen ohne Waisenpfade grün, und `docs/reference/frontend_components.md` führt keine der 19 Komponenten mehr; weitere beim Löschen auffallende Importeure folgen derselben Regel und stehen im Lieferbericht.
  - Test: `trip_hub_sprache.test.ts`, die f10-Nutzer und die benannten Testdateien aus dem Test Plan grün; die beiden Python-Tests benannt grün; Elementliste mit dem Projektwerkzeug erzeugt und gemessen.

- **AC-7:** Given die Löschung inklusive `issue-1093-unit.spec.ts` / When die Zahlenratschen (`BESTAND_OBERGRENZE`, ink4, `hoechststand`/`HOECHSTSTAND` ein_katalog, Zählung in `reaktivitaet_waechter`, Katalogschlüssel de/en, `E2E_MIN_SPECS`, `E2E_MIN_EXECUTED_HAUPT`, Positivliste) geprüft werden / Then stimmen alle Zahlen mit der Messung nach dem Löschen überein und sind nur gesunken, `hoechststand` (JSON) und `HOECHSTSTAND` (Python) sind identisch gesenkt, `E2E_MIN_SPECS` steht in `ci.yml` und in `test_2243_playwright_loeschscheibe.py` auf 85 und die Positivliste hat 85 Einträge, `E2E_MIN_EXECUTED_HAUPT` steht an beiden Stellen auf 757 (760 minus gemessene 3 Fälle), die Positivliste führt `issue-1093-unit` nicht mehr, und `test_e2e_positivliste_ratschen_bindung.py` sichert per Abwesenheits-Zusicherung, dass die Spec weder als Datei noch auf der Liste vorkommt; de und en führen dieselbe Schlüsselmenge und kein Schlüssel ohne Verwender bleibt.
  - Test: `bausteine_waechter`, `ink4_waechter`, `reaktivitaet_waechter`, `katalog_schluessel_haben_verwender`, `paritaet_de_en`, `deutsch_unveraendert`, `tests/unit/test_ein_katalog_eine_verarbeitung_ratsche.py`, `tests/unit/test_e2e_positivliste_ratschen_bindung.py` und `tests/unit/test_2243_playwright_loeschscheibe.py` grün.

- **AC-8:** Given die Seiten und Ansichten (insbesondere Trip-Editor, Vergleichs-Editor, Trip-Detail, mobile Navigation) / When die gesamte Frontend-Suite, der Produktions-Build und `svelte-check` laufen / Then sind alle grün, die svelte-check-Zahlen (Fehler/Warnungen) wurden vor dem Löschen auf dem Branch-Stand gemessen und steigen nachher nicht, und für Nutzer gibt es keine sichtbare Änderung.
  - Test: Frontend-Suite per `node --test`, `npm run build`, `svelte-check` (beide Zahlen vorher/nachher im Test-Artefakt); Python-Verweiswächter für `tests/fixtures/einstellung_gleich_mail/` grün.

- **AC-9:** Given die Scheibe S3 (#3385), alle übrigen Browser-Specs (#3374), `EinstellTabelle.svelte` und `.claude/hooks` / When S4 geliefert ist / Then sind deren Dateien unverändert (einzige Browser-Spec-Ausnahme ist die mitgelöschte `issue-1093-unit.spec.ts` samt Config), und die 7 verbleibenden Wächter-Einträge entsprechen genau der Scheibe S3.
  - Test: Wächter grün mit genau den 7 `versand-tab`-Einträgen; Vergleich gegen `main` zeigt keine Änderung an den genannten Pfaden (Prüfung im Validator-Lauf).

## Definition of Done

- [ ] Spec freigegeben (`approved`/`freigabe`)
- [ ] RED-Nachweis: Wächter und Lösch-Nachweis rot vor der Löschung, grün danach
- [ ] `WaypointPin.svelte` vor dem Löschen erneut als Waise bestätigt, Fallzahl von `issue-1093-unit` gemessen
- [ ] 19 S4-Dateien und `issue-1093-unit.spec.ts` samt Config gelöscht, mitgezogene Tests (Tabelle), Prüfstand-Teile (f9, f10), Goldens, Schlüssel, Ratschen, Positivliste, `ci.yml`, Doku im selben Commit gepflegt
- [ ] `OBERGRENZE_WAISEN` auf 7, `BEKANNTE_WAISEN` nur noch S3, Block `#3384` im Lösch-Nachweis
- [ ] F001, F002, F004 umgesetzt und je mit Mutations-Gegenprobe als rot nachgewiesen
- [ ] Zahlen nach dem Löschen gemessen und eingetragen, Elementliste mit Projektwerkzeug erzeugt
- [ ] Frontend-Suite, Build, `svelte-check` und die benannten Python-Tests grün (svelte-check vorher gemessen, nachher nicht höher)
- [ ] Adversary und Mutations-Gegenprobe am Wächter
- [ ] CI (6 Checks) grün, Deploy ohne sichtbare Änderung

## Known Limitations

- Das Issue und die Analyse sprechen von 18 Dateien, die Wächterliste führt 19 Einträge in Gruppe S4; die Spec folgt der Wächterliste. Ergibt die Messung nach dem Löschen eine weitere Waise, entscheidet der Wächter (rot) und die Zahl wird im Lieferbericht begründet nachgezogen.
- Die Einstufung je Testdatei beruht auf Import-/Titelanalyse; sie wird je Datei per benanntem Testlauf nach dem Löschen bestätigt, Mischfälle werden umgebaut statt gelöscht.
- Der Wächter ist ein statischer Importgraph: Verwendung über berechnete Zeichenketten oder externe Registries würde er nicht sehen. Die Array-Form von `import.meta.glob` (auch mit Typparameter) bleibt nicht unterstützt und schlägt laut an (fail-closed).
- Der Wortscan (F004) erfasst nur das Wort `ThresholdMetricRow`; andere gelöschte Namen in Kommentaren sind nicht Ziel.
- Tote Exporte in lebenden Dateien erfasst der Wächter nicht (Dateiebene).

## Out of Scope

- Scheibe S3 (#3385, versand-tab).
- #3374 (alle übrigen Browser-Specs, Playwright, Staging-Browserprüfungen wie `tests/tdd/test_issue_692_telegram_disabled_unconfigured.py`); einzige Ausnahme `issue-1093-unit.spec.ts` (siehe oben).
- `EinstellTabelle.svelte` und ihr Test; `.claude/hooks`; Produktionscode außerhalb der Löschmenge; Barrels und `lib/index.ts`.
- Finding F003 aus #3383 und tote Exporte in lebenden Dateien (eigenes Nachlauf-Issue).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Aufräumarbeit nach bestehender Entscheidung (Löschung von Alt-Editor-Bausteinen, #3297/#3122/#3366/#3383) nach vorhandenem Muster; keine neue Entscheidungsfläche.

## Changelog

- 2026-11-26: Initial spec created
- 2026-11-26: Korrigiert nach Validierung (issue-1093-unit mitgelöscht samt Positivliste und Ratschen, F001 exakte Gleichheit, F002 feste Regexe und zwei Blöcke, F004 Wortscan, f10 als MODIFY)
- 2026-11-26: v1.2 (Zählstellen ci.yml/test_2243 namentlich, Positivliste fest gezählt, F004 genau eine Ausnahme, Testdateien einzeln, S4_BLEIBT als Abwesenheits-Zusicherung)
