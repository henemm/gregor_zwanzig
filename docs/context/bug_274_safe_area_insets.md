# Context: Bug #274 — Safe-Area-Insets

## Request Summary

Auf iPhones mit Home-Indikator (iPhone X und neuer) überlagert der Indikator die Sticky-Bottom-Bar im Trip-Edit (`/trips/[id]/edit`). Außerdem fehlt `viewport-fit=cover` im HTML-Head, ohne das `env(safe-area-inset-bottom)` auf iOS-Safari keinen Effekt hat.

## Befund

### Was fehlt

| Datei | Problem |
|-------|---------|
| `frontend/src/app.html:6` | Viewport-Meta hat kein `viewport-fit=cover` — ohne dieses Flag ist `env(safe-area-inset-bottom)` auf iOS Safari ohne Wirkung |
| `frontend/src/lib/components/edit/TripEditView.svelte:138` | `fixed bottom-0` Action-Bar hat kein `padding-bottom: env(safe-area-inset-bottom)` |

### Was bereits korrekt implementiert ist

| Datei | Safe-Area |
|-------|-----------|
| `frontend/src/lib/components/ui/sidebar/BottomNav.svelte:19` | ✅ `padding-bottom: env(safe-area-inset-bottom)` |
| `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte:109` | ✅ `padding-bottom: env(safe-area-inset-bottom, 0px)` |
| `frontend/src/routes/compare/+page.svelte:456` | ✅ `padding-bottom: env(safe-area-inset-bottom)` |
| `frontend/src/routes/trips/+page.svelte:632` | ✅ `padding-bottom: env(safe-area-inset-bottom)` |
| `frontend/src/app.css:155` | ✅ `.mobile-scroll-pad` mit `calc(64px + env(safe-area-inset-bottom))` |

## Betroffene Dateien

| Datei | Relevanz |
|-------|----------|
| `frontend/src/app.html` | Viewport-Meta — `viewport-fit=cover` ergänzen |
| `frontend/src/lib/components/edit/TripEditView.svelte` | Action-Bar — `padding-bottom` mit safe-area ergänzen |

## Bestehendes Muster

Das Muster im Projekt (aus BottomNav, TripWizardShell, trips/+page.svelte) ist einheitlich:
- Inline-Style: `style="padding-bottom: env(safe-area-inset-bottom, 0px);"` oder
- Inline-Style: `style="... padding-bottom: env(safe-area-inset-bottom);"` (ohne Fallback, funktioniert auch)

In TripEditView hat die Bar bereits `p-3` (12px via Tailwind) — der safe-area-Wert muss dazu addiert werden: `padding-bottom: calc(0.75rem + env(safe-area-inset-bottom, 0px))` damit das bestehende Padding erhalten bleibt.

## Abhängigkeiten

- Upstream: Keine — rein kosmetischer Fix
- Downstream: Keine — kein anderer Code abhängig von diesen Styles

## Risiken

- **Minimal.** Zwei isolierte Änderungen in nicht-logischen Bereichen (HTML-Head + CSS-Padding)
- `viewport-fit=cover` ist global und könnte theoretisch andere Sticky-Elemente beeinflussen, aber da alle anderen Elemente bereits safe-area-Padding haben, ist das unkritisch

## Scope

Ausschließlich die zwei identifizierten Lücken schließen. Die Issue-Checklist nennt auch „zukünftige BottomNav" und „zukünftige Bottom-Sheets" — BottomNav ist bereits implementiert (Issue #267) und hat das Padding. Bottom-Sheets (#269/#270) sind noch nicht implementiert, daher kein Handlungsbedarf jetzt.
