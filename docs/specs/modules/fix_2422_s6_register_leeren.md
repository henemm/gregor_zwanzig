---
entity_id: fix_2422_s6_register_leeren
type: bugfix
created: 2026-09-30
updated: 2026-09-30
status: draft
version: "1.0"
tags: [testing, invariante, konfiguration, kanaele, sms, telegram, roh-einfach, wind-chill, register, fix]
workflow: fix-2422-s6-register
issues: ["#2422", "#2429"]
---

# Fix #2422 (Scheibe S6): Ausnahme-Register „Einstellung ≠ Auslieferung" leeren (B1, B2, B3, B5)

> **Abgelöst durch S6b** (`fix_2422_s6b_cape_aus_roh_einfach`): AC-6 und die cape-Teile von AC-7/AC-8 gelten nicht mehr; `cape` ist aus `SMS_FORMAT_MODE_METRIC_IDS` gestrichen.

## Approval

- [ ] Approved

## Purpose

Der Invarianten-Test aus S1 (`fix_2422_einstellung_gleich_auslieferung.md`) prüft, ob das, was im
gespeicherten Trip-JSON eingestellt ist, im gesendeten Text ankommt. Vier gemessene Abweichungen
wurden damals befristet im Ausnahme-Register `tests/helpers/einstellung_auslieferung_orakel.py::AUSNAHMEN`
geparkt, ohne das Produkt zu ändern. **S6 behebt sie im Produkt und entfernt die Einträge:**

| Befund | Was der Nutzer erlebt | Produkt-Ursache |
|---|---|---|
| **B1** | „Gefühlte Temperatur" ist im SMS-Reiter aktiv, fehlt aber in SMS, Premium-SMS und Telegram-Kurzform (Fall KHW 403) | `wind_chill` hat im Trip keinen Kurzform-Token; `builder.py` kennt nur N/L/D/FN/FL/FD |
| **B2** | „Einfach"/„Roh" je Metrik wirkt in SMS, Premium-SMS und Telegram-Kurzform nicht: Wolken/CAPE erscheinen immer als Zahl (`CT70@4`) | `trip_report.py` und `sms_trip.py::build_extended_metric_specs` reichen `format_mode` nicht in die `MetricSpec` |
| **B3** (= #2429) | Telegram rich zeigt die Roh/Einfach-Wahl der **E-Mail** statt seiner eigenen | `trip_report.py:155` `self._friendly_keys = build_friendly_keys(dc)` nach der E-Mail-Kollabierung, verbraucht in `:314` |
| **B5** | Telegram rich zeigt bei „Windrichtung mit Wind zusammengeführt" trotzdem eine Spalte `WD` mit nur Platzhaltern und verdrängt dadurch eine echte Metrik | `channel_layout.py::render_for_channel` filtert die zusammengeführte `wind_direction`-Spalte nicht |

PO-Entscheid 30.09.: **B1 Variante V1** — `wind_chill` erscheint in SMS/Premium-SMS/Telegram-Kurzform mit
eigenem Kürzel, es gibt keinen Editor-Hinweis „in SMS nicht verfügbar".

Der `gust`-Eintrag (Telegram-7er-Tabellenlimit, #360, `befristet=False`) **bleibt** — er ist eine
bewusste Design-Grenze, kein Fehler.

## Source

- **Register:** `tests/helpers/einstellung_auslieferung_orakel.py` (`AUSNAHMEN`, Z. ~100–226)
- **Schicht:** überwiegend **Python-Core** (`src/output/`, `src/app/`, `src/services/`, `api/`). Keine Go-Änderung. Frontend nur die Editor-Weiche im SMS-Reiter (`WeatherMetricsTab.svelte` reicht dem SMS-Kanal ein eigenes `modeCapable` an `WeatherV2Reihenfolge.svelte`, `types.ts` bekommt das Feld `sms_format_capable`); die Editor-Kürzelmarken lesen weiter `/api/sms-symbols` (`api/routers/config.py:60-90`), es gibt keine TS-/Go-Kopie des Registers.

## Befunde und Entscheidungen im Detail

### B1 — Kürzel `TF` im Trip

`wind_chill.sms_code="TF"` existiert bereits (`metric_catalog.py:~261`); der ADR-0011-Nachtrag #2232
führt `TF` als eigenständige Größe „Stundenwert" (Alarm-SMS/Telegram). Der Trip führt heute für die
gefühlte Temperatur drei Tagesauswertungen: `FL` (Tiefst) und `FD` (Höchst) über das **Gehzeit-Fenster**
(`collect_hiking_window_points`, `sms_trip.py:~246`, Felder `wind_chill_min_c/_max_c`) sowie `FN`
(Nacht-Tiefst am Ziel). Sie gehören den Kinder-Metriken `wind_chill_day_low/_day_high/_night`.

**OFFENER KONFLIKT zur PO-Freigabe (ehrlich benannt):** `TF` und `FL` messen dieselbe physikalische Größe
(gefühlte Temperatur, Tiefstwert) — genau die Konstellation, aus der `WC` in #1887 E6a ersatzlos entfiel
(„verdoppelte nachweislich FK: identisches Feld, Fenster, Aggregation", `metric_catalog.py:~868`; siehe auch
`sms_trip.py:~452`, dort wurde das Einzelwert-`wind_chill_c` bewusst abgeschafft) und die #2232 „ein Kürzel =
eine Größe" berührt. `TF` unterscheidet sich von `WC` nur dadurch, dass es **nicht identisch** ist:

| | Fenster | Aggregation | Ausgabe |
|---|---|---|---|
| `FL`/`FD` (Kinder `wind_chill_day_low/_day_high`) | Gehzeit-Fenster der Etappe (`collect_hiking_window_points`) | Tiefst bzw. Höchst | ganze °C ohne Uhrzeit |
| `FN` (Kind `wind_chill_night`) | Nachtfenster am Ziel, nur Abendbriefing | Tiefst | ganze °C |
| **`TF` (Eltern-Metrik `wind_chill`)** | **Tagesfenster** (`day_window_start_hour`–`end_hour`, Standard 04–19, `build_day_window_points`, wie `W`/`R`/`G`/`TH:`) | **Tiefst über die Stundenwerte, mit Uhrzeit** | `TF<°C>@<Stunde>` |

Der Unterschied ist damit Fenster **und** Zeitbezug (`@Stunde`), nicht bloß ein zweiter Buchstabe. Er ist
aber schmal: an einem Tag ohne Gehzeit-Abweichung sind `TF` und `FL` zahlengleich. **Grundlage dieser Spec
bleibt der PO-Entscheid V1 (`TF`).** Bewertet der PO den Unterschied als nicht tragfähig, ist die
**Alternative B1-alt** vorzulegen: „aktive Gefühlte Temperatur gibt die Kinder-Token `FL`/`FD` aus". Sie hat
einen belegten Haken: die Goldens a/b setzen die drei Kinder auf allen Ebenen **ausdrücklich `enabled:false`**,
und ein explizites `false` schlägt die Ableitung (`loader.py:~890`, `_DERIVED_METRIC_RULES` `:864-871`).
B1-alt würde also eine ausdrückliche Abwahl der Kinder übersteuern — Auslieferung ≠ Einstellung in der
Gegenrichtung. Diese Entscheidung trifft der PO mit der Freigabe der ACs 1–4; bis dahin gilt V1.

**Eltern-Metrik und `FL` gleichzeitig aktiv:** **beides wird ausgegeben, keine Unterdrückung.** Begründung:
Eltern-Metrik `wind_chill` und Kind `wind_chill_day_low` sind zwei getrennte, vom Nutzer ausdrücklich
gewählte Einträge (#1728: „unabhängige Auswahl-Entscheidungen"); Unterdrückung eines gewählten Tokens wäre
selbst eine Abweichung Einstellung ≠ Auslieferung. `TF` fällt beim Kürzen als Erstes (siehe unten), sodass
die Doppelung nie auf Kosten sicherheitsrelevanter Token geht. Eigene AC (AC-3).

**Token-Form (festgelegt):** Klasse (b) „Invers-Min" wie `VS`/`FZ` (`builder.py:456-468`,
`_mk_inverse_min_metric`, `tokens/metrics.py::render_inverse_min_value`): `TF<Tiefstwert in ganzen °C>@<Ortszeit-
Stunde>`, z. B. `TF-3@6`, `TF3@6`. Kälte ist die entscheidungsrelevante Richtung (`risk_thresholds=
{"high_lt": -20.0}`, Alarm-Text „Kaelte"); Hitze bleibt über `FD`/`D` abgedeckt.

**Nullform (belegt an den übrigen Temperatur-Token):** `builder.py:352-387` rendert jedes Temperatur-Token
über `render_temperature()`; ohne Wert entsteht `-` (Kürzel + `-`, z. B. `FL-`, „Null-Form `FK-`", `builder.py`
§9-Kommentar), bei Datenlücke `?` (`_gap_or`, #1483). `TF` folgt exakt dieser Regel: **`TF-`** (keine
Stundenwerte) und **`TF?`** (Lücke). Ein negativer Wert erscheint als `TF-3@6`. Für den Menschen liest sich
`FL-3` genauso wie heute bei `K-3`; für den Parser ist `TF-` von `TF-3@6` per `re.fullmatch` eindeutig
unterschieden (ganzer Wert `-` gegen `-3@6`). Die Orakel-Grammatik bekommt dafür das optionale Minus vor
Zahlen (siehe B2, „Token-Grammatik"). Keine Schwelle → immer sichtbar, sobald aktiv.

**Produzent (Pflicht, kein Adapter-Zufall):** `DailyForecast` hat heute keine Stunden-Serie der gefühlten
Temperatur, nur `wind_chill_min_c/_max_c` (Gehzeit) und `night_wind_chill_min_c`. Nötig ist eine neue Serie
`wind_chill_hourly` (Tuple `HourlyValue`), gefüllt in `sms_trip.py::_segments_to_normalized_forecast` aus
**derselben** Tagesfenster-Zeitreihe wie Regen/Wind/CAPE (`build_day_window_points`, `dp.wind_chill_c`),
**ohne** `> 0`-Filter (negative Werte sind gültig, wie `visibility`/`freezing_level`, Klasse (b)), Dedup je
Stunde mit **Tiefstwert** (`_dedup_by_hour_min`). Der Trip-Adapter `trip_result.py` (Legacy) bleibt
unverändert ohne Serie (`TF` entfällt dort mangels Daten, keine Null-Leiche: Muster „needs_spec").

**Position/Kürzung:** `TF` folgt der Layout-Position von `wind_chill` im SMS-Kanal-Layout (Position wie bei
den anderen Symbolen aus dem Layout geerbt, Bestandstest
`test_sms_wind_chill_position_inherits_from_anchor.py`). Priorität wie `FL` (`PRIORITY["TF"] = 4`,
`builder.py:62`). Kürzungsreihenfolge (`tokens/render.py:~90`): `TF` fällt **als allererstes** der
Komfort-Zusatzangaben, **vor** `FN`/`FL`/`FD`, also `("TF", "FN", "FL", "FD")` — `TF` ist das am ehesten
redundante der vier Token.

**Budget (gemessen, nachgerechnet):** Golden-SMS heute `E1: W20@4 R2.0@4 PR60%@4 G45@4 TH:M@4 TH+:- CT70@4 SU16`
= **55 Zeichen**. Mit Wolken-Einfachform `CT:SCT@4` (+2 gegenüber `CT70@4`) = **57**; zusätzlich `TF-3@6`
(+7 inkl. Leerzeichen) = **64**. Worst-Case-Beispiel mit Erst-/Spitzenwert `CT:BKN@4(OVC@9)` und
`TF-13@6`: **72**. Weit unter 160; Kürzen tritt erst bei sehr vielen aktiven Metriken ein, dann fällt `TF`
zuerst.

**Ortsvergleich unverändert:** die Vergleichs-SMS sendet `TF` bereits über `kurzform_kuerzel`
(`comparison.py:~647`; `TF-`/`TF+` wurden mit #2232 abgeschafft). Die Register-Änderung darf dort nichts
verschieben; Wächter `tests/tdd/test_compare_sms_kuerzel.py`.

### B2 — Roh/Einfach in SMS, Premium-SMS, Telegram-Kurzform

Premium-SMS und Telegram-Kurzform nutzen denselben `report.sms_text` (`notification_service.py:651-686`),
ein Fix wirkt auf alle drei. Die Kaskade liefert `format_mode` bereits
(`_dc_uncollapsed.get_metrics_for_channel("sms", report_type)`, `trip_report.py:~348`); die
`MetricSpec`-Builds (`trip_report.py:~391`, `~426`, `sms_trip.py:66-91`) reichen es nicht durch, obwohl
`MetricSpec` `format_mode` kennt (`tokens/dto.py:102-120`). Aufgelöst wird **pro Metrik** über
`_effective_format_mode(mc)` (`email/helpers.py:59-69`); `use_friendly_format` wird nicht roh gesetzt.
Auch `validator_render_service.build_sms_fidelity_specs` (`:500-512`) baut `MetricSpec` und muss
mitziehen, sonst weicht die Vorschau vom Versand ab.

Der bisherige Einfach-Zweig (`builder.py:170-203`, `\x00{friendly_label}`) würde das **Emoji-Label**
ausgeben — nicht GSM-7 und nicht 160-Zeichen-tauglich. Nötig ist ein **GSM-7-Einfach-Zweig**, der **dieselbe
Klassifikation wie die E-Mail** trägt (Kanalgleichheit, Epic #2133), nur in ASCII.

**Prinzip:** Einfach = *dieselbe* Token-Struktur wie Roh, nur wird die Zahl durch ihre Stufe ersetzt
(`CT70@4` → `CT:SCT@4`; mit Erst-/Spitzenwert: `Stufe@h(Stufe@h)`, kollabiert wie bei Zahlen, wenn beide
Werte in derselben Stufe und Stunde liegen). Schwellen-/Fensterlogik bleibt unverändert und arbeitet auf
den **Zahlen**; erst die Ausgabe wird auf die Stufe abgebildet.

**Wer bekommt eine SMS-Einfachform? (belegt am Editor und am Orakel, keine stille Oracle-Konstante)**

Gemessen: Der Trip-Editor bietet Roh/Einfach im **SMS-Reiter** heute für jede Größe aus `INDICATOR_MAP`
an (`frontend/src/lib/components/trip-detail/metricsEditor.ts:24-39`, `indicatorCapable()`, Default-
`modeCapable` in `weather-metrics-tab/WeatherV2Reihenfolge.svelte:75/110/157`): `wind_direction`,
`thunder`, `cape`, `cloud_total/low/mid/high`, `sunshine` — und zusätzlich `wind`, `gust`,
`rain_probability`, `precipitation` (Ampel-Größen; Backend `has_friendly_format=false`, die SMS-Token
`W`/`G`/`PR`/`R` bleiben Zahlen). Der Editor verspricht im SMS-Reiter also mehr, als die SMS liefert —
dieselbe Fehlerklasse wie #2422. Das Orakel prüft die Roh/Einfach-Dimension nur für Größen mit
`has_friendly_format` (`hat_roh_einfach_dimension`); `parse_sms_artig` (Z. 573–590) liest `[LMH]` und jeden
Nicht-Zahl-Wert als „friendly", Zahlen als „raw". `SU16` ist daher „raw"; ein Sektortext wie `NW` passt gar
nicht in `_VALUE_GRAMMAR` (er würde als fehlendes Token gelesen).

**Entscheidung (Variante (a) für Wolken/CAPE, Variante (b) für den Rest; eigene ACs 7 und 8):**

- **Echte Einfachform (a):** nur Größen, deren E-Mail-Einfachform eine **Klassifikation aus Zahlenwerten** ist
  und in der SMS ein Zahl-Token hat: Wolken `cloud_total/low/mid/high` (5 Stufen) und `cape` (Ampelband).
- **Nur eine SMS-Form (b):**
  - `thunder`: `TH:` ist bereits die Stufenform `L/M/H` der E-Mail-Klassifikation `thunder_ampel_band`;
    das Orakel liest `[LMH]` als „friendly" (Beleg `parse_sms_artig`). Eine SMS-Zahlenform gäbe es nur als
    künstlichen Stufenindex und wäre gegenüber der E-Mail-Roh-Form (deutsches Stufenwort) nicht kanalgleich.
  - `wind_direction`: `WD:` trägt den Kompass-Sektor. Der Sektor **ist** die E-Mail-Einfachform
    (`friendly_label="N/S/W/E"`); die SMS hat keine Gradzahl-Form.
  - `sunshine`: `SU16` ist eine **Tagessumme in Stunden**; die E-Mail-Einfachform ist ein **Stunden**-Symbol
    (`get_weather_emoji`). Ein Stufenband für eine Tagessumme wäre eine für die SMS neu erfundene
    Klassifikation ohne E-Mail-Gegenstück.
  - `wind`/`gust`/`rain_probability`/`precipitation`: Zahl-Token ohne SMS-Gegenstück zur Ampel.
  Für diese Größen **bietet der SMS-Reiter Roh/Einfach nicht mehr an**. Ein bereits gespeicherter Wert
  bleibt unverändert in der Datei (Merge-Regel, nie überschreiben) und wird in den SMS-artigen Kanälen nicht
  ausgewertet. Telegram rich und E-Mail behalten ihre Umschalter unverändert.
- **Eine einzige Quelle, kein zweites Verzeichnis:** benannte Katalog-Konstante
  `SMS_FORMAT_MODE_METRIC_IDS` in `metric_catalog.py` (Muster `SMS_NULLFORM_METRIC_IDS`) =
  `{cloud_total, cloud_low, cloud_mid, cloud_high, cape}`. Sie speist (1) den SMS-Builder (Einfachform nur
  für diese Größen), (2) den SMS-Reiter im Editor (`modeCapable` für den Kanal `sms`, geliefert über
  `GET /api/metrics`, Feld `sms_format_capable`; Muster #2049 „Sichtbarkeit und Backend-Wirkung an derselben
  Quelle"), (3) das Orakel: `hat_roh_einfach_dimension(metric_id, kanal)` prüft in `sms`/`premium_sms`/
  `telegram_kurzform` nur Größen aus dieser Konstante. Das ist **keine** Oracle-Ausnahme, das Orakel liest
  dieselbe Produktaussage „diese Größe hat in der SMS zwei Formen". Ein Produkttest beweist beide Hälften:
  Größe in der Konstante ⇒ Roh- und Einfach-Text verschieden; Größe nicht in der Konstante ⇒ Roh- und
  Einfach-Text **byte-gleich** (fängt eine stille Aufweichung in beide Richtungen).
- Die Zellen `sunshine`/`thunder`/`wind_direction` aus den B2-Registereinträgen entfallen damit
  **strukturell** (das Orakel erwartet dort keinen Modus mehr), nicht durch Überspringen; der Register-
  Endzustand bleibt „nur `gust`" (AC-14). Die Goldens a/b/d behalten ihre `use_friendly_format: true` für
  `sunshine`/`thunder` im SMS-Layout unverändert.

**Token-Grammatik der Einfachform (belegt):** Die Konvention #1824 B (`metric_catalog.py:826-832`): beginnt
der Wert mit einem **Buchstaben**, gehört der **Doppelpunkt ins gerenderte Kürzel** (`TH:M@4`, `WD:NW`,
`PT:S`) — „Kürzel und Wert verschmelzen sonst optisch zu einem Wort". `CTSCT@4` wäre genau das. Daher
**`CT:SCT@4`, `CL:FEW@4`, `CM:BKN@4`, `CH:OVC@4`, `CP:M@14`**. Der interne Token bleibt `symbol="CT"`
(Register-Kürzel; Abwahl #944, Priorität, `_drop_first` und `by_sym`-Zuordnung greifen unverändert); der
Doppelpunkt entsteht beim Rendern der Einfach-Stufe als führendes Zeichen des Werts (`value=":SCT@4"`).
Die Normalisierung `symbol.rstrip(":")` (`test_keine_doppelten_kennungen.py:69`, `_kurzform_kuerzel`
`metric_catalog.py:923-926`) bleibt gültig: das Register führt weiter `CT`, `CP`. `tests/helpers/
metrik_listen_scan.py` liest nur Register-Fundstellen (kein Token-Parsing) und ist nicht berührt. Das
Orakel (`_sms_treffer`, Z. 555–570) trennt Symbol und Wert per `re.fullmatch(symbol + _VALUE_GRAMMAR)` je
Register-Symbol (`_SMS_SYMBOL_TO_METRIC`), nicht per Zeichenklasse; `_VALUE_GRAMMAR` wird deshalb um die
Alternative `:(?:CLR|FEW|SCT|BKN|OVC|[LMH]|-)` samt `@h(…)`-Suffix erweitert, und `parse_sms_artig` liest
`:`-Werte als „friendly". Zusätzlich bekommt die Grammatik ein optionales Minus vor Zahlen (`-?\d+…`): heute
deckt sie ein einzelnes negatives `FL-3` nicht ab, weil `-?` nur in Bereichs-Hälften (`_RANGE_HALF`) steht.

**Vorschlag ASCII-Einfachform (PO gibt sie mit den ACs frei):**

| Metrik (Kürzel) | Roh | Einfach (ASCII, GSM-7) | Klassifikation (Quelle) |
|---|---|---|---|
| Wolken gesamt/tief/mittel/hoch (`CT`/`CL`/`CM`/`CH`) | `CT70@4` | `CT:SCT@4` — 5 Stufen **`CLR` `FEW` `SCT` `BKN` `OVC`** | ≤10 / ≤30 / ≤70 / ≤90 / >90 % — exakt die Bänder von `metric_format.cloud_emoji` (☀️🌤️⛅🌥️☁️) |
| CAPE (`CP`) | `CP900@14` | `CP:M@14` — Stufen **`-` `L` `M` `H`** | E-Mail-Ampelband `severity_for("cape")` (Schwellen 300/800/1500 J/kg): grün → `-`, gelb → `L`, orange → `M`, rot → `H` |
| Gewitter, Windrichtung, Sonne, Wind, Böen, Regenwahrscheinlichkeit, Niederschlag | — | **eine Form, unverändert** (`TH:M@4`, `WD:NW`, `SU16`, `W20@4` …) | siehe „Entscheidung"; kein Umschalter im SMS-Reiter |

Warum METAR-Wörter für Wolken: fünf Stufen brauchen fünf unterscheidbare Nicht-Zahl-Werte (Ziffern liest das
Orakel als „raw", `L/M/H` reicht nur für drei); `CLR/FEW/SCT/BKN/OVC` ist eine etablierte, selbsterklärende
Fünferskala der Luftfahrt-Wetterberichte mit denselben Deckungsgrad-Grenzen, drei ASCII-Großbuchstaben.

**CAPE grün = `-` (belegt an `TH`):** `TH:` stellt „kein Gewitterrisiko" heute als `-` dar
(`LEVELS = {0:"-",1:"L",2:"M",3:"H"}`, `tokens/metrics.py:14`; `TH:-`/`TH+:-` im Golden-Text); auch dort teilt
sich `-` die Darstellung mit „nichts über der Schwelle". `-` passt also zur bestehenden Stufenkonvention;
ein eigenes grünes Zeichen wäre die einzige Abweichung von `TH:`. Das Orakel liest `-`/`?` als ungeprüft —
damit die Prüfung im Regelfall nicht vakuum ist, **muss** die Voll-Wetter-Fixture für `cape` einen Wert im
Band gelb oder höher (≥300 J/kg) liefern, und ein Fixture-Test verlangt, dass für jede Größe aus
`SMS_FORMAT_MODE_METRIC_IDS` in den Goldens mindestens ein **geprüfter** Modus (`friendly`/`raw`, nicht
`None`) geparst wird (Vakuum-Schutz). Der Grün-Fall selbst wird vom Bandgrenzen-Test in AC-6 bewacht.

**Roh-Zweige nicht in Scope (Fall 3 geklärt):** Die Fixtures `nach_aenderung_fall3_roh_einfach_umschalten*.json`
schalten **ausschließlich `cloud_total` im E-Mail-Kanal** um (`aenderungsfaelle.json`: `channel: email`,
`false → true`); das SMS-Layout ist gegenüber `golden_a` unverändert. Ein Roh-Zweig `WD°`/Gewitter-Zahl/
Sonnen-Stufe wird deshalb weder gebraucht noch gebaut (für diese Größen gibt es in der SMS nur eine Form).

**Nutzersichtbare Änderung für Bestandsnutzer (bewusst):** Der Katalog-Default der Wolken-Metriken (und
CAPE) ist `symbol` (= Einfach, `default_format_mode="symbol"`). Nutzer, die diese Metrik nie ausdrücklich
auf „Roh" gestellt haben, sehen sie in SMS, Premium-SMS und Telegram-Kurzform künftig als **Stufe statt als
Zahl** (`CT:SCT@4` statt `CT70@4`). Das ist die getreue Umsetzung ihrer Einstellung, verändert aber die
bisher gesehene Ausgabe — eigene AC, PO-Freigabe.

Ortsvergleich-SMS kennt `format_mode` ebenfalls nicht (`comparison.py:608-643`): **nicht in S6**, Eintrag in
#1199 (siehe „Nicht in S6").

### B3 — Telegram rich erbt Roh/Einfach aus der E-Mail (#2429)

Fix lokal: in `trip_report.py:~314` `friendly_keys=build_friendly_keys(_dc_telegram)` statt
`self._friendly_keys` (`_dc_telegram` steht in `:~297`, wird bereits als `dc=` übergeben). Weitere Nutzer von
`self._friendly_keys`: nur `render_email` (`:245`, korrekt). Der Narrow-Pfad (`narrow.py:697`, `_cell`
83–88, `_narrow_table` 867) hängt an derselben Quelle und wird mitgeheilt. Ortsvergleich-Telegram ist
nicht betroffen (`comparison.py:~700-760` ohne `friendly_keys`). Testlücke laut #2429 (kein Telegram-Fall in
`test_issue_435_format_modes.py`) wird geschlossen.

### B5 — Geisterspalte `WD` in Telegram rich

Der Merge läuft bereits (`dp_to_row` + `fmt_val`: „20 W"); nur die Layout-Spalte wird nicht gefiltert
(`channel_layout.py:112-145`). Fix direkt nach dem `VISIBILITY_GATE_IDS`-Filter (`~:125`) und **vor**
`primary = sorted(...)`, damit `table_columns` **und** `demoted_count` stimmen: geteilter Helfer
`should_merge_wind_dir` (`email/helpers.py:72-90`) per **Lazy-Import** (Importzyklus) auf
`dataclasses.replace(dc, metrics=enabled)`. Die Ortsvergleich-Helfer (`compare_html.py:966`,
`comparison.py:274`) haben anderes Vokabular und werden nicht wiederverwendet; Ortsvergleich-Telegram
bleibt unberührt (`compare_metric_ids.py:44`).

**Folge für `gust`:** golden_b Telegram-Slotfolge heute: precipitation, wind, rain_probability, thunder,
cloud_total, cloud_low, **wind_direction (7)**, **gust (8, verdrängt)**. Ohne `WD` rückt `gust` auf Slot 7
und der `gust`-Eintrag würde unbenutzt (`test_ac6_ac7_…unbenutzten_eintraege` rot); ihn zu löschen bräche
den Vakuum-Schutz in `test_ac5_…`. **Lösung:** Eintrag NICHT löschen, Guard NICHT lockern. Das
golden_b-Telegram-Layout bekommt **eine weitere aktive Metrik**, damit das 7er-Limit wieder real eine
Metrik verdrängt (Kommentar `test_einstellung_gleich_auslieferung.py:~743-748` anpassen).

## Estimated Scope

- **LoC (produktiv):** ~200–320 (B3 ~1, B5 ~7, B1 ~50–70 inkl. `wind_chill_hourly`, B2 ~90–140 inkl. Einfach-Zweig, Katalog-Konstante `SMS_FORMAT_MODE_METRIC_IDS`, `/api/metrics`-Feld und Editor-Weiche im SMS-Reiter). Voraussichtlich **`workflow.py set-field loc_limit_override 500`** nötig (vorher `workflow.py status` fragen). Der Scope wird dafür **nicht verengt**; es wird kein Eintrag geparkt oder auf eine spätere Scheibe geschoben.
- **Files:** ~12 produktiv (davon 2 Frontend), ~16 Test-/Fixture-Dateien, 1 ADR.
- **Effort:** medium. Risk: MEDIUM (B2 verändert die SMS-Darstellung für nahezu alle Bestandsnutzer, B1 löst eine dokumentierte Kürzel-Entscheidung ab).

## Betroffene Dateien

### Produktiv

| Datei | Änderung |
|---|---|
| `src/output/renderers/trip_report.py` | B3 (`:~314`); B2 `format_mode` je SMS-Metrik in die Spec-Builds; B1 `wind_chill`-Spec (`TF`) |
| `src/output/renderers/sms_trip.py` | B2 `build_extended_metric_specs(format_by_metric=None)`; B1 `wind_chill_hourly` (Stunden-Serie, Tiefstwert je Stunde) |
| `src/output/tokens/dto.py` | B1 neues Feld `DailyForecast.wind_chill_hourly` |
| `src/output/tokens/builder.py` | B2 GSM-7-Einfach-Zweig; B1 `TF`-Token (Klasse (b)), `PRIORITY["TF"]`, Symbol-Liste |
| `src/output/tokens/metrics.py` | B2 Stufen-Abbildung Wolken (5) und CAPE (4) aus den E-Mail-Bändern |
| `src/output/tokens/render.py` | B1 Kürzungsreihenfolge `("TF","FN","FL","FD")` |
| `src/output/renderers/channel_layout.py` | B5 `wind_direction`-Merge-Filter |
| `src/app/metric_catalog.py` | B1 `wind_chill` als Trip-Kurzform-Symbol (`SMS_SYMBOL_BY_METRIC`, `COMPACT_LABEL_EXCEPTIONS`, Kommentar „WC entfällt ersatzlos" ~Z. 868); B2 neue Konstante `SMS_FORMAT_MODE_METRIC_IDS` |
| `api/routers/config.py` | B2 `/api/metrics`: Feld `sms_format_capable` (Z. ~113–115) |
| `frontend/src/lib/types.ts`, `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` (Aufruf `WeatherV2Reihenfolge` ~Z. 1717) | B2 Editor: im SMS-Reiter Roh/Einfach nur für Größen mit `sms_format_capable`; Frontend-Test dazu |
| `src/services/trip_command_processor.py` | B1 `TF` im Trip-Kontext von `KÜRZEL`/`CODES` nicht mehr entfernen (`codes_text(vergleich=False)`, ~Z. 355–420) |
| `src/services/validator_render_service.py` | B2 Vorschau-Specs mitziehen |
| `docs/adr/0011-alert-render-single-backend-renderer.md` | Nachtrag (s. u.) |

### Zu ziehende Pin-Tests und Test-Infrastruktur

| Datei | Änderung |
|---|---|
| `tests/helpers/einstellung_auslieferung_orakel.py` | Einträge B1/B2/B3/B5 raus, `gust` bleibt; `_VALUE_GRAMMAR` um `:`-Stufenwerte (`CLR\|FEW\|SCT\|BKN\|OVC\|L\|M\|H\|-`) und optionales Minus vor Zahlen erweitern; `hat_roh_einfach_dimension(metric_id, kanal)` liest `SMS_FORMAT_MODE_METRIC_IDS` (Produktquelle, keine eigene Oracle-Konstante) |
| `tests/fixtures/einstellung_auslieferung/golden_b.json` (+ bewusst neu eingefrorene `erwartung_golden_*.json`) | zusätzliche aktive Telegram-Metrik; Erwartungen **bewusst** neu einfrieren |
| `tests/tdd/test_einstellung_gleich_auslieferung.py` | B1-gebundene AC-2/AC-4-Tests (Z. ~135–200), Kommentare (Z. ~743–748), Docstring `test_ac9_m3_…` |
| `tests/unit/test_sms_token_symbol_register_ratchet.py` | Z. 469/490/514 (Kollision), 555–573 `_AC9_ERWARTUNG`, 622 `"wind_chill" not in SMS_MULTI_SYMBOLS_BY_METRIC`, 695–712 `test_sms_symbols_endpoint_fuehrt_wind_chill_nicht_mehr` |
| `tests/tdd/test_kuerzel_eindeutig.py` | Z. 82–95 (kein `TF` im Trip, #2454 AC-6/AC-7) |
| `tests/tdd/test_channel_metric_matrix.py` | Z. 901/990/1056 |
| `tests/tdd/test_sms_snow_symbols.py` (Z. 673), `tests/tdd/test_sms_temperature_range_token.py` (Z. 368), `tests/tdd/test_trip_sms_gsm7_charset.py` (Z. 133–189) | Register-Pins bzw. GSM-7-Wächter auf neuen Stand |
| `tests/unit/test_telegram_kuerzel_folgt_register.py` (Z. 290–320), `tests/unit/test_keine_doppelten_kennungen.py` (Z. 282–404), `tests/unit/test_sms_symbol_grammar_classes.py`, `tests/unit/test_kurzform_kuerzel_rangfolge.py`, `tests/unit/test_metric_catalog.py`, `tests/helpers/metrik_listen_scan.py` | `COMPACT_LABEL_EXCEPTIONS["wind_chill"]` und Register-Pins |
| `tests/tdd/test_sms_wind_chill_position_inherits_from_anchor.py`, `tests/tdd/test_ac6_sms_byte_identity_without_wc.py` | vorsorglich lesen/mitziehen (exponiert, nicht gelesen) |
| `tests/tdd/test_issue_1001_telegram_bubbles.py` (Z.141/171/202/303/655), `test_issue_360_channel_renderer.py`, `test_issue_429_channel_layouts.py`, `test_telegram_metric_notice.py`, `test_trip_renderer_characterization.py` | B5-Prüfung (Slotfolge Telegram) |
| `tests/red/test_issue_435_format_modes.py` | um Telegram-Fall erweitern (B3-Testlücke) |
| `tests/tdd/test_compare_sms_kuerzel.py` | unverändert, muss grün bleiben (Wächter Ortsvergleich) |

## Abgelöste Entscheidungen

- **#2454 AC-6/AC-7 „`TF` entfällt im Trip-Kontext"** (`tests/tdd/test_kuerzel_eindeutig.py:78-95`,
  `trip_command_processor.py:~355-420` `bed.pop("TF")`): abgelöst. `TF` ist im Trip die Stunden-Extrem-
  Größe `wind_chill` und steht in der `KÜRZEL`-/`CODES`-Antwort des Trips.
- **ADR-0011-Nachtrag E7** („Trip-SMS sendet `FK`/`FD`/`WC`, Vergleichs-/Alarm-SMS `TF`"): der Satz gilt
  nicht mehr; Trip-SMS sendet zusätzlich `TF` (Stundenwert). `WC` bleibt ersatzlos entfallen (#1887 E6a).
- **#2232-Ausnahme „`wind_chill.sms_code="TF"` … keine Tagesauswertung":** bleibt inhaltlich gültig und
  wird zur Begründung von B1.
- **Pflicht als Teil dieses Tickets:** neuer **ADR-0011-Nachtrag 2026-09-30 (#2422 S6)** in
  `docs/adr/0011-alert-render-single-backend-renderer.md`: `TF` = Stundenwert, jetzt auch im Trip
  (Klasse (b), `TF<°C>@<h>`); löst #2454 AC-6/AC-7 und den E7-Satz ab. Status unverändert „Akzeptiert".

## Nicht in S6

- **Ortsvergleich-SMS kennt `format_mode` ebenfalls nicht** (`comparison.py:608-643`): Paritäts-
  Nebenbefund, kein nutzerbezogener Datenverlust → Checkbox-Eintrag im Sammel-Issue **#1199**, nicht
  eigenes Issue.
- Roh-Zweige `WD°`/Gewitter-Zahl/Sonnen-Stufe in der SMS (Fall 3: kein Fixture fordert sie; für diese
  Größen gibt es in der SMS nur eine Form, der Editor bietet den Umschalter im SMS-Reiter nicht mehr an).
- Eine Sonnen-Stufe für die SMS-Tagessumme (bewusst keine erfundene Klassifikation).
- Die Alternative B1-alt (Kinder-Token `FL`/`FD` bei aktiver Eltern-Metrik) — nur falls der PO `TF` verwirft.

## Hinweise zu Gates

- **Renderer-Commit-Gate:** `trip_report.py` und `email/helpers.py`-nahe Mail-Inhalts-Dateien lösen es
  aus — vor dem Commit Modus-Matrix-Test und `uv run python3 .claude/hooks/briefing_mail_validator.py`
  (Trip-Briefing, Header `X-GZ-Mail-Type: trip-briefing`) frisch grün. Der E-Mail-Inhalt selbst ändert sich
  durch S6 nicht (B1/B2 wirken nur auf SMS-Kanäle, B3/B5 nur auf Telegram); das Gate wird trotzdem
  durchlaufen.
- **Zwei-Nutzer-Test:** nicht einschlägig — es entsteht **kein** neuer datenbewegender Endpoint; alle
  Änderungen liegen im Renderer/Token-Builder, der die bereits aufgelöste `DisplayConfig` des jeweiligen
  Trips bekommt. `/api/sms-symbols` ist ein Katalog-Endpoint ohne Nutzerdaten.
- Bestandsdaten: keine Persistenz-Änderung (`models.py`/`loader.py` unangetastet; `wind_chill_hourly` ist
  ein reines Laufzeit-DTO-Feld, kein Speicherformat).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `fix_2422_einstellung_gleich_auslieferung.md` (S1) | Spec | Register, Orakel, Golden-Fixtures, Invarianten-Test |
| `fix_2422_s5_ortsvergleich_kette.md` (S5) | Spec | Ortsvergleich-Kette; Paritäts-Wächter |
| `fix_1887_e6a_sms_kuerzel_register.md`, `fix_2232_kuerzel_ein_modell_trip_vergleich.md`, #2454 | Spec | Kürzel-Entscheidungen, die B1 berührt |
| ADR-0011, ADR-0037 | ADR | Kürzel-Quelle; Paar-Format der Metrik-Auswahl |
| `metric_format.cloud_emoji`, `thunder_ampel_band`, `severity_for` | Funktionen | Quelle der Stufen-Klassifikation (B2) |
| `email/helpers.py::_effective_format_mode`, `should_merge_wind_dir`, `build_friendly_keys` | Funktionen | geteilte Auflösung (B2/B3/B5) |

## Expected Behavior

- **Input:** gespeichertes Trip-JSON mit Kanal-Layouts (SMS/Telegram/E-Mail), je Metrik `format_mode`.
- **Output:** SMS, Premium-SMS und Telegram-Kurzform tragen jede aktive SMS-Metrik einschließlich `TF`, in
  der je Metrik eingestellten Form (Roh = Zahl, Einfach = ASCII-Stufe); Telegram rich zeigt seine eigene
  Roh/Einfach-Wahl und keine Geisterspalte.
- **Side effects:** Register enthält nur noch den `gust`-Eintrag; eingefrorene Golden-Erwartungen ändern
  sich **bewusst** (Begründung im Commit und im Test-Docstring: `TF` erscheint, Wolken als Stufe,
  Telegram-Spalte ohne `WD`).

## Acceptance Criteria

**AC-1 (B1, `TF` erscheint):** Given ein Trip mit aktiver „Gefühlte Temperatur" (`wind_chill`) im
SMS-Kanal-Layout (Fall KHW 403, Position aus dem Layout) und Stundenwerten der gefühlten Temperatur im
Tagesfenster, When das Briefing als SMS, Premium-SMS und Telegram-Kurzform gesendet wird, Then enthalten
alle drei Texte genau **ein** Token `TF<Tiefstwert>@<Stunde>` (z. B. `TF-3@6`) an der Layout-Position von
`wind_chill`, und die Texte sind ≤ 160 Zeichen; die Golden-SMS wächst von 55 auf 57 Zeichen (Wolken-Einfach)
plus 7 für `TF` = 64 Zeichen.
  - Test: echter Loader → Kaskade → Formatter → Transport-Aufzeichner mit golden_a/golden_b (kein Mock des
    Formatters); Orakel-Dimension „erscheint" für `wind_chill` in `sms`/`premium_sms`/`telegram_kurzform`
    grün ohne Register-Eintrag; der Wert ist das Minimum der Tagesfenster-Stundenwerte mit deren Stunde.

**AC-2 (B1, Nullform/Lücke/Kürzung):** Given `wind_chill` aktiv, When (a) keine Stundenwerte vorliegen, (b)
eine Datenlücke im Fenster vorliegt, (c) das 160-Zeichen-Budget überschritten würde, Then erscheint (a)
`TF-`, (b) `TF?`, und (c) fällt `TF` als **erstes** der Komfort-Zusatz-Token (vor `FN`/`FL`/`FD`, vor `PR`).
`TF-` (Nullform) und `TF-3@6` (negativer Wert) werden vom Orakel-Parser unterschieden.
  - Test: Token-Builder-Test mit echten `DailyForecast`-Werten; Kürzungsreihenfolge an einer überlangen
    Konfiguration; Parser-Test beider Formen.

**AC-3 (B1, `TF` und `FL` gleichzeitig; Abgrenzung):** Given ein Trip, in dem die Eltern-Metrik `wind_chill`
**und** das Kind `wind_chill_day_low` (`FL`) aktiv sind, When das Briefing gesendet wird, Then erscheinen
**beide** Token (`TF<°C>@<h>` aus dem Tagesfenster, `FL<°C>` aus dem Gehzeit-Fenster), keines wird
unterdrückt; ist nur die Eltern-Metrik aktiv und die Kinder sind ausdrücklich abgewählt (Goldens a/b), erscheint
nur `TF` und **kein** `FL`/`FD`/`FN`. Die Spec benennt den Konflikt „`TF` ≈ `FL`" offen; die Alternative
B1-alt (Kinder-Token statt `TF`) ist zur PO-Freigabe vorgelegt.
  - Test: zwei Konfigurationen (beide aktiv / Kinder abgewählt) gegen den echten Formatter; Fixture, in der
    Gehzeit- und Tagesfenster verschiedene Tiefstwerte liefern, damit `TF` ≠ `FL` messbar ist.

**AC-4 (B1, `KÜRZEL`/`CODES` und Editor-Marken):** Given ein Trip, When der Nutzer `KÜRZEL` oder `CODES` per
Kanal-Eingang sendet und den Editor öffnet, Then nennt die Antwort für den Trip `TF` (gefühlt), die
Editor-Kürzelmarken (`GET /api/sms-symbols`) führen `wind_chill` mit `TF`, und im **Ortsvergleich** bleibt
die Vergleichs-SMS byte-identisch zum Stand vor S6.
  - Test: `trip_command_processor.codes_text(vergleich=False)` und Endpoint-Antwort;
    `tests/tdd/test_compare_sms_kuerzel.py` unverändert grün.

**AC-5 (B2, Wolken Roh/Einfach):** Given eine SMS-Wolken-Metrik (`cloud_total`) mit Spitzenwert 70 % um
4 Uhr, When `format_mode` „Roh" ist, Then lautet der Token `CT70@4`; When „Einfach", Then `CT:SCT@4`
(Doppelpunkt im Kürzel nach der Konvention #1824 B). Die fünf Stufen sind `CLR` (≤10 %), `FEW` (≤30 %), `SCT`
(≤70 %), `BKN` (≤90 %), `OVC` (>90 %); `CL`/`CM`/`CH` verhalten sich gleich. Ein 0-%-Wert bleibt wie in der
Roh-Form ohne Sample und ergibt `-`. **Vorschlag zur Freigabe.**
  - Test: Token-Builder-Test über alle Bandgrenzen (10/11, 30/31, 70/71, 90/91) beider Modi; Orakel erkennt
    Roh als „raw", Einfach als „friendly".

**AC-6 (B2, CAPE Roh/Einfach):** Given `cape` im SMS-Layout mit Spitzenwert 900 J/kg um 14 Uhr, When „Roh",
Then `CP900@14`; When „Einfach", Then `CP:M@14`. Stufen aus dem E-Mail-Ampelband
(`severity_for("cape")`, Schwellen 300/800/1500): grün → `-`, gelb → `L`, orange → `M`, rot → `H` (wie `TH:`:
kein Signal = `-`). **Vorschlag zur Freigabe.**
  - Test: Bandgrenzen 299/300, 799/800, 1499/1500 in beiden Modi; die Voll-Wetter-Fixture liefert CAPE ≥ 300
    J/kg, damit „friendly" im Orakel geprüft wird und nicht auf dem ungeprüften `-` beruht.

**AC-7 (B2, Kanalgleichheit):** Given dieselbe Stunde mit denselben Rohwerten, When E-Mail (Einfach) und
SMS (Einfach) gerendert werden, Then entspricht die SMS-Stufe der E-Mail-Klassifikation: Wolken aus den
Bändern von `cloud_emoji`, CAPE aus `severity_for("cape")`, Gewitter (`TH:` `L`/`M`/`H`) aus
`thunder_ampel_band`.
  - Test: parametrisiert über die Band-Mittelpunkte; Zuordnung E-Mail-Band ↔ SMS-Stufe aus den
    Quellfunktionen abgeleitet, nicht hart kopiert.

**AC-8 (B2, Editor und Orakel lesen dieselbe Produktaussage; keine stille Oracle-Konstante):** Given der
SMS-Reiter des Trip-Editors, When der Nutzer die Metrikzeilen sieht, Then bietet er Roh/Einfach **nur** für
Größen aus `SMS_FORMAT_MODE_METRIC_IDS` (`cloud_total`, `cloud_low`, `cloud_mid`, `cloud_high`, `cape`) an —
nicht mehr für `thunder`, `wind_direction`, `sunshine`, `wind`, `gust`, `rain_probability`, `precipitation`;
Telegram- und E-Mail-Reiter behalten ihre Umschalter unverändert; ein gespeicherter `format_mode` dieser
Größen bleibt in der Datei erhalten. Für jede Größe **in** der Konstante unterscheiden sich Roh- und
Einfach-Text der SMS, für jede Größe **außerhalb** sind beide Texte **byte-gleich**; das Orakel prüft
Roh/Einfach in `sms`/`premium_sms`/`telegram_kurzform` genau für die Größen der Konstante (gleiche Quelle
wie Builder und Editor, `/api/metrics` Feld `sms_format_capable`).
  - Test: Frontend-Test (Umschalter im SMS-Reiter nur für die fünf Größen, Reiter Telegram/E-Mail
    unverändert); Produkttest Beide-Modi-Vergleich je Größe; Drift-Test Katalog-Konstante ↔ Endpoint-Feld;
    Orakel-Test, dass die Konstante nicht aus einer Test-Liste stammt. Mutation: Größe aus der Konstante
    streichen → Produkttest rot; `sunshine` in die Konstante nehmen, ohne Einfachform zu bauen → Produkttest rot.

**AC-9 (B2, GSM-7 und Länge):** Given jede Roh/Einfach-Kombination der Golden-Layouts, When SMS,
Premium-SMS und Telegram-Kurzform gebaut werden, Then besteht jedes Zeichen den GSM-7-Zeichensatz (kein
Emoji, keine Umlaute im Token) und die SMS bleibt ≤ 160 Zeichen; die Golden-SMS
`E1: W20@4 R2.0@4 PR60%@4 G45@4 TH:M@4 TH+:- CT70@4 SU16` (55 Zeichen) wächst durch Einfach-Stufe und `TF` auf
64 Zeichen (Worst-Case-Beispiel mit Erst-/Spitzenwert: 72).
  - Test: `tests/tdd/test_trip_sms_gsm7_charset.py` um die Einfach-Modi erweitert; Längenmessung an den
    Golden-Texten.

**AC-10 (B2, Bestandsnutzer, PO-Freigabe):** Given ein Bestandsnutzer, der `cloud_total` (oder `cape`)
nie ausdrücklich auf „Roh" gestellt hat (Katalog-Default `symbol` = Einfach), When sein nächstes SMS-,
Premium-SMS- oder Telegram-Kurzform-Briefing erzeugt wird, Then sieht er die Metrik als Stufe
(`CT:SCT@4`) statt wie bisher als Zahl (`CT70@4`); wer „Roh" gewählt hat, sieht unverändert die Zahl. Für
`thunder`, `wind_direction`, `sunshine` und die Ampel-Größen ändert sich nichts. Die Änderung ist im Commit
und in den neu eingefrorenen Golden-Erwartungen ausdrücklich benannt und wird mit dieser Spec vom PO
freigegeben.
  - Test: Trip-JSON ohne `format_mode` (Katalog-Default) gegen Trip-JSON mit `format_mode: "raw"`; die
    eingefrorenen Erwartungen tragen im Docstring den Grund der Änderung.

**AC-11 (B2, Vorschau):** Given ein Trip mit Roh/Einfach-Einstellungen, When die Editor-Vorschau
(`validator_render_service.build_sms_fidelity_specs`) und der echte Versand denselben Trip rendern, Then
sind beide SMS-Texte zeichengleich.
  - Test: beide Wege am selben Golden-Trip, Textvergleich.

**AC-12 (B3, jeder Kanal zeigt seine eigene Einstellung):** Given `cloud_total` im E-Mail-Layout „Roh" und
im Telegram-Layout „Einfach" (und umgekehrt), When das Trip-Briefing per E-Mail und Telegram rich gesendet
wird, Then zeigt die E-Mail ihre Wahl (Zahl bzw. Emoji), Telegram rich seine eigene (Emoji bzw. Zahl) —
nie die Wahl des anderen Kanals.
  - Test: beide Richtungen in einer Testdatei; schließt die Telegram-Lücke aus #2429 in
    `test_issue_435_format_modes.py`-Umfeld; Orakel-Dimension „Modus" grün ohne Register-Eintrag.

**AC-13 (B5, keine Geisterspalte):** Given ein Trip mit `wind_direction` im Skalenmodus zusammen mit
`wind` im Telegram-Layout, When Telegram rich gerendert wird, Then gibt es **keine** eigene Spalte `WD`,
die Windzelle zeigt Wert und Richtung („20 W"), und die bisher wegen des 7er-Limits verdrängte Metrik
rückt in die Tabelle nach; `demoted_count` zählt `wind_direction` nicht mit.
  - Test: `render_for_channel` und vollständiger Telegram-Render an golden_b; Ortsvergleich-Telegram
    unverändert (Wächter aus S5).

**AC-14 (Register-Endzustand):** Given der Stand nach S6, When der Invarianten-Test läuft, Then enthält
`AUSNAHMEN` **ausschließlich** den `gust`-Eintrag (`befristet=False`, Telegram-7er-Limit); der
Unbenutzt-Wächter (`test_ac6_ac7_…unbenutzten_eintraege`) und der Vakuum-Schutz (`test_ac5_…`) sind
unverändert scharf. Damit das 7er-Limit real verdrängt, trägt das golden_b-Telegram-Layout eine weitere
aktive Metrik (Slot 8 ist danach wieder belegt und `gust` wird real verdrängt).
  - Test: Invarianten-Test grün; Mutations-Gegenprobe (Register-Eintrag löschen → `test_ac5_…` rot;
    Metrik aus golden_b entfernen → Unbenutzt-Wächter rot).

**AC-15 (Kein stilles Einfrieren):** Given die geänderten Golden-Erwartungen (`erwartung_golden_*.json`),
When sie neu eingefroren werden, Then geschieht das ausdrücklich je Datei mit Begründung (`TF` neu, Wolken
als Stufe, Telegram ohne `WD`); ein Drift-Test aus S2a bleibt scharf und wird nicht gelockert.
  - Test: Drift-Test grün; Rückdreh-Gegenprobe (Erwartung auf alten Stand → Test rot).

## Geplante Tests

Nach Verhalten benannt (nicht nach Issue-Nummer), ohne Mocks, Naht nur am Transport-Aufzeichner:

- `tests/tdd/test_sms_gefuehlte_temperatur_kuerzel.py` — AC-1 bis AC-4 (Trip-Token, Nullform, Kürzung, Abgrenzung zu `FL`, Befehlsantwort, Marken)
- `tests/tdd/test_sms_einfach_roh_je_metrik.py` — AC-5 bis AC-11 (Bandgrenzen, Kanalgleichheit, Editor/Orakel-Konstante, GSM-7, Bestandsnutzer, Vorschau)
- `tests/tdd/test_telegram_rich_roh_einfach_eigenes_layout.py` — AC-12
- `tests/tdd/test_telegram_windrichtung_ohne_geisterspalte.py` — AC-13
- `tests/tdd/test_einstellung_gleich_auslieferung.py` (bestehend) — AC-14/AC-15 (Register-Endzustand, bewusstes Neu-Einfrieren)
- bestehende Invarianten-/Pin-Tests (Liste oben) auf den neuen Stand gezogen — **bewusst**, jeweils mit
  Begründung im Test-Docstring; kein Test wird gelöscht, ohne dass sein Zweck durch einen neuen abgedeckt ist.
- **Mutations-Gegenprobe (Pflicht, per String-Ersetzung mit externer Sicherungskopie):** (1) `format_mode`-
  Durchreichung entfernen → AC-5/AC-6 rot; (2) B3-Zeile auf `self._friendly_keys` zurück → AC-12 rot;
  (3) B5-Filter entfernen → AC-13 rot; (4) `TF` aus der Kürzungsreihenfolge → AC-2 rot; (5) Wolkenband-
  Grenze um 1 verschieben → AC-5/AC-7 rot; (6) `wind_chill_hourly` ohne Tiefstwert-Dedup → AC-1 rot.
  Melden, welche Verfälschung **kein** Test fängt.

## Known Limitations

- `TF` (Tiefstwert im Tagesfenster mit Uhrzeit) und `FL` (Gehzeit-Tiefst) messen dieselbe Größe
  „gefühlte Temperatur" über verschiedene Fenster; sind beide aktiv, erscheinen zwei ähnliche Werte. Offener
  Konflikt zur PO-Freigabe (siehe B1), Auflösung per B1-alt möglich.
- Die Wolken-Einfachform ist ein Vorschlag (METAR-Skala) und wird mit den ACs freigegeben; ein anderer
  Vorschlag ändert nur die Stufenwörter, nicht die Struktur.
- Ein Wolken-Wert von genau 0 % erzeugt in Roh wie Einfach kein Sample (`> 0`-Filter in `sms_trip.py`) und
  erscheint als `-`; `CLR` beginnt bei 1 %. Unverändertes Bestandsverhalten, nicht Teil von S6.
- Bestandsdaten mit gespeichertem `format_mode`/`use_friendly_format` für `thunder`/`wind_direction`/
  `sunshine`/Ampel-Größen im SMS-Layout bleiben unverändert erhalten, werden im SMS-Kanal aber nicht mehr
  ausgewertet (es gibt dort nur eine Form).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0011 (Nachtrag 2026-09-30, #2422 S6)
- **Rationale:** `TF` wird Trip-Kürzel für den Stundenwert der gefühlten Temperatur und löst „`TF` entfällt
  im Trip" (#2454 AC-6/AC-7) sowie den E7-Satz ab; eine dokumentierte Entscheidung wird nie still
  rückgängig gemacht. Kein neues ADR, weil Status und Grundsatz von ADR-0011 (eine Kürzel-Quelle, ein
  Kürzel = eine Größe) unverändert bleiben.

## Changelog

- 2026-09-30: Initial spec created (Scheibe S6, B1 V1 durch PO-Entscheid 30.09.)
- 2026-09-30: Rev. 2 nach Prüfung: SMS-Formfähigkeit je Größe an einer Produktquelle (`SMS_FORMAT_MODE_METRIC_IDS`) statt Oracle-Konstante; Einfach-Token mit Doppelpunkt (`CT:SCT@4`); CAPE-Grün an `TH:` belegt; `TF`/`FL`-Konflikt offen benannt; LoC-Override vermerkt
