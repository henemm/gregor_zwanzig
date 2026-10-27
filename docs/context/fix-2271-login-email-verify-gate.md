# Context: fix-2271-login-email-verify-gate

**Issue:** #2271 (S2 aus #2146, Epic #2138 Multi-User-Readiness) · **Label:** `priority:critical`
**Erstellt:** 2026-09-12 · **Messgrundlage:** `origin/main` = `c31a09a6`

## Verhältnis zum bestehenden Kontext-Dokument

Die vollständige Kartierung und Analyse dieses Themas steht bereits in
**`docs/context/fix-2271-login-email-verify.md`** (266 Zeilen, 2026-09-11). Sie wurde für
**beide** Scheiben geschrieben — S1 (#2304, geliefert) und S2 (dieses Ticket).

Dieses Dokument wiederholt sie **nicht**. Es hält nur fest, was sich seitdem geändert hat und
was die Nachmessung am 2026-09-12 zusätzlich zutage gefördert hat. Wer die Begründungen sucht
(Entscheidung je Anmeldeweg, warum kein Schalter, warum das Gate in `issueSession` sitzt),
liest dort — insbesondere die Abschnitte A1–A7.

## Request Summary

Die Anmeldung wird abgewiesen, solange die E-Mail-Adresse des Kontos nicht bestätigt ist. Das
Gate sitzt in `issueSession`, der einen Stelle, durch die alle Anmeldewege gehen. Die
öffentliche Passkey-Registrierung verliert ihr Auto-Login. Bestandskonten dürfen dabei nicht
ausgesperrt werden — diese Vorbedingung ist durch S1 bereits erfüllt.

## Was S1 (#2304) geliefert hat — nachgemessen, nicht übernommen

| Baustein | Beleg in `origin/main` | Stand |
|---|---|---|
| Selbstheilung Magic-Link / Google-OAuth | `internal/handler/auth.go:781` `selfHealEmailVerification` | ✅ vorhanden |
| Resend-Endpoint | `internal/router/router.go:71`, `internal/middleware/auth.go:59` (Public-Allowlist) | ✅ vorhanden |
| Staging-Testweg (Token im Klartext) | `internal/handler/staging_verify_token.go`, `router.go:80` (nur bei `GZ_ENV == "staging"`) | ✅ vorhanden |
| Bestandskonten nachgetragen | Prod: 0 offen · Staging: 0 von 63 offen (PO-Kommentar 2026-09-11) | ✅ ausgeführt |
| Spec | `docs/specs/modules/email_verify_vorbereitung_2304.md` | ✅ |
| **Das Gate selbst** | `auth.go:130` `issueSession` — prüft `EmailVerifiedAt` **an keiner Stelle** | ❌ offen |

Damit ist die Aussperr-Falle aus dem Ticket entschärft, **bevor** hier scharfgeschaltet wird.
Die zeitliche Entkopplung gegen den `*/5`-Staging-Cron (A4(a)) hat stattgefunden.

## Related Files — die Fläche von S2

| Datei | Relevanz |
|---|---|
| `internal/handler/auth.go:130` (`issueSession`) | **Der Wirkort.** Lädt den Nutzer selbst nach und prüft `EmailVerifiedAt`; kein Parameter der Aufrufer (sonst wäre der nächste Anmeldeweg die Lücke) |
| `internal/handler/auth.go:921` (`ChangePasswordHandler`) | Ausnahme — kein Anmeldeweg. Wer gerade seine Adresse geändert hat (`auth.go:708/713` setzt `EmailVerifiedAt = nil`), muss sein Passwort weiter ändern können |
| `internal/handler/auth_oauth.go:181` | Ausnahme in der **Form**, nicht in der Sache: antwortet mit `http.Redirect`. Ein zentraler JSON-Deny-Zweig brächte rohes JSON in einen Redirect-Fluss → eigene Vorprüfung, Weiterleitung auf `/login?error=email_not_verified` |
| `internal/handler/passkey.go:565` (`PasskeyRegisterPublicFinishHandler`) | Der `issueSession`-Aufruf entfällt ersatzlos. 201 bleibt, mit Hinweis „Bestätigung ausstehend" — wie `RegisterHandler` (`auth.go:117`), der schon heute kein Auto-Login macht |
| `internal/handler/passkey.go:258`, `:359` | Passkey-Login (Kennung) und Passkey-Login ohne Kennungseingabe — werden vom zentralen Gate regulär geblockt, kein eigener Code |
| `frontend/src/routes/login/+page.server.ts:32-36` | Heute mappt `!resp.ok` **pauschal** auf `401 'Invalid credentials'`. Der 403 des Gates würde dort verschluckt |
| `frontend/src/routes/login/+page.svelte:53-57` | Die Fehlerzeile ist eine Kette von Gleichheitsvergleichen auf `form.error` — der neue Fall braucht dort einen Zweig |
| `frontend/src/routes/login/+page.svelte:41-45` | 🔴 Der Hinweis nach der Registrierung lautet heute „Konto erfolgreich erstellt. **Bitte melde dich an.**" — nach der Scharfschaltung ist das eine Aufforderung zu etwas, das nicht geht |
| `docs/specs/modules/session_allowlist.md:59, 101, 117` | AC-13 und die Cookie-AC schreiben fest, dass **alle sechs** Anmeldewege ein Merkmal ausstellen. Wird hier fortgeschrieben |
| `docs/adr/0060-…` | Erwähnt „sechs Ausstellungsstellen" nur als Kontext (`:10`). Die bindende Zusage steht in der Spec, nicht im ADR — das neue ADR schreibt trotzdem beides fort (Auth ist Entscheidungsfläche) |

## Existing Patterns

- **Deny nach bestandener Geheimnisprüfung:** `auth.go:186` ist die Stelle, ab der Konto und
  Passwort feststehen. Erst danach antwortet das Gate — das unterscheidet den 403 qualitativ
  von den 401ern, die **vor** jeder Geheimnisprüfung greifen.
- **Staging-only-Registrierung von Routen:** `router.go:215` (#830) und `router.go:80` (#2304)
  — `if os.Getenv("GZ_ENV") == "staging"`. Produktion setzt `GZ_ENV` gar nicht, ein
  `!=`-Vergleich wäre dort aktiv. Nur `== "staging"` ist sicher.
- **Read-Modify-Write auf `user.json`:** `selfHealEmailVerification` (`auth.go:795-813`) lädt
  das ganze Objekt, ändert ein Feld, speichert zurück. Das Gate **liest** nur — es schreibt
  nichts und löst damit auch den Schema-Backup-Hook nicht aus.

## Dependencies

- **Upstream:** `store.LoadUser`, `model.User.EmailVerifiedAt` (`internal/model/user.go:32`),
  `middleware.SetSessionCookie`.
- **Downstream:** jeder Anmeldeweg; das Frontend-Login; die Playwright-Fixtures, die eine
  angemeldete Sitzung voraussetzen.
- **Nicht betroffen:** Der Python-Core meldet sich **nicht** per Login an. ADR-0062 legt den
  Header `X-GZ-Core-Auth` fest (`docs/adr/0062-…:36`); es gibt keinen Dienst-Account, der
  durch das Gate fiele. Gegengeprüft mit einer Volltextsuche nach `api/auth/login` über
  `*.py`/`*.sh`/`*.go` — Treffer ausschließlich in Tests und `scripts/setup-validator-user.sh`.

## Existing Specs

- `docs/specs/modules/session_allowlist.md` (#2129, approved) — **wird fortgeschrieben**
- `docs/specs/modules/email_verify_vorbereitung_2304.md` (S1) — Gegenstück, bleibt gültig
- `docs/specs/_archive/modules/issue_466_passkey_register_public.md` — beschreibt das heutige
  Auto-Login der öffentlichen Passkey-Registrierung (archiviert)
- `docs/adr/0060-dauerhafte-anmeldung-mit-widerrufsliste.md` — Bezugspunkt des neuen ADR

**Freie ADR-Nummer: 0066** (höchste vergebene in `origin/main` ist `0065`; gegen `origin/main`
bestimmt, nicht gegen den Worktree).

## Risks & Considerations

### R1 — Der Deny-Zweig verrät einem Angreifer mit geleaktem Passwort mehr als heute 🔴 PO-Entscheid

`403 {"error":"email_not_verified"}` erscheint erst **nach** bestandener Passwortprüfung. Wer
die Zugangsdaten ohnehin kennt, erfährt zusätzlich „Konto existiert, Passwort stimmt, Adresse
unbestätigt". Gegenüber einem Angreifer **ohne** Zugangsdaten entsteht kein neues Leck — die
Kontenaufzählung bleibt durch die unveränderten 401er verschlossen.

Das ist ein bewusster Tausch zugunsten der vom Ticket geforderten verständlichen Meldung: eine
einheitliche 401 wäre für den rechtmäßigen Nutzer nutzlos, er säße vor „Benutzername oder
Passwort nicht korrekt" und würde sein Passwort zurücksetzen, was nichts hilft. Der PO hat den
Punkt am 2026-09-11 ausdrücklich als spec-pflichtig markiert — er gehört in ein eigenes
Acceptance Criterion, nicht stillschweigend in den Code.

### R2 — Eine Prüfung nur im `LoginHandler` verfehlt das Ziel

Es gibt sechs Wege zur Sitzung. Fünf davon liegen außerhalb des `LoginHandler`. Deshalb sitzt
das Gate in `issueSession` und lädt den Nutzer **selbst** nach. Ein Flag, das die Aufrufer
mitgeben, wäre genau die Umgehungslücke: Ein künftiger siebter Weg müsste sich aktiv erinnern.
Die Tabelle in `session_issuance_test.go:284` ist zweiter Kontrollpunkt, **kein** Ersatz — sie
fängt nur, was jemand dort einträgt.

### R3 — Ein pauschales Gate mauert den Wiedereinstieg zu

Magic-Link und Google-OAuth **beweisen** Mailbox-Besitz und heilen den Status seit S1 selbst
(`selfHealEmailVerification`). Würden sie geblockt, gäbe es für ein unbestätigtes Konto keinen
Weg zurück außer dem Resend-Endpoint. Sie müssen durchgelassen werden — und zwar nachdem die
Heilung gelaufen ist, sonst blockiert das Gate im selben Request, den es heilen sollte.
🔴 **Reihenfolge im Request ist Teil der Zusicherung, nicht Implementierungsdetail.**

### R4 — Der Abweisungsgrund der öffentlichen Passkey-Registrierung ist kein Fehler

`passkey.go:565` stellt die Sitzung aus, während die Bestätigungsmail (`:563`) noch unterwegs
ist — das ist die Lücke, die das Ticket meint (beliebige Adresse angeben, Sitzung sofort). Ein
zentrales Gate, das hier mit 403 antwortete, gäbe einer **erfolgreichen** Kontoerstellung eine
Fehlerantwort. Richtig ist der Wegfall des Aufrufs, nicht seine Ablehnung.

**Entlastender Befund (2026-09-12):** `/api/auth/passkey/register/public/*` hat **keinen**
Aufrufer außerhalb des Backends — weder im Frontend (`frontend/src/lib/passkey.ts:37`
`registerPasskey` spricht den *authentifizierten* Endpunkt `/register/begin` an und wird nur
aus `frontend/src/routes/account/+page.svelte:248` benutzt) noch in Playwright. Der Wegfall des
Auto-Logins ist damit reine Backend-Arbeit ohne Frontend-Folge.

### R5 — Die Meldung im Frontend braucht einen Ausweg, nicht nur einen Text

Das Ticket verlangt „verständliche Meldung **und** die Möglichkeit, die Bestätigungsmail
erneut anzufordern". Der Endpunkt `POST /api/auth/verify-email/resend` steht seit S1, hat aber
**bisher keinen einzigen Aufrufer im Frontend** (gemessen: Treffer nur in `router.go`,
`middleware/auth.go`, `verify_resend_test.go`). Die Bedien-Fläche dafür ist neue Arbeit in S2.

### R6 — Testfläche: drei Schichten, nicht zwei

Die Scope-Tabelle im Vorgänger-Dokument nennt Go-Tests und Playwright. Die Nachmessung zeigt
eine **dritte** Schicht: Python-Tests unter `tests/tdd/`, die gegen einen laufenden Server ein
Konto anlegen und sich damit anmelden — u. a. `test_register_page.py:142`,
`test_issue_692_telegram_disabled_unconfigured.py:58`,
`test_issue_1068_tier_model_display.py:89`, `test_design_optimierungen.py:27`. Dazu
`scripts/setup-validator-user.sh:20/31` (registriert und meldet sich an).

**Entlastung:** Alle geprüften Vertreter sind `live`-markiert (`test_register_page.py:18`
`pytestmark = pytest.mark.live`) und liegen damit außerhalb der CI-Ampel. Betroffen ist die
Live-Schicht bei `/e2e-verify`, nicht der Commit-Pfad. `.claude/hooks/prod_selftest.py` legt
selbst **kein** Konto an und meldet sich nicht an — das harte Gate vor dem Issue-Close ist
nicht betroffen (gegengeprüft).

Konten mit **festen** Namen sind unkritisch: Sie sind Teil der 63 nachgetragenen Staging-Konten.
Kritisch ist nur, wer Konten **zur Laufzeit neu** erzeugt — dafür existiert der Staging-Testweg
aus S1.

### R7 — Die Rücknahme einer dokumentierten Entscheidung darf nicht still geschehen

`session_allowlist.md` AC-13 (`:101`) sagt: „Given ein Nutzer meldet sich über einen der sechs
Anmeldewege an … Then besteht das jeweils ausgestellte Anmelde-Merkmal die eigene Prüfung."
Nach S2 stellt Weg 6 gar kein Merkmal mehr aus, und die Wege 1/4/5 stellen es nur noch unter
einer Bedingung aus. Nach CLAUDE.md („Eine dokumentierte Entscheidung wird nie still
rückgängig gemacht") braucht das **ADR-0066** plus eine Fortschreibung der Spec.

### R8 — LoC

Vorgänger-Schätzung für S2: ~170 LoC. Das Standard-Limit liegt bei 250; `docs/`/`*.md` zählen
nicht mit. Ein Override ist nach heutigem Stand nicht nötig, wird aber vor `/50-implement`
gegen die dann bekannte Testfläche neu bewertet.

## Gemessene Testfläche (Inventur 2026-09-12, gegen `origin/main`)

### 🔴 Der Befund, der die Bauform festnagelt

Das Gate **muss** innerhalb `issueSession` per frischem `LoadUser` prüfen. Prüfte es statt
dessen in den Aufrufern auf der bereits im Speicher gehaltenen `user`-Variable, kippten die
Magic-Link-Fälle nach rot: `selfHealEmailVerification` schreibt auf die **Platte**, nicht in die
Caller-Struct. Die Nachlade-Entscheidung aus A1 ist damit nicht Geschmackssache, sondern
Voraussetzung dafür, dass der Wiedereinstiegsweg überhaupt funktioniert.

### Go-Tests — kein einziger zentraler Helfer, sondern zwei Muster

- `newTestStore` (`internal/handler/trip_write_test.go:15`, von 75 Testdateien genutzt) legt
  nur einen leeren Store an — **keinen** Nutzer. Hilft hier nicht.
- `registerForUserAt` (`internal/handler/passkey_test.go:962`, Seed `:969`) ist der **einzige**
  geteilte Nutzer-Seeder auf einem betroffenen Pfad und setzt `EmailVerifiedAt` nicht. Eine
  Änderung dort heilt **alle** Passkey-Login-Tests auf einen Schlag.
- Für Passwort-Login gibt es keinen gemeinsamen Helfer — jede Datei seedet inline.

**Rot durch das Gate (9 Stellen):**

| Datei:Zeile | Test | Pfad |
|---|---|---|
| `auth_test.go:442` (Seed `:448`) | `TestLoginHandlerSuccess` | Passwort |
| `auth_traversal_test.go:177` (Seed `:180`) | `…ValidCredentials_StillWorks_AC2` | Passwort |
| `auth_traversal_test.go:383` (Seed `:386`) | `TestResetPassword_RealUserStillWorks_AC7` | Reset → Passwort |
| `session_issuance_test.go:89` (`mintViaPassword`) | Sechs-Wege-Tabelle | Passwort |
| `passkey_test.go:364` / `:450` | Login-Roundtrip, Cookie-Secure | Passkey-Login |
| `session_issuance_test.go:170` (`mintViaPasskeyLogin`) | Sechs-Wege-Tabelle | Passkey-Login |
| `passkey_test.go:1129` / `:1272` (erster Call) | Discoverable-Roundtrip, Replay-401 | Passkey discoverable |
| `session_issuance_test.go:204` (`mintViaPasskeyDiscoverable`) | Sechs-Wege-Tabelle | Passkey discoverable |

**Grün geblieben, gegengeprüft:** Magic-Link-Tests (`auth_magic_test.go:205`, `:403`,
`session_issuance_test.go:107`) — die Heilung läuft vor `issueSession`, die Adresse stimmt
überein. Google-OAuth (`session_issuance_test.go:134` setzt das Feld bereits explizit;
`auth_oauth_test.go` ohnehin ausgenommen). `change_password_test.go:31` (ausgenommen). Die
*Begin*-Handler-Tests berühren `issueSession` nie. `data_export_test.go:270/457`,
`logout_test.go:53/81/84`, `verify_resend_test.go:151` bauen ihr Cookie direkt über
`s.AddSession` + `middleware.SignSessionWithID` — am Gate vorbei, nicht betroffen.

### 🔴 Struktureller Konflikt: die Sechs-Wege-Zusicherung

`session_issuance_test.go:283` enthält eine harte Zusicherung `if len(ways) != 6 { t.Fatalf }`.
Fällt `issueSession` bei der öffentlichen Passkey-Registrierung weg, lässt sich
`mintViaPasskeyRegistration` **nicht** ersatzlos aus der Liste streichen, ohne genau diese
Zusicherung anzufassen. Das ist die Testseite derselben Entscheidung, die ADR-0066 festhält —
beides muss zusammenpassen, sonst wird die Rücknahme an einer Stelle dokumentiert und an der
anderen stillschweigend weggekürzt.

### Wegfall des Auto-Logins (`passkey.go:565`) — betroffene Zusicherungen

| Datei:Zeile | Zusicherung heute |
|---|---|
| `passkey_public_test.go:169`, Cookie-Asserts `:224-241` | `gz_session` gesetzt, `HttpOnly`, `SameSite=Lax`, `MaxAge`, Wertpräfix `passwordless.` |
| `passkey_public_test.go:402`, Subtest `https_secure` `:441`, `found` `:480-482` | Cookie gefunden **und** `Secure=true` |
| `passkey_public_test.go:402`, Subtest `http_not_secure` | Schleifenkörper läuft künftig nie — die Zusicherung wird **leer**, ohne rot zu werden ⚠️ |
| `session_issuance_test.go:234` (`mintViaPasskeyRegistration`) | `t.Fatalf`, wenn kein Cookie |

Nicht betroffen: `passkey_public_test.go:254` (nur 201 + Mail-Dispatch), `:357` (409-Race).

### Playwright

**(a) `*.staging.setup.ts` — ca. 38 Dateien, alle mit festen Kontonamen** (`bundle-i-e2e-user`,
`e2e675user`, `e2e774user`, sonst `GZ_AUTH_USER`/`GZ_VALIDATOR_USER`, Rückfall `admin`).
Feste Namen heißt: vom Nachtrag aus S1 miterledigt. Der tatsächliche Zustand liegt allerdings
auf dem Staging-Server und ist aus dem Repository **nicht** ablesbar — er gehört gemessen, nicht
angenommen.

**(b) 🔴 Vier Specs erzeugen den zweiten Nutzer mit Laufzeit-Suffix** — strukturell nie durch
einen Nachtrag erreichbar, weil jeder Lauf einen neuen Namen erfindet:
`compare-cross-user-write-block.spec.ts:69`, `compare-editor-autosave-user-isolation.spec.ts:71`,
`feat-1461-s3b2b-compare-kanal-schwelle.spec.ts:420`, `feat-1745-a-alarm-premium-sms.spec.ts:307`.
Genau dafür gibt es den Staging-Testweg aus S1 (`staging_verify_token.go`). Sonderfall:
`pwa-offline-sperre-und-mandant.spec.ts:93` nutzt den **festen** Namen `e2e2131nutzerb` und
akzeptiert 409/429 — wiederverwendet, also vom Nachtrag erfasst.

**(c) Öffentliche Passkey-Registrierung in E2E:** keine. Volltextsuche über `frontend/e2e/*.ts`
und `frontend/src` nach `register/public` / `passwordless` liefert **null Treffer**.
`passkey-konto.spec.ts` und `passkey-regression.spec.ts` verwalten Passkeys ausschließlich für
bereits angemeldete Bestandskonten. Bestätigt R4.

---

# Analysis

Erstellt in Phase 2 (2026-09-12). Grundlage: die Inventur oben, eine strategische Bewertung
durch einen Plan-Agenten und vier eigene Gegenprüfungen am Quelltext.

## Type

**Feature** — neue Zugangsbedingung, kein Fehlverhalten des Bestands. Sicherheitsmotiviert
(`priority:critical`). Die Entscheidungen A1–A7 aus dem Vorgänger-Dokument bleiben gültig; hier
steht nur, was sie für die Umsetzung konkret bedeuten.

## Die Vorbedingung ist erfüllt — selbst gemessen, nicht übernommen

| Umgebung | Konten | mit `email_verified_at` | offen |
|---|---|---|---|
| Produktion (`/var/lib/gregor/users/`) | 3 | 3 | **0** |
| Staging (`/var/lib/gregor-staging/users/`) | 63 | 63 | **0** |

Gemessen am 2026-09-12 mit erhöhten Rechten. Kein Bestandskonto wird durch die Scharfschaltung
ausgesperrt.

## A8 — 🔴 Die Reihenfolge Heilung-vor-Gate ist bei OAuth heute UNBEWACHT

Bei Magic-Link fängt die Vertauschung sich selbst: `mintViaMagicLink`
(`session_issuance_test.go:107-131`) seedet unverifiziert und prüft `w.Code != 200`. Stünde das
Gate vor der Heilung, kippte der Test auf 403.

Bei Google-OAuth **nicht.** Gegengeprüft: `mintViaGoogle` (`session_issuance_test.go:141-145`)
seedet den Account **vorverifiziert** (`EmailVerifiedAt: &verified`).
`selfHealEmailVerification` steigt dort wegen `auth.go:800` sofort aus — auf die Reihenfolge
kommt es in diesem Test gar nicht an. **Eine Vertauschung wäre unsichtbar.**

Verschärfend: Erfolg und Ablehnung sind bei OAuth **beide** `302` (`auth_oauth.go:192` gegen die
künftige Weiterleitung auf `/login?error=email_not_verified`). Ein Statuscode-Assert bewacht
dort also nichts — geprüft werden muss der **`Location`-Header**.

**Folge für die Spec:** Ein neuer Test ist Pflicht — Bestandskonto **unverifiziert** anlegen,
dessen Adresse der von `oauthFakeServers` gelieferten entspricht, Callback aufrufen, und zwei
Dinge in derselben Funktion zusichern: `Location: /` (nicht der Fehler-Pfad) **und** der frisch
nachgeladene Nutzer hat `EmailVerifiedAt != nil`.

Derselbe Test deckt einen zweiten Ordnungsfall ab, den S2 neu einführt: Die
Redirect-Vorprüfung aus A1 muss **nach** der Heilung stehen, sonst weist sie genau das Konto
ab, das sich in diesem Request gerade selbst heilt.

## A9 — Die Sechs-Wege-Tabelle wird zu 5 + 4 + 1, mit Zähler je Gruppe

`session_issuance_test.go:283` hat heute `if len(ways) != 6 { t.Fatalf }`. Diese Zusicherung
darf nicht ersatzlos fallen, sonst wird die Rücknahme aus ADR-0066 auf der Testseite still
weggekürzt.

| Gruppe | Wege | Zusicherung |
|---|---|---|
| **Positiv (5)** — stellt aus | Passwort · Magic-Link · Google · Passkey-Login · Passkey ohne Kennungseingabe, je mit verifiziertem bzw. sich heilendem Ausgangszustand | `len(issuing) != 5 → Fatalf`; Cookie wie bisher |
| **Negativ (4)** — verweigert | Passwort · Passkey-Login · Passkey ohne Kennungseingabe, je unverifiziert · **NEU: Google mit Adress-Abweichung** | `len(blocking) != 4 → Fatalf`; 403 `email_not_verified` bzw. `Location=…error=email_not_verified`; **kein** Cookie |
| **Sonderfall (1)** | öffentliche Passkey-Registrierung | eigener Test: 201, **kein** Cookie, Hinweis „Bestätigung ausstehend" |

Der vierte Negativfall ist der Grund, warum die Redirect-Ausnahme aus A1 überhaupt nötig ist:
Steht `MailTo` auf einer anderen Adresse als die von Google bestätigte, greift der Deny-Zweig
wirklich. Ohne diesen Fall bliebe der Zweig toter Code.

**Der Zähler je Gruppe ist nicht Kosmetik.** Eine Tabelle ohne ihn fängt einen vergessenen oder
unbemerkt hinzugefügten Blockierfall nicht — genau das, wogegen die alte `!= 6`-Zeile stand.

### ⚠️ Die Falle im geteilten Seeder

`registerForUserAt` (`passkey_test.go:962`) seedet ohne `EmailVerifiedAt` — ein Fix dort heilt
alle Passkey-Login-Tests auf einen Schlag. **Aber:** Danach erreicht kein Test, der über diesen
Helfer läuft, je wieder den Deny-Zweig.

Gegengeprüft und **entschärfender Befund**: Der Helfer seedet nur unter
`if existing, _ := s.LoadUser(userID); existing == nil` (`passkey_test.go:969`). Ein Test, der
den Nutzer **vorher** selbst unverifiziert anlegt, gewinnt — der Helfer lässt ihn unangetastet.
Die Negativfälle brauchen also keinen zweiten Helfer, nur ein vorgeschaltetes `SaveUser` ohne
`EmailVerifiedAt`. Das ist in der Spec zu benennen, damit es nicht zufällig richtig gebaut wird.

## A10 — `TestPasskeyRegisterPublicFinish_CookieSecureFlag` entfällt vollständig

Beide Teiltests (`passkey_public_test.go:402-485`) prüfen eine Eigenschaft des dort
ausgestellten Cookies. Nach A3 gibt es dieses Cookie nicht mehr — es bleibt nichts zu prüfen.

Die Asymmetrie ist das eigentliche Argument: `https_secure` fiele **laut** rot (`found`-Assert
`:480-482`), `http_not_secure` liefe **lautlos leer** durch (Schleife über null Cookies). Ein
repariertes Paar, bei dem eines stumm nichts mehr bewacht, ist schlechter als ein entferntes.

**Kein Deckungsverlust** — dieselbe `SetSessionCookie`-Logik (`middleware/auth.go:210`,
`X-Forwarded-Proto`) bleibt über den Passkey-**Login**-Pfad geprüft (`passkey_test.go:441`,
`:499`). 🔴 Das gilt allerdings erst, **nachdem** dort der Seed auf verifiziert gefixt ist —
dieselben Tests stehen auf der roten Liste. Reihenfolge im Commit beachten.

## A11 — Frontend: SvelteKit erzwingt benannte Actions

`default` und benannte Actions können in SvelteKit nicht koexistieren. Der Resend braucht eine
zweite Action, also wird die bestehende umbenannt.

| Datei | Änderung |
|---|---|
| `login/+page.server.ts` | `default` → `login`; neue Action `resend` (Nutzlast `{username}`, POST an `/api/auth/verify-email/resend`, antwortet **immer** `{resent:true}` — das Backend antwortet ohnehin immer 200) |
| `login/+page.server.ts:35-37` | 403 aus dem pauschalen `!resp.ok`→401-Mapping herauslösen: eigener Zweig `email_not_verified` |
| `login/+page.svelte:59` | `<form method="POST">` → `action="?/login"` |
| `login/+page.svelte:53-56` | neuer Fehlerzweig + kleines zweites Formular (`action="?/resend"`, verstecktes `username`, Button „Bestätigungsmail erneut senden"), danach Bestätigung über `form?.resent` |
| `login/+page.svelte:43` | Text nach der Registrierung: nicht mehr „Bitte melde dich an", sondern Hinweis auf die Bestätigungsmail |

**Gegengeprüft, dass der Umbau E2E nicht bricht:** Der Playwright-Login-Helfer
(`frontend/e2e/helpers.ts:97-105`) füllt die Felder und klickt `button[type="submit"]` — er ist
an keinen Action-Pfad gebunden. Beim Implementieren ist `global.setup.ts` nach demselben Muster
gegenzulesen.

## A12 — Umfang und Reihenfolge

**LoC-Override auf 500 ist nötig.** Die Vorgänger-Schätzung (~170) unterschätzt zwei Posten: A9
verlangt eine echte Vier-Wege-Negativtabelle plus Sonderfalltest statt einer geänderten Zahl,
und A11 ist eine zweite Form-Action mit Bedien-Fläche, nicht ein Textaustausch.

| Baustein | ~LoC |
|---|---|
| Backend-Kern (Gate, Prädikat, OAuth-Vorprüfung, Auto-Login-Wegfall) | ~55 |
| Frontend (zwei Actions, Resend-Fläche, zwei Texte) | ~55 |
| Go-Tests (9 Seed-Fixes, Umbau 5+4+1, neuer OAuth-Ordnungstest, Sonderfall) | ~180–220 |
| Playwright (4 Specs auf den Staging-Testweg, 1 neue Gate-Spec) | ~90–130 |
| ADR-0066 + `session_allowlist.md` | zählt nicht |

**Reihenfolge — keine Präferenz, sondern die einzige Form ohne Rot-Fenster:**

1. **Eine atomare Scheibe:** Gate in `issueSession` + alle 9 roten Seeds + Umbau der
   Sechs-Wege-Tabelle + Auto-Login-Wegfall + Löschung von `CookieSecureFlag`. Jede Teilmenge
   für sich lässt den Rest rot.
2. **ADR-0066 und die Spec-Fortschreibung im SELBEN Commit** — `tests/test_adr_index_drift.py`
   erzwingt Index↔Datei-Konsistenz; ein ADR ohne Eintrag in `docs/adr/README.md` reißt die
   Python-Ampel. Vorher gegen `origin/main` prüfen, ob `0066` noch frei ist — es liefern gerade
   Parallelsitzungen aus.
3. **Frontend** — unabhängig von der Go-Testfläche.
4. **Playwright zuletzt** — die vier Laufzeit-Specs auf den Staging-Testweg aus S1 umstellen,
   plus die neue Gate-Spec (Registrierung → 403 → Testweg-Token → verifizieren → 200).

## Scope Assessment

- **Dateien:** ~14 (Backend 4, Frontend 2, Go-Tests 5, Playwright 5, Doku 3)
- **Geschätzte LoC:** ~380–460 → **Override auf 500 erforderlich**
- **Risk Level: HIGH** — Auth, kritischer Pfad, Verhaltensänderung für jeden Nutzer

## Offene Punkte — Stand nach der Analyse

Beantwortet in dieser Phase: Reihenfolge-Prüfung (A8) · Fortschreibung der Sechs-Wege-Tabelle
(A9) · Umgang mit `http_not_secure` (A10) · Bedien-Fläche für den Resend und der
Registrierungs-Hinweistext (A11) · Umfang und Reihenfolge (A12) · Ist-Zustand beider
Umgebungen (gemessen, 0 offen).

**Für den PO in der Spec-Freigabe:**

- [ ] **Antwortform (R1):** `403 {"error":"email_not_verified"}` **nach** bestandener
      Passwortprüfung. Wer ein geleaktes Passwort ausprobiert, erfährt dadurch zusätzlich, dass
      Konto und Passwort stimmen. Der Gegenvorschlag wäre eine einheitliche 401 — dann sieht
      der rechtmäßige Nutzer „Benutzername oder Passwort nicht korrekt" und setzt sein Passwort
      zurück, was nichts hilft. Empfehlung: 403, weil die Meldung sonst nutzlos wird. Gehört
      als benanntes Acceptance Criterion in die Spec, nicht stillschweigend in den Code.

**Für die Umsetzung, kein PO-Entscheid:**

- [ ] ADR-Nummer `0066` unmittelbar vor dem Schreiben erneut gegen `origin/main` prüfen —
      Parallelsitzungen liefern gerade aus
- [ ] `frontend/e2e/global.setup.ts` beim Frontend-Umbau gegenlesen (Action-Bindung wie in
      `helpers.ts`)
