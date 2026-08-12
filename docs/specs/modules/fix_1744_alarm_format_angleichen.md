---
entity_id: fix_1744_alarm_format_angleichen
type: module
created: 2026-08-12
updated: 2026-08-12
status: draft
version: "1.0"
tags: [alerts, renderer, email, subject]
---

# Alarm-Format angleichen: eine Ortssprache für alle Trip-Alarme (#1744 Scheibe A)

## Approval

- [x] Approved — PO-Freigabe 2026-08-12 („go"), ACs auf Deutsch vorgelegt

## Purpose

Zwei Alarm-Mails zum selben Ereignis nennen den Ort heute in zwei verschiedenen Sprachen
(`km 8–8` gegen `🏁 Ziel`) und sind auch im Aufbau kaum als verwandt zu erkennen. Diese Spec
gibt allen Trip-Alarmen **eine** Ortssprache — die Segment-Kennung — und **einen** Mail-Aufbau.

Nicht Gegenstand: die quellenübergreifende Entdopplung mehrerer Alarme zum selben Ereignis
(Scheibe B, gebucht an #1467 S4).

## Source

- **Datei:** `src/output/renderers/alert/render.py`, `src/output/renderers/alert/official_alerts.py`,
  `src/output/renderers/alert/model.py`, `src/output/renderers/alert/project.py`
- **Identifier:** `_km_str`, `_km_str_onset`, `render_subject`, `format_segment_reference`,
  `AlertEvent`, `OnsetEvent`, `to_alert_message`

Schicht: **Python-Core** (Renderer + Projektion). Keine Go-Änderung, keine Frontend-Änderung.

## Estimated Scope

Zwei Liefer-Scheiben, ein gemeinsames Zielbild.

| Scheibe | Inhalt | LoC (Produktiv) | Dateien |
|---|---|---|---|
| **A1** | Ortsangabe + Betreff | ~90 | 6 |
| **A2** | Mail-Körper | ~130 | 2 |

- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `format_segment_reference` | Funktion | bestehende Ortsformatierung der amtlichen Warnung — wird zur gemeinsamen |
| `TripSegment.segment_id` | Feld | Quelle der Kennung (`1..N` oder `"Ziel"`) |
| ADR-0033 | Entscheidung | Warn-Karte nennt nur betroffenen Umfang — bleibt inhaltlich bindend |
| `warnmail_official_alert_display.md` AC-3 | Spec | ehrliche Sammelangabe bei gemischtem Umfang — bleibt bindend |
| PO-Entscheid 2026-08-04 (#1467 S2 AG3b) | Entscheidung | Kurznachrichten nennen keinen Ort — bleibt bindend |

## Implementation Details

### Woher die Segment-Kennung kommt

Sie ist an beiden Stellen bereits zur Hand und wird nur nicht weitergereicht:

```
Abweichungsalarm: project.py:88   match = _find_segment(segments, ch.segment_id)
                                  → heute nur match.segment.start_point.distance_from_start_km
                                  → künftig zusätzlich match.segment.segment_id

Nowcast:          trip_alert.py:1098  active.start_point.distance_from_start_km
                                  → künftig zusätzlich active.segment_id
                                  → über RadarAlertRequest nach notification_service.py:1234
```

### Eine Formatierung, zwei Aufrufer

`format_segment_reference()` (heute `official_alerts.py:262-289`) zieht in ein eigenes Modul um
und wird von **beiden** Renderern importiert. Weder `render.py` noch `official_alerts.py`
importieren einander heute — der Umzug ist zyklenfrei.

Auflösungsreihenfolge der Ortsangabe (eine Funktion, alle Alarmarten):

```
1. location_label gesetzt      → Ortsname               (Ortsvergleich, unverändert)
2. Segment-Kennung vorhanden   → format_segment_reference()
3. sonst                       → km {von}–{bis}          (Rückfall, z.B. Altdaten)
```

### Gemeinsamer Mail-Aufbau (A2)

Beide Mailtypen folgen derselben Reihenfolge. Typ-eigene Bausteine sitzen an **festen**
Positionen, statt den Aufbau zu verdoppeln:

```
Kennzeichen (Alarmart)          beide
Überschrift (Kernaussage)       beide
Warnstufen-Skala                nur amtliche Warnung
Datenzeilen                     beide   ← hier gleicht sich die amtliche Warnung an
Sperrzeit-Hinweis               nur Nowcast
Stand-Zeile                     beide
Herkunfts-Fußzeile              beide
```

Die Warnstufen-Skala (GELB · ORANGE · ROT mit „niedrigste von drei") bleibt als **Skala**
erhalten und wandert nicht in eine Textzeile: sie trägt eine Einordnung, die eine bloße
Wortangabe verliert. Alles Übrige der amtlichen Warnung (Gefahrenart, Gültigkeitsfenster,
Ortsbezug, Quelle) wird zu Datenzeilen im Aufbau des Nowcasts.

## Expected Behavior

- **Input:** Trip-Alarme aller Arten (Abweichung, Nowcast, amtliche Warnung), Ortsvergleich-Alarme.
- **Output:** Betreff, E-Mail (HTML + Text) und Telegram-Langform nennen den Ort in derselben
  Sprache; beide Mailtypen haben denselben Aufbau.
- **Side effects:** keine. Reine Darstellungs- und Projektionsänderung, keine Auslöselogik,
  keine Persistenz, kein Kanal-Routing.

## Acceptance Criteria

### Scheibe A1 — Ortsangabe und Betreff

- **AC-1:** Given ein Trip-Nowcast-Alarm für das Ziel-Segment / When die Alarm-Mail versendet
  wird / Then nennt die Betreffzeile `🏁 Ziel` statt `km 8–8`, und der Betreff einer amtlichen
  Warnung für dasselbe Segment nennt denselben Text — die beiden Mails sind als derselbe Ort
  erkennbar.
  - Test: beide Mails für denselben Trip und dasselbe Segment rendern und die Ortsangabe der
    beiden Betreffzeilen auf Gleichheit prüfen. Der Test muss rot werden, wenn nur einer der
    beiden Pfade umgestellt ist.

- **AC-2:** Given ein Trip-Abweichungsalarm, der die Segmente 3, 4 und 5 betrifft / When der
  Betreff gerendert wird / Then steht dort `Segment 3–5` — dieselbe Zusammenfassung, die eine
  amtliche Warnung über dieselben drei Segmente erzeugt.
  - Test: Abweichungsalarm über drei zusammenhängende Segmente rendern und mit der Ausgabe der
    amtlichen Warnung über dieselben Segment-Kennungen vergleichen.

- **AC-3:** Given irgendein Trip-Alarm mit Ortsangabe / When die Ortsangabe gebildet wird /
  Then geschieht das über **genau eine** Funktion: eine Verfälschung dieser Funktion (z.B.
  `Segment` → `Etappe`) muss den Nowcast-Test, den Abweichungstest UND den Test der amtlichen
  Warnung gleichzeitig rot machen.
  - Test: Mutations-Gegenprobe. Bleibt einer der drei grün, existiert noch eine zweite
    Formatierung — das ist ein Verstoß gegen die Teilungsregel.

- **AC-4:** Given ein Alarm im Ortsvergleich (ein Ort oder mehrere) / When Betreff, Mail und
  Telegram gerendert werden / Then erscheinen weiterhin die Ortsnamen, unverändert zu heute —
  die Segment-Kennung greift dort nicht.
  - Test: die bestehenden Golden-Vergleiche des Ortsvergleichs laufen unverändert grün
    (`tests/tdd/test_issue_1169_compare_alert_consumer.py`).

- **AC-5:** Given ein Trip-Alarm / When die Kurznachricht (SMS und Premium-SMS) gerendert wird /
  Then nennt sie weiterhin **keinen** Ortsnamen und bleibt innerhalb von 140 Zeichen — der
  PO-Entscheid vom 2026-08-04 bleibt unangetastet.
  - Test: Kurznachricht für einen Trip-Alarm mit Ziel-Segment rendern; sie darf weder `Ziel`
    noch `Segment` enthalten, und ihre Länge bleibt ≤ 140.

- **AC-6:** Given eine Alarm-Mail mit Ortsangabe im Betreff / When der Mail-Körper gerendert
  wird / Then nennt die Zeile „Wo & wann" **denselben** Ortstext wie der Betreff — innerhalb
  einer Mail gibt es keine zwei Ortssprachen mehr.
  - Test: Betreff und Datenzeile derselben gerenderten Mail gegeneinander prüfen.

- **AC-7:** Given ein Trip-Alarm, dessen Etappe keine Segment-Kennung trägt (Altdaten) / When
  die Ortsangabe gebildet wird / Then fällt sie auf die km-Spanne zurück, statt leer zu bleiben
  oder den Versand abzubrechen.
  - Test: Alarm ohne Segment-Kennung rendern; Ortsangabe ist nicht leer und der Versand läuft.

### Scheibe A2 — Mail-Körper

- **AC-8:** Given je eine Nowcast-Mail und eine amtliche Warn-Mail / When beide gerendert werden /
  Then haben sie dieselbe Reihenfolge der Bausteine (Kennzeichen, Überschrift, Datenzeilen,
  Stand-Zeile, Fußzeile), und die Fakten der amtlichen Warnung stehen in Datenzeilen derselben
  Bauform wie beim Nowcast.
  - Test: beide Mails rendern und die Abfolge der Bausteine vergleichen.

- **AC-9:** Given eine amtliche Warnung der Stufe GELB / When die Mail gerendert wird / Then ist
  die Warnstufe weiterhin als **Skala** erkennbar (GELB · ORANGE · ROT mit der Einordnung
  „niedrigste von drei") und nicht auf ein einzelnes Wort reduziert.
  - Test: gerenderte Mail enthält alle drei Stufenbezeichnungen und die Einordnung.

- **AC-10:** Given eine amtliche Warnung im neuen Aufbau / When die Mail gerendert wird / Then
  enthält sie unverändert Gefahrenart, Gültigkeitsfenster, Ortsbezug und Quelle — durch den
  Umbau geht keine Information verloren.
  - Test: jede Angabe der heutigen Mail einzeln im neuen Aufbau nachweisen.

- **AC-11:** Given ein Trip mit 63 Segmenten und einer Warnung für 1 Segment / When die Mail
  gerendert wird / Then erscheinen weiterhin **keine** nicht betroffenen Segmente — ADR-0033
  bleibt gewahrt.
  - Test: der bestehende ADR-0033-Test bleibt grün
    (`tests/tdd/test_official_alert_template_render.py`).

- **AC-12:** Given mehrere amtliche Warnungen mit **verschiedenem** Umfang / When der Betreff
  gerendert wird / Then steht dort weiterhin die ehrliche Sammelangabe („mehrere Segmente") und
  nicht ein einzelnes Segment — AC-3 der Warnmail-Spec (#1248) bleibt gewahrt.
  - Test: der bestehende Test bleibt grün
    (`tests/tdd/test_official_alert_subject_compact.py`).

## Was sich ausdrücklich NICHT ändert

- Auslösung, Cooldown, Kanal-Routing, Empfängerauflösung, Ruhezeiten, Tageslimit.
- Die Kurznachricht (SMS, Premium-SMS) — weder Ortsangabe noch Aufbau.
- Der Ortsvergleich — dort ist die Ortssprache bereits einheitlich.
- Der Korridor-/Schwellen-Renderer — toter Code seit `8f2053f9` (#1460 P1a), siehe #1199.

## Risiken

1. **Golden-Tests brechen absichtlich.** Mindestens vier Testdateien sichern die heutigen
   Betreffe byte-genau und müssen mit dem Produktivfix zusammen umgestellt werden — nie vorher,
   sonst beweist der Test nichts.
2. **Renderer-Commit-Gate greift.** Jeder Commit an `src/output/renderers/alert/*.py` blockt, bis
   `tests/tdd/test_issue_811_mode_matrix.py` grün ist und ein `briefing_mail_validator.py`-Lauf
   bestanden hat.
3. **A2 berührt ADR-0033-Fläche.** Die Entscheidung selbst (nur betroffener Umfang) bleibt gültig;
   geändert wird nur ihr Träger. Ein neues ADR hält den geänderten Aufbau fest und verweist auf
   ADR-0033 als weiterhin bindend.
