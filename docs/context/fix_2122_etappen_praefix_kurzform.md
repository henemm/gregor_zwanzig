# Kontext: #2122 — Etappen-Nummer als Praefix in der Alarm-Kurzform

Workflow: `fix_2122_etappen_praefix_kurzform` · Issue: #2122 · Phase: Analyse (2)

## Auftrag (PO, 2026-08-30, waehrend der laufenden Tour)

> „Stelle sicher, dass alle Alerts in der Kurzform die Etappen-Nummer als Praefix enthalten.
> `Ziel: R2->42@16 Rest0` oder `km 10-14: TH:L->M TH:H->M TH:M->L` ist bei sehr asynchroner
> Kommunikation sehr ungenau."

## Analysis

### Type

Bug (nutzersichtbares Fehlverhalten, `[triage:po]` + `[triage:a]`).

### Root Cause — drei Schichten

**1. Die Etappen-Nummer erreicht den Alarm-Renderer nie.**
`AlertMessage` (`src/output/renderers/alert/model.py:257-291`) fuehrt kein Etappen-Feld.
`to_alert_message()` (`src/output/renderers/alert/project.py:297-300`) nimmt nur
`changes, segments, trip_name` — kein `Trip`, keine `Stage`. Der Aufrufer
`notification_service.py:785-789` hat `trip` im Zugriff, reicht aber nur `trip.name` durch.
`Trip.numbered_stage_label()` (`src/app/trip.py:289-305`) existiert seit #760 und wird im
gesamten Alarm-Pfad NIRGENDS benutzt — nur in Briefing-Pfaden
(`preview_service.py:190`, `trip_report_scheduler.py:1412`).

**2. Was heute wie eine Etappen-Nummer aussieht, ist keine.**
`AlertEvent.segment_id` ist tagesgebunden: `convert_trip_to_segments(trip, target_date)`
(`src/services/trip_segments.py:180-190`) loest via `trip.get_stage_for_date()` GENAU EINE
Stage auf; die Nummerierung `segment_id = i+1` (`trip_segments.py:248, 317`) laeuft nur ueber
`stage.waypoints` und beginnt an jedem Tag wieder bei 1. `Seg 4:` heisst also „Abschnitt 4 der
heutigen Etappe", nicht „Etappe 4".
Begriffs-Inkonsistenz im Bestand: `segments.py:38-39` schreibt „Begriff bewusst 'Segmente',
nicht 'Etappen'", waehrend `model.py:32-34` dasselbe Feld „Kennung der betroffenen Etappe"
nennt.

**3. Der vorhandene Abschnittsbezug wird verdraengt.**
`format_alert_location()` (`src/output/renderers/alert/segments.py:91-128`) ist eine
Prioritaetskette mit `return` je Stufe: Ortsname → GEMESSENE km-Spanne (#2036) →
Segmentbezug → km-Rueckfall. Sobald echte GPX-Wegstrecke vorliegt, faellt der Segmentbezug
komplett weg — der Fall `km 10-14:` aus der PO-Meldung.

### Gesicherte Nebenbefunde aus der Untersuchung

**a) Ein Alarm betrifft immer genau EIN `target_date` je Baustein.** Kein `AlertEvent`
buendelt mehrere Stages. Belege: `trip_segments.py:180-190`;
`resolve_current_segment() -> Optional[Tuple[TripSegment, date]]`
(`trip_segments.py:455-457`, Singular).

**b) Das richtige Datum ist NICHT immer `today`.**
- Abweichungs-Alarm (strikt): immer `today` — `_kanal_anker_kandidat()` verwirft jeden Anker
  mit `target_date != today` (`trip_alert.py:1170-1175`).
- Radar: `_resolve_alert_segment()` liefert `segment_date`, „nicht zwingend today"
  (`trip_alert.py:1618-1626`; Docstring `trip_segments.py:484-486`: „Aufrufer duerfen dieses
  Datum nicht durch `today` ersetzen"). Das Feld wird beim Bau von `RadarAlertRequest`
  (`trip_alert.py:2186-2230`) NICHT uebernommen — Luecke.
- Amtliche Warnung (lenient): Rolling-Anchor-Rueckfall `trip_alert.py:1076-1088` nimmt den
  ersten Kanal „ohne Tages- oder Alterspruefung". Das zugehoerige Datum ist ueber
  `alarm_anchor_target_date(trip_id, channel)` (`weather_snapshot.py:314-329`) lesbar, wird
  aber nicht abgefragt.

**c) Ein schmaler Rand-Fall buendelt zwei Datumsquellen in EINER Nachricht.**
`check_all_trips()` holt `changes` strikt (`trip_alert.py:920-922`, garantiert `today`) und
`official_notices` aus einem separaten, lenienten Aufruf (`trip_alert.py:927-928`). Fehlt der
Tagesschnappschuss und tragen zwei Kanaele unterschiedlich alte rollierende Anker, koennen
Abweichungs-Ereignisse (Etappe heute) und amtliche Notices (Etappe eines Vortags) in
derselben `AlertMessage` landen. Folge fuer den Entwurf: **ein einzelnes Feld auf
`AlertMessage` waere in diesem Fall falsch.**

**d) Trip vs. Ortsvergleich ist nur an der Aufrufstelle unterscheidbar** — kein Flag am DTO.
Bestehendes Muster: „Trip-Pfad setzt dieses Feld NIE" (`model.py:264-268`) bzw. „der
Ortsvergleich setzt sie nie" (`model.py:270-276`). Die Etappen-Nummer folgt demselben
additiven Muster: Trip-Pfad setzt, Compare-Pfad laesst `None`.

**e) Kollision mit einem PO-Entscheid vom 2026-08-17.** `render.py:1692-1693` haelt fest:
„kein Trip-Name mehr — PO-Entscheid 2026-08-17". Genau dieser Kopf-Zweig wurde vor 13 Tagen
bewusst geleert, um Zeichen zu sparen. Die Etappen-Nummer ist nicht der Trip-Name, aber die
Spec muss das ausdruecklich benennen, damit es nicht wie ein stilles Zurueckdrehen wirkt.

**f) Deutsche Woerter in der englischen Kurzform** (`Ziel`, `Rest`, `Erg`, `Seg`) —
`_ascii_alert_location` (`render.py:1802-1812`) faltet nur `"Segment " → "Seg "`.
NICHT Scope von #2122 → Nebenbefund fuer #1199.

### Affected Files

| Datei | Aenderung | Beschreibung |
|---|---|---|
| `src/output/renderers/alert/model.py` | MODIFY | Neues additives Feld `stage_number: int \| None = None` auf `AlertEvent`, `OnsetEvent`, `CorridorEvent`, `OnsetShiftEvent` — Muster von `segment_id` (#1744) und `km_measured` (#2036) |
| `src/output/renderers/alert/project.py` | MODIFY | Feld in `to_alert_message`, `to_corridor_events`, `to_multi_location_onset_alert_message`, `_to_onset_shift_event` durchreichen |
| `src/output/renderers/alert/render.py` | MODIFY | Praefix-Bau + Aggregation ueber die beteiligten Ereignisse; alle vier Kopf-Zweige (`473`, `1128-1132`, `1622-1627`, `1721`); Budget/Kuerzung (`1737-1751`) |
| `src/output/renderers/alert/official_alerts.py` | MODIFY | Feld auf dem Notice-DTO (`:144`), Kopf ueber `sms_scope` (`:2117`) |
| `src/services/notification_service.py` | MODIFY | Etappe an den Trip-Einstiegen aufloesen und uebergeben (`785`, `942`, `958`, `1394`) |
| `src/services/trip_alert.py` | MODIFY | `segment_date` in `RadarAlertRequest` uebernehmen (`2186-2230`); Datum fuer die amtliche Seite bereitstellen |
| `tests/tdd/test_alert_etappen_praefix_kurzform.py` | CREATE | Neue Wachter: Praefix je Alarmart, Aggregation, Budget, Naht-Test |

### Scope Assessment

- Produktivdateien: **6** · Neue Testdatei: **1**
- Geschaetzt: **+140 LoC** Produktivcode, **+150 LoC** Tests
- Risiko: **MEDIUM** — mechanisch gleichfoermig (dasselbe additive Muster fuenfmal), aber
  fuenf Kopf-Zweige in zwei Dateien plus Zeichenbudget
- **LoC-Limit-Override auf 500 noetig** (Standard 250)

Bestandstests: 26 Testdateien enthalten byte-genaue Kopf-Assertions auf die Kurzform,
40 pruefen das Laengenbudget. Weil das Feld **additiv mit Default `None`** eingefuehrt wird
und Bestandstests keine Etappe setzen, bleiben sie byte-identisch gruen — dieselbe
Regressions-Invariante wie bei `km_measured` (#2036) und `location_positions` (#1467).

### Technical Approach (Empfehlung)

1. **Feld auf Ereignis-Ebene, nicht auf Nachrichtenebene.** Grund: Befund (c) — eine
   Nachricht kann im Rand-Fall Bausteine zweier Etappen tragen. Ein Feld auf `AlertMessage`
   wuerde dort eine falsche Nummer behaupten. Ereignis-Ebene folgt zudem exakt dem bereits
   zweimal gefahrenen Muster (`segment_id`, `km_measured`) und ist damit risikoarm.
2. **Der Kopf aggregiert.** Eine Etappe → `S5`; mehrere zusammenhaengende → `S5-6`; sonst
   Aufzaehlung. Fehlt die Nummer bei irgendeinem Ereignis → **kein** Praefix (ehrlicher als
   eine Teilangabe; dieselbe Logik wie `_renderable_segment_ids`, `segments.py:77-88`).
3. **Schreibweise `S<N>`, nicht `E<N>`.** Die Kurzform ist ENGLISCH (PO-Ansage 2026-08-22:
   „SMS ist English"); `S` = Stage passt zum Feld `Trip.stages`. `E` waere deutsch.
4. **Praefix steht VOR dem Ortsteil und ueberlebt die Kuerzung.** Es gehoert zum Kopf
   (`head`), der in `render.py:1737-1751` nie gekuerzt wird — der harte
   `body[:limit]`-Schnitt (Degenerationsfall) braucht einen eigenen Test.
5. **Datum je Pfad korrekt beziehen** (Befund b): Abweichung → `today`; Radar →
   `segment_date` aus `_resolve_alert_segment`; amtlich → `alarm_anchor_target_date`.
   Kein Pfad ersetzt sein Datum durch `today`.
6. **Compare-Pfad bleibt unberuehrt** — setzt das Feld nie, Ausgabe byte-identisch.

Ergebnisform:

```
S5 km 10-14: TH:L->M TH:H->M TH:M->L
S5 Ziel: R2->42@16 Rest0
```

### Nachweis-Anforderungen (fuer die TDD-Phase)

- Je Alarmart ein Test: Etappe gesetzt → Praefix vorn; nicht gesetzt → byte-identisch zum Bestand
- **Naht-Test:** Die Nummer wird vom Trip-Auslöser ABGELEITET, nicht im Testaufbau als
  Literal gesetzt — sonst bleibt die Bildungsstelle unbewacht
- Budget: Kopf inkl. Praefix ueberlebt die Kuerzung; `len(body) <= limit` bleibt zugesichert;
  eigener Test fuer den harten Schnitt bei zweistelliger Etappe + langem Ortsnamen
- Kanal-Paritaet: SMS, Premium-SMS, Telegram-Kurzform tragen denselben Text
- Mutations-Gegenprobe: Praefix aus dem Kopf entfernen → mindestens ein Test je Alarmart rot

### Open Questions

- [ ] Schreibweise `S5` — gehoert als AC in die Spec und wird vom PO freigegeben
- [ ] Bleibt `Seg N` neben `S5` stehen, oder faellt der Abschnittsbezug in der Kurzform weg?
      (Empfehlung: bleibt — er traegt die feinere Ortsangabe; `S5 Seg 4:` ist eindeutig,
      solange die Spec beide Begriffe definiert.)
