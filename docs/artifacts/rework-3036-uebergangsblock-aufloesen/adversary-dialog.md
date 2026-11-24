# Adversary Dialog — rework-3036-uebergangsblock-aufloesen
Spec: docs/specs/modules/rework_3036_uebergangsblock_aufloesen.md
Datum: 2026-11-24 22:01

## Checkliste
- [x] **Input:** Nutzer öffnet Trip-Hub, Reiter Wetter, Karte „Was steht wo“; schaltet einen der zwei neuen Blöcke um.
- [x] **Output:** Teilfeld-PUT mit genau diesem Feld; die nächste ausführliche Mail zeigt oder verbirgt den Block.
- [x] **Side effects:** Reiter Zustellung ohne Übergangsrahmen; Elementliste ohne Übergangsblock-Ausnahmen.
- [x] **AC-1:** Given ein Trip-Hub mit geöffnetem Reiter Wetter / When die Karte „Was steht wo“ unter „Ganze Blöcke ein- und ausschalten“ betrachtet wird / Then erscheinen zwei zusätzliche Schalter Kurz-Zusammenfassung und Großwetterlage (`was-steht-wo-show_compact_summary`, `was-steht-wo-show_stability`) mit dem Startwert aus der gespeicherten report_config (fehlendes Feld = an), und beim Orts-Vergleich sind sie nicht sichtbar.
- [x] **AC-2:** Given ein Trip mit gespeicherter report_config inkl. weiterer Felder / When der Nutzer einen der beiden neuen Schalter umlegt / Then wird nur das geänderte Feld per Teilfeld-PUT gespeichert, alle anderen report_config-Felder (auch die vier Altfelder) bleiben unverändert erhalten, und die Daten eines zweiten Nutzers bleiben unberührt.
- [x] **AC-3:** Given eine zugestellte ausführliche Trip-Mail / When Kurz-Zusammenfassung bzw. Großwetterlage ausgeschaltet ist / Then enthalten HTML- und Text-Teil der Mail den jeweiligen Block nicht, und bei eingeschaltetem Schalter enthalten sie ihn.
- [x] **AC-4:** Given ein Trip mit E-Mail-Format Kompakt / When die Karte „Was steht wo“ angezeigt wird / Then sind beide neuen Schalter gesperrt und zeigen den vorhandenen Hinweis „nur ausführlich“ wie die übrigen Block-Schalter.
- [x] **AC-5:** Given ein Trip mit gespeicherter oder fehlender report_config / When die Placements-GET `blocks` liefert / Then enthält die Antwort `show_compact_summary` und `show_stability` (fehlend = true).
- [x] **AC-6:** Given Sprache Deutsch oder Englisch am Nutzer / When die zwei neuen Schalter angezeigt werden / Then erscheinen Titel und Hinweis in der Nutzersprache aus dem i18n-Katalog (ADR-0104), ohne feste Texte in der Komponente.
- [x] **AC-7:** Given der Reiter Zustellung eines Trips oder Orts-Vergleichs / When er geöffnet wird / Then gibt es keinen Block „Vorübergehend hier“ mehr (testid `zustellung-uebergang` und Keys `zustellung.uebergang.*` entfallen), der Beispiel-Alarm steht als eigener Abschnitt am Ende (Trip und Orte), und die Pausieren/Aktivieren-Karte der Orte steht als fester Abschnitt direkt unter dem Kopf (Hub und Anlegen) und ist wie bisher bedienbar.
- [x] **AC-8:** Given der Teststand nach der Auflösung / When die Frontend-Tests laufen / Then fehlen die zwei veralteten E2E-Specs (`alarm-ab-nur-lesbar.spec.ts`, `s3a2794-zustellung-inventar-speicherweg.spec.ts`), und alle übrigen Tests mit früherem `zustellung-uebergang` laufen gegen die neuen testids grün.
- [x] **AC-9:** Given die Elementliste für den Reiter Zustellung / When der Abgleich `--scope zustellung --abnahme` mit dem Prüfkonto gegen Staging läuft / Then ist er für DE und EN grün, und `elementliste_besitzer.json` enthält keine Übergangsblock-Ausnahmen (#2795, art zusaetzlich, Grund „Übergangsblock …“) mehr.
- [x] **AC-10:** Given gespeicherte Werte von `show_quick_take_tags`, `show_metrics_summary`, `show_highlights`, `daily_summary_metrics` und SMS-Schwellen / When ein Nutzer im Hub Einstellungen ändert und speichert / Then erscheint dafür keine neue Oberfläche, und die gespeicherten Werte bleiben unverändert erhalten.

## Dialog

### Runde 1
**Adversary:**
Tests (benannte Dateien): 16 Frontend-Testdateien, 226 pass / 0 fail; pytest tests/tdd/test_rework_3036_placements_bloecke.py + tests/test_2913_c2_besitzerliste.py gruen; Golden-/Sprach-Tests (585) gruen. Ausgabe: docs/artifacts/rework-3036-uebergangsblock-aufloesen/adversary-test-output.txt. Go nicht installiert (go test nicht ausfuehrbar).

Mutations-Gegenprobe (String-Ersetzung, Sicherung im Scratchpad, danach per diff identisch):
- (a) Python blocks-Default true->false / None: rot (test_ac5_fehlend_heisst_an). GEFANGEN
- (b) felderNutzlast schreibt zusaetzliches Feld show_night_block: 3 rot; show_stability aus Nutzlast entfernt: 3 rot; felderAusAntwort fehlend=an -> ===true: 5 rot. GEFANGEN
- (c) disabled-Sperre entfernt: 2 rot; nurAusfuehrlich fest false: 2 rot; Hinweis ohne Zusatz: 2 rot. GEFANGEN
- (d) tripBloecke im Kontext vergleich true: 1 rot. GEFANGEN
- (e) Aktivierung nach BriefingZeiten statt davor: 3 rot. GEFANGEN
- (f) BeispielAlarm-Mount entfernt/auskommentiert: 11 bzw. 54 rot. GEFANGEN
- (g) ein Nicht-Uebergangsblock-Eintrag (#2795 Bewusste Abweichung) aus besitzer entfernt: test_ac12_eintraege_anderer_scheiben_unveraendert rot (Zaehlung 36). GEFANGEN
- Zusatz: Titel von show_stability auf kurz-Key vertauscht: 3 rot; EN-Text durch deutschen ersetzt: 2 rot. GEFANGEN
Wirkstelle: Placements-Go-Handler reicht blocks unveraendert durch (kein Filter in internal/handler/placements*.go); Renderer (trip_report.py:218, html.py:1276, plain.py:275) wertet beide Felder aus. Kein Finding.

Datenverlust: Teilfeld-Nutzlast enthaelt nur geaenderte Schluessel (wasStehtWoSpeicherung.ts:239); Go-Merge mergeConfigMap (internal/handler/config_merge.go:11) ist generisch, report_config bleibt offene Map (kein Feld-Whitelist fuer show_*); generischer Zwei-Nutzer-Roundtrip-Test existiert (internal/handler/report_config_roundtrip_test.go), aber keiner mit den zwei neuen Schluesseln und den vier Altfeldern -> LOW F001, Staging-Pruefung AC-2/AC-10 offen.
**Implementierer:**

### Runde 2
**Adversary:**
Nachbohren: (1) Elementliste: 282 Eintraege in `besitzer` (art zusaetzlich, Grund Uebergangsblock) entfernt, 0 andere; keine Resttexte mit Uebergangsblock/Voruebergehend; Zaehlung #2795 318->36 im Test nachgezogen. (2) AC-8: beide E2E-Specs (alarm-ab-nur-lesbar, s3a2794-zustellung-inventar-speicherweg) geloescht, kein Rest von zustellung-uebergang/UebergangBlock im Code ausser Verneinungs-Assertions und alten docs/context-Notizen. (3) RED-Test rework_3036_zustellung_ohne_uebergang.test.ts nur um Typ-Cast geaendert (keine Abschwaechung). (4) Nichts aus #3020-Umfang geloescht (WeatherMetricsTab, vtBriefingChannelsText, layout-tab unveraendert). (5) i18n DE/EN je vier Keys, Pin-Test ergaenzt. (6) Trip/Vergleich: ein Code, Kontext nur als Daten (KONTEXT-Tabelle, BEISPIEL-Record). Schwaeche LOW F002: Elementliste-Test prueft nur die Anzahl der #2795-Eintraege; ein Tausch (einer weg, ein Uebergangsblock-Eintrag zurueck) bliebe ungefangen. Keine Befunde, die blockieren.
**Implementierer:**

### Runde 3
**Adversary:**
Nachbesserung AC-9 (Staging-Befund Zustellung DE+EN, 17 Eintraege ohne Besitzer). Geprueft: docs/context/einstellungen_neu/elementliste_besitzer.json (+21 Eintraege, alle exakt: art element mit id bzw. zusaetzlich mit Klartext, kein muster/Wildcard; Reiter zustellung; ctx korrekt: Pausieren/Pause-Karte nur orte, Fertig/Finished nur trip, Orte/Locations Westfalen nur orte, Beispiel-Alarm und Vorschau ohne ctx, weil live in trip und orte) und tests/test_2913_c2_besitzerliste.py (#2797 8->16 mit neuem Test auf exakt 8 Texte DE/EN, #3009 2->11). Verweise tragfaehig: #2797 offen (Hub-Kopf nimmt Beispiel-Alarm/Pausieren auf), #3009 Kontodaten, #2913 Mockup-Beispieldaten. Kein versteckter Produktfehler: Kanalzeile zeigt gekuerzte Konto-Adresse (zustellungModell.ts:112-116, Format aus #3202), DE/EN-Paare vollstaendig (bestaetigt/confirmed). Bericht el2: DE und EN je 0 Eintraege und 0 Zusaetzlich-Texte ohne Besitzer (vorher je 7+10; gesamt 462 unveraendert, Besitzer ordnen nur zu).
Mutations-Gegenprobe (String-Ersetzung, Sicherung im Scratchpad, danach cmp identisch, gestagte Fassung unveraendert): M1 Example-warning-Text verfaelscht: rot (Python-Test 1 failed). M2 Pausieren ctx orte->trip: rot. M5 Kanal-id verfaelscht: rot (node 1 fail). M6 Verweis #3009->#2913: rot. M7 muster-Wildcard eingefuegt: rot. M3 Finished-Text verfaelscht: GRUEN (kein Test faengt). M4 ctx von Fertig entfernt: GRUEN. Ursache: die Zusicherung fuer #2913-Eintraege (Mockup-Beispieldaten) existiert nur als Staging-Abgleich, nicht im Kern-Test; gleiche Luecke wie bei den vorhandenen #2913-Eintraegen (Trips, Mallorca, Gespeichert).
**Implementierer:**

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Verdict

Code reference: src/services/placements_view_service.py:428
Code reference: frontend/src/lib/components/shared/wetter-tab/wasStehtWoSpeicherung.ts:239
Code reference: frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte:54
Code reference: frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte:109
Code reference: frontend/src/lib/components/organisms/zustellung-tab/BeispielAlarm.svelte:1
Code reference: frontend/playwright.2794-s3a2.staging.config.ts:4
Code reference: frontend/src/lib/i18n/messages/de/wetter.json:202
Code reference: frontend/src/lib/i18n/messages/en/wetter.json:202
Code reference: frontend/src/lib/i18n/messages/de/zustellung.json:67
Code reference: frontend/src/lib/i18n/messages/en/zustellung.json:67
Code reference: frontend/src/lib/i18n/__tests__/deutsch_unveraendert.test.ts:529
Code reference: frontend/e2e/s3b2795-zustellung.helpers.ts:68
Code reference: frontend/e2e/s3b2795-zustellung-uebergang.spec.ts:48
Code reference: frontend/e2e/was-steht-wo-karte.spec.ts:725
Code reference: frontend/e2e/versand-tab.spec.ts:128
Code reference: frontend/e2e/s3a2794-hub-reiter-wetter-zustellung.spec.ts:14
Code reference: docs/context/einstellungen_neu/elementliste_besitzer.json:1
Code reference: tests/test_2913_c2_besitzerliste.py:171

Finding: {"id":"F001","severity":"LOW","category":"edge_case","description":"Kein Go-Test fuer Teilfeld-PUT mit den neuen Schluesseln show_compact_summary/show_stability neben den vier Altfeldern; nur generischer Roundtrip","evidence":"internal/handler/report_config_roundtrip_test.go; internal/handler/config_merge.go:11","remediation":"Zwei-Nutzer-Staging-Pruefung AC-2/AC-10 in /e2e-verify"}
Finding: {"id":"F002","severity":"LOW","category":"anti_pattern","description":"Elementlisten-Test zaehlt nur #2795-Eintraege (36), prueft nicht auf Abwesenheit von Uebergangsblock-Texten","evidence":"tests/test_2913_c2_besitzerliste.py:171","remediation":"optional Assertion auf Abwesenheit"}
Finding: {"id":"F003","severity":"LOW","category":"anti_pattern","description":"Die neuen #2913-Besitzer (Fertig/Finished, Orte/Locations Westfalen) sind im Kern-Test nicht bewacht: Verfaelschung von Text bzw. ctx bleibt gruen; Schutz nur ueber Staging-Abgleich. Gleiche Luecke wie bei vorhandenen #2913-Eintraegen","evidence":"tests/test_2913_c2_besitzerliste.py:171; docs/context/einstellungen_neu/elementliste_besitzer.json:1","remediation":"optional: Soll-Menge fuer #2913-zusaetzlich-Texte wie ZUSTELLUNG_2797"}

Offen fuer Staging (kein Defekt): AC-3 Mail-Validator, AC-9 Elementlisten-Abgleich DE/EN (Runde 3: Bericht el2 DE/EN ohne Besitzer = 0, belegt), Zwei-Nutzer gegen Staging, Playwright-E2E.

VERDICT: VERIFIED

## Geprüfte Dateien

- sha256:3a88d5c6026145312b30fd03a3fe402688fcc8faadfebaa013b9b5ea971af9dd  docs/context/einstellungen_neu/elementliste_besitzer.json
- sha256:99a2fad43b21add0ef306c94e121b9c649fbac9ddedbef71b91aa30b7e93ac24  frontend/e2e/s3a2794-hub-reiter-wetter-zustellung.spec.ts
- sha256:e1b70c13d90da618e4bd50d513ae7dba232f561cbc369aa7cb24f5e47b95c71b  frontend/e2e/s3b2795-zustellung-uebergang.spec.ts
- sha256:aa4ba98b8f25960331edc523b048ad673735433ad60c81bd1f4da5b6b7182ce0  frontend/e2e/s3b2795-zustellung.helpers.ts
- sha256:0dacf8093e79574ad0d117cf0bf53bd09df08b393915a2a3df4614842582d0cc  frontend/e2e/versand-tab.spec.ts
- sha256:79358055ec75248b22cb2cfce09d7d0b81ac29bb45a8bccb64b98b9fea743a26  frontend/e2e/was-steht-wo-karte.spec.ts
- sha256:9b09246cba334f2169f65e6486dacf01d649604b0c0e484df3bc2892df0a5f0c  frontend/playwright.2794-s3a2.staging.config.ts
- sha256:f4e1a9f46ba947f0366cda88ebc3a73a1339ae912b2d71e3be6bf7a6bd3db077  frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte
- sha256:5b563b612f316caf2fb7b21f9eb88cbaf8a0cfc669080fbcf8e9e638618b4854  frontend/src/lib/components/organisms/zustellung-tab/BeispielAlarm.svelte
- sha256:6198d81cab1399e4f50da0b3a39e2325ada293ca56ea7e7aeeea4c669bdfb1e0  frontend/src/lib/components/shared/wetter-tab/wasStehtWoSpeicherung.ts
- sha256:a23e9b83d05dbec4c6e698ec8bc52ed1c51b0e1b817bfc4c1cf6f81c60723abd  frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte
- sha256:7209ca35852c0af45e7e9dca5aebe1d64e418036d713a792d72117f52822ec69  frontend/src/lib/i18n/__tests__/deutsch_unveraendert.test.ts
- sha256:03f255f0903a1f9820c67aa697d53923825f5fb945cfae5506558869571fe37b  frontend/src/lib/i18n/messages/de/wetter.json
- sha256:74f9e8ce40bb34131c76928eafca3e633b986cb5a8c4873b4628915d0e2dd58a  frontend/src/lib/i18n/messages/de/zustellung.json
- sha256:ad153af01770b4e9e5f93a3b0f4986a142bf853f22677f60025a275fa8063d8e  frontend/src/lib/i18n/messages/en/wetter.json
- sha256:1ecad8bdb08f1e22288a76f3c3e06fde10b7136963040cc7fc4d8785468f66ac  frontend/src/lib/i18n/messages/en/zustellung.json
- sha256:d197651b58e62d8369b54a6aa29ede55c97a40bb29ffc079f5c366edd106d726  src/services/placements_view_service.py
- sha256:9697db89a47e6c944dce3d8df414b971a3b503a60b61a78af617ec14d02aa063  tests/test_2913_c2_besitzerliste.py

## Prüfbasis

- base: 892ec5af70ef8aca2a256d1ec6f314135c5c8fe0
- blob:fe937547211880c9cd5038d74c256467dac2a9e0  docs/context/einstellungen_neu/elementliste_besitzer.json
- blob:ef2892ebc4b34e366138bfe25e4ba8e9673cb1de  frontend/e2e/s3a2794-hub-reiter-wetter-zustellung.spec.ts
- blob:17e1c793cd0814e3ee89021efee73bc0ca001080  frontend/e2e/s3b2795-zustellung-uebergang.spec.ts
- blob:e57072cb7725ebac4ac4715265adbc72dcf829b0  frontend/e2e/s3b2795-zustellung.helpers.ts
- blob:19719e57a8058544e30ea1d55a09eb4d3e84fd78  frontend/e2e/versand-tab.spec.ts
- blob:40ba93115a34e9ed188aff64ba5da14c8a8f6129  frontend/e2e/was-steht-wo-karte.spec.ts
- blob:1985e527f53e878d5490498e37a05179653b152f  frontend/playwright.2794-s3a2.staging.config.ts
- blob:5de7d923fd759ec8ee3add72948d8a789bde5964  frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte
- blob:a1ba6a8de8239b802074fac11d0fbcb1e1bdfeb1  frontend/src/lib/components/organisms/zustellung-tab/BeispielAlarm.svelte
- blob:79d286d862a535d6f7b825764bfc3730d7ecf1f3  frontend/src/lib/components/shared/wetter-tab/wasStehtWoSpeicherung.ts
- blob:5316769deda9b1071e6e57fbfcc81d14f6baed04  frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte
- blob:f367171612328428d5f910dc748e40cff333356c  frontend/src/lib/i18n/__tests__/deutsch_unveraendert.test.ts
- blob:4b4f4129ed58218ef30e80fb2294227d6d4e3e28  frontend/src/lib/i18n/messages/de/wetter.json
- blob:c021ef3696ccb2a6b588cf36fd668f5f1ae11142  frontend/src/lib/i18n/messages/de/zustellung.json
- blob:3ce7623b387836f0678606140210fbfaab27e45c  frontend/src/lib/i18n/messages/en/wetter.json
- blob:dd026ef58c7475142ba333db48d717b5e0e7fdc1  frontend/src/lib/i18n/messages/en/zustellung.json
- blob:6fe265d0a1dd6eb78db38ddc84aa8391f6099cdf  src/services/placements_view_service.py
- blob:1de4b53249e675650bc48ee9bd592190514c761a  tests/test_2913_c2_besitzerliste.py

## Geprüfte Dateien

- sha256:c466a6eb7641631afe4e335239dc11ec2ef815c977a51dbbc3d1237e8b521a15  docs/context/einstellungen_neu/elementliste_besitzer.json
- sha256:99a2fad43b21add0ef306c94e121b9c649fbac9ddedbef71b91aa30b7e93ac24  frontend/e2e/s3a2794-hub-reiter-wetter-zustellung.spec.ts
- sha256:e1b70c13d90da618e4bd50d513ae7dba232f561cbc369aa7cb24f5e47b95c71b  frontend/e2e/s3b2795-zustellung-uebergang.spec.ts
- sha256:aa4ba98b8f25960331edc523b048ad673735433ad60c81bd1f4da5b6b7182ce0  frontend/e2e/s3b2795-zustellung.helpers.ts
- sha256:0dacf8093e79574ad0d117cf0bf53bd09df08b393915a2a3df4614842582d0cc  frontend/e2e/versand-tab.spec.ts
- sha256:4c1cdb37b299c02469e0926c447f85847713b6dbc2a5ec27bced3428ab5eb6a5  frontend/e2e/was-steht-wo-karte.spec.ts
- sha256:9b09246cba334f2169f65e6486dacf01d649604b0c0e484df3bc2892df0a5f0c  frontend/playwright.2794-s3a2.staging.config.ts
- sha256:f4e1a9f46ba947f0366cda88ebc3a73a1339ae912b2d71e3be6bf7a6bd3db077  frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte
- sha256:5b563b612f316caf2fb7b21f9eb88cbaf8a0cfc669080fbcf8e9e638618b4854  frontend/src/lib/components/organisms/zustellung-tab/BeispielAlarm.svelte
- sha256:6198d81cab1399e4f50da0b3a39e2325ada293ca56ea7e7aeeea4c669bdfb1e0  frontend/src/lib/components/shared/wetter-tab/wasStehtWoSpeicherung.ts
- sha256:a23e9b83d05dbec4c6e698ec8bc52ed1c51b0e1b817bfc4c1cf6f81c60723abd  frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte
- sha256:7209ca35852c0af45e7e9dca5aebe1d64e418036d713a792d72117f52822ec69  frontend/src/lib/i18n/__tests__/deutsch_unveraendert.test.ts
- sha256:03f255f0903a1f9820c67aa697d53923825f5fb945cfae5506558869571fe37b  frontend/src/lib/i18n/messages/de/wetter.json
- sha256:74f9e8ce40bb34131c76928eafca3e633b986cb5a8c4873b4628915d0e2dd58a  frontend/src/lib/i18n/messages/de/zustellung.json
- sha256:ad153af01770b4e9e5f93a3b0f4986a142bf853f22677f60025a275fa8063d8e  frontend/src/lib/i18n/messages/en/wetter.json
- sha256:1ecad8bdb08f1e22288a76f3c3e06fde10b7136963040cc7fc4d8785468f66ac  frontend/src/lib/i18n/messages/en/zustellung.json
- sha256:d197651b58e62d8369b54a6aa29ede55c97a40bb29ffc079f5c366edd106d726  src/services/placements_view_service.py
- sha256:fc4b473095d549c25d2eb950605ca08f3130664fc7043cb1122e3cec170716b8  tests/test_2913_c2_besitzerliste.py

## Prüfbasis

- base: b69009d5d7abf99633afd4674c4b98e6d4cf6d93
- blob:6805ef5ea66395fd243592fefe5f76268c474469  docs/context/einstellungen_neu/elementliste_besitzer.json
- blob:ef2892ebc4b34e366138bfe25e4ba8e9673cb1de  frontend/e2e/s3a2794-hub-reiter-wetter-zustellung.spec.ts
- blob:17e1c793cd0814e3ee89021efee73bc0ca001080  frontend/e2e/s3b2795-zustellung-uebergang.spec.ts
- blob:e57072cb7725ebac4ac4715265adbc72dcf829b0  frontend/e2e/s3b2795-zustellung.helpers.ts
- blob:19719e57a8058544e30ea1d55a09eb4d3e84fd78  frontend/e2e/versand-tab.spec.ts
- blob:71fb7fe89a5bfda22c4e5d82f9f15cc2ed160c22  frontend/e2e/was-steht-wo-karte.spec.ts
- blob:1985e527f53e878d5490498e37a05179653b152f  frontend/playwright.2794-s3a2.staging.config.ts
- blob:5de7d923fd759ec8ee3add72948d8a789bde5964  frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte
- blob:a1ba6a8de8239b802074fac11d0fbcb1e1bdfeb1  frontend/src/lib/components/organisms/zustellung-tab/BeispielAlarm.svelte
- blob:79d286d862a535d6f7b825764bfc3730d7ecf1f3  frontend/src/lib/components/shared/wetter-tab/wasStehtWoSpeicherung.ts
- blob:5316769deda9b1071e6e57fbfcc81d14f6baed04  frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte
- blob:f367171612328428d5f910dc748e40cff333356c  frontend/src/lib/i18n/__tests__/deutsch_unveraendert.test.ts
- blob:4b4f4129ed58218ef30e80fb2294227d6d4e3e28  frontend/src/lib/i18n/messages/de/wetter.json
- blob:c021ef3696ccb2a6b588cf36fd668f5f1ae11142  frontend/src/lib/i18n/messages/de/zustellung.json
- blob:3ce7623b387836f0678606140210fbfaab27e45c  frontend/src/lib/i18n/messages/en/wetter.json
- blob:dd026ef58c7475142ba333db48d717b5e0e7fdc1  frontend/src/lib/i18n/messages/en/zustellung.json
- blob:6fe265d0a1dd6eb78db38ddc84aa8391f6099cdf  src/services/placements_view_service.py
- blob:94628bc40888aa8c916e2546dd638abd9fb999c9  tests/test_2913_c2_besitzerliste.py
