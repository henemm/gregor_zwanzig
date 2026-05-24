# Context: Issue #334 — Cleanup TripHero.svelte (toter Code)

## Request Summary

`frontend/src/lib/components/trip-detail/TripHero.svelte` wird seit dem Trip-Detail-Redesign (#302) nirgends mehr gerendert. Diese Komponente, ihr Barrel-Re-Export und der zugehörige tote E2E-Test sollen entfernt werden — ohne noch genutzten Code mitzureißen.

## Related Files

| Datei | Relevanz | Status |
|------|----------|--------|
| `frontend/src/lib/components/trip-detail/TripHero.svelte` | Die tote Komponente selbst | **LÖSCHEN** |
| `frontend/src/lib/components/trip-detail/index.ts` | Zeile 5 re-exportiert `TripHero` (einzige verbleibende Referenz) | **Re-Export entfernen** |
| `frontend/e2e/trip-detail-hero.spec.ts` | E2E-Test prüft `trip-hero`-TestIDs, die seit #302 nicht mehr im DOM sind → gebrochener/toter Test | **LÖSCHEN (siehe Risiken)** |
| `frontend/src/lib/utils/tripHero.ts` | Utils — 2 von 4 Funktionen noch aktiv genutzt von `TripHeader.svelte` | **BEHALTEN** |
| `frontend/src/lib/utils/tripHero.test.ts` | Unit-Tests der Utils (node:test) | **BEHALTEN** (ggf. 2 obsolete Tests, siehe Scope) |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | #302-Ersatz; nutzt `formatDateRange` + `getDaysLabel` aus `tripHero.ts` | unverändert |
| `frontend/src/routes/trips/[id]/+page.svelte` | Importiert nur `TripHeader, TripTabs` — NICHT `TripHero` | unverändert (Beweis) |
| `frontend/docs/artifacts/epic-135-step3-trip-hero/screenshot-hero.png` | Artefakt des Hero-E2E-Screenshot-Tests | optional aufräumen |
| `docs/specs/modules/epic_135_step3_trip_hero.md` | Ursprüngliche Spec der Hero-Feature | historisch, NICHT löschen |

## Abhängigkeits-Analyse (kritisch)

`tripHero.ts` exportiert 4 Funktionen. Verwendung NACH TripHero-Entfernung:

| Funktion | Genutzt von | Nach Entfernung |
|----------|-------------|-----------------|
| `formatDateRange` | TripHeader.svelte:27 + TripHero | **weiter aktiv** |
| `getDaysLabel` | TripHeader.svelte:28 + TripHero | **weiter aktiv** |
| `getActiveStageDisplay` | nur TripHero + tripHero.test.ts | **verwaist** |
| `getNextBriefing` | nur TripHero + tripHero.test.ts | **verwaist** |

→ `tripHero.ts` und `tripHero.test.ts` dürfen NICHT pauschal gelöscht werden. Nur die zwei verwaisten Funktionen + deren Tests sind potenziell zusätzlich entfernbar (Scope-Entscheidung).

## Existing Patterns

- **Barrel-Export-Cleanup:** Komponenten werden zentral in `index.ts` re-exportiert; Entfernen = eine Zeile streichen + `.svelte`-Datei löschen.
- **Tote E2E-Specs:** #302-Redesign wird abgedeckt von `issue-302-trip-detail-redesign.spec.ts`, `trip-detail-tabs.spec.ts`, `trip-detail-actions.spec.ts`, `trip-detail-region.spec.ts`. Die noch validen Checks der Hero-Spec (AC-16 Tab-Nav, Breadcrumb, Status-Badge, AC-202 Region) sind dort redundant abgedeckt.
- **Vorgänger-Cleanups:** Issues #277/#323 (Hex-Fallbacks/Dead-Code) — gleiche Vorgehensweise: verifizieren → entfernen → grünes Test-Lauf.

## Dependencies

- **Upstream (was TripHero nutzt):** `tripHero.ts`-Utils, `TopoBg`, `$lib/types`. Keine dieser Abhängigkeiten wird durch das Löschen beschädigt (TopoBg/Types vielfach genutzt).
- **Downstream (was TripHero nutzt):** NICHTS außer `index.ts:5`. Kein `<TripHero>`-Tag im gesamten `frontend/src`.

## Existing Specs

- `docs/specs/modules/epic_135_step3_trip_hero.md` — Hero-Feature-Spec (historisch, durch #302 überholt)
- `docs/specs/modules/issue_302_trip_detail_page.md` — Redesign, das TripHero verdrängt hat

## Risks & Considerations

1. **E2E-Spec-Status verifizieren:** `trip-detail-hero.spec.ts` MÜSSTE seit #302 rot/gebrochen sein (testet nicht mehr existente `trip-hero`-TestIDs). In Phase 2 prüfen, ob die Spec im Lauf aktiv rot ist oder ob sie aus Versehen nie ausgeführt wird. Wenn rot → Löschen behebt zugleich einen roten Test.
2. **Scope-Frage (Phase 2/3 entscheiden):** Sollen die verwaisten Util-Funktionen `getActiveStageDisplay` + `getNextBriefing` (+ deren 8 Tests in `tripHero.test.ts`) mit-entfernt werden? Pro: keine toten Funktionen zurücklassen. Contra: Issue verlangt nur die Komponente; konservativer Scope. Empfehlung tendiert zu „mit-entfernen", da sonst ein zweiter Cleanup-Folge-Issue nötig wäre.
3. **Parallele Session-Arbeit:** Git-Index enthält bereits Staged-Arbeit für **#344** (account/wetter-profile). Diese Dateien NICHT anfassen, NIE `git add -A`. Beim Committen nur die #334-relevanten Pfade gezielt stagen (siehe Memory: shared-index-commit).
4. **Spec/Artefakt:** Hero-Spec `epic_135_step3_trip_hero.md` bleibt als historisches Dokument. Screenshot-Artefakt kann gelöscht werden (wird vom toten Test erzeugt), ist aber unkritisch.

## Analyse-Entscheidung (Phase 2)

**Typ:** Reine Aufräum-/Löschaufgabe (kein Bug, kein Feature). Keine Architektur-Entscheidung, keine neuen Pfade — daher keine 3-Explore-/Plan-Agenten-Ceremony (vgl. „kein Spec-Writer für Triviales").

**Helfer-Abhängigkeits-Trace in `tripHero.ts` (entscheidend):**

| Helfer | genutzt von Überlebenden? | Konsequenz |
|--------|---------------------------|------------|
| `daysBetween`, `parseStageDate`, `todayIso`, `sortedStageDates`, `MONTH_NAMES_DE`, `deriveTripStatus` | ja (getDaysLabel + formatDateRange) | **BEHALTEN** |
| `parseHHMM`, `compareHHMM` | nein — nur getNextBriefing | **MIT-ENTFERNEN** |

→ Die Schnittgrenzen sind crisp: `getActiveStageDisplay` (Z. 54–84) entfernen reißt nichts mit; `getNextBriefing` (Z. 102–117) + `parseHHMM` (86–93) + `compareHHMM` (95–100) bilden ein geschlossenes Cluster. Überlebende Funktionen bleiben byte-gleich.

**Empfehlung (vollständiger Cleanup, gewählt):**
1. `TripHero.svelte` löschen (96 Z.)
2. Re-Export in `index.ts` Zeile 5 entfernen (1 Z.)
3. `trip-detail-hero.spec.ts` löschen (197 Z.) — testet nicht mehr existente `trip-hero`-TestIDs, läuft im Playwright-Normallauf (keine Config-Ausnahme) → seit #302 rot; valide Rest-Checks redundant in `issue-302-…`/`trip-detail-tabs`/`-actions`/`-region`
4. `getActiveStageDisplay` + `getNextBriefing` + `parseHHMM` + `compareHHMM` aus `tripHero.ts` entfernen (~61 Z.) — **überlebende Funktionen + geteilte Helfer unangetastet**
5. Zugehörige 10 Tests aus `tripHero.test.ts` entfernen (~100 Z.) — Tests für `getDaysLabel` + `formatDateRange` bleiben
6. Screenshot-Artefakt `epic-135-step3-trip-hero/` entfernen (vom toten Test erzeugt; binär, zählt nicht in LoC)

**Begründung gegen Minimal-Variante:** Issue verlangt explizit die Prüfung, ob `tripHero.ts`-Utils tot sind. Ergebnis: 2 von 4 öffentlichen Funktionen sind tot. Würde man sie + die 10 Tests + die roten E2E-Tests stehenlassen, bliebe ein roter Testlauf und Dead-Code zurück → Folge-Issue nötig. Pattern-konsistent mit #277/#323.

**Scope:** 6 Dateien (5 Code/Test + 1 Barrel), ~455 LoC-Delta (fast ausschließlich Löschungen). LoC-Limit auf 500 angehoben (`loc_limit_override`).

**Risiken:** Gering. Einziges Restrisiko: versehentliches Mit-Entfernen eines geteilten Helfers → durch obigen Trace ausgeschlossen; `tripHero.test.ts` (Rest-Tests) + `svelte-check`/Build sind das Sicherheitsnetz für die überlebenden Funktionen.

## Verifikations-Nachweis (Phase 1)

```
$ grep -rn "TripHero" frontend/src frontend/e2e
frontend/src/lib/components/trip-detail/index.ts:5: export { default as TripHero } from './TripHero.svelte';
# → einzige Referenz; kein <TripHero>-Tag, kein Import außerhalb des Barrels

$ grep -n "import" frontend/src/routes/trips/[id]/+page.svelte
import { TripHeader, TripTabs } from '$lib/components/trip-detail';  # KEIN TripHero
```
