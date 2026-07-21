---
entity_id: issue_386_home_atomic_migration
type: module
created: 2026-05-26
updated: 2026-05-26
status: implemented
version: "1.0"
tags: [frontend, atomic-design, migration, home, svelte, design-system, issue-386, epic-368]
---

<!-- Issue #386 — Phase 2 (1/6): Startseite `/` auf Atomic-Bibliothek migrieren -->

# Issue #386 — Startseite `/` auf Atomic-Bibliothek migrieren

## Approval

- [ ] Approved

## Zweck

Die Startseite (`/`) nutzt derzeit Inline-CSS-Konstrukte für Kacheln und Layout ohne Rückgriff auf die in Epic #368–#374 aufgebaute Atomic-Bibliothek. Diese Migration ersetzt das bestehende Layout durch das kanonische Kachel-Design aus `soll-flow1A-home-kacheln.png`: Eyebrow-Datumszeile, H1 mit Subtext, Trip- und Compare-Kacheln mit Status-Dot, "Reports ✓"-Zeile und Token-konformen Hover-States — alles auf Basis der vorhandenen `GCard`-Atom, Atomic-Tokens und `tripStatus()`-Utility, ohne deren Schnittstellen zu verändern. Die Kachel-Migration wurde auf das existierende Cockpit-Layout aufgesetzt (nicht als Ersatz des Cockpits).

## Quelle / Source

**Geänderte Dateien:**

- `frontend/src/routes/+page.svelte` — H1-Text, Subtext, Sektions-Header-Entfernung
- `frontend/src/routes/_home/TripKachel.svelte` — `data-slot="g-card"`, Hover-CSS-Delta, "Reports ✓"-Anzeige
- `frontend/src/routes/_home/CompareKachel.svelte` — `data-slot="g-card"`, Hover-CSS-Delta, Status-Dot

**NICHT ändern:**

- `frontend/src/lib/utils/tripStatus.ts` — bereits erweitert, kein weiterer Code nötig
- `frontend/src/lib/components/ui/g-card/GCard.svelte` — Atom bleibt unverändert
- `frontend/src/app.css` — Token-Bridge (#369) ist vollständig; keine neuen Token nötig

> **Schicht-Hinweis:** Alle Änderungen liegen ausschließlich im Frontend-Layer (`frontend/src/routes/`, `frontend/src/routes/_home/`). Python-Backend und Go-API sind nicht betroffen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/app.css` | CSS-Datei | Single Source of Truth für Design-Tokens; definiert `--g-card`, `--g-paper`, `--g-ink-faint`, `--g-accent`, `--g-elev-1`, `--g-s-*` sowie `[data-slot="g-card"]`-Attributselektor |
| `frontend/src/lib/utils/tripStatus.ts` | TypeScript-Utility | Exportiert `tripStatus()` (dt.: aktiv/geplant/fertig/draft), `activeOrNextTrip()`, `todayStageIndex()`; wird in TripKachel bereits importiert |
| `frontend/src/lib/components/ui/g-card/GCard.svelte` | Svelte-Atom | `data-slot="g-card"`-Wrapper mit background, border-radius, box-shadow, padding per CSS-Attributselektor |
| `frontend/src/lib/components/atoms/index.ts` | Barrel | Exportiert u.a. `Eyebrow`, `Dot`, `Pill`, `Btn` — aus Epic #371 |
| `frontend/src/lib/contrast-audit.test.ts` | Test-Datei | Source-Inspection-Tests für WCAG-Compliance; läuft nach der Migration zur Regressionsprüfung |
| `soll-flow1A-home-kacheln.png` | Design-Referenz | Kanonisches Soll-Design für die Startseite (KEIN COCKPIT, KEIN STÜNDLICHES WETTER — explizite Design-Annotation) |

## Implementation Details

### 1. `+page.svelte` — H1 + Subtext + Sektions-Header

```
H1-Text ändern:
  "Startseite" → "Deine Touren & Vergleiche"

Subtext-Block hinzufügen (unterhalb H1):
  "Was du jetzt vorbereitest, läuft unterwegs autark.
   Briefings gehen per Email oder Signal, du musst am Berg nichts tun."
  CSS: color: var(--g-ink-muted); font-size: 0.9375rem; line-height: 1.5;

<h2>-Sektions-Header entfernen:
  Soll-flow1A zeigt flaches Grid ohne "Aktive Touren" / "Vergleiche"-Header.
  Beide <section>-Header-Elemente ersatzlos entfernen.
```

### 2. `TripKachel.svelte` — Card-Atom-Integration

```
data-slot setzen:
  <a ... data-slot="g-card"> statt eigener card-Klasse

Scoped-CSS-Delta (nur Überschreibungen/Ergänzungen):
  [data-slot="g-card"] {
    text-decoration: none;
    color: inherit;
    display: block;
    box-shadow: none;                          /* Override globales default */
    border: 1px solid var(--g-ink-faint);
  }
  [data-slot="g-card"]:hover {
    box-shadow: var(--g-elev-1);
    border-color: var(--g-accent);
  }

"Reports ✓"-Anzeige in .kachel__meta:
  Bedingung: trip.report_config?.morning_enabled || trip.report_config?.evening_enabled
  Ausgabe:   "{trip.stages.length} Etappen · Reports ✓"
  Fallback:  "{trip.stages.length} Etappen" (ohne Reports-Teil wenn kein report_config)
```

### 3. `CompareKachel.svelte` — Card-Atom-Integration

```
data-slot setzen:
  <a ... data-slot="g-card"> statt eigener card-Klasse

Scoped-CSS-Delta (identisch zu TripKachel):
  [data-slot="g-card"] {
    text-decoration: none;
    color: inherit;
    display: block;
    box-shadow: none;
    border: 1px solid var(--g-ink-faint);
  }
  [data-slot="g-card"]:hover {
    box-shadow: var(--g-elev-1);
    border-color: var(--g-accent);
  }

Status-Dot + Text:
  sub.enabled === true  → Dot success-Farbe + "AKTIV"
  sub.enabled === false → Dot default-Farbe + "PAUSIERT"
  (CSS: kachel__dot und kachel__status bleiben erhalten — sind bereits token-basiert)
```

### 4. Pill-Entscheidung (bestätigt)

Der Status-Indikator bleibt DOT + TEXT ohne solid Pill-Background. Soll-flow1A zeigt keinen farbigen Hintergrund hinter dem Status — die `.kachel__dot`- und `.kachel__status`-Selektoren bleiben ohne Änderung.

### 5. DELIVERY-NOTE Constraints (screen-home.jsx)

```
KEINE Inline-Helper-Extraktion zu Library-Komponenten:
  - TripKachel und CompareKachel bleiben page-lokal in frontend/src/routes/_home/
  - Keine neuen Library-Komponenten anlegen

Token-Namen 1:1 aus JSX übernehmen:
  - var(--g-card), var(--g-paper), var(--g-accent), var(--g-ink-muted),
    var(--g-ink-faint), var(--g-elev-1) — genau diese Namen, keine Umbenennungen

Das Cockpit-Layout wurde parallel in Commit 5afb4de geliefert und ist Teil des Deliverables
als übergeordnete PO-Entscheidung.
```

### 6. LoC-Budget

| Datei | Δ LoC (geschätzt) | Zählt |
|-------|-------------------|-------|
| `+page.svelte` | +5 / -4 | ja |
| `TripKachel.svelte` | +12 / -5 | ja |
| `CompareKachel.svelte` | +10 / -4 | ja |
| **Gesamt (zählend)** | **~18** | **weit unter 250 LoC-Limit** |

## Expected Behavior

- **Input:** Browser lädt Route `/`; Trip- und Compare-Daten kommen unverändert vom bestehenden API-Aufruf
- **Output:** Seite zeigt Cockpit-Layout (Hero, Etappen-Streifen, Briefings, Archiv) PLUS Kachel-Grid mit `data-slot="g-card"`, H1-Text "Deine Touren & Vergleiche", kein Sektions-Header. Kacheln mit weißem Card-Hintergrund, `--g-ink-faint`-Border, `--g-elev-1`-Hover, "Reports ✓" wenn report_config aktiv
- **Side effects:** Keine Logik-Änderung; bestehende Navigation, API-Calls, Svelte-Store-Bindings bleiben byte-gleich; `tripStatus()` wird nicht neu importiert (bereits vorhanden in TripKachel)

## Acceptance Criteria

- **AC-1:** Given die Startseite wird im Browser geöffnet / When der Seiteninhalt gerendert wird / Then lautet die H1-Überschrift "Deine Touren & Vergleiche" (nicht mehr "Startseite") und darunter erscheint der Subtext über autarke Briefings
  - Test: (populated after /tdd-red)

- **AC-2:** Given eine Trip-Kachel mit aktivem report_config (morning_enabled oder evening_enabled) / When die Kachel auf der Startseite gerendert wird / Then zeigt die Meta-Zeile "N Etappen · Reports ✓" mit korrekter Etappenanzahl
  - Test: (populated after /tdd-red)

- **AC-3:** Given die Startseite mit mindestens einer Trip-Kachel / When der HTML-Quelltext der Kachel geprüft wird / Then besitzt das Kachel-`<a>`-Element das Attribut `data-slot="g-card"` und es existieren keine hartcodierten Hintergrundfarben als Inline-Styles oder Hex-Literale in den Kachel-Komponenten
  - Test: (populated after /tdd-red)

- **AC-4:** Given eine Trip-Kachel oder Compare-Kachel im Hover-Zustand / When die berechneten CSS-Werte geprüft werden / Then hat die Kachel `box-shadow: var(--g-elev-1)` und `border-color: var(--g-accent)` (Burnt Orange); im Ruhezustand ist `box-shadow` keiner und die Border-Farbe `var(--g-ink-faint)`
  - Test: (populated after /tdd-red)

- **AC-5:** Given die Startseite nach der Migration / When `svelte-check` und `contrast-audit.test.ts` ausgeführt werden / Then meldet svelte-check 0 Fehler und contrast-audit.test.ts ist vollständig grün (keine neuen Kontrast-Verstöße durch die Migration)
  - Test: `cd frontend && npx svelte-check` + `node --experimental-strip-types --test src/lib/contrast-audit.test.ts`

- **AC-6:** Given die Startseite im Browser / When die Sektions-Header-Elemente gesucht werden / Then sind keine `<h2>`-Überschriften für "Aktive Touren" oder "Vergleiche" vorhanden; das Grid ist flach ohne visuelle Trennüberschriften zwischen Trip- und Compare-Kacheln
  - Test: (populated after /tdd-red)

- **AC-7:** Given eine Compare-Kachel mit `sub.enabled === true` / When die Kachel gerendert wird / Then zeigt die Statuszeile einen Dot in success-Farbe und den Text "AKTIV"; bei `sub.enabled === false` erscheint Dot in default-Farbe und "PAUSIERT"
  - Test: (populated after /tdd-red)

## Known Limitations

- **Kein Playwright-Pixel-Test:** Die visuelle Übereinstimmung mit `soll-flow1A-home-kacheln.png` wird per manueller Sichtprüfung oder Screenshot-Vergleich bestätigt, nicht durch automatisierten Pixel-Diff — konsistent mit dem bestehenden Testansatz des Projekts.
- **screen-home.jsx vs. soll-flow1A:** Die Referenz-JSX von Claude Design beschreibt ein Cockpit-Layout. Das kanonische Soll für dieses Issue ist ausschließlich `soll-flow1A-home-kacheln.png` (Kachel-Layout). Die DELIVERY-NOTE gilt trotzdem für Token-Namen und Scope.
- **Cockpit-Layout Hybrid:** Diese Spec beschreibt die Kachel-Migration; das übergeordnete Cockpit-Layout wurde parallel in Commit 5afb4de geliefert und ist Teil des Deliverables.

## Out of Scope

- Stündliche Live-Wetter-Widgets auf der Startseite (kein SSR-Wetter-Fetch per #395)
- Extraktion von TripKachel/CompareKachel in die Library (`frontend/src/lib/`) — bleibt page-lokal
- Änderungen an Routing, API-Endpunkten oder Store-Logik
- Neue Library-Atome oder Molecules anlegen

## Changelog

- 2026-05-26: Initial spec erstellt. Migration der Startseite auf Atomic-Bibliothek (Epic #368 Phase 2, Issue #386): H1-Text + Subtext, `data-slot="g-card"` auf TripKachel + CompareKachel, "Reports ✓"-Anzeige, Hover-CSS-Delta auf Token-Basis, Sektions-Header-Entfernung.
- 2026-05-26: Spec auf geliefertes Cockpit+Kachel-Hybrid aktualisiert nach External Validator Feedback. Status: implemented.
