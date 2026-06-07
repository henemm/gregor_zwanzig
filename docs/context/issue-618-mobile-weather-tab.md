# Context: Issue #618 — Mobile Wetter-Metriken-Tab (Trip bearbeiten 4/4)

## Request Summary
Volle Handy-Parität für den neuen Wetter-Metriken-Tab: die 4 Abschnitte vertikal
gestapelt + Mail-Vorschau als **Bottom-Sheet** (statt sticky-Spalte), Telegram-
Schnittlinie nach Spalte 8 auch mobil, Kanal-Tabs Email/Telegram/SMS (kein Signal).
Letztes Slice (4/4) des Design-Pakets „Trip bearbeiten" (#575).

## SOLL-Quelle
`claude-code-handoff/current/jsx/screen-trip-edit-v2-mobile.jsx` → `TM2_WetterTab`:
- `<ScreenScroll>` mit 4 Abschnitten (01 Profil · 02 Grundauswahl · 03 Reihenfolge · 04 Kanäle)
- Floating-Button „So kommt es an" (fixiert unten) → öffnet `<Sheet>` mit `WM2_ChannelTabs` + Email/Telegram/SMS-Vorschau
- KEINE Accordion-Overlay (das war die alte #415-UX)

## Related Files
| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Editor-Host; `.v2-layout` Grid bricht bei ≤899px auf 1 Spalte um. Enthält noch Legacy-`.mobile-metrics-trigger` → `WeatherMetricsMobileView` |
| `frontend/src/lib/components/trip-detail/WeatherV2MailPreview.svelte` | Vorschau MIT Kanal-Tabs Email/Telegram/SMS (kein Signal ✓) + Telegram-Overflow-Badge. `position:sticky` (Desktop-Spalte) |
| `frontend/src/lib/components/trip-detail/WeatherV2Reihenfolge.svelte` | Telegram-Schnittlinie `[data-testid=wm2-cut-line]` bei `i === tgBudget` wenn `activeChannel==='telegram'` |
| `frontend/src/lib/components/trip-detail/WeatherV2Grundauswahl/Kanaele/PresetBar.svelte` | Geteilte Editor-Abschnitte (reflowen bereits) |
| `frontend/src/lib/components/mobile/Sheet.svelte` | Kanonisches Bottom-Sheet (#373), `snap full/half/peek`, Body-Scroll-Lock, footer/children-Snippets |
| `frontend/src/lib/components/trip-detail/WeatherMetricsMobileView.svelte` | **Legacy #415**: Full-Screen-Accordion-Overlay OHNE Vorschau/Reihenfolge/Kanäle → Funktions-Parität-REGRESSION, widerspricht neuer JSX |
| `frontend/src/lib/components/trip-detail/metricsEditor.ts` | `CHANNEL_COL_BUDGET.telegram = 8` → AC-3 „nach Spalte 8" |

## Existing Patterns
- Responsive bisher rein über CSS-`@media (max-width: 899px)` (kein matchMedia/Viewport-Store im Repo)
- `Sheet` wird bereits in `mobile/`-Kontext genutzt (compare ActionSheet, StageSelectSheet)
- Editor-Abschnitte sind trip-agnostisch & props-only → auf Mobil identisch wiederverwendbar (= echte Parität AC-5)

## Dependencies
- Upstream: `WeatherV2*`-Komponenten, `Sheet.svelte`, `metricsEditor.ts`
- Downstream: nur `WeatherMetricsTab.svelte` rendert diese; keine externen Consumer

## Existing Specs
- `docs/specs/modules/issue_587_weather_tab_v2.md` — Desktop-Editor v2
- `docs/specs/modules/issue_373_mobile.md` — Sheet-Komponente
- `docs/specs/modules/issue_415_mobile_metrics_view.md` — Legacy-Accordion-Overlay (wird abgelöst)

## Risks & Considerations
- **Legacy-Overlay #415:** Die neue JSX hat KEIN Accordion-Overlay. `WeatherMetricsMobileView` + sein Trigger sind eine Parität-Regression (kein Reorder/Kanäle/Vorschau) und sollten entfernt werden. `WeatherMetricsMobileView.test.ts` (Datei-Inhalt-Checks, ohnehin regelwidrig) wäre dann stale → mit-entfernen.
- **Doppel-Mount der Vorschau:** Ohne Viewport-Store muss die Inline-Preview-Spalte auf Mobil per CSS versteckt und die Sheet-Variante separat gerendert werden → `WeatherV2MailPreview` mountet 2× (Desktop-Spalte hidden + Sheet). Hidden-but-mounted ist harmlos; sauberer wäre ein kleiner matchMedia-Guard.
- **AC-3 schon erfüllt** in `WeatherV2Reihenfolge` (Cut-Line bei Index 8) — muss auf Mobil nur sichtbar bleiben (Reflow zeigt Abschnitt 03).
- **AC-4 schon erfüllt** in `WeatherV2MailPreview` (Tabs Email/Telegram/SMS, kein Signal).
- Frontend-only, keine Backend-/Persistenz-Änderung → E2E-Pfad = `staging-validator` Playwright + Pixel-Diff gegen SOLL.
