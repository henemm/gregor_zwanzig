---
entity_id: fix_2136_outlook_col_label
type: feature
created: 2026-09-15
updated: 2026-09-15
status: draft
version: "1.0"
workflow: fix-2136-outlook-col-label
tags: [outlook, ausblick, mail, compare, metrik-katalog, col_label, adr-0068]
---

# 3-Tages-Ausblick nutzt col_label als Spaltenkopf — vereinheitlicht mit der Etappentabelle (Issue #2136)

## Approval

- [ ] Approved

## Purpose

Der 3-Tages-Ausblick der Trip-Briefing- UND Ortsvergleich-Mail (HTML + Klartext) trägt heute
zwei eigene, von der Etappentabelle unabhängige Namenslisten: der Standardfall ohne Metrik-Auswahl
hartkodierte deutsche Kürzel (`N`/`D`/`R`/`PR`/`Wind`/`Böen`/`Gew`), der konfigurierbare Fall
deutsche Langnamen aus `compare_metric_catalog.label`. PO-Ansage 2026-09-06: dieselbe Größe soll
in Etappentabelle und Ausblick derselben Mail denselben Namen tragen. Dieses Modul stellt beide
Ausblick-Renderpfade (HTML und Klartext) auf `MetricDefinition.col_label` aus dem zentralen
Metrik-Katalog um — dieselbe Quelle, die die Etappentabelle bereits über `get_col_defs()` →
`visible_cols()` verwendet — und löst dabei den Temperatur-Kollisionsfall (`temperature`
min/max/avg → identisch `"Temp"`) technisch auf, ohne ein neues Namensvokabular einzuführen.

> **Hinweis zur Quellenlage:** Der Original-Issue-Text (`gh issue view 2136`) konnte in dieser
> Session nicht abgerufen werden (kein Shell-Zugriff im Spec-Writer-Agenten). Diese Spec stützt
> sich stattdessen auf das vollständige Analyse-Dokument `docs/context/fix-2136-outlook-col-label.md`
> (das den Issue-Wortlaut, die PO-Ansage 2026-09-06 und die PO-Entscheidungen 2026-09-15 bereits
> zitiert) und auf `docs/adr/0068-ausblick-spaltenkopf-nutzt-col-label.md`. Die sieben
> Acceptance Criteria unten sind aus diesen beiden Quellen sowie aus einer eigenen Code-Prüfung
> rekonstruiert, nicht wörtlich aus dem Issue kopiert. **Vor Freigabe bitte gegen den echten
> Issue-Text gegenlesen.**

## Source

- **File:** `src/output/renderers/email/outlook.py`
- **Identifier:** `render_outlook_table()` (HTML, Pfad 1 Z.206–218 fest / Pfad 2 Z.160–166
  konfigurierbar), `render_outlook_plain()` (Klartext, Pfad 1 Z.376–379 fest / Pfad 2 Z.331–344
  konfigurierbar)
- **File:** `src/output/renderers/compare_outlook_metric_ids.py`
- **Identifier:** `outlook_columns()` Z.298–372 (Label-Quelle Z.346, Duplikat-Suffix Z.367–371),
  `_merge_min_max_pairs()` Z.375ff

> **Schicht-Hinweis:** Alle betroffenen Dateien liegen im Python-Core (`src/app/`,
> `src/output/renderers/`), FastAPI-Domäne über `api.main:app`. Keine Berührung von Go-API
> (`internal/`, `cmd/`) oder Frontend (`frontend/src/`) — reine Renderer-Änderung ohne neues
> Datenmodell-Feld.

## Estimated Scope

- **LoC:** ~250–400 (gemischt: reiner Produktionscode klein ~40–60 LoC, Tests/Fixtures/Doku
  dominieren — ADR bereits geschrieben, zählt nicht mehr in diesen Workflow)
- **Files:** 10–11 (Produktionscode 3, Tests 3, Golden-Fixtures 2 Verzeichnisse à 2–3 Dateien,
  Referenz-Doku 1)
- **Effort:** medium (fachlich einfache Label-Quellen-Umstellung, aber zwei Renderpfade × zwei
  Kanäle × zwei Mail-Arten plus bewusste Golden-Fixture-Nachführung)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `outlook_columns()` (`src/output/renderers/compare_outlook_metric_ids.py:298`) | function | Label-Quelle des konfigurierbaren Ausblick-Pfads (Pfad 2); Z.346 liefert künftig `MetricDefinition.col_label` statt `compare_metric_catalog.label` |
| `_merge_min_max_pairs()` / Duplikat-Suffix-Schleife (`compare_outlook_metric_ids.py:366–421`) | function | Bestehende Kollisionsauflösung, bleibt UNVERÄNDERT — arbeitet generisch auf `columns[i]["label"]`, unabhängig von der Label-Quelle (ADR-0068 Entscheidung 2) |
| `MetricDefinition` / `get_col_defs()` (`src/app/metric_catalog.py:29`, `:1498`) | class/function | Zentrales Register; `col_label` ist bereits die Quelle der Etappentabellen-Spaltenköpfe — dieses Modul zieht den Ausblick auf dieselbe Quelle |
| `aggregation_label_de()` (`src/app/metric_catalog.py`) | function | Deutsches Aggregations-Suffix-Wort (z. B. „Mittel"); bereits von der Duplikat-Suffix-Schleife in Pfad 2 genutzt, wird in diesem Modul zusätzlich für den statischen Temperatur-Kollisionsfall in Pfad 1 verwendet (kein neues Vokabular) |
| `build_column_legend()` / `visible_cols()` (`src/output/renderers/email/helpers.py:262`, `:560`) | function | Vorbild „richtig gemacht" für die Etappentabelle; wird in diesem Modul auf die Ausblick-Spalten erweitert (bisher nur `seg_tables`, Ausblick-Spalten fehlen in der Legende) |

## Implementation Details

### Pfad 2 — konfigurierbarer Ausblick (`outlook_columns()`, HTML + Klartext, Trip UND Compare)

`compare_outlook_metric_ids.py:346` liefert `"label": catalog["label"]` (aus
`compare_metric_catalog`, deutsch). Umstellung auf `MetricDefinition.col_label` für dieselbe
`(metric_id, aggregation)`-Kombination. Der Docstring-Kommentar Z.310–315, der die heutige
Ablehnung von `col_label` begründet, wird durch die ADR-0068-Begründung ersetzt (Merge-/
Dedup-Logik entkräftet den ursprünglichen Einwand). `_merge_min_max_pairs()` und die
Duplikat-Suffix-Schleife (Z.366–371) bleiben unverändert — sie lesen nur `column["label"]`,
unabhängig davon, welche Quelle den Wert eingetragen hat. `render_outlook_table()`
(`outlook.py:160–166`) und `render_outlook_plain()` (`outlook.py:331–344`) übernehmen
`c["label"]`/`c['label']` unverändert aus `outlook_columns()` — hier ist keine Code-Änderung
nötig, der Effekt entsteht allein durch die Quellenumstellung in Pfad 2.

### Pfad 1 — Standardfall ohne Auswahl (`outlook.py`, HTML Z.206–218 + Klartext-Pendant)

Dieser Pfad ruft `outlook_columns()` **nicht** auf — die sieben Kürzel sind literal im HTML-
`thead` (Z.209–215) sowie implizit in der Klartext-Zeilenformatierung kodiert. Die
Merge-/Dedup-Mechanik aus Pfad 2 greift hier strukturell nicht. Fünf der sieben Kürzel
(`R`/`PR`/`Wind`/`Böen`/`Gew`) sind je Größe eindeutig und werden 1:1 durch ihr `col_label`
ersetzt. Die beiden Temperatur-Kürzel (`N`=Minimum, `D`=Maximum) sind der statische
Sonderfall: eine naive Ersetzung durch `col_label` der Größe `temperature` erzeugt **zwei
Spalten mit identischem Kopf `"Temp"`** — exakt der in ADR-0037/ADR-0068 beschriebene
Kollisionsfall, hier aber **statisch**, weil Pfad 1 immer genau eine Minimum- und eine
Maximum-Spalte führt und diese laut Abgrenzung (s. u.) nicht zu einer Spannen-Spalte
zusammengeführt werden dürfen (das wäre eine Layout-Änderung, Spaltenzahl bliebe nicht bei
acht). Auflösung: dieselbe Suffix-Mechanik wie in Pfad 2 wird direkt angewendet — die
Minimum-Spalte trägt `col_label("temperature") + " " + aggregation_label_de("min")`, die
Maximum-Spalte entsprechend `aggregation_label_de("max")` (z. B. `"Temp Min"` / `"Temp Max"`).
Kein neues Suffix-Vokabular — derselbe Import (`aggregation_label_de`), dieselbe Wortquelle wie
in Pfad 2. `Tag` bleibt unverändert, ist kein Katalogfeld. Ergebnis: alle sieben Nicht-`Tag`-
Spalten wandern auf `col_label`-Quelle, die Gesamtspaltenzahl bleibt bei acht (`Tag` + 7).

### Legende (AC-5)

`build_column_legend()` (`helpers.py:560–581`) löst heute ausschließlich `visible_cols(seg_tables)`
auf, nicht die Ausblick-Spalten. Der Aufbau wird um die im Ausblick tatsächlich sichtbaren
Spaltenköpfe erweitert (Pfad 1: die sieben Kürzel-Ersetzungen inkl. der beiden
Temperatur-Suffix-Varianten; Pfad 2: die Spalten aus `outlook_columns()`), nach derselben Regel
wie ADR-0042 („auflösen, außer Kürzel und ausgeschriebener Name sind identisch"). Aufrufer
`email/html.py:1673–1675` und `email/plain.py:384` übergeben zusätzlich die Ausblick-Zeilen/-Spalten
an die Legendenbildung.

### Golden-Fixture-Nachführung (bewusste, dokumentierte Abweichung)

`tests/fixtures/outlook_trip_parity/` (genutzt von `tests/tdd/test_trip_outlook_parity.py`,
Paritäts-Wächter „Trip-Mail ändert sich in keinem Byte") und
`tests/fixtures/trip_outlook_reference/` (genutzt von `tests/helpers/trip_outlook_selection.py`)
enthalten aufgezeichnete HTML-/Klartext-Referenzen mit dem heutigen `Tag N D R PR Wind Böen Gew`-
Kopf. Diese Änderung ist die **erste beabsichtigte** Byte-Abweichung der Trip-Mail seit Bestehen
dieses Wächters (bisherige Ausnahme 2026-08-14 betraf nur Farbwerte, keinen Text). Beide
Fixture-Verzeichnisse werden nach demselben Muster wie die 2026-08-14-Ausnahme manuell
nachgezogen (Werkzeug `python -m tests.helpers.trip_outlook_selection --force` bzw. äquivalent
für `outlook_trip_parity`) und die Abweichung in den jeweiligen `README.md` dokumentiert
(„Nachgeführte Zellen"-Tabelle, Muster bereits etabliert). Die Erwartungswerte in den
Acceptance-Criteria-Tests unten werden **nicht** gegen diese Golden-Dateien selbst abgeleitet
(das würde nur die Fixture gegen sich selbst prüfen), sondern gegen `get_col_defs()`/`col_label`
direkt — die Golden-Dateien bleiben ausschließlich der Paritäts-Wächter für alles andere
(Werte, Layout, Zellenformatierung), das unverändert bleiben muss.

## Expected Behavior

- **Input:** Trip-Briefing-Mail und Ortsvergleichs-Mail (HTML + Klartext), 3-Tages-Ausblick-Block,
  mit und ohne konfigurierte `outlook_metrics`-Auswahl.
- **Output:** Jede Spaltenüberschrift im Ausblick ist identisch zur Spaltenüberschrift derselben
  Größe in der Etappentabelle (`MetricDefinition.col_label`), inklusive Temperatur-Sonderfall mit
  unterscheidbaren Köpfen. Die Spalten-Legende führt die im Ausblick sichtbaren Kürzel mit auf.
- **Side effects:** Kollateralwirkung auf Kurzform-Mail (`email/compact.py`) und Telegram
  (`renderers/narrow.py`), die dieselbe `outlook_columns()`-Quelle lesen und die neue Labelquelle
  automatisch erben (kein eigener Codepfad, keine gesonderte Änderung nötig).

## Acceptance Criteria

- **AC-1:** Given eine Ortsvergleichs- oder Trip-Mail (HTML) mit konfigurierter
  `outlook_metrics`-Auswahl (Pfad 2, `outlook.py:160–166` über `outlook_columns()`,
  `compare_outlook_metric_ids.py:346`) / When der Ausblick-Block gerendert wird / Then trägt
  jede Spalte denselben `col_label`-Text wie die gleichnamige Größe in der Etappentabelle
  derselben Mail, nicht mehr den deutschen Langnamen aus `compare_metric_catalog.label`.
  - Test: `render_compare_email()`/Trip-Renderpfad mit gesetzter Auswahl, BeautifulSoup liest
    `<th>`-Texte des Ausblicks UND der Etappentabelle, vergleicht je Größe.

- **AC-2:** Given eine Ortsvergleichs- oder Trip-Mail (HTML) OHNE konfigurierte Auswahl
  (Pfad 1, `outlook.py:206–218`, heute `Tag N D R PR Wind Böen Gew`) / When der Ausblick-Block
  gerendert wird / Then sind alle sieben Nicht-`Tag`-Kürzel durch das `col_label` der jeweiligen
  Katalog-Größe ersetzt — `R`/`PR`/`Wind`/`Böen`/`Gew` direkt, `N`/`D` mit dem
  Aggregations-Suffix nach AC-7 — `Tag` bleibt unverändert, die Spaltenzahl bleibt bei acht.
  - Test: BeautifulSoup liest die `<th>`-Texte des Standardfall-Ausblicks, vergleicht gegen
    `get_col_defs()`-Werte für `precipitation`/`rain_probability`/`wind`/`gust`/`thunder` sowie
    gegen die AC-7-Erwartung für die beiden Temperaturspalten.

- **AC-3:** Given eine Ortsvergleichs- oder Trip-Mail (Klartext) mit konfigurierter Auswahl
  (Pfad 2, `render_outlook_plain()` Z.331–344) / When der Ausblick-Block gerendert wird / Then
  trägt jedes Werte-Token dasselbe `col_label`-Präfix wie die Spalte der Etappentabelle für
  dieselbe Größe.
  - Test: Klartext-Ausgabe des konfigurierten Ausblicks, Zeilen-Tokens gegen `col_label`
    verglichen, Vergleich mit dem Klartext-Etappentabellen-Kopf derselben Mail.

- **AC-4 (korrigiert in TDD-RED, 2026-09-15 — ursprüngliche Fassung war widersprüchlich):**
  Given eine Ortsvergleichs- oder Trip-Mail (Klartext) OHNE konfigurierte Auswahl (Pfad 1,
  `render_outlook_plain()`) / When der Ausblick-Block gerendert wird / Then trägt **jedes
  tatsächlich gerenderte Token** die `col_label`-Überschrift seiner Größe — die Temperatur
  bleibt als **eine** Spanne ohne Auswertungs-Suffix, weil Pfad 1 Klartext Tief/Hoch strukturell
  bereits zu einem Token zusammenführt (kein AC-7-Suffix im Klartext, nur im HTML). Die
  ursprüngliche Formulierung „dieselben sieben Kürzel wie AC-2, identische Reihenfolge zum
  festen Format" ist für Pfad 1 Klartext **nicht erfüllbar**: Der Renderpfad zeigt tatsächlich
  nur vier Tokens (Temperatur-Spanne, Niederschlag, Wind, Gewitter) — Regenwahrscheinlichkeit
  und Böen kommen dort gar nicht vor. Diese Fassung ersetzt die ursprüngliche.
  - Test: Klartext-Ausgabe des Standardfall-Ausblicks, jedes gerenderte Token gegen
    `get_col_defs()`/`col_label`-Werte verglichen (nicht gegen die gleichzeitig nachgezogene
    Golden-Datei selbst — die bleibt der separate Paritäts-Wächter für Werte/Layout).

- **AC-5:** Given eine Mail mit sichtbarem Ausblick-Block (HTML oder Klartext, Trip oder
  Ortsvergleich) / When die Spalten-Legende gerendert wird / Then löst sie zusätzlich zu den
  Etappentabellen-Kürzeln auch die im Ausblick tatsächlich sichtbaren Kürzel auf (Regel aus
  ADR-0042: auflösen, außer Kürzel und Langname sind identisch).
  - Test: Mail mit Ausblick-Größe, deren `col_label` vom `label_de` abweicht (z. B. `Gust`),
    Legenden-Zeile unter der Mail enthält `Gust = <label_de-Wert>`.
  - **Hinweis aus TDD-RED (2026-09-15):** Der einzige echte Rot-Nachweis läuft über den
    Ortsvergleich (`compare_html._column_legend_text`). Die **Trip**-Legende (`build_column_legend()`,
    Aufrufer `email/html.py:1673–1675`, `email/plain.py:384`) ist bereits über-inklusiv — sie
    listet Kürzel auch dann, wenn die zugehörige Spalte in der konkreten Mail gar nicht sichtbar
    ist — wodurch sich dort kein gezielter Wirkort-Rot-Test konstruieren ließ. **Pflicht für
    Phase 6/Adversary:** nach der Implementierung manuell (oder mit Staging-Mail) verifizieren,
    dass die Trip-Legende nach der Umstellung weiterhin die Ausblick-Kürzel korrekt auflöst —
    diese RED-Testreihe bewacht nur die Compare-Seite.

- **AC-6 (Temperatur-Kollision, konfigurierbarer Ausblick):** Given eine Ortsvergleichs-Mail mit
  `outlook_metrics`-Auswahl `temperature` mit den drei Aggregationen min, max UND avg gleichzeitig
  gewählt (Pfad 2) / When `outlook_columns()` die Spalten baut / Then verschmilzt Min+Max zu einer
  Spannen-Spalte (`_merge_min_max_pairs()`, unverändert) und die verbleibende Avg-Spalte trägt
  `col_label("temperature") + " " + aggregation_label_de("avg")` (z. B. `"Temp Mittel"`) — kein
  Spaltenkopf-Duplikat, keine zwei Spalten mit identischem Text `"Temp"`.
  - Test: Neue TDD-Datei (Regressionstest, RED zuerst), Auswahl mit drei
    Temperatur-Aggregationen, `<th>`-Texte des gerenderten Ausblicks enthalten `"Temp"` (Spanne)
    und `"Temp Mittel"` als zwei unterscheidbare Strings, nie zweimal denselben Text.

- **AC-7 (Temperatur-Kollision, Standardfall-Ausblick):** Given eine Trip- oder
  Ortsvergleichs-Mail OHNE konfigurierte Auswahl (Pfad 1, Standardfall mit fest verdrahteten
  Minimum-/Maximum-Temperaturspalten `N`/`D`) / When der Ausblick-Block gerendert wird / Then
  tragen die beiden Temperaturspalten unterscheidbare Köpfe (`"Temp Min"`/`"Temp Max"` oder
  äquivalent aus `col_label` + `aggregation_label_de()`), nicht zweimal denselben Text `"Temp"`,
  UND die beiden Spalten bleiben strukturell getrennt (keine Zusammenführung zu einer
  Spannen-Spalte — das wäre eine Layout-Änderung außerhalb des Scopes dieses Fixes).
  - Test: Neue TDD-Datei (Regressionstest, RED zuerst), Standardfall-Ausblick (keine Auswahl
    gesetzt), `<th>`-Texte an Position von `N` und `D` sind zwei unterscheidbare Strings, beide
    enthalten `"Temp"` als Präfix; Spaltenanzahl bleibt bei acht (`Tag` + 7) wie bisher.

- **AC-8 (Ableitung statt Doppelpflege, Mutations-Gegenprobe):** Given ein `col_label`-Wert einer
  Ausblick-Größe im Metrik-Katalog wird verfälscht (z. B. `temperature.col_label` von `"Temp"` auf
  einen Testwert geändert) / When die Ausblick-Tests aus AC-1/AC-2 laufen / Then werden sie rot,
  weil der Ausblick-Kopf direkt aus dem Katalogfeld abgeleitet ist und nicht mehr an einer
  zweiten, unabhängigen Stelle steht — belegt, dass Pfad 1 UND Pfad 2 nach diesem Fix keine eigene
  Namensliste mehr führen.
  - Test: Fixture/Monkeypatch verändert `MetricDefinition.col_label` für eine im Ausblick
    sichtbare Größe zur Testzeit; derselbe Assertion-Block wie in AC-1/AC-2 muss mit dem
    verfälschten Wert übereinstimmen (nicht mit dem alten Literal) — schlägt fehl, falls
    irgendwo noch ein hartkodiertes Kürzel übrig ist.

## Known Limitations

- **AC-6-Szenario ist heute über keinen Nutzerweg erreichbar (TDD-RED-Befund 2026-09-15):**
  `derived_aggregations("temperature")` liefert nach #1848 A2 nur `['min','max']`, weil der
  Compare-Katalog keine `avg`-Zeile für Temperatur führt — drei gleichzeitig gewählte
  Temperatur-Aggregationen lassen sich über die UI heute nicht herstellen. Der zugehörige Test
  injiziert die fehlende Katalogzeile testweise und bewacht damit die Mechanik defensiv für eine
  künftige Katalog-Erweiterung, reproduziert aber keinen heute auslösbaren Defekt.
- **Akzeptierter Sprachmix im Temperatur-Restkollisionsfall (PO-Entscheid 2026-09-15):** Wird
  zusätzlich zu Min/Max eine dritte Temperatur-Aggregation gewählt (z. B. Avg), hängt ein
  deutsches Aggregations-Wort (`aggregation_label_de()`, z. B. „Mittel") an ein sonst englisches
  `col_label` (z. B. „Temp"), Ergebnis „Temp Mittel". Bewusst akzeptiert statt eines neuen,
  rein-englischen Suffix-Vokabulars (das wäre laut ADR-0042 die „fünfte Namensliste").
- **Kollateralwirkung auf Kurzform-Mail und Telegram:** `email/compact.py` und
  `renderers/narrow.py` lesen dieselbe `outlook_columns()`-Quelle und erben die neue Labelquelle
  automatisch, ohne eigenen Codepfad in diesem Modul. Das ist mit CLAUDE.md „alle vier Kanäle
  gleichrangig relevant, ein Vokabular" konsistent, wird hier aber nur als Konsequenz dokumentiert,
  nicht gesondert getestet — kein neuer Testfall für diese beiden Dateien in diesem Fix.
- **Ortsvergleich ist mitbetroffen** (PO-Entscheid 2026-09-15: in Ordnung für dieses Ticket, kein
  Konflikt mit der Projektregel „Ortsvergleich-Themen sind zurückgestellt", weil Issue #2136
  ausdrücklich „Trip UND Ortsvergleich" verlangt und die Architektur strukturell geteilt ist).
- **Abgrenzung:** Diese Änderung betrifft ausschließlich Spaltenüberschriften (Text der `<th>`-
  Zellen bzw. Klartext-Präfixe). Werte, Spaltenreihenfolge, Zellenformatierung, Farbschwellen und
  Layout (Spaltenanzahl, Tabellenstruktur) bleiben unverändert — mit der einen dokumentierten
  Ausnahme, dass Pfad 1 zwei zuvor identisch benennbare Temperaturspalten (`N`/`D`) jetzt
  unterscheidbare Köpfe trägt (AC-7), ohne dass sich ihre Zahl oder Reihenfolge ändert.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0068
- **Rationale:** ADR-0068 (`docs/adr/0068-ausblick-spaltenkopf-nutzt-col-label.md`) legt fest,
  dass der 3-Tages-Ausblick `MetricDefinition.col_label` als alleinige Spaltenkopf-Quelle
  verwendet — HTML und Klartext, Pfad 1 und Pfad 2, Trip UND Ortsvergleich —, dass die bestehende
  Merge-/Dedup-Logik in `outlook_columns()` unverändert bleibt, und dass im Temperatur-
  Restkollisionsfall ein akzeptierter Sprachmix (`aggregation_label_de()`-Suffix an englisches
  `col_label`) statt eines neuen Suffix-Vokabulars steht. Diese Spec setzt genau diese
  Entscheidung um und löst zusätzlich, technisch nicht in ADR-0068 im Detail ausgeführt, den
  strukturell separaten Kollisionsfall in Pfad 1 (AC-7) nach derselben Suffix-Logik.
  ADR-0068 löst seinerseits ADR-0037 (Abschnitt „Verworfene Alternativen", dritter Punkt) und
  ADR-0042 (Klasse-2-Tabelle, Zeile „3-Tages-Ausblick") teilweise ab — beide ADR-Dateien tragen
  bereits die entsprechende Teil-Ablösungszeile. `docs/specs/modules/issue_1361_1368_ausblick_konfigurierbar.md`
  ist bereits mit „abgelöst durch #2136/ADR-0068" fortgeschrieben (Z.194–205). Nach der
  Implementierung ist zusätzlich `docs/reference/metric_output_matrix.md` (Ausblick-Zeile) fortzuschreiben.

## Changelog

- 2026-09-15: Initial spec created (Issue #2136, ADR-0068)
