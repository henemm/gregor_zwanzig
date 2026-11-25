# Adversary Dialog — rework-3366-waisen-loeschen
Spec: docs/specs/modules/rework_3366_waisen_waechter_layout_tab.md
Datum: 2026-11-25 23:10

## Checkliste
- [x] **Input:** Quelltext von `frontend/src`.
- [x] **Output:** Wächter grün, solange die Waisenmenge (ohne `AUSNAHMEN`) exakt `BEKANNTE_WAISEN` entspricht und deren Länge die Konstante `OBERGRENZE_WAISEN` nicht übersteigt; Löschung ohne Funktionsänderung.
- [x] **Side effects:** Keine sichtbare Änderung für Nutzer; Ratschenzahlen und Katalog schrumpfen.
- [x] **AC-1:** Given der Quelltext unter `frontend/src` im Zustand nach der Löschung / When der Waisen-Wächter die Erreichbarkeit ab `routes/` und `src/*.ts` (Alias `$lib`, `.svelte`/`.ts`/`.js`, Barrels, dynamische Importe, Tests nicht als Aufrufer) berechnet / Then ist die Menge der Waisen, nachdem `AUSNAHMEN` (`lib/index.ts`) herausgerechnet wurde, genau `BEKANNTE_WAISEN`, es gilt `BEKANNTE_WAISEN.length <= OBERGRENZE_WAISEN` (feste Literal-Konstante) und der Test ist grün.
- [x] **AC-2:** Given eine neue Datei unter `frontend/src/lib`, die niemand aus `routes/` erreicht und nicht in `BEKANNTE_WAISEN` steht / When der Wächter läuft / Then wird der Test rot und nennt den Dateipfad der neuen Waise; ein neuer Eintrag in die Liste allein genügt nicht, solange `OBERGRENZE_WAISEN` nicht sichtbar erhöht wird.
- [x] **AC-3:** Given ein Eintrag in `BEKANNTE_WAISEN`, der wieder von einer Route erreichbar ist oder dessen Datei nicht mehr existiert / When der Wächter läuft / Then wird der Test rot mit der Meldung "aus der Liste streichen".
- [x] **AC-4:** Given eine Datei, die nur von einem Test oder nur über einen Barrel von einer Route erreicht wird / When der Wächter rechnet / Then gilt sie im ersten Fall als Waise (Tests zählen nicht als Aufrufer) und im zweiten als erreichbar (Barrel wird durchlaufen).
- [x] **AC-5:** Given S2 ist umgesetzt / When das Dateisystem geprüft wird / Then existieren die 6 Dateien `LTCapNote`, `LTChannelPicker`, `LTCutLine`, `LayoutTab`, `channelLayoutsDirty`, `ltIdealRange` unter `layout-tab/` und die 9 gelöschten Barrel-Dateien nicht mehr, `ltChannels.ts` und `lib/index.ts` bestehen weiter, und kein Produktionscode importiert die gelöschten Basisnamen.
- [x] **AC-6:** Given die Löschung der layout-tab-Dateien / When die Zahlenratschen (`BESTAND_OBERGRENZE`, Zählung in `reaktivitaet_waechter`, Katalogschlüssel de/en) geprüft werden / Then stimmen alle Zahlen mit der Messung nach dem Löschen überein, sind nur gesunken, de und en führen dieselbe Schlüsselmenge ohne Schlüssel ohne Verwender, und `HOECHSTSTAND`/ein_katalog bleiben unverändert, weil es für S2 keine Treffer gibt.
- [x] **AC-7:** Given die Seiten und Ansichten, die den Layout-Reiter nicht verwenden (insbesondere Trip- und Vergleichs-Editor, GPX-Import) / When die gesamte Frontend-Suite, der Produktions-Build und `svelte-check` laufen / Then sind alle grün, die GPX-Texte und -Goldens sind unverändert, und für Nutzer gibt es keine sichtbare Änderung.
- [x] **AC-8:** Given `outlookFriendlyCapability.ts` ist eine Waise, wird in S2 aber nicht gelöscht / When der Wächter läuft / Then steht sie in `BEKANNTE_WAISEN` (nicht als erreichbar gewertet) und der Eintrag in `ERHALTEN` des Lösch-Nachweises bleibt bestehen, bis sie in S1 gelöscht wird.

## Findings

Finding:
  ID: F001
  Severity: MEDIUM
  Category: edge_case
  Code reference: frontend/src/lib/__tests__/waisen_waechter.test.ts:169
  Description: Der Selbstnachweis am Mini-Baum bewacht mehrere Kantenarten und Wurzelregeln nicht. Mutationen, die KEIN Test faengt: dynamisches import() aus der Kantenerkennung (KANTE, Zeile 55) entfernen, import.meta.glob entfernen, new URL(..., import.meta.url) entfernen, Tests unter routes/ als Wurzeln zulassen (Zeile 169). Grund: im Mini-Baum liegt das dynamische Ziel (routes/lazy.ts) selbst unter routes/ und ist ohnehin Wurzel; Glob und new URL kommen nicht vor; es gibt keine Testdatei unter routes/. Der Filter !istTest(z) in Zeile 176 ist aequivalent (Tests sind nie Wurzel).
  Spec requirement: AC-1 / AC-4 — dynamische Importe und Barrels werden durchlaufen, Tests zaehlen nicht als Aufrufer
  Conflict: Die Zusicherung ist nur durch meine Planting-Gegenprobe am echten Baum belegt, nicht durch einen dauerhaften Test. Im echten Baum sind die Mutationen heute folgenlos, deshalb bleibt auch der Hauptfall gruen.
  Remediation: Mini-Baum um lib/nurDynamisch.ts (nur per import() aus lib/ erreicht), lib/nurGlob.ts, lib/nurUrl.ts und routes/x.test.ts mit Import einer Waise erweitern und im Kern-Test erwarten.

Finding:
  ID: F002
  Severity: LOW
  Category: anti_pattern
  Code reference: tests/golden/f8_layout_korridor/gpx_gespeichert.en.html:1
  Description: Das englische Review-Golden der GPX-Seite ist veraltet (border-green-200/bg-green-50 statt var(--g-ok-*)); mit GZ_GOLDEN_SCHREIBEN=en wird es anders geschrieben (von mir gemessen, danach wiederhergestellt). Der Test vergleicht nur die de-Golden, das en-Golden ist Review-Hilfe. Die Abweichung ist unabhaengig von #3366 (GPX-Code unveraendert); Zuruecksetzen auf HEAD war richtig.
  Spec requirement: AC-7 — GPX-Goldens unveraendert
  Conflict: kein Widerspruch zur Spec, Nebenbefund fuer das Sammel-Issue.
  Remediation: en-Golden bei Gelegenheit neu schreiben, eigener Schritt.

Finding:
  ID: F003
  Severity: LOW
  Category: edge_case
  Code reference: frontend/src/lib/i18n/__tests__/reaktivitaet_waechter.test.ts:51
  Description: Der Bereich layout-tab/ wurde aus dem Reaktivitaets-Waechter genommen; eine kuenftige .svelte-Datei dort wuerde nicht gescannt. Gemildert: keine .svelte-Datei im Ordner, Messaufbau prueft dateien.length == 2, und eine neue Datei ohne Aufrufer faengt der Waisen-Waechter.
  Spec requirement: AC-6 — Schutzwirkung nicht schwaechen
  Conflict: geringe, bewusst hingenommene Abschwaechung.
  Remediation: keine noetig; Ordner wieder aufnehmen, sobald dort wieder eine Komponente liegt.

## Confirmations

Confirmation:
  AC: AC-1
  Code reference: frontend/src/lib/__tests__/waisen_waechter.test.ts:161
  Evidence: findeWaisen rechnet echte Erreichbarkeit (Wurzeln routes/ und src/*.ts, Alias $lib, Barrel-index, Endungen, Tests weder Wurzel noch Aufrufer); Hauptfall (Waisenmenge == BEKANNTE_WAISEN, 40 Eintraege <= OBERGRENZE_WAISEN 40) gruen; Mutationen M2 (Barrel), M7 (routes-Wurzel), M9 ($lib) rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-2
  Code reference: frontend/src/lib/__tests__/waisen_waechter.test.ts:187
  Evidence: Planting: lib/zzorphan.ts angelegt -> Test rot mit Meldung "lib/zzorphan.ts: neue Waise ohne Aufrufer"; Mutation M6 (Pruefung neuer Waisen entfernt) rot; M4 (Obergrenzenpruefung entfernt) rot; Selbstnachweis "Eintrag ohne Erhoehung bleibt rot".
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: frontend/src/lib/__tests__/waisen_waechter.test.ts:195
  Evidence: Mutation M5 (Erreichbarkeits-Pruefung) rot; N7 (outlookFriendlyCapability aus Liste gestrichen) rot; Selbstnachweis meldet "aus der Liste streichen" fuer erreichbaren und fehlenden Eintrag.
  Status: CONFIRMED

Confirmation:
  AC: AC-4
  Code reference: frontend/src/lib/__tests__/waisen_waechter.test.ts:169
  Evidence: Mini-Baum: nurTest.ts (nur von Test erreicht) ist Waise, Barrel/dynamisch/hooks erreichbar. Planting: ein Test unter routes/ importiert eine Waise -> Waechter bleibt rot (Tests zaehlen nicht). Dynamische Importkette real geplantet -> erreichbar. Luecke der Selbstpruefung siehe F001.
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts:117
  Evidence: 15 Dateien existieren nicht mehr, ltChannels.ts und lib/index.ts bestehen; Suche auf die 6 Basisnamen und die 8 ui-Barrel-Pfade plus email-preview findet nur Kommentare und Tests mit Pfadlisten (issue_462 verbietet die Pfade, issue_390/577 gruen); npm run build Exit 0; Planting eines Imports auf $lib/components/ui/pill bzw. email-preview macht den Loesch-Nachweis rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-6
  Code reference: frontend/src/lib/__tests__/bausteine_waechter_regeln.ts:723
  Evidence: BESTAND 188->184 entspricht genau den 4 entfernten .svelte-Eintraegen (Mutation N5: 183 rot); ink4 -3 entspricht den 3 entfernten Eintraegen; reaktivitaet F8-Zaehlung 1->0 (N6: 9 rot) mit Messaufbau dateien.length==2; de und en layout.json je 83 Schluessel, identische Menge; die 3 entfernten Schluessel ohne Verwender; kein weiterer Schluessel ohne Verwender.
  Status: CONFIRMED

Confirmation:
  AC: AC-7
  Code reference: frontend/src/lib/components/shared/layout-tab/__tests__/f8Pruefstand.ts:74
  Evidence: Gesamte Frontend-Suite 11808 passed, 0 failed (2 skipped, vorbestehend); build Exit 0; GPX-Goldens de unveraendert und gruen; Pruefstand rendert OutputLayoutEditor, Mutationen N1, N2, N3 rot. svelte-check meldet 32 Fehler in nicht beruehrten Dateien, keiner mit geloeschten Pfaden.
  Status: CONFIRMED

Confirmation:
  AC: AC-8
  Code reference: frontend/src/lib/__tests__/waisen_waechter.test.ts:220
  Evidence: outlookFriendlyCapability.ts steht in BEKANNTE_WAISEN und wird als Waise gerechnet (nur ein Test importiert sie); ERHALTEN-Eintrag in trip_pfad_altfeld_loeschnachweis_3297.test.ts:43 besteht; Mutation N7 rot.
  Status: CONFIRMED

Confirmation:
  AC: Input / Output / Side effects
  Code reference: frontend/src/lib/i18n/__tests__/reaktivitaet_waechter.test.ts:178
  Evidence: Mitgezogene Tests: es fiel nur die Pruefung der geloeschten Komponenten weg (AST-Verdrahtung LayoutTab/LTChannelPicker, Wirkort LTCapNote, Layout-Reiter-Render). Lebender Code bleibt geprueft: ltChannels.ts-Funktionen, OutputLayoutEditor (de/en, aria, leer, ohne Detail, Zwei-Nutzer-Fall), Mail-Inhalt-Bausteintexte. Keine Nutzeraenderung.
  Status: CONFIRMED

Confirmation:
  AC: AC-6 / AC-7 (Begleitdatei)
  Code reference: frontend/src/lib/__tests__/ink4_waechter.test.ts:53
  Evidence: Diff gelesen: nur Entfernen oder Umstellen von Eintraegen der geloeschten Dateien bzw. Verweistext; Python-Tests (123 passed) und Frontend-Suite gruen; kein Nutzerverhalten betroffen.
  Status: CONFIRMED

Confirmation:
  AC: AC-6 / AC-7 (Begleitdatei)
  Code reference: frontend/src/lib/i18n/__tests__/deutsch_unveraendert.test.ts:189
  Evidence: Diff gelesen: nur Entfernen oder Umstellen von Eintraegen der geloeschten Dateien bzw. Verweistext; Python-Tests (123 passed) und Frontend-Suite gruen; kein Nutzerverhalten betroffen.
  Status: CONFIRMED

Confirmation:
  AC: AC-6 / AC-7 (Begleitdatei)
  Code reference: frontend/src/lib/i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts:441
  Evidence: Diff gelesen: nur Entfernen oder Umstellen von Eintraegen der geloeschten Dateien bzw. Verweistext; Python-Tests (123 passed) und Frontend-Suite gruen; kein Nutzerverhalten betroffen.
  Status: CONFIRMED

Confirmation:
  AC: AC-6 / AC-7 (Begleitdatei)
  Code reference: frontend/src/lib/components/shared/layout-tab/__tests__/f8KatalogAnker.ts:14
  Evidence: Diff gelesen: nur Entfernen oder Umstellen von Eintraegen der geloeschten Dateien bzw. Verweistext; Python-Tests (123 passed) und Frontend-Suite gruen; kein Nutzerverhalten betroffen.
  Status: CONFIRMED

Confirmation:
  AC: AC-6 / AC-7 (Begleitdatei)
  Code reference: frontend/src/lib/components/shared/layout-tab/__tests__/channelLimitModel.test.ts:210
  Evidence: Diff gelesen: nur Entfernen oder Umstellen von Eintraegen der geloeschten Dateien bzw. Verweistext; Python-Tests (123 passed) und Frontend-Suite gruen; kein Nutzerverhalten betroffen.
  Status: CONFIRMED

Confirmation:
  AC: AC-6 / AC-7 (Begleitdatei)
  Code reference: frontend/src/lib/components/shared/layout-tab/__tests__/layout_korridor_sprache.test.ts:121
  Evidence: Diff gelesen: nur Entfernen oder Umstellen von Eintraegen der geloeschten Dateien bzw. Verweistext; Python-Tests (123 passed) und Frontend-Suite gruen; kein Nutzerverhalten betroffen.
  Status: CONFIRMED

Confirmation:
  AC: AC-6 / AC-7 (Begleitdatei)
  Code reference: tests/fixtures/einstellung_gleich_mail/fallliste_editor.json:722
  Evidence: Diff gelesen: nur Entfernen oder Umstellen von Eintraegen der geloeschten Dateien bzw. Verweistext; Python-Tests (123 passed) und Frontend-Suite gruen; kein Nutzerverhalten betroffen.
  Status: CONFIRMED

Confirmation:
  AC: AC-6 / AC-7 (Begleitdatei)
  Code reference: docs/artifacts/rework-3366-waisen-loeschen/adversary-test-output.txt:1
  Evidence: Diff gelesen: nur Entfernen oder Umstellen von Eintraegen der geloeschten Dateien bzw. Verweistext; Python-Tests (123 passed) und Frontend-Suite gruen; kein Nutzerverhalten betroffen.
  Status: CONFIRMED

## Dialog

### Runde 1
**Adversary:** Spec, Waechter, Loesch-Nachweis und alle 37 gestagten Dateien gegen HEAD gelesen. Baseline: Waechter und Loesch-Nachweis 42 gruen. Mutationen am Waechter (je Sicherung, Wiederherstellung per sha256 identisch): M1 Tests als Aufrufer in der Traversierung -> KEIN Test rot; M2 Barrel ignorieren -> 5 rot; M3 dynamischen import() ignorieren -> KEIN Test rot; M4 Obergrenzenpruefung entfernt -> rot; M5 Erreichbarkeitspruefung entfernt -> rot; M6 Pruefung neuer Waisen entfernt -> rot; M7 routes/-Wurzeln entfernt -> 5 rot; M8 import.meta.glob ignoriert -> KEIN Test rot; M9 $lib-Aufloesung entfernt -> 5 rot; M10 routes-Tests als Wurzeln -> KEIN Test rot; M11 new URL ignoriert -> KEIN Test rot. Folge: F001. Gegenprobe am echten Baum durch Planting (temporaere Dateien, danach geloescht): neue Waise -> rot mit Pfad; Waise, die nur ein Test unter routes/ importiert -> bleibt rot; Waise nur ueber dynamischen import aus lib/ erreicht -> gruen (erreichbar). Loeschung: Suche auf alle 6 Basisnamen und die Barrel-Pfade in frontend/src, e2e, tests, docs/reference, internal, api, src, scripts: nur Kommentare und Tests mit Pfadlisten, kein Produktionsaufrufer; build Exit 0.
**Implementierer:** keine Rueckmeldung (Gedankengang bewusst nicht gesehen).

### Runde 2
**Adversary:** Mitgezogene Tests per Diff gegen HEAD: channelLimitModel verliert nur die AST-Verdrahtungsfaelle der geloeschten Komponenten, die reine Funktion ltChannelsFor bleibt geprueft; layout_korridor_sprache ersetzt den Layout-Reiter-Render durch OutputLayoutEditor (de/en, aria, leer, ohne Detail, Zwei-Nutzer); verloren geht nur der Wirkort-Fall LTCapNote. Die Stelle in f8Pruefstand.ts (ausgabeLayoutRendern) gelesen: Props vollstaendig; Mutationen N1 (hideDetailBucket), N2 (leer), N3 (Kanal fest) je rot. Ratschen: N4 (BESTAND 300) bleibt gruen, bewusst, Ratschen schuetzen nur nach oben; N5 (183) rot, also exakt 184 gemessen; N6 (Zaehlung 9) rot. Loesch-Nachweis: Mutationen N8 und N9 im Sollzustand folgenlos, deshalb Gegenprobe per Planting: Import auf $lib/components/ui/pill (Barrel als Verzeichnis) und auf email-preview macht den Test rot. Schluessel: de und en je 83 identisch, 3 entfernte Schluessel ohne Verwender. Gesamtsuite 11808 passed, 0 failed; Python-Tests 123 passed; svelte-check 32 vorbestehende Fehler in nicht beruehrten Dateien. Golden gpx_gespeichert.en.html veraltet, nicht von #3366 verursacht (F002).
**Implementierer:** keine Rueckmeldung.


## Herkunft der Vorbedingungen

Kein Feld mit Test-Zuweisung gefunden — nichts zu pruefen.

Hinweis: Die Aenderung ist reine Loeschung und Umstellung von Tests, es entstehen keine neuen Schreibstellen im Produktivcode.

## Verdict
**VERIFIED**

Alle 8 ACs und die 3 Rahmenpunkte bewiesen. Tests: Frontend-Suite 11808 passed, 0 failed; Zielmenge 393 passed; Python-Tests 123 passed; build Exit 0. Nacharbeit ohne Blocker: F001 MEDIUM, F002 LOW, F003 LOW.

## Geprüfte Dateien

- sha256:ea92dadacca35e5ebc023a8aedd35b61d2cbb57d10c9232901f83d0be4723a3e  docs/artifacts/rework-3366-waisen-loeschen/adversary-test-output.txt
- sha256:8d86451109572d9c542688e1c61bb9775b37c071f5692b1eb755b050bce3970e  frontend/src/lib/__tests__/bausteine_waechter_regeln.ts
- sha256:912684ab516ec22629c676eda6e1a34c8a224681eeccad0c92310d13d7944613  frontend/src/lib/__tests__/ink4_waechter.test.ts
- sha256:1a6205c3cca423786461d0703fba99c9d4d454bc49d553fba72d49cfc927e8ce  frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts
- sha256:efeea8d6f4adc290da9e914afe9d7d3f54862f31015e2c6250a5e3068fc2500e  frontend/src/lib/__tests__/waisen_waechter.test.ts
- sha256:30dfcc76057f80e365a51bf65d581f97f9f2ced790e2d6f4e6a989cfae67f48d  frontend/src/lib/components/shared/layout-tab/__tests__/channelLimitModel.test.ts
- sha256:07122edb7b8e3bf4b53f82f4f4426d6a97133c666246ecd96e61e9dd787fe910  frontend/src/lib/components/shared/layout-tab/__tests__/f8KatalogAnker.ts
- sha256:84cc44559668e305ed8593bf3dd084ef4e043ce7acff9ac57c41b5db90cffd1d  frontend/src/lib/components/shared/layout-tab/__tests__/f8Pruefstand.ts
- sha256:cbfef9810b9e31ad417fad671ffe7f655fd21f4a5ec5264d7f32529523916672  frontend/src/lib/components/shared/layout-tab/__tests__/layout_korridor_sprache.test.ts
- sha256:8132985f3e5bf9cd14e7f094c6158ca91ecad755287d028e773f7712a556494b  frontend/src/lib/i18n/__tests__/deutsch_unveraendert.test.ts
- sha256:590035117979e4223765e3ed21c9bfc98cc6350637ab83d6f8a8d3c6c1b368ca  frontend/src/lib/i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts
- sha256:fc9f4e1f33216f354ba048580befb022d5ad822ebdcd8c46ac87debd65ada55b  frontend/src/lib/i18n/__tests__/reaktivitaet_waechter.test.ts
- sha256:fecbea7f78a7c7b9c1f2886e453289c21ced4dd28c00a57f4dd68a99735f1fcb  tests/fixtures/einstellung_gleich_mail/fallliste_editor.json
- sha256:64e8ea223c255b05e194f28253f2f83003104dcb2101dc0deb423e69fb6b0cd9  tests/golden/f8_layout_korridor/gpx_gespeichert.en.html

## Prüfbasis

- base: 7dc4222668ec939439042cfb2c890344ebbf9825
- blob:771d4a5c6ba6ae95765284e581bd964749709f69  docs/artifacts/rework-3366-waisen-loeschen/adversary-test-output.txt
- blob:66d3e50fe20440e1d765e38c9d3cf1c39c09b898  frontend/src/lib/__tests__/bausteine_waechter_regeln.ts
- blob:941b9a6365682e07af935dc2075d7443866a5b7c  frontend/src/lib/__tests__/ink4_waechter.test.ts
- blob:c663fdd29e49e53bbf927b65fa3198c86a5e43e4  frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts
- blob:d84c8aa16d471f0b6fed79c62425938298dbbfd4  frontend/src/lib/__tests__/waisen_waechter.test.ts
- blob:7d21c0fa02ed34dee9a5987ec507a4bc32f3ca00  frontend/src/lib/components/shared/layout-tab/__tests__/channelLimitModel.test.ts
- blob:bfd28dfa2d30bd3548872848bb805eba6427bd04  frontend/src/lib/components/shared/layout-tab/__tests__/f8KatalogAnker.ts
- blob:f7cc384dc31fe8e017263677d3b59adbaffced6d  frontend/src/lib/components/shared/layout-tab/__tests__/f8Pruefstand.ts
- blob:0e8d3556abc2b771761bdb2ba3c173b67316dab9  frontend/src/lib/components/shared/layout-tab/__tests__/layout_korridor_sprache.test.ts
- blob:b0210e1a2f418f3f537ffbaec730f201ecba9fd3  frontend/src/lib/i18n/__tests__/deutsch_unveraendert.test.ts
- blob:ceacdd10276044c7254339cde5825bf765c6221f  frontend/src/lib/i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts
- blob:d01a4b59eb4d34478ed93d19e22c0fd2c5e68a75  frontend/src/lib/i18n/__tests__/reaktivitaet_waechter.test.ts
- blob:01008848854e62591a71c847f092d93333d5e9cb  tests/fixtures/einstellung_gleich_mail/fallliste_editor.json
- blob:bfdd273dc4cf2f628f0344c0d22d0769b7436463  tests/golden/f8_layout_korridor/gpx_gespeichert.en.html
