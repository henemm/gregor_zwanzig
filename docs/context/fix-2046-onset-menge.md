# Context: fix-2046-onset-menge

Issue #2046 — „Alert ohne echten Inhalt". Branch `fix-2046-onset-menge`, Basis `24e83b14`
(enthält #2020 und #1818). Standard Track (Intake-Score 3).

## Request Summary

Der Nutzer erhielt per Telegram im Kurzstil den Radar-Onset-Alarm `Ziel: R@18:00`. Die
Nachricht nennt keinerlei Regenmenge — nur Kürzel und Uhrzeit. Gesucht ist eine Kurzform,
die sagt, **wie viel** Regen erwartet wird, nicht nur **wann** er beginnt.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/renderers/alert/render.py:553-581` | `_render_sms_onset` — erzeugt exakt `Ziel: R@18:00` (`token = f"{kuerzel}@{...}"`, `body = f"{head}: {token}"`), liest von `OnsetEvent` nur `is_convective` und die Ortsfelder |
| `src/output/renderers/alert/render.py:1042-1080` | `_render_sms_body` — Onset-Weiche `if msg.source is not None` |
| `src/output/renderers/alert/model.py:38-62` | `OnsetEvent` — trägt `intensity_label` (Text), **kein** numerisches Mengen-/Ratenfeld |
| `src/output/renderers/alert/project.py:397-405` | Ortsvergleich-Bündelpfad baut `OnsetEvent` direkt aus `NowcastResult` |
| `src/services/radar_service.py:636-779` | `_derive_result` — berechnet `window_precip_mm` (mm) und `max_rate_mm_h` (mm/h) sowie `intensity_label` |
| `src/services/radar_service.py:129-169` | `NowcastResult` — führt beide Zahlen bereits, seit #2020 |
| `src/services/trip_alert.py:1468-1479` | Abbruchstelle Trip-Pfad: `RadarAlertRequest` übernimmt nur `intensity_label` + `is_convective` |
| `src/services/notification_service.py:165-194,1272-1314,1372-1374` | `RadarAlertRequest`-DTO, `send_radar_alert`, `render_alert_sms(...)`-Aufruf ohne `limit`-Override |
| `src/services/validator_render_service.py:108-152` | Vorschau-/Testeinspeiseweg baut `OnsetEvent` aus dem API-Payload `body.onset` |
| `src/output/tokens/metrics.py:14-67` | Briefing-Grammatik: `R` mit einer Nachkommastelle, `TH:` als Stufe (L/M/H) |

## Wirkkette der Zahl — wo sie abbricht

```
_derive_result  window_precip_mm / max_rate_mm_h   (radar_service.py:745-778)  ✅ vorhanden
      │
      ├─ Trip-Pfad:   trip_alert.py:1468-1479  → RadarAlertRequest   ❌ Zahl wird nicht übernommen
      │                notification_service.py:1290 → OnsetEvent     ❌ Feld existiert nicht
      ├─ Vergleich:   project.py:397-405       → OnsetEvent          ❌ Zahl wird nicht gelesen
      └─ Vorschau:    validator_render_service.py:108-121            ❌ Payload kennt kein Mengenfeld
                                   ↓
                      _render_sms_onset  →  "Ziel: R@18:00"
```

Einzige Leser von `window_precip_mm`/`max_rate_mm_h` im gesamten `src/`-Baum sind
`radar_service.py` selbst und die Überholungsprüfung `trip_alert.py:1382-1383`.

## Existing Patterns

- **Briefing-SMS ist die Referenz-Grammatik** (#1948-Konzept v3, Abschnitt 1): Regen erscheint
  als `R4.0@14` — Zahl mit einer Nachkommastelle plus Stunde; Gewitter erscheint als `TH:M@14`
  — **nie** als Zahl, sondern als Stufe. Ein `TH2.5` wäre in dieser Grammatik missverständlich.
- **Zweig a (Abweichungsalarm) nennt bereits Werte** (`_sms_token`), Zweig c (Radar-Onset) als
  einziger nicht.
- **Additiv-optionale Felder mit Default** sind das etablierte Muster für `OnsetEvent`
  (`location_label` #1041, `segment_id` #1744, `onset_day_offset` #2009) — jeweils
  bit-identisch im unveränderten Fall.

## Dependencies

- **Upstream:** `RadarNowcastService._derive_result` (Frames aus BrightSky/INCA/ARPAE-2I/
  AROME-FR/ICON-D2/Open-Meteo `minutely_15`; jeder Frame trägt numerisch `precip_mm_h`).
- **Downstream:** SMS, **Premium-SMS (Garmin inReach)** und **Telegram im Kurzstil** erhalten
  denselben gerenderten `sms_body` (`notification_service.py:1461-1476`) — eine Änderung am
  Token wirkt auf alle drei Kanäle gleichzeitig; E-Mail und Telegram-Langform sind nicht
  betroffen (eigene Renderer, zeigen `intensity_label` als Wort).

## Existing Specs

- `docs/specs/modules/fix_1948_s4_nowcast_sms_zielbild.md` — hat `_render_sms_onset` gebaut
  (Zeitpunkt statt Countdown, gemeinsamer Ortskopf). **Enthält keine Aussage zu Menge/
  Intensität** — das Weglassen war keine dokumentierte Entscheidung, sondern eine Lücke.
- `docs/specs/modules/fix_2020_alarm_ausloesung.md` — führte `window_precip_mm`/`max_rate_mm_h`
  ein. Die dortige Aussage „`max_rate_mm_h` bewusst ohne Regel-Leser" betrifft die
  **Auslösungslogik**, nicht die Anzeige.
- `docs/specs/modules/fix_2036_alarm_kilometer_ortsangabe.md` — parallele Arbeit am **Kopf**
  derselben Zeile.

## Risks & Considerations

- 🔴 **Messgrundlage:** `window_precip_mm` ist die Menge der nächsten **60 Minuten ab jetzt**
  (`radar_service.py:708-754`), der Alarm feuert aber bei Beginn bis **55 Minuten voraus**
  (`RADAR_ONSET_THRESHOLD_MIN = 55`). Bei spätem Beginn deckt das Fenster fast nur die noch
  trockene Zeit ab — die Zahl wäre systematisch zu klein und würde den Alarm entwerten.
  Die anzuzeigende Menge muss am **Beginn** ausgerichtet sein, nicht an „jetzt".
- **Gewitter-Onset (`TH`)**: Die Briefing-Grammatik reserviert die Position hinter `TH:` für
  eine Stufe. Eine Mengenangabe braucht dort eine eigene, unmissverständliche Form.
- **Ausweichform**: Ohne belastbare Zahl (keine Frames nach dem Beginn, Datenausfall) darf
  keine `0.0` erscheinen — dann bleibt die heutige Form ohne Zahl.
- **Zeichenlimit** 140 (Default, kein Aufrufer übergibt 160); heutige Zeile 13 Zeichen — keine
  Platznot, harter Schnitt `body[:limit]` bleibt unangetastet.
- **Kollision #2036**: ändert `format_alert_location`/den Kopf derselben Zeile, liegt noch
  nicht auf `origin/main`. Getrennte Teilstrings, Zusammenführung per Rebase.
- **Kanal-Parität**: Trip-Radar UND Ortsvergleich-Radar nutzen denselben Renderer — beide
  Projektionspfade müssen die Zahl führen, sonst entsteht eine stille Lücke im Vergleichspfad.

## Tests, die den heutigen Token festnageln

`test_alert_sms_onset_zeitpunkt.py`, `test_alert_onset_day_rollover.py`,
`test_alert_preview_nowcast_replay.py`, `test_952_onset_alert_fidelity.py`,
`test_alert_sms_location_positions.py`, `test_alert_addendum_sms.py`,
`test_issue_919_radar_alert_canonical.py`, `test_multi_location_onset_alert.py`.
