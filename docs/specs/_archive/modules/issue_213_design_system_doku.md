---
entity_id: issue_213_design_system_doku
type: module
created: 2026-05-16
updated: 2026-05-16
status: draft
version: "1.0"
tags: [frontend, docs, design-system]
issue: 213
---

<!-- Issue #213 — Design-System-Doku auf Ist-Stand aktualisieren -->

# Issue #213 — `design_system.md` Re-Synchronisation

## Approval

- [ ] Approved

## Zweck

`docs/reference/design_system.md` ist seit 2026-05-12 nicht mehr mit
`frontend/src/app.css` synchron — sie beschreibt den Soll-Zustand aus
dem ursprünglichen Anthropic-Design-Artifact, der inzwischen teilweise
abweichend implementiert wurde. Issues #208-#212 (alle CLOSED) haben den
Frontend-Stand gefestigt; jetzt kann die Spec dem Ist-Stand folgen.

**Tech-Lead-Entscheidung:** **Ist gewinnt.** Spec wird so umgeschrieben,
dass sie als Single-Source-of-Truth für künftige Entwickler/Agents zur
realen Codebase passt. Spec-Tokens die in Ist nicht existieren werden
entweder entfernt (Vision/Konzept) oder als „nicht implementiert"
markiert.

## Drift-Inventar (Spec vs Ist)

| Kategorie | Spec sagt | Ist (`app.css`) | Nach Fix in Spec |
|-----------|-----------|-----------------|------------------|
| Surfaces | `paper`, `paper-deep`, `card`, `card-alt`, `rule`, `rule-soft` | `paper`, `surface-0`, `surface-1`, `surface-2` | Surface-Tokens dokumentieren, alte Namen als "nicht implementiert" |
| Ink-Stufen | `ink`, `ink-2`, `ink-3`, `ink-4` (4) | `ink`, `ink-muted`, `ink-faint` (3) | Ist (3 Stufen) |
| Accent | `accent`, `accent-deep`, `accent-soft`, `accent-tint` | nur `accent` | Ist (1 Wert) + Hinweis dass Spec-Subtypes nicht implementiert |
| Semantic | `good`, `warn`, `bad`, `info` | `success`, `warning`, `danger`, `info` | Ist (Tailwind-kompatible Namen) |
| Wetter | `weather-rain/snow/thunder/sun/cloud` | `wx-rain/sun/wind/snow/thunder/fog` | Ist (kürzere Präfix, 6 Werte) |
| Radii | `r-1` (2px), …`r-pill` (999px) | `radius-xs/sm/md/lg/pill` (rem) | Ist (rem-Naming) |
| Spacing | `--g-s-1`…`--g-s-20` | identisch | unverändert ✓ |
| Type-Scale | `--g-text-xs`…`--g-text-5xl` | identisch | unverändert ✓ |
| Tracking | `--g-track-tight/normal/wide/caps` | identisch | unverändert ✓ |
| Elevation | `--g-shadow-1/2/3` (Hairline + Drop) | `--g-elev-1/2/3` (einfache Schatten) | Ist (Naming + Werte) |
| Btn-Variants | `primary`, `accent`, `ghost`, `quiet` (4) | `primary`, `accent`, `outline`, `ghost`, `secondary`, `destructive`, `link` (7) | Ist (alle 7) |
| Sidebar-Labels | „Heute", „Trips" | „Startseite", „Meine Touren", „Einstellungen" | Ist (3 Items) |

## Quelle / Source

- `docs/reference/design_system.md` (247 Zeilen) — Hauptdatei, wird grundlegend aktualisiert
- `docs/reference/design_system_tokens.css` (113 Zeilen) — Begleit-CSS, separater Stand-Hinweis am Anfang

## Acceptance Criteria

- **AC-1:** Given `docs/reference/design_system.md` / When ein Entwickler nach Surface-, Ink-, Semantic- oder Wetter-Tokens sucht / Then findet er ausschließlich die Namen, die in `frontend/src/app.css` tatsächlich definiert sind (`surface-0/1/2`, `ink-muted/faint`, `success/warning/danger`, `wx-*`); Spec-Wunsch-Namen sind klar als „Vision (nicht implementiert)" gekennzeichnet, falls überhaupt erwähnt

- **AC-2:** Given §6 (Komponenten) / When der Btn-Block gelesen wird / Then listet er alle 7 in `Btn.svelte` deklarierten Variants (`primary`, `accent`, `outline`, `ghost`, `secondary`, `destructive`, `link`) und alle 8 Sizes (`xs`, `sm`, `md`, `lg`, `icon`, `icon-xs`, `icon-sm`, `icon-lg`)

- **AC-3:** Given §10 (Drift-Block) / When er gelesen wird / Then ist er entweder entfernt oder durch einen aktuellen Block ersetzt, der den heutigen Zustand reflektiert; der Verweis auf nicht-existierendes `--g-surface-0` als „Pre-Migration-Stand" ist gestrichen

- **AC-4:** Given der Header der Spec / When er gelesen wird / Then trägt er Stand `2026-05-16` und referenziert Issue #213 als letzte Aktualisierung

- **AC-5:** Given `design_system_tokens.css` / When sie gelesen wird / Then trägt sie einen Kopf-Kommentar, der klarstellt: „Begleit-Datei zur Spec, kann von `app.css` abweichen; im Zweifel gilt `app.css`." (oder analoge Eindeutigkeit)

- **AC-6:** Given die `app.css`-Datei selbst / When sie geprüft wird / Then ist sie UNVERÄNDERT — keine Production-CSS-Änderung in diesem Issue

## Erwartetes Verhalten

### §1 Farben — Beispiel-Umbau

Surface-Tabelle ersetzen:
```markdown
### Surfaces
| Token | Hex | Verwendung |
|---|---|---|
| `--g-paper` | `#f6f4ee` | App-Hintergrund, leicht warmes Off-White |
| `--g-surface-0` | `#f6f4ee` | Alias für `--g-paper`, Surface-Basis |
| `--g-surface-1` | `#edeae1` | Erhöhte Surface (Card, gehobener Bereich) |
| `--g-surface-2` | `#e3dfd4` | Stärker erhöhte Surface (Modal, Sticky-Bar) |

**Vision (nicht implementiert):** `--g-paper-deep`, `--g-card`, `--g-card-alt`,
`--g-rule`, `--g-rule-soft` — siehe Anthropic-Design-Artifact, wenn Bedarf
besteht ggf. ergänzen.
```

### §6 Komponenten — Btn

Btn-Block ersetzen:
```markdown
### Button (`Btn`) — Implementiert in `frontend/src/lib/components/ui/btn/Btn.svelte`

- **Variants:** `primary` (default), `accent`, `outline`, `ghost`, `secondary`, `destructive`, `link`
- **Sizes:** `xs`, `sm`, `md` (default), `lg`, `icon`, `icon-xs`, `icon-sm`, `icon-lg`
- **Tag-Switch:** Render als `<a>` wenn `href` gesetzt, sonst `<button>`
- **Disabled-State:** ARIA-konform (`aria-disabled="true"`, `role="link"` + `tabindex={-1}` bei Links)
- **Tests:** SSR-Render-Tests im Spec-Archiv `issue_214_btn_feature_parity.md` (deaktiviert wegen Svelte-Loader, Issue #228)
```

### §10 — Drift-Block ersetzen

Komplett überarbeiten als „Stand 2026-05-16 nach Issues #208-#212". Tabelle
listet aktuelle Naming-Drift mit Notiz, dass die Spec **diesem** Stand folgt.

## Out-of-Scope

- **`app.css` ändern** — Ist gewinnt, Production-CSS bleibt.
- **Atom-Komponenten dokumentieren die nicht in Btn enthalten sind** (Pill, Card, Dot etc.) auf neuem Detail-Level — Issue beschreibt nur die genannten Drift-Stellen.
- **Neue Tokens hinzufügen** — falls etwas fehlt (z.B. `--g-rule` für Borders), eigener Issue.
- **`design_system_tokens.css` mit `app.css` automatisch synchronisieren** — bleibt manuell, Header-Hinweis genügt.

## Tests / Verifikation

- **Markdown-Lint:** Keine kaputten Markdown-Tabellen, Code-Blocks korrekt geschlossen.
- **Cross-Reference:** Stichprobe — sucht man nach `--g-good`, findet man **0 Treffer** in der aktualisierten Spec (Ist verwendet `--g-success`).
- **Code-Pfade:** `app.css` und `Btn.svelte` werden nicht angefasst — `git diff frontend/` → 0 Lines.

## Risiken & Migration

- **Risiko vernachlässigbar:** Reine Doku-Änderung.
- **Verständnis-Verlust für Designer:** Wer die Spec aus der Anthropic-Vision kennt, findet die neuen Namen erst. Begründet im Vision-Hinweis-Block.
- **Künftige Spec-Drift:** Tooling-mäßig keine Garantie gegen Re-Drift. Memory `reference_design_system.md` warnt schon, dass Spec/Ist-Drift zu beachten ist.
