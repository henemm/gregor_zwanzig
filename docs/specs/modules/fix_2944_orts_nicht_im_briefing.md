---
entity_id: fix_2944_orts_nicht_im_briefing
type: bugfix
created: 2026-11-15
updated: 2026-11-15
status: draft
version: "1.0"
workflow: fix-2944-orts-nicht-im-briefing
tags: [frontend, wetter-tab, ortsvergleich, bug-2944]
---

# Fix #2944: Orts-Briefing "Nicht im Briefing" bietet nur Vergleichs-Metriken an

## Approval

- [ ] Approved

## Purpose

Im Orts-Briefing (Reiter Wetter) soll der Abschnitt "Nicht im Briefing" nur Metriken anbieten, die der Vergleichs-Katalog kennt. Bisher erscheinen dort auch trip-exklusive Gehzeit- und Nacht-Größen, die für Orte nicht berechnet werden (PO-Entscheid 2026-08-19, #1848 C: Gehzeit ist trip-exklusiv).

## Source

- **File:** `frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte`
- **Identifier:** Ableitung `nichtIm` (~Z. 201-205); neue reine Funktion `briefingAngebot` in `frontend/src/lib/components/shared/wetter-tab/ampelModell.ts`

Schicht: Frontend (SvelteKit). Kein Go-/Python-Code betroffen.

- **Trip/Ortsvergleich-Teilung:** Bestehender geteilter Baustein (`shared/wetter-tab`, `context="route"|"vergleich"`); keine neue Komponente, kein Pendant nötig. Kontext-Unterschied als Daten-Tabelle `Record<Kontext, …>`, kein `if (context === …)` (Ratsche `context_herkunft_zweige_eingefroren`).
- **Mandantentrennung:** Rein clientseitige Filterung eines nutzerunabhängigen Katalogs; keine Datenbewegung, daher kein Zwei-Nutzer-Datentest nötig.
- **Kanäle:** Betrifft nur die Editor-Oberfläche, keinen Briefing-/Alarm-Inhalt; E-Mail, Telegram, SMS und Premium-SMS unberührt.
- **Sprache DE/EN:** Kein neuer Nutzertext, Katalog unberührt.

## Estimated Scope

- **LoC:** +60/-3 (davon ~45 Test)
- **Files:** 3
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `/api/metrics` | API | Zentraler Katalog (Trip), liefert `daten.eig` |
| `/api/compare/metrics` | API | SSoT Vergleichs-Katalog, via `loadCompareSelectionEntries()` (`metric_id` je Eintrag) |
| `shared/wetter-tab/wetterTabLaden.ts` | module | Lädt zentralen Katalog (unverändert) |
| `shared/wetter-tab/compareMetricCatalogLoader.ts` | module | Liefert Vergleichs-Katalog-Einträge (unverändert) |
| `organisms/wetter-tab/NichtImBriefing.svelte` | component | Stellt die Chips dar (unverändert) |
| `tests/unit/test_gehzeit_metriken_bleiben_trip_exklusiv.py` | test | Backend-Wächter, bleibt SSoT für Gehzeit-Exklusivität |
| `docs/specs/modules/feat_2794_s3a_teil3_wetter.md` | spec | Bezugs-Spec (AC-19 "Nicht im Briefing") |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/wetter-tab/ampelModell.ts` | MODIFY | Neue reine Funktion `briefingAngebot(context, eig, auswahl, katalogIds)` mit Daten-Tabelle `ANGEBOTS_FILTER: Record<Kontext, (id, katalogIds) => boolean>`; Reihenfolge über `zeilenGruppen` |
| `frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte` | MODIFY | `katalogIds` aus `laden()` als State halten, `nichtIm` über `briefingAngebot` ableiten |
| `frontend/src/lib/components/shared/wetter-tab/__tests__/nicht_im_briefing_kontextkatalog.test.ts` | CREATE | `node --test`; Vergleichs-Katalog aus echtem Python-Katalog (Muster `wetterTabDaten.ts`), kein Mock |

## Implementation Details

Ursache: `nichtIm` bildet das Angebot aus allen Schlüsseln von `daten.eig` (zentraler Katalog) minus Auswahl, ohne Kontextfilter. Der Vergleichs-Katalog liegt in `laden()` bereits vor, wird aber nur für `aggregation`/`altSchluessel` genutzt und danach verworfen.

Messung am Bestand: Nur im zentralen, nicht im Vergleichs-Katalog stehen `temperature_day_high`, `temperature_day_low`, `wind_chill_day_high`, `wind_chill_day_low` (Gehzeit) sowie `temperature_night`, `wind_chill_night`. Die übrigen 23 `metric_id`s sind in beiden.

Ansatz:

1. `briefingAngebot` in `ampelModell.ts`. Tabelle: `route` lässt jede Metrik zu, `vergleich` nur `metric_id`s aus `katalogIds`.
2. `laden()` hält `katalogIds = new Set(katalog.map(e => e.metric_id))`; `nichtIm` ruft die Funktion auf.
3. Die bestehende Auswahl wird nicht gefiltert, nur das Angebot. Keine Datenänderung, kein Schema-Rework.

## Expected Behavior

- **Input:** Kontext, zentraler Katalog (`daten.eig`), aktuelle Auswahl, Vergleichs-Katalog-IDs.
- **Output:** Liste der angebotenen Metriken in gewohnter Reihenfolge. Trip: alle zentralen Metriken minus Auswahl. Ort: Vergleichs-Katalog-Metriken minus Auswahl.
- **Side effects:** Keine.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN Kontext vergleich mit echtem Vergleichs-Katalog WHEN Angebot berechnet THEN keine der vier Gehzeit-IDs und keine Nacht-ID enthalten
- [ ] Test 2: GIVEN Kontext vergleich, leere Auswahl WHEN Angebot berechnet THEN genau die Vergleichs-Katalog-Metriken
- [ ] Test 3: GIVEN Kontext route WHEN Angebot berechnet THEN alle zentralen Metriken minus Auswahl, Gehzeit inklusive
- [ ] Test 4: GIVEN Orts-Auswahl enthält eine Nicht-Vergleichs-Metrik WHEN Angebot berechnet THEN Auswahl unverändert, Metrik nicht im Angebot
- [ ] Test 5 (Staging-E2E, Playwright gegen staging, kein Mock): GIVEN Orts-Briefing WHEN Chip in "Nicht im Briefing" angeklickt und Seite neu geladen THEN Metrik steht in der Auswahl und nicht mehr im Angebot

Tests 1–4 mit `node --test` (kein Vitest), Test 5 als Staging-E2E. Vergleichs-Katalog aus dem echten Python-Katalog, kein Mock. Staging-Nachweis aus Nutzersicht (Orts-Briefing und Trip im Browser).

## Acceptance Criteria

- **AC-1:** Given ein Orts-Briefing (Ort oder Vergleich) im Reiter Wetter / When der Nutzer den Abschnitt "Nicht im Briefing" öffnet / Then enthält er keine Gehzeit-Metriken (Tages-Tiefst/Höchst, Gefühlte … (Gehzeit)) und keine Nacht-Größen, die nicht im Vergleichs-Katalog stehen
  - Test: Angebot im Kontext vergleich gegen den echten Vergleichs-Katalog enthält keine der sechs trip-exklusiven IDs; Staging-Sichtprüfung im Orts-Briefing ohne "(Gehzeit)"

- **AC-2:** Given ein Orts-Briefing mit einer Auswahl / When der Nutzer "Nicht im Briefing" betrachtet / Then werden alle Vergleichs-Katalog-Metriken, die nicht gewählt sind, weiterhin angeboten
  - Test: Angebot = Vergleichs-Katalog minus Auswahl, vollständig und in gewohnter Reihenfolge

- **AC-3:** Given ein Trip-Briefing im Reiter Wetter / When der Nutzer "Nicht im Briefing" öffnet / Then werden weiterhin alle zentralen Metriken minus Auswahl angeboten, Gehzeit-Metriken inklusive
  - Test: Angebot im Kontext route entspricht allen Schlüsseln des zentralen Katalogs minus Auswahl; Staging-Sichtprüfung im Trip mit "(Gehzeit)"

- **AC-4:** Given ein Ort, dessen bestehende Auswahl eine Metrik außerhalb des Vergleichs-Katalogs enthält / When der Reiter geöffnet wird / Then bleibt die Auswahl unverändert und nur das Angebot ist gefiltert
  - Test: Auswahl vor und nach der Angebotsberechnung identisch; die Metrik erscheint nicht im Angebot

- **AC-5:** Given ein Orts-Briefing mit Chips in "Nicht im Briefing" / When der Nutzer einen Chip anklickt / Then wird die Metrik zur Auswahl hinzugefügt, gespeichert und verschwindet aus dem Angebot
  - Test: Staging-E2E (Playwright, echter Login, kein Mock): Chip anklicken, Seite neu laden, Metrik in der Auswahl und nicht im Angebot; Hinzufügen-/Speicherlogik selbst bleibt unverändert

- **AC-6:** Given der Code der Angebotsableitung / When der Kontext-Unterschied umgesetzt wird / Then steckt er in einer Daten-Tabelle `Record<Kontext, …>` und nicht in einem `if (context === …)`-Zweig
  - Test: Ratsche `context_herkunft_zweige_eingefroren` bleibt grün; Verhaltenstest ruft beide Kontexte über dieselbe Funktion auf

## Definition of Done

- AC-1 bis AC-6 grün: Tests 1–4 per `node --test`, Test 5 als Staging-E2E; Adversary VERIFIED inkl. Mutations-Gegenprobe (z. B. Filter entfernt, Kontexte vertauscht).
- Staging-Sichtprüfung: Orts-Briefing ohne „(Gehzeit)" in „Nicht im Briefing", Trip-Briefing unverändert mit „(Gehzeit)".
- PR mit allen 6 CI-Checks grün gemergt, Prod-Deploy und Selftest Exit 0.

## Known Limitations

- Eine bereits gespeicherte Orts-Auswahl mit Nicht-Vergleichs-Metrik wird nicht bereinigt (bewusst, keine Datenänderung).
- Der Nachweis für den Vergleichs-Katalog hängt vom Python-Katalog ab; der Backend-Wächter `test_gehzeit_metriken_bleiben_trip_exklusiv.py` sichert dessen Gehzeit-Exklusivität.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Angebotsfilterung nach bestehender Entscheidung (Gehzeit trip-exklusiv, #1848 C); keine neue Entscheidungsfläche.

## Changelog

- 2026-11-15: Initial spec created
