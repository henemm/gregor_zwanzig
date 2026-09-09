# Context: feat-2199-passkey-ui

Issue: #2199 — „Passkey-UI: erster Anmeldeweg auf dem Handy + Konto-Verwaltung"
Track: Full Process · Vorgänger: #2130 (geschlossen) · Historie: #878 (geschlossen), #450/#466/#467/#468

## Request Summary

Die Passkey-Oberfläche wieder sichtbar machen: auf dem Handy ist der Passkey der erste
angebotene Anmeldeweg, nach einem Passwort-Login gibt es einmalig ein abweisbares Angebot,
einen einzurichten, und in der Konto-Ansicht sind Passkeys sichtbar und einzeln entfernbar.
Das Backend dafür ist seit #2130 fertig; es fehlt fast ausschließlich Frontend.

## Ausgangslage: was schon da ist

**Backend — nahezu vollständig.** Alle Zeremonie-Endpunkte existieren und sind in
`docs/reference/api_contract.md` (Z. 141–154) dokumentiert:
Register (begin/finish), Login (begin/finish), Discoverable (begin/finish),
Register-Public (begin/finish), `DELETE /api/auth/passkey/credentials/{id}`.

`GET /api/auth/profile` liefert die Passkey-Liste bereits vollständig
(`internal/handler/auth.go:602` `toProfileResponse`):

| Feld | Herkunft |
|---|---|
| `id` | Credential-ID, `base64.RawURLEncoding` — direkt für den Delete-Pfad verwendbar |
| `label` | bei Registrierung vergeben |
| `authenticator_name` | Klarname aus der AAGUID (`internal/handler/aaguid.go`) |
| `created_at`, `last_used_at` | RFC3339; `last_used_at` fehlt, solange nie benutzt |
| `has_passkey` | Boolean auf Profil-Ebene (`auth.go:639`) |

`last_used_at` wird beim Passkey-Login automatisch fortgeschrieben. Die RP-ID leitet sich
seit #2130 aus `PublicHost` ab, nicht mehr aus `localhost`.

**Frontend — `frontend/src/lib/passkey.ts` (155 Zeilen) ist vollständig, hat aber null
Verwendungen.** Exportiert: `isWebAuthnSupported()`, `registerPasskey(label)`,
`loginWithPasskey(username)`, `loginWithDiscoverablePasskey(signal?)`.
Abhängigkeit `@github/webauthn-json@^2.1.1` ist installiert.

**Der 2026-06-24 in `c09172f5` entfernte UI-Code** (−90 Login, −136 Konto) liegt als Diff
im Scratchpad dieser Session (`c09172f5-passkey-ui-removal.diff`). Wiederverwendbar sind
Conditional-UI-Anbindung, `autocomplete="username webauthn"`, die deutschen Fehlertexte
(`Anmeldung abgebrochen.` / `Zeitüberschreitung. Bitte erneut versuchen.` /
`Kein passender Passkey gefunden.`) und `data-testid="login-passkey-btn"`.

## Related Files

| Datei | Relevanz |
|---|---|
| `frontend/src/routes/login/+page.svelte` (120 Z.) | ÄNDERN — Passkey-Weg + Reihenfolge nach Viewport |
| `frontend/src/routes/account/+page.svelte` (895 Z.) | ÄNDERN — Passkey-Karte zwischen „Kanäle" (endet Z. 475) und „Passwort ändern" (ab Z. 477) |
| `frontend/src/lib/passkey.ts` | ERGÄNZEN — es fehlen Helfer zum Auflisten/Löschen |
| `internal/model/user.go` (102 Z.) | ÄNDERN — neues Feld für „Angebot abgewiesen" (Schema!) |
| `internal/handler/auth.go:660` `UpdateProfileHandler` | ÄNDERN — Andockpunkt für das neue Feld |
| `internal/handler/auth.go:602` `toProfileResponse` | ÄNDERN — Feld mit ausliefern |
| `frontend/e2e/passkey-regression.spec.ts` (304 Z.) | VORBILD — virtueller Authentifikator per CDP |
| `.github/ci_e2e_specs.txt` | ggf. ERGÄNZEN — Positivliste, siehe Risiken |

## Existing Patterns

- **Mobile-Weiche, 899px:** viermal identisch verwendet
  (`trip-detail/TripTabs.svelte:136–142`, `trip-new/TripNewEditor.svelte`,
  `compare/CompareTabs.svelte`, `compare-new/CompareNewEditor.svelte`).
  ⚠️ Das Muster benutzt **`onMount` mit Rückgabe-Cleanup**, nicht `$effect` — das Issue
  beschreibt es als `$effect`, der Bestand sagt etwas anderes. Dem Bestand folgen.
- **Svelte 5 Runes** (`$props`, `$state`, `$derived`) durchgehend, `onMount` daneben weiter üblich.
- **Karten-Markup Konto:** `Card.Root` / `Card.Header` / `Card.Title` / `Card.Content`.
- **Schreibweg Profil:** `UpdateProfileHandler` ist lehrbuchmäßiges Read-Modify-Write —
  `LoadUser` → nur gesetzte Pointer-Felder ändern → `SaveUser(*user)`
  (`internal/store/user.go:70`, schreibt die vollständige `user.json`). Ein neues Feld erbt
  dieses Verhalten, wenn es demselben Muster folgt (Pointer im Update-Struct,
  `auth.go:671–677`). Das Angebot-Flag gehört idiomatisch neben `PremiumSmsReplyAt`
  (`internal/model/user.go:37–38`) und wird über denselben `PUT /api/auth/profile`
  gesetzt — kein eigener Endpunkt nötig.
- **Virtueller Authentifikator** (`passkey-regression.spec.ts`, `beforeEach`):
  `context.newCDPSession(page)` → `WebAuthn.enable` → `WebAuthn.addVirtualAuthenticator`
  mit `protocol: 'ctap2'`, `transport: 'internal'`, `hasResidentKey: true`,
  `hasUserVerification: true`, `isUserVerified: true`,
  `automaticPresenceSimulation: true`; Abbau über `WebAuthn.removeVirtualAuthenticator`.
  ⚠️ Der Bestandstest fährt die Zeremonie über `page.evaluate` + `fetch` — er prüft die
  **Schnittstelle**, nicht die Oberfläche. Für #2199 ist ein Test nötig, der die echten
  Bedienelemente anfasst, sonst misst er die Zusicherung nicht dort, wo sie wirkt.
- **Mandanten-Isolation:** `middleware.UserIDFromContext(r.Context())`, u.a. `auth.go:646/662`.

## Dependencies

- Upstream: `@github/webauthn-json`, Browser-WebAuthn-API, `GZ_PUBLIC_HOST` (RP-ID).
- Downstream: der Anmeldepfad selbst — jeder Fehler hier sperrt Nutzer aus.

## Existing Specs & ADRs

- `docs/specs/modules/passkey_webauthn.md` (#2130, 8 ACs) — Backend, geliefert.
- `docs/specs/modules/passkey_rp_konfiguration.md` (#2130) — RP-ID aus `PublicHost`.
- ADR-0030 (HMAC-Session-Cookie), ADR-0060 (dauerhafte Anmeldung + Widerrufsliste),
  ADR-0063 (PWA-Offline).
- `sveltekit_login_refactor.md` und `account_page_extend.md` sind DRAFT von 2026-04 ohne
  ACs und nicht produktiv — **nicht** als Grundlage verwenden.
- Für #2199 ist eine **neue Frontend-Spec** nötig.

## Risks & Considerations

1. **Manueller Nachweis auf Staging ist versperrt (#2200) — der automatische nicht.**
   Die RP-ID kommt aus `GZ_PUBLIC_HOST`; auf Staging ist die Variable nicht gesetzt, ein
   Passkey lässt sich dort also nicht von Hand durchklicken. Der vorhandene
   `passkey-regression.spec.ts` läuft jedoch gegen einen **lokalen** Stack
   (`baseURL`, mit `assertNotProdBaseURL` gegen Produktion abgesichert) — der
   automatisierte Nachweis über den virtuellen Authentifikator ist von #2200 **nicht**
   betroffen. Konsequenz: die Absicherung dieses Tickets ruht auf dem lokalen E2E-Lauf,
   die Staging-Runde bleibt auf das beschränkt, was ohne echte Passkey-Zeremonie sichtbar
   ist (Anordnung der Anmeldewege, Konto-Karte, Abweis-Verhalten des Angebots).
2. **`/login` und `/account` sind vom Frontend-Browser-Gate nicht abgedeckt.** Das Gate lädt
   sechs Kernseiten (`/`, `/trips`, `/trips/new`, `/compare`, `/compare/new`, `/locations`).
   Ein Fehler auf der Anmeldeseite käme dort nicht an — eigener E2E-Nachweis ist Pflicht,
   nicht Kür.
3. **Es gibt heute keinen einzigen Test für `/login` oder `/account`** (weder Unit noch E2E).
   Die Nachweisbasis entsteht komplett neu.
4. **Rate-Limits.** `bug-703-login-ratelimit.spec.ts` verbraucht absichtlich das IP-Limit von
   30 Logins/Stunde; für Passkey gilt ein eigenes Limit derselben Größe
   (`internal/router/router.go:94`). Neue E2E-Tests müssen das einplanen, sonst scheitern sie
   an „429" statt an einem echten Fehler.
5. **Aufnahme in `.github/ci_e2e_specs.txt` ist eine Ratsche** — eine neue Spec dort braucht
   einen eigenen Filter-B-Beleg (3× hintereinander grün). Nicht nebenbei erledigt.
6. **Schema-Änderung an `internal/model/user.go`** löst `data_schema_backup.py` aus;
   Read-Modify-Write mit Merge ist Pflicht (BUG-DATALOSS-GR221).
7. **Passkey darf nie der einzige Weg sein** — Magic-Link bleibt Rettungsanker. Ein ADR, das
   das festhält, existiert nicht; die Vorgabe steht nur im Issue.
8. **Die alte Anordnung ist nicht die neue.** In `c09172f5` saß der Passkey-Button *unter*
   dem Passwort hinter einem „oder"-Trenner. #2199 will ihn auf dem Handy davor — die
   Wiederherstellung ist kein reines Zurückdrehen.

## Offene Punkte für die Analyse-Phase

- Wo genau greift das einmalige Angebot ab (nach dem Login-Redirect? auf der Zielseite?),
  und wie verhält es sich bei Nutzern ohne WebAuthn-fähiges Gerät?
- Braucht die Konto-Karte einen Weg, ein Label nachträglich zu ändern? (Backend kann es heute
  nicht; das Issue verlangt es nicht.)
- Reihenfolge auf dem Desktop bleibt unverändert — heißt das, der Passkey-Weg erscheint dort
  weiterhin unterhalb, oder gar nicht?

---

# Analysis (Phase 2)

## Type

Feature.

## Der Befund, der alles andere ordnet

**Es gibt heute keinen Weg, einen Passkey anzulegen.** `registerPasskey()` ist in
`frontend/src/lib/passkey.ts:32` definiert und hat **null Aufrufer**; `$lib/passkey` wird
im gesamten Frontend nicht importiert, und `frontend/src/routes/register/` erwähnt
Passkeys nicht (nachgemessen). Damit ist die Konto-Verwaltung (Teil 3 des Issues) nicht
das Sahnehäubchen, sondern die **Grundlage**: Ohne sie hat niemand einen Passkey, den
Teil 1 (Anmeldung) oder Teil 2 (Angebot) benutzen könnte. Die Abhängigkeitsreihenfolge
ist **3 → 1 → 2**, nicht die Nummerierung des Tickets.

## Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `frontend/src/routes/account/+page.svelte` | MODIFY | Passkey-Karte zwischen „Kanäle" (endet 475) und „Passwort ändern" (ab 477): Liste, Gerätename, Anlagedatum, letzte Verwendung, Löschen, Anlegen |
| `frontend/src/lib/passkey.ts` | MODIFY | `RegisteredPasskey` um `authenticator_name`/`last_used_at` ergänzen; Helfer zum Löschen |
| `frontend/src/routes/login/+page.svelte` | MODIFY | Passkey-Weg + Conditional-UI + Reihenfolge nach Bildschirmgröße |
| `internal/model/user.go` | MODIFY | Feld „Angebot abgewiesen" (Schema — Backup-Hook greift) |
| `internal/handler/auth.go` | MODIFY | Feld in `toProfileResponse` (602) und `UpdateProfileHandler` (671 ff.) |
| `frontend/src/routes/login/+page.server.ts` | MODIFY | Marker an die Redirect-URL bei erfolgreichem Passwort-Login |
| `frontend/src/routes/+layout.server.ts` | MODIFY | `has_passkey` + Abweis-Feld durchreichen (Profil wird dort schon geladen) |
| `frontend/src/routes/+layout.svelte` | MODIFY | Angebot-Banner nach dem Muster des iOS-Hinweises (180–201) |
| `frontend/e2e/passkey-konto.spec.ts` | CREATE | Oberflächen-echter Nachweis Konto |
| `frontend/e2e/passkey-login.spec.ts` | CREATE | Oberflächen-echter Nachweis Login + Reihenfolge |
| `frontend/e2e/passkey-angebot.spec.ts` | CREATE | Nachweis Einmaligkeit + Gerätunabhängigkeit |
| `internal/handler/*_test.go` | CREATE/MODIFY | Merge-Nachweis für das neue Feld |

## Scope Assessment

- Dateien: 8 MODIFY, 3–4 CREATE
- Geschätzte LoC: **580–800 gesamt** (Produktivcode ~300–380, Tests ~220–340)
- Risiko: **MEDIUM** — Anmeldepfad ist kritisch, aber kein Weg wird entfernt

Das reißt das 250er-Limit deutlich und auch den üblichen Override-Wert 500.
**Das Ticket ist zu groß für ein Arbeitspaket.**

## Technical Approach

**Teil 3 — Konto (Grundlage).** Neue `Card.Root`-Karte an der im Issue genannten Stelle.
Datenquelle ist das vorhandene `GET /api/auth/profile` — keine neue Leseroute. Löschen über
das vorhandene `DELETE /api/auth/passkey/credentials/{id}`, Anlegen über `registerPasskey()`.
Reine Frontend-Arbeit, kein Schema-Risiko, kein Aussperr-Risiko.

**Teil 1 — Login.** Bausteine aus `c09172f5` wiederverwenden (Conditional-UI,
`autocomplete="username webauthn"`, deutsche Fehlertexte, `data-testid="login-passkey-btn"`).
Zur Reihenfolge siehe „Offene Entscheidung".

**Teil 2 — Einmaliges Angebot.** Der Login ist eine klassische Server-Aktion mit
302-Weiterleitung; zwischen Anmeldung und Zielseite läuft kein Client-Code, ein
Browser-Speicher-Trick scheidet also aus. Sauberster Weg: Die Server-Aktion hängt einen
Marker an die Weiterleitungs-Adresse; das Layout entscheidet dann anhand dreier Bedingungen
(kein Passkey vorhanden · nicht abgewiesen · Gerät kann WebAuthn), ob das Banner erscheint.
Das Layout lädt das Profil ohnehin schon — kein Zusatzabruf. „Nicht jetzt" schreibt das Feld
über den vorhandenen `PUT /api/auth/profile`, damit gerätunabhängig. Ein einfacher
Boolean genügt; „Feld fehlt" und „false" bedeuten beide „nicht abgewiesen".

## Risiken

- **Aussperren: strukturell ausgeschlossen**, solange Passwort und Magic-Link im Dokument
  bleiben und nur die sichtbare Reihenfolge wechselt. Genau deshalb ist die CSS-Variante
  auch die sicherere: sie entfernt nichts, sie sortiert nur.
- **Gerät ohne WebAuthn:** `isWebAuthnSupported()` liefert `false` (auch ohne HTTPS) → der
  Knopf erscheint gar nicht. Eigener AC.
- **Abbruch / Zeitüberschreitung:** Texte liegen aus dem alten Stand vor. **Zu messen:**
  ob fehlgeschlagene Passkey-Versuche gegen das eigene IP-Limit (`internal/router/router.go:94`,
  30/Stunde) zählen — sonst sperrt sich ein Nutzer durch wiederholte Abbrüche schneller aus
  als über Passwort-Fehlversuche. Kein Spekulationspunkt, sondern ein Messpunkt.
- **Schema:** Backup-Hook greift automatisch bei `internal/model/`; weder Go noch Python
  prüfen streng auf bekannte Felder (nachgemessen, `DisallowUnknownFields` kommt nirgends
  vor), die Profil-Tests vergleichen Einzelschlüssel statt Gesamtform. Risiko gering.
- **Staging bleibt lückenhaft (#2200):** Der Zeremonie-Nachweis ruht vollständig auf dem
  lokalen E2E-Lauf. Die Staging-Runde darf „Anordnung, Karte, Banner sichtbar" behaupten —
  **nicht** „Anmeldung funktioniert".

## Nachweis-Strategie

Durchgehend: virtueller Authentifikator per CDP **plus echte Klicks auf die Bedienelemente**.
Der vorhandene `passkey-regression.spec.ts` fährt die Zeremonie über `page.evaluate` + `fetch`
und ist damit oberflächenblind — als Muster für den Aufbau brauchbar, als Nachweis für dieses
Ticket nicht.

- Konto: Registrieren und Löschen über die echten Knöpfe; dazu ein netzfreier Unit-Test
  „kein WebAuthn ⇒ kein Anlegen-Knopf".
- Login: Anmeldung ohne Passworteingabe über den echten Knopf; getrennt davon ein
  Zwei-Viewport-Test (375 px / 1280 px), der die tatsächliche Bildschirmposition der Blöcke
  vergleicht — unabhängig vom Anmelde-Erfolg.
- Angebot: Go-Test für den Merge (Feld gesetzt, Nachbarfelder unberührt — direkte Gegenprobe
  zur Datenverlust-Klasse). E2E: Banner erscheint einmal, „Nicht jetzt" → verschwindet;
  **zweiter Browser-Kontext mit derselben Anmeldung zeigt es nicht erneut** — das ist der
  eigentliche Beweis für „serverseitig gemerkt, nicht im Gerätespeicher".
- Aufnahme in `.github/ci_e2e_specs.txt` erst nach dem geforderten Beleg (3× grün in Folge).

## Offene Entscheidung (gehört in die Spec)

**Reihenfolge auf der Anmeldeseite: Stylesheet-Weiche statt JavaScript-Erkennung.**
Das Issue markiert das JS-Muster als „bereits entschieden". Gemessen: Alle vier
Bestands-Stellen *tauschen* oder *blenden aus*, keine sortiert um; Umsortierung per CSS
kommt im Frontend bisher nirgends vor. Das JS-Muster erkennt die Bildschirmgröße erst nach
dem Laden — der Server liefert immer die Desktop-Fassung, danach springt es. Auf der
Anmeldeseite wäre das ein sichtbarer Sprung genau dort, wo der Nutzer zu tippen beginnt.
Empfehlung: **ein einziges Formular, eine einzige Feldinstanz**, sichtbare Reihenfolge über
die bereits zentral definierte `mobile:`/`desktop:`-Variante (`app.css:91–92`, identischer
899-px-Schnitt). Kein Sprung, keine doppelten Eingabefelder (wichtig für Passwortmanager
und Autofill). JavaScript bleibt für das reserviert, was es zwingend braucht: die
Geräte-Fähigkeitsprüfung. Die Absicht des Issues („denselben Schnitt wiederverwenden,
nichts Neues erfinden") bleibt gewahrt — es wechselt nur das Werkzeug.

## Empfehlung zum Schnitt

Drei Arbeitspakete statt eines, in Abhängigkeitsreihenfolge:

| # | Paket | LoC | Warum hier |
|---|---|---|---|
| 1 | **Konto-Verwaltung** (Teil 3) | ~190–250 | Kleinstes Stück mit eigenem Nutzen; erst hiermit kann überhaupt jemand einen Passkey anlegen |
| 2 | **Login-Reihenfolge** (Teil 1) | ~180–250 | Kernziel des Tickets; braucht Paket 1, sonst gibt es nichts zu prüfen |
| 3 | **Einmaliges Angebot** (Teil 2) | ~100–140 | Schema-Änderung, geringster Eigennutzen, meiste Verdrahtung — zuletzt |
