# Context + Analyse: Issue #238 — Profil-Signaturen im Design-System

Teil von Epic #236.

## Request Summary

Pro `ActivityProfile` (Wintersport, Wandern, Summer-Trekking, Allgemein) eine
visuelle Signatur (Akzentfarbe + Icon + Eyebrow-Text) im Design-System
verankern. Voraussetzung dafür, dass die kommenden Mail-Renderer-Umbauten
profil-bewusst werden, ohne pro Renderer eigene Hex-Werte/Icons zu erfinden.

## Relevante Dateien

| Datei | Rolle |
|-------|-------|
| `frontend/src/app.css` (49–126) | Live-Tokens, **Single Source of Truth** |
| `docs/reference/design_system_tokens.css` (1–98) | Begleit-CSS, muss mirrored sein |
| `docs/reference/design_system.md` (1–274) | Verbindliche Doku v2 |
| `frontend/src/lib/types.ts:68` | `type ActivityProfile = 'wintersport' \| 'wandern' \| 'allgemein' \| 'summer_trekking'` — schon da |
| `frontend/src/lib/utils/` | Helper-Konvention: `*.ts` mit named exports + `*.test.ts` |
| `frontend/src/lib/components/ui/eyebrow/Eyebrow.svelte` | Existiert, im Showroom wiederverwendbar |
| `frontend/src/lib/components/ui/dot/Dot.svelte` | Existiert, im Showroom wiederverwendbar |
| `frontend/src/routes/_design/+page.svelte` (1–138) | Showroom — bestehende Sektionen Atoms / Topo / Sparkline |

## Token-Design (Empfehlung Plan-Agent)

| Profil | Token | Hex | Begründung |
|--------|-------|-----|------------|
| Wintersport | `--g-profile-wintersport` | `#4a7fb5` | Alias zu `--g-wx-rain` — kühles Alpinblau (Schnee+Eis) |
| Wandern | `--g-profile-wandern` | `#3a7d44` | Alias zu `--g-success` — Waldgrün |
| Summer-Trekking | `--g-profile-summer-trekking` | `#c45a2a` | Alias zu `--g-accent` — Burnt-Orange (Standard-Akzent) |
| Allgemein | `--g-profile-allgemein` | `#6b675c` | Nahe `--g-ink-muted #5c5a52`, neutral |

Begründung der Aliasing-Strategie: Alle Werte existieren schon im Design-System
(`--g-wx-rain`, `--g-success`, `--g-accent`). Neue Tokens dokumentieren nur die
Verwendungs-Absicht („dieser Wert ist für Profile X gemeint"), führen aber
keinen neuen Farbwert ein → keine zusätzliche Marken-Komplexität.

Kebab-Case im CSS (`--g-profile-summer-trekking`), Snake-Case im TS-Type
(`summer_trekking`) — Mapping im Helper.

## Architektur

**Trennung Token vs. Helper:**
- CSS-Tokens (`app.css` + `tokens.css`) tragen nur die Farben
- TS-Helper `profileSignature(profile)` trägt Icon, Eyebrow-Label, und das
  Hex-Fallback (für Mail-Inline-CSS, das keine Custom-Properties versteht)

Helper-Signatur:
```ts
type ProfileSignature = {
  accent: string;          // `var(--g-profile-wintersport)`
  accentFallback: string;  // `#4a7fb5` (für Outlook/Mail)
  icon: string;            // unicode glyph, z.B. `❄`
  eyebrow: string;         // `Wintersport`
};
function profileSignature(profile: ActivityProfile): ProfileSignature;
```

## Implementierungs-Reihenfolge

1. `app.css` — 4 Token-Zeilen einfügen (nach `--g-wx-*`, Z. 79)
2. `design_system_tokens.css` — identisch mirroren
3. `profileSignature.ts` — Helper
4. `profileSignature.test.ts` — Tests (TDD-RED zuerst)
5. `design_system.md` — neuer Abschnitt zwischen §9 (Z. 224) und §10 (Z. 243)
6. `_design/+page.svelte` — neue Showroom-Sektion mit 4 Profil-Karten

## LoC-Budget

| Datei | LoC |
|-------|-----|
| `app.css` | +6 |
| `design_system_tokens.css` | +6 |
| `profileSignature.ts` | ~45 |
| `profileSignature.test.ts` | ~80 |
| `design_system.md` | ~25 |
| `_design/+page.svelte` | ~35 |
| **Summe** | **~197 / 250** |

Innerhalb des Workflow-Limits.

## Test-Strategie

- Unit: `profileSignature.test.ts` — Shape-Tests pro Profil, Hex-Pattern-Check
  für `accentFallback`, Default-Fallback auf `allgemein` für unbekannte
  Eingaben. Pattern wie `alertMetricLabels.test.ts`.
- Keine Snapshot-Tests auf Hex-Werten (zu fragil)
- Visueller Sichttest: `/_design`-Showroom mit 4 Profil-Karten manuell prüfen
- Kein E2E-Playwright für rein dekorative Karten

## Risiken

- **Drift `app.css` ↔ `tokens.css`**: bekanntes Dauerproblem (Issue #213).
  Mitigation: nur 4 Zeilen je Datei, manuell vergleichbar
- **Marken-Kohärenz**: Wandern-Grün könnte als „OK-Status" missgelesen werden.
  Mitigation: in der UI nie Farbe allein zeigen — immer mit Eyebrow + Icon
- **Kontrast**: `#c45a2a` auf `--g-surface-2 #e3dfd4` ist ~3.8:1, AA-Fail für
  Text. Profil-Akzent nur dekorativ verwenden, nicht als Textfarbe
- **Wetter-Tokens-Drift bleibt**: `--g-wx-*` (app.css) vs `--g-weather-*`
  (tokens.css) ist nicht Scope dieses Sub-Issues — eigener Issue-Fix nötig

## Out of Scope

- Mail-Renderer-Umbau (eigene Sub-Issues 3–8 von Epic #236)
- Frontend-Komponenten, die das Profil bereits zeigen (Trip-Hero etc.)
- Wetter-Tokens-Drift-Cleanup
