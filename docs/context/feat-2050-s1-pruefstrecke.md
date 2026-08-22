# Context: feat-2050-s1-pruefstrecke

Issue #2050, Scheibe 1 — Prüfstrecke: Einspeisung in die Auslöseentscheidung + vorbelegbarer Zustand.
Erhoben 2026-08-21 auf `b423c913` über drei parallele Explore-Läufe, alle Kernaussagen am Code nachgeprüft.

## Request Summary

Alarm-Szenarien sollen als **Zeitreihe mit Gedächtnis** gegen die *echte* Auslöseentscheidung
gefahren werden können — mehrere Prüfläufe hintereinander, mit stellbarer Uhr, vorbelegtem
Zustand und Abgriff aller vier Kanäle ohne echten Versand.

## Zentrale Korrektur am Issue-Bild

Das Issue nennt zwei fehlende Bausteine: „Einspeisung in die Auslöseentscheidung" und
„vorbelegbarer Zustand". **Beide existieren bereits** — nur unverbunden und ungesichert.
Der Aufwand liegt woanders.

| Issue sagt | Tatsächlich |
|---|---|
| Einspeisung fehlt | `check_and_send_alerts(trip, cached_weather, fresh_weather, official_notices)` nimmt die Daten als Parameter (`trip_alert.py:216`). Radar-Pfad über `_get_radar_service()` (`trip_alert.py:1100`) per Unterklasse ersetzbar. |
| Vorbelegbarer Zustand fehlt | Alle sechs Zustandsspeicher haben öffentliche Schreibwege (Tabelle unten); `tests/tdd/test_issue_1070_daily_alert_limit.py:643` fährt damit bereits eine echte Mehrlauf-Zeitreihe. |
| Stellbare Uhr „teils vorhanden" | `freezegun` ist etabliert (~30 Testdateien). Was fehlt, ist die Absicherung für *mehrere* Läufe im selben Prozess. |
| Alle vier Kanäle abgreifbar | Nur E-Mail in-process. Telegram/SMS/Premium-SMS brauchen einen lokalen HTTP-Stub, weil `TripAlertService` `sms_sink`/`telegram_sink` nicht durchreicht. |

**Der `alert-preview`-Endpoint aus #1948 S2 ist nicht defekt.** Er ist laut eigener Spec
(`docs/specs/modules/alarm_testeinspeisung.md:20`) und Docstrings bewusst zustandslos und
für den *Textbau* gebaut. S1 repariert ihn nicht, sondern baut daneben.

## Die drei Auslösepfade

Kein gemeinsamer Trichter. `check_all_trips()` (`trip_alert.py:475`) bündelt zwei der drei
Arten in einer Trip-Schleife; Radar läuft als eigener Cron mit eigener Schleife.

| Zweig | Entscheidungspunkt | Naht zum Textbau |
|---|---|---|
| Vorhersage-Abweichung | `check_and_send_alerts()` `trip_alert.py:216-456`, 9 Gate-Stufen | `NotificationService.send_deviation_alert` (`:1727`) |
| Amtliche Warnung | `_send_official_alert_only()` `trip_alert.py:1885-2022` | `send_official_alert` (`:1970`) |
| Radar/Nowcast | inline in `check_radar_alerts()` `trip_alert.py:1140-1623`, 9 Stufen | `send_radar_alert` (`:1546`) |

Geteilte Gate-Bausteine für Trip **und** Ortsvergleich: `src/services/alert_gate.py` —
`check_nowcast_gate:140`, `check_official_alert_gate:187`, `check_briefing_imminent:282`,
`check_event_identity_gate:617`, `record_event_identity:695`.

**Gemeinsames Muster aller drei Pfade:** Zustand wird erst *nach* bestätigter Zustellung
fortgeschrieben (`:430-454`, `:1998-2021`, `:1589-1620`). Ein Szenario muss also zwischen
„entschieden" und „gebucht" unterscheiden können.

## Zustandsspeicher (alle unter `get_data_dir(user_id)`)

| Zustand | Datei | Schreibweg |
|---|---|---|
| Melde-Gedächtnis + amtliches Gedächtnis + Event-Identität | `alert_state/<entity_id>.json` | `AlertStateService.save` (`alert_state.py:73`) |
| Sperrzeit/Cooldown, alle Scopes | `throttle_state.json` | `ThrottleStore.record` (`throttle_store.py:36-90`) |
| Tageszähler | `alert_daily_count.json` | `alert_daily_limit.increment` (`:110`) |
| Briefing-Anker | `briefing_anchor.json` | `record_briefing_sent` (`alert_briefing_anchor.py:192`) |
| Rollierender Δ-Vergleichspunkt | `weather_snapshots/<trip_id>_alarm_anchor_<channel>.json` | `WeatherSnapshotService.save_alarm_anchor` (`:225`) |
| Alarm-Protokoll | `alert_log.json` | `alert_log.append_entry` / `append_suppressed_entry` |

Drei Präfixe teilen sich `alert_state`: blank (Metrik/Segment), `official_alert:`,
`event_identity:`. `reset()` behält **nur** `official_alert:` — jeder andere Präfix fällt
beim Briefing-Reset weg (`alert_state.py:38-45`).

## Zeitsteuerung — der eigentliche Knackpunkt

Kein Entscheidungs-Eintrittspunkt nimmt einen Zeitpunkt entgegen:

- `check_and_send_alerts()` liest „jetzt" in **einem** Lauf mindestens viermal aus drei
  Funktionen (`trip_alert.py:279`, `:999`, `deviation_alert_engine.py:284`, Buchung `:430`/`:440`).
- `check_radar_alerts()` — kein Parameter, fest bei `:1158`.
- `check_official_alert_triggers(trip, now_utc=None)` nimmt einen Zeitpunkt, reicht ihn an
  `_get_cached_weather` (`:1789`) — und **überschreibt ihn dann bedingungslos** bei `:1811`.
  Am Code nachgeprüft. Heute folgenlos (beide Werte liegen Millisekunden auseinander), aber
  eine gestellte Uhr wird hier still verworfen.

Rohe `datetime.now(`-Fundstellen im Alarm-Pfad: `trip_alert.py:279,430,440,500,695,767,823,999,
1027,1158,1415,1604,1619,1646,1811,1900,2000,2020` · `deviation_alert_engine.py:284` ·
`alert_briefing_anchor.py:91,135,207,343` · `alert_log.py:364,462` · `alert_input_capture.py:66,104`.

Sauber injizierbar sind dagegen **alle** `alert_gate.py`-Funktionen (Pflicht-`now`, kein Fallback)
und `radar_service.py:193` (echter `now_fn`-Hook).

**Folgerung:** Ein `now=`-Parameter durchzureichen wäre ein eigener, breiter Umbau mit genau der
Falle, die `:1811` schon zeigt. Für S1 ist `freezegun` pro Lauf der tragfähige Weg.

## Mehrlauf-Risiken (der neue Teil)

1. **Singleton-Caches** überleben den einzelnen Lauf. `tests/conftest.py` setzt sie heute
   *pro Test* zurück: Radar (`:279`), Wetter (`:308`), Thunder-Window (`:294`),
   Telegram-Rate-Limit (`:323`). Innerhalb einer Zeitreihe im selben Test greift das nicht —
   Lauf 2 sähe den Cache von Lauf 1. Vgl. die schon bekannte Lehre aus #2018.
2. **`freeze_time` mehrfach im selben Prozess** ist laut `tests/helpers/wanduhr_matrix.py:12-25`
   riskant, sobald pydantic-v1-Importpfade berührt werden — dort wurde deshalb auf
   Subprozess-Isolation ausgewichen. Für S1 zu klären, ob der Alarmpfad das trifft.
3. **Fixture-Zeitanker folgt der gestellten Uhr.** `FixtureProvider` verankert seine Punkte über
   `datetime.now()` (`src/providers/fixture.py:110`) — unter `freeze_time` also am gestellten Tag.
   Das ist günstig, aber es bindet Szenariodaten an das Zeitfenster.

## Kanal-Abgriff ohne Versand

| Kanal | Weg | Beleg |
|---|---|---|
| E-Mail | `mail_sink`-Callback, in-process | `trip_alert.py:185`, `notification_service.py:906` |
| Telegram | lokaler HTTP-Stub (`TELEGRAM_API_BASE` umgebogen) | `tests/tdd/test_radar_alert_telegram_style.py:65-157` |
| SMS | lokaler HTTP-Stub (`sms_gateway_url`) | `tests/tdd/test_issue_936_sms_stub.py:27,83` |
| Premium-SMS | derselbe Stub, geteilte Basis `seven_io_base.py` | `tests/unit/test_premium_sms_versand.py:71-173` |

`NotificationService` kennt `sms_sink`/`telegram_sink`, `TripAlertService` reicht sie nicht
durch (`PremiumSmsOutput(...)` direkt bei `trip_alert.py:956,1264`). Trifft Anforderung D-1.

## Vorbild-Harness

`tests/tdd/test_952_onset_alert_fidelity.py` (818 Zeilen), von zwei weiteren Testdateien
importiert: `_GuaranteedWetRadar(RadarNowcastService)` als echte Unterklasse statt Mock (`:101`),
`_trip_with_active_segment` (`:150`), `_clean_user` (`:180`), `_SevenStub` (`:187`).
Keine Zeitreihe — das wäre das Neue.

Isolationsfundament: `tests/conftest.py:121` `_isolate_data_root` leitet den Datenbaum pro Test
auf ein temporäres Verzeichnis um und failt, wenn doch in den echten Baum geschrieben wird.

## Provider-Fixtures

`fixtures/openmeteo/{stubai,zillertal,innsbruck}.json` — Auswahl geografisch über `_nearest()`
(`src/providers/fixture.py:98`), umschaltbar über `GZ_TEST_FIXTURE_DIR` (`tests/conftest.py:20`).
Radar: `fixtures/radar/minutely_15.json`. Amtlich: `tests/fixtures/meteoalarm{,_feed}/`.
Szenarioeigene Daten sind also über ein eigenes Fixture-Verzeichnis einspeisbar.

## Risiken

- **Gestubbte Naht verdeckt alles darunter.** Fährt die Prüfstrecke an den Gates vorbei, sind
  ihre grünen Szenarien wertlos — das ist genau der Defekt, den #2050 abstellen will. Muss
  Negativ-AC werden: eine Mutation an einer Gate-Stufe MUSS ein Szenario rot färben.
- **Zustand nur schreiben, nicht lesen.** Ein Szenario, das Zustand vorbelegt, aber nicht
  nachweist, dass die Entscheidung ihn gelesen hat, prüft nichts.
- **Cache-Durchschlag zwischen den Läufen einer Zeitreihe** (s.o.) — würde falsches Grün liefern.
- **`alert_state`-Reset-Asymmetrie**: `reset()` verwirft `event_identity:`-Schlüssel still.
  Ein Szenario über Briefing-Grenzen hinweg muss das berücksichtigen.

## Nicht Teil von S1

Die zwölf Szenarien selbst (S2–S5), die Protokollergänzung (S6), Ortsvergleich-Pendants,
und ein durchgängiger `now=`-Umbau des Alarmpfads.

---

## Analysis (Phase 2, 2026-08-21)

### Type
Feature — neue Test-Infrastruktur, kein Produktivcode-Defekt.

### Entschiedener Ansatz

**Helper-Klasse, keine Fixture-Familie.** Fixtures sind pro Test gebunden; gebraucht wird ein
Objekt, das *innerhalb* eines Tests mehrfach „Lauf" macht und Historie hält.

`TripAlertService` wird **pro Lauf neu gebaut** — genau wie in Produktion, wo jeder Cron-Tick
eine frische Instanz erzeugt. Die Kontinuität kommt vom Datenträger unter `get_data_dir(user_id)`,
nicht vom Python-Objekt. Das macht die Strecke treuer zur echten Auslösung, nicht nur bequemer.

| Datei | Aktion | LoC |
|---|---|---|
| `tests/helpers/alarm_pruefstrecke.py` | CREATE | ~190 |
| `tests/tdd/test_2050_s1_alarm_pruefstrecke_selbstschutz.py` | CREATE | ~110 |

Kern: `AlarmPruefstrecke.lauf(at=..., zweig="deviation"|"official"|"radar", ...)` →
Cache-Reset → `freeze_time(at)` → frische `TripAlertService` → passender Einstiegspunkt →
`AlarmPruefstreckeLauf(triggered_count, mail, telegram, sms, premium_sms)`.

### Empirisch geklärt (nicht vermutet)

- **Mehrfaches `freeze_time` im selben Prozess trägt.** Gemessen 2026-08-21 auf `b423c913`:
  drei aufeinanderfolgende Fenster (14:00 / 14:30 / 23:50 UTC) nach Import von `trip_alert`
  und `DeviationAlertEngine`, alle drei liefern die gestellte Zeit. Der in
  `wanduhr_matrix.py:11-21` beschriebene Risikofall betrifft *sitzungsweites* Einfrieren **vor**
  den Pydantic-v1-Importen — nicht kurze Einzelläufe nach der Testsammlung.
  **Folge: keine Subprozess-Isolation nötig.**
  Abgrenzung: gemessen ist die Prozess-Verträglichkeit, nicht ein vollständiger
  `check_and_send_alerts`-Lauf unter Freeze. Den deckt Schritt 1 der Reihenfolge ab.
- **Die vier Cache-Resets sind aufrufbare Funktionen**, nicht nur Fixtures — am Quellcode
  bestätigt: `radar_cache.py:136`, `weather_cache.py:319`, `thunder_window_cache.py:166`,
  `telegram.py:650`. Die autouse-Fixtures greifen nur einmal pro Test; der Harness ruft sie
  zu Beginn **jedes Laufs** selbst. Kein neuer Reset-Code nötig.

### Kanal-Abgriff: HTTP-Stub für alle drei Nicht-Mail-Kanäle

Trade-off: Sinks durchreichen wäre leichtgewichtiger pro Lauf, verlangt aber eine neue
Produktivcode-Naht allein für den Test — Premium-SMS hat **gar keinen** Sink-Parameter
(`PremiumSmsOutput(...)` steht unbedingt bei `notification_service.py:956,1264`).
**Entscheidung: lokaler HTTP-Stub**, E-Mail bleibt `mail_sink` in-process. Bei einer Strecke,
die die echte Entscheidung ungeschminkt zeigen soll, wiegt „null Produktivcode-Änderung"
schwerer als der Server-Start pro Lauf.

### Selbstschutz — Kern der Scheibe, nicht Beiwerk

Ein Meta-Test sperrt je Zweig einen echten Gate-Baustein per `monkeypatch.setattr` auf dem
Modul (etabliertes Muster, kein Mock) und verlangt danach `triggered_count == 0` und leere
Kanal-Listen. Läuft die Strecke trotz erzwungener Sperre durch, ist sie an der Entscheidung
vorbeigefahren — **das muss rot werden**. Ohne diesen Nachweis produziert die Prüfstrecke
genau das wertlose Grün, das #2050 abstellen will.

### Reihenfolge

1. Cache-Reset + Mehrlauf-Smoke (blockiert alles andere, wenn falsch)
2. Harness nur Deviation-Zweig, nur `mail_sink`, gegen ein bekanntes Szenario aus `test_952`
3. Selbstschutz-Meta-Test für Deviation — grün/rot verifiziert, **bevor** mehr draufkommt
4. Radar- und Amtlich-Zweig samt Gegenproben
5. Telegram/SMS/Premium-SMS-Stubs

### Scope

~300 LoC, über dem 250-Limit. **Keine künstliche Teilung**: eine Prüfstrecke ohne ihren eigenen
Bypass-Nachweis ist der Defekt, den die Scheibe abstellen soll. `loc_limit_override 500` zu
Beginn setzen.

Risk Level: **LOW** für Produktion (kein Produktivcode geändert), **MEDIUM** für die Scheibe
selbst (falsches Grün wäre schlimmer als kein Test).

### Harness-Grenzen (dokumentieren, nicht lösen)

- `alert_state.reset()` verwirft `event_identity:`-Schlüssel still (`alert_state.py:38-45`) —
  Szenarien über eine Briefing-Grenze verlieren Vorbelegung unbemerkt. Sache von S2+.
- Premium-SMS teilt die Stub-Basis mit SMS (`seven_io_base.py`) → zwei Ports nötig, sonst
  überschreiben sich die Empfangslisten.
- `check_official_alert_triggers(now_utc=...)` verwirft den Parameter (`trip_alert.py:1811`).
  Der Harness bietet `now_utc=` deshalb **gar nicht** als Steuerweg an — sonst suggeriert er
  eine Wirkung, die es nicht gibt. Steuerung ausschließlich über die gestellte Uhr.

### Open Questions
Keine offenen technischen Fragen. Die Spec kann geschrieben werden.
