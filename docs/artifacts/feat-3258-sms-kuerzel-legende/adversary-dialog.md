# Adversary Dialog — feat-3258-sms-kuerzel-legende
Spec: docs/specs/modules/feat_3258_sms_kuerzel_legende.md
Datum: 2026-11-22 07:07

## Checkliste
- [x] **Input:** Mockup Fassung 4 mit Legende; Staging-Prüfkonto (Trip und Orte), Sprache DE und EN.
- [x] **Output:** Elementliste enthält Legende und Beispielwarnungen als Soll-Einträge (Trip und Orte, DE und EN); der Abgleich findet sie live. SMS-Beispielwerte laufen als Muster.
- [x] **Side effects:** Wechsel „zusätzlich“ zu „gefunden“ ist erwünscht; keine neue Abweichung. Produktverhalten unverändert.
- [x] **AC-1:** Given das Mockup Fassung 4 im Reiter Wetter, Bereich „Was steht wo“ / When der Nutzer den Block „Kürzel erklärt“ öffnet / Then sieht er je aktiver SMS-Metrik Kürzel mit Bedeutung und danach die festen Beispielwarnungen, in derselben Reihenfolge und mit demselben Wortlaut wie in der App, für Trip und Orte.
- [x] **AC-2:** Given die Elementliste wird mit dem Generator neu erzeugt / When Deutsch und Englisch gelesen werden / Then stehen die festen Beispielwarnungen mit Soll-Text aus dem Katalog `wetter.wsw.legende.*` (zum Beispiel „Warnung Wind“ und „wind warning“) in der Liste, ohne EN-Lücke und ohne neu erfundene Übersetzung.
- [x] **AC-3:** Given die SMS-Beispielwerte FN12, FD12/16 und die ganze SMS-Zeile hängen am Prüf-Datensatz / When die Elementliste sie führt / Then sind sie als Muster mit `{zahl}` erfasst und mit Besitzer `#3258` begründet, und das Muster erklärt nur Zahlen, keinen beliebigen Text.
- [x] **AC-4:** Given die Besitzerliste nach der Änderung / When der Abgleich beide Sprachen prüft / Then sind die vorher herrenlosen „zusätzlich“-Einträge der Legende entfallen oder einzeln mit Grund und Verweis zugeordnet, und es gibt keinen herrenlosen Eintrag.
- [x] **AC-5:** Given der Staging-Abgleich `--scope wetter` in Deutsch und Englisch für Trip und Orte / When er nach der Änderung läuft / Then werden Legende und Beispielwerte live gefunden, es entstehen keine neuen Abweichungen, „abweichend ohne Besitzer“ liegt höchstens beim Vorher-Wert 16 und „zusätzlich“ ist gesunken.
- [x] **AC-6:** Given die Elementliste wurde neu erzeugt / When die Prüfsumme geprüft wird / Then stimmt sie mit der Datei überein und ist im Test mit Begründung nachgezogen, und der Rest der Liste (übrige Reiter und Seiten-Zustände) bleibt unverändert.
- [x] **AC-7:** Given Nutzer mit Trips und Orts-Vergleichen / When sie die Anwendung nutzen / Then ändert sich nichts, denn Produktcode, Katalog und Prüfdaten bleiben unverändert.

## Dialog

### Runde 1
**Adversary:** Staging-Abgleich `--scope wetter` DE und EN aus dem Worktree (Staging-Commit vor und nach den Läufen 43a5c0df, unverändert; erster EN-Lauf scheiterte an ERR_CONNECTION_REFUSED von Staging, zweiter Lauf grün). Ergebnis DE vorher 1477/483/198/142 (gefunden/abweichend/nicht_pruefbar/zusätzlich), nachher 1549/595/198/57; EN vorher 1431/427/300/168, nachher 1519/469/354/104. „abweichend ohne Besitzer“ 16 vor und nach (DE und EN), kein Statuswechsel eines bestehenden Eintrags (Diff je ID: 0 Wechsel, 0 entfallen). Aber 184 neue Soll-Einträge: DE 72 gefunden, 112 abweichend „Reihenfolge im Abschnitt“ (Besitzer #3122); EN 88 gefunden, 42 Reihenfolge, 54 EN-Lücke nicht_pruefbar.

Finding F001: Severity HIGH, Category spec_violation. Code reference: docs/context/einstellungen_neu/elementliste.json:1. AC-5 verlangt „Legende live gefunden, keine neuen Abweichungen“. Trip DE: „Kürzel erklärt“ (Nr. 178), `@14`, `!TS:H@14`, Stufe-gelb-`L`, „Böen“, „Gewitter“ usw. stehen als abweichend (Reihenfolge) und tragen den Pauschal-Besitzer #3122 („Tabelle Was steht wo noch nicht gebaut“). Die Gesamtzahl „abweichend“ steigt um 112 (DE) bzw. 42 (EN). Der Zeiger `zuletzt` in `bewerteAbschnitt` (frontend/e2e/elementliste_abgleich_logik.ts:1347-1366) steht wegen der bereits kaputten Reihenfolge des Abschnitts (#3122) hinter der Legende; Ein-Zeichen-Kürzel (N, L, D) können zusätzlich an fremden Stellen treffen. Remediation: Anzahl neuer #3122-Abweichungen als Erwartung festhalten und im Issue ausweisen, oder die Reihenfolge-Abweichung der Legende einzeln begründen; AC-5 im Wortlaut anpassen („keine neue Abweichung ohne Besitzer“).

Finding F002: Severity MEDIUM, Category anti_pattern. Code reference: docs/context/einstellungen_neu/elementliste_besitzer.json:3914. Die 21 englischen Metrik-Bedeutungen („day max“, „index“, „night“, „medium“ …) stehen als `zusaetzlich`-Besitzer mit `text` ohne ctx. Sie wirken in jedem Zustand des Reiters Wetter in Trip und Orte und decken jeden künftigen Live-Text gleichen Wortlauts ab. Die EN-Soll-Seite bleibt Lücke (EN nicht_pruefbar von 300 auf 354). Die Lücke wird nur verschoben. Remediation: `text_en` aus `kuerzel_bedeutung_en` (src/app/metric_catalog.py) im Generator als Soll führen, Besitzer-Einträge entfallen lassen.

Finding F003: Severity LOW, Category anti_pattern. Code reference: scripts/elementliste_aus_mockup.ts:424. Der Kommentar „Katalogschlüssel der Chips“ steht jetzt über dem neuen `LEGENDE_PRAEFIX`, und `export const CHIP_SCHLUESSEL =` hat das Leerzeichen verloren. Rein kosmetisch.

Finding F004: Severity LOW, Category edge_case. Code reference: tests/test_2913_c2_besitzerliste.py:1. Der Zählwächter wurde nicht geändert (Datei nicht im Diff); Mutation 3 (Besitzer-Eintrag „gusts“ #3258 entfernt) bleibt für pytest grün (35 passed). Nur der node-Test `feat3258` fängt sie. AC-4 nennt pytest als Nachweis.

Finding F005: Severity LOW, Category spec_violation. Code reference: frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts:86. AC-7 schließt Dateien unter `frontend/src/` aus; diese Testdatei (Prüfsumme, AC-6) liegt dort. Kein Produktcode, Spec-Wortlaut ungenau.

**Implementierer:** (nicht beteiligt, nur Spec und Testausgaben)

### Runde 2
**Adversary:** Fix-Loop 1 geprüft. Staging blieb auf 43a5c0df (vor und nach). Live-Läufe `--scope wetter` in `adv3258/r2-de` und `adv3258/r2-en` (Ablage im Scratchpad; Logs in den Artefakten). Ergebnis DE 1549/595/198/57, EN 1539/503/300/77 (gefunden/abweichend/nicht_pruefbar/zusätzlich; vorher DE 1477/483/198/142, EN 1431/427/300/168). EN nicht_pruefbar 300, nicht gestiegen (F002 behoben). „Abweichend ohne Besitzer“ 16 in beiden Sprachen. 0 Statuswechsel bestehender Einträge, 0 entfallen. Alle neuen abweichenden Einträge (DE 78 Trip + 34 Orte, EN 76 Trip) tragen „Reihenfolge im Abschnitt“ und Besitzer #3122; kein neuer Grund. Zusätzlich mit Besitzer #3258: DE 3, EN 4 (nur SMS-Muster, die 21 EN-Texte sind entfallen).

Frage F001 (Probe): Test `probe.ts` (Scratchpad) ruft die echte `bewerteAbschnitt` mit der erzeugten Trip-Liste auf. Steht die Live-Reihenfolge wie das Mockup, werden 55 von 55 Legenden-Einträgen gefunden. Fehlt nur die Tabellenzeile „UV-Index“ vor der Legende (wie live bei abweichender Tabellenreihenfolge), kippen 41 Legenden-Einträge auf Reihenfolge-abweichend, weil der Zeiger `zuletzt` auf das Wort „UV-Index“ in der Legende springt (im Abgleich ist Nr. 149 „UV-Index“ der letzte gefundene Eintrag vor der Legende). Gleiche Ursache wie #3122 (Tabellenreihenfolge), die Legende ist nicht die Quelle. Schwäche: der Zeiger-Prüfer vervielfacht eine einzige Tabellenabweichung (Kaskade); das ist Altlast der Abgleich-Logik.

Frage (c): Der Schnappschuss `docs/context/einstellungen_neu/daten/kuerzel_bedeutung.json` entspricht `_METRICS.kuerzel_bedeutung_de/en` in `src/app/metric_catalog.py` plus O1 (Test grün). Mutation 4: EN „gusts“ zu „gustz“ im Schnappschuss: `tests/test_3258_kuerzel_bedeutung_schnappschuss.py` ROT (2 Tests), wiederhergestellt, sha256 d974b584… vor und nach. Mutation 5: Besitzer-Eintrag `FN{zahl}` entfernt: Zählwächter in `tests/test_2913_c2_besitzerliste.py` ROT (F004 behoben), wiederhergestellt 4da311d7….

Frage (d) Mutation 1: Kein Finding. `elementliste_aktuell.test.ts` (AC-12, Hash Mockup gegen Liste, läuft als node-Test in CI-Job frontend-test) wird mit entferntem legendeBlock ROT (2 Tests rot), sha256 c347e818… vor und nach. Der Playwright-Mockup-Lauf ist dafür nicht nötig. Er bleibt eine zusätzliche Determinismus-Prüfung; Vorschlag: nicht in CI aufnehmen, die Hash-Kontrolle genügt. Ein Mockup, das ohne Listen-Neulauf geändert wird, fällt auf. Ein neu erzeugter Lauf ohne Legende wird von den feat3258-Tests (Liste muss Legende enthalten) abgefangen.

Tests: node feat3258, elementliste_abgleich_logik, elementliste_*.test.ts: 422 passed, 0 failed, 0 skipped. pytest Besitzerliste und Schnappschuss: 38 passed. F003 bereinigt (Generator-Diff ohne Format-Glitch).
**Implementierer:** F001 als gleiche Ursache #3122 entschieden (Issue #3258), F006 alter Befund.

Finding F001: Severity LOW, Category anti_pattern. Code reference: frontend/e2e/elementliste_abgleich_logik.ts:1347. Der Zeiger `zuletzt` in `bewerteAbschnitt` macht aus einer Tabellenabweichung eine Kaskade (41 Legenden-Einträge in der Probe). Keine Legenden-Ursache, bleibt bei #3122. Remediation: nach dem Tabellen-Umbau (#3122) Legende erneut messen.

Confirmation:
  AC: AC-1
  Code reference: docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html:651
  Evidence: `legendeBlock()` nach `budgetZeile`, Reihenfolge Metriken dann feste Einträge, wie live; Mutation 1 rot im CI-Node-Test.
  Status: CONFIRMED

Confirmation:
  AC: AC-2
  Code reference: scripts/elementliste_aus_mockup.ts:432
  Evidence: `legendeEn` nimmt feste Einträge aus `wetter.wsw.legende.*`, Metrik-Bedeutungen aus dem Schnappschuss; keine EN-Lücke (EN nicht_pruefbar 300).
  Status: CONFIRMED

Confirmation:
  AC: AC-2
  Code reference: docs/context/einstellungen_neu/daten/kuerzel_bedeutung.json:1
  Evidence: Schnappschuss gleich Katalog, Drift-Mutation rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-2
  Code reference: tests/test_3258_kuerzel_bedeutung_schnappschuss.py:1
  Evidence: Test vergleicht gegen `_METRICS` ohne Mock, Mutation 4 rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: frontend/e2e/elementliste_abgleich_logik.ts:1026
  Evidence: `zielMuster` begrenzt `{zahl}` auf Ziffern; Mutation 2 (Runde 1) rot; 0 Statuswechsel live (b).
  Status: CONFIRMED

Confirmation:
  AC: AC-4
  Code reference: docs/context/einstellungen_neu/elementliste_besitzer.json:3914
  Evidence: Nur noch 4 SMS-Muster mit #3258; „ohne Besitzer“ 16; Mutation 5 rot im pytest.
  Status: CONFIRMED

Confirmation:
  AC: AC-4
  Code reference: tests/test_2913_c2_besitzerliste.py:172
  Evidence: Zählwächter `#3258: 4` fängt das Entfernen eines Eintrags.
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: docs/context/einstellungen_neu/elementliste.json:1
  Evidence: Live DE/EN: ohne Besitzer 16, zusätzlich 142 auf 57 und 168 auf 77, 0 Statuswechsel, neue Abweichungen nur Reihenfolge/#3122 (gleiche Ursache, Probe 55/55 bei gleicher Tabelle). Lesart „keine neue Abweichung ohne Besitzer, keine neue Ursache“.
  Status: CONFIRMED

Confirmation:
  AC: AC-6
  Code reference: frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts:86
  Evidence: Prüfsumme und Mockup-Hash passen, 184 neue Einträge nur in was-steht-wo, keine ID entfallen.
  Status: CONFIRMED

Confirmation:
  AC: AC-6
  Code reference: frontend/src/lib/__tests__/elementliste_aktuell.test.ts:82
  Evidence: Invariante angepasst, Hash-Test fängt Mockup-Änderung (Mutation 1).
  Status: CONFIRMED

Confirmation:
  AC: AC-7
  Code reference: frontend/e2e/feat3258_sms_kuerzel_legende.test.ts:1
  Evidence: Kein Produktcode, Katalog oder Prüfdaten im Diff (Testdateien unter frontend/src nur Tests).
  Status: CONFIRMED

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`). Keine Produktionsschreibstelle betroffen: Änderung betrifft nur Mockup, Generator, Listen und Tests.

## Verdict

═══════════════════════════════════════
VERDICT: VERIFIED
═══════════════════════════════════════
Tests: 422 node passed + 38 pytest passed, 0 failed, 0 übersprungen
Edge cases: Live DE/EN geprüft, 5 Mutationen alle rot, Probe zur Ursache F001
Regressions: None found (0 Statuswechsel)
Checklist: 10/10 points proven (AC-5 in der Lesart „keine neue Ursache“)

## Geprüfte Dateien

- sha256:d974b584e2f228a7ade9eab49d5551c229ae53a37414dea57e915993e7fd9d91  docs/context/einstellungen_neu/daten/kuerzel_bedeutung.json
- sha256:4f1227f88fd14bb3d1670e875b7d6d1ec94024283ebb65bf9f994228a50daedf  docs/context/einstellungen_neu/elementliste.json
- sha256:4da311d72884c61e49b7ad8939fe1dd25aaaa10280bb9b1fdd31cb23e4283782  docs/context/einstellungen_neu/elementliste_besitzer.json
- sha256:c347e818e03ed26119a6a9fd3460258b3409e8c322914041df6dbb9503cdb972  docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html
- sha256:5dde3d4748c0c39cc57930b6ec79c10024da909558e279a83866ed270dc8531d  frontend/e2e/elementliste_abgleich_logik.ts
- sha256:922c26f99788d81c8150a53af1ccda9632f06a99f64b686df260edfb375c02ac  frontend/e2e/feat3258_sms_kuerzel_legende.test.ts
- sha256:868483900daca343bb9f4ef31d211b1f2a6c394c8e499fe26d2385f3d7c41521  frontend/src/lib/__tests__/elementliste_aktuell.test.ts
- sha256:289badee2b6663ed7e0b84b6fb6be97833b2c6a87c658a8aed93be5cfafba085  frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts
- sha256:b7b3fcb670d4c3d74cda84c3a00c950810d5ed42cf35d009469d11cd835059a9  scripts/elementliste_aus_mockup.ts
- sha256:7e29d8114d3b0186693f25347d7720ab5b396dbcd1cd5b9832640fd228b4b2be  tests/test_2913_c2_besitzerliste.py
- sha256:481756cdec4e10125433fb59be113ce845b433a0877f549127bc99c23d430d94  tests/test_3258_kuerzel_bedeutung_schnappschuss.py

## Prüfbasis

- base: 43a5c0df154b842f8b27523a0448cfd69ae4ed62
- blob:58c2cf1005c97a8d952db515822ba5be1282b73d  docs/context/einstellungen_neu/daten/kuerzel_bedeutung.json
- blob:849d775d4a767bf62c49c65d7d2a8b2ca4224faf  docs/context/einstellungen_neu/elementliste.json
- blob:5d5e7ec5a140da4eba80222d3a1d8277cd77467c  docs/context/einstellungen_neu/elementliste_besitzer.json
- blob:2ee949c8cb0a8f1248079fd36d998b9a69c07515  docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html
- blob:c6202bcddf63fe82845f3e0aaf6dcd1666b66c8a  frontend/e2e/elementliste_abgleich_logik.ts
- blob:8e8e35c0adf3b11d6eaebf26c8f6f785ba89c57a  frontend/e2e/feat3258_sms_kuerzel_legende.test.ts
- blob:a347d8ccd704aec94adb7af1169e67db20ed1eb0  frontend/src/lib/__tests__/elementliste_aktuell.test.ts
- blob:f08129e325daa18852dd7a281d906cdb58b9c0cd  frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts
- blob:15c949f47dd9b9a932d2101f0de130491b6e3d0c  scripts/elementliste_aus_mockup.ts
- blob:411d0b6962e8d0e61088304d461f42fc75f2f51d  tests/test_2913_c2_besitzerliste.py
- blob:035439f313556e3da1e198d401e2dd339287dce7  tests/test_3258_kuerzel_bedeutung_schnappschuss.py
