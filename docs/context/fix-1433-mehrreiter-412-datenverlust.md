# Context: fix-1433-mehrreiter-412-datenverlust

## Request Summary
Issue #1433: Nach einem `412` (ETag-Konflikt) in einem Reiter der Trip-Seite kann ein anschließendes Speichern aus einem anderen Reiter still Daten überschreiben. Ziel: kein stiller Datenverlust mehr im Mehrreiter-Fall nach Konflikt.

## Korrekturen an den Prämissen des Tickets (Stand origin/main 2026-10-01)
- Zeilenverweise veraltet: `api.ts:73` → **`frontend/src/lib/api.ts:136`** (`discardEtag` bei 412); `+page.svelte:39` → **`:43`** (`tripSaveCtl`).
- Das Beispiel `AlertsTab.svelte` ist **nicht mehr eingehängt** (toter Code, ersetzt durch CorridorEditor/AlarmeTab, s. `TripTabs.svelte:9-10`). Ebenfalls tot: `briefings-tab/BriefingsTab.svelte`, `trip-detail/WaypointsPanel.svelte`.
- Das Fund-Artefakt `docs/artifacts/fix-1395-s4-nochmal-speichern/adversary-dialog.md` existiert nirgends (auch nicht in git-History) — einzige Quelle ist der Issue-Body.
- **Präzisierung des Verlusts:** Die abgelehnte Änderung von Reiter A erreichte den Server nie. Reiter B überschreibt auf dem Server die **fremde Änderung, die den 412 ausgelöst hat** (jeder veraltete Top-Level-Schlüssel von `display_config`/`report_config`, den B mitsendet). Reiter As eigene Änderung geht in der **UI** verloren (s. Zweitbefund).

## Zweitbefund: geteilter Controller verschluckt den Konflikt
- Alle Reiter teilen `tripSaveCtl` (`routes/trips/[id]/+page.svelte:43`, `createSaveStatus` in `lib/stores/saveStatusStore.svelte.ts`).
- Speichert Reiter B (`schedule()` :184 / `doSave` :120-143), springt der Zustand `conflict → saving → idle`; „Nochmal speichern" (`ui/SaveIndicator.svelte:44`, `retryConflict` :152-164) verschwindet, `_lastFailed` verwaist.
- Reiterwechsel unmountet Reiter A (`TripTabs.svelte:196`, nur aktiver Reiter gerendert); Flush beim Wechsel (:170-176) nur bei `hasPending` — nach Fehler false.

## Weitere Lücken ohne If-Match
- `trip-detail/BriefingScheduleTab.svelte:41-48,88-92` (Versand-Zeitplan) speichert **immer mit `keepalive: true`** ⇒ nie If-Match, nie serialisiert (`api.ts:183-185`); aktualisiert `trip` lokal statt aus Server-Antwort. Widerspricht Kommentar `api.ts:178` und S3-Spec Known Limitations („einziger Aufrufer = Unload-Flush").
- Pausieren/Archivieren: `routes/trips/[id]/+page.svelte:106` PATCH `/state` (raw fetch, kein If-Match, bewusst AC-15) und danach `discardEtag` (:137) ⇒ öffnet ebenfalls ein Fenster für einen unbedingten Schreibvorgang.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/etagRegistry.ts` | ETag-Registry: `knownEtags` :13, `discardEtag` :117, `adoptEtagFromPageLoad` :107 (re-armiert nach Discard nicht), `enqueueTripWrite` :151 |
| `frontend/src/lib/api.ts` | `send()` :72, If-Match :88/:98, **412 → discardEtag :136**, keepalive-Bypass :183-185, `refreshResourceEtag` ~:228 |
| `frontend/src/lib/stores/saveStatusStore.svelte.ts` | `'conflict'`-Zustand, `doSave`, `retryConflict`, `schedule` (ein Debounce-Slot) |
| `frontend/src/routes/trips/[id]/+page.svelte` | geteilter `tripSaveCtl`, `handleTripUpdate` :226 ersetzt `trip` komplett, `/state` + discard |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Reitermontage :196-235, `handleActivityChange` :188 (PUT `{activity}`, kein try/catch) |
| `frontend/src/lib/components/shared/AlarmeTab.svelte` :378-392 + `shared/alarme-tab/alarmeDeliveryPayload.ts` :106-135 | PUT mit **`display_config: {...currentDisplayConfig, metric_alert_levels}`** |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte` :265-274 (Mobile :226-235) | PUT `{corridors, display_config: trip.display_config}` — ganze display_config |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` :932-956, :1008-1041 + `tripSpeicherung.ts` | PUT `/weather-config` mit `{...display_config, …}` + PUT trip mit vollem `report_config` |
| `frontend/src/lib/components/trip-detail/BriefingScheduleTab.svelte` + `shared/VersandTab.svelte` :197-231 | PUT `{report_config}` mit keepalive (ohne If-Match) |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` :45 | PUT `{name}`, an Controller vorbei |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` :167/:190/:428 | PUT `{stages}` |
| `frontend/src/lib/components/shared/tripSpeicherung.ts` | `baueTripSpeicherung` :32 (Rumpf als Funktion = lazy body) |
| `internal/handler/trip.go` `UpdateTripHandler` :268 | Read-Modify-Write; If-Match-Prüfung :310; Lock :281 |
| `internal/handler/config_merge.go` :11-22 | `mergeConfigMap` = **einstufiger** Merge: Top-Level-Schlüssel überschreiben, Nested (z.B. `channel_layouts`, `metric_alert_levels`) als Ganzes ersetzt |
| `internal/handler/etag.go` `ifMatchAllows` :52-65 | fehlendes If-Match ⇒ akzeptiert; 412 ohne ETag-Header |
| `internal/handler/weather_config.go` ~:90/:105 | If-Match + mergeConfigMap auf display_config |

## Existing Patterns
- **Teilfeld-Payload je Reiter (Ortsvergleich, #2375/#2381):** `waehleEigenfelder` (`components/compare/compareEditorSave.ts:319`), `buildComparePresetPartialPayload` (:295); Feld-Eigentümer-Tabelle in `docs/specs/bugfix/compare_konfliktschutz_teilfelder.md` §2. Header sendet nur `{display_config:{region}}`. Die Spec überlässt `api.ts:136` explizit #1433. Trip-Seite hat dieses Muster **noch nicht**.
- Server-Merge ist schon einstufig ⇒ Teil-Payloads sind serverseitig bereits sicher.
- Serialisierung pro Ressource: `enqueueTripWrite`; Lazy-Body (`Rumpf` als Funktion) in `tripSpeicherung.ts`.
- Compare-Hub: eigener `hubSaveCtl` (`routes/compare/[id]/+page.svelte:70`), `enqueueHubWrite`/`hubPutQueue` in `CompareTabs.svelte:1016-1082`.
- Kein Trip-PATCH für Felder, kein „mit frischem Serverstand mergen"-Helfer.

## Dependencies
- Upstream: etagRegistry, api.ts `request/send`, saveStatusStore, Go `UpdateTripHandler` + `mergeConfigMap`, `/weather-config`.
- Downstream: alle Trip-Reiter (Alarme, Wertebereiche/Korridore, Wetter-Metriken, Versand, Etappen, Header, Aktivität), Pausieren/Archivieren, Listen-Seite (`routes/trips/+page.svelte:307`), `PUT /api/briefings/{id}?kind=route` (gleicher Handler), Python-Core-Schreiber (`briefings/<id>.json`: Telegram/SMS-Befehle, `skip_next`) als realistische 412-Quelle; Ortsvergleich teilt api.ts/Registry und die `shared/`-Reiter (Trip/Compare-Teilungsregel!).

## Existing Specs
- `docs/adr/0036-nebenlaeufigkeitsschutz-inhalts-fingerabdruck.md` — Fingerabdruck sha256 über ETag/If-Match; **nennt keinen Zeitpunkt, ab wann If-Match Pflicht wird**; nicht abgelöst.
- `docs/specs/modules/issue_1395_s2_etag_ifmatch.md` (Rollout „fehlt = akzeptiert", Known Limitations ~:353)
- `docs/specs/modules/issue_1395_s3_etag_registry.md` (Discard-Entscheidung :213ff, keepalive-Annahme :415ff — inzwischen falsch)
- `docs/specs/modules/issue_1395_s4_conflict_retry.md` (Retry, Known Limitations :305ff)
- `docs/specs/modules/issue_1395_s6_ortsvergleich_etag.md`, `speicherung_beim_neuladen.md` (#2317)
- `docs/specs/bugfix/compare_konfliktschutz_teilfelder.md` + `docs/context/fix-2375-compare-konfliktschutz.md` (Vorlage)
- `docs/context/fix-1395-s4-nochmal-speichern.md` :19/:32/:48 (Risiken bereits benannt)

## Existing Tests
- Frontend (`node --test`, kein Vitest): `lib/__tests__/apiTripEtagConflict.test.ts` (u.a. `test_afterDiscard_writeGoesThroughWithoutPrecondition` :261 — zementiert das heutige Verhalten), `apiKeepaliveSkipsIfMatch.test.ts`, `apiTripEtagHeaders.test.ts`, Harness `fakeTripServer.ts`; Compare-Konflikt-Tests `shared/__tests__/*_vergleich_konflikt_nochmal_speichern.test.ts`.
- Go: `internal/handler/trip_etag_ifmatch_test.go` (`NoIfMatch_Accepted` :110, `StaleIfMatch_Returns412` :143, …), `weather_config_etag_ifmatch_test.go`, `if_match_weak_etag_test.go`, `compare_preset_etag_ifmatch_test.go`, `briefing_*_etag_test.go`.
- **Lücke:** kein Test für „412 in Reiter A, danach Schreiben aus Reiter B" — weder veralteter Spread noch verschluckter Konfliktzustand.

## Lösungsrichtungen (für /20-analyse, nicht entschieden)
1. **Teilfeld-Payloads** auf Trip-Seite (Muster #2375 übernehmen, geteilte Bausteine ⇒ Trip+Compare gemeinsam) — begrenzt Schaden auf eigene Felder; schützt nicht Felder, die zwei Reiter teilen (`display_config.metric_alert_levels`, `active_metrics`).
2. **Kein Discard bei 412** bzw. Registry nach 412 sperren, bis Retry/Reload den frischen Stand geholt hat (unbedingtes Schreiben verhindern) — berührt S3-Entscheidung + Test :261 ⇒ ggf. neues ADR/ADR-Fortschreibung.
3. **Konfliktzustand nicht von anderem Reiter überschreiben lassen** (Controller-Sperre / pro-Reiter-Zustand) — adressiert UI-Verlust.
4. **keepalive-Bypass im BriefingScheduleTab** beseitigen; **/state-Discard** prüfen.
5. Server: If-Match erzwingen (428) — größter Hebel, aber Python-/Listen-/Briefings-Pfade müssen erst alle mitziehen.

## Risks & Considerations
- Trip/Compare-Teilungsregel: Änderungen an `shared/`-Reitern wirken in beiden Flächen — gemeinsam lösen, keine Trip-only-Kopie.
- Memory: ETag/If-Match fängt keinen Same-Tab-Race (#2381) — Teilfelder sind dafür der eigentliche Schutz.
- Datenschutz-Regel (CLAUDE.md „Read-Modify-Write mit Merge, niemals Replace") — Trip-Reiter verletzen sie clientseitig durch Spread veralteter Objekte.
- Bewusste Altentscheidungen (Discard nach 412, keepalive ohne If-Match) sind durch Tests zementiert — Änderung ⇒ Tests bewusst umschreiben + Spec/ADR-Fortschreibung.
- Scope-Gefahr: viele Schreiber ⇒ LoC-Limit 250 vermutlich zu knapp; Scheibenschnitt in der Analyse erwägen.
- Mehrnutzer: kein Bezug zur Mandantentrennung erwartet, aber Tests mit echtem Nutzerkontext.

## Prüfbefund gegen origin/main (5ec28b86, Phase 2)

Frontend/Go/Python im Worktree identisch zu origin/main. Gegenüber dem Kontext oben:

1. `api.ts:136` Discard bei 412 unverändert; gilt über `extractTripId` (`etagRegistry.ts:55-56`) für Trip **und** Ortsvergleich. Test `apiTripEtagConflict.test.ts:261-275` ruft `discardEtag` selbst auf — zementiert nur „nach Discard kein If-Match", **die 412→Discard-Entscheidung selbst hat keinen eigenen Test**.
2. `mergeConfigMap` einstufig bestätigt (`config_merge.go:18-20`); `alert_channels`/`alert_channel_thresholds` feldweise je Kanal (`trip.go:412-448`).
3. **ABWEICHUNG:** `VersandTab.svelte` schreibt nicht selbst (kein `api.put`). Versand-Schreiber auf der Trip-Seite ist allein `BriefingScheduleTab` (Compare: `versandVergleichSpeicherung.ts`).
4. **ABWEICHUNG/Verschärfung — 412-Quelle belegt:** Trip-ETag = SHA-256 der Bytes der Trip-Datei im Nutzer-Ordner `briefings/` (`internal/store/briefing_fingerprint.go:35`). Der Python-Core schreibt dieselbe Datei per `save_trip` (`src/app/loader.py:1922-1983`) ohne Go-Lock und ohne ETag: `trip_command_processor.py:2387/2467/2633/2660 (skip_next=True)/2961/2977`, `track_resolution.py:333`, `alert_gate.py:334` (`_skip_next_verbrauchen`). ⇒ Telegram/SMS-Befehle und Briefing-Läufe sind realistische 412-Auslöser ohne zweites Browserfenster.
5. **Neuer Verlustweg ohne 412:** `report_config` wird von `BriefingScheduleTab` (`{...reportConfig}`, :26/:45) **und** `WeatherMetricsTab` (ganzes `reportConfig`, :306-307/:1012/:1034) als Vollkopie geschickt ⇒ ein per Telegram/SMS gesetztes `report_config.skip_next` (bzw. sein Verbrauch) wird beim nächsten Speichern eines offenen Reiters still zurückgeschrieben; außerdem überschreiben sich die beiden Reiter gegenseitig (`day_window_*` vs. Versandzeiten).
6. Kollisionstabelle (eingehängte Schreiber, `TripTabs.svelte:221-234`):

| Schreiber | Trip-Top-Level | display_config | report_config | Veraltete Kopie? |
|---|---|---|---|---|
| TripHeader :45 | name | – | – | nein |
| handleActivityChange `TripTabs.svelte:188` | activity | – | – | nein |
| EditStagesPanelNew :167/:193/:428 | stages | – | – | nein |
| AlarmeTab (`alarmeDeliveryPayload.ts:106-135`) | official_warnings, alert_cooldown_minutes, alert_quiet_from/to, alert_channels, alert_channel_thresholds | `{...current, metric_alert_levels}` | – | JA (Rest von display_config) |
| CorridorEditor :272 (Mobile :228) | corridors | ganze `trip.display_config` | – | JA (komplett) |
| WeatherMetricsTab `/weather-config` :933-955 | – | `{...trip.display_config, metrics, channel_layouts, preset_name, telegram_kurzform, outlook_metrics, outlook_metric_formats}` | – | JA (u.a. metric_alert_levels) |
| WeatherMetricsTab PUT :980/:1012/:1034 | official_alerts_enabled | – | ganzes report_config | JA |
| BriefingScheduleTab :45/:56 | – | – | ganzes report_config | JA |
| PATCH /state `+page.svelte:106` | paused, archived | – | – | nein (aber danach Discard :137) |

   Echte Doppel-Eigentümer auf Schlüsselebene: keine — `metric_alert_levels` (Eigentümer AlarmeTab) und `metrics` (Eigentümer WeatherMetricsTab) schicken Nachbarn nur als Kopie mit ⇒ Teilfeld-Payloads lösen das. `report_config` muss dafür auf Unterschlüssel-Ebene geteilt werden (Versandzeiten/Kanäle vs. `day_window_*` etc.) — das verlangt serverseitig keinen tieferen Merge, solange jeder Reiter nur seine eigenen `report_config`-Unterschlüssel sendet (einstufiger Merge reicht).
7. `BriefingScheduleTab` speichert bei **jeder Geste** mit `keepalive: true` (`:42-47`, `:92`) ⇒ nie If-Match, nie serialisiert; `onTripUpdate` aus lokaler Kopie (:46). Kommentar `api.ts:178-182` falsch. Ortsvergleich nicht betroffen.
8. `saveStatusStore`: `schedule()` :184-189 und `doSave` :120-143 rufen `setSaving()` ohne Konflikt-Guard ⇒ `conflict` → `idle`, `_lastFailed` verwaist, `retryConflict`-Guard :153 macht „Nochmal speichern" wirkungslos. Trip (`tripSaveCtl`) und Compare (`hubSaveCtl`) identisch betroffen (gleiche Klasse).
9. **ADR:** „Discard nach 412" steht in keinem ADR (nur S3-Spec :213ff + Kommentar `api.ts:133-135`). Änderung ist kein ADR-Bruch; Fortschreibung ADR-0036 empfohlen.
10. Git: kein #1433-Fix; Compare-Teil per #2375/#2381 teilweise erledigt.
11. Helfer: `waehleEigenfelder` (`compareEditorSave.ts:319`) ist an `ComparePreset`/Preset-URL gebunden; Kern (Pick nach Top-/Display-Keys, `undefined` überspringen, `[]`/`{}`/`""` durchlassen) ist generalisierbar ⇒ gemeinsame Pick-Funktion unter `shared/`. Einhängepunkt Trip: `tripSpeicherung.ts:32`.
12. Nebenbefund: Sequenz `/weather-config` → Trip-PUT (`tripSpeicherung.ts:61-72`) nicht atomar bei 412 im ersten Schritt.

## Analysis

### Type
Bug (Datenverlust-Risiko, Kriterium b)

### Kernerkenntnis
Zwei unabhängige Verlustwege, beide aus derselben Wurzel „Reiter sendet veraltete Vollkopie fremder Felder":
- **W1 (Ticket):** Fremdänderung → 412 in Reiter A → `discardEtag` → Reiter B schreibt **ohne If-Match** mit veraltetem Spread von `display_config`/`report_config` ⇒ Fremdänderung still überschrieben; Konfliktanzeige von A verschwindet (`saveStatusStore` `conflict→saving→idle`).
- **W2 (neu, ohne 412):** Python-Core setzt/verbraucht `report_config.skip_next` u.a. in derselben Datei; BriefingScheduleTab (immer ohne If-Match via keepalive) und WeatherMetricsTab senden das ganze `report_config` zurück ⇒ Telegram/SMS-Befehl still rückgängig.

**Designfalle (verbindlich):** Nach 412 nur den ETag neu holen ist KEIN Fix — gültiges If-Match + veralteter Spread ⇒ 200 OK, Verlust abgesegnet (#2381-Lehre). Der eigentliche Schutz sind Teilfeld-Payloads; die Registry-/Controller-Änderung ergänzt sie für gleiche Schlüssel.

### Technical Approach (Tech-Lead-Entscheidung)
Kombination der Richtungen 1–4, Richtung 5 (Server erzwingt If-Match/428) nur Ausblick, weil `save_trip` im Python-Core ohne ETag schreibt.

1. **Teilfeld-Payloads (größter Hebel):** neue generische `shared/pickEigenfelder.ts` (`pickEigenfelder(quelle, {top, display, report})`; `undefined` überspringen, `[]`/`{}`/`""` durchlassen = Löschsemantik). `waehleEigenfelder`/`buildComparePresetPartialPayload` werden dünne Adapter darauf (Compare-Signaturen + Tests unverändert grün). Pick nur beim Senden, lokaler Zustand/Dirty-Erkennung unberührt.
   - AlarmeTab: Top-Level wie heute, `display_config:{metric_alert_levels}`.
   - CorridorEditor (Desktop+Mobile): `{corridors}` + nur eigene display-Schlüssel (in /30 per Grep festnageln), nicht `trip.display_config`.
   - WeatherMetricsTab `/weather-config`: nur `metrics, channel_layouts, preset_name, telegram_kurzform, outlook_metrics, outlook_metric_formats`.
   - WeatherMetricsTab Trip-PUT: `official_alerts_enabled` + `report_config` nur Inhalt-Schlüssel (`show_*`, `email_format`, `daily_summary_metrics`, `show_compact_summary`, `wind_exposition_min_elevation_m`, `day_window_start_hour/end_hour` — in /30 gegen `EditReportConfigSection`/`reportConfigPayload.ts` festnageln).
   - BriefingScheduleTab: `report_config` nur Versand-Schlüssel (`morning_/evening_enabled`, `morning_/evening_time`, `send_*`, `telegram_style`, ggf. `enabled`, `multi_day_trend_*`). **Entscheidung:** `multi_day_trend_*` gehören dem Versand-Reiter.
   - **Python-eigene Schlüssel sendet nie ein Reiter:** `skip_next`, `paused_until`, `updated_at`, `change_threshold_*`, unbekannte Schlüssel (Allowlist erzwingt das).
2. **Kein unbedingtes Schreiben nach 412:** `api.ts:136` verwirft den ETag nicht mehr, sondern markiert die Ressource als `konflikt` und behält den alten ETag ⇒ jeder Folge-Schreibvorgang trägt das alte If-Match und bekommt wieder 412 (nichts wird geschrieben). Konflikt endet nur durch `retryConflict` (GET → `trip` ersetzen → ETag adoptieren → Eigenfelder erneut senden) oder Reload. `trip.*` wird bei 412 NICHT ersetzt (würde As abgelehnte Eingabe wegwerfen).
3. **Konfliktanzeige bleibt:** `schedule()`/`doSave()` verlassen `conflict` nicht; `_lastFailed` wird deduplizierte Liste (ein Eintrag je Reiter), `retryConflict` führt alle nach einem Refresh aus. **Entscheidung Reiter B bei offenem Konflikt:** darf speichern, bekommt 412, landet in derselben Liste; Server trägt die Sperre, keine Client-Sperre. TripHeader und `handleActivityChange` melden 412 an den Controller (`meldeKonflikt`).
4. **Lücken schließen:** BriefingScheduleTab ohne Dauer-`keepalive` (über `schedule`, `init` des Unload-Flush durchreichen), `trip` aus Server-Antwort. `/state`: statt `discardEtag` (`+page.svelte:137`) GET + adoptieren — außer bei offenem Konflikt. Kommentar `api.ts:178-182` korrigieren.
5. **Doku:** ADR-0036 fortschreiben (Absatz „Verhalten nach 412 / Teilfeld-Prinzip"); S3-Spec (`issue_1395_s3_etag_registry.md` Discard + keepalive-Annahme) per „Abgelöst durch"-Hinweis korrigieren.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/pickEigenfelder.ts` | CREATE | generische Teilfeld-Auswahl |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | MODIFY | `waehleEigenfelder` als Adapter |
| `frontend/src/lib/components/shared/alarme-tab/alarmeDeliveryPayload.ts` | MODIFY | nur `metric_alert_levels` |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte` | MODIFY | Desktop+Mobile Teilfelder |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` (+ `tripSpeicherung.ts`) | MODIFY | `/weather-config` + report_config-Teilfelder |
| `frontend/src/lib/components/trip-detail/BriefingScheduleTab.svelte` | MODIFY | Teilfelder, kein Dauer-keepalive, Server-Antwort |
| `frontend/src/lib/etagRegistry.ts` | MODIFY | Konflikt-Markierung statt Discard |
| `frontend/src/lib/api.ts` | MODIFY | 412-Behandlung, Kommentar |
| `frontend/src/lib/stores/saveStatusStore.svelte.ts` | MODIFY | Konflikt-Guard, `_lastFailed`-Liste, `meldeKonflikt` |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte`, `TripTabs.svelte` | MODIFY | 412 an Controller melden |
| `frontend/src/routes/trips/[id]/+page.svelte` | MODIFY | `/state` → GET statt Discard |
| `frontend/src/lib/__tests__/fakeTripServer.ts` | MODIFY | `{merge:true}` (einstufig) + `foreignWrite` (Python-Schreiber) |
| neue Tests (`node --test`) | CREATE | s.u. |
| `docs/adr/0036-…md`, `docs/specs/modules/issue_1395_s3_etag_registry.md` | MODIFY | Fortschreibung |

Go/Python: keine Änderung.

### Bug-Tests aus Nutzersicht (rot vor Fix)
- `trip_mehrreiter_nach_412_kein_verlust.test.ts`: Seed → A lädt → `foreignWrite` setzt `display_config.metrics=[y]` → A speichert `metric_alert_levels` ⇒ 412, Controller `conflict` → B speichert `channel_layouts` über denselben Controller ⇒ Server `metrics` bleibt `[y]`, Controller bleibt `conflict`, B-PUT trug If-Match und bekam 412. Heute rot.
- `trip_python_skip_next_ohne_412.test.ts`: Python setzt `report_config.skip_next=true` → Reiter (frischer ETag) ändert `day_window_start_hour` ⇒ `skip_next` bleibt `true`. Heute rot.
- `pickEigenfelder`-Kernregel: `[]`/`{}`/`""` gehen durch, `skip_next` nie.
- Bewusst umzuschreiben/erweitern: `tripStateDiscardsEtag.test.ts`, `saveStatus.test.ts` (Konflikt/Retry), neuer Test „nach 412 trägt Folge-PUT altes If-Match"; prüfen: `*_vergleich_konflikt_nochmal_speichern.test.ts` (hängen an `_lastFailed`), `apiKeepaliveSkipsIfMatch.test.ts` (bleibt für echten Unload), E2E `issue-736-tabs-reorg.spec.ts`, `issue-776-metrics-toggle.spec.ts`. `apiTripEtagConflict.test.ts:261` bleibt (ruft Discard selbst).

### Scope Assessment
- Dateien: ~14 produktiv + Tests + 2 Doku
- Geschätzte LoC: ~+300/-80 produktiv ⇒ über 250 ⇒ `loc_limit_override 500` in /40 setzen. Ein Workflow, eine Spec, alle ACs (Memory: nie auf eine Scheibe verengen). Interne Umsetzungsreihenfolge: (1) Teilfelder, (2) Registry+Controller, (3) keepalive/`/state` — (2) darf nie ohne (1) ausgeliefert werden.
- Risk Level: **MEDIUM-HIGH** — zentrale Speicherlogik beider Flächen (Trip + Ortsvergleich teilen api.ts/Registry/Store/shared-Reiter).

### Risiken
- Ortsvergleich-Regression (gleiche Registry/Store) — Compare-Tests müssen unverändert grün bleiben.
- Löschsemantik: Server-Merge löscht nie ⇒ leere Werte müssen weiter gesendet werden.
- Unload-Flush: nach Wechsel auf Debounce muss Hard-Navigate über `flush({keepalive:true})` abgesichert sein (Test).
- `/weather-config` → Trip-PUT nicht atomar; mit Konflikt-Markierung steht Schritt 2 bis Retry, Retry ist mit Teilfeldern idempotent.
- Schlüssel-Eigentümerlisten müssen vollständig sein — ein vergessener Eigen-Schlüssel wäre ein stiller „wird nicht mehr gespeichert"-Fehler ⇒ je Reiter Roundtrip-Test „jedes bedienbare Feld landet auf dem Server".

### Dependencies
etagRegistry ← api.ts ← alle Schreiber; saveStatusStore ← `tripSaveCtl`/`hubSaveCtl`; Go `UpdateTripHandler`/`mergeConfigMap` (einstufig, unverändert); Python `save_trip` als Fremdschreiber.

### Open Questions
- [ ] Keine PO-Frage. Eigentümerlisten der display/report-Schlüssel je Reiter werden in /30 per Grep festgenagelt (technisch, kein PO-Thema).

## Übergabe aus /40 (RED) an /50 — Festlegungen der Tests

RED-Stand: 18 Testdateien, 171 Tests, 73 rot (alle AssertionError, kein Ladefehler), Baseline 188/188 grün, `go test ./internal/handler` grün. AC→Test-Mapping: `docs/artifacts/fix-1433-mehrreiter-412-datenverlust/ac-test-mapping.md`. Messaufbau: `frontend/src/lib/components/trip-detail/__tests__/tripMehrreiterPruefstand.ts` + `fakeTripServer.ts` (`merge: true`, `foreignWrite`, Go-treuer einstufiger Merge).

Die Tests setzen voraus:
1. `_lastFailed` ist eine Liste; `null`/`undefined` gelten als leere Liste.
2. Ein erfolgreicher `doSave` im Zustand `conflict` bleibt `conflict`; nur `retryConflict` (oder Neuladen) beendet ihn.
3. Registry: `markiereKonflikt(id)` / `istKonflikt(id)` exakt so benannt; `clearEtagRegistry()` setzt auch die Konflikt-Markierung zurück.
4. Retry von Kopf (`name`) und Aktivität sendet die Nutzereingabe erneut (kein wirkungsloses „Nochmal speichern“).
5. Der `discardEtag`-Import in `routes/trips/[id]/+page.svelte` entfällt.
6. Bei offenem Konflikt adoptiert weder Registry noch lokales `trip` etwas — auch nicht aus der PATCH-`/state`-Antwort. Der Retry-GET adoptiert trotz gesetzter Markierung (Trip + ETag gemeinsam).
7. Namen, an denen der Prüfstand hängt (nicht umbenennen): `buildSaveFn` (Wertebereiche), `scheduleSave`, `makeNameSaveHandler`, `handleActivityChange`, `handlePauseClick`, `handleArchiveConfirm`, Versand-`$effect` auf `_lastReportConfig`.
8. Spec-Prämisse korrigiert: `saveStatus.test.ts` zementierte das Verlassen von `conflict` nicht; dort wurde ein neuer Block ergänzt.
9. Grenzen: AC-19 nur über Reihenfolge gemessen (GET vor PUTs, If-Match = GET-Stempel); Dedup-Schlüssel der Liste nicht festgelegt/getestet. E2E `issue-736`/`issue-776` nicht betroffen (geprüft).
