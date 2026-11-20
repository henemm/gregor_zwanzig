---
entity_id: feat_3194_elementliste_en_zusammengesetzt
type: feature
created: 2026-11-20
updated: 2026-11-20
status: draft
version: "1.0"
workflow: feat-3194-elementliste-en-zusammengesetzt
tags: [elementliste, i18n, pruefwerkzeug, generator]
---

# Elementliste: EN-Zuordnung für zusammengesetzte Katalogtexte (#3194)

## Approval

- [ ] Approved

## Purpose

Das Mockup zeigt die Wetter-Dialogtexte (#3111) so, wie die App sie aus mehreren Katalogschlüsseln zusammensetzt (Titel „obenzu viel“, Grünhinweis plus „Abweichend von der Vorlage …“, Bestätigungs-Rumpf). Der Erzeuger kennt nur Ganztext-, Platzhalter- und „ · “-Treffer und lässt diese 100 Einträge als EN-Lücke stehen. Diese Spec ergänzt die Regel g „zusammengesetzt“ (Folge benannter Katalogschlüssel), ohne englischen Text zu erfinden und ohne neue Katalogschlüssel.

## Source

- **File:** `scripts/elementliste_aus_mockup.ts`
- **Identifier:** neue Tabelle `ZUSAMMENGESETZT`, Funktion `zusammengesetztEn`, Einhängen in `ermittleEn`

> Schicht: reines Prüfwerkzeug (Skripte, Tests, Daten-Artefakte, Doku). Kein Produktcode, kein Nutzerpfad, keine Nutzerdaten, kein Trip/Vergleich-Pendant, keine Kanal-Inhalte betroffen.

## Scope

**Im Scope:** deklarative Tabelle zusammengesetzter Muster (A Grenzen-Titel 54, B Grünhinweis plus abweichend 36, C Gewitter-Hinweis plus abweichend 6, D Bestätigungs-Rumpf 4), Neuerzeugung `elementliste.json`, Besitzerdatei von den gelösten 100 abräumen, Zählwächter `tests/test_2913_c2_besitzerliste.py` („#3194“) auf die Restzahl, Tests, Doku-Absatz Regel g.

**Nicht im Scope:** neue oder geänderte Katalogtexte; Eigenname „Mallorca Frühling“ (2, Kontodaten) und EN-Metriknamen „Cloud cover“, „Rain probability“, „UV index“ aus dem Metrik-Register (je Besitzer bleibt #3194); die Folge „Einheit + `wetter.hinweis.*`“ („mm · Summe“ usw.); Änderungen an Regeln a–f, am Abgleich oder am Mockup.

## Estimated Scope

- **LoC:** +220 / -110 (Erzeuger und Tabelle ca. 110, Tests ca. 110, Besitzerdatei schrumpft maschinell)
- **Files:** 6 (Erzeuger, neue Testdatei, `elementliste.json`, `elementliste_besitzer.json`, Zählwächter, `gates_und_ratschen.md`)
- **Effort:** small-medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/i18n/messages/{de,en}/wetter.json` | Katalog | einzige Quelle: `wetter.grenzen.{unten_1,unten_2,oben_1,oben_2,hinweis,abweichend}`, `wetter.gewitter.keins_gruen`, `wetter.vorlage.{ersetzt_route,ersetzt_vergleich,bleibt}` |
| `GrenzenEditor.svelte`, `VorlageKarte.svelte` | Komponenten (nur lesen) | Live-Komposition und Fuge der Schlüsselfolgen |
| `feat_2968_elementliste_en_zuordnung.md` | Spec | Regeln a–f, Vorbild; Regel g schließt an |
| `fix_3192_wetter_dialog_abgleich.md` | Spec | Quelle der 100 Lücken |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | Daten | Besitzerliste (108 Einträge #3194) |
| Issues #2913, #3192, #3111, #3151 | Issue | Epic, Herkunft der Lücken |

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Verfeinerung des Prüfwerkzeugs innerhalb bestehender Entscheidungen (ADR-0104 Zweisprachigkeit: Nutzertexte nur über den Katalog, ADR-0112 Oberflächen aus Bausteinen mit Elementliste als Prüfgrundlage, ADR-0124 Mockup Fassung 4); keine Entscheidungsfläche wird geändert.

## Implementation Details

**Regel g: zusammengesetzt.** Neue exportierte Tabelle `ZUSAMMENGESETZT`: je Zeile eine Folge benannter Katalogschlüssel mit Fuge (A leer, B bis D ein Leerzeichen) und optionalem Platzhalter `{vorlage}`. Zeilen: A1 `oben_1`+`oben_2`, A2 `unten_1`+`unten_2`; B `hinweis`+`abweichend`; C `keins_gruen`+`abweichend`; D1 `ersetzt_route`+`bleibt`, D2 `ersetzt_vergleich`+`bleibt`.

Matching in `zusammengesetztEn(t, katalog)`: DE-Werte der Folge mit der Fuge verketten, `{vorlage}` als Wertgruppe lesen (Wert bleibt wie bei `musterTreffer` unaufgelöst), gegen `norm(t)` vollständig abgleichen. Treffer nur, wenn JEDER Schlüssel in DE und EN existiert (Prinzip „kein EN-Wert, kein Treffer“). EN = EN-Werte mit derselben Fuge, `{vorlage}` bleibt Platzhalter. Eintrag: `i18n_key` = erster Schlüssel der Folge, `muster` = DE-Gesamtmuster mit `{vorlage}`, wenn die Folge einen Platzhalter trägt (B, C), sonst `null` wie bei Regel b und der sprachneutralen Regel (`muster` steht im Erzeuger nur für Texte mit Platzhalter; Festlegung in GREEN, 20.11.), `luecke: false`. Einhängen in `ermittleEn` nach den Regeln a–f und vor `luecke()`; ältere Regeln ändern sich nicht.

**Neuerzeugung und Besitzer.** Elementliste per `cd frontend && node --experimental-strip-types ../scripts/elementliste_aus_mockup.ts` neu erzeugen (Mockup-Hash bleibt). Besitzer-Einträge, die danach keine Lücke mehr sind, werden entfernt; es bleiben die echten Restfälle (erwartet 8: 2 Eigenname, 6 EN-Zusatztexte; exakte Zahl nach Neuerzeugung festschreiben). Der Zählwächter erhält die Restzahl und einen Chronik-Kommentar.

**Risiko Live-Abweichung.** Live zeigt `ersetzt_vergleich_ein` (genau ein Ort) und die Zeile `verlust`; das Mockup nicht. Das Mockup bildet nur `ersetzt_vergleich` ab. Die Spec ordnet nur zu, was das Mockup zeigt; EN-Abgleich `--scope wetter` prüft, dass daraus keine neue Abweichung entsteht.

**Doku.** Absatz Regel g im Abschnitt Elementliste von `docs/reference/gates_und_ratschen.md`.

## Expected Behavior

- **Input:** Mockup-Text (DE), echter Katalog, Tabelle `ZUSAMMENGESETZT`.
- **Output:** je passendem Text `text_en` aus den EN-Katalogtexten in Folge, `luecke: false`; sonst unverändert Lücke.
- **Side effects:** neu erzeugte `elementliste.json`, kleinere Besitzerdatei, EN-Abgleich meldet für diese Texte `gefunden` statt `nicht_pruefbar`.

## Test Plan

### Automated Tests (TDD RED)

Neue Datei `frontend/src/lib/__tests__/elementliste_zusammengesetzt_3194.test.ts` (`node --test`, echter Katalog, keine Mocks); Python-Test `tests/test_2913_c2_besitzerliste.py`.

- [ ] A: GIVEN „obenzu viel“ und „untenzu wenig“ / WHEN `ermittleEn` / THEN `text_en` „upper too much“ bzw. „lowertoo little“ nach EN-Fuge exakt aus `oben_1`+`oben_2` (Wert aus dem Katalog gelesen, nicht im Test erfunden).
- [ ] B/C: GIVEN Grünhinweis bzw. „keins“-Hinweis plus „Abweichend von der Vorlage „Allgemein““ / THEN EN = EN-Hinweis + EN-abweichend mit `{vorlage}`.
- [ ] D: GIVEN beide Rumpf-Texte (Trip, Orte) / THEN passende EN-Folge je Kontext, keine Vermischung.
- [ ] Negativ: GIVEN Text mit falscher Fuge, fehlendem Teil oder fremdem Zusatz / THEN Lücke; GIVEN Schlüssel ohne EN-Wert / THEN Lücke.
- [ ] Unverändert: GIVEN Regeln-a–f-Fälle (`elementliste_en_zuordnung_2968.test.ts`, `elementliste_en_schutz.test.ts`) / THEN weiter grün.
- [ ] Besitzer und Wächter: GIVEN neu erzeugte Liste / THEN „#3194“-Besitzer = Restzahl, jeder Besitzer verweist auf eine echte Lücke; `tests/test_2913_c2_besitzerliste.py` grün.
- [ ] Erzeuger zweimal laufen lassen: THEN Ausgabe identisch.
- [ ] Mutationsprobe (Pflicht): falsche Fuge oder vertauschte Schlüsselfolge in der Tabelle macht mindestens einen Test rot.

## Acceptance Criteria

- **AC-1:** Given ein Mockup-Text, der genau der verketteten DE-Folge eines Tabellenmusters entspricht (z. B. „obenzu viel“) / When der Generator `text_en` ermittelt / Then entsteht `text_en` exakt aus den EN-Katalogtexten derselben Schlüssel in derselben Reihenfolge mit derselben Fuge, und der Eintrag ist keine Lücke.
  - Test: Generator-Test je Muster A bis D gegen den echten Katalog; Sollwert aus dem EN-Katalog gelesen.

- **AC-2:** Given ein Muster mit Platzhalter `{vorlage}` (Grünhinweis, „keins“-Hinweis, jeweils mit „Abweichend von der Vorlage „Allgemein““) / When der Generator den Text zuordnet / Then trägt `text_en` den Platzhalter `{vorlage}` statt des konkreten Vorlagenamens, und andere Vorlagennamen („Alpen-Trekking“) treffen dasselbe Muster.
  - Test: Generator-Test mit zwei verschiedenen Vorlagennamen, beide mit identischem EN-Muster.

- **AC-3:** Given ein Text, bei dem nicht ALLE Teile der Folge im DE-Katalog exakt passen (falsche Fuge, fehlender oder zusätzlicher Teil) oder ein Schlüssel keinen EN-Wert hat / When der Generator ihn verarbeitet / Then bleibt der Eintrag Lücke und es entsteht kein EN-Text ohne Katalogquelle.
  - Test: Negativtests mit falscher Fuge, abgeschnittenem Text, fremdem Zusatz und Schlüssel ohne EN.

- **AC-4:** Given die bisherigen Zuordnungen nach den Regeln a–f / When die Elementliste mit der neuen Regel neu erzeugt wird / Then bleiben alle bereits zugeordneten Einträge unverändert, und die Liste unterscheidet sich von der bisherigen nur in den Einträgen, die zuvor Lücke waren.
  - Test: Vergleich alte gegen neue `elementliste.json` je Eintrag-ID; geänderte Einträge waren vorher Lücke; `elementliste_en_zuordnung_2968.test.ts` und `elementliste_aktuell.test.ts` bleiben grün.

- **AC-5:** Given die Besitzerdatei nach der Neuerzeugung / When der Zählwächter läuft / Then trägt „#3194“ nur noch die echten Restfälle (Eigenname „Mallorca Frühling“, EN-Metriknamen aus dem Register, EN-Zusatztexte), jeder dieser Einträge ist weiterhin Lücke, und die Wächter-Zahl stimmt mit der Datei überein.
  - Test: `tests/test_2913_c2_besitzerliste.py` mit angepasster Soll-Zahl; Gegenprobe, dass kein Besitzer auf einen gelösten Eintrag zeigt.

- **AC-6:** Given der EN-Abgleich `--scope wetter --sprache en` gegen Staging / When er mit der neu erzeugten Liste läuft / Then führt die neue Regel zu keiner neuen Abweichung gegenüber dem Stand davor, und die 100 gelösten Einträge sind nicht mehr `nicht_pruefbar`.
  - Test: Abgleich-Lauf vor und nach der Änderung, Ergebnisse je Eintrag verglichen (Staging, `/e2e-verify`).

- **AC-7:** Given der Erzeuger / When er zweimal hintereinander auf demselben Mockup und Katalog läuft / Then ist die erzeugte `elementliste.json` byte-identisch.
  - Test: Test erzeugt die Liste zweimal und vergleicht den Inhalt.

## Definition of Done

- Alle ACs grün; Kern-Tests (`elementliste_*`, Zählwächter, `katalog_schluessel_haben_verwender.test.ts`) grün.
- Mutationsprobe der Implementierungsprüfung gefangen (falsche Fuge, vertauschte Folge).
- `elementliste.json` neu erzeugt, Besitzerdatei und Zählwächter auf die Restzahl.
- Doku Regel g in `gates_und_ratschen.md`; Issue #3194 erst nach Prod-Deploy und Selftest geschlossen.

## Known Limitations

- Das Mockup zeigt `ersetzt_vergleich_ein` und `verlust` nicht; diese Live-Varianten sind nicht zugeordnet (siehe Risiko oben). Die Tabelle trifft nur, was das Mockup tatsächlich zeigt.
- EN-Metriknamen (Metrik-Register, nicht Katalog) und Konto-Eigennamen bleiben Lücke mit Besitzer; Lösung braucht ein eigenes Issue und ist hier bewusst nicht erfunden.
- Die Folge „Einheit + `wetter.hinweis.*`“ („mm · Summe“) ist nicht Teil dieser Spec.

## Changelog

- 2026-11-20: Initial spec created
- 2026-11-20: Implementation Details präzisiert: `muster` nur bei Platzhalter-Folgen (B, C) gesetzt, bei A/D `null` (Erzeuger-Konvention, wie Regel b)
