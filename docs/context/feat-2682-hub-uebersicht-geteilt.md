# Context: feat-2682-hub-uebersicht-geteilt

## Request Summary
Issue #2682 (Nebenbefund aus #2347 S4, Unter-Issue von Epic #2345): Die Übersicht im Detail-Hub ist zweimal gebaut. Der Ortsvergleich hat sie inline in `CompareTabs.svelte`, der Trip in `trip-detail/HubOverview.svelte`. Ziel ist ein geteilter Baustein unter `components/shared/` mit dem Parameter `context="route"|"vergleich"`. Nach CLAUDE.md und ADR-0097 darf nur Folgendes compare-eigen bleiben: der Orte-Reiter, die transponierte Übersicht und das Compare-Mail-Template.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/compare/CompareTabs.svelte:711-882` | Vergleichs-Übersicht (`activeTab === 'uebersicht'`, testid `compare-detail-panel-uebersicht`), Aufbau siehe unten |
| `CompareTabs.svelte:716-749` | Mobil: Kennzahlen-Raster 2×2 (Status in Kurzform, Nächster Versand, Zuletzt raus, Kanäle) |
| `CompareTabs.svelte:751-796` | Desktop: 5 Kennzahlen (Status in Langform, Nächster Versand, Briefings, Zuletzt raus, Kanäle) |
| `CompareTabs.svelte:802-835` | Mobil: Zusammenfassungs-Zeilen mit Pfeil (snippet `summaryChevron`, testid `hub-summary-row-mobile`) |
| `CompareTabs.svelte:837-872` | Desktop: Zusammenfassungs-Karten Orte / Wertebereiche / Versand (testid `compare-hub-versand-edit`) |
| `CompareTabs.svelte:877` | `<BriefingHistory kind="vergleich">` |
| `CompareTabs.svelte:1033-1051` | Snippet `hubActivationCard`: **KEIN toter Code** (Korrektur Analyse 2026-11-01) — wird in `:974` als `activation={hubActivationCard}` an `WetterMetrikenVersandPanel` übergeben. NICHT löschen, gehört nicht zur Übersicht. |
| `CompareTabs.svelte:1164-1263` | CSS `.hub-mobile-*` / `.hub-summary-*` |
| `CompareTabs.svelte:199-228` | Datenquellen: `deriveStatusWithScheduleOverride`, `formatNextBriefing(erstelleNaechstesBriefingLader({context:'vergleich'}))`, `presetBriefingTimesLabel`, `formatLastSent`, `channelNamesLabel`, `presetProfileLabel` |
| `frontend/src/lib/components/compare/subscriptionHelpers.js` | Helfer für Status, Kanäle und Zeiten; heute compare-eigen |
| `frontend/src/lib/components/trip-detail/HubOverview.svelte` (197 Z.) | Trip-Übersicht: Etappen (FullProfile, TripStageRow mit Risiko), Wetter-Metriken-Karte (4 Zustände), „Briefings laufen“ (ReportLine, **Kanäle fest `['email','telegram']`**), BriefingHistory, „Alerts (letzte 7 Tage)“ als **fester Text** |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte:191` | Einbindung: `<HubOverview {trip} onJump={handleValueChange} {metricsCatalog} />` |
| `frontend/src/lib/components/compare/CompareDetail.svelte:33` | Einbindung von CompareTabs |
| `frontend/src/lib/components/shared/versand-tab/naechstesBriefingLader.svelte.ts` | Bereits geteilt, mit `context` |
| `frontend/src/lib/components/shared/BriefingHistory*` | Bereits geteilt, mit `kind` |
| `frontend/src/lib/components/shared/subscription-header/SubscriptionHeader.svelte`, `shared/subscriptionTabs.ts` | Vorlage für einen Baustein mit `context` (#2284) |
| `atoms/Stat.svelte` + `molecules/Stat.svelte` | Kennzahlen-Baustein, **liegt doppelt vor** |
| `trip-detail/TripStatusBadge.svelte`, `compare/CompareStatusPill.svelte`, `molecules/CompareStatusRow.svelte` | Status-Paar, mögliche Pendant-Fläche |

## Existing Patterns
- Geteilte Organismen erhalten `context="route"|"vergleich"` (Muster: VersandTab, AlarmeTab, WeatherMetricsTab, SubscriptionHeader).
- Erlaubte inhaltliche Verzweigung nach `context`: Etappen ↔ Orte (fachlich begründet).
- Die Sprunglinks beider Hubs laufen über `handleValueChange(tab, anchor?)` / `onJump` mit den neuen Reiter-Kennungen (#2287).
- Mobil/Desktop-Umschaltung im Vergleich: `isMobileViewport` per matchMedia ≤899px (`CompareTabs.svelte:168-175`).

## Dependencies
- Upstream: atoms (`Card`, `Btn`, `Eyebrow`, `SectionH`, `Dot`), `BriefingHistory`, `erstelleNaechstesBriefingLader`, `compare/subscriptionHelpers.js`, `shared/trip-metrics` (`resolveTripMetricsOverviewState`), `fetchStageRisk`.
- Downstream: `TripTabs.svelte`, `CompareTabs.svelte`/`CompareDetail.svelte`; dazu Unit- und E2E-Tests (siehe unten).

## Tests (betroffen)
- **Unit (node --test):**
  - `compare/__tests__/compare_hub_fidelity.test.ts` (13 Fälle, liest den Quelltext von CompareTabs)
  - `compare/__tests__/compare_mobile_shared_hub.test.ts` (6)
  - `trip-detail/__tests__/hubOverviewMetricsBlock_structure.test.ts` (12)
  - `trip-detail/__tests__/briefings_karte_echte_zeiten_render.test.ts`
  - `shared/__tests__/reiter_sprunglinks_nur_neue_kennungen.test.ts:195`
  - `shared/__tests__/versand_sprung_auf_wetter_metriken.test.ts:41`
  - `shared/briefing_history_hubs.test.ts:56`
  - `shared/versand-tab/__tests__/naechstes_briefing_verdrahtung.test.ts`
  - Viele Tests lesen den Quelltext an einem festen Dateipfad. Wenn die Übersicht herausgelöst wird, müssen ihre Zusicherungen dem neuen Ort folgen.
- **E2E:**
  - `e2e/compare-hub-fidelity-s8c.spec.ts:122-210`: Kopf `gz-eigenstaendig` mit Begründung #2682
  - `e2e/hub-tab-bar.spec.ts`: HT-10 läuft nur für den Vergleich; die Sprungknöpfe sind je Art fest eingetragen (`:248-258`)
  - `e2e/hub-versand-briefing-zeiten.spec.ts`
  - `e2e/hub-reiter-alt-kennungen-umleitung.spec.ts`
  - `e2e/issue-616-trip-one-surface.spec.ts:110`
- **Wächter:**
  - `tests/unit/test_e2e_compare_paritaet_waechter.py`: Kopf `gz-eigenstaendig` oder `HUB_KINDS`-Schleife.
  - `.claude/hooks/pendant_gate.py`: Ein neuer neutral benannter Baustein unter `shared/` löst nicht aus. Löschen löst nie aus. `BEKANNTE_PAARE` enthält weder HubOverview noch CompareTabs.

## Existing Specs / ADRs
- `docs/adr/0097-trip-ortsvergleich-code-teilung.md` (Kern), `0032`, `0023`
- `docs/specs/modules/feat_2347_s4_paritaets_e2e.md` (Befund 6, `:193`, AC-20/22): beschreibt die Abweichung heute ausdrücklich als offen mit Verweis auf #2682
- `docs/reference/gates_und_ratschen.md:285-288`: dieselbe Ausnahme; nach dem Umbau anpassen
- `feat_2284_s1_subscription_header.md`, `feat_2284_s2_trip_kopf.md`, `feat_1435_e3a_uebersicht_wetter_block.md`, `feat_1969_naechstes_briefing.md`, `feat_1481b_pendant_gate.md`

## Risks & Considerations
1. **Überschneidung mit der i18n-Arbeit (hoch).** Die Specs F9 (#2658, `i18n_f9_trip_flaechen_2658.md`) und F10 (#2659, `i18n_f10_vergleich_flaechen_2659.md`) sind freigegeben, aber laut Sitzungsregister ist noch keine davon in Arbeit.
   - F9 ändert HubOverview.
   - F10 setzt Zeilennummern in CompareTabs voraus (`:723/758/768/773/841`), legt fest „keine neue Komponente“ und nutzt SSR-Golden-Fixtures.
   - Wer zuerst landet, macht die Zeilenangaben der anderen ungültig. Nach dem Merge von #2682 muss ein Hinweis an F9/F10 gehen, z. B. als Kommentar in #2658/#2659: neuer Ort ist der geteilte Baustein.
2. **Was der Trip neu bekommt.** Folgende Elemente zeigt der Trip nach dem Umbau zum ersten Mal: Status, Nächster Versand, Zuletzt raus, Kanäle, Zusammenfassungs-Karten, mobile Pfeil-Zeilen.
   - Für jede gilt Invariante 1: Ein neues Element muss einen echten Wert anzeigen und darf keine Attrappe sein. Datenquellen der Trip-Seite: `trip.letzter_versand`? Status? Gibt es Entsprechungen? Das klärt die Analyse.
3. **Bestehende Attrappen beim Trip.** Kanäle sind fest `['email','telegram']` eingetragen, „Alerts (letzte 7 Tage)“ ist fester Text. Beides verstößt heute schon gegen Invariante 1 und wird mit dem Umbau behoben oder ehrlich entfernt.
4. **Was compare-eigen bleiben darf.** Etappen gegenüber Orten ist fachlich begründet. Die Wetter-Metriken-Karte (Trip) und die Wertebereiche-Karte (Vergleich) müssen vereinheitlicht oder begründet werden.
5. **Doppelter Kennzahlen-Baustein.** `Stat` liegt als Atom und als Molekül vor. Es wird nur einer genutzt; das andere Pendant wird nicht neu verbreitet.
6. **Tests, die den Quelltext an festen Pfaden lesen.** Ihre Zusicherungen müssen auf den neuen Baustein umziehen. Testdateien dürfen dabei nicht still gelockert werden.
7. **Kleine Unstimmigkeit im Vergleich.** Die Kopfzeile nutzt `preset.location_ids.length`, die Karte `resolvedLocations`. Das wird beim Umbau vereinheitlicht.
8. Der Umbau betrifft nur das Frontend: keine Änderung am Datenmodell, kein Go- und kein Python-Code (sofern die Trip-Seite keine fehlenden Felder braucht, siehe Risiko 2).

## Analysis

### Type
Feature (Refactoring mit sichtbarer Angleichung der Trip-Übersicht; Unter-Issue Epic #2345)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/hub-uebersicht/HubUebersicht.svelte` | CREATE | Geteilter Baustein `context="route"\|"vergleich"`: Kennzahlen-Raster (mobil 2×2 / Desktop-Leiste), Zusammenfassungs-Karten bzw. mobile Pfeilzeilen (`summaryChevron`), Versand-Karte, `BriefingHistory kind={context}`; CSS `.hub-mobile-*`/`.hub-summary-*` zieht aus CompareTabs `:1164-1263` um; `isMobileViewport` (≤899px) wandert mit |
| `frontend/src/lib/components/shared/hub-uebersicht/hubUebersichtModell.ts` | CREATE | Reine Ableiter `deriveRouteKennzahlen(trip, …)` / `deriveVergleichKennzahlen(preset, …)` → EIN Modell `{kennzahlen[], karten[]}` mit Kurz-/Langform je Text, Sprungziel, testid-Präfix |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | Übersichts-Markup `:711-882` + CSS entfernen, durch `<HubUebersicht context="vergleich">` ersetzen; Wrapper-testid `compare-detail-panel-uebersicht` bleibt; `hubActivationCard` bleibt (Wetter-Metriken-Tab) |
| `frontend/src/lib/components/trip-detail/HubOverview.svelte` | MODIFY | Wird dünner Trip-Adapter (oder entfällt zugunsten direkter Einbindung): Etappen-Fläche (FullProfile, TripStageRow, `fetchStageRisk`) + Wetter-Metriken-Karte als context-eigener Inhalt; Kanäle aus `report_config.send_*` statt fest `['email','telegram']`; Alerts-Festtext entfernt |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | MODIFY | Einbindung `:191` anpassen |
| `frontend/src/lib/components/shared/BriefingHistory*` / `briefingHistory.ts` | MODIFY | Neuester Eintrag muss für „Zuletzt raus“ (Trip) an die Kennzahl gereicht werden (ein Laden, zwei Nutzer) |
| ~15–40 Unit-Tests (Liste unten) | MODIFY | Zusicherungen, die CompareTabs/HubOverview per Quelltextpfad lesen, ziehen auf den neuen Baustein/das Modell um — nicht lockern; Zuordnung Test → neue Datei kommt in die Spec |
| `frontend/e2e/compare-hub-fidelity-s8c.spec.ts` | MODIFY | `gz-eigenstaendig`-Kopf (Begründung #2682) entfällt → `HUB_KINDS`-Schleife für beide Arten |
| `frontend/e2e/hub-tab-bar.spec.ts` (HT-10), `hub-versand-briefing-zeiten.spec.ts` | MODIFY | Übersichts-Fälle für beide Arten |
| `docs/specs/modules/feat_2347_s4_paritaets_e2e.md` (Z.61 Befund 6, Z.193, AC-20, AC-22) | MODIFY | Abweichung „Hub-Übersicht doppelt“ als erledigt führen |
| `docs/reference/gates_und_ratschen.md:280-290` | MODIFY | Absatz „Dokumentierte Vergleichs-Eigenheit … #1199“ streichen |
| `docs/specs/modules/feat_1256_s8c_hub_fidelity.md` + zugehöriger Source-Wächter | MODIFY | Wächter hält HubOverview/TripTabs unverändert → bricht geplant, wird auf neuen Ort umgestellt |

### Befunde der Analyse
1. **Grundstruktur verschieden (wichtigster Befund).** Trip = 2 Spalten (links Etappen-Profil + Etappenliste + Wetter-Metriken, rechts Karten „Briefings laufen“, Alerts, Verlauf); die Design-Vorlage `claude-code-handoff/current/jsx/screen-trip-detail.jsx:73-120` zeigt genau dieses Layout. Vergleich = Kennzahlen-Leiste + 2×2-Zusammenfassungs-Karten (`screen-compare-detail.jsx`). „Zusammenführen“ bedeutet für den Trip neue sichtbare Elemente (Kennzahlen-Leiste, Zusammenfassungs-Karten). Das ist eine Layout-Entscheidung → muss als sichtbares AC in die Spec (PO entscheidet bei der Spec-Freigabe), nicht still. Empfohlener Schnitt: geteilt = Kennzahlen-Leiste + Versand-/Verlaufs-Karten + Zusammenfassungs-Karten-Mechanik; context-eigen = Hauptfläche (route: Etappen + Profil + Wetter-Metriken-Karte; vergleich: Orte-/Wertebereiche-Karten).
2. **Trip-Datenquellen** (Invariante 1 — kein neues Element ohne echten Wert):

   | Kennzahl | Trip-Quelle | Stand |
   |---|---|---|
   | Status | `deriveTripStatus(trip, now)` (`utils/tripStatus.ts`), anderes Modell als `deriveStatusWithScheduleOverride` (Compare) | echt; **Trip-Kopf zeigt Status bereits** (`TripHeader.svelte:134` `TripStatusBadge`) → Doppelung klären, Vergleich spiegeln |
   | Nächster Versand | `erstelleNaechstesBriefingLader({context:'route'})` | schon in HubOverview |
   | Briefing-Zeiten | `trip.report_config.morning/evening_time` + `reportSlotAktiv` | echt |
   | Zuletzt raus | kein Trip-Feld (`letzter_versand` nur ComparePreset, geschrieben in `src/services/scheduler_dispatch_service.py:493-519`); Trip-Quelle = neuester Eintrag Briefing-Log (`GET /api/briefings/{id}/briefing-history?kind=route`, `internal/handler/briefing_history.go`, geschrieben von `trip_report_scheduler.py:1990/2379`) | frontend-only machbar |
   | Kanäle | heute **Attrappe** fest `['email','telegram']`; echt aus `report_config.send_email/send_telegram/send_sms/send_premium_sms` | wird behoben |
   | Alerts (letzte 7 Tage) | heute **Attrappe** „Keine aktuellen Alerts.“; kein Trip-HTTP-Endpunkt für Alert-Historie (`store/log.go` `LoadAlertLog` nur Go-intern; Cockpit nur 24 h) | ehrlich entfernen (Vergleich hat keine solche Karte); eigener Endpunkt wäre eigenes Ticket |
3. **`hubActivationCard` ist nicht tot** (oben in „Related Files“ korrigiert).
4. **Kurz-/Langtexte:** mobil/desktop unterscheiden sich („Läuft autom.“/„Läuft automatisch“, „Nicht geplant“/„Noch nicht geplant“) → Modell trägt beide Formen.
5. **testids stabil halten:** `hub-summary-row-mobile` (3× vergeben, E2E zählt), `compare-hub-versand-edit`, `compare-detail-stat-briefings`, `compare-detail-stat-kanaele(-mobile)`, `compare-detail-panel-uebersicht`, `compare-detail-monitoring-mobile`, `compare-detail-summary-mobile`, `hub-overview`, `hub-metrics-*`. Lösung: testid-Präfix aus dem Modell, Vergleich behält `compare-*`.
6. **Kopfzeile vs. Karte im Vergleich** (`preset.location_ids.length` vs. `resolvedLocations`) → beim Umzug auf `resolvedLocations` vereinheitlichen (kleine Verhaltensänderung bei nicht auflösbaren Orten, in Spec festhalten).
7. **Sprung-Handler:** Trip `onJump(tab, anchor)`, Vergleich `handleValueChange(tab, anchor)`, gleiche Signatur → einheitliches `onJump`.
8. **Stat-Dublette** (`atoms/Stat` vs. `molecules/Stat`): CompareTabs nutzt keines; der Baustein verbreitet keins der beiden → Dublette bleibt Aufräum-Thema (Nebenbefund #1199).
9. **Pendant-Sperre:** neutral benannter Baustein unter `shared/` löst nicht aus; ein evtl. ausgelagertes `trip-detail/HubEtappen.svelte` braucht Kopf `gz-eigenstaendig` (Etappen trip-spezifisch, ADR-0097 Nr. 3).

### Scope Assessment
- Files: ~6 Produktdateien (2 neu) + ~15–40 Testdateien (Umzug der Zusicherungen) + 4 Doku-/Spec-Dateien
- Estimated LoC (Produktcode): ca. +500/-300 brutto, netto ca. +250 → am LoC-Limit 250/Workflow (`docs/reference/workflow_und_agenten.md:49`); vorgesehener Weg ist `loc_limit_override 500`, **kein** Abspalten in neue Tickets (Epic themenweise abschließen)
- Risk Level: MEDIUM — reiner Frontend-Umbau ohne Datenmodell/Go/Python, aber der Vergleichs-Hub ist breit durch Tests/E2E abgedeckt und der Trip-Hub ändert sich sichtbar

### Technical Approach
Ein Workflow, eine Spec, zwei Lieferschritte als getrennte Commits:
- **Schritt 1 (Umzug Vergleich, verhaltensgleich):** zuerst Charakterisierungstest (SSR-HTML der Vergleichs-Übersicht mobil + desktop) gegen den Ist-Stand; dann `HubUebersicht.svelte` + `hubUebersichtModell.ts` mit `context="vergleich"` aus CompareTabs herauslösen; Testpfade umhängen; Charakterisierung bleibt grün.
- **Schritt 2 (Trip anhängen):** `context="route"` mit Etappen-Fläche + Wetter-Metriken-Karte als context-eigenem Inhalt; Kanäle aus `report_config.send_*`; „Zuletzt raus“ aus neuestem Briefing-Log-Eintrag (Ladezustand „—“, leer „Noch nie“); Alerts-Attrappe entfernt; Status-Doppelung zum Kopf nach Vergleichs-Vorbild aufgelöst; Wächter-/Spec-Anpassungen (S4, gates_und_ratschen, s8c, `gz-eigenstaendig`-Kopf).
- Frontend-only: kein Backend-Feld, kein neuer Endpunkt.

### Dependencies
- Upstream: atoms `Card`/`Btn`/`Eyebrow`/`SectionH`/`Dot`, `BriefingHistory` + `briefingHistory.ts`, `erstelleNaechstesBriefingLader`, `compare/subscriptionHelpers.ts`, `utils/tripStatus.ts`, `shared/trip-metrics` (`resolveTripMetricsOverviewState`), `utils/stageRisk.ts`.
- Downstream: `TripTabs.svelte`, `CompareTabs.svelte`/`CompareDetail.svelte`.
- **i18n F9 (#2658) / F10 (#2659):** beide Specs `approved`, noch ohne Code (Stand 2026-11-01, keine laufende Sitzung darauf). Beide sagen „keine neue Komponente“ und nennen Zeilennummern in HubOverview/CompareTabs + SSR-Goldens `tests/golden/f9_*`/`f10_*`. #2682 landet zuerst → **Folgepflicht nach Merge:** Kommentar in #2658 und #2659 mit neuem Ort (`shared/hub-uebersicht/`); die Prämisse „keine neue Komponente“ und die Zeilenangaben sichtbar nachziehen. Vorteil: Übersichts-Texte nur noch einmal zu übersetzen.

### Tests, die geplant brechen bzw. umziehen (keine Regression)
- Quelltext-Pfad-Tests: `compare_hub_fidelity.test.ts`, `compare_mobile_shared_hub.test.ts`, `hubOverviewMetricsBlock_structure.test.ts`, `briefings_karte_echte_zeiten_render.test.ts`, `naechstes_briefing_verdrahtung.test.ts`, `reiter_sprunglinks_nur_neue_kennungen.test.ts:195-199,265` (enthält HubOverview-Sprungziel `wertebereiche`, das heute der Knopf „Alle Alerts →“ nutzt — beim Entfernen der Alerts-Karte bewusst anpassen und in der Spec benennen), `versand_sprung_auf_wetter_metriken.test.ts:41,185,293-299`, `briefing_history_hubs.test.ts:56,75-79`, `issue_582_compare_design_fidelity.test.ts` sowie weitere compare-Tests, die CompareTabs per Pfad lesen (Einzelzuordnung in Phase 4).
- s8c-Source-Wächter (`feat_1256_s8c`), `tests/unit/test_e2e_compare_paritaet_waechter.py` (`gz-eigenstaendig`-Kopf entfällt).

### Open Questions (für die Spec; PO entscheidet bei der Spec-Freigabe)
- [ ] Layout-Soll Trip-Übersicht: Kennzahlen-Leiste oben + bisherige 2-Spalten-Hauptfläche (Empfehlung) — als sichtbares AC formulieren.
- [ ] Status-Kennzahl im Trip trotz Status-Badge im Kopf? Prüfen, ob der Vergleichs-Kopf ebenfalls Status zeigt, und identisch handhaben.
- [ ] „Zuletzt raus“ gleiche Bedeutung? Compare: Zeitstempel des Scheduler-Dispatch; Trip: neuester Briefing-Log-Eintrag. Prüfen, ob der Log auch Test-Versand/Fehlversuche enthält → ggf. filtern.
- [ ] Alert-Kanalzeile in „Briefings laufen“: aus `AlertChannels` des Trips (echt) oder weglassen.
