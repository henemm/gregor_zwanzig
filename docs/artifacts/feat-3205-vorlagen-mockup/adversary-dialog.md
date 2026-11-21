# Adversary Dialog — feat-3205-vorlagen-mockup
Spec: docs/specs/modules/feat_3205_vorlagen_mockup.md
Datum: 2026-11-21 16:31

## Checkliste
- [x] **Input:** Mockup Fassung 4, Staging-Reiter Wetter (Trip und Orte), Prüfkonto-Seed.
- [x] **Output:** Abgleich meldet keinen Eintrag mit Besitzer `#3205`; Orte-Vorlagenauswahl im Mockup und live enthalten „Mallorca Frühling“ nicht; die Zurücksetzen-Zeile erzeugt keinen herrenlosen Eintrag.
- [x] **Side effects:** Wechsel abweichend→gefunden in anderen Besitzern ist erlaubt; neue Abweichung ohne Besitzer nicht. Produktverhalten (Vorlagen je Art, Duplikat- und Standard-Regeln) unverändert.
- [x] **AC-1:** Given der Orts-Vergleich-Reiter Wetter / When der Nutzer die Vorlagenauswahl öffnet / Then erscheinen dort nur die Vorlagen der Art Vergleich, die eigene Trip-Vorlage „Mallorca Frühling“ steht nicht in der Liste, und das Mockup zeigt dasselbe.
- [x] **AC-2:** Given der Trip-Reiter Wetter / When der Nutzer die Vorlagenauswahl öffnet / Then stehen die Systemvorlagen und die eigenen Trip-Vorlagen, darunter „Mallorca Frühling“, zur Auswahl, unverändert zu heute.
- [x] **AC-3:** Given ein Trip mit einer gewählten Vorlage und Änderungen an einzelnen Metriken / When der Nutzer die Vorlagenkarte ansieht / Then erscheint „Auf „Vorlage“ zurücksetzen“ (englisch „Reset to „Vorlage““) nur bei Abweichungen, und Mockup und Staging stimmen im Zustand überein, sodass kein Besitzer `#3205` übrig bleibt.
- [x] **AC-4:** Given der gewählte Weg für die Zurücksetzen-Zeile / When der Abgleich nach der Änderung läuft / Then entstehen in anderen Einträgen (Picker-Anzeige „unverändert“ gegen „N Abweichung(en)“, Abweichungsmarken) keine neuen Abweichungen.
- [x] **AC-5:** Given der Staging-Abgleich des Reiters Wetter in Deutsch und Englisch / When er nach der Änderung läuft / Then meldet er keinen Eintrag mit Besitzer `#3205`, keine neue Abweichung ohne Besitzer, und der Zählwächter steht auf 0, während `#3009` unverändert bei 2 bleibt.
- [x] **AC-6:** Given Bestandsnutzer mit eigenen Vorlagen / When sie Trip oder Orts-Vergleich öffnen / Then bleiben Speichern, Duplikat- und Standard-Regeln je Art wie bisher (AC-24 aus #2794), denn nur Mockup, Prüfdaten und Prüflisten ändern sich.
- [x] **AC-7:** Given die Orte-Vorlagenauswahl als Mockup und als Staging-Seite / When der Product Owner das Soll/Ist-Bild ansieht / Then stimmen beide in der Vorlagenliste sichtbar überein, ohne „Mallorca Frühling“.

## Dialog

### Runde 1
**Adversary:** Behauptung: Mockup trennt Vorlagen je Art, Besitzer #3205 weg.
Gegenprobe Mockup (Code reference: docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html:359-362 EIGENE mit Art-Spalte, ART, eigeneJeArt; Picker :496 nutzt eigeneJeArt; Namenspruefung und Speichern :756-757 je Art). Aenderung minimal (11 Zeilen).
Mutationen: M1 Filter entfernen (Picker wieder EIGENE.map) -> AC-1-Test rot plus 2 weitere rot. M2 Art von Mallorca auf vergleich -> 6 rot (Trip-Test, Orte-Test, Kern, Hash). Mockup-Seite damit bewacht. Namenspruefung nutzt eigeneJeArt, ein Name darf je Art doppelt vorkommen; deckt sich mit AC-24 (Duplikat je Art).
Generator-Lauf (Code reference: docs/context/einstellungen_neu/elementliste.json:1894): vier Orte-Eintraege entfallen, sonst nichts. Pruefsumme begruendet (Code reference: frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts:71), 2690 auf 2686.
Live: Staging-Abgleich Wetter DE (Exit 0, abweichend 453) und EN (Exit 0, abweichend 397) gegen Vorher-Berichte, gefiltert auf Wetter: nur-vorher = genau die 4 entfallenen Orte-Eintraege, nur-nachher leer, Statuswechsel leer, kein Eintrag mit #3205, Zuruecksetzen-Zeile nicht mehr als zusaetzlich gelistet (Ausnahme greift). Orte-Vorlagenauswahl live: alle Eintraege gefunden, kein Zusatz, also kein Mallorca bei Orten. Trip-Eintrag Mallorca bleibt (DE gefunden, EN nicht_pruefbar = Besitzer #3009 unveraendert 2).
**Implementierer:** (aus Spec/Artefakt) Weg B gewaehlt, Weg A verschoebe Picker-Anzeige und Abweichungsmarken.

### Runde 2
**Adversary:** Schwerpunkt Weg B (Code reference: docs/context/einstellungen_neu/elementliste_besitzer.json:4686-4699 zwei Ausnahmen; tests/test_2913_c2_besitzerliste.py:153-163). Bewertung: ehrlich in der Sache, die Bedingung ist identisch (Mockup :514 mit devs aus :491, live VorlageKarte.svelte:161 abweichungen > 0), das Pruefkonto-Trip steht live mit Abweichung. Aber: die Elementliste kennt keinen Abweichungszustand (Mockup-Zeile :514 wird nie gerendert), die Ausnahme ist ein pauschales Muster ohne Zustandsbezug. Zeigt live die Zeile bei 0 Abweichungen (echter Fehler), bleibt das unbemerkt. Mutation M3 (Ausnahme-Muster entfernt): alle 35 Python-Tests und 4 node-Dateien gruen, nur der Live-Abgleich wuerde es fangen, nicht die CI. Das ist eine Luecke der Ratsche, kein Fehler dieser Scheibe; Weg A wuerde die Zeile im Normalzustand pruefen, aber laut Spec mit Folgeabweichungen. Empfehlung: Weg B akzeptabel, Folgeeintrag fuer Abweichungszustand im Mockup. F001 (MEDIUM): Ausnahme nur live bewacht. F002 (LOW): Grund nennt Mockup Z. 511, Zeile steht jetzt auf 514 (Code reference: docs/context/einstellungen_neu/elementliste_besitzer.json:4690).
Die zwei entfernten Eintraege mit Besitzer #3151 (Code reference: tests/test_2913_c2_besitzerliste.py:154): ihre IDs gibt es nicht mehr, Besitzer auf verwaiste IDs roetet den Kern-Test (#3008). 4 auf 2 ist folgerichtig und im Testkommentar begruendet; der Wert 4 war nur der Ausgangszustand. Verbleibend 2 Trip-Eintraege. RED-Test frontend/e2e/feat3205_elementliste_vorlagen_je_art.test.ts:1 prueft AC-1 und AC-2 (jetzt gruen).
Kein Produktcode geaendert (AC-6). AC-7 Soll/Ist-Bild nicht von mir; Datengrundlage (Live-Orte-Auswahl ohne Mallorca) belegt.
**Implementierer:** keine Gegenrede; F001 und F002 nicht blockierend.

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`). Feld devs im Mockup: nur durch Bedienaktionen geschrieben (Zeilen 764-797), im Normalzustand 0; Bedingung davor: Nutzeraktion. Test fuer diesen Weg: keiner (Abweichungszustand nicht in der Elementliste), siehe F001.

## Verdict
Finding:
  ID: F001
  Severity: MEDIUM
  Category: edge_case
  Code reference: docs/context/einstellungen_neu/elementliste_besitzer.json:4686
  Description: Ausnahme fuer die Zuruecksetzen-Zeile ist ein pauschales Muster ohne Zustandsbezug; Mutation M3 (Muster entfernt) laesst alle Offline-Tests gruen.
  Spec requirement: AC-3 — Zeile nur bei Abweichungen, Mockup und Staging stimmen im Zustand ueberein
  Conflict: Zeile bei 0 Abweichungen live bliebe unbemerkt; Abweichungszustand fehlt in der Elementliste.
  Remediation: Folgeticket: Abweichungszustand im Mockup und in der Elementliste erfassen, Ausnahme dann streichen.

Finding:
  ID: F002
  Severity: LOW
  Category: anti_pattern
  Code reference: docs/context/einstellungen_neu/elementliste_besitzer.json:4690
  Description: Grund nennt Mockup Z. 511, die Zeile steht inzwischen auf 514.
  Spec requirement: AC-3 — nachvollziehbare Begruendung
  Conflict: veraltete Zeilenangabe.
  Remediation: Zeilenangabe entfernen oder korrigieren.

Confirmation:
  AC: AC-1
  Code reference: docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html:362
  Evidence: eigeneJeArt-Filter im Picker; M1 und M2 rot; Live-Orte-Auswahl ohne Mallorca (DE und EN)
  Status: CONFIRMED

Confirmation:
  AC: AC-2
  Code reference: frontend/e2e/feat3205_elementliste_vorlagen_je_art.test.ts:52
  Evidence: Trip-Auswahl fuehrt Mallorca; live DE gefunden, EN nicht_pruefbar (Besitzer #3009)
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte:161
  Evidence: gleiche Bedingung wie Mockup Zeile 514; Weg B ehrlich, mit F001 und F002
  Status: CONFIRMED

Confirmation:
  AC: AC-4
  Code reference: docs/context/einstellungen_neu/elementliste.json:4
  Evidence: Vorher/Nachher DE und EN Wetter: nur-vorher genau 4 Orte-Eintraege, keine Statuswechsel, nichts neu
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: tests/test_2913_c2_besitzerliste.py:158
  Evidence: #3205 0, #3009 2; 35 Python-Tests gruen; live kein Eintrag mit #3205
  Status: CONFIRMED

Confirmation:
  AC: AC-6
  Code reference: frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts:71
  Evidence: nur Mockup, Listen und Tests geaendert, kein Produktcode
  Status: CONFIRMED

Confirmation:
  AC: AC-7
  Code reference: docs/specs/modules/feat_3205_vorlagen_mockup.md:100
  Evidence: Datenlage Mockup gleich Live belegt; das Bild selbst ist nicht Teil dieses Laufs
  Status: CONFIRMED

═══════════════════════════════════════
VERDICT: VERIFIED
═══════════════════════════════════════
Tests: node 64 passed, Python 35 passed, 0 failed, 0 übersprungen
Live-Abgleich Wetter DE/EN: Exit 0, keine #3205-Eintraege, keine neue Abweichung
Mutationen M1, M2 gefangen; M3 nicht gefangen (F001, MEDIUM, nicht blockierend)

## Geprüfte Dateien

- sha256:fe6f2c75430d1ec60c10968ed8e884804540641a6945dfd475b6f47b02769a53  docs/context/einstellungen_neu/elementliste.json
- sha256:cc3f70787b42687be25be1a0f7979ec1b1f124907fa2618c2282aad82aa9af01  docs/context/einstellungen_neu/elementliste_besitzer.json
- sha256:24f6c2a420cddac018c1cf58e1893430dba2d20477e1374d400a1cea5765b1b8  docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html
- sha256:5717a92152d78f4c87675f32aea808561b553c69abc06ae272da9f86038fb99e  docs/specs/modules/feat_3205_vorlagen_mockup.md
- sha256:606aca865e0fe07f785d5c5b172d916f7e3aad19c3bcb7ff05de19b4eebc3d9b  frontend/e2e/feat3205_elementliste_vorlagen_je_art.test.ts
- sha256:fd7137cf1222dba6a86bc9b4526dc62e7fef1e2491120abeaeb76ec6da031aad  frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts
- sha256:7d2276aa35d3829323331227ebff904418298864fa56b228e8880aa4abccad7f  frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte
- sha256:8514a93cf67516179979bac30f23ffdcc0fdd0c6027d8c4d9100944b8ad3d934  tests/test_2913_c2_besitzerliste.py

## Prüfbasis

- base: 8d81a1775cd41b90b2db29fb59c9f607041f4a30
- blob:20d9e30d49f1274576bc7404058ac8b35f5f6770  docs/context/einstellungen_neu/elementliste.json
- blob:8f4c3d278d1bd436a999a926f28f50856c07bf9d  docs/context/einstellungen_neu/elementliste_besitzer.json
- blob:81e6c16893ea3aa233688932f204e3fd2ce6df39  docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html
- blob:7979bf101d98f975b434da799442adb72514e467  docs/specs/modules/feat_3205_vorlagen_mockup.md
- blob:fb56b2eab81bddb7dcd7b656e6bd3f7c14f43f81  frontend/e2e/feat3205_elementliste_vorlagen_je_art.test.ts
- blob:df4edc4768fe0158b35ffc4809528607d0d06373  frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts
- blob:c44d2883805ee9d1f8890618f2c721b68158108c  frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte
- blob:bc148a31bd0318f095838952b96a715ef03f7434  tests/test_2913_c2_besitzerliste.py

## Geprüfte Dateien

- sha256:fe6f2c75430d1ec60c10968ed8e884804540641a6945dfd475b6f47b02769a53  docs/context/einstellungen_neu/elementliste.json
- sha256:cc3f70787b42687be25be1a0f7979ec1b1f124907fa2618c2282aad82aa9af01  docs/context/einstellungen_neu/elementliste_besitzer.json
- sha256:24f6c2a420cddac018c1cf58e1893430dba2d20477e1374d400a1cea5765b1b8  docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html
- sha256:5717a92152d78f4c87675f32aea808561b553c69abc06ae272da9f86038fb99e  docs/specs/modules/feat_3205_vorlagen_mockup.md
- sha256:606aca865e0fe07f785d5c5b172d916f7e3aad19c3bcb7ff05de19b4eebc3d9b  frontend/e2e/feat3205_elementliste_vorlagen_je_art.test.ts
- sha256:fd7137cf1222dba6a86bc9b4526dc62e7fef1e2491120abeaeb76ec6da031aad  frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts
- sha256:7d2276aa35d3829323331227ebff904418298864fa56b228e8880aa4abccad7f  frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte
- sha256:8514a93cf67516179979bac30f23ffdcc0fdd0c6027d8c4d9100944b8ad3d934  tests/test_2913_c2_besitzerliste.py

## Prüfbasis

- base: 8d81a1775cd41b90b2db29fb59c9f607041f4a30
- blob:20d9e30d49f1274576bc7404058ac8b35f5f6770  docs/context/einstellungen_neu/elementliste.json
- blob:8f4c3d278d1bd436a999a926f28f50856c07bf9d  docs/context/einstellungen_neu/elementliste_besitzer.json
- blob:81e6c16893ea3aa233688932f204e3fd2ce6df39  docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html
- blob:7979bf101d98f975b434da799442adb72514e467  docs/specs/modules/feat_3205_vorlagen_mockup.md
- blob:fb56b2eab81bddb7dcd7b656e6bd3f7c14f43f81  frontend/e2e/feat3205_elementliste_vorlagen_je_art.test.ts
- blob:df4edc4768fe0158b35ffc4809528607d0d06373  frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts
- blob:c44d2883805ee9d1f8890618f2c721b68158108c  frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte
- blob:bc148a31bd0318f095838952b96a715ef03f7434  tests/test_2913_c2_besitzerliste.py

## Geprüfte Dateien

- sha256:fe6f2c75430d1ec60c10968ed8e884804540641a6945dfd475b6f47b02769a53  docs/context/einstellungen_neu/elementliste.json
- sha256:cc3f70787b42687be25be1a0f7979ec1b1f124907fa2618c2282aad82aa9af01  docs/context/einstellungen_neu/elementliste_besitzer.json
- sha256:24f6c2a420cddac018c1cf58e1893430dba2d20477e1374d400a1cea5765b1b8  docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html
- sha256:5717a92152d78f4c87675f32aea808561b553c69abc06ae272da9f86038fb99e  docs/specs/modules/feat_3205_vorlagen_mockup.md
- sha256:606aca865e0fe07f785d5c5b172d916f7e3aad19c3bcb7ff05de19b4eebc3d9b  frontend/e2e/feat3205_elementliste_vorlagen_je_art.test.ts
- sha256:fd7137cf1222dba6a86bc9b4526dc62e7fef1e2491120abeaeb76ec6da031aad  frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts
- sha256:7d2276aa35d3829323331227ebff904418298864fa56b228e8880aa4abccad7f  frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte
- sha256:8514a93cf67516179979bac30f23ffdcc0fdd0c6027d8c4d9100944b8ad3d934  tests/test_2913_c2_besitzerliste.py

## Prüfbasis

- base: 8d81a1775cd41b90b2db29fb59c9f607041f4a30
- blob:20d9e30d49f1274576bc7404058ac8b35f5f6770  docs/context/einstellungen_neu/elementliste.json
- blob:8f4c3d278d1bd436a999a926f28f50856c07bf9d  docs/context/einstellungen_neu/elementliste_besitzer.json
- blob:81e6c16893ea3aa233688932f204e3fd2ce6df39  docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html
- blob:7979bf101d98f975b434da799442adb72514e467  docs/specs/modules/feat_3205_vorlagen_mockup.md
- blob:fb56b2eab81bddb7dcd7b656e6bd3f7c14f43f81  frontend/e2e/feat3205_elementliste_vorlagen_je_art.test.ts
- blob:df4edc4768fe0158b35ffc4809528607d0d06373  frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts
- blob:c44d2883805ee9d1f8890618f2c721b68158108c  frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte
- blob:bc148a31bd0318f095838952b96a715ef03f7434  tests/test_2913_c2_besitzerliste.py
