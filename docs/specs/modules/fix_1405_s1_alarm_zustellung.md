---
entity_id: fix_1405_s1_alarm_zustellung
type: module
created: 2026-10-09
updated: 2026-10-09
status: draft
version: "1.0"
tags: [alarm, zustellung, erfolg-heisst-wirkung, backoff, kommando-report, issue-1405, epic-2505]
---

<!-- Issue #1405 Scheibe 1 (Wächter 2, "Erfolg heißt Wirkung"), Epic #2505 Versand-Zuverlässigkeit.
     Entscheidung: ADR-0086. Kontext: docs/context/fix-1405-s1-alarm-zustellung.md -->

# Alarm-Erfolg heißt Zustellung — Scheibe 1

## Approval

- [ ] Approved

## Purpose

Heute meldet der Alarm-Versand "gesendet", sobald ein Kanal **betreten** wurde — auch dann,
wenn jeder Transport (E-Mail, Telegram, SMS, Premium-SMS) scheitert. Alle sechs Alarm-Aufrufer
(Trip und Ortsvergleich) buchen daraufhin den Alarm als erledigt (Zustand, Sperrzeit,
Tageskontingent, Ereignis-Identität) und wiederholen ihn nie: ein komplett gescheiterter Alarm
geht still verloren. Diese Scheibe macht "gesendet" zu dem, was das Wort sagt — mindestens ein
Kanal hat wirklich zugestellt —, ersetzt die Folge "nie wieder versuchen" durch eine
**begrenzte Wiederholung** (höchstens ein Versuch je 30 Minuten je Ereignis) und behebt im
selben Zug das Kommando "report", das dem Nutzer auch bei Fehlschlag "Report gesendet"
antwortet (B15). Sie löst #684 AC-3 ab und präzisiert #1459 D4 (v1.4) sowie #1701 D7
(**ADR-0086**); sie setzt ADR-0021 ("Buchung nur nach erfolgreicher Zustellung") um.

**Alle vier Kanäle sind gleichrangig:** jede Regel unten gilt für E-Mail, Telegram, SMS und
Premium-SMS gleichermaßen.

## Source

- **Files (Python-Core, `src/services/`, `api/`):**
  `src/services/notification_service.py`, `src/services/trip_alert.py`,
  `src/services/compare_alert.py`, `src/services/compare_radar_alert.py`,
  `src/services/compare_official_alert.py`, `src/services/trip_command_processor.py`,
  `api/routers/scheduler.py`, `tests/test_success_status_guard.py` (Wächter-Pflege)
- **Identifier:** `NotificationResult` (+ neues Feld `attempted_channels`, neue Property
  `delivery_outcome`), `send_official_alert`, `_dispatch_alert_message`,
  `send_multi_location_official_alert`, `_trigger_report`, `_trigger_on_demand`,
  `send_test_trip_report`
- Kein Frontend, keine Go-API-Änderung. `alert_log.append_entry` und `ThrottleStore`
  bleiben in ihrer Schnittstelle unverändert (Backoff = zusätzlicher Scope im bestehenden Store).

## Estimated Scope

- **LoC:** produktiv ~250–350, Tests ~300–400 ⇒ **`workflow.py set-field loc_limit_override 500`**
  ist vorgesehen (erwarteter Schritt, nicht abspalten: Parität Trip/Ortsvergleich und B15 gehören dazu)
- **Files:** ~8 produktiv, ~6 Tests, ADR-0086 + Wächter-Spec-Tabelle
- **Effort:** high (zentrale Alarm-Buchungslogik aller Alarmarten)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `EmailOutput`, `TelegramOutput`, `SMSOutput`, `PremiumSmsOutput` | Transport | liefern Erfolg oder werfen — Quelle der Wahrheit für "zugestellt" |
| `_sms_gate_reserve`, `sms_daily_limit` | Gate | Tageslimit-Sperre (bewusst, mit Reason-Code) und Rückgabe der Reservierung bei Fehlschlag |
| `ThrottleStore` (`src/services/throttle_store.py`) | Zustand | Sperrzeit; neu: Fehlversuchs-Backoff mit eigenem Scope `<scope>:retry` |
| `alert_log.append_entry` | Protokoll | `entries`/`not_delivered` über `reachable_channels` (Cockpit-Zahl, #1459 AC-11/AC-15) |
| `record_event_identity`, `record_nowcast_sent`, `alert_daily_limit` | Buchung | nur bei Zustellung bzw. terminaler Sperre |
| `TripReportScheduler.send_test_report_outcome` | Report | liefert das echte Ergebnis für B15 |
| ADR-0086, ADR-0021, #684 AC-3, #1459 D4, #1701 D7 | Entscheidung | siehe Abschnitt ADR |

## Implementation Details

**1. Ergebnisfeld (`NotificationResult`).**
- `sent` = mindestens ein Kanal hat **zugestellt** (`bool(delivered_channels)`).
- `sent_channels` füllt jeder Pfad erst **nach** erfolgreichem Send (Muster `send_trip_report`).
- Neu: `attempted_channels` = Kanäle, die betreten wurden (Gate bestanden, Send versucht),
  eingetragen **nach** dem `try/except`-Block (Erfolg und Fehlschlag), nie davor. Er löst
  `sent_channels` als Quelle für `reachable_channels` ab. Damit ist `reachable` inhaltlich
  identisch mit dem heutigen `sent_channels` ⇒ Cockpit-Zahl unverändert.
- `failed_channels` (Transportfehler) und `blocked_channels`/`blocked_reason_codes`
  (bewusste Sperre) bleiben. `delivered_channels` bleibt Property.
- Neu: Property `delivery_outcome` (abgeleitet, nie gesetzt):

| Bedingung (in dieser Reihenfolge) | Wert |
|---|---|
| mindestens ein Kanal zugestellt | `delivered` |
| nichts zugestellt, mindestens ein Kanal in `failed_channels` (Transportfehler) | `transport_failed` |
| nichts zugestellt, kein Transportfehler, mindestens ein Kanal bewusst gesperrt (Key in `blocked_reason_codes`) | `blocked_only` |
| nichts betreten, nichts gesperrt (kein Kanal konfigurierbar) | `no_channel` |

Unterscheidung Sperre / Transportfehler: **Sperre = Key in `blocked_reason_codes`**,
**Transportfehler = Key in `failed_channels`**. Premium-SMS-Transportfehler steht in
`blocked_channels` OHNE Reason-Code und in `failed_channels` ⇒ Transportfehler. Im
Multi-Location-Pfad landet ein Kanal nur dann in `failed_channels`, wenn der Helfer `False`
liefert UND der Kanal keinen Reason-Code hat (heute: jede Sperre zählt als betreten+gescheitert
und ergibt `sent=True`); `attempted_channels` enthält dort — wie das heutige `sent_channels` —
auch den gesperrten Kanal, damit die Cockpit-Zahl gleich bleibt.

**2. Aufrufer (alle sechs) lesen `delivery_outcome`**, nicht `sent`:
`delivered` ⇒ Buchung wie heute; `blocked_only` ⇒ Buchung (terminal); `transport_failed` ⇒
keine Buchung, Backoff setzen; `no_channel` ⇒ unverändert (Warnung, keine Buchung, kein Backoff).

**3. Backoff.** Vor dem Versand fragt der Aufrufer über einen **geteilten Baustein** (Trip und
Ortsvergleich nutzen denselben Code) im `ThrottleStore` (Scope `<scope>:retry`, Schlüssel =
Ereignis-Fingerabdruck) ab, ob für dieses Ereignis ein Backoff läuft; wenn ja: kein Versand,
kein Protokolleintrag. Bei `transport_failed` setzt der Aufrufer den Backoff (30 Min). Bei
`delivered`/`blocked_only` wird ein evtl. vorhandener Backoff gelöscht.
Ereignis-Fingerabdruck: Trip-Änderungsalarm = Trip-ID + sortierte `metric:segment_id`-Schlüssel;
Radar = Entität + Gefahrenklasse + Zeitfenster; Amtlich = Entität + Meldungs-Kennungen;
Ortsvergleich entsprechend mit Preset-ID und Ort. Ein neues oder anderes Ereignis hat einen
anderen Fingerabdruck und wird vom Backoff eines alten **nicht** berührt.

**4. Wächter 1c.** Der Detektor `_find_pre_try_success_marker_violations` ist namensunabhängig:
jedes nackte `<Name>.append(...)` als Geschwister VOR einem riskanten `try` ist ein Fund. Deshalb
steht `attempted_channels.append` **nach** dem `try`-Block, `sent_channels.append` **im** `try`
nach dem Send. Der Detektor wird nicht verändert.

**5. B15/B16/B1.** `_trigger_report` wertet `send_test_report_outcome` aus; `success` und Text
folgen dem Ergebnis; eine Exception wird gefangen und als Fehlermeldung beantwortet.
`_trigger_on_demand`: `success` aus `outcome` abgeleitet. `send_test_trip_report`:
`"sent": outcome == "sent"`.

## Expected Behavior

- **Input:** Alarm-Auslösung (Änderung, Radar, Amtlich; Trip und Ortsvergleich), Kommando "report".
- **Output:** Zustellung auf allen konfigurierten Kanälen; Buchung nur bei Zustellung oder
  terminaler Sperre; sonst begrenzte Wiederholung. Kommando "report" antwortet mit dem echten Ergebnis.
- **Side effects:** neuer Throttle-Scope `<scope>:retry`; Alarm-Protokoll-Einträge bei Totalausfall
  höchstens einer je Backoff-Fenster statt einer je Lauf.

## Acceptance Criteria

Begriffe (für die Freigabe): **Zugestellt** = der Versandweg (z. B. der Mailserver) hat die
Nachricht angenommen, ohne Fehler zu melden. **Sperre** = der Kanal wurde bewusst nicht benutzt
(z. B. SMS-Tageslimit erreicht). **Transportfehler** = der Versand wurde versucht und ist
gescheitert. **Backoff** = Wartezeit von 30 Minuten, in der derselbe Alarm nicht erneut versucht wird.

### A. Was "gesendet" bedeutet

- **AC-1:** Given ein Alarm, bei dem für den jeweils einzigen konfigurierten Kanal (einzeln geprüft für E-Mail, Telegram, SMS und Premium-SMS) der Transport mit einem Fehler scheitert / When der Alarm versendet wird / Then meldet das Ergebnis "nicht gesendet" (`sent` ist falsch), der Kanal steht nicht unter den zugestellten Kanälen, und das Ergebnis lautet `transport_failed`.
  - Test: echte Output-Klasse gegen lokalen Fake-Server, der Verbindung/Antwort verweigert; je Kanal ein Fall; kein `patch()`.

- **AC-2:** Given ein Alarm mit mindestens einem erfolgreich zugestellten Kanal / When der Alarm versendet wird / Then ist `sent` wahr und das Ergebnis lautet `delivered` — auch dann, wenn ein weiterer Kanal desselben Alarms gescheitert ist (Teilerfolg); der gescheiterte Kanal bleibt in den fehlgeschlagenen Kanälen sichtbar.
  - Test: E-Mail gegen Fake-SMTP (ok) + Telegram gegen Fake-HTTP (Fehler); Ergebnis `delivered`, `failed_channels == ["telegram"]`.

- **AC-3:** Given ein Alarm, bei dem nichts zugestellt wurde, kein Kanal einen Transportfehler hatte und mindestens ein Kanal bewusst gesperrt wurde (z. B. SMS-Tageslimit erreicht, Eintrag in den Sperr-Codes) / When der Alarm versendet wird / Then lautet das Ergebnis `blocked_only`.
  - Test: SMS-Tageslimit ausgeschöpft (echter `sms_daily_limit`-Stand), einziger Kanal SMS.

- **AC-4:** Given ein Alarm, bei dem nichts zugestellt wurde, ein Kanal gesperrt ist **und** ein anderer Kanal einen Transportfehler hatte (Mischfall) / When der Alarm versendet wird / Then lautet das Ergebnis `transport_failed` (nicht `blocked_only`), damit der fehlgeschlagene Kanal erneut versucht wird; der gesperrte Kanal bleibt durch seine Sperre ohnehin gesperrt.
  - Test: SMS gesperrt (Limit) + E-Mail gegen Fake-SMTP mit Fehler.

- **AC-5:** Given Premium-SMS ist konfiguriert und der Transport scheitert (Eintrag in den gesperrten Kanälen ohne Sperr-Code) / When der Alarm versendet wird / Then gilt das als Transportfehler (`transport_failed`, Kanal in den fehlgeschlagenen Kanälen), nicht als Sperre; eine echte Sperre mit Sperr-Code (z. B. Tageslimit, veraltete Rückadresse) gilt dagegen nicht als Transportfehler.
  - Test: `PremiumSmsOutput` gegen Fake-Endpunkt mit Fehler vs. Tageslimit-Sperre; zwei Ergebnisse unterschieden.

- **AC-6:** Given ein Alarm an Telegram, der in mehrere Nachrichten-Blasen zerlegt wird / When mindestens eine Blase zugestellt wird und eine andere scheitert / Then gilt der Kanal Telegram als zugestellt (keine Wiederholung, damit keine Dubletten); die fehlgeschlagene Blase bleibt sichtbar (`telegram_fully_sent` ist falsch). Scheitern alle Blasen, gilt Telegram als Transportfehler.
  - Test: Fake-Telegram-Server, der Blase 2 ablehnt; Kanal `delivered`, `telegram_fully_sent == False`.

- **AC-7:** Given ein Alarm, bei dem kein Kanal konfigurierbar ist (nichts betreten, nichts gesperrt) / When der Alarm versendet wird / Then lautet das Ergebnis `no_channel` und das Verhalten bleibt wie bisher (#684 AC-1/AC-2): keine Buchung, keine Sperrzeit, kein Backoff, Warnung im Log.
  - Test: Trip ohne wirksamen Kanal; Zustand, Sperrzeit und Backoff unverändert.

### B. Was nach dem Versand gebucht wird

- **AC-8:** Given das Ergebnis `delivered` (auch Teilerfolg) / When der Aufrufer den Alarm nachbehandelt / Then wird wie bisher gebucht — Alarm-Zustand, Ereignis-Identität, Sperrzeit, Tageskontingent, bei Radar zusätzlich die Nowcast-Buchung — und der Alarm wird nicht wiederholt (auch nicht auf den gescheiterten Kanälen des Teilerfolgs).
  - Test: Teilerfolg-Lauf, danach zweiter Lauf mit gleicher Lage ⇒ kein zweiter Versand.

- **AC-9:** Given das Ergebnis `blocked_only` / When der Aufrufer den Alarm nachbehandelt / Then wird wie im Sammelpfad bisher gebucht (Zustand, Identität, Sperrzeit, Tageskontingent, Nowcast), und der Alarm wird nicht wiederholt (terminal, kein Versuch gegen dieselbe Sperre alle 30 Minuten).
  - Test: Tageslimit-Sperre, drei Läufe nacheinander ⇒ keine weiteren Versuche, ein Zustand.

- **AC-10:** Given das Ergebnis `transport_failed` / When der Aufrufer den Alarm nachbehandelt / Then wird **nichts** als erledigt gebucht (kein Zustand, keine Identität, keine Sperrzeit, kein Tageskontingent, keine Nowcast-Buchung); stattdessen wird der Backoff für dieses Ereignis gesetzt, und der nächste Lauf nach Ablauf des Backoffs versucht den Alarm erneut.
  - Test: Totalausfall; Zustandsdateien unverändert, Backoff-Eintrag vorhanden; Uhr +31 Min ⇒ erneuter Versuch.

### C. Begrenzung der Wiederholung (Spam-Grenze)

- **AC-11:** Given ein Dauer-Transportausfall und eine anhaltende Abweichung (Trip- und Ortsvergleich-Änderungsalarme enden nicht von selbst) / When die Alarmprüfung im Takt von 5 bzw. 15 Minuten über 30 Minuten mehrfach läuft / Then findet für dasselbe Ereignis höchstens **1 Versuch** und **1 Alarm-Protokoll-Eintrag** je 30 Minuten statt (über 24 Stunden höchstens 48).
  - Test: simulierte Uhr, 6 Läufe à 5 Min bei Dauerausfall ⇒ genau 1 Versand-Versuch, 1 Protokolleintrag; 24-Stunden-Simulation ⇒ höchstens 48.

- **AC-12:** Given für ein Ereignis A läuft ein Backoff / When ein anderes, neues Ereignis B desselben Trips (oder Ortsvergleichs) auftritt (andere Metrik, anderer Abschnitt, andere Gefahrenklasse) / Then wird B sofort versendet und nicht vom Backoff von A blockiert; der Backoff gilt je Ereignis, nicht je Trip.
  - Test: Ereignis A schlägt fehl (Backoff), Ereignis B im nächsten Lauf ⇒ B wird zugestellt und gebucht.

- **AC-13:** Given ein Backoff für ein Ereignis ist abgelaufen und die Transporte funktionieren wieder / When der nächste Lauf den Alarm erneut versucht / Then wird er zugestellt, normal gebucht, der Backoff gelöscht und der Alarm danach nicht mehr wiederholt.
  - Test: Fake-Server fällt aus, wird repariert; Lauf +31 Min ⇒ `delivered`, danach Lauf +62 Min ⇒ kein Versand.

- **AC-14:** Given es gibt **keinen** Versuchsdeckel (kein Zähler, wie bei #1662 abgelehnt) / When die Wiederholung bei Dauerausfall läuft / Then endet sie ausschließlich dadurch, dass das Ereignis entfällt (Warnung abgelaufen, Nowcast-Fenster vorbei, Abweichung verschwunden) oder ein Kanal zustellt; das Restrisiko — bei Dauerausfall bis zu 48 Versuche je Ereignis und Tag, bei mehrdeutigen Fehlschlägen (Timeout nach Annahme durch den Anbieter) bis zu 48 mögliche Dubletten je Tag — ist in Spec und ADR-0086 ausdrücklich benannt.
  - Test: Ereignis entfällt nach Fehlversuchen ⇒ kein weiterer Versuch; "Known Limitations" und ADR-0086 enthalten die Zahlen (`# doc-compliance-test`).

- **AC-15:** Given zwei verschiedene Nutzer, bei Nutzer A läuft ein Backoff für ein Ereignis / When für Nutzer B ein Alarm mit gleicher Trip-/Preset-Bezeichnung ausgelöst wird / Then wird B nicht durch A's Backoff gebremst und seine Daten bleiben getrennt (Mandantentrennung).
  - Test: zwei Nutzer mit identischer Trip-ID, Backoff nur bei A.

- **AC-16:** Given ein SMS- oder Premium-SMS-Versand scheitert / When die Reservierung des Tageskontingents zurückgegeben wird / Then ist das Tageskontingent nach beliebig vielen Fehlversuchen unverändert (ein Fehlversuch verbraucht kein Kontingent), und ein erfolgreicher späterer Versand verbraucht genau einen Platz.
  - Test: drei Fehlversuche, dann Erfolg ⇒ Zähler == 1.

### D. Alarm-Protokoll und Cockpit

- **AC-17:** Given ein Alarm mit zwei konfigurierten Kanälen, von denen einer scheitert / When das Alarm-Protokoll geschrieben wird / Then bleibt die im Cockpit angezeigte Zahl der Protokoll-Einträge so wie bisher (#1459 AC-11): `reachable_channels` wird aus `attempted_channels` gespeist und ist inhaltlich identisch mit dem bisherigen Wert.
  - Test: Cockpit-Zahl vor/nach Änderung für Teilerfolg, Totalausfall und Sperre gleich (umgeschriebener `test_alert_log_channels.py::test_ac11_…`).

- **AC-18:** Given ein Alarm, der konfiguriert war, aber nichts zugestellt hat (Totalausfall) / When das Alarm-Protokoll geschrieben wird / Then steht der Eintrag in `entries` (nicht in `not_delivered`) mit leerer Zugestellt-Liste und `delivery_failed` je Kanal (#1459 AC-15); während des Backoffs entsteht kein weiterer Eintrag.
  - Test: umgeschriebener `test_alert_log_channels.py::test_ac15_…`.

### E. Parität Trip und Ortsvergleich

- **AC-19:** Given die sechs Alarm-Aufrufer `trip_alert.py` (Änderungsalarm, Radar-Alarm, Amtlich-Alarm) und `compare_alert.py`, `compare_radar_alert.py`, `compare_official_alert.py` sowie der Sammelpfad `send_multi_location_official_alert` / When jeweils ein Totalausfall, ein Teilerfolg, eine reine Sperre und ein Ereignis-Wechsel simuliert werden / Then verhalten sich alle sieben identisch nach AC-8 bis AC-13 (gleiche Buchungsregel, gleicher Backoff aus dem geteilten Baustein); insbesondere ergibt eine Tageslimit-Sperre im Sammelpfad nicht mehr "gesendet", sondern `blocked_only`.
  - Test: parametrisierter Test über alle sieben Pfade mit echten Output-Klassen und Fake-Servern.

- **AC-20:** Given die drei Versandpfade `send_official_alert`, `_dispatch_alert_message` und `send_multi_location_official_alert` / When derselbe Ausgang (Totalausfall, Teilerfolg, Sperre) in jedem eintritt / Then liefern alle drei dasselbe `delivery_outcome` und dieselbe `attempted_channels`-Bedeutung (Kanal betreten, unabhängig vom Ausgang).
  - Test: gleiche Eingabe in drei Pfade, gleiche Ausgänge.

### F. Briefings bleiben unberührt

- **AC-21:** Given die Briefing-Pfade `send_trip_report`, `send_compare_report` und der Nachliefer-Pfad in `trip_report_scheduler.py` (ca. Z. 1759–1772), die `sent_channels` bereits als "zugestellt" lesen / When die Änderung ausgeliefert ist / Then verhalten sie sich unverändert (gleiche Ergebnisse, gleiche Buchung, gleiche Nachlieferung bei Fehler).
  - Test: bestehende Briefing-Tests laufen unverändert grün (`test_briefing_anchor_survives_dispatch_failure.py`, `test_alert_state_briefing_reset.py`, Briefing-Modus-Matrix).

### G. Kommando "report" (B15, nutzersichtbar) und formale Funde (B1/B16)

- **AC-22:** Given ein Nutzer sendet das Kommando "report" / When das Ergebnis des Test-Reports `sent`, `no_stage`, `no_weather`, `no_channels`, `channels_unreachable` oder `already_in_progress` ist / Then lautet der Antworttext je Ergebnis anders und sagt "Report gesendet" **nur** bei `sent`; bei allen anderen Ergebnissen nennt er den Grund in Klartext und die Antwort gilt als nicht erfolgreich.
  - Test: sechs Fälle, Antworttext je Fall verschieden; "gesendet" nur im `sent`-Fall.

- **AC-23:** Given das Kommando "report" löst beim Auslösen eine Ausnahme aus / When die Antwort erzeugt wird / Then erhält der Nutzer eine Fehlermeldung statt "Report gesendet", und der Befehlsablauf stürzt nicht ab.
  - Test: Auslöser, der wirft; Antwort enthält Fehlermeldung, kein "gesendet".

- **AC-24:** Given das Kommando "report" über jeden der drei echten Eingänge (E-Mail-Eingang `inbound_email_reader`, Telegram-Eingang `InboundTelegramReader`, SMS-Eingang `inbound_sms_reader`) und zwei verschiedene Nutzer mit je eigenem Trip / When beide das Kommando senden und das Ergebnis bei Nutzer A `sent`, bei Nutzer B `no_channels` ist / Then erhält jeder Nutzer die zu seinem eigenen Ergebnis passende Antwort über den Kanal, über den er gefragt hat, und keiner sieht Daten des anderen.
  - Test: `tests/tdd/test_report_kommando_meldet_echtes_ergebnis.py`, Kommando durch den echten Eingang, nicht durch direkten Aufruf von `_trigger_report`.

- **AC-25:** Given der Endpunkt `send_test_trip_report` und die Funktion `_trigger_on_demand` / When ihre Antwort ein Erfolgskennzeichen trägt / Then ist dieses aus dem tatsächlichen Ergebnis abgeleitet (`"sent": outcome == "sent"` bzw. `success` aus `outcome`) und nicht mehr als fester Wert geschrieben; Antworttext und Statuscodes bleiben unverändert.
  - Test: Antwort für `sent` und für `no_channels` ergibt unterschiedliche Kennzeichen; bestehende Endpunkt-Tests grün.

### H. Wächter und Alt-Tests

- **AC-26:** Given der Wächter `tests/test_success_status_guard.py` / When die Änderung ausgeliefert ist / Then sind die Einträge B14a (4), B14c (4), B1, B15 und B16 aus `KNOWN_VIOLATIONS` und `SPEC_LISTED_FINDINGS` entfernt (Ordinale der Restzeilen nachgezogen), die harten Zahlen im Zähltest lauten **21 Schlüssel / Summe 24** (vorher 26/35), die Tabelle in `docs/specs/modules/waechter_1405_erfolg_wirkung.md` (Zeilen ~427–433) ist mitgezogen, und der Wächter-Test ist grün, ohne dass ein Detektor gelockert wurde.
  - Test: `uv run pytest tests/test_success_status_guard.py` grün; Rückdreh-Gegenprobe (`sent_channels.append` wieder vor das `try`) macht den Wächter rot.

- **AC-27:** Given der Detektor 1c zählt jedes nackte `<Name>.append(...)` vor einem riskanten `try` (unabhängig vom Namen) / When `attempted_channels` befüllt wird / Then steht dessen `append` **nach** dem `try/except`-Block (nicht davor) und löst keinen 1c-Fund aus; eine synthetische Datei mit `attempted_channels.append` vor dem `try` bleibt ein Fund (Detektor nicht verändert).
  - Test: synthetische Dateien beider Reihenfolgen gegen `_find_pre_try_success_marker_violations`.

- **AC-28:** Given die bisherigen Tests, die "Totalausfall gilt als gesendet" festschreiben / When die Änderung ausgeliefert ist / Then sind sie bewusst umgeschrieben (nicht gelöscht, nicht abgeschwächt): `tests/tdd/test_issue_684_alert_email_guard.py::test_ac3_configured_smtp_transient_failure_still_records` (neu: Totalausfall ⇒ `sent=False`, kein Zustand, Backoff gesetzt), `tests/tdd/test_914_slice4_alert_sms_dispatch.py::test_ac3_sms_http_error_logged_email_still_delivers` (neu: Totalausfall ⇒ falsch, Teilerfolg ⇒ wahr), `tests/tdd/test_alert_log_channels.py::test_ac15_…` und `::test_ac11_…` (Eingabe auf `attempted_channels`, Aussage bleibt) sowie die indirekt betroffenen `test_alarm_pruefstrecke_selbstschutz.py` (~Z. 263) und `test_radar_convective_check_failure.py` (~Z. 230); jede Änderung trägt einen Kommentar mit Verweis auf ADR-0086.
  - Test: alle genannten Dateien grün; `git diff` zeigt je Test die Begründung.

## Alt-Tests (bewusst umgeschrieben)

| Test | Alte Zusicherung | Neue Zusicherung | Grund |
|---|---|---|---|
| `test_issue_684_alert_email_guard.py::test_ac3_configured_smtp_transient_failure_still_records` | transienter SMTP-Fehler ⇒ `True`, Sperrzeit + Log gesetzt | Totalausfall ⇒ `sent=False`, Zustand/Sperrzeit ungebucht, Backoff gesetzt, Log-Eintrag vorhanden | #684 AC-3 durch ADR-0086 abgelöst; Spam-Sorge wird durch den Backoff (AC-11) gelöst |
| `test_914_slice4_alert_sms_dispatch.py::test_ac3_sms_http_error_logged_email_still_delivers` | SMS-Fehler ⇒ E-Mail liefert trotzdem, Ergebnis wahr | zusätzlich: Totalausfall (SMS-Fehler allein) ⇒ falsch; Teilerfolg ⇒ wahr | Der Test deckte faktisch "Totalausfall = wahr" ab (Cockpit-Begründung #1459 v1.4) |
| `test_alert_log_channels.py::test_ac15_…`, `::test_ac11_…` | Eingabe über `sent_channels` ("betreten") | Eingabe über `attempted_channels`; AC-11/AC-15 unverändert | `sent_channels` bedeutet jetzt "zugestellt" |
| `test_alarm_pruefstrecke_selbstschutz.py` (~263), `test_radar_convective_check_failure.py` (~230) | gehen vom alten `sent`-Begriff aus | an `delivery_outcome` angepasst | indirekt betroffen; Prüfung im RED-Schritt |

Weitere Fixture-Nutzer, im RED-Schritt zu prüfen: `tests/helpers/alert_log_fixtures.py`,
`test_alert_channel_anchor_delivery.py`, `test_alert_state_briefing_reset.py`,
`test_briefing_anchor_survives_dispatch_failure.py`.

## Geplante neue Tests (nach Verhalten benannt)

- `tests/tdd/test_alarm_totalausfall_wird_wiederholt.py` — AC-1 bis AC-20: Totalausfall/Teilerfolg/Sperre/Mischfall, Backoff, Ereignis-Wechsel, Mandantentrennung, Parität über alle sieben Pfade. Echte Output-Klassen gegen lokale Fake-SMTP-/HTTP-Server mit kontrollierten Fehlern; keine `patch()`-Spiegel.
- `tests/tdd/test_report_kommando_meldet_echtes_ergebnis.py` — AC-22 bis AC-25 durch die echten Eingänge, zwei Nutzer.
- Ergänzung `tests/test_success_status_guard.py` — AC-26/AC-27 (Zahlen, synthetische Gegenprobe).

## Known Limitations

- **Restrisiko Dauerausfall:** ohne Versuchsdeckel bis zu 48 Versuche je Ereignis und Tag (alle 30 Min). Nutzerseitig kommt bei echtem Totalausfall nichts an; belastet sind nur Logs und das Alarm-Protokoll (je ein Eintrag je Versuch).
- **Restrisiko mehrdeutige Fehlschläge:** SMTP-Timeout nach DATA, Telegram-ReadTimeout nach Annahme, SMS-Timeout nach Annahme — der Alarm kann real angekommen sein und wird nach 30 Min erneut versendet: bis zu 48 mögliche Dubletten je Tag und Ereignis. Beim SMS-Timeout wird zusätzlich die Reservierung zurückgegeben, das Tageskontingent wird dann unterzählt. Bewusste Abwägung ADR-0086: ein verlorener Alarm wiegt schwerer als eine Dublette.
- **Verzögerung:** Ein nach Totalausfall wiederholter Radar-Alarm kommt frühestens nach 30 Minuten erneut (der 5-Minuten-Takt prüft, versendet aber erst nach Ablauf des Backoffs).
- Der Ereignis-Fingerabdruck unterscheidet nach Metrik/Abschnitt/Gefahrenklasse, nicht nach Zahlenwert: ändert sich nur der Wert derselben Metrik, gilt das Ereignis als dasselbe.
- **Verhaltensänderung im Trip-Pfad:** eine reine Sperre (alle Kanäle durch Tageslimit gesperrt) wurde dort bisher nicht gebucht und jeden Lauf neu geprüft; sie wird jetzt (wie im Sammelpfad bisher) terminal gebucht (AC-9).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0086 (`docs/adr/0086-alarm-erfolg-heisst-zustellung.md`)
- **Rationale:** Löst die dokumentierte Gegenentscheidung #684 AC-3 ab, präzisiert #1459 D4 (v1.4)
  und #1701 D7 und setzt ADR-0021 um; eine dokumentierte Entscheidung wird nie still
  rückgängig gemacht.

## Changelog

- 2026-10-09: Initial spec created (v1.0), Issue #1405 Scheibe 1
