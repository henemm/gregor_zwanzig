# Context

Workflow `feat-3194-elementliste-en-zusammengesetzt` — Issue #3194 (Refs #2913, #3192, #3111, #3151).

## Request Summary

Der Erzeuger `scripts/elementliste_aus_mockup.ts` ordnet Mockup-Texte nur dann einem EN-Katalogtext zu, wenn der DE-Text als Ganzes (exakt, als Platzhalter-Muster oder als „ · “-Segmente) im DE-Katalog steht. Die Wetter-Dialogtexte aus #3111 zeigt das Mockup aber zusammengesetzt, wie die App sie zusammenbaut (Verkettung mehrerer Katalogschlüssel). Diese Einträge bleiben `luecke: true` und hängen in `docs/context/einstellungen_neu/elementliste_besitzer.json` an `#3194` (Zählwächter: `tests/test_2913_c2_besitzerliste.py:135`, `"#3194": 108`). Aufgabe: deklarative Regel für zusammengesetzte Katalogtexte, Elementliste neu erzeugen, EN-Abgleich `--scope wetter`, Besitzer abräumen, Wächter nachziehen. Keine erfundenen EN-Sollwerte.

## Related Files

- `scripts/elementliste_aus_mockup.ts` (732 Z.): Erzeuger. Katalog laden `:92-104`; `norm` (Whitespace → 1 Leerzeichen, trim) `:106`; Platzhalter `{name}` `:107`; Index (`exakt`, `enJeDe`, `muster`) `:112-141`; `ermittleEn` (Einstieg) `:292-300`; `exaktEn` `:306`; `zeichenEn` (Regel e „gelb >“) `:321`; Sonderzuordner `listenzeileEn` `:337`, `chipEn` `:359`; Aufruf je Rohtext in `baueElemente` `:479-535` (EN-Zuordnung `:508`); Playwright-Erzeugung `erzeugeElementliste` `:570-672` (Grenzen-Dialog `data-edit` `:608-613`, Vorlagen-Auswahl/-Bestätigung `:616-620`); `lueckenKlasse`/`lueckenJeGrund` `:693-720`; CLI `:722-732`.
- `docs/context/einstellungen_neu/elementliste.json` (Artefakt, 844 KB, enthält `mockup_hash`; Neuerzeugung: `cd frontend && node --experimental-strip-types ../scripts/elementliste_aus_mockup.ts`, schreibt die Datei, druckt Lücken je Besitzer-Grund).
- `docs/context/einstellungen_neu/elementliste_besitzer.json`: 692 Besitzer, davon 108 `#3194`.
- `tests/test_2913_c2_besitzerliste.py:127-136`: Kommentar-Chronik und Soll-Map `soll` (`"#3194": 108`).
- Live-Komposition: `frontend/src/lib/components/organisms/wetter-tab/GrenzenEditor.svelte:34-40,73,93` (Titel = Schlüssel `_1`+`_2`; `mitAbweichung(hinweis)` = `${hinweis} ${abweichend(vorlage)}`); `VorlageKarte.svelte:40-41,79` (Rumpf = `ersetzt_*` + optional `verlust` + `bleibt`, per Leerzeichen).
- Katalog: `frontend/src/lib/i18n/messages/{de,en}/wetter.json`.
- Abgleich: `frontend/e2e/elementliste-abgleich.staging.spec.ts`, Logik `frontend/e2e/elementliste_abgleich_logik.ts`; Aufruf `cd frontend && npm run elementliste:abgleich -- --scope wetter [--sprache en] [--abnahme]` (Runbook `docs/reference/gates_und_ratschen.md:666-727`).
- Frontend-Tests des Erzeugers (`node --test`): `frontend/src/lib/__tests__/elementliste_en_zuordnung_2968.test.ts`, `elementliste_en_schutz.test.ts`, `elementliste_plural_3192.test.ts`, `elementliste_aktuell.test.ts` (Hash), `elementliste_abgleich_fixloop2.test.ts`; Browser-Test `frontend/e2e/elementliste-generator.mockup.spec.ts`.
- Specs: `docs/specs/modules/fix_3192_wetter_dialog_abgleich.md`, `feat_2968_elementliste_en_zuordnung.md`, `einstellungen_neu_neustart_adr_waechter_elementliste.md`.

## Existing Patterns

Zuordnung DE → Schlüssel → EN (`ermittleEn`, `:292`), nichts erfunden, Reihenfolge: (1) exakter Treffer des normalisierten DE-Textes im DE-Katalog (`exaktEn`; mehrere Schlüssel mit verschiedenem EN → `text_en_alternativen`, Regel f); (2) Katalogmuster mit `{platzhalter}` (`musterTreffer`, Wortlaut ≥ 4 Zeichen, eingesetzte Werte müssen aufgelöst sein; Plural-Prüfung `pluralPasst` #3192); (3) sprachneutral (Zahlen, Einheiten, Token, Eigennamen; Regel c); (4) „<Katalogwert> <Zeichen>“ (Regel e); (5) „ · “-Segmente, jedes Segment einzeln aufgelöst (Regel b). Sonst `luecke()`. Ein Schlüssel ohne EN-Wert zählt nie als Treffer (`:119`). Es gibt schon zwei Spezialzuordner im selben Stil (Chip, Listenzeile) — Vorbild für eine deklarative Tabelle.

Warum die 108 fallen: Das Mockup liefert Textknoten ohne Fuge (`obenzu viel` = `oben`+`zu viel` ohne Leerzeichen) bzw. Sätze, die in der App aus 2-3 Schlüsseln mit einem Leerzeichen zusammengesetzt werden. Kein Schlüssel hat solchen Gesamttext, ein „ · “ fehlt → Lücke.

## Dependencies

- Mockup `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` (unverändert; Hash bleibt).
- EN-Schlüssel sind vollständig vorhanden: `wetter.grenzen.{unten_1,unten_2,oben_1,oben_2,hinweis,abweichend}`, `wetter.gewitter.keins_gruen`, `wetter.vorlage.{ersetzt_route,ersetzt_vergleich,ersetzt_vergleich_ein,bleibt}`. Es muss kein Katalogtext neu erfunden werden.
- Neuerzeugung braucht Playwright aus `frontend/node_modules` und ändert `elementliste.json` (Hash-Test `elementliste_aktuell.test.ts` prüft nur den Mockup-Hash).
- Besitzer-Abgleichslogik (`leseBesitzer`/`wendeBesitzerAn`): ein Besitzer für ein Element wird wirkungslos, sobald der Eintrag keine Lücke mehr ist.

## Existing Specs/ADRs

ADR-0104 (Zweisprachigkeit; Protokoll-Token nie übersetzen, Nutzertexte nur über Katalog), ADR-0112 (Oberflächen nur aus Design-System-Bausteinen; Mockup-Bildabgleich je Scheibe, Elementliste als Prüfgrundlage), ADR-0124 (Mockup Fassung 4). Spezifisch: `feat_2968_elementliste_en_zuordnung.md` (Regeln a-f des EN-Zuordners — neue Regel g gehört dort angefügt oder in eine neue Spec), `fix_3192_wetter_dialog_abgleich.md` (Quelle der 108).

## Risks

- Falsche EN-Zuordnung wäre ein erfundener Sollwert: Verkettung nur über benannte Schlüsselfolge, jeder Schlüssel muss in DE und EN existieren, DE-Gesamttext muss die verkettete DE-Folge exakt ergeben (Fugenregel je Muster) — sonst Lücke.
- Platzhalter `{vorlage}` hat im Mockup konkrete Werte („Allgemein“, „Alpen-Trekking“); `{name}` aus dem Issue heißt im Katalog `{vorlage}`. Das EN-Muster behält `{vorlage}` (wie bestehende Regel: Werte nicht in EN kopieren).
- Der Rumpf-Text im Mockup hat nie die „Verlust“-Zeile (`wetter.vorlage.verlust`); Folge ohne sie ist eine Teilmenge, die Live-Seite kann sie bei Abweichungen zeigen — Abgleich-Verhalten gegen Live in `--scope wetter` prüfen.
- Orte mit genau einem Ort nutzt live `ersetzt_vergleich_ein`; Mockup zeigt nur „diese Orte“ → Folge `ersetzt_vergleich`.
- Zählwächter ist hart (`soll`-Map); jeder Rest nach der Abräumung muss bewusst gezählt werden.
- Grenzwert-Mutationsprobe (Pflicht): Verfälschung der Folge (z. B. falsche Fuge) muss ein Test fangen.

## Analysis

### Type: Feature

### Root Cause

Der Erzeuger kennt nur Ganztext-Treffer, Platzhalter-Muster und „ · “-Segmente. Die in der App aus mehreren Katalogschlüsseln zusammengesetzten Texte (GrenzenEditor, VorlageKarte) stehen im Mockup nur als DE-Gesamttext; es gibt keine Regel „Text = Verkettung von Schlüsseln“. Die 108 Besitzer-Einträge (Stand `tests/test_2913_c2_besitzerliste.py:135`) setzen sich zusammen aus (Auswertung der Elementliste/Besitzerdatei):

| Muster | Anz. | DE-Text im Mockup | Schlüsselfolge DE/EN | Platzhalter |
|---|---|---|---|---|
| A Grenzen-Titel | 54 | „obenzu viel“, „untenzu wenig“ (Fuge: keine) | `wetter.grenzen.oben_1`+`oben_2` = „oben“,„zu viel“ / „upper“,„too much“; `unten_1`+`unten_2` = „unten“,„zu wenig“ / „lower“,„too little“ | keine |
| B Grünhinweis + Abweichend | 36 | „Grün ist alles zwischen „gelb unten“ und „gelb oben“. Ein leeres Feld heißt: auf dieser Seite keine Grenze. Abweichend von der Vorlage „X“.“ (Fuge: 1 Leerzeichen) | `wetter.grenzen.hinweis` + `wetter.grenzen.abweichend` / EN „Green is everything … no limit on this side.“ + „Changed from the template “{vorlage}”.“ | `{vorlage}` |
| C Gewitter-Hinweis | 6 | „„keins“ ist immer grün. Abweichend von der Vorlage „Allgemein“.“ | `wetter.gewitter.keins_gruen` + `wetter.grenzen.abweichend` / „“none” is always green.“ + „Changed from …“ | `{vorlage}` |
| D Bestätigungs-Rumpf | 4 (je ctx × {normal, luecken}) | „Ersetzt Metrik-Auswahl, Ampel-Grenzen und Alarmstufen dieses Trips. Zustellung, Etappen und Orte bleiben unverändert.“ / „… für diese Orte. …“ | `wetter.vorlage.ersetzt_route` bzw. `ersetzt_vergleich` + `wetter.vorlage.bleibt` / EN „Replaces the metric selection, … of this trip.“ + „Delivery, stages and locations stay unchanged.“ | keine |
| E Eigene Vorlage „Mallorca Frühling“ | 2 | Knopf „Mallorca Frühling“ (Konto-Name) | kein Katalogschlüssel (nur `wetter.dialog.name_platzhalter` „z.B. Mallorca Frühling“ / „e.g. Mallorca spring“ — Platzhaltertext, nicht der Knopf) | — |
| F nur-EN-Zusatztexte (art `zusaetzlich`) | 6 | live EN-Texte ohne Listeneintrag | siehe Befunde | — |

Summe 54+36+6+4+2+6 = 108 (Besitzer: 102 `element`, 6 `zusaetzlich`).

### Affected Files (with changes)

- `scripts/elementliste_aus_mockup.ts`: neue exportierte deklarative Tabelle `ZUSAMMENGESETZT` (Name, Schlüsselfolge, Fuge, optionale Platzhalter-Bindung) und Funktion `zusammengesetztEn(t, katalog)`; Einhängen in `ermittleEn` vor `luecke()` bzw. nach `exaktEn`/`musterTreffer` (Reihenfolge so, dass ältere Regeln nichts ändern). Ergebnis: `i18n_key` = erster Schlüssel (oder neues optionales Feld `i18n_keys`, siehe Open Questions-frei: Tech-Lead-Entscheidung), `text_en` = EN-Folge mit `{vorlage}` im Muster, `muster` = DE-Gesamtmuster mit `{vorlage}`.
- `docs/context/einstellungen_neu/elementliste.json`: Neuerzeugung.
- `docs/context/einstellungen_neu/elementliste_besitzer.json`: 100 Besitzer (A-D, gelöste Titel/Hinweise: 54+36+6+4) entfallen; E (2) und unlösbare Reste behalten `#3194` oder neues Issue.
- `tests/test_2913_c2_besitzerliste.py:127-136`: Kommentar ergänzen, `"#3194"` auf Restzahl.
- `frontend/src/lib/__tests__/elementliste_en_zuordnung_2968.test.ts` (oder neue Datei `elementliste_zusammengesetzt_3194.test.ts`): Tests je Muster A-D (Katalog-EN erwartet, Verfälschung rot), Negativtest (unbekannte Fuge → Lücke, fehlender EN-Schlüssel → Lücke).
- Spec: `docs/specs/modules/feat_3194_elementliste_en_zusammengesetzt.md` (ACs); Eintrag `docs/reference/gates_und_ratschen.md` (EN-Zuordner-Abschnitt, Regel g).

### Scope Assessment

4-6 Dateien (+1 Spec), ca. 90-130 LoC Erzeuger+Tabelle, ca. 80-120 LoC Tests; JSON-Artefakte maschinell (Liste neu erzeugt, Besitzer -100 Einträge). Klein-mittel, innerhalb des LoC-Limits.

### Technical Approach

Deklarative Tabelle (bevorzugt): je Muster eine Folge `[{schluessel}|{literal}]` mit Fuge (`''` für Titel, `' '` für Sätze) und optionalem Platzhalter `{vorlage}`. Matching: DE-Katalogwerte der Folge werden mit Fuge verkettet, `{vorlage}`-Stelle wird als Wert-Gruppe `(.+?)` gelesen (das Mockup-Wert bleibt unaufgelöst, wie bei `musterTreffer`), gegen `norm(t)` abgeglichen. Treffer nur, wenn jeder Schlüssel in DE **und** EN vorhanden ist (`:119`-Prinzip); EN = EN-Werte mit gleicher Fuge verkettet. Variantenbildung nur über explizite Tabellenzeilen (`ersetzt_route` vs. `ersetzt_vergleich`/`_ein`); Hinweis-Folge B/C = `[hinweis | keins_gruen]` × `[abweichend]` (Abweichend-Teil auch optional als eigene Zeile, falls Mockup Fälle ohne Abweichung zeigt; EN je Variante). Prüfung ohne Browser (`node --test`), dann Neuerzeugung, dann `npm run elementliste:abgleich -- --scope wetter` (DE und `--sprache en`) gegen Staging. Besitzer-Einträge nur streichen, die danach nicht mehr `luecke` sind; Reste neu zuordnen.

### Befunde gegen den Plan

1. Issue spricht von „{name}“; der Katalog-Platzhalter heißt `{vorlage}` (`wetter.grenzen.abweichend`), „{neu}“ kommt im Katalog nicht vor. Muss nicht eingeführt werden.
2. Die 108 sind nicht nur Dialogtexte: 6 sind `zusaetzlich`-Einträge (nur-EN-Live-Texte „Cloud cover“, „Rain probability“, „UV index“, „mm · total“, „°C · daily high · daily low“, „m · minimum“), 2 sind „Mallorca Frühling“ (Konto-Eigenname). Diese 8 sind keine zusammengesetzten Dialogtexte.
3. Der Zählwächter-Kommentar nennt „100 EN-Lücken“ aus #3192 (54+42+4) — übereinstimmend mit A+B+C+D = 100. Mit den +6 aus #3151 (zusaetzlich) und +2 (Mallorca) ergeben sich 108.
4. Teilweise lösbar, 3 der 6 `zusaetzlich`: „°C · Tageshöchst · Tagestief“ (Elementliste, `luecke`) = Einheit + `wetter.hinweis.temperature` („Tageshöchst · Tagestief“ / „daily high · daily low“); analog „mm · Summe“ → „mm · total“ (`wetter.hinweis.precipitation`), „m · Minimum“ → „m · minimum“ (`wetter.hinweis.visibility`). Heute scheitert Regel b, weil „Tageshöchst“ allein kein Schlüssel ist (Mehr-Segment-Katalogwert). Mit derselben Tabelle (Folge `Einheit-neutral` + `hinweis.*`) ließe sich das mit lösen, wenn die DE-Gegenstücke in der Liste stehen. Prüfen in der Spec; kein EN-Text erfunden.
5. Nicht aus dem Katalog zusammensetzbar (Besitzer bleibt): „Mallorca Frühling“ (2, Kontodaten, braucht Besitzer ≠ #2968 → #3194 oder neues Konto-Daten-Issue), „Cloud cover“, „Rain probability“, „UV index“ (EN-Metriknamen kommen aus dem Metrik-Register `GET /api/metrics`, nicht aus dem Katalog; DE-Gegenstück „Regenwahrscheinlichkeit“ ist selbst Lücke). Erwartung nach Umsetzung: #3194 = 5 bis 8 (Zahl erst nach Neuerzeugung festlegen).
6. Im Abgleich hängt die Prüfung am Ist-Text der Live-Seite: `ersetzt_vergleich_ein` und `verlust`-Zeile erscheinen live je nach Zustand; Mockup deckt sie nicht ab (siehe Risks).

### Open Questions

Keine Produktfrage. Technische Entscheidungen (Schlüsselnamen im Eintrag, Aufteilung Tests/Spec, neues Issue für Metriknamen-EN und Konto-Eigennamen) trifft der Tech Lead.
