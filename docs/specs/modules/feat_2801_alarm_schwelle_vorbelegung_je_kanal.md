---
entity_id: feat_2801_alarm_schwelle_vorbelegung_je_kanal
type: feature
created: 2026-11-28
updated: 2026-11-28
status: draft
version: "1.0"
workflow: s9-2801-premium-sms-eigene-liste
tags: [alarm, schwelle, kanal, premium-sms, einstellungen-neu, epic-2791, adr-0046, adr-0124]
---

# #2801 Alarm-Dringlichkeit je Kanal: Vorbelegung E-Mail/Telegram gering, SMS mittel, Premium-SMS hoch

## Approval

- [ ] Approved

## Purpose

Wer keine Alarm-Dringlichkeit je Kanal gewählt hat, bekommt ab sofort kanalgerechte Startwerte: E-Mail und Telegram melden ab „gering“, die SMS ab „mittel“, die Premium-SMS (Satellit, kostet je Nachricht) nur bei „hoch“. Das gilt für alle Trips und Orts-Vergleiche ohne gesetzten Wert, neu wie Bestand. Die Premium-SMS bekommt im Briefing keine eigene Auswahl, sondern denselben Inhalt wie die SMS (PO-Entscheidung 2026-11-28, ersetzt Konzept N2 „eigene Liste“).

## Source

- **File:** `src/services/alert_channel_threshold.py` (Python-Quelle der Vorbelegung), `frontend/src/lib/components/shared/alarme-tab/alertChannelState.ts` (Frontend-Quelle)
- **Identifier:** `DEFAULT_CHANNEL_THRESHOLD` (heute ein Einzelwert `"LOW"`) wird zur Zuordnung je Kanal; `split_by_threshold`, `resolveAlertChannelThresholds`

## PO-Entscheidungen (bindend, 2026-11-28, AskUserQuestion)

1. Vorbelegung gilt für ALLE Trips und Orts-Vergleiche ohne gesetzten Wert (neu und Bestand): E-Mail LOW, Telegram LOW, SMS MODERATE, Premium-SMS HIGH. Gesetzte Werte bleiben unverändert, auch ein ausdrücklich gesetztes LOW. Rote Linie #638 bleibt (rohes Opt-in im Protokoll, Grund `below_channel_threshold`).
2. Keine eigene Premium-Auswahl. Premium-SMS-Briefing = SMS-Inhalt, von hinten auf 153 Zeichen gekürzt, amtliche Warnungen zuletzt (Verhalten unverändert, wird nur festgeschrieben). Keine Premium-Spalte in „Was steht wo“.

## Befund aus dem Code (Default-Stellen, per Grep geprüft)

Die Vorbelegung „nicht gesetzt = LOW“ steckt an genau diesen Stellen, alle werden auf EINE Quelle je Sprache umgestellt:

| Sprache | Stelle | Heute |
|---|---|---|
| Python | `src/services/alert_channel_threshold.py:17,30` (`split_by_threshold`) | `thresholds.get(channel) or "LOW"` |
| Python | `src/output/renderers/trip_report.py:460-465` (SMS-Briefing, niedrigste amtliche Stufe) | `_sms_threshold or "LOW"` |
| Python | `src/output/renderers/narrow.py:487-488` (Telegram-Briefing) | `_threshold or "LOW"` |
| Frontend | `shared/alarme-tab/alertChannelState.ts:127-145` (`resolveAlertChannelThresholds`) | Einzelwert `DEFAULT_CHANNEL_THRESHOLD = 'LOW'` |
| Frontend | `shared/zustellung-tab/zustellungModell.ts:233,334` | `: 'LOW'` bzw. `?? 'LOW'` |
| Frontend | `trip-new/tripNewLogic.ts:189` | `resolveAlertChannelThresholds(undefined)` (läuft über die Quelle) |
| Frontend | `compare/alarmePropsAus.ts:102-104,127` | `resolveAlertChannelThresholds(bestand)`, `wiz.channelThresholds ?? {}` |

Alle Alarm-Pfade (Trip-Wetter, amtlich, Radar; Orts-Vergleich-Wetter, amtlich, Radar) laufen über `split_by_threshold` (`trip_alert.py:2786,3154,3485`, `compare_alert.py:442`, `compare_official_alert.py:353`, `compare_radar_alert.py:409`) und haben keinen eigenen LOW-Fallback; sie erben die Umstellung. Go (`internal/model/trip.go`, `compare_preset.go`, Handler) setzt keinen Default (nil bleibt nil) und wird nicht geändert; Go-Tests sichern das nur ab. Gesetzt wird je Kanal einzeln: ein Wert für SMS lässt die anderen drei auf ihrer Vorbelegung.

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/alert_channel_threshold.py` | MODIFY | Einzelwert wird Zuordnung je Kanal (email/telegram LOW, sms MODERATE, premium_sms HIGH) plus Hilfsfunktion `default_threshold(channel)`; `split_by_threshold` nutzt sie |
| `src/output/renderers/trip_report.py` | MODIFY | :460-465 SMS-Schwelle aus der Quelle statt `"LOW"` |
| `src/output/renderers/narrow.py` | MODIFY | :487-488 Telegram-Schwelle aus der Quelle (bleibt LOW) |
| `frontend/src/lib/components/shared/alarme-tab/alertChannelState.ts` | MODIFY | Zuordnung je Kanal exportieren, `resolveAlertChannelThresholds` nutzt sie; ausdrücklich gesetzte Werte (auch LOW) bleiben |
| `frontend/src/lib/components/shared/zustellung-tab/zustellungModell.ts` | MODIFY | :233,:334 Fallback aus der Quelle statt `'LOW'` |
| `frontend/src/lib/components/shared/zustellung-tab/zustellungSpeicherung.ts` | PRÜFEN/MODIFY | Vergleich vorher/jetzt auf Basis derselben aufgelösten Werte (siehe „Speichern“) |
| `frontend/src/lib/components/trip-new/tripNewLogic.ts` | PRÜFEN | läuft über `resolveAlertChannelThresholds`; Test deckt Neuanlage ab |
| `frontend/src/lib/components/compare/alarmePropsAus.ts` | PRÜFEN | dito, geteilter Code (ADR-0097) |
| `frontend/src/lib/i18n/messages/{de,en}/zustellung.json` | MODIFY | Fußzeile Kanal-Tabelle (:60) ehrlich zur Vorbelegung |
| `frontend/src/lib/i18n/messages/{de,en}/wetter.json` | MODIFY | :150,:217-218 Hinweis Premium: DE „Die Premium-SMS bekommt denselben Inhalt wie die SMS.“, EN „The Premium SMS gets the same content as the SMS.“ |
| `frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte` | PRÜFEN | :324 nutzt den i18n-Schlüssel, keine eigene Logik |
| `docs/adr/0131-alarm-schwelle-vorbelegung-je-kanal.md` | CREATE | neues ADR (nächste freie Nummer, Vorgänger 0130) |
| `docs/adr/README.md` | MODIFY | Index (Drift-Test `tests/test_adr_index_drift.py`); ADR-0046 und ADR-0124 mit Vermerk |
| `docs/reference/premium_sms_format.md`, `sms_format.md` (Changelog), `api_contract.md` (falls Default dokumentiert) | MODIFY | Vorbelegung, Premium = SMS-Inhalt endgültig |
| `docs/context/einstellungen_neu.md` | MODIFY | N2 „eigene Liste“ abgelöst |
| `docs/specs/modules/feat_1461_s3b2a_kanal_schwelle.md` | MODIFY | Vermerk: AC-13 / PO 2026-08-05 aufgehoben durch ADR-0131 |
| `docs/specs/modules/feat_3122_was_steht_wo.md` (:92,:329), `feat_3057_kanal_liste_resolver.md` (AC-5) | MODIFY | „vorerst / eigene Auswahl später“ auf „endgültig derselbe Inhalt“ |
| i18n-Glossar | PRÜFEN | nur falls ein neuer Begriff entsteht (erwartet: keiner) |
| Tests | siehe Test Plan | umstellen und neu |

### Estimated Changes

- Files: ca. 22 (davon ca. 8 Code, 6 Doku/Spec, ca. 8 Tests)
- LoC: ca. +260/-60 (Code ca. 60, Tests ca. 160, Doku ca. 40)
- Effort: medium, Risiko mittel (Bestandsverhalten ändert sich bewusst)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services.alert_urgency` (`meets_or_exceeds`, `min_official_level_for_threshold`) | module | Rangvergleich und Abbildung Schwelle auf amtliche Stufe, unverändert |
| `alert_channel_threshold.split_by_threshold` | module | einziger Schwellenfilter aller sechs Alarm-Pfade |
| `notification_service` (Premium erhält `sms_body`) | module | Alarmtext Premium unverändert |
| `channel_list_resolver.py:163-170` | module | Premium fällt auf SMS-Liste, bleibt |
| ADR-0046, ADR-0095, ADR-0097, ADR-0101, ADR-0124 | ADR | Vorgaben und abzulösende Teile |
| Zustellung-Tab (`frontend/src/lib/components/organisms/zustellung-tab/KanalTabelle.svelte`, `zustellungModell.ts`, `zustellungSpeicherung.ts`) | Frontend | Anzeige und Speichern |

## Implementation Details

1. **Eine Quelle je Sprache.** Python: `alert_channel_threshold.py` hält die Zuordnung `{email: LOW, telegram: LOW, sms: MODERATE, premium_sms: HIGH}` und `default_threshold(channel)`. `split_by_threshold` löst je Kanal `thresholds.get(channel) or default_threshold(channel)`. `trip_report.py` und `narrow.py` rufen dieselbe Funktion, keine eigenen Literale. Frontend: `alertChannelState.ts` exportiert dieselbe Zuordnung; `resolveAlertChannelThresholds`, `zustellungModell.ts`, `tripNewLogic.ts`, `alarmePropsAus.ts` nutzen nur sie. Ein Paritäts-Test vergleicht beide Zuordnungen, damit sie nicht auseinanderlaufen.
2. **Gesetzt vs. nicht gesetzt.** Nur ein fehlender oder leerer Wert fällt auf die Vorbelegung. Ein vorhandenes `LOW`, `MODERATE` oder `HIGH` bleibt unverändert. Unbekannte Strings verhalten sich wie „nicht gesetzt“ (wie bisher).
3. **Kein Datenumbau.** Es werden keine Bestandsdaten migriert oder geschrieben; die Wirkung entsteht ausschließlich zur Laufzeit (ADR-0101: Bestand bleibt, kein Replace). Kein Eingriff in Schema-Dateien, der Pre-Snapshot-Hook ist nicht betroffen.
4. **Alarm-Wirkung** (Rang LOW < MODERATE < HIGH): Alarm „gering“ erreicht nur E-Mail und Telegram; „mittel“ zusätzlich SMS, nicht Premium-SMS; „hoch“ alle vier. Gilt für Wetter-, amtliche und Radar-Alarme in Trip und Orts-Vergleich. Unterdrückte Kanäle erscheinen im Protokoll weiter als rohes Opt-in mit Grund `below_channel_threshold` (#638).
5. **Premium-Briefing.** Unverändert: `trip_report.py:482-494` und `compare_briefing_aufbau.py:148-164` bauen den Premium-Text aus der SMS-Liste, auf 153 Zeichen (`channel_layout.py:57`) von hinten gekürzt, amtliche Warnungen zuletzt. Wird nur durch Tests festgeschrieben, keine Codeänderung erwartet.
6. **Anzeige Zustellung.** `KanalTabelle.svelte` zeigt bei nicht gesetztem Wert die Vorbelegung (E-Mail/Telegram „gering“, SMS „mittel“, Premium-SMS „hoch“). Die Fußzeile (`zustellung.json:60`, heute schon „SMS ab mittel, Premium-SMS nur bei hoch“) wird so umformuliert, dass sie für Nutzer ohne gesetzten Wert stimmt und sagt, dass eine eigene Wahl jederzeit gilt (DE und EN, Katalog, ADR-0104).
7. **Speichern.** `zustellungSpeicherung.ts:63-67` sendet bei jeder Änderung an irgendeinem Kanal alle vier Dringlichkeiten (`alleVier`), schreibt also die bis dahin nicht gesetzten Kanäle fest. Das ändert nichts Ungewolltes, solange die festgeschriebenen Werte exakt die angezeigten (aufgelösten) sind, also die neue Vorbelegung. Festgelegt: Vergleich und Schreibwert beruhen auf denselben aufgelösten Werten; eine Änderung an Alarm-Kanälen oder Zeiten ohne Dringlichkeitsänderung sendet `alert_channel_thresholds` nicht (heutiges Feldvergleichs-Verhalten bleibt, AC-32). Der Go-Merge (`internal/handler/trip.go:583-597`, Compare generisch) ist Read-Modify-Write und bleibt.

## Bekannte Folgen

1. **Amtliche Warnungen im SMS-Briefing.** Die SMS-Schwelle steuert nach ADR-0046 :64-77 auch die niedrigste amtliche Warnstufe im Kurznachrichten-Bericht (`trip_report.py:460-465` über `min_official_level_for_threshold`). Mit Vorbelegung MODERATE fallen im SMS-Briefing amtliche Warnungen der Stufe gering weg, und damit auch in der Premium-SMS (derselbe Text, gekürzt) für alle Trips ohne gesetzten Wert. Betroffen laut Code: Trip-SMS-Briefing und Trip-Premium-SMS-Briefing. Telegram nutzt die Telegram-Schwelle (`narrow.py:487`) und bleibt unverändert (LOW). E-Mail ist nicht betroffen. Orts-Vergleich-Briefing: im Code keine Verwendung der Schwelle in `compare_briefing_aufbau.py` gefunden, also nicht betroffen (der Umsetzer prüft das beim Bau und ergänzt einen Test, falls doch). Das ist die Folge der PO-Entscheidung und wird hier offengelegt, nicht abgemildert.
2. **Opt-in zuerst.** SMS und Premium-SMS sind bei Neuanlage aus (Opt-in, `alert_channel_new_default.md` AC-3). Die Vorbelegung wirkt erst, wenn der Nutzer den Kanal einschaltet. Bestandsnutzer, die SMS oder Premium schon eingeschaltet haben und nie eine Stufe gesetzt hatten, bekommen sofort weniger Alarme per SMS (erst ab „mittel“) bzw. Premium-SMS (erst ab „hoch“); E-Mail und Telegram bleiben vollständig, ein „gering“-Alarm geht also nie verloren (Kanal-Parität, ADR-0095).
3. **Aufgehobene Entscheidung.** PO-Entscheidung 2026-08-05 / `feat_1461_s3b2a` AC-13 / ADR-0046 Z.47 („Startwert LOW für alle“) und ADR-0095 Z.63 gelten für „nicht gesetzt“ nicht mehr; das ADR hält das fest.

## Test Plan

### Automated Tests (TDD RED, Kern-Schicht, ohne Mocks, ohne Netz)

Neue Dateien: `tests/tdd/test_2801_alarm_schwelle_vorbelegung.py` (Python), `frontend/src/lib/components/shared/alarme-tab/alertChannelVorbelegung.test.ts` (`node --test`), Go-Absicherung in `internal/handler/trip_alert_channel_thresholds_test.go` und `compare_preset_alert_channel_thresholds_test.go`. Echte Funktionen, echte Fixtures (Trip/Preset-Objekte), keine `Mock()`/`patch()`.

- [ ] T1 (rot zuerst): GIVEN Trip ohne `alert_channel_thresholds` WHEN `split_by_threshold` mit allen vier Kanälen für „mittel“ THEN erlaubt = email, telegram, sms; unterdrückt = premium_sms.
- [ ] T2: GIVEN dasselbe WHEN Dringlichkeit „hoch“ THEN alle vier erlaubt; bei „gering“ nur email, telegram.
- [ ] T3: GIVEN `{sms: "LOW"}` gesetzt, Rest leer WHEN „gering“ THEN SMS erlaubt, Premium unterdrückt (explizit LOW bleibt LOW, andere Kanäle behalten Vorbelegung).
- [ ] T4: GIVEN `{premium_sms: "LOW"}` WHEN „gering“ THEN Premium erlaubt. GIVEN `{email: "HIGH"}` WHEN „mittel“ THEN E-Mail unterdrückt.
- [ ] T5: Wetter-, amtlicher und Radar-Alarm für Trip (`trip_alert`) und Orts-Vergleich (`compare_alert`, `compare_official_alert`, `compare_radar_alert`) je mit echtem Preset ohne Wert, Dringlichkeit „mittel“: Zustellung an email/telegram/sms, nicht an premium_sms; Protokoll enthält premium_sms als rohes Opt-in mit Grund `below_channel_threshold`.
- [ ] T6: Briefing-Renderer: Trip ohne Wert, amtliche Warnung Stufe gering: SMS-Briefing und Premium-Briefing enthalten sie nicht; Trip mit SMS-Schwelle LOW: beide enthalten sie; Telegram-Briefing enthält sie ohne Wert weiterhin.
- [ ] T7: Premium-Briefing = SMS-Inhalt, auf 153 Zeichen von hinten gekürzt, amtliche Warnungen zuletzt, für Trip UND Orts-Vergleich (bestehende Tests bleiben gültig, ein Test je Seite ergänzt).
- [ ] T8: Zwei Nutzer A und B (verschiedene `user_id`): A hat `{sms: "LOW"}` gesetzt, B nichts; derselbe „gering“-Alarm erreicht bei A die SMS, bei B nicht; keine Vermischung, keine `"default"`-Nutzer-ID.
- [ ] T9 (Frontend): `resolveAlertChannelThresholds(undefined)` liefert email LOW, telegram LOW, sms MODERATE, premium_sms HIGH; mit `{sms:'LOW'}` bleibt SMS LOW; `tripNewLogic`-Anfangszustand und `alarmePropsAus` (Orts-Vergleich) liefern dieselben Werte (ein Code, `context`-Parität).
- [ ] T10 (Frontend): Zustellung-Modell zeigt bei nicht gesetztem Wert mittel/hoch; Speichern nach Änderung nur eines Kanals sendet die aufgelösten, angezeigten Werte (kein Wert springt); Speichern ohne Dringlichkeitsänderung sendet `alert_channel_thresholds` nicht.
- [ ] T11: Paritäts-Test: Python-Zuordnung und Frontend-Zuordnung sind gleich (einmal aus der Python-Quelle als JSON-Fixture, im Frontend-Test gelesen; gekennzeichnet `# doc-compliance-test` nur für diese Gleichheitsprüfung).
- [ ] T12: i18n: Hinweis Premium und Fußzeile existieren in DE und EN mit den neuen Texten; der alte Satz „eigene Auswahl kommt später“ ist in beiden Sprachen weg (`wetter_tab_i18n.test.ts`).
- [ ] T13 (Go): Handler setzt keinen Default; ein Trip/Preset ohne Feld kommt ohne Feld zurück; Merge überschreibt keinen anderen Kanalwert.

### Bestehende Tests, die umgestellt werden (Tests „Premium = SMS“ bleiben unverändert gültig)

- Umstellen, weil sie „ohne Schwelle erreicht alles / alle LOW“ festschreiben: `tests/tdd/test_alert_channel_threshold.py` (:645, :687), `test_compare_alert_channel_threshold.py` (:280, :316), `test_official_alert_channel_threshold.py`, ggf. Radar- und Premium-Alarm-Tests (`test_1701_*`, `fix_2275`-Tests), sofern sie ohne Schwelle Premium bei „gering“ erwarten; Frontend `alertChannelThresholds.test.ts` (:45, :50 „ohne Bestand alle vier LOW“), `zustellungModell.test.ts`, `zustellungSpeicherung.test.ts`, `rework_3020_defaults_gleich_auslieferung.test.ts`, tripNewLogic-Tests, `wetter_tab_i18n.test.ts` (:138-139).
- Unverändert gültig (sichern Entscheidung 2): `test_placements_aufloesung.py` (premium == sms), `test_3100_premium_sms_fallliste.py`, `test_3237_golden_vier_kanaele.py`, `test_3172_orte_premium_versandweg.py`, `test_compare_premium_sms_versand.py`, `test_3099_sms_resolver.py`, `test_3237_placements_aus_grundauswahl.py`; `was_steht_wo_karte*.test.ts` nur, soweit sie den Hinweistext prüfen.
- Go: `internal/handler/trip_alert_channel_thresholds_test.go`, `compare_preset_alert_channel_thresholds_test.go` bleiben grün (Go ändert sich nicht).

### E2E-Plan (Staging, nur in `/e2e-verify`, nach dem Push)

1. Prüfkonto auf Staging, Trip und Orts-Vergleich ohne gesetzte Stufen, SMS und Premium-SMS eingeschaltet: Zustellung-Tab zeigt gering/gering/mittel/hoch (Screenshot, DE und EN).
2. Alarm „mittel“ auslösen: E-Mail (Stalwart-Test-Postfach), Telegram und SMS kommen an, Premium-SMS nicht (Empfang über die zweite seven.io-Nummer; Premium-Prüfkonto Warnungen/Radar abschalten, #3181). Alarm „hoch“: alle vier. Für Trip und Orts-Vergleich.
3. Premium-SMS-Briefing: Text gleich SMS-Text, höchstens 153 Zeichen, über die zweite seven.io-Nummer empfangen, Trip und Orts-Vergleich.
4. Gesetzten Wert (SMS auf „gering“) speichern, Alarm „gering“: SMS kommt an; zweiter Nutzer ohne Wert: SMS kommt nicht an.

## Definition of Done

- [ ] Alle ACs (AC-1 bis AC-14) durch Kern-Tests (T1–T13) grün belegt, alle umgestellten Bestandstests grün.
- [ ] Vorbelegung je Kanal kommt in Python und im Frontend aus je einer Quelle; Paritäts-Test grün.
- [ ] ADR-0131 angelegt und im Index, Vermerke in ADR-0046/ADR-0124, Specs und Doku nachgeführt.
- [ ] Texte DE/EN im Katalog (Hinweis Premium-SMS, Fußzeile Zustellung).
- [ ] Adversary mit Mutations-Gegenprobe VERIFIED.
- [ ] E2E auf Staging bestanden (Anzeige, Alarm „mittel“/„hoch“ inkl. Premium-SMS-Empfang über die zweite seven.io-Nummer, Premium-Briefing ≤ 153 Zeichen, zwei Nutzer), Trip und Orts-Vergleich.
- [ ] Produktion ausgeliefert, Selbsttest Exit 0.

## Acceptance Criteria

- **AC-1:** Given ein Trip ohne gesetzte Alarm-Dringlichkeit je Kanal / When ein Alarm der Dringlichkeit „mittel“ ausgelöst wird / Then erreicht er E-Mail, Telegram und SMS, aber nicht die Premium-SMS.
  - Test: Trip ohne Schwellenwerte, Alarm mittel; Zustellprotokoll zeigt drei Kanäle zugestellt, Premium-SMS unterdrückt (T1, T5).

- **AC-2:** Given ein Trip ohne gesetzte Dringlichkeit / When ein Alarm der Dringlichkeit „hoch“ ausgelöst wird / Then erreicht er alle vier Kanäle, bei „gering“ nur E-Mail und Telegram.
  - Test: derselbe Trip, Alarm hoch bzw. gering; Zustellung je Kanal geprüft (T2).

- **AC-3:** Given ein Orts-Vergleich ohne gesetzte Dringlichkeit (Bestand oder neu angelegt) / When ein Wetter-, amtlicher oder Radar-Alarm „mittel“ ausgelöst wird / Then erreicht er E-Mail, Telegram und SMS, aber nicht die Premium-SMS, bei „hoch“ alle vier.
  - Test: je ein Alarm der drei Arten über `compare_alert`, `compare_official_alert`, `compare_radar_alert` (T5).

- **AC-4:** Given ein Trip oder Orts-Vergleich mit ausdrücklich gesetztem Wert, auch „gering“ für SMS oder Premium-SMS / When ein Alarm „gering“ ausgelöst wird / Then gilt der gesetzte Wert unverändert und nur nicht gesetzte Kanäle fallen auf ihre Vorbelegung.
  - Test: `{sms: LOW}` erreicht SMS bei „gering“, Premium nicht; `{premium_sms: LOW}` erreicht Premium; `{email: HIGH}` unterdrückt E-Mail bei „mittel“ (T3, T4).

- **AC-5:** Given ein Bestand-Trip oder -Orts-Vergleich, der vor dieser Änderung ohne Stufe gespeichert wurde / When er nach der Auslieferung einen Alarm „gering“ auslöst / Then gehen E-Mail und Telegram wie bisher, SMS und Premium-SMS sind (falls eingeschaltet) ab sofort unterdrückt und im Protokoll als rohes Opt-in mit Grund `below_channel_threshold` sichtbar.
  - Test: Fixture eines alten Trips und Presets ohne Feld; Alarm gering; Protokolleintrag mit Grund prüfen (T5).

- **AC-6:** Given ein neu angelegter Trip oder Orts-Vergleich / When der Nutzer SMS bzw. Premium-SMS später einschaltet, ohne eine Stufe zu wählen / Then gelten „mittel“ für SMS und „hoch“ für Premium-SMS, und beide Anlege-Wege (Trip, Orts-Vergleich) liefern dieselben Startwerte aus einem Code.
  - Test: Anfangszustand `tripNewLogic` und `alarmePropsAus` gleich, Werte gering/gering/mittel/hoch (T9).

- **AC-7:** Given die Zustellung-Tabelle eines Trips oder Orts-Vergleichs ohne gesetzten Wert / When der Nutzer sie öffnet / Then zeigt sie für E-Mail und Telegram „gering“, für SMS „mittel“ und für Premium-SMS „hoch“.
  - Test: Zustellung-Modell und Tabelle im Browser (E2E) (T10, E2E 1).

- **AC-8:** Given der Nutzer ändert in der Zustellung-Tabelle nur einen Kanal / When er speichert / Then werden nur die angezeigten Werte geschrieben, kein anderer Kanalwert springt, und ohne Änderung der Dringlichkeit wird `alert_channel_thresholds` gar nicht gesendet.
  - Test: Speicher-Payload vor und nach Änderung (T10, T13).

- **AC-9:** Given die Kanal-Tabelle in Zustellung und der Hinweis unter „Was steht wo“ / When die Oberfläche auf Deutsch oder Englisch steht / Then lautet der Hinweis „Die Premium-SMS bekommt denselben Inhalt wie die SMS.“ bzw. „The Premium SMS gets the same content as the SMS.“, die Fußzeile passt zur Vorbelegung, und „eigene Auswahl kommt später“ steht nirgends mehr.
  - Test: i18n-Test beider Sprachen und Sichtprüfung auf Staging (T12).

- **AC-10:** Given ein Trip oder Orts-Vergleich mit eingeschalteter Premium-SMS / When das Briefing versendet wird / Then ist der Premium-Text derselbe wie der SMS-Text, von hinten auf höchstens 153 Zeichen gekürzt, mit amtlichen Warnungen zuletzt, und es gibt keine eigene Premium-Spalte in „Was steht wo“.
  - Test: lange SMS-Liste Trip und Orts-Vergleich, Länge und Reihenfolge der Kürzung; Empfang über die zweite seven.io-Nummer (T7, E2E 3).

- **AC-11:** Given ein Trip ohne gesetzte SMS-Schwelle und eine amtliche Warnung der Stufe gering / When das SMS-Briefing und das Premium-Briefing gebaut werden / Then enthalten beide die Warnung nicht, mit gesetzter SMS-Schwelle „gering“ enthalten beide sie, und das Telegram-Briefing zeigt sie ohne Wert weiterhin.
  - Test: Renderer mit echter Warnung, drei Schwellenfälle (T6).

- **AC-12:** Given zwei verschiedene Nutzer, der erste mit gesetztem SMS-Wert „gering“, der zweite ohne / When für beide derselbe Alarm „gering“ ausgelöst wird / Then bekommt nur der erste die SMS, jeder Nutzer sieht ausschließlich seine eigenen Werte, nie ein Fallback auf `"default"`.
  - Test: zwei `user_id` mit getrennten Datenbäumen, Zustellung und Protokoll je Nutzer (T8, E2E 4).

- **AC-13:** Given die Vorbelegung existiert in Python und im Frontend / When beide Quellen verglichen werden / Then sind sie je Kanal identisch, und außerhalb dieser einen Quelle je Sprache steht kein eigener `"LOW"`-Fallback für Kanal-Schwellen mehr.
  - Test: Paritäts-Test gegen JSON-Fixture; Verhaltenstest, dass `trip_report.py`/`narrow.py` die Quelle nutzen (SMS ohne Wert MODERATE, Telegram ohne Wert LOW) (T6, T11).

- **AC-14:** Given das neue ADR 0131 und die Doku / When der ADR-Index-Test und die Doku-Prüfung laufen / Then ist ADR-0131 im Index, ADR-0046 und ADR-0124 tragen den Vermerk „teilweise abgelöst“, und `feat_1461_s3b2a` AC-13, `feat_3122`, `feat_3057` AC-5, `premium_sms_format.md`, `sms_format.md` und `einstellungen_neu.md` N2 nennen die neue Regel.
  - Test: `tests/test_adr_index_drift.py` grün (`# doc-compliance-test` nur für diesen Index-Test).

## Known Limitations

- Bestandsnutzer ohne gesetzte Stufe verlieren „gering“-Alarme per SMS und Premium-SMS (Opt-in-Kanäle); E-Mail und Telegram bleiben. Gewollt (PO 2026-11-28).
- Amtliche Warnungen der Stufe gering fehlen im SMS- und Premium-SMS-Briefing bei nicht gesetzter Schwelle (siehe „Bekannte Folgen“).
- Premium-Grenze ist 153 Zeichen, nicht 160 (`channel_layout.py:57`).
- Alarme haben keine Metrikliste; der Unterschied SMS/Premium bei Alarmen kommt allein über die Schwelle (ADR-0124 Nr. 11).
- Wer einen Kanalwert in der Zustellung ändert, schreibt danach alle vier Werte fest; spätere Änderungen der Vorbelegung erreichen diese Nutzer nicht mehr (gewollt, entspricht ADR-0101).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0131 (neu, `docs/adr/0131-alarm-schwelle-vorbelegung-je-kanal.md`)
- **Rationale:** Löst ADR-0046 teilweise ab (Startwert LOW für alle wird Vorbelegung je Kanal) und ADR-0095 Z.63; macht ADR-0124 Nr. 8 „vorerst“ endgültig (Premium-SMS = SMS-Inhalt); löst Konzept N2 „eigene Liste“ ab; hebt PO-Entscheidung 2026-08-05 / `feat_1461_s3b2a` AC-13 auf. Bewahrt rote Linie #638 und ADR-0101. Eine Entscheidung wird nie still rückgängig gemacht, daher neues ADR.

## Changelog

- 2026-11-28: Initial spec created (Issue #2801, Epic #2791 S9; PO-Entscheidungen 2026-11-28 eingearbeitet, Teil A „eigene Premium-Spalte“ entfällt)
