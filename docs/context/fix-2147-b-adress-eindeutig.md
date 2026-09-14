# Context: fix-2147-b-adress-eindeutig (#2147 Scheibe B, + #2311-Rest)

## Request Summary
PO-Vorgabe 13.09.: „Eine E-Mail-Adresse darf es im System nur einmal geben." Scheibe A (live, `10141ffb`) hat den
Magic-Link-Pfad gelöst. Scheibe B schließt die übrigen Schreib- und Lesepfade: Registrierung, Profil-Update,
öffentliche Passkey-Registrierung → 409 bei Kollision unter `LockEmailAddress`; Profil-Adresswechsel erst nach
Bestätigung wirksam; einheitlicher Adressbegriff in Python-Lookups und Resend-Allowlist; #2311-Rest
(Adresse als `email` in Konto X und als `mail_to` in Konto Y). Mitnahmen aus Scheibe A: F003, F004.
Scheibe C (nicht hier): Google-OAuth-Verknüpfung, Start-Kollisionszähler, ADR.

## Related Files
| File | Relevance |
|------|-----------|
| `internal/handler/auth.go:31-122` | `RegisterHandler` — Kommentar „keine Uniqueness" (`:74-75`), Adresse roh gespeichert (`:100-101`), 409 nur für Benutzername |
| `internal/handler/auth.go:719-812` | `UpdateProfileHandler` — `email`/`mail_to` änderbar, Wechsel setzt `EmailVerifiedAt=nil` + Bestätigungsmail, RMW ohne Lock, ohne Normalisierung |
| `internal/handler/auth.go:486-542, 827-846, 858-882, 891-985` | `VerifyEmailHandler`, `issueVerificationToken`, `selfHealEmailVerification` (eigene Normalisierung), Resend, `dispatchVerificationMail` |
| `internal/handler/passkey.go:454-578` | Öffentliche Passkey-Registrierung (#466): Adresse im Begin im ChallengeStore, gespeichert im Finish (`:541-542`) roh. Frontend nutzt den Pfad nicht, API aber öffentlich |
| `internal/handler/auth_magic.go:179-257` | Scheibe-A-Muster: Lock → `ResolveAddressOwner` → Anlage normalisiert |
| `internal/store/address_owner.go` | `NormalizeEmailAddress`, `effectiveContactAddress`, `hasLoginCredentials`, `ResolveAddressOwner` |
| `internal/store/address_lock.go` | `LockEmailAddress` (prozesslokal, refcount) — bisher nur Magic-Link |
| `internal/store/user.go:190-240` | Verifikations-Token: ein Slot pro Konto, Token ohne Adressbezug |
| `internal/model/user.go:10-56` | `User` (kein Pending-Feld), `EmailVerificationToken{TokenHash, ExpiresAt}` |
| `internal/store/user.go:473-495`, `internal/handler/telegram_connect.go:176-230` | Go-Telegram-Lookup nimmt ersten Treffer, fail-open; Connect lädt Nutzer vor dem Mutex |
| `src/app/loader.py:1232-1340` | `lookup_user_by_email` (nur `mail_to`, `.lower()` ohne Trim, Mehrfachtreffer → None bereits da), `lookup_user_by_telegram_chat_id` |
| `src/services/inbound_email_reader.py:293`, `inbound_telegram_reader.py:411` | Aufrufer der Python-Lookups (None → `default` = keine Antwort / Registrierungshinweis) |
| `internal/mail/sender.go:204-247, 376-419, 569` | Go-Resend-Allowlist: bestätigte Konten, **`mail_to` UND `email`** freigegeben |
| `src/output/channels/email.py:239-300` | Python-Allowlist, gleiche Regel |
| `frontend/src/routes/account/+page.svelte:286-300, 490-499` | Kontoseite: nur `mail_to` editierbar, Fehler roh angezeigt, keine 409-/„Bestätigung ausstehend"-Behandlung |
| `frontend/src/routes/register/+page.server.ts:39-47` | Jeder 409 → „Benutzername bereits vergeben" |
| `scripts/setup_staging_validator_trip.py:20-47` | Schreibt `mail_to=gregor-test@henemm.com` direkt in `validator-issue110/user.json` (kein Testnutzer laut `IsTestUserID`) |

## Existing Patterns
- **Scheibe A (Magic-Link):** `LockEmailAddress(normalized)` → Auflösung → Schreiben, fail-closed bei Lesefehler, neutrale Antwort ohne Adresse im Log.
- **Telegram-Eindeutigkeit (#2141, `telegram_chat_id_ownership.md`):** Mutex + Prüfung + 409 `chat_id_already_linked` — Vorlage für `email_taken`.
- **Python Mehrdeutigkeit (#2143/#2141):** Mehrfachtreffer → `None` + Log mit Kennungen, echter Treffer schlägt Testkonten.
- **#1517:** Benutzername-Existenz (409) wird vor E-Mail-Validierung geprüft — Reihenfolge bleibt.
- **Testkonten** (`IsTestUserID`) sind aus der Eindeutigkeit ausgenommen (Scheibe A).

## Dependencies
- Upstream: `store.LoadUser/SaveUser/ListUserIDs`, `NormalizeEmailAddress`, `LockEmailAddress`, Mail-Versand (`dispatchVerificationMail`, `SendVerificationMail`), #2271-Login-Gate (`EmailVerifiedAt`).
- Downstream: Frontend Register-/Kontoseite, Inbound-Reader (Mail/Telegram), Resend-Allowlist beider Sprachen, Staging-Validator-Skript, Scheibe C (OAuth nutzt denselben Belegt-Helfer).

## Existing Specs
- `docs/specs/modules/magic_link_adress_eindeutigkeit.md` — Scheibe A; Out-of-Scope (`:147-151`) listet Scheibe B
- `docs/specs/modules/email_verify_vorbereitung_2304.md`, `email_verify_scharfschaltung_2271.md` — Bestätigung & Login-Gate
- `docs/specs/modules/register_page.md`, `fix_1517_validator_register_order.md` — Registrierung
- `docs/specs/modules/user_profile_channels.md` — Profil (draft)
- `docs/specs/modules/telegram_chat_id_ownership.md` — Eindeutigkeits-Vorlage
- `docs/specs/modules/passkey_webauthn.md`, `_archive/modules/issue_466_passkey_register_public.md`
- `docs/context/fix-2147-email-eindeutig.md:78-98` — Scheibenschnitt, Registrierung 409 „mit verständlicher Meldung"

## Risks & Considerations
1. **Token ohne Adressbezug, ein Slot pro Konto.** „Wechsel erst nach Bestätigung" braucht ein Pending-Adressfeld + Adresse im Token (Schema-Änderung `internal/model/user.go` → Read-Modify-Write, Pre-Snapshot-Hook). Heute bestätigt ein Klick, was *gerade* im Profil steht.
2. **`ResolveAddressOwner` passt nicht als „belegt"-Prüfung:** eigenes Konto nicht ausschließbar, leere Adresse = Ambiguous, fail-closed-Lesefehler würde jede Registrierung mit 500 blockieren. Neuer Helfer nötig.
3. **Zwei Sperren beim Profilwechsel** (alte + neue Adresse) → feste Lock-Reihenfolge, sonst Deadlock.
4. **Tippfehler im Profil sperrt beim nächsten Login aus** (#2271-Gate prüft `EmailVerifiedAt`) — mit „wirksam erst nach Bestätigung" entschärft, da alte Adresse bestätigt bleibt.
5. **Allowlist gibt unbewiesenes `email` bestätigter Konten frei** (#2311-Kern im Versandpfad).
6. **Drei verschiedene Adressbegriffe** (Go Magic-Link normalisiert beide Felder; Python nur `mail_to`, ohne Trim; `selfHeal` eigene Kopie; Speichern roh).
7. **Frontend:** Register mappt jeden 409 auf Benutzername; Kontoseite zeigt Codes roh → neue Meldung nötig (UI-Anteil ⇒ Fresh-Eyes + E2E).
8. **Bestandsduplikate auf Prod ungemessen** (Sitzung liest `/var/lib/gregor` nicht). Neue Regel darf bestehende Doppel-Konten nicht aussperren (Profil-Speichern ohne Adressänderung muss weiter gehen).
9. **`validator-issue110`** umgeht die Prüfung per Skript und ist kein Testnutzer — potenzielle Kollision mit `gregor-test@henemm.com` in anderen Konten.
10. **Umfang:** Go (3 Handler + Store-Helfer + Token/Pending) + Python (2 Lookups + Allowlist) + Go-Allowlist + Frontend (2 Seiten) übersteigt 250 LoC deutlich → Schnitt in /20 prüfen.

## Analysis

### Type
Feature / Sicherheits-Härtung (Teil von #2147, Rest #2311)

### Befunde der Analyse (ergänzend zur Bestandsaufnahme)
- **Enumeration durch 409 `email_taken`:** Registrierung ist auf 5/h pro IP begrenzt (`internal/router/router.go:44`), öffentliche Passkey-Registrierung ebenso (`router.go:151`). Scheibenschnitt-Entscheid A (`docs/context/fix-2147-email-eindeutig.md:97`: „Registrierung bekommt 409 mit verständlicher Meldung") bleibt. Profil-PUT ist nur angemeldet (bestätigtes Konto, #2271) erreichbar, aber ohne eigene Ratenbremse → als Risiko in der Spec benennen.
- **Go-Allowlist** (`internal/mail/sender.go`) betrifft nur Auth-Mails; **Python-Allowlist** (`src/output/channels/email.py:705`) ist der Trip-Versandpfad → Verengung kann bestehende Zustellung still blockieren (eigene Risikoklasse).
- **Python-Lookup auf beide Felder** vergrößert den Mehrdeutigkeitszweig; `None` wird in `inbound_email_reader.py:293-296` zu `"default"` und die Mail still als gelesen markiert → braucht eigene ACs (keine `default`-Zuordnung), gehört zum Adressbegriff „bestätigte wirksame Adresse".
- **Staging-Validator:** E2E-Registrierungen nutzen `${username}@example.com` (`frontend/e2e/helpers.ts:137`, `fix-2271-email-verify-gate.spec.ts:31`) → eindeutig pro Kennung; Kennungs-409 greift vorher. `validator-issue110` wird per Skript direkt geschrieben (keine Handler-Prüfung) → neue Schreibregel trifft ihn nicht. Echte Staging-Daten (`/var/lib/gregor-staging`) für diese Sitzung nicht lesbar — Bestandsduplikate weiter ungemessen.
- **Profil ohne Adressänderung** darf nie blocken (Bestandsduplikate): Prüfung nur im bestehenden „Wert geändert"-Zweig (`auth.go:764-775`), eigenes Konto ausgeschlossen.

### Schnitt (Abweichung vom notierten Scheibe-B-Umfang, PO-Vorlage mit der Spec)
Notierter Umfang B: Register/Profil/Passkey-409 + #2311 + Profil-Adresswechsel erst nach Bestätigung + Python-Lookup + Allowlist.
Begründung für Teilung ist **nicht** LoC, sondern zwei getrennte Risikoklassen:
1. **Schema-Änderung** am Konto + adressgebundenes Bestätigungs-Token (Bestandsdaten, Pre-Snapshot-Hook, Alt-Tests `profile_email_verify_test.go:19,46`, 24-h-TOCTOU mit Re-Check beim Bestätigen).
2. **Versandpfad** (Python-Allowlist = Trip-Zustellung) und Inbound-Zuordnung (`default`-Fallback).

- **B1 (dieser Workflow) — „Es entstehen keine neuen Doppel-Adressen":** Belegt-Prüfung im Store (beide Felder, Testkonten ausgenommen, eigenes Konto ausgeschlossen, leere Adresse frei); Registrierung, öffentliche Passkey-Registrierung und Profil-Update prüfen unter `LockEmailAddress` → 409 `email_taken`; Profil sperrt alte + neue Adressen in fester Reihenfolge; F003 (Magic-Link-Übernahme prüft das nachgeladene Konto unter Lock erneut) + F004 (Test, der den Lock bewacht); Normalisierung beim Speichern; Frontend: Registrierung und Kontoseite zeigen verständliche Meldung statt „Benutzername vergeben"/Rohcode.
- **B2 (Folge) — „Eine Adresse gilt erst nach Bestätigung":** Pending-Adresse + adressgebundenes Token, Re-Check beim Bestätigen, Kontoseite „Bestätigung ausstehend"; Python-Lookup und Allowlist Go+Python auf bestätigte wirksame Adresse (#2311-Rest), Mehrdeutigkeit nie `default`. Allowlist ggf. als B3 — Entscheid beim Schnitt von B2.

### Affected Files (B1)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/store/address_owner.go` | MODIFY | Belegt-Prüfung (gemeinsame Iteration mit `ResolveAddressOwner`) |
| `internal/handler/auth.go` | MODIFY | Register + UpdateProfile: Lock, Prüfung, 409, Normalisierung |
| `internal/handler/passkey.go` | MODIFY | Public-Finish: Lock, Prüfung, 409 |
| `internal/handler/auth_magic.go` | MODIFY | F003 Re-Check nach Lock |
| `internal/handler/*_test.go` | CREATE/MODIFY | Zwei-Nutzer-Tests je Pfad, Lock-Test (F004) |
| `frontend/src/routes/register/+page.server.ts` | MODIFY | `email_taken` eigene Meldung |
| `frontend/src/routes/account/+page.svelte` | MODIFY | 409 verständlich anzeigen |
| `docs/reference/api_contract.md`, betroffene Specs | MODIFY | 409 `email_taken` dokumentieren |

### Scope Assessment
- Files: ~8 Code + Tests
- Estimated LoC: ~100 Prod / ~180 Test → `loc_limit_override` voraussichtlich nötig
- Risk Level: HIGH (Auth-Pfad), durch Schnitt ohne Schema-/Versand-Änderung

### Technical Approach
Scheibe-A-Muster wiederverwenden: Lock pro normalisierter Adresse → Belegt-Prüfung (fail-closed bei Lesefehler, konsistent mit A; Risiko „eine unlesbare fremde user.json blockiert Registrierungen" in Spec benennen) → Speichern. Mehrere Adressen immer sortiert und dedupliziert sperren.

### Open Questions
- [ ] PO: Teilung B1/B2 wie oben (mit Spec vorlegen)
