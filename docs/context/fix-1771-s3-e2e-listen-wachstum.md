# Context: #1771 Scheibe 3 — Wachstum der E2E-Positivliste

**Workflow:** `fix-1771-s3-e2e-listen-wachstum` · **Issue:** #1771 (offen, `priority:high`,
`session:taskforce`) · **Basis:** `origin/main` `1e5e0be9` · **Erstellt:** 2026-08-14

## Request Summary

Die mit Scheibe 2 eingeführte CI-Lane `e2e` fährt 36 Playwright-Specs (173 Testfälle) gegen
einen isolierten Offline-Stack. Scheibe 3 soll die Positivliste `.github/ci_e2e_specs.txt`
wachsen lassen. **PO-Entscheid 2026-08-14:** Diagnose vor Sanierung — Vermessungslauf fahren,
die roten Kandidaten nach **Fehlerursache** gruppieren, nur die größte Gruppe mit gemeinsamer
Wurzel beheben und nach Filter B aufnehmen. Einzelfälle ohne gemeinsame Wurzel werden belegt
zurückgewiesen statt einzeln repariert.

## 🔴 Ausgangsmessung: die Scheibe-3-Formulierung im Issue trägt nicht

Nachgemessen am 2026-08-14 gegen `origin/main` `1e5e0be9`:

| Gemessen | Wert |
|---|---|
| Playwright-Specs gesamt | 161 (davon 19 `*.staging.spec.ts`) |
| Dateien mit `waitForTimeout` (ohne Staging) | 23 |
| Dateien mit `test.skip`/`test.fixme`/`describe.skip` | 16 |
| Kandidatenpool nach Filter A (verschärft) | **87** — unverändert zur S2-Messung |
| Positivliste | 36 — alle noch gültige Kandidaten, **kein Drift** |
| Wachstumsreserve (Kandidat, nicht gelistet) | **51** |
| davon **neu** seit S2-Merge `bb22b8e6`, also nie vermessen | **0** |

**Folge:** Das Issue beschreibt Scheibe 3 als „Wachstum über den `workflow_dispatch`-
Vermessungsmodus". Das trägt nicht — die 51 Reserve-Dateien wurden am 2026-08-13 bereits
vermessen und waren dabei rot. Ein erneuter Vermessungslauf allein liefert **null Zuwachs**.
Wachstum ist nur über Reparatur möglich. (Reproduktion der Messung:
`docs/artifacts/fix-1771-s3-e2e-listen-wachstum/` bzw. Filter-A-Ausdruck aus `ci.yml:244-249`.)

**Das Rohprotokoll des 87er-Vermessungslaufs aus S2 existiert nicht mehr.** Unter
`docs/artifacts/fix-1771-s2-playwright-ci-ampel/` liegen nur Adversary-Reports (15 Dateien,
38 rot — der F001-Beleg) und der Positivlisten-Lauf. Die Ursachen der 51 Roten sind damit
**ungemessen**; sie neu zu erheben ist der Kern dieser Scheibe.

## Related Files

| Datei | Relevanz |
|---|---|
| `.github/ci_e2e_specs.txt` | Positivliste (36 Zeilen). Ratsche: darf nur WACHSEN. Kopf dokumentiert Filter A + B |
| `.github/workflows/ci.yml:176-344` | Job `e2e`. Zeile 200/201: `E2E_MIN_SPECS: 36`, `E2E_MIN_EXECUTED: 173`. Zeile 232-254: Modus-Umschaltung Positivliste ↔ Vermessung |
| `.github/scripts/e2e_gate.py` | Drei-Bedingungen-Auswertung (`unexpected==0`, `skipped==0`, `expected>=E2E_MIN_EXECUTED`), fail-closed ohne Schwelle |
| `frontend/e2e/ci-stack.sh` | Isolierter Offline-Stack. `GZ_PORT=8091` Pflicht, `GZ_USER_ID=admin`, `GZ_AUTH_PASS=test1234`, Fixtures `fixtures/openmeteo`, Ports über `GZ_CI_STACK_GO_PORT`/`_PY_PORT` verschiebbar |
| `frontend/playwright.config.ts` | `workers: 1` unter CI, `timeout: 30_000`, `retries: 0`, `webServer` auf Port 4173, `reuseExistingServer: !CI` |
| `frontend/e2e/global.setup.ts` | Login als `E2E_USER ?? 'admin'` + Seed (Trip `e2e-cockpit-test`, drei Fixture-Orte). Zählt als 173. Testfall |
| `frontend/e2e/helpers.ts` | Geteilte Helfer inkl. des in S1 gehärteten `dragDndZoneItem` |
| `docs/adr/0054-playwright-e2e-in-ci-ampel-positivliste.md` | Grundsatzentscheidung: Positivliste statt Ausschlussliste |
| `docs/specs/modules/fix_1771_s2_playwright_ci_ampel.md` | Spec S2 inkl. Abschnitt „Nicht in dieser Scheibe" (Zeilen 294-312) |
| `docs/artifacts/fix-1771-s2-playwright-ci-ampel/stack-verify-script.sh` | Vorlage für den lokalen Stack-Lauf auf freien Ports (8095/8005) |

## Existing Patterns

- **Ratschen-Listen:** `.github/ci_tdd_excludes.txt` (Ausschluss, darf nur schrumpfen) vs.
  `.github/ci_e2e_specs.txt` (Positivliste, darf nur wachsen). ADR-0054 begründet die
  Richtungsumkehr: eine Ausschlussliste setzt eine grüne Grundmenge voraus, die hier
  gemessen nicht existiert.
- **Schwellwerte als `env:` im Job** — Muster `BASELINE_ERRORS` im `svelte-check`-Job
  (`ci.yml:122`).
- **Fail-closed bei fehlendem Nachweis** — `e2e_gate.py::_lade_min_executed`, gleiche Linie
  wie das Frontend-Browser-Gate (#1558).
- **Vermessungsmodus als zweiter Trigger desselben Jobs** statt eigener Workflow-Datei
  (`ci.yml:232`, `workflow_dispatch` mit Input `e2e_vermessung`).

## Dependencies

- **Upstream:** Go-Binary (`cmd/server`), Python-Core (`api.main`), Fixtures
  `fixtures/openmeteo`, Node 22 + Chromium. Der Stack wird pro Lauf frisch hochgefahren.
- **Downstream:** **Jeder PR jeder Session.** `e2e` ist seit S2 einer der 6 Pflicht-Checks
  der Merge-Regel. Eine fälschlich erweiterte Liste färbt die Ampel rot und blockiert alle
  laufenden Arbeitsstränge — der Blast Radius ist projektweit.

## Existing Specs

- `docs/specs/modules/fix_1771_s2_playwright_ci_ampel.md` — Vorgänger-Scheibe, definiert
  Filter A/B, die drei Gate-Bedingungen und den Vermessungsmodus
- `docs/specs/modules/fix_1771_s1_dnd_wartestrategie.md` — Scheibe 1 (Ziehhelfer-Härtung)
- `docs/adr/0054-playwright-e2e-in-ci-ampel-positivliste.md`

## Risks & Considerations

1. 🔴 **Prüfort ≠ Wirkort bei Filter B.** Der S2-Vermessungslauf fuhr alle 87 Kandidaten
   **im Verbund** bei `workers: 1` auf **einer geteilten Datenwurzel**. Der Wirkort ist aber
   die 36er-Positivliste im CI-Job. Eine Datei kann im 87er-Verbund rot und in der Zielmenge
   grün sein (fremder Test hat Daten hinterlassen) — und umgekehrt. Filter-B-Nachweise
   müssen im **Zielverbund** erhoben werden, sonst belegt die Messung etwas anderes als das,
   was später läuft.
2. 🔴 **`E2E_MIN_EXECUTED` wird von Hand gepflegt und trägt keinen Puffer** (F006: „ein
   Puffer in einer Schwelle ist ein Loch"). Jede Listenerweiterung muss beide Zahlen exakt
   nachziehen. Wer Dateien hinzufügt und die Schwelle vergisst, reißt genau das Loch wieder
   auf, das S2 geschlossen hat. Zu prüfen: ob die Zahl aus der Liste **abgeleitet** statt
   gepflegt werden kann (`playwright test --list`).
3. **Laufzeit-Asymmetrie.** Rote Tests kosten das Vielfache der grünen (30-s-Timeouts):
   87 Kandidaten = ~57 min, die 36 grünen = ~130 s. Der Diagnoselauf ist teuer, der
   Ergebnislauf billig.
4. **Parallellauf-Falle.** Playwright teilt Port 4173 mit `reuseExistingServer: !CI`. Ein
   zweiter Lauf — auch aus einer fremden Session — übernimmt still den fremden Preview-Server
   samt fremdem `GZ_API_BASE`. Hat in S2 zwei Messungen unbrauchbar gemacht. Läufe müssen mit
   `CI=1` und auf eigenen Stack-Ports (8095/8005) gefahren werden.
5. **Messaufbau vor Prüfling verdächtigen.** In S2 sahen 61/72 rote Tests wie ein verrotteter
   Korpus aus und waren ein halbseitig gesetztes `GZ_SESSION_SECRET`. Pflicht beim
   Nachstellen: `GZ_REPO_ENV_FILE=/dev/null`, `GZ_API_BASE` + `GZ_E2E_API_PROXY_TARGET` auf
   den eigenen Port, `CI=1`.
6. **Zwei bekannt kaputte Dateien** sind bereits per Filter A ausgeschlossen und dürfen es
   bleiben: `list-routes-btn-migration.spec.ts:26` (fest verdrahteter Hauptrepo-Pfad ⇒
   falsches Grün aus einem Worktree, Verstoß gegen die Pfadregel #1409) und
   `issue-322-wicon-komponente.spec.ts:14` (`__dirname` in ESM). Für TypeScript existiert
   **keine** Pfad-Ratsche, für Python schon (`test_repo_path_hardcoding_ratchet.py`) —
   in #1196 gebucht, eigene Scheibe.
7. **LoC-Limit 250.** Liste + `ci.yml`-Schwellen sind klein; der Verbrauch entsteht durch die
   Reparaturen. Deckel des PO-Entscheids (nur die größte Ursachengruppe) hält das im Rahmen.
8. **Regel-Budget `e2e`:** Prüfdatum 2026-11-11, Fang-Kriterium „mindestens ein PR, in dem
   die Lane eine Regression fängt, die die anderen fünf Checks durchlassen". Diese Scheibe
   ändert das Kriterium nicht — sie vergrößert die Fangfläche.

## Analysis (gemessen 2026-08-14)

### Type

Feature (Erweiterung eines Gates) mit Diagnose-Anteil — kein Bug.

### Der Diagnoselauf

51 Reserve-Kandidaten gegen den isolierten Offline-Stack (Ports 8095/8005, `CI=1`,
`GZ_REPO_ENV_FILE=/dev/null`). Messaufbau vorab validiert: Stack oben, `POST /api/auth/login`
→ **200**. Laufzeit **56 min**.

| Ergebnis | Wert |
|---|---|
| Testfälle | **143 grün / 200 rot / 0 übersprungen** |
| Dateien vollständig grün (Aufnahme ohne jede Reparatur) | **2** — `compare-cross-user-write-block.spec.ts`, `compare-editor-autosave-user-isolation.spec.ts` (je 1 Testfall) |
| Dateien mit mindestens einem Roten | 49 |

### 🔴 Es gibt keine große gemeinsame Wurzel

Drei unabhängige Messungen sagen dasselbe:

1. **Die Roten sind über 52 verschiedene gesuchte UI-Elemente verteilt**, die meisten mit
   1–2 Fällen. Kein Muster trägt mehr als 9 Fälle.
2. **Rot-Quote über die Laufzeit konstant** (52–66 % in fünf chronologischen Blöcken) — bei
   kumulativer Zustandsverschmutzung durch die geteilte Datenwurzel müsste sie ansteigen.
3. **Einzellauf == Verbundlauf, testfallgenau.** Fünf im Verbund rote Dateien einzeln gegen
   frischen Stack gefahren: `alert-rules-editor` 0/21, `trip-edit` 0/9,
   `compare-hub-briefing-times` 6/4, `nav-redesign` 3/4, `issue-758-save-indicator` 5/2 —
   **identisch zum Verbund**.

⇒ Die Roten sind **deterministisch**, keine Flakes, und **nicht** durch den Verbund
verursacht. Das entschärft zugleich Risiko 1 oben: Filter-B-Messungen im Kandidatenverbund
sind für diese Dateien aussagekräftig.

⇒ Der PO-Entscheid „größte Ursachengruppe mit gemeinsamer Wurzel beheben" trifft auf einen
Befund, der eine solche Gruppe **nicht hergibt**.

### Was die Roten stattdessen sind

Von 52 gesuchten Testids existieren **22 im Frontend gar nicht mehr** (`trip-hero`,
`cta-new-trip`, `trip-wizard-*`, `compare-wizard-open-btn` …) — Tests gegen gelöschte UI,
Altbestand des am 2026-07-11 abgeschafften Wizards und Vorgänger-Oberflächen. Die übrigen 30
existieren; dort ist die Ursache Daten, Timing oder ein echter Defekt.

**Ergiebiger als die Ursache ist der Aufwand:** 13 Dateien haben **genau einen** roten
Testfall, 21 höchstens zwei. Sie beweisen durch ihre eigenen grünen Testfälle, dass sie im
isolierten Stack grundsätzlich lauffähig sind (z. B. `trip-detail-actions.spec.ts`: 12 grün /
1 rot) — bei ihnen hakt eine einzelne Prüfung, nicht die Umgebung.

### 🔴🔴 Der Korpus meldet einen echten Produktbefund

Die **einzige** Mehrfach-Wurzel unter den 13 ist kein Testfehler: `btn-feature-parity.spec.ts`
und `theme-bridge.spec.ts` erwarten beide `rgb(179, 58, 42)` (`#b33a2a`) und erhalten
`rgb(168, 50, 50)` (`#a83232`). Am Code nachgesehen ist der Token-Wechsel **unvollständig
geblieben**:

| Stelle | Wert |
|---|---|
| `frontend/src/app.css:161` | `--g-danger: #a83232` ← heute gültig |
| `frontend/src/app.css:19` | `@property --color-destructive { initial-value: rgb(179, 58, 42) }` ← alt |
| `frontend/src/app.css:311/316` | `rgba(179, 58, 42, …)` als Hintergrund, während Zeile 312/313 im selben Block `var(--g-danger)` nutzt ← alt neben neu |
| `frontend/src/routes/_design/+page.svelte:37` | weist `--g-danger` als `#b33a2a` mit Kontrastverhältnis **5.91** aus ← falsche Angabe; derselbe Farbwert steht Zeile 36 als `--g-bad` mit 6.63 |

Zwei E2E-Tests melden das seit unbekannter Zeit, und niemand hat es gelesen — exakt der
Mechanismus, den #1771 beschreibt. Die Design-Seite der Anwendung zeigt damit ein falsches
Kontrastverhältnis, und Kontrast ist ein PO-Leitprinzip. **Das ist ein Produktbefund, keine
Testanpassung** — welcher Wert gelten soll, ist eine Design-Entscheidung und gehört nicht in
diese Scheibe.

### Scope Assessment

- Sicher einlösbar ohne fachliche Entscheidung: **2 Dateien** (+2 Testfälle)
- Strukturelles Loch aus Befund 1 (Schwellen ungebunden an die Liste): **1 Wächter**
- Risiko-Level: **HIGH** — jede Änderung an Liste oder Schwellen wirkt auf die Pflicht-Ampel
  aller Sessions

### Open Questions

- [x] Ist der Verbund die Ursache? — **Nein**, gemessen (Einzellauf == Verbund)
- [x] Gibt es eine große gemeinsame Wurzel? — **Nein**, gemessen (52 Muster, kein Cluster)
- [ ] Wie wird die Scheibe neu zugeschnitten, nachdem der Entscheid vom 2026-08-14 auf einer
      widerlegten Annahme beruht? → PO vorgelegt

## Offen für die Analyse-Phase

- Wie werden die Roten **gruppiert**? Aus dem JSON-Report lassen sich Fehlermeldung und
  Fehlerort je Testfall ziehen; die Gruppierung muss reproduzierbar sein, nicht per Auge.
- Wird der Diagnoselauf lokal oder per `workflow_dispatch` auf dem Runner gefahren? Der
  Runner ist der Wirkort, wurde für den Vermessungsmodus aber **noch nie benutzt** (kein
  `workflow_dispatch`-Lauf in der Historie) — der erste Lauf ist zugleich ein Nachweis für
  AC-8 aus S2.
- Ab welcher Gruppengröße lohnt die Reparatur? Der PO-Entscheid sagt „größte Gruppe mit
  gemeinsamer Wurzel" — die Schwelle gehört in die Spec, nicht ins Bauchgefühl.
