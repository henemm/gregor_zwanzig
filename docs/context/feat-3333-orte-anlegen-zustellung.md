# Context: feat-3333-orte-anlegen-zustellung

## Request Summary
Issue #3333 (D2 von #3307, Teil D von #3041, Epic #3122): Im Ortsvergleich-Anlegen ersetzt der Reiter Zustellung (Anlege-Modus aus D1, #3332, live) das Alt-Panel `WetterMetrikenVersandPanel`. Der Stand fließt in `wiz` und den einen Anlege-POST, inklusive `send_email` (fehlt heute im POST) und Aktivierungs-Banner. Alte Oberfläche samt wirkungsloser Karte „Layout je Kanal“ (#3301) verschwindet aus beiden Anlegeseiten; Wächterregel „Anlegeseiten ohne WetterMetrikenVersandPanel“; Alt-Tests/E2E umstellen; zwei Nutzer. Danach sind #3036/#3020 frei.

Grundlage und ausführliche Feld-Übergabe: `docs/context/feat-3307-zustellung-anlegen.md` (Tabelle „Feld-Übergabe“, Risiken 1–12, Abschnitt D2). D1-Spec: `docs/specs/modules/feat_3332_zustellung_anlegen_trip.md`.

## Stand nach D1 (geprüft 2026-11-24 auf main 7c9025a50)
- Trip-Anlegen: `WetterMetrikenVersandPanel` und `MailInhaltCard` sind weg; `ZustellungTab context="route" createMode zustellungStart onAnlegeStand` Desktop Z.949 / Mobil Z.1202. `AlarmeTab createMode` bleibt (Z.976/1221) mit ausgeblendeten Abschnitten `channels/cooldown/quiet-hours` (`ZUSTELLUNG_IM_ANLEGEN_AUSGELAGERT[context]`, `alarmeTabSections(context, ohneZustellung)`); `official-warnings`, `metric-levels`, `sample` bleiben dort.
- Orte-Anlegen (`compare-new/CompareNewEditor.svelte`): unverändert Alt-Panel Desktop Z.534 / Mobil Z.581 mit `wetterMetrikenPropsAus(wiz)`, `versandPropsAus(wiz)`, `activation={versandActivationBanner}` (Snippet Z.446-460), `showInfobox`; `AlarmeTab context="vergleich" {...alarmePropsAus(wiz)}` Z.537/584 hinter `alarmeHydrated` (vollständig, alle Abschnitte inkl. Kanäle/Stille/Cooldown).
- Anlege-Rückkanal existiert: `erstelleZustellungAnlegeSpeicherer` (zustellungSpeicherung.ts), ZustellungTab-Props `createMode`, `zustellungStart`, `onAnlegeStand`; Trip mischt per `mitZustellung(reportConfig, alarm, stand)`.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | Hauptänderung: ZustellungTab `context="vergleich" createMode preset={zustellungAbo} activation={versandActivationBanner} beispielAlarmRegeln` statt Panel; Handler schreibt in `wiz.*`; Imports `WetterMetrikenVersandPanel`, `versandPropsAus`, `wetterMetrikenPropsAus` entfallen. Wetter-Reiter-Muster: `wetterAbo` ($derived aus wiz) + `handleWetterAnlegeStand` Z.153-202, `karteStand` Z.164. |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | `buildNewComparePresetPayload`/`legeVergleichAn`: `send_email` ergänzen. |
| `frontend/src/lib/components/shared/zustellung-tab/{ZustellungTab.svelte,zustellungModell.ts,zustellungSpeicherung.ts}` | Anlege-Modus aus D1; `standAusPreset` (Startstand Orte), `KONTEXT`-Tabelle. Prüfen, ob Orte-Zweig des Anlege-Modus (`vergleich`) schon vollständig ist (D1 hat ihn ggf. nur für route getestet). |
| `frontend/src/lib/components/shared/AlarmeTab.svelte`, `alarme-tab/alarmeTabSections.ts` | `ZUSTELLUNG_IM_ANLEGEN_AUSGELAGERT` – für `vergleich` auf true setzen (Doppelbedienung vermeiden) oder AlarmeTab im Anlegen ganz entfernen, wenn Metrik-Alarmstufen/amtliche Warnungen/Radar im Wetter-Reiter einen Besitzer haben. |
| `frontend/src/lib/components/shared/WetterTab.svelte`, `wetter-tab/wetterTabSpeicherung.ts:166` (`ANLEGE_NUTZLAST`) | Besitz-Frage: meldet die Anlege-Nutzlast `official_alerts_enabled`, `radar_alert_enabled` (ja, siehe handleWetterAnlegeStand) und `metric_alert_levels` (offen — `wiz.metricAlertLevels` wird heute nur von Vorbelegung Z.371 und AlarmeTab geschrieben)? |
| `frontend/src/lib/components/organisms/zustellung-tab/UebergangBlock.svelte` | Aktivierungs-Snippet + Beispiel-Alarm; ohne Abo-ID im Anlegen prüfen. |
| `frontend/src/lib/components/shared/WetterMetrikenVersandPanel.svelte`, `WeatherMetricsTab`, `VersandTab` | Bleiben als Dateien (Rückbau #3036/#3020/#3297); nach D2 von keiner Anlegeseite gemountet. `CompareTabs.svelte` referenziert Panel noch? (grep-Treffer — prüfen, ob nur Kommentar). |
| `frontend/src/lib/__tests__/bausteine_waechter_regeln.ts` | neue Wächterregel „Anlegeseiten ohne WetterMetrikenVersandPanel“. |

## Existing Patterns
- D1-Trip-Verdrahtung ist die Vorlage (Stand im Editor als `$state`, `zustellungStart` für Neuaufbau/Desktop-Mobil, Inhaltsgleichheits-Guard, Read-Modify-Write in den POST-Rumpf).
- Orte: Wertprops-Brücken `{...fooPropsAus(wiz)}` nur im Markup-Ausdruck (AST-Wächter); Abo-Sicht als `$derived` aus `wiz` (wie `wetterAbo`), Meldung schreibt Feld für Feld in `wiz`, fließt nie in die Abo-Sicht zurück.

## Dependencies
- Upstream: D1 (#3332, live), Karte #3306, Wetter-Reiter-Anlegen (#2794 S3a).
- Downstream: #3036, #3020, #3297, #3301 (wird hiermit gelöst), #3277/#3298 (warten auf #3276).
- Backend: keine Änderung erwartet; `send_email` am Vergleich kennt Go seit #2795 1a (in Analyse belegen).

## Existing Specs
- `docs/specs/modules/feat_3332_zustellung_anlegen_trip.md` (D1, Abgrenzung „D2“ Z.59/61/173/175).
- `docs/specs/modules/feat_2795_s3b_teil1_zustellung.md`, `feat_3122_was_steht_wo.md` (Nr. 14 jede Einstellung genau einmal), `feat_3306_tabelle_orte_anlegen.md` („Zwei Bedienstellen bis #3307“).
- Neue Spec: `docs/specs/modules/feat_3333_zustellung_anlegen_orte.md`.

## Risks & Considerations
1. Datenverlust: Panel bestimmt heute `wiz.send*`, `morning*/evening*`, `endDate` im POST; Ersatz muss dieselben Felder bitgleich liefern (Fixture-Parität wie D1 AC-4).
2. Startstand-Defaults Orte (`standAusPreset` aus Abo-Sicht vs. heutige Wizard-Defaults, `newEntityAlertChannelDefault()` email+telegram).
3. Alarm-Doppelung: AlarmeTab-Vergleich hat Kanäle/Stille/Cooldown, die ZustellungTab jetzt besitzt → ausblenden (wie D1) oder AlarmeTab im Anlegen entfernen (Issue-Wortlaut „alte Oberfläche … aus beiden Anlegeseiten weg“ + D1-Spec „entfällt in D2 nach Beleg“). Beleg Metrik-Alarmstufen/Radar/amtl. Warnungen im Wetter-Reiter ist in der Analyse zu führen.
4. `send_email` neu im POST — Go-Validierung/Persistenz und Zwei-Nutzer-Test.
5. Aktivierungs-Banner (`compare-step5-activation-banner`, `data-ready`) muss über `ZustellungTab.activation` erhalten bleiben (E2E/Unit hängen dran).
6. Große Alt-Testmenge (Liste in Parent-Context Z.96-105); nicht still löschen, auf Verhalten umstellen.
7. Infobox im Orte-Anlegen entfällt mit dem Panel (Hub-Parität, wie D1 AC-11).

## Analysis

### Type
Feature (Anlege-Modus für Ortsvergleich verdrahten + Alt-Panel aus dem Orte-Anlegen entfernen). Trip-Anlegen ist seit D1 bereits ohne Panel.

### Befunde (Explore, 2026-11-24)
- ZustellungTab-Anlegemodus ist kontextneutral (`ZustellungTab.svelte:80`, `KONTEXT.vergleich` in `zustellungSpeicherung.ts:36`, `versandTeil`/`alarmeTeil` liefern `end_date`, `morning_*`, `evening_*`, `send_*`, `alert_*`), aber nur für `route` verdrahtet/getestet. **Absturzgefahr:** ohne `zustellungStart` und ohne `preset` wirft `standAusPreset(undefined)` (`zustellungModell.ts:283ff`) → Editor muss ein Stub-Abo (`id:''`) übergeben.
- `onAnlegeStand` liefert `{stand, nutzlast:{versand, alarme}}` (`zustellungSpeicherung.ts:87-111`). Trip-Pendant `mitZustellung` (`trip-new/tripNewLogic.ts:361-385`); für Vergleich fehlt ein reiner Helfer `mitZustellungVergleich(wiz, stand)` → Felder `morningEnabled/Time`, `eveningEnabled/Time`, `sendEmail/Telegram/Sms/PremiumSms`, `endDate`, `channels`, `channelThresholds`, `alertQuietFrom/To`, `alertCooldownMinutes`.
- wiz-Defaults `compareFeldsatzStandard()` (`compareEditorSave.ts:~538-570`): sendEmail true, send_* false, Morgen 07:00 an, Abend 18:00 aus, endDate null, channels undefined → POST-Rückfall `newEntityAlertChannelDefault` (:426), cooldown/quiet undefined.
- `send_email` fehlt im POST (`NewComparePresetFields` :320ff, `baueVergleichAnlegeRumpf` :592ff). Go kennt es (`internal/model/compare_preset.go:94`, `SendEmail *bool omitempty`, Update-Roundtrip getestet `internal/handler/zustellung_2795_test.go:267/308`; Create-Test fehlt → im E2E/Go-Test belegen).
- **AlarmeTab kann im Anlegen nicht ganz entfallen:** `metric_alert_levels` (Empfindlichkeit je Metrik) und `alertMetricChannels` haben außerhalb des AlarmeTab keine Bedienstelle (WetterTab schreibt nur `ampel.alarm_ab`, `vergleichNutzlast` lässt `metric_alert_levels` weg). Lösung wie D1: `ZUSTELLUNG_IM_ANLEGEN_AUSGELAGERT.vergleich = true` (`alarme-tab/alarmeTabSections.ts:46`) → Kanäle/Cooldown/Stille Stunden nur noch im Reiter Zustellung. Doppelbedienung amtliche Warnungen/Radar (AlarmeTab + WetterTab) besteht schon heute in beiden Anlegeseiten, nicht Teil von D2 → Nebenbefund.
- UebergangBlock ohne `preset.id`: kein Abruf, Platzhalter `alert-preview-unsaved` (`AlertPreviewCard.svelte:79-83`) → unkritisch. Aktivierungs-Banner über `activation`-Snippet.
- Nach Entfernen hat `WetterMetrikenVersandPanel` keinen Mount mehr (`CompareTabs.svelte:45` nur Kommentar); `versandPropsAus`/`wetterMetrikenPropsAus` nur noch vom Panel genutzt → tote Dateien bleiben bis Rückbau #3020/#3036 (dort löschen), D2 entfernt nur die Mounts/Imports.
- Wächterregel: kein Regeltyp „darf nicht importieren“ in `bausteine_waechter_regeln.ts`; Vorbild `shared/__tests__/*_laedt_keine_compare_klebeschicht.test.ts` (neuer Test „Anlegeseiten ohne WetterMetrikenVersandPanel“, beide Editoren).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `compare-new/CompareNewEditor.svelte` | MODIFY (~+30/-15) | `zustellungStand` $state, Stub-Abo `$derived` aus wiz (id '', location_ids, send_*, morning/evening, end_date, alert_*), `handleZustellungAnlegeStand` → `mitZustellungVergleich`; ZustellungTab Desktop+Mobil statt Panel, `activation={versandActivationBanner}`; Imports Panel/versandPropsAus/wetterMetrikenPropsAus raus |
| `compare/compareEditorSave.ts` | MODIFY (~+20) | `mitZustellungVergleich` (rein) oder in eigenem Modul; `send_email` in `NewComparePresetFields`/POST-Rumpf |
| `shared/alarme-tab/alarmeTabSections.ts` | MODIFY (1 Zeile) | `vergleich: true` |
| Tests | CREATE/MODIFY | neu: reiner Helfer, POST mit `send_email:false`, SSR-Verdrahtung (ZustellungTab statt Panel), Wächter „Anlegeseiten ohne Panel“; Alt-Tests aus Explore-Liste auf Verhalten umstellen; E2E Orte-Anlegen mit Zeiten/Kanal/Stille → ein POST → Hub, zwei Nutzer |

### Scope Assessment
- Produktion: 3 Dateien, ca. +60/-20 LoC. Tests: ~4 neu, ~10-20 anpassen.
- Risk Level: MEDIUM (Datenverlust-Klasse POST-Felder; Alt-Testmenge).

### Technical Approach
D1-Muster 1:1 auf `vergleich`: Stand im Editor, Startstand beim Neuaufbau zurückreichen, reiner Misch-Helfer Feld-für-Feld in `wiz` (Read-Modify-Write, Inhaltsgleichheits-Guard), `send_email` im POST nur zusätzlich (Default true → ohne Änderung bitgleich zu heute außer neuem Feld; Entscheidung Spec: immer senden, Wert aus wiz). AlarmeTab-Abschnitte wie Trip. Panel-Dateien bleiben bis #3020/#3036.

### Open Questions
- Keine Produktfrage (Anlegen = Bearbeiten ist PO-Vorgabe).

## Entscheidungen aus TDD RED (2026-11-24)
- Schnittstelle: `mitZustellungVergleich(wiz, stand)` in `compare/compareEditorSave.ts`, schreibt in-place, `undefined` = no-op, Kopien für channels/channelThresholds, Stille aus = alertQuietFrom/To undefined. Editor: `zustellungStand`, `zustellungAbo` (id '', location_ids), `handleZustellungAnlegeStand`; Guard: gleicher Inhalt ⇒ dieselben Objekte.
- In GREEN umzustellen (widersprechen AC direkt): `trip_anlegen_zustellung_ssr_3332` Test 6, `alarme_tab_ohne_zustellung_3332` (vergleich vollständig), `compare_new_editor_postet_einmal`, `infobox_nur_beim_anlegen`; dazu DoD-Liste der Spec und laut grep: s3a2794_eine_wmt_instanz, s3a2794_teil3_wettertab_mount, compare_versand_wertprops, compare_alarme_wertprops, anlegen_ohne_autosave, wetter_metriken_versand_panel_paritaet, hub_geteilte_felder_cooldown_quiet_konsistent, versand_panel_ohne_wrapper_div, compare_wizard_state_entfernt, standardwerte_payload_paritaet_compare; E2E hub-anlegen-ablauf (Orte-Teil) und Alt-Panel-Selektoren (`compare-step5-channel-email`, issue-609-sms-profil:69).
