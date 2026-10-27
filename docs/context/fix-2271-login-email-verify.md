# Context: fix-2271-login-email-verify

Issue: [#2271](https://github.com/henemm/gregor_zwanzig/issues/2271) — Scheibe 4 von 4 aus #2146, Teil von Epic #2138 (Multi-User-Readiness). Label `priority:critical`.

## Request Summary

Die Anmeldung soll erst nach bestätigter E-Mail-Adresse möglich sein (PO-Entscheid 2026-09-09: Registrierung bleibt offen, E-Mail-Bestätigung wird Pflicht) — ohne dabei bestehende Konten auszusperren und ohne eine neue Kontenaufzählung zu schaffen.

## Ist-Stand der Daten (gemessen 2026-09-11 mit erhöhten Rechten)

Die vom Ticket ausdrücklich geforderte Vorab-Messung. Ergebnis auch als [Kommentar an #2271](https://github.com/henemm/gregor_zwanzig/issues/2271#issuecomment-5630152239) hinterlegt.

| Umgebung | Pfad | Konten | davon `email_verified_at` gesetzt |
|---|---|---|---|
| Produktion | `/var/lib/gregor/users/` | 3 mit `user.json` | 2 (`henning`, `steffi`, beide `2026-07-10T16:59:20Z`) |
| Staging | `/var/lib/gregor-staging/users/` | 63 | **0** |

- Produktion: nur `default` ist unbestätigt (hat Passwort-Hash, `email` leer, `mail_to` gesetzt). `validator-issue110` hat keine `user.json`.
- Der identische Zeitstempel bei `henning`/`steffi` stammt aus `scripts/migrate_1219_email_verified.py` (Positivliste `["henning","steffi"]`) — es gab also bereits genau einen solchen Nachtrag-Lauf.
- Staging: **alle 63 Konten unbestätigt**, inklusive `admin` (der E2E-Testnutzer) und `default`.

## Related Files

### Go-Backend — Session-Ausstellung

| Datei | Relevanz |
|------|-----------|
| `internal/handler/auth.go:129-147` | `issueSession` — **der einzige** Session-ausstellende Pfad. `SetSessionCookie`/`AddSession`/`SignSessionWithID` werden nirgends sonst direkt gerufen. Damit ist dies die natürliche Stelle für eine nicht umgehbare Prüfung. |
| `internal/handler/auth.go:149-199` | `LoginHandler` — Passwort-Login. Prüft `EmailVerifiedAt` an keiner Stelle. Die einzige im Ticket genannte Stelle. |
| `internal/handler/auth_magic.go:186` | Magic-Link-Login stellt Session aus. |
| `internal/handler/auth_oauth.go:181` | Google-OAuth-Callback stellt Session aus. |
| `internal/handler/passkey.go:258, 359, 565` | Drei Passkey-Wege stellen Session aus. |
| `internal/handler/auth.go:921` | `ChangePasswordHandler` — kein eigener Anmeldeweg, sondern Merkmal-Erneuerung bei bestehender Sitzung. |

### Go-Backend — Verifikationsmechanik

| Datei | Relevanz |
|------|-----------|
| `internal/model/user.go:32` | `EmailVerifiedAt *time.Time` (`email_verified_at,omitempty`), aus #1219. |
| `internal/model/user.go:12, 16` | `Email` und `MailTo` — zwei Adressfelder, `MailTo` hat Vorrang. |
| `internal/model/user.go:49-50` | `EmailVerificationToken{TokenHash, ExpiresAt}` — separater Store, nicht im Nutzer-Objekt. |
| `internal/handler/auth.go:754-840` | `dispatchVerificationMail` — Empfänger ist `MailTo`, ersatzweise `Email`; **stiller No-op** ohne Rückgabewert, wenn beide leer. Token 32 Byte, bcrypt-gehasht, 24 h gültig. |
| `internal/handler/auth.go:434-490` | `VerifyEmailHandler` — **einzige** Stelle, die `EmailVerifiedAt` setzt (`:479-480`, Read-Modify-Write). |
| `internal/handler/auth.go:707, 712` | `UpdateProfileHandler` setzt `EmailVerifiedAt = nil` bei tatsächlicher Adressänderung und stößt Resend an (`:737-739`). |
| `internal/mail/verify.go:13-37` | `BuildVerificationMail` — Link `{PublicHost}/verify-email?user=…&token=…`. |
| `internal/router/router.go:41-127` | Alle Auth-Routen samt Ratenlimits. |

### Frontend

| Datei | Relevanz |
|------|-----------|
| `frontend/src/routes/login/+page.server.ts:35-37` | Mappt **jede** Nicht-OK-Antwort (außer 429) pauschal auf `'Invalid credentials'` — eine neue Backend-Meldung käme beim Nutzer ohne Frontend-Änderung nicht an. |
| `frontend/src/routes/login/+page.svelte:53-56` | Textzuordnung der Fehlerfälle; kein Zweig für „nicht bestätigt". |
| `frontend/src/routes/verify-email/+page.svelte` / `+page.server.ts` | **Existiert bereits** — Bestätigungsseite, öffentlich erreichbar (`hooks.server.ts:25`). |
| `frontend/src/lib/components/shared/versand-tab/channelConnectionStatus.ts:49-52` | Zeigt „bestätigt"/„nicht bestätigt" im Versand-Tab — reine Anzeige, blockiert nichts. |

### Backfill

| Datei | Relevanz |
|------|-----------|
| `scripts/migrate_1219_email_verified.py` | **Exaktes Vorbild** — setzt `email_verified_at` für eine Positivliste. Dry-Run per Default, `--execute`, Pflicht-`--root`, tar.gz-Backup, idempotent, Read-Modify-Write. |
| `cmd/migrate1257/`, `cmd/migrate1258/` | Alternatives Go-Muster, wenn Store-Logik gebraucht wird. Hier nicht nötig. |

## Die sechs Anmeldewege und was sie beweisen

Kern der Analyse — eine Prüfung allein im `LoginHandler` wäre über fünf andere Wege umgehbar, eine pauschale Sperre in `issueSession` würde dagegen den Wiedereinstieg zumauern.

| # | Weg | Route | Ausweismittel | Beweist Mailbox-Zugriff? |
|---|---|---|---|---|
| 1 | Passwort | `POST /api/auth/login` | Passwort (bcrypt) | **Nein** — reines Wissensgeheimnis |
| 2 | Magic-Link | `POST /api/auth/magic-link/verify` | 6-stelliger Code, per Mail an `Email` zugestellt | **Ja** — nur wer die Mailbox liest, kennt den Code |
| 3 | Google-OAuth | `GET /api/auth/google/callback` | Google-Token, Zuordnung über `OAuthSub` | **Teilweise** — bei Erstanlage prüft der Code Googles `email_verified` (`auth_oauth.go:150`), danach nie wieder; Adresse wird nicht aktualisiert |
| 4 | Passkey (Username) | `POST /api/auth/passkey/login/finish` | WebAuthn-Signatur | **Nein** — Gerätebesitz |
| 5 | Passkey (Discoverable) | `POST /api/auth/passkey/discoverable/finish` | WebAuthn-Signatur, Resident-Key | **Nein** — Gerätebesitz |
| 6 | Passkey-Registrierung (öffentlich) | `POST /api/auth/passkey/register/public/finish` | WebAuthn-Attestation; `Email`/`MailTo` kommen **unverifiziert** aus dem Request-Body | **Nein** — Session wird sofort ausgestellt (`passkey.go:565`), während die Bestätigungsmail (`:563`) noch unterwegs ist |

**Keiner dieser Wege setzt `EmailVerifiedAt`.** Auch Weg 2 nicht, obwohl er Mailbox-Zugriff nachweislich belegt — das Feld bleibt `nil`, bis der Nutzer zusätzlich den Link aus der separaten Verifikationsmail einlöst.

## Risks & Considerations

### R1 — Staging sperrt sich vollständig selbst aus (🔴 blockierend für die Liefer-Kette)

63 von 63 Staging-Konten sind unbestätigt, `admin` eingeschlossen. Ein Resend hilft dort strukturell **nicht**, weil Staging Auth-Mails gar nicht zustellen kann (#1337 Egress-Sperre + Resend-Sperre). Ohne Vorbereitung fällt damit Schritt 3 der Liefer-Kette (Staging-Validierung) aus — ausgerechnet bei dem Feature, das dort validiert werden soll. Der Nachtrag muss **beide** Umgebungen abdecken und „als bestätigt eintragen" heißen, nicht „Bestätigungsmail schicken".

### R2 — Eine Prüfung nur im `LoginHandler` verfehlt das Sicherheitsziel

Das Ticket begründet sich damit, dass „unbestätigte Adressen vollen Kontozugriff erhalten". Genau das leistet heute Weg 6 (öffentliche Passkey-Registrierung): beliebige Adresse angeben, Session sofort. Ein Gate allein im Passwort-Login ließe diese Lücke offen.

### R3 — Eine pauschale Sperre in `issueSession` mauert den Wiedereinstieg zu

Weg 2 (Magic-Link) ist der einzige Weg, der Mailbox-Besitz beweist. Wird er mitgesperrt, hat ein unbestätigtes Konto **keinen** Weg zurück — außer der Verifikationsmail, die es womöglich nie erreicht hat. Naheliegender ist, dass dieser Weg `EmailVerifiedAt` **setzt**, statt zu blockieren. Das ist eine Entscheidung, die die Spec pro Weg treffen muss.

### R4 — Keine neue Kontenaufzählung

Der Bestand antwortet konsequent enumerationsfrei: `LoginHandler` gibt in allen Fehlerfällen identisch 401 `invalid credentials` (`auth.go:172, 180, 187`), `ForgotPasswordHandler` immer 200 `ok`, `VerifyEmailHandler` immer `invalid token`. Eine unterscheidbare Antwort „E-Mail nicht bestätigt" verrät, dass das Konto existiert — und dass das Passwort stimmte. Zielkonflikt mit der Ticket-Forderung nach „verständlicher Meldung"; auflösbar, weil die Meldung erst **nach** erfolgreicher Passwortprüfung kommt, also nur jemandem, der die Zugangsdaten ohnehin kennt. Das gehört als bewusste Entscheidung in die Spec, nicht als stiller Nebeneffekt.

### R5 — Es gibt keinen Resend-Endpoint

`dispatchVerificationMail` wird nur aus Registrierung (`auth.go:115`), OAuth-Neuanlage (`auth_oauth.go:178`), Passkey-Registrierung (`passkey.go:563`) und Profil-Adressänderung (`auth.go:737`) gerufen. In `router.go` existiert keine Resend-Route. Die vom Ticket geforderte Möglichkeit, die Bestätigungsmail erneut anzufordern, ist neue Fläche: Handler + Route + Ratenlimit (Muster: 5/Stunde wie `register`/`forgot-password`) + Frontend-Einstieg. Die Route muss selbst enumerationsfrei antworten.

### R6 — Rund ein Dutzend Tests wird rot

- **Go (~8 Tests):** `auth_test.go:442` (`TestLoginHandlerSuccess`), `auth_traversal_test.go:177, 383`, `session_issuance_test.go:89, 107, 170, 200`, `auth_magic_test.go:205`. Alle legen Konten ohne `EmailVerifiedAt` an und erwarten 200. Bemerkenswert: `session_issuance_test.go:134` (`mintViaGoogle`) setzt das Feld bereits explizit — die Konvention existiert also schon punktuell.
- **Playwright:** `frontend/e2e/helpers.ts:93-106` und `global.setup.ts:36-46` melden den festen `admin` an; mehrere Specs (`compare-cross-user-write-block`, `pwa-offline-sperre-und-mandant`, `compare-editor-autosave-user-isolation`, `feat-1745-a-alarm-premium-sms`, `feat-1461-s3b2b-compare-kanal-schwelle`) registrieren Zweitnutzer per API und loggen sofort ein.

Diese Tests sind **kein** Kollateralschaden, den man wegschreibt: dass sie rot werden, ist der Nachweis, dass das Gate greift. Sie müssen bewusst angepasst werden, nicht entschärft.

Für die Go-Tests genügt dafür `SaveUser` mit gesetztem Feld. **Für die Playwright-Specs nicht** — und das ist eine Entwurfsbedingung, kein Detail:

### R6b — Auf Staging zur Laufzeit erzeugte Konten sind dauerhaft unbestätigbar (🔴)

Die Zweitnutzer-Specs legen ihre Konten **über HTTP** an (`page.request.post('/api/auth/register', …)`). Sie haben keinen Store-Zugriff und können kein Feld setzen. Der einzige Produktweg zur Bestätigung ist der Mail-Link — und Staging kann Auth-Mails strukturell nicht zustellen (#1337). Ein dort zur Laufzeit erzeugtes Konto ließe sich also **nie** bestätigen.

Das ist ein Dauerzustand, kein Migrationsproblem: ein Backfill repariert die 63 Bestandskonten, die nächste E2E-Runde erzeugt neue tote. Betroffen sind ausgerechnet die Specs, die die Mandantentrennung bewachen (zwei verschiedene Nutzer — CLAUDE.md-Pflicht bei jedem datenbewegenden Endpoint). Die Lösung braucht daher einen serverseitigen Hebel, der Bestätigung ohne Mailzustellung herstellt; welchen, entscheidet `/20-analyse`.

### R1b — „Backfill vor Scharfschaltung" ist auf Staging nicht durch Reihenfolge erreichbar

Auf Produktion ist der Deploy ein Handgriff, dort lässt sich die Reihenfolge einhalten. Auf Staging zieht der Cron `*/5` automatisch `origin/main` — das Gate ist dort ~5 Minuten nach dem Merge scharf, bevor ein Hand-Backfill laufen könnte. `admin` wäre in diesem Fenster ausgesperrt, und `/e2e-verify` käme nicht mehr hinein, um überhaupt zu validieren. Ein Rennen zwischen Cron und Handarbeit ist keine Lieferform. Drei mögliche Auflösungen, zu prüfen in `/20-analyse`:

1. Gate hinter einem Schalter, Default aus, Scharfschaltung als eigener Ops-Schritt — die einzige Form ohne Rennen.
2. Backfill unmittelbar nach dem Merge auf `/var/lib/gregor-staging` von Hand. Schreibzugriff ist vorhanden (`sudo`, Verzeichnis gehört `claude-gregor`), löst aber das Rennen nicht und hilft R6b nicht.
3. Backfill beim Server-Start — dieses Muster existiert im Repo nicht (`cmd/server/main.go` hat keinen Migrations-Aufruf), wäre also neue Fläche.

### R7 — LoC-Limit

Login-Gate + Resend-Endpoint + Frontend-Meldung + Backfill-Skript + Testanpassungen reißen die 250 LoC voraussichtlich. `workflow.py set-field loc_limit_override 500` einplanen.

## Dependencies

- **Upstream:** `store.LoadUser`/`SaveUser`, `model.User.EmailVerifiedAt`, `dispatchVerificationMail`, `config.PublicHost`. Letzteres **nachgemessen**: `config.go:39` deklariert `envconfig:"PUBLIC_HOST"`, `config.go:55` verarbeitet mit Präfix `GZ` — die wirksame Variable ist also `GZ_PUBLIC_HOST`, genau die, die der systemd-Dienst auf Staging setzt. Gegenprobe von außen: `https://staging.gregor20.henemm.com/api/health` meldet `webauthn_rpid: staging.gregor20.henemm.com`. Der Default (= Produktivadresse) greift dort also **nicht**, Verifikationslinks aus Staging zeigen auf Staging.
- **Downstream:** Alle sechs Anmeldewege, das Frontend-Login, sämtliche Playwright-Specs, der E2E-Testnutzer `admin`.

## Existing Specs

Keine Spec beschreibt bisher eine Verifikationspflicht beim Login — `email_verified_at` diente ausschließlich der Resend-Eignung und der Anzeige.

- `docs/specs/modules/session_allowlist.md` — #2129, deckt die sechs Anmeldewege ab (aktuell gültig, direkt berührt)
- `docs/specs/modules/sveltekit_login_refactor.md`, `register_page.md`, `google_oauth_login.md`, `password_reset.md`, `change_password.md`
- `docs/specs/bugfix/login_rate_limit.md`, `register_rate_limit.md`, `forgot_reset_rate_limit.md`
- Archiviert, inhaltlich zentral: `docs/specs/_archive/modules/fix_1219_email_verify.md` (führt das Feld ein — ausdrücklich **nicht** als Login-Gate), `fix_1226_register_verify.md` (Dispatch-Trigger bei allen drei Kontoerstellungspfaden)

## Offene Punkte für `/20-analyse`

1. Entscheidung **pro Anmeldeweg**: blockieren, durchlassen oder `EmailVerifiedAt` setzen (R2/R3).
2. Wo sitzt die Prüfung — `issueSession` mit Ausnahmeliste oder je Handler? (Nicht umgehbar vs. nicht zumauernd.)
3. Antwortform des Gates, die R4 auflöst.
4. Zuschnitt des Backfill-Laufs: Positivliste oder pauschal, und wie die 63 Staging-Konten erfasst werden.
5. Reihenfolge der Auslieferung — Backfill **vor** Scharfschaltung, sonst sperrt der Zwischenstand aus.
6. Serverseitiger Hebel für zur Laufzeit erzeugte Staging-Konten (R6b) — ohne ihn scheitert die eigene E2E-Ampel in `/70-deploy`, egal wie sauber die ACs sind.
7. Lieferform gegen das Cron-Rennen auf Staging (R1b) — Schalter, Hand-Backfill oder Start-Migration.
8. ~~Prüfen, ob `PublicHost` auf Staging wirklich greift~~ — **erledigt 2026-09-11**, greift (siehe Dependencies).

---

# Analysis

Erstellt in Phase 2 (2026-09-11). Grundlage: die Kartierung oben, eine strategische Bewertung durch einen Plan-Agenten und drei eigene Nachmessungen.

## Type

**Feature** — neue Zugangsbedingung, kein Fehlverhalten des Bestands. Sicherheitsmotiviert (Label `priority:critical`).

## Korrektur aus der Nachmessung

Die Kartierung in Phase 1 sagte zu Weg 3 (Google-OAuth) „prüft nur bei Erstanlage". **Das ist falsch.** `internal/handler/auth_oauth.go:150-154` prüft `userinfo.EmailVerified` bei **jedem** Callback, noch vor der Verzweigung zwischen bestehendem und neuem Konto — ein Google-Login mit unbestätigter Google-Adresse kommt gar nicht bis zur Session-Ausstellung. Die Tabelle der Anmeldewege oben ist an dieser Stelle entsprechend zu lesen.

Zwei weitere Messungen:
- Das Staging-only-Registrierungsmuster existiert und ist Präzedenzfall: `internal/router/router.go:215` — `if os.Getenv("GZ_ENV") == "staging"` (Issue #830). **Wichtig:** Produktion setzt `GZ_ENV` gar nicht, ein `!=`-Vergleich wäre dort also aktiv. Nur `== "staging"` ist sicher.
- Kein Automatismus meldet sich als `default` per HTTP an. Die Treffer für `"default"` im Python-Core (`inbound_email_reader.py:296`, `inbound_telegram_reader.py:399` u. a.) sind interne Fallback-Kennungen beim Zuordnen eingehender Nachrichten, keine Anmeldungen.

## Technical Approach

### A1 — Die Prüfung sitzt in `issueSession` und lädt selbst nach

`issueSession` (`auth.go:129-147`) lädt den Nutzer per `LoadUser` selbst und prüft `EmailVerifiedAt` — **kein** Flag, das Aufrufer mitgeben. Begründung: Ein Parameter wäre genau die Umgehungslücke, vor der das Ticket warnt — ein künftiger siebter Anmeldeweg müsste sich aktiv erinnern, ihn korrekt zu berechnen. Lädt die Funktion selbst nach, erbt jeder neue Aufrufer die Prüfung, ohne etwas dafür zu tun; sie zu umgehen erforderte, bewusst eine andere Funktion zu suchen.

Die Tabelle in `session_issuance_test.go:284` ist dafür **kein** Ersatz: Sie fängt nur Wege, die jemand dort einträgt. Sie ist zweiter Kontrollpunkt, nicht Durchsetzung.

Zwei Ausnahmen, beide als **eigene, anders benannte Funktion** — nicht als Parameter:
- **`ChangePasswordHandler`** (`auth.go:921`) ist kein Anmeldeweg, sondern erneuert das Merkmal einer bereits angemeldeten Sitzung. Mit Prüfung könnte jemand, der eben seine Adresse geändert hat (`auth.go:707` setzt dabei `EmailVerifiedAt = nil`), sein Passwort nicht mehr ändern — Fehlverhalten ohne Sicherheitsgewinn.
- **Google-OAuth** (`auth_oauth.go:181`) antwortet mit `http.Redirect`, nicht mit JSON. Ein zentraler Deny-Zweig, der einen JSON-Body schreibt, brächte eine rohe JSON-Antwort in einen Redirect-Fluss. Der Handler prüft daher selbst vor dem Aufruf (dieselbe Prädikatsfunktion) und leitet bei Ablehnung auf `/login?error=email_not_verified`.

### A2 — Entscheidung pro Anmeldeweg

| # | Weg | Entscheidung | Begründung |
|---|---|---|---|
| 1 | Passwort | **blockieren** | Wissensgeheimnis, beweist nichts über die Adresse |
| 2 | Magic-Link | **`EmailVerifiedAt` setzen, dann durchlassen** | Mailbox-Besitz ist bewiesen; Blockieren mauerte den einzigen Wiedereinstieg zu (R3) |
| 3 | Google-OAuth | **`EmailVerifiedAt` setzen, dann durchlassen** | Google bestätigt die Adresse bei jedem Callback (`auth_oauth.go:150`); heilt bestehende OAuth-Konten von selbst |
| 4 | Passkey (Username) | **blockieren** | Gerätebesitz |
| 5 | Passkey (Discoverable) | **blockieren** | Gerätebesitz |
| 6 | Passkey-Registrierung öffentlich | **Auto-Login entfällt** | siehe A3 |

**Bedingung für Wege 2 und 3 (wichtig):** Gesetzt wird nur, wenn die nachgewiesene Adresse mit der **effektiven Kontaktadresse** des Kontos übereinstimmt (`MailTo`, ersatzweise `Email` — dieselbe Vorrangregel wie `dispatchVerificationMail`, `auth.go:761-764`). Weicht sie ab, weil jemand `MailTo` im Profil auf eine andere Adresse gestellt hat, wird **nicht** gesetzt — sonst gälte eine Adresse als bestätigt, die niemand nachgewiesen hat. Dieser Fall macht den Deny-Zweig für OAuth real erreichbar; der Redirect-Vorbehalt aus A1 ist deshalb Pflicht, nicht Vorsichtsmaßnahme.

### A3 — Weg 6 verliert das Auto-Login, statt eine Fehlerantwort zu bekommen

`passkey.go:565` stellt heute die Sitzung aus, während die Bestätigungsmail (`:563`) noch unterwegs ist — das ist die Lücke, die das Ticket meint. Ein zentrales Gate, das hier mit 403 antwortet, gäbe einer **erfolgreichen** Kontoerstellung eine Fehlerantwort. Stattdessen entfällt der `issueSession`-Aufruf: 201 mit Hinweis „Bestätigung ausstehend", genau wie `RegisterHandler` (`auth.go:117-119`), der schon heute kein Auto-Login macht. Der Weg zurück führt über Passkey-Login (4/5), das das Gate regulär prüft.

🔴 **Das berührt eine dokumentierte Entscheidung.** `docs/specs/modules/session_allowlist.md` (#2129, approved) und ADR-0060 schreiben fest, dass alle sechs Anmeldewege ein Sitzungsmerkmal ausstellen. Nach CLAUDE.md wird eine dokumentierte Entscheidung nie still zurückgenommen: Es braucht ein **neues ADR** (Auth ist ausdrücklich Entscheidungsfläche), das ADR-0060 in diesem Punkt fortschreibt, plus eine Fortschreibung von `session_allowlist.md`. Die freie ADR-Nummer ist **gegen `origin/main`** zu bestimmen, nicht gegen den Worktree.

### A4 — Kein Schalter im Gate. Staging wird über Daten und einen Testweg gelöst, nicht über abgeschaltete Logik

Ein Schalter, der auf Staging „aus" steht, bedeutet nicht bloß „ungetestet": Der Deny-Zweig würde dort **nie ausgeführt**. Der sicherheitsrelevante Pfad bliebe unbelegt, egal wie grün die Ampel ist. Der Gate-Code ist deshalb in beiden Umgebungen identisch und immer aktiv. Stattdessen zwei unabhängige Bausteine:

**(a) gegen R1b (Cron-Rennen):** Der Nachtrag-Lauf gehört in eine **eigene, frühere Auslieferung** — nicht in denselben PR wie das Gate. Damit hat er keine Frist und kein Rennen gegen den `*/5`-Cron: Wenn der Gate-Code später nach `main` geht, ist die Datenlage längst korrekt. Das ist Variante 2 aus R1b, entschärft durch strikte zeitliche Entkopplung.

**(b) gegen R6b (zur Laufzeit erzeugte Konten):** Ein staging-only Endpoint nach dem #830-Muster, registriert nur bei `GZ_ENV == "staging"`, **anmeldepflichtig** wie jeder normale Endpoint.

Die Anmeldepflicht ist möglich, weil eine Annahme aus der strategischen Bewertung sich in der Messung nicht bestätigt hat. Sie lautete: Die drei `.staging.setup.ts`-Dateien hätten vor ihrem Login keine Sitzung, ein anmeldepflichtiger Endpoint sei für sie ein Henne-Ei-Problem, es brauche ein geteiltes Geheimnis. **Nachgemessen 2026-09-11:** Diese drei registrieren Konten mit **festen** Namen — `e2e675user`, `e2e774user`, `bundle-i-e2e-user` (`issue-675.staging.setup.ts:7`, `issue-774.staging.setup.ts:13`, `bundle-i.staging.setup.ts:18`), die Registrierung ist idempotent (`.catch(() => {})` schluckt den 409). Diese Konten sind Teil der 63 und werden vom Nachtrag miterledigt — sie brauchen den Endpoint überhaupt nicht.

Ihn braucht nur, wer Konten **zur Laufzeit neu** erzeugt: die fünf Zwei-Nutzer-Specs. Alle fünf haben einen angemeldeten Primärkontext (`admin` aus der storageState-Fixture) und legen Nutzer B daneben an (`compare-cross-user-write-block.spec.ts:53-69`, `compare-editor-autosave-user-isolation.spec.ts:47-71`, `feat-1745-a-alarm-premium-sms.spec.ts:304-307`, `feat-1461-s3b2b-compare-kanal-schwelle.spec.ts:417-420`, `pwa-offline-sperre-und-mandant.spec.ts:93`). Der Aufruf läuft über den Primärkontext.

**Folge:** kein neues Geheimnis in `/etc/henemm/secrets.env`, keine neue Env-Variable im systemd-Unit, keine Abhängigkeit zu `henemm-infra`. Das Risikoprofil ist deutlich enger. In der Spec zu benennen bleibt, dass ein angemeldeter Staging-Nutzer damit ein Token für ein fremdes Konto anfordern kann — hinnehmbar, weil der Endpoint in Produktion nicht existiert und nur ein Token ausgibt, das ohnehin an die Kontoadresse ginge.

🔴 **Abweichung vom Plan-Vorschlag, bewusst:** Der Endpoint setzt **nicht** `EmailVerifiedAt`, sondern gibt ein frisch erzeugtes **Verifikations-Token im Klartext** zurück. Der Test durchläuft damit den echten `POST /api/auth/verify-email`. Zwei Gründe: Erstens bleibt es dabei, dass ausschließlich ein echter Besitznachweis das Feld setzt — Wege 2 und 3 haben einen, ein Debug-Endpoint hätte keinen. Zweitens prüft der Test so den Produktionspfad `VerifyEmailHandler` mit, statt ihn zu überspringen. Die Wirkung für einen Geheimnisträger ist dieselbe, die geprüfte Fläche ist größer.

**Nachweis des Gates auf Staging:** genau eine neue E2E-Spec — Wegwerfnutzer registrieren → Anmeldung erwartet 403 (**echter** Deny-Zweig, live) → Debug-Token holen → verifizieren → Anmeldung erwartet 200. Beide Zweige derselben Codestelle, echte Logik, ohne dauerhafte Sonderkonten.

### A5 — Antwortform (R4)

`403 {"error":"email_not_verified"}`, ausgegeben **nach** erfolgreicher Passwortprüfung (`auth.go:186`). Das unterscheidet sie qualitativ von den bestehenden 401-Antworten, die vor jeder Geheimnisprüfung greifen: Sie erreicht nur, wer die Zugangsdaten ohnehin kennt. Gegenüber einem Angreifer ohne Zugangsdaten entsteht kein neues Leck.

**Restrisiko, das ausdrücklich in die Spec gehört:** Wer ein geleaktes Passwort ausprobiert (Credential-Stuffing), erfährt zusätzlich „Konto existiert, Passwort stimmt, Adresse unbestätigt". Das ist ein bewusster Kompromiss zugunsten der vom Ticket geforderten verständlichen Meldung — er gehört als PO-Entscheid festgehalten, nicht stillschweigend eingebaut.

### A6 — Resend-Endpoint (R5)

`POST /api/auth/verify-email/resend`, Nutzlast `{username}` (nicht `email` — wie `ForgotPasswordHandler`, `auth.go:230`, damit die Nutzlast keine Adress-zu-Konto-Zuordnung erlaubt). Struktureller Zwilling dazu: immer `200 {"status":"ok"}`, `ValidUserID`-Vorprüfung mit identischem Antwortpfad, ruft bei vorhandenem Konto `dispatchVerificationMail` (`auth.go:760`) — keine neue Versandlogik. Ratenlimit `NewIPRateLimiter(5, time.Hour)` wie `forgotLimiter` (`router.go:54`). Muss in die Public-Allowlist (`internal/middleware/auth.go:51-59`), sonst greift die Anmeldepflicht vor dem Handler.

### A7 — Bestandskonten

- **Staging:** alle vorhandenen Konten pauschal nachtragen (63, alles Altbestand und tote Wegwerfkonten).
- **Produktion:** nur `default` (`henning`/`steffi` sind bestätigt). Nachtragen statt Verify-Flow, mit Präzedenzfall: `scripts/migrate_1219_email_verified.py` hat für `henning`/`steffi` genau das getan. `default` ist Altbestand von vor der Mandantenfähigkeit, kein Automatismus hängt an seiner Anmeldung (gemessen), und ein ausgesperrtes Altkonto wäre genau die Falle, die das Ticket verhindern will.
- Skript neu als `scripts/backfill_2271_email_verified.py` nach dem Vorbild von `migrate_1219`: Dry-Run als Vorgabe, `--execute`, Pflicht-`--root`, tar.gz-Sicherung, idempotent, Read-Modify-Write. `migrate_1219` ist nicht wiederverwendbar (feste Positivliste statt „alle").

## Scope Assessment

| Datei | Art | ~LoC |
|---|---|---|
| `internal/handler/auth.go` (Gate in `issueSession`, Remint-Variante, Prädikat, Resend-Handler) | MODIFY | ~85 |
| `internal/handler/auth_magic.go` (Feld setzen bei Adressgleichheit) | MODIFY | ~15 |
| `internal/handler/auth_oauth.go` (Feld setzen + Vorprüfung/Redirect) | MODIFY | ~20 |
| `internal/handler/passkey.go` (Auto-Login entfernen) | MODIFY | ~10 |
| `internal/handler/debug_verify_token.go` (staging-only) | CREATE | ~30 |
| `internal/router/router.go`, `internal/middleware/auth.go` | MODIFY | ~15 |
| `frontend/src/routes/login/+page.server.ts`, `+page.svelte` | MODIFY | ~15 |
| `scripts/backfill_2271_email_verified.py` | CREATE | ~120 |
| Go-Tests (~8 bestehende + neue Fälle) | MODIFY/CREATE | ~60 |
| Playwright (5 Zwei-Nutzer-Specs, 3 `.staging.setup.ts`, 1 neue Gate-Spec) | MODIFY/CREATE | ~50 |
| ADR + `session_allowlist.md` | CREATE/MODIFY | zählt nicht |

**Summe ~420 LoC** über beide Scheiben. Risk Level: **HIGH** (Auth, kritischer Pfad).

## Empfohlener Zuschnitt: zwei Scheiben

Die zeitliche Entkopplung aus A4(a) ist nur als getrennte Auslieferung echt — im selben PR bleibt es ein Rennen gegen den Cron.

- **S1 „Vorbereitung" (neues Issue, ändert kein Nutzerverhalten):** Backfill-Skript + ausgeführter Lauf gegen Produktion und Staging, `EmailVerifiedAt` setzen bei Magic-Link und OAuth, Resend-Endpoint, staging-only Debug-Endpoint. Alles davon ist für sich nützlich und harmlos: Es schaltet nichts scharf, es stellt nur her, dass niemand ausgesperrt wird.
- **S2 (#2271 selbst) „Scharfschaltung":** Gate in `issueSession`, Auto-Login bei Passkey-Registrierung entfernt, Frontend-Meldung, ADR + Spec-Fortschreibung, Testanpassungen, neue E2E-Gate-Spec.

Jede Scheibe bleibt unter dem 500er-Override; S1 liegt bei ~250, S2 bei ~170.

## Open Questions

- [ ] **PO-Entscheid (A5):** Die verständliche Meldung „E-Mail nicht bestätigt" verrät einem Angreifer, der bereits ein Passwort besitzt, dass Konto und Passwort stimmen. Bewusst in Kauf nehmen (Empfehlung, weil die Meldung sonst nutzlos wird) oder einheitlich 401 wie bisher?
- [ ] **PO-Entscheid (Zuschnitt):** Zwei Scheiben wie empfohlen — dieser Workflow liefert S1, #2271 folgt als S2?
