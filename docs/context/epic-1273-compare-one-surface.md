# Context: epic-1273-compare-one-surface

## Request Summary

PO-Entscheid (Prod-Audit, Befund 9, 2026-07-16): Der Ortsvergleich bekommt **EINE** Bearbeiten-Fläche nach dem Muster von #616 (Trip). Der heutige Detail-Hub (`CompareTabs.svelte`) wird die einzige Oberfläche — vollständig editierbar mit Auto-Save (saveController-Muster, „Gespeichert"-Chip). Der separate Editor `/compare/[id]/edit` (`CompareEditor.svelte`) entfällt. Der Create-Wizard (`/compare/new`) bleibt unverändert als Anlege-Weg bestehen.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/compare/CompareTabs.svelte` (1710 Zeilen) | Wird DIE Fläche. Aktuell 5 separate `api.put()`-Commit-Handler (`persistPickedIds`, `handleCorridorCommit`, `handleVersandCommit`, `handleAlarmeCommit`, `handleToggleActive`), serialisiert über `hubPutQueue` (Z.178). Kein zentraler `SaveStatus`, kein Chip. |
| `frontend/src/lib/components/compare/CompareEditor.svelte` (1686 Zeilen) | Entfällt. Hat bereits `compareSaveCtl = createSaveStatus()` (Z.76-83) + `computeCompareAutoSaveAction()`-Gate (Z.243-270) — nutzt schon fast das Trip-Muster, nur zusätzlich mit sichtbaren Speichern/Verwerfen-Buttons statt reinem Chip. Enthält die einzigen editierbaren Felder für **Name** (Z.1177-1189), **Region** (Z.1191-1200), **Aktivitätsprofil** (Z.1202-1247) — existieren im Hub nur read-only. |
| `frontend/src/routes/compare/[id]/edit/+page.svelte` (119 Z.) + `+page.server.ts` | Route entfällt → Redirect auf `/compare/[id]` (Vorbild AC-2 aus #616). |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | `buildComparePresetSavePayload()` (Round-Trip-Spread) — wiederverwendbare Payload-Logik, potenziell für den Hub-Save-Pfad zu übernehmen statt neu zu bauen. |
| `frontend/src/lib/stores/saveStatusStore.svelte.ts` | Geteilte `SaveStatus`-Klasse (Trip **und** Compare-Editor nutzen sie bereits) — Single Source of Truth, hier NICHT ändern, nur im Hub verdrahten. |
| `frontend/src/lib/components/ui/SaveIndicator.svelte` | Der „Gespeichert HH:MM"-Chip selbst (Trip-Vorbild) — direkt wiederverwendbar. |
| `frontend/src/routes/trips/[id]/+page.svelte` (Z.13,22,25-34,284-285) | Vorbild: Instanziierung `createSaveStatus()` auf Routen-Ebene + `beforeNavigate`-Flush-Guard. |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` (Z.44,47,204-217) | Vorbild: `saveController`-Prop wird ungebrochen an alle editierbaren Kind-Tabs durchgereicht. |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` (Z.488-505) | Vorbild-Beispiel für `saveController.schedule()` + `weatherSaveGate`-Kopplung in einem Kind-Tab. |
| `frontend/src/routes/compare/[id]/+page.svelte` (Z.102,180,215,158,167,208,237) | Hub-Route selbst — Kebab-Menü + Buttons verlinken aktuell auf `/edit`; Name/Region werden hier bereits read-only angezeigt (Parent der Tabs). |
| **7 weitere Link-Stellen** auf `/edit` | `CompareKachel.svelte:20`, `compare/+page.svelte:119-120`, `routes/+page.svelte:95,556,562,568` (Home-Hero, 3 Deep-Links inkl. `#idealwerte`/`#schedule`-Anker!), `subscriptionHelpers.ts:270,299-302` (Kebab-Action-Definition), `MCompareActionSheet.svelte` (Mobile-Bottom-Sheet, delegiert). |

## Existing Patterns

- **#616 (Trip-IA):** Exaktes Referenz-Muster für diese Migration — alte `/edit`-Seite wird zum Redirect, kanonische Tab-Oberfläche wird zur einzigen Fläche, Pro-Tab-/Auto-Save bleibt erhalten, Namens-Edit zieht auf die Hauptoberfläche. Spec: `docs/specs/modules/issue_616_trip_editor_tabs.md`.
- **#758/#880 (SaveStatus + Chip):** Bereits fertiger, geteilter Baustein — Trip nutzt ihn vollständig, Compare-Editor teilweise (nur in `CompareEditor.svelte`, nicht im Hub).
- **#1234/#1269 (Schreib-Gate + Baseline-Korrektheit):** `weatherSaveGate`/`compareAutosave.ts` verhindern Auto-Save ohne Nutzergeste. Gilt es beim Hub-Umbau konsequent mitzunehmen, sonst Regression von #1269 (gerade erst geschlossen).
- **Trip/Compare-Teilungs-Invariante (CLAUDE.md):** Editor-Rahmen, Lock-Engine, Speichern/Verwerfen bzw. Auto-Save sollen EIN geteilter Baustein sein (`context="route"|"vergleich"`). Bisher ist `CompareTabs.svelte` eine reine Compare-Eigenentwicklung ohne Trip-Pendant-Nutzung bei der Save-Mechanik — genau der im CLAUDE.md benannte Default-Fehler-Kandidat.

## Dependencies

- **Upstream (wird benutzt):** `saveStatusStore.svelte.ts` (SaveStatus-Klasse), `SaveIndicator.svelte` (Chip-UI), `compareAutosave.ts`/`weatherSaveGate.ts` (Schreib-Gate), `compareEditorSave.ts` (Payload-Bau), `hubPutQueue` aus `compareHubWizardBridge.ts` (Serialisierung — bleibt evtl. bestehen oder wird durch `schedule()`-Debounce abgelöst).
- **Downstream (hängt von Compare-Editor/Route ab):** ~7 produktive Link-Stellen (Kebab-Menüs, Mobile-Stift-Icon, Home-Hero-Deep-Links inkl. Tab-Anker), ~20 Playwright-e2e-Spec-Dateien mit `goto('/compare/{id}/edit')`, ~7 Unit-Tests die `CompareEditor.svelte`/die Edit-Route per Source-Inspection prüfen.
- **Vorbedingung erledigt:** #1269 (Speicher-Anzeige-Lüge, Trip+Compare) — abgeschlossen, live. #1268 (verworfene Zeitfenster-/Horizont-Felder) — abgeschlossen, live, betraf `CompareInhaltSection.svelte` (Layout-Tab-Inhalt, an dem #1273 ebenfalls rührt). #1272 (Sortierung vereinheitlichen, `OutputLayoutEditor.svelte`) — abgeschlossen, live; geteilter Baustein bleibt bei der Migration unangetastet nutzbar.
- **Sinnvoll vorher (nicht hart blockierend):** keine offenen mehr — #1268 ist inzwischen fertig.

## Existing Specs

- `docs/specs/modules/issue_616_trip_editor_tabs.md` — Trip-Referenzmuster (Redirect, EINE Oberfläche, Pro-Tab-Save).
- `docs/features/epic-677-compare-editor.md` — Historie des heutigen Compare-Editor-Tab-Umbaus (Slices 1-5), zeigt warum `CompareEditor.svelte` in seiner jetzigen Form entstand (Wizard → Tab-Editor) und was in Slice 6 „Cleanup" bereits als Zukunftsarbeit vermerkt war (Löschung von `CompareWizard.svelte`).
- `docs/specs/modules/issue_1269_save_status_lie.md` — direkte Voraussetzung, gerade approved+live; benennt #1273 explizit als Grund, warum Auto-Save vertrauenswürdig sein muss.
- `docs/specs/modules/issue_1256_*` (mehrere) — frühere Zwei-Flächen-Staffelung, die #1273 laut PO-Text ablöst.
- `docs/reference/api_contract.md` — DTO-Format `ComparePreset`/`display_config` für den Payload-Bau.

## Risks & Considerations

1. **Name/Region/Aktivitätsprofil fehlen im Hub komplett** — müssen als editierbare Felder neu in `CompareTabs.svelte` (Übersicht- oder Kopfbereich) gebaut werden, inkl. Persistenz. Bisher nirgends im Hub verdrahtet (nur read-only Anzeige im Parent).
2. **Zwei koexistierende Save-Mechaniken zusammenführen:** Hub nutzt aktuell 5 event-diskretisierte PUT-Commit-Handler über eine eigene `hubPutQueue`; Editor nutzt bereits `SaveStatus.schedule()`. Entscheidung nötig: `hubPutQueue` durch `saveController.schedule()` ersetzen, oder beide Mechaniken kombinieren (Serialisierung + Debounce-Chip). Sollte in der Analyse-Phase geklärt werden, bevor die Spec geschrieben wird.
3. **~7 produktive Link-Stellen umbiegen**, davon 3 mit **Tab-Anker-Deep-Links** (`#idealwerte`, `#schedule`) aus dem Home-Hero — der Redirect/die Zielroute muss dieselbe Tab-Sprungmarken-Fähigkeit behalten wie #616's „?tab=“-Mapping.
4. **Testlast:** ~20 e2e-Spec-Dateien + 7 Unit-Tests hängen direkt an `CompareEditor.svelte`/der Edit-Route. Diese müssen vor dem Löschen auf den Hub umgezogen oder abgelöst werden — deutlich mehr als bei #616 (dort nur vereinzelte Altlasten).
5. **Scheiben-Schnitt ist laut Ticket selbst noch offen** — PO-Text sagt ausdrücklich „Spec entscheidet den Schnitt". Empfehlung für die Analyse-Phase: erst Felder-Migration (Name/Region/Profil in den Hub) + Save-Modell-Vereinheitlichung als Scheibe 1, danach Redirect + Link-Umbiegung + Test-Migration als Scheibe 2, erst zuletzt `CompareEditor.svelte`/Route-Löschung als Abschluss-Scheibe (analog #616s eigenem Soll-Scope von ~250-350 LoC pro Slice).
6. **Mobile-Stift-Icon** (`routes/compare/[id]/+page.svelte:215`) zeigt aktuell auf `/edit` — muss laut PO-Text auf den Hub zeigen (ist ohnehin dieselbe Seite nach der Migration, ggf. nur noch Tab-Fokus statt Route-Wechsel).

## Analysis

### Type
Feature (Epic, mehrere Scheiben)

### Technical Approach — Speicher-Modell

**Nicht** `hubPutQueue` durch `saveController.schedule()` ersetzen — Datenverlust-Risiko: `SaveStatus.schedule()` hat nur EINEN Timer-/Pending-Slot; ein zweiter `schedule()`-Aufruf aus einem anderen Tab-Handler innerhalb der 700ms-Debounce würde den vorigen, noch nicht gefeuerten Save ersatzlos verwerfen (genau das Szenario, vor dem #1269 gerade erst geschützt hat). Der Hub hat 5 unabhängige Commit-Ziele, Trip dagegen disjunkte Zeitfenster pro Tab — nicht vergleichbar.

**Stattdessen: Kombination.** `hubPutQueue` bleibt für die Netzwerk-Korrektheit (Serialisierung, kein Drop). Ein geteilter `hubSaveCtl = createSaveStatus()` (Routen-Ebene, analog `tripSaveCtl`) wird manuell getrieben: `setSaving()` vor jedem `hubPutQueue.enqueue(...)`, `setSaved()`/`setError()` nach Abschluss — nicht über `schedule()`s Debounce. Damit nutzt der Hub dieselbe `SaveStatus`-Klasse + denselben `SaveIndicator`-Chip (Teilungs-Invariante erfüllt), ohne die Drop-Gefahr.

**Präzedenzfall bestätigt das Muster:** `TripHeader.svelte:31-54` — Trip-Name-Bearbeitung läuft NICHT über `saveController.schedule()`, sondern isoliert mit eigenem lokalem State + explizitem `api.put()`; der geteilte `saveController` wird dort nur für den Chip mitgerendert. Vorbild für Name/Region/Aktivitätsprofil im Hub.

### Risiko-Korrekturen gegenüber Kontext-Phase

- **Tab-Anker-Deep-Links sind entschärft:** `CompareEditor.svelte` hat kein DOM-Element mit `id="idealwerte"`/`id="schedule"` — die Hash-Links laufen HEUTE SCHON ins Leere. Migration ist ein Fix (`#idealwerte`→`?tab=idealwerte`, `#schedule`→`?tab=versand`), kein Erhalt einer funktionierenden Funktion.
- **Testlast größer als erstgeschätzt:** verifiziert ~26 e2e-Spec-Dateien (nicht ~20) + ~14-17 Unit-Tests (nicht ~7). Eigene Slices nötig, nicht "am Ende mitziehen".
- **Feature-Paritäts-Lücke ist Muss-Blocker vor jedem Redirect:** Name/Region/Aktivitätsprofil nur im alten Editor editierbar — Redirect ohne vorherige Migration = echte Funktionsregression.
- **`window.location.href` statt `goto()`** an mehreren Link-Stellen — beim Umbiegen auf Tab-Wechsel im Hub ggf. unnötiger Full-Reload statt weichem Tab-Switch (kleine UX-Regression, im Blick behalten).

### Scheiben-Schnitt (Empfehlung)

| Slice | Inhalt | Geschätzt |
|---|---|---|
| **S1** | Save-Chip-Infra im Hub: `hubSaveCtl`, `SaveIndicator` im Header, 5 Commit-Handler mit setSaving/setSaved/setError umwickelt (Serialisierung unverändert) | ~3 Dateien, ~120-180 LoC |
| **S2** | Name/Region/Aktivitätsprofil-Parität im Hub (TripHeader-Muster: isoliert, nicht über schedule()) | ~2-3 Dateien + 5-8 Tests, ~150-220 LoC |
| **S3** | 7 Link-Stellen umbiegen (inkl. Hash→Query-Fix) + Redirect-Route (`/edit` → `/compare/[id]?tab=`) | ~8-10 Dateien, ~100-160 LoC |
| **S4a** | ~26 e2e-Specs auf Hub migrieren (ggf. 2 Teil-Slices, PO-Override wahrscheinlich) | ~200-350 LoC |
| **S4b** | ~15 Unit-Tests (Source-Inspection) migrieren/löschen | ~100-150 LoC |
| **S5** | Cleanup: `CompareEditor.svelte` + Route löschen, verwaiste Helper prüfen | netto ~-1900 LoC (Sonderfall wie #616) |

**Reihenfolge:** S1 → S2 → S3 → (S4a/S4b parallel) → S5. Nach jeder Scheibe ist die App voll funktionsfähig (additiv bis S3, S3 macht die alte Route zum reinen Redirect ohne Codelöschung = sicherer Rollback-Punkt, S4 ist reine Testarbeit, S5 räumt erst auf wenn alles grün ist).

### Empfehlung erster Workflow

**S1 — „Compare-Hub: geteilter Save-Chip"**, ~120-180 LoC über 2-3 Produktivdateien (`CompareTabs.svelte`, `routes/compare/[id]/+page.svelte`), kein PO-Override nötig. Rein additiv, kein Redirect, keine Testlöschung — legt die Infrastruktur für S2/S3, löst die Teilungs-Invariante aus CLAUDE.md sofort sichtbar ein.

### Open Questions
- [ ] Braucht der Hub überhaupt echtes Debouncing, oder sind die 5 Commit-Handler bereits ausreichend event-diskretisiert (beeinflusst, ob `beforeNavigate`-Flush-Guard nötig ist)? — Klärung in S1-Spec.
- [ ] `compareEditorSave.ts`/`compareEditorLoad.ts` (Round-Trip-Payload-Bau) in S2 wiederverwenden statt neu bauen?

## Next Step

Analyse abgeschlossen. Weiter mit `/30-write-spec` für Slice S1 (Save-Chip-Infra), nach PO-Freigabe des Scheiben-Schnitts.
