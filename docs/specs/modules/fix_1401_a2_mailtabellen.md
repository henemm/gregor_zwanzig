---
entity_id: fix_1401_a2_mailtabellen
type: bugfix
created: 2026-07-28
updated: 2026-07-28
status: draft
workflow: fix-1401-a2-mailtabellen
version: "1.0"
tags: [compare, metric-catalog, naming, mail-renderer, trip-compare-sharing]
---

# Fix #1401 Scheibe A2: Die Vergleichs-Mail-Tabellen ziehen aus dem Register nach

## Approval

- [x] Approved — PO Henning, 2026-07-28 („Go"): Acceptance Criteria, die
  Entscheidung „englische Kurzform in **beiden** Mail-Tabellen" und die
  Aufteilung in A2a/A2b (s. u.).

## Aufteilung A2a / A2b (PO-Freigabe 2026-07-28)

Die Gesamtlieferung sprengt den Änderungsdeckel (Rechenweg unter *Estimated
Scope*). Geteilt wird entlang der **Sichtbarkeit**, nicht entlang der Dateien:

| Teil | Inhalt | Sichtbare Wirkung | Braucht #1404? |
|---|---|---|---|
| **A2a** (diese Lieferung) | Die 15 fehlenden `metric_id`/`aggregation`-Verknüpfungen in `CV2_METRICS` nachtragen; Vollständigkeits-Wächter **AC-3** inkl. Wirkungsnachweis | **keine** — reine Verdrahtung, jede Beschriftung bleibt Zeichen für Zeichen wie heute | **nein** |
| **A2b** (Folgelieferung) | Ableitung der Beschriftung aus `col_label` + Kollisionsregel, inkl. `comparison.py::_PLAIN_ROWS`/`_DAILY_PLAIN_ROWS` — **AC-1, AC-2, AC-4, AC-5** | Mail-Überschriften wechseln auf die englische Kurzform | **ja** — Renderer-Commit-Gate #811 verlangt einen bestandenen Validator-Lauf, und der Validator kennt die alten Überschriften wörtlich |

**A2a ist damit sofort lieferbar**, ohne auf #1404 zu warten. Sein Wert liegt
im Wächter: genau dieses Nachtragen wurde in #1296 und #1324 bereits zweimal
vergessen, ohne dass etwas anschlug.

**Zusätzliche Auflage für A2a:** Ein Test muss belegen, dass die Beschriftung
sich **nicht** ändert (Zeichen-für-Zeichen gegen den heutigen Stand) — sonst
ist „keine sichtbare Wirkung" eine Behauptung statt eines Nachweises.

## Purpose

Scheibe A1 hat die vier serverseitig gespeisten Compare-Auswahlflächen
(Grundauswahl, Reihenfolge, 3-Tages-Ausblick, Wertebereiche) auf das
zentrale Wetter-Namensregister (`src/app/metric_catalog.py`) zurückgeführt.
Die Vergleichs-**Mail** blieb dabei bewusst außen vor: ihre beiden
Tabellen — Übersichtstabelle und Stundentabelle, je in HTML **und**
Klartext — tippen ihre Spaltenüberschriften weiterhin selbst, an vier
Stellen mit teils unterschiedlichem Wortlaut für dieselbe Größe. Diese Spec
führt beide Mail-Tabellen (gestaltete Fassung und Klartext-Zwilling) auf
dieselbe Registerquelle zurück wie A1 — als Kurzform (`col_label`, englisch,
PO-Entscheidung #849/#862) statt als langem Namen, weil hier der
Tabellenkopf, nicht die Fließtext-Auswahl, das Platzbudget vorgibt — und
schließt die seit #1296/#1324 wiederholt aufgetretene Lücke, dass neue
Katalog-Zeilen ohne Namens-Verknüpfung still im Vokabular der Mail
verwaisen.

Etappe S2-Nachzügler von Epic #1372 (Kind von Dach-Epic #1374), Ticket #1401
Scheibe A2. Setzt auf der in A1 gelieferten `metric_id`/`aggregation`-
Verknüpfung auf (dort bereits für die vier Auswahlflächen genutzt) und
überträgt dasselbe Prinzip auf die Mail-Tabellen.

## Source

- **File:** `src/output/renderers/email/compare_html.py`
- **Identifier:** `CV2_METRICS` (Zeilen ~221-261), `HOUR_METRICS` (Zeilen
  ~267-277)
- **File:** `src/output/renderers/comparison.py`
- **Identifier:** `_DAILY_PLAIN_ROWS` (Zeilen ~52-69), `_PLAIN_ROWS`
  (Zeilen ~82-100)

> Schicht-Hinweis: reine Python-Core-Änderung
> (`src/output/renderers/email/`, `src/output/renderers/`), keine
> Go-Beteiligung, kein Frontend-Eingriff — die Mail-Renderer sind
> serverseitige Reintext-/HTML-Erzeugung ohne UI-Fläche.

## Ausgangslage (gemessen, s. `docs/context/fix-1401-namensregister-a.md`)

Vier Beschriftungsquellen für dieselbe Wettergröße in der Mail (vor dieser
Lieferung):

| # | Quelle | Zeilen | Verknüpft? |
|---|---|---|---|
| 1 | `CV2_METRICS` (Übersichtstabelle, HTML) | 27 (1 `kind:"warn"`, keine Metrik) | 11 von 26 Metrik-Zeilen tragen `metric_id`; 15 nicht |
| 2 | `HOUR_METRICS` (Stundentabelle, HTML) | 9 | alle 9 tragen `metric_id` |
| 3 | `_DAILY_PLAIN_ROWS` + `_PLAIN_ROWS` (`comparison.py`, Klartext-Übersicht) | 26 | eigene, vierte Namensquelle — **keine** `metric_id`-Verknüpfung, reine String-Duplikate von Quelle 1 |
| — | Klartext-Stundentabelle | — | nutzt bereits `_visible_hour_metrics()` aus `compare_html.py` — zieht mit dieser Lieferung automatisch nach, keine eigene Änderung nötig |

Die 15 fehlenden Verknüpfungen sind über `_DAILY_AGGREGATE_FIELD`
(`compare_html.py:377-396`) bzw. direkte `LocationResult`-Felder
(befüllt in `services/comparison_engine.py:189-255`) eindeutig auflösbar:

`temp_min`→temperature/min · `gust_max`→gust/max · `cape_max`→cape/max ·
`freezing_level`→freezing_level/min · `wind_direction_avg`→wind_direction/avg
· `wind_chill_min`→wind_chill/min · `wind_chill_max`→wind_chill/max ·
`cloud_low_avg`→cloud_low/avg · `cloud_mid_avg`→cloud_mid/avg ·
`cloud_high_avg`→cloud_high/avg · `humidity_avg`→humidity/avg ·
`dewpoint_avg`→dewpoint/avg · `pressure_avg`→pressure/avg ·
`precip_type`→precip_type/max · `snowfall_limit`→snowfall_limit/min.

**Namenskollisionen** gibt es über alle 26 Metrik-Zeilen nur zweimal:
`col_label="Temp"` (temperature/max, temperature/min) und
`col_label="Feels"` (wind_chill/max, wind_chill/min). Die übrigen 22 sind
eindeutig — unten als Ziel-Tabelle festgehalten.

### Ziel-Beschriftung je Zeile (Übersichtstabelle + Klartext-Zwilling)

| Zeilen-Key | metric_id | Auswertung | `col_label` | Kollision? | **Neue Beschriftung** |
|---|---|---|---|---|---|
| temp_max | temperature | max | Temp | ja (temp_min) | Temp max |
| temp_min | temperature | min | Temp | ja (temp_max) | Temp min |
| wind_max | wind | max | Wind | nein | Wind |
| precip_sum | precipitation | sum | Rain | nein | Rain |
| pop_max | rain_probability | max | Rain% | nein | Rain% |
| thunder_max | thunder | max | Thdr | nein | Thdr |
| sunny_hours | sunshine | sum | Sun | nein | Sun |
| cloud_avg | cloud_total | avg | Cloud | nein | Cloud |
| uv_max | uv_index | max | UV | nein | UV |
| visibility_min | visibility | min | Visib | nein | Visib |
| snow_depth_cm | snow_depth | max | SnowH | nein | SnowH |
| snow_new_cm | fresh_snow | sum | NewSn | nein | NewSn |
| gust_max | gust | max | Gust | nein | Gust |
| cape_max | cape | max | CAPE | nein | CAPE (unverändert) |
| freezing_level | freezing_level | min | 0°Line | nein | 0°Line |
| wind_direction_avg | wind_direction | avg | WDir | nein | WDir |
| wind_chill_min | wind_chill | min | Feels | ja (wind_chill_max) | Feels min |
| wind_chill_max | wind_chill | max | Feels | ja (wind_chill_min) | Feels max |
| cloud_low_avg | cloud_low | avg | CldLow | nein | CldLow |
| cloud_mid_avg | cloud_mid | avg | CldMid | nein | CldMid |
| cloud_high_avg | cloud_high | avg | CldHi | nein | CldHi |
| humidity_avg | humidity | avg | Humid | nein | Humid |
| dewpoint_avg | dewpoint | avg | Cond° | nein | Cond° |
| pressure_avg | pressure | avg | hPa | nein | hPa |
| precip_type | precip_type | max | PType | nein | PType |
| snowfall_limit | snowfall_limit | min | SnowL | nein | SnowL |

### Ziel-Beschriftung Stundentabelle (`HOUR_METRICS`, keine Kollision möglich —
alle 9 `metric_id` sind untereinander verschieden)

| Zeilen-Key | metric_id | `col_label` | heute | neu |
|---|---|---|---|---|
| t2m_c | temperature | Temp | Temp | Temp (unverändert) |
| wind_chill_c | wind_chill | Feels | Gef. | Feels |
| wind10m_kmh | wind | Wind | Wind | Wind (unverändert) |
| gust_kmh | gust | Gust | Böen | Gust |
| precip_1h_mm | precipitation | Rain | Regen | Rain |
| uv_index | uv_index | UV | UV | UV (unverändert) |
| thunder_level | thunder | Thdr | Gew. | Thdr |
| pop_pct | rain_probability | Rain% | Regen-W. | Rain% |
| visibility_m | visibility | Visib | Sicht | Visib |

Ergibt in kanonischer Reihenfolge `["Zeit","Temp","Feels","Wind","Gust",
"Rain","UV","Thdr","Rain%","Visib"]` — identisch mit dem in #1404 verlangten
`_HOUR_COLUMNS_V2`-Zielwert (s. Known Limitations).

## Estimated Scope

**LoC-Risiko vorab:** Die realistische Gesamtsumme (Verknüpfungen nachtragen
+ Ableitung + Vollständigkeits-Wächter + Testanpassung) liegt deutlich über
dem 250-Zeilen-Deckel. Empfehlung: Split (s. u.), analog zum Vorgehen bei A1
(dort per PO-Override gelöst, hier stattdessen per Split, weil sich die
beiden Teile — anders als bei A1s Backend/Frontend-Trennung — sauber in
"risikoarme Verknüpfung" und "sichtbare Ableitung" teilen lassen, ohne dass
dazwischen ein neuer Bug entsteht).

### Rechenweg

**Produktivcode:**

| Datei | Änderung | Netto-Zeilen |
|---|---|---|
| `src/output/renderers/email/compare_html.py` — `CV2_METRICS` | 15 Zeilen bekommen `metric_id`+`aggregation`; 11 bestehende bekommen zusätzlich `aggregation` (Feld existiert dort noch nicht); alle 26 verlieren das getippte `"label"` | ~40-55 |
| `src/output/renderers/email/compare_html.py` — `HOUR_METRICS` | 9 Zeilen verlieren das getippte `"label"` (kein `aggregation`, s. Implementation Details 1) | ~10 |
| `src/output/renderers/email/compare_html.py` — neue Ableitungsfunktion | Beschriftung = `get_metric(metric_id).col_label`, Kollisions-Suffix = roher `aggregation`-Wert, wenn `col_label` innerhalb der **aktuell sichtbaren** Zeilenmenge mehrfach vorkommt — Mechanik analog `compare_outlook_metric_ids.py::outlook_columns()` (dortiges `mehrfach`-Set), nachgenutzt statt neu gebaut; Verdrahtung in den Renderpfad der Übersichts- und Stundentabelle | ~30-45 |
| `src/output/renderers/comparison.py` — `_DAILY_PLAIN_ROWS`/`_PLAIN_ROWS` | getippte Labels entfernt, Beschriftung über dieselbe Ableitungsfunktion aus `compare_html.py` bezogen (keine fünfte Kopie) | ~20-30 |
| Docstrings/Kommentare (beide Dateien) | Herkunfts-Hinweis analog A1s `#1401 A1`-Kommentaren | ~10-15 |

**Produktivcode-Summe:** ~110-160 Netto-Zeilen.

**Tests:**

| Test | Inhalt | Netto-Zeilen |
|---|---|---|
| Vollständigkeits-Wächter (neu, `tests/unit/test_compare_mail_metric_link_completeness.py`) | Jede CV2_METRICS-/HOUR_METRICS-Zeile (außer `warn`) trägt ein auflösbares `metric_id`+`aggregation`-Paar; Wirkungsnachweis über künstlich reduzierte Kopie (Vorbild: `test_compare_metric_catalog_consistency.py::test_guard_actually_fails_when_a_catalog_metric_has_no_cv2_row`) | ~90-130 |
| Beschriftungs-Herkunft (neu, `tests/unit/test_compare_mail_label_source_catalog.py`) | Übersichts- und Stundentabelle zeigen `col_label` statt getippter Strings, für eine Auswahl ohne Kollisionsfall | ~40-60 |
| Kollisionsregel (neu, `tests/unit/test_compare_mail_label_collision_suffix.py`) | Nur temperature/max gewählt → "Temp"; beide gewählt → "Temp max"/"Temp min" (analog für Feels) | ~40-60 |
| HTML/Klartext-Parität (neu, `tests/unit/test_compare_mail_plaintext_html_label_parity.py`) | Dieselbe Auswahl, dieselbe Beschriftung in beiden Fassungen derselben Mail | ~30-50 |
| Bestehende, auf feste Label-Strings assertierende Tests | Grep auf die Ziel-Strings (s. Tabellen oben) findet mindestens 12 Compare-relevante Treffer (`test_compare_metric_catalog_endpoint.py`, `test_compare_empty_metric_selection.py`, `test_compare_outlook_metric_selection.py`, `test_compare_metric_order.py`, `test_compare_mail_blocks.py`, `test_compare_mail_validator_column_order.py`, `test_compare_matrix_metric_selection.py`, `test_compare_extra_daily_metrics.py`, `test_day_comparison_integration.py`, `test_compare_metric_order_and_wind_direction.py`, `test_issue_1106_hourly_metrics_config.py`, `tests/fixtures/compare_mail_structure_golden.json`); eine breitere Suche traf 30 Dateien — der Rest sind vermutlich Trip- oder unabhängige Docstring-Treffer und müssen bei der Umsetzung einzeln triagiert werden, nicht blind mitgezählt | ~190-300 |

**Test-Summe:** ~390-600 Netto-Zeilen (die vorab genannte Grobschätzung von
~190-360 Zeilen erwies sich bei genauerer Aufschlüsselung des
Vollständigkeits-Wächters plus Wirkungsnachweis als knapp — realistisch ist
die obere Hälfte dieser Spanne, weil Wirkungsnachweis-Tests (Vorbild-Datei
141 Zeilen) systematisch mehr Code brauchen als reine Assertions).

**Gesamt:** ~500-760 Netto-Zeilen — **weit über dem 250-Zeilen-Deckel**, auch
unter der günstigsten Annahme.

### Empfehlung: Split statt Override

Anders als bei A1 (wo ein Split zwischendurch einen sichtbaren, neuen Bug
erzeugt hätte — zwei ununterscheidbare Namen) lässt sich A2 **ohne
Zwischenzustand mit neuem Fehlverhalten** teilen:

- **A2a — "Verknüpfungen nachtragen + Linkage-Wächter"**
  (`metric_id` + `aggregation` an die 26 CV2-Zeilen anfügen; die 9
  HOUR-Zeilen tragen `metric_id` bereits und bekommen bewusst **kein**
  `aggregation`, s. Implementation Details 1;
  Vollständigkeits-Wächter für die **Verknüpfung** liefern). Ändert **keine
  einzige sichtbare Beschriftung** — die getippten `"label"`-Strings bleiben
  unangetastet. Dadurch: kein Validator-Konflikt, kein Renderer-Commit-Gate-
  Risiko, minimale Testanpassung (nur der neue Wächter-Test, keine
  bestehenden Label-Assertions betroffen). Geschätzt ~50-70 Produktivcode +
  ~90-130 Test = **~140-200 Zeilen — passt unter den Deckel.**
- **A2b — "Ableitung aus dem Register + Kollisionsregel"** (setzt auf A2a
  auf; entfernt die getippten Labels, führt die Ableitungsfunktion samt
  Kollisionsregel ein, zieht `comparison.py` nach, aktualisiert alle
  Label-String-Tests). Braucht **zwingend #1404** vorher (sonst blockiert
  der Pflicht-Validator jeden Commit). Geschätzt ~60-90 Produktivcode +
  ~300-470 Test — **liegt auch allein über dem Deckel** und braucht bei
  Lieferung einen PO-Override (Präzedenzfall A1) oder eine weitere,
  funktionale Unterteilung (z. B. Übersichtstabelle zuerst, Stundentabelle +
  Klartext-Parität separat).

**Diese Spec deckt den vollen A2-Umfang (a+b) inhaltlich ab** (s. Umfang
oben) — die Aufteilung in Liefer-Häppchen ist eine Umsetzungsentscheidung,
keine Scope-Entscheidung. Empfehlung an den PO: A2a zuerst freigeben und
liefern (kein Risiko, kein Gate-Konflikt), A2b erst nach #1404 anstoßen und
dort ggf. erneut nach Umfang fragen (Override oder weiterer Schnitt).

- **Files:** 2 Produktivdateien, mindestens 4 neue Testdateien + 8-12
  bestehende mit Anpassungsbedarf.
- **Effort:** medium (A2a) bis high (A2b, wegen Testvolumen und
  #1404-Abhängigkeit).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/metric_catalog.py` (`get_metric`, `col_label`) | READ | Zielquelle der Kurzform-Beschriftung |
| `src/output/renderers/compare_metric_catalog.py` (`aggregation`-Werte je `metric_id`) | READ (Referenz) | liefert die bereits kuratierten, testgesicherten `aggregation`-Rohwerte ("max"/"min"/"avg"/"sum") — dieselben Werte werden in `CV2_METRICS`/`HOUR_METRICS` eingetragen, keine neue Quelle |
| `src/output/renderers/compare_outlook_metric_ids.py` (`outlook_columns`) | READ (Vorbild) | liefert das bereits produktiv laufende Kollisions-Muster ("mehrfach"-Set über sichtbare Spalten) — wird nachgenutzt, nicht neu gebaut |
| `src/output/renderers/email/compare_html.py` (`CV2_METRICS`, `HOUR_METRICS`, `_visible_metrics`) | MODIFY | Kernänderung dieser Lieferung |
| `src/output/renderers/comparison.py` (`_DAILY_PLAIN_ROWS`, `_PLAIN_ROWS`) | MODIFY | Klartext-Zwilling zieht über dieselbe Ableitungsfunktion nach |
| **Issue #1404** (`.claude/hooks/email_spec_validator.py`) | **BLOCKIERT A2b** | Der Pflicht-Validator kennt die alten Spaltenüberschriften wörtlich (`_HOUR_COLUMNS_V2`, `_OVERVIEW_METRIC_CHECKS`). Sobald A2b die Beschriftung ändert, lehnt der unveränderte Validator die korrekte Mail ab — als Pflichtteil des Renderer-Commit-Gates (#811) verhindert das jeden Commit. **A2b ist erst commit-fähig, wenn #1404 geliefert ist.** A2a ändert keine Beschriftung und ist von #1404 unabhängig. |
| Renderer-Commit-Gate #811 (`renderer_mail_gate.py`) | PROZESS | `compare_html.py` liegt unter dem geschützten Pfad `src/output/renderers/email/*.py` — jeder Commit braucht zusätzlich einen frischen grünen Lauf von `tests/tdd/test_issue_811_mode_matrix.py` sowie einen erfolgreichen `briefing_mail_validator.py`-Lauf (Trip-Pfad-Validator). Das ist unabhängig vom compare-spezifischen `email_spec_validator.py`/#1404 — **zwei getrennte Nachweise**, weil das Gate pfadbasiert und nicht inhaltsbasiert greift. |
| `docs/specs/modules/fix_1401_a1_namensregister.md` | REFERENZ | Vorgänger-Scheibe, liefert `metric_id`/`aggregation`-Muster und die acht Namensentscheidungen (dort für `label_de`, hier für `col_label` — unabhängige Entscheidungsräume) |

**Nicht Teil dieser Lieferung:** `.claude/hooks/email_spec_validator.py`
(#1404, eigener Workflow), `col_label`-Werte selbst (auch die schwer
lesbaren wie „Cond°"/„0°Line" — Änderung träfe die Trip-Mail mit),
Frontend-Listen Stundenverlauf/Alarme (Scheibe B), Begründung bei fehlenden
Größen (Scheibe C).

## Implementation Details

**1. Verknüpfungen nachtragen (A2a):** Die 15 CV2-Zeilen ohne `metric_id`
(Tabelle oben, „Ziel-Beschriftung je Zeile") bekommen `metric_id` +
`aggregation` exakt wie in `compare_metric_catalog.py` bereits kuratiert.
Die 11 bereits verknüpften CV2-Zeilen bekommen zusätzlich `aggregation`
(heute nur `metric_id` vorhanden). Diese Änderung ist rein additiv — kein
`"label"`-Feld wird angefasst, keine Mail-Ausgabe ändert sich.

**Die 9 `HOUR_METRICS`-Zeilen bekommen ausdrücklich KEIN `aggregation`**
(Korrektur gegenüber der ursprünglichen Fassung dieser Spec, s. Changelog
2026-07-28b). Die Stundentabelle zeigt Momentanwerte, keine Tages-
Auswertungen: „Temperatur/max" für die 12-Uhr-Zelle wäre eine falsche
Angabe, und keiner der zentral hinterlegten `summary_fields`-Werte
(`min`/`max`/`avg`) ist für einen Momentanwert sachlich richtig. Der
einzige Verwendungszweck des Feldes — das Kollisions-Suffix aus A2b — kann
dort ohnehin strukturell nie greifen, weil alle 9 `metric_id` paarweise
verschieden sind (s. Ziel-Beschriftung Stundentabelle). Ein Feld, das nichts
trägt und dabei etwas Unwahres behauptet, ist schlechter als kein Feld.
Alle 9 Zeilen tragen bereits `metric_id`; für die Stundentabelle ist die
Verknüpfung damit vollständig.

**2. Vollständigkeits-Wächter (A2a):** Nach dem Vorbild von
`tests/unit/test_compare_metric_catalog_consistency.py` (bereits produktiv,
prüft heute nur „hat die Katalog-Metrik überhaupt eine CV2-Zeile"). Der neue
Wächter prüft eine Ebene tiefer, und für die beiden Tabellen bewusst
unterschiedlich streng:

- **Übersichtstabelle (`CV2_METRICS`, außer `kind:"warn"`):** hat jede Zeile
  ein `metric_id`, das `get_metric()` auflöst, **und** ein `aggregation`,
  das im zentralen Katalog dieser `metric_id` als `summary_fields`-Schlüssel
  existiert? (`summary_fields` ist dabei der strengere Maßstab als
  `default_aggregations` — `freezing_level` und `snowfall_limit` führen
  zentral `min`/`max`, aber nur `min` als Auswertungsfeld.)
- **Stundentabelle (`HOUR_METRICS`):** hat jede Zeile ein auflösbares
  `metric_id` — und trägt sie **kein** `aggregation`? Die zweite Hälfte ist
  keine Formalie, sondern verhindert, dass sich das Feld später doch
  einschleicht und für einen Momentanwert eine Auswertung behauptet
  (Begründung s. Punkt 1).

Wirkungsnachweis wie im Vorbild, für **beide** Tabellen: künstlich auf eine
Kopie angewandt, der ein Verknüpfungsfeld fehlt bzw. die ein unzulässiges
trägt — der Test muss dabei tatsächlich rot werden, sonst ist der Wächter
nur zufällig grün.

**3. Ableitungsfunktion (A2b):** Eine Funktion in `compare_html.py`, die aus
einer Liste sichtbarer Zeilen (bereits durch `_visible_metrics()` bzw. das
Stundentabellen-Äquivalent gefiltert) die Beschriftung berechnet:
`label = get_metric(row["metric_id"]).col_label`; kommt derselbe `col_label`
in der übergebenen Zeilenmenge mehrfach vor, wird jeder betroffenen Zeile
`" " + row["aggregation"]` angehängt (roher, kleingeschriebener Wert —
"max"/"min", keine Übersetzungstabelle nötig). Die Mehrfach-Erkennung ist
strukturell identisch zum bereits produktiven `mehrfach`-Muster in
`compare_outlook_metric_ids.py::outlook_columns()` (Zeilen 114-118) — **das
ist der in der Analyse geforderte, nachgenutzte Mechanismus, keine zweite
Kollisionslogik.** Die Stundentabelle durchläuft dieselbe Funktion, auch
wenn dort strukturell nie eine Kollision auftreten kann (alle 9 `metric_id`
sind paarweise verschieden) — kein Sonderfall im Code nötig.

**4. Klartext-Zwilling (A2b):** `_DAILY_PLAIN_ROWS`/`_PLAIN_ROWS` verlieren
ihr getipptes zweites Tupel-Element. Beide Fassungen der Mail (HTML,
Klartext) müssen für dieselbe Auswahl exakt dieselbe Beschriftung zeigen —
das ist nur garantiert, wenn `comparison.py` dieselbe Funktion aus
`compare_html.py` importiert und aufruft, statt eine eigene Kopie zu
pflegen (Purpose: „keine fünfte Kopie"). Wertquelle und Formatierung bleiben
unverändert (`_metric_value`/`_fmt_*`, bereits HTML-parallel seit #1359) —
nur die Beschriftung ändert sich.

## Expected Behavior

- **Input:** Ein Nutzer mit einer gespeicherten Metrik-Auswahl erhält einen
  Ortsvergleich per E-Mail (HTML und Klartext-Teil derselben Mail).
- **Output:** Übersichtstabelle und Stundentabelle zeigen für jede
  ausgewählte Größe die englische Kurzform aus dem zentralen Register
  (`col_label`), identisch in HTML und Klartext. Ist dieselbe Wettergröße
  mit zwei unterschiedlichen Auswertungen gleichzeitig ausgewählt (aktuell
  nur Temperatur max/min und Gefühlte Temperatur max/min möglich), wird die
  Auswertung klein angehängt ("Temp max"/"Temp min", "Feels max"/
  "Feels min"); ist nur eine der beiden gewählt, steht die reine Kurzform
  ohne Zusatz. Die Zahlenwerte je Zeile bleiben exakt wie vor dieser
  Umstellung — nur die Spaltenüberschrift ändert sich.
- **Side effects:** Referenziert eine Mail-Tabellenzeile künftig ein
  `metric_id`/`aggregation`-Paar, das im zentralen Katalog nicht auflösbar
  ist, deckt das der Vollständigkeits-Wächter auf (Testfehler mit
  benannter Zeile), statt dass die Zeile in der Mail lautlos ohne
  Beschriftung oder mit einer erfundenen erscheint.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer erhält eine Ortsvergleichs-Mail mit einer
  gespeicherten Metrik-Auswahl / When er die Übersichtstabelle und die
  Stundentabelle ansieht / Then zeigen beide Tabellen für jede Größe die
  englische Kurzform aus dem zentralen Register (z. B. "Wind" statt
  redaktionell unabhängig getippter Varianten), nicht mehr eine pro Tabelle
  eigenständig gepflegte Beschriftung.
  - Test: `tests/unit/test_compare_mail_label_source_catalog.py` (neu) —
    rendert Übersichts- und Stundentabelle für eine Auswahl ohne
    Kollisionsfall und prüft, dass jede Spaltenüberschrift dem
    `col_label` der zugehörigen zentralen Wettergröße entspricht.

- **AC-2:** Given eine gespeicherte, nicht-leere Metrik-Auswahl / When
  dieselbe Vergleichs-Mail als HTML **und** als Klartext gerendert wird /
  Then zeigen beide Fassungen für dieselbe Zeile dieselbe Beschriftung —
  keine Abweichung zwischen gestalteter Tabelle und ihrem
  Klartext-Zwilling.
  - Test: `tests/unit/test_compare_mail_plaintext_html_label_parity.py`
    (neu) — rendert `render_compare_html()` und `render_comparison_text()`
    aus demselben `ComparisonResult` und derselben Auswahl, vergleicht die
    Beschriftung Zeile für Zeile.

- **AC-3:** Given eine künftige Mail-Tabellenzeile nennt ihre zentrale
  Wettergröße nicht oder nicht auflösbar (Übersichtstabelle: `metric_id`
  **und** zulässige Auswertung; Stundentabelle: `metric_id`, ohne
  Auswertung — s. Implementation Details 1) / When der
  Vollständigkeits-Wächter läuft / Then schlägt er sichtbar fehl und
  benennt die betroffene Zeile — die Zeile erscheint nicht lautlos ohne
  oder mit erfundener Beschriftung in der Mail.
  - Test: `tests/unit/test_compare_mail_metric_link_completeness.py` (neu)
    — Kern-Test gegen die echten `CV2_METRICS`/`HOUR_METRICS`-Daten, plus
    Wirkungsnachweis gegen eine künstlich um eine Verknüpfung reduzierte
    Kopie (muss dabei tatsächlich rot werden, analog
    `test_compare_metric_catalog_consistency.py::test_guard_actually_fails_when_a_catalog_metric_has_no_cv2_row`).

- **AC-4:** Given eine Wettergröße mit zwei möglichen Auswertungen (z. B.
  Temperatur) / When nur eine der beiden Auswertungen in der Auswahl steht
  / Then zeigt die Mail die reine Kurzform ohne Zusatz ("Temp"). When
  **beide** Auswertungen gleichzeitig in derselben Tabelle sichtbar sind /
  Then bekommt jede der beiden Zeilen den rohen Auswertungs-Zusatz
  angehängt ("Temp max"/"Temp min") — genau in dem Moment, in dem die
  reine Kurzform die Zeilen sonst ununterscheidbar machen würde.
  - Test: `tests/unit/test_compare_mail_label_collision_suffix.py` (neu) —
    zwei Render-Läufe (nur eine Auswertung gewählt / beide gewählt) gegen
    dieselbe Wetterlage, prüft die jeweils erwartete Beschriftung.

- **AC-5:** Given eine gespeicherte Metrik-Auswahl mit realen Wetterdaten /
  When dieselbe Auswahl vor und nach dieser Umstellung gerendert wird /
  Then zeigen beide Ausgaben dieselben Zahlenwerte in denselben Zeilen (in
  derselben Reihenfolge) — nur die Spaltenüberschrift ändert sich, niemals
  der Wert.
  - Test: Erweiterung von `tests/unit/test_compare_extra_daily_metrics.py`
    und `tests/unit/test_compare_matrix_metric_selection.py` — bestehende
    Werte-Assertions bleiben unverändert bestehen, nur die
    Label-Erwartung wird auf die neue Beschriftung umgestellt (kein
    Wert-Regressionstest wird durch diese Lieferung entwertet).

## Known Limitations

- **`.claude/hooks/email_spec_validator.py` wird nicht angefasst** —
  Ticket #1404, eigener Workflow, muss **vor** A2b geliefert sein (s.
  Dependencies). Ziel-Literale für #1404, damit es diese Spec direkt
  übernehmen kann: `_HOUR_COLUMNS_V2` neu = `["Zeit","Temp","Feels","Wind",
  "Gust","Rain","UV","Thdr","Rain%","Visib"]`; `_OVERVIEW_METRIC_CHECKS`-
  Schlüssel: „Temp max" bleibt, „Wind" bleibt, „Sonne"→„Sun",
  „Wolken"→„Cloud", „UV max"→„UV".
- **`col_label`-Werte selbst bleiben unverändert** — insbesondere die
  schwer lesbaren „Cond°" (Taupunkt) und „0°Line" (Nullgradgrenze). Eine
  Überarbeitung träfe auch die Trip-Mail (`email/helpers.py:465-473`,
  `trip_report.py:503-524`, `email/html.py:1334`, `email/plain.py:293`) und
  ist bewusst ausgeklammert (identische Begründung wie A1).
  - **Renderer-Commit-Gate #811 greift pfadbasiert, nicht inhaltsbasiert**
  — `compare_html.py` liegt unter `src/output/renderers/email/*.py` und
  löst damit den Pflicht-Nachweis (mode-matrix-Test + Trip-
  `briefing_mail_validator.py`) auch dann aus, wenn inhaltlich nur die
  Compare-Tabellen betroffen sind. Beide Nachweise sind unabhängig vom
  compare-spezifischen `email_spec_validator.py`/#1404 zu erbringen.
- **Frontend-Listen Stundenverlauf/Alarme** bleiben unverändert — Scheibe
  B. **Begründung statt Leerstelle bei fehlenden Größen** — Scheibe C.
- **Kein neues Persistenzformat, keine Migration** — `active_metrics`
  bleibt exakt wie in #1373 Scheibe B beschrieben; diese Lieferung ändert
  nur, WIE die Beschriftung einer bereits gewählten Zeile berechnet wird,
  nicht die Auswahl-/Speicherlogik selbst.
- **Split A2a/A2b ist eine Liefer-, keine Scope-Entscheidung** (s.
  Estimated Scope) — beide Teile sind inhaltlich Bestandteil dieser Spec;
  ob sie als ein oder zwei Commits/Workflows geliefert werden, entscheidet
  der PO bei der Freigabe.

## ADR-Bezug

- **ADR-Nr.:** keine
- **Rationale:** Diese Spec setzt die in A1 dokumentierte, bereits
  freigegebene Kursänderung („Compare-Namen leiten sich aus dem zentralen
  Register ab statt redaktionell zu duplizieren") auf die Mail-Tabellen
  fort, ohne eine neue Grundsatzentscheidung zu treffen. Die
  Sprachentscheidung für die Kurzform (Englisch, PO 2026-07-27/2026-07-28)
  bestätigt lediglich die bereits bestehende #849/#862-Entscheidung und
  weitet sie auf den bislang abweichenden Ortsvergleich aus — kein neuer
  ADR-Auslöser (Kanäle, Provider, Datenmodell/Persistenz, Auth,
  Editor-Paradigma, Test-/Deploy-Strategie sind nicht betroffen).

## Changelog

- 2026-07-28b (Tech-Lead-Korrektur während TDD RED, keine AC-Erweiterung):
  Die 9 `HOUR_METRICS`-Zeilen bekommen **kein** `aggregation` — die
  ursprüngliche Fassung verlangte es pauschal für alle 35 Zeilen. Auslöser:
  Beim Schreiben des Wächters fiel auf, dass für einen Momentanwert keiner
  der zentral hinterlegten Auswertungswerte sachlich zutrifft; das Feld
  hätte dort eine Unwahrheit festgeschrieben, ohne je gelesen zu werden
  (Kollisions-Suffix greift bei 9 verschiedenen `metric_id` nie).
  Betroffen: Aufteilungstabelle, Estimated Scope, Implementation Details
  1+2, AC-3-Formulierung. Die geprüfte **Wirkung** von AC-3 (unverknüpfte
  Zeile schlägt sichtbar und benannt fehl) bleibt unverändert — der Wächter
  wird für die Stundentabelle sogar strenger, weil er ein
  fälschlich gesetztes `aggregation` jetzt aktiv zurückweist.
- 2026-07-28: Initial spec created (Fix #1401 Scheibe A2, Etappe
  S2-Nachzügler von Epic #1372/Dach #1374). Umfangsschätzung liegt deutlich
  über dem 250-Zeilen-Deckel (~500-760 Netto-Zeilen für den vollen
  A2-Umfang); Split-Empfehlung A2a ("Verknüpfungen nachtragen + Linkage-
  Wächter", ~140-200 Zeilen, unter dem Deckel, kein Validator-Risiko) /
  A2b ("Ableitung + Kollisionsregel", ~360-560 Zeilen, braucht #1404 UND
  vermutlich einen weiteren PO-Override oder Schnitt) dokumentiert, keine
  Schönrechnung vorgenommen.
