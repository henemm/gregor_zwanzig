# Kontext: #2036 — Alarm-Kurzform nennt Kilometer statt Segmentnummer

Workflow: `fix-2036-alarm-kilometer` · Branch `fix-2036-alarm-kilometer` · Issue #2036
Termin: Tour startet **2026-08-23**.

## Symptom

Alarm-Kurzmeldungen an Telegram-Kurzform, SMS und Premium-SMS tragen als Ortsangabe eine
Segmentnummer:

```
Ziel: G56->78@16 TH:-->H
Seg 3: R@11:30
Seg 4: G31->70@13 VS4400->540
```

Auf einem Garmin inReach ist nicht erkennbar, wo Segmentgrenzen liegen. Die Meldung ist damit
nicht verortbar.

## Analysis

### Type

Bug (nutzersichtbares Fehlverhalten), mit einem Datenmangel als Ursache.

### Ursache in zwei Schichten

**Schicht 1 — die Anzeige bevorzugt die Segmentnummer.**
`src/output/renderers/alert/segments.py:91-111` `format_alert_location()` löst in der
Reihenfolge `location_label` → `Segment N` → `km A–B` auf. Kilometer liegen jedem Alarm
bereits bei (`AlertEvent.km_from/km_to`, `src/output/renderers/alert/model.py:11-32`), sind
aber nur letzte Rückfallstufe. Die Umstellung allein wäre trivial.

**Schicht 2 — die vorhandenen Kilometer sind unbrauchbar.**
`src/services/trip_segments.py:225` rechnet `haversine_km()` zwischen aufeinanderfolgenden
Wegpunkten: **Luftlinie**, nicht Wegstrecke.

Messung an 13 realen Etappen (Luftlinie gegen echte GPX-Trackdistanz):

| | Luftlinie | Wegstrecke | Faktor |
|---|---|---|---|
| Etappe 06 | 11,6 km | 18,6 km | 1,59 |
| Etappe 02 | 7,6 km | 11,6 km | 1,53 |
| Etappe 01 | 7,2 km | 8,7 km | 1,22 |

Spanne 1,17–1,59 — kein pauschaler Korrekturfaktor möglich. Eine km-Angabe aus Luftlinie wäre
glaubwürdig aussehender Unsinn und damit **schlechter** als die heutige Segmentnummer.

### Schlüsselbefund: die richtige Zahl entsteht bereits und wird verworfen

Die Wegpunkte eines importierten Trips sind keine genäherten Punkte, sondern **exakt
Original-Trackpunkte** (gemessener Projektionsabstand **0,0 m**). Grund:
`src/core/segment_builder.py:118` setzt `start_point=points[seg_start_idx]` — das
Original-`GPXPoint` samt korrektem `distance_from_start_km` aus `src/core/gpx_parser.py:155`.

`src/services/gpx_processing.py:105-165` `segments_to_trip()` baut daraus Wegpunkte mit nur
`lat/lon/elevation_m/time_window` — **die Distanz wird 40 Zeilen nach ihrer Berechnung
weggeworfen.** Es braucht keine Projektion und keinen gespeicherten Track, nur ein Feld mehr.

Verworfen: Track ausdünnen und speichern (Längenverlust −3,6 % bei jedem 2. Punkt bis −28 %
bei jedem 8. — Serpentinen); `weather_snapshot` als Quelle (spiegelt nur die Luftlinie zurück,
`src/services/weather_snapshot.py:457-462`).

### Warum ein Re-Import keine Option ist

Für eine **bestehende** Etappe existiert kein Re-Import-Weg. Im Bearbeiten-Modus hängt ein
Upload eine **zusätzliche** Etappe an (`frontend/src/lib/components/edit/EditRouteSection.svelte:78-89`,
reines `push`, Datum aus „letzte Etappe + 1"). Go ersetzt danach das Stages-Array blind
(`internal/handler/trip.go:288-291`). Wer den alten Stand loswerden will, muss löschen — und
verliert dabei nachweislich: Wegpunkt-Namen (`gpx_processing.py:130-135` überschreibt mit
`Start`/`Seg N Start`/`Ziel`), `time_window` (`:137-140`), `arrival_override` und
`arrival_calculated` (fehlen im Rückgabe-Dict `:223-232`), `confirmed`
(`src/services/route_analyzer.py:43` setzt hart `False`), manuell ergänzte Wegpunkte,
Wegpunkt-IDs, Etappenname, Etappendatum, Etappen-`id`, `start_time`.

⇒ Eine Lösung, die nur beim Import füllt, ist für jeden Bestandstrip wirkungslos.

### Nachrüstung ohne Re-Import ist machbar

Hochgeladene GPX-Dateien bleiben dauerhaft unter `data/users/<user_id>/gpx/` liegen
(`api/routers/gpx.py:40`), werden nie aufgeräumt (`DeleteTrip` rührt sie nicht an). Eine
persistierte Zuordnung Datei↔Trip gibt es **nicht**.

Die Zuordnung lässt sich geometrisch herstellen: der passende Track enthält **alle** Wegpunkte
einer Etappe exakt. Gemessen: richtige Datei worst-case **0,0 m**, jede falsche Datei
**≥ 4.672 m** — drei Größenordnungen Trennschärfe. Kosten: ~10 ms Parse je Datei, ~37 ms für
einen kompletten Etappensatz.

Grenzen (jeweils fail-safe, nie falsche Zahlen):
- Von Hand ergänzte Wegpunkte liegen nicht auf dem Track
  (`frontend/src/lib/utils/waypointEditor.ts:70-74` interpoliert linear;
  `EditStagesPanelNew.svelte:610-620` setzt beliebige Kartenpunkte) ⇒ keine Zuordnung.
- Mehrdeutigkeit möglich, wenn zusätzlich eine Gesamt-GPX über alle Etappen hochgeladen wurde
  (dieselben Punkte, andere km) ⇒ bei mehr als einem Treffer nicht raten.
- Gleichnamige Uploads überschreiben sich stumm (`gpx_processing.py:66-69`).

### Auflösungsreihenfolge (Ergebnis der Analyse)

1. Wegpunkt trägt eine gemessene Wegstrecke → nutzen
2. sonst: eindeutig passenden Track im GPX-Bestand suchen → nutzen und einmalig
   zurückschreiben (Read-Modify-Write, additiv)
3. sonst: Etappe gilt als **unvermessen** → Ortsangabe bleibt `Segment N` (heutiges Verhalten)

Kilometer zählen **je Etappe ab 0** (PO-Vorgabe). Das Ziel-Segment behält `🏁 Ziel`
(`trip_segments.py:312-325` setzt dort `km_from == km_to`; „km 20–20" wäre eine
Verschlechterung).

### Echtheits-Kennzeichnung ist zwingend

`GPXPoint.distance_from_start_km` (`src/app/models.py:369`) hat Default `0.0` — „nicht
gesetzt" und „Kilometer 0" sind heute ununterscheidbar. Nötig:
- `Waypoint.distance_from_start_km: Optional[float] = None` (`None` = unbekannt)
- `TripSegment.distance_measured: bool = False`, durchgereicht über `weather_snapshot`
  (`:457-462`, `:521-535`) und die vier Event-Typen als `km_measured: bool = False`

Default-`False` ist zugleich der Terminschutz: alle Bestandstests bleiben unverändert grün,
weil keiner gemessene Daten baut.

### Affected Files

| Datei | Art | LoC | Anmerkung |
|---|---|---|---|
| `src/services/gpx_processing.py` | MODIFY | 8 | echte km je Waypoint durchreichen |
| `src/app/trip.py` | MODIFY | 3 | **schema-relevant** |
| `src/app/loader.py` | MODIFY | 4 | **schema-relevant**, lesen + schreiben |
| `internal/model/trip.go` | MODIFY | 3 | **schema-relevant** — ohne dies wischt jedes `SaveTrip` den Wert (vgl. `suggestion_reason`, existiert in Python, fehlt in Go, wird stumm verworfen) |
| `src/app/models.py` | MODIFY | 3 | **schema-relevant** |
| `src/services/trip_segments.py` | MODIFY | 30 | km aus Wegpunkten statt Luftlinie, Normierung auf 0 je Etappe, Plausibilitätsprüfung |
| *(neu)* Track-Auflösung | CREATE | ~60 | Zuordnung + Rückschreiben |
| `src/services/weather_snapshot.py` | MODIFY | 4 | Flag mitschreiben/-lesen |
| `src/output/renderers/alert/model.py` | MODIFY | 5 | `km_measured` an vier Event-Typen |
| `src/output/renderers/alert/project.py` | MODIFY | 6 | Flag durchreichen |
| `src/services/trip_alert.py` | MODIFY | 12 | Flag + `segment_km`-Karte für amtliche Warnungen |
| `src/output/renderers/alert/segments.py` | MODIFY | 14 | neue Reihenfolge |
| `src/output/renderers/alert/render.py` | MODIFY | 12 | Flag weiterreichen; `km{a}-{b}` → `km {a}–{b}` (`:998-1008`) |
| `src/output/renderers/alert/official_alerts.py` | MODIFY | 20 | additiver Parameter `segment_km` |

Produktion ~184 LoC, Tests ~130 ⇒ **LoC-Override auf 500 nötig** (Limit 250).

### Plausibilitätsprüfung (fängt Nachbearbeitung ab)

In `convert_trip_to_segments`: gemessene Spanne zweier Wegpunkte muss streng monoton steigen
**und** ≥ der Luftlinie zwischen ihnen sein (ein Track kann nie kürzer als die Gerade sein).
Verletzt eine Etappe das, gilt sie als unvermessen. Fängt Einfügen, Umsortieren und
Koordinaten-Edits strukturell ab, ohne Write-Seam-Logik in Go.

### Unteilbar — kein Aufteilen auf zwei Scheiben

`tests/tdd/test_alert_location_vocabulary.py:296-298` verlangt **Gleichheit** der Ortsangabe
von Nowcast, Abweichungsalarm und amtlicher Warnung (Teilungs-Invariante aus #1744);
`:514/525-533` dieselbe Auflösung in Betreff und SMS. Der amtliche Pfad kann also nicht
später folgen. Ein Deploy ohne `internal/model/trip.go` verlöre die Werte beim ersten Save.

### Bestehende Tests, die `Segment N`/`Seg N` prüfen (müssen grün bleiben)

`tests/tdd/test_alert_location_vocabulary.py` (zentraler Ratschen-Test) ·
`tests/tdd/test_alert_sms_segment_head.py:177` · `tests/tdd/test_alert_segment_reference.py` ·
`tests/tdd/test_official_alert_sms_ortskopf.py:94` ·
`tests/tdd/test_official_alert_template_render.py` ·
`tests/unit/test_official_alert_output_unchanged.py` + Snapshot
`tests/fixtures/official_alert_render_snapshot_1944.json:6` ·
`tests/tdd/test_feature_574_segment_km_header.py` · `tests/tdd/test_952_onset_alert_fidelity.py` ·
`tests/tdd/test_onset_shift_alert.py` · `tests/tdd/test_alert_addendum_sms.py` ·
`tests/tdd/test_radar_alert_telegram_style.py`

### Risk Level

MEDIUM — additiv und default-aus, aber schema-relevant in zwei Sprachen.

Bekannte Risiken:
1. Go-Modell vergessen ⇒ erster Editor-Save wischt alle km. Muss im selben Deploy raus.
2. `loader.py:130` ersetzt Listen wholesale ⇒ Telegram-Kommandos
   (`trip_command_processor.py:1245`) würden km löschen. Gleiche Kopplung.
3. Briefing-Segmentkopf (Feature #574) zeigt heute dieselben falschen Luftlinien-km und wird
   durch dieselbe Änderung richtig — sichtbare Änderung, gewollt.
4. Ohne auffindbaren Track bleibt alles wie heute. Das ist die Fallback-Garantie, kein Bug.

### Nicht Teil dieses Tickets

- **Naismith rechnet weiter auf Luftlinie** (`src/core/naismith.py:119`,
  `internal/model/naismith.go:118`) ⇒ Ankunftszeiten sind um denselben Faktor zu früh.
  Nutzersichtbar, eigenes Issue.
- `official_alerts.py:2137-2147` `_trip_total_segment_ids()` zählt über alle Etappen, während
  Segmentnummern je Etappe vergeben werden ⇒ „gesamte Route"-Verdichtung greift bei
  mehrtägigen Touren nie. Vorbestehender Nebenbefund → #1199.

### Open Questions

Keine offenen Fragen an den PO. Freigegeben: echte Wegstrecke (nicht Luftlinie, kein
Korrekturfaktor), Kilometerzählung je Tag ab 0, keine Lösung, die auf dem aktuellen
Konfigurationsstand einer konkreten Tour aufbaut.
