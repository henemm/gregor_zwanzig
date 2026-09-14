---
entity_id: adress_eindeutigkeit_schreibpfade
type: module
created: 2026-09-13
updated: 2026-09-14
status: draft
version: "1.0"
workflow: fix-2147-b-adress-eindeutig
tags: [security, multi-user, auth, issue-2147, issue-2311, epic-2138]
---

# Adress-Eindeutigkeit an den Schreibpfaden (Scheibe B1)

## Approval

- [ ] Approved

## Purpose

Eine E-Mail-Adresse darf im System nur einem Konto gehören (PO-Vorgabe 2026-09-13). Scheibe A hat
das für den Magic-Link-Anmeldeweg sichergestellt. Diese Spec (Scheibe B1) schließt die drei Wege,
über die überhaupt erst **neue** Doppel-Adressen entstehen können: Registrierung, öffentliche
Passkey-Registrierung und Profil-Update. Ab dieser Scheibe kann sich niemand mehr eine Adresse
holen, die bereits einem anderen (echten) Konto gehört — unabhängig davon, in welchem der beiden
Adressfelder (`email` oder `mail_to`) das andere Konto sie trägt. Ziel ist ausschließlich, dass
**keine neuen** Doppel-Adressen entstehen (Issue #2147 Scheibe B, Teil von #2311); bestehende
Doppel-Adressen werden hier nicht aufgelöst, und wann eine geänderte Adresse *wirksam* wird, regelt
die Folge-Scheibe B2.

## Source

- **File:** `internal/handler/auth.go` — **Identifier:** `RegisterHandler`, `UpdateProfileHandler`
- **File:** `internal/handler/passkey.go` — **Identifier:** `PasskeyRegisterPublicBeginHandler`,
  `PasskeyRegisterPublicFinishHandler`
- **File:** `internal/handler/auth_magic.go` — **Identifier:** `resolveMagicLinkAccount` (F003-Nachschärfung)
- **File:** `internal/store/address_owner.go` — **Identifier:** neue Belegt-Prüfung, wiederverwendet
  `NormalizeEmailAddress`
- **File:** `internal/store/address_lock.go` — **Identifier:** `LockEmailAddress` (bereits vorhanden aus Scheibe A)

## Estimated Scope

- **LoC:** ~100 Prod / ~180 Test — voraussichtlich über dem Standard-Limit, `loc_limit_override` einplanen
- **Files:** ~5 Prod (Go), 2 Frontend, mehrere Testdateien, 1 Doku (`api_contract.md`)
- **Effort:** medium-high (Auth-Kernpfad, Risk Level HIGH)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/store/address_owner.go` → `NormalizeEmailAddress` | Store-Funktion | Einzige Normalisierungsquelle (TrimSpace + ToLower), aus Scheibe A übernommen |
| `internal/store/address_lock.go` → `LockEmailAddress` | Store-Funktion | Prozessweiter Lock je normalisierter Adresse, aus Scheibe A übernommen |
| `internal/model/test_user.go` → `IsTestUserID` | Go-Prädikat | Testkonten tragen keine Adresse im Sinne dieser Prüfung und werden nie blockiert |
| `internal/handler/auth.go` → `dispatchVerificationMail` | Handler | Darf bei einer 409-Ablehnung NICHT aufgerufen werden |
| `docs/specs/modules/magic_link_adress_eindeutigkeit.md` | Spec | Scheibe A — Begriffe, Lock-Muster, F003/F004 |
| `docs/specs/modules/telegram_chat_id_ownership.md` | Spec | Vorlage „Prüfung + 409 unter Lock" |

## Implementation Details

### Begriffe (aus Scheibe A übernommen)

- **Adresse X:** eingegebene Adresse, normalisiert per `NormalizeEmailAddress` (TrimSpace + ToLower).
- **Ein Konto „trägt" X:** jedes Nicht-Testkonto (`!IsTestUserID`), dessen `email` ODER `mail_to`
  (normalisiert verglichen) gleich X ist. Für die B1-Belegt-Prüfung zählt jedes Tragen, unabhängig
  vom Bestätigungsstatus — anders als Scheibe A's `ResolveAddressOwner` (das nur für den
  Magic-Link-Anmeldeweg gilt und dort weiterhin unverändert bleibt).
- **Belegt-Prüfung:** neue, einfachere Store-Funktion (z. B. `IsAddressTakenByOtherAccount(address
  string, excludeUserID string) (bool, error)`), die dieselbe Konten-Iteration wie
  `ResolveAddressOwner` nutzt, aber ohne dessen Bestätigungs-/Zugangsdaten-Logik — sie beantwortet
  nur „trägt irgendein anderes, nicht-test Konto X bereits". `excludeUserID` schließt beim
  Profil-Update das eigene Konto aus.

### 1) Registrierung (`RegisterHandler`, `internal/handler/auth.go`)

Nach der bestehenden Formatprüfung (`invalid_email` bei fehlendem `@`, Reihenfolge #1517 bleibt:
Kennung-existiert-409 vor E-Mail-Prüfungen), zusätzlich unter `LockEmailAddress(X)`:

- Belegt-Prüfung mit `excludeUserID=""` (es existiert noch kein eigenes Konto).
- Belegt → `409 {"error":"email_taken"}` (flaches `error`-Feld, exakt wie `invalid_email` an
  derselben Stelle). Kein Konto wird angelegt, keine Verifikationsmail versendet.
- Frei → Konto wird wie heute angelegt, aber `Email`/`MailTo` werden **normalisiert** gespeichert
  (nicht mehr roh `req.Email`).
- Der Kommentar `auth.go:74-75` „keine Uniqueness-Prüfung (Spec)" wird entfernt — er beschreibt ab
  dieser Scheibe nicht mehr den Ist-Stand.

### 2) Öffentliche Passkey-Registrierung (`internal/handler/passkey.go`)

- **Begin** (`PasskeyRegisterPublicBeginHandler`): Belegt-Prüfung vor dem Ablegen im
  ChallengeStore. Belegt → `409 {"error":"email_taken"}`, keine Challenge wird erzeugt.
- **Finish** (`PasskeyRegisterPublicFinishHandler`): Unter `LockEmailAddress(X)` erneute
  Belegt-Prüfung derselben Adresse, die im Begin-Schritt im ChallengeStore hinterlegt wurde (nicht
  irgendein im Finish-Request mitgeschicktes Feld) — die Adresse kann zwischen Begin und Finish an
  ein anderes Konto vergeben worden sein. Belegt → `409 {"error":"email_taken"}`, kein Konto
  angelegt, kein Credential gespeichert.

### 3) Profil-Update (`UpdateProfileHandler`, `internal/handler/auth.go`)

- Nur wenn `update.Email` oder `update.MailTo` gesetzt ist UND der **normalisierte** Wert vom
  **normalisierten** Bestandswert abweicht UND der neue Wert nicht leer ist, gilt die Adresse als
  „geändert" und braucht eine Belegt-Prüfung. Ein rein case- oder whitespace-abweichender Wert
  (`Foo@X.de` → `foo@x.de`) zählt damit **nicht mehr** als Änderung — das ist eine bewusste
  Verhaltensänderung gegenüber heute (siehe Known Limitations) und heißt: kein Reset von
  `EmailVerifiedAt`, keine neue Bestätigungsmail für einen reinen Schreibweise-Unterschied.
- Betroffene normalisierte Adresse(n) — bei Änderung beider Felder in einem Aufruf zwei
  Adressen — werden **sortiert und dedupliziert** unter `LockEmailAddress` gesperrt (feste
  Reihenfolge verhindert Verklemmung, wenn zwei Nutzer gleichzeitig Adressen tauschen wollen, die
  jeweils dem anderen gehören).
- Das eigene Konto wird **innerhalb** des Locks frisch von der Platte geladen (Read-Modify-Write,
  nicht das bereits am Funktionsanfang — Zeile 722 — geladene Objekt weiterverwenden). Das schließt
  dieselbe TOCTOU-Lücke, die Scheibe A als F003 für den Magic-Link-Pfad geschlossen hat: ohne den
  frischen Reload könnte ein Konflikt entstehen, der zwischen dem ursprünglichen Laden und dem
  Sperren übersehen wird.
- Belegt-Prüfung je geänderter Adresse mit `excludeUserID=` eigene Kontokennung.
- Eine geänderte Adresse wird **normalisiert** gespeichert.
- Belegt (mindestens eine der geänderten Adressen) → `409 {"error":"email_taken"}`. Das **gesamte**
  Profil-Update wird verworfen — auch andere in derselben Anfrage mitgeschickte Felder
  (`display_name`, `sms_to` etc.) werden NICHT übernommen, `EmailVerifiedAt` bleibt unverändert, es
  wird nichts gespeichert und keine Mail verschickt.
- Speichern **ohne** Adressänderung (auch wenn das eigene Konto Teil eines Bestandsduplikats ist)
  blockiert **nie** — die Belegt-Prüfung läuft nur im „Adresse geändert"-Zweig.
- `mail_to` auf leer setzen bleibt uneingeschränkt erlaubt (kein „geändert auf belegte Adresse",
  weil leer nie belegt sein kann).
- Die eigene zweite Adresse übernehmen (`mail_to := eigenes email` oder umgekehrt) bleibt erlaubt —
  die Belegt-Prüfung mit `excludeUserID` = eigenes Konto lässt das durch.
- Das Leeren eines Adressfelds (z. B. `mail_to` → leer) ist nie eine Kollision, setzt aber — wie
  heute — `EmailVerifiedAt` zurück: sonst würde eine nie bestätigte `email` als neue wirksame
  Kontaktadresse als bestätigt gelten („bestätigt gilt pro Adresse", Scheibe A). Die frei werdende
  alte Adresse gehört mit in die Sperrmenge.
- Das heutige Verhalten „ein tatsächlicher Adresswechsel wirkt sofort, setzt `EmailVerifiedAt`
  zurück und löst eine Bestätigungsmail aus" bleibt in B1 **unverändert** — das erst
  nach-Bestätigung-wirksam-Machen ist Scheibe B2.

### 4) Magic-Link-Übernahme (F003-Nachschärfung, `resolveMagicLinkAccount`)

Ist-Stand (`auth_magic.go:214-235`): Die Übernahme eines zugangslosen, unbestätigten Kontos lädt das
Konto nach `ResolveAddressOwner` zwar frisch (`s.LoadUser(owner.ID)`), prüft das frisch geladene
Konto aber **nicht erneut** und setzt direkt `EmailVerifiedAt`. Ab B1 gilt: Das frisch geladene
Konto wird vor dem Speichern erneut geprüft — es muss X weiterhin als wirksame Kontaktadresse tragen
und weiterhin **ohne** Zugangsdaten (Passwort/Passkey/Google) sein. Hat es inzwischen Zugangsdaten
erhalten oder seine Kontaktadresse geändert → keine Übernahme, keine Anmeldung, dieselbe neutrale
Fehlerantwort wie bei jeder anderen Mehrdeutigkeit. Weil Profil-Adressänderungen ab B1 die **alte**
Adresse ebenfalls sperren, ist die Adress-Seite dieser Prüfung atomar; die Zugangsdaten-Seite
(z. B. gleichzeitige Passkey-Anlage im angemeldeten Zustand) wird durch die erneute Prüfung
abgefangen, soweit sie vor dem Neuladen gespeichert wurde (siehe Known Limitations).

### 5) F004 — die Sperre muss tragend sein

Mindestens ein Test pro Schreibpfad muss beweisen, dass er ohne den Lock scheitern würde: zwei
gleichzeitige Schreibversuche (Registrierung/Registrierung, Profil/Profil, Registrierung/Profil) auf
dieselbe freie Adresse dürfen zusammen **genau ein** Konto mit dieser Adresse erzeugen — der zweite
Versuch bekommt `409`.

### 6) Fehlerbehandlung bei Lesefehlern

Schlägt das Lesen einer fremden Kontodatei während der Belegt-Prüfung fehl, wird **fail-closed**
reagiert: `500`, nichts wird geschrieben (konsistent mit Scheibe A). Das Log nennt dabei nie die
geprüfte Adresse im Klartext.

### 7) Frontend

- `frontend/src/routes/register/+page.server.ts`: bildet heute **jeden** `409` auf „Benutzername
  bereits vergeben" ab. Ab dieser Scheibe unterscheidet die Zuordnung nach dem Fehlercode:
  `email_taken` bekommt eine eigene, verständliche Meldung (z. B. „Diese E-Mail-Adresse gehört
  bereits zu einem Konto. Melde dich an — bei Bedarf über ‚Passwort vergessen' oder den Anmeldelink
  per E-Mail."), der Kennungs-Konflikt (`user already exists`) behält seine bisherige Meldung.
- `frontend/src/routes/account/+page.svelte`: zeigt Fehler heute roh an (`body.detail ??
  body.error`). `email_taken` bekommt einen verständlichen deutschen Satz (z. B. „Diese
  E-Mail-Adresse wird bereits von einem anderen Konto verwendet."). Der eingegebene Wert bleibt im
  Formularfeld stehen, nichts wurde gespeichert.

## Expected Behavior

- **Input:** `POST /api/auth/register` `{"username","password","email"}`; `POST
  /api/auth/passkey/register/public/begin|finish`; `PUT /api/auth/profile`
  `{"email"?,"mail_to"?,...}`.
- **Output:** bei Adresskollision an jedem der drei Pfade `409 {"error":"email_taken"}`, sonst
  unverändertes bisheriges Verhalten (`201`/`200` je nach Pfad).
- **Side effects:** bei `email_taken` wird an keinem der drei Pfade irgendetwas geschrieben oder
  versendet — weder Konto/Credential noch Mail.

## Out of Scope

- **Scheibe B2 (Folgeworkflow):** Adresswechsel im Profil wird erst nach Bestätigung wirksam
  (ausstehende Adresse + adressgebundenes Token + erneute Prüfung beim Bestätigen-Klick,
  Kontoseite zeigt „Bestätigung ausstehend"); Python `lookup_user_by_email` auf die bestätigte
  wirksame Adresse umstellen (Mehrdeutigkeit nie stillschweigend `default`); Resend-Allowlist in Go
  UND Python auf die bestätigte wirksame Adresse verengen (#2311-Rest — die Python-Allowlist ist der
  Trip-Versandpfad und trägt ein eigenes Regressionsrisiko, siehe Scheibenschnitt unten).
- **Scheibe C:** Google-OAuth verknüpft ein bestehendes bestätigtes Konto statt ein Zweitkonto
  anzulegen; Kollisionszähler beim Serverstart für Bestandsduplikate; übergreifendes ADR
  „Adress-Eindeutigkeit".
- **Bestehende Doppel-Adressen** (bereits vor dieser Scheibe entstanden) werden durch B1 nicht
  aufgelöst und nicht gemeldet.

### Abweichung vom notierten Scheibenumfang

Notiert war Scheibe B als ein zusammenhängender Umfang: Register-/Profil-/Passkey-409 + #2311 +
„Profil-Adresswechsel erst nach Bestätigung wirksam" + Python-Lookup + Allowlist. Diese Spec teilt
das in B1 (hier) und B2, **nicht** wegen der Zeilenzahl, sondern wegen zweier unterschiedlicher
Risikoklassen: B1 ändert nur, wann ein Schreibversuch abgelehnt wird (kein Schema, kein neuer
Datenpfad). B2 fasst zwei eigenständige Risiken an — eine **Schema-Änderung** am Konto
(Pending-Adresse + adressgebundenes Bestätigungs-Token, Bestandsdaten, Pre-Snapshot-Hook) und den
**Versandpfad** (Python-Allowlist steuert die Trip-Zustellung; eine zu enge Fassung kann bestehende
Zustellung stillschweigend blockieren) sowie die Inbound-Zuordnung (`default`-Fallback bei
Mehrdeutigkeit). Dieser Schnitt liegt der PO zusammen mit den Acceptance Criteria zur Freigabe vor.

## Acceptance Criteria

- **AC-1:** Given eine Adresse gehört noch keinem Konto / When jemand sich mit dieser Adresse
  registriert / Then wird das Konto wie bisher angelegt, und die Adresse ist danach in `email` und
  `mail_to` normalisiert (klein geschrieben, ohne Leerzeichen am Rand) gespeichert.
  - Test: Handler-Test gegen echten `store.Store`; Registrierung mit `" Foo@X.De "`, danach
    `user.json` enthält `foo@x.de`.

- **AC-2:** Given ein anderes, echtes (Nicht-Test-) Konto trägt eine Adresse bereits in `email` oder
  `mail_to` / When sich jemand mit genau dieser Adresse registriert / Then wird `409` mit dem Code
  `email_taken` zurückgegeben, es entsteht kein neues Konto, und es wird keine Verifikationsmail
  verschickt.
  - Test: Zwei-Nutzer-Handler-Test, einmal Kollision über `email`, einmal über `mail_to`; Konten
    vor/nach der Anfrage zählen gleich viele.

- **AC-3:** Given nur ein Testkonto (z. B. `tg-live-e2e`) trägt eine Adresse / When sich jemand
  regulär mit genau dieser Adresse registriert / Then gelingt die Registrierung ganz normal — das
  Testkonto blockiert nicht.
  - Test: Handler-Test; neues Konto entsteht, Testkonto bleibt byteidentisch.

- **AC-4:** Given jemand registriert sich mit einer bereits vergebenen Kennung UND einer Adresse,
  die ebenfalls schon einem anderen Konto gehört / When die Anfrage geschickt wird / Then bekommt
  der Aufrufer den Kennungs-Konflikt (bestehendes Verhalten aus #1517), nicht `email_taken` — die
  Prüfreihenfolge bleibt Kennung vor Adresse.
  - Test: Handler-Test; Antwort enthält `user already exists`, nicht `email_taken`.

- **AC-5:** Given eine Adresse gehört bereits einem anderen Konto / When jemand die öffentliche
  Passkey-Registrierung mit dieser Adresse startet (Begin-Schritt) / Then wird sofort `409
  email_taken` zurückgegeben, ohne dass eine Challenge erzeugt wird.
  - Test: Handler-Test gegen `PasskeyRegisterPublicBeginHandler`; kein Eintrag im ChallengeStore.

- **AC-6:** Given eine Passkey-Registrierung wurde begonnen, während die Adresse noch frei war, und
  bevor der Nutzer den Finish-Schritt abschließt, registriert sich jemand anderes erfolgreich mit
  genau dieser Adresse / When der ursprüngliche Nutzer den Finish-Schritt abschließt / Then wird der
  Finish-Schritt mit `409 email_taken` abgelehnt, es entsteht kein Konto und kein Passkey wird
  gespeichert.
  - Test: Handler-Test, der zwischen Begin und Finish die Adresse über ein zweites Konto belegt.

- **AC-7:** Given ein angemeldetes Konto möchte seine Adresse auf eine Adresse ändern, die bereits
  einem anderen Konto gehört / When das Profil-Update abgeschickt wird / Then bekommt der Nutzer
  `409 email_taken`, und das gesamte Profil — inklusive aller anderen im selben Aufruf mitgeschickten
  Felder — bleibt exakt so gespeichert wie vorher, keine Mail wird verschickt.
  - Test: Zwei-Nutzer-Handler-Test mit Profil-Update, das gleichzeitig `display_name` und die
    kollidierende Adresse ändern will; `user.json` des änderungswilligen Kontos ist danach
    byteidentisch zu vorher.

- **AC-8:** Given ein Konto ist Teil eines bereits bestehenden Adress-Duplikats (Altlast) / When
  dieses Konto sein Profil speichert, OHNE seine `email`/`mail_to`-Werte zu ändern / Then gelingt
  das Speichern ganz normal — die neue Prüfung greift nur bei tatsächlicher Adressänderung.
  - Test: Handler-Test mit vorbereitetem Duplikat; Profil-Update ändert nur `display_name`,
    Antwort `200`.

- **AC-9:** Given ein Konto hat eine gesetzte `mail_to`-Adresse / When der Nutzer `mail_to` im
  Profil auf leer setzt / Then gelingt das immer, unabhängig davon, ob irgendein anderes Konto
  dieselbe Adresse trägt.
  - Test: Handler-Test; `mail_to` ist danach leer, Antwort `200`.

- **AC-10:** Given ein Konto hat zwei verschiedene eigene Adressen in `email` und `mail_to` / When
  der Nutzer `mail_to` auf den Wert seines eigenen `email`-Felds setzt (oder umgekehrt) / Then
  gelingt das Speichern, obwohl die Zieladresse bereits „belegt" ist — nämlich vom eigenen Konto.
  - Test: Handler-Test; Antwort `200`, beide Felder tragen danach denselben Wert.

- **AC-11:** Given zwei angemeldete Konten wollen im selben Moment ihre Adresse jeweils auf die
  aktuelle Adresse des anderen ändern / When beide Profil-Updates gleichzeitig eintreffen / Then
  läuft keine der beiden Anfragen in eine Verklemmung — beide Aufrufe kommen zu einem eindeutigen
  Ergebnis (Erfolg oder `409`), keine hängt unbegrenzt.
  - Test: Go-Test mit zwei Goroutinen hinter einer Startschranke und Timeout; beide Aufrufe kehren
    innerhalb der Testfrist zurück.

- **AC-12:** Given ein zugangsloses, unbestätigtes Konto trägt eine Adresse als wirksame
  Kontaktadresse, und nach der Zuordnung, aber bevor die Übernahme gespeichert wird, erhält dieses
  Konto Zugangsdaten (z. B. einen Passkey) oder eine andere Kontaktadresse / When der Magic-Link-Code
  für diese Adresse eingelöst wird / Then wird das Konto nicht übernommen, nicht als bestätigt
  markiert, es entsteht keine Sitzung, und die Antwort ist die neutrale Fehlerantwort.
  - Test: Handler-/Store-Test, der die Änderung genau zwischen Zuordnung und Neuladen einspielt
    (z. B. über eine Test-Naht); danach ist `email_verified_at` weiterhin leer und kein Cookie gesetzt.

- **AC-13:** Given zwei gleichzeitige Schreibversuche (z. B. zwei Registrierungen oder eine
  Registrierung und ein Profil-Update) zielen auf dieselbe, zu Beginn freie Adresse / When beide
  Versuche im selben Moment gestartet werden / Then wirkt am Ende genau ein Versuch — es entsteht
  genau ein Konto mit dieser Adresse, der andere Versuch erhält `409 email_taken`. Ohne den Lock
  würde dieser Test rot.
  - Test: Go-Test mit zwei Goroutinen hinter einer Startschranke, mehrfach wiederholt; am Ende
    trägt genau ein Konto die Adresse.

- **AC-14:** Given das Lesen der Kontodatei eines fremden Kontos schlägt während der Belegt-Prüfung
  fehl (z. B. beschädigte Datei) / When ein Schreibversuch (Registrierung, Passkey oder
  Profil-Update) diese Prüfung auslöst / Then wird der Versuch mit `500` abgelehnt, es wird nichts
  gespeichert, und im Server-Log erscheint die geprüfte Adresse nicht im Klartext.
  - Test: Handler-Test mit absichtlich beschädigter fremder `user.json`; `500`, Log-Mitschnitt
    ohne Adresse.

- **AC-15:** Given eine Registrierung wird mit einer bereits vergebenen Adresse abgelehnt / When
  die Fehlermeldung im Browser angezeigt wird / Then liest der Nutzer einen verständlichen
  deutschen Hinweis, dass die Adresse bereits einem Konto gehört und er sich anmelden soll — nicht
  die bisherige, sachlich falsche Meldung „Benutzername bereits vergeben".
  - Test: Frontend-Test (`node --test`) für `register/+page.server.ts`, der `email_taken`
    hereingibt und die neue Meldung erwartet.

- **AC-16:** Given ein Profil-Update wird wegen einer bereits vergebenen Adresse mit `409
  email_taken` abgelehnt / When die Fehlermeldung auf der Kontoseite angezeigt wird / Then sieht
  der Nutzer einen verständlichen deutschen Hinweis statt eines rohen Fehlercodes, und der von ihm
  eingegebene Wert bleibt im Formularfeld stehen.
  - Test: Frontend-Test (`node --test`) für die Fehler-Übersetzung der Kontoseite (`email_taken` →
    deutscher Satz, unbekannter Code → bisheriges Verhalten); erhaltener Feldwert per E2E auf Staging.

## Test Plan

- Neue/erweiterte Go-Testdatei(en), nach Verhalten benannt (z. B.
  `internal/handler/address_uniqueness_write_paths_test.go`), echter `store.Store` auf
  `t.TempDir()`, kein Mock-Theater. Jeder Pfad (Register, Passkey Begin+Finish, Profil) wird mit
  **zwei verschiedenen Nutzern** getestet.
- Frontend-Tests über `node --test` + `svelte/server` (kein Vitest — `frontend/package.json`
  gegenprüfen, welches Test-Kommando aktuell registriert ist) für `register/+page.server.ts` und
  `account/+page.svelte`.
- Live (Staging, `/e2e-verify`): Registrierung mit einer bereits im Test-Postfach-Umfeld verwendeten
  Adresse zeigt die neue Meldung im Browser.

## Documentation

- `docs/reference/api_contract.md`: Abschnitt Registrierung/Profil/Passkey — `409 {"error":
  "email_taken"}` ergänzen, die Zeile „keine Uniqueness-Prüfung" (aktuell um Zeile 2643) korrigieren.

## Known Limitations

- **Reine Schreibweise-Änderungen lösen keine Bestätigung mehr aus.** Weil der „geändert"-Vergleich
  im Profil ab dieser Scheibe normalisiert erfolgt, zählt `Foo@X.de` → `foo@x.de` nicht mehr als
  Adressänderung: kein Reset von `EmailVerifiedAt`, keine neue Bestätigungsmail. Das ist eine
  bewusste Verhaltensänderung gegenüber heute (heute vergleicht `auth.go:768/773` roh).
- **`validator-issue110` kann nach dieser Scheibe kollidieren.** `scripts/setup_staging_validator_trip.py`
  schreibt `mail_to=gregor-test@henemm.com` direkt in die Kontodatei, ohne über einen der geprüften
  Handler zu laufen und ohne ein Testkonto im Sinne von `IsTestUserID` zu sein. Registriert sich
  danach ein echter Nutzer mit genau dieser Adresse oder ändert ein anderes Konto sein Profil
  darauf, greift `email_taken` — das kann `/e2e-verify`-Läufe überraschen, die dieses Postfach
  nutzen.
- **`email_taken` verrät die Existenz eines Kontos zu einer Adresse.** Registrierung und öffentliche
  Passkey-Registrierung sind auf 5 Versuche/Stunde je IP begrenzt (`internal/router/router.go:44`
  bzw. `:151`); Profil-Update ist nur angemeldet (bestätigtes Konto, #2271) erreichbar, hat aber
  keine eigene Ratenbremse. Das ist ein bewusster Entscheid aus dem Scheibenschnitt von Scheibe A:
  eine verständliche `409`-Meldung wiegt schwerer als das Enumerations-Risiko.
- **Eine unlesbare fremde Kontodatei blockiert Registrierung, Passkey-Registrierung und
  Profil-Änderung** (fail-closed, bewusst — vermeidet eine falsche Freigabe).
- **Gleichzeitige Schreibzugriffe auf dasselbe Konto ohne Adressbezug** (z. B. Passkey-Anlage im
  angemeldeten Zustand genau im Moment einer Magic-Link-Übernahme) sind nicht unter der Adress-Sperre.
  Die erneute Prüfung (AC-12) fängt Änderungen ab, die vor dem Neuladen gespeichert wurden; ein
  allgemeiner Konto-Schreib-Lock (heute 56 unverriegelte Lade-/Speicher-Stellen) ist nicht Teil von B1.
- **Der Lock ist prozesslokal** (ein Go-Prozess je Umgebung) — kein verteiltes Locking über mehrere
  Instanzen.
- **Bestehende Doppel-Adressen auf Prod/Staging bleiben ungemessen und ungelöst** — B1 verhindert nur
  neue.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** B1 trifft keine neue Grundsatzentscheidung, sondern wendet das in Scheibe A
  etablierte Lock-Muster auf weitere Schreibpfade an. Das übergreifende ADR „Adress-Eindeutigkeit"
  folgt mit Scheibe C, wenn auch der Google-Login-Pfad feststeht.

## Changelog

- 2026-09-13: Initial spec created (Issue #2147 Scheibe B1, Teil von #2311, Epic #2138)
- 2026-09-14: Implementiert (Go-Handler + Store + Frontend); `api_contract.md` zur
  Leeren-Semantik korrigiert (Issue #2147 Scheibe B1)
