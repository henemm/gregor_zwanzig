---
entity_id: oeffentliche_startseite
type: module
created: 2026-10-07
updated: 2026-10-07
status: draft
version: "1.0"
tags: [frontend, landing, i18n, issue-2520]
---

# Oeffentliche Startseite (Landing) und Textkatalog

## Approval

- [ ] Approved

## Purpose

Wer nicht eingeloggt ist, sieht unter `/` eine oeffentliche Startseite, die erklaert, was Gregor Zwanzig ist, was bei ihm ankommt (Briefings, Alarme) und warum das unterwegs nuetzt. Gleichzeitig entsteht der zentrale Textkatalog (`t('key')`), auf dem auch #2521 aufbaut.

## Source

- **File:** `frontend/src/routes/+page.svelte`, `frontend/src/routes/+page.server.ts`, `frontend/src/hooks.server.ts`
- **Identifier:** `handle` (Hook), neue Komponente `LandingPage`, Funktion `t(key)`

## Estimated Scope

- **LoC:** ~250 (ohne Bilder und Katalog-Texte)
- **Files:** ~10
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/hooks.server.ts` | module | Auth-Redirect; `/` fuer Ausgeloggte durchlassen |
| `frontend/src/routes/+page.svelte` / `+page.server.ts` / `_home/` | module | Cockpit fuer Eingeloggte, bleibt unveraendert |
| `/register`, `/login` | route | Ziele der Call-to-Action-Links |
| `frontend/static/robots.txt` | static | Ist bereits `Disallow:` leer, `/` ist indexierbar, keine Aenderung noetig |
| Design-Tokens `--g-card`, `--g-paper` | css | Hoher Kontrast, WCAG-AA |

## Implementation Details

- Hook: `/` ohne Sitzung wird nicht auf `/login` umgeleitet, sondern ausgeliefert. Alle anderen geschuetzten Pfade leiten weiter wie bisher. Mit Sitzung rendert `/` das Cockpit.
- Der Ausgeloggt-Zweig laedt keine Nutzerdaten und ruft die Go-API nicht auf (Cross-User-Leck ausgeschlossen); `+page.server.ts` verzweigt vor jedem Datenzugriff.
- Textkatalog: `frontend/src/lib/i18n/messages/de.json` (flache Schluessel, Paraglide/inlang-kompatibel), Zugriff `t('key')` aus `frontend/src/lib/i18n/index.ts`, Schluessel typgeprueft (unbekannter Schluessel = Typfehler). Keine neue npm-Abhaengigkeit.
- Inhalt: Was ist Gregor Zwanzig; Briefing morgens/abends und Alarme; Nutzen (Empfangslage unterwegs unvorhersehbar: Huette eher WLAN, Pass Handyempfang; jeder Kanal beantwortet jede Frage). E-Mail als Hauptkanal, Telegram optional. SMS/Premium-SMS werden nicht beworben.
- Bilder: statische Screenshots unter `frontend/static/landing/` (Briefing-Mail, Telegram-Briefing, Alarm), aus Fixture-/Staging-Rendern mit Testdaten, ohne echte Adressen oder Personendaten; Alt-Texte aus dem Katalog.
- SEO: `title` und `description` aus dem Katalog.

## Expected Behavior

- **Input:** Aufruf von `/` mit bzw. ohne Sitzung.
- **Output:** Ohne Sitzung die Startseite mit Links "Registrieren" (`/register`) und "Anmelden" (`/login`); mit Sitzung das unveraenderte Cockpit.
- **Side effects:** Keine; kein Backend-Aufruf im Ausgeloggt-Zweig.

## Acceptance Criteria

- **AC-1:** Given ich bin nicht eingeloggt / When ich `/` aufrufe / Then sehe ich die oeffentliche Startseite (Status 200) und werde nicht auf `/login` umgeleitet.
  - Test: Vitest fuer `handle` mit Anfrage ohne Sitzung auf `/` (kein Redirect); Playwright gegen Staging ausgeloggt.

- **AC-2:** Given ich bin nicht eingeloggt / When ich einen anderen geschuetzten Pfad wie `/trips` aufrufe / Then werde ich weiterhin auf `/login` umgeleitet.
  - Test: Vitest fuer `handle` mit mehreren geschuetzten Pfaden ohne Sitzung.

- **AC-3:** Given ich bin eingeloggt / When ich `/` aufrufe / Then sehe ich unveraendert das Cockpit und nicht die Startseite.
  - Test: Playwright gegen Staging mit Test-Login: Cockpit-Elemente sichtbar, Landing-Ueberschrift fehlt.

- **AC-4:** Given ich bin nicht eingeloggt / When ich die Startseite lese / Then erfahre ich, was Gregor Zwanzig ist, dass morgens und abends ein Briefing sowie Alarme ankommen und warum das unterwegs nuetzt (Empfangslage unvorhersehbar, jeder Kanal beantwortet jede Frage).
  - Test: Vitest rendert die Seite und prueft die sichtbaren Abschnitte (Was, Was kommt an, Warum) anhand der Katalogtexte.

- **AC-5:** Given ich bin nicht eingeloggt / When ich die Startseite lese / Then wird E-Mail als Hauptkanal genannt, Telegram hoechstens als optional, und SMS oder Premium-SMS werden nirgends erwaehnt.
  - Test: Vitest auf gerenderten Seitentext: Mail vorhanden, Telegram nur als optional, kein "SMS" im sichtbaren Text.

- **AC-6:** Given ich bin nicht eingeloggt / When ich die Startseite oeffne / Then sehe ich Screenshots eines echten Briefings per E-Mail, eines Telegram-Briefings und eines Alarms, jeweils mit beschreibendem Alt-Text.
  - Test: Vitest: jedes `<img>` unter `/landing/` hat nicht-leeres `alt` aus dem Katalog; Playwright: Bilder laden (naturalWidth > 0), keine echten Empfaengeradressen sichtbar.

- **AC-7:** Given ich bin nicht eingeloggt / When ich auf "Registrieren" bzw. "Anmelden" klicke / Then lande ich auf `/register` bzw. `/login`.
  - Test: Playwright gegen Staging: beide Links klicken und URL pruefen.

- **AC-8:** Given ich bin nicht eingeloggt / When die Startseite ausgeliefert wird / Then werden keine Nutzerdaten geladen und kein Go-API-Aufruf ausgeloest.
  - Test: Vitest fuer `+page.server.ts` ohne Sitzung: kein Fetch/Store-Zugriff, Rueckgabe ohne Nutzerdaten.

- **AC-9:** Given der Textkatalog `de.json` / When ein Schluessel in `t('key')` nicht existiert oder ein Startseitentext im Code hartkodiert ist / Then schlaegt Typpruefung bzw. Katalog-Test fehl; alle sichtbaren Startseitentexte inklusive `title` und `description` stammen aus dem Katalog.
  - Test: Vitest: jeder von der Startseite genutzte Schluessel existiert und ist nicht leer; `svelte-check` meldet unbekannte Schluessel; gerenderter `<title>` entspricht dem Katalogwert.

- **AC-10:** Given ich rufe die Startseite am Handy (Breite 375 px) auf / When ich die Seite lese / Then ist sie ohne horizontales Scrollen lesbar, Karten sind weiss auf `--g-paper`, Text erreicht mindestens Kontrast 4.5:1.
  - Test: Playwright gegen Staging mit Mobil-Viewport: kein horizontaler Overflow, Axe-Kontrastpruefung ohne Verstoss.

## Known Limitations

- Nur Deutsch; weitere Sprachen ausser Scope.
- `robots.txt` erlaubt bereits alles, keine Aenderung.

## Out of Scope

- Englische Uebersetzung (Katalog ist nur vorbereitet).
- Onboarding fuer neue Nutzer (#2521).
- Bewerbung von SMS/Premium-SMS.

## Test Plan

- Kern (Vitest): `hooks.server.ts` (AC-1, AC-2), `+page.server.ts` (AC-8), Katalog und Seitenrendering (AC-4, AC-5, AC-6, AC-9).
- Live-E2E (Playwright gegen Staging): ausgeloggt und eingeloggt (AC-1, AC-3, AC-6, AC-7, AC-10).

## Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/hooks.server.ts` | MODIFY | `/` fuer Ausgeloggte durchlassen |
| `frontend/src/routes/+page.server.ts` | MODIFY | Verzweigung vor Datenzugriff |
| `frontend/src/routes/+page.svelte` | MODIFY | Landing oder Cockpit |
| `frontend/src/lib/components/landing/LandingPage.svelte` | CREATE | Startseite |
| `frontend/src/lib/i18n/index.ts` | CREATE | `t('key')`, typgeprueft |
| `frontend/src/lib/i18n/messages/de.json` | CREATE | Textkatalog |
| `frontend/static/landing/*.png` | CREATE | Screenshots |
| `frontend/src/hooks.server.test.ts` | CREATE/MODIFY | Vitest Hook |
| `frontend/src/lib/i18n/i18n.test.ts` | CREATE | Vitest Katalog |
| `frontend/src/routes/landing.test.ts` | CREATE | Vitest Seite |
| `frontend/e2e/landing.spec.ts` | CREATE | Playwright Staging |

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Keine Abweichung von bestehenden ADRs; Kanalrang folgt der PO-Vorgabe in CLAUDE.md.

## Changelog

- 2026-10-07: Initial spec created (Issue #2520)
