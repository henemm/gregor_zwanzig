# Context: fix-2247-passkey-mobile-first-login

<!-- Issue #2247 — Scheibe 2 von #2199. Scheibe 1 (#2246) ist geliefert und geschlossen. -->

## Request Summary

Auf der Anmeldeseite entsteht ein Passkey-Weg. Auf dem Handy ist er der **erste sichtbare**
Anmeldeweg; Passwort, Google und Magic-Link bleiben darunter erreichbar. Auf dem Desktop
bleibt die heutige Reihenfolge, der Passkey-Weg sitzt dort unterhalb des Passwort-Formulars.

Der Vorgänger-Kontext des Epics liegt in `docs/context/feat-2199-passkey-ui.md` (Analyse auf
Epic-Ebene, Schnitt in drei Pakete). Dieses Dokument ergänzt nur, was für Scheibe 2 neu
gemessen wurde — es wiederholt die Epic-Analyse nicht.

## Related Files

| Datei | Relevanz |
|---|---|
| `frontend/src/routes/login/+page.svelte` | **Einzige Produktivdatei mit Kern-Änderung.** 120 Zeilen, enthält heute kein Wort „passkey". Blockfolge: Formular 59–90 → Google 91–106 → Fusslinks 108–118 |
| `frontend/src/lib/passkey.ts` | Fertige Client-Bausteine, **null Aufrufer im Login-Pfad**: `isWebAuthnSupported():17`, `loginWithPasskey(username):67`, `loginWithDiscoverablePasskey(signal?):102`. Beide Login-Wege beenden selbst mit `window.location.assign('/')` (`:91`, `:144`) |
| `frontend/src/app.css:91-92` | `@custom-variant mobile { @media (max-width: 899px) }` / `desktop { min-width: 900px }` — zentral definiert, identischer Schnitt |
| `frontend/src/routes/account/+page.svelte` | **Frisches Vorbild aus #2246**: Tri-State-Fähigkeitsprüfung, deutsche Fehlertexte, `data-testid`-Schnitt |
| `internal/router/router.go:97-121` | Passkey-Routen mit gemeinsamem IP-Limiter |
| `internal/middleware/ratelimit.go:75` | Token-Bucket-Mechanik |
| `frontend/e2e/passkey-regression.spec.ts:55-74` | Aufsatz des virtuellen CDP-Authentifikators (#2130) |
| `frontend/e2e/passkey-konto.spec.ts:259-280` | Derselbe Aufsatz, zweite Kopie (#2246); dazu Abbruch-Erzwingung per `setAutomaticPresenceSimulation` |
| `frontend/e2e/run-passkey-konto.sh` | Vorbild für einen eigenen, rate-limit-bewussten Testlauf |
| `frontend/e2e/prodUrlGuard.ts` | `assertNotProdBaseURL` — Pflicht-Vorspann jeder Passkey-Spec (#1265) |

Wiederverwendbar aus Commit `c09172f5` (24.06.2026, „Passkey-UI temporär entfernt"): der
vollständige Login-Anteil, −90 Zeilen — Conditional-UI-Anbindung, `autocomplete="username
webauthn"`, deutsche Fehlertexte, `data-testid="login-passkey-btn"`.

## Existing Patterns

- **Fähigkeitsprüfung als Tri-State.** `account/+page.svelte:57` hält
  `passkeySupported = $state<boolean | null>(null)`; `null` heisst „noch nicht gemessen" und
  rendert **nichts**, `false` rendert den Hinweistext, `true` den Knopf. Gesetzt wird erst in
  `onMount:360`. Dieses Muster ist die Vorlage — es unterscheidet sauber zwischen „kann nicht"
  und „weiss noch nicht".
- **Deutsche Fehlertexte zentral gemappt.** `account/+page.svelte:232-238`
  (`passkeyFehlertext(e, ersatz)`) übersetzt `NotAllowedError|AbortError|TimeoutError`.
  `passkey.ts` selbst wirft nur technische Codes und fängt nichts — die Übersetzung ist
  Aufgabe des Aufrufers.
- **Umsortierung per CSS existiert bereits — genau einmal.** `EditStagesPanelNew.svelte:1055`
  setzt unter `@media (max-width: 899px)` ein `order: -1`. Die Annahme des Issues,
  „Umsortierung per CSS kommt im Frontend bisher nirgends vor", ist damit **widerlegt** — das
  stärkt die gewählte Richtung. Zwei Einschränkungen: (a) es ist ein Einzelfall, kein Muster;
  (b) er läuft über **handgeschriebenes CSS im `<style>`-Block**, nicht über Tailwind-
  Utilities. Die `mobile:`/`desktop:`-Varianten werden im Bestand nur mit `hidden` (10×),
  `block` (4×), `flex` (2×), `pt-6`, `p-6`, `first-child` benutzt — **kein einziges
  `mobile:order-*`**. Die im Issue genannte Schreibweise wäre also neu, wenn auch
  Tailwind-Standard.
- **Der Präzedenzfall benutzt `gap`, nicht `space-y`** — `EditStagesPanelNew.svelte:706`
  trägt `flex flex-col gap-4`. Genau das macht das `order: -1` dort unfallfrei.
- **Anmeldung läuft als SvelteKit-Form-Action**, nicht über den zentralen API-Client:
  `<form method="POST">` mit `ActionData`. Der Passkey-Weg ist demgegenüber reiner
  Client-Code (nackte `fetch` mit `credentials: 'include'`, danach Selbst-Weiterleitung).
  Beide Wege existieren im selben Dokument nebeneinander — das ist kein Widerspruch, aber
  der Grund, warum Passkey-Fehler **nicht** über `form?.error` laufen können.

## Dependencies

- **Upstream:** `frontend/src/lib/passkey.ts` · Go-Endpunkte `/api/auth/passkey/login/{begin,finish}`
  und `/api/auth/passkey/discoverable/{begin,finish}` (`router.go:97-111`)
- **Downstream:** niemand — `/login` ist Blattseite. Kein anderer Code hängt an ihrer Struktur.
- **Fachlich:** Scheibe 1 (#2246) liefert den einzigen Weg, überhaupt einen Passkey anzulegen.
  Ohne sie gäbe es nichts anzumelden. Geschlossen ⇒ Voraussetzung erfüllt.

## Existing Specs & ADRs

- `docs/specs/modules/passkey_webauthn.md` — Ursprungs-Spec (#450); Schritt 9 beschreibt die
  Login-Seite in ihrer **alten** Anordnung (Knopf unterhalb, hinter „oder"-Trenner)
- `docs/specs/modules/passkey_konto_verwaltung.md` — Scheibe 1 (#2246)
- `docs/specs/modules/passkey_rp_konfiguration.md` — RP-ID-Herkunft (#2130)
- `docs/specs/modules/sveltekit_login_refactor.md` — Form-Action-Architektur der Anmeldeseite
- `docs/adr/0030-session-auth-hmac-cookie.md` — Session-Cookie-Format, das der Passkey-Login
  unverändert mitbenutzt
- Ein ADR zu „Passkey darf nie der einzige Weg sein" **existiert nicht**; die Vorgabe steht
  bisher nur im Issue.

## Gemessen: die Rate-Limit-Frage des Issues

Das Issue stellt sie ausdrücklich als Messpunkt. Antwort mit Belegen:

1. **Ja, abgebrochene Versuche zählen.** `IPRateLimiter.Middleware` (`ratelimit.go:75`) zieht
   den Token beim **Eintreffen der Anfrage**, vor dem Handler, ergebnisunabhängig. Ein
   Abbruch (`NotAllowedError`) passiert erst **nach** `/login/begin` — der Token ist weg.
2. **Der Deckel ist gleich, der Verbrauch nicht — die Sorge des Issues trifft zu, aber
   milder als befürchtet.** Passkey-Limit (`router.go:97`) und Passwort-Login-Limit
   (`router.go:45`) sind zahlengleich: `NewIPRateLimiter(30, time.Hour)`. Aber ein
   vollständiger Passkey-Login sind **zwei** Anfragen (`begin` + `finish`), ein
   Passwort-Login **eine**. Bei gleichem Deckel verbraucht der Passkey-Weg das Budget also
   **doppelt so schnell**: 15 vollständige Anmeldungen am Stück statt 30.
   Ein *abgebrochener* Versuch kostet dagegen nur 1 Token — `NotAllowedError` entsteht rein
   im Browser und löst keine eigene Anfrage aus, aber `login/begin` (`passkey.ts:68`) lief
   bereits vor `get(options)` (`:78`).
3. **Es ist keine Stundensperre.** Token-Bucket mit `rate.Every(window/burst)` — Nachfüllung
   **ein Token je 2 Minuten**, Burst 30. Wer sich leerläuft, wartet Minuten, nicht eine Stunde.
4. **Der schärfere Befund, den das Issue nicht vorhergesehen hat:** Alle Passkey-Routen teilen
   sich **einen** Eimer (`router.go:97-121`) — einschliesslich `discoverable/begin`, das die
   Conditional-UI **ohne Zutun des Nutzers bei jedem Aufruf der Anmeldeseite** auslöst. Ein
   Passwort-Versuch kostet 1 Token; ein blosser Seitenbesuch kostet bereits 1, jeder bewusste
   Passkey-Versuch 2 weitere, und eine Abbruch-Schleife kostet **2 Token je Runde** (der alte
   Stand startet die Conditional-UI im `finally` neu). Der Eimer leert sich also ohne Absicht.
   Gemildert dadurch, dass `isConditionalMediationAvailable()` **vor** dem Netzaufruf geprüft
   wird (reine Client-Prüfung) — Geräte ohne Conditional-UI verbrauchen nichts.
   Empirisch bestätigt: `run-passkey-konto.sh` teilt seinen Lauf, weil 38 Anfragen auf
   Passkey-Routen zuverlässig in HTTP 429 enden.

## Risks & Considerations

1. **🔴 Der Sprung beim Nachladen — nicht der Sprung in der Reihenfolge.** Der PO hat das
   JS-Muster verworfen, weil die Seite nach dem Laden umspringt. Die CSS-Lösung beseitigt den
   **Sortier**-Sprung, aber nicht den **Einfüge**-Sprung: `isWebAuthnSupported()` ist reine
   Client-Prüfung (`passkey.ts:17`), der Server rendert den Passkey-Block also **gar nicht**,
   und `onMount` fügt ihn ein. Auf dem Handy, wo er oben sitzt, schiebt das Einfügen das
   Benutzernamen-Feld nach unten — derselbe sichtbare Sprung an derselben Stelle. Ein
   Zwei-Viewport-Test mit `getBoundingClientRect` misst den **Zustand nach** dem Nachladen und
   ginge grün durch, ohne das zu fangen (Muster „Wächter misst die Zusicherung nicht").
   ⇒ Platz muss reserviert werden, und der Nachweis muss **erstes Bild gegen Ruhezustand**
   messen, nicht nur 375 px gegen 1280 px.
2. **`space-y-6` verträgt sich nicht mit `order`.** Der Container (`login/+page.svelte:35`)
   setzt Abstände per `space-y-6`, das `margin-top` auf alle Kinder **ausser dem DOM-ersten**
   legt. Bei visueller Umsortierung sässe der fehlende Abstand am falschen Element.
   ⇒ `flex flex-col gap-6`.
3. **🔴 Der vorgezogene Block schiebt den Passwort-Weg nach unten — dieser Fehler ist hier
   schon einmal passiert.** `EditStagesPanelNew.svelte:1062-1070` dokumentiert die Folgefalle
   von #963 (Bug #1375): Der hinter die vorgezogene Karte rückende Block landete bei
   y≈1300 px, ausserhalb des 844-px-Viewports, und wurde nie gesehen. Dieselbe Mechanik gilt
   hier — wer den Passkey-Block auf dem Handy nach oben zieht, schiebt Passwort, Google und
   Magic-Link nach unten. „Passwort bleibt erreichbar" ist deshalb **keine Selbstverständ-
   lichkeit, sondern eine zu messende Zusicherung** (Sichtbarkeit im Viewport, nicht nur
   Vorhandensein im DOM).
4. **Der alte Knopf war tot, solange kein Benutzername getippt war** (`disabled={!username}`).
   Als *erstes* Element auf dem Handy wäre das ein grauer, nicht bedienbarer Knopf — genau
   gegenteilig zur Absicht „tippt kein Passwort".
5. **Beide Client-Wrapper in `passkey.ts` sind oberflächenblind ungetestet.** Die
   Discoverable-**Endpunkte** sind bewiesen (`passkey-regression.spec.ts:285-288` meldet sich
   ohne Benutzernamen an; Go-Tests in `passkey_test.go`), aber die Tests fahren per
   `page.evaluate` + `fetch` an der Oberfläche vorbei. `loginWithDiscoverablePasskey`
   (`passkey.ts:102`) umgeht zusätzlich die Ponyfill und kodiert base64url von Hand
   (`:119-123`) — und stammt aus dem Commit „nie getestet, nie funktioniert". Die
   Conditional-UI hängt genau daran. Risiko benennen, nicht umbauen: Mechanismuswechsel wäre
   eine stille Abweichung von einer dokumentierten Entscheidung.
6. **Die Nachweis-Fläche liegt ausserhalb der CI-Ampel.** Weder `passkey-regression.spec.ts`
   noch `passkey-konto.spec.ts` stehen auf `.github/ci_e2e_specs.txt`; beide laufen heute in
   **keiner** CI-Strecke. Eine neue `passkey-login.spec.ts` täte es ebenso — alle 6 Checks
   gingen grün, ohne den Wächter dieses Tickets je auszuführen. Aufnahme in die Positivliste
   ist eine Ratsche (3× grün in Folge). ⇒ Mindestens eine Zusicherung gehört netzfrei in
   `frontend-test` (Vitest), damit überhaupt etwas **innerhalb** der Ampel bewacht.
7. **`/login` ist vom Frontend-Browser-Gate nicht abgedeckt** (es lädt `/`, `/trips`,
   `/trips/new`, `/compare`, `/compare/new`, `/locations`). Eigener Nachweis ist Pflicht.
8. **Staging kann die echte Zeremonie doch — die Randbedingung des Issues ist überholt.**
   Gemessen am 11.09.2026 **dort, wo der Wert wirkt**, nicht am Stellvertreter:
   `POST /api/auth/passkey/discoverable/begin` liefert auf Staging im Options-JSON
   `rpId: staging.gregor20.henemm.com` (HTTP 200, Stand `c2dd28aa`). Da RP-ID und RP-Origin
   in `internal/config/webauthn.go` aus **derselben** `ok`-Verzweigung von
   `deriveFromPublicHost()` stammen und weder Unit noch Drop-ins noch `.env` einen Override
   setzen, trägt auch der geprüfte Origin zwingend die Staging-Adresse. Beleg der Quelle:
   `/etc/systemd/system/gregor-api-staging.service` bzw. versioniert
   `henemm-infra/systemd/gregor-api-staging.service:20` mit
   `GZ_PUBLIC_HOST=https://staging.gregor20.henemm.com`.
   *Grenze der Messung:* Der Origin ist abgeleitet, nicht direkt beobachtet — eine echte
   `finish`-Runde braucht einen Authentikator.
   *Bleibende Hürde:* nginx-Basic-Auth vor allem ausser `/api/health`. Playwright löst das
   über `httpCredentials`; Vorbild `frontend/e2e/playwright.2128.staging.config.ts:45`,
   Zugangsdaten-Herkunft `docs/reference/operations_playbook.md:150-165`.
   ⇒ Der Zeremonie-Nachweis muss **nicht** allein lokal ruhen.
   *Der lokale Lauf bleibt trotzdem die Hauptstrecke* — schneller, ohne Basic-Auth, mit
   `assertNotProdBaseURL` gegen Produktion abgesichert; Staging kommt als Bestätigung dazu.
9. **Aussperren ist strukturell ausgeschlossen**, solange nur die sichtbare Reihenfolge
   wechselt und kein Weg entfernt oder ausgeblendet wird. Das ist ein AC, kein Nebensatz.
10. **Virtuellen Authentifikator ein drittes Mal kopieren**, nicht zu einem Helper heben —
   ein Helper berührte zwei heute grüne Specs und läge ausserhalb dieses Tickets.

## Offene Punkte für die Analyse-Phase

- Wie wird der Platz reserviert, ohne auf dem Desktop eine Lücke zu hinterlassen (dort sitzt
  der Block unten, ein reservierter Platz wäre dort weniger störend, aber nicht gratis)?
- Welche Zusicherung wandert konkret in `frontend-test` (Vitest), und trägt die dortige
  Testumgebung eine Svelte-Komponente mit `onMount`?
- Bleibt der Knopf bei leerem Benutzernamen bedienbar (Fokus aufs Feld) oder deaktiviert?
- Gilt die Staging-Einschränkung aus dem Issue nach #2200 noch?

*(Alle vier Punkte sind in der Analyse unten beantwortet.)*

---

# Analysis (Phase 2)

## Type

Feature.

## Der Befund, der alles andere ordnet

**Das eigentliche Problem ist nicht die Reihenfolge, sondern das Einfügen.** Der PO hat das
JavaScript-Muster verworfen, weil die Seite nach dem Laden sichtbar umspringt. Die
CSS-Umsortierung beseitigt aber nur den *Sortier*-Sprung. Solange der Passkey-Block erst im
Browser entsteht (`isWebAuthnSupported()` braucht `window`, `passkey.ts:17`), fügt die
Hydration ihn nachträglich ein — auf dem Handy oben, wo er das Eingabefeld nach unten schiebt.
Derselbe Sprung, dieselbe Stelle, anderes Werkzeug.

**Die Auflösung:** Der Block wird **serverseitig immer mitgerendert**. Der reservierte Platz
*ist* damit der Knopf und kann nicht von dessen echter Höhe abdriften. Die Fähigkeitsprüfung
im Browser **tauscht danach nur noch den Inhalt**, statt etwas einzufügen.

Das kehrt den Tri-State aus #2246 um:

| Zustand | Bedeutung | Gerendert |
|---|---|---|
| `null` | noch nicht gemessen (= **jede** Server-Ausgabe) | Passkey-Knopf |
| `true` | Gerät kann WebAuthn | Passkey-Knopf |
| `false` | Gerät kann kein WebAuthn | Hinweistext, **gleiche Containerhöhe** |

Gekaufter Nachteil: Auf Geräten ohne WebAuthn ist der Knopf kurz sichtbar, bevor er zum
Hinweis wird. Betroffen sind fast nur In-App-WebViews und altes Android-Firefox; vor der
Hydration löst ein Klick ohnehin nichts aus. Auf dem Desktop sitzt der Block unten — dort
folgenlos.

## Affected Files

| Datei | Art | Beschreibung |
|---|---|---|
| `frontend/src/routes/login/+page.svelte` | MODIFY | Passkey-Block (aus `c09172f5`), Conditional-UI, `autocomplete="username webauthn"`, Order-Klassen, Container `space-y-6` → `flex flex-col gap-6` |
| `frontend/src/routes/login/__tests__/login_erstes_bild.test.ts` | CREATE | SSR-Render-Test — der tragende Wächter, **innerhalb der CI-Ampel** |
| `frontend/src/routes/login/__tests__/app-stores-stub-hooks.mjs` | CREATE | Lokale ESM-Hooks für `$app/stores`; bewusst **nicht** in die geteilte Hook-Datei, die fremde grüne Tests speist |
| `frontend/e2e/passkey-login.spec.ts` | CREATE | Zeremonie am echten Knopf · Zwei-Viewport-Positionsvergleich · Höhengleichheit · Abbruch |
| `frontend/e2e/run-passkey-login.sh` | CREATE | Rate-Limit-bewusster Lauf nach Vorbild `run-passkey-konto.sh` |

`frontend/src/app.css` bleibt **unberührt** — die `mobile:`/`desktop:`-Varianten existieren
bereits (`:91-92`).

**Verworfen: Auslagerung in eine eigene Komponente.** Naheliegend, um den Block isoliert
testbar zu machen — aber der SSR-Test kann die **Route selbst** rendern (gemessen: ein
6-Zeilen-Stub für `$app/stores` genügt, `body` 3257 Zeichen). Eine Komponente wäre ein
Stellvertreter; geprüft würde dann nicht mehr das ausgelieferte Artefakt. Die Route direkt zu
rendern ist die schärfere Messung und spart eine Datei.

## Scope Assessment

- Dateien: 1 MODIFY, 4 CREATE
- Produktiv-LoC: ~95–110 · Test-LoC: ~280 · **gesamt ~390 von 500**
- Risiko: **MEDIUM** — Anmeldepfad ist kritischer Pfad, aber kein Weg wird entfernt
- Kein Puffer für zwei volle Fix-Runden. Fällt der rAF-Fühler durch seine Positivkontrolle
  (siehe unten), landet man bei ~300.

## Technical Approach

**Anordnung.** Der Passkey-Block steht **DOM-zuerst**; `desktop:order-*` schiebt ihn auf dem
grossen Bildschirm unter das Formular. Ein einziges `<form>`, eine einzige Instanz jedes
Eingabefeldes. Container `login/+page.svelte:35` wird `flex flex-col gap-6` — `space-y-*`
hängt `margin-top` an alle DOM-Geschwister ausser dem ersten und sässe nach der Umsortierung
am falschen Element. Das `space-y-4` **innerhalb** des `<form>` bleibt, dort sortiert nichts um.

**Bewusst gekaufter Preis (WCAG 2.4.3, Focus Order).** Eine Dokumentreihenfolge kann nicht
zwei Bildschirmreihenfolgen bedienen: `order` ändert die Mal-, nicht die Tab-Reihenfolge. Der
Bruch ist unvermeidbar, aber man darf wählen, welche Seite ihn trägt. Er liegt auf dem
**Desktop** — Ziel des Tickets ist das Handy, dort stimmen Fokus- und Sichtreihenfolge überein.
Gehört benannt in die Spec, damit es später niemand als Defekt „entdeckt".

**Knopf bei leerem Benutzernamen: nicht deaktivieren.** Ein `disabled`-Knopf ist nicht
fokussierbar und fällt für Tastatur und Screenreader ganz aus dem Weg — als erstes Element auf
dem Handy, ab der ersten Millisekunde sichtbar, wäre das ein toter Auftakt. Klick bei leerem
Feld setzt den Fokus auf `#username` und weist per `aria-describedby` darauf hin.
🔴 **Dieser Klick darf den Conditional-UI-`AbortController` NICHT abbrechen.** Der alte Stand
(`c09172f5`) bricht ab und startet im `finally` neu — jeder Fehlklick kostete zwei Token aus
dem geteilten Passkey-Eimer und tötete die Autofill-Anbindung, also genau den Weg, für den der
Knopf nur Notausgang ist.

**Mechanismus unverändert.** Knopf → `loginWithPasskey(username)` (Ponyfill-Weg),
Autofill → `loginWithDiscoverablePasskey` hinter `isConditionalMediationAvailable()`. Kein
Wechsel auf Discoverable für den Knopf — das wäre eine stille Abweichung von einer
dokumentierten Entscheidung und legte den Hauptweg auf den am wenigsten erprobten Code.

**Hinweis im `false`-Zweig.** Hinweistext wie in #2246 (`passkey-unsupported`), **kein**
knopfförmiges Element — das Issue fordert „kein Passkey-Knopf". Höhengleichheit kommt nicht
aus „Text einzeilig halten" (brüchig), sondern aus dem Container: `h-10 flex items-center`
fest, Text `text-xs leading-tight`. 40 px tragen auch zwei Zeilen à 16 px. Kein `truncate`,
kein `nowrap` — nichts wird abgeschnitten, auch bei vergrösserter Systemschrift nicht.

## Nachweis-Strategie

**Der SSR-Test ist der tragende Wächter, nicht die Zugabe.** Der Einfüge-Sprung existiert
*genau dann*, wenn das Server-HTML den Block nicht enthält. Eine Zusicherung auf die
Server-Ausgabe misst damit die Sache selbst — deterministisch, ohne Zeitfenster, ohne Browser.

- **Werkzeug existiert:** `svelte/server` `render()` über `frontend/test-svelte-ssr-hooks.mjs`,
  Vorbild `versand-tab/__tests__/channel_checkbox_dedupe_render.test.ts`. **Kein Vitest im
  Projekt** — der Runner ist Nodes eigener (`frontend/package.json:13`).
- **Innerhalb der Ampel:** Der CI-Check `frontend-test` fährt `npm test` **ohne Dateiliste**
  (`ci.yml:109`) über alle 288 Testdateien. Keine Positivliste, keine Ratsche — anders als bei
  `.github/ci_e2e_specs.txt`, wo bis heute keine Passkey-Spec steht.
- **Zweiseitig mit Positivkontrolle.** „Kein WebAuthn ⇒ kein Knopf" allein wäre wertlos:
  serverseitig ist `window` nie da, der Zweig entsteht von selbst, und der Test bliebe grün,
  wenn man den Wächter ersatzlos löscht. Geprüft wird deshalb **beides** — Server-HTML
  *enthält* den Knopf (fällt, wenn jemand auf `onMount`-Einfügen zurückfällt) und der
  `false`-Zweig zeigt den Hinweis.

**Browser-Nachweise** (`passkey-login.spec.ts`, lokal gegen den gebauten Vorschauserver,
`assertNotProdBaseURL` als Pflicht-Vorspann):

1. **Zeremonie am echten Knopf** — virtueller CDP-Authentifikator, Aufsatz ein drittes Mal
   kopiert (`passkey-regression.spec.ts:55-74`), kein geteilter Helper. Anmeldung ohne
   Passworteingabe.
2. **Zwei-Viewport-Positionsvergleich (375/1280).** Wird gebaut — der SSR-Test **ersetzt ihn
   nicht**: Dieser sieht nur, dass die Order-Klassen im Markup stehen (Draht), nicht, dass sie
   im Browser greifen (Wirkung). Muster: `issue-725-mobile-sidebar.spec.ts:35-60`.
3. **Höhengleichheit in allen drei Zuständen** — `false` erzwingbar über `addInitScript`, das
   `window.PublicKeyCredential` löscht. Damit real gemessen statt behauptet.
4. **Passwort-Weg bleibt im Bildschirm** — nicht nur im DOM. Direkte Gegenprobe zu Bug #1375.
5. **Abbruch ⇒ deutsche Meldung**, Passwort-Weg weiter bedienbar. Muster
   `passkey-konto.spec.ts:579-604` (`setAutomaticPresenceSimulation: false` + Timeout-Kürzung).

**rAF-Fühler für den Sprung — mit Vorschaltbedingung.** `addInitScript` hält im ersten
Animationsframe `#username.getBoundingClientRect().top` fest, der Test vergleicht gegen den
Ruhezustand. Ohne Schwelle, misst die Grösse, um die es geht. **Nicht** zusätzlich CLS: beide
teilen denselben blinden Fleck (Einfügung vor dem ersten Paint), zwei Fühler verdoppeln nur
LoC und Flake-Fläche.
🔴 **Positivkontrolle zuerst:** An einer Attrappe mit `{#if}` + `onMount`-Einfügen messen, ob
der Fühler überhaupt ausschlägt. Schlägt er nicht aus, **fällt er ersatzlos** — die Schwelle
wird nicht nachjustiert. Dann trägt der SSR-Test allein, und die Browser-Spec beweist nur die
Zeremonie.

**Staging.** Entgegen der Randbedingung des Issues benutzbar (Risiko 8 oben). Der lokale Lauf
bleibt Hauptstrecke; Staging kommt als Bestätigung dazu, über `httpCredentials`
(`playwright.2128.staging.config.ts:45`).

**Betriebshinweis:** In diesem Worktree fehlt `frontend/node_modules` — vor dem ersten
Testlauf `npm ci` im `frontend/`-Verzeichnis.

## Dependencies

Unverändert gegenüber dem Kontext-Teil oben: `passkey.ts` (Client), vier Go-Login-Endpunkte,
Scheibe 1 (#2246) als fachliche Voraussetzung (geschlossen).

## Open Questions

Keine offenen Punkte für die Spec-Phase. Die vier Fragen aus Phase 1 sind beantwortet:
Platzreservierung über Server-Rendering · Wächter als SSR-Test in `frontend-test` (kein
Vitest, `onMount` läuft dort bewusst nicht — was hier der Vorteil ist) · Knopf bleibt
bedienbar und fokussiert das Feld · Staging ist nach #2200 wieder benutzbar.
