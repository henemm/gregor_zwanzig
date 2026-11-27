---
entity_id: feat_3441_test_alarm
type: feature
created: 2026-11-27
updated: 2026-11-27
status: draft
version: "1.0"
workflow: feat-3441-test-alarm
tags: [hub, alarm, versand, menue, kanaele, i18n, "#3441", "#2797", "#2791"]
---

# S5b: Test-Alarm im Menü „Test schicken ▾“

## Approval

- [ ] Approved

## Purpose

Im Menü „Test schicken ▾“ (gebaut in #3440) kommt nach dem Trenner unter „Alle eingerichteten Kanäle“ der Eintrag „Test-Alarm“. Er schickt einen Beispiel-Alarm mit echten Werten des Nutzers (echte Etappen bzw. Orte, echte Stundenreihe) an alle Alarm-Kanäle und ersetzt damit die Alarm-Vorschau als Prüfweg (PO-Entscheidung A14 in #2797). Der Nutzer sieht so vor dem Aufbruch, ob ein Alarm auf jedem Kanal wirklich ankommt, auch der Regen-Alarm (Hinweis #2800), weil dieselbe Kanalmenge gilt.

## Source

- **File:** `src/services/alert_test_service.py` (neu), `api/routers/briefings_test_alert.py` (neu), `internal/handler/briefing_test_alert.go` (neu), `frontend/src/lib/components/molecules/TestSchickenMenue.svelte` (Erweiterung)
- **Identifier:** `AlertTestService` (Beispiel-Änderungen, Kanalmenge, Versand), `POST /api/briefings/{id}/test-alert`, `BriefingTestAlertHandler`, Modell-Feld `erweiterungen` / Callback `onErweiterung`

## Estimated Scope

- **LoC:** Produktivcode ca. 400–480 (Backend ca. 300, Frontend ca. 150, ohne i18n/Doku/Tests); Tests ca. 450–650
- **Files:** ca. 20 (davon ca. 11 Produktiv, Rest Tests, i18n, Doku)
- **Effort:** high

**Scope-Override (Begründung):** Das Projektlimit `scope_guard.max_loc_delta: 250` wird überschritten. Der Workflow setzt `loc_limit_override 480` (Produktivcode) und `test_loc_limit_override 650` (Tests). Begründung: ein vertikaler Schnitt. Das Backend (Beispiel-Alarm bauen, Kanalmenge, Versand ohne Zustand) hat ohne den Menüeintrag keinen Nutzerwert und ist nicht E2E-abnehmbar; der Menüeintrag ohne Backend schickt nichts. Das Entfernen der Alarm-Vorschau-UI ist bewusst ausgelagert (Folge-Issue #3458), um Review-Fläche und Scope klein zu halten. Es sind keine Änderungen an der Gate-Konfiguration (`openspec.yaml`) und keine Schritte vorgesehen, die ein menschliches Override brauchen (Autark-Modus).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `feat_3440_test_schicken_menue` (TestSchickenMenue, `testSchickenModell.ts`, HubKopf) | spec/module | Menü mit Erweiterungs-Slot nach Trenner (AC-19 #3440), Rückmeldungs-Vokabular, `test-schicken-ok`/`-fehler`, `RUECKMELDUNG_MS` |
| `alert_channels.effective_alert_channels(subscription, settings, user_id)` | service | Die EINE Alarm-Kanal-Auflösung (Override `alert_channels`, sonst geerbte Briefing-Kanäle, Tarif-Gates); wird nie neu abgeleitet |
| `NotificationService.can_send_*` / `_dispatch_alert_message` | service | Zustellbarkeit je Kanal, Versand, `NotificationResult` (`sent_channels`, `failed_channels`, `blocked_channels`) |
| `NotificationService.send_deviation_alert` / `send_multi_location_deviation_alert` | service | Bestehender Alarm-Versand Trip bzw. Vergleich, erhält den Schalter `test=True` |
| `NotificationService._sms_gate_reserve` | service | SMS-/Premium-SMS-Tageskontingent, zählt unverändert mit (echte Kosten) |
| `alert_channel_texts` (`render_channel_texts`, `build_deviation_message`, `sms_suffix`-Muster) | module | Geteilter Renderer (ADR-0011); Präfix-Mechanik analog `sms_suffix` |
| `alert_preview_hours.trip_preview_series`, `preview_reference_date`, `compare_preview_point` | module | Echte Stundenreihe und Bezugstag wie die Vorschau (#1737) |
| `alertPreviewHelpers.ts` (Regel neu = Schwelle×1.2, alt = Schwelle×0.8) | module | Vorbild der Beispiel-Änderungen; Logik wird serverseitig nachgebaut |
| `api/routers/briefings_send.py`, Go `BriefingSendHandler`, `bremsen.Versand` | endpoint/handler | Muster für Router, Go-Handler, Mengenbremse; `user_id` aus Auth-Kontext |
| Kontingent `manueller_abruf` (`services.forecast_budget`, ADR-0117) | policy | Buchung je Klick |
| `send_outcomes.py` | module | Fehlervokabular, neu `keine_alarm_kanaele`, `vergleich_ohne_orte`, `trip_ohne_segmente` (DE/EN) |
| `docs/context/einstellungen_neu/elementliste.json` | doc | Abschnitt `test-menue`, Zeilen „Test-Alarm“ und Untertitel |
| `docs/reference/i18n_glossar.md` | doc | Begriffe Test-Alarm / Test alert |
| ADR-0011, 0092, 0095, 0097, 0104, 0109, 0112, 0117, 0118 | ADR | Renderer = Versand; Testmail nur an bestätigte Adresse; Kanal-Parität; Trip/Orte ein Code; DE/EN; Menü; Bausteine; Kontingent; Knopf-Stil |

## Implementation Details

**Backend-Vertrag.** `POST /api/briefings/{id}/test-alert?kind=route|vergleich`. Go-Handler nach Muster `BriefingSendHandler`: `kind` gegen die zwei Werte prüfen (sonst 400), Mengenbremse `bremsen.Versand`, `user_id` ausschließlich aus dem Auth-Kontext (kein Client-Wert, kein Fallback auf `"default"`), Weiterreichen an Python. Python-Router (`api/routers/briefings_test_alert.py`) nach Muster `briefings_send.py`: Eigentum prüfen (fremde oder unbekannte ID ⇒ 404), Kontingent `manueller_abruf` je Klick buchen, Fehler über `send_outcomes`. Antwort: `sent_channels` (Liste), `skipped_channels` und `failed_channels` je als Liste von `{channel, reason}` (Gründe: Kanal nicht bedienbar, SMS-/Premium-Tageskontingent erschöpft, Zustellung fehlgeschlagen).

**Beispiel-Alarm (neuer Baustein `src/services/alert_test_service.py`).**
- Trip: Beispiel-Änderungen aus den aktiven `alert_rules` des Trips; je Regel neu = Schwelle×1.2, alt = Schwelle×0.8 (bei Delta-Regeln alt = 0), wie `alertPreviewHelpers.ts`. Vergleich: aktive Alarm-Metriken des Ortsvergleichs mit ihrer Standardschwelle, gleiche Regel.
- Echte Segmente des Bezugstags (Trip) bzw. echte Orte (Vergleich); echte Stundenreihe des Nutzers über `alert_preview_hours` (Anker + frisch). Hat der Trip heute keine Etappe, gilt der Bezugstag `preview_reference_date`; eine fehlende `stage_number` (None) darf nicht abstürzen. Eine leere weather-Liste wird vor dem Rendern abgefangen.
- Randfälle: keine aktiven Metriken ⇒ Fallback-Beispielmetrik; fehlende Stundenreihe ⇒ Nachricht ohne Stundenzeilen, kein Fehler; Trip ohne Segmente ⇒ 422 `trip_ohne_segmente`; Vergleich ohne Orte ⇒ 422 `vergleich_ohne_orte`.

**Versand ohne Zustand.** Der Baustein ruft `send_deviation_alert` (Trip) bzw. `send_multi_location_deviation_alert` (Vergleich) mit neuem Schalter `test=True`, der bis `_dispatch_alert_message` durchgereicht wird. Diese Methoden sind zustandslos; Alarm-Zustand (`alert_state`), Anker, Sperrzeit, Tageslimit und Alarm-Protokoll schreiben nur `trip_alert.py`/`compare_alert.py` und werden vom Test-Alarm nie aufgerufen. Der Test-Alarm schreibt nichts davon.

**Kanalmenge.** `effective_alert_channels(...)` (inklusive Tarif-Gates) geschnitten mit der Zustellbarkeit (`can_send_*`). Ignoriert werden `radar_alert_enabled`, stille Stunden, Sperrzeit und Tageslimit (der Test prüft den Kanal, nicht die Alarm-Regeln). Kanäle, die zwar effektiv sind, aber nicht bedienbar, erscheinen in der Antwort als übersprungen mit Grund. Ist die Menge leer, antwortet der Endpunkt mit dem Fehlercode `keine_alarm_kanaele`, ohne etwas zu senden.

**[TEST]-Kennzeichnung.** Der Präfix `[TEST]` steht im Mail-Betreff, im Telegram-Text und im SMS-/Premium-SMS-Text (der Nutzer unterwegs darf den Test nicht für eine echte Warnung halten). Das SMS-Limit von 140 Zeichen gilt inklusive Präfix: der Präfix wird vorher vom Limit abgezogen (Muster `sms_suffix` in `render_channel_texts`). Mail-Header `X-GZ-Mail-Type: deviation-alert` bleibt erhalten. Die Nachricht wird in der Sprache des Nutzers (`language`) gerendert; Protokoll-Token (`sms_code`, `compact_label`, Kürzel) werden nie übersetzt.

**Kosten und Bremsen.** SMS- und Premium-SMS-Tageskontingent zählen unverändert mit (echte Kosten); ist es erschöpft, wird der Kanal als übersprungen gemeldet, die übrigen Kanäle gehen raus. Je Klick wird `manueller_abruf` gebucht; die Mengenbremse `bremsen.Versand` begrenzt Wiederholung. Ein eigener Sperrmechanismus mit 409 `already_running` ist nicht nötig: der Test-Alarm schreibt keinen gemeinsamen Zustand, der gegen Parallelität zu schützen wäre; Doppelklicks fängt das Frontend (Eintrag während der Anfrage gesperrt) und die Mengenbremse ab.

**Frontend.**
- Der Eintrag wird über den vorhandenen Erweiterungs-Mechanismus (`onErweiterung`, Modell-Feld `erweiterungen` in `TestSchickenMenue.svelte` / `testSchickenModell.ts`) nach dem Trenner unter „Alle eingerichteten Kanäle“ ergänzt; die Menüstruktur wird nicht umgebaut. `HubKopf.svelte` reicht `onErweiterung` durch. EIN Code für Trip und Orte (`context="route"|"vergleich"`), keine neue Compare-Komponente (Pendant-Sperre #1170).
- Texte: Titel „Test-Alarm“, Untertitel „Beispiel-Alarm mit echten Werten an alle Alarm-Kanäle“. Erfolg: „Test-Alarm geschickt: {Kanal} ✓ · … · {hh:mm}“, übersprungene und fehlgeschlagene Kanäle im Vokabular von #3440 („Telegram übersprungen ({Grund})“, „fehlgeschlagen“). Leere Kanalmenge: „Kein Alarm-Kanal eingerichtet, der Test-Alarm ging nirgends hin.“ im Fehlerton.
- Die Seiten `routes/trips/[id]/+page.svelte` und `routes/compare/[id]/+page.svelte` rufen den Endpunkt über `lib/api.ts`/`subscriptionExec.ts`; Rückmeldung über die bestehenden Meldungen `test-schicken-ok` bzw. `test-schicken-fehler`, 5 s (`RUECKMELDUNG_MS`), Desktop und ≤899 px gleich. Uhrzeit = Client-Uhr beim Eintreffen der Antwort.
- Alle Texte nur über den Katalog `test_schicken.*` (DE/EN), Glossar ergänzt. Elementliste `docs/context/einstellungen_neu/elementliste.json`: Zeilen „Test-Alarm“ (ordnung 12) und Untertitel (ordnung 13), Abschnitt `test-menue`, alle Kontexte, mit `i18n_key`, `text_en` und `luecke: false`.
- Archivierte oder im Entwurf stehende Abos: der Knopf „Test schicken ▾“ ist wie in #3440 gesperrt bzw. Setup-Modus; der Test-Alarm ist dort nicht erreichbar.

**Nicht im Umfang:** Entfernen der Alarm-Vorschau-UI (`AlertPreviewCard`, `BeispielAlarm` im Zustellungs-Reiter, AlarmeTab-Abschnitt `sample`, `api.ts` alarmVorschau) ⇒ Folge-Issue #3458. Die Backend-Endpunkte `alert-preview` bleiben (Testwerkzeug, `alarm_testeinspeisung.md`). Außerdem nicht: Kebab-Rückfragen (#3442), Entwurf aktivieren (#3443), eigener Abweichungs-Alarm-Mail-Validator, Änderung der Kanal-Auflösung oder der echten Alarmwege.

## Expected Behavior

- **Input:** Klick auf „Test schicken ▾“, dann auf „Test-Alarm“.
- **Output:** Je Alarm-Kanal des Nutzers eine Beispiel-Alarm-Nachricht mit `[TEST]`-Kennzeichnung und echten Werten; Rückmeldung 5 s mit Kanalergebnissen und Uhrzeit.
- **Side effects:** Echter Versand ausschließlich an die konfigurierten Empfänger dieses Nutzers; Buchung `manueller_abruf`; SMS-Tageskontingent zählt mit; kein Alarm-Zustand, kein Anker, keine Sperrzeit, kein Tageslimit, kein Alarm-Protokoll-Eintrag.

## Acceptance Criteria

- **AC-1:** Given der Trip-Hub oder der Orte-Hub eines aktiven Abos / When der Nutzer „Test schicken ▾“ öffnet / Then steht unter „Alle eingerichteten Kanäle“ nach einem Trenner der Eintrag „Test-Alarm“ mit dem Untertitel „Beispiel-Alarm mit echten Werten an alle Alarm-Kanäle“, in beiden Hubs aus demselben Baustein und auf Desktop wie auf ≤899 px.
  - Test: Playwright gegen Staging in beiden Hubs (Desktop und 390 px: Eintrag und Untertitel nach dem Trenner sichtbar) plus Unit `node --test` auf das Zeilenmodell (`erweiterungen` enthält den Eintrag für `context` route und vergleich, keine zweite Menü-Komponente).

- **AC-2:** Given ein Nutzer mit eingerichteten Alarm-Kanälen E-Mail und Telegram / When er „Test-Alarm“ wählt / Then kommt auf jedem dieser Kanäle ein Beispiel-Alarm mit echten Werten seines Trips bzw. Ortsvergleichs an, und sonst bei niemandem.
  - Test: Playwright gegen Staging mit Prüfkonto: echter Versand, Eingang im Stalwart-Test-Postfach (Betreff mit `[TEST]`, Header `X-GZ-Mail-Type: deviation-alert`, Anzahl 1) und Nachricht im Telegram-Testchat, je für Trip und Ortsvergleich; pytest am Endpunkt mit Transport-Fake an der Transportgrenze (genau die Alarm-Kanäle werden aufgerufen, kein weiterer).

- **AC-3:** Given ein Abo, bei dem `radar_alert_enabled=false` ist / When der Nutzer „Test-Alarm“ wählt / Then geht der Test trotzdem an die Alarm-Kanäle, weil der Test den Kanal prüft und nicht den Radar-Schalter, stille Stunden, Sperrzeit oder Tageslimit.
  - Test: pytest am Endpunkt (Abo mit `radar_alert_enabled=false`, Zeitpunkt in stillen Stunden, Tageslimit ausgeschöpft, Sperrzeit aktiv ⇒ trotzdem Versand, `sent_channels` gefüllt).

- **AC-4:** Given ein Abo, bei dem ein Kanal im Briefing ausgeschaltet ist, aber per Alarm-Kanal-Override für Alarme eingeschaltet (und umgekehrt) / When der Nutzer „Test-Alarm“ wählt / Then bestimmt allein `effective_alert_channels` die Kanalmenge, geschnitten mit der Zustellbarkeit; ein nur im Briefing eingeschalteter Kanal erhält keinen Test-Alarm, ein per Override eingeschalteter schon, und das Tarif-Gate für SMS/Premium-SMS bleibt wirksam.
  - Test: pytest am Endpunkt (Briefing-Kanal Telegram aus + Override Telegram an ⇒ Telegram erhält; Briefing-Kanal SMS an + Override ohne SMS ⇒ SMS erhält nicht; Tarif ohne SMS ⇒ SMS in `skipped_channels` mit Grund) für Trip und Vergleich.

- **AC-5:** Given ein Test-Alarm an E-Mail, Telegram und SMS bzw. Premium-SMS / When die Nachrichten gerendert werden / Then trägt jede mit `[TEST]` gekennzeichnet (Mail-Betreff, Telegram-Text, SMS-/Premium-SMS-Text), und der SMS-Text bleibt inklusive Präfix bei höchstens 140 Zeichen, ohne dass Protokoll-Token abgeschnitten werden.
  - Test: pytest auf den echten Renderer ohne Mock (Betreff beginnt mit `[TEST]`, Telegram-Text enthält `[TEST]`, SMS und Premium-SMS beginnen mit `[TEST]` und haben ≤140 Zeichen, auch bei langen Beispiel-Werten) plus Staging-E2E-Mail (Betreff mit `[TEST]`).

- **AC-6:** Given ein Nutzer mit Alarm-Zustand (Anker, Sperrzeit, Tageszähler, Alarm-Protokoll, `alert_state`) / When er den Test-Alarm auslöst, auch mehrfach / Then bleiben alle diese Zustände byte-gleich unverändert, und ein anschließender echter Alarm wird dadurch weder blockiert noch ausgelöst.
  - Test: pytest am Endpunkt mit echtem Dateibaum des Nutzers: Zustandsdateien vor und nach drei Test-Alarmen identisch; danach löst der echte Alarmweg mit denselben Eingaben unverändert aus (kein Cooldown durch den Test).

- **AC-7:** Given ein Nutzer ohne bedienbaren Alarm-Kanal / When er „Test-Alarm“ wählt / Then wird nichts gesendet, der Endpunkt antwortet mit dem Fehlercode `keine_alarm_kanaele`, und die Seite zeigt im Fehlerton „Kein Alarm-Kanal eingerichtet, der Test-Alarm ging nirgends hin.“ (DE bzw. EN-Pendant).
  - Test: pytest am Endpunkt (leere Menge ⇒ Fehlercode, kein Transportaufruf) plus Unit `node --test` auf die Rückmeldungsbildung plus Playwright gegen Staging mit Prüfkonto ohne Alarm-Kanal (`test-schicken-fehler` mit dem Text).

- **AC-8:** Given ein Test-Alarm, der auf mindestens einem Kanal ankommt / When die Antwort eintrifft / Then erscheint für 5 s „Test-Alarm geschickt: E-Mail ✓ · Telegram ✓ · {hh:mm}“, ein effektiver, aber nicht bedienbarer oder im Kontingent erschöpfter Kanal erscheint als „{Kanal} übersprungen ({Grund})“, ein Kanal mit Zustellfehler als „{Kanal} fehlgeschlagen“, in Trip und Orte gleich und auch bei ≤899 px.
  - Test: Unit `node --test` auf die Textbildung (gesendet / übersprungen mit Grund / fehlgeschlagen, Client-Uhr `hh:mm`) plus Playwright gegen Staging in beiden Hubs auf Desktop- und Mobil-Viewport (testid `test-schicken-ok`, Text, Verschwinden nach 5 s).

- **AC-9:** Given das Kontingent `manueller_abruf` ist erschöpft, die Mengenbremse spricht an, oder der Server antwortet mit einem Fehler / When der Nutzer „Test-Alarm“ wählt / Then wird nichts gesendet und die Seite zeigt rot (testid `test-schicken-fehler`) die bestehende Meldung aus `fehler.versand.*` (`kontingent_erschoepft`, Bremse, allgemeiner Serverfehler), in Trip und Orte gleich; jeder Klick bucht genau einmal `manueller_abruf`.
  - Test: pytest am Endpunkt (zwei Klicks ⇒ zwei Buchungen; erschöpftes Kontingent ⇒ Fehlertext, kein Versand) plus Go-Handler-Test (Bremse ⇒ 429 mit bestehendem Text, Python-Fehler wird durchgereicht) plus Unit `node --test` auf `sendOutcome`-Klassifikation.

- **AC-10:** Given die SMS- oder Premium-SMS-Tagesmenge des Nutzers ist ausgeschöpft / When er „Test-Alarm“ wählt / Then wird dieser Kanal als übersprungen gemeldet, die übrigen Kanäle gehen raus, und ein erfolgreich versandter Test-SMS-Alarm zählt wie ein echter gegen das Tageskontingent.
  - Test: pytest am Endpunkt mit Transport-Fake an der Grenze (Kontingentzähler vor/nach Versand +1; ausgeschöpftes Kontingent ⇒ Kanal in `skipped_channels`, E-Mail weiterhin in `sent_channels`); kein realer SMS-Versand (Kosten).

- **AC-11:** Given ein Trip mit aktiven Alarm-Regeln, echten Etappen und einer Stundenreihe / When der Test-Alarm gerendert wird / Then enthält die Nachricht je Regel eine Beispiel-Änderung (neu = Schwelle×1.2, alt = Schwelle×0.8, bei Delta alt = 0), die echten Etappen des Bezugstags und die Stundenzeilen aus der echten Stundenreihe; im Ortsvergleich gilt dasselbe für aktive Alarm-Metriken mit Standardschwelle und die echten Orte.
  - Test: pytest auf `alert_test_service` mit echten Trip-/Vergleichsdaten ohne Mock (Beispiel-Werte exakt aus Schwelle berechnet, Etappen- bzw. Ortsnamen und Stundenzeilen in der gerenderten Nachricht).

- **AC-12:** Given Randfälle des Beispiels / When der Nutzer „Test-Alarm“ wählt / Then gilt: Trip ohne heutige Etappe nutzt den Bezugstag ohne Absturz bei fehlender Etappennummer; keine aktiven Alarm-Metriken ergeben eine Fallback-Beispielmetrik; fehlende Stundenreihe ergibt eine Nachricht ohne Stundenzeilen und keinen Fehler; ein Trip ohne Segmente antwortet mit 422 `trip_ohne_segmente`; ein Ortsvergleich ohne Orte antwortet mit 422 `vergleich_ohne_orte`; eine leere weather-Liste wird abgefangen.
  - Test: pytest am Endpunkt je Randfall (Statuscode, Fehlercode, Nachrichtentext, kein Transportaufruf bei 422).

- **AC-13:** Given zwei verschiedene angemeldete Nutzer A und B mit je eigenem Trip, Ortsvergleich, Adresse und Chat / When B den Test-Alarm auslöst / Then gehen Nachricht und Ziel ausschließlich an B und A bleibt unberührt; die ID eines fremden Abos ergibt 404 ohne Versand, ein mitgesendeter `user_id`- oder Empfängerwert des Clients wird verworfen, und ohne Session antwortet der Endpunkt mit 401 statt auf einen Default-Nutzer zurückzufallen.
  - Test: pytest am Python-Endpunkt und Go-Handler-Test `internal/handler/briefing_test_alert_test.go` mit zwei Nutzern (Empfänger aus Profil von B, fremde ID ⇒ 404, ohne Session ⇒ 401, `kind` unbekannt ⇒ 400); Playwright gegen Staging: Test-Alarm von B erreicht nur die Ziele von B.

- **AC-14:** Given Sprache Deutsch oder Englisch am Nutzer / When Menüeintrag, Rückmeldungen und die Alarm-Nachricht erscheinen / Then stehen alle neuen Nutzertexte im Katalog `test_schicken.*` in DE und EN, die Nachricht ist in der Sprache des Nutzers gerendert, Protokoll-Token (Kanalnamen, `sms_code`, Kürzel) bleiben unübersetzt, und das Glossar enthält Test-Alarm / Test alert.
  - Test: Unit `node --test` i18n-Wächter (`keine_hartkodierten_nutzertexte`, Katalog-Parität DE/EN) plus pytest (Nutzer mit `language=en` erhält englischen Betreff/Text mit unverändertem `sms_code`).

- **AC-15:** Given die Elementliste mit dem Abschnitt `test-menue` / When der Abgleich läuft / Then sind die Zeilen „Test-Alarm“ und der Untertitel in allen Kontexten mit `i18n_key`, `text_en` und `luecke: false` eingetragen, und der Elementlisten-Abgleich findet beide Texte in DE und EN ohne Lücke.
  - Test: Unit `node --test` auf die echte `elementliste.json` (Zeilen vorhanden, `luecke` false, Schlüssel im Katalog) plus Playwright-Abgleich `elementliste-abgleich.staging.spec.ts` gegen Staging in DE und EN.

- **AC-16:** Given ein archiviertes oder im Entwurf stehendes Abo / When der Hub angezeigt wird / Then ist „Test schicken ▾“ wie in #3440 gesperrt bzw. Setup-Modus, das Menü und damit der Test-Alarm sind nicht erreichbar.
  - Test: Playwright gegen Staging (Knopf disabled bei archiviert, im Entwurf kein Menü) plus die bestehenden Unit-Tests `trip_hub_aktionen_verhalten.test.ts` / `compare_hub_aktionen_verhalten.test.ts`.

- **AC-17:** Given der Test-Alarm läuft / When der Nutzer während der Anfrage erneut auf den Eintrag klickt / Then wird kein zweiter Versand ausgelöst (Eintrag gesperrt bis zur Antwort), und die Bestandsfunktionen des Menüs (Kanalzeilen, „Alle eingerichteten Kanäle“) funktionieren unverändert.
  - Test: Unit `node --test` auf Zustand „läuft“ (Eintrag disabled) plus Playwright gegen Staging (Doppelklick ⇒ genau eine Mail im Stalwart-Postfach; Einzelkanal-Test aus #3440 weiterhin grün).

## Definition of Done

- [ ] Eintrag „Test-Alarm“ in beiden Hubs nach dem Trenner, Desktop und mobil (AC-1, AC-16, AC-17)
- [ ] Endpunkt `test-alert` (Go + Python), Kanalmenge über `effective_alert_channels`, [TEST]-Kennzeichnung, kein Zustand geschrieben (AC-2 bis AC-6)
- [ ] Leere Kanalmenge, Rückmeldungen, Fehlerfälle, SMS-Kontingent (AC-7 bis AC-10)
- [ ] Beispiel mit echten Werten und alle Randfälle (AC-11, AC-12)
- [ ] Zwei-Nutzer-Test Python und Go, 404/401/400 (AC-13)
- [ ] DE/EN über Katalog, Glossar, Elementliste ohne Lücke (AC-14, AC-15)
- [ ] Adversary-Verdict VERIFIED mit Mutations-Gegenprobe; alle 6 CI-Checks grün; Staging-E2E (E-Mail Stalwart + Telegram) grün; ausgeliefert, Selftest grün; Folge-Issue #3458 verlinkt

## Test Plan

### Automated Tests (TDD RED)

- [ ] pytest `tests/tdd/test_briefings_test_alert_endpoint.py` (neu): Kanalmenge (Override, Briefing-Kanal, Tarif-Gate, `radar_alert_enabled=false`, stille Stunden), `[TEST]` und SMS-Länge am echten Renderer, Zustand unverändert, leere Menge, Kontingent, SMS-Tageskontingent, Randfälle, Zwei-Nutzer-Test, Sprache. Transport-Fake nur an der Transportgrenze (AC-2 bis AC-6, AC-7, AC-9 bis AC-14)
- [ ] pytest `tests/tdd/test_alert_test_service.py` (neu): Beispiel-Änderungen, echte Segmente und Stundenreihe, Fallbacks (AC-11, AC-12)
- [ ] Go `internal/handler/briefing_test_alert_test.go` (neu): `kind`-Whitelist, `user_id` aus Auth-Kontext, Zwei-Nutzer, 401/404, Bremse (AC-9, AC-13)
- [ ] Unit `node --test` `testSchickenModell` und Rückmeldungstexte: Erweiterungs-Eintrag, gesendet/übersprungen/fehlgeschlagen, leer, Zustand „läuft“ (AC-1, AC-7, AC-8, AC-17)
- [ ] Unit `node --test` Katalog-Parität, Wächter `keine_hartkodierten_nutzertexte`, Elementliste (AC-14, AC-15)
- [ ] Playwright gegen Staging `hub-test-alarm.staging.spec.ts` (neu): beide Hubs, Desktop und 390 px, echter Versand E-Mail (Stalwart, `[TEST]`, `X-GZ-Mail-Type`) und Telegram (Testchat), leerer Kanalfall, Zwei-Nutzer, Doppelklick; SMS und Premium-SMS nur Endpunkt-Test mit Transport-Fake (Kosten) (AC-1, AC-2, AC-7, AC-8, AC-13, AC-16, AC-17)
- [ ] Umgestellt statt gelöscht: Bestandstests des Menüs `molecules/__tests__/test_schicken_*.test.ts`, `hub-kopf/__tests__/hub_kopf_*.test.ts` (neuer durchgereichter Callback), `elementliste-abgleich.staging.spec.ts`

## Scope (Affected Files)

| File | Change Type | LoC (ca.) | Description |
|------|-------------|-----------|-------------|
| `src/services/alert_test_service.py` | CREATE | +150 | Beispiel-Änderungen, Segmente/Stundenreihe, Kanalmenge, Versand |
| `src/services/notification_service.py` | MODIFY | +50 | Schalter `test=True` bis `_dispatch_alert_message`, [TEST]-Präfix, SMS-Limit |
| `src/services/alert_channel_texts.py` | MODIFY | +15 | Präfix-Mechanik analog `sms_suffix` |
| `src/services/send_outcomes.py` | MODIFY | +15 | `keine_alarm_kanaele`, `vergleich_ohne_orte`, `trip_ohne_segmente` (DE/EN) |
| `api/routers/briefings_test_alert.py` | CREATE | +50 | Router `POST /api/briefings/{id}/test-alert`, Kontingent, Fehler, Antwort |
| `api/main.py` (Router-Einbindung) | MODIFY | +2 | Router registrieren |
| `internal/handler/briefing_test_alert.go` | CREATE | +60 | Handler nach Muster `BriefingSendHandler`, `bremsen.Versand`, Auth-`user_id` |
| `internal/router/router.go` | MODIFY | +4 | Route registrieren |
| `frontend/src/lib/components/molecules/TestSchickenMenue.svelte` | MODIFY | +25 | Eintrag über `onErweiterung`, Zustand „läuft“ |
| `frontend/src/lib/components/molecules/testSchickenModell.ts` | MODIFY | +40 | Erweiterung `test-alarm`, Rückmeldungstexte |
| `frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte` | MODIFY | +8 | `onErweiterung` durchreichen |
| `frontend/src/routes/trips/[id]/+page.svelte` | MODIFY | +15 | Handler ruft Endpunkt, Rückmeldung |
| `frontend/src/routes/compare/[id]/+page.svelte` | MODIFY | +15 | wie Trip |
| `frontend/src/lib/components/shared/subscriptionExec.ts`, `frontend/src/lib/api.ts` | MODIFY | +15 | Aufruf `test-alert` |
| `frontend/messages/{de,en}/test_schicken.json` | MODIFY | +15 | Neue Schlüssel DE und EN |
| `docs/reference/i18n_glossar.md` | MODIFY | +4 | Test-Alarm / Test alert |
| `docs/context/einstellungen_neu/elementliste.json` | MODIFY | +30 | Zeilen ordnung 12/13 `test-menue` mit `i18n_key`, `text_en`, `luecke false` |
| Tests (Liste im Test Plan) | CREATE/MODIFY | +450–650 | Neue und umgestellte Tests, neu `frontend/e2e/hub-test-alarm.staging.spec.ts` |

## Known Limitations

- Auf Staging wird der echte Versand nur für E-Mail und Telegram geprüft; SMS und Premium-SMS (Kosten seven.io) nur im Endpunkt-Test mit Transport-Fake an der Grenze.
- Ein eigener Abweichungs-Alarm-Mail-Validator existiert nicht (nur `briefing_mail_validator.py` kennt `deviation-alert`); die E2E-Prüfung deckt Eingang, `[TEST]`-Betreff und `X-GZ-Mail-Type` im Stalwart-Postfach ab, ein eigener Validator liegt nicht in diesem Umfang.
- Der Beispiel-Alarm ist ein Abweichungs-Alarm; Radar- und amtliche Warnungen werden nicht separat erzeugt, „deckt Radar mit ab“ bedeutet dieselbe Kanalmenge.
- Die Uhrzeit der Rückmeldung ist die Client-Uhr beim Eintreffen der Antwort.
- Ein Test-SMS-Alarm verbraucht echtes SMS-Tageskontingent und kostet echtes Geld; das ist gewollt.
- Die Alarm-Vorschau-UI bleibt bis Folge-Issue #3458 bestehen; beide Wege laufen bis dahin parallel.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (setzt ADR-0011, ADR-0095, ADR-0097, ADR-0109 Punkt 6 um)
- **Rationale:** Renderer = Versand, Kanal-Parität und Menüstruktur sind bereits entschieden; der Test-Alarm nutzt den bestehenden Alarm-Versandweg mit einem Test-Schalter und die bestehende Kanal-Auflösung. Keine neue Grundsatzentscheidung.

## Changelog

- 2026-11-27: Initial spec created (Issue #3441, Scheibe S5b von #2797, Epic #2791)
