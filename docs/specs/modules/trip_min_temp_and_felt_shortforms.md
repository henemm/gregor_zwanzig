---
entity_id: trip_min_temp_and_felt_shortforms
type: feature
created: 2026-07-28
updated: 2026-07-28
status: draft
version: "1.1"
tags: [renderer, tokens, sms, telegram, compact-summary, epic-1372, issue-1410]
---

<!-- Issue #1410 — Epic #1372, Scheibe 2 zu #1357 S4a -->

# Tiefsttemperatur unterwegs + gefühlte Temperatur in den Kurzformen (Issue #1410)

## Approval

- [x] Approved — PO-Freigabe 2026-07-28 (12 Acceptance Criteria, PO-Entscheidungen
      F1 „morgens und abends" und F2 „gefuehlte Temperatur in den
      Zusammenfassungssatz")

> **Nachtrag 2026-07-29 (Issue #1417):** Die unter F3 und in den Dependencies
> getroffene Aussage, `segment_weather.py::_aggregate_for_segment()` sei „die"
> Gehzeit-Berechnung, war unvollstaendig — es existierten mehrere
> Implementierungen desselben Fensters, die sich in der Ankunftsstunde
> unterschieden. Die hier eingefuehrten Token `K`/`FK`/`FD` erbten dadurch
> anfangs dieselbe Divergenz zur Mail-Kachelzeile wie `D`. Seit #1417 stammen
> sie aus der einzigen geteilten Quelle
> `day_window.collect_hiking_window_points()`; die fachliche Aussage von F3
> („Rechenfenster = Gehzeit, exakt wie die gemessene Temperatur, keine neue
> Berechnung") bleibt unveraendert gueltig — nur der Bezugspunkt hat sich
> praezisiert. Spec: `docs/specs/modules/hiking_window_single_source.md`.

## Purpose

Zwei bisher fehlende Werte kommen in die drei Kurzformen (SMS,
E-Mail-Kurzzusammenfassung, Telegram): (1) die **Tiefsttemperatur während
des Trips** — die kälteste Stunde unterwegs, unterschieden von der bereits
bestehenden Nacht-Tiefsttemperatur am Schlafplatz (`N`) — und (2) die
**gefühlte Temperatur** überhaupt, die in SMS und Kurzzusammenfassung heute
vollständig fehlt. PO-Vorgabe wörtlich: „Die beiden Werte sollen sich bei
Trips exakt so verhalten, wie die normale Temperatur und auch exakt so
berechnet werden." Das ist bereits heute der Fall auf Ebene der
Rohberechnung (`wind_chill_min_c`/`wind_chill_max_c` entstehen aus
demselben gefensterten Zeitraum wie `temp_min_c`/`temp_max_c`,
`services/segment_weather.py:254-281`) — die Lücke liegt ausschließlich in
der **Darstellung** der drei Kurzformen.

**PO-Entscheidungen 2026-07-28 (Intake), nicht erneut zur Diskussion:**
- **F1:** Die kälteste Stunde unterwegs erscheint neu **morgens** (heute
  gibt es dort gar keinen Tiefstwert) **und abends zusätzlich** zur
  Nacht-Tiefsttemperatur am Schlafplatz (`N`). `N` behält seine Bedeutung
  unverändert (`night_temp_evening_only.md` bleibt gültig, wird NICHT
  umgekehrt) — der neue Wert tritt daneben, nicht an seine Stelle. **F1
  gilt einheitlich für alle drei Kurzformen** (SMS, E-Mail-
  Kurzzusammenfassung, Telegram) — s. „Berührung bestehender
  Entscheidungen" unten für die daraus folgende Korrektur an Telegram.
- **F2:** Die gefühlte Temperatur wird in den Zusammenfassungssatz der
  E-Mail aufgenommen (Beispiel: `GR221 Tag1: 8–15°C, gef. 6–13°C, teils
  bewölkt, …`).
- **F3:** Rechenfenster = Gehzeit, exakt wie die gemessene Temperatur.
  Keine neue Berechnung nötig.
- **F4:** Die Abend-Nacht-Regel (echte Nachttemperatur am Ziel statt
  Tagesminimum) gilt analog auch für die gefühlte Temperatur.
- **Zuschnitt:** Diese Lieferung umfasst beides — den neuen Tiefstwert
  „während des Trips" UND die Einführung der gefühlten Temperatur in den
  Kurzformen (SMS, Kurzzusammenfassung, Telegram-Absicherung).

Zwei Ausgaben brauchen dafür fast keine Arbeit: die Mail-Kachelzeile zeigt
die gefühlte Spanne bereits (Issue #1357 S4a), Telegram zeigt sie ebenfalls
bereits (`TF {min}-{max}@{h}`, katalog-generisch) — nur ungetestet. Die
eigentliche Arbeit liegt in SMS und E-Mail-Kurzzusammenfassung.

## Berührung bestehender Entscheidungen (night_temp_evening_only.md)

Diese Spec berührt `docs/specs/modules/night_temp_evening_only.md`
(#1319 Scheibe D) an genau einer Stelle: **DEC-2** dort — „morgens nur
das Tagesmaximum, kein Bereich/Min-Wert" (Belegstellen:
`compact_summary.py`-Kommentar „Issue #1319 Scheibe D (DEC-1/DEC-2)",
`narrow.py:407-411`-Morgenzweig, `_tg_vortag_line`-Filter) — wird durch
die PO-Entscheidung **F1** vom 2026-07-28 **abgelöst**: alle drei
Kurzformen zeigen morgens künftig ebenfalls eine Tiefst-Höchst-Spanne.
Der Tiefstwert ist dabei die kälteste Gehzeit-Stunde (`K` in SMS, das
gleichnamige Konzept in E-Mail-Kurzzusammenfassung/Telegram) — ein von
`N` unterschiedener, neuer Wert.

**DEC-1** (`N` = echte Nacht-Tiefsttemperatur am Ziel, ausschließlich
abends sichtbar) bleibt davon **unberührt und weiterhin gültig** — nur
die Morgen-Anzeige des (vorher gar nicht gezeigten) Tiefstwerts ändert
sich, nicht die Bedeutung, Quelle oder Sichtbarkeit von `N`. **DEC-3**
(große E-Mail-Tabelle „🌙 Nacht am Ziel") und **DEC-4** (kein
Persistenz-Eingriff) sind ebenfalls unberührt.

Eine bewusste, nicht abgelöste Ausnahme bleibt bestehen: der
Vortagsvergleich in Telegram (`_tg_vortag_line`) filtert morgens
weiterhin den „Temp min"-Delta-Eintrag heraus — Begründung s.
Implementation Details §8.

`docs/specs/modules/night_temp_evening_only.md` bekommt dazu einen
kurzen Verweis-Hinweis (Known Limitations + Changelog dort), **keine**
inhaltliche Umschreibung der DEC-1…DEC-4-Entscheidungen selbst.

## Source

> **Schicht:** Python-Core / Domain-Backend (`src/output/`), reine
> Renderer-/Token-Logik. Kein Go-, kein Frontend-Anteil.

- **File:** `src/output/tokens/dto.py:22-38` (`DailyForecast`) —
  bekommt vier neue Felder (s. Implementation Details §5)
- **File:** `src/output/tokens/builder.py:37-69,199-237` (`PRIORITY`,
  `POSITIONAL`, `build_token_line()` N/D-Token-Loop) — wird auf sechs
  Temperatur-Token erweitert
- **File:** `src/output/tokens/render.py:9-11,59-101` (`DROP_ORDER`,
  `_truncate()`) — neuer Kürzungsschritt für die gefühlten Token
- **File:** `src/output/renderers/sms_trip.py:95-240`
  (`_segments_to_normalized_forecast`), `:243-380` (`format_sms`,
  `SMS_SYMBOL_BY_METRIC`)
- **File:** `src/output/renderers/day_window.py:196-232`
  (`night_temp_min_c`) — wird intern auf einen geteilten Kern
  umgestellt, neue Funktion `night_wind_chill_min_c()`
- **File:** `src/output/renderers/compact_summary.py:100-250`
  (`format_stage_summary`, `format_weather_summary`,
  `_format_temperature`) — neue `_format_felt_temperature()`,
  Morgen-Zweig von `_format_temperature()` wird auf Spanne umgestellt
- **File:** `src/output/renderers/email/helpers.py:1285-1319`
  (`_aggregation_pill_text`) — kleine Spannen-Formatierungsfunktion wird
  herausgezogen und von der Kurzzusammenfassung mitbenutzt (geteilte
  Formatierung statt Nachbau)
- **File:** `src/output/renderers/narrow.py:368-424` (`_overview_line`),
  `:263-289` (`_tg_vortag_line`), `:476-530`
  (`render_telegram_bubbles`) — Morgen-Sonderzweig entfällt für
  `temperature`/`wind_chill`, Abend-Nachtwert-Ersetzung auf `wind_chill`
  ausgedehnt
- **File:** `src/output/renderers/trip_report.py:248-263` (Bug #944
  Disabled-Spec-Block) — Erweiterung um die drei neuen Felt-Symbole
- **File:** `docs/reference/sms_format.md` — Vertragsänderung (neue
  Token, Null-Formen, Kürzungsreihenfolge, Drift-Korrektur §6)
- **File (nur Referenz, unverändert):**
  `src/services/segment_weather.py:254-281` (Beleg „gleicher
  Rechenweg"), `src/app/metric_catalog.py:101-112` (`wind_chill`-
  Definition), `src/output/tokens/hazard_symbols.py:15-25` (Kollisions-
  Referenz)
- **File (Verweis-Hinweis, kleine additive Änderung):**
  `docs/specs/modules/night_temp_evening_only.md` — DEC-2-Ablösung
  vermerken (s. „Berührung bestehender Entscheidungen")

## Estimated Scope

- **LoC:** ~145-215 Produktivcode (day_window.py ~20, dto.py ~12,
  sms_trip.py ~35, builder.py ~45, render.py ~12, compact_summary.py
  ~35, email/helpers.py ~12, trip_report.py ~8, narrow.py ~16-18 — durch
  den Wegfall des Morgen-Sonderzweigs in `_overview_line()` eher eine
  Nettoentfernung von Code als ein Zuwachs). Unter dem 250-LoC-Limit,
  keine Override-Anfrage nötig. `docs/reference/sms_format.md`-Änderung
  und Golden-Fixtures zählen nicht mit (Projektkonvention).
- **Files:** 9 Produktivdateien + 1 Vertragsdokument + 1 kleine
  Verweis-Ergänzung in `night_temp_evening_only.md` + 5 SMS-Goldens +
  10 E-Mail-Goldens (5 Paare) + neue Testdateien.
- **Effort:** medium-high — drei unabhängige Renderer-Pfade (SMS,
  E-Mail-Kurzzusammenfassung, Telegram), ein Vertragsdokument, volle
  Golden-Neuerzeugung.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/renderers/day_window.py::night_temp_min_c()` | function (wird intern geteilt) | Liefert das Filtermuster für den neuen `night_wind_chill_min_c()` — dieselbe Ankunft→06:00-Fensterlogik, nur anderes DTO-Feld (`wind_chill_c` statt `t2m_c`) |
| `src/services/segment_weather.py::_aggregate_for_segment()` | function (unberührt, Beleg) | Zeigt, dass `temp_min_c`/`temp_max_c` und `wind_chill_min_c`/`wind_chill_max_c` bereits aus derselben gefensterten Zeitreihe stammen — kein neuer Rechenweg nötig (F3) |
| `docs/specs/modules/night_temp_evening_only.md` | Spec (DEC-1 unberührt, DEC-2 abgelöst) | DEC-1 (`N`, nur abends, echte Nachttemperatur am Ziel) bleibt exakt gültig. DEC-2 („morgens nur Höchstwert") wird durch PO-Entscheidung F1 abgelöst — s. „Berührung bestehender Entscheidungen". Die Zieldatei bekommt einen kurzen Verweis-Hinweis, keine inhaltliche Umschreibung |
| `docs/specs/modules/trip_aggregation_selection.md` (#1357 S4a) | Spec (Vorgänger) | Kachelzeile zeigt die gefühlte Spanne bereits; diese Spec ist genau die dort vorgeschlagene „Scheibe 2" |
| `src/output/renderers/email/helpers.py::_aggregation_pill_text()` | function (Formatierungsvorbild) | Spannen-Grundformat (Präfix, Nachkommastellen, En-Dash) wird als kleine gemeinsame Funktion herausgezogen und auch von `compact_summary.py` genutzt — KEIN Nachbau der Zahl-Formatierung |
| `src/app/metric_catalog.py` (`wind_chill`-Eintrag, `default_enabled=True`) | Katalog-Eintrag | Steuert, ob die drei neuen Felt-Token (`FN`/`FK`/`FD`) und der Kurzzusammenfassungs-Zusatzsatz überhaupt erscheinen — „nichts eingestellt heißt nichts angezeigt" gilt hier NUR für die Felt-Werte, nicht für `K`/`D`/`N` (die wie bisher unbedingt erscheinen, s. Implementation Details §6) |
| `src/output/tokens/hazard_symbols.py::HAZARD_SMS_SYMBOLS` | Katalog (Kollisions-Referenz) | Neue Token `K`, `FN`, `FK`, `FD` wurden gegen diese 9 amtlichen Kürzel, gegen `PRIORITY`/`POSITIONAL` (`builder.py`) und gegen alle `sms_code`-Werte in `metric_catalog.py` geprüft — kollisionsfrei (s. Implementation Details §1) |
| `renderer_mail_gate.py` (#811, Commit-Gate) | Tooling | `sms_trip.py`, `compact_summary.py`, `email/helpers.py` sind Mail-Inhalts-Dateien → vor Commit `tests/tdd/test_issue_811_mode_matrix.py` grün UND frischer `briefing_mail_validator.py`-Lauf gegen eine echt zugestellte Staging-Mail nötig |
| `test_naming_gate.py` | Tooling | Neue Testdateien nach Verhalten benennen, nicht nach Issue-Nummer — blockt sonst hart |
| `tests/golden/email/regenerate.py`, `tests/golden/test_sms_golden.py` | Tooling | Neu einzufrierende Fixtures nach der Implementierung |

## Expected Behavior

**Input:** Ein Trip mit Etappen-Segmenten und optionalem Ziel-Nachtwetter,
Report-Typ `morning` oder `evening`, sowie die Metrik-Auswahl des Nutzers
(`wind_chill` aktiviert ja/nein). Die Werte selbst existieren bereits:
`temp_min_c`/`temp_max_c` und `wind_chill_min_c`/`wind_chill_max_c` je
Segment, beide aus derselben zeitgefilterten Gehzeit-Zeitreihe
(`services/segment_weather.py:254-281`).

**Output je Kanal:**

| Kanal | morgens | abends |
|---|---|---|
| SMS | `K` (kälteste Gehzeit-Stunde), `D`; bei aktivierter gefühlter Temperatur zusätzlich `FK`, `FD` | zusätzlich `N` (Nacht am Ziel) und, bei aktivierter gefühlter Temperatur, `FN` |
| E-Mail-Kurzzusammenfassung | Spanne `{K}–{D}°C` statt bisher nur `{D}°C`; bei aktivierter gefühlter Temperatur zusätzlich `gef. {FK}–{FD}°C` | Spanne mit Nachtwert als Untergrenze, gefühlt analog |
| Telegram-Kurzübersicht | Spanne `{lo}-{hi}@{Spitzenstunde}` für gemessene und gefühlte Temperatur (Morgen-Sonderzweig entfällt) | Untergrenze ist der Nachtwert am Ziel, gemessen wie gefühlt |

**Side Effects:**
- `night_temp_evening_only.md::DEC-2` wird abgelöst (s. „Berührung
  bestehender Entscheidungen"); `DEC-1` bleibt unverändert gültig.
- `docs/reference/sms_format.md` ändert sich als Vertrag (neue Token,
  Null-Formen, Kürzungsreihenfolge).
- Alle 5 SMS-Goldens und 10 E-Mail-Goldens werden bewusst neu eingefroren.
- Keine Persistenz-, Auth- oder Schema-Änderung; keine Migration; kein
  Go-Eingriff.

## Implementation Details

### 1. Token-Symbole — Wahl, Begründung, Kollisionsprüfung

Vier neue Symbole, zusätzlich zu den bestehenden `D` (Tag-Höchst,
gemessen) und `N` (Nacht-Tiefst am Ziel, gemessen, nur abends):

| Symbol | Bedeutung | Sichtbarkeit | Quelle (neu/bestehend) |
|---|---|---|---|
| `K` | Tiefsttemperatur **unterwegs**, gemessen (kälteste Gehzeit-Stunde) | immer (morgens + abends) | NEU — Gehzeit-Fenster, gleicher Rechenweg wie `D` |
| `D` | Tages-Höchsttemperatur, gemessen | immer | unverändert |
| `N` | Nacht-Tiefsttemperatur am Ziel, gemessen | nur abends | unverändert (`night_temp_evening_only.md`, DEC-1) |
| `FK` | Tiefsttemperatur unterwegs, **gefühlt** | immer, nur wenn „Gefühlte Temperatur" aktiviert | NEU, Parität zu `K` |
| `FD` | Tages-Höchsttemperatur, **gefühlt** | immer, nur wenn aktiviert | NEU, Parität zu `D` |
| `FN` | Nacht-Tiefsttemperatur am Ziel, **gefühlt** | nur abends, nur wenn aktiviert | NEU, Parität zu `N` (F4) |

**Warum nicht die im Kontext-Dokument genannten Kandidaten `GN`/`GD`?**
Ein `G`-Präfix liegt visuell direkt neben dem bereits bestehenden,
alleinstehenden Symbol `G` (Böen). Unter Zeitdruck ist die Verwechslungs-
gefahr „`G` = Böen" vs. „`G…` = irgendein neuer Temperaturwert" real,
obwohl beide Symbole programmatisch eindeutig sind (Token-Vergleich ist
exakt, nicht Präfix-basiert). Ebenso verworfen: `L`/`M`/`H` als
Präfix/Symbol — diese Buchstaben sind bereits **Wert**-Buchstaben der
Warnstufen-Skala (`L`=Gelb, `M`=Orange, `H`=Rot, `hazard_symbols.py:33`),
ein neues Token mit demselben Buchstaben wäre zwar strukturell
unterscheidbar (Werte-Buchstaben stehen nie direkt an Zeilenanfang eines
Tokens ohne vorangehenden Doppelpunkt), aber unnötig riskant für ein
Sicherheitsformat. Gewählt wurde stattdessen:
- `K` — frei, keine bestehende Verwendung als Symbol- oder Werte-
  Buchstabe irgendwo im Format (Vorschlag: „Kälte", international
  trotzdem eindeutig lesbar als Ergänzung zu `D`/`N`).
- `F`-Präfix für „Felt/Gefühlt" — deckt sich mit dem bereits etablierten
  `compact_label="TF"` (`metric_catalog.py:105`, „Temperature Felt") und
  dem Präfix „gef. " in der Mail-Kachelzeile/Kurzzusammenfassung. `FD`,
  `FK`, `FN` teilen sich das `F`-Präfix rein untereinander (keine
  Kollision mit dem einzigen bestehenden `F`-Symbol `FR`, Waldbrand-
  Gefahr — das erscheint ausschließlich im `!`-Warn-Block mit Doppelpunkt
  und Stufe, z. B. `!FR:H`, nie als bloßes `FR9`; strukturell
  unterscheidbar).

**Kollisionsprüfung (alle drei Domänen):**

| Domäne | Geprüfte Werte | Treffer bei `K`/`FN`/`FK`/`FD`? |
|---|---|---|
| `PRIORITY`/`POSITIONAL` (`builder.py:37-69`) | `DBG, WC, AV, SFL, SN24+, SN, Z:, MAX, M:, PR, D, N, R, W, G, TH+:, HR:, TH:` | keiner |
| Amtliche Warn-Kürzel (`hazard_symbols.py:15-25`) | `TH, HR, W, SN, IC, HT, CD, FR, CL` | keiner |
| `sms_code` in `metric_catalog.py` | `D, N, HU, PR, TH, CP, SL, VS, UV, NL, SD, SN` | keiner |

Alle vier Symbole sind kollisionsfrei in allen drei Domänen.

### 2. Beispielzeilen mit Zeichenzählung

**Morgen** (Vorbild `gr20-spring-morning.txt`, heute 89 Zeichen):
```
GR20 E1: K3 D9 FK1 FD7 R0.2@4(18.5@11) PR50%@4(95%@11) W35@5(60@10) G55@5(85@10) TH:M@8(H@11) TH+:-
```
+ 12 Zeichen (` K3` ` FK1` ` FD7`), Gesamtlänge ~101, weit unter 160.

**Abend, alle sechs Temperaturwerte** (Vorbild `gr221-mallorca-evening.txt`,
heute 64 Zeichen — der schlankste Golden):
```
GR221 Tag1: N8 K6 D15 FN6 FK4 FD13 R- PR- W25@12(40@16) G35@12(55@16) TH:- TH+:-
```
64 + 16 (` K6` ` FN6` ` FK4` ` FD13`) = 80 Zeichen.

**Worst-Case-Rechnung gegen den heutigen Maximal-Golden**
(`corsica-vigilance.txt`, 122 Zeichen, Vigilance + Fire-Block, negative
Werte als Extremfall angenommen):
`K`, `FK`, `FD`, `FN` jeweils mit zweistelligem negativem Wert
(`K-12`=4 Zeichen, `FN-12`/`FK-12`/`FD-12`=5 Zeichen je) + Leerzeichen =
5+6+6+6 = **23 Zeichen** Zuwachs im ungünstigsten Fall.
122 + 23 = **145 Zeichen** — unter 160, aber mit nur 15 Zeichen Puffer
bei gleichzeitigem Vigilance- und Fire-Block. Kein bestehender Golden
reißt die Grenze; ein hypothetischer Trip mit Vigilance **und**
Wintersport **und** vollem Warn-Block gleichzeitig könnte die 160er-
Grenze erreichen — dafür existiert die Kürzungsreihenfolge (§3 unten).

### 3. Drei unabhängige Reihenfolgen (bekannte Falle, s. Projekt-Historie)

**a) `POSITIONAL`/`POS_INDEX` (`builder.py:55-69`, Anzeigereihenfolge):**
```python
POSITIONAL = [
    ("N", "forecast"), ("K", "forecast"), ("D", "forecast"),
    ("FN", "forecast"), ("FK", "forecast"), ("FD", "forecast"),
    ("R", "forecast"), ("PR", "forecast"), ("W", "forecast"), ("G", "forecast"),
    (FORECAST_TH, "forecast"), (FORECAST_THP, "forecast"),
    # ... Rest unverändert
]
```
Reihenfolge folgt der Parität `N↔FN`, `K↔FK`, `D↔FD` (gemessenes Trio,
dann gefühltes Trio, dann die übrigen Vorhersage-Token unverändert).

**b) `DROP_ORDER` + dedizierte Schritte (`render.py:9-11,59-101`,
Kürzungsreihenfolge bei >160 Zeichen):** `DROP_ORDER` selbst enthält
NIE `D`/`N`/`PR` — diese drei werden in `_truncate()` durch eigene,
spätere Schleifen entfernt (bekannte Falle: drei unterschiedliche
Mechanismen, keine einzige Liste). Neuer Schritt, **zwischen** dem
bestehenden Peak-Strip und dem PR-Schritt eingefügt:
```python
for sym in ("FN", "FK", "FD"):          # NEU: Felt-Trio faellt VOR PR
    if _drop_first(tokens, sym):
        ...
while _drop_first(tokens, "PR"):         # unveraendert
    ...
for sym in ("K", "D", "N"):              # ERWEITERT (vorher nur "D","N")
    if _drop_first(tokens, sym):
        ...
```
**Begründung „gefühlt vor gemessen":** die gefühlte Temperatur ist eine
Komfort-/Zusatzangabe (PO-Auftrag benennt sie explizit als Ergänzung),
während `R`/`PR`/`W`/`G`/`TH` sicherheitsrelevante Planungsgrößen sind —
das Felt-Trio fällt deshalb sogar vor `PR`, nicht erst danach. Innerhalb
des gemessenen Trios fällt `K` zuerst (neuester, am wenigsten
etablierter Wert), dann `D`, dann `N` zuletzt (unverändert zur
bestehenden Reihenfolge).

**c) `PRIORITY`-Dict (`builder.py:37-46`, nur Last-Resort-Rang,
`render.py:81-95`):**
```python
PRIORITY = {
    ...,
    "PR": 5, "D": 6, "N": 6, "K": 6,
    "FD": 4, "FK": 4, "FN": 4,
    "R": 7, ...
}
```
Felt-Token bekommen einen niedrigeren Rang als `PR` (5), obwohl sie
durch den dedizierten Schritt (b) ohnehin vor Erreichen des
Last-Resort-Pfads entfernt werden — die Zuordnung ist Dokumentations-
/Konsistenzpflicht, kein aktiver Nebenpfad. `KeyError` ohne diesen
Eintrag, da `builder.py` `priority=PRIORITY[sym]` ungeschützt aufruft.

### 4. Totes `WC`-Token — bleibt im Code, entfällt aus dem Vertrag

Der Wintersport-Pfad (`_wintersport()`, `builder.py:174-196`) ist im
Produktivpfad unerreichbar (`profile="wintersport"` nur in
`src/app/cli.py:233`, Legacy-CLI). **Entscheidung:** kein Code-Eingriff
in `_wintersport()` — `DailyForecast.wind_chill_c` (Einzelwert-Feld)
bleibt **unverändert bestehen**, zusätzlich zu den vier neuen Feldern
aus §5. Damit bleibt `tests/unit/test_token_builder.py` (nutzt
`wind_chill_c=-22.0` für den Wintersport-Truncation-Test) unangetastet —
kein Kollateralschaden an einem Test außerhalb dieses Scopes.
`docs/reference/sms_format.md` §3.6/§9 wird trotzdem korrigiert: `WC`
war seit Einführung nie im Produktivpfad erreichbar (Nebenbefund aus
#1357 S4a) — die Vertragsdoku macht das jetzt explizit, statt weiter
unwidersprochen „optional" zu behaupten.

### 5. Datenweg — `DailyForecast` bekommt vier neue Felder

`src/output/tokens/dto.py`, additiv (frozen dataclass, Default `None`
überall — keine Bestandsaufrufer brechen):
```python
wind_chill_min_c: Optional[float] = None   # Gehzeit-Tiefst, gefuehlt (FK)
wind_chill_max_c: Optional[float] = None   # Gehzeit-Hoechst, gefuehlt (FD)
night_temp_min_c: Optional[float] = None   # Nacht-Tiefst am Ziel, gemessen (N)
night_wind_chill_min_c: Optional[float] = None  # Nacht-Tiefst am Ziel, gefuehlt (FN)
```
**Wichtige Umstrukturierung:** Bisher überschrieb `sms_trip.py` das
Feld `temp_min_c` im Abendfall in-place mit dem Nachtwert (`day_min =
night_min`) — das würde `K` (das IMMER den Gehzeit-Tiefstwert zeigen
soll) im Abendbriefing zerstören. Ab jetzt bleibt `temp_min_c` IMMER
der Gehzeit-Tiefstwert (Quelle für `K`); der aufgelöste Nachtwert (echte
Nachttemperatur, fail-soft auf den Gehzeit-Wert wenn `night_weather`
fehlt — exakt das bestehende AC-6-Verhalten aus
`night_temp_evening_only.md`, nur jetzt in einem eigenen Feld statt
in-place überschrieben) wandert in `night_temp_min_c`, nur abends
gesetzt. Das bestehende `temp_max_c` (Quelle für `D`) ist unberührt.
Analog für gefühlt: `wind_chill_min_c`/`wind_chill_max_c` werden in
`_segments_to_normalized_forecast()` genau wie `temps_min`/`temps_max`
aus `s.aggregated.wind_chill_min_c`/`wind_chill_max_c` aggregiert
(min/max über alle Segmente); `night_wind_chill_min_c` kommt aus der
neuen `day_window.night_wind_chill_min_c()`, nur abends gesetzt,
fail-soft auf `wind_chill_min_c` wenn `night_weather` fehlt.

`src/output/renderers/day_window.py`: `night_temp_min_c()` wird
intern auf einen geteilten Kern umgestellt (gleiche Ankunft→06:00-
Fensterlogik, parametrisiertes DTO-Feld), zwei dünne Wrapper bleiben
öffentlich — `night_temp_min_c()` unverändert in Signatur/Verhalten,
neu `night_wind_chill_min_c()` liest `dp.wind_chill_c` statt
`dp.t2m_c`.

`src/output/tokens/builder.py`: die N/D-Schleife wird auf sechs
Einträge erweitert (Symbol, Wert, `evening_only: bool`) — `N`/`FN`
lesen jetzt `today.night_temp_min_c`/`today.night_wind_chill_min_c`
(statt bisher `today.temp_min_c`), `K`/`FK`/`FD` immer sichtbar,
`D` unverändert. Bestehende `MetricSpec`-Override-Fähigkeit
(`by_sym.get(sym)`) bleibt für alle sechs Symbole erhalten.

### 6. Gating der gefühlten Token — nur `K`/`D`/`N` sind unbedingt

`K`, `D`, `N` erscheinen wie bisher unbedingt (kein `MetricConfig`-Gate,
identisch zum heutigen Verhalten von `D`/`N`). `FK`/`FD`/`FN` erscheinen
NUR, wenn die Metrik „Gefühlte Temperatur" (`wind_chill`) im Trip
aktiviert ist — konsistent mit Mail-Pille und Telegram, die
`wind_chill` bereits heute über `dc.get_enabled_metric_ids()`/
`mc.enabled` gaten. Umsetzung: `trip_report.py`s bestehender Bug-#944-
Block (deaktivierte Metriken → `MetricSpec(symbol=sym, enabled=False)`)
wird um eine kleine Zuordnung erweitert:
```python
SMS_FELT_SYMBOLS_BY_METRIC = {"wind_chill": ("FN", "FK", "FD")}
```
Fehlt `"wind_chill"` in `active_metric_ids`, werden alle drei Symbole
als `enabled=False`-Specs angehängt (exakt dasselbe Prüfmuster wie für
SN/SFL — bewusst bug-kompatibel, keine neue Gating-Semantik).
`default_enabled` von `wind_chill` im Katalog ist `True` — bestehende
Trips zeigen die Felt-Token also ab dieser Auslieferung, sofern sie die
Metrik nicht aktiv deaktiviert haben (analog zur Mail-Pille seit #1357).

### 7. E-Mail-Kurzzusammenfassung — Morgen-Spanne + Felt-Satzteil

`compact_summary.py::_format_temperature()`: der Morgen-Zweig zeigt
künftig `{K}–{D}°C` (Spanne aus `summary.temp_min_c`/`temp_max_c` —
`summary.temp_min_c` ist bereits exakt der Gehzeit-Tiefstwert, keine
neue Datenquelle nötig) statt bisher nur `{D}°C`. Der Abend-Zweig bleibt
strukturell unverändert (`night_min_c` mit Fallback auf
`summary.temp_min_c`).

Neue Methode `_format_felt_temperature()`, Parallelstruktur zu
`_format_temperature()`: morgens `{FK}–{FD}°C` aus
`summary.wind_chill_min_c`/`wind_chill_max_c`; abends
`night_wind_chill_min_c` (neuer Parameter, analog `night_min_c`) mit
Fallback auf `summary.wind_chill_min_c`. Nur aufgerufen, wenn
`"wind_chill" in enabled` (existierendes `enabled`-Dict aus
`dc.metrics`).

**Geteilte Formatierung statt Nachbau:** Aus
`email/helpers.py::_aggregation_pill_text()` wird die reine
Spannen-Formatierung (Präfix + `min`–`max` mit `decimals`
Nachkommastellen, En-Dash) als kleine Funktion herausgezogen (z. B.
`format_temp_span(min_v, max_v, *, decimals) -> str`), die Zeit-Anker-
Ergänzung (`· Max HH:00`) bleibt EXKLUSIV in `_aggregation_pill_text()`
(die Kurzzusammenfassung kennt wie bisher keine Uhrzeit im Fließtext).
`compact_summary.py` importiert diese Funktion und ruft sie mit
`decimals=0` auf (konsistent mit der bestehenden gemessenen
Temperaturdarstellung im selben Satz und mit dem PO-Beispiel `gef.
6–13°C`), NICHT mit `decimals=1` wie die Kachelzeile — die
Kachelzeile bleibt bit-identisch (kein Eingriff in ihr Ergebnis, nur
Extraktion der Formel).

Der neue Satzteil wird direkt nach dem gemessenen Temperaturteil in die
bestehende `parts`-Liste eingefügt (`", ".join(parts)` bleibt
unverändert) — Präfix `"gef. "`, z. B. `"GR221 Tag1: 8–15°C, gef.
6–13°C, teils bewölkt, …"` (F2-Beispiel).

### 8. Telegram — Absicherung + Korrektur des Morgen-Sonderzweigs

**Absicherung (kein Verhaltens-Fix):** `TF {min}-{max}@{h}` erscheint
bereits heute in der Kurzübersicht, ist aber durch keinen Test belegt.
Neuer Test rendert eine Trip-Konfiguration mit aktivierter „Gefühlte
Temperatur" durch `render_telegram_bubbles()` und prüft, dass die
Kurzübersicht-Zeile `TF` mit Minimum, Maximum und Spitzenstunde zeigt.

**Korrektur (PO-Nachbesserung 2026-07-28) — Morgen-Sonderzweig entfällt
ersatzlos, für `temperature` UND `wind_chill`:** `_overview_line()`
(`narrow.py:368-424`) hat bisher morgens IMMER nur den Höchstwert
gezeigt (`if report_type == "morning": return f"{label} {hi}"`). Das
widersprach F1 („die kälteste Stunde unterwegs erscheint morgens UND
abends") und stand im Widerspruch zu AC-7 dieser Spec (Mail zeigt
morgens bereits eine Spanne). Dieser Morgen-Sonderzweig entfällt daher
vollständig:
```python
if metric_id in ("temperature", "wind_chill") and report_type == "evening":
    _night_val = night_min_c if metric_id == "temperature" else night_wind_chill_min_c
    if _night_val is not None:
        lo = f"{_night_val:.1f}"
```
Ohne den entfernten Morgenzweig läuft die Funktion für beide Größen im
Morgenfall automatisch in ihren bereits bestehenden generischen Pfad:
`lo`/`hi` werden aus `hits` berechnet, die aus `seg_tables` stammen —
den Gehzeit-Stundenzeilen, die schon heute nur die Wanderzeit abdecken
(nicht das Tagesfenster 04-19 Uhr). Der morgendliche Tiefstwert ist
damit **automatisch korrekt, ohne neue Datenquelle**: kein neues Feld,
keine neue Berechnung, nur das Entfernen der Sonderbehandlung — Telegram
braucht dafür sogar WENIGER Code als vorher. Der einzige verbleibende
Sonderfall ist die abendliche Nachtwert-Ersetzung (oben), jetzt
einheitlich für `temperature` und `wind_chill`. Neuer Parameter
`night_wind_chill_min_c: Optional[float] = None` auf `_overview_line()`;
`render_telegram_bubbles()` berechnet ihn einmalig
(`_night_wind_chill_min_c = night_wind_chill_min_c(night_weather,
segments, tz)`, analog zur bestehenden `_night_min_c`-Berechnung) und
reicht ihn bei jedem `_overview_line()`-Aufruf durch.

**Bewusste Ausnahme, bleibt unverändert — Vortagsvergleich
(`_tg_vortag_line`, `narrow.py:263-289`):** Der Filter „`temp_min`
entfällt morgens aus der Kandidatenliste" bleibt trotz der obigen
Korrektur bestehen. **Begründung (PO-Entscheidung 2026-07-28):** (a)
ein Vortagsvergleich der Nacht-Tiefsttemperatur ist morgens nicht
entscheidungsrelevant — es gibt morgens keine bevorstehende Nacht, auf
die sich ein Delta sinnvoll beziehen ließe; (b) der Vergleichswert in
`day_comparison.entries[*].temp_min` stammt aus einer anderen,
unabhängigen Snapshot-Quelle (Vortages-Vorhersage-Aggregat für den
gesamten Tag) als der neue Gehzeit-Tiefstwert dieser Spec — beide
stillschweigend gleichzusetzen wäre ein neuer, unbelegter
Annahme-Sprung, den diese Spec nicht trifft. Diese Ausnahme ist bewusst
und bleibt bestehen; sie ist KEINE Inkonsistenz zur neuen
Morgen-Sichtbarkeit von `K`/`FK` in der Kurzübersicht-Zeile — sie
betrifft eine andere Zeile (Vortagsvergleich) mit einer anderen
Datenquelle.

### 9. `docs/reference/sms_format.md` — Vertragspflege

Bei der Implementierung zu ergänzen/korrigieren:
- §2 Token-Reihenfolge: `N K D FN FK FD` statt `N D` in der
  Kopfzeile-Darstellung; Sichtbarkeitshinweise für `K`/`FK`/`FD`
  (immer) und `FN` (nur abends, nur wenn aktiviert).
- §3.2: neue Zeilen für `K`, `FK`, `FD`, `FN` nach demselben Muster wie
  bestehende `N`/`D`-Zeilen (Bedeutung, Quelle, Beispiel).
- §4 Null-Repräsentation: `K-`, `FK-`, `FD-`, `FN-` ergänzen. **Präzisierung
  (aus der RED-Phase, 2026-07-28):** Die Null-Form ist ausdrücklich an das
  Gating aus §6 gebunden — `FK-`/`FD-`/`FN-` erscheinen **nur**, wenn die
  Metrik „Gefühlte Temperatur" aktiviert ist und lediglich die Daten fehlen.
  Bei **deaktivierter** Metrik erscheint gar nichts, auch keine Null-Form
  (AC-5). Für `K-` gilt dieselbe Logik wie für die bestehenden `D-`/`N-`:
  unbedingt, da `K` nicht gegated ist.
- §6 Truncation-Strategie: die dokumentierten 6 Schritte um den neuen
  Felt-Kürzungsschritt auf 7 erweitern UND die vorbestehende Drift
  beheben (Code hat bereits einen 7./8. Schritt — Last-Resort-Priority-
  Pfad —, den die bisherige Doku gar nicht kennt).
- §3.6/§9: `WC` als „im Produktivpfad nie erreichbar, nur Legacy-CLI"
  kennzeichnen (Nebenbefund-Korrektur, s. §4 oben).
- §12 Versionierung: neuer Eintrag v2.12 mit Datum/Issue-Referenz.

## Acceptance Criteria

- **AC-1:** Given ein Trip ohne Einschränkung der gefühlten Temperatur /
  When das Morgenbriefing als SMS versendet wird / Then enthält die SMS
  eine eigenständige Tiefsttemperatur-Angabe für die kälteste erwartete
  Stunde unterwegs, obwohl das Morgenbriefing heute dort gar keinen
  Tiefstwert zeigt.
  - Test: `tests/tdd/test_sms_trip_min_temp_token.py::test_morning_shows_hiking_low`

- **AC-2:** Given ein Trip mit Ankunft am Etappenziel / When das
  Abendbriefing als SMS versendet wird / Then enthält die SMS ZWEI
  unterscheidbare Tiefstwerte — die kälteste Stunde unterwegs UND die
  Nacht-Tiefsttemperatur am Schlafplatz —, und der Nachtwert entspricht
  weiterhin exakt der bisherigen `N`-Bedeutung (keine Umkehr von
  `night_temp_evening_only.md` DEC-1).
  - Test: `tests/tdd/test_sms_trip_min_temp_token.py::test_evening_shows_both_hiking_and_night_low`

- **AC-3:** Given ein Trip mit aktivierter „Gefühlte Temperatur" / When
  Morgen- ODER Abendbriefing als SMS versendet wird / Then enthält die
  SMS zusätzlich zu den gemessenen Werten eine gefühlte
  Tiefst-unterwegs- UND eine gefühlte Höchsttemperatur.
  - Test: `tests/tdd/test_sms_trip_felt_temp_tokens.py::test_felt_hiking_low_and_high_present`

- **AC-4:** Given ein Trip mit aktivierter „Gefühlte Temperatur" und
  Ankunft am Etappenziel / When das Abendbriefing als SMS versendet
  wird / Then zeigt der gefühlte Nachtwert die echte gefühlte
  Nachttemperatur am Ziel — nicht die gefühlte Tiefsttemperatur
  unterwegs —, analog zur bestehenden Regel für die gemessene
  Nachttemperatur.
  - Test: `tests/tdd/test_sms_trip_felt_temp_tokens.py::test_felt_night_low_uses_destination_night_value`

- **AC-5:** Given ein Trip, bei dem der Nutzer „Gefühlte Temperatur"
  NICHT aktiviert hat / When Morgen- oder Abendbriefing als SMS
  versendet wird / Then enthält die SMS KEINE gefühlten
  Temperaturangaben — nur die gemessenen Werte erscheinen, unverändert
  zum heutigen Verhalten.
  - Test: `tests/tdd/test_sms_trip_felt_temp_tokens.py::test_felt_tokens_absent_when_metric_disabled`

- **AC-6:** Given eine SMS-Zeile, die durch alle bisherigen
  Kürzungsschritte immer noch über der 160-Zeichen-Grenze liegt, und
  sowohl gemessene als auch gefühlte Zusatzwerte enthält / When die SMS
  gekürzt wird / Then verschwinden die gefühlten Temperaturwerte
  zuerst — die gemessenen Werte (kälteste Stunde unterwegs,
  Nacht-Tiefst, Höchst) bleiben so lange wie möglich erhalten.
  - Test: `tests/tdd/test_sms_trip_min_temp_token.py::test_truncation_drops_felt_before_measured`

- **AC-7:** Given ein Trip mit Morgenbriefing / When die
  E-Mail-Kurzzusammenfassung gerendert wird / Then zeigt der
  Temperatur-Teil des Satzes eine Spanne (Tiefst- bis Höchsttemperatur)
  statt wie bisher nur des Höchstwerts.
  - Test: `tests/tdd/test_compact_summary_hiking_min_and_felt.py::test_morning_shows_temperature_range`

- **AC-8:** Given ein Trip mit aktivierter „Gefühlte Temperatur" / When
  die E-Mail-Kurzzusammenfassung (Morgen ODER Abend) gerendert wird /
  Then enthält der Satz direkt neben dem gemessenen Temperaturteil
  einen gefühlten Temperaturteil mit Präfix „gef." und derselben
  Spannen-Darstellung.
  - Test: `tests/tdd/test_compact_summary_hiking_min_and_felt.py::test_felt_range_appears_next_to_measured`

- **AC-9:** Given ein Trip mit aktivierter „Gefühlte Temperatur" und
  Ankunft am Etappenziel / When die abendliche
  E-Mail-Kurzzusammenfassung gerendert wird / Then basiert der
  gefühlte Tiefstwert im Satz auf der echten gefühlten Nachttemperatur
  am Ziel; fehlen Nachtdaten, fällt er fail-soft auf die gefühlte
  Tiefsttemperatur unterwegs zurück, ohne dass der Satz leer bleibt
  oder abstürzt.
  - Test: `tests/tdd/test_compact_summary_hiking_min_and_felt.py::test_felt_evening_uses_night_value_with_failsoft_fallback`

- **AC-10:** Given ein Trip mit aktivierter „Gefühlte Temperatur" / When
  das Telegram-Briefing gerendert wird / Then zeigt die
  Kurzübersicht-Zeile für die gefühlte Temperatur Minimum, Maximum und
  die Spitzenstunde — dieses bereits bestehende Verhalten ist ab jetzt
  durch einen Test belegt und kann nicht mehr unbemerkt wegbrechen.
  - Test: `tests/tdd/test_telegram_felt_temperature_overview.py::test_felt_overview_line_present`

- **AC-11:** Given ein Trip mit aktivierter „Gefühlte Temperatur" / When
  das Telegram-Briefing für Morgen UND Abend gerendert wird / Then
  zeigt die Kurzübersicht-Zeile für die gefühlte Temperatur in BEIDEN
  Report-Typen eine Tiefst-Höchst-Spanne — morgens mit der kältesten
  Gehzeit-Stunde als Untergrenze, abends mit der echten gefühlten
  Nachttemperatur am Ziel als Untergrenze —, exakt symmetrisch zur
  gemessenen Temperaturzeile.
  - Test: `tests/tdd/test_telegram_felt_temperature_overview.py::test_felt_overview_shows_range_morning_and_night_value_evening`

- **AC-12:** Given ein Trip mit Morgenbriefing / When das
  Telegram-Briefing gerendert wird / Then zeigt die
  Kurzübersicht-Zeile für die gemessene Temperatur eine
  Tiefst-Höchst-Spanne mit der kältesten Gehzeit-Stunde als
  Untergrenze — nicht mehr nur den Höchstwert wie bisher.
  - Test: `tests/tdd/test_telegram_temperature_morning_range.py::test_measured_overview_shows_range_in_morning`

## Test-Plan

Kern-Schicht (deterministisch, echte Renderer-Aufrufe, kein
Mock-Theater), Testdateien nach Verhalten benannt (nicht nach
Issue-Nummer — `test_naming_gate.py` blockt neue issue-nummerierte
Dateien hart):

| AC | Testdatei::Testfall |
|----|----------|
| AC-1 | `tests/tdd/test_sms_trip_min_temp_token.py::test_morning_shows_hiking_low` |
| AC-2 | `tests/tdd/test_sms_trip_min_temp_token.py::test_evening_shows_both_hiking_and_night_low` |
| AC-3 | `tests/tdd/test_sms_trip_felt_temp_tokens.py::test_felt_hiking_low_and_high_present` |
| AC-4 | `tests/tdd/test_sms_trip_felt_temp_tokens.py::test_felt_night_low_uses_destination_night_value` |
| AC-5 | `tests/tdd/test_sms_trip_felt_temp_tokens.py::test_felt_tokens_absent_when_metric_disabled` |
| AC-6 | `tests/tdd/test_sms_trip_min_temp_token.py::test_truncation_drops_felt_before_measured` |
| AC-7 | `tests/tdd/test_compact_summary_hiking_min_and_felt.py::test_morning_shows_temperature_range` |
| AC-8 | `tests/tdd/test_compact_summary_hiking_min_and_felt.py::test_felt_range_appears_next_to_measured` |
| AC-9 | `tests/tdd/test_compact_summary_hiking_min_and_felt.py::test_felt_evening_uses_night_value_with_failsoft_fallback` |
| AC-10 | `tests/tdd/test_telegram_felt_temperature_overview.py::test_felt_overview_line_present` |
| AC-11 | `tests/tdd/test_telegram_felt_temperature_overview.py::test_felt_overview_shows_range_morning_and_night_value_evening` |
| AC-12 | `tests/tdd/test_telegram_temperature_morning_range.py::test_measured_overview_shows_range_in_morning` |

**Golden-Regression (kein neuer Testfall, bewusste Neuerzeugung):** alle
5 `tests/golden/sms/*.txt` (K erscheint neu, immer) und alle 10
`tests/golden/email/*-{plain,html}.txt` werden über
`tests/golden/email/regenerate.py` bzw. das SMS-Golden-Äquivalent neu
eingefroren. Explizit betroffen und namentlich zu prüfen: die beiden
**Morgen**-Profile `arlberg-winter-morning-{plain,html}.txt` und
`gr20-spring-morning-{plain,html}.txt` — deren Kurzzusammenfassungssatz
wechselt von Einzelwert auf Spanne (AC-7); die drei **Abend**-Profile
(`gr20-summer-evening`, `corsica-vigilance`, `gr221-mallorca-evening`)
ändern sich nur, wenn im jeweiligen Fixture „Gefühlte Temperatur"
aktiviert ist (F2-Satzteil). Kein Telegram-Golden existiert im Projekt
(`tests/golden/` hat keinen `telegram/`-Ordner) — die
Telegram-Korrektur aus §8 wird ausschließlich über die neuen
TDD-Tests (AC-10 bis AC-12) abgesichert, nicht über Golden-Fixtures.
Das ist eine erwartete Fixture-Änderung (Verhaltensverbesserung), kein
Regressionsbefund. Ebenfalls anzupassen:
`tests/unit/test_trip_summary_text.py:104` (byte-identischer Vergleich),
`tests/integration/test_multi_day_trend.py:382-388,499`,
`tests/tdd/test_night_temp_evening_only.py:239,280` — dort wird
`N`/Nacht-Verhalten weiterhin exakt geprüft, nur die umgebende Zeile
ändert sich um `K`/Felt-Zusätze.

**Renderer-Commit-Gate #811 (Pflicht vor Commit):** `sms_trip.py`,
`compact_summary.py`, `email/helpers.py` sind Mail-Inhalts-Dateien →
`renderer_mail_gate.py` blockiert, bis (1)
`tests/tdd/test_issue_811_mode_matrix.py` grün ist UND (2) ein frischer
`briefing_mail_validator.py`-Lauf gegen eine echte Staging-Testmail
erfolgreich war.

## Out of Scope

- **Ortsvergleich (Compare):** keine Änderung in dieser Lieferung —
  weder die Tiefst-unterwegs- noch die Gefühlt-Erweiterung betrifft
  Compare-SMS/-Mail. Folgt ggf. mit einer eigenen Spec
  (Konvergenz-Programm #1230).
- **Doppelter Zeilenbau Telegram vs. Mail-Tabelle:** `trip_report.py`s
  eigene `_dp_to_row()`-Kopie (Zeile 468-496) vs. `email/helpers.py::
  dp_to_row()` bleibt bestehen — Nebenbefund, gehört nach #1199-Triage,
  nicht Teil dieser Lieferung. Betriebswirkung dieser Lieferung: keine,
  da beide Kopien dieselben Katalog-Felder lesen.
- **E-Mail-Betreffzeile:** `subject.py:167`s Positiv-Liste
  `_WHITELIST_FORECAST = ("D","W","G")` bleibt unverändert — die neuen
  Token `K`/`FK`/`FD`/`FN` erscheinen dort bewusst NICHT (Betreff bleibt
  knapp).

## Known Limitations

- **`WC`-Kontraktlücke:** bleibt als reine Vertragsdoku-Korrektur
  bestehen (kein Code-Eingriff), s. Implementation Details §4.
- **Kachelzeilen-Formatierungsfunktion:** die Extraktion aus
  `email/helpers.py::_aggregation_pill_text()` berührt eine
  Mail-Gate-#811-geschützte Datei — Verhalten der Kachelzeile selbst
  bleibt bit-identisch (reine Extraktion, kein Verhaltenswechsel), muss
  aber durch den bestehenden Golden-Test für die Kachelzeile
  mitbewiesen werden (keine neue Fixture-Änderung an dieser Stelle
  erwartet).
- **Bug-#944-Gating-Semantik nicht neu geprüft:** die Erweiterung um
  `SMS_FELT_SYMBOLS_BY_METRIC` übernimmt bewusst das bestehende
  Prüfmuster (`metric_id not in active_metric_ids`) unverändert,
  inklusive dessen möglicher Unschärfe bei `enabled=False`-Einträgen,
  die weiterhin in `dc.metrics` gelistet sind — Untersuchung dieser
  Unschärfe ist nicht Teil dieser Lieferung.
- **Telegram-Vortagsvergleich (`_tg_vortag_line`) filtert „Temp min"
  morgens weiterhin heraus** — bewusste, PO-bestätigte Ausnahme, s.
  Implementation Details §8. Keine Inkonsistenz zur neuen
  Morgen-Sichtbarkeit von `K`/`FK` in der Kurzübersicht-Zeile.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Kein neues strukturelles Muster. Die Erweiterung folgt
  exakt dem in `night_temp_evening_only.md` etablierten Muster
  (geteilte Wert-Ableitungsfunktion + report-type-abhängiges
  Sichtbarkeits-Gate), nur um ein zusätzliches, paralleles Werte-Paar
  (gefühlt statt gemessen) und einen zusätzlichen, danebenstehenden
  Tiefstwert (unterwegs statt Nacht) erweitert. Die Korrektur an
  Telegram (§8) entfernt sogar Code (Morgen-Sonderzweig), statt neuen
  hinzuzufügen. Kein neuer Kanal, kein neuer Provider, keine
  Schema-Änderung, keine Auth-/Editor-Paradigmenänderung.

## Changelog

- 2026-07-28: Initial spec created — Issue #1410, Epic #1372 Scheibe 2
  zu #1357 S4a
- 2026-07-28: PO-Nachbesserung — Widerspruch zwischen AC-7 (E-Mail
  zeigt morgens Spanne) und der ursprünglichen Telegram-Beschreibung
  (morgens weiterhin nur Höchstwert) behoben. Telegram-Morgen-
  Sonderzweig entfällt jetzt für `temperature` UND `wind_chill`
  ersatzlos (§8), AC-11 umgeschrieben, neue AC-12 für die gemessene
  Temperatur ergänzt, neuer Abschnitt „Berührung bestehender
  Entscheidungen" dokumentiert die (Teil-)Ablösung von DEC-2 aus
  `night_temp_evening_only.md` (DEC-1 bleibt unberührt), bewusste
  Ausnahme für `_tg_vortag_line` begründet und festgeschrieben.
