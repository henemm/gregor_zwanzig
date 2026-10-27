# Context: feat-2154-s2-verknuepfungscode-ui

## Request Summary

Issue #2154 Scheibe B: Der Premium-SMS-Verknüpfungscode (Scheibe A, live seit
2026-09-13, `29b5ae91`) ist bisher nur über die API erreichbar
(`GET`/`POST /api/auth/premium-sms-link-code`). Es fehlt eine Stelle in der
Kontoseite, an der ein Premium-Nutzer den Code sehen (einmalig, beim
Erzeugen/Erneuern) und erneuern kann.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/routes/account/+page.svelte` | Zielseite (1180 Zeilen). Enthält bereits Telegram-Verknüpfung (Zeile 303-568) als nächstliegendes Vorbild: Verbindungsstatus-Badge, Verbinden/Trennen-Buttons, `data-testid`-Konventionen. Auch Tier-Anzeige (`data.profile?.tier`, Zeile 69-88, `data-testid="tier"`) und Passkey-Karte (Zeile 580ff, `data-testid="passkeys-card"`) als Vorbild für „Geheimnis anzeigen + Bestätigungsdialog vor destruktiver Aktion" (Lösch-Bestätigung analog `showDeleteAccountDialog`/`showLogoutAllDialog`, Zeile 331-425). |
| `frontend/src/routes/account/+page.server.ts` | Lädt `profile` server-seitig parallel zu anderen Ressourcen (`Promise.all`, Zeile 20-32). `tier` kommt aus `profile`, `premium-sms-link-code`-Status (`exists`) NICHT — muss ergänzt werden, wenn der Anfangszustand ohne Client-Roundtrip sichtbar sein soll. |
| `internal/handler/premium_sms_link_code.go` | Backend-Endpoint aus Scheibe A. `POST` erzeugt/erneuert den Code, gibt ihn **genau einmal** im Klartext zurück (`{"code": "..."}`), speichert nur den bcrypt-Hash. `GET` meldet nur `{"exists": bool}`, nie den Code/Hash. Kein Backend-Code-Änderungsbedarf für Scheibe B. |
| `internal/router/router.go:110-111` | Route-Registrierung, anmeldepflichtig über die globale `AuthMiddleware`. |
| `docs/reference/api_contract.md:3323-3375` | Vollständiger Vertrag für beide Endpoints (Request/Response/Fehlerfälle). |
| `docs/specs/modules/fix_2154_premium_sms_verknuepfungscode.md` | Scheibe-A-Spec, Abschnitt „Out of Scope" (Zeile 355-358) benennt Scheibe B explizit: „Konto-Oberfläche im Frontend (Anzeigen/Erneuern des Codes als UI-Element)". |
| `frontend/src/lib/types.ts:704` | `UserTier = 'free' \| 'standard' \| 'premium'` — Sichtbarkeitsentscheidung (nur Premium-Nutzer?) hängt daran. |
| `frontend/src/lib/api.ts` | Zentraler API-Client (`api.get`, `api.post`, `api.put`, `api.del`) — Fehlerformat `{detail?, error?}`, wie in `save()`/`connectTelegram()` verwendet. |

## Existing Patterns

- **Verbindungsstatus-Karte (Telegram):** Zustand kommt aus `data.profile` beim Laden (`telegramConnected = !!data.profile?.telegram_chat_id`), Aktion per `api.get`/`api.put` mit lokalem `$state`-Update danach. Kein Store, keine Reload-Notwendigkeit.
- **Bestätigungsdialog vor irreversibler Aktion:** `showDeleteAccountDialog`/`showLogoutAllDialog` + `Dialog.Root` aus `$lib/components/ui/dialog` — State-Flag öffnet, Confirm-Handler führt aus. Erneuern des Codes ist ebenfalls irreversibel (alter Code wird sofort entwertet) → gleiches Muster passt.
- **Fehlerbehandlung:** einheitlich `catch (e: unknown) { const body = e as { detail?: string; error?: string }; ... }`.
- **`data-testid`-Konvention:** jedes interaktive/anzeigbare Element bekommt einen stabilen `data-testid` (z.B. `passkey-row`, `tier-change-submit`) — Grundlage für Playwright-E2E und den `fresh-eyes-inspector`.
- **Tier-Sichtbarkeit:** `TIER_OPTIONS`/`tierLabel()` zeigen, wie tier-abhängige UI-Bereiche schon strukturiert sind (Zeile 69-113).

## Dependencies

- **Upstream:** `internal/handler/premium_sms_link_code.go`, `internal/store` (Persistenz des Hash, Scheibe A abgeschlossen, unverändert zu lassen).
- **Downstream:** keine — der Code wird nur vom Garmin-inReach-Gerät des Nutzers manuell abgetippt und per SMS an die Dienstnummer gesendet (`src/services/inbound_sms_reader.py`, Lernpfad). Die UI ist ein reiner Anzeige-/Erneuerungs-Kanal, keine Komponente konsumiert den Code programmatisch weiter.

## Existing Specs

- `docs/specs/modules/fix_2154_premium_sms_verknuepfungscode.md` — Scheibe-A-Spec (Backend), referenziert Scheibe B als Out-of-Scope-Folgearbeit.
- `docs/adr/0049-premium-sms-vierter-kanal.md` — Grundsatzentscheidung Premium-SMS als vierter Kanal.

## Risks & Considerations

- **Geheimnis nur einmal sichtbar:** Der Server gibt den Klartext-Code nur in der `POST`-Antwort zurück. Verlässt der Nutzer die Seite oder lädt neu, ist der Code weg (ein `GET` liefert nie den Code). Die UI muss das unmissverständlich kommunizieren (z. B. "jetzt notieren, wird nicht erneut angezeigt") und darf den Wert nicht in einem Reload-fähigen State ablegen, der den Eindruck von Persistenz erweckt.
- **Erneuern entwertet sofort:** Wer erneuert, sperrt sein Gerät aus, bis der neue Code erneut per inReach gesendet wird (30 Tage TTL der gelernten Rückadresse betrifft nur bereits gelernte Nummern, nicht den Code selbst). Braucht eine Bestätigung analog Logout-All/Delete-Account, kein versehentlicher Klick.
- **Sichtbarkeit einschränken?** `tier === 'premium'` ist der naheliegende Gate — muss in der Spec/Analyse entschieden werden, ob die Karte nur für Premium-Nutzer erscheint oder immer sichtbar ist (mit Hinweis auf fehlende Tier-Berechtigung). Bewusst keine Vorentscheidung hier — Klärung in Phase 2/3.
- **Initialzustand ("exists"):** Entscheidung nötig, ob `GET /api/auth/premium-sms-link-code` in `+page.server.ts` (server-seitig, konsistent mit `profile`) oder client-seitig via `onMount` abgerufen wird. Server-seitig vermeidet Sichtbarkeits-Flackern, passt zum bestehenden `Promise.all`-Muster.
- **Kein Backend-Change nötig** — reine Frontend-Arbeit, LoC-Limit realistisch einhaltbar (~100-150 Zeilen inkl. Tests).
- **Fresh-Eyes-Inspector** ist Pflicht, da UI-Änderung (CLAUDE.md).

## Analysis

### Type
Feature (Standard-Track, Scheibe B von #2154 — reine Frontend-Arbeit, kein Bug).

### Entschiedene offene Fragen aus der Kontext-Phase

1. **Sichtbarkeit:** Karte erscheint **nur bei `data.profile?.tier === 'premium'`** — analog dazu, dass Premium-SMS als Kanal nur für Premium-Nutzer sinnvoll ist (Rückkanal ohne Wirkung für andere Tiers wäre irreführend). Kein Hinweis-Text für Nicht-Premium-Nutzer nötig, die Karte entfällt einfach (Precedent: Tier-abhängige Sichtbarkeit gibt es noch nicht 1:1, aber `TIER_OPTIONS`-Struktur zeigt, dass Tier bereits als UI-Gate-Größe etabliert ist).
2. **Bestätigung vor Erneuern:** Nur nötig, wenn bereits ein Code existiert (`exists === true`) — Erzeugen des allerersten Codes hat nichts zu verlieren, keine Bestätigung nötig. Erneuern eines bestehenden Codes entwertet ihn sofort → Bestätigungsdialog analog `showLogoutAllDialog`-Muster (Zeile 331-425 in `+page.svelte`).
3. **Initialzustand:** `GET /api/auth/premium-sms-link-code` wird in `+page.server.ts` in den bestehenden `Promise.all`-Block aufgenommen (gleiches Cookie-Weiterreiche-Muster wie `profile`), Ergebnis als `premiumSmsLinkCodeExists: boolean` in `data` — vermeidet Flackern beim Erstladen.

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/routes/account/+page.server.ts` | MODIFY | `GET /api/auth/premium-sms-link-code` in den `Promise.all`-Block aufnehmen, `premiumSmsLinkCodeExists` zurückgeben |
| `frontend/src/routes/account/+page.svelte` | MODIFY | Neue Karte/Sektion (nur bei `tier === 'premium'`): Zustand „kein Code" / „Code vorhanden", Button „Code erzeugen"/„Code erneuern" (mit Bestätigungsdialog bei Erneuern), einmalige Klartext-Anzeige nach `POST`-Antwort mit Hinweistext („wird nicht erneut angezeigt"), `data-testid`s nach bestehender Konvention |
| `frontend/src/lib/utils/premiumSmsLinkCodeHelpers.ts` | CREATE | Reine Logik-Funktionen nach `presetCardHelpers.ts`-Vorbild: `shouldShowPremiumSmsLinkCard(tier)`, `needsRenewConfirmation(exists)` — testbar ohne Svelte-Runtime |
| `frontend/src/lib/utils/premiumSmsLinkCodeHelpers.test.ts` | CREATE | `node --test`-Unit-Tests für die Helper-Funktionen |
| `frontend/e2e/*.spec.ts` (Name folgt in Spec-Phase) | CREATE (optional) | Playwright-E2E gegen Staging, falls die Ratsche (`ci_e2e_specs.txt`) es fordert — Entscheidung in Phase 3 |

### Scope Assessment
- Files: 4-5 (2 modify, 2-3 create)
- Estimated LoC: ~120-180 (inkl. Tests) — innerhalb des 250-LoC-Limits ohne `loc_limit_override`
- Risk Level: **LOW** — kein Backend-Change, isolierte Frontend-Karte, kein Datenmodell-Eingriff, kein Cross-User-Pfad (Session-User schon durch `AuthMiddleware`/Cookie sichergestellt)

### Technical Approach

Die Karte folgt strukturell der Telegram-Verbindungskarte, aber mit dem
Passkey-Karten-Bestätigungsmuster für die destruktive Aktion (Erneuern):

1. Serverseitiger Ladezustand (`premiumSmsLinkCodeExists`) bestimmt die
   initiale Anzeige ("Kein Code hinterlegt" vs. "Code hinterlegt, zuletzt
   [Datum falls vorhanden — Backend liefert aktuell nur `exists`, kein
   Zeitstempel; Anzeige bleibt auf Ja/Nein beschränkt]").
2. Klick auf „Code erzeugen" (kein bestehender Code) → sofortiger `POST`,
   Klartext-Code wird in einem client-seitigen `$state` (NICHT persistiert,
   NICHT Teil von `data`) angezeigt, mit Hinweistext.
3. Klick auf „Code erneuern" (bestehender Code) → Bestätigungsdialog → nach
   Bestätigung derselbe `POST`-Aufruf, neuer Code ersetzt die Anzeige.
4. Nach Verlassen der Seite / Reload ist der Klartext-Code weg (by design,
   Backend hält nur den Hash) — das ist Zusicherung, kein Bug, muss aber im
   Fresh-Eyes-Check unmissverständlich wirken.

### Dependencies
- Kein neuer Import außerhalb bestehender Bausteine (`api`, `Dialog`, `Card`, `Btn`).
- Downstream unverändert (Garmin-Gerät tippt den Code manuell ab).

### Open Questions
- [ ] Keine offenen technischen Fragen an den PO — Sichtbarkeit/Bestätigung/Ladezeitpunkt sind oben entschieden. ACs folgen in Phase 3 zur Freigabe.
