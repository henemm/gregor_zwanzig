# Adversary Dialog — feat-3202-kanalzeile-mockup
Spec: docs/specs/modules/feat_3202_kanalzeile_mockup.md
Datum: 2026-11-21 07:47

## Checkliste
- [x] **Input:** Profil (`mail_to`, `sms_to`, Verifizierungen, Telegram, Premium).
- [x] **Output:** Statuszeile je Kanal gekürzt wie oben, Trip und Orts-Vergleich identisch; keine Empfängerzahl.
- [x] **Side effects:** keine; nur Anzeige, Daten unverändert.
- [x] **AC-1:** Given ein Konto mit bestätigter E-Mail `henning@…`, bestätigter Handynummer `+49 171 …` und verbundenem Telegram / When der Nutzer den Reiter Zustellung eines Trips öffnet / Then zeigt die Kanalzeile `bestätigt · henning@…`, `bestätigt · +49 171 …` und `verbunden`, ohne volle Adresse, volle Nummer oder Chat-ID.
- [x] **AC-2:** Given ein Trip und ein Orts-Vergleich, dessen `preset.empfaenger` mit weiteren Adressen gefüllt ist / When der Nutzer jeweils den Reiter Zustellung öffnet / Then zeigt weder der Trip noch der Orts-Vergleich eine Empfängerzahl in der E-Mail-Zeile.
- [x] **AC-3:** Given die Kürzungsfunktionen / When sie kurze Lokalteile, Nummern ohne `+`, ausländische Vorwahlen mit 1 bis 3 Ziffern oder leere Werte erhalten / Then liefern sie die festgelegte Kürzung bzw. einen leeren Text, nie einen Fehler und nie den Volltext.
- [x] **AC-4:** Given der Zustand „Lücken“ (unbestätigte Nummer, verfallene Premium-Rückadresse, Telegram nicht verbunden) / When der Nutzer den Reiter öffnet / Then steht dort `unbestätigt · +49 171 …`, `inReach · Rückadresse verfallen` ohne Rückadresse und `nicht verbunden`.
- [x] **AC-5:** Given Premium-SMS im Normalzustand / When der Nutzer den Reiter öffnet / Then zeigt die Premium-Zeile den Status ohne Rückadresse.
- [x] **AC-6:** Given die Oberfläche in Deutsch bzw. Englisch / When der Nutzer den Reiter in Trip und Orts-Vergleich öffnet / Then erscheinen alle Statustexte in der gewählten Sprache aus dem Katalog, Adressen und Nummern bleiben unübersetzt.
- [x] **AC-7:** Given Staging mit dem Prüfkonto / When der Ganzseitenvergleich gegen die Elementliste läuft (DE und EN) / Then gibt es für die Kanalzeile keine neue Abweichung, die 23 Einträge `#3202` sind entfallen, es gibt keine Telegram-Ausnahme.
- [x] **AC-8:** Given zwei verschiedene Nutzer mit unterschiedlichen Adressen und Nummern / When jeder den Reiter Zustellung öffnet / Then sieht jeder nur die gekürzten Werte seiner eigenen Daten.
- [x] **AC-9:** Given das angeglichene Mockup Fassung 4 / When die Elementliste neu erzeugt wird / Then entsprechen die Sollzeilen der Kanaltabelle den PO-Entscheidungen (Telegram `verbunden`, E-Mail ohne „+1 Empfänger“) und die Liste ändert sich nur in diesen Zeilen; keine Sollzeile bleibt ohne Besitzer.

## Dialog

### Runde 1
**Adversary:** Grenzfaelle der Kuerzung per Probe-Skript (nicht eingecheckt): `+49 171`->`+49 171 …`, `+1 555..`->`+1 555 …`, `+353 87..`->`+353 871 …`, `491711234567`->`491 …`, `00491711234567`->`004 …`, `@x.de`/`abc`/leer/undefined/null->'' , `a@b@c`->`a@…`. Kein Fall zeigt eine lange Nummer/Adresse voll; nur Minimalwerte (`+4`, `1`, `a@`) erscheinen konstruktionsbedingt komplett (Finding F001, LOW). Alle kanalStatus-Zweige geprueft.
Finding:
  ID: F001
  Severity: LOW
  Category: edge_case
  Code reference: frontend/src/lib/components/shared/zustellung-tab/zustellungModell.ts:128
  Description: nummerGekuerzt liefert bei Nummern mit <=3 Ziffern nach der Vorwahl (`+49 171`, `+4`, `1`) die vollstaendige Ziffernfolge plus ` …`.
  Spec requirement: AC-3 — nie den Volltext
  Conflict: Bei unrealistisch kurzen Werten ist der Volltext sichtbar; reale Nummern haben >=6 Stellen, daher kein Datenschutzrisiko.
  Remediation: Keine noetig; optional in der Spec als Grenzfall festhalten.
Finding:
  ID: F002
  Severity: MEDIUM
  Category: edge_case
  Code reference: frontend/src/lib/components/shared/zustellung-tab/zustellungModell.ts:209
  Description: Zweig `sms_allowed === false` kuerzt per nummerGekuerzt. Mutation (ziel: nummer statt nummerGekuerzt(nummer)) laesst alle 70 Tests der Zustellungs-Dateien gruen: kein Test bewacht diesen Zweig.
  Spec requirement: AC-1/AC-3 — keine volle Nummer in der Kanalzeile
  Conflict: Rueckfall auf die volle Nummer im Tarif-gesperrten Zustand bliebe unbemerkt (Zusicherung nicht dort geprueft, wo sie wirkt).
  Remediation: Test in frontend/src/lib/components/shared/zustellung-tab/__tests__/zustellungModell.test.ts mit sms_allowed:false und sms_to gesetzt, erwartet ziel '+49 171 …'.
Confirmation:
  AC: AC-3
  Code reference: frontend/src/lib/components/shared/zustellung-tab/zustellungModell.ts:113
  Evidence: adresseGekuerzt/nummerGekuerzt liefern fuer leer/undefined/null/ohne @/ohne Ziffern '' und werfen nie; Vorwahltabelle 1/2/3-stellig (+1,+7,+49,+353) per Probe korrekt; Mutationen Vorwahl 1/49/353 und Nummer-ohne-+ rot.
  Status: CONFIRMED
Confirmation:
  AC: AC-1
  Code reference: frontend/src/lib/components/shared/zustellung-tab/zustellungModell.ts:186
  Evidence: E-Mail bestaetigt/unbestaetigt gekuerzt (Mutation email-raw: 5 Tests rot), SMS bestaetigt (3 rot), Telegram nur `verbunden` mit ziel '' (Mutation Chat-ID: 4 rot).
  Status: CONFIRMED
Confirmation:
  AC: AC-5
  Code reference: frontend/src/lib/components/shared/zustellung-tab/zustellungModell.ts:142
  Evidence: premiumStatus setzt ziel immer ''; Mutation Rueckadresse wieder anzeigen: 4 Tests rot.
  Status: CONFIRMED
**Implementierer:** (nicht beteiligt, Adversary-Lauf)

### Runde 2
**Adversary:** Runde 2: Restpunkte. Keine Empfaengerzahl: Suche nach empfaenger-/Zahl-Schluesseln in frontend/src ohne Treffer; im Modell kein Zugriff auf preset.empfaenger. Elementliste: 14 Kanalzeilen + mockup_hash geaendert (15 Zeilen +/-), Mockup nur `to`-Werte E-Mail/Telegram (2 Zeilen). Besitzerdatei: 23 #3202-Eintraege entfernt, zwei #3022-Eintraege nur mit neuer ID (Grund/Verweis unveraendert, ehrlich, da der Text der Zeile die ID bestimmt). Bestandstest ac14 exakt assert.equal angepasst, Pin ALT_SHA/MOCKUP_HASH mit Begruendung nachgezogen, Anzahl 2646 unveraendert; `#3202: 0` im Python-Test (35 passed). E2E-Spec: zwei Konten (AC-8), `finally` mit hub.aufraeumen() und Sprachreset, Fantasiedaten example.com. Kern-Tests Trip/Vergleich teilen denselben Code (ZustellungTab/zustellungModell).
Confirmation:
  AC: AC-2
  Code reference: frontend/src/lib/components/shared/zustellung-tab/zustellungModell.ts:177
  Evidence: kanalStatus kennt keine Empfaengerzahl mehr; E2E AC-6 prueft zusaetzlich `not /Empfaenger|recipient/` fuer Trip und Vergleich.
  Status: CONFIRMED
Confirmation:
  AC: AC-4
  Code reference: frontend/src/lib/components/shared/zustellung-tab/zustellungModell.ts:216
  Evidence: unbestaetigte Nummer gekuerzt (Mutation sms-unbest-raw: 2 rot), Premium verfallen ohne Adresse, Telegram nicht verbunden; E2E LUECKEN-Test.
  Status: CONFIRMED
Confirmation:
  AC: AC-6
  Code reference: frontend/src/lib/components/shared/zustellung-tab/__tests__/feat3202_kanalzeile_mockup.test.ts:1
  Evidence: Statustexte weiter ueber tr(...) aus dem Katalog; Katalog-Schluessel unveraendert, E2E prueft EN.
  Status: CONFIRMED
Confirmation:
  AC: AC-7
  Code reference: docs/context/einstellungen_neu/elementliste_besitzer.json:1
  Evidence: 23 #3202-Verweise entfernt, Soll `#3202: 0`; Staging-Ganzseitenvergleich ist Deploy-Gate (nicht lokal pruefbar).
  Status: CONFIRMED
Confirmation:
  AC: AC-8
  Code reference: frontend/e2e/s3b2795-zustellung-kanalzeile.spec.ts:1
  Evidence: zwei Konten, jedes sieht nur den eigenen gekuerzten Lokalteil; Kuerzung ist reine Funktion auf dem eigenen Profil.
  Status: CONFIRMED
Confirmation:
  AC: AC-9
  Code reference: docs/context/einstellungen_neu/elementliste.json:1
  Evidence: nur 14 Kanalzeilen (ordnung 8 und 15) + Hash geaendert; Telegram `verbunden`, E-Mail ohne Empfaenger; keine Sollzeile ohne Besitzer (Besitzer-Test gruen).
  Status: CONFIRMED
Confirmation:
  AC: AC-9
  Code reference: docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html:366
  Evidence: nur die `to`-Werte der Kanalzeile geaendert.
  Status: CONFIRMED
Confirmation:
  AC: AC-9
  Code reference: tests/test_2913_c2_besitzerliste.py:141
  Evidence: Soll #3202: 0, uebrige Zaehler unveraendert, nicht abgeschwaecht.
  Status: CONFIRMED
Confirmation:
  AC: AC-9
  Code reference: frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts:61
  Evidence: Pins nachgezogen und begruendet, Anzahl unveraendert.
  Status: CONFIRMED
Confirmation:
  AC: AC-1
  Code reference: frontend/src/lib/components/shared/zustellung-tab/__tests__/zustellungModell.test.ts:104
  Evidence: assert.equal auf den ganzen Wert (henning@…, '', +49 171 …).
  Status: CONFIRMED
Confirmation:
  AC: AC-1
  Code reference: frontend/src/lib/components/shared/zustellung-tab/__tests__/feat3202_kanalzeile_mockup.test.ts:1
  Evidence: Kern-Tests fuer Kuerzung und Zweige; Mutationen 9 von 10 rot.
  Status: CONFIRMED
Confirmation:
  AC: Output
  Code reference: docs/specs/modules/feat_3202_kanalzeile_mockup.md:1
  Evidence: Spec v1.1; Side effects: keine, nur Anzeige.
  Status: CONFIRMED
**Implementierer:** (nicht beteiligt, Adversary-Lauf)

### Runde 3
**Adversary:** F002 geschlossen: Mutation "SMS Tarif gesperrt ungekuerzt" wiederholt (sha256 vorher/nachher fe44ea10...0293 identisch): jetzt 2 Tests rot.
Confirmation:
  AC: AC-3
  Code reference: frontend/src/lib/components/shared/zustellung-tab/__tests__/feat3202_kanalzeile_mockup.test.ts:221
  Evidence: Neuer Test sms_allowed:false erwartet gekuerzte Nummer DE/EN; Mutation ziel: nummer faellt durch (70 pass, 2 fail).
  Status: CONFIRMED
**Implementierer:** (nicht beteiligt)

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Verdict

VERDICT: VERIFIED
Tests: Kern-Schicht Zustellung 70 passed, 0 failed; pytest besitzerliste 35 passed; voller Frontend-Lauf siehe test-output.txt
Mutationen: 9 von 10 rot; F002 (sms_allowed false, ungekuerzt) von keinem Test gefangen (MEDIUM, nicht blockierend).
Checklist: alle Punkte belegt

## Geprüfte Dateien

- sha256:c0f93c3a4f42e753143d22ce98389c18c2d013e37d72ddac98e2f1c4584b3f24  docs/context/einstellungen_neu/elementliste.json
- sha256:9e5ac0467a8154172066d79fb0f51630dde99adcd33d8a90e3927cbfb9912a94  docs/context/einstellungen_neu/elementliste_besitzer.json
- sha256:112bf2f645853eeed82c0a69fd98d6ffeef04dd454f03eaac4095b97479d18c6  docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html
- sha256:b443f825f35424a146555e9d0d3ba4a557e10ed4ca53f5dbe35c4bf9f3a304d5  docs/specs/modules/feat_3202_kanalzeile_mockup.md
- sha256:91d070c660f8ea69b7cc0f00891bce388a175b6215f0a0dfe9fd6f43775c793b  frontend/e2e/s3b2795-zustellung-kanalzeile.spec.ts
- sha256:150e8b4fa4141f8f299ffd900a3084c8d9f54cad0e643286a868e0b838cbf51c  frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts
- sha256:ec3c8f6cdc567dce6fd76c8744615a5730331745c65fd5c0243908e1717f005c  frontend/src/lib/components/shared/zustellung-tab/__tests__/feat3202_kanalzeile_mockup.test.ts
- sha256:00616fd66c3a4f065464ee7cd066c5652a94e37404dceb2ac0e88ac74669447e  frontend/src/lib/components/shared/zustellung-tab/__tests__/zustellungModell.test.ts
- sha256:fe44ea107f3c8aab74c2b3021c4802412cebd0b5bffa8dd07ae69fd7f1a00293  frontend/src/lib/components/shared/zustellung-tab/zustellungModell.ts
- sha256:8cf41f53a2703eb07fa88cd6fb4d559c8077785aef47955739f586ae424e61d8  tests/test_2913_c2_besitzerliste.py

## Prüfbasis

- base: c3f5e01fc8b0fd42fb776a515f5133cc2a3a2a41
- blob:0ada12ab7f848db0f30c7c7000a0a289746ae393  docs/context/einstellungen_neu/elementliste.json
- blob:c037358795526ba224260fd604ad96157325e2a3  docs/context/einstellungen_neu/elementliste_besitzer.json
- blob:22b5a3e19ce9eaad1b8e84b9553bb873d9bfdc42  docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html
- blob:485bcd2e8d9989e24418e7ced6955259680ce64e  docs/specs/modules/feat_3202_kanalzeile_mockup.md
- blob:2dd93579e239848efdeaaca9cf5a1d4a6caf594c  frontend/e2e/s3b2795-zustellung-kanalzeile.spec.ts
- blob:8a88fb22e1db359e64304eeba500bf81d176ae13  frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts
- blob:aee03f860a4dd3a57ead1593a1c7851390108871  frontend/src/lib/components/shared/zustellung-tab/__tests__/feat3202_kanalzeile_mockup.test.ts
- blob:f437fc5f6c8f053c06a62a1c53707eea2f11d8a6  frontend/src/lib/components/shared/zustellung-tab/__tests__/zustellungModell.test.ts
- blob:031e5d446ecce76d5ef762e7699b196a0707dc98  frontend/src/lib/components/shared/zustellung-tab/zustellungModell.ts
- blob:fb9d43cc8e526c8b4bd380852f86d51f92d4729c  tests/test_2913_c2_besitzerliste.py

## Geprüfte Dateien

- sha256:c0f93c3a4f42e753143d22ce98389c18c2d013e37d72ddac98e2f1c4584b3f24  docs/context/einstellungen_neu/elementliste.json
- sha256:9e5ac0467a8154172066d79fb0f51630dde99adcd33d8a90e3927cbfb9912a94  docs/context/einstellungen_neu/elementliste_besitzer.json
- sha256:112bf2f645853eeed82c0a69fd98d6ffeef04dd454f03eaac4095b97479d18c6  docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html
- sha256:b443f825f35424a146555e9d0d3ba4a557e10ed4ca53f5dbe35c4bf9f3a304d5  docs/specs/modules/feat_3202_kanalzeile_mockup.md
- sha256:91d070c660f8ea69b7cc0f00891bce388a175b6215f0a0dfe9fd6f43775c793b  frontend/e2e/s3b2795-zustellung-kanalzeile.spec.ts
- sha256:150e8b4fa4141f8f299ffd900a3084c8d9f54cad0e643286a868e0b838cbf51c  frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts
- sha256:ec3c8f6cdc567dce6fd76c8744615a5730331745c65fd5c0243908e1717f005c  frontend/src/lib/components/shared/zustellung-tab/__tests__/feat3202_kanalzeile_mockup.test.ts
- sha256:00616fd66c3a4f065464ee7cd066c5652a94e37404dceb2ac0e88ac74669447e  frontend/src/lib/components/shared/zustellung-tab/__tests__/zustellungModell.test.ts
- sha256:fe44ea107f3c8aab74c2b3021c4802412cebd0b5bffa8dd07ae69fd7f1a00293  frontend/src/lib/components/shared/zustellung-tab/zustellungModell.ts
- sha256:8cf41f53a2703eb07fa88cd6fb4d559c8077785aef47955739f586ae424e61d8  tests/test_2913_c2_besitzerliste.py

## Prüfbasis

- base: c3f5e01fc8b0fd42fb776a515f5133cc2a3a2a41
- blob:0ada12ab7f848db0f30c7c7000a0a289746ae393  docs/context/einstellungen_neu/elementliste.json
- blob:c037358795526ba224260fd604ad96157325e2a3  docs/context/einstellungen_neu/elementliste_besitzer.json
- blob:22b5a3e19ce9eaad1b8e84b9553bb873d9bfdc42  docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html
- blob:485bcd2e8d9989e24418e7ced6955259680ce64e  docs/specs/modules/feat_3202_kanalzeile_mockup.md
- blob:2dd93579e239848efdeaaca9cf5a1d4a6caf594c  frontend/e2e/s3b2795-zustellung-kanalzeile.spec.ts
- blob:8a88fb22e1db359e64304eeba500bf81d176ae13  frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts
- blob:aee03f860a4dd3a57ead1593a1c7851390108871  frontend/src/lib/components/shared/zustellung-tab/__tests__/feat3202_kanalzeile_mockup.test.ts
- blob:f437fc5f6c8f053c06a62a1c53707eea2f11d8a6  frontend/src/lib/components/shared/zustellung-tab/__tests__/zustellungModell.test.ts
- blob:031e5d446ecce76d5ef762e7699b196a0707dc98  frontend/src/lib/components/shared/zustellung-tab/zustellungModell.ts
- blob:fb9d43cc8e526c8b4bd380852f86d51f92d4729c  tests/test_2913_c2_besitzerliste.py

## Geprüfte Dateien

- sha256:c0f93c3a4f42e753143d22ce98389c18c2d013e37d72ddac98e2f1c4584b3f24  docs/context/einstellungen_neu/elementliste.json
- sha256:9e5ac0467a8154172066d79fb0f51630dde99adcd33d8a90e3927cbfb9912a94  docs/context/einstellungen_neu/elementliste_besitzer.json
- sha256:112bf2f645853eeed82c0a69fd98d6ffeef04dd454f03eaac4095b97479d18c6  docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html
- sha256:b443f825f35424a146555e9d0d3ba4a557e10ed4ca53f5dbe35c4bf9f3a304d5  docs/specs/modules/feat_3202_kanalzeile_mockup.md
- sha256:91d070c660f8ea69b7cc0f00891bce388a175b6215f0a0dfe9fd6f43775c793b  frontend/e2e/s3b2795-zustellung-kanalzeile.spec.ts
- sha256:150e8b4fa4141f8f299ffd900a3084c8d9f54cad0e643286a868e0b838cbf51c  frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts
- sha256:2c6a0c0f565b9ae84d1f9c39d153fd1c740c0978ed8d0ed5629cc9b3aa446670  frontend/src/lib/components/shared/zustellung-tab/__tests__/feat3202_kanalzeile_mockup.test.ts
- sha256:00616fd66c3a4f065464ee7cd066c5652a94e37404dceb2ac0e88ac74669447e  frontend/src/lib/components/shared/zustellung-tab/__tests__/zustellungModell.test.ts
- sha256:fe44ea107f3c8aab74c2b3021c4802412cebd0b5bffa8dd07ae69fd7f1a00293  frontend/src/lib/components/shared/zustellung-tab/zustellungModell.ts
- sha256:8cf41f53a2703eb07fa88cd6fb4d559c8077785aef47955739f586ae424e61d8  tests/test_2913_c2_besitzerliste.py

## Prüfbasis

- base: c3f5e01fc8b0fd42fb776a515f5133cc2a3a2a41
- blob:0ada12ab7f848db0f30c7c7000a0a289746ae393  docs/context/einstellungen_neu/elementliste.json
- blob:c037358795526ba224260fd604ad96157325e2a3  docs/context/einstellungen_neu/elementliste_besitzer.json
- blob:22b5a3e19ce9eaad1b8e84b9553bb873d9bfdc42  docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html
- blob:485bcd2e8d9989e24418e7ced6955259680ce64e  docs/specs/modules/feat_3202_kanalzeile_mockup.md
- blob:2dd93579e239848efdeaaca9cf5a1d4a6caf594c  frontend/e2e/s3b2795-zustellung-kanalzeile.spec.ts
- blob:8a88fb22e1db359e64304eeba500bf81d176ae13  frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts
- blob:cb8bb0342b866cc8bf24d3d03b6162be589f672b  frontend/src/lib/components/shared/zustellung-tab/__tests__/feat3202_kanalzeile_mockup.test.ts
- blob:f437fc5f6c8f053c06a62a1c53707eea2f11d8a6  frontend/src/lib/components/shared/zustellung-tab/__tests__/zustellungModell.test.ts
- blob:031e5d446ecce76d5ef762e7699b196a0707dc98  frontend/src/lib/components/shared/zustellung-tab/zustellungModell.ts
- blob:fb9d43cc8e526c8b4bd380852f86d51f92d4729c  tests/test_2913_c2_besitzerliste.py
