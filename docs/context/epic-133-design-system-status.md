# Context: Epic #133 — Design System & Tokens (Statuserhebung)

## Request Summary

Kontext-Erhebung für Epic #133. Ziel: Vollständigen Implementierungsstatus erfassen und klären, ob das Issue geschlossen werden kann oder noch Arbeit aussteht.

## Ergebnis: Epic #133 ist vollständig implementiert

Alle Scope-Items aus dem Issue sind in zwei Lieferläufen erledigt worden:

### Lauf A (Issues #141, #142, #145) — VERIFIED

| Scope-Item | Datei | Status |
|------------|-------|--------|
| CSS-Tokens (`--g-*` Namespace) | `frontend/src/app.css` | ✅ Implementiert |
| Schriften (Inter Tight + JetBrains Mono) | `frontend/src/app.html` | ✅ Implementiert |
| Sidebar-Navigation (Startseite / Trips / Orts-Vergleich / Einstellungen) | `frontend/src/lib/components/ui/sidebar/Sidebar.svelte` | ✅ Implementiert |
| Theme-Bridge (shadcn ↔ `--g-*`) | `frontend/src/app.css` | ✅ Implementiert (Issue #218) |
| Marken-CTAs auf `accent` | `frontend/src/lib/components/ui/btn/Btn.svelte` | ✅ Implementiert (Issue #219) |
| Button-Konsolidierung (Btn vs. Button) | `frontend/src/lib/components/ui/btn/` | ✅ Erledigt (Issues #212, #214, #215) |
| Topo auf Hero-Bereichen | `frontend/src/lib/components/ui/topo/TopoBg.svelte` | ✅ Implementiert (Issue #220) |
| Typography/Spacing-Tokens | `frontend/src/app.css` | ✅ Implementiert (Issue #208) |

### Lauf B (Issues #143, #144, #146) — VERIFIED (Adversary: VERIFIED)

| Scope-Item | Datei | Status |
|------------|-------|--------|
| Topo-Hintergrundmuster (`.g-topo` + `<TopoBg>`) | `frontend/src/lib/components/ui/topo/TopoBg.svelte` | ✅ |
| `<Btn>` Atom-Komponente | `frontend/src/lib/components/ui/btn/Btn.svelte` | ✅ |
| `<GCard>` Atom-Komponente | `frontend/src/lib/components/ui/g-card/GCard.svelte` | ✅ |
| `<Pill>` Atom-Komponente | `frontend/src/lib/components/ui/pill/Pill.svelte` | ✅ |
| `<Eyebrow>` Atom-Komponente | `frontend/src/lib/components/ui/eyebrow/Eyebrow.svelte` | ✅ |
| `<Dot>` Atom-Komponente | `frontend/src/lib/components/ui/dot/Dot.svelte` | ✅ |
| `<ElevSparkline>` (SVG-Höhenprofil) | `frontend/src/lib/components/ui/elev-sparkline/ElevSparkline.svelte` | ✅ |
| `/_design` Showcase-Route | `frontend/src/routes/_design/+page.svelte` | ✅ |

## Referenz-Dokumente

| Dokument | Beschreibung |
|----------|--------------|
| `docs/reference/design_system.md` | Single Source of Truth: alle Tokens, Farben, Komponenten-Verträge |
| `docs/reference/design_system_tokens.css` | CSS-Variablen-Referenz |
| `docs/specs/modules/epic_133_design_system_lauf_a.md` | Spec Lauf A (status: completed) |
| `docs/specs/modules/epic_133_design_system_lauf_b.md` | Spec Lauf B (status: completed) |
| `docs/artifacts/epic-133-design-system-lauf-b/validator-report.md` | Adversary Verdict: VERIFIED (12/12 ACs) |
| `docs/reference/sveltekit_best_practices.md` | Codifizierte Muster aus Lauf A & B |
| `frontend/e2e/design-system-lauf-b.spec.ts` | 10 E2E-Tests (alle grün) |

## Bewusst nicht implementierte Design-Vision-Tokens

Dokumentiert in `docs/reference/design_system.md` als bewusste Auslassung:
- `--g-paper-deep`, `--g-card`, `--g-card-alt`, `--g-rule`, `--g-rule-soft`
- `--g-ink-4` (vierte Ink-Stufe)
- `--g-accent-deep`, `--g-accent-soft`, `--g-accent-tint`
- Btn-Variant `quiet` → wird als `ghost` abgebildet

Diese Tokens werden bei konkretem Bedarf in separaten Issues erfasst.

## Aktuelle Verwendung der Atom-Komponenten

| Komponente | Genutzt in |
|------------|-----------|
| `ElevSparkline` | `StageCard.svelte`, `ActiveTripCard.svelte`, `BottomRow.svelte`, `_design`-Showcase |
| `Dot` | `Stepper.svelte`, `BriefingsTimeline.svelte`, `_design`-Showcase |
| `Btn` | Codebase-weit (Button-Migration Issue #215 abgeschlossen) |
| `Sidebar` | `+layout.svelte` (alle Routen) |

## Abhängigkeiten

- **Downstream:** Alle anderen Frontend-Epics (EPIC 2, 3, 4, 5, 7, 8, 9) nutzen die hier definierten Tokens und Atom-Komponenten als Fundament.
- **EPIC 9 — Email-Templates (#236):** Nutzt `design_system_tokens.css` als Referenz für `html.py`-Inline-CSS.

## Risiken & Offene Punkte

- **GitHub Issue #133 ist noch offen** — das Issue kann geschlossen werden, alle Scope-Items sind erledigt.
- **Drift-Risiko:** `design_system_tokens.css` und `frontend/src/app.css` können auseinanderlaufen. Issue #213 (Doku-Aktualisierung) wurde geschlossen und synchronisiert — bei künftigen Token-Änderungen beide Dateien gleichzeitig aktualisieren.
- **Kein Lauf C geplant** — es gibt keinen offenen GitHub-Issue der auf weiteres Design-System-Arbeit hinweist.

## Empfehlung

Epic #133 ist **vollständig abgeschlossen**. Das GitHub-Issue sollte geschlossen werden.
