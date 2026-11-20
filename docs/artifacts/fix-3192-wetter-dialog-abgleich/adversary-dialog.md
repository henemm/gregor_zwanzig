# Adversary Dialog — fix-3192-wetter-dialog-abgleich
Spec: docs/specs/modules/fix_3192_wetter_dialog_abgleich.md
Datum: 2026-11-20 07:32

## Checkliste
- [x] **Input:** Staging-Abgleich `--scope wetter` (DE, EN) mit dem Prüfkonto; Browser-Test für F004.
- [x] **Output:** Wetter-Dialog-Einträge werden auf Mockup-Datenlage gemessen; Besitzerliste ohne `#3111`.
- [x] **Side effects:** Prüf-Datensätze werden angelegt und im selben Lauf gelöscht; Produktdaten und GR221-Seed unverändert.
- [x] **AC-1:** Given der Abgleich legt für Trip und Orte je zwei Prüf-Datensätze an / When die Grenzen-Abschnitte und die Vorlage-Abschnitte gemessen werden / Then misst „mit Abweichung“ (gültiger Grenzen-Override je Briefing-Metrik gemäß erlaubter Seite, Gewitter über `thunder`) die `grenzen-*`-Einträge und „ohne Abweichung“ die `vorlage-*`-Einträge, und die Wahl der Seite je Abschnitt ist eine reine, unit-getestete Funktion.
- [x] **AC-2:** Given die Mockup-Datenlage / When der Abgleich die Vorlagen-Bestätigung herstellt / Then ist beim Trip „Alpen-Trekking“ aktiv und „Wandern“ das Wechselziel, bei Orten „Allgemein“ aktiv und „Alpen-Trekking“ das Wechselziel mit drei Orten („für diese Orte“); fehlt das Ziel in der Vorlagenliste, meldet der Abgleich „nicht herstellbar“ mit Grund und nie still, und die erste andere Vorlage dient nur als Ersatz, wenn es kein Mockup-Ziel gibt.
- [x] **AC-3:** Given der Abgleich läuft gegen das Prüfkonto / When er startet und endet / Then liegt je Art (Trip, Vergleich) eine eigene Vorlage mit Beschreibung „aus GR221 gespeichert“ im Prüf-Datensatz, Reste eines früheren Abbruchs sind vorher gelöscht, alles ist im `finally` aufgeräumt, und der GR221-Seed des Prüfkontos ist danach unverändert.
- [x] **AC-4:** Given ein Dialog mit Platzhaltertext in einem mehrzeiligen Textfeld / When der Abgleich die sichtbaren Texte sammelt / Then erscheint der Platzhalter des Textfelds in der Liste wie der eines einzeiligen Felds.
- [x] **AC-5:** Given die #3111-Texte tragen noch kein Englisch in der Elementliste / When die Elementliste neu erzeugt wird / Then enthalten sie `text_en`, der Pin `ALT_SHA` ist mit Begründung nachgezogen, und Anzahl 2646 sowie Mockup-Hash sind unverändert.
- [x] **AC-6:** Given der Staging-Abgleich ist in Deutsch und Englisch gelaufen / When die Besitzerliste ausgewertet wird / Then sind alle als gefunden belegten `#3111`-Einträge entfernt, jeder verbleibende Eintrag ist begründet umgehängt (#3151 Mockup-Beispieldaten, #3189 Herkunftszeile, #3190 Speichern-Dialog, #3194 EN-Sollwert zusammengesetzter Dialogtexte nicht automatisch zuordenbar), kein Eintrag bleibt an #3111, der Zählwächter stimmt, und der EN-Zuordnungstest ist grün.
- [x] **AC-7:** Given der Abgleich bedient die Wetter-Dialoge auf den neuen Datensätzen / When während der Bedienung eine Schreibanfrage ausgelöst wird / Then gilt das weiterhin als Fehlschlag des Abgleichs (lesend, #2966 AC-7); das Anlegen und Aufräumen der Prüf-Datensätze liegt außerhalb der Bedienung.
- [x] **AC-8:** Given Trip oder Orte mit geöffnetem Wetter-Reiter / When der Nutzer eine eigene Vorlage mit Beschreibung speichert / Then erscheint sie ohne Neuladen im Vorlagen-Menü als „eigene · <Beschreibung>“, und die Testdaten sind danach gelöscht.

## Dialog

### Runde 1
**Adversary:** Behauptung "alles gruen" nicht geglaubt. Tests selbst gelaufen: node 335 pass/0 fail/0 skipped, pytest Besitzerliste gruen (adversary-test-output.txt). Dann 17 String-Mutationen mit externer Sicherung (Scratchpad), je Node- und pytest-Lauf, danach zurueckkopiert.
Gefangen (13): wechselZiel trip->skitouren; datensatzFuerAbschnitt vertauscht; upper absteigend; lower absteigend; eingabeText ohne TEXTAREA; thunder entfernt; wechselZiel-Fallback `if(true)`; orte:3->2; pluralPasst invertiert; Plural-Pruefung in musterTreffer bzw. musterAufgeloest entfernt (je einzeln); ALT_ANZAHL (Zaehlwaechter 2646).
UEBERLEBT (4, nur im Live-Spec, kein Unit-/Struktur-Test):
- M8 sichtbareTexte-Inline-Regel ohne HTMLTextAreaElement (frontend/e2e/elementliste-abgleich.staging.spec.ts:123) -> kein Test faengt es; eingabeText (Spiegel) ist geprueft, die tatsaechlich wirkende Browser-Regel nicht. Nur ein Staging-Lauf mit textarea-Dialog haette es.
- M9 Verdrahtung datensatzFuerAbschnitt -> seitenId (:521): immer 'ohne_abweichung' ueberlebt; die reine Funktion ist geprueft, ihr Einsatz nicht.
- M10 EIGENE_VORLAGE_BESCHREIBUNG (:237) und M12 aktiveDerVorlage-Auswahl (:285) ohne Wirkung auf Unit-Tests.
- M11 Aufraeum-Push der eigenen Vorlage (:358) entfernt -> nichts rot (Leck bis zum naechsten Lauf, der Reste per Name vorab loescht).
**Implementierer:** (nicht anwesend; Befund aus Code und Belegen)

### Runde 2
**Adversary:** Zweite Runde: Gegenprobe ob Live-Belege die Ueberlebenden abdecken. DE-Abgleich 156/156 gefunden und EN 52 gefunden/0 abweichend belegen M9/M12 (sonst fehlten Grenzen-Texte) indirekt; M10 wird durch den Besitzer-Fall "eigene · aus GR221 gespeichert" nur in EN geprueft (4 Eintraege -> #3151). Aufraeumen: finally-/aufraeumen-Mechanik vorhanden (spec :358, AC-8-Test raeumt im finally), nicht per Test bewacht. Schreibschutz: bedieneAbschnitt/Tripwire-Tests unveraendert gruen (AC-7), Anlegen/Loeschen liegt ausserhalb der Bedienung (wetterPruefDaten vor Schleife). GR221-Seed: Spec loescht nur IDs/Namen mit Praefix E2E-GZ (:249-ff), kein Zugriff auf Seed/"Mallorca Fruehling". Keine Auth-/Credential-Dateien in git status (nur .claude/gate-events.jsonl, herdr-Logs - Hinweis: nicht committen). Besitzerliste: Test erzwingt #3111=0, #3194=100, #3151=4 (Summe 156-52=104). Plural-Aenderung: Alt-SHA bewusst nachgezogen mit Begruendung. AC-8: f004-staging-output 3 passed.
**Implementierer:** (nicht anwesend)

### Findings
Finding:
  ID: F001
  Severity: MEDIUM
  Category: anti_pattern
  Code reference: frontend/e2e/elementliste-abgleich.staging.spec.ts:123
  Description: Inline-Regel in sichtbareTexte (Browserkontext) nimmt HTMLTextAreaElement mit; Mutation ohne Textarea bleibt in allen Unit-Tests gruen.
  Spec requirement: AC-4 — Platzhalter mehrzeiliger Felder erscheinen in der Liste
  Conflict: Zusicherung ist nur im Spiegel eingabeText (Logik) geprueft, nicht dort, wo sie wirkt.
  Remediation: Struktur-Test (wie elementliste_hub_anker_2973) der den Inline-Rumpf auf HTMLTextAreaElement prueft, oder eingabeText-Regel per Funktionsstring in den Browser geben.

Finding:
  ID: F002
  Severity: MEDIUM
  Category: edge_case
  Code reference: frontend/e2e/elementliste-abgleich.staging.spec.ts:521
  Description: Verdrahtung Abschnitt->Datensatz (:521), Aufraeumen der eigenen Vorlage (:358), Beschreibung (:237) und aktive Metriken ohne Abweichung (:285) von keinem Unit-/Strukturtest bewacht; Mutationen M9-M12 ueberlebten.
  Spec requirement: AC-1/AC-3 — Wahl je Abschnitt; Aufraeumen im finally
  Conflict: Nur ein kompletter Staging-Lauf wuerde es merken; Aufraeumen-Verlust bliebe auch dort unbemerkt.
  Remediation: Struktur-Test auf die Aufrufstellen (datensatzFuerAbschnitt vor seitenId; aufraeumen.push je Vorlagenanlage) oder Leckpruefung am Laufende (Liste /api/metric-presets ohne E2E-GZ #3192).

## Confirmations

Confirmation:
  AC: AC-1
  Code reference: frontend/e2e/elementliste_abgleich_logik.ts:471
  Evidence: datensatzFuerAbschnitt und wetterOverrides (:481) unit-getestet, 5 Mutationen gefangen; Verdrahtung siehe F002
  Status: CONFIRMED

Confirmation:
  AC: AC-2
  Code reference: frontend/e2e/elementliste_abgleich_logik.ts:459
  Evidence: wechselZiel/MOCKUP_LAGE (:452); Mutationen Ziel, Fallback, Orte-Zahl gefangen; nicht_herstellbar mit Grund
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: frontend/e2e/elementliste-abgleich.staging.spec.ts:358
  Evidence: Vorab-Loeschen per Name und aufraeumen-Push; Leck-Mutation ueberlebt (F002), Seed nie angefasst
  Status: CONFIRMED

Confirmation:
  AC: AC-4
  Code reference: frontend/e2e/elementliste_abgleich_logik.ts:502
  Evidence: eingabeText inkl. TEXTAREA gefangen; Browser-Inline-Spiegel ungeschuetzt (F001)
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts:47
  Evidence: ALT_SHA mit Begruendung, Anzahl 2646 und Mockup-Hash gepinnt; Mutation ALT_ANZAHL gefangen
  Status: CONFIRMED

Confirmation:
  AC: AC-6
  Code reference: tests/test_2913_c2_besitzerliste.py:129
  Evidence: soll #3111=0,#3194=100,#3151=4; gruen
  Status: CONFIRMED

Confirmation:
  AC: AC-7
  Code reference: frontend/src/lib/__tests__/elementliste_abgleich_bedienplan.test.ts:193
  Evidence: Tripwire-/Bedienplan-Tests gruen, Anlegen ausserhalb der Bedienung
  Status: CONFIRMED

Confirmation:
  AC: AC-8
  Code reference: frontend/e2e/s3a2794-teil3-vorlage.spec.ts:159
  Evidence: Staging 3 passed (f004-staging-output.txt), Aufraeumen im finally
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: scripts/elementliste_aus_mockup.ts:221
  Evidence: pluralPasst, 3 Mutationen gefangen
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: docs/context/einstellungen_neu/elementliste.json:6
  Evidence: text_en vorhanden, 2646 Eintraege
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: docs/context/einstellungen_neu/elementliste_besitzer.json:4571
  Evidence: Umhaengeziel #3194 begruendet
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: frontend/src/lib/__tests__/elementliste_plural_3192.test.ts:30
  Evidence: Plural-Tests, gruen
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: frontend/src/lib/__tests__/elementliste_abgleich_mockuplage_3192.test.ts:48
  Evidence: AC-1/2/4 Unit-Tests, gruen
  Status: CONFIRMED

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Verdict

### Runde 3
**Adversary:** Nach Fix-Loop F001/F002: Node 345 pass/0 fail/0 skipped. 19 neue Mutationen (je Sicherung, exakt zurück, sha256 geprueft).
Gefangen (9, alle in der Logik): seitenIdFuer ohne datensatzFuerAbschnitt; wetterPruefPayload ohne aktiveMetriken-Zweig; ohne wetterOverrides; BESCHREIBUNG='x'; pruefReste ohne Vorlagen-Zweig; ohne Orte-Zweig; ohne WETTER_NAME-Praefix.
UEBERLEBT in der Logik (3): `enabled === true`->`!== false` in aktiveMetrikenDerVorlage (frontend/e2e/elementliste_abgleich_logik.ts:541); `id(t) === ABGLEICH_TRIP_ID` entfernt (pruefReste, :614); eigeneVorlagePayload metrics [] (:598).
UEBERLEBT im Spec (alle Verdrahtungen, kein Test liest sie): addInitScript auf `()=>''` (frontend/e2e/elementliste-abgleich.staging.spec.ts:404); eingabe-Aufruf mit tag 'DIV' (:131); `leckBefunde = []` (:527); Abruffehler-Befunde der Leckpruefung entfernt (:342); expect(leckBefunde) entfernt (:539, per sed, exit 0); seitenIdFuer durch festes 'ohne_abweichung' ersetzt (:505); wetterPruefPayload('trip', 'ohne_abweichung') (:291); eigeneVorlagePayload mit description 'x' (:318); aufraeumen.push der Vorlage entfernt (:321).
Bewertung: die reinen Funktionen sind jetzt bewacht, ihr Einsatz im Spec nicht; die Leckpruefung selbst kann ausgehebelt werden, ohne dass etwas rot wird (Wachposten ohne Wache). Die Original-Ueberlebenden M8-M12 sind damit nur in Teilen geschlossen: M8 (Inline-Regel) existiert nicht mehr, aber der Ersatz (addInitScript/Aufruf) ist ungeprueft; M9, M11 weiter ueberlebend.
**Implementierer:** (nicht anwesend)

### Findings (Runde 3)
Finding:
  ID: F003
  Severity: MEDIUM
  Category: anti_pattern
  Code reference: frontend/e2e/elementliste-abgleich.staging.spec.ts:539
  Description: Verdrahtung im Spec (addInitScript :404, eingabe-Aufruf :131, seitenIdFuer :505, Payload-Aufrufe :291/:318, Vorlagen-Aufraeumen :321, Leckpruefung :527/:539) wird von keinem Unit- oder Strukturtest bewacht; 9 Mutationen ueberleben. Ein Test, der elementliste-abgleich.staging.spec.ts als Quelltext liest (wie elementliste_abgleich_verdrahtung.test.ts), fehlt fuer diese Stellen.
  Spec requirement: AC-1/AC-3/AC-4 — Zusicherung dort pruefen, wo sie wirkt
  Conflict: F001/F002 nur halb behoben: Logik bewacht, Einsatz nicht.
  Remediation: in elementliste_abgleich_verdrahtung.test.ts Quelltext-Pruefungen (doc-compliance) fuer genau diese Aufrufstellen.

Finding:
  ID: F004
  Severity: LOW
  Category: edge_case
  Code reference: frontend/e2e/elementliste_abgleich_logik.ts:541
  Description: aktiveMetrikenDerVorlage (`=== true`), pruefReste-Zweig ABGLEICH_TRIP_ID (:614) und eigeneVorlagePayload.metrics (:598) haben keine Unit-Zusicherung.
  Spec requirement: AC-1/AC-3
  Conflict: Mutationen ueberleben.
  Remediation: je ein Test mit Fall enabled:false/fehlend, Trip-ID-Rest, metrics nicht leer.

Confirmation:
  AC: AC-3
  Code reference: frontend/e2e/elementliste_abgleich_logik.ts:614
  Evidence: pruefReste und Leckpruefung (Spec :331) laufen live gruen (abgleich-de-2), Logikzweige Vorlage/Orte/Praefix gefangen
  Status: CONFIRMED

### Runde 4
**Adversary:** 354 Tests pass/0 fail/0 skipped. Die 12 Ueberlebenden aus Runde 3 erneut mutiert (Sicherung, exakt zurueck, sha256 identisch): 11 gefangen (addInitScript, eingabe-Tag, leckBefunde=[], Abruf-Befunde, seitenIdFuer, Payload trip, eigeneVorlagePayload, Vorlagen-Aufraeumen, enabled===true, ABGLEICH_TRIP_ID, metrics []). Der Wortlaut-Test der expect-Zeile (:616ff, frontend/src/lib/__tests__/elementliste_abgleich_verdrahtung.test.ts) faengt das Loeschen von expect(leckBefunde) (353 pass/1 fail), aber nicht das Auskommentieren mit vorangestelltem `// ` (Regex trifft Kommentartext).
**Implementierer:** (nicht anwesend)

### Findings (Runde 4)
Finding:
  ID: F005
  Severity: LOW
  Category: edge_case
  Code reference: frontend/e2e/elementliste-abgleich.staging.spec.ts:539
  Description: expect(leckBefunde).toEqual([]) kann auskommentiert werden, ohne dass der Verdrahtungstest (:630) rot wird.
  Spec requirement: AC-3 — Aufraeumen/Leckpruefung wirkt
  Conflict: Quelltext-Regex ignoriert Kommentare.
  Remediation: Zeilenanfang `^\s*expect(` im Regex (multiline) verlangen. Nicht blockierend.

Confirmation:
  AC: AC-1
  Code reference: frontend/src/lib/__tests__/elementliste_abgleich_verdrahtung.test.ts:526
  Evidence: Verdrahtungstests fuer seitenIdFuer, Payloads, addInitScript, Aufraeum-Registrierung, Leckpruefung; F001-F004 geschlossen
  Status: CONFIRMED

VERDICT: VERIFIED
Alle 8 ACs belegt, 354 pass/0 fail/0 uebersprungen, Mutationen ausser einer LOW-Randvariante (F005, Kommentar) gefangen, keine Regression, Seed unberuehrt.

## Geprüfte Dateien

- sha256:6926c431981b51772f1ad7596ec1230ea1576079e013c8f370acb442c9dbee38  docs/context/einstellungen_neu/elementliste.json
- sha256:2223048195af066e6839e7ade6b6b06516cc568f1d6f1af5ea9b977e90a675e0  docs/context/einstellungen_neu/elementliste_besitzer.json
- sha256:848a6b848fff13631ea8c3b2e134e44ea8d7e173592324afaaa79e4ffe420b7a  frontend/e2e/elementliste-abgleich.staging.spec.ts
- sha256:6a9392cf7db0a6f33800c4fd1e99e5af2047106e2cfad64cb1f6c2f047c130c0  frontend/e2e/elementliste_abgleich_logik.ts
- sha256:8e8b591515eb28966ecb9dbfc2ca083941bbec5adc131daefd6e6eff79a04807  frontend/e2e/s3a2794-teil3-vorlage.spec.ts
- sha256:2a216755623e188d0ca73cc08e59b89c4ef6560f36f77672b0753d7c86362a0a  frontend/src/lib/__tests__/elementliste_abgleich_bedienplan.test.ts
- sha256:80cd404848168e2c7a73dda8891a6da6d4d7327ba2f214f699591342e22a8a22  frontend/src/lib/__tests__/elementliste_abgleich_mockuplage_3192.test.ts
- sha256:f95bfe955c7d1fb83549eabd9427cf237385eaa4fb74b2ac29ac5efc5d7d1ce2  frontend/src/lib/__tests__/elementliste_abgleich_verdrahtung.test.ts
- sha256:8287e71ec7dfd8e69190958c01d1b555ed3ceee0d4263db7389986fb90f4314b  frontend/src/lib/__tests__/elementliste_plural_3192.test.ts
- sha256:40cff3de8306f7463c64327a50eed739484ec98f9433de07d3db9b35725f9aba  frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts
- sha256:40d9b6c107be9c40bf63a13d22bcddf68136bcc83197d0e1db7b1517388e07fd  scripts/elementliste_aus_mockup.ts
- sha256:05ed806158c4ba3c31cc94b7899c7a71a588678180345828d58471ad214e9e53  tests/test_2913_c2_besitzerliste.py

## Prüfbasis

- base: 3d1da3093060defb4b0ba4ea7d4bcb6994e053bb
- blob:41f5f2668a6df1358c64751f479ef9f4d25f24b7  docs/context/einstellungen_neu/elementliste.json
- blob:2c2464c9228d4626b1495558d92247332b406b74  docs/context/einstellungen_neu/elementliste_besitzer.json
- blob:a11f36dfb91a4f6575d70bc1c901aad999a8a646  frontend/e2e/elementliste-abgleich.staging.spec.ts
- blob:f254069ee0728d3b63a37cf37b097bfe3520f494  frontend/e2e/elementliste_abgleich_logik.ts
- blob:7726f5b686f2f0cd4ed23875973bba4819d620db  frontend/e2e/s3a2794-teil3-vorlage.spec.ts
- blob:e5c5888787cbed3d70062d99e6f3cdc2b8aa8d8e  frontend/src/lib/__tests__/elementliste_abgleich_bedienplan.test.ts
- blob:4db4c79959d2cf20b888ba3ea65ab5f93a188a80  frontend/src/lib/__tests__/elementliste_abgleich_mockuplage_3192.test.ts
- blob:f5f5738ee6d78d505925af82fa5ebb812c1544f9  frontend/src/lib/__tests__/elementliste_abgleich_verdrahtung.test.ts
- blob:7c71b0134ff133adacf64f120bb10783280510e9  frontend/src/lib/__tests__/elementliste_plural_3192.test.ts
- blob:dad71278e77f274f7e341c096a6a1f019d3865be  frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts
- blob:6e4f1322b26a80cd1453c7991f2edf61c03ce753  scripts/elementliste_aus_mockup.ts
- blob:8de9fcf167139adc342419b7c2c95e38c18128f4  tests/test_2913_c2_besitzerliste.py

## Geprüfte Dateien

- sha256:6926c431981b51772f1ad7596ec1230ea1576079e013c8f370acb442c9dbee38  docs/context/einstellungen_neu/elementliste.json
- sha256:2223048195af066e6839e7ade6b6b06516cc568f1d6f1af5ea9b977e90a675e0  docs/context/einstellungen_neu/elementliste_besitzer.json
- sha256:848a6b848fff13631ea8c3b2e134e44ea8d7e173592324afaaa79e4ffe420b7a  frontend/e2e/elementliste-abgleich.staging.spec.ts
- sha256:6a9392cf7db0a6f33800c4fd1e99e5af2047106e2cfad64cb1f6c2f047c130c0  frontend/e2e/elementliste_abgleich_logik.ts
- sha256:8e8b591515eb28966ecb9dbfc2ca083941bbec5adc131daefd6e6eff79a04807  frontend/e2e/s3a2794-teil3-vorlage.spec.ts
- sha256:2a216755623e188d0ca73cc08e59b89c4ef6560f36f77672b0753d7c86362a0a  frontend/src/lib/__tests__/elementliste_abgleich_bedienplan.test.ts
- sha256:80cd404848168e2c7a73dda8891a6da6d4d7327ba2f214f699591342e22a8a22  frontend/src/lib/__tests__/elementliste_abgleich_mockuplage_3192.test.ts
- sha256:f95bfe955c7d1fb83549eabd9427cf237385eaa4fb74b2ac29ac5efc5d7d1ce2  frontend/src/lib/__tests__/elementliste_abgleich_verdrahtung.test.ts
- sha256:8287e71ec7dfd8e69190958c01d1b555ed3ceee0d4263db7389986fb90f4314b  frontend/src/lib/__tests__/elementliste_plural_3192.test.ts
- sha256:40cff3de8306f7463c64327a50eed739484ec98f9433de07d3db9b35725f9aba  frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts
- sha256:40d9b6c107be9c40bf63a13d22bcddf68136bcc83197d0e1db7b1517388e07fd  scripts/elementliste_aus_mockup.ts
- sha256:05ed806158c4ba3c31cc94b7899c7a71a588678180345828d58471ad214e9e53  tests/test_2913_c2_besitzerliste.py

## Prüfbasis

- base: 3d1da3093060defb4b0ba4ea7d4bcb6994e053bb
- blob:41f5f2668a6df1358c64751f479ef9f4d25f24b7  docs/context/einstellungen_neu/elementliste.json
- blob:2c2464c9228d4626b1495558d92247332b406b74  docs/context/einstellungen_neu/elementliste_besitzer.json
- blob:a11f36dfb91a4f6575d70bc1c901aad999a8a646  frontend/e2e/elementliste-abgleich.staging.spec.ts
- blob:f254069ee0728d3b63a37cf37b097bfe3520f494  frontend/e2e/elementliste_abgleich_logik.ts
- blob:7726f5b686f2f0cd4ed23875973bba4819d620db  frontend/e2e/s3a2794-teil3-vorlage.spec.ts
- blob:e5c5888787cbed3d70062d99e6f3cdc2b8aa8d8e  frontend/src/lib/__tests__/elementliste_abgleich_bedienplan.test.ts
- blob:4db4c79959d2cf20b888ba3ea65ab5f93a188a80  frontend/src/lib/__tests__/elementliste_abgleich_mockuplage_3192.test.ts
- blob:f5f5738ee6d78d505925af82fa5ebb812c1544f9  frontend/src/lib/__tests__/elementliste_abgleich_verdrahtung.test.ts
- blob:7c71b0134ff133adacf64f120bb10783280510e9  frontend/src/lib/__tests__/elementliste_plural_3192.test.ts
- blob:dad71278e77f274f7e341c096a6a1f019d3865be  frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts
- blob:6e4f1322b26a80cd1453c7991f2edf61c03ce753  scripts/elementliste_aus_mockup.ts
- blob:8de9fcf167139adc342419b7c2c95e38c18128f4  tests/test_2913_c2_besitzerliste.py
