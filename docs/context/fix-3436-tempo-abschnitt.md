# Context: fix-3436-tempo-abschnitt (Issue #3436)

## Request Summary
Reiter Etappen (Trip): Tempo-Karte trägt keinen Abschnitt-Haken `data-abschnitt="tempo"`; der
Elementlisten-Abgleich findet ihre Texte nur „seitenweit“ (je Sprache 10 Elemente × 4 Zustände = 40
Abweichungen) plus 2 herrenlose Zusatztexte („Grundtempo (km/h)“, „Gilt für alle Etappen, je Etappe
überschreibbar.“; EN „Base pace (km/h)“, „Applies to all stages, can be overridden per stage.“).
Ziel (AC des Issues): `--strict` DE und EN, Reiter Etappen → Abschnitt `tempo` ohne Abweichung und ohne
herrenlosen Zusatztext.

## Vorher-Messung (Staging, 28.11., `npm run elementliste:abgleich -- --scope etappen/normal`, DE)
- tempo: Fortbewegung, zu Fuß, Rad, MTB, Ski → `abweichend`, Grund „Abschnitt-Haken fehlt / nur seitenweit gefunden“
  (die Texte SIND live sichtbar).
- tempo: „Tempo flach“, „4,0 km/h“ (eingabe, muster `{zahl} km/h`, sprachneutral), „Aufstieg“
  (`trip.etappe.aufstieg`), „300 Hm/h“ (muster `{zahl} Hm/h`, EN-Lücke), „Gilt für alle Etappen, je Etappe
  überschreibbar (z.B. Ruhetag, Bergetappe).“ (EN-Lücke, ohne Katalogschlüssel) → `abweichend`, „Text nicht sichtbar“.
- Alle zehn tragen Besitzer `#2796` (geschlossen) in `docs/context/einstellungen_neu/elementliste_besitzer.json`
  (Eintrag `art: abschnitt`, ctx trip, reiter etappen, abschnitt tempo, ~Zeile 333).
- zusätzlich ohne Besitzer: „Grundtempo (km/h)“, „Gilt für alle Etappen, je Etappe überschreibbar.“
- Nicht im Scope (anderer Abschnitt `liste`): Reihenfolge „Tempo ändern“ vs. Etappennamen E2–E4 (Besitzer
  ebenfalls #2796 geschlossen, AC-16 feat_3007) — gehört zu einem eigenen Issue, als Nebenbefund prüfen.

## Produktentscheidung (bindend)
ADR-0108 Nr. 2, Anpassung 2026-11-20 (Issue #3196, PO-Entscheidung): Tempo = Fortbewegung + **Grundtempo
(km/h)**; Auf-/Abstiegsrate folgt dem Grundtempo und ist **nicht sichtbar**; ersetzt „Tempo flach und Aufstieg“
aus dem Mockup. Je Etappe überschreibbar nur das Grundtempo (#3197); Pausentag hat kein Tempo (kein Knopf) —
deshalb passt der Mockup-Zusatz „(z.B. Ruhetag, Bergetappe)“ fachlich nicht.
⇒ Live ist richtig; Mockup Fassung 4 ist an dieser Stelle durch die Entscheidung überholt.

## Related Files
- `frontend/src/lib/components/edit/EditStagesPanelNew.svelte:1089` — Snippet `tempoKarte` (Wrapper
  `<div class="etappen-tempo">`), gerendert nur mit `kopf` (Hub: `TripTabs.svelte:222` übergibt `kopf` + `listeZuerst`,
  also Pfad `etappenListe` Z. 1098). Hier gehört `data-abschnitt="tempo"` hin (nicht in TempoKarteInhalt, der auch
  im Anlegen und als Etappen-„Tempo ändern“-Karte läuft).
- `frontend/src/lib/components/shared/TempoKarte.svelte`, `organisms/tempo-karte/TempoKarteInhalt.svelte` — Karte.
- `frontend/src/lib/i18n/messages/{de,en}/trip.json:23-24` — `trip.tempo.grundtempo`, `trip.tempo.hinweis`.
- `docs/context/einstellungen_neu/elementliste.json` — generiert aus Mockup (Hash-Wächter
  `elementliste_aktuell.test.ts`), NICHT von Hand ändern.
- `docs/context/einstellungen_neu/elementliste_freigaben.json` — freigegebene Abweichungen (ctx/reiter/abschnitt,
  `i18n_keys` = Katalogschlüssel oder `text:<muster bzw. text_de>`, grund, spec) → Status `freigegeben` (zählt
  nicht in `--strict`).
- `docs/context/einstellungen_neu/elementliste_besitzer.json` — `besitzer` (alt #2796 entfernen) und `ausnahmen`
  (Live-Texte bewusst nicht in der Liste; `text`/`muster`, grund, spec; je Sprache ein Eintrag wie bei „Fertig“/„Finished“).
- `frontend/e2e/elementliste_abgleich_logik.ts` — `wendeFreigabenAn` (1131), `findeZusaetzliche` (1283),
  `exitCode` (139: strict rot bei abweichend+nicht_pruefbar).
- Muster-Tests: `frontend/src/lib/components/organisms/__tests__/wetter_tab_abschnitt_marker*.test.ts` (Haken),
  `tests/test_2913_c2_besitzerliste.py`, `frontend/src/lib/__tests__/elementliste_besitzer_kern.test.ts`.

## Ansatz (Tech Lead)
1. `data-abschnitt="tempo"` am Wrapper der Tempo-Karte im Reiter Etappen.
2. Freigabe trip/etappen/tempo für `text:Tempo flach`, `text:{zahl} km/h`, `trip.etappe.aufstieg`,
   `text:{zahl} Hm/h`, `text:Gilt für alle Etappen, je Etappe überschreibbar (z.B. Ruhetag, Bergetappe).` mit Grund
   ADR-0108-Anpassung und Spec-Stelle.
3. Ausnahmen (DE+EN) für „Grundtempo (km/h)“/„Base pace (km/h)“ und den Hinweis DE/EN.
4. Alten Besitzer-Eintrag #2796 für Abschnitt tempo entfernen.
5. Nachher-Messung `--strict` DE und EN (alle vier Zustände), Scope `etappen`.

## Risks
- „4,0 km/h“: live liest der Abgleich den Eingabewert („4“) — das Element wird nur über die Freigabe gedeckt;
  „4“ und „km/h“ erscheinen in der Vorher-Messung NICHT als zusätzlich.
- EN: Lücken-Elemente (keine EN-Erwartung) — prüfen, dass sie im EN-Lauf nicht `nicht_pruefbar` bleiben.
- Zustände laedt/fehler/luecken: Karte muss dort ebenfalls mit Haken sichtbar sein (Vorher-Messung nur `normal`).

## Analysis

**Type:** Bugfix / Angleichung (Elementlisten-Abgleich), Feature-Umfang null — keine neue Nutzerfunktion.

### Affected Files (Change Type)
| Datei | Change | Begründung |
|---|---|---|
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` (Snippet `tempoKarte`, Z. 1089–1094) | MODIFY | `data-abschnitt="tempo"` am Wrapper `<div class="etappen-tempo">`. Das Snippet wird in allen drei Layouts gerendert (mobil Z. 789, Band Z. 869, Liste Z. 1098) — eine Stelle deckt alle ab. Nicht in `TempoKarteInhalt` (läuft auch im Anlegen und in der Etappen-„Tempo ändern“-Karte → falscher Abschnitt). Der Zurückgesetzt-Hinweis `etappen-tempo-hinweis` liegt außerhalb des Wrappers; Text kommt in der Elementliste nicht vor → bleibt draußen. |
| `docs/context/einstellungen_neu/elementliste_freigaben.json` | MODIFY | Eine Freigabe trip/etappen/tempo für die fünf durch ADR-0108-Anpassung (2026-11-20, #3196) überholten Mockup-Elemente: `text:Tempo flach`, `text:{zahl} km/h`, `trip.etappe.aufstieg`, `text:{zahl} Hm/h`, `text:Gilt für alle Etappen, je Etappe überschreibbar (z.B. Ruhetag, Bergetappe).` |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | MODIFY | (a) Besitzer-Eintrag Abschnitt tempo (#2796, geschlossen, ~Z. 333) auf #3436 umschreiben bzw. entfernen; (b) vier `ausnahmen` (DE+EN) für „Grundtempo (km/h)“/„Base pace (km/h)“ und „Gilt für alle Etappen, je Etappe überschreibbar.“/„Applies to all stages, can be overridden per stage.“ mit Grund ADR-0108-Anpassung. |
| `docs/specs/modules/fix_3436_tempo_abschnitt.md` | CREATE | Spec mit ACs; dient als `spec`-Stelle der Freigaben/Ausnahmen. |
| Test (Kern): Muster `wetter_tab_abschnitt_marker*.test.ts` | CREATE | Render-Test: Tempo-Karte im Reiter Etappen liegt in einem Element mit `data-abschnitt="tempo"`, in allen drei Layouts; Tempo-Karte im Anlegen trägt den Haken NICHT. |
| Test (Kern): Muster `elementliste_besitzer_kern.test.ts` / `test_2913_c2_besitzerliste.py` | CREATE/MODIFY | Freigabe- und Ausnahme-Einträge wirken: `wendeFreigabenAn` setzt die fünf Elemente auf `freigegeben`, `findeZusaetzliche` meldet die beiden Live-Texte nicht mehr (DE+EN); kein Besitzer auf geschlossenem Issue für tempo. |
| `docs/context/einstellungen_neu/elementliste.json` | — | generiert, NICHT anfassen (Hash-Wächter). |

### Scope / Risk
- Scope: 1 Svelte-Zeile, 2 JSON-Dateien (~40 Zeilen), 1 Spec, 1–2 Testdateien. Frontend-only (+ Prüfdaten). Weit unter LoC-Limit.
- Risiko: **niedrig** — reines Markierungsattribut ohne Wirkung auf Darstellung/Verhalten; Freigaben betreffen nur das Prüfwerkzeug.
- Rest-Risiken: (1) Zustände laedt/fehler/luecken — Haken muss dort ebenso greifen; Nachher-Messung über alle vier Zustände, beide Sprachen. (2) EN-Lücken-Elemente (`{zahl} Hm/h`, Hinweis ohne Katalogschlüssel) dürfen im EN-Lauf nicht `nicht_pruefbar` bleiben — Freigabe muss auch dort greifen (`wendeFreigabenAn` vor `nicht_pruefbar`-Einstufung prüfen). (3) „4,0 km/h“ ist ein Eingabefeld; Deckung nur über Freigabe, kein Zusatztext „4“/„km/h“ erwartet.

### Technical Approach
1. RED: Kern-Render-Test für den Haken (rot), Kern-Test für Freigabe/Ausnahmen gegen die echten JSON-Dateien (rot).
2. GREEN: Attribut setzen, Freigabe + Ausnahmen + Besitzer-Korrektur eintragen.
3. Staging-Nachweis: `npm run elementliste:abgleich -- --scope etappen --strict` DE und EN, alle vier Zustände; Abschnitt `tempo` ohne Abweichung, ohne herrenlosen Zusatztext.

### Alternativen (verworfen)
- Mockup Fassung 4 „Tempo flach + Aufstieg“ live nachbauen → widerspricht bindender PO-Entscheidung #3196 (ADR-0108-Anpassung).
- Elementliste von Hand ändern → generiert, Hash-Wächter; Mockup-Änderung wäre Produktarbeit ohne Auftrag. Freigabe mit Spec-Stelle ist der vorgesehene Weg (wie #3202/#3440).

### Dependencies
- ADR-0108 Nr. 2 (Anpassung 2026-11-20), #3196/#3197 (Grundtempo, Pausentag ohne Tempo).
- Abgleich-Logik `frontend/e2e/elementliste_abgleich_logik.ts` (unverändert).
- Nebenbefund außerhalb Scope: Abschnitt `liste`, Reihenfolge „Tempo ändern“ vs. Etappennamen (Besitzer #2796 geschlossen) → eigenes Issue prüfen/anlegen.

### Open Questions
- Keine Produktfrage offen (Entscheidung #3196 ist bindend).

## Stand nach TDD RED (28.11.)
- Spec + RED-Tests gesichert (Commit 4b6a0faa4). RED-Artefakt registriert: 14 von 24 rot (AC-1, AC-3, AC-4, AC-5), AC-2 grün.
- RED-Befunde für GREEN: (1) `wendeFreigabenAn` (`frontend/e2e/elementliste_abgleich_logik.ts` ~Z.1131) muss gedeckte EN-Lücken (`nicht_pruefbar`, Grund „EN-Lücke: kein Katalogtext“) zu `freigegeben` machen — Spec Implementation Details 2a, neu freigegeben. (2) `tests/test_2913_c2_besitzerliste.py::test_ac12_tempo_karte_haengt_an_2796` pinnt #2796 → auf #3436 nachführen.
- Nebenbefund Abschnitt `liste` (16 Besitzer „Tempo ändern“ auf #2796) an #3439 vermerkt.
