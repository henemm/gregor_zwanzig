---
entity_id: feat_2794_s3a_teil4_entfernen
type: module
created: 2026-11-12
updated: 2026-11-12
status: draft
version: "1.0"
tags: [hub, reiter, entfernen, vorbelegung, uebersicht, texte, glossar, pendant, epic-2791]
---

# Einstellungen neu S3a, Teil-PR 4: Entfernen und Nachziehen (#2794)

## Approval

- [ ] Approved

## Purpose

Teil-PR 4 der freigegebenen Gesamt-Spec `feat_2794_s3a_reiter_wetter.md` (Epic #2791, Issue #2794) und letzter Teil von S3a. Die alte Oberfläche für Wertebereiche (Corridor-Editor), die Zeithorizont-Chips und die Metrik-Checkbox werden entfernt; die Übersicht, die Listen-Sprünge, Hilfe- und Onboarding-Texte, das Glossar und der Abgleich gegen Mockup Fassung 3 ziehen auf die neuen Reiter Wetter und Zustellung nach. Am Ende steht ein Soll/Ist-Bild an den PO.

Die Analyse (`docs/context/feature-2794-s3a-teil4.md`) hat zwei Dinge ergeben, die den Zuschnitt von AC-31 verändern:

1. Viele „Altkomponenten“ sind keine tote Oberfläche. `AlarmeTab`, `WeatherMetricsTab` und `layout-tab/` tragen den Übergangsreiter Zustellung (bis S3b, #2795) und bleiben. Die Gesamt-Spec §7, die `AlarmeTab`/`alarme-tab/`/`AlarmeScheduleTab` als „zu entfernen“ nennt, wird durch diese Detail-Spec präzisiert.
2. Der Corridor-Editor ist zwar nirgends mehr sichtbar, läuft aber versteckt (`display:none`) in den Anlege-Ketten von Trip und Orts-Briefing und liefert dort die Vorbelegung der Wertebereiche (`corridors`). Diese Logik muss ohne Oberflächen-Komponente weiterlaufen, bevor die Komponente gelöscht wird. Daraus kommen die neuen Kriterien AC-43 bis AC-47.

Diese Spec übernimmt AC-31 bis AC-35 der Gesamt-Spec und präzisiert sie. Die neuen Kriterien beginnen bei AC-43 (AC-1 bis AC-42 sind in Gesamt-Spec und Teil-Spec 3 vergeben).

Grundlagen: Gesamt-Spec (§7, Lieferplan, Teil-PR 4), Teil-Specs `feat_2794_s3a_teil2_leiste.md` und `feat_2794_s3a_teil3_wetter.md`, Analyse `docs/context/feature-2794-s3a-teil4.md`, Mockup `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html`, Glossar `docs/reference/i18n_glossar.md`, Pendant-Gate `docs/reference/gates_und_ratschen.md`, ADR-0109 (Reiterstruktur, Pendant-Sperre), ADR-0104 (zweisprachig), ADR-0101 (Read-Modify-Write).

## Lieferung in zwei Schritten (Tech-Lead-Entscheidung)

| Schritt | Inhalt | ACs |
|---|---|---|
| **4a Entfernen und Umzug** (eigener PR) | Re-Exporte löschen, Logikmodule umziehen, Vorbelegung als reine Funktion, Corridor-Editor und versteckte Mounts löschen, Tests entfallener Oberflächen löschen oder umstellen. Keine sichtbare Änderung. | AC-31, AC-43 bis AC-47, AC-34 (Querschnitt) |
| **4b Übersicht, Texte, Glossar, Fresh-Eyes** (zweiter PR) | Pendant-Gate, Übersicht U3/U4, Listen-Sprünge und Menü-Wortlaut, Texte, Glossar, Wächter gegen alte Reiternamen, Golden neu, Fresh-Eyes, Soll/Ist-Bild an den PO. | AC-32, AC-33, AC-35, AC-48 bis AC-50, AC-34 (Querschnitt) |

Gründe: (1) 4a ändert keine Oberfläche, trägt aber das höchste Funktionsrisiko (Vorbelegung beim Anlegen); ein Rollback darf nicht an Textänderungen gekoppelt sein. (2) Der Umzug und die Löschungen erzeugen einen großen Rename-Diff (ca. 5000 Zeilen), der die fachlich sichtbaren Änderungen von 4b verdecken würde. (3) Jeder Schritt ist einzeln lauffähig, hat eigene CI (6 Checks), eigenes Staging und `/e2e-verify`; 4a wird per Anlege-E2E mit zwei Nutzern abgenommen, 4b per Text- und Mockup-Abnahme. AC-34 (Katalog, Parität, Glossar) gilt in beiden Schritten für alle jeweils neuen oder geänderten Texte.

## Source

- **Frontend (Entfernen/Umzug, 4a):** `frontend/src/lib/components/shared/corridor-editor/`, `shared/wetter-tab/`, `shared/weather-metrics-tab/`, `trip-detail/{MetricCheckbox,MetricGroup}.svelte`, `ui/horizon-chip/`, `molecules/HorizonChips.svelte`, `organisms/MetricsEditorContextBar.svelte`, `trip-new/TripNewEditor.svelte`, `compare-new/CompareNewEditor.svelte`, `compare/CompareTabs.svelte`, `compare/corridorPropsAus.ts`, Barrels `organisms/index.ts`, `trip-detail/index.ts`, `molecules/index.ts`.
- **Frontend (Übersicht, Texte, 4b):** `shared/hub-uebersicht/{hubUebersichtModell.ts,HubUebersicht.svelte}`, `trip-detail/HubOverview.svelte`, `shared/subscriptionActions.ts`, `shared/infoboxKeys.ts`, `lib/utils/cockpitHelpers568.ts`, `routes/hilfe/+page.svelte`, `routes/+page.svelte`, `routes/trips/+page.svelte`, `routes/compare/+page.svelte`, `frontend/src/lib/i18n/messages/{de,en}/*.json`, `frontend/src/lib/i18n/__tests__/`.
- **Doku:** `docs/reference/i18n_glossar.md`, `docs/reference/gates_und_ratschen.md` (Pendant-Gate, nur lesen), Golden-Dateien unter `tests/golden/`.
- **Go-API und Python-Core:** keine Produktivänderung. Backend-Tests mit Namens-Treffern (`tests/tdd/test_corridor_*`, `test_compare_metric_catalog_endpoint.py` u. a.) betreffen das Backend und werden in 4a einzeln bestätigt, nicht umgezogen.

> **Schicht-Hinweis:** Alles Frontend (SvelteKit). Der Reiter Zustellung, die Speichergrenze (Go) und das Alarmquellen-Gate (Python) bleiben unberührt.
>
> **Trip/Ortsvergleich-Teilung (PFLICHT, #1170, Epic #2345):** Die reine Funktion `anlegeVorbelegung.ts` liegt unter `shared/wetter-tab/` und kennt beide Kontexte über einen Parameter; es entsteht keine Compare-Komponente mit Trip-Pendant. Compare-eigen bleiben nur Orte-Tab, transponierte Übersicht und Compare-Mail-Template.
>
> **Mandantentrennung:** Das Anlegen bewegt Nutzerdaten. `user_id` kommt aus dem Auth-Kontext, nie `"default"`; es entsteht kein neuer Datenweg (AC-46).
>
> **Kanäle:** Keine Änderung an Inhalt oder Zustellung in E-Mail · Telegram · SMS · Premium-SMS; Renderer-Gate und Mail-Validatoren werden nicht berührt.

## Estimated Scope

- **4a:** ca. 15 Dateien gelöscht, 5 Dateien umgezogen, ca. 90 Importzeilen angepasst, ca. +150 LoC neu (reine Funktion und Tests), zwei Anlege-Editoren angepasst; netto ca. −1500 bis −2000 LoC. Der Umzug ist ein reiner Pfadwechsel ohne Logikänderung; der Rename-Diff ist groß, der inhaltliche Diff klein.
- **4b:** ca. 20 Dateien, unter ±300 LoC, dazu Golden-Neuschrieb und Fresh-Eyes.
- **Effort:** medium (Risiko MEDIUM, in 4a an einer Stelle HIGH: Vorbelegung beim Anlegen; sonst mechanisch).

## Scope

### In Scope

- Entfernen der Oberfläche Wertebereiche (`CorridorEditor`, `CorridorEditorMobile`), der Zeithorizont-Chips (`HorizonChip`, `HorizonChips`), der Metrik-Checkbox (`MetricCheckbox`, `MetricGroup`) und der `MetricsEditorContextBar` samt Barrel-Zeilen und Tests entfallener Oberflächen.
- Umzug der Logikmodule aus `corridor-editor/` nach `shared/wetter-tab/` (Namen und Logik unverändert).
- Vorbelegung `corridors` beim Anlegen als reine Funktion plus einmaligem Effekt in `TripNewEditor` und `CompareNewEditor`; Entfernen der vier versteckten Mounts erst danach.
- Übersicht U3/U4, Listen-Sprünge und Menü-Wortlaut, Hilfe-, Onboarding- und Info-Texte, Glossar, Wächter-Test gegen alte Reiternamen, Golden neu, Pendant-Gate, Fresh-Eyes, Soll/Ist-Bild.

### Out of Scope

- **Bleiben bewusst bestehen (tragen den Übergangsreiter Zustellung bis S3b, #2795):** `shared/AlarmeTab.svelte` samt `alarme-tab/` und `trip-detail/AlarmeScheduleTab.svelte`, `shared/WeatherMetricsTab.svelte` samt `weather-metrics-tab/` (mit `SavePresetDialog`, `DayWindowCard`, `compareMetricSelection`), `shared/layout-tab/`, `alerts-tab/`. Ihre Nutzung im Reiter Zustellung ändert sich nicht.
- **S3b (#2795):** Inhalt je Kanal und Fläche, Roh/Einfach, Kanal-Tabelle; Neubau des Reiters Zustellung. Die Zustellung bleibt in beiden Schritten unberührt.
- **S8 (#2800):** Radar-Schalter für Trips.
- Neue Funktionen im Reiter Wetter, neue Grenzwerte oder Vorlagen; Änderungen an Go, Python, Renderer oder Mail-Inhalt.
- Die Gesamt-Spec selbst wird nicht geändert; ihre Abweichung (§7) ist im Changelog dieser Spec vermerkt.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Teil-PR 2 (#2892, live), Teil-PR 3 und #2913 (live) | Vorarbeit | Reiter Wetter (`organisms/wetter-tab/`), Leiste, Umleitungen `LEGACY` in `subscriptionTabs.ts`; `organisms/wetter-tab/` wird nur bei Importpfaden angefasst (`WetterTabInhalt.svelte`, `VorlageKarte.svelte`) |
| `shared/wetter-tab/wetterTabSpeicherung.ts`, `tripSpeicherung.ts` | Code | Zielordner des Umzugs; Speicherwege unverändert |
| `shared/corridor-editor/{corridorEditorState,compareMetricCatalogLoader,wertebereicheVergleichSpeicherung}.ts` | Code | Logikmodule, ziehen um (`corridorEditorState.ts` 872 Zeilen, Loader 309, Selbstspeicherer 274); Verwender u. a. `compareEditorSave.ts`, `compareHubHydration.ts`, `corridorPropsAus.ts`, `CompareTabs.svelte`, `WetterTabInhalt.svelte` |
| `shared/wetter-tab/ampelModell.ts` (`alarmZaehler`) | Code | Quelle für den „Alarm ab“-Zähler in U4 (derselbe wie im Reiter Wetter) |
| `shared/subscriptionTabs.ts` (`REITER_DEFINITION`, `LEGACY`) | Code | Reiter-Kennungen, bleibt unverändert |
| `docs/reference/i18n_glossar.md`, `i18n_konventionen.md` | Doku | Glossar zuerst, Katalog-Regeln, Zeile „Wertebereiche“ entfällt |
| `.claude/hooks/pendant_gate.py` (Pendant-Gate) | Gate | Prüfung AC-35, läuft in 4b zuerst |
| Playwright-Konfiguration Staging, zwei Staging-Konten | Test | Anlege-E2E mit zwei Nutzern (AC-46) |
| S3b (#2795), S8 (#2800) | Folgearbeit | Zustellung neu, Radar Trip |

## Affected Files

(Pfade ohne Präfix liegen unter `frontend/src/lib/components/`.)

### Schritt 4a

| File | Change Type | Description |
|------|-------------|-------------|
| `trip-detail/MetricCheckbox.svelte`, `trip-detail/MetricGroup.svelte`, `ui/horizon-chip/HorizonChip.svelte` (+`HorizonChip.test.ts`, `index.ts`), `molecules/HorizonChips.svelte`, `organisms/MetricsEditorContextBar.svelte` | DELETE | reine Barrel-Re-Exporte ohne Mount |
| `organisms/index.ts` (Z.19-20, 33), `trip-detail/index.ts` (Z.8-9), `molecules/index.ts` (Z.39) | MODIFY | Barrel-Zeilen raus (Rebase-Vorsicht: `molecules/index.ts` war Kollisionsfläche mit #2913) |
| `molecules/issue_578_molecules_organisms.test.ts`, `lib/__tests__/bausteine_waechter_regeln.ts`, `context_herkunft_baseline_ausserhalb_shared.test.ts`, `trip-detail/__tests__/f9Pruefstand.ts`, `frontend/e2e/issue-343-horizon-chips.spec.ts` | MODIFY/DELETE | Tests und Wächter der entfallenen Komponenten: löschen oder umstellen |
| `shared/corridor-editor/corridorEditorState.ts`, `compareMetricCatalogLoader.ts`, `wertebereicheVergleichSpeicherung.ts`, `__tests__/wertebereicheVergleichPruefstand.ts`, `corridorEditorState.test.ts` | MOVE | nach `shared/wetter-tab/`; Namen und Logik unverändert |
| `shared/corridor-editor/corridorMatch.ts` (+Test) | DELETE | einziger Verwender `CorridorEditorMobile.svelte` |
| ca. 90 Importzeilen (u. a. `compareEditorSave.ts`, `compareHubHydration.ts`, `corridorPropsAus.ts`, `alarmeVergleichSpeicherung.ts`, `versandVergleichSpeicherung.ts`, `compareMetricOrder.ts`, `weatherMetricsCompareSave.ts`, `wertebereicheAnzeige.ts`, `WeatherMetricsTab.svelte`, `CompareTabs.svelte`, `organisms/wetter-tab/WetterTabInhalt.svelte`, `VorlageKarte.svelte`, Wächter-Allowlists in `keine_hartkodierten_nutzertexte.test.ts`, `reaktivitaet_waechter.test.ts`, Farb- und Flush-Wächter) | MODIFY | Pfad `corridor-editor/` zu `wetter-tab/` |
| `shared/wetter-tab/anlegeVorbelegung.ts` | CREATE | reine Funktionen der Vorbelegung `corridors` (Trip aus `buildRoutePrefillRows`, Vergleich aus `belegeWertebereicheVor`/`buildComparePrefillRows`) |
| `shared/wetter-tab/__tests__/anlege_vorbelegung.test.ts` | CREATE | `node --test`, Fixtures aus `corridorEditorState.test.ts` |
| `trip-new/TripNewEditor.svelte` (Mounts, `handleVorbelegungFertig`, `defaultsBereit`) | MODIFY | versteckte Mounts raus; einmaliger Effekt nach Katalog und Metriken; Fertig-Signal auf jedem Ausgang |
| `compare-new/CompareNewEditor.svelte` (Mounts, `isFreshCompareCreate`, `syncToWizard`) | MODIFY | versteckte Mounts raus; Verhalten als Logik erhalten |
| `shared/corridor-editor/CorridorEditor.svelte`, `CorridorEditorMobile.svelte`, Komponenten-Tests in `__tests__/` (6 Dateien), `corridorEditorMobile.test.ts` | DELETE | Oberfläche Wertebereiche |
| `compare/corridorPropsAus.ts` | MODIFY/DELETE | schrumpft oder entfällt |
| E2E: `hub-wertebereiche-speichert-selbst`, `hub-wertebereiche-wertprops`, `issue-718-idealwert-validation`, `compare-editor-slice3`, `compare-hub-inline-edit`, `begriff-erklaerung`, `design-system-trip-vergleich`, `epic-138-block-b`, `issue-616-trip-one-surface`, `speicherung-ueberlebt-neuladen` u. a. | MODIFY/DELETE | je Datei: entfallene Oberfläche löschen, bleibendes Verhalten auf den Reiter Wetter umstellen |
| `frontend/e2e/s3a2794-teil4a-*.spec.ts` | CREATE | Anlege-E2E (AC-43 bis AC-46), Zwei-Nutzer-Lauf |
| Golden `tests/golden/f5_wertebereiche`, `f8_layout_korridor`, `f9_trip_flaechen`, `f10_vergleich_flaechen` | MODIFY | neu schreiben, soweit betroffen (`f7_alarme_tab` bleibt) |

### Schritt 4b

| File | Change Type | Description |
|------|-------------|-------------|
| `shared/hub-uebersicht/hubUebersichtModell.ts` (Z.133, 253-260), `HubUebersicht.svelte` | MODIFY | U3: Eyebrow der Karte nennt den Reiter Wetter statt `aktionen.reiter.wertebereiche`; `tripWetterAlarmAktiv()` berücksichtigt `alarm_ab` |
| `trip-detail/HubOverview.svelte` | MODIFY | U4: „bei Δ“ wird der „Alarm ab“-Zähler des Reiters Wetter (`alarmZaehler` aus `shared/wetter-tab/ampelModell.ts` auf der aufgelösten Ampel, Ladefehler „—“); Eyebrow- und Link-Texte „Wetter-Metriken“ zu „Wetter“ |
| `shared/subscriptionActions.ts`, `routes/trips/+page.svelte`, `routes/compare/+page.svelte`, `routes/+page.svelte` | MODIFY | Listen- und Startseiten-Sprünge, Menü-Wortlaut (AC-48) |
| `frontend/src/lib/i18n/messages/{de,en}/{hilfe,layout,alarme,aktionen,home,trip,vergleich,wertebereiche,bausteine}.json` | MODIFY | alte Reiternamen raus (Schlüsselliste siehe Implementation Details); Schlüssel ohne Verwender löschen |
| `shared/infoboxKeys.ts`, `lib/utils/cockpitHelpers568.ts`, `routes/hilfe/+page.svelte` | MODIFY | Info-Abschnitte, Startklar-Checkliste, Hilfe |
| `docs/reference/i18n_glossar.md` | MODIFY | Zeile „Wertebereiche“ (Z.24) entfällt; neue Begriffe stehen schon (Z.185-195) |
| `frontend/src/lib/i18n/__tests__/keine_alten_reiternamen.test.ts` | CREATE | Wächter (AC-49) |
| `frontend/e2e/s3a2794-teil4b-*.spec.ts` | CREATE | Übersicht, Sprünge, Englisch, Screenshots für Fresh-Eyes |
| Golden `tests/golden/f3_home_listen/cockpit_planung` u. a. | MODIFY | neu schreiben (`GZ_GOLDEN_SCHREIBEN`), Prüfstände anpassen |

## Implementation Details

### Schritt 4a: Reihenfolge verbindlich

1. **Re-Exporte löschen:** `MetricCheckbox`, `MetricGroup`, `HorizonChip`, `HorizonChips`, `MetricsEditorContextBar` samt Barrel-Zeilen und den zugehörigen Tests und Wächter-Einträgen. Diese Dateien haben keinen Mount; `svelte-check` und Build müssen danach grün sein.
2. **Umzug:** Die drei Logikmodule samt Prüfstand und Test ziehen nach `shared/wetter-tab/` (dort liegt schon `wetterTabSpeicherung.ts`). Reiner Pfadwechsel, keine Logikänderung; alle ca. 90 Importzeilen und die Wächter-Allowlists werden angepasst. `corridorMatch.ts` wird erst mit `CorridorEditorMobile` gelöscht.
3. **Vorbelegung als reine Funktion (TDD, `node --test`):** `anlegeVorbelegung.ts` liefert aus Katalog (`/api/metrics`), gewählten Metriken und Wizard-Zustand die Vorbelegung `corridors` (und im Vergleich `idealRanges`, `activeMetricKeys`, `metricAlertLevels`). Die Funktionen sind frei von Seiteneffekten; Fixtures stammen aus `corridorEditorState.test.ts`, die Fälle werden zuerst rot nachgewiesen. Die Orchestrierung ist ein einmaliger `$effect` in `TripNewEditor` und `CompareNewEditor`, getriggert nach Katalog und Metriken (`TripNewEditor`: Katalogabruf und `defaultsBereit`; `CompareNewEditor`: `catalogLoaded`).
4. **Erst dann löschen:** `CorridorEditor`, `CorridorEditorMobile`, `corridorMatch`, die Komponenten-Tests und alle vier versteckten Mounts (`TripNewEditor` zwei Stellen, `CompareNewEditor` zwei Stellen). Danach `corridorPropsAus.ts` verkleinern oder entfernen, Prüfstände und E2E umstellen.

Pflicht-Invarianten der Vorbelegung (heute über die versteckten Editoren, künftig über Funktion und Effekt):

- Trip: `corridors` landet im Anlege-POST; „Mit Standardwerten speichern“ (`defaultsBereit`) wird freigegeben, auch wenn keine Wetter-Metriken gewählt sind (`weatherMetrics.length === 0`); das Fertig-Signal `handleVorbelegungFertig` kommt genau einmal, auch ohne Vorbelegung.
- Vergleich: Vorbelegung nur bei leeren `wiz.corridors` (heute `isFreshCompareCreate`); Nutzereingaben werden beim Reiterwechsel nicht überschrieben; `idealRanges`, `activeMetricKeys`, `metricAlertLevels` landen wie heute im Wizard-Zustand.
- Der Wechsel zwischen Mobil und Desktop belegt nicht doppelt vor (heute Mount-XOR, künftig ein Effekt).
- Mandantentrennung: kein neuer Datenweg, `user_id` aus dem Auth-Kontext.

**Tests entfallener Oberflächen:** Rein auf die entfernte Oberfläche bezogene Tests (Komponenten-Tests Corridor-Editor, `HorizonChip`, `MetricCheckbox`, E2E `issue-343-horizon-chips`) werden gelöscht, damit kein Test Altcode am Leben hält. Tests, die ein bleibendes Verhalten prüfen (Speichern überlebt Neuladen, Idealwert-Validierung, Tagesfenster), werden auf den Reiter Wetter umgestellt, nicht gelöscht. Wächter werden nachgezogen, nicht aufgeweicht. Kein Mock-Theater.

### Schritt 4b: Reihenfolge

1. **Pendant-Gate zuerst (AC-35):** `pendant_gate.py` über die sieben Funktionen laufen lassen; Echte Pendants wurden in der Analyse nicht gefunden, Compare-seitige Reste sind Prop-Bündel (`compare/*PropsAus.ts`). Ein Fund wird behoben, nicht ausgenommen.
2. **U3/U4:** Karte „Wertebereiche“ der Orts-Übersicht führt in den Reiter Wetter (Ziel ist schon `wetter`, der Eyebrow-Text wird auf den Reiter Wetter umgestellt); `tripWetterAlarmAktiv()` berücksichtigt die Ampel-Alarmquelle wie der Server; die Trip-Zeile „bei Δ“ zeigt den „Alarm ab“-Zähler des Reiters Wetter (Details unter „Präzisierungen“). U1 und U5 (Kennzahlen, Versand-Historie) bleiben.
3. **Texte:** Alte Reiternamen aus dem Katalog DE und EN entfernen. Schlüsselliste aus der Analyse: `hilfe.alarme.*`, `layout.korridor.einleitung_route`, `alarme.metriken.keine_gewaehlt`, `alarme.tabelle.leer`, `alarme.vorschau.*`, `alarme.alarm_ab.umbau_hinweis`, `alarme.kanaele.kein_empfaenger` („Versand“), `aktionen.weather`/`aktionen.alarms` (nur Text; Schlüssel bleiben, weil `s3a2794_reiter_definition.test.ts` sie erwartet), `aktionen.reiter.wertebereiche`, `aktionen.uebersicht.uhrzeiten_festlegen`, `home.aktion.metriken` und `home.aktion.metriken_ziel`, `trip.uebersicht.*`, `trip.anlegen.alle_gpx`, `vergleich.neu.profil_hinweis`, `vergleich.neu.wetter_metriken`, `wertebereiche.vergleich.titel`, `bausteine.checkliste.layout` und `bausteine.checkliste.wertebereiche`, `tip.aria.wertebereiche`, `info.*`. Dazu `infoboxKeys.ts`, `cockpitHelpers568.ts` (Startklar-Checkliste), `routes/hilfe/+page.svelte`, `routes/+page.svelte`. Schlüssel, die nach 4a keinen Verwender mehr haben, werden gelöscht (der Wächter „Schlüssel ohne Verwender“ erzwingt das). Protokoll-Token bleiben unübersetzt.
4. **Glossar:** Zeile „Wertebereiche“ entfernen; die Begriffe Wetter, Vorlage, Ampel, Grenzen ändern, Alarm ab, Nicht im Briefing stehen bereits (Glossar zuerst).
5. **Wächter `keine_alten_reiternamen.test.ts`:** liest alle Kataloge DE und EN und schlägt an, wenn ein Nutzertext Wertebereiche, Alarme, Layout, Wetter-Metriken oder Versand als Reiter nennt. Erlaubt bleiben die Funktionsnamen (z. B. „Alarme“ als Funktion, „Layout je Kanal“ als Abschnitt der Zustellung) über eine ausdrücklich begründete Positivliste; die Unterscheidung wird im Test dokumentiert.
6. **Golden neu:** `GZ_GOLDEN_SCHREIBEN`, Prüfstände anpassen, Diff inhaltlich gegen die Erwartung prüfen.
7. **Fresh-Eyes:** Screenshots Trip und Orts-Briefing, Desktop und Mobil, gegen Mockup Fassung 3 vergleichen; Befunde beheben. Zum Abschluss das Soll/Ist-Bild an den PO (AC-50).

### Schritt 4b: Präzisierungen aus der Analyse vom 2026-11-12 (`docs/context/feature-2794-s3a-teil4b.md`)

- **Sprungziele stehen schon:** Trip-Liste, Orts-Liste und Startseite springen bereits auf `?tab=wetter` bzw. `?tab=zustellung`. AC-33 und AC-48 sind Wortlaut-Arbeit plus Live-Klicktest; die Ziele werden nicht umgebaut.
- **U4 Alarm-Zeile = Zähler des Reiters Wetter:** Mockup Fassung 3 arbeitet die Übersicht nicht aus („Unverändert“). Maßgeblich ist daher der Reiter Wetter: Die Alarm-Zeile der Trip-Übersicht zeigt denselben Zähler „{ausloesend} von {alarmfaehig} Metriken lösen einen Alarm aus“ (Funktion `alarmZaehler` aus `shared/wetter-tab/ampelModell.ts`, Katalog `wetter.alarm_ab.zaehler`), berechnet auf derselben aufgelösten Ampel (Vorlage plus Abweichungen, wie im Reiter Wetter). Kein zweites Rechenmodell. Kann die Vorlage nicht geladen werden, zeigt die Zeile „—“ statt einer geratenen Zahl. Gilt nur für den Trip; das Orts-Briefing hat keine Alarm-Zeile in der Übersicht.
- **„Alarm aktiv“ folgt der Server-Regel:** `tripWetterAlarmAktiv()` gilt zusätzlich als aktiv, wenn die Ampel-Alarmquelle des Servers greift (`src/services/trip_alert.py` `ampel_alarmquelle_aktiv()`: nur wenn `display_config.ampel` gesetzt ist, auf der aufgelösten Ampel mindestens eine aktive, alarmfähige Metrik mit „Alarm ab“ ungleich „nie“). Die Übersicht zeigt damit nie „aus“, während der Server tatsächlich alarmiert, und nie „an“, wenn er es nicht tut. Die bisherigen Quellen bleiben.
- **„Versand“ ist Abschnitt, kein Reiter:** Als Abschnitts- oder Funktionsname der Zustellung (Anker `#versand`) bleibt „Versand“ erlaubt, nie aber „Reiter/Tab Versand“. Der Wächter (AC-49) prüft Muster aus „Reiter“/„Tab“ plus altem Namen sowie die Reiter-Schlüssel selbst; jede Ausnahme steht mit Begründung auf der Positivliste.
- **Mockup-Abgleich auf den Umfang von 4b begrenzt:** Der Fresh-Eyes-Abgleich (AC-35, AC-50) bewertet, was 4b ändert: Übersicht, Listen-Menüs, Startseite, Hilfe, Texte und Reiterleiste. Abweichungen der Reiter-Seiten Wetter und Zustellung sowie des Seitenkopfs werden im Soll/Ist-Bild ausdrücklich dem Neustart „Einstellungen neu“ (#2913, PO-Entscheidung 2026-11-10) zugeordnet und in 4b nicht nachgebaut.

**Menü-Wortlaut (Vorschlag zur Freigabe mit dieser Spec, kein Extra-Halt):** Der Listen-Menüeintrag `aktionen.weather` („Wetter-Metriken“) heißt künftig „Wetter“ und führt in den Reiter Wetter; `aktionen.alarms` („Alarme“) bleibt als Funktionsname und führt in den Reiter Zustellung, weil die Alarm-Einstellung dort liegt, bis S3b sie neu ordnet.

## Expected Behavior

- **Input:** Anlegen von Trip und Orts-Briefing (Schnellweg „Mit Standardwerten speichern“ und Wizard), Öffnen von Hub und Übersicht, Klick auf Listen- und Startseiten-Sprünge, Hilfe lesen, Sprache Deutsch und Englisch.
- **Output 4a:** Oberfläche und Verhalten unverändert; die Vorbelegung der Wertebereiche beim Anlegen entsteht ohne die gelöschte Oberflächen-Komponente und ist im Anlege-POST bzw. im Wizard-Zustand identisch zu vorher.
- **Output 4b:** Übersicht, Listen, Hilfe und Texte nennen nur noch Übersicht · Etappen/Orte · Wetter · Zustellung als Reiter; Oberfläche beider Kontexte entspricht Mockup Fassung 3.
- **Side effects:** Keine Datenänderung, keine Migration, keine Änderung an Go, Python, Renderer oder Mail-Inhalt.

## Acceptance Criteria

Testschichten: **Kern** = ohne Netz (`node --test`, `svelte-check`, Build); **Live** = Playwright-E2E gegen Staging (`/e2e-verify`). Der Playwright-Code ist je AC derselbe für `route` und `vergleich`, wenn der AC beide Kontexte nennt.

- **AC-31:** Given der Stand nach Schritt 4a / When Hub, Anlege-Ketten und Hilfe durchlaufen werden / Then gibt es keine Oberfläche mehr für Wertebereiche (CorridorEditor, CorridorEditorMobile), Zeithorizont-Chips (HorizonChip, HorizonChips), Metrik-Checkbox (MetricCheckbox, MetricGroup) und MetricsEditorContextBar, der Reiter Alarme ist schon seit Teil-PR 2 weg, die Bausteine des Übergangsreiters Zustellung (`AlarmeTab`, `alarme-tab/`, `AlarmeScheduleTab`, `WeatherMetricsTab`, `weather-metrics-tab/`, `layout-tab/`, `alerts-tab/`) existieren weiter und arbeiten unverändert, und alle Aufrufer übersetzen und bauen ohne tote Importe
  - Test: Kern, `svelte-check` und Frontend-Build grün, `node --test` ohne Verweis auf gelöschte Dateien (Test, dass keine Quelldatei mehr aus `corridor-editor/` importiert, die Logikmodule liegen unter `shared/wetter-tab/`); Live, Playwright-Durchlauf Hub und Anlege-Kette je Kontext: kein Wertebereiche-Reiter, Reiter Zustellung zeigt Alarm-Baustein, Layout je Kanal und SMS-Schwellen wie zuvor; Tests der entfernten Oberflächen sind mit entfernt, kein Test hält Altcode am Leben.

- **AC-32:** Given die Übersicht eines Orts-Briefings und eines Trips / When der Nutzer sie öffnet / Then führt die Karte zu den Wertebereichen im Orts-Briefing in den Reiter Wetter und nennt dort den Reiter „Wetter“ (U3), die Zeile „Alarm bei Δ“ im Trip zeigt denselben „Alarm ab“-Zähler wie der Reiter Wetter („{x} von {y} Metriken lösen einen Alarm aus“, bei Ladefehler „—“) und gilt als aktiv, sobald der Server über die Ampel alarmiert (U4), und Kennzahlen und Versand-Historie (U1, U5) bleiben unverändert
  - Test: Kern, `node --test` auf das Übersichts-Modell (`hubUebersichtModell.ts`: Ziel `wetter`, Eyebrow-Schlüssel, `tripWetterAlarmAktiv()` mit und ohne `alarm_ab`); Live, Playwright je Kontext: Klick auf die Karte landet im Reiter Wetter, Text der Alarm-Zeile im Trip entspricht dem „Alarm ab“ des Reiters Wetter.

- **AC-33:** Given der Listen-Eintrag „Alarme“ in Trip-Liste, Orts-Liste und Startseite, der Eintrag „Wetter“ sowie die Hilfe- und Onboarding-Texte / When der Nutzer darauf klickt oder sie liest / Then landet er im Reiter Zustellung bzw. Wetter (je nach Ziel), und kein Text nennt noch Wertebereiche, Alarme, Layout oder Wetter-Metriken als Reiter (Funktionsnamen wie „Alarme“ im Menü bleiben erlaubt, siehe AC-48 und AC-49)
  - Test: Live, Playwright-Klick auf jeden Sprung (Trip-Liste, Orts-Liste, Startseite) mit Prüfung des aktiven Reiters; Kern, `node --test` über die Kataloge `de` und `en` (Wächter aus AC-49).

- **AC-34:** Given alle neuen und geänderten Texte beider Schritte / When die Oberfläche auf Deutsch und auf Englisch läuft / Then erscheinen alle über den Katalog in beiden Sprachen mit gleichen Platzhaltern, es gibt keinen hartkodierten Nutzertext, Protokoll-Token (z. B. `sms_code`, `compact_label`) bleiben unübersetzt, und die Begriffe Wetter, Vorlage, Ampel, Grenzen ändern, Alarm ab, Nicht im Briefing stehen vorab im Glossar
  - Test: Kern, bestehende Wächter `keine_hartkodierten_nutzertexte.test.ts` und Katalog-Parität (Platzhaltermengen DE = EN) in 4a und 4b grün; Live, Playwright mit `language=en` für Übersicht, Listen und Hilfe.

- **AC-35:** Given dieselbe Funktion in Trip und Orts-Briefing (Reiter Wetter, Zustellung, Vorlage-Karte, Metrik-Zeile, Grenzen-Editor, Karte Amtliche Warnungen & Radar, Karte Anpassen) / When der Code betrachtet wird / Then gibt es je Funktion genau eine Komponente unter `shared/` mit `context="route"|"vergleich"` und keine Compare-Komponente mit Trip-Pendant, und die von 4b geänderte Oberfläche beider Kontexte (Übersicht, Listen-Menüs, Startseite, Hilfe, Texte, Reiterleiste) entspricht dem Mockup Fassung 3 (Fresh-Eyes-Abgleich Desktop und Mobil); Abweichungen der Reiter-Seiten Wetter und Zustellung und des Seitenkopfs werden im Soll/Ist-Bild (AC-50) dem Neustart #2913 zugeordnet
  - Test: Kern, Pendant-Sperre des Gates (`pendant_gate.py`, `docs/reference/gates_und_ratschen.md`) grün und zu Beginn von 4b gelaufen; Live, Playwright-Screenshots beider Kontexte, Desktop und Mobil, für den Fresh-Eyes-Inspektor.

- **AC-43:** Given der Nutzer legt einen neuen Trip an (Schnellweg „Mit Standardwerten speichern“ oder Wizard bis Ende) / When der Nutzer speichert / Then enthält der Anlege-POST die vorbelegten `corridors`, der Knopf „Mit Standardwerten speichern“ wird freigegeben, auch wenn keine Wetter-Metriken gewählt sind, das Fertig-Signal der Vorbelegung kommt genau einmal (auch wenn nichts vorzubelegen ist), und der angelegte Trip enthält dieselben Wertebereiche wie vor der Entfernung des Corridor-Editors
  - Test: Kern, `anlege_vorbelegung.test.ts` (`node --test`) für Trip mit und ohne Metriken, Anzahl Fertig-Signale gleich eins; Live, Playwright legt einen Trip an und prüft die gespeicherte Trip-Datei (`corridors` vorhanden) sowie die Freigabe des Schnellwegs ohne Wetter-Metriken; bestehende Wächter `standardwerte_wartet_auf_wertebereiche_vorbelegung` und `trip_new_editor_weather_metrics_wiring` bleiben auf die neue Quelle umgestellt grün.

- **AC-44:** Given der Nutzer legt ein neues Orts-Briefing an / When er im Wizard den Reiter wechselt oder zurückgeht / Then werden die Wertebereiche nur belegt, wenn sie leer sind, bereits vom Nutzer geänderte Werte bleiben beim Reiterwechsel unverändert, und `idealRanges`, `activeMetricKeys` und `metricAlertLevels` stehen im Wizard-Zustand wie vor der Entfernung des Corridor-Editors
  - Test: Kern, `anlege_vorbelegung.test.ts` (leere Wertebereiche werden belegt, nicht leere bleiben, wiederholter Aufruf ändert nichts) und bestehender Wächter `compare_new_editor_postet_einmal` (genau ein Anlege-POST); Live, Playwright: Wert im Wizard ändern, Reiter wechseln, Wert bleibt; angelegtes Briefing enthält die geänderten Werte.

- **AC-45:** Given der Anlege-Wizard von Trip oder Orts-Briefing / When die Bildschirmbreite zwischen Mobil und Desktop wechselt (oder der Nutzer das Fenster dreht) / Then wird die Vorbelegung nicht doppelt ausgeführt, die Wertebereiche stehen genau einmal im Zustand, und der Anlege-POST wird weiterhin genau einmal gesendet
  - Test: Kern, `node --test` auf die Idempotenz der Funktion (zweiter Aufruf liefert denselben Zustand) und AST-Wächter, dass Effekt je Editor genau einmal läuft; Live, Playwright wechselt die Viewport-Größe mitten im Wizard und zählt die Anlege-Anfragen und die gespeicherten `corridors`.

- **AC-46:** Given zwei verschiedene Nutzer A und B auf Staging / When beide nacheinander einen Trip und ein Orts-Briefing anlegen (A mit geänderten Wertebereichen, B mit Standardwerten) / Then enthält jedes angelegte Objekt nur die Werte des eigenen Nutzers, B bekommt keine Werte von A, es gibt keinen neuen Datenweg, und `user_id` stammt aus dem Auth-Kontext, nie aus einem Fallback auf „default“
  - Test: Live, `frontend/e2e/s3a2794-teil4a-mandanten.spec.ts` mit zwei Konten, Dateizustand unter `data/users/<user_id>/` vorher und nachher; Kern, AST-Wächter gegen `"default"` als `user_id`-Fallback in den geänderten Dateien.

- **AC-47:** Given die umgezogenen Logikmodule (`corridorEditorState`, `compareMetricCatalogLoader`, `wertebereicheVergleichSpeicherung` samt Typ `IdealRange`) / When der Reiter Wetter im Hub geladen wird, der Katalog lädt, im Vergleich der Reiter gewechselt wird und Wertebereiche gespeichert werden / Then verhalten sie sich unverändert zu vorher: der Katalog-Loader füllt den Reiter Wetter, der Selbstspeicherer sichert Eingaben vor dem Reiterwechsel, und `IdealRange` wird von Speichern und Hydration wie bisher verwendet
  - Test: Kern, die umgezogenen Tests (`corridorEditorState.test.ts`, Prüfstand `wertebereicheVergleichPruefstand.ts`) laufen am neuen Ort unverändert grün; Live, bestehende E2E `hub-wertebereiche-speichert-selbst` und `speicherung-ueberlebt-neuladen` (auf den Reiter Wetter umgestellt) grün.

- **AC-48:** Given die Listen-Menüeinträge in Trip-Liste, Orts-Liste und Startseite / When der Nutzer das Menü öffnet / Then heißt der frühere Eintrag „Wetter-Metriken“ jetzt „Wetter“ und führt in den Reiter Wetter, „Alarme“ bleibt als Funktionsname und führt in den Reiter Zustellung, und beide Einträge sind auf Deutsch und Englisch vorhanden
  - Test: Live, Playwright öffnet das Menü je Liste, prüft die beiden Beschriftungen und das aktive Ziel nach dem Klick; Kern, `s3a2794_reiter_definition.test.ts` (Schlüssel `aktionen.weather` und `aktionen.alarms` bleiben) und Katalog-Parität.

- **AC-49:** Given das Glossar und alle Kataloge DE und EN / When die Kern-Schicht läuft / Then entfällt die Zeile „Wertebereiche“ im Glossar, und ein neuer Wächter `keine_alten_reiternamen.test.ts` schlägt an, sobald ein Nutzertext einen der alten Reiter (Wertebereiche, Alarme, Layout, Wetter-Metriken, Versand) als Reiter nennt, ohne dass Funktionsnamen auf einer dokumentierten Positivliste fälschlich anschlagen
  - Test: Kern, `node --test` auf `keine_alten_reiternamen.test.ts` mit einem positiven Fall (Katalog bereinigt, Test grün) und einem Negativ-Fall (Fixture mit altem Reiternamen, Test rot), plus bestehender Wächter „Schlüssel ohne Verwender“; Mutations-Gegenprobe: ein wieder eingefügter alter Reitername macht den Test rot.

- **AC-50:** Given Staging mit beiden Schritten / When der Fresh-Eyes-Abgleich für Trip und Orts-Briefing auf Desktop und Mobil gegen Mockup Fassung 3 gelaufen ist / Then liegt dem PO ein Soll/Ist-Bild in Alltagssprache vor, das je Kontext zeigt, was dem Mockup entspricht und was nicht, und offene Abweichungen sind benannt und je einem Plan zugeordnet (Abweichungen der Reiter-Seiten Wetter und Zustellung sowie des Seitenkopfs dem Neustart #2913); das Issue #2794 wird erst nach diesem Bild geschlossen
  - Test: Live, Playwright-Screenshots beider Kontexte, beider Breiten, beider Reiter (Übersicht bewertet; Wetter nur erfasst, seine Abweichungen werden #2913 zugeordnet und nicht in 4b behoben) gegen `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html`, Prüfung durch den Fresh-Eyes-Inspektor; Zeitbox ein Tag, keine unsichtbaren Prüf-Schleifen.

## Test Plan

### Automated Tests (TDD RED)

- [ ] **Kern Frontend (`node --test`):** `anlege_vorbelegung.test.ts` (AC-43 bis AC-45, rot vor der Umsetzung); umgezogene Tests am neuen Ort grün (AC-47); Übersichts-Modell (AC-32); Katalog-Parität und Wächter gegen hartkodierte Texte (AC-34); Wächter `keine_alten_reiternamen.test.ts` (AC-33, AC-49); AST-Wächter gegen Importe aus `corridor-editor/` und gegen `"default"`-Fallback (AC-31, AC-46).
- [ ] **Statische Prüfung:** `svelte-check` und Frontend-Build ohne tote Importe (AC-31) in 4a und 4b.
- [ ] **Go und Python:** nur falls betroffen; keine Produktivänderung erwartet. Backend-Tests mit Namens-Treffern (`tests/tdd/test_corridor_*`, `test_compare_metric_catalog_endpoint.py`) werden in 4a einzeln bestätigt. Es werden keine Dateien blind per `uv run pytest` ohne benannte Testdateien gestartet.
- [ ] **Tests entfallener Oberflächen:** löschen; Tests bleibenden Verhaltens auf den Reiter Wetter umstellen; Wächter nachziehen, nicht aufweichen; kein Mock-Theater (kein `Mock()`/`patch()`/`MagicMock`, die nur die eigene Annahme spiegeln, keine Dateiinhalt-Checks als Verhaltensnachweis außer `# doc-compliance-test`).
- [ ] **RED zuerst aus Nutzersicht:** 4a: AC-43 bis AC-46 (Anlege-Verhalten) rot, bevor die Vorbelegung umgebaut wird; 4b: AC-32, AC-33, AC-48, AC-49 rot, bevor Modell und Texte angepasst werden. Artefakte im Workflow registriert.
- [ ] **Mutations-Gegenprobe (Adversary):** mindestens Vorbelegung ohne `corridors` im POST, „Standardwerte“ ohne Freigabe bei leerer Metrik-Auswahl, Fertig-Signal zweimal oder nie, Vergleich überschreibt Nutzereingaben, doppelte Vorbelegung beim Breitenwechsel, alter Reitername im Katalog; jede Verfälschung muss einen Test rot machen. Mutationen nur per String-Ersetzung mit externer Sicherungskopie, nie `git checkout/stash/reset`.

### Live-E2E (nur `/e2e-verify` gegen Staging)

- [ ] 4a: Anlege-Ketten Trip und Orts-Briefing, Desktop und Mobil, Zwei-Nutzer-Lauf (AC-43 bis AC-47), Bestandstests der entfallenen Oberflächen gelöscht oder umgestellt.
- [ ] 4b: Übersicht, Listen- und Startseiten-Sprünge, Hilfe, `language=en` (AC-32, AC-33, AC-34, AC-48); Screenshots für Fresh-Eyes (AC-35, AC-50).
- [ ] Staging-Mailweg nicht nötig (Mail-Inhalt unverändert).

## Definition of Done

- [ ] 4a: AC-31, AC-43 bis AC-47 grün in ihrer Schicht, Kern-Schicht zu 100 % grün, alle 6 CI-Checks grün, Adversary-Verdict VERIFIED inklusive Mutations-Gegenprobe, `/e2e-verify` auf Staging grün, Prod-Deploy mit Selftest Exit 0.
- [ ] 4b: AC-32, AC-33, AC-35, AC-48 bis AC-50 grün, AC-34 in beiden Schritten, Pendant-Gate grün, Golden neu geschrieben und inhaltlich geprüft, Fresh-Eyes-Befunde behoben, `/e2e-verify` grün, Prod-Deploy mit Selftest Exit 0.
- [ ] Die Bausteine des Übergangsreiters Zustellung sind unverändert vorhanden; die Zustellung verhält sich wie vorher.
- [ ] Soll/Ist-Bild an den PO geliefert (AC-50); danach darf Issue #2794 geschlossen werden (nur bei Selftest Exit 0 des letzten Deploys).
- [ ] Glossar und Gesamt-Spec-Lieferplan nachgezogen (Hinweis auf die Detail-Spec in den Notizen der Lieferung, kein Eingriff in die freigegebenen ACs).

## Known Limitations

- **Zustellung bleibt Übergang:** `AlarmeTab`, `WeatherMetricsTab`, `layout-tab/` und `alerts-tab/` bleiben bis S3b (#2795) bestehen; Menüeintrag „Alarme“ führt solange in die Zustellung.
- **Nur Text, keine Neuordnung:** In 4b ändern sich nur Texte, Übersicht und Sprünge; die Neuordnung der Zustellung ist S3b.
- **Menü-Wortlaut:** „Wetter“ und „Alarme“ ist ein Vorschlag, der mit der Spec-Freigabe bestätigt wird; kippt der PO ihn, ändert sich nur Katalogtext.
- **Golden und Wächter:** Golden-HTML wird neu geschrieben; ein fachlich unerwarteter Unterschied im Diff gilt als Befund, nicht als zu akzeptierender Neuschrieb.
- **Radar Trip** fehlt weiter bis S8 (#2800).
- **Glossarzeile „Wertebereiche“ (Validierung 4b):** Die Zeile wird nicht gestrichen, sondern auf „Fachbegriff in Erklärtexten, kein Reiter mehr“ umgeschrieben, weil der Begriff in den Erklärtexten (`bausteine.*`) weiter vorkommt und nach der Regel „Glossar zuerst“ (ADR-0104) einen Glossareintrag braucht. Ziel von AC-49 (kein Reiter „Wertebereiche“ mehr) ist damit erfüllt; der Wächter `keine_alten_reiternamen.test.ts` prüft, dass die Zeile den Begriff nicht mehr als Reiter-Namen führt.

## Risiken

- **Verlust der Vorbelegung (HIGH):** Wird der Corridor-Editor vor der reinen Funktion gelöscht, verschwinden `corridors` im Anlege-POST und „Standardwerte“ bleibt blockiert. Gegenmaßnahme: verbindliche Reihenfolge (Funktion und Effekt vor Löschung), AC-43 bis AC-46, Mutations-Gegenprobe, eigener PR 4a.
- **Rename-Diff verdeckt Änderungen:** Gegenmaßnahme: Umzug als reiner Pfadwechsel in eigenem Commit, inhaltliche Änderungen getrennt.
- **Testumzug:** ca. 239 Frontend-Unit-, 63 E2E- und 53 Python-Dateien referenzieren Alt-Namen; viele betreffen bleibende Komponenten. Gegenmaßnahme: nur Tests rein entfallener Oberflächen löschen, Rest umstellen, Treffer einzeln prüfen.
- **Kollision mit parallelen Sitzungen:** gemeinsame Dateien (`molecules/index.ts`, E2E `speicherung-ueberlebt-neuladen`, `daywindow-*`, `s3a2794-teil3.helpers.ts`); `organisms/wetter-tab/` nur bei Importpfaden anfassen, vor dem PR auf `origin/main` rebasen.
- **Mandantentrennung:** keine neuen Datenwege; AC-46 mit zwei Nutzern.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue. ADR-0109 (Reiterstruktur, Pendant-Sperre), ADR-0104 (zweisprachig) und ADR-0101 (Read-Modify-Write) tragen die Entscheidung.
- **Rationale:** Die Aufteilung in 4a/4b und das Verschieben der Vorbelegung in eine reine Funktion sind lokale, umkehrbare Tech-Lead-Entscheidungen innerhalb dieser Scheibe; es wird keine Entscheidungsfläche geändert. Der Erhalt der Zustellungs-Bausteine folgt aus der bestehenden Staffelung (S3b offen) und weicht von keinem ADR ab.

## Changelog

- 2026-11-12: Initial spec created (Phase 3), Detail-Spec zu `feat_2794_s3a_reiter_wetter.md` (Teil-PR 4). AC-31 bis AC-35 aus der Gesamt-Spec übernommen und präzisiert; neue ACs AC-43 bis AC-50 (Vorbelegung beim Anlegen, Mandantentrennung, Umzug der Logikmodule, Menü-Wortlaut, Glossar und Wächter, Soll/Ist-Bild). Lieferung in zwei Schritten 4a/4b. Grundlage: Analyse `docs/context/feature-2794-s3a-teil4.md`.
- 2026-11-12: Präzisierung der Gesamt-Spec: §7 nennt `AlarmeTab`/`alarme-tab/`/`AlarmeScheduleTab` als „zu entfernen“; das widerspricht dem Übergangsreiter Zustellung, der sie mountet. Maßgeblich ist diese Detail-Spec (AC-31: sie bleiben bis S3b). Die Gesamt-Spec selbst wird nicht geändert.
- 2026-11-12: Präzisierung für Schritt 4b nach der Analyse `docs/context/feature-2794-s3a-teil4b.md` (4a ist live): U4 nutzt den Zähler des Reiters Wetter, „Alarm aktiv“ spiegelt die Server-Regel `ampel_alarmquelle_aktiv()`, „Versand“ als Abschnittsname erlaubt, Mockup-Abgleich auf den Umfang von 4b begrenzt und Reiter-Seiten-Abweichungen #2913 zugeordnet. AC-32, AC-35 und AC-50 entsprechend präzisiert, Affected Files, Dependencies und Reihenfolge nachgezogen, keine neuen ACs.
