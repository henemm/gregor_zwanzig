---
entity_id: issue_321_copy_fix_deine_touren
type: module
created: 2026-05-22
updated: 2026-05-22
status: draft
version: "1.0"
tags: [copy, frontend, trips]
---

# COPY-Fix: "Trip/Trips" → "Tour/Touren" in der Trips-Listenansicht

## Approval

- [ ] Approved

## Purpose

Bereinigt alle nutzer-sichtbaren Tabu-Wörter „Trip" und „Trips" in der Trips-Listenansicht und der mobilen Bottom-Navigation. COPY.md §9 verbietet diese Wörter im Produkt-UI. Keine Logik-Änderungen.

## Source

- **Datei 1:** `frontend/src/routes/trips/+page.svelte`
- **Datei 2:** `frontend/src/lib/components/ui/sidebar/BottomNav.svelte`
- **Autorität:** `docs/design-system/COPY.md`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/design-system/COPY.md` | Autorität | Terminologie-Dictionary, §1/§6/§7/§9 |

## Implementation Details

Ausschließlich Textersetzungen in Template-HTML und String-Literals. Keine Logik-, Typ- oder API-Änderungen.

### `frontend/src/routes/trips/+page.svelte`

| Zeile | Alt | Neu | Quelle |
|-------|-----|-----|--------|
| ~236 | `Alle aktiven Trips für` | `Alle aktiven Touren für` | §1 |
| ~271 | `<h1 …>Trips</h1>` | `<h1 …>Meine Touren</h1>` | §6 Page-Title |
| ~274 | `Neuer Trip` (Btn) | `+ Neue Tour` | §7 CTA + §9 |
| ~302 | `Keine Trips vorhanden` | `Noch keine Tour.` | §7 Headline |
| ~303 | `Erstelle deinen ersten Trip und konfiguriere Wetter-Reports.` | `Lege deine erste Tour an — Wizard in 4 Schritten.` | §7 Body |
| ~304 | `Ersten Trip erstellen` (Btn) | `+ Neue Tour` | §7 CTA |
| ~436 | `{n} von {n} Trips` | `{n} von {n} Touren` | §1 |
| ~450 | `Trip löschen` (Dialog-Titel) | `Tour löschen` | §9 |

### `frontend/src/lib/components/ui/sidebar/BottomNav.svelte`

| Zeile | Alt | Neu | Quelle |
|-------|-----|-----|--------|
| ~10 | `label: 'Trips'` | `label: 'Touren'` | §1 |

### Nicht ändern

- Code-Identifier (`trips`, `filteredTrips`, `deleteTarget: Trip`, etc.) → COPY §9 erlaubt diese explizit in Code
- API-Pfade (`/api/trips`) → technisches Detail, kein UI
- `testid`-Attribute in BottomNav → technisches Attribut, kein UI-Text

## Expected Behavior

- **Input:** Nutzer ruft `/trips` auf
- **Output:** Seite zeigt „Meine Touren" als H1, alle Buttons/Labels/Dialoge verwenden „Tour/Touren"
- **Side effects:** keine

## Acceptance Criteria

**AC-1:** Given die Trips-Listenansicht ist geöffnet / When die Seite lädt / Then lautet die H1-Überschrift „Meine Touren" (nicht „Trips")
- Test: (populated after /tdd-red)

**AC-2:** Given die Trips-Listenansicht ist leer / When keine Touren vorhanden sind / Then lautet die Empty-State-Headline „Noch keine Tour." und der Button „+ Neue Tour"
- Test: (populated after /tdd-red)

**AC-3:** Given die Trips-Listenansicht hat Einträge / When eine Tour gelöscht werden soll / Then lautet der Dialog-Titel „Tour löschen"
- Test: (populated after /tdd-red)

**AC-4:** Given die mobile Bottom-Navigation ist sichtbar / When der Nutzer auf das Touren-Icon schaut / Then lautet das Label „Touren" (nicht „Trips")
- Test: (populated after /tdd-red)

**AC-5:** Given die Trips-Listenansicht hat Einträge / When der primäre Anlegen-Button sichtbar ist / Then lautet er „+ Neue Tour"
- Test: (populated after /tdd-red)

## Known Limitations

- Der Eyebrow-Text `WORKSPACE · TOUREN` weicht minimal von COPY §6 (`TOUREN`) ab, enthält aber kein Tabu-Wort — kein Fix in diesem Issue.
- `testid="bottom-nav-item-trips"` bleibt unverändert (technisches Attribut).

## Changelog

- 2026-05-22: Initiale Spec — Issue #321
