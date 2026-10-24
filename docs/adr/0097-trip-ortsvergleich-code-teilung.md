# ADR-0097: Trip und Ortsvergleich teilen ihren Code — Compare-eigen nur Orte-Tab, transponierte Übersicht, Compare-Mail

- **Status:** Akzeptiert (rückwirkend dokumentiert 2026-10-21 — gelebte PO-Vorgabe, mehrfach bekräftigt; mechanisch abgesichert seit 2026-08-04, Commit `909fb394d`)
- **Datum:** 2026-10-21
- **Bezug:** CLAUDE.md §„Trip/Ortsvergleich-Code-Teilung", Anti-Pattern #1170, Pendant-Sperre `.claude/hooks/pendant_gate.py` (#1481 B, Spec `docs/specs/modules/feat_1481b_pendant_gate.md`), `docs/reference/gates_und_ratschen.md` §„Pendant-Sperre", Epic #2345 (Datenmodell-Konvergenz, Etappe P7, vormals #1230), ADR-0032 (Wizard-Abschaffung). Die Nummer ADR-0026 war 2026-07-16/17 von zwei Specs für dieses Thema vorläufig reserviert, das ADR wurde nie angelegt — das Thema ist hier aufgegangen.

## Kontext

Trip und Ortsvergleich sind fachlich verwandt: beide haben Wertebereiche, Layout, Versand und
Alarme. Sie wurden lange parallel gebaut. Die Pendant-Sperre hält beim Einführen fest: „Vier Paare
existieren heute doppelt, zwölf Paritäts-Tests bewachen Paare, die bereits doppelt entstanden sind"
(`pendant_gate.py`, Kopf-Docstring). Die Regel „möglichst viel Code teilen" stand bis 2026-08-04 nur
als Text in CLAUDE.md. #1170 ist das in CLAUDE.md benannte Anti-Pattern dafür.

## Entscheidung

1. **Geteilt ist EIN Code mit Parameter `context="route"|"vergleich"`:** Editor-Rahmen (Progressive
   Tabs, Lock-Engine, Speichern/Verwerfen), die Tab-Organismen Wertebereiche/Layout/Versand unter
   `frontend/src/lib/components/shared/`, das Muster Liste → Detail-Hub → Anlegen und die
   Datenmodell-Konvergenz (Epic #2345, P7).
2. **Anlegen folgt dem Trip-Muster** (ADR-0032): `/trips/new` und `/compare/new` sind
   Progressive-Tab-Anlege-Seiten aus geteilten Bausteinen.
3. **Compare-eigen dürfen nur sein:** Orte-Tab (statt Etappen), transponierte Übersicht (Orte =
   Spalten) und das Compare-Mail-Template.
4. **Default-Fehler:** Eine neue Compare-Komponente mit Trip-Pendant (oder umgekehrt) ist ein
   Verstoß. Ausnahme nur mit dokumentierter Begründung in der Spec.
5. **Durchsetzung:** Die Pendant-Sperre blockiert jeden Commit, der eine neu angelegte Datei in
   einem einseitigen Bereich enthält (`components/{compare,compare-new,trip-detail,trip-new}/**`,
   `src/output/renderers/**/{compare_*,trip_*}.py`), solange die Datei keine Kopfzeile
   `gz-eigenstaendig: <Grund>` trägt. Seit 2026-10-23 (#2346 S1) erkennt sie zusätzlich
   Namenspendants (`Compare*`/`Trip*`/neutral, `compare_*`/`trip_*`) in vier weiteren Wurzeln
   (u. a. `frontend/src/routes`, `src/services`, `internal/handler`); Bestandspaare stehen in der nur
   schrumpfenden Ausnahmeliste `BEKANNTE_PAARE`. Bei jeder Editor-/Detail-Arbeit ist „hätte das ein geteilter
   Baustein sein müssen?" ein expliziter Adversary-/Review-Punkt.

## Verworfene Alternativen

- **Zwei getrennte Code-Stränge mit Paritäts-Tests:** verworfen — die Tests bewachen nur bereits
  entstandene Doppel, sie verhindern keine neuen (Befund im Kopf von `pendant_gate.py`).
- **Reine Textregel ohne Mechanik:** bis 2026-08-04 gelebt, hat die Doppel nicht verhindert.

## Konsequenzen

- **Positiv:** Eine Änderung an Wertebereichen/Versand/Alarmen wirkt in beiden Flächen; weniger
  Drift zwischen Trip und Ortsvergleich.
- **Negativ / Preis:** Geteilte Bausteine brauchen den `context`-Parameter und werden komplexer.
  Die Sperre hat bewusste Grenzen: unpräfigierte Gegenstücke (z. B.
  `email/html.py`) sind unerkennbar (Namenspendants erst seit #2346 S1, Go nur unter `internal/handler`), die Begründung wird nur auf Länge geprüft, Bestand ist
  ausgenommen (`gates_und_ratschen.md` §„Pendant-Sperre").
- **Folgepflichten:** Die Sperre trägt Prüfdatum 2027-01-21 (verlängert 2026-10-23, vorher 2026-11-03; Regel-Budget, ADR-0100) — ohne
  belegten Fang Rückbau der Mechanik, nicht der Regel.
