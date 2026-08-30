---
entity_id: fix_2122_etappen_praefix_kurzform
type: bugfix
created: 2026-08-30
updated: 2026-08-30
status: draft
workflow: fix_2122_etappen_praefix_kurzform
---

# Fix #2122: Etappen-Nummer als Präfix in der Alarm-Kurzform

## Approval

- [x] Approved — PO (Henning) am 2026-08-30, Freigabe der zwölf ACs mit „go"

## Purpose

Die Alarm-Kurzform (SMS, Premium-SMS, Telegram-Kurzform) nennt heute keine Etappen-Nummer.
Köpfe wie `Ziel: R2->42@16 Rest0` oder `km 10-14: TH:L->M` sind bei verzögertem Empfang —
dem Normalfall auf Satellitenstrecke — nicht mehr zuordenbar. Dieser Fix stellt jeder
Alarm-Kurzform der Trip-Fläche die Etappen-Nummer der Tour als Präfix voran (`S5 Ziel: …`),
abgeleitet aus dem Datum, dem die betroffenen Segmente tatsächlich entstammen. Der
Ortsvergleich und Alarme ohne auflösbare Etappe bleiben byte-identisch zum Bestand.

## Source

- **File:** `src/output/renderers/alert/model.py`
- **Identifier:** `AlertEvent`, `OnsetEvent`, `CorridorEvent`, `OnsetShiftEvent`
- **File:** `src/output/renderers/alert/render.py`
- **Identifier:** `_render_sms_body`, `_render_sms_onset`, `_render_sms_onset_shift_only`, `_render_sms_corridor_only`
- **File:** `src/output/renderers/alert/official_alerts.py`
- **Identifier:** `OfficialAlertNotice`, `render_official_alert_sms`, `build_official_alert_notices`
- **File:** `src/output/renderers/alert/project.py`
- **Identifier:** `to_alert_message`, `to_corridor_events`, `to_multi_location_onset_alert_message`, `_to_onset_shift_event`
- **File:** `src/services/notification_service.py`
- **Identifier:** `send_deviation_alert`, `send_radar_alert`, `send_official_alert`
- **File:** `src/services/trip_alert.py`
- **Identifier:** `_resolve_alert_segment`, `RadarAlertRequest`-Bau, `check_official_alert_triggers`

## Estimated Scope

- **LoC:** ~140 Produktivcode, ~150 Tests
- **Files:** 6 MODIFY + 1 CREATE (Testdatei)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/trip.py` (`Trip.numbered_stage_label`, Z.289) | module | Liefert die 1-basierte chronologische Etappen-Position; bisher nur in Briefing-Pfaden benutzt |
| `src/app/trip.py` (`Trip.get_stage_for_date`, Z.275) | module | Löst Datum → Etappe auf; die Nummer entsteht aus der Position in `sorted(stages, key=date)` |
| `src/services/trip_segments.py` (`convert_trip_to_segments`, Z.180) | module | Belegt: Segmente eines Alarms stammen aus GENAU EINEM `target_date` |
| `src/services/trip_segments.py` (`resolve_current_segment`, Z.455) | module | Liefert `(TripSegment, date)` — das Datum darf NICHT durch `today` ersetzt werden (Docstring Z.484-486) |
| `src/services/weather_snapshot.py` (`alarm_anchor_target_date`, Z.314) | module | Liest das Datum des rollierenden Ankers je Kanal; heute ungenutzt, für den amtlichen Pfad nötig |
| `src/output/renderers/alert/segments.py` (`format_alert_location`, Z.91) | module | Die EINE Ortsauflösung — bleibt unverändert; das Präfix steht DAVOR, nicht darin |
| Issue #2036 | upstream | Hat die gemessene km-Spanne vor den Segmentbezug gezogen; dieser Fix dreht das NICHT zurück |
| PO-Entscheid 2026-08-17 (`render.py:1692-1693`) | decision | Hat den Trip-Namen aus dem Δ-Kopf entfernt (Zeichenbudget). Die Etappen-Nummer ist NICHT der Trip-Name; dieser Fix bringt den Trip-Namen NICHT zurück |
| PO-Ansage 2026-08-22 („SMS ist English") | decision | Begründet die Schreibweise `S` (Stage) statt `E` (Etappe) |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/alert/model.py` | MODIFY | Additives Feld `stage_number: int \| None = None` auf `AlertEvent`, `OnsetEvent`, `CorridorEvent`, `OnsetShiftEvent` — Muster von `segment_id` (#1744) und `km_measured` (#2036) |
| `src/output/renderers/alert/official_alerts.py` | MODIFY | Feld `stage_number` auf `OfficialAlertNotice` (Z.144); Kopfbau (Z.2117) stellt das Präfix voran |
| `src/output/renderers/alert/project.py` | MODIFY | `stage_number` in `to_alert_message`, `to_corridor_events`, `to_multi_location_onset_alert_message`, `_to_onset_shift_event` durchreichen |
| `src/output/renderers/alert/render.py` | MODIFY | Neuer Baustein `_stage_prefix(events)` (die EINE Stelle); alle vier Kopf-Zweige (Z.473, 1128-1132, 1622-1627, 1721) stellen ihn voran; Kürzung (Z.1737-1751) unverändert, weil das Präfix zum Kopf gehört |
| `src/services/notification_service.py` | MODIFY | Etappen-Nummer an den Trip-Einstiegen auflösen und übergeben (Z.785, 1394, 958); Compare-Einstiege (Z.888ff, 942) lassen sie `None` |
| `src/services/trip_alert.py` | MODIFY | `segment_date` aus `_resolve_alert_segment` (Z.1626) in `RadarAlertRequest` übernehmen (Z.2186-2230); für den amtlichen Pfad das Ankerdatum über `alarm_anchor_target_date` bereitstellen |
| `tests/tdd/test_alert_etappen_praefix_kurzform.py` | CREATE | Wächter für alle ACs dieser Spec |

## Implementation Details

```
Schreibweise (die EINE Stelle: render._stage_prefix)

  genau eine Etappe          -> "S5 "
  mehrere, zusammenhängend   -> "S5-6 "
  mehrere, nicht benachbart  -> "S5,7 "
  mehr als drei verschiedene -> ""        (kein Präfix — eine lange Liste
                                           kostet mehr Budget als sie nützt)
  mindestens ein Ereignis
  ohne Etappen-Nummer        -> ""        (Teilangabe wäre unehrlich; dieselbe
                                           Logik wie _renderable_segment_ids)

Position im Kopf

  <Präfix><Ortsangabe>: <Tokens>
  Beispiel: "S5 km 10-14: TH:L->M TH:H->M TH:M->L"
            "S5 Ziel: R2->42@16 Rest0"

  Das Präfix steht VOR der Ortsangabe und ist Teil von `head`. Die
  Ortsauflösung (segments.format_alert_location) bleibt unangetastet.

Datumsquelle je Alarmpfad (das Datum bestimmt die Etappe)

  Abweichungs-Alarm  -> today (strikt garantiert, trip_alert.py:1170-1175)
  Radar / Onset      -> segment_date aus _resolve_alert_segment (kann der
                        Vortag sein — Nachtsegment)
  Amtliche Warnung   -> alarm_anchor_target_date(trip_id, channel) des
                        tatsächlich verwendeten Ankers, sonst today
  Ortsvergleich      -> keine (Feld bleibt None)

Nummer = Position der Etappe in sorted(trip.stages, key=lambda s: s.date) + 1,
abgeleitet über trip.get_stage_for_date(<Datum>) — identisch zur Nummer, die
Trip.numbered_stage_label() im Briefing zeigt.
```

## Expected Behavior

- **Input:** Ein Trip-Alarm beliebiger Art, dessen betroffene Segmente einem Datum entstammen,
  zu dem der Trip eine Etappe führt.
- **Output:** Die Kurzform beginnt mit `S<Nummer> `, gefolgt von der bisherigen Ortsangabe und
  den bisherigen Tokens. E-Mail und Telegram-Langform bleiben unverändert.
- **Side effects:** Keine. Kein Alarm wird zusätzlich ausgelöst oder unterdrückt; die
  Auslöseentscheidung bleibt unberührt.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit mehreren Etappen und ein Abweichungs-Alarm auf der fünften
  Etappe / When die Kurzform gerendert wird / Then beginnt der Text mit `S5 ` vor der
  Ortsangabe, also z.B. `S5 Ziel: R2->42@16 Rest0`.
  - Test: Alarm über den echten Auslösepfad erzeugen, die Nummer wird aus dem Trip abgeleitet
    und NICHT im Testaufbau als Literal gesetzt; geprüft wird der zugestellte Kurztext.

- **AC-2:** Given derselbe Trip und ein Radar-/Nowcast-Alarm / When die Kurzform gerendert wird
  / Then trägt sie dasselbe Etappen-Präfix wie der Abweichungs-Alarm derselben Etappe.
  - Test: Radar-Alarm über den echten Pfad; Vergleich des Präfixes beider Alarmarten.

- **AC-3:** Given ein Alarm über eine Beginn-Verschiebung (Onset-Shift) / When die Kurzform
  gerendert wird / Then steht das Etappen-Präfix vor der Ortsangabe.
  - Test: Onset-Shift-Alarm erzeugen, Kurztext prüfen.

- **AC-4:** Given ein Alarm über einen Schwellen-Treffer (Korridor) / When die Kurzform
  gerendert wird / Then steht das Etappen-Präfix vor der Ortsangabe.
  - Test: Korridor-Alarm erzeugen, Kurztext prüfen.

- **AC-5:** Given eine amtliche Warnung für einen Trip / When die Kurzform gerendert wird
  / Then steht das Etappen-Präfix vor dem bisherigen Ortsteil (`sms_scope`).
  - Test: Amtliche Warnung über den echten Pfad; Kurztext prüfen.

- **AC-6:** Given ein Radar-Alarm, dessen betroffenes Segment aus der Nacht des VORTAGS stammt
  / When die Kurzform gerendert wird / Then nennt das Präfix die Etappe des Vortags, nicht die
  von heute.
  - Test: Alarm mit einem `segment_date` ungleich `today` auslösen und prüfen, dass die Nummer
    der Vortags-Etappe erscheint; Gegenprobe mit `today`.

- **AC-7:** Given ein Alarm, dessen Bausteine zu zwei verschiedenen Etappen gehören / When die
  Kurzform gerendert wird / Then nennt das Präfix beide (`S5-6` bei Nachbarschaft, sonst
  `S5,7`) und behauptet keine einzelne Etappe.
  - Test: Nachricht mit Ereignissen zweier Etappen bauen, beide Schreibweisen prüfen.

- **AC-8:** Given ein Alarm, bei dem für mindestens ein Ereignis keine Etappe auflösbar ist
  (Altdaten) / When die Kurzform gerendert wird / Then erscheint KEIN Präfix und der Text ist
  byte-identisch zum bisherigen Verhalten.
  - Test: Bestandsfall ohne Etappe rendern und mit dem eingefrorenen Bestandstext vergleichen.

- **AC-9:** Given ein Alarm aus dem Ortsvergleich / When die Kurzform gerendert wird / Then
  erscheint KEIN Etappen-Präfix und der Text ist byte-identisch zum bisherigen Verhalten.
  - Test: Ortsvergleich-Alarm rendern und mit dem Bestandstext vergleichen.

- **AC-10:** Given ein Alarm mit so vielen Tokens, dass die Kurzform gekürzt werden muss
  / When sie gerendert wird / Then bleibt das Etappen-Präfix vollständig erhalten, die Kürzung
  trifft nur die Tokens, und der Text ist höchstens so lang wie das Limit.
  - Test: Alarm nahe der Längengrenze mit zweistelliger Etappen-Nummer und langem Ortsnamen;
    Präfix vorhanden, `len(text) <= limit`.

- **AC-11:** Given derselbe Alarm auf allen drei Kurz-Kanälen / When SMS, Premium-SMS und
  Telegram-Kurzform erzeugt werden / Then tragen alle drei dasselbe Etappen-Präfix.
  - Test: Alle drei Kanäle aus demselben Alarm erzeugen und die Präfixe vergleichen.

- **AC-12:** Given die fertige Implementierung / When das Etappen-Präfix aus dem Kopfbau
  entfernt wird / Then wird für JEDE der fünf Alarmarten mindestens ein Test rot.
  - Test: Mutations-Gegenprobe per String-Ersetzung mit externer Sicherungskopie; protokolliert
    wird, welcher Test je Alarmart anschlägt.

## Known Limitations

- Ein Alarm, dessen Bausteine zu mehr als drei verschiedenen Etappen gehören, erhält kein
  Präfix. Dieser Fall entsteht praktisch nur über den lenienten Anker-Rückfall bei amtlichen
  Warnungen und ist damit sehr selten; eine vierstellige Aufzählung würde mehr Zeichenbudget
  kosten als sie an Zuordnung bringt.
- Der Abschnittsbezug innerhalb des Tages (`Seg 4`) bleibt unverändert bestehen. Er beantwortet
  eine andere Frage als die Etappen-Nummer (wo auf der Etappe statt welche Etappe). Die
  Begriffs-Inkonsistenz im Code — `segments.py:38-39` nennt es „Segmente", `model.py:32-34`
  „Etappe" — wird in diesem Fix nicht bereinigt.
- Deutsche Wörter in der englischen Kurzform (`Ziel`, `Rest`, `Erg`) werden hier NICHT
  angefasst — Nebenbefund für #1199.
- Der schmale Rand-Fall aus der Analyse (Abweichungs-Teil und amtlicher Teil ziehen
  unterschiedlich alte Anker) wird durch AC-7 korrekt dargestellt, aber nicht ursächlich
  behoben; der Anker-Rückfall selbst bleibt unverändert.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Kein neues Entscheidungsfeld. Das Feld wird nach dem im Repo zweimal
  gefahrenen additiven Muster eingeführt (`segment_id` aus #1744, `km_measured` aus #2036):
  optional, Default `None`, Trip-Pfad setzt, Compare-Pfad lässt leer. Die Ortsauflösung
  (`format_alert_location`) und die #2036-Priorität bleiben unangetastet.

## Changelog

- 2026-08-30: Initial spec created (#2122)
