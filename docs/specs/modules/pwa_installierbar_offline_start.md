---
entity_id: pwa_installierbar_offline_start
type: module
created: 2026-09-06
updated: 2026-09-06
status: draft
version: "1.0"
tags: [pwa, frontend, offline, service-worker, issue-2128, epic-2127]
---

# PWA: installierbar und ohne Netz startfähig

Issue #2128 · Scheibe 1 zu Epic #2127 · Workflow `feat-2128-pwa-installierbar`

## Approval

- [ ] Approved

## Purpose

Die Web-App liegt nach dieser Scheibe wie eine App auf dem Startbildschirm von Android und iOS,
zeigt ohne Netz eine eigene verständliche Seite statt der Browser-Fehlerseite, lädt ihre Schriften
selbst aus (kein Aufruf an Google mehr) und lädt ein Programm-Update erst, wenn der Nutzer es
antippt. Sie speichert dabei **keine** Inhalte — das kommt kontrolliert in Scheibe 4 (#2131).

## Source

- **File:** `frontend/src/service-worker.ts` (neu)
- **Identifier:** Service-Worker-Ereignisse `install` / `activate` / `fetch` / `message`
- **Schicht:** Frontend (SvelteKit) — kein Go-, kein Python-Anteil

## Estimated Scope

- **LoC:** ~300–430 (Limit für diesen Workflow auf 500 angehoben)
- **Files:** 15 (7 neu, 6 geändert, dazu Schrift- und Symbol-Dateien als Assets)
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `$service-worker` (SvelteKit 2.70) | Modul | liefert `build`, `files`, `version` für den Speicherinhalt |
| `@sveltejs/adapter-node` 5.5.4 | Auslieferung | beantwortet `static/`-Dateien vor der Anmelde-Weiche |
| `frontend/src/lib/components/mobile/Toast.svelte` | Komponente | vorhandene Hinweis-Optik für Update- und iOS-Hinweis |
| `frontend/src/hooks.server.ts` | Auth-Weiche | setzt `cache-control: no-cache` für HTML — bleibt unangetastet |
| ADR-0003 | Entscheidung | Mandantentrennung des Gerätespeichers |
| ADR-0020 | Entscheidung | Frontend-Unit-Tests laufen mit `node:test` |
| ADR-0061 (neu) | Entscheidung | PWA-Bauform, Speicherregeln, Update-Verhalten |

## Implementation Details

### Speicherregeln im Service Worker (vier Klassen)

```
install   → cache.addAll([...build, ...files])   Cache-Name: "gz-<version>"
activate  → alle Cache-Namen != "gz-<version>" löschen
fetch:
  1. url.pathname beginnt mit "/api/"   → return ohne respondWith (Browser holt selbst)
  2. request.mode === "navigate"        → nur Netz; bei Netzfehler caches.match("/offline.html")
                                          NIE caches.put()
  3. Treffer in build/files             → aus dem Speicher, sonst Netz
  4. alles Übrige                       → Netz, ohne Ablage
message: {type:"SKIP_WAITING"} → self.skipWaiting()
```

`self.skipWaiting()` steht **ausschließlich** im `message`-Zweig, niemals in `install`.

### Update erst auf Nachfrage

SvelteKit registriert den Worker selbst, sobald `frontend/src/service-worker.ts` existiert
(`config.kit.serviceWorker.register` = `true`). Eigener `navigator.serviceWorker.register(...)`-Code
ist verboten (Doppelregistrierung).

Der Ablauf liegt gekapselt in `frontend/src/lib/pwa/serviceWorkerUpdate.ts`:

```
registration.addEventListener("updatefound")
  → registration.installing.addEventListener("statechange")
     → state === "installed" UND navigator.serviceWorker.controller vorhanden
        → Hinweis anzeigen  (bei fehlendem controller: Erstinstallation, kein Hinweis)
Antippen → registration.waiting.postMessage({type:"SKIP_WAITING"})
navigator.serviceWorker "controllerchange" → einmalig location.reload() (Mehrfachschutz)
```

### Wortlaute

**Offline-Seite** (`frontend/static/offline.html`, eigenständig, Inline-CSS, keine Abhängigkeit von
`app.css` oder den Schriften):

> **Keine Verbindung**
> Gregor Zwanzig erreicht gerade das Netz nicht. Die App selbst liegt auf dem Gerät, die Inhalte
> kommen vom Server. Sobald wieder Empfang da ist, lädt die Seite normal.
> [ Erneut versuchen ]

**Update-Hinweis** (`Toast`, `kind="info"`):

> Neue Version verfügbar · *Wird erst auf Antippen geladen.* · [ Jetzt aktualisieren ]

**iOS-Installationshinweis** (einmalig, nur in Safari auf iOS und nur wenn die App nicht bereits
vom Startbildschirm läuft; schließbar, kehrt nach dem Schließen nicht wieder):

> Auf den Startbildschirm legen: unten „Teilen" antippen, dann „Zum Home-Bildschirm".

### Manifest (`frontend/static/site.webmanifest`)

Ergänzt werden `"id": "/"`, `"scope": "/"`, `"purpose": "any"` an den bestehenden Symbolen und ein
neues `icon-maskable-512.png` mit `"purpose": "maskable"`. `theme_color` und `background_color`
bleiben `#f6f4ee` — ein Akzentton in der Systemleiste widerspräche dem Leitprinzip „Akzentfarben
sparsam".

Das maskable Symbol entsteht aus `favicon-512.png`: dasselbe Motiv auf rund 60 % verkleinert und
mittig auf durchgehendes `#f6f4ee` gesetzt, damit der runde Zuschnitt unter Android weder Bergspitzen
noch Fuß abschneidet.

### Schriften

Sieben Schnitte als woff2 unter `frontend/static/fonts/`, auf `latin` beschnitten:
Inter Tight 400/500/600/700, JetBrains Mono 400/500/600. Einbindung per `@font-face` mit
`font-display: swap` in `frontend/src/app.css` (dort stehen bereits `--g-font-ui` und
`--g-font-data`). Die drei Zeilen `app.html:8-10` (Google-Fonts-Verweis und beide `preconnect`)
entfallen. Beide Schriften stehen unter der SIL Open Font License; der Lizenztext liegt als
`frontend/static/fonts/LICENSE.txt` bei. Über `$service-worker.files` landen die Dateien
automatisch im Speicher.

### Räumen beim Abmelden

Die beiden Abmelde-Wege setzen ein Merkmal, die Anmeldeseite räumt **nur darauf**:

- `frontend/src/routes/logout/+page.server.ts:16` — Ziel des Redirects trägt das Merkmal
- `frontend/src/routes/account/+page.svelte:309` — „Auf allen Geräten abmelden" ebenso
- `frontend/src/routes/login/+page.svelte` — bei gesetztem Merkmal: alle Caches löschen und
  `navigator.serviceWorker.getRegistrations()` → `unregister()`

Bedingungsloses Räumen beim Betreten der Anmeldeseite ist ausdrücklich **nicht** zulässig: dort
landet auch, wessen Sitzung abgelaufen ist oder wer die Seite schlicht aufruft — das würde die
Offline-Fähigkeit genau dann zerstören, wenn sie gebraucht wird.

## Expected Behavior

- **Input:** Seitenaufrufe, Datenabrufe und Ladevorgänge des Browsers, mit und ohne Netz.
- **Output:** Programmdateien aus dem Gerätespeicher; Seiten aus dem Netz oder — bei Netzfehler —
  die eigene Offline-Seite; Datenabrufe unverändert aus dem Netz.
- **Side effects:** Ein Service Worker ist nach dem ersten Besuch dauerhaft aktiv. Ein
  geräteweiter Merker hält fest, dass der iOS-Installationshinweis gesehen wurde (keine
  nutzerbezogene Angabe). Beim Abmelden werden Speicher und Worker abgeräumt.

## Acceptance Criteria

- **AC-1:** Given ein Gerät ohne installierte App / When der Nutzer die App im Browser öffnet und
  das Web-App-Manifest ausgewertet wird / Then enthält es `id`, `scope`, `start_url`, `display:
  standalone`, `theme_color`, `background_color` sowie mindestens ein Symbol mit `purpose: maskable`,
  und alle darin genannten Symboldateien sind tatsächlich abrufbar.
  - Test: Playwright ruft `/site.webmanifest` ab, prüft die Felder und ruft jede Symbol-URL auf
    (Status 200, Bildtyp).

- **AC-2:** Given das maskable Symbol / When es rund zugeschnitten wird, wie Android es tut / Then
  liegt das gesamte Bergmotiv innerhalb der Schutzzone und wird nicht angeschnitten.
  - Test: Der Bildinhalt wird geprüft — innerhalb des äußeren Randes (außerhalb der mittleren 80 %)
    findet sich ausschließlich die Hintergrundfarbe, kein Motivpixel.

- **AC-3:** Given ein erster Besuch mit Netz / When die Seite fertig geladen ist / Then ist ein
  Service Worker registriert und aktiv, und die Programmdateien der App liegen im Gerätespeicher
  unter einem Namen, der die Version trägt.
  - Test: Playwright wartet auf `navigator.serviceWorker.controller` und liest `caches.keys()`
    sowie die Anzahl der abgelegten Einträge aus.

- **AC-4:** Given eine App, die einmal mit Netz geladen wurde / When das Netz abgeschaltet ist und
  der Nutzer eine Seite der App aufruft / Then erscheint die eigene Offline-Seite mit der Überschrift
  „Keine Verbindung" und einer Schaltfläche „Erneut versuchen" — nicht die Fehlerseite des Browsers.
  - Test: Playwright setzt den Kontext auf offline, navigiert und prüft den sichtbaren Text.

- **AC-5:** Given die App wird geladen / When der Netzwerkverkehr des Ladevorgangs betrachtet wird /
  Then geht keine einzige Anfrage an `fonts.googleapis.com` oder `fonts.gstatic.com`, und die
  Schriften Inter Tight und JetBrains Mono werden aus dem eigenen Verzeichnis geliefert.
  - Test: Playwright zeichnet alle Anfragen auf und prüft, dass kein Fremd-Host vorkommt und
    mindestens eine woff2-Datei vom eigenen Host geladen wurde.

- **AC-6:** Given ein angemeldeter Nutzer / When die App Daten über `/api/...` abruft — auch durch
  den Vorabruf beim Überfahren von Verweisen / Then landet keine einzige `/api/`-Antwort im
  Gerätespeicher.
  - Test: Playwright durchklickt die App inklusive Hover über Navigationsverweise und prüft
    anschließend jeden Eintrag in jedem Cache darauf, dass keine URL `/api/` enthält.

- **AC-7:** Given ein beliebiger Seitenaufruf / When er erfolgreich aus dem Netz beantwortet wurde /
  Then liegt danach kein HTML-Dokument im Gerätespeicher.
  - Test: Playwright prüft nach mehreren Seitenwechseln, dass kein Cache-Eintrag den Inhaltstyp
    `text/html` trägt — mit Ausnahme der Offline-Seite.

- **AC-8:** Given eine laufende App und eine neue Programmversion auf dem Server / When der Browser
  die neue Version bemerkt / Then erscheint der Hinweis „Neue Version verfügbar", die App arbeitet
  unverändert mit der installierten Version weiter, und es wird nichts umgeschaltet.
  - Test: Playwright löst einen Versionswechsel aus, prüft das Erscheinen des Hinweises und dass
    der bisherige Worker weiterhin die Kontrolle hat.

- **AC-9:** Given ein sichtbarer Update-Hinweis / When der Nutzer „Jetzt aktualisieren" antippt /
  Then übernimmt die neue Version die Kontrolle und die Seite lädt genau einmal neu.
  - Test: Playwright klickt die Schaltfläche und prüft den Wechsel der Kontrolle sowie genau einen
    Neuladevorgang.

- **AC-10:** Given eine neue Version wartet und der Nutzer tippt den Hinweis nicht an / When er
  weiter in der App arbeitet / Then bleibt die installierte Version aktiv, und es wird keine
  Programmdatei der neuen Version nachgeladen.
  - Test: Playwright wartet nach dem Erscheinen des Hinweises, navigiert weiter und prüft, dass die
    Kontrolle beim alten Worker bleibt.

- **AC-11:** Given ein angemeldeter Nutzer mit gefülltem Gerätespeicher / When er sich abmeldet —
  über die Seitenleiste oder über „Auf allen Geräten abmelden" / Then ist der Gerätespeicher leer und
  kein Service Worker mehr registriert.
  - Test: Playwright meldet sich über beide Wege ab und liest jeweils `caches.keys()` und
    `navigator.serviceWorker.getRegistrations()` aus.

- **AC-12:** Given ein angemeldeter Nutzer mit gefülltem Gerätespeicher / When die Anmeldeseite ohne
  vorangegangenes Abmelden erreicht wird — etwa durch direkten Aufruf oder abgelaufene Sitzung /
  Then bleiben Gerätespeicher und Service Worker unangetastet.
  - Test: Playwright ruft die Anmeldeseite direkt auf und prüft, dass die Cache-Einträge unverändert
    vorhanden sind. (Gegenprobe zu AC-11 — ohne sie wäre AC-11 auch durch bedingungsloses Räumen
    erfüllbar.)

- **AC-13:** Given eine neue Programmversion hat die Kontrolle übernommen / When der Gerätespeicher
  betrachtet wird / Then existiert nur noch der Speicher der neuen Version; die Speicher aller
  vorherigen Versionen sind entfernt.
  - Test: Playwright liest `caches.keys()` nach dem Versionswechsel aus und erwartet genau einen
    Eintrag.

- **AC-14:** Given ein Gerät, dessen Zwischenspeicher vom Betriebssystem geleert wurde, während die
  App installiert bleibt / When der Nutzer die App mit Netz öffnet / Then startet sie normal und
  füllt den Speicher neu, ohne Fehlermeldung.
  - Test: Playwright löscht alle Caches bei aktivem Worker, lädt neu und prüft, dass die App
    erscheint und die Einträge wieder vorhanden sind.

- **AC-15:** Given Safari auf iOS und eine noch nicht installierte App / When der Nutzer die App
  öffnet / Then erscheint einmalig der Hinweis, wie man sie über „Teilen" auf den Startbildschirm
  legt; nach dem Schließen erscheint er nicht erneut, und wenn die App bereits vom Startbildschirm
  läuft, erscheint er gar nicht.
  - Test: Playwright fährt den Fall mit iOS-Safari-Kennung und prüft Erscheinen, Nichtwiederkehr
    nach dem Schließen sowie das Ausbleiben im Startbildschirm-Betrieb.

- **AC-16:** Given die bestehende Playwright-Prüfstrecke / When sie nach dieser Änderung läuft /
  Then bleibt sie vollständig grün, weil der Service Worker für die Bestandsprüfungen abgeschaltet
  ist und nur die neuen PWA-Prüfungen mit aktivem Worker laufen.
  - Test: Die in `.github/ci_e2e_specs.txt` geführte Strecke läuft unverändert grün durch.

## Known Limitations

- Es werden **keine Inhalte** offline verfügbar — nur die Programmdateien. Wer ohne Netz eine Seite
  aufruft, sieht die Offline-Seite, nicht das zuletzt gelesene Briefing. Das ist Scheibe 4 (#2131).
- Das tatsächliche Installieren auf einem echten iPhone lässt sich nicht automatisiert nachweisen.
  AC-15 prüft den Hinweis, nicht den Handgriff des Nutzers; das Installieren selbst bleibt ein
  manueller Nachweis des PO.
- Wer sich vorher im Browser angemeldet hat, muss sich in der installierten App unter Umständen
  einmalig erneut anmelden — die installierte App kann auf iOS einen eigenen Speicher führen. Mit
  der unbefristeten Anmeldung aus Scheibe 2 (#2129, bereits geliefert) bleibt es bei diesem einen Mal.
- Der Merker für den iOS-Hinweis liegt geräteweit, nicht je Nutzer. Er enthält keine
  nutzerbezogene Angabe, verletzt also die Mandantentrennung nicht, ist aber auch nicht je Nutzer
  getrennt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0061 (neu) — „PWA-Bauform: handgeführter Service Worker, Speicherregeln,
  Update erst auf Nachfrage"
- **Rationale:** Im Epic #2127 ausdrücklich als Pflicht benannt. Festzuhalten sind: der bewusste
  Verzicht auf `vite-plugin-pwa`/Workbox (deren Automatik legt Datenantworten mit ab — genau das,
  was Leitsatz 1 und die Mandantentrennung verbieten), die vier Speicherregeln mit der harten
  `/api/`-Grenze, der Verzicht auf automatisches `skipWaiting`, und dass Inhalte erst in Scheibe 4
  offline verfügbar werden.

## Changelog

- 2026-09-06: Initial spec created (Issue #2128, Scheibe 1 zu Epic #2127)
