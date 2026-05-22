# Context: Issue #321 — COPY-Fix "Trips" → "Touren" in der Trips-Listenansicht

## Request Summary
In der Trips-Listenansicht (`/trips`) werden Nutzer-sichtbare Texte mit dem verbotenen Wort „Trip/Trips" angezeigt. COPY.md §9 verbietet diese Worte im Produkt-UI. Alle Verletzungen sind zu korrigieren.

## Related Files

| File | Relevanz |
|------|----------|
| `frontend/src/routes/trips/+page.svelte` | Haupt-Datei, enthält alle COPY-Verletzungen |
| `frontend/src/lib/components/ui/sidebar/BottomNav.svelte` | Mobile Nav-Label "Trips" → "Touren" |
| `docs/design-system/COPY.md` | Autoritative Terminologie-Quelle |

## Konkrete COPY-Verletzungen

### `+page.svelte`

| Zeile | Ist (❌) | Soll (✅) | Quelle |
|-------|---------|----------|--------|
| 271 | `Trips` (H1) | `Meine Touren` | COPY.md §6, Touren-Liste Page-Title |
| 274 | `Neuer Trip` (CTA-Button) | `+ Neue Tour` | COPY.md §7 CTA + §9 Tabu |
| 302 | `Keine Trips vorhanden` (Empty-State Headline) | `Noch keine Tour.` | COPY.md §7 |
| 303 | `Erstelle deinen ersten Trip und konfiguriere Wetter-Reports.` (Body) | `Lege deine erste Tour an — Wizard in 4 Schritten.` | COPY.md §7 + §2 (Erstellen ❌) |
| 304 | `Ersten Trip erstellen` (Empty-State CTA) | `+ Neue Tour` | COPY.md §7 CTA |
| ~436 | `{n} von {n} Trips` (Footer) | `{n} von {n} Touren` | COPY.md §1 |
| ~450 | `Trip löschen` (Dialog-Titel) | `Tour löschen` | COPY.md §9 |

### `BottomNav.svelte`

| Zeile | Ist (❌) | Soll (✅) | Quelle |
|-------|---------|----------|--------|
| 10 | `label: 'Trips'` | `label: 'Touren'` | COPY.md §1 |

## Eyebrow-Status

Zeile 270 zeigt `WORKSPACE · TOUREN` — COPY.md §6 schreibt `TOUREN` vor. Der Präfix `WORKSPACE ·` ist kein expliziter Verstoß (kein Tabu-Wort), aber leicht von der Spec abweichend. **Kein Fix nötig** da kein Tabu-Wort enthalten.

## Nicht betroffene Elemente

- Code-Identifier (Variable `trips`, Funktionen `refetchTrips`, `deleteTarget: Trip`) → erlaubt (§9: "außer Code")
- API-Pfade `/api/trips` → erlaubt (technisches Detail)
- `Dialog.Description`-Text referenziert `deleteTarget?.name` → kein Tabu-Wort

## Existing Patterns

- Sidebar.svelte Zeile 28 zeigt bereits korrekt `'Meine Touren'`
- H1-Muster: `tracking-tight mt-1` (Issue #280 Referenz)
- Button-Präfix `+` wird nur im leeren Zustand verwendet (COPY §7)

## Risks & Considerations

- Rein textuelle Änderungen, keine Logik-Änderungen
- Empty-State-Body-Text weicht von bisherigem ab (kein Wizard-Step-Hinweis vorhanden) — COPY.md hat Vorrang
- `filteredTrips.length von trips.length Trips` ist technisch in einer `font-mono`-Zeile — dennoch Nutzer-sichtbar → muss korrigiert werden
