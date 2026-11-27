# Adversary Dialog — feat-3440-test-schicken-menue
Spec: docs/specs/modules/feat_3440_test_schicken_menue.md
Datum: 2026-11-27 08:31

## Checkliste
- [x] **Input:** Klick auf „Test schicken ▾“, danach (Trip) Wahl Morgen/Abend, danach Klick auf eine Kanalzeile oder „Alle eingerichteten Kanäle“.
- [x] **Output:** Versand an genau den gewählten Kanal bzw. an alle eingerichteten; Rückmeldung 5 s in Trip und Orte gleich; Fehler rot mit `fehler.versand.*`.
- [x] **Side effects:** Echter Versand an die Empfänger des angemeldeten Nutzers, Buchung `manueller_abruf` je Klick, Mengenbremse `bremsen.Versand`, [TEST]-Präfix im Trip-Testpfad bleibt.
- [x] **AC-1:** Given der Trip-Hub oder der Orte-Hub eines aktiven Abos / When der Nutzer „Test schicken ▾“ anklickt / Then öffnet sich ein Menü am Knopf und der Dialog „Briefing senden?“ erscheint nicht; beide Hubs nutzen denselben Baustein mit `context` route bzw. vergleich.
- [x] **AC-2:** Given der Trip-Hub / When das Menü offen ist / Then steht oben das Segment „Morgen-Briefing · Abend-Briefing“ (Vorauswahl Morgen), und ein Wechsel des Segments lässt das Menü offen; im Orte-Hub gibt es kein Segment.
- [x] **AC-3:** Given ein Nutzer mit bestätigter E-Mail, verbundenem Telegram, bestätigter SMS und eingerichtetem Premium-SMS / When das Menü offen ist / Then zeigt es vier Kanalzeilen in der Reihenfolge E-Mail, Telegram, SMS, Premium-SMS mit den Zielen gekürzte Adresse, „verbunden“ (ohne Namen und Chat-ID), gekürzte Nummer und „inReach · über Satellit“.
- [x] **AC-4:** Given ein Kanal, den `kanalStatus` als nicht bedienbar meldet (Telegram ohne Chat, SMS unbestätigt, Premium-SMS verfallen) / When das Menü offen ist / Then ist die Zeile ausgegraut mit „gesperrt: {Grund}“ und dem Knopf „Im Konto {verbinden|bestätigen|prüfen} →“, der zu `/account` führt, und ein Klick auf die Zeile schickt nichts.
- [x] **AC-5:** Given ein Nutzer mit unbestätigter E-Mail-Adresse / When er das Menü öffnet oder `channel=email` direkt am Endpunkt aufruft / Then ist die E-Mail-Zeile gesperrt („gesperrt: Adresse noch nicht bestätigt.“, „Im Konto bestätigen →“) und das Backend lehnt den Einzelversand an E-Mail ab, ohne etwas zu senden.
- [x] **AC-6:** Given ein verbundener, bedienbarer Kanal / When der Nutzer im offenen Menü auf diese Kanalzeile klickt / Then geht genau ein Versand an diesen Kanal raus (Request mit `channel`), das Menü schließt, und kein anderer Kanal erhält etwas.
- [x] **AC-7:** Given der Endpunkt `POST /api/briefings/{id}/send` / When `channel` einen unbekannten Wert hat / Then antwortet Go mit 400 und reicht nichts weiter; wird Python direkt mit unbekanntem `channel` aufgerufen, antwortet er ebenfalls 400 `invalid_channel`, und es geht nichts raus.
- [x] **AC-8:** Given ein verbundener Kanal, der im Abo des Trips bzw. Ortsvergleichs ausgeschaltet ist / When der Nutzer im Menü diese Kanalzeile wählt / Then geht der Test an diesen Kanal (der Test prüft den Kanal, nicht das Abo), und das Tarif-Gate für SMS/Premium-SMS bleibt wirksam.
- [x] **AC-9:** Given ein Nutzer ohne E-Mail-Konfiguration (kein `mail_to`), aber mit verbundenem Telegram / When er `channel=telegram` sendet / Then geht der Telegram-Test raus, ohne am E-Mail-Gate zu scheitern; ohne `channel` und bei `channel=email` bleibt das E-Mail-Gate wirksam.
- [x] **AC-10:** Given mindestens ein eingerichteter Kanal / When der Nutzer „Alle eingerichteten Kanäle“ wählt / Then wird ohne `channel` gesendet, die Antwort enthält `sent_channels`, und die Rückmeldung lautet „{Briefing} geschickt: E-Mail ✓ · Telegram übersprungen ({Grund}) · …“, wobei ein bedienbarer, im Abo ausgeschalteter Kanal als „übersprungen (im Briefing aus)“ und nur ein im Abo eingeschalteter, bedienbarer, aber nicht gesendeter Kanal als „fehlgeschlagen“ erscheint.
- [x] **AC-11:** Given ein erfolgreicher Einzelversand / When die Antwort eintrifft / Then erscheint „{Morgen-Briefing|Abend-Briefing|Briefing} an {Kanal} geschickt · {Ziel} · {hh:mm}“ (Trip mit Segment-Namen, Orte mit „Briefing“), identisch aufgebaut in Trip und Orte, auch bei Viewport ≤899 px, und verschwindet nach 5 s.
- [x] **AC-12:** Given ein fehlgeschlagener Versand (Kanal nicht erreichbar, Kontingent erschöpft, Mengenbremse) / When die Antwort eintrifft / Then erscheint die Fehlermeldung rot (testid `test-schicken-fehler`) mit dem bestehenden Text aus `fehler.versand.*`, in Trip und Orte gleich.
- [x] **AC-13:** Given ein Versand läuft für ein Abo / When der Nutzer erneut klickt (egal auf welchen Kanal) / Then antwortet das Backend 409 `already_running`, die Seite zeigt den unveränderten Text, und es entsteht kein zweiter Versand; der Schutz gilt je Abo, nicht je Kanal.
- [x] **AC-14:** Given zwei verschiedene angemeldete Nutzer A und B mit je eigener Adresse und eigenem Chat / When B den Einzelversand über `channel` auslöst / Then gehen Nachricht und Ziel ausschließlich an B; ein mitgesendeter `user_id`- oder Empfängerwert des Clients wird verworfen, und ohne Session gibt es 401 statt Rückfall auf einen Default-Nutzer.
- [x] **AC-15:** Given das Menü auf einem Desktop-Viewport / When der Nutzer es mit Escape oder Klick außerhalb schließt oder die Pfeiltasten und Enter nutzt / Then schließt das Menü bzw. bedient die Zeilen per Tastatur, der Knopf trägt `aria-haspopup="menu"` und `aria-expanded` entspricht dem Zustand, und auf ≤899 px öffnet statt des Dropdowns ein Sheet mit mindestens 44 px hohen Zeilen.
- [x] **AC-16:** Given Sprache Deutsch oder Englisch am Nutzer / When Menü, Sperrgründe, Konto-Knöpfe und Rückmeldungen erscheinen / Then stehen alle neuen Texte im Katalog DE und EN, Protokoll-Token (Kanalnamen, Kürzel) bleiben unübersetzt, und die Texte des Abschnitts `test-menue` stimmen mit der Elementliste in beiden Sprachen überein.
- [x] **AC-17:** Given die Elementliste mit dem Abschnitt `test-menue` / When der Abgleich läuft / Then hat der Abschnitt einen Bedienplan (Knopf öffnen, lesen, schließen) und ist nicht mehr `nicht_herstellbar`, die Ziele E-Mail („an 2 Empfänger“) und Telegram („@henning“) erscheinen als „freigegeben“ mit Verweis auf #3202 und diese Spec, und der Abschnitt trägt `data-abschnitt="test-menue"`.
- [x] **AC-18:** Given die Listen `/trips` und `/compare` / When der Nutzer dort „Briefing senden“ wählt / Then erscheint weiter der Dialog „Briefing senden?“ mit Ziel und (beim Trip) Morgen/Abend, unverändert zu heute.
- [x] **AC-19:** Given das Menü ist gebaut / When später der Eintrag „Test-Alarm“ (#3441) ergänzt wird / Then genügt ein zusätzlicher Eintrag nach dem Trenner unter „Alle eingerichteten Kanäle“ ohne Umbau der Menüstruktur; in diesem Workflow erscheint der Eintrag nicht.
- [x] **AC-20:** Given der Trip-Hub oder Orte-Hub eines archivierten oder im Entwurf stehenden Abos / When die Seite angezeigt wird / Then ist „Test schicken ▾“ wie bisher gesperrt bzw. im Entwurf Setup-Modus, und das Menü öffnet sich nicht.
- [x] **AC-21:** Given ein Klick auf eine Kanalzeile oder auf „Alle eingerichteten Kanäle“ / When der Versand gebucht wird / Then zählt jeder Klick einmal gegen das Kontingent `manueller_abruf` (auch ein Einzelkanal), und ein erschöpftes Kontingent ergibt die bestehende Fehlermeldung `kontingent_erschoepft`.

## Dialog

### Runde 1
**Adversary:** Alle 24 Punkte gegen Code und Tests geprüft; benannte Läufe: pytest 5 Dateien grün (adversary2-pytest-output.txt), Go handler+i18n grün (adversary2-go-output.txt), Frontend 8 Dateien, 150 Tests grün (adversary2-frontend-output.txt).
Fixes aus Runde 1:
- F001 behoben: `alleRueckmeldung` prüft Reihenfolge gesendet, gesperrt, Abo-aus, fehlgeschlagen. Code reference: frontend/src/lib/components/molecules/testSchickenModell.ts:171 (Abo-Stand `p.abo`, Zeile 185); beide Seiten reichen `aboKanaele(...)` durch (frontend/src/routes/trips/[id]/+page.svelte:295, frontend/src/routes/compare/[id]/+page.svelte:280).
- F002 behoben: 5 s, Reset auf Morgen und 44 px sind jetzt im Kern-Lauf bewacht. Code reference: frontend/src/lib/components/molecules/TestSchickenMenue.svelte (Zeile `@media (max-width: 899px)` / `min-height: var(--g-tap-min)`), testSchickenModell.ts:31 und :78; Staging-Config frontend/playwright.3440-test-menue.staging.config.ts:9.
- F003 behoben: Katalogtext ohne Platzhalter. Code reference: api/routers/briefings_send.py:144 (`channel=channel` wird an `_error` übergeben, `t()` ignoriert unbenutzte Werte; Mutation M6 mit `{channel}` im Text wird rot, also kein Spiegeln im Ist-Zustand). Toter Parameter = Kosmetik.
Weitere Code-Referenzen (alle Pflichtdateien): internal/handler/briefing_send.go:59 (Whitelist, 400 invalid_channel, channel nur nach Whitelist weitergereicht); src/services/send_outcomes.py:38 (email_unverified 422, invalid_channel 400); src/services/trip_report_scheduler.py:1499 (sent_channels_sink im finally, Lock je Abo, Zeile 1482/2015); src/services/scheduler_dispatch_service.py:1055 (Orte: sent_channels); frontend/src/lib/utils/sendOutcome.ts:162 (sentChannels aus Antwort); frontend/src/lib/components/shared/subscriptionExec.ts:104 (channel nur aus Menüwahl); frontend/src/lib/i18n/messages/de/index.ts:26 und frontend/src/lib/i18n/messages/en/index.ts:26 (Katalog test_schicken eingebunden).
Mutations-Gegenprobe (Sicherung im Scratchpad, nach jeder Mutation per diff identisch): 21 Mutationen, alle rot, ausser M2 (erste Fassung war äquivalent, wegen `z.bedienbar`-Bedingung; die echte Vertauschung M2_swap wird rot): M1 Abo-Stand ignorieren rot; M2b gesendet-Prüfung entfernen rot; M2_swap Abo vor Sperre rot; M3/M3b/M3c RUECKMELDUNG_MS (Modell, Trip-Seite, Orte-Seite) rot; M4 Reset entfernen rot; M5/M5b/M5c/M5d min-height, --g-tap-min, Media-Query, $effect entfernen rot; M6 channel in Text rot; M7 invalid_channel-Prüfung weg rot; M8 email_unverified weg rot; M9 E-Mail-Gate immer rot; M10 restrict_to_channel nicht durchgereicht rot; M11 Tarif-Gate weg rot; M12 Go-Whitelist weg rot; M13 Go reicht channel nicht weiter rot; M14 sent_channels entfernt rot; M15 Orte-Seite ohne echten Abo-Stand rot.
**Implementierer:** (Fix-Loop 1 bereits eingearbeitet, keine neuen Befunde.)

### Runde 2
**Adversary:** Skeptische Gegenprobe an der Wirkstelle: Abo-Stand wird von beiden Seiten tatsächlich an `testErgebnis` gereicht (M15, M3b/M3c rot), Backend-Ablehnung unbestätigter E-Mail greift vor dem Versand (M8), Kanal-Isolation (AC-14) nur über Whitelist, kein Empfängerwert wird akzeptiert (Go setzt nur channel, briefing_send.go:59). Kein weiteres Finding. Offen nur LOW-Beobachtung F004: `channel=channel` an `_error` ohne Platzhalter ist wirkungslos (api/routers/briefings_send.py:144), kann entfernt werden.
**Implementierer:** n/a

## Findings und Confirmations
(AC-1 bis AC-21 sowie Input/Output/Side effects: alle CONFIRMED; F001-F003 behoben; Tests und Mutationen siehe oben.)

Code reference: api/routers/briefings_send.py:144
Evidence: Finding F004 (LOW, anti_pattern): toter Parameter channel=channel an _error; AC-7 erfüllt, Katalogtext ohne Platzhalter.

Code reference: api/routers/briefings_send.py:77
Evidence: Confirmation AC-6/AC-8/AC-9: channel wird als restrict_to_channel an den Trip-Versand gereicht; Status CONFIRMED.

Code reference: api/routers/briefings_send.py:88
Evidence: Confirmation AC-10: sent_channels in der Antwort; Status CONFIRMED.

Code reference: internal/handler/briefing_send.go:59
Evidence: Confirmation AC-7/AC-14: Whitelist, 400 invalid_channel, nur channel weitergereicht; Status CONFIRMED.

Code reference: src/services/send_outcomes.py:38
Evidence: Confirmation AC-5: email_unverified 422; Status CONFIRMED.

Code reference: src/services/trip_report_scheduler.py:1499
Evidence: Confirmation AC-13/AC-21: Lock je Abo, sent_channels_sink; Status CONFIRMED.

Code reference: src/services/scheduler_dispatch_service.py:1055
Evidence: Confirmation AC-10 Orte: sent_channels; Status CONFIRMED.

Code reference: frontend/src/lib/utils/sendOutcome.ts:162
Evidence: Confirmation AC-10/AC-11: sentChannels aus Antwort; Status CONFIRMED.

Code reference: frontend/src/lib/components/shared/subscriptionExec.ts:104
Evidence: Confirmation AC-6/AC-14: channel nur aus Menüwahl; Status CONFIRMED.

Code reference: frontend/src/lib/components/molecules/testSchickenModell.ts:185
Evidence: Confirmation AC-10 (F001 behoben): Abo-aus ergibt übersprungen (im Briefing aus); Status CONFIRMED.

Code reference: frontend/src/lib/components/molecules/testSchickenModell.ts:31
Evidence: Confirmation AC-11 (F002 behoben): RUECKMELDUNG_MS 5000; Status CONFIRMED.

Code reference: frontend/src/lib/components/molecules/TestSchickenMenue.svelte:197
Evidence: Confirmation AC-15 (F002 behoben): 44-px-Zeilen im Media-Query; Status CONFIRMED.

Code reference: frontend/src/lib/i18n/messages/de/index.ts:26
Evidence: Confirmation AC-16: Katalog DE eingebunden; Status CONFIRMED.

Code reference: frontend/src/lib/i18n/messages/en/index.ts:26
Evidence: Confirmation AC-16: Katalog EN eingebunden; Status CONFIRMED.

Code reference: frontend/playwright.3440-test-menue.staging.config.ts:9
Evidence: Confirmation AC-11/AC-15/AC-17: Staging-Spec-Konfiguration vorhanden; Status CONFIRMED.

## Herkunft der Vorbedingungen

<!-- vom Prüfer auszufüllen, siehe `precondition_origins.py` -->

## Verdict

VERDICT: VERIFIED (mit LOW F004)

## Geprüfte Dateien

- sha256:081852c4b96bd46b405f83d77bf693fb58e9be542650ea7ab35f68501b00fc16  api/routers/briefings_send.py
- sha256:92e6fdcbe2e16c037796bebf83da68f35f68536e62b64e0c3ecca39259339d43  frontend/playwright.3440-test-menue.staging.config.ts
- sha256:44617c7e5e097c288393a827f5bab3bd73ef5c4f6f9533f0adb4920e3209fbab  frontend/src/lib/components/molecules/TestSchickenMenue.svelte
- sha256:a47e17fc543ccf0f2e38d1d1aa03074d553114ed616c13668cdd3ee46b456f55  frontend/src/lib/components/molecules/testSchickenModell.ts
- sha256:7da78139a904396998b2ad3d6c8c8d2ee949f946cd07350d5a96ab11f688efe2  frontend/src/lib/components/shared/subscriptionExec.ts
- sha256:7ef2ba3bccd3330948b678d45903c4ab42e6da39cfaf85efff3a746b1881ecdb  frontend/src/lib/i18n/messages/de/index.ts
- sha256:69cb729730b254aca5eb13818a12d42b5cdd76d7f02e9cb66d4a94e97a6d340d  frontend/src/lib/i18n/messages/en/index.ts
- sha256:3472a812fd10d589cba5ce36cd49aa3fe645dfbc882c6d0613e29f3b17abe027  frontend/src/lib/utils/sendOutcome.ts
- sha256:a7451f39503c5809159cedbf3da7673c9f5079a613d57365f95c3b6b0ae1e4ff  internal/handler/briefing_send.go
- sha256:5c4c12fe46e40ce2e5db42206d44a62a208b5c06b1e2ef0902698dc9cfd0a3b7  src/services/scheduler_dispatch_service.py
- sha256:8b5c0cb5471c3be5f9048a11f36026cdfb7aa50da1a4c4675806cbd4aa72462b  src/services/send_outcomes.py
- sha256:101a388842b2bd4c06cd4be1502d702d8a3c15206ff597a7484e98b750ce4da0  src/services/trip_report_scheduler.py

## Prüfbasis

- base: e762bb09a16abb4b744cbabb94e2b0ed96ccb207
- blob:488d8423a56f5c277eb647d111645c5e2cfca32c  api/routers/briefings_send.py
- blob:6f06026fe80202e0dec5728a7dbb9dc809d64a95  frontend/playwright.3440-test-menue.staging.config.ts
- blob:3a6e56614c98b42c1f95300ce6ec7a12652e8ddd  frontend/src/lib/components/molecules/TestSchickenMenue.svelte
- blob:a34c8055264c9b817808135255c5d063ba0add30  frontend/src/lib/components/molecules/testSchickenModell.ts
- blob:9c3884d9ff2fc957592e30a48fe99741cf436a5f  frontend/src/lib/components/shared/subscriptionExec.ts
- blob:51de80139e1d38b0f00b882daac7722fa3ed14bc  frontend/src/lib/i18n/messages/de/index.ts
- blob:7ee989369a963cb014501017ca639d4389216eb5  frontend/src/lib/i18n/messages/en/index.ts
- blob:98db13d6e0da23938d0c9aea23db9b4c45cef02f  frontend/src/lib/utils/sendOutcome.ts
- blob:f75a40a827653b8cad246b54a617b35e75dec6d0  internal/handler/briefing_send.go
- blob:8d584141914b8a4c1c9552b0bf46353730a72edb  src/services/scheduler_dispatch_service.py
- blob:74b3ac11c74af6946b66fc30e0bf29fe7aa49418  src/services/send_outcomes.py
- blob:e4921d6d4db8bc50ed7fcab22971894bfed262af  src/services/trip_report_scheduler.py

## Geprüfte Dateien

- sha256:081852c4b96bd46b405f83d77bf693fb58e9be542650ea7ab35f68501b00fc16  api/routers/briefings_send.py
- sha256:92e6fdcbe2e16c037796bebf83da68f35f68536e62b64e0c3ecca39259339d43  frontend/playwright.3440-test-menue.staging.config.ts
- sha256:44617c7e5e097c288393a827f5bab3bd73ef5c4f6f9533f0adb4920e3209fbab  frontend/src/lib/components/molecules/TestSchickenMenue.svelte
- sha256:a47e17fc543ccf0f2e38d1d1aa03074d553114ed616c13668cdd3ee46b456f55  frontend/src/lib/components/molecules/testSchickenModell.ts
- sha256:7da78139a904396998b2ad3d6c8c8d2ee949f946cd07350d5a96ab11f688efe2  frontend/src/lib/components/shared/subscriptionExec.ts
- sha256:7ef2ba3bccd3330948b678d45903c4ab42e6da39cfaf85efff3a746b1881ecdb  frontend/src/lib/i18n/messages/de/index.ts
- sha256:69cb729730b254aca5eb13818a12d42b5cdd76d7f02e9cb66d4a94e97a6d340d  frontend/src/lib/i18n/messages/en/index.ts
- sha256:3472a812fd10d589cba5ce36cd49aa3fe645dfbc882c6d0613e29f3b17abe027  frontend/src/lib/utils/sendOutcome.ts
- sha256:a7451f39503c5809159cedbf3da7673c9f5079a613d57365f95c3b6b0ae1e4ff  internal/handler/briefing_send.go
- sha256:5c4c12fe46e40ce2e5db42206d44a62a208b5c06b1e2ef0902698dc9cfd0a3b7  src/services/scheduler_dispatch_service.py
- sha256:8b5c0cb5471c3be5f9048a11f36026cdfb7aa50da1a4c4675806cbd4aa72462b  src/services/send_outcomes.py
- sha256:101a388842b2bd4c06cd4be1502d702d8a3c15206ff597a7484e98b750ce4da0  src/services/trip_report_scheduler.py

## Prüfbasis

- base: e762bb09a16abb4b744cbabb94e2b0ed96ccb207
- blob:488d8423a56f5c277eb647d111645c5e2cfca32c  api/routers/briefings_send.py
- blob:6f06026fe80202e0dec5728a7dbb9dc809d64a95  frontend/playwright.3440-test-menue.staging.config.ts
- blob:3a6e56614c98b42c1f95300ce6ec7a12652e8ddd  frontend/src/lib/components/molecules/TestSchickenMenue.svelte
- blob:a34c8055264c9b817808135255c5d063ba0add30  frontend/src/lib/components/molecules/testSchickenModell.ts
- blob:9c3884d9ff2fc957592e30a48fe99741cf436a5f  frontend/src/lib/components/shared/subscriptionExec.ts
- blob:51de80139e1d38b0f00b882daac7722fa3ed14bc  frontend/src/lib/i18n/messages/de/index.ts
- blob:7ee989369a963cb014501017ca639d4389216eb5  frontend/src/lib/i18n/messages/en/index.ts
- blob:98db13d6e0da23938d0c9aea23db9b4c45cef02f  frontend/src/lib/utils/sendOutcome.ts
- blob:f75a40a827653b8cad246b54a617b35e75dec6d0  internal/handler/briefing_send.go
- blob:8d584141914b8a4c1c9552b0bf46353730a72edb  src/services/scheduler_dispatch_service.py
- blob:74b3ac11c74af6946b66fc30e0bf29fe7aa49418  src/services/send_outcomes.py
- blob:e4921d6d4db8bc50ed7fcab22971894bfed262af  src/services/trip_report_scheduler.py

## Geprüfte Dateien

- sha256:081852c4b96bd46b405f83d77bf693fb58e9be542650ea7ab35f68501b00fc16  api/routers/briefings_send.py
- sha256:92e6fdcbe2e16c037796bebf83da68f35f68536e62b64e0c3ecca39259339d43  frontend/playwright.3440-test-menue.staging.config.ts
- sha256:44617c7e5e097c288393a827f5bab3bd73ef5c4f6f9533f0adb4920e3209fbab  frontend/src/lib/components/molecules/TestSchickenMenue.svelte
- sha256:a47e17fc543ccf0f2e38d1d1aa03074d553114ed616c13668cdd3ee46b456f55  frontend/src/lib/components/molecules/testSchickenModell.ts
- sha256:7da78139a904396998b2ad3d6c8c8d2ee949f946cd07350d5a96ab11f688efe2  frontend/src/lib/components/shared/subscriptionExec.ts
- sha256:7ef2ba3bccd3330948b678d45903c4ab42e6da39cfaf85efff3a746b1881ecdb  frontend/src/lib/i18n/messages/de/index.ts
- sha256:69cb729730b254aca5eb13818a12d42b5cdd76d7f02e9cb66d4a94e97a6d340d  frontend/src/lib/i18n/messages/en/index.ts
- sha256:3472a812fd10d589cba5ce36cd49aa3fe645dfbc882c6d0613e29f3b17abe027  frontend/src/lib/utils/sendOutcome.ts
- sha256:a7451f39503c5809159cedbf3da7673c9f5079a613d57365f95c3b6b0ae1e4ff  internal/handler/briefing_send.go
- sha256:5c4c12fe46e40ce2e5db42206d44a62a208b5c06b1e2ef0902698dc9cfd0a3b7  src/services/scheduler_dispatch_service.py
- sha256:8b5c0cb5471c3be5f9048a11f36026cdfb7aa50da1a4c4675806cbd4aa72462b  src/services/send_outcomes.py
- sha256:101a388842b2bd4c06cd4be1502d702d8a3c15206ff597a7484e98b750ce4da0  src/services/trip_report_scheduler.py

## Prüfbasis

- base: e762bb09a16abb4b744cbabb94e2b0ed96ccb207
- blob:488d8423a56f5c277eb647d111645c5e2cfca32c  api/routers/briefings_send.py
- blob:6f06026fe80202e0dec5728a7dbb9dc809d64a95  frontend/playwright.3440-test-menue.staging.config.ts
- blob:3a6e56614c98b42c1f95300ce6ec7a12652e8ddd  frontend/src/lib/components/molecules/TestSchickenMenue.svelte
- blob:a34c8055264c9b817808135255c5d063ba0add30  frontend/src/lib/components/molecules/testSchickenModell.ts
- blob:9c3884d9ff2fc957592e30a48fe99741cf436a5f  frontend/src/lib/components/shared/subscriptionExec.ts
- blob:51de80139e1d38b0f00b882daac7722fa3ed14bc  frontend/src/lib/i18n/messages/de/index.ts
- blob:7ee989369a963cb014501017ca639d4389216eb5  frontend/src/lib/i18n/messages/en/index.ts
- blob:98db13d6e0da23938d0c9aea23db9b4c45cef02f  frontend/src/lib/utils/sendOutcome.ts
- blob:f75a40a827653b8cad246b54a617b35e75dec6d0  internal/handler/briefing_send.go
- blob:8d584141914b8a4c1c9552b0bf46353730a72edb  src/services/scheduler_dispatch_service.py
- blob:74b3ac11c74af6946b66fc30e0bf29fe7aa49418  src/services/send_outcomes.py
- blob:e4921d6d4db8bc50ed7fcab22971894bfed262af  src/services/trip_report_scheduler.py
