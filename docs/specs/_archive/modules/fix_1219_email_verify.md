---
entity_id: fix_1219_email_verify
type: bugfix
created: 2026-07-10
updated: 2026-07-10
status: draft
version: "1.0"
tags: [mail, security, resend, allowlist, verification]
workflow: 1219-email-verify
---

<!-- Issue #1219, Scheibe 1 — Resend-Allowlist auf E-Mail-Verifikation umstellen -->

# Fix #1219 (Scheibe 1) — Resend-Allowlist auf E-Mail-Verifikation umstellen

## Approval

- [ ] Approved

## Purpose

Die aktuelle #1219-Allowlist (live) entscheidet „echtes Nutzerprofil, das über
Resend erreicht werden darf?" allein anhand einer Namens-Heuristik
(`is_test_user_id`/`IsTestUser`: Substring `test`/`tdd` im Konto-Namen). Ein
Konto mit neutralem Namen wie `e2e-758` entkommt dieser Heuristik — die
zugehörige Adresse `e2e-758@example.com` gilt als „echt" und wird über Resend
zugestellt. Dieser Fix ersetzt die Namens-Heuristik als Eignungskriterium durch
ein neues, explizites Profilfeld `email_verified_at`: nur Profile mit
gesetztem Verifikations-Zeitstempel sind allowlist-fähig. Zusätzlich werden
RFC-2606-reservierte Test-Domains (`example.com/.net/.org`, `.test`,
`.invalid`, `.localhost`, `.example`) als dauerhaftes Sicherheitsnetz IMMER
geblockt — unabhängig vom Verifikationsstatus. Eine Adressänderung am Profil
setzt die Verifikation zurück, damit ein einmal verifiziertes Konto nicht
nachträglich auf eine ungeprüfte Adresse umgebogen werden kann. Der
Self-Service-Bestätigungsflow, der `email_verified_at` normalerweise setzt,
ist NICHT Teil dieser Scheibe (→ Scheibe 2); in dieser Scheibe wird das Feld
für die beiden real existierenden Konten (`henning`, `steffi`) per
Migrationsschritt gesetzt.

## Source

- **File:** `internal/model/user.go` — `type User struct` @10. NEU: Feld
  `EmailVerifiedAt *time.Time \`json:"email_verified_at,omitempty"\`` (Go-API,
  `internal/`). Pointer-Typ analog zu `RequestedAt` @27 (Go's
  `encoding/json`-`omitempty` greift bei `time.Time`-Structs nicht — ein
  Zero-Value würde als `"0001-01-01T00:00:00Z"` statt als „fehlt" serialisiert).
- **File:** `internal/mail/sender.go` — `loadResendAllowlist()` @140,
  `resendAllowlistProfile` @87, `recipientBlocked()` @283 (Go-API,
  `internal/`). Eignungskriterium wird von `isResendAllowlistTestUser()` auf
  `profile.EmailVerifiedAt != ""` umgestellt; NEU: `isReservedTestDomain()`.
- **File:** `src/output/channels/email.py` — `_load_resend_allowlist()` @136,
  `EmailOutput.send()` Resend-Guard @371 (Python-Core, `src/output/`).
  Eignungskriterium wird von `is_test_user_id(user_id, ...)` auf
  `profile.get("email_verified_at")` (truthy) umgestellt; NEU:
  `_is_reserved_test_domain()`.
- **File:** `internal/handler/auth.go` — `UpdateProfileHandler()` @445
  (Go-API, `internal/`). Adressänderungs-Erkennung + `EmailVerifiedAt`-Reset
  VOR `s.SaveUser(*user)` @497.
- **File:** `scripts/migrate_1219_email_verified.py` (NEU, Python-Tooling,
  `scripts/`) — einmaliger, idempotenter Deploy-Migrationsschritt nach dem
  Muster von `scripts/cleanup_1133_testdata.py`: setzt `email_verified_at` für
  die Profile `henning` und `steffi`.

> **Schicht-Hinweis:** Konto-/Profilverwaltung (`user.json`-Schreibpfad) ist
> reines Go (`internal/handler/auth.go`, `internal/store/user.go`,
> `internal/model/user.go`). Python liest `user.json` in dieser Scheibe nur
> passiv (`_load_resend_allowlist`) — kein Python-Schreibpfad für
> `email_verified_at`.

## Estimated Scope

- **LoC:** ~+160 / -20
- **Files:** 7 (`internal/model/user.go` MODIFY, `internal/mail/sender.go`
  MODIFY, `internal/handler/auth.go` MODIFY, `src/output/channels/email.py`
  MODIFY, `scripts/migrate_1219_email_verified.py` CREATE, je eine neue/
  erweiterte Testdatei Python + Go)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `model.User` (`internal/model/user.go:10`) | struct | Trägt das neue Feld `EmailVerifiedAt` |
| `loadResendAllowlist()` / `_load_resend_allowlist()` | function | Bestehender #1219-Allowlist-Loader (Scheibe 0/live) — wird auf das neue Eignungskriterium umgestellt |
| `is_test_user_id()` (`src/app/config.py:30`) / `IsTestUser()` (`internal/mail/sender.go:48`) | function | Bleiben als Funktionen bestehen (u.a. für `Settings.is_test_mode`-Gate und `auth.go:224`), werden aber NICHT mehr als Allowlist-Eignungskriterium aufgerufen |
| `_raw_contains_test_mailbox()` / `rawContainsTestMailbox()` | function | Bleibt unverändert als zusätzliches Fangnetz gegen `gregor-test@`/`gregor-staging@henemm.com` bestehen (kein Ersatz, keine Abhängigkeit vom neuen Kriterium) |
| `UpdateProfileHandler()` (`internal/handler/auth.go:445`) | function | Muss `EmailVerifiedAt` bei Adressänderung zurücksetzen |
| `Store.SaveUser()` (`internal/store/user.go:67`) | function | Persistiert das volle, im Handler bereits per RMW gemergte `User`-Objekt — unverändert, kein eigener Merge-Code nötig, da der Handler mit einem geladenen `*user` arbeitet |
| `scripts/cleanup_1133_testdata.py` | script | Strukturelles Vorbild für den neuen Migrationsschritt (Dry-Run-Default, `--execute`, Backup vor Schreiben, Idempotenz) |
| `data/users/henning/user.json`, `data/users/steffi/user.json` | data | Ziel des Migrationsschritts — einzige real existierenden Konten mit echtem `mail_to` |

## Implementation Details

### 1. Neues Profilfeld (Go)

`internal/model/user.go`: `User` bekommt
`EmailVerifiedAt *time.Time \`json:"email_verified_at,omitempty"\`` — Pointer
analog zu `RequestedAt`, damit ein unverifiziertes Profil im JSON keinen
Zero-Value-Zeitstempel zeigt, sondern das Feld ganz fehlt. Kein Default außer
`nil`.

### 2. Allowlist-Eignungskriterium umstellen (symmetrisch Python + Go)

- **Go** (`loadResendAllowlist()` @140): Der bestehende Skip
  `if isResendAllowlistTestUser(dataDir, userID) { continue }` entfällt als
  Eignungs-Gate. Stattdessen liest `resendAllowlistProfile` (neues Feld
  `EmailVerifiedAt string \`json:"email_verified_at,omitempty"\``) das rohe
  JSON-Feld; ist es leer/fehlend, wird das Profil übersprungen (`continue`) —
  konservativ: im Zweifel NICHT in die Allowlist aufnehmen.
- **Python** (`_load_resend_allowlist()` @136): Der bestehende Skip
  `if is_test_user_id(user_id, data_dir=data_dir): continue` entfällt als
  Eignungs-Gate. Stattdessen wird nach dem Laden von `profile` geprüft:
  `if not profile.get("email_verified_at"): continue`.
- Beide Seiten bleiben fail-soft: fehlende/kaputte `user.json` überspringt nur
  das betroffene Profil, kein Crash des Sendepfads.
- `is_test_user_id()`/`IsTestUser()` werden NICHT gelöscht — sie bleiben für
  ihre bestehenden, anderen Aufrufer (`Settings.is_test_mode`-Gate in
  `email.py` @287, `auth.go:224`) unverändert bestehen. Nur ihre Rolle als
  Allowlist-Eignungskriterium entfällt.

### 3. Reservierte Test-Domains — dauerhafter Hard-Drop (symmetrisch)

Neue Prüfung, die UNABHÄNGIG vom Allowlist-Treffer läuft (auch ein
verifiziertes Profil mit einer reservierten Domain wird geblockt):

- **Python**, neue Funktion `_is_reserved_test_domain(addr: str) -> bool` in
  `email.py`: exakte Domains `{"example.com", "example.net", "example.org"}`
  ODER Domain endet auf eine der TLDs `.test`, `.invalid`, `.localhost`,
  `.example` (case-insensitive, nach Normalisierung).
- **Go**, neue Funktion `isReservedTestDomain(addr string) bool` in
  `sender.go`: identische Logik auf der normalisierten Adresse.
- Einbindung in die bestehende Blocked-Ermittlung: in `EmailOutput.send()`
  (Python @371 ff.) wird die OR-Kette um
  `or any(_is_reserved_test_domain(a) for a in candidates)` erweitert; in
  `recipientBlocked()` (Go @283 ff.) wird pro `part` zusätzlich
  `isReservedTestDomain(normalizedAddrForGuard(part))` geprüft. Ein Treffer
  blockiert den Empfänger, UNABHÄNGIG davon, ob er in der Allowlist steht.

### 4. `UpdateProfileHandler` — Verifikation bei Adressänderung zurücksetzen

`internal/handler/auth.go` @484 ff.: VOR dem Zuweisen von `update.Email`/
`update.MailTo` wird der bestehende Wert verglichen. Nur bei tatsächlicher
Änderung (neuer Wert ≠ alter Wert) wird `user.EmailVerifiedAt` auf `nil`
zurückgesetzt — ein erneutes Senden desselben Werts (No-Op-Update) löst
KEINEN Reset aus:

```go
if update.Email != nil && *update.Email != user.Email {
    user.Email = *update.Email
    user.EmailVerifiedAt = nil
}
if update.MailTo != nil && *update.MailTo != user.MailTo {
    user.MailTo = *update.MailTo
    user.EmailVerifiedAt = nil
}
```

Der Rest des Handlers (Laden via `s.LoadUser`, Mutation im Speicher, Speichern
via `s.SaveUser(*user)`) bleibt unverändert — das ist bereits Read-Modify-
Write auf Go-Struct-Ebene, kein Feldverlust für `SmsTo`/`TelegramChatID`/
`DisplayName`/Passkeys/etc.

### 5. Migration `henning`/`steffi` (Deploy-Schritt, kein Code-Automatismus)

Neues Script `scripts/migrate_1219_email_verified.py`, strukturelles Vorbild
`scripts/cleanup_1133_testdata.py`:

- Feste Positivliste `["henning", "steffi"]` (keine automatische Erkennung
  „echter" Konten — bewusst explizit, analog zum Kontext-Dokument).
- Pro Konto: `data/users/<id>/user.json` per Read-Modify-Write laden, NUR
  `email_verified_at` ergänzen (ISO-8601-UTC-Zeitstempel), alle anderen Felder
  unangetastet lassen, zurückschreiben.
- Idempotent: ist `email_verified_at` bereits gesetzt, wird das Konto
  übersprungen (kein Überschreiben eines bestehenden Zeitstempels ohne
  `--force`).
- Dry-Run per Default (zeigt nur den Änderungsplan), `--execute` führt aus.
  tar.gz-Backup vor jedem `--execute`-Lauf (analog #1133).
- Läuft **pro Host** (Prod, Staging) als User `claude-gregor` im selben
  Deploy-Fenster wie der Code-Rollout dieser Scheibe — beschrieben als
  Deploy-Runbook-Schritt in dieser Spec, NICHT als automatischer Codepfad im
  Request-Handling.

## Expected Behavior

- **Input (Allowlist-Guard):** Sendeaufruf über einen Resend-Host mit einem
  oder mehreren Empfängern (Python: `EmailOutput.send(to=...)`; Go:
  `mail.Send(cfg, to, msg)`/`SendWithFallback`).
- **Output:** Empfänger wird geblockt (Exception/Error VOR SMTP-Dial), wenn
  (a) kein Profil mit dieser Adresse existiert, ODER (b) das Profil existiert,
  aber `email_verified_at` leer/fehlend ist, ODER (c) die Adress-Domain eine
  reservierte Test-Domain ist (auch bei gesetztem `email_verified_at`).
  Zustellung läuft normal weiter, wenn die Adresse zu einem Profil mit
  gesetztem `email_verified_at` gehört UND keine reservierte Test-Domain ist.
  Stalwart-Host: Guard greift nicht, Verhalten unverändert.
- **Input (Profil-Update):** `PATCH`/`PUT` an `UpdateProfileHandler` mit
  geändertem `email` oder `mail_to`.
- **Output:** Neue Adresse wird übernommen, `email_verified_at` wird auf leer
  zurückgesetzt (nur bei tatsächlicher Werteänderung); alle anderen
  Profilfelder bleiben unverändert erhalten.
- **Side effects:** Log-Eintrag bei Allowlist-Blockade (maskierter Empfänger,
  unverändert aus der bestehenden #1219-Implementierung); Migrationsschritt
  schreibt ein tar.gz-Backup vor jeder Ausführung mit `--execute`.

## Acceptance Criteria

- **AC-1:** Given ein Sendeaufruf über einen Resend-Host mit der Adresse eines Profils ohne `test`/`tdd` im Namen und ohne gesetztes `email_verified_at` (`e2e-758@example.com`, der ursprüngliche Bug-Fall) / When der Guard geprüft wird / Then wird der Versand blockiert.
  - Test: Fixture-Profil `e2e-758` (Name ohne `test`/`tdd`, `mail_to=e2e-758@example.com`, `email_verified_at` NICHT gesetzt) anlegen, Sendeaufruf gegen Resend-Host ausführen, prüfen dass `OutputConfigError`/Go-Error geworfen wird und kein SMTP-Connect stattfindet.

- **AC-2:** Given dasselbe unverifizierte Profil, aber mit einer NICHT reservierten, sonst gültigen Domain (z.B. `e2e-758@gmail.com`) / When der Guard geprüft wird / Then wird der Versand ALLEIN wegen des fehlenden `email_verified_at` blockiert — isoliert vom reservierten-Domain-Kriterium.
  - Test: Fixture-Profil mit `mail_to=e2e-758@gmail.com` ohne `email_verified_at`, Sendeaufruf gegen Resend-Host ausführen, prüfen dass geblockt wird, obwohl die Domain nicht reserviert ist.

- **AC-3:** Given ein Fixture-Profil mit einer echten, nicht reservierten Domain UND gesetztem `email_verified_at` / When der Guard geprüft wird / Then wird die Zustellung erlaubt (Regressionsschutz für `henning`/`steffi` nach der Migration).
  - Test: Fixture-Profil mit `mail_to=<echte-domain>` und `email_verified_at=<ISO-Zeitstempel>` anlegen, Sendeaufruf gegen Resend-Host ausführen, prüfen dass kein Guard-Fehler geworfen wird.

- **AC-4:** Given ein Profil mit gesetztem `email_verified_at`, dessen `mail_to`-Adresse aber eine reservierte Test-Domain ist (z.B. `foo@example.com`, `foo@x.test`) / When der Guard geprüft wird / Then wird die Zustellung IMMER blockiert, unabhängig vom Verifikationsstatus.
  - Test: Fixture-Profil mit `mail_to=foo@example.com` und gesetztem `email_verified_at` anlegen, Sendeaufruf gegen Resend-Host ausführen, prüfen dass trotz Verifikation geblockt wird; Wiederholung mit `.test`/`.invalid`/`.localhost`/`.example`-Domain.

- **AC-5:** Given ein verifiziertes Profil, dessen `email`- oder `mail_to`-Feld über `UpdateProfileHandler` auf eine NEUE Adresse geändert wird / When das Update verarbeitet und danach ein Sendeaufruf an die neue Adresse ausgeführt wird / Then ist `email_verified_at` nach dem Update leer, und der Resend-Versand an die neue Adresse wird blockiert, bis erneut verifiziert wird.
  - Test: Profil mit gesetztem `email_verified_at` anlegen, `PATCH` mit geändertem `mail_to` an `UpdateProfileHandler` senden, gespeichertes `user.json` auf leeres `email_verified_at` prüfen, anschließenden Sendeaufruf an die neue Adresse gegen Resend-Host ausführen und Blockade nachweisen.

- **AC-6:** Given ein verifiziertes Profil, bei dem `UpdateProfileHandler` mit demselben (unveränderten) `email`/`mail_to`-Wert aufgerufen wird / When das Update verarbeitet wird / Then bleibt `email_verified_at` unverändert erhalten (kein Reset bei No-Op-Update).
  - Test: Profil mit gesetztem `email_verified_at` und `mail_to=X` anlegen, `PATCH` mit `mail_to=X` (identischer Wert) senden, gespeichertes `user.json` auf unverändertes `email_verified_at` prüfen.

- **AC-7:** Given identische Eingaben (gleiches Fixture-Profil, gleicher Empfänger, gleicher Host) / When der Guard einmal in Python (`email.py`) und einmal in Go (`sender.go`) ausgeführt wird / Then liefern beide Implementierungen dasselbe Verdikt (blockiert/erlaubt) für: unverifiziert, verifiziert+echte Domain, verifiziert+reservierte Domain.
  - Test: Dieselben drei Fixture-Fälle (AC-1/AC-2, AC-3, AC-4) einmal gegen den Python-Guard und einmal gegen den Go-Guard laufen lassen, Verdikte paarweise vergleichen.

- **AC-8:** Given die Profile `henning` und `steffi` VOR dem Migrationsschritt (kein `email_verified_at` gesetzt) / When `scripts/migrate_1219_email_verified.py --execute` gelaufen ist / Then haben beide Profile ein gesetztes `email_verified_at`, alle anderen Profilfelder (`mail_to`, `password_hash`, `passkey_credentials`, etc.) sind unverändert, und ein anschließender Sendeaufruf an die jeweilige `mail_to`-Adresse über Resend wird nicht mehr blockiert.
  - Test: Migrationsscript im Dry-Run gegen ein Fixture-Verzeichnis mit `henning`/`steffi`-Profilen laufen lassen (Plan prüfen, keine Schreibung), dann mit `--execute` ausführen, `user.json` beider Profile vor/nach vergleichen (Diff nur bei `email_verified_at`), erneuten Lauf auf Idempotenz prüfen (kein zweites Überschreiben ohne `--force`).

## Known Limitations

- Ohne Scheibe 2 (Self-Service-Bestätigungsflow) kann `email_verified_at`
  ausschließlich per Migrationsschritt gesetzt werden — es gibt in dieser
  Scheibe keinen Weg für neue Nutzerkonten, sich selbst zu verifizieren. Ein
  neu angelegtes Konto bleibt bis zu einem manuellen Migrationslauf oder bis
  Scheibe 2 von Resend-Versand ausgeschlossen.
- Da die Namens-Heuristik als Eignungskriterium entfällt, könnte theoretisch
  ein Konto mit `test`/`tdd` im Namen allowlist-fähig werden, sofern
  `email_verified_at` gesetzt wäre — in dieser Scheibe geschieht das nirgends
  automatisch (nur die feste Positivliste `henning`/`steffi` wird migriert),
  ist aber als Angriffsfläche für Scheibe 2 zu beachten (dort MUSS der
  Bestätigungsflow selbst verhindern, dass Test-Konten sich verifizieren).
- Die reservierte-Domain-Liste ist eine feste RFC-2606-Liste, kein
  konfigurierbares Set — Erweiterung erfordert einen Code-Change in beiden
  Sprachen.
- Der rohe Fangnetz-Scan (`_raw_contains_test_mailbox`/
  `rawContainsTestMailbox`) bleibt unverändert und deckt weiterhin
  ausschließlich die beiden literalen `gregor-test@`/`gregor-staging@henemm.com`-
  Postfächer ab — er ist kein Ersatz für die neue reservierte-Domain-Prüfung.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Härtung des bestehenden, durch #1122/#1147/#1148/#1219
  etablierten Empfänger-Guard-Musters (Eignungskriterium-Austausch +
  zusätzliche feste Sperrliste) sowie ein additives, optionales Profilfeld —
  kein neuer Architekturbaustein, keine neue Technologieentscheidung.

## Changelog

- 2026-07-10: Initial spec erstellt — Issue #1219 Scheibe 1, PO-Entscheidung 2026-07-10
