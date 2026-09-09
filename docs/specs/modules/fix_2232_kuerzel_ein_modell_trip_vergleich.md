---
entity_id: fix_2232_kuerzel_ein_modell_trip_vergleich
type: module
created: 2026-09-09
updated: 2026-09-09
status: draft
version: "2.0"
tags: [backend, frontend, metrik-kaskade, kuerzel, sms, compare, adr-0011, issue-2232]
---

# #2232 — Ein Modell, eine Kürzel-Quelle, ein Vokabular für Trip- und Vergleichs-SMS (Temperatur-Familie)

## Approval

- [ ] Approved — Rev. 2 nach Developer-Befund (2026-09-09), ACs erneut zur Freigabe

**Historie:**

- Rev. 1: [x] Approved — PO, 2026-09-09 („go"), ohne Einschränkung. Damit entschieden:
  Entscheidungspunkt 4 — der Zusatz „(Gehzeit)" wird aus `label_de` der vier Größen
  gestrichen (Empfehlung angenommen). **Durch Befund B1–B5 überholt; Label-Entscheid
  revidiert (siehe „Befund der Umsetzung" unten).**

## Purpose

Der Editor zeigt im Ortsvergleich für Tageshöchst- und Tagestiefsttemperatur zweimal die
Marke `D`, die zugestellte Vergleichs-SMS sendet `D+24 D-9`, während die Trip-Briefing-SMS
für dieselben Größen `L`/`D` sendet. Diese Scheibe beseitigt die Ursache — zwei
unterschiedliche Modellierungen derselben Wettergröße — statt nur die Anzeige zu flicken,
und macht Trip und Ortsvergleich für die Temperatur-Familie zu **einem** Modell mit
**einer** Kürzel-Quelle.

## Source

- Issue #2232, Kind von Epic #2259 (Elternteil)
- Tech-Lead-Zielbild, PO-go 2026-09-09 (dieser Spec-Freigabe-Punkt, Rev. 1)
- Tech-Lead-Entscheid Rev. 2 „Weg A" (2026-09-09) nach Developer-Messung von Rev.-1-Detail-1
- Vorgänger: ADR-0011 Nachtrag E7 (2026-08-15, „bewusst verschieden") — mit dieser Scheibe
  für die Temperatur-Familie widerrufen; Spec `fix_1719_s4_kuerzel_vereinheitlichung.md`
  Requirement 3 („Die Quelle richtet sich nach der Fläche") — mit dieser Scheibe abgelöst
- Bezug: Epic #1230 (Datenmodell-Konvergenz Trip/Ortsvergleich); #1848 Scheibe C
  (Gehzeit-Exklusivität, PO-Entscheid 2026-08-19)
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

## Befund der Umsetzung (Rev. 1 → Rev. 2)

Der Developer hat Implementation Detail 1 aus Rev. 1 (Vergleichs-`metric_id` auf das
Trip-Modell umstellen) experimentell angewandt und gemessen: **101 zusätzlich rote
Tests.** Ursache: `metric_id` ist nicht nur Kürzel-Identität, sondern zugleich
Auflösungs-Identität für Wert, Fenster, Alarm, Ausblick und Persistenz — dort wirkt eine
Änderung an anderer Stelle, als sie gedacht war.

- **B1** — `tests/unit/test_gehzeit_metriken_bleiben_trip_exklusiv.py:53-57` (#1848
  Scheibe C, PO-Entscheid 2026-08-19) hält fest, dass `temperature_day_low/_high`,
  `wind_chill_day_low/_high` dem Trip vorbehalten sind und im Ortsvergleich NIE als
  Kennung angeboten werden; sein AC-4 verlangt den Zusatz „(Gehzeit)" in `label_de`.
  Begründung `tests/unit/test_compare_catalog_derives_from_central_catalog.py:62-83`:
  Trip fenstert über `collect_hiking_window_points()`, der Vergleich über
  `resolve_configured_window()` (04–19) — verschiedene Zahlen unter einer Kennung wären
  Falschinformation.
- **B2** — Persistenz: `display_config.active_metrics` im Paar-Format
  (`frontend/src/lib/.../compareMetricSelection.ts:102`, ADR-0037) und
  `outlook_metrics` als reine Kennung (#1848 A2) lösen sich über `key_for()`
  (`compare_metric_catalog.py:249`) und `derived_aggregations()`
  (`compare_outlook_metric_ids.py:48`) nicht mehr auf → gespeicherte Auswahl verschwindet
  (Datenverlust-Klasse #102).
- **B3** — Trip-Ausblick verliert die Temperaturspalte, weil `derived_aggregations()`
  über `summary_fields` filtert und die vier Tagesrichtungen per #1728 bewusst keine
  haben (`metric_catalog.py:175-212`); 38 Tests in `tests/tdd/test_channel_metric_matrix.py`
  + `tests/tdd/test_trip_outlook_metric_selection.py`.
- **B4** — Die Vergleichs-Mail-Spaltenköpfe kommen NICHT aus `COMPARE_METRIC_CATALOG`,
  sondern aus `CV2_METRICS` (`src/output/renderers/email/compare_html.py:322,348,361-362`),
  gelesen von `derive_row_labels()` (`:466-538`), Übersicht mit `form="long"`
  (`:804-807`). AC-9 Rev. 1 war über Detail 1 nicht erreichbar.
- **B5** — `alert_metric_for()` (`metric_catalog.py:934-942`) verlangt
  `aggregation in summary_fields` → Alarm-Identität bricht (2 Tests
  `test_alert_metric_identity_delivery.py`).

**Konsequenz:** Rev. 2 folgt dem Tech-Lead-Entscheid „Weg A" — Kürzel-Identität wird von
Auflösungs-Identität getrennt, statt sie zu vereinheitlichen. `metric_id` bleibt
unangetastet, ein neues Feld `kuerzel_metric_id` trägt ausschließlich die Kürzel-Bildung.
Details siehe „Implementation Details" unten.

## Implementation Details

**S1 (diese Scheibe, Pflicht) — Rev. 2, Weg A:**

1. **Kürzel-Identität getrennt von Auflösungs-Identität.** `metric_id` der vier
   Vergleichseinträge bleibt `temperature`/`wind_chill` — trägt weiterhin Wertberechnung,
   Alarm-Zuordnung, Ausblick-Filterung und Persistenz-Schlüssel unverändert, keine dieser
   Wirkungen ändert sich. Neu: ein explizites Feld `kuerzel_metric_id` an genau diesen
   vier Einträgen in `COMPARE_METRIC_CATALOG` (`temp_max_c → "temperature_day_high"`,
   `temp_min_c → "temperature_day_low"`, `wind_chill_max_c → "wind_chill_day_high"`,
   `wind_chill_min_c → "wind_chill_day_low"`). Dieses Feld speist ausschließlich das
   SMS-Kürzel und die Editor-Marke — nie Wert, Fenster, Alarm, Ausblick oder
   Mail-Spaltenkopf. Ein Modul-Import-Assert stellt sicher, dass jede
   `kuerzel_metric_id` im Register existiert und keine Kennung ist, die der Vergleich
   selbst anbietet — Wächter für B1 (AC-11).

2. **SMS-Kürzelbildung löst über `kuerzel_metric_id` auf.**
   `_RENDERER_TO_CATALOG_METRIC_ID` (`comparison.py:556-560`) verwendet
   `kuerzel_metric_id ?? metric_id` zur Kürzel-Auflösung; `_sms_aggregation_sign`,
   `_AMBIGUOUS_CATALOG_METRIC_IDS`, `_metric_id_occurrences` und
   `_RENDERER_TO_AGGREGATION` (`:572-600`) sowie ihr Aufruf in `_sms_metric_cell`
   (`:661`) entfallen ersatzlos. `temperature_day_high.sms_code` wechselt von `""` auf
   `"D"` (`metric_catalog.py:208`), Kommentar entsprechend anpassen.

3. **Editor-Marke aus derselben Quelle, ohne die Auflösungs-Identität zu berühren.**
   `get_compare_metric_catalog()` (`compare_metric_catalog.py:317-332`) liefert
   `kuerzel_metric_id` (Fallback `metric_id`) zusätzlich aus; die drei
   Vergleichs-Editoren (`WeatherMetricsTab.svelte:1139-1143`,
   `CompareHourlyLayoutControls.svelte:139-146,241`,
   `CompareOutlookLayoutControls.svelte:114-122,255`) schlagen die Marke in
   `/api/sms-symbols` unter dieser Kennung nach — dieselbe Quelle wie der
   Touren-Editor; `compareKuerzelById`/`hourlyKuerzelById`/`outlookKuerzelById` aus
   `sms_code` entfallen. Frontend-Test `weather_metric_kuerzel_marken.test.ts:446-500`
   wird umgedreht (beide Flächen lesen aus `/api/sms-symbols`). `/api/sms-symbols`
   (`api/routers/config.py:30-69`) muss jede Größe des Vergleichs-Katalogs führen; sonst
   Fallback auf `sms_code` **im Endpoint** (nicht im Client) — kein zweiter Helfer, kein
   zweites Vokabular im Client.

4. **Label-Entscheid REVIDIERT: „(Gehzeit)" bleibt.** Im Touren-Editor stehen
   `temperature` (Fenster 04–19, Auswertung max/min) und `temperature_day_high/low`
   (Gehzeit) nebeneinander — ohne Zusatz nicht unterscheidbar; der Wächter aus B1
   (`test_gehzeit_metriken_bleiben_trip_exklusiv.py`, PO-Entscheid 2026-08-19) verlangt
   ihn. Die Vergleichs-Mail-Spaltenköpfe bleiben unverändert
   („Temperatur Maximum"/„Temperatur Minimum") — die Vergleichsgröße IST eine andere
   Größe (Tagesfenster statt Gehzeit), ein anderer Name ist dort korrekt; nur das
   SMS-Kürzel `D`/`L` („Tageshöchst/-tiefst") ist für beide zutreffend. Der Absatz
   „Mitlaufende Folge in der Vergleichs-Mail" aus Rev. 1 entfällt ersatzlos — AC-9 kehrt
   zur byte-identischen Mail zurück.

5. **Wächter über die Wege hinweg (Kern-Test, netzfrei), unverändert zu Rev. 1.** Ein
   Test rendert dieselbe Größe einmal als Trip-Token (`build_token_line`) und einmal als
   Vergleichszelle (`_sms_metric_cell`) und verlangt dasselbe Kürzel — für alle vier
   Größen der Temperatur-Familie plus eine Stichprobe außerhalb (Wind, Regen), siehe
   AC-3.

6. **ADR-0011 bekommt einen präzisierten Nachtrag 2026-09-09 (#2232, Rev. 2).** Geteilt
   wird ab #2232 die **Kürzel-Identität** (`kuerzel_metric_id` →
   `metric_catalog.sms_code`/`sms_multi_symbols` über `/api/sms-symbols`), nicht die
   **Auflösungs-Identität** (`metric_id`, Wertberechnung, Fensterung, Alarm-Zuordnung,
   Ausblick-Filterung, Persistenz-Schlüssel) — diese bleiben je Fläche getrennt. Die
   Gehzeit-Exklusivität aus #1848 Scheibe C bleibt vollständig gewahrt: der Vergleich
   bietet weiterhin keine der vier Gehzeit-Kennungen als eigene Kennung an. Entwurf des
   Nachtrags siehe Abschnitt „Architektur-Entscheidung (ADR)" unten; die ADR-Datei selbst
   wird im Zuge der Implementierung geändert, nicht durch diese Spec.

**S2 (Folge-Scheibe, außerhalb dieser Freigabe):** siehe „Known Limitations".

## Estimated Scope

- **LoC:** ~60–90 (S1); LoC-Limit 250/Workflow gilt, Golden-Dateien und Docs zählen nicht
- **Files:** ~10
- **Effort:** medium

### Betroffene Dateien

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/output/renderers/compare_metric_catalog.py` | ändern | `kuerzel_metric_id`-Feld an den vier Einträgen ergänzen; `get_compare_metric_catalog()` gibt es aus; Modul-Import-Assert (AC-11) |
| `src/output/renderers/comparison.py` | ändern | `_RENDERER_TO_CATALOG_METRIC_ID` löst `kuerzel_metric_id ?? metric_id` auf; `_sms_aggregation_sign`, `_AMBIGUOUS_CATALOG_METRIC_IDS`, `_metric_id_occurrences`, `_RENDERER_TO_AGGREGATION` entfernen |
| `src/app/metric_catalog.py` | ändern | `temperature_day_high.sms_code` auf `"D"` setzen; Kommentar anpassen (Label bleibt „(Gehzeit)", unverändert) |
| `api/routers/config.py` | prüfen/ändern | `/api/sms-symbols` deckt jede Vergleichs-Größe über `kuerzel_metric_id` ab; Fallback auf `sms_code` im Endpoint |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | ändern | Marken-Quelle auf `/api/sms-symbols` via `kuerzel_metric_id` umstellen |
| `frontend/src/lib/components/shared/CompareHourlyLayoutControls.svelte` | ändern | dito |
| `frontend/src/lib/components/shared/CompareOutlookLayoutControls.svelte` | ändern | dito |
| `frontend/src/lib/components/shared/__tests__/weather_metric_kuerzel_marken.test.ts` | ändern | Erwartung umgedreht: beide Flächen aus `/api/sms-symbols` |
| `tests/unit/test_alert_metric_identity_delivery.py` | prüfen | bleibt unverändert grün — `metric_id` unangetastet (AC-6) |
| `tests/unit/test_sms_kuerzel_trip_gleich_vergleich.py` | neu | Wächter Trip-Kürzel == Vergleichs-Kürzel (AC-3) |
| `tests/unit/test_kuerzel_identity_guard.py` | neu | Modul-Import-Assert: `kuerzel_metric_id` darf keine im Vergleich angebotene Kennung sein (AC-11) |
| `tests/unit/test_compare_metric_selection_format_roundtrip.py` | neu | Roundtrip aller drei Bestandsformate gegen `key_for()`/`derived_aggregations()` (AC-7) |
| `docs/adr/0011-alert-render-single-backend-renderer.md` | ändern | Nachtrag präzisiert (Kürzel- vs. Auflösungs-Identität, Rev. 2) |
| `docs/specs/modules/fix_1719_s4_kuerzel_vereinheitlichung.md` | ändern | Changelog-Zeile „Req. 3 abgelöst durch #2232" |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `metric_catalog` (`src/app/metric_catalog.py`) | module | Kürzel-Register (`sms_code`, `sms_multi_symbols`), einzige Quelle je Größe |
| `compare_metric_catalog` (`src/output/renderers/compare_metric_catalog.py`) | module | Vergleichs-Katalog, trägt neu `kuerzel_metric_id` an vier Einträgen; `metric_id` unverändert |
| `comparison` (`src/output/renderers/comparison.py`) | module | Vergleichs-SMS-Renderer, `_sms_metric_cell` löst über `kuerzel_metric_id` auf |
| `compare_outlook_metric_ids` (`src/output/renderers/compare_outlook_metric_ids.py`) | module | `derived_aggregations()` bleibt unverändert, weil `metric_id` nicht angetastet wird (vermeidet B2/B3) |
| `builder` (`src/output/tokens/builder.py`) | module | Trip-SMS-Token-Erzeugung, bleibt Schichtgrenze mit Ratsche |
| `config`-Router (`api/routers/config.py`) | module | `/api/sms-symbols`, einzige Editor-Kürzel-Quelle für beide Flächen |
| `WeatherMetricsTab.svelte` + zwei Compare-Layout-Controls | module | Editor-Anzeige der Kürzel-Marken |
| ADR-0011 | decision | Grundsatzentscheidung Alert-Render, hier per präzisiertem Nachtrag korrigiert |
| Spec #1719 S4 (`fix_1719_s4_kuerzel_vereinheitlichung.md`) | spec | Requirement 3 wird für die Temperatur-Familie abgelöst |
| Epic #2259 | epic | Elternteil dieses Tickets |
| Epic #1230 | epic | Datenmodell-Konvergenz Trip/Ortsvergleich, gleiche Zielrichtung |
| #1848 Scheibe C | issue | Gehzeit-Exklusivität, PO-Entscheid 2026-08-19 — bleibt vollständig gewahrt |

## Expected Behavior

- **Input:** Ortsvergleich mit ausgewählten Metriken Tageshöchst-/Tagestiefsttemperatur
  und/oder gefühlter Höchst-/Tiefsttemperatur; Touren- und Vergleichs-Editor mit
  geöffnetem Reiter „Wetter-Metriken" bzw. den Layout-Reglern für Stundenverlauf/Ausblick.
- **Output:** Vergleichs-SMS trägt für diese Größen dieselben Kürzel wie die Trip-SMS
  (`D`, `L`, `FD`, `FL`, ohne `+`/`-`-Vorzeichen); alle Editor-Flächen zeigen dieselbe
  Marke je Größe, gespeist aus `/api/sms-symbols` über `kuerzel_metric_id`.
- **Side effects:** `_AMBIGUOUS_CATALOG_METRIC_IDS`, `_sms_aggregation_sign`,
  `_metric_id_occurrences` und `_RENDERER_TO_AGGREGATION` entfallen ersatzlos; `metric_id`
  der vier Einträge bleibt unverändert (Alarm, Ausblick, Persistenz unangetastet — B1–B5
  vermieden); ADR-0011 erhält einen präzisierten Nachtrag; Spec #1719 S4 Requirement 3
  bleibt für die Temperatur-Familie als abgelöst vermerkt; Mail- und Telegram-Rendering
  bleiben byte-identisch unverändert (SMS-/Editor-only-Änderung).

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
    ohne Änderung der 10 geprüften Keys grün. Rev. 2: trivial erfüllt, weil `metric_id`
    der vier Einträge unangetastet bleibt (Weg A) — dennoch als Regressionslauf Pflicht.

- **AC-7:** Given ein bereits gespeicherter Ortsvergleich in einem der drei
  Bestandsformate — String-Altformat (`['temp_max_c', 'temp_min_c']`), Paar-Neuformat
  (`{'temperature', 'max'}`, ADR-0037) oder `outlook_metrics`-Kennungsformat
  (`['temperature', 'wind_chill']`) — von vor dieser Scheibe / When er nach der
  Umstellung geladen und gerendert wird / Then löst jedes der drei Formate unverändert
  über `key_for()` und `derived_aggregations()` auf, die Metrik-Auswahl bleibt erhalten
  und das Rendering ist unverändert.
  - Test: `tests/unit/test_compare_metric_selection_format_roundtrip.py` — je ein
    Roundtrip pro Format: laden, `key_for()`/`derived_aggregations()` auflösen, Ausgabe
    gegen den Stand vor der Änderung vergleichen.

- **AC-8:** Given der Metrik-Katalog nach der Umstellung / When die bestehende Ratsche
  `tests/unit/test_sms_token_symbol_register_ratchet.py` läuft / Then ist
  `temperature_day_high.sms_code == "D"`, identisch zu seinem Eintrag in
  `sms_multi_symbols`, ohne dass eine neue Ausnahmezeile in der Ratsche ergänzt wurde.
  - Test: der bestehende Ratschen-Test bleibt unverändert grün — kein Eingriff in seine
    Ausnahmeliste.

- **AC-9:** Given ein Ortsvergleich mit Mail- und Telegram-Versand und gewählter
  Tageshöchst-/Tagestiefst- sowie gefühlter Höchst-/Tiefsttemperatur / When beide
  Ausgaben nach der Umstellung gerendert werden / Then sind Mail und Telegram des
  Ortsvergleichs byte-identisch zum Stand vor der Umstellung — Spaltenköpfe, Winner-Box
  und Textblöcke bleiben unverändert, weil `metric_id` unangetastet bleibt und die
  Mail-Spaltenköpfe ohnehin aus `CV2_METRICS` (`compare_html.py:322,348,361-362`),
  nicht aus `COMPARE_METRIC_CATALOG`, stammen.
  - Test: Golden-Vergleich für Mail- und Telegram-Rendering desselben Fixture-Vergleichs;
    beide Golden-Dateien bleiben byte-identisch. Zusätzlich `email_spec_validator.py`
    gegen die echte Staging-Vergleichsmail (Exit 0).

- **AC-10:** Given die drei Wächter-Tests, die bei der Umsetzung von Rev. 1 als
  zusätzlich rot aufgefallen sind (`tests/unit/test_gehzeit_metriken_bleiben_trip_exklusiv.py`,
  `tests/tdd/test_channel_metric_matrix.py`,
  `tests/tdd/test_trip_outlook_metric_selection.py`) / When Rev. 2 umgesetzt ist / Then
  bleiben alle drei ohne Änderung ihrer Erwartungen grün — der Trip-Ausblick behält die
  Temperaturspalte, und der Ortsvergleich bietet weiterhin keine der vier
  Gehzeit-Kennungen als eigene Kennung an.
  - Test: Regressionslauf der drei genannten Testdateien unverändert.

- **AC-11:** Given die vier Katalogeinträge mit `kuerzel_metric_id` / When ein
  Entwickler `kuerzel_metric_id` versehentlich auf eine Kennung setzt, die der
  Ortsvergleich selbst als wählbare Metrik anbietet / Then scheitert der Modul-Import
  mit einem Assert — der dauerhafte Wächter für Befund B1 (Gehzeit-Exklusivität).
  - Test: neuer Test `tests/unit/test_kuerzel_identity_guard.py` mutiert
    `kuerzel_metric_id` eines Eintrags testweise auf eine im Vergleichskatalog geführte
    Kennung und erwartet einen `AssertionError`/Importfehler beim (Re-)Import des Moduls.

## Non-Goals (bewusst nicht in dieser Scheibe)

- **Mail- und Telegram-Inhalte.** Bleiben byte-identisch zum Stand vor der Umstellung
  (AC-9, Rev. 2) — kein Umbau an Spaltenköpfen, Winner-Box, Matrix oder Textblöcken.
- **Alarm-Kürzel `TF`.** Bleibt für Alarm-SMS/Telegram bestehen — andere Größe
  (Stundenwert-Schwelle) als die hier umgebaute Tagesauswertung.
- **Gewitter-Grammatik (`TH:`).** Nicht Teil dieser Familie, unangetastet.
- **Nacht-Größen (`N`/`FN`).** Existieren im Ortsvergleich nicht und werden hier nicht
  eingeführt.
- **Compare-Wizard/`CompareEditor.svelte`.** Alt-Bestand, fällt gemäß Epic #1230
  ersatzlos weg — kein Umbauziel dieser Scheibe.
- **Bereichs-Token `D9/24` im Vergleich.** Siehe „Known Limitations", S2.
- **Vereinheitlichung der Auflösungs-Identität (`metric_id`).** Bewusst verworfen (Weg A
  statt Weg B) — siehe „Befund der Umsetzung" oben.

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
- **`kuerzel_metric_id` ist eine zusätzliche Indirektion.** Wer die Kürzel-Auflösung
  liest, muss künftig `kuerzel_metric_id ?? metric_id` kennen, nicht nur `metric_id` —
  bewusst in Kauf genommen, weil die Alternative (Weg B, Rev. 1) messbar teurer war
  (101 rote Tests).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0011 (Nachtrag 2026-09-09, #2232, Rev. 2)
- **Rationale:** ADR-0011 Nachtrag E7 (2026-08-15) hielt „bewusst verschiedene"
  Kürzel-Quellen für Trip und Ortsvergleich fest und wurde von Spec #1719 S4
  Requirement 3 gespiegelt. Die gemessene Nutzerauswirkung (widersprüchliche Kürzel
  `D+24 D-9` vs. `L`/`D` für dieselbe Größe) zeigt, dass diese Trennung an dieser Stelle
  keine tragfähige Grundlage war. Rev. 1 versuchte, Kürzel- und Auflösungs-Identität über
  ein gemeinsames `metric_id` zu vereinheitlichen (Implementation Detail 1) — der
  Developer hat das experimentell umgesetzt und gemessen: 101 zusätzlich rote Tests
  (B1–B5, siehe „Befund der Umsetzung" oben), weil `metric_id` in Alarm, Ausblick,
  Persistenz und Mail-Rendering an anderer Stelle wirkt als am Kürzel. Rev. 2 trennt
  beide Identitäten (Weg A): ein neues Feld `kuerzel_metric_id` trägt ausschließlich die
  Kürzel-Auflösung, `metric_id` bleibt für alles andere unangetastet. Entwurfstext für
  den Nachtrag in der ADR-Datei:

  > **Nachtrag 2026-09-09 (#2232, Rev. 2):** Nachtrag E7 („bewusst verschiedene
  > Kürzel-Quellen für Trip und Ortsvergleich") wird für die Temperatur-Familie
  > (`temperature_day_high/low`, `wind_chill_day_high/low`) widerrufen — aber nur für
  > die **Kürzel-Identität**, nicht für die Auflösungs-Identität. Trip und Ortsvergleich
  > nutzen ab #2232 für diese Größen dieselbe Kürzel-Quelle
  > (`metric_catalog.sms_code`/`sms_multi_symbols` über `/api/sms-symbols`, adressiert
  > über das neue Feld `kuerzel_metric_id` am Vergleichs-Katalogeintrag). Die
  > Auflösungs-Identität (`metric_id`, Wertberechnung, Fensterung, Alarm-Zuordnung,
  > Ausblick-Filterung, Persistenz-Schlüssel) bleibt je Fläche getrennt: der Trip
  > fenstert über `collect_hiking_window_points()` (Gehzeit), der Ortsvergleich über
  > `resolve_configured_window()` (04–19, #1848 Scheibe C) — unterschiedliche Zahlen
  > unter derselben Kennung wären Falschinformation. Die PO-Vorgabe eines
  > `+`/`-`-Vorzeichens für Vergleichs-SMS vom 2026-07-29 ist aufgehoben. Spec #1719 S4
  > Requirement 3 („Die Quelle richtet sich nach der Fläche") gilt für die Kürzel-Quelle
  > dieser Familie nicht mehr; verbleibende, weiterhin gültige Ausnahmen:
  > `wind_chill.sms_code="TF"` bleibt eine eigenständige Größe für Alarm-SMS/Telegram
  > (Stundenwert-Schwelle, keine Tagesauswertung); die Gehzeit-Exklusivität aus #1848
  > Scheibe C (`test_gehzeit_metriken_bleiben_trip_exklusiv.py`) bleibt vollständig
  > gewahrt.

  Die ADR-Datei selbst (`docs/adr/0011-alert-render-single-backend-renderer.md`) wird im
  Zuge der Implementierung geändert, nicht durch diese Spec.

## Changelog

- 2026-09-09: Initial spec created (Tech-Lead-Zielbild, PO-go zum Zielbild; ACs zur Freigabe)
- 2026-09-09: Rev. 2 — Weg A (Kürzel-Identität getrennt von Auflösungs-Identität) nach
  Messung des Developers (+101 rote Tests unter Rev.-1-Detail-1)
