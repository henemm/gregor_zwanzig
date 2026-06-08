# Context: Issue #642 — User-Namen änderbar machen

## Request Summary
Aktuell kann ein Nutzer seinen angezeigten Namen nicht ändern. Der Name soll für den Nutzer editierbar werden.

## Kernproblem (architektonisch)
Der "Username" ist im Backend **identisch mit `User.ID`** und damit dreifach belegt:
1. **Auth-Identifier** — Login + Session-Signierung (`internal/handler/auth.go` Login Z.90-130, Session-Sign Z.115)
2. **Persistenz-Schlüssel** — `data/users/<user_id>/...` (`internal/store/user.go` Z.48-79)
3. **Mandanten-Isolations-Key** — gesamtes Multi-User-Modell hängt an `user_id`

→ Eine echte Umbenennung der `ID` erfordert Verzeichnis-Migration, Session-Neu-Signierung, Kollisions-Prüfung und Update aller Querverweise — hohes Datenverlust-Risiko (vgl. BUG-DATALOSS-GR221 / CLAUDE.md Schema-Rework-Regeln).

## Related Files
| File | Relevance |
|------|-----------|
| `internal/model/user.go` Z.10-21 | `User`-Struct: `ID` ist der Username; **kein** `display_name`-Feld |
| `internal/handler/auth.go` Z.403-417 | `GET /api/auth/profile` — liefert `id`, `email`, `mail_to`, `sms_to`, `telegram_chat_id`, `created_at`, `has_passkey` |
| `internal/handler/auth.go` Z.419-466 | `PUT /api/auth/profile` — Update-Struct akzeptiert nur `email`, `mail_to`, `sms_to`, `telegram_chat_id` (kein Name) |
| `internal/handler/auth.go` Z.356-365 | `profileResponse`-Struct |
| `internal/handler/auth.go` Z.26-88 | Registration: `username` wird direkt zu `User.ID`, Regex `[a-zA-Z0-9_-]+`, 3-50 Zeichen |
| `internal/store/user.go` Z.48-79 | `LoadUser`/`SaveUser` — Pfad `data/users/{id}/user.json` |
| `cmd/server/main.go` Z.101-102 | Router für GET/PUT `/api/auth/profile` |
| `frontend/src/routes/account/+page.svelte` Z.332-346 | Profil-Card: Benutzername read-only (`data.profile?.id`) |
| `frontend/src/routes/account/+page.svelte` Z.207-221 | `save()` → `PUT /api/auth/profile` mit `mail_to`, `sms_to` |
| `frontend/src/routes/account/+page.server.ts` Z.17-37 | Lädt Profil via `GET /api/auth/profile` |
| `frontend/src/lib/components/ui/sidebar/Sidebar.svelte` Z.41-43, 147-149 | Sidebar-Fußzeile: zeigt `userId` + Initial |
| `frontend/src/routes/+layout.server.ts` / `hooks.server.ts` | `userId` aus Session → an Sidebar |

## Lösungsoptionen
**Option A — `display_name` entkoppeln (empfohlen, Best Practice):**
- Neues optionales Feld `DisplayName` im `User`-Struct; `ID` bleibt unveränderlicher Login-/Storage-Schlüssel.
- PUT `/api/auth/profile` um `display_name` erweitern; UI zeigt `display_name || id` (Sidebar + Account).
- **Vorteil:** Null Migration, null Datenverlust-Risiko, Login bleibt stabil. Entspricht Standard (GitHub/Discord: Handle ≠ Anzeigename).
- **Nachteil:** Login-Name bleibt der alte; Nutzer ändert nur den *angezeigten* Namen.

**Option B — `User.ID` echt umbenennen:**
- Verzeichnis-Migration `data/users/old → new`, Session neu signieren, Kollisions-Check, alle Referenzen.
- **Vorteil:** Login-Name ändert sich mit.
- **Nachteil:** Hohes Datenverlust-Risiko, komplex, gegen CLAUDE.md Schema-Rework-Vorsicht.

## Dependencies
- Upstream: Session-Auth (`hooks.server.ts`, `verifySession`), Store-Persistenz.
- Downstream: Sidebar-Anzeige, Account-Seite, jede Stelle die `userId`/`profile.id` als Namen rendert.

## Risks & Considerations
- Option B verletzt die Schema-Rework-Vorsicht (Datenverlust). Option A ist additiv & rückwärtskompatibel.
- Mandantentrennung: Endpoint muss echte `user_id` aus Auth-Kontext nutzen (kein `default`-Fallback).
- Sidebar + Account müssen denselben Anzeige-Fallback (`display_name || id`) verwenden.
