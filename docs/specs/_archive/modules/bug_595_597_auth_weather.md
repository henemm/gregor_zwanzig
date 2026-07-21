# Spec: Bug #595 + #597 — reset-password UX + /weather löschen

## Kontext
Zwei Frontend-Bugs aus Playwright-Audit 2026-06-04.

**#595** `/reset-password` hat kein App-Branding (Wordmark) und ein immer sichtbares Token-Feld, obwohl der Reset-Link das Token als URL-Parameter mitbringt.

**#597** `/weather` leitet auf `/compare` weiter (Legacy-Redirect seit #76). Die Seite wird nicht mehr benötigt und soll vollständig entfernt werden.

---

## Acceptance Criteria

**AC-1:** Given `/reset-password` wird geöffnet / When die Seite rendert / Then ist die Wordmark-Komponente (`<Wordmark`) im Markup der `+page.svelte` eingebunden — analog zu `/login`.

**AC-2:** Given `/reset-password` wird mit URL-Parameter `?token=abc123` aufgerufen / When das Formular rendert / Then ist das Token-Input-Feld mit `type="hidden"` versteckt (kein sichtbares Textfeld für den Token).

**AC-3:** Given `/reset-password` wird ohne `?token`-URL-Parameter aufgerufen / When das Formular rendert / Then ist das Token-Input-Feld sichtbar (type="text") damit manuelle Eingabe möglich ist.

**AC-4:** Given `/forgot-password` wird geöffnet / When die Seite rendert / Then ist die Wordmark-Komponente (`<Wordmark`) im Markup der `+page.svelte` eingebunden — Konsistenz mit `/login` und `/reset-password`.

**AC-5:** Given die Route `/weather` existierte vorher / When das Routing ausgewertet wird / Then existieren weder `frontend/src/routes/weather/+page.svelte` noch `frontend/src/routes/weather/+page.server.ts` mehr im Repository.

---

## Nicht im Scope
- Inhaltliche Änderungen am Reset-Passwort-Formular (Backend-Logik bleibt unberührt)
- Neue Weather-Funktionalität
- Änderungen an `/login` oder `/register`
