# Context: rework-2276-compare-speicherweg

Issue #2276 · Epic #2345 Etappe P1 (Frontend) · Dach #1374
Erhoben 2026-09-18 im Worktree `pure-riding-owl`, gemessen auf `0d559eff`.

## Request Summary

Der Ortsvergleich-Hub soll auf den Trip-Speicherweg umgestellt werden: die geteilten
Tab-Organismen speichern selbst über `saveController`, die Compare-eigene Klebeschicht
(`compareHubWizardBridge` · `compareEditorSave` · `compareWizardState` · Commit-Handler in
`CompareTabs`) entfällt im Hub-Pfad.

## Ist-Stand — Korrekturen am Ticket-Text

Das Ticket stammt vom 2026-09-09. Zwei seiner Aussagen treffen heute nicht mehr zu:

| Ticket sagt | Gemessen 2026-09-18 |
|---|---|
| Der Vergleich speichere über Commit-Callbacks „von außen" als ein Vorgang | Der Hub feuert **bereits pro Reiter einen eigenen PUT** über eine gemeinsame `hubPutQueue`; je Handler eigener Diff-Snapshot und eigener Rollback. Die Divergenz zum Trip ist enger als beschrieben: **Ort** der Speicherlogik (Seite statt Organismus) und **Queue-Mechanik** (`createPutQueue` statt `saveController`). |
| Voll-Spread-Payload sei nötig, „solange der Go-Handler in das volle Modell dekodiert" | Mit #2285 (`0d559eff`, heute live) ist `applyComparePresetPatch` **ein** Merge-Kernel für beide PUT-Wege; der ~170-Zeilen-Feldrettungsblock ist entfallen. → eigener Prüfpunkt, siehe „Offene Fragen" |
| 48 `context ===`-Verzweigungen | **~60 Stellen über 10 Dateien** unter `shared/` |

Ebenfalls nicht im Ticket: `CompareWizardState` wird im Hub **nur als Feld-Container** genutzt
(`setContext('compare-wizard-state')`, `CompareTabs.svelte:330`); seine Save-Methoden
liefen dort gar nicht — die benutzt(e) nur der Anlege-Pfad (`routes/compare/new/+page.svelte`,
Thema #2277 in P2). **Nachtrag 2026-09-20 (S6a, `a789b4b5`):** `saveComparePreset()` war zu
diesem Zeitpunkt bereits Totcode (null Aufrufer, auch nicht vom Anlege-Pfad — der ruft
`saveNewPreset()`) und wurde in S6a entfernt; siehe
`docs/specs/modules/rework_2276_s6a_totcode_und_ratsche.md`.

## Related Files

### Abzulösende Compare-Klebeschicht (Hub-Pfad)

| Datei | Zeilen | Rolle |
|---|---|---|
| `frontend/src/lib/components/compare/CompareTabs.svelte` | 1855 | Hub-Orchestrator; 5 Commit-Handler + Hydrations-`$effect` + Snapshot + Rollback je Reiter |
| `.../compare/compareHubWizardBridge.ts` | 816 | Adapter Hub↔Payload; `buildHubPutPayload`, `hydrate*`, `flushPending*`, `rollback*`, `createPutQueue` |
| `.../compare/compareEditorSave.ts` | 460 | Payload-Bau `buildComparePresetSavePayload` (PUT, Round-Trip-Spread über `original`) + `buildNewComparePresetPayload` (POST, Anlegen) |
| `.../compare/compareWizardState.svelte.ts` | 246 | `$state`-Feld-Container; Save-Methoden nur im Anlege-Pfad benutzt |
| `.../compare/compareEditorLoad.ts` | 46 | `rehydrateActiveMetrics` — Lade-Gegenstück, unterscheidet „bewusst leer" von „Default" |

Commit-Handler in `CompareTabs.svelte`: `handleCorridorCommit` (404-425, Rumpf ausgelagert nach
`korridorCommit.ts`) · `handleVersandCommit` (507-553) · `handleAlarmeCommit` (648-678) ·
`handleWetterMetrikenCommit` (756-ff.) · `handleLayoutCommit` (832-ff.). Alle teilen
`hubPutQueue` und `currentPreset` als Baseline, jeder hat eigene `lastPersisted*Snapshot`.

### Trip-Vorbild

| Datei | Rolle |
|---|---|
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` (395 Z.) | mountet die vier Organismen mit `{trip} {onTripUpdate} {saveController}` (Z. 224-234); `handleValueChange` (145-182) erzwingt `saveController.flush()` beim Reiter-Wechsel |
| `frontend/src/lib/stores/saveStatusStore.svelte.ts` (257 Z.) | Klasse `SaveStatus`, Factory `createSaveStatus(tripId?)`; `schedule(fn, 700ms)`, `flush`, `defer`, `cancel`, `retryConflict`; Zustände `idle/dirty/saving/error/conflict` |
| `frontend/src/routes/trips/[id]/+page.svelte:43` | erzeugt genau **eine** Controller-Instanz je Seite, reicht sie als **Prop** (nicht Context) durch |
| `frontend/src/lib/components/ui/SaveIndicator.svelte` | liest `state/error/savedAt` vom Controller (`TripHeader.svelte:195`) |
| `frontend/src/lib/api.ts` | `send()` Z.71-166: ETag/If-Match + Serialisierung über `enqueueTripWrite`; ID-Erkennung via `extractTripId(path)` Z.176 |

Muster: Der Organismus baut eine `SaveFn = (init?: RequestInit) => Promise<void>` mit dem
`api.put`-Aufruf darin und übergibt sie an `saveController.schedule()`. Der Controller ruft
selbst kein HTTP auf. `onTripUpdate` ist beim Aufrufer ein reines lokales State-Replace
(`+page.svelte:226-228`), kein Reload.

## Existing Patterns

- **Ein Controller je Editor-Seite, als Prop durchgereicht** — kein Singleton, kein Context.
- **Debounce mit Letzter-gewinnt-Semantik**: `schedule()` überschreibt den vorherigen Timer
  (`saveStatusStore.svelte.ts:176-181`). Tab-übergreifende Verluste verhindert **nicht** der
  Controller, sondern der erzwungene `flush()` beim Reiter-Wechsel (`TripTabs.svelte:170-176`).
  → Diese Kopplung muss der Vergleich mit übernehmen, sonst entsteht genau die Verlustklasse
  aus AC-3.
- **412-Behandlung**: `send()` verwirft den ETag, `doSave()` setzt `state='conflict'`
  (nur wenn `tripId` bekannt), `SaveIndicator` bietet „Wiederholen" über `retryConflict()`.
- **Bestehender Compare-Schutz, der erhalten bleiben muss**: `hubPutQueue` serialisiert die
  Hub-PUTs und reicht den aktualisierten `currentPreset` als Baseline weiter (Nachweise
  F002/F003 in `__tests__/hub_put_queue.test.ts:106-146` / `:149-ff.`, F004 in
  `e2e/compare-hub-versand-inline.spec.ts:311-369`). Ein Umbau, der die Queue ersatzlos gegen
  den Debounce-Controller tauscht, verliert diese Zusicherung.

## `context ===`-Verzweigungen — Klassifikation

Vollständige Tabelle im Agentenbericht; verdichtet:

| Datei | Zeilen ges. | `wiz`/`ws` vs `trip` | Schwerpunkt |
|---|---|---|---|
| `shared/AlarmeTab.svelte` | 509 | 41 / 14 | überwiegend PERSISTENZ (Warnungen-Schalter, Metrik-Level, Kanäle, Schwellen); FACHLICH bleiben: Metrik-Auswahl existiert bei `route` strukturell nicht, `VTAlertSample` vs `AlertPreviewCard`, Radar |
| `shared/CorridorEditor.svelte` | 521 | 18+3 / 9 | PERSISTENZ inkl. `maybeSchedule` (218-234) = das Kernmuster „Commit-Callback vs. direkter Save"; FACHLICH: Copy „Idealbereiche/neutral" vs „Akzeptanzgrenzen" (284-325) |
| `shared/CorridorEditorMobile.svelte` | 505 | 17 / 9 | >90 % strukturgleiche Dublette von `CorridorEditor` mit Kommentar „bewusst dupliziert" — eigenes Thema, nicht #2276 |
| `shared/WeatherMetricsTab.svelte` | 2081 | 41 / 38 | PERSISTENZ (zwei Ladepfade); FACHLICH: reduzierter Funktionsumfang im Vergleich (ab 1288); **toter Zweig `:577`** (`vergleich \|\| route` deckt beide Werte ab) |
| `shared/VersandTab.svelte` | 357 | 31 / 4 | zwei Markup-Bäume (251/287) — **nicht rein persistenzbedingt**: Premium-SMS nur `route`, Mehrtages-Trend nur `route`, `VTLaufzeitRoute` (read-only aus Etappen) vs `VTLaufzeitVergleich` (editierbares Enddatum), `activation`-Snippet nur `vergleich` |

UNKLAR (Entscheidung in der jeweiligen Scheibe): Inhalt von `VERGLEICH_CTX_DEFAULTS` vs
`ROUTE_CTX_DEFAULTS` (`CorridorEditor` 250-252) · `wertebereicheTabId`
(`alarmeTabSections.ts:42`) · Mehrtages-Trend-Karte nur `route` (`VTSchedulePlan.svelte:55/184`).

## Regressionsnetz — Lücke

| Ebene | Lage |
|---|---|
| Unit (`frontend-test`, **in der CI-Ampel**) | `__tests__/hub_put_queue.test.ts` (F002/F003), `compare_hub_alarme_bridge.test.ts`, `compare_hub_layout_save.test.ts`/`_rollback`, `hub_versand_inline.test.ts`, `compareEditorSave.test.ts`, `compare_hub_wizard_bridge.test.ts` u. a. |
| E2E **in** `.github/ci_e2e_specs.txt` | `compare-cross-user-write-block`, `compare-detail-edit-entry`, `compare-editor-autosave-user-isolation`, `compare-editor-slice1/3`, `compare-legacy-fields-survive-save`, `compare-radar-toggle`, `issue-682-compare-editor-mobile`, `issue-690-custom-metrics-persist`; Trip: `speicherung-ueberlebt-neuladen` (prüft Trip **und** Vergleich, inkl. 412-Fall über Netzwerk-Halt) |
| E2E **nicht** in der Ratsche (laufen nicht in CI) | `compare-hub-save-chip`, `compare-hub-name-region-profil`, `compare-hub-versand-inline` (**inkl. F004-Lost-Update, :311-369**), `compare-hub-inline-edit`, `compare-hub-briefing-times`, `compare-metric-order`, `compare-hourly-metric-order`, `compare-alarm-config`, `compare-layout-tab-dissolution`, `compare-hub-fidelity-s8c/s8d`, `compare-flow-navigation`, `compare-mobile-vervollstaendigung` |

**Folge:** Der harte Persistenz- und Lost-Update-Nachweis für den Hub liegt überwiegend
außerhalb der Ampel. Aufnahme der einschlägigen Specs in `ci_e2e_specs.txt` gehört in den
Umfang der ersten Scheibe — sonst baut die Etappe ohne Netz um.

## Dependencies

- **Upstream:** `applyComparePresetPatch` (Go, #2285, live seit `0d559eff`) · `api.ts`
  ETag/Serialisierung · `saveStatusStore` · Metrik-Katalog `/api/metrics`
- **Downstream:** `CompareDetail.svelte` → `CompareTabs` · `routes/compare/[id]` ·
  `routes/compare/+page.svelte` (Listen-Kebab nutzt `buildFreshTogglePutPayload`) ·
  `Step2Orte.svelte` (liest den Context) · `korridorCommit.ts` ·
  `weatherMetricsCompareSave.ts` · ~20 Unit-Testdateien unter `compare/__tests__/`
- **Bleibt bestehen (P2, #2277):** Anlege-Pfad `routes/compare/new/+page.svelte` +
  `CompareNewEditor.svelte` nutzen `CompareWizardState.saveNewPreset()` weiter.

## Existing Specs

- `docs/context/rework-2279-alert-kanal-aufloesung.md` — Scheibenschnitt S1/S2 der Nachbar-Etappe
- `docs/specs/modules/rework_2279_s1_alert_kanal_aufloesung.md`
- `docs/reference/api_contract.md` — DTOs, seit #2285 mit `kind=route`/Merge-Kernel-Hinweis

## Risks & Considerations

1. **ETag/Serialisierung: geklärt, mit einer echten Lücke.** (gemessen 2026-09-18)
   - `TRIP_PATH_RE` (`etagRegistry.ts:47`) matcht **`/api/compare/presets/{id}` bereits mit** —
     If-Match (`api.ts:87/97`), ETag-Übernahme (`:156`) und Serialisierung über
     `enqueueTripWrite` (`:183-185`) greifen für den Vergleich also heute schon. Insoweit
     stimmt die Ticket-Aussage.
   - **Nicht abgedeckt: `/api/briefings/{id}`.** Ein Umbau, der auf die kind-neutrale Route
     wechselt, verlöre Konfliktschutz und Serialisierung ersatzlos. → **Zusicherung für die
     Spec: der Hub bleibt auf `/api/compare/presets/{id}`.**
   - **Lücke (im Ticket nicht erwähnt):** `refreshTripEtag` (`api.ts:222-224`) ruft fest
     `GET /api/trips/${tripId}`. `SaveStatus.retryConflict()` (`saveStatusStore.svelte.ts:145-150`)
     hängt daran. Bekommt der Vergleich den Trip-Controller, ist der „Wiederholen"-Knopf nach
     einem 412 **defekt** (Abruf gegen die falsche Entität). Verallgemeinerung von
     `refreshTripEtag` gehört damit in die **erste** Scheibe.
   - `doSave()` setzt `state='conflict'` nur bei gesetzter `_tripId` (`:123`) → der Controller
     des Vergleichs muss mit der Preset-ID erzeugt werden, sonst degradiert der Konfliktfall
     still zu `error` ohne Wiederholpfad.
2. **Feldweiser Merge im Go-Kernel: geklärt — tragfähig, mit einer namentlichen Ausnahme
   und einer Beweislücke.** (gemessen 2026-09-18, `internal/handler/compare_preset.go:292-354`)
   - `applyComparePresetPatch` → `mergeBriefingPatch` (`briefing_subscription.go:174-196`)
     legt den Patch als JSON-Overlay über das marshalte Original. **Fehlender Key = unverändert**,
     unabhängig von Pointer-Typen. Beide PUT-Wege nutzen denselben Kernel
     (`compare_preset.go:406`, `briefing_subscription.go:264`). Serververwaltete Felder
     (ID, UserID, CreatedAt, LetzterVersand, PausedAt, ArchivedAt, Kind) werden danach aus
     `original` restauriert.
   - `AlertChannelThresholds` und `OfficialWarnings` sind **sicher**: `mergeConfigMap`
     (`config_merge.go:11-22`) mergt eine Ebene tief, und beide Typen sind flach. Für den
     Compare-Pfad existiert kein eigener Schwellen-Merge-Code — er lebt vollständig vom
     generischen Kernel. 20 Go-Tests decken beide Schreibwege ab
     (`compare_preset_alert_channel_thresholds_test.go`).
   - **🔴 Ausnahme: `DisplayConfig map[string]interface{}` wird nur auf der obersten
     Schlüsselebene gemergt** — dokumentiert in `config_merge_structure_test.go:278-282`.
     Liegt unter einem `display_config`-Schlüssel selbst wieder ein mehrstufiges Objekt, ersetzt
     ein Teil-PUT diesen Unterschlüssel **komplett**. Genau `display_config` ist das Feld, das
     die Metrik- und Layout-Reiter schreiben → **die Metrik-/Layout-Scheibe muss ihren
     `display_config`-Teilbaum vollständig senden** oder den Merge vorher vertiefen. Diese
     Zusicherung gehört ausdrücklich in die Spec der betroffenen Scheibe.
   - Arrays (`LocationIDs`, `Corridors`, `Empfaenger`) werden bei Anwesenheit ersetzt → der
     schreibende Reiter sendet immer die vollständige Liste. Vertragsthema, kein Merge-Thema.
   - **Beweislücke:** Für Weg 1 (`PUT /api/compare/presets/{id}`) existiert **kein** Test, der
     wirklich nur ein einzelnes Feld ohne Pflichtfelder schickt — belegt ist das nur für Weg 2.
     Da der gesamte Umbau auf dieser Zusicherung steht, gehört dieser Test an den **Anfang**
     der ersten Scheibe. Zwei Testkommentare
     (`compare_preset_etag_ifmatch_test.go:39`, `compare_preset_alert_channel_thresholds_test.go:81`)
     beschreiben Weg 1 noch als „Voll-Ersetzen, Pflichtfelder müssen mit" — veraltete Doku aus
     der Zeit vor #2285, beim Anfassen mitkorrigieren.
3. **AC-Zuschnitt.** AC-2 („nur noch fachliche Verzweigungen") und AC-4 („kein Importeur von
   `compareHubWizardBridge`") sind erst nach der **letzten** Scheibe erfüllbar und AC-4
   zusätzlich erst nach #2277 (P2), weil der Anlege-Pfad die Module weiter braucht. Als
   Scheiben-AC wären sie strukturell nie bestehbar → müssen für die Spec je Scheibe neu
   gefasst und dem PO in dieser Fassung zur Freigabe vorgelegt werden.
4. **VersandTab ist keine mechanische Zusammenführung** (echte Fachunterschiede) und berührt
   #2275 (Premium-SMS). → späte Scheibe, nach Klärung von #2275.
5. **Verlust der Queue-Zusicherungen.** F002/F003/F004 hängen an `hubPutQueue`. Der
   Trip-Controller ersetzt sie nicht 1:1 (Debounce = letzter gewinnt + `flush()` beim
   Reiter-Wechsel). Die Ersatz-Mechanik muss benannt und getestet sein, bevor die Queue fällt.
6. **LoC-Limit.** Der Gesamtumbau liegt weit über 250 Zeilen je Workflow → Scheibenschnitt mit
   je eigener Spec und eigenem Workflow, `loc_limit_override` statt Nachschneiden.

## Tech-Lead-Entscheidungen (2026-09-18)

### E1 — Fassung von AC-4 für P1

`compareHubWizardBridge` hat **drei** Importeur-Gruppen: Hub (`CompareTabs`, `korridorCommit.ts`,
`weather-metrics-tab/weatherMetricsCompareSave.ts`), **Listenseite**
(`routes/compare/+page.svelte`, Kebab-Umschalter über `buildFreshTogglePutPayload`) und
**Anlege-Pfad** (`routes/compare/new/+page.svelte`, `CompareNewEditor.svelte`).

**Entscheidung:** P1 migriert **nur den Hub-Pfad**. Die Listenseite gehört thematisch zu #2278
(P3, Kebab/Action-Sheet), der Anlege-Pfad zu #2277 (P2). AC-4 lautet für diese Etappe:
> „Kein Importeur von `compareHubWizardBridge`/`compareEditorSave` mehr im **Hub-Pfad**;
> die verbleibenden Importeure sind namentlich belegt und an #2277 (Anlegen) bzw. #2278
> (Listen-Kebab) übergeben."

Begründung: P1 in P3 hineinwachsen zu lassen verwischt die Etappengrenzen des Epics und macht
die Scheibe unprüfbar groß. Die vollständige Tilgung ist Epic-DoD-1, nicht Scheiben-AC.

### E2 — Ersatzmechanik für die `hubPutQueue`

Die Queue (`createPutQueue`, `CompareTabs.svelte:208`) sichert heute, dass zwei Hub-Änderungen
nicht mit derselben veralteten `currentPreset`-Baseline rechnen (Nachweise F002/F003 in
`__tests__/hub_put_queue.test.ts`). Sie ist **kein** ETag-Ersatz — If-Match und
`enqueueTripWrite` laufen für `/api/compare/presets/{id}` bereits generisch über `api.ts`.

Der Trip erreicht dieselbe Eigenschaft ohne eigene Queue, über vier zusammenwirkende Teile:

1. `onTripUpdate` → lokales State-Replace beim Aufrufer (`trips/[id]/+page.svelte:226-228`)
2. **eine** Controller-Instanz je Seite, als Prop durchgereicht
3. erzwungenes `saveController.flush()` beim Reiter-Wechsel (`TripTabs.svelte:170-176`)
4. `enqueueTripWrite` serialisiert die Netzwerk-Schreibvorgänge

**Entscheidung:** Der Vergleich bekommt das Pendant `onCompareUpdate` in der Rolle, die heute
`currentPreset` spielt; die Queue fällt erst, wenn 1–4 stehen.

**Korrektur 2026-09-18 (frühere Fassung war falsch):** Der Hub hat **bereits** einen
Speicher-Controller — `routes/compare/[id]/+page.svelte:59` erzeugt `createSaveStatus()` und
reicht ihn an `CompareTabs` (`:494`). Er ist aber auf zwei Arten halb verdrahtet:

- Er wird **ohne Kennung** erzeugt ⇒ `_tripId` bleibt leer ⇒ der 412-Zweig in `doSave()`
  (`saveStatusStore.svelte.ts:123`) greift nie.
- Die Commit-Handler rufen `setSaving()`/`setSaved()`/`setError()` **direkt** und nie
  `doSave()`/`schedule()` ⇒ ein Konflikt erreicht den Zustand `conflict` überhaupt nicht.

**Folge:** Der „Wiederholen"-Knopf erscheint im Ortsvergleich heute gar nicht; ein 412 endet
als generischer Fehler. Das ist ein schärferer Befund als „ruft die falsche Adresse ab".
S1 stellt den Mechanismus bereit (Kennung wird übergebbar, Refresh entitätsneutral); **wirksam
für den Nutzer wird er erst in S2**, wenn die Handler auf `doSave()` umgestellt sind. S1 allein
hat an dieser Stelle bewusst keine sichtbare Wirkung — das ist kein Mangel, sondern die
Reihenfolge: erst der tragfähige Mechanismus, dann die Umstellung, die ihn benutzt. **Bedingung:** Da F002/F003
Unit-Tests **auf `createPutQueue`** sind, fallen sie mit der Queue. Die Scheibe, die die Queue
entfernt, muss die Zusicherung an der neuen Stelle prüfen **und** die Mutations-Gegenprobe dort
führen (Baseline nach dem ersten PUT nicht aktualisieren ⇒ Test muss rot werden). Ohne diesen
Nachweis wandert die Zusicherung stillschweigend in den nicht-geratschten E2E-Test F004.

### E3 — `display_config` (betrifft S4)

Geschrieben werden u. a. die Ebene-1-Schlüssel `telegram_style`, `hourly_metrics`,
`metric_alert_levels`. Da der Go-Merge nur Ebene 1 zusammenführt, gilt als **AC** der
betroffenen Scheibe: *Jeder Reiter sendet den von ihm verantworteten `display_config`-Teilbaum
vollständig.* Vor S4 ist zu prüfen, ob zwei Reiter denselben Ebene-1-Schlüssel beschreiben
(insbesondere `metric_alert_levels`: Alarme-Reiter vs. Metrik-Reiter) — falls ja, ist das ein
Verlustpfad und die Scheibe braucht entweder einen vertieften Merge oder eine klare
Schlüssel-Eigentümerschaft.

### E4 — Reihenfolge der Scheiben (Abweichung von der Epic-Empfehlung)

Epic #2345 nennt „Alarme → Wertebereiche → Versand → Wetter-Metriken". **Abweichung:** Versand
wandert ans Ende.

| Scheibe | Inhalt | Warum hier |
|---|---|---|
| **S1 — Netz und Fundament** | Weg-1-Minimal-PUT-Test (Go, Beweislücke) · `refreshTripEtag` entitätsneutral + `retryConflict` für den Vergleich · Compare-Hub-Persistenz-Specs in `ci_e2e_specs.txt` | Der gesamte Umbau steht auf „Teil-PUT ist verlustfrei" — unbewiesen für Weg 1. Ohne Specs in der Ampel bauen alle Folgescheiben ohne Netz um. Liefert nebenbei einen echten Defekt-Fix (412-Wiederholung im Vergleich). |
| **S2 — Alarme** | `saveController`-Instanz für den Hub **plus** `AlarmeTab` speichert selbst | Höchste Persistenz-Dichte (41 `wiz` / 14 `trip`), klar abgegrenzt; macht #2293 billiger |
| **S3 — Wertebereiche** | `CorridorEditor` (+ Mobile) | Enthält mit `maybeSchedule` (218-234) das Kernmuster „Commit-Callback vs. direkter Save" |
| **S4 — Wetter-Metriken/Layout** | `WeatherMetricsTab` | Größter Brocken (2081 Z.); `display_config`-Zusicherung aus E3; räumt den toten Zweig `:577` mit |
| **S5 — Versand** | `VersandTab` | **Zuletzt**, weil die beiden Markup-Bäume echte Fachunterschiede tragen (Premium-SMS, Mehrtages-Trend, `VTLaufzeitRoute` vs `VTLaufzeitVergleich`) und der Reiter mit #2275 kollidiert |
| **S6 — Rückbau und Bilanz** | Klebeschicht im Hub entfernen, Queue abbauen (E2), Zweig-Bilanz für AC-2 in der P1-Fassung | Erst sinnvoll, wenn alle Reiter umgestellt sind |

### E5 — Befund zu #2275 (nicht Teil dieser Etappe, aber belegt)

Die Ticket-Prämisse von #2275 („der Vergleich bietet einen wirkungslosen Premium-SMS-Schalter")
trifft auf den heutigen Code **nicht** zu: Der schaltbare Block in
`shared/versand-tab/VTBriefingChannels.svelte:194-217` rendert nur, wenn `onPremiumSmsChange`
übergeben wird — das tut ausschließlich der `route`-Zweig. Der Vergleich zeigt einen
„bald verfügbar"-Platzhalter. Invariante 1 ist damit in der behaupteten Form nicht verletzt.
Der Backend-Teil (Auflösung nimmt `premium_sms` auf, `send_compare_report` bedient ihn nicht)
ist davon unberührt und weiterhin zu prüfen.

**Zusätzlich:** Der Code beruft sich auf **ADR-0049** („Premium-SMS ist kein Vergleichs-Kanal").
Der Entscheid im Ticket-Kommentar („verdrahten") weicht davon ab ⇒ er braucht ein neues ADR mit
Status „Abgelöst durch", sonst wird eine dokumentierte Entscheidung still zurückgenommen
(CLAUDE.md-Regel). Gehört in den Umfang von #2275.
