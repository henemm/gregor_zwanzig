---
entity_id: fix_1660a_temp_trennung
type: module
created: 2026-08-09
updated: 2026-08-09
status: draft
version: "1.0"
tags: [metrics, sms, briefing, editor, aggregation]
---

<!-- Issue #1660 Scheibe A — Tages-Tief/Hoch/Nacht getrennt waehlbar,
     gemessen UND gefuehlt (Folge aus #1484) -->

# Temperatur-Trennung: Tages-Tief, Tages-Hoch und Nacht getrennt wählbar

## Approval

- [ ] Approved

## Purpose

Nach #1484 ist die **gemessene** Nacht-Tiefsttemperatur (`N`) eine eigene
wählbare Größe; Tages-Tief und Tages-Hoch (`K`/`D`) hängen dagegen weiterhin
gemeinsam an „Temperatur", und die **gefühlte** Seite (`FN`/`FK`/`FD`/`WC`)
hängt komplett an „Gefühlte Temperatur". PO-Auftrag #1660 (2026-08-09): alle
drei Zeitbezüge — Tages-Tief, Tages-Hoch, Nacht-Tief — sollen für gemessene
und gefühlte Temperatur unabhängig voneinander wählbar sein und in allen
Kanälen konsistent wirken.

Diese Scheibe erreicht das mit **zwei Mechanismen und ohne eine einzige neue
Bedienfläche**:

1. **Nacht-Abspaltung gefühlt:** neuer Katalogeintrag `wind_chill_night`,
   exakt nach dem Muster von `temperature_night` (#1484). Das Kürzel `FN`
   wandert von `wind_chill` zur neuen Größe; `WC` bleibt bei `wind_chill`.
2. **Tages-Tief ↔ Tages-Hoch über die bestehende Auswertungswahl:** die seit
   #1357 vorhandene Einzelwahl je Größe (`Spanne` / `Nur Tiefstwert` /
   `Nur Höchstwert` / `Nur Mittelwert`, gespeichert als
   `MetricConfig.aggregations`) wirkt bisher nur in der E-Mail-Kachelzeile.
   Die SMS-/Kurzform-Kette liest sie nicht und zeigt deshalb immer beide
   Token. Nach dieser Scheibe gilt: `min` gewählt ⇒ `K`, `max` gewählt ⇒ `D`;
   für die gefühlte Seite `FK`/`FD` analog.

## Source

### 1. Neuer Katalogeintrag `wind_chill_night`

- **File:** `src/app/metric_catalog.py` — neuer `MetricDefinition` direkt
  hinter `wind_chill` (heute Zeilen 151–173), gebaut **exakt** nach
  `temperature_night` (Zeilen 139–150):
  - `id="wind_chill_night"`, `label_de="Gefühlte Nacht-Tiefsttemperatur"`,
    `unit="°C"`, `dp_field="wind_chill_c"`, `category="temperature"`
  - `default_aggregations=("min",)` — dadurch liefert
    `available_aggregations()` genau eine Möglichkeit, und
    `showsAggregationChoice()` (Frontend) blendet die Auswertungswahl für
    diese Größe von selbst aus. **Keine** neue UI-Regel nötig.
  - **KEINE** `summary_fields` (⇒ keine Auswertungs-Pill, keine
    Tabellenspalte), **KEINE** `alert_metrics`/`risk_thresholds`/
    `sms_threshold`, **KEIN** `cmp`/`alert_label` — der Kälte-Alarm bleibt
    vollständig bei `temperature_cold` (#914), der `wind_chill`-Risikowert
    (`risk_thresholds={"high_lt": -20.0}`) bleibt bei `wind_chill`.
  - `compact_label="TFN"` (Telegram-Kurzübersicht-Zeile, Pendant zu `TN`)
  - `sms_code="FN"` — **kollisionsfrei geprüft** gegen alle 26 heutigen
    `sms_code`-Werte (`D N TN TF HU DP W G WD R PR TH CP SL PT CT CL CM CH
    VS SU UV HP NL SD NS`); `FN` kommt dort nicht vor. Grund für genau
    diesen Wert: er ist identisch mit dem SMS-Token-Symbol, das die Größe
    trägt — damit ist der Eintrag registerkonform im Sinne von #1435 E3b
    (bei `temperature_night` war `N` durch `temperature_cold` belegt,
    deshalb dort das Ersatzkürzel `TN`). Er wird für `carried_ids` der
    SMS-Fidelity-Vorschau gebraucht (#923b AC-4).

### 2. Kürzel-Bindung SMS

- **File:** `src/output/renderers/sms_trip.py:119-124` —
  `SMS_MULTI_SYMBOLS_BY_METRIC` aufteilen:
  `"wind_chill": ("FK", "FD", "WC")` und `"wind_chill_night": ("FN",)`.
  `"temperature": ("K","D")` und `"temperature_night": ("N",)` bleiben.
- **File:** `src/output/tokens/builder.py:262-304` — **unverändert**. Die
  Symbolliste (`N K D FN FK FD`), das Abend-Gate (`evening_only` für
  `N`/`FN`) und die Null-Form-Regel bleiben wie sie sind; gesteuert wird
  ausschließlich über `MetricSpec.enabled` je Symbol. Die Schichtgrenze
  (`output/tokens/` importiert nichts aus `src/app/`) bleibt gewahrt.
- **File:** `tests/unit/test_sms_token_symbol_register_ratchet.py:60-64` —
  die Ausnahme-Begründung `"WC: vier Kuerzel fuer eine Groesse (Register:
  TF)"` wird sachlich falsch (es sind nach der Aufteilung drei). Der
  Kommentar ist mitzuziehen; die Ausnahme selbst bleibt bestehen.

### 3. Bestandsdaten-Ableitung beim Lesen

- **File:** `src/app/loader.py:800-816` — **hier** sitzt die #1484-Ableitung
  (NICHT in `trip_metric_ids.py`; das Kontext-Dokument nennt die falsche
  Datei). Zweiter, baugleicher Block für `wind_chill_night`:
  fehlt der Eintrag in `display_config.metrics[]`, wird er mit
  `enabled=<Zustand von wind_chill>`, `aggregations=[]`, `bucket="secondary"`,
  `derived=True` ergänzt — und **nur dann**, wenn überhaupt ein
  `wind_chill`-Eintrag existiert (leere Liste = Altbestand Fall A, bleibt
  leer; Roundtrip-Invarianz).
- **File:** `src/app/models.py` — `MetricConfig.derived` existiert bereits
  (#1484), keine Modelländerung nötig. Der Filter, der abgeleitete Einträge
  vom Zurückschreiben ausnimmt (`loader.py:1302` und `:1507`,
  `getattr(mc, "derived", False)`), ist **generisch** und greift für den
  neuen Eintrag automatisch — hier ist nichts zu ergänzen, aber AC-8 muss
  es messen statt es anzunehmen.

### 4. Nacht-Datenbeschaffung

- **File:** `src/services/segment_weather.py:395-407` —
  `night_weather_needed(dc)` zusätzlich um
  `dc.is_metric_enabled("wind_chill_night")` erweitern. Sonst zeigt die
  Vorschau ein `FN`, das still auf den Gehzeit-Tiefstwert zurückfällt
  (`sms_trip.py:249-252`), während der Versand den echten Nachtwert trägt.

### 5. Abend-Untergrenze E-Mail-Kurzzusammenfassung und Telegram

- **File:** `src/output/renderers/compact_summary.py:171-203` — heute hängt
  der gefühlte Teil ausschließlich an `"wind_chill" in enabled` und reicht
  `night_wind_chill_min_c` unbedingt durch. Nach dem Muster der gemessenen
  Seite (Zeilen 172-190): `felt_night_selected = "wind_chill_night" in
  enabled`; Nachtwert nur dann durchreichen; ist **nur** die Nachtgröße
  gewählt, entsteht die Einzelangabe über denselben Formatierer ohne
  Tages-Aggregat (`elif`-Zweig analog Zeile 183-190).
- **File:** `src/output/renderers/narrow.py:501-522` und `:714-735` — zwei
  Stellen: (a) `_overview_line()` bindet die Abend-Untergrenze für
  `metric_id == "wind_chill"` an `night_wind_chill_min_c`; das muss vom
  Gewähltsein von `wind_chill_night` abhängen. (b) Die Schleife ab Zeile 720
  braucht einen zweiten Zweig wie den für `temperature_night`: ist
  `wind_chill` abgewählt und `wind_chill_night` gewählt, entsteht abends eine
  eigene Zeile mit `compact_label` + Wert.

### 6. Aggregations-Gate für K/D und FK/FD (SMS-Kette)

- **File:** `src/output/renderers/trip_report.py:285-333` — die Menge der
  SMS-Metriken kommt weiter aus der Kanal-Kaskade
  (`_dc_uncollapsed.get_metrics_for_channel("sms", report_type)`, #1575
  Scheibe 3). Die **Auswertungswahl** wird — wie schon `sms_threshold`
  zwei Zeilen darüber (KL-4 aus #1575) — aus der **globalen** Metrikliste
  `_global_metrics = {mc.metric_id: mc for mc in _dc_uncollapsed.metrics}`
  gelesen, nicht aus dem Kanal-Layout. Siehe DEC-2.
  Die bestehende Zeile
  `MetricSpec(symbol=sym, enabled=metric_id in active_metric_ids)` bekommt
  einen zweiten Faktor: für die vier Tages-Symbole zusätzlich das
  Aggregations-Gate, für `N`/`FN` nicht (eigene Metriken, eigene Auswahl).
- **File:** `src/output/renderers/email/html.py:1428-1431` — Referenzmuster
  für das Lesen (`{mc.metric_id: mc.aggregations for mc in dc.metrics if
  mc.enabled}`); **unverändert**, nur als Vorbild zitiert.

### 7. Vier Stellen mit `temperature_night`-Sonderbehandlung (mitzuziehen)

Der neue Eintrag ist wie `temperature_night` ein **Nachtfenster-Skalar**, kein
Stundenwert. Ohne diese vier Ergänzungen erscheint eine Tabellenspalte
„Gefühlte Nacht" mit Stundenwerten, die es gar nicht gibt:

| File | Was |
|------|-----|
| `src/output/renderers/channel_layout.py:88` | Filter `!= "temperature_night"` → Menge `{"temperature_night","wind_chill_night"}` |
| `src/output/renderers/email/helpers.py:97` | `NO_HOURLY_COLUMN_METRIC_IDS` um `wind_chill_night` |
| `src/output/renderers/compare_hourly_metric_ids.py:59` | `HOURLY_EXCLUDED_METRIC_IDS` um `wind_chill_night` |
| `src/output/renderers/compare_hourly_metric_ids.py:70-73` | `HOURLY_EXCLUSION_REASON` — Begründungstext für die Bedienfläche |

### 8. Parität / Frontend

- **Frontend:** KEINE neue Komponente, KEINE Änderung an
  `frontend/src/lib/components/shared/weather-metrics-tab/aggregationSelection.ts`.
  `WeatherMetricsTab` lädt den Katalog aus `GET /api/metrics`; der neue
  Eintrag erscheint automatisch als Ankreuzfeld in der Temperatur-Kategorie.
  Die Ausschlussliste `corridorEditorState.ts` braucht keinen Eintrag —
  ohne `alert_metrics` taucht die Größe im Alarm-Mapping gar nicht auf
  (bei #1484 vom Adversary belegt).
- **File:** `internal/model/alert_metric_mapping.generated.json` — kein
  `alert_metrics` ⇒ **kein** neuer Eintrag; der Paritätstest
  (`test_alert_metric_mapping_parity.py`) muss ohne Regenerierung grün
  bleiben. Läuft er rot, ist am Katalogeintrag zu viel deklariert.

## Estimated Scope

- **LoC:** ~100–140 produktiv über zwei Mechanismen (Katalogeintrag ~18,
  Kürzel-Tabelle 3, Bestandsableitung ~13, `night_weather_needed` 3,
  `compact_summary` ~14, `narrow` zwei Stellen ~20, vier
  Sonderbehandlungs-Listen ~10, Aggregations-Gate `trip_report` ~20,
  Ratschen-Kommentar 3)
- **Files:** ~11 produktiv
- **Effort:** medium–high

> **⚠️ LoC-Limit:** Produktiv bleibt der Schnitt unter 250. **Mit den Tests
> zu 14 Akzeptanzkriterien** (zwei Kanalseiten, beide Ableitungsrichtungen,
> Zwei-Nutzer-Fall, Golden-Mail) ist das Gesamt-Delta realistisch bei
> **300–400 LoC**. Ein `workflow.py set-field loc_limit_override 500` wird
> voraussichtlich gebraucht — er ist **vorab beim PO einzuholen**
> (CLAUDE.md: kein LoC-Override ohne Erlaubnis), nicht erst bei der
> Blockade. Alternative, falls der PO den Schnitt kleiner will: Mechanismus 1
> (gefühlte Nacht) und Mechanismus 2 (Aggregations-Gate) als zwei getrennte
> Workflows fahren — sie sind technisch unabhängig.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `feat_1484_night_temp_metric` | Spec | Blaupause; hebt dort Abgrenzung 1 auf |
| `night_temp_evening_only` | Spec | Abend-Gate (DEC-1/DEC-2) bleibt unverändert |
| `trip_aggregation_selection` (#1357) | Spec | Quelle der Auswertungswahl (UI + Persistenz) |
| Kanal-Kaskade #429/#434/#1575 | Feature | liefert die SMS-Metrikmenge |
| `day_window.night_wind_chill_min_c` | Funktion | Wertquelle für `FN` |
| `sms_format` | Spec | Token-Grammatik v2.x |

## Entscheidungen (DEC)

### DEC-1 — „Nur Mittelwert" entfernt in der SMS beide Tages-Token

Die Auswertungswahl ist seit #1357 eine **Einzelwahl** (PO 2026-07-28: „Es
gibt kein zusätzlich: entweder oder"). Für „Temperatur" ist `Nur Mittelwert`
(`aggregations=["avg"]`) wählbar — die SMS kennt aber kein Mittelwert-Token.

**Entscheidung:** `avg` wird ignoriert; sind weder `min` noch `max` gewählt,
entfallen `K` **und** `D`. Wer ausdrücklich nur den Mittelwert will, will
weder Tief noch Hoch — die E-Mail zeigt in dem Fall genau den Mittelwert-Pill,
die SMS zeigt für diese Größe nichts. **Kein** Rückfall auf die Spanne: ein
Rückfall würde die bewusste Wahl stillschweigend überstimmen.

*Für „Gefühlte Temperatur" stellt sich die Frage nicht — der Katalog führt
dort kein `avg`, also bietet die Oberfläche „Nur Mittelwert" gar nicht an.*

### DEC-2 — Die Auswertungswahl ist eine globale Größe, kein Kanal-Layout-Feld

`get_metrics_for_channel("sms", …)` kann `MetricConfig`-Objekte aus einem
gespeicherten SMS-Kanal-Layout liefern. Kanal-Layouts führen **keine**
Auswertungswahl; ihre `aggregations` fallen beim Laden auf den Default
`["min","max"]` zurück (`loader.py:841/874`). Läse das Gate aus der Kaskade,
wäre die Abwahl bei jedem Trip mit SMS-Kanal-Layout **wirkungslos** — ein
lautloser Fehlschlag.

**Entscheidung:** Menge der Metriken aus der Kaskade, Auswertungswahl aus der
globalen Liste `_dc_uncollapsed.metrics`. Das ist exakt das Muster, das
`sms_threshold` in derselben Funktion bereits verwendet (KL-4, #1575), und es
hält SMS und E-Mail auf **derselben** Quelle (`html.py:1428` liest ebenfalls
`dc.metrics`).

## Bestandsdaten (PFLICHT-Regel aus CLAUDE.md)

Zwei getrennte Bestandsfragen, beide **ohne Migrationslauf, ohne Replace**:

1. **`wind_chill_night` fehlt im gespeicherten Config** ⇒ die Größe gilt als
   aktiviert **genau dann, wenn `wind_chill` aktiviert ist**. Das heutige
   Verhalten (`FN` hängt an der gefühlten Temperatur) bleibt für Altbestand
   exakt erhalten. Erst ein bewusster Editor-Save materialisiert den
   expliziten Eintrag — über den bestehenden Merge-Pfad
   (`weather_config.go: mergeConfigMap`).
2. **`aggregations` fehlt im gespeicherten Config** ⇒ `["min","max"]`
   (`loader.py:787`) ⇒ `K`+`D` bzw. `FK`+`FD` erscheinen weiter beide.
   Auch der Migrationspfad `loader.py:957` schreibt die Katalog-Vorgabe
   (`temperature`: `min,max,avg`), enthält also min und max. **Kein
   Bestands-Trip verliert durch diesen Schnitt ein Token** — nur eine
   bewusste Abwahl im Editor entfernt eines.

Trips ganz ohne `display_config` brauchen keine Sonderbehandlung: sie erhalten
`build_default_display_config[_for_profile]`, das den neuen Eintrag über den
Katalog-Default (`default_enabled=True`) mitführt.

## Abgrenzungen (bewusst NICHT in dieser Scheibe)

1. **`WC` bleibt bei `wind_chill`.** Die Wintersport-Kennzahl ist ein
   Tageswert; ein Umhängen an die Nachtgröße wäre Regression #1450.
2. **Keine Alarm-/Grenzwert-Funktion für `wind_chill_night`** — keine
   `alert_metrics`, kein `sms_threshold`, kein `risk_thresholds`, nicht im
   Korridor-Editor. Der Kältealarm bleibt bei `temperature_cold` (#914), der
   gefühlte Risikowert bei `wind_chill`.
3. **E-Mail-Nacht-Stundentabelle bleibt an `show_night_block`.** Sie ist eine
   Tabellensektion mit eigenem Bedienelement, keine Metrik-Spalte.
4. **Ortsvergleich: keine Sonderbehandlung** außer dem Stundenverlauf-
   Ausschluss (Punkt 7 oben). Gleichziehen ist #1463.
5. **Teil B von #1660 (fehlende Token) ist NICHT enthalten** — das ist ein
   eigener Schnitt.
6. **Keine neue Bedienfläche.** Weder eine Tief/Hoch-Auswahl neben der
   Metrik-Auswahl noch eine Änderung an `aggregationSelection.ts`. Wird im
   Verlauf der Umsetzung eine neue UI-Fläche nötig, ist das ein Stopp-Grund
   und keine Erweiterung des Schnitts (PO-Vorgabe #1660).
7. **Die `?`-/Null-Form-Logik aus #1415/#1483 bleibt unverändert**
   (Datenlücke bei gewählter Größe ⇒ `FN-` bzw. `?`, abgewählt ⇒ Token
   entfällt ganz).

## Expected Behavior

- **Input:** Metrik-Auswahl (Reiter Wertebereiche) für „Temperatur",
  „Nacht-Tiefsttemperatur", „Gefühlte Temperatur", „Gefühlte
  Nacht-Tiefsttemperatur" — jeweils an/aus; dazu die Auswertungswahl je
  Tagesgröße (Spanne / nur Tiefstwert / nur Höchstwert / nur Mittelwert).
- **Output:** Sechs Temperatur-Token der SMS/Telegram-Kurzform erscheinen
  unabhängig voneinander: `N` an `temperature_night`, `FN` an
  `wind_chill_night`, `K`/`D` an `temperature` **und** deren
  Auswertungswahl, `FK`/`FD` an `wind_chill` **und** deren Auswertungswahl.
  E-Mail-Kurzzusammenfassung und Telegram-Abendübersicht folgen derselben
  Auswahl.
- **Side effects:** Nacht-Wetterabruf wird auch dann ausgelöst, wenn nur
  `wind_chill_night` (ohne `show_night_block`) gewählt ist.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit gewählter „Gefühlter Temperatur" und abgewählter „Gefühlter Nacht-Tiefsttemperatur" / When das Abend-Briefing als SMS erzeugt wird / Then enthält die SMS `FK`, `FD` und `WC`, aber kein `FN`-Token.
  - Test: SMS-Rendering mit realistischem Forecast-Fixture (Nachtwert ≠ Tageswert), Assertion auf die Token-Menge.

- **AC-2:** Given ein Trip mit gewählter „Gefühlter Nacht-Tiefsttemperatur" und abgewählter „Gefühlter Temperatur" / When das Abend-Briefing als SMS erzeugt wird / Then enthält die SMS `FN` mit dem Wert aus dem Nachtfenster (Ankunft→06:00), aber weder `FK` noch `FD` noch `WC`.
  - Test: wie AC-1, umgekehrte Auswahl; der geprüfte Zahlenwert stammt aus dem Nachtfenster, nicht aus dem Gehzeit-Aggregat.

- **AC-3:** Given ein Trip mit gewählter „Gefühlter Nacht-Tiefsttemperatur" / When das Morgen-Briefing erzeugt wird / Then erscheint kein `FN` — das bestehende Nur-Abends-Gate wirkt unverändert weiter.
  - Test: Morgen-Rendering, Assertion auf Abwesenheit von `FN`; die bestehende Suite zum Abend-Gate bleibt grün.

- **AC-4:** Given ein Trip mit gewählter „Temperatur" und der Auswertungswahl „Nur Höchstwert" / When das Briefing als SMS erzeugt wird / Then enthält die SMS `D`, aber kein `K` — und ein zusätzlich gewähltes `N` bleibt davon unberührt sichtbar.
  - Test: SMS-Rendering mit `aggregations=["max"]` auf `temperature`, Assertion auf `D` vorhanden / `K` abwesend / `N` vorhanden (Abend).

- **AC-5:** Given ein Trip mit gewählter „Gefühlter Temperatur" und der Auswertungswahl „Nur Tiefstwert" / When das Briefing als SMS erzeugt wird / Then enthält die SMS `FK`, aber kein `FD` — und ein zusätzlich gewähltes `FN` bleibt unberührt sichtbar.
  - Test: SMS-Rendering mit `aggregations=["min"]` auf `wind_chill`, Assertion auf alle drei Symbole einzeln.

- **AC-6:** Given ein Trip mit der Auswertungswahl „Nur Höchstwert" für „Temperatur" **und** einem gespeicherten SMS-Kanal-Layout (`channel_layouts.sms`) / When das Briefing als SMS erzeugt wird / Then wirkt die Abwahl trotzdem: die SMS enthält `D`, aber kein `K`.
  - Test: Trip-Fixture mit befülltem `channel_layouts.sms` (dessen Einträge tragen keine `aggregations`), Rendering, Assertion auf `K` abwesend. *Dieser Test ist der Wächter für DEC-2 — ohne ihn wäre das Gate bei jedem kanal-konfigurierten Trip wirkungslos, ohne dass irgendetwas rot würde.*

- **AC-7:** Given ein Trip mit gewählter „Temperatur" und der Auswertungswahl „Nur Mittelwert" / When das Briefing als SMS erzeugt wird / Then enthält die SMS weder `K` noch `D`; die Abend-E-Mail zeigt für diese Größe weiterhin den Mittelwert.
  - Test: SMS-Rendering mit `aggregations=["avg"]`, Assertion auf beide Symbole abwesend; dazu ein E-Mail-Rendering, das den Mittelwert-Pill weiterhin nachweist (DEC-1, kein stiller Totalverlust der Größe über alle Kanäle).

- **AC-8:** Given ein gespeicherter Bestands-Trip mit aktivierter „Gefühlter Temperatur" und **ohne** `wind_chill_night`-Eintrag / When der Trip geladen und das Abend-Briefing erzeugt wird / Then erscheint `FN` genau wie vor der Änderung, und ein anschließender Config-Save erhält alle übrigen `display_config`-Felder (Merge, kein Replace, kein Zurückschreiben des abgeleiteten Eintrags).
  - Test: Roundtrip mit echtem Bestands-JSON-Fixture (Format wie `data/users/<uid>/trips/*.json`); geprüft wird sowohl das gerenderte Token als auch die gespeicherte Datei nach dem Save.

- **AC-9:** Given ein gespeicherter Bestands-Trip mit **deaktivierter** „Gefühlter Temperatur" / When der Trip geladen wird / Then ist „Gefühlte Nacht-Tiefsttemperatur" abgeleitet AUS — es taucht kein neues Token unangefordert im Briefing auf.
  - Test: Ableitung beide Richtungen, zusätzlich der Fall „Metrikliste komplett leer" (Altbestand ohne `display_config`) — dort wird **kein** Eintrag erfunden.

- **AC-10:** Given „Gefühlte Nacht-Tiefsttemperatur" abgewählt und „Gefühlte Temperatur" gewählt / When die Abend-E-Mail-Kurzzusammenfassung und die Telegram-Abendübersicht erzeugt werden / Then erscheint dort keine gefühlte Nacht-Untergrenze, sondern der Gehzeit-Tiefstwert; bei umgekehrter Auswahl erscheint abends eine eigene Zeile mit dem Nachtwert — in beiden Kanälen.
  - Test: `compact_summary`- und `narrow`-Rendering, beide Auswahlrichtungen, Vergleich der Zahlenwerte (Nachtwert ≠ Gehzeit-Tiefstwert im Fixture, sonst beweist der Test nichts).

- **AC-11:** Given „Gefühlte Nacht-Tiefsttemperatur" gewählt und die Nacht-Stundentabelle (`show_night_block`) ausgeschaltet / When das Abend-Briefing über den Vorschau-Pfad erzeugt wird / Then zeigt `FN` das echte Nacht-Minimum, nicht still den Gehzeit-Tiefstwert.
  - Test: Vorschau-/Scheduler-Pfad mit `show_night_block=False`, Fixture mit deutlich abweichendem Nachtwert, Assertion auf den Nachtwert.

- **AC-12:** Given der Metrik-Katalog / When `GET /api/metrics` abgerufen wird / Then enthält die Antwort „Gefühlte Nacht-Tiefsttemperatur" als wählbare Größe der Temperatur-Kategorie; sie erscheint in **keiner** Stundentabelle (Trip-E-Mail wie Ortsvergleich), in **keinem** Kanal-Spaltenlayout und in **keinem** Alarm-Mapping.
  - Test: API-Test gegen den Router (FastAPI TestClient) plus je eine Assertion gegen `render_for_channel()`, den Trip-Zeilenbauer und `internal/model/alert_metric_mapping.generated.json` (Paritätstest bleibt ohne Regenerierung grün).

- **AC-13:** Given ein Trip mit unveränderten Vorgabe-Auswertungen (`min`+`max`) und ohne explizite Nacht-Einträge / When Trip-Briefing-E-Mail und SMS erzeugt werden / Then sind sie **zeichengleich** zum Stand vor dieser Änderung.
  - Test: bestehende Golden-Mail-Tests bleiben bit-identisch grün; zusätzlich ein SMS-Vergleich gegen den erwarteten Token-String. *Das ist der Bestandsschutz-Nachweis: der Schnitt ändert nur, was jemand bewusst abwählt.*

- **AC-14:** Given zwei verschiedene Nutzer mit entgegengesetzter Auswahl (Nutzer A: nur gefühlte Nacht, Auswertungswahl „Nur Höchstwert"; Nutzer B: nur gefühlter Tag, Auswertungswahl „Spanne") / When beide ihr Abend-Briefing erzeugen / Then wirkt jeweils nur die eigene Auswahl — keine Vermischung über `user_id`-Grenzen.
  - Test: zwei User-Verzeichnisse unter `data/users/<uid>/`, zwei Renderings im selben Prozess, gegenläufige Assertions auf allen sechs Temperatur-Token.

## Known Limitations

- Die SMS kann keinen Tages-Mittelwert darstellen; „Nur Mittelwert" ist dort
  gleichbedeutend mit „kein Temperatur-Token" (DEC-1). Wer das anders will,
  braucht ein neues Token — außerhalb dieses Schnitts.
- Die Auswertungswahl bleibt eine **globale** Größe je Metrik (DEC-2). Eine
  pro-Kanal unterschiedliche Auswertung ist damit weiterhin nicht möglich.
- `compact_label="TFN"` ist drei Zeichen lang; die Katalogkonvention nennt
  „1–2 Großbuchstaben" für `sms_code` (dort: `FN`, zwei Zeichen), nicht für
  `compact_label`. Falls ein bestehender Test die Länge des `compact_label`
  prüft, ist `TF-N` **keine** Ausweichlösung — dann ist die Konvention im
  Katalog zu klären, nicht der Wert zu verbiegen.
- Die Kürzel-Ratsche behält ihre `wind_chill_c`-Ausnahme; sie bewacht die
  vier bzw. drei Kürzel dieser Größe weiterhin nicht gegen das Register.

## Prüfhinweis für den Adversary

Leitfrage aus CLAUDE.md: **Ist die Zusicherung dort geprüft, wo sie WIRKT —
oder nur dort, wo der Code steht?** Die vier Stellen, an denen hier ein
grüner Testlauf ohne Wirkung entstehen kann:

1. **AC-6 / DEC-2 (Quelle der Auswertungswahl).** Ein Test ohne
   `channel_layouts.sms` im Fixture ist grün, egal ob das Gate aus der
   Kaskade oder aus der globalen Liste liest. Erst das befüllte Kanal-Layout
   trennt richtig von falsch.
2. **AC-11 (Datenbeschaffung).** Ein Fixture, in dem Nachtwert und
   Gehzeit-Tiefstwert zufällig gleich sind, beweist nichts.
3. **AC-8/AC-9 (Ableitung beim Lesen).** Prüfen, dass die Ableitung im
   **Ladepfad** (`loader.py`) wirkt und nicht nur im Katalog-Default —
   ein Test, der `MetricConfig` von Hand baut, umgeht genau die Stelle.
4. **AC-13 (Bestandsschutz).** Golden-Vergleiche müssen den **gerenderten
   Text** vergleichen, nicht die Konfiguration.

**Mutations-Gegenproben (Pflicht, per String-Ersetzung mit externer
Sicherungskopie — nie `git checkout/stash/reset`):**

- `SMS_MULTI_SYMBOLS_BY_METRIC["wind_chill"]` zurück auf
  `("FN","FK","FD","WC")` drehen und den `wind_chill_night`-Eintrag
  entfernen — welcher Test wird rot?
- Im Aggregations-Gate `"min"` und `"max"` vertauschen (K an max, D an min)
  — fängt das ein Test, oder prüfen alle nur „ein Token weniger"?
- Die Aggregations-Quelle von `_dc_uncollapsed.metrics` auf die
  Kanal-Kaskade umstellen — bleibt alles grün? Dann fehlt AC-6.
- Das Gate zusätzlich auf `N`/`FN` anwenden (die abgeleiteten Nacht-Einträge
  tragen `aggregations=[]`) — die Nacht-Token müssten verschwinden; fängt
  das ein Test?
- `night_weather_needed()` auf den Stand vor der Änderung zurücksetzen —
  wird AC-11 rot, oder fällt `FN` still auf den Tageswert?
- In `channel_layout.py` den `wind_chill_night`-Filter entfernen — entsteht
  eine Geisterspalte, die kein Test bemerkt?

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Der Schnitt folgt zwei bereits getroffenen Entscheidungen
  (#1484 Nacht-Abspaltung, #1357 Auswertungswahl) und schafft keine neue
  Entscheidungsfläche. Er hebt lediglich Abgrenzung 1 aus
  `feat_1484_night_temp_metric.md` planmäßig auf — dort ausdrücklich als
  Folgeschnitt vorgesehen.

## Changelog

- 2026-08-09: Initial spec created (Issue #1660 Scheibe A)
