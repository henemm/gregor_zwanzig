---
entity_id: rework_3374_tote_browserpruefungen
type: refactor
created: 2026-11-26
updated: 2026-11-26
status: draft
workflow: rework-3374-tote-browserpruefungen
version: "1.0"
tags: [frontend, e2e, playwright, testpflege, loeschen, "#3374", "#3122", "#3164"]
---

# Rework #3374: Tote Browser-Prüfungen des Alt-Editors neu schreiben oder streichen

## Approval

- [ ] Approved

## Purpose

Acht Playwright-Specs außerhalb der CI-Positivliste bewachen seit dem Rückbau des Alt-Editors (Wetter-Reiter `weather-metrics-tab`, `wm2-grundauswahl`, Alarme-Reiter, alte Compare-Layout-Flächen) nichts mehr oder sind auf Staging rot. Jede Zusicherung, die heute noch gilt und nirgends lebend bewacht ist, wird als benannter Testfall in eine CI-gelistete lebende Spec übertragen bzw. neu geschrieben; alles andere wird gestrichen. Danach werden die acht Alt-Specs samt ausschließlich von ihnen genutzter Configs und Setups gelöscht. Reine Testpflege, keine Produktänderung.

## Source

- **File:** `frontend/e2e/` (8 Specs gelöscht; Ziel-Specs `was-steht-wo-karte.spec.ts`, `hub-anlegen-ablauf.spec.ts`, `hub-konfliktschutz-zwei-kontexte.spec.ts`, `design-system-trip-vergleich.spec.ts` erweitert)
- **Identifier:** Testfälle `WS-neu-*`, `AN-neu-*`, `KS-neu-*`, `DS-neu-*` (genaue Nummern vergibt der Developer fortlaufend nach dem letzten Bestand der jeweiligen Datei); Lösch-Nachweis-Test `tests/unit/test_3374_tote_browserpruefungen_geloescht.py`

Schicht: ausschließlich Frontend-E2E (`frontend/e2e/`, `frontend/playwright.*.config.ts`) plus Python-Pin-Tests unter `tests/`. Kein Go-, kein Python-Produktionscode, keine Hook- oder Gate-Config-Änderung, kein Override. Trip/Vergleich-Teilung: kein neuer Baustein, die übertragenen Fälle laufen je Kontext (`route`/`vergleich`), wo das Original beide abdeckte. Mandantentrennung: keine neuen datenbewegenden Endpoints, Zwei-Nutzer-Regel greift nicht; die Fälle laufen unter dem jeweiligen Prüfkonto der Ziel-Spec. Kanäle: kein Briefing- oder Alarm-Inhalt verändert.

## Befund AC-4 „21 statt 9 Zeilen“ (compare-hourly-metric-order)

Kein Produktfehler. Seit #3047 H1 leitet ein Vergleich ohne eigene Stundenverlauf-Auswahl die Stundenzeilen aus der Grundauswahl ab (nur Metriken mit Stundenspalte); ein neuer Vergleich erbt die Grundauswahl aus der Vorlage, 21 Zeilen sind gewollt. Der feste 9er-Default `HOURLY_DEFAULT_METRIC_IDS` gilt nur, wenn auch die Grundauswahl nie gesetzt wurde. Belege: `src/output/renderers/compare_hourly_metric_ids.py` (Z. 105-117, 240-263 `_standard_aus_grundauswahl`), Aufruf `src/services/placements.py:338`. Die Liste auf `/compare/new` ist mit #3276 entfernt; das heutige AC-4 ist eine Negativ-Zusicherung (grün) und doppelt zu `hub-anlegen-ablauf.spec.ts` AN-12 (CI). Es erfolgt keine Code-Änderung.

## Estimated Scope

- **LoC:** ca. +350 / -2 300
- **Files:** 8 Specs + 8 Configs/Setups gelöscht, 4 Specs erweitert, 2 Python-Pin-Tests angepasst, 1 Config angepasst, 1 neuer Python-Test
- **Effort:** medium

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/e2e/epic-138-metriken-editor.spec.ts` | DELETE | Alt-Wetter-Reiter; AC-5b wird übertragen, Rest gestrichen |
| `frontend/e2e/weather-metrics-tab-autosave.spec.ts` | DELETE | AC-3 und F003/F004 übertragen, Rest gestrichen |
| `frontend/e2e/compare-hourly-metric-order.spec.ts` | DELETE | AC-3 übertragen, AC-4 gestrichen (AN-12 deckt) |
| `frontend/e2e/layout-tab-vergleich.spec.ts` | DELETE | AC-4 und AC-8 übertragen, AC-7/AC-11 gestrichen (AN-12 deckt) |
| `frontend/e2e/fix-2069-alert-preview-echte-segmente.spec.ts` | DELETE | Fall (a) neu geschrieben, Fall (b) gestrichen (WS-16 deckt) |
| `frontend/e2e/feat-1395-s3-etag-ifmatch.staging.spec.ts` | DELETE | Fall 3/4/5 übertragen, Fall 1/2 gestrichen |
| `frontend/e2e/save-status-indicator-honesty.spec.ts` | DELETE | AC-1..4 gestrichen (GG-1, SC-1, SC-1b decken) |
| `frontend/e2e/weather-metrics-editor-day-range-kuerzel.spec.ts` | DELETE | AC-1..9 gestrichen (Fläche entfallen, AN-12 kehrt AC-9 um) |
| `frontend/playwright.1234.staging.config.ts`, `frontend/e2e/feat-1234.staging.setup.ts` | DELETE | nur von weather-metrics-tab-autosave genutzt |
| `frontend/playwright.1269.staging.config.ts`, `frontend/e2e/feat-1269-save-status-lie.staging.setup.ts` | DELETE | nur von save-status-indicator-honesty genutzt |
| `frontend/e2e/playwright.feat-1395-s3.staging.config.ts`, `frontend/e2e/feat-1395-s3-etag-ifmatch.staging.setup.ts` | DELETE | nur von feat-1395-s3 genutzt |
| `frontend/playwright.compare-hourly-metric-order.staging.config.ts`, `frontend/e2e/compare-hourly-metric-order.staging.setup.ts` | DELETE | nur von compare-hourly-metric-order genutzt |
| `frontend/playwright.1273-s4c.staging.config.ts` | MODIFY | nur `layout-tab-vergleich` aus `testMatch` entfernen (Config bleibt, geteilt) |
| `frontend/e2e/was-steht-wo-karte.spec.ts` (+ `was-steht-wo.helpers.ts` falls Hilfsfunktion nötig) | MODIFY | 5 neue Fälle `WS-neu` |
| `frontend/e2e/hub-anlegen-ablauf.spec.ts` | MODIFY | 2 neue Fälle `AN-neu` |
| `frontend/e2e/hub-konfliktschutz-zwei-kontexte.spec.ts` | MODIFY | 2 neue Fälle `KS-neu` (Pausieren, Archivieren) |
| `frontend/e2e/design-system-trip-vergleich.spec.ts` | MODIFY | 1 neuer Fall `DS-neu` (Etappen-Startzeit mit If-Match, Neuladen); CI-gelistet. Alternative nur bei technischem Hindernis: `hub-konfliktschutz-zwei-kontexte.spec.ts`; `issue-675-stage-start-time.spec.ts` steht nicht auf der Positivliste und scheidet aus |
| `tests/unit/test_2243_playwright_loeschscheibe.py` | MODIFY | `GEKUERZTE_SPECS`, `LEBENDE_FAELLE` (epic-138) und `BEHALTENE_SPECS` (layout-tab-vergleich) nachziehen |
| `tests/tdd/test_compare_e2e_storagestate_migration.py` | MODIFY | `MIGRATED_FILES` ohne layout-tab-vergleich und ohne Verweis auf die angepasste 1273-s4c-Zeile |
| `tests/unit/test_3374_tote_browserpruefungen_geloescht.py` | CREATE | deterministischer Lösch- und Übertragungsnachweis, ohne Netz |

### Zu übertragende Zusicherungen (Ziel-Zuordnung)

| Zusicherung (Herkunft) | Ziel-Spec (CI) | Neuer Fall |
|---|---|---|
| Vorschau-Spalte Roh/Einfach wird gespeichert, Gewitter ohne Schalter (epic138 AC-5b) | `was-steht-wo-karte.spec.ts` | WS-neu-1 |
| Kartenwechsel per Tastatur speichert; Klick auf Überschrift speichert nichts (autosave F003/F004) | `was-steht-wo-karte.spec.ts` | WS-neu-2 |
| Katalog-Fehler zeigt Fehler + „Neu laden“ (`was-steht-wo-fehler`/`-erneut-laden`), kein PUT (autosave AC-3) | `was-steht-wo-karte.spec.ts` | WS-neu-3 |
| Stundenverlauf-Spalte im Vergleich: nur „nur in der E-Mail“, keine Kappungsaussage (hourly AC-3) | `was-steht-wo-karte.spec.ts` | WS-neu-4 |
| Trip ohne Etappe mit 2 Wegpunkten zeigt `alert-preview-no-stages` statt Vorschau, kein Abruf (fix2069 a); Saat mit `display_config.metrics`, Bereich `zustellung-beispiel-alarm` | `was-steht-wo-karte.spec.ts` | WS-neu-5 |
| Ohne Orte bleibt Reiter Zustellung beim Vergleich-Anlegen gesperrt (layout AC-4) | `hub-anlegen-ablauf.spec.ts` | AN-neu-1 |
| Zustellung bei 390 px ohne Querscrollen (layout AC-8) | `hub-anlegen-ablauf.spec.ts` | AN-neu-2 |
| Nach Pausieren im Hub speichert eine Alarm-Änderung in Zustellung ohne 412 (1395 Fall 3) | `hub-konfliktschutz-zwei-kontexte.spec.ts` | KS-neu-1 |
| Nach Archivieren im Hub speichert eine Alarm-Änderung in Zustellung ohne 412 (1395 Fall 4) | `hub-konfliktschutz-zwei-kontexte.spec.ts` | KS-neu-2 |
| Etappen-Startzeit wird mit If-Match gespeichert und bleibt nach Neuladen (1395 Fall 5) | `design-system-trip-vergleich.spec.ts` | DS-neu-1 |

### Gestrichene Zusicherungen (heute lebend an anderer Stelle bewacht)

epic138 AC-1/2/3/4/6/7/10 (WS-1, WS-B4, epic-138-block-b, hub-wetter-metriken MS-1/MS-6, hub-save-chip SC-2, speicherung-ueberlebt-neuladen AC-4); autosave AC-1/2/4/5/6 (GG-1, SC-1b, MS-1, MS-6, hub-wertebereiche-speichert-selbst); hourly AC-4 und layout AC-7/AC-11 (AN-12); fix2069 (b) (WS-16); 1395 Fall 1/2 (MS-1, KS-1, MS-5, VS-2); 1269 AC-1..4 (GG-1, SC-1, SC-1b); 1728 AC-1..9 (Fläche entfallen, AN-12 kehrt AC-9 um).

### Estimated Changes

- Files: 8 Specs + 8 Configs/Setups gelöscht, 4 Specs, 2 Pin-Tests, 1 Config angepasst, 1 Test neu
- LoC: +350 / -2 300

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/rework-3374-tote-browserpruefungen.md` | doc | Analyse, Einzelfall-Inventar, Ziel-Zuordnung |
| `.github/ci_e2e_specs.txt` | ci | Positivliste (Ratsche, Filter A); Ziel-Specs stehen dort, die 8 Alt-Specs nicht; die Liste wird nicht verändert |
| `frontend/e2e/was-steht-wo.helpers.ts` | test-helper | `oeffneKarte()` und Login per storageState |
| `tests/unit/test_2243_playwright_loeschscheibe.py` | test | Pin-Test Löschscheibe #2243 |
| `tests/tdd/test_compare_e2e_storagestate_migration.py` | test | Pin-Test storageState-Migration |
| `tests/unit/test_e2e_positivliste_ratschen_bindung.py` | test | Bindung Positivliste/Ratschen; muss unverändert grün bleiben |
| Playwright-Stack (CI-Stack bzw. Staging) | infra | echter Stack für Browser-Fälle, kein Mock |

## Implementation Details

**Reihenfolge.** (1) RED: Lösch-Nachweis-Test schreiben; er ist rot, solange die 8 Dateien existieren oder ein übertragener Testfall in seiner Ziel-Spec fehlt. (2) Die 10 neuen Fälle in den vier Ziel-Specs schreiben und gegen den echten Stack laufen lassen (CI-Stack, ersatzweise Staging `https://staging.gregor20.henemm.com` mit Staging-Login). (3) Alt-Specs, exklusive Configs und Setups löschen, `playwright.1273-s4c.staging.config.ts` nur im `testMatch` kürzen. (4) Pin-Tests nachziehen. (5) Betroffene Testdateien benannt laufen lassen (nie `uv run pytest` ohne Dateinamen).

**Neue Browser-Fälle.** Kein Mock-Theater: Ausnahme ist allein das gezielte Abfangen der Katalog-Antwort per `page.route` in WS-neu-3 (Fehlerzustand lässt sich am echten Stack nicht erzeugen); die UI-Reaktion und das Ausbleiben eines PUT werden am echten Stack gemessen. Warten ausschließlich auf Zustände (`expect(...).toBe...`, `waitForResponse`, `expect.poll`), nie `waitForTimeout`.

**Filter A (Positivliste).** Alle geänderten Ziel-Specs enthalten weiterhin kein `waitForTimeout`, `test.skip`, `test.fixme` und `describe.skip`, und kein `.staging.spec`-Namensmuster. Die Positivliste und die Ratschen (`E2E_MIN_SPECS`, `E2E_MIN_EXECUTED_HAUPT`) bleiben unverändert; die Ziel-Specs wachsen nur (Ratsche darf nur wachsen), die gelöschten Alt-Specs standen nicht auf der Liste.

**Lösch-Nachweis-Test (Python, deterministisch, ohne Netz).** Prüft (a) die 8 Spec-Dateien und die 8 exklusiven Config-/Setup-Dateien existieren nicht, (b) keine `playwright*.config.ts` unter `frontend/` und `frontend/e2e/` nennt einen der 8 Dateinamen oder gelöschten Config-Namen (Textsuche in Config-Dateien als Verweiswächter, nicht als Verhaltensnachweis), (c) `playwright.1273-s4c.staging.config.ts` existiert und nennt `layout-tab-vergleich` nicht mehr, (d) jede der 10 übertragenen Zusicherungen existiert als benannter Testfall (`test(`-Titel mit der Kennung `WS-neu-N`, `AN-neu-N`, `KS-neu-N`, `DS-neu-1`) in der jeweiligen Ziel-Spec, (e) die Ziel-Specs stehen auf der Positivliste und erfüllen Filter A (kein `waitForTimeout`, `test.skip`, `test.fixme`, `describe.skip`).

## Expected Behavior

- **Input:** Repository-Stand nach der Pflege.
- **Output:** Die 8 Alt-Specs samt exklusiven Configs/Setups sind weg; die 10 noch geltenden Zusicherungen laufen als benannte Fälle in CI-gelisteten Specs grün gegen den echten Stack; Pin-Tests und Lösch-Nachweis grün.
- **Side effects:** keine für Nutzer; CI-Abdeckung wächst um 10 Fälle, Staging-Läufe verlieren 33 rote Altfälle.

## Test Plan

### Automated Tests (TDD RED)

- [ ] RED Lösch-Nachweis: GIVEN der Stand vor der Pflege WHEN `tests/unit/test_3374_tote_browserpruefungen_geloescht.py` läuft THEN rot (8 Dateien existieren, die 10 Fälle fehlen); nach der Pflege grün. Mutations-Gegenprobe: eine gelöschte Datei wieder anlegen bzw. einen Fall umbenennen macht den Test rot.
- [ ] WS-neu-1: GIVEN Wetter-Reiter eines Trips WHEN Vorschau-Spalte Roh bzw. Einfach gewählt und neu geladen THEN bleibt die Wahl gespeichert, Gewitter hat keinen Schalter.
- [ ] WS-neu-2: GIVEN Karte „Was steht wo“ WHEN per Tastatur zwischen Karten gewechselt wird THEN wird gespeichert; ein Klick auf die Überschrift löst keinen PUT aus.
- [ ] WS-neu-3: GIVEN der Katalog-Abruf wird mit Fehler beantwortet WHEN die Karte öffnet THEN erscheinen `was-steht-wo-fehler` und `was-steht-wo-erneut-laden`, und es geht kein PUT hinaus.
- [ ] WS-neu-4: GIVEN ein Vergleich WHEN die Stundenverlauf-Spalte betrachtet wird THEN steht dort nur „nur in der E-Mail“ und keine Kappungsaussage.
- [ ] WS-neu-5: GIVEN ein Trip mit Metriken, aber ohne Etappe mit 2 Wegpunkten WHEN Zustellung/Beispiel-Alarm geöffnet wird THEN erscheint `alert-preview-no-stages` ohne Wetterabruf.
- [ ] AN-neu-1/2: GIVEN Vergleich-Anlegen ohne Orte WHEN Zustellung angesteuert wird THEN gesperrt; GIVEN 390 px Breite WHEN Zustellung offen THEN kein horizontales Scrollen.
- [ ] KS-neu-1/2: GIVEN ein pausierter bzw. archivierter Trip im Hub WHEN eine Alarm-Einstellung in Zustellung geändert wird THEN Antwort 200, kein 412 durch eigenen Vorgänger.
- [ ] DS-neu-1: GIVEN eine Etappe WHEN die Startzeit geändert wird THEN wird mit If-Match gespeichert und der Wert bleibt nach Neuladen.
- [ ] Pin-Tests benannt: `tests/unit/test_2243_playwright_loeschscheibe.py`, `tests/tdd/test_compare_e2e_storagestate_migration.py`, `tests/unit/test_e2e_positivliste_ratschen_bindung.py` grün.
- [ ] Browser-Fälle: die vier geänderten Ziel-Specs laufen gegen den echten Stack (CI-Stack bzw. Staging) grün, mindestens dreimal in Folge ohne Flake.

## Acceptance Criteria

- **AC-1:** Given der Wetter-Reiter eines Trips mit Vorschau-Spalte / When der Nutzer Roh bzw. Einfach wählt und die Seite neu lädt / Then bleibt die Wahl gespeichert und Gewitter hat keinen Roh/Einfach-Schalter (übertragen aus epic-138 AC-5b).
  - Test: `was-steht-wo-karte.spec.ts` Fall `WS-neu-1` im echten Browser gegen den echten Stack.

- **AC-2:** Given die Karte „Was steht wo“ geöffnet / When der Nutzer per Tastatur die Karte wechselt bzw. nur auf eine Überschrift klickt / Then speichert der Kartenwechsel per Tastatur und der Überschrift-Klick löst keinen Schreibvorgang aus (übertragen aus autosave F003/F004).
  - Test: `was-steht-wo-karte.spec.ts` Fall `WS-neu-2`, Schreibvorgänge am Netzwerk gezählt.

- **AC-3:** Given der Katalog-Abruf der Karte schlägt fehl / When die Karte öffnet / Then zeigt sie den Fehler (`was-steht-wo-fehler`) mit „Neu laden“ (`was-steht-wo-erneut-laden`) und es wird nichts gespeichert (übertragen aus autosave AC-3).
  - Test: `was-steht-wo-karte.spec.ts` Fall `WS-neu-3`; Fehlerantwort per Route-Abfangen, kein PUT beobachtet.

- **AC-4:** Given ein Vergleich mit Stundenverlauf-Spalte / When die Spalte angezeigt wird / Then steht dort nur „nur in der E-Mail“ und keine Aussage über Kappung (übertragen aus hourly AC-3).
  - Test: `was-steht-wo-karte.spec.ts` Fall `WS-neu-4` im Kontext Vergleich.

- **AC-5:** Given ein Trip mit gewählten Metriken, aber ohne Etappe mit mindestens zwei Wegpunkten / When der Bereich `zustellung-beispiel-alarm` geöffnet wird / Then erscheint `alert-preview-no-stages` statt einer Vorschau und es erfolgt kein Wetterabruf (neu geschrieben aus fix-2069 a).
  - Test: `was-steht-wo-karte.spec.ts` Fall `WS-neu-5` mit Saat inklusive `display_config.metrics`.

- **AC-6:** Given das Anlegen eines Vergleichs ohne Orte / When der Nutzer den Reiter Zustellung ansteuert / Then bleibt er gesperrt (übertragen aus layout AC-4).
  - Test: `hub-anlegen-ablauf.spec.ts` Fall `AN-neu-1`.

- **AC-7:** Given der Reiter Zustellung beim Anlegen bei 390 px Breite / When er geöffnet wird / Then lässt sich die Seite nicht horizontal scrollen (übertragen aus layout AC-8).
  - Test: `hub-anlegen-ablauf.spec.ts` Fall `AN-neu-2`, Messung `scrollWidth <= clientWidth` im echten Browser.

- **AC-8:** Given ein pausierter oder archivierter Trip im Hub / When der Nutzer in Zustellung eine Alarm-Einstellung ändert / Then wird sie gespeichert (Antwort 200) ohne Selbst-412 (übertragen aus 1395 Fall 3/4).
  - Test: `hub-konfliktschutz-zwei-kontexte.spec.ts` Fälle `KS-neu-1` (Pausieren über Kebab) und `KS-neu-2` (Archivieren).

- **AC-9:** Given eine Etappe eines Trips / When die Startzeit geändert wird / Then wird sie mit If-Match gespeichert und bleibt nach Neuladen erhalten (übertragen aus 1395 Fall 5).
  - Test: `design-system-trip-vergleich.spec.ts` Fall `DS-neu-1`, Request-Header und Wert nach Reload geprüft.

- **AC-10:** Given die acht Alt-Specs (`epic-138-metriken-editor`, `weather-metrics-tab-autosave`, `compare-hourly-metric-order`, `layout-tab-vergleich`, `fix-2069-alert-preview-echte-segmente`, `feat-1395-s3-etag-ifmatch.staging`, `save-status-indicator-honesty`, `weather-metrics-editor-day-range-kuerzel`) und ihre exklusiven Configs und Setups / When die Pflege geliefert ist / Then existiert keine dieser Dateien mehr und keine `playwright*.config.ts` verweist auf eine davon.
  - Test: `tests/unit/test_3374_tote_browserpruefungen_geloescht.py` (deterministisch, ohne Netz; Architektur-Wächter, kein Verhaltensnachweis, das Verhalten belegen AC-1..AC-9).

- **AC-11:** Given `playwright.1273-s4c.staging.config.ts`, die von mehreren Specs geteilt wird / When `layout-tab-vergleich` gelöscht ist / Then bleibt die Config bestehen, nennt in `testMatch` nur noch die übrigen Specs, und alle dort verbleibenden Specs existieren.
  - Test: Lösch-Nachweis-Test (Block 1273-s4c) und `test_compare_e2e_storagestate_migration.py` grün.

- **AC-12:** Given die Pin-Tests `test_2243_playwright_loeschscheibe.py` und `test_compare_e2e_storagestate_migration.py` / When die Specs gelöscht sind / Then führen beide die gelöschten Dateien nicht mehr als lebend (`GEKUERZTE_SPECS`, `LEBENDE_FAELLE`, `BEHALTENE_SPECS`, `MIGRATED_FILES`) und sind grün; eine Mutation (gelöschte Spec wieder eintragen) macht sie rot.
  - Test: beide Dateien benannt per `uv run pytest <Datei>`; Mutations-Gegenprobe per String-Ersetzung mit externer Sicherungskopie.

- **AC-13:** Given jede der 10 übertragenen Zusicherungen / When der Nachweis läuft / Then existiert sie als benannter Testfall (`WS-neu-1..5`, `AN-neu-1..2`, `KS-neu-1..2`, `DS-neu-1`) in ihrer Ziel-Spec, und kein Fall wurde gestrichen, ohne in der Streichliste dieser Spec mit lebendem Ersatz zu stehen.
  - Test: Nachweis-Block (d) im Lösch-Nachweis-Test; Mutation „Fall umbenennen“ ergibt rot.

- **AC-14:** Given die vier geänderten Ziel-Specs auf der CI-Positivliste / When sie geprüft werden / Then enthalten sie kein `waitForTimeout`, `test.skip`, `test.fixme` und `describe.skip` (Filter A), stehen weiter auf `.github/ci_e2e_specs.txt`, und alle neuen Fälle laufen gegen den echten Stack grün, ohne Gate-Config zu ändern oder einen Override zu brauchen.
  - Test: Nachweis-Block (e) im Lösch-Nachweis-Test; Browser-Lauf der vier Specs im CI-Stack bzw. auf Staging dreimal in Folge grün; `test_e2e_positivliste_ratschen_bindung.py` grün.

- **AC-15:** Given der Verdacht „21 statt 9 Zeilen“ aus compare-hourly-metric-order AC-4 / When er gegen den Code geprüft wird / Then gilt das Verhalten als gewollt (Grundauswahl-Erbe seit #3047 H1) und es erfolgt keine Produktcode-Änderung; die Negativ-Zusicherung bleibt durch `hub-anlegen-ablauf.spec.ts` AN-12 bewacht.
  - Test: `git diff` gegen `main` zeigt keine Änderung unter `src/`, `api/`, `internal/`, `frontend/src/`; AN-12 bleibt grün.

## Definition of Done

- AC-1 bis AC-15 sind erfüllt, jedes AC hat einen grünen Test; keine übertragene Zusicherung gelockert.
- Die acht Alt-Specs samt exklusiver Configs/Setups sind gelöscht, keine Playwright-Config verweist mehr darauf.
- Pull Request mit allen 6 CI-Checks grün gemergt (die neuen Browser-Fälle laufen dort im `e2e`-Check), `/e2e-verify` gegen Staging bestanden, Prod-Deploy mit Selftest-Exit 0.

## Known Limitations

- WS-neu-3 fängt den Katalog-Abruf per Route-Abfangen ab, weil sich ein Katalog-Fehler am echten Stack nicht erzeugen lässt; alles andere läuft ohne Abfangen.
- Der genaue Anker für DS-neu-1 (Etappen-Startzeit) kann beim Schreiben technisch auf `hub-konfliktschutz-zwei-kontexte.spec.ts` ausweichen; das ändert keinen AC, das Nachweis-Test-Ziel wird dann mitgezogen und im Lieferbericht genannt.
- Die Staging-Zahlen (33 rote Altfälle) stammen aus dem Inventar-Lauf vom 26.11.2026 und werden nicht gepflegt.

## Out of Scope

- Waisen-Löschungen S1..S4 (#3383, #3384, #3385, #3366).
- Änderungen an Positivliste, `ci.yml`-Ratschen oder Hooks.
- Jede Produktänderung, auch zu „21 statt 9“.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Testpflege nach bestehender Entscheidung (Rückbau des Alt-Editors, #3122/#3164) und vorhandenem Muster (#2243, #3207 „Tests im selben Umbau mitentfernen“); keine neue Entscheidungsfläche.

## Changelog

- 2026-11-26: Initial spec created
