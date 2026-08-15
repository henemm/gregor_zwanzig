---
entity_id: fix_1841_vorschau_metrik_tagesfenster
type: bugfix
created: 2026-08-14
updated: 2026-08-14
status: approved
version: "1.0"
tags: [gewitter, ausblick, vorschau, tagesfenster, metrik-zweig, issue-1841]
---

<!-- Issue #1841. Grundlage: PFLICHTLEKTUERE
     docs/context/fix-1841-ausblick-metrik-tagesfenster.md (am Stand
     `e6303c75` gemessen, nach Rebase auf `57e36375` nachgeprueft). ACHTUNG:
     #1594 (im Rebase enthalten) hat `trip_report_scheduler.py` verschoben —
     der Aufruf steht jetzt bei `:2282`, nicht mehr bei `:2200`. Die
     Renderer-Dateien sind unveraendert. Vorbilder:
     docs/specs/modules/fix_1671_kompaktmail_ausblick_tagesfenster.md
     (liefert den geteilten Helfer) und
     docs/specs/modules/fix_1653_ausblick_tag_nacht_trennung.md (dessen
     AC-6 den Ortsvergleich schuetzt). -->

# #1841 — 3-Tages-Vorschau: Gewitterspalte liest das falsche Zeitfenster

## Approval

- [x] Approved — PO-go 2026-08-15 (Klartext-Freigabe der neun ACs
      auf Deutsch). Zugleich gesetzt: keine Nachtangabe im Metrik-Zweig
      (Tagesfenster wie SMS), Ampelfarben als eigenes Issue #1849.

## Purpose

Setzt ein Nutzer im Trip-Editor unter **Wertebereiche → 3-Tages-Vorschau**
eine Spaltenauswahl und waehlt darin die Spalte **Gewitter**, zeigt die
3-Tages-Tabelle der Trip-Mail die Gewitterstufe aus dem auf die Gehzeit
geklemmten Tages-Aggregat statt aus dem konfigurierten **Tagesfenster**.
Ein reales Tagesgewitter kann dadurch verschwinden (falsch-negativ) oder
ein nicht vorhandenes behauptet werden (falsch-positiv) — dieselbe
Fehlerklasse, die #1653 fuer die damaligen Ausgabeorte behoben hat und
#1671 fuer die Kurzformat-Mail.

Diese Scheibe macht den Metrik-Zweig zum **vierten Aufrufer** des mit
#1671 gelieferten geteilten Helfers `resolve_thunder_day_branch()` —
statt eine vierte eigene Aufloesung derselben Frage zu bauen (ADR-0055).

## Source

- Issue #1841 (Label `bug`, `priority:high`, `session:khw`)
- Ursache: #1720 S1 (PR #1840, gemerged 2026-08-14) hat den bis dahin
  compare-exklusiven Metrik-Renderpfad fuer den Trip geoeffnet, ohne die
  Voraussetzung der damaligen Compare-Entscheidung mitzupruefen: der Trip
  **hat** eine Stundenreihe, und sein Aggregat **ist** gehzeit-geklemmt.

  🔴 Das ist belegt, nicht hergeleitet: `feat_1680_s5a` haelt unter „Am Code
  gemessen" Punkt 8 (`:440-444`, PO-go 2026-08-13) fest, der Metrik-Zweig sei
  **compare-exklusiv**, „der Trip ruft die Ausblick-Renderer immer mit
  `metrics=None` (`html.py:1357`, `plain.py:338`)". Am 2026-08-13 war das
  wahr. **Einen Tag spaeter** hat #1720 S1 genau diese Voraussetzung
  aufgehoben — `html.py:1364` und `plain.py:344` uebergeben seither
  `metrics=_outlook_metrics` auch fuer den Trip. Der Fehler entstand also
  nachweislich beim Ausweiten des Zweigs und war nicht schon vorher da.
  (Diese Spec-Zeile wird als Erratum korrigiert, siehe Implementation
  Details §5.)
- Vorgaenger: #1653 (drei Ausgabeorte umgestellt), #1671 (Kurzformat-Mail,
  liefert den geteilten Helfer), #1680 S5a (Herkunft der Gewitterstufe).
- Abgetrennt: #1849 (fehlende Ampelfarben im selben Renderpfad).

## Estimated Scope

| Was | Umfang |
|---|---|
| Produktivdateien | 2 (`outlook.py`, `helpers.py`), ~+40/−5 LoC |
| Testdateien | 1 Anpassung (Testhelfer), 1 neue Verhaltensdatei, ~+150 LoC |
| Dokumentation | 2 Korrekturen (zaehlen nicht aufs LoC-Budget) |
| LoC-Budget | 250 Produktiv / 500 Test — beides ausreichend, keine Anhebung noetig |
| Risiko | MEDIUM |

## Dependencies

- **Upstream:** `format_trend_tokens()` (`helpers.py`), `resolve_thunder_day_branch()`
  (`thunder_branch.py:54`), `union_of_max_carriers()` (`thunder_scale.py:118`),
  `thunder_label_value()`, `resolve_configured_window()`.
- **Downstream:** Trip-Vollmail HTML (`html.py:1364`) und Klartext
  (`plain.py:344`). Der Ortsvergleich (`compare_html.py:1242`,
  `comparison.py:360`) nutzt denselben Baustein und **muss unveraendert
  bleiben**.
- `build_outlook_row()` ist der einzige bewusst geteilte Trip/Compare-Baustein
  (`tests/unit/test_notification_service.py:191` fuehrt genau diesen Import
  als erlaubte Ausnahme).

## Am Code gemessen

Alle Angaben am Stand `57e36375` nachgeprueft, nicht aus dem Ticket uebernommen.

1. **Die falsche Quelle.** `outlook.py:581-587` baut `row["cells"]` ueber
   `getattr(summary, col["field"], None)`. Fuer die Gewitterspalte ist
   `col["field"]` gleich `thunder_level_max` — das gehzeit-geklemmte
   Aggregat. `thunder_day_token` wird in diesem Zweig nie gelesen.

2. **Der Diskriminator existiert bereits.** Genau **zwei** Produktionsaufrufer
   von `build_outlook_row()`, sauber getrennt (unabhaengig gegengeprueft):
   - Trip: `trip_report_scheduler.py:2282` — setzt immer
     `trip_display_config=dc`, `report_type=…`, `day_window_start_hour`,
     `day_window_end_hour`; setzt **nie** `metrics=`.
   - Ortsvergleich: `compare_html.py:1168` — setzt immer `metrics=…`;
     setzt **nie** `trip_display_config` und **kein** Tagesfenster.

   Keine dritte Fundstelle in `api/`, `sms_trip.py` oder Vorschau-Endpunkten.

3. **Der Fix passt in `build_outlook_row()`.** `format_trend_tokens(stage)`
   ist eine reine Funktion des Zeilen-Dicts und liest ausschliesslich
   Schluessel, die in `row` bereits stehen, bevor der Metrik-Zweig bei
   `:564` beginnt (`row.update(optional)` bei `:562`). Eine Korrektur dort
   erledigt HTML **und** Klartext in einem Zug — an den beiden Renderstellen
   waeren es zwei Kopien.

4. **Die Zelle braucht ein `ThunderLevel`, keinen Token-String.**
   `format_outlook_value()` erkennt die Gewitterspalte an `kind == "ordinal"`
   (`compare_outlook_metric_ids.py:164-166`) und reicht den Wert an
   `_fmt_thunder(level, hail, signals)` durch. `thunder_day_token` ist
   dagegen ein String der Form `"mittel@14(hoch@17)"`.

5. **`row["hourly_thunder_signals"]` ist unzuverlaessig als Stufenquelle.**
   Es ist `None`, sobald **kein** Datenpunkt eine Traegerliste fuehrt
   (`outlook.py:553-560`, Alt-Schnappschuesse vor #1680 S1).
   `row["hourly_thunder"]` ist dagegen immer befuellt, traegt die Stufe
   aber als Fliesskommazahl ueber `thunder_label_value()`.

6. **🔴 Aggregat und Stundenreihe stammen aus VERSCHIEDEN weit gefassten
   Datensaetzen — das ist die Ursache und zugleich die Testbedingung.**
   Im selben Aufruf `build_outlook_row(agg, _flat_points, …)`
   (`trip_report_scheduler.py:2282`) gilt:
   - `agg` (→ `summary`, Quelle der heutigen Zelle) ist auf die **Gehzeit**
     geklemmt: `segment_weather.py:264-281` filtert die Reihe auf
     `segment.start_time … segment.end_time` und aggregiert **nur** darueber.
   - `_flat_points` (→ `hourly_thunder`, Quelle des Tagesfensters) ist die
     **ungefilterte Ganztagsreihe** (`trip_report_scheduler.py:2258`:
     `sw.timeseries.data`; `segment_weather.py:239` haelt ausdruecklich fest,
     die ungefilterte Reihe bleibe „for table display" erhalten).

   Faellt die Gehzeit mit dem Tagesfenster zusammen, sind beide Rechnungen
   deckungsgleich und eine Fixture waere von einem No-Op nicht
   unterscheidbar — der Test bliebe nach jeder Mutation gruen.

7. **SMS macht es bereits genau so.** `sms_trip.py:303-323` baut die
   Gewitter-Stundenreihe ausschliesslich aus
   `build_day_window_points(start_hour=…, end_hour=…)` — rein Tagesfenster,
   ohne jede Nachtangabe. Die PO-Vorgabe „so wie auch fuer SMS" ist damit
   am Code belegt, nicht nur behauptet.

8. **Zwei Bestandstests umreissen den Korridor.**
   - `test_outlook_day_night_thunder_split.py:665` verlangt, dass
     `row["cells"]` mit und ohne `day_window_*` identisch bleibt —
     aufgerufen mit `metrics=` und ohne `trip_display_config`. Der Test
     stellt gezielt die Falle, am Tagesfenster statt am Trip-Diskriminator
     anzusetzen. Ein korrekter Fix laesst ihn gruen.
   - `test_outlook_day_night_thunder_split.py:645` ruft
     `render_outlook_plain()` mit vorgefertigten `rows` und beruehrt
     `build_outlook_row()` nie. Er bleibt gruen, gleichgueltig ob der Fix
     richtig oder falsch ist — **kein Nachweis fuer diese Scheibe** und in
     der Adversary-Runde nicht als solcher zu zitieren.

9. **Der Testhelfer prueft heute den falschen Pfad.**
   `tests/helpers/trip_outlook_selection.py:163` baut die Ausblick-Zeilen
   mit `build_outlook_row(..., metrics=metrics)` — der **Compare**-Konvention
   — und behauptet im Docstring (`:155-157`), das sei der Parameter, den der
   Zeitplaner fuellt. Gemessen fuellt `trip_report_scheduler.py:2282`
   stattdessen `trip_display_config`/`report_type`. Die gesamte
   #1720-S1-Renderer-Suite faehrt den Metrik-Zweig damit ueber den
   Compare-Weg. `test_trip_outlook_metric_selection.py:17-20` benennt diese
   Grenze selbst; ADR-0055 (`:167-171`) warnt unabhaengig davon fuer
   `test_trip_outlook_parity.py`.

## Vom PO entschieden (2026-08-14) — gesetzt, nicht Teil der Freigabefrage

1. **Keine Nachtangabe.** Die Gewitterspalte der 3-Tages-Vorschau zeigt
   ausschliesslich das **Tagesfenster**, genau wie SMS. Begruendung des PO
   woertlich: „Nein, nur Tagesfenster, so wie auch für SMS. Dafür definiert
   der Nutzer es ja." Das Tagesfenster ist eine bewusste Nutzereinstellung;
   sie zu respektieren ist die Zusicherung, nicht eine Einschraenkung.
   ⇒ Diese Scheibe weicht damit **bewusst** von #1653/#1671 ab, die eine
   Nachtangabe eingefuehrt haben. Dort ist die Spaltenmenge fest; hier hat
   der Nutzer die Spalten selbst gewaehlt.

2. **Fehlende Ampelfarben sind ein eigenes Issue** (#1849), nicht Teil
   dieser Scheibe.

## Implementation Details

### 1. Tagesfenster-Stufe additiv in `format_trend_tokens()` (`helpers.py`)

`format_trend_tokens()` erhaelt einen zusaetzlichen Rueckgabeschluessel
`thunder_day_level` — die hoechste Gewitterstufe **im Tagesfenster**,
berechnet aus denselben `_win_start`/`_win_end` wie `thunder_day_token`
(`helpers.py:1005-1022`).

🔴 Bewusst **dort** und nicht im Metrik-Zweig: es bleibt bei **einer**
Fensteraufloesung. Eine zweite, unabhaengige Aufloesung waere exakt die
Fehlerklasse, gegen die #1653 und #1680 S5a AC-9 schreiben (Stufe aus dem
einen, Herkunft aus dem anderen Fenster).

Die Stufe wird aus `stage["hourly_thunder"]` abgeleitet (immer befuellt,
siehe „Am Code gemessen" Punkt 5), nicht aus `hourly_thunder_signals`.
Rueckabbildung des Fliesskommawerts auf `ThunderLevel` ueber die geteilte
Skala in `thunder_scale.py` — **keine lokale Kopie der Zuordnung**
(#1474: eine lokale `{NONE:0,MED:1,HIGH:2}`-Kopie ist seit der
LOW-Erweiterung stillschweigend falsch).

**Nachtrag 2026-08-15 (RED/GREEN-Phase, am Code gemessen): ZWEI Schluessel,
nicht einer.** Die Herkunft braucht einen eigenen additiven Schluessel
`thunder_day_carriers` — die **Rohliste** der Traeger, nicht den bereits
verketteten String `thunder_day_origin`. Zwei gemessene Gruende:

1. `_fmt_thunder(v, hail, signals)` **iteriert** ueber `signals` und mappt
   selbst ueber `thunder_signal_label()`. Ein String liefe zeichenweise
   durch — ein stiller Formatfehler, kein Absturz.
2. Die Traeger in `outlook.py` erneut zu filtern waere die **zweite**
   Fensteraufloesung, die dieser Abschnitt und #1680 S5a AC-9 gerade
   verbieten.

Beide Schluessel speisen sich aus den Mengen, die `format_trend_tokens()
`**ohnehin schon** berechnet (`_day_samples` / `_day_carriers`,
`helpers.py:1010-1035`). Damit bleibt es bei **einer** Aufloesung.

Additiv: bestehende Aufrufer lesen nur ihre bekannten Schluessel, das
Verhalten aller heutigen Verbraucher bleibt zeichengleich.

### 2. Metrik-Zweig auf den geteilten Helfer umstellen (`outlook.py:564-587`)

Nur wenn `trip_display_config is not None` (der Trip-Fall) **und** die
Spalte `kind == "ordinal"` traegt, wird der Wert ersetzt. Die Zweigwahl
kommt aus `resolve_thunder_day_branch(format_trend_tokens(row), row)`:

| Zweig | Wert der Zelle | Herkunft (`signals`) |
|---|---|---|
| `"day"` | `tok["thunder_day_level"]` | `tok["thunder_day_carriers"]` (Rohliste) |
| `"none"` | `ThunderLevel.NONE` (explizit „kein Gewitter") | keine |
| `"plain"` | `summary.thunder_level_max` (unveraendert) | `summary.thunder_level_max_signals` (unveraendert) |

`"plain"` greift, wenn gar keine Stundenreihe vorliegt — dann bleibt alles
wie heute. Alle anderen Spalten (`kind != "ordinal"`) bleiben unberuehrt.

🔴 Der Diskriminator ist `trip_display_config`, **nicht** die Praesenz des
Tagesfensters und **nicht** `report_type`. `report_type` ist beim Trip immer
gesetzt und sagt nichts ueber den Pfad; die Fensterpraesenz ist genau die
Falle aus „Am Code gemessen" Punkt 8.

### 3. Herkunft wandert mit der Stufe

`outlook.py:580` reicht heute `summary.thunder_level_max_signals` durch —
die Herkunft des **Aggregats**. Wandert die Stufe ins Tagesfenster, muss die
Herkunft mit: `union_of_max_carriers()` ueber dieselbe gefensterte Menge.
Sonst entsteht der AC-12-Fehler aus #1680 Scheibe 1, vor dem der Kommentar
an genau dieser Stelle (`outlook.py:574-579`) ausdruecklich warnt.

Fuehrt kein Datenpunkt eine Traegerliste (`hourly_thunder_signals is None`),
erscheint die Stufe **ohne** Herkunft — nie eine Herkunft, die nicht zur
gezeigten Stufe gehoert (AC-10-Regel aus #1680 S5a).

### 4. Testhelfer auf die echte Trip-Konvention ziehen

`tests/helpers/trip_outlook_selection.py::outlook_rows()` uebergibt kuenftig
`trip_display_config` + `report_type` + Tagesfenster wie
`trip_report_scheduler.py:2282`, statt `metrics=`. Der veraltete Docstring
(`:155-157`) wird mitkorrigiert.

🔴 **Reihenfolge:** Dieser Schritt kommt **zuerst**. Ohne ihn faehrt die
#1720-S1-Suite weiter den Compare-Weg, der Fix waere fuer sie unsichtbar,
und jeder folgende gruene Lauf bewiese nichts (Prueforts-Regel).

### 5. Dokumentation nachziehen

- `docs/reference/metric_output_matrix.md` `:89`, `:214`, `:376` — behaupten
  „Der Trip-Ausblick hat keine waehlbaren Spalten (feste Sieben)". Seit
  #1720 S1 falsch; die Datei wurde beim Merge nicht nachgezogen.
- `docs/specs/modules/feat_1680_s5a_gewitter_herkunft_ausblick.md` `:440-444`
  — „Der Metrik-Zweig (AC-11b) ist compare-exklusiv. Der Trip ruft die
  Ausblick-Renderer immer mit `metrics=None`". Am 2026-08-13 richtig,
  einen Tag spaeter durch #1720 S1 ueberholt. Erratum-Zeile, kein Umschreiben.

## Expected Behavior

Ein Trip mit gesetzter Spaltenauswahl in „3-Tages-Vorschau", die die Spalte
**Gewitter** enthaelt, zeigt in der Trip-Mail (HTML **und** Klartext) die
Gewitterstufe des **konfigurierten Tagesfensters** — dieselbe Rechnung, die
SMS bereits verwendet und die #1653 fuer alle uebrigen Ausgabeorte
festgelegt hat. Liegt im Tagesfenster kein Gewitter, sagt die Zelle das
ausdruecklich, statt eine Nachtstufe zu zeigen. Eine Nachtangabe erscheint
in diesem Zweig **nicht**.

Trips **ohne** Spaltenauswahl, alle uebrigen Spalten und der gesamte
Ortsvergleich bleiben unveraendert.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit gesetzter Spaltenauswahl „3-Tages-Vorschau"
  inklusive Spalte Gewitter, dessen Stundenreihe im Tagesfenster ein
  Gewitter zeigt, waehrend das gehzeit-geklemmte Aggregat `NONE` meldet /
  When die Trip-Mail erzeugt wird / Then nennt die Gewitterspalte die Stufe
  aus dem Tagesfenster — das Gewitter verschwindet nicht mehr. Nachweis in
  HTML **und** Klartext.

- **AC-2:** Given denselben Trip, dessen Aggregat eine Stufe traegt, waehrend
  die Stundenreihe im Tagesfenster leer ist (das Gewitter liegt nachts) /
  When die Trip-Mail erzeugt wird / Then zeigt die Gewitterspalte
  ausdruecklich „kein Gewitter" und behauptet keine Tagesstufe.

- **AC-3:** Given denselben Trip mit einem Gewitter ausschliesslich im
  Nachtfenster / When die Trip-Mail erzeugt wird / Then enthaelt die
  3-Tages-Vorschau **keine** Nachtangabe — weder als eigene Spalte noch als
  Zusatz in der Gewitterzelle (PO-Entscheid 2026-08-14, bewusste Abweichung
  von #1653/#1671).

- **AC-4:** Given einen Trip mit gesetzter Spaltenauswahl, dessen Punkte
  ueberhaupt keine Gewitterstufen tragen (keine Stundenreihe) / When die
  Trip-Mail erzeugt wird / Then bleibt die Zelle zeichengleich zum Stand vor
  dieser Aenderung (Zweig `"plain"`, Rueckfall auf das Aggregat).

- **AC-5:** Given einen Ortsvergleich mit gesetzter Metrik-Auswahl und
  gewaehlter Gewitterspalte / When dessen Mail erzeugt wird / Then ist die
  Ausgabe **byte-identisch** zum Stand vor dieser Aenderung — in HTML und
  Klartext. #1653 AC-6 bleibt in Kraft.

- **AC-6:** Given denselben Trip aus AC-1 / When die Gewitterzelle eine
  Herkunft nennt / Then stammt diese aus **demselben** Tagesfenster wie die
  daneben gezeigte Stufe. Traegt kein Datenpunkt eine Traegerliste, erscheint
  die Stufe ohne Herkunft — nie eine Herkunft aus einer anderen Rechnung als
  die gezeigte Stufe (AC-10-Regel aus #1680 S5a).

- **AC-7:** Given einen Trip **ohne** gesetzte Spaltenauswahl / When die
  Trip-Mail erzeugt wird / Then bleibt die 3-Tages-Tabelle byte-identisch
  zum Stand vor dieser Aenderung, inklusive Nachtangabe und Ampelfarben
  (Altpfad unberuehrt).

- **AC-8:** Given den Testhelfer `tests/helpers/trip_outlook_selection.py` /
  When er Ausblick-Zeilen fuer den Trip baut / Then benutzt er dieselbe
  Aufrufkonvention wie `trip_report_scheduler.py:2282`
  (`trip_display_config`/`report_type`/Tagesfenster), nicht `metrics=`.
  Nachweis: eine Verfaelschung des Trip-Zweigs macht mindestens einen Test
  der #1720-S1-Suite rot.

- **AC-9:** Given die geaenderte `format_trend_tokens()` / When ein
  bestehender Aufrufer (Altpfad-Ausblick, Telegram, Kurzformat-Mail) sie
  aufruft / Then bleibt dessen Ausgabe zeichengleich — der neue Schluessel
  ist rein additiv.

## Nicht in dieser Scheibe

- **Ampelfarben im Metrik-Zweig (#1849).** Der Zweig faerbt keine Zelle ein
  (`outlook.py:141`, `_otd()` ohne `bg=`). Betrifft alle Spalten und beide
  Flaechen; eigener Fix, PO-Entscheid 2026-08-14.
- **Der Ortsvergleich.** Bleibt byte-identisch (AC-5). Er leidet **nicht** am
  Fehler dieser Scheibe: der Ortsvergleich kennt keine Etappen
  (`fix-1361-1368-ausblick-konfigurierbar.md:70`), also gibt es nichts, wogegen
  geklemmt werden koennte — `_group_by_calendar_day()` aggregiert den vollen
  Kalendertag, die Nacht ist dort bereits enthalten und verschwindet nicht.
  Ob zusaetzlich ein Tag/Nacht-Split fuer den Ortsvergleich sinnvoll waere,
  ist **unentschieden**: #1653 AC-6 ist reiner Bestandsschutz (das dortige
  Finding F003 nahm eine *versehentliche* Compare-Aenderung zurueck, es war
  keine bewusste Ablehnung), und #1680 S5a AC-11b begruendet nur die
  **Kohaerenz** von Stufe und Herkunft, nicht die Wahl des Fensters. Nicht
  hier entscheiden.
- **Das Auswahl-Vokabular (`{metric_id, aggregation}` vs. Katalog-Kennungen).**
  PO-Entscheid 2026-08-14, gebucht als **#1848**: die Paar-Darstellung und die
  Kaskaden-Nachbildung in `resolve_trip_outlook_metrics()`
  (`compare_outlook_metric_ids.py:78-102`) sollen perspektivisch entfallen.
  Diese Scheibe **vertieft sie nicht**: sie fasst weder
  `resolve_trip_outlook_metrics()` noch `outlook_columns()` an und erkennt die
  Gewitterspalte an `col["kind"] == "ordinal"` — einer **Katalog**-Eigenschaft
  (`compare_outlook_metric_ids.py:164-166`), nicht am Paar-Vokabular. Der Fix
  bleibt damit tragfaehig, egal welches Vokabular #1848 durchsetzt.

- **`render_outlook_table()` auf den geteilten Helfer umstellen.** #1671 hat
  das bewusst ausgelassen (strukturell andere Zweigwahl, dortige Known
  Limitation). Diese Scheibe aendert nur den Metrik-Zweig, nicht den
  HTML-Altpfad.

## Testplan

- [ ] AC-1: Tagesgewitter sichtbar trotz `NONE` im Aggregat — HTML + Klartext,
      ueber `render_email()` (echter Aufrufpfad, nicht der Renderer isoliert)
- [ ] AC-2: „kein Gewitter" statt Nachtstufe bei leerem Tagesfenster
- [ ] AC-3: keine Nachtangabe im Metrik-Zweig (Negativpruefung auf „nachts")
- [ ] AC-4: Nullfall ohne Stundenreihe — Zeichengleichheit zum Vorstand
- [ ] AC-5: Ortsvergleich byte-identisch (HTML + Klartext)
- [ ] AC-6: Herkunft aus demselben Fenster wie die Stufe; ohne Traegerliste
      keine Herkunft
- [ ] AC-7: Trip ohne Auswahl byte-identisch (Altpfad)
- [ ] AC-8: Testhelfer nutzt die Trip-Konvention
- [ ] AC-9: `format_trend_tokens()` additiv — Bestandsaufrufer zeichengleich

Kern-Schicht, deterministisch. Keine Mocks, kein Netz. Dateiname nach
Verhalten: `tests/tdd/test_vorschau_metrik_tagesfenster.py`.

### 🔴 Fixtur-Geometrie — AC-1 und AC-2 brauchen VERSCHIEDENE Zuschnitte

Aus „Am Code gemessen" Punkt 6 folgt eine harte Bedingung an die Testdaten.
Die beiden Fehlerrichtungen entstehen an **entgegengesetzten** Raendern:

| AC | Gewitterstunde liegt … | Gehzeit vs. Tagesfenster | Wirkung heute |
|---|---|---|---|
| AC-1 | im **Tagesfenster**, aber **ausserhalb der Gehzeit** | Gehzeit **enger** (z.B. Gehzeit 08–14, Fenster 04–19, Gewitter 17:00) | Aggregat sagt `NONE` → Gewitter verschwindet |
| AC-2 | in der **Gehzeit**, aber **ausserhalb des Tagesfensters** | Gehzeit **reicht hinaus** (z.B. Gehzeit 02–21, Fenster 04–19, Gewitter 02:00) | Aggregat traegt eine Stufe → Tagesgewitter erfunden |

🔴 **Eine einzige Fixture kann nicht beide ACs tragen.** Wer beide mit
derselben Geometrie baut, bekommt fuer eine der beiden Richtungen ein
Datenbild, in dem Aggregat und Tagesfenster **denselben** Wert liefern — der
Test ist dann von einem No-Op nicht unterscheidbar und bleibt nach jeder
Mutation gruen. Genau diese Falle hat die parallel gestoppte Session
gemeldet; hier ist sie um die zweite, entgegengesetzte Geometrie ergaenzt.

**Vorbedingungs-Test (PFLICHT, vor den AC-Tests):** je Fixture zeigen, dass
`summary.thunder_level_max` und die Tagesfenster-Stufe **verschieden** sind.
Sind sie gleich, prueft der darauf aufbauende AC-Test nichts — die Fixture
ist dann kaputt, nicht der Code.

## Mutations-Gegenprobe (PFLICHT)

| # | Verfaelschung | Muss rot werden |
|---|---|---|
| M1 | Diskriminator fest auf `True` (auch Compare korrigieren) | mindestens ein Compare-Test (AC-5) |
| M2 | Diskriminator fest auf `False` (Trip nicht korrigieren) | mindestens ein Trip-Test (AC-1/AC-2) |
| M3 | Diskriminator auf Fensterpraesenz statt `trip_display_config` | `test_outlook_day_night_thunder_split.py:665` |
| M4 | Herkunft weiter aus `summary.thunder_level_max_signals` | AC-6 |
| M5 | Zweig `"none"` liefert das Aggregat statt `ThunderLevel.NONE` | AC-2 |
| M6 | `thunder_day_level` aus dem 24h-Fenster statt dem Tagesfenster | AC-1 **und** AC-2 |
| M7 | Testhelfer zurueck auf `metrics=` | AC-8 |

🔴 **M1 und M2 muessen BEIDE greifen.** Wird nur eine Richtung rot, bewacht
der Nachweis nur die halbe Trennung — genau der Fehler, den
`test_compare_plain_carries_no_trip_format_remnants` vortaeuscht (er bleibt
in beiden Richtungen gruen).

## Nachweis vor Commit

1. `tests/tdd/test_vorschau_metrik_tagesfenster.py` gruen
2. `tests/tdd/test_outlook_day_night_thunder_split.py` gruen (Compare-Schutz)
3. `tests/tdd/test_trip_outlook_metric_selection.py` gruen (nach Helfer-Umbau)
4. `tests/tdd/test_trip_outlook_parity.py` gruen (Altpfad)
5. `tests/golden/email/test_outlook_thunder_day_night_golden.py` gruen
6. `tests/tdd/test_kompaktmail_ausblick_tagesfenster.py` gruen (#1671 unberuehrt)
7. `briefing_mail_validator.py` Exit 0 (Renderer-Commit-Gate, `outlook.py` ist
   eine Mail-Inhalts-Datei)
8. `tests/tdd/test_issue_811_mode_matrix.py` gruen (dasselbe Gate)

## Known Limitations

- Die Aufzeichnung `REFERENCE_TABLE` in
  `test_ac1_bestandstrip_html_ausblick_bleibt_byte_identisch` rendert einen
  Trip **ohne** Auswahl und bewacht damit den Altpfad. Sie sollte sich durch
  diese Scheibe **nicht** aendern; der im #1841-Kommentar erwartete zweite
  datierte Eintrag entfaellt voraussichtlich. Vor einem Nachziehen der
  Referenz ist das zu **messen**, nicht anzunehmen. Aendert sie sich wider
  Erwarten doch, gilt: einen **zweiten** datierten Eintrag anhaengen, den
  bestehenden #1801-Eintrag **nicht** ersetzen — die Historie muss lesbar
  bleiben (#1841-Kommentar vom 2026-08-14). Zur Einordnung: diese
  Aufzeichnungen bewachen die **Konstanz** der Ausgabe, nicht ihre
  **Korrektheit** — eine unveraenderte Referenz belegt nicht, dass der Inhalt
  vorher richtig war.
- Der Fix wirkt nur auf den Metrik-Zweig. Zeigt ein Trip beide Zustaende
  nacheinander (Auswahl gesetzt, dann geleert), wechselt er zwischen zwei
  Darstellungen mit und ohne Nachtangabe. Das ist die Folge des
  PO-Entscheids und beabsichtigt.
- Die Trip/Compare-Trennung haengt an der Aufrufkonvention, nicht an einem
  ausdruecklichen Merkmal. Ein kuenftiger dritter Aufrufer, der beides oder
  keines setzt, faellt still in den Compare-Zweig. AC-8 bewacht die heutigen
  zwei; ein struktureller Wachter dagegen ist nicht Teil dieser Scheibe.

## Architektur-Entscheidung (ADR)

Kein neues ADR. Die Scheibe **vollzieht** ADR-0055 Punkt 4 („eine
Aufloesung, nicht drei") fuer die Gewitterquelle des Ausblicks und macht den
Metrik-Zweig zum vierten Aufrufer des mit #1671 eingefuehrten geteilten
Helfers. Die bewusste Abweichung von #1653/#1671 (keine Nachtangabe) ist
eine PO-Entscheidung ueber eine **nutzerkonfigurierte** Spaltenmenge, keine
Architekturentscheidung — sie steht oben unter „Vom PO entschieden" und in
AC-3.

## Offene Punkte für den PO

Keine. Beide Designfragen sind am 2026-08-14 entschieden (keine Nachtangabe;
Ampelfarben als #1849).

## Changelog

| Datum | Version | Aenderung |
|---|---|---|
| 2026-08-14 | 1.0 | Erstfassung nach Kontext- und Analysephase (Stand `57e36375`) |
