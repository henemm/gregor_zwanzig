# Adversary Dialog — feat-3190-vorlage-dialog-inline
Spec: docs/specs/modules/feat_3190_vorlage_dialog_inline.md
Datum: 2026-11-20 13:16

## Checkliste
- [x] **Input:** Klick auf „Als eigene Vorlage speichern“ im Reiter Wetter (Trip oder Orts-Vergleich).
- [x] **Output:** Karte mit Titel, Name, ggf. Fehlerzeile, Beschreibung, Ankreuzfeld, Hinweis, Speichern, Abbrechen erscheint unter der Vorlage-Karte; zweiter Klick auf den Knopf schließt sie.
- [x] **Side effects:** Speichern legt wie bisher eine eigene Vorlage an (inkl. #3189-Herkunft); Metrik-Karte rutscht beim Öffnen nach unten (bewusst, Mockup-Verhalten).
- [x] **AC-1:** Given der Reiter Wetter eines Trips ist offen / When der Nutzer „Als eigene Vorlage speichern“ klickt / Then erscheint direkt unter der Vorlage-Karte und vor der Metrik-Karte eine Karte ohne abdunkelnden Hintergrund und ohne Schließen-Kreuz, und ein zweiter Klick auf denselben Knopf schließt sie wieder.
- [x] **AC-2:** Given der Reiter Wetter eines Orts-Vergleichs / When der Nutzer die Karte öffnet / Then sieht er dieselbe Karte mit „Als Standard für neue Orte“, bei Trips „Als Standard für neue Trips“.
- [x] **AC-3:** Given die Karte ist offen / When der Nutzer sie von oben nach unten liest / Then folgt: Titel, Feld Name, Fehlerzeile direkt unter Name, Beschreibung (einzeilig), Ankreuzfeld, Hinweistext, Speichern, Abbrechen.
- [x] **AC-4:** Given die Karte ist offen und der Name ist leer / When der Nutzer „Speichern“ klickt / Then erscheint die Pflicht-Fehlermeldung direkt unter dem Namensfeld, nichts wird gespeichert, und bei bereits vergebenem Namen erscheint die Duplikat-Meldung.
- [x] **AC-5:** Given ein gültiger Name / When der Nutzer Beschreibung und Ankreuzfeld ausfüllt und „Speichern“ klickt / Then schließt die Karte, die Meldung „Vorlage gespeichert“ erscheint, die Vorlage ist unter „Eigene“ mit Herkunft „aus <Name> gespeichert“ (#3189) und, wenn angekreuzt, als Standard vorhanden.
- [x] **AC-6:** Given die Karte ist offen / When der Nutzer „Abbrechen“ klickt oder Escape drückt, solange der Fokus in der Karte liegt / Then schließt sie ohne zu speichern und der Fokus liegt wieder auf dem Knopf „Als eigene Vorlage speichern“.
- [x] **AC-7:** Given die Vorlagen-Auswahl (Picker) ist geöffnet / When der Nutzer Escape drückt / Then schließt nur die Auswahl; eine offene Speichern-Karte bleibt unberührt, solange der Fokus nicht in ihr liegt.
- [x] **AC-8:** Given der Nutzer arbeitet nur mit Tastatur und Screenreader / When er die Karte öffnet / Then steht der Fokus im Namensfeld, die Karte ist als Gruppe mit Titel benannt, Ankreuzfeld und Fehlermeldung haben zugängliche Namen, und alle Bedienziele sind mindestens 44 px hoch.
- [x] **AC-9:** Given die Sprache des Nutzers ist Deutsch oder Englisch / When die Karte offen ist / Then stehen alle Texte, Platzhalter und der Hinweis unverändert aus dem Katalog (DE und EN), ohne neuen oder hartkodierten Text.
- [x] **AC-10:** Given der Alt-Editor (Anlegen eines Trips, Bereich Zustellung) mit sichtbarer Profil-Karte / When dort „Als eigene Vorlage speichern“ ausgelöst wird / Then erscheint dieselbe Karte unter der Profil-Karte, nicht am Seitenende, und Speichern/Abbrechen funktionieren wie im Reiter Wetter.
- [x] **AC-11:** Given die Elementliste und deren Abgleich gegen Staging / When der Abgleich den Abschnitt „Vorlage speichern“ samt Fehlerzustand bedient und liest / Then stimmen alle Texte weiterhin überein und die Karte wird danach wieder geschlossen.
- [x] **AC-12:** Given #3192 (AC-8) und die Herkunftsanzeige aus #3189 / When die Karte genutzt wird / Then bleiben beide Verhalten unverändert.

## Dialog

### Runde 1
**Adversary:** Spec-ACs gegen Code gelesen. (1) spd-* in app.css: Regel (a) verbietet nur eigenes <style> im Seiten-Scope, Tokens only, Scrim-Ausnahme entfernt: Umgehung nein, konsistent. (2) ampelSchreiben.ts: reine Logik ohne Markup, wetter-tab-Organismus nutzt sie ebenso: begruendet, enge Einzelausnahme. (3) Goldens: Wort-Diff zeigt nur Dialog-Block. (4) Bedienplan: Lesen unveraendert, nur Schliessen-Weg; Escape-Pfad in s3a-E2E. (5) Alt-Editor ohne Fokus-Rueckgabe: F001. (6) a11y ok per SSR. (7) kind-Prop statt context-Zweig, Katalog unveraendert.
**Implementierer:** keine Antwort (Prueflauf).

### Runde 2
**Adversary:** Mutationen (Sicherung im Scratchpad, sha vorher/nachher identisch): role=dialog zurueck (Treffer: 5 rot, nach korrekter Anwendung; erster Lauf traf nur Kommentarzeile), Beschriftung am Haken entfernt (4 rot), aria-expanded entfernt (4 rot), aria-describedby entfernt (1 rot), Fehlerzeile entfernt (1 rot). Ueberlebt lokal: Fokus ins Namensfeld, Escape stopPropagation, Picker-Guard, Alt-Editor-Trigger, Haken min-height: nur Staging-E2E (F002).
**Implementierer:** keine Antwort (Prueflauf).

### Runde 3
**Adversary:** Fix-Loop 1 geprüft. F001: geteilte Logik vorlageSpeichernKarte.ts, Alt-Editor hat Umschalter, aria-expanded/aria-controls an der PresetBar, Fokus-Rückgabe bei Close und Saved: behoben. F003: Escape-Guard `karteSchliesstPerTaste` behoben (stopPropagation bleibt, Picker-Escape unberührt). Zeilen-Zusammenziehen in WeatherMetricsTab.svelte: keine Wächter-Umgehung, der Wächter prüft weiter Text der Zeile und seine Nummer wurde zusätzlich 2005→2008 nachgeführt (context_herkunft_zweige_eingefroren.test.ts:268/418), nur Stilfrage (LOW, F004: zwei Anweisungen pro Zeile). Goldens: nur Auslöser-Attribute + Dialogblock. Mutationen (sha identisch): aria-expanded an PresetBar weg: 4 rot; Lib-Guard saving weg: 1 rot; Lib-zurueck weg: 2 rot; Lib-toggle: 1 rot. ÜBERLEBT: Fokus-Rückgabe im Alt-Editor weg (onClose/onSaved in WeatherMetricsTab) und saving-Guard-Aufruf in SavePresetDialog.taste durch `close()` ersetzt: nur die reinen Funktionen sind getestet, nicht die Verdrahtung (F002 bleibt für diese Stellen, LOW, nur Staging-E2E).
**Implementierer:** keine Antwort (Prüflauf).

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Verdict

Confirmation: AC-1/AC-2/AC-3/AC-4
  Code reference: frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte:109
  Evidence: Wurzel div role=group ohne Scrim/x; Reihenfolge Titel(118), Name(121), Fehler(133), Beschreibung(139), Haken(150), Hinweis(159), Speichern vor Abbrechen(163-164); Standard-Text je kind (50). SSR-Tests + Mutation role=dialog rot.
  Status: CONFIRMED

Confirmation: AC-1 (Platz, Umschalter)
  Code reference: frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte:156
  Evidence: aria-expanded/aria-controls, umschalten() toggelt, Karte direkt nach der Vorlage-Karte (169). Mutation ohne aria-expanded: 4 Tests rot.
  Status: CONFIRMED

Confirmation: AC-5/AC-12
  Code reference: frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte:86
  Evidence: Payload unveraendert ueber eigeneVorlagePayload mit herkunft (#3189), onSaved dann open=false.
  Status: CONFIRMED

Confirmation: AC-6/AC-7
  Code reference: frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte:100
  Evidence: Escape-Handler sitzt auf der Karte (Fokus-gebunden), stopPropagation; Picker-Escape in VorlageKarte.svelte:93 ohne dialogOffen-Bedingung; Fokus-Rueckgabe dialogZu/gespeichertMelden. Nur per Staging-E2E pruefbar, lokal Mutation ueberlebt (siehe F002).
  Status: CONFIRMED (Trip/Vergleich)

Confirmation: AC-8
  Code reference: frontend/src/lib/components/atoms/Haken.svelte:72
  Evidence: label.hk-beschriftet min-height --g-tap-min, Text benennt Kaestchen (kein aria-label), Input min-height tap (app.css .spd-feld), Fehler aria-describedby (SPD:131).
  Status: CONFIRMED (Tippflaeche nur per E2E gemessen)

Confirmation: AC-9
  Code reference: frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte:118
  Evidence: alle Texte ueber $t/tr aus wetter.dialog.*; keine Katalogaenderung im Diff, keine context-Zweige (nur kind-Prop).
  Status: CONFIRMED

Confirmation: AC-11 (Elementliste)
  Code reference: frontend/e2e/elementliste_abgleich_logik.ts:437
  Evidence: Plan klickt Abbrechen statt Escape; lesen-Schritt unveraendert, Tests bedienplan.test.ts ergaenzt (zwei Plaene). Abdeckung des Textlesens unveraendert; Escape-Weg ist durch s3a-E2E abgedeckt.
  Status: CONFIRMED

Confirmation: Wachter / E2E / Altbestand
  Code reference: frontend/src/lib/__tests__/bausteine_waechter_regeln.ts:510
  Evidence: SavePresetDialog von BESTAND nach SEITEN_SCOPE (strenger, Obergrenze 197->196); ampelSchreiben.ts als reine Logik freigegeben (rein, kein Markup). Gold: nur Dialog-Markup getauscht (word-diff). Weitere gelesene Dateien:
  Status: CONFIRMED

Confirmation: Dateien
  Code reference: frontend/src/app.css:1011
  Evidence: spd-* nur mit Tokens, Regel (a) verbietet nur <style> im Seiten-Scope; keine harten Farben, harte_farben_waechter Ausnahme (Scrim) entfernt.
  Status: CONFIRMED

Confirmation: Dateien 2
  Code reference: frontend/src/lib/components/shared/WeatherMetricsTab.svelte:1710
  Evidence: Karte unter Profil-Karte (AC-10 Position).
  Status: CONFIRMED

Confirmation: E2E-Specs
  Code reference: frontend/e2e/elementliste-abgleich.staging.spec.ts:353
  Evidence: nur Kommentar; Escape-Taste weiterhin fuer Picker.
  Status: CONFIRMED

Confirmation: E2E-Specs 2
  Code reference: frontend/e2e/s3a2794-teil3-design.spec.ts:117
  Evidence: natives-Control-Pruefung nimmt Haken-Atom aus (Haken ist selbst ein Baustein); AC-40 bleibt fuer Rest; Zusatz 44px-Pruefung.
  Status: CONFIRMED

Confirmation: E2E-Specs 3
  Code reference: frontend/e2e/s3a2794-teil3-dialog.spec.ts:5
  Evidence: nur Kommentar.
  Status: CONFIRMED

Confirmation: Tests
  Code reference: frontend/src/lib/__tests__/elementliste_abgleich_bedienplan.test.ts:202
  Evidence: neuer Plan getestet.
  Status: CONFIRMED

Confirmation: Tests 2
  Code reference: frontend/src/lib/__tests__/elementliste_abgleich_verdrahtung.test.ts:501
  Evidence: nur Kommentar angepasst, Regex unveraendert.
  Status: CONFIRMED

Confirmation: Tests 3
  Code reference: frontend/src/lib/__tests__/harte_farben_waechter.test.ts:69
  Evidence: Scrim-Ausnahme entfernt, passt zur Datei ohne Scrim.
  Status: CONFIRMED

Confirmation: Tests 4
  Code reference: frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts:268
  Evidence: Zeilenverschiebung 1990->2005, Bedingung unveraendert.
  Status: CONFIRMED

Confirmation: Tests 5
  Code reference: frontend/src/lib/components/shared/weather-metrics-tab/__tests__/wertebereiche_sprache.test.ts:208
  Evidence: "Close" faellt weg, korrekt (Kreuz entfernt).
  Status: CONFIRMED

Confirmation: Golden
  Code reference: tests/golden/f5_wertebereiche/route_voll.de.html:1
  Evidence: Wort-Diff: nur Dialog-Block (Scrim->Karte). Gleiches fuer bausteine/route_telegram/route_sms_schwellen_fehler de/en (tests/golden/f5_wertebereiche/bausteine.de.html:1, bausteine.en.html:1, route_sms_schwellen_fehler.de.html:1, route_sms_schwellen_fehler.en.html:1, route_telegram.de.html:1, route_telegram.en.html:1, route_voll.en.html:1).
  Status: CONFIRMED

Confirmation: Spec-Doku
  Code reference: docs/specs/modules/rework_2276_s6h_ac2_endbilanz.md:113
  Evidence: nur Zeilennummer 1990->2005.
  Status: CONFIRMED

Finding:
  ID: F001
  Severity: MEDIUM
  Category: spec_violation
  Code reference: frontend/src/lib/components/shared/WeatherMetricsTab.svelte:1706
  Description: Alt-Editor oeffnet die Karte nur per `showSavePresetDialog = true` und schliesst per onClose ohne Fokus-Rueckgabe; Ausloeser (WeatherV2PresetBar.svelte:61) hat weder aria-expanded noch Umschalter.
  Spec requirement: AC-10 — Speichern/Abbrechen funktionieren wie im Reiter Wetter (AC-6 Fokus zurueck, AC-1 zweiter Klick schliesst)
  Conflict: Nach Abbrechen/Escape im Alt-Editor geht der Fokus verloren (Karte verschwindet, Fokus auf body); kein Test (nur Position getestet, AC-10 ohne Verhaltenspruefung).
  Remediation: Ausloeser-Referenz merken und in onClose/onPresetSaved fokussieren, aria-expanded ergaenzen, oder AC-10 in der Spec auf Position beschraenken (Spec nennt zudem Bereich Zustellung, die Karte rendert nur bei grundauswahl).

Finding:
  ID: F002
  Severity: LOW
  Category: edge_case
  Code reference: frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte:62
  Description: Fokus-ins-Namensfeld, Escape-/Picker-Escape-Logik, Fokus-Rueckgabe und Haken-Tippflaeche (44px) sind lokal ungetestet: Mutationen (nameFeld?.focus entfernt, stopPropagation entfernt, Picker-Guard zurueck, min-height 0) ueberleben die Core-Tests; nur Staging-Spec s3a2794-teil3-vorlage-inline.spec.ts bewacht sie (lief nicht lokal).
  Spec requirement: AC-6/AC-7/AC-8
  Conflict: Zusicherung wirkt im Browser, geprueft nur in nachgelagerter Schicht.
  Remediation: vor Deploy Staging-E2E zwingend gruen sehen.

Finding:
  ID: F003
  Severity: LOW
  Category: edge_case
  Code reference: frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte:99
  Description: Escape waehrend saving=true schliesst und reset() die Karte mitten im POST; Abbrechen ist dann disabled, Escape nicht.
  Spec requirement: AC-6
  Conflict: Inkonsistenz Abbrechen (disabled) vs. Escape; Ergebnis des POST geht trotzdem durch, onSaved ruft dann Meldung.
  Remediation: in taste() bei saving nichts tun.

Tests: 8286 passed, 0 failed, 3 übersprungen (Core-Schicht frontend node --test; Staging-E2E nicht lokal ausführbar)

═══════════════════════════════════════
Zwischenstand Runde 2 (ueberholt): AMBIGUOUS
═══════════════════════════════════════
Ambiguous findings (require human review):
  F001: Alt-Editor ohne Fokus-Rückgabe/Umschalter — AC-10 "wie im Reiter Wetter" unklar, ob AC-6 gemeint; Spec nennt zudem Bereich Zustellung, Karte rendert nur bei grundauswahl
Weitere: F002 (LOW, nur Staging-E2E bewacht Fokus/Escape/44px), F003 (LOW, Escape während Speichern)
Proven points: 11/12 (AC-10 teilweise)

## Geprüfte Dateien

- sha256:af03f4963a6cd2a43bf352fd9b1b9d59b873f94ad7ad1d918bb65739a5be52bf  docs/specs/modules/rework_2276_s6h_ac2_endbilanz.md
- sha256:ac45dd1da9919f7c46ba08f3cf611a0ab5e5841e29d7101b2c2e4677eeeec5d4  frontend/e2e/elementliste-abgleich.staging.spec.ts
- sha256:12b9a7f12c90b77df35967a0da8e238223ac4a57d52e8f1b8820b542d11baea6  frontend/e2e/elementliste_abgleich_logik.ts
- sha256:b9f2dcaa55a4d3779b92436f7fc7f18e67f665be7c19ca13f5183621af2fe799  frontend/e2e/s3a2794-teil3-design.spec.ts
- sha256:acedbde36bd29912cab45b29b107657a734c3b36b1daf115e20fc7d806a69efd  frontend/e2e/s3a2794-teil3-dialog.spec.ts
- sha256:a675f3ed9e758a866e3e63c9a2c7e31b56890d363007fa32f325ceeaf7f24ec4  frontend/src/app.css
- sha256:96f4acf957622303307705a989148d4cac4a840a90ff4995ca4b91b6e4d3ec6d  frontend/src/lib/__tests__/bausteine_waechter_regeln.ts
- sha256:92b7402dce9eeb489cb014a2a1a2a37a97e0141337d78f0bd45ddbcfb5b460a4  frontend/src/lib/__tests__/elementliste_abgleich_bedienplan.test.ts
- sha256:806c940525ca8482bae365ad804a936647e0230a4f04ba9bb9f541342e53fc7a  frontend/src/lib/__tests__/elementliste_abgleich_verdrahtung.test.ts
- sha256:aaeaead8d0e4b9c7a9761acd9a0da177b4342f7511ab3d0ccb6c20fc0a7bd76f  frontend/src/lib/__tests__/harte_farben_waechter.test.ts
- sha256:9c284c023707b163a2f10e1951fb6c6d34b5403db285d55cd61ece97b3e45cd1  frontend/src/lib/components/atoms/Haken.svelte
- sha256:df7a5030ebefc05af8580b18c992598c07e8540f0bf003216c2f44cdc004c945  frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte
- sha256:7843f14e08e96f5d4b035b8755dbdb6a3d217a0d2f4e4e5097c6db098377b586  frontend/src/lib/components/shared/WeatherMetricsTab.svelte
- sha256:3939821c97725c4578bcd4a57eb7252568ba18b4f1dae02eb4ac919785a6566f  frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts
- sha256:598b222a749784117e9747840a282e94cd7f699ef3527f3fa3ef91bb5bce0dfe  frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte
- sha256:9c9423d3b7c97911b8bdf8a1bdc433e8a4a8b156db996c5e709210796dfa985b  frontend/src/lib/components/shared/weather-metrics-tab/__tests__/wertebereiche_sprache.test.ts
- sha256:07172247ac4fa4a713718d3e476ec74614487dda4fc249fee4839d5e578a7f6f  tests/golden/f5_wertebereiche/route_voll.de.html

## Prüfbasis

- base: ac1fd478bed6e85df0529954928097e3f8a172c5
- blob:9c65c720b6206cf200fad27c1a995ca8125e67e7  docs/specs/modules/rework_2276_s6h_ac2_endbilanz.md
- blob:21626913992de16d316d67424c11abb10351912d  frontend/e2e/elementliste-abgleich.staging.spec.ts
- blob:33ecac7e74cd4d5766506cd526c7999e39389c1c  frontend/e2e/elementliste_abgleich_logik.ts
- blob:0ba71267581e7977d7ae3e74f24b44f518ffc7cc  frontend/e2e/s3a2794-teil3-design.spec.ts
- blob:db97429cfae9e1eddd7c2229bcc16c6c2f4c61b4  frontend/e2e/s3a2794-teil3-dialog.spec.ts
- blob:5b6d10357f6e54d813ff3202824fa9ff23bf8a3a  frontend/src/app.css
- blob:e27d3a2aa8a90bbc19f86b8a773e484c1568906d  frontend/src/lib/__tests__/bausteine_waechter_regeln.ts
- blob:a1415faf43451f543415a95f84a79b9f2b97d02e  frontend/src/lib/__tests__/elementliste_abgleich_bedienplan.test.ts
- blob:2f1cd46f4dcf2937d4aff5a082e1f108c3f05818  frontend/src/lib/__tests__/elementliste_abgleich_verdrahtung.test.ts
- blob:442991f81913eae0c2d2b4fa5f2d236d81a68079  frontend/src/lib/__tests__/harte_farben_waechter.test.ts
- blob:462ce8e8a4e4f334298c481ba58d2862e65b6850  frontend/src/lib/components/atoms/Haken.svelte
- blob:78e49cfd2cfbc667e139bbea2d54b39b2f4dbe32  frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte
- blob:b143365f83bb73b41bc656ecb39114332f56e842  frontend/src/lib/components/shared/WeatherMetricsTab.svelte
- blob:8786f8d8cd1b2fbf124dacd7ebd67c51fa4a695a  frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts
- blob:78dc0c1d118a34e2ea2606ff0b938178bf5ec4bb  frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte
- blob:8a81beedab6568f587ffa32753946b49ee3c7b37  frontend/src/lib/components/shared/weather-metrics-tab/__tests__/wertebereiche_sprache.test.ts
- blob:a7266ce9752c0b4b176dc53be28390a957c0c782  tests/golden/f5_wertebereiche/route_voll.de.html

## Geprüfte Dateien

- sha256:af03f4963a6cd2a43bf352fd9b1b9d59b873f94ad7ad1d918bb65739a5be52bf  docs/specs/modules/rework_2276_s6h_ac2_endbilanz.md
- sha256:ac45dd1da9919f7c46ba08f3cf611a0ab5e5841e29d7101b2c2e4677eeeec5d4  frontend/e2e/elementliste-abgleich.staging.spec.ts
- sha256:12b9a7f12c90b77df35967a0da8e238223ac4a57d52e8f1b8820b542d11baea6  frontend/e2e/elementliste_abgleich_logik.ts
- sha256:b9f2dcaa55a4d3779b92436f7fc7f18e67f665be7c19ca13f5183621af2fe799  frontend/e2e/s3a2794-teil3-design.spec.ts
- sha256:acedbde36bd29912cab45b29b107657a734c3b36b1daf115e20fc7d806a69efd  frontend/e2e/s3a2794-teil3-dialog.spec.ts
- sha256:a675f3ed9e758a866e3e63c9a2c7e31b56890d363007fa32f325ceeaf7f24ec4  frontend/src/app.css
- sha256:96f4acf957622303307705a989148d4cac4a840a90ff4995ca4b91b6e4d3ec6d  frontend/src/lib/__tests__/bausteine_waechter_regeln.ts
- sha256:92b7402dce9eeb489cb014a2a1a2a37a97e0141337d78f0bd45ddbcfb5b460a4  frontend/src/lib/__tests__/elementliste_abgleich_bedienplan.test.ts
- sha256:806c940525ca8482bae365ad804a936647e0230a4f04ba9bb9f541342e53fc7a  frontend/src/lib/__tests__/elementliste_abgleich_verdrahtung.test.ts
- sha256:aaeaead8d0e4b9c7a9761acd9a0da177b4342f7511ab3d0ccb6c20fc0a7bd76f  frontend/src/lib/__tests__/harte_farben_waechter.test.ts
- sha256:9c284c023707b163a2f10e1951fb6c6d34b5403db285d55cd61ece97b3e45cd1  frontend/src/lib/components/atoms/Haken.svelte
- sha256:df7a5030ebefc05af8580b18c992598c07e8540f0bf003216c2f44cdc004c945  frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte
- sha256:7843f14e08e96f5d4b035b8755dbdb6a3d217a0d2f4e4e5097c6db098377b586  frontend/src/lib/components/shared/WeatherMetricsTab.svelte
- sha256:3939821c97725c4578bcd4a57eb7252568ba18b4f1dae02eb4ac919785a6566f  frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts
- sha256:598b222a749784117e9747840a282e94cd7f699ef3527f3fa3ef91bb5bce0dfe  frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte
- sha256:9c9423d3b7c97911b8bdf8a1bdc433e8a4a8b156db996c5e709210796dfa985b  frontend/src/lib/components/shared/weather-metrics-tab/__tests__/wertebereiche_sprache.test.ts
- sha256:07172247ac4fa4a713718d3e476ec74614487dda4fc249fee4839d5e578a7f6f  tests/golden/f5_wertebereiche/route_voll.de.html

## Prüfbasis

- base: ac1fd478bed6e85df0529954928097e3f8a172c5
- blob:9c65c720b6206cf200fad27c1a995ca8125e67e7  docs/specs/modules/rework_2276_s6h_ac2_endbilanz.md
- blob:21626913992de16d316d67424c11abb10351912d  frontend/e2e/elementliste-abgleich.staging.spec.ts
- blob:33ecac7e74cd4d5766506cd526c7999e39389c1c  frontend/e2e/elementliste_abgleich_logik.ts
- blob:0ba71267581e7977d7ae3e74f24b44f518ffc7cc  frontend/e2e/s3a2794-teil3-design.spec.ts
- blob:db97429cfae9e1eddd7c2229bcc16c6c2f4c61b4  frontend/e2e/s3a2794-teil3-dialog.spec.ts
- blob:5b6d10357f6e54d813ff3202824fa9ff23bf8a3a  frontend/src/app.css
- blob:e27d3a2aa8a90bbc19f86b8a773e484c1568906d  frontend/src/lib/__tests__/bausteine_waechter_regeln.ts
- blob:a1415faf43451f543415a95f84a79b9f2b97d02e  frontend/src/lib/__tests__/elementliste_abgleich_bedienplan.test.ts
- blob:2f1cd46f4dcf2937d4aff5a082e1f108c3f05818  frontend/src/lib/__tests__/elementliste_abgleich_verdrahtung.test.ts
- blob:442991f81913eae0c2d2b4fa5f2d236d81a68079  frontend/src/lib/__tests__/harte_farben_waechter.test.ts
- blob:462ce8e8a4e4f334298c481ba58d2862e65b6850  frontend/src/lib/components/atoms/Haken.svelte
- blob:78e49cfd2cfbc667e139bbea2d54b39b2f4dbe32  frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte
- blob:b143365f83bb73b41bc656ecb39114332f56e842  frontend/src/lib/components/shared/WeatherMetricsTab.svelte
- blob:8786f8d8cd1b2fbf124dacd7ebd67c51fa4a695a  frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts
- blob:78dc0c1d118a34e2ea2606ff0b938178bf5ec4bb  frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte
- blob:8a81beedab6568f587ffa32753946b49ee3c7b37  frontend/src/lib/components/shared/weather-metrics-tab/__tests__/wertebereiche_sprache.test.ts
- blob:a7266ce9752c0b4b176dc53be28390a957c0c782  tests/golden/f5_wertebereiche/route_voll.de.html


Confirmation: Fix-Loop 1 (F001/F003)
  Code reference: frontend/src/lib/utils/vorlageSpeichernKarte.ts:11
  Evidence: karteSchliesstPerTaste, speicherKarteAusloeser (Toggle + Fokus-Rueckgabe) geteilt; Mutationen im Lib rot.
  Status: CONFIRMED

Confirmation: Fix-Loop 1 Alt-Editor
  Code reference: frontend/src/lib/components/shared/WeatherMetricsTab.svelte:1706
  Evidence: onOpenSaveDialog toggelt, onClose/onSaved geben Fokus zurueck, id gebunden (aria-controls). Verdrahtung nur per Staging-E2E bewacht (Mutation ueberlebt).
  Status: CONFIRMED

Confirmation: Fix-Loop 1 PresetBar
  Code reference: frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2PresetBar.svelte:66
  Evidence: aria-expanded/aria-controls/Testid; Mutation aria-expanded weg: 4 rot.
  Status: CONFIRMED

Confirmation: Fix-Loop 1 Test
  Code reference: frontend/src/lib/components/shared/weather-metrics-tab/__tests__/vorlage_speichern_karte_3190.test.ts:34
  Evidence: reine Funktionen und SSR-Attribute getestet.
  Status: CONFIRMED

Confirmation: Fix-Loop 1 Dialog/Karte
  Code reference: frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte:106
  Evidence: Guard ueber karteSchliesstPerTaste(e.key, saving); id $bindable.
  Status: CONFIRMED

Confirmation: Fix-Loop 1 VorlageKarte
  Code reference: frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte:100
  Evidence: nutzt geteilte Logik; Picker-Guard ueber pickerSchliesstPerTaste.
  Status: CONFIRMED

Finding:
  ID: F004
  Severity: LOW
  Category: anti_pattern
  Code reference: frontend/src/lib/components/shared/WeatherMetricsTab.svelte:35
  Description: zwei Anweisungen pro Zeile (Import und Zustand) nur, um eingefrorene Zeilennummern zu schonen; die Nummer wurde dennoch nachgefuehrt.
  Spec requirement: AC-10 (kein Verstoss)
  Conflict: Lesbarkeit, keine Wächter-Umgehung.
  Remediation: normal formatieren und Zeilenzahl im Wächter nachfuehren.

Tests: 8300 passed, 0 failed, 3 übersprungen

═══════════════════════════════════════
VERDICT: VERIFIED
═══════════════════════════════════════
F001 und F003 behoben; F002 (Verdrahtung nur per Staging-E2E) und F004 sind LOW und blockieren nicht.
Checklist: 12/12 points proven

## Geprüfte Dateien

- sha256:5d7ae014a663c98a1ace569bed7ea6db143712499d646a093c1e003e6533710f  docs/specs/modules/rework_2276_s6h_ac2_endbilanz.md
- sha256:ac45dd1da9919f7c46ba08f3cf611a0ab5e5841e29d7101b2c2e4677eeeec5d4  frontend/e2e/elementliste-abgleich.staging.spec.ts
- sha256:12b9a7f12c90b77df35967a0da8e238223ac4a57d52e8f1b8820b542d11baea6  frontend/e2e/elementliste_abgleich_logik.ts
- sha256:b9f2dcaa55a4d3779b92436f7fc7f18e67f665be7c19ca13f5183621af2fe799  frontend/e2e/s3a2794-teil3-design.spec.ts
- sha256:acedbde36bd29912cab45b29b107657a734c3b36b1daf115e20fc7d806a69efd  frontend/e2e/s3a2794-teil3-dialog.spec.ts
- sha256:a675f3ed9e758a866e3e63c9a2c7e31b56890d363007fa32f325ceeaf7f24ec4  frontend/src/app.css
- sha256:96f4acf957622303307705a989148d4cac4a840a90ff4995ca4b91b6e4d3ec6d  frontend/src/lib/__tests__/bausteine_waechter_regeln.ts
- sha256:92b7402dce9eeb489cb014a2a1a2a37a97e0141337d78f0bd45ddbcfb5b460a4  frontend/src/lib/__tests__/elementliste_abgleich_bedienplan.test.ts
- sha256:806c940525ca8482bae365ad804a936647e0230a4f04ba9bb9f541342e53fc7a  frontend/src/lib/__tests__/elementliste_abgleich_verdrahtung.test.ts
- sha256:aaeaead8d0e4b9c7a9761acd9a0da177b4342f7511ab3d0ccb6c20fc0a7bd76f  frontend/src/lib/__tests__/harte_farben_waechter.test.ts
- sha256:9c284c023707b163a2f10e1951fb6c6d34b5403db285d55cd61ece97b3e45cd1  frontend/src/lib/components/atoms/Haken.svelte
- sha256:7d2276aa35d3829323331227ebff904418298864fa56b228e8880aa4abccad7f  frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte
- sha256:2bd266a1ceab847e37ddd25f297d9438b193ad5bc2e6e6168b7d4bd132412bdf  frontend/src/lib/components/shared/WeatherMetricsTab.svelte
- sha256:ddac339590ca302635d29057fdaab02d41c1d2a6decd75fd85e01bd7e3f41492  frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts
- sha256:af0489bb129927ce0f872f9dd12518855928e15155684a93d3289dd20d4cb405  frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte
- sha256:f06f70ffb2b80cb0983ae79e15993a5f06bde4da55ce9edc1f3223394344ef40  frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2PresetBar.svelte
- sha256:5f55f701f03460bb796e332e6926fd60aede2474eb88f188076f94eccdbf73cb  frontend/src/lib/components/shared/weather-metrics-tab/__tests__/vorlage_speichern_karte_3190.test.ts
- sha256:9c9423d3b7c97911b8bdf8a1bdc433e8a4a8b156db996c5e709210796dfa985b  frontend/src/lib/components/shared/weather-metrics-tab/__tests__/wertebereiche_sprache.test.ts
- sha256:b3f18ce359b983bc839c4750b7f11787f0bc0acc7d7dc8c3c21399ddd0813744  frontend/src/lib/utils/vorlageSpeichernKarte.ts
- sha256:2fbd5a117fb10fba3b621f94fc091735b805164433f92abd7f26c706bda67910  tests/golden/f5_wertebereiche/route_voll.de.html

## Prüfbasis

- base: ac1fd478bed6e85df0529954928097e3f8a172c5
- blob:bfb19916c0980764bfbd4219645dcfcf65d2acb1  docs/specs/modules/rework_2276_s6h_ac2_endbilanz.md
- blob:21626913992de16d316d67424c11abb10351912d  frontend/e2e/elementliste-abgleich.staging.spec.ts
- blob:33ecac7e74cd4d5766506cd526c7999e39389c1c  frontend/e2e/elementliste_abgleich_logik.ts
- blob:0ba71267581e7977d7ae3e74f24b44f518ffc7cc  frontend/e2e/s3a2794-teil3-design.spec.ts
- blob:db97429cfae9e1eddd7c2229bcc16c6c2f4c61b4  frontend/e2e/s3a2794-teil3-dialog.spec.ts
- blob:5b6d10357f6e54d813ff3202824fa9ff23bf8a3a  frontend/src/app.css
- blob:e27d3a2aa8a90bbc19f86b8a773e484c1568906d  frontend/src/lib/__tests__/bausteine_waechter_regeln.ts
- blob:a1415faf43451f543415a95f84a79b9f2b97d02e  frontend/src/lib/__tests__/elementliste_abgleich_bedienplan.test.ts
- blob:2f1cd46f4dcf2937d4aff5a082e1f108c3f05818  frontend/src/lib/__tests__/elementliste_abgleich_verdrahtung.test.ts
- blob:442991f81913eae0c2d2b4fa5f2d236d81a68079  frontend/src/lib/__tests__/harte_farben_waechter.test.ts
- blob:462ce8e8a4e4f334298c481ba58d2862e65b6850  frontend/src/lib/components/atoms/Haken.svelte
- blob:c44d2883805ee9d1f8890618f2c721b68158108c  frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte
- blob:a811b94d706f4c15e679494161cbd3dd78a16cc7  frontend/src/lib/components/shared/WeatherMetricsTab.svelte
- blob:44d0f0d8bb8b07cc14f82fd2e0351a35b02c7d15  frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts
- blob:a15972578d73c43edb04d1636d52cdb4ffde2af7  frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte
- blob:56c43e18169e122172810ab7ae6c8a3c4888db56  frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2PresetBar.svelte
- blob:39a5f0e6dc2880313c33cc1573e044c0284afe60  frontend/src/lib/components/shared/weather-metrics-tab/__tests__/vorlage_speichern_karte_3190.test.ts
- blob:8a81beedab6568f587ffa32753946b49ee3c7b37  frontend/src/lib/components/shared/weather-metrics-tab/__tests__/wertebereiche_sprache.test.ts
- blob:76ff0bfff5fbc093f5f20988f232c94bdd31d954  frontend/src/lib/utils/vorlageSpeichernKarte.ts
- blob:47125906db7d1b46339139217335b15797523d61  tests/golden/f5_wertebereiche/route_voll.de.html

## Geprüfte Dateien

- sha256:5d7ae014a663c98a1ace569bed7ea6db143712499d646a093c1e003e6533710f  docs/specs/modules/rework_2276_s6h_ac2_endbilanz.md
- sha256:ac45dd1da9919f7c46ba08f3cf611a0ab5e5841e29d7101b2c2e4677eeeec5d4  frontend/e2e/elementliste-abgleich.staging.spec.ts
- sha256:12b9a7f12c90b77df35967a0da8e238223ac4a57d52e8f1b8820b542d11baea6  frontend/e2e/elementliste_abgleich_logik.ts
- sha256:b9f2dcaa55a4d3779b92436f7fc7f18e67f665be7c19ca13f5183621af2fe799  frontend/e2e/s3a2794-teil3-design.spec.ts
- sha256:acedbde36bd29912cab45b29b107657a734c3b36b1daf115e20fc7d806a69efd  frontend/e2e/s3a2794-teil3-dialog.spec.ts
- sha256:a675f3ed9e758a866e3e63c9a2c7e31b56890d363007fa32f325ceeaf7f24ec4  frontend/src/app.css
- sha256:96f4acf957622303307705a989148d4cac4a840a90ff4995ca4b91b6e4d3ec6d  frontend/src/lib/__tests__/bausteine_waechter_regeln.ts
- sha256:92b7402dce9eeb489cb014a2a1a2a37a97e0141337d78f0bd45ddbcfb5b460a4  frontend/src/lib/__tests__/elementliste_abgleich_bedienplan.test.ts
- sha256:806c940525ca8482bae365ad804a936647e0230a4f04ba9bb9f541342e53fc7a  frontend/src/lib/__tests__/elementliste_abgleich_verdrahtung.test.ts
- sha256:aaeaead8d0e4b9c7a9761acd9a0da177b4342f7511ab3d0ccb6c20fc0a7bd76f  frontend/src/lib/__tests__/harte_farben_waechter.test.ts
- sha256:9c284c023707b163a2f10e1951fb6c6d34b5403db285d55cd61ece97b3e45cd1  frontend/src/lib/components/atoms/Haken.svelte
- sha256:7d2276aa35d3829323331227ebff904418298864fa56b228e8880aa4abccad7f  frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte
- sha256:2bd266a1ceab847e37ddd25f297d9438b193ad5bc2e6e6168b7d4bd132412bdf  frontend/src/lib/components/shared/WeatherMetricsTab.svelte
- sha256:ddac339590ca302635d29057fdaab02d41c1d2a6decd75fd85e01bd7e3f41492  frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts
- sha256:af0489bb129927ce0f872f9dd12518855928e15155684a93d3289dd20d4cb405  frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte
- sha256:f06f70ffb2b80cb0983ae79e15993a5f06bde4da55ce9edc1f3223394344ef40  frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2PresetBar.svelte
- sha256:5f55f701f03460bb796e332e6926fd60aede2474eb88f188076f94eccdbf73cb  frontend/src/lib/components/shared/weather-metrics-tab/__tests__/vorlage_speichern_karte_3190.test.ts
- sha256:9c9423d3b7c97911b8bdf8a1bdc433e8a4a8b156db996c5e709210796dfa985b  frontend/src/lib/components/shared/weather-metrics-tab/__tests__/wertebereiche_sprache.test.ts
- sha256:b3f18ce359b983bc839c4750b7f11787f0bc0acc7d7dc8c3c21399ddd0813744  frontend/src/lib/utils/vorlageSpeichernKarte.ts
- sha256:2fbd5a117fb10fba3b621f94fc091735b805164433f92abd7f26c706bda67910  tests/golden/f5_wertebereiche/route_voll.de.html

## Prüfbasis

- base: ac1fd478bed6e85df0529954928097e3f8a172c5
- blob:bfb19916c0980764bfbd4219645dcfcf65d2acb1  docs/specs/modules/rework_2276_s6h_ac2_endbilanz.md
- blob:21626913992de16d316d67424c11abb10351912d  frontend/e2e/elementliste-abgleich.staging.spec.ts
- blob:33ecac7e74cd4d5766506cd526c7999e39389c1c  frontend/e2e/elementliste_abgleich_logik.ts
- blob:0ba71267581e7977d7ae3e74f24b44f518ffc7cc  frontend/e2e/s3a2794-teil3-design.spec.ts
- blob:db97429cfae9e1eddd7c2229bcc16c6c2f4c61b4  frontend/e2e/s3a2794-teil3-dialog.spec.ts
- blob:5b6d10357f6e54d813ff3202824fa9ff23bf8a3a  frontend/src/app.css
- blob:e27d3a2aa8a90bbc19f86b8a773e484c1568906d  frontend/src/lib/__tests__/bausteine_waechter_regeln.ts
- blob:a1415faf43451f543415a95f84a79b9f2b97d02e  frontend/src/lib/__tests__/elementliste_abgleich_bedienplan.test.ts
- blob:2f1cd46f4dcf2937d4aff5a082e1f108c3f05818  frontend/src/lib/__tests__/elementliste_abgleich_verdrahtung.test.ts
- blob:442991f81913eae0c2d2b4fa5f2d236d81a68079  frontend/src/lib/__tests__/harte_farben_waechter.test.ts
- blob:462ce8e8a4e4f334298c481ba58d2862e65b6850  frontend/src/lib/components/atoms/Haken.svelte
- blob:c44d2883805ee9d1f8890618f2c721b68158108c  frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte
- blob:a811b94d706f4c15e679494161cbd3dd78a16cc7  frontend/src/lib/components/shared/WeatherMetricsTab.svelte
- blob:44d0f0d8bb8b07cc14f82fd2e0351a35b02c7d15  frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts
- blob:a15972578d73c43edb04d1636d52cdb4ffde2af7  frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte
- blob:56c43e18169e122172810ab7ae6c8a3c4888db56  frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2PresetBar.svelte
- blob:39a5f0e6dc2880313c33cc1573e044c0284afe60  frontend/src/lib/components/shared/weather-metrics-tab/__tests__/vorlage_speichern_karte_3190.test.ts
- blob:8a81beedab6568f587ffa32753946b49ee3c7b37  frontend/src/lib/components/shared/weather-metrics-tab/__tests__/wertebereiche_sprache.test.ts
- blob:76ff0bfff5fbc093f5f20988f232c94bdd31d954  frontend/src/lib/utils/vorlageSpeichernKarte.ts
- blob:47125906db7d1b46339139217335b15797523d61  tests/golden/f5_wertebereiche/route_voll.de.html
