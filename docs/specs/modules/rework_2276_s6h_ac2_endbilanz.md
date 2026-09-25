---
entity_id: rework_2276_s6h_ac2_endbilanz
type: refactor
created: 2026-09-25
updated: 2026-09-25
status: draft
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

## Anhang: AC-2-Endbilanz — alle 47 Ratschen-Einträge (Stand `3cece096`, S6g live)

### FACHLICH (27 — echter Sachunterschied, bleibt dauerhaft)

| Datei:Zeile | Grund |
|---|---|
| `AlarmeTab.svelte:256` | Ableitung `unalertableSelectedMetricNames` — route liefert strukturell immer `[]` (#1435 AC-7) |
| `AlarmeTab.svelte:514` | Anzeige-Zwilling der fachlichen Zusicherung aus `:256` |
| `AlarmeTab.svelte:566` | Beispielwarnung: Ort- statt Etappen-Subjekt, zwei verschiedene Komponenten |
| `VersandTab.svelte:358` | Markup-Baum Trip (`VTLaufzeitRoute`, Mehrtages-Trend, Premium-SMS) |
| `VersandTab.svelte:394` | Markup-Baum Vergleich (`VTLaufzeitVergleich`, kein Mehrtages-Trend, kein Premium-SMS) — zwei komplette, unterschiedliche Komponenten-Bäume |
| `WeatherMetricsTab.svelte:1439` | Metrik-Markup-Baum (#1311 C1: Vergleich-Grundauswahl) |
| `versand-tab/vtBriefingChannelsText.ts:21` | SMS-Zeichenbudget: Trip 160 / Vergleich 153 (unterschiedliches Layout) |
| `versand-tab/vtBriefingChannelsText.ts:26` | Einleitungstext: Etappen-Tabelle vs. Orts-Tabelle — inhaltlich verschiedene Datenform |
| `versand-tab/VTSchedulePlan.svelte:55` | `isRoute`-Ableitung — Mehrtages-Trend-Karte existiert nur im Trip |
| `alarme-tab/alarmeTabSections.ts:27` | Radar-Abschnitt nur im Vergleich |
| `corridor-editor/corridorEditorState.ts:297` | Markieren-Schalter bei Tages-Summen nur im Trip gesperrt |
| `weather-metrics-tab/weatherMetricsTabSections.ts:72` | SMS-Schwellen/Report-Config nur im Trip |
| `weather-metrics-tab/weatherMetricsTabSections.ts:73` | Stundenverlauf-Abschnitt nur im Vergleich |
| `corridor-editor/CorridorEditor.svelte:141` | `isFreshCompareCreate` — Profil-Prefill nur bei frischer Vergleichs-Anlage, kein Trip-Äquivalent |
| `corridor-editor/CorridorEditor.svelte:313` | `add()` — `addCompareRow`/`addRow` unterscheiden sich strukturell (CompareMetricDef vs. RouteMetricDef) |
| `corridor-editor/CorridorEditor.svelte:347` | Ladefehler-Banner, gebunden an den Compare-Katalog-Ladepfad |
| `corridor-editor/CorridorEditor.svelte:360` | Ladezustand „Lade Metriken…", gebunden an den Compare-Katalog-Ladepfad |
| `corridor-editor/CorridorEditor.svelte:363` | Ladezustand „Lade Metriken…", gebunden an den Route-Zusatzmetriken-Ladepfad |
| `corridor-editor/CorridorEditor.svelte:390` | Rückfall-Warnung auf die 6 Standardmetriken, nur route-spezifisch |
| `corridor-editor/CorridorEditor.svelte:519` | AC-13-Neutralitäts-Hinweis — Ranking-Konzept existiert nur im Vergleich |
| `corridor-editor/CorridorEditorMobile.svelte:144` | Mobil-Zwilling von `CorridorEditor.svelte:141` |
| `corridor-editor/CorridorEditorMobile.svelte:279` | Mobil-Zwilling von `CorridorEditor.svelte:313` |
| `corridor-editor/CorridorEditorMobile.svelte:342` | Mobil-Zwilling von `CorridorEditor.svelte:347` |
| `corridor-editor/CorridorEditorMobile.svelte:355` | Mobil-Zwilling von `CorridorEditor.svelte:360` |
| `corridor-editor/CorridorEditorMobile.svelte:358` | Mobil-Zwilling von `CorridorEditor.svelte:363` |
| `corridor-editor/CorridorEditorMobile.svelte:375` | Mobil-Zwilling von `CorridorEditor.svelte:390` |
| `corridor-editor/CorridorEditorMobile.svelte:496` | Mobil-Zwilling von `CorridorEditor.svelte:519` |

### DARSTELLUNG (6 — nur Beschriftung/Sichtbarkeit, kein Datenweg-Unterschied)

| Datei:Zeile | Grund |
|---|---|
| `AlarmeTab.svelte:533` | Kurzstil-Schalter — im Trip steht derselbe Schalter im Versand-Reiter (#1260 S5), reine Platzierung |
| `corridor-editor/CorridorEditor.svelte:369` | Überschrift-/Lauftext-Wahl, keine Datenverzweigung |
| `corridor-editor/CorridorEditorMobile.svelte:363` | Mobil-Zwilling von `CorridorEditor.svelte:369` |
| `versand-tab/VTSchedulePlan.svelte:83` | Erklärtext „wie beim Trip" — reine Zusatzerklärung, keine Funktionsänderung |
| `alarme-tab/alarmeTabSections.ts:38` | nur Überschrifttext |
| `alarme-tab/alarmeTabSections.ts:42` | nur DOM-/Tab-Id |

### HERKUNFT (14 — AC-2-Abweichung, bleibt bestehen, siehe Begründung oben)

| Datei:Zeile | Warum es (noch) eine HERKUNFT-Verzweigung ist | Warum sie bleibt |
|---|---|---|
| `versandVergleichSpeicherung.ts:221` | Erzeugungs-Prädikat: nur aktiv, wenn `context === 'vergleich'` | Gate für einen strukturell anderen Persistenz-Endpoint (Compare-Preset) |
| `corridor-editor/wertebereicheVergleichSpeicherung.ts:200` | dito für Wertebereiche | dito |
| `weather-metrics-tab/weatherMetricsCompareSave.ts:534` | dito für Wetter-Metriken | dito **und** zugleich die von S4 AC-13 geforderte Hydration-Barriere — AC-13 hat Vorrang (siehe AC-3) |
| `corridor-editor/CorridorEditor.svelte:184` | Katalog-Guard: lädt `loadCompareMetricCatalog()` nur im Vergleich | Mirror-Guard zu `:216`; Auflösung bräuchte injizierte Lade-Funktion statt `context`-Schalter |
| `corridor-editor/CorridorEditor.svelte:216` | Katalog-Guard: lädt `loadRouteExtraMetricDefs()` nur im Trip | dito, Kehrseite von `:184` |
| `corridor-editor/CorridorEditorMobile.svelte:172` | Mobil-Zwilling von `:184` | dito |
| `corridor-editor/CorridorEditorMobile.svelte:197` | Mobil-Zwilling von `:216` | dito |
| `corridor-editor/CorridorEditor.svelte:285` | `maybeSchedule()`: wählt zwischen `vergleichSpeicherung.aenderungMelden()` und `saveController.schedule(buildSaveFn())` | Genau der in AC-2 benannte Beispielfall „Vergleichs-Speicherweg vs. `saveController.schedule`" — Auflösung bräuchte eine injizierte `SaveFn`, eigene Architekturentscheidung |
| `corridor-editor/CorridorEditorMobile.svelte:252` | Mobil-Zwilling von `:285` | dito |
| `VersandTab.svelte:348` | Wirkort-Guard des Selbst-Speicher-Effekts — läuft nur im Vergleich | Effekt existiert nur für den Compare-Speicherweg; Trip speichert über einen anderen Mechanismus außerhalb dieser Datei |
| `WeatherMetricsTab.svelte:590` | Ladepfad-Zwilling: Hydration-Guard nur für `route` | Trip und Vergleich laden ihre Kataloge über verschiedene Wege; echte Vereinheitlichung ist eine Ladeschicht-Frage, nicht Teil von S6 |
| `WeatherMetricsTab.svelte:605` | Ladepfad-Zwilling: Katalog-Nachlade-Guard nur für `route` | dito |
| `WeatherMetricsTab.svelte:634` | Ladepfad-Zwilling: SMS-Symbole nur im Vergleich laden | dito |
| `WeatherMetricsTab.svelte:647` | Ladepfad-Zwilling: Katalog-Nachlade-Guard nur für `vergleich` | dito |

**Summe:** 27 FACHLICH + 6 DARSTELLUNG + 14 HERKUNFT = **47**, deckungsgleich
mit `EINGEFROREN_SOLL_ANZAHL`.

## Changelog

- 2026-09-25: Initial spec created (Scheibe S6h von #2276, Epic #2345, Fast Track)
- 2026-09-25: Korrektur (gefunden vom neuen Doc-Compliance-Test
  `ac2_endbilanz_deckt_alle_47_ab.test.ts` bei der Implementierung): in der
  HERKUNFT-Tabelle fehlte zwei Einträgen das Unterverzeichnis-Präfix —
  `wertebereicheVergleichSpeicherung.ts:200` → `corridor-editor/wertebereicheVergleichSpeicherung.ts:200`,
  `weatherMetricsCompareSave.ts:534` → `weather-metrics-tab/weatherMetricsCompareSave.ts:534`.
  Reine Pfad-Schreibweise, keine inhaltliche Änderung an Kategorie oder Begründung —
  keine neue Freigabe nötig (Fast Track ohne PO-Briefing-Gate).
