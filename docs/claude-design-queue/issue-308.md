# #308 — Design: Konto-Seite (/account) — Desktop + Mobile

**Labels:** `priority:medium` `frontend` `area:sidebar` `for:claude-design`
**URL:** https://github.com/henemm/gregor_zwanzig/issues/308
**Erstellt:** 2026-05-21

---

## Was fehlt

Die Konto-Seite (`/account`) ist im UX-Redesign (`docs/specs/ux_redesign_navigation.md §4`) **nur textlich beschrieben** — kein einziges visuelles Mockup existiert, weder für Desktop noch Mobile.

## Aktueller Zustand (Ist)

Die Seite enthält bereits alle Funktionen, aber in ad-hoc HTML ohne Design-System-Konformität:
- Profil-Block (Benutzername, Mitglied seit)
- Kanal-Block (E-Mail, Signal, Telegram mit Test-Buttons)
- Passwort-ändern-Formular (natives HTML, kein `<Btn>`)
- System-Status (Scheduler-Status, Report-Zähler)
- Wetter-Templates-Liste
- Account-Löschung

## Was ich brauche

**Desktop** (1440 px) + **Mobile** (375 px):

Sektionen klar visuell getrennt, jede mit Eyebrow-Label:
1. **PROFIL** — Username + Mitglied-seit in Mono
2. **BENACHRICHTIGUNGS-KANÄLE** — Jeder Kanal als Card mit Status-Dot, Test-Button, Konfigurationsfeldern
3. **PASSWORT** — Formular-Card
4. **SYSTEM-STATUS** — Scheduler-Status, nächster Report in Mono (Tabelle oder KV-Rows)
5. **WETTER-TEMPLATES** — Liste gespeicherter Templates mit Löschen-Button
6. **KONTO LÖSCHEN** — Danger-Zone am Ende, `<Btn variant="destructive">`

## Besondere Anforderungen

- Kanal-Karten müssen den aktuellen Verbindungsstatus klar zeigen (verbunden/nicht verbunden/Fehler)
- System-Status soll schnell lesbar sein (Mono-Zahlen, Zeitstempel)
- Danger-Zone visuell klar abgesetzt (roter Rand oder Abstand + Warning-Text)

## Betroffene Datei

- `frontend/src/routes/account/+page.svelte`
