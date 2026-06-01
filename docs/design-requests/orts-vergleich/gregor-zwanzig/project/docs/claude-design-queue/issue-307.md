# #307 — Design: Registrierung + Passwort-Reset — Auth-Flow komplett (Desktop + Mobile)

**Labels:** `priority:medium` `frontend` `for:claude-design`
**URL:** https://github.com/henemm/gregor_zwanzig/issues/307
**Erstellt:** 2026-05-21

---

## Was fehlt

Drei Auth-Seiten haben **weder Desktop- noch Mobile-Design**:
- `/register` — Konto erstellen
- `/forgot-password` — Passwort-Reset anfordern
- `/reset-password` — Token-basierter Reset

## Aktueller Zustand

Alle drei Seiten sind einfache Rohformulare ohne Design-Token-Nutzung. Wirken wie Platzhalter.

## Was ich brauche

**Desktop + Mobile** für alle drei Screens. Sie können als ein zusammenhängendes Storyboard (Auth-Flow) gestaltet werden — gleiches Layout wie Login, aber mit:

**Register (`/register`):**
- Felder: Benutzername, Passwort, Passwort bestätigen
- Submit: `<Btn variant="primary">Konto erstellen</Btn>`
- Link: „Bereits ein Konto? Anmelden"
- Validierungs-Fehlerstate (z.B. Passwort zu kurz)

**Passwort vergessen (`/forgot-password`):**
- Feld: Benutzername
- Submit: `<Btn variant="primary">Reset anfordern</Btn>`
- Success-State: Bestätigungstext nach Submit

**Passwort zurücksetzen (`/reset-password`):**
- Felder: Benutzername, Token (aus E-Mail), Neues Passwort
- Submit: `<Btn variant="primary">Passwort speichern</Btn>`

## Token-Basis

Identisch mit Login: `--g-paper`, `--g-surface-1`, `--g-accent`, `--g-ink`, `<Wordmark>`, `<TopoBg>`

## Betroffene Dateien

- `frontend/src/routes/register/+page.svelte`
- `frontend/src/routes/forgot-password/+page.svelte`
- `frontend/src/routes/reset-password/+page.svelte`
