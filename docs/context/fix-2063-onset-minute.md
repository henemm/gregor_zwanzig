# Context: fix-2063-onset-minute

## Request Summary

Issue #2063: Die Radar-Alarm-Uhrzeit (Beginn, seit #2051 S1 auch Ende) liegt in etwa jedem zweiten Lauf eine Minute vor dem Frame-Zeitstempel der Quelle (z. B. 17:59 statt 18:00). Betroffen sind alle Kanäle. Ziel: Die angezeigte Uhrzeit ist immer exakt der Frame-Zeitpunkt, egal in welcher Sekunde der Lauf startet.

## Ursache (bestätigt am Code, Stand origin/main c1d098484)

1. `src/services/radar_service.py:1306-1319` `_derive_result`: `onset_minutes = max(0, round(delta))`, der exakte `onset_ts` (Frame) liegt daneben vor, wird aber nur intern (Mengenrechnung #2046, Ende-Ableitung #2051) genutzt.
2. `radar_service.py:1436-1460`: `event_end_minutes = round((_end_ts - now)/60)`, gleiche Rundung; `_end_ts` exakt vorhanden (laufender Fall: `max(_end_ts, _laufend[3])`).
3. Die Verbraucher rechnen `now_x + timedelta(minutes=<gerundet>)` mit IHREM eigenen `now` (Sekunden!) zurück, dann `strftime("%H:%M")` (abschneiden, `utils/timezone.py:165 local_fmt`).

Zusatzbefund: Teilweise ist `now_x` nicht einmal dasselbe `now` wie in `_derive_result` (z. B. `radar_service.py:871`, `:957`, `starkregen_hint.py:57` holen ein frisches `datetime.now()`): zusätzliche Drift.

## Related Files (Rückrechnungs-Stellen, alle betroffen)

| Stelle | Zweck |
|---|---|
| `src/services/alert_log.py:300-329` `nowcast_onset_at` / `nowcast_event_end_at` | EINE Ableitung Trip + Ortsvergleich (#2050 S6) → `trip_alert.py:459, 2600`, `compare_radar_alert.py:88,117-118` |
| `src/output/renderers/alert/project.py:80-93` `onset_display` (+ `:161-178` `onset_event_from_nowcast`) | Baustein #2982 (Trip-Versand, Ortsvergleich, Replay) |
| `src/services/radar_service.py:868-937` (DE) und `:955-980` (EN) | Text-Formatierung Nowcast (Wetter-Abfrage/Antworten) |
| `src/output/renderers/email/starkregen_hint.py:55-75` | Starkregen-Kurzfristhinweis im Briefing |
| `src/services/trip_command_processor.py:3469-3510` | Inbound-Antworten Radar-Zonen (`z.onset_minutes`) |
| Nur Durchreicher von Minuten: `compare_alert_preview_service.py:158`, `validator_render_service.py:209-210`, `notification_service.py:853` |

Datenmodell: `NowcastResult` in `radar_service.py:~210-300` (dataclass, Felder `onset_minutes`, `event_end_minutes`, `already_running`, `event_ongoing_beyond_horizon`).

## Existing Patterns

- #2046 hat `onset_ts` bewusst exakt eingeführt (gerundete Zahl ungeeignet für Mengenrechnung), gleiche Begründung trägt hier.
- #2050 S6: eine zentrale Ableitung (`alert_log.nowcast_onset_at`) für beide Flächen (ADR-0021) → Fix gehört primär dorthin.
- `onset_minutes` selbst bleibt als Vorlauf-Anzeige („in ~22 Min“) und für Logik (`radar_alert_due`, Schwellen) unverändert.

## Dependencies / Dependents

- Fälligkeit/Entprellung nutzt `onset_minutes` (nicht ändern).
- Alarm-Anker/Verschiebung (#1468, #2009) vergleicht Onset-Zeitpunkte über `nowcast_onset_at`: exakte Frame-Zeit macht den Anker stabiler (kein Sekunden-Wandern), keine Regression erwartet, aber Tests `test_onset_anchor_*` beachten.
- Tagesbezug/Wochentag (#2054, #2219) hängt an `onset_dt`, bleibt korrekt.

## Existing Specs

`docs/specs/modules/radar_nowcast.md`, `fix_2046_onset_menge.md`, `fix_2009_nowcast_vorlauf.md`, `fix_2982_onset_event_baustein.md`, `fix_2078_onset_sms_zeit_token_schnitt.md`, `feat_2054_onset_wochentagskuerzel.md`.

## Bestandstests, die heutiges Verhalten festnageln (laut Issue)

`tests/tdd/test_alert_sms_onset_zeitpunkt.py`, `tests/tdd/test_alert_onset_day_rollover.py`, ggf. weitere `test_*onset*`.

## Risks

- Scope: ~6 Rückrechnungs-Stellen in 5+ Dateien → Scoping-Limit (4-5 Dateien) beachten; ggf. Kern (Modell + `alert_log` + `project.py`) zuerst, übrige Anzeigestellen in Folge-Scheibe.
- Objekte, die nur Minuten tragen (Zonen in `trip_command_processor`, Preview-/Validator-Payload) brauchen entweder das neue Feld oder bleiben bei Minuten (dann dort Rundung auf volle Minute statt Abschneiden).
- Replay/Preview-Pfade bauen `NowcastResult` ggf. ohne `now`-Bezug: Fallback auf `now + minutes` nötig, wenn exakter Zeitstempel fehlt.
- Tests dürfen keine echte Uhr nutzen: Sekunden-Lage des `now` muss im Test steuerbar sein (Reproduktion 17:37:42).

## Analysis

**Type:** Bug (nutzersichtbar, alle Kanäle, Trip + Ortsvergleich + Briefing + Kommando-Antwort)

**Root Cause:** `radar_service._derive_result` rundet Beginn/Ende/Reichweite auf ganze Minuten (:1315-1319, :1441, :1458, :1493) und verwirft die exakten Zeitstempel; Verbraucher rechnen `eigenes now + gerundete Minuten` zurück und schneiden per `%H:%M` ab. Reproduktion: now=17:37:42, Frame 18:00 → round(22.3)=22 → 17:59:42 → "17:59". Zusatzdrift: frisches `datetime.now()` in radar_service.py:871/:957, starkregen_hint.py:55; doppeltes Abschneiden `vorlauf` in project.py:169.

**Affected Files (Change Type), 3 Scheiben, EIN Release (Kanalparität ADR-0095):**
- S1: `src/services/radar_service.py` MODIFY (NowcastResult + `onset_at`/`event_end_at`/`source_reach_at`, `_derive_result` setzt sie; `format_now_text` DE/EN nutzt sie), `src/services/alert_log.py` MODIFY (`nowcast_onset_at`/`nowcast_event_end_at` bevorzugen Feld, Fallback `now+minutes`), `src/output/renderers/alert/project.py` MODIFY (`onset_display`, `event_end_display`, `source_reach_display`, kein `vorlauf`-Abschneiden).
- S2: `src/output/renderers/email/starkregen_hint.py`, `src/services/trip_report_scheduler.py` (~:2447), `src/services/notification_service.py` (~:845-853) MODIFY (exakte Zeitpunkte durchreichen, kein frisches now).
- S3: `src/services/rain_extent.py` (Zone trägt exakte Zeitpunkte), `src/services/trip_command_processor.py` (:3483/:3506) MODIFY.
- Tests: neue Tests je Scheibe; Bestandstests `test_alert_sms_onset_zeitpunkt`, `test_alert_onset_day_rollover`, `test_onset_*` laufen lassen (Fallback hält sie grün).

**Scope/Risk:** gesamt ~8 Src-Dateien, ~220 LoC, je Scheibe ≤4 Dateien. Risiko mittel: zentrale Zeitableitung, aber additiv (neue Optional-Felder, Default None, Fallback auf heutige Rechnung). `onset_minutes`/`event_end_minutes` und Fälligkeit/Schwellen unverändert („in ~22 Min“ bleibt).

**Technical Approach (Variante A2, empfohlen von Plan-Agent):** exakte Zeitstempel im Ergebnis statt Rückrechnung. Verworfen: B (`computed_at` + Rundung, Tie-Risiko bei exakt :30), C (nur Rundung in Verbrauchern, Drift durch frisches now bleibt).

**Details/Entscheidungen:**
- `already_running`: Beginn bleibt `now_utc` (Regel #2050 S6 unverändert), `onset_at` darf gesetzt oder None sein, wird dann ignoriert.
- Ende bei laufendem Regen: `event_end_at = max(_end_ts, _laufend[3])` (Deckungsgrenze, wie heute).
- Fallback, wenn Feld None (Replay/Preview/Stand-ins/alte Payloads): `now + minutes` wie heute.
- Tests steuern Sekunde über injiziertes `now` (`_derive_result(..., now=...)` bzw. `RadarNowcastService(now_fn=...)`), Sekundenlagen :12 und :42 → "18:00"; kein Mock-Theater.

**Dependencies:** Alarm-Anker (#1468/#2009) wird stabiler; Tagesbezug/Wochentag (#2054/#2219) hängt an `onset_dt`, bleibt korrekt.

**Open Questions:** keine (rein technisch, Zielverhalten eindeutig: angezeigte Uhrzeit = Frame-Zeit).
