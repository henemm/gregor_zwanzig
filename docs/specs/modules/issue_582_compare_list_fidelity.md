# Spec: Compare-Liste Design-Fidelity 1:1 (#582 · Paket 1)

- **created:** 2026-06-07
- **issue:** #582 (Klammer; dieses Paket = Compare-Liste `/compare`)
- **binding source:** `claude-code-handoff/current/jsx/screen-compare-list.jsx` + `molecules.jsx#CompareTile` + SOLL `claude-code-handoff/current/soll/G-compare-uebersicht-kacheln.png`
- **status:** draft (wartet auf PO-'go')

## Kontext

#582 (Compare-Design-Fidelity) wurde wieder geöffnet: 51,5 % Pixel-Drift gegen SOLL (Schwelle #603). PO-Entscheidung 2026-06-07: pro Screen splitten. Dieses Paket bringt **nur die Liste** (`/compare`) 1:1 an die JSX-Vorlage. Detail-Hub und Edit (Tab-Editor, löst Wizard ab) sind eigene Folge-Pakete.

Die Hauptabweichung sitzt in `CompareTile.svelte`: führender Status-Dot, Region, Profil-Label und der komplette Status-Fuß (Rhythmus + „zuletzt …") fehlen; statt der mono-Status-Eyebrow wird eine Pill genutzt. Dazu fehlt im Beschreibungstext der Einschub aus dem JSX.

## Nicht-Ziele

- Detail-Hub `/compare/[id]`, Edit/Wizard-Ablösung, Ortsverwaltung (eigene Pakete/Issues)
- **Signal-Kanal** — bleibt entfernt (PO #610). SOLL zeigt Signal, ist insoweit veraltet; Kanäle ∈ {Email, Telegram, SMS}.
- Backend-Schema-Änderungen an `ComparePreset` (alle benötigten Felder existieren oder sind clientseitig ableitbar)

## Datenherkunft (alles aus vorhandenem `ComparePreset`)

| Kachel-Element | Quelle |
|----------------|--------|
| Name | `name` |
| Status (active/paused/draft) | `deriveStatusFromPreset()` (vorhanden) |
| Region | `display_config.region` |
| „N Orte" | `location_ids.length` |
| Profil-Label (z.B. „Wintersport (Piste)") | ableiten aus `profil` (ActivityProfile→Label-Map) |
| Kanäle | aus `empfaenger` (≥1 → Email) + `display_config.channel_layouts`-Keys (telegram/sms); Signal ignoriert |
| Rhythmus-Label (z.B. „tägl. 06:30") | ableiten aus `schedule` + `weekday` + `hour_from` |
| „zuletzt …" (relativ: heute / Sa / vor 3 Wochen) | ableiten aus `letzter_versand` |
| „Setup unvollständig" (Draft-Fuß) | Status == draft |

## Acceptance Criteria

**AC-1: Beschreibungstext wortgleich**
Given die Compare-Liste `/compare`
When die Seite gerendert ist
Then enthält der Lede-Text unter „Orts-Vergleiche" wortgleich den JSX-Einschub: „Tägliche Briefings, die mehrere Orte gegeneinander stellen und eine Empfehlung mitliefern („heute ist Ort X am besten — weil …"). Einmalig eingerichtet, läuft pro Vergleich automatisch."

**AC-2: Seiten-Gerüst 1:1 (Inline-Styles)**
Given die Liste
When gerendert
Then übernimmt das Layout die JSX-Inline-Styles 1:1 ohne Tailwind-Übersetzung: `main` padding `32px 40px 60px`; Header-Zeile flex/space-between/`margin-bottom:28px`; Titel `font-size:32px font-weight:600 letter-spacing:-0.025em`; Such-Input `max-width:380px` mit Lupen-SVG links und `border-radius:var(--g-r-pill)`; Stats-Zeile flex gap 24 mit unterer 1px-Trennlinie `var(--g-rule-soft)`; Grid `repeat(auto-fill, minmax(300px,1fr)) gap 16`; Fuß-Zeile mono `font-size:11px var(--g-ink-4)` „N von M Vergleichen".

**AC-3: CompareTile 1:1 nach molecules.jsx**
Given eine Kachel
When gerendert
Then entspricht sie der JSX-`CompareTile`-Struktur: (a) Kopf = führender `Dot` (good wenn aktiv, sonst neutral) + Name (15.5px/600, ellipsis) + darunter mono-Status-Eyebrow (9.5px uppercase `letter-spacing:0.14em var(--g-ink-4)`) gefolgt von „· {Region}" + Kebab rechts; (b) Meta-Zeile mono „{N} Orte · {Profil-Label}" mit `padding-left:17px`; (c) Kanal-Pills mono custom-styled (`border var(--g-rule)`, `background var(--g-card-alt)`, `border-radius var(--g-r-pill)`) bzw. „noch keine Kanäle" wenn leer; (d) Status-Fuß mit `border-top:1px dashed var(--g-rule-soft) padding-top:11px`: links Rhythmus-Label (Draft: „Setup unvollständig"), rechts „zuletzt {relativ}" mit Dot (nur wenn nicht Draft).

**AC-4: Aktiv-Akzentrand & Hover**
Given eine aktive Kachel
When gerendert
Then hat sie `border-left:3px solid var(--g-accent)` (inaktiv: 1px `var(--g-rule)`); Hover setzt `border-color:var(--g-ink-3)` + `box-shadow` gemäß JSX.

**AC-5: Profil-Label & Rhythmus & relativer Versand korrekt abgeleitet**
Given ein Preset mit `profil="wintersport"`, `schedule`/`hour_from` gesetzt und `letzter_versand` heute
When die Kachel rendert
Then zeigt sie das menschenlesbare Profil-Label (nicht den Roh-Key „wintersport"), ein Rhythmus-Label wie „tägl. 06:30" und „zuletzt heute".

**AC-6: Leerzustand & Suche**
Given eine Suche ohne Treffer
When gefiltert
Then erscheint genau die JSX-`Card` (padding 40, zentriert, `var(--g-ink-3)` 13px) mit „Keine Vergleiche für »{query}« gefunden." — **kein** erfundenes Icon/Empty-Illustration.

**AC-7: Kein Signal-Kanal**
Given ein Preset egal welcher Konfiguration
When die Kanal-Pills rendern
Then erscheint **nie** ein Signal-Pill; mögliche Kanäle sind ausschließlich Email, Telegram, SMS (PO #610).

**AC-8: Pixel-Diff-Gate bestanden**
Given die deployte Liste auf Staging mit Demo-Presets, die der SOLL-Vorlage entsprechen (Seed analog #583)
When `python3 .claude/hooks/design_fidelity_diff.py --screen G-compare-uebersicht-kacheln` läuft
Then ist das Artefakt `docs/artifacts/<workflow>/design-diff-G-compare-uebersicht-kacheln.json` mit `"passed": true` geschrieben. Schwelle: primär < 10 %; falls verbleibende Differenz nachweislich reine Daten-/Anti-Aliasing-Divergenz bei 1:1-Layout ist, wird ein begründeter `SCREEN_THRESHOLD_MAP`-Eintrag gesetzt (Präzedenz #583/#486, 30 %) — mit Vermerk, dass das Layout durch `staging-validator` + `fresh-eyes-inspector` als 1:1 bestätigt wurde.

## Verifikation

- Frontend node:test (verhaltensnah, kein Mock): Tile rendert alle JSX-Strukturteile; Ableitungen (Profil-Label, Rhythmus, relativer Versand, Kanäle ohne Signal) korrekt; Leerzustand-Text.
- Staging: `staging-validator` prüft AC-1…AC-7 via Playwright als eingeloggter Nutzer; `fresh-eyes-inspector` Mode 2 gegen SOLL.
- Pixel-Diff-Gate (AC-8) als Hard-Gate vor Issue-bezogenem Close.

## Betroffene Dateien (Schätzung ~180–230 LoC)

- `frontend/src/lib/components/compare/CompareTile.svelte` (Rewrite 1:1)
- `frontend/src/routes/compare/+page.svelte` (Lede-Text, Gerüst-Feinschliff)
- `frontend/src/lib/components/compare/CompareGrid.svelte` (Leerzustand ohne Icon, gap-Token)
- `frontend/src/lib/components/compare/subscriptionHelpers.ts` (Profil-Label-, Rhythmus-, Relativ-Versand-, Kanal-Ableitung)
- ggf. `scripts/seed_validator_*.py` (Demo-Presets für Gate, analog #583)
- `.claude/hooks/design_fidelity_diff.py` (nur falls begründeter Threshold-Eintrag nötig — Tool sonst nicht umbauen)
