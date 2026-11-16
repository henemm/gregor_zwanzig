---
entity_id: fix_3061_ausblick_alle_groessen
type: bugfix
created: 2026-11-16
updated: 2026-11-16
status: draft
version: "1.0"
workflow: fix-3061-ausblick-alle-groessen
tags: [orte-vergleich, ausblick, editor, pruefkatalog, "3047", "3061"]
---

# Ausblick im Orte-Vergleich-Editor: bewusste Vollauswahl ist nicht "nie eingestellt"

## Approval

- [ ] Approved

## Purpose

Im Orte-Vergleich-Editor wird eine bewusst gespeicherte Grundauswahl, die genau alle Katalog-Größen enthält, im Ausblick-Block fälschlich wie ein Altbestand ohne Einstellung behandelt: Der Editor zeigt nur die sieben festen Vorgabe-Spalten aktiv, die Mail aber alle darstellbaren Größen (Befund F4 aus Epic #3047, Bug #3061). Die Korrektur reicht das vorhandene Signal "nie eingestellt" (`active_metrics` fehlt im Preset, im Editor `null`) bis zum Ausblick durch, statt es per Listenvergleich zu erraten. Damit zeigt der Editor dasselbe wie die Mail (#3047 AC-13/AC-21).

## Source

- **File:** `frontend/src/lib/components/shared/OutlookLayoutControls.svelte`
- **Identifier:** `istNieEingestellteOrteGrundauswahl` / `grundauswahlKennungen`

Die Ursache liegt in der Hydrierung: `hydrateWeatherMetricsFromPreset` (`weather-metrics-tab/weatherMetricsCompareSave.ts`) materialisiert ein fehlendes `active_metrics` zu `[...COMPARE_METRIC_KEYS]`. Beide Hub-Hydrierer (`CompareTabs.svelte` und `compareHubHydration.ts`) setzen damit `wizardState.activeMetricKeys` auf die volle Liste, das `null` geht verloren.

Mail-Seite (Referenz, bleibt unverändert): `src/output/renderers/compare_outlook_metric_ids.py` (fehlendes `active_metrics` ergibt feste Vorgabe-Spalten, volle Liste ergibt alle darstellbaren Größen).

> **Schicht:** ausschließlich Frontend (`frontend/src/...`) plus Prüfkatalog-Fixture und dessen Python-Test (`tests/`). Keine Go-API-, keine Python-Core-Änderung.
> **Trip/Ortsvergleich-Teilung (#1170):** Die Änderung liegt in den geteilten Bausteinen unter `shared/`. Der Trip-Kontext bleibt unverändert (Trip reicht nie `null` als Altbestand-Signal herein, `WeatherMetricsTab.svelte` Trip-Pfad bleibt).
> **Mandantentrennung:** Es werden keine Nutzerdaten bewegt, nur die Anzeige im Editor und das Lesen des Presets ändern sich. `user_id`-Pfade sind nicht berührt.
> **Kanäle:** Betroffen ist die Auswahl der Ausblick-Größen im Orte-Vergleich-Briefing. Gleichheit Editor = Mail gilt für E-Mail; die Auswahl steuert den Ausblick-Inhalt, den auch Telegram, SMS und Premium-SMS aus derselben Quelle beziehen (ADR-0095). An den Kanal-Renderern ändert sich nichts.

## Scope

- **Enthalten:** Durchreichen des Signals „nie eingestellt“ (`null`) von der Hub-Hydrierung bis zum Ausblick-Block im Orte-Vergleich-Editor; Entfernen des Listenvergleichs in `OutlookLayoutControls.svelte`; neuer Prüfkatalog-Fall „Vollauswahl gespeichert, outlook_metrics fehlt“ samt Fixture-Baulogik.
- **Nicht enthalten:** Mail-Renderer und Kanal-Renderer (Mail-Seite ist das Soll und bleibt unverändert), Go-API, Python-Core, Trip-Editor-Verhalten, Trip-Altbestand (#3048).

## Definition of Done

Alle AC-1 bis AC-6 sind durch die Tests im Test Plan grün nachgewiesen, die Tests zu AC-1 und zum Prüfstand Editor gleich Mail waren vorher rot; die Adversary-Gegenprobe (Wiedereinbau des Listenvergleichs bzw. Materialisierung in einem Hub-Hydrierer) fängt mindestens ein Test; auf Staging zeigt ein Orte-Vergleich mit gespeicherter Vollauswahl im Editor-Ausblick dieselben Größen wie die zugestellte Mail.

## Estimated Scope

- **LoC:** ca. +20/-20 Quelltext, +40 bis 60 Tests
- **Files:** 5 Quelldateien, 3 bis 4 Test-/Fixture-Dateien
- **Effort:** low bis medium (Risiko MEDIUM: `wizardState.activeMetricKeys` darf im Hub künftig `null` sein)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `hydrateHubFieldsFromPreset` (`compareHubHydration.ts`) | function | liefert bereits `activeMetricKeys: null` für Altbestand (#1191-Semantik: `null` = nie eingestellt, `[]` = bewusst leer) |
| `materializeActiveMetricKeys` (`compareMetricOrder.ts`) | function | materialisiert `null` zu `COMPARE_METRIC_KEYS` für Leser, die eine Liste brauchen |
| `AlarmeTab` / Alarm-Hydrierer (#1320) | component | braucht materialisierte Liste für die Empfindlichkeits-Tabelle, materialisiert selbst |
| `compareEditorSave.ts` | module | schreibt `active_metrics` nur, wenn editiert; bei `null` wird der Schlüssel nicht geschrieben |
| `compare_outlook_metric_ids.py` | module | Mail-Seite, Referenzverhalten (Soll) |
| Prüfkatalog `tests/fixtures/einstellung_gleich_mail/fallliste_orte.json` + `tests/tdd/test_einstellung_gleich_mail_orte.py`, `tests/tdd/test_einstellung_gleich_mail_fallliste.py` | fixture/test | Fälle `O-AB-*`, Dimension `auswahl_muster` |
| `feat_3047_einstellung_gleich_mail_pruefkatalog.md` | spec | Bezugs-Spec (AC-13/AC-21, O4) |

## Implementation Details

Technischer Ansatz (Tech-Lead-Entscheidung, kein zweites Flag, sondern der etablierte null-Vertrag):

1. `weatherMetricsCompareSave.ts`: neue Funktion `hydrateWeatherMetricsFromPresetOrNull` mit Rückgabe `string[] | null` (fehlendes `active_metrics` bleibt `null`). Die bestehende Funktion bleibt unverändert, weil `compareActiveMetricsStorageFormat.test.ts` die Rohform erwartet.
2. `CompareTabs.svelte` (Wetter-Metriken-Hydrierer) und `compareHubHydration.ts` (Alarm-Hydrierer) nutzen die null-Variante. Beide müssen umgestellt werden, sonst hängt das Ergebnis von der Reihenfolge der geöffneten Reiter ab. Kommentar zu #1320 wird angepasst (AlarmeTab materialisiert selbst).
3. `WeatherMetricsTab.svelte`: nur im Vergleich-Kontext `grundauswahl = activeMetricKeys == null ? null : materializedActiveMetricKeys`; der Trip-Pfad bleibt wie er ist.
4. `OutlookLayoutControls.svelte`: `istNieEingestellteOrteGrundauswahl` und seine Verwendung in `grundauswahlKennungen` entfallen. Nur noch `grundauswahl === null` bedeutet "nie eingestellt" (feste Vorgabe-Spalten). Eine Liste, auch die volle, gilt als bewusst gespeichert.
5. Dirty-Check/Speichern: Die Snapshots materialisieren weiterhin, damit keine Scheindifferenz entsteht; bei `null` schreibt `compareEditorSave.ts` kein `active_metrics`. Nach der ersten Änderung der Grundauswahl wird die Liste geschrieben und gilt ab dann für Editor und Mail gleich.
6. Prüfkatalog: `fallliste_orte.json` erhält einen Fall mit `active_metrics` = alle Katalog-Größen und fehlendem `outlook_metrics`; die Fixture-Baulogik `preset_aus_werten` in `test_einstellung_gleich_mail_orte.py` wird um diese Kombination erweitert (bisher war sie nicht darstellbar, deshalb war der Fehler unfangbar).

Vor dem Merge neu auf `main` aufsetzen (Parallelsitzung #3048 kann dieselbe Prüfkatalog-Datei berühren).

## Expected Behavior

- **Input:** Orte-Vergleich-Preset mit (a) `active_metrics` = alle Katalog-Größen ohne `outlook_metrics`, (b) ohne `active_metrics`, (c) beliebige Reihenfolge der geöffneten Editor-Reiter.
- **Output:** Der Ausblick-Block im Editor zeigt exakt die Größen, die die Mail ausweist: (a) alle darstellbaren Größen aktiv, (b) die sieben festen Vorgabe-Spalten.
- **Side effects:** Keine. Öffnen und Speichern ohne Änderung verändert das Preset nicht.

## Test Plan

Tests ohne Mock-Theater; Frontend-Tests laufen über `node --test` (kein Vitest), Python-Tests über benannte pytest-Dateien.

### Automated Tests (TDD RED)

- [ ] Test 1 (`frontend/src/lib/components/compare/__tests__/outlookMetricIdSelection.test.ts`, bestehende Datei): GIVEN `grundauswahl` = alle Katalog-Größen und `outlook_metrics` fehlt WHEN die Ausblick-Auswahl aufgelöst wird THEN sind alle darstellbaren Ausblick-Größen aktiv. Heute rot.
- [ ] Test 2 (`editor_standard_gleich_mail.test.ts`, Prüfstand auf null-Variante umgestellt): GIVEN Preset mit voller `active_metrics` WHEN der Editor hydriert und der Ausblick gerendert wird THEN stimmt die Editor-Auswahl mit der Mail-Auswahl überein. Heute rot.
- [ ] Test 3 (gleiche Datei): GIVEN Preset ohne `active_metrics` WHEN hydriert THEN bleiben die sieben festen Vorgabe-Spalten aktiv, identisch zur Mail (Regressionsschutz).
- [ ] Test 4 (gleiche Datei, Rendertest der echten Verdrahtung in `WeatherMetricsTab.svelte`): GIVEN Vergleich-Kontext mit `activeMetricKeys == null` bzw. voller Liste WHEN gerendert THEN erhält der Ausblick `null` bzw. die Liste; im Trip-Kontext unverändert.
- [ ] Test 5: GIVEN Alarme-Reiter wird vor dem Wetter-Metriken-Reiter geöffnet, Preset ohne `active_metrics` WHEN beide Hydrierer gelaufen sind THEN ist das Ausblick-Ergebnis identisch zur umgekehrten Reihenfolge, und die Alarm-Empfindlichkeits-Tabelle zeigt weiter Metriken (#1320).
- [ ] Test 6: GIVEN Altbestand ohne `active_metrics` WHEN der Editor geöffnet und ohne Änderung gespeichert wird THEN enthält das Speicher-Payload kein `active_metrics` und der Dirty-Check meldet keine Änderung.
- [ ] Test 7 (`test_einstellung_gleich_mail_orte.py` und `test_einstellung_gleich_mail_fallliste.py`): GIVEN neuer Fall "Vollauswahl gespeichert, outlook_metrics fehlt" in `fallliste_orte.json` WHEN die Mail-Seite des Prüfkatalogs läuft THEN ist der Fall grün und die Fallliste-Konsistenzprüfung besteht.

## Acceptance Criteria

- **AC-1:** Given ein Orte-Vergleich mit gespeichertem `active_metrics` = alle Katalog-Größen und ohne `outlook_metrics` / When der Nutzer den Ausblick-Block im Editor öffnet / Then zeigt der Editor alle darstellbaren Größen als aktiv, identisch zur versendeten Mail.
  - Test: Editor-Hydrierung plus Ausblick-Auflösung gegen die Mail-Auswahl desselben Presets (`outlookMetricIdSelection.test.ts`, `editor_standard_gleich_mail.test.ts`); heute rot, danach grün.

- **AC-2:** Given ein Orte-Vergleich ohne `active_metrics` (Altbestand, nie eingestellt) / When der Nutzer den Ausblick-Block im Editor öffnet / Then zeigt der Editor weiter die sieben festen Vorgabe-Spalten aktiv, identisch zur Mail.
  - Test: Prüfstand Editor gleich Mail für den Altbestand-Fall (Regressionsschutz, `editor_standard_gleich_mail.test.ts`).

- **AC-3:** Given ein Altbestand-Vergleich ohne `active_metrics` / When der Nutzer den Alarme-Reiter zuerst und danach den Wetter-Metriken-Reiter öffnet (oder umgekehrt) / Then ist das Ausblick-Ergebnis in beiden Reihenfolgen gleich, und der Alarme-Reiter zeigt weiterhin die Metriken in seiner Empfindlichkeits-Tabelle (#1320).
  - Test: Hydrierung in beiden Reiter-Reihenfolgen, Vergleich der Ausblick-Auswahl; Alarme-Tabelle enthält Metriken.

- **AC-4:** Given ein Altbestand-Vergleich ohne `active_metrics` / When der Nutzer den Editor öffnet und ohne Änderung speichert / Then wird kein `active_metrics` in das Preset geschrieben und der Editor zeigt keinen Hinweis auf nicht gespeicherte Änderungen.
  - Test: Speicher-Payload und Dirty-Check nach reinem Öffnen eines Altbestands (Nutzerverhalten, kein Dateiinhalt-Check).

- **AC-5:** Given ein Trip im Trip-Editor / When der Nutzer den Ausblick-Block öffnet / Then verhält sich der Trip-Editor genau wie vor der Änderung, die geteilten Bausteine liefern für `context="route"` dasselbe Ergebnis (Teilungs-Invariante #1170).
  - Test: bestehende Trip-Editor-Tests bleiben unverändert grün; Rendertest zeigt, dass der Trip-Pfad nie `null` als Altbestand-Signal erhält.

- **AC-6:** Given der Prüfkatalog `fallliste_orte.json` / When der Fall "Vollauswahl gespeichert, outlook_metrics fehlt" ausgeführt wird / Then ist er in der Fallliste enthalten und die Mail-Seite des Prüfkatalogs für diesen Fall grün.
  - Test: `test_einstellung_gleich_mail_orte.py` und `test_einstellung_gleich_mail_fallliste.py` laufen mit dem neuen Fall grün; die Fixture-Baulogik kann die Kombination erzeugen.

## Known Limitations

- Nach der ersten Änderung der Grundauswahl wird `active_metrics` geschrieben; ab dann gilt die gespeicherte Liste (auch wenn sie wieder alle Größen enthält) für Editor und Mail. Das ist gewollt, nicht rückgängig zu machen.
- Die alte Funktion `hydrateWeatherMetricsFromPreset` materialisiert weiterhin; nur die beiden Hub-Hydrierer wechseln auf die null-Variante.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Es wird der bestehende null-Vertrag (#1191: `null` = nie eingestellt, `[]` = bewusst leer) konsequent durchgereicht; kein neues Muster, keine Abweichung von bestehenden ADRs. Ein separates Flag wurde verworfen, weil es ein zweites Signal neben dem etablierten Vertrag wäre.

## Changelog

- 2026-11-16: Initial spec created
