---
entity_id: feat_3276_vergleich_altfelder_entfernen
type: module
created: 2026-11-23
updated: 2026-11-23
status: draft
version: "1.0"
workflow: b6b2-3276-altfelder-frontend
tags: [was-steht-wo, placements, rueckbau, frontend, ortsvergleich, epic-3122]
---

# Was steht wo B6b-2: Ortsvergleich schreibt nur noch die Tabelle, alte Einstellwege entfernt

## Approval

- [ ] Approved

## Purpose

Nach #3237 wertet die Ausgabe nur noch die Tabelle „Was steht wo“ (`display_config.placements`) aus. Der Ortsvergleich im Frontend schreibt aber beim Anlegen und Speichern noch die Altfelder (`channel_layouts`, `outlook_metrics`, `outlook_metric_formats`, `channel_active_metrics`, `hourly_metrics`, `hourly_metric_formats`) und bietet dafür alte Bedienflächen (Stundenverlauf, Ausblick). Dieses Paket (Issue #3276, Epic #3122, zweiter Teil von Spec-AC-38) lässt die Altschlüssel im Ortsvergleich ersatzlos weg und entfernt die alten Bedienflächen. Jede Einstellung ist dort nur noch einmal erreichbar: in der Tabelle.

## Source

- **File:** `frontend/src/lib/components/compare/compareEditorSave.ts` (Schreibpfad), `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` (Anlegen), `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` (Bedienflächen)
- **Identifier:** Vergleich-Zweig der Payload-Bildung (Anlegen POST, Speichern PUT); `CompareHourlyLayoutControls` (wird gelöscht)

> **Schicht-Hinweis:** Reines Frontend (`frontend/src/...`, SvelteKit). Die Go-API (`internal/`) und der Python-Core bleiben unverändert; sie sind nur Prüfgegenstand (siehe Implementation Details, Go-Prüfung).

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung (#1170):** Änderungen liegen im geteilten Code unter `shared/` bzw. entfernen Vergleich-eigenen Code. Es entsteht keine neue Vergleich-eigene Komponente. `CompareHourlyLayoutControls.svelte` ist ein Vergleich-eigener Baustein und wird gelöscht (Rückbau, kein Neubau).
> - **Mandantentrennung:** Der datenbewegende Endpoint (Anlegen/Speichern eines Vergleichs) wird mit zwei verschiedenen Nutzern geprüft; `user_id` stammt aus dem Auth-Kontext, nie `"default"`. Schreiben bleibt Read-Modify-Write mit Merge, nie Replace (#102).
> - **Kanäle:** E-Mail, Telegram, SMS und Premium-SMS geben für neu angelegte und gespeicherte Vergleiche denselben Inhalt wie zuvor aus (Golden #3237).

## Estimated Scope

- **LoC:** Produktion netto stark negativ (ca. −600 bis −900), neuer Code unter 100 Zeilen; Tests umgestellt
- **Files:** ca. 12 Produktionsdateien, 1 gelöscht, dazu zugehörige Unit- und Playwright-Tests
- **Effort:** medium (Risiko MEDIUM: sichtbarer Anlege-Ablauf des Ortsvergleichs)

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/compare/compareEditorSave.ts` | MODIFY | `hourly_*`, `outlook_*`, `channel_active_metrics`, `channel_layouts` nicht mehr in die Payload schreiben (ca. Zeilen 175–218, 551–572) |
| `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts` | MODIFY/DELETE | Altfeld-Payload des Vergleichs entfällt |
| `frontend/src/lib/components/shared/weather-metrics-tab/compareChannelMetricLayouts.ts` | MODIFY/DELETE | `channel_layouts`-Aufbau des Vergleichs entfällt |
| `frontend/src/lib/components/shared/versandVergleichSpeicherung.ts`, `alarmeVergleichSpeicherung.ts`, `wetter-tab/wertebereicheVergleichSpeicherung.ts` | MODIFY | Durchreicher von `hourly_*`/`outlook_*` an `compareEditorSave` entfernen |
| `frontend/src/lib/components/compare/wetterMetrikenPropsAus.ts` | MODIFY | `hourly*`-, `outlook*`-, `channelActive*`-Props entfernen (ca. 78–114) |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | MODIFY | POST ohne `channelActiveMetricKeys`, `hourly*`, `outlook*` (ca. 357–359); `placements` entstehen weiter über WetterTab `createMode` |
| `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts` | MODIFY | `stundenverlauf` und `ausblick` aus `ZUSTELLUNGS_SECTIONS` für den Vergleich entfernen (ca. Zeile 83) |
| `frontend/src/lib/components/compare/CompareHourlyLayoutControls.svelte` | DELETE | alte Bedienfläche Stundenverlauf |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | MODIFY | Vergleich-Zweig der Mounts (ca. 1601 und 1631) entfernen; Trip-Zweig von `OutlookLayoutControls` bleibt bis #3297 |
| zugehörige `*.test.ts` (Aufruf `node --test`) und Playwright-Specs unter `frontend/e2e/` | MODIFY | von Altfeld-Prüfung auf Verhaltensnachweis über `placements` bzw. POST/PUT-Body ohne Altschlüssel umstellen, nicht still löschen |
| `docs/specs/modules/feat_3122_was_steht_wo.md` | MODIFY | Nachtrag zu AC-38: Ortsvergleich-Teil erledigt durch #3276 |

### Nicht in dieser Spec

- Trip-Pfad (Anlegen/Speichern von Trips), `show_outlook` und die Home-Anzeige „Layout konfiguriert“ über `placements`: **#3297**.
- Typen (`types.ts`) und der Frontend-Sperrtest, der Altfelder im Quelltext verbietet: **#3298** (scharf erst nach #3276 und #3297).
- Bereinigung der Bestandsdaten, Loader, Serialisierung, Renderer-Parameter: **#3277**.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `feat_3122_was_steht_wo` | Spec | AC-38 (zweiter Teil: Oberfläche bietet keine Bedienung mehr für Altfelder) |
| `feat_3237_altpfad_entfernen` | Spec | Voraussetzung: Backend liest nur `placements`; Golden-Test `tests/tdd/test_3237_golden_vier_kanaele.py` |
| `feat_3154` / `ZustellungTab`, `WetterTab` | Frontend | Detail-Hub bereits sauber; neuer Weg über `placements` |
| `frontend/src/lib/components/shared/wetter-tab/wetterTabSpeicherung.ts` | Frontend | schreibt `placements` (`mitPlacements`), auch im `createMode` |
| `internal/handler/config_merge.go` (`mergeConfigMap`) | Go | Top-Level-Merge: nicht gesendete Schlüssel bleiben, gesendete Werte ersetzen den Bestand |
| `internal/handler/compare_preset.go`, `briefing_subscription.go` | Go | Anlegen/Speichern; Validierung geprüft (siehe unten) |
| #3277, #3297, #3298 | Issues | abgegrenzte Folgearbeit |

## Implementation Details

**Altschlüssel weglassen, nie leer senden.** Der Go-Merge (`config_merge.go`, `mergeConfigMap`) ersetzt Werte je Top-Level-Schlüssel von `display_config`. Würde das Frontend etwa `channel_layouts: {}` oder `outlook_metrics: []` senden, ersetzte das den Bestand. Deshalb bleiben `channel_layouts`, `outlook_metrics`, `outlook_metric_formats`, `channel_active_metrics`, `hourly_metrics`, `hourly_metric_formats` im Vergleich-POST (Anlegen) und -PUT (Speichern) ersatzlos aus dem Body. Weder `null` noch `{}` noch `[]`. Bestandsdaten bleiben dadurch erhalten (Read-Modify-Write), die Entfernung aus den Daten ist #3277.

**Go-Prüfung (Ergebnis).** `validateComparePreset` (`compare_preset.go:119–157`) prüft nur Name, Zeitplan, Profil, Vorhersagehorizont, Stundenfenster, Wochentag, Slot-Zeiten und Enddatum. `applyComparePresetPatch` (`compare_preset.go:325`) und `mergeBriefingPatch` (`briefing_subscription.go:176–203`) mergen `display_config` generisch eine Ebene tief per `mergeConfigMap`. Im Go-Produktionscode (`internal/`, ohne Tests) kommt keiner der Altschlüssel als Pflichtfeld, Default oder Validierung vor (einziger Treffer ist ein Kommentar in `internal/model/compare_preset.go:46`). Fehlende Altschlüssel führen also zu keinem Fehler und keinem Server-Default. Es ist keine Go-Änderung nötig.

**Bedienflächen.** `CompareHourlyLayoutControls.svelte` wird gelöscht, die Mounts des Vergleich-Zweigs in `WeatherMetricsTab.svelte` (Stundenverlauf, Ausblick) entfallen, die Abschnitte stehen im Vergleich nicht mehr in `ZUSTELLUNGS_SECTIONS`. Die Einstellungen für Stundenverlauf (Stellen und Formate je Metrik) und Ausblick (`outlook_reports` Morgen/Abend) sowie die Kanal-Auswahl sind in der Tabelle „Was steht wo“ vollständig abgedeckt, es geht keine Funktion verloren. Der Trip-Zweig von `OutlookLayoutControls` bleibt unverändert bis #3297.

**Neu angelegter Vergleich.** Er bekommt weiter korrekte `placements` über WetterTab `createMode` (`wetterTabSpeicherung.ts`); der Server ergänzt fehlende `rows` ohnehin aus der Grundauswahl (#3237). Die Mail-Ausgabe bleibt gegenüber dem Stand vor der Änderung gleich.

**Tests.** Frontend-Unit-Tests laufen mit `node --test` (kein Vitest). Tests, die bisher Altfelder prüfen, werden auf Verhaltensnachweise umgestellt: Body von POST/PUT enthält keinen Altschlüssel, `placements` sind vorhanden, Bestandswerte bleiben nach dem Speichern in den Daten. Keine Mocks als Verhaltensnachweis; Playwright-Specs prüfen sichtbares Nutzerverhalten gegen Staging bzw. den lokalen E2E-Stack.

## Expected Behavior

- **Input:** Nutzer legt einen Ortsvergleich an oder speichert einen bestehenden in den Reitern Wetter, Versand, Alarme.
- **Output:** Anlege-Body (POST) und Speicher-Body (PUT) tragen keinen der sechs Altschlüssel; `placements` sind vorhanden (neu angelegt) bzw. bleiben gemäß Tabelle erhalten. Die Einstellung für Stundenverlauf und Ausblick findet der Nutzer nur in „Was steht wo“.
- **Side effects:** Bestandsdaten behalten ihre Altfelder (Top-Level-Merge). Es wird nichts gelöscht; Bereinigung folgt in #3277.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer legt im Anlege-Ablauf einen neuen Ortsvergleich an / When er den Vergleich speichert und der Anlege-Aufruf (POST) abgesendet wird / Then enthält der gesendete Inhalt keinen der Schlüssel `channel_layouts`, `outlook_metrics`, `outlook_metric_formats`, `channel_active_metrics`, `hourly_metrics`, `hourly_metric_formats` (auch nicht leer) und trägt dafür `placements`.
  - Test: Playwright legt einen Vergleich an und liest den abgefangenen POST-Body; zusätzlich Unit-Test (`node --test`) der Payload-Bildung gegen eine echte Anlege-Eingabe.

- **AC-2:** Given ein bestehender Ortsvergleich mit gesetzten Altfeldern (`channel_layouts`, `outlook_metrics`, `hourly_metrics` u. a.) in den Daten / When der Nutzer in einem Reiter etwas ändert und speichert / Then enthält der Speicher-Aufruf (PUT) keinen der sechs Altschlüssel, und die Altwerte stehen danach unverändert in den gespeicherten Daten (kein Datenverlust, Merge).
  - Test: Vergleich mit Altfeldern per Staging-Seed anlegen, im UI ändern und speichern, PUT-Body prüfen und gespeicherte Datei vorher/nachher vergleichen; Unit-Test der Payload-Bildung des Speicherns.

- **AC-3:** Given ein Nutzer legt einen Ortsvergleich an oder öffnet einen bestehenden / When er den Anlege-Ablauf und die Reiter Wetter, Versand und Alarme durchgeht / Then gibt es keine alte Bedienfläche „Stundenverlauf“ oder „Ausblick“ mehr, und die Einstellung für Stundenverlauf und Ausblick ist ausschließlich in „Was steht wo“ erreichbar und dort änderbar.
  - Test: Playwright prüft, dass die alten Bedienflächen fehlen, ändert dieselbe Einstellung in „Was steht wo“ und prüft, dass sie danach in `placements` steht.

- **AC-4:** Given ein neu angelegter Ortsvergleich (ohne Altfelder angelegt) / When das Briefing erzeugt und über E-Mail, Telegram, SMS und Premium-SMS ausgegeben wird / Then entspricht der Inhalt jedes Kanals der Tabelle im Vergleich und ist inhaltlich identisch zur Ausgabe eines wie bisher angelegten Vergleichs mit derselben Grundauswahl (Golden #3237).
  - Test: Vergleich im UI auf Staging anlegen, echt zugestellte Mail mit `email_spec_validator.py` prüfen (Exit 0); Golden-Test `tests/tdd/test_3237_golden_vier_kanaele.py` bleibt grün.

- **AC-5:** Given zwei verschiedene Nutzer A und B mit je einem Ortsvergleich / When A einen neuen Vergleich anlegt und sein bestehendes Vergleichs-Abo speichert / Then bleiben die Daten von B unverändert, die Aufrufe laufen mit der echten `user_id` von A (nie `"default"`), und bestehende Felder von A bleiben durch Merge erhalten.
  - Test: Zwei Staging-Nutzer legen an und speichern; Datei von B vor/nach vergleichen, Daten von A auf Erhalt der Bestandsfelder prüfen.

- **AC-6:** Given ein Nutzer legt einen neuen Trip an oder speichert einen bestehenden Trip / When der Trip-Pfad durchläuft / Then verhält sich der Trip unverändert gegenüber dem Stand vor dieser Änderung, einschließlich der Bedienfläche `OutlookLayoutControls` und der gesendeten Trip-Felder (Regressionsschutz; Rückbau des Trip-Pfads ist #3297).
  - Test: bestehende Trip-Anlege- und Speicher-Tests (Unit und Playwright) laufen unverändert grün; Trip-POST-Body ist gleich dem Stand vor der Änderung.

- **AC-7:** Given der Go-Server nimmt einen Vergleich ohne die sechs Altschlüssel entgegen / When er validiert und speichert / Then lehnt er den Vergleich nicht ab, setzt keinen Default für die Altschlüssel und lässt gespeicherte Altwerte im Bestand unberührt.
  - Test: Go-Test zu `applyComparePresetPatch` bzw. Anlegen mit Body ohne Altschlüssel: Antwort 2xx, Altwerte im vorhandenen `display_config` bleiben erhalten.

## Definition of Done

- AC-1 bis AC-7 grün; Unit-Tests per `node --test`, Go-Test für AC-7, Playwright-Specs für AC-1, AC-2, AC-3, AC-5, AC-6.
- `CompareHourlyLayoutControls.svelte` ist gelöscht, kein Import verbleibt; `svelte-check` und Frontend-Build grün.
- Mutations-Gegenprobe durch den `implementation-validator`: Wiedereinbau eines Altschlüssels in POST/PUT wird von mindestens einem Test gefangen.
- Staging: Vergleich anlegen und speichern, Mail mit `email_spec_validator.py` grün; danach Prod-Deploy mit Selftest Exit 0.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN Anlege-Eingabe Ortsvergleich WHEN POST-Body gebildet THEN kein Altschlüssel (auch nicht leer), `placements` vorhanden (AC-1)
- [ ] Test 2: GIVEN bestehender Vergleich mit Altfeldern WHEN gespeichert THEN PUT-Body ohne Altschlüssel, Altwerte in den Daten erhalten (AC-2)
- [ ] Test 3: GIVEN Anlegen und Reiter eines Vergleichs WHEN gerendert THEN keine Bedienfläche Stundenverlauf/Ausblick; Änderung nur in „Was steht wo“ (AC-3)
- [ ] Test 4: GIVEN neu angelegter Vergleich WHEN Briefing in vier Kanälen THEN Inhalt gemäß Tabelle, Golden grün (AC-4)
- [ ] Test 5: GIVEN zwei Nutzer WHEN Anlegen und Speichern THEN Daten getrennt, kein `"default"` (AC-5)
- [ ] Test 6: GIVEN Trip anlegen/speichern WHEN Pfad läuft THEN unverändert (AC-6)
- [ ] Test 7: GIVEN Body ohne Altschlüssel WHEN Go validiert und mergt THEN 2xx, Bestand unberührt (AC-7)

Test-Politik: kein Mock-Theater, Verhaltensnachweis über `placements` und den tatsächlich gesendeten Body; Frontend-Unit-Tests laufen per `node --test` (kein Vitest). Ein Dateiinhalt-Scan der Quelltexte ist hier kein Nachweis; der Frontend-Sperrtest folgt in #3298.

## Known Limitations

- Bestandsdaten behalten ihre Altfelder (Top-Level-Merge); sie sind wirkungslos. Bereinigung: #3277.
- Im Trip-Pfad bleiben Altfeld-Schreibwege und `OutlookLayoutControls` bis #3297 bestehen; `show_outlook` und die Home-Anzeige „Layout konfiguriert“ ebenfalls.
- Typen in `types.ts` behalten die Altfelder bis #3298.
- Der Frontend-Sperrtest gegen Rückkehr der Altschlüssel kommt erst mit #3298.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0124 (Tabelle „Was steht wo“ als einzige Quelle)
- **Rationale:** ADR-0124 hat die Tabelle als einzige Quelle entschieden; dieses Paket vollzieht den vorgesehenen Rückbau im Frontend des Ortsvergleichs und ändert keine frühere Entscheidung. Ein neues ADR ist nicht nötig.

## Changelog

- 2026-11-23: Initial spec created (Issue #3276, Epic #3122, Spec-AC-38 zweiter Teil; Ortsvergleich-Pfad, Zuschnitt in #3297/#3298).
