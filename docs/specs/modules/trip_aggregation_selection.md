---
entity_id: trip_aggregation_selection
type: feature
created: 2026-07-28
updated: 2026-07-28
status: draft
version: "1.1"
tags: [renderer, email-pillen, metric-catalog, trip-editor, epic-1372, issue-1357]
---

<!-- Issue #1357 — Epic #1372 Scheibe S4a, Dach #1374 -->

# Trip-Auswertungswahl: Höchst-/Tiefstwert je Wettergröße in der Mail-Kachelzeile (Issue #1357)

## Approval

- [ ] Approved

## Purpose

Der Nutzer kann im Trip-Editor je Wettergröße einschränken, welche
Tagesauswertung (Höchst-, Tiefst- oder Mittelwert) in der
E-Mail-Kachelzeile („Metriken-Überblick") erscheint. Anlass: die gefühlte
Höchsttemperatur ist heute im Trip-Briefing nicht darstellbar — obwohl sie
**bereits korrekt berechnet wird** (`wind_chill_max_c`, identischer
Rechenweg wie die gemessene Temperatur, s. „Verifizierte Fakten" unten),
zeigt der Renderer sie nie an. Betroffen sind genau zwei Größen —
Temperatur und gefühlte Temperatur —, die einzigen im Katalog mit mehr als
einer tatsächlich berechenbaren Auswertung.

**Korrigierte Fassung (2026-07-28, nach PO-Klärung):** Die erste Fassung
dieser Spec unterstellte fälschlich Unterschiede im Rechenweg zwischen
Temperatur und gefühlter Temperatur sowie einen Migrationsbedarf am
Datenbestand. Beides ist widerlegt (s. u.). Diese Fassung beschränkt sich
zudem bewusst auf die Mail-Kachelzeile; die Ausweitung auf die Kurzformen
(SMS, E-Mail-Kurzzusammenfassung, Telegram) wird als eigene, zweite Scheibe
vorgeschlagen und dem PO zur Entscheidung vorgelegt (s. „Reichweite und
Schnittempfehlung").

### Verifizierte Fakten (Code-Beleg, ersetzt Annahmen der Erstfassung)

1. **Der Rechenweg ist bereits korrekt und identisch für beide Größen —
   kein Eingriff nötig.** `services/segment_weather.py:254-281`
   (`_aggregate_for_segment`) filtert die Zeitreihe je Segment strikt auf
   `start_floor <= dp.ts < end_floor` (Segment-Start bis -Ende, ortsgenau
   und zeitgenau) und berechnet **danach** `compute_basis_metrics()` +
   `compute_extended_metrics()` auf genau dieser gefilterten Zeitreihe.
   `temp_min_c`/`temp_max_c` UND `wind_chill_min_c`/`wind_chill_max_c`
   entstehen aus **demselben** gefilterten `filtered_ts` — kein
   Tagesmaximum, kein fremder Zeitraum. Die PO-Vorgabe „exakt so berechnet
   wie die normale Temperatur" ist damit für die **Berechnung** bereits
   erfüllt; die Lücke liegt ausschließlich in der **Darstellung**
   (`email/helpers.py:1233-1252` zeigt nur `wind_chill_min_c`, obwohl
   `wind_chill_max_c` im selben `SegmentWeatherSummary` bereitsteht).
2. **Temperatur und Regen/Gewitter/Wind unterscheiden sich im Zeitfenster
   — bewusst, nicht als Altlast.** PO-bestätigtes Modell: Temperatur
   (gemessen wie gefühlt) zählt nur, was der Wanderer **unterwegs**
   erlebt (`_collect_hiking_window_dps()`, Gehzeit); Regen/Gewitter/Wind
   zählen zusätzlich die Stunden **nach der Ankunft** bis 19 Uhr
   (`build_day_window_points()`, damit der Wanderer weiß, ob er sich
   beeilen muss). Diese Spec fasst **keine** dieser Fensterfunktionen an —
   weder `_collect_hiking_window_dps`, noch `build_day_window_points`,
   noch `night_temp_min_c()` (Nacht-Tiefsttemperatur, eigene Spec
   `night_temp_evening_only.md`, unberührt).
3. **Kein Migrationsbedarf.** `MetricConfig.aggregations` (`models.py:528`)
   bleibt `list[str]` mit Schreib-Default `["min", "max"]` — unverändert.
   Die tragende Einstellung ist **nicht** dieses Feld, sondern
   `MetricConfig.enabled` (bereits vorhanden): ist eine Größe nicht
   aktiviert, erscheint sie nicht — PO wörtlich: *„Wenn es Nutzer nichts
   einstellt wird nichts angezeigt. Das ist ein Profi-Tool."* Ist sie
   aktiviert, erscheint sie mit dem Katalog-Vorgabewert
   (Minimum+Maximum — für beide betroffenen Größen identisch, s.
   Implementation Details), bis der Nutzer die Auswahl aktiv einschränkt.
   Weil der Schreib-Default `["min", "max"]` für **beide** Größen bereits
   dem neuen Zielverhalten entspricht, ist kein Bestandsdatensatz
   „falsch" — nichts muss bereinigt werden.
4. **Die gefühlte Temperatur fehlt heute in Kurzformen (SMS,
   Kurzzusammenfassung, Telegram) VOLLSTÄNDIG, nicht nur asymmetrisch.**
   Das Token-Paar `N`/`D` (Tages-Tiefst/-Höchsttemperatur) bezieht sich
   ausschließlich auf die gemessene Temperatur. Ein `WC`-Token existiert
   im Katalog (`tokens/builder.py:174-196`, `_wintersport()`), wird aber
   **nur** ausgelöst, wenn `build_token_line(..., profile="wintersport")`
   aufgerufen wird — und das geschieht im gesamten Produktionscode
   **ausschließlich** in `src/app/cli.py:233` (Legacy-CLI, laut CLAUDE.md
   „Debug-Werkzeug, nicht der Produktivpfad"). Der produktive
   Trip-SMS-Pfad (`sms_trip.py::format_sms()` → `build_token_line()`)
   übergibt **kein** `profile`-Argument, läuft also immer mit dem Default
   `"standard"` — `_wintersport()`/`WC` wird nie erreicht.
   `sms_trip.py::_segments_to_normalized_forecast()` (Zeile 219, `today =
   DailyForecast(...)`) setzt `wind_chill_c` gar nicht erst.
   `compact_summary.py` und `narrow.py` (Telegram) enthalten **keine**
   einzige Erwähnung von `wind_chill`/„gefühlt". Die gefühlte Temperatur
   ist in den drei Kurzformen also nicht „nur als Einzelwert" sichtbar,
   sondern **vollständig unsichtbar** — obwohl `docs/reference/sms_format.md:269`
   sie als vom `trip.profile`-Feld gesteuertes Kontraktverhalten
   dokumentiert. Diese Lücke besteht unabhängig von #1357 bereits heute
   und ist nicht Gegenstand dieser Spec (s. „Reichweite und
   Schnittempfehlung").

## Source

> **Schicht-Hinweis:** Diese Spec berührt zwei Schichten — Python-Core
> (`src/app/`, `src/output/renderers/`) für Katalog und Renderer, sowie
> Frontend (`frontend/src/lib/`) für die Auswahlfläche im Trip-Editor.
> Kein Go-Eingriff (`display_config` bleibt opake Map,
> `internal/model/trip.go:108`).

- **File:** `src/services/segment_weather.py:226-289`
  (`_aggregate_for_segment`) — Beleg für identischen Rechenweg
  Temperatur/gefühlte Temperatur (Punkt 1 oben)
- **File:** `src/app/metric_catalog.py` — `MetricDefinition.summary_fields`
  (Quelle der anzeigbaren Auswertungen), neue Funktionen
  `summary_field_for()`/`available_aggregations()`/`aggregation_label_de()`/
  `pill_default_aggregations()`
- **File:** `src/output/renderers/email/helpers.py:1198-1252`
  (`_pill_for_metric`, Temperatur- und Wind-Chill-Zweig inkl. des
  #1351-F001-Sperrkommentars), `:1503-1556` (`build_metrics_summary_pills`)
- **File:** `src/output/renderers/email/html.py:1163-1179`,
  `email/plain.py:155-170`, `email/compact.py:146-155` — drei identische
  `_pill_metric_ids`-Aufbaustellen
- **File:** `src/output/renderers/compare_outlook_metric_ids.py:34-47`
  (`_summary_field()` — wird auf die gehobene Katalog-Funktion umgestellt)
- **File:** `frontend/src/lib/types.ts:178-194` (`WeatherConfigMetric` —
  fehlendes Feld `aggregations`, sonst Verlust beim Speicher-Roundtrip)
- **File:** `frontend/src/lib/components/shared/WeatherMetricsTab.svelte`
  (`context='route'`), neue kleine Zeilen-Komponente unter
  `weather-metrics-tab/` (Vorbild: `ThresholdMetricRow.svelte`, dieselbe
  Card-Sektions-Machart wie „04 — Schwellwerte")
- **File (nur Kontext, NICHT Teil dieser Lieferung):**
  `src/output/tokens/dto.py:36` (`DailyForecast.wind_chill_c`),
  `src/output/tokens/builder.py:174-196,263-264` (`_wintersport()`,
  Profile-Gate), `src/app/cli.py:233` (einziger Aufrufer mit
  `profile="wintersport"`), `docs/reference/sms_format.md:45,57,267-269,326,378,414`
  (WC-Kontrakt) — Beleg für Punkt 4 oben, relevant für die vorgeschlagene
  zweite Scheibe

## Reichweite und Schnittempfehlung (Tech-Lead-Vorschlag, PO entscheidet)

**Diese Spec deckt ausschließlich die E-Mail-Kachelzeile ab** (Scheibe 1).
Die Ausweitung auf Kurzformen (Scheibe 2) wird hier nur skizziert und
**nicht** durch Acceptance Criteria dieser Spec abgedeckt.

**Warum Scheibe 2 keine einfache Symmetrie-Korrektur ist:** Die
Verifikation (Punkt 4 oben) zeigt, dass die gefühlte Temperatur in
Kurzformen heute nicht „ungleich, aber vorhanden" ist, sondern **komplett
fehlt** und der bestehende `WC`-Mechanismus in Produktion nie erreicht
wird. Sie in die Kurzformen einzuführen heißt daher: neue Felder auf
`DailyForecast` (`wind_chill_min_c`/`wind_chill_max_c` statt des
ungenutzten `wind_chill_c`), neue Aggregation in
`sms_trip.py::_segments_to_normalized_forecast()` analog zu
`temps_min`/`temps_max` — inklusive der offenen Designfrage, ob die
Abend-Nacht-Anpassung (`night_temp_min_c()`, Scheibe D von #1319) auch für
die gefühlte Temperatur gelten soll, was direkt das Gebiet von
`night_temp_evening_only.md` berührt und dort eine eigene Klärung
bräuchte, statt „automatisch mitzulaufen". Dazu: neues Token-Paar (statt
des heute kontraktierten, aber unerreichbaren `WC`) oder Reaktivierung des
`trip.profile`-Gates in `builder.py`, Vertragsänderung
`docs/reference/sms_format.md`, Erweiterung `compact_summary.py`
(Kurzzusammenfassungssatz) und `narrow.py` (Telegram), SMS-Zeichenhaushalt
(GSM-7, #624) für ein zusätzliches Token.

**Empfehlung:** Scheibe 1 (Kachelzeile) jetzt ausliefern — geschätzt ~185
LoC, klar begrenzter, bereits vollständig verifizierter Umfang. Scheibe 2
(Kurzformen) als eigene Lieferung mit eigener Analyse-Phase, geschätzt
~180-220 LoC zusätzlich (grobe Schätzung, nicht code-verifiziert wie
Scheibe 1) — insbesondere die Nacht-Anpassungsfrage braucht eine eigene
Klärung, keine Nebenentscheidung in dieser Spec. **Bis Scheibe 2 umgesetzt
ist, bleibt die gefühlte Temperatur in SMS/Kurzzusammenfassung/Telegram
weiterhin vollständig unsichtbar** — unverändert zum heutigen Zustand,
kein Rückschritt, aber auch keine Gleichstellung in diesen Kanälen.

Nebenbefund (nicht Teil dieser Spec, gehört nach #1199-Triage): das
`WC`-Token ist laut `sms_format.md` vertraglich an `trip.profile ==
"wintersport"` gebunden, dieses Gate ist im produktiven SMS-Pfad aber nie
verdrahtet — der Kontrakt ist seit Einführung nie einlösbar gewesen.

## Estimated Scope

- **LoC:** tatsächlich rund 440 Produktivcode für Scheibe 1 (Kachelzeile) —
  deutlich über der ursprünglichen Schätzung von ~185. **PO-Freigabe der
  Grenze auf 450 am 2026-07-28.** Grund der Abweichung: die Erstschätzung
  hatte nur den Renderer- und Katalog-Anteil im Blick, nicht den Aufwand
  der Bedienoberfläche selbst — Zustand laden (`effectiveAggregations()`),
  Änderungen erkennen (Dirty-Check-Erweiterung), Verwerfen/Speichern-
  Roundtrip (`buildWeatherConfigMetrics`) sowie, nach dem F001-Fix (Runde
  3 des Adversary-Dialogs), die Umstellung von Mehrfachauswahl auf
  Einzelwahl samt Guard-Logik in beiden Schichten. Tests zusätzlich,
  zählen nach Projektkonvention nicht gegen die Kern-Grenze.
- **Files:** 6 Produktivdateien Python (`metric_catalog.py`,
  `email/helpers.py`, `email/html.py`, `email/plain.py`, `email/compact.py`,
  `compare_outlook_metric_ids.py`) + 2 Frontend-Dateien (`types.ts`,
  `WeatherMetricsTab.svelte` + neue Zeilen-Komponente) + zugehörige
  Testdateien. **Kein** Migrationsskript, **keine** Modell-/Loader-Änderung.
- **Effort:** medium (Mail-Renderer + geteilte Frontend-Oberfläche, zwei
  Schichten synchron; kein Persistenz-Schema-Eingriff mehr).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/metric_catalog.py` (`summary_fields`) | module | Quelle der pro Größe tatsächlich anzeigbaren Auswertungen — NICHT `default_aggregations` (verspricht bei `snowfall_limit`/`freezing_level` mehr, als berechenbar ist) |
| `src/services/segment_weather.py::_aggregate_for_segment()` | function (unberührt, Beleg) | Zeigt, dass `temp_*` und `wind_chill_*` bereits aus derselben gefilterten Zeitreihe stammen — keine Änderung nötig, nur Referenz für „gleicher Rechenweg" |
| `src/output/renderers/compare_outlook_metric_ids.py::_summary_field()` | function | Wird zur geteilten Naht: Body delegiert an die gehobene `metric_catalog.summary_field_for()` statt eigener Kopie |
| `docs/specs/modules/night_temp_evening_only.md` | Spec (unberührt) | Bedeutung von `N` (Nacht-Tiefsttemperatur am Ziel) und `night_temp_min_c()` bleiben exakt wie dort definiert — keine Berührung durch Scheibe 1; für eine künftige Scheibe 2 (Kurzformen) wäre eine eigene Klärung nötig, ob dieselbe Anpassung auch für die gefühlte Temperatur gilt |
| `docs/specs/modules/sms_daywindow_aggregation.md` | Spec (unberührt) | Tagesfenster-Regelung (04–19 Uhr, Gehzeit-Fensterung) für die SMS-Wert-Token — betrifft `R`/`PR`/`W`/`G`/`TH:`, nicht die Kachelzeilen-Temperatur; unberührt |
| `tests/tdd/test_issue_912_pill_textformat.py` | Test (Bestand) | `TestAC2WindChill` (insbesondere `test_wind_chill_format_exact`) muss **bewusst angepasst** werden — die gefühlte Temperatur zeigt künftig standardmäßig die Spanne, nicht mehr nur den Tiefstwert (gewollte Verhaltensänderung, kein Regressionsbruch) |
| `internal/handler/config_merge.go::mergeConfigMap` | function (unberührt, Falle) | Ersetzt Top-Level-Schlüssel komplett — betrifft `aggregations` nicht direkt (liegt innerhalb eines Metrik-Eintrags), aber `frontend/src/lib/types.ts` muss das Feld kennen, sonst geht eine Nutzer-Einschränkung beim nächsten Speichern über die Oberfläche verloren |
| `renderer_mail_gate.py` (#811, Commit-Gate) | Tooling | `email/helpers.py`, `email/html.py`, `email/plain.py`, `email/compact.py` sind Mail-Inhalts-Dateien → vor Commit `tests/tdd/test_issue_811_mode_matrix.py` grün **und** frischer `briefing_mail_validator.py`-Lauf gegen eine echt zugestellte Staging-Mail nötig |
| `src/output/renderers/compare_outlook_metric_ids.py::resolve_outlook_metrics()` | Referenzmuster | „leer heißt leer" + unauflösbare Einträge werden verworfen und per `logger.warning` sichtbar gemacht statt still geschluckt — Vorbild für den Guard aus AC-7 |

## Implementation Details

### 1. Katalog-Erweiterung — geteilte Naht statt zwei Kopien

`metric_catalog.py` bekommt vier kleine Funktionen auf Basis der bereits
vorhandenen `summary_fields`:

- `summary_field_for(metric_id, aggregation) -> Optional[str]` — Feldname
  auf `SegmentWeatherSummary` (oder `None`). `compare_outlook_metric_ids.py::_summary_field()`
  wird danach ein reiner Delegat (aktuell zwei fast identische
  Implementierungen — Duplikat entfällt).
- `available_aggregations(metric_id) -> list[str]` — anzeigbare
  Auswertungs-IDs in fester Reihenfolge (`min`, `max`, `avg`, `sum`,
  gefiltert auf `summary_fields.keys()`). Für `temperature`: `["min",
  "max", "avg"]`; für `wind_chill`: `["min", "max"]`; für alle übrigen 22
  Größen eine Einerliste.
- `pill_default_aggregations(metric_id) -> list[str]` — die Teilmenge, die
  ohne aktive Nutzereinschränkung erscheint: `{"min", "max"} ∩
  available_aggregations(metric_id)`, falls nicht leer, sonst alle
  angebotenen. Für Temperatur ergibt das `["min", "max"]` (bitgleich zum
  heutigen Verhalten — `avg` bleibt wählbar, ist aber nie Vorgabe). Für
  die gefühlte Temperatur ergibt das **ebenfalls** `["min", "max"]` —
  **das ist die gewollte Verhaltensänderung**: die gefühlte Temperatur
  zeigt künftig ohne jede Nutzeraktion die Spanne, weil dieselbe Regel
  wie bei der gemessenen Temperatur angewendet wird (kein Sonderfall, s.
  PO-Zitat in Purpose). Diese Ableitungsregel ist eine eigene technische
  Entscheidung dieser Spec (nicht wörtlich vom PO vorgegeben) — sie folgt
  aus „dieselben Auswertungen wie der Katalog bisher für die Kachel
  gezeigt hat" und vermeidet, dass Temperatur plötzlich auch `avg` zeigen
  müsste, was niemand verlangt hat.
- `aggregation_label_de(aggregation) -> str` — deutsches Label
  (Minimum/Maximum/Mittel/Summe). Bereits als `_AGGREGATION_LABELS` in
  `compare_metric_catalog.py:50` vorhanden; wird dorthin gehoben und von
  beiden Seiten importiert (eine Quelle für die Beschriftung, kein
  Compare→Trip- oder Trip→Compare-Rückverweis).

### 2. Persistenz — unverändert, kein Migrationsbedarf

`MetricConfig.aggregations` bleibt `list[str] = field(default_factory=
lambda: ["min", "max"])`, **keine Typänderung**. Der Renderer liest das
Feld künftig zum ersten Mal (bisher 0 Leser); solange der Nutzer nichts
einschränkt, steht dort für jeden Trip bereits `["min", "max"]` — für
beide betroffenen Größen exakt der neue Vorgabewert (Punkt 3 der
verifizierten Fakten). Schränkt der Nutzer aktiv ein (`["max"]`, `["min"]`,
`["min", "max", "avg"]` bei Temperatur, oder bewusst `[]`), wird genau das
gespeichert und gelesen — der bestehende Read-Modify-Write-Pfad in
`loader.py` braucht dafür keine Änderung.

### 3. Renderer — ein geteilter Auswahl- und Darstellungsweg für beide Größen

`build_metrics_summary_pills()` bekommt einen neuen, additiven
Schlüsselwortparameter `metric_aggregations: Optional[dict[str, list[str]]]
= None` (Metrik-ID → gespeicherte `aggregations`-Liste). Die drei
Aufbaustellen (`html.py:1163`, `plain.py:155`, `compact.py:146`) füllen
ihn zusätzlich zur bestehenden `_pill_metric_ids`-Liste:
`{mc.metric_id: mc.aggregations for mc in dc.metrics if mc.enabled}`.

`_pill_for_metric()` bekommt denselben Parameter durchgereicht
(`chosen_aggregations: Optional[list[str]] = None`, extrahiert aus
`metric_aggregations.get(metric_id)`). Die Temperatur- und
Wind-Chill-Zweige (`helpers.py:1218-1251`) werden auf **eine** gemeinsame
kleine Hilfsfunktion umgestellt, die aus einer Auswertungsmenge (Teilmenge
von `{min, max}`, für Temperatur zusätzlich `avg`) und den zugehörigen
Werten den Pill-Text baut:

- Fehlt `chosen_aggregations` (Aufrufer ohne den neuen Parameter, z. B.
  bestehende Direktaufrufe in Tests) ⇒ Rückfall auf
  `pill_default_aggregations(metric_id)`.
- Enthält die Menge sowohl `min` als auch `max` ⇒ Spannen-Form (Vorbild:
  die heutige Temperatur-Pille „X–Y°C · Max HH:00").
- Enthält sie nur `min` ODER nur `max` ⇒ Ein-Wert-Form (Vorbild: die
  heutige gefühlte-Temperatur-Pille „gef. min X.X°C · HH:00").
- Enthält sie `avg` (nur Temperatur, wenn Nutzer das aktiv wählt) ⇒
  Einzelwert-Form ohne Uhrzeitanker (Mittelwert ist kein
  Zeitpunkt-Ereignis) — exakte Textform ist TDD/Implement-Detail.
- Leere Menge ⇒ Pill entfällt (Rückgabe `None`).

Beide Metriken laufen durch **dieselbe** Fallunterscheidung, unterscheiden
sich nur in Label-Präfix („gef." vs. kein Präfix) und Nachkommastellen
(analog zu den bisherigen, je Metrik unterschiedlichen Formaten — das
betrifft nur die Zahlendarstellung, nicht den Auswahl-/Rechenweg). Damit
ist die PO-Vorgabe „derselbe Algorithmus, nur für andere Werte" für die
**Darstellung** eingelöst, wie sie es für die **Berechnung** bereits ist.

### 4. Frontend — Auswahlfläche nur an den zwei betroffenen Zeilen

Neue kleine Zeilen-Komponente (`AggregationMetricRow.svelte`) unter
`frontend/src/lib/components/shared/weather-metrics-tab/` (Vorbild:
`ThresholdMetricRow.svelte` — dieselbe Card-Sektions-Machart wie die
bestehende „04 — Schwellwerte"; **Segmented Control**, keine Checkboxen:
**PO-Entscheidung 2026-07-28, wörtlich „Es gibt kein zusätzlich: entweder
oder"** — die Auswahl ist eine **Einzelwahl** über sich gegenseitig
ausschließende Möglichkeiten (Spanne / nur Tiefstwert / nur Höchstwert /
nur Mittelwert), keine Mengen-Wahl. Anlass war Adversary-Befund F001: die
ursprünglich umgesetzte Mehrfachauswahl erlaubte Tiefstwert **und**
Mittelwert gleichzeitig anzuhaken; der Mittelwert verschwand danach still
aus der Kachel. Die Einzelwahl macht diese Kombination strukturell
unmöglich, statt sie abzufangen — s. „Bekannte Grenze" unten und
`docs/artifacts/feat-1357-trip-auswertungswahl/adversary-dialog.md` Runde 3.

Die angebotenen Möglichkeiten leiten sich aus `available_aggregations(metric_id)`
ab (`pill_aggregation_choices()`/`aggregationChoices()`, gespiegelt in
Python und TypeScript): Spanne nur, wenn Tiefst- **und** Höchstwert
berechenbar sind, dazu je eine Einzelwert-Möglichkeit pro Angebots-Eintrag —
**nie** aus `default_aggregations`. Für Temperatur ergibt das vier
Möglichkeiten (Spanne, nur Tiefstwert, nur Höchstwert, nur Mittelwert); für
die gefühlte Temperatur drei (kein Mittelwert, weil der Katalog dort kein
`avg`-Feld führt). Gerendert **ausschließlich** für `metric_id ∈
{temperature, wind_chill}`, **nur** wenn die Metrik aktiv ist, Vorbelegung
aus `pill_default_aggregations(metric_id)` wenn der Nutzer noch nichts
eingeschränkt hat, Label über `aggregation_label_de()`. `context='vergleich'`
bleibt unverändert ohne diese Zeile (`'auswertungen'` steht in
`ROUTE_ONLY_SECTIONS`, `weatherMetricsTabSections.ts`) — der Ortsvergleich
zieht mit **#1411** nach.

> **Korrektur 2026-08-15 (Issue #1728 Scheibe 2):** Der hier beschriebene
> Bedienabschnitt „05 — Auswertungen" (`context='route'`) ist ersatzlos
> entfernt, nicht mehr nur `context='vergleich'`-exklusiv — der zugrunde
> liegende Renderer-Mechanismus (`MetricConfig.aggregations`) wirkt seit
> Scheibe 1 (`feat_1728_s1_temp_aufloesung`) an keinem Trip-Ausgabeort mehr
> (die E-Mail-Pillen zeigen unbedingt die Spanne). `'auswertungen'` steht
> seither nicht mehr in `ROUTE_ONLY_SECTIONS`, weil der Abschnitt selbst
> nicht mehr existiert. Diese Spec beschreibt damit einen abgelösten Stand
> (s. `docs/specs/modules/feat_1728_s2_editor.md`, dort als Dependency
> ausdrücklich als „bleibt als Historie stehen" geführt) — als
> Implementierungshistorie weiterhin korrekt, nicht mehr als
> Ist-Beschreibung der Bedienoberfläche.

**Abbildung von Altbestand (nur zur Anzeigezeit, nichts wird beim Laden
umgeschrieben):** Eine gespeicherte Liste ohne Entsprechung in den vier
Möglichkeiten wird sowohl im Renderer (`_resolve_pill_aggregations()`) als
auch im Frontend (`effectiveAggregations()`) auf die nächstliegende
Möglichkeit abgebildet:

| Gespeicherter Wert | Abbildung | Meldung |
|---|---|---|
| `["min","max","avg"]` | Spanne | **keine** — das ist exakt der Katalog-Vorgabewert (`build_default_display_config()`), keine Nutzerwahl |
| `["min","avg"]` | nur Tiefstwert | ja, `logger.warning` |
| `["max","avg"]` | nur Höchstwert | ja, `logger.warning` |
| `["avg"]` | nur Mittelwert | — (das ist bereits eine gültige Möglichkeit) |
| `[]` | keine Kachel | — |

`frontend/src/lib/types.ts` — `WeatherConfigMetric` bekommt
`aggregations?: string[];` (analog zu `sms_threshold?`), sonst geht eine
Nutzer-Einschränkung beim nächsten Speichern über die Oberfläche verloren.

`docs/reference/api_contract.md` — `aggregations` bei `MetricConfig`
dokumentieren (bisher nicht erwähnt).

## Expected Behavior

- **Input:** `MetricConfig.aggregations: list[str]` je Metrik im Trip-
  `display_config` (unverändertes Feld); Auswahlfläche im Trip-Editor nur
  für Temperatur und gefühlte Temperatur.
- **Output:** E-Mail-Kachelzeile (HTML, Plain, Kompaktfassung) zeigt für
  diese zwei Größen die gewählten bzw. vorgegebenen Auswertungen; alle
  übrigen 22 Größen unverändert. **Beabsichtigte Verhaltensänderung:**
  jeder Trip, bei dem die gefühlte Temperatur aktiviert ist und noch keine
  Einschränkung getroffen wurde, zeigt ab dieser Auslieferung die Spanne
  (Tiefst- und Höchstwert) statt bisher nur den Tiefstwert.
- **Side effects:** keine neuen API-Calls; reine Render-Logik-Erweiterung.
  Kein Migrationsschritt, keine Persistenz-Schema-Änderung.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit aktivierter gefühlter Temperatur, bei dem
  der Nutzer nie eine Auswertung eingeschränkt hat, und deutlich
  auseinanderliegendem Tiefst- und Höchstwert / When die Briefing-Mail
  gerendert wird / Then zeigt die Kachelzeile für die gefühlte Temperatur
  sowohl den Tiefst- als auch den Höchstwert als Spanne — wie bei der
  gemessenen Temperatur, nicht mehr nur den Tiefstwert. Das gemeldete
  Problem (Höchstwert nicht darstellbar) ist damit bereits ohne jede
  Nutzeraktion gelöst.
  - Test: Fixture mit `wind_chill_min_c` ≠ `wind_chill_max_c`, Rendering
    vor/nach der Änderung vergleichen; Höchstwert muss neu im Text stehen.

- **AC-2:** Given ein Trip mit aktivierten übrigen Wettergrößen (u. a.
  gemessene Temperatur, Wind, Böen, Regen, Regenwahrscheinlichkeit,
  Gewitter, Sicht, Nullgradgrenze) / When dieselbe Mail gerendert wird /
  Then bleiben deren Kacheln — Text UND zugrundeliegender Zeitraum —
  unverändert zur heutigen Ausgabe; die Umstellung wirkt ausschließlich
  auf die gefühlte Temperatur.
  - Test: golden-Fixture-Vergleich über alle Kachel-Metriken außer
    `wind_chill`, bit-identisch vor/nach der Änderung.

- **AC-3:** Given ein Nutzer schränkt im Trip-Editor die gefühlte
  Temperatur explizit auf „nur Höchstwert" ein / When die nächste
  Briefing-Mail versendet wird / Then zeigt die Kachelzeile ausschließlich
  die gefühlte Höchsttemperatur, ohne den Tiefstwert.
  - Test: Trip mit expliziter Einschränkung `["max"]` für `wind_chill`,
    Assert, dass nur der Höchstwert im Pill-Text auftaucht.

- **AC-4:** Given ein Nutzer trifft bei Temperatur und bei gefühlter
  Temperatur dieselbe Einschränkung (z. B. jeweils „nur Höchstwert") /
  When die Mail gerendert wird / Then verhalten sich beide Kacheln in
  Darstellungsform identisch (gleiches Wert-plus-Uhrzeit-Muster), und
  beide Werte beziehen sich nachweislich auf denselben Zeitraum der
  Wanderung.
  - Test: identische Einschränkung für `temperature` und `wind_chill`,
    Assert auf strukturell gleiche Textform.

- **AC-5:** Given eine Wettergröße, die im Trip-Editor nur eine mögliche
  Auswertung anbietet (z. B. Wind, Niederschlag) / When der Nutzer die
  Metrik-Einstellungen öffnet / Then erscheint für diese Größe **keine**
  Auswertungs-Auswahl (kein wirkungsloses Bedienelement).
  - Test: Frontend-Komponententest, Zeilen-Komponente wird für Metriken
    mit einer `summary_fields`-Auswertung nicht gerendert.

- **AC-6:** Given ein Nutzer trifft eine Auswertungs-Einschränkung und
  speichert den Trip / When der Trip-Editor danach erneut geöffnet wird /
  Then ist die getroffene Einschränkung weiterhin sichtbar und
  unverändert — kein Datenverlust beim Speichern-und-neu-Laden.
  - Test: Speichern-Laden-Roundtrip über den echten Persistenzpfad, Assert
    auf identische Auswahl.

- **AC-7:** Given ein Trip, dessen gespeicherte Auswertungswahl für eine
  Größe eine dort unmögliche Auswertung enthält (z. B. „Mittelwert" bei
  der gefühlten Temperatur, die nur Höchst-/Tiefstwert kennt) / When die
  Mail gerendert wird / Then wird der ungültige Eintrag nicht still
  ignoriert, sondern sichtbar behandelt — entweder abgelehnt (Pill entfällt
  für die unauflösbare Auswertung, gültige Teile bleiben) oder mit einer
  nachvollziehbaren Meldung protokolliert.
  - Test: Fixture mit `aggregations=["avg"]` bei `wind_chill`, Assert auf
    sichtbares Guard-Verhalten (analog `resolve_outlook_metrics()`-Warnmuster).

- **AC-8:** Given ein Trip, dessen gespeicherte Auswertungswahl für eine
  der zwei Größen eine leere Liste ist (`aggregations=[]`) / When die Mail
  gerendert wird / Then erscheint für diese Größe **keine** Kachel — kein
  leeres oder kaputtes Element. **Bedienweg:** Über die Segmented-Control-
  Einzelwahl (`AggregationMetricRow.svelte`) ist eine leere Auswahl nicht
  erreichbar — sie bietet ausschließlich die vier sich ausschließenden
  Möglichkeiten an, nie „keine". Eine Wettergröße vollständig aus der Mail
  zu nehmen geschieht über die Grundauswahl (die Metrik selbst abwählen,
  `MetricConfig.enabled=False`), nicht über die Auswertungswahl. `[]` bleibt
  als gültiger, gespeicherter Zustand bestehen (Alt-API-Aufrufe, künftige
  Schreibwege) und wird beim Rendern korrekt in „keine Kachel" übersetzt.
  - Test: `aggregations=[]` explizit gesetzt, Assert, dass der Pill-Text
    für diese Metrik fehlt, alle anderen Kacheln unverändert.

- **AC-9:** Given ein Nutzer ändert die Auswertungswahl bei einem Trip /
  When er anschließend einen Ortsvergleich öffnet, der dieselbe
  Wettergröße zeigt / Then bleibt die Darstellung im Ortsvergleich
  unverändert — die Trip-Wahl hat keine Auswirkung auf den Vergleich
  (diese Lieferung stellt nur den Trip um, der Vergleich zieht mit #1411
  nach).
  - Test: Ortsvergleich-Golden-Fixture vor und nach einer Trip-Auswahl-
    Änderung rendern, Text bit-identisch.

## Test-Plan

Kern-Schicht (deterministisch, kein Mock-Theater), Testdateien nach
Verhalten benannt (nicht nach Issue-Nummer — `test_naming_gate.py` blockt
das hart).

| AC | Testfall |
|----|----------|
| AC-1 | `tests/tdd/test_trip_aggregation_pill_default_range.py` — gefühlte Temperatur zeigt Spanne ohne Nutzeraktion |
| AC-2 | golden-Fixture-Regressionsvergleich (bestehende Suiten `tests/golden/email/`), alle Nicht-Wind-Chill-Kacheln bit-identisch |
| AC-3 | `tests/tdd/test_trip_aggregation_pill_selection.py::test_wind_chill_max_only_shows_max` |
| AC-4 | `tests/tdd/test_trip_aggregation_pill_selection.py::test_temperature_and_wind_chill_same_selection_same_shape` |
| AC-5 | `frontend/src/lib/components/shared/weather-metrics-tab/*.test.ts` (node:test, `test-lib-loader.mjs`) — Zeilen-Komponente nicht gerendert für Einzel-Auswertungs-Metriken |
| AC-6 | `tests/test_metric_config_aggregations_roundtrip.py` — Loader-Schreib-/Lese-Roundtrip |
| AC-7 | `tests/tdd/test_trip_aggregation_invalid_choice_guard.py` |
| AC-8 | `tests/tdd/test_trip_aggregation_pill_selection.py::test_empty_selection_hides_pill` |
| AC-9 | `tests/golden/email/` — bestehendes Compare-Golden-Fixture unverändert nach Trip-Änderung |
| F001 (Fix-Loop Runde 3) | `tests/tdd/test_trip_aggregation_single_choice.py` — Einzelwahl statt Mehrfachauswahl: alle Teilmengen/Permutationen/Duplikate von `{min,max,avg}` außer der exakten Katalog-Vorgabe werden protokolliert und auf eine gültige Möglichkeit abgebildet, kein stiller `avg`-Verlust mehr |

**Bewusste Golden-Fixture-Neuerzeugung (kein Testbruch):** Die
`wind_chill`-Fälle in `tests/tdd/test_issue_912_pill_textformat.py`
(`TestAC2WindChill`, insbesondere `test_wind_chill_format_exact`) sowie
`wind_chill`-Zeilen in `tests/golden/email/` (dort, wo `wind_chill`
aktiviert ist) müssen auf die neue Spannen-Ausgabe umgestellt werden. Das
ist eine gewollte Folge von AC-1, keine Regression — muss beim Implement
explizit als „erwartete Fixture-Änderung", nicht als Fehlschlag behandelt
werden.

**Renderer-Commit-Gate #811 (Pflicht vor Commit):** `email/helpers.py`,
`email/html.py`, `email/plain.py`, `email/compact.py` sind
Mail-Inhalts-Dateien → `renderer_mail_gate.py` blockiert, bis (1)
`tests/tdd/test_issue_811_mode_matrix.py` grün ist UND (2) ein frischer
`briefing_mail_validator.py`-Lauf gegen eine echte Staging-Testmail
erfolgreich war.

## Known Limitations

- **Stundentabelle:** braucht keine Tagesauswertung — nicht Teil dieser
  Lieferung.
- **Nacht-Block („🌙 Nacht am Ziel"):** folgt der Sicherheits-Konvention
  „konservativster Wert" (`night_temp_evening_only.md`), keine
  Anzeigepräferenz — bewusst unberührt.
- **3-Tages-Ausblick:** der Renderer kann die Auswahl bereits verarbeiten
  (`outlook_columns(metrics)`), aber dem Trip fehlt dafür die Bedienfläche
  — eigener Umfang, nicht Teil von #1357.
- **Kurzformen (SMS, E-Mail-Kurzzusammenfassung, Telegram):** die gefühlte
  Temperatur ist dort heute vollständig unsichtbar (verifiziert, s.
  Purpose Punkt 4) — bewusst **nicht** Teil dieser Lieferung, als Scheibe
  2 vorgeschlagen (s. „Reichweite und Schnittempfehlung"). Die separate
  Anforderung „Tiefsttemperatur während des Trips als eigene Angabe" bleibt
  in **#1410**.
- **Ortsvergleich:** bekommt in dieser Lieferung keine Änderung (AC-9). Die
  geteilte Katalog-Naht (`summary_field_for`) entsteht hier bereits, damit
  #1411 sie direkt übernehmen kann, statt sie zu duplizieren.
- **WC-Kontraktlücke im produktiven SMS-Pfad** (s. Nebenbefund oben) ist
  vorbestehend und nicht Gegenstand dieser Spec.
- **Fehlalarm-Ausnahme für `["min","max","avg"]` ist wertbasiert, nicht
  herkunftsbasiert** (Adversary-Restpunkt, Runde 3, PO-informiert, kein
  Blocker): `_resolve_pill_aggregations()` unterdrückt die
  Protokollmeldung für exakt diese Liste, damit der Katalog-Schreib-Default
  (`build_default_display_config()`, den jeder neue Trip für Temperatur
  bekommt) nicht bei jeder Mail einen Fehlalarm auslöst. Die Prüfung kann
  aber nicht unterscheiden, ob die Liste vom System oder von einem
  Aufrufer stammt, der bewusst genau diese drei Werte gesendet hat — ein
  solcher Aufrufer bekäme weiterhin kommentarlos nur die Spanne, ohne dass
  „Mittelwert wurde verworfen" protokolliert wird. Über die ausgelieferte
  Oberfläche (Segmented Control) ist diese Liste **strukturell nicht mehr
  erzeugbar** — sie schreibt ausschließlich eine der vier kanonischen
  Möglichkeiten oder lässt das Feld unberührt. Relevant würde der
  Restpunkt erst, wenn ein weiterer Schreibweg zur Programmschnittstelle
  entsteht (Massen-Import, Datenwanderung).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Kein neues strukturelles Muster. Die geteilte Katalog-
  Naht (`summary_field_for`) hebt bereits dupliziert vorhandene Logik in
  eine gemeinsame Quelle, statt ein neues Muster einzuführen. Kein
  Persistenz-Schema-Eingriff (Korrektur gegenüber der Erstfassung), kein
  neuer Kanal, kein neuer Provider, keine Auth-/Editor-Paradigmenänderung.

## Changelog

- 2026-07-28: Initial spec created — Issue #1357, Epic #1372 Scheibe S4a
- 2026-07-28: Überarbeitet nach PO-Klärung — Rechenweg-Annahme korrigiert
  (Temperatur/gefühlte Temperatur bereits identisch berechnet),
  Migrationsbedarf entfällt (`enabled` statt `aggregations` ist die
  tragende Einstellung), AC-1 von „Bitgleichheit" auf „gewollte
  Gleichstellung" umgestellt, Reichweite auf die Kachelzeile begrenzt
  (Kurzformen als Scheibe-2-Vorschlag ausgegliedert, WC-Produktionslücke
  als Nebenbefund dokumentiert)
- 2026-07-28: Spec nach Fix-Loop Runde 3 des Adversary-Dialogs
  nachgezogen (Umsetzung ist maßgeblich, nicht die ursprüngliche Spec-
  Fassung). PO-Entscheidung, wörtlich: „Es gibt kein zusätzlich: entweder
  oder." Bedienfläche von Mehrfachauswahl/Checkboxen (Ursprung des
  Adversary-Befunds F001 — Mittelwert konnte still verschwinden) auf
  Segmented-Control-Einzelwahl über vier sich ausschließende
  Möglichkeiten umgestellt (Implementation Details §4). AC-8 auf den
  tatsächlichen Bedienweg umformuliert (leere Auswahl ist über die
  Oberfläche nicht mehr erreichbar, „ganz aus der Mail nehmen" geschieht
  über die Grundauswahl der Metrik). Abbildung von Altbestandswerten
  (`["min","max","avg"]` etc.) ergänzt. Bekannte, PO-informierte Grenze
  dokumentiert (Fehlalarm-Ausnahme ist wertbasiert, nicht
  herkunftsbasiert). Umfangsschätzung von ~185 auf tatsächlich ~440 LoC
  korrigiert, PO-Freigabe der Grenze auf 450. Test-Plan um
  `tests/tdd/test_trip_aggregation_single_choice.py` ergänzt.
