---
entity_id: issue_1010_1006_stille_fehler
type: bugfix
created: 2026-07-04
updated: 2026-07-04
status: draft
version: "1.0"
tags: [frontend, trip-editor, auth, session, save]
---

# Issues #1010 + #1006 — Stille Fehler: Startzeit-Verlust & Sitzungsablauf

## Approval

- [ ] Approved

## Purpose

Zwei „stille Fehler", beide am 2026-07-04 zweifach live beim PO aufgetreten
(Logbelege in den Issues):

1. **#1010:** `handleStartTimeChange` in `EditStagesPanelNew.svelte` (Issue #675)
   aktualisiert nur den lokalen Zustand und ist der EINZIGE Änderungs-Handler des
   Panels ohne `scheduleSave()`/`save()`-Aufruf — eine reine Startzeit-Änderung
   wird daher NIE gespeichert (geräteunabhängig; Logbeleg: 11:00 eingetragen bei
   gültiger Sitzung, null Schreibzugriffe am Server).
2. **#1006:** Der zentrale API-Wrapper `frontend/src/lib/api.ts::request()`
   behandelt 401 (Sitzung nach 24h-TTL abgelaufen, Go-Middleware) nicht — die
   Komponenten zeigen die rohe Meldung („unauthorized" / „Speichern
   fehlgeschlagen"), Aktionen und Eingaben aus offenen Tabs versanden still.
   Seitenloads werden bereits korrekt zu /login umgeleitet (hooks.server.ts).

## Source

- **File:** `frontend/src/lib/components/edit/EditStagesPanelNew.svelte:144-154`
  — `handleStartTimeChange`: Save-Trigger nach Panel-Muster ergänzen
  (`if (saveController) scheduleSave(); else void save();`, Vorbilder Z.133/140/270)
- **File:** `frontend/src/lib/api.ts:3-19` — `request()`: zentrale 401-Behandlung
  (Erkennung → Weiterleitung `/login?expired=1&redirect=<aktueller Pfad>` +
  aussagekräftige Fehlermeldung für alle Aufrufer, die nicht wegnavigieren)
- **File:** `frontend/src/routes/login/+page.svelte` — Hinweis-Banner bei
  `?expired=1` („Sitzung abgelaufen — bitte neu anmelden."), nach Login Rückkehr
  zum `redirect`-Pfad (nur relative Pfade akzeptieren — kein Open-Redirect)
- **Identifier:** `handleStartTimeChange`, `request`, `saveController`

## Estimated Scope

- **LoC:** ~30-50 Produktionscode (Frontend), + Playwright-E2E-Spec
- **Files:** 3 Code + 1-2 Tests — **Risk Level:** LOW (zentrale, mustergetreue Fixes)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `saveStatusStore` (#758) | store | Auto-Save-Controller — bestehender Save-/Fehlerkanal |
| `verifySession`/24h-TTL (auth.ts, middleware/auth.go) | behavior | 401-Quelle; unverändert |
| `hooks.server.ts` Redirect | pattern | Vorbild für Login-Rückleitung |
| Playwright/Staging (`GZ_SVELTE_BASE`) | infra | E2E-Nachweis als eingeloggter Nutzer |

## Implementation Details

1. **#1010:** In `handleStartTimeChange` nach dem State-Update den Save-Trigger
   nach exakt dem Muster der Nachbar-Handler ergänzen. Keine weitere Logik-
   Änderung (Kaskaden-/Neuberechnungslogik bleibt unangetastet).
2. **#1006:** In `request()` bei `res.status === 401`: browserseitig auf
   `/login?expired=1&redirect=<location.pathname>` navigieren und einen
   Fehler mit klarer deutscher Meldung werfen („Sitzung abgelaufen — bitte neu
   anmelden."), damit offene Fehlerpfade (saveController, Buttons) bis zur
   Navigation Sinnvolles anzeigen. SSR-Kontext (kein `window`) unverändert
   durchwerfen.
3. **Login-Seite:** Banner bei `expired=1`; nach erfolgreichem Login Redirect auf
   den mitgegebenen relativen Pfad (Validierung: muss mit `/` beginnen, kein `//`).

## Expected Behavior

- **Input/Output #1010:** Nutzer ändert im Etappen-Editor NUR die Startzeit →
  Auto-Save läuft (Save-Status sichtbar), nach Seiten-Neuladen ist die Zeit
  persistent; Briefings rechnen ab dieser Zeit (#1004-Kette).
- **Input/Output #1006:** Beliebige UI-Aktion mit abgelaufener Sitzung → keine
  kryptische Meldung, sondern Weiterleitung zur Anmeldeseite mit Banner
  „Sitzung abgelaufen"; nach Anmeldung landet der Nutzer wieder auf der Seite,
  von der er kam.
- **Side effects:** keine Backend-Änderungen; keine neuen Endpoints.

## Acceptance Criteria

- **AC-1 (Startzeit-Persistenz, Kern #1010):** Given ein eingeloggter Nutzer auf
  Staging im Trip-Editor (Reiter Etappen) / When er AUSSCHLIESSLICH die
  Startzeit einer Etappe über das Zeitfeld ändert (keine weitere Änderung) und
  die Seite nach Abschluss des Auto-Saves neu lädt / Then zeigt das Zeitfeld die
  neue Startzeit (persistiert), und die Trip-Daten (API-Antwort) enthalten sie.
  - Test: Playwright gegen Staging als echter eingeloggter Nutzer — echter
    Klick-Pfad ins Zeitfeld, UI-Wert nach Reload prüfen (rot vor Fix).

- **AC-2 (Save-Status sichtbar):** Given dieselbe Situation / When die Startzeit
  geändert wird / Then durchläuft die Speicheranzeige sichtbar den Zustand
  „speichert…/gespeichert" (bestehender saveController-Mechanismus) — die
  Änderung versandet nicht mehr stumm.
  - Test: Playwright — Save-Status-Element beobachten.

- **AC-3 (401 → klare Meldung + Login, Kern #1006):** Given ein Nutzer mit
  ungültiger/abgelaufener Sitzung (Playwright: gz_session-Cookie entfernt oder
  verfälscht — der Server lehnt dann REAL mit 401 ab) auf einer bereits
  geladenen Seite / When er eine Aktion auslöst, die die API ruft (z.B.
  Startzeit ändern oder Testbriefing senden) / Then landet er auf der
  Anmeldeseite mit sichtbarem Hinweis „Sitzung abgelaufen" — keine kryptische
  Meldung, kein stilles Versanden.
  - Test: Playwright gegen Staging — Cookie manipulieren, Aktion klicken,
    Banner + URL prüfen.

- **AC-4 (Rückkehr nach Login):** Given der 401-Redirect aus AC-3 von der Seite
  `/trips/<id>?tab=stages` / When der Nutzer sich neu anmeldet / Then landet er
  wieder auf `/trips/<id>?tab=stages` (nur relative Pfade; externe/`//`-Ziele
  werden ignoriert → Standardziel Startseite).
  - Test: Playwright — kompletter Kreis: Cookie weg → Aktion → Login → zurück.

- **AC-5 (keine Regression im Editor):** Given der Etappen-Editor / When Datum,
  Ruhetag/Kaskade oder andere Felder geändert werden / Then speichern diese
  Pfade unverändert (bestehende Editor-E2E/Unit-Tests bleiben grün); der
  #1010-Fix fügt nur den fehlenden Save-Trigger hinzu.
  - Test: bestehende Editor-Tests + gezielter Playwright-Durchgang.

- **AC-6 (Zwei-Nutzer-Isolation):** Given Nutzer A ändert seine Startzeit über
  die UI / When Nutzer B seinen eigenen Trip lädt / Then sieht B ausschließlich
  seine eigenen Daten unverändert (Startzeit-Änderung wirkt nur im Trip von A).
  - Test: Playwright mit zwei Staging-Test-Accounts.

## Known Limitations

- **Kein Eingabe-Erhalt über den Re-Login hinweg:** Was zum Zeitpunkt des
  Sitzungsablaufs ungespeichert im Formular stand, ist nach dem Login nicht
  automatisch wiederhergestellt (separates Feature; in #1006 als „idealerweise"
  notiert). Dieser Fix garantiert: klare Meldung + Rückkehr zur Ausgangsseite.
- **24h-Sitzungsdauer bleibt unverändert** (Sicherheitsentscheidung; nicht Teil
  dieses Bündels).
- **Nur der zentrale `api.*`-Wrapper wird gehärtet:** Direkte `fetch()`-Aufrufe
  außerhalb des Wrappers (z.B. GPX-Upload) profitieren nur, sofern sie den
  Wrapper nutzen; ein Audit weiterer Roh-fetches ist Folgearbeit, falls Funde.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine — Bugfix nach bestehenden Mustern, kein neues Schema/Gate/
  Kanal, keine neue UI-Architektur (bestehende Login-Seite + SaveStatus-Mechanik).

## Test Coverage

- `frontend/e2e/` bzw. `e2e/` Playwright-Spec (NEU): AC-1 bis AC-6 gegen Staging
- Bestehende Editor-/675er-Tests: Regression (AC-5)

## Changelog

- 2026-07-04: Initial spec — Bündel #1010 (fehlender Save-Trigger Startzeit) +
  #1006 (zentrale 401-Behandlung), Root Causes mit Logbelegen in den Issues.
