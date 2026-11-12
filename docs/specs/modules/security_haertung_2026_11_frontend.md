---
entity_id: security_haertung_2026_11_frontend
type: module
created: 2026-11-12
updated: 2026-11-12
status: approved
version: "1.0"
tags: [security, frontend, pwa, csp, issue-2961]
---

# Sicherheits-Härtung Frontend (Review 2026-11)

## Approval

- [x] Approved — PO-Auftrag vom 2026-11-12 („alle Befunde beheben, ohne Rückfragen"), Issue #2961.
  Der Auftrag ist die Vorgabe; diese Spec hält Umfang und Akzeptanzkriterien fest.

## Purpose

Das SvelteKit-Frontend behandelt Nutzereingaben, Sitzungen und den Offline-Speicher so, dass
Inhalte immer als Text erscheinen, Anfragen an die Go-API nur geprüfte Pfade und Kopfzeilen
tragen, der Browser eine Sicherheitsrichtlinie durchsetzt und der Offline-Speicher streng je
Nutzer und zeitlich begrenzt bleibt. Testläufe gegen Staging arbeiten nur mit Zugangsdaten aus
der Umgebung.

## Source

- **Dateien:** `frontend/src/lib/utils/kartenPopup.ts`, `frontend/src/lib/server/apiPfad.ts`,
  `frontend/src/routes/api/[...path]/+server.ts`, `frontend/src/lib/pwa/datenspeicher.ts`,
  `frontend/src/service-worker.ts`, `frontend/src/lib/api.ts`, `frontend/src/hooks.server.ts`,
  `frontend/svelte.config.js`, `frontend/src/lib/auth.ts`, `frontend/e2e/stagingZugang.ts`
- **Schicht:** ausschließlich Frontend (SvelteKit-Server und Browser). Go-API und Python-Core
  sind nicht Teil dieser Spec (eigene Pakete aus demselben Review).

> **Querschnitts-Prüfpunkte:** Trip/Ortsvergleich-Teilung — keine neue einseitige Komponente;
> die Sprechblasen-Funktion ist ein neutraler Baustein unter `lib/utils/`, die Kennungsprüfung
> gilt für Trip und Vergleich gleich. Mandantentrennung — der Offline-Speicher wird mit zwei
> Nutzern im Browser geprüft. Kanäle — nicht betroffen (kein Briefing-/Alarm-Inhalt).

## Estimated Scope

- **LoC:** ~600 Produktivcode + Tests (über dem Standardlimit; Sicherheitspaket mit acht Befunden,
  Override durch den Auftrag)
- **Files:** ~25 Produktivdateien, dazu ~70 Staging-Playwright-Dateien (mechanische Umstellung)
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/store/pathsafe.go` (`ValidEntityIDRe`) | Go (nur gelesen) | kanonisches Kennungsmuster |
| ADR-0061 / ADR-0063 | ADR | Bauform Service Worker, Offline-Inhalte, Mandanten-Bucket |
| `pwa_installierbar_offline_start.md`, `pwa_offline_ansicht_letzter_stand.md` | Spec | Offline-Verhalten, angepasst |
| `docs/reference/operations_playbook.md` „Zugangsdaten: DREI Quellen" | Doku | Herkunft der Staging-Zugangsdaten |

## Implementation Details

1. **Karten-Sprechblase:** `popupKnoten()` erzeugt einen DOM-Knoten, Text nur über
   `textContent`; `MapCanvas.svelte` übergibt ihn an `bindPopup`. Weitere Leaflet-Senken mit
   Zeichenketten (Tooltip, `setContent`, `divIcon`, eigene Steuerelemente) gibt es im Code nicht.
2. **Kennungen zur Go-API:** `kennungImPfad()` prüft gegen das Go-Muster und kodiert als genau
   ein Pfadsegment; Trip-Ansicht, Vergleichs-Ansicht und Trip-Vorlage (`?from=`) nutzen es
   (ungültig ⇒ 404 bzw. keine Vorlage). Die Vergleichs-Vorlage war bereits kodiert und bleibt
   unverändert. Bearbeiten-Umleitungen kodieren Kennung und Reiter.
3. **Durchreicher `/api/[...path]`:** Segmente einzeln dekodiert, geprüft (leer, `.`, `..`,
   Trenner, NUL, nicht dekodierbar ⇒ 400 ohne Aufruf der Go-API) und neu kodiert. Weitergereicht
   werden nur `Content-Type`, `Accept`, `Accept-Language`, `If-Match` (Konfliktschutz der
   Speicherung) und `X-Real-IP` (wie die übrigen Server-Routen), als Cookie nur `gz_session`.
4. **Sicherheits-Kopfzeilen und CSP:** `hooks.server.ts` setzt auf jede Antwort
   `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options`, `Permissions-Policy`.
   `kit.csp` (Modus `auto`) setzt die Richtlinie für Seitenantworten; das Kopf-Skript aus
   `app.html` bekommt seinen Hash beim Bauen aus der Datei. `offline.html` ohne Inline-Handler
   (`static/offline.js`).
5. **Signaturvergleich:** `crypto.timingSafeEqual`, ungleiche Länge ⇒ ungültig.
6. **Secure-Cookie:** `NODE_ENV === 'production'` oder `url.protocol === 'https:'`.
7. **Entwickler-Vorschau:** `/email-preview-dev` nicht mehr in der Liste öffentlicher Pfade.
   Die Route selbst bleibt vorerst: `e2e/email-preview-header.spec.ts` (CI-Positivliste)
   verweist noch darauf; ohne Entwicklungsmodus leitet sie ohnehin auf `/` um.
8. **Offline-Speicher** (`lib/pwa/datenspeicher.ts`, `service-worker.ts`, `lib/api.ts`,
   Anmeldeseite): fremde `gz-daten-*` fallen bei jeder same-origin-Antwort mit
   Mandantenkennung; gelesen wird nur aus dem einzigen verbliebenen Speicher (mehrere ⇒ keiner);
   Höchstalter 30 Tage über einen Ablagezeitpunkt je Antwort (Bestand ohne Zeitpunkt: Stand der
   Ansicht); echtes 401 räumt `gz-daten-*` vor der Umleitung; `/login?abgemeldet=1` räumt nur,
   wenn die Go-API keine Sitzung mehr bestätigt.
9. **Staging-Zugangsdaten:** `e2e/stagingZugang.ts` (`ausUmgebung`, `wegwerfPasswort`) ersetzt
   alle Rückfall-Werte in Staging-Specs, -Setups und -Configs. Der isolierte CI-Stack bleibt.

## Expected Behavior

- **Input:** Nutzereingaben (Wegpunktnamen, Kennungen in Adressen), Browser-Anfragen an den
  Durchreicher, Antworten der Go-API (401), Seitenaufrufe mit Service Worker.
- **Output:** Text statt Auszeichnung, geprüfte Pfade, Sicherheits-Kopfzeilen und Richtlinie,
  mandantenreiner und zeitlich begrenzter Offline-Speicher.
- **Side effects:** Staging-Playwright-Läufe brauchen die Zugangsdaten als Umgebungsvariablen.

## Acceptance Criteria

- **AC-1:** Given ein Wegpunkt, dessen Name HTML-Auszeichnung enthält (z. B. aus einer GPX-Datei) / When der Nutzer auf der Karte den Marker öffnet / Then zeigt die Sprechblase den Namen wörtlich als Text, und es entsteht kein Element und keine Skriptausführung aus dem Namen.
  - Test: `frontend/e2e/karte-wegpunktname-als-text.spec.ts` (echtes Leaflet), Logiktest `frontend/src/lib/utils/kartenPopup.test.ts`.

- **AC-2:** Given eine Trip- oder Vergleichs-Adresse bzw. `?from=` mit einer Kennung, die Abfrage-, Anker- oder Pfadzeichen enthält / When der Frontend-Server die Go-API fragt / Then steht die Kennung kodiert als genau ein Pfadsegment im Pfad, und eine Kennung außerhalb des Zulassungsmusters führt ohne Anfrage zu 404 bzw. zu keiner Vorlage.
  - Test: `frontend/src/lib/server/__tests__/apiPfad.test.ts`, `frontend/src/routes/api/[...path]/__tests__/durchreicher_pfad_und_kopfzeilen.test.ts` (echter lokaler HTTP-Server).

- **AC-3:** Given eine Browser-Anfrage an `/api/…` / When ein Pfadsegment leer, `.`/`..`, nicht dekodierbar ist oder kodiert einen Trenner enthält / Then antwortet der Durchreicher 400 und die Go-API erhält nichts; bei gültigem Pfad erhält sie nur die Kopfzeilen der Positivliste und als Cookie nur die Sitzung.
  - Test: wie AC-2 (Durchreicher gegen echten HTTP-Server).

- **AC-4:** Given eine beliebige Antwort des Frontend-Servers / When der Browser sie lädt / Then trägt sie die Sicherheits-Kopfzeilen, jede Seitenantwort trägt die Content-Security-Policy, und auf Anmeldung, Startseite, Trip-Liste, Konto, Trip-Detail mit Karte, Vergleich und Alarm-Vorschau meldet der Browser keine Verletzung.
  - Test: `frontend/src/hooks.server.sicherheitskopfzeilen.test.ts`, `frontend/e2e/sicherheitsrichtlinie-ohne-verletzung.spec.ts` (mit Positivkontrolle).

- **AC-5:** Given ein Anmelde-Merkmal mit falscher, verkürzter oder verlängerter Signatur / When der Frontend-Server es prüft / Then gilt es als ungültig, der Vergleich läuft in konstanter Zeit und wirft bei ungleicher Länge keine Ausnahme.
  - Test: `frontend/src/lib/auth_signaturvergleich.test.ts`.

- **AC-6:** Given eine Anmeldung per Passwort oder Code über HTTPS ohne `NODE_ENV=production` / When der Server das Sitzungs- und das Sprach-Cookie setzt / Then tragen beide das Secure-Flag; mit `NODE_ENV=production` bleibt es wie bisher gesetzt.
  - Test: `frontend/src/routes/login/__tests__/login_reicht_sprach_cookie_weiter.test.ts`, `frontend/src/routes/magic-link/verify/__tests__/anmelde_cookie_secure.test.ts`.

- **AC-7:** Given ein Besucher ohne Sitzung / When er `/email-preview-dev` aufruft / Then leitet der Server auf die Anmeldung um, ohne die Seite aufzulösen.
  - Test: `frontend/src/hooks.server.entwickler_vorschau_nicht_oeffentlich.test.ts`.

- **AC-8:** Given Nutzer A hat Ansichten offline abgelegt und Nutzer B meldet sich auf demselben Gerät an / When B die erste Seite öffnet, auch eine, die selbst nie abgelegt wird (Startseite) / Then ist As Inhaltsspeicher gelöscht.
  - Test: `frontend/e2e/pwa-offline-sperre-und-mandant.spec.ts` („#2961 AC-8"), Logiktest `frontend/src/lib/pwa/__tests__/datenspeicher_mandant_und_hoechstalter.test.ts`.

- **AC-9:** Given auf dem Gerät liegen ausnahmsweise Inhaltsspeicher zweier Nutzer / When die App ohne Netz eine Ansicht oder die Offline-Übersicht ausliefert / Then liefert sie aus keinem der beiden; sonst nur aus dem Speicher des zuletzt angemeldeten Nutzers.
  - Test: Logiktest wie AC-8.

- **AC-10:** Given eine offline vorgehaltene Ansicht, deren Ablage mehr als 30 Tage zurückliegt / When der Worker aktiviert wird oder die Ansicht bzw. die Offline-Übersicht abgerufen wird / Then wird sie entfernt und nicht mehr ausgeliefert; jüngere bleiben.
  - Test: Logiktest wie AC-8.

- **AC-11:** Given ein angemeldeter Nutzer mit Offline-Inhalten / When die Go-API eine Anfrage mit 401 beantwortet / Then sind die Inhaltsspeicher gelöscht, bevor auf die Anmeldung umgeleitet wird, Programmdateien und Worker bleiben; ein Netzfehler oder ein 503 löscht nichts.
  - Test: `frontend/src/lib/__tests__/api_401_raeumt_inhaltsspeicher.test.ts`.

- **AC-12:** Given ein Nutzer mit gültiger Sitzung und Offline-Inhalten / When er einem Verweis auf `/login?abgemeldet=1` folgt / Then bleibt sein Offline-Speicher erhalten; nach echtem Abmelden (Sitzung beendet oder eigener Abmelde-Merker des Tabs) wird wie bisher geräumt.
  - Test: `frontend/src/routes/login/__tests__/abmelde_merkmal_nur_ohne_sitzung.test.ts`, `frontend/e2e/pwa-offline-sperre-und-mandant.spec.ts` („#2961 AC-12"); Bestand AC-11/AC-15 der PWA-Specs.

- **AC-13:** Given ein Playwright-Lauf gegen Staging ohne gesetzte Zugangsdaten-Variablen / When die Konfiguration oder ein Setup die Zugangsdaten braucht / Then bricht der Lauf mit einer Meldung ab, die die Variablen und ihre Quelle nennt; im Quelltext steht kein Staging-Passwort.
  - Test: `frontend/e2e/stagingZugang.test.ts`; Lauf `npx playwright test --config playwright.staging.config.ts --list` ohne Variablen bricht ab.

## Known Limitations

- **Kopfzeilen bei Umleitungen und statischen Dateien:** Eine im Hook geworfene Umleitung (z. B.
  auf `/login`) und von adapter-node direkt ausgelieferte Dateien aus `static/` und `_app/`
  laufen nicht durch `handle`; sie tragen die Sicherheits-Kopfzeilen nicht. In Produktion kann
  nginx sie zusätzlich setzen (außerhalb des Repos).
- **`offline.html`** wird vom Service Worker ohne Richtlinie ausgeliefert und behält ihr
  Inline-Kopf-Skript (Dunkel-Modus vor dem ersten Paint, `dark_mechanik.test.ts`); nur der
  Inline-Handler ist entfallen.
- **Kein Lesen bei zwei Inhaltsspeichern:** fällt aus, bis die nächste angemeldete Antwort
  den fremden Speicher räumt — bewusst fail-closed.
- **Bestand ohne Ablagezeitpunkt:** eine `__data.json` ohne eigene Ansicht in der Buchführung
  gilt als abgelaufen und wird beim ersten Zugriff entfernt.
- **Leaflet-Klick in Playwright:** ein Maus-Klick auf den Marker öffnete die Sprechblase im
  Test nicht; der Nachweis löst das Klick-Ereignis am Marker direkt aus.
- **Staging-Testkonten:** die bisher im Quelltext stehenden Passwörter selbst angelegter
  Staging-Konten sind öffentlich bekannt; die Konten sind zu löschen oder ihre Passwörter neu zu
  setzen und als Umgebungsvariable zu hinterlegen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0063 (Nachtrag 2026-11-12)
- **Rationale:** §4 sicherte das Räumen „bei jeder Antwort" zu, umgesetzt war es nur bei der
  Ablage; dazu kommen Höchstalter, Lesen nur aus dem aktuellen Speicher und Räumen bei 401 —
  Fortschreibung derselben Entscheidung, keine Ablösung.

## Changelog

- 2026-11-12: Spec angelegt (Issue #2961, PO-Auftrag Sicherheits-Härtung).
