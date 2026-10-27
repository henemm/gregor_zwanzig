# Context: fix-2147-b2-adresse-nach-bestaetigung

Issue #2147 (Scheibe B2) + #2311-Rest · Epic #2138 · Vorgänger: Scheibe A (`10141ffb`), B1 (`84d3200e`)

## Request Summary

Eine geänderte Konto-Adresse (`mail_to`/`email`) soll erst **nach Bestätigung** wirksam werden; bis dahin
bleibt die alte bestätigte Adresse in Kraft. Zusätzlich sollen die Python-Zuordnung `lookup_user_by_email`
und die Resend-Allowlist (Go + Python) nur noch die **bestätigte wirksame Adresse** (mail_to, ersatzweise
email) kennen — Fortführung von „bestätigt gilt PRO ADRESSE" aus Scheibe A.

## Ist-Stand (Kernbefund)

Bestätigung gilt heute **für das Konto, nicht für eine Adresse**:

- `UpdateProfileHandler` (`internal/handler/auth.go:759-971`) überschreibt `Email` (`:924`) / `MailTo`
  (`:931`) sofort und setzt `EmailVerifiedAt = nil` (`:927/:934`), danach `dispatchVerificationMail`
  (`:965`) an die schon neue Adresse.
- Token (`issueVerificationToken`, `auth.go:986`; `model.EmailVerificationToken`, `internal/model/user.go:53`)
  = `TokenHash` + `ExpiresAt`, **ohne Adresse**; Link `/verify-email?user=<id>&token=<t>`
  (`internal/mail/verify.go:13`).
- `VerifyEmailHandler` (`auth.go:509-565`) stempelt nur `EmailVerifiedAt = now` — kein Adressvergleich,
  kein Lock, keine Belegt-Neuprüfung.
- `ResendVerificationHandler` (`auth.go:1050`) versendet nur bei `EmailVerifiedAt == nil`.
- **Folge mit Login-Gate #2271:** Adresswechsel ⇒ 403 `email_not_verified` bei jedem Login
  („Aussperr-Falle", Kommentar `frontend/src/routes/+layout.svelte:70-74`); einzige Ausnahme
  `issueSessionWithoutVerificationGate` beim Passwortwechsel (`auth.go:196-201`, `:1225-1229`).
- Ein Konzept „wartende Adresse" (`pending_email` o. ä.) existiert **nirgends** im Code.

## Related Files

| File | Relevance |
|------|-----------|
| `internal/model/user.go` | `User` (Email, MailTo, EmailVerifiedAt), `EmailVerificationToken` — Schema-Änderung (Pre-Snapshot-Hook) |
| `internal/handler/auth.go` | UpdateProfile, VerifyEmail, ResendVerification, dispatchVerificationMail, issueVerificationToken, selfHealEmailVerification, Login-Gate `hasVerifiedEmail`/`issueSession`, toProfileResponse |
| `internal/store/user.go:194-232` | Token-Persistenz `email_verification.json` |
| `internal/store/address_owner.go` | `EffectiveContactAddress`, `ResolveAddressOwner`, `IsAddressTakenByOtherAccount` — wartende Adresse zählt heute nicht mit |
| `internal/store/address_lock.go` | `LockEmailAddress` (Pflicht beim Bestätigen-Klick) |
| `internal/handler/auth_magic.go` | `resolveMagicLinkAccount` — sieht wartende Adressen nicht |
| `internal/handler/staging_verify_token.go` | Staging-Testweg für Token, ohne Adressbezug |
| `internal/handler/auth_oauth.go:172` | einziger Aufrufer `selfHealEmailVerification` |
| `internal/mail/sender.go:204-240, :393` | Go-Allowlist `loadResendAllowlist` (Schleife über MailTo UND Email), Aufrufer `recipientBlocked` |
| `internal/mail/verify.go` | Bestätigungslink/-mail |
| `src/app/loader.py:1232` | `lookup_user_by_email` — vergleicht nur `mail_to`, ignoriert Bestätigung |
| `src/services/inbound_email_reader.py:217-247, :293-296` | einziger Lookup-Aufrufer; `or "default"`-Rückfall |
| `src/output/channels/email.py:239-298, :451-470, :700-760` | Python-Allowlist (MailTo UND Email), Aufrufer Fallback-Guard + Resend-Zweig |
| `src/app/config.py:398, :416-418` | `with_user_profile` übernimmt nur `mail_to` + `email_verified_at` |
| `src/services/scheduler_dispatch_service.py:428-432` | Compare-Versand an `mail_to` |
| `frontend/src/routes/account/+page.svelte` | editiert nur `mail_to` (`:491-509`), kein „Bestätigung ausstehend" |
| `frontend/src/routes/account/profileSaveError.ts` | Fehlertexte Profil-Speichern |
| `frontend/src/lib/components/shared/versand-tab/channelConnectionStatus.ts`, `sendTargetLabel.ts` | Anzeige „bestätigt / nicht bestätigt" |
| `frontend/src/routes/verify-email/+page.server.ts`, `login/+page.server.ts` | Einlöse-Seite, Login-Hinweis |
| `scripts/backfill_2271_email_verified.py` | hat alle Bestandskonten gestempelt |

## Existing Patterns

- **Adresssperre + frischer Reload + Belegt-Prüfung** (B1): sortiertes `LockEmailAddress` → `LoadUser` →
  `IsAddressTakenByOtherAccount` → 409 `email_taken`. Wiederzuverwenden beim Bestätigen-Klick.
- **„Bestätigt gilt pro Adresse"** (Scheibe A, `ResolveAddressOwner:84`): bestätigt = `EmailVerifiedAt` gesetzt
  UND Adresse == `EffectiveContactAddress`.
- **Mehrdeutigkeit ⇒ keine Zuordnung** (Python #2141/#2143): `None` + Log statt erstem Treffer; echte vor Test-Nutzern.
- **Read-Modify-Write mit Merge** für `user.json` (CLAUDE.md, BUG-DATALOSS #102).
- Go/Python-Allowlist sind **symmetrische Pendants** mit Paritätstests (`recipient_parity_test.go`).

## Dependencies

- **Upstream:** Store (`LoadUser`/`SaveUser`, Adresslock), `mail.SendVerificationMail`, Login-Gate #2271,
  Python `get_data_root`/`is_test_user_id`.
- **Downstream:** Login/Magic-Link/Passkey/OAuth (Gate liest `EmailVerifiedAt`), Python-Versand aller Kanäle
  E-Mail (Trip-Briefing, Compare, Alarme — Ziel `settings.mail_to`), Inbound-Mail-Kommandos, Frontend
  Kontoseite + Versand-Tab-Statusanzeige, DSGVO-Export (`data_export_test.go:46`).

## Existing Specs

- `docs/specs/modules/adress_eindeutigkeit_schreibpfade.md` (B1) — Out of Scope `:182-202` **beschreibt B2
  verbindlich**: ausstehende Adresse + adressgebundenes Token + erneute Prüfung beim Klick, Kontoseite
  „Bestätigung ausstehend", Lookup auf bestätigte wirksame Adresse (nie still `default`), Allowlist Go+Python enger.
- `docs/specs/modules/magic_link_adress_eindeutigkeit.md` (A) — „bestätigt gilt pro Adresse"; Out of Scope
  `:145-151` nennt noch „Lookup **über beide Felder**" und „Mail-Text der Bestätigungsmail gegen fremd
  ausgelöste Bestätigung". ⚠️ **Widerspruch zu B1** (dort: nur bestätigte wirksame Adresse) — Analyse muss auflösen.
- `docs/specs/modules/email_verify_scharfschaltung_2271.md` — Login-Gate zentral in `issueSession`.
- `docs/specs/modules/email_verify_vorbereitung_2304.md` — Backfill, Selbstheilung, Resend, Staging-Token.
- Archiv: `docs/specs/_archive/modules/fix_1219_resend_allowlist.md` (Allowlist = Vereinigung mail_to ∪ email),
  `fix_1219_email_verify.md`, `fix_1219_verify_flow_2a*.md`, `fix_1226_register_verify.md`,
  `issue_1235_stalwart_recipient_guard.md`.

## Existing Tests

- Go `internal/handler/`: `profile_email_verify_test.go`, `profile_verify_send_test.go`, `profile_test.go`,
  `address_uniqueness_write_paths_test.go`, `verify_email_test.go`, `verify_resend_test.go`,
  `staging_verify_token_test.go`, `email_verify_selbstheilung_test.go`, `login_email_verify_gate_test.go`,
  `magic_link_address_ownership_test.go`, `magic_link_takeover_recheck_test.go`, `register_mail_to_fallback_test.go`
- Go `internal/mail/`: `sender_allowlist_test.go`, `sender_verified_allowlist_test.go`, `recipient_guard_test.go`,
  `recipient_parity_test.go`, `verify_send_test.go`, `fallback_guard_test.go`
- Python `tests/tdd/`: `test_resend_verified_allowlist.py`, `test_resend_recipient_allowlist.py`,
  `test_issue_1147_resend_recipient_invariant.py`, `test_inbound_email_sender_authentication.py`,
  `test_issue_1009_1019_inbound_robustness.py`
- Frontend: `routes/account/__tests__/profile_save_error.test.ts`,
  `shared/__tests__/channel_connection_status.test.ts`, `versand-tab/__tests__/sendTargetLabel.test.ts`,
  `routes/verify-email/page-server.test.ts`, E2E `e2e/fix-2271-email-verify-gate.spec.ts`

## Risks & Considerations

1. **Schema-Änderung** (neues Feld für ausstehende Adresse + Adresse im Token): Pre-Snapshot-Hook, Merge statt
   Replace, Bestandsdaten ohne Feld müssen unverändert laden; Python verwirft unbekannte Felder still (ok).
2. **Eindeutigkeit der ausstehenden Adresse:** zählt sie bei der Belegt-Prüfung mit? Ohne Mitzählen können zwei
   Konten dieselbe Adresse gleichzeitig ausstehend halten — Bestätigen-Klick braucht dann Lock + Neuprüfung
   (Verlierer: definierte Abweisung). Mit Mitzählen: Reservierungs-/Blockade-Angriff auf fremde Adressen.
3. **Magic-Link auf eine ausstehende Adresse** legt heute ein neues `m-`-Konto an → spätere Kollision beim
   Bestätigen des anderen Kontos.
4. **Allowlist enger:** Python versendet ohnehin nur an `mail_to` → Briefings nicht blockiert. Echtes Risiko:
   `PO_EMAIL` (Tier-Antrag, `auth.go:1311`) und Adressen, die nur im `email`-Feld eines Kontos mit abweichendem
   `mail_to` stehen. Prod-Daten aus dem Worktree nicht lesbar → Bestandsprüfung nur über andere Instanz/Weg.
5. **Backfill #2271** hat Bestandskonten pauschal gestempelt — nie bestätigte `mail_to` gelten als bestätigt;
   bleibt so (keine rückwirkende Entwertung, sonst stille Zustellungsausfälle).
6. **Aussperr-Falle** verschwindet mit B2 — Passwortwechsel-Ausnahme und Frontend-Kommentar anpassen, nicht
   stehen lassen. Leeren von `mail_to` (wirksam wird eine nie bestätigte `email`) braucht eine eigene Regel.
7. **ResendVerification** muss bestätigte Konten mit ausstehender Adresse bedienen; Staging-Token und
   `selfHealEmailVerification` brauchen eine Regel für die ausstehende Adresse.
8. **Inbound `or "default"`-Rückfall** (`inbound_email_reader.py:293-296`) widerspricht der CLAUDE.md-Pflicht
   (nie `default`) — mit B2 schließen.
9. **Staging-Messbarkeit:** Staging versendet über Stalwart, Resend-Allowlist greift nur in Prod; Test-Postfach
   `gregor-test@` gehört keinem Profil. Bestätigungsmail-Zustellung auf Staging nur über Staging-Token-Weg messbar.
10. **LoC-Limit 250** wird bei Schema + Handler + Python + Frontend sehr wahrscheinlich überschritten → in der
    Analyse Schnitt oder `loc_limit_override` begründen.

## Analysis

### Type
Feature (Sicherheits-/Multi-User-Härtung, Fortsetzung #2147 Scheibe B2 + #2311-Rest)

### Verifizierte Korrekturen an Agenten-Aussagen
- Specs A (`magic_link_adress_eindeutigkeit.md`) und B1 (`adress_eindeutigkeit_schreibpfade.md`) sind **freigegeben und live** (A `10141ffb`, B1 `84d3200e`) — keine Entwürfe. Widerspruch „Lookup über beide Felder" (A, Out of Scope) vs. „bestätigte wirksame Adresse" (B1, neuer, auf A aufbauend): **B1 gilt** — Lookup über beide Felder würde „bestätigt gilt pro Adresse" brechen.
- Inbound-`"default"` ist **kein aktives Leck**: `_process_single` (`inbound_email_reader.py:131`) verwirft `default` ohne Reply. Wird trotzdem umgebaut (CLAUDE.md-Pflicht), aber **Gate und Rückgabe gemeinsam** — sonst wird der Wächter toter Code.
- Tier-Antrag an `cfg.PoEmail` läuft über `SendWithFallback → Send → recipientBlocked → loadResendAllowlist` (`sender.go:377-420`, `auth.go:1319`) — es gibt **keinen** anderen Mechanismus. Prod-Wert laut `fix_1555_tier_antrag_sichtbarkeit.md:77` `henning@henemm.com`, Default in `config.go:42` ist ein anderer.
- Passwort-Reset geht bereits an die wirksame Kontaktadresse (`auth.go:359/404`) → von der Verengung nicht betroffen.

### Technische Entscheidungen (Tech Lead, nicht PO-Frage)
1. **Maßgeblich ist die wirksame Kontaktadresse** (`mail_to`, ersatzweise `email`). Eine Profiländerung, die sie **nicht** ändert (z. B. nur `email` bei gesetztem `mail_to`), wird wie heute sofort geschrieben (B1-Eindeutigkeit gilt weiter), **ohne** Bestätigungs-Reset. Eine Änderung, die sie **ändert** (neues `mail_to`, Leeren von `mail_to` ⇒ `email` würde wirksam), wird bei einem **bestätigten** Konto als **ausstehende Änderung** abgelegt; die alte Adresse bleibt wirksam, `EmailVerifiedAt` bleibt, Login bleibt möglich (Aussperr-Falle entfällt). Sonderfall: neue wirksame Adresse == bisherige wirksame Adresse ⇒ sofort, kein Reset.
2. **Unbestätigte Konten** (nie bestätigt) schreiben weiterhin direkt (nichts zu schützen, Tippfehler korrigierbar).
3. **Revision einer B1-Regel (explizit in Spec):** B1 ließ Leeren von `mail_to` sofort wirken und `EmailVerifiedAt` zurücksetzen. B2 ersetzt das durch „ausstehend bis Bestätigung". Invariante bleibt erhalten und wird als AC geprüft: **eine nie bestätigte Adresse wird nie wirksam-und-bestätigt**.
4. **Token adressgebunden:** `EmailVerificationToken` erhält die zu beweisende Adresse. Einlösen übernimmt die ausstehende Änderung nur, wenn Token-Adresse == aktuell ausstehende wirksame Adresse; neuer Wechsel ersetzt die ausstehende Änderung und entwertet das alte Token. **Alt-Tokens ohne Adresse** (vor Deploy ausgestellt) gelten weiter für die wirksame Adresse eines **unbestätigten** Kontos (Registrierungslinks überleben den Deploy).
5. **Ausstehende Adressen zählen NICHT als belegt** (sonst Reservierungsangriff ohne Zustellnachweis). Beim Einlösen unter `LockEmailAddress` + frischem Reload erneute Belegt-Prüfung; Verlierer bekommt definierte Abweisung, Token verbraucht, nichts übernommen.
6. **Erneut senden** bedient auch bestätigte Konten mit ausstehender Änderung (an die ausstehende Adresse). Staging-Verify-Token adressiert die ausstehende Adresse, falls vorhanden.
7. **Python `lookup_user_by_email`:** Treffer nur bei Adresse == wirksame Kontaktadresse UND `email_verified_at` gesetzt (Pendant zu `ResolveAddressOwner`); Mehrdeutigkeit ⇒ keine Zuordnung. Inbound: `None` statt `"default"`, Gate in `_process_single` im selben Schritt umgestellt; Test prüft **Verhalten** (unbekannter Absender ⇒ nicht verarbeitet, keine Antwort).
8. **Resend-Allowlist Go + Python:** nur wirksame Kontaktadresse bestätigter Konten; Paritäts-Falltabelle um „Adresse nur in `email`, `mail_to` abweichend" erweitert. **Go erlaubt zusätzlich die konfigurierte PO-Adresse** (Betreiber-Konfiguration, unabhängig von Profildaten) — sonst hinge die Zustellung von Tier-Anträgen davon ab, wie das PO-Konto seine Felder gerade gesetzt hat, und wäre aus dieser Sitzung nicht vorab messbar.
9. **Kontoseite:** zeigt „Bestätigung ausstehend für X — bis dahin gehen Mails weiter an Y" + erneut senden. Bestätigungsseite zeigt Erfolg bzw. „Adresse inzwischen vergeben".
10. **Profil-Antwort** liefert die ausstehende Adresse (nie Token/Zeitstempel); DSGVO-Export enthält sie (liegt in `user.json`).
11. **Known Limitation:** Magic-Link/`ResolveAddressOwner` ignorieren ausstehende Adressen — ein anderes Konto kann die Adresse zwischenzeitlich beanspruchen; beim Einlösen greift dann Entscheidung 5.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/model/user.go` | MODIFY | ausstehende Adressänderung am `User`; `Address` am `EmailVerificationToken` |
| `internal/handler/auth.go` | MODIFY | UpdateProfile (ausstehend statt sofort), VerifyEmail (Adressvergleich, Lock, Neuprüfung, Übernahme), ResendVerification, dispatchVerificationMail/issueVerificationToken (Zieladresse), toProfileResponse |
| `internal/handler/staging_verify_token.go` | MODIFY | Token für ausstehende Adresse |
| `internal/store/user.go` / `address_owner.go` | MODIFY | Token-Persistenz mit Adresse; ggf. Helfer „wirksame Adresse nach Änderung" |
| `internal/mail/sender.go` | MODIFY | Allowlist nur wirksame Adresse; PO-Adresse erlaubt |
| `src/app/loader.py` | MODIFY | `lookup_user_by_email` wirksam + bestätigt |
| `src/services/inbound_email_reader.py` | MODIFY | `None` statt `"default"` + Gate |
| `src/output/channels/email.py` | MODIFY | Allowlist nur wirksame Adresse |
| `frontend/src/routes/account/+page.svelte` (+ Profiltyp, Fehlertexte) | MODIFY | Anzeige ausstehend + erneut senden |
| `frontend/src/routes/verify-email/+page.server.ts` / `+page.svelte` | MODIFY | Ergebnis „vergeben" |
| `frontend/src/routes/+layout.svelte:70-74` | MODIFY | veralteten Aussperr-Kommentar korrigieren |
| Tests Go/Python/Frontend (s. Existing Tests) | MODIFY/CREATE | inkl. Zwei-Nutzer-Test, Paritätstabelle, Alt-Token |

### Scope Assessment
- Files: ~12 Produktiv + ~10 Test
- Estimated LoC: ~+300/-60 Produktivcode ⇒ `loc_limit_override 500` (begründet, **kein** weiterer Schnitt: B2 ist als eine Scheibe PO-freigegeben; der Lesepfad-Anteil ist klein)
- Risk Level: HIGH (Schema, Auth, Versand-Guard)

### Technical Approach
Reihenfolge in der Umsetzung: (1) Modell + Token-Adresse + Alt-Token-Kompatibilität, (2) UpdateProfile/VerifyEmail/Resend + Zwei-Nutzer-Rennen, (3) Allowlist Go/Python + PO-Adresse + Parität, (4) Python-Lookup + Inbound-Gate, (5) Frontend.

### Dependencies
- Baut auf B1 (Adresslock, Belegt-Prüfung, Normalisierung) und A („bestätigt gilt pro Adresse") auf; berührt ADR-0066 (Login-Gate) nur positiv (kein Aussperren mehr).
- Staging: Resend-Allowlist greift dort nicht (Stalwart) ⇒ Allowlist nur im Kern belegbar; Bestätigungsfluss über Staging-Verify-Token messbar.

### Open Questions
- keine an den PO — alle Designfragen oben entschieden; Freigabe erfolgt über die ACs der Spec.
