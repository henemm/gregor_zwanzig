---
entity_id: fix_3241_elementliste_en_metrikzeile_chips
type: bugfix
created: 2026-11-28
updated: 2026-11-28
status: draft
version: "1.0"
workflow: fix-3241-en-chips-abgleich
tags: [elementliste, i18n, pruefwerkzeug, abgleich, wetter]
---

# Elementliste EN: Metrik-Zeilen und Metrik-Chips einzeln prüfbar (#3241)

## Approval

- [ ] Approved

## Purpose

Der englische Elementlisten-Abgleich (Reiter Wetter, Abschnitt `metriken`) kann Metrik-Zeilen („mm · Summe“, „m · Minimum“, „°C · Tageshöchst · Tagestief“, „· grün: bis 6“) und die Metrik-Chips „+ {metrik}“ nicht einzeln prüfen. Sie bleiben als Lücke oder Abweichung stehen, 61 Besitzer-Einträge verweisen auf #3241. Diese Spec macht alle einzeln prüfbar, ohne englischen Text zu erfinden, und räumt die Besitzer ab.

## Source

- **File:** `scripts/elementliste_aus_mockup.ts` und `frontend/e2e/elementliste_abgleich_logik.ts`
- **Identifier:** neuer Sonderfall `metrikZeileEn` (Erzeuger, Abschnitt `metriken`); `bewerteKontoChips`, `bewerteAbschnitt`, `NamensPaar` (Abgleich)

> Schicht: reines Prüfwerkzeug (Skripte, Tests, Daten-Artefakte). Kein Produktcode, kein Nutzerpfad, keine Nutzerdaten (Prüfkonto nur lesend), kein Trip/Vergleich-Pendant, keine Kanal-Inhalte betroffen.

## Estimated Scope

- **LoC:** ca. +180 / -90 (Erzeuger ~40, Abgleich ~50, Tests ~90, Besitzerdatei schrumpft maschinell)
- **Files:** 8
- **Effort:** low-medium

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `scripts/elementliste_aus_mockup.ts` | MODIFY | Sonderfall `metrikZeileEn` nur im Abschnitt `metriken`, Vorrang vor der Segmentregel |
| `docs/context/einstellungen_neu/elementliste.json` | MODIFY | neu erzeugt; genau 12 Einträge ändern sich (B 6, C 4, D 2), alle übrigen bleiben textgleich |
| `frontend/e2e/elementliste_abgleich_logik.ts` | MODIFY | `bewerteKontoChips`/`bewerteAbschnitt` mit Namenspaaren, EN-Einzelprüfung der Chips |
| `frontend/e2e/elementliste-abgleich.staging.spec.ts` | MODIFY | `namenDeEn` an die zwei `bewerteAbschnitt`-Aufrufe reichen |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | MODIFY | alle 61 Einträge mit Verweis #3241 entfernen |
| `tests/test_2913_c2_besitzerliste.py` | MODIFY | Zählwächter auf „#3241: 0“ |
| `frontend/e2e/fix3241_metrikzeile_erzeuger.test.ts` | CREATE | `node --test`: Erzeuger-Regel gegen echten Katalog und echte Liste |
| `frontend/e2e/fix3241_en_chips.test.ts` | CREATE | `node --test`: EN-Chip-Bewertung gegen echte Namenspaare und Schnappschuss |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/i18n/messages/{de,en}/wetter.json` | Katalog | einzige Quelle: `wetter.hinweis.*`, `wetter.gruen.{bis,ab,von_bis}` |
| `frontend/src/lib/components/shared/wetter-tab/ampelModell.ts`, `frontend/src/lib/components/organisms/wetter-tab/MetrikZeile.svelte` | Komponenten (nur lesen) | Live-Aufbau von Hinweis und Grünbereich, Vorbild der Schlüsselwahl |
| `docs/context/einstellungen_neu/daten/metrik_namen.json` | Daten | DE→EN-Metriknamen, geladen als `namenDeEn` (`NamensPaar`, #3422) |
| `feat_2968_elementliste_en_zuordnung.md` | Spec | Regeln a–f des Erzeugers |
| `feat_3194_elementliste_en_zusammengesetzt.md` | Spec | Regel g; ausdrücklich ausgeklammerte Folge „Einheit + `wetter.hinweis.*`“ wird hier gelöst |
| `feat_3419_elementliste_nachzug.md` | Spec | Vorbild DE-Chip-Logik |
| Issues #2913, #3241, #3154, #3422, #3009 | Issue | Epic, Herkunft, Namensregister, Abnahme |

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Verfeinerung des Prüfwerkzeugs innerhalb bestehender Entscheidungen (ADR-0104 Zweisprachigkeit: Nutzertexte nur über den Katalog, ADR-0112 Elementliste als Prüfgrundlage); keine Entscheidungsfläche ändert sich.

## Implementation Details

**1. Erzeuger.** Im Abschnitt `metriken` gilt vor der allgemeinen Segmentregel `metrikZeileEn`:
- „<Einheit> · <DE-Wert eines Schlüssels wetter.hinweis.*>“ wird zu „<Einheit> · <EN desselben Schlüssels>“, `i18n_key` ist der Hinweis-Schlüssel. Der Hinweis enthält selbst „ · “ (Temperatur: „Tageshöchst · Tagestief“), deshalb wird der Hinweis als Ganzes gegen den Katalog gelesen, nicht gesplittet.
- Grünbereich ohne Einheit („· grün: bis 6“, ebenso ab bzw. von–bis): DE-Muster „· grün: bis {bis}“, EN „· green: up to {bis}“, aus `wetter.gruen.*` ohne „ {einheit}“.
- Ergebnis: „mm · Summe“ zu „mm · total“, „m · Minimum“ zu „m · minimum“, „°C · Tageshöchst · Tagestief“ zu „°C · daily high · daily low“, „· grün: bis 6“ zu „· green: up to {bis}“. Fehlt DE oder EN eines Schlüssels, bleibt es Lücke („kein EN-Wert, kein Treffer“). Alle anderen Einträge bleiben textgleich, Element-IDs hängen am DE-Text und ändern sich nicht.

**2. Abgleich.** `bewerteKontoChips` und `bewerteAbschnitt` erhalten die Paare (`NamensPaar[]`). Nur im EN-Lauf gilt je Chip die Einzelerwartung „+ <EN-Name>“; der DE-Name kommt aus `text_de` über das DE-Muster „+ {metrik}“, der EN-Name aus dem Paar. Sichtbar im Konto ist gefunden. Nicht sichtbar verhält sich wie DE: das erste Element vertritt die Chip-Zeile, jedes weitere ist nicht_pruefbar „<EN-Text> ist in diesem Konto kein Chip“. Ohne Paar ist es nicht_pruefbar „kein EN-Name für <DE-Name>“ (fail-closed, nie geraten). Der DE-Lauf bleibt unverändert.

**3. Besitzer.** 61 Einträge #3241 entfernen: 54 Element-Besitzer (10 Klasse A sind schon heute gefunden, also veraltet) und 7 zusätzlich-Besitzer (3 davon, „Cloud cover“, „Rain probability“, „UV index“, treten nicht mehr auf, 4 verschwinden mit der neuen Liste). Zählwächter auf „#3241: 0“ mit Chronik-Kommentar.

**4. Neuerzeugung.** `cd frontend && node --experimental-strip-types ../scripts/elementliste_aus_mockup.ts`; Diff darf außerhalb der 12 Einträge nichts verschieben (Mockup-Drift-Risiko).

## Expected Behavior

- **Input:** Mockup-Text der Metrik-Zeile, Katalog `wetter`, Namenspaare, sichtbare Chips des Prüfkontos (EN).
- **Output:** 12 Metrik-Zeilen mit `text_en` und Katalogschlüssel; im EN-Abgleich je Chip gefunden oder nicht_pruefbar mit benanntem Grund.
- **Side effects:** neu erzeugte `elementliste.json`, kleinere Besitzerdatei; keine Produktänderung.

## Test Plan

### Automated Tests (TDD RED)

Kern-Schicht mit `node --test` (kein Vitest), echte Katalog-, Listen- und Schnappschussdateien, kein Mock-Theater; dazu der Python-Zählwächter als Strukturwächter der Besitzerliste (Verhaltensnachweis führen die node-Tests und der EN-Staging-Abgleich).

- [ ] Test 1: GIVEN echter Katalog und Mockup-Zeile „mm · Summe“ / WHEN der Erzeuger sie zuordnet / THEN EN „mm · total“ mit Schlüssel `wetter.hinweis.*`
- [ ] Test 2: GIVEN „°C · Tageshöchst · Tagestief“ / WHEN zugeordnet / THEN EN „°C · daily high · daily low“ (Hinweis als Ganzes, nicht gesplittet)
- [ ] Test 3: GIVEN „· grün: bis 6“ ohne Einheit / WHEN zugeordnet / THEN EN „· green: up to {bis}“, mit Einheit („mm“) bleibt das bisherige Ergebnis
- [ ] Test 4: GIVEN neu erzeugte Liste gegen die Liste vor der Änderung / WHEN verglichen / THEN ändern sich genau 12 Einträge, alle anderen sind textgleich
- [ ] Test 5: GIVEN EN-Lauf, Chip „+ Regenwahrscheinlichkeit“, Konto zeigt „+ Rain probability“ / WHEN bewertet / THEN gefunden
- [ ] Test 6: GIVEN EN-Chip, der im Konto nicht sichtbar ist / WHEN bewertet / THEN erstes Element vertritt die Zeile, weitere nicht_pruefbar „ist in diesem Konto kein Chip“
- [ ] Test 7: GIVEN Chip ohne Namenspaar / WHEN EN bewertet / THEN nicht_pruefbar „kein EN-Name für <DE-Name>“, kein geratener Name
- [ ] Test 8: GIVEN DE-Lauf mit denselben Eingaben wie vor der Änderung / WHEN bewertet / THEN identisches Ergebnis
- [ ] Test 9: GIVEN Besitzerliste / WHEN Zählwächter läuft / THEN „#3241: 0“ und kein Eintrag mit diesem Verweis

### Live-Schicht

Englischer Staging-Abgleich mit Prüfkonto, Scope wetter, in `/e2e-verify`.

## Acceptance Criteria

- **AC-1:** Given der englische Katalog kennt `wetter.hinweis.*` / When der Erzeuger die Metrik-Zeilen „mm · Summe“ und „m · Minimum“ zuordnet / Then lauten die englischen Texte „mm · total“ und „m · minimum“ mit dem Hinweis-Schlüssel der App
  - Test: Erzeuger-Regel gegen echten Katalog; im Staging-Abgleich sind beide Zeilen gefunden statt „Text nicht sichtbar“

- **AC-2:** Given der Hinweis „Tageshöchst · Tagestief“ enthält selbst ein „ · “ / When die Zeile „°C · Tageshöchst · Tagestief“ zugeordnet wird / Then lautet der englische Text „°C · daily high · daily low“ und nicht mehr nicht_pruefbar
  - Test: Erzeuger-Regel gegen echten Katalog; im Staging-Abgleich ist die Zeile gefunden

- **AC-3:** Given ein Grünbereich ohne Einheit („· grün: bis 6“) / When der Erzeuger ihn zuordnet / Then ist das Muster „· grün: bis {bis}“ mit englisch „· green: up to {bis}“ hinterlegt, Zeilen mit Einheit bleiben unverändert
  - Test: Erzeuger-Regel; Staging-Abgleich zeigt „· green: up to 6“ als gefunden

- **AC-4:** Given die Liste wird neu erzeugt / When sie mit der bisherigen verglichen wird / Then ändern sich genau die 12 Metrik-Zeilen-Einträge und alle übrigen Einträge bleiben textgleich
  - Test: Vergleich neue gegen bisherige `elementliste.json` im `node --test`

- **AC-5:** Given der englische Abgleich läuft mit dem Prüfkonto / When ein Metrik-Chip „+ <Name>“ bewertet wird / Then gilt die Einzelerwartung „+ <englischer Name>“ aus dem Namenspaar: sichtbar ist gefunden, nicht sichtbar verhält sich wie im deutschen Lauf
  - Test: Chip-Bewertung gegen echte Namenspaare und Schnappschuss; im Staging-Abgleich sind die Chips im Abschnitt metriken gefunden

- **AC-6:** Given ein Chip, für den kein DE→EN-Namenspaar existiert / When der englische Abgleich ihn bewertet / Then meldet er nicht_pruefbar mit „kein EN-Name für <DE-Name>“ und rät keinen Namen
  - Test: Chip-Bewertung mit Namen ohne Paar

- **AC-7:** Given der deutsche Abgleich / When er nach der Änderung läuft / Then sind Bewertung und Ergebnis jedes Chips und jeder Zeile identisch zu vorher
  - Test: DE-Lauf gegen denselben Schnappschuss wie vor der Änderung

- **AC-8:** Given die Besitzerliste / When der Zählwächter läuft / Then trägt kein Eintrag mehr den Verweis #3241, im englischen Abgleich tauchen „mm · total“, „m · minimum“, „°C · daily high · daily low“ und „· green: up to 6“ nicht mehr als zusätzlicher Text auf, und `--abnahme` erzeugt im Reiter Wetter keine neue herrenlose Abweichung
  - Test: `tests/test_2913_c2_besitzerliste.py` und englischer Staging-Abgleich mit `--abnahme`

## Definition of Done

- [ ] Spec freigegeben, Tests rot vor Umsetzung, dann grün
- [ ] Elementliste neu erzeugt, Diff nur in den 12 erwarteten `metriken`-Einträgen
- [ ] Staging-Lauf `--sprache en --scope wetter` (Prüfkonto) vorher/nachher als Artefakt unter `docs/artifacts/fix-3241-en-chips-abgleich/`; DE-Lauf Reiter Wetter unverändert
- [ ] Adversary mit Mutationsprobe (EN-Chip-Einzelerwartung, Sonderfall Metrik-Zeile, Grünbereich ohne Einheit) rötet je einen Test
- [ ] Keine Besitzer mit Verweis #3241, Zählwächter „#3241: 0“
- [ ] PR mit allen 6 CI-Checks grün, Deploy, Selftest, Issue #3241 geschlossen

## Known Limitations

- Chips, die im Prüfkonto wirklich fehlen, bleiben nicht_pruefbar („kein Chip in diesem Konto“); das ist beabsichtigt, kein Erzeugerfehler.
- Live-Texte, die das Mockup nicht zeigt, werden nicht zugeordnet; die Spec ordnet nur zu, was das Mockup enthält.

## Changelog

- 2026-11-28: Initial spec created (Issue #3241, Epic #2913)
