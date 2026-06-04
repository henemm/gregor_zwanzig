# Context: Issue #580 — Design-Fidelity Trips-Liste 1:1 nach screen-trips.jsx

## Request Summary
Die Trips-Übersichtsseite (`/trips`) soll 1:1 aus der JSX-Vorlage `screen-trips.jsx` re-implementiert werden. Die aktuelle Svelte-Seite weicht im Desktop-Layout erheblich vom SOLL ab: keine Stats-Summary-Bar mit `SummaryStat`, kein Grid-basierter `TripRow` im Card-Container, keine `ActionBtn`-Reihe mit Einzelbuttons.

## SOLL-Design (screen-trips.jsx)

Hauptunterschiede IST → SOLL:

| Bereich | IST (aktuell) | SOLL (screen-trips.jsx) |
|---------|---------------|------------------------|
| Stats-Zeile | `<span>`-Werte mit Tailwind, nur `desktop:flex` | `SummaryStat`-Komponenten: value+label, `tone="accent"` für Aktiv |
| Table-Header | `<thead><th>` mit Tailwind | Grid `1.6fr 0.8fr 1.4fr auto`, `var(--g-paper-deep)` Hintergrund, Mono-Uppercase-11px |
| Zeilen-Layout | `<tr><td>` mit Tailwind-Klassen | Grid `1.6fr 0.8fr 1.4fr auto`, alternating `var(--g-paper-deep)` |
| Name-Zelle | Link + Mono-Caption | Dot (7px) + fett Name + Mono-Caption `· {label}` |
| Etappen-Zelle | versteckt in Name-Cell | Eigene Spalte, tabular-nums |
| Aktionen | Dropdown-Menu + Primary-Btn | 6× `ActionBtn`-Einzelbuttons + Separator, kein Dropdown |
| Footer | "N Trips · M versteckt" | "{N} von {M} Trips", Mono-11px |
| Suche | Input + Lucide Icon | Inline-SVG Suche, `--g-r-pill` rounded |
| Überschrift | "Meine Trips" | "Trips" (H1 fontSize:32, fontWeight:600) |
| Beschreibungstext | "Alle Trips auf einen Blick…" | Anderer Text (längere Beschreibung) |

## Neue Teilkomponenten laut JSX (Desktop-only, in +page.svelte inline oder als lokale Komponenten)

1. **`SummaryStat`** — value+label mit optionalem `tone="accent"` → Map auf `<Stat layout="inline">` (Stat-Atom ist bereits fertig in `$lib/components/atoms/Stat.svelte`)
2. **`TripRow`** — Grid-Zeile, alternating background, status-dot + name + Etappen + Zeitraum + ActionBtns
3. **`ActionBtn`** — 30×30px Button mit SVG-Icon, `--g-rule-soft` Border, `--g-r-2` Radius; 6 Typen: alert/weather/play/preview/edit/trash

## Mobile Layout bleibt erhalten

Der mobile Card-Stack (Issue #268/#413) und die Filter-Pills müssen unverändert bleiben. Nur der `desktop:block`-Bereich wird neu implementiert.

## Betroffene Dateien

| Datei | Änderungstyp |
|-------|-------------|
| `frontend/src/routes/trips/+page.svelte` | Haupt-Änderung: Desktop-Table-Bereich ersetzen |
| `frontend/src/routes/trips/issue_580.test.ts` | NEU: RED-Tests für AC-1/AC-2/AC-3 |

## Abhängigkeiten

| Komponente | Status | Pfad |
|-----------|--------|------|
| `Stat` (Atom) | ✅ vorhanden | `$lib/components/atoms/Stat.svelte` |
| `Card` (Atom) | ✅ vorhanden | `$lib/components/atoms/Card.svelte` |
| `Eyebrow` (Atom) | ✅ vorhanden | `$lib/components/atoms/Eyebrow.svelte` |
| `Btn` (Atom) | ✅ vorhanden | `$lib/components/atoms/Btn.svelte` |
| `tripStatus` | ✅ vorhanden | `$lib/utils/tripStatus.ts` |

## Vorhandene Tests (alle müssen grün bleiben)

- `issue_402.test.ts` — 4 Tests (pass) — Atomic-Migration Grundstruktur
- `issue_477_486.test.ts` — 14 Tests (pass) — Kebab-UX-Redesign, keine ui/-Importe
- `bug_596.test.ts` — unbekannt

## Risiken

1. **ActionBtn-SVGs** — JSX hat inline SVGs mit `stroke={c}`. Svelte benötigt Template-Syntax.
2. **Status-Mapping** — JSX hat `active/scheduled/completed/draft`, IST nutzt `aktiv/geplant/fertig/draft` via `tripStatus()`. Die Dot-Farbe muss über das bestehende `statusTone()` abgebildet werden.
3. **Bestehende Tests nicht brechen** — `issue_477_486.test.ts` prüft `status-caption`-Klasse, DropdownMenu, ConfirmDialog etc. — manche davon werden durch die Neuimplementierung obsolet oder ändern sich.
4. **Mobile unberührt** — Der mobile Card-Stack muss exakt gleich bleiben.
