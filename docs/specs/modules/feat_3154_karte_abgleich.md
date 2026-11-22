---
entity_id: feat_3154_karte_abgleich
type: refactor
created: 2026-11-22
updated: 2026-11-22
status: draft
version: "1.0"
workflow: karte-3154-abgleich
tags: [was-steht-wo, elementliste, abgleich, mockup, seed, "#3154", "#3122"]
---

# Abnahme-Abgleich der Karte „Was steht wo“ (#3154)

## Approval

- [ ] Approved

## Purpose

Schließt AC-21 der Spec `feat_3122_was_steht_wo.md`: Der Elementlisten-Abgleich für den Abschnitt `was-steht-wo` läuft mit `--strict` in Deutsch und Englisch ohne Abweichung, und das Soll/Ist-Bild (Trip, drei Orte, ein Ort) hat keinen offenen Befund. Die Live-Karte ist richtig und bleibt unverändert; abweichend sind der Seed des Prüfkontos, das Soll-Bild (Mockup Fassung 4) gegenüber bereits freigegebenen Entscheidungen und zwei Lücken im Abgleich-Werkzeug.

## Source

- **File:** `scripts/staging_pruefkonto_mockupdaten.py`, `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html`, `scripts/elementliste_aus_mockup.ts`, `frontend/e2e/elementliste_abgleich_logik.ts`
- **Identifier:** Seed-Soll `soll_wetter()` (Platzierungen), Mockup `wasStehtWo()` / `blockEinst()` / `budgetZeile()` / `smsCalc`, Generator `baueElemente`, Abgleich `bewerteAbschnitt` / `musterAlsRegExp` / `ermittleEn`

Schicht: Test-/Werkzeug-Schicht (Skripte, E2E-Hilfen, Mockup-Dokument). Kein Frontend-Produktcode, kein Go, kein Python-Core. Tabu (Sitzung #3237): `src/services/channel_list_resolver.py`, `src/services/placements.py`, `.claude/hooks/_soll_aus_konfiguration.py`, `api/routers/validator.py`.

Querschnitt: Trip/Ortsvergleich-Teilung unberührt (keine neue Komponente). Mandantentrennung: der Seed schreibt nur in das Staging-Prüfkonto, `user_id` kommt aus dem Login, kein `"default"`; Test mit zwei verschiedenen Konten (siehe AC-3). Kanäle: alle vier bleiben Gegenstand des Soll-Bilds, es ändert sich kein Ausgabeinhalt.

## Estimated Scope

- **LoC:** ~250 netto handgeschrieben, dazu mechanisch neu erzeugte Elementliste
- **Files:** ~8 handgeschrieben
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/specs/modules/feat_3122_was_steht_wo.md` | Spec | Nr. 5 / AC-7 (gesperrte Zellen), Teil A Nr. 4/5, AC-21, AC-27 |
| ADR-0124 | ADR | eine Tabelle „Was steht wo“, Grundauswahl einmal |
| ADR-0125 | ADR | Orte-SMS als Token-Zeile, ohne „+N“-Satz |
| `GET/PUT /api/briefings/{id}/placements?kind=route\|vergleich` | Go-API | Seed schreibt die gespeicherte Tabelle (nur genutzt, nicht geändert) |
| `docs/runbooks/staging_pruefkonto_seed.md` | Runbook | Seed-Aufruf, Prüfkonto-Login |
| `docs/context/einstellungen_neu/daten/kuerzel_bedeutung.json` | Daten | Vorbild für den EN-Metriknamen-Schnappschuss (#3258) |
| mockup-bildpruefer | Agent | Soll/Ist-Bild-Abnahme |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `scripts/staging_pruefkonto_mockupdaten.py` | MODIFY | Seed schreibt die Tabelle (Trip, Orte) in Mockup-Reihenfolge und -Formaten, idempotent |
| `tests/tdd/test_staging_pruefkonto_tabelle.py` | CREATE | Payload-Aufbau ohne Netz, Idempotenz, zwei Konten |
| `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` | MODIFY | Nachzug an freigegebene Entscheidungen (gesperrte Zellen, Gewitter-Knopf, Orte-SMS, Zeichenzahl, Ausblick-Schalter) |
| `scripts/elementliste_aus_mockup.ts` | MODIFY | Muster `{wert}`, `{n} von {max} Zeichen`, EN-Metriknamen |
| `docs/context/einstellungen_neu/daten/metrik_namen.json` | CREATE | EN-Schnappschuss der Metriknamen |
| `frontend/e2e/elementliste_abgleich_logik.ts` | MODIFY | `{wert}` mit Negativvorschau gegen Zellennamen |
| `frontend/e2e/*.test.ts` (Generator/Logik) | CREATE/MODIFY | node --test-Fälle zu AC-4/5/9/10/11 |
| `docs/context/einstellungen_neu/elementliste.json`, `elementliste_besitzer.json` | MODIFY (generiert / zwei Einträge gestrichen) | Neu erzeugt, keine Handpflege |

Nicht im Scope: Live-Karte (außer Fallback in Implementation Details Nr. 5), Backend, Tabu-Dateien von #3237.

## Definition of Done

- [ ] Spec freigegeben, Tests rot vor Umsetzung, dann grün
- [ ] Seed schreibt die Tabellen, Prüfkonto auf Staging neu befüllt
- [ ] Mockup nachgezogen, Elementliste neu erzeugt, Prüfsumme begründet nachgezogen, zwei veraltete Besitzer-Einträge gestrichen
- [ ] Staging-Abgleich `--strict` Abschnitt `was-steht-wo` DE und EN ohne Abweichung, vorher/nachher als Artefakt unter `docs/artifacts/karte-3154-abgleich/`
- [ ] mockup-bildpruefer Soll/Ist (Trip, drei Orte, ein Ort) ohne offenen Befund nach höchstens zwei Runden
- [ ] Adversary mit Mutationsprobe (Muster `{wert}` zu großzügig, gesperrte Zelle entfernt) rötet je einen Test
- [ ] PR mit allen 6 CI-Checks grün, Deploy, Selftest

## Implementation Details

1. **Seed** (`scripts/staging_pruefkonto_mockupdaten.py`): Payload-Aufbau als reine Funktion (ohne Netz testbar). Trip: Tabelle in Mockup-Reihenfolge (18 Zeilen inkl. der fünf Nur-Anzeige-Zeilen), Formate wie Mockup (Roh, außer Windrichtung/Gewitter/Bewölkung/Sonne = Einfach), Ausblick-Berichte wie Mockup. Orte: Temperatur Max und Min, Formate wie Mockup (Bewölkung, Sonne, Gewitter-E-Mail = Einfach), Ausblick wie Mockup (Abend). Ablauf GET, vergleichen, PUT (idempotent, Read-Modify-Write nur an `display_config.placements`).
2. **Mockup Fassung 4** an freigegebene Entscheidungen angleichen (optisches Soll sonst unverändert): sechs Fensterzeilen (Nacht, Tages-Tief/-Hoch, drei gefühlte Fensterwerte) in E-Mail und 3-Tages-Ausblick als gesperrt mit Grundtext; Gewitter-Einfach-Knopf nur in der E-Mail (Stellenliste je Metrik statt globalem `HASF`); Orte-SMS als Token-Zeile laut ADR-0125 ohne „+N“ und ohne Satz „Dafür steht +N je Ort“; Zeichenzahl in eigenem `<span>`; Ausblick-Schalter vor dem Titel, Titel als `aria-hidden`-Span wie live; Telegram-Marke „nur Tageswert“ nur falls die Neumessung sie als Abweichung zeigt.
3. **Generator** (`scripts/elementliste_aus_mockup.ts`): Beispielzellen und SMS-Beispielzeilen als Muster `{wert}`; zweites Element `{n} von {max} Zeichen`; EN-Metriknamen aus neuem Schnappschuss `docs/context/einstellungen_neu/daten/metrik_namen.json`.
4. **Abgleich** (`frontend/e2e/elementliste_abgleich_logik.ts`): `{wert}` in `musterAlsRegExp`, `neutralMuster`, `gegenMuster`, mit Negativvorschau gegen Zellennamen (`… in/im E-Mail|Telegram|SMS|Stundenverlauf|3-Tages-Ausblick`, `Darstellung …`, `Format of …`), damit ein fehlender Beispieltext nie den nächsten Zellennamen verschluckt. SMS-Kürzungsmarken („passt nicht mehr“) bleiben bewusst Wortlaut.
5. **Elementliste** neu erzeugen; die zwei Besitzer-Einträge `was-steht-wo` (Trip, Orte; „noch nicht gebaut“) streichen. Neue Besitzer-Einträge nur für Echtes mit offenem Issue. Fallback (nur wenn der Ausblick-Schalter nach Neuerzeugung noch abweicht): im Live-Titel einen eigenen Textknoten setzen, im Spec-Verlauf vermerken.

## Expected Behavior

- **Input:** Prüfkonto auf Staging mit gespeicherten Tabellen, Mockup Fassung 4 (angeglichen), neu erzeugte Elementliste.
- **Output:** `--strict` für Abschnitt `was-steht-wo` in DE und EN ohne Abweichung; Soll/Ist-Bild ohne offenen Befund.
- **Side effects:** Das Staging-Prüfkonto bekommt gespeicherte Tabellen (Trip und Orte). Kein Produktivsystem betroffen.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Seed (pytest, ohne Netz): GIVEN Mockup-Reihenfolge WHEN der Trip-Payload gebaut wird THEN liegen 18 Zeilen in Mockup-Folge mit Mockup-Formaten vor
- [ ] Seed (pytest): GIVEN der Orte-Seed WHEN der Payload gebaut wird THEN enthält er Temperatur Max und Min und Einfach für Bewölkung, Sonne, Gewitter-E-Mail
- [ ] Seed (pytest): GIVEN bereits gleich gespeicherte Tabelle WHEN der Seed läuft THEN entsteht kein PUT (idempotent); zwei verschiedene Konten bekommen je nur den eigenen Payload
- [ ] Abgleich (node --test): GIVEN Muster `Temp {wert}` WHEN der nächste Text ein Zellenname ist THEN passt es nicht (Negativvorschau)
- [ ] Abgleich (node --test): GIVEN ein fehlender Beispieltext WHEN bewertet wird THEN entsteht eine einzelne Abweichung, keine Reihenfolge-Kaskade
- [ ] Generator (node --test): GIVEN Beispielzelle und SMS-Zeile WHEN die Elementliste erzeugt wird THEN stehen dort `{wert}` und ein getrenntes Element `{n} von {max} Zeichen`
- [ ] Generator (node --test): GIVEN das Mockup mit gesperrten Fensterzellen und Gewitter-Knopf nur in der E-Mail WHEN der Generator die Elemente baut THEN tragen die gesperrten Zellen den Sperr-Grund und Gewitter hat nur eine Einfach-Darstellung
- [ ] Generator (node --test): GIVEN der EN-Schnappschuss WHEN `ermittleEn` läuft THEN haben „Regenwahrscheinlichkeit“, „Tiefe Wolken“, „UV-Index“, „Bewölkung“ einen EN-Namen
- [ ] Elementliste (node --test): GIVEN die neu erzeugte Datei THEN stimmt die Prüfsumme (`elementliste_aktuell.test.ts`)

## Acceptance Criteria

- **AC-1:** Given das Staging-Prüfkonto mit gespeicherter Tabelle des Trips / When die Karte „Was steht wo“ im Reiter Wetter des Trips angezeigt wird / Then stehen die Zeilen in der Reihenfolge des Soll-Bilds (Temperatur, Nacht, Tages-Tief, Tages-Hoch, Gefühlte … bis Schneefall) mit den Formaten des Soll-Bilds.
  - Test: Seed-Payload-Test (pytest) für Reihenfolge und Formate; auf Staging Sichtprüfung der Zeilenfolge im Trip-Reiter.

- **AC-2:** Given das Prüfkonto mit einem Abo mit drei Orten / When die Karte im Reiter Wetter angezeigt wird / Then zeigt die Temperaturzeile Max und Min, Bewölkung, Sonne und Gewitter-E-Mail stehen auf Einfach und der Ausblick folgt dem Soll-Bild (Abend).
  - Test: Seed-Payload-Test (pytest) für Metriken, Formate und Ausblick; Soll/Ist-Bild für drei Orte.

- **AC-3:** Given der Seed wird zweimal hintereinander und für zwei verschiedene Konten ausgeführt / When er die Tabellen schreibt / Then ändert der zweite Lauf nichts, und jedes Konto erhält nur seine eigene Tabelle.
  - Test: pytest ohne Netz (Payload-Aufbau, Vergleich vor PUT, zwei `user_id`).

- **AC-4:** Given das angeglichene Soll-Bild / When die sechs Fensterzeilen (Nacht, Tages-Tief, Tages-Hoch, drei gefühlte Fensterwerte) in E-Mail und 3-Tages-Ausblick betrachtet werden / Then sind diese Zellen als gesperrt mit Grundtext gezeichnet, wie es Spec Nr. 5 und AC-7 verlangen, nicht als normale Haken.
  - Test: Unit-Test über die Generator-Funktion (node --test): aus dem Mockup entstehen für diese Zellen Elemente mit Sperr-Grund; der Abgleich-Lauf (`--strict`, Abschnitt was-steht-wo) bewertet sie auf Staging als gefunden.

- **AC-5:** Given das angeglichene Soll-Bild / When die Darstellungs-Knöpfe von Gewitter betrachtet werden / Then gibt es den Einfach-Knopf nur in der E-Mail, in Telegram, Stundenverlauf und Ausblick nicht.
  - Test: Unit-Test über die Generator-Funktion (node --test): für Gewitter entsteht nur in der E-Mail ein Einfach-Element; der Abgleich-Lauf (`--strict`, Abschnitt was-steht-wo) findet an den übrigen Stellen keinen Knopf und meldet keine Abweichung.

- **AC-6:** Given das Soll-Bild für Orte / When die SMS-Spalte betrachtet wird / Then steht dort die Token-Zeile laut ADR-0125 (z. B. `O1 D19 W30@10(43@16) …`) ohne „+N“ je Ort, und der Satz „Dafür steht +N je Ort“ fehlt im Hinweis.
  - Test: Generator-Unit-Test auf die erzeugten Elemente; Abgleich Orte ohne Abweichung in der SMS-Spalte.

- **AC-7:** Given das Soll-Bild / When unter dem SMS-Beispiel die Zeichenzahl betrachtet wird / Then steht „{n} von {max} Zeichen“ als eigenes Element und das Beispiel selbst als Muster `{wert}`.
  - Test: Generator-Unit-Test (node --test) für die zwei Elemente.

- **AC-8:** Given das Soll-Bild und die Live-Karte / When der Bereich 3-Tages-Ausblick betrachtet wird / Then stehen Schalter und Titel in derselben Reihenfolge, und „Morgen-Briefing“ bzw. „Abend-Briefing“ erzeugen keine Reihenfolge-Abweichung.
  - Test: `--strict` für Trip meldet für die Ausblick-Zeilen nichts; sonst Fallback aus Implementation Details Nr. 5.

- **AC-9:** Given ein Muster `{wert}` / When der Abgleich einen Beispieltext erwartet, dieser aber fehlt / Then verschluckt `{wert}` keinen folgenden Zellennamen und es entsteht keine Kaskade „Reihenfolge im Abschnitt“.
  - Test: node --test mit Negativprobe gegen Zellennamen (E-Mail, Telegram, SMS, Stundenverlauf, 3-Tages-Ausblick, Darstellung, Format of).

- **AC-10:** Given die englische Oberfläche / When der Abgleich EN läuft / Then hat jede Metrik einen EN-Namen aus dem Schnappschuss, und keine Zeile ist wegen eines fehlenden EN-Namens „nicht prüfbar“.
  - Test: node --test auf `ermittleEn` mit den vier bisherigen Lücken; EN-`--strict` ohne `nicht_pruefbar` im Abschnitt.

- **AC-11:** Given die neu erzeugte Elementliste ohne die zwei veralteten Besitzer-Einträge / When der Abgleich mit `--abnahme` für den Abschnitt was-steht-wo läuft / Then wird der Abschnitt wirklich bewertet und nicht mehr als „Besitzer: noch nicht gebaut“ abgedeckt gemeldet, und die Prüfsumme der Elementliste stimmt.
  - Test: Abgleich-Lauf `--abnahme` auf Staging (Bericht enthält keinen Besitzer-Treffer „noch nicht gebaut“ im Abschnitt was-steht-wo, Abschnitt hat bewertete Elemente); `elementliste_aktuell.test.ts` (node --test) für die Prüfsumme.

- **AC-12:** Given das gesäuberte Prüfkonto auf Staging / When der Abgleich für den Abschnitt `was-steht-wo` mit `--strict` in Deutsch und in Englisch läuft / Then endet jeder Lauf ohne Abweichung, und jeder Treffer, der noch auftaucht, ist vor Abschluss einer Befundgruppe zugeordnet und behoben.
  - Test: Abgleich-Lauf auf Staging, Berichte `docs/artifacts/karte-3154-abgleich/abgleich-nachher-{de,en}.json` mit 0 Abweichungen.

- **AC-13:** Given Trip, Abo mit drei Orten und Abo mit einem Ort auf Staging / When der mockup-bildpruefer Soll und Ist vergleicht / Then bleibt nach höchstens zwei Runden kein offener Befund.
  - Test: Bildprüfer-Bericht (Soll/Ist) für alle drei Fälle; Live-Karte `WasStehtWoKarte.svelte` bleibt ohne Änderung, außer Fallback aus Implementation Details Nr. 5.

## Known Limitations

- Beispielwerte prüfen nur die Form (`{wert}`), nicht die Zahl: der Datensatz `placements_beispiel.py` hat eigene Zahlen, das Mockup andere. Die inhaltliche Richtigkeit der Beispiele sichern die Tests der Beispiel-Erzeugung (B2), nicht dieser Abgleich.
- SMS-Kürzungsmarken („passt nicht mehr“) bleiben ausgabeabhängig und sind nicht als Muster entschärft.
- Übrige Abweichungen außerhalb von `was-steht-wo` (Kopf, Vorlage, Grenzen, Zustellung-Lücken, Orte-Erklärtext, Vergleichstabelle-Kopf, #2795) gehören nicht zu #3154.
- Der Abgleich dauert je Sprache etwa 7 Minuten.
- Entfernen des Altpfads `ALTBESTAND_UEBER_UMRECHNUNG` und Validator-Soll bleiben bei #3237/#3273.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue (Bezug ADR-0124, ADR-0125)
- **Rationale:** Das Soll-Bild wird an bereits freigegebene Entscheidungen angeglichen; es entsteht keine neue Produkt- oder Architekturentscheidung.

## Changelog

- 2026-11-22: Initial spec created
- 2026-11-22: Umlaute korrigiert; Nachweise AC-4, AC-5, AC-11 als Verhalten statt Dateiinhalt
