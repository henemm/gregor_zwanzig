---
entity_id: issue_1314_compare_warn_chip_dedup
type: bugfix
created: 2026-07-20
updated: 2026-08-02
status: draft
version: "1.1"
tags: [compare, official-alerts, email, html-renderer]
---

# Ortsvergleich-Matrix: doppelte "Hitze"-Chips visuell zusammenfassen (#1314, korrigiert #1451)

## Approval

- [x] Approved (PO „Freigabe", 2026-07-20)

## Purpose

In der HTML-Ortsvergleich-Mail zeigt die Matrix-Zeile "Amtliche Warnungen" pro
Ort für zwei extreme_heat-Warnungen mit unterschiedlichem Zeitfenster (oder
unterschiedlicher `region_label`/`dedup_id`/Quelle) zwei sichtbar **identische**
"Hitze"-Chips untereinander, weil das Kürzel-Mapping (`_warn_short`) für
`extreme_heat` kein unterscheidendes Detail (Stufe/Zeitraum) trägt. Der Fix
kollabiert im Matrix-Chip nur **identisch gerenderte** Chips **derselben
Region/Identität** (gleicher Kürzel-Text UND gleiche Stufe/Farbe UND gleiche
Regions-Identität) zu einem — der Pro-Ort-Streifen mit Detail-Informationen
bleibt unverändert. Issue #1314, Epic #1301 Scheibe B. **Korrektur #1451
(2026-08-02):** der ursprüngliche `visual_key` trug keine Regions-/Identitäts-
komponente, wodurch auch echte Warnungen VERSCHIEDENER Regionen (z. B.
Hitzewarnung Haute-Corse + Hitzewarnung Corse-du-Sud, beide Stufe 3) fälschlich
zu einem Chip kollabierten — eine Warnung wurde dem Nutzer unterschlagen. Der
`visual_key` trägt jetzt zusätzlich eine Regions-Identitätskomponente.

## Source

- **File:** `src/output/renderers/email/compare_html.py`
- **Identifier:** `def _render_warn_cell`

> **Schicht-Hinweis:** Betroffen ist ausschließlich Python-Core (`src/output/renderers/email/`,
> Compare-Mail-HTML-Renderer, konsumiert vom FastAPI-Core). Kein Go-API-, kein
> SvelteKit-Frontend-Code betroffen.

## Estimated Scope

- **LoC:** ~10-15 (Original #1314) + ~3-5 (#1451-Korrektur)
- **Files:** 1 (`src/output/renderers/email/compare_html.py`) + 1 Testdatei
  (`tests/tdd/test_mail_alert_dedup.py`, s. Test-Plan-Korrektur unten)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `dedupe_official_alerts` (`src/output/renderers/alert/official_alerts.py`) | function | Kanonische Datenebene-Dedup (Identität + Zeitraum); bleibt UNANGETASTET (#1245/#1134). Liefert die Identitäts-Präzedenz `dedup_id` > `region_label` > `label` (Zeile 294-339), die der #1451-Fix in `_render_warn_cell` spiegelt |
| `_dedup_alerts` (`src/output/renderers/email/compare_html.py`) | function | Dünner Wrapper um `dedupe_official_alerts` für Matrix-Chip UND Pro-Ort-Streifen; bleibt unangetastet |
| `_warn_short` (`src/output/renderers/email/compare_html.py`) | function | Liefert (Kürzel-Text, Severity) je Alert — Eingabe für die Chip-Kollaps-Logik |
| `_ALERT_LEVEL_CELL` (`src/output/renderers/email/compare_html.py`) | dict | Level → (bg, fg)-Farbe je Alert-Stufe — bestimmt zusammen mit Kürzel-Text und Regions-Identität die Chip-"Identität" |
| `render_official_alerts_html` (`src/output/renderers/alert/official_alerts.py`) | function | Pro-Ort-Streifen (Zeile ~675) — bleibt unverändert, zeigt weiterhin beide Warnungen mit Detail |
| `render_official_alerts_plain` (`src/output/renderers/alert/official_alerts.py`) | function | Klartext-Compare (`comparison.py`) — eine Zeile pro Alert mit Detail, kein komprimierter Chip, daher nicht betroffen |
| `OfficialAlert` (`src/services/official_alerts/models.py`) | dataclass | Testdaten-Konstruktion (`hazard`, `level`, `label`, `valid_from`, `valid_to`, `region_label`, `dedup_id`) — `dedup_id`/`region_label`/`label` sind jetzt auch Eingabe für den `region_ident`-Teil des `visual_key` |

## Implementation Details

`_render_warn_cell(alerts: list) -> str` iteriert bereits über die (datenebene-
deduplizierte) `alerts`-Liste und rendert pro Alert einen Chip-`<div>`. Der
#1314-Fix fügt eine visuelle Kollaps-Ebene NUR beim Chip-Aufbau ein: bevor ein
Chip angehängt wird, wird sein Rendering-Schlüssel gegen die Menge bereits
gerenderter Schlüssel geprüft. Ist der Schlüssel schon vorhanden, wird der
Chip übersprungen (Alert bleibt in `alerts`, beeinflusst also z. B. keine
Zähl-Logik anderswo — nur der Chip-String wird nicht erneut angehängt). Die
Reihenfolge des ersten Vorkommens bleibt erhalten (kein Sortieren/Gruppieren).

**#1451-Korrektur:** der Rendering-Schlüssel war ursprünglich
`(short_text, bg, fg)` — rein visuell, ohne Regions-/Identitätskomponente.
Dadurch kollabierten auch fachlich unterschiedliche Alerts (gleicher hazard,
gleiche Stufe, andere Region) fälschlich. Der Schlüssel wird um eine
**namespaced** Identitätskomponente erweitert, die dieselbe Präzedenz UND
dieselbe Namespace-Tag-Struktur spiegelt wie die kanonische Quelle
`dedupe_official_alerts` (Zeile 294-339):

```python
if alert.dedup_id:
    region_ident = ("id", alert.dedup_id)
elif alert.region_label:
    region_ident = ("region", alert.region_label)
else:
    region_ident = ("label", alert.label)
visual_key = (short, bg, fg, region_ident)
```

**Adversary-Fund (Runde 1, behoben):** eine erste Fassung nutzte eine flache
OR-Kette (`alert.dedup_id or alert.region_label or alert.label`) ohne
Namespace-Tag. Das reproduziert dieselbe Fehlerklasse wie F002 in
`dedupe_official_alerts`: ein zufällig gleicher String zwischen `region_label`
der einen Warnung und `label` der anderen Warnung (z. B. eine Massiv-Sperre,
deren `label` denselben Text trägt wie das `region_label` einer anderen
Warnung) kollabierte fälschlich zu einem Chip. Der Namespace-Tag
(`"id"`/`"region"`/`"label"`) verhindert das strukturell — Test
`test_ac8_region_label_collision_not_collapsed_in_overview_chip` beweist es.

Damit bleibt der ursprüngliche #1314-Zweck erhalten: zwei Perioden
**derselben** Region/Identität kollabieren weiterhin zu einem Chip, weil
`region_ident` bei beiden gleich ist (z. B. gleiches `dedup_id` einer
Massiv-Sperre, oder gleiches `region_label`/`label` bei zwei Zeitfenstern
derselben Region). Verschiedene Regionen (unterschiedlicher `region_ident`)
bleiben jetzt sichtbar getrennt, auch bei zufälliger String-Kollision
zwischen `region_label` und `label` verschiedener Warnungen.

Kein Eingriff in `_dedup_alerts`, `dedupe_official_alerts` oder `_warn_short`
— nur die Erweiterung des Schleifen-lokalen `visual_key` innerhalb von
`_render_warn_cell`. Kein neuer Modul-Zustand, keine neue Funktion nötig
(Set-basierte Dedup passt weiterhin in die bestehende `for alert in alerts:`-
Schleife).

**Geprüft und bestätigt (kein Bruch durch die Erweiterung):** die eskalierende
Massiv-Sperre (`dedup_id` konstant über Stufen, `region_label=None`, Test
`test_ac7_escalating_massif_closure_dedups_in_briefing`) wird bereits VOR
`_render_warn_cell` durch `_dedup_alerts`/`dedupe_official_alerts` auf einen
Repräsentanten reduziert — der `seen`-Mechanismus in `_render_warn_cell` sieht
dort praktisch nie zwei Elemente mit demselben `dedup_id`. Keine weiteren
Fundstellen mit demselben Muster im Code (der `visual_key`/`seen`-Mechanismus
existiert nur in `_render_warn_cell`).

## Expected Behavior

- **Input:** Liste bereits datenebene-deduplizierter `OfficialAlert`-Objekte
  für einen Ort (aus `_dedup_alerts(loc.official_alerts)`).
- **Output:** HTML-String mit einem `<div>`-Chip pro **visuell eindeutiger
  Kombination aus Kürzel-Text, Farbe (Stufe) UND Regions-Identität**
  (`dedup_id`/`region_label`/`label`, Präzedenz wie kanonische Quelle).
  Mehrfache Alerts derselben Region, die zum identischen Chip rendern (z. B.
  zwei extreme_heat gleicher Stufe mit unterschiedlichem Zeitfenster, gleiche
  Region), erzeugen genau einen Chip. Alerts unterschiedlicher Regionen
  bleiben getrennt, auch bei gleichem Kürzel-Text und gleicher Stufe.
- **Side effects:** Keine — reine Funktion, kein I/O, keine Mutation von
  `alerts`. Pro-Ort-Streifen (`render_official_alerts_html`) und Klartext-Pfad
  (`render_official_alerts_plain`) bleiben komplett unberührt, da beide eine
  eigene Render-Funktion mit Detail-Ausgabe sind und `_render_warn_cell` nicht
  aufrufen.

## Acceptance Criteria

- **AC-1:** Given zwei `OfficialAlert`-Objekte mit `hazard="extreme_heat"`,
  gleichem `level`, unterschiedlichem `(valid_from, valid_to)`, aber
  **derselben Regions-Identität** (gleiches `dedup_id`/`region_label`/`label`)
  für denselben Ort / When `_render_warn_cell` auf die (datenebene-
  deduplizierte) Liste beider Alerts angewendet wird / Then enthält der
  resultierende HTML-String genau EIN "Hitze"-Chip-`<div>`, nicht zwei.
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
  AC-1 (gleiche Stufe, unterschiedliches Zeitfenster, gleiche Region) / When
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

- **AC-6 (#1451, Kernfall der Korrektur):** Given zwei `OfficialAlert`-Objekte
  mit `hazard="extreme_heat"`, gleichem `level=3`, aber **unterschiedlicher
  Regions-Identität** (`region="Haute-Corse"` vs. `region="Corse-du-Sud"`)
  für denselben Ort / When `_render_warn_cell` (über `_render_overview_row`)
  auf die Liste beider Alerts angewendet wird / Then enthält der
  resultierende HTML-String genau ZWEI Chips, nicht einen — die Warnungen
  verschiedener Regionen dürfen nicht fälschlich zusammengefasst werden.
  - Test: bereits vorhanden und rot vor dem Fix —
    `tests/tdd/test_mail_alert_dedup.py::test_ac5_same_hazard_different_region_not_collapsed`
    (Zeile 185). GIVEN zwei Hitze-Alerts Stufe 3 aus verschiedenen Regionen,
    WHEN `_render_overview_row` gerendert wird, THEN `CHIP_SIG`-Vorkommen
    (`row.count(CHIP_SIG)`) == 2.

## Known Limitations

- **Korrigiert durch #1451 (2026-08-02):** Ursprünglich (#1314) basierte die
  Kollaps-Prüfung ausschließlich auf dem sichtbaren Chip-Inhalt (Kürzel-Text +
  Farbe), OHNE Regions-/Identitätskomponente — das führte dazu, dass auch
  fachlich unterschiedliche Alerts VERSCHIEDENER Regionen fälschlich zu einem
  Chip zusammengefasst wurden (eine Warnung wurde dem Nutzer unterschlagen).
  Das war ein unbeabsichtigter Bug, kein gewünschtes Verhalten. Seit dem
  #1451-Fix trägt der Rendering-Schlüssel zusätzlich eine Regions-Identität
  (`dedup_id`/`region_label`/`label`, Präzedenz wie `dedupe_official_alerts`):
  Kollaps erfolgt jetzt NUR bei gleicher Region/Identität UND gleichem
  Kürzel-Text+Stufe. Verschiedene Regionen bleiben immer sichtbar getrennt,
  auch bei identischem Kürzel-Text und identischer Stufe. Wer weitere Details
  (Zeitraum, Quelle) wissen will, findet sie im Pro-Ort-Streifen (unverändert,
  zeigt weiterhin alle Einzel-Warnungen mit Detail).
- `dedupe_official_alerts` und `_dedup_alerts` werden NICHT geändert — die
  Datenebene behält weiterhin beide Alerts als getrennte Objekte in `alerts`
  (Semantik #1245/#1134 bleibt vollständig erhalten). Der Fix wirkt
  ausschließlich auf der Render-/Anzeige-Ebene innerhalb von
  `_render_warn_cell`.
- Reihenfolge: Es wird nach erstem Vorkommen dedupliziert, nicht nach Stufe
  sortiert — ein späterer Alert mit niedrigerer Stufe, der denselben
  Kürzel-Text+Farbe+Regions-Identität wie ein früherer Alert trägt, würde
  ohnehin denselben Chip erzeugen und damit kollabieren (kein Sortier-
  Sonderfall nötig, da die Kollaps-Prüfung ausschließlich auf Gleichheit
  prüft).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Bugfix-Änderung innerhalb einer einzelnen bestehenden
  Render-Funktion (`_render_warn_cell`), ohne neue Schnittstellen, ohne neuen
  Modul-Zustand und ohne Eingriff in die kanonische Dedup-Quelle. Die
  Änderung wendet lediglich das bereits in ADR-0011 (Alert-Render-System —
  ein Backend-Renderer, Registry als Single Source) festgelegte Prinzip an:
  Render-Details bleiben lokal im jeweiligen Ausgabe-Layer gekapselt, ohne
  die geteilte Datenebene zu verändern. Die #1451-Korrektur ist ebenfalls
  keine neue architektonische Entscheidung, sondern eine Präzisierung des
  #1314-Rendering-Schlüssels, die die bereits in `dedupe_official_alerts`
  etablierte Identitäts-Präzedenz (`dedup_id` > `region_label` > `label`)
  konsequent auf die Chip-Render-Ebene spiegelt. Höchste bisher vergebene
  ADR-Nummer im Repository ist ADR-0041; eine neue ADR wäre hier nicht
  gerechtfertigt, da keine neue Leitentscheidung getroffen wird, sondern eine
  bestehende konsequent umgesetzt/korrigiert wird.

## Test Plan

### Automated Tests (TDD RED)

Kern-Schicht (deterministisch, netzfrei, keine Mocks — direkte
`OfficialAlert`-Objektkonstruktion und direkter Funktionsaufruf).
**Korrektur (2026-08-02):** die primär verwendete Kern-Testdatei für diesen
Bereich ist `tests/tdd/test_mail_alert_dedup.py`. Die im initialen
#1314-Plan genannte `tests/unit/test_compare_warn_chip_dedup.py` **existiert
entgegen der vorherigen Spec-Aussage** — sie wurde damals doch angelegt. Ihr
`test_ac1_two_extreme_heat_same_level_different_window_collapse_to_one_chip`
nutzte ursprünglich zwei VERSCHIEDENE Regionen ("Nord"/"Sued") und erwartete
für diesen Fall einen Chip — das kodierte exakt das #1451-Bug-Verhalten als
vermeintlich gewünscht. Fixture im Zuge des #1451-Fixes auf dieselbe Region
korrigiert (Spec-AC-1 verlangt seit v1.1 ausdrücklich dieselbe
Regions-Identität); der ursprüngliche Testzweck (Kollaps bei gleicher Region,
unterschiedlichem Zeitfenster) bleibt inhaltlich erhalten.

- [x] Test 1 (AC-1): GIVEN zwei `OfficialAlert(hazard="extreme_heat", level=3, ...)`
      mit unterschiedlichem `valid_from`/`valid_to`, gleicher Region WHEN
      `_render_warn_cell` aufgerufen wird THEN enthält das Ergebnis genau
      einen "Hitze"-Chip.
- [x] Test 2 (AC-2): GIVEN zwei `extreme_heat`-Alerts mit `level=2` und `level=3`
      WHEN `_render_warn_cell` aufgerufen wird THEN enthält das Ergebnis zwei
      Chips mit unterschiedlicher Hintergrundfarbe.
- [x] Test 3 (AC-3): GIVEN ein `extreme_heat`- und ein `access_ban`-Alert WHEN
      `_render_warn_cell` aufgerufen wird THEN enthält das Ergebnis je einen
      Chip mit Text "Hitze" und "Zugang".
- [x] Test 4 (AC-4): GIVEN dieselben zwei extreme_heat-Alerts wie Test 1 WHEN
      `render_official_alerts_html` (Pro-Ort-Streifen) auf dieselbe Liste
      angewendet wird THEN erscheinen beide Zeitfenster/Details im Ergebnis
      (kein Kollaps außerhalb von `_render_warn_cell`).
- [x] Test 5 (AC-5): GIVEN dieselben zwei extreme_heat-Alerts WHEN
      `render_official_alerts_plain` aufgerufen wird THEN erscheinen beide
      Zeilen mit Detail im Klartext-Ergebnis (Beleg der Nicht-Betroffenheit
      des Klartext-Pfads).
- [x] Test 6 (AC-6, #1451): GIVEN zwei Hitze-Alerts Stufe 3 aus verschiedenen
      Regionen (`region="Haute-Corse"` vs. `region="Corse-du-Sud"`) WHEN
      `_render_overview_row` (ruft `_render_warn_cell` intern auf) gerendert
      wird THEN enthält das Ergebnis 2 Chips (`CHIP_SIG`-Vorkommen == 2), nicht
      1 —
      `tests/tdd/test_mail_alert_dedup.py::test_ac5_same_hazard_different_region_not_collapsed`.
- [x] Test 7 (Adversary-Fund F002-Klasse, #1451): GIVEN zwei Alerts mit
      zufällig identischem String zwischen `region_label` der einen und
      `label` der anderen Warnung (z. B. Massiv-Sperre) WHEN
      `_render_warn_cell` gerendert wird THEN 2 Chips, nicht 1 (Namespace-Tag
      verhindert die Kollision) —
      `tests/tdd/test_mail_alert_dedup.py::test_ac8_region_label_collision_not_collapsed_in_overview_chip`.

## Changelog

- 2026-07-20: Initial spec created
- 2026-08-02: #1451 — visual_key um namespaced Regions-Identität erweitert
  (Adversary-Fund F002-Klasse in Runde 1 behoben), Known Limitations
  korrigiert (Cross-Region-Kollaps war unbeabsichtigter Bug), Testplan-Referenz
  auf `tests/unit/test_compare_warn_chip_dedup.py` korrigiert (Datei existierte
  entgegen ursprünglicher Spec-Aussage bereits, Fixture angepasst)
