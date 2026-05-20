# Context: Issue #272 — iOS-Auto-Zoom durch Font-Size < 16px

## Request Summary

iOS Safari zoomt beim Fokussieren von `<input>`, `<select>` und `<textarea>` automatisch ein, wenn deren `font-size < 16px` ist. Im Frontend nutzen viele Elemente Tailwind-Klassen `text-sm` (13px) oder `text-xs` (11px) — das löst den Zoom aus.

## Root Cause

`input.svelte` (die wiederverwendbare UI-Komponente) macht es **bereits richtig**: `text-base md:text-sm` — d.h. 16px auf Mobile, ab `md` (768px+) dann 13px. Aber zahlreiche Svelte-Seiten und Sections nutzen **raw** `<input>`/`<select>` mit fest kodiertem `text-sm`, ohne das responsive Muster.

## Betroffene Dateien

| Datei | Elemente | Problem |
|-------|----------|---------|
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` | `<select>` Z.176, Z.237, Z.379 | `text-sm` |
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` | Buttons Z.184, Z.193, Z.245, Z.254 | `text-xs` |
| `frontend/src/lib/components/WeatherConfigDialog.svelte` | `<select>` Z.174 | `text-sm` |
| `frontend/src/lib/components/edit/EditWeatherSection.svelte` | `<select>` Z.175 | `text-sm` |
| `frontend/src/lib/components/compare/LocationsRail.svelte` | `<input>` Z.91 | `text-sm` |
| `frontend/src/routes/register/+page.svelte` | 3× `<input>` | `text-sm` |
| `frontend/src/routes/login/+page.svelte` | 2× `<input>` | `text-sm` |
| `frontend/src/routes/account/+page.svelte` | 7× `<input>` | `text-sm` |
| `frontend/src/routes/trips/+page.svelte` | `<input>`/`<select>` | `text-sm` |
| `frontend/src/routes/compare/+page.svelte` | `<select>` Z.316 | `text-sm` |
| `frontend/src/lib/components/trip-detail/SavePresetDialog.svelte` | `<textarea>` | prüfen |

## Bestehende Muster

- **`input.svelte`:** `text-base md:text-sm` — korrekt, deckt `<input>`-Komponente ab
- Tailwind `md:`-Breakpoint = 768px (Standard, kein custom config)
- Media-Queries im Projekt: 640px, 720px, 960px — kein konsistenter Mobile-Breakpoint
- `--g-text-sm` = 13px, `--g-text-xs` = 11px (Design-Token-Definitionen in `app.css`)

## Fix-Strategie

**Option A — Globale CSS-Regel in `app.css`** (empfohlen):
```css
@media (max-width: 767px) {
  input, select, textarea { font-size: 16px; }
}
```
→ Deckt alle Raw-Elemente ab, konsistent mit `input.svelte`, keine Einzeländerungen, zero Drift-Risiko.

**Option B — Per-Komponente:** `text-sm` → `text-base md:text-sm` in 30+ Stellen.

## Abhängigkeiten

- `frontend/src/app.css` — enthält Design-Tokens + globale Styles (kein Media-Query für Inputs vorhanden)
- `frontend/src/lib/components/ui/input/input.svelte` — Referenz-Implementierung des korrekten Patterns
- Kein Backend-Einfluss

## Risiken

- **Option A:** `!important` nicht nötig, da kein `font-size`-Override auf Input-Ebene in app.css existiert; Tailwind-Klassen sind aber spezifischer — ggf. doch `!important` für `text-sm`-Overrides auf `<select>` nötig
- **iOS-Grenze:** Exakt 16px, nicht 15px — `--g-text-md` (15px) reicht nicht!
- Buttons mit `text-xs` in EditReportConfigSection: auf Mobile ggf. durch größere Variante ersetzen, um Tappability zu wahren

## Scope-Empfehlung

Globale CSS-Regel (Option A) + prüfen ob `text-xs`-Buttons touch-freundlich genug bleiben (min-height 44px schon vorhanden?).
