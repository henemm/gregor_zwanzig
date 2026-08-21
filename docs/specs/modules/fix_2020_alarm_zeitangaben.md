---
entity_id: fix_2020_alarm_zeitangaben
type: module
created: 2026-08-21
updated: 2026-08-21
status: draft
version: "1.0"
tags: [alert, deviation-alert, zeitangaben, issue-2020]
---

# Abweichungsalarm: Zeitangaben sagen, was sie meinen und wann sie liegen

## Approval

- [ ] Approved

## Purpose

Der Abweichungsalarm nennt mehrere Uhrzeiten nebeneinander, ohne zu sagen, welche Größe
jede meint und auf welchen Tag sie sich bezieht — und formuliert sie durchgängig so, als
läge das Ereignis noch bevor. Diese Spec macht jede Zeitangabe im Abweichungsalarm
selbsterklärend: sie benennt ihre Größe, trägt einen Tagesbezug, wenn der Tag vom
Versandtag abweicht, und wird als vergangen ausgewiesen, wenn sie vergangen ist.

## Source

- **File:** `src/output/renderers/alert/project.py`, `src/output/renderers/alert/render.py`,
  `src/output/renderers/alert/model.py`
- **Identifier:** `to_alert_message()`, `_datablock_single()`, `_onset_shift_line()`,
  `_onset_time_label()`, `AlertEvent`, `OnsetShiftEvent`

## Estimated Scope

- **LoC:** ~80 Produktivcode (+80/-25), ~150 Test
- **Files:** 5 MODIFY, 1 CREATE
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/utils/timezone.py` → `day_offset()` | reuse | Kalendertage zwischen jetzt und Zielzeitpunkt in Ortszeit (aus #2009) |
| `src/utils/timezone.py` → `local_fmt()` | reuse | `HH:MM` in Ortszeit — unverändert |
| `src/services/notification_service.py:662` | caller | berechnet `datetime.now(timezone.utc)` bereits, reicht es künftig durch |
| `src/services/validator_render_service.py:144` | caller | zweiter Aufrufer der Projektion, reicht dieselbe Referenzzeit durch |
| `src/services/trip_alert.py:1330` | observability | Briefing-Unterdrückung des Nowcasts protokollieren |

## Implementation Details

**Arbeitsteilung wie in #2009: Die Projektion rechnet, der Renderer formuliert.**

```
notification_service.py:662   now_utc = datetime.now(timezone.utc)   (existiert bereits)
        │
        ▼
to_alert_message(..., now_utc=now_utc)          project.py
        │   je Zeitangabe:
        │     day_offset(now_utc, ziel_utc, tz)  -> int (negativ = Vergangenheit)
        │     ziel_utc < now_utc                 -> bool
        ▼
AlertEvent.occurred_at            "17:00"   (UNVERAENDERT — bestehende Wert-Tests bleiben gruen)
AlertEvent.occurred_day_offset    int       (NEU, additiv)
AlertEvent.occurred_is_past       bool      (NEU, additiv)
OnsetShiftEvent.to_day_offset     int       (NEU, additiv)
OnsetShiftEvent.to_is_past        bool      (NEU, additiv)
        │
        ▼
render.py    setzt die Worte — E-Mail (HTML + Klartext), Telegram, SMS, Premium-SMS
```

**Wortlaut (Vorschlag zur Freigabe — hier entscheidet der PO):**

| Lage | Zeile „Wo & wann" | Zeile „Niedersch-Beginn" |
|---|---|---|
| Zeitpunkt liegt heute noch bevor | `🏁 Ziel · stärkste Stunde 17:00` | `19:00 → 15:00 (4 h früher)` |
| Zeitpunkt ist heute schon vorbei | `🏁 Ziel · stärkste Stunde war 17:00` | `19:00 → seit 15:00 (4 h früher)` |
| Zeitpunkt liegt an einem anderen Tag | `🏁 Ziel · stärkste Stunde morgen 17:00` | `19:00 → morgen 15:00 (4 h früher)` |

Der Tagesbezug erscheint **nur**, wenn der Tag vom Versandtag abweicht. Für den
Versandtag selbst trägt die Fußzeile („Stand: heute 18:15") den Tag bereits; ein
zusätzliches „heute" in jeder Zeile wäre Lärm.
*Alternative, falls der PO es ausdrücklich will: „heute" immer ausschreiben. Das ist
eine reine Wortentscheidung und ändert an der Mechanik nichts.*

**Härtung des bestehenden Tagesbezugs:** `render.py:310` prüft heute auf Wahrheitswert
(`if e.onset_day_offset`) und macht damit aus **jedem** Versatz ungleich null ein
„morgen" — auch aus `-1`. Im Nowcast-Pfad unerreichbar, im Abweichungsalarm der
Normalfall. Die Auflösung erfolgt künftig über den **exakten** Versatz:
`-1 → gestern`, `0 → (kein Wort)`, `1 → morgen`, alles darüber/darunter → Wochentag.

## Expected Behavior

- **Input:** `changes` (WeatherChange-Liste mit `occurred_at`/Onset-Epochenwerten),
  `tz` (Ortszeit des Segment-Startpunkts), **neu** `now_utc` (Referenzzeit des Versands)
- **Output:** Alarm-Nachricht in vier Kanälen, in der jede Uhrzeit ihre Größe benennt,
  ihren Tagesbezug trägt und ihre Vergangenheit ausweist
- **Side effects:** Keine. Zusätzlich wird die bereits bestehende Unterdrückung eines
  Nowcasts durch das Briefing im Alarm-Protokoll vermerkt (bisher nur `logger.debug`).

## Acceptance Criteria

- **AC-1:** Given ein Abweichungsalarm, dessen Niederschlagsbeginn zum Versandzeitpunkt
  bereits verstrichen ist (Beginn 15:00 Ortszeit, Versand 15:30 Ortszeit) / When die
  Alarm-Nachricht gerendert wird / Then weist die Beginn-Zeile den Zeitpunkt als
  vergangen aus (`19:00 → seit 15:00 (4 h früher)`) und formuliert ihn nicht als
  bevorstehend.
  - Test: Nachricht mit vergangener Onset-Zeit rendern und prüfen, dass der Klartext
    die Vergangenheitsform trägt; Gegenprobe mit künftiger Onset-Zeit, die sie nicht trägt.

- **AC-2:** Given ein Abweichungsalarm, dessen Zeitpunkt auf einem anderen Kalendertag
  als dem Versandtag liegt / When die Nachricht gerendert wird / Then nennt die
  Zeitangabe den Tag beim Namen, und zwar passend zum tatsächlichen Versatz — `-1`
  ergibt „gestern", `+1` ergibt „morgen".
  - Test: Je ein Rendering mit Versatz `-1` und `+1` gegen dieselbe Uhrzeit; der
    `-1`-Fall darf unter keinen Umständen „morgen" ergeben (Regression zur
    Wahrheitswert-Prüfung in `render.py:310`).

- **AC-3:** Given ein Abweichungsalarm mit einer Wertänderung, deren Spitzenwert zu
  einer bestimmten Stunde auftritt / When die Nachricht gerendert wird / Then benennt
  die Zeile „Wo & wann" die Uhrzeit als Zeitpunkt des stärksten Werts und lässt sie
  nicht unkommentiert neben einer Beginn-Zeit stehen.
  - Test: Gerenderte Zeile enthält die Kennzeichnung der Größe zusätzlich zum Ort und
    zur Uhrzeit.

- **AC-4:** Given ein Abweichungsalarm, der gleichzeitig eine Wertänderung UND eine
  Beginn-Verschiebung trägt (der Fall aus #2020, bisher von keinem Test abgedeckt) /
  When die Nachricht gerendert wird / Then stehen beide Zeitangaben mit
  unterscheidbarer Bedeutung in derselben Nachricht, sodass eine Spitze um 17:00 neben
  einem Beginn um 15:00 nicht als Widerspruch lesbar ist.
  - Test: Eine `AlertMessage` mit befülltem `events` UND `onset_shift_events` rendern
    und prüfen, dass beide Zeilen ihre Größe benennen.

- **AC-5:** Given dieselbe Alarm-Nachricht mit vergangenem Zeitpunkt / When sie in alle
  vier Kanäle gerendert wird (E-Mail HTML, E-Mail Klartext, Telegram, SMS,
  Premium-SMS) / Then trägt jeder Kanal die Vergangenheits- bzw. Tagesbezug-Information;
  kein Kanal fällt auf die alte, mehrdeutige Form zurück.
  - Test: Rendering je Kanal prüfen; für die Kurznachricht zusätzlich, dass die
    160-Zeichen-Grenze eingehalten bleibt.

- **AC-6:** Given ein Testlauf zu einem beliebigen Systemdatum / When die Nachricht mit
  einer explizit übergebenen Referenzzeit gerendert wird / Then hängt das Ergebnis
  ausschließlich von dieser Referenzzeit ab und nicht von der Systemuhr.
  - Test: Dasselbe Rendering zweimal mit unterschiedlicher Referenzzeit und identischen
    Wetterdaten ergibt unterschiedliche Tagesbezüge; kein Aufruf von `datetime.now()`
    im Renderpfad der Zeitdarstellung.

- **AC-7:** Given ein Nowcast, der unterdrückt wird, weil das Briefing den Niederschlag
  bereits angekündigt hatte / When der Alarm-Tick durchläuft / Then hinterlässt die
  Unterdrückung einen nachvollziehbaren Eintrag im Alarm-Protokoll mit dem Grund,
  statt nur eine Debug-Zeile im Anwendungs-Log.
  - Test: Tick mit angekündigtem, nicht-konvektivem Niederschlag auslösen und prüfen,
    dass ein Unterdrückungs-Eintrag mit dem Grund im Protokoll landet.

## Known Limitations

- **„Stärkste Stunde" ist für maximum- und summenbasierte Größen treffend**
  (Niederschlag, Windböe, Gewitter). Für eine künftige Größe, deren Alarm auf einem
  Minimum beruht, kann die Formulierung schief wirken. Die Aggregationsart liegt im
  Katalog vor und ließe sich später in das Wort übersetzen; das ist hier bewusst nicht
  Teil des Zuschnitts.
- **Der Tagesbezug erscheint nicht am Versandtag.** Wer die Fußzeile „Stand: heute
  18:15" überliest, hat für Zeiten desselben Tages weiterhin keinen expliziten Tag.
  Bewusste Abwägung gegen Textlärm; per PO-Entscheid umkehrbar.
- **Kein Vier-Kanäle-Wächter.** Es gibt keinen automatischen Test, der bei künftigen
  Textänderungen alle vier Kanäle einfordert. AC-5 deckt den hier geänderten Fall ab,
  nicht die Gattung. → Eintrag für #1196.

## Nicht-Ziele (ausdrücklich ausgeschlossen)

- **Wiederholung desselben Alarms und die stehende Vergleichsbasis.** Der Alarm ging am
  2026-08-20 um 15:30 und um 18:15 mit bitgleichem Inhalt raus, weil die
  Vergleichsbasis bewusst den ganzen Tag stehen bleibt (`trip_alert.py:412-413`,
  #1916). Das gehört zu **#2018** und **#1987** — die #2018-Session hat die Belege.
- **Früher warnen.** Untersucht und ausgeschlossen: Die Prüfung läuft alle 15 Minuten
  ohne Ergebnis-Cache; Open-Meteo hat den Beginn nachträglich auf einen bereits
  verstrichenen Zeitpunkt vorverlegt. Ein schnellerer Takt ändert daran nichts.
- **Ein Filter, der vergangene Ereignisse unterdrückt.** Er hätte die beanstandete Mail
  nicht verhindert (der Regen lief um 18:15 noch, das Etappenfenster reichte bis 20:00)
  und würde künftig wertvolle Meldungen verschlucken. Der Fehler ist die Formulierung,
  nicht die Zustellung.
- **Die Auslöseregel des Nowcasts ändern.** Dass ein mit 7,4 mm angekündigter Regen die
  Unterdrückung eines Nowcasts über 29,4 mm rechtfertigt, ist fachlich fragwürdig — aber
  eine eigene Produktentscheidung mit Flut-Risiko. AC-7 macht die Unterdrückung
  zunächst nur **sichtbar**; die Regeländerung bekommt ein eigenes Issue.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Die Spec führt keine neue Entscheidungsfläche ein, sondern zieht eine
  bereits in #2009 getroffene Entscheidung (Tagesbezug als additives Modellfeld,
  Rechnen in der Projektion, Formulieren im Renderer) auf den zweiten Alarmpfad nach.

## Changelog

- 2026-08-21: Initial spec created (Issue #2020)
