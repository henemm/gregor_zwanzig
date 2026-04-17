# External Validator Report

**Spec:** docs/specs/modules/account_page_extend.md
**Datum:** 2026-04-17T14:30:00Z
**Server:** https://gregor20.henemm.com
**Test-Account:** valtest42 (registriert und nach Tests geloescht)

## Checklist

| # | Expected Behavior | Beweis | Verdict |
|---|-------------------|--------|---------|
| 1 | Signal API Key Feld existiert unterhalb Signal-Nummer, oberhalb Telegram-ID | Screenshot val_06_account_full.png | PASS |
| 2 | Signal API Key Feld ist type="password" (maskiert) | Playwright: type="password", Screenshot val_07_apikey_filled.png zeigt Punkte | PASS |
| 3 | Placeholder "Callmebot API Key" | Screenshot val_06_account_full.png | PASS |
| 4 | Hilfetext "Callmebot API Key fuer Signal-Benachrichtigungen" | Screenshot val_06_account_full.png | PASS |
| 5 | Gefahrenzone Card mit rotem Styling am Ende der Seite | Screenshot val_06_account_full.png — roter Titel, roter Rahmen | PASS |
| 6 | Account loeschen Button (rot) in Gefahrenzone | Screenshot val_06_account_full.png | PASS |
| 7 | Warntext korrekt | Screenshot val_06_account_full.png — "Das Loeschen deines Accounts ist unwiderruflich..." | PASS |
| 8 | Signal API Key wird nach Speichern geleert (write-only) | Playwright: field value "" nach save | PASS |
| 9 | PUT Body enthaelt signal_api_key wenn Feld gefuellt | Playwright Network: {"signal_api_key":"test-key-123"} | PASS |
| 10 | PUT Body enthaelt signal_api_key NICHT wenn Feld leer | Playwright Network: {"mail_to":"","signal_phone":"","telegram_chat_id":""} — kein signal_api_key | PASS |
| 11 | window.confirm Dialog erscheint bei Klick auf "Account loeschen" | Playwright Dialog Event: "Bist du sicher? Alle deine Daten werden unwiderruflich geloescht." | PASS |
| 12 | Abbruch des Dialogs verhindert API-Call | Playwright: 0 API requests nach dismiss | PASS |
| 13 | Bestaetigung loest DELETE /api/auth/account aus | Playwright Network: DELETE 200 | PASS |
| 14 | Redirect zu /login nach Loeschung (Hard Redirect) | Playwright: page.url = /login | PASS |
| 15 | Session invalidiert nach Loeschung | Playwright: /account -> Redirect /login | PASS |
| 16 | Geloeschter Account kann sich nicht mehr einloggen | Screenshot val_12_login_deleted.png — "Invalid credentials" | PASS |

## Findings

Keine Findings. Alle 16 Pruefpunkte bestanden.

## Verdict: VERIFIED

### Begruendung

Alle Expected-Behavior-Punkte aus der Spec wurden einzeln geprueft und mit Screenshots/Network-Traces belegt:

1. **Signal API Key Feld:** Korrekt positioniert, maskiert (type=password), Placeholder und Hilfetext stimmen, write-only Semantik funktioniert (Feld leert sich nach Speichern), leeres Feld wird korrekt aus dem PUT-Payload ausgelassen.

2. **Account-Loeschung:** Gefahrenzone-Card visuell korrekt (rot), window.confirm-Dialog mit korrektem Text, Abbruch verhindert API-Call, Bestaetigung loest DELETE aus, Redirect zu /login, Session wird invalidiert, Account ist danach nicht mehr login-faehig.

Alle 16/16 Pruefpunkte: **PASS**
