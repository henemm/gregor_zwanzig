# Context: feat-2287-tab-kennungen

## Request Summary
Issue #2287 (Epic #2345, Etappe P2): Trip-Hub und Ortsvergleich-Hub benennen dieselben Reiter verschieden
(`alerts`/`idealwerte`, `briefings`/`versand`, `overview`/`uebersicht` …). Ziel: gemeinsame Kennungen
`uebersicht · etappen|orte · wetter-metriken · wertebereiche · alarme · versand · vorschau`, ein gemeinsames
`resolveTab()` mit Alt-Kennungs-Umleitung für beide kinds; der kontextabhängige Sonderfall
`wertebereicheTabId` entfällt.

Pfad-Präfix unten: `R = frontend/src`.

## Ist-Stand der Kennungen

| Reiter | Trip-Hub | Vergleich-Hub | Trip-Anlegen | Vergleich-Anlegen |
|---|---|---|---|---|
| Übersicht | `overview` | `uebersicht` | `route` | `vergleich` |
| Etappen/Orte | `stages` | `orte` | `etappen` (+`wegpunkte`) | `orte` |
| Wetter-Metriken | `weather` | `wetter-metriken` | `metriken` | `metriken` |
| Wertebereiche | `alerts` | `idealwerte` | `wertebereiche` | `idealwerte` |
| Alarme | `alarme` | `alarme` | `alarme` | `alarme` |
| Versand | `briefings` | `versand` | `versand` | `versand` |
| Vorschau | `preview` | `vorschau` | – | – |

Anlege-Editoren schreiben kein `?tab=`; ihre IDs sind intern (Lock-Engine). Nicht zwingend im Scope,
aber `wertebereiche`/`idealwerte` dort ist dieselbe Drift (`anlegeLockEngine.ts:11-14` kommentiert sie).

## Related Files

| File | Relevance |
|---|---|
| `R/lib/components/trip-detail/TripTabs.svelte` | `TABS` :85-93, `VALID_VALUES` :111, `resolve()` :113-115 (still auf `overview`), `initialTab` :48/:127-129, Flush-Guard-Literale :168, `goto(?tab=)` :178, testids `trip-detail-tab-${value}` :106, `-badge-` :107, `trip-detail-panel-` :195, Badges-Interface :25-33/:63-71, Panel-Weiche :196-214 |
| `R/routes/trips/[id]/+page.svelte` | liest `?tab=` :115 (Default `overview`), reicht :396 durch |
| `R/lib/components/compare/compareTabsResolve.ts` | `COMPARE_TABS` :7-23, `RETIRED_TABS = {layout:'wetter-metriken'}` :33-35, `resolveCompareTab` :37-40 — einziger produktiver Importeur `CompareTabs.svelte:103` |
| `R/lib/components/compare/CompareTabs.svelte` | `resolve` :134-137, Default :128/:139, testid `compare-detail-tab-${value}` :149, `history.replaceState` :175-177, ~13 `activeTab ===`-Vergleiche, `handleValueChange('…')` :875-946, Panel-testids :778-1156 |
| `R/routes/compare/[id]/+page.svelte` | liest `?tab=` :205, `tabNachUebernahme` :117/:133, `?tab=vorschau` :260, `?tab=versand` :348 |
| `R/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts` | `SELBST_SPEICHERNDE_VERGLEICH_REITER` :251-256 (`alarme, idealwerte, wetter-metriken, versand`) |
| `R/lib/components/shared/alarme-tab/alarmeTabSections.ts` | `wertebereicheTabId(ctx)` :41-43 — **kein produktiver Aufrufer**, nur `shared/__tests__/alarme_tab_sections.test.ts:28,:96-101` |
| `R/routes/+page.svelte` (Home) | Trip: `TRIP_TAB_MAP` :92/:99, `?tab=overview` :97/:190/:279/:701, stages :299, weather :305, briefings :311, preview :317, alerts :382. Vergleich: idealwerte :573, versand :579, **`?tab=preview` :585 (existiert im Vergleich nicht → landet still auf Übersicht = Bestandsbug)** |
| `R/routes/trips/+page.svelte` | `?tab=preview` :139/:164/:521; **`#weather` :141/:529 (Hash, wird nicht gelesen → Bestandsbug)**; Kebab-Keys :94-96/:112 (keine Tab-IDs) |
| `R/routes/compare/+page.svelte` | `?tab=vorschau` :127 |
| `R/lib/components/trip-detail/{BriefingPreviewCard:51, AlertsPreviewCard:61, PreviewCard:26/:34}.svelte`, `alerts-tab/AlertPreviewCard.svelte:65`, `HubOverview.svelte:58/106/115/122/128` (`makeJumpHandler`) | Trip-Sprunglinks mit Alt-Kennungen |
| `R/lib/components/edit/WeatherSummaryCard.svelte:28` | `goto(/trips/${id}#weather)` — Hash, Bestandsbug |
| `R/lib/components/shared/VersandTab.svelte:305` | `onJump?.('stages')`; `TripNewEditor.svelte:366` übersetzt `stages|etappen → etappen` |
| `R/routes/trips/[id]/edit/+page.server.ts:5-6` | reicht `?tab=` ungeprüft durch; `R/routes/compare/[id]/edit/+page.server.ts:11` ohne tab |
| `R/lib/components/mobile/MTabBar.svelte` | geteilte Reiterleiste; beide Hubs reichen eigene Item-Listen (TripTabs :101-109, CompareTabs :144-151) |
| `R/lib/components/shared/subscription-header/SubscriptionHeader.svelte` | geteilter Hub-Kopf aus #2284 (`kind: 'trip'|'vergleich'`), kennt keine Reiter |

Kein Tab-Bezug (Namensgleichheit, nicht anfassen): `WeatherMetricsTab.svelte:1018` `'wetter-metriken'`
(Speicher-Schlüssel, `tripSpeicherung.ts:141`), `subscriptionHelpers.ts:300` `'preview'` (Action-ID),
Kebab-Keys der Trip-Liste.

## Existing Patterns
- Umleitung stillgelegter Reiter existiert nur beim Vergleich (`RETIRED_TABS`, aus `compare_layout_tab_dissolution`). Das ist das Muster für die Alt-Kennungs-Umleitung beider kinds.
- Trip schreibt die URL per `goto(?tab=…, {replaceState})`, Vergleich per `history.replaceState`. Unterschiedlich, aber außerhalb des Kern-Scopes.
- Geteilte Bausteine liegen unter `R/lib/components/shared/` mit `context="route"|"vergleich"` bzw. `kind`.

## Dependencies
- Upstream: SvelteKit `page.url.searchParams`, `MTabBar`.
- Downstream: Home-Schnellaktionen, Listen, Kebab/Action-Sheet, Hub-interne Sprunglinks, Flush-Guards (Trip :168, Vergleich `wertebereicheVergleichSpeicherung.ts:251`), Badges-Interface.
- Backend/Mails: **keine** `?tab=`-Links in `internal/`, `src/`, `api/`, `cmd/`. Alte Kennungen stecken nur in Lesezeichen/Verlauf der Nutzer → Umleitung genügt.
- Kein localStorage-Merker für den Reiter; er lebt nur in der URL.

## Existing Specs
- `docs/specs/modules/compare_layout_tab_dissolution.md` (RETIRED_TABS-Muster)
- `docs/specs/modules/feat_1273_s3_redirect.md` (Home-Links `?tab=idealwerte`/`versand`)
- `docs/specs/modules/mobile_tab_leisten_mtabbar.md`
- `docs/specs/modules/feat_2277_s3_reiter_angleichung_rueckbau.md`, `feat_2277_s4_anlege_lockengine.md`, `fix_2277_s2a_wertebereiche_trip_anlegen.md`
- `docs/specs/modules/feat_2284_s1_subscription_header.md`, `feat_2284_s2_trip_kopf.md`
- `docs/specs/modules/compare_weather_metrics_tab.md`
- Keine Spec erwähnt #2287.

## Risks & Considerations
1. **testids enthalten die Kennung** (`trip-detail-tab-${id}`, `-badge-`, `-panel-`, `compare-detail-tab-${id}`, `compare-detail-panel-<id>`). 96 E2E-Specs nutzen sie (z. B. `weather` 53× detail-tab, `stages` 27×, `versand` 25×). Entscheidung nötig: testids mit umbenennen (großer E2E-Diff) oder testids bewusst entkoppeln (stabile Test-Kennung ≠ URL-Kennung). E2E ist nicht in der CI-Ampel → Brüche würden erst auf Staging/`/e2e-verify` auffallen.
2. **Unit-Tests nageln Alt-Kennungen fest**: u. a. `issue_1273_s3_redirect_links.test.ts:82-94`, `issue_850_alert_metrics_stale.test.ts:69`, `routes/trips/trip_edit_leitet_auf_detailseite_um.test.ts:44-46`, `alarme_tab_sections.test.ts:96-101`, `safeRedirect.test.ts:13`. Diese laufen in der Ampel (`frontend-test`).
3. **Alte Lesezeichen**: Umleitung `overview/stages/weather/alerts/briefings/preview` (Trip) und `idealwerte/layout` (Vergleich) muss für beide Hubs gelten. Ein unbekannter `?tab=` soll nicht mehr still fallen (AC-1-Entwurf).
4. **Bestandsbugs im Umfeld**: Home `?tab=preview` auf Vergleich (:585), Trip-Liste und `WeatherSummaryCard` mit `#weather` (Hash). Werden durch das gemeinsame Resolve teils mitgelöst (preview→vorschau), Hash-Links müssen explizit umgestellt werden.
5. **Pendant-Sperre / Teilung**: `subscriptionTabs(kind)` + `resolveTab()` gehören nach `shared/`; `compareTabsResolve.ts` wird dann Delegate oder entfällt. Panels und Flush-Guards bleiben je Hub, vergleichen aber auf neue Literale.
6. **Kennung `etappen` vs. `punkte`**: Issue-Zielbild nennt `punkte|etappen|orte`. Trip-Anlegen hat bereits `etappen` (+ `wegpunkte` separat). Klären in der Analyse.
7. **LoC-Limit 250**: Produktivcode moderat, Testanpassungen zählen gegebenenfalls nicht → vorher `workflow.py status` prüfen; bei Bedarf `loc_limit_override`.

## Analysis

### Type
Feature (type:rework, Epic #2345 Etappe P2) — Konvergenz Trip/Ortsvergleich, keine neue Nutzerfunktion.

### Verifikation Ist-Stand (Explore, 2026-10-05)
Zeilennummern oben stimmen (CompareTabs `resolve` real :135-137). testids interpolieren die Kennung direkt
(`TripTabs.svelte:106/107/195`, `CompareTabs.svelte:149`). Kein `?tab=` in Go/Python. `wertebereicheTabId`
nur im Test. E2E-Treffer (Zeilen):
- `trip-detail-tab-*` 106: overview 10 · stages 27 · weather 53 · alerts 6 · briefings 7 · preview 3
- `compare-detail-tab-*` 98: davon nur `idealwerte` 12 betroffen (übrige Kennungen bleiben gleich)
- plus `trip-detail-panel-*`/`-badge-*`, `compare-detail-panel-idealwerte`

Unit-Tests (Ampel `frontend-test`) mit Alt-Kennungen: `alerts-tab/issue_850_alert_metrics_stale.test.ts:69`,
`compare/__tests__/issue_1273_s3_redirect_links.test.ts:82-94`, `utils/safeRedirect.test.ts:13`,
`routes/trips/trip_edit_leitet_auf_detailseite_um.test.ts:44-46`,
`compare/__tests__/compare_layout_tab_dissolution.test.ts:207` (`?tab=layout` → bleibt als Alt-Umleitung gültig),
`shared/__tests__/alarme_tab_sections.test.ts:28,96-101`.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `R/lib/components/shared/subscriptionTabs.ts` | CREATE | `subscriptionTabs(kind)`, `LEGACY`-Map (kind-übergreifend), `resolveTab(kind, raw) → {tab, known, legacy}` |
| `R/lib/components/compare/compareTabsResolve.ts` | DELETE | einziger produktiver Importeur ist CompareTabs |
| `R/lib/components/trip-detail/TripTabs.svelte` | MODIFY | Tabelle/resolve aus shared, Default `uebersicht`, Flush-Guard-Literale, URL-Bereinigung bei Alt-Kennung |
| `R/lib/components/compare/CompareTabs.svelte` | MODIFY | dito; `idealwerte`→`wertebereiche` in Vergleichen, Panel-testids, `handleValueChange` |
| `R/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts` | MODIFY | `SELBST_SPEICHERNDE_VERGLEICH_REITER`: `idealwerte`→`wertebereiche` |
| `R/lib/components/shared/alarme-tab/alarmeTabSections.ts` | MODIFY | `wertebereicheTabId` löschen |
| `R/routes/trips/[id]/+page.svelte`, `R/routes/compare/[id]/+page.svelte` | MODIFY | Defaults/`tabNachUebernahme`/Sprunglinks |
| `R/routes/+page.svelte` (Home) | MODIFY | `TRIP_TAB_MAP` + alle `?tab=`-Links auf neue Kennungen; Vergleich `preview`→`vorschau` (Bestandsbug) |
| `R/routes/trips/+page.svelte` | MODIFY | `?tab=preview`→`vorschau`; `#weather`→`?tab=wetter-metriken` (Bestandsbug) |
| `R/routes/compare/+page.svelte` | MODIFY | prüfen (`vorschau` bereits neu) |
| `R/lib/components/edit/WeatherSummaryCard.svelte` | MODIFY | `#weather`→`?tab=wetter-metriken` (Bestandsbug) |
| `R/lib/components/trip-detail/{HubOverview,BriefingPreviewCard,AlertsPreviewCard,PreviewCard}.svelte`, `alerts-tab/AlertPreviewCard.svelte` | MODIFY | Sprunglinks auf neue Kennungen |
| `R/lib/components/shared/VersandTab.svelte:305`, `TripNewEditor.svelte:366` | MODIFY | `onJump('stages')`→`'etappen'` (Übersetzung vereinfachen) |
| Unit-Tests (Liste oben) | MODIFY/DELETE | auf neue Kennungen; `wertebereicheTabId`-Test löschen |
| `R/lib/components/shared/__tests__/subscription_tabs_resolve.test.ts` | CREATE | beide kinds, alle Alt-Kennungen, kind-fremde, unbekannt |
| E2E-Specs (`trip-detail-*`, `compare-detail-*-idealwerte`) | MODIFY | mechanischer Literal-Tausch (Script, Wortgrenzen, danach `rg` auf Altliterale = 0) |

Nicht anfassen (andere Namensräume): `WeatherMetricsTab.svelte:1018`/`tripSpeicherung.ts:141` (Speicher-Schlüssel),
`subscriptionHelpers.ts:300` (Action-ID `preview`), Kebab-Keys der Trip-Liste.

### Scope Assessment
- Files: ~20 produktiv + ~7 Unit-Tests + E2E-Specs (mechanisch)
- Estimated LoC produktiv: grob +180/-120 (neues Modul ~80, Literal-Tausch ~25 Stellen, Löschungen ~45) → knapp am Limit 250; vor `/50` `workflow.py status`, ggf. `loc_limit_override 500`
- Risk Level: MEDIUM — fachlich simpel, aber breit (alle Sprunglinks + E2E-testids; E2E nicht in der Ampel → erst `/e2e-verify` deckt Brüche auf)

### Technical Approach (Empfehlung)
1. **Ein geteiltes Modul** `shared/subscriptionTabs.ts`: gemeinsame Kennungen
   `uebersicht · etappen|orte · wetter-metriken · wertebereiche · alarme · versand · vorschau`. `LEGACY`-Map gilt
   kind-übergreifend: `overview→uebersicht`, `stages→etappen`, `weather→wetter-metriken`, `alerts→wertebereiche`,
   `briefings→versand`, `preview→vorschau`, `idealwerte→wertebereiche`, `layout→wetter-metriken`; außerdem
   `orte`↔`etappen` je kind. Reihenfolge: eigene Tabelle → LEGACY → Fallback `uebersicht`.
2. **Etappen-Kennung = `etappen`** (nicht `punkte`): Trip-Anlegen nutzt `etappen` schon; `punkte` existiert nirgends.
3. **URL-Bereinigung:** Bei erkannter Alt-Kennung einmal `replaceState` auf die neue Kennung (Lesezeichen heilen sich,
   aktive URL eindeutig). Je Hub im bestehenden Muster (Trip `goto`, Vergleich `history.replaceState`).
4. **Unbekannter `?tab=`** (weder neu noch alt): Übersicht wie bisher, keine neue UI. AC-1 des Issues ist durch die
   Umleitung erfüllt (alte Links fallen nicht mehr still).
5. **testids mitumbenennen** (Option A), im selben Ticket: dauerhaft stabile Alt-testids würden genau die Drift
   konservieren, die das Epic beseitigt; Folgeticket hieße stumm rote E2E. Tausch ist mechanisch (Testcode, zählt nicht ins LoC).
6. **Bestandsbugs mitlösen:** Home-Vergleich `?tab=preview` (landet heute auf Übersicht), `#weather`-Hash-Links (3 Stellen).
7. **Anlege-Editoren außerhalb des Scopes** (kein `?tab=`, interne Lock-Engine-IDs `route/vergleich/metriken`) — eigene
   Konvergenz-Etappe im Epic. `compareTabsResolve.ts` entfällt ersatzlos.

### Dependencies
Upstream SvelteKit `page.url`, `MTabBar` (bekommt Items, kennt keine Kennungen). Downstream: Home, Listen, Hub-Sprunglinks,
Flush-Guards, Badges-Interface (`TripTabs.svelte:25-33/:63-71` — Badge-Keys mit umbenennen). Kein Backend, keine Mails.

### Open Questions
- Keine PO-Fragen. Technische Entscheidungen oben getroffen (Etappen-Kennung, testids, URL-Bereinigung, Scope Anlege-Editoren).

## Hinweise aus TDD RED für /50 (2026-10-05)
- Worktree braucht `frontend/node_modules` → Symlink auf `/home/hem/gregor_zwanzig/frontend/node_modules` (gitignored), sonst Umgebungs-Rot.
- Die drei Dateien `subscription_tabs_resolve`, `hub_reiter_gemeinsame_aufloesung`, `reiter_sprunglinks_nur_neue_kennungen` brachen im RED-Lauf schon beim Laden ab (Modul fehlt) — ihre Einzeltests liefen noch nie gegen echten Code. Nach GREEN genau hinsehen.
- Harness (`svelteInstanzPruefstand.ts`, neue Option `{ jsAlsTs }`) führt `$effect`-Rümpfe aus, **nicht** `onMount`: Alt-Kennungs-URL-Bereinigung muss in einem `$effect` stehen (oder einer von dort gerufenen Funktion).
- Hubs müssen `resolveTab`/`subscriptionTabs` aus `shared/subscriptionTabs` importieren (Wertegleichheit wird geprüft), `handleValueChange` und `activeTab` behalten; MTabBar-Items werden über die testid-Form gefunden.
- Nur per E2E/Playwright in `/e2e-verify`: AC-3 (`history.length`/Zurück), AC-10 Klickpfade, AC-12 Panel-testid, AC-13 Anlege-Flow, AC-14 Handy-Viewport, AC-15 (`rg` + E2E-Specs umstellen — noch nicht geschehen, gehört in /50).
