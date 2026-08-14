---
entity_id: fix_1771_s3_e2e_listen_wachstum
type: feature
created: 2026-08-14
updated: 2026-08-14
status: draft
workflow: fix-1771-s3-e2e-listen-wachstum
tags: [testing, e2e, playwright, ci, infrastructure]
---

# Playwright-E2E-Positivliste erweitern: Mandanten-Nachweise, Einzelfall-Diagnose, Schwellen-Wächter (#1771 Scheibe 3)

- **Issue:** #1771 (`priority:high`, `session:taskforce`) · Scheibe 3 von mehreren. Scheibe 1
  (Ziehhelfer-Härtung) und Scheibe 2 (CI-Job `e2e` mit Positivliste, 36 Dateien / 173
  Testfälle) sind bereits LIVE.
- **Scope dieser Scheibe:** `.github/ci_e2e_specs.txt` gemäß PO-Entscheid vom 2026-08-14
  wachsen lassen — zweistufig: (a) die 2 vollständig grünen Dateien aufnehmen, (b) die 13
  Dateien mit genau einem roten Testfall nach dokumentiertem Verfahren einzeln diagnostizieren
  und ggf. reparieren, (c) einen Wächter bauen, der `E2E_MIN_SPECS`/`E2E_MIN_EXECUTED` an die
  Positivliste bindet, (d) das Diagnose-Ergebnis dauerhaft dokumentieren.
- **Typ:** Feature/Infrastruktur an der CI-Pipeline, mit punktuellen Reparaturen an bis zu
  13 Testdateien in `frontend/e2e/` — kein sonstiger Produktcode betroffen.

## Approval

- [x] Approved — PO-Freigabe 2026-08-14 ("Go"), alle 10 ACs auf Deutsch vorgelegt und
  freigegeben. Ausdrücklich mitfreigegeben: das Ergebnis der Einzelfall-Diagnose ist bei
  Freigabe offen (zwischen 2 und 13 zusätzlich aufgenommenen Dateien, KL-2).

## Purpose

Der PO-Entscheid vom 2026-08-14 ging zunächst davon aus, die 51 nicht gelisteten
Kandidaten-Dateien ließen sich über eine **einzige gemeinsame Fehlerursache** sanieren. Der
Diagnoselauf (51 Kandidaten, isolierter Stack, 143 grün / 200 rot, 56 min) widerlegt das mit
drei unabhängigen Messungen (52 verteilte Fehlermuster ohne Cluster über 9 Fällen, konstante
Rot-Quote 52–66 % über fünf chronologische Blöcke, testfallgenaue Übereinstimmung zwischen
Einzel- und Verbundlauf). Diese Scheibe ersetzt den verworfenen "eine-Wurzel"-Ansatz durch ein
**Einzelfall-Verfahren**: die zwei bereits vollständig grünen Dateien werden ohne Reparatur
aufgenommen, für die 13 Dateien mit genau einem roten Testfall gilt eine dokumentierte
Drei-Wege-Entscheidung (veralteter Test reparieren und aufnehmen / echter Produktbefund buchen
und ausschließen / Diagnose zu teuer buchen und ausschließen), und ein neuer Kern-Test bindet
die CI-Schwellen mechanisch an die tatsächliche Listenlänge, damit ein künftiges
Listenwachstum nicht erneut das Loch aus Adversary-Fund F006 ("ein Puffer in einer Schwelle
ist ein Loch") öffnet.

## Source

- **Files:**
  - `.github/ci_e2e_specs.txt` — MODIFY (mindestens +2, höchstens +13 Zeilen, abhängig vom
    Ergebnis der Einzelfall-Diagnose)
  - `.github/workflows/ci.yml` — MODIFY (`E2E_MIN_SPECS`/`E2E_MIN_EXECUTED` exakt auf die neue
    Summe nachgezogen, Kommentar aktualisiert)
  - `tests/unit/test_e2e_positivliste_ratschen_bindung.py` — CREATE (Kern-Test, zwei Prüfungen:
    Schwellen-Bindung + Schreibpfad-Kriterium, s. u.)
  - bis zu 13 Dateien unter `frontend/e2e/*.spec.ts` — MODIFY (nur die als "veralteter Test"
    diagnostizierten; Reparatur oder Löschung der veralteten Prüfung)
  - `frontend/e2e/trip-detail-actions.spec.ts` — MODIFY (Screenshot-Schreibpfad-Fix, s.
    Implementation Detail 3, unabhängig vom Ausgang der Status-Badge-Diagnose)
  - `docs/adr/0054-playwright-e2e-in-ci-ampel-positivliste.md` — MODIFY (Korrektur der
    Filter-A-Behauptung + Nachtrag Diagnose-Ergebnis)
  - `docs/specs/modules/fix_1771_s2_playwright_ci_ampel.md` — MODIFY (dieselbe Korrektur,
    Changelog-Eintrag)
- **Identifier:** Positivliste `.github/ci_e2e_specs.txt`; Schwellen `E2E_MIN_SPECS`/
  `E2E_MIN_EXECUTED` in `ci.yml:200-201`; neuer Kern-Test
  `tests/unit/test_e2e_positivliste_ratschen_bindung.py`

## Estimated Scope

- **LoC:** ~150–250, abhängig vom Diagnose-Ausgang der 11 offenen Ein-Fehler-Dateien (2 sind
  bereits als Produktbefund #1831 ausgeschieden). Deckel: 250 (Workflow-LoC-Limit); die
  Abbruchgrenze (Implementation Detail 2) verhindert ein Überschreiten durch unbegrenztes
  Weiterdiagnostizieren. `.md`-Dateien zählen laut CLAUDE.md nicht.
- **Files:** 3 sichere Code-Dateien (`ci_e2e_specs.txt`, `ci.yml`, neuer Kern-Test) + bis zu
  14 `frontend/e2e/*.spec.ts`-Dateien (13 Kandidaten + `trip-detail-tabs.spec.ts` opportunistisch,
  s. u.) + 2 Doku-Dateien (ADR-0054, S2-Spec)
- **Effort:** medium — kein neues Grundsatz-Konzept (ADR-0054 bleibt gültig), aber 13
  unabhängige Einzelfall-Diagnosen mit je eigener Beweislast

### Affected Files (Scope)

| Datei | Änderungstyp | ~LoC |
|---|---|---|
| `.github/ci_e2e_specs.txt` | MODIFY | +2 bis +13 Zeilen (+ Kopfkommentar-Ergänzung) |
| `.github/workflows/ci.yml` | MODIFY | ~10 (Schwellen-Nachzug + Kommentar) |
| `tests/unit/test_e2e_positivliste_ratschen_bindung.py` | CREATE | ~90–120 |
| bis zu 11 `frontend/e2e/*.spec.ts` (Einzelfall-Reparaturen) | MODIFY | variabel, je Datei ~5–30 |
| `frontend/e2e/trip-detail-actions.spec.ts` | MODIFY | ~1 (Screenshot-Pfad-Fix) |
| `frontend/e2e/trip-detail-tabs.spec.ts` | MODIFY | ~2 (opportunistisch, gleicher Fehler, kein Aufnahme-Kandidat) |
| `docs/adr/0054-playwright-e2e-in-ci-ampel-positivliste.md`, `docs/specs/modules/fix_1771_s2_playwright_ci_ampel.md` | MODIFY | 0 (zählt nicht) |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `.github/ci_e2e_specs.txt` (Bestand) | Ratsche (Positivliste) | Ziel dieser Erweiterung; Kopfkommentar dokumentiert Filter A + B, bekommt hier zusätzlich Filter C |
| `.github/workflows/ci.yml:180-344` (Bestand) | CI-Job `e2e` | Enthält `E2E_MIN_SPECS`/`E2E_MIN_EXECUTED` und den tatsächlich verdrahteten Filter-A-Grep (`ci.yml:244-247`) |
| `.github/scripts/e2e_gate.py` (Bestand) | Drei-Bedingungen-Auswerter | Wird von dieser Scheibe NICHT verändert, nur die Eingangszahlen (`E2E_MIN_*`) |
| `tests/unit/test_e2e_ci_gate.py` (Bestand) | Kern-Test | Prüft nur die Auswertungslogik, NICHT die Bindung der Listen-Schwellen an die Liste selbst — genau diese Lücke schließt Implementation Detail 4 |
| `docs/adr/0054-...md` (Bestand) | ADR | Enthält die zu korrigierende Filter-A-Behauptung sowie den Ort für den Diagnose-Nachtrag |
| `.gitignore:80` (Bestand) | Ratsche (Ignore-Regel) | `docs/artifacts/` ist ohne führenden Slash am Ort der `.gitignore` (Repo-Root) verankert und deckt NICHT `frontend/docs/artifacts/` — Wurzel des Screenshot-Befunds |
| Issue #1831 (Bestand) | Produktbefund | `btn-feature-parity`/`theme-bridge` bleiben dort gebucht, keine Reparatur in dieser Scheibe |
| Issue #1196 (Bestand, Sammel-Issue) | Nebenbefund-Ablage | Aufnahmeort für "Diagnose zu teuer"-Befunde, sofern nicht nutzersichtbar |

## Implementation Details

### 1. Aufnahme ohne Reparatur: die zwei Mandanten-Trennungs-Dateien

`e2e/compare-cross-user-write-block.spec.ts` und `e2e/compare-editor-autosave-user-isolation.spec.ts`
(je 1 Testfall) waren im 51er-Diagnoselauf vollständig grün — inhaltlich die wertvollste Klasse
im Korpus, weil sie exakt die CLAUDE.md-Pflicht belegen ("Jeder neue datenbewegende Endpoint
MUSS mit zwei verschiedenen Nutzern getestet werden").

**Filter-B-Pflicht im Zielverbund, nicht im 51er-Kandidatenverbund.** Der Diagnoselauf fuhr im
51er-Kandidatenpool, nicht im Zielverbund der künftigen Positivliste (36 Dateien plus diese 2).
Nach der Lehre aus dem Kontext-Dokument ("Prüfort ≠ Wirkort bei Filter B") ist vor der Aufnahme
ein eigener Nachweis **im Zielverbund** zu erheben: die aktuelle Positivliste plus diese 2
Dateien, 3× hintereinander grün. Erst danach werden `E2E_MIN_SPECS` (36 → 38) und
`E2E_MIN_EXECUTED` (173 → 175, sofern der Zielverbund-Nachweis exakt diese Zahl bestätigt)
nachgezogen.

### 2. Einzelfall-Entscheidungsverfahren für die 13 Ein-Fehler-Dateien

Gemessen im 51er-Diagnoselauf (2026-08-14):

| Datei | grün/rot | Fehler |
|---|---|---|
| `btn-feature-parity.spec.ts` | 7/1 | Farbwert erwartet `rgb(179,58,42)`, erhalten `rgb(168,50,50)` |
| `theme-bridge.spec.ts` | 4/1 | derselbe Farbwert |
| `bug-274-safe-area-insets.spec.ts` | 1/1 | `getByTestId('edit-save-btn')` nicht sichtbar (Testid existiert im Frontend) |
| `compare-editor-slice1.spec.ts` | 4/1 | `compare-editor-progress-segment`: erwartet 7, erhalten 6 |
| `compare-editor-slice3.spec.ts` | 8/1 | Test-Timeout 30000ms, kein Locator im Report |
| `design-compliance-group-a.spec.ts` | 6/1 | `getByRole('link', {name:'Bearbeiten'})` nicht sichtbar |
| `issue-269-mobile-trip-tabs.spec.ts` | 7/1 | `overflow-x`: erwartet "auto", erhalten "visible" |
| `issue-280-home-topbar-polish.spec.ts` | 0/1 | `h1.home__title` nicht sichtbar |
| `issue-579-home-fidelity.spec.ts` | 1/1 | Text "Einrichten" nicht sichtbar |
| `issue-616-trip-one-surface.spec.ts` | 7/1 | Test-Timeout 30000ms |
| `orts-vergleich-c4.spec.ts` | 3/1 | Test-Timeout 30000ms |
| `trip-detail-actions.spec.ts` | 12/1 | Status-Badge: erwartet "accent", erhalten `["success","info"]` |
| `waypoint-mapclick-autosave.spec.ts` | 0/1 | Test-Timeout 30000ms |

**Zwei bereits ausgeschieden:** `btn-feature-parity.spec.ts` und `theme-bridge.spec.ts` melden
denselben Produktbefund — Danger-Rot-Token unvollständig gewechselt (`app.css:161` `--g-danger:
#a83232`, aber `app.css:19`/`311`/`316` und `_design/+page.svelte:37` nutzen weiterhin den
alten Wert `#b33a2a`). Gebucht unter **Issue #1831**, eine Design-Entscheidung ist
Voraussetzung. **Nicht in dieser Scheibe repariert**, beide Dateien bleiben ausgeschlossen.

**Für die verbleibenden 11 Dateien gilt folgende Entscheidungsregel** (keine Datei bleibt
unentschieden):

1. **Veralteter Test** (prüft UI, die es nicht mehr gibt, oder bewusst geändertes Verhalten) ⇒
   Test reparieren oder die veraltete Prüfung löschen, danach Filter-B-Nachweis im Zielverbund
   erheben und aufnehmen. Deckt sich mit der CLAUDE.md-Test-Politik: "sofort fixen ODER löschen
   (wenn er veraltetes Verhalten prüft)".
2. **Echter Produktbefund** (der Test meldet zutreffend ein Fehlverhalten der Anwendung) ⇒
   **nicht** in dieser Scheibe reparieren. Buchen: eigenes Issue bei nutzersichtbarem
   Fehlverhalten, sonst Checkbox-Zeile in Sammel-Issue #1196 (Nebenbefund-Triage). Datei bleibt
   von der Positivliste ausgeschlossen.
3. **Diagnose zu teuer (Abbruchgrenze)** ⇒ buchen (wie 2.), Datei bleibt ausgeschlossen.
   **Abbruchgrenze, explizit:** pro Datei genau **ein** gezielter Diagnosedurchgang (rote
   Fehlermeldung lesen, zugehörige Frontend-Stelle identifizieren, optional ein lokaler
   Nachlauf mit Trace). Bleibt die Ursache danach unklar, gilt die Datei als "zu teuer" — keine
   weitere Zeit wird investiert, sonst entsteht aus dieser Scheibe genau das offene
   Sanierungsprojekt, vor dem Issue #1771 selbst warnt. **Vier Risikokandidaten**, die
   ausschließlich "Test-Timeout 30000ms" ohne jeden Locator-Hinweis im JSON-Report melden und
   damit keinen Ansatzpunkt für den einen Diagnosedurchgang bieten:
   `compare-editor-slice3.spec.ts`, `issue-616-trip-one-surface.spec.ts`,
   `orts-vergleich-c4.spec.ts`, `waypoint-mapclick-autosave.spec.ts`.

**Diese Spec verspricht nicht, dass alle 11 aufgenommen werden.** Sie legt das Verfahren fest;
das Ergebnis (zwischen 0 und 11 zusätzlich aufgenommenen Dateien) entsteht erst in der
Implementierungsphase.

### 3. Zusätzliches Aufnahme-Kriterium: keine Schreibpfade in getrackte Verzeichnisse (Filter C)

**Befund, gemessen am 2026-08-14 über alle `page.screenshot({ path: ... })`-Aufrufe im
161-Datei-Korpus:** 27 der gemessenen relativen Schreibpfade beginnen mit `../docs/artifacts/`.
Playwright-Tests laufen mit `frontend/` als Arbeitsverzeichnis; `../docs/artifacts/` löst damit
zum Repo-Root-Verzeichnis `docs/artifacts/` auf, das `.gitignore:80` ignoriert — **harmlos**.
Genau **3 Pfade in genau 2 Dateien** beginnen dagegen OHNE `../`-Präfix mit `docs/artifacts/`:
`trip-detail-actions.spec.ts:211` und `trip-detail-tabs.spec.ts:113,119` (je 2 Aufrufe dort,
1 in `trip-detail-actions.spec.ts`). Diese Pfade lösen zu `frontend/docs/artifacts/...` auf —
einem eigenständigen Verzeichnis, das die Ignore-Regel `docs/artifacts/` NICHT abdeckt, weil
ein Muster mit Slash am Ort der `.gitignore`-Datei (Repo-Root) verankert ist, nicht an jeder
Verzeichnisebene. Entsprechende PNG-Dateien liegen dort bereits versioniert im Repo (z. B.
`frontend/docs/artifacts/epic-135-step2-trip-detail-actions/screenshot-trip-header.png`). Ein
Lauf dieser beiden Dateien verändert damit eine getrackte Datei im Arbeitsbaum — ein Test, der
seinen eigenen Prüfling bzw. den Arbeitsbaum verändert, ist ein Anti-Pattern.

**Einordnung:** 27 von 30 gemessenen Pfaden sind korrekt — das ist ein isolierter Ausrutscher
in zwei Dateien (ein fehlendes `../`), kein verbreitetes Muster. Die Reparatur ist eine
**Ein-Zeichen-Korrektur** (`docs/artifacts/...` → `../docs/artifacts/...`) ohne fachliche
Entscheidung, kein Ausschlussgrund für `trip-detail-actions.spec.ts`. Für den Kandidaten
`trip-detail-actions.spec.ts` (12 grün / 1 rot, Status-Badge-Befund s. o.) ist die Aufnahme
**zusätzlich** an diese Korrektur gebunden, unabhängig vom Ausgang der
Status-Badge-Einzelfall-Diagnose (Punkt 2). `trip-detail-tabs.spec.ts` ist kein
Aufnahme-Kandidat dieser Scheibe (nicht Teil der 13 Ein-Fehler-Dateien), bekommt den gleichen
trivialen Fix aber opportunistisch mit, weil er beim Bau des neuen Kern-Tests ohnehin auffällt
und jeder künftige Lauf dieser Datei sonst weiterhin den Arbeitsbaum verschmutzt.

**Neues statisches Kriterium, Teil desselben Kern-Tests wie der Schwellen-Wächter (Punkt 4):**
für jede Datei auf der Positivliste gilt als Verstoß, wenn ihr Text einen
`page.screenshot({ ... path: '<Wert>' ... })`-Aufruf enthält, dessen `<Wert>` **nicht** mit
`../` beginnt und **nicht** unter `test-results/` oder `playwright/` liegt (beide laut
`.gitignore:83-84` explizit ignoriert). Rein statische Textprüfung, kein Playwright-Lauf nötig
— verhindert den Rückfall, falls künftig eine weitere Datei mit demselben fehlenden `../`
aufgenommen werden soll.

### 4. Wächter: `E2E_MIN_SPECS` exakt an die Positivliste gebunden

Heute bindet nichts `E2E_MIN_SPECS` (`ci.yml:200`) an die tatsächliche Zeilenzahl von
`.github/ci_e2e_specs.txt`. Der zur Laufzeit vorhandene Check (`ci.yml:256-260`) prüft nur
`N >= E2E_MIN_SPECS` — eine reine Untergrenze, die eine veraltete (zu niedrige) Schwelle nie
auffliegen lässt, solange die Liste weiter wächst. Wächst die Liste künftig ohne exakten
Nachzug beider Zahlen, öffnet sich Adversary-Fund F006 aus Scheibe 2 wieder ("ein Puffer in
einer Schwelle ist ein Loch"): bei z. B. 45 Dateien/210 Testfällen und unverändert gebliebener
Schwelle 173 dürften 37 Testfälle still verschwinden, ohne dass ein Check das bemerkt.

**Neuer Kern-Test** `tests/unit/test_e2e_positivliste_ratschen_bindung.py` (deterministisch,
ohne Netz, `tests/unit/`, Prüfling relativ zur Testdatei aufgelöst — Pfadregel #1409):

- Liest `E2E_MIN_SPECS` aus `ci.yml` per Regex (statischer Text-Read, kein YAML-Parser nötig).
- Zählt die Nicht-Kommentar-/Nicht-Leer-Zeilen von `.github/ci_e2e_specs.txt`.
- Verlangt **exakte Gleichheit**, nicht nur `>=`: ein Puffer nach unten (Liste wächst, Schwelle
  bleibt stehen) ist die aus F006 bekannte Lücke; ein "Puffer nach oben" (Schwelle höher als die
  tatsächliche Zeilenzahl) wäre umgekehrt ein Bug, der jeden PR grundlos blockiert. Exakte
  Gleichheit macht beide Richtungen der Divergenz sofort sichtbar.
- Prüft zusätzlich das Filter-C-Kriterium aus Punkt 3 für jede gelistete Datei.

**`E2E_MIN_EXECUTED` bleibt in dieser Scheibe NICHT statisch bewachbar.** Die Zahl
tatsächlich ausgeführter Testfälle je Datei ist keine zuverlässig statisch zählbare Größe
(parametrisierte Tests, verschachtelte `describe`-Blöcke, das mitgezählte
`global.setup`-Projekt) — verlässlich nur über einen echten `npx playwright test --list`-Lauf
zu ermitteln, der Node/Playwright/Browser-Abhängigkeiten voraussetzt und damit die
Kern-Schicht-Anforderung "kein Netz, keine echten Dienste, deterministisch ohne
Zusatzinstallation" (CLAUDE.md Test-Politik) verletzen würde. Die Zusicherung gegen ein
stilles Verschwinden **einzelner** Testfälle trägt stattdessen weiterhin die bereits
bestehende **Existenzprüfung** (`ci.yml:261-281`): verschwindet eine gelistete **Datei**
komplett, bricht der Job vor dem Playwright-Lauf ab. Nicht gefangen: ein einzelner
`test()`-Block verschwindet aus einer weiterhin existierenden Datei, ohne dass
`E2E_MIN_EXECUTED` nachgezogen wird — das bleibt Prozessdisziplin (Kopfkommentar der Liste:
"Hinzufügen = neuer Filter-B-Beleg nötig"), nicht mechanisch erzwungen. Diese Lücke wird
explizit als Known Limitation benannt statt stillschweigend als gelöst behauptet.

### 5. Korrektur: ADR-0054 und S2-Spec behaupten ein Filter-A-Kriterium, das nicht verdrahtet ist

Der tatsächlich verdrahtete Filter-A-Grep (`ci.yml:244-247`) schließt Kandidaten ausschließlich
über vier strukturelle Kriterien aus: `waitForTimeout`/`test.skip`/`test.fixme`/`describe.skip`,
`.staging.spec.ts`-Dateien, den hartkodierten Hauptrepo-Pfad und `__dirname` in ESM-Modulen.
**Ein Wetter-Werte-Kriterium kommt darin nicht vor.** ADR-0054 (Zeile 30) und die S2-Spec
(Zeile 189) behaupten dennoch, Filter A schließe "keine Specs, die Wetterwerte prüfen" ein —
eine Zusicherung, die die Doku macht, aber der Code nicht einlöst. Beide Dokumente werden um
eine Erratum-Anmerkung ergänzt: Filter A umfasst ausschließlich die vier strukturellen
Kriterien; die Beobachtung zum Fixture-Fenster (nur heute + 2 Tage, S2-Spec KL-1) bleibt als
reine Beobachtung stehen, nicht als aktiv gefilterte Bedingung. **Konsequenz, nur benannt, nicht
behoben:** der 87er Filter-A-Kandidatenpool kann wertprüfende Wetter-Specs enthalten, die bei
einer künftigen Aufnahme gesondert zu prüfen wären.

### 6. Diagnose-Ergebnis dauerhaft buchen

Der PO-Entscheid vom 2026-08-14 ging von einer großen gemeinsamen Fehlerwurzel aus; die Messung
widerlegt das mit drei unabhängigen Belegen: 52 verteilte Fehlermuster ohne Cluster über 9
Fällen, konstante Rot-Quote (52–66 %) über fünf chronologische Blöcke (widerspricht
kumulativer Zustandsverschmutzung), und testfallgenaue Übereinstimmung zwischen Einzellauf und
Verbundlauf für fünf Stichprobendateien (`alert-rules-editor` 0/21, `trip-edit` 0/9,
`compare-hub-briefing-times` 6/4, `nav-redesign` 3/4, `issue-758-save-indicator` 5/2). Damit
dieses Ergebnis nicht nur im workflow-gebundenen, nicht dauerhaft geteilten Kontext-Dokument
steht, wird es in **ADR-0054** als Nachtrag festgehalten — Folge-Scheiben sollen diese Messung
nicht wiederholen müssen, sondern direkt beim Einzelfall-Verfahren ansetzen.

## Nicht in dieser Scheibe

- **Produktbefund #1831** (Danger-Rot-Token unvollständig gewechselt) — Design-Entscheidung
  über den korrekten Wert ist Voraussetzung, `btn-feature-parity.spec.ts`/`theme-bridge.spec.ts`
  bleiben unrepariert und ausgeschlossen.
- **8 weitere Dateien mit genau zwei roten Testfällen** (21 Dateien mit ≤ 2 Roten insgesamt
  minus die hier behandelten 13) — Reserve für Folge-Scheiben.
- **~28 Dateien mit mehr als zwei roten Testfällen** (49 Dateien mit mindestens 1 Rotem minus
  21 mit ≤ 2 Roten) — Reserve für Folge-Scheiben, keine Diagnose in dieser Scheibe.
- **Die 22 gesuchten Testids, die im Frontend gar nicht mehr existieren** (Altbestand des am
  2026-07-11 abgeschafften Wizards) — betrifft primär die o. g. Reserve-Dateien, nicht die 13
  Kandidaten dieser Scheibe; wo eine der 13 Kandidatendateien betroffen ist, fällt sie unter
  "veralteter Test" (Punkt 2, Entscheidungsregel 1).
- **Zwei strukturell kaputte Dateien aus Filter A** bleiben ausgeschlossen:
  `list-routes-btn-migration.spec.ts` (hartkodierter Hauptrepo-Pfad, Pfadregel #1409),
  `issue-322-wicon-komponente.spec.ts` (`__dirname` in ESM) — unverändert seit S2.
  `waitForTimeout`, konditionale Skips, Toter Bestand, Config-Wildwuchs, Sharding, die 16
  `.staging.spec.ts` — alles unverändert wie in S2 "Nicht in dieser Scheibe" begründet.
- **27 der 30 gemessenen `page.screenshot`-Schreibpfade** (mit korrektem `../`-Präfix) — kein
  Handlungsbedarf, dienen als Referenz für das neue Filter-C-Kriterium.
- **Ein Volllauf über alle 921 Testfälle** — bleibt per `workflow_dispatch`-Vermessungsmodus
  aus S2 verfügbar, ist für diese Scheibe nicht Vorbedingung.

## Expected Behavior

- **Input:** Diese Scheibe wird implementiert (Einzelfall-Diagnose der 13 Kandidaten,
  Aufnahme der 2 Mandanten-Dateien, neuer Kern-Test, Doku-Korrekturen).
- **Output:**
  - `.github/ci_e2e_specs.txt` enthält mindestens 38 Dateien (36 bestehend + 2 Mandanten-Dateien),
    höchstens 49 (zusätzlich alle 11 reparierbaren Ein-Fehler-Dateien), jede mit belegtem
    Filter-B-Nachweis **im Zielverbund**.
  - `E2E_MIN_SPECS`/`E2E_MIN_EXECUTED` in `ci.yml` sind exakt auf die neue Summe nachgezogen —
    kein Puffer in beide Richtungen.
  - `tests/unit/test_e2e_positivliste_ratschen_bindung.py` ist grün und schlägt bei jeder
    künftigen Divergenz zwischen Schwelle und Listenlänge sowie bei jedem künftigen
    Schreibpfad-Verstoß (Filter C) rot.
  - `trip-detail-actions.spec.ts` schreibt Screenshots nicht mehr in einen getrackten Pfad.
  - ADR-0054 enthält die korrigierte Filter-A-Beschreibung sowie den Diagnose-Nachtrag.
- **Side effects:** Jeder künftige PR läuft weiterhin gegen die (nun größere) Positivliste;
  die CI-Wanduhrzeit des `e2e`-Jobs steigt geringfügig mit der Zahl zusätzlicher Testfälle,
  bleibt aber unter der `test`-Job-Laufzeit (Ampel-Engpass unverändert bei `test`).

## Acceptance Criteria

- **AC-1:** Given `compare-cross-user-write-block.spec.ts` und
  `compare-editor-autosave-user-isolation.spec.ts` sind je vollständig grün im 51er-Diagnoselauf
  gemessen / When ein Zielverbund-Nachweis (Positivliste + beide Dateien, 3× hintereinander
  grün) erhoben wird / Then stehen beide Dateien in `.github/ci_e2e_specs.txt`, und
  `E2E_MIN_SPECS`/`E2E_MIN_EXECUTED` sind exakt auf die neue Summe nachgezogen.
  - Test: Zielverbund-Lauf (lokal oder `workflow_dispatch`) dreimal grün mit identischer
    `expected`-Zahl protokolliert, analog zu Filter B aus S2 Punkt 3.

- **AC-2:** Given die 13 Ein-Fehler-Dateien aus dem 2026-08-14-Diagnoselauf / When diese
  Scheibe abgeschlossen ist / Then liegt für JEDE der 13 Dateien eine dokumentierte
  Einzelfall-Entscheidung vor (veralteter Test repariert & aufgenommen, ODER echter
  Produktbefund gebucht & ausgeschlossen, ODER Diagnose zu teuer nach Abbruchgrenze gebucht &
  ausgeschlossen) — keine Datei bleibt unentschieden liegen.
  - Test: Abgleich der 13-Zeilen-Tabelle aus dieser Spec gegen die finale
    `.github/ci_e2e_specs.txt` sowie die Buchungen unter #1831/#1196 bzw. Einzel-Issues — jede
    Zeile hat einen nachvollziehbaren Verbleib.

- **AC-3:** Given `btn-feature-parity.spec.ts` und `theme-bridge.spec.ts` scheitern beide am
  selben Produktbefund (Danger-Rot-Token, `#a83232` statt `#b33a2a`) / When diese Scheibe
  abgeschlossen ist / Then bleiben beide Dateien unrepariert und von der Positivliste
  ausgeschlossen, der Befund bleibt unter #1831 gebucht statt geschlossen.
  - Test: `.github/ci_e2e_specs.txt` enthält nach dieser Scheibe weder `btn-feature-parity.spec.ts`
    noch `theme-bridge.spec.ts`; Issue #1831 ist referenziert, nicht geschlossen.

- **AC-4:** Given vier der 13 Dateien melden ausschließlich "Test-Timeout 30000ms" ohne
  Locator-Hinweis im JSON-Report (`compare-editor-slice3.spec.ts`,
  `issue-616-trip-one-surface.spec.ts`, `orts-vergleich-c4.spec.ts`,
  `waypoint-mapclick-autosave.spec.ts`) / When der eine vorgesehene Diagnosedurchgang je Datei
  keine eindeutige Ursache ergibt / Then werden diese Dateien NICHT aufgenommen, sondern
  gebucht (#1196 bzw. eigenes Issue bei nutzersichtbarem Fehlverhalten) — es entsteht kein
  offenes Sanierungsprojekt über diese Scheibe hinaus.
  - Test: Für jede der vier Dateien liegt entweder ein Aufnahme-Beleg (Filter B, 3× grün im
    Zielverbund) oder ein Buchungs-Verweis vor, nie ein unkommentiertes Weglassen.

- **AC-5:** Given genau 3 von 30 gemessenen `page.screenshot`-Schreibpfaden im Korpus beginnen
  ohne `../`-Präfix und landen damit in `frontend/docs/artifacts/` statt im per
  `.gitignore:80` ignorierten Repo-Root-`docs/artifacts/` (betroffen:
  `trip-detail-actions.spec.ts:211`, `trip-detail-tabs.spec.ts:113,119`) / When
  `trip-detail-actions.spec.ts` als einer der 13 Ein-Fehler-Kandidaten für die Positivliste
  geprüft wird / Then ist die Aufnahme zusätzlich an eine Ein-Zeichen-Korrektur des
  Schreibpfads (`docs/artifacts/...` → `../docs/artifacts/...`) gebunden, unabhängig vom
  Ausgang der Status-Badge-Diagnose — ohne diese Korrektur würde jeder Lauf eine getrackte
  Datei verändern.
  - Test: `git status` nach einem lokalen Lauf von `trip-detail-actions.spec.ts` zeigt vor der
    Korrektur eine Änderung an
    `frontend/docs/artifacts/epic-135-step2-trip-detail-actions/screenshot-trip-header.png`,
    nach der Korrektur keine.

- **AC-6:** Given heute bindet nichts `E2E_MIN_SPECS` (`ci.yml:200`) an die tatsächliche
  Zeilenzahl von `.github/ci_e2e_specs.txt`, wodurch eine veraltete (zu niedrige) Schwelle bei
  wachsender Liste nicht auffällt / When der neue Kern-Test
  `tests/unit/test_e2e_positivliste_ratschen_bindung.py` beide Werte gegeneinander liest / Then
  schlägt der Test rot, sobald sie nicht exakt übereinstimmen — in beide Richtungen (Liste
  gewachsen ohne Nachzug der Schwelle, oder Schwelle geändert ohne passende Zeilenzahl).
  - Test: Mutations-Gegenprobe — `E2E_MIN_SPECS` in `ci.yml` testweise um 1 verändern (externe
    Sicherungskopie vorher, kein `git checkout`/`stash`/`reset`), Kern-Test muss rot werden;
    danach Rückbau der Verfälschung.

- **AC-7:** Given der neue Kern-Test prüft zusätzlich für jede Datei der Positivliste, ob ein
  `page.screenshot`-Aufruf einen Schreibpfad ohne `../`-Präfix außerhalb von
  `test-results/`/`playwright/` verwendet (Filter C) / When eine künftige PR eine Datei mit
  einem solchen Schreibpfad zur Positivliste hinzufügen will / Then schlägt der Kern-Test rot
  und verhindert die Aufnahme, ohne dass ein echter Runner-Lauf nötig ist.
  - Test: Mutations-Gegenprobe — an einer externen Kopie den bereits korrigierten `../`-Präfix
    aus `trip-detail-actions.spec.ts` wieder entfernen, Kern-Test muss rot werden; danach
    Rückbau der Verfälschung.

- **AC-8:** Given `E2E_MIN_EXECUTED` lässt sich ohne einen echten Playwright-Lauf (Node,
  Browser-Abhängigkeiten) nicht zuverlässig aus dem Quelltext ableiten / When diese Scheibe
  abgeschlossen ist / Then bleibt die Zusicherung gegen ein stilles Verschwinden einzelner
  Testfälle explizit bei der bestehenden Existenzprüfung (`ci.yml:261-281`, fängt verschwundene
  DATEIEN) plus der Prozessdisziplin im Listen-Kopfkommentar — dokumentiert als Known
  Limitation, nicht stillschweigend als mechanisch gelöst behauptet.
  - Test: Diese Spec (Abschnitt Known Limitations, unten) benennt die Lücke explizit; kein
    neuer Kern-Test behauptet fälschlich, `E2E_MIN_EXECUTED` sei an die Liste gebunden.

- **AC-9:** Given ADR-0054 (Zeile 30) und die S2-Spec (Zeile 189) behaupten, Filter A schließe
  "wertprüfende Wetter-Specs" aus / When der tatsächlich verdrahtete Filter (`ci.yml:244-247`)
  nachgelesen wird / Then enthält er ausschließlich vier strukturelle Kriterien (kein
  Wetter-Werte-Kriterium), und beide Dokumente sind entsprechend um eine Erratum-Anmerkung
  ergänzt.
  - Test: `grep -n "wertprüfende Wetter\|Wetterwerte prüfen" docs/adr/0054-playwright-e2e-in-ci-ampel-positivliste.md
    docs/specs/modules/fix_1771_s2_playwright_ci_ampel.md` zeigt nach der Korrektur nur noch
    die Erratum-Anmerkung, nicht mehr die unkorrigierte Behauptung als aktives Kriterium.

- **AC-10:** Given der Diagnoselauf vom 2026-08-14 widerlegt die Annahme des PO-Entscheids
  (große gemeinsame Wurzel) mit drei unabhängigen Messungen / When diese Scheibe live ist /
  Then ist dieses Ergebnis dauerhaft in ADR-0054 festgehalten (nicht nur im flüchtigen
  Kontext-Dokument), damit Folge-Scheiben die Messung nicht wiederholen müssen.
  - Test: `docs/adr/0054-playwright-e2e-in-ci-ampel-positivliste.md` enthält nach dieser
    Scheibe einen Nachtrags-Abschnitt, der die drei Messungen (Musterverteilung, Rot-Quote
    über Zeit, Einzel- vs. Verbundlauf) und das Ergebnis "keine große gemeinsame Wurzel"
    benennt.

## Known Limitations

- **KL-1 · `E2E_MIN_EXECUTED` bleibt Handpflege:** siehe Implementation Detail 4/AC-8 — nur
  indirekt über die Existenzprüfung abgesichert, nicht mechanisch an die Testfallzahl
  gebunden. Ein verschwindender einzelner `test()`-Block in einer weiterhin existierenden
  Datei wird nicht automatisch gefangen.
- **KL-2 · Ergebnis der Einzelfall-Diagnosen ist bei Spec-Freigabe offen:** die Spec legt das
  Verfahren fest, nicht das Ergebnis. Die tatsächliche Zahl neu aufgenommener Dateien (zwischen
  2 und 13) steht erst nach Implementierung fest.
- **KL-3 · Produktbefund #1831 bleibt ungelöst:** eine Design-Entscheidung über den korrekten
  Danger-Rot-Wert ist Voraussetzung für eine künftige Aufnahme von `btn-feature-parity.spec.ts`
  und `theme-bridge.spec.ts`.
- **KL-4 · Reserve bleibt unbearbeitet:** 8 Dateien mit genau zwei roten Testfällen und rund
  28 Dateien mit mehr als zwei roten Testfällen bleiben Reserve für Folge-Scheiben.
- **KL-5 · Filter-C-Kern-Test prüft nur die Positivliste, nicht den vollen 161-Datei-Korpus:**
  die übrigen 27 korrekten `../docs/artifacts/`-Pfade außerhalb der Liste werden nicht
  automatisch überwacht — greift erst, sobald eine der betroffenen Dateien selbst zur
  Aufnahme ansteht.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0054 (Ergänzung/Korrektur am bestehenden Dokument, keine neue ADR-Nummer)
- **Rationale:** Diese Scheibe führt die in ADR-0054 getroffene Grundsatzentscheidung
  (Positivliste, Filter A + B, Drei-Bedingungen-Gate) nur fort — sie berührt keine neue
  Entscheidungsfläche. Das neue Filter-C-Kriterium (keine Schreibpfade in getrackte
  Verzeichnisse) ist eine Präzisierung von Filter A auf derselben Ebene, keine neue
  Grundsatzfrage. Die zwei Korrekturen (Filter-A-Fehlbehauptung, Diagnose-Nachtrag) werden
  deshalb als Ergänzung in ADR-0054 selbst untergebracht statt eine neue ADR-Nummer zu
  vergeben — sie präzisieren den bestehenden Geltungsbereich, statt ihn zu ändern.

## Changelog

- 2026-08-14: Initial spec created
