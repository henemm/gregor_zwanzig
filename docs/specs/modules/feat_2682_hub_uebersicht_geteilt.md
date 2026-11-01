---
entity_id: feat_2682_hub_uebersicht_geteilt
type: feature
created: 2026-11-01
updated: 2026-11-01
status: draft
version: "1.0"
workflow: feat-2682-hub-uebersicht-geteilt
tags: [epic-2345, trip-compare-teilung, hub-uebersicht, shared, refactoring, paritaet, frontend-only]
---

# Hub-Übersicht für Trip und Ortsvergleich geteilt (Issue #2682, Epic #2345)

## Approval

- [ ] Approved

## Purpose

Die Übersicht im Detail-Hub ist zweimal gebaut: der Ortsvergleich hat sie inline in `CompareTabs.svelte`, der Trip in `trip-detail/HubOverview.svelte`. Dabei zeigt der Vergleich Kennzahlen-Leiste, Zusammenfassungs-Karten, mobile Pfeil-Zeilen, Status-Kurzform und Versand-Karte, der Trip nichts davon. Das widerspricht der PO-Vorgabe (CLAUDE.md „Trip/Ortsvergleich-Code-Teilung", ADR-0097): compare-eigen dürfen nur der Orte-Reiter, die transponierte Übersicht und das Compare-Mail-Template sein.

Diese Spec legt **einen** geteilten Baustein `shared/hub-uebersicht/HubUebersicht.svelte` mit `context="route"|"vergleich"` an. Er trägt Kennzahlen-Leiste, Versand-Karte (Desktop-Karte bzw. mobile Pfeil-Zeile) und Versand-Historie für beide Arten. Die fachlich verschiedene Hauptfläche (Trip: Etappen und Wetter-Metriken; Vergleich: Orte und Wertebereiche) bleibt context-eigener Inhalt. Beim Trip verschwinden dabei zwei bestehende Attrappen (fest eingetragene Kanäle, Festtext „Keine aktuellen Alerts.").

Ein Workflow, eine Spec, zwei Lieferschritte als getrennte Commits (kein Abspalten in neue Tickets, Epic wird themenweise abgeschlossen):

1. **Schritt 1, Umzug des Vergleichs, verhaltensgleich:** zuerst Charakterisierungstest gegen den Ist-Stand (SSR-HTML mobil und Desktop), dann Herauslösen nach `shared/hub-uebersicht/`. Charakterisierung bleibt grün.
2. **Schritt 2, Trip anhängen:** `context="route"` mit echten Werten, Wächter-, Test- und Doku-Folgen.

## Source

- **Neu (Pfade relativ zu `frontend/src/lib/components/`):**
  `shared/hub-uebersicht/HubUebersicht.svelte`, `shared/hub-uebersicht/hubUebersichtModell.ts`, `shared/briefingHistoryLader.svelte.ts`.
- **Geändert:** `compare/CompareTabs.svelte` (Übersichts-Markup `:711-882` und CSS `.hub-mobile-*`/`.hub-summary-*` `:1164-1263` entfallen, ersetzt durch `<HubUebersicht context="vergleich">`), `trip-detail/HubOverview.svelte` (wird dünner Trip-Adapter für die Hauptfläche), `trip-detail/TripTabs.svelte` (Einbindung `:191`), `trip-detail/ChannelDot.svelte` (vierter Kanal Premium-SMS), `shared/BriefingHistory.svelte` (optionaler Lader, ohne Prop unverändert).
- **Tests/E2E/Wächter/Doku:** siehe Scope.
- **Identifier:** `HubUebersicht`, `hubUebersichtModell`, `deriveRouteKennzahlen`, `deriveVergleichKennzahlen`, `erstelleBriefingHistoryLader`, testids siehe „Stabile testids".

> **Schicht-Hinweis:** ausschließlich **Frontend** (SvelteKit). Kein Go-, kein Python-Code, kein Datenmodell, kein neuer Endpunkt. Der Trip nutzt den bestehenden Endpunkt `GET /api/briefings/{id}/briefing-history?kind=route` (`internal/handler/briefing_history.go`), der nur den Log des eingeloggten Nutzers (`middleware.UserIDFromContext`) liest.

> **Trip/Ortsvergleich-Teilung:** Kern dieser Spec. Der Baustein liegt unter `shared/` und löst die Pendant-Sperre nicht aus (`BEKANNTE_PAARE` kennt weder HubOverview noch CompareTabs). Ein evtl. ausgelagerter Etappen-Teil `trip-detail/HubEtappen.svelte` bekommt den Kopf `gz-eigenstaendig:` (Etappen sind trip-spezifisch, ADR-0097 Nr. 3).
> **Mandantentrennung:** Das Laden der Versand-Historie für „Zuletzt raus" ist datenbewegend und wird mit zwei Nutzern geprüft (AC-14).
> **Kanäle:** Die Kanal-Kennzahl und die Alert-Kanalzeile nennen alle vier Kanäle gleichrangig: E-Mail, Telegram, SMS, Premium-SMS (ADR-0095). Es wird nichts versendet.

## Entscheidungen (Tech Lead, am Code gemessen; der PO sieht sie als ACs)

1. **Layout-Soll Trip-Übersicht.** Oben die geteilte Kennzahlen-Leiste (Desktop eine Leiste, mobil Raster 2×2), darunter die bisherige context-eigene Hauptfläche (Trip: Etappen-Profil, Etappenliste, Wetter-Metriken-Karte, Karte „Briefings laufen"; Vergleich: Orte- und Wertebereiche-Karten), darunter die geteilte Versand-Karte und die Versand-Historie. Begründung: die Hauptfläche ist fachlich verschieden und wird nicht verformt; angeglichen wird, was beide Arten gleichermaßen betrifft. Sichtbare Änderung für Trips: neue Kennzahlen-Leiste und Versand-Karte (AC-1, AC-2, AC-8).
2. **Status-Kennzahl im Trip trotz Status-Badge im Kopf.** Beide Köpfe zeigen den Status bereits: Trip `trip-detail/TripHeader.svelte:134` (`TripStatusBadge`), Vergleich `routes/compare/[id]/+page.svelte:369` (`CompareStatusPill`). Der Vergleich zeigt ihn trotzdem zusätzlich als Kennzahl in der Übersicht. Parität heißt: der Trip bekommt die Kennzahl ebenfalls. Quelle ist `deriveTripStatus(trip, now)` (`utils/tripStatus.ts`), Beschriftung wortgleich zum Status-Badge (Entwurf, Geplant, Pausiert, Archiviert usw.), damit es kein zweites Vokabular gibt; Kurz- und Langform sind beim Trip gleich. Der Vergleich behält seine Texte („Läuft autom." mobil, „Läuft automatisch" Desktop).
3. **„Zuletzt raus" beim Trip.** Der Trip hat kein Feld `letzter_versand`. Quelle ist der neueste Eintrag des Briefing-Logs (`GET /api/briefings/{id}/briefing-history?kind=route`, geschrieben von `src/services/trip_report_scheduler.py:1990` über `_append_briefing_log` `:2379`). Gemessen: der Log enthält Einträge mit `on_demand=true` (Test-Versand-Knopf, SMS „heute/morgen", Inbound-Kommando „report"), aber **keine** Fehlversuche und keine Versuche ohne Kanal (`:1967-1974` schreiben keinen Eintrag). Beim Vergleich bedeutet `letzter_versand` dagegen „planmäßiger Scheduler-Lauf" (`save_compare_preset_status` wird nur im Dispatch-Pfad `scheduler_dispatch_service.py:1046` gerufen). Gleiche Bedeutung heißt deshalb: **neuester Eintrag mit `on_demand !== true`**. Anzeige im selben Format wie beim Vergleich (`formatLastSent`, Datum TT.MM.JJJJ). Ein Laden: der neue `erstelleBriefingHistoryLader` holt die Liste einmal; Kennzahl und Versand-Historie nutzen dieselbe Antwort (der Lader gehört dem Baustein, `BriefingHistory` bekommt ihn optional als Prop).
4. **Alert-Kanalzeile und Alerts-Karte.** Die Zeile „Alert-Trigger" in „Briefings laufen" zeigt die echten Alert-Kanäle des Trips: `trip.alert_channels` (E-Mail, Telegram, SMS, Premium-SMS), und solange dieses Feld fehlt (Altbestand, vererbt laut `types.ts:399-407`) die Briefing-Flags `report_config.send_email/send_telegram/send_sms/send_premium_sms`. Die Morgen- und Abend-Zeilen zeigen ebenfalls die echten Briefing-Kanäle statt fest `['email','telegram']` bzw. `['email']`. `ChannelDot` lernt den vierten Kanal. Die Karte „Alerts (letzte 7 Tage)" mit Festtext „Keine aktuellen Alerts." und dem Knopf „Alle Alerts →" entfällt ersatzlos: es gibt keinen Trip-Endpunkt für die Alert-Historie (`store/log.go` `LoadAlertLog` ist nur Go-intern), der Vergleich hat keine solche Karte, und ein Festtext ohne Datenquelle ist eine Attrappe. Folge: das Sprungziel `wertebereiche` aus HubOverview (`reiter_sprunglinks_nur_neue_kennungen.test.ts:195-199,265`) entfällt dort bewusst; die Zusicherung „keine Alt-Kennung als Sprungziel" bleibt für alle übrigen Sprungziele unverändert.
5. **Orte-Zahl im Vergleich.** Die Kopfzeile der Karte nutzte `preset.location_ids.length`, die Namenszeile `resolvedLocations`. Einheitlich gilt `resolvedLocations.length`. Einzige bewusste Verhaltensänderung in Schritt 1: bei nicht auflösbaren Orten (gelöschter Ort) zeigt die Karte jetzt die Zahl der auflösbaren Orte statt der gespeicherten Kennungen.
6. **Lade- und Leerzustände (am Vergleich ausgerichtet).** Beim Laden zeigt jede abhängige Kennzahl „—". Ohne Eintrag zeigt „Zuletzt raus" den Text „Noch kein Versand" (Wortlaut `formatLastSent`). Bei Ladefehler zeigt die Kennzahl „—", die Versand-Historie ihre bestehende Fehlermeldung. Keine Kennzahl zeigt einen erfundenen Wert.
7. **Kennzahlen-Umfang.** Desktop (5): Status, Nächster Versand, Briefings (Zeiten), Zuletzt raus, Kanäle. Mobil (4): Status, Nächster Versand, Zuletzt raus, Kanäle. Beim Trip: Briefings-Zeiten aus `report_config.morning_time/evening_time` mit `reportSlotAktiv`, „Nächster Versand" aus `erstelleNaechstesBriefingLader({context:'route'})` und `formatNextBriefing(wert,'route')`, Kanäle aus den Briefing-Flags (E-Mail gilt als aktiv, solange `send_email !== false`, Muster `report_slot_aktiv.test.ts:185`).
8. **Stat-Dublette** (`atoms/Stat` vs. `molecules/Stat`): der Baustein nutzt keine der beiden und verbreitet sie nicht; Aufräumen bleibt Nebenbefund #1199.
9. **`hubActivationCard`** (`CompareTabs.svelte:1033-1051`) ist kein toter Code (Übergabe an `WetterMetrikenVersandPanel` in `:974`) und bleibt unberührt.

## Stabile testids

Alle bestehenden testids bleiben: `compare-detail-panel-uebersicht` (Wrapper bleibt in CompareTabs), `compare-detail-monitoring-mobile`, `compare-detail-summary-mobile`, `hub-summary-row-mobile`, `compare-hub-versand-edit`, `compare-detail-stat-briefings`, `compare-detail-stat-kanaele`, `compare-detail-stat-kanaele-mobile`, `hub-overview`, `hub-metrics-*`, `briefing-history*`. Der Vergleich behält das Präfix `compare-*`, das Präfix kommt aus dem Modell. Der Trip bekommt dieselben Kennzahlen mit Präfix `hub-uebersicht-*` (z. B. `hub-uebersicht-stat-kanaele`, `hub-uebersicht-stat-zuletzt-raus`, `hub-uebersicht-versand-edit`).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `shared/versand-tab/naechstesBriefingLader.svelte.ts`, `nextBriefingText.ts` | module | „Nächster Versand" je context (bereits geteilt) |
| `shared/BriefingHistory.svelte`, `briefingHistory.ts` | component | Versand-Historie `kind={context}`; Endpunkt `GET /api/briefings/{id}/briefing-history` |
| `compare/subscriptionHelpers.ts` | module | `deriveStatusWithScheduleOverride`, `presetBriefingTimesLabel`, `formatLastSent`, `channelNamesLabel`, `presetProfileLabel` (Vergleich) |
| `utils/tripStatus.ts` | module | `deriveTripStatus` (Trip) |
| `utils/reportSlotAktiv.ts` | module | aktive Slots des Trips |
| `shared/trip-metrics/tripActiveMetricNames` | module | Wetter-Metriken-Karte (Trip-Hauptfläche, unverändert) |
| `utils/stageRisk.ts` (`fetchStageRisk`) | module | Risiko-Ampel je Etappe (Trip-Hauptfläche, unverändert) |
| atoms `Card`, `Btn`, `Eyebrow`, `SectionH`, `Dot` | component | Darstellung |
| `shared/subscription-header/SubscriptionHeader.svelte` | component | Vorbild für Bausteine mit `context` (#2284) |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/hub-uebersicht/HubUebersicht.svelte` | CREATE | Geteilter Baustein: Kennzahlen-Raster (mobil 2×2 / Desktop-Leiste), Versand-Karte bzw. mobile Pfeil-Zeile (`summaryChevron`), Slot für context-eigene Hauptfläche, `BriefingHistory`; CSS `.hub-mobile-*`/`.hub-summary-*` zieht hierher; `isMobileViewport` (≤899px) wandert mit |
| `frontend/src/lib/components/shared/hub-uebersicht/hubUebersichtModell.ts` | CREATE | Reine Ableiter `deriveRouteKennzahlen` und `deriveVergleichKennzahlen` liefern EIN Modell `{kennzahlen[], versandKarte, testidPraefix}` mit Kurz-/Langform je Text und Sprungziel |
| `frontend/src/lib/components/shared/briefingHistoryLader.svelte.ts` | CREATE | `erstelleBriefingHistoryLader`: ein Laden mit Stale-Guard, liefert Liste und „neuester planmäßiger Eintrag" |
| `frontend/src/lib/components/shared/BriefingHistory.svelte` | MODIFY | Optionale Prop `lader`; ohne sie lädt der Baustein wie bisher selbst |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | Übersicht `:711-882` und CSS `:1164-1263` entfernt, ersetzt durch `<HubUebersicht context="vergleich">`; `hubActivationCard` bleibt |
| `frontend/src/lib/components/trip-detail/HubOverview.svelte` | MODIFY | Dünner Trip-Adapter: Etappen-Fläche, Wetter-Metriken-Karte, „Briefings laufen" mit echten Kanälen; Alerts-Karte entfernt |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | MODIFY | Einbindung `:191` auf `<HubUebersicht context="route">` mit Trip-Hauptfläche |
| `frontend/src/lib/components/trip-detail/ChannelDot.svelte` | MODIFY | Vierter Kanal Premium-SMS |
| Unit-Tests (Zuordnung unten) | MODIFY/CREATE | Charakterisierungstest, Modelltests, Umzug der Quelltext-Zusicherungen auf den neuen Baustein |
| `frontend/e2e/compare-hub-fidelity-s8c.spec.ts` | MODIFY | `gz-eigenstaendig`-Kopf (Begründung #2682) entfällt, Übersichts-Fälle laufen per `HUB_KINDS` für beide Arten |
| `frontend/e2e/hub-tab-bar.spec.ts` | MODIFY | HT-10 für beide Arten; Sprungknöpfe `:248-258` je Art ohne „Alle Alerts →" |
| `frontend/e2e/hub-versand-briefing-zeiten.spec.ts` | MODIFY | Übersichts-Fälle für beide Arten |
| `tests/unit/test_e2e_compare_paritaet_waechter.py` | MODIFY | `compare-hub-fidelity-s8c` trägt keinen Kopf mehr, `HUB_KINDS`-Schleife wird geprüft |
| `docs/specs/modules/feat_1256_s8c_hub_fidelity.md` und zugehöriger Source-Wächter | MODIFY | Wächter hält HubOverview/TripTabs eingefroren, wird auf den neuen Ort umgestellt |
| `docs/specs/modules/feat_2347_s4_paritaets_e2e.md` | MODIFY | Befund 6 (`:61`), `:193`, AC-20, AC-22: Abweichung „Hub-Übersicht doppelt" als erledigt führen |
| `docs/reference/gates_und_ratschen.md` | MODIFY | Absatz „Dokumentierte Vergleichs-Eigenheit außerhalb des CLAUDE.md-Katalogs" (`:285-288`) streichen |

## Estimated Scope

- Files: 8 Produktdateien (3 neu), ca. 15 bis 40 Testdateien (Umzug der Zusicherungen), 3 Doku-/Spec-Dateien, 2 Wächter-Dateien.
- Effort: high
- LoC: Produktcode ca. +500/-300 brutto, netto ca. +250. Das liegt am Limit von 250 pro Workflow (`docs/reference/workflow_und_agenten.md:49`). Vorgesehen ist `loc_limit_override 500`, **kein** Abspalten in neue Tickets (Epic wird themenweise abgeschlossen).
- Risiko: MEDIUM. Frontend-Umbau ohne Datenmodell, aber der Vergleichs-Hub ist breit durch Tests und E2E abgedeckt und der Trip-Hub ändert sich sichtbar.

## Implementation Details

Schritt 1: Charakterisierungstest zuerst (SSR-HTML der Vergleichs-Übersicht mobil und Desktop, festgehalten gegen den Ist-Stand, vor jeder Produktänderung). Danach `deriveVergleichKennzahlen` und `HubUebersicht` aus CompareTabs herauslösen; ausgenommen ist nur Entscheidung 5. Testpfade umhängen, Charakterisierung bleibt grün.

Schritt 2: `deriveRouteKennzahlen(trip, status, briefing, letzterVersand)` baut dasselbe Modell aus Trip-Daten. Der Lader holt die Historie einmal, filtert für „Zuletzt raus" auf `on_demand !== true`, nimmt den neuesten Eintrag (der Log ist chronologisch, siehe `BriefingHistory.svelte:54`) und gibt dieselbe Liste an `BriefingHistory`. Sprung-Handler vereinheitlicht: `onJump(tab, anchor?)`, gleiche Signatur wie `handleValueChange`. In `HubOverview` bleibt „kein `anchor?:`"-Konvention der SSR-Prüfstände erhalten. Keine Code-Blöcke über 30 Zeilen in dieser Spec; Details stehen im Code.

### Zuordnung der Tests (nichts wird gelockert)

Zusicherungen, die heute CompareTabs/HubOverview per Quelltextpfad lesen, ziehen auf den neuen Ort um. Die Zusicherung bleibt gleich streng, nur der Pfad folgt.

| Test | Heute liest | Neuer Ort |
|---|---|---|
| `compare/__tests__/compare_hub_fidelity.test.ts` (13 Fälle) | `CompareTabs.svelte` | `shared/hub-uebersicht/HubUebersicht.svelte` und `hubUebersichtModell.ts` (Übersichtsfälle); CompareTabs-Fälle außerhalb der Übersicht bleiben |
| `compare/__tests__/compare_mobile_shared_hub.test.ts` (6) | `CompareTabs.svelte` | `HubUebersicht.svelte` (mobiler Teil) |
| `trip-detail/__tests__/hubOverviewMetricsBlock_structure.test.ts` (12) | `HubOverview.svelte` | bleibt in `HubOverview.svelte` (Wetter-Metriken-Karte bleibt dort), Wrapper-Pfad auf Einbindung in `HubUebersicht` angepasst |
| `trip-detail/__tests__/briefings_karte_echte_zeiten_render.test.ts` | `HubOverview.svelte` | `HubOverview.svelte` (Karte „Briefings laufen"), Kanal-Zusicherung neu: echte statt feste Kanäle |
| `shared/__tests__/reiter_sprunglinks_nur_neue_kennungen.test.ts:195-199,265` | HubOverview-Sprungziele | `HubOverview.svelte` plus `HubUebersicht.svelte`; Sprungziel `wertebereiche` (Knopf „Alle Alerts →") entfällt bewusst (Entscheidung 4) |
| `shared/__tests__/versand_sprung_auf_wetter_metriken.test.ts:41,185,293-299` | CompareTabs/HubOverview | `HubUebersicht.svelte` (Versand-Sprung `wetter-metriken` mit Anker `versand`) |
| `shared/briefing_history_hubs.test.ts:56,75-79` | CompareTabs/HubOverview | `HubUebersicht.svelte` (`BriefingHistory kind={context}`) |
| `shared/versand-tab/__tests__/naechstes_briefing_verdrahtung.test.ts` | CompareTabs/HubOverview | `HubUebersicht.svelte`/Modell (Lader-Verdrahtung je context) |
| `compare/__tests__/issue_582_compare_design_fidelity.test.ts` und weitere compare-Tests, die CompareTabs per Pfad lesen | `CompareTabs.svelte` | Einzelzuordnung in Phase 4 (RED); jede Umhängung wird im Commit benannt |
| NEU `hub_uebersicht_charakterisierung.test.ts` (Schritt 1) | SSR-Render | Vergleichs-Übersicht mobil und Desktop |
| NEU `hub_uebersicht_modell.test.ts` | Modell | Kennzahlen route und vergleich, Kurz-/Langform, Filter `on_demand`, Kanäle |

## Test Plan

### Automated Tests (TDD RED)

- [ ] Charakterisierung Vergleichs-Übersicht (SSR, mobil + Desktop) gegen Ist-Stand, grün vor und nach dem Umzug (Schritt 1).
- [ ] Modell `deriveRouteKennzahlen`: GIVEN Trip mit `send_premium_sms=true` WHEN Kennzahlen abgeleitet THEN enthält die Kanal-Kennzahl „Premium-SMS" neben E-Mail.
- [ ] Modell Filter: GIVEN Log mit Eintrag von Hand (neuer) und planmäßigem Eintrag (älter) WHEN „Zuletzt raus" abgeleitet THEN zeigt es das Datum des planmäßigen Eintrags.
- [ ] Modell Zustände: GIVEN Log noch nicht geladen / leer / Ladefehler WHEN abgeleitet THEN „—" / „Noch kein Versand" / „—".
- [ ] Zwei-Nutzer-Test: Nutzer A mit Versand-Eintrag, Nutzer B ohne; B öffnet seinen Trip (E2E auf Staging, beide Konten).
- [ ] E2E `HUB_KINDS`: Kennzahlen-Leiste, Versand-Karte, Versand-Historie, Sprungknöpfe für beide Arten (`compare-hub-fidelity-s8c`, `hub-tab-bar` HT-10).
- [ ] Wächter: `test_e2e_compare_paritaet_waechter.py` grün ohne Kopf in s8c; Mutation: Kopf wieder eintragen ⇒ Wächter darf ihn nicht länger brauchen, Löschen der `HUB_KINDS`-Schleife ⇒ rot.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit Etappen / When der Nutzer die Übersicht des Trips öffnet / Then steht oben eine Kennzahlen-Leiste mit Status, Nächster Versand, Briefings, Zuletzt raus und Kanäle, darunter die Etappen-Fläche mit Profil, Etappenliste und Wetter-Metriken-Karte.
  - Test: E2E auf Staging, Trip anlegen, Übersicht öffnen, die fünf Kennzahlen und die Etappenliste sind sichtbar.
- **AC-2:** Given ein Trip auf dem Handy (Breite ≤899 px) / When der Nutzer die Übersicht öffnet / Then zeigt die Leiste vier Kennzahlen im 2×2-Raster (Status, Nächster Versand, Zuletzt raus, Kanäle) und die Versand-Karte erscheint als Pfeil-Zeile.
  - Test: E2E mit Mobil-Viewport für den Trip, vier Kennzahlen und eine Zeile `hub-summary-row-mobile` für Versand.
- **AC-3:** Given ein Ortsvergleich / When der Nutzer die Übersicht auf Desktop oder Handy öffnet / Then sieht er dieselben Kennzahlen, Zusammenfassungs-Karten bzw. Pfeil-Zeilen, Texte und Sprungziele wie vor dem Umbau (Status-Kurzform „Läuft autom.", Draft „Noch nicht geplant").
  - Test: Charakterisierungstest (SSR mobil + Desktop) vor und nach dem Umzug identisch, dazu E2E `compare-hub-fidelity-s8c` unverändert grün.
- **AC-4:** Given ein Ortsvergleich mit einem gelöschten Ort in der Liste / When die Übersicht geöffnet wird / Then nennt die Orte-Karte die Zahl der auflösbaren Orte, in Kopfzeile und Namenszeile übereinstimmend (bewusste Änderung gegenüber der gespeicherten Kennungszahl).
  - Test: Modelltest mit drei Kennungen und zwei auflösbaren Orten ergibt „2 Kandidaten".
- **AC-5:** Given ein aktiver Trip / When die Übersicht geöffnet wird / Then zeigt die Status-Kennzahl denselben Wortlaut wie das Status-Badge im Trip-Kopf, und der Ortsvergleich zeigt weiter Kopf-Pille und Status-Kennzahl nebeneinander.
  - Test: E2E für beide Arten, Kennzahl-Text gleich Badge-Text (Trip).
- **AC-6:** Given ein Trip, dessen Briefing-Log einen planmäßigen Versand vom 28.10.2026 und einen später per Test-Versand-Knopf ausgelösten Eintrag vom 30.10.2026 enthält / When die Übersicht geöffnet wird / Then zeigt „Zuletzt raus" den 28.10.2026.
  - Test: Modelltest mit zwei Einträgen (`on_demand` gesetzt/nicht gesetzt), dazu E2E mit echtem Test-Versand.
- **AC-7:** Given ein Trip ohne jeden Versand / When die Übersicht geladen ist / Then zeigt „Zuletzt raus" „Noch kein Versand", beim Laden und bei Ladefehler „—", und niemals ein erfundenes Datum.
  - Test: Modelltest und E2E mit frischem Trip.
- **AC-8:** Given ein Trip / When die Übersicht geöffnet wird / Then erscheint die Versand-Karte (Briefing-Zeiten, nächster Versand) mit Knopf „Bearbeiten →", der in den Reiter Wetter-Metriken am Abschnitt Versand springt; bei Entwurf steht dort „Noch nicht geplant".
  - Test: E2E, Klick auf den Knopf landet im Versand-Abschnitt; Entwurf-Trip zeigt den Hinweistext.
- **AC-9:** Given ein Trip mit aktivierten Kanälen E-Mail, Telegram, SMS und Premium-SMS / When die Übersicht geöffnet wird / Then nennt die Kanäle-Kennzahl alle vier Kanäle, und die Karte „Briefings laufen" zeigt je Zeile die tatsächlich eingestellten Kanäle statt fest E-Mail und Telegram.
  - Test: E2E: Trip mit allen vier Kanälen, dann Trip mit nur Premium-SMS; Anzeige folgt der Einstellung.
- **AC-10:** Given ein Trip mit eigenem Alert-Kanal-Satz (`alert_channels`) / When die Übersicht geöffnet wird / Then zeigt die Zeile „Alert-Trigger" genau diese Kanäle; fehlt der Satz (Altbestand), die Briefing-Kanäle.
  - Test: Modelltest und E2E mit je einem Trip pro Fall.
- **AC-11:** Given ein Trip / When die Übersicht geöffnet wird / Then gibt es keine Karte „Alerts (letzte 7 Tage)" und keinen Knopf „Alle Alerts →" mehr; die Alarme bleiben über den Reiter Alarme erreichbar.
  - Test: E2E: weder Karte noch Knopf vorhanden, Reiter Alarme öffnet sich per Klick.
- **AC-12:** Given ein Trip und ein Ortsvergleich / When jeweils die Übersicht geöffnet wird / Then lädt die Seite die Versand-Historie genau einmal, und Kennzahl „Zuletzt raus" (Trip) und Historien-Liste stammen aus derselben Antwort.
  - Test: E2E zählt Netzaufrufe an `/api/briefings/{id}/briefing-history` (Trip: ein Aufruf).
- **AC-13:** Given Trip und Ortsvergleich / When der Nutzer die Übersicht öffnet / Then gibt es unter der Hauptfläche für beide Arten die Versand-Historie, und alle bisherigen Kennungen (`hub-summary-row-mobile`, `compare-hub-versand-edit`, `compare-detail-stat-kanaele`, `hub-metrics-*`) sind unverändert vorhanden.
  - Test: E2E `HUB_KINDS`-Schleife, Existenz und Anzahl der Kennungen.
- **AC-14:** Given zwei verschiedene Nutzer A (mit Versand-Eintrag) und B (ohne) / When B seine Trip-Übersicht öffnet / Then sieht B weder Datum noch Einträge von A, „Zuletzt raus" zeigt „Noch kein Versand", und der Aufruf mit der Trip-Kennung von A liefert B keine Daten.
  - Test: E2E auf Staging mit zwei Konten.
- **AC-15:** Given die Übersicht eines Trips oder Vergleichs / When sie dargestellt wird / Then zeigt kein Element einen Festwert ohne Datenquelle: kein Festtext zu Alerts, keine fest eingetragenen Kanäle, keine Handlungsempfehlung, nur Daten.
  - Test: Modelltest: jede Kennzahl ist aus Eingabedaten ableitbar; Eingabe geändert ⇒ Anzeige geändert (Mutation Festwert ⇒ rot).
- **AC-16:** Given der Ortsvergleich-Hub / When der Reiter Wetter-Metriken geöffnet wird / Then funktioniert die Aktivierungs-Karte (`hubActivationCard`) unverändert.
  - Test: bestehender E2E zur Aktivierung bleibt grün.
- **AC-17:** Given die Spec-Wächter / When `compare-hub-fidelity-s8c` ohne `gz-eigenstaendig`-Kopf läuft / Then besteht `test_e2e_compare_paritaet_waechter.py` nur, weil die Spec per `HUB_KINDS` beide Arten prüft; HT-10 in `hub-tab-bar` läuft ebenfalls für beide Arten.
  - Test: Wächter-Test grün; Mutation (Schleife entfernt) ⇒ rot.
- **AC-18:** Given die Unit-Tests, die heute CompareTabs/HubOverview per Quelltextpfad lesen / When der Umbau fertig ist / Then prüfen sie die gleichen Zusicherungen am neuen Baustein (Tabelle „Zuordnung der Tests"), keine ist gelöscht oder abgeschwächt; allein das Sprungziel „Alle Alerts →" entfällt gemäß AC-11.
  - Test: Test-Diff-Prüfung in /60: Anzahl und Strenge der Zusicherungen je Datei vor und nach dem Umzug.
- **AC-19:** Given die Doku / When der Umbau geliefert ist / Then führen `feat_2347_s4_paritaets_e2e.md` (Befund 6, AC-20, AC-22) und `docs/reference/gates_und_ratschen.md` die Hub-Übersicht nicht mehr als Vergleichs-Eigenheit, und in #2658 (i18n F9) und #2659 (i18n F10) steht je ein Kommentar mit dem neuen Ort `shared/hub-uebersicht/` und dem Hinweis, dass die Prämisse „keine neue Komponente" und die Zeilenangaben nachzuziehen sind.
  - Test: Doku-Prüfung in /60 (Absatz gestrichen, Kommentare vorhanden); Doku-Test `tests/unit/test_hub_uebersicht_doku_2682.py` mit Kennzeichnung `# doc-compliance-test`: gates-Absatz gestrichen; weil `feat_2347_s4` abgeschlossen und eingefroren ist (Befund 6, AC-20, AC-22, Kopftabelle per `frozen_spec_sha256` gesperrt), prüft er dort je Stelle einen Vermerk „Abgelöst durch #2682" mit dem Pfad `shared/hub-uebersicht/HubUebersicht.svelte` in Known Limitations und im Changelog-Eintrag 2026-11-01.

## Known Limitations

- Die Karte „Briefings laufen" (Trip) überschneidet sich teilweise mit der Kennzahl „Briefings" und der Versand-Karte. Sie bleibt, weil sie je Slot Aktiv-Status und Alert-Kanäle trägt, die sonst nirgends in der Übersicht stehen. Eine Zusammenlegung ist bewusst nicht Teil dieses Tickets.
- Eine Alert-Historie (7 Tage) für Trips gibt es nur mit einem neuen Endpunkt; das wäre ein eigenes Ticket und ist hier nicht enthalten.
- „Zuletzt raus" des Trips ist die Zeit des neuesten planmäßig zugestellten Briefings; Versuche ohne zustellbaren Kanal oder mit Fehler erscheinen nicht (der Log führt sie nicht).
- Die Dublette `atoms/Stat` / `molecules/Stat` bleibt bestehen (#1199).
- Folgepflicht nach Merge: Kommentar in #2658 und #2659 (AC-19), weil F9/F10 Zeilenangaben und SSR-Golden-Fixtures auf HubOverview/CompareTabs stützen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; setzt ADR-0097 (Trip/Ortsvergleich-Code-Teilung) und ADR-0095 (Kanal-Parität) um.
- **Rationale:** Der Baustein folgt dem etablierten Muster `context="route"|"vergleich"` unter `shared/` (SubscriptionHeader, VersandTab, AlarmeTab); es wird keine Entscheidung rückgängig gemacht.

## Changelog

- 2026-11-01: Initial spec created (Issue #2682, Epic #2345)
