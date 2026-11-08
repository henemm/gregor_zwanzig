---
entity_id: rework_2837_s2b_anlege_fortschritt
type: feature
created: 2026-11-08
updated: 2026-11-08
status: draft
version: "1.0"
workflow: feature-2837-s2b-fortschritt
tags: [epic-2345, trip-compare-teilung, anlege-rahmen, fortschritt, shared, paritaet, frontend-only, dod-2]
---

# Scheibe S2b: Fortschrittsbalken der Anlege-Seiten als ein Baustein (Issue #2837, Epic #2345)

## Approval

- [ ] Approved

## Purpose

Der Fortschrittsbalken auf `/trips/new` und `/compare/new` ist heute vierfach gebaut: je Editor einmal für den Computer und einmal für das Handy. Das ist ein Nachzug zu S2 (PR #2861), dessen Spec fälschlich annahm, der Fortschritt sei „schon heute gleich“. Die Fresh-Eyes-Prüfung (AC-21 aus S2) hat den Unterschied gefunden: Auf dem Handy tönt der Ortsvergleich den aktiven Schritt hell orange, der Trip nicht. Die Tönung nutzt zudem einen Rückfallwert `#bcd` (Blau), der nie gedacht war.

Diese Spec legt **einen** Baustein `shared/anlege-rahmen/AnlegeFortschritt.svelte` an. Er zeichnet Segmente und Zähler für beide Arten und beide Geräte nach **einer** Regel. Die Zählung selbst (`progressCount` in `shared/anlegeLockEngine.ts`) ist schon geteilt und bleibt unverändert; geteilt wird nur das Markup. ADR-0110 gilt auch hier, es braucht kein neues ADR, nur einen Nachtrag.

**Nicht im Scope:** die Handy-Reiterleiste (ebenfalls doppelt gebaut, aber im Fresh-Eyes-Befund „gleich“; eine Notiz kommt ins Issue #2837), die Zählung, die Lock-Engines, Speichern und Autosave.

## Entscheidungen (Tech-Lead-Entscheid, bindend)

| Nr. | Thema | Vorher | Nachher (beide Arten, beide Geräte) | Warum |
|---|---|---|---|---|
| 1 | **Baustein** | Vier eigene Markups | Ein Baustein `AnlegeFortschritt` mit `variante: 'desktop' \| 'mobil'` | Gleiche Regel an einer Stelle |
| 2 | **Farbregel** | Handy Vergleich: aktiver Schritt hell orange (`--g-accent-soft`, Rückfall `#bcd`); sonst keine Tönung | Erledigt = `--g-accent`, sonst `--g-rule`. **Keine Tönung des aktiven Schritts** | 3 von 4 Balken tönen heute nicht. Den aktiven Schritt zeigt die Reiterleiste direkt darunter (2 px Akzentlinie). `#f3d9c8` gegen `--g-rule` ist kontrastschwach, das Leitprinzip „hoher Kontrast“ spricht gegen ein schwaches Doppelsignal |
| 3 | **Unterschied der Varianten** | – | Nur Breite (Computer 24 px fest, Handy flexibel) und Zählertext (Computer „n von 5 Abschnitten“, Handy „n/5“) | Alles andere ist ein Markup |
| 4 | **Einbau Computer** | Snippet `fortschritt` im Rahmen | Der Rahmen bindet den Baustein selbst ein; Snippet-Slot `fortschritt` entfällt | Weniger Verzweigung, kein Editor baut den Balken mehr selbst |
| 5 | **Einbau Handy** | Handy-Teil liegt beim Trip außerhalb des Rahmens (`tn-desktop` gegenüber `tn-mobile`) | Die Editoren binden `AnlegeFortschritt variante="mobil"` an ihrer Handy-Stelle ein | Ein Baustein, zwei Einsatzorte je Gerät |

## Source

- **Identifier:** `AnlegeFortschritt` (Svelte-Komponente, Props `steps`, `done`, `aktiv?`, `variante`, `testidPrefix`)

- **Neu (Pfade relativ zu `frontend/src/lib/components/`):** `shared/anlege-rahmen/AnlegeFortschritt.svelte`; Unit-Test `shared/anlege-rahmen/__tests__/anlege_fortschritt.test.ts`. Neue Dateien ausschließlich unter `shared/` (Pendant-Gate `.claude/hooks/pendant_gate.py`).
- **Geändert:**
  - `shared/anlege-rahmen/AnlegeRahmen.svelte` (Snippet `fortschritt` Z. 36 und 72 entfällt; neue Props `steps`, `done`, `aktiv?`; Einbau der Desktop-Variante im Kopf).
  - `trip-new/TripNewEditor.svelte` (Desktop-Snippet Z. 571-584 und Handy-Balken Z. 963-971 ersetzen; neue Testid `tn-mobile-progress`).
  - `compare-new/CompareNewEditor.svelte` (Desktop-Snippet Z. 466-477 und Handy-Balken Z. 600-607 ersetzen; Tönung und Rückfallwert `#bcd` entfallen).
  - `shared/anlege-rahmen/__tests__/anlege_rahmen.test.ts` (die Probe auf das `fortschritt`-Snippet Z. 96 und 177 wird zur Zusicherung des eingebauten Bausteins).
  - `frontend/e2e/anlege-rahmen-paritaet.spec.ts` (neue Fälle für den Fortschritt).
  - Doku: `docs/specs/modules/rework_2837_s2_anlege_rahmen.md` (Z. 51 richtigstellen), `docs/adr/0110-hub-kopf-und-anlege-rahmen-ein-baustein.md` (Nachtrag).
- **Nicht anfassen:** `shared/anlegeLockEngine.ts` (`progressCount`), `trip-new/tripNewLogic.ts`, die Handy-Reiterleiste.

> **Schicht-Hinweis:** ausschließlich **Frontend** (SvelteKit). Kein Go-, kein Python-Code, kein Datenmodell, kein neuer Endpunkt.
> **Trip/Ortsvergleich-Teilung:** Kern dieser Spec. Baustein unter `shared/anlege-rahmen/`; es entsteht keine Komponente mit Pendant unter `trip-new/` oder `compare-new/`.
> **Mandantentrennung:** reine Oberfläche, keine Datenbewegung; ein Zwei-Nutzer-Test entfällt.
> **Kanäle:** nicht betroffen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `shared/anlegeLockEngine.ts` (`progressCount`) | module | Gemeinsame Zählung der erledigten Schritte, bleibt unverändert |
| `shared/anlege-rahmen/AnlegeRahmen.svelte` | component | Bindet die Desktop-Variante ein |
| Design-Tokens `--g-accent`, `--g-rule` | css | Farbregel erledigt / offen |
| `lib/i18n` Katalog (`trip.anlegen.nichts_eingerichtet`, `trip.anlegen.abschnitte`) | module | Zählertexte in Deutsch und Englisch (ADR-0104) |
| `compare-new/__tests__/compare_new_lock_engine_wirkstelle.test.ts` | test | Liest den Zähler per Regex aus dem HTML (Testfalle, siehe unten) |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/anlege-rahmen/AnlegeFortschritt.svelte` | CREATE | Ein Baustein für Segmente und Zähler, `variante`, `testidPrefix` |
| `frontend/src/lib/components/shared/anlege-rahmen/AnlegeRahmen.svelte` | MODIFY | Snippet `fortschritt` entfällt, Props `steps`/`done`/`aktiv`, eigener Einbau |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | MODIFY | Desktop- und Handy-Balken durch den Baustein, neue Testid `tn-mobile-progress` |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | MODIFY | Desktop- und Handy-Balken durch den Baustein, Tönung und `#bcd` entfallen |
| `frontend/src/lib/components/shared/anlege-rahmen/__tests__/anlege_fortschritt.test.ts` | CREATE | Unit-Tests des Bausteins |
| `frontend/src/lib/components/shared/anlege-rahmen/__tests__/anlege_rahmen.test.ts` | MODIFY | Snippet-Probe wird Zusicherung des eingebauten Bausteins |
| `frontend/e2e/anlege-rahmen-paritaet.spec.ts` | MODIFY | Fortschritts-Fälle auf Computer und Handy |
| `docs/specs/modules/rework_2837_s2_anlege_rahmen.md` | MODIFY | Z. 51 richtigstellen, Verweis auf diese Spec |
| `docs/adr/0110-hub-kopf-und-anlege-rahmen-ein-baustein.md` | MODIFY | Nachtrag S2b |

## Estimated Scope

- Files: 9 (4 Code, 3 Test, 2 Doku)
- LoC Produktcode: ca. +120/-50, dazu Tests. Unter dem Limit, kein Override nötig.
- Risiko: LOW. Nur Frontend, Zählung unverändert.

## Implementation Details

1. **Baustein** `AnlegeFortschritt.svelte`: Props `steps`, `done`, `aktiv?`, `variante: 'desktop' | 'mobil'`, `testidPrefix`. Ein Markup, keine Verzweigung nach Art. `variante` wählt nur Segmentbreite und Zählertext. Segmentfarbe: erledigt `--g-accent`, sonst `--g-rule`; `aktiv` wird für **keine** Farbe benutzt (höchstens für ein `aria-current`, ohne Optik). Jedes Segment trägt `data-done="true|false"`. Der Zähler ist ein `<span class="mono">` und **letztes Kind** des Testid-Containers. Bei null erledigten Schritten steht `trip.anlegen.nichts_eingerichtet`, sonst `trip.anlegen.abschnitte` (Computer) bzw. „n/5“ (Handy).
2. **Rahmen:** `AnlegeRahmen` nimmt `steps`/`done`/`aktiv` entgegen und rendert die Desktop-Variante im Kopf, über dem Inhalt und vor dem Fuß mit den Standardwerten. Der Snippet-Slot `fortschritt` wird entfernt.
3. **Editoren:** reichen `PROGRESS_STEPS`, das Ergebnis von `progressCount` und `activeTab` durch. An der Handy-Stelle binden sie `AnlegeFortschritt variante="mobil"` mit den Testids `tn-mobile-progress` (Trip) und `cm-mobile-progress` (Vergleich) ein.
4. **Testids** bleiben exakt erhalten: `trip-new-progress`, `trip-new-progress-segment`, `compare-editor-progress`, `compare-editor-progress-segment`, `cm-mobile-progress`. Neu: `tn-mobile-progress`, `data-done` an Segmenten.

### Testfallen (in Phase 2 gefunden)

- `compare_new_lock_engine_wirkstelle.test.ts:107-108` liest den Zähler per Regex aus dem HTML: Testid-Container, dann `<span class="mono">TEXT</span>`, auf dem Handy direkt danach `</span>\s*</div>`. Darum ist der Zähler letztes Kind des Containers.
- `compare_anlege_freischaltung.test.ts:319` zählt 5 Segmente mit `compare-editor-progress-segment`. Handy-Segmente dürfen deshalb **nicht** so heißen (sonst 10); sie tragen das Präfix `cm-mobile-progress-segment` bzw. `tn-mobile-progress-segment`.
- `standardwerte_knopf_geteilt.test.ts:130` verlangt `compare-editor-standardwerte` im HTML nach `compare-editor-progress`. Das bleibt, weil der Fortschritt im Kopf, die Standardwerte im Fuß stehen.
- E2E `helpers.ts:888-929` nutzt `:visible`; `issue-682-compare-editor-mobile.spec.ts:78` erwartet `cm-mobile-progress` sichtbar. Der Computer-Balken darf auf dem Handy nicht sichtbar doppelt auftauchen (bleibt durch `tn-desktop`/`tn-mobile` getrennt).

## Expected Behavior

- **Input:** `steps`, `done`, optional `aktiv`, `variante`, `testidPrefix`.
- **Output:** n Segmente (heute 5), erledigte in Akzentfarbe, übrige in Linienfarbe, dazu Zählertext je Variante.
- **Side effects:** keine.

## Test Plan

Test-Politik: kein Mock-Theater, keine Dateiinhalt-Checks als Verhaltensnachweis (Ausnahme `# doc-compliance-test`). Frontend-Unit-Tests laufen über `node --test`. Jede Zusicherung wird dort geprüft, wo sie wirkt: Farbe und Lage im E2E aus Nutzersicht, Aufbau und Textwahl im Unit-Test des Bausteins.

### Automated Tests (TDD RED)

- [ ] Unit `anlege_fortschritt.test.ts`: GIVEN 5 Schritte und 2 erledigt WHEN der Baustein in beiden Varianten rendert THEN gibt es 5 Segmente, genau 2 mit `data-done="true"`, kein Segment trägt eine Tönung für den aktiven Schritt, der Zähler ist letztes `<span class="mono">` im Container; Zählertexte Computer und Handy in Deutsch und Englisch aus dem Katalog.
- [ ] Unit `anlege_rahmen.test.ts`: GIVEN beide `context` WHEN der Rahmen rendert THEN steht der Fortschritt im Kopf, und es gibt keinen Snippet-Slot `fortschritt` mehr (die Prop ist aus der Signatur entfernt).
- [ ] E2E `anlege-rahmen-paritaet.spec.ts` (Schleife über beide Arten, 1440 und 390 px, de und en): Segmentzahl, `data-done`, Segmentfarben, aktiver Schritt ohne Sonderfarbe, Zählertext, Sichtbarkeit.
- [ ] Bestehende Tests bleiben unverändert grün: `compare_new_lock_engine_wirkstelle`, `compare_anlege_freischaltung`, `standardwerte_knopf_geteilt`, `issue-682-compare-editor-mobile`.
- [ ] Mutationen (Pflicht, per String-Ersetzung mit externer Sicherung): Tönung des aktiven Schritts wieder eingebaut ⇒ rot; Farbregel erledigt/offen vertauscht ⇒ rot; Handy-Zähler zeigt Computer-Text ⇒ rot; `data-done` am Segment entfernt ⇒ rot; Handy-Segment heißt wieder `compare-editor-progress-segment` ⇒ rot; Trip-Handy ohne `tn-mobile-progress` ⇒ rot.

## Acceptance Criteria

- **AC-1:** Given der Nutzer öffnet `/trips/new` und `/compare/new` auf dem Computer (1440 px) / When die Seite geladen ist / Then zeigt der Kopf bei beiden Arten genau 5 Segmente, die ersten erledigten in Akzentfarbe (`--g-accent`), die übrigen in Linienfarbe (`--g-rule`), und beide sehen bis auf die Texte der Art gleich aus.
  - Test: E2E-Schleife über beide Arten bei 1440 px: Segmentzahl, berechnete Hintergrundfarbe je Segment, `data-done` passt zur Farbe.
- **AC-2:** Given der Nutzer öffnet beide Assistenten auf dem Handy (390 px) / When er den Fortschritt oben betrachtet / Then sieht er bei Trip und Ortsvergleich denselben Balken mit 5 Segmenten nach derselben Farbregel, und beide haben eine eigene Testid (`tn-mobile-progress` bzw. `cm-mobile-progress`), die sichtbar ist.
  - Test: E2E-Schleife bei 390 px: Testid sichtbar, 5 Segmente, Farben wie auf dem Computer.
- **AC-3:** Given der Nutzer ist im Ortsvergleich-Assistenten auf dem Handy in einem Schritt, der noch nicht erledigt ist / When er den Balken betrachtet / Then ist der aktive Schritt nicht hell orange oder anders getönt, sondern wie jeder offene Schritt in Linienfarbe, und es steht kein Blau (`#bcd`) mehr im Balken.
  - Test: E2E bei 390 px: berechnete Farbe des aktiven, noch nicht erledigten Segments gleich `--g-rule`; Unit: keine Farbangabe für den aktiven Schritt im gerenderten Baustein.
- **AC-4:** Given Trip und Ortsvergleich im selben Zustand (gleiche Zahl erledigter Schritte, gleicher aktiver Reiter) / When der Nutzer beide auf dem Computer und auf dem Handy vergleicht / Then sind Segmentzahl, `data-done`-Folge und Segmentfarben je Gerät bei beiden Arten identisch.
  - Test: E2E-Schleife (Art x Breite): Folge von `data-done` und Farben pro Segment wird zwischen Trip und Vergleich gegeneinander verglichen (Parität).
- **AC-5:** Given der Nutzer erledigt einen weiteren Schritt / When der Schritt freigeschaltet ist / Then wird genau ein weiteres Segment auf Computer und Handy erledigt (`data-done="true"`, Akzentfarbe), und der Zähler wächst um eins.
  - Test: E2E: Schritt erfüllen, Segment- und Zählerwert vorher gegen nachher, bei beiden Arten und beiden Breiten.
- **AC-6:** Given die Oberfläche steht auf Deutsch / When der Nutzer den Zähler liest / Then steht auf dem Computer „n von 5 Abschnitten“ (bei null erledigten der Katalogtext „nichts eingerichtet“) und auf dem Handy „n/5“, und beide Texte stammen aus dem i18n-Katalog.
  - Test: Unit `anlege_fortschritt.test.ts` für beide Varianten mit 0 und mehr erledigten Schritten; E2E bei 1440 und 390 px in Deutsch.
- **AC-7:** Given die Oberfläche steht auf Englisch / When der Nutzer den Zähler liest / Then erscheinen beide Zählertexte (Computer und Handy) in der englischen Fassung aus dem Katalog, ohne deutsche Reste und ohne hart kodierten Text.
  - Test: Unit mit englischem Katalog; E2E-Schleife in Englisch bei beiden Breiten; `keine_hartkodierten_nutzertexte.test.ts` bleibt grün.
- **AC-8:** Given bestehende Tests und Automatisierungen / When der Umbau fertig ist / Then sind die Testids `trip-new-progress`, `trip-new-progress-segment`, `compare-editor-progress`, `compare-editor-progress-segment` und `cm-mobile-progress` unverändert vorhanden, neu sind `tn-mobile-progress` und `data-done` an den Segmenten, und `compare-editor-progress-segment` kommt genau 5-mal vor (nicht 10).
  - Test: Unit `compare_anlege_freischaltung` (5 Segmente) und `compare_new_lock_engine_wirkstelle` (Zähler per Regex) unverändert grün; E2E zählt jede Testid.
- **AC-9:** Given der Baustein im HTML / When der Zähler ausgelesen wird / Then ist er ein `<span class="mono">` und letztes Kind des Testid-Containers, damit die bestehende Auslese in `compare_new_lock_engine_wirkstelle.test.ts` ohne Änderung weiter greift.
  - Test: Unit `anlege_fortschritt.test.ts` prüft die Reihenfolge im gerenderten HTML; `compare_new_lock_engine_wirkstelle.test.ts` läuft unverändert grün.
- **AC-10:** Given der Rahmen im Quelltext / When beide Editoren gerendert werden / Then besitzt `AnlegeRahmen` keinen Snippet-Slot `fortschritt` mehr und bindet den Fortschritt selbst ein, und es gibt in `trip-new/` und `compare-new/` kein eigenes Balken-Markup mehr (kein Pendant, Pendant-Gate löst nicht aus).
  - Test: Unit `anlege_rahmen.test.ts` rendert beide `context` ohne Snippet und findet den Balken im Kopf; Pendant-Gate `.claude/hooks/pendant_gate.py` löst nicht aus (als Strukturwächter, nicht als alleiniger Nachweis).
- **AC-11:** Given der Vergleichs-Assistent auf dem Computer / When der Nutzer die Seite von oben nach unten liest / Then steht der Fortschritt im Kopf und „Mit Standardwerten speichern“ im Fuß, also weiterhin in dieser Reihenfolge, und das Handy zeigt den Balken nicht doppelt.
  - Test: Unit `standardwerte_knopf_geteilt.test.ts` unverändert grün; E2E: auf dem Handy ist nur der Handy-Balken sichtbar, auf dem Computer nur der Computer-Balken (`:visible`).
- **AC-12:** Given die Doku nach der Lieferung / When sie geprüft wird / Then ist die falsche Annahme in der S2-Spec („Fortschrittsanzeige schon heute gleich“, Z. 51) richtiggestellt mit Verweis auf diese Spec, und ADR-0110 enthält einen Nachtrag, dass der Fortschritt zum Baustein des Anlege-Rahmens gehört (kein neues ADR).
  - Test: Doku-Prüfung in /60 (`# doc-compliance-test`); `tests/test_adr_index_drift.py` grün.
- **AC-13:** Given die Umsetzung / When die Testsuite läuft / Then sind die neuen Tests (`anlege_fortschritt.test.ts`, erweiterter `anlege_rahmen.test.ts`, `anlege-rahmen-paritaet.spec.ts`) grün, keine Zusicherung eines bestehenden Tests ist gelockert, und die Pflicht-Mutationen werden von mindestens einem Test gefangen.
  - Test: `node --test` auf den benannten Unit-Dateien, Playwright auf der benannten E2E-Datei; Adversary-Verdict VERIFIED mit Mutationsprotokoll.

## Definition of Done

- AC-1 bis AC-13 sind erfüllt, jedes AC hat einen grünen Test; keine Zusicherung gelockert.
- Pull Request mit allen 6 CI-Checks grün gemergt, `/e2e-verify` gegen Staging bestanden, Prod-Deploy mit Selftest-Exit 0.
- Notiz zur doppelt gebauten Handy-Reiterleiste steht als Kommentar im Issue #2837.

## Known Limitations

- Die Handy-Reiterleiste ist weiterhin je Editor eigens gebaut (außerhalb dieser Scheibe, Notiz im Issue).
- Der aktive Schritt wird im Balken bewusst nicht hervorgehoben; er zeigt sich allein in der Reiterleiste.

## Risiken

1. **Regex-Auslese des Zählers** in `compare_new_lock_engine_wirkstelle.test.ts`: Der Test wird rot, wenn der Zähler nicht letztes Kind bleibt, obwohl die Funktion stimmt (AC-9).
2. **Segment-Testid auf dem Handy:** Heißt sie wie die Computer-Testid, zählt `compare_anlege_freischaltung` doppelt (AC-8).
3. **Zwei Einsatzorte je Gerät:** Der Handy-Teil liegt beim Trip außerhalb des Rahmens; beide Einsatzorte müssen denselben Baustein nutzen (AC-4).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0110 `hub-kopf-und-anlege-rahmen-ein-baustein` gilt auch für S2b; kein neues ADR, nur ein Nachtrag.
- **Rationale:** Der Fortschritt ist Teil des Anlege-Rahmens und folgt dem Muster „ein Baustein, `context` wählt nur Texte und Testid-Präfix“ (wie `StatusSchild` und `AnlegeRahmen`).

## Changelog

- 2026-11-08: Initial spec created (Issue #2837, Epic #2345, Scheibe S2b Fortschrittsbalken)
