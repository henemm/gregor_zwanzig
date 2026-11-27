---
entity_id: feat_3440_test_schicken_menue
type: feature
created: 2026-11-27
updated: 2026-11-27
status: draft
version: "1.0"
workflow: feat-3440-test-schicken-menue
tags: [hub, versand, menue, kanaele, i18n, "#3440", "#2797", "#2791"]
---

# S5a: Menü „Test schicken ▾“ mit Kanalliste, Zielen, Sperren und Morgen/Abend

## Approval

- [ ] Approved

## Purpose

Der Kopf-Knopf „Test schicken ▾“ im Trip-Hub und im Orte-Hub öffnet statt des Dialogs „Briefing senden?“ ein Menü am Knopf. Das Menü zeigt je Kanal (E-Mail, Telegram, SMS, Premium-SMS) eine Zeile mit Ziel oder Sperrgrund, beim Trip oben die Wahl Morgen-/Abend-Briefing, und unten „Alle eingerichteten Kanäle“. Ein Klick auf eine Zeile schickt genau an diesen Kanal. Der Nutzer kann damit jeden Kanal einzeln prüfen (ADR-0095, ADR-0109 Punkt 6, PO-Entscheidungen K9–K12 in #2797).

## Source

- **File:** `frontend/src/lib/components/molecules/TestSchickenMenue.svelte` (neu), `frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte` (Knopf öffnet Menü), `api/routers/briefings_send.py` (Kanalparameter)
- **Identifier:** `TestSchickenMenue` (Baustein, `context="route"|"vergleich"`), `HubKopf` (Prop `onTest`), `send_briefing_endpoint` (Query `channel`), `BriefingSendHandler` (Go-Whitelist)

## Estimated Scope

- **LoC:** Produktivcode ca. 435–550 (Backend ca. 105, Frontend ca. 330–445, ohne i18n/Doku/Tests); Tests ca. 450–800
- **Files:** ca. 28 (davon ca. 10 Produktiv, Rest Tests, i18n, Doku)
- **Effort:** high

**Scope-Override (Begründung):** Das Projektlimit `scope_guard.max_loc_delta: 250` wird überschritten. Der Workflow setzt `loc_limit_override 550` (Produktivcode) und `test_loc_limit_override 800` (Tests, weil rund 25 Bestandstests auf das neue Verhalten umgestellt statt gelöscht werden). Begründung: ein vertikaler Schnitt. Der Backend-Teil (Kanalwahl am Handversand-Endpunkt) hat ohne das Menü keinen Nutzerwert und ist nicht E2E-abnehmbar; das Menü ohne Backend kann nicht an einen einzelnen Kanal senden. Kleine verwandte Teile laufen in einem Durchlauf (PO-Regel). Es sind keine weiteren Änderungen an der Gate-Konfiguration (`openspec.yaml`) und keine Schritte vorgesehen, die ein menschliches Override brauchen (Autark-Modus, #622).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `zustellungModell.kanalStatus(profil)` | module | Einzige Quelle für bedienbar/gesperrt, Grund, Konto-Verb (verbinden/bestätigen/prüfen), gekürztes Ziel (#3202). Sperrlogik wird nie neu abgeleitet |
| `zustellungModell.adresseGekuerzt` / `nummerGekuerzt` | function | Ziel-Texte E-Mail und SMS |
| `sendTargetLabel.ts` / `SendConfirmDialog` | module | Bleiben für die Listen `/trips` und `/compare` unverändert bestehen |
| `subscriptionExec.sendSubscription` / `sendOutcome.briefingSendUrl` | module | Frontend-Versandweg, erhält Parameter `channel`, wertet `sent_channels` aus |
| `Sheet`, `Segmented`, bits-ui `DropdownMenu` | atom/molecule | Mobil Sheet, Desktop Dropdown (Muster `SubscriptionKebab`), Segment Morgen/Abend |
| Go `BriefingSendHandler` (`internal/handler/briefing_send.go`) | handler | Reicht `channel` nur nach Whitelist weiter; `user_id` aus Auth-Kontext |
| Python `send_briefing_endpoint` | endpoint | Validiert `channel` erneut, liefert `sent_channels` |
| `TripReportSchedulerService.send_test_report_outcome` / `_send_trip_report_outcome(restrict_to_channel)` | service | Trip-Testpfad bekommt die Kanalnaht (#2126) |
| `SchedulerDispatchService.send_compare_preset(restrict_to_channel)` | service | Orte-Pfad nutzt die Naht aus #2282 |
| `user_tier.resolve_restricted_channel_flags` | service | Kanal wird auch bei im Abo ausgeschaltetem Kanal eingeschaltet, Tarif-Gate (SMS/Premium) bleibt |
| `send_outcomes.py` | module | Fehlervokabular (`channels_unreachable`, `kontingent_erschoepft`, neu `invalid_channel`, `email_unverified`) |
| Kontingent `manueller_abruf` (ADR-0117), Mengenbremse `bremsen.Versand` | policy | Buchung je Klick |
| ADR-0092, 0095, 0097, 0104, 0109, 0112, 0118 | ADR | Testmail nur an bestätigte Adresse; Kanal-Parität; Trip/Orte ein Code; DE/EN; Menü-Struktur; Bausteine/Tokens; Knopf-Stil |
| `docs/specs/modules/feat_2278_aktionsmodell.md` | spec | Wird für den Hub fortgeschrieben (siehe Fortschreibung) |

## Implementation Details

**Backend-Vertrag.** `POST /api/briefings/{id}/send?kind=…&report_type=…&channel=…`. Fehlt `channel`, gilt das heutige Verhalten (alle eingerichteten Kanäle). Go prüft `channel` gegen die vier Namen `email|telegram|sms|premium_sms` und reicht ihn sonst nicht weiter (400). Python validiert erneut gegen `_BEKANNTE_KANAELE`; unbekannt ⇒ 400 `invalid_channel`. `user_id` kommt weiter aus dem Auth-Kontext, der Kanalparameter wählt nie einen Empfänger. Antwort bekommt `sent_channels: [..]` (Trip und Vergleich). Trip: `send_test_report_outcome(..., restrict_to_channel=None, sent_channels_sink=None)` reicht an `_send_trip_report_outcome` durch; Vergleich: Sink in `send_compare_preset`. Ein gesperrter Kanal liefert `channels_unreachable` mit dem bestehenden Text. E-Mail-Gate `can_send_email()` gilt nur bei `channel` None oder `email`; `channel=email` bei unbestätigter Adresse wird abgelehnt (`email_unverified`, ADR-0092); ein Telegram-Test geht ohne Mail-Konfiguration. In-Flight-Schutz und Python-Lock bleiben je Abo (nicht je Kanal): ein zweiter Klick während eines laufenden Versands ergibt 409 `already_running` mit bestehendem Text. Das Kontingent `manueller_abruf` bucht je Klick, auch bei Einzelkanal.

**Frontend.**
- `TestSchickenMenue.svelte` (molecules) ist EIN Baustein für Trip und Orte (`context="route"|"vergleich"`), ruft keine API, emittiert `{kanal: KanalId | 'alle', berichtsart}`. Desktop bits-ui `DropdownMenu`, ≤899 px `Sheet` mit 44-px-Zeilen (Kebab-Muster). Abschnitt-Haken `data-abschnitt="test-menue"`. Die Struktur (Kopf mit Segment, Kanalzeilen, Trenner, „Alle eingerichteten Kanäle“, Slot für weitere Einträge nach einem Trenner) erlaubt den späteren Eintrag „Test-Alarm“ (#3441) ohne Umbau; er wird hier NICHT gebaut.
- `testSchickenModell.ts` (molecules): Zeilenmodell aus `kanalStatus(profil)`; E-Mail unbestätigt wird über ein Test-Flag im Modell gesperrt („gesperrt: Adresse noch nicht bestätigt.“, Konto-Verb „bestätigen“), ohne die Logik zu kopieren. Rückmeldungstexte Einzel/Alle.
- Ziele: E-Mail = gekürzte Konto-Adresse (`adresseGekuerzt`), Telegram = „verbunden“ (kein Name, keine Chat-ID), SMS = `nummerGekuerzt`, Premium-SMS = „inReach · über Satellit“. Das Mockup zeigt „an 2 Empfänger“ und „@henning“; das widerspricht den PO-Entscheidungen vom 20./21.11. (#3202: kein Telegram-Name, keine Empfängerzahl, `preset.empfaenger` inert seit #1452) und ist bereits entschieden. Die Abweichung wird in `docs/context/einstellungen_neu/elementliste_freigaben.json` als zwei Freigaben (Schema `ctx, reiter, abschnitt, i18n_keys, grund, spec`; Abschnitt `test-menue`, Reiter `wetter`, Kontexte trip/orte) mit Verweis auf #3202 und diese Spec eingetragen.
- `HubKopf.svelte`: Knopf `subscription-hub-send` toggelt das Menü (`aria-haspopup="menu"`, `aria-expanded`), neuer Callback `onTest({kanal, berichtsart})` ersetzt `onSend`. Stil bleibt `Btn variant="accent"` (ADR-0118).
- Seiten `routes/trips/[id]/+page.svelte` und `routes/compare/[id]/+page.svelte`: `SendConfirmDialog` und sein Zustand entfallen im Hub, `handleTest` ruft `sendSubscription` mit Kanal; Rückmeldung einheitlich über das Snippet `meldungen` (testids `test-schicken-ok` / `test-schicken-fehler`), 5 s, in jeder Breite. Uhrzeit = Client-Uhr beim Erfolg (`hh:mm`, lokal). Orte-Label „Briefing“ (nicht „Orts-Briefing“, Glossar).
- Rückmeldung „Alle“: „{Briefing} geschickt: E-Mail ✓ · Telegram übersprungen ({Grund}) · …“. „✓“ je Kanal in `sent_channels`; „übersprungen ({Grund})“ je nicht bedienbarem Kanal aus `kanalStatus` (Grund = letzter Teil des Statustexts); „übersprungen (im Briefing aus)“ je bedienbarem Kanal, der im Abo ausgeschaltet ist (Abo-Kanalstand aus `standAusTrip`/`standAusPreset`, über eine context-Tabelle für Trip und Orte; die Seiten reichen ihn durch); „fehlgeschlagen“ nur bei im Abo eingeschaltet und bedienbar, aber nicht in `sent_channels`. Rückmeldedauer `RUECKMELDUNG_MS` (5 s) als eine Konstante für Trip und Orte.
- Texte nur über den Katalog DE/EN in `frontend/messages/{de,en}/` (Namensraum `test_schicken.*`): Ziel Premium-SMS, „Alle eingerichteten Kanäle“, E-Mail-Sperrgrund, Einzel-/Alle-Rückmeldung, „übersprungen“, neutrales „Briefing“. Bestand wird wiederverwendet (`trip.briefing.morgen/abend`, `zustellung.kanal.*`, `zustellung.gesperrt`, `zustellung.konto.*`, `fehler.versand.*`, `aktionen.kopf.test_schicken`). Der Bestandsschlüssel `bausteine.senden_dialog.*` bleibt, weil die Listen den Dialog behalten. Glossar `docs/reference/i18n_glossar.md` wird um die neuen Begriffe ergänzt (Test schicken/Send test, Alle eingerichteten Kanäle/All set-up channels, gesperrt/locked im Menü, übersprungen/skipped, Ziel/target).
- Elementlisten-Abgleich: `frontend/e2e/elementliste_abgleich_logik.ts` erhält den Bedienplan `test-menue` (Klick auf `subscription-hub-send`, lesen, schließen); der Abschnitt ist nicht mehr `nicht_herstellbar`.

**Fortschreibung `feat_2278_aktionsmodell.md`.** Die Dialog-ACs AC-3, AC-4, AC-10 und der Dialog-Teil von AC-12 gelten ab dieser Spec nur noch für die Listen `/trips` und `/compare`. Im Trip-Hub und Compare-Hub ersetzt das Menü den Dialog (Morgen/Abend als Segment im Menü statt im Dialog; Ziel je Kanalzeile statt eine Zielzeile; kein Bestätigen-Schritt, der zweite Klick ist die Auslösung). Die Hub-Anteile von AC-16 (jede Aktion hat Wirkung) bleiben gültig. Die Fortschreibung wird im Changelog von `feat_2278_aktionsmodell.md` vermerkt.

**Nicht im Umfang:** Test-Alarm (#3441), Kebab-Rückfragen (#3442), Aktivieren-Pill (#3443), Änderungen an den Listen, Änderung der Kanal-Sperrlogik.

## Expected Behavior

- **Input:** Klick auf „Test schicken ▾“, danach (Trip) Wahl Morgen/Abend, danach Klick auf eine Kanalzeile oder „Alle eingerichteten Kanäle“.
- **Output:** Versand an genau den gewählten Kanal bzw. an alle eingerichteten; Rückmeldung 5 s in Trip und Orte gleich; Fehler rot mit `fehler.versand.*`.
- **Side effects:** Echter Versand an die Empfänger des angemeldeten Nutzers, Buchung `manueller_abruf` je Klick, Mengenbremse `bremsen.Versand`, [TEST]-Präfix im Trip-Testpfad bleibt.

## Acceptance Criteria

- **AC-1:** Given der Trip-Hub oder der Orte-Hub eines aktiven Abos / When der Nutzer „Test schicken ▾“ anklickt / Then öffnet sich ein Menü am Knopf und der Dialog „Briefing senden?“ erscheint nicht; beide Hubs nutzen denselben Baustein mit `context` route bzw. vergleich.
  - Test: Playwright gegen Staging in beiden Hubs (Menü sichtbar, `send-confirm-dialog` nicht im DOM) plus Unit `node --test` auf die Seiten-Bindung (beide Seiten binden `TestSchickenMenue`, keine zweite Menü-Komponente).

- **AC-2:** Given der Trip-Hub / When das Menü offen ist / Then steht oben das Segment „Morgen-Briefing · Abend-Briefing“ (Vorauswahl Morgen), und ein Wechsel des Segments lässt das Menü offen; im Orte-Hub gibt es kein Segment.
  - Test: Playwright gegen Staging (Segment klicken, Menü bleibt offen, `aria-expanded` bleibt true; im Orte-Hub kein Segment) und Unit `node --test` auf das Zeilenmodell (Segment nur bei `context="route"`).

- **AC-3:** Given ein Nutzer mit bestätigter E-Mail, verbundenem Telegram, bestätigter SMS und eingerichtetem Premium-SMS / When das Menü offen ist / Then zeigt es vier Kanalzeilen in der Reihenfolge E-Mail, Telegram, SMS, Premium-SMS mit den Zielen gekürzte Adresse, „verbunden“ (ohne Namen und Chat-ID), gekürzte Nummer und „inReach · über Satellit“.
  - Test: Unit `node --test` auf `testSchickenModell` mit echten Profilobjekten (kein Mock) plus Playwright gegen Staging mit Prüfkonto (Zeilentexte gelesen).

- **AC-4:** Given ein Kanal, den `kanalStatus` als nicht bedienbar meldet (Telegram ohne Chat, SMS unbestätigt, Premium-SMS verfallen) / When das Menü offen ist / Then ist die Zeile ausgegraut mit „gesperrt: {Grund}“ und dem Knopf „Im Konto {verbinden|bestätigen|prüfen} →“, der zu `/account` führt, und ein Klick auf die Zeile schickt nichts.
  - Test: Unit `node --test` auf das Modell (Grund und Verb je Kanal identisch zu `kanalStatus`) plus Playwright gegen Staging mit Prüfkonto im Zustand „Lücken“ (Zeile gesperrt, Request bleibt aus, Link-Ziel `/account`); kein realer SMS-Versand.

- **AC-5:** Given ein Nutzer mit unbestätigter E-Mail-Adresse / When er das Menü öffnet oder `channel=email` direkt am Endpunkt aufruft / Then ist die E-Mail-Zeile gesperrt („gesperrt: Adresse noch nicht bestätigt.“, „Im Konto bestätigen →“) und das Backend lehnt den Einzelversand an E-Mail ab, ohne etwas zu senden.
  - Test: Unit `node --test` (Sperre im Modell) und pytest am Endpunkt `tests/tdd/test_briefings_send_endpoint.py` (Nutzer mit `email_verified=false`, `channel=email` ⇒ Ablehnung `email_unverified`, kein Transportaufruf).

- **AC-6:** Given ein verbundener, bedienbarer Kanal / When der Nutzer im offenen Menü auf diese Kanalzeile klickt / Then geht genau ein Versand an diesen Kanal raus (Request mit `channel`), das Menü schließt, und kein anderer Kanal erhält etwas.
  - Test: Playwright gegen Staging mit Prüfkonto: E-Mail (Eingang im Stalwart-Test-Postfach, Anzahl 1) und Telegram (Nachricht im Testchat); pytest Endpunkt mit Transport-Fake an der Grenze (nur der gewählte Kanal wird aufgerufen).

- **AC-7:** Given der Endpunkt `POST /api/briefings/{id}/send` / When `channel` einen unbekannten Wert hat / Then antwortet Go mit 400 und reicht nichts weiter; wird Python direkt mit unbekanntem `channel` aufgerufen, antwortet er ebenfalls 400 `invalid_channel`, und es geht nichts raus.
  - Test: Go-Handler-Test `internal/handler/briefing_send_test.go` (Whitelist, Weiterreichen der vier gültigen Namen) und pytest `tests/tdd/test_briefings_send_endpoint.py` (unbekannter Kanal ⇒ 400).

- **AC-8:** Given ein verbundener Kanal, der im Abo des Trips bzw. Ortsvergleichs ausgeschaltet ist / When der Nutzer im Menü diese Kanalzeile wählt / Then geht der Test an diesen Kanal (der Test prüft den Kanal, nicht das Abo), und das Tarif-Gate für SMS/Premium-SMS bleibt wirksam.
  - Test: pytest Endpunkt (Abo mit `send_telegram=false`, Telegram verbunden, `channel=telegram` ⇒ Versand an Telegram; Tarif ohne SMS ⇒ `channels_unreachable`).

- **AC-9:** Given ein Nutzer ohne E-Mail-Konfiguration (kein `mail_to`), aber mit verbundenem Telegram / When er `channel=telegram` sendet / Then geht der Telegram-Test raus, ohne am E-Mail-Gate zu scheitern; ohne `channel` und bei `channel=email` bleibt das E-Mail-Gate wirksam.
  - Test: pytest Endpunkt `tests/tdd/test_briefings_send_endpoint.py` (Profil ohne `mail_to`: Telegram 200 mit `sent_channels=["telegram"]`, E-Mail ⇒ Gate-Fehler).

- **AC-10:** Given mindestens ein eingerichteter Kanal / When der Nutzer „Alle eingerichteten Kanäle“ wählt / Then wird ohne `channel` gesendet, die Antwort enthält `sent_channels`, und die Rückmeldung lautet „{Briefing} geschickt: E-Mail ✓ · Telegram übersprungen ({Grund}) · …“, wobei ein bedienbarer, im Abo ausgeschalteter Kanal als „übersprungen (im Briefing aus)“ und nur ein im Abo eingeschalteter, bedienbarer, aber nicht gesendeter Kanal als „fehlgeschlagen“ erscheint.
  - Test: pytest Endpunkt (Antwort enthält `sent_channels` für Trip und Vergleich) plus Unit `node --test` auf die Rückmeldungsbildung (gesendet / übersprungen mit Grund / übersprungen (im Briefing aus) für bedienbare, im Abo ausgeschaltete Kanäle, z. B. Ortsvergleich mit Telegram im Abo aus / fehlgeschlagen nur bei im Abo an, bedienbar, nicht gesendet) plus Playwright gegen Staging (Rückmeldung mit E-Mail ✓ und übersprungenen Kanälen des Prüfkontos).

- **AC-11:** Given ein erfolgreicher Einzelversand / When die Antwort eintrifft / Then erscheint „{Morgen-Briefing|Abend-Briefing|Briefing} an {Kanal} geschickt · {Ziel} · {hh:mm}“ (Trip mit Segment-Namen, Orte mit „Briefing“), identisch aufgebaut in Trip und Orte, auch bei Viewport ≤899 px, und verschwindet nach 5 s.
  - Test: Playwright gegen Staging in beiden Hubs auf Desktop- und Mobil-Viewport (testid `test-schicken-ok`, Text, Verschwinden nach 5 s) plus Unit `node --test` auf Textbildung (Client-Uhr `hh:mm`).

- **AC-12:** Given ein fehlgeschlagener Versand (Kanal nicht erreichbar, Kontingent erschöpft, Mengenbremse) / When die Antwort eintrifft / Then erscheint die Fehlermeldung rot (testid `test-schicken-fehler`) mit dem bestehenden Text aus `fehler.versand.*`, in Trip und Orte gleich.
  - Test: Unit `node --test` auf `sendOutcome`-Klassifikation je Fehlerart plus Playwright gegen Staging (Fehlerfall über gesperrten Kanal am Endpunkt, Meldung rot).

- **AC-13:** Given ein Versand läuft für ein Abo / When der Nutzer erneut klickt (egal auf welchen Kanal) / Then antwortet das Backend 409 `already_running`, die Seite zeigt den unveränderten Text, und es entsteht kein zweiter Versand; der Schutz gilt je Abo, nicht je Kanal.
  - Test: pytest Endpunkt (zwei Aufrufe mit unterschiedlichem `channel` bei gehaltenem Lock ⇒ zweiter 409) plus bestehender Playwright-Test `send-in-flight-guard.spec.ts`, umgestellt auf das Menü.

- **AC-14:** Given zwei verschiedene angemeldete Nutzer A und B mit je eigener Adresse und eigenem Chat / When B den Einzelversand über `channel` auslöst / Then gehen Nachricht und Ziel ausschließlich an B; ein mitgesendeter `user_id`- oder Empfängerwert des Clients wird verworfen, und ohne Session gibt es 401 statt Rückfall auf einen Default-Nutzer.
  - Test: pytest Endpunkt `tests/tdd/test_briefings_send_endpoint.py` und Go-Handler-Test mit zwei Nutzern (Empfänger aus Profil von B, A unberührt); Playwright gegen Staging: Menü von B zeigt nur Ziele von B.

- **AC-15:** Given das Menü auf einem Desktop-Viewport / When der Nutzer es mit Escape oder Klick außerhalb schließt oder die Pfeiltasten und Enter nutzt / Then schließt das Menü bzw. bedient die Zeilen per Tastatur, der Knopf trägt `aria-haspopup="menu"` und `aria-expanded` entspricht dem Zustand, und auf ≤899 px öffnet statt des Dropdowns ein Sheet mit mindestens 44 px hohen Zeilen.
  - Test: Playwright gegen Staging (Escape, Außenklick, Tastatur, `aria-expanded`, Viewport 390 px: Sheet und Zeilenhöhe).

- **AC-16:** Given Sprache Deutsch oder Englisch am Nutzer / When Menü, Sperrgründe, Konto-Knöpfe und Rückmeldungen erscheinen / Then stehen alle neuen Texte im Katalog DE und EN, Protokoll-Token (Kanalnamen, Kürzel) bleiben unübersetzt, und die Texte des Abschnitts `test-menue` stimmen mit der Elementliste in beiden Sprachen überein.
  - Test: Unit `node --test` i18n-Wächter (`keine_hartkodierten_nutzertexte`, Katalog-Parität DE/EN) plus Elementlisten-Abgleich `elementliste-abgleich.staging.spec.ts` gegen Staging in DE und EN.

- **AC-17:** Given die Elementliste mit dem Abschnitt `test-menue` / When der Abgleich läuft / Then hat der Abschnitt einen Bedienplan (Knopf öffnen, lesen, schließen) und ist nicht mehr `nicht_herstellbar`, die Ziele E-Mail („an 2 Empfänger“) und Telegram („@henning“) erscheinen als „freigegeben“ mit Verweis auf #3202 und diese Spec, und der Abschnitt trägt `data-abschnitt="test-menue"`.
  - Test: Unit `node --test` `elementliste_abgleich_bedienplan.test.ts` (umgestellt) plus `leseFreigaben` auf die echte Datei plus Playwright-Abgleich gegen Staging (Abschnitt gefunden, Freigaben gezählt).

- **AC-18:** Given die Listen `/trips` und `/compare` / When der Nutzer dort „Briefing senden“ wählt / Then erscheint weiter der Dialog „Briefing senden?“ mit Ziel und (beim Trip) Morgen/Abend, unverändert zu heute.
  - Test: Playwright gegen Staging auf beiden Listen (Dialog sichtbar, Versand erst nach Bestätigen) plus die unveränderten Unit-Tests `send_confirm_dialog*.test.ts`.

- **AC-19:** Given das Menü ist gebaut / When später der Eintrag „Test-Alarm“ (#3441) ergänzt wird / Then genügt ein zusätzlicher Eintrag nach dem Trenner unter „Alle eingerichteten Kanäle“ ohne Umbau der Menüstruktur; in diesem Workflow erscheint der Eintrag nicht.
  - Test: Unit `node --test` auf das Zeilenmodell (Struktur mit Erweiterungs-Slot, kein Eintrag „Test-Alarm“ im Ergebnis dieser Scheibe).

- **AC-20:** Given der Trip-Hub oder Orte-Hub eines archivierten oder im Entwurf stehenden Abos / When die Seite angezeigt wird / Then ist „Test schicken ▾“ wie bisher gesperrt bzw. im Entwurf Setup-Modus, und das Menü öffnet sich nicht.
  - Test: Unit `node --test` `trip_hub_aktionen_verhalten.test.ts` / `compare_hub_aktionen_verhalten.test.ts` (umgestellt) plus Playwright gegen Staging (Knopf disabled bei archiviert).

- **AC-21:** Given ein Klick auf eine Kanalzeile oder auf „Alle eingerichteten Kanäle“ / When der Versand gebucht wird / Then zählt jeder Klick einmal gegen das Kontingent `manueller_abruf` (auch ein Einzelkanal), und ein erschöpftes Kontingent ergibt die bestehende Fehlermeldung `kontingent_erschoepft`.
  - Test: pytest Endpunkt (zwei Klicks ⇒ zwei Buchungen; erschöpftes Kontingent ⇒ Fehlertext, kein Versand).

## Definition of Done

- [ ] Trip- und Orte-Hub öffnen das Menü, Dialog dort entfernt, Listen behalten ihn (AC-1, AC-18, AC-20)
- [ ] Segment, vier Kanalzeilen, Ziele, Sperren mit Konto-Link, E-Mail-unbestätigt-Sperre (AC-2 bis AC-5)
- [ ] Endpunkt mit `channel` (Go-Whitelist + Python-Validierung, 400), E-Mail-Gate kanalgebunden, `sent_channels`, Zwei-Nutzer-Test, 409 und Kontingent unverändert (AC-6 bis AC-10, AC-13, AC-14, AC-21)
- [ ] Rückmeldungen Einzel/Alle/Fehler in Trip und Orte gleich, auch ≤899 px (AC-10 bis AC-12)
- [ ] Bedienung Desktop-Dropdown/mobil Sheet, Tastatur, Escape, Außenklick (AC-15); Struktur für Test-Alarm vorbereitet (AC-19)
- [ ] DE/EN über Katalog, Glossar ergänzt, Elementlisten-Freigaben und Bedienplan `test-menue` (AC-16, AC-17)
- [ ] Bestandstests umgestellt, nicht gelöscht; Adversary-Verdict VERIFIED mit Mutations-Gegenprobe; alle 6 CI-Checks grün; Staging-E2E (E-Mail Stalwart + Telegram) grün; ausgeliefert, Selftest grün

## Test Plan

### Automated Tests (TDD RED)

- [ ] Unit `testSchickenModell`: GIVEN Profil mit allen vier Kanälen WHEN Zeilenmodell gebaut THEN vier Zeilen mit Zielen gemäß AC-3; GIVEN gesperrte Kanäle THEN Grund und Verb identisch zu `kanalStatus`; GIVEN E-Mail unbestätigt THEN gesperrt (AC-4, AC-5)
- [ ] Unit Rückmeldungstexte: GIVEN `sent_channels` und `kanalStatus` WHEN „Alle“ THEN ✓/übersprungen/fehlgeschlagen; GIVEN Einzel THEN Muster mit Segment-Name, Kanal, Ziel, hh:mm (AC-10, AC-11)
- [ ] pytest `tests/tdd/test_briefings_send_endpoint.py`: Kanalwahl je Kanal, unbekannt ⇒ 400, unbestätigte E-Mail, Telegram ohne Mail-Konfig, im Abo ausgeschalteter Kanal, `sent_channels` (Trip und Vergleich), 409 je Abo, Zwei-Nutzer-Test, Kontingent (AC-5 bis AC-10, AC-13, AC-14, AC-21). Transport-Fake nur an der Transportgrenze
- [ ] Go `internal/handler/briefing_send_test.go`: Whitelist der vier Kanäle, unbekannt ⇒ 400, `user_id` aus Auth-Kontext, Zwei-Nutzer (AC-7, AC-14)
- [ ] Playwright gegen Staging: `hub-send-menue.staging.spec.ts` (neu) für AC-1, 2, 3, 4, 6, 10, 11, 12, 15, 17, 18, 20; echter Versand nur E-Mail (Stalwart-Postfach) und Telegram; SMS und Premium-SMS nur Zeilen-/Sperrdarstellung und Endpunkt-Test ohne realen Versand (Kosten)
- [ ] Umgestellt statt gelöscht: `molecules/__tests__/send_confirm_dialog*.test.ts` (Listen-Bezug bleibt), `shared/__tests__/aktionsmodell_seiten_bindung.test.ts`, `aktionsmodell_bausteine_ausloeser.test.ts`, `hub-kopf/__tests__/hub_kopf_{baustein,c2_mockup,c2_bildabgleich,seiten_bindung,seiten_paritaet}.test.ts`, `trip-detail/__tests__/trip_hub_aktionen_verhalten.test.ts`, `routes/compare/__tests__/compare_hub_{aktionen_verhalten,test_send_meldung,versand_neuer_endpunkt,loeschen_bestaetigung}.test.ts`, `compare_send_dialog_target.test.ts`, `routes/trips/[id]/__tests__/trip_hub_loeschen.test.ts`, `compare/__tests__/vergleich_hub_sprache.test.ts`, `versand-tab/__tests__/sendTargetLabel*.test.ts` (unverändert, Listen), `keine_hartkodierten_nutzertexte.test.ts`, `reaktivitaet_waechter.test.ts`, `elementliste_abgleich_bedienplan.test.ts`, `bausteine_waechter` (neuer Baustein in Regeln); E2E `hub-send-dialog-target.staging.spec.ts`, `send-in-flight-guard.spec.ts`, `issue-767-768-test-briefing.spec.ts`, `aktionsmodell-durchklick.spec.ts`, `hub-kopf-c2-{mockup,bildabgleich}.staging.spec.ts`, `hub-kopf-aufbau.spec.ts`, `mobile-ux-audit.spec.ts`, `fix-2271-email-verify-gate.spec.ts`, `pwa-offline-sperre-und-mandant.spec.ts`, `e2e/helpers.ts`, `elementliste-abgleich.staging.spec.ts`; Backend `tests/tdd/_handversand_fixtures.py`, `tests/tdd/test_api_fehlertexte_forecast_handversand.py`, `internal/router/mengenbremsen_*_test.go`

## Scope (Affected Files)

| File | Change Type | LoC (ca.) | Description |
|------|-------------|-----------|-------------|
| `api/routers/briefings_send.py` | MODIFY | +45 | Query `channel`, Validierung, E-Mail-Gate nur bei None/email, `sent_channels` in Antwort |
| `src/services/trip_report_scheduler.py` | MODIFY | +30 | `restrict_to_channel` und Sink in `send_test_report_outcome`, Durchreichen |
| `src/services/scheduler_dispatch_service.py` | MODIFY | +15 | Sink gesendeter Kanäle in `send_compare_preset` |
| `src/services/send_outcomes.py` | MODIFY | +10 | `invalid_channel`, `email_unverified` samt Texten |
| `internal/handler/briefing_send.go` | MODIFY | +15 | Whitelist `channel` (400 bei unbekannt) |
| `frontend/src/lib/components/molecules/TestSchickenMenue.svelte` | CREATE | +190 | Menü-Baustein, Dropdown/Sheet, Segment, Konto-Links, Erweiterungs-Slot |
| `frontend/src/lib/components/molecules/testSchickenModell.ts` | CREATE | +110 | Zeilenmodell, E-Mail-Sperre, Rückmeldungstexte |
| `frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte` | MODIFY | +30/-10 | Knopf öffnet Menü, `onTest` |
| `frontend/src/routes/trips/[id]/+page.svelte` | MODIFY | +30/-35 | Dialog raus, `handleTest`, Rückmeldung 5 s |
| `frontend/src/routes/compare/[id]/+page.svelte` | MODIFY | +30/-35 | wie Trip |
| `frontend/src/lib/components/shared/subscriptionExec.ts` | MODIFY | +10 | `channel` durchreichen |
| `frontend/src/lib/utils/sendOutcome.ts` | MODIFY | +15 | `channel` in `briefingSendUrl`, `sent_channels` auswerten |
| `frontend/messages/{de,en}/*.json` | MODIFY | +30 | Neue Schlüssel `test_schicken.*` DE und EN |
| `docs/reference/i18n_glossar.md` | MODIFY | +10 | Neue Begriffe |
| `docs/context/einstellungen_neu/elementliste_freigaben.json` | MODIFY | +20 | Freigaben Ziel E-Mail und Telegram (Verweis #3202 und diese Spec) |
| `frontend/e2e/elementliste_abgleich_logik.ts` | MODIFY | +20 | Bedienplan `test-menue` |
| `frontend/src/lib/__tests__/bausteine_waechter_regeln.ts` | MODIFY (falls nötig) | +5 | Neuer Baustein im Scope |
| `docs/specs/modules/feat_2278_aktionsmodell.md` | MODIFY | +3 | Changelog-Vermerk Fortschreibung |
| Tests (Liste im Test Plan), neu `frontend/e2e/hub-send-menue.staging.spec.ts` | CREATE/MODIFY | +450–800 | Neue Tests und umgestellte Bestandstests |

## Known Limitations

- Die Menü-Uhrzeit ist die Client-Uhr beim Eintreffen der Antwort (kein Zeitstempel in der Antwort).
- Auf Staging wird der echte Versand nur für E-Mail und Telegram geprüft; SMS und Premium-SMS (Kosten seven.io) werden nur als Zeilen-/Sperrdarstellung und im Endpunkt-Test mit Transport-Fake an der Grenze abgesichert.
- E-Mail-Ziel zeigt nur die Konto-Adresse, keine Empfängerzahl; Telegram zeigt nur „verbunden“ (PO-Entscheidungen #3202).
- Zustand „Lücken“ braucht ein Prüfkonto mit fehlendem Telegram, unbestätigter SMS und verfallener Premium-Rückadresse (Seed auf Staging).
- Die Listen behalten den Dialog; das Menü gilt nur in den beiden Hubs.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (setzt ADR-0109 Punkt 6, ADR-0095, ADR-0097 und ADR-0118 um)
- **Rationale:** Struktur und Kanalparität sind bereits entschieden; die Ziel-Texte folgen den PO-Entscheidungen aus #3202. Keine neue Grundsatzentscheidung, nur Umsetzung mit einer Erweiterung des Handversand-Endpunkts um einen validierten Parameter.

## Changelog

- 2026-11-27: Initial spec created (Issue #3440, Scheibe S5a von #2797, Epic #2791)
- 2026-11-27: AC-10 präzisiert nach Adversary F001 (im Abo ausgeschalteter Kanal = übersprungen, nicht fehlgeschlagen)
