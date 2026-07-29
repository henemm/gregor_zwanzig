# Context: fix-1417-gehzeit-eine-quelle

<!-- Issue #1417 — PO-Vorgabe 2026-07-29: „Gehzeit darf nicht doppelt berechnet werden" -->

## Request Summary

Mail und Kurznachricht zeigen für dieselbe Etappe verschiedene Temperaturen
(`13–17°C` vs. `K13 D16`). Der Fehler ist reproduziert; die Ursache sind
mehrere unabhängige Implementierungen desselben Gehzeit-Fensters. **PO-Vorgabe:
nicht angleichen, sondern auf EINE Berechnung zurückführen.**

## Es sind vier Stellen, nicht zwei

| Fundstelle | Ausgabe | Ankunftsstunde |
|---|---|---|
| `services/segment_weather.py:254-273` (`_aggregate_for_segment`) | SMS, Telegram-Fallback, Kurzzusammenfassung, Mail-Betreff | **exklusiv** |
| `output/renderers/email/helpers.py:1598-1621` (`_collect_hiking_window_dps`) | Mail-Kachelzeile | **inklusiv** (nur letztes Segment) |
| `output/renderers/trip_report.py:319-332` (`_extract_hourly_rows`) | Mail-Stundentabelle, Basis der Telegram-`seg_tables` | **inklusiv**, je Segment |
| `output/renderers/trip_report.py:551-665` (`_compute_highlights`) | Mail-Highlights | inklusiv je Segment |

Betroffen sind damit **alle** Kanäle, nicht nur Mail vs. SMS: Die
Telegram-Kurzübersicht (`narrow.py:368-424`) bezieht ihre Werte über
`seg_tables` und ist damit eine **dritte** Variante derselben Aussage.

**Nicht betroffen (bewusst eigene Fenster, kein Duplikat):**
`day_window.build_day_window_points()` (04–19 Uhr für R/PR/W/G/TH, ADR-0025),
`night_temp_min_c()`/`night_wind_chill_min_c()` (Nachtfenster, #1319 Scheibe D),
`comparison_engine._filter_by_target_date_and_window()` (Ortsvergleich, andere
Datenform — eigener Docstring begründet die Nicht-Wiederverwendbarkeit).

## Die beiden Regeln sind je ein korrekter Fix — das ist der kritische Punkt

- **#806/#807** (`066ef174`): exklusive Regel `start_h <= h < end_h`, damit die
  **Grenzstunde zwischen zwei Segmenten** nicht doppelt zählt. Landete in
  `email/helpers.py` **und** `segment_weather.py`.
- **#1146** (`3943604c`, Spec `docs/specs/_archive/modules/bug_1146_badge_window_mismatch.md`):
  Die exklusive Regel verschluckte die **Ankunftsstunde des letzten Segments** —
  „kein Regen"-Badge trotz Regen genau in dieser Stunde. Fix: `is_last`-Sonderfall,
  **nur** in `_collect_hiking_window_dps`. `segment_weather.py` und
  `compact_summary.py` waren dort ausdrücklich **out of scope** — der Nebenbefund
  ist bis heute offen.

Beide Regeln gleichzeitig korrekt zu halten (innere Grenzen exklusiv, äußere
Ankunft inklusiv) erfordert **Report-Kontext** („bin ich das letzte Segment?").

## Warum die Mail nicht einfach die Aggregate liest

`SegmentWeatherSummary` trägt `temp_min_c`/`temp_max_c` als reine **Werte, ohne
Zeitstempel**. Die Mail-Kachelzeile rendert aber einen Zeitanker
(`8–15°C · Max 12:00`, Muster identisch bei `cloud_total`/`visibility`/`humidity`,
`helpers.py:1373-1387`) und braucht dafür die Rohpunkte. SMS und Telegram
brauchen den Anker für Temperatur nicht (`K3 D9`) und lesen deshalb direkt die
Aggregate — das spart Code und kostet die Konsistenz.

Der Unterschied ist also **darstellerisch**, nicht fachlich: eine Datenquelle,
mehrere Formatierer.

## Architektur-Randbedingung

`segment_weather.py::_aggregate_for_segment()` ist bewusst **rein pro Segment**
(Invariante aus #1329: „Aggregat entsteht bei JEDEM Aufruf beim aufrufenden
Segment, nie aus fremdem Kontext"). Es kann strukturell keine „ist letztes
Segment"-Ausnahme kennen — genau das war 2026-07 die Begründung, #1146 dort
NICHT zu fixen. Weitere Konsumenten (`aggregate_stage()`, Betreffzeile,
Fail-soft-Pfade für `has_error`-Segmente, Multi-Day-Trend-Fetches im Scheduler,
die Segmente unabhängig cachen) würden eine dortige Regeländerung unkontrolliert
erben.

## Fachlich richtige Regel

**Ankunftsstunde inklusiv** — sie ist erlebte Gehzeit (Begründung aus #1146,
gestützt durch die immer-inklusive Referenztabelle `_extract_hourly_rows`).
**Innere Segmentgrenzen exklusiv bzw. dedupliziert** (#806/#807). Dasselbe
Muster tragen die Nachbarfälle `sms_daywindow_aggregation.md` und
`night_temp_evening_only.md`: Übergangsstunde nicht verlieren, sondern
deduplizieren („höchster Wert gewinnt").

## Lösungsrichtung (Empfehlung der Analyse)

`_collect_hiking_window_dps()` aus `email/helpers.py` in ein geteiltes Modul
heben (naheliegend `day_window.py`, das bereits das analoge Muster für
R/PR/W/G/TH und die Nachtwerte trägt) und **SMS** (`sms_trip.py:139-156`),
**Telegram-Kurzübersicht** (`narrow.py::_overview_line` über `seg_tables`) und
**Kurzzusammenfassung** (`compact_summary.py::_aggregate`/`_format_temperature`/
`_format_felt_temperature`) darauf umstellen, statt weiter
`segment.aggregated.temp_*`/`wind_chill_*` direkt zu lesen.

`segment_weather.py` bleibt unverändert für seine anderen, legitimen Zwecke.

Verworfen: die Regel nach `segment_weather.py` zu verlagern (bricht die
#1329-Invariante frontal, alle weiteren Konsumenten erben sie unkontrolliert).

## Risiken & Nebenwirkungen

- **Golden-Neuerzeugung** in SMS und Mail überall dort, wo die Ankunftsstunde
  bisher fehlte — bewusste Änderung, kein Regressionsbefund (Präzedenz #1410).
- `tests/tdd/test_issue_807_reproduction.py::test_pills_respect_segment_window`
  und `test_issue_1146_badge_window_mismatch.py` müssen grün bleiben — sie
  sichern genau die Regel, die zur einzigen wird.
- **Kommentar-Drift:** `sms_trip.py:143-145` behauptet, die Werte stammten aus
  derselben Zeitreihe wie die Mail (`segment_weather.py:254-281`) — nach der
  Umstellung stimmt das erst wirklich; der Verweis ist zu korrigieren.
- **`compact_summary.py`** ist der in #1146 dokumentierte, nie geschlossene
  Nebenbefund — muss mit umgestellt werden, sonst bleibt eine dritte Quelle.
- Renderer-Commit-Gate #811 greift (`compact_summary.py`, `email/helpers.py`,
  `sms_trip.py` sind Mail-Inhalts-Dateien).
- Kleinerer Befund am selben Ort (aus #1417): unterschiedliche **Rundung** je
  Kanal — Mail `int()` (`helpers.py:1464,1473`), SMS `round()`
  (`tokens/metrics.py::_fmt_num`). 19,6 km/h → Mail „19", SMS „20".

## Offene Frage für die Spec

Ob die Rundungs-Divergenz im selben Zug behoben wird oder getrennt bleibt —
sie hat dieselbe Wurzel („ein Wert, zwei Ausgaben"), ist aber ein eigenes
Format-Thema und vergrößert die Golden-Änderung.
