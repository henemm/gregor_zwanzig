---
entity_id: fix_1425_s2b_markier_wirkung
type: feature
created: 2026-07-31
updated: 2026-07-31
status: draft
version: "1.0"
tags: [trip, corridor-editor, metric-catalog, wertebereiche, markieren]
---

# Trip-Wertebereiche: Markieren wirkt fuer 20 von 23 Groessen (#1425 Schritt 2, Teil 2, Scheibe A)

## Approval

- [x] Approved (PO, 2026-07-31)

## Purpose

Seit #1425 Teil 1 bietet der Trip-Reiter *Wertebereiche* 23 Wettergroessen mit
„Markieren"-Schalter an, aber im Trip-Briefing wirkt die Markierung nur fuer
die 5 alten Route-Keys (`wind_gust`, `temperature_min`, `temperature_max`,
`thunder_level`, `snow_line`). Die 17 mit Teil 1 dazugekommenen
Katalog-Groessen tragen Compare-Keys, die die Uebergangs-Zuordnung
`TRIP_CORRIDOR_METRIC_TO_COL_KEY` nicht kennt — der Schalter ist fuer sie ein
Bedienelement ohne Wirkung (die Fehlerklasse, wegen der #1384 neu geschnitten
wurde, Invariante 1 aus #1372). Diese Spec schliesst die Luecke fuer 15 der 17
neuen Groessen (alle ausser den zwei neuen Tages-Summen) durch eine
zweistufige Aufloesung ueber den zentralen Metrik-Katalog, blendet den
Schalter im Trip-Kontext fuer die drei Tages-Summen (kein 1:1-Stundenpendant)
ehrlich aus und laesst die Vergleichs-Mail byte-identisch.

Schritt 2, Teil 2, Scheibe A von Issue #1425 (Kind von Epic #1372, Dach-Epic
#1374). Scheibe B (Gewitter-Skalen-Migration) und Scheibe C (Banner-Text)
sind eigene Folge-Workflows.

## Source

- **File:** `src/output/renderers/email/html.py`
- **Identifier:** `TRIP_CORRIDOR_METRIC_TO_COL_KEY` (Zeile 563), Aufruf
  `mark_lookup_multi(corridors, TRIP_CORRIDOR_METRIC_TO_COL_KEY)` (Zeile 895)

> **Schicht-Hinweis:** Backend-Aenderung ist Python-Core
> (`src/output/renderers/email/html.py`, ggf. `compare_metric_catalog.py`
> als reine Lesequelle). Frontend-Aenderung ist SvelteKit
> (`frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte`
> und `CorridorEditorMobile.svelte`). Kein Go-API-Eingriff. `corridor_mark.py`
> (geteilter Baustein) und `compare_html.py` bleiben unveraendert.

## Estimated Scope

- **LoC:** ~120-220 (ueberwiegend Tests)
- **Files:** ~6
- **Effort:** medium (zwei Schichten — Backend-Aufloesung und
  Frontend-Schalter-Sichtbarkeit —, aber additiv, kein Schreibpfad-Umbau,
  keine Datenmigration)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `compare_metric_catalog.COMPARE_METRIC_CATALOG` (`src/output/renderers/compare_metric_catalog.py:64-145`) | data | Liefert `key` → `metric_id`/`aggregation` fuer die Katalog-Groessen — Quelle der zweistufigen Aufloesung |
| `metric_catalog.get_metric()` (`src/app/metric_catalog.py:558`) | function | `metric_id` → `MetricDefinition.col_key` — zweiter Schritt der Aufloesung |
| `corridor_mark.mark_lookup_multi()` / `is_marked_any()` (`src/output/renderers/email/corridor_mark.py`) | function | Geteilter Baustein Trip+Compare, bleibt unveraendert wiederverwendet — loest den Kollisionsfall (`temp`, `felt`) bereits |
| `compare_metric_ids.CORRIDOR_METRIC_TO_HOUR_KEY` (`src/output/renderers/compare_metric_ids.py:78-98`) | reference | Vorbild-Pattern und fachliche Begruendung der Summen-Ausnahme im Vergleich |
| `frontend/.../corridor-editor/compareMetricCatalogLoader.ts:130-154` | function | `buildRouteMetricDefsFromCatalog()` — Herkunft der `row.metric`-Werte (Katalog-`key`), die der Frontend-Filter fuer die Schalter-Sichtbarkeit auswertet |
| `tests/tdd/test_trip_mail_corridor_mark.py` | test | Bestehende Regressionsbasis fuer die 5 alten Route-Keys — muss unveraendert grün bleiben |
| `tests/tdd/test_issue_811_mode_matrix.py` + `briefing_mail_validator.py` | gate | Renderer-Commit-Gate #811 — `html.py` ist eine Mail-Inhalts-Datei, beide muessen frisch gruen sein |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/output/renderers/email/html.py` | MODIFY | Neue Hilfsfunktion baut die kombinierte `id_map` fuer `mark_lookup_multi()`: die 5 bestehenden Eintraege aus `TRIP_CORRIDOR_METRIC_TO_COL_KEY` (unveraendert, explizit) plus die per Katalog-Auflösung gewonnenen Eintraege fuer alle Katalog-Groessen mit `aggregation != "sum"`. Unbekannte/ nicht aufloesbare Katalog-Keys werden uebersprungen, kein Crash. |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte` | MODIFY | „Markieren"-Button (Zeile ~409) wird fuer die drei Summen-Metriken (`precipitation_sum`, `snow_new_sum_cm`, `sunny_hours_h`) nur ausgeblendet, wenn `context === 'route'` — im Vergleichs-Kontext unveraendert sichtbar |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditorMobile.svelte` | MODIFY | Dieselbe Ausblend-Logik fuer den mobilen „Markieren"-Button (Zeile ~384) |
| `tests/tdd/test_trip_mail_corridor_mark.py` | MODIFY | Erweitert um Faelle fuer einen Extremum- und einen Mittelwert-Vertreter der neuen Katalog-Groessen; bestehende 5er-Faelle bleiben als Regressionsschutz unveraendert |
| Frontend-Unit-Test zu `CorridorEditor.svelte`/`CorridorEditorMobile.svelte` (bestehende Testdatei erweitern oder neue Datei im selben Verzeichnis) | MODIFY/CREATE | Prueft: Summen-Schalter unsichtbar bei `context='route'`, sichtbar bei `context='vergleich'` |
| `tests/tdd/test_compare_mail_corridor_mark.py` (oder gleichwertiger bestehender Byte-Identitaets-Test) | MODIFY (falls noetig) / Nachweis | sha256-Vergleich HTML+Klartext der Vergleichs-Mail vor/nach der Aenderung — Regressionsschutz fuer den geteilten Baustein |

**Explizit NICHT geaendert:** `src/output/renderers/email/corridor_mark.py`
(geteilter Baustein, keine Verhaltensaenderung noetig), `compare_html.py`
(Vergleichs-Renderer), `compare_metric_ids.CORRIDOR_METRIC_TO_HOUR_KEY`
(eigener, unabhaengiger Vergleichs-Namensraum), die 5 expliziten Eintraege in
`TRIP_CORRIDOR_METRIC_TO_COL_KEY` (bleiben woertlich bestehen — Bestandsdaten
tragen diese Keys, sie sind keine Katalog-Keys und werden in dieser Scheibe
**nicht** durch die Katalog-Auflösung ersetzt).

## Implementation Details

**Zweistufige Auflösung (Backend, analog zum bereits vorhandenen, aber
nirgends verketteten Muster):**

1. Fuer jeden Eintrag in `COMPARE_METRIC_CATALOG` mit `aggregation != "sum"`:
   `key` (z.B. `cape_max_jkg`) → `metric_id` (`cape`) → `get_metric(metric_id).col_key`
   (`src/app/metric_catalog.py:558`). Schlaegt ein Schritt fehl (unbekannte
   `metric_id`, `KeyError`), wird der Eintrag still uebersprungen — analog zum
   bestehenden Verhalten von `mark_lookup_multi()`, das Metriken ausserhalb
   der `id_map` ebenfalls stillschweigend ignoriert.
2. Die so gewonnene Abbildung wird an die 5 bestehenden, expliziten Eintraege
   aus `TRIP_CORRIDOR_METRIC_TO_COL_KEY` angehaengt (nicht ersetzt) und
   zusammen als `id_map` an `mark_lookup_multi(corridors, id_map)` (Zeile 895)
   uebergeben.
3. Ausschluss der drei Tages-Summen (`precipitation_sum`, `snow_new_sum_cm`,
   `sunny_hours_h`) geschieht **strukturell** ueber den `aggregation == "sum"`-
   Filter aus dem Compare-Katalog, nicht als handgepflegte Liste:
   `snow_new_sum_cm` und `sunny_hours_h` sind Katalog-Eintraege mit
   `aggregation="sum"` und werden vom Filter automatisch ausgeschlossen.
   `precipitation_sum` ist kein Katalog-Key, sondern einer der 5 alten
   Route-Keys aus Schritt 1 — er war dort bereits bewusst NICHT in
   `TRIP_CORRIDOR_METRIC_TO_COL_KEY` aufgenommen (Kommentar `html.py:560-562`:
   „precipitation_sum fehlt bewusst — Tages-Summe hat keine 1:1-Stundenspalte").
   Diese Scheibe aendert daran nichts, macht die Begruendung aber konsistent
   mit den zwei neuen Summen-Ausnahmen.
4. Der bereits geloeste Kollisionsfall (`temperature_min`/`temperature_max`
   → `temp`, neu zusaetzlich `wind_chill_min_c`/`wind_chill_max_c` → `felt`)
   erfordert keine Aenderung an `mark_lookup_multi`/`is_marked_any` — beide
   sind bereits kollisionssicher (sammeln alle Korridore je Ziel-Spalte statt
   nur den letzten).

**Schalter-Sichtbarkeit (Frontend):**

5. `CorridorEditor.svelte`/`CorridorEditorMobile.svelte` blenden den
   „Markieren"-Button pro Zeile aus, wenn `context === 'route'` **und**
   `row.metric` zu den drei Summen-Metriken gehoert. Im Vergleichs-Kontext
   (`context === 'vergleich'`) bleibt der Schalter fuer dieselben Metriken
   unveraendert sichtbar, weil dort die Uebersichtszeile Tages-Aggregate
   korrekt markiert (`CORRIDOR_METRIC_TO_HOUR_KEY`-Pfad bleibt unberuehrt).
   Bereits gesetzte `mark=true`-Flags auf einem Summen-Korridor im Trip
   werden dadurch nicht geloescht (Read-Modify-Write-Prinzip, CLAUDE.md) —
   sie werden nur nicht mehr ueber den (dann unsichtbaren) Schalter bedienbar;
   in der Mail-Auswertung sind sie ohnehin wirkungslos, weil sie nicht im
   Ziel-`id_map` landen.

**Bewusst unveraendert:**
- Der vollstaendige Rueckbau der expliziten 5er-Zuordnung in
  `TRIP_CORRIDOR_METRIC_TO_COL_KEY` (Bestandsdaten tragen diese Route-Keys,
  keine Katalog-Keys) ist in dieser Scheibe **nicht** moeglich und **nicht**
  Ziel — er folgt erst mit der Gewitter-Skalen-Migration (Scheibe B), die
  `thunder_level` auf eine Katalog-vereinheitlichte Skala umstellt.
- Klartext-Teil der Mail, Telegram, SMS kennen weiterhin keine Auszeichnung
  (wie in Schritt 1 bewusst ausserhalb).

## Expected Behavior

- **Input:** Trip mit gespeicherten Korridoren (`trip.corridors`), darunter
  mindestens ein Korridor auf eine der 15 neuen, nicht-summen Katalog-Groessen
  mit `mark: true`.
- **Output:** Die Trip-Mail (Desktop-Tabelle, Mobile-Kompaktzeilen,
  Nacht-Tabelle) markiert die entsprechende Stundenzelle additiv
  (`corridor-mark`-Border), sobald der Stundenwert im eingestellten Bereich
  liegt — identisch zum bestehenden Verhalten der 5 alten Route-Keys. Fuer
  die drei Summen-Metriken bleibt die Markierung wirkungslos, und der
  Trip-Editor zeigt fuer sie keinen „Markieren"-Schalter mehr.
- **Side effects:** Keine Aenderung an Persistenz-Format, keine Migration
  bestehender Korridore. Die Vergleichs-Mail (HTML + Klartext) ist
  byte-identisch zum Stand vor dieser Aenderung.

## Acceptance Criteria

- **AC-1:** Given ein Trip-Korridor auf `cape_max_jkg` (Extremum-Vertreter,
  Bereich z.B. `[1000, null]`) mit `mark: true` und ein Stundenwert von
  1500 J/kg in der aktivierten CAPE-Spalte, When die Trip-Mail gerendert
  wird, Then traegt die entsprechende Stundenzelle die
  `corridor-mark`-Auszeichnung (Inline-Border), genau wie es das Audit im
  Kontext-Dokument fuer diese Kombination als fehlend belegt hat.
  - Test: `tests/tdd/test_trip_mail_corridor_mark.py` reproduziert exakt
    den Audit-Fall (Korridor + aktive Spalte + Stundenwert) und prueft das
    gerenderte HTML auf die Marken-Signatur der Zelle — kein
    Dateiinhalt-Check des Renderer-Codes.

- **AC-2:** Given ein Trip-Korridor auf `humidity_avg_pct` (Mittelwert-
  Vertreter) mit `mark: true` und ein Stundenwert innerhalb des Bereichs,
  When die Trip-Mail gerendert wird, Then traegt die entsprechende
  Stundenzelle dieselbe Auszeichnung wie bei den Extremum-Metriken.
  - Test: Analoger Fall wie AC-1, andere Metrik/Spalte (`humidity`).

- **AC-3:** Given ein Trip-Korridor auf `snow_line` (einer der 5 alten
  Route-Keys) mit `mark: true`, When die Trip-Mail gerendert wird, Then
  markiert er die `snow_limit`-Spalte exakt wie vor dieser Aenderung —
  keine Verhaltensaenderung fuer die 5 alten Route-Keys.
  - Test: Bestehender `snow_line`-Fall aus
    `tests/tdd/test_trip_mail_corridor_mark.py` laeuft unveraendert gruen
    (Regressionsschutz fuer den live gegangenen Schritt 1).

- **AC-4:** Given ein Trip-Korridor auf `sunny_hours_h` (Tages-Summen-
  Vertreter) mit `mark: true`, When die Trip-Mail gerendert wird, Then bleibt
  jede Stundenzelle ohne Auszeichnung, UND im Trip-Korridor-Editor
  (`context='route'`) ist fuer diese Zeile kein „Markieren"-Schalter
  sichtbar, WAEHREND derselbe Schalter im Ortsvergleich-Editor
  (`context='vergleich'`) fuer die entsprechende Groesse weiterhin sichtbar
  ist.
  - Test: Backend-Test prueft „keine Marken-Signatur trotz `mark: true`"
    fuer `sunny_hours_h`; Frontend-Test rendert `CorridorEditor.svelte`
    einmal mit `context='route'` und einmal mit `context='vergleich'` und
    prueft An-/Abwesenheit des Markieren-Buttons fuer dieselbe Metrik-Zeile.

- **AC-5:** Given ein Trip-Korridor traegt eine unbekannte oder nicht
  aufloesbare Metrik-ID (z.B. Freitext-Tippfehler), When die Trip-Mail
  gerendert wird, Then wird dieser Korridor bei der Markierung still
  uebersprungen — kein Absturz, kein Datenverlust der uebrigen Korridore
  oder anderer Trip-Daten.
  - Test: Fixture mit gemischter Korridor-Liste (eine unbekannte Metrik-ID
    plus mindestens ein gueltiger Korridor); Rendern schlaegt nicht fehl,
    der gueltige Korridor markiert weiterhin korrekt.

- **AC-6:** Given dieselben Korridor- und Wetterdaten wie vor dieser
  Aenderung, When die Vergleichs-Mail (`compare_html.py`) gerendert wird,
  Then ist ihr HTML- und Klartext-Teil byte-identisch (sha256) zum Stand vor
  dieser Aenderung — der geteilte Baustein `corridor_mark.py` bleibt fuer den
  Vergleichs-Pfad unveraendert wirksam.
  - Test: sha256-Vergleich der gerenderten Vergleichs-Mail vor/nach der
    Aenderung anhand eines fixen Korridor-/Wetter-Fixtures (wie bereits in
    Schritt 1 praktiziert).

## Known Limitations

- Klartext-Teil der Mail, Telegram und SMS kennen weiterhin keine
  Auszeichnung fuer Korridor-Markierungen (bewusst wie schon in Schritt 1).
- Die drei Tages-Summen (`precipitation_sum`, `snow_new_sum_cm`,
  `sunny_hours_h`) bleiben fachlich ohne Markier-Wirkung im Trip — es gibt im
  Trip-Briefing keine Uebersichts-Tabellenzeile fuer Tages-Aggregate, an die
  eine Markierung andocken koennte (anders als im Vergleich).
- Die explizite 5er-Zuordnung in `TRIP_CORRIDOR_METRIC_TO_COL_KEY` faellt in
  dieser Scheibe **nicht** weg — der vollstaendige Rueckbau auf eine rein
  katalogbasierte Auflösung ist erst nach der Gewitter-Skalen-Migration
  (Scheibe B) moeglich, weil `thunder_level` noch die alte,
  nicht-katalogkompatible Prozent-Definition traegt.
- Kein serverseitiges Enum fuer `Corridor.Metric` (Go,
  `internal/model/trip.go:72`) — eine ungueltige Metrik-ID wird weiterhin
  klaglos gespeichert (vorbestehender Zustand, AC-5 deckt nur die
  Render-Robustheit ab, nicht die Eingabevalidierung).

## Nicht Teil dieser Spec

- **Scheibe B — Gewitter-Skalen-Migration:** Vereinheitlichung von
  `thunder_level` (Prozent) auf die katalogseitige Ordinalskala inkl.
  Datenmigration bestehender Korridore. Erst danach kann die explizite
  5er-Zuordnung vollstaendig durch die katalogbasierte Auflösung ersetzt
  werden.
- **Scheibe C — Banner-Text:** Kuerzung der Legenden-/Banner-Beschriftung auf
  „im Bereich = markiert" im Korridor-Editor. PO-Entscheidung liegt bereits
  vor, ist aber ein eigener, unabhaengiger Frontend-Text-Workflow.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Es handelt sich um eine additive Erweiterung eines bereits
  etablierten Musters (zweistufige Katalog-Auflösung existiert im Vergleich
  bereits konzeptionell, wird hier fuer den Trip-Pfad verkettet). Es wird
  kein neuer Provider, Kanal, kein neues Datenmodell und keine neue
  Auth-/Persistenz-Entscheidung getroffen — die Filterlogik
  (`aggregation == "sum"`) ist Implementierungsdetail innerhalb des bereits
  entschiedenen "ein zentraler Katalog"-Ansatzes (vgl. ADR-freie Praxis in
  #1373 und Teil 1 dieses Issues, `docs/specs/modules/fix_1425_s2_corridor_pool.md`).

## Changelog

- 2026-07-31: Initial spec created
