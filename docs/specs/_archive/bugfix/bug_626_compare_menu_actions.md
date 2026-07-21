# Bug #626 — Ortsvergleiche: Listen-Menü-Aktionen tot

- **Status:** Spec
- **Created:** 2026-06-06
- **Issue:** #626
- **Typ:** Bug (Frontend)
- **Workflow:** bug-626-compare-menu-actions

## Problem

Auf der Übersichtsseite `/compare` zeigt jede Kachel ein „⋯"-Menü (`CompareKebab`)
mit den Aktionen aus `compareActions(status)`. Für aktive/pausierte Vergleiche
sind das: Pausieren · Briefing jetzt senden · Vorschau öffnen · Bearbeiten ·
Archivieren · Löschen.

Aber `handleAction()` in `CompareGrid.svelte:39-46` verarbeitet **nur** `delete`
und `archive`. Die Aktionen `pause`, `send`, `preview`, `edit` und `setup` (Draft)
fallen in einen toten Kommentar („Weitere Aktionen folgen in späteren Issues") →
**stiller Fehlschlag**: Der Nutzer klickt, nichts passiert. Eingerichtete
Vergleiche lassen sich aus der Liste heraus nicht verwalten.

Zusätzlich: Das Toggle-Label ist statisch „Pausieren" (`subscriptionHelpers.ts:116`),
auch wenn ein Vergleich bereits pausiert ist. Claude Design (`molecules.jsx`
`compareActions`) sieht ein **kontextabhängiges** Label vor: „Pausieren" bei
aktiv, „Aktivieren" bei pausiert.

## Zielfunktionen existieren bereits

- Edit-Seite: `frontend/src/routes/compare/[id]/edit/+page.svelte` (+ SSR-Loader)
- Vorschau: `CompareTabs.svelte` Tab `vorschau` (erreichbar via `?tab=vorschau`)
- Pause-Mechanik: `schedule === 'manual'` = pausiert (`deriveStatusFromPreset`,
  `subscriptionHelpers.ts:89`); Toggle bereits funktional im Versand-Tab
  (`CompareTabs.handleToggleActive`)

Es fehlt also nur die **Verdrahtung** des Listen-Menüs mit diesen vorhandenen
Funktionen — keine neue Backend-Funktionalität.

## Scope

- **In Scope:** reines Frontend — `CompareGrid.svelte` (`handleAction`) +
  `subscriptionHelpers.ts` (`compareActions`-Label).
- **Out of Scope:** echter Briefing-Versand (`send`) → eigenes Issue **#627**
  (Full-Stack, Backend-Lückenschluss). Damit in Teil 1 kein toter „Senden"-Knopf
  zurückbleibt, wird die `send`-Aktion **vorübergehend aus dem Listen-Menü
  entfernt** und in #627 zusammen mit der echten Versandlogik wieder eingeführt.

## Multi-User

Alle betroffenen Backend-Pfade (Edit-Save, Pause-Toggle via PUT, Vorschau) sind
bereits über `s.WithUser(middleware.UserIDFromContext(...))` mandantengetrennt.
Dieser Bug-Fix ändert keinen Backend-Pfad und führt keine `user_id`-Behandlung
ein — die Isolation bleibt unangetastet. (Die kritische `user_id`-Durchreichung
beim Versand ist Thema von #627.)

## Acceptance Criteria

**AC-1:** Given ein aktiver Orts-Vergleich auf `/compare`, When der Nutzer im
„⋯"-Menü „Bearbeiten" wählt, Then navigiert die App zur Bearbeiten-Seite
`/compare/{id}/edit` und lädt das Preset zur Bearbeitung.

**AC-2:** Given ein aktiver Orts-Vergleich, When der Nutzer im Menü „Pausieren"
wählt, Then wird das Preset auf `schedule = 'manual'` umgestellt (PUT,
Read-Modify-Write, keine anderen Felder verändert), der Status-Pill der Kachel
wechselt auf „Pausiert" und das Menü-Label lautet anschließend „Aktivieren".

**AC-3:** Given ein pausierter Orts-Vergleich (`schedule = 'manual'`), When der
Nutzer im Menü „Aktivieren" wählt, Then wird das Preset auf einen aktiven
Schedule (`'daily'`) umgestellt, der Status-Pill wechselt auf „Aktiv" und das
Menü-Label lautet anschließend wieder „Pausieren".

**AC-4:** Given ein beliebiger Orts-Vergleich, When der Nutzer im Menü „Vorschau
öffnen" wählt, Then navigiert die App zu `/compare/{id}?tab=vorschau` und zeigt
den Vorschau-Tab.

**AC-5:** Given ein Draft-Vergleich (ohne Name oder ohne Orte), When der Nutzer im
Menü „Setup fortsetzen" wählt, Then navigiert die App zur Bearbeitung
`/compare/{id}/edit`.

**AC-6:** Given das „⋯"-Menü eines aktiven/pausierten Vergleichs, When es geöffnet
wird, Then enthält es **keine** Aktion „Briefing jetzt senden" (verschoben nach
#627), sodass kein nicht-funktionaler Menüpunkt sichtbar ist.

**AC-7:** Given die bereits funktionierenden Aktionen, When der Nutzer
„Archivieren" oder „Löschen" wählt, Then verhalten sie sich unverändert
(Regressions-Schutz: Archivieren setzt `archived_at` via PATCH und entfernt die
Kachel; Löschen öffnet den Bestätigungsdialog und löscht nach Bestätigung).

## Verifikation

Playwright-E2E gegen Staging als eingeloggter Nutzer (kein Mock): für einen
Test-Vergleich jede Menü-Aktion einmal durchklicken und die resultierende
Route/den Status prüfen. Mindestens AC-2/AC-3 (Toggle) beweisen das reproduzierte
Verhalten rot-vor-Fix / grün-nach-Fix.
