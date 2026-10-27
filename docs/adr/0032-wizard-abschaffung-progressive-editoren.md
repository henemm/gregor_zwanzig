# ADR-0032: Multi-Step-Wizards abgeschafft — progressive Tab-Editoren mit Auto-Save

- **Status:** Akzeptiert (rückwirkend dokumentiert 2026-07-22 — PO-bekräftigt 2026-07-19, Issue #1343)
- **Datum:** 2026-07-22
- **Bezug:** #622 (TripNewEditor), Epic #1273/#1301 (Compare-Konsolidierung), CLAUDE.md §Trip/Ortsvergleich-Code-Teilung, `frontend/src/lib/components/shared/__tests__/legacy_wizard_removed.test.ts`
- **Ergänzt durch:** ADR-0097 (Trip/Ortsvergleich-Code-Teilung)

## Kontext

Trip-Anlage (Epic #136) und Compare-Anlage (Epic #438) waren als 4- bzw.
5-Schritt-Wizards mit Stepper gebaut. Zwei parallele Wizard-Systeme
duplizierten Editor-Logik, wichen vom Bearbeitungs-Pfad (Detail-Hub mit Tabs)
ab und erzeugten wiederholt Drift zwischen Anlegen und Bearbeiten.

## Entscheidung

Es gibt keine Multi-Step-Wizards mehr. Anlegen und Bearbeiten verwenden
dasselbe Muster: progressive Tab-Editoren mit Auto-Save aus geteilten
Bausteinen (`shared/`-Tab-Organismen, Parameter `context="route"|"vergleich"`).
`/trips/new` = `TripNewEditor` (#622), `/compare/new` = `CompareNewEditor`
(#1301 F2). `trip-wizard/`, `CompareWizard.svelte` und `CompareEditor.svelte`
wurden ersatzlos gelöscht; die Entfernung ist testgesichert
(`legacy_wizard_removed.test.ts`). **Es gibt keine offene Designfrage dazu —
nicht erneut vorlegen** (PO, 2026-07-19).

## Verworfene Alternativen

- **Wizards beibehalten und teilen** — Stepper-Semantik (linear, abschließend)
  passt nicht zum Auto-Save-Modell und bleibt ein zweites Editor-Paradigma.
- **Eigener Compare-Anlege-Editor** — verletzt die Code-Teilungs-Invariante
  (Anti-Pattern-Referenz #1170).

## Konsequenzen

- **Positiv:** Ein Editor-Paradigma, geteilte Bausteine, Anlegen = Bearbeiten.
- **Negativ / Preis:** Kein „Schritt-für-Schritt-geführt"-Gefühl für
  Erstnutzer; Freischalt-Logik (`tripNewLogic.ts`/`compareNewLogic.ts`) muss
  Progressive Disclosure leisten.
- **Folgepflichten:** Neue Anlege-/Editor-Flächen folgen dem geteilten Muster;
  eine neue Compare-Komponente mit Trip-Pendant (oder umgekehrt) ist ein
  Verstoß, Ausnahme nur mit dokumentierter Begründung in der Spec.

## Nachtrag 2026-10-21: Ist-Stand `/compare/new` und die verworfene Alternative

Die Entscheidung nennt `CompareNewEditor`, die verworfenen Alternativen nennen „Eigener
Compare-Anlege-Editor". Das liest sich widersprüchlich. Ist-Stand im Code:

- `frontend/src/routes/compare/new/+page.svelte` mountet
  `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` (Epic #1301 F2a, Spec
  `docs/specs/modules/feat_1301_f2a_compare_new_trip_pattern.md`).
- `CompareNewEditor` ist eine **eigene Anlege-Shell** je Domäne, als struktureller Spiegel von
  `trip-new/TripNewEditor.svelte` (#622). Die Inhalte kommen aus den **geteilten** Organismen
  unter `shared/` (`WeatherMetricsTab`, `CorridorEditor`/`CorridorEditorMobile`, `AlarmeTab`,
  `VersandTab`, `EditorStickyFooter`, `StandardwerteSpeichernKnopf`), die Freischalt-Logik aus
  `shared/anlegeLockEngine.ts` (#2277 S4).
- `CompareEditor.svelte` ist gelöscht (Commit `db0ca26b8`, 2026-07-19, #1301 F2b/S5);
  `CompareWizard.svelte` und `trip-wizard/` existieren nicht mehr, testgesichert durch
  `shared/__tests__/legacy_wizard_removed.test.ts`.
- Reste der Alt-Benennung bleiben: die Zustandsklasse `compare/compareWizardState.svelte.ts` und die
  Context-Schlüssel `compare-wizard-state`/`compare-wizard-profile`.

Lesart der verworfenen Alternative: verworfen ist ein Compare-Anlege-Editor mit **eigener**
Editor-Logik (wie der gelöschte `CompareEditor`), nicht eine dünne domänenspezifische Shell über
geteilten Bausteinen. Ob die zwei Shells `TripNewEditor`/`CompareNewEditor` selbst ein geteilter
Baustein sein müssten, bemisst sich nach ADR-0097 (Code-Teilung). Nebenbefund: Der Kopfkommentar
von `CompareNewEditor.svelte` begründet die eigene Shell mit „ADR-0029" — ADR-0029 ist die
Open-Meteo-Provider-Entscheidung, der Verweis ist falsch.
