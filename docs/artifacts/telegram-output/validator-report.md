# External Validator Report

**Spec:** docs/specs/modules/telegram_output.md
**Datum:** 2026-04-15T18:10:00+02:00
**Server:** http://localhost:8080 (NiceGUI Dev-Server)
**Hinweis:** gregor_zwanzig.service ist gecrasht (seit 13:40 UTC). gregor20.henemm.com zeigt Go/SvelteKit-Frontend ohne NiceGUI-Features. Validierung daher gegen lokalen NiceGUI-Server auf Port 8080.

## Checklist

| # | Expected Behavior | Beweis | Verdict |
|---|-------------------|--------|---------|
| 1 | Settings UI: Telegram (Bot API) Karte mit Bot Token, Chat ID, Test-Button | Screenshot: Karte "Telegram (Bot API)" mit Bot Token, Chat ID Inputs und "SEND TEST TELEGRAM" Button sichtbar | **PASS** |
| 2 | Settings: Test-Button zeigt Warnung ohne Credentials | Notification: "Telegram not configured. Please fill Bot Token and Chat ID." | **PASS** |
| 3 | Subscriptions: Telegram-Checkbox im Edit-Dialog | Screenshot: Dialog zeigt unter "Kanäle" drei Checkboxen: E-Mail, Signal, Telegram | **PASS** |
| 4 | Subscriptions: Telegram-Flag wird persistiert | `send_telegram: true` in compare_subscriptions.json nach Toggle+Save, `false` nach Reset | **PASS** |
| 5 | Trip Report Config: Telegram-Checkbox im Dialog | Screenshot: Dialog zeigt "Telegram senden" Checkbox unter Kanäle | **PASS** |
| 6 | Trip Report Config: Telegram-Flag wird persistiert | `send_telegram: True` in trip JSON nach Toggle+Save | **PASS** |
| 7 | Backward Compatibility: Bestehende Daten ohne send_telegram laden korrekt | Existierende Subscriptions/Trips laden fehlerfrei, Default False | **PASS** |
| 8 | Compare: Telegram-Dispatch beim manuellen Senden | Button heißt nur "Per E-Mail senden" — Backend-Dispatch nicht extern prüfbar | **UNKLAR** |
| 9 | Bugfix: per-trip Flag Gating (Email/Signal/Telegram) | Nicht extern prüfbar ohne Scheduler-Lauf + Logfiles | **UNKLAR** |
| 10 | TelegramOutput.send(): HTTP POST an Bot API | Nicht prüfbar ohne konfigurierte Bot-Credentials | **UNKLAR** |

## Findings

### Finding 1: Compare-Seite — Button-Label irreführend
- **Severity:** LOW
- **Expected:** Laut Spec dispatcht Compare auch an Telegram wenn `subscription.send_telegram=True`
- **Actual:** Button heißt "Per E-Mail senden" — kein Hinweis auf multi-channel Dispatch
- **Evidence:** Screenshot `/tmp/val_local_compare.png`
- **Anmerkung:** Backend-Logik könnte korrekt sein, aber Button-Text suggeriert nur E-Mail. Ohne Credentials nicht verifizierbar.

### Finding 2: systemd-Service gecrasht — Production nicht testbar
- **Severity:** MEDIUM
- **Expected:** gregor_zwanzig.service läuft, gregor20.henemm.com zeigt NiceGUI-App
- **Actual:** Service Status "failed" seit 13:40 UTC. Production-URL zeigt Go/SvelteKit-Frontend ohne Telegram-UI.
- **Evidence:** `systemctl status gregor_zwanzig.service` → `Active: failed (Result: exit-code)`
- **Anmerkung:** Alle Telegram-Features sind nur auf dem lokalen Dev-Server sichtbar (nicht-deployeter Code).

### Finding 3: Core-Funktion (Nachricht senden) nicht verifizierbar
- **Severity:** MEDIUM
- **Expected:** Telegram-Nachricht wird tatsächlich zugestellt
- **Actual:** Kein Telegram-Bot konfiguriert (Bot Token + Chat ID leer)
- **Evidence:** Settings-Seite zeigt leere Felder; `grep -i telegram .env` → keine Treffer

### Positive Befunde
- Alle UI-Elemente (Settings-Karte, Subscription-Checkbox, Trip-Config-Checkbox, Test-Button) sind vorhanden
- Persistenz funktioniert korrekt in beide Richtungen (Subscription + Trip)
- Backward Compatibility: bestehende Daten ohne `send_telegram` Feld laden fehlerfrei
- Test-Button zeigt korrekte Validierungsmeldung bei fehlenden Credentials

## Verdict: AMBIGUOUS

### Begründung

**7 von 10 Prüfpunkten PASS.** Alle sichtbaren UI-Elemente sind vorhanden und funktional:
- Telegram-Karte auf Settings mit Bot Token, Chat ID, Test-Button ✓
- Telegram-Checkboxen in Subscription- und Trip-Dialogen ✓
- Persistenz (Write/Read Cycle) verifiziert ✓
- Backward Compatibility bestätigt ✓

**3 Prüfpunkte UNKLAR** — nicht wegen erkennbarer Fehler, sondern weil sie ohne konfigurierte Telegram-Credentials nicht extern verifizierbar sind:
1. Tatsächlicher HTTP POST an Telegram Bot API (Core-Funktion)
2. Bugfix: per-trip Flag Gating für alle Channels
3. Compare-Seite: Multi-Channel-Dispatch

**Nicht VERIFIED:** Die Core-Funktion (Nachricht senden) ist ungetestet.
**Nicht BROKEN:** Alle sichtbaren/testbaren Aspekte funktionieren korrekt.
**AMBIGUOUS:** Vollständige Verifikation erfordert konfigurierte Telegram-Credentials.

### Empfehlung zur Erreichung von VERIFIED

1. Telegram-Bot erstellen (@BotFather) und Credentials konfigurieren
2. Test-Button auf Settings → echte Nachricht muss im Telegram-Chat ankommen
3. Trip mit `send_telegram=True` → Test Morning/Evening → Telegram-Nachricht verifizieren
4. systemd-Service neustarten damit Production-Server die Features zeigt
