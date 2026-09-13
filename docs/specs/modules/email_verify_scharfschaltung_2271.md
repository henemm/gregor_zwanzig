---
entity_id: email_verify_scharfschaltung_2271
type: module
created: 2026-09-12
updated: 2026-09-12
status: draft
version: "1.0"
tags: ["auth", "email-verification", "epic-2138"]
---

# E-Mail-Verifikation: Scharfschaltung des Login-Gates (#2271)

## Approval

- [x] Approved — PO-Freigabe am 2026-09-12. Eingeschlossen: der Entscheid zur Antwortform aus AC-1 (403 „E-Mail nicht bestätigt" nach bestandener Passwortprüfung, mit dem dort benannten Preis).

## Purpose

Die Anmeldung wird abgewiesen, solange die E-Mail-Adresse des Kontos nicht bestätigt ist — die Prüfung sitzt zentral in `issueSession`, sodass kein Anmeldeweg sie umgehen kann. Die öffentliche Passkey-Registrierung verliert dafür ihr Auto-Login. Scheibe 2 von 2 aus #2146/#2271 (Epic #2138); Scheibe 1 (#2304) hat die Vorbedingung bereits hergestellt — kein Bestandskonto wird durch diese Scheibe ausgesperrt.

## Source

- **File:** `internal/handler/auth.go` (Gate in `issueSession`, Prädikatsfunktion), `internal/handler/auth_oauth.go` (Redirect-Vorprüfung), `internal/handler/passkey.go` (Auto-Login-Wegfall)
- **Identifier:** `issueSession`, neue Prädikatsfunktion (Name Implementierungsdetail, z. B. `requireVerifiedEmail`), `PasskeyRegisterPublicFinishHandler`

> **Schicht-Hinweis:** Ausschließlich Go-API (`internal/`) und SvelteKit-Frontend (`frontend/src/routes/login/`, `frontend/e2e/`). Kein Python-Core-Code betroffen (gegengeprüft in der Analyse-Phase: Volltextsuche nach `api/auth/login` über `*.py` liefert nur Treffer in Tests/Setup-Skripten, kein Dienst-Account meldet sich per Login an).

## Abgrenzung

Nicht Teil dieser Scheibe — bereits durch #2304 (S1) geliefert und hier nur genutzt, nicht verändert:

- Das Nachtrag-Skript und die ausgeführten Backfill-Läufe gegen Produktion und Staging.
- Die Selbstheilung bei Magic-Link und Google-OAuth (`selfHealEmailVerification`, `auth.go:781`) — S2 ändert an ihrer Mechanik nichts, nutzt aber ihre Reihenfolge relativ zum neuen Gate (siehe Implementation Details).
- Der Resend-Endpoint `POST /api/auth/verify-email/resend` — existiert bereits, bekommt in S2 nur seinen ersten Frontend-Aufrufer.
- Der staging-only Testweg (`staging_verify_token.go`) — existiert bereits, wird in S2 für die neue Gate-E2E-Spec und die Umstellung der vier Zwei-Nutzer-Specs genutzt.

Nicht Teil dieser Scheibe, weil außerhalb des Tickets:

- Eine Geräteliste oder UI-Anzeige bestätigter/unbestätigter Adressen über den bestehenden Versand-Tab-Hinweis hinaus.
- Verhaltensänderungen an `ChangePasswordHandler` — er bleibt unverändert nutzbar, das ist eine Invariante dieser Scheibe, kein neuer Baustein.

## Estimated Scope

- **LoC:** ~380–460 → **Override auf 500 erforderlich** (bereits gesetzt)
- **Files:** 17
- **Effort:** high

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `internal/handler/auth.go` | MODIFY | Gate-Prädikat, Aufruf in `issueSession` nach frischem `LoadUser`, 403-Antwort; **zusätzlich** eine anders benannte Variante ohne Gate für `ChangePasswordHandler` (`:931`, ruft `issueSession` bei `:999` auf) |
| `internal/handler/auth_oauth.go` | MODIFY | Redirect-Vorprüfung **nach** der Selbstheilung, Weiterleitung auf `/login?error=email_not_verified` bei Ablehnung |
| `internal/handler/passkey.go` | MODIFY | `issueSession`-Aufruf in `PasskeyRegisterPublicFinishHandler` entfällt ersatzlos, Antworttext „Bestätigung ausstehend" |
| `internal/handler/auth_test.go` | MODIFY | Seed für `TestLoginHandlerSuccess` (`:448`) auf `EmailVerifiedAt` gesetzt |
| `internal/handler/auth_traversal_test.go` | MODIFY | Seeds `:180`, `:386` auf `EmailVerifiedAt` gesetzt |
| `internal/handler/session_issuance_test.go` | MODIFY | Sechs-Wege-Tabelle wird zu 5 Positiv + 4 Negativ + 1 Sonderfall mit je eigenem Zähler; neuer OAuth-Ordnungstest |
| `internal/handler/passkey_test.go` | MODIFY | Seeds `:364/:450`, `:1129/:1272` auf `EmailVerifiedAt` gesetzt (per vorgeschaltetem `SaveUser`, nicht am geteilten Helfer) |
| `internal/handler/passkey_public_test.go` | MODIFY | `TestPasskeyRegisterPublicFinish_CookieSecureFlag` (`:402-485`, beide Teiltests) entfällt vollständig |
| `frontend/src/routes/login/+page.server.ts` | MODIFY | Action `default`→`login`, neue Action `resend`, 403 aus dem pauschalen `!resp.ok`-Mapping herausgelöst |
| `frontend/src/routes/login/+page.svelte` | MODIFY | Neuer Fehlerzweig mit Resend-Formular, Registrierungs-Hinweistext angepasst |
| `frontend/e2e/compare-cross-user-write-block.spec.ts` | MODIFY | Zweitnutzer-Erzeugung (`:69`) auf Staging-Testweg umgestellt |
| `frontend/e2e/compare-editor-autosave-user-isolation.spec.ts` | MODIFY | Zweitnutzer-Erzeugung (`:71`) auf Staging-Testweg umgestellt |
| `frontend/e2e/feat-1461-s3b2b-compare-kanal-schwelle.spec.ts` | MODIFY | Zweitnutzer-Erzeugung (`:420`) auf Staging-Testweg umgestellt |
| `frontend/e2e/feat-1745-a-alarm-premium-sms.spec.ts` | MODIFY | Zweitnutzer-Erzeugung (`:307`) auf Staging-Testweg umgestellt |
| `frontend/e2e/fix-2271-email-verify-gate.spec.ts` | CREATE | Neue Gate-Spec: Wegwerfkonto → 403 → Testweg-Token → verifizieren → 200 |
| `docs/adr/0066-login-erfordert-bestaetigte-email-adresse.md` | CREATE | Zählt nicht zum LoC-Limit. Schreibt ADR-0060 fort: Sitzungsausstellung setzt künftig eine bestätigte Adresse voraus, öffentliche Passkey-Registrierung stellt keine Sitzung mehr aus |
| `docs/specs/modules/session_allowlist.md` | MODIFY | Zählt nicht zum LoC-Limit. AC-13 und die Cookie-AC (AC-18) fortgeschrieben: nur noch 5 der 6 Wege stellen ein Merkmal aus, 3 davon nur bedingt |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `issueSession` (`internal/handler/auth.go:130`) | Go-Funktion | Der Wirkort des Gates — einziger Session-ausstellender Pfad, lädt den Nutzer selbst nach |
| `selfHealEmailVerification` (`internal/handler/auth.go:781`, aus S1) | Go-Funktion | Muss vor dem Gate laufen, sonst blockiert das Gate im selben Request das Konto, das sich gerade heilt |
| `dispatchVerificationMail` / Resend-Endpoint (aus S1) | Go-Funktion / Route | Ziel des neuen Frontend-Formulars „Bestätigungsmail erneut senden" — keine neue Backend-Logik nötig |
| `staging_verify_token.go` (aus S1) | Go-Handler, `GZ_ENV == "staging"` | Liefert das Klartext-Token für die neue Gate-E2E-Spec und die vier umgestellten Zwei-Nutzer-Specs |
| `registerForUserAt` (`internal/handler/passkey_test.go:962`) | Go-Test-Helfer | Seedet nur unter `if existing == nil` (`:969`) — Negativfälle müssen ihr Konto vorher selbst unverifiziert anlegen, um den Helfer zu unterlaufen, statt ihn zu ändern |
| `session_allowlist` (Spec, #2129, approved) | Spec | AC-13/AC-18 werden hier fortgeschrieben — dokumentierte Entscheidung, keine stille Rücknahme |
| ADR-0060 (`docs/adr/0060-dauerhafte-anmeldung-mit-widerrufsliste.md`) | ADR | Wird durch das neue ADR-0066 fortgeschrieben, nicht ersetzt |

## Implementation Details

**Das Gate.** Eine Prädikatsfunktion prüft `EmailVerifiedAt` auf einem frisch per `LoadUser` geladenen Nutzer-Objekt — nicht auf einer bereits im Speicher gehaltenen Struct, sonst kippen die Magic-Link-Fälle nach rot, weil `selfHealEmailVerification` auf die Platte schreibt, nicht in die Caller-Struct. Aufgerufen wird sie **innerhalb** `issueSession`, ohne Parameter der Aufrufer: Kein Flag, das ein künftiger siebter Anmeldeweg vergessen könnte.

🔴 **Der Passwortwechsel braucht echte Arbeit, keine Annahme.** `ChangePasswordHandler` (`auth.go:931`) **ruft `issueSession` auf** (`auth.go:999`) — nachgemessen am 2026-09-12. Er ist damit **nicht** strukturell ausgenommen. Nach dem Passwortwechsel werden die bestehenden Anmelde-Merkmale ungültig und ein neues wird ausgestellt; liefe das Gate dort mit, könnte jemand, der gerade seine E-Mail-Adresse geändert hat (`auth.go:708/713` setzt dabei `EmailVerifiedAt = nil`), sein Passwort nicht mehr ändern und verlöre im selben Zug seine Sitzung. Deshalb bekommt `ChangePasswordHandler` eine **eigene, anders benannte** Funktion ohne Gate — ausdrücklich **kein** Parameter an `issueSession`, denn ein Parameter wäre genau die Umgehungslücke, die das zentrale Gate verhindern soll. Zwei Funktionen mit sprechenden Namen machen die Ausnahme sichtbar; ein Flag machte sie unsichtbar.

**Reihenfolge (Pflicht, kein Implementierungsdetail).** Bei Magic-Link und Google-OAuth muss die Selbstheilung **vor** dem Gate laufen. Bei Google-OAuth zusätzlich vor der neuen Redirect-Vorprüfung — sonst weist die Vorprüfung genau das Konto ab, das sich im selben Request gerade heilt. Erfolg und Ablehnung sind bei OAuth beide `302`; die Vorprüfung antwortet bei Ablehnung mit Redirect auf `/login?error=email_not_verified`, bei Erfolg mit dem bisherigen Redirect auf `/`.

**Antwortform.** `403 {"error":"email_not_verified"}`, ausgegeben nach bestandener Geheimnisprüfung (Passwort bzw. WebAuthn-Signatur), kein Session-Cookie. Kein JSON-Deny-Zweig im OAuth-Redirect-Fluss — dort ausschließlich der Redirect-Parameter.

**Wegfall des Auto-Logins.** `passkey.go:565` verliert den `issueSession`-Aufruf ersatzlos. Die Antwort bleibt `201`, der Text wechselt auf einen Hinweis „Bestätigung ausstehend" — wie `RegisterHandler` (`auth.go:117`), der schon heute kein Auto-Login macht. Kein `403` hier: Die Kontoerstellung war erfolgreich.

🔴 **Nachtrag 2026-09-12 (nach der Freigabe, Befund B2 aus der RED-Phase): Der Antwort-Vertrag war unbestimmt.** AC-8 verlangte einen „Hinweis auf ausstehende Bestätigung", ohne ihn festzulegen — damit wäre die AC entweder unprüfbar oder der Test hinge an einer Formulierung, die eine spätere Umformulierung grundlos bräche. **Festgelegt:** `201` mit Körper `{"id":"<kennung>","status":"verification_pending"}`. Die Kennung bleibt erhalten (steht heute dort, wird vom Aufrufer gebraucht), der Hinweis reist im Feld `status`. Der RED-Test fixiert genau diesen Schlüssel; wer ihn ändern will, ändert Spec und Test gemeinsam — nicht den Test an den Code an, das kehrte die Beweisrichtung um.

**`TestPasskeyRegisterPublicFinish_CookieSecureFlag` entfällt vollständig**, beide Teiltests (`passkey_public_test.go:402-485`). Grund: Nach dem Wegfall des Cookies gibt es nichts mehr zu prüfen — `https_secure` fiele laut rot (`found`-Assert), `http_not_secure` liefe lautlos leer durch (Schleife über null Cookies). Ein Testpaar, bei dem eine Hälfte stumm nichts mehr bewacht, wird ersatzlos entfernt statt halb repariert. Die `Secure`-Flag-Logik bleibt über den Passkey-**Login**-Pfad geprüft (`passkey_test.go:441`, `:499`) — das gilt erst, nachdem dort die Seeds auf verifiziert gefixt sind; im Commit müssen beide Änderungen zusammen stehen, nicht die Löschung vor dem Seed-Fix.

**Die Sechs-Wege-Tabelle** (`session_issuance_test.go:283`, heute `if len(ways) != 6`) wird zu drei Gruppen mit je eigenem Zähler-Assert: 5 Positivfälle (stellen aus — Passwort, Magic-Link, Google, Passkey-Login, Passkey ohne Kennungseingabe, jeweils mit verifiziertem bzw. sich im selben Request heilendem Ausgangszustand), 4 Negativfälle (verweigern — Passwort, Passkey-Login, Passkey ohne Kennungseingabe unverifiziert, sowie neu: Google mit Adress-Abweichung), 1 Sonderfall (öffentliche Passkey-Registrierung: 201, kein Cookie). Der eigene Zähler je Gruppe ist notwendig, weil eine einzelne Gesamtzahl einen verschobenen Fall zwischen den Gruppen nicht fängt.

**Negativfälle und der geteilte Seeder.** `registerForUserAt` seedet nur, wenn noch kein Nutzer existiert. Die vier Negativfälle legen ihr Konto deshalb **vorher selbst** per `SaveUser` ohne `EmailVerifiedAt` an — das unterläuft den Helfer, statt ihn zu ändern, und verhindert, dass eine spätere Änderung am Helfer alle Negativfälle stillschweigend grün spült.

**Frontend.** SvelteKit erlaubt `default` und benannte Actions nicht gleichzeitig: die bestehende Login-Action wird zu `login`, dazu kommt `resend` (POST an `/api/auth/verify-email/resend`, Nutzlast `{username}`, antwortet immer bestätigend, weil das Backend ohnehin immer 200 liefert). Der 403-Fall bekommt einen eigenen, verständlichen deutschen Fehlertext plus das Resend-Formular. Der Hinweistext auf der Login-Seite (`login/+page.svelte:43`), der heute nach erfolgreicher Registrierung dort angezeigt wird, wechselt von „Bitte melde dich an" auf einen Hinweis zur Bestätigungsmail, da eine sofortige Anmeldung nach der Scharfschaltung nicht mehr möglich ist. Die Registrierungsseite selbst (`frontend/src/routes/register/`) ändert sich nicht — sie leitet wie bisher nach `/login` weiter, nur der dort gezeigte Text ist neu.

**Reihenfolge der Auslieferung (eine atomare Scheibe für Backend+Tests, danach Frontend, danach Playwright):** Gate, alle Seed-Fixes, Umbau der Sechs-Wege-Tabelle, Auto-Login-Wegfall und Löschung von `CookieSecureFlag` gehören in denselben Commit — jede Teilmenge für sich lässt den Rest rot. ADR-0066 und die Fortschreibung von `session_allowlist.md` gehören ebenfalls in diesen Commit, weil `tests/test_adr_index_drift.py` Index↔Datei-Konsistenz erzwingt. Die ADR-Nummer 0066 ist gegen den lokalen Worktree-Stand frei (höchste vergebene: 0065) — **unmittelbar vor dem Schreiben erneut gegen `origin/main` prüfen**, weil Parallelsitzungen gerade ausliefern. Frontend und Playwright können unabhängig davon folgen.

## Expected Behavior

- **Input:** Anmeldeversuch über einen der sechs Wege; Aufruf des Resend-Formulars im Frontend; Registrierung über die öffentliche Passkey-Registrierung; Staging-E2E-Lauf über den Testweg aus S1.
- **Output:** 403 `{"error":"email_not_verified"}` ohne Cookie bei unverifizierten Passwort- und Passkey-Anmeldungen; 200 mit Cookie bei Magic-Link/Google (verifiziert oder im selben Request geheilt); Redirect auf `/login?error=email_not_verified` bei OAuth-Ablehnung; 201 ohne Cookie bei öffentlicher Passkey-Registrierung.
- **Side effects:** Keine neuen Schreibzugriffe durch das Gate selbst — es liest nur. Die Selbstheilung (aus S1) schreibt wie bisher `EmailVerifiedAt`. Kein Bestandskonto wird ausgesperrt (Prod 3/3, Staging 63/63 bestätigt, Stand 2026-09-12).

## Acceptance Criteria

- **AC-1:** Given ein Konto ohne bestätigte E-Mail-Adresse mit korrektem Passwort / When sich jemand damit über den Passwort-Login anmeldet / Then antwortet der Dienst mit 403 `{"error":"email_not_verified"}` und stellt kein Session-Cookie aus — wer ein geleaktes Passwort ausprobiert, erfährt dadurch zusätzlich, dass Konto und Passwort stimmen; das ist ein bewusst in Kauf genommener Preis für eine für den rechtmäßigen Nutzer verständliche Meldung.
  - Test: Konto ohne `EmailVerifiedAt` per `SaveUser` anlegen, `POST /api/auth/login` mit korrektem Passwort aufrufen, Statuscode UND Antwortkörper prüfen, UND dass die Antwort keinen `Set-Cookie`-Header für `gz_session` enthält.

- **AC-2:** Given ein Konto ohne bestätigte E-Mail-Adresse / When sich jemand damit per Passkey-Login (mit Kennungseingabe) mit gültiger WebAuthn-Signatur anmeldet / Then antwortet der Dienst mit 403 `{"error":"email_not_verified"}` ohne Session-Cookie.
  - Test: Konto vorher selbst per `SaveUser` ohne `EmailVerifiedAt` anlegen (unterläuft `registerForUserAt`s `if existing == nil`), echten Passkey-Login-Roundtrip durchlaufen, 403 und Cookie-Abwesenheit prüfen.

- **AC-3:** Given ein Konto ohne bestätigte E-Mail-Adresse / When sich jemand damit per Passkey-Login ohne Kennungseingabe (discoverable) anmeldet / Then antwortet der Dienst mit 403 `{"error":"email_not_verified"}` ohne Session-Cookie.
  - Test: Konto vorher selbst unverifiziert anlegen (gleiche Technik wie AC-2), discoverable Roundtrip durchlaufen, 403 und Cookie-Abwesenheit prüfen.

- **AC-4:** Given ein bestehendes Google-OAuth-Konto ohne bestätigte E-Mail-Adresse, dessen `MailTo` einer ANDEREN Adresse entspricht als der von Google im Callback bestätigten / When sich das Konto per Google anmeldet / Then leitet der Dienst auf `/login?error=email_not_verified` weiter, und der Nutzer bleibt danach unverifiziert.
  - Test: Store-Fixture mit `MailTo` ≠ von `oauthFakeServers` gelieferter Adresse, Callback aufrufen, den `Location`-Header (nicht den Statuscode — Erfolg und Ablehnung sind beide 302) auf `/login?error=email_not_verified` prüfen, UND den Nutzer danach über den Store neu laden und `EmailVerifiedAt == nil` prüfen.

- **AC-5:** Given ein bestehendes Google-OAuth-Konto ohne bestätigte E-Mail-Adresse, dessen effektive Kontaktadresse der von Google im Callback bestätigten Adresse entspricht / When sich das Konto per Google anmeldet / Then zeigt der `Location`-Header auf `/` (nicht auf den Fehlerpfad), und derselbe Test lädt den Nutzer danach über den Store neu und stellt fest, dass `EmailVerifiedAt` gesetzt ist.
  - Test: Beide Zusicherungen in derselben Testfunktion — ein Statuscode-Assert allein bewacht nichts, da Erfolg und Ablehnung beide 302 sind. Deckt zugleich ab, dass die Redirect-Vorprüfung nach der Selbstheilung läuft: liefe sie davor, würde dieses Konto im selben Request abgewiesen, das sich gerade heilt.

- **AC-6:** Given die fünf Ausstellungsstellen, die nach dieser Scheibe ein Anmelde-Merkmal ausstellen können (Passwort verifiziert, Magic-Link, Google, Passkey-Login verifiziert, Passkey ohne Kennungseingabe verifiziert) / When der Test der Sechs-Wege-Tabelle läuft / Then scheitert der Lauf, sobald eine dieser Ausstellungsstellen fehlt oder eine neue hinzukommt, ohne in dieser Gruppe eingetragen zu sein.
  - Test: Zähler-Assert `len(issuing) != 5 → Fatalf` über die Positiv-Gruppe der Sechs-Wege-Tabelle (`session_issuance_test.go`), zusätzlich zu den Einzel-Cookie-Prüfungen je Weg. Deckt zugleich den Magic-Link-Durchlass ab: liefe das Gate vor der Selbstheilung, fehlte dort das Cookie und die Gruppe hätte nur 4 statt 5 Einträge.

- **AC-7:** Given die vier Ausstellungsstellen, die nach dieser Scheibe ein Anmelde-Merkmal verweigern (Passwort unverifiziert, Passkey-Login unverifiziert, Passkey ohne Kennungseingabe unverifiziert, Google mit Adress-Abweichung) / When der Test der Sechs-Wege-Tabelle läuft / Then scheitert der Lauf, sobald eine dieser Verweigerungen fehlt oder eine neue hinzukommt, ohne in dieser Gruppe eingetragen zu sein.
  - Test: Zähler-Assert `len(blocking) != 4 → Fatalf`, zusätzlich zu den Einzel-403/Redirect-Prüfungen je Weg. Ohne diesen Zähler bliebe ein vergessener oder unbemerkt entfernter Blockierfall unentdeckt — genau das, wogegen die alte `!= 6`-Zeile stand.

- **AC-8:** Given ein Aufruf der öffentlichen Passkey-Registrierung mit gültiger Attestation / When die Registrierung abgeschlossen ist / Then antwortet der Dienst mit 201, enthält keinen `Set-Cookie`-Header, und der Antworttext weist auf eine ausstehende Bestätigung hin.
  - Test: Vollständigen `passkey/register/public/finish`-Roundtrip durchlaufen, Statuscode UND Abwesenheit von `Set-Cookie` UND den Hinweistext im Antwortkörper prüfen.

- **AC-9:** Given drei Anmeldeversuche über den Passwort-Login — (a) eine Kennung, zu der kein Konto existiert, (b) ein bestätigtes Konto mit falschem Passwort, (c) ein UNBESTÄTIGTES Konto mit falschem Passwort / When alle drei Versuche laufen / Then sind Statuscode und Antwortkörper in allen drei Fällen zeichengleich 401 — das neue Gate antwortet erst nach bestandener Passwortprüfung und schafft damit keine neue Kontenaufzählung.
  - Test: Alle drei Antworten paarweise byteweise auf Gleichheit vergleichen. Fall (c) ist der eigentliche Wächter über die Reihenfolge: Läge das Gate vor der Passwortprüfung, lieferte (c) 403 statt 401 und verriete die Existenz des Kontos an jemanden, der das Passwort nicht kennt.

- **AC-10:** Given ein angemeldeter Nutzer hat gerade seine E-Mail-Adresse geändert, wodurch `EmailVerifiedAt` auf `nil` gesetzt wurde (`auth.go:708/713`) / When er über `ChangePasswordHandler` (`auth.go:931`) sein Passwort ändert / Then gelingt die Passwortänderung unverändert UND er erhält ein neues, gültiges Anmelde-Merkmal — er verliert seine Sitzung nicht, obwohl seine Adresse in diesem Moment unbestätigt ist.
  - Test: Nutzer mit `EmailVerifiedAt == nil` anlegen, angemeldeten Aufruf von `ChangePasswordHandler` durchführen, Erfolgscode prüfen UND dass die Antwort ein `gz_session`-Cookie setzt, das anschließend einen geschützten Endpunkt öffnet. 🔴 Der Cookie-Teil ist der eigentliche Wächter: `ChangePasswordHandler` ruft `issueSession` auf (`auth.go:999`, nachgemessen). Ein Test, der nur den Statuscode prüft, ginge auch dann grün durch, wenn der Nutzer im selben Zug seine Sitzung verliert.

- **AC-11:** Given ein Dienst, der ohne gesetztes `GZ_ENV` gebaut wurde (die Produktionslage) / When sich ein unverifiziertes Konto per Passwort anmeldet / Then greift das Gate unverändert mit 403 — es gibt keinen Umgebungs-Schalter, der es dort abschaltet.
  - Test: Router explizit ohne `GZ_ENV` bauen (Muster S1 AC-9), unverifizierten Passwort-Login durchführen, 403 prüfen.

- **AC-12:** Given ein Nutzer versucht sich mit korrektem Passwort, aber unbestätigter E-Mail-Adresse im Frontend anzumelden / When die Antwort 403 `email_not_verified` eintrifft / Then zeigt die Login-Seite einen verständlichen deutschen Hinweistext statt „Ungültige Anmeldedaten".
  - Test: Playwright — Login mit unverifiziertem Testkonto durchführen, den angezeigten Fehlertext auf den neuen Hinweis prüfen (nicht auf den bisherigen „Invalid credentials"-Text).

- **AC-13:** Given der Hinweistext aus AC-12 wird angezeigt / When der Nutzer das Resend-Formular absendet / Then wird die Form-Action `?/resend` ausgelöst und die Seite zeigt eine Bestätigung, dass die Mail (erneut) unterwegs ist.
  - Test: Playwright — im Fehlerzustand aus AC-12 das Resend-Formular abschicken, den POST auf `/login?/resend` beobachten, angezeigten Bestätigungstext prüfen.
  - 🔴 **Korrektur 2026-09-12 (nach der Freigabe, Befund B1 aus der RED-Phase):** Die ursprüngliche Fassung verlangte, den Aufruf von `POST /api/auth/verify-email/resend` zu beobachten. Das ist **strukturell unmöglich**: Das Resend-Formular ist eine SvelteKit-Form-Action, deren Code im Node-Prozess des Frontends läuft. Playwright sieht vom Browser aus ausschließlich den POST auf `/login?/resend`; der Aufruf der Go-API findet server-zu-server statt. Ein Test, der den ursprünglichen Nachweis behauptet, müsste auf den falschen Request prüfen oder einen Mock einziehen — beides wertlos bzw. verboten. **Die AC bewacht daher bewusst nur die Bedien-Fläche.** Der Resend-Endpunkt selbst ist bereits gedeckt: `verify_resend_test.go` (`TestResendErzeugtGueltigesTokenUndAntwortetOk_AC7`) ruft ihn echt auf und prüft, dass ein gültiges Token im Store entsteht. Ungedeckt bleibt allein die neue Svelte-Action **als Aufrufer** — bewusst in Kauf genommen, weil jeder Nachweis dafür entweder einen Mock oder eine Annahme über die Token-Ersetzung bräuchte.

- **AC-14:** Given ein Nutzer registriert sich neu und landet dabei wie bisher auf der Login-Seite / When die Registrierung abgeschlossen ist / Then trägt die Login-Seite einen Hinweis auf die Bestätigungsmail statt der bisherigen Aufforderung „Bitte melde dich an" — eine sofortige Anmeldung ist nach dieser Scheibe nicht mehr möglich.
  - Test: Playwright — Registrierung durchlaufen, angezeigten Text auf der Login-Seite nach der Weiterleitung prüfen (enthält keinen Aufruf zur sofortigen Anmeldung mehr).

- **AC-15:** Given ein frisch registriertes Wegwerfkonto auf Staging / When es sich vor der Bestätigung anmeldet, dann über den staging-only Testweg ein Token holt, sich per `POST /api/auth/verify-email` verifiziert und sich erneut anmeldet / Then liefert der erste Anmeldeversuch 403, der zweite 200 — beide Zweige des Gates real durchlaufen, ohne dauerhafte Sonderkonten.
  - Test: Neue Playwright-Spec `fix-2271-email-verify-gate.spec.ts` gegen Staging: Registrierung → Login erwartet 403 → Token über den Testweg aus S1 holen → `POST /api/auth/verify-email` → Login erwartet 200, alles in einem Testlauf mit demselben Konto.

- **AC-16:** Given die vier bestehenden Zwei-Nutzer-Playwright-Specs (`compare-cross-user-write-block`, `compare-editor-autosave-user-isolation`, `feat-1461-s3b2b-compare-kanal-schwelle`, `feat-1745-a-alarm-premium-sms`) erzeugten ihren zweiten Nutzer bisher per Registrierung und sofortigem Login mit Laufzeit-Suffix / When sie auf den staging-only Testweg aus S1 umgestellt sind / Then bestehen alle vier weiterhin auf Staging, obwohl das Gate scharf ist.
  - Test: CI-/`e2e-verify`-Lauf gegen Staging zeigt alle vier Specs grün nach der Umstellung; vorher (mit scharfem Gate, ohne Umstellung) wären sie strukturell nie wieder grün, weil jeder Lauf einen neuen, unbestätigbaren Nutzernamen erzeugt.

🔴 **Nachtrag 2026-09-12 zu AC-15 und AC-16 (nach der Freigabe, Befund B3 aus der RED-Phase): Wessen Sitzung das Token holt, war offen — und das Naheliegende ist unmöglich.**

Der staging-only Testweg `POST /api/auth/verify-email/staging-token` ist **anmeldepflichtig** (`staging_verify_token.go:15` — bewusst nicht in der Public-Allowlist, bewusst nicht unter einem der drei von `AuthMiddleware` pauschal befreiten Präfixe). Nach der Scharfschaltung ist ein frisch registriertes Konto genau das, was sich **nicht** anmelden kann. Es könnte sein eigenes Token also nie abholen — die Formulierung „es holt über den Testweg ein Token" beschreibt einen unmöglichen Ablauf.

**Auflösung (verbindlich):** Das Token holt eine **fremde, bereits angemeldete und bestätigte Sitzung** — in Playwright die Admin-Fixture (`storageState` aus `playwright.config.ts`). Möglich ist das, weil der Handler die Kennung aus der **Nutzlast** nimmt (`staging_verify_token.go:34`), nicht aus dem Auth-Kontext, und `EmailVerifiedAt` bewusst nicht ansieht. Die Anmeldepflicht der Route bleibt damit unangetastet, es entsteht kein neuer Endpunkt und kein dauerhaftes Sonderkonto.

**Die Reihenfolge ist zwingend, nicht beliebig:** zweiten Nutzer registrieren → Token **mit der Admin-Sitzung** holen → `POST /api/auth/verify-email` → **erst dann** Login des zweiten Nutzers. Jede andere Reihenfolge scheitert am Gate.

Verworfene Alternativen: (a) Testweg in die Public-Allowlist nehmen — öffentlich erreichbarer Token-Ausgabepunkt, selbst staging-only ein schlechterer Zustand als heute, und eine stille Rücknahme einer S1-Entscheidung ohne ADR. (b) Zweitnutzer als festes Bestandskonto — nähme den vier Specs die Isolation zwischen Läufen, für die die Laufzeitnamen überhaupt existieren.

**Preis der gewählten Variante, bewusst getragen:** Jede angemeldete Staging-Sitzung kann ein Klartext-Token für ein fremdes Konto ziehen. Auf Staging vertretbar — und ein weiterer Grund, warum diese Route nie nach Produktion darf.

🔴 **Offener Punkt für `/70-deploy` (Befund B4, nicht in dieser Scheibe zu lösen):** Die Registrierung ist auf **5 Versuche pro Stunde und IP** gedeckelt (`router.go:40-41`, Limiter im langlebigen Staging-Prozess). Nach dieser Scheibe stehen in `frontend/e2e` **7 Registrierungen** (4 aus den Zwei-Nutzer-Specs + 3 aus `fix-2271-email-verify-gate.spec.ts`). Heute ist ein 429 dort folgenlos; nach der Scharfschaltung heißt „keine Registrierung" auch „kein Token, keine Anmeldung" und sieht im Testlauf aus wie ein defektes Gate. Vor dem Prod-Deploy zu entscheiden.

- **AC-17:** Given diese Scheibe nimmt die dokumentierte Zusage aus `session_allowlist.md` (AC-13: alle sechs Wege stellen ein Merkmal aus) teilweise zurück / When der Commit mit dem Gate gemerged wird / Then enthält derselbe Commit sowohl ADR-0066 (mit Eintrag in `docs/adr/README.md`) als auch die Fortschreibung von AC-13 und AC-18 in `session_allowlist.md`, und `tests/test_adr_index_drift.py` läuft grün.
  - Test: `tests/test_adr_index_drift.py` im selben Testlauf wie die übrige Kern-Schicht ausführen — muss grün sein.

## Known Limitations

- Die Registrierung selbst bleibt offen (PO-Entscheid 2026-09-09) — nur die Anmeldung mit einem frisch registrierten, unbestätigten Konto wird blockiert. Ein unbestätigtes Konto hat als Rückweg ausschließlich Magic-Link, Google-OAuth oder den Resend-Weg; Passwort- und Passkey-Login bleiben bis zur Bestätigung gesperrt.
- Der Preis aus AC-1 (Credential-Stuffing erfährt zusätzlich „Konto existiert, Passwort stimmt") ist ein bewusster, vom PO zu bestätigender Kompromiss zugunsten einer für den rechtmäßigen Nutzer verständlichen Meldung. Gegenüber einem Angreifer ohne Zugangsdaten entsteht kein neues Leck (AC-9).
- Die öffentliche Passkey-Registrierung hat aktuell keinen Aufrufer im Frontend oder in Playwright (gegengeprüft in der Analyse-Phase) — AC-8 ist trotzdem Pflicht, weil die Route öffentlich erreichbar bleibt.
- Diese Scheibe ändert nichts an der 24-Stunden-Frist bzw. der Gästeliste aus `session_allowlist.md` — sie greift ausschließlich in die Frage ein, OB überhaupt ein Merkmal ausgestellt wird, nicht WIE LANGE es gilt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0066
- **Rationale:** Nimmt eine dokumentierte Entscheidung aus ADR-0060 / `session_allowlist.md` teilweise zurück (nicht mehr alle sechs Anmeldewege stellen ein Merkmal aus, drei davon nur bedingt) — nach CLAUDE.md darf das nicht still geschehen. Das neue ADR hält fest: Sitzungsausstellung setzt künftig eine bestätigte E-Mail-Adresse voraus; die öffentliche Passkey-Registrierung stellt keine Sitzung mehr aus. Die ADR-Nummer ist gegen den Stand vom 2026-09-12 frei (höchste vergebene: 0065) — unmittelbar vor dem Schreiben erneut gegen `origin/main` zu prüfen, da Parallelsitzungen ausliefern.

## Changelog

- 2026-09-12: Initial spec created (Issue #2271, S2 aus #2146/#2304, Epic #2138)
