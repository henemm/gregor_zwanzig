---
entity_id: adresswechsel_nach_bestaetigung
type: module
created: 2026-09-14
updated: 2026-09-14
status: draft
version: "1.0"
workflow: fix-2147-b2-adresse-nach-bestaetigung
tags: [security, multi-user, auth, issue-2147, issue-2311, epic-2138]
---

# Adresswechsel wird erst nach Bestätigung wirksam (Scheibe B2)

## Approval

- [ ] Approved

## Purpose

Ändert ein bestätigtes Konto seine wirksame Kontaktadresse (`mail_to`, ersatzweise `email`), wirkt
das heute **sofort**: Der alte, bestätigte Nachweis wird verworfen, die neue — noch nie bestätigte —
Adresse übernimmt seine Rolle, und der Login-Gate (#2271) sperrt das Konto aus, bis die neue Adresse
bestätigt ist ("Aussperr-Falle"). B2 macht daraus eine **ausstehende Änderung**: Die alte Adresse
bleibt wirksam und bestätigt, bis der Nutzer den Bestätigungslink an die neue Adresse anklickt; erst
dann übernimmt die neue Adresse. Zusätzlich schließt B2 zwei Folgelöcher derselben Schwäche:
Python `lookup_user_by_email` und die Resend-Allowlist (Go + Python) sollen nur noch die
**bestätigte wirksame Adresse** eines Kontos kennen, nicht mehr jede Adresse in `email` oder
`mail_to` unabhängig vom Bestätigungsstatus (Issue #2147 Scheibe B2, #2311-Rest, Epic #2138).

## Source

- **File:** `internal/handler/auth.go` — **Identifier:** `UpdateProfileHandler`, `VerifyEmailHandler`,
  `ResendVerificationHandler`, `dispatchVerificationMail`, `issueVerificationToken`, `toProfileResponse`
- **File:** `internal/model/user.go` — **Identifier:** `User`, `EmailVerificationToken`
- **File:** `internal/store/address_owner.go` — **Identifier:** `IsAddressTakenByOtherAccount`,
  `EffectiveContactAddress`, `ResolveAddressOwner`
- **File:** `internal/mail/sender.go` — **Identifier:** `loadResendAllowlist`
- **File:** `src/app/loader.py` — **Identifier:** `lookup_user_by_email`
- **File:** `src/services/inbound_email_reader.py` — **Identifier:** `_resolve_settings_for_sender`, `_process_single`
- **File:** `src/output/channels/email.py` — **Identifier:** `_load_resend_allowlist`

## Estimated Scope

- **LoC:** ~+300/-60 Produktivcode — über dem Standard-Limit, `loc_limit_override 500` (Begründung
  siehe „Scheibe bleibt eine Scheibe" unten)
- **Files:** ~12 Produktiv (Go 5, Python 3, Frontend 4), ~10 Testdateien
- **Effort:** high (Auth-Kernpfad + Schema-Änderung + Versand-Guard, Risk Level HIGH)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/store/address_lock.go` → `LockEmailAddress` | Store-Funktion | Prozessweiter Lock je normalisierter Adresse — beim Bestätigen-Klick wiederverwendet, exakt wie beim Profil-Update (B1) |
| `internal/store/address_owner.go` → `IsAddressTakenByOtherAccount`, `EffectiveContactAddress`, `ResolveAddressOwner`, `NormalizeEmailAddress` | Store-Funktionen | Belegt-Prüfung + wirksame Adresse — beim Einlösen erneut aufgerufen, NICHT erweitert um ausstehende Adressen (Entscheidung 5) |
| `internal/store/user.go` → `SaveVerificationToken`/`LoadVerificationToken`/`DeleteVerificationToken` | Store-Funktionen | Ein Token je Konto unter `email_verification.json` — ein neuer Wechsel überschreibt das Token kommentarlos (`user.go:192-193`: "ein zweiter Adresswechsel invalidiert bewusst das erste Token") |
| `internal/model/test_user.go` → `IsTestUserID` | Go-Prädikat | Testkonten bleiben von der Belegt-Prüfung ausgenommen (B1-Muster, unverändert) |
| `docs/specs/modules/adress_eindeutigkeit_schreibpfade.md` | Spec | B1 — Adresslock, Belegt-Prüfung, „geändert"-Prädikate; B2 baut auf denselben Bausteinen auf |
| `docs/specs/modules/magic_link_adress_eindeutigkeit.md` | Spec | A — „bestätigt gilt pro Adresse" (`ResolveAddressOwner`); Known Limitation dieser Spec beschreibt die Lücke zur ausstehenden Adresse |
| `docs/specs/modules/email_verify_scharfschaltung_2271.md` | Spec | Login-Gate `issueSession` — B2 lässt es unverändert, entfernt aber die Ursache der Aussperr-Falle |

## Implementation Details

### Begriffe

- **Wirksame Kontaktadresse:** `EffectiveContactAddress(u)` — `mail_to`, ersatzweise `email`
  (`internal/store/address_owner.go:29-34`), bereits Grundlage von A und B1.
- **Ausstehende Änderung:** zwei neue Felder am `User`: `PendingContactAddress` (die neue, noch nicht
  bewiesene Adresse — bzw. bei „mail_to leeren" die Adresse, die dann aus `email` wirksam würde) und
  `PendingContactField` (`"email"` oder `"mail_to"` — welches Feld beim Einlösen geschrieben wird).
  Solange eine Änderung aussteht, bleiben `email` und `mail_to` **unverändert** auf ihren alten,
  bestätigten Werten stehen — die neue Adresse taucht in KEINEM der beiden Felder auf, solange sie
  nicht bestätigt ist. Das ist entscheidend für `ResolveAddressOwner`/`IsAddressTakenByOtherAccount`
  (beide lesen ausschließlich `email`/`mail_to`, nicht die Pending-Felder — Entscheidung 5): eine
  ausstehende Adresse ist für sie schlicht unsichtbar, taucht also weder als „belegt" noch als
  „bestätigt wirksam" auf. Existiert nur, solange eine Änderung aussteht; danach werden beide Felder
  gelöscht (nicht auf leer gesetzt — Bestandsdaten ohne diese Felder müssen unverändert laden,
  Read-Modify-Write mit Merge).
- **Adressgebundenes Token:** `EmailVerificationToken` (`internal/model/user.go:51-56`) erhält ein
  zusätzliches Feld `Address` (die zu beweisende Adresse, == `PendingContactAddress` bei Ausstellung).
  Persistenz bleibt **ein** Token je Konto unter `email_verification.json`
  (`internal/store/user.go:190-207`) — ein neuer Wechsel überschreibt das bestehende Token
  vollständig, das alte ist damit automatisch entwertet.
- **Alt-Token:** vor diesem Deploy ausgestellte Tokens ohne `Address`-Feld (leerer String nach
  JSON-Unmarshal). Sie gelten weiter, aber nur für ein **unbestätigtes** Konto (siehe Entscheidung 4).

### 1) Profil-Update (`UpdateProfileHandler`)

Die heutige Reset-Logik (`auth.go:911-936`, Kommentarblock ab `:802`) wird durch eine ausstehend-Logik
ersetzt. Grundlage bleiben die B1-Prädikate `emailFieldChanged`/`mailToFieldChanged` (Feld gesendet UND
normalisiert abweichend) und `emailChanged`/`mailToChanged` (zusätzlich nicht leer) — die Belegt-Prüfung
unter `LockEmailAddress` und der frische Reload (`auth.go:821-871`) bleiben unverändert (B1 gilt weiter:
der vom Nutzer eingegebene neue Wert wird VOR jeder weiteren Verarbeitung gegen
`IsAddressTakenByOtherAccount` geprüft — belegt durch ein anderes echtes Konto → `409 email_taken`,
nichts wird abgelegt, exakt wie in B1, AC-10). Erst danach wird unterschieden, WIE die (nicht belegte)
Änderung wirkt:

- **Wirksame Adresse ändert sich nicht** (nur `email` bei gesetztem `mail_to`, oder umgekehrt eine
  Änderung des inaktiven Felds): Feld wird sofort übernommen, **kein** Reset von `EmailVerifiedAt`,
  **keine** Bestätigungsmail. Das ist eine Korrektur der heutigen `auth.go:926-929`/`:933-936`-Logik,
  die den Reset am breiten „Feld geändert"-Prädikat aufhängt und dadurch auch bei unveränderter
  wirksamer Adresse feuert — der zugehörige Begründungskommentar (`auth.go:802-821`, „PO-Korrektur
  nach Freigabe, Sicherheitsrückschritt sonst") beschreibt ab B2 nicht mehr die geltende Regel und
  wird ersetzt.
- **Wirksame Adresse ändert sich, Konto ist unbestätigt** (`EmailVerifiedAt == nil`): wie heute direkt
  — Feld wird geschrieben, keine ausstehende Änderung, `dispatchVerificationMail` läuft (Entscheidung 2).
- **Wirksame Adresse ändert sich, Konto ist bestätigt, neue wirksame Adresse == bisherige wirksame
  Adresse** (z. B. `mail_to` wird geleert und `email` trägt bereits denselben Wert): sofort wirksam,
  Feld wird geschrieben, kein Reset, kein Token, keine Mail (Sonderfall aus Entscheidung 1).
- **Wirksame Adresse ändert sich, Konto ist bestätigt, neue wirksame Adresse ist neu:** `email` und
  `mail_to` werden **NICHT** geschrieben — beide behalten ihre alten, bestätigten Werte, und
  `EmailVerifiedAt` bleibt unverändert gesetzt. Damit sehen Versand, `ResolveAddressOwner`, Python-
  Lookup und beide Allowlists ausschließlich die alte Adresse (AC-1, AC-5) — die B1-Belegt-Prüfung
  lief bereits vorher auf dem eingegebenen Wert, ihr Ergebnis fließt nur nicht mehr in `email`/`mail_to`.
  Stattdessen wird `PendingContactAddress` auf die neue, normalisierte Adresse gesetzt,
  `PendingContactField` auf den Namen des geänderten Felds (`"email"` oder `"mail_to"`; ändern sich
  beide Felder in einem Aufruf und wird dadurch `mail_to` neu gesetzt, ist `mail_to` das maßgebliche
  Feld — ein gleichzeitig geändertes, nicht wirksames `email` fällt unter den ersten Fall oben und
  wird sofort geschrieben), ein adressgebundenes Token erzeugt und die Bestätigungsmail an die neue
  Adresse verschickt. Ein bereits vorhandenes altes Pending/Token wird dabei überschrieben (neuer
  Wechsel ersetzt den alten, `user.go:192-193`).
- **Leeren von `mail_to` bei bestätigtem Konto, sodass `email` wirksam würde:** fällt unter den
  vorigen Fall — `mail_to` bleibt vorerst auf dem alten Wert stehen (wird NICHT geleert),
  `PendingContactField = "mail_to"`, `PendingContactAddress` = der aktuelle, unveränderte Wert von
  `email`. Erst beim Einlösen wird `mail_to` tatsächlich geleert (§2) — das ist die einzige Ausnahme
  vom sonst geltenden „Zielfeld = `PendingContactAddress`".

### 2) Bestätigen-Klick (`VerifyEmailHandler`)

Token-Hash-Vergleich und Ablaufprüfung (`auth.go:531-546`) bleiben unverändert; scheitern sie, bleibt
die Antwort wie heute (`400 invalid token` / `400 token expired`). Danach:

1. **Token trägt keine Adresse (Alt-Token):** kein zusätzlicher Lock (Verhalten identisch zu heute —
   `VerifyEmailHandler` sperrt heute keine Adresse). Konto frisch laden. Besitzt es KEINE ausstehende
   Änderung (Regelfall für ein Alt-Token, Entscheidung 4): `EmailVerifiedAt` wird gesetzt/neu
   gestempelt, Token gelöscht — wie heute. Besitzt es entgegen der Erwartung bereits eine ausstehende
   Änderung (kann nach einem Deploy-Wechsel nicht mehr neu entstehen, wird aber defensiv behandelt):
   das Alt-Token gilt als ungültig, `400 invalid token`, nichts wird geändert.
2. **Token trägt eine Adresse `X`:** unter `store.LockEmailAddress(X)` Konto frisch laden
   (Read-Modify-Write, wie beim B1-Profil-Update).
   - **`X` stimmt NICHT mit `PendingContactAddress` überein** (ein neuerer Wechsel hat die
     ausstehende Änderung bereits ersetzt, AC-3): `400 {"error":"token expired"}`, nichts wird
     geändert — derselbe Code wie ein regulär abgelaufenes Token, kein Sonderfall nötig.
   - **`X` stimmt überein:** erneute Belegt-Prüfung
     `IsAddressTakenByOtherAccount(PendingContactAddress, excludeUserID=<eigene Kennung>)`.
     - Belegt (ein anderes Konto hat die Adresse inzwischen erhalten) → `PendingContactAddress`/
       `PendingContactField` UND Token werden gelöscht, Antwort `409 {"error":"address_taken"}` —
       ein eigenständiger Code, bewusst NICHT `email_taken` (das ist B1's Schreibpfad-Code für den
       AUSLÖSENDEN Versuch) und NICHT `token expired` (das würde fälschlich eine Fristüberschreitung
       suggerieren, obwohl der Link noch gültig war). Nichts wird übernommen (Entscheidung 5).
     - Frei → das Zielfeld wird geschrieben: ist `PendingContactField == "mail_to"` UND
       `PendingContactAddress` gleich dem aktuellen, unveränderten Wert von `email` (der
       „mail_to-leeren"-Sonderfall aus §1), wird `mail_to` auf leer gesetzt; sonst wird
       `PendingContactField` auf `PendingContactAddress` gesetzt. `EmailVerifiedAt` wird NEU
       gestempelt (aktueller Zeitstempel — ein frischer Nachweis wurde gerade erbracht),
       `PendingContactAddress`/`PendingContactField` UND Token werden gelöscht, gespeichert.

### 3) `ResendVerificationHandler` und Staging-Token-Weg

`ResendVerificationHandler` (`auth.go:1050-1072`) prüft heute nur `EmailVerifiedAt == nil`. Ergänzt um:
bestätigtes Konto MIT ausstehender Änderung → `dispatchVerificationMail` an `PendingContactAddress`
(neues Token für dieselbe Adresse). Bestätigtes Konto OHNE ausstehende Änderung → weiterhin nichts
(heutiges Verhalten). `StagingVerificationTokenHandler` (`internal/handler/staging_verify_token.go`)
adressiert ebenfalls `PendingContactAddress`, falls vorhanden, sonst wie heute die wirksame Adresse.

### 4) `selfHealEmailVerification` — unverändert, strukturell sicher

`selfHealEmailVerification` (`auth.go:1017-1041`) bricht bei `user.EmailVerifiedAt != nil` sofort ab
(`:1026-1028`). Ein bestätigtes Konto mit ausstehender Änderung kann diese Funktion also nie erreichen
— sie bleibt unverändert, keine Anpassung nötig.

### 5) Resend-Allowlist Go (`internal/mail/sender.go`, `loadResendAllowlist`)

Heute: Schleife über **beide** Felder `MailTo`/`Email` bei gesetztem `EmailVerifiedAt`
(`sender.go:224-240`). Ab B2: nur `EffectiveContactAddress(profile)` (ein Eintrag statt bis zu zwei)
bei gesetztem `EmailVerifiedAt`. Da Pending-Felder nie in `email`/`mail_to` geschrieben werden (§1),
ist eine ausstehende Adresse hier automatisch NICHT enthalten — keine gesonderte Ausschlussregel
nötig. Zusätzlich (Entscheidung 8): die konfigurierte PO-Adresse (`cfg.PoEmail`, Tier-Antrag-Versand
`auth.go:1288-1320`) wird der Allowlist unabhängig von jedem Nutzerprofil hinzugefügt — sonst hinge
die Zustellbarkeit von Tier-Anträgen davon ab, wie das PO-Konto zufällig seine Profilfelder gesetzt hat.

### 6) Resend-Allowlist Python (`src/output/channels/email.py`, `_load_resend_allowlist`)

Heute: Schleife über `("mail_to", "email")` bei gesetztem `email_verified_at` (`email.py:293-298`). Ab
B2: nur die wirksame Adresse (`mail_to`, ersatzweise `email`) je Profil, analog Go — auch hier
automatisch ohne Pending-Adressen, aus demselben Grund wie in §5. Parität wird über die gemeinsame
Falltabelle `tests/fixtures/mail_recipient_parity/faelle.json` geprüft — ein neuer Fall „Adresse nur
in `email`, `mail_to` abweichend, Konto bestätigt" mit `soll: block` wird ergänzt (bestehende Fälle
wie `mehrfach-adresse-verifiziert` mit `email: "a@b.de, c@d.de"` ohne `mail_to` bleiben unberührt, da
dort `mail_to` leer ist und `email` weiterhin die wirksame Adresse ist).

### 7) Python `lookup_user_by_email` (`src/app/loader.py:1232-1284`)

Heute vergleicht die Funktion nur `profile.get("mail_to")`, unabhängig vom Bestätigungsstatus
(`loader.py:1265`). Ab B2: Treffer nur, wenn die eingehende Adresse der wirksamen Kontaktadresse
(`mail_to`, ersatzweise `email`) entspricht UND `email_verified_at` gesetzt ist — Pendant zu
`ResolveAddressOwner` (Go, Scheibe A). Mehrdeutigkeit (≥2 echte Konten mit derselben wirksamen,
bestätigten Adresse) bleibt `None` mit Log (`loader.py:1272-1279`, unverändert). Eine ausstehende
Adresse taucht hier ebenfalls nicht auf (§1: nie in `mail_to`/`email` geschrieben).

### 8) Inbound-Zuordnung (`src/services/inbound_email_reader.py`)

`_resolve_settings_for_sender` (`:280-297`) liefert heute `"default"` als Rückfall
(`:296`: `lookup_user_by_email(...) or "default"`). Ab B2: `None` statt `"default"`. `_process_single`
(`:118-190`) prüft bereits heute `if _user_id == "default"` (`:131`) und verwirft ohne Antwort
(`log.warning`, `imap.store(..., "\\Seen")`, `return 0`, `:132-134`) — dieselbe Verhaltensweise bleibt
erhalten, nur die Rückgabe wechselt von der Zeichenkette `"default"` auf `None`; das Gate wird im
selben Schritt auf `if _user_id is None` umgestellt (Gate und Rückgabetyp gemeinsam, sonst wird der
Wächter toter Code — Entscheidung 7).

### 9) Frontend

- **Kontoseite** (`frontend/src/routes/account/+page.svelte`): Anzeige „Bestätigung ausstehend für
  `<neu>` — bis dahin gehen Mails weiter an `<alt>`" plus Button „Bestätigungsmail erneut senden"
  (ruft den bestehenden `ResendVerificationHandler`-Endpunkt), sichtbar sobald `data.profile` eine
  ausstehende Adresse trägt (analog zur bestehenden bedingten Anzeige bei `testStatus`,
  `+page.svelte:511-516`). `profileSaveErrorMessage` (`profileSaveError.ts:1-13`) bleibt unverändert
  — sie behandelt Fehler beim Speichern, nicht den neuen Erfolgsfall „ausstehend".
- **Bestätigungsseite** (`frontend/src/routes/verify-email/+page.server.ts`): Der `action`-Handler
  unterscheidet die `400`-Antwort bereits heute nach `body.error === "token expired"` (`:38-40`). Ab
  B2 kommt der neue Code `409 address_taken` (§2) hinzu und bekommt eine eigene Meldung: „Diese
  Adresse gehört inzwischen zu einem anderen Konto. Bitte ändere deine Adresse im Konto erneut." Die
  bestehenden Codes (`token expired`, `invalid token`) behalten ihre bisherige, allgemeinere Meldung.
- **`frontend/src/routes/+layout.svelte:71-73`**: Der Kommentar „nach #2271 eine Aussperr-Falle" bleibt
  sachlich richtig (Passkey-Angebot ändert nie `email`/`mail_to`), wird aber um einen Hinweis ergänzt,
  dass die allgemeine Aussperr-Falle bei Adressänderung seit B2 entfällt — nur damit ein späterer
  Leser den Kommentar nicht als „gilt noch überall" fehlinterpretiert.

### 10) DSGVO-Export — kein Code-Änderungsbedarf

`ExportUser` (`internal/store/user.go:311-323`) zippt `user.json` wholesale durch
`exportFilterUserJSON` (`:427-436`), die generisch **alle** Felder außer einer festen Geheimnisliste
(`exportGeheimnisFelder = []string{"password_hash", "passkey_credentials"}`, `:297`) durchreicht. Die
neuen Pending-Felder erscheinen damit automatisch im Export, ohne Codeänderung an `data_export.go`
oder `user.go`. `email_verification.json` (Token-Hash) steht **nicht** in
`exportErlaubteDateienExakt` (`:263-276`) und wird nie exportiert — das gilt unverändert auch für das
neue adressgebundene Token.

## Expected Behavior

- **Input:** `PUT /api/auth/profile` `{"email"?,"mail_to"?,...}`; `POST /api/auth/verify-email`
  `{"user","token"}`; `POST /api/auth/resend-verification` `{"username"}`.
- **Output:** Profil-Update mit Adressänderung eines bestätigten Kontos liefert weiterhin `200` mit dem
  aktualisierten Profil — `email`/`mail_to` unverändert, zusätzlich die ausstehende Adresse,
  `email_verified` bleibt `true`. Bestätigen: Erfolg `200`; Ablauf/Ersetzung `400 {"error":"token
  expired"}`; Adresse zwischenzeitlich vergeben `409 {"error":"address_taken"}`.
- **Side effects:** Bei einer ausstehenden Änderung bleibt die alte Adresse das einzige Versandziel
  (Trip-Briefings, Compare, Alarme, Inbound-Zuordnung) bis zur Bestätigung. Login bleibt für das Konto
  während der ganzen ausstehenden Phase möglich (kein 403 durch #2271).

## Scheibe bleibt eine Scheibe

B2 ist als **eine** Scheibe PO-freigegeben (siehe `adress_eindeutigkeit_schreibpfade.md`, Abschnitt
„Abweichung vom notierten Scheibenumfang"). Die LoC-Überschreitung wird über
`workflow.py set-field loc_limit_override 500` gelöst, **nicht** durch einen weiteren Schnitt — der
Lesepfad-Anteil (Python-Lookup, Allowlists) ist klein gegenüber dem Schema-/Handler-Kern, und ein
Schnitt würde die Schema-Änderung (Pending-Felder + adressgebundenes Token) künstlich von ihren
einzigen Aufrufern trennen.

## Acceptance Criteria

- **AC-1:** Given ein bestätigtes Konto ändert im Profil seine wirksame Kontaktadresse (`mail_to`,
  ersatzweise `email`) auf eine noch nicht vergebene neue Adresse / When das Profil-Update
  abgeschickt wird / Then bleibt die alte Adresse weiter wirksam — Trip-Briefings und ein
  Passwort-Reset gehen weiterhin an die alte Adresse, der Nutzer kann sich unverändert anmelden (kein
  403), an die neue Adresse geht eine Bestätigungsmail, und die Profil-Antwort zeigt die neue Adresse
  als „ausstehend" an, nicht als aktiv.
  - Test: Handler-Test gegen echten `store.Store`; nach dem Update `email_verified_at` weiterhin
    gesetzt, `mail_to`/`email` byteidentisch zum Zustand vor dem Update, Pending-Feld trägt die neue
    Adresse.

- **AC-2:** Given ein bestätigtes Konto hat eine ausstehende Adressänderung und eine gültige
  Bestätigungsmail wurde verschickt / When der Nutzer den Bestätigungslink anklickt / Then wird die
  neue Adresse ab sofort die wirksame Kontaktadresse, das Konto bleibt bestätigt (der Zeitstempel
  wird dabei neu gesetzt), die ausstehende Änderung ist verschwunden, und derselbe Link kann kein
  zweites Mal etwas bewirken.
  - Test: Handler-Test; nach dem Einlösen `mail_to`/`email` = neue Adresse, `email_verified_at`
    gesetzt (neuer Zeitstempel als vor dem Einlösen), zweiter Einlöseversuch mit demselben Token
    scheitert (`400 token expired`, da Pending-Feld bereits gelöscht).

- **AC-3:** Given ein bestätigtes Konto hat bereits eine ausstehende Adressänderung / When der Nutzer
  im Profil erneut eine (andere) neue Adresse einträgt, bevor er den ersten Link angeklickt hat /
  Then ersetzt die zweite Änderung die erste vollständig, und der ursprüngliche Bestätigungslink
  bewirkt danach nichts mehr — er wird mit `400 {"error":"token expired"}` abgewiesen, exakt wie ein
  regulär abgelaufener Link.
  - Test: Handler-Test; zwei Profil-Updates hintereinander, danach Einlösen des ersten,
    zwischenzeitlich entwerteten Tokens ergibt `400 token expired`, das Konto bleibt bei der
    zweiten ausstehenden Adresse.

- **AC-4:** Given ein bestätigtes Konto hat eine gesetzte `mail_to`-Adresse / When der Nutzer
  `mail_to` im Profil auf leer setzt, sodass danach `email` wirksam würde / Then wird `email` NICHT
  sofort und automatisch als bestätigt übernommen — `mail_to` bleibt vorerst auf dem alten Wert
  stehen —, sondern erst nach Einlösen eines Bestätigungslinks wird `mail_to` tatsächlich geleert.
  Ausnahme: trägt `email` bereits genau die aktuelle wirksame Adresse, wirkt das Leeren sofort ohne
  erneute Bestätigung.
  - Test: zwei Handler-Tests — einmal mit abweichendem `email` (`mail_to` bleibt nach dem Profil-Update
    unverändert gesetzt, Pending-Feld zeigt auf `email`-Wert, erst nach Einlösen ist `mail_to` leer),
    einmal mit `email` == aktueller wirksamer Adresse (sofort geleert, kein Reset, kein Pending).

- **AC-5:** Given ein bestätigtes Konto hat eine ausstehende Adressänderung, die noch nicht bestätigt
  wurde / When man in diesem Zustand (a) den Adress-Resolver (Go `ResolveAddressOwner` bzw. Python
  `lookup_user_by_email`) für die NEUE Adresse abfragt, (b) die Resend-Allowlist (Go und Python)
  prüft und (c) das tatsächliche Versandziel für dieses Konto ermittelt / Then zeigt keine der drei
  Prüfungen die neue Adresse als bestätigt-wirksam für dieses Konto — sie taucht in keiner Allowlist
  auf, der Resolver ordnet sie diesem Konto nicht zu, und der Versand adressiert weiterhin die alte
  Adresse.
  - Test: kombinierter Handler-/Store-Test: nach einer ausstehenden Änderung liefert
    `ResolveAddressOwner(neueAdresse)`/`lookup_user_by_email(neueAdresse)` NICHT dieses Konto, und
    `loadResendAllowlist`/`_load_resend_allowlist` enthalten die neue Adresse nicht, die alte
    weiterhin.

- **AC-6:** Given ein bestätigtes Konto ändert im Profil ein Adressfeld, das NICHT die wirksame
  Kontaktadresse ist (z. B. `email`, während `mail_to` gesetzt bleibt) / When das Update abgeschickt
  wird / Then wird die Änderung sofort gespeichert, es gibt keine ausstehende Änderung, kein Reset
  von `email_verified_at`, und keine Bestätigungsmail wird verschickt.
  - Test: Handler-Test; `email` sofort im gespeicherten Zustand, `email_verified_at` unverändert,
    kein Mail-Versand-Aufruf (Test-Naht zählt Aufrufe).

- **AC-7:** Given ein unbestätigtes Konto (z. B. frisch registriert, Bestätigungsmail noch nicht
  eingelöst) / When der Nutzer im Profil seine Adresse ändert / Then wirkt die Änderung wie bisher
  sofort — keine ausstehende Änderung, an die neue Adresse geht eine Bestätigungsmail.
  - Test: Handler-Test; `mail_to`/`email` sofort auf dem neuen Wert, kein Pending-Feld gesetzt.

- **AC-8:** Given zwei verschiedene, angemeldete Konten A und B / When Konto A eine
  Adressänderung auf `x@beispiel.de` beantragt (ausstehend, noch nicht bestätigt) und danach Konto B
  sich erfolgreich mit genau `x@beispiel.de` registriert oder sein eigenes Profil darauf ändert /
  Then gelingt B's Vorgang ganz normal — eine ausstehende Änderung zählt nicht als belegt. Löst A
  anschließend seinen (weiterhin gültigen) Bestätigungslink für `x@beispiel.de` ein, wird das mit
  `409 address_taken` abgelehnt, A behält seine alte Adresse, und B bleibt unverändert.
  - Test: Zwei-Nutzer-Handler-Test in genau dieser Reihenfolge; nach A's gescheitertem Einlösen ist
    B's Konto byteidentisch, A trägt weiterhin die alte wirksame Adresse, A's Pending-Feld ist gelöscht.

- **AC-9:** Given Konto A hat eine ausstehende Änderung auf eine Adresse, die gerade noch frei ist,
  und Konto B versucht sich exakt in diesem Moment auf dieselbe Adresse zu ändern oder zu
  registrieren, während A gleichzeitig seinen Bestätigungslink einlöst / When beide Vorgänge
  gleichzeitig laufen / Then gewinnt am Ende genau einer der beiden — es gibt zu keinem Zeitpunkt zwei
  Konten mit derselben wirksamen, bestätigten Adresse.
  - Test: Go-Test mit zwei Goroutinen hinter einer Startschranke (Adresssperre + frischer Reload wie
    bei B1); am Ende trägt genau ein Konto die Adresse als bestätigt wirksam.

- **AC-10:** Given eine gewünschte Adressänderung zeigt auf eine Adresse, die bereits einem anderen
  echten Konto gehört (in `email` ODER `mail_to`, unabhängig von dessen Bestätigungsstatus) / When
  das Profil-Update abgeschickt wird / Then bleibt die B1-Ablehnung (`409 email_taken`) bestehen — es
  entsteht in diesem Fall gar keine ausstehende Änderung, exakt wie in B1 beschrieben.
  - Test: Zwei-Nutzer-Handler-Test; Antwort `409 email_taken`, kein Pending-Feld gesetzt, kein Token
    erzeugt.

- **AC-11:** Given ein bestätigtes Konto mit ausstehender Änderung möchte die Bestätigungsmail erneut
  anfordern / When der Endpunkt „Erneut senden" aufgerufen wird / Then geht die neue Mail an die
  AUSSTEHENDE Adresse, nicht an die aktuell wirksame. Fordert dasselbe Konto OHNE ausstehende Änderung
  „Erneut senden" an, obwohl es bereits bestätigt ist, passiert weiterhin nichts.
  - Test: zwei Handler-Tests (mit/ohne ausstehende Änderung); Mail-Versand-Test-Naht zeigt im ersten
    Fall genau einen Aufruf mit der ausstehenden Adresse, im zweiten Fall keinen Aufruf.

- **AC-12:** Given ein Bestätigungs-Token wurde vor dieser Änderung ausgestellt (kein
  adressgebundenes Feld, „Alt-Token") und gehört zu einem zum Ausstellungszeitpunkt unbestätigten
  Konto / When dieses Alt-Token eingelöst wird / Then funktioniert die Bestätigung wie bisher — die
  aktuelle wirksame Adresse des Kontos wird bestätigt.
  - Test: Handler-Test, der ein Token ohne `Address`-Feld direkt in `email_verification.json`
    ablegt (simuliert Vor-Deploy-Zustand); Einlösen bestätigt das Konto normal.

- **AC-13:** Given der Python-Kommandoweg (`lookup_user_by_email`) soll einer eingehenden
  Absenderadresse ein Konto zuordnen / When die Adresse zwar in einem Profil steht, aber entweder nur
  im Feld `email` bei abweichendem `mail_to`, oder das Konto insgesamt unbestätigt ist / Then erfolgt
  KEINE Zuordnung (Rückgabe `None`).
  - Test: Python-Unit-Test mit drei Profil-Varianten (Adresse nur im Nebenfeld; unbestätigtes Konto;
    korrekt wirksame + bestätigte Adresse) — nur der dritte Fall liefert das Konto.

- **AC-14:** Given eine E-Mail von einer unbekannten, mehrdeutigen oder unbestätigten
  Absenderadresse trifft im Kommando-Postfach ein / When der Inbound-Reader sie verarbeitet / Then
  wird kein Kommando ausgeführt, keine Antwortmail verschickt, und die Mail wird als gelesen markiert
  — es gibt dabei zu keinem Zeitpunkt einen Rückfall auf ein Konto „default".
  - Test: Python-Unit-Test (verhaltensbasiert, kein Dateiinhalt-Check) mit einem Mail-Fixture von
    einer nicht zuordenbaren Adresse; `TripCommandProcessor.process` wird NICHT aufgerufen, keine
    Antwortmail-Methode wird aufgerufen.

- **AC-15:** Given die Resend-Allowlist (Go und Python) soll prüfen, ob eine Zieladresse zustellbar
  ist / When eine Adresse nur im Feld `email` eines Kontos mit abweichendem, verschiedenem `mail_to`
  steht / Then wird diese Adresse in BEIDEN Sprachen blockiert — nur die bestätigte wirksame
  Kontaktadresse ist erlaubt.
  - Test: Go- und Python-Unit-Test je einen Fall pro Sprache, plus ein gemeinsamer Fall in
    `tests/fixtures/mail_recipient_parity/faelle.json` (neuer Eintrag „Adresse nur in email, mail_to
    abweichend"), geprüft über `internal/mail/recipient_parity_test.go` UND das Python-Pendant.

- **AC-16:** Given die konfigurierte Betreiber-Adresse (`GZ_PO_EMAIL`) empfängt einen
  Tier-Änderungsantrag / When der Versand über den Resend-Host läuft / Then wird diese Adresse NICHT
  von der Allowlist blockiert — unabhängig davon, welches Profil gerade welche Felder trägt.
  - Test: Go-Handler-/Mail-Test; Tier-Antrag mit `cfg.PoEmail` gesetzt auf eine Adresse, die in
    KEINEM Nutzerprofil vorkommt, wird trotzdem nicht vom Guard blockiert.

- **AC-17:** Given ein bestätigtes Konto hat eine ausstehende Adressänderung / When der Nutzer die
  Kontoseite im Browser öffnet / Then sieht er den Hinweis „Bestätigung ausstehend für `<neue
  Adresse>` — bis dahin gehen Mails weiter an `<alte Adresse>`" und eine Möglichkeit, die
  Bestätigungsmail erneut zu senden. Löst er anschließend erfolglos einen zwischenzeitlich
  vergebenen Link ein, sieht er auf der Bestätigungsseite den Hinweis „Diese Adresse gehört
  inzwischen zu einem anderen Konto", keinen rohen Fehlercode.
  - Test: Frontend-Test (`node --test`) für die Bedingungsanzeige der Kontoseite und für die
    Fehlertext-Zuordnung der Bestätigungsseite (`address_taken` → eigene Meldung, `token expired`/
    `invalid token` → bisherige Meldung); Live (Staging, `/e2e-verify`): Kontoseite mit einem über
    den Staging-Token-Weg erzeugten ausstehenden Zustand zeigt den Hinweis im Browser.

- **AC-18:** Given ein Konto wurde vor dieser Änderung angelegt und besitzt keine Pending-Felder /
  When sein Profil geladen oder gespeichert wird (ohne Adressänderung) / Then verhält es sich exakt
  wie vorher — kein Fehler, keine Migration nötig, `user.json` bleibt ansonsten unverändert
  (Read-Modify-Write mit Merge). Der DSGVO-Export eines Kontos MIT ausstehender Änderung enthält die
  Pending-Felder automatisch, ohne dass die Export-Logik selbst geändert werden musste; das
  Bestätigungs-Token wird dabei nie mit-exportiert.
  - Test: Handler-Test mit einem Bestandskonto ohne Pending-Felder (Profil-Update ohne
    Adressänderung, Antwort `200`, Datei byteidentisch bis auf das geänderte Feld); Export-Test mit
    einem Konto MIT ausstehender Änderung, entpacktes `user.json` enthält die Pending-Felder,
    `email_verification.json` fehlt im Archiv.

## Known Limitations

- **Magic-Link (`resolveMagicLinkAccount`/`ResolveAddressOwner`) sieht ausstehende Adressen nicht.**
  Ein anderes Konto kann eine gerade ausstehende Adresse per Magic-Link oder Registrierung
  zwischenzeitlich beanspruchen, bevor der ursprüngliche Nutzer seinen Bestätigungslink einlöst — der
  Einlöse-Vorgang fängt das über die erneute Belegt-Prüfung (`409 address_taken`, AC-8/AC-9) ab,
  verliert aber die ausstehende Änderung ersatzlos. Kein aktives Datenleck, aber ein unbequemer
  Nutzerpfad; bleibt für Scheibe C offen.
- **Resend-Allowlist auf Staging nicht live messbar.** Staging versendet über Stalwart, nicht über
  Resend-Hosts (`with_user_profile`, `src/app/config.py:394-397`: `force_test` greift für
  `env == "staging"`) — die engere Allowlist ist nur über den Kern-Test bewiesen, nicht per
  `/e2e-verify`.
- **Bestandsduplikate bleiben unaufgelöst.** Tragen bereits heute zwei Konten dieselbe Adresse als
  bestätigte wirksame Kontaktadresse (vor B1/B2 entstanden), ändert B2 daran nichts — Auflösung ist
  Scheibe C.
- **Bestätigungsmail-Zustellung ans Test-Postfach bleibt gesperrt** (#1219, Egress-Sperre #1337) —
  Staging-Nachweis für den neuen Ablauf läuft über `StagingVerificationTokenHandler`
  (`internal/handler/staging_verify_token.go`), nicht über echten IMAP-Empfang.
- **Vor-Deploy-Tokens für bestätigte Konten mit ausstehender Änderung gibt es strukturell nicht** —
  die Alt-Token-Regel (AC-12) greift ausschließlich für unbestätigte Konten, weil die
  Pending-Funktion vor diesem Deploy nicht existierte.
- **Der Prozess-Lock (`LockEmailAddress`) ist prozesslokal**, wie bereits in A/B1 dokumentiert — kein
  verteiltes Locking über mehrere Instanzen.

## Out of Scope

- **Scheibe C:** Google-OAuth verknüpft ein bestehendes bestätigtes Konto statt ein Zweitkonto
  anzulegen; Kollisionszähler beim Serverstart für Bestandsduplikate; übergreifendes ADR
  „Adress-Eindeutigkeit"; Auflösung der Magic-Link-Lücke aus „Known Limitations".
- **Mail-Text der Bestätigungsmail gegen fremd ausgelöste Bestätigung** (z. B. ein Hinweis „falls du
  das nicht warst") ist NICHT Teil dieser Scheibe — die bestehende `BuildVerificationMail` bleibt
  textlich unverändert.
- **Empfängerlisten und Kanal-Auswahl** (SMS, Telegram, Premium-SMS) sind nicht betroffen — B2 ändert
  ausschließlich die E-Mail-Kontaktadresse und ihre Bestätigung.
- **Bestehende Doppel-Adressen** werden durch B2 nicht aufgelöst oder gemeldet.

## Test Plan

- **Go (`internal/handler/`, `internal/store/`, `internal/mail/`):** neue/erweiterte Testdatei(en)
  nach Verhalten benannt (z. B. `profile_email_pending_test.go`,
  `verify_email_pending_address_test.go`), echter `store.Store` auf `t.TempDir()`, kein
  Mock-Theater. AC-9 braucht einen echten Zwei-Goroutinen-Test mit Startschranke (F004-Muster aus
  B1). `recipient_parity_test.go` wird um den neuen Fall aus `faelle.json` ergänzt.
- **Python (`tests/tdd/`):** `lookup_user_by_email` (AC-13), Inbound-Gate (AC-14, verhaltensbasiert:
  Aufruf-Zählung von `TripCommandProcessor.process` und der Antwortmail-Methode, kein
  String-in-Datei-Check), `_load_resend_allowlist` (AC-15).
- **Frontend (`node --test`, KEIN Vitest — `frontend/package.json` gegenprüfen):**
  Kontoseiten-Anzeige, Fehlertext der Bestätigungsseite (AC-17).
- **Zwei-Nutzer-Pflicht (CLAUDE.md):** AC-8, AC-9, AC-10, AC-15 laufen alle mit zwei verschiedenen
  Nutzern/Konten.
- **Live (Staging, `/e2e-verify`):** Ausstehende Änderung über `StagingVerificationTokenHandler`
  erzeugen, Kontoseite zeigt den Hinweis, Einlösen über den Token-Weg macht die neue Adresse wirksam;
  Resend-Allowlist bleibt auf dieser Ebene ungetestet (siehe Known Limitations).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** B2 trifft keine neue Grundsatzentscheidung, sondern vervollständigt das in Scheibe A
  etablierte Prinzip „bestätigt gilt pro Adresse" um den fehlenden Zeitpunkt (wann eine Änderung
  wirksam wird) und zieht die beiden Folgelöcher (Python-Lookup, Allowlist) nach. Das übergreifende
  ADR „Adress-Eindeutigkeit" folgt weiterhin erst mit Scheibe C.

## Changelog

- 2026-09-14: Initial spec created (Issue #2147 Scheibe B2, #2311-Rest, Epic #2138)
