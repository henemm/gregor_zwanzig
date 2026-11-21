---
entity_id: feat_3205_vorlagen_mockup
type: feature
created: 2026-11-21
updated: 2026-11-21
status: draft
version: "1.0"
workflow: feat-3205-vorlagen-mockup
tags: [einstellungen-neu, reiter-wetter, elementlisten-abgleich, mockup, vorlagen, "#3205", "#2913"]
---

# Reiter Wetter: Vorlagen nach Art trennen und Zurücksetzen-Zeile klären (Mockup Fassung 4)

## Approval

- [ ] Approved

## Purpose

Die vier Besitzer-Einträge `#3205` (Epic #2913) entstehen aus zwei Abweichungen zwischen App und Mockup Fassung 4: Die App trennt eigene Vorlagen nach Art (Trip gegen Orts-Vergleich, PO-Entscheidung #2794 vom 08.11.2026, AC-24), das Mockup zeigt dagegen eine globale Liste, und die Zurücksetzen-Zeile steht live im Prüfkonto, im Mockup-Normalzustand aber nicht. Die Trennung bleibt (PO-Entscheidung, Tech-Lead-Plan im letzten Kommentar von Issue #3205); das Mockup wird angepasst, der Produktcode bleibt unverändert.

## Source

- **File:** `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` (`VORLAGEN` Z. 358, `EIGENE` Z. 359, Picker Z. 492-493, Zurücksetzen-Zeile Z. 510-511)
- **Identifier:** `EIGENE` und Picker-Rendering im Mockup; Prüfdaten in `scripts/staging_pruefkonto_mockupdaten.py`

> Schicht: Mockup (Soll), generierte Elementliste, Besitzerliste, Prüfdaten-Skript. Kein Go-API-/Python-Core-/Frontend-Produktcode (`wetterTabLaden.ts`, `VorlageKarte.svelte`, `internal/` bleiben unverändert).
> Trip/Orts-Vergleich: Die Art-Trennung ist ein Filter-Parameter im geteilten Code (`eigeneVorlagen` filtert `artVon(p) === kind`), keine zweite Komponente; vereinbar mit ADR-0097 und der Code-Teilung Trip/Vergleich.
> Kanäle: keine Änderung an Briefing- oder Alarm-Inhalt (E-Mail, Telegram, SMS, Premium-SMS unberührt). Keine Nutzerdaten bewegt; Prüfkonto-Daten nur auf Staging.

## Scope

**Im Scope**
- Mockup: eigene Vorlagen je Art führen. Trip zeigt die eigenen Trip-Vorlagen (u. a. „Mallorca Frühling“), Orte zeigt nur Vorlagen der Art Vergleich (Systemvorlagen plus eigene Orts-Vergleich-Vorlagen). „Mallorca Frühling“ erscheint in den Orte-Zuständen nicht mehr. Erlaubt ist, `EIGENE` nach Art zu gliedern; der Picker (Z. 492-493) wählt je Kontext.
- Zurücksetzen-Zeile: Ursache ist ein Zustandsunterschied, kein Code-Unterschied (gleiche Bedingung `abweichungen > 0` in Mockup Z. 511 und `VorlageKarte.svelte`). Zwei zulässige Wege, siehe Implementation Details; gewählt wird der Weg, der in anderen Einträgen keine neuen Abweichungen erzeugt.
- Elementliste per `scripts/elementliste_aus_mockup.ts` neu erzeugen; Prüfsumme in `frontend/e2e/elementliste_uebersicht_2969.test.ts` mit Begründung nachziehen.
- Besitzerliste: vier Einträge `#3205` abräumen; Zählwächter `tests/test_2913_c2_besitzerliste.py` auf `"#3205": 0`.
- Staging-Abgleich Reiter Wetter DE+EN und Soll/Ist-Bild der Orte-Vorlagenauswahl für den PO.

**Nicht im Scope**
- Produktcode jeder Schicht (AC-24 aus #2794 bleibt unverändert gültig).
- #3250 und #3009 (Kontoname „Mallorca Frühling“ ohne EN-Katalogtext bleibt Besitzer #3009; zwei Einträge dort unberührt).
- Vorlagen im Trip-Reiter über die Beispielnamen hinaus; Systemvorlagen-Liste.

## Estimated Scope

- **LoC:** ca. +20/-8 (ohne generierte Elementliste)
- **Files:** 5 bis 6 (Mockup, generierte `elementliste.json`, `elementliste_uebersicht_2969.test.ts`, `elementliste_besitzer.json`, `tests/test_2913_c2_besitzerliste.py`, optional `scripts/staging_pruefkonto_mockupdaten.py`)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` | mockup | Soll des Reiters Wetter, Vorlagen-Picker wird nach Art getrennt |
| `scripts/elementliste_aus_mockup.ts` | script | Erzeugt `elementliste.json` deterministisch aus dem Mockup |
| `scripts/staging_pruefkonto_mockupdaten.py` | script | Prüfdaten des Staging-Prüfkontos (Trip-Zustand für den Zurücksetzen-Weg) |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | data | Besitzer-Einträge `#3205` (4 Stück) |
| `tests/test_2913_c2_besitzerliste.py` | test | Zählwächter je Besitzer (Z. 155-156) |
| `frontend/e2e/elementliste_uebersicht_2969.test.ts` | test | Prüfsumme der Elementliste |
| `frontend/src/lib/components/shared/wetter-tab/wetterTabLaden.ts` | module | Art-Filter, nur gelesen |
| `frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte` | module | Zurücksetzen-Zeile, nur gelesen |
| `docs/specs/modules/feat_2794_s3a_reiter_wetter.md` | spec | P3 und AC-24: Vorlagen je Art |
| `feat_3204_anzeige_metriken_mockup.md` | spec | Vorgänger, gleiche Elementlisten-Mechanik |
| ADR-0097, ADR-0108, ADR-0112 | adr | Code-Teilung, Vorlagen für Trip und Orte, Mockup-Bildprüfung |

## Implementation Details

1. **Mockup, Vorlagen je Art:** `EIGENE` erhält eine Art-Angabe je Eintrag (Trip beziehungsweise Vergleich). Der Picker (Z. 492-493) zeigt im Trip-Kontext Systemvorlagen plus eigene Vorlagen der Art Trip, im Orte-Kontext Systemvorlagen plus eigene Vorlagen der Art Vergleich. Im Mockup gibt es keine eigene Orts-Vergleich-Vorlage; die Orte-Auswahl enthält daher nur die sieben Systemvorlagen. „Mallorca Frühling“ bleibt im Trip.
2. **Zurücksetzen-Zeile, Weg A (Prüfdaten):** `scripts/staging_pruefkonto_mockupdaten.py` bringt den Prüfkonto-Trip in den Mockup-Normalzustand („▾ unverändert“, keine Abweichung zur gewählten Vorlage). Dann fehlt die Zeile live wie im Mockup.
3. **Zurücksetzen-Zeile, Weg B (Zuordnung):** Die Einträge werden dem Abweichungs-Zustand des Mockups zugeordnet (Mockup zeigt die Zeile ab `devs > 0`, Z. 511); die Elementliste erfasst dafür den Zustand „Abweichung“.
4. **Wahl des Wegs (Developer):** Staging-Abgleich Reiter Wetter DE+EN vor der Änderung und nach jedem Weg ablegen. Gewählt wird der Weg ohne neue Abweichungen in anderen Einträgen (zum Beispiel „▾ 1 Abweichung“ im Picker, Abweichungsmarken an Zeilen, Zustandsnamen im Prüfkonto). Erzeugt Weg A solche Folgen, gilt Weg B, und umgekehrt. Die Wahl und das Vorher/Nachher-Ergebnis werden im Abgleich-Artefakt begründet.
5. **Elementliste und Prüfsumme:** Generator laufen lassen, keine Handpflege; Prüfsumme in `elementliste_uebersicht_2969.test.ts` mit Kommentar „#3205: Vorlagen je Art im Mockup“ nachziehen.
6. **Besitzerliste:** vier Einträge `#3205` entfernen (zwei Auswahl-Einträge Orte, zwei Zurücksetzen-Muster DE/EN); Zählwächter auf `"#3205": 0` mit Kommentar wie bei #3204.
7. **Wirkung messen:** Soll/Ist-Bild der Orte-Vorlagenauswahl (Mockup gegen Staging, ADR-0112) für den PO.

## Expected Behavior

- **Input:** Mockup Fassung 4, Staging-Reiter Wetter (Trip und Orte), Prüfkonto-Seed.
- **Output:** Abgleich meldet keinen Eintrag mit Besitzer `#3205`; Orte-Vorlagenauswahl im Mockup und live enthalten „Mallorca Frühling“ nicht; die Zurücksetzen-Zeile erzeugt keinen herrenlosen Eintrag.
- **Side effects:** Wechsel abweichend→gefunden in anderen Besitzern ist erlaubt; neue Abweichung ohne Besitzer nicht. Produktverhalten (Vorlagen je Art, Duplikat- und Standard-Regeln) unverändert.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Elementlisten-Test (node --test): In der Elementliste des Orte-Reiters Wetter, Zustände `luecken` und `normal`, enthält die Vorlagenauswahl „Mallorca Frühling“ nicht; die Trip-Auswahl enthält ihn (rot vor der Änderung).
- [ ] Mockup-Test: Picker im Orte-Kontext liefert nur Vorlagen der Art Vergleich; im Trip-Kontext zusätzlich die eigenen Trip-Vorlagen.
- [ ] Elementlisten-Test zur Zurücksetzen-Zeile: je nach gewähltem Weg Zeile in keinem Zustand ohne Abweichung beziehungsweise im Abweichungs-Zustand erfasst.
- [ ] `elementliste_uebersicht_2969.test.ts` grün mit begründeter neuer Prüfsumme.
- [ ] `tests/test_2913_c2_besitzerliste.py`: `"#3205": 0`, keine herrenlosen Einträge.
- [ ] Staging-Abgleich Reiter Wetter DE+EN vorher/nachher: Diff enthält nur Einträge `#3205` (abweichend→gefunden), keine neue Abweichung ohne Besitzer.

## Acceptance Criteria

- **AC-1:** Given der Orts-Vergleich-Reiter Wetter / When der Nutzer die Vorlagenauswahl öffnet / Then erscheinen dort nur die Vorlagen der Art Vergleich, die eigene Trip-Vorlage „Mallorca Frühling“ steht nicht in der Liste, und das Mockup zeigt dasselbe.
  - Test: Staging-Abgleich Orte DE ohne Eintrag `#3205`; Elementlisten-Test zu den Zuständen `luecken` und `normal`.

- **AC-2:** Given der Trip-Reiter Wetter / When der Nutzer die Vorlagenauswahl öffnet / Then stehen die Systemvorlagen und die eigenen Trip-Vorlagen, darunter „Mallorca Frühling“, zur Auswahl, unverändert zu heute.
  - Test: Elementlisten-Test Trip enthält den Namen; Staging-Abgleich Trip ohne neue Abweichung.

- **AC-3:** Given ein Trip mit einer gewählten Vorlage und Änderungen an einzelnen Metriken / When der Nutzer die Vorlagenkarte ansieht / Then erscheint „Auf „Vorlage“ zurücksetzen“ (englisch „Reset to „Vorlage““) nur bei Abweichungen, und Mockup und Staging stimmen im Zustand überein, sodass kein Besitzer `#3205` übrig bleibt.
  - Test: Abgleich DE+EN vorher/nachher; Entscheidung für Weg A oder B im Abgleich-Artefakt begründet.

- **AC-4:** Given der gewählte Weg für die Zurücksetzen-Zeile / When der Abgleich nach der Änderung läuft / Then entstehen in anderen Einträgen (Picker-Anzeige „unverändert“ gegen „N Abweichung(en)“, Abweichungsmarken) keine neuen Abweichungen.
  - Test: Vorher/Nachher-Diff des Staging-Abgleichs enthält ausschließlich Einträge `#3205`.

- **AC-5:** Given der Staging-Abgleich des Reiters Wetter in Deutsch und Englisch / When er nach der Änderung läuft / Then meldet er keinen Eintrag mit Besitzer `#3205`, keine neue Abweichung ohne Besitzer, und der Zählwächter steht auf 0, während `#3009` unverändert bei 2 bleibt.
  - Test: Abgleich DE+EN vorher/nachher; `tests/test_2913_c2_besitzerliste.py` grün.

- **AC-6:** Given Bestandsnutzer mit eigenen Vorlagen / When sie Trip oder Orts-Vergleich öffnen / Then bleiben Speichern, Duplikat- und Standard-Regeln je Art wie bisher (AC-24 aus #2794), denn nur Mockup, Prüfdaten und Prüflisten ändern sich.
  - Test: bestehende Vorlagen-Tests laufen unverändert grün; kein Diff in `frontend/src/` und `internal/`.

- **AC-7:** Given die Orte-Vorlagenauswahl als Mockup und als Staging-Seite / When der Product Owner das Soll/Ist-Bild ansieht / Then stimmen beide in der Vorlagenliste sichtbar überein, ohne „Mallorca Frühling“.
  - Test: Bildabgleich Mockup gegen Staging (ADR-0112) wird dem PO als Soll/Ist-Bild vorgelegt.

## Definition of Done

- [ ] Spec freigegeben (`approved`/`freigabe`), Tests rot vor Umsetzung, dann grün
- [ ] Abgleich-Bericht Reiter Wetter DE+EN vorher/nachher als Artefakt abgelegt, Wahl Weg A oder B begründet
- [ ] Mutationsprobe: „Mallorca Frühling“ im Orte-Picker des Mockups wieder eingefügt rötet den Elementlisten-Test
- [ ] Prüfsumme begründet nachgezogen, Besitzerliste und Zählwächter angepasst, PR mit allen 6 CI-Checks grün, Deploy, Selftest
- [ ] Soll/Ist-Bild an den PO

## Known Limitations

- Das Mockup führt keine eigene Orts-Vergleich-Vorlage; die Orte-Auswahl zeigt daher nur Systemvorlagen. Eigene Vergleich-Vorlagen sind live möglich und im Abgleich kein Besitzer-Thema.
- #3009 (EN-Katalogtext für den Kontonamen) bleibt offen; Einstufung als Kontoname bleibt dort.
- Eine künftige PO-Entscheidung, eigene Vorlagen in beiden Kontexten zu zeigen, bräuchte ein neues ADR und Produktcode (Filter, Duplikat- und Standard-Regeln je Art).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Ausführung bestehender Entscheidungen (#2794 P3/AC-24 Vorlagen je Art, ADR-0097 Code-Teilung, ADR-0112 Mockup-getriebene Scheiben mit Bildprüfung); es wird nur das Soll angepasst.

## Changelog

- 2026-11-21: Initial spec created (Vorlagen je Art im Mockup, Zurücksetzen-Zeile über Prüfdaten oder Zuordnung, Besitzer #3205 auf 0)
