---
entity_id: etappen_bauliche_aenderung_speichern
type: module
created: 2026-10-18
updated: 2026-10-18
status: implemented
version: "1.0"
workflow: fix-2213-etappen-bauliche-aenderung-speichern
tags: [frontend, trip-editor, auto-save, etappen, kaskade, datenverlust]
---

# Etappen-Editor speichert bauliche Änderungen im Auto-Save-Modus (#2213)

- **Issue:** #2213 (aus Sammel-Issue #1199, Befund B2-07; B2-03/B2-04 sind durch #2288 erledigt)
- **Typ:** Bug (stiller Datenverlust, nutzersichtbar)

## Approval

- [ ] Approved

## Purpose

Im Trip-Detail (Etappen-Tab) gibt es keinen Speichern-Knopf; Änderungen werden automatisch gespeichert.
Mehrere „bauliche" Handlungen (Etappe hinzufügen oder löschen, Pausentag einfügen, Klick ins Höhenprofil,
Wegpunkt umbenennen oder löschen) ändern aber nur den Bildschirmstand und stoßen kein Speichern an.
Die Änderung ist auch nicht vorgemerkt, sodass weder ein Seitenwechsel noch ein Tab-Wechsel sie rettet:
Sie geht still verloren. Diese Spec legt fest, dass jede dieser Handlungen im Auto-Save-Modus sofort
gespeichert wird, ohne die Rückfrage zur Datumsverschiebung zu umgehen.

## Source

- **File:** `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` (einziger Änderungsort der Logik)
- **Identifier:** neuer Helfer `speichereBaulicheAenderung`; betroffene Handler `handleMobileAddPause`
  (:86), `handlePauseInsert` (:522), `confirmRemoveStage` (:530), `handleAddStage` (:560),
  `handleProfileAdd` (:568), `makeRenameHandler` (:609), `makeDeleteHandler` (:623),
  Vorlage `handleReorderEnd` (:496, #2288)
- **Nur falls die Sperre es braucht:** `WaypointCard`- bzw. Höhenprofil-Komponente erhält ein
  `disabled`-Prop.
- **Tests (neu):** Kern-Test unter `frontend/src/lib/components/trip-detail/__tests__/` und
  `frontend/e2e/etappen-bauliche-aenderung-speichert.spec.ts`.

> **Schicht:** ausschließlich Frontend (`frontend/src`, `frontend/e2e`). Kein Go, kein Python, keine
> Schema- oder Persistenzänderung. Der Go-Handler `UpdateTripHandler` nimmt eine leere Etappe an
> (`internal/handler/trip_write_test.go:63`) — keine Backend-Änderung nötig.

## Scope

**In Scope (alle in `EditStagesPanelNew.svelte`):**

- Etappe löschen (Lösch-Dialog)
- Etappe hinzufügen: Strip „+ Etappe" (Desktop) und „+ Etappe" (Mobil)
- Pausentag einfügen: Strip-Lücke (Desktop) und Pausentag-Auswahl (Mobil)
- Klick ins Höhenprofil (fügt einen Wegpunkt ein)
- Wegpunkt umbenennen und Wegpunkt löschen
- Umsortieren (#2288) nutzt künftig denselben Helfer; sein Verhalten bleibt unverändert.
- Nebenbefund: die Zeile `if (saveController?.hasPending) deferSave()` in `confirmRemoveStage` (:557)
  entfällt zugunsten des Helfers. Sie wandelt heute einen entprellten Speichervorgang ohne offene
  Rückfrage in einen zurückgestellten ohne Zeitgeber um, der erst beim Verlassen der Seite feuert.

**Out of Scope:**

- `TripNewEditor` (Neuanlage): nutzt das Panel ohne `tripId`/`saveController` und speichert weiterhin
  nicht automatisch.
- Knopf-Modus (`showSave` ohne `saveController`): speichert weiterhin nur per Knopf.
- Backend (Go/Python), Datenformat.
- Etappe umbenennen bleibt entprellt (`scheduleSave`, Texteingabe).
- Datum und Startzeit ändern: Verhalten unverändert (`handleDateChange`, `handleStartTimeChange`).
- Kaskaden-Logik selbst (`applyCascade`, `dismissCascade`) bleibt unverändert.

## Estimated Scope

- **LoC:** produktiv ca. +40 / −10 (Tests ca. +200, zählen nicht ins Limit)
- **Files:** 1 produktive Datei (ggf. +1–2 für ein `disabled`-Prop), 2 neue Testdateien
- **Effort:** medium (Risiko MEDIUM: verzahnt mit der Rückfrage zur Datumsverschiebung, #1389/#1390/#1393)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `saveController` (`saveStatusStore.svelte.ts`) | Store | `doSave`, `cancel`, `defer`, `hasPending` |
| `deferSave()` | Panel-Funktion | merkt den aktuellen Stand neu vor, schreibt nicht sofort |
| `settleMootCascade` / `dismissCascade` | Panel-Funktion | löst eine gegenstandslose Rückfrage auf; `dismissCascade` schreibt dabei selbst |
| `cascadeBusy` | Panel-Zustand | Riegel, solange eine Kaskade angewendet wird |
| `enqueueTripWrite` (`api.ts`) | Warteschlange | serialisiert PUTs pro Trip, If-Match wird erst in der Warteschlange gelesen |
| `beforeNavigate`-Flush, Tab-Wechsel-Flush | Bestand | retten nur Vorgemerktes (`hasPending`) |

## Technischer Ansatz (Variante A: sofort schreiben, ein gemeinsamer Helfer)

Verworfen: Variante B (entprellt, 700 ms). Sie wäre eine zweite Regel neben dem Umsortieren (#2288);
„eine abgeschlossene Handlung" soll genau eine Regel haben. Die Mehrlast bei Serien von Profil-Klicks
(mehrere PUTs) ist wegen der Schreib-Warteschlange unkritisch (kein Stand-Konflikt).

1. Jeder bauliche Handler liest **vor** der Änderung `warOffen = cascade !== null && !cascade.done`,
   ändert `stages` und ruft dann `speichereBaulicheAenderung(warOffen)`.
2. Der Helfer wird aus `handleReorderEnd` herausgelöst (dieses nutzt ihn ebenfalls) und hat drei Zweige:
   - **Kein `saveController` oder keine `tripId`** (Knopf-Modus, Neuanlage): nichts tun.
   - **Rückfrage ist weiterhin offen:** `deferSave()`, also den aktuellen Stand neu vormerken, nicht schreiben.
   - **Sonst:** `saveController.cancel()` und `void saveController.doSave(buildStagesSave())`;
     **Ausnahme:** hat `settleMootCascade` → `dismissCascade` den Stand soeben schon geschrieben, folgt
     **kein** zweiter Speichervorgang.
3. Die Unterscheidung „`dismissCascade` hat geschrieben" gegenüber „Rückfrage ohne Schreiben verworfen"
   (Auslöser-Etappe gelöscht ⇒ `cascade = null`, es wurde nichts geschrieben) wird über ein **explizites
   Signal** (Rückgabewert von `settleMootCascade`/`dismissCascade`) getroffen und nicht aus `warOffen`
   erraten.
4. **Sperre:** `handleProfileAdd`, `makeRenameHandler` und `makeDeleteHandler` erhalten
   `if (cascadeBusy) return` wie die Strip-Handler. Zusätzlich sind Höhenprofil-Fläche und
   Wegpunkt-Aktionen während `cascadeBusy` **sichtbar** gesperrt (reduzierte Deckkraft, nicht klickbar,
   `aria-busy`/`disabled`) — ein stillschweigend ignorierter Klick wäre derselbe stille Verlust.
   Begründung gegen „nach der Kaskade vormerken": `applyCascade` schreibt aus einer festgehaltenen
   Grundlage und ruft im Fehlerfall `cancel()`; ein in dieses Fenster gelegter Speichervorgang würde
   verworfen oder liefe gegen den Kaskaden-Stand. Sperren ist die etablierte Linie (R5-F001), das
   Fenster ist kurz (Obergrenze 15 s).
5. Wegpunkt umbenennen ist eine einmalige Eingabe (Abfragedialog) und wird sofort geschrieben, nicht
   entprellt.

## Expected Behavior

- **Input:** eine der in Scope genannten Handlungen im Etappen-Tab eines bestehenden Trips (Auto-Save-Modus).
- **Output:** der neue Stand liegt nach der Handlung auf dem Server; ein Neuladen zeigt ihn.
- **Side effects:** genau ein Speichervorgang je Handlung (außer bei vorgemerktem Stand, s. AC-7); bei
  offener Rückfrage zur Datumsverschiebung wird nur vorgemerkt und beim Beantworten bzw. Verlassen
  geschrieben.

## Acceptance Criteria

- **AC-1:** Given ein bestehender Trip ist im Etappen-Tab geöffnet (Desktop, ohne Speichern-Knopf) und
  keine Rückfrage zur Datumsverschiebung ist offen / When ich eine Etappe hinzufüge, einen Pausentag
  einfüge oder eine Etappe über den Lösch-Dialog lösche / Then wird der neue Stand sofort einmal
  gespeichert, ohne Speichern-Knopf und ohne Seitenwechsel, und nach dem Neuladen ist die Änderung
  vorhanden.
  - Test: Kern-Test (je Handler genau ein PUT mit neuem Stand) + Playwright Desktop: Hinzufügen und
    Löschen → Neuladen → Stand erhalten.

- **AC-2:** Given ein bestehender Trip ist in der mobilen Ansicht des Etappen-Tabs geöffnet / When ich
  über „+ Etappe" eine neue Etappe oder einen Pausentag anlege oder eine Etappe lösche / Then wird der
  neue Stand sofort gespeichert und ist nach dem Neuladen vorhanden.
  - Test: Kern-Test (`handleMobileAddPause`, `handleAddStage`) + Playwright mobil (Viewport klein).

- **AC-3:** Given ein bestehender Trip ist im Etappen-Tab geöffnet und eine Etappe hat ein Höhenprofil
  mit Wegpunkten / When ich ins Höhenprofil klicke (neuer Wegpunkt) oder einen Wegpunkt umbenenne oder
  lösche / Then wird der neue Stand sofort gespeichert und nach dem Neuladen zeigt die Etappe den
  geänderten Wegpunkt-Stand.
  - Test: Kern-Test (`handleProfileAdd`, Umbenennen-/Lösch-Handler: je ein PUT mit neuem Wegpunkt-Stand).

- **AC-4:** Given der Trip wird im Knopf-Modus (Speichern-Knopf sichtbar, kein Auto-Save) oder in der
  Neuanlage bearbeitet / When ich eine Etappe hinzufüge, lösche, einen Pausentag einfüge oder ins
  Höhenprofil klicke / Then wird nichts automatisch gespeichert; gespeichert wird weiterhin nur über den
  Speichern-Knopf bzw. die Anlage-Schaltfläche.
  - Test: Kern-Test ohne `saveController` ⇒ 0 PUT; bestehender TripNewEditor-Test bleibt grün.

- **AC-5:** Given die Rückfrage zur Datumsverschiebung ist offen („Lückenlos anschließen" / „Nur diese
  Etappe") / When ich eine Etappe hinzufüge, einen Pausentag einfüge oder eine Folge-Etappe lösche und
  die Rückfrage dabei offen bleibt / Then wird nichts an der Rückfrage vorbei geschrieben, die Änderung
  ist vorgemerkt, und sie geht beim Beantworten der Rückfrage oder beim Verlassen der Seite bzw. beim
  Tab-Wechsel nicht verloren.
  - Test: Kern-Test (offene Rückfrage ⇒ 0 PUT, `hasPending` wahr, nach Flush/Antwort ein PUT mit
    neuem Stand).

- **AC-6:** Given die Rückfrage zur Datumsverschiebung ist offen, weil ich das Datum einer Etappe
  geändert habe / When ich genau diese auslösende Etappe lösche / Then verschwindet die Rückfrage, und
  es erfolgt genau ein Speichervorgang, der die gelöschte Etappe nicht mehr enthält (die Etappe
  erscheint nach dem Neuladen nicht wieder).
  - Test: Kern-Test (genau 1 PUT ohne die Etappe, Rückfrage weg, nichts vorgemerkt).

- **AC-7:** Given die Rückfrage zur Datumsverschiebung ist offen und betrifft mehrere Folge-Etappen /
  When ich die letzte Folge-Etappe lösche, sodass die Rückfrage gegenstandslos wird / Then erfolgt genau
  ein Speichervorgang (kein doppelter) mit dem Stand ohne die gelöschte Etappe.
  - Test: Kern-Test (PUT-Zählung exakt 1; Mutation „Helfer schreibt zusätzlich" macht den Test rot).

- **AC-8:** Given ich habe das Datum einer Etappe geändert, es ist keine Rückfrage zur Datumsverschiebung
  offen und das Speichern dieser Datumsänderung steht noch aus / When ich gleich danach eine
  andere Etappe lösche / Then wird der Stand ohne Seitenwechsel gespeichert, das geänderte Datum
  bleibt erhalten und die gelöschte Etappe erscheint nach dem Neuladen nicht wieder.
  - Test: Kern-Test (Datum ändern → Etappe löschen ⇒ PUT ohne Navigation mit neuem Datum und ohne die
    Etappe; kein verwaister, zeitgeberloser Vormerkzustand) + Playwright.

- **AC-9:** Given eine Kaskade wird gerade angewendet („Wird angepasst …") / When ich ins Höhenprofil
  klicke oder einen Wegpunkt umbenenne oder lösche / Then sind Höhenprofil und Wegpunkt-Aktionen
  sichtbar gesperrt (nicht klickbar, abgedunkelt), die Handlung ändert nichts und löst keinen
  Speichervorgang aus; nach Ende der Kaskade sind sie wieder bedienbar.
  - Test: Kern-Test (`cascadeBusy` ⇒ `stages` unverändert, 0 PUT) + Playwright (Sperre sichtbar:
    `aria-busy`/`disabled`).

- **AC-10:** Given ein bestehender Trip im Etappen-Tab / When ich Etappen umsortiere / Then verhält
  sich das Speichern beim Ablegen unverändert zu #2288 (sofort ein Speichervorgang, bei offener
  Rückfrage vorgemerkt, kein doppelter nach aufgelöster Rückfrage).
  - Test: bestehende #2288-Tests bleiben grün (Regressionsschutz für den herausgelösten Helfer).

## Geplante Tests (für /40)

| Ebene | Datei | Deckt ab |
|-------|-------|----------|
| Kern (`node --test`) | `frontend/src/lib/components/trip-detail/__tests__/etappen_bauliche_aenderung_speichert.test.ts` — über `tripMehrreiterPruefstand.ts` (echtes Instanz-Skript per AST, echter SaveStatus) + `fakeTripServer.ts`; Handler direkt aufrufbar (`inst.u.handleAddStage()` …) | AC-1 bis AC-3, AC-4 (ohne Controller), AC-5 bis AC-9, AC-10 (Regression) |
| Playwright | `frontend/e2e/etappen-bauliche-aenderung-speichert.spec.ts` (Vorlage `mobile-etappen-sortieren-speichert.spec.ts`, PUT-Zählung per Route-Abfang) | AC-1/AC-2 (Hinzufügen/Löschen → Neuladen, Desktop + Mobil), AC-8, AC-9 (sichtbare Sperre) |

Mutations-Gegenprobe (für den Adversary): Helfer-Aufruf in einem Handler entfernen; Zweig „Rückfrage
offen" auf Schreiben stellen; Doppel-PUT-Schutz entfernen; `cascadeBusy`-Riegel im Profil-Klick
entfernen — jede Verfälschung muss einen benannten Test rot machen.

## Known Limitations

- Serien von Profil-Klicks erzeugen mehrere nacheinander laufende Speichervorgänge (kein Konflikt dank
  Warteschlange, nur mehr Netzlast).
- Die Sperre während der Kaskade ist kurz (Obergrenze 15 s); Eingaben in diesem Fenster werden nicht
  vorgemerkt, sondern sichtbar verweigert.
- Nicht vom Speichern erfasst bleibt das Schließen des Browser-Tabs innerhalb weniger Millisekunden
  nach der Handlung; der Speichervorgang ist dann aber bereits gestartet.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Anwendung des bestehenden Musters „abgeschlossene Handlung = sofort schreiben" (#2288)
  auf weitere Handler derselben Datei; keine neue Grundsatzentscheidung, keine Persistenzänderung.

## Changelog

- 2026-10-18: Initial spec created (Issue #2213)
