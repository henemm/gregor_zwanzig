---
entity_id: feat_3333_zustellung_anlegen_orte
type: module
created: 2026-11-24
updated: 2026-11-24
status: draft
version: "1.0"
workflow: feat-3333-orte-anlegen-zustellung
tags: [zustellung, anlegen, ortsvergleich, alarme, epic-3122]
---

# Reiter Zustellung beim Ortsvergleich-Anlegen (#3333, Teil D2 von #3307)

## Approval

- [ ] Approved

## Purpose

Beim Anlegen eines Ortsvergleichs bedient der Nutzer Briefing-Zeiten, Kanäle, Alarm-Kanäle mit Dringlichkeit, Stille Stunden und Cooldown im selben Reiter „Zustellung“ wie im Hub eines gespeicherten Vergleichs (Anlegen = Bearbeiten) und nicht mehr im Alt-Panel. Der Stand reist im einen Anlege-Aufruf mit, einschließlich des bisher fehlenden Felds `send_email`, und der Aktivierungs-Banner bleibt erhalten. Damit verschwindet das Alt-Panel samt wirkungsloser Karte „Layout je Kanal“ (#3301) aus beiden Anlegeseiten, und #3036/#3020 sind frei. Teil D2 von #3307 (Teil D von #3041, Epic #3122); Teil D1 (Trip, #3332) ist live.

## Source

- **File:** `frontend/src/lib/components/compare-new/CompareNewEditor.svelte`, `frontend/src/lib/components/compare/compareEditorSave.ts`, `frontend/src/lib/components/shared/alarme-tab/alarmeTabSections.ts`
- **Identifier:** `CompareNewEditor` (`zustellungStand`, `zustellungAbo`, `handleZustellungAnlegeStand`), `mitZustellungVergleich` (neu), `NewComparePresetFields.send_email`, `baueVergleichAnlegeRumpf`, `buildNewComparePresetPayload`, `ZUSTELLUNG_IM_ANLEGEN_AUSGELAGERT`

> **Schicht-Hinweis:** Ausschließlich Frontend (SvelteKit, `frontend/src/...`). Go-API (kennt `send_email` am Vergleich, `internal/model/compare_preset.go:94`) und Python-Core bleiben unverändert; kein Backend-Code.

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Keine neue Komponente. Der bestehende `ZustellungTab` (D1-Anlegemodus, `context="vergleich"`) wird verdrahtet; Kontext-Unterschiede bleiben Daten in der `KONTEXT`-Tabelle (Ratsche `context_herkunft_zweige_eingefroren`, Gate #1170). Der neue Helfer ist das Orte-Pendant zu `mitZustellung` (Trip), kein zweiter Reiter.
> - **Mandantentrennung:** Der POST legt beim angemeldeten Nutzer an, nie `"default"`; Kanalstatus und Telegram-Verbindung kommen aus dem Profil des angemeldeten Nutzers. Test mit zwei verschiedenen Nutzern.
> - **Kanäle:** E-Mail, Telegram, SMS und Premium-SMS stehen gleichrangig in der Kanal-Tabelle; Briefing- und Alarm-Kanäle bleiben getrennt wählbar (ADR-0095).

## Estimated Scope

- **LoC:** Produktion ca. +60 bis +90 netto (Zielgrenze ~250), Tests ca. +250 bis +400 (zählen nicht mit)
- **Files:** 3 Produktionsdateien, ca. 4 neue und ca. 10 bis 20 angepasste Testdateien
- **Effort:** medium (Risiko MEDIUM: Datenverlust-Klasse POST-Felder, große Alt-Testmenge)

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | MODIFY (~+30/-15) | `zustellungStand` als `$state`, Stub-Abo `zustellungAbo` als `$derived` aus `wiz` (`id: ''`), `handleZustellungAnlegeStand` mit Inhaltsgleichheits-Guard; `ZustellungTab context="vergleich" createMode` (Desktop und Mobil) ersetzt `WetterMetrikenVersandPanel`; `activation={versandActivationBanner}`; Imports Panel, `versandPropsAus`, `wetterMetrikenPropsAus` entfallen |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | MODIFY (~+30) | Reiner Helfer `mitZustellungVergleich(wiz, stand)`; `send_email` in `NewComparePresetFields` und `baueVergleichAnlegeRumpf`/`buildNewComparePresetPayload` (immer aus `wiz.sendEmail`) |
| `frontend/src/lib/components/shared/alarme-tab/alarmeTabSections.ts` | MODIFY (1 Zeile) | `ZUSTELLUNG_IM_ANLEGEN_AUSGELAGERT.vergleich = true` |
| Tests (`node --test`) | CREATE/MODIFY | siehe Test Plan |
| `frontend/e2e/orte-anlegen-zustellung-3333.spec.ts` | CREATE | Zustellung bedienen, ein POST mit Zeiten, Kanal, Stille, `send_email:false`, Hub-Reiter zeigt denselben Stand, zwei Nutzer |
| `frontend/e2e/*` mit Alt-Panel-Selektoren im Orte-Anlegen | MODIFY | Selektoren und Annahmen auf den Reiter Zustellung umstellen (z. B. `hub-anlegen-ablauf.spec.ts`, Orte-Teil) |

### Nicht in dieser Spec

- Backend (Go, Python), Hub (unverändert), Trip-Anlegen (unverändert, außer dem neuen Wächtertest).
- Löschen von `WetterMetrikenVersandPanel`, `versandPropsAus`, `wetterMetrikenPropsAus`, `WeatherMetricsTab`, `VersandTab`: gehört zu #3020/#3036/#3297; es wird keine Datei gelöscht.
- Ganz-Entfernen des Reiters Alarme im Anlegen (siehe Known Limitations).
- Änderungen an Gate-Konfiguration; der Auftrag braucht keine Sperren-Aufhebung.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ZustellungTab` (`createMode`, `zustellungStart`, `onAnlegeStand`, `activation`, `preset`) | Frontend | D1-Anlegemodus, hier für `vergleich` verdrahtet |
| `erstelleZustellungAnlegeSpeicherer`, `standAusPreset`, `KONTEXT.vergleich` (`zustellungSpeicherung.ts`, `zustellungModell.ts`) | Frontend | Rückkanal ohne Netz, Startstand aus Abo-Sicht (wirft bei `undefined`, daher Stub-Abo) |
| `mitZustellung` (`trip-new/tripNewLogic.ts:361`) | Frontend | Vorbild für den Orte-Helfer |
| `compareFeldsatzStandard`, `baueVergleichAnlegeRumpf`, `newEntityAlertChannelDefault` (`compareEditorSave.ts`) | Frontend | Standardwerte und POST-Rumpf |
| `versandActivationBanner` (Snippet im Editor), `UebergangBlock` | Frontend | Aktivierungs-Banner (`compare-step5-activation-banner`, `data-ready`) |
| `AlarmeTab`, `alarmeTabSections` | Frontend | Abschnittsliste mit Ausblenden der Zustellungs-Abschnitte |
| `feat_3332_zustellung_anlegen_trip` | Spec | D1, gleiches Muster (AC-4 Fixture-Parität, AC-9 Alarm-Doppelung, AC-11 Infobox) |
| `feat_2795_s3b_teil1_zustellung`, `feat_3306_tabelle_orte_anlegen`, `feat_3122_was_steht_wo` | Spec | Reiter, Karte im Orte-Anlegen, Nr. 14 „Jede Einstellung genau einmal“ |
| `GET /api/auth/profile` | API | Kanalstatus und Telegram-Verbindung je Nutzer |
| ADR-0095, ADR-0097, ADR-0124 | ADR | Kanal-Parität, Code-Teilung, eine Tabelle |

## Implementation Details

**Anlege-Modus für Orte.** `CompareNewEditor` mountet im Schritt Zustellung (Desktop und Mobil) `ZustellungTab` mit `context="vergleich"`, `createMode`, `preset={zustellungAbo}`, `zustellungStart={zustellungStand}`, `onAnlegeStand` und `activation={versandActivationBanner}` statt `WetterMetrikenVersandPanel`. `zustellungAbo` ist ein `$derived` aus `wiz` mit `id: ''` (Stub-Abo; ohne es wirft `standAusPreset(undefined)`) und liefert den Startstand aus den heutigen Wizard-Standardwerten (E-Mail an, Morgen 07:00 an, Abend 18:00 aus, Alarm-Kanäle E-Mail und Telegram an).

**Stand im Editor.** `zustellungStand` ist ein `$state`, der beim Neuaufbau (Schrittwechsel, Desktop/Mobil) als `zustellungStart` zurückgegeben wird. Die Meldung ändert nie die Abo-Sicht (Schleifenschutz, Muster `wetterAbo`/`handleWetterAnlegeStand`); ein Inhaltsgleichheits-Guard verhindert Update-Schleifen.

**Reiner Helfer `mitZustellungVergleich(wiz, stand)`.** Schreibt Feld für Feld in `wiz`: `morningEnabled/Time`, `eveningEnabled/Time`, `sendEmail/Telegram/Sms/PremiumSms`, `endDate`, `channels`, `channelThresholds`, `alertQuietFrom/To`, `alertCooldownMinutes`. Read-Modify-Write (bestehende Felder bleiben), kein Replace; rasterfremde Uhrzeiten werden nie übernommen (letzte gültige bleibt, Server verlangt Viertelstunden-Raster). Der Helfer ist rein und ohne Mock testbar.

**`send_email` im POST.** `NewComparePresetFields` und `baueVergleichAnlegeRumpf` senden `send_email` immer aus `wiz.sendEmail`. Ohne Nutzeränderung ist der POST bis auf das neue Feld `send_email: true` bitgleich zu heute (Fixture-Parität wie D1 AC-4). Go kennt das Feld bereits (`SendEmail *bool omitempty`).

**Nie beide Schreiber.** Das Alt-Panel entfällt im Orte-Anlegen; der Reiter ist der einzige Schreiber der Versand-Felder.

**Alarm-Doppelung (Entscheidung D2).** `ZUSTELLUNG_IM_ANLEGEN_AUSGELAGERT.vergleich = true`: im Orte-Anlegen entfallen im Reiter Alarme die Abschnitte Kanäle, Cooldown und Stille Stunden; sie stehen nur noch im Reiter Zustellung. Amtliche Warnungen, Radar, Metrik-Alarmstufen und Beispiel bleiben (`metric_alert_levels` hat sonst keine Bedienstelle). Hub und Trip-Anlegen unverändert.

**Karte „Layout je Kanal“ (#3301).** Verschwindet im Anlegen mit dem Panel (war wirkungslos). Panel-Dateien bleiben als Dateien; nach D2 importiert keine Anlegeseite das Panel. Neuer Wächtertest „Anlegeseiten (TripNewEditor, CompareNewEditor) ohne WetterMetrikenVersandPanel“ nach Muster `shared/__tests__/*_laedt_keine_compare_klebeschicht.test.ts`.

**Infobox.** Die Infobox des Alt-Panels im Orte-Anlegen entfällt (Hub-Parität wie D1 AC-11); die Infobox des `AlarmeTab` bleibt nur beim Anlegen.

## Expected Behavior

- **Input:** Nutzer legt einen Ortsvergleich an, stellt im Schritt Zustellung Morgen 06:45, Kanal Telegram, Stille Stunden ein und schaltet E-Mail ab.
- **Output:** Genau ein `POST` auf die Vergleichs-Anlage mit diesen Werten (`send_email: false`, `morning_time` 06:45, Telegram, `alert_quiet_from/_to`); der Hub-Reiter Zustellung des neuen Vergleichs zeigt denselben Stand.
- **Side effects:** Nur der lesende Profil-Abruf; kein PUT, kein Speichern vor dem Anlegen.

## Acceptance Criteria

- **AC-1:** Given ein angemeldeter Nutzer legt einen Ortsvergleich an / When er den Schritt Zustellung öffnet, in der Mobil- und in der Desktop-Ansicht / Then sieht er den Reiter Zustellung mit Briefing-Zeiten, Kanal-Tabelle und Stille Stunden wie im Hub, und das Alt-Panel (Versand-Abschnitt, Karte „Layout je Kanal“, Infobox) erscheint dort nicht mehr.
  - Test: E2E in beiden Ansichten: `zustellung-tab` sichtbar, Alt-Panel-Testids (`channel-email` u. a.) abwesend; SSR-Test des Editors mountet `ZustellungTab` und kein `WetterMetrikenVersandPanel`.

- **AC-2:** Given der Nutzer stellt im Orte-Anlegen Briefing-Zeiten, Kanäle und Stille Stunden ein / When er den Vergleich anlegt / Then enthält der eine POST `morning_time`/`evening_time`, `morning_enabled`/`evening_enabled`, `send_email/telegram/sms/premium_sms`, `end_date` und `alert_quiet_from/_to` mit genau den eingestellten Werten.
  - Test: E2E zeichnet den POST-Körper auf und vergleicht; Unit-Test `mitZustellungVergleich` mit gesetztem Stand und anschließendem Rumpfbau.

- **AC-3:** Given der Nutzer wählt Alarm-Kanäle, die Dringlichkeit HIGH für Telegram und einen Cooldown / When er den Vergleich anlegt / Then stehen `alert_channels`, `alert_channel_thresholds.telegram == "HIGH"` und `alert_cooldown_minutes` im POST.
  - Test: E2E mit Selektor `zustellung-kanal-telegram-dringlichkeit-HIGH` prüft den POST; Unit-Test `mitZustellungVergleich`.

- **AC-4:** Given der Nutzer schaltet im Reiter die E-Mail ab / When er den Vergleich anlegt / Then enthält der POST `send_email: false`; bei unberührter E-Mail enthält er `send_email: true`, weil das Feld jetzt immer mitgesendet wird.
  - Test: Unit-Test `baueVergleichAnlegeRumpf` mit `wiz.sendEmail` true und false; E2E prüft den aufgezeichneten POST nach Abwahl.

- **AC-5:** Given der Nutzer öffnet den Schritt Zustellung, bedient den Reiter aber nicht / When er den Vergleich anlegt / Then ist der POST-Körper bis auf das neue Feld `send_email: true` bitgleich zum heutigen Körper (Zeiten, Kanäle, Alarm-Felder, Standardwerte).
  - Test: Unit-Test vergleicht den Körper mit Referenz-Fixture ohne Reiter-Bedienung (Regressionsschutz, Datenverlust-Klasse); Bestandstest `feat3276_vergleich_ohne_altfelder` bleibt grün.

- **AC-6:** Given der Nutzer ändert Werte im Reiter / When er bis zum Anlegen weitermacht / Then gibt es weder einen PUT noch einen Autosave noch einen Schreibaufruf vor dem Anlegen, und beim Anlegen genau einen POST.
  - Test: E2E zählt Netzwerkaufrufe: null PUT, null Schreibaufrufe vor dem Anlegen, genau ein POST; `compare_new_editor_postet_einmal` und `anlegen_ohne_autosave` bleiben grün.

- **AC-7:** Given der Nutzer hat im Reiter Zustellung Werte gesetzt / When er zwischen Mobil und Desktop wechselt oder Schritte vor und zurück geht / Then bleibt der Stand erhalten und die Werte stehen unverändert im POST.
  - Test: E2E: Wert setzen, Ansicht und Schritte wechseln, Wert prüfen; Unit-Test: Neuaufbau mit `zustellungStart` ergibt denselben Stand.

- **AC-8:** Given der Nutzer gibt eine rasterfremde Uhrzeit ein (z. B. 06:50) / When er den Vergleich anlegt / Then sendet der POST die letzte gültige Viertelstunden-Zeit und es gibt keinen Server-Fehler 400.
  - Test: Unit-Test `mitZustellungVergleich` mit ungültiger Zeit (Wert unverändert); E2E mit 06:50 legt erfolgreich an.

- **AC-9:** Given ein Ortsvergleich wird im Anlegen mit gesetzter Zustellung angelegt / When der Nutzer danach den Hub-Reiter Zustellung öffnet / Then zeigt er dieselben Zeiten, Kanäle, Dringlichkeiten, Stille Stunden, denselben Cooldown und den E-Mail-Schalter wie beim Anlegen eingestellt.
  - Test: E2E-Rückweg: nach dem Anlegen Hub-Reiter öffnen und jeden eingestellten Wert vergleichen (Zeiten 06:45, Telegram, Stille Stunden, E-Mail aus).

- **AC-10:** Given der Nutzer ist im Schritt Alarme des Orte-Anlegens / When er den Reiter öffnet / Then fehlen dort Alarm-Kanäle, Cooldown und Stille Stunden (sie stehen im Reiter Zustellung), während amtliche Warnungen, Radar und Metrik-Alarmstufen dort bleiben; jedes Feld hat genau eine Bedienstelle, und Hub und Trip-Anlegen sind unverändert.
  - Test: Unit-Test `alarmeTabSections` für `vergleich` (Abschnitte fehlen im Anlegen, im Hub vollständig, `route` unverändert); E2E prüft die Bedienstellen je Feld.

- **AC-11:** Given der Aktivierungs-Banner im Orte-Anlegen / When der Nutzer den Schritt Zustellung öffnet / Then erscheint der Banner weiter (`compare-step5-activation-banner`, `data-ready` unverändert) und stammt aus dem Reiter Zustellung, nicht aus dem Alt-Panel.
  - Test: Angepasste Bestandstests `compare_new_editor_postet_einmal` und `s3a2794_*` prüfen Testid und `data-ready`; E2E sieht den Banner im Reiter.

- **AC-12:** Given der Reiter Zustellung im Orte-Anlegen / When der Nutzer ihn öffnet / Then erscheint dort keine Infobox des Alt-Panels mehr, während die Infobox im Reiter Alarme beim Anlegen wie bisher erscheint.
  - Test: Angepasster Test `infobox_nur_beim_anlegen`: Reiter Zustellung ohne Infobox, Alarme-Reiter nur beim Anlegen, Hub ohne Infobox.

- **AC-13:** Given die Anlegeseiten Trip und Ortsvergleich / When der Code geprüft wird / Then importiert und mountet keine der beiden Anlegeseiten `WetterMetrikenVersandPanel`, und die Dateien des Panels bleiben bis zum Rückbau (#3020, #3036) bestehen.
  - Test: Wächtertest „Anlegeseiten ohne WetterMetrikenVersandPanel“ (Import-/Mount-Prüfung beider Editoren, Muster `*_laedt_keine_compare_klebeschicht.test.ts`; dokumentierter Strukturwächter, kein Verhaltensnachweis); Verhalten bleibt durch AC-1 belegt.

- **AC-14:** Given zwei verschiedene Nutzer A und B mit verschiedenem Kanalstatus (A hat Telegram verbunden, B nicht) / When beide je einen Ortsvergleich anlegen / Then zeigt der Reiter bei A die Dringlichkeit für Telegram und bei B nicht, jeder Vergleich erscheint nur beim jeweiligen Nutzer, und B sieht den Vergleich von A nicht.
  - Test: E2E mit zwei Prüfkonten (`orte-anlegen-zustellung-3333.spec.ts`): Profil-Status je Nutzer, Anlage je Nutzer, gegenseitige Listen.

- **AC-15:** Given das Trip-Anlegen / When der Nutzer einen Trip anlegt / Then verhält es sich unverändert wie nach D1 (Reiter Zustellung, ein POST).
  - Test: Bestandstests und E2E aus D1 (`trip-anlegen-zustellung-3332.spec.ts`) bleiben grün.

## Definition of Done

- AC-1 bis AC-15 durch Kern-Tests (`node --test`, ohne Mock-Theater) und E2E grün; Datenverlust (AC-2, AC-3, AC-4, AC-5) und Doppelbedienung (AC-10) zuerst rot nachgewiesen.
- Alt-Tests nicht still gelöscht, sondern auf Verhalten umgestellt: `vergleich_anlegen_karte_verdrahtung_3306`, `compare_anlege_freischaltung`, `compare_wetter_metriken_wertprops`, `compare_versand_hydration_unter_wetter_metriken`, `compare_wizard_save_new_preset_channels`, `compare_layout_tab_dissolution`, `fix_3061_hub_hydrierer`, `compare_hub_uebernimmt_serverantwort_als_basis`, `compare_new_editor_postet_einmal`, `infobox_nur_beim_anlegen`; `feat3276_vergleich_ohne_altfelder` bleibt grün. Tests, die nur das Panel-Bauteil selbst prüfen (Datei existiert bis #3020/#3036), bleiben bestehen; reine Mount-Annahmen im Anlegen werden umgestellt. Ratsche `context_herkunft_zweige_eingefroren` und Wächterliste (`bausteine_waechter_regeln.ts`) ohne neue Verstöße.
- Staging: Ortsvergleich mit Prüfkonto angelegt (Zeiten 06:45, Telegram, Stille Stunden, E-Mail aus), genau ein POST, Hub-Reiter Zustellung zeigt denselben Stand; zweiter Nutzer sieht nichts.
- Live auf Produktion, Selftest Exit 0. Keine Änderung an Gate-Konfiguration, keine menschliche Sperren-Aufhebung nötig.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN Stand mit Zeiten, Kanälen, Stille, Cooldown WHEN `mitZustellungVergleich` THEN `wiz`-Felder wie erwartet, übrige Felder erhalten, kein Rückfluss in die Abo-Sicht (AC-2, AC-3)
- [ ] Test 2: GIVEN rasterfremde Zeit WHEN `mitZustellungVergleich` THEN letzte gültige Zeit bleibt (AC-8)
- [ ] Test 3: GIVEN `wiz.sendEmail` true/false WHEN `baueVergleichAnlegeRumpf` THEN `send_email` entsprechend im POST (AC-4)
- [ ] Test 4: GIVEN Reiter nicht bedient WHEN Rumpf gebaut THEN bitgleich zu Referenz-Fixture heute plus `send_email: true` (AC-5)
- [ ] Test 5: GIVEN `alarmeTabSections` für `vergleich` im Anlegen THEN `channels`, `cooldown`, `quiet-hours` fehlen, Rest und Hub unverändert (AC-10)
- [ ] Test 6: GIVEN Orte-Editor SSR WHEN Schritt Zustellung THEN `ZustellungTab` gemountet, `WetterMetrikenVersandPanel` nicht; Banner-Testid und `data-ready` vorhanden (AC-1, AC-11)
- [ ] Test 7: GIVEN Neuaufbau mit `zustellungStart` THEN gleicher Stand; Stub-Abo mit `id: ''` wirft nicht (AC-7)
- [ ] Test 8: GIVEN Infobox-Test angepasst THEN Reiter Zustellung ohne Infobox (AC-12)
- [ ] Test 9: Wächtertest „Anlegeseiten ohne WetterMetrikenVersandPanel“ (AC-13)
- [ ] Test 10: E2E `orte-anlegen-zustellung-3333.spec.ts`: Zeiten 06:45, Telegram, Stille Stunden, E-Mail aus, ein POST, kein PUT, Hub zeigt denselben Stand (AC-2, AC-4, AC-6, AC-9)
- [ ] Test 11: E2E beide Ansichten, Stand überlebt Wechsel (AC-1, AC-7)
- [ ] Test 12: E2E zwei Nutzer (AC-14)
- [ ] Test 13: Alt-Tests und Alt-E2E auf Verhalten umgestellt (Liste in Definition of Done)

Test-Politik: kein Mock-Theater; Kern-Tests deterministisch ohne Netz (`node --test`, kein Vitest), Live-Nachweis im E2E gegen Staging. Dateiinhalt-Checks sind kein Verhaltensnachweis (einzige Ausnahme: der Strukturwächter in AC-13, als solcher gekennzeichnet).

## Known Limitations

- Der Reiter Alarme bleibt im Orte-Anlegen (und im Trip-Anlegen) mit Metrik-Alarmstufen, amtlichen Warnungen, Radar und Beispiel bestehen. Begründung: `metric_alert_levels` und `alertMetricChannels` haben außerhalb des Reiters keine Bedienstelle; Ganz-Entfernen ist nicht Teil von D2.
- Amtliche Warnungen und Radar sind im Anlegen an zwei Stellen bedienbar (Alarme-Reiter und Wetter-Reiter). Das besteht schon heute in beiden Anlegeseiten, ist nicht Teil von D2 und wird als Nebenbefund erfasst.
- Mit dem Alt-Panel entfallen im Orte-Anlegen die ⓘ-Erklärungen zu Dringlichkeit und Cooldown sowie die Karte „Layout je Kanal“ (#3301, wirkungslos); Hub-Parität.
- Die Dringlichkeit je Kanal ist nur sichtbar, wenn Alarm für den Kanal an und der Kanal verbunden ist (Verhalten des Reiters, wie im Hub).
- Panel und seine Bausteine (`WetterMetrikenVersandPanel`, `versandPropsAus`, `wetterMetrikenPropsAus`, `WeatherMetricsTab`, `VersandTab`) bleiben als tote Dateien bis #3020/#3036/#3297.
- Der Aktivierungs-Banner prüft ohne Abo-ID im Anlegen keinen Serverstand; die Vorschau zeigt den Platzhalter „ungespeichert“ (`alert-preview-unsaved`).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue (ADR-0095, ADR-0097, ADR-0124 gelten unverändert)
- **Rationale:** Umsetzung der PO-Vorgabe „Anlegen = Bearbeiten“ mit gemeinsamem Code für Trip und Ortsvergleich (Epic #3122); ADR-0124 Nr. 14 verlangt jede Einstellung genau einmal. Alarm-Abschnittsschnitt und Infobox sind Tech-Entscheidungen auf Basis der Hub-Parität wie in D1 und ändern keine frühere Entscheidung.

## Changelog

- 2026-11-24: Initial spec created (Teil D2 von #3307, Issue #3333, Epic #3122).
