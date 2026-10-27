# Context: feat-2268-footer-rechtstexte

## Request Summary
Issue #2268 (S1 von #2146, Epic #2138): Gregor bekommt einen app-weiten Footer mit zwei
Links (Impressum, Datenschutz) und unter dem Registrieren-Knopf einen Hinweissatz mit
Datenschutz-Link. Die Zielseiten sind seit 2026-09-21 live (henemm-website PR #74).
Nur Frontend-Arbeit; kein Backend, keine Daten, keine eigene Route in Gregor.

## Feststehende PO-Entscheide (nicht erneut vorlegen)
- Impressum -> `https://www.henemm.com/footer-information/imprint/`
- Datenschutz -> `https://www.henemm.com/legal/gregor-zwanzig/privacy-policy/`
- Hinweissatz (Wortlaut): „Hinweise zum Umgang mit deinen Daten: Datenschutz" (Link auf dem letzten Wort)
- KEINE Pflicht-Checkbox (#2269 gestrichen), Rechtsgrundlage Art. 6 Abs. 1 lit. b DSGVO
- Footer: app-weit, auch mobil über der BottomNav erreichbar, auch ohne Login sichtbar

## Related Files
| File | Relevanz |
|------|----------|
| `frontend/src/routes/+layout.svelte` (367 Z.) | Einziger Ort für app-weites Chrome. Zwei Zweige: `{#if isLogin \|\| isShowcase}` (nackt) und `{:else}` (Sidebar + `<main class="mobile-scroll-pad ...">` + BottomNav). Kein `<footer>`. |
| `frontend/src/routes/register/+page.svelte` | Konto-erstellen-Seite, `min-h-screen` zentriert; Knopf „Konto erstellen" Z.67-72, danach Google-Block und „Bereits registriert?"-Link |
| `frontend/src/app.css` Z.180-265 | Bottom-Stack-Tokens `--g-nav-*`; `.mobile-scroll-pad` (Utility-Layer) gibt unten `--g-nav-clearance + --g-s-4` frei, ab 900px 0 |
| `frontend/src/lib/components/ui/sidebar/BottomNav.svelte` | `fixed z-50`, nur mobil (`desktop:hidden`); `KontoSheet` daneben |
| `frontend/src/lib/components/shared/OfflineSperre.svelte`, `app.html` `#gz-stand` | Offline-Bänder oben, außerhalb `<main>` |
| `frontend/src/hooks.server.ts:25` | öffentliche Pfade serverseitig: login, register, logout, forgot-password, reset-password, verify-email, email-preview-dev, magic-link, magic-link/verify |

## Befunde aus der Recherche
1. **Zwei Zweige im Layout, Showcase teilt sich den nackten Zweig.** `/_design` (isShowcase) rendert
   ohne Chrome, damit „die Brand-Demos die einzigen App-Bausteine" sind (Kommentar Z.206). Ein Footer
   im nackten Zweig landet ungewollt auch dort → `{#if}` muss in drei Arme getrennt werden
   (öffentlich / Showcase / App) oder der Footer im nackten Zweig ausdrücklich für Showcase ausgenommen.
2. **Platzierung im App-Zweig:** äußeres `div.flex.h-screen`, `<main>` ist `overflow-auto`. Ein
   Footer NACH `</main>` würde die Sidebar-Spalte/Höhe verzerren; INNERHALB `<main>` scrollt er mit und
   erbt die vorhandene BottomNav-Freihaltung (`.mobile-scroll-pad`, inkl. `:has()`-Regeln für
   Offline-Bänder). „erreichbar" im Ticket = ans Ende des Scrollbereichs, nicht dauerhaft
   eingeblendet. Kein neues `fixed`-Element am unteren Rand (Vorrangregel #2316 AC-7: nie zwei
   Systemhinweise übereinander).
3. **Layout-Lücke (Bestand, außerhalb Scope):** `publicPages` im Layout (`/login /register
   /forgot-password /reset-password /verify-email`) ist kürzer als die serverseitige Liste
   (`/magic-link`, `/magic-link/verify`, `/email-preview-dev` fehlen). Diese Seiten rendern also für
   Nicht-Angemeldete im App-Chrome inkl. Sidebar. Der Footer erscheint dort über den App-Zweig
   ohnehin — kein Blocker für #2268. Nebenbefund → Sammel-Issue #1199, kein eigenes Ticket.
4. **Register-Seite ist `min-h-screen`-zentriert:** der Footer aus dem Layout hängt darunter
   (unter der Falte, ggf. Scroll). Der Hinweissatz unter dem Knopf ist für die Registrierung der
   eigentlich sichtbare Verweis; der Footer ist der app-weite Auffangweg.
5. **Externe Links:** keine bestehende Konvention für `target="_blank"` im Frontend (0 Treffer).
   Service-Worker (`service-worker.ts` Regel 3) fängt nur same-origin-Navigationen ab; ein
   Cross-Origin-Link (henemm.com) läuft unbeeinflusst. Keine CSP mit `navigate-to`/`form-action`
   in `hooks.server.ts` gefunden.
6. **Keine `/datenschutz`- oder `/impressum`-Route** in Gregor und keine geplant (PO 2026-09-15).

## Test-Infrastruktur (Erkenntnis für /20 und /40)
- `frontend-test` = `node --test` (kein Vitest), in der CI-Ampel; Playwright-E2E NICHT in der Ampel.
- SSR-Prüfstand: `test-svelte-ssr-hooks.mjs` (kompiliert `.svelte`, `$lib`-Auflösung),
  `trip-new/__tests__/ssrRunesHook.mjs` (Runen-Module + `$app/*`-Stubs).
- 🔴 **`$app/state` fehlt in allen Stubs.** `+layout.svelte` liest `page` aus `$app/state`
  (`page.url.pathname`); vorhanden sind nur `$app/navigation`, `$app/environment`, `$app/stores` (dort
  fest auf `/trips/new`). Zusätzlich `import '../app.css'`, das Node nicht laden kann. Ein
  Layout-Rendertest je Pfad braucht daher einen Stub für `$app/state` mit einstellbarem Pfad plus eine
  Leer-Auflösung für `.css`. Vorbild für einstellbaren Pfad:
  `routes/login/__tests__/app-stores-url-stub-hooks.mjs`. Weitere Layout-Importe (`$lib/pwa/*`,
  `$lib/api.js`, `$lib/passkey`) laufen im SSR nicht an (nur `onMount`/Handler) — beim Bau des
  Prüfstands zu bestätigen.
- Es existiert KEIN Test, der `+layout.svelte` rendert (`hooks.server.test.ts` und zwei E2E-Specs
  erwähnen es nur). Der Verdrahtungsbeweis (Footer da/nicht da je Route) ist also Neubau.
- Register-Seite: Test-Vorbild `register/__tests__/register_email_taken.test.ts` (Action-Test, kein
  Render); Render-Vorbild `shared/__tests__/alarme_tab_quiet_hours_zone_hinweis.test.ts`.

## Existing Patterns
- Geteilte Bausteine unter `frontend/src/lib/components/shared/`; `EditorStickyFooter.svelte` ist
  Editor-Footer, KEIN Seiten-Footer — nicht wiederverwenden.
- Kontrast-Vorgabe (CLAUDE.md): WCAG-AA 4.5:1; `--g-ink-4` nur Placeholder/Disabled;
  `--g-ink-3` (#6b675c) auf `--g-paper` (#f6f4ee) ist der zulässige gedämpfte Ton — Verhältnis messen.
- Kein Trip/Compare-Pendant betroffen (Code-Teilungs-Regel greift nicht: app-weites Chrome).

## Dependencies
- Upstream: keine Daten, keine API. Zwei feste Ziel-URLs auf henemm.com (live, `verify-live.sh` PASS).
- Downstream: jede Route rendert durch `+layout.svelte`; Bestands-E2E zur BottomNav
  (`mobile-bottom-nav*.spec.ts`, `issue-951-sheet-bottomnav.spec.ts`) messen Geometrie am unteren
  Rand und müssen weiter grün bleiben.

## Existing Specs
- Keine Spec zum App-Chrome/Footer. Nachbarn: #2316 (Systemhinweise, Vorrang am unteren Rand),
  #2131 (Offline-Bänder), #2128 (selbst gehostete Schriften). ADR-0034 (gesperrt und begründet).

## Risks & Considerations
- R1 Showcase-Leck (Befund 1) → eigener AC.
- R2 Footer unter der BottomNav verdeckt (Befund 2) → Platzierung im Scrollbereich, AC + Fresh-Eyes mobil.
- R3 Auf kurzen Seiten steht der Footer direkt unter dem Inhalt, nicht am Fensterrand — für den Start
  akzeptabel; Spalten-Layout mit `min-h` nur, wenn Adversary/PO es bemängelt.
- R4 Ein Test der nur die Komponente rendert beweist die Verdrahtung nicht → Layout-SSR-Test mit
  `$app/state`-Stub einplanen; Produktiv-LoC ~100, Prüfstand-Stub zählt als Test.
- R5 Kontrast der Footer-Links (WCAG-AA) → AC mit gemessenem Verhältnis.
- R6 Wortlaut/URLs sind PO-Vorgabe → im Test wörtlich prüfen (Ziel-URL, Linktext, Satz).

## Analysis

### Type
Feature (reine Frontend-Arbeit, kein Backend, keine Daten, keine Route in Gregor).

### Nachprüfung gegen `origin/main` (c737159e) — Ergänzung zur Recherche oben
- `+layout.svelte:234-265`: Login/Register/Passwort-Seiten (`publicPages`, Z.203) und `/_design` teilen sich den **nackten Zweig** `{#if isLogin || isShowcase}{@render children()}`. Der App-Zweig hat `<main class="mobile-scroll-pad flex-1 overflow-auto …">` (Z.249) mit BottomNav (nicht im Wizard `/trips/new`).
- **Folge:** Ein einziger Footer im Layout reicht nicht; er muss in **zwei** Zweigen erscheinen (öffentlich + App) und im Showcase-Zweig **fehlen**. Sauberste Form: `{#if isShowcase}` / `{:else if isLogin}` / `{:else}` mit dem Baustein `AppFooter` — jeder Zweig entscheidet bewusst.
- `register/+page.svelte:67-72`: „Konto erstellen"-Knopf, direkt danach `</form>`, dann Google-Block (nur bei `googleEnabled`), dann „Bereits registriert?". Der Hinweissatz gehört **direkt unter den Knopf, vor den „oder"-Trenner** — sichtbar auch für Google-Registrierer.
- Kein bestehender Rechtstext-Link im Frontend (Treffer nur ein Kommentar in `login/+page.server.ts:76`).
- Kontrast gemessen: `--g-ink-3` (#6b675c) auf `--g-paper` 5.13:1, auf Weiß 5.65:1 ⇒ WCAG-AA erfüllt. Die Register-Seite nutzt shadcn-Tokens (`text-muted-foreground`), nicht `--g-*` — dort denselben gedämpften Ton wie die Nachbarzeilen verwenden.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/AppFooter.svelte` | CREATE | Footer-Baustein mit zwei Links (Impressum, Datenschutz); URLs als Konstanten |
| `frontend/src/routes/+layout.svelte` | MODIFY | Footer im öffentlichen Zweig (unter `children`) und im App-Zweig (am Ende von `<main>`, erbt `.mobile-scroll-pad`); Showcase ausdrücklich ohne |
| `frontend/src/routes/register/+page.svelte` | MODIFY | Hinweissatz „Hinweise zum Umgang mit deinen Daten: Datenschutz" (Link auf dem letzten Wort) unter dem Knopf |
| Test: Layout-SSR-Prüfstand + Stub für `$app/state` (einstellbarer Pfad) + `.css`-Leer-Auflösung | CREATE | Verdrahtungsbeweis je Route (Neubau, s. „Test-Infrastruktur") |
| Test: Register-Hinweissatz | CREATE | Wortlaut, Link-Ziel, Position relativ zum Knopf |

### Scope Assessment
- Files: 3 produktiv + 2–3 Test-/Prüfstand-Dateien
- Estimated LoC: produktiv ca. +50/-1 (Baustein ~35, Layout ~8, Register ~8); Tests ca. +150 (zählen nicht gegen das Limit, wo als Testdatei erkannt — vor `/40` mit `workflow.py status` gegenlesen)
- Risk Level: **LOW–MEDIUM** — zentrale Datei (`+layout.svelte` rendert jede Route), aber rein additiv; Hauptrisiko ist der untere Rand mobil (BottomNav) und das Showcase-Leck.

### Technical Approach
1. **Baustein `AppFooter.svelte`** in `shared/` — zwei `<a>`-Links, gedämpfter Ton (`--g-ink-3`), Mindest-Tippfläche mobil. Kein `fixed`, keine Höhe erzwingen.
2. **App-Zweig:** Footer als letztes Kind **innerhalb** `<main>` (nicht als Geschwister neben `<main>` — würde die Flex-Zeile Sidebar|main verzerren). Er scrollt mit, ist mobil über `.mobile-scroll-pad` (inkl. `:has()`-Offline-Regeln) oberhalb der BottomNav erreichbar. **Kein neues Dauer-Element am unteren Rand** (Vorrangregel #2316 AC-7).
3. **Öffentlicher Zweig:** Footer nach `{@render children()}`; Login/Register sind `min-h-screen` ⇒ Footer steht unter der Falte, Seite scrollt. Der Hinweissatz auf der Register-Seite ist der sichtbare Verweis, der Footer der Auffangweg.
4. **Showcase:** kein Footer (eigener AC).
5. **Externe Links:** `target="_blank" rel="noopener noreferrer"` — Begründung: die App läuft als PWA (Standalone); ein same-tab-Wechsel auf henemm.com nähme dem Nutzer den Rückweg in die App. Service-Worker fängt nur same-origin ab ⇒ unbeeinflusst.
6. **Wortlaut/URLs sind PO-Vorgabe** → im Test wörtlich prüfen.
7. **Verdrahtungsbeweis:** Layout-SSR-Test je Pfad (`/login`, `/register`, `/trips`, `/trips/new`, `/_design`) mit `$app/state`-Stub; Vorbild `login/__tests__/app-stores-url-stub-hooks.mjs`. Mutations-Gegenprobe (Adversary): Footer aus einem Zweig entfernen / im Showcase-Zweig einschalten / URL vertauschen ⇒ je ein Test muss rot werden.

### Dependencies
- Upstream: nur die zwei live erreichbaren Ziel-URLs auf henemm.com (Datenschutz seit 2026-09-21, PR henemm-website #74).
- Downstream: jede Route rendert durch `+layout.svelte`; Bestands-E2E `mobile-bottom-nav*.spec.ts`, `issue-951-sheet-bottomnav.spec.ts` messen Geometrie am unteren Rand und müssen grün bleiben. Fresh-Eyes-Prüfung mobil (Footer nicht unter BottomNav verdeckt) ist Pflicht (UI-Änderung).

### Open Questions
- [x] Ziel-URLs, Wortlaut, keine Checkbox, Rechtsgrundlage — PO-Entscheid 2026-09-15/21, nicht erneut vorlegen.
- [x] `target="_blank"` — Tech-Entscheidung (PWA-Rückweg), keine PO-Frage.
- Keine offenen Fragen an den PO. Für /30: AC-Zuschnitt (Zweige, Showcase, Wortlaut, Kontrast, mobil erreichbar; Zwei-Nutzer-Test entfällt — kein datenbewegender Endpoint).
- Nebenbefund → #1199 (Sammel-Issue), kein eigenes Ticket: `publicPages` im Layout kürzer als serverseitige Liste (`/magic-link`, `/magic-link/verify`, `/email-preview-dev`).
