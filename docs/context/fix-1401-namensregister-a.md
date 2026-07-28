# Context: fix-1401-namensregister-a

Issue #1401 · Epic #1372 (Etappe **S2-Nachzügler**, gehört vor S4) · Dach #1374

## Request Summary

Dieselbe Wettergröße heißt an jeder Auswahlfläche anders („Temperatur max" /
„Temperatur" / „Höchsttemperatur" / „Temp max" / „Temp"). **Scheibe A** dieses
Tickets führt die Anzeigenamen im Kern auf **eine Quelle** zurück: Der Name
kommt aus der Wettergröße, die **Auswertung** (Maximum/Minimum/Mittel) ist ein
eigenes Element daneben — nicht mehr Teil des Namens. Betroffen sind alle
Backend-Flächen und die Vergleichs-Mail.

**Nicht in dieser Lieferung:** hartkodierte Frontend-Listen (Stundenverlauf,
Alarme, Trip-Wertebereiche) → Scheibe B; sichtbare Begründung bei fehlenden
Größen → Scheibe C.

## Ausgangslage: wo die Namen heute herkommen

**Vier deutsche Anzeigenamen für dieselbe Größe im Backend** (gemessen 2026-07-27):

| # | Quelle | Umfang | Beispiel „Temperatur (max)" | Rolle |
|---|---|---|---|---|
| 1 | `src/app/metric_catalog.py:75-435` (`MetricDefinition.label_de`) | 24 Größen (22 wählbar) | „Temperatur" | **zentraler Katalog — Zielquelle** |
| 2 | `src/output/renderers/compare_metric_catalog.py:51-132` (`label`) | 26 Zeilen | „Temperatur max" | Compare-Auswahlflächen + `/api/compare/metrics` |
| 3 | `src/output/renderers/email/compare_html.py:220-260` (`CV2_METRICS.label`) | ~20 | „Temp max" | Spaltenköpfe Vergleichstabelle der Mail |
| 4 | `src/output/renderers/email/compare_html.py:266-276` (`HOUR_METRICS.label`) | 9 | „Temp" | Spaltenköpfe Stundentabelle der Mail |

Der zentrale Katalog trägt zusätzlich **drei Längenstufen derselben Größe**
(`label_de` / `col_label` / `compact_label` / `alert_label`). Das ist **kein**
Widerspruch zu #1401 — verschiedene Platzbudgets (Fließtext, Tabellenkopf,
SMS-Kürzel) sind legitim, solange sie aus **einer** Quelle stammen. Genau das
ist der Hebel: Quelle 3 und 4 sind nichts anderes als handgepflegte
`col_label`-Duplikate.

### Die Brücken liegen bereits — S2 hat sie gebaut

- `compare_metric_catalog.py:19-27` — jeder der 26 Einträge trägt seit #1373
  bereits `metric_id` **und** `aggregation`. Die Zuordnung ist vollständig und
  testgesichert (`test_compare_metric_catalog_endpoint.py::EXPECTED_METRIC_ORIGIN`).
- `compare_html.py:206-212` — `CV2_METRICS` und `HOUR_METRICS` tragen ebenfalls
  je ein `metric_id`-Feld, laut Kommentar ausdrücklich als „dokumentierte
  Verbindung für die Konsolidierung" — **heute ungenutzt**: kein einziger
  `get_metric(...).label_de`-Aufruf im Renderpfad.
- `compare_metric_catalog.py:199-218` — Rückwärts-Index `key_for(metric_id, aggregation)`.

Der Umbau ist damit **Rückbau auf einen vorhandenen Weg**, kein Neubau: die
Verdrahtung existiert, nur der Name wird noch danebengelegt statt abgeleitet.

### Bewusste Kursänderung gegenüber S2

`docs/specs/modules/feat_1373_s2_ein_katalog.md:341-356` entschied ausdrücklich,
die Compare-Namen **kuratiert** zu lassen: die Labels wichen „redaktionell ab und
sind nicht ableitbar". Die PO-Meldung in #1401 kehrt das um: die redaktionelle
Abweichung ist genau der Defekt. Der zentrale Name gewinnt; wo eine
Compare-Formulierung besser ist („Windspitzen" statt „Wind"), wandert sie **in
den zentralen Katalog**, statt daneben zu leben. Das gehört als Entscheidung in
die Spec (Kandidat für ADR, weil es eine dokumentierte Entscheidung ablöst).

## Related Files

| Datei | Relevanz |
|---|---|
| `src/app/metric_catalog.py` | Zielquelle; ggf. Aufnahme besserer Compare-Formulierungen |
| `src/output/renderers/compare_metric_catalog.py` | `label` wird abgeleitet statt getippt; `aggregation` wird eigenes Ausgabefeld |
| `api/routers/compare.py:11-22` | reicht den Katalog 1:1 durch — Name + Auswertung kommen automatisch mit |
| `api/routers/config.py:58-83` | `/api/metrics` (Trip) liefert `label` aus `label_de` — bereits sauber |
| `src/output/renderers/email/compare_html.py:206-276` | `CV2_METRICS`/`HOUR_METRICS` lesen künftig über `metric_id` |
| `src/output/renderers/comparison.py` | Klartext-Fassung der Mail — blinder Fleck des Pflicht-Validators, muss mitgeprüft werden |
| `src/output/metric_format.py:147-160` | vorhandener Auswahlmechanismus zwischen den Längenstufen (`label`/`col`/`compact`) — Vorbild statt Neubau |

## Dependencies

- **Upstream:** `metric_catalog.py` (Namen, `summary_fields`, `col_label`)
- **Downstream:** `/api/compare/metrics` → Frontend-Grundauswahl, Reihenfolge,
  3-Tages-Ausblick, Wertebereiche (Vergleichs-Zweig) — diese vier Flächen lesen
  den Namen **bereits aus der API** und ändern sich ohne Frontend-Eingriff mit.
- **Go:** reine Weiterleitung, keine eigene Namenskopie
  (`internal/router/router.go:122,155`, Passthrough-Test vorhanden) — **kein
  Go-Eingriff nötig**.

## Existing Specs

- `docs/specs/modules/feat_1373_s2_ein_katalog.md` — S2 Scheibe A (Herkunftsfelder + Drift-Guard)
- `docs/specs/modules/feat_1373_s2b_metrik_speicherformat.md` — S2 Scheibe B (Persistenz `{metric_id, aggregation}`)
- `docs/specs/modules/compare_metric_catalog_endpoint.md`, `compare_metric_ssot_final.md`, `compare_metric_parity.md`

## Risks & Considerations

1. **Der Pflicht-Validator blockiert diese Lieferung strukturell.**
   `.claude/hooks/email_spec_validator.py:221-241` kennt die Spaltennamen der
   Mail **wörtlich** (`_HOUR_COLUMNS_V2` = „Temp", „Gef.", „Gew." …;
   `_OVERVIEW_METRIC_CHECKS` = „Temp max" …). Sobald die Mail-Spaltenköpfe aus
   dem Register kommen, lehnt er die korrekte Mail ab — und als Pflichtteil des
   Renderer-Commit-Gates (#811) verhindert er jeden Commit. Das ist die
   #1381-Falle in neuer Form.
   **Auflösung:** Validator-Anpassung darf **nicht** in diesem Workflow
   passieren (Specification Gaming). Sie braucht ein eigenes Ticket mit eigenem
   Workflow und Gold-Standard-Test — angestoßen **nachdem** die Spec die neuen
   Namen festgelegt hat, geliefert **vor** dem Commit von Scheibe A.
2. **Zwei Mail-Fassungen.** Der Validator liest nur HTML; der Klartext-Teil
   (`comparison.py`) ist ein belegter blinder Fleck (#1366). Nachweis muss in
   **beiden** Fassungen an einer echt zugestellten Staging-Mail geführt werden.
3. **Parallele Arbeit an derselben Datei (#1402).** Die Nachbar-Sitzung ändert
   in `compare_html.py` die Zeitzonen-Parameter bei `:658,789,904` sowie
   `email/helpers.py:926`; diese Lieferung sitzt bei `:206-276`. Getrennte
   Stellen, aber dieselbe Datei — **erst rebasen, wenn #1402 geliefert hat**,
   dann implementieren. #1402 stellt zusätzlich die gesamte Testsuite auf eine
   Nicht-Weltzeit-Zone um (neue `conftest.py`), was jeden hier neu
   geschriebenen Test betrifft.
4. **Änderungsbudget.** 250 Zeilen je Workflow. Der Katalog-Umbau plus zwei
   Renderer-Tabellen liegt erfahrungsgemäß an der Grenze; notfalls schneidet
   die Spec die Mail-Spaltenköpfe als eigene Teillieferung ab.
5. **Kein stilles Verwerfen (Invariante 2).** Fällt beim Ableiten ein Name weg
   (z.B. Größe ohne `col_label`), muss das sichtbar scheitern, nicht auf einen
   leeren Kopf hinauslaufen.
6. ~~Gestaltungsfrage Mail-Spalte~~ — **entschieden, siehe unten.**

## PO-Entscheidung 2026-07-27 (Gestalt des Registers)

> „Kurzform beibehalten. Aber es muss an zentraler Stelle einmalig definiert
> werden: langer Name, Kurzform (z.B. Tabellenkopf) und SMS. Am besten noch eine ID."

Das Register ist damit **je Wettergröße ein Eintrag** mit vier festen Angaben —
**Kennung**, **langer Name**, **Kurzform** (Tabellenkopf), **SMS-Kürzel** — plus
der Auswertung als eigenständigem Element daneben. Das entspricht exakt der
bereits vorhandenen Struktur `MetricDefinition` (`id`, `label_de`, `col_label`,
`compact_label`/`sms_code`): **der zentrale Katalog IST das Register**, es wird
keine neue Struktur gebaut. Alle anderen Tabellen leiten ab.

Folgen für den Zuschnitt:

- Die Mail-Spaltenköpfe bleiben verdichtet (heute „Temp max"), werden aber aus
  `col_label` + Auswertung **abgeleitet** statt getippt. Wo die Ableitung
  denselben String ergibt wie heute, bleibt die Mail unverändert — dann greift
  Risiko 1 (Validator) gar nicht. Wo sie abweicht, ist es entweder eine zu
  korrigierende Kurzform im zentralen Katalog oder ein Fall für das
  Validator-Ticket. **Diese Abweichungsmessung ist die erste Aufgabe der
  Analyse-Phase.**
- Die Auswertung wird als eigenes Feld ausgegeben, sodass die Auswahlflächen
  „Temperatur · Maximum" zeigen können, ohne dass der Name sie enthält.

## Analysis (2026-07-27)

### Type
Bug (nutzersichtbare Namensdivergenz), umgesetzt als strukturelle Zusammenführung.

### Messergebnis (gemessen am Code, nicht geschätzt)

| Fläche | Ableitbar? | Befund |
|---|---|---|
| Compare-Auswahlliste (26) | ja | 19/26 Namen bereits stringgleich mit `label_de`; **8** weichen redaktionell ab (s.u.) |
| Mail-Übersichtstabelle `CV2_METRICS` (27 Zeilen) | teilweise | nur **11** tragen `metric_id`; **15** Wetterzeilen ohne Verknüpfung (aus #1296/#1324), 1 Nicht-Metrik („Amtliche Warnungen") |
| Mail-Stundentabelle `HOUR_METRICS` (9) | ja | alle tragen `metric_id`; Zielstring = `col_label` |
| Trip-Auswahlflächen | — | bereits im Zielzustand: `/api/metrics` gibt `label_de` unverändert durch |

### PO-Entscheidung 2026-07-27 (Sprache der Kurzform)

> „Es bleibt Englisch […] und wenn der Ortsvergleich noch Deutsch ist, muss er auch
> Englisch werden. Irgendwann soll die App ja international werden."

Das **bestätigt und erweitert** die bestehende Entscheidung aus #849/#862
(`docs/specs/_archive/modules/fix_862_849_col_labels.md:58`: „Spaltenköpfe bleiben
bewusst englisch (PO-Entscheidung)", bewacht von
`tests/tdd/test_issue_862_849_col_labels.py::test_no_german_col_labels_in_catalog`).
Der Ortsvergleich ist der Ausreißer und wird angeglichen — **nicht** umgekehrt.

**Konsequenz:** Das Register braucht **kein neues Feld**. `MetricDefinition` trägt
bereits alle vier vom PO geforderten Angaben:

| PO-Begriff | Feld | Sprache | Beispiel |
|---|---|---|---|
| Kennung | `id` | — | `temperature` |
| langer Name | `label_de` | deutsch | „Temperatur" |
| Kurzform (Tabellenkopf) | `col_label` | **englisch** | „Temp" |
| SMS-Kürzel | `sms_code`/`compact_label` | — | „T" |
| Auswertung (daneben) | `aggregation` | deutsch beschriftet | „Maximum" |

### Zuschnitt (Empfehlung, aus der Bewertung)

| Teil | Inhalt | Renderer-Gate #811 | Umfang |
|---|---|---|---|
| **A1** | `compare_metric_catalog.py` leitet den langen Namen aus `label_de` ab; `aggregation` wird eigenes Ausgabefeld; 8 redaktionelle Namensentscheidungen ins Register | **nein** — belegt: `compare_metric_catalog.py` und `email/compare_html.py` importieren einander nicht | ~120-180 Zeilen |
| **Gate-Ticket** | `email_spec_validator.py` lernt die neuen Spaltenüberschriften (Gold-Standard-Test) — eigener Workflow, Pflicht vor A2 | ist das Ticket | klein |
| **A2** | `CV2_METRICS`/`HOUR_METRICS` leiten `col_label` + Auswertung ab; **15** fehlende `metric_id` nachtragen mit Vollständigkeits-Wächter | ja | wahrscheinlich > 250 → erneut zu teilen |

**A1 fasst `col_label` NICHT an** — sonst zöge es über `email/helpers.py:465-473`,
`trip_report.py:503-524`, `email/html.py:1334` und `email/plain.py:293` sofort in
die Trip-Mail durch.

### Die 8 redaktionellen Namensentscheidungen (Freigabe mit der Spec)

| Größe | heute Vergleich | heute Register | Vorschlag | Begründung |
|---|---|---|---|---|
| `wind`/max | Windspitzen | Wind | **Wind** | „Spitzen" sind sachlich die Böen (eigene Größe) — heutige Benennung ist irreführend |
| `sunshine`/sum | Sonnenstunden | Sonnenschein | **Sonnenstunden** | benennt die Einheit (h) korrekt |
| `cape`/max | Gewitter-Energie (CAPE) | Gewitterenergie (CAPE) | **Gewitterenergie (CAPE)** | Rechtschreibung |
| `wind_chill`/min | Gefühlte Temp. min | Gefühlte Temperatur | **Gefühlte Temperatur** | Auswertung steht künftig daneben, Abkürzung entfällt |
| `wind_chill`/max | Gefühlte Temp. max | Gefühlte Temperatur | **Gefühlte Temperatur** | dito |
| `cloud_low`/avg | Wolken tief | Tiefe Wolken | **Tiefe Wolken** | grammatisch korrekt; Register gewinnt, wo kein Sachgrund dagegen spricht |
| `cloud_mid`/avg | Wolken mittel | Mittelhohe Wolken | **Mittelhohe Wolken** | dito |
| `cloud_high`/avg | Wolken hoch | Hohe Wolken | **Hohe Wolken** | dito |

### Risiken

- **Vollständigkeit statt stillem Verwerfen:** Die 15 CV2-Zeilen ohne `metric_id`
  sind ein belegtes Wiederholungsmuster (#1296/#1324: additive Zeilen wurden
  schon einmal still verworfen). A2 braucht einen Wächter-Test, keine Prosa.
- **Validator:** `_HOUR_COLUMNS_V2` bricht bei A2 hart (6 von 9 Spalten),
  `_OVERVIEW_METRIC_CHECKS` bricht **still** (4 von 5 Prüfungen würden lautlos
  übersprungen — Gate-Erosion). Beides gehört ins Gate-Ticket, nicht hierher.
- **#1402 (parallel):** dieselbe Datei `compare_html.py` (dort `:658,789,904`),
  betrifft erst A2. Vor A2 rebasen.

### Open Questions
- [x] Sprache der Kurzform → PO 2026-07-27: englisch, Vergleich zieht nach
- [x] Zusätzliches Register-Feld nötig? → nein
- [ ] Freigabe der 8 Namensentscheidungen → mit der Spec

## Nebenbefunde (nicht Teil dieser Lieferung)

- **Widersprüchliches SMS-Kürzel:** `sms_trip.py:54-62` gibt `snow_depth` das
  Kürzel „SN", der zentrale Katalog „SD" (`metric_catalog.py:414-423`); `fresh_snow`
  fehlt in der Tabelle ganz. Genutzt von `/sms-symbols`. → Sammel-Issue #1199.
- **Divergente Alarm-Namenskopie im Frontend:** `alertMetricLabels.ts:16-32`
  sagt „Temperaturänderung"/„Niederschlagsänderung", die tatsächlich gerenderte
  Kopie `alerts-tab/AlertMetricLevelTable.svelte:24-39` sagt
  „Temperatursturz"/„Regenänderung". → Scheibe B (gehört sachlich dorthin).
- **#1384** (Trip-Wertebereiche: nur 5 von 24 Größen hinzufügbar) ist die fünfte
  Liste und liegt bereits terminiert in S6 — hier nicht mitnehmen.
