---
entity_id: issue_1314_compare_warn_chip_dedup
type: bugfix
created: 2026-07-20
updated: 2026-07-20
status: draft
version: "1.0"
tags: [compare, official-alerts, email, html-renderer]
---

# Ortsvergleich-Matrix: doppelte "Hitze"-Chips visuell zusammenfassen (#1314)

## Approval

- [x] Approved (PO „Freigabe", 2026-07-20)

## Purpose

In der HTML-Ortsvergleich-Mail zeigt die Matrix-Zeile "Amtliche Warnungen" pro
Ort für zwei extreme_heat-Warnungen mit unterschiedlichem Zeitfenster (oder
unterschiedlicher `region_label`/`dedup_id`/Quelle) zwei sichtbar **identische**
"Hitze"-Chips untereinander, weil das Kürzel-Mapping (`_warn_short`) für
`extreme_heat` kein unterscheidendes Detail (Stufe/Zeitraum) trägt. Der Fix
kollabiert im Matrix-Chip nur **identisch gerenderte** Chips (gleicher
Kürzel-Text UND gleiche Stufe/Farbe) zu einem — der Pro-Ort-Streifen mit
Detail-Informationen bleibt unverändert. Issue #1314, Epic #1301 Scheibe B.

## Source

- **File:** `src/output/renderers/email/compare_html.py`
- **Identifier:** `def _render_warn_cell`

> **Schicht-Hinweis:** Betroffen ist ausschließlich Python-Core (`src/output/renderers/email/`,
> Compare-Mail-HTML-Renderer, konsumiert vom FastAPI-Core). Kein Go-API-, kein
> SvelteKit-Frontend-Code betroffen.

## Estimated Scope

- **LoC:** ~10-15
- **Files:** 1 (`src/output/renderers/email/compare_html.py`) + 1 neue Testdatei
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `dedupe_official_alerts` (`src/output/renderers/alert/official_alerts.py`) | function | Kanonische Datenebene-Dedup (Identität + Zeitraum); bleibt UNANGETASTET (#1245/#1134) |
| `_dedup_alerts` (`src/output/renderers/email/compare_html.py`) | function | Dünner Wrapper um `dedupe_official_alerts` für Matrix-Chip UND Pro-Ort-Streifen; bleibt unangetastet |
| `_warn_short` (`src/output/renderers/email/compare_html.py`) | function | Liefert (Kürzel-Text, Severity) je Alert — Eingabe für die neue Chip-Kollaps-Logik |
| `_ALERT_LEVEL_CELL` (`src/output/renderers/email/compare_html.py`) | dict | Level → (bg, fg)-Farbe je Alert-Stufe — bestimmt zusammen mit dem Kürzel-Text die Chip-"Identität" |
| `render_official_alerts_html` (`src/output/renderers/alert/official_alerts.py`) | function | Pro-Ort-Streifen (Zeile ~675) — bleibt unverändert, zeigt weiterhin beide Warnungen mit Detail |
| `render_official_alerts_plain` (`src/output/renderers/alert/official_alerts.py`) | function | Klartext-Compare (`comparison.py`) — eine Zeile pro Alert mit Detail, kein komprimierter Chip, daher nicht betroffen |
| `OfficialAlert` (`src/services/official_alerts/models.py`) | dataclass | Testdaten-Konstruktion (`hazard`, `level`, `label`, `valid_from`, `valid_to`, `region_label`, `dedup_id`) |

## Implementation Details

`_render_warn_cell(alerts: list) -> str` iteriert bereits über die (datenebene-
deduplizierte) `alerts`-Liste und rendert pro Alert einen Chip-`<div>`. Der Fix
fügt eine visuelle Kollaps-Ebene NUR beim Chip-Aufbau ein: bevor ein Chip
angehängt wird, wird sein Rendering-Schlüssel `(short_text, bg, fg)` — also
exakt das, was der Nutzer sieht (Kürzel + Farbe) — gegen die Menge bereits
gerenderter Schlüssel geprüft. Ist der Schlüssel schon vorhanden, wird der
Chip übersprungen (Alert bleibt in `alerts`, beeinflusst also z. B. keine
Zähl-Logik anderswo — nur der Chip-String wird nicht erneut angehängt). Die
Reihenfolge des ersten Vorkommens bleibt erhalten (kein Sortieren/Gruppieren).

Kein Eingriff in `_dedup_alerts`, `dedupe_official_alerts`, `_warn_short` oder
`_ALERT_LEVEL_CELL` — nur eine zusätzliche Schleifen-lokale Prüfung innerhalb
von `_render_warn_cell`. Kein neuer Modul-Zustand, keine neue Funktion nötig
(Set-basierte Dedup passt in die bestehende `for alert in alerts:`-Schleife).

## Expected Behavior

- **Input:** Liste bereits datenebene-deduplizierter `OfficialAlert`-Objekte
  für einen Ort (aus `_dedup_alerts(loc.official_alerts)`).
- **Output:** HTML-String mit einem `<div>`-Chip pro **visuell eindeutiger**
  Kombination aus Kürzel-Text und Farbe (Stufe). Mehrfache Alerts, die zum
  identischen Chip rendern (z. B. zwei extreme_heat gleicher Stufe mit
  unterschiedlichem Zeitfenster), erzeugen genau einen Chip.
- **Side effects:** Keine — reine Funktion, kein I/O, keine Mutation von
  `alerts`. Pro-Ort-Streifen (`render_official_alerts_html`) und Klartext-Pfad
  (`render_official_alerts_plain`) bleiben komplett unberührt, da beide eine
  eigene Render-Funktion mit Detail-Ausgabe sind und `_render_warn_cell` nicht
  aufrufen.

## Acceptance Criteria

- **AC-1:** Given zwei `OfficialAlert`-Objekte mit `hazard="extreme_heat"`,
  gleichem `level`, aber unterschiedlichem `(valid_from, valid_to)` für
  denselben Ort / When `_render_warn_cell` auf die (datenebene-deduplizierte)
  Liste beider Alerts angewendet wird / Then enthält der resultierende
  HTML-String genau EIN "Hitze"-Chip-`<div>`, nicht zwei.
  - Test: `_render_warn_cell([alert1, alert2])` aufrufen, Anzahl der
    `<div style="display:inline-block;...">Hitze</div>`-Vorkommen im
    Rückgabe-String zählen (`result.count("Hitze")` bzw. `<div`-Vorkommen mit
    Text "Hitze") — muss 1 sein.

- **AC-2 (Nicht-Regression):** Given zwei `extreme_heat`-Alerts mit
  UNTERSCHIEDLICHER Stufe (z. B. `level=2` und `level=3`) / When
  `_render_warn_cell` aufgerufen wird / Then bleiben BEIDE Chips sichtbar
  (unterschiedliche Hintergrundfarbe = unterschiedlicher visueller Inhalt,
  auch wenn der Kürzel-Text bei beiden "Hitze" lautet).
  - Test: Ergebnis enthält zwei `<div>`-Chips mit Text "Hitze", die
    unterschiedliche `background:`-Werte tragen (aus `_ALERT_LEVEL_CELL[2]`
    vs. `_ALERT_LEVEL_CELL[3]`).

- **AC-3 (Nicht-Regression):** Given zwei Alerts unterschiedlicher `hazard`
  (z. B. `extreme_heat` und `access_ban`) / When `_render_warn_cell` aufgerufen
  wird / Then bleiben beide Chips sichtbar ("Hitze" und "Zugang"), keine
  Kollaps-Logik greift zwischen unterschiedlichen Kürzel-Texten.
  - Test: Ergebnis enthält je einen Chip mit Text "Hitze" und "Zugang".

- **AC-4 (Nicht-Regression):** Given dieselben zwei extreme_heat-Alerts wie in
  AC-1 (gleiche Stufe, unterschiedliches Zeitfenster) / When
  `render_official_alerts_html` (Pro-Ort-Streifen) statt `_render_warn_cell`
  auf dieselbe Alert-Liste angewendet wird / Then zeigt der Pro-Ort-Streifen
  weiterhin BEIDE Warnungen mit ihrem jeweiligen Detail (Zeitraum/Quelle) —
  `dedupe_official_alerts`/`_dedup_alerts` bleiben unverändert, die
  Chip-Kollaps-Logik wirkt ausschließlich in `_render_warn_cell`.
  - Test: `render_official_alerts_html([(ort_name, [alert1, alert2])])`
    aufrufen, Ergebnis enthält beide unterscheidenden Detail-Strings
    (z. B. beide `valid_from`-Zeitfenster oder beide `region_label`-Werte).

- **AC-5 (Konsistenz-Check, dokumentiert):** Given der Klartext-Compare-Pfad
  (`comparison.py`, `render_official_alerts_plain`) rendert amtliche Warnungen
  als eine Zeile pro Alert mit ausgeschriebenem Detail (kein komprimierter
  Kürzel-Chip, keine Aufruf-Kette über `_render_warn_cell`) / When zwei
  extreme_heat-Alerts gleicher Stufe mit unterschiedlichem Zeitfenster in die
  Klartext-Rendering-Funktion gegeben werden / Then bleibt das Verhalten
  unverändert — beide Zeilen erscheinen mit Detail, da der Klartext-Pfad
  strukturell keine Kürzel-Kompression kennt und somit nicht vom Bug/Fix
  betroffen ist.
  - Test: kein Code-Änderungstest nötig (keine Codeänderung an
    `comparison.py`); ein einzelner bestehender oder neuer Regressionstest
    ruft `render_official_alerts_plain` mit den zwei Alerts auf und prüft,
    dass beide Zeilen im Ergebnis vorkommen — belegt die Nicht-Betroffenheit
    explizit statt sie nur zu behaupten.

## Known Limitations

- Die Kollaps-Prüfung basiert ausschließlich auf dem sichtbaren Chip-Inhalt
  (Kürzel-Text + Farbe). Zwei fachlich unterschiedliche Alerts, die zufällig
  zum selben Kürzel+Stufe rendern (z. B. zwei extreme_heat-Alerts gleicher
  Stufe aus unterschiedlichen Quellen), werden bewusst zu einem Chip
  zusammengefasst — das ist das gewünschte Verhalten dieses Fixes, nicht ein
  Seiteneffekt. Wer die Quelle wissen will, findet sie im Pro-Ort-Streifen
  (unverändert, zeigt weiterhin alle Einzel-Warnungen mit Detail).
- `dedupe_official_alerts` und `_dedup_alerts` werden NICHT geändert — die
  Datenebene behält weiterhin beide Alerts als getrennte Objekte in `alerts`
  (Semantik #1245/#1134 bleibt vollständig erhalten). Der Fix wirkt
  ausschließlich auf der Render-/Anzeige-Ebene innerhalb von
  `_render_warn_cell`.
- Reihenfolge: Es wird nach erstem Vorkommen dedupliziert, nicht nach Stufe
  sortiert — ein späterer Alert mit niedrigerer Stufe, der denselben
  Kürzel-Text+Farbe wie ein früherer Alert trägt, würde ohnehin denselben
  Chip erzeugen und damit kollabieren (kein Sortier-Sonderfall nötig, da die
  Kollaps-Prüfung ausschließlich auf Gleichheit prüft).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Bugfix-Änderung innerhalb einer einzelnen bestehenden
  Render-Funktion (`_render_warn_cell`), ohne neue Schnittstellen, ohne neuen
  Modul-Zustand und ohne Eingriff in die kanonische Dedup-Quelle. Die
  Änderung wendet lediglich das bereits in ADR-0011 (Alert-Render-System —
  ein Backend-Renderer, Registry als Single Source) festgelegte Prinzip an:
  Render-Details bleiben lokal im jeweiligen Ausgabe-Layer gekapselt, ohne
  die geteilte Datenebene zu verändern. Höchste bisher vergebene ADR-Nummer
  im Repository ist ADR-0028 (`docs/adr/0028-...md`); eine neue ADR-0029 wäre
  hier nicht gerechtfertigt, da keine neue architektonische Leitentscheidung
  getroffen wird, sondern eine bestehende konsequent umgesetzt wird.

## Test Plan

### Automated Tests (TDD RED)

Kern-Schicht (deterministisch, netzfrei, keine Mocks — direkte
`OfficialAlert`-Objektkonstruktion und direkter Funktionsaufruf).
Testdatei nach Verhalten benannt (nicht nach Issue-Nummer):
`tests/unit/test_compare_warn_chip_dedup.py`.

- [ ] Test 1 (AC-1): GIVEN zwei `OfficialAlert(hazard="extreme_heat", level=3, ...)`
      mit unterschiedlichem `valid_from`/`valid_to` WHEN `_render_warn_cell`
      aufgerufen wird THEN enthält das Ergebnis genau einen "Hitze"-Chip.
- [ ] Test 2 (AC-2): GIVEN zwei `extreme_heat`-Alerts mit `level=2` und `level=3`
      WHEN `_render_warn_cell` aufgerufen wird THEN enthält das Ergebnis zwei
      Chips mit unterschiedlicher Hintergrundfarbe.
- [ ] Test 3 (AC-3): GIVEN ein `extreme_heat`- und ein `access_ban`-Alert WHEN
      `_render_warn_cell` aufgerufen wird THEN enthält das Ergebnis je einen
      Chip mit Text "Hitze" und "Zugang".
- [ ] Test 4 (AC-4): GIVEN dieselben zwei extreme_heat-Alerts wie Test 1 WHEN
      `render_official_alerts_html` (Pro-Ort-Streifen) auf dieselbe Liste
      angewendet wird THEN erscheinen beide Zeitfenster/Details im Ergebnis
      (kein Kollaps außerhalb von `_render_warn_cell`).
- [ ] Test 5 (AC-5): GIVEN dieselben zwei extreme_heat-Alerts WHEN
      `render_official_alerts_plain` aufgerufen wird THEN erscheinen beide
      Zeilen mit Detail im Klartext-Ergebnis (Beleg der Nicht-Betroffenheit
      des Klartext-Pfads).

## Changelog

- 2026-07-20: Initial spec created
