---
entity_id: fix_2036_alarm_kilometer_ortsangabe
type: bugfix
created: 2026-08-21
updated: 2026-08-21
status: draft
version: "1.0"
tags: [alarm, sms, telegram, gpx, kilometer]
workflow: fix-2036-alarm-kilometer
---

# Alarm-Kurzform: gemessene Kilometer statt Segmentnummer als Ortsangabe

## Approval

- [x] Approved — PO Henning, 2026-08-21 („freigabe")

## Purpose

Alarm-Kurzmeldungen an Telegram-Kurzform, SMS und Premium-SMS zeigen heute als Ortsangabe eine
Segmentnummer (`Seg 3`), die auf einem Garmin inReach nicht verortbar ist — der Nutzer kann nicht
erkennen, wo Segmentgrenzen entlang der Tour liegen. Diese Spec ersetzt die Ortsangabe durch eine
**gemessene** Kilometer-Spanne entlang der echten Wegstrecke (`km 12-20`), aber ausschließlich
dort, wo eine belastbare, aus GPX-Trackdaten stammende Distanz vorliegt. Ohne belastbare Messung
bleibt die heutige Segmentnummer unverändert stehen — eine aus Luftlinie erfundene
Kilometerangabe wäre glaubwürdig aussehender Unsinn und damit schlechter als der Status quo.

## Source

- **File:** `src/output/renderers/alert/segments.py`
- **Identifier:** `format_alert_location()` (:91-111)

> **Schicht-Hinweis:** Python-Core / Domain-Backend
> (`src/output/renderers/alert/`, `src/services/`, `src/app/`) für Datenherkunft, Auflösung und
> Persistenz. Zusätzlich **Go-API** (`internal/model/trip.go`), da die Wegstrecke am Waypoint
> auch dort modelliert werden muss — ohne das Go-Feld wischt der erste Editor-Save (`SaveTrip`)
> den Wert wieder weg (Präzedenzfall: `suggestion_reason`, existiert in Python, fehlt in Go, wird
> stumm verworfen).

## Estimated Scope

- **LoC:** ~184 Produktion, ~130 Tests (Limit 250 reicht nicht; **LoC-Override auf 500 bereits
  gesetzt**)
- **Files:** 13 (siehe Affected Files unten)
- **Effort:** medium — additiv und default-aus, aber schema-relevant in zwei Sprachen (Python +
  Go)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/core/gpx_parser.py` (`GPXPoint.distance_from_start_km`) | module | Liefert die bereits korrekt berechnete Wegstrecke je Original-Trackpunkt, wird bislang nach dem Segment-Bau verworfen |
| `src/core/segment_builder.py` | module | Übergibt Original-`GPXPoint`s (inkl. Distanz) an die Segmentbildung, unverändert |
| `src/services/gpx_processing.py` (`segments_to_trip`) | module | Baut Waypoints aus GPX-Segmenten; muss die Distanz zusätzlich zu lat/lon/elevation durchreichen |
| `src/services/trip_segments.py` (`convert_trip_to_segments`) | module | Bisherige Quelle der Luftlinien-km (`haversine_km`); wird um gemessene km, Etappen-Normierung auf 0 und Plausibilitätsprüfung erweitert |
| *(neu)* Track-Auflösungs-Service | module | Ordnet Bestandstrips ohne gemessene Distanz eindeutig einen GPX-Track aus `data/users/<user_id>/gpx/` zu und schreibt das Ergebnis einmalig zurück |
| `src/services/weather_snapshot.py` | module | Muss das Echtheits-Flag beim Speichern und Rekonstruieren des Snapshots mitführen |
| `src/output/renderers/alert/model.py` (`AlertEvent`) | module | Vier Event-Typen bekommen das Feld `km_measured` |
| `src/output/renderers/alert/project.py` | module | Reicht das Flag von der Datenquelle in die Event-Projektion durch |
| `src/services/trip_alert.py` | module | Baut die `segment_km`-Karte für amtliche Warnungen inkl. Flag |
| `src/output/renderers/alert/segments.py` (`format_alert_location`) | module | Neue Auflösungsreihenfolge: gemessene km vor Segmentnummer |
| `src/output/renderers/alert/render.py` | module | Format-Vereinheitlichung `km A-B` (Leerzeichen), Flag-Weiterreichung |
| `src/output/renderers/alert/official_alerts.py` | module | Amtliche Warnungen nutzen dieselbe Ortsangabe wie Nowcast/Abweichungsalarm (Teilungs-Invariante #1744) |
| `internal/model/trip.go` | module | Go-Gegenstück zum Python-Waypoint-Feld — schema-relevant, ohne dies Datenverlust beim ersten Editor-Save |

## Implementation Details

**Auflösungsreihenfolge je Wegpunkt (Ergebnis der Analyse in
`docs/context/fix-2036-alarm-kilometer.md`):**

1. Der Wegpunkt trägt bereits eine gemessene Wegstrecke (`distance_from_start_km is not None`)
   → nutzen.
2. Sonst: im GPX-Bestand des Nutzers (`data/users/<user_id>/gpx/`) wird nach einem Track
   gesucht, der **alle** Wegpunkte der Etappe innerhalb einer Toleranz von **10 m** enthält
   (Begründung siehe „Festgelegte Schwellenwerte"). Bei **genau einem** Treffer wird die gemessene Distanz übernommen und einmalig
   additiv an den Trip zurückgeschrieben (Read-Modify-Write mit Merge, niemals Replace). Bei
   **null oder mehr als einem** Treffer wird nicht geraten.
3. Sonst gilt die Etappe als **unvermessen** — die Ortsangabe bleibt `Segment N` /
   `Seg N` (heutiges Verhalten, byte-identisch).

**Kilometerzählung je Etappe ab 0.** `convert_trip_to_segments` normiert die gemessene Distanz
auf den Etappenstart (PO-Vorgabe: „jeder Tag zählt neu seine Kilometer"), unabhängig von der
kumulierten Gesamtstrecke der Tour. Das Etappenziel behält die bestehende Sonderbehandlung
`🏁 Ziel` (`km_from == km_to`), auch wenn die Etappe vermessen ist — `km 20-20` wäre eine
Verschlechterung gegenüber dem heutigen Symbol.

**Plausibilitätsprüfung fängt Nachbearbeitung ab.** Für zwei aufeinanderfolgende Wegpunkte einer
Etappe muss die gemessene Spanne streng monoton steigen **und** mindestens so groß sein wie die
Luftlinie zwischen ihnen (ein Track kann nie kürzer als die direkte Verbindung sein). Verletzt
eine Etappe diese Regel — etwa durch einen nachträglich eingefügten, verschobenen oder manuell
gesetzten Wegpunkt (`frontend/src/lib/utils/waypointEditor.ts:70-74` interpoliert linear,
`EditStagesPanelNew.svelte:610-620` setzt beliebige Kartenpunkte) — gilt die **gesamte Etappe**
als unvermessen, auch wenn einzelne Wegpunkte für sich genommen plausibel wären.

**Echtheits-Kennzeichnung, damit „unbekannt" nie mit „Kilometer 0" verwechselt wird.**
`Waypoint.distance_from_start_km` wird `Optional[float] = None` (statt des heutigen
Default-`0.0` in `GPXPoint`); `None` heißt „nicht gemessen". Ein zusätzliches boolesches Flag
(`distance_measured` am `TripSegment`, `km_measured` an den vier `AlertEvent`-Typen) läuft
additiv von der Datenquelle über `weather_snapshot` (Speichern **und** Rekonstruieren) bis zum
Renderer mit. Default `False` ist zugleich der Terminschutz: solange kein Code aktiv gemessene
Daten baut, bleibt jeder Bestandstest unverändert grün.

**Format-Vereinheitlichung.** `render.py` schreibt heute `km12-20` ohne Leerzeichen; das wird
auf `km 12-20` angeglichen (SMS-Schreibweise nach `_ascii()`: Bindestrich, Leerzeichen nach
„km"). Der Ratschen-Test `test_alert_location_vocabulary.py:534`, der per
`re.search(r"km\d", sms)` genau die alte, leerzeichenlose Schreibweise verbietet, bleibt dadurch
grün statt (wie bei unveränderter Schreibweise) permanent rot.

**Amtliche Warnungen teilen dieselbe Auflösung.** Die Teilungs-Invariante aus #1744
(`test_alert_location_vocabulary.py:296-298`) verlangt Gleichheit der Ortsangabe zwischen
Nowcast-Alarm, Abweichungsalarm und amtlicher Warnung. `official_alerts.py` bekommt daher einen
additiven Parameter `segment_km`, der aus derselben Quelle gespeist wird — kein separater,
zweiter Auflösungspfad. Das Ticket ist deshalb **nicht in zwei Scheiben teilbar**: ein Deploy
ohne `official_alerts.py` oder ohne `internal/model/trip.go` bricht entweder die
Gleichheits-Invariante oder verliert die Werte beim ersten Trip-Save.

## Expected Behavior

- **Input:** Ein Alarm-Event (Nowcast, Abweichungsalarm oder amtliche Warnung) für ein Segment
  einer Etappe, deren Wegpunkte entweder eine gemessene Wegstrecke tragen, eindeutig einem
  GPX-Track im Bestand des Nutzers zuordenbar sind, oder keines von beidem.
- **Output:** Die Kurzform-Ortsangabe zeigt `km A-B` (mit Leerzeichen), wenn eine plausible
  gemessene Spanne vorliegt; sonst unverändert `Segment N` / `Seg N`. Das Ziel-Segment zeigt
  weiterhin `🏁 Ziel`. E-Mail-Betreff, Telegram-rich und amtliche Warnungen folgen derselben
  Auflösung.
- **Side effects:** Bei erfolgreicher Track-Zuordnung wird die gemessene Distanz einmalig
  additiv an den betroffenen Trip zurückgeschrieben (Read-Modify-Write mit Merge). Kein anderer
  Feld-Verlust, kein Netzabruf, keine Änderung an nicht betroffenen Trips.

## Festgelegte Schwellenwerte

| Größe | Wert | Begründung |
|---|---|---|
| Zuordnungs-Toleranz Wegpunkt ↔ Track | **10 m** | Wegpunkte importierter Etappen sind Original-Trackpunkte, gemessener Abstand **0,0 m**; die nächstbeste (falsche) Datei liegt bei **≥ 4.672 m**. 10 m deckt Koordinatenrundung ab und liegt drei Größenordnungen unter dem Fehlerfall. |
| Rundung der km-Anzeige | **ganze Kilometer** (`int(round(...))`) | Unverändert zur heutigen km-Rückfallstufe; Nachkommastellen kosten SMS-Zeichen ohne Erkenntnisgewinn. |
| SMS-Längengrenze | **140 Zeichen** (`render.py:1020`) | Bestand. `Seg 3` (5 Zeichen) → `km 12-20` (8 Zeichen) bleibt unkritisch. |

## Acceptance Criteria

- **AC-1:** Given ein Alarm-Event hat für sein Segment eine gemessene, plausible
  Kilometer-Spanne (`km_measured=True`) / When die Kurzform-Ortsangabe aufgelöst wird
  (Telegram-Kurzform, SMS, Premium-SMS) / Then zeigt sie `km A-B` (Bindestrich, Leerzeichen nach
  „km", `_ascii()`-Schreibweise) statt `Seg N`, wobei A und B wie bisher auf **ganze Kilometer**
  gerundet werden (`int(round(...))`, unverändert zur heutigen Rückfallstufe — Nachkommastellen
  kosten SMS-Zeichen ohne Erkenntnisgewinn auf dem Gerät).
  - Test: Ein Nowcast-Alarm für ein vermessenes Segment mit den Grenzen 12,31 km und 20,00 km
    wird über die Kurzform-Renderer formatiert; der erzeugte Text enthält `km 12-20` in exakt
    dieser Schreibweise und nicht mehr `Seg N`.

- **AC-2:** Given dieselbe Auflösungsfunktion wird auch für E-Mail-Betreff und Telegram-rich
  verwendet / When ein Segment eine gemessene Kilometer-Spanne trägt / Then ändern sich Betreff
  und Telegram-rich-Text ebenfalls auf die km-Angabe.
  - Test: Für ein vermessenes Segment werden Betreff-Renderer und Telegram-rich-Renderer
    aufgerufen; beide zeigen dieselbe km-Angabe wie die Kurzform, nicht mehr die Segmentnummer.

- **AC-3:** Given Nowcast-Alarm, Abweichungsalarm und amtliche Warnung beziehen sich auf
  dasselbe vermessene Segment / When alle drei Alarmarten ihre Ortsangabe rendern / Then zeigen
  alle drei identisch `km A-B` (Ratschen-Test `test_alert_location_vocabulary.py:296-298`
  verlangt Gleichheit über alle drei Alarmarten).
  - Test: Für dasselbe vermessene Segment werden Nowcast-, Abweichungs- und amtlicher
    Warnungs-Renderer aufgerufen; ein String-Vergleich der drei Ortsangaben ergibt Gleichheit.

- **AC-4:** Given das letzte Segment einer Etappe hat `km_from == km_to` (Etappenziel) / When
  die Ortsangabe für dieses Segment aufgelöst wird, auch wenn die Etappe vermessen ist / Then
  bleibt die Anzeige `🏁 Ziel` und wird nicht durch `km 20-20` ersetzt.
  - Test: Ein vermessenes Etappenziel-Segment wird formatiert; die Ausgabe enthält weiterhin das
    Symbol `🏁 Ziel` und keine km-Spanne mit identischem Start- und Endwert.

- **AC-5:** Given eine gemessene km-Spanne wird in der SMS-Kurzform gerendert / When der Text
  erzeugt wird / Then folgt er dem Muster `km A-B` mit Leerzeichen nach „km" (nicht `kmA-B` wie
  bisher), und der Ratschen-Test, der `re.search(r"km\d", sms)` als Verstoß wertet, bleibt grün.
  - Test: Der bestehende Ratschen-Test `test_alert_location_vocabulary.py:534` läuft gegen eine
    erzeugte SMS mit gemessener km-Angabe und bleibt grün (kein Treffer für `km` direkt gefolgt
    von einer Ziffer).

- **AC-6:** Given ein Nutzer importiert eine neue Etappe per GPX-Upload / When die Waypoints aus
  dem Track gebaut werden / Then trägt jeder gespeicherte Waypoint sein `distance_from_start_km`
  aus dem Original-Trackpunkt sowohl im Python-Datenmodell als auch im Go-Modell
  (`internal/model/trip.go`), und ein anschließender Editor-Save über die Go-API löscht den Wert
  nicht.
  - Test: Eine Etappe wird per GPX importiert, anschließend über die Go-API gespeichert
    (`SaveTrip`); vor und nach dem Speichern trägt jeder Waypoint denselben
    `distance_from_start_km`-Wert.

- **AC-7:** Given ein Bestandstrip ohne gemessene Wegstrecke am Waypoint und genau eine
  GPX-Datei unter `data/users/<user_id>/gpx/`, deren Track **jeden** Wegpunkt der Etappe mit
  einem Abstand von **höchstens 10 m** enthält / When die Alarm-Ortsangabe für diese Etappe
  erstmals aufgelöst wird /
  Then wird die gemessene Distanz aus diesem Track einmalig additiv an den Trip
  zurückgeschrieben (Read-Modify-Write mit Merge) und ab da für die Ortsangabe genutzt.
  - Test: Ein Trip ohne gemessene Waypoints und eine passende GPX-Datei im Nutzerbestand werden
    angelegt; nach der ersten Alarm-Auflösung trägt der persistierte Trip die gemessene Distanz,
    alle übrigen Felder (Name, `time_window`, `arrival_override`, `confirmed`, IDs) bleiben
    unverändert erhalten.

- **AC-8:** Given eine Etappe erhält eine gemessene km-Spanne aus dem gefundenen Track / When
  die Spanne zwischen zwei aufeinanderfolgenden Wegpunkten nicht streng monoton steigt oder
  kleiner als deren Luftlinienabstand ist / Then gilt die gesamte Etappe als unvermessen, und
  die Ortsangabe bleibt `Segment N`.
  - Test: Ein manipulierter Waypoint-Satz mit einer nicht-monotonen Distanzfolge wird durch die
    Plausibilitätsprüfung geschickt; das Ergebnis der Etappe ist „unvermessen", die
    Alarm-Ortsangabe zeigt weiterhin `Segment N`.

- **AC-9:** Given eine mehrtägige Tour mit mehreren vermessenen Etappen / When die
  Kilometer-Spanne für eine beliebige Etappe berechnet wird / Then beginnt die Zählung an diesem
  Etappenstart wieder bei 0 km, unabhängig von der kumulierten Gesamtstrecke der Tour.
  - Test: Für die dritte Etappe einer vermessenen Mehrtagestour wird die erste Kilometer-Spanne
    berechnet; ihr Startwert ist 0, nicht die Summe der Distanzen der vorherigen Etappen.

- **AC-10:** Given ein Bestandstrip, für den sich kein passender GPX-Track im Bestand des
  Nutzers eindeutig zuordnen lässt / When die Alarm-Ortsangabe für eine seiner Etappen aufgelöst
  wird / Then bleibt die Ausgabe byte-identisch zum heutigen Verhalten (`Segment N` / `Seg N`),
  keine km-Angabe erscheint.
  - Test: Ein Trip ohne jede passende GPX-Datei im Bestand wird vor und nach der Implementierung
    denselben Alarm-Renderern zugeführt; der erzeugte Text ist in beiden Läufen identisch.

- **AC-11:** Given mehr als eine GPX-Datei im Bestand des Nutzers passt gleichermaßen auf die
  Wegpunkte einer Etappe (z. B. Einzeletappe und eine Gesamt-GPX über alle Etappen) / When die
  Track-Auflösung läuft / Then wird keine der Dateien geraten, die Etappe gilt als unvermessen,
  und die Ortsangabe bleibt `Segment N`.
  - Test: Zwei GPX-Dateien, die beide alle Wegpunkte der Etappe enthalten, liegen im Bestand des
    Nutzers; die Track-Auflösung liefert kein Ergebnis, die Alarm-Ortsangabe zeigt `Segment N`.

- **AC-12:** Given eine Etappe enthält mindestens einen manuell im Editor ergänzten oder
  verschobenen Wegpunkt, dessen Abstand zum nächstgelegenen Punkt des sonst passenden
  GPX-Tracks **mehr als 10 m** beträgt / When die Track-Zuordnung läuft / Then wird für die
  gesamte betroffene Etappe keine Kilometer-Angabe angezeigt.
  - Test: Eine sonst passende Etappe bekommt einen zusätzlichen, abseits des Tracks liegenden
    Wegpunkt; die Track-Zuordnung schlägt für diese Etappe fehl, die Alarm-Ortsangabe bleibt
    `Segment N`.

- **AC-13:** Given kein Wegpunkt der Etappe trägt eine gemessene Wegstrecke und kein Track
  konnte eindeutig zugeordnet werden / When die Ortsangabe aufgelöst wird / Then wird zu keinem
  Zeitpunkt ein aus Luftlinie (`haversine_km`) berechneter Kilometerwert als Ortsangabe
  angezeigt.
  - Test: Für eine unvermessene Etappe wird geprüft, dass der von `haversine_km` intern
    berechnete Luftlinienwert nirgends im gerenderten Alarmtext auftaucht — weder als km-Angabe
    noch versteckt in einer anderen Formatierung.

- **AC-14:** Given der erste Wegpunkt einer Etappe hat gemessen `distance_from_start_km=0.0`
  (Etappenstart) und ein zweiter beteiligter Wegpunkt hat `distance_from_start_km=None` / When
  die Etappe auf Vermessenheit geprüft wird / Then zählt der Wert `0.0` als gültige Messung,
  während `None` als unbekannt behandelt wird und die Etappe insgesamt als unvermessen gilt,
  solange irgendein beteiligter Wegpunkt `None` trägt.
  - Test: Eine Etappe mit `distance_from_start_km=0.0` am Start und `None` an einem weiteren
    Wegpunkt wird geprüft; das Ergebnis ist „unvermessen" wegen des `None`-Werts, nicht wegen
    des `0.0`-Werts — ein separater Test mit ausschließlich `0.0`-und-höher-Werten ergibt
    „vermessen".

- **AC-15:** Given ein Segment mit gemessener km-Spanne durchläuft `weather_snapshot`-Speichern
  und -Rekonstruieren sowie die vier Alert-Event-Typen bis zum Renderer / When das Flag
  `distance_measured` / `km_measured` an jeder dieser Stellen geprüft wird / Then bleibt es an
  jeder Stelle `True` erhalten, ohne unterwegs auf den Default `False` zurückzufallen.
  - Test: Ein vermessenes Segment wird gespeichert, aus dem Snapshot rekonstruiert und über
    jeden der vier Alert-Event-Typen bis zum Renderer geführt; an jeder Zwischenstufe wird das
    Flag ausgelesen und ist `True`.

## Nicht Teil dieser Spec

- **Naismith-Gehzeiten** (`src/core/naismith.py:119`, `internal/model/naismith.go:118`) rechnen
  weiterhin auf Luftlinie, wodurch Ankunftszeiten um denselben Faktor zu früh ausfallen.
  Nutzersichtbar, aber eigenes Ticket → **#2042**.
- **`official_alerts.py:2137-2147` `_trip_total_segment_ids()`** zählt Segmente über alle
  Etappen einer Tour hinweg, obwohl Segmentnummern je Etappe vergeben werden — die
  „gesamte Route"-Verdichtung greift dadurch bei mehrtägigen Touren nie. Vorbestehender
  Nebenbefund, gehört ins Sammel-Issue → **#1199**.

## Bestandstests, die grün bleiben müssen

`tests/tdd/test_alert_location_vocabulary.py` (zentraler Ratschen-Test) ·
`tests/tdd/test_alert_sms_segment_head.py:177` · `tests/tdd/test_alert_segment_reference.py` ·
`tests/tdd/test_official_alert_sms_ortskopf.py:94` ·
`tests/tdd/test_official_alert_template_render.py` ·
`tests/unit/test_official_alert_output_unchanged.py` + Snapshot
`tests/fixtures/official_alert_render_snapshot_1944.json:6` ·
`tests/tdd/test_feature_574_segment_km_header.py` ·
`tests/tdd/test_952_onset_alert_fidelity.py` · `tests/tdd/test_onset_shift_alert.py` ·
`tests/tdd/test_alert_addendum_sms.py` · `tests/tdd/test_radar_alert_telegram_style.py`

## Risiken

1. **Go-Modell vergessen** ⇒ der erste Editor-Save wischt alle gemessenen Kilometer wieder weg.
   `internal/model/trip.go` muss im **selben** Deploy raus wie die Python-Änderungen.
2. **`loader.py:130` ersetzt Listen wholesale** ⇒ Telegram-Kommandos
   (`trip_command_processor.py:1245`) könnten gemessene km löschen, wenn dieselbe Kopplung nicht
   berücksichtigt wird — Read-Modify-Write mit Merge ist an dieser Stelle zwingend, kein Replace.
3. **Briefing-Segmentkopf (Feature #574)** zeigt heute dieselben falschen Luftlinien-km und wird
   durch diese Änderung ebenfalls korrekt — eine sichtbare, aber gewollte Nebenwirkung, kein
   Kollateralschaden.
4. **Ohne auffindbaren Track bleibt alles wie heute.** Das ist die Fallback-Garantie (AC-10),
   kein Bug — muss aber im Adversary-Dialog aktiv als Positivfall geprüft werden, nicht nur als
   impliziter Nebeneffekt.

## Known Limitations

- Gleichnamige GPX-Uploads überschreiben sich stumm im Bestand (`gpx_processing.py:66-69`) —
  vorbestehendes Verhalten, wird durch diese Spec nicht verändert und kann die Track-Auflösung
  auf einen falschen (weil überschriebenen) Track treffen lassen; das fällt dann unter die
  Plausibilitätsprüfung (AC-8) oder die Eindeutigkeitsprüfung (AC-11), wird aber nicht separat
  erkannt oder gemeldet.
- Die Track-Auflösung läuft bei Bedarf (lazy) bei der ersten Alarm-Auflösung einer unvermessenen
  Etappe, nicht proaktiv beim GPX-Upload für Bestandstrips — ein Nutzer, der nach dem Fix eine
  weitere GPX-Datei hochlädt, sieht die Kilometer-Angabe erst beim nächsten Alarm für die
  betroffene Etappe, nicht sofort.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Es handelt sich um eine additive Erweiterung des bestehenden
  Waypoint-/TripSegment-Datenmodells (ein optionales Feld, ein boolesches Echtheits-Flag) sowie
  eine geänderte Auflösungsreihenfolge in einer bestehenden Renderer-Funktion. Es wird keine
  neue Persistenzschicht, kein neuer Kanal und keine neue Auth-Entscheidung eingeführt. Die
  Teilungs-Invariante zwischen Nowcast-, Abweichungs- und amtlichem Alarm (#1744) bleibt
  unverändert bestehen — diese Spec speist lediglich alle drei Pfade aus derselben, um eine
  zusätzliche Quelle erweiterten Auflösung.

## Nachweisführung

- **Der Produktionspfad für Bestandstrips ist der Nachrüstungs-Weg (AC-7), nicht der
  Import-Weg (AC-6).** Ein RED-Test, der nur den Import-Fall (frisch angelegter Trip) abdeckt,
  lässt die für heutige Nutzer relevante Nachrüstung ungetestet — beide Wege brauchen eigene
  Tests.
- **AC-10 ist der Gegenfall zu AC-1/AC-7** und existiert, um eine versehentliche Immer-Ja-Logik
  in der Track-Auflösung fangbar zu machen (jede Datei „passt", wenn die Toleranzprüfung fehlt
  oder invertiert ist). Ohne AC-10 bleibt diese Mutation unsichtbar.
- **AC-14 ist der Gegenfall zu AC-9/AC-7** und existiert, um eine Verwechslung von `None`
  (unbekannt) und `0.0` (gültiger Startwert) fangbar zu machen — genau der Bug, den
  `GPXPoint.distance_from_start_km` mit seinem heutigen Default `0.0` strukturell begünstigt.
  Ein Test, der nur mit durchweg vorhandenen oder durchweg fehlenden Werten arbeitet, deckt
  diese Unterscheidung nicht ab.
- **AC-3 und AC-5 sind Ratschen-Nachweise gegen bestehende Tests**
  (`test_alert_location_vocabulary.py:296-298` bzw. `:534`) und müssen gegen den unveränderten
  Test-Wortlaut laufen, nicht gegen eine angepasste Kopie.
- Tests lösen ihren Prüfling **relativ zur eigenen Testdatei** auf, nie über den festen
  Hauptrepo-Pfad, damit sie im Worktree korrekt gegen den lokalen Stand laufen.

## Changelog

- 2026-08-21: Initial spec created
