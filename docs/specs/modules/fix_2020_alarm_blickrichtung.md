---
entity_id: fix_2020_alarm_blickrichtung
type: module
created: 2026-08-21
updated: 2026-08-21
status: approved
version: "1.0"
tags: [alert, deviation-alert, blickrichtung, restmenge, zeitangaben, issue-2020, scheibe-2]
---

# Abweichungsalarm: Die Meldung schaut nach vorn, nicht zurück (Scheibe 2, Umschnitt)

## Approval

- [x] Approved — PO-Freigabe 2026-08-21 („go")

## Purpose

Der Abweichungsalarm vom 2026-08-20, 18:15 Ortszeit, meldete „Niederschlag 7,4 → 29,4 mm,
Beginn 19:00 → 15:00" — zu diesem Zeitpunkt war der überwiegende Teil der Menge bereits
gefallen. Die Meldung bestand ausschließlich aus Vergangenheit. Der PO hat die dafür
vorbereitete Wortlaut-Spec (`fix_2020_alarm_zeitangaben.md`, 7 ACs) zurückgewiesen: „ich
verstehe immer noch nicht, was mir das sagen soll — und was hilft es mir, wenn ich um
18:15 diese Information bekomme?" **Diese Spec löst jene Spec ab.**

**Widerrufen:** Die dortige Festlegung „der Fehler ist die Formulierung, nicht die
Zustellung" (Nicht-Ziel „Vergangenheitsfilter") gilt **nicht mehr in dieser Form**. Ein
Vergangenheitsfilter bleibt zwar weiterhin ausgeschlossen — aber nicht mehr, weil die
Formulierung angeblich der einzige Fehler wäre, sondern weil der PO ausdrücklich
entschieden hat, dass eine deutlich höhere Regenmenge als angekündigt die Lage **auch
rückblickend** ändert (nasse Ausrüstung, Wegzustand, Bäche) und deshalb **immer**
zugestellt werden soll (siehe „Nicht-Ziele").

Diese Spec macht den Abweichungsalarm **vorwärtsgewandt**: seine Hauptaussage ist die
Regenmenge, die ab dem Versandzeitpunkt noch kommt, und bis wann sie fällt. Das bereits
Gefallene bleibt als Einordnung erhalten, ist aber nicht mehr die Botschaft. Zusätzlich
(unverändert aus Scheibe 2 alt übernommen, sonst stünde wieder eine nackte Uhrzeit da):
jede Zeitangabe benennt ihre Größe, trägt einen Tagesbezug, wenn der Tag vom Versandtag
abweicht, und wird als vergangen ausgewiesen, wenn sie vergangen ist. **Scheibe 1**
(Auslösung/Mengen-Überholung) ist bereits in Produktion (`b423c913`). Diese Scheibe ändert
**keine** Auslösung, nur Inhalt und Blickrichtung der bereits ausgelösten Meldung.

**🔴 Korrektur 2026-08-21 (nach erster Fassung dieser Spec):** Restmenge und Ende beziehen
sich zwingend auf das **Tagesfenster des Trips** (konfigurierbar, Default 4–19 Uhr,
`day_window.py`), nicht auf den Kalendertag — aus demselben Grund, aus dem das Briefing es
schon so macht (siehe „Implementation Details"). Ein realer Regenfall außerhalb dieses
Fensters bleibt für den Alarm unsichtbar, damit Alarm und Briefing niemals mit
verschiedenen Fenstern rechnen. Die ursprüngliche erste Fassung dieser Spec hatte fälschlich
mit einer Kalendertag-Reihe gerechnet (inkl. einer 22-Uhr-Regenstunde, die je nach
Trip-Konfiguration außerhalb des Fensters liegen kann) — die Acceptance Criteria unten sind
entsprechend korrigiert und verwenden ausschließlich konstruierte Beispielreihen mit
ausdrücklich genanntem Tagesfenster, nicht die tatsächliche, unbekannte Konfiguration des
PO-Trips.

## Source

- **File:** `src/output/renderers/alert/project.py`, `src/output/renderers/alert/render.py`,
  `src/output/renderers/alert/model.py`, `src/services/weather_change_detection.py`,
  `src/app/models.py`
- **Identifier:** `to_alert_message()`, `_datablock_single()`, `_onset_shift_line()`,
  `_onset_time_label()`, `_sms_token()`, `_sms_onset_shift_token()`,
  `WeatherChangeDetectionService.detect_changes()`, `_peak_occurred_at()`, `AlertEvent`,
  `OnsetShiftEvent`, `WeatherChange`

## Estimated Scope

- **LoC:** ~160 Produktivcode (+180/-30), ~250 Test (das Doppelte der abgelösten Spec —
  zusätzlich zum Tagesbezug-Zuschnitt kommt die Restmengen-/Ende-Berechnung samt
  Vier-Kanal-Formatierung und die Fenstergrenzen-Absicherung)
- **Files:** 7 MODIFY, 1-2 CREATE
- **Effort:** high

### Affected Files

| Datei | Change Type | Description |
|---|---|---|
| `src/app/models.py` | MODIFY | additive Felder `remaining_mm: float \| None`, `precip_ends_at: datetime \| None` an `WeatherChange` (Muster `occurred_at`, Issue #1386) |
| `src/services/weather_change_detection.py` | MODIFY | neue Hilfsfunktion `_precip_remaining(new_data, now_utc)` (Vorbild `_peak_occurred_at()`, `:301-373`, **dasselbe** Segmentfenster wie dort — `seg_start`/`seg_end`), Aufruf am bestehenden Konstruktionsort von `WeatherChange` für `metric == "precip_sum_mm"` (`:783`) |
| `src/output/renderers/alert/model.py` | MODIFY | additive Felder an `AlertEvent` (`occurred_day_offset`, `occurred_is_past`, `remaining_mm`, `remaining_until_time`, `remaining_until_day_offset`) und `OnsetShiftEvent` (`to_day_offset`, `to_is_past`), alle mit Default, am Ende des Feldblocks |
| `src/output/renderers/alert/project.py` | MODIFY | Projektion rechnet Tagesversatz/Vergangenheit je Zeitangabe (`day_offset(now_utc, ...)`) und formatiert Restmenge + Ende aus den neuen `WeatherChange`-Feldern; `_fmt_occurred_at`/`_fmt_onset_at` bleiben in ihrer Form |
| `src/output/renderers/alert/render.py` | MODIFY | Langform (E-Mail/Telegram): Kopf „mehr Regen als angekündigt" + Restmengen-/Ende-Zeilen für Niederschlags-Summen-Ereignisse, `gestern HH:MM`/`vor N Tagen HH:MM`/`morgen HH:MM`/`seit HH:MM` für alle anderen Zeitangaben; Kurzform (SMS/Premium-SMS): Restmengen-Token `Rest{mm}@{HH}`, Wochentagskürzel für Tagesbezug (`R7@Do15`); Bedeutungswort „stärkste Stunde" für Nicht-Niederschlags-Δ-Ereignisse; `_onset_time_label` auf exakten Versatz gehärtet. **NICHT** anfassen: `_render_sms_onset`, `to_multi_location_onset_alert_message`, `_sms_onset_time` (Fläche der #2046-Session, siehe „Zur Entscheidung mit der Freigabe") |
| `src/services/notification_service.py` | MODIFY | reicht die bereits vorhandene `now_utc` (`:662`) durch |
| `src/services/validator_render_service.py` | MODIFY | zweiter Aufrufer, reicht dieselbe Referenzzeit durch |
| `tests/tdd/test_alert_restmenge_und_ende.py` (oder analog benannt) | CREATE | RED-Nachweis: Restmenge/Ende innerhalb des Tagesfensters, Fenstergrenzen-Absicherung, Gegenfall früh am Tag, ehrliches „nichts mehr", Tagesbezug, alle vier Kanäle |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/segment_weather.py` → `_aggregate_for_segment()` (`:237-320`) | Invariante-Beleg | Beleg dafür, dass Alarm-Pfad und Briefing-Pfad **dasselbe** Segmentfenster verwenden (Kommentar `:292-308`: „sonst nennt der Alarm eine andere Stunde als das Briefing") — Restmenge/Ende dürfen dieses Fenster nicht umgehen |
| `src/app/day_window.py` → `resolve_configured_window()` (`:24-54`) | reuse | EINE Quelle für die effektiven Fenster-Grenzen (Default 4–19, `start > end` gültig über Mitternacht, ADR-0035) |
| `src/app/day_window.py` → `window_end_utc_exclusive()` (`:57-84`) | Muster (kein Code-Reuse, andere Aufrufsituation) | Beleg für die INKLUSIVE Bedeutung von `end_hour`: die Endstunde zählt VOLL mit, das Fenster endet damit technisch erst um `(end_hour+1):00` Ortszeit — bindend für die Berechnung des „Ende"-Zeitpunkts dieser Scheibe |
| `src/services/radar_service.py` → `window_precip_mm`-Berechnung (`:745-754`) | Muster (kein Code-Reuse) | Vorwärtsfenster-Summe Rate×Dauer über Frame-Paare — dieselbe Idee, andere Datenform (`RadarFrame` vs. `ForecastDataPoint` mit fertigem `precip_1h_mm`-Stundenwert, daher keine Interpolation über Frame-Nachbarn nötig) |
| `src/services/weather_metrics.py` → `WeatherMetricsService._onset_of()` (`:629-658`) | Muster (kein Code-Reuse, andere Klasse/anderer Datenfluss) | `min(treffer)` für den Beginn, gefiltert auf das Tagesfenster (`hour_in_window`) — das Ende dieser Scheibe ist das symmetrische `max(treffer)`, ebenfalls fenstergebunden |
| `src/utils/timezone.py` → `day_offset()` | reuse | Kalendertage zwischen jetzt und Zielzeitpunkt in Ortszeit (aus #2009) |
| `src/utils/timezone.py` → `format_reference_at()` | reuse | liefert bereits die Hausnotation `gestern HH:MM Uhr`/`vor N Tagen HH:MM Uhr` für die Fußzeile — dieselbe Wortwahl gilt jetzt auch für die Ereignis-Zeitangaben selbst |
| `src/utils/timezone.py` → `local_fmt()` | reuse | `HH:MM` in Ortszeit — unverändert |
| `src/output/renderers/alert/official_alerts.py` → `_de_weekday_short()` (`:802`) | reuse | liefert das Wochentagskürzel für die Kurzform — **nicht** nachbauen |
| `src/services/notification_service.py:662` | caller | berechnet `datetime.now(timezone.utc)` bereits, reicht es künftig durch |
| `src/services/validator_render_service.py:144` | caller | zweiter Aufrufer der Projektion, reicht dieselbe Referenzzeit durch |

## Implementation Details

**Arbeitsteilung wie in #2009: Der Erkennungsdienst rechnet aus der Rohreihe, die
Projektion formatiert in Ortszeit, der Renderer setzt die Worte.**

```
weather_change_detection.py:783   WeatherChange(..., occurred_at=_peak_occurred_at(...),
                                                  remaining_mm=_precip_remaining(new_data, now_utc)[0],
                                                  precip_ends_at=_precip_remaining(new_data, now_utc)[1])
        │   NUR wenn metric == "precip_sum_mm" (Katalog-Summary-Field, dp_field
        │   "precip_1h_mm", Issue-Beleg: metric_catalog.py:378-385) — andere
        │   Metriken lassen beide Felder auf None (Δ-Pfad bleibt unveraendert).
        ▼
to_alert_message(..., now_utc=now_utc)          project.py
        │   je Zeitangabe: day_offset()/is_past wie in Scheibe 2 alt
        │   zusaetzlich: remaining_mm, remaining_until (HH:MM Ortszeit oder
        │   None = "kein weiterer Regen"), bereits_gefallen = new_value - remaining_mm
        ▼
AlertEvent.remaining_mm, .remaining_until_time, .remaining_until_day_offset  (NEU)
AlertEvent.occurred_day_offset, .occurred_is_past                            (NEU)
OnsetShiftEvent.to_day_offset, .to_is_past                                   (NEU)
        │
        ▼
render.py    setzt die Worte — E-Mail (HTML + Klartext), Telegram, SMS, Premium-SMS
```

### 🔴 Bindende Invariante: Restmenge und Ende rechnen im TAGESFENSTER des Trips, nicht über den Kalendertag

`_aggregate_for_segment()` (`segment_weather.py:237-320`) schneidet die Stundenreihe für
JEDEN Alarm- und Briefing-Aufruf auf dasselbe Segmentfenster (`segment.start_time`/
`.end_time`), dessen Grenzen aus `resolve_configured_window()` (`day_window.py:24-54`,
ADR-0035, Default **4–19 Uhr**, konfigurierbar, `start > end` gültig über Mitternacht)
stammen. Der Code-Kommentar dort begründet es ausdrücklich (`:292-308`): sonst nennt der
Alarm eine andere Stunde als das Briefing, und beide Vergleichsseiten könnten mit
verschiedenen Fenstern rechnen. `_peak_occurred_at()` (die bestehende „stärkste
Stunde"-Berechnung, `weather_change_detection.py:301-373`) folgt genau diesem Fenster
(`seg_start <= _as_utc(p.ts) <= seg_end`, `:336-343`) — **`_precip_remaining()` verwendet
dasselbe Fenster**, nicht ein zweites, separat aufgelöstes.

Wichtig für die Grenze selbst: `end_hour` zählt gemäß `window_end_utc_exclusive()`
(`day_window.py:57-84`, PO-Entscheidung 2026-08-17, ADR-0035) **vollständig mit** — das
Fenster endet technisch erst um `(end_hour+1):00` Ortszeit. Bei einem Tagesfenster 4–19
Uhr endet das Fenster also effektiv um **20:00 Ortszeit**, nicht um 19:00. Diese Scheibe
rechnet grundsätzlich relativ zum konfigurierten Fenster; feste Uhrzeiten in den ACs unten
sind Beispielwerte zu einem jeweils **ausdrücklich genannten** Fenster, keine Annahme über
die tatsächliche Konfiguration eines bestimmten Trips (die ist nicht gesichert und kann
sich jederzeit ändern).

**`_precip_remaining(new_data, now_utc) -> tuple[float, datetime | None]`**
(neu, `weather_change_detection.py`, Geschwisterfunktion von `_peak_occurred_at`, gleicher
Zugriff auf `new_data.timeseries.data` und dasselbe `seg_start`/`seg_end`-Fenster):

1. **Restmenge** = Summe aller `precip_1h_mm`-Stundenwerte **innerhalb des Segmentfensters**,
   deren Stunde nicht bereits vollständig vergangen ist. Regel für die angebrochene Stunde:
   *die Stunde, in der `now_utc` liegt, zählt VOLL zur Restmenge* (nicht anteilig).
   Begründung: `precip_1h_mm` ist ein Stundenwert ohne untertägige Rate — eine anteilige
   Aufteilung würde eine Genauigkeit vortäuschen, die das Modell nicht hergibt. Die volle
   Zählung ist die **konservative** Richtung (nicht zu wenig warnen).
2. **Ende** = letzte Stunde **im gesamten Segmentfenster** (nicht nur der laufenden
   Regenphase) mit `precip_1h_mm >= 0,1 mm` (Mess-Schwelle, keine Alarm-Schwelle — es geht
   um „hat es noch geregnet", nicht „war es Alarm-relevant"). Begründung für „gesamtes
   Fenster" statt „laufende Phase": zwei getrennte Regenphasen im selben Fenster (Pause
   dazwischen) sind ein realer Fall (siehe AC-5). Eine Meldung, die beim ersten Regenende
   „nichts mehr" sagt, wäre falsch, sobald die zweite Phase im Fenster liegt.
3. Regen **außerhalb** des Segmentfensters (vor Fensterbeginn oder nach dem effektiven
   Fensterende) fließt **nicht** in Restmenge oder Ende ein (AC-6) — exakt das, was das
   Briefing für denselben Zeitraum ebenfalls nicht sieht.
4. Kein Treffer im restlichen Fenster → `remaining_mm == 0.0` und `precip_ends_at is None`
   → „kein weiterer Regen [bis Tagesende]" (AC-3).

**Projektion (`project.py`):** `bereits_gefallen = ch.new_value - remaining_mm` — bewusst
**keine** zweite unabhängige Summierung der bereits vergangenen Stunden, um ein
Auseinanderdriften zweier separat berechneter Teilsummen auszuschließen (`new_value` ist
bereits die Fenster-Gesamtsumme aus dem frischen Forecast, da `SegmentWeatherSummary`
ebenfalls aus der fenstergefilterten Reihe aggregiert wird, `_aggregate_for_segment()`).

**Wortlaut Langform (E-Mail + Telegram), Beispiel mit ausdrücklich genanntem Tagesfenster
4–19 Uhr (effektives Fensterende 20:00 Ortszeit), konstruierte Stundenreihe angelehnt an
den realen Fall (13:00=8 · 15:00=10 · 16:00=3 · 17:00=1 mm, angekündigt waren 5 mm),
Referenzzeit 14:30 Ortszeit — siehe AC-1 für die vollständige Herleitung:**

```
🏁 Ziel · mehr Regen als angekündigt
Bis jetzt: ~8 mm gefallen (angekündigt waren 5)
Ab jetzt: noch ~14 mm, letzter Regen gegen 17:00
```

Bei `remaining_mm == 0.0` (dieselbe Reihe, Referenzzeit NACH der letzten Regenstunde, aber
VOR dem effektiven Fensterende — der beanstandete Originalfall, siehe AC-3):

```
🏁 Ziel · mehr Regen als angekündigt
Bis jetzt: ~22 mm gefallen (angekündigt waren 5)
Ab jetzt: kein weiterer Regen bis Tagesende (Fensterende 20:00 Ortszeit)
```

**Diese Restmengen-/Ende-Zeilen ersetzen den bisherigen Kopf „stärkste Stunde HH:MM" NUR
für Niederschlags-Summen-Ereignisse** (`e.remaining_mm is not None`). Für alle anderen
Δ-Metriken (Wind, Temperatur, …) bleibt der Kopf aus Teil 3 („stärkste Stunde") die
richtige Formulierung — eine „Restmenge" ergibt für Wind/Temperatur keinen Sinn.

**Wortlaut Kurzform (SMS + Premium-SMS):** neuer Kompakt-Token neben dem bestehenden
Δ-Token aus `_sms_token()` (`render.py:957-995`, unverändert `{code}{von}->{bis}@{HH}`):
`Rest{round(remaining_mm)}@{Tagesbezug}{HH}` — Tagesbezug nach derselben
Wochentagskürzel-Regel wie Teil 3 (leer am Versandtag). Beispiel (dieselbe Reihe wie oben,
Referenzzeit 14:30): `Ziel: R5->22@15 Rest14@17`. Bei „kein weiterer Regen": `Rest0` ohne
Zeit-Suffix.

### Teil 3 — Zeitangaben benennen ihre Größe und ihren Tagesbezug (aus Scheibe 2 alt übernommen)

**Wortlaut — Langform, Bestandsnotation aus `format_reference_at`:**

| Lage | Zeile „Wo & wann" (Nicht-Niederschlags-Metrik) |
|---|---|
| Zeitpunkt liegt heute noch bevor | `🏁 Ziel · stärkste Stunde 17:00` |
| Zeitpunkt ist heute schon vorbei | `🏁 Ziel · stärkste Stunde war 17:00` |
| Zeitpunkt liegt einen Tag zurück | `🏁 Ziel · stärkste Stunde war gestern 17:00` |
| Zeitpunkt liegt ≥2 Tage zurück | `🏁 Ziel · stärkste Stunde war vor 2 Tagen 17:00` |
| Zeitpunkt liegt einen Tag voraus | `🏁 Ziel · stärkste Stunde morgen 17:00` |

Das ist **keine Neuerfindung**: `format_reference_at` (`src/utils/timezone.py:154-169`)
erzeugt `gestern HH:MM Uhr`/`vor N Tagen HH:MM Uhr` bereits heute für die Fußzeile
(„Stand: heute 18:15 · verglichen mit gestern 18:03 Uhr", `render.py:948-951`). Diese
Scheibe wendet dieselbe Hausnotation auf die Ereignis-Zeitangaben selbst an.

**Wortlaut Kurzform Tagesbezug (SMS + Premium-SMS), Bestandsnotation der amtlichen
Warnung:** Das Wochentagskürzel klebt vor die Stunde, `_de_weekday_short()`
(`official_alerts.py:802`, Muster `Do12-22`/`Fr22-Sa03`). Aus dem Δ-Token `R7@15`
(vereinfachtes Beispiel) wird bei Versatz `-1` an einem Donnerstag `R7@Do15`. Am
**heutigen** Tag entfällt das Kürzel ersatzlos (dieselbe Regel wie #1948 S5,
`official_alerts.py:1929-1943`).

**Verworfen: ein Zahlensuffix (`17:00-1`).** Drei belegte Gründe:
1. `-` ist in der Kurzform bereits dreifach belegt — Wert gefallen (`-R7`), Bereichstrenner
   (`12-22`), km-Spanne (`km8-8`, `render.py:1006`).
2. Die Fensterform der amtlichen Warnung ist formgleich: `_tag_hour()`
   (`official_alerts.py:1896-1902`) setzt Minuten, sobald sie nicht auf `:00` liegen — ein
   Gültigkeitsfenster lautet dann `15:20-17`, neben `17:00-1` nicht mehr per Form
   unterscheidbar.
3. `_sms_onset_time()` hängt das Vorzeichen fest an (`f"{base}+{day_offset}"`,
   `render.py:550`) — mit `day_offset = -1` entstünde `17:00+-1`. Diese Funktion bleibt in
   dieser Scheibe unangetastet.

**Ein gemeinsamer Baustein für das Tageswort der Langform — nicht zwei.** Heute löst
`_onset_time_label()` (`render.py:367-374`) den Tagesversatz nur über **Wahrheitswert**
auf: `f"morgen {e.onset_time}" if e.onset_day_offset else e.onset_time` — jeder Versatz
ungleich null wird zu „morgen", auch `-1`. Im Nowcast-Pfad unerreichbar (Vorwärtsfenster),
im Abweichungsalarm der Normalfall. Deshalb: eine typunabhängige Hilfsfunktion
`(hhmm: str, day_offset: int, is_past: bool) -> str` löst den **exakten** Versatz auf
(`-1 → gestern`, `-N → vor N Tagen`, `0 & vergangen → seit … (kein Tageswort)`,
`0 & bevorstehend → kein Wort`, `1 → morgen`). `_onset_time_label()` wird auf sie
umgestellt.

**Nachbarschaft in Bewegung:** `render.py` wird parallel von **#2036**
(`fix-2036-alarm-kilometer`, additives `km_measured: bool = False`, `km{A}-{B}` →
`km {A}-{B}`) angefasst. Vor dem Schreiben rebasen.

## Expected Behavior

- **Input:** `changes` (WeatherChange-Liste, jetzt additiv mit `remaining_mm`/
  `precip_ends_at` bei Niederschlags-Summen-Metriken, beide ausschließlich aus der
  Stundenreihe **innerhalb des Segment-Tagesfensters** berechnet), `tz` (Ortszeit des
  Segment-Startpunkts), `now_utc` (Referenzzeit des Versands)
- **Output:** Alarm-Nachricht in vier Kanälen. Niederschlags-Summen-Ereignisse nennen
  primär die Restmenge ab Versand und deren Ende — beide fenstertreu, nie über das
  konfigurierte Tagesfenster hinaus; alle Ereignisse benennen ihre Größe, tragen ihren
  Tagesbezug und weisen ihre Vergangenheit aus.
- **Side effects:** Keine.

## Acceptance Criteria

- **AC-1:** Given ein Tagesfenster 4–19 Uhr (effektives Fensterende 20:00 Ortszeit, `end_hour`
  zählt gemäß `window_end_utc_exclusive()` voll mit) und eine Stundenreihe innerhalb dieses
  Fensters (13:00=8 mm · 15:00=10 mm · 16:00=3 mm · 17:00=1 mm, angekündigt waren 5 mm) /
  When die Nachricht bei Referenzzeit 14:30 Ortszeit gerendert wird (nach der 13:00-Stunde,
  vor der 15:00-Stunde) / Then lautet die Hauptaussage vorwärtsgewandt: Kopf
  `🏁 Ziel · mehr Regen als angekündigt`, `Bis jetzt: ~8 mm gefallen (angekündigt waren 5)`,
  `Ab jetzt: noch ~14 mm, letzter Regen gegen 17:00`.
  - Test: Rendering mit dieser konstruierten Stundenreihe und Referenzzeit 14:30 prüft
    exakt diese drei Zeilen im Klartext (E-Mail/Telegram). Die Reihe bewusst OHNE eine
    Stunde außerhalb des Fensters (keine Kalendertag-Annahme).

- **AC-2:** Given dieselbe Stundenreihe und dasselbe Tagesfenster wie AC-1 / When die
  Nachricht mit einer frühen Referenzzeit 10:00 Ortszeit gerendert wird, bevor irgendeine
  Stunde der Reihe begonnen hat / Then ist die Restmenge nahe der Fenster-Gesamtmenge
  (`Ab jetzt: noch ~22 mm, letzter Regen gegen 17:00`) und
  das bereits Gefallene nahe null (`Bis jetzt: ~0 mm gefallen (angekündigt waren 5)`) — die
  Endzeit (17:00) bleibt gegenüber AC-1 unverändert, weil sie eine Eigenschaft der Reihe
  ist, nicht der Referenzzeit.
  - Test: Dieselbe Stundenreihe, Referenzzeit 10:00 statt 14:30; Restmenge und
    Bereits-Gefallen-Wert verhalten sich gegenläufig zu AC-1 (Restmenge deutlich höher,
    Bereits-Gefallen deutlich niedriger), keine Formel darf einen negativen oder über der
    Fenster-Gesamtmenge liegenden Wert liefern.

- **AC-3:** Given dieselbe Stundenreihe und dasselbe Tagesfenster wie AC-1 (letzte
  Regenstunde 17:00) / When die Nachricht mit Referenzzeit 18:15 Ortszeit gerendert wird —
  NACH der letzten Regenstunde, aber VOR dem effektiven Fensterende 20:00 (der beanstandete
  Originalfall, ehemals „Beginn 19:00 → 15:00") / Then meldet sie ehrlich
  `Ab jetzt: kein weiterer Regen bis Tagesende (Fensterende 20:00 Ortszeit)` statt eine
  Restmenge zu erfinden oder eine bereits verstrichene Uhrzeit als bevorstehend zu
  formulieren — UND wird trotzdem zugestellt (PO-Entscheid, keine Unterdrückung), weil
  bereits mehr gefallen ist als angekündigt.
  - Test: Rendering mit Referenzzeit 18:15 gegen dieselbe Reihe liefert eine nicht-leere
    Nachricht mit dem exakten Satz (kein `None`/leerer String) UND `Bis jetzt: ~22 mm
    gefallen (angekündigt waren 5)`.

- **AC-4:** Given eine Referenzzeit, die mitten in einer angebrochenen Regenstunde
  innerhalb des Tagesfensters liegt (z. B. 14:20 Ortszeit bei einem Stundenwert von 2,0 mm
  um 14:00) / When die Restmenge berechnet wird / Then zählt diese angebrochene Stunde
  VOLL zur Restmenge (nicht anteilig nach verstrichenen Minuten) — dieselbe Stundenreihe
  ergibt bei Referenzzeit 14:00 exakt denselben Restmengen-Wert wie bei 14:20.
  - Test: Restmengen-Berechnung mit Referenzzeit 14:00 und 14:20 gegen dieselbe
    Stundenreihe vergleichen — beide Werte müssen identisch sein (Grenzstabilität der
    Regel); eine Implementierung, die anteilig kürzt, muss diesen Test brechen.

- **AC-5:** Given ein Tagesfenster 4–19 Uhr und eine Stundenreihe mit zwei getrennten
  Regenphasen, die BEIDE innerhalb dieses Fensters liegen (6:00=1 mm · 7:00=1 mm, Pause,
  dann 16:00=1 mm · 17:00=1 mm) / When das Ereignis-Ende bei Referenzzeit 10:00 Ortszeit
  (zwischen den beiden Phasen) berechnet wird / Then ist das Ende die letzte Regenstunde
  des GESAMTEN Fensters (17:00), NICHT das Ende der ersten Phase (7:00).
  - Test: Rendering bei Referenzzeit 10:00 prüft, dass `letzter Regen gegen 17:00` steht —
    eine Implementierung, die nur die laufende bzw. bereits abgeschlossene erste Phase
    betrachtet, würde `7:00` oder gar keine Endzeit liefern und muss diesen Test brechen.
    Der reale Fall vom 2026-08-20 (zwei Phasen mit Pause) bleibt als Beleg im Fließtext,
    ist aber NICHT der Testfall — seine tatsächliche Fensterkonfiguration ist nicht
    gesichert.

- **AC-6:** Given dieselbe Stundenreihe wie AC-1, ergänzt um eine zusätzliche Regenstunde
  AUSSERHALB des Tagesfensters 4–19 (z. B. 21:00=5 mm, außerhalb des effektiven
  Fensterendes 20:00) / When Restmenge und Ende bei Referenzzeit 10:00 berechnet werden /
  Then bleiben beide Werte GENAU wie in AC-2 (Restmenge ~22 mm, Ende 17:00) — die
  21:00-Stunde fließt nicht ein. Wird dieselbe erweiterte Reihe stattdessen mit einem
  WEITEREN Tagesfenster (z. B. 4–22, effektives Ende 23:00) gerendert, ändern sich beide
  Werte fenstertreu (Restmenge ~27 mm, Ende 21:00).
  - Test: Zwei Renderings derselben um 21:00=5 mm erweiterten Reihe — einmal mit Fenster
    4–19 (muss mit AC-2 identisch bleiben), einmal mit Fenster 4–22 (muss die 21:00-Stunde
    einschließen). Eine Implementierung, die das Fenster ignoriert oder global über die
    Reihe summiert, muss mindestens einen der beiden Fälle brechen.

- **AC-7:** Given denselben Abweichungsalarm mit Restmenge und Ende (Reihe/Fenster/
  Referenzzeit wie AC-1) / When er in alle vier Kanäle gerendert wird (E-Mail HTML,
  E-Mail Klartext, Telegram, SMS, Premium-SMS) / Then tragen E-Mail und Telegram die
  vollständigen Sätze aus AC-1, SMS und Premium-SMS tragen denselben Sachverhalt als
  Kompakt-Token (`Ziel: R5->22@15 Rest14@17`), und die 160-Zeichen-Grenze der
  Kurznachricht bleibt eingehalten.
  - Test: Rendering je Kanal prüfen (SMS und Premium-SMS über denselben
    `_render_sms_body`-Pfad, der laut Bestand denselben Text an beide liefert); für die
    Kurznachricht zusätzlich Zeichenlängenprüfung ≤160.

- **AC-8:** Given ein Abweichungsalarm, dessen Niederschlagsbeginn zum Versandzeitpunkt
  bereits verstrichen ist, aber am selben Kalendertag liegt (Beginn 15:00 Ortszeit,
  Versand 15:30 Ortszeit) / When die Alarm-Nachricht gerendert wird / Then weist die
  Beginn-Zeile den Zeitpunkt als vergangen aus (`19:00 → seit 15:00 (4 h früher)`) und
  formuliert ihn nicht als bevorstehend.
  - Test: Nachricht mit vergangener Onset-Zeit rendern und prüfen, dass der Klartext die
    Vergangenheitsform trägt; Gegenprobe mit künftiger Onset-Zeit, die sie nicht trägt.

- **AC-9:** Given ein Abweichungsalarm, dessen Zeitpunkt auf einem anderen Kalendertag
  als dem Versandtag liegt / When die Nachricht in E-Mail oder Telegram gerendert wird /
  Then nennt die Zeitangabe den Tag beim Namen, in der Hausnotation aus
  `format_reference_at` — `-1` ergibt `gestern 15:00`, `-2` ergibt `vor 2 Tagen 15:00`,
  `+1` ergibt `morgen 15:00`.
  - Test: Je ein Rendering mit Versatz `-1`, `-2` und `+1` gegen dieselbe Uhrzeit; der
    `-1`- und `-2`-Fall dürfen unter keinen Umständen „morgen" ergeben (Regression zur
    Wahrheitswert-Prüfung in `render.py:374`). Dieselbe Gegenprobe gilt für den
    Nowcast-Pfad, der auf denselben Baustein umgestellt wird.

- **AC-10:** Given denselben Fall wie AC-9, aber gerendert in SMS oder Premium-SMS /
  When die Kurznachricht gebaut wird / Then klebt das Wochentagskürzel vor die Stunde des
  Kurzform-Tokens — aus `R7@15` wird bei einem Donnerstag und Versatz `-1` `R7@Do15`;
  kein Kanal fällt auf ein Zahlensuffix zurück.
  - Test: Rendering mit Versatz `-1` an einem festgelegten Wochentag prüft exakt
    `R7@Do15` (bzw. das analoge Token für den tatsächlichen Renderer-Aufbau) im
    SMS-Text, nicht `R7@15-1` oder `R7@15+-1`.

- **AC-11:** Given ein Abweichungsalarm mit einer Wertänderung EINER Nicht-Niederschlags-
  Metrik (z. B. Windböe), deren Spitzenwert zu einer bestimmten Stunde auftritt / When die
  Nachricht gerendert wird / Then benennt die Zeile „Wo & wann" die Uhrzeit ausdrücklich
  als Zeitpunkt des stärksten Werts (`🏁 Ziel · stärkste Stunde 17:00`, bzw.
  `stärkste Stunde war 17:00` bei einem vergangenen Zeitpunkt) — für diese Metrikart bleibt
  die alte Kopfform bestehen, weil eine „Restmenge" für Wind/Temperatur keine sinnvolle
  Größe ist.
  - Test: Gerenderte Zeile einer Windböen-Änderung enthält die Kennzeichnung der Größe
    zusätzlich zum Ort und zur Uhrzeit; Gegenprobe, dass eine reine Beginn-Zeile
    (`-Beginn`) weiterhin ohne dieses Wort auskommt.

- **AC-12:** Given ein Abweichungsalarm, der gleichzeitig eine Wertänderung UND eine
  Beginn-Verschiebung trägt (der Fall aus #2020, bisher von keinem Test abgedeckt) / When
  die Nachricht gerendert wird / Then stehen beide Zeitangaben mit unterscheidbarer
  Bedeutung in derselben Nachricht, sodass eine Restmengen-/Spitzen-Aussage neben einem
  Beginn um 15:00 nicht als Widerspruch lesbar ist.
  - Test: Eine `AlertMessage` mit befülltem `events` UND `onset_shift_events` rendern und
    prüfen, dass beide Zeilen ihre Größe benennen.

- **AC-13:** Given ein Testlauf zu einem beliebigen Systemdatum / When die Nachricht mit
  einer explizit übergebenen Referenzzeit gerendert wird / Then hängt das Ergebnis
  ausschließlich von dieser Referenzzeit ab und nicht von der Systemuhr.
  - Test: Dasselbe Rendering zweimal mit unterschiedlicher Referenzzeit und identischen
    Wetterdaten ergibt unterschiedliche Tagesbezüge UND unterschiedliche Restmengen; kein
    Aufruf von `datetime.now()` im Renderpfad der Zeit-/Restmengen-Darstellung.
    Zusätzlich: `test_onset_shift_alert.py` und `test_alert_event_time_uses_local_timezone.py`
    (beide ohne `freeze_time`, feste Kalenderdaten) bleiben grün, weil sie die Referenzzeit
    künftig explizit setzen.

- **AC-14:** Given zwei Kurzform-Ausschnitte, die im selben Kanal nebeneinander
  vorkommen können — die Tagesbezug-Form dieses Alarms (`R7@Do15`) und die Fensterform
  der amtlichen Warnung (`Do12-22` bzw. `15:20-17` bei `_tag_hour`) / When ein
  Wächter-Test beide aus dem echten Renderer-Code zieht und in einer Zeile
  gegenüberstellt / Then macht eine spätere Änderung der Fensterform (z. B. Umstellung
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

- **Restmenge/Ende gelten nur für die Niederschlags-Summen-Metrik (`precip_sum_mm`).**
  Andere Δ-Metriken (Wind, Temperatur, Gewitter) behalten den „stärkste Stunde"-Kopf aus
  Teil 3 — eine Restmengen-Aussage ergibt für sie keinen Sinn. Eine künftige Metrik mit
  ähnlicher Vorwärts-Semantik (z. B. Schneefall-Summe) bräuchte ein eigenes Ticket.
- **Die angebrochene Stunde zählt komplett zur Restmenge** — eine bewusst vereinfachende,
  konservative Annahme (kein untertägiger Rate-Wert im Bestand). Bei einer Metrik mit
  tatsächlich stark ungleichmäßiger Verteilung innerhalb der Stunde kann die Restmenge
  geringfügig überschätzt werden.
- **🔴 Regen nach Fensterende (Nachtregen) erscheint weder in der Restmenge noch in der
  Endzeit.** Restmenge und Ende sind strikt auf das konfigurierte Tagesfenster begrenzt
  (Default effektiv 4–20 Uhr) — für jemanden, der abends im Zelt liegt, kann ein
  Regenfall nach Fensterende trotzdem relevant sein, und diese Scheibe macht ihn nicht
  sichtbar. Die Alternative — der Alarm rechnet über das Tagesfenster hinaus — würde Alarm
  und Briefing auseinanderlaufen lassen (dieselbe Stunde hieße dann in beiden Meldungen
  etwas anderes) und ist deshalb hier bewusst NICHT gewählt. Das bleibt ein offener Punkt
  für den PO, ohne Ziel dieser Scheibe zu sein — bei Bedarf ein eigenes Ticket.
- **„Stärkste Stunde" ist für maximum- und summenbasierte Nicht-Niederschlags-Größen
  treffend** (Windböe, Gewitter). Für eine künftige Größe, deren Alarm auf einem Minimum
  beruht, kann die Formulierung schief wirken — bewusst nicht Teil dieses Zuschnitts.
- **Der Tagesbezug erscheint nicht am Versandtag.** Wer die Fußzeile „Stand: heute 18:15"
  überliest, hat für Zeiten desselben Tages weiterhin keinen expliziten Tag. Bewusste
  Abwägung gegen Textlärm; per PO-Entscheid umkehrbar.
- **Kein Vier-Kanäle-Wächter für Zeit-/Restmengen-Label allgemein.** Es gibt keinen
  automatischen Test, der bei künftigen Textänderungen alle vier Kanäle einfordert. AC-7
  deckt den hier geänderten Fall ab, nicht die Gattung. → Eintrag für #1196.
- **🔴 Der Ortsvergleich bekommt das WORT, aber nicht die Mechanik** (Adversary-Befund
  F004, 2026-08-21). `to_multi_point_alert_message()`/`to_point_alert_message()`
  (`project.py:336-387`/`:500-513`) nehmen **kein** `now_utc` entgegen — Tagesbezug,
  Vergangenheits-Ausweis und Restmenge erreichen den Ortsvergleich also nie. Was dort
  ankommt, ist allein die geteilte Wortkonstante „stärkste Stunde" aus dem gemeinsamen
  Renderer (belegt durch die nachgezogene Zusicherung in
  `test_alert_location_vocabulary.py:367-372`). Das ist ein **Zwischenzustand**: Der
  Ortsvergleich sagt jetzt „stärkste Stunde 16:00", ohne Vergangenes als vergangen
  auszuweisen. Bewusst so belassen, weil Ortsvergleich-Themen PO-seitig zurückgestellt
  sind; die Source-Liste dieser Spec nennt ausschließlich den Trip-Pfad. AC-8/AC-9/AC-10
  sind generisch formuliert („ein Abweichungsalarm"), gelten aber nur für den Trip-Pfad —
  diese Einschränkung war in der Spec vor der Umsetzung **nicht** benannt und wird hier
  nachgetragen. Nachziehen des Ortsvergleichs = eigenes Ticket.
- **`CorridorEvent` bleibt unangetastet.** Der Schwellen-Alarm-Zweig (`render.py:263`,
  `_sms_corridor_token`) wirft ebenfalls Minuten weg, ist aber keine der beiden
  Ereignisarten aus dem gemeldeten Vorfall. Außerhalb des Zuschnitts dieser Scheibe.
- **`_sms_onset_time` (Radar-Onset-Zahlensuffix) bleibt unangetastet** — Gegenstand des
  Freigabe-Punkts oben, Umsetzung ggf. per Folgeticket der #2046-Session.

## Nicht-Ziele (ausdrücklich ausgeschlossen)

- **Wiederholung desselben Alarms und die stehende Vergleichsbasis.** Der Alarm ging am
  2026-08-20 um 15:30 und um 18:15 mit bitgleichem Inhalt raus, weil die Vergleichsbasis
  bewusst den ganzen Tag stehen bleibt (`trip_alert.py:412-413`, #1916). Das gehört zu
  **#2018** und **#1987** — die #2018-Session hat die Belege.
- **Früher warnen.** Untersucht und ausgeschlossen: Die Prüfung läuft alle 15 Minuten ohne
  Ergebnis-Cache; Open-Meteo hat den Beginn nachträglich auf einen bereits verstrichenen
  Zeitpunkt vorverlegt. Ein schnellerer Takt ändert daran nichts.
- **Ein Filter, der vergangene Ereignisse unterdrückt — bleibt Nicht-Ziel, aber mit neuer
  Begründung.** Die alte Begründung („der Fehler ist die Formulierung, nicht die
  Zustellung") ist **widerrufen**. Die neue, PO-bestätigte Begründung: Eine Meldung, bei
  der deutlich mehr Regen gefallen ist als angekündigt, bleibt relevant, auch wenn nichts
  mehr kommt — nasse Ausrüstung, Wegzustand, Bäche ändern sich rückblickend. Ein Filter
  würde genau diese Meldungen verschlucken. Deshalb: die Meldung wird IMMER zugestellt
  (auch bei `remaining_mm == 0.0`), aber sie sagt jetzt ausdrücklich, dass nichts mehr
  kommt, statt es zu verschweigen oder als bevorstehend zu formulieren.
- **Über das Tagesfenster hinaus rechnen (Nachtregen sichtbar machen).** Bewusst
  ausgeschlossen, weil es Alarm und Briefing mit unterschiedlichen Fenstern rechnen ließe
  (siehe Known Limitations). Ein eigenes Ticket, falls der PO das will.
- **Die Auslöseregel des Nowcasts ändern — bereits erledigt, gehört nicht zu dieser
  Scheibe.** Scheibe 1 (#2020, Prod `b423c913`) hat die Briefing-Sperre bereits gehärtet:
  sie bricht jetzt bei mengenmäßiger Überholung (`window_precip_mm >= 2 × _briefing_precip`
  UND `>= 2,0 mm`). Diese Scheibe ändert **keine** Auslösung mehr — sie ändert
  ausschließlich, **wie** die bereits ausgelöste Nachricht ihren Inhalt und ihre
  Blickrichtung formuliert.
- **`_sms_onset_time`, `_render_sms_onset`, `to_multi_location_onset_alert_message` bleiben
  unangetastet** — Fläche der #2046-Session.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Die Spec führt keine neue Entscheidungsfläche ein. Sie zieht die in #2009
  getroffene Entscheidung (Tagesbezug als additives Modellfeld, Rechnen in der Projektion
  bzw. im Erkennungsdienst, Formulieren im Renderer) auf den zweiten Alarmpfad nach, und
  überträgt für die Restmengen-/Ende-Berechnung ein bereits im Bestand etabliertes Muster
  (Vorwärtsfenster-Summe, `radar_service.window_precip_mm`) auf eine andere Datenquelle
  (Forecast-Stundenreihe statt Radar-Frames). Die Fensterbindung selbst ist keine neue
  Entscheidung, sondern die bereits in ADR-0035/#1372 S1b getroffene Konvention
  (Tagesfenster als gemeinsame Rechengrundlage von Alarm und Briefing), hier nur konsequent
  auf die neue Berechnung angewandt.

## Changelog

- 2026-08-21: Initial spec created (Issue #2020, Scheibe 2 alt: `fix_2020_alarm_zeitangaben.md`)
- 2026-08-21: **Umschnitt nach PO-Rückweisung der Wortlaut-Spec.** Neue Spec
  `fix_2020_alarm_blickrichtung.md` löst `fix_2020_alarm_zeitangaben.md` ab. Kern der
  Änderung: Die Meldung wird vorwärtsgewandt — Restmenge ab Versandzeitpunkt und deren
  Ende (letzte Regenstunde des Tagesfensters) werden die Hauptaussage für
  Niederschlags-Summen-Ereignisse; das bereits Gefallene bleibt als Einordnung erhalten.
  Der Fall „kein weiterer Regen" wird ausdrücklich gemeldet, NICHT unterdrückt (PO-Entscheid:
  eine deutlich höhere Regenmenge als angekündigt ändert die Lage auch rückblickend). Die
  alte Begründung des Nicht-Ziels „Vergangenheitsfilter" („der Fehler ist die Formulierung,
  nicht die Zustellung") wird widerrufen und durch die neue PO-Begründung ersetzt. Die
  Zeitangaben-Kriterien aus Scheibe 2 alt (Tagesbezug, Vergangenheits-Ausweis, „stärkste
  Stunde"-Marker, Wächter-Test gegen Formkollision) wandern unverändert in diese Spec.
- 2026-08-21: **Sachfehler-Korrektur (Fenster statt Kalendertag).** Restmenge und Ende
  rechnen zwingend im Tagesfenster des Trips (`segment_weather.py:285-320`,
  `resolve_configured_window()`, ADR-0035), nicht über den Kalendertag — Beleg: die
  Ziel-Segmentgrenzen entstehen aus demselben Fenster, das auch das Briefing verwendet,
  ausdrücklich damit Alarm und Briefing nie mit verschiedenen Fenstern rechnen. Als
  Invariante in „Implementation Details" ergänzt (inkl. `window_end_utc_exclusive()`-
  Beleg: `end_hour` zählt voll, effektives Fensterende ist `(end_hour+1):00`). **AC-1**
  komplett umgebaut: nutzt jetzt Referenzzeit 14:30 statt 18:15, damit tatsächlich eine
  Restmenge entsteht (der ursprüngliche 18:15-Fall läge bei Standardfenster bereits am
  Fensterende und ergäbe „nichts mehr"). Der 18:15-Fall (beanstandeter Originalfall)
  bekommt dafür ein **eigenes, neues AC-3**: zeigt, dass die Meldung dort ehrlich
  „kein weiterer Regen bis Tagesende" sagt statt eine Restmenge zu erfinden, und trotzdem
  zugestellt wird. **AC-2** (frühe Referenzzeit) von der 22-Uhr-Endzeit befreit, nennt
  jetzt die letzte Regenstunde innerhalb des Fensters. **AC-5** (zwei Regenphasen) neu
  konstruiert mit beiden Phasen **innerhalb** desselben Fensters (6/7 Uhr und 16/17 Uhr,
  Fenster 4–19) — der reale Fall vom 20.08. bleibt als Beleg im Fließtext, ist aber nicht
  mehr der Testfall, weil seine tatsächliche Fensterkonfiguration nicht gesichert ist.
  **Neues AC-6** (Fenstergrenzen-Absicherung): Regen nach Fensterende darf Restmenge/Ende
  nicht beeinflussen, Gegenprobe mit einem weiteren Fenster liefert fenstertreu andere
  Werte. Alle nachfolgenden ACs entsprechend verschoben (vier Kanäle jetzt AC-7,
  Zeitangaben-Kriterien jetzt AC-8 bis AC-14). Neue Known Limitation zu Nachtregen
  außerhalb des Fensters (offener PO-Punkt, kein Ziel dieser Scheibe) sowie ein
  korrespondierendes Nicht-Ziel ergänzt. Insgesamt jetzt **14 ACs** (zuvor 13). Keine
  konkrete Trip-Konfiguration mehr als Testgrundlage — alle Beispiele nennen ihr Fenster
  ausdrücklich.
