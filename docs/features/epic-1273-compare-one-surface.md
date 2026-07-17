# Epic 1273: Ortsvergleich auf EINE Fläche

**Status:** In Progress (Slice 1 Complete — 2026-07-16)
**Epic Scope:** Der Ortsvergleich-Hub (`CompareTabs.svelte`) wird nach dem Muster von #616 (Trip-IA) zur **einzigen** Bearbeiten-Fläche für einen Ortsvergleich — vollständig editierbar mit Auto-Save-Chip (`SaveStatus`/`SaveIndicator`, „✓ Gespeichert HH:MM"). Der separate Editor `/compare/[id]/edit` (`CompareEditor.svelte`, aus Epic #677) entfällt am Ende der Migration. Der Create-Wizard (`/compare/new`) bleibt unverändert bestehen.
**Related Specs:**
- `docs/specs/modules/feat_1273_s1_compare_hub_save_chip.md` (Slice S1 — Save-Chip-Infra) — Approved, VERIFIED
- `docs/context/epic-1273-compare-one-surface.md` (Kontext-/Analyse-Dokument, Scheiben-Schnitt)

**Child Slices:** S1 ✓ (2026-07-16) · S2 offen · S3 offen · S4a/S4b offen · S5 offen

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
| **S2** | Name/Region/Aktivitätsprofil-Parität im Hub (TripHeader-Muster: isoliert, nicht über `schedule()`) — Feature-Paritäts-Lücke, Muss-Blocker vor jedem Redirect | Geplant |
| **S3** | 7 produktive Link-Stellen auf den Hub umbiegen (inkl. Hash→Query-Fix `#idealwerte`→`?tab=idealwerte`, `#schedule`→`?tab=versand`) + Redirect-Route (`/edit` → `/compare/[id]?tab=`) | Geplant |
| **S4a** | ~26 e2e-Playwright-Specs von `CompareEditor.svelte`/der Edit-Route auf den Hub migrieren (ggf. Teil-Slices) | Geplant |
| **S4b** | ~15 Unit-Tests (Source-Inspection auf `CompareEditor.svelte`) migrieren/löschen | Geplant |
| **S5** | Cleanup: `CompareEditor.svelte` + `/edit`-Route löschen, verwaiste Helper prüfen (netto ~-1900 LoC, Sonderfall wie #616) | Geplant |

**Reihenfolge:** S1 → S2 → S3 → (S4a/S4b parallel) → S5. Nach jeder Scheibe ist die App voll funktionsfähig — additiv bis S3, S3 macht die alte Route zum reinen Redirect ohne Codelöschung (sicherer Rollback-Punkt), S4 ist reine Testarbeit, S5 räumt erst auf wenn alles grün ist.

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

## Architecture

### Component Hierarchy (Ziel-Zustand nach S5)

```
frontend/src/routes/compare/
├── new/
│   └── +page.svelte
│       └── <CompareEditor mode="create" />        (bleibt — Create-Wizard unverändert)
│
└── [id]/
    ├── +page.svelte
    │   └── <CompareDetail saveController={hubSaveCtl} ... />
    │       └── <CompareTabs saveController={...} />   (DIE einzige Bearbeiten-Fläche)
    │
    └── edit/
        └── +page.svelte                            (S3: reiner Redirect auf /compare/[id]?tab=...; S5: Route gelöscht)
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

---

## Future Work

- **S2:** Name/Region/Aktivitätsprofil-Parität im Hub (Muss-Blocker vor jedem Redirect).
- **S3:** 7 Link-Stellen umbiegen + Redirect-Route `/compare/[id]/edit` → `/compare/[id]?tab=`.
- **S4a/S4b:** Test-Migration (~26 e2e-Specs, ~15 Unit-Tests) weg von `CompareEditor.svelte`.
- **S5:** `CompareEditor.svelte` + `/edit`-Route löschen — schließt zugleich Slice 6 aus Epic #677 ab (dort als „CompareWizard-Deletion, Full Tab-Editor-Umstieg" vermerkt).

