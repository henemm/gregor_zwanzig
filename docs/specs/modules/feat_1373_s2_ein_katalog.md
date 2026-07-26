---
entity_id: feat_1373_s2_ein_katalog
type: module
created: 2026-07-26
updated: 2026-07-26
status: draft
version: "1.2"
tags: [compare, metric-catalog, drift-guard]
---

# S2 Scheibe A: Compare-Katalog an den zentralen Katalog binden + Drift-Guard

## Approval

- [ ] Approved

## Purpose

Der Ortsvergleich pflegt seine wählbaren Wettergrößen heute in einer eigenen,
parallelen Liste (`compare_metric_catalog.py`), die nichts vom zentralen
Wetterkatalog (`metric_catalog.py`) weiß. Beide Listen sind zufällig
deckungsgleich (26 Compare-Zeilen zu 24 zentralen wählbaren Größen), aber
nichts prüft das — eine neue zentrale Größe kann im Vergleich verschwinden,
ohne dass ein Test anschlägt.

**Diese Spec macht die zweite Liste NICHT verschwinden** — nachgemessen am
Code (2026-07-26) sind Labels, Wertebereiche und Bedienstruktur redaktionell
zu verschieden, um sie mechanisch abzuleiten (s. Offene Punkte). Sie bleibt
eine gepflegte Tabelle. **Scheibe A** verbindet stattdessen jeden der 26
Einträge nachweisbar mit dem zentralen Katalog (`metric_id` + `aggregation`
je Eintrag) und liefert die eigentliche Neuerung: einen Drift-Guard, der
künftig sichtbar fehlschlägt und die fehlende Größe benennt, wenn eine
wählbare zentrale Größe den Vergleich nicht erreicht — statt dass sie
unbemerkt abdriftet. Scheibe A ändert **nichts** an Persistenz, Migration
oder Frontend-Speicherpfaden — das ist Scheibe B, eine eigene Lieferung
(PO-Entscheidung 2026-07-26: 250-Zeilen-Deckel, sachlich trennbar).

Etappe S2 von Epic #1372 (Kind von Dach-Epic #1374), Ticket #1373.

## Source

- **File:** `src/output/renderers/compare_metric_catalog.py`
- **Identifier:** `COMPARE_METRIC_CATALOG`, `get_compare_metric_catalog()`
- **File:** `src/app/metric_catalog.py`
- **Identifier:** `MetricDefinition`, `get_all_metrics()`, `summary_fields`

## Estimated Scope

- **LoC:** ~150-190 Netto (Rechenweg unten). Deutlich unter dem alten
  Entwurf (dort ~210-315), weil keine Restrukturierung von
  `COMPARE_METRIC_CATALOG` mehr nötig ist — nur zwei Felder je Eintrag plus
  ein reiner Prüf-Test.
  - `compare_metric_catalog.py`: jeder der 26 Dict-Literale bekommt
    `"metric_id"` + `"aggregation"` ergänzt (Werte s. gemessene Zuordnung in
    `tests/tdd/test_compare_metric_catalog_endpoint.py::EXPECTED_METRIC_ORIGIN`,
    bereits vorhanden). Kein struktureller Umbau. ~50 Zeilen Diff
    (Docstring-Anpassung eingerechnet).
  - `tests/unit/test_compare_catalog_derives_from_central_catalog.py`: diese
    Datei existiert bereits aus einer vorherigen RED-Runde für den
    **verworfenen** Ableitungs-Entwurf — sie testet `COMPARE_METRIC_OVERLAY`
    und `build_compare_metric_catalog()`, die es in diesem Entwurf nicht mehr
    gibt. Der Generierungs-Test (`test_new_central_metric_with_overlay_appears_in_derived_catalog`,
    ~85 Zeilen) entfällt ersatzlos; die drei bestehenden Guard-Tests
    (Richtung a/b + Wirkungsnachweis) bleiben, da sie bereits gegen
    `get_compare_metric_catalog()` prüfen, nicht gegen den Generierungsweg.
    Neu kommen hinzu: dritte Prüfung (`aggregation` ⊆ `summary_fields`, wo
    vorhanden) + Ausnahmeliste (#1391/#1392) + Schrumpf-Test der
    Ausnahmeliste. ~90-110 Zeilen neu. Diese Datei ist Testpflege, nicht
    Teil dieser Spec-Umsetzung selbst, aber Teil der ehrlichen Umfangsschätzung.
  - `tests/tdd/test_compare_metric_catalog_endpoint.py`: bereits vollständig
    auf dieses Design vorbereitet (`EXPECTED_METRIC_ORIGIN`-Fixture inkl. der
    vier Ausnahmen, gemessen 2026-07-26, plus drei Tests AC-6). Voraussichtlich
    **0 Zeilen** Änderung.
  - `frontend/src/lib/types.ts`: `CompareMetricCatalogEntry` um zwei optionale
    Felder (`metric_id?`, `aggregation?`) ergänzen. ~2-4 Zeilen.
  - `frontend/.../compareMetricSelection.ts`: bedingtes Durchreichen (nur
    ergänzen, wenn im Endpoint-Eintrag vorhanden — sonst bricht der
    bestehende strikte `deepEqual`-Vergleich aus #1350). ~8-15 Zeilen.
  - `frontend/.../__tests__/compareMetricSelection.test.ts`: bereits
    vollständig vorbereitet (Fixture + drei Tests für AC-5/AC-6, s. u.).
    Voraussichtlich **0 Zeilen** Änderung.
  - `api/routers/compare.py`: **0 Zeilen** — der Endpoint reicht
    `get_compare_metric_catalog()` bereits 1:1 durch (`{"metrics": ...}`,
    kein Feldfilter), geprüft am Code.
- **Files:** ~4 mit tatsächlicher Codeänderung
  (`compare_metric_catalog.py`, `test_compare_catalog_derives_from_central_catalog.py`,
  `types.ts`, `compareMetricSelection.ts`); 2 weitere nur zur Verifikation
  gelesen, keine Änderung erwartet.
- **Effort:** small-medium (die Datenanreicherung ist trivial, der
  Drift-Guard mit Ausnahmeliste ist der eigentliche Kern der Lieferung).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/metric_catalog.py` | READ-ONLY | Quelle: `get_all_metrics()` (24 wählbare Größen) + `summary_fields` je Größe |
| `src/output/renderers/compare_metric_catalog.py` | MODIFY | Jeder der 26 Einträge bekommt `metric_id`/`aggregation` ergänzt — Tabelle bleibt sonst unverändert kuratiert |
| `api/routers/compare.py` | CHECK | `GET /api/compare/metrics` liefert die neuen Felder automatisch mit (reines Durchreichen, geprüft, keine Codeänderung erwartet) |
| `tests/tdd/test_compare_metric_catalog_endpoint.py` | CHECK | bereits auf dieses Design vorbereitet (Herkunfts-Fixture + AC-6-Tests) — keine Änderung erwartet |
| `tests/unit/test_compare_metric_catalog_consistency.py` | CHECK | bestehende Katalog↔Resolver↔CV2-Guards bleiben unverändert (S3-Zuständigkeit), müssen weiterhin grün sein |
| `tests/unit/test_compare_catalog_derives_from_central_catalog.py` | MODIFY | Umschreiben: Generierungs-Test entfernen (verworfener Mechanismus), dritte Prüfung + Ausnahmeliste + deren Schrumpf-Test ergänzen |
| `frontend/src/lib/types.ts` | MODIFY | `CompareMetricCatalogEntry`: `metric_id?`, `aggregation?` ergänzen (optional, `key` bleibt) |
| `frontend/src/lib/components/shared/weather-metrics-tab/compareMetricSelection.ts` | MODIFY | Bedingtes Durchreichen von `metric_id`/`aggregation` |
| `frontend/.../__tests__/compareMetricSelection.test.ts` | CHECK | bereits vollständig vorbereitet (Fixture + Tests für bedingtes Durchreichen) — keine Änderung erwartet |

**Nicht Teil dieser Lieferung** (Scheibe B, s. eigener Abschnitt unten):
`src/output/renderers/compare_metric_ids.py`, `scripts/migrate_1373_*`, alle
vier Frontend-Speicher-Ergänzungsstellen, `compareEditorLoad.ts`. Ebenfalls
unangetastet: der Renderer (`compare_html.py`, S3/S5) und `compare_hourly_metric_ids.py`.

## Implementation Details

```
1. KATALOG BLEIBT KURATIERT, BEKOMMT HERKUNFTSFELDER

   COMPARE_METRIC_CATALOG bleibt eine gepflegte Liste von 26 Dict-Literalen
   -- sie wird nicht generiert. Jeder Eintrag bekommt zwei zusaetzliche
   Schluessel: "metric_id" (die zentrale Katalog-ID, z. B. "temperature")
   und "aggregation" (die Auswertung, die dieser Eintrag zeigt, z. B.
   "max"). Die Zuordnung ist bereits gemessen und in
   tests/tdd/test_compare_metric_catalog_endpoint.py::EXPECTED_METRIC_ORIGIN
   festgehalten -- fuer 22 der 26 Keys ist der Compare-Key woertlich (oder
   nahezu woertlich) der Summary-Feldname der zentralen Groesse, fuer vier
   Keys (s. Punkt 4) existiert diese Herkunftsangabe ohne mechanischen
   Beleg im zentralen Katalog.

2. ENDPOINT-FELDER (GET /api/compare/metrics)

   Keine Code-Aenderung in api/routers/compare.py -- der Endpoint reicht
   get_compare_metric_catalog() bereits 1:1 durch (get_compare_metrics()
   liefert {"metrics": get_compare_metric_catalog()}, kein Feldfilter,
   geprueft am Code). key bleibt unveraendert erhalten
   (Rueckwaertskompatibilitaet -- das Frontend nutzt ihn weiterhin fuer
   Auswahl/Snapshot, Scheibe B).

3. DRIFT-GUARD (tests/unit/test_compare_catalog_derives_from_central_catalog.py)

   Drei Pruefungen statt einer:
   a) Jede waehlbare zentrale Groesse (metric_catalog.get_all_metrics())
      hat mindestens einen Compare-Eintrag mit passendem metric_id.
   b) Jeder Compare-Eintrag traegt ein metric_id, das im zentralen Katalog
      existiert (keine verwaisten Zeilen nach einer zentralen Umbenennung).
   c) Wo die zentrale Groesse summary_fields traegt, ist die im
      Compare-Eintrag angegebene aggregation eine davon (Ausnahmen s.
      Punkt 4).
   Plus Wirkungsnachweis: der Guard wird kuenstlich mit einer um eine
   Groesse reduzierten Kopie geprueft und muss dann tatsaechlich
   anschlagen (Vorbild: test_compare_metric_catalog_consistency.py) -- ein
   Guard ohne Wirkungsnachweis ist nur zufaellig gruen.

4. AUSNAHMELISTE (klein, benannt, schrumpft nur)

   Pruefung 3c kann heute fuer vier Keys nicht erfuellt werden, weil die
   zentrale Groesse strukturell kein summary_fields traegt:
     cloud_low_avg_pct, cloud_mid_avg_pct, cloud_high_avg_pct
       -- kein Tages-Auswertungsfeld auf SegmentWeatherSummary (#1392)
     snowfall_limit_m
       -- Feld existiert und wird befuellt, aber summary_fields fehlt (#1391,
          echter Bug mit Trip-Alarm-Wirkung)
   Diese vier stehen als benannte Ausnahmeliste IM TEST, je mit
   Issue-Verweis und einem Satz Begruendung. Regel: die Liste darf nur
   schrumpfen (wenn #1391/#1392 behoben werden), nie wachsen -- ein neuer
   Eintrag ist ein Befund, kein Workaround. Ein zusaetzlicher Test prueft,
   dass keiner der vier Ausnahme-Keys inzwischen doch summary_fields traegt
   (verhindert, dass die Ausnahme zur Dauereinrichtung wird).

5. FRONTEND: BEDINGTES DURCHREICHEN

   compareMetricSelection.ts::toCompareSelectionEntries() reicht
   metric_id/aggregation NUR durch, wenn der Endpoint-Eintrag sie traegt --
   kein Erfinden leerer/undefined-Schluessel. Grund: der bestehende
   strikte deepEqual-Vergleich aus #1350 (AC-2) wuerde sonst brechen. Keine
   neue UI, keine neue Auswahl-Logik -- die Felder liegen bereit, damit
   Scheibe B sie nutzen kann.

6. KEIN UMBAU

   compare_metric_ids.py (FRONTEND_TO_RENDERER_METRIC_ID,
   RENDERER_TO_TRIP_METRIC_ID), der Renderer (CV2_METRICS/HOUR_METRICS in
   compare_html.py) und die Persistenz (display_config.active_metrics)
   bleiben in dieser Lieferung unangetastet -- S3/S5/Scheibe B.
```

## Scheibe B (Folgelieferung, nicht in dieser Spec)

**Geliefert:** `4d8fafae` — eigene Spec
`docs/specs/modules/feat_1373_s2b_metrik_speicherformat.md` (12 AC). Die
Skizze unten ist die Vorarbeit dieser Spec und bleibt zur Entscheidungs-
Nachvollziehbarkeit erhalten; für den aktuellen Stand gilt die verlinkte
Scheibe-B-Spec.

Ausgegliedert per PO-Entscheidung 2026-07-26 (250-Zeilen-Deckel, sachlich
trennbar von Scheibe A). Damit die nächste Sitzung nicht neu recherchieren
muss, verdichtet hier festgehalten:

- **Persistenzformat.** `display_config.active_metrics` wechselt von
  `list[str]` auf `list[{"metric_id": str, "aggregation": str}]`. Lesen:
  Altformat (String) bleibt akzeptiert, wird auf denselben Compare-Key
  zurückgeführt wie heute; Neuformat wird über `(metric_id, aggregation)`
  aufgelöst — Rückgriff auf dieselbe Zuordnungstabelle, die Scheibe A in
  `compare_metric_catalog.py` bereits aufbaut (keine fünfte
  Übersetzungstabelle). Schreiben: NUR das Neuformat wird geschrieben, das
  Altformat wird ab Scheibe B nie mehr erzeugt (nur noch gelesen, für
  Bestandsdaten vor der Migration bzw. vor dem nächsten Speichern). Betrifft
  `src/output/renderers/compare_metric_ids.py` (`resolve_enabled_metrics()`).
- **Migration.** `scripts/migrate_1373_compare_active_metrics_format.py`,
  Vorbild `migrate_1191_compare_active_metrics.py`/
  `migrate_1360_drop_compare_top_n.py` (Dry-Run-Default, `--execute`,
  `--root`, tar.gz-Backup, Plan→Apply, Idempotenz, Read-Modify-Write-Merge,
  nur `kind=vergleich`). Verifikationsanker (gemessen 2026-07-26): 3
  Produktions-Vergleiche mit sowohl `temp_max_c` als auch `temp_min_c`, 1
  mit `wind_chill_min_c` — die Migration darf keinen davon verlieren.
- **Vier Frontend-Speicher-Ergänzungsstellen.** `WeatherMetricsSnapshot`/
  `hydrateWeatherMetricsFromPreset()`/`norm()` (weatherMetricsCompareSave.ts),
  `currentWetterMetrikenSnapshot()` (CompareTabs.svelte),
  `buildHubPutPayload()` (compareHubWizardBridge.ts),
  `buildComparePresetSavePayload()`/`buildNewComparePresetPayload()`
  (compareEditorSave.ts). Entscheidung: Snapshot-/Diff-Ebene bleibt bei
  `activeMetricKeys: string[]` (UI unverändert) — nur die beiden
  Payload-Bau-Funktionen übersetzen beim Schreiben ins Neuformat, das hält
  den Dirty-/Diff-Vergleich (`JSON.stringify`) unverändert funktionsfähig und
  begrenzt die Änderungsfläche. `rehydrateActiveMetrics()`
  (compareEditorLoad.ts) muss künftig beide Formate lesen und auf
  `string[]` zurückführen.
- **Ursprüngliche AC-4/AC-5/AC-10** (Neuformat wird geschrieben, Migration
  idempotent/verlustfrei, alle vier Speicherpfade wirksam) gehören in die
  Scheibe-B-Spec, nicht hierher.

## Expected Behavior

- **Input:** Zentraler Wetterkatalog (`metric_catalog.py`) bleibt Quelle der
  Wahrheit für Größen; ein Nutzer wählt im Ortsvergleich weiterhin einzelne
  Metrik-Zeilen (inkl. „Temperatur max"/„Temperatur min" getrennt) — an der
  Bedienoberfläche ändert sich in dieser Lieferung nichts.
- **Output:** `GET /api/compare/metrics` liefert weiterhin 26 Einträge, jetzt
  zusätzlich mit `metric_id` und `aggregation`. `display_config.active_metrics`
  bleibt in dieser Lieferung unverändert im bisherigen String-Format — Lesen,
  Schreiben und Migration sind Scheibe B. Die Mail (HTML/Klartext/Telegram/
  SMS) zeigt für dieselbe Auswahl exakt dieselben Zeilen wie vor der
  Umstellung, da an der Katalog-Tabelle nur zwei zusätzliche Felder ergänzt
  werden, nichts an Reihenfolge, Label oder Wert.
- **Side effects:** Eine neue zentrale Katalog-Größe ohne passenden
  Compare-Eintrag lässt künftig einen Test sichtbar fehlschlagen und nennt
  die fehlende Größe im Fehlertext, statt kommentarlos zu verschwinden.

## Acceptance Criteria

- **AC-1:** Given der zentrale Wetterkatalog wird um eine neue wählbare
  Größe erweitert, ohne dass der Ortsvergleich sie erreicht / When die
  Test-Suite läuft / Then schlägt mindestens ein Test sichtbar fehl und
  benennt die fehlende Größe im Fehlertext, statt sie kommentarlos aus dem
  Vergleich verschwinden zu lassen.
  - Test: der Drift-Guard, künstlich mit einer um eine Größe reduzierten
    Kopie der Compare-Seite geprüft (Wirkungsnachweis) — der Fehlertext
    muss die entfernte Größe nennen.

- **AC-2:** Given ein Nutzer öffnet die Metrik-Auswahl im Ortsvergleich /
  When er die Liste durchsieht / Then findet er weiterhin „Temperatur max"
  und „Temperatur min" als zwei getrennte, einzeln wählbare Einträge, ebenso
  „Gefühlte Temperatur max" und „Gefühlte Temperatur min".
  - Test: Kern-Test gegen `GET /api/compare/metrics` — beide Paare als
    eigenständige Einträge mit unterschiedlichem `key` vorhanden.

- **AC-3:** Given ein bestehender Vergleich mit einer bereits gespeicherten,
  nicht-leeren Metrik-Auswahl / When vor und nach der Umstellung je eine
  Mail erzeugt wird / Then zeigen beide Mails dieselben Zeilen in derselben
  Reihenfolge mit denselben Werten — in HTML, Klartext, Telegram und SMS
  gleichermaßen.
  - Test: echte Staging-Mail vor/nach über das Test-Postfach, ausgewertete
    Struktur verglichen (nicht byte-genau, Wetterwerte ändern sich).

- **AC-4:** Given ein Vergleich, der noch nie eine Metrik-Auswahl gespeichert
  hat / When eine Mail für ihn erzeugt wird / Then zeigt die
  Übersichtstabelle weiterhin alle Metriken, wie vor dieser Umstellung.
  - Test: Kern-Test der Auflösungsfunktion mit fehlendem Feld (kein
    `active_metrics`-Schlüssel im Preset) — reiner Bestandsschutz, unberührt
    von der Katalog-Erweiterung.

- **AC-5:** Given die Metrik-Auswahlliste im Ortsvergleich-Editor wird
  geladen / When die Antwort des Katalog-Endpunkts ausgewertet wird / Then
  trägt jeder Eintrag neben dem bisherigen Kurznamen auch die zugehörige
  Wettergröße und die Auswertung als eigene, auslesbare Angaben.
  - Test: Kern-Test (Python) gegen `GET /api/compare/metrics` — `metric_id`
    und `aggregation` für alle 26 Einträge vorhanden und plausibel (z. B.
    `temp_max_c` → `metric_id="temperature"`, `aggregation="max"`).
    Zusätzlich Kern-Test (Node) für `compareMetricSelection.ts` — beide
    Felder werden aus der Endpoint-Antwort unverändert durchgereicht, wenn
    vorhanden, und nicht erfunden, wenn sie fehlen.

## Known Limitations

- Der Renderer selbst (`CV2_METRICS`/`HOUR_METRICS` in `compare_html.py`)
  bleibt unverändert — er liest weiterhin über
  `FRONTEND_TO_RENDERER_METRIC_ID`/`resolve_enabled_metrics()`. Sein Umbau
  ist S3 (#1366/#1378) bzw. S5 (#1377).
- Die Auswertung (min/max/avg) bleibt weiterhin NICHT wählbar — S4 (#1357).
  „Temperatur max"/„Temperatur min" bleiben zwei feste, vorgegebene
  Einträge, keine wählbare Kombination aus einer Größe.
- #1384 (Trip-Wertebereiche-Pool 5-von-24) ist NICHT Teil dieser Spec — die
  Begrenzung existiert ausschließlich im Trip-Zweig des Korridor-Editors und
  wandert zu #1371 in S6.
- `hourly_metrics` (Stundenverlauf-Auswahl) ist ein eigenständiges Vokabular
  (`compare_hourly_metric_ids.py`) und wird von dieser Spec NICHT verändert
  — weder Format noch Drift-Guard.
- **Persistenzformat, Migration und Frontend-Speicherpfade sind Scheibe B**
  (eigener Abschnitt oben) — nicht Teil dieser Lieferung.
- **#1392 (ausgelagert, nicht Teil dieser Spec):** `cloud_low`, `cloud_mid`,
  `cloud_high` haben strukturell **kein** Tages-Auswertungsfeld auf
  `SegmentWeatherSummary` (`src/app/models.py:349-407`, nur `cloud_avg_pct`
  für die Gesamtbewölkung existiert dort). Der Vergleich rechnet sich diese
  drei Werte selbst aus (`src/services/comparison_engine.py:203-211,449-457`).
  Diese Spec behebt das nicht — sie hält lediglich fest, dass genau diese
  drei Keys deshalb von Guard-Prüfung 3c ausgenommen sind.
- **#1391 (ausgelagert, nicht Teil dieser Spec):** `snowfall_limit` hat kein
  `summary_fields`, obwohl das Feld existiert und befüllt wird — ein echter
  Fehler mit Trip-Alarm-Wirkung. Diese Spec behebt das nicht, sondern nimmt
  `snowfall_limit_m` deshalb von Guard-Prüfung 3c aus.
- **Messkorrektur:** `sunshine` (`metric_catalog.py:368`) und
  `wind_direction` (`:177`) tragen ihr `summary_fields` bereits — sie sind
  **keine** Ausnahme von Guard-Prüfung 3c, auch wenn der Compare-Key
  namentlich leicht abweicht (`sunny_hours_h` vs. zentral `sunny_hours`,
  `wind_direction_deg` vs. zentral `wind_direction_avg_deg`).
- **Feststellung (gehört zu #1366/S3, hier NICHT behoben):** „Leere Auswahl
  bleibt leer" ist im heutigen Code inkonsistent behandelt. Der Compare-Δ-
  Alarm-Pfad (`compare_alert.py::_display_config_from_active_metrics`,
  #1191) unterscheidet bereits korrekt: `active_metrics` fehlt ganz → `None`
  → Legacy „alles feuert"; `active_metrics` ist eine (auch leere) Liste →
  explizit abgebildet, `[]` heißt „nichts feuert". Der Render-Pfad für die
  Übersichtstabelle (`resolve_enabled_metrics()` in `compare_metric_ids.py`)
  tut das NICHT — `if not active_metrics: return None` wirft `[]` und `None`
  in denselben Topf, eine bewusst leere Auswahl zeigt heute fälschlich
  ALLES. Die tieferliegenden Renderer-Funktionen (`_visible_metrics()` in
  `compare_html.py`, `format_location_summary()` in `compact_summary.py`)
  unterstützen den leeren Fall bereits korrekt — der Bug sitzt isoliert in
  `resolve_enabled_metrics()`. Diese Lieferung ändert daran NICHTS
  (Dach-Epic #1374 untersagt das Mitnehmen von Tickets aus anderen Etappen);
  Zuständigkeit #1366, Etappe S3.

## Offene Punkte

- **Erzeugen scheidet aus, verbinden+prüfen bleibt:** eine mechanische
  Ableitung des Compare-Katalogs aus dem zentralen Katalog wurde geprüft und
  verworfen (PO-Entscheidung 2026-07-26), weil sie an drei Stellen bricht:
  (1) Labels weichen redaktionell ab und sind nicht ableitbar
  („Windspitzen" vs. zentral „Wind", „Wolken tief/mittel/hoch" vs. „Tiefe/
  Mittelhohe/Hohe Wolken", „Gewitter-Energie (CAPE)" mit Bindestrich vs.
  zentral ohne, „Gefühlte Temp. min" vs. „Gefühlte Temperatur"); (2)
  Wertebereiche, Schrittweiten, `kind`, `ordinalLabels` und `higherIsBetter`
  existieren ausschließlich auf der Compare-Seite, der zentrale Katalog
  kennt sie nicht; (3) drei Größen (`cloud_low`, `cloud_mid`, `cloud_high`)
  haben strukturell **kein** Tages-Auswertungsfeld, aus dem sich überhaupt
  etwas ableiten ließe (#1392). Ein generierter Katalog wäre entweder eine
  zweite, noch aufwendigere Überlagerungstabelle (kein Gewinn gegenüber der
  heutigen kuratierten Liste) oder unvollständig. Die kleinere, robustere
  Lösung: die Tabelle bleibt kuratiert, bekommt aber nachweisbare
  Herkunftsfelder plus einen Test, der Abdriften sichtbar macht.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Setzt die bestehende Trip/Compare-Teilungs-Invariante
  (CLAUDE.md) und die Drift-Guard-Praxis (`compare_metric_catalog.py:92-109`,
  `test_compare_metric_catalog_consistency.py`) fort, ohne eine neue
  Entscheidungsfläche zu eröffnen. Reine Ergänzung zweier Herkunftsfelder an
  einer bestehenden, weiterhin kuratierten Datenquelle plus ein Prüf-Test —
  kein Persistenz-, Kanal- oder Datenmodellentscheid.

## Changelog

- 2026-07-26: Initial spec created (S2 von Epic #1372, Ticket #1373)
- 2026-07-26: Auf Scheibe A zurückgeschnitten (PO-Entscheidung: 250-Zeilen-
  Deckel, S2 in zwei Lieferungen geteilt). Persistenzformat, Migration und
  die vier Frontend-Speicher-Ergänzungsstellen nach „Scheibe B" verschoben
  (eigener Abschnitt, verdichtet erhalten). AC-8 (leere Auswahl) entfernt —
  gehört zu #1366/S3, Dach-Epic #1374 untersagt Etappen-Mischung; Fund als
  Feststellung unter Known Limitations erhalten. ACs neu durchnummeriert
  (AC-1 bis AC-6). Fund ergänzt: Compare-Labels weichen vom zentralen
  `label_de` ab (nicht mechanisch ableitbar) — Überlagerungstabelle bleibt
  fast so groß wie die heutige Literal-Liste, `unit` dagegen ist 1:1
  übernehmbar.
- 2026-07-26: **Von „ableiten" auf „verbinden und prüfen" umgestellt**
  (PO-Entscheidung 2026-07-26, Messung widerlegt den bisherigen Entwurf).
  `COMPARE_METRIC_CATALOG` bleibt eine kuratierte Tabelle — sie wird NICHT
  generiert. Jeder Eintrag bekommt stattdessen `metric_id` + `aggregation`
  ergänzt; der Drift-Guard prüft die Beziehung zum zentralen Katalog in
  beide Richtungen plus (neu) `aggregation` ⊆ `summary_fields`, mit einer
  kleinen, benannten, nur schrumpfenden Ausnahmeliste für #1391
  (`snowfall_limit`, echter Bug: fehlendes `summary_fields` trotz
  befülltem Feld) und #1392 (`cloud_low`/`cloud_mid`/`cloud_high`, kein
  Tages-Auswertungsfeld auf `SegmentWeatherSummary`). Messkorrektur:
  `sunshine`/`wind_direction` tragen ihr `summary_fields` bereits — keine
  Ausnahme. AC-1 (alt: „erscheint automatisch") und AC-3 (alt: Drift-Guard)
  sagten dasselbe und wurden zu einem AC-1 zusammengeführt, ACs neu
  durchnummeriert (AC-1 bis AC-5, vorher AC-1 bis AC-6). „Offene Punkte"
  von „naive Cartesian-Ableitung" auf die Begründung gegen jede Form von
  Erzeugen umgeschrieben. Umfangsschätzung deutlich verkleinert (~150-190
  statt ~210-315 Zeilen) — größter Teil der Backend-/Frontend-Tests ist
  bereits aus einer vorherigen RED-Runde vorhanden und mit dem neuen Design
  kompatibel; einzig `tests/unit/test_compare_catalog_derives_from_central_catalog.py`
  muss umgeschrieben werden, weil sie den verworfenen Generierungsmechanismus
  testet.
