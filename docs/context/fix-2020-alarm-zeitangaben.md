# Context: fix-2020-alarm-zeitangaben

Issue: [#2020](https://github.com/henemm/gregor_zwanzig/issues/2020) · `priority:critical` · `type:bug` · `session:alarm`
Basis: `d7fad756` (enthält #2009 und #2017 A)

## Request Summary

Ein Abweichungsalarm (Trip „KHW 403", Ort „Ziel") nennt drei Uhrzeiten, die der PO
als widersprüchlich liest: „Wo & wann · Ziel 17:00", „Niedersch-Beginn 19:00 → 15:00
(4 h früher)" und „Stand: heute 18:15 · verglichen mit 07:02". Vier Beanstandungen:
(1) die Zeiten passen nicht zusammen, (2) das jüngste Uhrzeiten-Rework taugt nichts,
(3) die Warnung kommt nach dem Ereignis, (4) warum kam kein Nowcast.

## Der reale Vorfall — aus dem Produktiv-Alarmprotokoll rekonstruiert

Quelle: `/var/lib/gregor/users/henning/alert_log.json`, Trip `5f534011`, 2026-08-20.
Ortszeit = Europe/Rome (UTC+2), Ziel-Wegpunkt G4 bei 46,730 N / 12,322 O (Innichen).

| Versand (UTC) | Ortszeit | reason | Inhalt |
|---|---|---|---|
| 13:30:20 | **15:30** | `forecast_change` | `precipitation/onset` 1787245200 → 1787230800 · `precipitation/sum` 7,4 → 29,4 |
| 16:15:16 | **18:15** | `forecast_change` | **bitgleich dieselben Werte** |

Umgerechnet: Beginn verschiebt sich von **19:00** auf **15:00** Ortszeit, Menge 7,4 → 29,4 mm.
Die zweite Zeile ist die Mail aus dem Screenshot.

Daraus folgen vier belegte Befunde:

**B1 — Die Warnung kam nach dem Ereignis, und zwar zweimal.**
Der gemeldete Regenbeginn liegt um 15:00 Ortszeit. Der **erste** Versand ging um 15:30 —
30 Minuten zu spät. Der **zweite** um 18:15 — 3 h 15 zu spät, und da war auch die
gemeldete Spitze (17:00) schon vorbei. Im Auswertungskern gibt es **keinen
Vergangenheitsfilter**: `weather_change_detection.py` prüft nirgends `occurred_at`
oder die Onset-Zeit gegen „jetzt". Einzige Spur ist eine reine Debug-Warnung in
`src/services/segment_weather.py:424-427`, die nichts unterdrückt.

**B2 — Derselbe Alarm wurde unverändert wiederholt.**
Beide Einträge tragen identische `value`/`previous_value`. Die **Vergleichsbasis ist
nach dem ersten Versand nicht nachgezogen** (`previous` bleibt 7,4). Der Trip hat
`alert_cooldown_minutes: 30`; bei 2 h 45 Abstand greift der Cooldown nicht. Das ist
die Fläche von **#2018** (Session `intake-2018`) und **#1987/#1916** — hier nur als
Kontext festgehalten, **nicht** Gegenstand dieses Tickets.

**B3 — „Wo & wann" ist nicht „wann es losgeht".**
`17:00` ist der **Spitzenwert-Zeitpunkt** der geänderten Metrik
(`render.py:589` ← `AlertEvent.occurred_at` ← `_peak_occurred_at()`,
`weather_change_detection.py:301-368`: Scan der Stundenreihe im Segmentfenster nach
der Stunde mit der größten Regenmenge). `15:00` ist der **Beginn**
(`OnsetShiftEvent.to_time`, `project.py:113-122`). Zwei verschiedene Größen, beide
unter Bezeichnungen, die nach „wann" klingen, direkt untereinander.
Beide Zweige laufen seit #1468 **völlig unabhängig** in dieselbe Mail
(`project.py:141-170`, Verzweigung über `_is_onset_change()`); es gibt **keine
Kreuzprüfung und keinen Test**, der sie gegeneinander hält.

**B4 — Keine der Uhrzeiten trägt einen Tagesbezug.**
#2009 hat genau diese Lücke am 2026-08-21 geschlossen — aber nur für den **Nowcast**
(`render.py:310`, `onset_day_offset` → „morgen HH:MM"). Der **Abweichungsalarm** hat
sie weiterhin: `occurred_at`, `from_time`, `to_time` und `stand_at` sind reine
`HH:MM`-Strings. Aus der Mail ist nicht erkennbar, ob 15:00/17:00 heute oder an einem
Folgetag liegen — obwohl der Rohwert (`_peak_occurred_at` liefert ein volles
`datetime`) den Tag kennt und erst die Projektionsschicht ihn wegwirft.

**Nicht die Ursache:** Zeitzonen. Alle vier Werte laufen über dieselbe
`local_fmt`/`tz_for_coords`-Familie in Ortszeit (`project.py:149,162`,
`notification_service.py:658-662`, `trip_alert.py:367-369`). Kein UTC/Lokal-Mix.

**Ebenfalls nicht die Ursache:** das Etappenfenster. Der „Ziel"-Abschnitt läuft
absichtlich bis zum Ende des Tagesfensters (Default 4–19 Uhr, also bis 20:00 Ortszeit,
`day_window.py:57-87`), nicht bis zur Ankunft um 12:45. Wetter um 15:00/17:00 am Ziel
zu bewerten ist also richtig — der Wanderer ist dann dort.

## Zu Beanstandung 4 — es kam sehr wohl Nowcast, nur nicht zu diesem Ereignis

Am 2026-08-20 stehen **sechs** `reason=nowcast`-Einträge im Protokoll
(09:52, 12:52, 13:52, 14:37, 15:22, 16:07 UTC) — **alle** zur Metrik `thunder/max`,
**keiner** zum Niederschlag. Zwei Code-belegte Gründe, warum der Regen keinen eigenen
Nowcast auslöste:

- **Briefing-Unterdrückung** (`trip_alert.py:1330`): Hatte das Briefing für den
  Onset-Zeitpunkt bereits ≥ 0,5 mm angekündigt und ist der Nowcast **nicht** konvektiv,
  wird er als redundant verworfen. Nur Gewitter/Hagel durchbricht die Sperre.
  **Beobachtbarkeits-Loch:** diese Unterdrückung schreibt nur `logger.debug`, **keinen**
  `alert_log`-Eintrag — sie ist im Protokoll unsichtbar.
- **Reines Vorwärtsfenster** (`radar_service.py:599-602`, `f.timestamp >= now`): Ein
  bereits verstrichener Beginn kann strukturell nie gefangen werden.

Ausgeschlossen: Region (46,6 N/12,8 O liegt in der GeoSphere-INCA-Box,
`radar_service.py:39-42`) und gegenseitige Sperre (Nowcast und Abweichungsalarm haben
getrennte Sperrzeit-Töpfe, `throttle_store.py:41-49`).

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/renderers/alert/project.py` | Projektionsschicht — wirft hier den Tag weg (`_fmt_occurred_at:67`, `_fmt_onset_at:91`); baut `events` und `onset_shift_events` getrennt (`141-170`) |
| `src/output/renderers/alert/render.py` | Mail/Telegram/SMS-Bauformen: `_datablock_single:558` („Wo & wann"), `_onset_shift_line:211`, Fußzeile `685/740`, Nowcast-Tagesbezug `_onset_time_label:310` |
| `src/output/renderers/alert/model.py` | `AlertEvent.occurred_at`, `OnsetShiftEvent.from_time/to_time`, `onset_day_offset` (#2009) |
| `src/services/weather_change_detection.py` | `_peak_occurred_at:301` — liefert volles `datetime`, kein Vergangenheitsfilter |
| `src/services/deviation_alert_engine.py` | Auswertungskern: Detektor, Filter, Severity, Quiet-Hours, Cooldown — Ort für einen Vergangenheitsfilter |
| `src/services/trip_alert.py` | Adapter; `reference_at` (`363-372`), Briefing-Unterdrückung des Nowcasts (`1316-1334`) |
| `src/services/notification_service.py` | `stand_at` (`658-662`) |
| `src/utils/timezone.py` | `local_fmt`, `tz_for_coords` — seit #2009 mit Tagesbezug-Baustein |
| `src/app/day_window.py` | Tagesfenster/`display_end_time` — erklärt, warum „Ziel" bis 20:00 bewertet wird |

## Existing Patterns

- **Tagesbezug gibt es schon** — #2009 hat ihn für den Nowcast eingeführt
  (`onset_day_offset` im Modell, „morgen HH:MM" im Renderer). Der Abweichungsalarm
  braucht dieselbe Bauform, keine zweite Erfindung.
- **Ortszeit-Auflösung je Punkt** ist etabliert (`_tz_for_location`, `tz_for_coords`).
- **Ein Katalog entscheidet, was eine Beginn-Größe ist** (`_is_onset_change()` über
  `metric_and_aggregation_for_field`) — keine zweite Feldliste im Renderer (#1435).
- **Alle vier Kanäle sind gleichrangig** (CLAUDE.md): eine Änderung an der
  Zeitdarstellung muss E-Mail, Telegram, SMS und Premium-SMS gemeinsam tragen.

## Existing Specs

- `docs/specs/modules/fix_2009_nowcast_vorlauf.md` — Tagesbezug für den Nowcast (Vorbild)
- `docs/specs/modules/issue_1168_alert_engine_extract.md` — Aufbau des Auswertungskerns
- `docs/adr/` — ADR-0013 (Δ-Schwelle), ADR-0035 (inklusive Fenster-Obergrenze)

## Dependencies

- **Upstream:** Open-Meteo-Vorhersage → `WeatherChangeDetectionService` → `DeviationAlertEngine` → `to_alert_message()`
- **Downstream:** `render_email` / `render_telegram` / `render_sms` / Premium-SMS; die Mail-Validatoren (`briefing_mail_validator.py`) prüfen die Trip-Briefing-Mail, **nicht** die Alarm-Mail

## Risks & Considerations

- **R1 — Nachbarschaft in Bewegung.** `render.py` wird von **#1948 S6** (Stand-Zeile in
  Telegram, Commit `b9f4c1d1`, noch nicht auf `main`) angefasst. Vor dem Schreiben
  rebasen und mit Session `gregor-zwanzig-79` abstimmen. **#2018** (Session
  `intake-2018`) sitzt auf dem Cooldown-/Dedupe-Pfad — Befund **B2** gehört dorthin,
  nicht hierher.
- **R2 — Abgrenzung.** B2 (Wiederholung, Vergleichsbasis) ist ein anderer Fehler als
  B1/B3/B4. Wird er hier mitgefixt, kollidiert das mit #2018 und #1987. Der Zuschnitt
  dieses Tickets muss das ausdrücklich als Nicht-Ziel führen.
- **R3 — Ein Vergangenheitsfilter kann Alarme verschlucken.** „Ereignis liegt in der
  Vergangenheit" heißt nicht immer „irrelevant": Ein Beginn um 15:00 mit Spitze um
  19:00, gemeldet um 16:00, ist weiterhin wertvoll. Der Filter darf am **Ende** des
  Ereignisses ansetzen, nicht am Beginn — sonst entsteht die Umkehrung der Lehre
  „Fix wirkungslos, weil ein späteres Tor ihn verwirft": ein Tor, das zu viel wegwirft.
- **R4 — Tagesbezug ohne Wirkort-Test ist wertlos.** Der Tagesbezug muss an der
  Stelle geprüft werden, an der er **wirkt** (der echte Versandpfad), nicht nur dort,
  wo der Code steht — genau die Falle, die #2009 im Fix-Loop nachbessern musste
  (`e2c4a50f`).
- **R5 — Beobachtbarkeit.** Die Briefing-Unterdrückung des Nowcasts hinterlässt keine
  Spur im `alert_log`. Ohne sie ist Beanstandung 4 auch künftig nicht nachweisbar.
- **R6 — Die Abweichungsalarm-Mail hat keinen Inhalts-Validator.**
  `radar_alert_mail_validator.py:105` macht bei allem außer `X-GZ-Mail-Type: radar-alert`
  ein No-Op; `briefing_mail_validator.py:574` überspringt `deviation-alert` ausdrücklich.
  Das Renderer-Gate (`renderer_mail_gate.py:47`) bewacht zwar `renderers/alert/*.py`,
  der geforderte Nachweis lässt sich aber mit einer **Radar**-Alarm-Mail erbringen,
  während die Änderung die **Abweichungs**-Alarm-Mail trifft. Genau die Mail aus diesem
  Ticket ist die eine, die kein Validator prüft. → Gate-Befund für #1197.

## Analysis

### Type

**Bug.** Kein Rechen- und kein Zeitzonenfehler, sondern ein Darstellungsfehler mit
einer gemeinsamen Wurzel.

### Root Cause (eine Ursache, drei Symptome)

> **Die Projektionsschicht wirft den Kalendertag weg, und der Renderer formuliert jede
> Zeitangabe so, als läge sie in der Zukunft — geprüft wird das nirgends.**

`_peak_occurred_at()` und die Onset-Werte tragen ein vollständiges `datetime`
(`weather_change_detection.py:301`). Erst `_fmt_occurred_at()`/`_fmt_onset_at()`
(`project.py:67,91`) reduzieren es auf `HH:MM`. Ab da ist nicht mehr entscheidbar, ob
der Zeitpunkt heute, morgen oder — wie hier — schon vorbei ist. Der Renderer setzt die
Zahlen anschließend ohne Vorbehalt in eine Zukunftsform („Beginn verschiebt sich auf
15:00"), obwohl es zum Versandzeitpunkt 15:30 war. Daraus folgen alle drei Symptome:
die scheinbar widersprüchlichen Zeiten (**B3**), der fehlende Tagesbezug (**B4**) und
die als Vorhersage gelesene Rückschau (**B1**).

### Warum die Meldung nicht früher kommen konnte

Untersucht und **ausgeschlossen**: Die Abweichungsprüfung läuft alle 15 Minuten
(`internal/scheduler/scheduler.go:192,369-373`), holt die Vorhersage bei **jedem** Lauf
frisch (`trip_alert.py:1537-1564`) und hat **keinen** Ergebnis-Cache — der einzige
Cache im Provider ist die 7-Tage-Modellverfügbarkeit (`providers/openmeteo.py:238`),
nicht die Werte. Zwischen Briefing (05:02 UTC) und Alarm (13:30 UTC) lagen ~34 Läufe.
Die Erkennungslatenz ist damit auf höchstens 15 Minuten gedeckelt.

**Schlussfolgerung: Open-Meteo hat den Regenbeginn nachträglich auf einen bereits
verstrichenen Zeitpunkt vorverlegt.** Der Alarm um 15:30 war so früh wie technisch
möglich. Ein früheres Warnen ist nicht die Lösung — die Meldung muss lediglich sagen,
dass das Ereignis bereits läuft, statt es als bevorstehend zu formulieren.

### Falle: der Tagesbezug aus #2009 verträgt keine Vergangenheit

`day_offset()` (`src/utils/timezone.py`, aus #2009) liefert auch **negative** Werte.
Die Anzeige daneben prüft aber nur auf Wahrheitswert:

```
render.py:310:  return f"morgen {e.onset_time}" if e.onset_day_offset else e.onset_time
```

Im Nowcast-Pfad folgenlos (dort ist der Beginn immer in der Zukunft, Vorwärtsfenster
`radar_service.py:599-602`). Beim Abweichungsalarm sind vergangene Zeitpunkte der
Normalfall — unverändert übernommen würde aus „gestern 15:00" ein **„morgen 15:00"**.
Der Baustein wird wiederverwendet, die Anzeige muss auf den exakten Tagesversatz
gehärtet werden.

### Technischer Ansatz

1. `to_alert_message()` nimmt zusätzlich `now_utc` entgegen. Beide Aufrufer berechnen
   es ohnehin schon bzw. können es trivial reichen:
   `notification_service.py:662` (`datetime.now(timezone.utc)`) und
   `validator_render_service.py:144`.
2. Die Projektion berechnet je Zeitangabe den Tagesversatz über `day_offset()` und
   legt ihn — zusammen mit der Information „liegt bereits zurück" — aufs Modell
   (`AlertEvent`, `OnsetShiftEvent`). **Rechnen in der Projektion, Worte im Renderer**
   — dieselbe Arbeitsteilung wie in #2009 (`radar_alert_service.py:71`).
3. Der Renderer benennt, welche Größe eine Zeile meint, und stellt jeder Uhrzeit den
   Tagesbezug voran. Für **alle vier Kanäle** — E-Mail, Telegram, SMS, Premium-SMS.
4. `_onset_time_label()` wird auf den exakten Tagesversatz gehärtet.

**Bewusst NICHT gewählt:** ein Filter, der vergangene Ereignisse unterdrückt (R3). Er
hätte die beanstandete Mail gar nicht verhindert — der Regen lief um 18:15 noch, das
Etappenfenster reichte bis 20:00. Und er würde weiterhin wertvolle Meldungen
verschlucken („es regnet seit einer Stunde, 29 mm bis heute Abend"). Der Fehler ist die
Formulierung, nicht die Zustellung.

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/output/renderers/alert/model.py` | MODIFY | Tagesversatz + Vergangenheits-Merker an `AlertEvent`/`OnsetShiftEvent` |
| `src/output/renderers/alert/project.py` | MODIFY | `now_utc` entgegennehmen, `day_offset()` je Zeitangabe, Felder füllen |
| `src/output/renderers/alert/render.py` | MODIFY | Zeilenbezeichnung + Tagesbezug in allen vier Kanälen; `_onset_time_label` härten |
| `src/services/notification_service.py` | MODIFY | `now_utc` durchreichen (≈3 Zeilen) |
| `src/services/validator_render_service.py` | MODIFY | dito (≈3 Zeilen) |
| `tests/tdd/test_alert_zeitangaben_2020.py` | CREATE | RED-Nachweis: Vergangenheit, Tagesgrenze, kombinierter Fall, alle vier Kanäle |

### Scope Assessment

- Dateien: **5 MODIFY + 1 CREATE**
- Geschätzt: **+80/-25** Produktivcode, **+150** Test → **LoC-Limit 250 wird gerissen**,
  Anhebung auf 500 einplanen
- Risiko: **MEDIUM–HIGH** — kritischer Pfad, vier Kanäle, `render.py` wird parallel
  von #1948 S6 angefasst

### Open Questions

- [ ] **Beanstandung 4 braucht eine Produktentscheidung.** Der Nowcast wurde bewusst
      unterdrückt, weil das Briefing den Regen schon angekündigt hatte
      (`trip_alert.py:1330`). Nur: angekündigt waren **7,4 mm**, gekommen sind
      **29,4 mm** — „redundant" trifft es nicht. Empfehlung in der Spec vorlegen,
      Entscheidung beim PO.

