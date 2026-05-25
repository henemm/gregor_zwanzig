# Context: Issue #370 — Brand-Bibliothek `lib/brand/` (Berg+Blitz-Glyph + Wordmark-Lockup)

## Request Summary

Anlegen des kanonischen Brand-Verzeichnisses `frontend/src/lib/brand/` mit 6 Svelte-Komponenten (BrandIcon, BrandIconSquare, BrandWordmark, BrandUserBadge, BrandSidebar, BrandShell), 1:1 portiert aus `brand-kit.jsx`. Der Berg+Blitz-Glyph wird byte-genau übernommen. Schließt zugleich **#279** (Sidebar zeigt Glyph statt reiner Text-Wordmark). Teil von **Epic #368** (Atomic-Design-Migration), Migrations-Schritt 2 aus `body-15`.

## Related Files

| Datei | Relevanz |
|------|-----------|
| `docs/design-requests/issue_15_atomic_design/spec/brand-kit.jsx` | **Kanonische Quelle** — alle 6 Komponenten + SVG-Pfade byte-genau hierher delegieren |
| `docs/design-requests/issue_15_atomic_design/spec/body-15-atomic-design-library.md` | Master-Spec: §Brand-Katalog, §Migration Schritt 2, Acceptance Criteria, Test-Hooks |
| `frontend/src/lib/components/ui/wordmark/Wordmark.svelte` | Bestehende Text-Wordmark (#293) — wird ersetzt; Import-Pfad muss als Alias erhalten bleiben (Backward-compat) |
| `frontend/src/lib/components/ui/sidebar/Sidebar.svelte:56` | Nutzt `<Wordmark size="md" />` — bekommt nach Migration den Glyph (#279) |
| `frontend/src/lib/components/ui/sidebar/TopAppBar.svelte:34` | Nutzt `<Wordmark size="sm" />` |
| `frontend/src/routes/login/+page.svelte:13` | Nutzt `<Wordmark size="lg" href="/" />` — **einzige Stelle mit `href`-Prop** |
| `frontend/src/routes/_design/+page.svelte:194-196` | Showcase nutzt Wordmark in sm/md/lg |
| `docs/specs/modules/issue_369_token_bridge.md` | **Direkte Abhängigkeit** — liefert die Tokens, die BrandWordmark braucht |
| `frontend/src/app.css` | Token-Quelle; `--g-font-mono`, `--g-ink-4` fehlen aktuell (kommen via #369) |

## Existing Patterns

- **Aktuelle Komponenten-Struktur:** `$lib/components/ui/<name>/<Name>.svelte` (z. B. `ui/wordmark/`, `ui/eyebrow/`, `ui/sidebar/`). Die Atomic-Struktur (`lib/brand/`, `lib/components/atoms/`) existiert **noch nicht** — `lib/brand/` ist komplett neu.
- **Svelte 5 Runes:** Bestehende Komponenten nutzen `$props()` mit typisiertem `interface Props` und `<script lang="ts">` (siehe `Wordmark.svelte`). C2 der Master-Spec fordert genau das.
- **Token-Disziplin:** Komponenten setzen Farben via `var(--g-*)`, kein Inline-Hex (C1). Ausnahme: der Blitz-Akzent im SVG-Pfad darf hart bleiben, falls Token-Substitution dort technisch nicht geht.
- **Backward-compat per Alias:** `brand-kit.jsx` exportiert alte Namen (`WordmarkBrand`) als Alias. Analog soll der alte `Wordmark`-Import nutzbar bleiben (C6 / AC).
- **JSX→Svelte-Portierung:** Inline-`style={{...}}`-Objekte aus dem JSX werden zu Svelte-`style`/`<style>`; px-Maße aus den SIZES-Tabellen übernehmen.

## Dependencies

- **Upstream (was #370 braucht):**
  - **#369 Token-Bridge** — BrandWordmark referenziert `--g-font-mono`, `--g-ink-4` (Punkt-Farbe), `--g-accent`, dunkle Varianten. `--g-font-mono` und `--g-ink-4` sind aktuell **nicht** in `app.css` (nur `--g-accent`, `--g-paper`, `--g-paper-deep`, `--g-rule-soft` vorhanden). BrandSidebar braucht zusätzlich `--g-paper-deep`, `--g-rule`, `--g-rule-soft`, `--g-accent-deep`, `--g-r-3`, `--g-r-pill`, `--g-ink-2/3`. Ohne die Bridge rendert der Wordmark optisch falsch (Mono-Font + Punktfarbe fehlen).
  - `brand-kit.jsx` als kanonische Geometrie-/Maß-Quelle.
- **Downstream (was #370 nutzt):**
  - Sidebar, TopAppBar, Login, `_design`-Showcase importieren die Wordmark → müssen auf `BrandWordmark` umziehen bzw. über den Alias weiterlaufen.
  - Epic #368-Folge-Issues (Atoms #371, Molecules #372, Mobile #373, Showcase #374) bauen auf `lib/brand/` als unterste Schicht auf — Migrations-Schritt 2 Punkt 1–4.

## Existing Specs

- `docs/specs/modules/issue_369_token_bridge.md` — Token-Bridge (Entwurf, wartet auf Approval), direkte Voraussetzung.
- `docs/specs/modules/issue_293_wordmark.md` — bisherige Text-Wordmark, die #370 ablöst.
- `docs/design-requests/issue_15_atomic_design/spec/body-15-atomic-design-library.md` — Master-Spec des Epics.

## Risks & Considerations

- **R1 — Token-Abhängigkeit zu #369:** Ohne gemergte Token-Bridge fehlen `--g-font-mono`/`--g-ink-4`; der Wordmark würde mit Fallback-Font und falscher Punktfarbe rendern. Reihenfolge #369 → #370 einhalten oder im Fix berücksichtigen. **Spec muss diese Abhängigkeit explizit nennen.**
- **R2 — `href`-Verlust:** Die alte `Wordmark` ist ein `<a href>`. `BrandWordmark` aus `brand-kit.jsx` hat **kein** `href`. Login + Sidebar erwarten ggf. einen Klick-Link zur Home. Backward-compat-Alias muss das Link-Verhalten bewahren (Wrapper) — sonst bricht die Navigation.
- **R3 — Byte-Genauigkeit SVG:** Blitz `M48 11 L41 23 L45 23 L43 29 L50 17 L46 17 Z`, Bergkamm `M3 54 L18 22 L29 38 L38 26 L52 50 L61 54 Z`. AC fordert byte-genaue Übernahme — keine Auto-Formatierung/Prettier-Drift im Pfad.
- **R4 — Parallel-Sessions / belegter Hauptordner:** `git status` zeigt uncommittete Fremd-Arbeit (#366: `comparison_*.py` + `ChannelPreviewBlock.svelte` + golden files; #369: Token-Bridge-Spec; aktiver Fremd-Workflow `bug-274`). **Implementierung von #370 muss in einem isolierten `gz-workspace` laufen**, nicht im Hauptordner (Konvention „ein Projektordner = eine Session"). Phase 1 (read-only + additives Context-Doc) ist davon unberührt.
- **R5 — Scope-Disziplin:** #370 liefert NUR die 6 Brand-Dateien + Migration der 4 Wordmark-Verwendungsstellen + Backward-compat-Alias. Atoms/Molecules/Mobile/Showcase sind separate Folge-Issues (#371–374). LoC-Limit 250 im Auge behalten (6 neue Svelte-Dateien können das sprengen → ggf. `loc_limit_override`).
- **R6 — `BrandSidebar`/`BrandShell` vs. bestehende Sidebar:** `brand-kit.jsx` enthält eine vollständige eigene `BrandSidebar`/`BrandShell`. Die App hat bereits eine `ui/sidebar/Sidebar.svelte`. Hier ist zu klären (Phase 2/Spec), ob die bestehende Sidebar auf BrandSidebar umzieht oder ob BrandSidebar zunächst nur als Library-Baustein existiert (Migration der Screens ist Schritt 3, separate Issues).

---

## Analyse-Ergebnisse (Phase 2)

### Neue, entscheidende Befunde

1. **Bestehender E2E-Test wird brechen:** `frontend/e2e/issue-293-wordmark.spec.ts` (168 Zeilen, AC-1–AC-8) prüft u. a.:
   - Selektor `a[aria-label="Gregor Zwanzig — Home"]` (Link!) → muss erhalten bleiben.
   - Caption-Text **lowercase** `"v0.20 · wetter-briefing"`. brand-kit gibt aber `caption="V0.20 · Wetter-Briefing"` mit `text-transform: uppercase` → sichtbar `"V0.20 · WETTER-BRIEFING"`. **Case-sensitiver Test bricht.**
   - CSS-Klassen `.wordmark__zwanzig` / `.wordmark__dot` + deren Farben. Neue Struktur ändert das.
   - Klick navigiert zu `/`.
   → **Der Test muss als Teil von #370 aktualisiert werden** (#293 wird offiziell abgelöst).

2. **Backward-compat — sauberster Weg:** Kein `index.ts` im wordmark-Ordner; alle 4 Stellen sind Default-Imports `from '$lib/components/ui/wordmark/Wordmark.svelte'`. Empfohlene Strategie: **alte `Wordmark.svelte` wird zum Thin-Wrapper**, der `BrandWordmark` (`icon="left"`) rendert, das `<a href>` + `aria-label="Gregor Zwanzig — Home"` umschließt und `size` durchreicht. So bleiben alle 4 Imports byte-gleich, der Link bleibt erhalten (R2 gelöst), und Sidebar/TopAppBar/Login bekommen automatisch den Glyph (#279).

3. **Token-Lücke exakt vermessen (Abhängigkeit #369):** Von 14 gebrauchten Tokens **fehlen 9** in `app.css`: `--g-ink-4`, `--g-ink-3`, `--g-ink-2`, `--g-font-mono`, `--g-font-sans`, `--g-r-3`, `--g-r-pill`, `--g-rule`, `--g-accent-deep`. **Alle 9 liefert #369** (tokens.css). Insbesondere `--g-font-mono`/`--g-ink-4` (für die Mono-Typo + Punktfarbe des Wordmarks) und `--g-rule`/`--g-accent-deep`/`--g-r-3` (für BrandSidebar). → **#370 setzt #369 als gemergt voraus.**

### Architektur-Entscheidung (1:1-Portierung, keine Designfreiheit)

Die Geometrie/Maße/Token-Namen sind durch `brand-kit.jsx` kanonisch vorgegeben (body-15 §Referenz-Dateien: brand-kit hat höchste Autorität). #370 portiert 1:1 nach Svelte 5 (`<script lang="ts">` + `interface Props` + `$props()`, Inline-SVG, scoped `<style>` — Konvention wie `Btn.svelte`/`Dot.svelte`).

**Scope-Grenze BrandSidebar/BrandShell:** Werden als **Library-Bausteine** angelegt (für Showcase #374 + spätere Screen-Migration), aber die produktive `ui/sidebar/Sidebar.svelte` wird in #370 **nicht** auf BrandSidebar umgebaut (das ist body-15 Migrations-Schritt 3, eigenes Issue). In #370 ändert sich an der echten App **nur das Logo** (Glyph erscheint) via Wordmark-Wrapper.

### Scope-Schätzung

| Kategorie | Dateien | LoC (grob) |
|-----------|---------|-----------|
| Neu `lib/brand/` | BrandIcon, BrandIconSquare, BrandWordmark, BrandUserBadge, BrandSidebar, BrandShell | ~370 |
| Neu Barrel | `lib/brand/index.ts` | ~10 |
| Umbau | `ui/wordmark/Wordmark.svelte` → Thin-Wrapper | ~30 |
| Test-Update | `e2e/issue-293-wordmark.spec.ts` | ~40 |
| **Summe** | **~9 Dateien** | **~450 LoC** |

→ **Überschreitet LoC-Limit 250** (Library-Anlage inhärent) → `loc_limit_override 500` setzen. **Überschreitet 4–5-Datei-Richtwert** — gerechtfertigt, da 6 Komponenten = 6 Dateien.
