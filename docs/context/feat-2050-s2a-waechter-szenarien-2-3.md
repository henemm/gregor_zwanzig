# Context: #2050 Scheibe S2a — Wächter für Szenarien 2 und 3

> Erhoben 2026-08-22 auf `main` @ `41abfbac` (Worktree `ws-2050-s2`), zwei Explore-Läufe,
> alle Aussagen am Code belegt. Vorgänger: `docs/context/feat-2050-s1-pruefstrecke.md`.

## Request Summary

Issue #2050 gibt dem Alarmsystem ein Sollverhalten und eine Prüfstrecke dafür. Scheibe S1 hat
den Harness geliefert (`tests/helpers/alarm_pruefstrecke.py`). **S2a stellt zwei der zwölf
Szenarien als dauerhafte Wächter auf diese Strecke — ohne Produktivcode zu ändern:**

- **Szenario 2** (Anforderungen C-1, A-3): Briefing kündigte 1 mm an, Radar zeigt 11 mm → Alarm.
  Gegenprobe: kurze Spitze bei gleicher Menge löst **nicht** aus.
- **Szenario 3** (Anforderungen C-1, B-2): Gewitterbeginn rückt von 17 auf 15 Uhr vor → Alarm
  über die **Verschiebung**, beide Zeiten genannt.

Szenario 1 (B-1, „Regen läuft schon") ist **nicht** Teil dieser Scheibe — es braucht Produktivcode
und kollidiert mit #2020 Scheibe 2. Es wird als **S2b** nachgezogen. Begründung im
Issue-Kommentar vom 2026-08-22.

## Der Kern: was die bestehenden Tests NICHT prüfen

Beide Szenarien haben bereits Testabdeckung — aber auf einer Ebene, die die eigentliche
Zusicherung nicht erreicht. Genau das ist das Muster, das Issue #2050 abstellen will.

### Szenario 2 — 17 Tests, kein einziger mit Gedächtnis

`tests/tdd/test_nowcast_briefing_overtake.py` (1405 Zeilen, 17 Tests) fährt die
Mengen-Überholung über den echten Einstieg `TripAlertService.check_radar_alerts()` — inklusive
der geforderten Gegenprobe (`test_ac2_high_peak_rate_without_enough_amount_keeps_suppression`,
`test_ac4_high_peak_rate_alone_never_triggers_the_overtake`).

**Jeder dieser 17 Tests ist ein Einzelaufruf mit leerem Datenträger.** Jeder Testkörper legt eine
frische `uid` an (`_clean_user`/`_ensure_real_user_dir`); selbst
`test_ac3_stronger_or_equal_nowcast_never_alarms_less_than_a_weaker_one` (Zeilen 594–670) baut
zwei **unabhängige** Nutzer `uid1`/`uid2` statt einer Folge. Nirgends wird `check_radar_alerts()`
zweimal auf demselben Trip gerufen.

**Folge:** Der Sperrzeit-/Cooldown-Mechanismus (`ThrottleStore`) kommt in dieser Datei **nie zum
Tragen**, weil jeder Lauf ohne Vorgeschichte startet. Die Anforderung A-3 („eine Verschärfung
überholt jede Sperre") ist damit an der Stelle, an der sie wirkt, unbewacht — geprüft wird nur,
ob die Überholung *erkannt* wird, nicht ob sie eine *bestehende Sperre bricht*.

### Szenario 3 — 10 Tests, alle unterhalb der Auslöseentscheidung

`tests/tdd/test_onset_shift_alert.py` (767 Zeilen, 10 Tests) prüft `OnsetShiftEvent` (#1468)
gründlich: beide Uhrzeiten im Text, Richtungswort, Mitternachtsübergang, Erstauftauchen,
Protokoll, alle vier Kanäle.

**Alle zehn setzen an `WeatherChangeDetectionService.detect_changes()` an** (über den lokalen
Helfer `_aenderungen()`, Zeile 161), nicht an `TripAlertService.check_and_send_alerts()`.

**Belegte Lücke:** Ein Grep über alle 41 Testdateien, die `check_and_send_alerts` aufrufen,
gefiltert auf `thunder_onset`, liefert **null Treffer**. Es gibt im gesamten Repo keinen Test, der
eine Gewitter-Vorverlegung durch die echte Auslöseentscheidung fährt.

**Warum das eine echte Fehlerklasse ist:** `DeviationAlertEngine._select_detector`
(`src/services/deviation_alert_engine.py:175-204`) wertet `thunder_onset` nur aus, wenn
`trip.display_config.metric_alert_levels["thunder_onset"]` einen Level ≠ „off" trägt. Ein Trip
kann den Alarmtyp also **konfigurativ gar nicht erreichen**, ohne dass ein einziger bestehender
Test das bemerkt — die zehn Tests umgehen diese Auswahl, indem sie die Regeln direkt übergeben.

## Related Files

| Datei | Relevanz |
|---|---|
| `tests/helpers/alarm_pruefstrecke.py` (189 Z.) | Der Harness. Wird **benutzt**, nicht geändert |
| `tests/tdd/test_nowcast_briefing_overtake.py` (1405 Z.) | Bestehende Abdeckung Szenario 2 — wird **nicht** angefasst |
| `tests/tdd/test_onset_shift_alert.py` (767 Z.) | Bestehende Abdeckung Szenario 3 — wird **nicht** angefasst |
| `tests/helpers/nowcast_gate_fixtures.py` (529 Z.) | `make_trip()` (:385), `frozen_active_window()` (:438) — **belegt durch Session #2036** |
| `src/services/trip_alert.py` | Überholungsprüfung :1370-1378, `_briefing_precip_for_onset` :1111, Cooldown-Adapter :978 |
| `src/services/deviation_alert_engine.py` | `_select_detector` :175-204 — die Konfigurations-Weiche |
| `src/services/weather_snapshot.py` | `save_alarm_anchor(trip_id, target_date, segments, channel)` :225 |
| `src/services/throttle_store.py` | `record(scope, key, now)` :84, `is_throttled` :71 |
| `src/services/alert_daily_limit.py` | `increment(user_id, now, zone)` :110 |
| `src/services/alert_state.py` | `AlertStateService.save(entity_id, state)` :73 — Änderungs-Gedächtnis |
| `src/services/alert_briefing_anchor.py` | `record_briefing_sent(...)` :192, `write_anchor_and_reset_memory(...)` :259 |

## Die Prüfstrecke — API und Eigenheiten

```python
AlarmPruefstrecke(*, user_id: str, settings: Settings | None = None, throttle_hours: int = 2)

.lauf(*, at: datetime, zweig: Literal["deviation","official","radar"], trip: Trip,
      cached_weather: list | None = None, fresh_weather: list | None = None,
      official_notices: list | None = None, radar_service: object | None = None,
     ) -> AlarmPruefstreckeLauf(triggered_count, mail, telegram, sms, premium_sms)
```

| Eigenschaft | Bedeutung für S2a |
|---|---|
| Zweig → Einstieg | `deviation` → `check_and_send_alerts(...)` · `radar` → `check_radar_alerts()` · `official` → `_send_official_alert_only(...)` |
| Uhr | Der Harness friert selbst ein (`with freeze_time(at)`), Aufrufer übergibt nur `at=`. Kein `now_utc=` — `check_official_alert_triggers` verwirft es (`trip_alert.py:1811`) |
| Zwischen zwei Läufen | Vier Cache-Resets (Radar, Weather, Thunder-Window, Telegram-Rate-Limit) + **frische** `TripAlertService`-Instanz. Kontinuität kommt vom Datenträger unter `get_data_dir(user_id)` — genau wie bei jedem Cron-Tick |
| Vier Kanäle | Kein Setup nötig: zwei lokale HTTP-Stubs (Telegram, seven.io) plus `mail_sink`. SMS vs. Premium-SMS werden am `from`-Feld getrennt (`PREMIUM_SMS_SENDER`) |
| **Kein Parameter für den Briefing-Anker** | Der Aufrufer muss ihn **vor** dem Lauf über den produktiven Schreibweg setzen — das ist die Naht, an der S2a arbeitet |

## Existing Specs

- `docs/specs/modules/alarm_pruefstrecke.md` — S1, `status: approved`. Sagt ausdrücklich, dass
  die zwölf Szenarien spätere Scheiben sind und der Zustand über die produktiven Schreibwege
  vorbelegt wird
- `docs/specs/modules/alarm_testeinspeisung.md` — der zustandslose `alert-preview`-Endpoint aus
  #1948 S2. **Nicht** betroffen, bekennt sich in seiner eigenen Spec zur Zustandslosigkeit

## Risks & Considerations

1. **Doppelung statt Zugewinn.** Ein Wächter, der nur nachbaut, was die 17 bzw. 10 bestehenden
   Tests schon prüfen, ist Ballast. Jeder neue Test muss die oben belegte Lücke treffen:
   *Zeitreihe mit Gedächtnis* (Szenario 2) bzw. *echte Auslöseentscheidung inklusive
   Konfigurations-Weiche* (Szenario 3).
2. **Kein Produktivcode.** Sollte sich zeigen, dass ein Wächter ohne Produktivänderung nicht
   grün zu bekommen ist, ist das ein **Befund**, kein Anlass zum Nachbessern am Produktivcode —
   er gehört dann als eigene Scheibe gemeldet.
3. **Wortlaut-Sperre gegenüber #2020 S2.** Keine textprüfenden Zusicherungen auf Formulierungen,
   die dort gerade entstehen (Langform `Bis jetzt:` / `Ab jetzt:`, Kurzform-Token
   `Rest{mm}@{HH}`, Bedeutungswörter bei Zeitangaben). Szenario 3 darf auf `→` und Richtungswort
   prüfen — das ist #1468-Bestand und dort ausdrücklich Nicht-Ziel.
4. **Dateibelegung.** `tests/helpers/nowcast_gate_fixtures.py` wird von Session #2036 bearbeitet
   (Fixture-Falle #1196). S2a darf die Datei **lesen und importieren**, aber nicht ändern.
5. **Uhrzeit-Abhängigkeit.** `check_radar_alerts()` braucht ein aktives Segment.
   `save_trip()` rechnet Segmentzeiten per Naismith neu (Compute-on-Save) — Fixture-Zeiten
   überleben das nicht. Das `at=` der Läufe muss im garantiert aktiven Fenster liegen
   (Vorbild: `frozen_active_window()`, Default 12:00 UTC).
6. **Geteilter Prozess-Cache.** Der Harness setzt vier Caches zurück; ein Wächter, der einen
   eigenen `RadarNowcastCacheService` mitbringt, muss ihn je Lauf frisch bauen, sonst wird die
   Zeitreihe wirkungslos.
7. **Mandantentrennung.** Jeder Wächter arbeitet auf einer eigenen `user_id` unter
   `data/users/<user_id>/`; Parallelläufe anderer Sitzungen dürfen nicht hineinspielen.

## Technischer Ansatz (Analyse)

**Zwei neue Testdateien, kein Produktivcode, keine bestehende Testdatei geändert.**

### Wächter 1 — Szenario 2 als Dreilauf-Zeitreihe (`zweig="radar"`)

Eine `AlarmPruefstrecke` auf **einer** `user_id`, drei aufeinanderfolgende `lauf()`-Aufrufe zu
gestellten Zeiten innerhalb der Sperrzeit:

| Lauf | Lage | Erwartung | Anforderung |
|---|---|---|---|
| 1 | Briefing 1 mm, Radar 11 mm | Alarm, Kanäle tragen Inhalt | C-1 |
| 2 | unverändert, kurz danach | **schweigt** — und zwar wegen der von Lauf 1 gebuchten Sperre, nicht wegen unveränderter Daten | C-1 |
| 3 | deutlich verschärft | **kommt durch**, obwohl die Sperre noch läuft | A-3 |

Dazu die Gegenprobe als vierter Lauf auf **eigener** `user_id`: kurze Spitze bei gleicher
Spitzenrate, aber zu geringer Menge → `triggered_count == 0`.

Der Unterschied „schweigt wegen Sperre" vs. „schweigt wegen gleicher Daten" muss am Ergebnis
unterscheidbar sein — sonst wäre Lauf 2 trivial grün. Wie das nachgewiesen wird (Alarmprotokoll
mit benanntem Unterdrückungsgrund, D-2), ist in der Spec festzulegen.

### Wächter 2 — Szenario 3 durch die echte Auslöseentscheidung (`zweig="deviation"`)

Ein Trip mit `display_config.metric_alert_levels["thunder_onset"]` aktiv, `cached_weather` mit
`thunder_onset_utc` = 17:00, `fresh_weather` = 15:00. Ein `lauf()` über
`check_and_send_alerts(...)`:

- genau ein Alarm
- der ausgelieferte Text nennt **beide** Uhrzeiten und das Richtungswort
- Negativprobe: derselbe Lauf mit `metric_alert_levels["thunder_onset"]` abgeschaltet löst
  **nicht** aus — das nagelt die Konfigurations-Weiche fest, die heute unbewacht ist

### Bewusst nicht enthalten

- Szenario 1 (B-1) → S2b
- Änderungen an Produktivcode
- Änderungen an `test_nowcast_briefing_overtake.py`, `test_onset_shift_alert.py`,
  `nowcast_gate_fixtures.py`
- Ein Szenario für Etappen < 1 h (Nebenbefund aus #2020 S2, `trip_segments.py:294-311` vs.
  `:220-243`, Bug #856) — vermerkt für eine spätere Scheibe
