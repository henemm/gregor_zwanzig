# Context: Issue #268 – Trips-Liste Mobile Card-Stack

## Request Summary

Die Trips-Übersicht (`/trips`) zeigt auf Mobile (≤ 899 px) eine Tabelle mit kleinen Aktions-Icons (~30 px) unter dem 44-px-Touch-Target-Minimum. Ziel: Card-Stack-Layout pro Trip + Aktionen in einem `···`-Bottom-Sheet mit ≥ 44 × 44 px Touch-Target.

## Ist-Zustand

| Datei | Zustand |
|-------|---------|
| `frontend/src/routes/trips/+page.svelte` | Tabellen-Layout mit `shadcn-svelte` Table-Komponenten. Mobile: `hidden sm:` für Spalten Etappen + Zeitraum. Icons in `inline-flex gap-3` mit `size-3.5` (~14px Icon, ~30px Button). |
| `frontend/src/lib/utils/tripStatus.ts` | `deriveTripStatus()` – pure function, liefert `planned | active | paused | archived` |
| `frontend/src/lib/components/ui/dot/Dot.svelte` | Generische Dot-Komponente für Status-Visualisierung (tones: success/warning/danger/info + weather) |
| `frontend/src/app.css` | Breakpoints: `@custom-variant mobile { @media (max-width: 899px) }` / `desktop { @media (min-width: 900px) }`. Tokens `--g-paper-deep` und `--g-rule-soft` sind vorhanden. |

## Was geändert werden muss

### 1. TripCard (Mobile-View)
Neue Komponente oder inline-Block in `+page.svelte`:
- Links: Status-Dot (`deriveTripStatus` → Dot tone: `success`=active, `info`=planned, `warning`=paused, `danger`=archived)
- Rechts davon: Trip-Name (font-medium) + Zeile darunter: Etappen-Count + Zeitraum (mono, muted)
- Ganz rechts: `···`-Button (≥ 44 × 44 px Touch-Target)

### 2. Bottom-Sheet (Aktions-Menü)
Kein `shadcn-svelte`-Sheet-Komponente vorhanden → einfaches Overlay-Pattern:
- Fixed-positioned Panel von unten einblenden
- Aktionen: Report-Konfiguration, Wetter-Konfiguration, Bearbeiten, Löschen, ggf. Test-Reports
- Backdrop schließt das Sheet

### 3. Desktop unverändert
Tabellen-Layout ab ≥ 900 px bleibt exakt wie bisher.

## Bestehende Patterns / Komponenten

| Pattern | Wo |
|---------|-----|
| `@custom-variant mobile / desktop` | `app.css` – Tailwind-Erweiterung für 900px-Breakpoint |
| `deriveTripStatus()` | `frontend/src/lib/utils/tripStatus.ts` |
| `Dot` Komponente | `frontend/src/lib/components/ui/dot/` |
| BottomNav (Mobile-Fixed-Overlay) | `frontend/src/lib/components/ui/sidebar/BottomNav.svelte` – Referenz für fixed-bottom-Panels |
| Dialog-Pattern | `$lib/components/ui/dialog/` – shadcn-svelte – für Desktop-Dialoge |
| `Btn` Komponente | `$lib/components/ui/btn/` |

## Abhängigkeiten

**Upstream:** `Trip`-Interface (`frontend/src/lib/types.ts`), `api.get('/api/trips')`, alle bestehenden Dialog-Logiken im Script-Block
**Downstream:** Keine anderen Komponenten konsumieren `+page.svelte` direkt

## Risiken & Überlegungen

- Bottom-Sheet-Interaktion muss Scroll-Lock berücksichtigen (BottomNav ist auch fixed, kein Konflikt wenn z-index korrekt)
- Mobile BottomNav hat `z-50` → Bottom-Sheet braucht `z-60` oder höher
- Sheet schließen bei: Backdrop-Click, Escape-Key, nach Aktion
- Kein neues Design-Token nötig – alle relevanten Tokens existieren
- `sm:` Breakpoint in Tailwind = 640px, Projekt-Standard ist 900px → `desktop:` Klasse nutzen statt `sm:`
- Keine neue Datei nötig wenn Sheet inline in `+page.svelte` bleibt (Komponente bei Wachstum extrahieren)
