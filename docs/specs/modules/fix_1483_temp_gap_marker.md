---
entity_id: fix_1483_temp_gap_marker
type: bugfix
created: 2026-08-05
updated: 2026-08-05
status: draft
version: "1.0"
tags: [sms, temperature, kurznachricht, datenluecke]
workflow: fix-1483-temp-gap-marker
---

# Fix #1483 — Temperatur-Kürzel (N/K/D/FN/FK/FD) melden eine Datenlücke nicht

## Approval

- [ ] Approved

## Purpose

In der SMS kennen die Schwellwert-Kürzel `R`/`PR`/`W`/`G`/`TH:`/`TH+:` bereits
die Unterscheidung zwischen „geprüft, nichts über der Schwelle" (`-`) und „nicht abrufbar, weil
im ausgewerteten Fenster eine Datenlücke lag" (`?`, Issue #1328). Die sechs Temperatur-Kürzel
`N`/`K`/`D`/`FN`/`FK`/`FD` kennen diese Unterscheidung nicht: Sie zeigen bei einer Datenlücke
fälschlich dieselbe `-`-Form wie bei „geprüft und unauffällig" — eine Fehl-Entwarnung, weil
Wanderer nicht erkennen können, ob die Temperatur tatsächlich geprüft wurde oder ob schlicht
keine Daten vorlagen.

## Source

- **File:** `src/output/tokens/builder.py`
- **Identifier:** `build_token_line()` (Temperatur-Schleife, Zeile ~251-284), `_mk_metric()`
  (Zeile ~120-142)

## Estimated Scope

- **LoC:** ~10-15 (Helfer-Extraktion + 2 Call-Sites) + ~30-40 (Testanpassung, zwei Testdateien)
- **Files:** 1 Code-Datei + 2 Testdateien (`tests/tdd/test_sms_unknown_on_missing_data.py`,
  `tests/unit/test_token_builder.py`) + 1 Referenz-Doku = 4
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `DailyForecast.has_data_gap` (`src/output/tokens/dto.py:45`) | DTO-Feld | Trägt das bereits berechnete Gap-Signal bis zu `build_token_line()` — keine neue Datenquelle nötig |
| `notification_service.compute_has_gap()` | Bestehender Berechnungspunkt | Einziger Ort, an dem `has_data_gap` ermittelt wird (siehe Docstrings `sms_trip.py:177`, `narrow.py:207`) — dieser Fix konsumiert den Wert nur, dupliziert ihn nicht |
| `_mk_metric()` (`builder.py:120-142`) | Bestehendes Muster | Enthält bereits die Regel `if value == "-" and has_gap: value = "?"` (Zeile 135-136) für R/PR/W/G/TH:/TH+: — Vorlage für den zu extrahierenden Helfer |
| `render_temperature()` / `render_int`-Alias (`src/output/tokens/metrics.py:70-74`) | Bestehende Formatierung | Liefert reine Zahl-oder-`-`-Strings, kennt `has_gap` bewusst nicht — bleibt unverändert |
| `_wintersport()` (`builder.py:196-222`) | Bestehender Konsument von `render_int` | MUSS unverändert bleiben — Datenlücken bei Schnee/Lawine/Windchill-Wintersport bleiben bewusst stumm (kein `?`) |
| `docs/specs/modules/fix_1482_th_plus_metrik_luecke.md` | Vorgänger-Fix | Strukturell identisches Muster (Gap→`?`-Anbindung eines zuvor nicht angeschlossenen Zweigs) — Vorlage für AC-Stil |

## Implementation Details

Gemeinsamer kleiner Helfer statt Duplikat und statt Signaturänderung an `render_temperature()`/
`render_int` (ein Default-Parameter würde jede der fünf `_wintersport()`-Aufrufstellen zwingen,
explizit `has_gap=False` mitzuschleppen — fehleranfällig und unnötig, weil dort nie ein `?`
entstehen soll):

1. Neue Funktion `_gap_or(value: str, has_gap: bool) -> str` in `src/output/tokens/builder.py`,
   extrahiert aus der bestehenden Inline-Zeile in `_mk_metric()` (Zeile 135-136): gibt `"?"`
   zurück, wenn `value == "-"` und `has_gap` wahr ist, sonst `value` unverändert.
2. `_mk_metric()` ruft `_gap_or(value, has_gap)` statt der Inline-Zeile auf — reines Refactoring,
   kein Verhaltenswechsel für R/PR/W/G/TH:/TH+:.
3. Die Temperatur-Schleife in `build_token_line()` (Zeile ~251-284, aktuell `render_temperature(val)`
   ohne Gap-Anbindung) wrappt den Aufruf zusätzlich mit `_gap_or(render_temperature(val), today.has_data_gap)`.
4. `_wintersport()` (Zeile ~196-222) bleibt UNVERÄNDERT — ruft weiterhin nackt `render_int(val)` auf.
   Diese Isolation ist strukturell garantiert (kein gemeinsamer Aufrufpfad mit `_gap_or()`), nicht
   per Default-Parameter — eine harte Anforderung, keine Nebensache.

```python
def _gap_or(value: str, has_gap: bool) -> str:
    return "?" if value == "-" and has_gap else value
```

## Expected Behavior

- **Input:** `DailyForecast` mit `has_data_gap=True` oder `False`; Temperatur-Rohwerte
  (`night_temp_min_c`/`temp_min_c`/`temp_max_c`/`night_wind_chill_min_c`/`wind_chill_min_c`/
  `wind_chill_max_c`) vorhanden oder `None`; Metrik-Auswahl (`MetricSpec.enabled`) für die
  jeweiligen Temperatur-Symbole.
- **Output:** Der SMS-Text zeigt für N/K/D/FN/FK/FD bei aktivierter Metrik,
  fehlendem Rohwert UND `has_data_gap=True` das Kürzel mit `?` statt `-`. Ohne Datenlücke bleibt
  bei fehlendem Rohwert weiterhin `-`. Abgewählte Metriken erscheinen weiterhin gar nicht.
- **Side effects:** Keine Änderung an `_wintersport()` (SD/NS24+/SL/AV/WC bleiben Zahl-oder-`-`,
  nie `?`). Keine Änderung an R/PR/W/G/TH:/TH+: (reines Refactoring dort). `narrow.py`
  (Telegram-Kurzform-Aufbau) ruft `build_token_line()` nicht auf und ist von diesem Fix nicht
  betroffen.

## Acceptance Criteria

- **AC-1:** Given eine Etappe mit aktivierten Metriken „Temperatur" und „Gefühlte Temperatur" und
  einer Datenlücke im ausgewerteten Fenster (kein Rohwert für N/K/D/FN/FK/FD ermittelbar) / When
  die Kurznachricht (SMS) für diese Etappe gerendert wird / Then zeigt der
  Text für JEDES der sechs Kürzel `N?`, `K?`, `D?`, `FN?`, `FK?`, `FD?` statt `N-`, `K-`, `D-`,
  `FN-`, `FK-`, `FD-`.
  - Test: Rendert `SMSTripFormatter().format_sms(report_type="evening", ...)` mit vollständig
    aktivierten Temperatur-/Gefühlt-Spezifikationen (kein `_TEMPERATURE_OFF`-Ausschluss) und
    Segmenten, die eine echte Datenlücke erzeugen (`_error_segment()` + `compute_has_gap()`, wie
    in `test_sms_unknown_on_missing_data.py` bereits für R/PR/W/G/TH: etabliert) — Assertion
    prüft, dass alle sechs Substrings `"N?"`, `"K?"`, `"D?"`, `"FN?"`, `"FK?"`, `"FD?"` im
    zurückgegebenen Text vorkommen und keines der sechs Kürzel mit `-` erscheint.

- **AC-2 (Abgrenzung zu AC-1):** Given dieselbe Etappe und dieselben aktivierten Metriken, aber
  OHNE Datenlücke (Wetterdaten vollständig, echt kein Temperatur-Rohwert für ein Kürzel
  vorhergesagt) / When die Kurznachricht (SMS) gerendert wird / Then zeigt der Text für dieses Kürzel
  weiterhin `-`, NICHT `?`.
  - Test: Derselbe Aufbau wie AC-1, aber mit vollständigen, fehlerfreien Segmenten
    (`_regular_segment()` ohne `_error_segment()`, `compute_has_gap()` liefert `False`) —
    Assertion prüft, dass die betroffenen Kürzel mit `-` erscheinen und `?` für keines der sechs
    Kürzel vorkommt. Ohne diese Gegenprobe wäre AC-1 nur zufällig erfüllt, weil `?` und `-` sonst
    nicht unterscheidbar geprüft wären.

- **AC-3 (Regressionsschutz #1415, WICHTIG):** Given eine Etappe mit ABGEWÄHLTER Metrik
  „Temperatur" (bzw. „Gefühlte Temperatur") UND einer Datenlücke im Fenster / When die Kurznachricht
  (SMS) gerendert wird / Then fehlt das jeweilige Kürzel vollständig im Text — weder als `-` noch als
  `?` — unabhängig davon, dass eine Datenlücke vorliegt.
  - Test: Rendert mit `disabled_specs`, die die Temperatur-Metriken ausschließen (analog
    `_TEMPERATURE_OFF` in `test_sms_unknown_on_missing_data.py`), und derselben
    Datenlücken-Fixture wie AC-1 — Assertion prüft, dass keines der Substrings `"N?"`, `"N-"`,
    `"K?"`, `"K-"`, `"D?"`, `"D-"`, `"FN?"`, `"FN-"`, `"FK?"`, `"FK-"`, `"FD?"`, `"FD-"` im Text
    vorkommt. Die Abwahl-Prüfung MUSS vor der Lücken-Prüfung greifen (Reihenfolge aus #1415 darf
    durch diesen Fix nicht umgekehrt werden).

- **AC-4 (Isolation Wintersport, PFLICHT, korrigiert nach Code-Verifikation):** Given eine Etappe
  mit einer Datenlücke im Fenster (`has_data_gap=True`) UND aktivierten Wintersport-Metriken
  (Schneehöhe/Neuschnee/Schneefallgrenze/Lawinenstufe/Windchill) / When die Kurznachricht (SMS)
  gerendert wird / Then verhalten sich die Wintersport-Kürzel `SD`/`NS24+`/`SL`/`AV`/`WC`
  UNVERÄNDERT zum Vor-Fix-Zustand: bei vorhandenem Rohwert erscheint die Zahl, bei fehlendem
  Rohwert fehlt das Kürzel VOLLSTÄNDIG (kein Token — `_wintersport()` kennt anders als
  `_mk_metric()` gar keine `-`-Nullform, sondern überspringt `val is None` komplett). In BEIDEN
  Fällen erscheint NIEMALS `?`, auch bei vorliegender Datenlücke.
  - Korrektur ggü. Erstfassung: die ursprüngliche AC-4 behauptete eine `-`-Nullform für
    Wintersport-Kürzel bei fehlendem Wert — durch direkten Aufruf von `build_token_line()`
    widerlegt (`_wintersport()`, `builder.py:196-222`: `if not _visible(...) or val is None:
    continue`, keine `-`-Zeile im Gegensatz zu `_mk_metric()`).
  - Test: Direkter, symbolgenauer Test auf `build_token_line()`-Ebene (nicht über die
    SMS-Pipeline, die diese Felder in den bestehenden Fixtures nicht populiert) — zwei
    `DailyForecast`-Instanzen mit `has_data_gap=True`, einmal mit gesetzten
    Wintersport-Rohwerten, einmal mit `None`-Rohwerten. Assertion prüft: Fall „vorhanden" zeigt
    die Zahl (`SD180` etc.), Fall „fehlend" zeigt das Kürzel gar nicht — in keinem der beiden
    Fälle kommt `"SD?"`/`"NS24+?"`/`"SL?"`/`"AV?"`/`"WC?"` im Text vor.

- **AC-5 (Zeichenbudget):** Given eine Etappe mit mehreren `?`-Kürzeln aus AC-1 / When die
  Kurznachricht (SMS) gerendert wird / Then bleibt der Text weiterhin innerhalb der 160-Zeichen-Grenze
  (§1 `docs/reference/sms_format.md`) — `?` belegt exakt eine Zeichenstelle wie zuvor `-`, es
  entsteht kein zusätzlicher Text.
  - Test: Erweitert die AC-1-Fixture (mehrere `?`-Kürzel gleichzeitig sichtbar) um eine
    `len(sms) <= 160`-Assertion, analog `TestAC4LengthBudget` in
    `test_sms_unknown_on_missing_data.py`.

- **AC-6 (Mutations-Gegenprobe, PFLICHT):** Given die Implementierung aus AC-1 bis AC-5 / When der
  Adversary in Phase 6 gezielt die Gap-Anbindung der Temperatur-Schleife verfälscht (z. B. den
  `_gap_or(...)`-Aufruf um `render_temperature(val)` entfernt bzw. durch `render_temperature(val)`
  ohne Wrapper ersetzt) / Then muss mindestens ein Test aus AC-1 an der Wirkstelle rot werden. Die
  Fehl-Entwarnung (`N-`/`K-`/`D-`/`FN-`/`FK-`/`FD-` statt `?` bei vorliegender Lücke) ist die
  sicherheitsrelevante Richtung, die geprüft sein muss — findet der Adversary eine Verfälschung,
  die kein Test fängt, ist das ein Finding, kein bestandener Lauf.
  - Test: Kein eigener Test-Fall — Pflichtvorgabe an den Adversary-Dialog in Phase 6
    (String-Ersetzung mit externer Sicherungskopie, siehe `.claude/agents/implementation-validator.md`
    Sektion „Step 3b").

## Test Plan

**Korrigiert nach Fixture-Verifikation** (empirisch mit dem aktuellen, ungefixten Code geprüft —
die Erstfassung ging von einer falschen Fixture-Kombination für AC-1 aus):

- **Wichtige Erkenntnis:** Die Temperatur-Kürzel N/K/D/FN/FK/FD werden über das GEHZEIT-Fenster
  der Etappen aggregiert (`hiking_field_min_max()`), nicht über das feste 04-19-Uhr-Tagesfenster,
  das `compute_has_gap()`/R/PR/W/G/TH: verwenden. Die ursprünglich vorgesehene Fixture
  (`_error_segment()` + `_regular_segment()`, wie `TestAC1ShowsUnknownTokenOnSegmentError`)
  erzeugt zwar `has_gap=True`, liefert aber für N/K/D über die verbleibende reguläre Etappe einen
  ECHTEN Wert (`N15 K15 D15`) — kein `-`, also auch kein `?`. Nur FN/FK/FD sind in dieser
  Mischform echt `-` (kein `wind_chill_c` in den Test-Datenpunkten). Für „alle sechs Kürzel zeigen
  `?`" (AC-1 wörtlich) braucht es zwei `_error_segment()`s (kompletter Etappenausfall).

- **`_TEMPERATURE_OFF` anpassen:** Bisher schließt diese Konstante N/K/D/FN/FK/FD/WC pauschal aus.
  Neue Tests bauen eigene, gezielt aktivierte `MetricSpec`-Listen statt der globalen
  Ausschlussliste, um bestehende Tests (die weiterhin nur R/PR/W/G/TH: prüfen) unverändert zu
  lassen.

- **Neue Testklasse `TestTemperatureShowsUnknownOnGap`** (benannt nach Verhalten, nicht nach
  Issue-Nummer):
  - `test_all_six_show_unknown_on_total_segment_failure` (AC-1): zwei `_error_segment()`s (kein
    reguläres Segment, kompletter Ausfall), `report_type="evening"`, alle sechs Temperatur-Specs
    aktiviert → erwartet `N? K? D? FN? FK? FD?`, keines der sechs mit `-`.
  - `test_found_measured_value_survives_partial_gap_while_missing_felt_becomes_unknown`
    (Ergänzung zu AC-1, schützt die „gefundener Wert wird nie zu `?`"-Regel speziell für
    Temperatur, analog `TestAC2KeepsFoundRiskDespiteGap`): ein `_error_segment()` +
    ein `_regular_segment()` (Mischform, `has_gap=True`) → `N15 K15 D15` bleiben echte Werte
    (NICHT `?`), während `FN? FK? FD?` erscheinen (echt keine Windchill-Daten in der Fixture).
  - `test_no_gap_missing_felt_temperature_stays_dash` (AC-2): zwei `_regular_segment()`s +
    `_complete_night_weather()` (`has_gap=False`) → `FN- FK- FD-` bleiben `-`, kein `?`.
  - `test_disabled_temperature_metrics_absent_despite_gap` (AC-3): dieselbe
    Totalausfall-Fixture wie AC-1, aber alle sechs Temperatur-Specs `enabled=False` → keiner der
    zwölf Substrings `N?/N-/K?/K-/D?/D-/FN?/FN-/FK?/FK-/FD?/FD-` kommt vor.
  - `test_unknown_marker_stays_within_length_budget` (AC-5): dieselbe Totalausfall-Fixture wie
    AC-1 → `len(sms) <= 160`.

- **AC-4 (Wintersport-Isolation) — eigener Test in `tests/unit/test_token_builder.py`**, NICHT in
  der SMS-Pipeline-Suite: Die bestehenden Segment-Fixtures populieren die Wintersport-Felder von
  `DailyForecast` (`snow_depth_cm` etc.) gar nicht, und `_wintersport()` kennt ohnehin keine
  `-`-Nullform (siehe korrigierte AC-4). Zwei direkte `build_token_line()`-Aufrufe mit
  `DailyForecast(has_data_gap=True, ...)`, einmal mit gesetzten, einmal mit `None`-Wintersport-
  Rohwerten (Muster wie `_build_default_line()` in derselben Datei) — Assertion: kein `?` in
  keinem der beiden Fälle.

- Keine Mocks, keine Dateiinhalt-Checks — ausschließlich reale `SegmentWeatherData`-Fixtures bzw.
  reale `DailyForecast`/`build_token_line()`-Aufrufe, wie in beiden Suiten bereits etabliert.

## Known Limitations

- `narrow.py` (Telegram-Kurzform) konstruiert seine Token parallel und ruft `build_token_line()`
  nicht auf — ist von diesem Fix strukturell nicht betroffen (korrigiert gegenüber der
  ursprünglichen Vermutung im Bug-Intake, siehe `docs/context/fix-1483-temp-gap-marker.md`
  Dependencies-Sektion).
- `cli.py` (Debug-Konsument von `build_token_line()`, Zeile ~228) erhält denselben Fix automatisch
  mit, ohne eigene Testabdeckung in dieser Spec — es ist kein Produktivpfad.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Der Fix erweitert ausschließlich ein bestehendes, etabliertes Muster
  (`DailyForecast.has_data_gap` → Gap→`?`-Regel, bereits für R/PR/W/G/TH:/TH+: etabliert,
  #1328/#1482) um den bislang nicht angeschlossenen Temperatur-Zweig. Es entsteht keine neue
  Architektur, kein neuer Kanal, keine neue Datenquelle — daher kein ADR nötig.

## Changelog

- 2026-08-05: Initial spec created
