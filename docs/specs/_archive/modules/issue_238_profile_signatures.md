---
entity_id: issue_238_profile_signatures
type: module
created: 2026-05-16
updated: 2026-05-16
status: draft
version: "1.0"
tags: [frontend, design-system, activity-profile, epic-236]
issue: 238
epic: 236
---

<!-- Issue #238 — Profil-Signaturen im Design-System definieren (Epic #236 Sub-Issue 2) -->

# Issue #238 — Profil-Signaturen im Design-System

## Approval

- [ ] Approved

## Zweck

Pro `ActivityProfile` (Wintersport, Wandern, Summer-Trekking, Allgemein) eine
visuelle Signatur (Akzentfarbe + Icon + Eyebrow-Label) zentral im Design-System
verankern. Damit erbt jeder künftige Renderer (Frontend-Cards wie Mail-HTML)
dieselben Werte aus einer Quelle, statt sie pro Stelle neu zu erfinden.

**Tech-Lead-Entscheidung:** Token-Werte werden **als Aliase auf existierende
Design-Tokens** definiert (`--g-wx-rain`, `--g-success`, `--g-accent`,
`--g-ink-muted`-nah). Das dokumentiert Verwendungsabsicht ohne neue Farben in
die Marke zu schleusen und hält das Vokabular klein.

## Kontext

Voraussetzung für Epic #236 (Mail-Templates ans Design-System angleichen). Ohne
diese Sub-Issue würde jeder Mail-Renderer-Umbau ad-hoc-Profil-Looks erfinden.

## Quelle / Source

**Geänderte Dateien (alle vorhanden):**
- `frontend/src/app.css` — Live-Token-Source
- `docs/reference/design_system_tokens.css` — Begleit-CSS, Mirror
- `docs/reference/design_system.md` — Doku-Source
- `frontend/src/routes/_design/+page.svelte` — Showroom

**Neue Dateien:**
- `frontend/src/lib/utils/profileSignature.ts` — Helper
- `frontend/src/lib/utils/profileSignature.test.ts` — Tests

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ActivityProfile` (`frontend/src/lib/types.ts:68`) | TS-Type | Eingabe-Type für Helper, alle 4 Enum-Werte |
| `frontend/src/lib/components/ui/eyebrow/Eyebrow.svelte` | Komponente | Im Showroom referenzieren |
| `frontend/src/lib/components/ui/dot/Dot.svelte` | Komponente | Im Showroom referenzieren |
| `--g-wx-rain`, `--g-success`, `--g-accent`, `--g-ink-muted` (app.css) | CSS-Token | Alias-Targets |

## Implementation Details

### Token-Definitionen (CSS)

**`frontend/src/app.css`** — neuer Block direkt nach Wetter-Tokens (~Z. 79),
vor Typografie-Block:

```css
/* Aktivitätsprofile (Issue #238) — Aliase auf bestehende Tokens */
--g-profile-wintersport:      #4a7fb5;  /* Alias zu --g-wx-rain */
--g-profile-wandern:          #3a7d44;  /* Alias zu --g-success */
--g-profile-summer-trekking:  #c45a2a;  /* Alias zu --g-accent */
--g-profile-allgemein:        #6b675c;  /* nahe --g-ink-muted, neutral */
```

**`docs/reference/design_system_tokens.css`** — identisches Mirror nach
Wetter-Block.

### Helper

**`frontend/src/lib/utils/profileSignature.ts`** (~45 LoC):

```ts
import type { ActivityProfile } from '$lib/types';

export type ProfileSignature = {
  accent: string;          // CSS-Variablen-Referenz: var(--g-profile-...)
  accentFallback: string;  // Hex-Fallback für Inline-CSS (Mail/Outlook)
  icon: string;            // Unicode-Glyph
  eyebrow: string;         // Sichtbares Label
};

const SIGNATURES: Record<ActivityProfile, ProfileSignature> = {
  wintersport: {
    accent: 'var(--g-profile-wintersport)',
    accentFallback: '#4a7fb5',
    icon: '❄',          // ❄
    eyebrow: 'Wintersport',
  },
  wandern: {
    accent: 'var(--g-profile-wandern)',
    accentFallback: '#3a7d44',
    icon: '\u{1F97E}',       // 🥾
    eyebrow: 'Wandern',
  },
  summer_trekking: {
    accent: 'var(--g-profile-summer-trekking)',
    accentFallback: '#c45a2a',
    icon: '\u{1F3D4}',       // 🏔
    eyebrow: 'Sommer-Trekking',
  },
  allgemein: {
    accent: 'var(--g-profile-allgemein)',
    accentFallback: '#6b675c',
    icon: '◯',          // ◯
    eyebrow: 'Allgemein',
  },
};

export function profileSignature(profile: ActivityProfile | string): ProfileSignature {
  return SIGNATURES[profile as ActivityProfile] ?? SIGNATURES.allgemein;
}
```

### Showroom-Sektion

**`frontend/src/routes/_design/+page.svelte`** — neue Sektion am Ende, vor dem
schliessenden `</section>` oder nach `sparkline-section`:

```html
<section class="atoms-section">
  <h2>Aktivitätsprofile (Issue #238)</h2>
  <div class="profile-grid">
    {#each PROFILES as p}
      <article class="profile-card" style="--profile-accent: {profileSignature(p).accent}">
        <Eyebrow tone="accent">{profileSignature(p).icon} {profileSignature(p).eyebrow}</Eyebrow>
        <Dot tone="accent" />
        <code>{profileSignature(p).accentFallback}</code>
      </article>
    {/each}
  </div>
</section>
```

Wobei `PROFILES = ['wintersport', 'wandern', 'summer_trekking', 'allgemein']`.

### Doku

**`docs/reference/design_system.md`** — neuer Abschnitt **„§10 · Aktivitätsprofile"**
zwischen dem heutigen §9 (Screen-Kanon, Z. 224) und dem heutigen §10
(Stand-Block, Z. 243). Bestehender §10 wird zu §11. Inhalt:

```markdown
## 10 · Aktivitätsprofile — visuelle Signatur

Vier Aktivitätsprofile, je mit Akzent, Icon, Eyebrow-Label. Token-Werte sind
Aliase auf bestehende Design-Tokens — kein neuer Wert wird der Marke
hinzugefügt; nur die Verwendungsabsicht wird benannt.

| Profil | CSS-Token | Hex | Icon | Eyebrow-Label |
|---|---|---|---|---|
| Wintersport | `--g-profile-wintersport` | `#4a7fb5` (Alias `--g-wx-rain`) | `❄` | `Wintersport` |
| Wandern | `--g-profile-wandern` | `#3a7d44` (Alias `--g-success`) | `🥾` | `Wandern` |
| Summer-Trekking | `--g-profile-summer-trekking` | `#c45a2a` (Alias `--g-accent`) | `🏔` | `Sommer-Trekking` |
| Allgemein | `--g-profile-allgemein` | `#6b675c` (neutral, nahe `--g-ink-muted`) | `◯` | `Allgemein` |

**Helper:** `frontend/src/lib/utils/profileSignature.ts` —
`profileSignature(profile) → { accent, accentFallback, icon, eyebrow }`.
`accent` ist die CSS-Variable, `accentFallback` der Hex-Wert (für Inline-CSS
in Mails). Unbekannte Werte fallen auf `allgemein` zurück.

**Verwendungs-Regel:** Akzentfarbe rein dekorativ (Pin, Dot, Header-Border) —
nicht als Textfarbe verwenden; Kontrast auf hellen Surfaces ist knapp AA.
Sichtbare Profil-Identifikation immer als Eyebrow + Icon **plus** Akzent, nie
nur als Farbe (Branding-Kohärenz).
```

Stand-Block (jetzt §11) bekommt Zeile zu Issue #238 ergänzt.

## Expected Behavior

- **Input** (Helper): String aus `ActivityProfile`-Union oder beliebiger String
- **Output** (Helper): `ProfileSignature`-Objekt mit allen 4 Feldern; bei
  unbekanntem String → Signatur von `allgemein`
- **Side effects:** Keine — reine Daten-Funktion, keine I/O, keine DOM-Effekte

## Acceptance Criteria

- **AC-1:** Given `frontend/src/app.css` und `docs/reference/design_system_tokens.css` / When beide Dateien gelesen werden / Then enthält jede genau einen Block mit den vier Tokens `--g-profile-wintersport`, `--g-profile-wandern`, `--g-profile-summer-trekking`, `--g-profile-allgemein` mit den Hex-Werten `#4a7fb5`, `#3a7d44`, `#c45a2a`, `#6b675c` in dieser Reihenfolge
  - Test: (populated after /tdd-red)

- **AC-2:** Given `docs/reference/design_system.md` / When ein Leser zwischen dem bisherigen §9 (Screen-Kanon) und dem bisherigen §10 (Stand) sucht / Then findet er einen neuen Abschnitt „Aktivitätsprofile" mit Token-Tabelle, Helper-Verweis und Verwendungs-Regel; der bisherige §10 wird zu §11 nummeriert
  - Test: (populated after /tdd-red)

- **AC-3:** Given `frontend/src/lib/utils/profileSignature.ts` / When `profileSignature('wintersport')` aufgerufen wird / Then liefert er ein Objekt mit `accent='var(--g-profile-wintersport)'`, `accentFallback='#4a7fb5'`, `icon='❄'` (`❄`), `eyebrow='Wintersport'`; analog für `wandern`, `summer_trekking`, `allgemein`
  - Test: (populated after /tdd-red)

- **AC-4:** Given `profileSignature` / When eine unbekannte oder leere Eingabe übergeben wird (z.B. `''`, `'unknown'`, `null`-Cast) / Then liefert er die Signatur von `allgemein` als Fallback, **nicht** `undefined` oder einen Fehler
  - Test: (populated after /tdd-red)

- **AC-5:** Given `frontend/src/routes/_design/+page.svelte` / When die Route `/_design` im Browser geladen wird / Then ist eine Sektion „Aktivitätsprofile" sichtbar, die für alle vier Profile je eine Karte mit Akzent-Dot, Eyebrow + Icon und dem Hex-Fallback als `<code>`-Block zeigt — vier visuell unterscheidbare Karten
  - Test: (populated after /tdd-red, manuell-visuell)

- **AC-6:** Given die geänderten Dateien / When `git diff` läuft / Then bleiben Mail-Renderer (`src/output/renderers/email/`), Frontend-Komponenten ausserhalb `_design`, und produktive Routen unverändert — keine inhaltlichen Frontend-/Mail-Änderungen in diesem Sub-Issue
  - Test: (populated after /tdd-red)

## Known Limitations

- Token-Werte in `app.css` und `design_system_tokens.css` werden **manuell**
  synchron gehalten — kein automatischer Sync (bekannter Issue #213-Stand)
- Helper kennt keine i18n — Eyebrow-Labels sind deutsch hartkodiert
  (Mehrsprachigkeit hat eigenes Issue #94, deferred)
- Icon-Glyphs hängen am Font/Emoji-Support des Clients — in Mails (Outlook,
  reine Text-Clients) ggf. kein Emoji-Rendering. Akzeptabel: ohne Icon bleiben
  Akzent + Eyebrow erhalten

## Out of Scope

- **Mail-Renderer-Umbau** (eigene Sub-Issues 3–8 von Epic #236)
- **Wetter-Tokens-Drift** zwischen `app.css` (`--g-wx-*`) und `tokens.css`
  (`--g-weather-*`) — bekanntes Restproblem, eigener Issue nötig
- **Profil-Sichtbarkeit in produktiven Frontend-Komponenten** (Trip-Hero,
  Trip-Liste) — eigene Folge-Tickets, nicht hier
- **i18n** der Eyebrow-Labels

## Risiken & Migration

- **Drift app.css ↔ tokens.css:** Mitigation durch identisches Mirroring im
  selben PR; nur 4 Zeilen je Datei
- **Marken-Kohärenz:** Wandern-Grün ist `--g-success`-Hex — könnte als
  „OK-Status"-Signal missgelesen werden. Mitigation in Doku-Regel: Akzent immer
  mit Eyebrow + Icon zusammen, nie nur als Farbe
- **Kontrast:** `#c45a2a` und `#3a7d44` auf hellen Surfaces sind knapp AA für
  Text. Doku verbietet Verwendung als Textfarbe; Akzent ist dekorativ

## Tests / Verifikation

- **Unit** (`profileSignature.test.ts`):
  - Shape-Test pro Profil — alle 4 Felder vorhanden, Strings nicht leer
  - Hex-Pattern-Check für `accentFallback` (`/^#[0-9a-fA-F]{6}$/`)
  - Fallback-Test — `''`, `'unknown'` ergeben `allgemein`-Signatur
- **Manuell-visuell:** `/_design` im Browser laden, vier Karten erkennbar
  unterscheidbar
- **Diff-Stichprobe:** `git diff src/output/renderers/email/` liefert 0 Lines

## Changelog

- 2026-05-16: Initial spec (Epic #236 / Sub-Issue 2)
- 2026-05-16: Eyebrow-Label korrigiert von 'Summer-Trekking' zu 'Sommer-Trekking' (Adversary-Finding F002, Konsistenz mit existierendem UI-Dropdown)
