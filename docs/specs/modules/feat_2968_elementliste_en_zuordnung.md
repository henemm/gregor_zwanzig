---
entity_id: feat_2968_elementliste_en_zuordnung
type: feature
created: 2026-11-19
updated: 2026-11-19
status: draft
version: "1.0"
workflow: feat-2968-en-katalogtexte
tags: [elementliste, i18n, pruefwerkzeug, generator]
---

# Elementliste: EN-Zuordner im Generator (#2968)

## Approval

- [ ] Approved

## Purpose

Der Elementlisten-Generator ordnet deutsche Mockup-Texte heute nur selten einem Katalogschlüssel zu; 1022 Einträge (eingecheckt 1190) gelten als „EN-Lücke“, obwohl der englische Katalog vollständig ist. Diese Spec macht den Zuordner genauer (verschachtelte Muster, „ · “-Segmente, sprachneutrale Texte), ohne englischen Text zu erfinden und ohne neue Katalogschlüssel, damit der EN-Abgleich dieselbe Prüftiefe wie der DE-Abgleich bekommt.

## Source

- **File:** `scripts/elementliste_aus_mockup.ts`
- **Identifier:** `ermittleEn`, `chipEn`, `index` (Zuordner); `erwartung` in `frontend/e2e/elementliste_abgleich_logik.ts` (Abgleich)

> Schicht: reines Prüfwerkzeug (Skripte, Frontend-E2E-Logik, Tests, Doku). Kein Produktcode, kein Nutzerpfad, keine Nutzerdaten, kein Trip/Vergleich-Pendant, keine Kanal-Inhalte betroffen.

## Estimated Scope

- **LoC:** +300 / -450 (die Besitzerliste schrumpft stark)
- **Files:** 9
- **Effort:** medium

## Scope

**Drin:** Zuordner im Generator (Regeln a–d), Schnappschüsse Metriknamen/Eigennamen mit Drift-Tests, `sprachneutral` im EN-Abgleich, Elementliste neu erzeugt, Besitzerliste von #2968 befreit, Doku.

**Nicht drin:** neue Katalogschlüssel oder geänderte EN-Texte. Begründung: Der englische Katalog ist vollständig (Paritätstest), jeder deutsche Katalogtext hat bereits sein englisches Gegenstück; Schlüssel ohne Verwender sind verboten. Der Titel des Tickets („Katalogtexte ergänzen“) meint die EN-Spalte der Elementliste, nicht den App-Katalog: deren EN-Werte werden aus dem vorhandenen Katalog ergänzt, wie im Ticket gefordert („EN-Texte der Elementliste aus dem i18n-Katalog ergänzen“).

**Restlücken und Abnahme #3009:** Die verbleibenden Lücken sind Einträge, deren deutscher Mockup-Text in der App selbst anders oder noch gar nicht vorkommt. Dort ist schon der DE-Lauf `abweichend`; EN und DE haben also dieselbe Prüftiefe, wie das Ticket verlangt. Lückenlos (#3009) werden sie, wenn die zuständige Scheibe Mockup und App angleicht: dann trifft der Zuordner den Katalogtext automatisch. Jede Restlücke trägt deshalb diese Scheibe als Besitzer.

## Definition of Done

- Alle ACs grün, Kern-Tests (`elementliste_*`, `paritaet_de_en`, Drift-Tests) grün.
- Elementliste neu erzeugt, Lückenzahl im Test festgeschrieben; Restlücken nur noch Klassen Mockup≠App, ungebaut, Kontodaten (Ausgangswert 1022; die frühere Schätzung ≤ 25 % war zu niedrig, weil allein die DE-seitigen Abweichungen rund 380 Einträge ausmachen).
- Jede Restlücke ist ein Eintrag, der auch im DE-Abgleich nicht `gefunden` sein kann (Mockup≠App oder ungebaut), und hat einen Besitzer ≠ #2968.
- Kein Eintrag der Besitzerliste verweist auf #2968.
- Doku in `gates_und_ratschen.md` beschreibt die Zuordner-Regeln.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/i18n/messages/{de,en}/*.json` | Katalog | einzige Quelle für EN-Texte; keine neuen Schlüssel (Schlüssel ohne Verwender sind verboten, `katalog_schluessel_haben_verwender.test.ts`) |
| `src/app/metric_catalog.py` | Python-Modul | Quelle der Metriknamen (`label_de`) und Kurz-Token (`sms_code`, `compact_label`) |
| `docs/reference/i18n_konventionen.md` §2 | Regel | Protokoll-Token, Zahlen, Eigennamen werden nie übersetzt |
| `feat_2913_abgleich_ganzseite.md` | Spec | Abgleich, Besitzerliste, Platzhalter bleiben im EN-Muster (C5) |
| `einstellungen_neu_neustart_adr_waechter_elementliste.md` | Spec | Generator, AC-11 (EN nie erfunden) |
| #3011 | Issue | Vorbild „bekannte Metriknamen“ in der Gegenrichtung |
| #2967 | Issue | Prüfkonto-Daten (Eigennamen) |
| #3009 | Issue | Abnahme DE+EN lückenlos (Verbraucher des Ergebnisses) |

## Implementation Details

Grundsatz: Ein Text gilt nur als aufgelöst, wenn **jeder** Teil für sich aufgelöst ist; sonst bleibt `luecke: true`. EN bleibt Muster mit Platzhaltern (#2913 C5), der Abgleich liest Platzhalter als „beliebiger Wert“. Normalisierung wie bisher (`norm`).

**Regel a: Platzhalter-Muster ohne Wortlaut-Hälfte.** Passt ein Katalogmuster auf den Text, entfällt die Wortlaut-Hälfte-Regel (Wortlaut mindestens 4 Zeichen und halbe Textlänge), wenn JEDER eingesetzte Wert selbst aufgelöst ist. Aufgelöst heißt: (1) exakter DE-Katalogwert, (2) bekannter Metrikname (Schnappschuss, Regel d), (3) Zahl oder Zahl mit Einheit, (4) rekursiv ein Katalogmuster nach Regel a. Rekursionstiefe höchstens 2. Beispiel: „Darstellung Böen in Telegram: Roh“ = `bausteine.darstellung.name` mit `{name}` = „Böen in Telegram“ (`wetter.wsw.zelle.telegram`, `{metrik}` = „Böen“) und `{form}` = „Roh“ (Katalogwert). Ist ein Wert nicht aufgelöst, gilt weiter die alte Wortlaut-Hälfte-Regel samt Wertlänge ≤ 40 Zeichen.

**Regel b: Segmente.** Enthält der Text den Trenner „ · “, wird er zerlegt; aufgelöst ist die Zeile nur, wenn jedes Segment aufgelöst ist (Katalog exakt, Muster nach Regel a, oder sprachneutral nach Regel c). EN = EN der Segmente, mit „ · “ verbunden; `i18n_key` bleibt `null`, `muster` = Segment-Muster mit „ · “ verbunden. Ein führendes „· “ (Mockup-Knoten wie „· grün: bis 30 km/h“) wird als Trenner behandelt und vor dem Auflösen abgetrennt; das EN-Ergebnis trägt es mit.

**Berührung mit dem Schutzfall „°C · vor der Etappe“:** Die Segmentregel löst diesen Text nur auf, wenn „vor der Etappe“ als Ganzes exakt (oder nach Regel a) im Katalog steht; „{count} Etappe“ darf ein Segment nie über die Wortlaut-Hälfte treffen, weil innerhalb eines Segments Regel a nur mit vollständig aufgelösten Werten greift und „vor der“ kein aufgelöster Wert ist. Steht „vor der Etappe“ nicht exakt im Katalog, bleibt die Zeile Lücke. Der bestehende Schutz-Test bleibt unverändert gültig; ein zusätzlicher Test prüft beide Ausgänge.

**Regel c: Sprachneutral.** Neues Feld `sprachneutral: true` am Listeneintrag (bei allen übrigen `false` bzw. fehlend); dann `text_en` = DE-Muster (Zahlen als `{zahl}`), `luecke: false`, `i18n_key: null`. Sprachneutral sind ausschließlich:
1. Texte ohne jeden Buchstaben (Zahlen, „60%“, „+49 171 …“, „-15“);
2. reine Einheiten (°C, km/h, mm, %, m, h) und Zahl mit Einheit;
3. bekannte Metrik-Kurztoken und Protokoll-Token aus dem Schnappschuss (Regel d), auch Token mit Zahl („N10“, „SnowL 1820“, „VS-“);
4. bekannte Eigennamen des Prüfkontos/Mockups aus dem Schnappschuss `docs/context/einstellungen_neu/daten/eigennamen.json` (exakte, normalisierte Zeichenfolgen mit Quellenangabe, z. B. „Münster“, „GR221 Mallorca“, „@henning“). Entscheidung: keine freie Heuristik (großgeschrieben o. ä.), nur die exakte Liste. Ein Text mit Eigennamen, der nicht vollständig in der Liste steht, bleibt Lücke mit Besitzer. Drift-Test: jeder Eintrag kommt im Mockup vor, und kein Eintrag ist ein DE-Katalogwert.

Ein deutsches Wort ist nie sprachneutral: Prüfreihenfolge ist Katalog/Muster zuerst; Regel c greift nur für die vier Klassen oben, nie für „Buchstabentext, der nicht gefunden wurde“.

**Regel d: Metriknamen-Schnappschuss.** `docs/context/einstellungen_neu/daten/metriknamen.json` (aus `src/app/metric_catalog.py`: `label_de`, `sms_code`, `compact_label`, Kürzel). Der Generator liest die Datei (kein Python-Aufruf zur Laufzeit). Drift-Test in Python `tests/test_2968_metriknamen_schnappschuss.py`: Schnappschuss und Katalog sind gleich.

**Abgleich.** `erwartung` (EN) behandelt Einträge mit `sprachneutral: true` wie DE-Muster: Erwartung ist das DE-Muster (Zahlen als beliebige Zahl, sonst wörtlich). Der Abgleich bleibt sonst unverändert; `ListenElement` bekommt das optionale Feld `sprachneutral`.

**Neu erzeugen und Besitzer.** Elementliste neu erzeugen (Hash-Test `elementliste_aktuell.test.ts` bleibt grün; IDs hängen nicht von `text_en` ab). In `elementliste_besitzer.json` werden alle 451 Einträge mit Verweis #2968 bearbeitet: geschlossene Lücken entfernt, verbleibende auf die zuständige Scheibe/das Issue umgehängt (z. B. #2795, #2796, #2913-e, #3012, #3111, sonst Hauptbesitzer der Scheibe) mit neuem, ehrlichem `grund` statt „kein englischer Katalogtext“. Danach kommt „#2968“ im Besitzer-Verweis nicht mehr vor; `elementliste_besitzer_kern.test.ts` bleibt grün.

**Erwartete Rest-Lücken (echte Mockup≠App-Abweichungen):** „obenzu viel“ vs. „oben / zu viel“, Anführungszeichen „“ vs. ‚‘, „Uhrzeit Morgen“ (#2795), „Archivieren?“, Test-Alarm-Menü, Tempo-Karte (#2796), Reiter Orte/Etappen (#2913-e). Die Ausgabe des Generators nennt die verbleibenden Lücken je Grund (Anzahl je Besitzer/Klasse).

**Doku.** Neuer Absatz im Abschnitt Elementliste von `docs/reference/gates_und_ratschen.md`: Regeln a bis d, Eigennamen-Schnappschuss, Schutzgrundsatz „nichts erfinden“.

**Regel e: Katalogwert + Zeichen.** Ein Text „<Katalogwert> <Zeichen ohne Buchstaben>“ ist aufgelöst; EN = EN des Katalogwerts + dasselbe Zeichen (die App setzt Grenzen-Beschriftungen so zusammen).

**Regel f: Mehrdeutiges EN.** Steht ein DE-Text unter mehreren Schlüsseln mit verschiedenem EN, trägt der Eintrag alle EN-Kandidaten (`text_en_alternativen`); der EN-Abgleich akzeptiert jeden davon. Nichts wird erfunden, es wird nur nicht mehr willkürlich der erste Schlüssel gewählt.

## Expected Behavior

- **Input:** Mockup-Text (DE), echter Katalog, Schnappschüsse (Metriknamen, Eigennamen).
- **Output:** je Element `i18n_key`/`text_en`/`muster`/`luecke` plus `sprachneutral`; verbleibende Lücken nur ohne belastbare Zuordnung.
- **Side effects:** neu erzeugte `elementliste.json`, bereinigte Besitzerliste; EN-Abgleich meldet weniger `nicht_pruefbar`/`zusaetzlich`.

## Test Plan

### Automated Tests (TDD RED)

Alle Tests laufen gegen den echten Katalog (`ladeKatalog`), ohne Mocks.

- [ ] Regel a: GIVEN „Regenwahrscheinlichkeit in SMS“ / WHEN `ermittleEn` / THEN Muster `wetter.wsw.zelle.sms`, `luecke: false`; Gegenbeispiel „Etwas Unbekanntes in SMS“ (Wert weder Metrikname noch Katalogwert) ⇒ Lücke.
- [ ] Regel a rekursiv: GIVEN „Darstellung Böen in Telegram: Roh“ / THEN `bausteine.darstellung.name`, EN mit Platzhaltern; Gegenbeispiel „Darstellung Unbekanntes in Telegram: Roh“ ⇒ Lücke; Tiefe 3 ⇒ Lücke.
- [ ] Regel b: GIVEN „km/h · Mittelwind“ und „· grün: bis 30 km/h“ / THEN aufgelöst, EN mit „ · “ verbunden; Gegenbeispiel „km/h · Unbekannter Satz“ ⇒ ganze Zeile Lücke.
- [ ] Schutzfall: GIVEN „°C · vor der Etappe“ / THEN Treffer nur, wenn „vor der Etappe“ exakt im Katalog steht (Test prüft den Ist-Katalog), und nie über „{count} Etappe“.
- [ ] Regel c: GIVEN „60%“, „+49 171 123“, „°C“, „N10“, „Münster“ / THEN `sprachneutral: true`, `luecke: false`, `text_en` = DE-Muster; Gegenbeispiele: „Gewitter“, „Münster Hauptbahnhof“ (nicht in der Eigennamen-Liste) ⇒ nie sprachneutral, Lücke.
- [ ] Abgleich: GIVEN Eintrag `sprachneutral: true` / WHEN `erwartung(e, 'en')` / THEN Regex passt auf den DE-Text mit anderer Zahl, nicht auf fremden Text.
- [ ] Drift Metriknamen: GIVEN `metriknamen.json` / WHEN Vergleich mit `src/app/metric_catalog.py` (pytest) / THEN gleich; veränderter Eintrag ⇒ rot.
- [ ] Eigennamen: jeder Eintrag steht im Mockup und ist kein DE-Katalogwert.
- [ ] Messgröße und Besitzer: Test über die neu erzeugte Liste (Lückenzahl, jede Lücke hat Besitzer ≠ #2968, kein Besitzer-Verweis mit #2968).
- [ ] Bestehend grün: `elementliste_en_schutz.test.ts`, `elementliste_besitzer_kern.test.ts`, `elementliste_aktuell.test.ts`, `katalog_schluessel_haben_verwender.test.ts`.

## Acceptance Criteria

- **AC-1:** Given ein Mockup-Text mit Katalogmuster, dessen Werte alle aufgelöst sind (z. B. „Regenwahrscheinlichkeit in SMS“) / When der Generator `text_en` ermittelt / Then wird das EN-Muster mit Platzhaltern zugeordnet und der Eintrag ist keine Lücke, obwohl der Wortlaut kürzer als die halbe Textlänge ist.
  - Test: Generator-Test gegen den echten Katalog mit Positivfall; Gegenbeispiel mit unbekanntem Platzhalterwert bei kurzem Wortlaut bleibt Lücke.

- **AC-2:** Given ein verschachtelter Text wie „Darstellung Böen in Telegram: Roh“ / When der Generator ihn auflöst / Then wird `bausteine.darstellung.name` mit aufgelöstem `{name}` und `{form}` zugeordnet; bei unbekanntem Wert oder Rekursionstiefe über 2 bleibt die Zeile Lücke.
  - Test: Generator-Test mit Positivfall, unbekanntem Wert und Tiefe 3.

- **AC-3:** Given ein Text mit Trenner „ · “ oder führendem „· “ / When der Generator ihn in Segmente zerlegt / Then ist die Zeile nur aufgelöst, wenn jedes Segment aufgelöst ist, und das EN ist die Segment-EN mit „ · “ verbunden; ein einziges unaufgelöstes Segment macht die ganze Zeile zur Lücke.
  - Test: Generator-Test mit „km/h · Mittelwind“, „· grün: bis 30 km/h“ und einem Gegenbeispiel mit unbekanntem Segment.

- **AC-4:** Given der bestehende Schutzfall „°C · vor der Etappe“ / When der Generator ihn auflöst / Then wird er nie über „{count} Etappe“ aufgelöst, sondern nur, wenn „vor der Etappe“ exakt im Katalog steht, sonst bleibt er Lücke.
  - Test: Schutz-Test gegen den echten Katalog, beide Ausgänge geprüft.

- **AC-5:** Given Texte ohne Buchstaben, reine Einheiten, Zahl mit Einheit, bekannte Kurz-/Protokoll-Token oder Eigennamen aus dem Schnappschuss / When der Generator sie verarbeitet / Then sind sie `sprachneutral: true` mit `text_en` = DE-Muster und `luecke: false`; ein deutsches Wort („Gewitter“) oder ein Eigennamen-Text außerhalb der Liste wird nie sprachneutral.
  - Test: Generator-Test mit Positiv- und Gegenfällen, inklusive Test, dass kein Eigennamen-Eintrag ein DE-Katalogwert ist.

- **AC-6:** Given ein Listeneintrag mit `sprachneutral: true` / When der EN-Abgleich seine Erwartung bildet / Then gilt das DE-Muster (Zahlen beliebig), der Eintrag ist im EN-Lauf prüfbar und nicht mehr `nicht_pruefbar`.
  - Test: Test von `erwartung` mit passendem und nicht passendem Live-Text.

- **AC-7:** Given der Schnappschuss `metriknamen.json` / When der Python-Drift-Test ihn gegen `src/app/metric_catalog.py` vergleicht / Then sind beide gleich, und eine Änderung am Katalog ohne Schnappschuss-Update macht den Test rot.
  - Test: pytest `tests/test_2968_metriknamen_schnappschuss.py` mit echtem Katalog.

- **AC-8:** Given die Elementliste wird neu erzeugt / When die Lücken gezählt werden / Then ist jede verbleibende Lücke ein Eintrag, der auch im DE-Abgleich nicht wörtlich aus dem Katalog stammt (Mockup≠App-Abweichung, ungebautes Pendant oder Kontodaten), die gemessene Zahl ist im Test als Obergrenze festgeschrieben (nur Senkung erlaubt), und es entstehen keine neuen Katalogschlüssel.
  - Test: Test über `elementliste.json` mit festgeschriebener Lückenobergrenze und Klassen-Zählung (`lueckenJeGrund`); Katalog-Verwender-Test bleibt grün.

- **AC-11:** Given ein Mockup-Text aus einem Katalogwert und einem durch Leerzeichen abgetrennten Zeichen ohne Buchstaben (z. B. „gelb >“, „rot <“) / When der Generator ihn auflöst / Then ist er aufgelöst, EN = EN des Katalogwerts mit demselben Zeichen („yellow >“); ein Text mit zwei Wörtern oder einem unbekannten Wort bleibt Lücke.
  - Test: positiv „gelb >“ gegen Ist-Katalog; Gegenbeispiele „Hagelschauer >“ und „gelb sehr >“ ⇒ Lücke.

- **AC-12:** Given ein DE-Text, der im Katalog unter mehreren Schlüsseln mit verschiedenem EN steht (z. B. „Fertig“ ⇒ „Finished“ und „Done“) / When der Generator den Eintrag erzeugt und der EN-Abgleich die Erwartung bildet / Then gelten alle EN-Kandidaten dieser Schlüssel als erwartet (Alternative), nicht nur der erste; ein fremder Text passt weiterhin nicht.
  - Test: „Fertig“ ⇒ Erwartung passt auf „Done“ und „Finished“, nicht auf „Ready“.

- **AC-13:** Given die Listenzeilen der Reiter Etappen und Orte (#3007, z. B. „E1 · Port d'Andratx → Estellencs“) / When die Elementliste neu erzeugt wird / Then bleiben ihre Katalogschlüssel und EN-Muster wie bisher erhalten (Sonderfall nur im Abschnitt `liste` dieser Reiter, analog `chipEn`).
  - Test: `elementliste_listen_3007.test.ts` bleibt grün.

- **AC-9:** Given die bereinigte `elementliste_besitzer.json` / When der Abgleich-Lauf die Besitzer anwendet / Then verweist kein Eintrag mehr auf #2968, jede verbleibende Lücke hat einen Besitzer mit passendem Grund, und `elementliste_besitzer_kern.test.ts` sowie `elementliste_aktuell.test.ts` sind grün.
  - Test: Besitzer-Test über alle Einträge gegen die neu erzeugte Liste.

- **AC-10:** Given der Generator-Lauf / When er endet / Then nennt die Ausgabe die verbleibenden Lücken je Grund (Mockup≠App-Abweichung, ungebautes Pendant, Eigennamen ohne Listeneintrag), und `gates_und_ratschen.md` beschreibt die Regeln a bis d im Abschnitt Elementliste.
  - Test: Generator-Test auf die Zusammenfassungsausgabe; Doku mit `# doc-compliance-test` nur für den Abschnitt.

## Known Limitations

- Prüftiefe „wie DE“ ist für Mockup≠App-Abweichungen und ungebaute Teile (Tempo-Karte, Reiter Orte/Etappen) strukturell nicht erreichbar, solange DE dort selbst abweicht; sie bleiben Lücke mit Besitzer.
- Die Eigennamen-Liste ist handgepflegt; neue Mockup-Eigennamen bleiben Lücke, bis sie eingetragen sind (bewusst, statt erfundener Neutralität).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Verfeinerung des Prüfwerkzeugs innerhalb bestehender Entscheidungen (ADR-0104 Zweisprachigkeit, ADR-0112 Oberflächen aus Bausteinen, Abnahme per Elementliste); keine Entscheidungsfläche wird geändert.

## Changelog

- 2026-11-19: Nach Umsetzungsmessung (540 Restlücken, davon 162 „Katalogwert + Zeichen“ und 54 mehrdeutiges EN): Regeln e/f und AC-11..AC-13 ergänzt, AC-8 auf festgeschriebene gemessene Zahl und Klassen statt 25 % umgestellt.

- 2026-11-19: Initial spec created
