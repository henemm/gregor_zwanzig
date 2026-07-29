---
entity_id: hiking_window_single_source
type: bugfix
created: 2026-07-29
updated: 2026-07-29
status: draft
version: "1.0"
tags: [renderer, sms, telegram, compact_summary, email-pillen, hiking-window, issue-1417, issue-1146, issue-806, issue-807]
---

<!-- Issue #1417 — PO-Vorgabe woertlich: "Gehzeit darf nicht doppelt berechnet werden." -->

# Eine Gehzeit-Fenster-Quelle fuer Mail-Kachelzeile, SMS, Telegram-Kurzuebersicht und E-Mail-Kurzzusammenfassung (Issue #1417)

## Approval

- [x] Approved — PO-Freigabe 2026-07-29 (nach Praezisierung von AC-6:
      „Teilausfall verschlechtert sich nicht" statt der urspruenglichen,
      unzutreffenden Formulierung „zeigt weiterhin einen Wert")

## Purpose

Mail und Kurznachricht zeigen fuer dieselbe Etappe unterschiedliche Temperaturen
(`13–17°C` vs. `K13 D16`). Ursache sind zwei unabhaengige Berechnungen desselben
Gehzeit-Fensters mit unterschiedlicher Randstunden-Regel: `segment_weather.py`
schliesst die Ankunftsstunde des letzten Segments EXKLUSIV aus (liefert SMS,
Telegram-Kurzuebersicht ueber ihre heutige Kopie und die E-Mail-Kurzzusammenfassung),
waehrend die Mail-Kachelzeile (`_collect_hiking_window_dps`) sie seit #1146
bewusst INKLUSIV mitzaehlt. PO-Vorgabe: nicht angleichen (zwei Regeln synchron
halten), sondern auf **eine** Berechnung zurueckfuehren, aus der alle vier
Ausgaben schoepfen. Diese Spec hebt die bereits korrekte Regel aus
`_collect_hiking_window_dps` in ein geteiltes Modul (`day_window.py`) und
stellt SMS, Telegram-Kurzuebersicht und E-Mail-Kurzzusammenfassung darauf um,
statt weiter `segment.aggregated.temp_min_c/temp_max_c/wind_chill_min_c/
wind_chill_max_c` zu lesen. `segment_weather.py` selbst bleibt unangetastet
(#1329-Invariante, s. Out of Scope).

## Source

> **Schicht:** Python-Core / Domain-Backend (`src/output/renderers/...`). Kein
> Go-, kein Frontend-Anteil.

- **File:** `src/output/renderers/email/helpers.py:1598-1621`
  **Identifier:** `_collect_hiking_window_dps()` — wird nach `day_window.py`
  verschoben (unveraendertes Verhalten, nur neuer Ort + oeffentlicher Name
  `collect_hiking_window_points()`). Aufrufer `build_metrics_summary_pills()`
  (Zeile 1669) importiert die verschobene Funktion statt der lokalen.
- **File:** `src/output/renderers/day_window.py`
  **Identifier:** neue Funktionen `collect_hiking_window_points()` (verschoben)
  und `hiking_field_min_max()` (neu, kleine Ableitung `(min, max, max_ts)` aus
  einer Punktliste + Feldname — nach demselben Muster wie das bereits
  bestehende `_night_min_of_field()`, Issue #1410).
- **File:** `src/output/renderers/sms_trip.py:139-172`
  **Identifier:** `_segments_to_normalized_forecast()` — `temps_min`/
  `temps_max`/`felt_min_vals`/`felt_max_vals` (heute aus
  `s.aggregated.temp_min_c`/`temp_max_c`/`wind_chill_min_c`/`wind_chill_max_c`)
  wechseln auf `collect_hiking_window_points(segments)` +
  `hiking_field_min_max(..., "t2m_c"/"wind_chill_c")`, mit Fail-soft-Ruecksprung
  auf die bisherige Segment-Aggregat-Quelle, wenn keine Punkte vorliegen.
  Kommentar-Drift-Korrektur: Zeile 143-145 behauptet bereits heute "dieselbe
  Zeitreihe wie die Mail" — nach dieser Aenderung stimmt das erstmals wirklich
  und der Verweis wird prazisiert.
- **File:** `src/output/renderers/compact_summary.py:46-102,244-298`
  **Identifier:** `format_stage_summary()` (neue lokale Berechnung der
  Gehzeit-Extrema, durchgereicht an `format_weather_summary()`),
  `_format_temperature()`, `_format_felt_temperature()` (lesen neu
  `hiking_min_c`/`hiking_max_c`/`hiking_felt_min_c`/`hiking_felt_max_c` statt
  `summary.temp_min_c`/`temp_max_c`/`wind_chill_min_c`/`wind_chill_max_c`,
  Fail-soft-Ruecksprung auf `summary.*` wenn `None`). `_aggregate()` (Zeile
  204-210) bleibt **unveraendert** — sie bleibt Quelle fuer Wolken/Wind/Regen/
  Gewitter, nur Temperatur/gefuehlte Temperatur wechseln die Quelle.
- **File:** `src/output/renderers/narrow.py:369-428,480-560`
  **Identifier:** `_overview_line()` (neue optionale Parameter
  `hiking_temp_extrema`/`hiking_felt_extrema` fuer `metric_id in
  ("temperature", "wind_chill")`, ersetzen die heutige Berechnung aus
  `seg_tables` fuer genau diese zwei Metrik-IDs), `render_telegram_bubbles()`
  (berechnet die beiden Extrema-Tupel einmalig ueber
  `collect_hiking_window_points()`/`hiking_field_min_max()` und reicht sie
  durch, analog zur bestehenden `_night_min_c`-Berechnung Zeile 518-520).
  Alle uebrigen Metrik-IDs (R/PR/W/G/TH ueber `seg_tables`) bleiben
  unveraendert (nicht Teil dieser Spec, s. Out of Scope).

**Importrichtung-Praezedenzfall:** `narrow.py:34` importiert bereits
`fmt_val`/`format_trend_tokens` aus `email/helpers.py` — Cross-Modul-Importe
zwischen Renderern sind im Projekt etabliert, kein Sonderfall. `day_window.py`
selbst importiert nichts aus `email/helpers.py` (keine Zyklusgefahr); die
verschobene Funktion wird umgekehrt VON `email/helpers.py` importiert.
`sms_trip.py`/`compact_summary.py`/`narrow.py` importieren bereits heute aus
`day_window.py` (`DAY_WINDOW_START_HOUR`, `build_day_window_points`,
`night_temp_min_c`) — die neuen Funktionen reihen sich in denselben,
bestehenden Import ein.

## Estimated Scope

- **LoC:** ~140-190 Produktivcode (day_window.py ~45 netto [+Funktion
  verschoben +neue Ableitung], email/helpers.py ~-20/+5 [Funktion entfernt,
  Import ergaenzt], sms_trip.py ~+25/-12, compact_summary.py ~+25/-6,
  narrow.py ~+35/-12). Unter dem 250-LoC-Workflow-Limit, kein Override noetig
  nach heutigem Stand — bei Ueberschreitung waehrend der Implementierung PO-
  Permission einholen (CLAUDE.md).
- **Files:** 5 Produktivdateien (`day_window.py`, `email/helpers.py`,
  `sms_trip.py`, `compact_summary.py`, `narrow.py`) + 1 neue Testdatei +
  betroffene Golden-Fixtures (s. Test-Plan).
- **Effort:** medium-high — vier unabhaengige Renderer-Einstiegspunkte muessen
  synchron auf dieselbe Quelle umgestellt werden, volle Golden-Pruefung noetig.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services/segment_weather.py::_aggregate_for_segment()` (Zeile 254-273) | service (unveraendert) | Bleibt exklusive Randregel fuer alle Zwecke ausserhalb dieser Spec (Fail-soft bei `has_error`, `confidence_pct_min`, Betreffzeile, Multi-Day-Trend-Fetches) — #1329-Invariante, darf kein "letztes Segment"-Wissen bekommen |
| `docs/specs/_archive/modules/bug_1146_badge_window_mismatch.md` | Spec (Vorbild) | Die dort eingefuehrte Regel (letztes Segment inklusiv, innere Grenzen exklusiv) wird durch diese Spec NICHT geaendert, nur an einen geteilten Ort gehoben und auf weitere Konsumenten ausgedehnt |
| `tests/tdd/test_issue_807_reproduction.py` (`test_pills_respect_segment_window`, `test_last_segment_arrival_hour_included`, `test_shared_boundary_hour_not_double_counted`) | Bestehende Tests | Pruefen aktuell `build_metrics_summary_pills()` mit den Metrik-IDs `gust`/`precipitation` — diese laufen seit Epic #1319 Scheibe A durch `build_day_window_points()` (04-19-Fenster), NICHT durch die hier verschobene Funktion. Bleiben unveraendert gruen, testen aber NICHT den hier geaenderten Temperatur-Pfad — neue, gezielte Tests noetig (s. Test-Plan) |
| `docs/specs/modules/sms_daywindow_aggregation.md` (Epic #1319 Scheibe A) | Spec (Nachbarfenster, unberuehrt) | `build_day_window_points()` (04-19 Uhr, R/PR/W/G/TH) bleibt exakt wie spezifiziert — diese Spec aendert ausschliesslich das GEHZEIT-Fenster fuer Temperatur/gefuehlte Temperatur, nicht das Tagesfenster |
| `docs/specs/modules/night_temp_evening_only.md` (Epic #1319 Scheibe D) | Spec (Nachbarfenster, unberuehrt) | `N`/`FN` (Nacht-Tiefsttemperatur am Ziel, `night_temp_min_c()`/`night_wind_chill_min_c()`) bleiben exakt wie spezifiziert — diese Spec aendert nur `K`/`D`/`FK`/`FD` (Gehzeit-Extrema), nie den Nachtwert |
| `docs/specs/modules/trip_min_temp_and_felt_shortforms.md` (Issue #1410) | Spec (Konsument, wird korrigiert) | F3 dort nahm an, `segment_weather.py:254-281` sei bereits "der" Rechenweg fuer `K`/`D`/`FK`/`FD` in SMS/Kurzzusammenfassung — das war zum Zeitpunkt der Spec richtig beschrieben (Werte kamen tatsaechlich von dort), ist aber exakt die hier behobene Duplikat-Quelle. Diese Spec aendert NICHT die Token-Bedeutung/Sichtbarkeit aus #1410 (K/D/FK/FD erscheinen weiterhin wie dort spezifiziert), nur deren Datenquelle |
| `renderer_mail_gate.py` (#811, Commit-Gate) | Tooling | `email/helpers.py`, `sms_trip.py`, `compact_summary.py` sind Mail-Inhalts-Dateien → vor Commit `tests/tdd/test_issue_811_mode_matrix.py` gruen UND ein frischer `briefing_mail_validator.py`-Lauf gegen eine echt zugestellte Staging-Testmail noetig |
| `test_naming_gate.py` | Tooling | Neue Testdatei nach Verhalten benennen (`test_hiking_window_parity.py`), nicht nach Issue-Nummer — blockt sonst hart |
| `tests/golden/email/regenerate.py`, SMS-Golden-Aequivalent | Tooling | Neu einzufrierende Fixtures nach der Implementierung, dort wo die Ankunftsstunde bisher ein Extremwert war |

## Implementation Details

### 1. Geteilte Rohpunkt-Quelle — `day_window.py::collect_hiking_window_points()`

Die bestehende Funktion `_collect_hiking_window_dps()` (Logik unveraendert)
wandert von `email/helpers.py` nach `day_window.py` und wird oeffentlich:

```python
def collect_hiking_window_points(
    segments: Sequence[SegmentWeatherData],
) -> list[ForecastDataPoint]:
    """Gehzeit-Fenster je Segment: inklusiver Start, EXKLUSIVES Ende — ausser
    beim LETZTEN Segment eines Reports, dessen Ende INKLUSIV zaehlt (Bug
    #1146: Ankunftsstunde ist erlebte Gehzeit). Innere Segmentgrenzen bleiben
    dadurch exakt einmal gezaehlt (#806/#807). Einzige Quelle fuer Temperatur/
    gefuehlte Temperatur in Mail-Kachelzeile, SMS, Telegram-Kurzuebersicht und
    E-Mail-Kurzzusammenfassung (Issue #1417)."""
    # ... (Rumpf 1:1 aus der bisherigen _collect_hiking_window_dps, keine
    # Verhaltensaenderung)
```

`email/helpers.py::build_metrics_summary_pills()` importiert diese Funktion
statt der bisherigen lokalen und verhaelt sich dadurch bit-identisch (reine
Verschiebung, keine Golden-Aenderung an der Mail-Kachelzeile selbst).

**Bewusst NICHT migriert:** die naive `.hour`-Verwendung (kein
`local_hour(dp.ts, tz)`, kein `s.start_time.hour` ueber `local_hour()`) bleibt
exakt wie im Original — die Funktion nimmt bis heute keinen `tz`-Parameter.
Das ist bestehendes, in Produktion laufendes Verhalten der Mail-Kachelzeile
und wird durch die reine Verschiebung nicht angefasst (kein neuer Rechenweg,
kein neues Risiko relativ zum Ist-Zustand — s. Known Limitations).

### 2. Kleine geteilte Ableitung — `day_window.py::hiking_field_min_max()`

```python
def hiking_field_min_max(
    points: Sequence[ForecastDataPoint], field: str,
) -> Optional[tuple[float, float, "datetime"]]:
    """(min_value, max_value, max_ts) fuer EIN ForecastDataPoint-Feld aus
    bereits gefensterten Rohpunkten (``collect_hiking_window_points()``).
    ``max_ts`` bedient sowohl den Mail-Zeitanker (´· Max HH:00´) als auch die
    Telegram-Peak-Stunde (´@{h}´) — EINE Ableitung, zwei Verwendungen, statt
    zwei parallelen Berechnungen. ``None``, wenn kein Punkt das Feld traegt
    (Fail-soft-Signal an den Aufrufer)."""
    vals_ts = [(getattr(dp, field, None), dp.ts) for dp in points]
    vals_ts = [(v, ts) for v, ts in vals_ts if v is not None]
    if not vals_ts:
        return None
    min_val = min(v for v, _ in vals_ts)
    max_val, max_ts = max(vals_ts, key=lambda x: x[0])
    return min_val, max_val, max_ts
```

Nach demselben, bereits etablierten Muster wie `_night_min_of_field()`
(Issue #1410: ein geteilter Kern, duenne oeffentliche Wrapper pro Feld/
Aufrufer-Bedarf). Die Mail-Kachelzeile (`_pill_for_metric`/
`_aggregation_pill_text`) bleibt UNVERAENDERT — sie berechnet Min/Max/Anker
bereits inline aus `all_dps` nach demselben Muster; ein Umbau auf
`hiking_field_min_max()` dort waere reine Kosmetik ohne Verhaltensaenderung
und wird nicht vorgenommen (Scope-Disziplin, LoC-Budget).

### 3. SMS — `sms_trip.py::_segments_to_normalized_forecast()`

```python
hiking_points = collect_hiking_window_points(segments)
temp_extrema = hiking_field_min_max(hiking_points, "t2m_c")
felt_extrema = hiking_field_min_max(hiking_points, "wind_chill_c")

if temp_extrema is not None:
    day_min, day_max, _ = temp_extrema
else:
    # Fail-soft (kein Segment mit verwertbarer Zeitreihe, z.B. alle
    # has_error): bisheriges Verhalten aus dem Segment-Aggregat.
    temps_min = [s.aggregated.temp_min_c for s in segments if s.aggregated.temp_min_c is not None]
    temps_max = [s.aggregated.temp_max_c for s in segments if s.aggregated.temp_max_c is not None]
    day_min = min(temps_min) if temps_min else None
    day_max = max(temps_max) if temps_max else None

# analog fuer felt_extrema -> felt_min/felt_max (Fallback auf
# s.aggregated.wind_chill_min_c/wind_chill_max_c)
```

`night_min`/`night_felt_min` (Nachtwert, `N`/`FN`) bleiben **exakt**
unveraendert — sie kommen weiterhin aus `night_temp_min_c()`/
`night_wind_chill_min_c()` (Issue #1319 Scheibe D / #1410), diese Spec
betrifft ausschliesslich `day_min`/`day_max`/`felt_min`/`felt_max` (Quelle
fuer `K`/`D`/`FK`/`FD`).

Kommentar-Korrektur Zeile 143-145: der Verweis "dieselbe Zeitreihe wie die
Mail (`segment_weather.py:254-281`)" wird auf den tatsaechlichen, jetzt
gemeinsamen Ort (`day_window.collect_hiking_window_points()`) korrigiert.

### 4. E-Mail-Kurzzusammenfassung — `compact_summary.py`

`_aggregate()` (Zeile 204-210, `aggregate_stage()`) bleibt **unveraendert** —
sie bleibt Quelle fuer Wolken/Wind/Regen/Gewitter. `format_stage_summary()`
berechnet zusaetzlich, VOR dem Aufruf von `format_weather_summary()`:

```python
hiking_points = collect_hiking_window_points(segments)
temp_extrema = hiking_field_min_max(hiking_points, "t2m_c")
felt_extrema = hiking_field_min_max(hiking_points, "wind_chill_c")
hiking_min_c, hiking_max_c = (temp_extrema[0], temp_extrema[1]) if temp_extrema else (None, None)
hiking_felt_min_c, hiking_felt_max_c = (felt_extrema[0], felt_extrema[1]) if felt_extrema else (None, None)
```

und reicht diese vier Werte als neue optionale Parameter durch
`format_weather_summary()` an `_format_temperature()`/
`_format_felt_temperature()` weiter. Dort ersetzen sie
`summary.temp_min_c`/`temp_max_c`/`wind_chill_min_c`/`wind_chill_max_c` mit
Fail-soft-Ruecksprung auf `summary.*`, wenn `None` (kein Provider-Ausfall-
Regressionsrisiko):

```python
t_max = hiking_max_c if hiking_max_c is not None else summary.temp_max_c
t_min = (hiking_min_c if hiking_min_c is not None else summary.temp_min_c) \
    if report_type == "morning" else \
    (night_min_c if night_min_c is not None else
     (hiking_min_c if hiking_min_c is not None else summary.temp_min_c))
```

**Ortsvergleich unberuehrt:** `format_weather_summary()` wird auch von
`format_location_summary()` (Ortsvergleich-Kontext) aufgerufen — die vier
neuen Parameter bekommen dort keinen Wert (Default `None`), wodurch der
Vergleichspfad exakt beim bisherigen `summary.temp_min_c`/`temp_max_c`
bleibt. Kein Eingriff in Compare (s. Out of Scope).

### 5. Telegram-Kurzuebersicht — `narrow.py`

`render_telegram_bubbles()` berechnet einmalig (analog zur bestehenden
`_night_min_c`-Berechnung Zeile 518):

```python
_hiking_points = collect_hiking_window_points(segments)
_hiking_temp_extrema = hiking_field_min_max(_hiking_points, "t2m_c")
_hiking_felt_extrema = hiking_field_min_max(_hiking_points, "wind_chill_c")
```

und reicht sie bei jedem `_overview_line()`-Aufruf durch. In `_overview_line()`
wird — NUR fuer `metric_id in ("temperature", "wind_chill")` — die heutige
Berechnung aus `seg_tables` (`hits`/`lo_row`/`hi_row`) durch das passende
Extrema-Tupel ersetzt: `lo`/`hi` aus `min_val`/`max_val` (gerundet wie
bisher ueber `fmt_val`), `peak_hour` aus `local_hour(max_ts, tz):02d`
(dasselbe Zahlformat wie das bisherige `hi_row.get("time","")`, das aus
`f"{local_hour(dp.ts, self._tz):02d}"` in `trip_report.py::_dp_to_row`
stammt — s. Source). Die bestehende Abend-Nachtwert-Ersetzung (`_night_val`
ueberschreibt `lo`) bleibt **unveraendert** danach angewendet. Alle uebrigen
Metrik-IDs (R/PR/W/G/TH ueber `seg_tables`) sind von dieser Aenderung nicht
betroffen (anderes Fenster, Epic #1319 Scheibe A, s. Out of Scope).

**Fail-soft:** liefert `hiking_field_min_max()` `None` (keine Segment-
Zeitreihe verwertbar), faellt `_overview_line()` fuer diese zwei Metrik-IDs
auf ihre bisherige `seg_tables`-Berechnung zurueck (kein Absturz, kein
leerer Wert) — exakt das bisherige Verhalten bleibt als Fallback erhalten.

## Expected Behavior

- **Input:** `segments` (Etappen-Zeitreihen), unveraendert `night_weather`,
  `report_type`, `tz` — keine neuen Pflichtparameter fuer externe Aufrufer
  (Scheduler, Preview-Endpunkte).
- **Output:** Mail-Kachelzeile, SMS (`K`/`D`/`FK`/`FD`), Telegram-
  Kurzuebersicht (Temperatur-/gefuehlte-Temperatur-Zeile) und E-Mail-
  Kurzzusammenfassungssatz zeigen fuer dieselbe Etappe denselben Tiefst- und
  Hoechstwert — insbesondere wenn die Ankunftsstunde des letzten Segments den
  Tages-Extremwert traegt (der gemeldete Fall #1417). Der Nachtwert (`N`/`FN`,
  night_temp_evening_only.md) und das Tagesfenster 04-19 fuer R/PR/W/G/TH
  (sms_daywindow_aggregation.md) sind unveraendert.
- **Side effects:** keine neuen API-Calls, keine Persistenz-/Schema-Aenderung.
  Golden-Neuerzeugung dort, wo die Ankunftsstunde bisher ein Extremwert war,
  der in SMS/Telegram/Kurzzusammenfassung fehlte (bewusste Aenderung, kein
  Regressionsbefund — Praezedenz #1410).

## Acceptance Criteria

- **AC-1:** Given eine Etappe, deren waermste Stunde die Ankunftsstunde des
  letzten Segments ist / When Mail und Kurznachricht desselben Briefings
  gerendert werden / Then nennen beide denselben Hoechstwert (heute:
  unterschiedliche Werte, weil die SMS die Ankunftsstunde ausschliesst).
  - Test: `test_mail_and_sms_agree_when_arrival_hour_is_extreme` in
    `tests/tdd/test_hiking_window_parity.py`, rot vor Fix, gruen danach —
    reproduziert exakt den gemeldeten Fall `13–17°C` vs. `K13 D16`.

- **AC-2:** Given dieselbe Konstellation wie AC-1 / When Mail-Kachelzeile,
  SMS UND Telegram-Kurzuebersicht aus demselben Report erzeugt werden / Then
  zeigen alle drei denselben Tiefst- UND Hoechstwert fuer die gemessene
  Temperatur.
  - Test: `test_mail_sms_telegram_agree_measured_temperature`.

- **AC-3:** Given eine Etappe mit aktivierter gefuehlter Temperatur, deren
  kaelteste gefuehlte Stunde die Ankunftsstunde ist / When Mail-Kachelzeile,
  SMS, E-Mail-Kurzzusammenfassung und Telegram-Kurzuebersicht gerendert
  werden / Then zeigen alle vier denselben gefuehlten Tiefstwert.
  - Test: `test_mail_sms_compact_telegram_agree_felt_temperature`.

> **Nachweisweg zu AC-4 (Ergaenzung aus der RED-Phase, verbindlich):** Ueber
> Tiefst-/Hoechstwert allein ist Doppelzaehlung **nicht beobachtbar**
> (`min(x, x) == min(x)`) — ein reiner Spannenvergleich waere blind fuer
> #806/#807. Der Nachweis laeuft deshalb ueber die **Mittelwert-Kachel**
> (Auswertungswahl „nur Mittelwert", #1357): 40 °C in der Grenzstunde, sonst
> 10 °C, Fenster 08–12 → **16 °C bei Einfachzaehlung, 20 °C bei
> Doppelzaehlung**. Ein kuenftiger Umbau darf diesen Nachweisweg nicht durch
> einen Spannenvergleich ersetzen.

- **AC-4 (Regressionsschutz #806/#807):** Given zwei aufeinanderfolgende
  Segmente mit gemeinsamer Grenzstunde (Ende Segment 1 = Start Segment 2,
  NICHT die Ankunft), an der ein Extremwert liegt / When SMS und
  Mail-Kachelzeile aus demselben Report erzeugt werden / Then zaehlt dieser
  Wert in beiden Ausgaben genau einmal (keine Verdopplung, kein doppelt
  hoher Ausschlag gegenueber dem tatsaechlichen Messwert).
  - Test: `test_shared_boundary_hour_counted_once_across_channels`.

- **AC-5 (Einzigkeit der Quelle, nicht nur zufaellige Uebereinstimmung):**
  Given eine Matrix aus mehreren Etappen-Konstellationen (Extremwert an der
  Ankunftsstunde, an einer inneren Segmentgrenze, mitten in einem Segment,
  bei einem einzelnen Segment, bei drei Segmenten) / When fuer JEDE
  Konstellation Mail-Kachelzeile, SMS, E-Mail-Kurzzusammenfassung und
  Telegram-Kurzuebersicht aus demselben Report gerendert werden / Then
  liefern alle vier Kanaele in JEDER Konstellation identische Tiefst-/
  Hoechstwerte — ein Test, der nur EINEN Fall vergleicht, waere auch bei
  zwei zufaellig uebereinstimmenden, aber unabhaengigen Berechnungen gruen;
  diese Matrix deckt die Faelle ab, in denen zwei unabhaengige Regeln
  auseinanderlaufen wuerden (insbesondere AC-1s Ankunftsstunden-Fall).
  - Test: `test_parity_matrix_across_constellations` (parametrisiert,
    mindestens 5 Konstellationen aus der obigen Liste).

- **AC-6 (Teilausfall verschlechtert sich nicht):** Given eine Etappe aus
  mehreren Teilen, von denen einer wegen Provider-Ausfall keine verwertbaren
  Daten hat (`has_error=True`, leeres `SegmentWeatherSummary`) / When Mail,
  SMS, Kurzzusammenfassung und Telegram gerendert werden / Then bilden alle
  vier denselben Tiefst-/Hoechstwert aus derselben verkuerzten Grundlage
  (den verbliebenen Teilen) — die Umstellung darf den Ausfall nicht
  verschaerfen, indem in einem Kanal gar kein Wert mehr erscheint, wo heute
  einer steht. Faellt die GESAMTE Etappe aus, zeigen alle vier
  uebereinstimmend die Null-Form (`K-`/`D-` bzw. leerer Temperaturteil).
  - Test: `test_partial_segment_failure_same_shortened_basis_all_channels`
    und `test_total_failure_yields_null_form_in_all_channels`.

  **Klarstellung (PO-Rueckfrage 2026-07-29):** Ein ausgefallener Etappenteil
  liefert **keinen Ersatzwert** — sein `SegmentWeatherSummary` ist leer
  (`segment_weather.py:161,208`), und die Aggregation ueberspringt `None`
  (`sms_trip.py:142-145`). Der Wert entsteht also aus einer stillschweigend
  **verkuerzten** Grundlage. Das ist Bestandsverhalten und wird hier
  **nicht** geaendert — diese Spec stellt nur sicher, dass alle Kanaele
  dieselbe verkuerzte Grundlage benutzen.

  **Bewusst ausserhalb (eigener Posten):** Anders als `R`/`PR`/`W`/`G`/`TH:`
  kennzeichnen die Temperatur-Token eine Datenluecke **nicht** — dort wird
  aus `-` kein `?` (`builder.py:263`, `render_temperature()` ohne
  `has_gap`-Auswertung, waehrend `_mk_metric` sie bei den uebrigen
  Groessen anwendet, `builder.py:118-123`). `K-` heisst damit „keine Daten",
  sieht aber aus wie eine Entwarnung. Das ist eine neue Verhaltensregel
  (und betraefe Mail und Telegram gleichermassen), keine Vereinheitlichung —
  daher nicht Teil dieser Lieferung.

- **AC-7 (Nachtwert unberuehrt):** Given ein Abendbriefing mit Ankunft am
  Etappenziel und vorhandenem `night_weather` / When SMS, E-Mail-
  Kurzzusammenfassung und Telegram gerendert werden / Then bleibt die
  Nacht-Tiefsttemperatur (`N`/`FN`) exakt die echte Nachttemperatur am Ziel,
  unveraendert durch diese Aenderung (night_temp_evening_only.md DEC-1
  bleibt gueltig — diese Spec aendert ausschliesslich den Gehzeit-Tiefst-/
  Hoechstwert `K`/`D`/`FK`/`FD`).
  - Test: `test_night_temperature_unaffected_by_hiking_window_change`.

- **AC-8 (Bestandsverhalten ohne Randstunden-Extremwert):** Given eine
  Etappe, deren Extremwerte NICHT an der Ankunftsstunde oder einer
  Segmentgrenze liegen (klar in der Mitte eines Segments) / When alle vier
  Kanaele gerendert werden / Then bleibt das Ergebnis bit-identisch zum
  Vorzustand (keine unbeabsichtigte Verhaltensaenderung fuer den
  Normalfall).
  - Test: bestehende Golden-Fixtures ohne Randstunden-Extremwert bleiben nach
    Neu-Regeneration bit-identisch (kein Diff), namentlich zu pruefen.

- **AC-9 (Ausgefallener LETZTER Etappenteil, Fund der RED-Phase):** Given eine
  Etappe, deren letzter Teil wegen Provider-Ausfall keine Daten hat, waehrend
  der davorliegende Teil seinen Hoechstwert in seiner **eigenen Endstunde**
  traegt / When alle vier Kanaele gerendert werden / Then nennen alle vier
  denselben Hoechstwert — der ueberlebende Teil verliert seine Endstunde
  nicht dadurch, dass ein ausgefallener Teil hinter ihm steht.
  - Test: `test_failed_last_part_keeps_survivor_arrival_hour_in_all_channels`
  - **Belegte Ursache:** `_collect_hiking_window_dps` bestimmt `last_idx =
    len(segments) - 1` ueber die **Rohliste**, also inklusive ausgefallener
    Teile. Faellt der letzte Teil aus, gilt der ueberlebende nicht mehr als
    „letzter"; seine Endstunde wird ausgeschlossen, waehrend
    `_extract_hourly_rows` (Telegram) sie weiter mitnimmt. Gemessen: Mail/SMS/
    Kurzzusammenfassung `5–15 °C`, Telegram `5–22 °C`.
  - **Konsequenz fuer die Umsetzung:** Die geteilte Funktion muss „letzter
    Teil" ueber die **verwertbaren** Teile bestimmen, nicht ueber die
    Rohliste. Ohne das bleibt die Divergenz nach der Vereinheitlichung
    bestehen — und der Auftrag „eine Berechnung" waere nicht erfuellt.

- **AC-10 (Zusammenfassungssatz nennt die Temperatur, wenn Gehzeit-Punkte
  vorliegen):** Given eine Etappe mit verwertbaren Gehzeit-Punkten, deren
  Segment-Aggregat aber keine Auswertungsregeln traegt / When die
  E-Mail-Kurzzusammenfassung gerendert wird / Then nennt der Satz einen
  Temperaturteil, der zur Kachelzeile derselben Mail passt — statt die
  Temperatur wegzulassen, waehrend die Kachel zwei Zeilen weiter oben eine
  Spanne zeigt.
  - Test: `test_compact_summary_names_temperature_whenever_hiking_points_exist`
  - **PO-Entscheidung 2026-07-29:** Die Gehzeit-Werte ueberstimmen den
    Frueh-Ausstieg in `CompactSummaryFormatter._aggregate()`. Begruendung:
    Sonst blieben zwei Wege zur selben Aussage bestehen — genau das, was
    diese Lieferung beseitigen soll.
  - **Belegte Ursache des heutigen Verhaltens:**
    `SegmentWeatherSummary.aggregation_config` hat den Default `{}`
    (`models.py:403`) und wird nur von `compute_basis_metrics()`/
    `compute_extended_metrics()` gefuellt. Fehlt die Regelkarte, iteriert
    `aggregate_stage()` ueber eine leere Karte und liefert ein Etappen-
    Aggregat, in dem **jedes** Feld `None` ist — deshalb fehlen im
    betroffenen Golden auch der Wolken-Teil und nicht nur die Temperatur.
    Bei einteiligen Etappen faellt das nicht auf, weil `_aggregate()` dort
    das Segment-Aggregat direkt durchreicht.

## Test-Plan

Kern-Schicht (deterministisch, echte Renderer-Aufrufe, kein Mock-Theater),
neue Testdatei nach Verhalten benannt: `tests/tdd/test_hiking_window_parity.py`.

| AC | Testfall |
|----|----------|
| AC-1 | `test_mail_and_sms_agree_when_arrival_hour_is_extreme` |
| AC-2 | `test_mail_sms_telegram_agree_measured_temperature` |
| AC-3 | `test_mail_sms_compact_telegram_agree_felt_temperature` |
| AC-4 | `test_shared_boundary_hour_counted_once_across_channels` |
| AC-5 | `test_parity_matrix_across_constellations` |
| AC-6 | `test_sms_falls_back_to_segment_aggregate_without_timeseries` |
| AC-7 | `test_night_temperature_unaffected_by_hiking_window_change` |
| AC-8 | Golden-Regression (kein neuer Unit-Test, s.u.) |

**Betroffene Bestandstests (Review-Pflicht, keine automatische Anpassung
ohne Pruefung):**
- `tests/tdd/test_sms_trip_min_temp_token.py`,
  `tests/tdd/test_sms_trip_felt_temp_tokens.py`,
  `tests/tdd/test_compact_summary_hiking_min_and_felt.py`,
  `tests/tdd/test_telegram_felt_temperature_overview.py`,
  `tests/tdd/test_telegram_temperature_morning_range.py` (alle Issue #1410) —
  deren Fixtures nutzten bisher `segment.aggregated.temp_min_c`/`temp_max_c`
  als implizite Quelle; sofern kein Fixture-Extremwert an der Ankunftsstunde
  liegt, bleiben sie unveraendert gruen. Vor Commit einzeln laufen lassen.
- `tests/tdd/test_issue_807_reproduction.py::test_pills_respect_segment_window`
  — **KORREKTUR (RED-Phase 2026-07-29):** Die urspruengliche Annahme dieser
  Spec („bleibt unveraendert gruen") ist falsch. Der Test ist **vorbestehend
  rot seit `087f643f` vom 2026-07-19** (#1319 Scheibe A). Dort wechselte die
  Boeen-Kachel ueber `_DAY_WINDOW_PILL_IDS` vom Gehzeit- auf das
  Tagesfenster 04–19 Ortszeit; der Fixture-Peak liegt bei 02:00 UTC =
  **04:00 Ortszeit**, also exakt in dessen erster Stunde. Die Kachel
  `Boeen >20 km/h ab 04:00 · max 95 (04:00)` ist damit korrekt — die
  Testerwartung beschreibt eine Regel, die fuer Boeen seit dem 19.07. nicht
  mehr gilt. Belegt durch den Nachbartest
  `test_compact_summary_respects_segment_window`, den #1330 (`d042e911`,
  2026-07-21) genau dafuer nachzog (`peak_h=2` → `peak_h=0` samt Docstring
  „echt ausserhalb des Tagesfensters"). Dieser Test blieb liegen.
  **Gehoert fachlich zu #1319/#1330, nicht zu #1417** — dieselbe
  Ein-Zeilen-Korrektur, als eigener Commit ausserhalb dieser Lieferung
  (Kern-Tests duerfen nicht rot liegenbleiben, CLAUDE.md Test-Politik).
  Nachweis der Einordnung: Stichproben ueber `git archive` in Snapshots —
  `087f643f` rot, dessen Vorgaenger `b0f90fa3` gruen.

**Golden-Regression (bewusste Neuerzeugung, kein Regressionsbefund) —
KORRIGIERT nach Sichtung in der RED-Phase:**

- **SMS-Goldens: kein Diff zu erwarten.** `tests/golden/test_sms_golden.py`
  ruft `build_token_line()` mit von Hand gebauten `DailyForecast`-Objekten auf
  und laeuft **nicht** durch `sms_trip.py` (die Datei sagt es selbst: „NO
  cross-check against legacy output.renderers.sms_trip"). Eine Aenderung in
  `_segments_to_normalized_forecast()` kann diese Fixtures strukturell nicht
  erreichen. Die urspruengliche Anweisung „alle `tests/golden/sms/*.txt` neu
  einfrieren" geht ins Leere.
- **Mail-Goldens: alle 10 aendern sich** (5 Profile × plain/html), und zwar
  **ausschliesslich im Kurzzusammenfassungssatz** — die Kachelzeile bleibt
  unveraendert, weil die Funktion nur verschoben und nicht veraendert wird.
  Ursache ist eine vorbestehende Fixture-Eigenart: `regenerate.py::_build_seg_weather`
  schreibt `aggregated` von Hand, entkoppelt von der eigenen Zeitreihe
  (`t2m_c = 15.0 + Stunde*0.3`, streng monoton → das Maximum jedes Fensters
  liegt immer in der letzten Stunde, beim letzten Teil also exakt in der
  Ankunftsstunde). Der Satz zieht damit heute andere Zahlen als die Kachel
  derselben Mail; nach der Umstellung stimmen beide ueberein.
- `gr20-summer-evening` bekommt **erstmals** einen Temperaturteil im Satz
  (erwartet `18–20°C, gef. 11.8–13.2°C`, deckungsgleich mit seiner eigenen
  Kachelzeile) — Folge der Entscheidung in AC-9.

**Renderer-Commit-Gate #811 (Pflicht vor Commit):** `email/helpers.py`,
`sms_trip.py`, `compact_summary.py` sind Mail-Inhalts-Dateien →
`renderer_mail_gate.py` blockiert, bis (1)
`tests/tdd/test_issue_811_mode_matrix.py` gruen ist UND (2) ein frischer
`briefing_mail_validator.py`-Lauf gegen eine echte Staging-Testmail
erfolgreich war.

## Out of Scope

- **`src/services/segment_weather.py`** bleibt vollstaendig unveraendert
  (`_aggregate_for_segment()`, exklusive Randregel) — #1329-Invariante, s.
  Purpose/Dependencies. Seine uebrigen Konsumenten (Fail-soft bei
  `has_error`, `confidence_pct_min`, Betreffzeile, Multi-Day-Trend-Fetches)
  behalten ihr heutiges Verhalten unveraendert.
- **Ortsvergleich (`comparison_engine`, `format_location_summary`):** keine
  Aenderung — `format_weather_summary()`s neue Parameter bleiben dort
  `None`, der Vergleichspfad bleibt exakt beim bisherigen
  `summary.temp_min_c`/`temp_max_c` (eigene Datenform, eigener Docstring-
  begruendeter Nicht-Wiederverwendungs-Fall).
- **Tagesfenster 04:00-19:00** (`day_window.build_day_window_points()`,
  R/PR/W/G/TH, sms_daywindow_aggregation.md) — unveraendert, anderes Fenster
  fuer andere Metriken.
- **Nachtfenster** (`night_temp_min_c()`/`night_wind_chill_min_c()`,
  night_temp_evening_only.md) — unveraendert, s. AC-7.
- **Issue #1415/#1416** — nicht Teil dieser Lieferung.
- **Mail-Highlights (`trip_report.py::_compute_highlights`) und
  Mail-Stundentabelle (`trip_report.py::_extract_hourly_rows`)** — beide
  bereits inklusiv je Segment (Referenzverhalten, nicht Teil der
  Duplikat-Kette dieser Spec, da sie einzelne Tabellenzeilen produzieren statt
  eines report-weiten Min/Max-Aggregats — keine Aenderung noetig).

## Known Limitations

- **Rundungs-Divergenz (bewusst NICHT in dieser Lieferung behoben):** Die
  Wind/Boen-Pille in `email/helpers.py` rundet mit `int(peak_val)`
  (Abschneiden, Zeile 1467) waehrend `tokens/metrics.py::_fmt_num()` mit
  `int(round(value))` rundet (Zeile 22) — 19,6 km/h zeigt Mail „19", SMS
  „20". **Entscheidung:** getrennt von dieser Lieferung, eigener
  Nebenbefund-Eintrag (#1199-Kandidat, LOW/kosmetisch). Begruendung: (1)
  andere Wurzel — ein Formatierungs-/Rundungskonventions-Unterschied im
  WIND-Pfad, nicht dieselbe Fenster-Berechnungs-Duplikation, die diese Spec
  behebt (betrifft nicht Temperatur/gefuehlte Temperatur); (2) die PO-Vorgabe
  fuer #1417 ist woertlich "nicht angleichen, sondern eine Berechnung" — die
  Rundungsdivergenz IST ein Angleichungsfall (zwei Formeln sollen dasselbe
  Ergebnis liefern), kein Ein-Quelle-Fall, ihre Aufnahme wuerde die
  Zielsetzung dieser Lieferung verwaessern; (3) Bündelung würde eine weitere,
  unabhaengige Mail-Gate-geschuetzte Datei (`tokens/metrics.py` ist kein
  Renderer, aber der Wind-Pfad in `helpers.py` ist es) und weitere
  Golden-Diffs in denselben Commit ziehen, ohne dass die Diffs kausal
  zusammenhaengen. **Konsequenz Weg A (getrennt, hier gewaehlt):** #1417 bleibt
  fokussiert und klein nachweisbar; die Rundungsdivergenz bleibt ein
  bekannter, dokumentierter Kosmetik-Fehler bis zu einem eigenen Ticket.
  **Konsequenz Weg B (mitgenommen):** ein Commit, eine Adversary-Runde, aber
  ein Golden-Diff, der zwei ursaechlich unabhaengige Aenderungen vermischt —
  erschwert Bisect/Review und widerspricht der PO-Vorgabe, hier NICHT
  anzugleichen, sondern zu vereinheitlichen.
- **`collect_hiking_window_points()` nutzt weiterhin `dp.ts.hour`/
  `segment.start_time.hour` ohne explizite `local_hour(..., tz)`-Konvertierung**
  (identisch zum unveraenderten Original-Verhalten der Mail-Kachelzeile) —
  kein neues Risiko relativ zum Ist-Zustand, da die Funktion 1:1 verschoben
  wird; eine etwaige TZ-Unschaerfe existierte bereits vor dieser Spec und ist
  nicht Teil dieser Behebung.
- **Cloud/Humidity/Visibility-Pillen** lesen in der Mail ebenfalls aus
  `collect_hiking_window_points()` (ueber `hiking_dps` in
  `build_metrics_summary_pills()`), haben aber in SMS/Telegram/
  Kurzzusammenfassung keine direkte Entsprechung und sind vom gemeldeten
  Bug (#1417, nur Temperatur) nicht betroffen — keine Aenderung an ihrer
  Verdrahtung.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Kein neues strukturelles Muster — Fortfuehrung des bereits
  etablierten Musters aus `night_temp_evening_only.md`/`trip_min_temp_and_
  felt_shortforms.md` (geteilte, kleine Ableitungsfunktion in `day_window.py`,
  von mehreren Renderern konsumiert, Fail-soft-Ruecksprung auf die bisherige
  Quelle). Die einzige inhaltliche Entscheidung — Ankunftsstunde inklusiv,
  innere Grenzen exklusiv — wurde bereits in #1146 getroffen und ADR-artig
  begruendet; diese Spec aendert die Regel nicht, sondern hebt sie an den
  einen Ort, aus dem alle Konsumenten schoepfen (PO-Vorgabe #1417).

## Changelog

- 2026-07-29: Initial spec created — Issue #1417.
