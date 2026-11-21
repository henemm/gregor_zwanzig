---
entity_id: feat_3251_abweichungszustand_vorlage
type: feature
created: 2026-11-21
updated: 2026-11-21
status: draft
version: "1.0"
workflow: feat-3251-abweichungszustand-vorlage
tags: [einstellungen-neu, reiter-wetter, elementlisten-abgleich, mockup, vorlagen, abweichung, "#3251", "#3205", "#2913"]
---

# Abweichungszustand der Vorlagenkarte in Elementliste und Abgleich (Option B)

## Approval

- [ ] Approved

## Purpose

Das Mockup Fassung 4 zeigt "▾ N Abweichung(en)" und die Zeile "Auf „{vorlage}“ zurücksetzen" erst, nachdem eine Metrik abgewählt wurde (Bedienzustand `devs>0`). Die Elementliste erfasst nur den Normalzustand, deshalb stehen für diese Texte keine Soll-Einträge, und der Abgleich deckt sie mit pauschalen Ausnahmen aus #3205 zu. Diese Spec erzeugt die Soll-Einträge über einen eigenen Script-Abschnitt, damit die Ausnahmen entfallen und der Abgleich die Texte wirklich prüft.

## Source

- **File:** `scripts/elementliste_aus_mockup.ts` (Script-Abschnitte im Reiter Wetter, Z. 640-690; `vorlage-auswahl` Z. 666)
- **Identifier:** neuer Abschnitt `vorlage-abweichung`; `datensatzFuerAbschnitt` und `SCRIPT_ABSCHNITT` in `frontend/e2e/elementliste_abgleich_logik.ts` (Z. 391, 474)

> Schicht: Prüfwerkzeug (Generator, Abgleich-Logik, Elementliste, Besitzerliste). Kein Go-API-/Python-Core-/Frontend-Produktcode, keine Änderung an Prüfdaten (`scripts/staging_pruefkonto_mockupdaten.py`) und kein dritter globaler Seiten-Zustand.
> Trip/Orts-Vergleich: Der Abschnitt wird wie `grenzen-*` und `vorlage-auswahl` über den geteilten Kontext-Mechanismus erzeugt, keine zweite Komponente (ADR-0097).
> Kanäle: keine Änderung an Briefing- oder Alarm-Inhalt (E-Mail, Telegram, SMS, Premium-SMS unberührt). Keine Nutzerdaten bewegt.

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `scripts/elementliste_aus_mockup.ts` | MODIFY | Neuer Script-Abschnitt `vorlage-abweichung` (frische Seite, eine Metrik per `data-rm` abwählen, `#content` mit `nur: 'vorlage-abweichung'` lesen) |
| `frontend/e2e/elementliste_abgleich_logik.ts` | MODIFY | `SCRIPT_ABSCHNITT` um `vorlage-abweichung` erweitern; `datensatzFuerAbschnitt` ordnet ihn `mit_abweichung` zu |
| `docs/context/einstellungen_neu/elementliste.json` | MODIFY (generiert) | Mit dem Generator neu erzeugt, keine Handpflege |
| `frontend/e2e/elementliste_uebersicht_2969.test.ts` | MODIFY | Prüfsumme begründet nachziehen |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | MODIFY | Pauschale Ausnahmen aus #3205 (Zurücksetzen-Zeile, DE und EN, ctx trip/wetter) streichen |
| `tests/test_2913_c2_besitzerliste.py` | MODIFY | Zählwächter anpassen, soweit er die gestrichenen Einträge zählt |
| `frontend/e2e/elementliste_abgleich_logik.test.ts` (bzw. vorhandener Logik-Test) | MODIFY | Test der Datensatz-Zuordnung |
| Elementlisten-Test für den neuen Abschnitt | CREATE/MODIFY | Test, dass die Elementliste die Soll-Einträge des Abschnitts enthält |

### Estimated Changes

- Files: 7 bis 8
- LoC: ca. +30/-12 (ohne generierte Elementliste)

**Nicht im Scope**
- Produktcode jeder Schicht, Prüfdaten des Prüfkontos, Mockup-Inhalt.
- Ein dritter globaler Zustand "abweichung" neben normal, laedt, fehler, luecken (würde jede Seite verdoppeln, siehe Kontextdatei).
- Weitere Bedienzustände (Grenzen, Alarm, Dialog), sie bleiben bei den vorhandenen Abschnitten.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/feat-3251-abweichungszustand-vorlage.md` | doc | Analyse, Optionen A bis C, Empfehlung B |
| `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` | mockup | Soll; `devs` steigt bei Klick auf `data-rm`, ab `devs>0` Abweichungstext und Zurücksetzen-Zeile |
| `scripts/elementliste_aus_mockup.ts` | script | Generator der Elementliste |
| `frontend/e2e/elementliste_abgleich_logik.ts` | module | Abschnitt-Zuordnung zu Prüf-Datensatz |
| `frontend/e2e/elementliste-abgleich.staging.spec.ts` | test | Staging-Abgleich, `--scope wetter` |
| `scripts/staging_pruefkonto_mockupdaten.py` | script | Datensatz `mit_abweichung` existiert bereits, nur gelesen |
| `frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte` | module | Zurücksetzen-Zeile bei `abweichungen > 0`, nur gelesen |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | data | Pauschale Ausnahmen aus #3205 |
| `docs/specs/modules/feat_3205_vorlagen_mockup.md` | spec | Herkunft der Ausnahmen (Weg B) |
| ADR-0097, ADR-0112 | adr | Code-Teilung; Mockup-getriebene Scheiben |

## Implementation Details

Tech-Lead-Entscheidung Option B: Script-Abschnitt statt dritter globaler Zustand, nach dem Muster der vorhandenen `grenzen-*`- und `vorlage-auswahl`-Abschnitte.

1. **Generator:** Im Wetter-Reiter, Zustand normal, nach den vorhandenen Script-Abschnitten ein Block von etwa fünf Zeilen: frische Seite aufrufen, eine aktive Metrik per `data-rm` abwählen (`devs` wird größer als 0), dann `#content` mit `lies(..., { nur: 'vorlage-abweichung' })` lesen. Die Abschnitts-Erkennung (Z. 444 ff.) ordnet die Elemente dem Abschnitt `vorlage-abweichung` zu. Erfasst werden "▾ 1 Abweichung" / "1 change" im Picker und die Zeile „Auf „{vorlage}“ zurücksetzen“ / „Reset to „{vorlage}““.
2. **Abgleich-Logik:** `SCRIPT_ABSCHNITT` (Z. 391) erhält `vorlage-abweichung`; `datensatzFuerAbschnitt` (Z. 474) liefert für `grenzen-*` und `vorlage-abweichung` den Datensatz `mit_abweichung`, sonst `ohne_abweichung`. Der Datensatz hat laut Payload Overrides, die Karte zeigt live also `abweichungen > 0`. Vor der Umsetzung messen: erscheint die Zurücksetzen-Zeile live beim Datensatz `mit_abweichung`, und wie wird der Plural „Abweichung(en)“ gegen "1 Abweichung" verglichen.
3. **Elementliste und Prüfsumme:** Generator laufen lassen, keine Handpflege. Prüfsumme in `elementliste_uebersicht_2969.test.ts` mit Kommentar „#3251: Abschnitt vorlage-abweichung“ nachziehen. Der Rest der Liste bleibt unverändert (Diff nur neue Einträge des Abschnitts und Mockup-Hash).
4. **Besitzerliste:** Die pauschalen Ausnahmen aus #3205 (`muster` `Auf "{vorlage}" zurücksetzen` und `Reset to "{vorlage}"`, ctx trip, reiter wetter) streichen; Zählwächter in `tests/test_2913_c2_besitzerliste.py` auf den neuen Stand, Besitzer `#3009` bleibt unverändert.
5. **Staging-Abgleich:** `--scope wetter` in DE und EN vor und nach der Änderung; Vorher/Nachher-Diff ablegen. Erwartet: Zurücksetzen-Zeile und „1 Abweichung“ / „1 change“ gefunden, keine neue Abweichung ohne Besitzer, die Ausnahme ist weg.

## Expected Behavior

- **Input:** Mockup Fassung 4 mit abgewählter Metrik, Staging-Prüfkonto-Datensatz `mit_abweichung`.
- **Output:** Elementliste enthält den Abschnitt `vorlage-abweichung` mit den Soll-Einträgen; der Abgleich findet sie live in DE und EN.
- **Side effects:** Wechsel "zusätzlich" oder Ausnahme zu "gefunden" ist erlaubt; neue Abweichung ohne Besitzer nicht. Produktverhalten unverändert.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Elementlisten-Test (node --test): GIVEN die neu erzeugte Elementliste / WHEN der Abschnitt `vorlage-abweichung` gelesen wird / THEN enthält er "▾ 1 Abweichung" und die Zurücksetzen-Zeile, DE und EN über den Katalog (rot vor dem Generatorlauf).
- [ ] Logik-Test Datensatz-Zuordnung: GIVEN `datensatzFuerAbschnitt` / WHEN `vorlage-abweichung` übergeben wird / THEN `mit_abweichung`; `vorlage-auswahl` und `normal` bleiben `ohne_abweichung`; `SCRIPT_ABSCHNITT` erkennt den neuen Namen.
- [ ] `elementliste_uebersicht_2969.test.ts` grün mit begründeter neuer Prüfsumme.
- [ ] `tests/test_2913_c2_besitzerliste.py`: keine herrenlosen Einträge, gestrichene Ausnahmen werden nicht mehr gezählt.
- [ ] Staging-Abgleich `--scope wetter` DE und EN vorher/nachher: Zurücksetzen-Zeile und „1 Abweichung“ gefunden, keine neue Abweichung ohne Besitzer, Ausnahme weg.

## Acceptance Criteria

- **AC-1:** Given das Mockup mit einer abgewählten Metrik im Reiter Wetter / When der Generator die Elementliste neu erzeugt / Then enthält sie einen Abschnitt `vorlage-abweichung` mit "▾ 1 Abweichung" / "1 change" und der Zeile „Auf „{vorlage}“ zurücksetzen“ / „Reset to „{vorlage}““.
  - Test: Elementlisten-Test auf den Abschnitt; Mutation (Abwahl-Klick im Generator entfernt) rötet ihn.

- **AC-2:** Given der Abgleich-Code / When ein Eintrag des Abschnitts `vorlage-abweichung` einem Prüf-Datensatz zugeordnet wird / Then wird der Datensatz `mit_abweichung` verwendet, und alle übrigen Abschnitte außerhalb `grenzen-*` bleiben bei `ohne_abweichung`.
  - Test: Logik-Test der Datensatz-Zuordnung.

- **AC-3:** Given der Staging-Abgleich `--scope wetter` in Deutsch und Englisch / When er nach der Änderung läuft / Then sind die Zurücksetzen-Zeile und „1 Abweichung“ / „1 change“ als gefunden gemeldet, ohne dass eine Ausnahme sie abdeckt.
  - Test: Abgleich DE+EN vorher/nachher als Artefakt.

- **AC-4:** Given die Besitzerliste nach der Änderung / When der Abgleich beide Sprachen prüft / Then sind die pauschalen Ausnahmen aus #3205 für die Zurücksetzen-Zeile gestrichen, und es entsteht keine neue Abweichung ohne Besitzer.
  - Test: Vorher/Nachher-Diff des Abgleichs; `tests/test_2913_c2_besitzerliste.py` grün.

- **AC-5:** Given die Elementliste wurde neu erzeugt / When die Prüfsumme geprüft wird / Then stimmt sie mit der Datei überein und ist im Test mit Begründung nachgezogen, und der Rest der Liste (alle Seiten-Zustände normal, laedt, fehler, luecken) bleibt unverändert.
  - Test: `elementliste_uebersicht_2969.test.ts`; Diff der Elementliste zeigt nur den neuen Abschnitt und den Mockup-Hash.

- **AC-6:** Given Nutzer mit Trips und Orts-Vergleichen / When sie die Anwendung nutzen / Then ändert sich nichts, denn Produktcode, Prüfdaten und Mockup bleiben unverändert und kein dritter globaler Zustand entsteht.
  - Test: Diff enthält keine Datei unter `frontend/src/`, `internal/`, `src/`, `api/` und nicht `scripts/staging_pruefkonto_mockupdaten.py`.

## Definition of Done

- [ ] Spec freigegeben (`approved`/`freigabe`), Tests rot vor Umsetzung, dann grün
- [ ] Elementliste mit dem Generator neu erzeugt, Prüfsumme begründet nachgezogen
- [ ] Staging-Abgleich `--scope wetter` DE und EN vorher/nachher als Artefakt abgelegt, Ergebnis gemäß AC-3 und AC-4
- [ ] Mutationsprobe: Abwahl-Klick im Generator oder Zuordnung auf `ohne_abweichung` verfälscht rötet je einen Test
- [ ] Besitzerliste und Zählwächter angepasst, PR mit allen 6 CI-Checks grün, Deploy, Selftest

## Known Limitations

- Weitere Bedienzustände (zum Beispiel Alarm, Dialog) bleiben ohne eigenen Abschnitt, bis ein Befund sie braucht.
- Der Abschnitt nutzt den bestehenden Prüf-Datensatz `mit_abweichung`; dessen Abweichungszahl muss live "1" ergeben, sonst ist die Zuordnung vor der Umsetzung zu prüfen (siehe Implementation Details Punkt 2).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Prüfwerkzeug-Mechanik nach bestehendem Muster (Script-Abschnitte); Ausführung von ADR-0112 (Mockup-getriebene Scheiben), keine neue Grundsatzentscheidung.

## Changelog

- 2026-11-21: Initial spec created (Option B: Script-Abschnitt vorlage-abweichung, Datensatz mit_abweichung, Ausnahmen aus #3205 streichen)
