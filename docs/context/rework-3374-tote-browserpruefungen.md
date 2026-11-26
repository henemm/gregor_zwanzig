# Context: rework-3374-tote-browserpruefungen

## Request Summary
Issue #3374 (Epic #3122, aus #3164 Punkt D): Playwright-Specs außerhalb der CI-Positivliste, die seit dem
Rückbau des Alt-Editors (Wetter-Reiter `weather-metrics-tab`/`wm2-grundauswahl`, alte Compare-Layout-Flächen)
nichts mehr bewachen. Je Fall: auf die Karte „Was steht wo“ bzw. den heutigen Ort neu schreiben oder streichen.
`compare-hourly-metric-order` AC-4 („21 statt 9 Zeilen“) zuerst als möglichen echten Fehler prüfen.
#3366 (verwaiste Alt-Editor-Bausteine) ist bereits geschlossen.

## Bereits erledigt (nicht mehr vorhanden)
- `compare-neu-kanal-anlegen.staging.spec.ts` gelöscht mit #3333 (600cb31b0)
- `issue-88-report-config-dialog.spec.ts` gelöscht mit #3207 (89d093a6a)
- `issue-932-activity-type-route-tab.spec.ts` gelöscht mit #3196 (e089d39a2)

## AC-4 „21 statt 9“: kein Produktfehler
Seit #3047 H1 leitet ein Vergleich ohne eigene Stundenverlauf-Auswahl die Stundenzeilen aus der Grundauswahl
ab (nur Metriken mit Stundenspalte); ein neuer Vergleich erbt die Grundauswahl aus der Vorlage → 21 Zeilen sind
gewollt. Fester 9er-Default `HOURLY_DEFAULT_METRIC_IDS` nur, wenn auch die Grundauswahl nie gesetzt wurde.
Belege: `src/output/renderers/compare_hourly_metric_ids.py:105-117`, `:240-263` (`_standard_aus_grundauswahl`),
Aufruf `src/services/placements.py:338`. Die alte Liste auf `/compare/new` ist mit #3276 entfernt; heutiges AC-4 ist
eine Negativ-Zusicherung (grün), doppelt zu `hub-anlegen-ablauf.spec.ts` AN-12 (CI).

## Staging-Lauf (26.11.2026, Inventar-Agent)
| Datei | grün / rot | Grund |
|---|---|---|
| epic-138-metriken-editor | 1 / 7 | `weather-metrics-tab`, `wm2-grundauswahl`, `weather-preset-pill-*` fehlen |
| weather-metrics-tab-autosave | 2 / 4 | `weather-metrics-tab`, `weather-metrics-load-error` fehlen |
| compare-hourly-metric-order | 2 / 0 | – (seit #3276/#3359 umgeschrieben) |
| layout-tab-vergleich | 4 / 0 | – (seit #3276 umgeschrieben) |
| fix-2069-alert-preview-echte-segmente | 0 / 2 | Saat ohne `display_config.metrics` → „Keine alert-fähigen Wetter-Metriken“; Fläche existiert |
| feat-1395-s3-etag-ifmatch.staging | 1 / 5 | Fall 1 `weather-metrics-tab`; Fall 2–4 `alarme-tab` (im Hub entfallen) |
| save-status-indicator-honesty | 0 / 3 | `weather-metrics-tab`, `versand-abschnitt` fehlen |
| weather-metrics-editor-day-range-kuerzel | 0 / 4 | `weather-metrics-tab(-vergleich)` fehlt |

## Einzelfall-Inventar (Empfehlung)
| Test | Zusicherung | Ersatz heute | Empfehlung |
|---|---|---|---|
| epic138 AC-1/2/3/4/6/7/10 | Editor sichtbar, Toggles, Preset-Pills, Autosave, Reload | was-steht-wo-karte WS-1/WS-B4, epic-138-block-b, hub-wetter-metriken MS-1/MS-6, hub-save-chip SC-2, speicherung-ueberlebt-neuladen AC-4 (CI) | streichen |
| epic138 AC-5b | Vorschau-Spalte Roh/Einfach gespeichert, Gewitter ohne Schalter | WS-3 nur teilweise | in was-steht-wo-karte übertragen |
| autosave AC-1/2/4/5/6 | Öffnen schreibt nichts, leer persistiert, Hinzufügen/Schwelle speichert | GG-1, SC-1b, MS-1, MS-6, hub-wertebereiche-speichert-selbst (CI) | streichen |
| autosave AC-3 | Katalog-Fehler zeigt Fehler + Neu laden, kein PUT | nur Unit `was_steht_wo_karte.test.ts` | neu auf Karte (`was-steht-wo-fehler`/`-erneut-laden`) |
| autosave F003/F004 | Kartenwechsel per Tastatur speichert; Überschrift-Klick speichert nichts | – | in was-steht-wo-karte übertragen |
| hourly AC-3 | Stundenverlauf-Spalte nur „nur in der E-Mail“, keine Kappung | – | in was-steht-wo-karte übertragen (Vergleich) |
| hourly AC-4 | /compare/new ohne eigene Stundenliste | hub-anlegen-ablauf AN-12 (CI) | streichen |
| layout AC-7/AC-11 | Zustellung ohne Stundenregler/Kanal-Tabs/Vorschau | AN-12 (CI) | streichen |
| layout AC-4 | Ohne Orte bleibt Zustellung gesperrt | AN-1/AN-5 teilweise | in hub-anlegen-ablauf übertragen |
| layout AC-8 | Zustellung bei 390 px ohne Querscrollen | issue-682 nur erster Schritt | in hub-anlegen-ablauf übertragen |
| fix2069 (a) | Trip ohne 2-Wegpunkt-Etappe zeigt `alert-preview-no-stages`, kein Fetch | nur Unit | neu: Saat mit Metriken, Bereich `zustellung-beispiel-alarm` |
| fix2069 (b) | Geplanter Trip zeigt Beispiel-Alarm | WS-16 (CI) | streichen |
| 1395 Fall 1/2 | Zwei Schreibvorgänge, 412 bei Fremdänderung | MS-1, KS-1, MS-5, VS-2 (CI) | streichen |
| 1395 Fall 3/4 | Nach Pausieren/Archivieren speichert Alarm-Einstellung ohne Selbst-412 | nicht abgedeckt | neu: Kebab Pause/Archiv, dann Alarm in Zustellung ändern, 200 |
| 1395 Fall 5 | Etappen-Startzeit mit If-Match gespeichert | nicht abgedeckt | in lebende Spec übertragen |
| 1269 AC-1..4 | Öffnen hält Chip idle, kein PUT | GG-1, SC-1, SC-1b (CI) | streichen |
| 1728 AC-1..9 | Kürzelzeilen in „04 — Schwellwerte“, Aggregationen | Fläche entfallen; AN-12 kehrt AC-9 um | streichen |

## Related Files
| Datei | Relevanz |
|---|---|
| `frontend/e2e/{8 Specs oben}` | löschen bzw. Fälle übertragen |
| `frontend/e2e/was-steht-wo-karte.spec.ts`, `was-steht-wo.helpers.ts` | Ziel für übertragene Karten-Fälle |
| `frontend/e2e/hub-anlegen-ablauf.spec.ts` | Ziel für Anlege-Fälle (layout AC-4/AC-8) |
| `.github/ci_e2e_specs.txt` | Positivliste (Ratsche, darf nur wachsen) – neue/übertragene Fälle sollten in CI-gelisteten Dateien landen |
| `frontend/playwright.1234.staging.config.ts`, `e2e/feat-1234.staging.setup.ts` | nur von autosave genutzt → mit löschen |
| `frontend/playwright.1269.staging.config.ts`, `e2e/feat-1269-save-status-lie.staging.setup.ts` | nur von 1269 → mit löschen |
| `frontend/e2e/playwright.feat-1395-s3.staging.config.ts`, `e2e/feat-1395-s3-etag-ifmatch.staging.setup.ts` | nur von 1395 → mit löschen |
| `frontend/playwright.compare-hourly-metric-order.staging.config.ts`, `e2e/compare-hourly-metric-order.staging.setup.ts` | nur von hourly → mit löschen |
| `frontend/playwright.1273-s4c.staging.config.ts` | geteilt; nur `layout-tab-vergleich` aus `testMatch` entfernen |
| `tests/unit/test_2243_playwright_loeschscheibe.py` | pinnt epic-138 (`GEKUERZTE_SPECS`, `LEBENDE_FAELLE`, Z. 224) und layout-tab-vergleich (`BEHALTENE_SPECS`) → anpassen |
| `tests/tdd/test_compare_e2e_storagestate_migration.py` | `MIGRATED_FILES` enthält layout-tab-vergleich + 1273-s4c-Config → anpassen |

## Existing Patterns
- Löschscheiben mit Nachweis-Test: #2243 (`test_2243_playwright_loeschscheibe.py`), #3207 (Regel „Tests im selben Umbau mitentfernen“), #3384 Waisen-Wächter.
- Karten-Specs nutzen `oeffneKarte()` aus `was-steht-wo.helpers.ts`, Login per storageState.

## Risks & Considerations
- Positivliste ist Ratsche (nur wachsen): Löschen nicht gelisteter Dateien unkritisch; übertragene Fälle in gelistete Dateien erhöhen CI-Abdeckung, müssen dort aber im isolierten CI-Stack grün laufen.
- Neu geschriebene Fälle (Pause/Archiv-Alarm, Fehlerzustand, Startzeit) brauchen eigene Saat; Zwei-Nutzer-Regel gilt nicht (keine Datenbewegungs-Endpoints neu).
- Keine Produktänderung; reine Testpflege.

## Analysis

### Type
Feature (Testpflege, keine Produktänderung). Der vermutete Fehler (AC-4 „21 statt 9“) ist widerlegt: gewolltes Verhalten seit #3047 H1.

### Technical Approach
Grundsatz: Eine Zusicherung, die heute noch gilt und nirgends lebend bewacht ist, wandert in eine **CI-gelistete** lebende Spec
(alle Ziele stehen in der Positivliste); alles andere wird gestrichen. Danach werden die 8 Alt-Dateien samt exklusiver
Configs/Setups gelöscht und die beiden Python-Pin-Tests nachgezogen.

| Zusicherung (Herkunft) | Ziel-Spec (CI) | Neuer Fall |
|---|---|---|
| Vorschau-Spalte Roh/Einfach wird gespeichert, Gewitter ohne Schalter (epic138 AC-5b) | `was-steht-wo-karte.spec.ts` | WS-neu |
| Kartenwechsel per Tastatur speichert; Klick auf Überschrift speichert nichts (autosave F003/F004) | `was-steht-wo-karte.spec.ts` | WS-neu |
| Katalog-Fehler zeigt Fehler + „Neu laden“, kein PUT (autosave AC-3) | `was-steht-wo-karte.spec.ts` (Route-Abfangen des Katalogs) | WS-neu |
| Stundenverlauf-Spalte im Vergleich: nur „nur in der E-Mail“, keine Kappungsaussage (hourly AC-3) | `was-steht-wo-karte.spec.ts` | WS-neu |
| Beispiel-Alarm: Trip ohne Etappe mit 2 Wegpunkten zeigt Hinweis statt Vorschau, kein Abruf (fix2069 a) | `was-steht-wo-karte.spec.ts` bzw. Zustellung-Beispiel-Alarm | WS-neu |
| Ohne Orte bleibt Reiter Zustellung beim Vergleich-Anlegen gesperrt (layout AC-4) | `hub-anlegen-ablauf.spec.ts` | AN-neu |
| Zustellung bei 390 px ohne Querscrollen (layout AC-8) | `hub-anlegen-ablauf.spec.ts` | AN-neu |
| Nach Pausieren bzw. Archivieren im Hub speichert eine Alarm-Änderung in Zustellung ohne 412 (1395 Fall 3/4) | `hub-konfliktschutz-zwei-kontexte.spec.ts` | KS-neu |
| Etappen-Startzeit wird mit If-Match gespeichert und bleibt nach Neuladen (1395 Fall 5) | lebende Etappen-Spec (z. B. `issue-675-stage-start-time.spec.ts`, sonst Hub-Spec in CI) | neu |

Löschen: `epic-138-metriken-editor`, `weather-metrics-tab-autosave`, `compare-hourly-metric-order`, `layout-tab-vergleich`,
`fix-2069-alert-preview-echte-segmente`, `feat-1395-s3-etag-ifmatch.staging`, `save-status-indicator-honesty`,
`weather-metrics-editor-day-range-kuerzel` (je .spec.ts) + exklusive Configs/Setups (Liste oben). `playwright.1273-s4c.staging.config.ts`:
nur `layout-tab-vergleich` aus `testMatch`. Pin-Tests: `tests/unit/test_2243_playwright_loeschscheibe.py`,
`tests/tdd/test_compare_e2e_storagestate_migration.py` auf den neuen Stand. Lösch-Nachweis-Test (Dateien weg, keine Config verweist mehr darauf).

### Scope Assessment
- Dateien: ~8 Specs + 8 Config/Setup löschen, 4–5 Specs erweitern, 2 Python-Tests anpassen, 1 Config anpassen
- LoC: ca. +350 / −2.300
- Risiko: niedrig (nur Tests); Hauptrisiko: neue Fälle müssen im isolierten CI-E2E-Stack grün laufen (keine Wartezeiten mit waitForTimeout, Filter A der Positivliste).

### Open Questions
- keine Produktfrage; Freigabe nur über die Spec.
