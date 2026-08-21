---
entity_id: alarm_pruefstrecke
type: feature
created: 2026-08-21
updated: 2026-08-21
status: approved
workflow: feat-2050-s1-pruefstrecke
version: "1.0"
tags: [alarm, testing, harness]
---

# Alarm-Prüfstrecke (Scheibe S1, Issue #2050)

## Approval

- [x] Approved — PO ("go"), 2026-08-21

## Purpose

Alarm-Szenarien lassen sich heute nicht als **Zeitreihe mit Gedächtnis** gegen die *echte*
Auslöseentscheidung fahren — es gibt keinen wiederverwendbaren Harness, der mehrere Prüfläufe
hintereinander mit stellbarer Uhr, vorbelegtem Zustand und Abgriff aller vier Kanäle ohne echten
Versand durchführt. Diese Scheibe baut genau diese Strecke (`AlarmPruefstrecke`) samt ihrem
eigenen Selbstschutz-Nachweis. Sie ersetzt NICHT den zustandslosen `alert-preview`-Endpoint aus
#1948 S2 (`docs/specs/modules/alarm_testeinspeisung.md`) — der bleibt für den Textbau zuständig,
diese Scheibe für die Auslöseentscheidung selbst. Die zwölf Alarm-Szenarien, die auf dieser
Strecke laufen sollen, sind spätere Scheiben (S2–S5) und nicht Teil dieser Spec.

## Source

- **File:** `tests/helpers/alarm_pruefstrecke.py` (neu), `tests/tdd/test_alarm_pruefstrecke_selbstschutz.py` (neu)
- **Identifier:** `AlarmPruefstrecke`, `AlarmPruefstreckeLauf`

> Schicht: Python-Core-Testinfrastruktur (`tests/helpers/`, `tests/tdd/`) — kein Produktivcode
> in `src/`/`api/` wird geändert, kein Go-/Frontend-Anteil.

## Estimated Scope

- **LoC:** ~300 (Helper ~190, Selbstschutz-Test ~110) — über dem 250-LoC-Standardlimit,
  `loc_limit_override 500` ist bereits gesetzt (Begründung: eine Prüfstrecke ohne ihren eigenen
  Bypass-Nachweis ist der Defekt, den #2050 abstellen soll — künstliche Teilung würde genau den
  Nachweis von der Strecke trennen, die er absichert).
- **Files:** 2 neue Testdateien
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/trip_alert.py::TripAlertService.check_and_send_alerts` (`:216-456`) | method | Deviation-Zweig-Entscheidungspunkt, nimmt `trip, cached_weather, fresh_weather, official_notices` als Parameter |
| `src/services/trip_alert.py::TripAlertService._send_official_alert_only` (`:1885-2022`) | method | Amtlicher Zweig-Entscheidungspunkt |
| `src/services/trip_alert.py::TripAlertService.check_radar_alerts` (`:1140-1623`) | method | Radar/Nowcast-Zweig, Ersetzung des Radar-Providers über `_get_radar_service()` (`:1100`) per echter Unterklasse |
| `src/services/alert_gate.py` | module | Geteilte Gate-Bausteine (`check_nowcast_gate:140`, `check_official_alert_gate:187`, `check_briefing_imminent:282`, `check_event_identity_gate:617`, `record_event_identity:695`) — Ziel der Selbstschutz-Sperren |
| Vier Cache-Reset-Funktionen: `services/radar_cache.py:136`, `services/weather_cache.py:319`, `services/thunder_window_cache.py:166`, `output/channels/telegram.py:650` | function | Zu Beginn jedes Laufs aufgerufen, um Mehrlauf-Cache-Durchschlag auszuschließen |
| `tests/tdd/test_952_onset_alert_fidelity.py::_GuaranteedWetRadar` (`:101`) | class | Vorbild-Muster: echte `RadarNowcastService`-Unterklasse als DI-Seam statt Mock |
| `tests/tdd/test_issue_1070_daily_alert_limit.py:643` | test | Bestehender Beleg, dass Mehrlauf-Zeitreihen über die vorhandenen Zustandsspeicher bereits funktionieren |
| `freezegun` | library | Zeitsteuerung pro Lauf; etabliert in ~30 Testdateien des Projekts |
| `app.loader::get_data_dir` | function | Ort aller sechs Zustandsspeicher, pro Test durch `tests/conftest.py:121` (`_isolate_data_root`) isoliert |

## Implementation Details

### `AlarmPruefstrecke.lauf(...)` — ein Prüflauf

```
AlarmPruefstrecke.lauf(
    at: datetime,                       # gestellte Uhrzeit, per freeze_time
    zweig: Literal["deviation", "official", "radar"],
    trip: Trip,
    ...zweigspezifische Eingabedaten (cached_weather/fresh_weather/official_notices
        für "deviation", official_notices für "official", Frames/Provider für "radar"),
) -> AlarmPruefstreckeLauf
```

**Pfadauflösung:** `test_alarm_pruefstrecke_selbstschutz.py` importiert `AlarmPruefstrecke` und
alle Produktivmodule (`src/services/...`) relativ zur eigenen Testdatei bzw. über den regulären
`sys.path`/`conftest.py`-Mechanismus der Testsuite — nie über einen fest eingetragenen
Hauptrepo-Pfad. Sonst prüft ein Lauf aus diesem Worktree den Code eines anderen Checkouts und
liefert falsches Grün.

Ablauf je Lauf:

1. Vier Cache-Resets aufrufen (Radar, Wetter, Thunder-Window, Telegram-Rate-Limit) — jeder Lauf
   startet mit leeren Singleton-Caches, unabhängig davon, was ein vorheriger Lauf im selben Test
   gefüllt hat.
2. `freeze_time(at)` setzen.
3. Frische `TripAlertService`-Instanz bauen (kein Wiederverwenden über Läufe hinweg — Kontinuität
   kommt ausschließlich vom Datenträger unter `get_data_dir(user_id)`, genau wie in Produktion,
   wo jeder Cron-Tick eine neue Instanz erzeugt).
4. Den zum `zweig` passenden Entscheidungs-Einstiegspunkt real aufrufen.
5. Ergebnis in `AlarmPruefstreckeLauf(triggered_count, mail, telegram, sms, premium_sms)`
   einsammeln.

`now_utc=` wird **bewusst nicht** als Steuerparameter angeboten: `check_official_alert_triggers`
nimmt zwar `now_utc` entgegen, verwirft ihn aber bedingungslos bei `trip_alert.py:1811` und liest
stattdessen selbst `datetime.now()`. Einen Parameter anzubieten, den der Produktivcode ignoriert,
würde eine Wirkung suggerieren, die es nicht gibt. Einzige Zeitsteuerung ist die gestellte Uhr
(`freeze_time`).

### Kanal-Abgriff ohne echten Versand

- **E-Mail:** `mail_sink`-Callback, in-process (`trip_alert.py:185`, `notification_service.py:906`).
- **Telegram, SMS, Premium-SMS:** lokale HTTP-Stub-Server, analog
  `tests/tdd/test_radar_alert_telegram_style.py:65-157` (Telegram) und
  `tests/tdd/test_issue_936_sms_stub.py:27,83` (SMS). Premium-SMS teilt die Stub-Basis mit SMS
  (`services/seven_io_base.py`) — die Strecke muss dafür **zwei getrennte Ports** verwenden, sonst
  überschreiben sich die beiden Empfangslisten.

Kein Produktivcode wird geändert: `TripAlertService` reicht `sms_sink`/`telegram_sink` nicht
durch (`PremiumSmsOutput(...)` steht unbedingt bei `trip_alert.py:956,1264`), daher HTTP-Stub statt
Sink-Parameter für alle drei Nicht-Mail-Kanäle.

### Zustand vorbelegen und lesen

Alle sechs Zustandsspeicher (Melde-/amtliches Gedächtnis + Event-Identität in
`alert_state/<entity_id>.json`, Cooldown in `throttle_state.json`, Tageszähler in
`alert_daily_count.json`, Briefing-Anker in `briefing_anchor.json`, Δ-Vergleichspunkt in
`weather_snapshots/...`, Alarm-Protokoll in `alert_log.json`) haben bereits öffentliche
Schreibwege (`AlertStateService.save`, `ThrottleStore.record`, `alert_daily_limit.increment`,
`record_briefing_sent`, `WeatherSnapshotService.save_alarm_anchor`, `alert_log.append_entry`).
Die Prüfstrecke ruft diese Schreibwege vor einem Lauf auf, um Zustand vorzubelegen, und weist
danach über eine beobachtbare Wirkung nach, dass die Entscheidung den vorbelegten Zustand
tatsächlich gelesen hat (z. B. Cooldown-Vorbelegung ⇒ Lauf löst NICHT aus, obwohl die
Eingangsdaten dafür sprächen).

## Expected Behavior

- **Input:** ein `Trip`-Fixture, ein `zweig`, eine gestellte Uhrzeit, zweigspezifische
  Eingangsdaten (Wetteränderungen/amtliche Meldungen/Radar-Frames), optional vorbelegter Zustand.
- **Output:** `AlarmPruefstreckeLauf` mit Auslösezähler und den vier Kanal-Ausgaben (leer, wenn
  nichts ausgelöst wurde).
- **Side effects:** reale Schreibvorgänge in die sechs Zustandsspeicher unter dem pro-Test
  isolierten `get_data_dir(user_id)` (durch `_isolate_data_root` isoliert) — kein echter
  Mail-/SMS-/Telegram-Versand, keine Persistenz außerhalb des Test-Datenbaums.

## Acceptance Criteria

- **AC-1:** Given zwei aufeinanderfolgende Läufe derselben Prüfstrecke für denselben Trip und
  Zweig, wobei der erste Lauf eine Auslösung bucht, When der zweite Lauf mit frisch gebauter
  `TripAlertService`-Instanz gestartet wird, Then liest der zweite Lauf nachweislich den vom
  ersten Lauf geschriebenen Zustand (z. B. greift ein Cooldown, der erst durch den ersten Lauf
  entstanden ist).
  - Test: Lauf 1 löst aus und bucht Cooldown/Alert-State; Lauf 2 mit identischen
    Eingangsdaten prüfen — `triggered_count == 0` wegen des gebuchten Zustands, nicht wegen
    unveränderter Eingangsdaten.

- **AC-2:** Given derselbe Prüflauf (identische Eingangsdaten, identischer Zweig) wird einmal mit
  gestellter Uhr zu einem Zeitpunkt innerhalb und einmal zu einem Zeitpunkt außerhalb eines
  zeitabhängigen Gates (z. B. Nachtruhe/Briefing-Fenster) ausgeführt, When beide Läufe verglichen
  werden, Then treffen sie nachweislich unterschiedliche Auslöseentscheidungen (`triggered_count`
  unterscheidet sich zwischen den beiden gestellten Zeitpunkten).
  - Test: zwei Läufe mit `freeze_time` auf zwei verschiedene, gate-relevante Uhrzeiten,
    `triggered_count` beider Läufe vergleichen und Ungleichheit nachweisen.

- **AC-3:** Given Lauf 1 füllt einen der vier Singleton-Caches (Radar, Wetter, Thunder-Window,
  Telegram-Rate-Limit) mit Daten, die eine Auslösung in Lauf 2 verfälschen würden, When Lauf 2
  über dieselbe Prüfstrecke im selben Testprozess gestartet wird, Then sieht Lauf 2 nachweislich
  nicht die Cache-Daten von Lauf 1 (Entscheidung von Lauf 2 hängt ausschließlich von seinen
  eigenen Eingangsdaten ab, nicht von denen aus Lauf 1).
  - Test: Lauf 1 mit Eingangsdaten füttern, die (ohne Reset) den Cache so besetzen würden, dass
    Lauf 2 fälschlich auslöst oder fälschlich nicht auslöst; Lauf 2 mit neutralen Eingangsdaten
    fahren und das cache-unabhängige Ergebnis nachweisen.

- **AC-4:** Given der Briefing-Nähe-Gate-Baustein des Deviation-Zweigs
  (`alert_gate.check_briefing_imminent`) wird per `monkeypatch.setattr` auf dem Modul erzwungen
  gesperrt (liefert immer "nicht senden"), When ein Prüflauf mit Eingangsdaten gefahren wird, die
  ohne die Sperre eine Auslösung erzeugen würden, Then liefert der Lauf `triggered_count == 0`
  und leere Kanal-Listen für alle vier Kanäle.
  - Test: bekanntes Auslöse-Szenario aus `test_952_onset_alert_fidelity.py` als Eingangsdaten
    verwenden, `check_briefing_imminent` sperren (NICHT `check_nowcast_gate` — das ist der
    Radar-Baustein aus AC-6), `triggered_count == 0` und leere
    `mail`/`telegram`/`sms`/`premium_sms` nachweisen.

- **AC-5:** Given der amtliche Zweig-Gate-Baustein (`check_official_alert_gate`) wird per
  `monkeypatch.setattr` auf dem Modul erzwungen gesperrt, When ein Prüflauf mit einer amtlichen
  Warnung gefahren wird, die ohne die Sperre einen Versand auslösen würde, Then liefert der Lauf
  `triggered_count == 0` und leere Kanal-Listen für alle vier Kanäle.
  - Test: amtliche Testmeldung als Eingangsdaten, `check_official_alert_gate` sperren,
    Nullbefund über alle vier Kanäle nachweisen.

- **AC-6:** Given der Radar-Zweig-Gate-Baustein (`check_nowcast_gate`) wird per
  `monkeypatch.setattr` auf dem Modul erzwungen gesperrt, When ein Prüflauf mit
  Nowcast-Frames gefahren wird, die ohne die Sperre einen Onset-Alarm auslösen würden, Then
  liefert der Lauf `triggered_count == 0` und leere Kanal-Listen für alle vier Kanäle.
  - Test: Frames-Fixture mit garantiertem Onset (`_GuaranteedWetRadar`-Muster), Gate sperren,
    Nullbefund über alle vier Kanäle nachweisen.

- **AC-7:** Given ein Prüflauf wird mit vorbelegtem Zustand gestartet, der die Auslöseentscheidung
  in eine bestimmte Richtung zwingen sollte (z. B. vorbelegter Cooldown, der eine sonst fällige
  Auslösung unterdrückt), When der Lauf mit Eingangsdaten gefahren wird, die ohne die Vorbelegung
  auslösen würden, Then zeigt das Ergebnis nachweislich die Wirkung der Vorbelegung
  (`triggered_count == 0` trotz auslösungsfähiger Eingangsdaten) statt lediglich, dass der
  Zustand geschrieben wurde.
  - Test: Cooldown/Alert-State vor dem Lauf direkt über die öffentlichen Schreibwege
    (`ThrottleStore.record`/`AlertStateService.save`) setzen, denselben Lauf ohne Vorbelegung
    zum Vergleich fahren, Ergebnisunterschied nachweisen.

- **AC-8:** Given ein Prüflauf löst über einen der drei Zweige einen Versand über alle vier
  Kanäle aus (E-Mail, Telegram, SMS, Premium-SMS), When der Lauf beendet ist, Then liefert
  `AlarmPruefstreckeLauf` für jeden der vier Kanäle den tatsächlich gerenderten Inhalt, ohne dass
  ein echter externer Versand stattgefunden hat (kein Netzwerkzugriff auf Resend/Telegram-API/
  seven.io außerhalb der lokalen Stubs).
  - Test: Szenario fahren, das alle vier Kanäle bedient; für jeden Kanal Inhalt auf dem
    jeweiligen Abgriffsweg (`mail_sink`, lokale HTTP-Stubs) nachweisen; keine Anfrage an eine
    echte externe URL nachweisen (Stub-Server als einzige Gegenstelle).

## Known Limitations

- `alert_state.reset()` verwirft `event_identity:`-Schlüssel still (`alert_state.py:38-45`) —
  Szenarien, die über eine Briefing-Grenze hinweg vorbelegten Zustand voraussetzen, verlieren
  diese Vorbelegung unbemerkt. Betrifft S2+, nicht diese Scheibe.
- Premium-SMS teilt die Stub-Basis mit SMS (`services/seven_io_base.py`) → die Strecke braucht
  zwei getrennte Ports, sonst überschreiben sich die beiden Empfangslisten.
- `check_official_alert_triggers(now_utc=...)` verwirft den übergebenen Parameter
  (`trip_alert.py:1811`). Die Prüfstrecke bietet `now_utc=` deshalb **gar nicht** als Steuerweg
  an — sonst würde sie eine Wirkung suggerieren, die es nicht gibt. Zeitsteuerung ausschließlich
  über die gestellte Uhr (`freeze_time`).

## Nicht Ziel

- Die zwölf Alarm-Szenarien selbst (Scheiben S2–S5 aus #2050).
- Die Protokollergänzung (Scheibe S6 aus #2050).
- Ortsvergleich-Pendants der Prüfstrecke.
- Ein durchgängiger `now=`-Umbau des Alarmpfads (alle rohen `datetime.now(`-Fundstellen in
  `trip_alert.py`, `deviation_alert_engine.py`, `alert_briefing_anchor.py`, `alert_log.py`,
  `alert_input_capture.py` bleiben unangetastet).
- Jede Änderung am `alert-preview`-Endpoint aus #1948 S2
  (`docs/specs/modules/alarm_testeinspeisung.md`) — der bleibt zustandslos für den Textbau.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Test-Infrastruktur ohne Produktivcode-Änderung, keine neue Route, kein
  neues Datenmodell, keine Rücknahme einer bestehenden Architekturentscheidung. Kein
  ADR-würdiger Grundsatzentscheid.

## Changelog

- 2026-08-21: Initial spec created (Scheibe S1 aus #2050, verdichtet aus
  `docs/context/feat-2050-s1-pruefstrecke.md`).
- 2026-08-21: Testdateiname korrigiert (`test_alarm_pruefstrecke_selbstschutz.py` statt
  Issue-Nummer im Namen, CLAUDE.md-Regel „Testdateien nach Verhalten benennen"), Pfadauflösung
  relativ zur Testdatei ergänzt, AC-4 auf reines Beobachtungsergebnis umformuliert.
