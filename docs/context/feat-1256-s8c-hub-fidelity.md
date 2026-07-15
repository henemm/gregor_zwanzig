# Context: feat-1256-s8c-hub-fidelity

## Request Summary

S8c von #1256 (Restliste-Kommentar 2026-07-14): **R2** Hub-Layout-Tab-Rahmen (Überschrift + Hint + 3 Limit-Pillen + Card + mobile dense) und **R3** Hub-Fidelity-Bündel (SummaryCards-Copy, Orte-Tab-Rahmen, Breadcrumb, profileLabel, Mobile-Eyebrow, Mobile-Summary-Stack). Rein darstellend — keine neuen Schreibpfade, alles hinter `hubPutQueue` bleibt unberührt.

## Soll-Quellen (JSX = Wahrheit)

| Quelle | Was |
|---|---|
| `claude-code-handoff/current/jsx/screen-compare-detail.jsx:244-266` | R2 Desktop: `CHub_LayoutTab` — `CHub_EditSection title="Übersicht pro Kanal" hint="Metrik-Zeilen · Orte sind die Spalten — der Renderer kappt je Kanal"` + 3 Mono-Limit-Pillen (`Email · alle Spalten` / `Telegram · max 8` / `SMS · flach · 0`) + `Card padding=20` um die `CompareLayoutRow`s (gap 16) |
| dito `:416-426` | `CHub_EditSection`: h2 18px/600 + mono-Hint 11px rechts, baseline-bündig, marginBottom 12 |
| dito `:155-180` | R3 SummaryCards: Orte `+N weitere` bei >3 (Z.159); Layout-Karte title = konfigurierte Kanäle bzw. „Keine Kanäle" (Z.169) + Copy „Engere Kanäle zeigen automatisch weniger Spalten — Reihenfolge nach Priorität." (Z.171); Versand-Karte Draft: title „Noch nicht geplant", Copy „Briefing-Uhrzeiten im Tab Versand festlegen." (Z.175-177) |
| dito `:193-218` | R3 Orte-Tab: `CHub_EditSection title="Verglichene Orte" hint="Reihenfolge = Spalten im Briefing · ziehen zum Sortieren"` + `Card padding=0` um Liste, „Ort hinzufügen" im Card-Footer (padding 14) |
| dito `:66-70` | Breadcrumb Soll: ZWEI Krümel „Orts-Vergleiche / Hub" |
| dito `:78-80` | Unterzeile Soll: `{region} · {profileLabel} · {N} Orte` |
| Mobile `gregor-zwanzig-mobile/project/screen-compare-detail-mobile.jsx` (im Scratchpad `handoff4/`) | `:148-166` R2 mobil: `CDM_SectionH title="Spalten pro Kanal" hint="Renderer kappt je Kanal"`, kompaktere Pillen (10.5px, `SMS · flach` OHNE „· 0"), `CompareLayoutRow … dense`, KEIN Card um die Rows (gap 10). `:81` Status-Kurzform „Läuft autom." `:87-93` + `:276-293` Summary als gestapelte Chevron-Zeilen `CDM_SummaryRow` (eyebrow/title/desc/Chevron, Orte-Kürzung slice(0,2) + `+N`, Layout-desc „Übersicht pro Kanal", Versand draft „Nicht geplant"/„Aktivierung offen"). `:51` Eyebrow „Orts-Vergleich · Hub". `:267-274` `CDM_SectionH` = Eyebrow + mono-Hint 9.5px |

## Ist-Stand (Explore-Audit, Stand HEAD 10e800af)

| Datei:Zeile | Befund |
|---|---|
| `frontend/src/lib/components/compare/CompareTabs.svelte:847-853` | Layout-Panel = nur `{#each}` → `CompareLayoutRow`; KEIN Rahmen, kein `dense` mobil |
| `frontend/src/lib/components/molecules/CompareLayoutRow.svelte` | hat `dense`-Prop bereits (Z.17,20); SMS-Sonderfall vorhanden |
| `CompareTabs.svelte:725-762` | SummaryCard-Grid Desktop=Mobil GLEICH (kein Chevron-Stack); Orte ohne „+N weitere" (Z.732-733); Wertebereiche-Karte zeigt `preset.profil` ROH (Z.741, Soll JSX:163 `profileLabel`); Layout-Karte (Z.750-751): `channels.join(' · ')` mit HARTER Liste `['email','telegram','sms']` (Z.470) statt konfigurierter Kanäle mit Labels/„Keine Kanäle", Copy ohne „ — Reihenfolge nach Priorität."; Versand-Karte (Z.759-760) ohne Draft-Sonderfall (`versandSummaryText` Z.126-128 statisch) |
| `CompareTabs.svelte:643-675` | Mobile-Monitoring 2×2 (4 Stats) existiert (S8); Status zeigt mobil Langform „Läuft automatisch"/„Entwurf · nicht aktiv" (Z.649-653) statt CDM-Kurzform „Läuft autom."/„Entwurf" (CDM:81) |
| `CompareTabs.svelte:847-853` | Layout-Panel iteriert ebenfalls über die HARTE `channels`-Liste — JSX:259 zeigt nur konfigurierte Kanäle (Fallback email); NICHT in Restliste R2 gelistet → Known Limitation, nicht S8c-Scope |
| `CompareTabs.svelte:775-825` | Orte-Panel ohne Überschrift/Hint/Card-Container |
| `frontend/src/routes/compare/[id]/+page.svelte:144-150` | Breadcrumb Desktop DREI Krümel (WORKSPACE · ORTS-VERGLEICHE / Hub) — Soll: zwei |
| dito `:158-160` | Desktop-Unterzeile zeigt `data.preset.profil` ROH, obwohl `profileLabel` in Z.48 berechnet |
| dito `:183-222` | Mobile-Header ohne Eyebrow „Orts-Vergleich · Hub"; Unterzeile nutzt dort `profileLabel` (inkonsistent zu Desktop) |
| `frontend/src/lib/components/atoms/SectionH.svelte:12-26` | geteilter Section-Header (eyebrow/title/right-Snippet), KEIN `hint`-Prop |
| `frontend/src/lib/components/compare/subscriptionHelpers.ts:134` | `presetProfileLabel(profil)` = zentrales Mapping, bereits von CompareTile/HomeHero genutzt |
| `frontend/src/lib/components/shared/layout-tab/LayoutTab.svelte` | geteilte Editor-LayoutTab (Picker+Preview+LTCapNote) — ANDERES Artefakt, wird im Hub laut JSX-Soll NICHT verwendet (Hub = read-only CompareLayoutRow-Ansicht) |

## Existing Patterns

- Section-Rahmen: Trip-`HubOverview` nutzt `SectionH` (atoms) + `Card` (atoms). `SectionH` hat bereits ein `right`-Snippet (SectionH.svelte:12-26) — der mono-Hint kommt dort hinein, KEINE neue Komponente, KEINE Prop-Erweiterung nötig (Trip/Compare-Sharing-Invariante erfüllt).
- Kanal-Label-Mapping existiert: `channelNamesLabel(preset)` → `channelsLabel` (CompareTabs.svelte:132, '—' bei leer) — für Layout-Karten-Titel wiederverwenden.
- Mobile-Weiche: `isMobileViewport` via matchMedia 899px existiert bereits in CompareTabs (S8, Ein-Mount).
- Alle Hub-Schreibpfade laufen durch `hubPutQueue` (S7) — S8c fügt KEINE Schreibpfade hinzu.

## Dependencies

- Upstream: `presetChannels()`/`presetBriefingTimesLabel` (subscriptionHelpers), `CompareLayoutRow`, `SectionH`, `Card`, `Eyebrow`.
- Downstream: `SectionH` wird von Trip-`HubOverview` u.a. genutzt → `hint`-Prop nur ADDITIV (optional, default unverändert).

## Risks & Considerations

- **Sharing-Invariante:** kein neues Compare-Pendant zu existierendem Trip-Baustein — Rahmen via `SectionH`-Erweiterung; `CDM_SummaryRow`-Äquivalent ist Compare-eigen erlaubt (kein Trip-Pendant existiert, JSX-Soll ist Compare-spezifisch) — Begründung gehört in die Spec.
- Breadcrumb-Angleich (3→2 Krümel): nur Compare-Hub-Seite anfassen; prüfen ob Trip-Hub dasselbe 3-Krümel-Muster hat (dann bewusst-anders dokumentieren statt App-weit ändern — Scope-Grenze S8c).
- Spec-Behauptungen „bereits vorhanden" IMMER mit Code-Beleg (dritter Fall der Klasse in S8b — Status-Kurzform mobil, Layout-Karten-Copy erst verifizieren).
- Rein darstellende Änderung, aber CompareTabs ist Ein-Mount Desktop+Mobil → Playwright-Wächter für beide Viewports (Muster .1256-s8-Suite).
