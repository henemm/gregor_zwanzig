# Mini-Spec: Handy-Tabellengitter vom Ampel-Modus entkoppeln

- **Status:** Draft
- **created:** 2026-07-22
- **Workflow:** fix-mobile-grid-decouple-ampel (Bug fast-track)

## Was ändert sich

- `_render_mobile_compact_rows` (src/output/renderers/email/html.py) rendert die
  Stundentabelle in der Handy-Ansicht (`class="mobile-compact"`) **immer als
  bordierte `<table>` mit Gitterlinien** — auch im Roh-Modus (`use_friendly_format=
  false`), nicht mehr als gitterlosen `<pre>`-Monospace-Block.
- Breite Roh-Werte scrollen horizontal (`overflow-x:auto`), damit die Tabelle auf
  schmalen Screens nie über den Seitenrand läuft.

## Was darf sich NICHT ändern

- Desktop-Tabelle (unverändert bordiert).
- Ampel-Modus-Handy-Ansicht (zeigte schon die bordierte Tabelle — bleibt so).
- Inhaltliche Werte/Spalten, Datenlücken-Logik, has_gap.

## Acceptance Criteria

- **AC-1:** Given ein Trip im Roh-Modus (keine Ampel-Metrik friendly, `indicator_keys`
  leer), When das Briefing gerendert wird, Then enthält die Handy-Ansicht
  (`mobile-compact`) eine bordierte `<table>` mit Zell-Rahmenlinien und **keinen**
  `<pre>`-Block.
- **AC-2:** Given eine beliebige Stundentabelle in der Handy-Ansicht, When gerendert,
  Then ist sie in einen horizontal scrollbaren Container (`overflow-x:auto`) gewickelt,
  sodass breite Roh-Zahlen nicht den Seitenrand sprengen.
- **AC-3:** Given der Fix, When der Test läuft, Then prüft er die Handy-Ansicht eines
  Roh-Modus-Trips: bordierte Tabelle vorhanden, 0 `<pre>` — rot vor Fix, grün nach Fix.
- **AC-4:** Given bestehende Tests zur bisherigen `<pre>`-/Dual-Mode-Ausgabe
  (#305/#636), When sie durch die neue Grid-immer-Ausgabe rot werden, Then werden sie
  auf das neue Verhalten aktualisiert (nicht ersatzlos gelöscht), Kern-Schicht 100% grün.

## Manuelle Test-Schritte / Staging

- Staging-Test-Mail eines Roh-Modus-Trips: Handy-Breite (<600px) zeigt bordierte
  Tabelle mit Gitter, horizontal scrollbar; `briefing_mail_validator.py` Exit 0.
