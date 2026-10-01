---
entity_id: feat_2277_s4_anlege_lockengine
type: feature
created: 2026-10-01
updated: 2026-10-01
status: draft
version: "1.0"
tags: [trip-new, compare-new, lock-engine, shared, refactoring, parity, rueckbau]
---

# Geteilte Freischalt-Logik der Anlege-Seiten (Issue #2277 Scheibe S4)

## Approval

- [ ] Approved

## Purpose

Scheibe **S4** von #2277 (Anlege-Strecke-Konvergenz, Epic #2345). Die Freischalt-Logik („Lock-Engine")
der beiden Anlege-Seiten `/trips/new` und `/compare/new` existiert heute zweimal
(`trip-new/tripNewLogic.ts`, `compare-new/compareNewLogic.ts`). Nach S3 ist die Reiterkette ab
Wetter-Metriken auf beiden Seiten inhaltlich gleich, aber als zwei getrennte Implementierungen mit
unterschiedlichen Signaturen gepflegt. Das widerspricht der PO-Vorgabe „möglichst viel Code zwischen Trip
und Ortsvergleich teilen".

S4 ist ein **reines Refactoring ohne Verhaltensänderung**:

- EIN geteilter Kern `frontend/src/lib/components/shared/anlegeLockEngine.ts` hält die gemeinsame
  Schwanz-Kette **Wetter-Metriken → Wertebereiche → Alarme → Versand**, die Regel „Anlegen erst nach
  Besuch von Versand" und einen generischen Fortschrittszähler `progressCount(done, steps)`.
- Das **Vorderteil** bleibt kind-eigen und wird dem Kern als Parameter übergeben (Trip: Name + Startdatum,
  Etappen erledigt; Ortsvergleich: Name, mindestens 2 Orte).
- Der **Fortschrittszähler** bleibt je Seite wie heute (Trip „/4" über Route · Etappen · Metriken ·
  Versand; Ortsvergleich Anzahl erledigter Reiter, gedeckelt bei 6). Eine Angleichung wäre eine eigene
  Produktentscheidung und ist **nicht** Teil dieser Scheibe.
- `compare-new/compareNewLogic.ts` wird **gelöscht** (Ticket-AC-5, Teil 2).

Für den Nutzer ändert sich nichts Sichtbares.

## Source

- **Frontend:**
  `frontend/src/lib/components/shared/anlegeLockEngine.ts` (CREATE),
  `frontend/src/lib/components/trip-new/tripNewLogic.ts` (MODIFY, nur Freischalt-/Fortschritts-Funktionen),
  `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` (MODIFY, Import und Vorderteil),
  `frontend/src/lib/components/compare-new/compareNewLogic.ts` (DELETE)
- **Identifier:** `unlockedTabs`, `doneTabs`, `progressCount`, `canSave`/`canActivate` (Trip bzw.
  Ortsvergleich); neu `anlegeLockEngine` mit Schwanz-Kette und `progressCount(done, steps)`.

> **Schicht-Hinweis:** ausschließlich **Frontend**. Kein Go-API-, kein Python-Core-Code, kein
> Schema-Eingriff, kein Mail-Inhalt. Payload-Builder in `tripNewLogic.ts` (`buildCreateTripPayload`,
> Alarm-Schatten-State) bleiben unberührt.

## Entscheidungen

1. **Kern-Form (Tech-Lead-Entscheidung):** Der Kern kennt nur die **Schwanz-Kette** und bekommt das
   Vorderteil als Wahrheitswerte übergeben (Vorderteil frei für Wetter-Metriken, plus je Seite die
   Besuchs-Flags für Metriken, Wertebereiche, Alarme, Versand). Der Kern kennt weder `name`, `startDate`
   noch `pickedCount`. Das hält ihn DOM-frei, parameterarm und ohne `context`-Weiche.
2. **Tab-IDs bleiben je Seite unverändert.** Der Trip-Anlege-Editor nennt den Reiter `wertebereiche`, der
   Ortsvergleich-Editor `idealwerte`. Diese IDs sind lokal und werden hier **nicht** angeglichen. Der Kern
   erhält die Schwanz-IDs als Parameter (oder arbeitet auf neutralen Schlüsseln, die die Wrapper
   abbilden) — das ist Implementierungsdetail, die Außen-Signaturen der Trip-Funktionen und die
   Reiter-IDs der Editoren bleiben gleich.
3. **Trip-Wrapper behalten ihre Signatur** (`unlockedTabs(name, startDate, etDone, wtVisited, wbVisited,
   alVisited, vsVisited)`, `doneTabs(...)`, `progressCount(done)`, `canSave(done)`). Sie delegieren an den
   Kern. So bleibt die Eingriffsfläche im 1.170-Zeilen-Editor `TripNewEditor.svelte` null.
4. **Ortsvergleich-Editor importiert den Kern direkt.** Das Compare-eigene Vorderteil (Name nicht leer;
   `pickedCount >= 2`) bleibt als kleine Ableitung im Editor (oder in einer bestehenden Datei des
   Ordners `compare-new/`), **nicht** als neue Datei in `compare-new/` (Pendant-Sperre).
5. **Fortschrittszähler als Parameter:** `progressCount(done, steps)` zählt, wie viele der `steps` in
   `done` stehen. Trip übergibt `['route','etappen','metriken','versand']`; der Ortsvergleich zählt wie
   heute alle erledigten Reiter und deckelt bei 6 (Verhalten bit-gleich zu `Math.min(done.size, 6)`).
6. **`canFinish`** im Kern: `done.has(versandId)`. Trip-`canSave` und Compare-`canActivate` bleiben als
   dünne Aufrufe erhalten bzw. gehen im Editor auf den Kern.
7. **Ablageort:** `shared/` (Namenskollision per `ls` geprüft: keine). Die neue Datei ist ein geteilter
   Baustein, also das Gegenteil eines Pendants.

## Nicht im Umfang

- **Rest von Ticket-AC-5:** `AlertRulesEditor`/`AlertRuleRow`/`alertChannels` sind seit S3 gelöscht. In
  `src/` (außer Tests/Kommentaren) importiert sie niemand mehr; Stichprobe per `grep` bestätigt.
  `EditReportConfigSection` hat dagegen noch **drei produktive Importeure**
  (`trip-new/TripNewEditor.svelte`, `briefings-tab/BriefingsTab.svelte`, `shared/WeatherMetricsTab.svelte`)
  — dieser Rest fällt in **S5** (Mail-Inhalt-Karte nach `shared/`; Löschung von
  `edit/EditReportConfigSection.svelte`, `edit/reportConfigWrite.ts`, `briefings-tab/BriefingsTab.svelte`).
  Nicht Teil von S4.
- Reiterleisten, Beschriftungen, Lock-Hinweistexte, Reiter-IDs, Hub-Reiter (`TripTabs.svelte`,
  `compareTabsResolve.ts`).
- Angleichung des Fortschrittszählers (/4 vs. /6), Vorlagen-Konzept (`?from=` für Ortsvergleich).
- Go-API, Python-Core, Datenmodell, Mail-Renderer, Payload-Builder.
- **Issue #2277 bleibt nach S4 offen**, bis S5 geliefert ist.

## Affected Files

Pfade relativ zu `frontend/src/lib/components/`.

| File | Change Type | Description |
|------|-------------|-------------|
| `shared/anlegeLockEngine.ts` | CREATE | Geteilter Kern: Schwanz-Kette, `canFinish`, generische `progressCount(done, steps)`. DOM-frei, keine Svelte-Imports. |
| `trip-new/tripNewLogic.ts` | MODIFY | `unlockedTabs`/`doneTabs`/`progressCount`/`canSave` delegieren an den Kern; Signaturen unverändert; Payload-Builder und Alarm-State unberührt. |
| `compare-new/CompareNewEditor.svelte` | MODIFY | Importiert den Kern statt `./compareNewLogic.ts`; Compare-Vorderteil (Name, ≥ 2 Orte) und Zähler-Deckel 6 hier. Kommentar Zeile ~10 und ~125 nachziehen. |
| `compare-new/compareNewLogic.ts` | DELETE | Kopie fällt (Ticket-AC-5, Teil 2). |
| `shared/__tests__/anlege_lock_engine.test.ts` | CREATE | Kern-Test (siehe Tests). |
| `compare-new/__tests__/compareNewLogic.test.ts` | MODIFY/MOVE | Tests werden gegen Kern plus Compare-Vorderteil gelesen; Datei wird nach Verhalten umbenannt (Benennung nach Verhalten, nicht nach gelöschter Datei). Keine Zusicherung entfällt. |
| `compare-new/__tests__/compareNewVorlage.test.ts` (Z. 21) | MODIFY | Importpfad nachziehen, Aussage unverändert. |
| `compare/__tests__/compare_layout_tab_dissolution.test.ts` (Z. 43) | MODIFY | Importpfad nachziehen, Aussage unverändert. |
| `compare/__tests__/issue_683_wizard_remove.test.ts` (Z. ~255, ~268) | MODIFY | Verweis auf `compareNewLogic.ts` im Text und im Importmuster nachziehen; Wächter wird nicht abgeschwächt. |
| `trip-new/__tests__/tripNewLogic.test.ts` (Z. ~50) | MODIFY | Kommentar-Verweis auf `compareNewLogic.ts` nachziehen. |
| `trip-new/tripNewLogic.ts` (Z. ~25) | MODIFY | Kommentar-Verweis nachziehen (gehört zur Delegation). |
| `frontend/e2e/compare-neu-kanal-anlegen.staging.spec.ts` (Z. 45, 99) | MODIFY | Nur Kommentar-Verweise. |

## Estimated Scope

- **LoC (produktiv):** ca. +90 Zusätze, -120 Löschungen; Tests ca. ±150. Unter dem 250-LoC-Limit.
- **Files:** 4 produktiv betroffen (1 neu, 1 gelöscht, 2 geändert), ca. 6 Test-/Wächterdateien.
- **Effort:** medium.
- **Risk Level: MITTEL** — Verhalten muss bit-gleich bleiben (Zähler /4 vs. /6, Lock-Hinweise,
  Anlegen-Knopf); reine Funktionen, aber die Editor-Verdrahtung des Ortsvergleichs wird umgehängt.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `trip-new/TripNewEditor.svelte` | component | Einziger Aufrufer der Trip-Logik; bleibt unverändert (Wrapper-Signaturen). |
| `compare-new/CompareNewEditor.svelte` | component | Einziger produktiver Aufrufer der Compare-Logik; wird auf den Kern umgestellt. |
| `trip-new/__tests__/tripNewSsr.ts`, `ssrRunesHook.mjs` | test harness | SSR-Harness für die Editor-Wirkstellen-Tests (Trip). |
| `shared/__tests__/anlege_reiterleiste_trip_vergleich_paritaet.test.ts` | test | Paritätstest aus S3; muss unverändert grün bleiben. |
| `feat_1481b_pendant_gate.md` | spec | Pendant-Sperre: keine neue Datei in `trip-new/`/`compare-new/` ohne `gz-eigenstaendig`. |
| `feat_2277_s3_reiter_angleichung_rueckbau.md` | spec | Vorgänger-Scheibe; Reiterkette beider Seiten bereits angeglichen. |

## Implementation Details

1. **Reihenfolge:** (a) Kern und Kern-Test anlegen (RED zuerst), (b) Trip-Wrapper delegieren lassen
   (bestehende Trip-Tests müssen unverändert grün bleiben), (c) Compare-Editor auf den Kern umstellen,
   (d) `compareNewLogic.ts` löschen, Tests/Wächter/Kommentare nachziehen.
2. **Kern (`anlegeLockEngine.ts`):** Eingabe sind die Wahrheitswerte des Vorderteils (frei für
   Wetter-Metriken) und die vier Besuchs-Flags. Ausgabe sind freigeschaltete und erledigte Reiter der
   Schwanz-Kette: Wertebereiche frei nach Besuch Wetter-Metriken, Alarme frei nach Besuch Wertebereiche,
   Versand frei nach Besuch Alarme; erledigt = jeweiliges Besuchs-Flag. `canFinish(done)` ⇒ Versand
   erledigt. `progressCount(done, steps)` zählt die Schnittmenge.
3. **Trip-Wrapper:** Vorderteil bleibt dort: `route` immer frei; `etappen` frei bei Name und Startdatum;
   `wegpunkte` und `metriken` frei bei `etDone`. Done-Vorderteil: `route` bei Name und Startdatum,
   `etappen` bei `etDone`. Der Schwanz kommt aus dem Kern. Fortschritts-Schritte
   `['route','etappen','metriken','versand']` bleiben im Wrapper.
4. **Compare-Editor:** Vorderteil: `vergleich` immer frei; `orte` frei bei nicht leerem Namen; Metriken
   frei bei Name und ≥ 2 Orten. Done-Vorderteil: `vergleich` bei Name, `orte` bei ≥ 2 Orten. Zähler =
   `Math.min(done.size, 6)` bleibt exakt erhalten (die Kern-Funktion oder der Editor liefert denselben Wert
   für alle 64 Kombinationen der Besuchs-Flags und Vorderteil-Zustände).
5. **Keine Änderung** an Reiter-Definitionen, Lock-Hinweistexten, IDs, Fußzeilen, Mobile-Button-Texten.
6. Nach der Löschung: `grep -rn compareNewLogic frontend/src frontend/e2e tests` darf nur noch
   erklärende Kommentar-Erwähnungen mit neuem Verweis finden, **keinen** Import.

## Expected Behavior

- **Input:** Nutzer durchläuft `/trips/new` bzw. `/compare/new`.
- **Output:** Freischaltung, Lock-Hinweise, Häkchen, Fortschrittszähler und Anlegen-Knopf verhalten sich
  exakt wie vor dieser Scheibe. Nur die Quelle der Logik ändert sich.
- **Side effects:** Keine. Kein Backend, keine Persistenz-, Payload- oder Mail-Änderung.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer auf `/compare/new` mit Namen und mindestens 2 gewählten Orten / When er die
  Reiterleiste bedient / Then sind die Reiter nur in der Kette Wetter-Metriken, Wertebereiche, Alarme,
  Versand nacheinander anwählbar: jeder Reiter wird erst nach dem Besuch des Vorgängers frei, und alle
  noch gesperrten Reiter bleiben nicht anwählbar.
  - Test: Kern — Editor-SSR-Harness-Test auf der echten Reiterleiste von `CompareNewEditor` (disabled-
    Zustand je Reiter nach jedem Besuchsschritt); Kern-Test der Schwanz-Kette.
  - Mutations-Gegenprobe: im Kern „Alarme frei nach Besuch Wertebereiche" auf „frei ohne Besuch"
    ändern ⇒ der Editor-Test (Reiterleiste) wird rot, nicht nur der Logik-Test.

- **AC-2:** Given ein Nutzer auf `/trips/new`, der Name, Startdatum und Etappen erledigt hat / When er die
  Reiterleiste bedient / Then sind Wetter-Metriken frei, Wertebereiche erst nach Besuch von Wetter-Metriken,
  Alarme erst nach Besuch von Wertebereiche und Versand erst nach Besuch von Alarme — genau wie vor
  dieser Scheibe; die Signatur der Trip-Funktionen ist unverändert.
  - Test: Kern — bestehender `tripNewLogic`-Test bleibt unverändert grün; bestehende Trip-Editor-SSR-Tests
    (`trip_new_alarme_reiter`, `trip_new_wertebereiche_reiter`) bleiben unverändert grün.
  - Mutations-Gegenprobe: im Trip-Wrapper `wbVisited` an den Kern nicht durchreichen ⇒ ein Trip-Test an
    der Reiterleiste wird rot.

- **AC-3:** Given ein Nutzer auf `/trips/new` oder `/compare/new`, der alle Pflichtangaben gemacht und
  Alarme, aber noch nicht Versand besucht hat / When er den Anlegen-Knopf ansieht / Then ist „Anlegen"
  (bzw. „Briefing aktivieren") deaktiviert; erst nach dem Besuch von Versand wird er aktiv.
  - Test: Kern — Editor-SSR-Harness-Test beider Editoren prüft den `disabled`-Zustand des Knopfs vor und
    nach dem Versand-Besuch; Kern-Test `canFinish`.
  - Mutations-Gegenprobe: `canFinish` auf `done.has('alarme')` ändern ⇒ der Knopf-Test beider Editoren
    wird rot.

- **AC-4:** Given ein Nutzer auf `/trips/new` / When er Route, Etappen, Wetter-Metriken und Versand
  erledigt hat / Then zeigt der Fortschritt „/4" mit höchstens 4 erledigten Schritten (Route · Etappen ·
  Metriken · Versand); Wertebereiche und Alarme zählen dort weiterhin nicht mit.
  - Test: Kern — `progressCount(done, steps)` mit Trip-Schritten; bestehender `tripNewLogic`-Test auf den
    Zähler bleibt unverändert grün.
  - Mutations-Gegenprobe: `wertebereiche` in die Trip-Schritte aufnehmen ⇒ der Zähler-Test wird rot.

- **AC-5:** Given ein Nutzer auf `/compare/new`, der alle sechs Reiter erledigt hat / When er den
  Fortschrittszähler ansieht / Then zeigt er höchstens 6 von 6; mit weniger erledigten Reitern zeigt er
  genau deren Anzahl (bit-gleich zu vor dieser Scheibe).
  - Test: Kern — Compare-Vorderteil-Test über alle Kombinationen aus Name, Orte-Anzahl und Besuchs-Flags
    (Zähler gleich `min(erledigte, 6)`); Editor-Test liest den Zähler in der Anlege-Leiste.
  - Mutations-Gegenprobe: den Deckel von 6 auf 7 setzen oder den Deckel entfernen ⇒ ein Test wird rot.

- **AC-6:** Given ein Nutzer auf `/compare/new` mit leerem Namen, mit Namen aber nur einem Ort, und mit
  Namen und zwei Orten / When er die Reiterleiste ansieht / Then ist im ersten Fall Orte gesperrt, im
  zweiten Orte frei und Wetter-Metriken gesperrt, im dritten Wetter-Metriken frei.
  - Test: Kern — Compare-Vorderteil-Test (unverändert in der Aussage) und Editor-SSR-Test an der
    Reiterleiste.
  - Mutations-Gegenprobe: `pickedCount >= 2` auf `>= 1` ändern ⇒ der Editor-Test an der Reiterleiste wird
    rot.

- **AC-7:** Given ein Nutzer, der bereits einen Reiter besucht hat / When er zu einem früheren Reiter
  zurückwechselt / Then bleiben die später erreichten Reiter freigeschaltet und die Häkchen stehen
  (einmal besucht bleibt besucht), wie vor dieser Scheibe, auf beiden Anlege-Seiten.
  - Test: Kern — Kern-Test: Besuchs-Flags sind monoton, die Funktionen sind rein; Editor-SSR-Test mit
    gesetzten Besuchs-Flags.
  - Mutations-Gegenprobe: im Kern einen Besuch bei Rückwechsel zurücksetzen (Flag wird wieder
    ausgewertet als false) ⇒ ein Test wird rot.

- **AC-8:** Given der Quellbaum nach dem Umbau / When man nach `compareNewLogic` sucht / Then existiert die
  Datei `compare-new/compareNewLogic.ts` nicht mehr, kein Quell- oder Testcode importiert sie, und
  `CompareNewEditor.svelte` sowie `tripNewLogic.ts` importieren den Kern `shared/anlegeLockEngine.ts`.
  - Test: Kern — Wächtertest (Datei existiert nicht; Import-Scan über `src/` und `e2e/` findet keinen
    Import; beide Importstellen verweisen auf den Kern). Der Dateipfad-Wächter `issue_683_wizard_remove`
    bleibt in seiner Aussage erhalten.
  - Mutations-Gegenprobe: `compareNewLogic.ts` zurücklegen oder in `CompareNewEditor` wieder importieren
    ⇒ der Wächtertest wird rot.

- **AC-9:** Given die neue geteilte Datei und die Pendant-Sperre / When der Commit-Wächter
  (`pendant_gate.py`) die Änderung prüft / Then bleibt die Sperre grün: die neue Datei liegt in `shared/`,
  es entsteht keine neue Datei in `trip-new/` oder `compare-new/` ohne Begründung.
  - Test: Kern — Lauf der Pendant-Sperre auf dem Änderungssatz; Ablageort per `ls` des Zielordners belegt.
  - Mutations-Gegenprobe: dieselbe Logik probehalber als neue Datei in `compare-new/` anlegen ⇒ die
    Pendant-Sperre schlägt an (Nachweis, dass die Sperre wirkt, nicht Teil des Produkts).

- **AC-10:** Given die Tests und Wächter, die den Compare-Dateipfad kannten / When sie nach dem Umbau
  laufen / Then sind sie auf den Kern bzw. den neuen Ort umgestellt, prüfen dieselben Zusicherungen wie
  zuvor, und kein Test wurde gelöscht, ohne dass seine Zusicherung in einem verbleibenden Test steht.
  - Test: Kern — Zuordnungstabelle alter Test ⇒ neuer Test im Adversary-Bericht; alle betroffenen
    Testdateien laufen grün (`node --test`).
  - Mutations-Gegenprobe: je eine Verfälschung pro früher bewachter Zusicherung (Reihenfolge der Kette,
    Name-Pflicht, Orte-Zahl, Zähler-Deckel, Versand-Besuch) ⇒ jeweils mindestens ein Test wird rot.

## Tests

**Neu:**
- **Kern-Test** `shared/__tests__/anlege_lock_engine.test.ts` (`node --test`): Schwanz-Kette in allen
  Besuchs-Kombinationen, `canFinish`, `progressCount(done, steps)` mit Trip-Schritten und mit Compare-
  Deckel, Reinheit/Monotonie (AC-1, AC-3, AC-4, AC-5, AC-7). Keine Mocks der Prüflinge.
- **Compare-Vorderteil-Test** (umgezogener `compareNewLogic.test.ts`, nach Verhalten benannt): Name
  leer/gefüllt, Orte 0/1/2, Zähler-Deckel; bisherige Zusicherungen vollständig übernommen (AC-5, AC-6).
- **Editor-SSR-Harness-Test** (Compare analog `trip-new/__tests__/tripNewSsr.ts`): rendert die echte
  Reiterleiste und den Anlegen-Knopf von `CompareNewEditor` und prüft `disabled` je Besuchsschritt
  (AC-1, AC-3, AC-6). Zusicherung an der **Wirkstelle** (Reiterleiste/Knopf), nicht nur in der Logik. Ist
  ein Harness für den Compare-Editor aufwändig, darf der bestehende Trip-Harness (`tripNewSsr.ts`,
  `ssrRunesHook.mjs`) gemeinsam genutzt werden; ein Nachweis „Wirkstelle erreicht" gehört dazu.
- **Wächtertest** (AC-8): Datei nicht vorhanden, kein Import, beide Wrapper-Stellen verweisen auf den Kern.

**Unverändert grün zu halten:** `tripNewLogic.test.ts` (inkl. Payload-Tests),
`trip_new_alarme_reiter`, `trip_new_wertebereiche_reiter`, `trip_new_versandkanaele_unabhaengig_von_metriken`,
`trip_new_zeitplan_tab_nutzt_geteilten_versand_baustein`, `anlege_reiterleiste_trip_vergleich_paritaet`.

**Mutations-Gegenprobe (Pflicht, Phase 5, Adversary):** Mutationen nur per String-Ersetzung mit externer
Sicherungskopie (nie `git checkout/stash/reset`). Zu verfälschen: (1) Kern-Kette, z. B. Alarme ohne
Wertebereiche-Besuch, (2) `canFinish` auf Alarme statt Versand, (3) Compare-Vorderteil
`pickedCount >= 2` ⇒ `>= 1`, (4) Zähler-Deckel 6, (5) Trip-Schritte um Wertebereiche erweitern,
(6) Durchreichen eines Besuchs-Flags im Trip-Wrapper auslassen. Gemeldet wird, **welcher** Test jeweils rot
wird. Mindestens Mutationen (1), (2) und (3) müssen an der **Wirkstelle** (Editor-Reiterleiste bzw.
Anlegen-Knopf, SSR-Harness) rot werden — wird nur ein Logik-Test rot, ist das ein Finding.

**Playwright (Staging):** keine Änderung nötig; `compare-neu-kanal-anlegen.staging.spec.ts` wird nur im
Kommentar angepasst und läuft unverändert. Beim Deploy-Nachweis durchläuft die Verifikation `/compare/new`
und `/trips/new` einmal (Reiterkette, Anlegen-Knopf erst nach Versand).

## Staging-Verifikation

Nach Merge und Staging-Auto-Deploy (`https://staging.gregor20.henemm.com`), mit Test-Nutzer (kein
Sammel-Versand):

1. `/trips/new` durchklicken: Reiter werden in der Kette frei, „Anlegen" erst nach Versand, Zähler „/4".
2. `/compare/new` durchklicken: Name, 2 Orte, dann Kette bis Versand; „Briefing aktivieren" erst danach;
   Zähler bis höchstens 6.
3. Unverändertes Verhalten gegenüber Produktion (kein Unterschied sichtbar).
4. Staging-Basic-Auth und Login-Zugangsdaten aus `/home/hem/gregor_zwanzig_staging/.env`; ist ein Teil nicht
   messbar, wird er als `NOT_MEASURABLE_ON_STAGING` geführt, nicht als PASS.

Reine Frontend-Änderung; Mail-Validatoren entfallen (kein Mail-Inhalts-Eingriff).

## Known Limitations

- Die Fortschrittszähler bleiben bewusst verschieden (Trip „/4", Ortsvergleich bis 6). Die Angleichung ist
  eine eigene Produktentscheidung.
- Die Reiter-IDs bleiben je Seite verschieden (`wertebereiche` beim Trip, `idealwerte` beim Ortsvergleich);
  der Kern abstrahiert darüber.
- Das Vorderteil (Trip: Name/Startdatum/Etappen; Ortsvergleich: Name/Orte) bleibt kind-eigen und ist die
  einzige legitime Abweichung (Muster Trip/Ortsvergleich-Code-Teilung).
- Ticket-AC-5 ist nach S4 noch nicht vollständig erfüllt: `EditReportConfigSection`, `reportConfigWrite`,
  `BriefingsTab` folgen in S5. Issue #2277 bleibt offen.

## Risiken

- **Verhaltensdrift im Compare-Editor:** Zähler-Deckel oder Vorderteil weichen unbemerkt ab. Gegenmittel:
  Kombinatorik-Test (alle Besuchs-/Vorderteil-Zustände) gegen die alte Formel, plus SSR-Test an der
  Reiterleiste.
- **Test-Löschung nimmt Zusicherung mit:** Beim Umziehen von `compareNewLogic.test.ts` darf keine Aussage
  verloren gehen. Gegenmittel: Zuordnungstabelle alt ⇒ neu (AC-10).
- **Falsches Grün durch Pfad-Auflösung:** Neue Tests lösen ihren Prüfling relativ zur eigenen Testdatei
  auf, nie über den festen Hauptrepo-Pfad.
- **Pendant-Sperre:** neue Dateien nur in `shared/`; vor dem Anlegen `ls` des Zielordners.
- **Commit im Worktree:** drei Wächter mit Formvorgaben (Message-Datei); `e2e_scope` nach jedem Commit
  gegenlesen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue (umgesetzt wird ADR-0032, progressive Tab-Editoren, und die PO-Vorgabe
  Trip/Ortsvergleich-Code-Teilung)
- **Rationale:** S4 führt zwei bestehende Kopien derselben Entscheidung zusammen; keine Entscheidungsfläche
  wird neu entschieden oder umgekehrt.

## Changelog

- 2026-10-01: Initial spec created (#2277 S4: geteilte Lock-Engine, Löschung `compareNewLogic.ts`)
