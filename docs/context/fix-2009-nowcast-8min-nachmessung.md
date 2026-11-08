# Context: fix-2009-nowcast-8min-nachmessung

**Issue:** #2009 „Gewitter in 8 min — geht es nicht früher?" (type:bug, priority:high, go-live-pflicht)
**Erstellt:** 2026-11-08 · **Vorgänger-Workflow:** `fix-2009-nowcast-vorlauf` (PR #2024, geliefert 2026-08-21, Kontext `docs/context/fix-2009-nowcast-vorlauf.md`)

## Request Summary

Das Ticket wurde am 2026-08-24 wieder geöffnet: Auch nach dem Fix lauteten 18 von 18 Onset-Meldungen
im August „in 8 Min". Offen ist, ob es sich um ein Rasterartefakt handelt oder ob die Datenquelle das so liefert,
und ob Gregor heute (Stand `main` @ `22f4cd7fa`) früher und mit echter Streuung warnt.

## Neue Messung (2026-11-08) — Produktiv-Alarmlog `/var/lib/gregor/users/henning/alert_log.json`

55 Radar-/Nowcast-Einträge mit `lead_time_minutes`, alle Quelle INCA, alle Trip `5f534011`, letzter Eintrag 2026-09-05:

| Monat | Vorlauf (Min) → Anzahl |
|---|---|
| 2026-08 | 8 → 40 · 23 → 2 · 38 → 1 · 53 → 5 · 98 → 1 |
| 2026-09 | 8 → 2 · 53 → 3 · 68 → 1 |

**Befund 1: Die Streuung ist da.** Nach dem Fix aus PR #2024 kamen 23/38/53/68/98 vor. Die Hypothese „eine
noch nicht gefundene Stelle hält Alarme zurück" (Kommentar vom 2026-08-24) ist damit widerlegt.

**Befund 2 — Hauptquelle der „8": ein bereits laufender Regen wurde als bevorstehend gemeldet.** Am 29.08. gab es zwischen 11:07 und 15:07 UTC
**15 Alarme in Folge, jede Viertelstunde einen**, jeweils „in 8 Min", mit `event_at` = nächster Viertelstundenpunkt
und `event_end_at` Stunden später (z. B. 11:52 → Beginn 12:00, Ende 14:45). Ursache: Der Filter `f.timestamp >= now`
verwarf das laufende Frame. Bei laufendem Regen war deshalb das nächste Frame der „Beginn": 15 − 7 = 8.
Damit erklärt sich der Großteil der 42× „8". Kein Wetterphänomen, sondern ein Artefakt.

**Befund 3:** Seit 2026-09-05 gab es keinen einzigen Radar-Alarm in Produktion mehr (kein aktiver Trip, Saisonende).
Unter dem **heutigen** Code gibt es also noch keinen Produktiv-Nachweis.

> **KORREKTUR (Analyse 2026-11-08):** Die Zahlen oben sind am Produktiv-Alarmlog **nicht reproduzierbar**. Nachzählung
> derselben Datei (220 Einträge, 12.06.–06.11.): nur **11** Einträge mit `lead_time_minutes` (E-1-Feld gibt es erst seit ~24.08.),
> **keine** 15er-Serie am 29.08. (dort genau 1 Alarm, Vorlauf 23). Maßgeblich ist die Tabelle im Abschnitt „Analysis".

## Was seit August am Code geändert wurde (alle drei Ursachen sind adressiert)

| Ursache der „8" | Behoben durch | Stand heute |
|---|---|---|
| Schwelle 20 Min (nur die 8 passt) | PR #2024 (→ 55), #2261 A-1 `70f18b8ac` (→ Quell-Horizont 180) | `RADAR_ONSET_THRESHOLD_MIN` in `src/services/radar_service.py` |
| Cron `7,22,37,52` → nächster Frame immer 8 Min entfernt | #2261 A-2 S2 `324b3ae04` (2026-10-05) | `internal/scheduler/scheduler.go:352/355`: `3-58/5 * * * *` (alle 5 Min, Versatz 3). Abstand zum nächsten INCA-Frame jetzt 2/7/12 Min |
| Laufendes Ereignis als „in 8 Min" | #2050 S2b (Spec `docs/specs/modules/alarm_szenario_laufendes_ereignis.md`) | `_laufendes_frame()` `radar_service.py:439`, Zweig `:1277-1297`; Wächter `tests/tdd/test_alarm_szenario_laufendes_ereignis.py` |
| Anzeige „in N Min" | #2261 A-1 B-2: Uhrzeit statt Restminuten | Renderer `src/output/renderers/alert/render.py` |

## Related Files

| File | Relevance |
|---|---|
| `src/services/radar_service.py` | Onset-Ableitung `_derive_result` (`:1259-1297`), `_laufendes_frame` (`:439`), Schwelle |
| `src/services/trip_alert.py` | `check_radar_alerts()`, `radar_alert_due()`: Trip-Auslösepfad |
| `src/services/compare_radar_alert.py` | Auslösepfad des Ortsvergleichs (ADR-0021 geteilt) |
| `src/services/alert_log.py:300-325` | `nowcast_onset_at`, E-1-Felder `lead_time_minutes`/`event_at`/`event_end_at`: das Messinstrument dieser Analyse |
| `src/services/alert_input_capture.py:34` | Mitschnitte werden nur **24 h** aufbewahrt (`_MAX_AGE_SECONDS`) |
| `internal/scheduler/scheduler.go:352,355` | Radar-Takt Trip/Vergleich |
| `tests/tdd/test_alarm_szenario_laufendes_ereignis.py` | bestehender Wächter für laufende Ereignisse |
| `tests/tdd/test_radar_onset_threshold_variance.py` | Varianz-Wächter aus PR #2024 (Rasterwerte) |

## Existing Patterns

- Alarm-Wächter fahren über die `AlarmPruefstrecke` gegen den echten `check_radar_alerts()`, Frames über die DI-Naht `frame_source=` des echten `RadarNowcastService`; kein Mock.
- Zeitfestigkeit über `tests/helpers/wanduhr_matrix.py` (24-h- **und** 10-Min-Raster, siehe PR #2024).
- Die Produktiv-Messung erfolgt über das Alarmlog (E-1-Felder). Mitschnitte unter `/var/lib/gregor/debug/alert_input/nowcast/` (aktuell 714 RADOLAN vom 07.11., 8 Korsika, 1 INCA, alle trocken).

## Dependencies

- Upstream: INCA (15-Min-Frames), RADOLAN (5-Min-Frames), Météo-France (15 Min), Scheduler-Takt.
- Downstream: alle vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS), Trip und Ortsvergleich, Alarmlog/Entdopplung.

## Existing Specs

- `docs/specs/modules/fix_2009_nowcast_vorlauf.md` (Vorgänger, AC-1..AC-6)
- `docs/specs/modules/feat_2261_a1_radar_vorlauf.md`, `feat_2261_a2s2_radar_takt.md`
- `docs/specs/modules/alarm_szenario_laufendes_ereignis.md` (#2050 S2b)

## Risks & Considerations

- **Offen bleibt nur der Nachweis, kein bekannter Defekt.** Der Rest von #2009 ist: unter dem heutigen Code aus Nutzersicht
  belegen, dass (a) laufender Regen nicht als „in 8 Min" kommt und (b) der Vorlauf bei einem 5-Min-Takt streut. Ein
  Produktiv-Nachweis ist erst mit Regen auf einem aktiven Trip möglich. Ein deterministischer Nachbau des 29.08.-Musters
  (laufender Regen über 4 h, Takt alle 5 Min) über die `AlarmPruefstrecke` ist sofort machbar.
- Der „nächste Regentag"-Plan aus dem Kommentar vom 24.08. trägt nicht: Mitschnitte verfallen nach 24 h.
- Neue mögliche Rasterkonstante: Takt `3-58/5` gegen 15-Min-INCA ergibt Vorläufe ≡ 2/7/12 (mod 15). Das ist ehrliche
  Arithmetik, keine Klemmung, sollte aber im Wächter als erwartete Werte stehen, sonst wiederholt sich der Verdacht.
- Nebenbefund: die 15er-Serie am 29.08. (ein Alarm je Lauf für dasselbe Ereignis) trotz Ereignis-Entdopplung. Prüfen, ob
  das unter S2b/C-2 (ein Alarm je Ereignis) heute entdoppelt wird; das gehört in den Nachbau.
- Prozess: Ticket nur mit Nachweis schließen; kein Code-Fix ohne roten Test aus Nutzersicht.

## Analysis

### Type
Bug (Messgröße und Ereignis-Anker falsch bei laufendem Regen; Anzeige an den Nutzer korrekt)

### Messung am Produktiv-Alarmlog (2026-11-08, korrigiert)

11 Radar-Alarme mit `lead_time_minutes` (alle Trip, 24.08.–29.08.):

| gesendet (UTC) | Quelle | Vorlauf | Beginn → Ende | Schwere | Deutung |
|---|---|---|---|---|---|
| 24.08. 12:22 / 12:37 / 13:07 | ARPAE-2I | 53 / 38 / 8 | 13:15 → 15:00 (dreimal gleich) | HIGH | echter Vorlauf, aber dreifach gemeldet → **#2848** |
| 24.08. 16:22 | ARPAE-2I | 53 | 17:15 → 18:00 | MODERATE | echter Vorlauf |
| 25.08. 04:07 / 04:52 / 06:52 / 09:52 | ARPAE-2I | 8 / 8 / 8 / 8 | Beginn = nächster Viertelstundenpunkt, Ende ≈ gesendet + 3 h (Horizontende) | LOW→MODERATE | **Log-Artefakt:** Regen lief bereits |
| 25.08. 13:22 | INCA | 98 | 15:00 → 16:15 | LOW | echter Vorlauf |
| 25.08. 16:52 | INCA | 23 | 17:15 → 19:45 | LOW | echter Vorlauf |
| 29.08. 04:07 | INCA | 23 | 04:30 → 05:00 | HIGH | echter Vorlauf |

Seit 29.08. kein Radar-Alarm mehr (kein aktiver Trip). Die Streuung ist da (98/53/53/38/23/23). Die „8" ist überwiegend das unten beschriebene Artefakt.

### Root Cause (am Code belegt)
`RadarNowcastService._derive_result` (`src/services/radar_service.py:1257-1282`) filtert `f.timestamp >= now`; `onset_minutes` ist der Abstand zum **nächsten** nassen Frame. Läuft der Regen schon (`already_running`, S2b), bleibt `onset_minutes` trotzdem z. B. 8 (nicht 0/None). Der Renderer (`_onset_wann_kopf`) zieht `already_running` vor und zeigt „läuft bereits", die Anzeige ist also korrekt. **Nicht** vorgezogen wird es an:
- `alert_log.nowcast_onset_at` (`:300-307`): Docstring behauptet fälschlich „laufend → onset_minutes None"
- `trip_alert.py:443` (`lead_time_minutes`), `:2560` (`_onset_dt` → Identität/`event_at`/Briefing-Vergleich)
- `compare_radar_alert.py:86` (`_onset_at`), `:345/:471` (Log), `:416` (Backoff-Schlüssel; Trip `:2862` macht es schon richtig)
- ggf. `project.py:609/625` (prüfen)
Folge: Log meldet „8", `event_at` wandert pro Lauf zum nächsten Viertelstundenpunkt.

### Varianten
| Variante | Änderung | Bewertung |
|---|---|---|
| A | Quelle: `onset_minutes=0` bei laufend | hohes Risiko, ändert Semantik für rain_extent, Aufenthaltsfenster, Mengenvergleich, Sharpness; viele Tests → verworfen |
| **B (empfohlen)** | eine geteilte Ableitung in `alert_log.py` (Beginn = jetzt, Vorlauf 0 bei `already_running`), die Trip- und Vergleichspfad nutzen; Backoff-Schlüssel Vergleich wie Trip | kleiner Scope, Quelle unberührt, ADR-0021 (geteilt) |
| C | B + stabiler Anker `running_since` (Slot-Start des laufenden Frames) | nur Folgeticket, falls Entdopplung mit „jetzt" nicht hält |

### Affected Files (with changes)
| File | Change Type | Description |
|---|---|---|
| `src/services/alert_log.py` | MODIFY | `nowcast_onset_at` + neue Vorlauf-Ableitung zieht `already_running` vor; Docstring richtig |
| `src/services/trip_alert.py` | MODIFY | `:443`, `:2560` auf die geteilte Ableitung |
| `src/services/compare_radar_alert.py` | MODIFY | `:86`, `:345`, `:471`, Backoff `:416` |
| `src/services/project.py` | MODIFY? | `:609/:625` prüfen |
| `tests/tdd/test_alarm_szenario_laufendes_ereignis.py` | MODIFY | Taktminute `:07` → 5-Min-Takt `3-58/5` |
| `tests/tdd/test_radar_onset_threshold_variance.py` | MODIFY | Grid ≡ 8 (mod 15) → Werte des 5-Min-Takts (2/7/12 mod 15) |
| `tests/tdd/test_2009_laufender_regen_vorlauf_*.py` | CREATE | RED-Wächter (s. u.) |

### Scope Assessment
- Produktivcode 3–4 Dateien, ca. +25–45 LoC; Tests ca. +140–180 LoC
- Risk Level: LOW–MEDIUM (Entdopplung hängt am `event_at`; Wächter muss Einmal-Alarm belegen)

### RED-Wächter (über `check_radar_alerts` / `check_all_compare_presets`, `frame_source`-DI, kein Mock)
1. Trip, Regen läuft (laufendes Frame nass, nächstes nass), Lauf im 5-Min-Takt: Log-Vorlauf 0, Beginn = Lauf-Zeitpunkt, nicht nächster Viertelstundenpunkt
2. dasselbe im Ortsvergleich
3. Langlauf (mehrere Läufe im 5-Min-Takt bei laufendem Regen): genau **ein** Alarm
4. Übergang „kommt in 8" → „läuft": kein zweiter Alarm
5. Gegenprobe: Frame davor trocken, Regen in 8 → Vorlauf bleibt 8
6. Vorlauf-Werte im 5-Min-Takt (2/7/12 mod 15 bei INCA) als erwartete Werte
7. Kanäle zeigen „läuft bereits", nie „in 0 Min"

### Dependencies
Downstream: Alarmlog (E-1), Ereignis-Entdopplung (`alert_gate`), alle vier Kanäle über Trip- und Vergleichspfad. Upstream unverändert.

### Gegenbefunde
- Die Artefakt-Deutung der 25.08.-Serie ist ein Indiz (Ende = Horizontende), kein Beweis; der Wächter 1 belegt den Mechanismus deterministisch.
- Der Nutzer-Text war schon korrekt („läuft bereits"); der Fix bessert Messung und Entdopplungsanker, nicht die Anzeige.
- Nicht in diesem Ticket: Dreifachmeldung 24.08. (#2848, anderer Mechanismus).

### Open Questions
- keine (Entscheidungen technisch, PO-Freigabe erst an der Spec)
