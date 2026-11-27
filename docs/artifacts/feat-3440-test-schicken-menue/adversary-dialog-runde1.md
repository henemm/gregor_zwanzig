# Adversary Dialog — feat-3440-test-schicken-menue
Spec: docs/specs/modules/feat_3440_test_schicken_menue.md
Datum: 2026-11-27 07:45

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
- [x] **AC-10:** Given mindestens ein eingerichteter Kanal / When der Nutzer „Alle eingerichteten Kanäle“ wählt / Then wird ohne `channel` gesendet, die Antwort enthält `sent_channels`, und die Rückmeldung lautet „{Briefing} geschickt: E-Mail ✓ · Telegram übersprungen ({Grund}) · …“, wobei ein nicht gesendeter, aber bedienbarer Kanal als „fehlgeschlagen“ erscheint.
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
**Adversary:** Tests gelaufen (Artefakte: adversary-pytest-output.txt 170 Punkte grün, adversary-go-output.txt ok, adversary-frontend-output.txt 632 pass / 0 fail). Mutations-Gegenprobe, jeweils per String-Ersetzung, Original per diff identisch wiederhergestellt:
- Python-Whitelist `invalid_channel` entfernt (api/routers/briefings_send.py:143) -> rot test_3440_ac7_...[signal-route]
- E-Mail-Gate immer an (api/routers/briefings_send.py:67) -> rot test_3440_ac9_telegram_ohne_mail_to
- `email_unverified` entfernt (api/routers/briefings_send.py:146) -> rot test_3440_ac5_...
- `restrict_to_channel` im Trip nicht durchgereicht -> rot ac6_trip; im Vergleich nicht durchgereicht -> rot ac6_vergleich
- Tarif-Gate `channels_unreachable` entfernt (src/services/trip_report_scheduler.py:1484) -> rot ac8_tarif_gate
- `sent_channels` Trip (trip_report_scheduler.py:2015) und Vergleich (src/services/scheduler_dispatch_service.py:1055) gekappt -> rot ac10_erfolgsform
- Lock-Rückgabe `already_in_progress` neutralisiert -> rot ac9_fehlerform
- Go-Whitelist (internal/handler/briefing_send.go:58) entfernt/`len != 1` entfernt/`q.Set("channel")` entfernt -> rot TestBriefingSend3440_*
- Frontend: briefingSendUrl ohne channel (frontend/src/lib/utils/sendOutcome.ts:128), sentChannels (sendOutcome.ts:167), channel im Seitenaufruf (Trip und Orte), testProfil=null, E-Mail-unbestätigt-Sperre, Ziel/„verbunden“-Kürzung, „übersprungen“-Zweig, Bindung `disabled`, `data-abschnitt` -> alle rot.
- NICHT gefangen: (a) Rückmeldungsdauer 5000 -> 4000 bzw. 9000 (Trip +page.svelte:290, Orte +page.svelte), (b) Vorauswahl „Morgen“ bei erneutem Öffnen entfernt (TestSchickenMenue.svelte `if (offen) berichtsart = ...`), (c) 44-px-Mindesthöhe `--g-tap-min` entfernt, (d) Python `user_id: Query(...)` -> Query("default") (Bestandsverhalten, Go setzt user_id immer, daher nur LOW). (a)-(c) werden nur von der Staging-Spec geprüft (läuft in /e2e-verify): Finding F002.
Code reference: frontend/src/lib/components/shared/subscriptionExec.ts:104 — channel wird für Trip und Orte nur aus der Menüwahl durchgereicht, nie ein Empfänger.
Code-Review Mandantentrennung: Go setzt user_id ausschließlich über appendUserID(UserIDFromContext) (internal/handler/send_proxy.go:26); channel nur nach Whitelist; Python wählt Empfänger nie aus channel; Test ac14 (zwei Nutzer, fremde user_id/Empfänger im Request) und Go-Test mit 401 ohne Session grün.
Bestandstests: Diff geprüft, alle 17 geänderten Frontend-Tests und 6 Python-Tests wurden auf neues Verhalten umgestellt (onSend -> onTest, Dialog -> Menü in Hubs, Dialog in Listen unverändert und weiter geprüft, AC-18), keine Abschwächung gefunden; Listen /trips und /compare binden SendConfirmDialog weiter.
Abweichungen: Sheet.svelte `typeof window` ist verhaltensgleich zu `browser` (konstant zur Komponenteninitialisierung), SSR bleibt false; wendeFreigabenAn nur für abweichende Elemente und nur im Abschnitt/ctx der Freigabe, kein Masking anderer Abschnitte; Katalogbereich test_schicken.json ist in de/en index.ts eingebunden (Code reference: frontend/src/lib/i18n/messages/de/index.ts:26, frontend/src/lib/i18n/messages/en/index.ts:26); entfernte Bestandsschlüssel haben keine Restverwender (Tests grün).
Staging-Spec/Playwright-Config (Code reference: frontend/playwright.3440-test-menue.staging.config.ts:9): Selektoren (subscription-hub-send, data-abschnitt, test-menue-berichtsart-*, test-schicken-ok/-fehler, data-kanal, aria-expanded) stimmen mit TestSchickenMenue.svelte/HubKopf.svelte überein; Staging-Basis wird gegen Prod abgesichert.
**Implementierer:** (Developer-Stelle bekannt: „Alle“-Rückmeldung) siehe Runde 2.

### Runde 2
**Adversary:** Vertiefung der bekannten offenen Stelle (AC-10, frontend/src/lib/components/molecules/testSchickenModell.ts:155). Fall: Telegram verbunden und bedienbar, im Abo aber aus (Standard: Orte-Abo `send_telegram ?? false`, frontend/src/lib/components/shared/zustellung-tab/zustellungModell.ts:279). Klick auf „Alle eingerichteten Kanäle“: Backend sendet bewusst nur an die im Abo eingeschalteten Kanäle (richtig), `sent_channels` ohne Telegram; die Rückmeldung sagt „Telegram fehlgeschlagen“. Das ist falsch: nichts ist fehlgeschlagen, der Kanal ist im Abo aus. Die Spec verlangt den Wortlaut zwar (AC-10), die Absicht (ehrliche Rückmeldung) wird aber verfehlt, und der Fall ist der Regelfall. Fixvorschlag: alleRueckmeldung bekommt den Abo-Kanalstand (Trip: zustellungModell.ts:263, Orte: :279-289, schon vorhanden) und liefert für bedienbar-aber-im-Abo-aus den Text „{Kanal} übersprungen (im Briefing aus)“ (neuer Katalogschlüssel DE/EN, Glossar), „fehlgeschlagen“ nur für im Abo eingeschaltet, bedienbar, nicht in sent_channels; AC-10 und Unit-Test entsprechend fortschreiben. Ebenso unentschieden: Fehlschlag des Tarifs (SMS ohne Tarif) landet über kanalStatus bereits bei „übersprungen“, falls briefingGesperrt gilt – bitte im Unit-Test mit abdecken.
Weitere Randfälle geprüft: leerer/mehrfacher `channel` (Go 400), `?channel=` leer (400, Frontend sendet nie leer), Lock bei Frühabbruch (kein Sink-Eintrag, kein Release-Fehler), E-Mail-Gate nur bei channel None/email, Einzelkanal bucht je Klick (ac21 grün), Orte `fehlende_orte` wird an Einzel- und Alle-Text angehängt.
**Implementierer:** offen, siehe Findings F001, F002.

## Herkunft der Vorbedingungen

Keine fremden Vorbedingungen übernommen: Testdaten (Nutzer, Tarife, Kanäle) stammen aus den Fixtures der Testdateien im Worktree (`lage`, `_nutzer_alle_kanaele`), nicht aus Behauptungen des Entwicklers.

## Findings
Finding:
  ID: F001
  Severity: MEDIUM
  Category: spec_violation
  Code reference: frontend/src/lib/components/molecules/testSchickenModell.ts:155
  Description: alleRueckmeldung meldet jeden bedienbaren, nicht in sent_channels enthaltenen Kanal als „fehlgeschlagen“, ohne den Abo-Zustand zu kennen.
  Spec requirement: AC-10 / AC-8 — Rückmeldung soll das tatsächliche Ergebnis wiedergeben; Kanal im Abo aus ist kein Fehler.
  Conflict: Telegram verbunden, im Abo aus (Standardfall bei Orte) -> „Telegram fehlgeschlagen“ obwohl nichts fehlschlug. Spec-Wortlaut deckt das, Nutzersicht ist eine falsche Aussage.
  Remediation: Abo-Kanalstand (zustellungModell.ts:263/279) an alleRueckmeldung geben, für „im Abo aus“ neuen Text „{Kanal} übersprungen (im Briefing aus)“ (DE/EN, Glossar), Spec-AC-10 und Unit-Test anpassen.

Finding:
  ID: F002
  Severity: LOW
  Category: edge_case
  Code reference: frontend/src/routes/trips/[id]/+page.svelte:290
  Description: Rückmeldedauer 5000 ms, Vorauswahl „Morgen“ beim erneuten Öffnen (frontend/src/lib/components/molecules/TestSchickenMenue.svelte, $effect auf `offen`) und 44-px-Mindesthöhe sind durch keinen Unit-/Core-Test bewacht (Mutation 4000/9000 ms, Effekt entfernt, min-height 0: alles grün); nur die Staging-Spec (läuft in /e2e-verify) prüft sie.
  Spec requirement: AC-11, AC-2, AC-15
  Conflict: Zusicherung nur in der Live-Schicht geprüft.
  Remediation: Dauer als Konstante exportieren und im Seitenbindungstest (setTimeout-Argument) prüfen; Test für Zurücksetzen der Berichtsart beim Öffnen; CSS-Check auf --g-tap-min im Menü-Test.

Finding:
  ID: F003
  Severity: LOW
  Category: security
  Code reference: src/services/send_outcomes.py:37
  Description: Python spiegelt den unbekannten `channel`-Wert im Fehlertext (`versand.ergebnis.invalid_channel` mit {channel}); Go whitelisted davor, Python ist intern erreichbar. JSON, kein HTML, daher geringes Risiko. Zusätzlich ist `user_id` am Python-Endpunkt ohne Test gegen Default-Ersatz (Mutation Query("default") grün), Bestandsverhalten.
  Spec requirement: AC-7
  Conflict: gespiegelte Kennung (vgl. #2163 S2) nur Go-seitig verhindert.
  Remediation: Wert nicht spiegeln oder auf 40 Zeichen kürzen.

## Confirmations
Confirmation: AC-1 Code reference: frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte:116 — Menü statt Dialog, ein Baustein für beide Kontexte. CONFIRMED
Confirmation: AC-2 Code reference: frontend/src/lib/components/molecules/testSchickenModell.ts:60 — Segment nur Trip. CONFIRMED (Rest-Lücke F002)
Confirmation: AC-3/AC-4/AC-5 Code reference: frontend/src/lib/components/molecules/testSchickenModell.ts:74 — Zeilen, Sperrgründe, E-Mail-Sperre; Backend api/routers/briefings_send.py:146. CONFIRMED
Confirmation: AC-6/AC-7/AC-9 Code reference: internal/handler/briefing_send.go:58 und api/routers/briefings_send.py:143,67. CONFIRMED (Mutationen rot)
Confirmation: AC-8 Code reference: src/services/trip_report_scheduler.py:1484 — Abo-aus-Kanal wird bedient, Tarif-Gate bleibt. CONFIRMED
Confirmation: AC-10 Code reference: frontend/src/lib/components/molecules/testSchickenModell.ts:142 — spec-konform, siehe F001. AMBIGUOUS
Confirmation: AC-11/AC-12 Code reference: frontend/src/routes/trips/[id]/+page.svelte:272 — gleich gebaut in Orte. CONFIRMED (Dauer nur Staging, F002)
Confirmation: AC-13/AC-14/AC-21 Code reference: src/services/trip_report_scheduler.py:1478 und internal/handler/send_proxy.go:26 — Lock je Abo, user_id aus Auth, Buchung je Klick. CONFIRMED
Confirmation: AC-15/AC-16/AC-17/AC-18/AC-19/AC-20 Code reference: frontend/src/lib/components/molecules/TestSchickenMenue.svelte:1 — ARIA, Sheet, Katalog, Freigaben, Listen behalten Dialog, Erweiterungsslot leer, Sperre via sendDisabled. CONFIRMED (Tastatur/Viewport nur Staging)

## Verdict

VERDICT: AMBIGUOUS
Ambiguous: F001 — Implementierung spec-konform, aber „fehlgeschlagen“ für im Abo ausgeschalteten Kanal ist für Nutzer falsch (Fix und Spec-Anpassung empfohlen vor Merge). Zusätzlich F002/F003 LOW.
Tests: Python 170 Punkte grün, Go ok, node --test 632 pass / 0 fail.
