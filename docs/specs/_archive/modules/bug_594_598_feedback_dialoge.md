# Spec: Bug #594 + #598 — Feedback & Bestätigungs-Dialoge

**Issues:** #594 (Trip-Detail: Test-Briefing ohne Feedback), #598 (Trips-Liste: Archivieren ohne Dialog)  
**Workflow:** bug-594-598-feedback-dialoge  
**Typ:** Bug-Fix (Frontend only)

---

## Problem

### #594
Der Button „Test-Briefing senden" auf `/trips/[id]` zeigt nach dem API-Call eine Meldung,
aber mit `color: var(--g-ink-muted)` — kaum sichtbar, WCAG-Verstoß für Content-Text.
Der Nutzer erkennt nicht, ob der Versand funktioniert hat.

### #598
Der Primär-Button „Archivieren" in der Trips-Liste (`/trips`) führt die Aktion sofort aus.
„Löschen" hat einen Bestätigungs-Dialog — das Verhalten ist inkonsistent.
Archivierte Trips erhalten keine Briefings mehr; versehentliches Archivieren ist störend.

---

## Acceptance Criteria

**AC-1:** Given der Nutzer klickt „Test-Briefing senden" und der API-Call gelingt /
When die Antwort eintrifft /
Then erscheint unmittelbar eine grün gefärbte Erfolgs-Meldung „Test-Briefing wurde gesendet." mit ausreichendem Kontrast (WCAG AA, ≥ 4.5:1 auf Weiß).

**AC-2:** Given der Nutzer klickt „Test-Briefing senden" und der API-Call schlägt fehl /
When die Antwort eintrifft /
Then erscheint unmittelbar eine rot gefärbte Fehler-Meldung mit ausreichendem Kontrast (WCAG AA).

**AC-3:** Given der Nutzer klickt im ⋯-Menü oder auf den Primär-Button „Archivieren" /
When der Klick ausgelöst wird /
Then öffnet sich ein Bestätigungs-Dialog mit Titel „Trip archivieren?", Beschreibungstext „Archivierte Trips erhalten keine Briefings mehr.", Buttons [Abbrechen] [Archivieren].

**AC-4:** Given der Bestätigungs-Dialog ist offen /
When der Nutzer auf [Abbrechen] klickt oder den Dialog schließt /
Then schließt der Dialog ohne Aktion, der Trip bleibt unverändert.

**AC-5:** Given der Bestätigungs-Dialog ist offen /
When der Nutzer auf [Archivieren] klickt /
Then wird der Trip archiviert (PATCH `/api/trips/{id}/state`) und die Liste aktualisiert sich.

**AC-6:** Given der Nutzer klickt auf „Dearchivieren" /
When der Klick ausgelöst wird /
Then wird die Aktion sofort ausgeführt (kein Dialog — Dearchivieren ist reversibel).

---

## Implementierung

### #594 — `TripHeader.svelte`
- `testBriefingKind: 'success' | 'error' | null` State hinzufügen
- Nach API-Call: kind auf `'success'` oder `'error'` setzen
- `.briefing-msg` CSS: bei `kind='success'` → `--g-success` Farbe; bei `kind='error'` → `--g-danger`

### #598 — `trips/+page.svelte`
- `archiveTarget: Trip | null` State hinzufügen
- `handlePrimaryAction`: Archivieren-Pfad setzt nur `archiveTarget = trip`, kein PATCH direkt
- `handleArchive()`: PATCH + `refetchTrips()` + `archiveTarget = null`
- `ConfirmDialog` für Archive analog zum bestehenden Delete-Dialog hinzufügen
- Dearchivieren-Pfad bleibt unverändert (sofort, kein Dialog)

---

## Nicht in Scope
- Toast/Snackbar-Infrastruktur (kein globales Toast-System nötig)
- Mobile Bottom-Sheet — Archivieren-Option dort nicht vorhanden (nur Löschen)
- Dearchivieren-Dialog

---

## Changelog

**2026-06-04 — RESOLVED**
- Implementierung abgeschlossen
- AC-1 bis AC-6 bestätigt
- Frontend: TripHeader.svelte + trips/+page.svelte deployed
- Spec-Validator + Adversary VERIFIED
- Post-Deploy-Selftest PASS
