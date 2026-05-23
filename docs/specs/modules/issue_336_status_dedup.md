---
entity_id: issue_336_status_dedup
type: module
created: 2026-05-23
updated: 2026-05-23
status: draft
version: "1.0"
tags: [sveltekit, frontend, trip-detail, design-compliance, ux]
---

# Issue #336 — Doppelte Status-Anzeige im Tour-Kopf bereinigen

## Approval

- [ ] Approved

## Purpose

Im Tour-Kopf auf `/trips/[id]` erscheint der Status doppelt: als Versalien-Text-Präfix
("**AKTIV** · läuft seit Tag 3") **und** als farbige Pill ("Aktiv"). Diese Spec entfernt
das nicht-konforme Versalien-Präfix und behält die Pill als alleinige Statusdarstellung.
Grundlage: Design-System `COPY.md §3` + `ANTI-PATTERNS AP-020` definieren Status
ausschließlich über semantische Indikatoren (Pill/Dot), nicht über Text-Präfixe.

## Source

- **File:** `frontend/src/lib/components/trip-detail/TripHeader.svelte`
- **Identifier:** Status-Zeile `.status-line` (Z. 81–86), lokale `statusLabelMap` (Z. 32–37),
  `.status-text` + `.status-{active|planned|paused|archived}` Styles (Z. 174–182)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `TripStatusBadge.svelte` | Komponente (unverändert) | Farbige Pill mit deutschem Label + Tone — bleibt alleinige Statusdarstellung |
| `getDaysLabel()` (`tripHero.ts`) | Util (unverändert) | Liefert den Zusatz ("läuft seit Tag N" / "in N Tagen" / …) |
| `deriveTripStatus()` (`tripStatus.ts`) | Util (unverändert) | Status-Quelle für die Pill |
| `--g-ink-muted`, `--g-text-sm` | CSS-Token | Gedämpfter Sekundärtext für den Zusatz |
| `COPY.md §3`, `AP-020` | Design-System | Autorität: Status nur als semantischer Indikator |

## Implementation Details

```svelte
<!-- vorher (Z. 81–86) -->
<div class="status-line">
  <span class="status-text status-{status}">
    {statusLabelMap[status]} · {daysLabel}
  </span>
  <TripStatusBadge {trip} {now} />
</div>

<!-- nachher -->
<div class="status-line">
  <span class="status-supplement" data-testid="trip-detail-status-supplement">
    {daysLabel}
  </span>
  <TripStatusBadge {trip} {now} />
</div>
```

Weitere Änderungen in `TripHeader.svelte`:
- Tote `statusLabelMap`-Konstante (Z. 32–37) entfernen.
- `.status-text` → `.status-supplement`: gedämpfter Sekundärtext
  (`color: var(--g-ink-muted)`, `font-size: var(--g-text-sm)`), **ohne** das bisherige
  `letter-spacing: 0.05em` (Versalien-Anmutung entfällt). Die Statusfarbe lebt jetzt
  ausschließlich in der Pill.
- Tote Farbklassen `.status-active/.status-planned/.status-paused/.status-archived`
  (Z. 179–182) + das `status-{status}`-Klassen-Binding entfernen.
- `<TripStatusBadge>` bleibt **unverändert**.

Kein Backend, keine Daten-Schema-Berührung, keine geteilten Utils geändert.

## Expected Behavior

- **Input:** User öffnet `/trips/[id]` einer Tour (Status active/planned/paused/archived).
- **Output:** Die Status-Zeile zeigt den Status **genau einmal** — als farbige Pill —
  gefolgt vom dezenten, grau gedämpften Zusatz (z. B. "läuft seit Tag 3"). Kein
  Versalien-Präfix mehr.
- **Side effects:** keine.

## Acceptance Criteria

**AC-1:** Given eine aktive Tour wird auf `/trips/[id]` geöffnet / When die Status-Zeile gerendert wird / Then enthält `[data-testid="trip-detail-status-supplement"]` den Zusatztext (z. B. "läuft seit Tag") und **nicht** das Versalien-Präfix "AKTIV"
- Test: (populated after /tdd-red)

**AC-2:** Given eine aktive Tour wird auf `/trips/[id]` geöffnet / When der Tour-Kopf gerendert wird / Then ist die Pill `[data-testid="trip-detail-status-badge"]` weiterhin sichtbar und enthält das deutsche Label "Aktiv" (Status wird genau einmal angezeigt)
- Test: (populated after /tdd-red)

**AC-3:** Given eine pausierte Tour wird auf `/trips/[id]` geöffnet / When der Tour-Kopf gerendert wird / Then enthält die Pill `[data-testid="trip-detail-status-badge"]` "Pausiert" (Regressions-Guard für die 9 bestehenden Pill-Assertions in `trip-detail-actions.spec.ts`)
- Test: (populated after /tdd-red)

**AC-4:** Given der Tour-Kopf wird gerendert / When der Zusatztext-Span dargestellt wird / Then verwendet `[data-testid="trip-detail-status-supplement"]` die gedämpfte Sekundärfarbe `var(--g-ink-muted)` und **nicht** eine Status-Accent-Farbe (die Farbe lebt allein in der Pill)
- Test: (populated after /tdd-red)

## Known Limitations

- `getDaysLabel()` liefert für `paused` "pausiert seit N Tagen" neben der Pill "Pausiert"
  (milder Wort-Wiederholer). Bewusst nicht angefasst — geteilte Util, Änderung wäre
  Scope-Creep gegenüber der reinen Doppel-Darstellung.
- Die `TripStatusBadge`-Darstellung als Pill (statt `Dot+Label` für "Aktiv" laut
  `COPY.md §3`) bleibt — projektweit bereits auf Pill standardisiert (#282/#295),
  separate Frage.

## Related — Spec-Nachzug (Pflicht)

`docs/specs/modules/issue_302_trip_detail_page.md` §163 + §313 ("Statuszeile
'AKTIV · TAG N VON M'") erhält im selben Workflow eine additive #336-Korrektur-Notiz,
damit Doku und Code nicht driften.

## Changelog

- 2026-05-23: Spec erstellt für Issue #336 (Versalien-Status-Präfix entfernen, Pill behalten)
