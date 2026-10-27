# Context: feat-2128-pwa-installierbar

Issue: #2128 (Scheibe 1 zu Epic #2127) · Track: Full Process · erstellt 2026-09-06

## Request Summary

Die Web-App soll auf Android und iOS vom Startbildschirm aus starten, auch ohne Netz eine
verständliche eigene Seite zeigen statt der Browser-Fehlerseite, die Schriften selbst ausliefern
(kein Google-Fonts-Aufruf mehr) und ein Programm-Update erst nach Nachfrage laden.

## Gemessener Ist-Stand

| Fundstelle | Befund |
|---|---|
| `frontend/src/app.html:8-10` | Schriften kommen extern von `fonts.googleapis.com` (Inter Tight 400/500/600/700, JetBrains Mono 400/500/600). Kein `@font-face`, keine lokalen Font-Dateien im Repo. |
| `frontend/src/app.html` (20 Z.) | Kein `theme-color`, kein `apple-mobile-web-app-capable`, keine Service-Worker-Registrierung. |
| `frontend/static/site.webmanifest` | Vorhanden: `name`, `short_name`, `start_url`, `display: standalone`, `background_color`/`theme_color` beide `#f6f4ee`, Icons 192/512. **Fehlt:** `id`, `scope`, `purpose: maskable`. |
| `frontend/static/` | `favicon.ico/svg`, `favicon-192.png`, `favicon-512.png`, `apple-touch-icon.png`, `robots.txt`, `site.webmanifest`. Keine Unterordner, keine Font-Dateien. |
| Volltextsuche Repo | **Null Treffer** für `service-worker`, `serviceWorker`, `workbox`, `vite-plugin-pwa`. Alles muss neu entstehen. |
| `frontend/svelte.config.js` | `@sveltejs/adapter-node`, Output nach `frontend/build/`. Runes erzwungen. |
| `frontend/package.json` | SvelteKit ^2.57, **Svelte 5** (^5.55), Vite ^8. Unit-Tests via Node-Test-Runner (`--experimental-strip-types`), kein vitest — siehe ADR-0020. |
| `frontend/src/hooks.server.ts:6,10-12,16-22,27-29` | Auth-Guard mit `publicPaths`-Liste; Session-Cookie `gz_session`, sonst `redirect(302,'/login')`. Setzt **`cache-control: no-cache` für alle `text/html`-Antworten**. |
| `frontend/src/routes/+layout.svelte:2,63-100` | Bindet `app.css` ein; steuert Chrome (TopAppBar/Sidebar/BottomNav) je nach Route. Einziger app-weiter Einhängepunkt. |
| `frontend/src/routes/+error.svelte` | **Existiert nicht.** Keine Fehler- und keine Offline-Seite vorhanden. |
| `frontend/src/lib/components/mobile/Toast.svelte` | Einzige Hinweis-Komponente. `kind` = info/success/warn/error, `position: absolute`, `bottom: 76px`, `role="status"`. **Kein globaler Store** — wird lokal in `TripNewEditor.svelte` und `CompareNewEditor.svelte` eingebettet. |
| `frontend/src/app.css:56,58,59,91-92` | `--g-accent #c45a2a`, `--g-paper #f6f4ee`, `--g-ink #1a1a18`; `--g-font-ui: 'Inter Tight'`, `--g-font-data: 'JetBrains Mono'`. Schriftnamen stehen **nur** in `app.css` und `app.html`. |
| Auslieferung | Systemd `gregor-frontend` / `gregor-frontend-staging`, Build `npm run build`, nginx proxied `/`. `/_app/immutable/…` bereits `max-age=31536000, immutable` + Brotli. Nginx setzt keine CSP — ein Service Worker ist nicht blockiert. |

## Existing Patterns

- **Globale Einbindung** gibt es nur über `+layout.svelte`; alles andere ist komponentenlokal.
- **Hinweis-Optik:** `Toast.svelte` ist das etablierte Muster (Token-Farben, `role="status"`). Der
  Update-Hinweis sollte es wiederverwenden, nicht ein zweites Hinweis-Aussehen erfinden.
- **Playwright:** `frontend/playwright.config.ts` fährt lokal gegen `http://localhost:4173`
  (Projekte `setup` → `tests`, `storageState: playwright/.auth/admin.json`). Staging läuft über
  eigene Configs (`frontend/e2e/playwright.<N>.staging.config.ts`) mit zwei Anmeldeschichten:
  nginx-Basic-Auth (`GZ_VALIDATOR_USER/PASS`) plus App-Login (`GZ_AUTH_USER/PASS`).
  `frontend/e2e/prodUrlGuard.ts` blockt Prod-Ziele fail-closed.
- **CI-Ratsche** `.github/ci_e2e_specs.txt` (167 Z.): Positivliste; `*.staging.spec.ts` ist per
  Filter A ausgeschlossen — der Staging-Nachweis läuft also über `/e2e-verify`, nicht über die CI.

## Dependencies

- **Upstream:** SvelteKit-Modul `$service-worker` (liefert `build`, `files`, `prerendered`,
  `version`) · `adapter-node`-Build-Output · nginx-Auslieferung der `static/`-Dateien.
- **Downstream:** Jede Seite der App läuft künftig durch den Service Worker. Scheibe 4 (#2131,
  Offline-Ansicht mit Stand-Kennzeichnung) baut direkt auf dieser Bauform auf.

## Existing Specs / ADRs

- **ADR-0020** — `node:test` ist der kanonische Frontend-Unit-Test-Runner (kein vitest).
- **ADR-0061** (neu, entsteht in dieser Scheibe) — PWA-Grundsatz: Service-Worker-Bauform,
  Caching-Regeln, Update-Verhalten. Im Epic #2127 ausdrücklich als Pflicht benannt.
- Keine bestehende Spec unter `docs/specs/modules/` berührt Frontend-Auslieferung oder Caching.

## Verbindliche Vorgaben aus Epic #2127

1. **Offline-Anzeige trägt ihren Stand.** In dieser Scheibe wird noch *kein* Inhalt offline
   ausgeliefert — genau deshalb darf hier auch kein HTML-Dokument zwischengespeichert werden.
2. **Gerätespeicher ist mandantengetrennt** (ADR-0003). Der Service Worker darf keine
   nutzerbezogenen Antworten ablegen, sonst sieht der nächste Nutzer desselben Geräts fremde Daten.
3. **Kein neuer Zustellweg** — keine Push-Benachrichtigungen.
4. **Update erst fragen** — kein automatisches `skipWaiting`.

## Risks & Considerations

- **R1 — SSR ohne Netz liefert gar nichts.** Mit `adapter-node` entsteht jedes HTML-Dokument am
  Server. `$service-worker.build`/`files` enthalten nur Client-Bündel und `static/`-Dateien, kein
  HTML. Die Offline-Seite muss deshalb eine eigenständige, vorab abgelegte Datei sein
  (`frontend/static/offline.html` mit eigenem Inline-CSS) — eine Svelte-Route würde ohne Netz
  nicht rendern und liefe zusätzlich in den Auth-Guard.
- **R2 — `cache-control: no-cache` auf HTML** (`hooks.server.ts:10-12`) ist bereits die richtige
  Vorgabe und darf nicht angetastet werden; der Service Worker muss sie fortschreiben, nicht
  unterlaufen.
- **R3 — Datenantworten dürfen nicht in den Speicher.** `/api/*` muss ausdrücklich am
  Service Worker vorbeigehen. Das ist die Stelle, an der Leitsatz 1 und 2 kippen könnten.
- **R4 — Abmelden muss den Speicher leeren.** Sobald ein Service Worker existiert, überlebt er den
  Nutzerwechsel. Auch wenn diese Scheibe nur Programmdateien ablegt: der Räum-Weg gehört hier
  eingezogen, nicht erst in Scheibe 4.
- **R5 — Schrift-Dateien sind Binärdateien im Repo.** Inter Tight und JetBrains Mono stehen unter
  der SIL Open Font License, Selbsthosten ist erlaubt; Lizenztext muss mitgeliefert werden.
  Auf `latin` beschnittene woff2 je Schnitt ≈ 20–30 KB, 7 Schnitte ≈ 150–200 KB.
- **R6 — Ein defekter Service Worker ist zäh.** Er überlebt Neuladen und kann eine kaputte Version
  festhalten. Es braucht einen verlässlichen Ausstieg (Abmelden räumt, Versionsname im Cache).
- **R7 — iOS ist nicht automatisiert prüfbar.** „Teilen → Zum Home-Bildschirm" lässt sich weder in
  Playwright noch sonst automatisiert nachstellen. Der Hinweis dafür ist eine UI-Komponente und
  muss als solche geprüft werden; das tatsächliche Installieren bleibt ein Handgriff des PO.
- **R8 — Erstmals etwas app-weit im Layout.** Der Update-Hinweis ist die erste global eingehängte
  Komponente. Er darf die Chrome-Steuerung in `+layout.svelte:63-100` nicht stören (Login-Seite und
  `_design`-Showcase rendern ohne Chrome).
- **R9 — LoC.** Über dem 250-Zeilen-Limit; Anhebung auf 500 ist im Issue eingeplant
  (`workflow.py set-field loc_limit_override 500`). Font-Dateien zählen als Assets nicht mit.

---

## Analysis

### Type

Feature (Scheibe 1 von Epic #2127). Kein Bug — die Fähigkeit existiert schlicht noch nicht.

### Nachgemessene Befunde (gegen `frontend/node_modules`, SvelteKit 2.70.1 / adapter-node 5.5.4)

**B1 — SvelteKit registriert den Service Worker selbst.** `config.kit.serviceWorker.register` ist
per Default `true` (`@sveltejs/kit/src/core/config/options.js:322-323`); beim SSR-Rendern jeder
Seite wird ein Registrierungs-Script injiziert
(`@sveltejs/kit/src/runtime/server/page/render.js:554-576`), der gebaute Worker liegt unter
`/service-worker.js` (`@sveltejs/kit/src/exports/vite/index.js:1275`). Das gilt **auch im
Entwicklungs- und Vorschaubetrieb**, nicht nur in Produktion. Ein eigenes
`navigator.serviceWorker.register(...)` im App-Code wäre eine Doppelregistrierung und ist verboten.
`$service-worker` exportiert `base`, `build`, `files`, `prerendered`, `version`
(`@sveltejs/kit/types/index.d.ts:3935-3959`).

**B2 — R1 bestätigt.** adapter-node baut die Kette
`sequence([serve(client, true), serve_prerendered(), ssr])`
(`@sveltejs/adapter-node/files/handler.js:1489-1492`). Der `sirv`-Static-Handler steht **vor** `ssr`,
und `ssr` (`handler.js:1350-1414`) ist der einzige Ort, der `server.respond` und damit
`hooks.server.ts:handle` aufruft. Eine Datei aus `static/` erreicht den Auth-Guard also nie.
→ `frontend/static/offline.html` ist der richtige Weg; eine Svelte-Route wäre es nicht.

**B3 — Schnitte bestätigt.** Im Frontend kommen nur `font-weight` 400/500/600/700 vor; für
JetBrains Mono ist kein 700 nachweisbar. Die sieben Schnitte aus dem Issue stimmen.

**B4 — Playwright bekommt einen aktiven Service Worker.** `frontend/e2e/start-preview.sh` fährt
einen echten Produktionsbau; wegen B1 wird der Worker in jeder getesteten Seite registriert.
Playwright kennt dafür die Kontext-Option `serviceWorkers: 'block'`. Bestehende Suiten müssen
blockieren, nur die neuen PWA-Prüfungen laufen mit aktivem Worker.

**B5 — `data-sveltekit-preload-data="hover"`** (`app.html:17`) löst Datenabrufe schon beim
Überfahren aus. Die `/api/*`-Ausnahme im Worker muss diese Anfragen genauso erfassen — sonst wäre
gerade der nutzerbezogene Abruf die anfälligste Stelle für eine versehentliche Ablage.

### Technical Approach

**Vier Regeln im `fetch`-Handler**, nach Anfrageart getrennt:

1. **Programmdateien** (`build` + `files` aus `$service-worker`): beim `install` vollständig
   ablegen, danach Cache-first. Cache-Name trägt `version`; im `activate` werden alle anderen
   Cache-Namen entfernt.
2. **Seitenaufrufe** (`request.mode === 'navigate'`): ausschließlich aus dem Netz, **nie** ablegen.
   Schlägt der Abruf fehl → `offline.html` aus dem Cache. Damit bleibt `cache-control: no-cache`
   aus `hooks.server.ts:10-12` unangetastet (R2).
3. **`/api/*`**: der Worker fasst diese Anfragen gar nicht an — früher `return` ohne
   `respondWith`, der Browser holt selbst. Kein Lesen, kein Schreiben, keine Ausnahme (R3, ADR-0003).
4. **Alles Übrige** (Icons, Manifest, Schriften): fällt über `files` unter Regel 1.

**Update erst auf Nachfrage:** kein `skipWaiting` im `install`. Der Client hört `updatefound` →
`statechange` auf `installed` **und** vorhandenem `controller` (sonst wäre es die Erstinstallation)
→ zeigt den Hinweis. Auf Antippen `registration.waiting.postMessage({type:'SKIP_WAITING'})`;
der Worker ruft daraufhin `self.skipWaiting()`. Der Client lädt bei `controllerchange` einmalig neu
(Mehrfach-Schutz nötig).

**Einhängepunkt:** in `+layout.svelte` als Geschwister **außerhalb** des
`{#if isLogin || isShowcase}`-Blocks (`+layout.svelte:71-100`). Was dort fehlen soll, ist die
Navigations-Chrome — ein Systemhinweis gehört auch auf der Anmeldeseite hin (R8). Optik über die
vorhandene `Toast.svelte` (`kind="info"`, Props `action`/`onaction` sind bereits da).

**Räumen beim Abmelden (R4) — abweichend von der Bewertung.** Der Vorschlag, beim Betreten der
Anmeldeseite bedingungslos zu räumen, ist nicht tragfähig: auf `/login` landet auch, wessen Sitzung
nur abgelaufen ist oder wer die Seite schlicht aufruft (`hooks.server.ts:20-21`). Jeder solche
Besuch würde den Speicher leeren und die Offline-Fähigkeit systematisch zerstören; beim allerersten
Besuch käme das Räumen zudem mit der laufenden Erstregistrierung ins Gehege. Stattdessen setzen die
beiden Abmelde-Wege ein ausdrückliches Merkmal, und nur darauf wird geräumt:

- `frontend/src/routes/logout/+page.server.ts:16` — `redirect(302, '/login')` → mit Merkmal.
- `frontend/src/routes/account/+page.svelte:309` — „Auf allen Geräten abmelden", `window.location.href`
  → dasselbe Merkmal.

Die Anmeldeseite räumt dann Caches und Worker-Registrierung. Beim nächsten Aufruf registriert
SvelteKit neu (B1), `install` füllt frisch — ein sauberer Zustand statt eines leeren Speichers
hinter einem aktiven Worker.

**Maskable-Icon muss erzeugt werden.** `favicon-512.png` ist randfüllend (Motiv bis Unterkante und
Seiten, Hintergrund durchgehend `#f6f4ee`, kein Alpha). Als `maskable` deklariert würde Android
Bergspitzen und Fußpunkte wegschneiden. Es braucht eine zweite Datei mit demselben Motiv in der
Schutzzone. Pillow 12.2 ist auf dem Server vorhanden.

### Affected Files

| Datei | Art | Beschreibung |
|---|---|---|
| `frontend/src/service-worker.ts` | CREATE | Die vier Regeln, Versionscache, `SKIP_WAITING`-Nachricht |
| `frontend/static/offline.html` | CREATE | Eigenständige Seite, Inline-CSS, ohne `app.css`/Schrift-Abhängigkeit |
| `frontend/src/lib/pwa/serviceWorkerUpdate.ts` | CREATE | Kapselung des Update-Ablaufs (prüfbar ohne Layout) |
| `frontend/src/routes/+layout.svelte` | MODIFY | Update-Hinweis app-weit einhängen |
| `frontend/src/routes/login/+page.svelte` | MODIFY | Räumen, nur bei gesetztem Abmelde-Merkmal |
| `frontend/src/routes/logout/+page.server.ts` | MODIFY | Abmelde-Merkmal im Redirect |
| `frontend/src/routes/account/+page.svelte` | MODIFY | Abmelde-Merkmal beim Abmelden auf allen Geräten |
| `frontend/src/app.html` | MODIFY | Google-Fonts raus; `theme-color`, `apple-mobile-web-app-*` rein |
| `frontend/src/app.css` | MODIFY | Sieben `@font-face` |
| `frontend/static/site.webmanifest` | MODIFY | `id`, `scope`, `purpose: maskable` |
| `frontend/static/fonts/*.woff2` + `LICENSE.txt` | CREATE | Assets, zählen nicht als LoC |
| `frontend/static/icon-maskable-512.png` | CREATE | Asset |
| `frontend/e2e/pwa-*.spec.ts` (+ Staging-Variante) | CREATE | Nachweis |
| `frontend/playwright.config.ts` | MODIFY | `serviceWorkers: 'block'` für Bestandssuite |
| `docs/adr/0061-pwa-service-worker-bauform.md` | CREATE | Grundsatz-ADR (Pflicht laut Epic) |

### Scope Assessment

- Dateien: 15 (7 CREATE Code/Doku, 6 MODIFY, Assets separat)
- Geschätzte LoC: **+300 bis +430** — innerhalb des angehobenen Limits von 500
- Risiko: **MITTEL** — nicht wegen Umfang, sondern weil ein fehlerhafter Worker zäh ist (R6),
  `+layout.svelte` erstmals eine app-weite Nebenwirkung bekommt (R8) und die `/api/*`-Grenze (R3)
  Mandantentrennung berührt

### Open Questions

Keine blockierenden. Die Wortlaute der Offline-Seite und des Update-Hinweises schlage ich in der
Spec vor; sie sind Teil der Akzeptanzkriterien und damit freigabepflichtig.
