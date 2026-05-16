# Context: Issue #213 — Design-System-Doku auf Ist-Stand aktualisieren

## Request Summary

`docs/reference/design_system.md` (247 Zeilen) ist die Spec aus dem
Anthropic-Design-Artifact vom 2026-05-12. Sie beschreibt einen Soll-Zustand,
der inzwischen NUR teilweise in `frontend/src/app.css` (324 Zeilen)
implementiert ist. Issue verlangt: Spec dem Ist-Stand angleichen
(Ist gewinnt) oder Drift explizit dokumentieren.

## Drift-Analyse (Spec vs Ist)

### Tokens — Farben

| Kategorie | Spec sagt | Ist (app.css) | Maßnahme |
|-----------|-----------|---------------|----------|
| Ink-Stufen | `ink`, `ink-2`, `ink-3`, `ink-4` (4 Stufen) | `ink`, `ink-muted`, `ink-faint` (3 Stufen) | Spec auf Ist (3 Stufen, andere Namen) |
| Surfaces | `paper`, `paper-deep`, `card`, `card-alt`, `rule`, `rule-soft` | nur `paper` | Spec: nur dokumentieren was IST, Rest als "nicht implementiert" |
| Semantic | `good`, `warn`, `bad`, `info` | `success`, `warning`, `danger`, `info` | Spec auf Ist (Tailwind-konforme Namen) |
| Wetter | `weather-rain/snow/thunder/sun/cloud` | `wx-rain/sun/wind/snow/thunder/fog` | Spec auf Ist (`wx-*`-Präfix + andere Werte) |
| Accent | `accent`, `accent-deep`, `accent-soft`, `accent-tint` | nur `accent` (`#c45a2a`) | Spec auf Ist (nur 1 Wert) |
| Radii | `r-1` (2px), `r-2` (4px), `r-3` (6px), `r-4` (10px), `r-pill` (999px) | `radius-xs/sm/md/lg/pill` (rem-basiert) | Spec auf Ist (rem-Naming) |

### Tokens — Typografie/Spacing (Issue #208 hat angeglichen)

Spec sagt `--g-text-xs..5xl` (9 Stufen), `--g-track-tight..caps`.
Ist hat `--g-text-xs..xl` (5 Stufen), `--g-track-tight..caps` ✓.

→ Spec auf Ist (5 statt 9 Text-Stufen, Tracking unverändert).

### Komponenten — Btn

Spec sagt Variants: `primary`, `accent`, `ghost`, `quiet`.
Ist (`Btn.svelte`) hat: `primary`, `accent`, `outline`, `ghost`, `secondary`, `destructive`, `link` (7 Variants).
→ Spec auf Ist (alle 7 Variants dokumentieren).

### Sidebar — Labels

Spec sagt: „Heute", „Trips".
Ist: „Startseite", „Meine Touren" (+ „Einstellungen" laut Issue #210).
→ Spec auf Ist + Einstellungen ergänzen.

## Related Files

| Datei | Rolle |
|-------|-------|
| `docs/reference/design_system.md` | 247 Zeilen Spec — zu aktualisieren |
| `docs/reference/design_system_tokens.css` | 113 Zeilen Begleit-CSS — vermutlich auch veraltet, ggf. anpassen |
| `frontend/src/app.css` | 324 Zeilen — Quelle der Wahrheit (Tokens) |
| `frontend/src/lib/components/ui/btn/Btn.svelte` | Btn-Komponente — Quelle für Variants/Sizes |

## Dependencies

- **#208** (Typography/Spacing) — CLOSED ✓
- **#209** (Topo) — CLOSED ✓
- **#210** (Sidebar) — CLOSED ✓
- **#211** (Fonts) — CLOSED ✓
- **#212** (Button) — CLOSED ✓ (heute)

Alle Vorgänger fertig — Pfad für #213 ist frei.

## Strategie

**Pragmatische Re-Synchronisation:** Spec dem Ist-Stand angleichen, nicht
Ist dem Spec-Stand. Das ist die Issue-Empfehlung. Spec-Sektionen:

1. **§1 Farben:** Token-Tabellen ersetzen mit den 16 Tokens aus app.css. Spec-Namen die NICHT in Ist sind als „nicht implementiert (Design-Vision)" markieren oder entfernen.
2. **§2 Typografie:** Schon angeglichen durch #208 — Tabelle auf 5 Stufen reduzieren.
3. **§3 Spacing:** `--g-s-*` ist NICHT in app.css; entweder Tailwind-Spacing dokumentieren oder als Vision markieren.
4. **§4 Radii:** Naming-Umbau `r-*` → `radius-*` (rem-Werte).
5. **§5 Elevation:** Prüfen ob Shadow-Tokens in app.css existieren.
6. **§6 Komponenten:** Btn-Variants auf 7 erweitern; Pill/Card/Eyebrow/Dot prüfen.
7. **§7-9 Layout/Logo/Screen-Kanon:** wenig Drift, Stand-Header aktualisieren.
8. **§10 Drift:** Komplett ersetzen — alter Block referenziert nicht-existierende `--g-surface-0`.
9. **Header:** Stand auf 2026-05-16.

## Risks & Considerations

- **Risiko gering:** Reine Doku-Änderung, keine Code-Auswirkung.
- **Wichtigste Quelle:** `app.css` `@theme`-Block + `Btn.svelte` Type-Definitionen.
- **`design_system_tokens.css`:** Nicht direkt verlinkt aus Code (nur Doku-Begleit) — kann ggf. ebenfalls aktualisiert oder mit Drift-Hinweis versehen werden.

## Scope

1 Datei groß überarbeiten (~100-150 Edit-Zeilen), 1 Datei evtl. kleinere Updates (~20 Zeilen). Klein bis mittel.
