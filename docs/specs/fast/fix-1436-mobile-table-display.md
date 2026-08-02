# Mini-Spec: fix-1436-mobile-table-display

## Was ändert sich

`frontend/src/lib/components/alerts-tab/AlertMetricLevelTable.svelte`, Media Query `@media (max-width: 899px)`:

- `table, thead { display: none; }` wird ersetzt durch:
  - `table { display: block; }`
  - `thead { display: none; }`
- `tbody { display: block; }` bleibt unverändert

Grund: `display: none` auf `<table>` nimmt den kompletten Teilbaum aus dem Layout — `tbody { display: block }` darunter kann das nicht zurückholen. Nur die Kopfzeile (`thead`) soll ausgeblendet werden; `AlertMetricLevelRow.svelte` liefert bereits eine eigene Block-Darstellung für die Zeilen, die dadurch erstmals sichtbar wird.

## Was sich nicht ändern darf

- Desktop-Darstellung (>899px) — unverändert, keine Regel in der Media Query betrifft sie
- `AlertMetricLevelRow.svelte` — bleibt unangetastet, ihre Mobil-Darstellung existiert bereits
- Kein neuer Compare-eigener oder Trip-eigener Sonderpfad — die Komponente ist geteilt (Touren + Ortsvergleich), der Fix gilt automatisch für beide

## Manuelle Test-Schritte

**Wichtig (aus Issue-Kommentar):** Ein reiner DOM-Sichtbarkeits-Check (Element existiert, ist einzeln nicht `display:none`) erkennt den Bug NICHT — der Vorfahre `<table>` versteckt den Teilbaum, einzelne Kind-Elemente melden sich trotzdem als vorhanden. Nur ein Screenshot oder eine Bounding-Box-Prüfung (`getBoundingClientRect()` > 0×0) zeigt den echten Zustand.

1. Staging, Viewport 390×844 (Handy-Breite ≤899px)
2. Trip-Reiter *Alarme* öffnen, mit aktiven Wettergrößen → Screenshot: Alarm-Zeilen sichtbar (nicht 0×0)
3. Ortsvergleich-Hub, Reiter *Alarme* öffnen → Screenshot: Alarm-Zeilen sichtbar
4. `/compare/new`, Reiter *Alarme* → Screenshot: Alarm-Zeilen sichtbar
5. Desktop-Breite (>899px), alle drei Kontexte → unverändert (Tabellen-Layout wie bisher)

## Inline-Test (wird während Implementierung geschrieben)

- [ ] Playwright/Component-Test: bei Viewport ≤899px hat mindestens eine Alarm-Zeile eine Bounding-Box > 0×0 (nicht nur DOM-Präsenz)
