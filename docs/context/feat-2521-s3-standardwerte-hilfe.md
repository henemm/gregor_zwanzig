# Context: feat-2521-s3-standardwerte-hilfe

## Request Summary
Letzte Scheibe von #2521 (PO 17.10.: beide Restpunkte zusammen, danach Issue zu):
(A) „Mit Standardwerten speichern" im Trip- (`/trips/new`) und Ortsvergleich-Anlege-Editor (`/compare/new`), sobald die Pflichtangaben da sind — heute muss jeder hintere Reiter einmal besucht werden.
(B) Hilfeseite „So funktioniert Gregor" (Briefing-Zeiten, Alarme, Kanäle; Antwort-Befehle nachrangig) inkl. Hilfelink aus der Startklar-Checkliste (S2). Alle Texte im Textkatalog.

S1 (ⓘ + Infobox) und S2 (Willkommen, Checkliste, Testmail) sind live. Gesamt-Spec: `docs/specs/modules/onboarding_hilfe_2521.md` (S3-Absatz + AC-15..17, Hilfe-AC-2) — **teilweise veraltet**, siehe Risiken.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/shared/anlegeLockEngine.ts` | Geteilter Kern: `tailUnlocked`/`tailDone` (Z.33–51), `canFinish = done.has(versand)` (Z.54–56), `progressCount` (Z.59). Hierhin gehört eine kind-neutrale Pflicht-/Standardwerte-Regel |
| `frontend/src/lib/components/trip-new/tripNewLogic.ts` | `TabId` (Z.21), `unlockedTabs` (Z.30), `doneTabs` (Z.57), `canSave` (Z.97), `initialCreateTripAlarmState` (Z.151), `buildCreateTripPayload` (Z.197–257) |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | TAB_DEFS (Z.77–85, nur wegpunkte optional), `etDone` (Z.169), `switchTab` setzt Besuchs-Flags (Z.246–259), `buildAndSave` (Z.425–455), **`beforeNavigate`-Autosave bei `ready`** (Z.458–465), Speichern-Knopf Desktop `trip-new-save-btn` im `EditorStickyFooter` (Z.941–952), mobil `tn-mobile-save` (Z.1220–1224); Versand-Reiter nur bei aktivem Tab gemountet (Z.869–884) |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | Reiter (Z.61,113–120), Freischaltung Name→≥2 Orte→Schwanz (Z.143–173), `canActivateNow = canFinish(done)` (Z.176), `switchTab` (Z.207–214), `handleActivate` (Z.236–246); Desktop-Knopf `compare-editor-activate` **in der Breadcrumb-Kopfzeile** (Z.309–322), mobil `cm-mobile-activate` im StickyFooter nur auf Versand (Z.540–555); Schwanz-Reiter nur aktiv gemountet (Z.420–449) |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | Alle Compare-Defaults im State (Z.14–116); `saveNewPreset` (Z.132–188) |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | `buildNewComparePresetPayload` (Z.425ff), Alarm-Kanal-Default `newEntityAlertChannelDefault()` (Z.455) |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | Dauerhaft gemountet (Trip); schreibt Metriken erst nach `catalogLoaded` (Z.707–711), Kanäle (Z.672–676), Tagesfenster 4/19 (Z.717–724), Aktivitäts-Vorlage (Z.663–669) |
| `frontend/src/lib/components/shared/VersandTab.svelte` + `versand-tab/reportConfigPayload.ts` | `$effect` beim Mount schreibt report_config-Defaults (Z.201–236; Defaults Z.65–134) |
| `frontend/src/lib/components/trip-new/MailInhaltCard.svelte` + `mailInhaltZustand.ts` | schreibt `email_format`/`show_*` erst beim Mount |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte` (+ `CorridorEditorMobile.svelte`) | Compare: Profil-Prefill beim Mount spiegelt `corridors`/`idealRanges`/`activeMetricKeys`/`metricAlertLevels` in den Wizard (Z.146–152,197–200,281–291) |
| `frontend/src/lib/components/shared/EditorStickyFooter.svelte` | Geteilter Footer-Rahmen (Z.10–23), nur children-Snippet |
| `frontend/src/lib/components/shared/alertChannelState.ts` | Alarm-Kanal-Default E-Mail + Telegram an (Z.27–36, #2518 closed) |
| `frontend/src/lib/i18n/messages/de.json` + `i18n/index.ts` | Textkatalog, `t(key: MessageKey)`, unbekannter Key = Typfehler; Infobox-Texte `info.*` (Z.32–40) |
| `frontend/src/lib/components/shared/infoboxKeys.ts` | Infobox-Zuordnung (Z.14–33); Ratsche `context_herkunft_zweige_eingefroren` (Z.5–7) |
| `frontend/src/routes/_home/StartklarCheckliste.svelte` | S2-Checkliste; Hilfelink-Stelle Kopf (Z.57–62) oder nach Hinweisen (Z.94–98); eingebunden in `routes/+page.svelte:193–203` |
| `frontend/src/hooks.server.ts` | `publicPaths` (Z.25); neue Route ist automatisch nur für Eingeloggte |
| `frontend/src/routes/archiv/` | Vorlage für einfache statische Seite |
| `frontend/src/lib/components/ui/sidebar/Sidebar.svelte` (Z.32–35, 169–177), `KontoSheet.svelte` (Z.39–41), `shared/AppFooter.svelte` (Z.25–33) | Kandidaten für Navigations-Hilfelink |
| `internal/handler/trip.go` (Z.162–240), `internal/handler/compare_preset.go` (Z.194–258) | Backend-Defaults: Trip setzt keine report_config-Defaults; Compare setzt forecast_hours 48, Slots 07:00 an / 18:00 aus |
| `src/app/loader.py` (Z.595–625), `src/app/models.py` (Z.1132–1190) | Python-Lese-Defaults für fehlende report_config (u. a. `multi_day_trend_reports=["evening"]`) |
| `src/services/trip_command_processor.py` | `_COMMAND_SPECS` (Z.251–278) = einzige Quelle der Antwort-Befehle; `command_rows()` (Z.287), `hilfe_kurzform()` (Z.335); Warnung gegen Kopien (Z.287–293) |

## Existing Patterns
- Progressive Tabs + geteilte Lock-Engine (`anlegeLockEngine.ts`), Trip und Vergleich parametrisiert über `context="route"|"vergleich"`; Paritätstest `anlege_reiterleiste_trip_vergleich_paritaet.test.ts`.
- „Done" der Schwanz-Reiter = besucht (Flag in `switchTab`), nie zurückgesetzt.
- Defaults werden teils im Parent-State geführt (Trip-Alarme, Compare-Wizard), teils erst von Reiter-`$effect`s beim Mount geschrieben (Trip-Versand/Mail-Inhalt, Compare-Wertebereiche-Prefill).
- Texte: `t('…')` aus `$lib/i18n/index.js` (Muster `StartklarCheckliste.svelte:4`); Katalog-Tests `textkatalog.test.ts`, `onboarding_textkatalog.test.ts` (prüfen u. a. „Tour" und Handlungsempfehlungen).
- Frontend-Tests: `node --import ./test-lib-loader.mjs --experimental-strip-types --test …` (kein Vitest).

## Dependencies
- Upstream: `GET /api/metrics` (Katalog, `default_enabled`), `POST /api/trips`, `POST /api/compare/presets`, Python-Lese-Defaults, `alertChannelState`.
- Downstream: Trip-/Compare-Detailseiten, Scheduler (`trip_report_scheduler.py`, `send_email = not config or config.send_email` Z.1916), Startseiten-Cockpit (`cockpitHelpers.ts:124`), alle Tests, die das Speicher-Gate fixieren (s. u.).

## Existing Specs
- `docs/specs/modules/onboarding_hilfe_2521.md` — Gesamtbild, S3 + AC-15..17, Hilfe-AC-2 (draft)
- `docs/specs/modules/onboarding_willkommen_checkliste.md` — S2 („kein Hilfelink, spätere Scheibe", Z.102/182)
- `docs/specs/modules/begriff_erklaerung_infobox.md` — S1
- `docs/specs/modules/feat_2277_s4_anlege_lockengine.md`, `feat_1301_f2a_compare_new_trip_pattern.md`, `fix_2277_s1_alarme_tab_route.md`, `fix_2277_s2a_wertebereiche_trip_anlegen.md`
- ADR-0032 (Wizard-Abschaffung, nicht erneut vorlegen), ADR-0092 (Testmail)

## Risks & Considerations
1. **Kernbefund: Speichern ohne Reiter-Besuch erzeugt heute NICHT dieselben Daten wie Durchklicken.**
   - Trip: `report_config` enthält ohne Versand-Besuch nur das Tagesfenster; Python-Lese-Default `multi_day_trend_reports=["evening"]` vs. VersandTab schreibt `[]` → ohne Besuch Mehrtages-Trend im Abend-Briefing. Go-Flachfelder (`SendEmail` …) bleiben nil.
   - Trip: `weatherMetrics=[]` bis `catalogLoaded` → Wettlauf, Knopf muss bis dahin gesperrt sein oder aus dem Katalog bauen.
   - Compare: Wertebereiche-Prefill (Profil) entsteht nur beim Besuch → ohne Besuch fehlen `corridors`/`ideal_ranges`/`active_metrics`. Infobox sagt „keine Wertebereiche" → Entscheidung, was „Standard" heißt.
   - Lösungsrichtung: Defaults explizit über dieselben Bausteine bauen, die die Reiter nutzen (z. B. `baueReportConfigPayload(ladeReportZustand(...))`), kein zweites Regelwerk.
2. **`beforeNavigate`-Autosave** (Trip Z.458–465) hängt an `ready`: wird `canSave` aufgeweicht statt eigenes Gate, löst jedes Wegnavigieren nach Name+Datum einen POST aus.
3. **Pflichtangabe Trip:** Gesamt-Spec sagt `stages.length >= 1` — immer wahr (Editor startet mit 2 leeren Etappen). Heutige Sperre verlangt `etDone` (alle Etappen mit GPX). Muss bleiben oder bewusst entschieden werden.
4. **Veraltete Annahmen der Gesamt-Spec:** „Alarm nur E-Mail" (seit #2518 E-Mail + Telegram); „Knopf im EditorStickyFooter" (Compare-Desktop hat keinen Footer, Knopf in Kopfzeile); „weatherMetrics startet leer" nur halb wahr.
5. **Infobox-Konsistenz:** `info.alarme.vergleich` nennt „amtliche Warnungen aus", Compare sendet aber `official_alert_triggers_enabled: true` — Begriffsunschärfe prüfen. `info.versand.route` erwähnt den Trend nicht.
6. **Tests fixieren das alte Gate:** `tripNewLogic.test.ts:160–172`, `trip_new_reiterleiste_besuchs_flags.test.ts:74–81`, `anlege_lock_engine.test.ts:86–92`, `compare_new_lock_engine_wirkstelle.test.ts:97–98`, `compare_anlege_freischaltung.test.ts:61`, Paritätstest, `infobox_nur_beim_anlegen.test.ts`; E2E `compare-editor-slice4.spec.ts:34–50` u. a. Bewusst anpassen, nicht stilllegen. Mögliche Lösung: Bestands-Knopf unverändert lassen, zusätzlicher Knopf mit eigenem Gate.
7. **Code-Teilung:** EIN geteilter Knopf/Baustein + EINE geteilte Gate-Funktion; keine neuen `context`-Verzweigungen (Ratsche); Pendant-Sperre am Commit.
8. **Hilfeseite:** Antwort-Befehle nicht als Kopie in de.json pflegen (Drift gegen `_COMMAND_SPECS`) — Quelle verdrahten oder Katalog-Drift-Test. Öffentlich oder nur eingeloggt (Default: nur eingeloggt, wie alle Routen). Keine „Tour"-/Wizard-Anmutung, keine Handlungsempfehlungen. Kanäle: alle vier gleichrangig beschreiben (CLAUDE.md), SMS/Premium-SMS „je nach Tarif".
9. Multi-User: neue Speichern-Wege laufen über bestehende Endpoints (user_id aus Auth-Kontext) — kein neuer Endpoint geplant; falls Befehlsliste per Endpoint kommt → Zwei-Nutzer-Test nicht nötig (nutzerneutral), aber Auth-Schutz prüfen.

## Analysis

### Type
Feature (letzte Scheibe #2521: A = „Mit Standardwerten speichern", B = Hilfeseite `/hilfe`). EIN Workflow für beide Teile (PO 17.10.), `loc_limit_override 500` statt Abspaltung.

### Kernbefunde (Recherche 17.10.)
- **Trip:** WeatherMetrics/Wertebereiche/Alarme sind Desktop UND Mobile dauerhaft gemountet (`TripNewEditor.svelte:900-937`, mobil ~1165-1195, `style:display`) und schreiben ohne Besuch. Versand + MailInhalt nur bei `activeTab==='versand'` (Z.869-885, mobil ~1150). Ohne Versand-Besuch: `report_config` = nur `{day_window_start_hour:4, day_window_end_hour:19}`; es fehlen `enabled`, `morning/evening_enabled/_time`, `multi_day_trend_*`, `telegram_style`, `send_*`, alle Mail-Felder (`email_format`, `show_*`, `daily_summary_metrics`, `wind_exposition_min_elevation_m`, `show_metrics_summary`).
- Reine Builder existieren: `ladeReportZustand(undefined)` + `baueReportConfigPayload` (`shared/versand-tab/reportConfigPayload.ts:71-133`), `ladeMailZustand(undefined)` (`shared/mailInhaltZustand.ts:25-41`). VersandTab-`$effect` Z.201-236, MailInhaltCard-`$effect` Z.61-80.
- `display_config.metrics` erst nach `catalogLoaded` (`WeatherMetricsTab.svelte:707-709`), Parent startet `[]` (Z.104) → Wettlauf. Trip nutzt `trip_default_enabled`, nicht `default_enabled`.
- Python-Lese-Default `multi_day_trend_reports=["evening"]` (`src/app/loader.py` ~595-625) ≠ VersandTab-Schreibwert `[]` → ohne explizites Bauen anderes Abend-Briefing.
- **Compare:** Wizard-State hält Versand-/Alarm-Defaults bereits (`compareWizardState.svelte.ts:14-116`). Ohne Wertebereiche-Besuch: `corridors []`, kein `active_metrics`/`ideal_ranges`/`metric_alert_levels` → Mail zeigt alle CV2-Metriken ohne Markierung (`compare_html.py:813`, Baseline-Test `test_compare_mail_corridor_mark.py:183`). Beim Besuch dagegen Profil-Prefill über reine Funktionen `buildComparePrefillRows` (`corridorEditorState.ts:642-668`) + `buildCompareCorridorSavePayload` (:693-750), braucht `GET /api/compare/metrics`. Profil-Unschärfe: Prefill ALLGEMEIN (`CorridorEditor.svelte:149`), Payload `activityProfile ?? 'wandern'` (`compareEditorSave.ts:~432`).
- Gate nur im UI: `saveNewPreset` hat keinen Guard; `canActivateNow=canFinish(done)` (`CompareNewEditor.svelte:176`, `anlegeLockEngine.ts:54-56`).
- **Hilfe:** keine `/hilfe`-Route, keine Nav-Links (`Sidebar.svelte:32-35`, `BottomNav.svelte:33-36`, `KontoSheet.svelte:39-41`, `AppFooter.svelte:29-30`). Befehle: einzige Quelle `_COMMAND_SPECS`/`command_rows()` (`trip_command_processor.py:251-287`), kein Endpoint; `telegram.py:123-130` hat bereits statische Kopie.
- **Infobox-Fehler:** `info.alarme.vergleich` „amtliche Warnungen aus" widerspricht `official_alerts_enabled=true` (Wizard :75/:86) → in diesem Workflow mitkorrigieren.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/anlegeLockEngine.ts` | MODIFY | kind-neutrale Gate-Funktion `canFinishMitStandardwerten({pflichtErfuellt, defaultsBereit})` neben `canFinish` |
| `frontend/src/lib/components/shared/StandardwerteSpeichernKnopf.svelte` | CREATE | EIN geteilter Knopf (Props enabled/saving/onclick/testid), keine `context`-Verzweigung |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | MODIFY | Knopf Desktop-Footer (Z.941-952) + mobil (Z.1220); beim Klick fehlende `reportConfig` aus `baueReportConfigPayload(ladeReportZustand(undefined))` + `ladeMailZustand(undefined)` bauen; Gate an `catalogLoaded` |
| `frontend/src/lib/components/trip-new/tripNewLogic.ts` | MODIFY | reiner Defaults-Ergänzer für `reportConfig` (testbar ohne Mount) |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | MODIFY | Knopf Kopfzeile (Z.309-322) + mobil StickyFooter auf allen Reitern (Z.540-555) |
| `frontend/src/routes/hilfe/+page.svelte` | CREATE | Hilfeseite (Briefing-Zeiten, Alarme, Kanäle, untergeordnet Antwortbefehle), Muster `routes/archiv/` |
| `frontend/src/routes/_home/StartklarCheckliste.svelte` | MODIFY | Hilfelink (Kopf Z.57-62) |
| `frontend/src/lib/components/ui/sidebar/Sidebar.svelte`, `KontoSheet.svelte` | MODIFY | Hilfe-Navigationslink (BottomNav unverändert, Slots knapp) |
| `frontend/src/lib/i18n/messages/de.json` | MODIFY | Knopf-, Hilfe-, Link-Texte; Korrektur `info.alarme.vergleich` |
| `docs/specs/modules/onboarding_hilfe_2521.md` | MODIFY | AC-15..17 + Hilfe-AC-2 nachziehen (veraltet, s. u.) |
| Tests (neu) | CREATE | Gate-Unit, Paritätstest Defaults-Builder ↔ Reiter-Ausgabe (Deep-Equal), Autosave-kein-Doppel-POST, Hilfe-Render gegen Katalog, Python-Drift-Test `command_rows()` ↔ de.json, E2E Trip+Compare „Pflicht → Standardwerte → Detailseite", Paritätstest Reiterleiste um neuen Knopf erweitern |

### Scope Assessment
- Files: ~10 produktiv + ~6 Tests
- Estimated LoC: ~+300 produktiv (A ~150, B ~150), Schätzung → `loc_limit_override 500`
- Risk Level: MEDIUM (A berührt Speicherpfade beider Anlege-Editoren; B ist risikoarm)

### Technical Approach
**A — Standardwerte (Variante V1, gewählt):** Defaults beim Klick über dieselben reinen Funktionen bauen, die die Reiter nutzen — kein zweites Regelwerk. Verworfen V2 (Versand/MailInhalt versteckt immer mounten): Testmail-, Fetch- und Infobox-Nebenwirkungen, bewusstes XOR (Z.869-884).
- **Bestandsknopf bleibt** (`canSave`/`canFinish` unverändert). Neuer Knopf zusätzlich mit eigenem Gate; verschwindet, sobald der Bestandsknopf frei ist. Alte Gate-Tests bleiben gültig.
- **Pflichtangaben:** Trip = Name + Startdatum + alle Etappen mit GPX (`etDone`, heutiges `metrikenFrei`; „≥1 Etappe" der Spec ist immer wahr, verworfen). Compare = Name + ≥2 Orte.
- **`defaultsBereit`:** Trip = Metrik-Katalog geladen (erste Emission nach `catalogLoaded`); Compare = Vergleichs-Metrik-Katalog geladen (PO-Entscheid Vorbelegen, s. Open Questions).
- **Autosave** `beforeNavigate` (Z.458-465) bleibt an `ready` — NICHT an das neue Gate; `savedTripId` verhindert Doppel-POST (Test).
- `multi_day_trend_reports=[]` wie VersandTab (= Durchklicken), Python-Lese-Default für Altdaten unberührt.
- Leitprinzip: Standardwerte-Speichern = exakt dieselben Daten wie unverändertes Durchklicken aller Reiter.

**B — Hilfeseite:** Statischer Katalog-Text + Python-Drift-Test gegen `command_rows()` (statt neuem Endpoint über 3 Stacks: ~60 LoC + Auth/Proxy für einen nachrangigen Abschnitt unverhältnismäßig). Kanäle: **alle vier gleichrangig** — E-Mail, Telegram, SMS, Premium-SMS (Signal entfernt, #610); Spec-Formulierung „E-Mail als Hauptkanal" streichen (CLAUDE.md). Keine „Tour"-, Wizard- oder Handlungsempfehlungs-Anmutung. Route nur für Eingeloggte (`hooks.server.ts:25`).

### Dependencies
- Upstream: `GET /api/metrics` (Trip-Katalog), `POST /api/trips`, `POST /api/compare/presets` (bestehend, user_id aus Auth — kein neuer Endpoint), `reportConfigPayload.ts`, `mailInhaltZustand.ts`, `alertChannelState.ts`, `_COMMAND_SPECS`.
- Downstream: Trip-/Compare-Detailseiten, Scheduler, Briefing-Mails, Reiterleisten-Paritätstest, Textkatalog-Tests (`textkatalog.test.ts`, `onboarding_textkatalog.test.ts`).

### Befunde gegen/neben den Plan
1. Kanal-Uneinheitlichkeit Trip (`display_config.channels.telegram=true`, `report_config.send_telegram=false`, `alert_channels.telegram=true`) entsteht auch beim Durchklicken → nicht Teil dieser Scheibe; Kandidat für #1199.
2. Spec `onboarding_hilfe_2521.md` veraltet: „Alarm nur E-Mail" (seit #2518 E-Mail+Telegram), „Knopf im StickyFooter" (Compare-Desktop: Kopfzeile), „≥1 Etappe" (immer wahr), „E-Mail Hauptkanal" → in `/30` nachziehen.
3. Python-Lese-Default `["evening"]` vs. Schreibwert `[]` — bestehender Widerspruch, nur dokumentiert.

### Open Questions
- [x] **PO-Entscheid 17.10. (AskUserQuestion): Ortsvergleich wird VORBELEGT** — gleiche Wertebereiche wie beim Öffnen des Reiters (Leitprinzip: Standardwerte = unverändertes Durchklicken).
  Folgen für Spec/Umsetzung:
  - Compare-Standardwerte bauen Wertebereiche über `buildComparePrefillRows` (`corridorEditorState.ts:642-668`) + `buildCompareCorridorSavePayload` (:693-750) — dieselbe Kette wie `CorridorEditor` (`computeInitialCompare`/`syncToWizard`, Z.143-152, ~279-291), kein zweites Regelwerk; Profil exakt wie beim Besuch (Prefill-Profil, Z.149) — die Abweichung zum Payload-Fallback `'wandern'` darf beim Standardwerte-Weg NICHT entstehen.
  - Compare `defaultsBereit` = `GET /api/compare/metrics` geladen (nicht mehr „immer true"); Fehlerpfad: Knopf bleibt gesperrt.
  - Paritätstest Compare: Standardwerte-Payload Deep-Equal zur Payload nach unverändertem Wertebereiche-Besuch.
  - Infobox `info.wertebereiche.vergleich` („Standard: keine Wertebereiche …") ist dann falsch → im Textkatalog korrigieren.
  - Compare-Wiring wächst um ~+25 LoC (Katalog-Load + Prefill) → Gesamtschätzung ~+325, `loc_limit_override 500` bleibt ausreichend.
