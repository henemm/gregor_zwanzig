---
entity_id: fix_3436_tempo_abschnitt
type: bugfix
created: 2026-11-28
updated: 2026-11-28
status: draft
version: "1.0"
workflow: fix-3436-tempo-abschnitt
tags: [elementliste, abgleich, etappen, tempo, "#3436", "#3196", "#3197", "#2796"]
---

# Reiter Etappen: Abschnitt-Haken für die Tempo-Karte und Freigaben im Elementlisten-Abgleich

## Approval

- [ ] Approved

## Purpose

Die Tempo-Karte im Reiter Etappen (Trip) bekommt den Abschnitt-Haken `data-abschnitt="tempo"`, damit der Elementlisten-Abgleich ihre Texte dem Abschnitt `tempo` zuordnet statt sie nur seitenweit zu finden. Die fünf Mockup-Elemente, die durch die PO-Entscheidung zum Grundtempo (ADR-0108, Anpassung 2026-11-20, #3196/#3197) bewusst anders gebaut sind, werden als freigegebene Abweichung eingetragen; die beiden Live-Texte (Grundtempo, Hinweis) als Ausnahmen. Für Nutzer ändert sich nichts Sichtbares.

## Source

- **File:** `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` (Snippet `tempoKarte`), `docs/context/einstellungen_neu/elementliste_freigaben.json`, `docs/context/einstellungen_neu/elementliste_besitzer.json`
- **Identifier:** `tempoKarte` (Wrapper `<div class="etappen-tempo">`), Freigabe trip/etappen/tempo, Besitzer-Eintrag Abschnitt `tempo`

> **Schicht:** Frontend (`frontend/src/...`) plus Prüfdaten unter `docs/context/einstellungen_neu/`. Kein Go-, kein Python-Code, keine Nutzerdaten, kein Briefing- oder Alarm-Inhalt (Kanäle und Mandantentrennung nicht berührt). Trip/Orte-Teilung: die Tempo-Karte im Reiter Etappen gibt es nur beim Trip, ein Compare-Pendant existiert nicht.

## Scope

**Im Scope:**
- Abschnitt-Haken `data-abschnitt="tempo"` am Wrapper der Tempo-Karte im Reiter Etappen (alle drei Layouts)
- Freigabe der fünf durch ADR-0108-Anpassung überholten Mockup-Elemente in `elementliste_freigaben.json`
- Vier Ausnahmen (DE+EN) für die Live-Texte Grundtempo und Hinweis in `elementliste_besitzer.json`
- Besitzer-Eintrag trip/etappen/tempo von #2796 auf #3436 (samt Nachführung von `test_ac12_tempo_karte_haengt_an_2796`)
- `wendeFreigabenAn`: gedeckte EN-Lücken werden `freigegeben` (Implementation Details 2a)
- Kern-Tests für AC-1 bis AC-5

**Außerhalb des Scopes:**
- Abschnitt `liste` (Reihenfolge „Tempo ändern“ gegen Etappennamen) — eigenes Issue
- Nachbau „Tempo flach + Aufstieg“ aus dem Mockup (widerspricht #3196)
- Handänderung an der generierten `elementliste.json`, Gate-Konfiguration

## Estimated Scope

- **LoC:** ca. 70 (1 Svelte-Zeile, ca. 5 Zeilen Abgleich-Logik, ca. 40 Zeilen JSON, Rest Tests ohne Zählung im Limit)
- **Files:** 4 produktiv/Prüfdaten (1 Svelte, 2 JSON, 1 Spec) plus 2 Testdateien
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| ADR-0108 Nr. 2 (Anpassung 2026-11-20) | ADR | Bindende Produktentscheidung: Grundtempo statt „Tempo flach + Aufstieg“, Pausentag ohne Tempo |
| #3196, #3197 | Issues | PO-Entscheidung Grundtempo, Überschreibung je Etappe nur beim Grundtempo |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | component | Reicht `kopf` und `listeZuerst` an `EditStagesPanelNew`, Pfad `etappenListe` |
| `frontend/src/lib/components/organisms/tempo-karte/TempoKarteInhalt.svelte` | component | Läuft auch im Anlegen und in der Etappen-„Tempo ändern“-Karte; bleibt ohne Haken |
| `frontend/e2e/elementliste_abgleich_logik.ts` | module | `wendeFreigabenAn` (MODIFY, siehe Implementation Details 2a), `findeZusaetzliche`, `exitCode` (unverändert) |
| `tests/test_2913_c2_besitzerliste.py` | test | `test_ac12_tempo_karte_haengt_an_2796` pinnt den alten Besitzer #2796; wird auf #3436 nachgeführt |
| `elementliste.json` | generierte Datei | Wird NICHT angefasst (Hash-Wächter `elementliste_aktuell.test.ts`) |
| `docs/specs/modules/feat_3440_test_schicken_menue.md` | spec | Vorbild für Freigaben mit Spec-Verweis |

## Implementation Details

1. **Haken.** Im Snippet `tempoKarte` von `EditStagesPanelNew.svelte` erhält der Wrapper `<div class="etappen-tempo">` das Attribut `data-abschnitt="tempo"`. Das Snippet wird in allen drei Layouts (mobil, Band, Liste) gerendert, eine Stelle genügt. Nicht in `TempoKarteInhalt`, damit die Tempo-Karte im Anlegen und die Etappen-„Tempo ändern“-Karte keinen Haken tragen. Der Zurückgesetzt-Hinweis `etappen-tempo-hinweis` liegt außerhalb des Wrappers und bleibt draußen.
2. **Freigabe** in `elementliste_freigaben.json` (Schema `ctx, reiter, abschnitt, i18n_keys, grund, spec`): ctx trip, reiter etappen, abschnitt tempo, `i18n_keys` = `text:Tempo flach`, `text:{zahl} km/h`, `trip.etappe.aufstieg`, `text:{zahl} Hm/h`, `text:Gilt für alle Etappen, je Etappe überschreibbar (z.B. Ruhetag, Bergetappe).`; Grund: ADR-0108 Nr. 2 Anpassung 2026-11-20, PO-Entscheidung #3196/#3197 (Grundtempo statt Tempo flach + Aufstieg, Pausentag ohne Tempo); `spec` = diese Datei. Die Freigabe muss auch im EN-Lauf greifen (EN-Lücken-Elemente dürfen nicht `nicht_pruefbar` bleiben).
2a. **Abgleich-Logik (RED-Befund 28.11.).** `wendeFreigabenAn` wandelt heute nur `abweichend` um; EN-Lücken-Elemente kommen als `nicht_pruefbar` („EN-Lücke: kein Katalogtext“) an und bleiben stehen. Änderung: Ein Element mit Status `nicht_pruefbar` und genau diesem EN-Lücken-Grund wird ebenfalls `freigegeben`, wenn eine Freigabe es deckt — eine Freigabe sagt, dass das Mockup-Element bewusst nicht gebaut ist, in jeder Sprache. Andere `nicht_pruefbar`-Gründe (z. B. fehlender Abschnitt-Haken, Script-Abschnitt) bleiben unverändert.
3. **Ausnahmen** in `elementliste_besitzer.json` (je Sprache ein Eintrag, Muster „Fertig“/„Finished“): `Grundtempo (km/h)`, `Base pace (km/h)`, `Gilt für alle Etappen, je Etappe überschreibbar.`, `Applies to all stages, can be overridden per stage.`; ctx trip, reiter etappen, Grund wie oben, `spec` = diese Datei.
4. **Besitzer.** Der Eintrag Abschnitt `tempo` (ctx trip, reiter etappen, Verweis #2796, geschlossen) wird auf #3436 umgestellt; kein Besitzer auf einem geschlossenen Issue.
5. **Tests (Kern, ohne Mock-Theater, `node --test`):** Render-Test nach Muster `frontend/src/lib/components/organisms/__tests__/wetter_tab_abschnitt_marker*.test.ts` (Haken in drei Layouts, kein Haken in Anlegen und Etappen-„Tempo ändern“); Kern-Test gegen die echten JSON-Dateien mit der echten Logik aus `elementliste_abgleich_logik.ts` (`wendeFreigabenAn`, `findeZusaetzliche`), Muster `frontend/src/lib/__tests__/elementliste_besitzer_kern.test.ts`.

**Nicht im Umfang:** Abschnitt `liste` (Reihenfolge „Tempo ändern“ gegen Etappennamen, Besitzer #2796) wird als Nebenbefund in einem eigenen Issue geführt. Keine Änderung der Gate-Konfiguration, keine Schritte mit menschlichem Override.

## Expected Behavior

- **Input:** Abgleich `npm run elementliste:abgleich -- --scope etappen --strict` gegen Staging, DE und EN, Zustände normal, laedt, fehler, luecken.
- **Output:** Abschnitt `tempo` ohne Abweichung und ohne herrenlosen Zusatztext; die fünf Mockup-Elemente stehen als „freigegeben“.
- **Side effects:** Keine sichtbare Änderung für Nutzer; das Attribut hat keine Wirkung auf Darstellung oder Verhalten.

## Acceptance Criteria

- **AC-1:** Given der Reiter Etappen eines Trips im Layout Liste, Band oder mobil / When die Seite gerendert wird / Then liegt die Tempo-Karte in einem Element mit `data-abschnitt="tempo"`, in allen drei Layouts.
  - Test: Kern-Render-Test (`node --test`, Muster `wetter_tab_abschnitt_marker*.test.ts`) rendert `EditStagesPanelNew` je Layout und findet die Karte unter dem Haken.

- **AC-2:** Given die Tempo-Karte beim Anlegen eines Trips und die Etappen-„Tempo ändern“-Karte / When beide gerendert werden / Then tragen sie kein `data-abschnitt="tempo"`, damit der Abschnitt nur im Reiter Etappen gilt.
  - Test: Kern-Render-Test prüft, dass weder die Anlegen-Karte noch die „Tempo ändern“-Karte ein Element mit diesem Haken enthält.

- **AC-3:** Given die echte Freigabendatei und die echte Abgleich-Logik / When `wendeFreigabenAn` für trip/etappen/tempo in DE und EN läuft / Then stehen „Tempo flach“, „{zahl} km/h“, „Aufstieg“, „{zahl} Hm/h“ und der Mockup-Hinweis „(z.B. Ruhetag, Bergetappe)“ auf „freigegeben“, auch die EN-Lücken-Elemente und nicht auf „nicht_pruefbar“.
  - Test: Kern-Test mit `node --test` lädt `elementliste_freigaben.json` und `elementliste.json` und ruft `wendeFreigabenAn` je Sprache auf.

- **AC-4:** Given die echte Ausnahmenliste und die gemessenen Live-Texte des Abschnitts tempo / When `findeZusaetzliche` in DE und EN läuft / Then meldet es weder „Grundtempo (km/h)“ noch „Gilt für alle Etappen, je Etappe überschreibbar.“ noch die englischen Entsprechungen „Base pace (km/h)“ und „Applies to all stages, can be overridden per stage.“ als herrenlosen Zusatztext.
  - Test: Kern-Test mit `node --test` gegen `elementliste_besitzer.json` und die echte `findeZusaetzliche`, je Sprache ein Durchlauf.

- **AC-5:** Given die Besitzerliste / When der Besitzer-Eintrag für trip/etappen/tempo gelesen wird / Then verweist er auf das offene Issue #3436 und nicht mehr auf das geschlossene #2796, und kein Eintrag für diesen Abschnitt zeigt auf ein geschlossenes Issue.
  - Test: Kern-Test liest `elementliste_besitzer.json`, sucht den Eintrag und prüft den Verweis; Muster `frontend/src/lib/__tests__/elementliste_besitzer_kern.test.ts`.

- **AC-6:** Given das Prüfkonto auf Staging mit dem Trip im Reiter Etappen / When der Abgleich mit `--scope etappen --strict` in DE und EN in allen vier Zuständen (normal, laedt, fehler, luecken) läuft / Then zeigt der Abschnitt `tempo` keine Abweichung und keinen herrenlosen Zusatztext, und für `tempo` entsteht kein Strict-Fehler.
  - Test: Playwright-Abgleich gegen `https://staging.gregor20.henemm.com` mit Ausgabe je Sprache und Zustand (Nachweis im Issue #3436).

## Test Plan

| AC | Testart | Datei (geplant) | Nachweis |
|---|---|---|---|
| AC-1, AC-2 | Kern-Render-Test (`node --test`) | `frontend/src/lib/components/organisms/__tests__/etappen_tempo_abschnitt_marker.test.ts` | Haken in Liste/Band/mobil vorhanden; Anlegen-Karte und „Tempo ändern“-Karte ohne Haken |
| AC-3, AC-4, AC-5 | Kern-Test gegen echte JSON-Dateien und echte Abgleich-Logik (`node --test`) | `frontend/src/lib/__tests__/elementliste_tempo_3436_kern.test.ts` | fünf Elemente `freigegeben` DE+EN; keine herrenlosen Zusatztexte DE+EN; Besitzer #3436 |
| AC-6 | Staging-Abgleich `--scope etappen --strict` DE+EN, vier Zustände | – (Messlauf) | Ausgabe je Sprache/Zustand als Kommentar in #3436 |

Gegenproben (Mutation, Phase 5/6): Haken entfernen ⇒ AC-1 rot; Haken in `TempoKarteInhalt` verschieben ⇒ AC-2 rot; einen Freigabe-Schlüssel entfernen ⇒ AC-3 rot; eine EN-Ausnahme entfernen ⇒ AC-4 rot; Besitzer zurück auf #2796 ⇒ AC-5 rot.

## Definition of Done

- AC-1 bis AC-5 durch Kern-Tests belegt, Kern-Schicht grün
- AC-6 durch Staging-Abgleich `--strict` DE und EN belegt, Ergebnis im Issue #3436 dokumentiert
- Nebenbefund Abschnitt `liste` als eigenes Issue eingeordnet
- Adversary-Verdict VERIFIED, alle 6 CI-Checks grün, ausgeliefert und Prod-Selftest grün

## Known Limitations

- „4,0 km/h“ ist ein Eingabefeld; der Abgleich liest den Eingabewert, deshalb deckt nur die Freigabe `{zahl} km/h` das Element.
- Die Reihenfolge „Tempo ändern“ gegen die Etappennamen im Abschnitt `liste` bleibt außerhalb dieses Fixes.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; gestützt auf ADR-0108 Nr. 2 (Anpassung 2026-11-20)
- **Rationale:** Die Produktentscheidung (Grundtempo statt Tempo flach + Aufstieg) liegt vor; hier wird nur das Prüfwerkzeug angeglichen. Das Mockup wird nicht nachgebaut, die generierte Elementliste nicht von Hand geändert.

## Changelog

- 2026-11-28: Initial spec created (Issue #3436)
- 2026-11-28: Scope, Test Plan, Definition of Done ergänzt (CI-Spec-Gate)
- 2026-11-28: RED-Befund eingearbeitet: `wendeFreigabenAn` deckt EN-Lücken (2a), Python-Besitzertest nachführen
