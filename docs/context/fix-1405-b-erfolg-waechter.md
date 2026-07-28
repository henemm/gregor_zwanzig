# Context: fix-1405-b-erfolg-waechter

Issue: [#1405](https://github.com/henemm/gregor_zwanzig/issues/1405) — Wächter 2 von 5
Scheibe: **Hälfte B — „Erfolg heißt Wirkung"**. Hälfte A („Was hineingeht, kommt heraus")
ist seit `0627612d` live. PO-Zuschnitt 2026-07-28: die beiden Hälften laufen nacheinander
als eigene Arbeitseinheiten.

## Request Summary

Zielbild-Satz 2 aus #1405: *Ein `ok`/`sent`/`success` wird aus dem tatsächlichen Ergebnis
abgeleitet, nie konstant gesetzt. Teilerfolg meldet Teilerfolg.* Belegte Vorfälle: #1290
(Scheduler meldet ok, obwohl alle Presets scheitern), #1346 (stiller Totalausfall meldet
Erfolg), #1348, #1403 (Sende-Endpunkt meldet `sent: true` ohne Zustellung).

Diese Einheit baut den Wächter und nimmt die Restliste auf. **Kein Produktivcode** —
Reparatur ist S4.

## Leitbefund: die Norm existiert im Bestand

Wie bei Hälfte A muss nichts erfunden werden. `src/services/dispatch_orchestrator.py:157`
`run_briefing_dispatch()` ist die durchsetzbare Hausnorm, und beide Vorbild-Endpunkte
laufen durch sie:

```python
# api/routers/scheduler.py:42-44 und :142-144 — identisches Muster
sent, failed = service.send_reports_for_hour(current_hour)
status = "partial" if failed > 0 else "ok"
return {"status": status, "count": sent, "failed": failed}
```

```python
# TripDispatchStrategy.dispatch_one, dispatch_orchestrator.py:65-77
try:
    outcome = self._service._send_trip_report_outcome(trip, report_type)
    if outcome == "no_weather":
        self._failed += 1          # genuiner Fehlausgang zählt als Fehler
    else:
        self._sent += 1
except Exception as e:
    self._failed += 1
    logger.error(...)
```

**Die Norm in einem Satz:** Zähl-Tupel `(sent, failed)` aus einer Schleife mit
Fehler-Isolierung; der Status ist reine Ableitung aus `failed > 0`, nie ein Literal. Die
Schleife bricht bei Einzelfehlern nicht ab (Isolierung bleibt), aber der Fehler wird
gezählt und nach oben durchgereicht.

**B9–B12 und B11b/B11c haben nur die halbe Norm:** Fehler-Isolierung ja, Fehlerzähler
nein. Genau diese Hälfte fehlt.

Zweites Positivbeispiel: `src/services/channel_test_service.py:send_test_message()` —
`{"status": "ok"}` nur, wenn `output.send()` ohne Ausnahme durchläuft, sonst
`{"error": ...}`.

## Restliste (verifiziert gegen `0627612d`)

### Klasse 1 — konstanter Erfolgswert

| # | Stelle | Funktion | Befund |
|---|---|---|---|
| B1 | `api/routers/scheduler.py:217` | `send_test_trip_report` | **Der #1403-Fall.** `send_test_report_outcome()` liefert laut `trip_report_scheduler.py:974` auch `"no_channels"` (`return "no_channels" if result.no_channel_configured else "sent"`). Der Router prüft nur `"no_stage"` (Z. 202) und `"no_weather"` (Z. 212) — `"no_channels"` fällt durch bis `"sent": True` |
| B2 | `api/routers/scheduler.py:54` | `trigger_alert_checks` | `status: "ok"` fest; `count` echt, fließt nicht in den Status |
| B3 | `:64` | `trigger_compare_alert_checks` | dito |
| B4 | `:74` | `trigger_radar_alert_checks` | dito |
| B5 | `:84` | `trigger_compare_radar_alert_checks` | dito |
| B6 | `:94` | `trigger_compare_official_alert_checks` | dito |
| B7 | `:111` | `trigger_inbound` | dito |
| B8 | `:126` | `trigger_inbound_telegram` | dito (Feld heißt `"processed"`) |
| B12 | `src/services/scheduler_dispatch_service.py:443` | `send_compare_preset` | `send_one_compare_preset()` (Z. 390–404) ruft `send_compare_report()` auf, dessen `NotificationResult(sent, sent_channels)` **gar keiner Variablen zugewiesen** wird. Die Funktion weiß strukturell nicht, welche der drei Kanäle zugestellt wurden, meldet aber immer `"status": "ok"` |

### Klasse 2 — teilerfolg-blind

| # | Stelle | Funktion | Befund |
|---|---|---|---|
| B9 | `src/services/trip_alert.py:275` | `check_all_trips` | try/except je Trip (Z. 348–360), nur `alerts_sent` hoch, Ausnahme nur `logger.error`; `return alerts_sent` (int) bei Z. 362 |
| B10 | `src/services/trip_alert.py:606` | `check_radar_alerts` | try/except bei Z. 675–682, `continue`-Pfade ohne Fehlerzähler; `return sent` (int) bei Z. 801 |
| B11 | `src/services/compare_alert.py:80` | `check_all_compare_presets` | try/except je Ort in `_detect_triggered_locations` (Z. 161–165), nur `sent` gezählt |
| B11b | `src/services/compare_radar_alert.py:66` | `CompareRadarAlertService.check_all_compare_presets` | **neu.** Gleiches Muster (Z. 146–152); ein Nowcast-Fehler je Ort verschwindet in `logger.error` |
| B11c | `src/services/compare_official_alert.py:72` | `CompareOfficialAlertService.check_all_compare_presets` | **neu.** `sum(1 for preset in presets if self._check_one_preset(...))` — kein Fehlerzähler |

### Klasse 3 — Heartbeat ohne Wirkung

| # | Stelle | Funktion | Befund |
|---|---|---|---|
| B13 | `api/routers/scheduler.py:147` | `_ping_heartbeat_compare` | **Toter Code — der Compare-Heartbeat feuert nie.** Die Funktion wird nirgends aufgerufen (nur Definition + ein Unit-Test des No-Env-Verhaltens); `trigger_compare_presets_daily` ruft sie nicht auf. Kein „bedingungsloser Ping", sondern der Gegenpol: ein Überwachungsmechanismus, der komplett unverdrahtet ist |

### Aus Hälfte A übernommen (PO-Entscheidung 2026-07-28)

`src/services/notification_service.py:1065/1081/1102` (`_dispatch_alert_message`, genutzt
von Änderungs-, Radar- und amtlichen Alarmen), zusätzlich `:660ff` und `:863ff`:
`sent_channels.append("email")` steht **vor** dem `try` des Versands, mit Verweis auf
#684 AC-3. `NotificationResult.sent=True` heißt damit „konfiguriert", nicht „zugestellt" —
und die Doppelalarm-Sperre greift auch dann, wenn nichts ankam. **Zählt als Fund**, nicht
als dauerhafte Ausnahme; Reparatur in S4, weil das Umstellen echtes Verhalten ändert.

## Ausnahmekandidaten

| Stelle | Begründung |
|---|---|
| `api/routers/health.py:9` | Reine Lebendmeldung, keine Aktion davor. „ok" heißt „der Prozess antwortet" — per Definition wahr, sobald der Handler läuft |
| `api/routers/webhook.py:62/72` | `telegram_webhook`, dokumentiert (Z. 54f.): „Immer 200 — verhindert Telegram-Wiederhol-Sturm." Hier passiert eine Aktion, deren Fehlschlag unsichtbar bleibt; die Semantik ist aber eine Protokoll-Empfangsbestätigung an Telegram, keine fachliche Erfolgsmeldung. **Nicht blind grün durchwinken**, sondern ausdrücklich als „Protokoll-Ack, kein Erfolgsstatus" kennzeichnen, sonst taucht er bei jeder Prüfung erneut als falscher Fund auf |

Kein Fund: `inbound_email_reader.py:50` und `inbound_telegram_reader.py:91` —
`processed` zählt dort nur tatsächlich verarbeitete Nachrichten, ist also bereits
erfolgsbereinigt. Der Fehler sitzt weiterhin bei B7/B8 (Router meldet `ok` unabhängig davon).

## Technischer Ansatz

Bauform wie Hälfte A (`tests/test_resolution_loss_guard.py`, Vorbild #1402): AST-Scan,
`KNOWN_VIOLATIONS` mit Begründung je Eintrag, zwei gekoppelte Ratschen, synthetische
Wirkungsnachweise.

**Signatur Klasse 1 (konstant):** Rückgabe-Dict mit Schlüssel aus
`{status, sent, success, ok}` und Literalwert, in einer Funktion, die vorher einen Aufruf
mit Fehlerpotential tätigt und dabei entweder (a) ihn in `try/except` einbettet, ohne dass
der `except`-Zweig den Rückgabewert beeinflusst, oder (b) dessen Rückgabewert **gar keiner
Variablen zuweist**. Trifft B1 und B12; trifft `channel_test_service.py` nicht (dort
beeinflusst der `except`-Zweig die Rückgabe) und `health.py` nicht (keine vorherige
Ein-/Ausgabe).

**Signatur Klasse 2 (teilerfolg-blind):** Schleife mit Fehler-Isolierung im Rumpf, deren
Funktion einen Erfolgszähler führt, aber keinen Namen, der **ausschließlich** in einem
Fehlerpfad erhöht wird und im `return` erscheint. Wichtig: die Prüfung darf **nicht** am
Rückgabetyp hängen (`int` statt `tuple`) — das ist nur das Symptom. Eine Funktion könnte
`(int, int)` liefern und `failed` nie erhöhen (Attrappe). Nötig ist derselbe Datenfluss-
Ansatz wie in Hälfte A: wird im Fehlerzweig ein Name erhöht, der im Erfolgszweig **nicht**
erhöht wird, und fließt er in die Rückgabe?

**Signatur Klasse 3 (Heartbeat):** Funktion mit `heartbeat`/`betterstack` im Namen muss
außerhalb ihrer Definition und außerhalb `tests/` überhaupt **aufgerufen** werden, und der
Aufruf muss hinter einer Erfolgsbedingung stehen. Trifft B13 (null Aufrufer).

## Risks & Considerations

1. **Die Absichts-Grenze ist hier härter als in Hälfte A.** Ob ein konstantes `ok`
   berechtigt ist, ist eine inhaltliche Frage (Lebendmeldung, Protokoll-Empfangsbestätigung),
   keine strukturelle. Ausnahmeliste mit Begründung je Eintrag ist Pflicht; eine
   Kommentar-Konvention (`# status-ok-intentional: <Grund>`) wäre die Alternative, wurde in
   Hälfte A aber ausdrücklich verworfen — ein Kommentar erreicht den Betrieb nicht.
2. **Attrappen-Gefahr bei Klasse 2** (s. o.): Symptom-Prüfung am Rückgabetyp wäre
   trivial zu umgehen und würde eine Sicherheit vortäuschen.
3. **Go bleibt außen vor.** Die übrigen Heartbeat-Aufrufe liegen in `internal/notify/mq.go`
   und `internal/config/config.go` — außerhalb der Reichweite eines Python-Scans. Als
   bewusste Lücke benennen.
4. **Erwartung aus Hälfte A:** dort fand der Wächter 22 statt der aufgenommenen 13. Auch
   hier ist mit mehr als den 16 aufgenommenen Stellen zu rechnen; die 20er-Heuristik gegen
   Fehlalarme gilt sinngemäß, aber echte Funde werden nicht wegdefiniert.
5. **Regel-Budget:** neue Pflicht-Regel → Prüfdatum +90 Tage = **2026-10-26**.

## Über das Ticket hinaus

**B13 ist ein Überwachungsloch, kein reiner Wächter-Fund:** Der Compare-Heartbeat ist
verdrahtet gedacht, aber nie angeschlossen — bleibt der Compare-Versand komplett aus,
schlägt niemand Alarm. Das berührt die Hausregel „Heartbeat-Pflicht: Readiness statt
Liveness" und gehört gemeldet, unabhängig vom Wächterbau.
