# Context: Issue #609 — SMS-Rufnummer im Profil-Editor

## Request Summary
Im Nutzerprofil-Editor soll ein Eingabefeld für die SMS-Handynummer (`sms_to`) ergänzt werden, damit der fertige SMS-Kanal (#608) nutzbar wird. Aktuell fehlt das Feld in Model, API-Handler und Frontend.

## Related Files
| Datei | Relevanz |
|-------|----------|
| `internal/model/user.go` | User-Struct — hier fehlt `SmsTo string` |
| `internal/handler/auth.go` | `profileResponse`, `UpdateProfileHandler` — hier fehlen `sms_to`-Felder |
| `internal/handler/profile_test.go` | Bestehende Tests — hier neuer Test für `sms_to` |
| `frontend/src/routes/account/+page.svelte` | UI — hier fehlt `let smsTo`, Eingabefeld + Badge |

## Existing Patterns
- `mail_to`: einfaches Textfeld (type="email"), wird im `save()`-Call mitgeschickt, Badge in Kanalübersicht
- `telegram_chat_id`: komplexer OAuth-Flow — kein Vorbild für SMS, aber Badge-Muster ist identisch
- `save()` schickt PUT an `/api/auth/profile` — `sms_to` muss hier ebenfalls ergänzt werden
- `testStatus`/`testError` Records für Channel-Test-Buttons — SMS folgt gleichem Muster

## Dependencies
- Upstream: `data/users/{id}/user.json` — JSON-Persistenz, kein DB-Schema-Migration nötig (neues Feld wird einfach additiv geschrieben)
- Downstream: SMS-Kanal (#608) liest `user.SmsTo` — sobald Feld im Model und gespeichert, funktioniert Kanal

## Existing Tests (profile_test.go)
- `TestGetProfileHandler` — prüft `mail_to` + `telegram_chat_id` im Response
- `TestUpdateProfileHandler` — prüft PUT mit `mail_to` + `telegram_chat_id`
- Beide Tests müssen `sms_to` ebenfalls abdecken

## Risks & Considerations
- Kein Pflichtfeld — `omitempty` im JSON-Tag sicherstellt, dass fehlende Nummer nicht bricht
- Format-Validierung: Issue nennt internationales Format (`+49XXXXXXXXXX`), aber kein Pflicht-Validator nötig (analog mail_to, das ebenfalls keine serverseitige Validierung hat)
- Test-Button für SMS: sendTest('sms') wäre analog zu email/telegram, aber kein AC dafür — NICHT implementieren
