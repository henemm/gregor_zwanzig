---
entity_id: rework_3020_altbausteine_entfernen
type: refactor
created: 2026-11-25
updated: 2026-11-26
status: draft
version: "2.1"
workflow: rework-3020-altbausteine-entfernen
tags: [rueckbau, wetter-tab, zustellung, epic-3122, epic-2795]
---

# Rückbau Alt-Bausteine Wetter/Zustellung, zweiter Teil (Schutz wiederherstellen, Restbestand löschen)

## Approval

- [ ] Approved

## Purpose

#3357 hat die alte Wetter-/Zustellungs-Oberfläche zum großen Teil gelöscht (12 von 54 Dateien, 60 Testdateien). Dabei sind Prüfungen weggefallen, deren Aussage am lebenden Code weiter gelten muss (Speichern ohne Datenverlust, Pause/Überspringen, Zwei-Nutzer-Trennung, Kanal-Vorgaben). Diese Spec stellt zuerst den Schutz wieder her (R1) und löscht dann den Restbestand toter Dateien (R2; ursprünglich 42, gemessen am 2026-11-26 noch 11, siehe Nachtrag). Nutzer sehen in keiner Scheibe einen Unterschied. Die PO-Freigabe, dass Alt-Bausteine, `telegram_kurzform` und die SMS-Schwellen mit #3020 fallen, liegt vor (#3036, 2026-11-24).

## Source

- **File:** `frontend/src/lib/components/` (Restbestand laut Abschnitt Scope), Tests unter `frontend/src/lib/**/__tests__/`, `tests/fixtures/einstellung_gleich_mail/`
- **Identifier:** ursprünglich 42 Dateien (4 454 Zeilen), 6 Barrel-Zeilen; in R2 verbleiben 11 Dateien und 6 Barrel-Zeilen (Nachtrag). 24 + 33 Zeilen der Testtabelle, 145 entfallene Testfälle, 15 gestrichene Katalogfälle

Schicht: **Frontend** und Testunterbau, CI-Konfiguration. **Kein** Python-Produktions- und kein Go-Code.

**Querschnitts-Prüfpunkte:**
- **Trip/Ortsvergleich-Teilung:** Es entsteht kein neuer Baustein. R1 prüft die lebenden gemeinsamen Bausteine (`shared/wetter-tab`, `organisms/wetter-tab`, `shared/zustellung-tab`) je mit `context="route"` und `"vergleich"`. R2 löscht gemeinsamen Code ohne Importeur. Das Pendant-Paar ist schon weg: `.claude/hooks/pendant_gate.py` nennt keine der 42 Dateien und wird nicht angefasst (keine Sperren-Freigabe nötig).
- **Mandantentrennung:** Kein Endpoint wird geändert. Jede wiederhergestellte Speicher- und Ladezusicherung läuft mit zwei verschiedenen Nutzern (AC-2). `user_id` kommt aus dem Auth-Kontext, nie `"default"`.
- **Kanäle:** E-Mail, Telegram, SMS, Premium-SMS: Briefing- und Alarm-Inhalt bleibt unverändert, weil kein Renderer-, Python- oder Go-Code berührt wird; R1 sichert zusätzlich die Kanal-Vorgaben der Bedienung gegen die Auslieferung (AC-4).

## Estimated Scope

- **R1 Schutz wiederherstellen:** 0 Produktionszeilen; geschätzt 20 bis 30 Testdateien neu oder geändert, Testzeilen Schätzung +1 500 bis +3 000 (nicht gemessen).
- **R2 Restbestand löschen (Stand Nachtrag 2026-11-26, gemessen):** 11 Produktionsdateien gelöscht, 6 Barrel-Zeilen, ca. 17 Test- und Listendateien angepasst (13 rote Testdateien, 1 Python-Fall, `ein_katalog_ausnahmen.json`, rote Liste, `fallliste_editor.json`), Katalogschlüssel, Ratschen, Doku. Fast nur Löschungen: Produktion −1 545 Zeilen (gemessen), Tests geschätzt −500 bis −900 Zeilen.
- **Das Limit von 250 LoC / 4-5 Dateien wird in beiden Scheiben bewusst überschritten**; die Freigabe dieser Spec deckt das ab (R2 fast nur Löschungen, R1 nur Tests). Je Scheibe wird `loc_limit_override` gesetzt.
- **Effort:** high, zwei Scheiben, je eigener PR.

## Scope

### Scheiben

Eine Spec, eine Freigabe, zwei Scheiben mit je eigenem PR. Jede Scheibe ist grün (alle 6 CI-Checks), einzeln auslieferbar und einzeln per Revert zurückrollbar. Reihenfolge fest **R1 → R2**: Die Schutzlücke besteht schon auf `main`, und das Löschen macht sie nicht kleiner.

| Scheibe | Inhalt | Produktion gelöscht |
|---|---|---|
| R1 Schutz wiederherstellen | Prüfungen aus #3357 am lebenden Code wieder herstellen, Prüfkatalog, Testtabelle, Wächter | keine |
| R2 Restbestand löschen | verbliebene Dateien, 6 Barrel-Zeilen, Testfolgen, Katalogschlüssel, Ratschen | ursprünglich 42 Dateien / 4 454 Zeilen; gemessen noch 11 Dateien (Nachtrag) |

### R1: Umfang

Quelle zum Portieren ist Commit `8b9749601` (`git show 8b9749601:<pfad>`); die Helfer haben sich geändert, daher nicht blind kopieren. Reihenfolge (Vorrang Datenverlust und Zwei-Nutzer):

1. skip_next-Schutz, 2. If-Match/keepalive-Flush an Zustellung, 3. `show_night_block` „aus bleibt aus“ (`trip_night_block_schalter_nutzlast` ist von 7 auf 1 Fall gekürzt), 4. Feld-Erhalt samt `sms_threshold`, 5. Roundtrip je Feld, 6. Retry-/412-Fälle, 7. zwei Nutzer beim Laden, 8. Kanal-Vorgaben gleich Auslieferung (Telegram, SMS, Premium-SMS), 9. Reiter Wetter und Zustellung an einem Controller; danach 10. Telegram-Grenze Orte (Katalog 23 bis 34), 11. Klebeschicht-Ladetests, 12. Übriges.

Arbeitspakete:
- **(a)** Die 33 Zeilen mit Beleglücke der 57 Zeilen „umstellen“ in `docs/specs/modules/rework_3020_testtabelle.md`: 23 mit Vermerk „neu in S3/S4“, 16 mit Beleg, den es auf `main` nicht gibt (u. a. `wetter_tab_karte_mitspeichern_3020`, `feld_erhalt_ohne_ausnahme`, `trip_python_skip_next_ohne_412`, `s3a2794_speicher_owner_waechter`; 6 mit beidem).
- **(b)** Die übrigen 24 Zeilen: je Zeile prüfen, ob der genannte Fall in der Belegdatei noch steht (#3357 hat u. a. `trip_reiter_roundtrip_jedes_feld` von 26 auf 13 und `trip_reiter_nutzlast_nur_eigene_felder` von 12 auf 8 Fälle gekürzt).
- **(c)** Die 145 in weiterlaufenden Testdateien entfallenen Fälle (Namensvergleich, Beleg `testnamen_diff.txt`; umbenannte zählen mit) je Fall einordnen: umbenannt / prüfte nur toten Quelltext / Zusicherung fehlt, dann Beleg schreiben.
- **(d)** Die 15 gestrichenen grünen Katalogfälle „Einstellung = Mail“ in `tests/fixtures/einstellung_gleich_mail/fallliste_editor.json` (SMS-LADEN-A/B, zwölf F3/F3N-Fälle Trip/Orte, P12-TL3-ORTE-KURZSTIL): je Fall mit lebendem Beleg wieder eintragen oder Streichung begründen; Verweisänderungen in `fallliste_trip.json` und `fallliste_orte.json` auswerten.
- **(e)** `tests/tdd/test_einstellung_gleich_mail_fallliste.py`: die heute leer laufende `praefixe`-Prüfung (Zeile 492 bis 512) auf die heutigen Testdateien richten; sie darf nicht vakuum-grün sein.
- **(f)** Rückbau-Wächter `frontend/src/lib/__tests__/rework_3020_rueckbau_waechter.test.ts`, rote Liste `rework_3020_rote_liste.ts`, Umfang `rework_3020_umfang.ts` und die Probe (`rework_3020_probe_loeschung.test.ts`, `rework_3020_probe_hooks.mjs`) liegen **nicht** im Baum (nur in `8b9749601`): neu auf den Restbestand ausrichten, Testtabelle fortschreiben.
- **(g)** LOW-Befunde aus der Adversary-Runde, soweit noch zutreffend (R2-F1 am 25.11. bestätigt, Zeile 322-334): R2-F1 (Attribute der Karten-Einbettung in `organisms/wetter-tab/WetterTabInhalt.svelte` unbewacht: `{context}`, `onUebernahme`, `{createMode}`), R2-F2 (Ersatzbeleg muss Testdatei mit Testname sein, kein Verzeichnis), R2-F3 (Zahl der Tabellenzeilen im Wächter festhalten), R2-F4 (`wetter_tab_karte_mitspeichern_3020` in die Liste der lebenden Helfer-Nutzer).

Regeln: Jede wiederhergestellte Zusicherung bekommt eine **Mutationsprobe am lebenden Code** (String-Ersetzung mit externer Sicherungskopie, nie `git checkout/stash/reset`). Fälle zu #3355 (Vollkopie `report_config` im Reiter Wetter) bleiben ausstehend markiert mit Verweis auf #3355; ihre Anzahl steht im Wächter und in der Testtabelle. Findet R1 einen echten Fehler im lebenden Code, entsteht ein eigenes Bug-Issue, der Fall steht ausstehend markiert mit Verweis, und er wird **nicht hier behoben**. Dazu gehören #1510 AC-4 (Briefing-Mail bei unbestätigter Adresse), die Fachkurzform je Größe in Orten und die Katalogfälle 35 bis 37 „nur morgens/abends“: R1 klärt sie, das Ergebnis steht in der Testtabelle.

### R2: Umfang (ursprünglich 42 Dateien; gültiger Stand siehe Nachtrag)

Pfade relativ zu `frontend/src/`. Menge = Schnittmenge aus `tot_nach_3357.txt` (Messung auf `c8329fea4`) mit den Listen A (26) und B (16) aus `umfangslisten.md`; `docs/artifacts/` ist gitignored, daher stehen die Pfade hier. **Hinweis:** 31 dieser 42 Dateien sind inzwischen auf `main` gelöscht, es gilt der Nachtrag unten.

- `lib/components/compare/` (5): `compareHourlyMetricDefs.ts`, `hourlyFriendlyMap.ts`, `layoutPreviewRows.ts`, `versandPropsAus.ts`, `wetterMetrikenPropsAus.ts`
- `lib/components/molecules/` (1): `GrundauswahlLeerHinweis.svelte`
- `lib/components/organisms/` (4): `AlertsCard.svelte`, `MetricOffShelf.svelte`, `OutboxCard.svelte`, `PresetRail.svelte`
- `lib/components/shared/` (2): `OutputLayoutEditor.svelte`, `reportConfigDirty.ts`
- `lib/components/shared/layout-tab/` (6): `LTCapNote.svelte`, `LTChannelPicker.svelte`, `LTCutLine.svelte`, `LayoutTab.svelte`, `channelLayoutsDirty.ts`, `ltIdealRange.ts`
- `lib/components/shared/versand-tab/` (7): `VTBriefingChannels.svelte`, `VTLaufzeitRoute.svelte`, `VTLaufzeitVergleich.svelte`, `VTNextBriefing.svelte`, `VTSchedulePlan.svelte`, `channelContactLabel.ts`, `vtBriefingChannelsText.ts`
- `lib/components/shared/weather-metrics-tab/` (9): `AggregationMetricRow.svelte`, `MultiSymbolMetricRow.svelte`, `ThresholdMetricRow.svelte`, `WeatherV2Grundauswahl.svelte`, `WeatherV2PresetBar.svelte`, `compareAggregationGrouping.ts`, `nurEinBericht.ts`, `outlookFriendlyCapability.ts`, `wertebereicheAnzeige.ts`
- `lib/components/trip-detail/` (8): `ActiveMetricRow.svelte`, `BucketSection.svelte`, `BucketSectionOff.svelte`, `ChannelLimitMarkers.svelte`, `PresetRow.svelte`, `TablePreview.svelte`, `WeatherV2Kanaele.svelte`, `weatherSaveGate.ts`

Dazu 6 Barrel-Zeilen: `lib/components/organisms/index.ts` (`OutputLayoutEditor`, `OutboxCard`, `AlertsCard`, `PresetRail`, `MetricOffShelf`) und `lib/components/trip-detail/index.ts` (`TablePreview`).

**Nie löschen** (lebend laut Spec #3036 Nr. 5): `channelConnectionStatus.ts`, `sendTargetLabel.ts`, `dayWindowClamp.ts`, `nextBriefingText.ts`, `naechstesBriefingLader.svelte.ts`, `nextBriefingLoad.ts`, `reportConfigPayload.ts`, `mergeReportConfig.ts`, `ltChannels.ts`, `kanalStilSpeicherung.ts`. Lebend und unangetastet außerdem `weatherMetricsCompareSave.ts`, `compareChannelMetricLayouts.ts`, `mailInhaltZustand.ts`, `mailInhaltKonstanten.ts`, `pickEigenfelder.ts` (Altfeld-Stellen darin gehören zum Rest von #3297).

**Nicht Umfang:** Liste C (24 Dateien, fachfremd), `mobile/Drawer.svelte`, `molecules/CompareStatusRow.svelte`, `molecules/ScoreToggle.svelte` (neu als tot gemeldet), #3358 (Vorlage folgt der Fortbewegung), #3355, #3351, Altfeld-Stellen in lebenden Dateien.

### R2: Nachtrag 2026-11-26 (gemessener Restbestand)

Quelle: `docs/context/rework-3020-r2-restbestand.md`, gemessen auf `origin/main` d7180c9e8. **Dieser Nachtrag ersetzt für R2 die Zahl 42 durch die gemessene Zahl 11; die ACs bleiben inhaltlich, nur ihre Zahlen werden angepasst.**

**Schon gelöscht (31 von 42):** durch #3298 (9bf9c2dbf), #3301 (02f684e86), #3366 (PR #3386, `shared/layout-tab/*`), #3383/#3384/#3385 (Waisen S1 bis S4) und #3389 (tote Exporte, PR #3408). Ihre Löschung bewacht der Rückbau-Wächter über `VORAB_GELOESCHT` und die Waisen-Wächter (`trip_pfad_altfeld_loeschnachweis_3297.test.ts`). Dazu gehören u. a. `compare/compareHourlyMetricDefs.ts`, `compare/hourlyFriendlyMap.ts` und die 6 Dateien `shared/layout-tab/*`.

**Restbestand (11 Dateien, alle ohne Produktions-Importeur außer Barrel und gegenseitig), Pfade unter `frontend/src/lib/components/`:**

- `organisms/`: `AlertsCard.svelte`, `MetricOffShelf.svelte`, `OutboxCard.svelte`, `PresetRail.svelte`
- `shared/`: `OutputLayoutEditor.svelte`
- `trip-detail/`: `ActiveMetricRow.svelte`, `BucketSection.svelte`, `BucketSectionOff.svelte`, `ChannelLimitMarkers.svelte`, `PresetRow.svelte`, `TablePreview.svelte`

Dazu die 6 Barrel-Zeilen (`organisms/index.ts` fünf, `trip-detail/index.ts` eine). Kein Python-/Go-Produktionscode; die Katalogschlüssel (i18n DE/EN) dieser Bausteine werden verwaist und fallen (AC-9).

**Probe-Löschung (Wegwerf-Kopie, volle Frontend-Suite):** Baseline 118 rote Dateien (umgebungsbedingt), Probe 129; neu oder stärker rot genau 13 Dateien (rote Fälle Probe/Baseline), je mit Entscheid (AC-8). Die Entscheide gelten nur als Streichen oder Kürzen, nie als Lockern eines Wächters.

| Testdatei | rot | Entscheid |
|---|---|---|
| `components/molecules/issue_578_molecules_organisms.test.ts` | 16/0 | Fälle für AlertsCard/OutboxCard/PresetRail/MetricOffShelf streichen (prüfen nur Alt-Bausteine) |
| `components/shared/__tests__/OutputLayoutEditor.test.ts` | 4/0 | Datei löschen (prüft nur den gelöschten Baustein) |
| `components/trip-detail/bug_499_skala_label.test.ts` | 5/0 | Fälle für ActiveMetricRow/TablePreview streichen, Datei löschen falls kein lebender Anteil bleibt |
| `components/shared/layout-tab/__tests__/layout_korridor_sprache.test.ts` | 1/0 | OutputLayoutEditor-/BucketSection-Fall streichen; f8-Prüfstand um Alt-Bausteine kürzen |
| `components/trip-detail/__tests__/trip_hub_sprache.test.ts` | 4/0 | f9-Prüfstand (`f9Altbausteine.ts`) um gelöschte Bausteine kürzen, Datei löschen falls kein lebender Anteil bleibt |
| `components/__tests__/bausteine_sprache.test.ts` | 5/0 | Einträge OutboxCard/PresetRail streichen |
| `i18n/__tests__/katalog_schluessel_haben_verwender.test.ts` | 2/0 | verwaiste DE/EN-Schlüssel entfernen (AC-9), Wächter nicht lockern |
| `i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts` | 2/0 | Eintrag OutputLayoutEditor streichen |
| `i18n/__tests__/reaktivitaet_waechter.test.ts` | 4/0 | Eintrag OutputLayoutEditor streichen |
| `__tests__/bausteine_waechter.test.ts` | 2/0 | 7 BESTAND-Einträge und 4 AUSNAHMEN-Einträge streichen, `BESTAND_OBERGRENZE` 162 → 155 |
| `__tests__/ink4_waechter.test.ts` | 1/0 | Einträge MetricOffShelf/PresetRail streichen |
| `__tests__/rework_3020_rueckbau_waechter.test.ts` | 15/2 | `STAND` 1 → 2 (erwartet), `VORAB_GELOESCHT` bleibt |
| `__tests__/rework_3020_probe_loeschung.test.ts` | 12/10 | nach der Löschung auflösen (sein Prüfling existiert nicht mehr); `rework_3020_probe_hooks.mjs` wird mit aufgelöst |

Außerhalb der Frontend-Suite: `tests/tdd/test_issue_289_surface_tokens.py::test_preset_row_color_mix_uses_surface0` (liest `PresetRow.svelte`) wird gestrichen; `tests/unit/ein_katalog_ausnahmen.json`: die 2 Einträge `BucketSectionOff` und `TablePreview` werden gestrichen.

**Ratschen:** `BESTAND_OBERGRENZE` 162 → 155 (7 BESTAND-Einträge), AUSNAHMEN 4 Einträge streichen. E2E: keine Änderung (die Namen stehen nur in Kommentaren der E2E-Specs), `E2E_MIN_SPECS` und `E2E_MIN_EXECUTED_HAUPT` bleiben unverändert (die Senkung 86 → 85 aus Version 2.0 entfällt, `issue-1093-unit.spec.ts` ist nicht mehr betroffen). svelte-check-Baseline wird nur gesenkt, falls CI weniger misst. `metricsEditor.ts` nennt `TablePreview` nur im Kommentar (keine Änderung).

**Pflegepunkte aus #3385:** `rework_3020_rote_liste.ts` Einträge E070/E071/E080/E081/E086 bis E088 (ihre Testdateien sind bereits gelöscht) und `_hinweis` in `tests/fixtures/einstellung_gleich_mail/fallliste_editor.json` nachziehen.

**Doku (AC-12):** `docs/reference/{frontend_components,api_contract,gates_und_ratschen,metric_output_matrix}.md`, `docs/features/architecture.md` und zusätzlich `docs/features/epic-1273-compare-one-surface.md` auf gelöschte Bausteine prüfen und als entfernt kennzeichnen.

**Testtabelle:** `docs/specs/modules/rework_3020_testtabelle.md` bekommt den Abschnitt „R2“ mit genau diesen 13 Dateien plus dem Python-Fall, je Entscheid und Begründung (AC-8). Anmerkung zur Fassung 2.1: Der Abschnitt wird in der Umsetzung (Phase TDD) eingetragen; die Tabelle oben ist seine verbindliche Vorlage.

### Affected Files

| File | Change Type | Scheibe | Description |
|------|-------------|---------|-------------|
| 20 bis 30 Testdateien unter `frontend/src/lib/**/__tests__/` (Namen legt die Testtabelle fest) | CREATE/MODIFY | R1 | wiederhergestellte Zusicherungen am lebenden Code |
| `docs/specs/modules/rework_3020_testtabelle.md` | MODIFY | R1, R2 | heute noch im Schema S1 bis S4: auf R1/R2 umstellen; Zeilen auf Restbestand, Mutationsproben, Anzahlen; R2: Abschnitt mit 13 Dateien + Python-Fall |
| `frontend/src/lib/__tests__/rework_3020_rueckbau_waechter.test.ts`, `rework_3020_rote_liste.ts`, `rework_3020_umfang.ts`, `rework_3020_probe_loeschung.test.ts`, `rework_3020_probe_hooks.mjs` | CREATE (R1) / MODIFY, DELETE (R2) | R1 (wächst in R2) | Wächter und eingefrorene Liste; R2: `STAND` 1 → 2, Probe-Test und Hooks aufgelöst, rote Liste nachgepflegt |
| `tests/fixtures/einstellung_gleich_mail/{fallliste_editor,fallliste_trip,fallliste_orte}.json` | MODIFY | R1, R2 | R1: 15 Fälle, Verweise; R2: `_hinweis` in `fallliste_editor.json` |
| `tests/tdd/test_einstellung_gleich_mail_fallliste.py` | MODIFY | R1 | `praefixe` nicht mehr leer |
| 11 Dateien (siehe Nachtrag) | DELETE | R2 | Restbestand (31 weitere der ursprünglich 42 sind schon gelöscht) |
| `lib/components/organisms/index.ts`, `lib/components/trip-detail/index.ts` | MODIFY | R2 | 6 Barrel-Zeilen |
| 13 Testdateien laut Nachtrag (Probe-Löschung gemessen) | DELETE/MODIFY | R2 | je rotem Test ein Entscheid |
| `tests/tdd/test_issue_289_surface_tokens.py` | MODIFY | R2 | Fall `test_preset_row_color_mix_uses_surface0` streichen |
| `frontend/src/lib/__tests__/bausteine_waechter_regeln.ts` | MODIFY | R2 | `BESTAND_OBERGRENZE` 162 → 155 |
| `tests/unit/ein_katalog_ausnahmen.json` | MODIFY | R2 | 2 Einträge (`BucketSectionOff`, `TablePreview`) streichen |
| `frontend/src/lib/i18n/messages/{de,en}/*.json` | MODIFY | R2 | verwaiste Schlüssel (Zahl in R2 neu messen) |
| `.github/workflows/ci.yml` (svelte-check-Baseline) | MODIFY | R2 | nur senken, falls CI weniger misst; E2E-Positivliste und `E2E_MIN_*` unverändert |
| `docs/reference/{frontend_components,api_contract,gates_und_ratschen,metric_output_matrix}.md`, `docs/features/architecture.md`, `docs/features/epic-1273-compare-one-surface.md` | MODIFY | R2 | gelöschte Bausteine nicht als bestehend beschreiben |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/rework-3020-altbausteine-entfernen.md` (Abschnitt Analysis) | Kontext | Messung auf `c8329fea4` |
| `docs/context/rework-3020-r2-restbestand.md` | Kontext | Messung des Restbestands und der Probe-Löschung auf `d7180c9e8` (Nachtrag) |
| `docs/artifacts/rework-3020-altbausteine-entfernen/` (gitignored) | Belege | `tot_nach_3357.txt`, `umfangslisten.md`, `restbestand_tests.txt`, `del_3357.txt`, `testnamen_diff.txt` |
| `docs/specs/modules/feat_3297_trip_pfad_ohne_altfelder.md` | Spec | AC-7 (Löschliste) und AC-10 (Test-Zuordnung) von #3297 sind erfüllt; diese Spec übernimmt den Rest |
| ADR-0112, ADR-0124 | ADR | Ratschen nur senken; eine Tabelle |
| `tests/tdd/test_einstellung_gleich_mail_fallliste.py` | Wächter | Abdeckungsmatrix Prüfkatalog |
| `tests/unit/test_e2e_positivliste_ratschen_bindung.py` | Wächter | bindet `E2E_MIN_SPECS`/`E2E_MIN_EXECUTED_HAUPT` |
| `frontend/src/lib/i18n/__tests__/katalog_schluessel_haben_verwender.test.ts` | Wächter | tote Katalogschlüssel, bleibt ungelockert |
| `npm run elementliste:abgleich` (`scripts/elementliste_abgleich.ts`) | Skript | Nachweis „keine sichtbare Änderung“ |
| #3355, #3298, #3301, #3297, #3358, #3351, #3385, #3389 | Issues | #3355 offene Fälle; #3298 behält Typen und Text-Sperre; #3301 und #3298 sind bereits geschlossen (Nachweis-Kommentar an #3020); #3385 Pflegepunkte; #3389 tote Exporte |

## Implementation Details

1. **R1 je Zeile entscheiden.** Für jede Zeile und jeden entfallenen Fall gilt: lebender Beleg vorhanden (Verweis nachziehen, Beleg muss eine Testdatei **mit Testname** sein) oder Zusicherung am lebenden Modul neu schreiben (Ablauf: Test rot gegen verfälschten lebenden Code, grün gegen echten) oder streichen mit Begründung „Ohne lebende Aussage:“, nur wenn die Aussage ausschließlich eine nicht mehr vorhandene Oberfläche betraf. Bei Zweifel schreiben, nicht streichen.
2. **Lebende Module** für R1: `shared/wetter-tab/ampelSchreiben.ts`, `organisms/wetter-tab/WetterTabInhalt.svelte` und `WasStehtWoKarte.svelte`, `shared/zustellung-tab/zustellungSpeicherung.ts`, `kanalStilSpeicherung.ts`; die Helfer der Prüfstände (`f9Pruefstand`, `tripMehrreiterPruefstand` u. a.) bleiben, soweit sie lebenden Code laden.
3. **Prüfkatalog.** Regel je Fall: wieder eintragen mit lebendem Beleg, sonst Streichung begründen. Die Zahl der Fälle sinkt höchstens um begründet gestrichene Fälle. Der Test `test_einstellung_gleich_mail_fallliste.py` wird nicht gelockert, nur die Prüfung der Testdateien wird scharf gestellt.
4. **R2 Ablauf (Reihenfolge fest):** (1) Vor Beginn prüfen, ob eine andere Sitzung an den Dateien des Restbestands arbeitet. (2) **Probe-Löschung in einer Wegwerf-Kopie, nie im Arbeitsbaum** (am 2026-11-26 für die 11 Dateien und 6 Barrel-Zeilen erfolgt, Ergebnis im Nachtrag; `vite build`, `svelte-check` und der Probe-Revert laufen in CI bzw. vor dem PR erneut). (3) Testtabelle: je rotem Test ein Entscheid (löschen / umstellen / Ersatzbeleg) mit Begründung. (4) Rückbau-Wächter wird RED: `STAND` 1 → 2 (Dateien existieren noch). (5) Löschen, Wächter grün. (6) Verwaiste Katalogschlüssel DE/EN und Ratschen mitziehen. #3301 und #3298 sind bereits geschlossen; es folgt nur ein Nachweis-Kommentar an #3020, kein erneutes Schließen.
5. **Ratschen.** `BESTAND_OBERGRENZE` um genau die Zahl der entfernten `BESTAND`-Einträge senken (R2: 162 → 155, 7 Einträge), AUSNAHMEN 4 Einträge streichen. E2E-Ratschen `E2E_MIN_*` bleiben unverändert, svelte-check-Baseline nur senken, falls CI weniger misst. Nie anheben. Keine Gate-Konfiguration (`openspec.yaml`) ändern; kein Schritt dieser Spec braucht eine menschliche Sperren-Freigabe (override).
6. **Katalogschlüssel.** In R2 neu messen; Schlüssel in der Scheibe entfernen, in der der letzte Verwender fällt; `katalog_schluessel_haben_verwender` bleibt ungelockert, Pin-Tests (`deutsch_unveraendert`) nur um entfernte Schlüssel kürzen. Neue Nutzertexte entstehen nicht.
7. **Altdaten.** Keine Speicherstelle wird geändert. Gespeicherte Altfelder (`telegram_kurzform`, SMS-Schwellen, `channel_layouts` u. a.) bleiben im Bestand (Merge, nie Replace; ADR-0101, CLAUDE.md Daten-Schema-Pflicht); sie verlieren nur ihre tote Bedienoberfläche.
8. **Abgrenzung zu #3297.** Dessen Löschliste ist durch #3357 erfüllt; #3297 und #3020 werden nicht zusammen geschlossen. #3020 schließt erst nach R2.

## Expected Behavior

- **Input:** Nutzer öffnet Trip-Hub, Orte-Hub, Trip-Anlegen oder Orte-Anlegen (DE/EN, Computer und Handy), speichert Wetter- und Zustellungs-Einstellungen.
- **Output:** Identisch zu vorher; kein Element, Text oder Verhalten fällt weg oder kommt hinzu.
- **Side effects:** R1 mehr und schärfere Tests; R2 11 Dateien weniger im Bundle, kleinere Test- und Katalogmenge, niedrigere Ratschen-Obergrenzen.

## Definition of Done

- [ ] **R1:** AC-1 bis AC-6 und AC-11 erfüllt; 6 CI-Checks grün; Adversary-Prüfung ohne offenen Befund; jede wiederhergestellte Zusicherung mit Mutationsprobe in der Testtabelle; echte Fehler als eigene Issues; Staging-Rauchtest; live auf Produktion mit Selftest Exit 0.
- [ ] **R2:** AC-1 und AC-7 bis AC-12 erfüllt; die 11 verbliebenen Dateien gelöscht, Nie-löschen-Liste und Liste C unberührt; 6 CI-Checks grün; Adversary-Prüfung ohne offenen Befund; Staging-Rauchtest DE und EN (Computer und Handy); Elementlisten-Abgleich unverändert; live auf Produktion mit Selftest Exit 0.
- [ ] Ratschen nur gesenkt, keine Änderung der Gate-Konfiguration. #3301 und #3298 (schon geschlossen) mit Nachweis-Kommentar an #3020 belegt, #3020 erst nach R2 geschlossen, Doku nachgezogen.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1 (R1): GIVEN Altfelder und die Daten eines zweiten Nutzers WHEN Reiter Wetter oder Zustellung (Trip und Orte) ein Feld ändert und speichert THEN gehen weder Altfelder noch fremde Daten verloren (Roundtrip je Feld, Feld-Erhalt samt `sms_threshold`, `show_night_block` aus bleibt aus). RED: Mutationsprobe am lebenden Speicherweg.
- [ ] Test 2 (R1): GIVEN pausierter oder übersprungener Trip WHEN ein Reiter speichert THEN bleibt `skip_next` unberührt, ohne 412; die Fälle zu #3355 stehen sichtbar als ausstehend.
- [ ] Test 3 (R1): GIVEN Konflikt (412) oder Wiederholung WHEN der zweite Reiter speichert THEN trägt er das alte If-Match, und der Flush beim Verlassen läuft (keepalive).
- [ ] Test 4 (R1): GIVEN Kanal-Vorgaben der Bedienung (Telegram, SMS, Premium-SMS) WHEN der Standard angezeigt und ausgeliefert wird THEN sind beide gleich, in `route` und `vergleich`.
- [ ] Test 5 (R1): GIVEN die 15 gestrichenen Katalogfälle WHEN `test_einstellung_gleich_mail_fallliste.py` läuft THEN ist jeder Fall mit lebendem Beleg eingetragen oder begründet gestrichen, und die `praefixe`-Prüfung läuft nicht leer.
- [ ] Test 6 (R1): GIVEN die Testtabelle WHEN der Wächter läuft THEN hat jede der 60 gelöschten Testdateien (57 „umstellen“ = 33 + 24, dazu 3 „löschen“) und jeder der 145 Fälle einen Entscheid, die Zeilen- und die Ausstehend-Anzahl stimmen, jeder Ersatzbeleg ist eine existierende Testdatei mit Testname.
- [ ] Test 7 (R2): GIVEN die 11 verbliebenen Dateien WHEN der Rückbau-Wächter mit `STAND` 2 vor der Löschung läuft THEN ist er rot (Dateien existieren), nach der Löschung grün (keine der 11 Dateien, kein Import, kein Barrel-Eintrag, `VORAB_GELOESCHT` und Nie-löschen-Liste vorhanden).
- [ ] Test 8 (R2): GIVEN die Probe-Löschung WHEN die roten Testdateien gemessen sind THEN steht jede der 13 Dateien plus der Python-Fall genau einmal mit Entscheid in der Testtabelle (Abschnitt R2).
- [ ] Test 9 (R2): GIVEN Ratschen und Katalog WHEN die Wächter laufen THEN sind `bausteine_waechter` (Obergrenze 155), `test_e2e_positivliste_ratschen_bindung.py`, `katalog_schluessel_haben_verwender` und `context_herkunft_zweige_eingefroren` grün ohne Lockerung.
- [ ] Test 10 (je Scheibe): GIVEN der Elementlisten-Abgleich vor und nach der Scheibe WHEN beide verglichen werden THEN sind sie in DE und EN identisch; Staging-Rauchtest grün.
- [ ] Test 11 (je Scheibe): GIVEN der PR WHEN CI und Diff-Prüfung laufen THEN 6 Checks grün, kein Python-/Go-Produktionscode im Diff, bei R2 baut der Probe-Revert (AC-11).
- [ ] Test 12 (R2): GIVEN R2 ist ausgeliefert WHEN Issues und die sechs Doku-Dateien geprüft werden THEN stimmen Issue-Status, Nachweis-Kommentar an #3020 und Namenssuche (AC-12).

## Acceptance Criteria

- **AC-1:** Given ein Nutzer mit Trips und Orte-Vergleichen / When er nach jeder Scheibe Trip-Hub, Orte-Hub, Trip-Anlegen und Orte-Anlegen in DE und EN auf Computer und Handy öffnet / Then sind Elemente, Texte und Bedienung unverändert (Scheibe R1 und R2)
  - Test: `npm run elementliste:abgleich` vor und nach jeder Scheibe identisch (DE/EN); die E2E-Dateien der CI-Positivliste, die einen der Namen nennen, bleiben grün und unverändert (die Namen stehen dort nur in Kommentaren; `E2E_MIN_*` unverändert); Rauchtest auf Staging je Scheibe.

- **AC-2:** Given Bestandsdaten mit Altfeldern (`telegram_kurzform`, `sms_threshold`, `channel_layouts`, `show_night_block` u. a.) und ein zweiter Nutzer mit eigenen Daten / When ein Nutzer im Reiter Wetter oder Zustellung (Trip und Orte) ein Feld ändert und speichert, auch nach Fehlern, Wiederholung oder 412 / Then bleiben alle nicht geänderten Felder erhalten, „aus“ bleibt aus, und die Daten des zweiten Nutzers sind unberührt (Scheibe R1)
  - Test: Roundtrip je Feld, Feld-Erhalt, Retry-/412-Fälle, Laden mit zwei Nutzern in der Vorrangreihenfolge; je Zusicherung Mutationsprobe am lebenden Speicherweg macht den Test rot.

- **AC-3:** Given ein pausierter oder übersprungener Trip / When ein Reiter speichert / Then bleibt der Schutz von `skip_next` erhalten, soweit er am lebenden Code gilt; wo er wegen #3355 nicht gilt, steht der Fall sichtbar als ausstehend mit Verweis auf #3355 (Scheibe R1)
  - Test: `trip_python_skip_next_ohne_412` (gelöschte Datei) wiederhergestellt und `trip_reiter_nutzlast_nur_eigene_felder` (vorhandene Datei, von 12 auf 8 Fälle gekürzt) um die fehlenden Fälle ergänzt; Anzahl der ausstehenden Fälle im Wächter und in der Testtabelle festgehalten; Mutationsprobe `skip_next` mitgesendet macht grüne Fälle rot.

- **AC-4:** Given die Kanal-Vorgaben der Bedienung für Telegram, SMS und Premium-SMS / When der Nutzer sie in Trip oder Orte sieht und der Versand sie ausliefert / Then sind angezeigte und ausgelieferte Vorgabe gleich (Scheibe R1)
  - Test: Vergleichstest am lebenden Reiter Zustellung je Kanal und Kontext (Ersatz für `versand_tab_defaults_gleich_auslieferung`); Mutationsprobe an der Vorgabe macht ihn rot.

- **AC-5:** Given der Prüfkatalog „Einstellung = Mail“ / When die 15 gestrichenen Fälle bearbeitet sind / Then ist jeder mit lebendem Beleg wieder eingetragen oder mit Begründung gestrichen, und die Prüfung der Testdateien in `test_einstellung_gleich_mail_fallliste.py` läuft nicht mehr leer (Scheibe R1)
  - Test: `tests/tdd/test_einstellung_gleich_mail_fallliste.py` grün; eine Mutationsprobe (Verweis auf nicht vorhandenen Test) macht ihn rot, `praefixe` bzw. die ersetzte Prüfung ist nicht leer.

- **AC-6:** Given die 60 in #3357 gelöschten Testdateien und die 145 entfallenen Fälle / When R1 ausgeliefert ist / Then steht für jede der 60 Dateien (57 „umstellen“ = 33 + 24, 3 „löschen“) und jeden Fall ein Entscheid in der Testtabelle, keine Zusicherung entfällt still, und echte Fehler im lebenden Code haben ein eigenes Issue (Scheibe R1)
  - Test: Rückbau-Wächter prüft beide Richtungen (Tabelle gegen rote Liste), Zeilenzahl und Zahl der ausstehenden Fälle festgehalten, jeder Ersatzbeleg ist Testdatei mit Testname.

- **AC-7:** Given die 11 verbliebenen Dateien aus dem Nachtrag (die übrigen 31 der 42 sind bereits gelöscht und werden vom Wächter über `VORAB_GELOESCHT` bzw. die Waisen-Wächter bewacht) / When R2 ausgeliefert ist / Then existiert keine von ihnen, kein Quelltext und kein Barrel importiert sie, und die Nie-löschen-Liste ist vorhanden (Scheibe R2)
  - Test: Rückbau-Wächter `rework_3020_rueckbau_waechter.test.ts` mit Schalter `STAND` 1 → 2: rot vor, grün nach der Löschung; `rework_3020_probe_loeschung.test.ts` wird nach der Löschung aufgelöst (sein Prüfling existiert nicht mehr, Entscheid in der Testtabelle); `svelte-check` und `vite build` ohne unaufgelöste Importe (Strukturwächter, kein Verhaltensnachweis).

- **AC-8:** Given die Probe-Löschung in einer Wegwerf-Kopie / When die roten Testdateien gemessen sind / Then hat jede einen Entscheid (löschen, umstellen, Ersatzbeleg) mit Begründung in der Testtabelle, und kein Test wird ohne Entscheid gelöscht (Scheibe R2)
  - Test: Abgleich der Testtabelle `rework_3020_testtabelle.md` gegen die Messung: Abschnitt R2 enthält genau die 13 roten Testdateien plus den Python-Fall `test_preset_row_color_mix_uses_surface0`, je mit Entscheid und Begründung; bei „umstellen“ Mutationsprobe am lebenden Modul.

- **AC-9:** Given verwaiste Katalogschlüssel in DE und EN / When der letzte Verwender gelöscht ist / Then sind sie in beiden Sprachen entfernt, kein lebender Schlüssel fehlt (Scheibe R2)
  - Test: `katalog_schluessel_haben_verwender` ungelockert grün, Katalog-Parität DE/EN und `keine_hartkodierten_nutzertexte` grün; kein Schlüssel-Rohtext auf Staging in DE und EN.

- **AC-10:** Given die Ratschen (`BESTAND_OBERGRENZE`, `context_herkunft_zweige_eingefroren`, `ein_katalog_ausnahmen.json`, `E2E_MIN_SPECS`, `E2E_MIN_EXECUTED_HAUPT`, svelte-check-Baseline) / When R2 ausgeliefert ist / Then sind sie nur gesenkt bzw. um gelöschte Einträge gekürzt, nie angehoben: `BESTAND_OBERGRENZE` 162 → 155, AUSNAHMEN 4 und `ein_katalog_ausnahmen.json` 2 Einträge gestrichen, `E2E_MIN_*` unverändert (Scheibe R2)
  - Test: `test_e2e_positivliste_ratschen_bindung.py`, `bausteine_waechter.test.ts` grün; Diff der Ratschenwerte im PR (Obergrenze 162 → 155, Positivliste unverändert).

- **AC-11:** Given jede Scheibe / When der PR geprüft wird / Then sind alle 6 CI-Checks (`test`, `lint`, `go-test`, `svelte-check`, `frontend-test`, `e2e`) grün, die Scheibe ist einzeln auslieferbar und per Revert zurückrollbar, und der Inhalt aller vier Kanäle bleibt unverändert (Scheibe R1 und R2)
  - Test: CI je PR grün, Selftest Exit 0 nach Auslieferung; Diff enthält keine Datei unter den Wurzelordnern `src/` (Python-Core), `api/`, `internal/`, `cmd/` (`frontend/src/` ist nicht gemeint); bei R2 baut ein Probe-Revert in einer Wegwerf-Kopie (`vite build` Exit 0).

- **AC-12:** Given #3301, #3298, #3020 und die Doku / When R2 ausgeliefert ist / Then sind #3301 und #3298 (schon geschlossen) mit Nachweis-Kommentar an #3020 belegt, ohne erneutes Schließen, #3020 geschlossen, und keine Doku-Datei (`frontend_components.md`, `api_contract.md`, `gates_und_ratschen.md`, `metric_output_matrix.md`, `docs/features/architecture.md`, `docs/features/epic-1273-compare-one-surface.md`) beschreibt einen gelöschten Baustein als bestehend (Scheibe R2)
  - Test: Issue-Status und Nachweis-Kommentar an #3020; Namenssuche der gelöschten Dateien in den sechs Dokumenten, jeder Treffer ist als entfernt oder historisch erkennbar (Strukturprüfung).

## Known Limitations

- **Testfolgen von R2 sind seit dem Nachtrag gemessen** (13 rote Testdateien plus ein Python-Fall, Probe-Löschung 2026-11-26). Zahlen zu R1 (20 bis 30 Testdateien) sind Schätzungen.
- Die 24 „nur vorhandene Dateien“-Zeilen der Testtabelle sind bisher nur nach Dateiname geprüft; R1 prüft den Fall.
- Probe-Löschung läuft lokal auf Node 26 (CI Node 22), Python- und Playwright-Tests laufen dort nicht; der CI-Lauf je PR ist maßgeblich. Die Baseline von 118 roten Dateien ist umgebungsbedingt; verglichen wird nur die Differenz.
- Wächter und rote Liste müssen in R1 neu entstehen (aus `8b9749601` portiert), sie liegen auf `main` nicht mehr vor.
- Offener Fehler #3355 (Vollkopie `report_config` im Reiter Wetter) wird nicht behoben; #3358 (Vorlage folgt der Fortbewegung) ebenso nicht.
- LoC-Limit 250 in beiden Scheiben bewusst überschritten (R2 fast nur Löschungen); keine Seiteneffekte außerhalb des Tickets, Liste C bleibt liegen. Vor R2 ist erneut zu prüfen, ob eine andere Sitzung an den Dateien des Restbestands arbeitet.
- AC-6, AC-7 und AC-12 sind bewusst Strukturwächter (Tests mit `# doc-compliance-test` gekennzeichnet), AC-8 bis AC-10 sind Abgleiche und Ratschen; keine davon ist ein Verhaltensnachweis. Verhalten belegen AC-1 bis AC-5.
- Der Kommentar in `src/app/metric_catalog.py:1314` nennt `outlookFriendlyCapability.ts` und veraltet mit R2 (Datei ist schon gelöscht). Er bleibt stehen, weil kein Python-Produktionscode geändert wird; er wird als Nebenbefund an #3298 vermerkt.
- `docs/artifacts/` ist gitignored; was für R1 und R2 gebraucht wird, steht in dieser Spec und der Testtabelle. Die Messlisten braucht nur die Umsetzung in diesem Worktree.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (ADR-0112 und ADR-0124 werden umgesetzt)
- **Rationale:** Der Rückbau führt eine bereits entschiedene Linie aus (Epic #3122/#2795, PO-Freigabe #3036); es entsteht keine neue Entscheidungsfläche.

## Changelog

- 2026-11-25: Initial spec created
- 2026-11-25: Version 2.0, vollständig neu gefasst. #3357 (`c8329fea4`) hat 12 der 54 Dateien und 60 Testdateien gelöscht; die Scheiben S1 bis S4 (19/26/9) und AC-3/4/6/11/12 der Fassung 1.0 beziehen sich auf den überholten Stand. Neu: zwei Scheiben R1 (Schutz wiederherstellen) und R2 (Restbestand 42 Dateien löschen).
- 2026-11-26: Version 2.1, Nachtrag für Scheibe R2. Gemessener Restbestand auf `d7180c9e8`: 31 der 42 Dateien sind durch #3298, #3301, #3366, #3383/#3384/#3385 und #3389 schon gelöscht, es verbleiben 11 Dateien und 6 Barrel-Zeilen. Probe-Löschung: 13 rote Testdateien plus Python-Fall mit Entscheid. Ratsche `BESTAND_OBERGRENZE` 162 → 155, AUSNAHMEN -4, `ein_katalog_ausnahmen.json` -2, E2E-Ratschen unverändert. AC-7 (11 Dateien, `STAND` 1 → 2), AC-8, AC-10 und AC-12 (#3301/#3298 schon geschlossen, nur Nachweis-Kommentar; zusätzlich `epic-1273-compare-one-surface.md`) an den gemessenen Stand angepasst; AC-1 und AC-9 inhaltlich unverändert. Pflegepunkte aus #3385 aufgenommen.
