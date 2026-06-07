---
entity_id: issue_634_treffer_quote_cleanup
type: module
created: 2026-06-07
updated: 2026-06-07
status: approved
version: "1.0"
tags: [cleanup, design-system, archive, frontend]
---

# Issue #634 — Cleanup: Reste der erfundenen Forecast-Treffer-Quote entfernen

## Approval

- [x] Approved (PO 'go', 2026-06-07)

## Purpose

Die letzten beiden Code-Reste der von Claude Design erfundenen Forecast-Treffer-Quote
(`accuracy_pct` / „Treffer Ø") entfernen. Backend-Berechnung (#606) ist wontfix, die
Archiv-Anzeige + `AccuracyBar`-Komponente sind bereits durch #611 entfernt. Übrig sind
nur ein Demo-Wert im Design-System-Showcase und ein obsoleter e2e-Test.

## Source

- **File:** `frontend/src/routes/_design-system/+page.svelte` (Demo-`Stat` „Treffer Ø", ~Z. 619)
- **File:** `frontend/e2e/issue-583-archiv-design-fidelity.spec.ts` (obsoleter e2e-Test)
- **Identifier:** Showcase-Snippet `statBody`; Test-Suite `Issue #583: Archiv-Screen 1:1`

## Estimated Scope

- **LoC:** ~5 produktiv (1 Zeile ersetzt) + ~91 Test-Zeilen gelöscht
- **Files:** 2 (1 editiert, 1 gelöscht)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/atoms/Stat.svelte` | Komponente | Generisches Atom — **bleibt unverändert**, real genutzt in Compare/TripHeader/Trips-Liste |
| `frontend/src/routes/archiv/+page.svelte` | Referenz | Aktueller Archiv-Stand (nur Name/Umfang/Datum) — definiert, was als „real existierendes Beispiel" gilt |

## Implementation Details

```
1. _design-system/+page.svelte (statBody-Snippet, "layout=inline / Archiv-Style"):
   - ENTFERNEN: <Stat layout="inline" label="Treffer Ø" tone="accent" value="87%" />
   - ERSETZEN durch ein neutrales, real im Archiv existierendes inline-Beispiel,
     z.B. <Stat layout="inline" label="Etappen" value="8" /> (Stage-Count ist ein
     reales Archiv-Datum) ODER die tone="accent"-Variante mit einem realen Label.
   - Ziel: Showcase zeigt weiterhin layout=inline inkl. tone="accent"-Variante,
     aber ohne die erfundene Metrik.

2. e2e/issue-583-archiv-design-fidelity.spec.ts:
   - Datei vollständig LÖSCHEN.
   - Begründung: AC-3 (AccuracyBar) + AC-4 (headline) testen seit #611 entfernte
     Features (seed liefert die Werte nicht mehr → Tests dauerhaft rot/tot).
     AC-1 (8 Demo-Trips) ist durch das Seed-Script abgedeckt, AC-5 (Suchfeld-Breite)
     durch frontend/src/lib/issue_480_archiv_suchfeld_breite.test.ts. Der getestete
     "1:1 nach screen-archive.jsx"-Design wurde durch #611 ersetzt → Spec obsolet.
```

## Expected Behavior

- **Input:** Aufruf der Design-System-Showcase-Seite `/_design-system`; Lauf der Test-Suite.
- **Output:** Showcase rendert den `Stat`-Block weiterhin (beide Layouts, inkl. `tone="accent"`),
  aber ohne „Treffer Ø". e2e-#583-Spec existiert nicht mehr.
- **Side effects:** Keine — keine Persistenz, kein Backend, keine geteilte Komponente verändert.

## Acceptance Criteria

- **AC-1:** Given die Design-System-Showcase-Seite `/_design-system` / When sie gerendert wird / Then erscheint im `Stat`-Showcase **kein** Label „Treffer Ø" und kein Wert „87%" mehr, während der `Stat`-Block (beide Layouts, inkl. einer `tone="accent"`-Variante) weiterhin sichtbar gerendert wird.
  - Test: Playwright gegen Staging `/_design-system` (eingeloggt) — `page.getByText('Treffer Ø')` nicht vorhanden; der Stat-Showcase-Panel („Stat · zwei Layouts") sichtbar mit mindestens einem accent-getönten Stat.

- **AC-2:** Given die `Stat`-Komponente wird an realen Stellen verwendet / When die Trips-Liste bzw. Trip-Detailseite gerendert wird / Then funktionieren diese unverändert (die generische Komponente wurde nicht beschädigt).
  - Test: Playwright gegen Staging — Trips-Liste `/trips` lädt und zeigt ihre Stat-Kennzahlen weiterhin korrekt an.

- **AC-3:** Given das Repository / When repo-weit in Prod-Code (`frontend/src`, `src`, `internal`, `api`, `cmd`) nach `accuracy` bzw. `Treffer Ø` gegrept wird / Then gibt es **keinen** Treffer mehr (ausgenommen unkritische historische Hinweis-Kommentare im seed-Script).
  - Test: `grep -rni "accuracy\|Treffer Ø" frontend/src src internal api cmd` (ohne Tests) liefert 0 funktionale Treffer; bestehende Test-Suite (`npm test`) bleibt grün.

## Known Limitations

- Der historische Hinweis-Kommentar in `scripts/seed_validator_archive.py` (dokumentiert die #611-Entfernung) bleibt absichtlich erhalten — er ist Doku, kein Feature-Rest.

## Changelog

- 2026-06-07: Initial spec created (#634)
