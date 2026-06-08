# Context: Issue #661 — Mobile-Parität /trips/new (Progressive Tab Editor)

**Status: ✅ LIVE (2026-06-08)**

## Request Summary

Der Progressive Tab Editor unter `/trips/new` (Epic #622, „ein Trip-Pfad") war auf Desktop
vollständig live (Slice 1 #622, Slice 2 #658). Dieses Issue holte **AC-9 (Mobile-Parität)**
nach: Der gesamte Anlege-Flow soll auf Mobile-Viewport (≤899px) gemäß der verbindlichen
Design-Quelle rendern — kein abgeschnittenes Desktop-Layout, bedienbare Touch-Interaktion.
**Reine responsive/Layout-Arbeit, frontend-only, additiv. Kein Backend-/Schema-Change.**

**Implementierung abgeschlossen (2026-06-08):** TripNewEditor.svelte um Mobile-Markup und
`@media (max-width:899px)` CSS erweitert. #622-Paket vollständig (alle 9 ACs).

## Design-Quelle (verbindlich, 1:1)

`docs/design-requests/trip-anlegen-2026-06-06/screen-trip-new-v2-mobile.jsx`
(Desktop-Pendant zum Abgleich: `screen-trip-new-v2.jsx`)

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | **Kern.** 577 Z., komplett Inline-Styles, Desktop 1:1. Hier entsteht die Mobile-Adaption. |
| `frontend/src/lib/components/trip-new/tripNewLogic.ts` | Pure Logik (unlockedTabs/doneTabs/stageDate/progressCount/canSave/buildCreateTripPayload) — bleibt unverändert, mobil identisch genutzt. |
| `frontend/src/lib/components/trip-new/__tests__/tripNewLogic.test.ts` | Bestehende Unit-Tests (node:test). |
| `frontend/src/routes/trips/new/+page.svelte` | Einstieg: rendert `<TripNewEditor />`. |
| `frontend/src/lib/components/mobile/Sheet.svelte` | Bottom-Sheet (snap full/half/peek). Mobile-Muster für Etappenname-Edit + Skip-Bestätigung. |
| `frontend/src/lib/components/mobile/{MBtn,MInput,MField,MTab,Toast}.svelte` | Touch-Primitives (MBtn 40/48/56px, MInput, MField label+sub). |
| `frontend/src/lib/components/mobile/TopAppBar.svelte` | Re-Export → `ui/sidebar/TopAppBar` (title/eyebrow/leftIcon/right). Mobile-Kopf statt Breadcrumb. |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Wetter-Tab (createMode). **Bereits mobil (#618: FAB + Bottom-Sheet).** Wird im Wetter-Tab wiederverwendet. |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | Wegpunkte-Editor. **Hat bereits eigenes Mobile-Layout** (MapCanvas + ProfileSheetEmbedded + StageSelectSheet). |
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` | Zeitplan-Tab. **Keine Mobile-CSS** — braucht ggf. Wrapper-Padding. |
| `frontend/src/lib/components/alert-rules-editor/AlertRulesEditor.svelte` | Alerts-Tab. **Keine Mobile-CSS** — braucht ggf. Wrapper-Padding. |
| `frontend/src/app.css` (Z. 49-50) | `@custom-variant mobile { @media (max-width: 899px) }` — die kanonische Breakpoint-Grenze. |

## Existing Patterns

- **Responsive = CSS-only Media Queries @ 899px.** Kein JS-Viewport-Store, kein `matchMedia`.
  Mobile-Erkennung passiert ausschließlich über `@media (max-width: 899px)` im `<style>`-Block.
- **CSS-only Tab-Umschaltung (Referenz #618, WeatherMetricsTab):** Desktop- UND Mobile-Markup
  werden gerendert; die Media-Query blendet das jeweils falsche per `display:none` aus
  (`.preview-col { display:none }` mobil; FAB nur mobil sichtbar).
- **FAB-Muster:** kein eigenes Primitive — inline `position:fixed; bottom:16px; left/right:14px`
  + Pill-Styling. Floating-CTA über dem Inhalt.
- **Bottom-Sheet:** `Sheet.svelte` für sekundäre Editier-Flows (Etappenname, Skip-Bestätigung).
- **Touch-Targets:** minHeight 44–48px, Input font-size 16px (verhindert iOS-Auto-Zoom).
- **E2E-Mobile:** Playwright `page.setViewportSize({width:375,height:667})` (iPhone SE),
  Vorbilder `e2e/bug-270-compare-mobile.spec.ts`, `e2e/issue-269-mobile-trip-tabs.spec.ts`.

## Mobile-JSX → Struktur (Soll)

| Bereich | Desktop (live) | Mobile-Soll (JSX) |
|---------|----------------|-------------------|
| Kopf | Breadcrumb „Trips / Neue Tour" + Abbrechen/Speichern | **TopAppBar**: title=aktiver Tab, eyebrow=Tour-Name, back-Icon, „Speichern" rechts |
| Fortschritt | feste 24px-Segmente + „N/4 Abschnitte" | flex:1-Segmente + „N/4" |
| TabBar | horizontal scroll, hover | scroll, minHeight 44, **Lock-Tap → Toast** (statt Flash) |
| Route | max-width 640, Footer-CTA rechts | MField/MInput, **Floating-CTA** unten |
| Etappen | Grid (36px/1fr/60px/200px/28px) | **vertikale Cards**, Name-Edit via **Sheet**, Floating-CTAs |
| Wegpunkte | eingebetteter `EditStagesPanelNew` (Desktop-Grid) | JSX: vereinf. Karten-Placeholder. **Aber:** `EditStagesPanelNew` hat schon Mobile-Layout → Reuse statt Mock (Spec-Entscheidung) |
| Wetter | `WeatherMetricsTab` | identisch (bereits mobil) |
| Zeitplan | `EditReportConfigSection` (max-width 720) | mobil padding |
| Alerts | `AlertRulesEditor` | mobil padding |

## Dependencies

- Upstream: `tripNewLogic.ts` (Logik, unverändert), Mobile-Primitives, `Sheet.svelte`.
- Downstream: nur Route `/trips/new`. Keine anderen Konsumenten von `TripNewEditor`.

## Existing Specs

- `docs/specs/modules/issue_622_trip_new_progressive_editor.md` — Desktop-Spec (Slice 1).
- `frontend/docs/specs/modules/issue_618_mobile_weather_tab.md` — Mobile-Wetter-Tab-Referenz.

## Risks & Considerations

- **R1 — Inline-Styles vs. Media-Query (zentral):** `TripNewEditor` ist komplett mit Inline-Styles
  gebaut. Inline-Styles haben höhere Spezifität als CSS-Klassen → eine Media-Query kann sie NICHT
  überschreiben. Für jeden mobil veränderten Bereich müssen Inline-Styles in Klassen überführt
  oder Desktop/Mobile-Markup parallel gerendert + per `display:none` umgeschaltet werden
  (etabliertes #618-Muster). Das ist der Hauptaufwand.
- **R2 — Desktop-Regression:** Desktop-Layout ist 1:1 fidelity-gated (#622). Jede Umstrukturierung
  muss Desktop pixelgleich lassen → Regressionsschutz Pflicht (Desktop-Pixel-Gate erneut).
- **R3 — LoC-Budget:** Shell + Route + Etappen mobil = voraussichtlich > 250 LoC (CSS-only
  bedeutet ggf. parallel gerendertes Mobile-Markup). Wegpunkte/Wetter delegieren an bereits
  mobile Komponenten; Zeitplan/Alerts brauchen nur Padding. Budget vor Implementierung klären
  (kein eigenmächtiger LoC-Override).
- **R4 — Wegpunkte-Scope:** JSX zeigt vereinfachten Mock-Placeholder; `EditStagesPanelNew` hat
  aber bereits ein echtes, validiertes Mobile-Layout. Empfehlung: das echte Reuse-Mobile-Layout
  nutzen (kein Wegwerf-Mock) — die JSX-Vereinfachung war ein Design-Platzhalter, kein Auftrag,
  funktionierende Wegpunkt-Bedienung zu verschlechtern. In Spec festzurren.
- **R5 — Pixel-Gate-Quelle:** Es existiert noch kein SOLL-Mobile-PNG. Muss aus dem Mobile-JSX
  gerendert werden (Technik wie #632/#658: Wrapper-HTML + http.server + Playwright-Screenshot).
- **R6 — Verifikation:** staging-validator im Mobile-Viewport (375px) via Playwright + Pixel-Gate.
```
