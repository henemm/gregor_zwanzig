# Context: feature-2794-s3a-teil2-leiste (#2794 S3a, Teil-PR 2 „Leiste und Umleitung“)

## Request Summary
Teil-PR 2 der freigegebenen Spec `docs/specs/modules/feat_2794_s3a_reiter_wetter.md` (AC-1 bis AC-8, AC-36): Hub von Trip und Orts-Briefing bekommt die vier Reiter Übersicht · Etappen/Orte · Wetter · Zustellung (neue Kennungen `wetter`, `zustellung`), alte Kennungen werden umgeleitet, die Anlege-Ketten folgen, Zustellung wird Übergangsreiter aus den heutigen Alarm- und Versand-Bausteinen, Reiterleiste und Seitenüberschrift nach Atomic-Design-Soll. Teil-PR 1 (Backend) ist live (PR #2870). Gesamt-Analyse: `docs/context/feature-2794-s3a-reiter-wetter.md`.

## Ist-Lage (gemessen gegen origin/main @ 1b59ef105, 2026-11-09)

**Reiter-Kennungen heute** (`frontend/src/lib/components/shared/subscriptionTabs.ts`):

| | Hub | Anlegen |
|---|---|---|
| Trip | uebersicht, etappen, wetter-metriken, wertebereiche, alarme | route, etappen, wegpunkte, wetter-metriken, wertebereiche, alarme |
| Vergleich | uebersicht, orte, wetter-metriken, wertebereiche, alarme | vergleich, orte, wetter-metriken, wertebereiche, alarme |

- `REITER_DEFINITION` :40–62 (`uebersicht`, `punkte[kind]`, `schwanz` :46–50, `anlegeKopf[kind]` :52–60), `ANLEGE_SCHWANZ_HINWEIS` :67–70 (Schlüssel `wetter-metriken`), `subscriptionTabs()` :83, `anlegeKette()` :88, `LEGACY` :117–128 (overview, stages, weather, alerts, briefings, versand, preview, vorschau, idealwerte, layout), `LEGACY_ANKER` :131 (briefings/versand → Anker `versand`), `resolveTab` :137–151, `versandSprungStart` :155, `bereinigteTabAdresse` :167–178.
- `versand` und `layout` sind heute schon nur Alt-Kennungen (→ `wetter-metriken` + Anker `#versand`).

**Inhalt je Reiter im Hub:**
- Trip `trip-detail/TripTabs.svelte:191–218`: wetter-metriken → `shared/WetterMetrikenVersandPanel context="route"` :207; wertebereiche → `CorridorEditor` / `CorridorEditorMobile` (nur lesen seit S1c-3) :209–213; alarme → `trip-detail/AlarmeScheduleTab.svelte` (Hülle um `shared/AlarmeTab`) :215.
- Vergleich `compare/CompareTabs.svelte`: wetter-metriken → Panel `context="vergleich"` :778–805 (nach Hydration); wertebereiche → CorridorEditor :807–822; alarme → `AlarmeTab` :832–850; orte eigenes Markup :706–776 (compare-eigen erlaubt).
- `shared/WetterMetrikenVersandPanel.svelte`: oben `WeatherMetricsTab` :63, darunter `<section id="versand">` :65 (Trip-Hub `BriefingScheduleTab` :68, Vergleich/Anlegen `VersandTab` :76).

**Inventar (Spec §3, 16 Elemente) heute verortet:**
- Im Reiter alarme (`shared/AlarmeTab.svelte`): ChannelToggle :518/:597, `AlertMetricLevelTable` :538 (nur lesbar), `AlertMetricChannelsBlock` :544, `AlertChannelPicker` :564, `TelegramKurzstilToggle` :576, `AlertCooldownCard` :585, `AlertQuietHoursCard` :591, `AlertPreviewCard` :605/:608; dazu amtliche Warnungen und Radar (Orte).
- Im Abschnitt `#versand` (`VersandTab.svelte`): Briefing-Kanäle `VTBriefingChannels` (inkl. Telegram-Kurzstil :173), Morgen/Abend + Trend `VTSchedulePlan`, `VTNextBriefing`, Laufzeit `VTLaufzeitRoute`/`VTLaufzeitVergleich`, Aktivieren (nur Vergleich, Snippet `hubActivationCard` CompareTabs :855).
- Im oberen Teil von `WeatherMetricsTab.svelte`: `LayoutTab` (Layout je Kanal, `channel_layouts` :952–978) :1553/:1746, `DayWindowCard` :1597/:1815, Stundenverlauf :1617, 3-Tages-Ausblick `OutlookLayoutControls` :1654/:2028, Mail-Inhalt `MailInhaltCard` :2007 (route), amtliche Warnungen :2043, Nacht-Block :2061 (route).

**Speichern beim Reiterwechsel / Dirty-Guard:**
- Trip `TripTabs.svelte:163–169`: Liste aktiver Reiter (wertebereiche, wetter-metriken, alarme, etappen) → `saveController.flush()`.
- Vergleich `CompareTabs.svelte:179` → `sichereSelbstSpeichererVorReiterwechsel()` in `corridor-editor/wertebereicheVergleichSpeicherung.ts:265–273`, Liste `SELBST_SPEICHERNDE_VERGLEICH_REITER` :254–258. Lazy-Hydration an Kennungen gekoppelt :388, 415, 471, 525, 556.
- **Achtung:** gleiche Wörter als Speicher-Besitzer (nicht Reiter): `saveController.schedule(…, 'versand')` (`BriefingScheduleTab.svelte:107`, `versandVergleichSpeicherung.ts:325`), `'wetter-metriken'`/`'wetter-metriken-report-config'` (`WeatherMetricsTab.svelte:1051–1073`), `'wertebereiche'` (CorridorEditor :301), `'alarme'` (AlarmeTab :420). Diese bleiben unverändert (Speicherweg muss gleich bleiben, AC-8).

**Weitere fest verdrahtete Kennungen:** `infoboxKeys.ts:11–23`, `anlegeLockEngine.ts:51` (`letzterId='alarme'`), `hubUebersichtModell.ts:51,98,248,259`, `HubOverview.svelte:152` (`makeJumpHandler('wetter-metriken','versand')`), `edit/WeatherSummaryCard.svelte:29`, `alerts-tab/AlertPreviewCard.svelte:71`, `routes/+page.svelte:143,292–304,367,470,476`, `routes/trips/+page.svelte:109–110`, `routes/compare/+page.svelte:125–126`, `routes/compare/[id]/+page.svelte:370` (`?tab=wetter-metriken#versand`).

**Anlege-Editoren:** `trip-new/TripNewEditor.svelte` (anlegeKette :18/101, Literale :281, 293–295, 814–866, 889–923, 1175–1261), `trip-new/tripNewLogic.ts` (`TabId` :27, `TAIL` :35, `PROGRESS_STEPS` :101), `compare-new/CompareNewEditor.svelte` (`CompareNewTabId` :91–93, :176, 274–276, 421), Rahmen `shared/anlege-rahmen/AnlegeRahmen.svelte`.

**Badges:** Trip `TripTabs.svelte:60–66` (etappen = stages.length; wertebereiche = aktive alert_rules → entfällt), testid `trip-detail-tab-badge-<id>`; Vergleich `orteCount` CompareTabs :243/:158.

**Seitenkopf (AC-36):** `shared/hub-kopf/HubKopf.svelte` (`titleSize` Default 38) → `shared/subscription-header/SubscriptionHeader.svelte:123` h1: mobil `--g-text-xl` (20px), `desktop:text-[38px]`; Breakpoint `desktop` = `min-width: 900px` (`app.css:92`). Trip `TripHeader.svelte:141,161–162`, Vergleich `routes/compare/[id]/+page.svelte:364,384`, beide `titleSize={38}`. **Widerspruch zur Spec („heute 20 px“) in der Analyse per Messung klären.**

**Reiterleiste Optik:** `MTabBar.svelte` (generisch, `items`; `data-slot="segmented"`, `segmented-badge`), Segmented-Box `app.css:502–528`. Tokens `--g-rule`, `--g-accent`, `--g-paper-deep`, `--g-ink-3` vorhanden.

**i18n:** `aktionen.weather` („Wetter-Metriken“) und `aktionen.alarms` werden auch im Aktionsmenü (`subscriptionActions.ts:40–41`), `WeatherConfigDialog.svelte:154`, `HubOverview.svelte:121` benutzt ⇒ neue Reiter-Schlüssel `aktionen.reiter.wetter` / `aktionen.reiter.zustellung` statt Umbenennen. Anker-Abgleich `trip-detail/__tests__/f9KatalogAnker.ts`.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/shared/subscriptionTabs.ts` | einzige Reiter-Definition, LEGACY, Anlege-Kette |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte`, `compare/CompareTabs.svelte` | Hub-Leisten, Reiter-Inhalte, Flush vor Reiterwechsel, Badges |
| `frontend/src/lib/components/mobile/MTabBar.svelte`, `frontend/src/app.css:502–528` | Leistenoptik (Segmented entfernen, Pill mobil behalten) |
| `frontend/src/lib/components/shared/WetterMetrikenVersandPanel.svelte` | heute Wetter + Versand in einem Reiter; wird aufgeteilt |
| `frontend/src/lib/components/shared/AlarmeTab.svelte`, `trip-detail/AlarmeScheduleTab.svelte` | Alarm-Bausteine; wandern unverändert in Zustellung |
| `shared/zustellung-tab/*` (neu) | Übergangsreiter, `context="route"|"vergleich"` |
| `shared/corridor-editor/wertebereicheVergleichSpeicherung.ts` | Selbst-Speicherer-Liste je Reiter (Vergleich) |
| `trip-new/*`, `compare-new/*`, `shared/anlegeLockEngine.ts`, `shared/infoboxKeys.ts` | Anlege-Ketten |
| `hub-uebersicht/hubUebersichtModell.ts`, `trip-detail/HubOverview.svelte`, `routes/+page.svelte`, Listen-Seiten | Sprunglinks auf Reiter (nur Kennungen nachziehen; Inhalt U3/U4/K17 ist Teil-PR 4) |
| `shared/subscription-header/SubscriptionHeader.svelte`, `shared/hub-kopf/HubKopf.svelte` | h1 (AC-36) |
| `frontend/src/lib/i18n/messages/{de,en}/aktionen.json` | neue Reiter-Labels |
| `tests/golden/f9_trip_flaechen/*`, `f10_vergleich_flaechen/*`, `f3_home_listen/*` | Golden-Referenzen mit Reiter-testids |

## Existing Patterns
- Eine Definition für Hub und Anlege-Kette (`REITER_DEFINITION`), Alt-Kennungen über `LEGACY` + `bereinigteTabAdresse` (replaceState) — bewährt seit #2287/#1273.
- Shared-Komponente mit `context="route"|"vergleich"` (Muster `WetterMetrikenVersandPanel`, `AlarmeTab`).
- Golden-Prüfstände `f9Pruefstand.ts` / `f10Pruefstand.ts` (SSR-Render ohne Mocks) für Leisten-Struktur.
- Kern-Tests `node --test` (kein Vitest), E2E Playwright gegen Staging.

## Dependencies
- Upstream: `saveController`, Vergleichs-Speicherer (`versandVergleichSpeicherung`, `alarmeVergleichSpeicherung`, `wertebereicheVergleichSpeicherung`), i18n-Katalog.
- Downstream: Teil-PR 3 (Reiter Wetter ersetzt den Inhalt hinter `wetter`), Teil-PR 4 (Entfernen, Übersicht U3/U4, K17, Hilfe X1), S3b #2795 (baut Zustellung um).

## Existing Specs
- `docs/specs/modules/feat_2794_s3a_reiter_wetter.md` (freigegeben, diese Arbeit)
- `docs/specs/modules/mobile_tab_leisten_mtabbar.md` (Pill-Leiste mobil bleibt)
- `docs/specs/modules/rework_2845_hub_reiterleiste.md` (PR #2871, offen: eine Leistenoptik ohne `size`-Variante)
- `feat_2287_tab_kennungen`, `rework_2276_s*`, `versand_tab_*`, `layout_tab_route` (implemented; Altkennungen)

## Risks & Considerations
1. **Parallel-PRs:** PR #2871 (#2845, andere Sitzung) ändert TripTabs/CompareTabs/MTabBar und Goldens; PR #2872 (S2b) ändert `AlarmeTab.svelte` und `alerts-tab/*`. Beide vor eigenen Edits an diesen Dateien mergen lassen bzw. danach rebasen; Sitzungen per SendMessage informiert (2026-11-09). Rückmeldung #2871: Merge direkt nach dem letzten CI-Job, danach keine weitere Arbeit an der Hub-Reiterleiste; vor eigenen Edits `origin/main` prüfen und rebasen.
2. **„Kein Element verschwindet“ (AC-7):** Wertebereiche ist nur lesend; nach Spec-Lieferplan zeigt `wetter` in PR 2 vorläufig die bestehende Metrik-Oberfläche. Analyse muss entscheiden, wo die nur-lesende Wertebereiche-Ansicht und die Alarm-Elemente, die später nach Wetter wandern (amtliche Warnungen, Radar, Alarmstufen-Tabelle), bis Teil-PR 3 stehen (vorläufig in Zustellung bzw. unter Wetter), ohne dass etwas wegfällt.
3. **Versand-Teile im WeatherMetricsTab** (Layout je Kanal, Ausblick, Nacht, Stundenverlauf, Mail-Inhalt) gehören laut Inventar in Zustellung, stecken aber im >2000-Zeilen-`WeatherMetricsTab`. Herauslösen vs. vorläufig in Wetter lassen ist abzuwägen (Wegwerf-Arbeit, da Teil-PR 3 den Reiter ersetzt und S3b die Zustellung).
4. **Speicher-Besitzer-Strings** (`'versand'`, `'alarme'`, `'wetter-metriken'`) dürfen nicht mit den Reiter-Kennungen mitumbenannt werden (AC-8 „derselbe Speicherweg“).
5. **Flush/Hydration** an Kennungen gekoppelt (Trip-Liste :163–169, Vergleich :254–258, Hydration :388ff) — Datenverlust beim Reiterwechsel, wenn die neue Kennung fehlt.
6. **Testumzug:** ca. 60 Kern-Testdateien und ~89 E2E-Specs mit alten Kennungen, Goldens f9/f10/f3/f7/f8. Spec: Tests ausschließlich entfallener Oberflächen löschen statt umbiegen.
7. **AC-36:** Code zeigt `desktop:text-[38px]` ab 900px — Spec sagt „heute 20 px“. Vor RED auf Staging messen; ggf. greift die Klasse nicht (Tailwind-Arbitrary + custom-variant) oder Spec-Annahme ist überholt.
8. **Badge Wertebereiche** entfällt, Etappen/Orte-Badge bleibt.

## Analysis

### Type
Feature (Teil-PR 2 der freigegebenen Spec; ACs AC-1 bis AC-8, AC-36)

### Befunde der Analyse (2026-11-09)
1. **AC-36 ist am Desktop bereits erfüllt.** Staging-Messung 1280×900 (nur lesend, Konto `GZ_AUTH_USER` aus Staging-`.env`): Trip-Hub `/trips/4cffd11c` h1 = 38 px/600, Vergleichs-Hub `/compare/cp-21e198c1b74020dd` h1 = 38 px/600. Gebautes Staging-CSS enthält `.desktop\:text-\[38px\]` im 900-px-Block; `HubKopf.svelte:62` setzt 38, `TripHeader.svelte:162` und `routes/compare/[id]/+page.svelte:384` übergeben `titleSize={38}`. Die „20 px“ der Spec-Prämisse stammen von der h1 der Anlege-Seiten (`/trips/new`, `/compare/new`: „Route“/„Vergleich“ 20 px) bzw. vom mobilen `--g-text-xl`. ⇒ AC-36 bleibt unverändert gültig (Then 30–38 px) und wird in PR 2 als **Regressionswächter** umgesetzt (Playwright ≥1024 px, beide Kontexte, derselbe Kopf-Baustein); die Klammer „heute 20 px“ wird in Phase 3 als sachliche Korrektur im Spec-Changelog vermerkt (Akzeptanz unverändert).
2. **Zustellungs-Blöcke im WeatherMetricsTab (WMT) teilen State und Speicher-Owner mit der Metrik-Auswahl.** LayoutTab (`channel_layouts`, WMT :1553 vergleich / :1746 route, hängt am Gate `reihenfolge` :1552/:1743), Stundenverlauf (:1616, nur vergleich), Ausblick (:1646 / :2019), MailInhaltCard (Gate `report_config` :1986, nur route, !createMode, teilt `reportConfig` mit DayWindowCard), Nacht-Block (:2052, route, !createMode, ohne Abschnittsnamen). Speichern route: Owner `'wetter-metriken'` (`scheduleAutoSave` :1035–1052, `buildWeatherPayload` :942, Filter `WETTER_DISPLAY_KEYS` pickEigenfelder.ts:77; Server ersetzt `channel_layouts` komplett) und `'wetter-metriken-report-config'` (:1063–1073, `WETTER_REPORT_KEYS` pickEigenfelder.ts:64 inkl. day_window). Vergleich: ein Owner `'wetter-metriken'` mit 10-Feld-Snapshot (`weather-metrics-tab/weatherMetricsCompareSave.ts:322/370/490–535`).
   ⇒ **Zwei gleichzeitig gemountete WMT-Instanzen überschreiben sich mit veraltetem Stand (Datenverlust).** Herauslösen in eine eigene Komponente mit eigenem Speichern ist deshalb verworfen.
3. `sections = $derived(weatherMetricsTabSections(context))` (WMT :239) ist rein abgeleitet, kein Effekt hängt daran ⇒ ein zusätzlicher Darstellungsfilter setzt keinen State zurück.
4. Montage heute: Hub-Trip per if-Kette (`TripTabs.svelte:206`, Remount + Rehydration über `onTripUpdate`), Hub-Vergleich nach Gate `wetterMetrikenLayoutHydrationBereit && versandHydrated` (`CompareTabs.svelte:780`), TripNewEditor Desktop: je Schritt EINE dauerhafte Instanz mit `style:display` (#932, :889ff; Mobil per `isMobileViewport` XOR), CompareNewEditor per if-Kette mit State im Wizard (:554ff). Der Versand-Abschnitt `<section id="versand">` liegt im Panel (`WetterMetrikenVersandPanel.svelte:65`). Einziger WMT-Mount ist das Panel (TripTabs :207, TripNewEditor :894/:1177, CompareTabs :791, CompareNewEditor :559/:649). AST-Wächter `compare/__tests__/compare_wetter_metriken_wertprops.test.ts:309–460` verlangt das Wertprops-Bündel an jeder WMT-Einbettung.
5. **Parallel-PRs:** #2871 (#2845) ändert MTabBar (size-Prop weg, 1-px-Grundlinie, Accent-Unterstrich, neutraler Badge, mobil Pill), CompareTabs, f10-Goldens, `hub-tab-bar.spec.ts`; nicht app.css/TripTabs. Nach #2871 offen für AC-3: aktiv 600, Badge Mono 10 px, Segmented-Box (`data-slot="segmented"`, `segmented-badge`, app.css:502–528) entfernen. #2872 (S2b) ändert `AlarmeTab.svelte`, `alerts-tab/*`, Glossar, api_contract; Sitzung meldet „inhaltlich fertig, Merge nach CI grün“. Beide vor Implementierung mergen lassen, dann auf `origin/main` rebasen.
6. **Testumzug (Bestandsaufnahme):** 27 Frontend-Kern-Testdateien (88 Treffer), 82 E2E-Dateien (262), 32 Golden-Dateien (f10 14, f9 10, f3 6, f7 2; f8 0), 1 Python (`tests/unit/test_e2e_compare_paritaet_waechter.py`). Literal-Gruppe manuell prüfen: `wetterMetrikenTabRegistration.test.ts`, `tripNewLogic.test.ts`, `trip_new_alarme_reiter.test.ts`, `trip_new_wertebereiche_reiter.test.ts`, `reiterfolge_eine_quelle.test.ts`, `anlege_lock_engine.test.ts`, `infobox_nur_beim_anlegen.test.ts`, `compare_anlege_freischaltung.test.ts`. Redirect-Tests (`hub-reiter-alt-kennungen-umleitung.spec.ts`, `issue_1273_s3_redirect_links.test.ts`) behalten Alt-Kennungen als Eingabe. Corridor-/WMT-Unit-Tests nutzen `'wertebereiche'` nur als Owner ⇒ unberührt.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/subscriptionTabs.ts` | MODIFY | `wetter`/`zustellung` in `REITER_DEFINITION`, Anlege-Köpfe, `ANLEGE_SCHWANZ_HINWEIS`, `LEGACY` (wetter-metriken/wertebereiche/layout → wetter; alarme/versand/briefings → zustellung), `LEGACY_ANKER` → zustellung#versand, `versandSprungStart` |
| `shared/weather-metrics-tab/weatherMetricsTabSections.ts` | MODIFY | zweiter Parameter `bereich` (`wetter`/`zustellung`/`alles`); neue Abschnittsnamen `layout_kanal`, `nachtblock`; Wetter = grundauswahl, tagesfenster, sms_schwellen, official_alerts; Zustellung = reihenfolge/layout_kanal, stundenverlauf, ausblick, report_config (Mail-Inhalt), nachtblock |
| `shared/WeatherMetricsTab.svelte` | MODIFY | Prop `bereich`, Gates auf neue Abschnittsnamen (Nacht-Block :2052); Speicherwege/Owner unverändert |
| `shared/WetterMetrikenVersandPanel.svelte` | MODIFY | `bereich` durchreichen; Versand-Abschnitt nur bei `bereich=zustellung` |
| `shared/zustellung-tab/ZustellungTab.svelte` | CREATE | Übergangsreiter `context="route"|"vergleich"`: WMT(bereich=zustellung) + Versand (`BriefingScheduleTab`/`VersandTab`, Anker `#versand`, Aktivieren im Vergleich) + `AlarmeTab` unverändert (inkl. amtl. Warnungen-Alarm, Radar, Alarmstufen-Tabelle bis PR 3) |
| `trip-detail/TripTabs.svelte` | MODIFY | Reiter wetter (Panel bereich=wetter + nur-lesender CorridorEditor darunter), zustellung (ZustellungTab), Flush-Liste :163–169, Badge Wertebereiche entfällt |
| `trip-detail/AlarmeScheduleTab.svelte` | MODIFY | Hülle wird in ZustellungTab verwendet (Löschen erst PR 4) |
| `compare/CompareTabs.svelte` | MODIFY | Reiter wetter/zustellung, Lazy-Hydration :388/415/471/525/556 je neuer Kennung, Panel-Gate :780 je Reiter, `hubActivationCard` in Zustellung |
| `shared/corridor-editor/wertebereicheVergleichSpeicherung.ts` | MODIFY | `SELBST_SPEICHERNDE_VERGLEICH_REITER` :254–258 auf wetter/zustellung |
| `mobile/MTabBar.svelte`, `frontend/src/app.css` | MODIFY | (nach #2871) aktiv 600, Badge Mono 10 px, Segmented-Markup und Box :502–528 entfernen; mobil Pill bleibt |
| `trip-new/TripNewEditor.svelte`, `trip-new/tripNewLogic.ts` | MODIFY | Kette route·etappen·wegpunkte·wetter·zustellung (`TabId`, `TAIL`, `PROGRESS_STEPS`), EINE dauerhafte WMT-Instanz, deren `bereich` dem aktiven Schritt folgt; Wertebereiche-Schritt entfällt |
| `compare-new/CompareNewEditor.svelte` | MODIFY | Kette vergleich·orte·wetter·zustellung (`CompareNewTabId` :91–93) |
| `shared/anlegeLockEngine.ts`, `shared/infoboxKeys.ts` | MODIFY | `letzterId='zustellung'`, Infobox-Schlüssel |
| `hub-uebersicht/hubUebersichtModell.ts`, `trip-detail/HubOverview.svelte:152`, `edit/WeatherSummaryCard.svelte:29`, `alerts-tab/AlertPreviewCard.svelte:71`, `routes/+page.svelte`, `routes/trips/+page.svelte`, `routes/compare/+page.svelte`, `routes/compare/[id]/+page.svelte:370` | MODIFY | Sprungziele auf neue Kennungen (nur Kennung; Inhalt U3/U4/K17 = PR 4) |
| `frontend/src/lib/i18n/messages/{de,en}/aktionen.json` | MODIFY | neue Schlüssel `aktionen.reiter.wetter` / `aktionen.reiter.zustellung` (bestehende `aktionen.weather`/`alarms` bleiben fürs Aktionsmenü) |
| Tests (Befund 6), Goldens f9/f10/f3/f7 | MODIFY/DELETE | Kennungen umstellen; Tests ausschließlich entfallener Reiter löschen |
| neue Kern-Tests | CREATE | `weatherMetricsTabSections` je bereich (disjunkt, Vereinigung = alles), LEGACY/`bereinigteTabAdresse` für alle Alt-Kennungen inkl. `#versand`, Flush-Listen enthalten wetter+zustellung, Wächter „Speicher-Owner-Strings unverändert“, Wächter „höchstens eine WMT-Instanz“ (Hub und Anlegen) |

### Scope Assessment
- Produktion: ca. 20 Dateien, grob +900/−400 LoC (größte Brocken: TripTabs/CompareTabs, TripNewEditor, ZustellungTab, subscriptionTabs)
- Tests: ca. 140 Dateien Umzug (überwiegend Kennungs-Ersetzung), ca. 6 neue Kern-Testdateien
- Risk Level: **MEDIUM-HIGH** — reine Umordnung ohne neue Speicherwege, aber Datenverlust-Risiko bei Doppel-Instanz, Flush-Listen, Vergleichs-Hydration-Gate und Anlege-Ketten

### Technical Approach
Empfehlung (Plan-Bewertung + eigene Prüfung):
- **Ein PR, drei lauffähige Commits:** (1) Leiste nach Soll + AC-36-Regressionswächter; (2) Kennungen, LEGACY, Hub- und Anlege-Ketten, Flush/Hydration (wetter zeigt vorübergehend das bisherige Panel inkl. Versand, zustellung zeigt AlarmeTab ⇒ nichts verschwindet); (3) `bereich`-Filter: Zustellungs-Blöcke und Versand ziehen nach `zustellung`, nur-lesende Wertebereiche-Ansicht hängt unter `wetter`.
- **`bereich` als reiner Darstellungsfilter** in `weatherMetricsTabSections(context, bereich)` — Speicherwege, Owner, Hydration bitgleich (AC-8). **Nie zwei WMT-Instanzen gleichzeitig:** Hub mountet je Reiter (if-Kette), Trip-Anlegen hält EINE dauerhafte Instanz, deren `bereich` dem Schritt folgt; Vergleichs-Anlegen per if-Kette mit Wizard-State.
- **AlarmeTab bleibt unverändert und vollständig im Reiter Zustellung** (amtl. Warnungen-Alarmschalter, Radar Orte, nur-lesende Alarmstufen-Tabelle eingeschlossen) bis PR 3; kein Zerlegen jetzt, weil #2872 genau diese Dateien ändert und PR 3 sie ohnehin neu verortet.
- **Speicher-Owner-Strings** (`'wetter-metriken'`, `'wetter-metriken-report-config'`, `'versand'`, `'alarme'`, `'wertebereiche'`) werden NICHT umbenannt; Wächter-Test.
- Altlink `?tab=wetter-metriken#versand` (`routes/compare/[id]/+page.svelte:370`) → `zustellung` (Anker `#versand` gewinnt), konsistent zu AC-5.

### Dependencies
- Vorher gemergt und rebased: PR #2871 (Leiste), PR #2872 (AlarmeTab/alerts-tab). Teil-PR 1 ist live (#2870).
- Downstream: Teil-PR 3 ersetzt Inhalt hinter `wetter` (nach PR #2862), Teil-PR 4 löscht Altkomponenten, S3b #2795 baut Zustellung um.

### Open Questions
- Keine Produktfrage offen. Technisch in Phase 3 festzulegen: Trip-Anlegen ohne Wertebereiche-Schritt — wirkt die Corridor-Vorbelegung (`handleVorbelegungFertig`, TripNewEditor :909) heute nur über den sichtbaren Schritt? Falls ja, Vorbelegung ohne Oberfläche erhalten (AC-6 „vollständig gespeichert“).
