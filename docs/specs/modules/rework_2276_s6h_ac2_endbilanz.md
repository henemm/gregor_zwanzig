---
entity_id: rework_2276_s6h_ac2_endbilanz
type: refactor
created: 2026-09-25
updated: 2026-09-25
status: implemented
version: "1.0"
tags: [compare, ratsche, ac2, endbilanz, epic-2276]
---

# AC-2-Endbilanz der HERKUNFT-Ratsche (Issue #2276, Scheibe S6h, Epic #2345) — Mini-Spec (Fast Track)

## Approval

- [ ] Approved

## Was ändert sich

Reine Dokumentation, **kein Produktivcode**. S6a–S6g haben die HERKUNFT-Ratsche
(`shared/__tests__/context_herkunft_zweige_eingefroren.test.ts`) von 69 auf 47
Fundstellen gesenkt. Die freigegebene AC-2-Neufassung (S6a-Spec) verlangt eine
Liste, die **jede verbleibende Verzweigung** einzeln als FACHLICH, DARSTELLEND
oder — mit Begründung, warum sie trotzdem bleibt — als HERKUNFT ausweist.
S6f/S6g haben diese Bilanz bewusst nicht gezogen und benannten explizit „14
verbleibende HERKUNFT-Einträge" als Rest für S6h.

Diese Scheibe:

1. **Kategorisiert alle 47 aktuellen Ratschen-Einträge** einzeln (Tabelle
   unten) — sortiert nach FACHLICH (27) / DARSTELLUNG (6) / HERKUNFT (14).
2. **Löst den Konflikt AC-2 ↔ S4 AC-13** für `weatherMetricsCompareSave.ts:534`
   auf: dieselbe Zeile ist gleichzeitig eine HERKUNFT-Verzweigung (liest
   `context`) UND die von S4 freigegebene „zweite Barriere" gegen verfrühte
   PUTs vor abgeschlossener Hydration. Sie bleibt bestehen — die AC-13-Pflicht
   hat Vorrang.
3. **Formuliert eine explizite AC-2-Abweichung** (PO-Freigabe über diese
   Mini-Spec) für die 14 HERKUNFT-Einträge: sie werden **nicht** entfernt.
   Grund: alle 14 sitzen an der Grenze zwischen zwei strukturell
   verschiedenen Persistenz-Zielen (Trip-Entität vs. Compare-Preset,
   unterschiedlicher Endpoint, unterschiedliches Payload-Shape, Hub-weite
   Schreib-Serialisierung `enqueueHubWrite`) — ihre Auflösung bräuchte eine
   neue Abstraktion (z. B. eine injizierte `SaveFn` pro Organismus statt eines
   `context`-Schalters), die eine eigene Architekturentscheidung ist, kein
   Fortsetzen des bestehenden Wertprop-Musters. Tech-Lead-Empfehlung:
   **jetzt akzeptieren, nicht bauen** — der Aufwand steht in keinem Verhältnis
   zum Nutzen (keine Bugs, keine Nutzerwirkung, reine interne Konsistenz).
   Eine `ADR`-gestützte Vereinheitlichung („eine Barriere je Speicherweg,
   gebunden an Wertprop-Präsenz statt `context`") bleibt als Option in einem
   **eigenen, künftigen Ticket** offen, falls ein weiterer geteilter Organismus
   dazukommt und die Doppelung erneut schmerzt.
4. **Bestätigt AC-4** unverändert erfüllt: `compareHubWizardBridge.ts` existiert
   nicht mehr, bewacht seit S6f durch
   `compare/__tests__/compare_hub_bridge_restlos_entfernt.test.ts` (grün,
   unverändert).
5. **Schließt Issue #2276**, sobald diese Spec freigegeben und die Endbilanz
   dokumentiert im Issue steht.

## Was darf sich nicht ändern

- Kein Produktivcode in `frontend/src/`.
- `EINGEFROREN_SOLL_ANZAHL` in `context_herkunft_zweige_eingefroren.test.ts`
  bleibt **47** — diese Scheibe streicht und verschiebt keinen Eintrag.
- Die HERKUNFT-Ratsche selbst wird nicht editiert.
- Keine neue Architekturentscheidung (kein ADR) — die Vereinheitlichungsoption
  wird nur benannt, nicht umgesetzt.

## Acceptance Criteria

- **AC-1:** Given die 47 eingefrorenen Ratschen-Einträge aus
  `context_herkunft_zweige_eingefroren.test.ts`, When man sie einzeln gegen
  den aktuellen Quelltext liest, Then trägt jeder Eintrag genau eine Kategorie
  (FACHLICH/DARSTELLUNG/HERKUNFT) mit stichhaltigem Grund, und die Summe der
  drei Kategorien ergibt exakt 47.
- **AC-2:** Given die 14 als HERKUNFT verbleibenden Einträge, When die
  Mini-Spec freigegeben wird, Then gilt das als PO-Freigabe der AC-2-
  Abweichung (sie bleiben bestehen) — dokumentiert mit Begründung je
  Eintrags-Gruppe, nicht nur als Sammelverweis.
- **AC-3:** Given `weatherMetricsCompareSave.ts:534`, When der Konflikt
  AC-2 (HERKUNFT) gegen S4 AC-13 (Pflicht-Barriere) geprüft wird, Then
  gewinnt AC-13, und die Zeile bleibt mit exakt diesem Vorrang dokumentiert.
- **AC-4:** Given `compare_hub_bridge_restlos_entfernt.test.ts`, When der
  Kern-Testlauf ausgeführt wird, Then bleibt er unverändert grün — kein neuer
  Test nötig, AC-4 aus #2276 gilt als erfüllt.

## Manuelle Test-Schritte

1. `cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts` → unverändert grün, 47 Einträge.
2. `cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test src/lib/components/compare/__tests__/compare_hub_bridge_restlos_entfernt.test.ts` → unverändert grün (AC-4).
3. `cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test src/lib/components/shared/__tests__/ac2_endbilanz_deckt_alle_47_ab.test.ts` → neuer Doc-Compliance-Test grün (siehe Inline-Test).
4. Volle Frontend-Suite unverändert grün (keine Regression, da kein Produktivcode angefasst wird).

## Inline-Test (wird während Implementierung geschrieben)

- [ ] `ac2_endbilanz_deckt_alle_47_ab.test.ts` (`# doc-compliance-test`,
  Ausnahme zum Verbot reiner Dateiinhalts-Checks): parst die Tabelle unten aus
  dieser Spec-Datei, vergleicht die 47 `Datei:Zeile`-Einträge **mengengleich**
  gegen `EINGEFROREN` aus der Ratsche (Import der Konstante, kein zweiter
  Zählbefehl) und prüft, dass die drei Kategorie-Summen 27/6/14 ergeben.
  Verhindert, dass diese Dokumentation und die Ratsche künftig auseinanderlaufen.

## Anhang: AC-2-Endbilanz — alle 7 Ratschen-Einträge (seit #3458 ohne `AlarmeTab.svelte:608` (Beispielwarnung entfernt), AlarmeTab-Zeilen um 2 nachgerückt; seit #3389 ohne `versandVergleichSpeicherung.ts:236` und `weather-metrics-tab/weatherMetricsCompareSave.ts:364`; seit #3385 ohne `versand-tab/vtBriefingChannelsText.ts:22/:29` und `versand-tab/VTSchedulePlan.svelte:72` (Waisen gelöscht); seit #3297/#3020 ohne die elf Einträge von `VersandTab.svelte`, `WeatherMetricsTab.svelte`, `weatherMetricsTabSections.ts` und `WetterMetrikenVersandPanel.svelte` (Dateien gelöscht); Stand `3cece096`, S6g live; seit #2287 ohne `alarmeTabSections.ts:42`; seit #1743 mit `WetterMetrikenVersandPanel.svelte:66`; seit #1721 mit `WeatherMetricsTab.svelte:2042`; AlarmeTab-Zeilen seit #1895 S3b1 und S3b2 nachgemessen; seit #2794 S3a Teil-PR 4a ohne die 22 Einträge von `CorridorEditor.svelte`/`CorridorEditorMobile.svelte` (Oberfläche entfernt), Korridor-Logik unter `wetter-tab/`)

### FACHLICH (4 — echter Sachunterschied, bleibt dauerhaft)

| Datei:Zeile | Grund |
|---|---|
| `AlarmeTab.svelte:270` | Ableitung `unalertableSelectedMetricNames` — route liefert strukturell immer `[]` (#1435 AC-7) |
| `AlarmeTab.svelte:555` | Anzeige-Zwilling der fachlichen Zusicherung aus `:270` |
| `alarme-tab/alarmeTabSections.ts:27` | Radar-Abschnitt nur im Vergleich |
| `wetter-tab/corridorEditorState.ts:331` | Markieren-Schalter bei Tages-Summen nur im Trip gesperrt |

### DARSTELLUNG (2 — nur Beschriftung/Sichtbarkeit, kein Datenweg-Unterschied)

| Datei:Zeile | Grund |
|---|---|
| `AlarmeTab.svelte:573` | Kurzstil-Schalter — im Trip steht derselbe Schalter im Versand-Reiter (#1260 S5), reine Platzierung |
| `alarme-tab/alarmeTabSections.ts:38` | nur Überschrifttext |

### HERKUNFT (1 — AC-2-Abweichung, bleibt bestehen, siehe Begründung oben)

| Datei:Zeile | Warum es (noch) eine HERKUNFT-Verzweigung ist | Warum sie bleibt |
|---|---|---|
| `wetter-tab/wertebereicheVergleichSpeicherung.ts:203` | Erzeugungs-Prädikat für Wertebereiche: nur aktiv, wenn `context === 'vergleich'` | Gate für einen strukturell anderen Persistenz-Endpoint (Compare-Preset) |

**Summe:** 4 FACHLICH + 2 DARSTELLUNG + 1 HERKUNFT = **7**, deckungsgleich
mit `EINGEFROREN_SOLL_ANZAHL` (Summenzeile in #2727 korrigiert — sie nannte 14 / 46;
Abgleich der `context ===`-Zweige gegen die Soll-Liste bestanden, kein Zweig entfällt;
#1721 hob danach FACHLICH 27 → 28; #2794 S3a Teil-PR 4a senkte sie mit dem entfernten
Corridor-Editor auf 14 / 3 / 9 = 26; #3155 entfernte die `isRoute`-Weiche in `VTSchedulePlan.svelte`: 13 / 3 / 9 = 25; #3297/#3020 löschten den Alt-Editor samt Versand-Baustein: 7 / 3 / 3 = 13; #3385 löschte die Waisen `vtBriefingChannelsText.ts` und `VTSchedulePlan.svelte`: 5 / 2 / 3 = 10;
#3389: 5 / 2 / 1 = 8 — `versandVergleichSpeicherung.ts:236` und `weatherMetricsCompareSave.ts:364`
(die beiden `…SpeicherungAktiv`-Weichen) mit den toten Exporten gelöscht;
#3458: 4 / 2 / 1 = 7 — `AlarmeTab.svelte:608` (Beispielwarnung, `AlertPreviewCard`) mit dem Abschnitt
`sample` entfernt).

## Changelog

- 2026-11-26: #3389 (tote Exporte) — `versandVergleichSpeicherung.ts:236` und
  `weather-metrics-tab/weatherMetricsCompareSave.ts:364` (die `…SpeicherungAktiv`-Weichen) mit den
  toten Exporten gelöscht; HERKUNFT 3 → 1, Summe 10 → 8 (Ratsche nachgezogen).
- 2026-11-26: #3399 S1: AlarmeTab-Zeilen +4 nachgezogen (268→272, 553→557, 571→575, 604→608).
- 2026-11-25: #3297/#3020 (Rückbau Alt-Editor) — `VersandTab.svelte`, `WeatherMetricsTab.svelte`,
  `weatherMetricsTabSections.ts` und `WetterMetrikenVersandPanel.svelte` gelöscht; ihre elf Einträge
  entfallen als ENTFERNTE Verzweigungen (FACHLICH 12 → 7, HERKUNFT 9 → 3), Summe 24 → 13 (Ratsche nachgezogen).
- 2026-11-19: #3155 (B4, Karte „Mehrtages-Trend" entfernt) — `VTSchedulePlan.svelte:57`
  (`isRoute`-Ableitung, nur für die Trend-Karte) entfällt, FACHLICH 14 → 13, Summe 26 → 25;
  `VTSchedulePlan.svelte` 84→72 und `VersandTab.svelte` 360→359, 370→369, 406→401 nur
  verschoben, Bedingungstext unverändert (Ratsche nachgezogen).
- 2026-11-15: #2931 (Rückbau DayWindowCard/Tagesfenster-Abschnitt) — alle sechs
  `WeatherMetricsTab.svelte`-Einträge nur verschoben (594→587, 609→602, 638→631, 651→644,
  1467→1447, 2056→1967) und `weatherMetricsTabSections.ts` 72→67, 73→68 (Kommentarblock zum
  entfallenen Abschnitt `tagesfenster` gelöscht); Bedingungstext unverändert, kein Eintrag
  entfällt, Summe bleibt 26 (Ratsche nachgezogen).

- 2026-11-12: #2794 S3a Teil-PR 4a (AC-31) — `CorridorEditor.svelte` und
  `CorridorEditorMobile.svelte` sind gelöscht; ihre 22 Einträge entfallen als ENTFERNTE
  Verzweigungen (FACHLICH −14, DARSTELLUNG −2, HERKUNFT −6). Die Logikmodule zogen nach
  `wetter-tab/` um (`corridorEditorState.ts:331`, `wertebereicheVergleichSpeicherung.ts:209`,
  Zeilen und Bedingungstext unverändert, nur der Pfad). Summe 48 → 26 (Ratsche und
  Doc-Compliance-Tests nachgezogen).

- 2026-11-02: #1721 — `WeatherMetricsTab.svelte:2042` (Nacht-Stundentabelle-Schalter nur im
  Trip) neu als FACHLICH; die fünf übrigen WeatherMetricsTab-Einträge nur verschoben
  (581→594, 596→609, 625→638, 638→651, 1429→1457), Bedingungstext unverändert.
  FACHLICH 27 → 28, Summe 47 → 48 (Ratsche und Doc-Compliance-Test nachgezogen).
- 2026-11-04: #2792 S1a — `WeatherMetricsTab.svelte` 1457→1467 und 2042→2052 nur verschoben
  (Ampel-Zustand beim Anwenden einer Vorlage im Script-Teil), Bedingungstext unverändert,
  Summe bleibt 48.
- 2026-11-09: #2794 S3a Teil-PR 2 — `WeatherMetricsTab.svelte` 2052→2056 nur verschoben
  (Darstellungsfilter `bereich`), Bedingungstext unverändert, Summe bleibt 48.
- 2026-10-05: #2287 (AC-11) — `alarme-tab/alarmeTabSections.ts:42` (`wertebereicheTabId`) entfällt mit der
  Funktion; DARSTELLUNG 6 → 5, Summe 47 → 46 (Ratsche und Doc-Compliance-Test nachgezogen).
- 2026-09-25: Initial spec created (Scheibe S6h von #2276, Epic #2345, Fast Track)
- 2026-09-25: Korrektur (gefunden vom neuen Doc-Compliance-Test
  `ac2_endbilanz_deckt_alle_47_ab.test.ts` bei der Implementierung): in der
  HERKUNFT-Tabelle fehlte zwei Einträgen das Unterverzeichnis-Präfix —
  `wertebereicheVergleichSpeicherung.ts:200` → `corridor-editor/wertebereicheVergleichSpeicherung.ts:200`,
  `weatherMetricsCompareSave.ts:534` → `weather-metrics-tab/weatherMetricsCompareSave.ts:534`.
  Reine Pfad-Schreibweise, keine inhaltliche Änderung an Kategorie oder Begründung —
  keine neue Freigabe nötig (Fast Track ohne PO-Briefing-Gate).
