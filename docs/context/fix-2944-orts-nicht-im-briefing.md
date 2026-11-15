# Context: fix-2944-orts-nicht-im-briefing

## Request Summary
Im Orts-Briefing (`context="vergleich"`), Reiter Wetter, bietet „Nicht im Briefing" alle Metriken des
zentralen Trip-Katalogs an, darunter die trip-exklusiven Gehzeit-Größen („Tages-Tiefst-/Höchsttemperatur
(Gehzeit)", „Gefühlte Tages-… (Gehzeit)"). Für Orte darf nur angeboten werden, was der Vergleichs-Katalog kennt.

## Ursache (belegt)
- `frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte:201-205` — `nichtIm` =
  alle Schlüssel von `daten.eig` minus Auswahl, **ohne Kontextfilter**.
- `daten.eig` kommt aus `ladeWetterDaten()` (`shared/wetter-tab/wetterTabLaden.ts:61-74`), das für beide
  Kontexte `/api/metrics` (zentraler Katalog) lädt.
- Der Vergleichs-Katalog wird im Vergleich bereits geladen (`VERGLEICHS_KATALOG[context]()`,
  `WetterTabInhalt.svelte:54-57, 97`), aber nur für `aggregation`/`altSchluessel` genutzt.
- Messung am Bestand (Python, `get_compare_metrics()` vs. `get_all_metrics()`): Nur im zentralen Katalog,
  nicht im Vergleich: `temperature_day_high`, `temperature_day_low`, `wind_chill_day_high`,
  `wind_chill_day_low` (Gehzeit, PO-Entscheid 2026-08-19 trip-exklusiv, #1848 C) sowie
  `temperature_night`, `wind_chill_night`. Alle übrigen 23 `metric_id`s sind in beiden.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte` | `nichtIm`-Ableitung, lädt Vergleichs-Katalog |
| `frontend/src/lib/components/shared/wetter-tab/ampelModell.ts` | reine Funktionen (`zeilenGruppen`, `Kontext`), Ort für eine testbare Angebotsfunktion |
| `frontend/src/lib/components/shared/wetter-tab/wetterTabLaden.ts` | gemeinsamer Lader (zentraler Katalog) |
| `frontend/src/lib/components/shared/wetter-tab/compareMetricCatalogLoader.ts` | `loadCompareSelectionEntries()` (`metric_id` je Eintrag) |
| `frontend/src/lib/components/organisms/wetter-tab/NichtImBriefing.svelte` | Darstellung (unverändert) |
| `tests/unit/test_gehzeit_metriken_bleiben_trip_exklusiv.py` | Backend-Wächter: Gehzeit nie im Vergleichs-Katalog |
| `docs/specs/modules/feat_2794_s3a_teil3_wetter.md` | Spec des Reiters (AC-19 „Nicht im Briefing") |

## Existing Patterns
- Kontext-Unterschiede als Daten-Tabellen (`Record<Kontext, …>`, Ratsche `context_herkunft_zweige_eingefroren`) —
  keine `if (context === …)`-Zweige.
- Logik als reine Funktion in `shared/wetter-tab/*.ts`, getestet mit `node --test` (kein Vitest).

## Dependencies
- Upstream: `/api/metrics`, `/api/compare/metrics` (SSoT Vergleichs-Katalog).
- Downstream: `NichtImBriefing` (Chips „+ X"), `hinzufuegen()` (Auswahl erweitern, Speichern).

## Risiken
- Trip-Kontext darf sich nicht ändern (weiter alle zentralen Metriken).
- Bestands-Auswahl eines Orts mit (theoretisch) Nicht-Vergleichs-Metrik: nur das Angebot filtern, Auswahl nicht anfassen.
- DE/EN: keine neuen Texte nötig; Zwei-Nutzer-Test: rein clientseitige Filterung, Katalog nutzerunabhängig.

## Analysis

### Type
Bug (Frontend-only, Orts-Briefing Reiter Wetter, Abschnitt „Nicht im Briefing")

### Root Cause (bestätigt am Code, Stand 507570a0c)
`WetterTabInhalt.svelte` (`nichtIm`, ~Z. 201-205) bildet das Angebot aus `Object.keys(daten.eig)` (zentraler
Katalog `/api/metrics`) minus Auswahl, ohne Kontextfilter. Der Vergleichs-Katalog (`VERGLEICHS_KATALOG[context]()`,
`CompareSelectionEntry[]` mit `metric_id`) liegt in `laden()` bereits vor, wird aber nur für `aggregation`/`altSchluessel`
verwertet und danach verworfen. Bug-Intake-/Plan-Agenten nicht separat gestartet: Ursache und Katalog-Differenz sind in
Phase 1 per Code und Python-Messung belegt; Scope ist eine Ableitung.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/wetter-tab/ampelModell.ts` | MODIFY | neue reine Funktion `briefingAngebot(context, eig, auswahl, katalogIds)` mit Daten-Tabelle `Record<Kontext, …>` (route: alle zentralen Metriken; vergleich: nur `metric_id`s des Vergleichs-Katalogs), Reihenfolge über `zeilenGruppen` |
| `frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte` | MODIFY | `katalogIds` aus `laden()` als State halten, `nichtIm` über `briefingAngebot` ableiten |
| `frontend/src/lib/components/shared/wetter-tab/__tests__/nicht_im_briefing_kontextkatalog.test.ts` | CREATE | `node --test`: Vergleich bietet keine Gehzeit-/Nacht-Metriken an, Trip unverändert alle; Vergleichs-Katalog aus echtem Python-Katalog (Muster `wetterTabDaten.ts`), kein Mock |

### Scope Assessment
- Files: 3 (2 MODIFY, 1 CREATE)
- Estimated LoC: +60/-3 (davon ~45 Test)
- Risk Level: LOW (reine Angebotsfilterung, Auswahl/Speichern unberührt, Trip-Pfad per Tabelle identisch)

### Technical Approach
1. Reine Funktion in `ampelModell.ts`; Kontext-Unterschied als Daten (`ANGEBOTS_FILTER: Record<Kontext, (id, katalogIds) => boolean>`),
   kein `if (context === …)` (Ratsche `context_herkunft_zweige_eingefroren`).
2. `laden()` speichert `katalogIds = new Set(katalog.map(e => e.metric_id))`; `nichtIm` nutzt die Funktion.
3. Bestehende Auswahl eines Orts wird NICHT gefiltert (nur das Angebot): keine Datenänderung, kein Schema-Rework.
4. Kein neuer Text (DE/EN unberührt); Katalog nutzerunabhängig, keine Datenbewegung ⇒ kein Zwei-Nutzer-Datentest nötig.
5. Nachweis aus Nutzersicht: Staging Orts-Briefing → „Nicht im Briefing" ohne „(Gehzeit)", Trip weiter mit.

### Dependencies
Upstream `/api/metrics`, `/api/compare/metrics` (via `loadCompareSelectionEntries`, gecacht). Downstream `NichtImBriefing.svelte`
(unverändert), `hinzufuegen()`. Backend-Wächter `tests/unit/test_gehzeit_metriken_bleiben_trip_exklusiv.py` bleibt SSoT.

### Open Questions
- keine (Produktentscheid Gehzeit trip-exklusiv liegt vor, #1848 C, PO 2026-08-19)
