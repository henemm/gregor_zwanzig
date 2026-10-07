---
entity_id: oeffentliche_startseite_2520
type: module
created: 2026-10-07
updated: 2026-10-07
status: draft
version: "1.0"
tags: [frontend, landing, startseite, i18n, textkatalog, auth, pwa, issue-2520]
---

# Öffentliche Startseite für nicht eingeloggte Besucher

## Approval

- [ ] Approved

## Purpose

Wer nicht eingeloggt ist, soll vor der Registrierung verstehen, was Gregor Zwanzig ist, was bei ihm ankommt (Briefing morgens/abends, Alarme) und warum das unterwegs nützt (unvorhersehbare Empfangslage, jeder Kanal beantwortet jede Frage). Dazu zeigt `/` Ausgeloggten eine öffentliche Startseite mit statischen Screenshots und Links zu Registrieren und Login; Eingeloggte sehen unverändert das Cockpit. Issue #2520. Legt außerdem den typisierten Textkatalog an, den #2521 mitnutzt.

## Source

- **File:** `frontend/src/hooks.server.ts`, `frontend/src/routes/+page.server.ts`, `frontend/src/routes/+page.svelte`, `frontend/src/routes/+layout.svelte`, `frontend/src/routes/_start/Startseite.svelte` (neu), `frontend/src/lib/i18n/index.ts` (neu), `frontend/src/lib/i18n/messages/de.json` (neu), `frontend/static/landing/` (neu)
- **Identifier:** `handle` (erweitert), `load` in `+page.server.ts` (erweitert), `Startseite`, `t(key)`, `MessageKey`

> **Schicht-Hinweis:** Reines SvelteKit-Frontend. Kein Go-, kein Python-Code, keine neue Abhängigkeit. Die Startseite besteht aus Atoms/Molecules (Card, Btn, Eyebrow, Wordmark); sie ist kein neuer geteilter Editor-Baustein, daher greift die Trip/Ortsvergleich-Pendant-Regel nicht.

## Estimated Scope

- **LoC:** ca. 250-330 Code ohne Tests und ohne Katalog-/Asset-Inhalt (hooks ~15, Loader ~8, Layout ~3, Startseite ~170, i18n-Modul ~30, `de.json` ~60 Zeilen). Das kann das Workflow-Limit von 250 LoC berühren: bei Bedarf `workflow.py set-field loc_limit_override 500`.
- **Files:** 8 Code-/Katalogdateien plus 3-4 Screenshot-Assets und Tests
- **Effort:** medium

### Betroffene Dateien

| Datei | Änderung | Beschreibung |
|-------|----------|--------------|
| `frontend/src/hooks.server.ts` | MODIFY | Nur exakt `/` lässt Ausgeloggte durch (kein Redirect, kein Mandant-Header); alle anderen geschützten Pfade leiten unverändert auf `/login` |
| `frontend/src/routes/+page.server.ts` | MODIFY | Ohne `locals.userId` sofort `{ oeffentlich: true, trips: [], presets: [], cockpitStatus: null }` zurückgeben, keine Aufrufe an die Go-API |
| `frontend/src/routes/+page.svelte` | MODIFY | Verzweigt: `data.oeffentlich` → `Startseite`, sonst Cockpit unverändert |
| `frontend/src/routes/+layout.svelte` | MODIFY | App-Chrome (Sidebar/TopBar/BottomNav) auf `/` ausblenden, wenn kein Nutzer angemeldet ist |
| `frontend/src/routes/_start/Startseite.svelte` | CREATE | Sektionen: Was ist Gregor Zwanzig, Was kommt an, Warum nützt es; Links Registrieren/Login |
| `frontend/src/lib/i18n/index.ts` | CREATE | `t(key: MessageKey)`; Typ `MessageKey = keyof typeof de` |
| `frontend/src/lib/i18n/messages/de.json` | CREATE | Flache Schlüssel, kompatibel zu inlang/Paraglide; enthält alle Startseitentexte inkl. Alt-Texte |
| `frontend/static/landing/*.png` | CREATE | Statische Screenshots (Briefing-Mail, Telegram, Alarm) aus Fixture-/Staging-Renders mit Testdaten |
| `frontend/src/lib/i18n/__tests__/`, `frontend/src/routes/__tests__/`, `frontend/e2e/` | CREATE | Tests zu den ACs |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `verifySession` (`$lib/auth.js`) | function | Entscheidet in `handle`, ob eine gültige Sitzung vorliegt |
| `MANDANT_HEADER` / `mandantenKennung` in `hooks.server.ts` | function | Header nur bei Session (#2131); die Startseite darf ihn nicht tragen |
| Service Worker `frontend/src/service-worker.ts` (Regel 3 und 5) | module | `/` wird nur als Navigation „nur Netz, nie ablegen" bedient, statische Assets ohne Ablage; kein Eingriff nötig |
| `+layout.svelte` `publicPages` | const | Steuert App-Chrome; für `/` zusätzlich vom Anmeldezustand abhängig |
| `/register`, `/login` | route | Ziele der beiden Links; Einladungslinks aus #2519 bleiben zusätzlich bestehen |
| Atoms (Card, Btn, Eyebrow), `Wordmark` | component | Aufbau der Seite ohne neue Organismen |
| ADR-0003 (PWA/Gerätespeicher) | adr | Mandantentrennung im Gerätespeicher |
| ADR-0066 | adr | E-Mail-Bestätigung bleibt Teil der Registrierung |

## Implementation Details

**1. Routing in `handle`.** Vor dem Redirect wird die Sitzung wie bisher geprüft. Ist keine gültige Sitzung vorhanden und ist `event.url.pathname === '/'` (exakter Vergleich, nicht `startsWith`), wird `resolve(event)` aufgerufen. Die Antwort bekommt `cache-control: no-cache` wie die übrigen HTML-Antworten und **keinen** `x-gz-mandant`-Header (#2131). `locals.userId` bleibt ungesetzt. Die Client-Navigation vom Login-Formular zur Startseite holt `/__data.json`; SvelteKit setzt dafür `url.pathname` auf den Seitenpfad `/` (siehe Kommentar im bestehenden Hook), der exakte Vergleich deckt das ab. Alle anderen Pfade (`/trips`, `/compare`, `/admin`, `/api/...`, `/landing/...` ausgenommen, siehe Punkt 5) laufen unverändert in `redirect(302, '/login')`. Mit gültiger Sitzung ändert sich nichts.

**2. Loader.** `+page.server.ts` prüft zuerst `locals.userId`. Fehlt es, kommt sofort die leere Antwort mit `oeffentlich: true` zurück, ohne `fetch` an Go (kein Netzwerkzugriff, kein 401-Rauschen, kein Datenleck). Mit Nutzer: bestehender Code unverändert, zusätzlich `oeffentlich: false`.

**3. Layout.** `+layout.server.ts` ruft bereits nur bei `locals.userId` die Go-API auf. `+layout.svelte` behandelt `/` als Standalone-Seite (kein App-Chrome), wenn `data.userId` leer ist; für Eingeloggte bleibt `/` mit Chrome.

**4. Textkatalog.** `frontend/src/lib/i18n/messages/de.json` mit flachen Schlüsseln (z. B. `start.hero.title`, `start.mail.alt`). `index.ts` importiert die JSON-Datei und exportiert `t(key: MessageKey): string` mit `MessageKey = keyof typeof de`; ein unbekannter Schlüssel ist ein TypeScript-Fehler (`svelte-check`). Keine neue Abhängigkeit, kein Paraglide. Deutsch ist die einzige Sprache. Der Katalog ist bewusst allgemein gehalten, damit #2521 ihn mitnutzt.

**5. Statische Assets.** Screenshots liegen unter `frontend/static/landing/`, erzeugt aus Fixture-/Staging-Renders mit Testdaten (keine echten Empfänger, keine Personendaten). Gezeigt werden Briefing-Mail (Hauptkanal), Telegram-Nachricht und Alarm. Alt-Texte kommen aus dem Katalog. Hinweis: Der Hook leitet auch Anfragen an `/landing/...` für Ausgeloggte auf `/login` um. Darum wird der Pfadpräfix `/landing/` im Hook als öffentlich behandelt (exakt `startsWith('/landing/')`, nur statische Dateien, Methode GET). Alternative ohne Hook-Eingriff: Assets per Import über Vite bündeln (`/_app/immutable/...`); dort greift der Hook ebenfalls nicht. Die Umsetzung wählt die Variante, die ohne Sonderpfad im Hook auskommt, wenn der Build das zulässt; andernfalls gilt `/landing/`.

**6. Inhalt und Tonalität.** Drei Sektionen mit weißen Karten (`--g-card`) auf `--g-paper`, Fließtext in `--g-ink` (mindestens 4.5:1), einspaltig mobil zuerst, zwei Spalten ab Tablet-Breite. E-Mail wird als Hauptkanal kommuniziert, daneben Telegram. Die Wörter „SMS" und „Premium-SMS" kommen im gesamten Startseitentext und in den Alt-Texten nicht vor; auch keine SMS-Screenshots. Kernaussage zur Empfangslage: unterwegs ist unvorhersehbar, was gerade ankommt, darum beantwortet jeder Kanal jede Frage. Zwei sichtbare Handlungsaufrufe: „Registrieren" → `/register` (primär), „Anmelden" → `/login` (sekundär). Kein Tracking, keine Analytics-Skripte, keine Live-Daten.

**7. PWA/Service Worker.** `/` fällt in Regel 3 des Workers (Navigation: nur Netz, nie ablegen), die Startseite landet also nie im nutzerbezogenen Gerätespeicher und kann nie als Cockpit-Stand eines Nutzers erscheinen. Umgekehrt erhält die Startseite keinen Mandant-Header, würde also selbst bei künftiger Positivliste-Erweiterung fail-closed nicht abgelegt (`ablegen` bricht ohne Kennung ab). Statische Assets laufen über Regel 5 (Netz ohne Ablage). Der Worker bleibt deshalb unverändert.

**8. Login/Register.** Ein Link „Zur Startseite" auf diesen Seiten ist ausdrücklich Out of Scope.

## Expected Behavior

- **Input:** GET `/` mit und ohne gültiges Sitzungs-Cookie `gz_session`.
- **Output:** Ohne Sitzung: HTML-Startseite (200). Mit Sitzung: Cockpit wie bisher.
- **Side effects:** Keine. Insbesondere keine API-Aufrufe an Go ohne Sitzung, kein Mandant-Header, keine Ablage im Gerätespeicher.

## Acceptance Criteria

- **AC-1:** Given ein nicht eingeloggter Besucher / When er `/` aufruft / Then sieht er die öffentliche Startseite (Status 200, keine Weiterleitung auf `/login`) mit Überschrift, Erklärung „Was ist Gregor Zwanzig" und den Sektionen „Was bei dir ankommt" und „Warum das unterwegs nützt".
  - Test: Vitest/Node gegen echtes `handle` ohne Cookie auf `/` → 200 bzw. kein `redirect`; Render-Test der Startseite prüft die drei Sektionen.

- **AC-2:** Given ein nicht eingeloggter Besucher / When er einen geschützten Pfad wie `/trips`, `/compare`, `/admin` oder `/trips/abc` aufruft / Then wird er weiterhin mit Status 302 auf `/login` umgeleitet, nur der exakte Pfad `/` ist geöffnet.
  - Test: `handle` ohne Cookie auf mehrere Pfade (`/trips`, `/admin`, `/x/`, `//`) → je 302 auf `/login`; `/` und `/?x=1` bleiben offen (200); Mutation `startsWith('/')` muss den Test rot färben.

- **AC-3:** Given ein eingeloggter Nutzer mit gültiger Sitzung / When er `/` aufruft / Then sieht er unverändert das Cockpit mit seinen Trips und Orts-Vergleichen und nicht die öffentliche Startseite.
  - Test: `handle` mit gültigem signiertem Cookie auf `/` → Antwort trägt Mandant-Header; Loader mit `locals.userId` liefert `oeffentlich: false` und ruft die Go-API (bestehende Cockpit-Tests bleiben grün). Zwei verschiedene Nutzer bekommen je ihre eigenen Daten.

- **AC-4:** Given ein nicht eingeloggter Besucher / When die Startseite geladen wird / Then werden keine Daten eines Nutzers geladen oder ausgeliefert: der Loader ruft die Go-API nicht auf, und die Antwort trägt keinen `x-gz-mandant`-Header.
  - Test: Loader ohne `locals.userId` mit einem `fetch`, das bei Aufruf den Test scheitern lässt (echte Funktion, kein Spiegel-Mock) → leeres Ergebnis; `handle`-Antwort auf `/` ohne Cookie enthält keinen `x-gz-mandant`.

- **AC-5:** Given die Startseite im Browser / When der Besucher auf „Registrieren" bzw. „Anmelden" klickt / Then gelangt er auf `/register` bzw. `/login`, und beide Links sind ohne Scrollen auf einem 375 px breiten Display erreichbar oder per Seitenende sichtbar.
  - Test: Playwright gegen Staging, Viewport 375 px, ausgeloggt: beide Links sichtbar, Klick führt auf die Zielseite.

- **AC-6:** Given die Startseite / When ein Besucher den Text liest / Then wird E-Mail als Hauptkanal genannt, Telegram wird erwähnt, und das Wort „SMS" (auch „Premium-SMS") erscheint weder im sichtbaren Text noch in Alt-Texten.
  - Test: Katalog-Test über alle Schlüssel `start.*` in `de.json`: kein Treffer auf `/sms/i`; Render-Test der Startseite prüft sichtbaren Text und `alt`-Attribute; ein Schlüssel nennt „E-Mail" im Hero-Bereich.

- **AC-7:** Given die Startseite / When sie angezeigt wird / Then zeigt sie mindestens drei statische Screenshots (Briefing-Mail, Telegram-Nachricht, Alarm), jeweils mit nicht leerem Alt-Text auf Deutsch, die tatsächlich geladen werden (HTTP 200, nicht kaputt).
  - Test: Playwright gegen Staging: alle `img` auf der Startseite haben `naturalWidth > 0` und einen Alt-Text mit Inhalt; Node-Test prüft, dass jede im Katalog referenzierte Bilddatei existiert. Freiheit von echten Personendaten (Adressen, Namen) ist manuelle Sichtprüfung bei der Asset-Erstellung.

- **AC-8:** Given der Textkatalog `de.json` / When Quelltext `t('start.unbekannt')` mit nicht vorhandenem Schlüssel verwendet wird / Then schlägt die Typprüfung (`svelte-check`/`tsc`) fehl, und alle sichtbaren Texte der Startseite stammen aus dem Katalog, nicht aus dem Markup.
  - Test: Typtest mit `@ts-expect-error` auf unbekannten Schlüssel (schlägt fehl, wenn der Schlüsseltyp zu weit ist); Test, dass `Startseite.svelte` keinen deutschen Fließtext außerhalb von `t(...)` enthält (`# doc-compliance-test`), plus `t('start.hero.title')` liefert den Katalogwert.

- **AC-9:** Given der Service Worker ist aktiv / When ein Besucher die Startseite besucht und sich danach als Nutzer A einloggt, dann abmeldet / Then erscheint auf `/` nie ein zwischengespeicherter Stand eines anderen Nutzers: ausgeloggt kommt immer die Startseite aus dem Netz, eingeloggt immer das eigene Cockpit.
  - Test: Playwright gegen Staging: ausgeloggt `/` → Startseite; Login Nutzer A → Cockpit; Logout → wieder Startseite, ohne Cockpit-Inhalte; Prüfung, dass in den Caches `gz-daten-*` kein Eintrag für `/` liegt.

- **AC-10:** Given die Startseite auf einem 375 px breiten Display / When sie geladen wird / Then gibt es keinen horizontalen Scrollbalken, der App-Chrome (Sidebar, Bottom-Navigation) ist ausgeblendet, und der Fließtext hat einen Kontrast von mindestens 4.5:1 auf der weißen Karte.
  - Test: Playwright gegen Staging: `document.documentElement.scrollWidth <= innerWidth`, kein Element mit `data-testid` der Navigation sichtbar; Kontrastprüfung der Textfarbe (Token-Wert gegen `--g-card`) im Node-Test.

- **AC-11:** Given ein Besucher mit einem Einladungslink `/register?invite=…` (#2519) / When er die Registrierung nutzt / Then funktioniert diese unverändert unabhängig von der Startseite, und `/register` bleibt ohne Anmeldung erreichbar.
  - Test: Bestehende Register-Tests bleiben grün; `handle` ohne Cookie auf `/register` → keine Weiterleitung.

## Known Limitations

- Nur Deutsch; der Katalog ist für spätere Sprachen vorbereitet, eine Sprachumschaltung gibt es nicht.
- Keine Live-Daten, keine Marketing-Tracking- oder Analytics-Skripte.
- Screenshots sind statisch und veralten bei Renderer-Änderungen; sie werden nicht automatisch neu erzeugt.
- Kein Link von `/login` und `/register` zurück zur Startseite (Out of Scope).
- SMS und Premium-SMS werden bewusst nicht beworben (PO-Vorgabe), obwohl alle vier Kanäle im Produkt gleichrangig sind.

## Architektur-Entscheidung (ADR)

Kein neues ADR nötig. Die Entscheidung berührt „Auth" nur durch eine einzige zusätzliche öffentliche Route (exakt `/`); die Abweichung ist hier dokumentiert. Der Textkatalog-Ansatz (kein Paraglide) ist im Issue-Kommentar vom 2026-10-07 entschieden.

## Changelog

- 2026-10-07: Initial spec created (Issue #2520)
