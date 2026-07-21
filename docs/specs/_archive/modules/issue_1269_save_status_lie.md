---
entity_id: issue_1269_save_status_lie
type: bugfix
created: 2026-07-16
updated: 2026-07-16
status: draft
version: "1.0"
tags: [bug, frontend, trip-editor, compare-editor, autosave, save-indicator, epic-1230, epic-1273]
workflow: fix-1269-save-status-lie
---

# Spec: #1269 — Die Speicher-Status-Anzeige lügt (Trip + Ortsvergleich)

## Approval

- [x] Approved — PO Henning, 2026-07-16 („Freigabe" nach Vorlage der 7 ACs inkl. Known Limitations)

## Purpose

Die Speicher-Status-Anzeige (der „● Nicht gespeichert" / „✓ Gespeichert HH:MM"-Chip) lügt in beiden Editoren, in zwei Richtungen:

- **(a) Falsches „● Nicht gespeichert":** Der Nutzer öffnet einen Tab und **fasst nichts an** — trotzdem springt der Chip auf „Nicht gespeichert". (Trip-Inhalt-Tab; Ortsvergleich-Layout-Tab.)
- **(b) Falsches „✓ Gespeichert HH:MM":** Der Chip meldet „gespeichert" mit frischem Zeitstempel, **obwohl kein Speichervorgang zum Server stattfand**. (Ortsvergleich-Editor.)

Beide untergraben das Vertrauen in das Auto-Speichern systemweit — und das ist die **Voraussetzung** für Epic #1273 („Ortsvergleich wird EINE Fläche wie Trip", das voll auf Auto-Speichern setzt).

Beim Nachbohren trat ein **dritter, schwererer Befund** derselben Wurzel zutage, der bisher in keinem Ticket stand (aber in der #1234-Spec als vertagter Zwilling vorhergesagt war):

- **(c) Ungewollter echter Schreibzugriff:** Das bloße Öffnen des Trip-Tabs **„Versand"** (Briefing-Zeitplan) kann einen echten Speichervorgang zum Server (`PUT /api/trips/{id}`) auslösen, **ohne jede Nutzergeste** — und bei Fehlschlag einen „Fehler beim Speichern"-Banner zeigen, den der Nutzer nie ausgelöst hat.

**Gemeinsame Wurzel:** Beim Öffnen eines Tabs normalisiert/hydratisiert eine (Unter-)Komponente die Konfiguration und schreibt sie zurück (z. B. `"07:00"` → `"07:00:00"`, Ergänzung fehlender Felder). Für die „geändert?"-Erkennung ist diese **maschinelle** Änderung von einer **Nutzeränderung** nicht zu unterscheiden. Weil drei Editor-Flächen den Speicher-/„geändert"-Zustand **uneinheitlich** verwalten, zeigt sich dieselbe Wurzel drei Mal verschieden.

**Diese Spec löst das Thema einmal und wartbar für Trip UND Ortsvergleich** (PO-Vorgabe 2026-07-16, Wartbarkeit als oberste Maxime), indem alle Flächen konsequent durch **dieselben, bereits vorhandenen geteilten Bausteine** geführt werden — kein neuer Sonderweg.

## Source

**Geteilte Bausteine (existieren, gut entworfen — bleiben die Single Source of Truth):**
- **File:** `frontend/src/lib/stores/saveStatusStore.svelte.ts`
  - **Identifier:** `class SaveStatus` — Zustandsmaschine (`idle|dirty|saving|error`, `savedAt`). Regel-Verschärfung: `setSaved()` (stempelt `savedAt`) ist ausschließlich über `doSave()` nach erfolgreichem `saveFn()` erreichbar. Ggf. additiv: eine „clean-ohne-Neustempeln"-Transition (dirty→idle ohne `savedAt`-Update), falls die Anzeige clean werden muss, ohne einen Save vorzutäuschen.
- **File:** `frontend/src/lib/components/trip-detail/weatherSaveGate.ts`
  - **Identifier:** `weatherSaveGate(input): 'save' | 'skip'` — reines Schreib-Gate (`catalogLoaded && userTouched`). Context-agnostisch, unit-testbar ohne Mocks.
- **File:** `frontend/src/lib/components/compare/compareAutosave.ts`
  - **Identifier:** `computeCompareAutoSaveAction()` — reused `weatherSaveGate` bereits.

**Zu ändernde Flächen:**
- **File:** `frontend/src/lib/components/compare/CompareEditor.svelte`
  - **Identifier:** Dirty-Sync-`$effect` (Z. ~237-243) — **(b):** das unbedingte `compareSaveCtl.setSaved()` (Z. ~240-241) bei dirty→clean umgehen; `setSaved` darf nur aus echtem PUT-Erfolg kommen. **(a):** Mount-Baseline `initial` (Z. ~163-205) vs. `channelLayouts`-Rewrite (Z. ~728-741) so korrigieren, dass die Mount-Kanonisierung keinen Diff erzeugt.
- **File:** `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte`
  - **Identifier:** reportConfig-Watch-`$effect` (Z. ~507-513) / Baseline `_lastReportConfigJson` (Z. ~506/270) — **(a):** Baseline auf die kanonisierte Editier-Form setzen, damit die Mount-Normalisierung kein „dirty" erzeugt.
- **File:** `frontend/src/lib/components/trip-detail/BriefingScheduleTab.svelte`
  - **Identifier:** reportConfig-Watch-`$effect` (Z. ~56-70), der `saveController.doSave(...)` **ohne Gate** ruft — **(c):** hinter das Schreib-Gate `weatherSaveGate` (userTouched) legen.
- **File:** `frontend/src/lib/components/shared/VersandTab.svelte` (**geteilter Code**, context `route`|`vergleich`)
  - **Identifier:** Mount-Write-Back-`$effect` (Z. ~110-130) — **(c):** die Mount-Kanonisierung darf keinen ungewollten Save auslösen; einheitliche Baseline-/Geste-Behandlung wie oben.
- **File (evtl.):** `frontend/src/lib/components/edit/EditReportConfigSection.svelte`
  - **Identifier:** Mount-Normalisierungs-Write-Back (Z. ~174-216) — Quelle des Trip-(a)-Diffs; falls nötig idempotent machen bzw. Baseline-Kopplung.

> **PFLICHT — Schicht-Hinweis:** Ausschließlich **Frontend** (`frontend/src/...`, SvelteKit). Der Bug entsteht im Client (Anzeige-Zustand + Auto-Save-Trigger). Go-API und Python-Core sind **geprüft nicht betroffen** — es geht um Client-Zustandsführung, nicht um Serverlogik.

## Estimated Scope

- **LoC:** ~150–220 (inkl. Tests). Mehrere Flächen, aber überwiegend Verdrahtung an vorhandene Bausteine + Baseline-Korrektur. **LoC-Limit 250 — voraussichtlich kein Override nötig**; falls die Baseline-Korrektur breiter ausfällt, wird ein Override **vorher** mit dem PO abgestimmt.
- **Files:** 4–5 geändert, 0–1 neu (nur falls eine Baseline-Kanonisierung als geteilte Helper-Funktion extrahiert wird), 2–3 Testdateien.
- **Effort:** medium.

Backend (Go + Python): **keine Änderung.**

## Dependencies

| Komponente | Grund | Status |
|---|---|---|
| `stores/saveStatusStore.svelte.ts` | Zustandsmaschine, Single Source of Truth für den Speicher-Zustand | benutzt; ggf. additive Transition |
| `trip-detail/weatherSaveGate.ts` | Schreib-Gate — soll ALLE drei Flächen gaten | benutzt (Versand neu angebunden) |
| `compare/compareAutosave.ts` | Compare-Wrapper um das Gate | benutzt, unverändert |
| `compare/CompareEditor.svelte` | (a)+(b) | wird geändert |
| `trip-detail/WeatherMetricsTab.svelte` | (a) Trip-Inhalt | wird geändert |
| `trip-detail/BriefingScheduleTab.svelte` | (c) ungated `doSave` | wird geändert |
| `shared/VersandTab.svelte` | (c) Mount-Write-Back; **geteilt** route+vergleich | wird geändert |
| `edit/EditReportConfigSection.svelte` | Quelle Trip-(a)-Diff | evtl. geändert |
| Bezug: #1234 (`issue_1234_autosave_hydration_gate.md`) | hat (c) als „latente Zwillinge" vertagt (Known Limitations) | wird hier eingelöst |

## Implementation Details

**Leitprinzip (aus #1234 bestätigt, Best Practice belegt in `docs/context/fix-1269-save-status-lie.md`):**
Programmatische (Mount-)Änderungen sind **keine** Nutzerabsicht. Die **Anzeige** darf im Zweifel konservativ „nicht gespeichert" zeigen; ein **Schreibzugriff** darf **nie** ohne Nutzergeste passieren. Diese beiden Regeln scheitern asymmetrisch-sicher (siehe *Robustheits-Invariante*).

**Drei Änderungen, je eigene, nicht redundante Aufgabe — alle auf die vorhandenen geteilten Bausteine gestützt:**

1. **Zustandsmaschine strikt einhalten (fixt (b)).** `setSaved()` (das `savedAt` stempelt) wird ausschließlich aus `doSave()` nach erfolgreichem PUT erreicht. Der einzige PUT-lose `setSaved()`-Aufruf im gesamten Frontend (`CompareEditor.svelte:~241`) entfällt. Wenn der Dirty-Zustand ohne Save auf „clean" zurückgeht (Nutzer macht eine Änderung manuell rückgängig), zeigt die Anzeige „gespeichert/idle" **ohne** den Zeitstempel neu zu setzen — kein vorgetäuschter Speichervorgang.

2. **Schreib-Gate auf ALLEN Flächen (fixt (c)).** Jeder Auto-Save-Trigger läuft durch `weatherSaveGate` (`catalogLoaded && userTouched`): Trip-Inhalt ✅ (heute schon), Ortsvergleich ✅ (heute schon via `compareAutosave`), **Trip-Versand — heute GAR NICHT gegatet** → wird angebunden. Damit kann das bloße Öffnen des Versand-Tabs keinen echten PUT mehr auslösen.

3. **Baseline-Korrektheit (fixt (a)) — NICHT durch Gating der Anzeige.** Die „clean"-Vergleichsbasis muss die **kanonisierte** (post-Normalisierungs-)Editier-Form sein, damit die Mount-Kanonisierung keinen Diff erzeugt. Der Diff wird dort neutralisiert, wo beim Laden normalisiert wird (Compare-Layout, Trip-Inhalt, Versand) — deterministisch, ereignis-gebunden, **nicht** timing-flag-gebunden. **Ausdrücklich verworfen:** `setDirty` an `userTouched` koppeln (würde bei einem übersehenen Gesten-Signal die Anzeige fälschlich auf „gespeichert" setzen, während echte Änderungen ungespeichert bleiben → stiller Datenverlust; genau die Fehlerklasse, vor der #1234 warnt).

**Wartbarkeit (PO-Maxime, Trip/Compare-Teilungs-Invariante):** Es entsteht **kein** vierter Sonderweg. Alle Flächen nutzen dieselbe Zustandsmaschine (`SaveStatus`) und dasselbe Schreib-Gate (`weatherSaveGate`). Falls die Baseline-Kanonisierung an mehreren Stellen identisch gebraucht wird, wird sie **einmal** als reine Helper-Funktion extrahiert (unit-testbar ohne Mocks), nicht pro Fläche kopiert. „Hätte das ein geteilter Baustein sein müssen?" ist im Adversary-/Review-Schritt ein Pflicht-Prüfpunkt.

**Robustheits-Invariante (der Grund, warum das sicher ist):** Anzeige und Schreiben scheitern in **entgegengesetzte, jeweils sichere** Richtung — die Anzeige zeigt im Zweifel „nicht gespeichert" (nie fälschlich „gespeichert"), der Schreibzugriff unterbleibt im Zweifel (nie ungewollt). Deshalb muss **keiner** der beiden Mechanismen perfekt sein: Ein evtl. übersehenes Gesten-Signal (F003/F004-Klasse: Slider-Griffe, Drag) führt höchstens dazu, dass kein Auto-Save feuert — die ehrliche „nicht gespeichert"-Anzeige bleibt das Sicherheitsnetz, über das der Nutzer manuell speichern kann.

## Expected Behavior

| Situation | Heute (Bug) | Nach dem Fix |
|---|---|---|
| Ortsvergleich: Layout-/Versand-Tab öffnen, nichts anfassen | Chip → „● Nicht gespeichert" | Chip bleibt „✓ Gespeichert" (nichts geändert) |
| Ortsvergleich: Chip springt auf „Gespeichert HH:MM" | ohne dass ein PUT stattfand | „Gespeichert HH:MM" nur nach echtem, erfolgreichem PUT |
| Trip: Inhalt-Tab öffnen, nichts anfassen | Chip → „● Nicht gespeichert" | Chip bleibt „✓ Gespeichert" |
| Trip: **Versand**-Tab öffnen, nichts anfassen | **echter PUT** auf `/api/trips/{id}`, evtl. Fehler-Banner | kein PUT, kein Banner |
| Beliebige echte Nutzeränderung (Trip + Vergleich) | Auto-Speichern + Chip-Verlauf | unverändert: „Nicht gespeichert" → „Speichere…" → „Gespeichert HH:MM" |
| Echte Änderung via Slider/Drag (Gesten-Erfassung übersieht sie) | — | Chip zeigt ehrlich „Nicht gespeichert"; nie fälschlich „gespeichert" |

## Test Plan

| Test | Schicht | Prüft |
|---|---|---|
| `saveStatus.test.ts` (erweitert) | Kern (Vitest, keine Mocks) | `setSaved` stempelt `savedAt` nur via `doSave`-Erfolg; dirty→clean-ohne-Save setzt keinen neuen `savedAt` |
| `weatherSaveGate.test.ts` (unverändert) | Kern | Gate-Entscheidungstabelle (Regression) |
| `save-indicator-trip.spec.ts` | Playwright (Staging) | (a) Trip-Inhalt öffnen, nichts klicken → Chip bleibt „gespeichert"; (c) Versand-Tab öffnen → **null** PUTs, kein Fehler-Banner |
| `save-indicator-compare.spec.ts` | Playwright (Staging) | (a) Compare-Layout/Versand öffnen → Chip bleibt „gespeichert"; (b) → nie „Gespeichert HH:MM" ohne PUT |
| dito (beide) | Playwright | Regression: echte Änderung → Chip-Verlauf korrekt, nach Reload persistiert; Trip- und Compare-Verhalten identisch in äquivalenter Situation |

**RED-Nachweis:** (a) und (c) müssen den Mount-Effekt deterministisch treffen (Tab öffnen, Netzwerk-/Chip-Zustand über Debounce hinaus beobachten), vor dem Fix rot, nach dem Fix grün. Vor Implementierung empirisch verifizieren, ob Trip-„Wertebereiche"/„Alarme" (a) **unabhängig** vom Inhalt-Tab auslösen (bestimmt die Zahl der Baseline-Fixstellen).

## Acceptance Criteria

- **AC-1:** Given ein Ortsvergleich im Bearbeiten-Modus ohne ungespeicherte Änderungen / When der Nutzer einen Tab (z. B. Layout oder Versand) öffnet und **nichts** eingibt / Then zeigt die Speicher-Anzeige **nicht** „● Nicht gespeichert", sondern bleibt im gespeicherten Zustand — das bloße Ansehen eines Tabs erzeugt keinen „geändert"-Status.
  - Test: Playwright/Staging — Compare mit gespeichertem Stand öffnen, Layout-Tab anklicken, 3 s warten (> Debounce), Chip-Text ablesen: bleibt „✓ Gespeichert" / nie „● Nicht gespeichert". Wiederholung für Versand-Tab.

- **AC-2:** Given ein Ortsvergleich im Bearbeiten-Modus / When die Anzeige „✓ Gespeichert HH:MM" zeigt / Then entspricht dieser Zeitstempel einem **tatsächlich erfolgten, erfolgreichen** Speichervorgang zum Server — die Anzeige zeigt niemals „gespeichert" mit frischem Zeitstempel ohne vorausgegangenen echten Speichervorgang.
  - Test: Playwright/Staging — Netzwerk-Mitschnitt aktiv; Tabs öffnen/wechseln ohne Eingabe → über den gesamten Ablauf springt der Chip **nicht** auf ein neues „Gespeichert HH:MM", solange kein `PUT` mit 2xx im Mitschnitt steht.

- **AC-3:** Given ein Trip / When der Nutzer den Tab „Inhalt" (sowie „Wertebereiche" / „Alarme") öffnet und **nichts** eingibt / Then zeigt die Speicher-Anzeige **nicht** „● Nicht gespeichert".
  - Test: Playwright/Staging — Trip öffnen, Inhalt-Tab anklicken, 3 s warten, Chip ablesen: kein „Nicht gespeichert". Verifizieren, ob Wertebereiche/Alarme unabhängig betroffen sind.

- **AC-4:** Given ein bestehender Trip / When der Nutzer den Tab „Versand" (Briefing-Zeitplan) öffnet, **nichts** eingibt, die Auto-Speicher-Verzögerung abwartet und den Tab wechselt / Then wird **kein** Speichervorgang auf den Trip ausgelöst (kein `PUT /api/trips/{id}`) und **kein** „Fehler beim Speichern"-Banner angezeigt.
  - Test: Playwright/Staging — Netzwerk-Mitschnitt über den gesamten Ablauf: **null** PUT-Requests auf `/api/trips/{id}`; Fehler-Banner nicht sichtbar.

- **AC-5:** Given ein Editor (Trip oder Ortsvergleich) ist vollständig geladen / When der Nutzer eine echte Änderung macht (Metrik/Wert/Zeit/Kanal ändern) / Then durchläuft die Anzeige wie bisher „● Nicht gespeichert" → „Speichere…" → „✓ Gespeichert HH:MM", die Änderung wird gespeichert und bleibt nach Seiten-Neuladen erhalten — die bestehende Auto-Speicher-Funktion bleibt vollständig erhalten.
  - Test: Playwright/Staging — je einmal Trip und Compare: eine echte Änderung → Chip-Verlauf beobachten, Debounce abwarten, Seite neu laden → Änderung persistiert.

- **AC-6:** Given eine echte Nutzeränderung wird über eine Interaktion gemacht, die die Gesten-Erfassung möglicherweise nicht erfasst (z. B. Schieberegler-Griff, Drag-Umsortierung) / When kein Auto-Speichern feuert / Then zeigt die Anzeige **weiterhin** „● Nicht gespeichert" (niemals fälschlich „gespeichert") — keine echte Änderung wird jemals still als gespeichert ausgegeben; der Nutzer kann manuell speichern.
  - Test: Playwright/Staging — eine Änderung per Slider-/Drag-Interaktion auslösen; falls kein PUT feuert, prüfen: Chip zeigt „Nicht gespeichert", **nicht** „Gespeichert". (Sicherheits-Invariante — verhindert stillen Datenverlust.)

- **AC-7:** Given äquivalente Situationen in Trip- und Ortsvergleichs-Editor / When dieselbe Nutzeraktion ausgeführt wird (Tab öffnen ohne Eingabe; echte Änderung) / Then verhält sich die Speicher-Anzeige in beiden Editoren **gleich** — dieselbe zugrunde liegende Mechanik, kein flächen-eigener Sonderweg.
  - Test: Parallel-Prüfung der Szenarien AC-1/AC-3 und AC-5 in beiden Editoren; identisches beobachtbares Verhalten. Struktur-Prüfpunkt im Review/Adversary: beide Flächen nutzen `SaveStatus` + `weatherSaveGate`, keine dritte Dirty-/Save-Mechanik.

## Known Limitations

- **Der Schutz liegt im Client.** Wie bei #1234 verhindert der Fix, dass der Client ohne Nutzergeste schreibt; das Backend akzeptiert weiterhin, was ihm der Client schickt. Eine serverseitige Absicherung ist nicht Teil dieses Bugfixes.
- **Manueller Revert vor Auto-Save:** Macht der Nutzer eine Änderung und setzt sie manuell auf den Ausgangswert zurück, bevor der debounced Save feuert, kann ein idempotenter No-Op-PUT abgehen (unschädlich) bzw. die Anzeige geht auf „gespeichert/idle" ohne neuen Zeitstempel. Kein Datenverlust, kein falscher „gespeichert"-Zeitstempel.
- **Gesten-Erfassung bleibt nicht garantiert lückenlos** (F003/F004-Historie). Das ist bewusst toleriert, weil die Robustheits-Invariante den Fehlerfall sicher abfängt (ehrliche „nicht gespeichert"-Anzeige statt stillem Verlust). Eine handler-basierte statt DOM-capture-basierte Geste-Erfassung wäre robuster, ist aber ein größerer Umbau und nicht Teil dieses Fixes.

## Architektur-Entscheidung (ADR)

**ADR-Nr.:** keine

**Keine neue ADR erforderlich.** Diese Spec trifft keine neue Architektur-Entscheidung, sondern **konsolidiert auf bestehende**: die Zustandsmaschine `SaveStatus` (#758/#880) und das Schreib-Gate `weatherSaveGate` (#1234) werden zur einheitlichen Mechanik für alle Editor-Flächen (Trip + Ortsvergleich) gemacht. Das entspricht der bestehenden Trip/Compare-Teilungs-Invariante (CLAUDE.md) und der #1234-Grundregel „ohne Nutzergeste kein Schreibzugriff". Die in #1234 Known Limitations vertagten „latenten Zwillinge" (Versand/BriefingSchedule) werden hier eingelöst.

## Changelog

| Datum | Version | Änderung |
|---|---|---|
| 2026-07-16 | 1.0 | Erstfassung. Scope per PO-Entscheid = eine wartbare Lösung für Trip + Ortsvergleich (Wartbarkeit oberste Maxime). Adversary-Challenge (analysis-challenger) hat die ursprüngliche Fix-Hypothese („setDirty an userTouched koppeln") als Silent-Data-Loss-Risiko verworfen und den dritten Befund (c) (ungewollter Versand-PUT) aufgedeckt — in #1234 bereits als vertagter Zwilling vorhergesagt. Design: Konsolidierung auf die zwei vorhandenen geteilten Bausteine + Baseline-Korrektheit, gestützt auf die Robustheits-Invariante. |
