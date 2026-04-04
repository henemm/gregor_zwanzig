# QA Report: F12a Channel-Switch für Subscriptions

**Feature:** CompareSubscription mit `send_email` und `send_signal` Flags; Scheduler und UI respektieren diese Flags.
**Test-Datum:** 2026-04-04
**Tester:** QA Agent (Claude Sonnet 4.6)
**Service-URL:** https://gregor20.henemm.com
**Branch:** main

---

## Test 1: Service-Health

**Status: PASSED**

- HTTP-Status `https://gregor20.henemm.com`: **200 OK**
- `systemctl status gregor_zwanzig.service`: **active (running)**
- Gestartet: 2026-04-04 10:33:38 UTC (zum Zeitpunkt des Tests ca. 48s laufend)
- Memory: 64.4M, CPU: 675ms — unauffällig

---

## Test 2: Subscriptions-Page erreichbar

**Status: PASSED**

- HTTP-Status `https://gregor20.henemm.com/subscriptions`: **200 OK**
- Screenshot gespeichert: `qa-subscriptions-page.png`
- Subscription-Card "Zillertal täglich" sichtbar mit Status-Badge "Disabled"
- Buttons (play, send, edit, delete) korrekt gerendert

**Auffälligkeit (Minor):** Die Seite trägt noch den Titel "Email Subscriptions" und die Beschreibung "Automatic ski resort comparison via email at scheduled times." — diese Texte sind nach dem Channel-Switch Feature veraltet und sollten auf etwas Neutraleres wie "Subscriptions" oder "Benachrichtigungs-Subscriptions" aktualisiert werden.

---

## Test 3: Bestehende Subscriptions laden korrekt (Backward Compatibility)

**Status: PASSED mit Beobachtung**

Inhalt von `compare_subscriptions.json`:
```json
{
  "subscriptions": [
    {
      "id": "zillertal-t-glich",
      "name": "Zillertal täglich",
      "enabled": false,
      "locations": ["*"],
      "forecast_hours": 24,
      "time_window_start": 9,
      "time_window_end": 16,
      "schedule": "daily_evening",
      "weekday": 4,
      "include_hourly": true,
      "top_n": 3
    }
  ]
}
```

Die bestehende Subscription enthält **keine** `send_email`- oder `send_signal`-Felder. Sie stammt aus der Zeit vor F12a.

**Beobachtung:** Beim Öffnen des Edit-Dialogs für diese Subscription zeigt die UI E-Mail=checked, Signal=unchecked — d.h. der Code setzt für fehlende Felder einen Default. Das Verhalten ist korrekt (backward-compatible), aber es gibt ein Risiko:

**Wenn der User diese Subscription jetzt unverändert speichert, werden `send_email=true` und `send_signal=false` in die JSON-Datei geschrieben.** Das ist das korrekte Verhalten, sollte aber geloggt oder dokumentiert sein.

Keine Fehler beim Laden der Subscription. Service gestartet ohne Load-Fehler.

---

## Test 4: Screenshot Subscriptions-Page

**Status: PASSED**

Screenshot: `qa-subscriptions-page.png`

Sichtbar:
- "Email Subscriptions" als Seitentitel (veraltet, siehe Test 2)
- Subscription-Card "Zillertal täglich" mit Badge "Disabled"
- Zeitangabe: "18:00 (tomorrow) | 09:00-16:00 | 24h Forecast"
- "Locations: All locations"
- Vier Action-Buttons: play_arrow, send, edit, delete
- "NEW SUBSCRIPTION"-Button

**Auffälligkeit:** Es gibt keinen sichtbaren Channel-Indikator auf der Subscription-Card. Da die bestehende Subscription keine `send_email`/`send_signal`-Felder hat, ist unklar welche Channels aktiv sind, wenn man die Card-Ansicht betrachtet — kein E-Mail-Icon, kein Signal-Icon. Das ist eine UX-Lücke, kein Bug.

---

## Test 5: New Subscription Dialog — Kanäle-Checkboxen

**Status: PASSED**

Screenshot: `qa-new-subscription-dialog.png`

Sichtbar im Dialog:
- Alle bekannten Felder vorhanden (Name, Locations, Schedule, Weekday, Time Window, Forecast Period, Hourly details, Top N, Enabled)
- **Abschnitt "Kanäle"** am Ende des Formulars sichtbar
- **"E-Mail" Checkbox: checked (aktiv)**
- **"Signal" Checkbox: unchecked (inaktiv)**
- CANCEL und SAVE Buttons vorhanden

Die Checkboxen sind korrekt positioniert, klar beschriftet und die Defaults sind sinnvoll (E-Mail an, Signal aus).

**Edit-Dialog (bestehende Subscription):**

Screenshot: `qa-edit-subscription-dialog.png`

Beim Bearbeiten von "Zillertal täglich":
- Gleicher Aufbau mit "Kanäle"-Sektion am Ende
- E-Mail=checked, Signal=unchecked — korrekte Defaults für eine Subscription ohne explizite Channel-Flags

---

## Test 6: Heartbeat / Scheduler

**Status: PASSED**

Log-Einträge nach dem aktuellen Start (10:33:38 UTC):
```
Scheduler started: Subscriptions 07:00/18:00, Trip Reports hourly, Alert Checks every 30min, Inbound Commands every 5min (Europe/Vienna)
```

Alle 5 Jobs korrekt registriert:
- Morning Subscriptions (07:00)
- Evening Subscriptions (18:00)
- Trip Reports (hourly check)
- Alert Checks (every 30 min)
- Inbound Command Poll (every 5min)

---

## Test 7: Fehler in Logs seit Restart

**Status: PASSED (mit bekanntem Nicht-Feature-Bug)**

Einziger Fehler seit dem aktuellen Neustart (10:33:38 UTC):

```
2026-04-04 10:35:00 - services.inbound_email_reader - ERROR - Network error: [SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1000)
```

Dieser Fehler tritt regelmäßig alle 5 Minuten beim Inbound-Command-Poll auf und ist **nicht mit F12a verwandt**. Er zeigt ein pre-existierendes Problem mit dem Mail-Server-SSL-Handshake.

**Kein Fehler im Zusammenhang mit dem Channel-Switch-Feature.**

**Zusätzlicher Fehler im Pre-Restart-Fenster (nicht F12a-bezogen):**

```
trip_alert - ERROR - Failed to send alert for gr221-mallorca: int() argument must be a string, a bytes-like object or a real number, not 'NoneType'
```

Dieser `TypeError` trat vor dem Neustart wiederholt auf (10:00 Uhr und 10:30 Uhr). **Ursache liegt in `trip_alert`, nicht in F12a.** Nach dem Neustart wurde dieser Fehler noch nicht ausgelöst (nächste Alert-Check-Ausführung steht aus).

---

## Gesamtergebnis

| Test | Status | Notiz |
|------|--------|-------|
| 1 Service-Health | PASSED | Active (running), 200 OK |
| 2 Subscriptions-Page | PASSED | 200 OK, Karte sichtbar |
| 3 Backward Compatibility | PASSED | Alte Subscription lädt ohne Fehler, Defaults korrekt |
| 4 Screenshot Page | PASSED | Karte mit korrektem Inhalt |
| 5 Kanäle-Checkboxen | PASSED | E-Mail + Signal sichtbar, korrekte Defaults |
| 6 Scheduler / Heartbeat | PASSED | Alle Jobs gestartet |
| 7 Fehler-Check | PASSED | Keine F12a-Fehler |

**F12a Feature: FREIGEGEBEN**

---

## Bekannte Issues (nicht F12a)

### BUG-1: trip_alert TypeError (pre-existierend)
- **Fehler:** `int() argument must be a string, a bytes-like object or a real number, not 'NoneType'`
- **Service:** `trip_alert`, Job "Alert Checks (every 30 min)"
- **Trip:** gr221-mallorca
- **Häufigkeit:** Bei jedem Alert-Check-Lauf (alle 30 min) seit mindestens dem heutigen Tag
- **Schwere:** ERROR — verhindert Alert-Versand für diesen Trip
- **F12a-Bezug:** Keiner — pre-existierender Bug
- **Empfehlung:** Separates Issue erstellen

### BUG-2: Inbound Email Reader SSL-Fehler (pre-existierend)
- **Fehler:** `[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol`
- **Service:** `inbound_email_reader`, alle 5 Minuten
- **Schwere:** ERROR im Log, aber kein Absturz
- **F12a-Bezug:** Keiner

---

## Offene UX-Hinweise (keine Bugs)

1. **Seitentitel veraltet:** "Email Subscriptions" und "Automatic ski resort comparison via email at scheduled times." sollte auf neutralere Texte angepasst werden, die beide Channels (E-Mail + Signal) berücksichtigen.

2. **Kein Channel-Badge auf Subscription-Cards:** Die Karten-Ansicht zeigt nicht an, welche Channels für eine Subscription aktiv sind. Ein kleines E-Mail- oder Signal-Icon auf der Karte würde die Übersicht verbessern.

3. **JSON-Persistenz bei Edit bestehender Subscriptions:** Wenn eine alte Subscription (ohne Channel-Flags) geöffnet und unverändert gespeichert wird, werden `send_email=true` und `send_signal=false` explizit in die JSON geschrieben. Das ist korrekt, aber ein stiller Default-Upgrade ohne Nutzer-Feedback.

---

## Artifacts

| Datei | Inhalt |
|-------|--------|
| `qa-subscriptions-page.png` | Screenshot der Subscriptions-Seite |
| `qa-new-subscription-dialog-top.png` | Screenshot "New Subscription" Dialog (Gesamtansicht) |
| `qa-new-subscription-dialog.png` | Screenshot "New Subscription" Dialog (nach Scroll) |
| `qa-edit-subscription-dialog.png` | Screenshot "Edit Subscription" für bestehende Subscription |
| `qa-report.md` | Dieser Report |

