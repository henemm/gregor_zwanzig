# Context: feat-1357-trip-auswertungswahl

Issue: [#1357](https://github.com/henemm/gregor_zwanzig/issues/1357) · Scheibe **S4** von Epic [#1372](https://github.com/henemm/gregor_zwanzig/issues/1372) (Dach: #1374)
Track: Full Process · erstellt 2026-07-28

## Request Summary

Im Trip-Briefing fehlt die Auswahl, **welche Auswertung** (Höchst-/Tiefst-/Mittelwert) einer Wettergröße
in der Mail erscheint. Das Feld `MetricConfig.aggregations` existiert und wird gespeichert, aber
**kein Renderer liest es** — und im Trip-Editor gibt es keine Fläche, es zu setzen. Sichtbarer Anlass:
die gefühlte **Höchst**temperatur ist im Ortsvergleich wählbar, im Trip-Briefing nicht darstellbar.

## Befundlage (am Code belegt, Stand `eaaff540`)

### Schreibweg vorhanden, Leseweg fehlt

| Richtung | Fundstelle | Zustand |
|---|---|---|
| Datenmodell | `src/app/models.py:528` — `aggregations: list[str] = ["min","max"]` | vorhanden |
| Serialisieren | `src/app/loader.py:159` | vorhanden |
| Parsen | `src/app/loader.py:779`, `:813`, `:846` (Default `["min","max"]`) | vorhanden |
| Migration Altformat | `src/app/loader.py:907-929` (`enabled_metrics[m.id]` bzw. `m.default_aggregations`) | vorhanden |
| **Renderer liest `mc.aggregations`** | **0 Treffer** in `src/`, `api/` | **fehlt** |
| **Auswahlfläche Trip-Editor** | keine | **fehlt** |

### Was stattdessen entscheidet — der Katalog-Default

Alle Auswertungen werden heute fest aus dem zentralen Katalog gezogen, nicht aus der Nutzerwahl:

- `src/output/renderers/email/helpers.py:175-186` — `agg = metric_def.default_aggregations[0]`,
  mit Sonderregel „falls mehrere und `min` dabei ⇒ `min`". Danach min/max/sum/avg.
- `src/output/renderers/trip_report.py:427-429` — identische Logik, zweite Kopie.

Die **Rechenlogik existiert also bereits vollständig**; es fehlt ausschließlich das Signal, welche
Auswertung der Nutzer will (PO-Nachtrag im Ticket, 2026-07-24).

### Der Engpass: Metrik-IDs ohne Auswertung

Der Pillen-Pfad reicht nur nackte IDs durch — an **drei** Stellen identisch:

- `src/output/renderers/email/html.py:1163` — `_pill_metric_ids = [mc.metric_id for mc in dc.metrics if mc.enabled]`
- `src/output/renderers/email/plain.py:155` — dieselbe Zeile
- `src/output/renderers/email/compact.py:146` — dieselbe Zeile

Empfänger ist `build_metrics_summary_pills()` (`email/helpers.py:1503`), das nur `list[str]` annimmt.
Der Beleg steht als Kommentar an der Bruchstelle: `email/helpers.py:1233-1247` (wind_chill-Pille)
dokumentiert den in #1351 zurückgebauten Versuch — eine Werteabweichungs-Heuristik (`max != min`)
blendete die Höchsttemperatur ungefragt bei **jedem** Trip ein und brach 10 Golden-Tests
(Adversary-Fund F001, CRITICAL).

### Weitere Leser von `dc.metrics` (potenzieller Umfang)

`grep "for mc in dc.metrics"` — die Auswertungs-Wahl könnte über die Pillen hinaus wirken:

| Pfad | Fundstelle |
|---|---|
| Stundentabelle Spaltenaufbau/-reihenfolge | `email/html.py:715`, `:779-782` |
| Tages-/Nachtblock-Aggregation | `email/helpers.py:76`, `:95`, `:147`, `:971`, `:991`, `:1012` |
| Textreport / SMS | `trip_report.py:252`, `:258`, `:395`, `:477` |
| Kompaktfassung | `compact_summary.py:140` |
| Ausblick (`selected_metrics`) | `email/html.py:1194`, `email/plain.py:147` |

**Offene Frage für die Analyse:** Welche dieser Pfade sollen die Nutzerwahl respektieren und welche
bleiben katalog-getrieben? Ticket-Punkt 4 nennt neben `wind_chill` auch `temperature`,
`snowfall_limit`, `freezing_level` als Größen mit mehreren Auswertungen.

## Existing Patterns — der Vergleich hat es bereits

### Auswahl-Schlüssel = Größe + Auswertung

`frontend/src/lib/components/shared/weather-metrics-tab/compareMetricSelection.ts`
speichert seit #1373 (S2 Scheibe B) `{metric_id, aggregation}` statt eines getippten Schlüssels und
hält einen Umkehr-Index. Grundregel dort: **jede Übersetzung ist verlustfrei**, Unauflösbares bleibt
unverändert stehen (nichts wird still verworfen).

### Namensregister (#1401 A1, live seit `21a82c12`) — das Fundament für S4

- `src/app/compare_metric_catalog.py`: Label wird aus `metric_catalog.label_de` abgeleitet;
  `aggregation_label` (Maximum/Minimum/Mittel/Summe) kommt als **eigenes Feld** dazu.
- Frontend zeigt die Auswertung als eigenes Element neben dem Namen
  (`WeatherMetricsTab.svelte:884-887`, CSS `:1509`), **context-abhängig**: der Trip-Zweig
  (`context='route'`) setzt `aggregation_label` heute nicht.

### Geteilte Bausteine (PO-Vorgabe, Epic #1230)

`WeatherMetricsTab.svelte` ist bereits geteilt (`context: 'route' | 'vergleich'`,
`weatherMetricsTabSections(context)`). Unterbausteine unter
`frontend/src/lib/components/shared/weather-metrics-tab/`: `WeatherV2Grundauswahl`,
`WeatherV2Reihenfolge`, `WeatherV2MailPreview`, `ThresholdMetricRow`, `DayWindowCard`.
⇒ Die Auswertungs-Auswahl **muss** als geteilter Baustein entstehen; eine trip-eigene
Zweitlösung wäre laut CLAUDE.md ein Default-Fehler (Anti-Pattern-Referenz #1170).

### Katalog kennt beide Erscheinungsformen bereits

`src/app/metric_catalog.py:32,38` — jeder Eintrag trägt `default_aggregations: tuple[str,...]`
**und** `summary_fields: dict[str,str]` (z. B. `temperature`: `min/max/avg`; `wind_chill`: `min/max`).
Der Katalog ist damit die vorhandene Quelle für „welche Auswertungen bietet diese Größe an".

## Dependencies

**Upstream (wovon wir abhängen)**
- `src/app/metric_catalog.py` — welche Auswertungen eine Größe anbietet
- `src/app/loader.py` — Persistenz-Rand (Read-Modify-Write, Bestandsdaten!)
- `src/app/compare_metric_catalog.py` — Namensregister/`aggregation_label` (#1401 A1)

**Downstream (was von uns abhängt)**
- Alle Mail-Renderer (`src/output/renderers/email/*`), Textreport, Kompaktfassung
- Golden-Fixtures: `tests/golden/email/`, `tests/golden/text_report/`, `tests/golden/test_sms_golden.py`
- `tests/tdd/test_issue_912_pill_textformat.py::test_wind_chill_format_exact` — in #1351 von
  Substring- auf Exakt-Vergleich verschärft; fängt genau diesen Fehler

**Go-Schicht: voraussichtlich kein Eingriff nötig**
`internal/model/trip.go:108` hält `DisplayConfig` als opake `map[string]interface{}`;
`internal/handler/trip.go:297-298` merged sie feldweise (`mergeConfigMap`). Ein neues Feld innerhalb
`display_config.metrics[]` fließt damit ohne Go-Änderung durch — **in der Analyse verifizieren**
(vgl. Memory: „display_config spart den Go-Eingriff", ADR-0037).

## Existing Specs

- `docs/specs/modules/compare_metric_selection_source.md` — Herkunft der Compare-Auswahlliste
- `docs/context/fix-1094-compare-config.md` — „vier inkompatible Metrik-Vokabulare"
- `docs/adr/` — ADR-0035 (gemeinsames Tagesfenster), ADR-0037 (geteilter Ausblick)

## Risks & Considerations

1. **Golden-Test-Bruch (Hauptrisiko, in #1351 real eingetreten).** Ticket-Punkt 3 ist bindend:
   Bestandsauswahl ⇒ Ausgabe **bitgleich** zu heute, keine Fixture-Neugenerierung. Das verlangt
   einen Default, der die heutige Katalog-Heuristik (`helpers.py:175-186`) exakt reproduziert.
2. **Zwei Kopien derselben Aggregations-Logik** (`helpers.py:175` und `trip_report.py:427`) —
   Auseinanderlaufen bei einseitiger Änderung.
3. **Bestandsdaten.** `loader.py` ist schema-relevant (CLAUDE.md „Daten-Schema-Reworks"):
   Read-Modify-Write mit Merge, nie Replace. Alt-Trips ohne bewusste Auswahl dürfen sich nicht ändern.
4. **Renderer-Commit-Gate #811** greift zwingend (`email/*.py` + `trip_report.py` sind gelistet):
   `test_issue_811_mode_matrix.py` grün **und** frischer `briefing_mail_validator.py`-Lauf gegen eine
   echt zugestellte Staging-Mail, sonst blockt der Commit.
5. **LoC-Limit 250** — drei Schichten (Oberfläche, Durchreichweg, Renderer) könnten reißen.
   Schneiden statt Override; Override nur mit PO-Freigabe.
6. **Teilungs-Invariante.** „Hätte das ein geteilter Baustein sein müssen?" ist expliziter
   Adversary-Punkt — gilt für Auswahlfläche *und* für den Durchreichweg.
7. **Umfangsfrage offen** (Ticket-Punkt 4): nur `wind_chill` oder alle mehrdeutigen Größen; nur
   Pillen oder auch Stundentabelle/Ausblick. Muss in `/20-analyse` entschieden werden, weil davon
   Score und Schnitt abhängen.

---

# Analysis (Phase 2, abgeschlossen 2026-07-28)

## Type

**Feature** (Nachrüstung einer nie gebauten Auswahlfläche + Wirkpfad), kein Bug.

## Befund 1 — die Kandidatenmenge ist winzig: zwei Größen

Katalog-Dump über `get_all_metrics()` (selbst ausgeführt, nicht geschätzt):

| id | `default_aggregations` | `summary_fields` | real wählbar? |
|---|---|---|---|
| `temperature` | min, max, avg | min→`temp_min_c`, max→`temp_max_c`, avg→`temp_avg_c` | **ja — 3 Auswertungen** |
| `wind_chill` | min, max | min→`wind_chill_min_c`, max→`wind_chill_max_c` | **ja — 2 Auswertungen** |
| `snowfall_limit` | min, max | **nur** min→`snowfall_limit_m` | nein |
| `freezing_level` | min, max | **nur** min→`freezing_level_m` | nein |

Alle übrigen 22 Katalog-Einträge haben genau eine Auswertung.

**Ableitung:** Die anzubietenden Auswertungen kommen aus **`summary_fields`**, nicht aus
`default_aggregations`. Bei `snowfall_limit`/`freezing_level` ist „max" mangels Tagesfeld nicht
berechenbar — dort eine Wahl anzubieten wäre ein Attrappen-Element und verstieße gegen
Epic-Invariante 1. Kein Katalog-Fix nötig, kein Picker für diese beiden.
(Nebenbefund: `default_aggregations` verspricht dort mehr als `summary_fields` hält → #1199.)

## Befund 2 — heutiger Ist-Zustand der beiden Pillen

- `temperature` (`email/helpers.py:1215-1231`): zeigt bereits **min UND max** als Spanne
  („8–11°C · Max 15:00"). Zwei Auswertungen gleichzeitig sind also der Normalfall, nicht die Ausnahme.
- `wind_chill` (`email/helpers.py:1233-1252`): zeigt **nur min** („gef. min 6.6°C · 13:00"),
  mit dem in #1351 F001 gesetzten Sperr-Kommentar.

⇒ Die Auswahl ist eine **Mengen**-Wahl (welche Auswertungen erscheinen), keine Einzelwahl.

## Befund 3 — das vorhandene Feld kann „nie eingestellt" nicht ausdrücken

`loader.py:159` schreibt `aggregations` bei **jedem** Speichern, Feld-Default ist `["min","max"]`
(`models.py:528`). Folge: praktisch jeder gespeicherte Trip trägt bereits `["min","max"]`, ohne dass
je ein Nutzer etwas gewählt hätte. Eine naive Auswertung dieses Feldes würde bei `wind_chill` für
**alle** Bestands-Trips zusätzlich den Höchstwert einblenden — exakt der #1351-F001-Fehler auf
anderem Weg.

**Entschieden (Tech-Lead-Entscheidung, gehört in die Spec):** `aggregations` (Plural) bleibt das
**eine** Feld und wird auf `Optional[list[str]] = None` umgestellt; die Alt-Werte werden per
idempotenter Migration mit Sicherung entfernt (Muster: #1373, `test_compare_active_metrics_format_migration.py`).
Verlustfrei, weil das Feld nachweislich nie bedienbar war — jeder gespeicherte Wert ist der
Schreib-Default, keine Nutzerwahl.
*Verworfene Alternative:* ein zweites Feld `aggregation` (Singular) neben `aggregations`. Vermeidet
die Migration, schafft aber zwei fast gleichnamige Felder mit verschiedener Bedeutung — genau die
Altlast-Klasse, die Epic #1372 beseitigt — und zementiert „Trip kann nur eine Auswertung", obwohl
die Temperatur-Pille heute schon zwei zeigt.

## Befund 4 — Eingangsformat je Ausgabe-Bereich

| Bereich | bekommt heute | Fundstelle | Wahl nutzbar? |
|---|---|---|---|
| **Kurz-Kacheln (Pillen)** | nackte `list[str]` | `html.py:1163/1174`, `plain.py:155/166`, `compact.py:146/152` → `build_metrics_summary_pills` (`helpers.py:1503`) → `_pill_for_metric` (`helpers.py:1198`) | erst nach Umbau der Kette |
| Nacht-Block (2h-Zeilen, 18–06) | `MetricConfig`-Objekte | `helpers.py:147-186`, `trip_report.py:395-430` | Feld liegt an, wird ignoriert — aber **Sicherheits-Konvention** (konservativster Wert), keine Anzeigepräferenz |
| Stundentabelle | `MetricConfig`, Rohwerte | `trip_report.py:468-486` | entfällt — keine Tagesauswertung |
| 3-Tages-Ausblick | nackte `list[str]` + feste Felder | `html.py:1194`, `plain.py:147`, `outlook.py:332-333` | Renderer **kann** es bereits (`outlook_columns(metrics)`, `outlook.py:115/262/389`) — Parameter ist heute `nur Compare` (`outlook.py:51,321`); es fehlt die Trip-**Bedienfläche** |
| Textreport / Kompakt / SMS | fest verdrahtet | `trip_report.py:216`, `compact_summary.py:230-244`, `sms_trip.py:134-137` | eigener Umbau je Renderer, GSM-7-Budget (#624) |

## Befund 5 — geteilte Naht existiert, Bedienmuster unterscheidet sich

- **Teilbar und klein:** `_summary_field()` (`compare_outlook_metric_ids.py:34-47`) übersetzt
  `(metric_id, aggregation)` → Feldname **allein** über `metric_catalog.summary_fields`, ohne
  Compare-Abhängigkeit. Gehört nach `metric_catalog.py` gehoben und von beiden Seiten genutzt.
- **Nicht direkt teilbar:** `resolve_outlook_metrics()` selbst hängt an
  `compare_metric_catalog.key_for()` (`:24-26`) — reines Compare-Spaltenvokabular.
- **Oberfläche:** `WeatherMetricsTab.svelte` ist bereits context-geteilt; Grundauswahl-Schleife
  `:877-892` ist dieselbe Komponente. Der Vergleich führt jede (Größe, Auswertung) als **eigene
  Zeile**, der Trip Größen in Buckets (`{primary: string[], off: string[]}`, `:178-179`).
  **Wichtig:** Die getrennten Compare-Zeilen sind laut Epic #1372 der **Altbestand**, der Picker
  („eine Größe, dann Auswertung bestimmen") ist das **Zielbild** — der Trip-Picker ist also nicht
  die Abweichung, sondern die Zielrichtung, auf die der Vergleich später nachzieht.

## Befund 6 — Persistenz: kein Go-Eingriff, aber eine Falle

- Go behandelt `display_config` als opake Map (`internal/model/trip.go:108`); ein Feld darin fließt
  ohne Go-Änderung durch. **Bestätigt.**
- `mergeConfigMap` (`internal/handler/config_merge.go:11-22`) ersetzt Top-Level-Schlüssel
  **komplett** (`dst[k] = v`): sendet die Oberfläche `metrics`, wird die ganze Liste ersetzt.
- `frontend/src/lib/types.ts:159-194` (`WeatherConfigMetric`) kennt `aggregations` **nicht** ⇒
  sobald die Oberfläche speichert, fiele das Feld heute weg. Muss mit aufgenommen werden.
- `docs/reference/api_contract.md` dokumentiert das Feld nicht.

## Scope Assessment

| Schicht | Dateien | LoC (geschätzt) |
|---|---|---|
| Python Kern | `metric_catalog.py` (+`summary_field_for`), `models.py`, `loader.py` | ~30 |
| Python Renderer | `email/helpers.py` (Dispatch + zwei Pillen), `html.py`, `plain.py`, `compact.py`, `compare_outlook_metric_ids.py` (auf geteilte Funktion umstellen) | ~75 |
| Migration | Skript + Sicherung, idempotent, Dry-Run-Default | ~40 |
| Frontend | `types.ts`, `WeatherMetricsTab.svelte` (Picker nur bei den zwei Größen), Persistenz-Einmischung | ~70 |
| Go | — | **0** |
| Tests | Default-Bitgleichheit (F001-Wächter), Auswahl-Wirkung, Migrations-Roundtrip, Frontend-Komponente | ~100 |
| **Summe** | | **~315** |

- Risk Level: **MEDIUM–HIGH** (Mail-Ausgabepfad + Datenmigration, beides mit Präzedenzfall)
- **LoC-Limit 250 wird gerissen** → Override nötig, vorab beim PO einzuholen.

## Technical Approach (Empfehlung)

1. `summary_field_for(metric_id, aggregation)` nach `metric_catalog.py` heben; Compare-Ausblick
   darauf umstellen (eine geteilte Naht statt zwei Kopien).
2. `MetricConfig.aggregations` → `Optional[list[str]] = None`; Migration entfernt die Alt-Defaults.
3. Pillen-Kette von `list[str]` auf „ID + gewählte Auswertungen" umstellen; `_pill_for_metric`
   bekommt die Auswahl. Default `None` ⇒ heutige Ausgabe **bitgleich** (F001-Wächter-Test zuerst).
4. Picker in der geteilten `WeatherMetricsTab` nur an den Zeilen für `temperature`/`wind_chill`,
   gespeist aus `summary_fields` — damit nie eine wirkungslose Wahl erscheint.
5. Ausblick, Nacht-Block, Textreport/SMS **ausdrücklich nicht** in dieser Lieferung; Begründung je
   Bereich in der Spec, damit es nicht als vergessen gilt.

---

# Korrektur durch den PO (2026-07-28) — Richtungsentscheidung

Die Analyse oben hatte einen wesentlichen blinden Fleck: sie behandelte „Höchst-/Tiefstwert" als
einfache Aggregation über Stundenwerte. **Das ist im Trip nicht so.** PO-Hinweis:
*„die Höchsttemperatur und auch die niedrigste Temperatur beim Trip ist sehr speziell berechnet.
Dafür gibt es eine eigene Spec die zu beachten extrem relevant ist!!!!"*

## Nachgetragener Befund — drei verschiedene Berechnungswege

| Weg | Was | Fundstelle |
|---|---|---|
| **Segment-Aggregate** | SMS bildet `min(alle temp_min_c)` / `max(alle temp_max_c)` über die Etappen-Segmente | `sms_trip.py:134-137` |
| **Zwei Quellen in DERSELBEN Kachelzeile** | Wind/Böen/Regen/Regenwahrsch./Gewitter (`_DAY_WINDOW_PILL_IDS`, `helpers.py:1475`) nutzen `build_day_window_points()` — festes Tagesfenster 04–19, ortsgenau bis Ankunft entlang der Route, danach am Ziel. **Temperatur und gefühlte Temperatur bleiben auf `_collect_hiking_window_dps()`** = reine Gehzeit | `helpers.py:1478-1556`; Spec `sms_daywindow_aggregation.md` (Epic #1319 Scheibe A, ADR-0025) |
| **Nacht-Tiefsttemperatur** | Abendbriefing: echte Nachttemperatur am Schlafplatz (Ankunft→06:00) statt Tagessegment-Minimum; Morgenbriefing: Wert entfällt ganz | Spec `night_temp_evening_only.md` (#1319 Scheibe D, DEC-1, PO-freigegeben 2026-07-23); `day_window.py:196`, angewandt in `sms_trip.py:144`, `narrow.py:514`, `compact_summary.py:85` |

**Token-Lage in den Kurzformen** (`src/output/tokens/builder.py:181,222-232`):
`N` = Nacht-Min (nur abends), `D` = Tages-Max, `WC` = gefühlte Temperatur als **einzelner** Wert
in der Kategorie „wintersport" mit Schwellwert-Filter — also ohne Höchst-/Tiefstwert-Unterscheidung.

## PO-Entscheidungen

1. **Beide Größen zusammen** — Temperatur **und** gefühlte Temperatur, nicht nacheinander.
2. **Gleichbehandlung, nicht nur Sichtbarkeit:** *„Die beiden Werte sollen sich bei Trips exakt so
   verhalten, wie die normale Temperatur und auch exakt so berechnet werden. Es gibt doch den
   Algorithmus, der muss nur für andere Werte verwendet werden."*
   ⇒ Die gefühlte Temperatur bekommt **denselben** Berechnungs- und Darstellungsweg wie die
   gemessene, angewandt auf `wind_chill_c` statt `t2m_c`. Kein Nachbau, keine Sonderbehandlung.
   Der heutige Sonderfall `WC` (Einzelwert, Kategorie „wintersport") ist damit die zu behebende
   Ungleichbehandlung.
3. **Kein „Widerspruch" zu melden.** Die von mir gemeldete Divergenz (Kurznachricht zeigt abends die
   Nachttemperatur, Kachel die kälteste Gehstunde) ist kein Fehlerbefund — die Werte beantworten
   verschiedene Fragen. Stattdessen:
4. **Neue Anforderung ausgegliedert → #1410:** „die Tiefsttemperatur **während des Trips**
   ausgeben — egal ob gefühlt oder gemessen". Diese Größe existiert heute als eigenständige
   Angabe nicht (`N` ist die Nacht am Ziel, nicht die kälteste Stunde unterwegs).
5. **LoC-Grenze angehoben** auf 400 für diese Lieferung.

## Folgen für den Zuschnitt von #1357

- Die Auswertungs-Auswahl (min/max/avg) bleibt der Kern, gilt aber für **beide** Größen.
- Zusätzlich: die gefühlte Temperatur wird der gemessenen im Berechnungs- und Darstellungsweg
  gleichgestellt. Das berührt über die Kachelzeile hinaus die Kurzformen (SMS-Token,
  Kurzzusammenfassung, Telegram), weil dort heute die Ungleichbehandlung sitzt.
- Unberührt bleiben: `night_temp_evening_only.md` (Bedeutung von `N`) und die Tagesfenster-Regelung
  aus `sms_daywindow_aggregation.md`. Der geerbte Berechnungsweg wird **übernommen**, nicht neu
  entschieden.
- **Offen für die Spec-Phase** (Tech-Lead-Vorschlag, PO gibt die ACs frei): wie weit die
  Gleichstellung in dieser Lieferung reicht — nur Kachelzeile, oder alle Kurzformen mit.

## Offene Punkte

- [ ] Ortsvergleich in derselben Lieferung auf den geteilten Baustein umstellen? — Tech-Lead-Vorgabe
      bis auf Widerspruch: **nein**, erst der Trip; der Vergleich zieht als eigene Scheibe nach.
