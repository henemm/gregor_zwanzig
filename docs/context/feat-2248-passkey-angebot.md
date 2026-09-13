# Context: feat-2248-passkey-angebot

Issue: #2248 (#2199 Scheibe 3) · Track: Standard · Erstellt: 2026-09-12

## Request Summary

Wer sich mit Passwort anmeldet und noch keinen Passkey hinterlegt hat, bekommt **einmalig**
das Angebot, jetzt einen einzurichten. Das Angebot ist abweisbar, und die Abweisung gilt
**geräteübergreifend** — sie wird deshalb serverseitig im Nutzerprofil gemerkt, nicht im
Gerätespeicher.

Voraussetzungen erfüllt: #2246 (S1, Passkeys im Konto anlegbar) und #2247 (S2, Passkey als
erster Anmeldeweg) sind geschlossen und live.

> ⚠️ **Die Zeilenangaben für `internal/handler/auth.go` sind seit dem 2026-09-12, 15:35 überholt.**
> Die parallel laufende #2271-Session hat oberhalb unserer Stellen eingefügt (u.a. eine
> Nachbarfunktion zu `issueSession`). Gemessener Versatz: `profileResponse` 589 → **606**,
> `toProfileResponse` 622 → **654**, `UpdateProfileHandler` 672 → **712**; er wächst weiter,
> solange dort gearbeitet wird. **Stellen per Symbolnamen suchen, nicht per Zeilennummer** — in
> dieser Datei liegen Struct-Felder und Handler-Zuweisungen dicht beieinander, eine Zahl aus
> zweiter Hand trifft verlässlich die falsche Stelle.

## Related Files

| Datei | Relevanz |
|------|-----------|
| `internal/model/user.go:38` | Neues Feld neben `PremiumSmsReplyAt`. `bool` mit `omitempty` genügt — „fehlt" und „false" bedeuten beide „nicht abgewiesen" |
| `internal/handler/auth.go:603` | `toProfileResponse` — Feld in die Profil-Antwort |
| `internal/handler/auth.go:671` | Update-Struct in `UpdateProfileHandler` — Pointer-Feld nach dem Muster `DisplayName` |
| `internal/store/user.go:52,73` | `LoadUser`/`SaveUser` — die Read-Modify-Write-Naht |
| `frontend/src/routes/login/+page.server.ts:55` | `redirect(302, safeRedirectPath(...))` — hier entsteht der Marker |
| `frontend/src/routes/+layout.server.ts:10` | Lädt das Profil bereits zentral, reicht aber nur `displayName` weiter |
| `frontend/src/routes/+layout.svelte:165-201` | Systemhinweis-Bereich außerhalb des Chrome-Blocks — hier lebt das Banner |
| `frontend/src/lib/passkey.ts:17,37` | `isWebAuthnSupported()`, `registerPasskey(label)` |
| `.github/ci_e2e_specs.txt` | E2E-Ratsche (Positivliste, 46 Dateien) |

## Existing Patterns

**Systemhinweis-Banner (`+layout.svelte:165-201`).** Der iOS-Installationshinweis ist die
Vorlage: fest positionierter Block, `role="status"`, eigener `data-testid`, Schließen-Knopf.
Er steht bewusst **außerhalb des Chrome-Blocks** (Issue #2128), hat selbst keine Höhe und
fängt daher keine Klicks ab — erscheint also auch auf `/login`. Daneben liegt der
`updateBereit`-Toast auf derselben Ebene.

Abweichung für #2248: Der iOS-Hinweis merkt die Abweisung in `localStorage`
(`gz-ios-install-hint`, ausdrücklich als „geräteweiter Merker, keine nutzerbezogene Angabe"
kommentiert). Genau das reicht hier **nicht** — die Abweisung ist nutzerbezogen und muss ins
Profil. Das ist ein neues Muster in dieser Datei.

Der `Toast`-Baustein (`$lib/components/mobile/Toast.svelte`) taugt nicht: er kennt eine
Aktion, hier braucht es zwei („Jetzt einrichten" / „Nicht jetzt").

**Read-Modify-Write (`auth.go:661-745`).** `LoadUser` → nur gesetzte Pointer-Felder ändern →
`SaveUser`. Sauber. **Aber:** `SaveUser` marshalt das *gesamte* Struct — ein Schlüssel in
`user.json`, den das Go-Struct nicht kennt, geht beim Speichern verloren. Das Feld gehört also
ins Struct, nicht daneben.

**SSR-Tri-State (#2247, `login/+page.svelte:41,146`).** `webAuthnFaehig = $state<boolean|null>(null)`
in einem Container fester Höhe. Solange `null` oder `true`: Passkey-Knopf; erst ein gemessenes
`false` tauscht auf Hinweistext. Damit steht der Knopf schon im Server-HTML, und der
Browser-Check tauscht nur aus — kein Einfüge-Sprung, den der PO verworfen hat.

**Virtueller Authenticator (`frontend/e2e/passkey-login.spec.ts:273-275`).**
`context.newCDPSession(page)` + `WebAuthn.addVirtualAuthenticator` — echte Zeremonie ohne Gerät.

**Zweiter Browser-Kontext (`frontend/e2e/compare-cross-user-write-block.spec.ts:43-65`).**
`browser.newContext({ storageState: undefined })` — das `undefined` ist Pflicht, sonst erbt der
Kontext den globalen Auth-Zustand. Das ist die Vorlage für den Geräte-Übergreifend-Nachweis.

## Dependencies

- **Upstream:** `model.User` → `store.SaveUser`/`LoadUser` → `PUT /api/auth/profile`;
  `+layout.server.ts` → `GET /api/auth/profile`; `passkey.ts` → `/api/auth/passkey/register/*`
- **Downstream:** Jeder Leser von `user.json` (Go-API und Python-Core). Der Python-Core liest
  ausschließlich über `.get()` einzelner Schlüssel, `DisallowUnknownFields` kommt im Repo
  nirgends vor — ein neues Feld bricht dort nichts (im Issue nachgemessen).

## Existing Specs

- `docs/specs/modules/passkey_konto_verwaltung.md` — #2246 (S1), approved 08.09.
- `docs/specs/modules/passkey_login_anordnung.md` — #2247 (S2), Anordnung auf `/login`
- `docs/specs/modules/passkey_webauthn.md`, `passkey_rp_konfiguration.md` — Grundbausteine

Keine bestehende Spec trägt ein Angebot-Banner mit serverseitigem Merken. Am nächsten liegt
`passkey_login_anordnung.md`, aber das Banner ist ein Querschnitt (Layout + Profil), nicht
Login-Seite. → **Eigene Spec-Datei**, Entscheidung in der Analyse begründet.

## Risks & Considerations

1. **🔴 SSR-Negativzweig ist ein Vakuum.** Die Anzeigebedingung hängt an
   `isWebAuthnSupported()` (nur im Browser). Eine serverseitige Zusicherung „Banner fehlt, wenn
   Passkey vorhanden" stellt sich im SSR von selbst ein und bewacht nichts. Negativ-Aussagen
   gehören deshalb in den Browser (E2E), nicht in den SSR-Test.
2. **🔴 Der eigentliche Beweis hängt nicht in der CI-Ampel.** `.github/ci_e2e_specs.txt` ist eine
   Positivliste; `passkey-login.spec.ts` steht nicht einmal drin. Der Zwei-Kontext-Beweis läuft
   sonst nur in `/e2e-verify`. Aufnahme braucht 3×-grün-Beleg — in der Spec zu entscheiden,
   nicht in Phase 7.
3. **Nutzlast-Disziplin beim „Nicht jetzt".** `auth.go:706-715` setzt `email_verified_at` zurück,
   wenn ein *abweichender* `email`/`mail_to`-Wert mitkommt. Schickt das Banner nur sein eigenes
   Feld, bleibt `update.Email == nil` und der Zweig wird nicht betreten. Nach #2271 (Login-Pflicht
   auf bestätigte Adresse) wäre ein zu großzügiger Nutzlast-Aufbau eine Aussperr-Falle.
4. **Stale `has_passkey` nach Erfolg.** Richtet der Nutzer den Passkey über das Banner ein, ist
   der Layout-Ladewert veraltet. Das Banner muss nach Erfolg von sich aus verschwinden.
5. **Marker in der Ziel-Adresse.** `safeRedirectPath` liefert einen relativen Pfad, der bereits
   eine Query tragen kann — der Marker muss korrekt angehängt werden. Offene Frage für die
   Analyse: Bleibt der Marker in der Adresse stehen (Neuladen zeigt das Banner erneut) oder wird
   er nach der Anzeige entfernt?
6. **Kollision mit #2271 geklärt.** Jene Scheibe fasst `issueSession` (:130), zwei neue Funktionen
   und `ChangePasswordHandler` (:931) an — **nicht** `toProfileResponse`, `GetProfileHandler`,
   `UpdateProfileHandler` oder `internal/model/user.go`. Disjunkt, von der #2271-Session bestätigt.
7. **E2E-Konten nach #2271.** Sobald die Login-Pflicht steht, brauchen zur Laufzeit angelegte
   Testkonten eine Bestätigung. Auf Staging gibt es dafür
   `POST /api/auth/verify-email/staging-token` (#2304, nur bei `GZ_ENV == "staging"`,
   anmeldepflichtig).

## Analyse-Entscheidungen (Phase 2)

**A. Marker-Transport: Query-Parameter, wie im Issue skizziert.** Ein kurzlebiges Cookie wäre
optisch sauberer, aber `+layout.server.ts` läuft bei *jeder* Navigation und bei Invalidierung —
ein dort gelöschtes Cookie wird von dem Ladelauf verbraucht, der zufällig zuerst feuert. Das
„einmalig" hinge dann an der Reihenfolge von Ladeläufen, was im E2E hält und beim PO einmal
fehlschlägt. Der Query-Parameter hat keine Reihenfolgen-Semantik. Angehängt wird er **nach**
`safeRedirectPath`, das bereits eine Query tragen kann — beide Fälle (mit/ohne `?`) sind ein
Zweig, der einen eigenen Test in der Ampel bekommt.

**B. Anzeige-Entscheidung als reine Funktion.** `+layout.svelte` ruft eine parameterlose
Entscheidungsfunktion `passkeyAngebotFaellig({ marker, hasPasskey, dismissed, webauthnFaehig })`
in einem eigenen `.ts`-Modul. Die Funktion liest **nichts** selbst — alle vier Eingaben kommen
von außen, `dismissed` ausdrücklich aus `data` (also vom Server). Damit ist die
Entscheidungstabelle unter `node --test` prüfbar und liegt in der CI-Ampel.

**C. Sichtbarkeit clientseitig geschaltet, nach dem Muster des iOS-Hinweises.** Gleiche Datei,
gleiche Elementklasse (fest positionierte Einblendung ohne Layout-Beteiligung) — anders als bei
#2247, wo der Einfüge-Sprung im Formularfluss das Problem war. Hier gibt es keinen Sprung.

**D. Was welche Verfälschung fängt (offen ausgesprochen).** Baut jemand das Merken auf
`localStorage` statt auf den `PUT` um, geht **nur der E2E-Nachweis** rot — und der läuft erst in
`/e2e-verify`, nicht in der Ampel. Die Entscheidungstabelle fängt das nicht, weil sie `dismissed`
als Parameter bekommt. Das ist die bewusst in Kauf genommene Lücke; sie ist der Preis dafür, die
Entscheidung überhaupt ampeltauglich zu machen.

**E. E2E bleibt außerhalb der Ratsche.** `passkey-login.spec.ts` aus S2 steht nicht in
`.github/ci_e2e_specs.txt`, und S2 ist so ausgeliefert worden. Eine neue Passkey-E2E in die
Ampel zu heben, hieße eine strengere Latte anzulegen als bei beiden Geschwister-Scheiben — und
ein CDP-Virtual-Authenticator-Test in der Ampel ist eine Flake-Haftung auf `main`. In der Ampel
bewacht bleiben: der Go-Merge-Test und die Entscheidungstabelle.

**F. Eigene Nutzlast für das „Nicht jetzt".** `api.put` ist ein dünner Helfer, jede Aufrufstelle
baut ihre Nutzlast selbst (`account/+page.svelte:290` schickt `display_name`/`mail_to`/`sms_to`).
Es gibt keinen geteilten Voll-Profil-Serialisierer, den man erben könnte. Das Banner schickt
ausschließlich sein eigenes Feld.
