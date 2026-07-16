# Context: fix-1261-compare-edit-save

**Issue:** #1261 (`priority:critical`, `type:bug`, `type:rework`) — Ortsvergleich: **(a)** kein „Bearbeiten"-Einstieg auffindbar, **(b)** Änderungen (Orte, Wertebereich, Versand) werden nicht gespeichert; Autospeichern fehlt.
**Track:** Full Process (Intake-Score 4: Scope Medium, Blast Radius High, Unsicherheit Medium)
**Base:** `origin/main @ 3b06f89f` (nach FF-Merge, enthält bereits #1258 S4 — `CompareAlarmSection` gelöscht, geteilter `AlarmeTab context="vergleich"` aktiv).

## Request Summary

Der Nutzer öffnet einen bestehenden Ortsvergleich und (a) findet keinen Weg, ihn zu bearbeiten — im ⋮-Menü der Detailseite stehen nur *Pausieren/Archivieren/Löschen* — und (b) ändert dann Orte/Wertebereich/Versand, aber die Änderungen werden nicht gespeichert; ein Autospeichern wie beim Trip-Editor existiert nicht.

## Befund (a): „Bearbeiten" fehlt im Detail-⋮-Menü — bewusst entfernt (#1256 S3)

Zwei Aktions-Baupläne in `frontend/src/lib/components/compare/subscriptionHelpers.ts`:

| Funktion | Zeile | Enthält `edit`? | Wer rendert damit |
|---|---|---|---|
| `compareActions(status)` | :253 | **Ja** (`{id:'edit'}` :269, nur `active`/`paused`) | Listen-Tiles über `CompareKebab`-Default (`CompareTile.svelte:168` ohne `actions`-Prop → Fallback `CompareKebab.svelte:32`) |
| `compareLifecycleActions(status)` | :279 | **Nein** (`pause/resume`, `archive`, `trash`) | **Detailseite** `routes/compare/[id]/+page.svelte:179` (injiziert als `actions`-Prop) + Mobile-Detail `MCompareActionSheet.svelte:31` |

- **Ursache:** Auf der **Detailseite/Hub** injiziert der Kebab bewusst `compareLifecycleActions` → nur Lebenszyklus → **kein „Bearbeiten"**. Der Kommentar `subscriptionHelpers.ts:274-278` dokumentiert die Absicht (#1256 Scheibe 3): der Hub-Header-Kebab soll nur Lebenszyklus zeigen; Bearbeiten/Vorschau/Senden „exklusiv über Tabs/Primäraktion".
- Der `handleAction('edit')`-Zweig existiert auf der Detailseite (`routes/compare/[id]/+page.svelte:100-102`, navigiert nach `/compare/{id}/edit`), wird vom Header-Kebab aber **nie ausgelöst** → toter Zweig.
- **Die #1256-S3-Annahme ist gescheitert:** Der Nutzer fand die gedachte „Primäraktion/Tabs"-Route zum Editor nicht → faktisch keine Bearbeiten-Möglichkeit auf der Detailseite (Desktop). Mobile-Detail hat ein Stift-Symbol (`routes/compare/[id]/+page.svelte` ~:211-217 → `/compare/{id}/edit`); die **Listen**-Tiles haben „Bearbeiten" im Kebab.
- **Struktur-Divergenz zum Trip:** Beim Trip IST die Detailseite der Editor (`/trips/[id]/edit` ist deprecated → Redirect auf `/trips/[id]`). Beim Compare sind Detail/Hub (`/compare/[id]`) und Editor (`/compare/[id]/edit`) **getrennte Routen** — der Einstieg vom Hub zum Editor ist die verlorene Kante.

## Befund (b): Autospeichern fehlt — Compare speichert nur per Button

**Trip = verteiltes Autospeichern** (Referenz-Muster):
- Controller: `routes/trips/[id]/+page.svelte:22` `createSaveStatus()` → `TripTabs saveController={tripSaveCtl}` (:285) → `TripTabs.svelte:44` reicht an alle Tabs.
- `beforeNavigate`-Flush: `routes/trips/[id]/+page.svelte:25` → `tripSaveCtl.flush()`.
- Persistenz pro Tab (context='route'): `CorridorEditor.maybeSchedule()` :125-132 → `saveController?.schedule(buildSaveFn())`; `AlarmeTab` `$effect` :207-222 (Guard `if (context!=='route') return` :208) → `saveController.schedule(...)`; `VersandTab` schedulet nicht selbst — Wrapper `BriefingScheduleTab.svelte:61-70` → `saveController.doSave(buildSaveFn())`.

**Compare = zentraler manueller Save**:
- `CompareEditor.svelte` `handleSave` :277-383 → `api.put('/api/compare/presets/{id}')`; Dirty-Tracking `initial`/`dirty`; `compareSaveCtl = createSaveStatus()` :72 zeigt nur eine **Status-Pille** (`SaveIndicator` :1433, `setDirty`/`setSaved` :211-216), ruft aber **nie** `.schedule()`/`.flush()`.
- Geteilte Tabs im `vergleich`-Zweig schreiben nur in `wiz.*` und bekommen **keinen** `saveController` (überall `undefined`): CorridorEditor (`:1171`), VersandTab (`:1205/1207`), AlarmeTab (`:1193/1346`).
- **Kein `beforeNavigate`-Flush** im Compare-Edit-Pfad (`routes/compare/[id]/edit/+page.svelte`).
- **Nutzersicht:** Statusanzeige suggeriert Autospeichern, es passiert aber nur beim Klick auf „Speichern". Wer ändert und wegnavigiert → Verlust. Deckt sich exakt mit dem Bug-Report.

## #1234-Schutz „ohne Nutzergeste kein Speichern" — nur im Trip

- `frontend/src/lib/components/trip-detail/weatherSaveGate.ts` (reine Funktion :39-43: `catalogLoaded && userTouched → 'save'`, sonst `'skip'`).
- Eingehängt **ausschließlich** in `WeatherMetricsTab.svelte` (Capture-Listener :781-787, `userTouched`-Flags, `catalogLoaded` nach Katalog-Fetch). `WeatherMetricsTab` wird **nie** im Compare-Editor gemountet.
- CorridorEditors `saveGateDecision()` ist ein **Daten-Validitäts**-Gate (Zeilen gültig?), **kein** Nutzergesten-Gate.
- **Konsequenz:** Ein nachgerüstetes Compare-Autospeichern erbt den #1234-Schutz **nicht** — ein äquivalenter Gesten-Gate muss separat verdrahtet werden, sonst schreibt Autosave ohne echte Nutzer-Eingabe (Datenverlust-Klasse GR221/#1234).

## Related Files

| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/compare/subscriptionHelpers.ts` | (a) beide Menü-Baupläne :253/:279 + Absichts-Kommentar :274-278 |
| `frontend/src/routes/compare/[id]/+page.svelte` | (a) Detail-Kebab :179 (`compareLifecycleActions`), toter `edit`-Handler :100-102, Mobile-Stift ~:211-217 |
| `frontend/src/lib/components/compare/MCompareActionSheet.svelte` | (a) Mobile-Detail :31 (`compareLifecycleActions`) |
| `frontend/src/lib/components/compare/CompareGrid.svelte` / `CompareTile.svelte` / `CompareKebab.svelte` | (a) Listen-Kebab (hat edit) — Referenz für „richtig verdrahtet" |
| `frontend/src/lib/components/compare/CompareEditor.svelte` | (b) zentraler `handleSave` :277-383, `compareSaveCtl` :72/:211-216/:1433, vergleich-Tab-Render :1171/1193/1205/1346 |
| `frontend/src/routes/compare/[id]/edit/+page.svelte` | (b) Edit-Route — hier fehlt `beforeNavigate`-Flush/Controller-Propagation |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | (b) Payload-Bau PUT (RMW-sicher, zentral) |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | (b) `wiz`-State, `saveNewPreset`/`saveComparePreset` |
| `frontend/src/lib/components/shared/{corridor-editor/CorridorEditor,VersandTab,AlarmeTab}.svelte` | (b) geteilte Tabs — vergleich-Zweig ohne Controller; route-Zweig als Muster |
| `frontend/src/lib/components/trip-detail/weatherSaveGate.ts` + `WeatherMetricsTab.svelte` | (b) #1234-Gesten-Gate — Referenz, nicht wiederverwendet im Compare |
| `frontend/src/routes/trips/[id]/+page.svelte` + `trip-detail/TripTabs.svelte` | (b) Trip-Autosave-Fädelung als Referenz |
| Go: `internal/handler/compare_preset.go` (Update-RMW :331-342), Router `PUT /api/compare/presets/{id}` | Persistenz-Endpoint existiert, funktioniert bei manuellem Save — Backend NICHT die Ursache |

## Zwei Lösungsansätze für (b) — Entscheidung gehört in Analyse/Spec

**Ansatz A — zentraler Autospeicher-Auslöser (minimal, risikoarm):** Compare behält das zentrale `handleSave`/`wiz`-Modell; ein debounced `$effect` auf die Dirty-/`wiz`-Änderung ruft `compareSaveCtl.schedule(handleSave)` + `beforeNavigate`-Flush in `compare/[id]/edit/+page.svelte` + ein Compare-Gesten-Gate. Wiederverwendet die bestehende, RMW-sichere Payload-/Dirty-/Reset-/officialWarnings-Logik vollständig. Kein Umbau der geteilten Komponenten → geringe Regressionsgefahr für den Trip.

**Ansatz B — Konvergenz auf das Trip-Muster (verteiltes Autospeichern):** `saveController` an die vergleich-Instanzen der geteilten Tabs durchreichen, deren vergleich-Ausschlüsse (CorridorEditor :126-129, AlarmeTab :208) fallen lassen, VersandTab-vergleich einen schedule-Pfad geben; jeder Tab baut eine compare-spezifische Save-Funktion (PUT `/api/compare/presets/{id}`) + Gesten-Gate. Maximale Code-Teilung (PO-Richtung #1230), aber verteilt die zentral gebündelte Payload-Logik, berührt geteilte Komponenten (Trip-Regressionsrisiko) und ist deutlich größer.

**Vorläufige Tech-Lead-Empfehlung:** Für den **kritischen Bug** Ansatz A (schnell, sicher, kein Umbau geteilter Bausteine, #1234-Gate lokal ergänzbar). Die volle Save-Wiring-Konvergenz (Ansatz B) gehört in das Konvergenz-Epic #1230, nicht in einen Hotfix. Ansatz A erzeugt **keine** neue Compare-Komponente mit Trip-Pendant → verletzt die Teilungs-Invariante nicht. **PO/Spec entscheidet.**

## Existing Specs / verwandte Programme

- `docs/context/feat-1258-s4-compare-editor.md` — Editor-Struktur (frisch), Persistenz-Weiche „vergleich schreibt nur wiz".
- `docs/specs/modules/issue_1258_alarme_tab_official_warnings.md` — laufendes Compare-Editor-Programm.
- Konvergenz-Epic #1230 (`issue_1250_briefing_subscription.md`) — Zielbild geteiltes Save-Modell.
- #1234/GR221 (`known_issues.md`) — Datenverlust-Historie des Speicher-Pfads (Gesten-Gate-Begründung).

## Dependencies

- **Upstream:** geteilte Tabs (CorridorEditor/VersandTab/AlarmeTab), `compareWizardState`, `compareEditorSave`, Go-RMW `UpdateComparePresetHandler` (existiert, funktioniert).
- **Downstream:** Trip-Editor teilt CorridorEditor/VersandTab/AlarmeTab — jeder Eingriff am `route`-Zweig oder an geteilten Save-Signaturen betrifft den Trip. Compare-Hub (`CompareTabs`)/Bridge (S5, #1258) nutzen dieselben Tabs im vergleich-Kontext.

## Risks & Considerations

- **Datenverlust-Klasse (kritisch):** Autospeichern ohne Gesten-Gate = GR221/#1234-Wiederholung. Ein Gesten-Gate ist Pflichtteil des Fixes, nicht optional.
- **Blast Radius geteilte Komponenten:** Ansatz B berührt Komponenten, die der Trip nutzt → Trip-Regressionsgefahr; der `route`-Zweig muss byte-genau unberührt bleiben.
- **Parallele Arbeit #1258:** derselbe Editor ist aktiv in Bearbeitung (S4 gerade gemergt, S5/S6 folgen) — Kollisionsgefahr, Stand vor Implementierung erneut gegen `origin/main` prüfen.
- **(a) ist eine bewusste #1256-S3-Entscheidung** — der Fix muss die dortige Absicht (Hub-Kebab nur Lebenszyklus, Editieren als „Primäraktion") respektieren oder mit PO revidieren: entweder „Bearbeiten" zurück ins Detail-Menü **oder** eine klar sichtbare Primär-„Bearbeiten"-Aktion auf Hub/Detail. Design-/PO-Entscheidung.
- **Compare Detail vs. Edit getrennt** (anders als Trip) — beeinflusst, wo der Bearbeiten-Einstieg logisch hingehört.

## Offene Analyse-Fragen (für /20-analyse)

1. **(a) Lösungsform:** „Bearbeiten" zurück in den Detail-Kebab (`compareLifecycleActions` erweitern / Detail auf `compareActions` umstellen) **oder** eine sichtbare Primär-„Bearbeiten"-Aktion auf Hub/Detail (Design-Soll `screen-compare-detail.jsx` prüfen)? Was ist die aktuelle „Primäraktion" der Detailseite, die #1256 S3 gemeint hat?
2. **(a) Status-Abdeckung:** Für welche Status (active/paused/draft/archived) soll Bearbeiten erscheinen? (`compareActions` hat es nur active/paused; draft → `setup`.)
3. **(b) Ansatz A vs. B** — endgültige Wahl + Begründung; wenn A: exakter Auslöser (welches `$effect`/welche Dirty-Quelle triggert `schedule`), Debounce-Wert (Trip: 700 ms), Flush-Punkte (beforeNavigate; Tab-Wechsel?).
4. **(b) Gesten-Gate für Compare:** Wo genau einhängen (Editor-Root Capture-Listener analog `WeatherMetricsTab` :781-787)? Was zählt als „Nutzergeste" über alle vergleich-Tabs (Orte/Wertebereich/Versand)?
5. **(b) Interaktion mit dem Button:** Bleibt der „Speichern"/„Verwerfen"-Button erhalten (Redundanz zum Autosave) oder wird er wie beim Trip zur reinen Statusanzeige? Verwerfen-Semantik bei aktivem Autosave klären.
6. **(b) Reproduktionstest:** Test, der im Compare-Edit eine echte Nutzergeste auslöst (z. B. Ort ändern) und einen debounced PUT beobachtet — und ein Gegentest: Tab öffnen, nichts tun, wegnavigieren → **null** PUTs (Gesten-Gate-Nachweis, #1234-Muster).

---

## Analyse-Entscheidungen (Phase 2 — gelockt)

### Type
**Bug** (kritisch, `type:bug`+`type:rework`). Nutzersicht: Editor schwer auffindbar + speichert nicht.

### PO-Richtungsentscheid (2026-07-15, emphatisch)
> „Ortvergleich soll sich so verhalten wie Trips!!!!!!!"

→ Trip-Verhalten 1:1 spiegeln, keine Platzierungs-Rückfragen. **Faktenanker:** Der Trip hat **keinen** separaten `/edit`-Screen (`TripHeader.svelte:33`; `/trips/[id]/edit` → Redirect) — die Detailseite **ist** der inline-Editor mit Autospeichern. Der Compare hat noch getrennte Routen `/compare/[id]` (Hub) vs `/compare/[id]/edit`.

### Scope-Grenze (wichtig)
Der Bug-Report belegt, dass der Nutzer den Editor **erreicht** hat (Punkt b: „ich kann … ändern"). #1261 = **Verhaltensparität**: (a) Bearbeiten trip-gleich auffindbar, (b) Autospeichern trip-gleich. **NICHT** in #1261: die strukturelle Routen-Verschmelzung (Detail = inline-Editor) — das ist Konvergenz-Epic **#1230** und würde mit laufender #1258/#1250-Arbeit an genau diesem Editor kollidieren.

### (a) Entscheidung — Bearbeiten auffindbar machen (trip-gleich)
Auf der Compare-Detailseite einen klar sichtbaren „Bearbeiten"-Einstieg schaffen (Desktop hat heute gar keinen). Spiegelt die Trip-Auffindbarkeit (dort ist Editieren immer präsent). Konkret in der Spec: sichtbare „Bearbeiten"-Aktion auf der Detailseite **und** Wiederherstellung im Desktop-⋮-Kebab (wo der Nutzer gesucht hat); Mobile-Stift bleibt. Respektiert #1256-S3-Absicht (Editieren als Primäraktion), macht sie aber real auffindbar.

### (b) Entscheidung — Autospeichern nachrüsten (Ansatz A)
Compare behält seine **zentrale** Speicher-Logik (`handleSave`/`compareEditorSave`, RMW-sicher), bekommt aber den **automatischen Auslöser** wie der Trip:
1. Debounced Auto-Save (Trip-Parität ~700 ms) getriggert durch echte Dirty-Änderung am `wiz`-State.
2. `beforeNavigate`-Flush in `routes/compare/[id]/edit/+page.svelte` (offenes Speichern vor Verlassen).
3. **#1234-Gesten-Gate** auf Editor-Ebene: ohne echte Nutzergeste (pointer/keydown auf interaktive Ziele **+** change/input) kein Schreibzugriff — verhindert Autosave-Datenverlust (GR221-Klasse). `weatherSaveGate.ts`-Logik wiederverwenden (Funktion ist context-agnostisch), Capture-Listener am Compare-Editor-Root ergänzen.
4. Status-Pille (`SaveIndicator`) bleibt; „Speichern"/„Verwerfen"-Button-Semantik trip-gleich klären (Trip: reine Statusanzeige, kein manueller Save-Zwang) — in Spec-AC festlegen.

**Warum Ansatz A statt B (verteilt/geteilte Tabs):** kritischer Bug → geringstes Regressionsrisiko; kein Umbau der geteilten Bausteine (Trip-Regressionsgefahr); volle Wiederverwendung der bestehenden datensicheren Payload-/Dirty-/Reset-Logik. Verhaltensparität zum Trip aus Nutzersicht identisch. Vollständige Wiring-Konvergenz = #1230.

### Affected Files (Änderungs-Erwartung)
| File | Change | Zweck |
|---|---|---|
| `frontend/src/lib/components/compare/subscriptionHelpers.ts` | MODIFY | (a) `compareLifecycleActions` um `edit` ergänzen bzw. Detail-Kebab auf edit-haltige Liste |
| `frontend/src/routes/compare/[id]/+page.svelte` | MODIFY | (a) sichtbare „Bearbeiten"-Aktion Desktop-Header/Detail |
| `frontend/src/lib/components/compare/MCompareActionSheet.svelte` | MODIFY | (a) Mobile-Detail konsistent (falls nötig) |
| `frontend/src/lib/components/compare/CompareEditor.svelte` | MODIFY | (b) Auto-Save-Trigger auf `wiz`-Dirty + Gesten-Gate + Capture-Listener |
| `frontend/src/routes/compare/[id]/edit/+page.svelte` | MODIFY | (b) `beforeNavigate`-Flush |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | evtl. MODIFY | (b) zentrale Dirty-/Autosave-Signalquelle |
| Wiederverwendet: `weatherSaveGate.ts` | REUSE | (b) Gesten-Gate-Logik (context-agnostisch) |
| Tests (Vitest/Playwright) | CREATE/MODIFY | (b) debounced-PUT bei Geste; **null** PUT ohne Geste; (a) Bearbeiten erreichbar |

### Scope Assessment
- Files: ~5–7 Frontend · Est. LoC: ~120–200 → LoC-Limit 250, evtl. knapp; Override nur mit PO-Freigabe.
- Risk: **MEDIUM-HIGH** — Speicher-Pfad mit Datenverlust-Historie (#1234/GR221), geteilte Statusanzeige, aktiver Parallel-Umbau (#1258). Backend unberührt (FE-only; `PUT /api/compare/presets/{id}` existiert & funktioniert).

### Open Questions (für Spec/PO-Gate)
- [ ] „Verwerfen"-Semantik bei aktivem Autospeichern (Trip-Verhalten spiegeln) — in AC festlegen.
- [ ] Vor Implementierung erneut gegen `origin/main` prüfen (#1258 S5/S6 könnten CompareEditor/Detail weiter verändern).
