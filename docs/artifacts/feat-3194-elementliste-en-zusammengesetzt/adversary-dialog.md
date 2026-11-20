# Adversary Dialog — feat-3194-elementliste-en-zusammengesetzt
Spec: docs/specs/modules/feat_3194_elementliste_en_zusammengesetzt.md
Datum: 2026-11-20 19:46

## Checkliste
- [x] **Input:** Mockup-Text (DE), echter Katalog, Tabelle `ZUSAMMENGESETZT`.
- [x] **Output:** je passendem Text `text_en` aus den EN-Katalogtexten in Folge, `luecke: false`; sonst unverändert Lücke.
- [x] **Side effects:** neu erzeugte `elementliste.json`, kleinere Besitzerdatei, EN-Abgleich meldet für diese Texte `gefunden` statt `nicht_pruefbar`.
- [x] **AC-1:** Given ein Mockup-Text, der genau der verketteten DE-Folge eines Tabellenmusters entspricht (z. B. „obenzu viel“) / When der Generator `text_en` ermittelt / Then entsteht `text_en` exakt aus den EN-Katalogtexten derselben Schlüssel in derselben Reihenfolge mit derselben Fuge, und der Eintrag ist keine Lücke.
- [x] **AC-2:** Given ein Muster mit Platzhalter `{vorlage}` (Grünhinweis, „keins“-Hinweis, jeweils mit „Abweichend von der Vorlage „Allgemein““) / When der Generator den Text zuordnet / Then trägt `text_en` den Platzhalter `{vorlage}` statt des konkreten Vorlagenamens, und andere Vorlagennamen („Alpen-Trekking“) treffen dasselbe Muster.
- [x] **AC-3:** Given ein Text, bei dem nicht ALLE Teile der Folge im DE-Katalog exakt passen (falsche Fuge, fehlender oder zusätzlicher Teil) oder ein Schlüssel keinen EN-Wert hat / When der Generator ihn verarbeitet / Then bleibt der Eintrag Lücke und es entsteht kein EN-Text ohne Katalogquelle.
- [x] **AC-4:** Given die bisherigen Zuordnungen nach den Regeln a–f / When die Elementliste mit der neuen Regel neu erzeugt wird / Then bleiben alle bereits zugeordneten Einträge unverändert, und die Liste unterscheidet sich von der bisherigen nur in den Einträgen, die zuvor Lücke waren.
- [x] **AC-5:** Given die Besitzerdatei nach der Neuerzeugung / When der Zählwächter läuft / Then trägt „#3194“ nur noch die echten Restfälle (Eigenname „Mallorca Frühling“, EN-Metriknamen aus dem Register, EN-Zusatztexte), jeder dieser Einträge ist weiterhin Lücke, und die Wächter-Zahl stimmt mit der Datei überein.
- [x] **AC-6:** Given der EN-Abgleich `--scope wetter --sprache en` gegen Staging / When er mit der neu erzeugten Liste läuft / Then führt die neue Regel zu keiner neuen Abweichung gegenüber dem Stand davor, und die 100 gelösten Einträge sind nicht mehr `nicht_pruefbar`.
- [x] **AC-7:** Given der Erzeuger / When er zweimal hintereinander auf demselben Mockup und Katalog läuft / Then ist die erzeugte `elementliste.json` byte-identisch.

## Dialog

### Runde 1
**Adversary:** Erzeuger-Diff gelesen (scripts/elementliste_aus_mockup.ts:299-348). Regel g hängt nach zeichenEn/segmenteEn nur bei Lücke ein. Programmcheck gegen HEAD-Liste: 2662 Einträge, genau 100 verändert, alle vorher luecke=true, geändert nur i18n_key/text_en/muster/luecke, keiner bleibt Lücke; Schlüssel: hinweis 38, oben_1 34, unten_1 20, keins_gruen 4, ersetzt_route 2, ersetzt_vergleich 2. Stichprobe 12 Einträge (A–D) gelesen: text_en = Katalog-EN-Folge wortgleich, {vorlage} bleibt Platzhalter. Besitzerdatei: 692 -> 592, 0 hinzugefügt, 100 entfernt, Reihenfolge der übrigen unverändert; #3194 = 8 (Test test_2913_c2_besitzerliste.py:138), Python-Test grün. Determinismus: Erzeuger zweimal, sha256 b62d1927... beide Male identisch zur Arbeitskopie. Node-Gesamtlauf 8375 Tests, 8371 pass, 0 fail, 3 skipped.
**Implementierer:** (nicht befragt, Kontextisolation)

### Runde 2
**Adversary:** Mutations-Gegenprobe (String-Ersetzung, Sicherung scratchpad/m3194.bak, sha256 vorher = nachher fadff502...): Fuge B ohne Leerzeichen -> 4 rot; Schlüsselfolge oben_2/oben_1 -> 5 rot; Bedingung „jeder Schlüssel hat EN“ entfernt -> 1 rot; D2-Zeile gelöscht -> 2 rot; Regel g vor a–f -> 0 rot (Test 3194 UND erzeugte Liste unverändert: gleichwertige Mutation auf echten Daten, aber AC-4-Vorrang ist nirgends als Test festgenagelt, Finding F001 LOW). `muster` null bei A/D: kein Verbraucher außer dem Erzeuger; die Übersicht-Prüfsumme deckt es. Prüfsumme in elementliste_uebersicht_2969.test.ts:56 geändert nur wegen der 100 Einträge (Liste vor/nach identisch außer diesen). Live-Texte: die App setzt den Rumpf live aus [ersetzt_*, verlust?, bleibt] zusammen; mit Verlust-Satz oder Einzahl „diesen Ort“ passt keine Zeile -> bleibt Lücke, keine Falschzuordnung (Mockup enthält 4 Rümpfe, keinen mit „diesen Ort“). Nebenbefund F002 LOW: „uppertoo much“/„lowertoo little“ ist wortgleich Katalog (Fuge leer wie die App), aber als EN-Soll unschön; Katalogthema. AC-6 (Staging-Abgleich) nicht live gefahren; die 100 Einträge tragen nun i18n_key und text_en, Beleg indirekt.
**Implementierer:** (nicht befragt)

## Findings und Bestätigungen

Finding:
  ID: F001
  Severity: LOW
  Category: edge_case
  Code reference: scripts/elementliste_aus_mockup.ts:299
  Description: Einhängen von Regel g nach a–f ist per Test nicht abgesichert; Mutation „Regel g zuerst“ bleibt grün.
  Spec requirement: AC-4 — bereits zugeordnete Einträge bleiben unverändert
  Conflict: Nur Gleichheit auf den heutigen Daten schützt; ein künftiger Tabellenkonflikt würde ältere Zuordnung still überschreiben.
  Remediation: Test mit Text, den a–f und g unterschiedlich zuordnen würden.

Finding:
  ID: F002
  Severity: LOW
  Category: anti_pattern
  Code reference: scripts/elementliste_aus_mockup.ts:314
  Description: A1/A2 verketten ohne Fuge, EN ergibt „uppertoo much“.
  Spec requirement: AC-1 — EN exakt aus Katalog mit derselben Fuge
  Conflict: Spec-konform, aber Katalog-Stil; kein Verstoß.
  Remediation: Katalogtexte in eigenem Ticket prüfen.

Confirmation:
  AC: AC-1
  Code reference: scripts/elementliste_aus_mockup.ts:328
  Evidence: zusammengesetztEn verkettet DE/EN mit Fuge; 100 Einträge wortgleich Katalog.
  Status: CONFIRMED

Confirmation:
  AC: AC-2
  Code reference: frontend/src/lib/__tests__/elementliste_zusammengesetzt_3194.test.ts:65
  Evidence: {vorlage} bleibt im EN, „Alpen-Trekking“ trifft dasselbe Muster (Liste: 38+4 Einträge).
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: scripts/elementliste_aus_mockup.ts:340
  Evidence: DE und EN je Schlüssel geprüft, vollständiger Regex-Abgleich; Mutation ohne EN-Bedingung rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-4
  Code reference: docs/context/einstellungen_neu/elementliste.json:1
  Evidence: Programmvergleich gegen HEAD: nur 100 vorherige Lücken geändert.
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: docs/context/einstellungen_neu/elementliste_besitzer.json:1
  Evidence: 100 entfernt, nichts sonst geändert, Rest 8; Python-Test grün.
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: tests/test_2913_c2_besitzerliste.py:138
  Evidence: Wächterzahl "#3194": 8 stimmt mit Datei.
  Status: CONFIRMED

Confirmation:
  AC: AC-7
  Code reference: frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts:56
  Evidence: Prüfsumme neu; zweimal Erzeugen byte-gleich b62d1927...
  Status: CONFIRMED

Confirmation:
  AC: AC-6
  Code reference: docs/reference/gates_und_ratschen.md:754
  Evidence: Regel g dokumentiert; 100 Einträge tragen i18n_key (Live-Abgleich nicht gefahren, indirekt).
  Status: CONFIRMED

Confirmation:
  AC: Spec
  Code reference: docs/specs/modules/feat_3194_elementliste_en_zusammengesetzt.md:61
  Evidence: muster-Präzisierung deckt sich mit Code (null bei A/D).
  Status: CONFIRMED

## Herkunft der Vorbedingungen
kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Verdict
VERDICT: VERIFIED
Tests: 8371 passed, 0 failed, 3 übersprungen (Node); Python-Test Besitzerliste grün
Edge cases: geprüft; 2 LOW-Findings
Regressions: keine
Checklist: 7/7 ACs bewiesen (AC-6 indirekt)

## Geprüfte Dateien

- sha256:b62d1927fffcebde9d734261e8c589a6e70ff3e817bb6b24999b3040340e9928  docs/context/einstellungen_neu/elementliste.json
- sha256:5ca2f9a91d09f0b850f025c7864ab184601508b7b6d1df25fe23333b0f09373e  docs/context/einstellungen_neu/elementliste_besitzer.json
- sha256:25356bba4d8fe3da054d7d85cfa9e06013ec5607c718ca8e8225a9815770125a  docs/reference/gates_und_ratschen.md
- sha256:18cec609f107fadff4daf914a452bb05e5cbd0af2adae5e4298f079dec8eea56  docs/specs/modules/feat_3194_elementliste_en_zusammengesetzt.md
- sha256:00e600600a16d74cfc29ebc126962403285ee5dce9e02542459791d4d8251823  frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts
- sha256:8a607c0b694daf054090d792f7fe9705f183e8e682957bcdc8ae85157a697982  frontend/src/lib/__tests__/elementliste_zusammengesetzt_3194.test.ts
- sha256:fadff502eca1ec22910cc1d6848d2bf06538776c6896f73b040131da51172a66  scripts/elementliste_aus_mockup.ts
- sha256:71809fbff2ff7e6015e369ee4e7dba50054de3fc2f43adda95f22532702a354d  tests/test_2913_c2_besitzerliste.py

## Prüfbasis

- base: bf24cd3c1e63ecf74656fdfc7b9b27256f51a750
- blob:5ca113bb223cbe116240f9e64a6cc43be6cf3f31  docs/context/einstellungen_neu/elementliste.json
- blob:c06f53f361486352bd53c7045cd43973313e861c  docs/context/einstellungen_neu/elementliste_besitzer.json
- blob:eaeec81162a2d4f3d48d45f9282c96624c62d664  docs/reference/gates_und_ratschen.md
- blob:2fb34301ce2512ded6655cc02a99224f4cbbc76d  docs/specs/modules/feat_3194_elementliste_en_zusammengesetzt.md
- blob:261cbb59e588ea87b114fc68c6a1f4588598828e  frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts
- blob:6aa9c88415a5df9383c045a2baca6fd3839fba9a  frontend/src/lib/__tests__/elementliste_zusammengesetzt_3194.test.ts
- blob:63ba024506817a20e60fb67934ea2c2eee371c20  scripts/elementliste_aus_mockup.ts
- blob:4057e7dfabd532dd7a1f6c655212a62b93465c54  tests/test_2913_c2_besitzerliste.py
