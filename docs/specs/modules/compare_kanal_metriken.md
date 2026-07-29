---
entity_id: compare_kanal_metriken
type: bugfix
created: 2026-07-29
updated: 2026-07-29
status: draft
version: "1.0"
tags: [compare, telegram, sms, kurzform, issue-1362, issue-1399, epic-1372]
---

# Compare-Kurznachrichten bedienen die volle Metrik-Auswahl (Scheibe S5)

Issues [#1362](https://github.com/henemm/gregor_zwanzig/issues/1362) und
[#1399](https://github.com/henemm/gregor_zwanzig/issues/1399), Etappe S5 des
Metrik-Zielbilds (Epic #1372, Dach #1374).

## Approval

- [x] Approved — PO-Freigabe 2026-07-29

## Purpose

Die Kurznachrichten des Ortsvergleichs (Telegram, SMS) kennen heute nur sechs
fest verdrahtete Wettergrößen. Wählt der Nutzer eine der übrigen zwanzig
Größen (z.B. Taupunkt, Gewitterenergie, Nullgradgrenze), verschwindet sie
ersatzlos — ohne Fehlermeldung, ohne Zähler. Diese Spec bringt die
Kurznachrichten auf denselben Mechanismus, den der Trip-Kanal-Renderer dafür
bereits hat: Priorisieren und bei Platzmangel verschieben statt verwerfen.
#1399 (angeblich falsche Zeitzone im Telegram-Kurztext) wird dabei NICHT
gefixt, sondern nur mit einem Nachweis-Test versehen — der Fehler ist nach
Aktenlage bereits durch #1402 behoben, nur die Testabdeckung fehlt.

## Source

- **File:** `src/output/renderers/comparison.py` — `_CHANNEL_METRICS`,
  `_format_channel_metric`, `_channel_metric_cells`, `render_compare_telegram`,
  `_sms_location_part`, `render_compare_sms` (Zeilen 380–436, 439–536, 574–684)
- **File:** `src/output/renderers/channel_layout.py` — `render_for_channel`,
  `CHANNEL_LIMITS` (wiederverwendet, nicht verändert)
- **File:** `src/app/metric_catalog.py` — `get_sms_code`; zehn bisher fehlende
  `sms_code`-Einträge werden ergänzt (Scheibe S5b, s. Implementation Details
  Punkt 3) — das ist eine echte, wenn auch kleine Änderung an dieser Datei,
  kein reines "Wiederverwenden".
- **Schicht:** Python-Core (`src/output/renderers/`, `src/app/`) — kein
  Frontend-, Go- oder Persistenz-Anteil in dieser Spec.

## Estimated Scope

- **LoC:** ~305 (+250 / −50) über zwei Quelldateien plus Tests — **liegt über
  dem Workflow-Limit von 250.** Aufteilung siehe „Vorschlag Teilscheiben"
  unten.
- **Files:** 2 Quelldateien (`comparison.py`, `metric_catalog.py`) + 2–3
  Testdateien (Regressions-Update von `test_compare_mail_blocks.py`/
  `test_compare_metric_order.py`, neue Nachweis-Tests)
- **Effort:** medium-high (die eigentliche Teilungs-Konstruktion ist der
  aufwendige Teil, s. „Implementation Details — Die Naht")

### Vorschlag Teilscheiben (LoC-Limit)

- **S5a — Telegram (#1362, Telegram-Teil) + #1399-Nachweis:** volle
  Metrik-Auswahl im Telegram-Kurztext, Overflow-Zähler, Nachweis-Test für
  #1399. Deckt AC-1, AC-2, AC-4 (Telegram-Teil), AC-5 (Telegram-Teil), AC-6,
  AC-7 (Telegram-Teil) ab. ~150 LoC.
- **S5b — SMS (#1362, SMS-Teil) + Katalog-Ergänzung:** Kürzel-basierte
  SMS-Darstellung mit Zeichen-Budget-Kürzung statt fester
  Zwei-Metriken-Grenze, dazu die zehn fehlenden `sms_code`-Einträge in
  `metric_catalog.py`. Deckt AC-3, AC-4 (SMS-Teil), AC-5 (SMS-Teil), AC-7
  (SMS-Teil), AC-8 ab. ~155 LoC.

Begründung für den Schnitt an dieser Stelle (nicht anders): Telegram hat
großzügige Grenzen (4096 Zeichen, 7 Metrik-Zellen je Ort) und lässt sich mit
der bereits vorhandenen `_PLAIN_ROWS`-Formatierung fast reibungslos umbauen.
SMS hat die härtere Zeichengrenze (140) UND (bis S5b) fehlende Katalog-Kürzel
für einen Teil der 26 Größen — das ist die eigentliche Konstruktionsarbeit und
rechtfertigt eine eigene Scheibe mit eigenem Review.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `channel_layout.render_for_channel` / `CHANNEL_LIMITS` | upstream | liefert Priorisierung, Platz-Zuteilung und `demoted_count` — die geteilte Quelle, die diese Spec statt einer eigenen Sechserliste nutzt |
| `comparison._PLAIN_ROWS` / `_metric_value` | upstream (bereits Compare-intern) | liefert Label+Formatierung für alle 26 Größen — ersetzt die bisherige 6-Größen-if-Kette in `_format_channel_metric` |
| `metric_catalog.get_sms_code` / `metric_catalog.py`-Katalogeinträge | upstream, **von S5b erweitert** | liefert Kürzel für die SMS-Scheibe; zehn bisher fehlende Einträge werden in dieser Spec ergänzt (s. Implementation Details Punkt 3) — keine Ableitungsregel außerhalb des Katalogs |
| `app.models.MetricConfig` / `UnifiedWeatherDisplayConfig` | upstream | Zielform, die `render_for_channel` erwartet — wird aus der Compare-Auswahl synthetisch gebaut (s. „Die Naht") |
| `render_compare_telegram` / `render_compare_sms` | downstream | einzige Aufrufer der geänderten Bausteine |
| `test_compare_mail_blocks.py`, `test_compare_metric_order.py` | downstream | bestehende Tests, die auf die alte Sechserliste bzw. das alte Verhalten festgelegt sind — werden umgestellt (s. Known Limitations) |

## Implementation Details

### 1. Die Naht: wie die Compare-Auswahl in `render_for_channel()` ankommt

Das ist die eigentliche Konstruktionsfrage dieser Spec. Zwei Datenwelten
treffen aufeinander:

- **Trip-Welt:** `channel_layout.render_for_channel(channel, dc, report_type)`
  erwartet eine `UnifiedWeatherDisplayConfig` mit `dc.metrics: list[MetricConfig]`,
  wobei jede `MetricConfig` ein `bucket` (`"primary"`/`"secondary"`) und ein
  `order` (int) trägt. Die Funktion sortiert `primary` nach `order`, schneidet
  an der Kanalgrenze ab und schiebt den Rest nach `detail_metrics`
  (`demoted_count` = Zähler).
- **Compare-Welt:** `enabled_metrics: list[str] | None` ist eine flache,
  bereits nutzergeordnete Liste von Renderer-IDs (Listenposition =
  Reihenfolge, seit #1359) — kein `bucket`, kein `order`-Feld.

**Bridge-Funktion (neu, klein):** Aus der flachen Liste wird eine
`UnifiedWeatherDisplayConfig` MIT GENAU DER NUTZER-REIHENFOLGE gebaut — nicht
mit `channel_layout.auto_distribute()`, das die Reihenfolge nach
`METRIC_PRIORITY` NEU sortieren würde (und dessen Prioritätstabelle ohnehin
auf TRIP-Metrik-IDs schlüsselt, nicht auf Compare-Renderer-IDs — ein viertes,
inkompatibles Vokabular neben den bereits in `compare_metric_ids.py`
dokumentierten dreien):

```
metrics = [MetricConfig(metric_id=mid, bucket="primary", order=i)
           for i, mid in enumerate(enabled_metrics or _CHANNEL_METRICS_IDS)]
dc = UnifiedWeatherDisplayConfig(metrics=metrics)
layout = render_for_channel(channel, dc, report_type="evening")
```

Alle ausgewählten Größen werden als `"primary"` markiert — Compare kennt
(anders als der Trip-Editor) keine Nutzer-Unterscheidung zwischen
„eigene Spalte" und „Detail-Zeile"; jede gewählte Größe soll gleichwertig um
die verfügbaren Zellen konkurrieren, entschieden allein durch die vom Nutzer
gewählte Reihenfolge. `report_type="evening"` ist ein neutraler Fixwert ohne
Wirkung (Compare kennt kein Morgen/Abend-Override auf `MetricConfig`-Ebene).

`layout.table_columns` liefert die Metrik-IDs, die als Zelle erscheinen
(≤7 bei Telegram); `layout.demoted_count` die Zahl der verdrängten. Für den
tatsächlichen Zellenwert wird NICHT `_format_channel_metric`s alte
6-Größen-if-Kette verwendet, sondern `_metric_value(loc_result, metric_id)` +
das Label/die Formatierung aus `_PLAIN_ROWS` — beides bereits vorhandene,
für alle 26 Größen funktionierende Bausteine (identisch zur Klartext-Zeile
derselben Mail, keine zweite Werte-/Formatierungsquelle).

**Warum das eine echte Teilung ist, keine dritte Variante:** Die
Priorisierungs- und Abschneide-LOGIK (`render_for_channel`, `CHANNEL_LIMITS`)
ist zu 100% die des Trips — Compare übernimmt sie unverändert. Was neu
entsteht, ist ausschließlich der Adapter, der Compare-Vokabular in
Trip-Vokabular übersetzt (eine `MetricConfig`-Liste bauen) — das ist
dieselbe Art von Übersetzungsschicht, die `compare_metric_ids.py` bereits für
zwei andere Vokabular-Paare leistet (Frontend→Renderer,
Renderer→Trip-Zusammenfassungssatz). Kein neuer Prioritäts-Algorithmus, keine
neue Abschneide-Regel.

**Wo die Teilung an eine Grenze stößt (ehrlich benannt):** `METRIC_PRIORITY`
selbst (die Heuristik, WELCHE 5 Größen bei einer AUTOMATISCHEN Verteilung
"primary" werden) wird für Compare nicht gebraucht und nicht wiederverwendet
— Compare hat immer eine explizite Nutzerreihenfolge, nie eine automatische.
Das ist kein Bruch der Teilung, sondern zeigt nur, dass `auto_distribute()`
(die Heuristik-Hälfte von `channel_layout.py`) für Compare nicht die passende
Funktion ist — `render_for_channel()` (die Kanalgrenzen-Hälfte) hingegen
schon.

### 2. Telegram (S5a)

`render_compare_telegram` ruft je Ortsblock die Bridge auf (EINMAL für die
ganze Nachricht, nicht je Ort — die Auswahl ist ortsunabhängig) und ersetzt
`_channel_metric_cells`/`_format_channel_metric` durch
`layout.table_columns` + `_PLAIN_ROWS`-Lookup. `layout.demoted_count` wird in
die bestehende Kürzungs-Hinweis-Logik integriert: der vorhandene
`_telegram_notice(omitted_locations)` (Orts-Überlauf) bekommt einen
zusätzlichen Zweig für Metrik-Überlauf, z.B.
`"… +3 weitere Wettergrößen je Ort (Telegram-Limit) — vollständig per E-Mail"`
— beide Hinweise können nebeneinander stehen, wenn sowohl Orte als auch
Größen verdrängt wurden.

`layout.detail_metrics` (die verdrängten Größen selbst) bekommen in Compare
KEINE sichtbare Zeile — anders als beim Trip, wo die Bubble eine
Detail-Zeile kennt. Compare hat kein Äquivalent zu dieser Detail-Zeile (die
Blockstruktur ist "ein Ortsname + eine Zellenzeile", keine zweite Ebene) und
eine neue einzuführen würde Platz kosten, der für zusätzliche ORTE gebraucht
wird (das eigentliche Kernanliegen von #1269, bereits gelöst). Der Zähler
allein erfüllt „nichts verschwindet still" — s. AC-2.

### 3. SMS (S5b)

`_sms_location_part` ersetzt die feste `_SMS_METRICS_PER_LOCATION = 2` durch
eine Zeichen-Budget-Schleife nach demselben PRINZIP wie
`tokens/render.py:_truncate` (Größen einzeln, in aufsteigender
Nutzer-Prioritäts-Reihenfolge von hinten, aus der Zellenliste entfernen, bis
die Zeile passt — nie mitten in einem Kürzel/Wert schneiden). Eine 1:1-Nutzung
von `_truncate`/`Token`/`TokenLine` selbst ist NICHT vorgesehen: dieser
Baustein ist an die Trip-Stufenzeile (mehrere Tage, D/N/W/G/R/TH-Symbole)
gebunden und müsste für Compare (Orte statt Tage, andere Kürzel-Menge) neu
verdrahtet werden — das wäre mehr Umbau, als eine Wiederverwendung
rechtfertigt, und würde bei einer harten Trennung zwischen "Kürzungsprinzip"
(übernommen) und "Kürzungs-Maschinerie" (nicht übernommen) sauberer bleiben,
als eine Teilbenutzung der Token-DTOs für einen strukturell anderen
Anwendungsfall zu erzwingen. Übernommen wird stattdessen NUR: `get_sms_code()`
für die Kürzel selbst.

**Kürzel kommen AUSSCHLIESSLICH aus dem Katalog, keine Ableitung zur
Laufzeit** (PO-Korrektur 2026-07-29 — eine frühere Fassung dieser Spec sah
für Größen ohne Katalog-Kürzel ein zur Laufzeit aus dem `_PLAIN_ROWS`-Label
abgeleitetes Kurz-Label vor; das ist zurückgenommen, s. Changelog). Von den
26 Compare-Größen führen 15 bereits ein `sms_code`
(`D, N, HU, W, G, R, PR, TH, CP, SL, VS, UV, NL, SD, SN`). Die verbleibenden
zehn Katalog-Metriken bekommen in dieser Spec einen ECHTEN Katalog-Eintrag in
`src/app/metric_catalog.py`:

| Katalog-ID | neues `sms_code` | Herkunft |
|---|---|---|
| `wind_chill` | `TF` | identisch zum bestehenden `compact_label` dieser Metrik |
| `dewpoint` | `DP` | identisch zum bestehenden `compact_label` dieser Metrik |
| `wind_direction` | `WD` | identisch zum bestehenden `compact_label` dieser Metrik |
| `precip_type` | `PT` | identisch zum bestehenden `compact_label` dieser Metrik |
| `cloud_low` | `CL` | identisch zum bestehenden `compact_label` dieser Metrik |
| `cloud_mid` | `CM` | identisch zum bestehenden `compact_label` dieser Metrik |
| `cloud_high` | `CH` | identisch zum bestehenden `compact_label` dieser Metrik |
| `cloud_total` | `CT` | NEU — `cloud_total`s eigener `compact_label` ist nur `"C"` (zu generisch für ein SMS-Kürzel neben `CL`/`CM`/`CH`); `CL` selbst ist bereits an `cloud_low` vergeben, siehe Kollisionshinweis unten |
| `pressure` | `HP` | NEU (Hektopascal) — `pressure`s eigener `compact_label` ist `"P"`, das im SMS-Kontext zu dicht an `R`/`PR` (Niederschlag/Regenwahrscheinlichkeit) läge |
| `sunshine` | `SU` | NEU — `compact_label` ist das Emoji `☀`, laut Feldkommentar von `sms_code` ("GSM-7-tauglicher Token … ASCII") nicht direkt übernehmbar |

Sieben der zehn neuen Kürzel sind schlicht der bereits im Katalog vorhandene
`compact_label` derselben Metrik, jetzt zusätzlich im `sms_code`-Feld
eingetragen — keine neue Abkürzungsregel, nur ein bisher unbefüllter
Katalog-Eintrag. Drei (`cloud_total`, `pressure`, `sunshine`) sind neu
erfunden, weil ihr `compact_label` entweder bereits anderweitig vergeben ist
oder nicht ASCII-tauglich ist.

**Kollisionsprüfung:** gegen die 15 bestehenden `sms_code`-Werte und
untereinander sind alle 25 resultierenden Kürzel paarweise verschieden. Ein
Vorschlag aus der Analysephase (`cloud_total` → `CL`) wurde hier KORRIGIERT
zu `CT`, weil `CL` bereits `cloud_low`s eigener `compact_label` ist — hätte
`cloud_total` ebenfalls `CL` bekommen, wären zwei verschiedene Wettergrößen
im selben Katalog nicht mehr unterscheidbar gewesen (Verstoß gegen die vom
Feld selbst geforderte Kollisionsfreiheit, `metric_catalog.py:57`). Die
Trip-eigenen "Feels"-Tokensymbole `FN`/`FK`/`FD` (`tokens/builder.py:44,64`)
liegen in einem separaten Symbol-Vokabular (Tages-Trend-Zeile, nicht
`get_sms_code()`) und wurden für diese Prüfung bewusst nicht als Kollision
gewertet — sie gehören nicht zum `sms_code`-Namensraum, den das Katalogfeld
selbst als kollisionsfrei beansprucht.

Zellen verwenden also `get_sms_code(catalog_id)` statt der
Telegram-Vollform ("TF 12°C" statt "Gefühlte Temp. max 12°C"), für alle 26
Größen ohne Ausnahme.

Overflow wird — wie beim bestehenden Orts-Überlauf — als `+N` ausgewiesen,
hier je Ort für die nicht mehr passenden Metrik-Zellen (z.B.
`"Andermatt D 16°C W 15km/h +2"`), niemals durch stilles Weglassen.

## Expected Behavior

- **Input:** `enabled_metrics: list[str] | None` (Compare-Renderer-IDs, bis zu
  26 möglich, nutzergeordnet) je Telegram-/SMS-Renderaufruf
- **Output:** Telegram-Kurztext mit bis zu 7 Metrik-Zellen je Ort aus der
  vollen Auswahl (statt nur der alten Sechserliste) + Überlauf-Zähler;
  SMS-Zeile mit so vielen Zellen, wie ins 140-Zeichen-Budget passen, gekürzt
  in Kürzel-Einheiten
- **Side effects:** keine — reine Renderfunktionen, kein I/O, kein
  Persistenz-Zugriff

## Sichtbare Wirkung (bewusst, PO-informiert)

- Wählt ein Nutzer heute z.B. Taupunkt, Gewitterenergie oder Nullgradgrenze
  für den Ortsvergleich, tauchen diese Größen künftig auch in der
  Telegram-Nachricht und (kürzelgekürzt) in der SMS auf — bisher erschienen
  sie nur in der E-Mail.
- Reicht der Platz nicht für alle gewählten Größen, zeigt die Nachricht die
  wichtigsten (in der vom Nutzer eingestellten Reihenfolge) und nennt die
  Anzahl der übrigen — statt sie kommentarlos zu verschweigen.
- Eine Auswahl, die ausschließlich aus neuen (bisher nicht unterstützten)
  Größen besteht, zeigt jetzt tatsächlich Werte — heute zeigt sie
  fälschlich "keine Werte".
- Telegram-Labels wechseln für alle Größen auf dieselbe Beschriftung wie im
  Klartext-Teil derselben Mail (z.B. "Temp max" statt bisher "Temp") —
  Nebenfolge der Wiederverwendung von `_PLAIN_ROWS` statt einer eigenen
  Kurz-Label-Tabelle; für die bisherigen sechs Größen ändert sich dadurch die
  Beschriftung sichtbar (nicht der Wert).

## Acceptance Criteria

- **AC-1 (neue Größe erscheint im Telegram):** Given eine ausgewählte
  Wettergröße außerhalb der heutigen Sechserliste (z.B. Taupunkt) / When der
  Telegram-Kurztext für einen Ort gerendert wird / Then erscheint diese
  Größe mit Bezeichnung und Wert im Text — heute verschwindet sie
  ersatzlos.
  - Test: `render_compare_telegram(result, enabled_metrics=["dewpoint_avg"])`
    enthält "Taupunkt" und den formatierten Wert im gerenderten Text.

- **AC-2 (Überlauf wird gezählt, nicht verschwiegen):** Given mehr
  ausgewählte Größen, als Telegram-Zellen Platz haben (z.B. 10 gewählte
  Größen bei 7 Zellen je Ort) / When der Telegram-Kurztext gerendert wird /
  Then erscheinen die 7 wichtigsten in der Nutzer-Reihenfolge als Zellen,
  UND ein sichtbarer Hinweis nennt die Zahl der übrigen — heute verschwinden
  überzählige Größen kommentarlos.
  - Test: `enabled_metrics` mit 10 Renderer-IDs → genau 7 Zellen im
    Ortsblock, Text enthält einen Hinweis mit der Zahl "3".

- **AC-3 (SMS bleibt im Budget, kürzt nie mittendrin):** Given eine
  Metrik-Auswahl, die mehr Größen enthält, als ins 140-Zeichen-Budget einer
  SMS passen / When die SMS gerendert wird / Then bleibt die Nachricht unter
  140 Zeichen und lässt ganze Größen entfallen statt ein Kürzel oder einen
  Wert mittendrin abzuschneiden.
  - Test: `render_compare_sms` mit einer großen `enabled_metrics`-Liste;
    `len(sms) <= 140`; kein abgeschnittenes Teil-Kürzel am Zeilenende
    (Regex-Prüfung auf vollständige "Kürzel Wert"-Paare).

- **AC-4 (Nutzer-Reihenfolge wirkt weiterhin):** Given zwei Metrik-Auswahlen
  mit denselben Größen in umgekehrter Reihenfolge / When Telegram bzw. SMS
  gerendert werden / Then unterscheidet sich die Zellfolge entsprechend der
  jeweils eingestellten Reihenfolge.
  - Test: zwei `enabled_metrics`-Listen (Reihenfolge A/B, inkl. mindestens
    einer Größe außerhalb der alten Sechserliste) → die resultierenden
    Zellfolgen in Telegram UND SMS unterscheiden sich und entsprechen
    jeweils der eingegebenen Reihenfolge.

- **AC-5 (keine leere Nachricht bei reiner Nicht-Sechser-Auswahl):** Given
  eine Auswahl ausschließlich aus Größen außerhalb der heutigen
  Sechserliste (z.B. nur Taupunkt und Luftdruck) / When Telegram und SMS
  gerendert werden / Then zeigen beide die gewählten Werte — heute liefert
  die Schnittmenge mit der Sechserliste nichts, und der Ortsblock zeigt
  fälschlich "keine Werte".
  - Test: `enabled_metrics=["dewpoint_avg", "pressure_avg"]` →
    `render_compare_telegram`/`render_compare_sms` enthalten NICHT die
    Zeichenkette "keine Werte" und zeigen stattdessen die beiden Werte.

- **AC-6 (Nachweis #1399 — Telegram rechnet in Ortszeit):** Given ein Ort
  ohne gespeichertes Zeitzonenfeld (nur Koordinaten, z.B. in einer von UTC
  abweichenden Zone) mit einer amtlichen Warnung oder einem Ausblick-Wert,
  der eine Uhrzeit zeigt / When der Telegram-Kurztext für diesen Ort
  gerendert wird / Then zeigt die Uhrzeit die ORTSZEIT (über
  `resolve_location_tz`/Koordinaten-Fallback), nicht die Weltzeit. Dies ist
  ein NACHWEIS-Test (kein Bugfix): Bleibt er grün, gilt #1399 als bereits
  durch #1402 behoben und wird mit diesem Test geschlossen. Wird er rot,
  eskaliert das Ergebnis an den Product Owner statt eines stillschweigenden
  Fixes.
  - Test: `SavedLocation` ohne `timezone`-Feld, Koordinaten in einer Zone mit
    Offset ≠ 0 zur Servertestzeit (analog `test_compare_local_time_basis.py`,
    aber für `render_compare_telegram` statt nur `render_compare_email`/
    `render_compare_sms`) — die angezeigte Stunde entspricht der
    Koordinaten-Ortszeit, nicht UTC.

- **AC-7 (Regressionsschutz — die heutigen sechs Größen unverändert):**
  Given eine Auswahl, die exakt die heutigen sechs Größen enthält (Temp max,
  Wind, Sonne, Wolken, Schneehöhe, Neuschnee) in ihrer bisherigen Reihenfolge
  / When Telegram und SMS gerendert werden / Then sind die dargestellten
  WERTE unverändert gegenüber dem heutigen Verhalten (die Beschriftung darf
  sich ändern, s. „Sichtbare Wirkung" — die Zahlen und ihre Zuordnung zu den
  richtigen Orten nicht).
  - Test: bestehende Fixtures aus `test_compare_mail_blocks.py`/
    `test_compare_metric_order.py` mit genau diesen 6 IDs, Wert-für-Wert-
    Vergleich (nicht String-Gleichheit der ganzen Nachricht, da sich Labels
    ändern dürfen).

- **AC-8 (SMS-Kürzel kommen ausschließlich aus dem Katalog):** Given jede der
  26 Compare-Größen, die grundsätzlich in der SMS erscheinen kann / When ihr
  Kürzel über `get_sms_code()` auf die zugrundeliegende Katalog-Metrik
  abgefragt wird / Then liefert JEDE Größe ein nicht-leeres Kürzel — keine
  Größe erzeugt ihr Kürzel aus einer zur Laufzeit abgeleiteten Bezeichnung
  (z.B. den ersten Buchstaben ihres Labels).
  - Test: Schleife über alle 26 Compare-Renderer-IDs (bzw. deren
    zugrundeliegende Katalog-Metrik-ID), `get_sms_code(catalog_id) != ""`
    für jede einzelne — schlägt fehl, sobald eine Größe ohne Katalog-Kürzel
    eingeführt oder eine bestehende versehentlich entfernt wird.

## Known Limitations

- **`tests/unit/test_compare_mail_blocks.py:343-379`
  (`test_telegram_and_sms_output_unchanged_by_summary_block_removal`) schreibt
  das heutige Fehlverhalten als Sollwert fest.** Er erwartet wörtlich
  `"Andermatt\n   Temp 16°C"` für eine Auswahl aus `temp_max_c` UND
  `precip_sum_mm` — `precip_sum` fehlt in der Erwartung, weil es 2026-07-08
  (vor dieser Spec) noch nicht in `_CHANNEL_METRICS` stand. Diese Spec macht
  genau das zum Fehler: `precip_sum` MUSS künftig erscheinen. Der Test wird
  umgestellt auf einen Wert-für-Wert-Vergleich, der beide Größen erwartet
  (analog AC-7), statt der harten String-Gleichheit gegen die alte,
  unvollständige Ausgabe. Sein Nachfolger sichert weiterhin ab, dass
  Telegram/SMS eigenständig rendern (kein Aufruf von
  `render_comparison_text`) — nur der ERWARTETE INHALT ändert sich.
- **`tests/unit/test_compare_metric_order.py:229-296`** benennt
  `_CHANNEL_METRICS` ausdrücklich als heutige Quelle der Telegram-/
  SMS-Metrikmenge (Docstrings der Testklassen). Nach dieser Umstellung ist
  `_CHANNEL_METRICS` kein Filter mehr, sondern höchstens noch der
  Altbestands-Fallback bei `enabled_metrics=None` — Docstrings und
  Fixtures dieser Datei werden entsprechend nachgezogen, die Kern-Aussage
  (Reihenfolge wirkt in Telegram und SMS) bleibt unverändert gültig und wird
  von AC-4 weiter abgesichert.
- **Korrektur einer Annahme aus der Analysephase:**
  `CompareRenderOptions.enabled_metrics` (`report_config_resolver.py:177`)
  ist zum Zeitpunkt dieser Spec bereits `Optional[list[str]]`, NICHT mehr
  `Optional[set]` — der Kommentar dort verweist ausdrücklich auf #1359 und
  begründet die Listenform mit genau der Reihenfolge-Erhaltung, die diese
  Spec ebenfalls braucht. Es ist an dieser Stelle also KEINE eigene Änderung
  nötig; die Ordnung kommt bereits geordnet an. Wo Ordnung tatsächlich neu
  entsteht (und erhalten werden muss), ist die in „Implementation Details —
  Die Naht" beschriebene Bridge-Funktion, die aus dieser Liste eine
  `MetricConfig`-Liste baut.
- **`layout.detail_metrics` bleibt in Compare ohne sichtbare Zeile.** Anders
  als beim Trip-Telegram (das eine Detail-Zeile in der Bubble kennt) hat
  Compare keine zweite Anzeigeebene je Ortsblock. Nur der Zähler
  (`demoted_count`) wird sichtbar gemacht (s. Implementation Details Punkt 2).
  Eine Detail-Zeile einzuführen war nicht beauftragt und würde Platz kosten,
  der für zusätzliche ORTE gebraucht wird (Kernanliegen des bestehenden
  Orts-Überlaufs, #1269).
- **`tokens/render.py:_truncate` wird nach PRINZIP übernommen, nicht als
  Funktion aufgerufen.** Eine echte Wiederverwendung der `Token`/
  `TokenLine`-DTOs hätte bedeutet, für Compare (Orte statt Trip-Tage) eine
  eigene Token-Konstruktion aufzubauen — mehr neue Maschinerie, als die
  Wiederverwendung rechtfertigt. Übernommen wird das Kürzungsprinzip
  (ganze Einheiten von hinten entfernen, bis das Budget passt) sowie
  `get_sms_code()` für die Kürzel selbst.
- **`METRIC_PRIORITY`/`auto_distribute()` (`channel_layout.py:29-36,84-109`)
  werden NICHT wiederverwendet.** Sie schlüsseln auf Trip-Metrik-IDs
  (ein zu den Compare-Renderer-IDs inkompatibles Vokabular, s.
  `compare_metric_ids.py`-Kopfkommentar „Vier inkompatible
  Metrik-Vokabulare") und dienen der AUTOMATISCHEN Verteilung ohne
  Nutzerauswahl — Compare hat immer eine explizite, geordnete Auswahl.
  Wiederverwendet wird ausschließlich `render_for_channel()`/
  `CHANNEL_LIMITS` (die Kanalgrenzen-Hälfte von `channel_layout.py`).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Die Grundsatzentscheidung „Trip und Compare teilen
  Bausteine, kein Neubau" ist bereits in CLAUDE.md (Abschnitt
  „Trip/Ortsvergleich-Code-Teilung") verankert. Diese Spec wendet sie auf
  einen konkreten, bisher nicht geteilten Baustein an — sie weicht davon
  nicht ab, sondern führt sie aus.

## Changelog

- 2026-07-29: Initial spec created (#1362 + #1399, Scheibe S5 aus Epic #1372)
- 2026-07-29: PO-Korrektur — die ursprünglich vorgesehene, zur Laufzeit aus
  `_PLAIN_ROWS`-Labels abgeleitete Kurz-Label-Notlösung für Größen ohne
  Katalog-`sms_code` wurde zurückgenommen (wäre ein fünftes Vokabular
  gewesen). Stattdessen bekommen die zehn fehlenden Katalog-Metriken einen
  echten `sms_code`-Eintrag in `metric_catalog.py` (S5b-Umfang erweitert,
  neuer AC-8). Dabei wurde die ursprünglich vorgeschlagene Zuordnung
  `cloud_total → CL` als Kollision mit dem bestehenden `compact_label` von
  `cloud_low` erkannt und auf `CT` korrigiert; zusätzlich zu den in der
  Analysephase genannten sechs Größen wurden `wind_chill`, `cloud_low`,
  `cloud_mid` und `cloud_high` als ebenfalls ohne `sms_code` identifiziert
  und in die Katalog-Ergänzung aufgenommen.
