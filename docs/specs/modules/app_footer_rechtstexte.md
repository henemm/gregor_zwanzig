---
entity_id: app_footer_rechtstexte
type: module
created: 2026-09-21
updated: 2026-09-21
status: draft
version: "1.0"
tags: [frontend, layout, footer, datenschutz, impressum, multi-user, epic-2138, issue-2268]
---

# App-Footer mit Impressum und Datenschutz

## Approval

- [ ] Approved

## Purpose

Gregor bekommt einen app-weiten Footer mit genau zwei Links, „Impressum" und „Datenschutz", die auf die bereits veröffentlichten Rechtstexte auf henemm.com zeigen, sowie unter dem Knopf „Konto erstellen" einen Hinweissatz mit Datenschutz-Link. Damit ist die Informationspflicht für das Multi-User-Produkt (Epic #2138, S1 von #2146) erfüllt, ohne eine eigene Rechtstext-Route in Gregor zu betreiben und ohne Zustimmungsschritt bei der Registrierung (Rechtsgrundlage Art. 6 Abs. 1 lit. b DSGVO).

**Feststehende PO-Entscheide (nicht neu verhandeln):**

- Impressum: `https://www.henemm.com/footer-information/imprint/`, Linktext „Impressum".
- Datenschutz: `https://www.henemm.com/legal/gregor-zwanzig/privacy-policy/`, Linktext „Datenschutz".
- Hinweissatz wörtlich: „Hinweise zum Umgang mit deinen Daten: Datenschutz". Der Link liegt NUR auf dem letzten Wort „Datenschutz". Der Satz steht direkt unter dem Knopf „Konto erstellen", VOR dem „oder"-Trenner und dem Google-Block, ist also auch für Google-Registrierer sichtbar.
- KEINE Pflicht-Checkbox (Ticket #2269 ist gestrichen). Der Knopf bleibt ohne Zustimmungsschritt bedienbar.
- Footer app-weit, auch ohne Login sichtbar, mobil über der BottomNav erreichbar.

## Source

- **File:** `frontend/src/routes/+layout.svelte` (Verdrahtung), `frontend/src/lib/components/shared/AppFooter.svelte` (neuer Baustein), `frontend/src/routes/register/+page.svelte` (Hinweissatz)
- **Identifier:** `AppFooter` (neu); `{#if}`-Verzweigung im Layout (Zeilen 234–265); Formular-Ende und Google-Block in `register/+page.svelte` (Zeilen 67–89)

> Schicht: reine Frontend-Arbeit (SvelteKit auf gregor20.henemm.com). Kein Go-, kein Python-Code, keine API, keine Persistenz.

## Estimated Scope

- **LoC:** ca. +50/-1 produktiv (Baustein ~35, Layout ~8, Register ~8); Tests ca. +150 (zählen nicht gegen das Limit; vor `/40` mit `workflow.py status` gegenlesen)
- **Files:** 3 produktive Dateien (1 neu, 2 geändert) + 2–3 Test-/Prüfstand-Dateien (neu)
- **Effort:** low–medium (zentrale Datei `+layout.svelte` rendert jede Route, Änderung ist aber rein additiv)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/routes/+layout.svelte` | Frontend-Layout | einziger Ort für app-weites Chrome; rendert jede Route |
| `frontend/src/app.css` (`.mobile-scroll-pad`, `--g-nav-clearance`, `--g-ink-3`, `--g-paper`) | Design-Tokens/Utility | Freihaltung über der BottomNav; gedämpfter, AA-tauglicher Ton |
| `frontend/src/lib/components/ui/sidebar/BottomNav.svelte` | Frontend-Baustein | `fixed z-50`, nur mobil; der Footer darf ihn nicht verdecken/verdeckt werden |
| `frontend/src/lib/components/shared/EditorStickyFooter.svelte` | Frontend-Baustein | Editor-Footer (nur `CompareNewEditor`), KEIN Seiten-Footer; nicht wiederverwenden |
| `https://www.henemm.com/footer-information/imprint/`, `https://www.henemm.com/legal/gregor-zwanzig/privacy-policy/` | externe Ziele | seit 2026-09-21 live (henemm-website PR #74); keine Laufzeitabhängigkeit der App |
| Spec #2316 (Systemhinweise), AC-7 | Vorrangregel | nie zwei Systemhinweise übereinander am unteren Rand |

## Implementation Details

**Befund gegen den echten Code (Stand Worktree, `+layout.svelte` 367 Zeilen):**

- Es gibt heute genau zwei Zweige: `{#if isLogin || isShowcase}` (nackt, nur `{@render children()}`) und `{:else}` (App-Chrome: `OfflineSperre`, `div.flex.h-screen` mit `Sidebar` und `<main class="mobile-scroll-pad flex-1 overflow-auto px-4 desktop:p-6 desktop:pt-6">`, danach `{#if !isWizard}` BottomNav + KontoSheet).
- `isLogin` ist `publicPages.includes(pathname)` mit `/login /register /forgot-password /reset-password /verify-email`. `isShowcase` ist `pathname === '/_design'`. `isWizard` ist `pathname.startsWith('/trips/new')`.
- `/trips/new` (`TripNewEditor.svelte`) hat KEINEN `EditorStickyFooter` und kein `position: fixed/sticky` am unteren Rand. `EditorStickyFooter` wird nur von `CompareNewEditor` (`/compare/new`) verwendet; dort ist `isWizard` falsch, die BottomNav also sichtbar. `<main>` trägt auch im Wizard weiterhin `.mobile-scroll-pad` (nur die BottomNav entfällt).

**1. Neuer Baustein `frontend/src/lib/components/shared/AppFooter.svelte`**

- `<footer>` mit `<nav aria-label="Rechtliches">` und genau zwei `<a>`: „Impressum" und „Datenschutz". Die zwei URLs stehen als benannte Konstanten im Baustein (eine Quelle der Wahrheit, im Test wörtlich geprüft).
- Beide Links: `target="_blank"` und `rel="noopener noreferrer"`. Begründung: Die App läuft als PWA (Standalone); ein Wechsel im selben Tab auf henemm.com nähme dem Nutzer den Rückweg in die App. Der Service-Worker fängt nur same-origin-Navigationen ab (Regel 3), der Cross-Origin-Link läuft unbeeinflusst; in `hooks.server.ts` gibt es keine CSP mit `navigate-to`/`form-action`.
- Gedämpfter Ton `color: var(--g-ink-3)` (`#6b675c`; gemessen 5.13:1 auf `--g-paper` `#f6f4ee`, 5.65:1 auf Weiß, WCAG-AA erfüllt). `--g-ink-4` wird NICHT verwendet (nur 2.85:1 auf Weiß; laut Design-Leitprinzip nur Placeholder/Disabled).
- Mindest-Tippfläche: jeder Link `min-height: 44px` (und ausreichend Breite/Abstand), damit er mobil sicher trifft.
- KEIN `position: fixed`/`sticky`, keine erzwungene Höhe, keine Hintergrundfarbe (erbt Papier bzw. Weiß der Umgebung).

**2. `+layout.svelte`: `{#if}` in drei Arme trennen**

```
{#if isShowcase}
  {@render children()}                       <!-- bewusst KEIN Footer -->
{:else if isLogin}
  {@render children()}
  <AppFooter />                              <!-- öffentlicher Zweig -->
{:else}
  <OfflineSperre />
  <div class="flex h-screen"> <Sidebar …/>
    <main class="mobile-scroll-pad …">
      {@render children()}
      <AppFooter />                          <!-- letztes Kind INNERHALB <main> -->
    </main>
  </div>
  {#if !isWizard} BottomNav + KontoSheet {/if}
{/if}
```

- App-Zweig: Der Footer ist das letzte Kind INNERHALB von `<main>` (nicht Geschwister neben `<main>`, das verzerrte die Flex-Zeile Sidebar|main). Er scrollt mit, erbt die BottomNav-Freihaltung `.mobile-scroll-pad` (inklusive der `:has()`-Regeln für die Offline-Bänder) und ist ab 900 px Breite ohne Zusatzarbeit am Ende des Inhalts erreichbar.
- Öffentlicher Zweig: Footer nach `{@render children()}`. Login/Register sind `min-h-screen`-zentriert, der Footer steht darunter (unter der Falte, Seite scrollt). Der Hinweissatz auf der Register-Seite ist der sichtbare Verweis, der Footer der Auffangweg.
- Showcase (`/_design`): bewusst KEIN Footer, damit „die Brand-Demos die einzigen App-Bausteine" bleiben (Kommentar im Layout, Zeile 206). Der Showcase-Arm trägt einen erklärenden Kommentar.
- Vorrangregel #2316 AC-7: kein neues `fixed`-Element am unteren Rand. Update-Hinweis, iOS-Hinweis und Passkey-Angebot bleiben unverändert und haben weiterhin Vorrang.

**3. `frontend/src/routes/register/+page.svelte`: Hinweissatz**

Direkt nach dem `<form>`-Element (das den Knopf enthält), VOR `{#if data.googleEnabled}` (also vor dem „oder"-Trenner), ein Absatz `<p class="text-center text-xs text-muted-foreground">Hinweise zum Umgang mit deinen Daten: <a href="https://www.henemm.com/legal/gregor-zwanzig/privacy-policy/" target="_blank" rel="noopener noreferrer" class="underline …">Datenschutz</a></p>`. Die Seite nutzt shadcn-Tokens; `text-muted-foreground` (`--g-ink-muted` `#5c5a52`, 6.28:1 auf `--g-paper`) ist derselbe gedämpfte Ton wie die Nachbarzeilen. Der Satz liegt als Geschwister NACH dem `<form>`-Element; das Formular bleibt unverändert, keine neuen Felder. Die Ziel-URL des Satzes ist dieselbe Konstante wie im Footer, sofern sie ohne Zusatzaufwand importierbar ist; andernfalls Literal mit identischem Wert (Test prüft den Wert).

**4. Test-Strategie (Neubau, deshalb hier festgehalten)**

- `frontend-test` ist `node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks --test` (KEIN Vitest) und in der CI-Ampel; Playwright-E2E sind NICHT in der Ampel.
- Es existiert kein Test, der `+layout.svelte` rendert. Der Verdrahtungsbeweis „Footer da/nicht da je Route" braucht deshalb einen Layout-SSR-Rendertest je Pfad (`/login`, `/register`, `/trips`, `/trips/new`, `/_design`, zusätzlich `/compare/new`) mit `svelte/server`. Dafür entstehen NEU: (a) ein Hook-Stub für `$app/state` mit einstellbarem Pfad (`page.url.pathname`, je Aufruf frisch gelesen wie in `frontend/src/routes/login/__tests__/app-stores-url-stub-hooks.mjs`; `+layout.svelte` liest `page` aus `$app/state`, das in allen bestehenden Stubs fehlt) und (b) eine Leer-Auflösung für `.css`-Importe (`import '../app.css'`). Weitere Layout-Importe (`$lib/pwa/*`, `$lib/api.js`, `$lib/passkey`, `bits-ui` über `ui/sidebar`) sind beim Bau zu bestätigen; falls `bits-ui`-Runen-Module stören, wird `frontend/src/lib/components/trip-new/__tests__/ssrRunesHook.mjs` (`compileModule`-Hook plus `$app/*`-Stubs) mit eingebunden.
- Tatsächlich vorhandene Prüfstände (real geprüft): `frontend/test-svelte-ssr-hooks.mjs` (liegt im Frontend-Wurzelordner, NICHT unter `src/lib/`; kompiliert `.svelte` per `svelte/compiler`, löst `$lib/*` relativ zur Testdatei auf), `frontend/src/lib/components/trip-new/__tests__/ssrRunesHook.mjs`, Vorbild für einstellbaren Pfad `frontend/src/routes/login/__tests__/app-stores-url-stub-hooks.mjs`, Render-Vorbild `frontend/src/lib/components/shared/__tests__/alarme_tab_quiet_hours_zone_hinweis.test.ts` (Hook-Registrierung relativ zur Testdatei, Pfadregel #1409).
- Register-Test: rendert `register/+page.svelte` per SSR (mit `data={{ googleEnabled: true }}` und `false`) und prüft Wortlaut, Link-Ziel, Link nur auf „Datenschutz" und die Reihenfolge Knopf, Satz, „oder"-Trenner. Bestehender Test `register/__tests__/register_email_taken.test.ts` ist ein Action-Test ohne Render und bleibt unberührt.
- Testdateien werden nach Verhalten benannt (z. B. `app_footer_je_route.test.ts`, `register_datenschutz_hinweis.test.ts`), nicht nach Issue-Nummer.
- Kontrast und Tippfläche werden gemessen (Rechenprobe der Kontrastformel gegen die echten Token-Werte aus `app.css`; Tippflächen im Browser per Live-Prüfung), nicht per Dateiinhalt-Grep.
- Zusätzlich: Live-Prüfung auf Staging (`https://staging.gregor20.henemm.com`) und Fresh-Eyes-Inspektion mobil (UI-Änderung, Pflicht).
- **Erwartung an die Mutations-Gegenprobe des Adversary** (je Verfälschung MUSS mindestens ein Test rot werden, sonst ist es ein Finding): Footer aus dem öffentlichen Zweig entfernen; Footer aus dem App-Zweig entfernen; Footer im Showcase-Zweig einschalten; Impressum- und Datenschutz-URL vertauschen; `rel`/`target` entfernen; Hinweissatz-Link auf das falsche Wort legen (z. B. auf den ganzen Satz); Hinweissatz hinter den „oder"-Trenner verschieben; Footer als `position: fixed` setzen; Footer im App-Zweig als Geschwister neben `<main>` statt darin.

**5. Code-Teilungs-Regel Trip/Ortsvergleich:** Der Footer ist app-weites Chrome, kein Trip- oder Compare-Baustein. Es existiert kein Pendant, das geteilt werden müsste; die Regel „Trip und Ortsvergleich teilen Code" greift daher nicht. Der Baustein liegt trotzdem unter `shared/`, weil er von Layout und (bei URL-Wiederverwendung) Register genutzt wird.

**6. Kein datenbewegender Endpoint:** Es werden keine Daten gelesen, geschrieben oder pro Nutzer getrennt. Die Zwei-Nutzer-Prüfung (Pflicht bei jedem neuen datenbewegenden Endpoint) entfällt daher; es gibt keinen Endpoint und keine `user_id`.

## Expected Behavior

- **Input:** Aufruf beliebiger Gregor-Seiten im Browser, mit oder ohne Anmeldung, Desktop und Mobil; Klick auf „Impressum" oder „Datenschutz"; Öffnen der Registrierungsseite.
- **Output:** Am Ende des Inhalts jeder Seite außer `/_design` stehen die Links „Impressum" und „Datenschutz" in gedämpftem, gut lesbarem Ton; sie öffnen die Rechtstexte auf henemm.com in einem neuen Tab. Unter „Konto erstellen" steht der Satz „Hinweise zum Umgang mit deinen Daten: Datenschutz" mit Link auf dem letzten Wort.
- **Side effects:** Keine. Keine Persistenz, keine Netzwerkaufrufe der App, kein neues festes Element, kein Zustimmungsschritt. Die Registrierung funktioniert unverändert.

## Acceptance Criteria

- **AC-1:** Given ein angemeldeter Nutzer auf einer App-Route wie `/trips` / When er bis zum Ende des Inhalts scrollt / Then steht dort ein Footer mit genau zwei Links: „Impressum" mit Ziel `https://www.henemm.com/footer-information/imprint/` und „Datenschutz" mit Ziel `https://www.henemm.com/legal/gregor-zwanzig/privacy-policy/`, Linktexte und URLs wörtlich.
  - Test: Layout-SSR-Rendertest für `/trips` (App-Zweig) zählt die Links im `<footer>` (genau 2), prüft Linktext und `href` wörtlich und dass der Footer INNERHALB von `<main>` als letztes Kind steht. Live-Prüfung auf Staging klickt beide Links durch.

- **AC-2:** Given ein Besucher ohne Anmeldung auf `/login` bzw. `/register` / When er die Seite ansieht und ans Ende scrollt / Then ist derselbe Footer mit denselben zwei Links sichtbar (öffentlicher Zweig, ohne Sidebar und BottomNav).
  - Test: Layout-SSR-Rendertest für `/login` und `/register` prüft je Pfad, dass der Footer mit den zwei Links vorhanden ist und keine Sidebar/BottomNav gerendert wird. Live-Prüfung auf Staging ohne Session.

- **AC-3:** Given die Showcase-Seite `/_design` / When sie geladen wird / Then erscheint dort KEIN Footer (die Brand-Demos bleiben die einzigen App-Bausteine).
  - Test: Layout-SSR-Rendertest für `/_design` prüft, dass weder `<footer>` noch einer der zwei Links im Ergebnis steht (Leck-Schutz gegen den gemeinsamen nackten Zweig).

- **AC-4:** Given der Nutzer öffnet den Anlege-Editor `/trips/new` (App-Zweig ohne BottomNav) / When er bis ans Ende der Seite scrollt / Then stehen die zwei Footer-Links unterhalb des Editors vollständig sichtbar und anklickbar und werden von keinem festen oder klebenden Editor-Element verdeckt.
  - Test: Layout-SSR-Rendertest für `/trips/new` prüft Footer im `<main>`-Zweig ohne BottomNav; Live-Prüfung auf Staging (Desktop und mobil) scrollt ans Ende und klickt beide Links. Der Test belegt zugleich, dass der Editor keinen `EditorStickyFooter` mountet.

- **AC-5:** Given der Nutzer öffnet den Vergleichs-Anlegeeditor `/compare/new` mit seinem klebenden Editor-Fuß / When er bis ans Ende scrollt / Then bleiben sowohl die Aktion des Editor-Fußes als auch beide Footer-Links erreichbar und der Editor-Fuß deckt die Footer-Links nicht ab.
  - Test: Layout-SSR-Rendertest für `/compare/new` prüft, dass der Footer im `<main>` nach dem Editor steht; Live-Prüfung auf Staging mobil prüft per Geometrie, dass die Links am Scroll-Ende oberhalb des Editor-Fußes/der BottomNav liegen und klickbar sind.

- **AC-6:** Given ein Nutzer auf einem Mobilgerät (Viewport < 900 px) auf einer App-Route mit sichtbarer BottomNav / When er ganz nach unten scrollt / Then sind beide Footer-Links vollständig sichtbar und anklickbar, liegen oberhalb der BottomNav und werden nicht von ihr verdeckt; der Footer selbst ist kein `position: fixed`-Element.
  - Test: Playwright-Live-Prüfung auf Staging (Mobil-Viewport): am Scroll-Ende liegt die Unterkante beider Links oberhalb der Oberkante der BottomNav, `elementFromPoint` in der Linkmitte trifft den Link, berechneter Stil des Footers ist nicht `fixed`. Zusätzlich SSR-Test: der Footer steht innerhalb des Elements mit Klasse `mobile-scroll-pad`.

- **AC-7:** Given der Footer ist sichtbar / When der Nutzer „Impressum" oder „Datenschutz" anklickt / Then öffnet sich das Ziel in einem neuen Tab (`target="_blank"`) und der Link trägt `rel="noopener noreferrer"`, sodass die App im ursprünglichen Tab (auch als PWA) erhalten bleibt.
  - Test: Layout-SSR-Rendertest prüft `target` und `rel` beider Links; Live-Prüfung auf Staging klickt einen Link und beobachtet ein neues Fenster/Tab mit der Ziel-URL, während die App-Seite im Ursprungstab stehen bleibt.

- **AC-8:** Given die Registrierungsseite `/register` / When sie geladen wird / Then steht direkt unter dem Knopf „Konto erstellen" der Satz „Hinweise zum Umgang mit deinen Daten: Datenschutz", und der Link liegt ausschließlich auf dem letzten Wort „Datenschutz" mit Ziel `https://www.henemm.com/legal/gregor-zwanzig/privacy-policy/`.
  - Test: SSR-Rendertest von `register/+page.svelte` prüft den Textinhalt des Absatzes wörtlich, dass genau ein Link im Absatz existiert, dessen Text „Datenschutz" ist, und dessen `href`/`target`/`rel`.

- **AC-9:** Given die Registrierungsseite mit aktiviertem Google-Login (`googleEnabled = true`) / When der Nutzer von oben nach unten liest / Then steht der Hinweissatz zwischen dem Knopf „Konto erstellen" und dem „oder"-Trenner mit dem Google-Knopf, ist also auch für Google-Registrierer sichtbar; ohne Google-Login (`false`) steht er ebenfalls direkt unter dem Knopf.
  - Test: SSR-Rendertest mit `googleEnabled` `true` und `false` prüft die Reihenfolge der Positionen im gerenderten HTML (Knopf, Satz, dann „oder"/Google-Link) und die Anwesenheit des Satzes in beiden Fällen.

- **AC-10:** Given die Registrierungsseite / When der Nutzer die Felder ausfüllt und „Konto erstellen" betätigt / Then ist der Knopf ohne jeden Zustimmungsschritt bedienbar: es gibt keine Checkbox und kein Pflichtfeld für eine Datenschutz-Zustimmung, das Formular enthält unverändert nur Benutzername, E-Mail, Passwort und Passwort-Bestätigung.
  - Test: SSR-Rendertest zählt die Formularfelder (4 Eingaben, 0 `input[type=checkbox]`, Knopf ohne `disabled`); Live-Prüfung auf Staging: Formular mit gültigen Daten absenden, keine Zustimmung nötig.

- **AC-11:** Given Footer-Links und Hinweissatz in ihren realen Farben / When der Kontrast gegen den jeweiligen Hintergrund gemessen wird / Then beträgt er mindestens 4.5:1 (WCAG-AA); gemessen sind Footer-Links `--g-ink-3` `#6b675c` mit 5.13:1 auf `--g-paper` und 5.65:1 auf Weiß, Hinweissatz `--g-ink-muted` `#5c5a52` mit 6.28:1 auf `--g-paper`; `--g-ink-4` kommt nicht vor. Jeder Footer-Link ist mindestens 44 px hoch tippbar.
  - Test: Rechenprobe der WCAG-Kontrastformel mit den aus `app.css` gelesenen Token-Werten der tatsächlich gerenderten Farben (Test schlägt fehl, wenn ein Wert unter 4.5 fällt oder auf `--g-ink-4` gewechselt wird); Live-Prüfung auf Staging misst per `getBoundingClientRect` die Höhe der Links (>= 44 px) im Mobil-Viewport.

- **AC-12:** Given die Bestandsfunktionen der BottomNav und des Konto-Sheets / When die bestehenden Mobil-E2E-Spezifikationen laufen / Then bleiben `mobile-bottom-nav.spec.ts`, `mobile-bottom-nav-floating.spec.ts` und `issue-951-sheet-bottomnav.spec.ts` grün (Geometrie am unteren Rand unverändert; kein neues festes Element am unteren Rand, Vorrangregel #2316 AC-7).
  - Test: Lauf der drei Bestands-Specs gegen Staging nach dem Deploy (Live-Schicht, `/e2e-verify`); Ergebnis grün ohne Anpassung der Specs.

## Known Limitations

- **Kurze Seiten (R3):** Auf Seiten mit wenig Inhalt steht der Footer direkt unter dem Inhalt, nicht am unteren Fensterrand. Für den Start akzeptiert; ein Spalten-Layout mit `min-height` folgt nur, falls Adversary oder PO es bemängeln.
- **„Erreichbar" heißt „am Ende des Scrollbereichs":** Der Footer ist bewusst nicht dauerhaft eingeblendet (kein `fixed`, Vorrangregel #2316 AC-7).
- **Login/Register unter der Falte:** Diese Seiten sind `min-h-screen`-zentriert; der Footer erscheint erst beim Scrollen. Auf `/register` trägt der Hinweissatz den sichtbaren Verweis, der Footer ist der Auffangweg.
- **Abweichung von der Analyse:** Die Analyse ließ offen, ob `/trips/new` einen `EditorStickyFooter` hat. Nach Prüfung des Codes hat `TripNewEditor.svelte` keinen (nur `CompareNewEditor` unter `/compare/new` mountet ihn); AC-4 legt für den Wizard „Footer vorhanden, nichts verdeckt" fest, AC-5 deckt den Vergleichs-Editor mit klebendem Fuß zusätzlich ab (nicht Teil der Analyse). Außerdem liegt der genannte SSR-Prüfstand `test-svelte-ssr-hooks.mjs` im Frontend-Wurzelordner (`frontend/`), nicht unter `frontend/src/lib/`.
- **Nebenbefund außerhalb des Scopes (`publicPages`-Lücke):** `publicPages` im Layout (`/login /register /forgot-password /reset-password /verify-email`) ist kürzer als die serverseitige Liste in `hooks.server.ts` (`/magic-link`, `/magic-link/verify`, `/email-preview-dev` fehlen). Diese Seiten rendern für Nicht-Angemeldete im App-Chrome inklusive Sidebar. Der Footer erscheint dort über den App-Zweig ohnehin; die Lücke wird hier NICHT behoben, sondern als Checkbox-Zeile im Sammel-Issue #1199 geführt.
- **Externe Ziele:** Sind die Seiten auf henemm.com zeitweilig nicht erreichbar, öffnet sich im neuen Tab eine Fehlerseite; die App ist davon unberührt. Die Erreichbarkeit der Ziele wird beim Deploy per `verify-live.sh` der Website geprüft, nicht von Gregor.
- **Wortlaut und URLs** sind PO-Vorgabe; jede Änderung erfordert eine neue Freigabe, kein stilles Nachziehen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Berührt keine Entscheidungsfläche laut ADR-Index (Kanäle, Provider, Datenmodell/Persistenz, Auth, Editor-Paradigma, Test-/Deploy-Strategie). Es ist rein additives UI-Chrome im vorhandenen Layout; ADR-0034 (Bedienelemente sperren statt verstecken) und die Vorrangregel #2316 AC-7 bleiben unberührt. Der Verzicht auf eine eigene Datenschutz-/Impressum-Route und auf eine Pflicht-Checkbox ist PO-Entscheid (2026-09-15/21) und in Ticket #2146/#2268 dokumentiert.

## Changelog

- 2026-09-21: Initial spec created (Issue #2268, S1 von #2146, Epic #2138)
