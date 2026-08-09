# Kontext — #1651: Gewitter außerhalb des Tagesfensters in der Mail nennen

Stand: 2026-08-09, Basis `bcc4aeaf`. Alle Angaben unten sind **gemessen**, nicht hergeleitet;
wo etwas ungeprüft ist, steht es ausdrücklich dabei.

## Ausgangslage

Entstanden aus der Staging-Funktionsprobe zu #1498. Beide dort gemeldeten Widersprüche sind
behoben und belegt (A/B gegen die Elterncommits). Übrig blieb ein Widerspruch derselben
Familie in **umgekehrter Richtung**, gemessen an einer echt zugestellten Mail:

| Stelle in derselben Mail | Aussage zum 10.08.2026 |
|---|---|
| ⚡ Gewitter-Vorschau | `Kein Gewitter erwartet` |
| 🌙 Nacht am Ziel, Zeile `00` | roter Punkt `#b91c1c` = `ThunderLevel.HIGH` |

Beide Sätze sind für sich korrekt — das Gewitter lag um 00:00, außerhalb des Tagesfensters
04–19. Die Vorschau nennt ihr Fenster aber nicht.

**PO-Entscheidung 2026-08-09:** Nicht das Fenster beschriften, sondern das Nachtgewitter
**nennen, mit exakter Uhrzeit** — in E-Mail und Telegram. SMS zeigt es weiterhin nicht.

## Relevante Dateien

### Wo der Vorschau-Satz entsteht (genau zwei Stellen, wortgleich)

| Stelle | Datei:Zeile |
|---|---|
| Trend-Weg | `src/services/trip_report_scheduler.py:1838-1848` (`_thunder_entry_from_trend_row`) |
| Fetch-Weg | `src/services/trip_report_scheduler.py:2034-2041` (`_build_thunder_forecast`) |
| Orchestrierung beider | `trip_report_scheduler.py:1670` (`_build_thunder_forecast_from_trend_or_fetch`) |

Beide haben das aufgelöste Fenster bereits als lokale Variable (`resolve_configured_window`,
Zeile 1799 bzw. 2005). Die Klemmung sitzt in `:1789-1793` bzw. `outlook.py:353-360`.

### Wer den Eintrag liest

| Leser | Datei:Zeile | Gelesene Felder |
|---|---|---|
| Mail HTML | `src/output/renderers/email/html.py:1323` | `level`, `date`, `text`, `hail` |
| Mail Klartext | `src/output/renderers/email/plain.py:328` | dieselben |
| SMS | `src/output/renderers/sms_trip.py:461-483` | **nur** `level`, `hour`, `hail` — und nur `"+1"` |
| Telegram rich | — | liest den Eintrag **gar nicht** |

HTML und Klartext bekommen dasselbe Objekt (`email/__init__.py:150` und `:187`) — eine
Änderung an der Quelle erreicht beide.

### Die zweite Mail-Stelle: der Mehrtages-Ausblick

`outlook_active = show_outlook and bool(multi_day_trend)` (`email/html.py:1307-1312`,
`plain.py:308-309`). Ist er aktiv, **entfällt die Gewitter-Vorschau komplett**.
`multi_day_trend_reports` hat den Vorgabewert `["evening"]` (`app/loader.py:897`).

⇒ Morgen-Mail zeigt die Vorschau, Abend-Mail den Ausblick. Beide verschweigen das
Nachtgewitter, an verschiedenen Codestellen.

## 🔴 Gemessen: Mail und Telegram widersprechen sich heute schon

Eigene Messung mit identischen Eingangsdaten (Gewitter `HIGH` um 02:00 Ortszeit, Gehzeit
08–17, `metrics=None` = Trip-Standard):

```
row['thunder']        = NONE
row['hourly_thunder'] = [(2, 3.0)]

format_trend_tokens(row):
  thunder_word  = 'kein'
  thunder_token = 'hoch@2'

render_outlook_plain([row])   ->  "Mo  15–25°C  –  10  ⚡–"
narrow._outlook_lines([row])  ->  "Mo  15–25°C  R–  10  ⚡hoch@2"
```

Beide Zellen entstehen aus derselben Zeile und derselben Funktion. **Die Mail rendert das
Wort, Telegram das Token.** Telegram erfüllt die PO-Vorgabe damit bereits; zu bauen ist sie
nur in der E-Mail.

## Datenlage: kein neuer Netzabruf nötig

- `outlook.py:380-396` baut `hourly_thunder` **ungefiltert** über alle Punkte.
- `segment_weather.py:236-238` hält die Rohzeitreihe ungefiltert („OpenMeteo returns
  full-day (24h) data"); nur `.aggregated` wird auf die Gehzeit geklemmt.
- `openmeteo.py:993-1000` fragt nach Kalendertagen, nicht nach Stunden.

⇒ Die vollen 24 Stunden liegen an allen Bauwegen bereits vor, für `+1` und `+2`.

## 🔴 Das Rückfallrisiko in #1498

`night_weather` deckt Ankunft **heute** bis **06:00 des Folgetags** ab
(`segment_weather.py:436-441`), gebaut einmal pro Report aus `segment_weather[-1]`
(`trip_report_scheduler.py:876-878`, `preview_service.py:219-220`).

Die `+1`-Vorschau-Daten stammen aus einem **anderen** Abruf (`_build_stage_trend` bzw.
`_collect_future_stage_weather`). Für die Stunden **00:00–06:00 des Folgetags** behaupten
damit zwei Quellen etwas über dieselbe Stunde — exakt die Konstellation, die den
ursprünglichen #1498-Fehler erzeugte („ab 02:00" gegen „kein").

Beide laufen zwar über denselben Roh-Cache (`weather_cache.py:253-255`), ein Treffer ist
aber an Koordinate, Modell, Fensterabdeckung und TTL gebunden — **keine Garantie**.
*Nicht verifiziert:* ob im Ist-Zustand tatsächlich ein Cache-Treffer eintritt.

Für den Abend von `+1` (20:00–23:00) und für ganz `+2` gibt es keine Gegenquelle — dort kann
nichts widersprechen, aber auch nichts bestätigen.

## Bestehende Muster, die wiederverwendet werden

- **Additive Schlüssel im Eintrags-Dict:** `hail` (#1475) und `_gap_offsets` (#1482) sind
  Vorbilder für Felder, die die SMS ignoriert.
- **Fenster-Auflösung an einer Stelle:** `app/day_window.py:20-50`
  (`resolve_configured_window`, wrap-fähig seit #1361/#1372) und `:52-63` (`hour_in_window`).
- **Höchstes Level ermitteln:** `metric_format.max_thunder` / `thunder_ordinal` — nacktes
  `max()` wäre alphabetisch falsch.

## Was es NICHT gibt

Eine Notation, die ein Zeitfenster als Text benennt, existiert im ganzen Code nicht.
`⚡ möglich 4:00–19:00` (`compact_summary.py:578-586`) sieht so aus, ist aber die Spanne der
tatsächlichen Gewitterstunden (`min`/`max`) — **nicht** das Fenster. Verwechslungsgefahr.

## Angrenzende Befunde (nicht in dieser Scheibe)

- **„Metriken-Überblick"-Pille** (`email/helpers.py:1686-1730`): meldet
  `Gewitter ab 04:00 · stärkste 04:00`, während **keine** Tabelle der Mail eine Stunde vor
  08:00 zeigt. Ursache ist kein Klemmfehler, sondern die bewusste Absenkung der Untergrenze
  für das erste Segment (`day_window.py:117-129`, Absicht seit #1317/#1319). Eigener
  Sachverhalt, noch nicht verbucht.
- **Gewitter-Spalte fehlt bei einem neu angelegten Trip per Vorgabe** — Altbefund aus einem
  #1498-Kommentar, nie verbucht.

## Betroffene Tests

`tests/unit/test_thunder_forecast_day_window.py` (Zeilen 95,112,146,161,198,214),
`tests/tdd/test_thunder_forecast_low_level.py`, `tests/tdd/test_briefing_parity_night_thunder.py:55`,
`tests/tdd/test_bug_874_th_plus_sms.py`, `tests/unit/test_trip_report_formatter_v2.py:266`,
Golden-Snapshots `tests/golden/email/corsica-vigilance-{html,plain}.txt` und
`gr20-spring-morning-{html,plain}.txt`.
