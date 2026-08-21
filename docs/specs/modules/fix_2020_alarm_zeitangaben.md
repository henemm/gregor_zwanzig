---
entity_id: fix_2020_alarm_zeitangaben
type: module
created: 2026-08-21
updated: 2026-08-21
status: draft
version: "1.0"
tags: [alert, deviation-alert, zeitangaben, issue-2020, scheibe-2]
---

# Abweichungsalarm: Zeitangaben sagen, was sie meinen und wann sie liegen (Scheibe 2)

## Approval

- [ ] Approved

## Purpose

Der Abweichungsalarm nennt mehrere Uhrzeiten nebeneinander, ohne zu sagen, welche Größe
jede meint und auf welchen Tag sie sich bezieht — und formuliert sie durchgängig so, als
läge das Ereignis noch bevor. Diese Spec macht jede Zeitangabe im Abweichungsalarm
selbsterklärend: sie benennt ihre Größe, trägt einen Tagesbezug, wenn der Tag vom
Versandtag abweicht, und wird als vergangen ausgewiesen, wenn sie vergangen ist.
**Scheibe 2** von #2020 — Scheibe 1 (Auslösung/Mengen-Überholung) ist bereits in
Produktion (`b423c913`). Diese Scheibe ändert **keine** Auslösung, nur den Wortlaut.

## Source

- **File:** `src/output/renderers/alert/project.py`, `src/output/renderers/alert/render.py`,
  `src/output/renderers/alert/model.py`
- **Identifier:** `to_alert_message()`, `_datablock_single()`, `_onset_shift_line()`,
  `_onset_time_label()`, `AlertEvent`, `OnsetShiftEvent`

## Estimated Scope

- **LoC:** ~80 Produktivcode (+80/-25), ~150 Test
- **Files:** 5 MODIFY, 1 CREATE

### Affected Files

| Datei | Change Type | Description |
|---|---|---|
| `src/output/renderers/alert/model.py` | MODIFY | additive Felder (Tagesversatz, Vergangenheits-Merker) an `AlertEvent` und `OnsetShiftEvent`, mit Default, am Ende des Feldblocks |
| `src/output/renderers/alert/project.py` | MODIFY | Projektion rechnet den Versatz (`day_offset(now_utc, ziel_utc, tz)`) und den Vergangenheits-Merker je Zeitangabe; `_fmt_occurred_at`/`_fmt_onset_at` bleiben in ihrer Form |
| `src/output/renderers/alert/render.py` | MODIFY | Langform (E-Mail/Telegram) formuliert `gestern HH:MM`/`vor N Tagen HH:MM`/`morgen HH:MM`/`seit HH:MM`; Kurzform (SMS/Premium-SMS) klebt das Wochentagskürzel vor die Stunde (`R7@Do15`); Bedeutungswort für die Spitzenstunde in der „Wo & wann"-Zeile; `_onset_time_label` wird auf den exakten Versatz gehärtet. **NICHT** anfassen: `_render_sms_onset`, `to_multi_location_onset_alert_message`, `_sms_onset_time` (Fläche der #2046-Session, siehe Abschnitt „Zur Entscheidung mit der Freigabe") |
| `src/services/notification_service.py` | MODIFY | reicht die bereits vorhandene `now_utc` (`:662`) durch |
| `src/services/validator_render_service.py` | MODIFY | zweiter Aufrufer, reicht dieselbe Referenzzeit durch |
| `tests/tdd/…` | CREATE | neue Testdatei, nach Verhalten benannt (nicht nach Issue-Nummer) |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/utils/timezone.py` → `day_offset()` | reuse | Kalendertage zwischen jetzt und Zielzeitpunkt in Ortszeit (aus #2009) |
| `src/utils/timezone.py` → `format_reference_at()` | reuse | liefert bereits die Hausnotation `gestern HH:MM Uhr`/`vor N Tagen HH:MM Uhr` für die Fußzeile — dieselbe Wortwahl gilt jetzt auch für die Ereignis-Zeitangaben selbst |
| `src/utils/timezone.py` → `local_fmt()` | reuse | `HH:MM` in Ortszeit — unverändert |
| `src/output/renderers/alert/official_alerts.py` → `_de_weekday_short()` (`:802`) | reuse | liefert das Wochentagskürzel für die Kurzform — **nicht** nachbauen |
| `src/services/notification_service.py:662` | caller | berechnet `datetime.now(timezone.utc)` bereits, reicht es künftig durch |
| `src/services/validator_render_service.py:144` | caller | zweiter Aufrufer der Projektion, reicht dieselbe Referenzzeit durch |

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

**Wortlaut — Langform (E-Mail + Telegram), Bestandsnotation aus `format_reference_at`:**

| Lage | Zeile „Wo & wann" | Zeile „Niedersch-Beginn" |
|---|---|---|
| Zeitpunkt liegt heute noch bevor | `🏁 Ziel · stärkste Stunde 17:00` | `19:00 → 15:00 (4 h früher)` |
| Zeitpunkt ist heute schon vorbei | `🏁 Ziel · stärkste Stunde war 17:00` | `19:00 → seit 15:00 (4 h früher)` |
| Zeitpunkt liegt einen Tag zurück | `🏁 Ziel · stärkste Stunde war gestern 17:00` | `19:00 → gestern 15:00 (4 h früher)` |
| Zeitpunkt liegt ≥2 Tage zurück | `🏁 Ziel · stärkste Stunde war vor 2 Tagen 17:00` | `19:00 → vor 2 Tagen 15:00 (4 h früher)` |
| Zeitpunkt liegt einen Tag voraus | `🏁 Ziel · stärkste Stunde morgen 17:00` | `19:00 → morgen 15:00 (4 h früher)` |

Das ist **keine Neuerfindung**: `format_reference_at` (`src/utils/timezone.py:154-169`)
erzeugt `gestern HH:MM Uhr`/`vor N Tagen HH:MM Uhr` bereits heute für die Fußzeile
(„Stand: heute 18:15 · verglichen mit gestern 18:03 Uhr", `render.py:784-786/845-847/949-951`).
Diese Scheibe wendet dieselbe Hausnotation auf die Ereignis-Zeitangaben selbst an, statt
eine zweite Schreibweise zu erfinden. Für die Zukunft existiert bereits `morgen HH:MM`
(`_onset_time_label`, `render.py:367-374`); der Tagesbezug erscheint **nur**, wenn der
Tag vom Versandtag abweicht — für den Versandtag selbst trägt die Fußzeile den Tag
bereits, ein zusätzliches „heute" in jeder Zeile wäre Lärm.

**Wortlaut — Kurzform (SMS + Premium-SMS), Bestandsnotation der amtlichen Warnung:**
Das Wochentagskürzel klebt vor die Stunde, `_de_weekday_short()` (`official_alerts.py:802`,
Muster `Do12-22`/`Fr22-Sa03`). Aus dem Δ-Token `R7@15` (`render.py:990-993`) wird bei
Versatz `-1` an einem Donnerstag `R7@Do15`. Am **heutigen** Tag entfällt das Kürzel
ersatzlos (dieselbe Regel wie #1948 S5, `official_alerts.py:1929-1943`).

**Verworfen: ein Zahlensuffix (`17:00-1`).** Drei belegte Gründe:
1. `-` ist in der Kurzform bereits dreifach belegt — Wert gefallen (`-R7`, `render.py:987`),
   Bereichstrenner (`12-22`), km-Spanne (`km8-8`, `render.py:1006`).
2. Die Fensterform der amtlichen Warnung ist formgleich: `_tag_hour()`
   (`official_alerts.py:1896-1902`) setzt Minuten, sobald sie nicht auf `:00` liegen —
   ein Gültigkeitsfenster lautet dann `15:20-17`, neben einem Tagesversatz `17:00-1` nicht
   mehr per Form unterscheidbar.
3. `_sms_onset_time()` hängt das Vorzeichen fest an (`f"{base}+{day_offset}"`,
   `render.py:550`) — mit `day_offset = -1` entstünde `17:00+-1`. Diese Funktion bleibt
   in dieser Scheibe unangetastet (siehe Abschnitt „Zur Entscheidung mit der Freigabe").

**Ein gemeinsamer Baustein für das Tageswort der Langform — nicht zwei.**
Heute löst `_onset_time_label()` (`render.py:367-374`) den Tagesversatz auf, arbeitet
aber auf `OnsetEvent` (Nowcast) und prüft nur auf **Wahrheitswert**:

```
render.py:374:  return f"morgen {e.onset_time}" if e.onset_day_offset else e.onset_time
```

Damit wird aus **jedem** Versatz ungleich null ein „morgen" — auch aus `-1`. Im
Nowcast-Pfad ist das unerreichbar (Vorwärtsfenster, `radar_service.py:599-602`), im
Abweichungsalarm wäre es der Normalfall.

Deshalb: eine **typunabhängige Hilfsfunktion** `(hhmm: str, day_offset: int, is_past: bool) -> str`
löst den **exakten** Versatz in das Wort auf (`-1 → gestern`, `-N → vor N Tagen`,
`0 & vergangen → seit … (kein Tageswort)`, `0 & bevorstehend → kein Wort`,
`1 → morgen`). `_onset_time_label()` wird auf sie umgestellt, der Abweichungsalarm
benutzt dieselbe. Eine zweite Auflösungstabelle daneben wäre genau die Doppelpflege, die
das Projekt an anderer Stelle (#1435) abgeschafft hat.

**Nachbarschaft in Bewegung:** `render.py` wird parallel von **#2036**
(`fix-2036-alarm-kilometer`, additives `km_measured: bool = False` an allen vier
Event-Dataclasses, `km{A}-{B}` → `km {A}-{B}`) angefasst. Vor dem Schreiben rebasen.

## Expected Behavior

- **Input:** `changes` (WeatherChange-Liste mit `occurred_at`/Onset-Epochenwerten),
  `tz` (Ortszeit des Segment-Startpunkts), **neu** `now_utc` (Referenzzeit des Versands)
- **Output:** Alarm-Nachricht in vier Kanälen, in der jede Uhrzeit ihre Größe benennt,
  ihren Tagesbezug trägt und ihre Vergangenheit ausweist
- **Side effects:** Keine.

## Acceptance Criteria

- **AC-1:** Given ein Abweichungsalarm, dessen Niederschlagsbeginn zum Versandzeitpunkt
  bereits verstrichen ist, aber am selben Kalendertag liegt (Beginn 15:00 Ortszeit,
  Versand 15:30 Ortszeit) / When die Alarm-Nachricht gerendert wird / Then weist die
  Beginn-Zeile den Zeitpunkt als vergangen aus (`19:00 → seit 15:00 (4 h früher)`) und
  formuliert ihn nicht als bevorstehend.
  - Test: Nachricht mit vergangener Onset-Zeit rendern und prüfen, dass der Klartext
    die Vergangenheitsform trägt; Gegenprobe mit künftiger Onset-Zeit, die sie nicht trägt.

- **AC-2:** Given ein Abweichungsalarm, dessen Zeitpunkt auf einem anderen Kalendertag
  als dem Versandtag liegt / When die Nachricht in E-Mail oder Telegram gerendert wird
  / Then nennt die Zeitangabe den Tag beim Namen, in der Hausnotation aus
  `format_reference_at` — `-1` ergibt `gestern 15:00`, `-2` ergibt `vor 2 Tagen 15:00`,
  `+1` ergibt `morgen 15:00`.
  - Test: Je ein Rendering mit Versatz `-1`, `-2` und `+1` gegen dieselbe Uhrzeit; der
    `-1`- und `-2`-Fall dürfen unter keinen Umständen „morgen" ergeben (Regression zur
    Wahrheitswert-Prüfung in `render.py:374`). Dieselbe Gegenprobe gilt für den
    Nowcast-Pfad, der auf denselben Baustein umgestellt wird.

- **AC-3:** Given ein Abweichungsalarm mit einer Wertänderung, deren Spitzenwert zu
  einer bestimmten Stunde auftritt / When die Nachricht gerendert wird / Then benennt
  die Zeile „Wo & wann" die Uhrzeit ausdrücklich als Zeitpunkt des stärksten Werts
  (`🏁 Ziel · stärkste Stunde 17:00`, bzw. `stärkste Stunde war 17:00` bei einem
  vergangenen Zeitpunkt) und lässt sie nicht unkommentiert neben einer Beginn-Zeit
  stehen. Das Wort „stärkste Stunde" ist neu im Bestand — es reiht sich neben die
  etablierten Bedeutungs-Marker `ab` (Beginn), `-Beginn`, `jetzt`, `Stand:`,
  `verglichen mit`, `Gültig:` ein, ohne mit einem davon zu kollidieren.
  - Test: Gerenderte Zeile enthält die Kennzeichnung der Größe zusätzlich zum Ort und
    zur Uhrzeit; Gegenprobe, dass eine reine Beginn-Zeile (`-Beginn`) weiterhin ohne
    dieses Wort auskommt.

- **AC-4:** Given ein Abweichungsalarm, der gleichzeitig eine Wertänderung UND eine
  Beginn-Verschiebung trägt (der Fall aus #2020, bisher von keinem Test abgedeckt) /
  When die Nachricht gerendert wird / Then stehen beide Zeitangaben mit
  unterscheidbarer Bedeutung in derselben Nachricht, sodass eine Spitze um 17:00 neben
  einem Beginn um 15:00 nicht als Widerspruch lesbar ist.
  - Test: Eine `AlertMessage` mit befülltem `events` UND `onset_shift_events` rendern
    und prüfen, dass beide Zeilen ihre Größe benennen.

- **AC-5:** Given dieselbe Alarm-Nachricht mit einem Zeitpunkt an einem anderen
  Kalendertag als dem Versandtag / When sie in alle vier Kanäle gerendert wird (E-Mail
  HTML, E-Mail Klartext, Telegram, SMS, Premium-SMS) / Then tragen E-Mail und Telegram
  die Langform (`gestern 15:00`), SMS und Premium-SMS tragen das Wochentagskürzel
  geklebt vor die Stunde des Kurzform-Tokens — aus `R7@15` wird bei einem Donnerstag
  `R7@Do15`; kein Kanal fällt auf die alte, mehrdeutige Form zurück; die
  160-Zeichen-Grenze der Kurznachricht bleibt eingehalten.
  - Test: Rendering je Kanal prüfen; für die Kurznachricht zusätzlich, dass die
    160-Zeichen-Grenze eingehalten bleibt.

- **AC-6:** Given ein Testlauf zu einem beliebigen Systemdatum / When die Nachricht mit
  einer explizit übergebenen Referenzzeit gerendert wird / Then hängt das Ergebnis
  ausschließlich von dieser Referenzzeit ab und nicht von der Systemuhr.
  - Test: Dasselbe Rendering zweimal mit unterschiedlicher Referenzzeit und identischen
    Wetterdaten ergibt unterschiedliche Tagesbezüge; kein Aufruf von `datetime.now()`
    im Renderpfad der Zeitdarstellung. Zusätzlich: `test_onset_shift_alert.py` und
    `test_alert_event_time_uses_local_timezone.py` (beide ohne `freeze_time`, feste
    Kalenderdaten) bleiben grün, weil sie die Referenzzeit künftig explizit setzen.

- **AC-7:** Given zwei Kurzform-Ausschnitte, die im selben Kanal nebeneinander
  vorkommen können — die Tagesbezug-Form dieses Alarms (`R7@Do15`) und die Fensterform
  der amtlichen Warnung (`Do12-22` bzw. `15:20-17` bei `_tag_hour`) / When ein
  Wächter-Test beide aus dem echten Renderer-Code zieht und in einer Zeile
  gegenüberstellt / Then macht eine spätere Änderung der Fensterform (z.B. Umstellung
  auf `HH:MM-HH:MM`) diesen Test sofort rot, bevor die Verwechselbarkeit in Produktion
  erneut auftritt.
  - Test: Testfall ruft `_tag_hour`/`_de_weekday_short` und den neuen Tagesbezug-Baustein
    mit denselben Beispielwerten auf und prüft strukturelle Unterscheidbarkeit (keine
    Form, bei der beide Ausgaben identisch aussehen könnten); der Test bricht, wenn
    jemand die Fensterform ohne Rücksicht auf diese Kollision ändert.

## Zur Entscheidung mit der Freigabe

Ein Punkt gehört zur Freigabe, ist aber kein Akzeptanzkriterium, weil diese Scheibe ihn
nicht umsetzt:

**Zieht der Radar-Onset-Kurzform-Zweig nach?** Er schreibt denselben Sachverhalt heute als
Zahlensuffix (`17:00+1`, `_sms_onset_time`, `render.py:550`). Bleibt er so, trägt der
Kurzkanal zwei Schreibweisen für „Uhrzeit an einem anderen Tag" nebeneinander.

- **Empfehlung:** Wochentagskürzel für beide Zweige — dann gibt es genau eine Schreibweise.
  Die Umstellung ist **nicht** Teil dieser Scheibe; sie wird ein Folgeticket der
  #2046-Session, die diesen Zweig ohnehin gerade bearbeitet und die Anlage zugesagt hat.
- **Alternative:** Onset bleibt bei `+1`. Dann gehört die Begründung in den
  Freigabe-Kommentar, damit die Abweichung dokumentiert ist und nicht als Versehen
  wiederkehrt.

`_sms_onset_time` bleibt in dieser Scheibe in jedem Fall unangetastet.

## Known Limitations

- **„Stärkste Stunde" ist für maximum- und summenbasierte Größen treffend**
  (Niederschlag, Windböe, Gewitter). Für eine künftige Größe, deren Alarm auf einem
  Minimum beruht, kann die Formulierung schief wirken. Die Aggregationsart liegt im
  Katalog vor und ließe sich später in das Wort übersetzen; das ist hier bewusst nicht
  Teil des Zuschnitts.
- **Der Tagesbezug erscheint nicht am Versandtag.** Wer die Fußzeile „Stand: heute
  18:15" überliest, hat für Zeiten desselben Tages weiterhin keinen expliziten Tag.
  Bewusste Abwägung gegen Textlärm; per PO-Entscheid umkehrbar.
- **Kein Vier-Kanäle-Wächter für Zeit-Label allgemein.** Es gibt keinen automatischen
  Test, der bei künftigen Textänderungen alle vier Kanäle einfordert. AC-5 deckt den
  hier geänderten Fall ab, nicht die Gattung. → Eintrag für #1196.
- **`CorridorEvent` bleibt unangetastet.** Der Schwellen-Alarm-Zweig (`render.py:263`,
  `_sms_corridor_token`) wirft ebenfalls Minuten weg, ist aber keine der beiden
  Ereignisarten aus dem gemeldeten Vorfall (B3/B4). Außerhalb des Zuschnitts dieser
  Scheibe; ein analoger Tagesbezug wäre ein eigenes Ticket.
- **`_sms_onset_time` (Radar-Onset-Zahlensuffix) bleibt unangetastet** — Gegenstand von
  AC-7, Umsetzung ggf. per Folgeticket der #2046-Session.

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
- **Die Auslöseregel des Nowcasts ändern — bereits erledigt, gehört nicht zu dieser
  Scheibe.** Scheibe 1 (#2020, Prod `b423c913`) hat die Briefing-Sperre bereits
  gehärtet: sie bricht jetzt bei mengenmäßiger Überholung
  (`window_precip_mm >= 2 × _briefing_precip` UND `>= 2,0 mm`). Diese Scheibe ändert
  **keine** Auslösung mehr — sie ändert ausschließlich, **wie** die bereits ausgelöste
  Nachricht ihre Zeitangaben formuliert.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Die Spec führt keine neue Entscheidungsfläche ein, sondern zieht eine
  bereits in #2009 getroffene Entscheidung (Tagesbezug als additives Modellfeld,
  Rechnen in der Projektion, Formulieren im Renderer) auf den zweiten Alarmpfad nach,
  und übernimmt für die Wortwahl ausschließlich bereits im Bestand etablierte
  Notationen (`format_reference_at`, Wochentagskürzel der amtlichen Warnung) statt neue
  zu erfinden.

## Changelog

- 2026-08-21: Initial spec created (Issue #2020)
- 2026-08-21: Scheibe-2-Zuschnitt nach Auslieferung von Scheibe 1 (Prod `b423c913`)
  aktualisiert: AC-7 (Nowcast-Protokoll-Sichtbarkeit) entfernt — von Scheibe 1 bereits
  geliefert (`trip_alert.py:1390`, `alert_log.append_suppressed_entry`). Nicht-Ziel
  „Auslöseregel des Nowcasts ändern" umgeschrieben — Scheibe 1 hat die Auslösung
  bereits geändert (Mengen-Überholung), diese Scheibe rührt daran nicht mehr.
  Tagesbezug-Wortlaut auf die bestehenden Bestandsnotationen festgelegt: Langform
  (E-Mail/Telegram) übernimmt `gestern HH:MM`/`vor N Tagen HH:MM` aus
  `format_reference_at`, Kurzform (SMS/Premium-SMS) übernimmt das klebende
  Wochentagskürzel der amtlichen Warnung (`R7@Do15`); das erwogene Zahlensuffix
  `17:00-1` verworfen (drei belegte Kollisionsgründe). Zwei neue ACs ergänzt: AC-7
  (offene PO-Entscheidung zur Vereinheitlichung mit `_sms_onset_time`) und AC-8
  (Wächter-Test gegen Formkollision mit der amtlichen Warnung).
