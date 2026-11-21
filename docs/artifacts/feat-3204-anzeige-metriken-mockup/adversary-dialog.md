# Adversary Dialog — feat-3204-anzeige-metriken-mockup
Spec: docs/specs/modules/feat_3204_anzeige_metriken_mockup.md
Datum: 2026-11-21 14:20

## Checkliste
- [x] **Input:** Mockup Fassung 4, Katalog DE/EN, Staging-Seite Reiter Wetter (Trip), Prüfkonto-Seed.
- [x] **Output:** Abgleich meldet für Namen, Untertitel, Zeilenmitte und Erklärsatz der beiden Metriken keine Abweichung; keine herrenlosen Besitzer-Einträge.
- [x] **Side effects:** Wechsel abweichend→gefunden in anderen Besitzern ist erlaubt; neue Abweichung ohne Besitzer ist es nicht. Produktverhalten (Metrik-Wahl, SMS L/D) unverändert.
- [x] **AC-1:** Given der Trip-Reiter Wetter in Deutsch / When der Nutzer die Gruppe Temperatur liest / Then stehen dort „Tages-Tiefsttemperatur (Gehzeit)“ und „Tages-Höchsttemperatur (Gehzeit)“ zwischen Tiefsttemperatur Nacht und Gefühlter Temperatur, und das Mockup Fassung 4 zeigt dieselbe Reihenfolge.
- [x] **AC-2:** Given eine der beiden Gehzeit-Metriken im Trip-Reiter Wetter / When der Nutzer die Zeile betrachtet / Then zeigt sie den Untertitel „°C · nur Anzeige, keine Ampel“ und in der Mitte „keine Ampel, nur Anzeige“, ohne Ampel-Grenzen und ohne Alarm-Auswahl, wie die Windrichtung.
- [x] **AC-3:** Given eine Nur-Anzeige-Metrik im Reiter Wetter (Trip, Deutsch oder Englisch) / When der Nutzer den Erklärsatz liest / Then verweist er auf den Abschnitt „Was steht wo“ (englisch der entsprechende Abschnittsname) statt „je Liste“, wortgleich zum Mockup.
- [x] **AC-4:** Given der Orts-Vergleich / When der Nutzer dort die Metrikliste öffnet / Then erscheinen Tages-Tief und Tages-Hoch weiterhin nicht (ADR-0011), und das Mockup der Orte bleibt unverändert.
- [x] **AC-5:** Given der Staging-Abgleich des Reiters Wetter in Deutsch und Englisch / When er nach der Änderung läuft / Then meldet er keinen Eintrag mit Besitzer `#3204`, keine neue Abweichung ohne Besitzer, und der Zählwächter steht auf 0.
- [x] **AC-6:** Given Bestandstrips mit aktivierten Tages-Tief/-Hoch-Metriken / When der Nutzer seinen Trip öffnet / Then bleiben Auswahl, SMS-Kürzel L/D und Briefing unverändert, denn nur Mockup, Erklärsatz und Prüflisten ändern sich.
- [x] **AC-7:** Given der Trip-Reiter Wetter als Mockup und als Staging-Seite / When der Product Owner das Soll/Ist-Bild ansieht / Then stimmen beide in den zwei neuen Zeilen und im Erklärsatz sichtbar überein.

## Dialog

### Runde 1
**Adversary:** Erklärsatz EN/DE, Elementlisten-Diff, Alttests, Besitzerliste.
- Elementliste semantisch (nach id, ohne ordnung): 0 entfernt, 44 neu (22 Zustand normal + 22 luecken, nur ctx trip/reiter wetter), 2 geänderte Zähler-Einträge „9 von 13 … 3“ -> „9 von 15 … 5“ (+2 Metriken, +2 ohne Alarm: korrekt, beide Nur-Anzeige). Orte unberührt. Neue Einträge: je Metrik Entfernen-Knopf, Name, Untertitel, Zeilenmitte, Erklärsatz, „kein Alarm“, dazu Name + 4 Haken in „Was steht wo“; alle luecke=false (DE+EN gedeckt). Die 10 #3204-Besitzer-Einträge entfernt (-80 Zeilen = 10 Einträge), keine andere Besitzer-Zeile berührt.
- EN-Satz: „…below under ‘What goes where’.“ = wetter.wsw.titel „What goes where“ (en/wetter.json:134); einfache Anführungszeichen wie im Bestand (wetter.nicht_im_briefing.hinzugefuegt, alarme.alarm_ab.umbau_hinweis); DE wortgleich zu Mockup Z. 429. Nur Katalog, kein hartcodierter Text.
- Alttests: wetter_tab_i18n (GEAENDERT_FREIGEGEBEN, +1 Schlüssel je Sprache) und s3a2794 AC-18 (Soll-Text getauscht): ehrlich nachgezogen, weiter exakter Wortlaut, nichts aufgeweicht.
- Tests: node-Suite (71 Tests inkl. e2e-Ordner) grün, 0 fail, 0 skipped; Python-Zählwächter test_2913_c2_besitzerliste grün. Keine Python/Go-Änderung (Statusliste enthält keine Dateien in src, internal, cmd, api): AC-6.
**Implementierer:** n/a (Kontextisolation).

### Runde 2
**Adversary:** Mutationen per String-Ersetzung, Sicherung im Scratchpad (sha256 vor = nach: mockup eb4b3442…, de 8b94cb9b…, en 270a5892…).
- M1 Mockup-Zeile on=false: node-Suite 66 grün (überlebt dort), Playwright-Generatorlauf e2e/elementliste-generator.mockup.spec.ts ROT (CI-Check e2e).
- M2 Reihenfolge Tages-Tief/-Hoch getauscht: node-Suite überlebt, Generatorlauf ROT.
- M3 DE-Erklärsatz zurück auf „je Liste“ (Katalog+Mockup): 7 node-Tests rot.
- M4 EN-Abschnittsname falsch („What goes there“): 6 node-Tests rot.
- M5 Orte-Liste um Gehzeit-Metrik: Generatorlauf ROT.
- F001 (LOW): node-Tests prüfen das Mockup nur über die eingecheckte Liste; M1/M2/M5 fängt allein der Playwright-Generatorlauf (CI e2e). Wirkt dort, wo die Zusicherung wirkt: akzeptabel.
- F002 (LOW): Briefing docs/briefings/feat-3204-anzeige-metriken-mockup.md:27 sagt „zunächst nicht aktiv“, Spec §1 sagt „aktiv“ (on=true, nötig damit Untertitel/Zeilenmitte/Erklärsatz in der Liste stehen). Mockup folgt der Spec; Briefing veraltet, reine Doku. Windrichtung bleibt on=false (Z. 324).
- AC-5/AC-7 live: „live nach Übernahme“; lokal über Elementliste + Besitzerliste (#3204: 0) gedeckt.
**Implementierer:** n/a.

Finding:
  ID: F001
  Severity: LOW
  Category: edge_case
  Code reference: frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts:73
  Description: MOCKUP_HASH ist fest eingetragen und vergleicht nur die eingecheckte Liste; Mockup-Änderungen ohne Neugenerierung fängt nur der Playwright-Generatorlauf.
  Spec requirement: AC-1/AC-2 — Reihenfolge und Zeilenform im Mockup
  Conflict: node-Suite allein überlebt M1/M2/M5; CI-e2e fängt sie (nachgewiesen).
  Remediation: keine nötig.

Finding:
  ID: F002
  Severity: LOW
  Category: anti_pattern
  Code reference: docs/briefings/feat-3204-anzeige-metriken-mockup.md:27
  Description: Briefing nennt die neuen Zeilen „nicht aktiv“, Mockup und Spec: aktiv.
  Spec requirement: AC-2 — Untertitel und Zeilenmitte sichtbar
  Conflict: Dokumentationsabweichung, kein Produktfehler.
  Remediation: Briefing-Satz auf „aktiv“ korrigieren.

Confirmation:
  AC: AC-1
  Code reference: docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html:319
  Evidence: Zeilen 319/320 zwischen temperature_night (318) und wind_chill; Reihenfolgetest grün, M2 rot im Generatorlauf.
  Status: CONFIRMED

Confirmation:
  AC: AC-2
  Code reference: docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html:320
  Evidence: Untertitel „nur Anzeige, keine Ampel“, °C, keine Grenzen, Nur-Anzeige-Flag; Liste enthält Untertitel und Zeilenmitte DE+EN.
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: frontend/src/lib/i18n/messages/en/wetter.json:84
  Evidence: EN nutzt „What goes where“ (wetter.wsw.titel, Z. 134); M4 rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: frontend/src/lib/i18n/messages/de/wetter.json:84
  Evidence: „… unten unter „Was steht wo“ ein.“ wortgleich Mockup Z. 429; M3 rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-4
  Code reference: docs/context/einstellungen_neu/elementliste.json:1
  Evidence: alle 44 neuen Einträge ctx=trip; Orte identisch; M5 im Generatorlauf rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: docs/context/einstellungen_neu/elementliste_besitzer.json:3607
  Evidence: 10 #3204-Einträge entfernt; Zählwächter grün; Staging-Teil live nach Übernahme.
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: tests/test_2913_c2_besitzerliste.py:155
  Evidence: Zählwächter "#3204": 0, grün.
  Status: CONFIRMED

Confirmation:
  AC: AC-6
  Code reference: frontend/src/lib/components/organisms/__tests__/wetter_tab_i18n.test.ts:189
  Evidence: nur Katalogtext geändert; keine Änderung an Python/Go.
  Status: CONFIRMED

Confirmation:
  AC: AC-7
  Code reference: frontend/src/lib/components/shared/__tests__/s3a2794_teil3_wetter_katalog.test.ts:90
  Evidence: lokal Soll-Wortlaut Mockup = Katalog; Bildabgleich live nach Übernahme.
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts:73
  Evidence: Prüfsumme/Anzahl 2690 begründet nachgezogen; Generatorlauf grün gegen eingecheckte Liste.
  Status: CONFIRMED

Confirmation:
  AC: AC-1
  Code reference: frontend/e2e/feat3204_elementliste_anzeige_metriken.test.ts:80
  Evidence: RED-Test Reihenfolge/Orte, jetzt grün.
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: frontend/src/lib/components/organisms/__tests__/feat3204_erklaersatz_anzeige.test.ts:1
  Evidence: RED-Test Erklärsatz DE/EN, grün; M3/M4 rot.
  Status: CONFIRMED

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Verdict

═══════════════════════════════════════
VERDICT: VERIFIED
═══════════════════════════════════════
Tests: 71 node + Besitzer-Zählwächter grün, 0 failed, 0 übersprungen; Mutationen M1-M5 alle gefangen (M1/M2/M5 vom Playwright-Generatorlauf, M3/M4 von node).
Edge cases: F001/F002 LOW, nicht blockierend. AC-5/AC-7 live: nach Übernahme.
Regressions: None found
Checklist: 10/10 points proven

## Geprüfte Dateien

- sha256:d775db054226853fe0560dc8025f3b641174592fe12c4c6a78b3c3f3c4afe08e  docs/briefings/feat-3204-anzeige-metriken-mockup.md
- sha256:4d221ba6825e579b86ee15602c2acae0635650b648c02433e4f148d13685621d  docs/context/einstellungen_neu/elementliste.json
- sha256:22e7f810fe63be4747244841d2c9835f377d27b4ac1f451e93068ef1507601a8  docs/context/einstellungen_neu/elementliste_besitzer.json
- sha256:eb4b34429611f1a354cb9924e866c5f181012a093c37ac44c95e4a9538f2d1c4  docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html
- sha256:852fb5d428ebb6dec2451d78369d42d434c91f8152b6eecd366e344ad8584d81  frontend/e2e/feat3204_elementliste_anzeige_metriken.test.ts
- sha256:f6a66751eec74d523354df46e2cea0d8e24b2d4cd652994c3140f78dee16d4e9  frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts
- sha256:47641901192b357d53d75a133da8903bd2f738d112f8d100ecc70fe6c7f934b5  frontend/src/lib/components/organisms/__tests__/feat3204_erklaersatz_anzeige.test.ts
- sha256:c992dbf6ac4763b655db4544e940df36d8b67250ed30ef9cb766ce18ce69430a  frontend/src/lib/components/organisms/__tests__/wetter_tab_i18n.test.ts
- sha256:5de61f1e3298a41332064251d5bb0bf58b452235320b5efc686d1863f58cdd10  frontend/src/lib/components/shared/__tests__/s3a2794_teil3_wetter_katalog.test.ts
- sha256:8b94cb9b79c08f1c64b61671e8d68b80af3cc5f4c4036836507547ecd1cf82af  frontend/src/lib/i18n/messages/de/wetter.json
- sha256:270a589217c0ad05fb3b6dddf38d266eae09d92b6934ee4583ed1ed50e19e601  frontend/src/lib/i18n/messages/en/wetter.json
- sha256:440606ff17f195898305ef7f6441358920ce3676d54a33ec83b9041ee423a97a  tests/test_2913_c2_besitzerliste.py

## Prüfbasis

- base: b7f42ec889c43b001696ecce03cd1039d709cb8e
- blob:46cf64b13d279e9c2e3c665a76f60680b5ad2e55  docs/briefings/feat-3204-anzeige-metriken-mockup.md
- blob:432d4e3f152879ac596c8a5eff62de7522754ec8  docs/context/einstellungen_neu/elementliste.json
- blob:6978a5533e7889e0321b9a09a2281a992da6afb4  docs/context/einstellungen_neu/elementliste_besitzer.json
- blob:db40d939725e35b72a4d5342b7bd69b7d8238d05  docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html
- blob:865ebbc3138aa7e1b14d84744422f197dab6e04b  frontend/e2e/feat3204_elementliste_anzeige_metriken.test.ts
- blob:0e775e07348c0daa4faff94c2b5039821079bee3  frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts
- blob:33ef9237be3742e4b95bba77e518cc9b32f5fc86  frontend/src/lib/components/organisms/__tests__/feat3204_erklaersatz_anzeige.test.ts
- blob:2629764900592f4c0532a6a2868997bc890cc5ba  frontend/src/lib/components/organisms/__tests__/wetter_tab_i18n.test.ts
- blob:8a68fa4a7782567d0e482f2c7fb2ff9ac50e37f9  frontend/src/lib/components/shared/__tests__/s3a2794_teil3_wetter_katalog.test.ts
- blob:674c70b9433ff0ed372f0f25ad756aa82f921d5b  frontend/src/lib/i18n/messages/de/wetter.json
- blob:770858351351c085f6b856b026181b614f12140e  frontend/src/lib/i18n/messages/en/wetter.json
- blob:1dd89a20d628a6b052819dff99f687bf818734e2  tests/test_2913_c2_besitzerliste.py
