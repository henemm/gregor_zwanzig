---
entity_id: epic_133_tokens_and_topo
type: context
created: 2026-05-13
issues: [208, 209]
parent: 133
---

# Context: Epic #133 — Token-Familie nachziehen + Topo-Muster sichtbar machen

## Request Summary

Zwei eng verwandte Sub-Stories aus Epic #133 in einem Workflow:
- **#208**: Typography-, Spacing- und Tracking-Tokens aus `design_system_tokens.css` in `app.css` nachziehen
- **#209**: Topo-Hintergrundmuster auf die Spec-Geometrie (Ellipsen) umstellen UND sichtbar machen

Beide ändern ausschließlich `app.css` (#208) bzw. `app.css` + `TopoBg.svelte` + zwei Aufruferstellen (#209).

## #208 — Token-Diff

| Token-Gruppe | Status in app.css | Spec |
|---|---|---|
| Surface, Ink, Semantic, Wetter, Radii, Elevation, Font-Family | vorhanden | Drift bei Namen — Klärung in #213, nicht in #208 |
| **Type Scale (`--g-text-xs..-5xl`)** | FEHLT KOMPLETT | 9 Werte aus Spec übernehmen |
| **Tracking (`--g-track-tight/normal/wide/caps`)** | FEHLT KOMPLETT | 4 Werte aus Spec übernehmen |
| **Spacing Grid (`--g-s-1..-20`)** | FEHLT KOMPLETT | 11 Werte aus Spec übernehmen |

Quelle: `/home/hem/gregor_zwanzig/docs/reference/design_system_tokens.css` Z. 41–78.

## #209 — Topo aktueller vs. Soll-Stand

**Ist (`app.css` Z. 85–92):**
```css
.g-topo {
  background-image:
    radial-gradient(circle at 50% 50%, ..., var(--g-ink) ..., transparent ...),
    radial-gradient(circle at 50% 50%, ..., var(--g-ink) ..., transparent ...);
  background-size: 60px 60px;
  opacity: var(--g-topo-opacity, 0.04);
}
```
Effekt: 2 konzentrische Punkt-Ringe auf 60×60-Raster, hart-schwarz multipliziert mit ~0.04–0.06 Opacity → praktisch unsichtbar.

**Spec (`design_system_tokens.css` Z. 94–102):** 5 organische Ellipsen (800×400px bis 900×450px), an verschiedenen Positionen (20%/30%, 22%/32%, 24%/34%, 80%/70%, 78%/68%), alle mit `rgba(26,26,24,0.025–0.035)` und `background-color: var(--g-paper)`.

**Problem mit literarer Übernahme:**
- Spec setzt `background-color: var(--g-paper)` direkt im `.g-topo`. Die `TopoBg`-Komponente ist aber ein **Overlay** (`absolute inset-0`) — die Hintergrundfarbe würde alles darunter verdecken.
- Die rgba-Alphas in der Spec (0.025–0.035) sind sehr niedrig. Multipliziert mit der zusätzlichen `opacity` der TopoBg-Komponente bleibt nichts sichtbares.

**Pragmatische Lösung:**
- Geometrie aus Spec übernehmen (5 Ellipsen statt 2 Circles)
- rgba-Alphas auf mittlere Werte (0.10–0.14) anheben, damit das Muster sichtbar wird ohne dass die Wirkung von der `opacity` der TopoBg-Komponente abhängt
- `background-color` weglassen (Overlay-Pattern bleibt erhalten)
- TopoBg-Komponente: Default-Prop `opacity` von `0.04` auf `0.5` anheben, damit der Default sichtbar ist
- Aufrufer (`ActiveTripCard.svelte`, `_design/+page.svelte`): hartkodierte `opacity={0.06}` entfernen oder auf `opacity={0.5}` setzen, damit sie nicht weiter den Default überschreiben

## Datei-Plan

| Art | Datei | Zweck | LoC |
|---|---|---|---|
| EDIT | `frontend/src/app.css` | 24 neue Tokens (#208) + Topo-Geometrie (#209) | +30 / -3 |
| EDIT | `frontend/src/lib/components/ui/topo/TopoBg.svelte` | Default-Prop `opacity` auf `0.5` | +0/-0 (1 Wert) |
| EDIT | `frontend/src/routes/_cockpit/ActiveTripCard.svelte` | `opacity={0.06}` entfernen (Default greifen lassen) | -0 (1 Attribut weg) |
| EDIT | `frontend/src/routes/_design/+page.svelte` | dito | -0 (1 Attribut weg) |
| NEU | `frontend/e2e/tokens-and-topo.spec.ts` | Playwright-Tests für Tokens + Topo-Struktur | ~50 |
| **Summe** | | | **~80 LoC** |

Unter Default 250er-Limit, kein Override nötig.

## Test-Strategie

**E2E (Playwright) `tokens-and-topo.spec.ts`:**

**#208 — Tokens vorhanden:**
- AC-1: `getComputedStyle(document.documentElement).getPropertyValue('--g-text-md')` liefert `"15px"`
- AC-2: `--g-s-4` liefert `"16px"`
- AC-3: `--g-track-wide` liefert `"0.06em"`
- (Ein einzelner Test prüft alle drei stellvertretend — vollständige Token-Liste in Spec dokumentiert)

**#209 — Topo-Struktur:**
- AC-4: `getComputedStyle(<.g-topo>).backgroundImage` enthält Substring `"ellipse"`
- AC-5: `getComputedStyle(<.g-topo>).backgroundImage` enthält 5x `"radial-gradient"`
- AC-6: TopoBg-Komponente rendert mit Opacity >= 0.4 (über Inline-Style oder Default)

**Visuelle Regression:** kein Snapshot-Test — fragil. Sichtprüfung post-deploy via Screenshot des `/_design`-Showcase.

## Risiken

| # | Risiko | Mitigation |
|---|---|---|
| R1 | Höhere Topo-Opacity könnte ActiveTripCard zu unruhig machen | Visuelle Sichtprüfung post-deploy; Opacity ist von Aufrufer override-bar (0.3 statt 0.5 falls zu viel) |
| R2 | Neue Type-Scale-Tokens werden noch nicht genutzt | Issue #213 dokumentiert Migrations-Pfad; aktuelle Komponenten brechen nicht |
| R3 | Tracking-Werte aus Spec (`--g-track-wide: 0.06em`) weichen von Issue-Body (`0.04em`) ab | Spec ist die maßgebliche Quelle — `0.06em` übernehmen, Issue-Body war ungenau |
| R4 | `--g-text-md` vs `--g-text-base` Naming: Spec nutzt `-md`, Issue-Body sagt `-base` | Spec gewinnt — `-md` |

## Bekannte Limitierungen (für Spec-„Known Limitations")

- Migration der Tailwind-Klassen (`text-sm` → `text-[var(--g-text-sm)]` etc.) ist nicht in Scope — die neuen Tokens stehen ab jetzt zur Verfügung, ein bewusster Refactor-Sprint kommt später.
- Token-Naming-Drift (Spec `--g-paper` vs. Ist `--g-surface-0`, Spec `--g-good` vs. Ist `--g-success`) bleibt vorerst bestehen — wird in #213 final geklärt.
- Tracking-Wert `--g-track-wide: 0.06em` weicht von Issue #208 (`0.04em`) ab; Spec ist maßgeblich.
