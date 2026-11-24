---
entity_id: feat_3332_zustellung_anlegen_trip
type: module
created: 2026-11-24
updated: 2026-11-24
status: approved
version: "1.0"
workflow: feat-3307-zustellung-anlegen
tags: [zustellung, anlegen, trip, alarme, epic-3122]
---

# Reiter Zustellung beim Trip-Anlegen (#3332, Teil D1 von #3307)

## Approval

- [x] Approved (automatisch, Ampel grün, 2026-11-24)

## Purpose

Beim Anlegen eines Trips bedient der Nutzer Briefing-Zeiten, Kanäle, Alarm-Kanäle mit Dringlichkeit, Stille Stunden und Cooldown im selben Reiter „Zustellung“ wie im Hub eines gespeicherten Trips (Anlegen = Bearbeiten) und nicht mehr im Alt-Panel. Der Stand reist im einen Anlege-Aufruf mit, und nach dem Anlegen zeigt der Hub-Reiter Zustellung genau diesen Stand. Teil D1 von #3307 (Teil D von #3041, Epic #3122); Ortsvergleich-Anlegen (D2, #3333) ist nicht Teil dieser Spec.

## Source

- **File:** `frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte`, `frontend/src/lib/components/shared/zustellung-tab/zustellungSpeicherung.ts`, `frontend/src/lib/components/trip-new/TripNewEditor.svelte`
- **Identifier:** `ZustellungTab` (Props `createMode`, `zustellungStart`, `onAnlegeStand`), `erstelleZustellungAnlegeSpeicherer` (neu, Muster `anlegeSpeicherer`), `zustellungNutzlast`, `zustellungStand` und `handleZustellungAnlegeStand` (neu im Editor), `alarmeTabSections`

> **Schicht-Hinweis:** Ausschließlich Frontend (SvelteKit, `frontend/src/...`). Go-API (Anlage nimmt `report_config`, `alert_*` wie bisher) und Python-Core bleiben unverändert; die POST-Felder sind dieselben wie heute.

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Keine neue Komponente. Der bestehende `ZustellungTab` bekommt nur einen `createMode`-Zweig; Kontext-Unterschiede bleiben Daten in der `KONTEXT`-Tabelle (Ratsche `context_herkunft_zweige_eingefroren`, Gate #1170). Der Ortsvergleich nutzt den Zweig in D2 (#3333); bis dahin bleibt dort das Alt-Panel unverändert.
> - **Mandantentrennung:** Der POST legt beim angemeldeten Nutzer an, nie `"default"`; Kanalstatus und Telegram-Verbindung kommen aus dem Profil des angemeldeten Nutzers (ein Abruf `/api/auth/profile`). Test mit zwei verschiedenen Nutzern.
> - **Kanäle:** E-Mail, Telegram, SMS und Premium-SMS stehen in der Kanal-Tabelle gleichrangig; kein Kanal ersetzt einen anderen, Briefing- und Alarm-Kanäle bleiben getrennt wählbar.

## Estimated Scope

- **LoC:** Produktion ca. +150 bis +190 netto (Zielgrenze ~250), Tests ca. +300 bis +450 (zählen nicht mit)
- **Files:** 6 bis 7 Produktionsdateien, ca. 6 neue und ca. 8 angepasste Testdateien
- **Effort:** medium (Risiko MEDIUM bis HIGH: Datenverlust, wenn Alt-Panel entfällt und der Stand nicht im POST ankommt; Doppelbedienung Alarm-Felder; Doppel-POST)

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte` | MODIFY (~+25) | Props `createMode?`, `zustellungStart?: ZustellungStand` (Startstand vom Editor, sonst `KONTEXT.stand()`), `onAnlegeStand?`; bei `createMode` Anlege-Speicherer statt `erstelleZustellungSpeicherung`; ohne `saveController` und ohne Netz |
| `frontend/src/lib/components/shared/zustellung-tab/zustellungSpeicherung.ts` | MODIFY (~+20) | `erstelleZustellungAnlegeSpeicherer({context, basis, anlegen})`: `aenderungMelden(jetzt)` ruft `anlegen({stand: jetzt, nutzlast: zustellungNutzlast(context, basis, jetzt)})`; kein zweiter Nutzlast-Baustein |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | MODIFY (~+55/-35) | `zustellungStand` als `$state` (überlebt Schrittwechsel und Desktop/Mobil), `handleZustellungAnlegeStand`; `ZustellungTab` (Desktop und Mobil) ersetzt im Schritt Zustellung `WetterMetrikenVersandPanel` und `MailInhaltCard`; `AlarmeTab` mit ausgeblendeten Zustellungs-Abschnitten; `handleChannelsChange` entfällt; Eintrittstrip aus `stubTrip` und Alarm-Startwerten |
| `frontend/src/lib/components/trip-new/tripNewLogic.ts` | MODIFY (~+30) | Reiner Helfer `mitZustellung(reportConfig, alarm, stand)`: mischt per Read-Modify-Write in `report_config` und die Alarm-Felder des einen POST (Muster `mitKarte`); ungültige Uhrzeit wird nie gesendet, letzte gültige bleibt |
| `frontend/src/lib/components/shared/alarme-tab/alarmeTabSections.ts` | MODIFY (~+10) | Optionaler Parameter `ohneZustellung`: lässt `channels`, `cooldown`, `quiet-hours` weg (datengetrieben) |
| `frontend/src/lib/components/shared/AlarmeTab.svelte` | MODIFY (~+3) | Reicht `createMode` und `context="route"` als `ohneZustellung` an die Abschnittsliste; im Hub und im Ortsvergleich unverändert |
| `frontend/src/lib/components/shared/infoboxKeys.ts` | MODIFY (nur falls nötig) | Eintrag der Infobox des Alt-Panels bleibt für das Alt-Panel (Ortsvergleich) bestehen |
| Tests (`node --test`) | CREATE/MODIFY | siehe Test Plan |
| `frontend/e2e/hub-anlegen-ablauf.spec.ts` | MODIFY | AN-6: Selektor `alert-channel-threshold-telegram-HIGH` wird zu `zustellung-kanal-telegram-dringlichkeit-HIGH` (Trip-Teil) |
| `frontend/e2e/trip-anlegen-zustellung-3332.spec.ts` | CREATE | Zustellung bedienen, ein POST mit Zeiten, Kanälen und Stille, Hub-Reiter Zustellung zeigt denselben Stand, zwei Nutzer |

### Nicht in dieser Spec

- Ortsvergleich-Anlegen (Alt-Panel bleibt dort bis D2, #3333), `send_email` im Orte-POST, Aktivierungs-Banner, Karte „Layout je Kanal“ (#3301).
- Rückbau von `WetterMetrikenVersandPanel`, `WeatherMetricsTab`, `VersandTab` (#3036, #3020, #3297); es wird keine Datei gelöscht.
- Entfernen des Reiters Alarme im Trip-Anlegen (erst nach Beleg des Besitzers von Metrik-Alarmstufen und amtlichen Warnungen im Wetter-Reiter, D2).
- Änderungen an Go-API, Python-Core oder Gate-Konfiguration.

### Ehrliche Scope-Grenze

Die Zielgrenze von ~250 LoC Produktion wird nach Schätzung eingehalten (ca. 150 bis 190 mit Helfer und Abschnittsliste). Bei der Umsetzung zeigt sich, ob der Eintrittstrip (`wetterAnlegeTrip`-Muster) mehr Code braucht; wird die Grenze überschritten, meldet der Developer das im PR-Text, statt still zu schneiden.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `zustellungNutzlast`, `standAusTrip`, `ZustellungStand` (`zustellungModell.ts`/`zustellungSpeicherung.ts`) | Frontend | Reine Funktionen: Stand und Delta gegen den Anlege-Startstand |
| `anlegeSpeicherer` (`wetterTabSpeicherung.ts`) | Frontend | Vorbild für den Rückkanal ohne Netz |
| `ergaenzeVersandStandard`, `ergaenzeStandardwerteReportConfig`, `buildCreateTripPayload`, `mitKarte` (`tripNewLogic.ts`) | Frontend | Standardwerte im POST und Muster Read-Modify-Write |
| `WasStehtWoKarte` (#3305) | Frontend | Besitzt `email_format`, `show_stage_stats`, `show_yesterday_comparison`, `show_night_block`, `telegram_style`, Stundenverlauf; bleibt dort |
| `GET /api/auth/profile` | API | Kanalstatus und Telegram-Verbindung je Nutzer (ein Abruf) |
| `feat_2795_s3b_teil1_zustellung` | Spec | Reiter Zustellung im Hub (AC-8 Raster, AC-27, AC-32 nur Geändertes, AC-33 ein Speicherer, AC-36 Profil einmal) |
| `feat_3305_tabelle_trip_anlegen`, `feat_3122_was_steht_wo` | Spec | Karte im Anlegen, Nr. 14 „Jede Einstellung genau einmal“ |
| ADR-0095, ADR-0097, ADR-0124 | ADR | Kanal-Parität, Code-Teilung Trip/Vergleich, eine Tabelle |

## Implementation Details

**Anlege-Modus im Reiter.** `ZustellungTab` bekommt `createMode`, `zustellungStart` und `onAnlegeStand`. Der Startstand ist `zustellungStart ?? KONTEXT[context].stand()` (einmal gelesen mit `untrack`). Im Anlegen ist `speicherung` der Anlege-Speicherer: jede Änderung meldet `{stand, nutzlast}` nach oben, ohne PUT, ohne `saveController`, ohne Autosave. Die Meldung ändert nie die Eingangs-Prop (Schleifenschutz, wie bei der Karte).

**Editor hält den Stand.** `TripNewEditor` hält `zustellungStand` als `$state` und gibt ihn beim Neuaufbau als `zustellungStart` zurück (Wechsel Desktop und Mobil, Vor und Zurück der Schritte). Der Eintrittstrip für den Reiter wird aus `stubTrip` und den heutigen Alarm-Startwerten abgeleitet, sodass `standAusTrip` exakt die heutigen Anlege-Standardwerte liefert (Morgen an, Abend nach `reportSlotAktiv`, E-Mail an, Alarm-Kanäle E-Mail und Telegram an). Ein Inhaltsgleichheits-Guard verhindert Update-Schleifen (Muster `handleDayWindowChange`).

**Ein POST, Read-Modify-Write.** `mitZustellung` mischt den Stand erst beim POST in den vorhandenen Rumpf: `report_config.morning_enabled/evening_enabled/enabled`, `morning_time/evening_time` (HH:MM:SS), `send_email/telegram/sms/premium_sms`; Alarm-Kanäle, Dringlichkeit, Stille Stunden und Cooldown in die Alarm-Felder (`alert_channels`, `alert_channel_thresholds`, `alert_quiet_from/_to`, `alert_cooldown_minutes`). `ergaenzeVersandStandard` bleibt im POST (u. a. `multi_day_trend_reports`). Wer den Reiter nie bedient, sendet einen Körper, der dem heutigen bitgleich ist; es gibt keinen stillen Wechsel der Startwerte. Eine rasterfremde Uhrzeit wird nie gesendet, die letzte gültige bleibt (Server verlangt Viertelstunden-Raster).

**Nie beide Schreiber.** Im Schritt Zustellung entfällt das Alt-Panel mit `bind:reportConfig`; der Reiter ist der einzige Schreiber der Versand-Felder. `handleChannelsChange` entfällt; `display_config.channels` bleibt beim Editor-Standard `{email: true, telegram: true, sms: false}`, wie ihn das Alt-Panel bisher zurückmeldete (kein Bedienelement im Zustellungsschritt änderte es).

**Alarm-Doppelung (Entscheidung D1).** Im Trip-Anlegen blendet der Reiter Alarme die Abschnitte `channels`, `cooldown` und `quiet-hours` aus, weil der Reiter Zustellung sie besitzt. `official-warnings`, `metric-levels` und `sample` bleiben dort bis D2. Die Abschnittsliste ist datengetrieben (`alarmeTabSections`), der Hub-Reiter hat sie nicht.

**MailInhaltCard.** Entfällt im Trip-Anlegen (Hub-Parität; der Hub hat keine MailInhaltCard). Besitzer der Felder: `email_format`, `show_stage_stats`, `show_yesterday_comparison`, `show_night_block` liegen in der Karte „Was steht wo“ (#3305, bleibt). `show_stability` (Großwetterlage) und die Bestandsfelder ohne Bedienstelle behalten ihren Standardwert aus `ergaenzeStandardwerteReportConfig`; das ist beim Neuanlegen kein Datenverlust, nur der Wegfall eines Schalters, den der Hub ebenfalls nicht anbietet. Dieser Wegfall wird hier ausdrücklich aufgeführt (Known Limitations).

**Infobox (Tech-Entscheidung, Hub-Parität).** Der Reiter bekommt keine Infobox (`showInfobox` nur beim Anlegen entfällt für Zustellung im Trip-Anlegen). Das Hilfswissen steht in den Bereichstexten des Reiters selbst. Der Test `infobox_nur_beim_anlegen` wird angepasst: Das Alt-Panel (Ortsvergleich, bis D2) und `AlarmeTab` zeigen die Infobox weiter nur beim Anlegen; der Reiter Zustellung zeigt nie eine. Begründung: Anlegen = Bearbeiten, ein zusätzliches nur-Anlegen-Element im geteilten Reiter würde die Parität brechen.

## Expected Behavior

- **Input:** Nutzer legt einen Trip an, stellt im Schritt Zustellung Zeiten (z. B. Morgen 06:45), Kanäle, Dringlichkeit Telegram HIGH und Stille Stunden ein und legt an.
- **Output:** Genau ein `POST` auf die Trip-Anlage mit diesen Werten in `report_config` und den Alarm-Feldern; der Hub-Reiter Zustellung des neuen Trips zeigt denselben Stand.
- **Side effects:** Nur der lesende Profil-Abruf; kein PUT, kein Speichern vor dem Anlegen.

## Acceptance Criteria

- **AC-1:** Given ein angemeldeter Nutzer legt einen Trip an / When er den Schritt Zustellung öffnet, in der Mobil- und in der Desktop-Ansicht / Then sieht er den Reiter Zustellung mit Briefing-Zeiten, Kanal-Tabelle und Stille Stunden wie im Hub, und das Alt-Panel mit Versand-Abschnitt und die Mail-Inhalt-Karte erscheinen dort nicht mehr.
  - Test: E2E in beiden Ansichten: `zustellung-tab` sichtbar, Alt-Panel-Testids (`channel-email` u. a.) und Mail-Inhalt-Karte abwesend; SSR-Test des Editors mountet `ZustellungTab` und kein `WetterMetrikenVersandPanel`.

- **AC-2:** Given der Nutzer stellt im Anlegen Briefing-Zeiten, Kanäle und Stille Stunden ein / When er den Trip anlegt / Then enthält der eine POST `report_config.morning_time`/`evening_time` (HH:MM:SS), `morning_enabled`/`evening_enabled`, `send_email/telegram/sms/premium_sms` und `alert_quiet_from/_to` mit genau den eingestellten Werten.
  - Test: E2E zeichnet den POST-Körper auf und vergleicht; Unit-Test `mitZustellung` mit gesetztem Stand.

- **AC-3:** Given der Nutzer wählt Alarm-Kanäle, die Dringlichkeit HIGH für Telegram und einen Cooldown / When er den Trip anlegt / Then stehen `alert_channels`, `alert_channel_thresholds.telegram == "HIGH"` und `alert_cooldown_minutes` im POST.
  - Test: E2E (AN-6 mit neuem Selektor `zustellung-kanal-telegram-dringlichkeit-HIGH`) prüft den POST; Unit-Test `mitZustellung`.

- **AC-4:** Given der Nutzer öffnet den Schritt Zustellung, bedient den Reiter aber nicht / When er den Trip anlegt / Then ist der POST-Körper in `report_config`, den Alarm-Feldern und `display_config.channels` bitgleich zu dem heutigen Körper (keine stille Änderung der Startwerte, `multi_day_trend_reports` und die Standardwerte aus `ergaenzeVersandStandard` weiter vorhanden).
  - Test: Unit-Test vergleicht den Körper mit Referenz-Fixture ohne Reiter-Bedienung (Regressionsschutz); E2E prüft dieselben Felder.

- **AC-5:** Given der Nutzer ändert Werte im Reiter / When er bis zum Anlegen weitermacht / Then gibt es weder einen PUT noch einen Autosave noch einen Schreibaufruf vor dem Anlegen, und beim Anlegen genau einen POST.
  - Test: E2E zählt Netzwerkaufrufe: null PUT, null Schreibaufrufe vor dem Anlegen, genau ein POST; `anlegen_ohne_autosave` bleibt grün.

- **AC-6:** Given der Nutzer hat im Reiter Zustellung Werte gesetzt / When er zwischen Mobil und Desktop wechselt oder Schritte vor und zurück geht / Then bleibt der Stand erhalten und die Werte stehen unverändert im POST.
  - Test: E2E: Wert setzen, Ansicht und Schritte wechseln, Wert prüfen; Unit-Test: Neuaufbau mit `zustellungStart` ergibt denselben Stand.

- **AC-7:** Given der Nutzer gibt eine rasterfremde Uhrzeit ein (z. B. 06:50) / When er den Trip anlegt / Then sendet der POST die letzte gültige Viertelstunden-Zeit und es gibt keinen Server-Fehler 400.
  - Test: Unit-Test `mitZustellung` mit ungültiger Zeit (kein Wert im POST geändert); E2E mit 06:50 legt erfolgreich an.

- **AC-8:** Given ein Trip wird im Anlegen mit gesetzter Zustellung angelegt / When der Nutzer danach den Hub-Reiter Zustellung dieses Trips öffnet / Then zeigt er dieselben Zeiten, Kanäle, Dringlichkeiten, Stille Stunden und denselben Cooldown wie beim Anlegen eingestellt.
  - Test: E2E-Rückweg: nach dem Anlegen Hub-Reiter öffnen und jeden eingestellten Wert vergleichen.

- **AC-9:** Given der Nutzer ist im Schritt Alarme des Trip-Anlegens / When er den Reiter öffnet / Then fehlen dort die Abschnitte Alarm-Kanäle, Cooldown und Stille Stunden (sie stehen im Reiter Zustellung), während amtliche Warnungen und Metrik-Alarmstufen dort bleiben; jedes Feld hat genau eine Bedienstelle, und im Hub und im Ortsvergleich-Anlegen bleibt der Reiter Alarme unverändert.
  - Test: Unit-Test `alarmeTabSections` mit und ohne `ohneZustellung`; E2E prüft die Bedienstellen je Feld im Anlegen (genau eine) und die vollständige Liste im Ortsvergleich-Anlegen.

- **AC-10:** Given ein Nutzer legt einen Trip an / When er im Schritt Zustellung die Mail-Inhalt-Felder sucht / Then sind E-Mail-Format, Etappen-Statistik, Vortagesvergleich und Nacht-Block weiter über die Karte „Was steht wo“ bedienbar, ihre Werte stehen wie bisher im POST, und `show_stability` sowie Bestandsfelder behalten ihren Standardwert.
  - Test: Unit-Test: POST ohne und mit Karten-Änderung (`email_format` wirkt), `show_stability` gleich Standard; Bestandstest `trip_new_mail_inhalt_karte_genau_eine_instanz` an die Hub-Parität angepasst.

- **AC-11:** Given der Reiter Zustellung im Trip-Anlegen / When der Nutzer ihn öffnet / Then erscheint dort keine Infobox mehr, während sie im Alt-Panel des Ortsvergleich-Anlegens und im Reiter Alarme des Trip-Anlegens wie bisher nur beim Anlegen erscheint.
  - Test: Angepasster Test `infobox_nur_beim_anlegen`: Reiter Zustellung ohne Infobox, übrige Mounts unverändert, Hub ohne Infobox.

- **AC-12:** Given zwei verschiedene Nutzer A und B mit verschiedenem Kanalstatus (A hat Telegram verbunden, B nicht) / When beide je einen Trip anlegen / Then zeigt der Reiter bei A die Dringlichkeit für Telegram und bei B nicht, jeder Trip erscheint nur beim jeweiligen Nutzer, und B sieht den Trip von A nicht.
  - Test: E2E mit zwei Prüfkonten (`trip-anlegen-zustellung-3332.spec.ts`): Profil-Status je Nutzer, Anlage je Nutzer, gegenseitige Listen.

- **AC-13:** Given der Ortsvergleich wird angelegt / When der Nutzer den Schritt Zustellung öffnet / Then verhält er sich unverändert wie vor dieser Änderung (Alt-Panel, ein POST), D1 ändert dort nichts.
  - Test: Bestandstests `compare_new_editor_postet_einmal` und `feat3276_vergleich_ohne_altfelder` bleiben grün; Wächter-Test: Orte-Editor mountet weiter `WetterMetrikenVersandPanel`.

## Definition of Done

- AC-1 bis AC-13 durch Kern-Tests (`node --test`, ohne Mock-Theater) und E2E grün; Datenverlust (AC-2, AC-3, AC-4) und Doppelbedienung (AC-9) zuerst rot nachgewiesen.
- Bestehende Bestände grün oder angepasst: `compare_new_editor_postet_einmal`, `feat3276_vergleich_ohne_altfelder`, `anlegen_ohne_autosave`, `infobox_nur_beim_anlegen` (angepasst), Alt-Tests des Trip-Anlegens mit Panel-Annahme (`trip_new_editor_weather_metrics_wiring`, `trip_new_versandkanaele_unabhaengig_von_metriken`, `trip_anlegen_karte_verdrahtung_3305`) auf den neuen Aufbau umgestellt; Ratsche `context_herkunft_zweige_eingefroren` und Wächterliste (`bausteine_waechter_regeln.ts`) ohne neue Verstöße.
- Staging: Trip mit Prüfkonto angelegt, Zeiten, Kanäle, Dringlichkeit und Stille gesetzt, genau ein POST, Hub-Reiter Zustellung zeigt denselben Stand; zweiter Nutzer sieht nichts (AC-8, AC-12).
- Live auf Produktion, Selftest Exit 0. Keine Änderung an Gate-Konfiguration.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN Startstand und geänderter Stand WHEN Anlege-Speicherer meldet THEN `{stand, nutzlast}` kommt zurück, Nutzlast nur Geändertes, kein Netz (AC-2, AC-3)
- [ ] Test 2: GIVEN Stand mit Zeiten, Kanälen, Stille, Cooldown WHEN `mitZustellung` THEN `report_config` und Alarm-Felder wie erwartet, bestehende Felder erhalten (AC-2, AC-3)
- [ ] Test 3: GIVEN Reiter nicht bedient WHEN Rumpf gebaut THEN bitgleich zu Referenz-Fixture heute (AC-4)
- [ ] Test 4: GIVEN rasterfremde Zeit WHEN `mitZustellung` THEN letzte gültige Zeit (AC-7)
- [ ] Test 5: GIVEN `alarmeTabSections` mit `ohneZustellung` THEN `channels`, `cooldown`, `quiet-hours` fehlen, Rest unverändert, Hub unverändert (AC-9)
- [ ] Test 6: GIVEN Editor SSR WHEN Schritt Zustellung THEN `ZustellungTab` gemountet, `WetterMetrikenVersandPanel` und `MailInhaltCard` nicht; Orte-Editor mountet Alt-Panel weiter (AC-1, AC-13)
- [ ] Test 7: GIVEN Neuaufbau mit `zustellungStart` THEN gleicher Stand (AC-6)
- [ ] Test 8: GIVEN Infobox-Test angepasst THEN Reiter Zustellung ohne Infobox (AC-11)
- [ ] Test 9: E2E AN-6 mit Selektor `zustellung-kanal-telegram-dringlichkeit-HIGH` (AC-3)
- [ ] Test 10: E2E `trip-anlegen-zustellung-3332.spec.ts`: Zeiten, Kanäle, Stille, ein POST, kein PUT, Hub zeigt denselben Stand (AC-2, AC-5, AC-8)
- [ ] Test 11: E2E beide Ansichten, Stand überlebt Wechsel (AC-1, AC-6)
- [ ] Test 12: E2E zwei Nutzer (AC-12)

Test-Politik: kein Mock-Theater; Kern-Tests deterministisch ohne Netz (`node --test`, kein Vitest, pytest nur mit benannten Dateien, falls überhaupt), Live-Nachweis im E2E gegen Staging. Dateiinhalt-Checks sind kein Verhaltensnachweis.

## Known Limitations

- Mit dem Reiter Zustellung entfallen im Trip-Anlegen auch die ⓘ-Erklärungen zu „Dringlichkeits-Schwelle“ und „Cooldown“ (Hub-Parität: der Reiter Zustellung hat Bereichstexte, keine ⓘ). Im Ortsvergleich-Anlegen bleiben sie bis D2 (#3333).
- Ortsvergleich-Anlegen nutzt bis D2 (#3333) weiter das Alt-Panel; die Karte „Layout je Kanal“ (#3301) bleibt dort bis dahin.
- Im Trip-Anlegen entfallen der Schalter Großwetterlage (`show_stability`) und weitere Bestandsfelder der Mail-Inhalt-Karte ohne Bedienstelle; sie behalten den Standardwert. Der Hub bietet sie ebenfalls nicht an (Anlegen = Bearbeiten, ADR-0124 Nr. 14). Kein Datenverlust, da Neuanlage.
- Der Reiter Alarme bleibt im Trip-Anlegen bis D2 mit Metrik-Alarmstufen und amtlichen Warnungen bestehen.
- Das Alt-Panel und seine Bausteine bleiben als Dateien bestehen (Rückbau #3036, #3020, #3297).
- Die Dringlichkeit je Kanal ist nur sichtbar, wenn Alarm für den Kanal an und der Kanal verbunden ist (Verhalten des Reiters, wie im Hub).
- Der Auftrag braucht keine Sperren-Aufhebung und keine Änderung der Gate-Konfiguration.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue (ADR-0095, ADR-0097, ADR-0124 gelten unverändert)
- **Rationale:** Umsetzung der PO-Vorgabe „Anlegen = Bearbeiten“ mit gemeinsamem Code für Trip und Ortsvergleich; ADR-0124 Nr. 14 verlangt jede Einstellung genau einmal. Die Entscheidung über Infobox, Mail-Inhalt-Karte und den Alarm-Abschnittsschnitt ist eine Tech-Entscheidung auf Basis der Hub-Parität und ändert keine frühere Entscheidung.

## Changelog

- 2026-11-24: Initial spec created (Teil D1 von #3307, Issue #3332, Epic #3122).
- 2026-11-24: Nachtrag (docs-updater, #3333 / Teil D2 von #3307): Die Known-Limitations-Punkte „bis D2 (#3333)“ (Ortsvergleich-Anlegen: Alt-Panel, Karte „Layout je Kanal“, ⓘ-Erklärungen, Reiter Alarme) sind mit D2 erledigt, soweit sie den Ortsvergleich betreffen. Der Reiter Alarme bleibt im Trip-Anlegen mit Metrik-Alarmstufen und amtlichen Warnungen bestehen (D2 entfernt ihn nicht).
