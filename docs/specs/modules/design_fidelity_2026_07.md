---
entity_id: design_fidelity_2026_07
type: module
created: 2026-07-12
updated: 2026-07-12
status: draft
version: "1.0"
tags: [frontend, design-fidelity, compare, trips]
---

# Design-Fidelity-Fixbündel 2026-07-12

## Approval

- [x] Approved (PO-„go" 2026-07-12)

## Purpose

Sechs kleine 1:1-Abweichungen zwischen Live-Frontend und der kanonischen
JSX-Design-Quelle (`claude-code-handoff/current/jsx/`) beheben, die im
Design-Durchgang 2026-07-12 gefunden wurden: 28 IST-Screenshots wurden von
vier unabhängigen Fresh-Eyes-Prüfern begutachtet und gegen `current/jsx/`
adjudiziert (PO-Auftrag, kein Einzel-Issue). Zusätzlich entsteht eine kurze
`README.md` im Screenshot-Ordner, die klarstellt, dass `current/jsx/*` die
kanonische Design-Wahrheit ist und historische `soll-*.png` überholt sein
können.

## Source

- **File:** `frontend/src/routes/compare/[id]/+page.svelte:204` — Kanal-Zähler ohne Singular-Weiche
- **File:** `frontend/src/lib/components/compare/CompareTabs.svelte:248` — Referenz-Pattern (bereits korrekt: „1 Kanal“/„N Kanäle“)
- **File:** `frontend/src/routes/trips/+page.svelte:345` — Untertitel Trips-Liste
- **File:** `frontend/src/routes/compare/+page.svelte:51-55` — Untertitel Compare-Liste
- **File:** `frontend/src/routes/compare/[id]/+page.svelte:159-186` — Mobile-Header Compare-Detail (Status-Pille + fehlende Unterzeile)
- **File:** `frontend/src/lib/components/compare/CompareEditor.svelte:614-666` — Create-Step-1: Profil-Karten + Weiter-CTA
- **Identifier:** kein Issue — Design-Durchgang 2026-07-12 (PO-Auftrag), Referenz: `claude-code-handoff/current/jsx/screen-trips.jsx`, `screen-compare-list.jsx`, `screen-compare-detail.jsx`, `screen-compare-editor.jsx`

> **Schicht-Hinweis:** Alle betroffenen Dateien liegen unter `frontend/src/...`
> (SvelteKit) — reines Frontend-Fix-Bündel, kein Go-/Python-Backend betroffen.

## Estimated Scope

- **LoC:** ~120-150 (rein `frontend/src`, plus eine neue `.md`-Datei die nicht zählt)
- **Files:** 5 Svelte-Dateien (davon eine ggf. + `subscriptionHelpers.ts`), 1 neue `README.md`, 1-2 Testdateien
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/compare/subscriptionHelpers.ts` (`presetLocationsLabel`, `presetProfileLabel`) | module | Vorbild für Singular/Plural-Pattern (Fix 1) und Quelle für Profil-Label (Fix 4) |
| `frontend/src/lib/types.ts` (`ACTIVITY_PROFILE_OPTIONS`, `ActivityProfile`, `toCompareProfile`) | module | Kanonische Profil-Keys/Labels, System→Engine-Namespace-Mapping |
| `frontend/src/lib/components/compare/compareMetricDefs.ts` (`PROFILE_METRICS_WITH_SCALES`) | module | Reale Metrik-Zuordnung je Aktivitätsprofil (Fix 6) — einzige bestehende Quelle dieser Zuordnung im FE |
| `frontend/src/lib/components/ui/btn/Btn.svelte` | module | `variant="quiet"` + `disabled`-Prop bereits vorhanden — kein neuer Button-Zustand nötig (Fix 5) |
| `frontend/src/lib/components/compare/CompareStatusPill.svelte` | module | Bestehende Pille (bereits `inline-flex`, kompakt) — Fix 4 ändert nur die Einbettung im Markup, nicht die Pille selbst |
| `claude-code-handoff/current/jsx/*` | design-source | Kanonische Design-Wahrheit für alle 6 Fixes |

## Implementation Details

**Fix 1 — Singular „Kanal“ (`compare/[id]/+page.svelte:204`):**
Aktuell: `{(data.preset.empfaenger ?? []).length} Kanäle` — immer Plural,
auch bei 1 Empfänger. `CompareTabs.svelte:248` zeigt das korrekte Muster:
`{n} {n === 1 ? 'Kanal' : 'Kanäle'}`. Gleiche Ternary hier übernehmen (inline
oder als kleiner Helper analog `presetLocationsLabel` in
`subscriptionHelpers.ts`, damit das Pattern node:test-testbar ist).

**Fix 2 — Trips-Untertitel (`trips/+page.svelte:345`):**
Aktuell: „Alle Trips auf einen Blick — Status, Zeitraum und Aktionen.“
Ersetzen durch den kanonischen Wortlaut aus `screen-trips.jsx:30`:
„Alle aktiven, geplanten und abgeschlossenen Mehrtages-Trips. Pro Trip
kannst du Alerts justieren, ein Briefing direkt schicken oder die
Email-Vorschau öffnen.“

**Fix 3 — Compare-Untertitel ohne Empfehlungs-Versprechen (`compare/+page.svelte:51-55`):**
Aktuell verspricht der Text eine tagesaktuelle Ort-Empfehlung („heute ist
Ort X am besten — weil …“) — das widerspricht der PO-Modellentscheidung
2026-07-11 (`claude-code-handoff/INSTRUCTIONS.md`): „Briefing neutral (kein
Score/Rang/Empfehlung — konsistent mit CompareEmailV2)“. Ersetzen durch den
kanonischen Wortlaut aus `screen-compare-list.jsx:38-41`: „Stehende
Monitore: dieselben Orte im Blick. Briefings wie beim Trip — Morgen-Briefing
für heute, Abend-Briefing für morgen, zur gewählten Uhrzeit. Werte
nebeneinander, ohne Ranking. Einmal eingerichtet, läuft jeder Vergleich, bis
du ihn stoppst.“

**Fix 4 — Mobile Compare-Detail-Header (`compare/[id]/+page.svelte:159-186`):**
Aktuell steht `<CompareStatusPill {status} />` (Zeile 186) als eigener Block
unterhalb der TopBar, ohne Unterzeile. Kanonisches Muster
(`screen-compare-detail.jsx:74-80`): Pille kompakt **inline neben dem
Titel** (`display:flex; align-items:center; gap:12px`), darunter eine
Unterzeile `{region} · {profileLabel} · {N} Orte` (Region weglassen, wenn
nicht gesetzt — `ComparePreset.display_config.region` ist optional).
`profileLabel` via `presetProfileLabel(data.preset.profil)`,
Orte-Anzahl via `data.locations.length` (bzw. bestehendes
`presetLocationsLabel`-Pattern).

**Fix 5 — Weiter-CTA im Create-Step-1 immer sichtbar (`CompareEditor.svelte:656-665`):**
Aktuell: `{#if canContinue && !isEdit}` — Button wird bei leerem Namen gar
nicht gerendert, nur der „⊘ Name fehlt“-Hinweis bleibt. Kanonisches Muster
(`screen-compare-editor.jsx:185-194`): Button **immer** rendern wenn
`!isEdit`, mit `variant={canContinue ? 'accent' : 'quiet'}`,
`disabled={!canContinue}` (Btn-Komponente unterstützt beides bereits),
`onclick` nur wirksam wenn `canContinue`. Hinweistext „⊘ Name fehlt“ bleibt
zusätzlich sichtbar.

**Fix 6 — Metriken-Unterzeile auf Profil-Karten (`CompareEditor.svelte:631-637`):**
Aktuell zeigen die vier Profil-Karten nur `{opt.label}`, keine
Metriken-Vorschau. Kanonisches Muster (`screen-compare-editor.jsx:180`):
Mono-Unterzeile mit den Metrik-Labels, `·`-getrennt. Die reale
Profil→Metriken-Zuordnung existiert bereits im FE in
`compareMetricDefs.ts::PROFILE_METRICS_WITH_SCALES` (Keys `WINTERSPORT` /
`ALPINE_TOURING` / `SUMMER_TREKKING` / `ALLGEMEIN`), erreichbar über
`toCompareProfile(opt.value)` (System-Key → Engine-Key-Mapping in
`types.ts:404-411`). Konkrete Zuordnung (Label-Reihenfolge wie im Array):
- **Allgemein:** Temperatur max · Windspitzen · Niederschlag · Sichtweite min
- **Wintersport:** Schneehöhe · Neuschnee · Sonnenstunden · Windspitzen · Bewölkung Ø
- **Wandern:** Neuschnee · Sichtweite min · Windspitzen
- **Sommer-Trekking:** Niederschlag · Gewitter · Windspitzen · UV-Index max · Sichtweite min

Diese Werte sind aus dem bestehenden Code abgeleitet (`MetricDef.label` je
Eintrag in `PROFILE_METRICS_WITH_SCALES[...]`), nicht neu erfunden.

**Dokumentation (gleicher Commit): `claude-code-handoff/screenshots/README.md` (NEU)**
Erklärt: kanonische Design-Wahrheit = `current/jsx/*` (Snapshot laut
`MANIFEST.txt`-Changelog zuletzt 2026-07-11 aktualisiert); die `soll-*.png`
in diesem Ordner sind historische Beweisbilder ihrer jeweiligen Issues und
können vom aktuellen JSX-Snapshot überholt sein — bei Konflikt gewinnt
`current/jsx`. Kurzliste der aktuell noch maßgeblichen PNGs:
`soll-29b-desktop-layout-route.png`, `soll-29b-desktop-layout-vergleich.png`,
`soll-29b-desktop-versand-route.png`, `soll-29b-desktop-versand-vergleich.png`,
`soll-29b-mobile.png`.

## Expected Behavior

- **Input:** bestehende Compare-Presets/Trips-Daten (unverändert), Nutzer-Interaktion mit Compare-Liste, Compare-Detail (mobil), Trips-Liste, Compare-Editor Create-Step-1.
- **Output:** korrekte Singular/Plural-Kanalanzeige, JSX-identischer Fließtext auf zwei Übersichtsseiten, kompakte inline Status-Pille + sichtbare Kontext-Unterzeile im mobilen Compare-Detail-Header, immer sichtbarer (ggf. disabled) Weiter-Button im Create-Step-1, Metriken-Unterzeile auf allen vier Profil-Karten.
- **Side effects:** keine — reine Darstellungs-/Text-Änderungen, keine neuen API-Calls, keine Schema-Änderung, kein Verhalten hinter den bestehenden `data-testid`s ändert sich.

## Acceptance Criteria

- **AC-1:** Given ein Vergleich hat genau einen Empfänger/Kanal, When die Detail-Seite (Desktop-Grid) geladen wird, Then zeigt die Kachel „1 Kanal“ (Singular), nicht „1 Kanäle“.
  - Test: Kern node:test auf die Singular/Plural-Ternary bzw. den extrahierten Helper mit Input 1 → „1 Kanal“ und Input 0/2 → „0 Kanäle“/„2 Kanäle“.

- **AC-2:** Given die Trips-Übersicht wird geöffnet, When die Seite rendert, Then steht als Untertitel exakt „Alle aktiven, geplanten und abgeschlossenen Mehrtages-Trips. Pro Trip kannst du Alerts justieren, ein Briefing direkt schicken oder die Email-Vorschau öffnen.“
  - Test: Staging-Playwright öffnet `/trips`, liest den Untertitel-Text und vergleicht ihn zeichengenau mit dem JSX-Wortlaut.

- **AC-3:** Given die Compare-Übersicht wird geöffnet, When die Seite rendert, Then enthält der Untertitel keinen Empfehlungs-/Rang-Hinweis mehr und lautet exakt „Stehende Monitore: dieselben Orte im Blick. Briefings wie beim Trip — Morgen-Briefing für heute, Abend-Briefing für morgen, zur gewählten Uhrzeit. Werte nebeneinander, ohne Ranking. Einmal eingerichtet, läuft jeder Vergleich, bis du ihn stoppst.“
  - Test: Staging-Playwright öffnet `/compare`, liest den Untertitel-Text, prüft Abwesenheit von „Empfehlung“/„am besten“ und Übereinstimmung mit dem JSX-Wortlaut.

- **AC-4:** Given ein Compare-Preset wird auf einem mobilen Viewport geöffnet, When der Detail-Header rendert, Then steht die Status-Pille kompakt inline neben dem Titel (nicht als eigene volle Zeile) und darunter ist eine Unterzeile mit Profil-Label und Ortsanzahl sichtbar (Region davor, falls gesetzt).
  - Test: Staging-Playwright mit Mobile-Viewport öffnet `/compare/{id}`, prüft Bounding-Box der Pille (neben Titel, nicht darunter volle Breite) und liest die Unterzeile.

- **AC-5:** Given der Create-Step-1 des Compare-Editors ist offen und das Namensfeld ist leer, When der Nutzer auf den Tab schaut, Then ist der „Orte hinzufügen →“-Button sichtbar aber disabled (quiet-Stil) neben dem „⊘ Name fehlt“-Hinweis; When ein Name eingegeben wird, Then wird derselbe Button aktiv (accent-Stil) und klickbar.
  - Test: Staging-Playwright öffnet `/compare/new`, prüft Button-Sichtbarkeit + `disabled`-Zustand vor und nach Namenseingabe (echter Klick-Pfad, kein DB-Check).

- **AC-6:** Given der Create-Step-1 zeigt die vier Aktivitätsprofil-Karten, When eine Karte gerendert wird, Then zeigt sie unter dem Label eine Mono-Unterzeile mit den echten, aus `PROFILE_METRICS_WITH_SCALES` abgeleiteten Metrik-Namen des jeweiligen Profils (z.B. Wintersport → „Schneehöhe · Neuschnee · Sonnenstunden · Windspitzen · Bewölkung Ø“).
  - Test: Staging-Playwright öffnet `/compare/new`, liest die Unterzeile jeder der vier Karten und vergleicht sie mit der in dieser Spec dokumentierten Liste.

- **AC-7:** Given die bestehende Test-Suite und `data-testid`-Verträge vor diesem Bündel, When die sechs Fixes implementiert sind, Then bleiben alle bisherigen `data-testid`-Attribute unverändert und die bestehenden Kern-Suiten (u.a. `compareEditorSlice3.test.ts`, Compare-Tile-/Subscription-Helper-Tests) laufen weiterhin grün.
  - Test: `uv run` bzw. `npm run test` der betroffenen Kern-Suiten vor/nach dem Fix; Diff der `data-testid`-Vorkommen in den geänderten Dateien ist leer.

## Known Limitations

- **KL-1:** Accent-CTAs bleiben orange (PO-Entscheidung #219 — der JSX-Snapshot hinkt bei der Akzentfarbe hinterher). Kein Teil dieses Bündels.
- **KL-2:** Die Mobile-Chrome-Frage (Titel-in-Bar vs. Wordmark) ist NICHT Teil dieses Bündels und braucht einen eigenen PO-Entscheid bzw. ein eigenes Issue.
- **KL-3:** Die volle Vorschau-Tab-Konvergenz (Trip vs. Compare) ist Gegenstand von Epic #1204, nicht dieses Bündels.
- **KL-4:** LoC-Umfang ist klein (<150) — kein `loc_limit_override` nötig.
- **Edge Case:** 0 Kanäle zeigt korrekt „0 Kanäle“ (Plural bleibt bei 0, nur `n === 1` ist Singular).
- **Edge Case:** Ein Compare-Preset ohne gesetzte Region zeigt die Unterzeile ohne Region-Teil, also nur „{Profil-Label} · {N} Orte“.

## Out of Scope

- Alle 22 übrigen Befunde des Design-Durchgangs, deren Verdikt STALE-SOLL, FUTURE oder DATA war (nicht Teil dieses Bündels).
- Umbenennungen/Struktur-Änderungen aus Issue #1231.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Text-/Markup-Korrekturen an bestehenden Komponenten, keine neue Architektur, kein neues Datenmodell, keine neue Schnittstelle.

## Changelog

- 2026-07-12: Initial spec created
