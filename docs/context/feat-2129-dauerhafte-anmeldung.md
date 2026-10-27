# Context: feat-2129-dauerhafte-anmeldung

Issue: [#2129](https://github.com/henemm/gregor_zwanzig/issues/2129) · Elternscheibe: #2127 (S2 von 5)
Track: Full Process · Erstellt: 2026-09-05

## Request Summary

Die Anmeldung soll unbefristet gelten (bis zum aktiven Abmelden) statt nach 24 Stunden hart
abzulaufen. Bedingung des PO: ein Widerruf, der einen Server-Neustart überlebt — inklusive
„auf allen Geräten abmelden". Ohne diesen Widerruf wäre ein einmal abgegriffenes Cookie
unbegrenzt gültig.

## Ist-Stand (recherchiert 2026-09-05)

### Cookie-Format

`gz_session` = `{userId}.{unixTimestamp}.{hmacSigHex}`, HMAC-SHA256 über `{userId}:{ts}`.

| Rolle | Ort |
|---|---|
| Bau | `internal/middleware/auth.go:77-83` (`SignSession`) |
| Prüfung Go | `internal/middleware/auth.go:91-120` (`validateSession`) — `SplitN(".", 3)`, Ablauf Z107, `hmac.Equal` Z111-116 |
| Prüfung Frontend (eigenständig!) | `frontend/src/lib/auth.ts:9-29` (`verifySession`) — `parts.pop()`-Strategie, Ablauf Z23, Vergleich Z26 **ohne** `timingSafeEqual` |

### Ausstellungsstellen (6× Go, 2× Frontend)

Alle identisch: `gz_session`, Path `/`, HttpOnly, SameSite Lax, **MaxAge 86400**, Secure abhängig
von `X-Forwarded-Proto`/`r.TLS`.

| Datei:Zeile | Login-Weg |
|---|---|
| `internal/handler/auth.go:154-164` | Passwort |
| `internal/handler/auth_magic.go:187-197` | Magic-Link |
| `internal/handler/auth_oauth.go:182-192` | Google OAuth |
| `internal/handler/passkey.go:256-266` | Passkey-Login |
| `internal/handler/passkey.go:365-375` | Passkey discoverable |
| `internal/handler/passkey.go:575-585` | Passkey-Registrierung |
| `frontend/src/routes/login/+page.server.ts:43-49` | setzt das vom Go-Dienst erhaltene Cookie **erneut** |
| `frontend/src/routes/magic-link/verify/+page.server.ts:42-48` | dito |

### Widerruf heute

- `var sessionBlacklist sync.Map` — `internal/middleware/auth.go:16`, Modul-global, reiner
  Prozessspeicher. Key = **kompletter Token-String**.
- `LogoutHandler` — `internal/handler/auth.go:431-449`: blacklistet genau diesen einen Token,
  löscht das Cookie (`MaxAge -1`).
- `DeleteAccountHandler` — `auth.go:189-196`: dasselbe.
- **Kein Muster für „alle Sessions eines Nutzers"** — die Blacklist kann nur Token sperren, die man
  kennt.

### Prüfung und Kontext

`AuthMiddleware` — `internal/middleware/auth.go:31-68`: Whitelist öffentlicher Pfade (Z34-47),
Cookie lesen (Z52), `validateSession` (Z58), `IsBlacklisted` (Z59), bei Erfolg
`context.WithValue(userIDContextKey, userId)` (Z64). Abruf via `UserIDFromContext` (Z70-73).
Frontend-Gegenstück: `frontend/src/hooks.server.ts:1-31`, `publicPaths` Z6, bei ungültig
`redirect(302, '/login')` Z21 (ohne `?redirect=`), bei gültig `event.locals.userId` Z24.

### Persistenz-Muster

- `LoadUser` / `SaveUser` — `internal/store/user.go:48-79`. `SaveUser` schreibt das **ganze**
  `model.User`-Struct; das Read-Modify-Write-Merge entsteht ausschließlich beim Aufrufer.
- Atomar via `writeFileAtomic` — `internal/store/write.go:35-59` (Temp + Rename).
- **Kein Mutex** um Load→Modify→Save auf `user.json` (anders als `internal/store/briefing_lock.go:17`).
- `model.User` — `internal/model/user.go:10-39`: kein Feld für Widerrufs-/Versionsstand vorhanden.
  Nächstliegendes Bestandsmuster: `*time.Time` mit `omitempty` (wie `EmailVerifiedAt`, `RequestedAt`).

## Related Files

| Datei | Relevanz |
|---|---|
| `internal/middleware/auth.go` | Bau, Prüfung, Blacklist — **das Herzstück**, alles Format-Bruchrisiko konzentriert sich hier |
| `internal/handler/auth.go` | Login, Logout, Passwortwechsel, Account-Löschung |
| `internal/handler/auth_magic.go` / `auth_oauth.go` / `passkey.go` | vier weitere Ausstellungsstellen |
| `internal/handler/auth.go:744-793` | `ChangePasswordHandler` — Ort für „Passwortwechsel meldet überall ab" |
| `internal/handler/auth.go:308-375` | `ResetPasswordHandler` — dito |
| `internal/store/user.go`, `internal/model/user.go` | Ablageort des Widerrufs-Stands (**löst `data_schema_backup.py` aus**) |
| `internal/router/router.go:49` | Routen-Registrierung, Ort für einen neuen Endpunkt |
| `frontend/src/lib/auth.ts`, `frontend/src/hooks.server.ts` | zweite, eigenständige Prüfung |
| `frontend/src/routes/login/+page.server.ts`, `.../magic-link/verify/+page.server.ts` | Frontend-Cookie-Ausstellung |
| `frontend/src/lib/api.ts:61-69` | 401 → harter Sprung auf `/login?expired=1&redirect=…` |
| `frontend/src/routes/logout/+page.server.ts:6-17` | Formular-POST-Logout |
| `frontend/src/lib/components/ui/sidebar/Sidebar.svelte:194-199, 259-264` | „Abmelden"-Knopf (2×: Desktop + Mobile) |
| `frontend/src/routes/account/+page.svelte:761-779, 800-816` | „Gefahrenzone" + Dialog-Bestätigung — **Vorbild** für „Auf allen Geräten abmelden" |
| `docs/adr/0030-session-auth-hmac-cookie.md` | wird durch diese Scheibe abgelöst |
| `docs/reference/api_contract.md` Z2250, 2295, 2585, 2659, 2814 | Vertragstext zum Cookie |

## Existing Patterns

- **Destruktive Aktion im UI:** Card „Gefahrenzone" (rot) → Klick setzt `show…Dialog = true` →
  `Dialog.Root` mit `Btn variant="outline"` (Abbrechen) + `Btn variant="destructive"` → `api.del/post`
  → bei Fehler **inline** `{#if errorMsg}`-Box (kein Toast-System im Projekt). Vorbild:
  „Account löschen", `account/+page.svelte:282-295`.
- **Nutzerdaten-Änderung:** `LoadUser` → Feld setzen → `SaveUser(*user)` (Read-Modify-Write beim
  Aufrufer, ADR-0031).
- **Optionales Zeitfeld:** `*time.Time` mit `json:"…,omitempty"` — Nil bedeutet „nie geschehen",
  das trägt die Abwärtskompatibilität für Bestandsnutzer ohne Migrationsskript.
- **ADR-Ablösung:** altes ADR bleibt stehen, Status → „Abgelöst durch ADR-XXXX"; neues ADR nach
  `docs/adr/_template.md`; Index-Zeile in `docs/adr/README.md`. **Nächste freie Nummer: 0060.**
  `tests/test_adr_index_drift.py` erzwingt beides sofort: jede ADR-Datei muss im Index verlinkt
  sein **und** die Status-Klasse muss zwischen Datei und Index übereinstimmen — der Statuswechsel
  von ADR-0030 auf „abgelöst" muss also im selben Zug in den Index, sonst wird die Ampel rot.

## Dependencies

- **Upstream:** `GZ_SESSION_SECRET` (Go + Frontend), `store.Store`, `model.User`, `bcrypt`.
- **Downstream:** jeder authentifizierte API-Aufruf (`UserIDFromContext`), jede geschützte
  SvelteKit-Route (`event.locals.userId`), 17 Playwright-Setups, die `gz_session` aus einem echten
  Login in `frontend/e2e/playwright/.auth/*.json` ablegen.

## Existing Specs

| Spec | Zustand |
|---|---|
| `docs/specs/modules/logout_session_blacklist.md` | beschreibt die heutige In-Memory-Blacklist — **muss aktualisiert werden** |
| `docs/specs/modules/user_auth_endpoints.md` | Endpunkt-Liste, neuer Widerrufs-Endpunkt gehört hinein |
| `docs/specs/modules/sveltekit_login_refactor.md` | Frontend-Anmeldeweg |
| `docs/specs/modules/passkey_webauthn.md` (created 2026-05-30) | bei Änderung **AC-Pflicht** (created ≥ 2026-05-11) |
| `docs/specs/modules/google_oauth_login.md` | Cookie-Ausstellung im OAuth-Weg |

## Risks & Considerations

### Befunde, die vom Ticket abweichen — vor der Spec zu klären

1. **Punkt 4 des Tickets stimmt nicht.** „Passwortwechsel meldet überall ab — bislang der einzige
   Notweg": `ChangePasswordHandler` (`auth.go:744-793`) ändert **nur** den Passwort-Hash, ohne jede
   Session-Invalidierung; ebenso `ResetPasswordHandler` (`auth.go:308-375`). Es gibt heute also
   **gar keinen** wirksamen Notweg. Sicherheitlich ist der Reset-Fall der schwerere: wer sein
   Passwort zurücksetzt, weil es kompromittiert war, wirft den Angreifer heute nicht hinaus.
2. **Vertragstext widerspricht sich selbst.** `api_contract.md:2250` behauptet „7-day expiry",
   Z2585/2659/2814 sagen 24 h — der Code sagt 24 h. Bestehende Doku-Drift, im Zuge der
   Vertragsänderung mitzuräumen.
3. **Frontend-Fallback-Secret.** `hooks.server.ts:16` fällt auf `'dev-secret-change-me'` zurück,
   wenn `GZ_SESSION_SECRET` fehlt. Bei unbefristeten Anmeldungen wiegt ein still greifender
   Fallback schwerer als heute. → Nebenbefund-Triage.
4. **Kein `timingSafeEqual` im Frontend** (`auth.ts:26`) — Go macht es korrekt (`hmac.Equal`).
   → Nebenbefund-Triage.

### Technische Risiken

5. **Zwei Prüfstellen müssen synchron bleiben.** Lässt die eine durch, was die andere abweist,
   entsteht ein Zustand, in dem die Seite lädt, aber jeder Datenabruf 401 gibt (oder umgekehrt eine
   Umleitungsschleife). Beide Seiten gehören in **einen** Testlauf.
6. **Race auf `user.json`.** Load→Modify→Save ist ungelockt. „Auf allen Geräten abmelden" schreibt
   in dieselbe Datei wie jede andere Nutzeränderung; ein gleichzeitiger Schreiber kann den Widerruf
   überschreiben — dann bliebe ein verlorenes Handy angemeldet. Der Widerruf ist genau die
   Operation, die diesen Verlust nicht verträgt.
7. **Ein Lesezugriff pro Anfrage.** Der Widerrufs-Stand muss bei **jeder** authentifizierten
   Anfrage geprüft werden. Naiv ist das ein `user.json`-Lesevorgang pro Request. Frage für die
   Analyse: Zwischenspeicher — und wenn ja, wie wird er beim Widerruf sofort ungültig (ein
   Zwischenspeicher, der den Widerruf verzögert, hebt die Zusicherung auf)?
8. **Bestandstests, die MaxAge 86400 festschreiben** — `auth_test.go:479-480`,
   `auth_magic_test.go:259-260`, `passkey_test.go:419-420`, `passkey_public_test.go:239-240`, und
   vor allem `middleware/auth_test.go:70-87` (`TestExpiredCookie_Returns401`, Cookie 25 h alt →
   erwartet 401). Diese Erwartungen werden durch die Änderung **fachlich falsch** und sind bewusst
   umzuschreiben, nicht wegzulöschen.
9. **Frontend-Cookie-Attribute sind test-unbewacht.** Kein Test prüft `maxAge`/`httpOnly`/
   `sameSite` in `login/+page.server.ts` — eine Änderung dort fällt heute niemandem auf.
10. **Übergang ohne Ausloggen.** Bestandscookies im Altformat müssen weiterlaufen und still auf
    das neue Format gehoben werden. Ein Nutzer mit einem 20 h alten Cookie darf durch das Deploy
    nicht hinausfliegen.
11. **Mandantentrennung.** Der Widerrufs-Stand ist pro Nutzer; die Nutzerkennung kommt weiterhin
    ausschließlich aus dem geprüften Merkmal, nie aus einem Standardwert (ADR-0003). Nachweis
    zwingend mit **zwei verschiedenen Nutzern**.
12. **Schema-Änderung an `internal/model/user.go`** löst den Pre-Snapshot-Hook
    `data_schema_backup.py` aus und verlangt Migrations-/Roundtrip-Nachweis (ADR-0031).

### Erfreulich unkritisch

- Keine Service-Worker-/Offline-Schicht vorhanden (nur `static/site.webmanifest`) — kein
  Client-Cache, der eine unbefristete Session umgehen könnte. Das kommt erst mit S1 (#2128).
- Kein Prüfwerkzeug und kein E2E-Setup baut ein `gz_session` synthetisch nach; alle lesen es aus
  einem echten Login. Das Bruchrisiko der Formatänderung liegt praktisch vollständig in
  `internal/middleware/auth.go` und `frontend/src/lib/auth.ts`.

## Analysis

### Type

Feature (mit eingebetteter Sicherheitsbehebung).

### Entwurfsentscheidung: Allowlist gültiger Sitzungen

Zwei Entwürfe standen gegeneinander:

| | **A — Generationszähler** | **B — Allowlist gültiger Sitzungen** |
|---|---|---|
| Prinzip | Zahl im Nutzerdatensatz, Cookie trägt sie mit; passt sie nicht, ist es ungültig | Jede Anmeldung erhält eine Zufalls-Kennung im Cookie; gültig ist, was in der Liste steht |
| „alle Geräte abmelden" | Zähler erhöhen | Liste leeren |
| **„nur dieses Gerät abmelden"** | **nicht möglich** — bräuchte zusätzlich eine dauerhafte Sperrliste, die bei unbefristeten Cookies nie schrumpft | einen Eintrag entfernen |
| Wachstum | keines | ~100 Byte je Gerät, schrumpft beim Abmelden |

**Gewählt: B.** A scheitert an einer der beiden geforderten Abmelde-Arten und bräuchte, um sie zu
erfüllen, ohnehin genau die Struktur von B — zwei Mechanismen nebeneinander wären doppelter Code,
doppelte Migration, doppelte Tests ohne Gegenwert.

### Ablage und Nebenläufigkeit

- **Eigene Datei `data/users/<user_id>/sessions.json`**, nicht in `user.json`. Zwei Gründe: (1) die
  15 bestehenden `SaveUser`-Aufrufer schreiben das *ganze* Nutzerobjekt zurück — ein gleichzeitiger
  Profil-Schreiber könnte einen Widerruf schlicht überschreiben, und ausgerechnet der Widerruf
  verträgt diesen Verlust nicht; (2) es bleibt aus dem `model.User`-Schema heraus, löst also nicht
  bei jeder Anmeldung den Schema-Backup-Hook aus.
- **Pro-Nutzer-Sperre** nach dem Vorbild `internal/store/briefing_lock.go:17-58` (Mutex-Pool auf
  Paketebene mit Referenzzählung). Ein Prozess je Umgebung, daher genügt eine Prozess-Sperre.

### Kein Zwischenspeicher — bewusst gegen die Agenten-Empfehlung

Der Strategie-Agent empfahl einen In-Memory-Zwischenspeicher mit synchroner Ungültigmachung. Ich
entscheide dagegen und lese bei jeder Anfrage direkt:

- Gemessen: `AuthMiddleware` liest heute **keine** Datei; real existierende `user.json` sind
  193–433 Byte; der Bestand umfasst eine Handvoll Nutzer. Ein 400-Byte-Lesevorgang aus dem
  Betriebssystem-Cache ist gegenüber allem anderen in der Anfrage nicht messbar.
- Ein Zwischenspeicher ist ein zweiter Zustandsbehälter, der genau die Zusicherung tragen müsste,
  auf der die unbefristete Anmeldung beruht. Der billigste Weg, ihn nie falsch werden zu lassen,
  ist, ihn nicht zu haben.
- Nachrüstbar, sobald es je eine Lastmessung gibt, die ihn rechtfertigt. Heute gibt es überhaupt
  keine Request-Metriken (nachgesehen: keine).

### Cookie-Format

| | Format | Signatur über |
|---|---|---|
| alt (3 Teile) | `{userId}.{ts}.{sig}` | `{userId}:{ts}` |
| **neu (4 Teile)** | `{userId}.{sessionId}.{ts}.{sig}` | `{userId}:{sessionId}:{ts}` |

`sessionId` = 16 Zufallsbytes hex. `ts` bleibt erhalten, obwohl es für die Gültigkeit nicht mehr
gebraucht wird — der Legacy-Zweig braucht es weiter.

**Korrektur 2026-09-06 (bei der Umsetzung gefunden):** Die ursprüngliche Annahme, die *Teilezahl*
unterscheide alt und neu eindeutig, ist falsch. Eine Nutzerkennung mit Punkt erzeugt auch im alten
Format vier Segmente — `alice.smith.{ts}.{sig}` ist von `{userId}.{sessionId}.{ts}.{sig}` nicht an
der Segmentzahl zu trennen. Unterschieden wird stattdessen über die **Signatur**: zuerst wird das
neue Format geprüft (HMAC über `{userId}:{sessionId}:{ts}`), bei Fehlschlag das alte
(`{userId}:{ts}`). Beides sind HMAC-Vergleiche, die Reihenfolge kostet nichts. Ohne diese
Korrektur wäre entweder AC-14 oder der Legacy-Zweig gebrochen.

**Beide Seiten parsen von rechts** (die letzten drei Segmente sind `sessionId`/`ts`/`sig`, alles
davor ist die userId). Das behebt zugleich Befund 13 (siehe unten).

### Befund 13 — Parsing-Divergenz zwischen den beiden Prüfstellen

Nachgerechnet für `alice.smith`: Go (`SplitN(".", 3)`, `auth.go:92`) zerlegt
`alice.smith.1757000000.abcdef` zu `["alice", "smith", "1757000000.abcdef"]`, scheitert dann beim
Timestamp-Parsen und weist ab. Das Frontend (`auth.ts:14-18`, `pop()`) rekonstruiert `alice.smith`
korrekt — es wurde im Zuge von #425 AC-7 vorsorglich gefixt, **Go wurde nie nachgezogen**.

**Heute nicht ausnutzbar:** alle drei Kennungs-Erzeuger sind punktfrei
(`^[a-zA-Z0-9_-]+$` bei Registrierung/Passkey, `m-{8hex}`, `g-{8hex}`), und kein einziger
Nutzerordner im echten Bestand enthält einen Punkt. Es ist also kein Bug, sondern eine strukturelle
Divergenz zwischen zwei Stellen, die dasselbe prüfen sollen — in genau der Datei, die wir ohnehin
anfassen. Wird mitbehoben (~5 Zeilen), nicht als Nebenbefund vertagt.

### Migrationspfad

- Alt-Cookies (3 Teile) bleiben gültig — **behalten dabei ihre 24-Stunden-Grenze**. Neue Cookies
  (4 Teile) haben keine. Damit verschwindet der Altbestand binnen 24 Stunden nach dem Deploy von
  selbst, und der Legacy-Zweig kann später ersatzlos entfallen.
- Bei einem gültigen Alt-Cookie legt die Middleware synchron eine Sitzungs-Kennung an, trägt sie in
  die Allowlist ein und setzt das neue Cookie über den `ResponseWriter` nach. Niemand fliegt durch
  das Deploy hinaus.
- Nutzer ohne `sessions.json`: Datei fehlt = leere Liste, wird beim ersten Eintrag angelegt. Kein
  Migrationsskript nötig.
- Bekannte Grenze: Bei server-zu-server-Aufrufen aus SvelteKit-Ladefunktionen erreicht ein
  `Set-Cookie` des Go-Dienstes den Browser nicht. Ein Nutzer, der 24 Stunden lang ausschließlich
  Seiten betrachtet und nie eine Aktion auslöst, behält bis dahin sein Alt-Cookie — das ist exakt
  das heutige Verhalten, also keine Verschlechterung.

### Die zwei Prüfstellen

Der Frontend-Server hat keinen Zugriff auf den Nutzer-Datenbestand und prüft weiterhin **nur**
Signatur und Format, nicht die Allowlist. Das ist kein neues Zugeständnis: die heutige Sperrliste
ist dem Frontend genauso unbekannt. Nachvollzogen, was ein Nutzer bei einer widerrufenen Sitzung
sieht: die Ladefunktion bekommt 401, fängt es ab und liefert leere Daten — die Seite lädt, wirkt
leer; der nächste Klick löst den harten Sprung auf `/login?expired=1` aus. **Keine
Umleitungsschleife.** Bewusst wird **keine** Rückfrage vom Frontend-Server zum Go-Dienst
eingeführt: das kostete Wartezeit bei jedem Seitenaufbau und bräche die Trennung, ohne einen
echten Schaden abzuwenden.

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `internal/store/sessions.go` | CREATE | Allowlist lesen/hinzufügen/entfernen/leeren, atomar |
| `internal/store/sessions_lock.go` | CREATE | Pro-Nutzer-Sperre nach `briefing_lock.go`-Vorbild |
| `internal/middleware/auth.go` | MODIFY | Format 4-teilig, rechts-verankertes Parsen, Allowlist-Prüfung, Legacy-Zweig + Nachsetzen, Sperrliste entfällt |
| `internal/handler/auth.go` | MODIFY | Login mintet Kennung; Logout entfernt Eintrag; neuer Endpunkt „alle abmelden"; Passwortwechsel **und** -Zurücksetzen leeren die Liste; Account-Löschung |
| `internal/handler/auth_magic.go` | MODIFY | Ausstellungsstelle |
| `internal/handler/auth_oauth.go` | MODIFY | Ausstellungsstelle |
| `internal/handler/passkey.go` | MODIFY | drei Ausstellungsstellen |
| `internal/router/router.go` | MODIFY | Route für „alle abmelden" |
| `frontend/src/lib/auth.ts` | MODIFY | Format spiegeln, Ablaufprüfung nur noch für Altformat |
| `frontend/src/routes/login/+page.server.ts` | MODIFY | Cookie-Lebensdauer |
| `frontend/src/routes/magic-link/verify/+page.server.ts` | MODIFY | Cookie-Lebensdauer |
| `frontend/src/routes/account/+page.svelte` | MODIFY | „Auf allen Geräten abmelden" nach Vorbild „Gefahrenzone" + Bestätigungsdialog |
| `docs/adr/0060-*.md` | CREATE | löst ADR-0030 ab |
| `docs/adr/0030-session-auth-hmac-cookie.md` | MODIFY | Status → abgelöst |
| `docs/adr/README.md` | MODIFY | Index-Zeile + Statuswechsel (sonst Ampel rot) |
| `docs/reference/api_contract.md` | MODIFY | Format + vier Set-Cookie-Stellen, inkl. der falschen „7-day"-Zeile |
| `docs/specs/modules/logout_session_blacklist.md` | MODIFY | beschreibt heute die abgelöste Mechanik |
| Tests Go + Frontend | MODIFY/CREATE | fünf MaxAge-/Ablauf-Erwartungen werden fachlich falsch; neu: Neustart-Nachweis, zwei Nutzer, Wettlauf |

### Scope Assessment

- Dateien: ~18 (davon 2 neu im Code, 1 neues ADR)
- Geschätzte LoC: **+450 bis +600** — das 250er-Limit wird gerissen, ein Override ist nötig und
  wird gesetzt, sobald `workflow.py status` es anzeigt.
- Risiko: **HIGH** (Anmeldung, Mandantentrennung, API-Vertrag)

### Warum das trotz Größe *eine* Scheibe bleibt

Der Strategie-Agent schlug vor, Backend und Frontend zu trennen. Das geht nicht: seine eigene
Reihenfolge verlangt, dass die Frontend-Spiegelung **vor oder gleichzeitig mit** der
Backend-Formatänderung live ist, sonst weist der Frontend-Server jede frische Anmeldung ab und
sperrt alle Nutzer aus. Getrennte Scheiben heißen getrennte Deploys — der Schnitt widerspricht sich
selbst.

Auch der naheliegendere Schnitt „erst der Widerruf, später die Entfristung" wird nicht gezogen: Der
PO hat die unbefristete Anmeldung ausdrücklich an die Bedingung einer wirksamen Fern-Abmeldung
geknüpft. Beide Hälften gehören in **einen** Auslieferungsstand — die Reihenfolge wird stattdessen
*innerhalb* der Scheibe erzwungen (siehe unten).

### Reihenfolge — das Netz vor dem Sprung

1. Allowlist-Ablage + Sperre, additiv und unbenutzt, mit eigenem Roundtrip-Test.
2. Alle acht Ausstellungsstellen minten die Sitzungs-Kennung und tragen sie ein. **Die
   24-Stunden-Grenze bleibt in diesem Schritt scharf** — nichts wird dadurch unsicherer.
3. Frontend-Spiegelung des Formats (muss mit Schritt 2 zusammen ausgeliefert werden).
4. Abmelden (ein Gerät) auf Allowlist umstellen — **hier wird der Neustart-Nachweis geführt**.
5. „Auf allen Geräten abmelden" samt Bedienelement; Passwortwechsel und -Zurücksetzen verdrahten.
6. **Zuletzt** die Ablaufprüfung für das neue Format entfernen und die Cookie-Lebensdauer
   hochsetzen. Dieser Schritt nimmt das Sicherheitsnetz weg und darf erst laufen, wenn 1–5 grün
   nachgewiesen sind.

### Über den Ticket-Wortlaut hinaus

- **Passwort-Zurücksetzen** wird mit verdrahtet, obwohl das Ticket nur den Passwortwechsel nennt.
  Sicherheitlich ist es der wichtigere Fall: Wer zurücksetzt, *weil* das Passwort abgegriffen
  wurde, wirft den Angreifer sonst nicht hinaus.
- **Nicht gebaut:** eine Geräteliste („angemeldet auf 3 Geräten seit …"). Das Ticket fordert sie
  nicht. Die Allowlist macht sie später ohne Umbau möglich.

### Nebenbefunde → Triage (nicht in dieser Scheibe)

- Frontend-Server fällt ohne gesetztes Geheimnis still auf `'dev-secret-change-me'` zurück
  (`hooks.server.ts:16`).
- Frontend vergleicht die Signatur ohne laufzeitkonstanten Vergleich (`auth.ts:26`); Go macht es
  korrekt.
- `SaveUser` ist generell ungelockt (15 Aufrufer) — diese Scheibe umgeht das Problem, statt es
  allgemein zu lösen.

### Open Questions

Keine. Alle offenen Punkte waren technischer Natur und sind oben entschieden.

## Nachweis-Anforderung (aus dem Ticket)

Zwei verschiedene Nutzer. Anmeldung überlebt einen echten Dienst-Neustart und ist jenseits von
24 Stunden noch gültig (mit vorgestellter Uhr geprüft). „Auf allen Geräten abmelden" macht ein
zuvor gültiges Merkmal ungültig **und es bleibt auch nach einem Neustart ungültig** — das ist die
Gegenprobe, die heute fehlschlagen würde.
