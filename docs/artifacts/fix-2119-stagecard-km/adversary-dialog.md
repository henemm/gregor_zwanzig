# Adversary Dialog — fix-2119-stagecard-km
Spec: docs/specs/fast/fix-2119-stagecard-km.md
Datum: 2026-10-18 17:07

## Checkliste
- [x] **AC-1:** Given eine Etappe, deren Wegpunkte alle `distance_from_start_km` tragen, When die Etappen-Kachel (Desktop `StageCard`) gerendert wird, Then zeigt sie die Differenz letzter minus erster `distance_from_start_km` (z. B. 17.5 km) und nicht die Luftlinie.
- [x] **AC-2:** Given dieselbe Etappe, When die mobile Kachel (`StageCardM`) gerendert wird, Then zeigt sie denselben km-Wert wie die Desktop-Kachel und der Trip-Header.
- [x] **AC-3:** Given eine Etappe ohne vollständige `distance_from_start_km`, When die Kachel gerendert wird, Then zeigt sie weiterhin die Näherungs-Distanz (Fallback), ohne Fehler; bei weniger als 2 Wegpunkten erscheint keine km-Angabe.

## Dialog

### Runde 1
**Adversary:** Diff gelesen. AC-1: StageCard.svelte:24-26 ruft computeHeaderStats(stage).distanceKm (headerStats.ts: Differenz distance_from_start_km nur bei voll vermessener Etappe). Test frontend/src/lib/components/trip-detail/waypoints/__tests__/stage_card_km_gpx_distanz.test.ts:54-56 rendert echt (svelte/server), Luftlinie waere ca. 11 km, Erwartung 17.5. AC-2: StageCardM.svelte:68 nutzt dieselbe Funktion, Zahl identisch (Test :58-60); Ascent-Schleife :63-67 unveraendert. AC-3: unter 2 Wegpunkten null (StageCard.svelte:25, StageCardM.svelte:62 Guard wps.length >= 2); Fallback Haversine (Test :62-70). Repo-weit keine weitere 111.32-Formel mehr (grep); TripHeader/StageDetailRow/naismith/fullProfile nutzen headerStats-Regel. Pausen-Etappen: isPause-Zweig in beiden Kacheln unberuehrt (StageCard.svelte:96, StageCardM.svelte:105). Tests: 4 pass / 0 fail.
Mutationen (String-Ersetzung, Sicherung in Jobs-tmp, danach Byte-Identitaet geprueft): km konstant/0/null in beiden Kacheln, <2-Guard entfernt (Desktop) bzw. >=1 (mobil), useTrack=false/true, Faktor x2, letzter-minus-erster -> nur letzter: ALLE rot. Ueberlebt: M7 headerStats useTrack nur nach erstem Wegpunkt (Kacheltest nutzt nur voll/gar nicht vermessene Etappen; Teilmessung gehoert in headerStats.test.ts), M10/M11 Hoehenmeter-Teil der Anzeige auf null (Test prueft nur km-Regex, nicht das Format 12.8 km - Aufstieg).
**Implementierer:** (keine Rueckmeldung angefordert)

### Runde 2
**Adversary:** Gezielt gegen die Wirkstelle: beide Kacheln werden produktiv eingebunden (EtappenStrip.svelte:9 -> StageCard, EditStagesPanelNew.svelte:39 -> StageCardM), also kein toter Pfad. Test rendert die echten Komponenten, kein Monkeypatch. Randfall: Etappe mit nur teilweiser Messung faellt per stageHasFullTrackDistance komplett auf Haversine zurueck (kein Mischen) - in beiden Kacheln gleich, da gleiche Funktion. Randfall Rundung: computeHeaderStats rundet auf 0.01, Anzeige toFixed(1) - Desktop und mobil identisch. Keine Regression: Rueckgabewert bei >=2 Wegpunkten war vorher ebenfalls number; Fallback-Wert aendert sich leicht (Haversine statt Grad-Naeherung), laut Spec gewollt.
**Implementierer:** (keine Rueckmeldung angefordert)

## Herkunft der Vorbedingungen

Kein Sprachprofil konfiguriert.


### Findings
- F001 (LOW, edge_case): Kein Test faengt die Verfaelschung, die Teilmessung im Kachel-Pfad als voll vermessen wertet (headerStats.ts useTrack nur ueber ersten Wegpunkt).
  Code reference: frontend/src/lib/components/trip-detail/waypoints/__tests__/stage_card_km_gpx_distanz.test.ts:44-46 (nur voll- bzw. gar nicht vermessene Etappen). Abgedeckt dort nur indirekt durch headerStats.test.ts. Sammel-Eintrag, kein Blocker.
- F002 (LOW, edge_case): Hoehenmeter-Anteil der Kachel-Anzeige (Spec: darf sich nicht aendern) ungeschuetzt; ascent=null ueberlebt.
  Code reference: frontend/src/lib/components/mobile/StageCardM.svelte:63-67
  Code reference: frontend/src/lib/components/trip-detail/waypoints/StageCard.svelte:28-37
  Sammel-Eintrag.

### Bewiesene Stellen
Code reference: frontend/src/lib/components/trip-detail/waypoints/StageCard.svelte:24-26
Code reference: frontend/src/lib/components/mobile/StageCardM.svelte:68

## Verdict
**VERIFIED**
AC-1, AC-2, AC-3 bewiesen (Code-Pfad + 4/4 Tests, 10 von 13 Mutationen rot, 3 Ueberlebende (M7, M10, M11) nur LOW). Arbeitsbaum nach Mutationen byte-identisch zur Sicherung.

## Geprüfte Dateien

- sha256:d1b3b9bce9f4867a434751438b8bf7fa8342b543c0ce096d9ea7aec1346a1794  frontend/src/lib/components/mobile/StageCardM.svelte
- sha256:a706c911d68f7ce70f6edbb913eb756a2cd507e4c7ba997b173425424c8e81f5  frontend/src/lib/components/trip-detail/waypoints/StageCard.svelte
- sha256:abf8efebce5170b278c016c67f3278c626ef8cdeddf444ba850bb98ea500850b  frontend/src/lib/components/trip-detail/waypoints/__tests__/stage_card_km_gpx_distanz.test.ts

## Prüfbasis

- base: 302131e31733fa2f542b3cd1b3047b29c1faac93
- blob:fa3c9c86b20acd5a73c1c3d0941737604dc1a1b7  frontend/src/lib/components/mobile/StageCardM.svelte
- blob:36231bf46908c7b80130f521777d3e95f5af3e8e  frontend/src/lib/components/trip-detail/waypoints/StageCard.svelte
- blob:2f4933bcdc29ba03407dfc19aab35f493c0a4900  frontend/src/lib/components/trip-detail/waypoints/__tests__/stage_card_km_gpx_distanz.test.ts
