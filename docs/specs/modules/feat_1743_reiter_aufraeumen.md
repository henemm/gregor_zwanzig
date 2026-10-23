---
entity_id: feat_1743_reiter_aufraeumen
type: feature
created: 2026-10-22
updated: 2026-10-22
status: draft
version: "1.0"
tags: [trip-hub, compare-hub, reiter, versand, vorschau, anlegen, saveController, shared, aufraeumen, backend-rueckbau]
workflow: feat-1743-reiter-aufraeumen
---

# Reiter aufräumen: Versand unter Wetter-Metriken, Briefing-Vorschau entfällt, eine Quelle der Reiterfolge (Issue #1743)

## Approval

- [ ] Approved

## Purpose

Issue #1743. Die Hub-Reiterleiste von Trip und Ortsvergleich wird auf fünf Reiter verkürzt und überall
gleich gebaut: **Übersicht · Etappen & Wegpunkte (Trip) / Orte (Vergleich) · Wetter-Metriken · Wertebereiche ·
Alarme**. Der Reiter „Versand" entfällt — sein Inhalt (Versandzeiten, Kanäle, beim Ortsvergleich die
Aktivierungs-Karte Pausieren/Aktivieren) hängt unten am Reiter Wetter-Metriken (Anker `#versand`). Der Reiter
„Vorschau" entfällt **ersatzlos** (PO-Entscheid 2026-10-22): die Briefing-Vorschau je Kanal wird samt Aktionen,
Sprunglinks und Backend-Endpoint zurückgebaut.

Der PO-Wunsch lautet ausdrücklich: **den Code aufräumen und alles rund um die Reiter vereinheitlichen.** Darum
gehört zu diesem Ticket nicht nur das Streichen von zwei Reitern, sondern:

1. **Eine Quelle der Reiterfolge.** Heute ist die Reiterliste dreifach verdrahtet (`shared/subscriptionTabs.ts`
   für beide Hubs, eigene Listen in `TripNewEditor.svelte` / `tripNewLogic.ts` und `CompareNewEditor.svelte`).
   Danach leiten Hubs und Anlege-Seiten Kennung, Label und Reihenfolge aus **einer** Definition ab.
2. **Ein geteilter Panel-Baustein** „Wetter-Metriken + Versand" für Hub und Anlegen, beide Kontexte.
3. **Keine Alt-Reste:** Totcode (`PreviewCard`, `BriefingPreviewCard`, `LTComparePreview`), nicht mehr benötigte
   Typen/Schlüssel/Listeneinträge (`versand`/`vorschau` in Badges, Flush-Listen, `TRIP_TAB_MAP`, Aktionsmodell),
   der Infobox-Typ `InfoboxReiter` (heißt Reiter, enthält aber `versand`, das kein Reiter mehr ist), der tote
   Backend-Endpoint `GET /api/briefings/{id}/preview` samt Python-Gegenstück und veraltete Tests/Specs.
4. **Datenverlust-Risiko beheben:** Der `saveController` hat einen einzigen Pending-Slot. Liegen Wetter-Metriken
   und Versand auf einer Seite, überschreibt der zweite Schreiber binnen 700 ms den ersten **still** (Anzeige
   trotzdem „Gespeichert"). Das Risiko besteht heute schon innerhalb von `WeatherMetricsTab` (zwei eigene
   Speicherwege) und wird durch das Zusammenlegen der Reiter verschärft — es wird im selben Ticket behoben
   (Besitzer-Schlüssel).

### Was der PO nach dieser Etappe anders sieht

1. Beide Hubs haben fünf Reiter; „Versand" und „Vorschau" gibt es nicht mehr.
2. Unter den Wetter-Metriken folgt ein Abschnitt „Versand" (Zeiten, Kanäle; beim Ortsvergleich zusätzlich
   Pausieren/Aktivieren). „Zeitplan bearbeiten →" springt direkt dorthin.
3. Die Aktionen „Vorschau" in Trip-/Ortsvergleich-Liste, Mobil-Menü, Cockpit („Vorschau prüfen →") und
   Übersicht („Vorschau öffnen") sind weg. Mini-Vorschauen (Chat-Blase, SMS-Rahmen, Kanal-Umschalter) gibt es
   nicht mehr (PO-Entscheid 2026-10-22); es bleibt nur die Alarm-Vorschau im Reiter Alarme.
4. Auf `/trips/new` und `/compare/new` gibt es keinen Schritt „Versand" mehr; sein Inhalt steht unten im Schritt
   „Wetter-Metriken". Fertig/Anlegen wird frei, sobald „Alarme" besucht ist.
5. Alte Links (`?tab=versand`, `?tab=briefings`, `?tab=vorschau`, `?tab=preview`) funktionieren weiter und
   werden einmal auf die neue Adresse umgeschrieben.
6. Auf Versand-Einstellungen aller **vier Kanäle** (E-Mail · Telegram · SMS · Premium-SMS) hat das keinen
   inhaltlichen Einfluss: Briefing- und Alarm-Inhalt bleiben unverändert; nur die Stelle der
   Versand-Einstellungen wechselt.

## Source

- **Frontend (Pfade relativ zu `frontend/src/`)** — Bearbeitung und Löschung siehe „Affected Files".
  Kern: `lib/components/shared/subscriptionTabs.ts`, `lib/components/trip-detail/TripTabs.svelte`,
  `lib/components/compare/CompareTabs.svelte`, `lib/stores/saveStatusStore.svelte.ts`,
  `lib/components/trip-new/*`, `lib/components/compare-new/*`, `lib/components/shared/anlegeLockEngine.ts`.
- **Go-API:** `internal/router/router.go`, `internal/handler/briefing_preview.go`.
- **Python-Core:** `api/routers/preview.py`, `src/services/preview_service.py`.
- **Kontext:** `docs/context/feat-1743-reiter-aufraeumen.md` (Analyse inkl. PO-Entscheide, verbindlich).

> **Schicht:** Full-Stack. Frontend (SvelteKit) = Hauptlast; Go und Python nur Rückbau (Löschen) der
> Vorschau-Endpoints `GET /api/briefings/{id}/preview`, `GET /api/preview/{trip}/email|telegram` und
> `POST /api/preview/compare/{id}` samt toter Vorschau-Hüllen; `GET /api/preview/{trip}/sms` bleibt. Es entstehen **keine neuen Endpoints** und keine neuen datenbewegenden Pfade.

### Trip/Ortsvergleich-Teilung (Pendant-Prüfung)

- **Geteilt (EIN Code, Parameter `context="route"|"vergleich"`):** neuer Panel-Baustein
  `shared/WetterMetrikenVersandPanel.svelte` (Wetter-Metriken **und** Versand-Abschnitt, in dieser Reihenfolge,
  Anker `#versand`), eingesetzt von `TripTabs` (context `route`), `CompareTabs` (context `vergleich`) und
  beiden Anlege-Editoren. Er komponiert die bereits geteilten Bausteine `WeatherMetricsTab` und `VersandTab`
  (Trip über den Wrapper `BriefingScheduleTab`); `WeatherMetricsTab.svelte` (~2200 Zeilen) bleibt unangetastet
  bis auf Besitzer-Schlüssel und Kommentar.
- **Eine Reiter-Quelle:** `shared/subscriptionTabs.ts` liefert Hub-Leiste **und** Anlege-Kette (siehe
  Implementation Details). Keine zweite Liste in `trip-new/` oder `compare-new/`.
- **Compare-eigen bleibt nur:** Punkte-Reiter Orte (statt Etappen), Aktivierungs-Karte Pausieren/Aktivieren
  (Quelle: `VersandTab` mit `hubActivationCard`; wird im geteilten Panel nur im Kontext `vergleich` gezeigt).
  Eine einseitige Neuanlage gibt es nicht — Pendant-Sperre unproblematisch.

## Estimated Scope

- **LoC (produktiv):** grob +350 / −1100 (Löschanteil hoch: Vorschau-Reiter, Loader, Endpoint, Totcode,
  Dreifach-Liste). Das 250er-Limit wird überschritten; `loc_limit_override 500` ist gesetzt. Test- und
  Doku-Änderungen zählen nicht.
- **Files:** ~30 produktiv (Frontend ~25, Go 3, Python 4), ~30 Unit-Tests, ~18 Playwright-Specs, 3 Python-Test-Dateien, ~6 Docs/Specs.
- **Effort:** high. **Risiko:** MEDIUM-HIGH (stiller Datenverlust im Speicher-Slot, breite Test-Ratsche).
- **Umsetzungsreihenfolge als Scheiben innerhalb EINES Workflows:**
  (S1) Speicher-Slot im Store + Tests;
  (S2) geteilter Panel-Baustein + beide Hubs + Alt-Kennungen + Sprunglinks;
  (S3) eine Reiter-Quelle + beide Anlege-Seiten;
  (S4) Vorschau-Rückbau Frontend + Backend + Totcode + Tests/Doku.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `saveController` (`saveStatusStore.svelte.ts`) | Store | Autosave/Debounce, wird um Besitzer-Schlüssel erweitert |
| `pickEigenfelder.ts` (`VERSAND_REPORT_KEYS` vs. `WETTER_*_KEYS`) | Modul | Feldmengen disjunkt — Voraussetzung dafür, dass beide Schreiber im selben Panel sicher sind |
| `hubPutQueue` / `enqueueTripWrite` + If-Match | Modul | Netz-PUTs je Ressource serialisiert (unverändert) |
| `bereinigteTabAdresse`, `resolveTab` | Funktion | Alt-Kennungen und einmalige Adressbereinigung |
| `anlegeLockEngine.ts` | Modul | Reiter-Sperre/Freischaltung der Anlege-Seiten |
| `WeatherMetricsTab`, `VersandTab`, `BriefingScheduleTab` | Komponenten | geteilte Inhalte, werden komponiert |
| `BriefingAlertPreviewHandler` | Handler | **bleibt** (Alarm-Vorschau) |
| `CompareChatBubble`, `CompareChannelSwitch`, `SmsPhoneFrame` | Komponenten | **entfallen** (PO-Entscheid 2026-10-22, F003); im Arbeitsbaum unter `frontend/src` keine Nutzung mehr (`grep -rn SmsPhoneFrame frontend/src` ohne Treffer) |
| #1839 (Vorschau-502), #2243, #2347, #2345 | Tickets | #1839 wird gegenstandslos |

## Implementation Details

### 1. Eine Quelle der Reiterfolge (`shared/subscriptionTabs.ts`)

```
type SubscriptionKind = 'trip' | 'vergleich'
subscriptionTabs(kind): SubscriptionTab[]      // Hub-Leiste, 5 Einträge
anlegeKette(kind): AnlegeSchritt[]             // aus derselben Definition abgeleitet
```

- Hub-Leiste je kind: `uebersicht · (etappen|orte) · wetter-metriken · wertebereiche · alarme`.
- Anlege-Kette je kind: **Trip** `route · etappen · wegpunkte · wetter-metriken · wertebereiche · alarme`,
  **Vergleich** `vergleich · orte · wetter-metriken · wertebereiche · alarme`. Der Schwanz ab
  `wetter-metriken` wird **nicht** neu aufgezählt, sondern aus der Hub-Definition übernommen (Kennung, Label,
  Reihenfolge). Anlege-eigen sind nur die Kopf-Schritte (`route`/`etappen`/`wegpunkte` bzw. `vergleich`/`orte`
  statt `uebersicht`) und die Zusatzfelder `lockHint`, `optional`.
- Die Liste ist **eine** Konstante; Entfernen oder Umbenennen eines Reiters wirkt ohne Zweitänderung auf Trip-Hub,
  Vergleichs-Hub, `/trips/new` und `/compare/new`. Mobile `MTabBar` bekommt die Liste von `TripTabs`/`CompareTabs`
  (also aus `subscriptionTabs`); eine eigene Liste in `MTabBar.svelte` darf nicht existieren (Prüfung in S3,
  falls vorhanden entfernen).
- `TripNewEditor.svelte:~81-87`, `tripNewLogic.ts:~23,30`, `CompareNewEditor.svelte:~74-78,138-143` verlieren
  ihre eigenen Listen und rufen die Ableitung auf.

### 2. Alt-Kennungen (LEGACY-Map)

- `versand`, `briefings` → `wetter-metriken`, **Anker `#versand`** (Hash der Adresse bleibt/wird gesetzt).
- `vorschau`, `preview` → `uebersicht`.
- Bestehend bleiben `overview`, `stages`, `weather`, `alerts`, `idealwerte`, `layout`.
- `resolveTab` liefert zusätzlich einen optionalen Anker (`anchor?: 'versand'`); `bereinigteTabAdresse` schreibt
  `?tab=wetter-metriken#versand` einmalig um (Muster #2287; kein zusätzlicher Verlaufseintrag, keine Schleife).
- Der Hub scrollt beim Öffnen mit `#versand` zum Versand-Abschnitt, erst nachdem dessen Hydration abgeschlossen
  ist (siehe 4.).

### 3. Geteilter Panel-Baustein `shared/WetterMetrikenVersandPanel.svelte`

- Parameter `context: 'route' | 'vergleich'` plus die bisherigen Props von `WeatherMetricsTab` und
  `VersandTab`/`BriefingScheduleTab`, durchgereicht.
- Reihenfolge: Wetter-Metriken-Inhalt, darunter `<section id="versand">` mit Versand-Inhalt; im Kontext
  `vergleich` ist die Aktivierungs-Karte (Pausieren/Aktivieren) Teil dieses Abschnitts.
- Die Versand-Infobox (nur beim Anlegen, wie bisher) steht **über** dem Versand-Abschnitt.
- Kein Wrapper-`div`, der die bestehende Struktur-Pins (`versand_panel_ohne_wrapper_div`) verletzt; der Test wird
  auf die neue Stelle umgezogen, nicht gelöscht.
- Eingesetzt von `TripTabs.svelte` (Panel `wetter-metriken`), `CompareTabs.svelte` (Panel `wetter-metriken`),
  `TripNewEditor.svelte` und `CompareNewEditor.svelte` (Schritt `wetter-metriken`).

### 4. Compare-Hydration

Versand-`$effect` (`CompareTabs.svelte:~420-425`) und Wetter-`$effect` (`~525-530`) hängen beide an
`activeTab === 'wetter-metriken'`. Der Versand-Abschnitt mountet erst nach seiner eigenen Hydration (keine
Platzhalter-Werte, die vom Autosave als Nutzereingabe gespeichert werden könnten).

### 5. Speicher-Slot (`saveStatusStore.svelte.ts`)

- `saveController.schedule(fn, ms, owner)`: Ist ein Pending-Slot eines **fremden** Besitzers belegt, wird dessen
  Funktion **zuerst gesendet** (flush), danach der neue Slot gesetzt. Gleicher Besitzer ersetzt wie bisher
  (Debounce).
- `saveController.cancel(owner)`: löscht nur den Slot des angegebenen Besitzers. Ohne Argument nur, wenn kein
  Besitzer bekannt ist (Rückwärtskompatibilität im Store-Test, kein Produktaufruf ohne Besitzer).
- Der Flush vor Fremd-Slot muss mit `defer`/`retryConflict`/`cancel` zusammenpassen (Reihenfolge der Netz-PUTs
  bleibt über `hubPutQueue`/`enqueueTripWrite` serialisiert; If-Match-Konflikte laufen wie bisher).
- Anzeige bleibt **ein** Zustand pro Seite.
- Aufrufer mit Schlüssel versehen: `shared/versandVergleichSpeicherung.ts` (`'versand'`),
  `shared/weather-metrics-tab/weatherMetricsCompareSave.ts` (`'wetter-metriken'`),
  `shared/WeatherMetricsTab.svelte` (zwei eigene Wege `scheduleAutoSave` ~1002-1020 und
  `scheduleReportConfigOnlySave` ~1030-1040: zwei verschiedene Schlüssel), `trip-detail/BriefingScheduleTab.svelte`
  (`'versand'`). Das behebt auch den heutigen Trip-internen Verlust zwischen den zwei Wegen.
- Re-Hydration nach einem PUT (`onTripUpdate`) überschreibt noch nicht gespeicherte Eingaben des **anderen**
  Abschnitts nicht (Read-Modify-Write mit Merge nach CLAUDE.md; Feldmengen disjunkt nach `pickEigenfelder`).

### 6. Vorschau-Rückbau — Frontend

Entfallen: Hub-Panel `vorschau` (TripTabs, CompareTabs), `shared/PreviewTab.svelte`, `shared/previewLoader.ts`,
Aktion `preview` in `shared/subscriptionActions.ts` samt Einträgen in `routes/trips/+page.svelte`,
`routes/compare/+page.svelte` und Mobil-ActionSheet, Cockpit „Vorschau prüfen →" (`routes/+page.svelte`),
CompareTabs-Sprunglink, HubOverview „Vorschau öffnen", die Funktion für `GET /api/briefings/{id}/preview` in
`lib/api.ts` (~295-310) samt Typen. Nach PO-Entscheid 2026-10-22 (F003) entfallen außerdem die danach
verwaisten Reste: `molecules/CompareChatBubble.svelte`, `molecules/CompareChannelSwitch.svelte` (samt
Barrel-Export), `premiumSmsPreviewNote` in `compare/subscriptionHelpers.ts`, `langlaeufer.compareVorschau` +
`ZEITLIMIT_COMPARE_VORSCHAU_MS` in `lib/api.ts`; `preview/SmsPhoneFrame.svelte`, `EmailIframe` und
`previewHelpers.ts` hingen ausschließlich am Vorschau-Reiter und sind mit ihm entfallen. **Bleibt:** nur die
Alarm-Vorschau (`POST /api/briefings/{id}/alert-preview`).

### 7. Vorschau-Rückbau — Backend

- **Go:** Route `r.Get("/api/briefings/{id}/preview", …)` (`internal/router/router.go:~299`) und
  `BriefingPreviewHandler` (`internal/handler/briefing_preview.go`) entfernen. `briefingPreviewTarget` **bleibt**
  (genutzt von `BriefingAlertPreviewHandler`). Tests `briefing_preview_test.go` (nur Vorschau-Teile),
  `internal/router/preview_proxy_targets_test.go`, `internal/router/testdata/python_preview_routes.json` nachziehen.
- **Python:** Endpoint `@router.get("/api/briefings/{entity_id}/preview")` in `api/routers/preview.py` (Stand vor #1743: ~155-195)
  entfernen, `BRIEFING_KINDS` nur entfernen, wenn danach unbenutzt. `PreviewService.render_all_channels`
  (`src/services/preview_service.py:~424`) entfernen, sofern danach unreferenziert; Hilfsfunktionen
  `_email_html_of` (wird auch an anderer Stelle benutzt, Zeile ~370) und `_telegram_body_of` (~422) nur
  entfernen, wenn ebenfalls unreferenziert — vor dem Löschen per Suche belegen.
  Nach PO-Entscheid 2026-10-22 (F003) entfallen außerdem die Routen ohne Aufrufer
  `POST /api/preview/compare/{id}`, `GET /api/preview/{trip}/email` und `GET /api/preview/{trip}/telegram`
  (Go-Proxy und Python). **Bleibt:** `GET /api/preview/{trip}/sms` als Messweg der Staging-Specs
  `metrik-abwahl-schreibt-alle-kanaele-durch` und `metrik-grundauswahl-schneidet-kanal` (SMS-Kurzform).
  Zusätzlich entfallen die toten Vorschau-Hüllen ohne Produktiv-Aufrufer: `ComparePreviewService.render_email_preview`,
  `.render_telegram_preview`, `.render_sms_preview`; `PreviewService.render_email_preview`, `.render_telegram_preview`;
  ebenso der `call_log`-Marker `"render_email_preview"` in `src/providers/call_log.py`. **Bleibt:**
  `PreviewService.render_sms_preview` (SMS-Route + Preflight-Skript), `ComparePreviewService.render_all_channels`
  (Rechen-Naht der Paritätstests „Vorschau = Versand"), `_load_preset`, `order_locations_by_ids` und
  `scripts/premium_sms_preflight_check.py` (unverändert); der Versand (`scheduler_dispatch_service`,
  `trip_report_scheduler`) bleibt unberührt. Tests auf die entfernten Hüllen ziehen auf
  `PreviewService._build_report` bzw. `ComparePreviewService.render_all_channels` um; Tests auf den
  call_log-Marker nutzen `render_sms_preview` als Marker. Ratsche `internal/router/core_auth_sweep_test.go`:
  gemessener Ist-Wert 24 → 21 (drei entfernte Go→Python-Proxies email/telegram/compare), Konstante
  `minPythonCallsReached` nach der Konvention „Ist-Wert − 3" auf 18.
- Einziger Aufrufer des Endpoints war `previewLoader.ts` (geprüft). Weitere Aufrufer wären in der
  Implementierung zu belegen; wird einer gefunden, bleibt der Endpoint und die Spec wird angepasst.
- `docs/reference/api_contract.md` und `tests/test_api_contract_drift.py` nachziehen.

### 8. Infobox-Typ ehrlich benennen

`shared/infoboxKeys.ts`: Der Typ `InfoboxReiter` (enthält `versand`, das kein Reiter mehr ist) wird zu
`InfoboxAbschnitt` umbenannt; Schlüssel `versand` bleibt als **Abschnitt** erhalten (Versand-Infobox beim
Anlegen über dem Versand-Abschnitt). Alle Importeure (`infoboxKey()`-Aufrufer, `infoboxTexte`-Tests,
Anlege-Editoren) ziehen nach; kein Name mit „Reiter" für Nicht-Reiter.

### 9. Anlege-Seiten

- „Fertig/Anlegen" ist freigeschaltet, sobald der letzte Schritt **Alarme** besucht ist; der Fortschrittszähler
  zählt keinen `versand`-Schritt. `anlegeLockEngine.ts`: TailIds ohne `versand`, `canFinish` auf `alarme`.
- Beide Anlege-Seiten haben denselben Aufbau. Trip: Standard-Versandzeiten, Vergleich: Standard-`schedule`
  (`compare-new/compareNewVorlage.ts`) werden **unabhängig davon** in den POST übernommen, ob der
  Versand-Abschnitt je berührt wurde. Der Server verlangt `schedule` beim Ortsvergleich (sonst 400
  `validation_error`).
- Speicher-Slot auf Anlege-Seiten: dort wird erst beim Anlegen gespeichert; kein Debounce-Autosave. In S3 per
  Test belegt (kein Autosave-Pfad vorhanden), nicht angenommen.

### 10. Totcode und Kommentare

Löschen: `trip-detail/PreviewCard.svelte`, `trip-detail/BriefingPreviewCard.svelte`,
`shared/layout-tab/LTComparePreview.svelte`, die Exporte in `trip-detail/index.ts`. Kommentar in
`WeatherMetricsTab.svelte` („Mail-Vorschau bleibt im Hub-Reiter Vorschau") korrigieren. Badge-Schlüssel und
Flush-Listen (`TripTabs.svelte`, `shared/corridor-editor/wertebereicheVergleichSpeicherung.ts:~252-257`
`SELBST_SPEICHERNDE_VERGLEICH_REITER`) ohne `versand`/`vorschau`; der Flush beim Reiterwechsel gilt künftig für
das Panel `wetter-metriken` als Ganzes (beide Besitzer).

## Expected Behavior

- **Input:** Aufruf von Trip-/Ortsvergleich-Hub, Anlege-Seiten, Listen, Cockpit, Alt-Links.
- **Output:** Fünf Reiter, Versand unten im Reiter Wetter-Metriken, Anlege-Kette ohne Versand, keine
  Vorschau-Aktionen, `GET /api/briefings/{id}/preview` nicht mehr vorhanden.
- **Side effects:** Adresszeile wird bei Alt-Kennungen einmal umgeschrieben; Speichern von Wetter-Metriken und
  Versand binnen 700 ms geht nie verloren; #1839 wird gegenstandslos. Keine Datenmigration (Reiter lebt nur in
  der URL, `report_config` unverändert).

## Acceptance Criteria

Alle ACs werden als Verhalten geprüft (Rendering, Funktionsausgabe, Netz-Körper), nicht als Dateiinhalt.
Pfade aus „Affected Files". Mutations-Gegenprobe pro Gruppe ist Pflicht (siehe Test Plan).

### Reiterleiste und Alt-Kennungen

- **AC-1:** Given ein geöffneter Trip-Hub, When die Seite rendert, Then zeigt die Reiterleiste genau diese fünf Reiter in dieser Reihenfolge: Übersicht, Etappen & Wegpunkte, Wetter-Metriken, Wertebereiche, Alarme — ohne „Versand" und ohne „Vorschau".
  - Test: Hub gemountet, sichtbare Reiter-Beschriftungen und Panel-testids auslesen.

- **AC-2:** Given ein geöffneter Ortsvergleich-Hub, When die Seite rendert, Then zeigt die Reiterleiste genau Übersicht, Orte, Wetter-Metriken, Wertebereiche, Alarme in dieser Reihenfolge — ohne „Versand" und ohne „Vorschau"; die Mobil-Leiste (`MTabBar`) zeigt dieselben fünf Einträge.
  - Test: Hub in Desktop- und Mobil-Breite mounten; Reiter-Beschriftungen vergleichen.

- **AC-3:** Given ein Link `?tab=versand` oder `?tab=briefings` (Trip UND Ortsvergleich), When der Hub öffnet, Then ist der Reiter Wetter-Metriken aktiv, die Adresszeile wird genau einmal (ohne zusätzlichen Verlaufseintrag) auf `?tab=wetter-metriken#versand` umgeschrieben und der Versand-Abschnitt ist sichtbar.
  - Test: `resolveTab`/`bereinigteTabAdresse` je kind mit beiden Alt-Kennungen; Hub-Mount prüft aktiven Reiter, Adresse und Sichtbarkeit des Abschnitts.

- **AC-4:** Given ein Link `?tab=vorschau` oder `?tab=preview` (Trip UND Ortsvergleich), When der Hub öffnet, Then ist die Übersicht aktiv und die Adresszeile wird einmal auf `?tab=uebersicht` bereinigt — kein Leerlauf, keine Fehlerseite.
  - Test: `resolveTab`/`bereinigteTabAdresse` je kind; Hub-Mount.

- **AC-5:** Given die übrigen bereits gültigen Alt-Kennungen (`overview`, `stages`, `weather`, `alerts`, `idealwerte`, `layout`), When ein Hub sie öffnet, Then lösen sie unverändert auf (keine Regression gegenüber #2287).
  - Test: Tabelle der Alt-Kennungen je kind gegen erwartete Auflösung.

### Versand unter Wetter-Metriken

- **AC-6:** Given der Reiter Wetter-Metriken im Trip-Hub, When er angezeigt wird, Then steht darunter der Versand-Abschnitt (Versandzeiten und Kanäle E-Mail, Telegram, SMS, Premium-SMS) mit Anker `#versand`, und „Zeitplan bearbeiten →" (Übersicht) öffnet `?tab=wetter-metriken#versand` und scrollt dorthin.
  - Test: Hub mit Trip-Fixture mounten; Abschnitt vorhanden; Link-Ziel und Sprung prüfen.

- **AC-7:** Given der Reiter Wetter-Metriken im Ortsvergleich-Hub, When er angezeigt wird, Then steht darunter derselbe Versand-Abschnitt inklusive der Aktivierungs-Karte (Pausieren/Aktivieren), und Pausieren bzw. Aktivieren wirkt wie vorher (Backend-Status ändert sich, Karte zeigt neuen Zustand).
  - Test: Hub gemountet; Klick auf Pausieren/Aktivieren; Netz-Körper und Kartenzustand.

- **AC-8:** Given die Kombination „Wetter-Metriken + Versand", When Trip-Hub, Ortsvergleich-Hub, `/trips/new` und `/compare/new` sie einsetzen, Then ist es **derselbe** Baustein `shared/WetterMetrikenVersandPanel` mit `context="route"|"vergleich"` — der Compare-Hub rendert dieselbe Struktur (Wetter-Metriken, Abschnitt `#versand`) wie der Trip-Hub, abgesehen von der Aktivierungs-Karte und den Orte-spezifischen Inhalten.
  - Test: Struktur-Vergleich der gerenderten Abschnittsfolge je context aus dem gemounteten Baustein (kein Quelltext-Lesen).

- **AC-9:** Given ein Ortsvergleich mit Link `?tab=wetter-metriken#versand`, When die Seite lädt, Then erscheint der Versand-Abschnitt erst mit den gespeicherten Werten (Zeiten, Kanäle) und nicht mit Platzhaltern; ein Autosave schreibt nie Platzhalterwerte.
  - Test: Compare-Hub mit verzögerter Hydration mounten; erst nach Hydration sind die Werte sichtbar; es wird kein PUT mit Platzhaltern gesendet.

### Speicher-Slot (Datenverlust)

- **AC-10:** Given das Panel „Wetter-Metriken + Versand" im **Trip-Hub** und im **Ortsvergleich-Hub**, When ein Nutzer eine Wetter-Metrik ändert und binnen 700 ms eine Versandzeit ändert, Then enthalten die PUT-Körper im Backend **beide** Änderungen und die UI zeigt nach Re-Hydration beide Werte.
  - Test: Beide Bausteine gemountet (nicht nur der Store); Fake-Backend zeichnet PUT-Körper auf; in beiden contexts.

- **AC-11:** Given dasselbe Panel, When die Reihenfolge umgekehrt wird (erst Versandzeit, binnen 700 ms danach Wetter-Metrik), Then gehen ebenfalls beide Änderungen im Backend ein und werden angezeigt.
  - Test: wie AC-10, umgekehrte Reihenfolge, beide contexts.

- **AC-12:** Given zwei Besitzer im `saveController`, When Besitzer A `cancel(A)` aufruft, Then wird nur der Slot von A verworfen; ein wartender Slot von B wird weiterhin gesendet.
  - Test: Store-Test mit zwei Besitzern und Fake-Timer; nach `cancel(A)` wird B gesendet, A nicht.

- **AC-13:** Given ein ungespeicherter Wert im Abschnitt Versand, When der Wetter-Metriken-Teil ein PUT abschließt und die Seite den Trip/Vergleich neu hydriert, Then überschreibt die Re-Hydration den ungespeicherten Versand-Wert nicht (und umgekehrt).
  - Test: Panel gemountet; Versandwert ändern, Wetter-PUT abschließen lassen, Re-Hydration auslösen; Versandwert bleibt und wird anschließend gespeichert.

- **AC-14:** Given `WeatherMetricsTab` mit seinen zwei eigenen Speicherwegen (Auto-Save und nur-`report_config`-Save), When beide binnen 700 ms ausgelöst werden, Then gehen beide Änderungen ins Backend (behebt den schon bestehenden Trip-internen Verlust).
  - Test: nur Wetter-Metriken-Baustein gemountet; zwei Änderungen verschiedener Wege; beide im PUT.

- **AC-15:** Given eine Speicher-Anzeige der Seite, When zwei Besitzer nacheinander speichern, Then zeigt die Anzeige „Gespeichert" erst, wenn **beide** Schreiber erfolgreich waren, und bei Fehler eines Schreibers „Fehler" statt „Gespeichert".
  - Test: Panel gemountet; ersten PUT scheitern lassen; Anzeige-Zustand.

### Eine Quelle der Reiterfolge und Anlege-Seiten

- **AC-16:** Given die exportierten Ableitungsfunktionen aus `shared/subscriptionTabs.ts` (Hub-Leiste je kind, Anlege-Kette je kind), When ein Test ihre Ausgaben vergleicht, Then sind die Reiter ab `wetter-metriken` in allen vier Ketten (Trip-Hub, Vergleichs-Hub, Trip-Anlegen, Vergleich-Anlegen) nach Kennung, Label und Reihenfolge identisch.
  - Test: Funktionsausgaben vergleichen (kein Quelltext-Lesen).

- **AC-17:** Given die Anlege-Kette je kind, When sie abgeleitet wird, Then lautet sie für Trip `route · etappen · wegpunkte · wetter-metriken · wertebereiche · alarme` und für Vergleich `vergleich · orte · wetter-metriken · wertebereiche · alarme`; anlege-eigen sind nur Kopf-Schritte, `lockHint` und `optional`.
  - Test: Ausgabe der Ableitung je kind gegen die erwartete Folge.

- **AC-18:** Given die eine Definition, When ein Test in einer **ersetzten Kopie der Definition** einen Reiter entfernt (Testdouble nur der Eingabe, nicht des Prüflings), Then verschwindet er in allen vier abgeleiteten Ketten, ohne dass eine zweite Liste angepasst wird.
  - Test: Ableitungsfunktionen mit injizierter Eingabe; vier Ausgaben prüfen. Beweist, dass keine Zweitliste existiert (nicht durch Quelltext-Suche, sondern durch Wirkung).

- **AC-19:** Given `/trips/new` und `/compare/new`, When sie gerendert werden, Then gibt es keinen Schritt „Versand"; der Versand-Inhalt steht unten im Schritt „Wetter-Metriken" (Baustein aus AC-8), der Fortschrittszähler zählt ihn nicht als eigenen Schritt, und „Fertig/Anlegen" wird freigeschaltet, sobald „Alarme" besucht ist (nicht früher).
  - Test: Anlege-Editoren gemountet; Schritte durchklicken; Zähler und Knopf-Zustand nach jedem Schritt.

- **AC-20:** Given `/compare/new`, When ein Nutzer einen Ortsvergleich anlegt, ohne je zum Versand-Abschnitt zu scrollen oder ihn zu berühren, Then enthält der POST einen gültigen Standard-`schedule` und das Anlegen gelingt (Server antwortet nicht mit 400).
  - Test: Editor gemountet; Schritte bis Alarme besuchen; Anlegen; aufgezeichneter POST-Körper enthält `schedule`. Ergänzend gegen Staging mit echtem Server (kein 400).

- **AC-21:** Given `/trips/new`, When ein Nutzer einen Trip anlegt, ohne den Versand-Abschnitt zu berühren, Then enthält der POST die Standard-Versandzeiten und das Anlegen gelingt.
  - Test: wie AC-20 für Trip.

- **AC-22:** Given die Infobox-Schlüssel, When der Versand-Abschnitt beim Anlegen angezeigt wird, Then steht die Versand-Infobox über dem Abschnitt (nicht beim Bearbeiten) und der Typ heißt `InfoboxAbschnitt`; es existiert kein Typ mit „Reiter" im Namen, der `versand` enthält.
  - Test: Anlege-Editor zeigt Infobox, Hub nicht (Verhalten); Typ-Name wird durch `svelte-check` bewacht, nicht durch Quelltext-Lesen.

### Sprunglinks, Badges, Aktionen

- **AC-23:** Given Cockpit-Schnellaktionen und `TRIP_TAB_MAP`, When ein Link mit alter Kennung (`versand`, `vorschau`) gesucht wird, Then gibt es keinen: Versand-Aktionen führen zu `?tab=wetter-metriken#versand`, es gibt keine Vorschau-Schnellaktion mehr.
  - Test: Cockpit gemountet; alle Aktions-Ziele auslesen; jede `?tab=`-Kennung muss über `resolveTab` **ohne** `legacy` auflösen.

- **AC-24:** Given „Setup abschließen" auf der Ortsvergleich-Detailseite, When der Nutzer darauf klickt, Then öffnet es `?tab=wetter-metriken#versand`.
  - Test: Seite gemountet; Link-Ziel und Sprung.

- **AC-25:** Given alle Sprunglinks (HubOverview, CompareTabs, Cockpit, Listen), When ihre Ziele geprüft werden, Then löst jede Kennung ohne Legacy-Umweg auf (nur neue Kennungen).
  - Test: Test `reiter_sprunglinks_nur_neue_kennungen` wird angepasst und deckt die neuen Ziele ab.

- **AC-26:** Given die Badges/Flush-Logik von `TripTabs` und `CompareTabs`, When Reiter gewechselt werden, Then gibt es keine Einträge für `versand`/`vorschau`; beim Wechsel weg von `wetter-metriken` werden ausstehende Speicher-Slots **beider** Besitzer gesendet, bevor der neue Reiter erscheint.
  - Test: Hub gemountet; Änderung, sofort Reiterwechsel; PUT-Körper enthält beide Änderungen.

- **AC-27:** Given Trip-Liste, Ortsvergleich-Liste und Mobil-ActionSheet, When die Aktionen eines Eintrags angezeigt werden, Then gibt es keine Aktion „Vorschau"; die übrigen Aktionen bleiben unverändert in Reihenfolge und Wirkung.
  - Test: Aktionsmodell-Ausgabe je kind; Listen gemountet.

### Vorschau-Rückbau

- **AC-28:** Given die Übersicht (HubOverview) und das Cockpit, When sie gerendert werden, Then gibt es weder „Vorschau öffnen" noch „Vorschau prüfen →".
  - Test: Komponenten gemountet; Link-Texte und -Ziele.

- **AC-29:** Given die Alarm-Vorschau im Reiter Alarme, When der Nutzer sie nutzt, Then funktioniert sie unverändert (`POST /api/briefings/{id}/alert-preview`); weitere Kanal-Vorschauen (Chat-Blase, SMS-Rahmen, Kanal-Umschalter) gibt es nach PO-Entscheid 2026-10-22 nicht mehr.
  - Test: bestehende Tests der Alarm-Vorschau laufen unverändert grün; `previewVerdrahtungHubs.test` behält/verschiebt den Alarm-Vorschau-Teil; im Wetter-Metriken-Reiter gemountet gibt es keine Chat-Blase, keinen SMS-Rahmen und keinen Kanal-Umschalter.

- **AC-30:** Given die Go-API, When `GET /api/briefings/{id}/preview` aufgerufen wird, Then antwortet sie mit 404 bzw. 405 (Route existiert nicht), während `POST /api/briefings/{id}/alert-preview` unverändert mit 200 antwortet.
  - Test: Go-Router-Test mit echtem Router; zwei Nutzer, Alarm-Vorschau für fremde ID bleibt abgewiesen (Mandantentrennung unverändert).

- **AC-31:** Given der Python-Core und die Go-API, When `GET /api/briefings/{id}/preview`, `GET /api/preview/{trip}/email`, `GET /api/preview/{trip}/telegram` oder `POST /api/preview/compare/{id}` aufgerufen wird, Then antworten sie 404/405; `GET /api/preview/{trip}/sms` antwortet weiterhin; die toten Hüllen `ComparePreviewService.render_email_preview`/`.render_telegram_preview`/`.render_sms_preview` und `PreviewService.render_email_preview`/`.render_telegram_preview` existieren nicht mehr; `PreviewService.render_sms_preview`, `ComparePreviewService.render_all_channels` und `scripts/premium_sms_preflight_check.py` laufen unverändert.
  - Test: FastAPI-Testclient und Go-Router-Test mit echtem Router (404/405 bzw. SMS-Route 200); Import-/Aufruf-Test des Preflight-Skripts (`--collect-only`-sicher, ohne Versand); Paritätstests „Vorschau = Versand" laufen über `render_all_channels`.

- **AC-32:** Given die Frontend-API und die Vertragsdokumentation, When der Rückbau abgeschlossen ist, Then gibt es keinen Client-Aufruf und keinen Vertragseintrag für den Vorschau-Endpoint mehr (`lib/api.ts`, `docs/reference/api_contract.md`, Drift-Test `test_api_contract_drift.py` grün).
  - Test: Drift-Test; Frontend-Typprüfung (`svelte-check`) ohne Rest-Verweise.

### Aufräumen (Alt-Reste)

- **AC-33:** Given der Projektstand nach Lieferung, When nach `PreviewCard`, `BriefingPreviewCard`, `LTComparePreview`, `PreviewTab`, `previewLoader`, `InfoboxReiter` und Endpoint-Aufrufen für `/api/briefings/{id}/preview` gesucht wird, Then gibt es keine Verweise mehr in Produktcode und Tests (außer Archiv-Dokumentation).
  - Test: `svelte-check`, Kompilierung (`go build`, `go vet`), `pytest --collect-only` ohne Importfehler; zusätzlich ein Such-Schritt im Adversary (kein Dateiinhalt-Test als Verhaltensnachweis).

- **AC-34:** Given Referenzdoku und Altspecs, When sie gelesen werden, Then sind `docs/reference/navigation.md` und `docs/features/architecture.md` auf die fünf Reiter und `#versand` aktualisiert, und die abgelösten ACs der Specs `feat_2287_tab_kennungen` (AC-4, AC-9), `shared_preview_tab` (AC-8, AC-9 bzw. ganz), `feat_2278_aktionsmodell` (AC-2) und `mobile_tab_leisten_mtabbar` (AC-1-Beispiel) sind als „abgelöst durch #1743" markiert.
  - Test: `# doc-compliance-test` für die Doku (bewusst Dokument-Prüfung); Verhalten ist durch AC-1 bis AC-33 bewacht.

## Affected Files

**Frontend (REPO-relative Pfade):**

- `frontend/src/lib/stores/saveStatusStore.svelte.ts` — MODIFY (Besitzer-Schlüssel `schedule`/`cancel`)
- `frontend/src/lib/components/shared/subscriptionTabs.ts` — MODIFY (5 Reiter, Anlege-Ableitung, LEGACY, Anker)
- `frontend/src/lib/components/shared/WetterMetrikenVersandPanel.svelte` — CREATE (geteilter Panel-Baustein)
- `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` — MODIFY (Besitzer-Schlüssel, Kommentar)
- `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts` — MODIFY (Besitzer)
- `frontend/src/lib/components/shared/versandVergleichSpeicherung.ts` — MODIFY (Besitzer)
- `frontend/src/lib/components/shared/VersandTab.svelte` — MODIFY (Einsatz im Panel, Aktivierungs-Karte, Anker)
- `frontend/src/lib/components/trip-detail/BriefingScheduleTab.svelte` — MODIFY (Besitzer)
- `frontend/src/lib/components/trip-detail/TripTabs.svelte` — MODIFY (Panel, Leiste, Badges, Flush)
- `frontend/src/lib/components/compare/CompareTabs.svelte` — MODIFY (Panel, Hydration, Sprunglinks, Vorschau-Panel raus)
- `frontend/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts` — MODIFY (Selbstspeicherer-Liste)
- `frontend/src/lib/components/mobile/MTabBar.svelte` — MODIFY (nur falls eigene Liste/`versand`/`vorschau` vorhanden)
- `frontend/src/lib/components/trip-new/TripNewEditor.svelte` — MODIFY
- `frontend/src/lib/components/trip-new/tripNewLogic.ts` — MODIFY
- `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` — MODIFY
- `frontend/src/lib/components/compare-new/compareNewVorlage.ts` — MODIFY (Default-`schedule` unabhängig vom Versand-Abschnitt)
- `frontend/src/lib/components/shared/anlegeLockEngine.ts` — MODIFY
- `frontend/src/lib/components/shared/infoboxKeys.ts` — MODIFY (`InfoboxAbschnitt`) und Importeure
- `frontend/src/lib/components/shared/subscriptionActions.ts` — MODIFY (Aktion `preview` raus)
- `frontend/src/routes/trips/+page.svelte`, `frontend/src/routes/compare/+page.svelte` — MODIFY (Listen-Aktion)
- `frontend/src/routes/+page.svelte` — MODIFY (`TRIP_TAB_MAP`, Schnellaktionen, Vorschau prüfen)
- `frontend/src/routes/compare/[id]/+page.svelte` — MODIFY („Setup abschließen")
- `frontend/src/routes/trips/[id]/+page.svelte` — MODIFY (Tab-Defaults, falls Referenzen auf `versand`/`vorschau`)
- `frontend/src/lib/components/trip-detail/HubOverview.svelte` — MODIFY
- `frontend/src/lib/components/trip-detail/index.ts` — MODIFY (Exporte)
- `frontend/src/lib/api.ts` — MODIFY (Vorschau-Aufruf und Typen raus, ~295-310)
- `frontend/src/lib/components/shared/PreviewTab.svelte` — DELETE
- `frontend/src/lib/components/shared/previewLoader.ts` — DELETE
- `frontend/src/lib/components/trip-detail/PreviewCard.svelte` — DELETE
- `frontend/src/lib/components/trip-detail/BriefingPreviewCard.svelte` — DELETE
- `frontend/src/lib/components/shared/layout-tab/LTComparePreview.svelte` — DELETE

**Go:**

- `internal/router/router.go` — MODIFY (Route entfernen)
- `internal/handler/briefing_preview.go` — MODIFY (`BriefingPreviewHandler` raus, `briefingPreviewTarget` bleibt)
- `internal/handler/briefing_preview_test.go` — MODIFY
- `internal/router/preview_proxy_targets_test.go` — MODIFY
- `internal/router/testdata/python_preview_routes.json` — MODIFY
- `internal/router/core_auth_sweep_test.go` — MODIFY (F003: Ratsche `minPythonCallsReached` auf 18 = gemessener Ist-Wert 21 − 3)

**Python:**

- `api/routers/preview.py` — MODIFY (Endpoint, ggf. `BRIEFING_KINDS`)
- `src/services/preview_service.py` — MODIFY (`render_all_channels`, ggf. Hilfsfunktionen; F003: `render_email_preview`/`render_telegram_preview` raus, `render_sms_preview` bleibt)
- `src/services/compare_preview_service.py` — MODIFY (F003: `render_email_preview`/`render_telegram_preview`/`render_sms_preview` raus, `render_all_channels` bleibt)
- `src/providers/call_log.py` — MODIFY (F003: Marker `"render_email_preview"` entfällt)

**Tests (REPO-relativ):**

- NEU: `frontend/src/lib/stores/__tests__/saveStatusStoreBesitzer.test.ts` (AC-12), `frontend/src/lib/components/shared/__tests__/wetter_metriken_versand_panel_speicherung.test.ts` (AC-10, 11, 13, 14, 15), `frontend/src/lib/components/shared/__tests__/reiterfolge_eine_quelle.test.ts` (AC-16 bis 18), `frontend/src/lib/components/shared/__tests__/wetter_metriken_versand_panel_paritaet.test.ts` (AC-8)
- ANPASSEN (Reiter-Fixierungen auf fünf Reiter/neue Ziele): `subscription_tabs_resolve`, `hub_reiter_gemeinsame_aufloesung`, `reiter_sprunglinks_nur_neue_kennungen`, `wetterMetrikenTabRegistration`, `versand_panel_ohne_wrapper_div`, `issue_1273_s3_redirect_links`, `tripMehrreiterPruefstand`, `deadTripOverviewComponentsRemoved`, `aktionsmodell_seiten_bindung`, `alarme_vergleich_flush_beim_reiterwechsel`, `versand_vergleich_reiterwechsel_verliert_nichts`, `anlege_reiter_kennungen_gleich`, `anlege_reiterleiste_trip_vergleich_paritaet`, `anlege_weiter_knopf_zielt_auf_existierenden_reiter`, `anlege_lock_engine`, `compare_anlege_freischaltung`, `tripNewLogic.test`, `trip_new_reiterleiste_besuchs_flags`, `trip_new_zeitplan_tab_nutzt_geteilten_versand_baustein`, `trip_new_mail_inhalt_karte_genau_eine_instanz`, `trip_new_versandkanaele_unabhaengig_von_metriken`, `trip_new_wertebereiche_reiter`, `infobox_nur_beim_anlegen`, `infoboxTexte`, `standardwerte_knopf_geteilt`, `standardwerte_gate`, `begriff_erklaerung_infobox_bausteine`, `versand_tab_meldet_aenderungen_reaktiv`, `previewVerdrahtungHubs.test` (Alarm-Vorschau-Teil bleibt/zieht um), `apiZeitlimit.test.ts` (Abschnitt Briefing-Vorschau ~426-473 raus, Rest bleibt), `compareReiterAufbauPruefstand.ts`, `compare_reiter_nutzlast_nur_eigene_felder` — alle unter `frontend/src/lib/components/**/__tests__/` bzw. wo sie heute liegen (genaue Pfade per Suche in S2-S4).
- Python-Tests, die die entfernten Hüllen (`render_email_preview`/`render_telegram_preview`/`render_sms_preview` von `ComparePreviewService`, `render_email_preview`/`render_telegram_preview` von `PreviewService`, call_log-Marker `"render_email_preview"`) nutzen — MODIFY (F003: umziehen auf `PreviewService._build_report` bzw. `ComparePreviewService.render_all_channels`; Marker-Tests nutzen `render_sms_preview`).
- LÖSCHEN: `previewTab.test.ts`, `previewLoader.test.ts`, `compare_preview_channel_switch.test.ts` (nur der Briefing-Vorschau-Teil; übrige Fälle falls vorhanden bleiben).
- Playwright ANPASSEN: `frontend/e2e/trip-detail-tabs.spec.ts`, `hub-reiter-alt-kennungen-umleitung.spec.ts`, `issue-616-trip-one-surface.spec.ts`, `versand-tab.spec.ts`, `versand-tab-vergleich.spec.ts`, `issue-758-save-indicator.spec.ts`, `versandzeit-stundenwahl.spec.ts`, `compare-hub-briefing-times.spec.ts`, `bug-626-compare-menu-actions.spec.ts`, `begriff-erklaerung.spec.ts`, `kanal-grenzen-ortsvergleich.staging.spec.ts` (Briefing-Vorschau-Teile raus); LÖSCHEN (prüften nur die entfallene Briefing-Vorschau): `ausblick-einfach-wirkt.staging.spec.ts`, `trip-preview-thunder-origin.staging.spec.ts`; `preview-tab-gleiche-anordnung.spec.ts` (LÖSCHEN, prüft den entfallenen Reiter), `email-preview-header.spec.ts` (prüfen).
- LÖSCHEN Playwright: `frontend/e2e/issue-736-tabs-reorg.spec.ts` (widerspricht direkt: Kanal-Schalter NICHT in Wetter-Metriken).
- `.github/ci_e2e_specs.txt` — MODIFY (gelöschte/umbenannte Specs)
- Python: `tests/integration/test_briefing_preview_user_isolation.py`, `tests/integration/test_briefing_preview_bundle.py`, `tests/integration/test_briefing_preview_kind_und_demo.py` — LÖSCHEN bzw. auf verbleibendes Verhalten reduzieren; `tests/test_api_contract_drift.py` — MODIFY; `tests/tdd/test_issue_1069_tier_channel_gating.py` — PRÜFEN (`?tab=briefings` läuft über LEGACY weiter).

**Doku/Specs:**

- `docs/reference/navigation.md`, `docs/reference/api_contract.md`, `docs/features/architecture.md` (~1209) — MODIFY
- `docs/specs/modules/feat_2287_tab_kennungen.md`, `docs/specs/modules/shared_preview_tab.md`, `docs/specs/modules/feat_2278_aktionsmodell.md`, `docs/specs/modules/mobile_tab_leisten_mtabbar.md` — MODIFY (abgelöste ACs markieren)

## Test Plan

**Neu (Kern, deterministisch, kein Mock-Theater):**

1. **Store-Test Besitzer** — zwei Besitzer, Fake-Timer; Flush des fremden Slots vor eigenem Slot; `cancel(owner)` löscht nur eigenen (AC-12). Dazu Mutations-Gegenprobe: `cancel` ignoriert den Besitzer → Test muss rot werden.
2. **Panel-Speicher-Test (gemountet, beide Bausteine, beide contexts)** — Fake-Backend zeichnet PUT-Körper; Szenarien AC-10/11/13/14/15. Die Zusicherung wird dort geprüft, wo sie wirkt (gemountetes Panel), nicht nur am Store. Mutations-Gegenprobe: Schlüssel eines Aufrufers auf denselben Besitzer setzen → mindestens ein Test rot.
3. **Reiter-Quelle-Test** — Funktionsausgaben (AC-16/17/18).
4. **Panel-Parität** — Abschnittsfolge je context (AC-8).
5. **Anlegen ohne Versand-Berührung** — POST-Körper enthält Standard-`schedule` bzw. Standard-Versandzeiten (AC-20/21). Ein Live-Nachweis gegen Staging (kein 400) ergänzt in der Live-Schicht.
6. **Go-Router-Test** — `GET …/preview` nicht vorhanden; `POST …/alert-preview` unverändert; zwei Nutzer.
7. **Python/Go** — Briefing-Vorschau- und Kanal-Vorschau-Endpoints weg (SMS-Vorschau bleibt), tote Vorschau-Hüllen weg, Paritätstests über `render_all_channels`, Preflight-Skript importierbar.

**Angepasst:** Reiter-Fixierungen (~30 Unit-Tests, ~13 Playwright-Specs) auf die fünf Reiter und neue Sprungziele. Veraltetes Verhalten wird angepasst oder gelöscht, nie rot liegengelassen.

**Gelöscht:** Tests des entfallenen Reiters/Loaders/Endpoints (Liste oben), `issue-736-tabs-reorg.spec.ts`, `preview-tab-gleiche-anordnung.spec.ts`.

**Live-Schicht (`/e2e-verify`):** Staging: Hub beider Entitäten, Alt-Links (`versand`, `briefings`, `vorschau`, `preview`), Metrik + Versandzeit binnen 700 ms ändern und Neuladen, Anlegen ohne Versand-Berührung; Briefing-Mail-Pfade sind inhaltlich unverändert (Validator-Pflicht nur falls Renderer-Dateien berührt werden — hier nicht erwartet).

**Mutations-Gegenprobe (Adversary, Pflicht):** (a) `schedule` ohne Flush des Fremd-Slots; (b) `cancel` ohne Besitzer; (c) Versand-Hydration an falschen Reiter; (d) Default-`schedule` nur setzen, wenn Abschnitt berührt; (e) `versand` in LEGACY auf `uebersicht`; (f) Zweitliste in einem Anlege-Editor. Jede Verfälschung muss mindestens einen benannten Test rot machen. Mutation nur per String-Ersetzung mit externer Sicherungskopie.

**Mandantentrennung:** Es entstehen keine neuen datenbewegenden Endpoints; verbleibende Alarm-Vorschau-Prüfung bleibt mit zwei Nutzern abgedeckt (AC-30).

## Known Limitations

- **Briefing-Vorschau je Kanal entfällt ersatzlos** (PO-Entscheid). Es gibt keinen Ort mehr, an dem das Briefing vorab je Kanal gesehen werden kann; es bleibt nur die Alarm-Vorschau im Reiter Alarme. Die früher hier genannten „Mini-Vorschauen" (Chat-Blase, SMS-Rahmen) existierten nur im Vorschau-Reiter und sind mit ihm samt Resten entfallen (F003, PO-Entscheid 2026-10-22). Eine Wiedereinführung müsste neu spezifiziert werden.
- **#1839 (Vorschau-502 nach 30 s)** wird gegenstandslos und ist **nach Lieferung mit Verweis auf #1743 zu schließen** (nicht vorher; erst nach Prod-Deploy und Selftest Exit 0).
- Der Reiter Wetter-Metriken wird länger (Versand unten angehängt); Orientierung über den Anker `#versand`.
- Lesezeichen mit `?tab=versand|briefings` landen auf Wetter-Metriken (mit Sprung zum Versand) statt auf einem eigenen Reiter.
- Falls sich ein weiterer Aufrufer von `GET /api/briefings/{id}/preview` findet (Inbound-Befehle, Tests mit Fachwert), bleibt der Endpoint bestehen; die Spec wird dann in /50 angepasst und die Abweichung begründet.
- Die Anlege-Seiten kennen den Speicher-Slot-Konflikt nach heutiger Analyse nicht (Speichern erst beim Anlegen); das wird in S3 per Test belegt, nicht nur angenommen.
- `MTabBar`: ob eine eigene Reiterliste existiert, ist in S3 zu prüfen; falls ja, wird sie entfernt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Kein ADR legt Reiterleiste oder Vorschau-Reiter fest (Analyse). Der Besitzer-Schlüssel im `saveController` ist ein Detail des bestehenden Autosave-Musters, keine Grundsatzentscheidung.

## Changelog

- 2026-10-22: Initial spec created (Issue #1743; PO-Entscheide 2026-10-22: Vorschau entfällt ersatzlos, Versand unter Wetter-Metriken, Anlege-Seiten gleich, Reiterfolge eine Quelle).
- 2026-10-22: F003: Mini-Vorschauen existierten nur im Vorschau-Reiter; PO-Entscheid: ersatzlos inkl. Reste. Entfallen zusätzlich `CompareChatBubble`, `CompareChannelSwitch`, `premiumSmsPreviewNote`, `langlaeufer.compareVorschau`/`ZEITLIMIT_COMPARE_VORSCHAU_MS` sowie im Backend `POST /api/preview/compare/{id}`, `GET /api/preview/{trip}/email|telegram`; `GET /api/preview/{trip}/sms` bleibt als Messweg der Staging-Specs, `ComparePreviewService`/`PreviewService` und `scripts/premium_sms_preflight_check.py` unverändert. Soll-Fassung AC-29: „Given die Alarm-Vorschau im Reiter Alarme, When der Nutzer sie nutzt, Then funktioniert sie unverändert (POST /api/briefings/{id}/alert-preview); weitere Kanal-Vorschauen gibt es nach PO-Entscheid 2026-10-22 nicht mehr." Soll-Fassung AC-31: `GET /api/briefings/{id}/preview`, `GET /api/preview/{trip}/email|telegram` und `POST /api/preview/compare/{id}` antworten 404/405; `GET /api/preview/{trip}/sms` bleibt als Messweg; `ComparePreviewService`/`PreviewService` und `scripts/premium_sms_preflight_check.py` laufen unverändert. (Beide AC-Texte selbst sind Spec-Freeze — Übernahme erst nach erneuter Freigabe.) F001: Panel-Tests „ändern und binnen 700 ms zurücksetzen" je Kontext und Abschnitt ergänzt.
- 2026-10-22: Nachfreigabe F003: AC-29/AC-31, Dependencies, „Was der PO sieht" Punkt 3 auf PO-Entscheid nachgezogen; zusätzlich tote Vorschau-Hüllen (`ComparePreviewService.render_email_preview`/`.render_telegram_preview`/`.render_sms_preview`, `PreviewService.render_email_preview`/`.render_telegram_preview`) + call_log-Marker entfernt, Ratsche 18 (Ist-Wert 21 − 3). Die Übernahme der AC-Texte erfolgt damit jetzt.
