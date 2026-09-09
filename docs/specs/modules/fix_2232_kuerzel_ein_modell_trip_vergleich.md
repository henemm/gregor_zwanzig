---
entity_id: fix_2232_kuerzel_ein_modell_trip_vergleich
type: module
created: 2026-09-09
updated: 2026-09-09
status: approved
version: "1.0"
tags: [backend, frontend, metrik-kaskade, kuerzel, sms, compare, adr-0011, issue-2232]
---

# #2232 — Ein Modell, eine Kürzel-Quelle, ein Vokabular für Trip- und Vergleichs-SMS (Temperatur-Familie)

## Approval

- [x] Approved — PO, 2026-09-09 („go"), ohne Einschränkung. Damit entschieden: **Entscheidungspunkt 4** — der Zusatz „(Gehzeit)" wird aus `label_de` der vier Größen gestrichen (Empfehlung angenommen).

## Purpose

Der Editor zeigt im Ortsvergleich für Tageshöchst- und Tagestiefsttemperatur zweimal die
Marke `D`, die zugestellte Vergleichs-SMS sendet `D+24 D-9`, während die Trip-Briefing-SMS
für dieselben Größen `L`/`D` sendet. Diese Scheibe beseitigt die Ursache — zwei
unterschiedliche Modellierungen derselben Wettergröße — statt nur die Anzeige zu flicken,
und macht Trip und Ortsvergleich für die Temperatur-Familie zu **einem** Modell mit
**einer** Kürzel-Quelle.

## Source

- Issue #2232, Kind von Epic #2259 (Elternteil)
- Tech-Lead-Zielbild, PO-go 2026-09-09 (dieser Spec-Freigabe-Punkt)
- Vorgänger: ADR-0011 Nachtrag E7 (2026-08-15, „bewusst verschieden") — mit dieser Scheibe
  für die Temperatur-Familie widerrufen; Spec `fix_1719_s4_kuerzel_vereinheitlichung.md`
  Requirement 3 („Die Quelle richtet sich nach der Fläche") — mit dieser Scheibe abgelöst
- Bezug: Epic #1230 (Datenmodell-Konvergenz Trip/Ortsvergleich)
- **File:** `src/output/renderers/compare_metric_catalog.py`
- **Identifier:** `COMPARE_METRIC_CATALOG["temp_max_c"]`, `COMPARE_METRIC_CATALOG["temp_min_c"]`

## Ist-Stand: eine Größe, zwei Modelle

Kein Renderer-Fehler, sondern eine unterschiedliche Modellierung derselben Wettergröße:

**Trip:** Tageshöchst/Tagestiefst/Nacht sind eigene Katalog-Größen —
`temperature_day_high` (`src/app/metric_catalog.py:200-212`, `sms_code=""`,
`sms_multi_symbols=("D",)`), `temperature_day_low` (`:185-193`, `sms_code="L"`),
`temperature_night` (`:171-172`, `("N",)`); gefühlt analog `wind_chill_day_high`
(`:283-291`, `sms_code="FD"`), `wind_chill_day_low` (`:272-280`, `sms_code="FL"`).
Trip-SMS-Token entstehen als Literale in `src/output/tokens/builder.py:324-330`, per
Ratsche `tests/unit/test_sms_token_symbol_register_ratchet.py` an `sms_multi_symbols`
gekettet; der Bereichs-Token `D9/24` entsteht in `builder.py:378-385`. Die
Editor-Marke des Touren-Editors kommt aus `/api/sms-symbols`
(`api/routers/config.py:30-69`) → `WeatherMetricsTab.svelte:188-191, 1558`.

**Ortsvergleich:** `COMPARE_METRIC_CATALOG` (`compare_metric_catalog.py:112-114` für
`temp_max_c`, `:124-126` für `temp_min_c`) trägt für **beide** `metric_id: "temperature"`
— unterschieden nur über `aggregation`. Ebenso `:142-147` `wind_chill_min_c`/`_max_c` →
`metric_id: "wind_chill"`. Die Kürzel-Erzeugung `_sms_metric_cell`
(`src/output/renderers/comparison.py:638-671`) nimmt `get_sms_code(catalog_id)`
(→ `temperature.sms_code="D"`, `metric_catalog.py:133`; `wind_chill.sms_code="TF"`,
`:234`) und hängt über `_sms_aggregation_sign` (`comparison.py:584-600`, `+` bei max,
`-` bei min, nur für die in `_AMBIGUOUS_CATALOG_METRIC_IDS` geführten Größen,
`:576-581`) ein Vorzeichen an. Die Editor-Marke der drei Vergleichs-Editoren
(`compareKuerzelById` aus `compareCatalog[].sms_code`,
`WeatherMetricsTab.svelte:1139-1143`, analog `CompareHourlyLayoutControls.svelte:139-146`
und `CompareOutlookLayoutControls.svelte:114-122`) kommt aus der Anreicherung in
`compare_metric_catalog.py:317-332` (`label`, `col_label`, `sms_code` aus dem Register).

Zwei Marken-Quellen sind bislang **bewusst** so festgehalten: Spec #1719 S4
Requirement 3 und ADR-0011 Nachtrag E7 (2026-08-15); der Frontend-Test
`frontend/src/lib/components/shared/__tests__/weather_metric_kuerzel_marken.test.ts:446-500`
prüft heute aktiv, dass der Vergleich **nicht** aus `/api/sms-symbols` liest. Die
PO-Vorgabe für das `+`/`-`-Vorzeichen stammt vom 2026-07-29 (`comparison.py:585-591`).

Nuance, die für die Label-Frage unten wichtig ist: `temperature_day_high/low` sind im
Trip über die Gehzeit gefenstert (`collect_hiking_window_points()`), Label
„Tages-Höchsttemperatur (Gehzeit)". Im Ortsvergleich gibt es keine Gehzeit — dort bleibt
das reine Tagesfenster (`LocationResult.temp_max`/`temp_min`, Renderer-IDs `temp_max`/
`temp_min` in `src/output/renderers/compare_metric_ids.py:21,37`, `wind_chill_min/max`
`:45-46`). Das Fenster ist eine Eigenschaft der **Fläche** (Route vorhanden oder nicht),
nicht der Größe.

## Implementation Details

**S1 (diese Scheibe, Pflicht):**

1. **Vergleichs-Katalog folgt dem Trip-Modell.** `temp_max_c.metric_id →
   "temperature_day_high"`, `temp_min_c → "temperature_day_low"`, `wind_chill_max_c →
   "wind_chill_day_high"`, `wind_chill_min_c → "wind_chill_day_low"`. `aggregation`
   bleibt als Rechenvorschrift für den Wert (Renderer-IDs und Wertberechnung
   unverändert), ist aber nicht mehr Identitätsmerkmal. Folge: `_AMBIGUOUS_CATALOG_METRIC_IDS`
   wird leer; `_sms_aggregation_sign` und alle Aufrufer werden ersatzlos entfernt — kein
   totes Sicherheitsnetz stehen lassen. **Prüfpflicht bei der Umsetzung:**
   `alert_metric_for(metric_id, aggregation)` (`compare_metric_catalog.py:304`) und
   `_SUMMARY_KEY_TO_CATALOG_ID`/`tests/unit/test_alert_metric_identity_delivery.py` —
   die Alarm-Identität (`temperature` max/min als Alarm-Metrik) muss erhalten bleiben.
   Falls die Alarm-Zuordnung über `metric_id` läuft, braucht der Katalogeintrag ein
   explizites `alert_metric_id: "temperature"` statt einer Ableitung aus der neuen
   `metric_id` — dies ist ein Umsetzungshinweis mit Prüfpflicht, keine feststehende
   Tatsache.

2. **Kürzel ausschließlich im Register.** `temperature_day_high.sms_code` wechselt von
   `""` auf `"D"` — der bisherige Grund für das Leeren („kein `get_sms_code()`-Leser")
   entfällt, weil der Vergleich das Register künftig liest. `temperature_day_low="L"`,
   `wind_chill_day_high="FD"`, `wind_chill_day_low="FL"` sind bereits gesetzt und bleiben
   unverändert. Die Literale in `builder.py` bleiben stehen (Schichtgrenze Trip-SMS), die
   Ratsche bewacht sie weiter.

3. **Editor-Marke aus EINER Quelle für beide Flächen.** Die drei Vergleichs-Editoren
   (`WeatherMetricsTab` Übersicht, `CompareHourlyLayoutControls`,
   `CompareOutlookLayoutControls`) lesen `kuerzelById` künftig aus `/api/sms-symbols`,
   genau wie der Touren-Editor; `compareKuerzelById`/`hourlyKuerzelById`/
   `outlookKuerzelById` aus `sms_code` entfallen. Der Frontend-Test-Abschnitt „Vergleich
   NICHT aus /api/sms-symbols" wird umgedreht (beide Flächen: dieselbe Quelle).
   `/api/sms-symbols` muss dafür jede Größe des Vergleichs-Katalogs führen (heute Vorrang
   `SMS_MULTI_SYMBOLS_BY_METRIC`, sonst `SMS_SYMBOL_BY_METRIC`); **Prüfpflicht:** ob alle
   23 Vergleichs-Größen dort ankommen, sonst Fallback auf `sms_code` **im Endpoint**
   (nicht im Frontend — keine zweite Kürzel-Quelle im Client).

4. **Label-Frage — Entscheidungspunkt für den PO, mit Empfehlung.** `label_de` von
   `temperature_day_high/low` und `wind_chill_day_high/low` trägt den Zusatz
   „(Gehzeit)". Im Ortsvergleich gibt es keine Gehzeit. **Empfehlung:** den Zusatz
   „(Gehzeit)" aus `label_de` streichen („Tages-Höchsttemperatur"), die Fensterung in den
   Hilfetext/die Beschreibung der Trip-Fläche verlagern — das Fenster ist eine
   Eigenschaft der Fläche, nicht der Größe. **Alternative** (abgelehnt): ein
   flächenabhängiger Label-Suffix im Frontend — das wäre eine zweite Namensquelle und
   widerspricht dem „ein Modell"-Ziel dieser Scheibe.

   **Mitlaufende Folge in der Vergleichs-Mail (gewollt):** `compare_html.py:524` nimmt
   die Spaltenüberschrift aus `col_label`/`label_de` der Register-Größe, und hängt den
   Auswertungs-Zusatz („Maximum"/„Minimum") nur an, wenn zwei Spalten denselben
   Grundnamen tragen (`:527-534`, `mehrfach`). Mit eigenen Größen je Richtung fällt
   der Zusatz von selbst weg: aus „Temp Maximum"/„Temp Minimum" wird „DayMax"/„DayMin"
   (Langform „Tages-Höchsttemperatur"/„Tages-Tiefsttemperatur"), gefühlt
   „DayMaxF"/„DayMinF" — **exakt die Spaltennamen, die die Trip-Mail für dieselben
   Größen führt.** Das ist kein Nebeneffekt, sondern das Ziel „ein Vokabular" auf dem
   Mail-Kanal. Alle übrigen Spalten und der Telegram-Text bleiben unverändert (AC-9).

5. **Wächter über die Wege hinweg (Kern-Test, netzfrei).** Ein neuer Test rendert
   dieselbe Größe einmal als Trip-Token (`build_token_line`) und einmal als
   Vergleichszelle (`_sms_metric_cell`) und verlangt dasselbe Kürzel — für alle vier
   Größen der Temperatur-Familie plus eine Stichprobe außerhalb (Wind, Regen). Diese
   Prüfung schließt genau die Lücke, die ADR-0011 Nachtrag E7 heute noch explizit
   erlaubt, und wird ab dieser Scheibe zum Pflicht-Gate.

6. **ADR-0011 bekommt einen Nachtrag 2026-09-09 (#2232).** Nachtrag E7 „bewusst
   verschieden" ist für die Temperatur-Familie widerrufen; die PO-Vorgabe `+`/`-` vom
   29.07. ist aufgehoben; Spec #1719 S4 Requirement 3 („Die Quelle richtet sich nach der
   Fläche") ist für diese Familie abgelöst. Verbleibende bewusste Ausnahme:
   `wind_chill.sms_code="TF"` bleibt ausschließlich für Alarm-SMS/Telegram
   (Stundenwert-Schwelle, eine andere Größe als `wind_chill_day_high/low`). Entwurf des
   Nachtrags siehe Abschnitt „Architektur-Entscheidung (ADR)" unten; die ADR-Datei selbst
   wird im Zuge der Implementierung geändert, nicht durch diese Spec.

**S2 (Folge-Scheibe, außerhalb dieser Freigabe):** siehe „Known Limitations".

## Estimated Scope

- **LoC:** ~120 (S1); LoC-Limit 250/Workflow gilt, Golden-Dateien und Docs zählen nicht
- **Files:** ~12
- **Effort:** medium

### Betroffene Dateien

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/output/renderers/compare_metric_catalog.py` | ändern | 4 `metric_id`-Zuordnungen auf Trip-Modell umstellen |
| `src/output/renderers/comparison.py` | ändern | `_sms_aggregation_sign`, `_AMBIGUOUS_CATALOG_METRIC_IDS`, `_RENDERER_TO_AGGREGATION` entfernen; Aufruf in `_sms_metric_cell` streichen |
| `src/app/metric_catalog.py` | ändern | `temperature_day_high.sms_code` auf `"D"` setzen; Label-Entscheid umsetzen |
| `api/routers/config.py` | prüfen/ändern | `/api/sms-symbols` deckt alle Vergleichs-Größen ab |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | ändern | Marken-Quelle auf `/api/sms-symbols` umstellen |
| `frontend/src/lib/components/shared/CompareHourlyLayoutControls.svelte` | ändern | Marken-Quelle auf `/api/sms-symbols` umstellen |
| `frontend/src/lib/components/shared/CompareOutlookLayoutControls.svelte` | ändern | Marken-Quelle auf `/api/sms-symbols` umstellen |
| `frontend/src/lib/components/shared/__tests__/weather_metric_kuerzel_marken.test.ts` | ändern | Erwartung umdrehen: beide Flächen aus `/api/sms-symbols` |
| `tests/tdd/test_compare_sms_kuerzel.py` | anpassen | Erwartungswerte auf `D`/`L`/`FD`/`FL` ohne Vorzeichen |
| `tests/golden/*` (Vergleichs-SMS mit `D+`/`D-`) | anpassen | Golden-Dateien auf neue Kürzelform |
| `tests/unit/test_alert_metric_identity_delivery.py` | prüfen | Alarm-Identität bleibt unverändert |
| `tests/unit/test_sms_kuerzel_trip_gleich_vergleich.py` | neu | Wächter Trip-Kürzel == Vergleichs-Kürzel |
| `docs/adr/0011-alert-render-single-backend-renderer.md` | ändern | Nachtrag 2026-09-09 (#2232) |
| `docs/specs/modules/fix_1719_s4_kuerzel_vereinheitlichung.md` | ändern | Changelog-Zeile „Req. 3 abgelöst durch #2232" |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `metric_catalog` (`src/app/metric_catalog.py`) | module | Kürzel-Register (`sms_code`, `sms_multi_symbols`), einzige Quelle je Größe |
| `compare_metric_catalog` (`src/output/renderers/compare_metric_catalog.py`) | module | Vergleichs-Katalog, `metric_id`-Zuordnung wird angeglichen |
| `comparison` (`src/output/renderers/comparison.py`) | module | Vergleichs-SMS-Renderer, `_sms_metric_cell` |
| `builder` (`src/output/tokens/builder.py`) | module | Trip-SMS-Token-Erzeugung, bleibt Schichtgrenze mit Ratsche |
| `config`-Router (`api/routers/config.py`) | module | `/api/sms-symbols`, einzige Editor-Kürzel-Quelle für beide Flächen |
| `WeatherMetricsTab.svelte` + zwei Compare-Layout-Controls | module | Editor-Anzeige der Kürzel-Marken |
| ADR-0011 | decision | Grundsatzentscheidung Alert-Render, hier per Nachtrag korrigiert |
| Spec #1719 S4 (`fix_1719_s4_kuerzel_vereinheitlichung.md`) | spec | Requirement 3 wird für die Temperatur-Familie abgelöst |
| Epic #2259 | epic | Elternteil dieses Tickets |
| Epic #1230 | epic | Datenmodell-Konvergenz Trip/Ortsvergleich, gleiche Zielrichtung |

## Expected Behavior

- **Input:** Ortsvergleich mit ausgewählten Metriken Tageshöchst-/Tagestiefsttemperatur
  und/oder gefühlter Höchst-/Tiefsttemperatur; Touren- und Vergleichs-Editor mit
  geöffnetem Reiter „Wetter-Metriken" bzw. den Layout-Reglern für Stundenverlauf/Ausblick.
- **Output:** Vergleichs-SMS trägt für diese Größen dieselben Kürzel wie die Trip-SMS
  (`D`, `L`, `FD`, `FL`, ohne `+`/`-`-Vorzeichen); alle Editor-Flächen zeigen dieselbe
  Marke je Größe, gespeist aus `/api/sms-symbols`.
- **Side effects:** `_AMBIGUOUS_CATALOG_METRIC_IDS` und `_sms_aggregation_sign` entfallen
  ersatzlos; ADR-0011 erhält einen Nachtrag; Spec #1719 S4 Requirement 3 wird für die
  Temperatur-Familie als abgelöst vermerkt; Mail- und Telegram-Rendering bleiben
  unverändert (SMS-/Editor-only-Änderung).

## Acceptance Criteria

- **AC-1:** Given ein Ortsvergleich mit den gewählten Metriken Tageshöchst- und
  Tagestiefsttemperatur / When die Vergleichs-SMS für einen Ort gerendert wird / Then
  zeigt die Zelle für Tageshöchst `D 24` und für Tagestiefst `L 9` — ohne `+`/`-`-Zeichen
  — und zwar in dieser Kürzel-Form für jeden Ort im Vergleich.
  - Test: Kern-Test ruft `render_compare_sms()` mit einer Fixture-`LocationResult`
    (`temp_max=24`, `temp_min=9`) auf und prüft den gerenderten SMS-Text auf `D 24` und
    `L 9`, nicht auf `D+24`/`D-9`.

- **AC-2:** Given ein Ortsvergleich mit gewählter gefühlter Höchst- und
  Tiefsttemperatur / When die Vergleichs-SMS gerendert wird / Then tragen die Zellen
  `FD` und `FL`, niemals `TF+` oder `TF-`.
  - Test: Kern-Test wie AC-1 mit Fixture-Werten für `wind_chill_max`/`wind_chill_min`;
    Assertion auf Anwesenheit von `FD`/`FL` und Abwesenheit von `TF+`/`TF-` im
    gerenderten SMS-Text.

- **AC-3:** Given dieselbe Wettergröße (Tageshöchst-, Tagestiefst-, gefühlte Höchst-,
  gefühlte Tiefsttemperatur, plus zwei Stichproben außerhalb der Familie) / When sie
  einmal als Trip-SMS-Token und einmal als Vergleichs-SMS-Zelle mit denselben Werten
  gerendert wird / Then ist das gesendete Kürzel in beiden Wegen identisch.
  - Test: neuer Wächter `tests/unit/test_sms_kuerzel_trip_gleich_vergleich.py` ruft
    `build_token_line()` und die Vergleichs-SMS-Zellenerzeugung mit denselben
    Eingabewerten auf und vergleicht die extrahierten Kürzel-Substrings gegeneinander —
    kein Abtippen erwarteter Werte, sondern Gegenüberstellung der zwei Renderpfade.

- **AC-4:** Given der Ortsvergleichs-Editor mit geöffnetem Reiter „Wetter-Metriken" /
  When der Nutzer die Zeilen Tageshöchst- und Tagestiefsttemperatur ansieht / Then trägt
  die Zeile Tageshöchst die Marke `D` und die Zeile Tagestiefst die Marke `L`, beide
  gespeist aus `/api/sms-symbols` wie im Touren-Editor.
  - Test: Frontend-Test per Svelte-AST
    (`weather_metric_kuerzel_marken.test.ts`, Erwartung umgedreht: beide Flächen lesen
    aus `/api/sms-symbols`) plus erweiterter Staging-Klickpfad
    `kuerzel-marken-sichtbar.staging.spec.ts`, der die sichtbaren Markentexte im
    geöffneten Ortsvergleichs-Editor ausliest.

- **AC-5:** Given die drei Vergleichs-Editoren Übersicht, Stundenverlauf und Ausblick /
  When dieselbe Größe (z.B. Tageshöchsttemperatur) in jedem der drei angezeigt wird /
  Then zeigen alle drei dieselbe Marke wie der Touren-Editor für dieselbe Größe.
  - Test: Staging-Klickpfad, der nacheinander durch die drei Editor-Flächen navigiert
    und den angezeigten Markentext gegen den Touren-Editor vergleicht.

- **AC-6:** Given ein Ortsvergleich mit einem konfigurierten Alarm auf
  Tageshöchsttemperatur / When die Wetterdaten den konfigurierten Schwellwert
  überschreiten / Then löst der Alarm weiterhin über die Alarm-Metrik `temperature`/`max`
  aus, unverändert zum Verhalten vor dieser Scheibe.
  - Test: bestehender Test `tests/unit/test_alert_metric_identity_delivery.py` bleibt
    ohne Änderung der 10 geprüften Keys grün; Regressionslauf nach der Umstellung der
    `metric_id`-Zuordnung.

- **AC-7:** Given ein bereits gespeicherter Ortsvergleich mit `temp_max_c`/`temp_min_c`
  in der Metrik-Auswahl (Bestandsdaten von vor dieser Scheibe) / When er nach der
  Umstellung geladen und gerendert wird / Then bleibt die Metrik-Auswahl erhalten und das
  Rendering ist unverändert — lediglich die interne `metric_id` hinter dem Auswahl-Key
  hat sich geändert.
  - Test: Roundtrip-Test mit einer Fixture-Vergleichskonfiguration im Vor-Umstellungs-
    Format: laden, rendern, Ausgabe gegen den Stand vor der Änderung vergleichen.

- **AC-8:** Given der Metrik-Katalog nach der Umstellung / When die bestehende Ratsche
  `tests/unit/test_sms_token_symbol_register_ratchet.py` läuft / Then ist
  `temperature_day_high.sms_code == "D"`, identisch zu seinem Eintrag in
  `sms_multi_symbols`, ohne dass eine neue Ausnahmezeile in der Ratsche ergänzt wurde.
  - Test: der bestehende Ratschen-Test bleibt unverändert grün — kein Eingriff in seine
    Ausnahmeliste.

- **AC-9:** Given ein Ortsvergleich mit Mail- und Telegram-Versand und gewählter
  Tageshöchst-/Tagestiefst- sowie gefühlter Höchst-/Tiefsttemperatur / When beide
  Ausgaben nach der Umstellung gerendert werden / Then tragen in der Mail genau diese
  vier Spalten die Überschriften, die die Trip-Mail für dieselben Größen führt
  (`DayMax`/`DayMin`/`DayMaxF`/`DayMinF`, Langform ohne Auswertungs-Zusatz), und alle
  übrigen Spalten, die Winner-Box sowie der gesamte Telegram-Text sind byte-identisch
  zum Stand vor der Umstellung.
  - Test: Golden-Vergleich für Mail- und Telegram-Rendering desselben Fixture-Vergleichs;
    die Mail-Golden-Datei ändert sich ausschließlich in den vier Spaltenköpfen, die
    Telegram-Golden-Datei gar nicht. Zusätzlich `email_spec_validator.py` gegen die
    echte Staging-Vergleichsmail (Exit 0).

## Non-Goals (bewusst nicht in dieser Scheibe)

- **Mail- und Telegram-Inhalte jenseits der vier Spaltenköpfe.** Telegram bleibt
  unverändert, die Mail ändert sich nur in den Überschriften der vier umgebauten
  Spalten (AC-9, Implementation Details Punkt 4). Kein Umbau an Winner-Box, Matrix
  oder Textblöcken.
- **Alarm-Kürzel `TF`.** Bleibt für Alarm-SMS/Telegram bestehen — andere Größe
  (Stundenwert-Schwelle) als die hier umgebaute Tagesauswertung.
- **Gewitter-Grammatik (`TH:`).** Nicht Teil dieser Familie, unangetastet.
- **Nacht-Größen (`N`/`FN`).** Existieren im Ortsvergleich nicht und werden hier nicht
  eingeführt.
- **Compare-Wizard/`CompareEditor.svelte`.** Alt-Bestand, fällt gemäß Epic #1230
  ersatzlos weg — kein Umbauziel dieser Scheibe.
- **Bereichs-Token `D9/24` im Vergleich.** Siehe „Known Limitations", S2.

## Known Limitations

- **S2 (Folge-Scheibe, außerhalb dieser Freigabe):** der Bereichs-Token aus
  `builder.py:378-385` (`D9/24`) wird derzeit nicht in einen geteilten Helfer gezogen —
  die Vergleichs-SMS zeigt je Ort weiterhin zwei getrennte Zellen (`D 24`, `L 9`) statt
  eines zusammengezogenen `D9/24`. Das ist eine bewusste Nicht-Ziel-Entscheidung für S1,
  keine ACs dieser Scheibe hängen daran.
- **`TF` bleibt im Alarm-Pfad** als eigenes, von der Tagesauswertung unabhängiges Kürzel
  für Stundenwert-Schwellen — keine Vereinheitlichung mit `FD`/`FL` vorgesehen.
- **Trip-Literale in `builder.py` bleiben** bewusst als Schichtgrenze bestehen, weiterhin
  über die Ratsche `test_sms_token_symbol_register_ratchet.py` an das Register gekettet,
  statt direkt aus `sms_multi_symbols` generiert zu werden.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0011 (Nachtrag 2026-09-09, #2232)
- **Rationale:** ADR-0011 Nachtrag E7 (2026-08-15) hielt „bewusst verschiedene"
  Kürzel-Quellen für Trip und Ortsvergleich fest und wurde von Spec #1719 S4
  Requirement 3 gespiegelt. Die gemessene Nutzerauswirkung (widersprüchliche Kürzel
  `D+24 D-9` vs. `L`/`D` für dieselbe Größe) zeigt, dass diese Trennung an dieser Stelle
  keine tragfähige Grundlage war, sondern eine Modellierungs-Inkonsistenz verdeckt hat.
  Entwurfstext für den Nachtrag in der ADR-Datei:

  > **Nachtrag 2026-09-09 (#2232):** Nachtrag E7 („bewusst verschiedene Kürzel-Quellen
  > für Trip und Ortsvergleich") wird für die Temperatur-Familie
  > (`temperature_day_high/low`, `wind_chill_day_high/low`) widerrufen. Trip und
  > Ortsvergleich nutzen ab #2232 für diese Größen dasselbe Katalog-Modell und dieselbe
  > Kürzel-Quelle (`metric_catalog.sms_code`/`sms_multi_symbols` über
  > `/api/sms-symbols`). Die PO-Vorgabe eines `+`/`-`-Vorzeichens für Vergleichs-SMS vom
  > 2026-07-29 ist damit aufgehoben. Spec #1719 S4 Requirement 3 („Die Quelle richtet
  > sich nach der Fläche") gilt für diese Familie nicht mehr; verbleibende, weiterhin
  > gültige Ausnahme: `wind_chill.sms_code="TF"` bleibt eine eigenständige Größe für
  > Alarm-SMS/Telegram (Stundenwert-Schwelle), keine Tagesauswertung.

  Die ADR-Datei selbst (`docs/adr/0011-alert-render-single-backend-renderer.md`) wird im
  Zuge der Implementierung geändert, nicht durch diese Spec.

## Changelog

- 2026-09-09: Initial spec created (Tech-Lead-Zielbild, PO-go zum Zielbild; ACs zur Freigabe)
