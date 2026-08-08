# Context: Alarme schalten 2 Stunden nach Ankunft ab (#1584)

## Request Summary

Am 2026-08-07 zog ein Hagelgewitter (Böen bis 44 km/h, 21,5 mm Regen) über das
Tagesziel des laufenden Trips „KHW 403" — **kein einziger Alarm** ging raus.
Ursache ist nicht das Tageslimit aus #1555, sondern die Bindung des Alarmpfads
an ein hartcodiertes Zwei-Stunden-Fenster nach Ankunft.

## Analysis

### Type

**Bug** mit einer Design-Entscheidung (welches Zeitfenster gilt für Alarme).

### Belegte Ursachenkette

| Stelle | Befund |
|---|---|
| `src/services/trip_segments.py:258` | Ziel-Segment endet hart bei `arrival_time + timedelta(hours=2)`. Ursprünglich Aktivitäts-Marker für den Radar-Check (#822), inzwischen faktisch die einzige Quelle für „Wetter am Zielort". |
| `src/services/segment_weather.py:254-271` | `_aggregate_for_segment` filtert strikt auf `[start_floor, end_floor)` des Segments — obwohl `timeseries` desselben Objekts **24 Stunden** enthält. |
| `src/services/weather_change_detection.py:43,593-607` | Alarmregeln lesen ausschließlich `aggregated`. Folge: die Regel `thunder_level` kann **strukturell nie** auslösen, wenn das Gewitter nach Ankunft+2h liegt. |
| `src/services/trip_alert.py:964-969` | Deviations-Fetch überspringt alle Segmente mit `end_time < now` → leere Liste → `No fresh weather data`. |
| `src/services/trip_alert.py:737-750` | Radar-Pfad bricht bei „alle Segmente vorbei" ab (Z. 741-745) — **vor** der Ruhezeiten-Prüfung (Z. 748), die dadurch nie erreicht wird. |

### 🔴 Widerlegt — nicht Gegenstand

„Das Briefing verschweigt die Gefahr" ist durch eine Staging-Gegenprobe
**widerlegt** (Issue-Kommentar 3): Die zugestellte Mail enthält Gewittersymbole,
Böen bis 44 km/h und 21,5 mm Regen im Nacht-Block, dazu Hinweise in Kopfzeile
und Metriken-Überblick. Der Nacht-Block holt seine Daten über
`fetch_night_weather()` (Ankunft → 06:00 Folgetag), unabhängig vom
Segment-Zuschnitt. **Kein Renderer-Fix nötig.**

Die falsche Behauptung entstand aus dem Lesen einer Zwischendatei statt der
zugestellten Nachricht — dieselbe Fehlerklasse, die bei #1555 drei
Arbeitsstränge fehlgeleitet hat.

### PO-Entscheidungen (2026-08-07, verbindlich)

- Beobachteter Ort außerhalb der Gehzeit: **das Tagesziel**
- Maßgebliches Zeitfenster: **das Tagesfenster** (`day_window_start_hour`/
  `-end_hour`, Default 4/19), nicht die Etappenzeit

### Technischer Ansatz (Empfehlung)

**Das Ziel-Segment-Ende von `arrival_time + 2h` auf die ortszeit-aufgelöste
`day_window_end_hour` umstellen** (`trip_segments.py:258`).

Warum diese Stelle: Beide Alarmpfade und die Aggregation lesen
`segment.end_time`. Eine Korrektur an der Quelle zieht Alarm, Aggregation und
Anzeige automatisch auf denselben Zeitbegriff — ohne dass diese Dateien selbst
angefasst werden. Der Provider liefert ohnehin volle 24 Stunden, es entsteht
kein zusätzlicher Abruf.

**Zeitzone:** Kein neuer Helfer nötig. `trip_segments.py:181-191` enthält das
Muster bereits (`tz_for_coords(lat, lon)` → lokale Zeit → `.astimezone(utc)`).

**Verworfen:**
- *Zweites Fenster an `_aggregate_for_segment` durchreichen* — erodiert den
  dokumentierten Vertrag („Aggregat entsteht aus GENAU diesem Fenster") und
  schafft eine neue Diskrepanz zwischen Anzeige- und Alarm-Fenster. Genau die
  Fehlerklasse, die dieses Issue aufgedeckt hat.
- *Separater „Aufenthalt am Ziel"-Datensatz* — größter Eingriff, dupliziert
  Aggregationslogik mit Divergenz-Risiko, löst die strukturelle Bindung nicht.

### 🔴 Kollision mit #1329 geprüft — besteht nicht

`tests/unit/test_forecast_cache_sharing.py:385-457` fordert, dass Aggregat und
Identität aus dem **eigenen** Segment-Fenster des jeweiligen Aufrufers
entstehen — Schutz gegen Kontamination zwischen Trip und Ortsvergleich. Die
Absicht gilt **pro Aufrufer**, nicht **pro Segmentgröße**. Ein größeres, aber
weiterhin eindeutig zugeordnetes Fenster verletzt sie nicht. Keine Ablösung
nötig, die Tests bleiben grün.

(Der verworfene Ansatz „zweites Fenster" hätte hier zwar auch keinen Test rot
gemacht — aber die Schutz*absicht* unterlaufen. Der Unterschied zwischen „Tests
bleiben grün" und „Schutz bleibt gültig" war die Kernfrage.)

### Ruhezeiten vs. Tagesfenster — Empfehlung revidiert

Meine erste Empfehlung („Tagesfenster ersetzt Ruhezeiten für Alarme") ist
**zurückgezogen.** Gegenargument, das sie schlägt:

Ruhezeiten sind eine **explizit gesetzte Nutzereinstellung**, das Tagesfenster
meist ein unangetasteter Default (beim KHW-Trip nicht gesetzt). Wer seine
Ruhezeiten bewusst auf 22–05 gestellt hat, bekäme bei einer Ablösung plötzlich
Alarme zwischen 19 und 22 Uhr — eine Regression, die größer wäre als der
behobene Fehler.

Zudem sind es zwei verschiedene Fragen: Das Tagesfenster ist ein
**Daten-Geltungsbereich** („welche Stunden zählen als heute am Ziel"), die
Ruhezeiten ein **Zustellungs-Gate** („darf mich jetzt etwas erreichen").

**Empfehlung: beide gelten (Schnittmenge, ≈6–19 Uhr bei Standardwerten).** Das
Regel-Budget ist gewahrt, weil das Tagesfenster den Segment-Zuschnitt ablöst —
eine Regel ersetzt eine andere, nur eben nicht die Ruhezeiten. Entscheidung
liegt beim PO in der Spec.

**Nebenbefund:** `deviation_alert_engine.py:78-106` rechnet Ruhezeiten hart in
`Europe/Vienna`, nicht in der Ortszeit des Ziels. Bestehender Sonderfall, nicht
Gegenstand dieser Scheibe, aber relevant für Trips außerhalb Mitteleuropas.

### Affected Files — Scheibe 1

| File | Change | Beschreibung |
|------|--------|--------------|
| `src/services/trip_segments.py:258` | MODIFY | Ziel-Segment-Ende auf ortszeit-aufgelöste `day_window_end_hour`; Randfall „Ankunft nach Fensterende" analog zum bestehenden Mitternachts-Guard (Z. 193-204) |
| `tests/unit/test_destination_segment.py:101-109` | MODIFY | `test_destination_segment_time_window` fixiert heute die 2 Stunden — muss auf das neue Verhalten umgeschrieben werden |
| *(neu)* E2E-Test am Sendepfad | CREATE | s.u. |

- Scope: 3 Dateien, ~60–90 LoC
- Risk: **MEDIUM** — nutzersichtbare Nebenwirkung (s.u.)

### Wie die Wirkung nachgewiesen wird

Der Test muss am **Alarm-Sendepfad** hängen, nicht am Briefing — das zeigt die
Gefahr bereits heute korrekt und wäre auch ohne Fix grün.

```
GEGEBEN  Trip, dessen letztes Segment vor 17:00 Ortszeit endet (Ankunft 13:18),
         Tagesfenster 4–19, Fixture liefert um 17:00 thunder_level=HIGH
WENN     der Alarm-Check zu einer simulierten Zeit von 17:05 Ortszeit läuft
DANN     wird tatsächlich ein Alarm ausgeliefert (sent == True)

GEGENPROBE (muss weiterhin ausbleiben)
WENN     dieselbe Prüfung um 22:00 Ortszeit läuft
DANN     kein Alarm — außerhalb des Tagesfensters
```

Heute rot, weil Ankunft+2h < 17:00 → Segment übersprungen. Vorbild für einen
Test über echte Produktionspfade: `test_forecast_cache_sharing.py:460+`.

### Risks & Considerations

- **Nutzersichtbare Nebenwirkung:** Zielsegment-Zeile und Highlights im
  Trip-Report zeigen künftig Aggregate über ein 5–15-Stunden-Fenster statt über
  2 Stunden. Gewollt — es beseitigt die Diskrepanz (Segment 0,0 mm vs.
  Metriken-Überblick 8,9 mm für denselben Tag), aber der PO sollte es wissen.
- **Ein bestehender Test fixiert die 2 Stunden** und muss bewusst umgeschrieben
  werden — kein Nebenbei-Anpassen.
- **Nicht einzeln verifiziert:** weitere `aggregated`-Konsumenten
  (`risk_engine.py`, `corridor_threshold.py`, `day_comparison.py`,
  `point_weather.py`) könnten für das Zielsegment andere Schwellen auslösen.
  Restrisiko, durch die bestehende Suite teilweise abgedeckt.
- **Nicht belegt:** ob das SMS-Zeichenbudget bei größeren Niederschlagswerten
  Formatierungsprobleme bekommt.

### Folge-Scheiben (nicht in Scheibe 1)

1. Ruhezeiten-Prüfung im Radar-Pfad **vor** den Segment-Check ziehen
   (`trip_alert.py:737-750`) — verhindert, dass die Architektur denselben
   Fehler erneut ermöglicht. ~10 LoC.
2. Tagesfenster beim Trip-Anlegen editierbar machen
   (`WeatherMetricsTab.svelte:1244`) — durch die Alarmrelevanz aufgewertet.
3. Prüfen, ob der Compare-Pfad dieselbe Zeitfenster-Bindung hat.

### Open Questions (für die Spec-Freigabe)

- [ ] Ruhezeiten: Schnittmenge (empfohlen) oder Ablösung?
- [ ] Ist die geänderte Darstellung der Ziel-Zeile im Briefing so gewollt?
