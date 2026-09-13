---
entity_id: magic_link_adress_eindeutigkeit
type: module
created: 2026-09-13
updated: 2026-09-13
status: draft
version: "1.1"
workflow: fix-2147-email-eindeutig
tags: [security, multi-user, magic-link, auth, issue-2147, issue-2311, epic-2138]
---

# Magic-Link: Adress-Eindeutigkeit und Konto-Auflösung (Scheibe A)

## Approval

- [ ] Approved

## Purpose

Eine E-Mail-Adresse darf im System nur einem Konto gehören (PO-Vorgabe 2026-09-13). Dieses Modul
legt fest, wie der Magic-Link-Anmeldeweg (`internal/handler/auth_magic.go`) eine per Code
nachgewiesene Adresse **genau einem** Konto zuordnet — statt wie bisher den ersten Treffer über das
Feld `email` zu nehmen. Es schließt die Kernlücke aus Issue #2147 (Magic-Link liefert eine Sitzung
in ein fremdes Konto) und den Zweitkonto-Schaden aus Issue #2311 (Magic-Link mit der
`mail_to`-Adresse legt ein leeres Zweitkonto an). Nur der Magic-Link-Pfad ist Gegenstand dieser
Spec — siehe „Out of Scope".

## Source

- **File:** `internal/handler/auth_magic.go` — **Identifier:** `MagicLinkRequestHandler`,
  `MagicLinkVerifyHandler`, `createMagicLinkUser`
- **File:** `internal/store/user.go` — **Identifier:** `FindUserByEmail` (wird ersetzt durch
  `ResolveAddressOwner`), neue Hilfsfunktion `NormalizeEmailAddress`
- **File:** `internal/store/address_lock.go` (neu) — **Identifier:** `LockEmailAddress`

## Estimated Scope

- **LoC:** ~110 Prod / ~200 Test (`FindUserByEmail` hat außerhalb von `auth_magic.go` und seinen
  Tests keinen Aufrufer — per Volltextsuche geprüft)
- **Files:** 3 Prod, 2 bestehende Test-Dateien angepasst, 1 neue Test-Datei, 1 Doku
- **Effort:** medium (Auth-Kernpfad, Risk Level HIGH)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/model/test_user.go` → `IsTestUserID` | Go-Prädikat | Testnutzer werden bei der Auflösung übersprungen (Muster #2141) |
| `internal/store/sessions.go` → `ClearSessions` | Store | Entfernt Sitzungen eines zugangslosen, unbestätigten Kontos vor der Übernahme |
| `internal/mail/sender.go` → `SendVerificationMail` | Versand | Adressnachweis-Mails an noch nicht bestätigte Adressen (#1219 Sonderpfad) |
| `internal/handler/auth.go` → `issueSession`, `hasVerifiedEmail` | Handler | Bestätigungs-Gate aus #2271 — bleibt unverändert |
| `internal/handler/telegram_connect.go` → `telegramConnectMu` | Muster | „Prüfung + Speichern unter einem Lock" (#2141) |
| `docs/specs/modules/email_verify_scharfschaltung_2271.md` | Spec | Login-Gate, darf nicht umgangen werden |
| `docs/specs/modules/telegram_chat_id_ownership.md` | Spec | Vorlage Eindeutigkeit + Besitz |

## Implementation Details

### Begriffe

- **Adresse X:** eingegebene Adresse, normalisiert per `NormalizeEmailAddress` (TrimSpace + ToLower).
  Einzige Normalisierungsquelle; die inline-Kopien in `auth_magic.go` werden darauf umgestellt.
- **Inhaber von X:** jedes Nicht-Testkonto (`!IsTestUserID`), dessen `email` ODER `mail_to`
  (normalisiert) gleich X ist.
- **Bestätigter Inhaber von X:** Inhaber mit `EmailVerifiedAt != nil` UND X ist seine
  **wirksame Kontaktadresse** (`mail_to`, ersatzweise `email`, wenn `mail_to` leer). Begründung:
  `EmailVerifiedAt` bestätigt genau diese eine Adresse (`src/app/config.py:225`,
  `selfHealEmailVerification`, `dispatchVerificationMail`). Ein bestätigtes Konto, das X nur im
  anderen Feld trägt, hat X nie nachgewiesen.
- **Zugangsdaten eines Kontos:** `PasswordHash != ""` ODER `len(PasskeyCredentials) > 0` ODER
  `OAuthSub != ""`.

### 1) `internal/store/user.go`

```go
type AddressResolution int
const (
    AddressFree      AddressResolution = iota // kein Inhaber
    AddressOwned                              // genau ein Konto, siehe Regeln
    AddressAmbiguous                          // keine eindeutige Zuordnung möglich
)
func NormalizeEmailAddress(s string) string
func (s *Store) ResolveAddressOwner(address string) (*model.User, AddressResolution, error)
```

Regeln (Reihenfolge verbindlich):

| Lage | Ergebnis |
|---|---|
| genau 1 bestätigter Inhaber | `AddressOwned` → dieses Konto |
| ≥ 2 bestätigte Inhaber | `AddressAmbiguous` |
| 0 bestätigte, 0 Inhaber | `AddressFree` |
| 0 bestätigte, genau 1 Inhaber, X ist seine wirksame Kontaktadresse, **keine** Zugangsdaten | `AddressOwned` → dieses Konto |
| alles andere (1 Inhaber mit Zugangsdaten; 1 Inhaber, der X nur im Nebenfeld trägt; ≥ 2 Inhaber) | `AddressAmbiguous` |

`FindUserByEmail` entfällt (einziger Aufrufer ist `auth_magic.go`); die bestehenden Store-Tests in
`internal/store/user_magic_test.go` werden auf `ResolveAddressOwner` umgestellt.

### 2) `internal/store/address_lock.go` (neu)

`func LockEmailAddress(normalizedAddress string) (unlock func())` — paketweiter Lock je Adresse,
damit Scheibe B/C denselben Lock verwenden.

### 3) `MagicLinkRequestHandler`

- Legt **kein Konto** mehr an, ruft keine Auflösung auf. `otpEntry` verliert `userID`.
- Antwort bleibt immer `200 {"status":"ok"}`.
- Versand des Codes über `mail.SendVerificationMail` statt `mail.SendWithFallback`: Der Code ist
  ein Adressnachweis wie die Bestätigungsmail. Über `Send` greift die Resend-Empfänger-Allowlist
  (`internal/mail/sender.go:393`, nur Adressen **bestätigter** Konten) — ohne diesen Wechsel erreicht
  der Code eine noch kontolose Adresse auf Resend-Hosts nie (am Code belegt, nicht live gemessen).
  Missbrauchsschutz bleibt der IP-Limiter (5 / 15 Min, `router.go:102`).

### 4) `MagicLinkVerifyHandler`

1. Code-Vergleich wie heute; der OTP-Eintrag wird am Erfolgsmoment mit
   `otpStore.CompareAndDelete` verbraucht — nur der Aufruf, dem das gelingt, fährt fort, ein
   zeitgleicher zweiter erhält `400 invalid_or_expired_code`.
2. Unter `store.LockEmailAddress(X)`: `ResolveAddressOwner(X)`.
   - `err` → 500.
   - `AddressAmbiguous` → `log.Printf` nur mit Konto-IDs bzw. Anzahl, **nie** mit X;
     Antwort `400 {"error":"invalid_or_expired_code"}` (von außen nicht von falschem Code
     unterscheidbar); kein Speichern, keine Sitzung.
   - `AddressFree` → `createMagicLinkUser` (ID `m-{8hex}`, `email = mail_to = X`,
     `EmailVerifiedAt = jetzt`).
   - `AddressOwned`, Konto unbestätigt (nur möglich: zugangslos, X wirksame Kontaktadresse) →
     Read-Modify-Write: `LoadUser` frisch, `EmailVerifiedAt = jetzt`, `SaveUser`; danach
     `ClearSessions` (VOR `issueSession`, sonst würde die neue Sitzung mitgelöscht).
   - `AddressOwned`, Konto bestätigt → keine Änderung am Konto.
3. `issueSession` für das aufgelöste Konto. Das Gate aus #2271 bleibt unverändert und lässt in
   allen drei Erfolgsfällen durch.

`selfHealEmailVerification` wird aus dem Magic-Link-Pfad entfernt (seine Wirkung übernimmt 4.2);
für den Google-Pfad (`auth_oauth.go`) bleibt die Funktion unverändert.

## Expected Behavior

- **Input:** `POST /api/auth/magic-link` `{"email"}`; `POST /api/auth/magic-link/verify`
  `{"email","code"}`.
- **Output:** Anfordern immer `200`. Einlösen: Erfolg `200` + Session-Cookie; Mehrdeutigkeit,
  falscher/abgelaufener/verbrauchter Code → dieselbe neutrale `400`.
- **Side effects:** Kontoanlage erst beim Einlösen. Ein zugangsloses unbestätigtes Konto verliert
  beim Übernehmen seine alten Sitzungen. Konten mit Passwort, Passkey oder Google-Verknüpfung werden
  nie per Magic-Link übernommen und nie verändert. Log bei Mehrdeutigkeit ohne Klartext-Adresse.

## Out of Scope

- **Scheibe B** (#2147 + #2311): Eindeutigkeit bei Registrierung, Profiländerung und
  Passkey-Registrierung (verständliche Meldung „Adresse bereits vergeben"), Normalisierung beim
  Speichern, Adresswechsel im Profil erst nach Bestätigung wirksam, Python
  `lookup_user_by_email` über beide Felder, Resend-Allowlist nur mit wirksamen Kontaktadressen,
  Mail-Text der Bestätigungsmail gegen fremd ausgelöste Bestätigung.
- **Scheibe C:** Google-Login verknüpft bestehendes bestätigtes Konto statt Zweitkonto,
  Kollisionszähler beim Start (ohne Adressen), ADR „Adress-Eindeutigkeit".
- Issue #2147 bleibt bis Scheibe C offen.

## Acceptance Criteria

- **AC-1:** Given für eine Adresse gibt es noch kein Konto / When jemand dafür einen Anmeldecode
  anfordert / Then bekommt er wie bisher eine neutrale Erfolgsantwort und der Code wird an diese
  Adresse verschickt, es entsteht dabei aber noch KEIN Konto.
  - Test: Handler-Test gegen echten `store.Store`; Kontenanzahl vor/nach dem Anfordern gleich;
    der Versand läuft über den Bestätigungsmail-Weg (Allowlist-freier Sonderpfad).

- **AC-2:** Given für eine Adresse gibt es noch kein Konto und ein Code wurde angefordert / When der
  Code korrekt eingelöst wird / Then entsteht genau jetzt genau ein neues, bestätigtes Konto mit
  dieser Adresse, und die Anmeldung erfolgt in dieses Konto.
  - Test: Handler-Test; vorher kein, nachher genau ein neues Konto, Sitzung gehört zu ihm.

- **AC-3:** Given Konto B hat die Adresse `opfer@x.de` als bestätigte Kontaktadresse, und ein
  anderes, ebenfalls bestätigtes Konto A trägt `opfer@x.de` nur zusätzlich im Feld `email`
  (Kontaktadresse von A ist eine andere) / When jemand den Code für `opfer@x.de` einlöst / Then
  landet er in Konto B — nie in A, unabhängig von der Reihenfolge der Konten im Verzeichnis — und A
  bleibt unverändert (Kernlücke #2147).
  - Test: Zwei-Nutzer-Handler-Test in beiden Anlage-Reihenfolgen; Sitzung gehört zu B, A's
    `user.json` byteidentisch.

- **AC-4:** Given ein bestätigtes Konto A trägt `opfer@x.de` nur im Feld `email` (Kontaktadresse
  von A ist eine andere), und sonst hat niemand diese Adresse / When jemand den Code für
  `opfer@x.de` einlöst / Then erfolgt KEINE Anmeldung und KEIN neues Konto, sondern die neutrale
  Fehlermeldung — A wird nicht verändert.
  - Test: Handler-Test; `400`, kein `Set-Cookie`, Kontenanzahl unverändert, A byteidentisch.

- **AC-5:** Given ein bestehendes Konto hat `email=alt@x.de` und die bestätigte Kontaktadresse
  `neu@x.de` (#2311) / When jemand den Code für `neu@x.de` einlöst / Then landet er in diesem
  bestehenden Konto; es entsteht kein Zweitkonto, und die übrigen Sitzungen des Kontos bleiben
  bestehen.
  - Test: Handler-Test; Kontenanzahl unverändert, Sitzung gehört zum bestehenden Konto, vorhandene
    Sitzung weiterhin gültig.

- **AC-6:** Given ein Konto hat die noch unbestätigte Kontaktadresse `neu@x.de` und besitzt ein
  Passwort (typisch: Adresse im Profil geändert, Bestätigungsmail noch nicht geklickt) / When
  jemand den Code für `neu@x.de` einlöst / Then erfolgt keine Anmeldung, kein Zweitkonto, und das
  Konto bleibt samt Passwort, Passkeys und Sitzungen unverändert.
  - Test: Handler-Test; Varianten Passwort, Passkey, Google-Verknüpfung — jeweils `400`, Konto
    byteidentisch, Kontenanzahl unverändert.

- **AC-7:** Given ein unbestätigtes Konto ohne Passwort, Passkey und Google-Verknüpfung hat
  `opfer@x.de` als Kontaktadresse und eine laufende Sitzung / When der Adressinhaber den Code für
  `opfer@x.de` einlöst / Then wird dieses Konto bestätigt, die alte Sitzung ungültig, und nur der
  Einlösende erhält eine neue Sitzung; Trips, Orte und Einstellungen im Konto bleiben erhalten.
  - Test: Handler-Test mit vorbereiteter Sitzung und Beispiel-Trip-Datei; danach
    `EmailVerifiedAt` gesetzt, alte Sitzung nicht mehr in `LoadSessions`, neue vorhanden,
    Trip-Datei byteidentisch.

- **AC-8:** Given zwei Konten haben `opfer@x.de` beide als bestätigte Kontaktadresse
  (Bestandsduplikat) / When jemand den Code dafür einlöst / Then erfolgt keine Anmeldung und kein
  neues Konto, die Antwort ist die neutrale Fehlermeldung, und das Server-Log nennt die Adresse
  nicht im Klartext.
  - Test: Handler-Test; `400`, kein `Set-Cookie`, Log-Mitschnitt enthält die Adresse nicht.

- **AC-9:** Given ein gültiger Code für eine kontolose Adresse / When zwei Einlöse-Anfragen
  gleichzeitig eintreffen / Then wirkt der Code nur einmal: genau ein Konto entsteht, genau eine
  Anfrage ist erfolgreich, die andere erhält die neutrale Fehlermeldung.
  - Test: Go-Test mit zwei Goroutinen hinter einer Startschranke, mehrfach wiederholt; danach
    genau ein neues Konto.

- **AC-10:** Given nur ein Testkonto (z. B. `tg-live-e2e`) trägt die eingelöste Adresse / When der
  Code eingelöst wird / Then wird das Testkonto ignoriert: Anmeldung in ein neu angelegtes reguläres
  Konto, nie in das Testkonto.
  - Test: Handler-Test; Sitzung gehört nicht zum Testkonto, Testkonto byteidentisch.

- **AC-11:** Given zwei Konten tragen dieselbe Adresse (Bestandsduplikat) und haben je ein Passwort
  / When sich jeder Inhaber mit seinem Benutzernamen und Passwort anmeldet / Then gelingt das für
  beide unverändert — die neue Regel wirkt nur beim Magic-Link.
  - Test: Handler-Test mit zwei bestätigten Konten gleicher Adresse, Passwort-Login für beide.

## Test Plan

- Neue Datei `internal/handler/magic_link_address_ownership_test.go` (AC-1 bis AC-11), echter
  `store.Store` auf `t.TempDir()`, kein Mock-Theater. Versandnachweis AC-1 über die vorhandene
  Test-Naht des Mail-Pakets (keine echte Zustellung).
- Anzupassen: `TestMagicLinkRequestHandler_CreatesNewUserForUnknownEmail`,
  `TestMagicLinkRequestHandler_UsesExistingUserForKnownEmail` (`auth_magic_test.go`) und
  `TestFindUserByEmail*` (`internal/store/user_magic_test.go`) — sie prüfen das alte Verhalten.
- Live (Staging, `/e2e-verify`): Code anfordern für eine neue Adresse im Test-Postfach-Umfeld,
  Zustellung per IMAP prüfen, Einlösen → Konto entsteht.

## Documentation

- `docs/reference/api_contract.md` — Abschnitt Magic-Link: Anlage beim Einlösen, neutrale
  Mehrdeutigkeits-Antwort, Adressbegriff.

## Known Limitations

- **Anmeldecode für eine Adresse, die nur im Nebenfeld steht, führt nicht mehr ins Konto.** Wer
  sich mit `alt@x.de` registriert, später `neu@x.de` als Kontaktadresse bestätigt und dann einen
  Code für `alt@x.de` einlöst, wird abgewiesen (heute: Anmeldung). Grund: Das System kann nicht
  unterscheiden, ob `alt@x.de` je nachgewiesen wurde — genau diese Lage nutzt der Angriff aus
  #2147. Passwort, Passkey und Code für `neu@x.de` funktionieren weiter.
- **Unbestätigtes Konto mit Zugangsdaten sperrt den Magic-Link für diese Adresse**, bis die
  Bestätigung erfolgt oder Scheibe B das Belegen fremder Adressen verhindert. Keine Übernahme,
  kein Datenverlust.
- **Mehrdeutigkeit verbraucht den Code** (Verbrauch vor der Auflösung); neuer Versuch braucht einen
  neuen Code.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Scheibe A trifft keine Grundsatzentscheidung über Kontoübernahme; das
  übergreifende ADR „Adress-Eindeutigkeit" folgt mit Scheibe C, wenn alle Anmeldewege feststehen.

## Changelog

- 2026-09-13: Initial spec created (Issue #2147, #2311, Epic #2138)
- 2026-09-13: v1.1 — „bestätigt" pro Adresse (wirksame Kontaktadresse); keine Übernahme von Konten
  mit Zugangsdaten statt Zugangs-Löschung; Code-Versand über Bestätigungsmail-Weg
