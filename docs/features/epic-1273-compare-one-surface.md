# Epic 1273: Ortsvergleich auf EINE Fläche

**Status:** Complete (Slice S5/F2b — 2026-07-19)
**Epic Scope:** Der Ortsvergleich-Hub (`CompareTabs.svelte`) wird nach dem Muster von #616 (Trip-IA) zur **einzigen** Bearbeiten-Fläche für einen Ortsvergleich — vollständig editierbar mit Auto-Save-Chip (`SaveStatus`/`SaveIndicator`, „✓ Gespeichert HH:MM"). Der separate Editor `/compare/[id]/edit` (`CompareEditor.svelte`, aus Epic #677) ist mit F2b (2026-07-19) ersatzlos gelöscht. Die Anlege-Strecke `/compare/new` folgt seit F2a (2026-07-19) dem Trip-Muster #622 (`CompareNewEditor`); der alte Wizard/`CompareEditor` existiert nicht mehr im Repo.
**Related Specs:**
- `docs/specs/modules/feat_1273_s1_compare_hub_save_chip.md` (Slice S1 — Save-Chip-Infra) — Approved, VERIFIED
- `docs/specs/modules/feat_1273_s2_compare_hub_name_region_profil.md` (Slice S2 — Name/Region/Aktivitätsprofil inline editierbar) — Approved, Adversary-Verdict AMBIGUOUS→Freigabe nach Test-Fix
- `docs/specs/modules/feat_1273_s3_redirect.md` (Slice S3 — Edit-Route wird reiner Redirect) — Approved, Adversary-Verdict AMBIGUOUS→behoben, alle 7 ACs CONFIRMED
- `docs/context/epic-1273-compare-one-surface.md` (Kontext-/Analyse-Dokument, Scheiben-Schnitt)

**Child Slices:** S1 ✓ (2026-07-16) · S2 ✓ (2026-07-17) · S3 ✓ (2026-07-17) · S4a ✓ Teilmenge 4/26 e2e (2026-07-17) · S4b ✓ (2026-07-17) · S4c ✓ (2026-07-19, `c822cb85`) · S5/F2a ✓ (2026-07-19, `37381f47`+`c5503e3a`: /compare/new = CompareNewEditor nach Trip-Muster #622, Alt-Editor unangetastet) · S5/F2b ✓ (2026-07-19: `CompareEditor.svelte` + Editor-only-Helfer gelöscht) — **S5 KOMPLETT, Epic #1273 abgeschlossen**

**PO-Auftrag:** Prod-Audit, Befund 9, 2026-07-16.

---

## Overview

Der heutige Ortsvergleich hat zwei Bearbeiten-Flächen: den Detail-Hub `CompareTabs.svelte` (read-only für Name/Region/Aktivitätsprofil, aber mit 5 eigenständigen `PUT`-Commit-Handlern für Orte/Wertebereiche/Versand/Alarme/Aktiv-Status) und den separaten `CompareEditor.svelte` unter `/compare/[id]/edit` (voll editierbar, aus Epic #677, Tab-Umbau des ursprünglichen 5-Schritt-Wizards). Dieser Zwei-Flächen-Zustand widerspricht der Trip/Compare-Teilungs-Invariante (CLAUDE.md) und der etablierten Trip-IA aus #616, bei der der Detail-Hub selbst die einzige Bearbeiten-Fläche ist.

**Ziel:** `CompareTabs.svelte` wird — wie `TripTabs.svelte` für Trips — die alleinige Fläche. `/compare/[id]/edit` wird zu einem reinen Redirect (analog #616 AC-2) und am Ende gelöscht, inklusive `CompareEditor.svelte` selbst.

**Nutzerfall:** VOR-ORT-Urlauber konfiguriert einen Ortsvergleich (Name, Region, Aktivitätsprofil, Orte, Wertebereiche, Versand, Alarme) an einer einzigen Stelle, mit sofortigem, ehrlichem Speicher-Feedback statt Sprung zwischen zwei Oberflächen.

---

## Vorgänger-Tickets

| Ticket | Bezug |
|---|---|
| **#616** | Trip-IA-Referenzmuster: Detail-Hub wird einzige Fläche, alte Edit-Route wird Redirect, Pro-Tab-/Auto-Save bleibt erhalten. Exaktes Vorbild für #1273. Spec: `docs/specs/modules/issue_616_trip_editor_tabs.md`. |
| **#1269** | „Speicher-Anzeige-Lüge" (Trip + Compare) — am 2026-07-16 geschlossen, direkte Voraussetzung für S1: liefert `markPristine()` für No-Op-Commits, ohne die S1 dieselbe Lüge (falscher „Fehler"-Zustand bei No-Op) reproduziert hätte. |
| **#1268** | Verworfene Zeitfenster-/Horizont-Felder in `CompareInhaltSection.svelte` (Layout-Tab-Inhalt) — abgeschlossen, live; derselbe Compare-Bereich, an dem #1273 in späteren Slices ebenfalls rührt. |
| **#1272** | Sortierung vereinheitlicht in `OutputLayoutEditor.svelte` — abgeschlossen, live; geteilter Baustein bleibt bei der Migration unangetastet nutzbar. |
| **Epic #677** | Historie des heutigen `CompareEditor.svelte` (Wizard → Tab-Editor, Slices 1–5). Slice 6 dort („CompareWizard-Deletion, Full Tab-Editor-Umstieg") wird durch #1273 nicht fortgeführt, sondern durch die hier beschriebene Konsolidierung abgelöst — s. Verweis in `docs/features/epic-677-compare-editor.md`. |

---

## Geplante Slices (Scheiben-Schnitt aus Analyse-Phase)

| Slice | Inhalt | Status |
|---|---|---|
| **S1** | Save-Chip-Infra im Hub: `hubSaveCtl`, `SaveIndicator` im Header, 5 Commit-Handler mit `setSaving()`/`setSaved()`/`setError()`/`markPristine()` umwickelt (Serialisierung über `hubPutQueue` unverändert) | ✓ Complete 2026-07-16 |
| **S2** | Name/Region/Aktivitätsprofil-Parität im Hub (TripHeader-Muster: isoliert, nicht über `schedule()`) — Feature-Paritäts-Lücke, Muss-Blocker vor jedem Redirect | ✓ fertig 2026-07-17 |
| **S3** | 7 produktive Link-Stellen auf den Hub umbiegen (inkl. Hash→Query-Fix `#idealwerte`→`?tab=idealwerte`, `#schedule`→`?tab=versand`) + Redirect-Route (`/edit` → `/compare/[id]?tab=`) | ✓ fertig 2026-07-17 |
| **S4a** | Teilmenge der ~26 e2e-Specs: 4 Dateien, die nur totes Editor-Chrome oder eine überholte URL prüfen (löschen/URL-Fix) — NICHT die vollständigen ~26, s. Korrektur unten | ✓ Complete 2026-07-17 |
| **S4b** | ~15 Unit-Tests (Source-Inspection auf `CompareEditor.svelte`) migrieren/löschen | ✓ Complete 2026-07-17 |
| **S4c** *(neu, 2026-07-17 bei S4a-Recherche entdeckt)* | ~19 verbleibende e2e-Specs, die gültige Fachlogik über den alten Editor prüfen (Idealwerte, Alarme, Radar-Toggle, Altfelder-Erhalt beim Speichern — Bezug BUG-DATALOSS-GR221/#102 —, Versand-Tab, Autosave-Mandantentrennung) strukturell auf den Hub umziehen (Testids, Autosave-Warten statt Save-Klick) | ✓ Complete 2026-07-19 (`c822cb85`, Spec `epic_1273_s4c_e2e_migration.md`): 9 Dateien Hub-Klasse, 5 Wizard-Klasse (echter Klickpfad ab `/compare/new`), Chrome-DELETEs spec-autorisiert; Autosave-ACs auf Hub-Semantik (1 PUT/Aktion, echte Navigations-Race); 4 vorbestehend faule Fixtures repariert (skitour-Profil, Registrierung ohne E-Mail #1226, Metrik-Keys, mail_to-Reset-Pointer-Falle) |
| **S5** | Cleanup: `CompareEditor.svelte` + Editor-only-Helfer löschen, verwaiste Helper prüfen (netto ~-2000 LoC, Sonderfall wie #616). **Anlege-Strecke ENTSCHIEDEN (PO-bekräftigt 2026-07-19, war nie offen):** `/compare/new` wird nach dem Trip-Muster #622 neu zusammengesetzt (Progressive-Tab-Anlege-Seite aus den geteilten Organismen WeatherMetricsTab/CorridorEditor/AlarmeTab/VersandTab, Pendant `TripNewEditor`); der alte Wizard fällt mit. Die frühere Zeile „Create-Wizard bleibt unverändert" in der Ziel-Hierarchie unten ist überholt und gilt nicht. Die `/edit`-Route selbst bleibt (Trip-Muster #616 — reiner Redirect), nur der Alt-Editor wird gelöscht. Schnitt: F2a Anlege-Seite nach Trip-Vorbild, F2b Löschung | F2a ✓ 2026-07-19 (`37381f47`+`c5503e3a`) · F2b ✓ 2026-07-19 — **S5 komplett** |

**Reihenfolge:** S1 → S2 → S3 → (S4a/S4b/S4c parallel) → S5. Nach jeder Scheibe ist die App voll funktionsfähig — additiv bis S3, S3 macht die alte Route zum reinen Redirect ohne Codelöschung (sicherer Rollback-Punkt), S4a/S4b/S4c sind reine Testarbeit, S5 räumt erst auf wenn alles grün ist.

Details und Begründung des Schnitts: `docs/context/epic-1273-compare-one-surface.md`, Abschnitt „## Analysis" → „Scheiben-Schnitt (Empfehlung)".

---

## Slice S1: Compare-Hub — geteilter Save-Chip (Issue #1273, Spec `feat_1273_s1_compare_hub_save_chip.md`)

**Status:** ✓ Completed 2026-07-16, Adversary-Verdict **VERIFIED**

Reine additive Infrastruktur: kein Redirect, keine Feldmigration, keine Testlöschung, keine Änderung am bestehenden Speicherverhalten selbst. Legt die Voraussetzung, dass der Hub in S2–S5 schrittweise zur einzigen Bearbeiten-Fläche werden kann, und erfüllt sofort sichtbar die Trip/Compare-Teilungs-Invariante (CLAUDE.md): kein neuer Compare-eigener Baustein, sondern Verdrahtung des bestehenden geteilten `SaveStatus`/`SaveIndicator`-Paars in eine dritte Fläche.

**Was gebaut wurde:**

- `hubSaveCtl = createSaveStatus()` auf Routen-Ebene (`frontend/src/routes/compare/[id]/+page.svelte`), analog `tripSaveCtl` bei Trips.
- Thin-Shell-Pass-through über `CompareDetail.svelte` (neue `saveController`-Prop, unverändert durchgereicht) in `CompareTabs.svelte`.
- `<SaveIndicator controller={saveController} />` (position:fixed, geteilter Baustein aus #758/#880, unverändert) im Hub gerendert.
- Alle 5 bestehenden Commit-Handler (`persistPickedIds`, `handleCorridorCommit`, `handleVersandCommit`, `handleAlarmeCommit`, `handleToggleActive`) manuell mit `setSaving()`/`setSaved()`/`setError()` umwickelt — **nicht** über `SaveStatus.schedule()`, da dessen Einzel-Pending-Slot bei den 5 unabhängigen Commit-Zielen des Hubs (anders als Trips disjunkte Tab-Zeitfenster) einen noch nicht gefeuerten Save eines anderen Tabs hätte verwerfen können (Datenverlust-Risiko, exakt das Szenario aus #1269).
- `hubPutQueue` (Serialisierung, Netzwerk-Korrektheit) bleibt unverändert bestehen — Kombination statt Ersatz.
- Für die 3 Handler mit No-Op-Pfad (`handleCorridorCommit`, `handleVersandCommit`, `handleAlarmeCommit`: `if (!payload) return null;` bei fehlendem Diff) wird `markPristine()` (aus #1269) genutzt, um „kein Diff, kein PUT" von „PUT versucht und fehlgeschlagen" zu unterscheiden — sonst wäre ein No-Op fälschlich als Fehler angezeigt worden (neue Variante der gerade erst behobenen Speicher-Anzeige-Lüge).
- Kein `beforeNavigate`-Flush-Guard: bewusst entschieden, da `hubSaveCtl` in S1 nie über `schedule()` getrieben wird und `hasPending` damit strukturell immer `false` ist (Known Limitation, s. Spec).

**4 Acceptance Criteria** (Chip zeigt „✓ Gespeichert" beim Laden; Chip-Verlauf „Speichere…"→„✓ Gespeichert HH:MM" bei echtem Commit; Zeitstempel bleibt bei reinem Tab-Wechsel/No-Op unverändert — Regressionsschutz gegen #1269; Fehler-Zustand + Rollback bei fehlgeschlagenem PUT) — alle vom Adversary-Agent (`implementation-validator`) geprüft, Verdict **VERIFIED**.

**Known Limitations (aus Spec übernommen):**
- Name/Region/Aktivitätsprofil weiterhin nicht im Hub editierbar (S2-Scope).
- Kein `beforeNavigate`-Flush-Guard (s. o.).
- Schmales Race-Fenster bei zwei nahezu gleichzeitigen Commits aus unterschiedlichen Tabs (Chip kann kurz „✓ Gespeichert" zeigen während ein zweiter Commit noch in der Queue wartet) — kein Datenverlust, LOW/kosmetisch, kein eigenes Issue.
- Rein clientseitiger Schutz, keine serverseitige Bestätigung.

Details: `docs/specs/modules/feat_1273_s1_compare_hub_save_chip.md`.

---

## Slice S2: Compare-Hub — Name/Region/Aktivitätsprofil inline editierbar (Issue #1273, Spec `feat_1273_s2_compare_hub_name_region_profil.md`)

**Status:** ✓ Completed 2026-07-17, Adversary-Verdict **AMBIGUOUS** (nach Test-Fix Freigabe erteilt), 6/7 ACs sofort CONFIRMED, AC-5 nach Fix ebenfalls CONFIRMED.

Schließt die Feature-Paritäts-Lücke, die ein Redirect von `/compare/[id]/edit` auf den Hub (S3) sonst zu einer echten Funktionsregression gemacht hätte: Name, Region und Aktivitätsprofil waren im Hub bislang nur lesbar.

**Was gebaut wurde:**

- Name, Region und Aktivitätsprofil sind im Kopfbereich des Compare-Hubs (`frontend/src/routes/compare/[id]/+page.svelte`) inline editierbar — Desktop- **und** Mobile-Block, identisches Verhalten auf beiden.
- UI-Muster: Stift-Icon-Toggle (analog `TripHeader.svelte`), lokaler Edit-State pro Feld, isolierter Save-Pfad mit eigenem `api.put()` **außerhalb** von `saveController`/`schedule()` — Header-Edits laufen nicht über die `hubPutQueue`-Serialisierung der 5 bestehenden Tab-Handler.
- Aktivitätsprofil als Auswahl-Kacheln (Muster `CompareEditor.svelte`), kein Freitext — Klick auf eine Kachel committet sofort, kein Zwischenzustand.
- **Round-Trip-Spread-Payload** (`{ ...data.preset, <geändertes Feld> }`) statt Minimal-Body: `UpdateComparePresetHandler` dekodiert den PUT-Body in ein frisches, ungeschütztes `model.ComparePreset{}` — ein Minimal-Body hätte `location_ids`/`empfaenger`/`schedule`/`profil` auf Zero-Value zurückgesetzt (BUG-DATALOSS-Muster, CLAUDE.md). Gleiches Prinzip wie im alten `CompareEditor.svelte` (`compareEditorSave.ts`).
- **Referenz-Ersetzung `data.preset = updated`** statt In-Place-Mutation — notwendig, damit der bereits bestehende defensive `$effect` in `CompareTabs.svelte` (Zeile 821-826) auf den Referenzwechsel reagiert und `currentPreset` auffrischt. Ohne diesen Referenzwechsel hätte ein nachfolgender Commit im selben Seitenaufenthalt (z. B. Wertebereiche- oder Versand-Tab) den gerade geänderten Namen/Region/Profil stillschweigend zurücküberschrieben — dieselbe Datenverlust-Klasse wie der bereits behobene „Staging-Fund F004".

**Adversary-Fund:** Der ursprüngliche AC-5-Test (Cross-Tab-Datenverlust-Schutz) prüfte nicht das eigentlich Geforderte — er nutzte `page.goto()` statt eines echten In-Page-Tab-Klicks und hätte damit einen serverseitigen Reload statt der clientseitigen Zustandserhaltung getestet. Der Test wurde korrigiert (echter Tab-Klick innerhalb der Seite), danach war AC-5 ebenfalls CONFIRMED.

**7 Acceptance Criteria** (Name/Region/Aktivitätsprofil sofort sichtbar + persistiert nach Reload; Datenverlust-Schutz bei Teil-Edit; Datenverlust-Schutz Cross-Tab; Mobile-Parität; Fehlerfall mit sichtbarer Fehlermeldung und offenem Eingabefeld) — geprüft vom Adversary-Agent (`implementation-validator`).

**Known Limitations (aus Spec übernommen):**
- Cross-Tab-Datenverlust-Schutz ist strukturell an die bestehende `$effect`-Resync-Logik in `CompareTabs.svelte` gekoppelt, kein eigenständiger Mechanismus dieser Slice.
- Kein optimistisches Locking / keine ETags — Header-Edits laufen unabhängig von der `hubPutQueue`; „letzter Schreiber gewinnt" ist bestehendes, unverändertes Projektverhalten.
- Kein page-weites Verwerfen — jedes Feld committet isoliert und sofort.
- Testid-Duplikation Desktop/Mobile (etabliertes Projektmuster, Sichtbarkeitsfilter in Tests nötig).
- Markup-Duplikation Desktop/Mobile bewusst nicht extrahiert (YAGNI).

Details: `docs/specs/modules/feat_1273_s2_compare_hub_name_region_profil.md`.

---

## Slice S3: Compare-Edit-Route wird reiner Redirect auf den Hub (Issue #1273, Spec `feat_1273_s3_redirect.md`)

**Status:** ✓ Completed 2026-07-17, Adversary-Verdict **AMBIGUOUS** (F001 behoben, danach Verdict-Revision auf verifiziert), alle 7 ACs CONFIRMED.

Biegt die letzten produktiven Zugänge zur alten Bearbeiten-Fläche auf den Hub um und macht `/compare/[id]/edit` — analog zum Trip-Vorbild #616 — zu einem reinen Redirect ohne eigenes Rendering.

**Was gebaut wurde:**

- `/compare/[id]/edit` ist jetzt ein reiner 307-Redirect auf `/compare/[id]` (`frontend/src/routes/compare/[id]/edit/+page.server.ts`), exaktes Vorbild `trips/[id]/edit/+page.server.ts`. Kein Fetch gegen die Python-API mehr, `+page.svelte` auf eine leere Hülle reduziert (SvelteKit-Routing verlangt die Datei weiterhin, rendert sie aber nach `redirect()` nie).
- Alle 7 externen Linkstellen umgebogen: Home-Kachel-Kebab (`CompareKachel.svelte`), Listen-Kebab `setup`+`edit` (`compare/+page.svelte`), Home-Hero-CTA sowie 3 Schnellaktionen (`+page.svelte`) — jede zeigt jetzt auf `/compare/{id}` statt `/compare/{id}/edit`.
- 2 davon vormals hash-basierte Schnellaktionen ("Ideal-Werte ändern", "Briefing-Zeitplan") nutzen jetzt `?tab=idealwerte` bzw. `?tab=versand` statt der zuvor toten Hash-Anker `#idealwerte`/`#schedule` (es gab kein DOM-Element mit diesen IDs) — kein neuer Mechanismus, `CompareTabs.svelte` unterstützt `?tab=` über `initialTab`/`resolve()` bereits seit S1/S2.
- Die dadurch redundanten Hub-eigenen Bearbeiten-Affordanzen entfernt (PO-Entscheid): Desktop-„Bearbeiten"-Button (`data-testid="compare-detail-edit-button"`) und Mobile-Stift-Icon (`aria-label="Bearbeiten"`) in `compare/[id]/+page.svelte` — analog zum Trip-Hub, der ebenfalls keinen separaten „Bearbeiten"-Knopf mehr hat.
- `compareDetailActions()` (`subscriptionHelpers.ts`) liefert keinen `edit`-Eintrag mehr — ist jetzt ein reiner 1:1-Alias auf `compareLifecycleActions(status)`, keine Sonderbehandlung mehr nötig. `compareActions()` (Listen-/Home-Kebab) bleibt bewusst unverändert und liefert weiterhin `edit`/`setup`-Einträge — nur das Linkziel der Aufrufer wurde in Schritt 2 umgebogen.

**Adversary-Fund F001 (MEDIUM, behoben):** Die ursprünglichen AC-2/AC-3-Tests prüften nur per Datei-Grep (`readFileSync` + String-Match), ob `?tab=idealwerte`/`?tab=versand` im Quelltext vorkommen — ohne echten Funktionsaufruf, wie von der Spec für AC-3 explizit gefordert (`resolve('idealwerte')`/`resolve('versand')`). Behoben durch Extraktion von `TABS`/`VALID_VALUES`/`resolve()` aus `CompareTabs.svelte` in eine eigene, testbare Datei `frontend/src/lib/components/compare/compareTabsResolve.ts` (`COMPARE_TABS`/`COMPARE_TAB_VALUES`/`resolveCompareTab()`, verhaltensidentisch); `CompareTabs.svelte` importiert jetzt von dort. Der AC-3-Test ruft `resolveCompareTab()` jetzt direkt auf. F002 (LOW, veralteter Kopf-Kommentar in `CompareKachel.svelte`) bewusst nicht behoben — kosmetisch, Kandidat für Sammel-Issue #1199.

**7 Acceptance Criteria** (307-Redirect ohne CompareEditor-Rendering/404; alle 7 Linkstellen zeigen auf den Hub; die 2 Tab-Schnellaktionen öffnen tatsächlich den jeweiligen Tab; Desktop-Button/Mobile-Stift-Icon entfernt; `compareDetailActions()` ohne edit-Eintrag für alle Status; `compareLifecycleActions()` unverändert ohne edit-Eintrag; Listen-/Home-Kebab funktioniert weiterhin, nur mit neuem Linkziel) — alle CONFIRMED nach Fix.

**Bekannte Grenze (aus Spec übernommen):**
- `CompareEditor.svelte` bleibt vollständig im Repo liegen — nur unerreichbar. Löschung ist explizit **S5**-Scope.
- ~26 e2e-Playwright-Specs sowie weitere Unit-Tests außerhalb von `compareDetailEditActions.test.ts`, die noch aktiv `/compare/[id]/edit` ansteuern, sind durch diese Slice **strukturell rot** (die Route liefert jetzt einen Redirect statt der Editor-Seite). Erwartetes, akzeptiertes Verhalten dieser Slice — Behebung ist **S4**-Scope, bewusst nicht Teil von S3.
- Kein Tab-Query-Passthrough im Redirect selbst (anders als beim Trip-Vorbild) — nicht nötig, da alle bekannten Aufrufer bereits mit dem korrekten Zielpfad inkl. `?tab=` verlinkt werden.

Details: `docs/specs/modules/feat_1273_s3_redirect.md`, Adversary-Dialog: `docs/artifacts/epic-1273-s3-redirect/adversary-dialog.md`.

---

## Slice S5/F2b: Ersatzlose Löschung des Alt-Editors `CompareEditor.svelte` (Issue #1301, Spec `feat_1301_f2b_editor_loeschung.md`)

**Status:** ✓ Completed 2026-07-19, Adversary-verifiziert.

Schließt Epic #1273 ab: der tote Alt-Editor `CompareEditor.svelte` (1.686 Zeilen, unerreichbar seit S3) sowie seine Editor-only-Helfer `compareEditorLogic.ts` und `compareAutosave.ts` samt 3 zugehöriger Testdateien werden gelöscht (−2.103/+96 LoC). `issue_718_idealwert_validation.test.ts` bereinigt (Import auf gelöschtes Modul entfernt) und der Wächter `issue_683_wizard_remove.test.ts` um Wortgrenzen-Abwesenheits-Checks für `CompareEditor.svelte`/`compareEditorLogic.ts`/`compareAutosave.ts` ergänzt (schließt die Substring-Falle `CompareEditor` ~ `CompareNewEditor`).

Die Redirect-Route `/compare/[id]/edit` (307 → Hub) bleibt bewusst bestehen (Trip-Muster #616, `routes/trips/[id]/edit/`) — nur die Editor-**Komponente** wird gelöscht, nicht die Route. `Step2Orte.svelte`, `compareEditorSave.ts`/`compareEditorLoad.ts`, `compareWizardState.svelte.ts`, `compareHubWizardBridge.ts` bleiben unverändert bestehen (weiterverwendet von `CompareNewEditor`/Hub-Save-Pfad).

Details: `docs/specs/modules/feat_1301_f2b_editor_loeschung.md`.

---

## Architecture

### Component Hierarchy (Ziel-Zustand nach S5)

```
frontend/src/routes/compare/
├── new/
│   └── +page.svelte
│       └── (S5/F2: Progressive-Tab-Anlege-Seite nach Trip-Muster #622 aus geteilten
│            Organismen — ersetzt <CompareEditor mode="create">; PO-bekräftigt 2026-07-19)
│
└── [id]/
    ├── +page.svelte
    │   └── <CompareDetail saveController={hubSaveCtl} ... />
    │       └── <CompareTabs saveController={...} />   (DIE einzige Bearbeiten-Fläche)
    │
    └── edit/
        └── +page.svelte                            (✓ S3: reiner Redirect auf /compare/[id]?tab=...; bleibt bestehen, Trip-Muster #616 — S5/F2b löscht nur CompareEditor.svelte selbst)
```

### Speicher-Modell (S1)

`hubPutQueue` (Serialisierung der 5 Netzwerk-Commits, unverändert) **kombiniert** mit einem manuell getriebenen, geteilten `SaveStatus` (`hubSaveCtl`) für den Chip — kein Ersatz von einem durch das andere:

```
[Nutzer-Aktion in einem Tab]
  ↓
saveController?.setSaving()                    // synchron VOR enqueue()
  ↓
hubPutQueue.enqueue(async () => {
  const payload = build...(...);
  if (!payload) return null;                    // No-Op: kein Diff
  try {
    const result = await api.put(...);
    return result;
  } catch (e) {
    // Rollback (unverändert je Handler)
    failure = e;
    return null;
  }
})
  ↓
if (updated)            → saveController?.setSaved()
else if (failure)        → saveController?.setError(extractMessage(failure))
else                      → saveController?.markPristine()   // No-Op, kein neuer Zeitstempel, kein Fehler
```

Präzedenzfall: `TripHeader.svelte` (Trip-Name-Bearbeitung läuft ebenfalls isoliert mit eigenem `api.put()`, nicht über `saveController.schedule()`; der geteilte `saveController` wird dort nur für den Chip mitgerendert) — Vorbild auch für S2 (Name/Region/Aktivitätsprofil im Hub).

---

## Changelog

| Date | Slice | Change |
|------|-------|--------|
| 2026-07-16 | S1 | Save-Chip-Infra im Compare-Hub: `hubSaveCtl` (Routen-Ebene) + `SaveIndicator`-Chip via Thin-Shell-Pass-through (`CompareDetail.svelte`) in `CompareTabs.svelte`. Alle 5 bestehenden Commit-Handler mit `setSaving()`/`setSaved()`/`setError()`/`markPristine()` umwickelt, `hubPutQueue` unverändert für Netzwerk-Serialisierung. Adversary-Verdict VERIFIED. Issue #1273 (Slice 1). Spec: `docs/specs/modules/feat_1273_s1_compare_hub_save_chip.md`. |
| 2026-07-17 | S2 | Name/Region/Aktivitätsprofil inline editierbar im Compare-Hub-Kopfbereich (Desktop + Mobile), TripHeader-Muster (Stift-Icon, isolierter Save-Pfad ohne `saveController`), Round-Trip-Spread-Payload gegen Datenverlust, `data.preset = updated`-Referenzersetzung für Cross-Tab-Resync über bestehenden `$effect` in `CompareTabs.svelte`. Adversary-Verdict AMBIGUOUS→Freigabe nach Test-Fix (AC-5-Test nutzte ursprünglich `page.goto()` statt In-Page-Tab-Klick, korrigiert). 6/7 ACs sofort CONFIRMED, AC-5 nach Fix ebenfalls CONFIRMED. Issue #1273 (Slice 2). Spec: `docs/specs/modules/feat_1273_s2_compare_hub_name_region_profil.md`. |
| 2026-07-17 | S3 | `/compare/[id]/edit` wird reiner 307-Redirect auf `/compare/[id]` (Muster #616), alle 7 externen Linkstellen umgebogen, 2 vormals hash-basierte Schnellaktionen nutzen jetzt `?tab=idealwerte`/`?tab=versand`, redundante Hub-eigene Bearbeiten-Affordanzen (Desktop-Button, Mobile-Stift) entfernt, `compareDetailActions()` liefert keinen `edit`-Eintrag mehr (reiner Alias auf `compareLifecycleActions()`). Adversary-Verdict AMBIGUOUS→behoben: F001 (AC-2/AC-3-Tests nutzten Datei-Grep statt echtem Funktionsaufruf) behoben durch Extraktion von `resolveCompareTab()` in `compareTabsResolve.ts`, alle 7 ACs CONFIRMED. Bekannte Grenze: `CompareEditor.svelte` bleibt toter Code (S5), ~26 e2e-Specs + einzelne Unit-Tests auf `/edit` sind strukturell rot (S4-Scope). Issue #1273 (Slice 3). Spec: `docs/specs/modules/feat_1273_s3_redirect.md`. |
| 2026-07-17 | S4a | 4 von ~26 e2e-Playwright-Specs migriert (nur totes Editor-Chrome/überholte URL, NICHT die vollständige Migration — Korrektur ggü. ursprünglicher Slice-Beschreibung, s. „Geplante Slices" oben). NEU: `compare-cross-user-write-block.spec.ts` (Sicherheitstest User-Isolation, rein API-basiert). GELÖSCHT: `compare-editor-edit.spec.ts` (unerreichbar nach S3-Redirect). Aktualisiert: `bug-626-compare-menu-actions.spec.ts`, `compare-detail-edit-entry.spec.ts`; `compare-editor-autosave-user-isolation.spec.ts` unverändert (selbst strukturell rot, gehört zu S4c). Adversary-Verdict AMBIGUOUS→Override erteilt (F002 gelöst via Draft-Preset-Fixture; F001/F004 kosmetisch). 11 passed, 0 failed, 0 skipped. Verbleibende ~19 e2e-Specs mit gültiger Fachlogik → neue Scheibe S4c. Issue #1273 (Slice 4a). Spec: `docs/specs/modules/epic_1273_s4a_test_migration.md`. |
| 2026-07-17 | S4b | ~15 Unit-Tests migriert/gelöscht: GELÖSCHT 3 Dateien (`compare_editor_gesture_capture_scope.test.ts`, `compare_editor_mobile_fidelity.test.ts`, `compare_editor_layout_tab_wiring.test.ts`). ANGEPASST 2 Dateien (je ein Testblock von `CompareEditor.svelte` auf `CompareTabs.svelte` umgezogen): `step2_orte_library_grouping.test.ts`, `corridorEditorMobile.test.ts`. NACHTRAG 1 Datei: `issue_683_wizard_remove.test.ts` (veralteter S3-Test korrigiert). Gesamt Pytest-Kernlauf: 462/470 Tests grün; 5 Fehlschläge nachweislich unabhängig (#1296, #1268). Adversary-Verdict AMBIGUOUS→Override erteilt (2 kosmetische Spec-Dokumentationsfehler behoben, keine Implementierungsfehler). Issue #1273 (Slice 4b). Spec: `docs/specs/modules/epic_1273_s4b_unit_test_migration.md`. |
| 2026-07-19 | S5/F2b | `CompareEditor.svelte` (1.686 Z.) + `compareEditorLogic.ts` + `compareAutosave.ts` + 3 Testdateien gelöscht (−2.103/+96 LoC). `issue_718_idealwert_validation.test.ts` und Wächter `issue_683_wizard_remove.test.ts` aktualisiert (neue Wortgrenzen-Abwesenheits-Checks). Redirect-Route `/compare/[id]/edit` bleibt bestehen (Trip-Muster #616). Adversary-verifiziert. **Epic #1273 damit abgeschlossen.** Issue #1301 (Scheibe F2b) / #1273 (S5). Spec: `docs/specs/modules/feat_1301_f2b_editor_loeschung.md`. |

---

## Future Work

Keine offenen Slices — Epic #1273 ist mit S5/F2b (2026-07-19) abgeschlossen. F2b schließt zugleich Slice 6 aus Epic #677 ab (dort als „CompareWizard-Deletion, Full Tab-Editor-Umstieg" vermerkt).

