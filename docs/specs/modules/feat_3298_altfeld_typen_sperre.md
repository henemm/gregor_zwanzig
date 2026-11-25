---
entity_id: feat_3298_altfeld_typen_sperre
type: module
created: 2026-11-25
updated: 2026-11-25
status: draft
version: "1.0"
workflow: feat-3298-altfeld-typen-sperre
tags: [was-steht-wo, placements, rueckbau, frontend, sperre, epic-3122]
---

# Was steht wo B6b-4: Altfeld-Typen entfernen und Frontend-Sperre (#3298)

## Approval

- [ ] Approved

## Purpose

Im Frontend stehen noch die Namen der zehn Altfelder (`ALTFELDER` in `src/app/loader.py`) in Typen, Whitelists, Wizard-Zustand und im Ortsvergleich-Speichern, obwohl das Backend sie seit #3277 beim Schreiben verwirft und nie mehr liefert. Dieses Paket (#3298, Epic #3122, Spec AC-38 zweiter Teil) entfernt alle diese Namen samt dem toten Round-Trip (`outlook_enabled`, camelCase-Wizardfelder, Lese-Naht `channel_active_metrics`), löscht `hourlyFriendlyMap.ts` und schaltet eine dauerhafte Text-Scan-Sperre unter `node --test` scharf, damit kein Altname je wieder in den Frontend-Produktionscode gelangt. Für Nutzer ändert sich nichts Sichtbares.

## Source

- **File:** `frontend/src/lib/types.ts`, `frontend/src/lib/components/shared/pickEigenfelder.ts`, `frontend/src/lib/components/compare/compareEditorSave.ts`, `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts`, `frontend/src/lib/altfeld_namen_sperre.test.ts`
- **Identifier:** `WETTER_DISPLAY_KEYS`, `hydrateLayoutFieldsFromPreset`, `hydrateChannelActiveMetricsFromPreset`, `LayoutSnapshot`, `ComparePreset`, `DisplayConfig`

> **Schicht-Hinweis:** Nur Frontend (`frontend/src`, `frontend/e2e`) und Doku. Kein Go-, kein Python-Eingriff, kein Datenlauf (#3351). Das Backend verwirft Altfelder bereits beim Speichern (`src/app/loader.py`, `ALTFELDER`, #3277); die Python-Sperre `tests/test_altfeld_namen_sperre.py` bleibt unverändert.

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung (Gate):** Es entsteht keine neue Komponente und kein Pendant. Entfernt wird toter Code in geteilten und Vergleich-eigenen Modulen; Trip-Pfad und Vergleich-Pfad laufen weiter über denselben Code.
> - **Mandantentrennung:** Kein neuer datenbewegender Endpoint; Nutzlast-Tests laufen mit dem Go-Merge-Fake für zwei verschiedene Nutzer, `user_id` kommt aus dem Auth-Kontext, nie `"default"`.
> - **Kanäle:** E-Mail, Telegram, SMS und Premium-SMS sind nicht berührt (Ausgabe entsteht im Backend aus `placements`).
> - **Altschlüssel nur weglassen, nie leer senden, nie löschen:** Go ersetzt Top-Level-Werte (`internal/handler/config_merge.go`); Bestandsdaten bleiben per Read-Modify-Write-Merge erhalten, aufgeräumt werden sie vom Datenlauf #3351.

## Estimated Scope

- **LoC:** Produktion ca. -250/+30 (fast nur Löschungen), neuer Sperr-Test ca. +150, Testanpassungen ca. ±150
- **Files:** ca. 11 Produktionsdateien geändert, 1 gelöscht (`hourlyFriendlyMap.ts`), 1 neuer Test, 6 bis 10 bestehende Tests/Prüfstände angepasst
- **Effort:** mittel (ein Durchlauf; überwiegend Löschungen, ein neuer Test)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `feat_3277_altfelder_entfernen` | Spec | Backend verwirft/liefert Altfelder nicht mehr; Vorbild der Sperre |
| `feat_3276_vergleich_altfelder_entfernen` | Spec | Vorbild Nutzlast-Test Vergleich |
| `feat_3297_trip_pfad_ohne_altfelder` | Spec | Trip-Pfad bereits bereinigt (live) |
| `feat_3122_was_steht_wo` | Spec | Epic-Spec, AC-38 zweiter Teil |
| ADR-0124 Nr. 5, Nr. 6 | ADR | `placements` einzige Quelle; `outlook_reports` ersetzt `outlook_enabled` |
| `src/app/loader.py` (`ALTFELDER`) | Python | Quelle der zehn Namen; Abgleich im Sperr-Test |
| `tests/test_altfeld_namen_sperre.py` | Test | Vorbild (ERLAUBT-Tabelle, Selbstnachweis) |
| `frontend/src/lib/issue_523_suggested_flag_cleanup.test.ts` | Test | Vorbild `node:test` mit `readFileSync` |
| `internal/handler/config_merge.go` | Go | Flaches Merge: Altschlüssel weglassen, nie leer senden |
| Issues #3298, #3020 (geschlossen), #3301, #3351, #3366 | Issues | Paket / Folgeschritte |

## Scope

### Entscheidungen (Tech Lead, verbindlich)

- Entfernt werden alle Altfeld-Namen aus `ALTFELDER` aus dem Frontend-Produktionscode, `multi_day_trend_morning/evening` zusätzlich nur aus dem Typ (nicht in der Sperre, da nicht in `ALTFELDER`).
- Der camelCase-Wizardzustand (`outlookEnabled`, `hourlyMetricKeys`, `outlookMetricKeys`, `outlookMetricFormats`, `hourlyMetricFormats`) entfällt, soweit ohne Wirkung; sonst bliebe `outlook_enabled` als toter Round-Trip im PUT.
- Die Lese-Naht `channel_active_metrics` (`hydrateChannelActiveMetricsFromPreset`, `compareChannelActiveMetricsFromStored`) entfällt; das Backend liefert den Schlüssel nicht mehr.
- `hourlyFriendlyMap.ts` wird hier gelöscht (#3020 ist geschlossen, R2 entfällt).
- Die ERLAUBT-Tabelle der Sperre startet leer; `hourly_metrics` erhält keine Ausnahme; `hourly_enabled` gehört nicht zu den Altnamen.
- Verwaiste Module ohne Altfeld-Bezug werden NICHT hier aufgeräumt (Issue #3366).

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/types.ts` | MODIFY | `channel_layouts`, `channel_layouts_per_report`, `outlook_metrics`, `outlook_metric_formats`, `multi_day_trend_morning/evening` aus `DisplayConfig`/`ReportConfig`; `outlook_enabled` aus `ComparePreset`; Kommentar am `display_config` ohne Altnamen; Typen `ChannelLayouts`/`ChannelLayoutsPerReport` nur löschen, wenn sonst ungenutzt |
| `frontend/src/lib/components/shared/pickEigenfelder.ts` | MODIFY | `WETTER_DISPLAY_KEYS` auf `metrics, preset_name, telegram_kurzform, show_night_block, ampel` |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | MODIFY | `outlookEnabled` aus Edits, Body-Spread, Teilfeld-Body, Wizard-Feldsatz; camelCase-Wizardfelder raus; Kommentare ohne Altnamen |
| `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts` | MODIFY | `hydrateLayoutFieldsFromPreset`, `LayoutSnapshot`, Flush, Rollback, `WETTER_TOP` nur noch `hourlyEnabled`; `hydrateChannelActiveMetricsFromPreset` entfernt |
| `frontend/src/lib/components/shared/weather-metrics-tab/compareChannelMetricLayouts.ts` | MODIFY | Lese-Naht `compareChannelActiveMetricsFromStored` und Altnamen in Kommentaren raus |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | Hydration ohne `outlookEnabled` und ohne `channel_active_metrics` |
| `frontend/src/lib/components/compare-new/compareNewVorlage.ts` | MODIFY | Hydration beim Anlegen aus Vorlage ohne Altfelder |
| `frontend/src/lib/components/shared/alarmeVergleichSpeicherung.ts` | MODIFY | ohne `preset.outlook_enabled` / `outlookEnabled` |
| `frontend/src/lib/components/shared/versandVergleichSpeicherung.ts` | MODIFY | dito |
| `frontend/src/lib/components/shared/wetter-tab/wertebereicheVergleichSpeicherung.ts` | MODIFY | dito |
| `frontend/src/lib/components/compare/subscriptionHelpers.ts`, `shared/alarme-tab/alarmeDeliveryPayload.ts`, `utils/cockpitHelpers568.ts` | MODIFY | nur Kommentare ohne Altnamen |
| `frontend/src/lib/components/compare/hourlyFriendlyMap.ts` | DELETE | ohne Produktionsaufrufer; nur Test `compare_hourly_metric_formats_persistenz.test.ts` |
| `frontend/src/lib/altfeld_namen_sperre.test.ts` | CREATE | dauerhafte Text-Scan-Sperre mit Selbstnachweis und Abgleich gegen `ALTFELDER` |
| Prüfstände und Tests (`goMergeServerPruefstand.ts`, `versandVergleichPruefstand.ts`, `wetterMetrikenVergleichPruefstand.ts`, `compareEditorHourly*.test.ts`, `compare_hourly_metric_formats_persistenz.test.ts` u. a.) | MODIFY/DELETE | Erwartungen auf entfernte APIs nachziehen; Fixtures dürfen Altnamen behalten |
| `docs/specs/modules/feat_3122_was_steht_wo.md` | MODIFY | Nachtrag AC-38: zweiter Teil erledigt |

### Test-Zuordnung (Löschen nur mit Begründung)

- **Löschen:** nur Tests zu gelöschten oder entfernten Pfaden (`hourlyFriendlyMap.ts`, `hydrateChannelActiveMetricsFromPreset`, `compareChannelActiveMetricsFromStored`, `outlookEnabled`-Round-Trip). Jede gelöschte Testdatei wird im Commit-Text der entfernten Produktionsfunktion zugeordnet.
- **Umstellen:** Tests der Live-Funktionen (Ortsvergleich speichern, Hydration, Prüfstände): Altfeld-Erwartung wird durch „Schlüssel fehlt“ ersetzt.
- **Grenzfall:** Tests mit gemischtem Inhalt werden auf den Live-Teil gekürzt, nicht gelöscht.

### Estimated Changes

- Files: ca. 11 Produktionsdateien geändert, 1 gelöscht, 1 neu (Test), 6 bis 10 Tests angepasst
- LoC: Produktion ca. -250/+30, Sperr-Test ca. +150, Testanpassungen ca. ±150

### Nicht in dieser Spec

- Verwaiste Module ohne Altfeld-Bezug (über 40 Dateien): Issue #3366.
- Datenlauf auf Bestandsdaten: #3351.
- Änderungen an Backend, Go-Merge oder `tests/test_altfeld_namen_sperre.py`.

## Implementation Details

**Schritt 1, Sperre zuerst (RED):** `altfeld_namen_sperre.test.ts` nach Vorbild `tests/test_altfeld_namen_sperre.py`. Dateimenge: rekursiv `frontend/src`, `.ts/.svelte/.js`, ohne `__tests__/`, `*.test.ts`, `*Pruefstand.ts`, `*Anker.ts` und Hilfsdateien der Wächterregeln. Vor dem Scan werden Kommentare (`//`, `/* */`, `<!-- -->`) entfernt; Treffer wortgenau (`\bname\b`, snake_case) auf die zehn Namen aus `ALTFELDER` (`channel_layouts`, `channel_layouts_per_report`, `outlook_metrics`, `outlook_metric_formats`, `hourly_metrics`, `hourly_metric_formats`, `outlook_enabled`, `channel_active_metrics`, `show_outlook`, `multi_day_trend_reports`). ERLAUBT = `{(Datei, Name): (Grund ≥ 20 Zeichen, Ablaufdatum)}`, startet leer; abgelaufener Eintrag oder zu kurzer Grund macht rot. Auf dem Ist-Stand ist die Sperre rot.

**Schritt 2, Selbstnachweis und Abgleich:** Die Scan-Funktion ist testbar (synthetischer Quelltext): Verstoß erkannt, Name im Kommentar kein Treffer, `hourly_enabled` kein Treffer, gültiger ERLAUBT-Eintrag besteht, abgelaufener Eintrag schlägt an, zu kurzer Grund abgelehnt. Zusätzlich liest der Test `ALTFELDER` aus `src/app/loader.py` und verlangt Gleichheit mit seiner Namensliste, damit beide nicht auseinanderlaufen.

**Schritt 3, Bereinigung (GREEN, nur weglassen):** Typen in `types.ts`; `WETTER_DISPLAY_KEYS`; in `weatherMetricsCompareSave.ts` Layout-Hydration, Snapshot, Flush, Rollback und `WETTER_TOP` auf `hourlyEnabled` kürzen und `hydrateChannelActiveMetricsFromPreset` samt Lese-Naht entfernen (Aufrufer `CompareTabs.svelte`, `compareNewVorlage.ts`); in `compareEditorSave.ts` `outlookEnabled` und die camelCase-Wizardfelder aus Edits, Feldsatz und Body entfernen; die drei `*VergleichSpeicherung.ts` ohne `outlookEnabled`. Bestandswerte laufen nur noch über den `...baseDisplayConfig`-Spread und bleiben so erhalten; es wird nie `delete` oder ein leerer Wert gesendet.

**Schritt 4, Löschen und Nachziehen:** `hourlyFriendlyMap.ts` nach Grep-Gate (kein Produktionsimport) löschen; Tests und Prüfstände nach Test-Zuordnung anpassen (u. a. Erwartung `goMergeServerPruefstand.ts` zu `outlook_enabled`).

**Schritt 5, Nachweis:** Nutzlast-Test Ortsvergleich speichern (Wertebereiche, Layout, Versand, Alarme, Anlegen aus Vorlage) gegen den Go-Merge-Fake für zwei Nutzer: kein Altschlüssel im POST/PUT; Bestand bleibt nach Merge erhalten; Ausblick über `placements.outlook_reports` unverändert. Adversary-Mutation: Altname in eine Produktionsdatei einfügen, die Sperre muss rot werden.

## Expected Behavior

- **Input:** Ortsvergleich anlegen (auch aus Vorlage), Ortsvergleich-Reiter speichern, Trip speichern, Seiten öffnen.
- **Output:** Kein Request-Body enthält einen der zehn Altnamen; die Hydration liest sie nicht. Frontend-Typen kennen sie nicht. Neue Altnamen im Produktionscode machen die Sperre rot.
- **Side effects:** Keine sichtbare Änderung in Editor, Mail oder Kanälen (DE und EN). Bestandsdaten bleiben bis #3351 unberührt auf der Platte.

## Acceptance Criteria

- **AC-1:** Given die Typen `DisplayConfig`, `ReportConfig` und `ComparePreset` / When das Frontend mit `svelte-check` geprüft wird / Then kennen die Typen keinen der zehn Altfeld-Namen und kein `multi_day_trend_morning/evening` mehr, und `svelte-check` meldet keinen Fehler.
  - Test: `svelte-check` grün; Sperr-Test ohne Treffer in `types.ts`.

- **AC-2:** Given ein Ortsvergleich wird angelegt oder in einem Reiter (Wertebereiche, Layout, Versand, Alarme) gespeichert / When der Speicher-Request an die API gesendet wird / Then enthält der Body keinen der zehn Altschlüssel (weder gefüllt noch leer), insbesondere kein `outlook_enabled`, und alle übrigen Bestandsfelder bleiben nach dem Go-Merge erhalten.
  - Test: Nutzlast-Test (node --test) über die echte Speicherlogik gegen `goMergeServerPruefstand` mit zwei verschiedenen Nutzern; Bestand vorher/nachher ohne Datenverlust; E2E prüft den echten Request-Body.

- **AC-3:** Given ein gespeicherter Ortsvergleich oder eine Vorlage, deren Daten noch Altfelder tragen / When der Editor hydriert wird (`CompareTabs`, Anlegen aus Vorlage) / Then liest die Hydration weder `outlook_enabled` noch `channel_active_metrics` oder die Layout-Altfelder, der Ausblick folgt `placements.outlook_reports`, und der Editor zeigt dieselben Werte wie zuvor.
  - Test: node-Test der Hydrationsfunktionen mit Altfeld-Fixture (Altwerte ändern das Ergebnis nicht); Playwright-E2E auf Staging: Ortsvergleich öffnen, Werte stehen.

- **AC-4:** Given `WETTER_DISPLAY_KEYS` in `pickEigenfelder.ts` / When ein Wetter-Reiter-Body gebaut wird / Then enthält die Whitelist nur `metrics`, `preset_name`, `telegram_kurzform`, `show_night_block`, `ampel`, und kein Altname wird übernommen, auch wenn er in den Eingabedaten steht.
  - Test: `pick_eigenfelder_kernregel.test.ts` (node --test) mit Eingabe, die Altnamen enthält; Ergebnis ohne sie.

- **AC-5:** Given jemand fügt einen der zehn Altnamen in eine Produktionsdatei unter `frontend/src` ein / When die Sperre `altfeld_namen_sperre.test.ts` läuft / Then wird sie rot und nennt Datei und Namen; Namen in Kommentaren, `hourly_enabled` sowie Tests und Prüfstände lösen nichts aus.
  - Test: Sperr-Test (node --test) auf dem echten Baum grün, auf dem Ist-Stand vor der Bereinigung rot (RED-Nachweis); Adversary-Mutation mit Altname in einer Produktionsdatei macht ihn rot.

- **AC-6:** Given die Sperre mit leerer ERLAUBT-Tabelle / When ihr Selbstnachweis mit synthetischem Quelltext läuft / Then erkennt er einen Verstoß, ignoriert Kommentar-Treffer und `hourly_enabled`, akzeptiert einen gültigen Eintrag (Grund ≥ 20 Zeichen, Ablaufdatum in der Zukunft) und schlägt bei abgelaufenem Eintrag oder zu kurzem Grund an.
  - Test: Selbstnachweis-Fälle im selben Testfile (node --test), je Fall eine Prüfung.

- **AC-7:** Given die Namensliste der Sperre und die Liste `ALTFELDER` in `src/app/loader.py` / When der Sperr-Test läuft / Then sind beide Mengen identisch (zehn Namen), und eine Abweichung macht den Test rot.
  - Test: Abgleich im Sperr-Test (node --test) durch Einlesen von `loader.py`; Gegenprobe mit synthetisch abweichender Liste.

- **AC-8:** Given `hourlyFriendlyMap.ts` ohne Produktionsaufrufer / When der Rückbau abgeschlossen ist / Then existiert die Datei nicht mehr, keine Produktionsdatei importiert sie, und `vite build` sowie `svelte-check` laufen ohne unaufgelöste Importe.
  - Test: `vite build` und `svelte-check` grün; Import-Freiheit durch Grep-Gate dokumentiert (kein Dateiinhalt-Check als Verhaltensnachweis).

- **AC-9:** Given ein Nutzer bedient Ortsvergleich (anlegen, Reiter Wertebereiche/Layout/Versand/Alarme speichern) und Trip auf Staging, in Deutsch und Englisch / When er wie bisher speichert und neu lädt / Then sieht und bedient er dieselben Flächen wie vor dem Rückbau, und alle Werte inklusive Ausblick bleiben nach dem Neuladen erhalten.
  - Test: Playwright-E2E gegen Staging (DE und EN): Ortsvergleich und Trip anlegen, Reiter ändern, speichern, neu laden, Werte stehen; Request-Body ohne Altschlüssel.

- **AC-10:** Given Tests, die entfernte Pfade prüften / When der Rückbau abgeschlossen ist / Then ist jede gelöschte Testdatei einer gelöschten oder entfernten Produktionsfunktion zugeordnet, alle übrigen sind auf „Schlüssel fehlt“ umgestellt, und die Kern-Schicht (Frontend `node --test` benannter Dateien, `svelte-check`, Playwright-Kern) ist grün.
  - Test: Diffstatistik der Validierung ordnet jede gelöschte Testdatei einer entfernten Produktionsfunktion zu; die Zuordnung steht im Commit-Text; betroffene Testdateien einzeln benannt grün.

## Definition of Done

- AC-1 bis AC-10 durch Kern-Tests ohne Mock grün (`node --test` benannte Dateien, `svelte-check`, `vite build`).
- Sperre `altfeld_namen_sperre.test.ts` erst rot (Ist-Stand), dann grün; Adversary-Mutation und Mutations-Gegenprobe belegen sie.
- Nutzlast-Test beweist: kein Altschlüssel im Vergleich-POST/PUT, Bestand bleibt erhalten, zwei Nutzer.
- Grep-Gate für `hourlyFriendlyMap.ts` dokumentiert; Test-Zuordnung eingehalten.
- Staging: `/e2e-verify` mit Request-Body-Prüfung und Bedienung DE/EN grün.
- Live auf Produktion, Selftest Exit 0; danach #3298 schließen. Epic #3122 nicht schließen. Keine Änderung an Gate-Konfiguration.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN Ist-Stand WHEN Sperr-Test läuft THEN rot mit Fundstellen der Altnamen (AC-5)
- [ ] Test 2: GIVEN synthetischer Quelltext WHEN Selbstnachweis THEN Verstoß erkannt, Kommentar und `hourly_enabled` nicht, Ablauf und kurzer Grund schlagen an (AC-6)
- [ ] Test 3: GIVEN Namensliste und `ALTFELDER` WHEN Abgleich THEN identisch, Abweichung rot (AC-7)
- [ ] Test 4: GIVEN Ortsvergleich-Speichern WHEN Body gebaut über Go-Merge-Fake, zwei Nutzer THEN kein Altschlüssel, Bestand erhalten (AC-2)
- [ ] Test 5: GIVEN Preset/Vorlage mit Altfeldern WHEN Hydration THEN Altwerte ohne Wirkung (AC-3)
- [ ] Test 6: GIVEN Eingabe mit Altnamen WHEN `pickEigenfelder` Wetter THEN nur die fünf erlaubten Schlüssel (AC-4)
- [ ] Test 7: GIVEN bereinigte Typen WHEN `svelte-check` und `vite build` THEN grün, `hourlyFriendlyMap.ts` ohne Importe (AC-1, AC-8)
- [ ] Test 8: GIVEN Staging WHEN Ortsvergleich und Trip bedient (E2E, DE/EN) THEN gleiche Flächen, Werte bleiben, Body ohne Altschlüssel (AC-9)
- [ ] Test 9: GIVEN umgestellte Tests WHEN benannte Testdateien laufen THEN grün, Zuordnung vollständig (AC-10)

Test-Politik: kein Mock-Theater, Frontend-Unit mit `node --test`, Playwright-E2E wo sichtbar. Dateiinhalt-Scan nur für die Sperre selbst (`# doc-compliance-test`). Die Live-Schicht läuft in `/e2e-verify`.

## Known Limitations

- Bestandsdaten mit Altfeldern bleiben bis zum Datenlauf (#3351) wirkungslos auf der Platte; das Frontend trägt sie nur per Spread weiter.
- Die Sperre erfasst nur snake_case-Namen der zehn `ALTFELDER`; camelCase-Reste werden durch die Bereinigung entfernt, aber nicht gescannt.
- Verwaiste Module ohne Altfeld-Bezug bleiben bis #3366.
- Merge-Konflikte mit parallelen Vergleich-Änderungen möglich; Reihenfolge: #3297 und #3301 sind bereits live.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue (ADR-0124 Nr. 5 und Nr. 6)
- **Rationale:** ADR-0124 hat entschieden, dass `placements` die einzige Quelle ist und `outlook_reports` `outlook_enabled` und `show_outlook` ersetzt. Dieses Paket vollzieht den Frontend-Rückbau und die dauerhafte Sperre ohne Verhaltensänderung und widerspricht keiner früheren Entscheidung; die Sperre spiegelt das Backend-Muster aus #3277.

## Changelog

- 2026-11-25: Initial spec created (B6b-4, Issue #3298, Epic #3122).
