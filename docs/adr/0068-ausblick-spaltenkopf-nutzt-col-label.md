# ADR-0068: 3-Tages-Ausblick-Spaltenkopf nutzt `col_label` — vereinheitlicht mit der Etappentabelle

- **Status:** Akzeptiert
- **Datum:** 2026-09-15
- **Bezug:** GitHub-Issue #2136, PO-Ansage 2026-09-06, Epic #2133 (Leitsatz „ein Vokabular über
  alle Kanäle"), löst ADR-0037 Abschnitt „Verworfene Alternativen" (dritter Punkt) teilweise
  ab, löst die Zeile „3-Tages-Ausblick" in der Klasse-2-Tabelle von ADR-0042 ab. Spec
  `docs/specs/modules/fix_2136_outlook_col_label.md`, Kontext
  `docs/context/fix-2136-outlook-col-label.md`.

## Kontext

Der 3-Tages-Ausblick (HTML + Klartext, geteilter Baustein zwischen Trip-Briefing und
Ortsvergleich, `src/output/renderers/email/outlook.py`) hat zwei Renderpfade — und **keiner**
benutzt `MetricDefinition.col_label` aus dem zentralen Metrik-Katalog, obwohl die Etappentabelle
genau das bereits tut (`get_col_defs()` → `visible_cols()`):

- **Pfad 1** (Standardfall ohne Metrik-Auswahl): hartkodierte Kürzel `Tag · N · D · R · PR ·
  Wind · Böen · Gew` — eine eigene, handgepflegte Namensliste.
- **Pfad 2** (konfigurierbarer Ausblick, `outlook_columns()`): deutsche Langnamen aus
  `compare_metric_catalog.label`.

PO-Ansage 2026-09-06: „Die Tabellenüberschrift soll bei der E-Mail auch im 3-Tagesausblick
verwendet werden" — dieselbe Größe soll in Etappentabelle und Ausblick derselben Mail denselben
Namen tragen.

**Das widerspricht zwei früheren, wohlbegründeten Entscheidungen:**

- **ADR-0037** (27.07.2026) hat `col_label` als Ausblick-Spaltenkopf-Quelle bereits geprüft und
  im Abschnitt „Verworfene Alternativen" explizit verworfen: `temperature` liefert für
  min/max/avg identisch `"Temp"` — zwei gewählte Temperatur-Auswertungen ergäben zwei gleich
  beschriftete Spalten.
- **ADR-0042** (02.08.2026) ordnet den 3-Tages-Ausblick der Namensklasse „voll" (ausgeschriebene
  deutsche Form) zu, nicht der „Kurzform"-Klasse (`col_label`, englisch, ≤ 6 Zeichen) — obwohl
  der Ausblick baulich eine Tabelle mit Spaltenköpfen ist und damit ebenso gut in die
  Kurzform-Zeile passen würde. Diese Spannung stand bereits im ADR selbst.

**Was sich seit dem 27.07. geändert hat:** `outlook_columns()` hat durch zwei spätere,
unabhängige PO-Entscheidungen bereits eine generische Kollisions-Auflösung bekommen, die am
27.07. noch nicht existierte:

- `_merge_min_max_pairs()` (PO-Entscheid #1848 A1, 2026-08-20): sind für dieselbe Größe Min UND
  Max gewählt, werden sie zu **einer** Spannen-Spalte verschmolzen — keine Kollision.
- Der generische Duplikat-Check (aus #1401 A1): trägt ein verbleibendes Label-Duplikat (z. B. Avg
  neben einem gemergten Min/Max-Paar) `aggregation_label_de()` nach (z. B. „Temp Mittel").

Diese Mechanik arbeitet generisch auf dem Spaltenlabel, unabhängig davon, ob dort der
Compare-Katalog-Name oder `col_label` steht. Der technische Einwand aus ADR-0037 ist damit durch
später — aus anderem Anlass — gebaute Infrastruktur entkräftet, **nicht** durch neue
Katalogeinträge: Die zwischenzeitlich ergänzten `Night`/`DayMin`/`DayMax`-Einträge lösen die
Kollision nicht, da sie ohne `summary_fields` für den konfigurierbaren Ausblick gar nicht
wählbar sind (sie bedienen ausschließlich SMS/Kurzform, #1484/#1728).

## Entscheidung

1. **Der 3-Tages-Ausblick verwendet `MetricDefinition.col_label` als alleinige
   Spaltenkopf-Quelle** — HTML und Klartext, Pfad 1 und Pfad 2, Trip UND Ortsvergleich —
   dieselbe Quelle wie die Etappentabelle.
2. **Die bestehende Merge-/Dedup-Logik in `outlook_columns()` bleibt unverändert** die
   Kollisionsauflösung (Min/Max-Verschmelzung, Duplikat-Suffix). Kein neues Katalogfeld, kein von
   Grund auf neues Aggregations-Suffix-Schema.
3. **Im verbleibenden Restkollisionsfall** (z. B. Avg zusätzlich zu Min/Max gewählt) wird ein
   deutsches Aggregations-Wort (`aggregation_label_de()`) an das sonst englische `col_label`
   angehängt — akzeptierter Sprachmix (PO-Entscheid 2026-09-15), statt eines neuen, rein kurzen
   Suffix-Vokabulars, das laut ADR-0042 die „fünfte Namensliste" wäre.
4. **`kuerzel_metric_id` (#2232) bleibt ausschließlich SMS-Kürzel-Quelle** und wird für den
   Ausblick-Spaltenkopf nicht verwendet.
5. **Die Spalten-Legende (`build_column_legend`) wird auf die Ausblick-Spalten erweitert.**
   ADR-0042 verlangt die Auflösungspflicht bereits „in allen vier Ausgaben (Trip und
   Ortsvergleich, je HTML und Klartext)" — der Ausblick war hier lückenhaft umgesetzt, dieses
   ADR schließt die Lücke, führt aber keine neue Regel ein.

**Löst ab:**
- ADR-0037, Abschnitt „Verworfene Alternativen", dritter Punkt („Spaltenköpfe aus
  `metric_catalog.col_label`").
- ADR-0042, Klasse-2-Tabelle, Zeile „3-Tages-Ausblick": wandert von der Namensklasse „voll" in
  die Klasse „Kurzform".

## Verworfene Alternativen

- **Neues Katalogfeld je Aggregation** (z. B. `col_label_min`/`col_label_max`/`col_label_avg`).
  Verworfen: unnötig, weil die bestehende Merge-/Dedup-Logik das Kollisionsproblem bereits
  generisch löst; ein neues Feld wäre zusätzliche, ungenutzte Komplexität im Katalog.
- **Eigenes kurzes Aggregations-Suffix-Vokabular** (z. B. `TempMin`/`TempMax`/`TempAvg`, analog
  zu den bestehenden `Night`/`DayMin`/`DayMax`-Einträgen). Verworfen laut PO-Entscheid
  2026-09-15: erzeugt die von ADR-0042 ausdrücklich verworfene „fünfte Namensliste"; der seltene
  Sprachmix im Restfall wiegt geringer.
- **`kuerzel_metric_id` für den Ausblick-Spaltenkopf zweckentfremden.** Verworfen: verletzt die
  #2232-Invariante („nur SMS-Kürzel, nie Mail-Spaltenkopf").

## Konsequenzen

- **Positiv:** Eine Größe trägt in Etappentabelle und 3-Tages-Ausblick derselben Mail künftig
  dieselbe Beschriftung — Einheitlichkeit des Vokabulars über alle Kanäle (Epic #2133 Leitsatz),
  keine fünfte Namensliste.
- **Negativ / Preis:** Seltener Sprachmix im Temperatur-Mehrfachauswahl-Randfall
  („Temp Mittel"). `outlook.py` bleibt der Renderer-Baustein mit den meisten
  Fallunterscheidungen.
- **Folgepflichten:** `docs/specs/modules/issue_1361_1368_ausblick_konfigurierbar.md`
  (PO-Entscheidung 27.07.) wird mit „abgelöst durch #2136/ADR-0068" fortgeschrieben.
  `docs/reference/metric_output_matrix.md` Ausblick-Zeile fortschreiben. Wer künftig eine neue
  Ausgabefläche mit Tabellen-Spaltenköpfen baut, verwendet `col_label`, nicht ein eigenes Label —
  Präzedenzfall im Sinne von ADR-0042.
