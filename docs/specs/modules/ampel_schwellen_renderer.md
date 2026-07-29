---
entity_id: ampel_schwellen_renderer
type: module
created: 2026-07-29
updated: 2026-07-29
status: draft
version: "1.0"
tags: [ampel, schwellen, renderer, issue-1377, epic-1374]
---

# Ampel-Schwellen in den Renderern (Scheibe B)

Issue [#1377](https://github.com/henemm/gregor_zwanzig/issues/1377), Etappe S5 des
Ortsvergleich-Reworks (#1374/#1372). Scheibe B von zwei.

## Approval

- [x] Approved — PO-Freigabe 2026-07-29

## Purpose

Scheibe A (`dbbb30fb`) hat den zentralen Metrik-Katalog zur alleinigen Quelle aller
Warnschwellen gemacht. Die Renderer selbst lesen ihn aber noch nicht überall — Trip-Briefing
und Ortsvergleich führen an mehreren Stellen weiterhin eigene, voneinander abweichende
Schwellenwerte. Dieselbe Vorhersage kann dadurch in der Trip-Mail grün und im
Ortsvergleich gelb erscheinen (oder umgekehrt) — der Kernbefund von #1377. Scheibe B
schließt diese Lücke: jede Zell-, Punkt- und Kachel-Färbung fragt künftig denselben
Katalog wie ihr Nachbar.

## Source

- **File:** `src/output/renderers/email/html.py` — Zell-Tönung, `_row_risk`
- **File:** `src/output/renderers/email/outlook.py` — Ausblick-Tabelle (von Trip UND
  Ortsvergleich gemeinsam genutzt)
- **File:** `src/output/renderers/email/compare_html.py` — `_sev_*`-Funktionen der
  Vergleichsmatrix
- **File:** `src/output/renderers/email/helpers.py` — `_pill_for_metric`,
  `_level_from_thresholds`
- **Schicht:** Python-Core (`src/output/renderers/email/`)

## Estimated Scope

- **LoC:** ~265 (+205 / −60) über vier Quelldateien plus Tests plus
  Golden-Regenerierung — **liegt über dem Workflow-Limit von 250.** Aufteilung in
  zwei Teilscheiben siehe „Known Limitations" (Abschnitt „Vorschlag Teilscheiben
  B1/B2").
- **Files:** 4 Quelldateien (`html.py`, `outlook.py`, `compare_html.py`, `helpers.py`) +
  ~4 neue/erweiterte Testdateien + 5 Golden-HTML-Dateien (regeneriert, zählen nicht als
  LoC)
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `metric_catalog.get_metric` / `display_thresholds` | upstream | liefert die Schwellen (Scheibe A) |
| `severity_for` / `severity_from_thresholds` | upstream | einzige Bandauswertung (Scheibe A) |
| `design_tokens.tone_css` | upstream | (bg, fg)-Tupel je Stufe; nur `[0]` wird verwendet |
| `_render_html_table` (`html.py`) | downstream | Aufrufer der Zell-Tönung + `_row_risk` |
| `render_outlook_table` (`outlook.py`) | downstream | gemeinsam von Trip UND Ortsvergleich genutzt |
| `build_metrics_summary_pills` (`helpers.py`) | downstream | Klartext-Kachel in HTML/Plain/Compact |
| Vergleichsmatrix (`compare_html.py`) | downstream | Zellen der Orts-Vergleichstabelle |

## Implementation Details

### 1. Zell-Tönung der Stundentabelle (`html.py:596-628`)

Zeilen 604-612 lesen bereits den Katalog (`ampel_level`) für Metriken, die in
`indicator_keys` stehen — das ist der „freundliche" Anzeigemodus. Der elif-Block
615-628 ist der Fallback für den Roh-Modus sowie für Sichtweite und Gewitter, die
`_COL_KEY_TO_METRIC_ID` heute gar nicht kennt. Er wird auf `severity_for` umgestellt,
mit EINER Ausnahme: `thunder` bleibt außerhalb des Katalogwegs (kein
`display_thresholds` im Katalog, siehe „Feste Vorgaben"). **Nachtrag 2026-07-29
(#1418/S1):** Der `thunder`-Zweig blieb zunächst wörtlich unangetastet und war
dadurch wirkungslos — er las weiterhin `float(raw_val)`, was für das
`ThunderLevel`-Enum immer `None` ergab, die Zelle blieb also ungefärbt. Seit
`docs/specs/modules/fix_1418_gewitter_risikopunkt.md` liest dieser Zweig
stattdessen `_thunder_risk_level(raw_val)` (Helfer in `html.py`, direkt über
`_row_risk`) und färbt `'risk'` rot (`#f6c5bf`) bzw. `'watch'` orange
(`#fad6b8`) — weiterhin ohne den Katalog zu nutzen, `thunder` führt nach wie
vor kein `display_thresholds`. Diese Zell-Umstellung ist Teil dieses
Workflows (noch nicht committet); der Risiko-Punkt (`_row_risk`, s.u.) nutzt
denselben Helfer bereits seit Commit `659ada95`. `vis`/`visibility` erhält damit
erstmals die Katalog-Werte 2000/1000/500 m statt der bisherigen 2/1/0,5 km
(rechnerisch identisch, aber jetzt über dieselbe Funktion wie der
Ortsvergleich ausgewertet statt über einen eigenen
Kilometer-Umrechnungspfad).

### 2. `_row_risk` (`html.py:147-161`)

Bestimmt den Risiko-Punkt am Zeilenende aus fünf hartcodierten Schwellen
(`thunder>20`, `gust>30`, `wind>20`, `precip>1`, `pop>50`, `vis<2`). Wird auf
`severity_for` je Metrik umgestellt (Gewitter bleibt hartcodiert, s.u.); aus den
resultierenden Stufen `green/yellow/orange/red` wird die schärfste genommen.

**Nachtrag 2026-07-29 (#1418/S1):** „Gewitter bleibt hartcodiert" hieß zum
Zeitpunkt dieser Spec, dass die alte Zahl-Schwelle `thunder>20` unverändert
bestehen blieb. Sie war jedoch wirkungslos: `thunder` trägt im Produktivpfad
ein `ThunderLevel`-Enum (NONE/MED/HIGH), keine Zahl, und `float("HIGH")`
schlägt fehl und fällt still auf `0.0` zurück — der Punkt blieb bei Gewitter
immer grün. Issue #1418 (Fehler 1, Scheibe S1 von Epic #1419,
`docs/specs/modules/fix_1418_gewitter_risikopunkt.md`, geliefert mit Commit
`659ada95`) ersetzt die reine Zahl-Schwelle durch den neuen Helfer
`_thunder_risk_level()` direkt über `_row_risk`: Er vergleicht die Stufe als
String (`ThunderLevel` erbt von `str`, deckt Enum- und Namen-String-Form ab)
— HIGH trägt direkt zu `"risk"` bei, MED zu `"watch"` — und behält den
historischen Zahlenvergleich (`> 20` → `"risk"`, `> 0` → `"watch"`) als
Fallback, weil der AC-7-Regressionsschutz aus #1377 rohe Zahlen übergibt und
genau deshalb unverändert grün bleiben muss. Gewitter bleibt damit weiterhin
außerhalb des Katalogwegs (`severity_for`/`display_thresholds`) — nur die
frühere, wirkungslose Zahl-Schwelle wurde durch den funktionierenden
Stufenvergleich ersetzt.

Der Punkt selbst zeigt weiterhin nur drei Farben (`_RISK_DOT_COLORS`:
`ok`/`watch`/`risk` — grün/orange/rot, **kein** eigenes Gelb). Das bleibt so:
`green` → `ok`, `yellow` **und** `orange` → `watch`, `red` → `risk`. Eine vierte
Punktfarbe einzuführen wäre eine zusätzliche, hier nicht angefragte optische
Änderung. `_row_risk` bekommt dadurch dieselbe SCHWELLENQUELLE wie die
Einzelzellen, bleibt aber bei seinem eigenen, gröberen Anzeige-Vokabular — das
Zusammenfassungs-Symbol einer ganzen Zeile ist kein Ersatz für die feingranulare
Ampel jeder einzelnen Metrik und muss nicht mit ihr identisch auflösen.

### 3. Ausblick-Tabelle (`outlook.py:57-73, 197-200`)

`_outlook_cell_bg` nimmt ein 3er-Tupel `(caution, warn, danger)` entgegen. Die vier
Aufrufstellen (Regen, Regenwahrscheinlichkeit, Wind, Böen) erhalten die
Katalog-Werte über `get_metric(id).display_thresholds` statt der hartcodierten
Tupel. Wind wird dabei von zweistufig (20/30) auf dreistufig (30/50/70) erweitert —
eine neue rote Stufe, die es im Ausblick bisher nicht gab. `render_outlook_table`
wird **sowohl von Trip als auch von Ortsvergleich** aufgerufen (ein Renderer, zwei
Aufrufer) — diese eine Umstellung schließt die Ausblick-Lücke zwischen beiden
Mail-Arten in einem Schritt.

### 4. Vergleichsmatrix (`compare_html.py:62-63, 88-123`)

`_sev_wind` und `_sev_cape` rufen bereits `severity_for` auf und übersetzen das
Ergebnis über `_CANONICAL_TO_COMPARE` in das Compare-lokale Vokabular
(`ok/caution/warn/danger`) — das ist die Vorlage. `_sev_temp`, `_sev_rain`,
`_sev_uv`, `_sev_pop`, `_sev_visibility` werden nach demselben Muster umgestellt:
Katalog-Werte statt hartcodierter Zahlen.

`_sev_gust` wird **ebenfalls umgestellt** (Korrektur 2026-07-29, Adversary-Fund
B2/F001): Die drei Zahlenwerte 30/45/60 sind zwar deckungsgleich zum Katalog, die
**Grenz-Inklusivität** aber nicht — die Handschwelle prüfte `> 30`, der Katalog
wertet `>= 30`. Bei genau 30 km/h liefen Trip und Ortsvergleich damit weiter
auseinander, also genau der Fehler, den #1377 beseitigt. Betroffen ist nur der
exakte Schwellenwert; abgesichert durch
`test_sev_gust_exact_30_becomes_caution`.

`_sev_temp` bekommt dadurch **zusätzlich zur Hitze-Seite** auch die neu im Katalog
hinterlegte Kälte-Seite (0/−5/−15 °C) — eine über die fünf in „Sichtbare Wirkung"
genannten Zeilen hinausgehende, aber notwendige Folge: dieselbe Katalog-Metrik darf
in Trip und Vergleich nicht verschieden viele Bänder haben. Ohne diesen Schritt
bliebe die Kälte-Seite ausgerechnet im Ortsvergleich unsichtbar, obwohl sie in der
Trip-Kachel (Punkt 5) neu erscheint.

`_CANONICAL_TO_COMPARE`/`_COMPARE_TO_CANONICAL` (Zeilen 62-63) entfallen — sie
übersetzten das Compare-Vokabular 1:1 in das kanonische und zurück, was nach der
Umstellung nur noch ein Umbenennungsschritt ohne Mehrwert ist. `_sev_*` liefern
das Compare-Vokabular direkt aus `severity_for` (interne Zuordnungstabelle statt
Zwei-Wege-Übersetzung); die beiden Aufrufstellen, die bisher
`_COMPARE_TO_CANONICAL[level]` an `tone_css` übergeben haben
(Zeilen 498, 631), rufen `tone_css` künftig mit dem kanonischen Level direkt auf,
das `severity_for` ohnehin schon geliefert hat.

**Fehlende Messwerte sind bereits abgesichert.** Beide Aufrufstellen der
Vergleichsmatrix (`compare_html.py:492-493` und die zweite Renderfunktion
`:714-715`) rufen `sev_fn` grundsätzlich nur auf, wenn der Messwert nicht `None`
ist (`sev_fn(value) if (sev_fn and value is not None) else None`) — ein fehlender
Wert erreicht `_sev_*` also gar nicht erst und bleibt ungefärbt
(`bg = "transparent"`). Das bestehende `.get(severity_for(...), "ok")`-Muster in
`_sev_wind`/`_sev_cape` (Zeile 98/123) ist dadurch bereits heute unproblematisch und
bleibt es nach der Umstellung der übrigen `_sev_*`-Funktionen: `severity_for`
bekommt hier nie einen `None`-Wert WEGEN EINES FEHLENDEN MESSWERTS, weil er vorher
abgefangen wird. Ein gesonderter Test für diesen Fall ist deshalb nicht nötig
(Details s. „Known Limitations"). Das ist ein anderer Fall als AC-8 (fehlende
SCHWELLEN, nicht fehlende Messwerte) — siehe Implementation Details Punkt 5.

### 5. Klartext-Kachel — Klasse-2-Neutralität aufheben (`helpers.py:1340-1444`)

`_pill_for_metric` färbt heute **acht** Größen fest mit `_PILL_NEUTRAL_TONE`,
unabhängig vom Wert: `temperature`, `wind_chill`, `cloud_total`, `cloud_low`,
`freezing_level`, `dewpoint`, `uv_index`, `sunshine`. Von diesen acht führt der
Katalog nur für drei überhaupt `display_thresholds` (`temperature`, `wind_chill`,
`uv_index`) — die übrigen fünf (`cloud_total`, `cloud_low`, `freezing_level`,
`dewpoint`, `sunshine`) haben schlicht keine Warnschwellen und liefern bei
`severity_for(...)` immer `None` (Katalog-F001 aus dem Adversary-Lauf zu Scheibe A:
„keine Schwellen" ist ein anderer `None`-Grund als „kein Messwert").

Diese Umstellung hebt die Neutralität **ausschließlich** für `temperature` und
`wind_chill` auf (`_AGGREGATION_PILL_METRICS`, Zeilen 1207-1214) — die übrigen
sechs Größen (`cloud_total`, `cloud_low`, `freezing_level`, `dewpoint`, `uv_index`,
`sunshine`) bleiben unverändert neutral. Das gilt auch für `uv_index`, obwohl der
Katalog dafür bereits Schwellen führt (3/6/8): Der Auftrag für Scheibe B
beschränkt sich ausdrücklich auf die beiden Größen, für die der PO-Befund vom
2026-07-28 galt (Temperatur/gefühlte Temperatur); eine Ausweitung auf UV-Index
wäre eine eigene, hier nicht angefragte Produktentscheidung.

`temperature`/`wind_chill` bekommen wie Wind/Böen (Klasse 1) eine Ampel-Farbe aus
`severity_for`, ausgewertet auf dem für die gewählte Auswertung (min/max/Spanne)
maßgeblichen Extremwert — bei Hitze der Höchstwert, bei Kälte der Tiefstwert,
analog zur bereits bestehenden zweiseitigen Bandauswertung aus Scheibe A.

Die Aggregation filtert fehlende Einzelwerte bereits vor dem Aufruf von
`severity_for` heraus (`vals_ts = [(v, ts) for v, ts in vals_ts if v is not None]`,
`helpers.py:1370-1373`) und liefert `None` (kein Chip) zurück, wenn für die gesamte
Etappe kein einziger Wert vorliegt — `severity_for` bekommt hier also praktisch nie
einen `None`-Wert wegen eines fehlenden MESSWERTS. Trotzdem gilt: `severity_for`
(nicht `ampel_stage_tone`) ist für `temperature`/`wind_chill` die richtige Wahl,
weil `ampel_stage_tone` bei fehlender SCHWELLE grün zurückgibt — für Temperatur und
gefühlte Temperatur gibt es aber immer Schwellen.

**Regressionsgefahr bei unsauberer Umsetzung:** Wird die Neutralität statt gezielt
für `temperature`/`wind_chill` versehentlich pauschal für alle acht Größen
aufgehoben, laufen die übrigen sechs — vor allem die fünf ganz ohne Katalog-Schwelle
— in den `None`-Fall von `severity_for`. Je nach Implementierung könnte ein
unsauberer Umgang mit diesem `None` einen fälschlich grünen Chip erzeugen, obwohl
die Größe gar keine Bewertung hat. AC-8 sichert genau das als Regressionsschutz ab.

### 6. `_level_from_thresholds` entfällt (`helpers.py:501-517`)

Delegiert seit Scheibe A bereits vollständig an `severity_from_thresholds` — ist
nur noch ein Argument-vertauschender Wrapper. Die beiden verbleibenden Aufrufer
(`ampel_dot`, `ampel_level`) rufen `severity_from_thresholds` künftig direkt auf;
der Wrapper wird gelöscht. Kein Verhaltensunterschied, reine Aufräumarbeit im
Zuge der Umstellung.

## Expected Behavior

- **Input:** Ein Messwert je Metrik, an einer der fünf oben genannten
  Rendering-Stellen (Zell-Tönung, `_row_risk`, Ausblick, Vergleichsmatrix,
  Klartext-Kachel)
- **Output:** Zell-, Punkt- oder Kachel-Farbe aus genau vier Stufen
  (`green`/`yellow`/`orange`/`red`, intern ggf. auf ein lokales 3er- oder
  Vokabular abgebildet wie bei `_row_risk` und dem Pill-Tag), oder keine
  Tönung, wenn kein Messwert vorliegt oder die Größe keine Schwellen führt
- **Side effects:** Fünf Wettergrößen ändern sichtbar ihre Farbgrenze in der
  Mail (s. „Sichtbare Wirkung"); die Ausblick-Tabelle konvergiert für Trip UND
  Ortsvergleich in einem Schritt, weil beide denselben Renderer teilen

## Sichtbare Wirkung (bewusst, PO-informiert)

Fünf Wettergrößen ändern durch diese Spec ihre Farbgrenze sichtbar in der Mail.
Alle Richtungen sind bewusst gewählt: die Katalog-Werte aus Scheibe A gelten
unverändert, hier wird nur der Leser (Renderer) auf sie umgestellt.

| Größe | heute | künftig | Richtung |
|---|---|---|---|
| Regenwahrscheinlichkeit | Trip ab 50 %, Vergleich ab 40 % | beide ab 30 % | färbt früher |
| Regen | Trip/Vergleich >1/>4/>8 mm, Ausblick ≥2/≥5/≥8 mm | 1/5/10 mm | färbt später |
| Wind | Trip/Ausblick zweistufig >20/>30 km/h | dreistufig 30/50/70 km/h | färbt später, neue rote Stufe |
| Sichtweite | Vergleich <5000/<3000/<1000 m | 2000/1000/500 m | Vergleich färbt später, jetzt gleich wie Trip |
| Temperatur + gefühlte Temperatur | Kachel fest neutral (nie eingefärbt) | erstmals eingefärbt, inkl. Kälte-Seite | neu sichtbar — behebt den PO-Befund vom 2026-07-28 |

Konkretes Beispiel für den Kernfehler des Issues: 35 km/h Wind zeigt in der
Trip-Zelle heute **orange** (eigener Schwellenwert >30), im Ortsvergleich (bereits
katalogbasiert seit #1214) aber **gelb** — derselbe Wert, zwei Farben in zwei
Mails. Nach dieser Umstellung zeigen beide **gelb**.

Nicht sichtbar verändert: Böen (schon deckungsgleich), CAPE/UV (schon katalogbasiert
im Ortsvergleich bzw. unverändert), Gewitter (bewusst ausgenommen, s.
„Known Limitations"), sowie die sechs Klartext-Kacheln ohne Ampel-Anschluss
(`cloud_total`, `cloud_low`, `freezing_level`, `dewpoint`, `uv_index`, `sunshine`
— bleiben neutral, s. Implementation Details Punkt 5).

## Acceptance Criteria

- **AC-1 (Regenwahrscheinlichkeit):** Given eine Regenwahrscheinlichkeit von 45 % /
  When Trip-Stundentabelle und Ortsvergleichs-Matrix für denselben Wert gerendert
  werden / Then zeigen beide „gelb" — heute zeigt die Trip-Zelle bei 45 % noch
  keine Farbe (Schwelle erst ab 50 %), der Ortsvergleich bereits gelb (Schwelle
  ab 40 %).
  - Test: Renderer-Aufruf für Trip-Zelle und für `compare_html._sev_pop(45)` mit
    demselben Erwartungswert `"yellow"` bzw. dem entsprechenden Compare-Tag

- **AC-2 (Regen):** Given 1,5 mm Niederschlag in einer Stunde / When Trip-Zelle,
  Ortsvergleichs-Matrix und Ausblick-Tabelle für denselben Wert gerendert werden /
  Then zeigen alle drei „gelb" — heute zeigt der Ausblick bei 1,5 mm noch keine
  Farbe (Schwelle erst ab 2 mm), Trip-Zelle und Vergleich zeigen schon gelb
  (Schwelle ab >1 mm).
  - Test: drei Renderer-Aufrufe (Zelle, `_sev_rain`, `render_outlook_table`) mit
    identischem Eingabewert und identischer erwarteter Stufe

- **AC-3 (Wind):** Given 35 km/h Wind / When Trip-Zelle und Ortsvergleichs-Matrix
  für denselben Wert gerendert werden / Then zeigen beide „gelb" — heute zeigt die
  Trip-Zelle „orange" (eigene Schwelle >30 km/h), der Ortsvergleich bereits „gelb"
  (Katalog-Schwelle, seit #1214 migriert).
  - Test: Renderer-Aufruf für die Trip-Zelle bei 35 km/h liefert dieselbe Stufe wie
    `severity_for("wind", 35) == "yellow"`

- **AC-4 (Sichtweite):** Given eine Sichtweite von 1500 m / When Trip-Zelle und
  Ortsvergleichs-Matrix für denselben Wert gerendert werden / Then zeigen beide
  „gelb" — heute zeigt die Trip-Zelle „gelb" (eigene Schwelle <2000 m), der
  Ortsvergleich aber „orange" (eigene Schwelle <3000 m).
  - Test: Renderer-Aufruf für die Trip-Zelle bei 1500 m und `_sev_visibility(1500)`
    liefern dieselbe Stufe

- **AC-5 (Temperatur/gefühlte Temperatur):** Given 32 °C gemessene und 32 °C
  gefühlte Temperatur / When die Klartext-Kachel und die Ortsvergleichs-Matrix für
  denselben Wert gerendert werden / Then zeigen alle drei (Kachel-Temperatur,
  Kachel-gefühlte-Temperatur, Vergleichs-Zelle) „orange" — heute bleibt die Kachel
  in jedem Fall neutral/farblos, unabhängig vom Wert.
  - Test: `severity_for("temperature", 32) == severity_for("wind_chill", 32) ==
    "orange"`, und die von `_pill_for_metric("temperature", …)` sowie
    `_pill_for_metric("wind_chill", …)` zurückgelieferte Tönung entspricht „orange",
    nicht der bisherigen `_PILL_NEUTRAL_TONE`

- **AC-6 (Ausblick folgt Stundentabelle):** Given ein Ausblick-Tag mit 1,5 mm
  Niederschlag / When die Ausblick-Tabelle gerendert wird / Then ist die
  Niederschlags-Zelle „gelb" statt wie bisher ungefärbt — identisch zur
  entsprechenden Stundentabellen-Zelle desselben Werts.
  - Test: `render_outlook_table`-Aufruf mit precip_mm=1.5; Zellhintergrund ist
    nicht mehr leer

- **AC-7 (Gewitter unverändert durch diese Umstellung):** Given ein
  Trip-Briefing und ein Ortsvergleich mit identischer Gewitterlage (z.B. Stufe
  „hoch") / When beide Mails gerendert werden / Then ist die Gewitter-Färbung
  in beiden exakt wie vor dieser Änderung — Gewitter ist ausdrücklich nicht
  Teil dieser Umstellung (Scheibe B). Dieser AC war zum Zeitpunkt der
  Umstellung bereits erfüllt (Regressionsschutz, kein Bugfix-Nachweis für
  Scheibe B).
  - Test: Golden-Vergleich der Gewitter-Zeilen/-Zellen vor und nach der
    Änderung; keine Abweichung erlaubt.
  - **Nachtrag 2026-07-29 (#1418/S1):** Von den beiden für diesen AC
    ursprünglich genutzten Unit-Tests in
    `tests/tdd/test_renderer_katalog_schwellen.py` bleibt
    `test_ac7_thunder_row_risk_unchanged` **unverändert grün** — der neue
    Helfer `_thunder_risk_level()` (s. Implementation Details Punkt 2) behält
    den historischen Zahlenvergleich als Fallback genau zu diesem Zweck, der
    Test wurde nicht ersetzt. Nur `test_ac7_thunder_cell_tint_unchanged`
    wurde ersetzt durch `test_ac7_thunder_cell_tint_follows_level` (Spec:
    `docs/specs/modules/fix_1418_gewitter_risikopunkt.md`), weil die Zelle
    jetzt tatsächlich gefärbt wird (zuvor strukturell nie, s.
    Implementation Details Punkt 1) und der alte Testname „unchanged" nicht
    mehr zutrifft. Die AC-7-Aussage „Gewitter ist nicht Teil dieser
    Umstellung (Scheibe B)" bleibt davon unberührt — sie bezieht sich auf den
    Katalogweg (`severity_for`/`display_thresholds`), nicht auf die
    Testbenennung. Lieferung verteilt auf zwei Commits: `659ada95` für
    `_row_risk` (Punkt), dieser Workflow für die Zell-Tönung (noch nicht
    committet).

- **AC-8 (Metriken ohne Schwellen bleiben neutral — Regressionsschutz):** Given
  eine Größe ohne hinterlegte Warnschwellen im Katalog (z.B. Taupunkt oder
  Sonnenscheindauer) / When die Klartext-Kachel dafür gerendert wird / Then bleibt
  sie neutral — sie wird nie grün eingefärbt, obwohl ein gültiger Messwert
  vorliegt. Dieser AC ist bereits vor der Umstellung erfüllt (Regressionsschutz,
  wie AC-7) — er sichert zu, dass die Aufhebung der Klasse-2-Neutralität für
  Temperatur/gefühlte Temperatur NICHT versehentlich auf die übrigen sechs
  neutralen Größen ausgeweitet wird.
  - Test: `_pill_for_metric` für mindestens zwei schwellenlose Größen (z.B.
    `dewpoint`, `sunshine`) mit gültigem Messwert liefert `_PILL_NEUTRAL_TONE`,
    niemals eine Ampel-Tönung; zusätzlich `severity_for("dewpoint", …) is None`
    und `severity_for("sunshine", …) is None`

- **AC-9 (Golden-Mails):** Given die fünf bestehenden Mail-Schnappschüsse in
  `tests/golden/email/` / When sie nach der Änderung neu erzeugt werden / Then
  unterscheiden sie sich ausschließlich in den fünf in „Sichtbare Wirkung"
  genannten Größen (Regenwahrscheinlichkeit, Regen, Wind, Sichtweite, Temperatur/
  gefühlte Temperatur); alle übrigen Zellen, Zahlen und Texte sind unverändert.
  - Test: Golden-Vergleich; jede Abweichung außerhalb dieser fünf Größen lässt den
    Test fehlschlagen

- **AC-10 (`_row_risk` bekommt einen direkten Test):** Given zwei Testzeilen — eine
  mit 25 km/h Wind und sonst unauffälligen Werten, eine mit exakt 30 km/h Böen und
  sonst unauffälligen Werten / When der Risiko-Punkt am Zeilenende für beide
  berechnet wird / Then zeigt die erste künftig „unauffällig" statt wie bisher
  „Achtung" (heutige Schwelle `wind > 20`, die Katalog-Schwelle für Wind beginnt
  erst bei 30 km/h), und die zweite künftig „Achtung" statt wie bisher
  „unauffällig" (heutige Schwelle `gust > 30` ist exklusiv und lässt genau 30 km/h
  noch durch, der Katalog wertet ab einschließlich 30 km/h).
  - Test: `_row_risk({"wind": 25})` liefert vor der Änderung `"watch"`, danach
    `"ok"`; `_row_risk({"gust": 30})` liefert vor der Änderung `"ok"`, danach
    `"watch"` — erster direkter Unit-Test für diese Funktion, bisher nur indirekt
    über Golden-Snapshots abgedeckt

## Known Limitations

- **Gewitter bleibt außerhalb des Katalogwegs.** Der Katalog führt für
  `thunder` weiterhin keine `display_thresholds` — die Datenform-Divergenz
  (Prozentwert vs. Stufen MED/HIGH) ist Gegenstand von Epic #1372, ergänzt
  seit 2026-07-29 um Epic #1419, das die Gewitter-Datenform als eigenes
  Vorhaben führt (nicht Gegenstand dieser Spec). Von den drei bestehenden
  hartcodierten Gewitter-Färbungen bleiben `outlook.py` und `compare_html.py`
  unangetastet; `html.py` färbt Gewitter seit #1418/S1 (2026-07-29,
  `docs/specs/modules/fix_1418_gewitter_risikopunkt.md`) über den neuen
  Helfer `_thunder_risk_level()` statt über die zuvor wirkungslose
  Zahl-Schwelle — weiterhin nicht über den Katalog, `thunder` führt nach wie
  vor kein `display_thresholds`. Geliefert in zwei Commits: `_row_risk`
  (Risiko-Punkt) mit `659ada95`, die Zell-Tönung mit diesem Workflow (noch
  nicht committet) — beide nutzen bewusst denselben Helfer statt einer
  zweiten Stufenquelle direkt daneben.
- **Verlässlichkeits-Anzeigen bleiben draußen.** `_confidence_dot_color`
  (`html.py:1091-1107`) und `outlook._acc_dot` (`outlook.py:87-107`) zeigen die
  Vorhersage-SICHERHEIT (Ensemble-Divergenz), keine Wetterlage — sie dürfen laut
  PO-Entscheidung vom 2026-06-10 (Issue #710) ohnehin nicht als Wettermetrik
  behandelt werden und sind hier bewusst nicht Teil der Umstellung.
- **Hero-/Mobil-Stundenliste (`html.py:198-349`, insb. 243-245) bleibt draußen.**
  Verifiziert per Grep (`grep -rn "_render_mobile_hour_list" src/ tests/`):
  ausschließlich die Definition selbst — kein einziger Aufrufer, auch kein Test.
  Toter Code seit `bf5ef21f` (der `<pre>`-Pfad der Mobilansicht wurde entfernt;
  seitdem rendert `_render_mobile_compact_rows` immer die normale Tabelle). Eine
  Umstellung hätte keinen Nutzer-Effekt und würde nur unnötig Umfang binden.
  Kandidat für einen Sammel-Eintrag (#1199), keine eigene Umstellung in
  Scheibe B.
- **`helpers.py:838-841` (Wind 30/50 in `format_trend_tokens`) bleibt draußen.**
  Verifiziert per Grep: `wind_highlight`/`wind_risk` werden zwar berechnet, aber
  von keinem aktiven Renderer (`compact.py`, `narrow.py`, `outlook.py`) tatsächlich
  gelesen — toter Code ohne sichtbare Wirkung. Eine Umstellung hätte keinen
  Nutzer-Effekt und würde nur unnötig Umfang binden. Kandidat für einen
  Sammel-Eintrag (#1199), keine eigene Umstellung in Scheibe B.
- **`_COL_KEY_TO_METRIC_ID` (`html.py:552`) und `_AMPEL_KEY_TO_METRIC_ID`
  (`helpers.py:579`) bleiben als redundante Teilkopien bestehen.** Beide könnten
  durch `metric_catalog.get_metric_by_col_key` ersetzt werden — beide Wege liefern
  im Normalfall dieselbe Metrik. Die Ablösung wird in Scheibe B NICHT vorgenommen,
  weil eine Unschärfe vorher geklärt werden müsste: `html.py:625` behandelt sowohl
  den Spaltenschlüssel `vis` als auch `visibility`, während der Katalog nur
  `visibility` als `col_key` kennt (`metric_catalog.py:368`). Eine blinde Ablösung
  würde die `vis`-Schreibweise stillschweigend aus der Tönung herausfallen lassen.
  Gehört in eine eigene, kleine Aufräum-Umstellung — Sammel-Eintrag (#1199).
- **None-Sicherheit bei fehlenden MESSWERTEN geprüft, kein gesonderter AC nötig
  (anderer Fall als AC-8, der fehlende SCHWELLEN behandelt).** Eine mögliche Lücke
  „fehlender Messwert wird stillschweigend grün" wurde geprüft und erwies sich als
  bereits strukturell ausgeschlossen: Die Vergleichsmatrix ruft `_sev_*` nur bei
  `value is not None` auf (`compare_html.py:492-493`, `:714-715`), die
  Klartext-Kachel filtert fehlende Einzelwerte vor der Aggregation heraus
  (`helpers.py:1370-1373`) und liefert bei komplett fehlenden Daten `None`
  (kein Chip) statt eines gefärbten Chips. Ein entsprechender AC wurde deshalb
  NICHT aufgenommen — er wäre nicht konstruierbar gewesen, weil kein Eingabewert
  existiert, der einen fehlerhaften „grün trotz fehlendem Messwert"-Zustand vor der
  Umstellung tatsächlich auslöst. Nebenbefund dabei: `_sev_rain_safe`
  (`compare_html.py:174-175`) setzt einen fehlenden Regenwert bereits heute auf
  0 mm (= grün) — vorbestehendes, von dieser Umstellung unabhängiges Verhalten;
  kein Fix in Scheibe B, Kandidat für #1199.
- **Überlappende Bänder** (Hitze- und Kältegrenze überschneiden sich) werden von
  `severity_from_thresholds` nicht erkannt — für die hier verwendeten Werte tritt
  der Fall nicht auf (unverändert aus Scheibe A übernommen).

### Vorschlag Teilscheiben B1/B2 (LoC-Limit)

Die Schätzung (~265 LoC) liegt über dem Workflow-Limit von 250. Empfohlener Schnitt
für zwei separate Workflows/PRs, beide gegen diese eine Spec:

- **B1 — Trip-intern + gemeinsamer Ausblick:** `html.py` (Zell-Tönung, `_row_risk`),
  `helpers.py` (`_pill_for_metric`-Klasse-2, `_level_from_thresholds`-Entfernung),
  `outlook.py` (vier Schwellen-Tupel — wirkt wegen des gemeinsamen Renderers
  bereits auf Trip UND Ortsvergleich). Deckt AC-2 (Trip-Zelle- und
  Ausblicks-Teil), AC-5 (Kachel-Teil), AC-6, AC-8, AC-10 sowie den Trip-Zell-Teil
  von AC-1/AC-3/AC-4 ab. AC-7 (Gewitter) wird für den Trip-Teil mitgeprüft.
- **B2 — Ortsvergleichs-Matrix:** `compare_html.py` (`_sev_*`, Entfernen von
  `_CANONICAL_TO_COMPARE`/`_COMPARE_TO_CANONICAL`, Anpassen der beiden
  `tone_css`-Aufrufstellen). Deckt den verbleibenden Vergleichsmatrix-Teil von
  AC-1, AC-3, AC-4, AC-5 ab; AC-7 (Gewitter) wird für den Vergleichs-Teil
  mitgeprüft.

B1 behebt bereits den in „Sichtbare Wirkung" gezeigten Kernwiderspruch (Böen-Punkt
vs. Zelle, Ausblick vs. Tabelle) und schaltet die Temperatur-Kachel frei. B2 schließt
danach die verbleibende Trip-vs-Vergleich-Lücke für Regen/Wind/Sicht/Temperatur in
der Matrix. Golden-Regenerierung und der volle AC-9-Nachweis sind erst nach B2
vollständig — B1 kann seinen Teil der Golden-Diffs bereits isoliert zeigen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Die Grundsatzentscheidung „der zentrale Katalog ist die
  Schwellenquelle" wurde bereits in Scheibe A (Issue #1377) getroffen. Diese Spec
  führt die Renderer-seitige Konsequenz nur aus. Ein ADR wäre erst nötig, wenn
  davon abgewichen würde.

## Changelog

- 2026-07-29: Initial spec created (Scheibe B von #1377)
- 2026-07-29: Korrekturen nach Koordinator-Review — AC-7 (Mobil-Stundenliste)
  ersatzlos gestrichen (toter Code, kein Aufrufer); AC „None-Fall" gestrichen
  (Szenario strukturell unerreichbar, hätte keinen echten Vorher/Nachher-Unterschied
  gezeigt); `_row_risk`-AC auf zwei tatsächlich unterschiedliche Werte umgestellt
  (35 km/h Böen war schon vor der Umstellung „Achtung" und bewies nichts)
- 2026-07-29: Zweite Korrektur — F001 (fehlende SCHWELLEN, nicht fehlende
  Messwerte) neu als AC-8 aufgenommen, ausdrücklich als Regressionsschutz
  gekennzeichnet (analog AC-7 Gewitter); Implementation Details Punkt 5 stellt
  jetzt klar, dass die Neutralität nur für `temperature`/`wind_chill` aufgehoben
  wird, die übrigen sechs Größen (`cloud_total`, `cloud_low`, `freezing_level`,
  `dewpoint`, `uv_index`, `sunshine`) bleiben neutral
- 2026-07-29: Nachtrag aus Issue #1418/S1 (Epic #1419) — `html.py` färbt
  Gewitter jetzt über den neuen Helfer `_thunder_risk_level()` (direkt über
  `_row_risk`) statt über die zuvor wirkungslose Zahl-Schwelle (`float("HIGH")`
  fiel still auf `0.0` zurück); der Katalogweg bleibt für `thunder` weiterhin
  ungenutzt. Der Helfer behält den historischen Zahlenvergleich als Fallback,
  deshalb bleibt `test_ac7_thunder_row_risk_unchanged` unverändert grün — nur
  `test_ac7_thunder_cell_tint_unchanged` wurde durch
  `test_ac7_thunder_cell_tint_follows_level` ersetzt. Lieferung auf zwei
  Commits verteilt: `659ada95` (Risiko-Punkt, `_row_risk`, live), dieser
  Workflow (Zell-Tönung, noch nicht committet). AC-7, Implementation Details
  Punkt 1 (Zell-Tönung) und Punkt 2 (`_row_risk`) sowie „Known Limitations"
  entsprechend nachgezogen. Details:
  `docs/specs/modules/fix_1418_gewitter_risikopunkt.md`
