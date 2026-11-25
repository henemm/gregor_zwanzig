---
entity_id: rework_3020_altbausteine_entfernen
type: refactor
created: 2026-11-25
updated: 2026-11-25
status: draft
version: "1.0"
workflow: rework-3020-altbausteine-entfernen
tags: [rueckbau, wetter-tab, zustellung, epic-3122, epic-2795]
---

# Rückbau Alt-Bausteine Wetter/Zustellung (WeatherMetricsTab und Umfeld)

## Approval

- [ ] Approved

## Purpose

Die alte Wetter-/Zustellungs-Oberfläche (`WeatherMetricsTab` samt Versand-, Layout- und Wertebereiche-Umfeld) wird gelöscht. Seit #3154, #3332/#3333 und #3036 zeigt sie kein Nutzer mehr; sie hält nur noch Tests, Wächter-Ausnahmen und tote Katalogschlüssel am Leben. Nutzer sehen keinen Unterschied. Die PO-Freigabe, dass Alt-Bausteine, die Anzeige `telegram_kurzform` und die SMS-Schwellen mit #3020 fallen, liegt vor (#3036, 2026-11-24).

## Source

- **File:** `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` (Wurzel); Umfang laut Abschnitt Scope
- **Identifier:** 54 Dateien (Listen A und B), 8 Barrel-Zeilen, 196 Katalogschlüssel je Sprache

Schicht: **Frontend** (`frontend/src/...`), dazu Testunterbau, CI-Konfiguration und ein Hook-Eintrag. **Kein** Python-/Go-Code geändert.

**Querschnitts-Prüfpunkte:**
- **Trip/Ortsvergleich-Teilung:** Es entsteht nichts Neues. Gelöscht wird je ein gemeinsamer Code für beide Kontexte; die lebenden Pendants (`wetter-tab/`, `WasStehtWoKarte`, `zustellung-tab/`) bleiben. Das Paar `compareChannelMetricLayouts`/`channelMetricLayouts` fällt aus `BEKANNTE_PAARE`, weil die Datei nicht mehr existiert.
- **Mandantentrennung:** Es wird kein Endpoint geändert. Die bestehenden Roundtrip-/Speicherweg-Tests mit zwei verschiedenen Nutzern bleiben bzw. werden auf lebende Module umgestellt (AC-5).
- **Kanäle:** E-Mail, Telegram, SMS, Premium-SMS: Briefing-/Alarm-Inhalt bleibt byteidentisch, weil kein Renderer-, Python- oder Go-Code berührt wird (AC-8).

## Estimated Scope

- **LoC:** Produktion −8 881 (nur Löschungen) plus 8 Barrel-Zeilen und Katalog-Löschungen; Tests grob −10 000 bis −20 000; hinzugefügte bzw. umgeschriebene Zeilen Schätzung unter 2 000. **Das Limit von 250 LoC / 4-5 Dateien wird bewusst überschritten**; die Freigabe dieser Spec deckt das ausdrücklich ab (Begründung: fast nur Löschungen, Produktionscode wird nicht neu geschrieben). Je Scheibe wird `loc_limit_override` gesetzt.
- **Files:** 54 gelöscht, rund 180 weitere berührt (160 rote Testdateien laut Probe-Löschung, davon ein Teil gelöscht).
- **Effort:** high, in vier Scheiben (je eigener PR).

## Scope

### Scheiben

Je Scheibe: eigener PR, alle 6 CI-Checks grün, eigene Auslieferung, einzeln per Revert des PR zurückrollbar. Reihenfolge fest S1 → S2 → S3 → S4. Regel: keine Scheibe löscht eine Datei, die ein noch vorhandener Baustein importiert (Prüfung gegen `importebenen.txt` und die Zwischenkanten, siehe Implementation Details).

| Scheibe | Inhalt | Produktion gelöscht |
|---|---|---|
| S1 Testunterbau | Testhelfer von toten Dateien lösen, Probe-Löschung wiederholen, Testtabelle anlegen, Rückbau-Wächter (RED) | keine (nur der Testhelfer `LayoutTabPruefstand.svelte`, 0 Nutzer) |
| S2 Lose Blätter | Ebene-1-Blätter ohne Panel plus Teilbaum unter `OutputLayoutEditor` | 19 Dateien, ca. 2 236 Zeilen |
| S3 Kern | Panel, `WeatherMetricsTab`, `BriefingScheduleTab`, Wetter- und Layout-Cluster | 26 Dateien, ca. 5 081 Zeilen |
| S4 Versand-Cluster | `VersandTab`, `VT*`, `MailInhaltCard`, `channelContactLabel`, `vtBriefingChannelsText` | 9 Dateien, ca. 1 564 Zeilen |

Pfade relativ zu `frontend/src/`.

**S2 (19):**
`lib/components/compare/compareHourlyMetricDefs.ts`, `compare/hourlyFriendlyMap.ts`, `compare/layoutPreviewRows.ts`, `compare/versandPropsAus.ts`, `compare/wetterMetrikenPropsAus.ts`, `lib/components/organisms/AlertsCard.svelte`, `organisms/MetricOffShelf.svelte`, `organisms/OutboxCard.svelte`, `organisms/PresetRail.svelte`, `lib/components/shared/OutputLayoutEditor.svelte`, `shared/layout-tab/channelLayoutsDirty.ts`, `shared/layout-tab/ltIdealRange.ts`, `lib/components/trip-detail/TablePreview.svelte`, `trip-detail/WeatherV2Kanaele.svelte`, `trip-detail/ActiveMetricRow.svelte`, `trip-detail/BucketSection.svelte`, `trip-detail/BucketSectionOff.svelte`, `trip-detail/ChannelLimitMarkers.svelte`, `trip-detail/PresetRow.svelte`.

**S3 (26):**
`lib/components/shared/WetterMetrikenVersandPanel.svelte`, `shared/WeatherMetricsTab.svelte`, `lib/components/trip-detail/BriefingScheduleTab.svelte`, `lib/components/molecules/GrundauswahlLeerHinweis.svelte`, `shared/OutlookLayoutControls.svelte`, `shared/reportConfigDirty.ts`, `trip-detail/weatherSaveGate.ts`, `shared/layout-tab/LayoutTab.svelte`, `shared/layout-tab/LTCapNote.svelte`, `shared/layout-tab/LTChannelPicker.svelte`, `shared/layout-tab/LTCutLine.svelte`, und unter `shared/weather-metrics-tab/`: `AggregationMetricRow.svelte`, `MultiSymbolMetricRow.svelte`, `ThresholdMetricRow.svelte`, `WeatherV2Grundauswahl.svelte`, `WeatherV2PresetBar.svelte`, `WeatherV2Reihenfolge.svelte`, `channelMetricLayouts.ts`, `compareAggregationGrouping.ts`, `kuerzelLegende.ts`, `kuerzelMarken.ts`, `nurEinBericht.ts`, `outlookFriendlyCapability.ts`, `weatherMetricsSavePayload.ts`, `weatherMetricsTabSections.ts`, `wertebereicheAnzeige.ts`.

**S4 (9):**
`lib/components/shared/VersandTab.svelte`, `shared/MailInhaltCard.svelte`, `shared/versand-tab/VTBriefingChannels.svelte`, `VTLaufzeitRoute.svelte`, `VTLaufzeitVergleich.svelte`, `VTNextBriefing.svelte`, `VTSchedulePlan.svelte`, `channelContactLabel.ts`, `vtBriefingChannelsText.ts`.

Summe 19 + 26 + 9 = 54 (Liste A 35 + Liste B 19). **Liste C (24 Dateien, fachfremd) ist nicht Umfang** und bleibt liegen.

**Nie löschen** (lebend laut Spec #3036 Nr. 5, keine davon in A/B): `channelConnectionStatus.ts`, `sendTargetLabel.ts`, `dayWindowClamp.ts`, `nextBriefingText.ts`, `naechstesBriefingLader.svelte.ts`, `nextBriefingLoad.ts`, `reportConfigPayload.ts`, `mergeReportConfig.ts`, `ltChannels.ts`, `kanalStilSpeicherung.ts`. Ebenfalls lebend und unangetastet: `weatherMetricsCompareSave.ts`, `compareChannelMetricLayouts.ts`, `mailInhaltZustand.ts`, `mailInhaltKonstanten.ts`, `pickEigenfelder.ts` (Altfeld-Stellen darin: nicht Umfang, Rest-Umfang von #3297).

### Affected Files (außer den 54)

| File | Change Type | Scheibe | Description |
|------|-------------|---------|-------------|
| `shared/weather-metrics-tab/__tests__/{f5Pruefstand,_editor_kette}.ts`, `shared/layout-tab/__tests__/f8Pruefstand.ts`, `shared/versand-tab/__tests__/f6VersandSsr.ts`, `trip-detail/__tests__/{tripMehrreiterPruefstand,f9Pruefstand}.ts`, `shared/__tests__/infoboxSsr.ts` | MODIFY | S1 | von toten Dateien auf lebende Bausteine umstellen |
| `shared/layout-tab/__tests__/LayoutTabPruefstand.svelte` | DELETE | S1 | 0 Nutzer |
| `lib/__tests__/rework_3020_rueckbau_waechter.test.ts` | CREATE | S1 (wächst je Scheibe) | Rückbau-Wächter |
| `docs/specs/modules/rework_3020_testtabelle.md` | CREATE | S1, fortgeschrieben je Scheibe | Entscheid je Testdatei |
| `lib/components/trip-detail/index.ts`, `lib/components/organisms/index.ts` | MODIFY | S2 (6 Zeilen), S3 (2 Zeilen) | Barrel-Re-Exports |
| 160 Testdateien laut `probeloeschung_folgen.txt` (auf dem Stand der S1-Wiederholung neu bestimmt) | DELETE/MODIFY | je Scheibe | siehe Testtabelle |
| `lib/__tests__/bausteine_waechter_regeln.ts` | MODIFY | S2, S3, S4 | `BESTAND` und `BESTAND_OBERGRENZE` (195) um die Zahl entfernter Einträge senken |
| `shared/__tests__/context_herkunft_zweige_eingefroren.test.ts` | MODIFY | S2-S4 | Einträge gelöschter Dateien streichen, übrige unverändert |
| `shared/__tests__/anlegeseiten_ohne_versand_panel_3333.test.ts` | MODIFY | S3 | Vakuum-Schutz „Panel-Datei existiert" ersetzen |
| `src/routes/_home/__tests__/home_hero_paritaet.test.ts`, `src/routes/trips/[id]/__tests__/trip_hub_loeschen.test.ts` | MODIFY | S2/S3 | siehe Implementation Details Nr. 7 |
| `frontend/src/lib/i18n/messages/{de,en}/{wertebereiche,trip,versand,layout,bausteine}.json` | MODIFY | S2-S4 | verwaiste Schlüssel (Stand Probe: 196 je Sprache), in der Scheibe des letzten Verwenders |
| `tests/golden/{f5_wertebereiche,f6_versand_tab,f8_layout_korridor,f9_trip_flaechen}/` | MODIFY | S2-S4 | nur Blöcke toter Bausteine entfallen, lebende bytegleich |
| `tests/fixtures/einstellung_gleich_mail/{fallliste_editor,fallliste_trip,fallliste_orte}.json` | MODIFY | S3 | 45 Fälle umhängen/neu schreiben (Implementation Details Nr. 2) |
| `tests/unit/ein_katalog_ausnahmen.json` | MODIFY | S2 (BucketSectionOff, TablePreview), S3 (4 weitere) | 6 tote Dateien entfernen |
| `.claude/hooks/pendant_gate.py` (Z. 83-84) | MODIFY | S3 | Paar `compareChannelMetricLayouts`/`channelMetricLayouts` aus `BEKANNTE_PAARE` streichen (Known Limitations) |
| `tests/tdd/test_issue_289_surface_tokens.py` | MODIFY | S2 | AC-4 (liest `PresetRow.svelte`) entfällt |
| `tests/tdd/test_issue_934_wizard_schedule.py` | MODIFY | S3 | Einzelentscheid |
| `tests/tdd/test_issue_692_telegram_disabled_unconfigured.py` | MODIFY/DELETE | S2 (WeatherV2Kanaele) bzw. S3 | Einzelentscheid |
| `frontend/e2e/issue-1093-unit.spec.ts`, `.github/ci_e2e_specs.txt`, `.github/workflows/ci.yml` (`E2E_MIN_SPECS`, `E2E_MIN_EXECUTED_HAUPT`) | DELETE/MODIFY | S2 | Positivliste 86 → 85 |
| `.github/workflows/ci.yml` (svelte-check-Baseline, heute 34 Fehler / 132 Warnungen) | MODIFY | je Scheibe | nur senken |
| `docs/reference/{frontend_components,api_contract,gates_und_ratschen,metric_output_matrix}.md`, `docs/features/architecture.md` | MODIFY | je Scheibe | gelöschte Bausteine nicht mehr als bestehend beschreiben |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/rework-3020-altbausteine-entfernen.md` | Kontext | Analyse, Probe-Löschung, Kernbefunde |
| `docs/artifacts/rework-3020-altbausteine-entfernen/` (gitignored, nur im Worktree) | Belege | Importebenen, rote Tests, verwaiste Schlüssel; die Pfade stehen deshalb oben in dieser Spec |
| ADR-0112 (Bausteine-Ratsche), ADR-0124 | ADR | Ratschen nur senken; Rückbau umgesetzt |
| `tests/tdd/test_einstellung_gleich_mail_fallliste.py` | Wächter | Abdeckungsmatrix Prüfkatalog, bleibt unverändert und grün |
| `tests/unit/test_e2e_positivliste_ratschen_bindung.py` | Wächter | bindet `E2E_MIN_SPECS`/`E2E_MIN_EXECUTED_HAUPT` exakt |
| `frontend/src/lib/i18n/__tests__/katalog_schluessel_haben_verwender.test.ts` | Wächter | tote Schlüssel, bleibt ungelockert |
| `npm run elementliste:abgleich` | Skript | Nachweis „keine sichtbare Änderung" |
| #3301, #3297, #3298, #3277 | Issues | #3301 wird mit Nachweis geschlossen; #3297 bekommt den Restumfang als Kommentar |

## Implementation Details

1. **S1 Testunterbau (Produktion unverändert).** Probe-Löschung auf dem aktuellen Stand (Branch auf `da6991ed9`, #3353/#2987 gemergt) in einer Wegwerf-Kopie wiederholen, nie im Arbeitsbaum; Ergebnis (rote Testdateien) fortschreiben. Testhelfer von toten Dateien lösen und auf lebende Bausteine (`wetter-tab/`, `WasStehtWoKarte`, `zustellung-tab/`, `placements`) umstellen: `tripMehrreiterPruefstand` (21 Nutzer), `f9Pruefstand` (16), `f5Pruefstand` (9), `_editor_kette` (5), `f6VersandSsr` (4), `f8Pruefstand` (3), `infoboxSsr`; `LayoutTabPruefstand.svelte` (0 Nutzer) löschen. Die Nutzer, die lebendes Verhalten prüfen (`tempo_*`, `trip_retry_*`, `hub_kopf_*` u. Ä.), sind danach in der normalen Kopie **und** in der Probe-Löschung grün. Nutzer, die ausschließlich tote Bausteine prüfen, behalten ihren bisherigen Helferteil bis zur Scheibe, in der ihr Baustein fällt; er wird dafür bei Bedarf vom lebenden Teil abgetrennt.
2. **Prüfkatalog „Einstellung = Mail".** 45 Fälle hängen an Tests, die mit der Löschung rot werden: `fallliste_editor` 43 (`editor_standard_gleich_mail` 22, `telegram_kanalgrenze_je_kontext` 6, `telegram_schnittlinie_wahr` 6, `nur_ein_bericht_kennzeichnung` 4, `versand_telegram_je_kontext` 3, `lade_kanal_layouts_aus_trip` 2), `fallliste_trip` 1 (`neue_metrik_in_allen_listen`), `fallliste_orte` 1 (`neue_metrik_in_allen_listen_orte`). 57 weitere frontend-Fälle der Editor-Liste (u. a. `ac26_einstellung_gleich_ausgabe` 21, `p5c_ableitung_hub_orte_ausgabe` 17) sind nicht betroffen. Regel je Fall: (a) lebender Beleg mit gleicher Aussage vorhanden: Testverweis umhängen; (b) sonst Zusicherung auf lebendes Modul neu schreiben; (c) streichen nur, wenn die Aussage ausschließlich eine nicht mehr vorhandene Oberfläche betrifft, mit Begründung je Fall in der Testtabelle. Die Fallzahl sinkt höchstens um die nach (c) begründet gestrichenen Fälle; die Abdeckungsmatrix bleibt vollständig; `test_einstellung_gleich_mail_fallliste.py` wird nicht gelockert. Umhängen geschieht in S3 (die Fälle laufen über `WeatherMetricsTab`/`channelMetricLayouts`).
3. **Reihenfolge und Zwischenkanten.** Importgraph ist zyklenfrei, 5 Ebenen. Geprüfte Kanten: `reportConfigDirty` und `weatherSaveGate` haben nur Importeure in S3 (`WeatherMetricsTab`, `BriefingScheduleTab`); `weatherMetricsSavePayload` → `channelMetricLayouts` beide S3; `hourlyFriendlyMap` (S2) importiert `outlookFriendlyCapability` (S3), also ist die Richtung S2 vor S3 zulässig; `LTCutLine` und `kuerzelLegende` werden nur von `WeatherV2Reihenfolge` importiert (alle S3); `WetterMetrikenVersandPanel` und `BriefingScheduleTab` (beide S3) importieren `VersandTab` (S4), daher S4 nach S3; `MailInhaltCard` und die `VT*`-Dateien importieren keine S2-/S3-Datei. Vor jeder Scheibe prüft der Rückbau-Wächter bzw. `svelte-check`/`vite build`, dass kein verbleibender Import auf eine gelöschte Datei zeigt.
4. **Barrels.** S2: `trip-detail/index.ts` (`TablePreview`), `organisms/index.ts` (`OutputLayoutEditor`, `OutboxCard`, `AlertsCard`, `PresetRail`, `MetricOffShelf`); S3: `WeatherMetricsTab` in beiden Barrels. Insgesamt 8 Zeilen.
5. **E2E.** Von 21 Playwright-Dateien mit Namenstreffern importiert nur `frontend/e2e/issue-1093-unit.spec.ts` ein totes Modul (`layoutPreviewRows.ts`); sie steht auf der CI-Positivliste (3 Testfälle, prüft nur toten Code) und wird in S2 gelöscht; `.github/ci_e2e_specs.txt` und `E2E_MIN_SPECS` (86 → 85) sowie `E2E_MIN_EXECUTED_HAUPT` (um die tatsächlich wegfallenden Fälle) werden exakt nachgezogen. Die übrigen 11 CI-gelisteten Dateien nennen die Namen nur und steuern die laufende Oberfläche; sie bleiben unverändert grün und sind der E2E-Beleg „keine sichtbare Änderung".
6. **Python.** `test_issue_692_...` und `test_issue_934_...` sind `pytest.mark.staging` (nicht Kern-Schicht). 692 nennt `WeatherV2Kanaele`/`WeatherMetricsTab` nur in Kommentar/Assertion-Text und prüft per Playwright eine nicht mehr vorhandene Oberfläche; 934 (`TestBug1KeineDoppelteUI`) sucht die `WeatherMetricsTab`-Funktion im Bundle (`createMode`) und wird gegenstandslos: Einzelentscheid in der Testtabelle (S3). `test_issue_289_surface_tokens.py` AC-4 entfällt in S2. `ein_katalog_ausnahmen.json`: 6 tote Dateien raus. Übrige Python-Treffer sind Kommentare/Docstrings, nicht Umfang. `pendant_gate.py` Z. 83-84 wird in S3 gestrichen, sonst bricht `test_jede_datei_der_ausnahmeliste_existiert_im_repo` (die Liste darf nur schrumpfen); `EINGEFROREN`/`_BESTANDSPAARE` in den Tests bleiben unverändert (beide verkraften laut ihren Kommentaren das Streichen; beim Lauf zu bestätigen).
7. **Einzelfälle Frontend.** `trip_hub_loeschen.test.ts` wird rot, weil es `f9Pruefstand` lädt (löst S1). `home_hero_paritaet.test.ts` Z. 140-141 verlangt die Existenz von `shared/OutlookLayoutControls.svelte`: dieser Testfall entfällt in S3, der Rest bleibt. `anlegeseiten_ohne_versand_panel_3333.test.ts:37`: Vakuum-Schutz „Panel-Datei existiert" wird umgestellt auf „kein Import und kein Mount in Anlege-/Hub-Dateien, Datei existiert nicht mehr". Rückbau-Wächter (`daywindowcard_rueckbau_waechter`, `mail_inhalt_rueckbau_waechter`, `totcode_rueckbau_speicherweg` u. Ä.) prüfen Abwesenheit in toten Dateien: eine gelöschte Datei erfüllt sie stärker; Entscheid je Test in der Testtabelle. `compare_versand_wertprops` (Z. 518, 536) und `compare_wetter_metriken_wertprops` (Z. 424) bewachen `versandPropsAus`/`wetterMetrikenPropsAus` und werden mit S2 umgestellt oder gelöscht.
8. **Ratschen.** `BESTAND_OBERGRENZE` steht bei 195; 33 tote `.svelte`-Namen kommen darin vor (Analyse: S2 12, S3 14, S4 7). Je Scheibe exakt um die Zahl der entfernten `BESTAND`-Einträge senken. `context_herkunft_zweige_eingefroren`: Einträge der gelöschten Dateien streichen, Fließtext in `docs/reference/gates_und_ratschen.md` nachziehen. Golden-Verzeichnisse: Diff nur Löschungen. svelte-check-Baseline in `ci.yml` nach jeder Scheibe auf den in CI gemessenen Wert senken, nie anheben.
9. **Katalogschlüssel.** 196 verwaiste Schlüssel je DE und EN (wertebereiche 76, trip 46, versand 36, layout 24, bausteine 14) laut Probe; in der Scheibe entfernen, in der der letzte Verwender fällt. Zahl auf dem neuen Stand neu messen. `katalog_schluessel_haben_verwender` bleibt ungelockert; Pin-Tests (`deutsch_unveraendert`) nur um entfernte Schlüssel kürzen.
10. **Altdaten.** Es wird keine Speicherstelle geändert. Gespeicherte Altfelder (`telegram_kurzform`, SMS-Schwellen, `channel_layouts` u. a.) bleiben unverändert im Bestand (Merge, nie Replace; ADR-0101, CLAUDE.md Daten-Schema-Pflicht); sie verlieren nur ihre tote Bedienoberfläche.
11. **Testtabelle.** `docs/specs/modules/rework_3020_testtabelle.md` (versioniert) enthält je Testdatei der 160: Scheibe, Entscheid (löschen / umstellen / Ersatzbeleg), Begründung, Ersatzbeleg-Pfad; sie wird in S1 angelegt und vor jeder Löschung der Scheibe fortgeschrieben. Umgestellte Zusicherungen erhalten eine Mutationsprobe (String-Ersetzung mit externer Sicherung, nie `git checkout/stash/reset`).
12. **Mutationsprobe und TDD-RED.** RED = der neue Rückbau-Wächter einer Scheibe schlägt vor der Löschung fehl (Datei existiert/wird importiert), grün nach der Löschung. Für umgestellte Zusicherungen: Verfälschung des lebenden Moduls macht den umgestellten Test rot.
13. **Gate-Konfiguration** (`openspec.yaml`) bleibt unverändert. Keine neue ADR.

## Expected Behavior

- **Input:** Nutzer öffnet Trip-Hub, Orte-Hub, Trip-Anlegen oder Orte-Anlegen (DE/EN, Computer und Handy).
- **Output:** Identisch zu vorher; keine Funktion, kein Text, kein Element fällt weg oder kommt hinzu.
- **Side effects:** 54 Dateien weniger im Bundle; kleinere Test- und Katalogmenge; niedrigere Ratschen-Obergrenzen.

## Definition of Done

- AC-1 bis AC-13 erfüllt und je Scheibe belegt (Kern-Tests, CI-E2E, Staging); die Testtabelle ist vollständig, keine Zusicherung still entfallen, umgestellte Zusicherungen mit Mutationsprobe.
- Alle 54 Dateien der Listen A und B gelöscht, Liste C und die Nie-löschen-Liste unberührt.
- Je Scheibe: 6 CI-Checks grün, Adversary-Prüfung ohne offenen Befund, Staging-Rauchtest in DE und EN (Computer und Handy), Elementlisten-Abgleich unverändert, live auf Produktion mit Selftest Exit 0.
- Ratschen nur gesenkt, Golden-Dateien nur mit Löschungen, keine Änderung an der Gate-Konfiguration. Einzige menschliche Sperren-Freigabe: die Streichung in `pendant_gate.py` (S3, siehe Known Limitations).
- #3301 mit Nachweis geschlossen, Restumfang in #3297 kommentiert, Doku nachgezogen.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Rückbau-Wächter (`rework_3020_rueckbau_waechter.test.ts`, node --test): GIVEN Scheibe n ist ausgeliefert / WHEN alle Pfade der Scheiben 2..n geprüft werden / THEN keine Datei existiert und kein Quelltext importiert sie; RED vor jeder Löschung.
- [ ] Nutzer der umgestellten Testhelfer (je Scheibe): grün in normaler Kopie und in der Probe-Löschung.
- [ ] Elementlisten-Abgleich vor/nach jeder Scheibe identisch (DE und EN).
- [ ] CI-Positivliste E2E (11 + übrige) grün; Staging-Rauchtest je Scheibe.
- [ ] `test_einstellung_gleich_mail_fallliste.py` grün, Abdeckungsmatrix unverändert.
- [ ] Mutationsprobe je umgestellter Zusicherung (Testtabelle, Spalte Mutation).
- [ ] `katalog_schluessel_haben_verwender`, `bausteine_waechter`, `test_e2e_positivliste_ratschen_bindung.py`, `test_pendant_gate_bekannte_paare.py`: grün ohne Lockerung.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer mit Trips und Orte-Vergleichen / When er nach jeder der vier Scheiben Trip-Hub, Orte-Hub, Trip-Anlegen und Orte-Anlegen in DE und EN auf Computer und Handy öffnet / Then sind Elemente, Texte und Bedienung unverändert
  - Test: `npm run elementliste:abgleich` vor und nach jeder Scheibe identisch (DE/EN), die 11 CI-gelisteten E2E-Dateien mit Namenstreffern unverändert grün, Rauchtest auf Staging je Scheibe.

- **AC-2:** Given Bestandsdaten mit Altfeldern (`telegram_kurzform`, SMS-Schwellen, `channel_layouts` u. a.) / When ein Nutzer im Trip-Hub oder Orte-Hub (Reiter Wetter oder Zustellung) eine Einstellung ändert und speichert / Then bleiben alle nicht geänderten Altfelder erhalten und die Daten eines zweiten Nutzers bleiben unberührt
  - Test: bestehende Roundtrip-/Speicherweg-Tests (Read-Modify-Write, zwei verschiedene Nutzer) laufen weiter grün bzw. sind auf lebende Module umgestellt (`trip_reiter_roundtrip_jedes_feld`, `merge_report_config_read_modify_write` und Entsprechungen laut Testtabelle).

- **AC-3:** Given Scheibe n ist umgesetzt / When der Rückbau-Wächter läuft / Then existiert keine Datei der Scheiben 2..n mehr, kein Quelltext importiert oder mountet sie, und keine ist neu angelegt (Muster Rückbau-Wächter; Strukturwächter, kein Verhaltensnachweis).
  - Test: `rework_3020_rueckbau_waechter.test.ts` rot vor, grün nach jeder Löschung; Vakuum-Schutz: Liste der 54 Pfade hat je Scheibe die in dieser Spec genannte Länge (19/26/9).

- **AC-4:** Given die 160 roten Testdateien der Probe-Löschung (neu gemessen in S1) / When eine Scheibe gelöscht wird / Then steht für jede betroffene Testdatei in der Testtabelle `rework_3020_testtabelle.md` ein Entscheid (löschen, umstellen oder Ersatzbeleg) mit Begründung, und keine Zusicherung entfällt still
  - Test: Abgleich der Testtabelle gegen die rote Liste der Probe-Löschung der Scheibe (jede Datei genau einmal, nur Entscheid „löschen" bei Aussage über eine nicht mehr vorhandene Oberfläche); bei „umstellen" Mutationsprobe (Verfälschung des lebenden Moduls macht den Test rot).

- **AC-5:** Given Zusicherungen zu Speicherweg, Zwei-Nutzer-Trennung und Premium-SMS in Tests mit toten Komponenten als Maßstab / When die Tests umgestellt werden / Then prüfen sie dieselbe Aussage an lebenden Modulen (`wetter-tab`, `WasStehtWoKarte`, `zustellung-tab`, `placements`)
  - Test: je umgestellter Test die Mutationsprobe aus der Testtabelle (Spalte Mutation), z. B. falscher Feldname im lebenden Speicherweg macht den Test rot.

- **AC-6:** Given der Prüfkatalog „Einstellung = Mail" (`tests/fixtures/einstellung_gleich_mail`) / When S3 die 45 Fälle umhängt, neu schreibt oder (nur mit Begründung) streicht / Then bleibt die Abdeckungsmatrix vollständig und `test_einstellung_gleich_mail_fallliste.py` unverändert grün
  - Test: Wächter `tests/tdd/test_einstellung_gleich_mail_fallliste.py` grün ohne Änderung der Datei; je Fall Eintrag (a/b/c) in der Testtabelle; die 57 nicht betroffenen Fälle unverändert.

- **AC-7:** Given die Ratschen (`BESTAND_OBERGRENZE`, `context_herkunft_zweige_eingefroren`, svelte-check-Baseline, `E2E_MIN_SPECS`, `E2E_MIN_EXECUTED_HAUPT`, `BEKANNTE_PAARE`, `ein_katalog_ausnahmen.json`) / When eine Scheibe ausgeliefert wird / Then sind sie nur gesenkt bzw. um die gelöschten Einträge gekürzt, nie angehoben, und die Golden-Verzeichnisse haben nur Löschungen im Diff
  - Test: Bindungstest `test_e2e_positivliste_ratschen_bindung.py`, `bausteine_waechter.test.ts`, `test_pendant_gate_bekannte_paare.py` grün; Diff-Prüfung der Ratschenwerte und der Golden-Dateien im PR (Positivliste 86 → 85).

- **AC-8:** Given Briefing- und Alarm-Versand über E-Mail, Telegram, SMS und Premium-SMS / When die vier Scheiben ausgeliefert sind / Then ist der Inhalt aller vier Kanäle unverändert, weil kein Python- oder Go-Code geändert wurde
  - Test: Diff der Scheiben enthält keine Datei unter `src/`, `api/`, `internal/`, `cmd/`; Kern-Schicht und `briefing_mail_validator.py` gegen Staging-Mail grün (kein Mock).

- **AC-9:** Given Katalogschlüssel in `wertebereiche`, `trip`, `versand`, `layout`, `bausteine` (Stand Probe: 196 verwaist je Sprache) / When die jeweils letzte verwendende Datei gelöscht ist / Then sind diese Schlüssel in DE und EN entfernt, kein lebender Schlüssel fehlt, und die Zählung auf dem neuen Stand ist in der Testtabelle bzw. im PR genannt
  - Test: `katalog_schluessel_haben_verwender.test.ts` ungelockert grün, Katalog-Paritätstest DE/EN und `keine_hartkodierten_nutzertexte` grün; Anzeige auf Staging in DE und EN ohne sichtbaren Schlüssel-Rohtext (Teil des Rauchtests aus AC-1).

- **AC-10:** Given jede der vier Scheiben / When der PR geprüft wird / Then sind alle 6 CI-Checks (`test`, `lint`, `go-test`, `svelte-check`, `frontend-test`, `e2e`) grün, die Scheibe ist einzeln auslieferbar und per Revert des PR zurückrollbar
  - Test: CI-Lauf je PR grün; nach Auslieferung Selftest Exit 0; bei S2-S4 Probe-Revert in Wegwerf-Kopie baut (`vite build` Exit 0).

- **AC-11:** Given S1 / When die Probe-Löschung auf dem Stand nach #3353/#2987 in einer Wegwerf-Kopie wiederholt wird / Then sind die Nutzer der umgestellten Helfer (`tripMehrreiterPruefstand`, `f9Pruefstand`, `f5Pruefstand`, `_editor_kette`, `f6VersandSsr`, `f8Pruefstand`), soweit sie lebendes Verhalten prüfen, auch dort grün, und `LayoutTabPruefstand.svelte` ist gelöscht
  - Test: Ergebnisliste der Wiederholung in der Testtabelle; `vite build` Exit 0 in der Kopie; Arbeitsbaum unberührt.

- **AC-12:** Given #3301 und #3297 / When S2 ausgeliefert ist (`compareHourlyMetricDefs.ts` gelöscht) bzw. S4 abgeschlossen ist / Then ist #3301 mit Nachweis geschlossen und #3297 trägt den Restumfang (Altfeld-Stellen in lebenden Dateien wie `weatherMetricsCompareSave.ts`) als Kommentar
  - Test: Issue-Status und Kommentar nach Auslieferung; kein Eintrag zu `compareHourlyMetricDefs` mehr in `ein_katalog_ausnahmen.json`/Wächtern.

- **AC-13:** Given die Doku (`frontend_components.md`, `api_contract.md`, `gates_und_ratschen.md`, `metric_output_matrix.md`, `docs/features/architecture.md`) / When eine Scheibe ausgeliefert ist / Then beschreibt keine dieser Dateien einen gelöschten Baustein als bestehend (Ausnahme: ausdrücklich als entfernt/historisch markiert)
  - Test: Suche nach den Namen der gelöschten Dateien in den fünf Dokumenten je Scheibe; jeder verbleibende Treffer ist im Text als entfernt oder historisch erkennbar (Strukturprüfung, kein Verhaltensnachweis).

## Known Limitations

- **Hook-Eintrag:** `.claude/hooks/pendant_gate.py` ist als Infrastruktur geschützt. Die eine nötige Streichung in S3 (Z. 83-84) braucht voraussichtlich eine einmalige menschliche Freigabe (`override`). Das ist als Definition-of-Done-Schritt von S3 ausgewiesen; es gibt keinen Umgehungsweg. Ohne die Streichung wird `test_jede_datei_der_ausnahmeliste_existiert_im_repo` rot.
- **Probe-Löschung** läuft lokal auf Node 26 (CI Node 22); Python- und Playwright-Tests laufen dort nicht. Der CI-Lauf je PR ist der maßgebliche Beleg. Drei Tests sind schon vor der Löschung rot und aus den 160 herausgerechnet: `pill_toene_kontrast`, `anlege_lock_engine_waechter`, `weather_metric_kuerzel_marken` (Ursache nicht Teil dieser Spec).
- Der Skript-Befund beruht auf Regex statt Parser; dynamische Pfade und CSS sind nicht geprüft. Gegenprobe: `svelte-check` und `vite build` je Scheibe.
- Zahlen (160 rote Dateien, 196 Schlüssel, 45 Fälle) sind Stand Probe auf `819a37abf`/`da6991ed9`-Vorgänger; S1 misst neu, die Testtabelle gilt.
- LoC-Limit 250 überschritten, bewusst; Freigabe dieser Spec deckt das ab. Keine Seiteneffekte außerhalb des Tickets: Liste C bleibt liegen, kein Drive-by.
- Keine Dateiinhalt-Checks als Verhaltensnachweis außer den benannten Strukturwächtern (AC-3, AC-7, AC-13).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (ADR-0112 und ADR-0124 werden umgesetzt)
- **Rationale:** Der Rückbau führt eine bereits entschiedene Linie aus (Epic #3122/#2795, PO-Freigabe in #3036); es entsteht keine neue Entscheidungsfläche.

## Changelog

- 2026-11-25: Initial spec created
