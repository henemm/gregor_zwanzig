# External Validator Report

**Spec:** docs/specs/modules/user_profile_channels.md
**Datum:** 2026-04-16T08:35Z
**Server:** https://gregor20.henemm.com

## Checklist

| # | Expected Behavior | Beweis | Verdict |
|---|-------------------|--------|---------|
| 1 | GET /api/auth/profile ohne Auth → 401 `{"error":"unauthorized"}` | Response: `{"error":"unauthorized"}`, HTTP 401 | **PASS** |
| 2 | PUT /api/auth/profile ohne Auth → 401 | HTTP 401 | **PASS** |
| 3 | GET /api/auth/profile mit Auth → 200 mit Profil | Response: `{"id":"__test_validator__","created_at":"2026-04-16T08:35:15Z"}`, HTTP 200 | **PASS** |
| 4 | Response enthaelt KEIN password_hash | Kein `password_hash` Feld in allen Responses | **PASS** |
| 5 | PUT /api/auth/profile aktualisiert Channel-Felder | mail_to, signal_phone, telegram_chat_id korrekt gesetzt, HTTP 200 | **PASS** |
| 6 | GET nach PUT zeigt persistierte Werte | Alle Felder stimmen ueberein | **PASS** |
| 7 | PUT mit leerem Body → 400 | Kein Body → 400 korrekt. Aber `{}` → 200 (unveraendertes Profil) | **UNKLAR** |
| 8 | PUT mit password_hash → wird ignoriert | password_hash nicht aktualisiert, Login mit Original-Passwort weiterhin 200 | **PASS** |
| 9 | POST /api/auth/register erstellt Unterordner | locations/, trips/, gpx/, weather_snapshots/ vorhanden | **PASS** |
| 10 | Partial Update: nur gesendete Felder aendern | email aktualisiert, mail_to/signal_phone/telegram_chat_id blieben erhalten | **PASS** |
| 11 | Response-Format: id, email, mail_to, signal_phone, telegram_chat_id, created_at | Alle genannten Felder vorhanden (wenn gesetzt) | **PASS** |
| 12 | signal_api_key im Response | Feld fehlt in GET/PUT Response, obwohl im User-Struct und als erlaubtes Update-Feld definiert | **FAIL** |

## Findings

### Finding 1: Leerer JSON-Body `{}` gibt 200 statt 400
- **Severity:** LOW
- **Expected:** Spec sagt "PUT mit leerem Body → 400 `{"error":"invalid request"}`"
- **Actual:** Kein Body (kein Content-Type) → 400 korrekt. Aber `{}` (valides JSON ohne Felder) → 200 mit unveraendertem Profil
- **Evidence:** HTTP 200, Profil unveraendert zurueckgegeben
- **Bewertung:** Interpretationsfrage. `{}` ist technisch kein "leerer Body", sondern ein leeres JSON-Objekt. Das Verhalten ist defensiv und sinnvoll (no-op), aber weicht von der Spec ab wenn man `{}` als "leeren Body" interpretiert.

### Finding 2: signal_api_key fehlt in API-Response
- **Severity:** MEDIUM
- **Expected:** Spec definiert `signal_api_key` im User-Struct (Step 1) und als erlaubtes Update-Feld in UpdateProfileHandler (Step 3). Response soll "User-Felder OHNE password_hash" enthalten (Step 3, Punkt 3/7). Daraus folgt: signal_api_key gehoert in die Response.
- **Actual:** signal_api_key erscheint in keiner GET- oder PUT-Response. Ob der Wert gespeichert wird, konnte nicht verifiziert werden (Secrets Guard blockiert user.json Zugriff).
- **Evidence:** `python3 -c "... print('signal_api_key present:', 'signal_api_key' in d)"` → `False`
- **Bewertung:** Entweder (a) das Feld wird absichtlich wie password_hash aus der Response gefiltert (als Security-Massnahme fuer API-Keys), was aber nicht in der Spec dokumentiert ist, oder (b) es ist ein Bug im Response-Mapping. Die Spec-Beispiel-Response listet signal_api_key nicht auf, aber der Text sagt "ohne password_hash" — alles andere sollte drin sein.

## Verdict: AMBIGUOUS

### Begruendung

9 von 12 Checks sind klare **PASS**. Die Kernfunktionalitaet (Profil lesen, aktualisieren, Partial Update, password_hash-Schutz, Directory-Provisioning, Auth-Guard) funktioniert einwandfrei.

Zwei Findings verhindern ein klares VERIFIED:

1. **`{}` Body-Handling** (LOW): Vertretbares Verhalten, aber Spec-Abweichung. Klaerung noetig ob `{}` als "leerer Body" gilt.
2. **signal_api_key fehlt in Response** (MEDIUM): Die Spec ist intern widersprüchlich — das Beispiel-Response-Format zeigt signal_api_key nicht, aber der Text sagt "alle Felder außer password_hash". Entweder Spec oder Implementation muss angepasst werden.

Keines der Findings ist CRITICAL. Die App ist funktional und sicher. Aber die Spec-Abweichungen muessen geklaert werden bevor ein VERIFIED moeglich ist.
