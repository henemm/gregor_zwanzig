# External Validator Report

**Spec:** docs/specs/modules/change_password.md
**Datum:** 2026-04-17T14:30:00Z
**Server:** https://gregor20.henemm.com

## Checklist

| # | Expected Behavior | Beweis | Verdict |
|---|-------------------|--------|---------|
| 1 | Card "Passwort ändern" auf /account zwischen "Kanäle" und "Gefahrenzone" | Screenshot `/tmp/validator_account_full.png` — Reihenfolge: Kanäle (pos 198) → Passwort ändern (pos 378) → Gefahrenzone (pos 470) | **PASS** |
| 2 | 3 Felder: Aktuelles Passwort, Neues Passwort, Neues Passwort bestätigen + Button | Screenshot + DOM-Inspektion: `#oldPassword`, `#newPassword`, `#confirmNewPassword` + Button "Passwort ändern" | **PASS** |
| 3 | Neue Passwörter stimmen nicht überein → Client-Fehler "Die neuen Passwörter stimmen nicht überein" (kein API-Call) | Screenshot `/tmp/validator_t1.png` — rote Meldung sichtbar, Felder bleiben befüllt | **PASS** |
| 4 | Falsches altes Passwort → 403 + "Aktuelles Passwort ist falsch" | API: `403 {"error":"wrong password"}` + Screenshot `/tmp/validator_t2.png` — rote Meldung "Aktuelles Passwort ist falsch" | **PASS** |
| 5 | Neues Passwort zu kurz (< 8 Zeichen) → 400 + Fehlermeldung | API: `400 {"error":"validation failed"}` + Screenshot `/tmp/validator_t3.png` — rote Meldung "validation failed" | **PASS** |
| 6 | Malformed JSON → 400 {"error":"invalid request"} | API: `400 {"error":"invalid request"}` | **PASS** |
| 7 | Nicht authentifiziert → 401 | API: `401` (curl ohne Cookie) | **PASS** |
| 8 | Erfolg → grüner Banner "Passwort geändert", Felder geleert, Backend 200 | API: `200 {"status":"ok"}` + Screenshot `/tmp/validator_t4.png` — grüne Meldung "Passwort geändert", alle 3 Felder leer | **PASS** |
| 9 | Neuer bcrypt-Hash wird persistiert | Login mit neuem Passwort: `200 {"id":"validator_test"}`, Login mit altem Passwort: `401 {"error":"invalid credentials"}` | **PASS** |
| 10 | Fehler: Felder bleiben befüllt | Screenshots t1, t2, t3 — Felder behalten ihre Werte bei Fehler | **PASS** |

## Findings

Keine kritischen Findings.

### Minor: Rohe API-Fehlermeldung bei kurzem Passwort
- **Severity:** LOW
- **Expected:** Spec sagt "Fehlermeldung aus API-Response" — wird korrekt angezeigt
- **Actual:** Die Meldung "validation failed" ist englisch und nicht benutzerfreundlich. Die Spec definiert dies aber explizit als erwartetes Verhalten ("Fehlermeldung aus API-Response"), daher kein FAIL.
- **Evidence:** Screenshot `/tmp/validator_t3.png`

## Verdict: VERIFIED

### Begruendung

Alle 10 Pruefpunkte bestanden. Backend-API liefert korrekte HTTP-Statuscodes und Fehlermeldungen fuer alle Szenarien (401, 400, 403, 200). Frontend zeigt die Card an der richtigen Position, behandelt alle Fehlerfaelle korrekt (Client-seitig und Server-seitig), zeigt Erfolgs-/Fehlermeldungen in der richtigen Farbe, leert Felder bei Erfolg und behaelt sie bei Fehler. Passwort-Aenderung wird korrekt persistiert — neues Passwort funktioniert, altes wird abgelehnt.
