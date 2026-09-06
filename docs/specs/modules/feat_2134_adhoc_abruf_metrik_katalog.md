---
entity_id: feat_2134_adhoc_abruf_metrik_katalog
type: feature
created: 2026-09-06
updated: 2026-09-06
status: implemented
version: "1.0"
tags: [metric-catalog, trip-command-processor, ad-hoc-abruf, single-source-of-truth]
---

# Ad-hoc-Abruf: Befehlssatz aus dem Metrik-Katalog ableiten

## Approval

- [ ] Approved

## Purpose

Der Ad-hoc-Abruf (Nutzer fragt unterwegs per Telegram oder E-Mail nach einer
Wettergröße) kennt heute nur drei Größen (Gewitter, Wind, Regen), weil sie in
einer handgepflegten Kurzliste (`_DRILLDOWN_METRICS`) stehen. Insgesamt
existieren **acht** unabhängig gepflegte Befehlslisten im Repo (Kommando-
Whitelist, Bare-Keyword-Map, Query-Keys, Hilfetext, zwei Fehlertexte, zwei
E-Mail-Fußzeilen), von denen keine zwei übereinstimmen — der Nutzer bekommt je
nach Kanal und Fehlerweg eine andere Auskunft darüber, was er darf.

Diese Spec macht den Metrik-Katalog (`src/app/metric_catalog.py`,
`MetricDefinition.col_label`) zur **einzigen Quelle** für Abrufwörter, Hilfe-
Ausgabe, Fehlertexte und beide E-Mail-Fußzeilen. Sie räumt zugleich zwei
eingeschlossene Bugs mit ab, die dieselbe Funktion (`_parse_command`)
betreffen: `>` vor „Heute" wird nicht erkannt (#2137) und `/strecke 5` mit
führendem Slash wird nicht erkannt (#2120).

Scheibe S1 von Epic #2133, Ticket #2134.

## Source

- **File:** `src/services/trip_command_processor.py`
- **Identifier:** `_DRILLDOWN_METRICS`, `_DRILLDOWN_PATTERN`, `_HOURS_PATTERN`,
  `_BARE_KEYWORD_MAP`, `_VALID_COMMANDS`, `_parse_command`, `_show_help`,
  `_handle_drilldown`, `_handle_hours_drilldown`

## PO-Vorgaben (bindend, 2026-09-06)

1. Das Abrufwort ist die Tabellenüberschrift `MetricDefinition.col_label` —
   einheitlich über alle Kanäle. Nicht `label_de`, nicht ein neu erfundenes
   Wort.
2. `Hilfe` gibt die vollständige Liste aus — auf allen Kanälen, ausdrücklich
   auch per E-Mail.
3. Der E-Mail-Fußzeilenblock „Antwort-Kommandos" wird angepasst (Klartext UND
   HTML).
4. Umfangreiche Tests.
5. #2137 (`> Heute` wird nicht erkannt) und #2120 (`/strecke 5` wird nicht
   erkannt) werden mit abgeräumt — dieselbe Funktion `_parse_command`.

## Estimated Scope

- **LoC:** ~430–550 (Produktiv ~230–280, Tests ~250–320, Vergleichsdateien
  regeneriert und zählen als generiert nicht mit)
- **Files:** 6 Produktivdateien, ~10 angepasste + ~4 neue Testdateien, 12
  regenerierte Vergleichsdateien
- **Effort:** high
- **LoC-Limit:** 250-Deckel wird gerissen → Anhebung auf 500 nötig
  (`workflow.py set-field loc_limit_override 500`)

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `src/app/metric_catalog.py` (`MetricDefinition`, `get_all_metrics`) | module | Quelle des Vokabulars — liefert bereits nur `selectable=True` |
| `src/output/metric_format.py` (`format_value`, `THUNDER_LABEL_DE`) | module | Zentrale Wertformatierung inkl. Einheit + `display_unit` |
| `src/utils/geo.py` (`degrees_to_compass`) | function | Windrichtung als Himmelsrichtung statt Gradzahl |
| `src/services/weather_extractor.py` (`drilldown`) | function | Generischer Einzelgrößen-Abruf, unverändert nutzbar |
| `_day_window()` / `trip_local_today()` (ADR-0044) | function | Ortstag-Fensterung „heute"/„morgen", unverändert weiterverwenden |
| `email/plain.py` (`ACTIONS_BUBBLE_BUTTONS`, bereits aus `trip_command_processor` importiert) | module | Beleg für zirkelfreie Import-Richtung |

## Implementation Details

### Normalisierung des Eingabeworts

Regel: kleingeschrieben, `%` → `pct`, `°` getilgt, übrige Nicht-Alphanumerik
getilgt.

Begründung (gemessen, 2026-09-06): Ohne die `%`→`pct`-Regel fallen `Rain`
(precipitation) und `Rain%` (rain_probability) auf dasselbe normalisierte
Wort zusammen — mit bloßer Tilgung 1 Kollision unter den 29 `col_label`-
Werten, mit `%`→`pct` 0 von 29. `°` wird getilgt (`0°Line` → `0line`), die
schwer tippbare Nullgradgrenze bleibt zusätzlich über die Zweitschreibweise
erreichbar (s. u.).

### Zweitschreibweise über `sms_code`

`sms_code` wird zusätzlich als Alias akzeptiert, z. B. `FZ` für die
Nullgradgrenze (Katalogkürzel `0°Line` ist schwer tippbar). `sms_code` ist
über alle 27 belegten Werte kollisionsfrei.

### `selectable=false` wird nicht zweitformuliert

Die Ableitung des Vokabulars läuft ausschließlich über `get_all_metrics()`,
das bereits nach `selectable=True` filtert. Betroffen (bleiben unerreichbar
per Abrufwort): `confidence` (#710, Final — niemals per-Etappe-Metrik),
`temperature_cold`, `cape`. Wer stattdessen über eine interne `_METRICS`-Liste
iteriert, baut die Filterregel ein zweites Mal auf — genau die Doppelpflege,
die dieses Ticket abschafft.

### Formatierer folgt aus dem Katalogeintrag

Keine neue Liste — Dispatch nach Eigenschaft des `MetricDefinition`-Eintrags:

| Bedingung | Formatierer | Beleg |
|---|---|---|
| `metric.is_level` | `_thunder_fmt` (bereits katalog-gespeist über `THUNDER_LABEL_DE`) | `metric_format.py:283` |
| `dp_field == "wind_direction_deg"` | `degrees_to_compass()` | `src/utils/geo.py:32` |
| `dp_field == "precip_type"` | neues `PRECIP_TYPE_LABEL_DE` (analog zu `THUNDER_LABEL_DE`) | neu in `src/output/metric_format.py` |
| sonst | `format_value(metric.id, value)` | `metric_format.py:78-130` — rundet, hängt Einheit an, rechnet `display_unit` m→km (Sichtweite) |

Die Prüfung geht auf `metric.is_level`, **nicht** auf `metric.id == "thunder"`
— damit eine künftige zweite Stufengröße automatisch mitgetragen wird, ohne
Codeänderung an dieser Stelle.

### Einzelquelle für Steuerbefehle

Neue Konstante `_COMMAND_SPECS` in `src/services/trip_command_processor.py`
(Wort, Argumentform, Beschreibung) für die Nicht-Metrik-Befehle (Heute,
Morgen, Strecke, Pause, Skip, Weiter, Report, Hilfe, …). Import-Richtung ist
geprüft und zirkelfrei: `output/renderers/email/plain.py:52` importiert
bereits `ACTIONS_BUBBLE_BUTTONS` aus `trip_command_processor`; die
Gegenrichtung existiert nicht — `trip_command_processor` importiert nur
`output.metric_format`, nie `output.renderers.*`.

### Metrik-Abrufwörter werden abgeleitet, nicht eingetragen

Neue Funktion `metric_command_words()` in `src/app/metric_catalog.py`, neben
den dort bereits bestehenden Ableitungen (`metric_and_aggregation_for_field()`,
`SMS_MULTI_SYMBOLS_BY_METRIC`). Liefert normalisiertes Wort → `metric.id`,
über `get_all_metrics()` — erbt `selectable=False`-Filterung automatisch.

### Temperatur-Abbruch entschärfen

`trip_command_processor.py:799` bricht heute mit `if not r_temp.available:
return` den **gesamten** Stundenabruf ab, obwohl Wind/Regen/Gewitter separat
abgerufen und per Zeitstempel gemappt werden (`:812-814`) und damit unabhängig
vorhanden sein könnten. Künftig: Abbruch nur, wenn **alle** abgerufenen
Größen fehlen; einzelne fehlende Größen werden als Lücke benannt, nicht durch
stillen Komplettabbruch verdeckt.

### Hilfe-Länge

Überschlagsrechnung: 12 Befehle × ~55 Zeichen + 29 Metrikwörter × ~35 Zeichen
+ Rahmen ≈ 1800 Zeichen, gegen die Telegram-Grenze von 4096
(`src/output/channels/telegram.py:18`). Eine Nachricht reicht, keine
Aufteilung nötig — die Metrikzeile trägt Kürzel + Einheit, nicht den vollen
`label_de`.

### Ortstag bleibt unverändert

`_day_window()` löst „heute"/„morgen" bereits über `trip_local_today()` auf
(ADR-0044). Diese Spec baut das nicht neu.

### Betroffene Dateien

| Datei | Change | Beschreibung |
|---|---|---|
| `src/app/metric_catalog.py` | MODIFY | neue Funktion `metric_command_words()` |
| `src/services/trip_command_processor.py` | MODIFY | `_COMMAND_SPECS`, `_DRILLDOWN_METRICS`/`_DRILLDOWN_PATTERN` durch Katalog-Auflösung ersetzt, `_parse_command` streift führende `>`/`/`, `_show_help` abgeleitet, Fehlertexte `:402`/`:488` ersetzt, Temperatur-Abbruch `:799` |
| `src/output/metric_format.py` | MODIFY | `PRECIP_TYPE_LABEL_DE` neben `THUNDER_LABEL_DE` |
| `src/services/inbound_telegram_reader.py` | MODIFY | eigene Liste `:33-35` und Fehlertext `:206` an dieselbe Quelle gehängt |
| `src/output/renderers/email/plain.py` | MODIFY | Fußzeile `:364-375` aus `_COMMAND_SPECS` |
| `src/output/renderers/email/html.py` | MODIFY | `_render_kommandos_section` `:471-519` aus `_COMMAND_SPECS` |
| `tests/golden/email/{stem}-plain.txt` (5), `{stem}-html.txt` (5) | REGENERATE | nach Diff-Verfahren s. u. |
| `tests/fixtures/outlook_trip_parity/trip_outlook_show_acc_true.{html,txt}` | REGENERATE | dito |

## Expected Behavior

- **Input:** getipptes Wort per Telegram oder E-Mail-Antwort, z. B. `Sicht`,
  `Rain%`, `FZ`, `> Heute`, `/strecke 5`, `Hilfe`.
- **Output:** bei einem gültigen Katalog-Wort ein Stundenverlauf/eine Antwort
  mit korrekt formatiertem Wert (Einheit, Stufenwort, Himmelsrichtung je nach
  Größe); bei `Hilfe` die vollständige Liste aller 29 wählbaren Größen plus
  Steuerbefehle, kanalunabhängig identisch in der Wortmenge; bei fehlender
  Einzelgröße eine benannte Lücke statt eines stillen Komplettabbruchs.
- **Side effects:** beide E-Mail-Fußzeilen (Klartext + HTML) und der
  Telegram-Fehlertext ändern sich sichtbar, weil sie aus derselben Quelle
  gespeist werden; zwölf zeichengenaue Vergleichsdateien werden regeneriert.

## Acceptance Criteria

- **AC-1:** Given der Metrik-Katalog führt die Sichtweite (`visibility`) mit der Tabellenüberschrift `Visib` und Anzeige-Einheit km, und sie ist heute per Ad-hoc-Abruf nicht erreichbar / When ein Nutzer per Telegram `Visib` sendet / Then enthält die Antwort Stundenwerte der Sichtweite mit der Einheit km aus dem Katalog.
  - Test: Ad-hoc-Abruf einer bisher unmöglichen Größe über ihr `col_label`, Antwort enthält Zahl + Einheit km.
- **AC-2:** Given `humidity` (`col_label` = `Humid`) ist im Katalog `selectable=true` und hat in keiner Sonderliste des Abrufpfads einen Eintrag / When ein Nutzer `Humid` sendet / Then enthält die Antwort die Stundenwerte der Luftfeuchtigkeit — geprüft über den Kanal-Eingang, nicht über einen direkten Aufruf der Ableitungsfunktion.
  - Test: Abruf von `Humid` durch `TripCommandProcessor.process()` mit einer `InboundMessage`; ein `grep` belegt zusätzlich, dass `humidity` in keiner Erlaubt-Liste des Abrufpfads namentlich vorkommt.
- **AC-3:** Given `confidence`, `temperature_cold` und `cape` sind im Katalog mit `selectable=false` markiert / When eines ihrer `col_label`-Wörter oder ein naheliegendes Kürzel per Ad-hoc-Abruf gesendet wird / Then antwortet das System mit „unbekanntes Kommando"/Hilfe-Verweis statt mit einem Wert, weil `metric_command_words()` sie nicht enthält.
  - Test: Abruf von `confidence`-Wort liefert keine Metrik-Antwort.
- **AC-4:** Given die Temperatur-Teilgröße eines Stundenabrufs ist nicht verfügbar, Wind/Regen/Gewitter aber schon / When der Nutzer die Stundenübersicht abruft / Then erscheinen Wind, Regen und Gewitter in der Antwort und die fehlende Temperaturspalte wird als Lücke benannt, statt dass die gesamte Antwort leer bleibt.
  - Test: Extraktor liefert `r_temp.available=False`, andere Größen `available=True` — Antwort enthält die verfügbaren Werte und eine Lückenkennzeichnung für Temperatur.
- **AC-5:** Given ein Nutzer sendet `> Heute` mit führendem `>`-Zeichen / When `_parse_command` die Eingabe verarbeitet / Then wird der Befehl als „Heute" erkannt und die Tagesübersicht ausgeliefert (behebt #2137).
  - Test: Eingabe `"> Heute"` erzeugt dieselbe Antwort wie `"Heute"`.
- **AC-6:** Given ein Nutzer sendet `/strecke 5` mit führendem `/`-Zeichen / When `_parse_command` die Eingabe verarbeitet / Then wird der Befehl als „Strecke" mit Argument `5` erkannt (behebt #2120).
  - Test: Eingabe `"/strecke 5"` erzeugt dieselbe Antwort wie `"strecke 5"`.
- **AC-7:** Given eine unveränderte Eingabe ohne führendes Sonderzeichen, z. B. `Wind` / When `_parse_command` sie verarbeitet / Then bleibt das Verhalten identisch zum Stand vor dieser Änderung (Positivkontrolle gegen Überkorrektur durch das Streifen von `>`/`/`).
  - Test: Eingabe `"Wind"` liefert exakt dieselbe Antwort wie vor der Änderung an `_parse_command`.
- **AC-8:** Given der Metrik-Katalog führt 29 `selectable`-Größen / When der Nutzer `Hilfe` per Telegram sendet / Then enthält die Antwort für jede der 29 Größen ein Abrufwort, strukturell geprüft gegen `get_all_metrics()` (kein Textvergleich gegen eine fest eingetragene Liste).
  - Test: Menge der in der Hilfe-Antwort enthaltenen Wörter ⊇ Menge der normalisierten `col_label`-Werte aus `get_all_metrics()`.
- **AC-9:** Given der Metrik-Katalog führt 29 `selectable`-Größen / When der Nutzer `Hilfe` per E-Mail-Antwort sendet / Then erhält er dieselbe vollständige Liste wie per Telegram (PO-Vorgabe 2 — Hilfe ausdrücklich auch per E-Mail).
  - Test: E-Mail-Kommandoantwort auf `Hilfe` enthält dieselbe Wortmenge wie die Telegram-Antwort.
- **AC-10:** Given ein Nutzer sendet ein unbekanntes Wort und der heutige Fehlertext (`:402`, `:488`) nennt nur `ruhetag, report, startdatum, abbruch, status, hilfe` / When das System den Fehlertext erzeugt / Then nennt er den vollständigen aktuellen Befehlssatz aus derselben Quelle wie die Erkennung, insbesondere die heute verschwiegenen `heute`, `morgen`, `jetzt`, `gewitter` und `strecke`.
  - Test: Fehlertext bei unbekanntem Kommando enthält jedes Wort aus `_COMMAND_SPECS`; Mutations-Gegenprobe: ein Eintrag aus `_COMMAND_SPECS` entfernt lässt den Test rot werden (der Text ist abgeleitet, nicht danebengeschrieben).
- **AC-11:** Given die Klartext- und die HTML-E-Mail-Fußzeile „Antwort-Kommandos" / When beide gerendert werden / Then stammen beide aus derselben `_COMMAND_SPECS`-Quelle und enthalten dieselbe Befehlsmenge (bisher fehlte `strecke` in beiden, `ruhetag` zusätzlich in HTML).
  - Test: Menge der Befehlswörter in `plain.py`-Fußzeile == Menge in `html.py`-Fußzeile.
- **AC-12:** Given der Telegram-Fehlertext in `inbound_telegram_reader.py:206` / When ein unbekanntes Kommando eingeht / Then stammt der Fehlertext aus derselben Quelle wie der Fehlertext in `trip_command_processor.py`, nicht aus einer eigenen achten Liste.
  - Test: Beide Fehlertexte enthalten dieselbe Befehlsmenge, geprüft strukturell (nicht Zeichenkette-für-Zeichenkette, da Formulierung kanalspezifisch bleiben darf).
- **AC-13:** Given die Größe `thunder` trägt `is_level=True` und die Tabellenüberschrift `Thdr` / When ein Nutzer `Thdr` sendet / Then erscheinen die Stundenwerte als Stufenwörter aus `THUNDER_LABEL_DE`, nicht als Rohzahl — und die Auswahl des Formatierers hängt an `is_level`, nicht am Namen `thunder`.
  - Test: Abruf von `Thdr` liefert Stufenwörter; Mutations-Gegenprobe: `is_level` einer anderen Größe testweise auf `True` gesetzt lässt auch diese als Stufenwort erscheinen (die Regel hängt am Merkmal, nicht an der Kennung).
- **AC-14:** Given die Größe `wind_direction` (`dp_field == "wind_direction_deg"`) trägt die Tabellenüberschrift `WDir` / When ein Nutzer `WDir` sendet / Then erscheinen die Stundenwerte als Himmelsrichtung (z. B. `NW`), nicht als Gradzahl.
  - Test: Abruf von `WDir` liefert Kompass-Bezeichnungen, keine reine Zahl mit `°`.
- **AC-15:** Given die Größe `precip_type` trägt die Tabellenüberschrift `PType` / When ein Nutzer `PType` sendet / Then erscheinen die Stundenwerte als deutsches Wort aus `PRECIP_TYPE_LABEL_DE` (z. B. „Schnee"), nicht als interner Enum-Bezeichner.
  - Test: Abruf von `PType` liefert deutsche Wörter, kein `PrecipType.SNOW`.
- **AC-16:** Given die Größe `visibility` hat `unit` = m und `display_unit` = km / When ein Nutzer `Visib` sendet / Then tragen die Werte die Einheit km und sind entsprechend umgerechnet (2000 m erscheint als 2 km), nicht als vierstellige Meterzahl.
  - Test: Stundenwert 2000 im Feld `visibility_m` erscheint in der Antwort als `2 km`.
- **AC-17:** Given eine im Katalog geführte Größe ist im abgefragten Gebiet nicht befüllt (Fallback-Kette liefert kein Stundenfeld) / When sie per Ad-hoc-Abruf abgefragt wird / Then benennt die Antwort die Lücke ausdrücklich (z. B. „nicht verfügbar für diesen Ort"), statt zu schweigen oder eine leere Antwort zu senden.
  - Test: Stundenfeld für die abgefragte Größe ist `None`/fehlt — Antwort enthält einen expliziten Lückenhinweis statt Leerausgabe.
- **AC-18:** Given die 29 normalisierten `col_label`-Wörter im Katalog / When `metric_command_words()` gebildet wird / Then ist die Menge kollisionsfrei — ein Test schlägt fehl, sobald zwei Größen auf dasselbe normalisierte Wort abbilden.
  - Test: Kollisionswächter über alle `selectable=True`-Einträge, inklusive Regressionsfall `Rain`/`Rain%` (die `%`→`pct`-Regel verhindert die Kollision).
- **AC-19:** Given das `col_label` der Sichtweite wird im Katalog testweise von `Visib` auf einen anderen Wert geändert / When ein Nutzer danach `Visib` sendet / Then wird `Visib` **nicht** mehr erkannt und der neue Wert **wird** erkannt — das Abrufwort ist aus dem Katalog abgeleitet und nicht daneben eingetragen.
  - Test: Mutations-Gegenprobe per String-Ersetzung mit externer Sicherungskopie (nie `git checkout/stash/reset`); beide Richtungen geprüft, nicht nur das Verschwinden.
- **AC-20:** Given `gewitter` ist ein bestehender Steuerbefehl (→ `heute_gewitter`) und `Thdr` ist das Abrufwort derselben Wettergröße / When beide gesendet werden / Then liefert `gewitter` weiterhin die Gewitter-Tagesaussage und `Thdr` den Stundenverlauf — Steuerbefehle haben Vorrang und werden vom Metrik-Vokabular nicht verdrängt.
  - Test: Beide Eingaben in einem Testlauf, zwei unterschiedliche Antworten; zusätzlich ein Wächter, dass die Wortmenge der Steuerbefehle und die der Metrik-Abrufwörter disjunkt sind.

## Known Limitations

- **Elf zeichengenaue Vergleichsdateien brechen sicher**, sobald sich die
  Fußzeile ändert: `tests/golden/email/{stem}-plain.txt` (5),
  `{stem}-html.txt` (5), `tests/fixtures/outlook_trip_parity/
  trip_outlook_show_acc_true.{html,txt}` (2) — macht zusammen 12 Dateien.
  Verfahren zum korrekten Neuziehen (PFLICHT, sonst rutscht eine
  unbeabsichtigte Änderung mit durch):
  1. Baseline sichern: `git diff` auf die Vergleichsdateien ist leer.
  2. Betroffenen Test rot laufen lassen, den gerenderten Ist-Stand in eine
     Scratch-Datei schreiben.
  3. `diff alt neu` zeilenweise — jede Abweichung außerhalb des
     Fußzeilenblocks ist ein Abbruchkriterium, keine Rundungstoleranz.
  4. Erst dann überschreiben. Der committete Diff ist der Beleg.
- **Acht Größen teilen sich zwei Stundenfelder:** `temperature`,
  `temperature_night`, `temperature_day_low`, `temperature_day_high` zeigen
  alle auf `t2m_c`; die vier `wind_chill_*`-Varianten auf `wind_chill_c`. Als
  Verlauf liefern sie denselben Kurvenzug — sie unterscheiden sich nur in der
  Tages-Auswertung. Das ist hinzunehmen und zu dokumentieren, nicht
  wegzukürzen: die Abrufwörter sind eindeutig, und eine Auswahl unter ihnen
  zu treffen hieße, wieder eine neue, handgepflegte Liste einzuführen.
- **Geführt ≠ gefüllt:** Nicht jede Größe ist in jedem Gebiet befüllt
  (Fallback-Kette, `docs/reference/decision_matrix.md`). Eine Lücke wird
  benannt (AC-17), nicht als Schweigen ausgeliefert — dieselbe Anforderung
  wie die Messlücken-Kennzeichnung aus #2050 S4b.
- **Abgrenzung (ausdrücklich NICHT Teil dieser Scheibe):** Zeitachse „ab
  jetzt" und Wechselpunkte → S2 · Kanaltreue der Antwort → S3/#2126 ·
  Premium-SMS als Eingangsweg → S4 · Verlaufsdarstellung für die Kurzform →
  S5 · der 3-Tagesausblick → #2136.
- **Telegram-Buttons bleiben eine kuratierte Auswahl** (Stunden, Gewitter,
  Wind, Regen) — sie können nicht 29 Größen tragen. Das getippte Wort ist der
  Weg zur vollen Breite; kein Widerspruch zu AC-8/AC-9.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — erfüllt ADR-0042 (Namensklassen: keine neue
  Namensliste, sondern Ableitung), ADR-0044 (Ortstag über
  `trip_local_today()`, unverändert) und ADR-0037/ADR-0055 (Katalog als
  Quelle statt handgepflegter Liste).
- **Rationale:** Der Umbau ersetzt acht divergierende Listen durch
  Ableitungen aus dem bestehenden Metrik-Katalog. Das setzt ein im Repo
  etabliertes Muster fort (`metric_and_aggregation_for_field()`,
  `SMS_MULTI_SYMBOLS_BY_METRIC`) statt es zu durchbrechen — kein neues ADR
  nötig.

## Changelog

- 2026-09-06: Initial spec created
