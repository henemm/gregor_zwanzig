---
entity_id: feat_3258_sms_kuerzel_legende
type: feature
created: 2026-11-22
updated: 2026-11-22
status: draft
version: "1.0"
workflow: feat-3258-sms-kuerzel-legende
tags: [einstellungen-neu, reiter-wetter, elementlisten-abgleich, mockup, sms, legende, "#3258", "#3250", "#2913"]
---

# SMS-Kürzel-Legende „Kürzel erklärt“ im Mockup Fassung 4 (Option C)

## Approval

- [ ] Approved

## Purpose

Die App zeigt im Reiter Wetter unter „Was steht wo“ den aufklappbaren Block „Kürzel erklärt“ (Kürzel je aktiver SMS-Metrik mit Bedeutung, dazu feste Beispielwarnungen). Das Mockup Fassung 4 hat ihn nicht, daher stehen diese Live-Texte im Abgleich als „zusätzlich“ ohne Besitzer. Der PO hat am 22.11. im Issue #3258 entschieden: Der Block kommt in den Entwurf, die App ändert sich nicht. Diese Spec nimmt die Legende ins Mockup auf, erzeugt die Soll-Einträge über den Generator und führt die datensatzabhängigen SMS-Beispielwerte als Muster.

## Source

- **File:** `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` (Funktion `wasStehtWo()` Z. 624-659, `budgetZeile()` Z. 611-613, SMS-Tokens `TF` Z. 558 ff.)
- **Identifier:** neue Mockup-Funktion `legendeBlock()` (Block „Kürzel erklärt“ nach `budgetZeile(sm)`); Vorlage im Code: `frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte` Z. 203-218, `frontend/src/lib/components/shared/wetter-tab/wasStehtWoAnsicht.ts` (`legendeAus` Z. 153, `LEGENDE` Z. 53, `smsAus` Z. 133)

> Schicht: Entwurf (Mockup) und Prüfwerkzeug (Generator, Elementliste, Besitzerliste). Kein Go-API-/Python-Core-/Frontend-Produktcode, keine Änderung an Prüfdaten (`scripts/staging_pruefkonto_mockupdaten.py`).
> Trip/Orts-Vergleich: Die Legende gilt für beide Kontexte, wie live eine geteilte Karte (ADR-0097, `context="route"|"vergleich"`). Im Mockup entsteht sie einmal in `wasStehtWo()` für Trip und Orte, keine zweite Variante.
> Kanäle: keine Änderung an Briefing- oder Alarm-Inhalt (E-Mail, Telegram, SMS, Premium-SMS unberührt). Keine Nutzerdaten bewegt, daher kein Zwei-Nutzer-Test nötig.

## Estimated Scope

- **LoC:** ca. +45/-10 (ohne generierte Elementliste)
- **Files:** 6 bis 8
- **Effort:** medium

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` | MODIFY | Block „Kürzel erklärt“ unter der SMS-Beispielzeile in `wasStehtWo()`; Texte DE und EN wie Katalog |
| `scripts/elementliste_aus_mockup.ts` | MODIFY | Legende im Zustand normal (Aufklapper geöffnet) lesen, Abschnitt `was-steht-wo`; EN-Zuordnung über Katalogschlüssel `wetter.wsw.legende.*` |
| `docs/context/einstellungen_neu/elementliste.json` | MODIFY (generiert) | Mit dem Generator neu erzeugt, keine Handpflege |
| `frontend/e2e/elementliste_uebersicht_2969.test.ts` | MODIFY | Prüfsumme begründet nachziehen („#3258: Legende Kürzel erklärt“) |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | MODIFY | Betroffene herrenlose „zusätzlich“-Einträge (Legende, Beispielwarnungen) entfallen; SMS-Beispielwerte als `muster` mit `verweis` `#3258` |
| `tests/test_2913_c2_besitzerliste.py` | MODIFY | Zählwächter auf den neuen Stand |
| Elementlisten-Test für die Legende (node --test, neben `elementliste_uebersicht_2969.test.ts`) | CREATE | Soll-Einträge der Legende in DE und EN |

### Estimated Changes

- Files: 6 bis 8
- LoC: ca. +45/-10

**Nicht im Scope**
- Produktcode jeder Schicht (App-Legende, Katalog, Server-API `legend.*`), Prüfdaten des Prüfkontos.
- Neue Übersetzungen: Der Mockup-Wortlaut wird aus dem bestehenden Katalog übernommen, nicht neu formuliert.
- Weitere Mockup-Abweichungen des Reiters Wetter (eigene Issues im Epic #2913).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/feat-3258-sms-kuerzel-legende.md` | doc | Analyse, Optionen A bis C |
| Issue #3258, letzter Kommentar vom 22.11. | decision | PO: „Kürzel erklärt“ in den Entwurf, App unverändert |
| `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` | mockup | Soll, wird ergänzt |
| `frontend/src/lib/i18n/messages/{de,en}/wetter.json` | catalog | `wetter.wsw.legende.*`, `wetter.wsw.sms.*`, nur gelesen |
| `scripts/elementliste_aus_mockup.ts` | script | Generator |
| `frontend/e2e/elementliste_abgleich_logik.ts` | module | Abgleich, `musterAlsRegExp` für `{zahl}`-Muster |
| `frontend/e2e/elementliste-abgleich.staging.spec.ts` | test | Staging-Abgleich `--scope wetter` |
| `docs/specs/modules/feat_3251_abweichungszustand_vorlage.md` | spec | Muster-Spec; Vorbild datensatzabhängige Werte |
| `scripts/staging_pruefkonto_mockupdaten.py` | script | Prüf-Datensatz, nur gelesen |
| ADR-0095, ADR-0097, ADR-0104, ADR-0112, ADR-0124 | adr | Kanal-Parität, Code-Teilung, Zweisprachigkeit, Mockup-getriebene Scheiben, „Was steht wo“ |

## Implementation Details

Tech-Lead-Entscheidung Option C (Empfehlung der Analyse, durch die PO-Entscheidung bestätigt): Legende bewusst ins Mockup, Beispielwerte datensatzabhängig als Muster.

1. **Mockup:** In `wasStehtWo()` nach `budgetZeile(sm)` ein Aufklapper „Kürzel erklärt“ (`<details>`, Titel wie Katalog `wetter.wsw.legende.titel`) mit einer Definitionsliste: je Metrik mit SMS-Haken Kürzel und Bedeutung, danach die festen Einträge. Reihenfolge wie live (`legendeAus`: erst Metriken in Tabellenreihenfolge, dann feste Einträge; gleiches Kürzel nur einmal). Die festen Einträge tragen den Wortlaut aus dem Katalog `wetter.wsw.legende.*`: zeit_ab_gelb, amtliche_warnung („amtliche Warnung: Gewitter, Stufe hoch, ab 14 Uhr“), stufe_gelb/orange/rot, warnung_wind, warnung_starkregen, lawinenstufe, warnquelle_nicht_erreichbar. Bei Orten kommt zusätzlich der feste Eintrag `O1` mit seiner Bedeutung wie live (Server-Katalog). Der Wortlaut der Metrik-Bedeutungen („N gefühlt“, „D gefühlt“ usw.) wird vor dem Bau aus der Live-Antwort `legend.metrics` des Prüfkontos gelesen und im Mockup übernommen; der Block folgt der aktiven Metrik-Auswahl des Mockups. Keine neue CSS-Klasse außerhalb des Design-Systems (ADR-0112).
2. **Sprache:** Das Mockup führt DE-Texte; die EN-Entsprechung bestimmt der Generator über die Katalogschlüssel (wie bei den übrigen Mockup-Texten). Protokoll-Token und Kürzel werden nie übersetzt (ADR-0104).
3. **Generator:** Im Zustand normal des Reiters Wetter den Aufklapper öffnen und die Legende als Elemente des Abschnitts `was-steht-wo` lesen. Die festen Beispielwarnungen erhalten ihren `i18n_key` aus `wetter.wsw.legende.*`, damit der EN-Soll-Text aus dem Katalog kommt und keine EN-Lücke entsteht.
4. **SMS-Beispielwerte:** FN12, FD12/16 und die ganze SMS-Zeile („… TF- FN12 FD12/16 …“) hängen am Prüf-Datensatz (Mockup: `FN7 FD7/12`). Sie werden in der Elementliste als Muster geführt, nach dem `{count}`/`{zahl}`-Vorbild und #3251: Zahlen werden zu `{zahl}`, die Zeichenzahl zu `{zahl}`; die Besitzer-Einträge nennen als `grund` „Mockup-Beispieldaten, hängt vom Prüf-Datensatz ab“ und `verweis` `#3258`. Das Muster darf nur Zahl-Text erklären (`{zahl}`), keinen beliebigen Text.
5. **Elementliste und Prüfsumme:** Generator laufen lassen, keine Handpflege. Prüfsumme in `elementliste_uebersicht_2969.test.ts` mit Begründung nachziehen. Der Diff der Elementliste zeigt nur neue Legenden-Einträge, geänderte Beispielzeile und den Mockup-Hash.
6. **Besitzerliste:** Die betroffenen herrenlosen „zusätzlich“-Einträge im Reiter Wetter (Legende, Beispielwarnungen, Kürzel als Textknoten) verschwinden, weil sie jetzt Soll-Einträge haben. Bleiben Einträge übrig (zum Beispiel Kürzel von Metriken, die der Prüf-Trip aktiv hat, das Mockup aber nicht), werden sie einzeln mit `grund` und `verweis` `#3258` zugeordnet. Zählwächter in `tests/test_2913_c2_besitzerliste.py` anpassen.
7. **Staging-Abgleich:** `--scope wetter` in DE und EN, für Trip und Orte, vorher (Stand 16 „abweichend ohne Besitzer“) und nachher; beide Läufe als Artefakt ablegen.

## Expected Behavior

- **Input:** Mockup Fassung 4 mit Legende; Staging-Prüfkonto (Trip und Orte), Sprache DE und EN.
- **Output:** Elementliste enthält Legende und Beispielwarnungen als Soll-Einträge (Trip und Orte, DE und EN); der Abgleich findet sie live. SMS-Beispielwerte laufen als Muster.
- **Side effects:** Wechsel „zusätzlich“ zu „gefunden“ ist erwünscht; keine neue Abweichung. Produktverhalten unverändert.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Elementlisten-Test (node --test): GIVEN die neu erzeugte Elementliste / WHEN der Abschnitt `was-steht-wo` gelesen wird / THEN enthält er „Kürzel erklärt“, „amtliche Warnung: Gewitter, Stufe hoch, ab 14 Uhr“, „Warnung Wind“, „Warnung Starkregen“ mit EN-Soll „Abbreviations explained“, „official warning: thunderstorm, level high, from 2 pm“, „wind warning“, „heavy rain warning“ (rot vor dem Generatorlauf).
- [ ] Reihenfolge-Test: GIVEN Mockup-Legende und `legendeAus`-Regel / WHEN die Einträge gelesen werden / THEN stehen Metrik-Kürzel vor den festen Einträgen, jedes Kürzel einmal.
- [ ] Muster-Test: GIVEN die SMS-Beispielzeile mit FN12 FD12/16 / WHEN sie gegen den Soll-Eintrag `FN{zahl} FD{zahl}/{zahl}` verglichen wird / THEN passt sie; ein Text mit Buchstaben statt Zahl passt nicht (Gegenprobe gegen „beliebiger Text“).
- [ ] `elementliste_uebersicht_2969.test.ts` grün mit begründeter neuer Prüfsumme.
- [ ] `tests/test_2913_c2_besitzerliste.py`: keine herrenlosen Einträge, Zählwächter auf neuem Stand.
- [ ] Staging-Abgleich `--scope wetter` DE und EN, Trip und Orte, vorher/nachher: Legende und Beispielwerte gefunden, keine neuen Abweichungen, „abweichend ohne Besitzer“ höchstens 16, „zusätzlich“ niedriger als vorher.

## Acceptance Criteria

- **AC-1:** Given das Mockup Fassung 4 im Reiter Wetter, Bereich „Was steht wo“ / When der Nutzer den Block „Kürzel erklärt“ öffnet / Then sieht er je aktiver SMS-Metrik Kürzel mit Bedeutung und danach die festen Beispielwarnungen, in derselben Reihenfolge und mit demselben Wortlaut wie in der App, für Trip und Orte.
  - Test: Elementlisten-Test auf die Legenden-Einträge; Mutation (Block aus `wasStehtWo()` entfernt) rötet ihn.

- **AC-2:** Given die Elementliste wird mit dem Generator neu erzeugt / When Deutsch und Englisch gelesen werden / Then stehen die festen Beispielwarnungen mit Soll-Text aus dem Katalog `wetter.wsw.legende.*` (zum Beispiel „Warnung Wind“ und „wind warning“) in der Liste, ohne EN-Lücke und ohne neu erfundene Übersetzung.
  - Test: Elementlisten-Test auf `text_de` und `text_en` der festen Einträge.

- **AC-3:** Given die SMS-Beispielwerte FN12, FD12/16 und die ganze SMS-Zeile hängen am Prüf-Datensatz / When die Elementliste sie führt / Then sind sie als Muster mit `{zahl}` erfasst und mit Besitzer `#3258` begründet, und das Muster erklärt nur Zahlen, keinen beliebigen Text.
  - Test: Muster-Test mit passender Zahl-Zeile und Gegenprobe mit Buchstaben.

- **AC-4:** Given die Besitzerliste nach der Änderung / When der Abgleich beide Sprachen prüft / Then sind die vorher herrenlosen „zusätzlich“-Einträge der Legende entfallen oder einzeln mit Grund und Verweis zugeordnet, und es gibt keinen herrenlosen Eintrag.
  - Test: `tests/test_2913_c2_besitzerliste.py` grün; Vorher/Nachher-Diff der Besitzerliste.

- **AC-5:** Given der Staging-Abgleich `--scope wetter` in Deutsch und Englisch für Trip und Orte / When er nach der Änderung läuft / Then werden Legende und Beispielwerte live gefunden, es entstehen keine neuen Abweichungen, „abweichend ohne Besitzer“ liegt höchstens beim Vorher-Wert 16 und „zusätzlich“ ist gesunken.
  - Test: Abgleich DE+EN vorher/nachher als Artefakt.

- **AC-6:** Given die Elementliste wurde neu erzeugt / When die Prüfsumme geprüft wird / Then stimmt sie mit der Datei überein und ist im Test mit Begründung nachgezogen, und der Rest der Liste (übrige Reiter und Seiten-Zustände) bleibt unverändert.
  - Test: `elementliste_uebersicht_2969.test.ts`; Diff der Elementliste zeigt nur Legenden-Einträge, die Beispielzeile und den Mockup-Hash.

- **AC-7:** Given Nutzer mit Trips und Orts-Vergleichen / When sie die Anwendung nutzen / Then ändert sich nichts, denn Produktcode, Katalog und Prüfdaten bleiben unverändert.
  - Test: Diff enthält keine Datei unter `frontend/src/`, `internal/`, `src/`, `api/` und nicht `scripts/staging_pruefkonto_mockupdaten.py`.

## Definition of Done

- [ ] Spec freigegeben (`approved`/`freigabe`), Tests rot vor Umsetzung, dann grün
- [ ] Mockup um den Block „Kürzel erklärt“ ergänzt, Wortlaut aus dem Katalog
- [ ] Elementliste mit dem Generator neu erzeugt, Prüfsumme begründet nachgezogen
- [ ] Besitzerliste angeglichen, Zählwächter angepasst, keine herrenlosen Einträge
- [ ] Staging-Abgleich `--scope wetter` DE und EN, Trip und Orte, vorher/nachher als Artefakt abgelegt, Ergebnis gemäß AC-5
- [ ] Mutationsprobe: Legendenblock im Mockup entfernt oder Muster auf beliebigen Text verfälscht rötet je einen Test
- [ ] Keine Änderung an Produktcode und Prüfdaten (AC-7)
- [ ] PR mit allen 6 CI-Checks grün, Deploy, Selftest

## Known Limitations

- Die Metrik-Bedeutungen kommen live vom Server (`legend.metrics`); das Mockup trägt sie als feste Texte. Ändert der Server-Katalog sie, zeigt der Abgleich die Abweichung, das Mockup wird dann nachgezogen.
- Die Orte-SMS nutzt andere Token als die Trip-SMS; die Legende zeigt je Kontext nur die zugehörigen Kürzel. Beispielwerte (FN/FD) gibt es nur für Trip.
- Weitere Mockup-Abweichungen des Reiters Wetter bleiben bei ihren eigenen Issues.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Ausführung von ADR-0112 (Mockup-getriebene Scheiben) und ADR-0124 (Was steht wo) nach PO-Entscheidung vom 22.11. im Issue #3258; keine neue Grundsatzentscheidung, Produktverhalten unverändert.

## Changelog

- 2026-11-22: Initial spec created (Option C: Legende ins Mockup, SMS-Beispielwerte als Muster, Besitzerliste angleichen)
