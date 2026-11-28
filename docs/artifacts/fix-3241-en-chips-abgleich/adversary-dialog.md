# Adversary Dialog — fix-3241-en-chips-abgleich
Spec: docs/specs/modules/fix_3241_elementliste_en_metrikzeile_chips.md
Datum: 2026-11-28 01:35

## Checkliste
- [x] **Input:** Mockup-Text der Metrik-Zeile, Katalog `wetter`, Namenspaare, sichtbare Chips des Prüfkontos (EN).
- [x] **Output:** 12 Metrik-Zeilen mit `text_en` und Katalogschlüssel; im EN-Abgleich je Chip gefunden oder nicht_pruefbar mit benanntem Grund.
- [x] **Side effects:** neu erzeugte `elementliste.json`, kleinere Besitzerdatei; keine Produktänderung.
- [x] **AC-1:** Given der englische Katalog kennt `wetter.hinweis.*` / When der Erzeuger die Metrik-Zeilen „mm · Summe“ und „m · Minimum“ zuordnet / Then lauten die englischen Texte „mm · total“ und „m · minimum“ mit dem Hinweis-Schlüssel der App
- [x] **AC-2:** Given der Hinweis „Tageshöchst · Tagestief“ enthält selbst ein „ · “ / When die Zeile „°C · Tageshöchst · Tagestief“ zugeordnet wird / Then lautet der englische Text „°C · daily high · daily low“ und nicht mehr nicht_pruefbar
- [x] **AC-3:** Given ein Grünbereich ohne Einheit („· grün: bis 6“) / When der Erzeuger ihn zuordnet / Then ist das Muster „· grün: bis {bis}“ mit englisch „· green: up to {bis}“ hinterlegt, Zeilen mit Einheit bleiben unverändert
- [x] **AC-4:** Given die Liste wird neu erzeugt / When sie mit der bisherigen verglichen wird / Then ändern sich genau die 12 Metrik-Zeilen-Einträge und alle übrigen Einträge bleiben textgleich
- [x] **AC-5:** Given der englische Abgleich läuft mit dem Prüfkonto / When ein Metrik-Chip „+ <Name>“ bewertet wird / Then gilt die Einzelerwartung „+ <englischer Name>“ aus dem Namenspaar: sichtbar ist gefunden, nicht sichtbar verhält sich wie im deutschen Lauf
- [x] **AC-6:** Given ein Chip, für den kein DE→EN-Namenspaar existiert / When der englische Abgleich ihn bewertet / Then meldet er nicht_pruefbar mit „kein EN-Name für <DE-Name>“ und rät keinen Namen
- [x] **AC-7:** Given der deutsche Abgleich / When er nach der Änderung läuft / Then sind Bewertung und Ergebnis jedes Chips und jeder Zeile identisch zu vorher
- [x] **AC-8:** Given die Besitzerliste / When der Zählwächter läuft / Then trägt kein Eintrag mehr den Verweis #3241, im englischen Abgleich tauchen „mm · total“, „m · minimum“, „°C · daily high · daily low“ und „· green: up to 6“ nicht mehr als zusätzlicher Text auf, und `--abnahme` erzeugt im Reiter Wetter keine neue herrenlose Abweichung

## Dialog

### Runde 1
**Adversary:** Tests laufen lassen (node: 397 pass/0 fail, pytest: alle gruen; Ausgaben adv-node-output.txt, adv-pytest-output.txt). Neuerzeugung reproduzierbar (diff leer). Diff gegen HEAD: genau 12 Eintraege (6+4+2) geaendert, alle anderen textgleich (24 +/- Zeilen). Besitzerdatei: 330 -> 269, 61 entfernt, alle mit #3241, nichts hinzugefuegt, ausnahmen unveraendert; #3241 0 mal vorhanden.
Code reference: scripts/elementliste_aus_mockup.ts:440 (hinweisZeileEn), :454 (gruenOhneEinheitEn), :471 (metrikZeileEn)
Code reference: frontend/e2e/elementliste_abgleich_logik.ts:1529 (bewerteKontoChips), :1558 (chipName), :1573 (enChip), :1666 (bewerteAbschnitt)
Code reference: frontend/e2e/elementliste-abgleich.staging.spec.ts:507 und :535 (namenDeEn durchgereicht)
Code reference: docs/context/einstellungen_neu/elementliste.json:118 (Beispiel mm . Summe -> wetter.hinweis.precipitation / mm . total)
Code reference: docs/context/einstellungen_neu/elementliste_besitzer.json:3 (besitzer, ohne #3241)
Code reference: tests/test_2913_c2_besitzerliste.py:192 (soll-Dict komplett, #3241: 0; auskommentierte Eintraege #3009 usw. wiederhergestellt, Hinweis (b) geprueft)
Code reference: frontend/src/lib/__tests__/elementliste_abgleich_fixloop2.test.ts:117 (EN-Bestandstest praezisiert, nicht abgeschwaecht: prueft jetzt konkreten Grund pro Chip)
Code reference: frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts:155 (Hash-Waechter, neuer Hash passt zur Datei, Diff je ID von mir bestaetigt)
Hinweise (a)-(c): (a) sachgerecht, verhindert Verschiebung von 72 Diff-Zeilen, aber ungetestet (F001); (b) ok; (c) keine Abschwaechung.
**Implementierer:** keine Erwiderung (Adversary-Lauf).

### Runde 2
**Adversary:** Mutationen (Scratchpad-Sicherung, nach jeder Probe diff identisch): EN-Name->DE-Name: rot (3). Fail-closed->raten: rot (Test 7). DE-Zweig fuer EN-Logik: rot (Test 8). DE-Zweig entfernt: rot (C5). Hinweis-Sonderfall entfernt: rot (Test 1, 2). Hinweis ohne Ganzes (split): rot (Test 2). Gruenbereich entfernt: rot (Test 3). Abschnittsfilter entfernt: rot (Test 3, zufaellig ueber anderen Weg). Paare nicht an Kontochips: rot (3). Erstes-Element-Regel: rot (C5). NICHT rot: M7 (Regel a entfernt, 72 Diff-Zeilen in regenerierter Liste), M9 (namenDeEn im Staging-Spec nicht durchgereicht).
Finding F001 (MEDIUM): Regel (a) in metrikZeileEn ungeschuetzt. Finding F002 (MEDIUM): Verdrahtung im Staging-Spec ungetestet (Wirkstelle, EN-Lauf wuerde alle Chips nicht_pruefbar melden).
**Implementierer:** offen.

## Herkunft der Vorbedingungen

Testdaten: echter Katalog, echte Liste, echte Namenspaare; keine Mocks.


### Runde 3 (Fix-Loop 1)
**Adversary:** F001 geprueft. Code reference: frontend/e2e/fix3241_metrikzeile_erzeuger.test.ts:104 (Gruppe Reproduzierbarkeit, 2 Tests). Nicht zirkulaer: nur Rohtexte (text_de, rolle, abschnitt) aus der eingecheckten Liste werden gruppiert und durch E.baueElemente mit echtem Katalog neu erzeugt; verglichen wird Erzeugnis gegen Datei je ID. Mutation Regel (a) entfernt (scripts/elementliste_aus_mockup.ts:471, Sicherung, danach identisch): Test 5 rot (je-ID-Vergleich). F001 geschlossen. Erneut: node 399 pass / 0 fail (adv-node-output-r2.txt), pytest alle gruen (adv-pytest-output-r2.txt). Weitere Code references unveraendert: frontend/e2e/elementliste_abgleich_logik.ts:1573, frontend/e2e/elementliste-abgleich.staging.spec.ts:507, docs/context/einstellungen_neu/elementliste.json:118, docs/context/einstellungen_neu/elementliste_besitzer.json:3, tests/test_2913_c2_besitzerliste.py:192.
F002: akzeptiert per Orchestrator-Entscheidung, Abdeckung durch verbindlichen EN-Staging-Abgleich in /e2e-verify (--sprache en --scope wetter, Chips in metriken gefunden). Offen bis dahin, an /e2e-verify uebergeben.

## Verdict
**VERIFIED** (Kern-Schicht); F002 an /e2e-verify uebergeben.

## Geprüfte Dateien

- sha256:fd20857939f1161b94562941cd08ef4517f6fb60d08eefcb37eb6c348f8ce271  docs/context/einstellungen_neu/elementliste.json
- sha256:40181ec64a147bab03ab4c57a48c0852deec27f86459bc1216954fb460c41b8d  docs/context/einstellungen_neu/elementliste_besitzer.json
- sha256:a2b3dd51e637c3582e3747db2284d4a193053257fb93958f73b757e0eb322ee1  frontend/e2e/elementliste-abgleich.staging.spec.ts
- sha256:ee8672d065dd049eb82f19fa07d935fbe170b5c35a67b6eaa24085203dde930e  frontend/e2e/elementliste_abgleich_logik.ts
- sha256:660682d8b89113a2d02bbbbfec932cb088b5b7cddfd67361e137b4dd59dfe382  frontend/src/lib/__tests__/elementliste_abgleich_fixloop2.test.ts
- sha256:9493a77efc3fd3fef97af6e694d27960190267a3ab417b97f24f4bfc1455e435  frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts
- sha256:5a36ace49be4477606e7bd32e7f25d5ced8a7e76ea324b54a73faa21148a3b76  scripts/elementliste_aus_mockup.ts
- sha256:a4b2785260e9966e0fe13f7158a588b9e8db0b5e0895971a6d581f424f270df1  tests/test_2913_c2_besitzerliste.py

## Prüfbasis

- base: 71589250317483d3c962970113867b9015ad6183
- blob:23433ed5c98eabc8a894df09270afaf8018badd9  docs/context/einstellungen_neu/elementliste.json
- blob:782288c63e3aab68f9312a71d5a48c984903bc95  docs/context/einstellungen_neu/elementliste_besitzer.json
- blob:73e1a9dd32434c17c39d20749d4d592150e85ed5  frontend/e2e/elementliste-abgleich.staging.spec.ts
- blob:388419cf3a0faac511d99d4c058cbff7bd533f6c  frontend/e2e/elementliste_abgleich_logik.ts
- blob:21ed72ac40ad8b73475a91f8aa558a03cf1929ae  frontend/src/lib/__tests__/elementliste_abgleich_fixloop2.test.ts
- blob:2e141766446d7e10a7f420e9e38265811073e8be  frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts
- blob:417ba39afe62e3fadd08844f9ad07c77c9c1c6bc  scripts/elementliste_aus_mockup.ts
- blob:38d9d12f3dfe1ba3af675983a6155f71ae9f5d04  tests/test_2913_c2_besitzerliste.py

## Geprüfte Dateien

- sha256:fd20857939f1161b94562941cd08ef4517f6fb60d08eefcb37eb6c348f8ce271  docs/context/einstellungen_neu/elementliste.json
- sha256:40181ec64a147bab03ab4c57a48c0852deec27f86459bc1216954fb460c41b8d  docs/context/einstellungen_neu/elementliste_besitzer.json
- sha256:a2b3dd51e637c3582e3747db2284d4a193053257fb93958f73b757e0eb322ee1  frontend/e2e/elementliste-abgleich.staging.spec.ts
- sha256:ee8672d065dd049eb82f19fa07d935fbe170b5c35a67b6eaa24085203dde930e  frontend/e2e/elementliste_abgleich_logik.ts
- sha256:660682d8b89113a2d02bbbbfec932cb088b5b7cddfd67361e137b4dd59dfe382  frontend/src/lib/__tests__/elementliste_abgleich_fixloop2.test.ts
- sha256:9493a77efc3fd3fef97af6e694d27960190267a3ab417b97f24f4bfc1455e435  frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts
- sha256:5a36ace49be4477606e7bd32e7f25d5ced8a7e76ea324b54a73faa21148a3b76  scripts/elementliste_aus_mockup.ts
- sha256:a4b2785260e9966e0fe13f7158a588b9e8db0b5e0895971a6d581f424f270df1  tests/test_2913_c2_besitzerliste.py

## Prüfbasis

- base: 71589250317483d3c962970113867b9015ad6183
- blob:23433ed5c98eabc8a894df09270afaf8018badd9  docs/context/einstellungen_neu/elementliste.json
- blob:782288c63e3aab68f9312a71d5a48c984903bc95  docs/context/einstellungen_neu/elementliste_besitzer.json
- blob:73e1a9dd32434c17c39d20749d4d592150e85ed5  frontend/e2e/elementliste-abgleich.staging.spec.ts
- blob:388419cf3a0faac511d99d4c058cbff7bd533f6c  frontend/e2e/elementliste_abgleich_logik.ts
- blob:21ed72ac40ad8b73475a91f8aa558a03cf1929ae  frontend/src/lib/__tests__/elementliste_abgleich_fixloop2.test.ts
- blob:2e141766446d7e10a7f420e9e38265811073e8be  frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts
- blob:417ba39afe62e3fadd08844f9ad07c77c9c1c6bc  scripts/elementliste_aus_mockup.ts
- blob:38d9d12f3dfe1ba3af675983a6155f71ae9f5d04  tests/test_2913_c2_besitzerliste.py
