# Context: rework-2845-hub-reiterleiste

## Request Summary
Issue #2845 (Epic #2345): Die Hub-Reiterleiste sieht auf Desktop (1440 px) bei Trip und Ortsvergleich verschieden aus
(Trip: inaktive Reiter dunkel, größer, Unterstrich-Linie; Vergleich: grau, 13 px, enger, keine Linie, ≈6 px höher).
Ziel: EINE gemeinsame Reiterleiste (Pendant-Verstoß gegen Trip/Vergleich-Code-Teilung). Nebenbefund: „Nächster Versand"
zeigt Trip `So 06:00 (CEST)`, Vergleich `So 06:00 (CET)` für denselben Sonntag 8.11.2026 (Winterzeit) — prüfen.

## Befund (Ursache Reiterleiste)
Beide nutzen bereits den geteilten Baustein `MTabBar`. Die Abweichung ist ein bewusst eingebauter Prop `size`:
`CompareTabs.svelte:679` ruft `<MTabBar … size="sm">`, `TripTabs.svelte:185` ohne (= `md`).
`MTabBar.svelte` Zeilen ~150-163 (`.mtabbar.sm`): padding 12px 16px, font 13px, inaktiv `--g-ink-3`, `border-bottom: none`;
`md`: padding 0.5rem 1rem, 0.875rem, inaktiv `--g-ink`, 1px Linie `--g-ink-faint`. Mobil (<900px) ist beides gleich.
Lösungsrichtung: `size`-Prop samt `.sm`-Regeln entfernen, Compare ruft ohne `size`. Eine Optik für beide (Trip-Optik = `md`;
Kontrast-Leitprinzip: hoher Kontrast gewinnt, `--g-ink-3` inaktiv wäre der schwächere Kontrast).

## Related Files
| File | Relevance |
|------|-----------|
| frontend/src/lib/components/mobile/MTabBar.svelte | Baustein; `size`-Prop + `.mtabbar.sm`-CSS = Ursache; Kopfkommentar erwähnt `sm` |
| frontend/src/lib/components/compare/CompareTabs.svelte | Zeile 679 `size="sm"`; Kommentar Z.673-678 |
| frontend/src/lib/components/trip-detail/TripTabs.svelte | Zeile 185, Referenz-Optik (`md`) |
| frontend/src/lib/components/mobile/__tests__/mtabbar_zaehler_neutral.test.ts | testet MTabBar/size-Annahmen (prüfen) |
| frontend/src/routes/compare/__tests__/issue_582_compare_design_fidelity.test.ts | Compare-Design-Test, evtl. an `sm` gekoppelt |
| frontend/src/lib/components/compare/__tests__/compare_mobile_shared_hub.test.ts | referenziert MTabBar |
| frontend/e2e/hub-tab-bar.spec.ts, issue-269-mobile-trip-tabs.spec.ts | E2E der Leiste |
| docs/specs/modules/mobile_tab_leisten_mtabbar.md | Ursprungsspec (Iteration 2 führte `size="sm"` ein) — Spec-Änderung nötig |
| docs/specs/modules/rework_2837_s1_hub_kopf.md | Vorgänger (AC-10 Zähler neutral) |

## Nebenbefund Zeitzone (CEST/CET)
Frontend (`shared/versand-tab/nextBriefingText.ts`) zeigt nur `tz_abbr` aus dem Backend. Quelle:
`src/services/next_briefing.py::_termin` (`vor_ort.tzname()`); Trip-Pfad `_trip_treffer`/`_trip_kandidat_utc`
(Zone via `services/trip_day.py::display_tz`/`anchor_tz`), Vergleich-Pfad `next_compare_briefing`.
Hypothese (unbestätigt, Aufgabe von /20-analyse): im Trip-Pfad wird das Kürzel mit der Zone/Offset eines anderen
Datums gebildet (z. B. `at = vor_ort.replace(...)` im Nicht-strict-Zweig, oder Etappen-Zone gegen Wegpunkt-Zone).
Tests: `tests/tdd/test_next_briefing.py` (Z.219/326/334 prüfen CEST/CET). Nutzersicht-Reproduktion mit echtem
Winterzeit-Termin nötig (erst rot nachweisen). Eventuell eigenes Issue, falls kein Frontend-Bezug.

## Existing Patterns
- Ein Code für Trip und Vergleich (`context="route"|"vergleich"`, Epic #2345); neuer Pendant-Code = Verstoß (#1170).
- Hoher Kontrast = Lesbarkeit (WCAG-AA, PO-bestätigt 2026-05-25).

## Dependencies
- Upstream: CSS-Variablen `--g-ink`, `--g-ink-3`, `--g-ink-faint`, `--g-accent`; Reiter-Daten aus `shared/subscriptionTabs.ts`.
- Downstream: Trip-Hub und Vergleichs-Hub (Desktop-Optik; Test-IDs `data-slot=segmented-*` bleiben).

## Existing Specs
- `docs/specs/modules/mobile_tab_leisten_mtabbar.md`, `docs/specs/modules/rework_2837_s1_hub_kopf.md`

## Risks & Considerations
- Tests/E2E, die die 13px/12-16px-Optik des Vergleichs fixieren, müssen mitgezogen werden.
- Höhe ändert sich beim Vergleich um ≈6 px: Layout-/Hub-Kopf-Paritätstests prüfen.
- Zeitzonen-Fix berührt Python-Core und braucht Test aus Nutzersicht.

## Analysis

### Type
Feature/Rework (Pendant-Verstoß beseitigen) — Teil A Reiterleiste; Teil B Zeitzonen-Kürzel separat prüfen.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| frontend/src/lib/components/mobile/MTabBar.svelte | MODIFY | `size`-Prop, `.sm`-CSS (Z.150-163), Kommentar Z.40 entfernen; eine Optik (= bisher `md`) |
| frontend/src/lib/components/compare/CompareTabs.svelte | MODIFY | `size="sm"` (Z.679) und Kommentar Z.673-678 entfernen |
| frontend/src/lib/components/mobile/__tests__/mtabbar_zaehler_neutral.test.ts | MODIFY | Test hängt an `size`-Varianten ('md'/'sm'); Zähler-Neutralität (AC-10 #2837 S1) muss in der Einheitsoptik erhalten bleiben |
| frontend/e2e/hub-tab-bar.spec.ts | MODIFY | Z.231-235: Vergleich erwartet 13px — künftig gleiche Erwartung wie Trip |
| docs/specs/modules/mobile_tab_leisten_mtabbar.md | MODIFY | Iteration "size=sm" zurücknehmen (Spec-Änderung, neues Spec-Dokument für #2845) |
| tests: issue_582_compare_design_fidelity, compare_mobile_shared_hub | CHECK | auf `sm`/13px-Kopplung prüfen |

### Scope Assessment
- Files: ~6-7, LoC ca. +30/-50, Risk: LOW (reines Frontend, Mobil bleibt gleich; Desktop-Vergleich wird ≈6 px höher, inaktive Reiter dunkler = besserer Kontrast).

### Technical Approach
`size`-Prop vollständig entfernen statt Variante umbiegen (ein Code, kein künftiger Rückfall). Trip-Optik (`md`) gewinnt: Leitprinzip hoher Kontrast; Zähler-Badge bleibt neutral (`--g-paper-deep`/`--g-ink-3`, Kontrast ≥4,5:1) und hängt schon jetzt nicht an `size`. E2E-Beweis aus Nutzersicht: Vergleich und Trip haben auf 1440 px gleiche Schriftgröße, Farbe inaktiver Reiter, Linie, Höhe.

### Nebenbefund Zeitzone (CEST/CET)
Code-Lektüre `next_briefing.py`: Kürzel kommt aus `vor_ort.tzname()` des Termin-Moments. Trip-Strict-Zweig rechnet über `trip_local_now(trip, moment)` korrekt pro Moment; Nicht-strict-Zweig nimmt `now` und setzt nur die Stunde (gleicher Tag, daher korrekt). Eine Ursache ist aus dem Code NICHT erkennbar, die Hypothese ist unbestätigt. Mögliche Auslöser: Etappe ohne Wegpunkte → `trip_tz`-Rückfall, oder Termin liegt in anderem Tag als `now` über Zeitumstellung (7.11. CEST → 8.11. CET). Empfehlung: aus #2845 herauslösen, eigenes Bug-Issue mit Nutzersicht-Reproduktion (Termin über Umstellung hinweg), erst rot nachweisen.

### Dependencies
Reiter-Daten `shared/subscriptionTabs.ts`; CSS-Variablen `--g-ink*`, `--g-accent`. Keine Backend-Abhängigkeit für Teil A.

### Open Questions
- [ ] Zeitzonen-Nebenbefund: eigenes Issue anlegen (Empfehlung) — kein PO-Entscheid nötig.
